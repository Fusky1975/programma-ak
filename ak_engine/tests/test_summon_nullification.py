"""Mirror Image, Gate Demon, Gate Angel and Illusory Hero dissolve each other, in any
combination, when two of them meet in an encounter (user-specified 2026-11-23)."""

from __future__ import annotations

import itertools
import random
from unittest.mock import patch

import pytest

from ak_engine.models.alignment import Alignment
from ak_engine.models.enums import Ability, Maneuver, Spell
from ak_engine.models.feature import Feature, FeatureType
from ak_engine.models.game_state import GameState, KingdomState, LeaderState
from ak_engine.models.kingdom import SkillTable
from ak_engine.models.map import HexCoord
from ak_engine.models.monster import Monster
from ak_engine.models.race import Race
from ak_engine.report.turn_report import describe_summon_nullifications
from ak_engine.turn.challenge_execution import execute_challenge
from ak_engine.turn.challenge_pursue_decode import ChallengeRequest
from ak_engine.turn.encounter import SUMMON_SPELLS, EncounterCombatResult
from ak_engine.turn.search_decode import SearchRequest, SearchTactic
from ak_engine.turn.search_execution import execute_search

FIELD = HexCoord(1, 1)


def _mage_skills() -> SkillTable:
    raw = [0] * 30
    for ability in (Ability.ILLUSION, Ability.NECROMANCY, Ability.WHITE):
        raw[ability.value * 2] = 5
        raw[ability.value * 2 + 1] = 9
    return SkillTable(raw)


def _cast(spell: Spell) -> SearchTactic:
    return SearchTactic(Maneuver.CAST, spell.value)


# -- the set itself --


def test_the_four_summoning_spells():
    assert SUMMON_SPELLS == {Spell.MIRROR_IMAGE, Spell.GATE_DEMON, Spell.GATE_ANGEL, Spell.ILLUS_HERO}


# -- Challenge: two mages --

CHALLENGE_SPELLS = (Spell.MIRROR_IMAGE, Spell.GATE_DEMON, Spell.ILLUS_HERO)  # Gate Angel is a Search-only duel


def _two_mages(second_plan) -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, FIELD))
    state.add_kingdom(KingdomState(2, "Defendia", Race.HUMAN, Alignment.GOOD, FIELD))
    state.add_leader(LeaderState(1, 1, "Attacker", FIELD, skills=_mage_skills(), alignment=Alignment.GOOD))
    state.add_leader(
        LeaderState(
            2, 2, "Defender", FIELD, skills=_mage_skills(), alignment=Alignment.GOOD, special_encounter_plan=tuple(second_plan)
        )
    )
    return state


def _challenge(state: GameState, first_plan, *, rolls=(True, True)):
    request = ChallengeRequest(target_character_id=2, unconfirmed_extra0=0, tactics=list(first_plan))
    with patch("ak_engine.turn.challenge_execution.resolve_personal_combat_spell_cast", side_effect=list(rolls)), patch(
        "ak_engine.turn.challenge_execution.resolve_mirror_image_duel"
    ) as mirror, patch("ak_engine.turn.challenge_execution.resolve_illusory_hero_duel") as hero, patch(
        "ak_engine.turn.challenge_execution.roll_gate_demon_type"
    ) as demon, patch("ak_engine.turn.challenge_execution.resolve_melee_duel") as melee:
        melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        result = execute_challenge(state, 1, request, rng=random.Random(0))
    return result, {"mirror": mirror, "hero": hero, "demon": demon, "melee": melee}


@pytest.mark.parametrize("attacker_spell,defender_spell", list(itertools.product(CHALLENGE_SPELLS, repeat=2)))
def test_two_summons_in_any_combination_dissolve_each_other_in_a_challenge(attacker_spell, defender_spell):
    state = _two_mages([_cast(defender_spell)])

    result, calls = _challenge(state, [_cast(attacker_spell)])

    assert not calls["mirror"].called and not calls["hero"].called and not calls["demon"].called
    assert result.combat_occurred
    assert len(state.summon_nullifications) == 1
    first_name, first_spell, second_name, second_spell, kingdoms = state.summon_nullifications[0]
    assert {first_spell, second_spell} == {attacker_spell, defender_spell}
    assert {first_name, second_name} == {"Attacker", "Defender"}
    assert set(kingdoms) == {1, 2}


def test_the_encounter_goes_on_with_the_next_tactic_after_the_summons_dissolve():
    state = _two_mages([_cast(Spell.MIRROR_IMAGE)])

    result, calls = _challenge(state, [_cast(Spell.GATE_DEMON), SearchTactic(Maneuver.MELEE)])

    assert calls["melee"].called
    assert not calls["demon"].called
    assert result.winner_leader_id == 1  # the plain Melee that follows decided it


def test_a_lone_summon_still_takes_effect():
    state = _two_mages([SearchTactic(Maneuver.MELEE)])

    result, calls = _challenge(state, [_cast(Spell.MIRROR_IMAGE)], rolls=(True,))
    del result

    assert calls["mirror"].called
    assert state.summon_nullifications == []


def test_a_summon_that_fizzles_does_not_dissolve_the_other():
    state = _two_mages([_cast(Spell.MIRROR_IMAGE)])
    # The defender has the higher talent in his magic, so his spell goes first in the round ([5.0]).
    for ability in (Ability.ILLUSION, Ability.NECROMANCY, Ability.WHITE):
        state.leaders[2].skills.set_pair_for_ability(ability, 7, 9)

    # The defender's Mirror Image fizzles (first roll), the attacker's Gate Demon takes effect.
    result, calls = _challenge(state, [_cast(Spell.GATE_DEMON)], rolls=(False, True))
    del result

    assert state.summon_nullifications == []
    assert calls["demon"].called


def test_a_non_summoning_spell_does_not_dissolve_a_summon():
    state = _two_mages([_cast(Spell.INVISIBILITY)])

    _result, calls = _challenge(state, [_cast(Spell.MIRROR_IMAGE)], rolls=(True, True))

    assert state.summon_nullifications == []
    assert calls["mirror"].called


# -- Search: a guardian that summons too --


def _search_state() -> GameState:
    state = GameState()
    state.add_leader(LeaderState(1, 1, "Searcher", FIELD, skills=_mage_skills(), alignment=Alignment.GOOD))
    state.add_feature(Feature(feature_id=1, coord=FIELD, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    return state


def _search(state: GameState, leader_plan, monster_plan, *, rolls):
    request = SearchRequest(feature_id=1, unconfirmed_extra0=0, tactics=list(leader_plan))
    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", side_effect=list(rolls)), patch(
        "ak_engine.turn.search_execution.roll_monster_encounter_plan", return_value=tuple(monster_plan)
    ), patch("ak_engine.turn.search_execution.resolve_mirror_image_duel") as mirror, patch(
        "ak_engine.turn.search_execution.resolve_illusory_hero_duel"
    ) as hero, patch("ak_engine.turn.search_execution.roll_gate_demon_type") as demon, patch(
        "ak_engine.turn.search_execution.roll_monster_alignment", return_value=Alignment.GOOD
    ), patch("ak_engine.turn.search_execution.resolve_melee_duel") as melee:
        melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        mirror.return_value = EncounterCombatResult(winner="a", rounds=1)
        hero.return_value = EncounterCombatResult(winner="a", rounds=1)
        result = execute_search(state, 1, request, random.Random(0))
    return result, {"mirror": mirror, "hero": hero, "demon": demon, "melee": melee}


@pytest.mark.parametrize("leader_spell", [Spell.MIRROR_IMAGE, Spell.GATE_DEMON, Spell.GATE_ANGEL, Spell.ILLUS_HERO])
def test_the_leaders_summon_and_the_guardians_mirror_image_dissolve_each_other(leader_spell):
    state = _search_state()

    _result, calls = _search(
        state, [_cast(leader_spell), SearchTactic(Maneuver.MELEE)], [_cast(Spell.MIRROR_IMAGE), SearchTactic(Maneuver.MELEE)],
        rolls=(True, True),
    )

    assert not calls["mirror"].called and not calls["hero"].called and not calls["demon"].called
    assert len(state.summon_nullifications) == 1
    first_name, first_spell, second_name, second_spell, kingdoms = state.summon_nullifications[0]
    assert (first_name, first_spell) == ("Searcher", leader_spell)
    assert second_spell is Spell.MIRROR_IMAGE
    assert kingdoms == (1,)  # the guardian has no Kingdom
    assert calls["melee"].called  # both plans go on to the Melee


def test_a_guardians_mirror_image_with_no_summon_from_the_leader_takes_effect():
    state = _search_state()

    _result, calls = _search(
        state, [SearchTactic(Maneuver.MELEE)], [_cast(Spell.MIRROR_IMAGE), SearchTactic(Maneuver.MELEE)], rolls=(True,)
    )

    assert state.summon_nullifications == []
    assert calls["mirror"].called


def test_the_guardians_summon_dissolves_the_leaders_next_queued_one():
    # The leader's Melee goes first; the guardian's Mirror Image then meets the leader's
    # *next* queued tactic, the Gate Demon, and both dissolve.
    state = _search_state()

    _result, calls = _search(
        state,
        [SearchTactic(Maneuver.MELEE), _cast(Spell.GATE_DEMON)],
        [_cast(Spell.MIRROR_IMAGE), SearchTactic(Maneuver.MELEE)],
        rolls=(True, True),
    )

    assert len(state.summon_nullifications) == 1
    assert not calls["mirror"].called and not calls["demon"].called


# -- the report --


def test_the_report_tells_each_kingdom_involved():
    state = GameState()
    state.summon_nullifications.append(("Attacker", Spell.GATE_DEMON, "Defender", Spell.MIRROR_IMAGE, (1, 2)))

    assert describe_summon_nullifications(state, 1) == [
        "Attacker's Gate Demon spell and Defender's Mirror-Image Phantasm spell met, and both dissolved."
    ]
    assert describe_summon_nullifications(state, 2) == describe_summon_nullifications(state, 1)
    assert describe_summon_nullifications(state, 3) == []
