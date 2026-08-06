from __future__ import annotations

import random
from unittest.mock import patch

import pytest

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.enums import Ability, Maneuver, Spell
from ak_engine.models.game_state import ArmyState, GameState, KingdomState, LeaderState
from ak_engine.models.kingdom import SkillTable
from ak_engine.models.map import HexCoord
from ak_engine.models.monster import Monster
from ak_engine.models.race import Race
from ak_engine.models.temper import Temper
from ak_engine.models.treasure import Treasure
from ak_engine.turn.challenge_execution import (
    ChallengeExecutionResult,
    _apply_successful_theft,
    _close_to,
    _leader_combatant,
    _resolve_personal_combat_cast,
    _resolve_steal_tactic,
    execute_challenge,
    has_combat_intent,
    is_encounter_accepted,
    resolve_challenge_combat,
)
from ak_engine.turn.challenge_pursue_decode import ChallengeRequest
from ak_engine.turn.combat import Quality
from ak_engine.turn.encounter import (
    CHARACTER_HIT_POINTS,
    CombatRange,
    EncounterCombatResult,
    MeleeRoundOutcome,
    ReactiveMeleeSwingResult,
)
from ak_engine.turn.search_decode import SearchTactic

from _helpers import ScriptedRandom

FIELD = HexCoord(1, 1)
ELSEWHERE = HexCoord(9, 9)


def _skills_with(ability: Ability, skill: int, aptitude: int) -> SkillTable:
    raw = [0] * 30
    raw[ability.value * 2] = skill
    raw[ability.value * 2 + 1] = aptitude
    return SkillTable(raw)


def _peaceful_request(target_id: int) -> ChallengeRequest:
    return ChallengeRequest(target_character_id=target_id, unconfirmed_extra0=0, tactics=[SearchTactic(Maneuver.TALK)])


def _melee_request(target_id: int) -> ChallengeRequest:
    return ChallengeRequest(target_character_id=target_id, unconfirmed_extra0=0, tactics=[SearchTactic(Maneuver.MELEE)])


def _cast_request(target_id: int, spell: Spell, *following: Maneuver) -> ChallengeRequest:
    tactics = [SearchTactic(Maneuver.CAST, spell.value)]
    tactics += [SearchTactic(m) for m in following]
    return ChallengeRequest(target_character_id=target_id, unconfirmed_extra0=0, tactics=tactics)


# -- has_combat_intent --------------------------------------------------


def test_has_combat_intent_true_for_melee():
    request = ChallengeRequest(target_character_id=2, unconfirmed_extra0=0, tactics=[SearchTactic(Maneuver.MELEE)])
    assert has_combat_intent(request) is True


def test_has_combat_intent_true_for_fire_arrow():
    request = ChallengeRequest(target_character_id=2, unconfirmed_extra0=0, tactics=[SearchTactic(Maneuver.SHOOT)])
    assert has_combat_intent(request) is True


def test_has_combat_intent_false_for_peaceful_tactics():
    request = ChallengeRequest(
        target_character_id=2, unconfirmed_extra0=0, tactics=[SearchTactic(Maneuver.TALK), SearchTactic(Maneuver.STEAL)]
    )
    assert has_combat_intent(request) is False


def test_has_combat_intent_false_for_no_tactics_at_all():
    request = ChallengeRequest(target_character_id=2, unconfirmed_extra0=0, tactics=[])
    assert has_combat_intent(request) is False


def test_has_combat_intent_true_for_a_decodable_cast_tactic():
    # Phase 290: [3.12]'s own text names "personal combat spells
    # (including Charm)" alongside combat tactics -- a CAST entry is
    # combat intent too, not just Melee/Fire Arrow.
    request = ChallengeRequest(
        target_character_id=2, unconfirmed_extra0=0, tactics=[SearchTactic(Maneuver.CAST, Spell.CHARM.value)]
    )
    assert has_combat_intent(request) is True


def test_has_combat_intent_false_for_cast_with_an_undecodable_spell_id():
    request = ChallengeRequest(target_character_id=2, unconfirmed_extra0=0, tactics=[SearchTactic(Maneuver.CAST, 9999)])
    assert has_combat_intent(request) is False


# -- is_encounter_accepted: rulebook [3.12]'s King/Hero decision tree ---


def test_king_target_accepts_only_when_mutual():
    accepted = is_encounter_accepted(
        target_is_king=True, target_leads_army=False, challenger_is_king=False, mutual_encounter=True, rng=ScriptedRandom([])
    )
    assert accepted is True


def test_king_target_refuses_when_not_mutual():
    accepted = is_encounter_accepted(
        target_is_king=True, target_leads_army=False, challenger_is_king=False, mutual_encounter=False, rng=ScriptedRandom([])
    )
    assert accepted is False


def test_hero_leading_an_army_always_refuses():
    accepted = is_encounter_accepted(
        target_is_king=False, target_leads_army=True, challenger_is_king=True, mutual_encounter=True, rng=ScriptedRandom([])
    )
    assert accepted is False


def test_armyless_hero_vs_king_challenger_is_a_50_50_roll():
    accepted_low = is_encounter_accepted(
        target_is_king=False, target_leads_army=False, challenger_is_king=True, mutual_encounter=False,
        rng=ScriptedRandom([0.49]),
    )
    accepted_high = is_encounter_accepted(
        target_is_king=False, target_leads_army=False, challenger_is_king=True, mutual_encounter=False,
        rng=ScriptedRandom([0.5]),
    )
    assert accepted_low is True
    assert accepted_high is False


def test_armyless_hero_vs_hero_challenger_always_accepts_without_consuming_rng():
    accepted = is_encounter_accepted(
        target_is_king=False, target_leads_army=False, challenger_is_king=False, mutual_encounter=False,
        rng=ScriptedRandom([]),  # any .random() call here would raise IndexError
    )
    assert accepted is True


def test_leader_combatant_reads_real_temper():
    # Phase 284: the Temper Table's own melee mechanics need each
    # combatant's real Temper threaded through.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Braveland", Race.HUMAN, Alignment.GOOD, FIELD))
    leader = LeaderState(501, kingdom_id=1, name="Hero", location=FIELD, temper=Temper.CAUTIOUS)
    state.add_leader(leader)

    combatant = _leader_combatant(leader, state)

    assert combatant.temper is Temper.CAUTIOUS


# -- execute_challenge: co-location, not-found, peaceful bypass ---------


def _base_state() -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, FIELD))
    state.add_kingdom(KingdomState(2, "Defendia", Race.HUMAN, Alignment.GOOD, FIELD))
    return state


def test_execute_challenge_reports_not_found_when_challenger_missing():
    state = _base_state()
    state.add_leader(LeaderState(2, kingdom_id=2, name="Target", location=FIELD))

    result = execute_challenge(state, 1, _peaceful_request(2))

    assert result.accepted is False
    assert result.reason == "challenger or target not found"


def test_execute_challenge_reports_not_found_when_target_missing():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Challenger", location=FIELD))

    result = execute_challenge(state, 1, _peaceful_request(2))

    assert result.accepted is False
    assert result.reason == "challenger or target not found"


def test_execute_challenge_refuses_when_not_co_located():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Challenger", location=FIELD))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Target", location=ELSEWHERE))

    result = execute_challenge(state, 1, _peaceful_request(2))

    assert result.accepted is False
    assert result.reason == "not co-located"


def test_execute_challenge_peaceful_plan_bypasses_acceptance_and_combat():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Challenger", location=FIELD, is_king=True))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Target", location=FIELD, is_king=True))

    result = execute_challenge(state, 1, _peaceful_request(2), rng=ScriptedRandom([]))

    assert result == ChallengeExecutionResult(accepted=True, combat_occurred=False)
    assert 1 in state.leaders and 2 in state.leaders


def test_execute_challenge_king_target_refused_when_not_mutual_and_no_combat_happens():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Challenger", location=FIELD))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Target", location=FIELD, is_king=True))

    result = execute_challenge(state, 1, _melee_request(2), rng=ScriptedRandom([]))

    assert result.accepted is False
    assert result.reason == "encounter refused"
    assert 1 in state.leaders and 2 in state.leaders


def test_execute_challenge_hero_with_army_target_refused():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Challenger", location=FIELD, is_king=True))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Target", location=FIELD))
    state.add_army(ArmyState(201, 2, ArmyType.GARRISON, Quality.GREEN, FIELD, commanded_by=2))

    result = execute_challenge(state, 1, _melee_request(2), rng=ScriptedRandom([]))

    assert result.accepted is False
    assert result.reason == "encounter refused"


# -- execute_challenge: combat resolution + loser removal ---------------


def test_execute_challenge_combat_removes_the_decisive_loser():
    state = _base_state()
    state.add_leader(
        LeaderState(1, kingdom_id=1, name="A", location=FIELD, skills=_skills_with(Ability.MELEE, 3, 9))
    )
    state.add_leader(
        LeaderState(2, kingdom_id=2, name="B", location=FIELD, skills=_skills_with(Ability.MELEE, 0, 9))
    )
    # A always acts first (higher melee skill, no initiative roll needed);
    # scripted so A always hits and B always misses.
    rng = ScriptedRandom([0.1, 0.5, 0.9] * 15)

    result = execute_challenge(state, 1, _melee_request(2), rng=rng)

    assert result.accepted is True
    assert result.combat_occurred is True
    assert result.winner_leader_id == 1
    assert result.loser_leader_id == 2
    assert result.loser_killed is True
    assert 2 not in state.leaders
    assert 1 in state.leaders


def test_execute_challenge_combat_loots_the_decisive_losers_items():
    # Phase 313, rulebook [5.9]: "looting a vanquished foe's treasure,
    # magic items changing hands" -- same setup as the removal test above.
    state = _base_state()
    state.add_leader(
        LeaderState(1, kingdom_id=1, name="A", location=FIELD, skills=_skills_with(Ability.MELEE, 3, 9))
    )
    state.add_leader(
        LeaderState(2, kingdom_id=2, name="B", location=FIELD, skills=_skills_with(Ability.MELEE, 0, 9))
    )
    item = state.add_item(Treasure.ABILITY_MELEE, owner_leader_id=2)
    rng = ScriptedRandom([0.1, 0.5, 0.9] * 15)

    result = execute_challenge(state, 1, _melee_request(2), rng=rng)

    assert result.loser_killed is True
    assert result.looted_item_ids == [item.item_id]
    assert state.items[item.item_id].owner_leader_id == 1


def test_execute_challenge_combat_with_no_decisive_winner_kills_nobody():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="A", location=FIELD))
    state.add_leader(LeaderState(2, kingdom_id=2, name="B", location=FIELD))
    # execute_challenge doesn't expose resolve_melee_duel's max_rounds, so
    # this exercises the real default (1000) all the way to its cap: both
    # combatants have equal (zero) melee skill, so every round's initiative
    # tie-break plus both always-miss attack rolls consumes 3 scripted
    # values -- 1000 rounds * 3.
    rng = ScriptedRandom([0.99] * 3000)

    result = execute_challenge(state, 1, _melee_request(2), rng=rng)

    assert result.accepted is True
    assert result.combat_occurred is True
    assert result.winner_leader_id is None
    assert result.loser_killed is False
    assert 1 in state.leaders and 2 in state.leaders


# -- Fire Arrow (Phase 273): SHOOT now actually resolves via Fire Arrow --


def test_execute_challenge_shoot_tactic_resolves_via_fire_arrow_before_melee():
    state = _base_state()
    # A has real Archery skill (10 free attacks, guaranteed hit chance since
    # 0.30 + 0.10*10 > 1.0) and no Melee skill at all. B has real Melee
    # skill (9) but no Archery -- if this still fell straight to Melee (the
    # pre-Phase-273 bug), B's own higher skill would act first and A
    # wouldn't reliably win. A's 10 guaranteed archery hits (minimum 1
    # damage each) always total at least 10, guaranteeing B's death within
    # Fire Arrow alone, regardless of the exact (unscripted) damage rolled
    # per hit.
    state.add_leader(
        LeaderState(1, kingdom_id=1, name="A", location=FIELD, skills=_skills_with(Ability.ARCHERY, 10, 9))
    )
    state.add_leader(
        LeaderState(2, kingdom_id=2, name="B", location=FIELD, skills=_skills_with(Ability.MELEE, 9, 9))
    )
    rng = ScriptedRandom([0.01] * 25)
    shoot_request = ChallengeRequest(target_character_id=2, unconfirmed_extra0=0, tactics=[SearchTactic(Maneuver.SHOOT)])

    result = execute_challenge(state, 1, shoot_request, rng=rng)

    assert result.combat_occurred is True
    assert result.winner_leader_id == 1
    assert result.loser_leader_id == 2
    assert result.loser_killed is True


def test_execute_challenge_mutual_king_encounter_can_result_in_combat():
    state = _base_state()
    state.add_leader(
        LeaderState(1, kingdom_id=1, name="A", location=FIELD, is_king=True, skills=_skills_with(Ability.MELEE, 3, 9))
    )
    state.add_leader(
        LeaderState(2, kingdom_id=2, name="B", location=FIELD, is_king=True, skills=_skills_with(Ability.MELEE, 0, 9))
    )
    rng = ScriptedRandom([0.1, 0.5, 0.9] * 15)

    result = execute_challenge(state, 1, _melee_request(2), rng=rng, mutual_encounter=True)

    assert result.accepted is True
    assert result.winner_leader_id == 1
    # Phase 259: a King's death installs a Royal Heir under the same
    # leader_id rather than leaving the Kingdom leaderless.
    assert 2 in state.dead_leaders
    assert state.leaders[2].is_royal_heir is True


# -- Phase 290: Personal-Combat spells wired via resolve_challenge_combat --


def test_execute_challenge_cast_charm_success_makes_the_caster_flee():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="A", location=FIELD, skills=_skills_with(Ability.PSYCHIC, 5, 9)))
    state.add_leader(LeaderState(2, kingdom_id=2, name="B", location=FIELD))
    request = _cast_request(2, Spell.CHARM, Maneuver.MELEE)

    result = execute_challenge(state, 1, request, rng=ScriptedRandom([0.1]))

    assert result.accepted is True
    assert result.combat_occurred is True
    assert result.fled is True
    assert result.winner_leader_id is None
    assert 1 in state.leaders and 2 in state.leaders


def test_execute_challenge_cast_control_undead_success_kills_undead_target():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="A", location=FIELD, skills=_skills_with(Ability.NECROMANCY, 5, 9)))
    state.add_leader(LeaderState(2, kingdom_id=2, name="B", location=FIELD, alignment=Alignment.UNDEAD))
    request = _cast_request(2, Spell.CONTROL_UNDEAD)

    result = execute_challenge(state, 1, request, rng=ScriptedRandom([0.1]))

    assert result.winner_leader_id == 1
    assert result.loser_leader_id == 2
    assert result.loser_killed is True


def test_execute_challenge_cast_control_undead_ineligible_target_consumes_no_roll():
    # Target isn't Undead -- the same leader-only "else" branch `turn/
    # search_execution.py` already uses, re-derived here.
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="A", location=FIELD))
    state.add_leader(LeaderState(2, kingdom_id=2, name="B", location=FIELD, alignment=Alignment.GOOD))
    request = _cast_request(2, Spell.CONTROL_UNDEAD, Maneuver.MELEE)

    with patch("ak_engine.turn.challenge_execution.resolve_personal_combat_spell_cast") as mock_roll, patch(
        "ak_engine.turn.challenge_execution.resolve_melee_duel"
    ) as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        result = execute_challenge(state, 1, request, rng=ScriptedRandom([]))

    assert not mock_roll.called
    assert mock_melee.called
    assert result.winner_leader_id == 1


def test_execute_challenge_cast_fireball_kills_via_damage():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="A", location=FIELD, skills=_skills_with(Ability.ELEMENTAL, 4, 9)))
    state.add_leader(LeaderState(2, kingdom_id=2, name="B", location=FIELD))
    request = _cast_request(2, Spell.FIREBALL)

    with patch("ak_engine.turn.challenge_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.challenge_execution.roll_fireball_damage", return_value=99
    ):
        result = execute_challenge(state, 1, request, rng=ScriptedRandom([]))

    assert result.winner_leader_id == 1
    assert result.loser_leader_id == 2
    assert result.loser_killed is True


def test_execute_challenge_cast_words_of_healing_heals_the_caster():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="A", location=FIELD, skills=_skills_with(Ability.WHITE, 5, 9)))
    state.add_leader(LeaderState(2, kingdom_id=2, name="B", location=FIELD, skills=_skills_with(Ability.MELEE, 9, 9)))
    request = _cast_request(2, Spell.HEAL, Maneuver.MELEE)

    with patch("ak_engine.turn.challenge_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.challenge_execution.resolve_melee_duel"
    ) as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_challenge(state, 1, request, rng=ScriptedRandom([]))

    caster_combatant = mock_melee.call_args[0][0]
    assert caster_combatant.hit_points == CHARACTER_HIT_POINTS


def test_execute_challenge_cast_words_of_healing_level_gate_blocks_low_white_skill():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="A", location=FIELD, skills=_skills_with(Ability.WHITE, 4, 9)))
    state.add_leader(LeaderState(2, kingdom_id=2, name="B", location=FIELD, skills=_skills_with(Ability.MELEE, 9, 9)))
    request = _cast_request(2, Spell.HEAL, Maneuver.MELEE)

    with patch("ak_engine.turn.challenge_execution.resolve_personal_combat_spell_cast") as mock_roll, patch(
        "ak_engine.turn.challenge_execution.resolve_melee_duel"
    ) as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_challenge(state, 1, request, rng=ScriptedRandom([]))

    assert not mock_roll.called
    assert mock_melee.called


def test_execute_challenge_cast_hand_of_death_channel_win_kills_target():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="A", location=FIELD, skills=_skills_with(Ability.NECROMANCY, 4, 9)))
    state.add_leader(LeaderState(2, kingdom_id=2, name="B", location=FIELD))
    request = _cast_request(2, Spell.HAND_OF_DEATH)

    with patch("ak_engine.turn.challenge_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.challenge_execution.resolve_hand_of_death_channel"
    ) as mock_channel:
        mock_channel.return_value = EncounterCombatResult(winner="a", rounds=3)
        result = execute_challenge(state, 1, request, rng=ScriptedRandom([]))

    assert result.winner_leader_id == 1
    assert result.loser_leader_id == 2


def test_execute_challenge_cast_mirror_image_caster_wins():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="A", location=FIELD, skills=_skills_with(Ability.ILLUSION, 4, 9)))
    state.add_leader(LeaderState(2, kingdom_id=2, name="B", location=FIELD))
    request = _cast_request(2, Spell.MIRROR_IMAGE)

    with patch("ak_engine.turn.challenge_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.challenge_execution.resolve_mirror_image_duel"
    ) as mock_duel:
        mock_duel.return_value = EncounterCombatResult(winner="a", rounds=2)
        result = execute_challenge(state, 1, request, rng=ScriptedRandom([]))

    assert result.winner_leader_id == 1


def test_execute_challenge_cast_gate_demon_summons_and_the_demon_wins():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="A", location=FIELD, skills=_skills_with(Ability.NECROMANCY, 4, 9)))
    state.add_leader(LeaderState(2, kingdom_id=2, name="B", location=FIELD, alignment=Alignment.GOOD))
    request = _cast_request(2, Spell.GATE_DEMON)

    with patch("ak_engine.turn.challenge_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.challenge_execution.roll_gate_demon_type", return_value=Monster.SUCCUBUS
    ), patch("ak_engine.turn.challenge_execution.resolve_melee_duel") as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        result = execute_challenge(state, 1, request, rng=ScriptedRandom([0.5]))

    assert result.winner_leader_id == 1
    demon_combatant = mock_melee.call_args[0][0]
    assert demon_combatant.name  # a real, named monster Combatant was summoned


def test_execute_challenge_cast_psychic_blast_bonus_attacks_can_finish_the_target():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="A", location=FIELD, skills=_skills_with(Ability.PSYCHIC, 4, 9)))
    state.add_leader(LeaderState(2, kingdom_id=2, name="B", location=FIELD))
    request = _cast_request(2, Spell.PSYCHIC_BLAST)

    with patch("ak_engine.turn.challenge_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.challenge_execution.roll_psychic_blast_stun_rounds", return_value=2
    ), patch("ak_engine.turn.challenge_execution.roll_melee_attack", return_value=99):
        result = execute_challenge(state, 1, request, rng=ScriptedRandom([]))

    assert result.winner_leader_id == 1
    assert result.loser_leader_id == 2


def test_augur_combat_cast_first_shirks_and_flees_on_a_simulated_loss():
    state = _base_state()
    caster_leader = LeaderState(
        1, kingdom_id=1, name="A", location=FIELD, skills=_skills_with(Ability.PSYCHIC, 4, 9), temper=Temper.COWARDLY
    )
    target_leader = LeaderState(2, kingdom_id=2, name="B", location=FIELD)
    state.add_leader(caster_leader)
    state.add_leader(target_leader)
    caster = _leader_combatant(caster_leader, state)
    target = _leader_combatant(target_leader, state)
    tactic = SearchTactic(Maneuver.CAST, Spell.AUGUR_COMBAT.value)

    with patch("ak_engine.turn.challenge_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.challenge_execution.resolve_melee_duel"
    ) as mock_melee, patch("ak_engine.turn.challenge_execution.resolve_augur_combat", return_value=True):
        mock_melee.return_value = EncounterCombatResult(winner="b", rounds=1)
        outcome = _resolve_personal_combat_cast(
            caster, caster_leader, target, target_leader, tactic, state, ScriptedRandom([]), is_first_tactic=True
        )

    assert outcome == "fled"


def test_augur_combat_cast_later_is_a_documented_gap_with_no_effect_yet():
    # Module docstring's own Phase 290 addendum: unlike Search, this
    # module has no real Flee tactic/base-chance table to act as yet --
    # confirmed as a genuine, still-open gap rather than a guess.
    state = _base_state()
    caster_leader = LeaderState(
        1, kingdom_id=1, name="A", location=FIELD, skills=_skills_with(Ability.PSYCHIC, 4, 9), temper=Temper.COWARDLY
    )
    target_leader = LeaderState(2, kingdom_id=2, name="B", location=FIELD)
    state.add_leader(caster_leader)
    state.add_leader(target_leader)
    caster = _leader_combatant(caster_leader, state)
    target = _leader_combatant(target_leader, state)
    tactic = SearchTactic(Maneuver.CAST, Spell.AUGUR_COMBAT.value)

    with patch("ak_engine.turn.challenge_execution.resolve_personal_combat_spell_cast") as mock_roll:
        outcome = _resolve_personal_combat_cast(
            caster, caster_leader, target, target_leader, tactic, state, ScriptedRandom([]), is_first_tactic=False
        )

    assert outcome is None
    assert not mock_roll.called


# -- Phase 292: the round-based range engine + real spell disruption ----


def _combatants(**overrides):
    state = _base_state()
    caster_leader = LeaderState(1, kingdom_id=1, name="A", location=FIELD, **overrides.pop("caster_kwargs", {}))
    target_leader = LeaderState(2, kingdom_id=2, name="B", location=FIELD, **overrides.pop("target_kwargs", {}))
    state.add_leader(caster_leader)
    state.add_leader(target_leader)
    caster = _leader_combatant(caster_leader, state)
    target = _leader_combatant(target_leader, state)
    return state, caster_leader, caster, target_leader, target


def test_close_to_advances_one_tier_at_a_time_and_never_widens():
    assert _close_to(CombatRange.BOW_RANGE, CombatRange.SPELL_RANGE) is CombatRange.BOW_RANGE
    assert _close_to(CombatRange.MELEE_RANGE, CombatRange.SPELL_RANGE) is CombatRange.MELEE_RANGE
    assert _close_to(CombatRange.MELEE_RANGE, CombatRange.BOW_RANGE) is CombatRange.MELEE_RANGE
    assert _close_to(CombatRange.MELEE_RANGE, CombatRange.MELEE_RANGE) is CombatRange.MELEE_RANGE
    assert _close_to(CombatRange.SPELL_RANGE, CombatRange.MELEE_RANGE) is CombatRange.MELEE_RANGE  # never widens


def test_resolve_challenge_combat_last_melee_tactic_fights_atomically():
    # Every real caller and pre-Phase-292 test orders MELEE last -- that
    # exact shape must still resolve via the full atomic resolve_melee_
    # duel(), not the new one-round primitive.
    state, caster_leader, caster, target_leader, target = _combatants()
    tactics = [SearchTactic(Maneuver.MELEE)]

    with patch("ak_engine.turn.challenge_execution.resolve_melee_duel") as mock_duel, patch(
        "ak_engine.turn.challenge_execution.resolve_one_melee_round"
    ) as mock_round:
        mock_duel.return_value = EncounterCombatResult(winner="a", rounds=1)
        outcome = resolve_challenge_combat(
            tactics, caster_leader, caster, target_leader, target, state, ScriptedRandom([])
        )

    assert mock_duel.called
    assert not mock_round.called
    assert outcome.winner == "a"


def test_resolve_challenge_combat_non_last_melee_tactic_steps_one_round_then_falls_through():
    # A MELEE tactic followed by more tactics is the new plan shape --
    # only one round is fought, and (undecided) the walk continues,
    # eventually reaching the same exhausted-list atomic fallback.
    state, caster_leader, caster, target_leader, target = _combatants()
    tactics = [SearchTactic(Maneuver.MELEE), SearchTactic(Maneuver.TALK)]

    with patch("ak_engine.turn.challenge_execution.resolve_one_melee_round") as mock_round, patch(
        "ak_engine.turn.challenge_execution.resolve_melee_duel"
    ) as mock_duel:
        mock_round.return_value = MeleeRoundOutcome(result=None)
        mock_duel.return_value = EncounterCombatResult(winner="b", rounds=1)
        outcome = resolve_challenge_combat(
            tactics, caster_leader, caster, target_leader, target, state, ScriptedRandom([])
        )

    assert mock_round.called
    assert mock_duel.called  # the exhausted-list fallback still ran afterward
    assert outcome.winner == "b"


def test_resolve_challenge_combat_non_last_melee_tactic_ends_combat_on_a_decisive_round():
    state, caster_leader, caster, target_leader, target = _combatants()
    tactics = [SearchTactic(Maneuver.MELEE), SearchTactic(Maneuver.TALK)]

    with patch("ak_engine.turn.challenge_execution.resolve_one_melee_round") as mock_round, patch(
        "ak_engine.turn.challenge_execution.resolve_melee_duel"
    ) as mock_duel:
        mock_round.return_value = MeleeRoundOutcome(result=EncounterCombatResult(winner="a", rounds=1))
        outcome = resolve_challenge_combat(
            tactics, caster_leader, caster, target_leader, target, state, ScriptedRandom([])
        )

    assert outcome.winner == "a"
    assert not mock_duel.called  # a decisive round ends the encounter outright


def test_resolve_challenge_combat_shoot_ignored_once_at_melee_range():
    # [5.0]: "In the melee zone, only spells or hand-to-hand attacks" --
    # a SHOOT tactic ordered after range has already closed to MELEE_
    # RANGE is a pure no-op, never reaching resolve_fire_arrow_duel.
    state, caster_leader, caster, target_leader, target = _combatants()
    tactics = [SearchTactic(Maneuver.MELEE), SearchTactic(Maneuver.SHOOT)]

    with patch("ak_engine.turn.challenge_execution.resolve_one_melee_round") as mock_round, patch(
        "ak_engine.turn.challenge_execution.resolve_fire_arrow_duel"
    ) as mock_shoot, patch("ak_engine.turn.challenge_execution.resolve_melee_duel") as mock_duel:
        mock_round.return_value = MeleeRoundOutcome(result=None)
        mock_duel.return_value = EncounterCombatResult(winner=None, rounds=1)
        resolve_challenge_combat(tactics, caster_leader, caster, target_leader, target, state, ScriptedRandom([]))

    assert not mock_shoot.called
    assert mock_duel.called  # falls through to the atomic fallback afterward


def test_resolve_challenge_combat_cast_at_melee_range_disrupted_by_a_landed_hit_never_attempts_the_cast():
    state, caster_leader, caster, target_leader, target = _combatants(
        caster_kwargs={"skills": _skills_with(Ability.WHITE, 5, 9)}
    )
    tactics = [SearchTactic(Maneuver.MELEE), SearchTactic(Maneuver.CAST, Spell.HEAL.value)]

    with patch("ak_engine.turn.challenge_execution.resolve_one_melee_round") as mock_round, patch(
        "ak_engine.turn.challenge_execution.resolve_reactive_melee_swing",
        return_value=ReactiveMeleeSwingResult(hit=True, damage=5),
    ) as mock_swing, patch("ak_engine.turn.challenge_execution.resolve_spell_disruption", return_value=True) as mock_disrupt, patch(
        "ak_engine.turn.challenge_execution.resolve_spell_disruption_from_missed_attack"
    ) as mock_miss_disrupt, patch(
        "ak_engine.turn.challenge_execution.resolve_personal_combat_spell_cast"
    ) as mock_cast, patch(
        "ak_engine.turn.challenge_execution.resolve_melee_duel"
    ) as mock_duel:
        mock_round.return_value = MeleeRoundOutcome(result=None)
        mock_duel.return_value = EncounterCombatResult(winner=None, rounds=1)
        resolve_challenge_combat(tactics, caster_leader, caster, target_leader, target, state, ScriptedRandom([]))

    assert mock_swing.called
    assert mock_disrupt.called
    assert not mock_miss_disrupt.called  # a landed hit uses the damage-scaled formula, not the flat-miss one
    assert not mock_cast.called  # disrupted -- "the caster loses a turn," no cast-chance roll at all


def test_resolve_challenge_combat_cast_at_melee_range_disrupted_by_a_missed_swing():
    state, caster_leader, caster, target_leader, target = _combatants(
        caster_kwargs={"skills": _skills_with(Ability.WHITE, 5, 9)}
    )
    tactics = [SearchTactic(Maneuver.MELEE), SearchTactic(Maneuver.CAST, Spell.HEAL.value)]

    with patch("ak_engine.turn.challenge_execution.resolve_one_melee_round") as mock_round, patch(
        "ak_engine.turn.challenge_execution.resolve_reactive_melee_swing",
        return_value=ReactiveMeleeSwingResult(hit=False, damage=0),
    ), patch("ak_engine.turn.challenge_execution.resolve_spell_disruption") as mock_damage_disrupt, patch(
        "ak_engine.turn.challenge_execution.resolve_spell_disruption_from_missed_attack", return_value=True
    ) as mock_miss_disrupt, patch(
        "ak_engine.turn.challenge_execution.resolve_personal_combat_spell_cast"
    ) as mock_cast, patch(
        "ak_engine.turn.challenge_execution.resolve_melee_duel"
    ) as mock_duel:
        mock_round.return_value = MeleeRoundOutcome(result=None)
        mock_duel.return_value = EncounterCombatResult(winner=None, rounds=1)
        resolve_challenge_combat(tactics, caster_leader, caster, target_leader, target, state, ScriptedRandom([]))

    assert mock_miss_disrupt.called
    assert not mock_damage_disrupt.called  # a miss uses the flat 30%, not the damage-scaled formula
    assert not mock_cast.called


def test_resolve_challenge_combat_cast_at_melee_range_not_disrupted_still_attempts_the_cast():
    state, caster_leader, caster, target_leader, target = _combatants(
        caster_kwargs={"skills": _skills_with(Ability.WHITE, 5, 9)}
    )
    tactics = [SearchTactic(Maneuver.MELEE), SearchTactic(Maneuver.CAST, Spell.HEAL.value)]

    with patch("ak_engine.turn.challenge_execution.resolve_one_melee_round") as mock_round, patch(
        "ak_engine.turn.challenge_execution.resolve_reactive_melee_swing",
        return_value=ReactiveMeleeSwingResult(hit=True, damage=2),
    ), patch("ak_engine.turn.challenge_execution.resolve_spell_disruption", return_value=False), patch(
        "ak_engine.turn.challenge_execution.resolve_personal_combat_spell_cast", return_value=True
    ) as mock_cast, patch("ak_engine.turn.challenge_execution.words_of_healing_heal") as mock_heal, patch(
        "ak_engine.turn.challenge_execution.resolve_melee_duel"
    ) as mock_duel:
        mock_round.return_value = MeleeRoundOutcome(result=None)
        mock_duel.return_value = EncounterCombatResult(winner=None, rounds=1)
        resolve_challenge_combat(tactics, caster_leader, caster, target_leader, target, state, ScriptedRandom([]))

    assert mock_cast.called  # not disrupted -- the cast-chance roll still happens
    assert mock_heal.called  # ... and, having succeeded, the spell's own effect still lands


def test_resolve_challenge_combat_reactive_swing_killing_the_caster_ends_combat_immediately():
    state, caster_leader, caster, target_leader, target = _combatants(
        caster_kwargs={"skills": _skills_with(Ability.WHITE, 5, 9)}
    )
    caster.hit_points = 1
    tactics = [SearchTactic(Maneuver.MELEE), SearchTactic(Maneuver.CAST, Spell.HEAL.value)]

    def _lethal_swing(attacker, defender, rng):
        defender.hit_points -= 5
        return ReactiveMeleeSwingResult(hit=True, damage=5)

    with patch("ak_engine.turn.challenge_execution.resolve_one_melee_round") as mock_round, patch(
        "ak_engine.turn.challenge_execution.resolve_reactive_melee_swing", side_effect=_lethal_swing
    ), patch("ak_engine.turn.challenge_execution.resolve_spell_disruption") as mock_disrupt, patch(
        "ak_engine.turn.challenge_execution.resolve_personal_combat_spell_cast"
    ) as mock_cast:
        mock_round.return_value = MeleeRoundOutcome(result=None)
        outcome = resolve_challenge_combat(
            tactics, caster_leader, caster, target_leader, target, state, ScriptedRandom([])
        )

    assert outcome.winner == "b"
    assert not mock_disrupt.called  # dead before a disruption check would even matter
    assert not mock_cast.called


def test_resolve_challenge_combat_cast_at_spell_range_never_checks_disruption():
    # Unchanged, established scope: disruption is only checked at
    # MELEE_RANGE -- a CAST as the very first tactic (still SPELL_RANGE)
    # never rolls it, matching every pre-Phase-292 CAST test unaffected.
    state, caster_leader, caster, target_leader, target = _combatants(
        caster_kwargs={"skills": _skills_with(Ability.WHITE, 5, 9)}
    )
    tactics = [SearchTactic(Maneuver.CAST, Spell.HEAL.value)]

    with patch("ak_engine.turn.challenge_execution.resolve_reactive_melee_swing") as mock_swing, patch(
        "ak_engine.turn.challenge_execution.resolve_spell_disruption"
    ) as mock_disrupt, patch(
        "ak_engine.turn.challenge_execution.resolve_personal_combat_spell_cast", return_value=True
    ), patch("ak_engine.turn.challenge_execution.words_of_healing_heal"), patch(
        "ak_engine.turn.challenge_execution.resolve_melee_duel"
    ) as mock_duel:
        mock_duel.return_value = EncounterCombatResult(winner=None, rounds=1)
        resolve_challenge_combat(tactics, caster_leader, caster, target_leader, target, state, ScriptedRandom([]))

    assert not mock_swing.called
    assert not mock_disrupt.called


# -- Phase 294: apply_temper_melee_setup fix for the non-last MELEE branch --


def test_resolve_challenge_combat_non_last_melee_applies_temper_setup_before_the_first_round():
    # A real bug found while building the analogous engine in turn/
    # search_execution.py (Phase 293): the non-last-MELEE round-stepping
    # branch never called apply_temper_melee_setup() at all, so a
    # Berserk caster's own bonus hit points (turn/encounter.py's own
    # Phase 284 addendum) silently never applied for this specific plan
    # shape. resolve_one_melee_round() is mocked (undecided) so only the
    # setup step's own effect is observed.
    state, caster_leader, caster, target_leader, target = _combatants(caster_kwargs={"temper": Temper.BERSERK})
    tactics = [SearchTactic(Maneuver.MELEE), SearchTactic(Maneuver.TALK)]

    with patch("ak_engine.turn.challenge_execution.resolve_one_melee_round") as mock_round, patch(
        "ak_engine.turn.challenge_execution.resolve_melee_duel"
    ) as mock_duel:
        # mock_duel guards the exhausted-tactic-list fallback (reached
        # once TALK, unwired, falls through) -- unmocked, it would run a
        # second, real apply_temper_melee_setup() internally and muddy
        # this test's own isolated observation of the fix's own single
        # explicit call.
        mock_round.return_value = MeleeRoundOutcome(result=None)
        mock_duel.return_value = EncounterCombatResult(winner=None, rounds=1)
        resolve_challenge_combat(tactics, caster_leader, caster, target_leader, target, state, random.Random(0))

    assert CHARACTER_HIT_POINTS < caster.hit_points <= CHARACTER_HIT_POINTS + 4


def test_resolve_challenge_combat_non_last_melee_only_applies_temper_setup_once():
    # Two separate non-last MELEE tactics (a genuinely new plan shape,
    # but a real one this project must not silently mishandle) must not
    # double-apply Berserk's own bonus hit points or consume an extra
    # roll the second time around.
    state, caster_leader, caster, target_leader, target = _combatants(caster_kwargs={"temper": Temper.BERSERK})
    tactics = [
        SearchTactic(Maneuver.MELEE),
        SearchTactic(Maneuver.TALK),
        SearchTactic(Maneuver.MELEE),
        SearchTactic(Maneuver.TALK),
    ]

    with patch("ak_engine.turn.challenge_execution.resolve_one_melee_round") as mock_round, patch(
        "ak_engine.turn.challenge_execution.apply_temper_melee_setup"
    ) as mock_setup, patch("ak_engine.turn.challenge_execution.resolve_melee_duel") as mock_duel:
        mock_round.return_value = MeleeRoundOutcome(result=None)
        mock_duel.return_value = EncounterCombatResult(winner=None, rounds=1)
        resolve_challenge_combat(tactics, caster_leader, caster, target_leader, target, state, ScriptedRandom([]))

    assert mock_setup.call_count == 1


# -- Phase 297: the exhausted-fallback's own resolve_melee_duel() call must
# not re-apply Temper setup a second time --


def test_resolve_challenge_combat_non_last_melee_trailing_fallback_does_not_double_apply_temper_setup():
    # A real bug found in a dedicated bug-hunt audit: Phase 294's own fix
    # only guarded the *explicit* apply_temper_melee_setup() call before
    # round-stepping -- but resolve_melee_duel() itself always applies
    # setup again, internally, and the exhausted-tactic-list fallback
    # calls it unconditionally. So a non-last MELEE (round-stepping,
    # setup applied once) followed by an unwired tactic (TALK, falling
    # through to the fallback's own atomic resolve_melee_duel()) really
    # did apply Cautious' own dodge multiplier twice: 1.0 -> 0.9 -> 0.81
    # instead of the intended single 0.9. Unlike the two tests above,
    # resolve_melee_duel() is genuinely NOT mocked here -- the whole
    # point is observing its own real internal behavior.
    state, caster_leader, caster, target_leader, target = _combatants(caster_kwargs={"temper": Temper.CAUTIOUS})
    tactics = [SearchTactic(Maneuver.MELEE), SearchTactic(Maneuver.TALK)]

    with patch("ak_engine.turn.challenge_execution.resolve_one_melee_round") as mock_round:
        mock_round.return_value = MeleeRoundOutcome(result=None)
        resolve_challenge_combat(tactics, caster_leader, caster, target_leader, target, state, random.Random(0))

    assert caster.defensive_hit_multiplier == pytest.approx(0.9)


# -- Phase 305: character-vs-character Steal [ST], rulebook [5.5] ------


def test_apply_successful_theft_transfers_the_victims_first_held_item():
    state = _base_state()
    thief = LeaderState(1, kingdom_id=1, name="Thief", location=FIELD)
    victim = LeaderState(2, kingdom_id=2, name="Victim", location=FIELD)
    state.add_leader(thief)
    state.add_leader(victim)
    first = state.add_item(Treasure.ABILITY_TACTICAL, owner_leader_id=2)
    second = state.add_item(Treasure.ABILITY_MARCH, owner_leader_id=2)

    _apply_successful_theft(state, thief, victim)

    assert state.items[first.item_id].owner_leader_id == 1
    assert state.items[second.item_id].owner_leader_id == 2  # only one item changes hands


def test_apply_successful_theft_is_a_no_op_when_the_victim_holds_nothing():
    state = _base_state()
    thief = LeaderState(1, kingdom_id=1, name="Thief", location=FIELD)
    victim = LeaderState(2, kingdom_id=2, name="Victim", location=FIELD)
    state.add_leader(thief)
    state.add_leader(victim)

    _apply_successful_theft(state, thief, victim)  # must not raise

    assert state.items_held_by(1) == []


def test_resolve_steal_tactic_success_applies_theft():
    state = _base_state()
    thief = LeaderState(1, kingdom_id=1, name="Thief", location=FIELD)
    victim = LeaderState(2, kingdom_id=2, name="Victim", location=FIELD)
    state.add_leader(thief)
    state.add_leader(victim)
    item = state.add_item(Treasure.ABILITY_TACTICAL, owner_leader_id=2)

    outcome = _resolve_steal_tactic(thief, victim, state, ScriptedRandom([0.1]))  # < 15% base chance

    assert outcome == "success"
    assert state.items[item.item_id].owner_leader_id == 1


def test_resolve_steal_tactic_failure_then_evaded_leaves_no_trace():
    state = _base_state()
    thief = LeaderState(1, kingdom_id=1, name="Thief", location=FIELD)
    victim = LeaderState(2, kingdom_id=2, name="Victim", location=FIELD)
    state.add_leader(thief)
    state.add_leader(victim)

    outcome = _resolve_steal_tactic(thief, victim, state, ScriptedRandom([0.2, 0.1]))  # fail attempt, evade capture

    assert outcome == "evaded"


def test_resolve_steal_tactic_hero_thief_caught_robbing_a_king_is_executed():
    state = _base_state()
    thief = LeaderState(1, kingdom_id=1, name="Thief", location=FIELD)
    king = LeaderState(2, kingdom_id=2, name="King", location=FIELD, is_king=True)
    state.add_leader(thief)
    state.add_leader(king)

    outcome = _resolve_steal_tactic(thief, king, state, ScriptedRandom([0.5, 0.5]))  # fail attempt, fail evasion

    assert outcome == "executed"


def test_resolve_steal_tactic_hero_thief_caught_robbing_an_army_commanding_hero_is_executed():
    state = _base_state()
    thief = LeaderState(1, kingdom_id=1, name="Thief", location=FIELD)
    general = LeaderState(2, kingdom_id=2, name="General", location=FIELD)
    state.add_leader(thief)
    state.add_leader(general)
    state.add_army(ArmyState(201, 2, ArmyType.GARRISON, Quality.GREEN, FIELD, commanded_by=2))

    outcome = _resolve_steal_tactic(thief, general, state, ScriptedRandom([0.5, 0.5]))

    assert outcome == "executed"


def test_resolve_steal_tactic_king_vs_king_caught_pays_half_treasury_as_ransom():
    state = _base_state()
    state.kingdoms[1].treasury = 100
    thief_king = LeaderState(1, kingdom_id=1, name="Thief King", location=FIELD, is_king=True)
    victim_king = LeaderState(2, kingdom_id=2, name="Victim King", location=FIELD, is_king=True)
    state.add_leader(thief_king)
    state.add_leader(victim_king)

    outcome = _resolve_steal_tactic(thief_king, victim_king, state, ScriptedRandom([0.5, 0.5]))

    assert outcome == "ransom"
    assert state.kingdoms[1].treasury == 50


def test_resolve_steal_tactic_king_vs_king_caught_with_no_gold_is_executed():
    state = _base_state()
    state.kingdoms[1].treasury = 0
    thief_king = LeaderState(1, kingdom_id=1, name="Thief King", location=FIELD, is_king=True)
    victim_king = LeaderState(2, kingdom_id=2, name="Victim King", location=FIELD, is_king=True)
    state.add_leader(thief_king)
    state.add_leader(victim_king)

    outcome = _resolve_steal_tactic(thief_king, victim_king, state, ScriptedRandom([0.5, 0.5]))

    assert outcome == "executed"
    assert state.kingdoms[1].treasury == 0


def test_resolve_steal_tactic_caught_targeting_a_non_army_hero_is_combat():
    state = _base_state()
    thief = LeaderState(1, kingdom_id=1, name="Thief", location=FIELD)
    hero = LeaderState(2, kingdom_id=2, name="Hero", location=FIELD)
    state.add_leader(thief)
    state.add_leader(hero)

    outcome = _resolve_steal_tactic(thief, hero, state, ScriptedRandom([0.5, 0.5]))

    assert outcome == "combat"


def test_resolve_steal_tactic_king_caught_targeting_a_non_army_hero_is_also_combat():
    state = _base_state()
    king = LeaderState(1, kingdom_id=1, name="King", location=FIELD, is_king=True)
    hero = LeaderState(2, kingdom_id=2, name="Hero", location=FIELD)
    state.add_leader(king)
    state.add_leader(hero)

    outcome = _resolve_steal_tactic(king, hero, state, ScriptedRandom([0.5, 0.5]))

    assert outcome == "combat"


def test_resolve_steal_tactic_king_thief_caught_robbing_a_non_king_army_hero_is_unresolved():
    # None of the three sourced capture branches literally covers this
    # combination -- module docstring's own Phase 305 addendum.
    state = _base_state()
    king = LeaderState(1, kingdom_id=1, name="King", location=FIELD, is_king=True)
    general = LeaderState(2, kingdom_id=2, name="General", location=FIELD)
    state.add_leader(king)
    state.add_leader(general)
    state.add_army(ArmyState(201, 2, ArmyType.GARRISON, Quality.GREEN, FIELD, commanded_by=2))

    outcome = _resolve_steal_tactic(king, general, state, ScriptedRandom([0.5, 0.5]))

    assert outcome == "unresolved"


def test_resolve_steal_tactic_is_unresolved_with_no_rng_consumed_for_a_missing_leaderstate():
    # A garrison commander (Phase 291's own Duel reuse) has no LeaderState.
    state = _base_state()
    target = LeaderState(2, kingdom_id=2, name="Target", location=FIELD)
    state.add_leader(target)

    outcome = _resolve_steal_tactic(None, target, state, ScriptedRandom([]))  # any .random() call would raise

    assert outcome == "unresolved"


def test_resolve_challenge_combat_steal_executed_ends_the_encounter():
    state, caster_leader, caster, target_leader, target = _combatants()
    tactics = [SearchTactic(Maneuver.STEAL)]

    with patch("ak_engine.turn.challenge_execution._resolve_steal_tactic", return_value="executed"):
        outcome = resolve_challenge_combat(tactics, caster_leader, caster, target_leader, target, state, ScriptedRandom([]))

    assert outcome.winner == "b"
    assert outcome.steal_outcome == "executed"


def test_resolve_challenge_combat_steal_success_lets_the_plan_continue():
    state, caster_leader, caster, target_leader, target = _combatants()
    tactics = [SearchTactic(Maneuver.STEAL), SearchTactic(Maneuver.MELEE)]

    with patch("ak_engine.turn.challenge_execution._resolve_steal_tactic", return_value="success"), patch(
        "ak_engine.turn.challenge_execution.resolve_melee_duel"
    ) as mock_duel:
        mock_duel.return_value = EncounterCombatResult(winner="a", rounds=1)
        outcome = resolve_challenge_combat(tactics, caster_leader, caster, target_leader, target, state, ScriptedRandom([]))

    assert outcome.winner == "a"
    assert outcome.steal_outcome == "success"


def test_resolve_challenge_combat_steal_capture_combat_at_spell_range_lets_a_following_melee_tactic_decide():
    state, caster_leader, caster, target_leader, target = _combatants()
    tactics = [SearchTactic(Maneuver.STEAL), SearchTactic(Maneuver.MELEE)]

    with patch("ak_engine.turn.challenge_execution._resolve_steal_tactic", return_value="combat"), patch(
        "ak_engine.turn.challenge_execution.resolve_melee_duel"
    ) as mock_duel:
        mock_duel.return_value = EncounterCombatResult(winner="a", rounds=1)
        outcome = resolve_challenge_combat(
            tactics, caster_leader, caster, target_leader, target, state, ScriptedRandom([], choice_indices=[0])
        )

    assert outcome.winner == "a"  # decided by the following MELEE tactic, not an atomic Steal-side duel
    assert outcome.steal_outcome == "combat"
    assert outcome.steal_capture_range is CombatRange.SPELL_RANGE


def test_resolve_challenge_combat_steal_capture_sets_the_rolled_range_and_falls_through_to_the_exhausted_default():
    # Phase 306 correction: no follow-up tactic after STEAL -- being
    # caught no longer atomically resolves its own duel, so this falls
    # through to the pre-existing "exhausted tactic list defaults to
    # Melee" tail, the same way an unwired trailing tactic already would.
    state, caster_leader, caster, target_leader, target = _combatants()
    tactics = [SearchTactic(Maneuver.STEAL)]

    with patch("ak_engine.turn.challenge_execution._resolve_steal_tactic", return_value="combat"), patch(
        "ak_engine.turn.challenge_execution.resolve_melee_duel"
    ) as mock_duel:
        mock_duel.return_value = EncounterCombatResult(winner="b", rounds=1)
        outcome = resolve_challenge_combat(
            tactics, caster_leader, caster, target_leader, target, state, ScriptedRandom([], choice_indices=[1])
        )

    assert outcome.winner == "b"
    assert outcome.steal_outcome == "combat"
    assert outcome.steal_capture_range is CombatRange.BOW_RANGE
    mock_duel.assert_called_once()  # the exhausted-list tail, not an atomic Steal-side resolution


def test_resolve_challenge_combat_steal_capture_at_melee_range_then_a_following_melee_tactic_resolves_once():
    # [11.3]'s own worked example ("CA-IN, ST, FL, ME"): getting caught
    # hands control to the plan's own next tactic. FLEE stays unwired
    # (a separate, already-documented gap) and is skipped; the following
    # MELEE picks up from the rolled range without re-closing it.
    state, caster_leader, caster, target_leader, target = _combatants()
    tactics = [SearchTactic(Maneuver.STEAL), SearchTactic(Maneuver.FLEE), SearchTactic(Maneuver.MELEE)]

    with patch("ak_engine.turn.challenge_execution._resolve_steal_tactic", return_value="combat"), patch(
        "ak_engine.turn.challenge_execution.resolve_melee_duel"
    ) as mock_duel:
        mock_duel.return_value = EncounterCombatResult(winner="b", rounds=1)
        outcome = resolve_challenge_combat(
            tactics, caster_leader, caster, target_leader, target, state, ScriptedRandom([], choice_indices=[2])
        )

    assert outcome.winner == "b"
    assert outcome.steal_outcome == "combat"
    assert outcome.steal_capture_range is CombatRange.MELEE_RANGE
    mock_duel.assert_called_once()
