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

    out = _flow_battle_block(lines, set(), {})

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


# ---- stage 2 -------------------------------------------------------------

import random as _random

from ak_engine.models.advanced_ability import AdvancedAbility
from ak_engine.models.alignment import Alignment
from ak_engine.models.game_state import GameState, HexCoord, KingdomState, LeaderState, ProvinceState
from ak_engine.models.map import Terrain
from ak_engine.models.office import Office
from ak_engine.models.race import Race
from ak_engine.report.turn_report import (
    _FIXED_PARAGRAPHS,
    _apply_fixed_paragraphs,
    _characters_report_display_name,
    _pascal_armies_lines,
    _pascal_office_table,
    _special_abilities_lines,
    _wanderer_news_lines,
    compose_letter_report,
)


def test_office_table_reproduces_the_real_se3_rows():
    # Rows copied from SE3__T3.K1 (column positions included).
    lines = [
        "Imperial Treasurer        Uga-Buga Makumb (5 points, rank 5, 46%)",
        "Esteemed High Chancellor  Guerin (4 points, rank 8, 33%)",
        "                          Lallipugh (3 points, rank 13, 22%)",
        "Imperial Grand Marshal    Teleko (2 points, rank 8, 38%)",
        "                          Uga-Buga Makumb (2 points, rank 8, 38%)",
        "Lord High Defender        Odysseus (1 points, rank 2, None)",
        "                          Teleko (1 points, rank 2, None)",
    ]

    out = _pascal_office_table(lines)

    assert out[0] == "Imperial Office           Best Hope     Rank  Riv%   Second Hope   Rank  Riv%"
    assert out[1] == "Imperial Treasurer        Uga-Buga Makumb  5    46   None"
    assert out[2] == "Esteemed High Chancellor  Guerin           8    33   Lallipugh       13    22"
    assert out[3] == "Imperial Grand Marshal    Teleko           8    38   Uga-Buga Makumb   8    38"
    assert out[4] == "Lord High Defender        Odysseus         2     0   Teleko           2     0"


def test_office_table_drops_unheld_optional_titles_but_keeps_mandatory_ones():
    lines = [
        "Imperial Treasurer        None at present",
        "King of Pain              None at present",
    ]

    out = _pascal_office_table(lines)

    assert out[-1] == "Imperial Treasurer        None"
    assert not any("King of Pain" in line for line in out)


def test_armies_section_ends_with_the_modified_quality_note():
    lines = ["ARMIES", "intro", "", "table row", ""]

    out = _pascal_armies_lines(lines)

    assert out[-2:] == [
        '  Note: "Modified Quality" includes the modifiers for your home-province    ',
        "bonus, desert terrain, special magic items, race and druidic ability.       ",
    ]
    assert out[-4:-2] == ["", ""]


def test_armies_section_sets_the_mercenary_list_off_by_two_blank_lines():
    lines = ["ARMIES", "row", "", "The following unit(s) are independent mercenaries which you may Recruit:", "", "row"]

    out = _pascal_armies_lines(lines)

    at = out.index("The following unit(s) are independent mercenaries which you may Recruit:")
    assert out[at - 2 : at] == ["", ""]
    assert out[-3] == ""


def _state_with_hero(name: str, leader_id: int) -> tuple[GameState, LeaderState]:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Humania", Race.HUMAN, Alignment.GOOD, HexCoord(0, 0)))
    hero = LeaderState(leader_id, kingdom_id=1, name=name, location=HexCoord(0, 0))
    state.add_leader(hero)
    return state, hero


def test_character_names_carry_the_leader_number_in_a_14_column_field():
    state, hero = _state_with_hero("Guerin", 18)
    assert _characters_report_display_name(state, hero, with_id=True) == "Guerin (18)"
    long_hero = LeaderState(30, kingdom_id=1, name="Melantheus", location=HexCoord(0, 0))
    assert _characters_report_display_name(state, long_hero, with_id=True) == "Melantheus(30)"
    other = LeaderState(97, kingdom_id=1, name="Odysseus", location=HexCoord(0, 0))
    assert _characters_report_display_name(state, other, with_id=True) == "Odysseus (97)"


def test_special_abilities_block_lists_office_perks_and_advanced_abilities():
    _, hero = _state_with_hero("Uga-Buga", 1)
    hero.advanced_abilities.add(AdvancedAbility.GATE_DEMON_SPELL)

    lines = _special_abilities_lines(hero, [Office.TREASURER, Office.MAGE])

    assert lines[0] == "Special Abilities:  "
    assert "  IMPERIAL TREASURER: Know Treasuries" in lines
    assert "  ARCH-MAGE: Sense Magic Items in Province" in lines
    assert '  "GATE DEMON" SPELL: Summon Demon' in lines
    assert lines[-1] == " " * 77


def test_a_leader_without_special_abilities_gets_no_block():
    _, hero = _state_with_hero("Guerin", 18)

    assert _special_abilities_lines(hero, []) == []


def test_fixed_introductions_get_the_original_line_breaks():
    line = (
        "My lord, the following Kings have wisely allied with thy ever-victorious majesty:"
    )

    assert _apply_fixed_paragraphs([line]) == [
        "  My lord, the following Kings have wisely allied with thy ever-",
        "victorious majesty:                    ",
    ]
    assert len(_FIXED_PARAGRAPHS) == 10


def test_wanderers_news_lists_events_in_the_kingdoms_own_provinces_only():
    state, _ = _state_with_hero("Guerin", 18)
    home = state.kingdoms[1].home_province
    state.add_province(ProvinceState(home, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, name="Numenor"))
    state.record_world_event(home, ["Drago (#39) has arrived in Cantia from Orielle."], kind="wander")
    state.record_world_event(home, ["Somebody was battling."])

    assert _wanderer_news_lines(state, 1) == ["Drago (#39) has arrived in Cantia from Orielle."]
    assert _wanderer_news_lines(state, 2) == []


def test_compose_letter_report_in_pascal_layout_reports_wanderers_before_the_finances():
    state, _ = _state_with_hero("Guerin", 18)
    state.leaders[18].is_king = True
    home = state.kingdoms[1].home_province
    state.add_province(ProvinceState(home, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, name="Numenor"))
    state.record_world_event(home, ["Drago (#39) has arrived in Cantia from Orielle."], kind="wander")

    report = compose_letter_report([], state, 1, _random.Random(1), pascal_layout=True)

    news = report.index("  Your Majesty, I have news to report of wanderers in our kingdom:  ")
    assert report[news + 1] == "  Drago (#39) has arrived in Cantia from Orielle."
    assert any(line.startswith("  Here is the financial report") for line in report[news:])
    assert "ACTION REPORT    " in report
    assert "CHARACTERS   " in report


# ---- stage 3 -------------------------------------------------------------

from ak_engine.models.feature import Feature, FeatureType
from ak_engine.report.turn_report import feature_label


def test_feature_label_has_article_name_and_number():
    assert feature_label(Feature(97, HexCoord(0, 0), FeatureType.ALTAR)) == "an Altar (#97)"
    assert feature_label(Feature(126, HexCoord(0, 0), FeatureType.GLADE)) == "a Glade (#126)"


def test_feature_label_uses_an_before_any_vowel_name():
    from ak_engine.models.feature import FEATURE_TYPE_NAMES

    for kind, name in FEATURE_TYPE_NAMES.items():
        label = feature_label(Feature(1, HexCoord(0, 0), kind))
        article = label.split(" ", 1)[0]
        assert article == ("an" if name[0].upper() in "AEIOU" else "a")


def test_discovery_sentence_with_a_leading_adjective_keeps_a_single_article():
    from ak_engine.models.monster import Monster
    from ak_engine.report.turn_report import describe_feature_discovery

    feature = Feature(88, HexCoord(0, 0), FeatureType.CAVE, guardian_monster=Monster.DRYAD)
    seen = set()
    for seed in range(40):
        first = describe_feature_discovery(feature, "Guerin", "Hollabrand", _random.Random(seed))[0]
        assert " a a " not in first and " an a " not in first and "a an " not in first
        seen.add("previously" in first or "heretofore" in first)
        assert "Cave" in first
    assert True in seen


def test_battle_narration_uses_the_pronoun_for_a_leaders_own_troops():
    lines = [
        "The armies were drawn up into lines of battle as shown here:",
        "  ATTACKING ARMY, Battle of Javir (1306):",
        "",
        "  DEFENDING ARMY",
        "Gladstone stood ready at the head of Gladstone's thousands.",
    ]

    out = _flow_battle_block(lines, {"Gladstone"}, {"Gladstone": "his"})

    assert "  Gladstone stood ready at the head of his thousands." in out


# ---- audit fixes ---------------------------------------------------------


def test_first_person_leaves_a_longer_name_that_contains_the_writers_alone():
    assert _to_first_person("Isis rode into Isis Sea.  Isis was hurt.", "Isis", ["Isis Sea"]) == (
        "I rode into Isis Sea.  I was hurt."
    )


def test_first_person_treats_a_name_after_a_conjunction_as_the_subject_and_fixes_the_verb():
    assert _to_first_person("Guerin has a plan, and Guerin found himself in Hollabrand.", "Guerin") == (
        "I have a plan, and I found myself in Hollabrand."
    )
    assert _to_first_person("The Dragon spoke to Guerin, and Guerin replied.", "Guerin") == (
        "The Dragon spoke to me, and I replied."
    )


def test_first_person_does_not_split_a_hyphenated_name():
    assert _to_first_person("Tao-Li hired Tao and Tao-Li's friend.", "Tao-Li") == "I hired Tao and my friend."


def test_reflexive_possessive_looks_at_each_sentence_on_its_own():
    assert _reflexive_possessive("Fusky marched.  Fusky's army won.", "Fusky", "his") == (
        "Fusky marched.  Fusky's army won."
    )
    assert _reflexive_possessive("Fusky took Fusky's prize.  Fusky kept Fusky's word.", "Fusky", "his") == (
        "Fusky took his prize.  Fusky kept his word."
    )


def test_reflexive_possessive_ignores_a_name_inside_another_word():
    assert _reflexive_possessive("Anna met Ann and Ann's friend.", "Ann", "her") == "Anna met Ann and her friend."


def test_office_table_handles_fractional_points_and_a_paragraph_between_rows():
    lines = [
        "Imperial Treasurer        Warg Riders army in Rosewood (19.0 points, rank 1, 50%)",
        "",
        "As the Treasurer Fusky did something.",
        "                          Gladstone (3 points, rank 2, 30%)",
        "Imperial Grand Marshal    Teleko (2 points, rank 8, 38%)",
    ]

    out = _pascal_office_table(lines)

    assert not any("points" in line for line in out)
    assert out[1].startswith("Imperial Treasurer        Warg Riders army in Rosewood")
    assert "Gladstone" in out[1]
    assert out[2:4] == ["", "As the Treasurer Fusky did something."]
    assert out[4].startswith("Imperial Grand Marshal    Teleko")


def test_reset_turn_report_scratch_empties_every_per_turn_list():
    state, _ = _state_with_hero("Guerin", 18)
    state.record_world_event(HexCoord(0, 0), ["x"], kind="wander")
    state.battle_narratives_by_kingdom[1] = ["stale battle"]
    state.blackmail_narratives_by_kingdom[1] = ["stale"]
    state.tornado_victim_notices_by_kingdom[1] = ["stale"]
    state.plague_victim_notices_by_kingdom[1] = ["stale"]
    state.illusory_terrain_reveals_by_kingdom[1] = ["stale"]

    state.reset_turn_report_scratch()

    assert state.world_events == []
    assert state.battle_narratives_by_kingdom == {}
    assert state.blackmail_narratives_by_kingdom == {}
    assert state.tornado_victim_notices_by_kingdom == {}
    assert state.plague_victim_notices_by_kingdom == {}
    assert state.illusory_terrain_reveals_by_kingdom == {}
