from __future__ import annotations

from pathlib import Path

import pytest
from overwatch_voice_lines.wikitext import (
    character_from_page,
    guess_language_from_text,
    infer_language,
    parse_page,
)

FIXTURE = Path(__file__).parent / "fixtures" / "quotes_sample.wikitext"


@pytest.fixture(scope="module")
def parsed():
    return parse_page(
        FIXTURE.read_text(encoding="utf-8"),
        page="Widowmaker/Quotes",
        character="Widowmaker",
        revision=123,
    )


def by_audio(parsed, needle: str):
    matches = [u for u in parsed.utterances if needle in u.audio_file]
    assert matches, f"no utterance for {needle!r}"
    return matches[0]


def test_parses_sections_and_skips_empty_audio(parsed):
    assert set(parsed.by_section()) == {
        "Abilities",
        "Interactions",
        "Non-Languages",
        "Voice Lines",
    }
    assert parsed.rows_without_audio == 1  # grappling hook grunt has no audio
    assert parsed.audio_refs == 17


def test_rowspan_context_is_applied(parsed):
    shy = by_audio(parsed, "Don't be shy")
    begin = by_audio(parsed, "Let the performance begin")
    assert shy.context == "Widow's Kiss / Scoped"
    assert begin.context == shy.context
    assert shy.section == "Abilities"


def test_inline_double_pipe_is_one_cell(parsed):
    begin = by_audio(parsed, "Let the performance begin")
    assert begin.text == "Let the performance begin."
    assert begin.speaker == "Widowmaker"


def test_quote_translation_uses_spoken_language(parsed):
    french = by_audio(parsed, "(French)")
    assert french.text == "Cible repérée."
    assert french.translation == "Target detected."
    assert french.language == "fr"
    assert french.speaker == "Widowmaker"


def test_multiple_audio_per_quote_becomes_multiple_records(parsed):
    jumps = [u for u in parsed.utterances if "jumping grunt" in u.audio_file]
    assert len(jumps) == 2
    assert {u.text for u in jumps} == {"jumping grunt"}
    assert all(not u.verbal for u in jumps)
    assert all(u.section == "Non-Languages" for u in jumps)


def test_interaction_bullets_pair_with_audio(parsed):
    ana = by_audio(parsed, "I heard Talon")
    widow = by_audio(parsed, "Do not speak to me")
    assert ana.speaker == "Ana"
    assert ana.text == "I heard Talon failed another mission."
    assert widow.speaker == "Widowmaker"
    assert widow.section == "Interactions"


def test_note_and_alternative_bullets_are_handled(parsed):
    doomfist = by_audio(parsed, "Doomfist - You're coming")
    reaper = by_audio(parsed, "Reaper - You're coming")
    baptiste = by_audio(parsed, "Why won't you leave me alone")
    assert doomfist.speaker == "Doomfist"
    assert reaper.speaker == "Reaper"
    assert baptiste.speaker == "Baptiste"
    assert "one of two" not in doomfist.text.casefold()


def test_single_clip_with_two_speakers_is_labelled_mixed(parsed):
    mixed = by_audio(parsed, "Ana pregame")
    assert mixed.speaker == "Ana + Widowmaker"
    assert "You were once a legend." in mixed.text
    assert "Things change." in mixed.text


def test_stage_directions_are_removed_but_words_kept(parsed):
    power = by_audio(parsed, "What power")
    assert power.text == "What power."
    assert power.verbal is True


def test_context_templates_and_media_extensions(parsed):
    encore = by_audio(parsed, "Encore.ogg")
    assert encore.context == "Credits 25"
    perfect = by_audio(parsed, "A perfect 10.mp3")
    assert perfect.context == "Summer Games"
    assert perfect.audio_file.endswith(".mp3")


def test_character_from_page():
    assert character_from_page("Widowmaker/Quotes") == "Widowmaker"
    assert character_from_page("Widowmaker/Quotes/Overwatch 1") == "Widowmaker"


@pytest.mark.parametrize(
    ("filename", "translation", "text", "expected"),
    [
        ("Widowmaker - Hello.ogg", None, "Hello.", "en"),
        ("Widowmaker - (French) Bonjour.ogg", "Hello.", "Bonjour.", "fr"),
        ("Widowmaker - Bonjour.ogg", "Hello.", "Bonjour.", "und"),
        ("Widowmaker - Bonjour.ogg", "Hello.", "À la vie, à la mort.", "fr"),
        ("Widowmaker - Hello.ogg", "Hello.", "こんにちは", "ja"),
        ("Widowmaker - Hello.ogg", "Hello.", "Привет", "ru"),
    ],
)
def test_infer_language(filename, translation, text, expected):
    assert infer_language(filename, translation, text=text) == expected


def test_guess_language_requires_translation():
    assert guess_language_from_text("À la vie", None) is None
    assert guess_language_from_text("À la vie", "To life") == "fr"
