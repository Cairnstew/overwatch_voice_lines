from __future__ import annotations

import json
from pathlib import Path

import pytest
from overwatch_voice_lines import dataset
from overwatch_voice_lines.models import Utterance


def utterance(
    filename: str,
    *,
    text: str = "Hello.",
    speaker: str = "Widowmaker",
    character: str = "Widowmaker",
    verbal: bool = True,
    missing: bool = False,
    section: str = "Voice Lines",
    context: str = "Default",
    language: str = "en",
) -> Utterance:
    return Utterance(
        character=character,
        speaker=speaker,
        section=section,
        context=context,
        text=text,
        translation=None,
        language=language,
        verbal=verbal,
        audio_file=filename,
        source_page="Widowmaker/Quotes",
        source_revision=1,
        file_url=None,
        missing=missing,
    )


@pytest.fixture()
def fake_audio(monkeypatch):
    """Replace ffmpeg with a byte copy and give every clip a fixed duration."""

    durations: dict[str, float] = {}

    def convert(source: Path, destination: Path, **kwargs) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())
        durations.setdefault(destination.name, 2.0)

    monkeypatch.setattr(dataset, "convert_to_wav", convert)
    monkeypatch.setattr(dataset, "probe_duration", lambda path: durations.get(path.name, 2.0))
    return durations


def prepare(utterances, tmp_path: Path, **overrides):
    options = {
        "out_dir": tmp_path,
        "character": "Widowmaker",
        "character_slug": "widowmaker",
        "page": "Widowmaker/Quotes",
        "source_url": "https://overwatch.fandom.com/wiki/Widowmaker",
        "revision": 1,
        "database_name": "Widowmaker",
    }
    options.update(overrides)
    return dataset.prepare_dataset(utterances, **options)


def read_split(path: Path) -> set[str]:
    return {json.loads(line)["id"] for line in path.read_text().splitlines() if line}


def write_raw(tmp_path: Path, filename: str, payload: bytes) -> None:
    raw = tmp_path / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    (raw / dataset.raw_filename(filename)).write_bytes(payload)


def test_naming_helpers_are_stable():
    assert dataset.slugify("Widowmaker (Overwatch 1)") == "widowmaker-overwatch-1"
    assert dataset.slugify("  ") == "character"
    assert dataset.raw_filename("Widowmaker - Hello.ogg") == dataset.raw_filename(
        "Widowmaker - Hello.ogg"
    )
    assert dataset.raw_filename("Widowmaker - Hello.OGG").endswith(".ogg")
    assert dataset.clip_id("widowmaker", "A.ogg") == dataset.clip_id("widowmaker", "A.ogg")
    assert dataset.clip_id("widowmaker", "A.ogg") != dataset.clip_id("widowmaker", "B.ogg")


def test_prepare_filters_and_reports(tmp_path, fake_audio):
    write_raw(tmp_path, "Widowmaker - Hello.ogg", b"one")
    write_raw(tmp_path, "Widowmaker - Again.ogg", b"two")
    write_raw(tmp_path, "Widowmaker - Copy.ogg", b"one")  # duplicate bytes
    rows = [
        utterance("Widowmaker - Hello.ogg", text="Hello."),
        utterance("Widowmaker - Again.ogg", text="Hello."),
        utterance("Widowmaker - Copy.ogg", text="Copy."),
        utterance("Ana - Hi.ogg", text="Hi.", speaker="Ana"),
        utterance("Widowmaker - Grunt.ogg", text="grunt", verbal=False),
        utterance("Widowmaker - Gone.ogg", missing=True),
        utterance("Widowmaker - No raw.ogg"),
    ]
    report = prepare(rows, tmp_path)

    assert len(report.clips) == 2
    assert report.duplicates == 1
    assert report.skipped_speaker == 1
    assert report.skipped_nonverbal == 1
    assert report.skipped_missing == 1
    assert report.skipped_no_raw == 1
    assert {clip.audio_file for clip in report.clips} == {
        "Widowmaker - Hello.ogg",
        "Widowmaker - Again.ogg",
    }
    assert report.train_count + report.val_count == 2

    metadata = dataset.read_metadata(tmp_path)
    assert len(metadata) == 2
    assert {row["id"] for row in metadata} == {clip.id for clip in report.clips}
    assert all(row["wav_path"].startswith("wav/") for row in metadata)
    assert all(row["raw_path"].startswith("raw/") for row in metadata)
    assert (tmp_path / "metadata.csv").exists()
    assert (tmp_path / "dataset_card.md").read_text().startswith("# Widowmaker")


def test_nonverbal_can_be_included(tmp_path, fake_audio):
    write_raw(tmp_path, "Widowmaker - Grunt.ogg", b"grunt")
    write_raw(tmp_path, "Widowmaker - Word.ogg", b"word")
    rows = [
        utterance("Widowmaker - Grunt.ogg", text="grunt", verbal=False),
        utterance("Widowmaker - Word.ogg", text="Word."),
    ]
    report = prepare(rows, tmp_path, include_nonverbal=True)
    assert len(report.clips) == 2
    assert report.skipped_nonverbal == 0


def test_duration_filter(tmp_path, fake_audio):
    write_raw(tmp_path, "Widowmaker - Long.ogg", b"long")
    identifier = dataset.clip_id("widowmaker", "Widowmaker - Long.ogg")
    fake_audio[f"{identifier}.wav"] = 120.0
    report = prepare([utterance("Widowmaker - Long.ogg")], tmp_path, max_duration=60)
    assert report.clips == []
    assert report.skipped_duration == 1
    assert not list((tmp_path / "wav").glob("*.wav"))


def test_split_is_deterministic_and_groups_equal_text(tmp_path, fake_audio):
    for index in range(6):
        write_raw(tmp_path, f"Widowmaker - Line {index}.ogg", f"line-{index}".encode())
    rows = [
        utterance(f"Widowmaker - Line {index}.ogg", text=f"Line {index}.") for index in range(6)
    ]
    rows += [
        utterance("Widowmaker - Repeat A.ogg", text="Same line."),
        utterance("Widowmaker - Repeat B.ogg", text="Same line."),
    ]
    for name in ("Widowmaker - Repeat A.ogg", "Widowmaker - Repeat B.ogg"):
        write_raw(tmp_path, name, name.encode())

    report = prepare(rows, tmp_path, val_fraction=0.5)
    train = read_split(tmp_path / "splits/train.jsonl")
    val = read_split(tmp_path / "splits/val.jsonl")
    assert train | val == {clip.id for clip in report.clips}
    assert not train & val
    assert report.train_count + report.val_count == 8

    repeat_ids = {dataset.clip_id("widowmaker", f"Widowmaker - Repeat {x}.ogg") for x in "AB"}
    assert repeat_ids <= train or repeat_ids <= val

    first = {clip.id: clip.id in val for clip in report.clips}
    prepare(rows, tmp_path, val_fraction=0.5)
    second = {clip_id: clip_id in read_split(tmp_path / "splits/val.jsonl") for clip_id in first}
    assert first == second


def test_val_fraction_zero_puts_everything_in_train(tmp_path, fake_audio):
    write_raw(tmp_path, "Widowmaker - One.ogg", b"one")
    write_raw(tmp_path, "Widowmaker - Two.ogg", b"two")
    report = prepare(
        [utterance("Widowmaker - One.ogg"), utterance("Widowmaker - Two.ogg")],
        tmp_path,
        val_fraction=0,
    )
    assert report.train_count == 2
    assert report.val_count == 0
    assert (tmp_path / "splits/val.jsonl").read_text() == ""


def test_prepare_can_limit(tmp_path, fake_audio):
    for index in range(3):
        write_raw(tmp_path, f"Widowmaker - {index}.ogg", str(index).encode())
    rows = [utterance(f"Widowmaker - {index}.ogg", text=f"Line {index}.") for index in range(3)]
    report = prepare(rows, tmp_path, limit=2)
    assert len(report.clips) == 2
