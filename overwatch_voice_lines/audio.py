"""ffmpeg/ffprobe helpers for turning wiki audio into clone-ready wav files."""

from __future__ import annotations

import hashlib
import logging
import shutil
import subprocess
from pathlib import Path

LOGGER = logging.getLogger(__name__)


class AudioError(RuntimeError):
    """ffmpeg/ffprobe is missing or failed."""


def find_tool(name: str, explicit: str | None = None) -> str:
    if explicit:
        if Path(explicit).is_file():
            return explicit
        found = shutil.which(explicit)
        if found:
            return found
        raise AudioError(f"{name} not found at {explicit!r}")
    found = shutil.which(name)
    if not found:
        raise AudioError(
            f"{name} is required but was not found on PATH. "
            "Install it with `nix shell nixpkgs#ffmpeg` or `apt install ffmpeg`."
        )
    return found


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def probe_duration(path: Path, ffprobe: str | None = None) -> float:
    tool = find_tool("ffprobe", ffprobe)
    command = [
        tool,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise AudioError(f"ffprobe failed for {path}: {result.stderr.strip()}")
    try:
        return float(result.stdout.strip())
    except ValueError as exc:
        raise AudioError(f"ffprobe returned no duration for {path}") from exc


def _filter_chain(*, sample_rate: int, normalize: bool, trim_silence: bool) -> str | None:
    filters: list[str] = []
    if trim_silence:
        filters.append(
            "silenceremove=start_periods=1:start_silence=0.03:start_threshold=-50dB:"
            "stop_periods=-1:stop_silence=0.05:stop_threshold=-50dB"
        )
    if normalize:
        # Single-pass EBU R128. -16 LUFS with a -1.5 dBTP ceiling is a sensible
        # target for speech models and avoids clipping short, loud grunts.
        filters.append("loudnorm=I=-16:TP=-1.5:LRA=11")
    if not filters:
        return None
    if sample_rate:
        filters.append(f"aresample={sample_rate}")
    return ",".join(filters)


def convert_to_wav(
    source: Path,
    destination: Path,
    *,
    sample_rate: int = 24000,
    normalize: bool = True,
    trim_silence: bool = False,
    ffmpeg: str | None = None,
) -> None:
    """Decode any wiki audio format to mono 16-bit PCM wav."""

    tool = find_tool("ffmpeg", ffmpeg)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".part.wav")
    command = [
        tool,
        "-nostdin",
        "-y",
        "-loglevel",
        "error",
        "-i",
        str(source),
        "-vn",
        "-ac",
        "1",
        "-ar",
        str(sample_rate),
        "-sample_fmt",
        "s16",
    ]
    filters = _filter_chain(
        sample_rate=sample_rate,
        normalize=normalize,
        trim_silence=trim_silence,
    )
    if filters:
        command += ["-af", filters]
    command.append(str(temporary))
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        temporary.unlink(missing_ok=True)
        raise AudioError(
            f"ffmpeg failed for {source.name}: {result.stderr.strip() or 'unknown error'}"
        )
    if not temporary.exists() or temporary.stat().st_size == 0:
        temporary.unlink(missing_ok=True)
        raise AudioError(f"ffmpeg produced an empty file for {source.name}")
    temporary.replace(destination)
