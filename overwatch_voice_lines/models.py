"""Data structures shared by the parser, downloader and dataset builder."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class FileInfo:
    """A wiki ``File:`` page resolved through the MediaWiki imageinfo API."""

    filename: str
    url: str | None = None
    size: int | None = None
    mime: str | None = None
    missing: bool = False

    @property
    def extension(self) -> str:
        name = self.filename.rsplit(".", 1)
        return name[1].lower() if len(name) == 2 else ""


@dataclass
class Utterance:
    """One spoken line, paired with exactly one audio file.

    A single wiki table row can produce several utterances: a quote cell with
    three ``{{Audio}}`` players becomes three utterances, and an interaction row
    with one player per speaker becomes one utterance per audio file.
    """

    character: str
    speaker: str
    section: str
    context: str
    text: str
    translation: str | None
    language: str
    verbal: bool
    audio_file: str
    source_page: str
    source_revision: int | None = None
    file_url: str | None = None
    file_size: int | None = None
    missing: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Utterance:
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in known})


@dataclass
class Page:
    """A fetched wiki page and the revision it was fetched at."""

    title: str
    wikitext: str
    revision: int | None = None
    url: str | None = None


@dataclass
class ParseResult:
    """What a wikitext page yielded, plus non-fatal issues worth reporting."""

    utterances: list[Utterance] = field(default_factory=list)
    rows_seen: int = 0
    rows_without_audio: int = 0
    rows_without_text: int = 0
    tables_seen: int = 0
    warnings: list[str] = field(default_factory=list)
    audio_refs: int = 0

    def by_section(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for utt in self.utterances:
            counts[utt.section] = counts.get(utt.section, 0) + 1
        return dict(sorted(counts.items()))


@dataclass
class Clip:
    """A prepared, voice-clone-ready wav plus its transcript metadata."""

    id: str
    character: str
    speaker: str
    section: str
    context: str
    text: str
    translation: str
    language: str
    verbal: bool
    audio_file: str
    raw_path: str
    wav_path: str
    duration_s: float
    sample_rate: int
    sha256: str
    source_page: str
    source_url: str
    duplicate_of: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
