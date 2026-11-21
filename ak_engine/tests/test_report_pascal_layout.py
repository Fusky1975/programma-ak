"""Tests for the Pascal-style report layout (title page, ACTION REPORT
paragraphs, letters, state sections) -- the shapes below are taken from the
real ``SE3__T*.K1`` reports written by the original program."""

from __future__ import annotations

import random

from ak_engine.report.layout import flow_prose_in_lines, looks_like_prose
from ak_engine.report.title_page import centered, processed_turn_title_lines, quote_block, quote_index_for_turn
from ak_engine.report.turn_report import (
    LETTER_SQUIRE_NAMES,
    _flow_battle_block,
    _flow_story_lines,
    _polish_state_sections,
    _reflexive_possessive,
    _to_first_person,
    render_season_intro,
)


def test_title_page_has_the_banner_the_king_and_the_quote_block():
    lines = processed_turn_title_lines(3, 4, "Fusky")

    assert lines[:2] == ["", ""]
    assert lines[2] == centered("ADVENTURER-KINGS:  GAME 3, TURN 4")
    assert lines[4] == centered("FOR")
    assert lines[6] == centered("FUSKY")
    assert "  Quote of the Week:" in lines
    assert lines[-2:] == ["", ""]


def test_banner_is_centered_left_biased_on_a_71_column_page():
    # SE3__T3.K1: "ADVENTURER-KINGS:  GAME 3, TURN 3" is 33 characters wide.
    assert centered("ADVENTURER-KINGS:  GAME 3, TURN 3") == " " * 19 + "ADVENTURER-KINGS:  GAME 3, TURN 3"


def test_quote_block_is_stable_for_a_turn_and_lines_stay_within_the_margin():
    assert quote_index_for_turn(1, 5) == quote_index_for_turn(1, 5)
    assert all(len(line) <= 77 for line in quote_block(quote_index_for_turn(1, 5)))


def test_first_person_rewrites_subject_possessive_and_object():
    sentence = "Tao-Li recruited the 272nd Dragons, to serve under Guerin; Tao-Li's skill grew and Guerin thanked Tao-Li."

    assert _to_first_person(sentence, "Tao-Li") == (
        "I recruited the 272nd Dragons, to serve under Guerin; my skill grew and Guerin thanked me."
    )


def test_first_person_after_a_season_connector_and_a_sentence_end():
    assert _to_first_person("Done.  Teleko could not recruit Wargs.", "Teleko") == "Done.  I could not recruit Wargs."
    assert _to_first_person("Speaking with farmers, Teleko heard a rumor.", "Teleko") == (
        "Speaking with farmers, I heard a rumor."
    )


def test_reflexive_possessive_uses_the_pronoun_for_the_actors_own_things():
    assert _reflexive_possessive("Fusky practiced Fusky's Tactics well.", "Fusky", "his") == (
        "Fusky practiced his Tactics well."
    )
    assert _reflexive_possessive("In spring, Gladstone marched Gladstone's command.", "Gladstone", "his") == (
        "In spring, Gladstone marched his command."
    )


def test_a_sentence_that_opens_with_the_possessive_name_keeps_it():
    assert _reflexive_possessive("Tao-Li's naval forces took control of the Crabman Sea.", "Tao-Li", "her") == (
        "Tao-Li's naval forces took control of the Crabman Sea."
    )


def test_squire_names_are_the_ones_of_the_real_reports():
    assert set(LETTER_SQUIRE_NAMES) == {"Gunga Din", "Gridley", "Watson", "Montgomery", "Tattoo", "Mortimer"}


def test_season_intro_for_each_phase_mentions_the_actor():
    rng = random.Random(7)
    for phase_index in range(5):
        text, is_connector = render_season_intro(phase_index, "Fusky", "his", rng)
        assert text[0].isupper()
        assert is_connector == text.endswith(" ")


def test_battle_block_sets_the_diagram_off_by_blank_lines_and_splits_paragraphs():
    lines = [
        "The armies were drawn up into lines of battle as shown here:",
        "  ATTACKING ARMY, Battle of Javir (1306):",
        "",
        " 138th/A  ",
        "  Legion  ",
        "----------",
        "  DEFENDING ARMY",
        "standing at the ready with Gladstone's warriors was Gladstone.",
        "no generals were present to lead the forces of the natives of Javir.",
        "the 138th Orc Legion battled with the 127th Dragons and was steadily pushed back.",
        "the defenders turned back Fusky's forces.",
    ]

    out = _flow_battle_block(lines, set())

    diagram_start = out.index("  ATTACKING ARMY, Battle of Javir (1306):")
    assert out[diagram_start - 1] == ""
    assert out[diagram_start - 2].startswith("  The armies were drawn up")
    diagram_end = out.index("  DEFENDING ARMY")
    assert out[diagram_end + 1] == ""
    prose = out[diagram_end + 2 :]
    assert prose[0].startswith("  Standing at the ready with Gladstone's warriors was Gladstone.")
    assert any(line.startswith("  The 138th Orc Legion battled") for line in prose)
    assert any(line.startswith("  The defenders turned back") for line in prose)


def test_story_lines_without_a_battle_are_flowed_as_prose():
    out = _flow_story_lines(["Fusky was blackmailed.", "Gladstone paid up."], set())

    assert out == ["  Fusky was blackmailed.  Gladstone paid up."]


def test_looks_like_prose_tells_introductions_from_tables_and_figures():
    assert looks_like_prose("O Great One, I submit for thy examination the following figures concerning the finances")
    assert not looks_like_prose("Gold in treasury:   3")
    assert not looks_like_prose("Province            Tax   Race   Terrain  Expl%     Type 1     Type 2")
    assert not looks_like_prose("  Sire, our royal scribe has drawn up a map of all neighboring lands: ")
    assert not looks_like_prose("None at present")


def test_flow_prose_in_lines_leaves_non_prose_lines_alone():
    lines = ["FINANCES", "", "Gold in treasury:   3"]

    assert flow_prose_in_lines(lines) == lines


def test_state_sections_get_indented_lists_and_figures():
    lines = [
        "DIPLOMACY",
        "",
        "My lord, the following Kings have wisely allied with thy ever-victorious majesty:",
        "",
        "None at present",
        "",
        "My lord, the following Kings are foolishly at war with thy ever-victorious majesty:",
        "",
        "Vitello (#2)",
        "",
        "FINANCES",
        "Gold in treasury:   3",
        "Expected Revenues:  10",
        "Expected Expenses:  17",
    ]

    out = _polish_state_sections(lines, {"Vitello"})

    assert "  None at present" in out
    assert "  Vitello (#2)" in out
    assert "  Gold in treasury:    3" in out
    assert "  Expected Revenues:  10" in out
    assert "  Expected Expenses:  17" in out
    second_intro = next(i for i, line in enumerate(out) if line.startswith("  My lord, the following Kings are foolishly"))
    assert out[second_intro - 2 : second_intro] == ["", ""]
    assert all(len(line) <= 77 for line in out)
