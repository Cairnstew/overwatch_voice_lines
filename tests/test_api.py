from __future__ import annotations

import pytest
from overwatch_voice_lines.api import (
    MAX_TITLES_PER_QUERY,
    WikiClient,
    WikiError,
    canonical_file_name,
)
from overwatch_voice_lines.models import Page


def test_canonical_file_name_handles_wiki_normalisation():
    assert canonical_file_name("widowmaker_-_Hello.ogg") == "Widowmaker - Hello.ogg"
    assert canonical_file_name("File:Widowmaker - Hello.ogg") == "Widowmaker - Hello.ogg"
    assert canonical_file_name("  Widowmaker   -   Hello.ogg ") == "Widowmaker - Hello.ogg"


def test_resolve_files_maps_aliases_and_missing():
    client = WikiClient(cache_dir=None)

    def fake_request(params):
        assert params["action"] == "query"
        return {
            "query": {
                "normalized": [
                    {"from": "File:Widowmaker_-_Hello.ogg", "to": "File:Widowmaker - Hello.ogg"}
                ],
                "pages": [
                    {
                        "title": "File:Widowmaker - Hello.ogg",
                        "imageinfo": [
                            {
                                "url": "https://static.wikia.nocookie.net/hello.ogg",
                                "size": 1234,
                                "mime": "audio/ogg",
                            }
                        ],
                    },
                    {"title": "File:Widowmaker - Missing.ogg", "missing": True},
                ],
            }
        }

    client._request = fake_request  # type: ignore[method-assign]
    files = client.resolve_files(
        [
            "Widowmaker_-_Hello.ogg",
            "Widowmaker - Missing.ogg",
            "Widowmaker - Never mentioned.ogg",
        ]
    )

    hello = files["Widowmaker - Hello.ogg"]
    assert hello.url == "https://static.wikia.nocookie.net/hello.ogg"
    assert hello.size == 1234
    assert hello.mime == "audio/ogg"
    assert hello.missing is False
    assert files["Widowmaker - Missing.ogg"].missing is True
    assert files["Widowmaker - Never mentioned.ogg"].missing is True


def test_resolve_files_batches_at_the_api_limit():
    client = WikiClient(cache_dir=None)
    calls: list[list[str]] = []

    def fake_request(params):
        titles = params["titles"].split("|")
        calls.append(titles)
        return {
            "query": {
                "pages": [
                    {"title": title, "imageinfo": [{"url": "https://example/" + title}]}
                    for title in titles
                ]
            }
        }

    client._request = fake_request  # type: ignore[method-assign]
    names = [f"Clip {index}.ogg" for index in range(MAX_TITLES_PER_QUERY + 3)]
    files = client.resolve_files(names)

    assert len(files) == len(names)
    assert [len(call) for call in calls] == [MAX_TITLES_PER_QUERY, 3]


def test_fetch_page_returns_wikitext_and_url():
    client = WikiClient(cache_dir=None)

    def fake_request(params):
        assert params["action"] == "parse"
        assert params["page"] == "Widowmaker/Quotes/Overwatch 1"
        return {
            "parse": {
                "title": "Widowmaker/Quotes/Overwatch 1",
                "revid": 42,
                "wikitext": "== Voice Lines ==\n",
            }
        }

    client._request = fake_request  # type: ignore[method-assign]
    page = client.fetch_page("Widowmaker/Quotes/Overwatch 1")

    assert isinstance(page, Page)
    assert page.title == "Widowmaker/Quotes/Overwatch 1"
    assert page.revision == 42
    assert page.wikitext.startswith("== Voice Lines ==")
    assert page.url is not None
    assert page.url.endswith("Widowmaker/Quotes/Overwatch_1")


def test_fetch_page_raises_on_missing_page():
    client = WikiClient(cache_dir=None)
    client._request = lambda params: {}  # type: ignore[method-assign]
    with pytest.raises(WikiError):
        client.fetch_page("Nope/Quotes")


def test_cache_key_is_stable(tmp_path):
    client = WikiClient(cache_dir=tmp_path)
    params = {"action": "parse", "page": "Widowmaker/Quotes"}
    first = client._cache_path(params)
    second = client._cache_path({"page": "Widowmaker/Quotes", "action": "parse"})
    assert first == second
    assert first is not None and first.parent == tmp_path
