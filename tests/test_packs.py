"""Consistency checks for the committed Breeze reference packs."""

from __future__ import annotations

import json
import struct
from pathlib import Path

import pytest

PACKS_DIR = Path(__file__).resolve().parents[1] / "packs"
PACK_DIRS = sorted(path for path in PACKS_DIR.iterdir() if path.is_dir())
PACK_IDS = [path.name for path in PACK_DIRS]


def _u32(data: bytes, offset: int) -> int:
    if offset + 4 > len(data):
        raise ValueError("truncated .breeze header")
    return struct.unpack_from("<I", data, offset)[0]


def parse_breeze(path: Path) -> dict[str, object]:
    """Parse enough of a v1/v2 .breeze container to validate it."""
    data = path.read_bytes()
    if len(data) < 24:
        raise ValueError("file is too short to be a .breeze voice")

    magic, version, sample_rate, n_codebooks, frames, transcript_len = struct.unpack_from(
        "<4sIIIII", data, 0
    )
    if magic != b"BRZV":
        raise ValueError(f"bad magic {magic!r}")
    if version not in (1, 2):
        raise ValueError(f"unsupported .breeze version {version}")
    if not (0 < n_codebooks <= 64) or not (0 < frames <= 100_000):
        raise ValueError("invalid codebook/frame count")

    offset = 24
    if offset + transcript_len > len(data):
        raise ValueError("truncated transcript")
    transcript = data[offset : offset + transcript_len].decode("utf-8")
    offset += transcript_len

    description = ""
    metadata: dict[str, str] = {}
    if version == 2:
        description_len = _u32(data, offset)
        offset += 4
        if offset + description_len > len(data):
            raise ValueError("truncated description")
        description = data[offset : offset + description_len].decode("utf-8")
        offset += description_len

        field_count = _u32(data, offset)
        offset += 4
        for _ in range(field_count):
            key_len = _u32(data, offset)
            offset += 4
            key = data[offset : offset + key_len].decode("utf-8")
            offset += key_len

            value_len = _u32(data, offset)
            offset += 4
            value = data[offset : offset + value_len].decode("utf-8")
            offset += value_len
            metadata[key] = value

    expected_size = offset + frames * n_codebooks * 4
    if expected_size != len(data):
        raise ValueError(f"expected {expected_size} bytes, found {len(data)}")

    return {
        "version": version,
        "sample_rate": sample_rate,
        "n_codebooks": n_codebooks,
        "frames": frames,
        "transcript": transcript,
        "description": description,
        "metadata": metadata,
    }


@pytest.mark.parametrize("pack", PACK_DIRS, ids=PACK_IDS)
def test_pack_has_required_files(pack: Path) -> None:
    for name in ("reference.wav", "reference.txt", "voice.json", "voice.breeze"):
        assert (pack / name).is_file(), f"{pack.name} is missing {name}"


@pytest.mark.parametrize("pack", PACK_DIRS, ids=PACK_IDS)
def test_pack_breeze_matches_manifest(pack: Path) -> None:
    manifest = json.loads((pack / "voice.json").read_text(encoding="utf-8"))
    breeze = parse_breeze(pack / "voice.breeze")

    assert manifest["name"]
    assert manifest["breeze_file"] == "voice.breeze"
    assert manifest["ref_text"] == breeze["transcript"]
    assert (pack / "reference.txt").read_text(encoding="utf-8").strip() == breeze["transcript"]
    assert breeze["sample_rate"] > 0
    assert breeze["n_codebooks"] > 0
    assert breeze["frames"] > 0


@pytest.mark.parametrize("pack", PACK_DIRS, ids=PACK_IDS)
def test_pack_records_model_family(pack: Path) -> None:
    manifest = json.loads((pack / "voice.json").read_text(encoding="utf-8"))

    assert manifest["model_family"] == "breeze-tts-2"
    assert manifest["model"] == "breeze-tts-2-q4_k.gguf"
    assert manifest["model_quant"] == "q4_k"
