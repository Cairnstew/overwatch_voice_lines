"""Small, dependency-free MediaWiki client tuned for the Overwatch wiki.

Why the API and not the HTML page? ``overwatch.fandom.com/wiki/...`` is behind
a bot filter that answers a plain ``curl`` with a short block page even for a
normal browser User-Agent. The ``/api.php`` endpoint is not, and it gives us
the wikitext (which is far easier to parse than Fandom's rendered markup) plus
the revision id we want to record in the dataset card.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .models import FileInfo, Page

LOGGER = logging.getLogger(__name__)

DEFAULT_API_URL = "https://overwatch.fandom.com/api.php"
DEFAULT_USER_AGENT = (
    "overwatch-voice-lines/0.1 "
    "(dataset preparation; https://github.com/Cairnstew/overwatch_voice_lines)"
)
MAX_TITLES_PER_QUERY = 50


class WikiError(RuntimeError):
    """The wiki API returned an error or an unusable response."""


def _canonical_title(name: str) -> str:
    """Normalise a file name for matching API responses back to wikitext names.

    MediaWiki treats the first letter case-insensitively, converts underscores
    to spaces, and collapses runs of whitespace, so ``widowmaker_-_Hello.ogg``
    and ``Widowmaker - Hello.ogg`` must compare equal.
    """

    name = name.strip()
    if name.lower().startswith("file:"):
        name = name[5:]
    name = name.replace("_", " ")
    name = re.sub(r"\s+", " ", name).strip()
    return name[:1].upper() + name[1:]


class WikiClient:
    """Minimal MediaWiki client with on-disk caching and polite retries."""

    def __init__(
        self,
        *,
        api_url: str = DEFAULT_API_URL,
        user_agent: str = DEFAULT_USER_AGENT,
        timeout: float = 60.0,
        min_interval: float = 0.25,
        cache_dir: Path | None = None,
        refresh: bool = False,
    ) -> None:
        self.api_url = api_url
        self.user_agent = user_agent
        self.timeout = timeout
        self.min_interval = min_interval
        self.cache_dir = cache_dir
        self.refresh = refresh
        self._last_request = 0.0

    # -- low level ---------------------------------------------------------

    def _cache_path(self, params: dict[str, Any]) -> Path | None:
        if self.cache_dir is None:
            return None
        key = urllib.parse.urlencode(sorted((k, str(v)) for k, v in params.items()))
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]
        return self.cache_dir / f"{digest}.json"

    def _request(self, params: dict[str, Any]) -> dict[str, Any]:
        cache_path = self._cache_path(params)
        if cache_path is not None and cache_path.exists() and not self.refresh:
            try:
                return json.loads(cache_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                LOGGER.debug("discarding unreadable cache entry %s", cache_path)

        query = {"format": "json", "formatversion": "2", "maxlag": "5", **params}
        url = f"{self.api_url}?{urllib.parse.urlencode(query)}"
        attempts = 4
        last_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            wait = self.min_interval - (time.monotonic() - self._last_request)
            if wait > 0:
                time.sleep(wait)
            request = urllib.request.Request(
                url,
                headers={
                    "User-Agent": self.user_agent,
                    "Accept": "application/json",
                },
            )
            try:
                self._last_request = time.monotonic()
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    payload = json.load(response)
            except urllib.error.HTTPError as exc:
                last_error = exc
                retry_after = exc.headers.get("Retry-After") if exc.headers else None
                delay = float(retry_after) if retry_after and retry_after.isdigit() else 2**attempt
                LOGGER.warning(
                    "wiki API HTTP %s on attempt %d/%d, retrying in %.1fs",
                    exc.code,
                    attempt,
                    attempts,
                    delay,
                )
                if exc.code in (429, 500, 502, 503, 504):
                    time.sleep(delay)
                    continue
                raise WikiError(f"wiki API returned HTTP {exc.code}: {exc.reason}") from exc
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                last_error = exc
                delay = 2**attempt
                LOGGER.warning(
                    "wiki API error on attempt %d/%d (%s), retrying in %.1fs",
                    attempt,
                    attempts,
                    exc,
                    delay,
                )
                time.sleep(delay)
                continue

            if "error" in payload:
                error = payload["error"]
                code = error.get("code", "unknown")
                info = error.get("info", "")
                if code == "maxlag":
                    time.sleep(2**attempt)
                    last_error = WikiError(f"maxlag: {info}")
                    continue
                raise WikiError(f"wiki API error {code}: {info}")

            if cache_path is not None:
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                tmp = cache_path.with_suffix(".tmp")
                tmp.write_text(json.dumps(payload), encoding="utf-8")
                tmp.replace(cache_path)
            return payload

        raise WikiError(f"wiki API request failed after {attempts} attempts: {last_error}")

    # -- public ------------------------------------------------------------

    def fetch_page(self, page: str) -> Page:
        """Fetch the wikitext and revision id of ``page``."""

        payload = self._request(
            {
                "action": "parse",
                "page": page,
                "prop": "revid|wikitext",
                "redirects": "1",
            }
        )
        parsed = payload.get("parse")
        if not parsed:
            raise WikiError(f"page not found: {page!r}")
        title = parsed.get("title", page)
        LOGGER.info(
            "fetched %s (revision %s, %d bytes)",
            title,
            parsed.get("revid"),
            len(parsed.get("wikitext", "")),
        )
        return Page(
            title=title,
            wikitext=parsed.get("wikitext", ""),
            revision=parsed.get("revid"),
            url=f"https://overwatch.fandom.com/wiki/{urllib.parse.quote(title.replace(' ', '_'))}",
        )

    def resolve_files(self, filenames: Iterable[str]) -> dict[str, FileInfo]:
        """Resolve wiki file names to direct download URLs.

        The returned mapping is keyed by :func:`_canonical_title` so callers can
        look names up without worrying about underscores or first-letter case.
        Missing files are included with ``missing=True`` rather than dropped, so
        the caller can report them.
        """

        unique: list[str] = []
        seen: set[str] = set()
        for name in filenames:
            key = _canonical_title(name)
            if key and key not in seen:
                seen.add(key)
                unique.append(key)

        result: dict[str, FileInfo] = {}
        for start in range(0, len(unique), MAX_TITLES_PER_QUERY):
            chunk = unique[start : start + MAX_TITLES_PER_QUERY]
            self._resolve_chunk(chunk, result)
        return result

    def _resolve_chunk(self, names: list[str], result: dict[str, FileInfo]) -> None:
        titles = "|".join(f"File:{name}" for name in names)
        payload = self._request(
            {
                "action": "query",
                "prop": "imageinfo",
                "iiprop": "url|size|mime",
                "titles": titles,
                "redirects": "1",
            }
        )
        query = payload.get("query", {})

        # The API may normalise/redirect titles; map the returned title back to
        # the canonical key the caller asked for.
        aliases: dict[str, str] = {}
        for item in query.get("normalized", []):
            aliases[_canonical_title(item.get("to", ""))] = _canonical_title(item.get("from", ""))
        for item in query.get("redirects", []):
            aliases[_canonical_title(item.get("to", ""))] = _canonical_title(item.get("from", ""))

        for page in query.get("pages", []):
            title = _canonical_title(page.get("title", ""))
            key = aliases.get(title, title)
            if key not in result:
                key = title
            info = (page.get("imageinfo") or [{}])[0]
            url = info.get("url")
            result[key] = FileInfo(
                filename=key,
                url=url,
                size=info.get("size"),
                mime=info.get("mime"),
                missing=bool(page.get("missing")) or not url,
            )

        # Any requested name the API did not answer is missing.
        for name in names:
            result.setdefault(
                _canonical_title(name),
                FileInfo(filename=name, missing=True),
            )


def canonical_file_name(name: str) -> str:
    """Public wrapper used by the parser and tests."""

    return _canonical_title(name)
