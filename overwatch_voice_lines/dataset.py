"""Download wiki audio and build a voice-clone-ready dataset directory."""

from __future__ import annotations

import csv
import hashlib
import json
import logging
import re
import time
import urllib.error
import urllib.request
from collections import Counter
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .audio import AudioError, convert_to_wav, probe_duration, sha256_file
from .models import Clip, Utterance

LOGGER = logging.getLogger(__name__)

METADATA_FIELDS = [
    "id",
    "character",
    "speaker",
    "section",
    "context",
    "text",
    "translation",
    "language",
    "verbal",
    "audio_file",
    "wav_path",
    "raw_path",
    "duration_s",
    "sample_rate",
    "sha256",
    "source_page",
    "source_url",
]


# ---------------------------------------------------------------------------
# Naming
# ---------------------------------------------------------------------------


def slugify(value: str) -> str:
    value = value.strip().casefold()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value or "character"


def safe_stem(filename: str, limit: int = 80) -> str:
    stem = filename.rsplit(".", 1)[0]
    stem = re.sub(r"[^A-Za-z0-9]+", "-", stem).strip("-").casefold()
    return stem[:limit].rstrip("-") or "clip"


def raw_filename(filename: str) -> str:
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else "ogg"
    digest = hashlib.sha1(filename.encode("utf-8")).hexdigest()[:10]
    return f"{digest}_{safe_stem(filename)}.{extension}"


def clip_id(character_slug: str, filename: str) -> str:
    digest = hashlib.sha1(filename.encode("utf-8")).hexdigest()[:8]
    return f"{character_slug}__{safe_stem(filename, 50)}__{digest}"


def same_speaker(left: str, right: str) -> bool:
    def normalise(value: str) -> str:
        return re.sub(r"[^a-z0-9]", "", value.casefold())

    return normalise(left) == normalise(right)


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------


@dataclass
class DownloadReport:
    downloaded: int = 0
    skipped: int = 0
    missing: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "downloaded": self.downloaded,
            "skipped_existing": self.skipped,
            "missing": self.missing,
            "failed": self.failed,
            "errors": self.errors,
        }


def _download_one(
    utterance: Utterance,
    destination: Path,
    *,
    user_agent: str,
    timeout: float,
    attempts: int = 3,
) -> None:
    if not utterance.file_url:
        raise RuntimeError("no file_url")
    temporary = destination.with_suffix(destination.suffix + ".part")
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            request = urllib.request.Request(
                utterance.file_url,
                headers={"User-Agent": user_agent, "Accept": "*/*"},
            )
            with urllib.request.urlopen(request, timeout=timeout) as response:
                temporary.parent.mkdir(parents=True, exist_ok=True)
                with temporary.open("wb") as handle:
                    while chunk := response.read(1024 * 256):
                        handle.write(chunk)
            if temporary.stat().st_size == 0:
                raise RuntimeError("downloaded zero bytes")
            temporary.replace(destination)
            return
        except (urllib.error.URLError, TimeoutError, OSError, RuntimeError) as exc:
            last_error = exc
            temporary.unlink(missing_ok=True)
            if attempt < attempts:
                delay = 2**attempt
                LOGGER.warning(
                    "download failed (%s), retrying %s in %ss",
                    exc,
                    utterance.audio_file,
                    delay,
                )
                time.sleep(delay)
    raise RuntimeError(f"download failed after {attempts} attempts: {last_error}")


def download_utterances(
    utterances: Iterable[Utterance],
    raw_dir: Path,
    *,
    user_agent: str,
    force: bool = False,
    workers: int = 4,
    timeout: float = 90.0,
) -> DownloadReport:
    """Download every referenced file once, honouring a local cache."""

    unique: dict[str, Utterance] = {}
    for utterance in utterances:
        existing = unique.get(utterance.audio_file)
        if existing is None or (existing.missing and not utterance.missing):
            unique[utterance.audio_file] = utterance

    report = DownloadReport()
    jobs: list[tuple[Utterance, Path]] = []
    for utterance in unique.values():
        if utterance.missing or not utterance.file_url:
            report.missing += 1
            continue
        destination = raw_dir / raw_filename(utterance.audio_file)
        if destination.exists() and destination.stat().st_size > 0 and not force:
            report.skipped += 1
            continue
        jobs.append((utterance, destination))

    if not jobs:
        return report

    raw_dir.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {
            pool.submit(
                _download_one,
                utterance,
                destination,
                user_agent=user_agent,
                timeout=timeout,
            ): utterance
            for utterance, destination in jobs
        }
        for future in as_completed(futures):
            utterance = futures[future]
            try:
                future.result()
                report.downloaded += 1
                LOGGER.debug("downloaded %s", utterance.audio_file)
            except Exception as exc:
                report.failed += 1
                message = f"{utterance.audio_file}: {exc}"
                report.errors.append(message)
                LOGGER.warning("could not download %s", message)

    return report


# ---------------------------------------------------------------------------
# Prepare
# ---------------------------------------------------------------------------


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=METADATA_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _split_bucket(text: str, speaker: str) -> int:
    normalised = re.sub(r"\s+", " ", text.casefold()).strip()
    digest = hashlib.sha1(f"{speaker.casefold()}\x00{normalised}".encode()).hexdigest()
    return int(digest[:8], 16) % 10_000


def _dataset_card(
    *,
    name: str,
    character: str,
    page: str,
    revision: int | None,
    source_url: str,
    clips: list[Clip],
    train_count: int,
    val_count: int,
    sample_rate: int,
    generated_at: str,
) -> str:
    sections = Counter(clip.section for clip in clips)
    languages = Counter(clip.language for clip in clips)
    speakers = Counter(clip.speaker for clip in clips)
    total_seconds = sum(clip.duration_s for clip in clips)
    lines = [
        f"# {name} — Overwatch voice line dataset",
        "",
        f"Prepared for voice cloning from `{page}`"
        + (f" (revision {revision})" if revision else "")
        + ".",
        f"Generated {generated_at} by `overwatch-voice-lines`.",
        "",
        "## Summary",
        "",
        "| | |",
        "|---|---|",
        f"| Character | {character} |",
        f"| Clips | {len(clips)} |",
        f"| Audio | {total_seconds / 60:.1f} min, mono {sample_rate} Hz, 16-bit PCM wav |",
        f"| Splits | train {train_count}, val {val_count} |",
        f"| Source | {source_url} |",
        "",
        "## Sections",
        "",
        "| Section | Clips |",
        "|---|---|",
    ]
    lines += [f"| {section} | {count} |" for section, count in sections.most_common()]
    lines += ["", "## Languages", "", "| Language | Clips |", "|---|---|"]
    lines += [f"| {language or 'und'} | {count} |" for language, count in languages.most_common()]
    lines += ["", "## Speakers", "", "| Speaker | Clips |", "|---|---|"]
    lines += [f"| {speaker} | {count} |" for speaker, count in speakers.most_common()]
    lines += [
        "",
        "## Files",
        "",
        "| Path | Contents |",
        "|---|---|",
        "| `metadata.jsonl` | One JSON object per clip with transcript and provenance |",
        "| `metadata.csv` | The same table as CSV |",
        "| `wav/` | Prepared mono wav files, named by clip id |",
        "| `raw/` | Original wiki files (ogg/mp3/wav) |",
        "| `splits/train.jsonl`, `splits/val.jsonl` | Deterministic train/validation split |",
        "| `quotes.jsonl` | Every parsed utterance including missing/unusable files |",
        "| `report.json` | Counts, warnings and failures from the build |",
        "",
        "The split is derived from a hash of the normalised text, so identical",
        "lines never straddle train and validation, and re-running the build keeps",
        "the same assignment. Non-verbal clips (grunts, gasps) are skipped by",
        "default; pass `--include-nonverbal` to keep them in the dataset.",
        "",
        "## Licence and intended use",
        "",
        "Overwatch audio and character voices are © Blizzard Entertainment.",
        "Wiki text is available under CC BY-SA; see the source page for",
        "attribution. This dataset is intended for personal research and",
        "experimentation with voice cloning. Do not redistribute the audio or use",
        "a cloned voice for impersonation, harassment, or commercial purposes.",
        "Respect Blizzard's terms and the rights of the original voice actors.",
        "",
    ]
    return "\n".join(lines)


@dataclass
class PrepareReport:
    clips: list[Clip] = field(default_factory=list)
    skipped_nonverbal: int = 0
    skipped_speaker: int = 0
    skipped_missing: int = 0
    skipped_no_raw: int = 0
    skipped_duration: int = 0
    duplicates: int = 0
    conversion_errors: list[str] = field(default_factory=list)
    train_count: int = 0
    val_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "clips": len(self.clips),
            "train": self.train_count,
            "val": self.val_count,
            "skipped_nonverbal": self.skipped_nonverbal,
            "skipped_speaker": self.skipped_speaker,
            "skipped_missing_file": self.skipped_missing,
            "skipped_no_raw_file": self.skipped_no_raw,
            "skipped_duration": self.skipped_duration,
            "duplicates": self.duplicates,
            "conversion_errors": self.conversion_errors,
        }


def prepare_dataset(
    utterances: Iterable[Utterance],
    *,
    out_dir: Path,
    character: str,
    character_slug: str,
    page: str,
    source_url: str,
    revision: int | None,
    database_name: str,
    sample_rate: int = 24000,
    val_fraction: float = 0.1,
    target_speaker_only: bool = True,
    include_nonverbal: bool = False,
    min_duration: float = 0.25,
    max_duration: float = 60.0,
    normalize: bool = True,
    trim_silence: bool = False,
    force: bool = False,
    limit: int | None = None,
) -> PrepareReport:
    """Convert downloaded files into wav clips and write the dataset."""

    report = PrepareReport()
    raw_dir = out_dir / "raw"
    wav_dir = out_dir / "wav"
    quotes = list(utterances)

    seen_files: set[str] = set()
    seen_hashes: dict[str, str] = {}
    rows: list[dict[str, Any]] = []
    considered = 0

    for utterance in quotes:
        if target_speaker_only and not same_speaker(utterance.speaker, character):
            report.skipped_speaker += 1
            continue
        if not include_nonverbal and not utterance.verbal:
            report.skipped_nonverbal += 1
            continue
        if utterance.missing or not utterance.audio_file:
            report.skipped_missing += 1
            continue
        if utterance.audio_file in seen_files:
            continue
        seen_files.add(utterance.audio_file)

        if limit is not None and considered >= limit:
            break
        considered += 1

        source = raw_dir / raw_filename(utterance.audio_file)
        if not source.exists() or source.stat().st_size == 0:
            report.skipped_no_raw += 1
            continue

        digest = sha256_file(source)
        if digest in seen_hashes:
            report.duplicates += 1
            continue
        seen_hashes[digest] = utterance.audio_file

        identifier = clip_id(character_slug, utterance.audio_file)
        wav_path = wav_dir / f"{identifier}.wav"
        try:
            if force or not wav_path.exists():
                convert_to_wav(
                    source,
                    wav_path,
                    sample_rate=sample_rate,
                    normalize=normalize,
                    trim_silence=trim_silence,
                )
            duration = probe_duration(wav_path)
        except AudioError as exc:
            report.conversion_errors.append(f"{utterance.audio_file}: {exc}")
            LOGGER.warning("conversion failed for %s: %s", utterance.audio_file, exc)
            continue

        if duration < min_duration or duration > max_duration:
            report.skipped_duration += 1
            wav_path.unlink(missing_ok=True)
            continue

        clip = Clip(
            id=identifier,
            character=character,
            speaker=utterance.speaker,
            section=utterance.section,
            context=utterance.context,
            text=utterance.text,
            translation=utterance.translation or "",
            language=utterance.language,
            verbal=utterance.verbal,
            audio_file=utterance.audio_file,
            raw_path=str(source.relative_to(out_dir)),
            wav_path=str(wav_path.relative_to(out_dir)),
            duration_s=round(duration, 3),
            sample_rate=sample_rate,
            sha256=digest,
            source_page=page,
            source_url=source_url,
        )
        report.clips.append(clip)

    report.clips.sort(key=lambda clip: (clip.section.casefold(), clip.context.casefold(), clip.id))
    rows = [clip.to_dict() for clip in report.clips]
    _write_jsonl(out_dir / "metadata.jsonl", rows)
    _write_csv(out_dir / "metadata.csv", rows)

    if val_fraction <= 0:
        train = report.clips
        val: list[Clip] = []
    else:
        cutoff = int(max(0.0, min(1.0, val_fraction)) * 10_000)
        train = []
        val = []
        for clip in report.clips:
            bucket = _split_bucket(clip.text, clip.speaker)
            (val if bucket < cutoff else train).append(clip)
        if not val and len(train) > 1:
            val.append(train.pop())
        if not train and len(val) > 1:
            train.append(val.pop())
    report.train_count = len(train)
    report.val_count = len(val)
    _write_jsonl(out_dir / "splits" / "train.jsonl", (clip.to_dict() for clip in train))
    _write_jsonl(out_dir / "splits" / "val.jsonl", (clip.to_dict() for clip in val))

    generated_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    card = _dataset_card(
        name=database_name,
        character=character,
        page=page,
        revision=revision,
        source_url=source_url,
        clips=report.clips,
        train_count=report.train_count,
        val_count=report.val_count,
        sample_rate=sample_rate,
        generated_at=generated_at,
    )
    (out_dir / "dataset_card.md").write_text(card, encoding="utf-8")
    return report


def write_report(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def read_metadata(out_dir: Path) -> list[dict[str, Any]]:
    path = out_dir / "metadata.jsonl"
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows
