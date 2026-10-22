"""Parse Overwatch wiki quote tables into one record per audio file.

The wiki stores every quote in a ``listtable`` whose last column is a
``{{Audio|File.ogg}}`` player. The first column is a *context* cell (ability,
skin, availability, interaction partner) that often spans several rows with
``rowspan``. A row can also hold several players, in which case the quote cell
holds one line per player (``*'''Ana''': ...``).

Nothing here needs the network, which keeps the parser unit-testable against
fixtures.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass

from .api import canonical_file_name
from .models import ParseResult, Utterance

MEDIA_EXTENSIONS = (".ogg", ".oga", ".mp3", ".wav", ".flac", ".m4a", ".opus")

# ---------------------------------------------------------------------------
# Language markers
# ---------------------------------------------------------------------------

LANGUAGE_MARKERS: tuple[tuple[str, str], ...] = (
    ("(french)", "fr"),
    ("(japanese)", "ja"),
    ("(german)", "de"),
    ("(spanish)", "es"),
    ("(italian)", "it"),
    ("(korean)", "ko"),
    ("(chinese)", "zh"),
    ("(russian)", "ru"),
    ("(portuguese)", "pt"),
    ("(polish)", "pl"),
    ("(swedish)", "sv"),
    ("(dutch)", "nl"),
    ("(turkish)", "tr"),
    ("(arabic)", "ar"),
    ("(hindi)", "hi"),
    ("(latin)", "la"),
)

SCRIPT_LANGUAGES: tuple[tuple[str, str], ...] = (
    ("japanese", "ja"),
    ("korean", "ko"),
    ("chinese", "zh"),
    ("russian", "ru"),
    ("arabic", "ar"),
    ("hindi", "hi"),
    ("latin", "la"),
    ("french", "fr"),
    ("german", "de"),
    ("spanish", "es"),
    ("italian", "it"),
    ("portuguese", "pt"),
)

ATTR_ONLY_RE = re.compile(
    r"""^\s*(?:[A-Za-z_:][-A-Za-z0-9_:]*\s*=\s*(?:"[^"]*"|'[^']*'|[^\s|]+)\s*)+$""",
    re.S,
)
ATTR_RE = re.compile(r"""([A-Za-z_:][-A-Za-z0-9_:]*)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s|]+))""")
AUDIO_TEMPLATE_NAME = "audio"
QUOTE_TRANSLATION_NAME = "quotetranslation"
DIRECTION_RE = re.compile(r"\*[^*\n]+\*")


# ---------------------------------------------------------------------------
# Small balanced-markup helpers
# ---------------------------------------------------------------------------


def _split_top_level(text: str, separator: str) -> list[str]:
    """Split on ``separator`` outside ``{{...}}``, ``[[...]]`` and quotes."""

    parts: list[str] = []
    start = 0
    braces = brackets = 0
    i = 0
    while i < len(text):
        pair = text[i : i + 2]
        if pair == "{{":
            braces += 1
            i += 2
            continue
        if pair == "}}":
            braces = max(0, braces - 1)
            i += 2
            continue
        if pair == "[[":
            brackets += 1
            i += 2
            continue
        if pair == "]]":
            brackets = max(0, brackets - 1)
            i += 2
            continue
        if braces == 0 and brackets == 0 and text.startswith(separator, i):
            parts.append(text[start:i])
            i += len(separator)
            start = i
            continue
        i += 1
    parts.append(text[start:])
    return parts


def _split_first_top_level(text: str, separator: str = "|") -> tuple[str, str | None]:
    parts = _split_top_level(text, separator)
    if len(parts) == 1:
        return text, None
    return parts[0], separator.join(parts[1:])


def _cell_content_and_attrs(cell: str) -> tuple[str, dict[str, str]]:
    """Separate ``rowspan="3" | actual content`` from cell content."""

    left, right = _split_first_top_level(cell, "|")
    if right is None:
        return cell, {}
    if not ATTR_ONLY_RE.match(left):
        return cell, {}
    attrs = {
        match.group(1).lower(): next(group for group in match.groups()[1:] if group is not None)
        for match in ATTR_RE.finditer(left)
    }
    return right, attrs


def _iter_templates(text: str, name: str):
    """Yield the raw argument string of each balanced ``{{name|...}}``."""

    wanted = name.casefold()
    i = 0
    while True:
        start = text.find("{{", i)
        if start == -1:
            return
        depth = 0
        end = -1
        j = start
        while j < len(text):
            if text.startswith("{{", j):
                depth += 1
                j += 2
                continue
            if text.startswith("}}", j):
                depth -= 1
                if depth == 0:
                    end = j
                    break
                j += 2
                continue
            j += 1
        if end == -1:
            return
        inner = text[start + 2 : end]
        template_name, _, args = inner.partition("|")
        if template_name.strip().casefold() == wanted:
            yield args
        i = end + 2


def _strip_templates(text: str) -> str:
    """Remove all balanced ``{{...}}`` templates."""

    out: list[str] = []
    i = 0
    while i < len(text):
        if text.startswith("{{", i):
            depth = 1
            j = i + 2
            while j < len(text) and depth:
                if text.startswith("{{", j):
                    depth += 1
                    j += 2
                elif text.startswith("}}", j):
                    depth -= 1
                    j += 2
                else:
                    j += 1
            i = j
            continue
        out.append(text[i])
        i += 1
    return "".join(out)


def _resolve_links(text: str) -> str:
    text = re.sub(r"\[\[(?:File|Image):[^\]]*\]\]", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", text)
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"\[(?:https?://\S+)\s+([^\]]+)\]", r"\1", text)
    return text


def _clean_text(text: str) -> str:
    """Turn one cell (or bullet line) into display-ready plain text."""

    text = re.sub(r"<ref[^>]*/\s*>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<ref[^>]*>.*?</ref>", "", text, flags=re.IGNORECASE | re.S)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = _resolve_links(text)
    text = _strip_templates(text)
    text = text.replace("'''", "").replace("''", "")
    text = html.unescape(text)
    text = text.replace("\u00a0", " ")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line).strip()


def _clean_translation(text: str | None) -> str | None:
    if not text:
        return None
    cleaned = _clean_text(text).replace("\n", " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or None


def _clean_context(text: str) -> str:
    """Clean the first table column, e.g. a skin or ability label."""

    if not text:
        return ""

    def render(match: re.Match[str]) -> str:
        inner = match.group(1)
        name, _, args = inner.partition("|")
        template = name.strip().casefold()
        values = [part.strip() for part in _split_top_level(args, "|")]
        if template == "credits":
            return "Credits"
        if template == "battle pass":
            return "Battle Pass"
        if template == "rl":
            return values[-1] if values else ""
        if template.endswith("icon"):
            return ""
        return ""

    text = re.sub(r"\{\{(.*?)\}\}", render, text, flags=re.S)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = _resolve_links(text)
    text = text.replace("'''", "").replace("''", "")
    text = html.unescape(text).replace("\u00a0", " ")
    parts = [re.sub(r"\s+", " ", part).strip(" ,;:/") for part in text.splitlines()]
    return " / ".join(part for part in parts if part)


# ---------------------------------------------------------------------------
# Table structure
# ---------------------------------------------------------------------------


@dataclass
class _Row:
    is_header: bool
    cells: list[str]


def _split_inline_cells(payload: str, *, header: bool) -> list[str]:
    cells = _split_top_level(payload, "||")
    if header:
        expanded: list[str] = []
        for cell in cells:
            expanded.extend(_split_top_level(cell, "!!"))
        cells = expanded
    return [cell.strip("\n") for cell in cells]


def _parse_rows(body: str) -> list[_Row]:
    rows: list[_Row] = []
    current: _Row | None = None

    for raw_line in body.split("\n"):
        line = raw_line.rstrip()
        stripped = line.lstrip()
        if not stripped:
            if current and current.cells:
                current.cells[-1] += "\n"
            continue
        if stripped.startswith("{|") or stripped.startswith("|}"):
            continue
        if stripped.startswith("|-"):
            current = None
            continue

        is_header = stripped.startswith("!")
        starts_cell = stripped.startswith("|") or is_header
        if starts_cell:
            if current is None:
                current = _Row(is_header=is_header, cells=[])
                rows.append(current)
            # A line starting with "||" is one cell whose marker consumed both
            # pipes (MediaWiki semantics), not an empty cell followed by one.
            payload = stripped[2:] if stripped.startswith("||") else stripped[1:]
            current.cells.extend(_split_inline_cells(payload, header=is_header))
            continue

        # Continuation of the previous cell: multi-line quote lists, wrapped
        # quotations, or a QuoteTranslation spread over several lines.
        if current is not None and current.cells:
            current.cells[-1] += "\n" + line
        elif current is not None:
            current.cells.append(line)

    return rows


def _expand_rowspans(rows: list[_Row]) -> list[_Row]:
    """Expand ``rowspan``/``colspan`` into a rectangular grid."""

    grid: list[_Row] = []
    pending: dict[int, list] = {}  # column -> [remaining_rows, value]

    for row in rows:
        parsed = [_cell_content_and_attrs(cell) for cell in row.cells]
        output: list[str] = []
        col = 0
        index = 0
        while index < len(parsed) or any(remaining > 0 for remaining, _ in pending.values()):
            if col in pending and pending[col][0] > 0:
                output.append(pending[col][1])
                pending[col][0] -= 1
                col += 1
                continue
            if index >= len(parsed):
                if any(
                    column > col and remaining > 0 for column, (remaining, _) in pending.items()
                ):
                    output.append("")
                    col += 1
                    continue
                break
            content, attrs = parsed[index]
            index += 1
            try:
                rowspan = max(1, int(attrs.get("rowspan", "1")))
            except ValueError:
                rowspan = 1
            try:
                colspan = max(1, int(attrs.get("colspan", "1")))
            except ValueError:
                colspan = 1
            for _ in range(colspan):
                output.append(content)
                if rowspan > 1:
                    pending[col] = [rowspan - 1, content]
                col += 1
        for column in [c for c, (remaining, _) in pending.items() if remaining <= 0]:
            del pending[column]
        grid.append(_Row(is_header=row.is_header, cells=output))

    return grid


def _table_blocks(text: str) -> list[str]:
    return [match.group(0) for match in re.finditer(r"(?ms)^\{\|.*?^\|\}", text)]


# ---------------------------------------------------------------------------
# Quotes
# ---------------------------------------------------------------------------


@dataclass
class _Segment:
    text: str
    translation: str | None = None
    script_hint: str | None = None
    speaker: str | None = None
    verbal: bool = True


def _parse_quote_translation(args: str) -> tuple[str, str | None, str | None]:
    params: dict[str, str] = {}
    for part in _split_top_level(args, "|"):
        key, _, value = part.partition("=")
        if value:
            params[key.strip().casefold()] = value.strip()
        elif part.strip():
            params.setdefault("quote", part.strip())
    quote = params.get("quote", "")
    translation = params.get("translation")
    script_hint = params.get("script") or params.get("native")
    return quote, translation, script_hint


def _extract_translation(text: str) -> tuple[str, str | None, str | None]:
    """Replace the first QuoteTranslation with its spoken-language quote."""

    for args in _iter_templates(text, QUOTE_TRANSLATION_NAME):
        quote, translation, script = _parse_quote_translation(args)
        # Re-find precisely: the template is the first one whose name matches.
        match = re.search(
            r"\{\{\s*QuoteTranslation\b.*?\}\}",
            text,
            flags=re.IGNORECASE | re.S,
        )
        if not match:
            break
        replacement = quote
        text = text[: match.start()] + replacement + text[match.end() :]
        return text, translation, script
    return text, None, None


def _classify_verbal(text: str) -> tuple[str, bool]:
    """Split stage directions from the spoken words.

    ``*laughs* What power.`` keeps the words and drops the direction;
    ``*grunts*`` has no words, so it stays as a label and is marked non-verbal
    (useful for a dataset, but not as a transcript for TTS).
    """

    without_directions = DIRECTION_RE.sub(" ", text)
    words = re.sub(r"[^\w]+", "", without_directions)
    if words:
        return re.sub(r"\s+", " ", without_directions).strip(" ,;:-"), True
    directions = [match.strip("* ") for match in DIRECTION_RE.findall(text)]
    label = "; ".join(d for d in directions if d) or text.strip("* ").strip()
    return label, False


def _speaker_from_bullet(line: str) -> tuple[str | None, str]:
    match = re.match(r"^\s*'''\s*(.+?)\s*'''\s*:?\s*(.*)$", line, flags=re.S)
    if match:
        return match.group(1).rstrip(":").strip(), match.group(2)
    match = re.match(r"^\s*([A-Z][^:\n]{0,40}?)\s*:\s*(.*)$", line, flags=re.S)
    if match:
        return match.group(1).strip(), match.group(2)
    return None, line


def _parse_quote_cell(cell: str) -> list[_Segment]:
    lines = cell.splitlines()
    bullet_indexes = [i for i, line in enumerate(lines) if line.lstrip().startswith("*")]
    if not bullet_indexes:
        text, translation, script = _extract_translation(cell)
        cleaned = _clean_text(text)
        if not cleaned:
            return []
        cleaned, verbal = _classify_verbal(cleaned)
        return [_Segment(cleaned, translation, script, verbal=verbal)] if cleaned else []

    segments: list[_Segment] = []
    for line in lines:
        if line.lstrip().startswith("*"):
            # "**" is a nested/alternative bullet; strip the whole run.
            body = line.lstrip().lstrip("*").strip()
            # Italic-only notes ("''One of three:''", "''(one of two):''") are
            # table instructions, not spoken lines. Without this guard the
            # plain "Name:" speaker pattern mistakes them for a character.
            if re.match(r"^''.+?:\s*''$", body) or re.match(r"^\([^)]*\)\s*:?$", body):
                continue
            speaker, rest = _speaker_from_bullet(body)
            text, translation, script = _extract_translation(rest)
            cleaned = _clean_text(text)
            if not cleaned:
                continue
            # Parenthetical notes such as "''(one of two):''" are table
            # instructions, not lines spoken by anyone.
            if not speaker and re.match(r"^\([^()]*\)\s*:?$", cleaned):
                continue
            cleaned, verbal = _classify_verbal(cleaned)
            if not cleaned:
                continue
            if speaker:
                speaker = _clean_text(speaker) or None
            segments.append(_Segment(cleaned, translation, script, speaker, verbal))
        elif segments:
            extra, translation, script = _extract_translation(line)
            extra = _clean_text(extra)
            if extra:
                combined, _ = _classify_verbal(f"{segments[-1].text} {extra}")
                segments[-1].text = combined
                segments[-1].translation = segments[-1].translation or translation
    return segments


def _extract_audio_files(cell: str) -> list[str]:
    found: list[str] = []
    for args in _iter_templates(cell, AUDIO_TEMPLATE_NAME):
        positional: list[str] = []
        for part in _split_top_level(args, "|"):
            if re.match(r"^\s*[A-Za-z_-]+\s*=", part):
                continue
            positional.append(part.strip())
        if not positional:
            continue
        name = positional[0].strip()
        name = re.sub(r"^\[\[(?:File|Image):", "", name, flags=re.IGNORECASE)
        name = name.rstrip("]").strip()
        name = re.sub(r"^File:", "", name, flags=re.IGNORECASE)
        name = name.replace("\n", " ").strip()
        if not name.lower().endswith(MEDIA_EXTENSIONS):
            continue
        canonical = canonical_file_name(name)
        if canonical and canonical not in found:
            found.append(canonical)
    return found


def _speaker_from_filename(filename: str, character: str) -> str:
    stem = filename.rsplit(".", 1)[0].replace("_", " ")
    match = re.match(r"^([^-]+?)\s+-\s+", stem)
    if match:
        candidate = match.group(1).strip()
        if candidate:
            return candidate
    return character


def _same_speaker(left: str, right: str) -> bool:
    def normalise(value: str) -> str:
        return re.sub(r"[^a-z0-9]", "", value.casefold())

    return normalise(left) == normalise(right)


FRENCH_WORDS = re.compile(
    r"\b(?:le|la|les|un|une|des|du|de|je|tu|il|elle|nous|vous|ils|elles|"
    r"c'est|n'est|pas|pour|avec|dans|mon|ma|mes|ton|ta|tes|son|sa|ses|"
    r"est|sont|que|qui|quoi|plus|rien|tout|tous|toute|comme|mais|sur)\b",
    re.IGNORECASE,
)
FRENCH_CHARS = re.compile(r"[àâçéèêëîïôûùüÿœæ]", re.IGNORECASE)


def guess_language_from_text(text: str, translation: str | None) -> str | None:
    """Best-effort fallback for translated quotes with unmarked file names.

    Scripts are unambiguous, so they are detected directly. A Latin-script
    quote with a translation gets a French tag only when it has French-specific
    characters or at least two common French words; anything else stays
    undetermined rather than mislabelled.
    """

    if not translation:
        return None
    if re.search(r"[\u3040-\u30ff]", text):
        return "ja"
    if re.search(r"[\uac00-\ud7af]", text):
        return "ko"
    if re.search(r"[\u4e00-\u9fff]", text):
        return "zh"
    if re.search(r"[\u0400-\u04ff]", text):
        return "ru"
    if re.search(r"[\u0600-\u06ff]", text):
        return "ar"
    if re.search(r"[\u0900-\u097f]", text):
        return "hi"
    if FRENCH_CHARS.search(text):
        return "fr"
    if len(FRENCH_WORDS.findall(text)) >= 2:
        return "fr"
    return None


def infer_language(
    filename: str,
    translation: str | None,
    script_hint: str | None = None,
    text: str | None = None,
) -> str:
    haystack = filename.casefold()
    for marker, code in LANGUAGE_MARKERS:
        if marker in haystack:
            return code
    if script_hint:
        hint = script_hint.casefold()
        for marker, code in SCRIPT_LANGUAGES:
            if marker in hint:
                return code
    if translation:
        guessed = guess_language_from_text(text or "", translation)
        return guessed or "und"
    return "en"


def _find_columns(header: list[str] | None) -> tuple[int, int, int]:
    """Return ``(context_idx, quote_idx, audio_idx)`` for a table."""

    if not header:
        return 0, -2, -1

    names = [_clean_context(cell).casefold() for cell in header]
    audio_idx = next((i for i, name in enumerate(names) if "audio" in name), None)
    quote_idx = next(
        (i for i, name in enumerate(names) if "quote" in name or "line" in name),
        None,
    )
    if audio_idx is None:
        audio_idx = len(names) - 1
    if quote_idx is None:
        quote_idx = 0 if audio_idx != 0 else 1
    context_idx = next(
        (i for i in range(len(names)) if i not in (quote_idx, audio_idx)),
        0,
    )
    return context_idx, quote_idx, audio_idx


def _parse_table(
    table: str,
    *,
    section: str,
    page: str,
    character: str,
    revision: int | None,
    result: ParseResult,
) -> None:
    body = re.sub(r"^\{\|[^\n]*\n?", "", table, count=1)
    body = re.sub(r"\n?\|\}\s*$", "", body, count=1)
    rows = _expand_rowspans(_parse_rows(body))
    if not rows:
        return
    result.tables_seen += 1

    header_row = next((row for row in rows if row.is_header), None)
    header_cells = header_row.cells if header_row else None
    context_idx, quote_idx, audio_idx = _find_columns(header_cells)

    for row in rows:
        if row.is_header:
            continue
        width = max(len(row.cells), audio_idx + 1, quote_idx + 1)
        if not any(cell.strip() for cell in row.cells):
            continue
        result.rows_seen += 1
        cells = row.cells + [""] * max(0, width - len(row.cells))
        # Negative indexes mean "last/second-to-last column" for headerless
        # tables; guard rows that are shorter than that.
        context = (
            _clean_context(cells[context_idx]) if -len(cells) <= context_idx < len(cells) else ""
        )
        quote_cell = cells[quote_idx] if -len(cells) <= quote_idx < len(cells) else ""
        audio_cell = cells[audio_idx] if -len(cells) <= audio_idx < len(cells) else ""

        audios = _extract_audio_files(audio_cell)
        result.audio_refs += len(audios)
        if not audios:
            result.rows_without_audio += 1
            continue

        segments = _parse_quote_cell(quote_cell)
        if not segments:
            result.rows_without_text += 1
            continue

        if len(segments) == len(audios):
            pairs = list(zip(audios, segments, strict=True))
        elif len(segments) == 1:
            pairs = [(audio, segments[0]) for audio in audios]
        else:
            distinct_speakers: list[str] = []
            for segment in segments:
                if segment.speaker and not any(
                    _same_speaker(segment.speaker, known) for known in distinct_speakers
                ):
                    distinct_speakers.append(segment.speaker)

            if section == "Interactions" and len(audios) == 1 and len(distinct_speakers) <= 1:
                # One conversation clip, several lines by the same speaker:
                # keep every line as the transcript for that clip.
                joined = " ".join(dict.fromkeys(segment.text for segment in segments))
                translations = [segment.translation for segment in segments if segment.translation]
                merged = _Segment(
                    joined,
                    " / ".join(dict.fromkeys(translations)) or None,
                    segments[0].script_hint,
                    distinct_speakers[0] if distinct_speakers else None,
                    all(segment.verbal for segment in segments),
                )
                pairs = [(audios[0], merged)]
            elif section == "Interactions" and len(audios) == 1 and len(distinct_speakers) > 1:
                # A clip that contains several speakers is not a clean
                # single-voice sample. Label it explicitly so the target-speaker
                # filter excludes it unless the caller asks for every speaker.
                joined = " / ".join(
                    f"{segment.speaker}: {segment.text}" if segment.speaker else segment.text
                    for segment in segments
                )
                translations = [segment.translation for segment in segments if segment.translation]
                merged = _Segment(
                    joined,
                    " / ".join(dict.fromkeys(translations)) or None,
                    None,
                    " + ".join(distinct_speakers),
                    all(segment.verbal for segment in segments),
                )
                pairs = [(audio, merged) for audio in audios]
                result.warnings.append(
                    f"{page} [{section}] {context or '-'}: {len(audios)} multi-speaker "
                    f"clip(s) labelled {' + '.join(distinct_speakers)}"
                )
            else:
                # Best effort: pair each file with the segment by the speaker in
                # its filename, then fall back to the first line.
                pairs = []
                for audio in audios:
                    speaker = _speaker_from_filename(audio, character)
                    match = next(
                        (
                            segment
                            for segment in segments
                            if segment.speaker and _same_speaker(segment.speaker, speaker)
                        ),
                        segments[0],
                    )
                    pairs.append((audio, match))
                result.warnings.append(
                    f"{page} [{section}] {context or '-'}: {len(segments)} text lines for "
                    f"{len(audios)} audio files; paired by speaker/first line"
                )

        for audio, segment in pairs:
            if not segment.text:
                continue
            speaker = segment.speaker
            if section == "Interactions":
                speaker = speaker or _speaker_from_filename(audio, character)
            else:
                # Outside interactions every file on a hero page is that hero,
                # even when the file name is an internal id (000000043B9D.ogg).
                speaker = character
            utterance = Utterance(
                character=character,
                speaker=speaker,
                section=section,
                context=context,
                text=segment.text,
                translation=_clean_translation(segment.translation),
                language=infer_language(
                    audio,
                    segment.translation,
                    segment.script_hint,
                    segment.text,
                ),
                verbal=segment.verbal,
                audio_file=audio,
                source_page=page,
                source_revision=revision,
            )
            result.utterances.append(utterance)


def _sections(wikitext: str) -> list[tuple[str, str]]:
    matches = list(re.finditer(r"(?m)^(==)(?!=)\s*(.+?)\s*==\s*$", wikitext))
    if not matches:
        return [("", wikitext)]
    sections: list[tuple[str, str]] = []
    preamble = wikitext[: matches[0].start()]
    if preamble.strip():
        sections.append(("", preamble))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(wikitext)
        sections.append((match.group(2).strip(), wikitext[match.end() : end]))
    return sections


def character_from_page(page: str) -> str:
    """``Widowmaker/Quotes/Overwatch 1`` -> ``Widowmaker``."""

    return page.split("/", 1)[0].strip().replace("_", " ")


def parse_page(
    wikitext: str,
    *,
    page: str,
    character: str | None = None,
    revision: int | None = None,
) -> ParseResult:
    """Parse every quote table on a hero quotes page."""

    character = (character or character_from_page(page)).strip()
    result = ParseResult()

    for section, body in _sections(wikitext):
        for table in _table_blocks(body):
            _parse_table(
                table,
                section=section or "Preamble",
                page=page,
                character=character,
                revision=revision,
                result=result,
            )

    return result
