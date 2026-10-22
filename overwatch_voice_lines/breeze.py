"""Export a prepared dataset as a Breeze-TTS WebUI reference pack.

Breeze clones from a single reference clip plus its exact transcript.  The
WebUI's clone/direction/changer panels take that pair directly, and the server
can persist it as a saved ``.breeze`` voice through ``POST /v1/voices``.

This module turns a whole prepared dataset into one 5-15 second reference clip
(concatenated from the cleanest target-speaker lines), a transcript that
matches it, and the small set of files needed to import it by hand or with one
curl command.
"""

from __future__ import annotations

import json
import re
import secrets
import urllib.error
import urllib.request
import wave
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Breeze's own guidance: five to fifteen seconds of clean speech works best.
MIN_REFERENCE_SECONDS = 5.0
MAX_REFERENCE_SECONDS = 15.0

# Prefer neutral, studio-like lines over combat shouts and processed radio
# chatter.  Values are added to a duration/text score below.
SECTION_SCORE = {
    "voice lines": 4.0,
    "chatter": 3.5,
    "abilities": 3.0,
    "call-outs": 2.0,
    "mission specific": 1.5,
    "interactions": 1.5,
    "pve": 1.0,
    "communication": 0.5,
    "cosmetics": 0.0,
    "skin-specific": 0.0,
    "map-specific": -0.5,
    "event-specific": -0.5,
    "emotes": -1.0,
    "eliminations": -1.5,
    "non-verbal": -10.0,
    "non-languages": -10.0,
}


class BreezeError(RuntimeError):
    """A Breeze reference pack could not be built or uploaded."""


@dataclass
class ReferenceClip:
    id: str
    text: str
    section: str
    context: str
    duration_s: float
    wav_path: Path
    language: str
    score: float = 0.0


@dataclass
class BreezePack:
    directory: Path
    name: str
    transcript: str
    description: str
    duration_s: float
    clips: list[ReferenceClip] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)

    @property
    def wav_path(self) -> Path:
        return self.directory / "reference.wav"

    @property
    def transcript_path(self) -> Path:
        return self.directory / "reference.txt"

    @property
    def manifest_path(self) -> Path:
        return self.directory / "voice.json"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "ref_text": self.transcript,
            "description": self.description,
            "duration_s": round(self.duration_s, 3),
            "reference_wav": self.wav_path.name,
            "transcript_file": self.transcript_path.name,
            "metadata": self.metadata,
            "clips": [
                {
                    "id": clip.id,
                    "text": clip.text,
                    "section": clip.section,
                    "context": clip.context,
                    "duration_s": round(clip.duration_s, 3),
                    "language": clip.language,
                    "score": round(clip.score, 3),
                }
                for clip in self.clips
            ],
        }


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------


def _score_clip(row: dict[str, Any], text: str, duration: float) -> tuple[float, int]:
    words = len(text.split())
    score = SECTION_SCORE.get(str(row.get("section", "")).casefold(), 0.0)
    score -= 0.6 * abs(duration - 3.2)
    score += min(words, 8) * 0.06
    if words < 3:
        score -= 0.8
    if duration < 1.5:
        score -= 0.4
    # Lines with quoted words or stage directions are less predictable as a
    # neutral reference; only penalise quotes lightly, they are still valid.
    if text.count('"') >= 2:
        score -= 0.3
    return score, words


def select_clips(
    rows: Iterable[dict[str, Any]],
    *,
    dataset_dir: Path,
    language: str = "en",
    target_seconds: float = 10.0,
    min_clip_seconds: float = 1.2,
    max_clip_seconds: float = 8.0,
    max_clips: int = 8,
) -> list[ReferenceClip]:
    """Pick clean, varied target-speaker clips up to ``target_seconds``."""

    target = max(MIN_REFERENCE_SECONDS, min(MAX_REFERENCE_SECONDS, target_seconds))
    candidates: list[ReferenceClip] = []
    seen_text: set[str] = set()

    for row in rows:
        if not row.get("verbal", True):
            continue
        if language != "all" and str(row.get("language", "")) != language:
            continue
        text = re.sub(r"\s+", " ", str(row.get("text", ""))).strip()
        if not text or re.search(r"[()[\]{}]", text):
            continue
        try:
            duration = float(row.get("duration_s", 0.0))
        except (TypeError, ValueError):
            continue
        if not min_clip_seconds <= duration <= max_clip_seconds:
            continue
        normalised = re.sub(r"\W+", " ", text.casefold()).strip()
        if not normalised or normalised in seen_text:
            continue
        wav_path = dataset_dir / str(row.get("wav_path", ""))
        if not wav_path.is_file():
            continue
        seen_text.add(normalised)
        score, _ = _score_clip(row, text, duration)
        candidates.append(
            ReferenceClip(
                id=str(row.get("id", wav_path.stem)),
                text=text,
                section=str(row.get("section", "")),
                context=str(row.get("context", "")),
                duration_s=duration,
                wav_path=wav_path,
                language=str(row.get("language", "")),
                score=score,
            )
        )

    candidates.sort(key=lambda clip: (-clip.score, clip.id))
    selected: list[ReferenceClip] = []
    total = 0.0
    for clip in candidates:
        if total >= target or len(selected) >= max_clips:
            break
        # ``target`` is a preference, not a hard cap: one more line may be
        # needed to get above the 5 s floor.  Never exceed Breeze's 15 s max.
        if total + clip.duration_s > MAX_REFERENCE_SECONDS:
            continue
        selected.append(clip)
        total += clip.duration_s

    if not selected:
        raise BreezeError(
            "no usable reference clips (need verbal, non-empty, "
            f"{min_clip_seconds:.1f}-{max_clip_seconds:.1f} s target-speaker "
            f"clips in language {language!r})"
        )
    if total < MIN_REFERENCE_SECONDS:
        raise BreezeError(
            f"only {total:.1f}s of usable speech found; Breeze wants at least "
            f"{MIN_REFERENCE_SECONDS:.0f}s (try --language all or a lower --min-clip-seconds)"
        )
    return selected


# ---------------------------------------------------------------------------
# Audio
# ---------------------------------------------------------------------------


def _silence(rate: int, seconds: float) -> bytes:
    if seconds <= 0:
        return b""
    return b"\x00\x00" * int(rate * seconds)


def write_reference_wav(
    clips: list[ReferenceClip],
    destination: Path,
    *,
    gap_seconds: float = 0.3,
    lead_seconds: float = 0.15,
    tail_seconds: float = 0.4,
) -> float:
    """Concatenate clips into one mono 16-bit wav, returning its duration."""

    if not clips:
        raise BreezeError("no clips to concatenate")
    destination.parent.mkdir(parents=True, exist_ok=True)

    with wave.open(str(clips[0].wav_path), "rb") as first:
        channels = first.getnchannels()
        width = first.getsampwidth()
        rate = first.getframerate()
    if channels != 1 or width != 2:
        raise BreezeError(
            f"{clips[0].wav_path.name} is not mono 16-bit PCM "
            f"({channels} channel(s), {width * 8}-bit); re-run `prepare`"
        )

    parts = [_silence(rate, lead_seconds)]
    for index, clip in enumerate(clips):
        with wave.open(str(clip.wav_path), "rb") as handle:
            if (
                handle.getnchannels() != channels
                or handle.getsampwidth() != width
                or handle.getframerate() != rate
            ):
                raise BreezeError(
                    f"{clip.wav_path.name} has different audio parameters; "
                    "re-run `prepare` so every clip is mono 24 kHz s16"
                )
            if index:
                parts.append(_silence(rate, gap_seconds))
            parts.append(handle.readframes(handle.getnframes()))
    parts.append(_silence(rate, tail_seconds))

    payload = b"".join(parts)
    temporary = destination.with_suffix(".tmp.wav")
    with wave.open(str(temporary), "wb") as handle:
        handle.setnchannels(channels)
        handle.setsampwidth(width)
        handle.setframerate(rate)
        handle.writeframes(payload)
    temporary.replace(destination)
    return len(payload) / 2 / rate


# ---------------------------------------------------------------------------
# Pack
# ---------------------------------------------------------------------------


def voice_name(value: str) -> str:
    """Match Breeze's saved-voice naming rules (letters, digits, - and _)."""

    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", value).strip("_")
    return cleaned[:64] or "voice"


def _sh_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def _md_cell(value: str) -> str:
    return value.replace("|", r"\|")


def _default_description(character: str, clip_count: int) -> str:
    return (
        f"{character} voice reference assembled from {clip_count} Overwatch "
        "voice lines. Clean, close recording; game character delivery."
    )


def build_pack(
    *,
    pack_dir: Path,
    dataset_dir: Path,
    rows: list[dict[str, Any]],
    name: str,
    character: str,
    page: str,
    revision: int | None,
    source_url: str,
    description: str | None = None,
    language: str = "en",
    target_seconds: float = 10.0,
    min_clip_seconds: float = 1.2,
    max_clip_seconds: float = 8.0,
) -> BreezePack:
    """Build ``reference.wav`` plus transcript, manifest, import script and README."""

    clips = select_clips(
        rows,
        dataset_dir=dataset_dir,
        language=language,
        target_seconds=target_seconds,
        min_clip_seconds=min_clip_seconds,
        max_clip_seconds=max_clip_seconds,
    )
    pack_dir.mkdir(parents=True, exist_ok=True)

    wav_path = pack_dir / "reference.wav"
    duration = write_reference_wav(clips, wav_path)
    transcript = " ".join(clip.text.strip() for clip in clips)
    transcript = re.sub(r"\s+", " ", transcript).strip()
    (pack_dir / "reference.txt").write_text(transcript, encoding="utf-8")

    saved_name = voice_name(name)
    desc = (description or _default_description(character, len(clips))).strip()
    metadata = {
        "character": character,
        "dataset": name,
        "source": "Overwatch wiki (Fandom)",
        "source_page": page,
        "source_revision": str(revision) if revision is not None else "",
        "source_url": source_url,
        "reference_seconds": f"{duration:.2f}",
        "reference_clips": ";".join(clip.id for clip in clips),
        "language": language,
    }

    pack = BreezePack(
        directory=pack_dir,
        name=saved_name,
        transcript=transcript,
        description=desc,
        duration_s=duration,
        clips=clips,
        metadata=metadata,
    )
    manifest = pack.to_dict()
    manifest.update(
        {
            "created_at": datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
            "source": {
                "page": page,
                "revision": revision,
                "url": source_url,
            },
        }
    )
    (pack_dir / "voice.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    metadata_json = json.dumps(metadata, ensure_ascii=False)
    script = f"""#!/usr/bin/env bash
# Save this reference directly into a running breeze-server.
# Usage: ./import.sh [SERVER_URL]
# Example: ./import.sh https://server.tail685690.ts.net:8445
set -euo pipefail
cd "$(dirname "$0")"
SERVER="${{1:-http://127.0.0.1:8080}}"
curl --fail-with-body -sS -X POST "${{SERVER%/}}/v1/voices" \\
  -F "ref_audio=@reference.wav;type=audio/wav" \\
  -F "ref_text=<reference.txt" \\
  --form-string {_sh_quote("name=" + saved_name)} \\
  --form-string {_sh_quote("description=" + desc)} \\
  --form-string {_sh_quote("metadata=" + metadata_json)}
echo
"""
    script_path = pack_dir / "import.sh"
    script_path.write_text(script, encoding="utf-8")
    script_path.chmod(0o755)

    rows_md = "\n".join(
        f"| {index} | {_md_cell(clip.section) or '-'} | {clip.duration_s:.2f}s | "
        f"`{clip.id}` | {_md_cell(clip.text)} |"
        for index, clip in enumerate(clips, 1)
    )
    readme = f"""# Breeze-TTS reference pack — {character}

A single reference clip and its exact transcript, ready to import into the
Breeze-TTS WebUI. The clip is assembled from {len(clips)} clean target-speaker
lines and is {duration:.2f}s long (Breeze recommends 5–15s).

## WebUI (manual, quickest)

1. Open the Breeze WebUI and switch to **VOICE CLONE**.
2. **REFERENCE AUDIO (WAV)** → choose `reference.wav`.
3. **REFERENCE TRANSCRIPT (EXACT)** → paste the contents of `reference.txt`.
4. Optionally type `{saved_name}` in **SAVE AS** and a description, then press
   **SAVE VOICE**. It then appears in **VOICE LIBRARY**.

## HTTP / CLI

```bash
./import.sh http://127.0.0.1:8080
# or the server you use:
./import.sh https://server.tail685690.ts.net:8445
```

This uploads the WAV + transcript as a saved voice named `{saved_name}`.

## Files

| File | Purpose |
|---|---|
| `reference.wav` | Mono 24 kHz 16-bit PCM reference clip |
| `reference.txt` | Exact transcript of `reference.wav` |
| `voice.json` | Manifest with provenance and the selected lines |
| `import.sh` | One-command `POST /v1/voices` upload |
| `README.md` | This file |

## Transcript

> {transcript}

## Selected lines

| # | Section | Duration | Clip id | Text |
|---|---|---|---|---|
{rows_md}

## Licence

The audio is © Blizzard Entertainment and is intended for personal research
and experimentation with voice cloning. Do not redistribute it or use a cloned
voice for impersonation, harassment, or commercial purposes.
"""
    (pack_dir / "README.md").write_text(readme, encoding="utf-8")
    return pack


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------


def _multipart(fields: dict[str, str], file_field: str, file_path: Path, filename: str):
    boundary = "----breeze" + secrets.token_hex(16)
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.append(
            (
                f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'
            ).encode()
        )
    chunks.append(
        (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{file_field}"; filename="{filename}"\r\n'
            "Content-Type: audio/wav\r\n\r\n"
        ).encode()
    )
    chunks.append(file_path.read_bytes())
    chunks.append(f"\r\n--{boundary}--\r\n".encode())
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def upload_pack(
    pack: BreezePack,
    server: str,
    *,
    save_name: str | None = None,
    timeout: float = 180.0,
) -> dict[str, Any]:
    """POST the pack to ``/v1/voices`` and return the server's JSON response."""

    name = voice_name(save_name or pack.name)
    fields = {
        "name": name,
        "ref_text": pack.transcript,
        "description": pack.description,
        "metadata": json.dumps(pack.metadata, ensure_ascii=False),
    }
    body, content_type = _multipart(fields, "ref_audio", pack.wav_path, "reference.wav")
    request = urllib.request.Request(
        f"{server.rstrip('/')}/v1/voices",
        data=body,
        headers={
            "Content-Type": content_type,
            "Accept": "application/json",
            "User-Agent": "overwatch-voice-lines/0.1",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:800]
        raise BreezeError(f"breeze server returned HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise BreezeError(f"could not reach breeze server at {server!r}: {exc}") from exc
    try:
        result = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise BreezeError(f"breeze server returned non-JSON: {payload[:300]!r}") from exc
    if not isinstance(result, dict) or "id" not in result:
        raise BreezeError(f"unexpected breeze server response: {payload[:300]}")
    return result
