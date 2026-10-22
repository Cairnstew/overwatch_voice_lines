"""Command line interface: fetch metadata, download audio, prepare a dataset."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import Counter
from pathlib import Path

from . import __version__
from .api import DEFAULT_USER_AGENT, WikiClient, WikiError
from .audio import AudioError
from .breeze import BreezeError, build_pack, upload_pack
from .dataset import (
    download_utterances,
    prepare_dataset,
    read_metadata,
    same_speaker,
    slugify,
    write_report,
)
from .models import ParseResult, Utterance
from .wikitext import character_from_page, parse_page

LOGGER = logging.getLogger("overwatch_voice_lines")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _dataset_name(page: str, character: str) -> str:
    parts = page.split("/")
    if len(parts) > 2:
        return f"{character} ({'/'.join(parts[2:])})"
    return character


def _resolve_targets(values: list[str], name: str | None) -> list[tuple[str, str, str]]:
    if name and len(values) > 1:
        raise SystemExit("--name can only be used with a single page")
    targets: list[tuple[str, str, str]] = []
    for value in values:
        if "/" in value:
            page = value
            character = character_from_page(page)
        else:
            character = value
            page = f"{value}/Quotes"
        display = name or _dataset_name(page, character)
        targets.append((page, character, display))
    return targets


def _write_jsonl(path: Path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _read_quotes(path: Path) -> list[Utterance]:
    if not path.exists():
        return []
    utterances: list[Utterance] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                utterances.append(Utterance.from_dict(json.loads(line)))
    return utterances


def _parse_report(result: ParseResult, utterances: list[Utterance] | None = None) -> dict:
    items = result.utterances if utterances is None else utterances
    sections: Counter[str] = Counter(u.section for u in items)
    return {
        "utterances": len(items),
        "tables": result.tables_seen,
        "rows": result.rows_seen,
        "rows_without_audio": result.rows_without_audio,
        "rows_without_text": result.rows_without_text,
        "audio_refs": result.audio_refs,
        "sections": dict(sorted(sections.items())),
        "languages": dict(Counter(u.language for u in items)),
        "speakers": dict(Counter(u.speaker for u in items)),
        "warnings": result.warnings,
    }


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def cmd_fetch(args: argparse.Namespace) -> int:
    client = WikiClient(
        user_agent=args.user_agent,
        cache_dir=args.cache_dir,
        refresh=args.refresh,
    )
    for page, character, display in _resolve_targets(args.pages, args.name):
        out_dir = args.data_dir / slugify(display)
        page_data = client.fetch_page(page)
        result = parse_page(
            page_data.wikitext,
            page=page_data.title,
            character=character,
            revision=page_data.revision,
        )
        limit = getattr(args, "limit", None)
        utterances = result.utterances[:limit] if limit is not None else result.utterances

        files = client.resolve_files(u.audio_file for u in utterances)
        missing: list[str] = []
        for utterance in utterances:
            info = files.get(utterance.audio_file)
            if info is None or info.missing:
                utterance.missing = True
                missing.append(utterance.audio_file)
            else:
                utterance.file_url = info.url
                utterance.file_size = info.size

        _write_jsonl(out_dir / "quotes.jsonl", (u.to_dict() for u in utterances))
        report = _parse_report(result, utterances)
        report.update(
            {
                "page": page_data.title,
                "revision": page_data.revision,
                "source_url": page_data.url,
                "character": character,
                "name": display,
                "resolved": len(utterances) - len(missing),
                "missing": len(missing),
                "missing_files": sorted(set(missing)),
            }
        )
        write_report(out_dir / "report.json", report)
        _print_parse_summary(display, report)
    return 0


def cmd_download(args: argparse.Namespace) -> int:
    for page, character, display in _resolve_targets(args.pages, args.name):
        out_dir = args.data_dir / slugify(display)
        quotes_path = out_dir / "quotes.jsonl"
        if not quotes_path.exists():
            LOGGER.info("%s has no quotes.jsonl yet; fetching first", display)
            fetch_args = argparse.Namespace(**vars(args))
            fetch_args.pages = [page]
            fetch_args.name = display
            cmd_fetch(fetch_args)
        utterances = _read_quotes(quotes_path)
        selected = _filter_speakers(utterances, character, args.speakers)
        report = download_utterances(
            selected,
            out_dir / "raw",
            user_agent=args.user_agent,
            force=args.force,
            workers=args.workers,
        )
        payload = _read_quotes_report(out_dir)
        payload["download"] = report.to_dict()
        write_report(out_dir / "report.json", payload)
        print(
            f"{display}: downloaded {report.downloaded}, "
            f"already present {report.skipped}, missing {report.missing}, "
            f"failed {report.failed}"
        )
        if report.errors:
            print("  failures:", file=sys.stderr)
            for error in report.errors[:10]:
                print(f"   - {error}", file=sys.stderr)
    return 0


def cmd_prepare(args: argparse.Namespace) -> int:
    for page, character, display in _resolve_targets(args.pages, args.name):
        out_dir = args.data_dir / slugify(display)
        quotes_path = out_dir / "quotes.jsonl"
        utterances = _read_quotes(quotes_path)
        if not utterances:
            raise SystemExit(
                f"no quotes for {display!r} at {quotes_path}; run `fetch` or `build` first"
            )
        metadata = _read_quotes_report(out_dir)
        prepare_report = prepare_dataset(
            utterances,
            out_dir=out_dir,
            character=character,
            character_slug=slugify(display),
            page=metadata.get("page", page),
            source_url=metadata.get("source_url", f"https://overwatch.fandom.com/wiki/{page}"),
            revision=metadata.get("revision"),
            database_name=display,
            sample_rate=args.sample_rate,
            val_fraction=args.val_fraction,
            target_speaker_only=args.speakers == "target",
            include_nonverbal=args.include_nonverbal,
            min_duration=args.min_duration,
            max_duration=args.max_duration,
            normalize=not args.no_normalize,
            trim_silence=args.trim_silence,
            force=args.force,
            limit=args.limit,
        )
        report = metadata or {}
        report["prepare"] = prepare_report.to_dict()
        write_report(out_dir / "report.json", report)
        print(
            f"{display}: {len(prepare_report.clips)} clips "
            f"(train {prepare_report.train_count}, val {prepare_report.val_count}); "
            f"skipped nonverbal {prepare_report.skipped_nonverbal}, "
            f"speaker {prepare_report.skipped_speaker}, "
            f"missing {prepare_report.skipped_missing}, "
            f"no-raw {prepare_report.skipped_no_raw}, "
            f"duration {prepare_report.skipped_duration}, "
            f"duplicates {prepare_report.duplicates}"
        )
        for error in prepare_report.conversion_errors[:5]:
            print(f"  conversion error: {error}", file=sys.stderr)
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    client = WikiClient(
        user_agent=args.user_agent,
        cache_dir=args.cache_dir,
        refresh=args.refresh,
    )
    exit_code = 0
    for page, character, display in _resolve_targets(args.pages, args.name):
        out_dir = args.data_dir / slugify(display)
        page_data = client.fetch_page(page)
        result = parse_page(
            page_data.wikitext,
            page=page_data.title,
            character=character,
            revision=page_data.revision,
        )
        utterances = (
            result.utterances[: args.limit] if args.limit is not None else result.utterances
        )
        files = client.resolve_files(u.audio_file for u in utterances)
        missing: list[str] = []
        for utterance in utterances:
            info = files.get(utterance.audio_file)
            if info is None or info.missing:
                utterance.missing = True
                missing.append(utterance.audio_file)
            else:
                utterance.file_url = info.url
                utterance.file_size = info.size
        _write_jsonl(out_dir / "quotes.jsonl", (u.to_dict() for u in utterances))

        selected = _filter_speakers(utterances, character, args.speakers)
        download_report = download_utterances(
            selected,
            out_dir / "raw",
            user_agent=args.user_agent,
            force=args.force,
            workers=args.workers,
        )
        prepare_report = prepare_dataset(
            utterances,
            out_dir=out_dir,
            character=character,
            character_slug=slugify(display),
            page=page_data.title,
            source_url=page_data.url or page,
            revision=page_data.revision,
            database_name=display,
            sample_rate=args.sample_rate,
            val_fraction=args.val_fraction,
            target_speaker_only=args.speakers == "target",
            include_nonverbal=args.include_nonverbal,
            min_duration=args.min_duration,
            max_duration=args.max_duration,
            normalize=not args.no_normalize,
            trim_silence=args.trim_silence,
            force=args.force,
            limit=args.limit,
        )
        report = _parse_report(result, utterances)
        report.update(
            {
                "page": page_data.title,
                "revision": page_data.revision,
                "source_url": page_data.url,
                "character": character,
                "name": display,
                "resolved": len(utterances) - len(missing),
                "missing": len(missing),
                "missing_files": sorted(set(missing)),
                "download": download_report.to_dict(),
                "prepare": prepare_report.to_dict(),
            }
        )
        write_report(out_dir / "report.json", report)

        print(
            f"\n{display}: {len(prepare_report.clips)} clips, "
            f"{sum(c.duration_s for c in prepare_report.clips) / 60:.1f} min, "
            f"train {prepare_report.train_count} / val {prepare_report.val_count}"
        )
        print(
            f"  parsed {len(utterances)} utterances from {report['tables']} tables; "
            f"missing files {len(set(missing))}; "
            f"downloaded {download_report.downloaded}, "
            f"cached {download_report.skipped}, failed {download_report.failed}"
        )
        print(f"  output: {out_dir}")
        if download_report.failed:
            exit_code = 1
        if prepare_report.conversion_errors:
            exit_code = 1
    return exit_code


def cmd_export_breeze(args: argparse.Namespace) -> int:
    targets = _resolve_targets(args.pages, args.name)
    if args.out and len(targets) > 1:
        raise SystemExit("--out can only be used with a single page")
    exit_code = 0
    for page, character, display in targets:
        dataset_dir = args.data_dir / slugify(display)
        rows = read_metadata(dataset_dir)
        if not rows:
            print(
                f"error: no prepared dataset for {display!r} at {dataset_dir}; "
                "run `prepare` or `build` first",
                file=sys.stderr,
            )
            exit_code = 1
            continue
        report = _read_quotes_report(dataset_dir)
        pack_dir = args.out or (dataset_dir / "breeze")
        try:
            pack = build_pack(
                pack_dir=pack_dir,
                dataset_dir=dataset_dir,
                rows=rows,
                name=display,
                character=report.get("character", character),
                page=report.get("page", page),
                revision=report.get("revision"),
                source_url=report.get("source_url", f"https://overwatch.fandom.com/wiki/{page}"),
                description=args.description,
                language=args.language,
                target_seconds=args.target_seconds,
                min_clip_seconds=args.min_clip_seconds,
                max_clip_seconds=args.max_clip_seconds,
            )
        except BreezeError as exc:
            print(f"error: {display}: {exc}", file=sys.stderr)
            exit_code = 1
            continue

        print(
            f"{display}: Breeze reference {pack.duration_s:.2f}s from "
            f"{len(pack.clips)} clips -> {pack.directory}"
        )
        print(f"  transcript: {pack.transcript}")
        print(f"  import in the WebUI, or run: {pack.directory / 'import.sh'} <server>")
        if args.server:
            try:
                result = upload_pack(pack, args.server, save_name=args.save_name)
            except BreezeError as exc:
                print(f"error: upload failed: {exc}", file=sys.stderr)
                exit_code = 1
                continue
            print(
                f"  saved voice {result.get('name', args.save_name or pack.name)!r} "
                f"(id {result.get('id')}, {float(result.get('seconds', 0)):.2f}s, "
                f"saved={result.get('saved')})"
            )
    return exit_code


def cmd_stats(args: argparse.Namespace) -> int:
    found = False
    for _, _, display in _resolve_targets(args.pages, args.name):
        out_dir = args.data_dir / slugify(display)
        rows = read_metadata(out_dir)
        if not rows:
            print(f"{display}: no prepared dataset at {out_dir}")
            continue
        found = True
        total = sum(float(row.get("duration_s", 0)) for row in rows)
        print(f"\n{display} — {len(rows)} clips, {total / 60:.1f} min")
        print(f"  sections: {_counts(row.get('section') for row in rows)}")
        print(f"  languages: {_counts(row.get('language') for row in rows)}")
        print(f"  speakers: {_counts(row.get('speaker') for row in rows)}")
        print(f"  nonverbal: {sum(1 for row in rows if not row.get('verbal', True))}")
    return 0 if found else 1


# ---------------------------------------------------------------------------
# Small utilities
# ---------------------------------------------------------------------------


def _filter_speakers(utterances: list[Utterance], character: str, speakers: str) -> list[Utterance]:
    if speakers == "all":
        return utterances
    return [u for u in utterances if same_speaker(u.speaker, character)]


def _read_quotes_report(out_dir: Path) -> dict:
    path = out_dir / "report.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _counts(values) -> str:
    return ", ".join(f"{value or 'none'}={count}" for value, count in Counter(values).most_common())


def _print_parse_summary(display: str, report: dict) -> None:
    print(
        f"{display}: parsed {report['utterances']} utterances from "
        f"{report['tables']} tables; resolved {report['resolved']}, "
        f"missing {report['missing']}"
    )
    print(f"  sections: {_counts(report['sections'])}")


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="overwatch-voice-lines",
        description=(
            "Download Overwatch hero voice lines from the Fandom wiki and prepare "
            "mono wav clips with transcripts for voice cloning."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  overwatch-voice-lines fetch Widowmaker\n"
            "  overwatch-voice-lines build Widowmaker\n"
            "  overwatch-voice-lines build 'Widowmaker/Quotes/Overwatch 1'\n"
            "      --name 'Widowmaker OW1'\n"
            "  overwatch-voice-lines stats Widowmaker\n"
            "  overwatch-voice-lines export-breeze Widowmaker\n"
            "  overwatch-voice-lines export-breeze Widowmaker --server http://127.0.0.1:8080\n"
            "\nAudio requires ffmpeg and ffprobe on PATH "
            "(nix shell nixpkgs#ffmpeg)."
        ),
    )
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data"),
        help="dataset root (default: data)",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path(".cache/ovl"),
        help="wiki API response cache (default: .cache/ovl)",
    )
    parser.add_argument(
        "--user-agent",
        default=DEFAULT_USER_AGENT,
        help="HTTP User-Agent; set a contact URL/email for heavy use",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="ignore the API response cache",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging")

    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_page_args(sub: argparse.ArgumentParser) -> None:
        sub.add_argument(
            "pages",
            nargs="+",
            metavar="CHARACTER|PAGE",
            help=(
                "hero name (fetches '<name>/Quotes') or a full wiki page such as "
                "'Widowmaker/Quotes/Overwatch 1'"
            ),
        )
        sub.add_argument(
            "--name",
            help="dataset name/slug (default derived from the page; single page only)",
        )
        sub.add_argument(
            "--limit",
            type=int,
            help="only handle the first N parsed utterances (useful for a smoke test)",
        )

    fetch = subparsers.add_parser("fetch", help="parse the wiki page and resolve file URLs")
    add_page_args(fetch)
    fetch.set_defaults(func=cmd_fetch)

    download = subparsers.add_parser("download", help="download the original audio files")
    add_page_args(download)
    download.add_argument("--workers", type=int, default=4, help="parallel downloads (default: 4)")
    download.add_argument("--force", action="store_true", help="re-download existing files")
    download.add_argument(
        "--speakers",
        choices=["target", "all"],
        default="target",
        help="download only the target hero's lines, or every speaker (default: target)",
    )
    download.set_defaults(func=cmd_download)

    prepare = subparsers.add_parser("prepare", help="convert cached audio and write the dataset")
    add_page_args(prepare)
    _add_prepare_options(prepare)
    prepare.set_defaults(func=cmd_prepare)

    build = subparsers.add_parser("build", help="fetch, download and prepare in one run")
    add_page_args(build)
    _add_prepare_options(build)
    build.add_argument("--workers", type=int, default=4, help="parallel downloads (default: 4)")
    build.set_defaults(func=cmd_build)

    breeze = subparsers.add_parser(
        "export-breeze",
        help="write a Breeze-TTS WebUI reference pack (wav + exact transcript)",
    )
    breeze.add_argument("pages", nargs="+", metavar="CHARACTER|PAGE")
    breeze.add_argument("--name", help="dataset name/slug")
    breeze.add_argument(
        "--out",
        type=Path,
        help="pack directory (default: <dataset>/breeze); single page only",
    )
    breeze.add_argument("--language", default="en", help="reference language (default: en; 'all')")
    breeze.add_argument(
        "--target-seconds",
        type=float,
        default=10.0,
        help="target speech duration, 5-15s (default: 10)",
    )
    breeze.add_argument(
        "--min-clip-seconds",
        type=float,
        default=1.2,
        help="ignore clips shorter than this (default: 1.2)",
    )
    breeze.add_argument(
        "--max-clip-seconds",
        type=float,
        default=8.0,
        help="ignore clips longer than this (default: 8)",
    )
    breeze.add_argument("--description", help="saved-voice description")
    breeze.add_argument(
        "--server",
        help="also POST to a running breeze-server, e.g. http://127.0.0.1:8080",
    )
    breeze.add_argument(
        "--save-name",
        help="saved voice name for --server (default: dataset name)",
    )
    breeze.set_defaults(func=cmd_export_breeze)

    stats = subparsers.add_parser("stats", help="summarise an existing dataset")
    stats.add_argument("pages", nargs="+", metavar="CHARACTER|PAGE")
    stats.add_argument("--name", help="dataset name/slug")
    stats.set_defaults(func=cmd_stats)

    return parser


def _add_prepare_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--sample-rate",
        type=int,
        default=24000,
        help="output sample rate in Hz (default: 24000)",
    )
    parser.add_argument(
        "--val-fraction",
        type=float,
        default=0.1,
        help="validation split fraction, 0 disables the split (default: 0.1)",
    )
    parser.add_argument(
        "--speakers",
        choices=["target", "all"],
        default="target",
        help="keep only the target hero's lines, or every speaker (default: target)",
    )
    parser.add_argument(
        "--include-nonverbal",
        action="store_true",
        help="also keep grunts/gasps in the dataset (skipped by default)",
    )
    parser.add_argument(
        "--min-duration",
        type=float,
        default=0.25,
        help="drop clips shorter than this many seconds (default: 0.25)",
    )
    parser.add_argument(
        "--max-duration",
        type=float,
        default=60.0,
        help="drop clips longer than this many seconds (default: 60)",
    )
    parser.add_argument(
        "--no-normalize",
        action="store_true",
        help="skip EBU R128 loudness normalisation",
    )
    parser.add_argument(
        "--trim-silence",
        action="store_true",
        help="trim leading/trailing silence with ffmpeg",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="re-convert existing wav files (and re-download in `build`)",
    )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )
    try:
        return int(args.func(args))
    except (WikiError, AudioError, BreezeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return 130


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
