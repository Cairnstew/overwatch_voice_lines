from __future__ import annotations

import json
from pathlib import Path

import pytest
from overwatch_voice_lines import cli
from overwatch_voice_lines.api import canonical_file_name
from overwatch_voice_lines.models import FileInfo, Page

WIKITEXT = """== Voice Lines ==
{| class="listtable"
|-
! width="20%" | Availability
! width="70%" | Quote
! width="10%" | Audio
|-
| rowspan="1" | Default
|Hello there.
|{{Audio|Widowmaker - Hello there.ogg}}
|}
"""


class StubClient:
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs

    def fetch_page(self, page: str) -> Page:
        return Page(
            title=page,
            wikitext=WIKITEXT,
            revision=7,
            url="https://overwatch.fandom.com/wiki/" + page.replace(" ", "_"),
        )

    def resolve_files(self, names):
        return {
            canonical_file_name(name): FileInfo(
                filename=name,
                url="https://static.wikia.nocookie.net/" + name,
                size=10,
                mime="audio/ogg",
            )
            for name in names
        }


def test_parser_defaults():
    parser = cli.build_parser()
    args = parser.parse_args(["build", "Widowmaker"])
    assert args.command == "build"
    assert args.pages == ["Widowmaker"]
    assert args.sample_rate == 24000
    assert args.val_fraction == 0.1
    assert args.speakers == "target"
    assert args.data_dir == Path("data")


def test_prepare_parser_has_speaker_option():
    parser = cli.build_parser()
    args = parser.parse_args(["prepare", "Widowmaker", "--speakers", "all"])
    assert args.command == "prepare"
    assert args.speakers == "all"
    assert args.force is False


def test_resolve_targets_expands_names_and_derives_display_names():
    assert cli._resolve_targets(["Widowmaker"], None) == [
        ("Widowmaker/Quotes", "Widowmaker", "Widowmaker")
    ]
    assert cli._resolve_targets(["Widowmaker/Quotes/Overwatch 1"], None) == [
        (
            "Widowmaker/Quotes/Overwatch 1",
            "Widowmaker",
            "Widowmaker (Overwatch 1)",
        )
    ]
    assert cli._resolve_targets(["Widowmaker/Quotes"], "Widow") == [
        ("Widowmaker/Quotes", "Widowmaker", "Widow")
    ]


def test_name_with_multiple_pages_is_rejected():
    with pytest.raises(SystemExit):
        cli._resolve_targets(["Ana", "Tracer"], "Heroes")


def test_fetch_writes_quotes_and_report(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "WikiClient", StubClient)
    exit_code = cli.main(
        [
            "--data-dir",
            str(tmp_path),
            "fetch",
            "Widowmaker",
        ]
    )
    assert exit_code == 0
    out = tmp_path / "widowmaker"
    quotes = [json.loads(line) for line in (out / "quotes.jsonl").read_text().splitlines()]
    assert len(quotes) == 1
    assert quotes[0]["text"] == "Hello there."
    assert quotes[0]["file_url"].startswith("https://static.wikia.nocookie.net/")

    report = json.loads((out / "report.json").read_text())
    assert report["page"] == "Widowmaker/Quotes"
    assert report["revision"] == 7
    assert report["utterances"] == 1
    assert report["resolved"] == 1
    assert report["missing"] == 0
    assert report["sections"] == {"Voice Lines": 1}


def test_fetch_limit_keeps_first_rows(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "WikiClient", StubClient)
    assert cli.main(["--data-dir", str(tmp_path), "fetch", "Widowmaker", "--limit", "0"]) == 0
    quotes = (tmp_path / "widowmaker/quotes.jsonl").read_text().splitlines()
    assert quotes == []


def test_download_fetches_missing_quotes_first(tmp_path, monkeypatch):
    from overwatch_voice_lines.dataset import DownloadReport

    monkeypatch.setattr(cli, "WikiClient", StubClient)
    calls = {}

    def fake_download(utterances, raw_dir, **kwargs):
        calls["count"] = len(list(utterances))
        Path(raw_dir).mkdir(parents=True, exist_ok=True)
        return DownloadReport()

    monkeypatch.setattr(cli, "download_utterances", fake_download)

    assert cli.main(["--data-dir", str(tmp_path), "download", "Widowmaker"]) == 0
    assert calls["count"] == 1
    assert (tmp_path / "widowmaker/quotes.jsonl").exists()
    report = json.loads((tmp_path / "widowmaker/report.json").read_text())
    assert report["download"]["downloaded"] == 0


def test_stats_without_dataset_returns_one(tmp_path, capsys):
    assert cli.main(["--data-dir", str(tmp_path), "stats", "Widowmaker"]) == 1
    assert "no prepared dataset" in capsys.readouterr().out


def test_version_exits_zero():
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["--version"])
    assert excinfo.value.code == 0
