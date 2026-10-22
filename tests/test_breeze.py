from __future__ import annotations

import json
import struct
import wave
from pathlib import Path

import pytest
from overwatch_voice_lines import breeze, cli

RATE = 24000


def write_wav(path: Path, seconds: float, value: int = 800) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = struct.pack("<h", value) * int(RATE * seconds)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(RATE)
        handle.writeframes(frames)


def row(
    identifier: str,
    *,
    text: str = "A line.",
    duration: float = 2.0,
    section: str = "Voice Lines",
    language: str = "en",
    verbal: bool = True,
    has_wav: bool = True,
) -> dict:
    return {
        "id": identifier,
        "text": text,
        "duration_s": duration,
        "section": section,
        "context": "Default",
        "language": language,
        "verbal": verbal,
        "wav_path": f"wav/{identifier}.wav" if has_wav else "",
    }


@pytest.fixture()
def dataset(tmp_path: Path) -> Path:
    directory = tmp_path / "widowmaker"
    rows = [
        row("good-1", text="The Countess was feared by all.", duration=2.5),
        row("good-2", text="A single death can change everything.", duration=2.2),
        row("good-3", text="The performance is about to begin.", duration=2.4),
        row("short", text="No.", duration=0.5),
        row("nonverbal", text="grunt", verbal=False),
        row("french", text="Cible repérée.", language="fr"),
        row("parenthetical", text="Hello. (to Reaper)"),
        row("missing", text="Gone.", has_wav=False),
        row("duplicate", text="The Countess was feared by all.", duration=2.5),
    ]
    for item in rows:
        if item["wav_path"]:
            write_wav(directory / item["wav_path"], float(item["duration_s"]))
    (directory / "metadata.jsonl").write_text(
        "".join(json.dumps(item) + "\n" for item in rows), encoding="utf-8"
    )
    (directory / "report.json").write_text(
        json.dumps(
            {
                "character": "Widowmaker",
                "page": "Widowmaker/Quotes",
                "revision": 7,
                "source_url": "https://overwatch.fandom.com/wiki/Widowmaker/Quotes",
            }
        ),
        encoding="utf-8",
    )
    return directory


def test_select_clips_filters_and_reaches_target(dataset: Path):
    rows = [json.loads(line) for line in (dataset / "metadata.jsonl").read_text().splitlines()]
    clips = breeze.select_clips(rows, dataset_dir=dataset, target_seconds=5.0)
    assert {clip.id for clip in clips} == {"good-1", "good-2", "good-3"}
    assert all(clip.language == "en" for clip in clips)
    assert sum(clip.duration_s for clip in clips) >= 5.0


def test_select_clips_can_include_every_language(dataset: Path):
    rows = [json.loads(line) for line in (dataset / "metadata.jsonl").read_text().splitlines()]
    clips = breeze.select_clips(rows, dataset_dir=dataset, language="all", target_seconds=10.0)
    assert "french" in {clip.id for clip in clips}


def test_reference_wav_is_mono_24k_with_silence(dataset: Path, tmp_path: Path):
    rows = [json.loads(line) for line in (dataset / "metadata.jsonl").read_text().splitlines()]
    clips = breeze.select_clips(rows, dataset_dir=dataset, target_seconds=5.0)
    destination = tmp_path / "reference.wav"
    duration = breeze.write_reference_wav(clips, destination)

    with wave.open(str(destination), "rb") as handle:
        assert handle.getnchannels() == 1
        assert handle.getsampwidth() == 2
        assert handle.getframerate() == RATE
        assert handle.getnframes() / RATE == pytest.approx(duration)
    speech = sum(clip.duration_s for clip in clips)
    assert duration > speech
    assert duration < speech + 2.0


def test_build_pack_writes_importable_files(dataset: Path, tmp_path: Path):
    rows = [json.loads(line) for line in (dataset / "metadata.jsonl").read_text().splitlines()]
    pack = breeze.build_pack(
        pack_dir=tmp_path / "pack",
        dataset_dir=dataset,
        rows=rows,
        name="Widowmaker",
        character="Widowmaker",
        page="Widowmaker/Quotes",
        revision=7,
        source_url="https://overwatch.fandom.com/wiki/Widowmaker/Quotes",
        target_seconds=5.0,
    )

    assert pack.wav_path.is_file()
    assert pack.transcript_path.read_text() == " ".join(clip.text for clip in pack.clips)
    assert not pack.transcript_path.read_text().endswith("\n")
    assert (pack.directory / "import.sh").stat().st_mode & 0o111
    assert "REFERENCE AUDIO" in (pack.directory / "README.md").read_text()
    manifest = json.loads(pack.manifest_path.read_text())
    assert manifest["name"] == "Widowmaker"
    assert manifest["ref_text"] == pack.transcript
    assert manifest["metadata"]["character"] == "Widowmaker"
    assert manifest["metadata"]["source_revision"] == "7"
    assert len(manifest["clips"]) == 3


def test_upload_pack_posts_multipart_fields(dataset: Path, tmp_path: Path, monkeypatch):
    rows = [json.loads(line) for line in (dataset / "metadata.jsonl").read_text().splitlines()]
    pack = breeze.build_pack(
        pack_dir=tmp_path / "pack",
        dataset_dir=dataset,
        rows=rows,
        name="Widowmaker",
        character="Widowmaker",
        page="Widowmaker/Quotes",
        revision=7,
        source_url="https://overwatch.fandom.com/wiki/Widowmaker/Quotes",
        target_seconds=5.0,
    )
    captured = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps(
                {"id": "abc", "name": "widow", "seconds": 6.0, "saved": True}
            ).encode()

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr(breeze.urllib.request, "urlopen", fake_urlopen)
    result = breeze.upload_pack(pack, "http://127.0.0.1:8080/", save_name="widow")

    assert result["id"] == "abc"
    request = captured["request"]
    assert request.full_url == "http://127.0.0.1:8080/v1/voices"
    assert request.headers["Content-type"].startswith("multipart/form-data; boundary=")
    body = request.data
    assert b'name="ref_audio"' in body
    assert b'name="ref_text"' in body
    assert pack.transcript.encode() in body
    assert b"\r\n\r\nwidow\r\n" in body
    assert pack.wav_path.read_bytes() in body


def test_cli_export_breeze(dataset: Path, tmp_path: Path, capsys):
    out = tmp_path / "out"
    code = cli.main(
        [
            "--data-dir",
            str(dataset.parent),
            "export-breeze",
            "Widowmaker",
            "--out",
            str(out),
            "--target-seconds",
            "5",
        ]
    )
    assert code == 0
    assert (out / "reference.wav").is_file()
    assert "Breeze reference" in capsys.readouterr().out


def test_cli_export_breeze_without_dataset(tmp_path: Path, capsys):
    code = cli.main(["--data-dir", str(tmp_path), "export-breeze", "Nobody"])
    assert code == 1
    assert "no prepared dataset" in capsys.readouterr().err
