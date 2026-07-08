from __future__ import annotations

import random

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.game_state import ArmyState, GameState, KingdomState, ProvinceState
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.race import Race
from ak_engine.turn.battle_line import BattleUnit
from ak_engine.turn.battle_orchestrator import (
    MultiAttackerParty,
    _build_battle_units,
    _maybe_fight_duel,
    _select_side_commander,
    fight_battle,
    fight_multi_attacker_battle,
)
from ak_engine.turn.combat import Quality

from _helpers import ScriptedRandom

FIELD = HexCoord(1, 1)
DEFENDER_HOME = HexCoord(2, 1)  # a neighbor of FIELD on the odd-r grid


def build_state(attacker_quality=Quality.ELITE, defender_quality=Quality.GREEN) -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, HexCoord(0, 0)))
    state.add_kingdom(KingdomState(2, "Defendia", Race.HUMAN, Alignment.NEUTRAL, DEFENDER_HOME))
    state.add_province(ProvinceState(FIELD, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2))
    state.add_province(ProvinceState(DEFENDER_HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2))
    state.add_army(ArmyState(101, 1, ArmyType.HVY_CAVALRY, attacker_quality, FIELD))
    state.add_army(ArmyState(201, 2, ArmyType.GARRISON, defender_quality, FIELD))
    return state


def no_luck_overwhelming_attacker_rng(
    win_roll=0.1, pursuit_attempt_roll=0.99, winner_quality_roll=0.99, loser_quality_roll=0.99
):
    # pursuit_attempt_roll=0.99 (>= the 75% cavalry-pursuit chance) means
    # the sole winning HVY_CAVALRY unit declines to attempt pursuit, so
    # resolve_pursuit never runs (0 further rolls) and every retreating
    # army proceeds through the ordinary retreat/disband path unchanged
    # from before Phase 28's Pursuit wiring. This roll lands right after
    # the battle-resolution rolls and before the attacker's own
    # winner_quality_roll, since defender-side pursuit is checked before
    # the attacker per-army loop runs.
    return ScriptedRandom(
        [0.9, 0.9, 0.9, win_roll, pursuit_attempt_roll, winner_quality_roll, loser_quality_roll]
    )


def test_overwhelming_attacker_conquers_and_defender_retreats():
    state = build_state()
    rng = no_luck_overwhelming_attacker_rng()

    report = fight_battle(state, attacker_kingdom_id=1, province_coord=FIELD, attacker_army_ids=[101], rng=rng)

    assert report.conquered is True
    assert state.provinces[FIELD].owner_kingdom_id == 1
    assert state.provinces[FIELD].contested_by_kingdom_id is None
    assert 201 in report.retreated_army_ids
    assert state.armies[201].location == DEFENDER_HOME
    assert 101 in state.armies  # attacker survives


def test_overwhelming_attacker_conquers_and_defender_is_destroyed_when_no_retreat_allowed():
    state = build_state()
    rng = no_luck_overwhelming_attacker_rng()

    report = fight_battle(
        state, attacker_kingdom_id=1, province_coord=FIELD, attacker_army_ids=[101],
        loser_retreats=False, rng=rng,
    )

    assert report.conquered is True
    assert 201 in report.destroyed_army_ids
    assert 201 not in state.armies


def test_defender_disbands_when_no_friendly_province_to_retreat_to():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, HexCoord(0, 0)))
    state.add_kingdom(KingdomState(2, "Defendia", Race.HUMAN, Alignment.NEUTRAL, FIELD))
    state.add_province(ProvinceState(FIELD, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2))
    state.add_army(ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, FIELD))
    state.add_army(ArmyState(201, 2, ArmyType.GARRISON, Quality.GREEN, FIELD))
    rng = no_luck_overwhelming_attacker_rng()

    report = fight_battle(state, attacker_kingdom_id=1, province_coord=FIELD, attacker_army_ids=[101], rng=rng)

    assert 201 in report.disbanded_army_ids
    assert 201 not in state.armies


def test_defender_becomes_unhireable_mercenary_when_average_quality_and_no_retreat():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, HexCoord(0, 0)))
    state.add_kingdom(KingdomState(2, "Defendia", Race.HUMAN, Alignment.NEUTRAL, FIELD))
    state.add_province(ProvinceState(FIELD, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2))
    state.add_army(ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, FIELD))
    state.add_army(ArmyState(201, 2, ArmyType.GARRISON, Quality.AVERAGE, FIELD))
    rng = no_luck_overwhelming_attacker_rng()

    report = fight_battle(state, attacker_kingdom_id=1, province_coord=FIELD, attacker_army_ids=[101], rng=rng)

    assert 201 in report.mercenary_army_ids
    assert state.armies[201].unhireable_this_turn is True
    assert 201 in state.armies  # not removed, just marked
    assert state.armies[201].kingdom_id is None  # ownerless -- a real mercenary now
    assert state.armies[201].commanded_by is None


def test_mercenaries_at_the_target_province_do_not_get_swept_in_as_defenders():
    # A masterless mercenary band sitting in a contested-owner province
    # isn't anyone's defender by default -- rulebook doesn't grant it that
    # role, and `is_allied(None, x)` being False must not be read as "this
    # is an enemy".
    state = build_state()
    state.add_army(ArmyState(301, None, ArmyType.GARRISON, Quality.AVERAGE, FIELD))
    rng = no_luck_overwhelming_attacker_rng()

    report = fight_battle(state, attacker_kingdom_id=1, province_coord=FIELD, attacker_army_ids=[101], rng=rng)

    # Untouched by the battle entirely -- not a participant, so it appears
    # in none of the report's per-army outcome lists.
    all_reported_ids = {
        *report.destroyed_army_ids,
        *report.retreated_army_ids,
        *report.disbanded_army_ids,
        *report.mercenary_army_ids,
        *report.quality_changes.keys(),
    }
    assert 301 not in all_reported_ids
    assert state.armies[301].kingdom_id is None
    assert state.armies[301].quality == Quality.AVERAGE
    assert state.armies[301].location == FIELD


def test_allied_armies_are_not_treated_as_defenders():
    state = build_state()
    state.allied_kingdoms.add(frozenset({1, 2}))
    rng = ScriptedRandom([])  # should never be consumed: no battle happens

    try:
        fight_battle(state, attacker_kingdom_id=1, province_coord=FIELD, attacker_army_ids=[101], rng=rng)
        assert False, "expected ValueError: no enemy defenders present"
    except ValueError:
        pass


def test_fight_battle_raises_without_defenders():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, HexCoord(0, 0)))
    state.add_province(ProvinceState(FIELD, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=None))
    state.add_army(ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, FIELD))

    try:
        fight_battle(state, attacker_kingdom_id=1, province_coord=FIELD, attacker_army_ids=[101], rng=random.Random(0))
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_fight_battle_structural_invariants_with_real_rng():
    state = build_state(attacker_quality=Quality.AVERAGE, defender_quality=Quality.AVERAGE)
    rng = random.Random(2026)

    report = fight_battle(state, attacker_kingdom_id=1, province_coord=FIELD, attacker_army_ids=[101], rng=rng)

    # Exactly one battle outcome category applies.
    outcome_flags = [
        report.conquered,
        101 in report.destroyed_army_ids or 201 in report.destroyed_army_ids,
        state.provinces[FIELD].contested_by_kingdom_id is not None,
    ]
    assert any(outcome_flags) or state.provinces[FIELD].owner_kingdom_id == 2


def test_build_battle_units_checks_home_province_against_the_battle_province_not_army_location():
    # Regression test: an attacking army's `.location` is still its
    # *origin* before a Move that triggers a battle actually completes.
    # The home-province strength bonus must be judged against the battle
    # province (`province_coord`), not that stale `.location`.
    origin = HexCoord(9, 9)
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, home_province=FIELD))
    army = ArmyState(101, 1, ArmyType.BOWMEN, Quality.AVERAGE, location=origin)
    state.add_army(army)

    units_at_home = _build_battle_units(
        [army], state, is_defender=False, terrain=Terrain.PLAINS, province_coord=FIELD, rng=random.Random(0)
    )
    units_away = _build_battle_units(
        [army], state, is_defender=False, terrain=Terrain.PLAINS, province_coord=origin, rng=random.Random(0)
    )

    # FIELD is the kingdom's home province -> +1 quality level -> higher strength.
    assert units_at_home[0].effective_strength > units_away[0].effective_strength


# --- Pursuit (rulebook [7.3]) -------------------------------------------


def test_pursuit_destroys_a_caught_retreating_army():
    state = build_state()
    # 3 luck, win_roll (decisive attacker win), pursuit-attempt (0.1 < the
    # 75% cavalry chance -> the winning HVY_CAVALRY attempts pursuit),
    # pursuit-standstill (0.1 -> destroys the far-weaker retreating
    # GARRISON/GREEN target), attacker's own winner_quality_roll. The
    # defender never reaches _retreat_or_disband at all, so no further
    # rolls are consumed.
    rng = ScriptedRandom([0.9, 0.9, 0.9, 0.1, 0.1, 0.1, 0.99])

    report = fight_battle(state, attacker_kingdom_id=1, province_coord=FIELD, attacker_army_ids=[101], rng=rng)

    assert report.conquered is True
    assert 201 in report.pursuit_destroyed_army_ids
    assert 201 not in report.retreated_army_ids
    assert 201 not in state.armies


def test_pursuit_does_not_apply_when_loser_retreats_is_false():
    state = build_state()
    rng = no_luck_overwhelming_attacker_rng()

    report = fight_battle(
        state, attacker_kingdom_id=1, province_coord=FIELD, attacker_army_ids=[101],
        loser_retreats=False, rng=rng,
    )

    assert report.pursuit_destroyed_army_ids == []
    assert 201 in report.destroyed_army_ids


# --- Duel (rulebook [7.1]) ------------------------------------------------


def test_select_side_commander_falls_back_to_garrison_for_unled_defenders():
    armies = [ArmyState(201, 2, ArmyType.GARRISON, Quality.GREEN, FIELD)]  # unled
    units = [BattleUnit(ArmyType.GARRISON, 10.0, source_id=201)]

    commander, commander_units = _select_side_commander(armies, units, allow_garrison_fallback=True)

    assert commander is not None
    assert commander.leader_id is None
    assert commander.contingent_size == 1
    assert commander_units == units


def test_select_side_commander_no_fallback_for_unled_attackers():
    armies = [ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, FIELD)]  # unled
    units = [BattleUnit(ArmyType.HVY_CAVALRY, 100.0, source_id=101)]

    commander, commander_units = _select_side_commander(armies, units, allow_garrison_fallback=False)

    assert commander is None
    assert commander_units == []


def test_select_side_commander_picks_largest_contingent_among_led_armies():
    armies = [
        ArmyState(101, 1, ArmyType.BOWMEN, Quality.AVERAGE, FIELD, commanded_by=1),
        ArmyState(102, 1, ArmyType.BOWMEN, Quality.AVERAGE, FIELD, commanded_by=2),
        ArmyState(103, 1, ArmyType.BOWMEN, Quality.AVERAGE, FIELD, commanded_by=2),
    ]
    units = [
        BattleUnit(ArmyType.BOWMEN, 10.0, source_id=101),
        BattleUnit(ArmyType.BOWMEN, 10.0, source_id=102),
        BattleUnit(ArmyType.BOWMEN, 10.0, source_id=103),
    ]

    commander, commander_units = _select_side_commander(armies, units, allow_garrison_fallback=False)

    assert commander.leader_id == 2  # 2 armies vs leader 1's 1 army
    assert commander.contingent_size == 2
    assert {u.source_id for u in commander_units} == {102, 103}


def test_maybe_fight_duel_demoralizes_the_losers_own_led_units():
    attacker_armies = [ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, FIELD, commanded_by=501)]
    defender_armies = [ArmyState(201, 2, ArmyType.GARRISON, Quality.GREEN, FIELD, commanded_by=502)]
    attacker_units = [BattleUnit(ArmyType.HVY_CAVALRY, 100.0, source_id=101)]
    defender_units = [BattleUnit(ArmyType.GARRISON, 10.0, source_id=201)]
    rng = ScriptedRandom([0.01])  # attacker's huge strength edge -> wins the duel

    outcome = _maybe_fight_duel(attacker_armies, defender_armies, attacker_units, defender_units, rng)

    assert outcome.attacker_commander_leader_id == 501
    assert outcome.defender_commander_leader_id == 502
    assert outcome.loser_side == "defender"
    assert defender_units[0].effective_strength == 10.0 * 0.75  # DUEL_DEMORALIZATION_MULTIPLIER
    assert attacker_units[0].effective_strength == 100.0  # winner's own units untouched


def test_maybe_fight_duel_skips_when_attacker_is_unled():
    attacker_armies = [ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, FIELD)]  # unled
    defender_armies = [ArmyState(201, 2, ArmyType.GARRISON, Quality.GREEN, FIELD, commanded_by=502)]
    attacker_units = [BattleUnit(ArmyType.HVY_CAVALRY, 100.0, source_id=101)]
    defender_units = [BattleUnit(ArmyType.GARRISON, 10.0, source_id=201)]
    rng = ScriptedRandom([])  # must not be consumed -- no duel without an attacker commander

    outcome = _maybe_fight_duel(attacker_armies, defender_armies, attacker_units, defender_units, rng)

    assert outcome.loser_side is None
    assert defender_units[0].effective_strength == 10.0  # untouched


def test_fight_battle_reports_duel_commanders_and_demoralizes_loser():
    state = build_state()
    state.armies[101].commanded_by = 501
    state.armies[201].commanded_by = 502
    # duel roll (0.01, attacker wins), then the usual no-luck-overwhelming
    # sequence (3 luck, win_roll, pursuit-decline, winner_quality,
    # loser_quality for the defender's successful retreat to DEFENDER_HOME).
    rng = ScriptedRandom([0.01, 0.9, 0.9, 0.9, 0.1, 0.99, 0.99, 0.99])

    report = fight_battle(state, attacker_kingdom_id=1, province_coord=FIELD, attacker_army_ids=[101], rng=rng)

    assert report.attacker_commander_leader_id == 501
    assert report.defender_commander_leader_id == 502
    assert report.duel_loser_side == "defender"
    assert report.conquered is True


def test_fight_battle_no_duel_when_attacker_is_unled():
    state = build_state()  # armies unled by default
    rng = no_luck_overwhelming_attacker_rng()

    report = fight_battle(state, attacker_kingdom_id=1, province_coord=FIELD, attacker_army_ids=[101], rng=rng)

    assert report.duel_loser_side is None
    assert report.attacker_commander_leader_id is None


# --- Multiple Contingents (rulebook [7.8]) --------------------------------


def test_fight_multi_attacker_battle_unites_same_origin_attackers():
    state = build_state()
    state.add_army(ArmyState(102, 1, ArmyType.BOWMEN, Quality.AVERAGE, FIELD))
    origin = HexCoord(5, 5)
    parties = [
        MultiAttackerParty(leader_id=10, kingdom_id=1, army_ids=[101], origin_province=origin),
        MultiAttackerParty(leader_id=20, kingdom_id=1, army_ids=[102], origin_province=origin),
    ]
    # 0.1 < SAME_ORIGIN_UNITE_CHANCE (0.85) -> unites into one battle; the
    # rest are generic, repeated "safe" rolls so the 2-vs-1 battle that
    # follows never runs out of scripted values regardless of exactly how
    # many luck/quality rolls its own resolution consumes.
    rng = ScriptedRandom([0.1] + [0.1] * 40, choice_indices=[0] * 40)

    reports = fight_multi_attacker_battle(state, FIELD, parties, rng=rng)

    assert len(reports) == 1
    all_ids = {
        *reports[0].destroyed_army_ids,
        *reports[0].retreated_army_ids,
        *reports[0].disbanded_army_ids,
        *reports[0].mercenary_army_ids,
        *reports[0].pursuit_destroyed_army_ids,
        *reports[0].quality_changes.keys(),
    }
    assert 101 in all_ids
    assert 102 in all_ids  # both armies fought in the SAME (united) battle


def test_fight_multi_attacker_battle_splits_different_origin_attackers():
    state = build_state(attacker_quality=Quality.GREEN, defender_quality=Quality.ELITE)
    state.armies[201].army_type = ArmyType.HVY_CAVALRY  # overwhelmingly strong defender:
    state.add_army(ArmyState(102, 1, ArmyType.BOWMEN, Quality.GREEN, FIELD))  # survives both separate battles
    parties = [
        MultiAttackerParty(leader_id=10, kingdom_id=1, army_ids=[101], origin_province=HexCoord(5, 5)),
        MultiAttackerParty(leader_id=20, kingdom_id=1, army_ids=[102], origin_province=HexCoord(9, 9)),
    ]
    # 0.99 >= DIFFERENT_ORIGIN_UNITE_CHANCE (0.30) -> stays split into two
    # separate battles against the same (overwhelmingly strong, so it
    # survives both) defender.
    rng = ScriptedRandom([0.99] + [0.5] * 40, choice_indices=[0] * 40)

    reports = fight_multi_attacker_battle(state, FIELD, parties, rng=rng)

    assert len(reports) == 2


def test_fight_multi_attacker_battle_claims_province_for_largest_contingent_kingdom():
    state = build_state()
    state.add_kingdom(KingdomState(3, "Allia", Race.HUMAN, Alignment.GOOD, HexCoord(9, 9)))
    state.allied_kingdoms.add(frozenset({1, 3}))
    state.add_army(ArmyState(102, 3, ArmyType.BOWMEN, Quality.AVERAGE, FIELD))
    state.add_army(ArmyState(103, 3, ArmyType.BOWMEN, Quality.AVERAGE, FIELD))
    origin = HexCoord(5, 5)
    parties = [
        MultiAttackerParty(leader_id=10, kingdom_id=1, army_ids=[101], origin_province=origin),
        MultiAttackerParty(leader_id=20, kingdom_id=3, army_ids=[102, 103], origin_province=origin),  # larger contingent
    ]
    # Unite (same origin), then overwhelming, no-luck attacker rolls for
    # the resulting 3-vs-1 battle against the weak GARRISON/GREEN defender.
    rng = ScriptedRandom([0.1] + [0.1] * 40, choice_indices=[0] * 40)

    reports = fight_multi_attacker_battle(state, FIELD, parties, rng=rng)

    assert len(reports) == 1
    if reports[0].conquered:
        assert state.provinces[FIELD].owner_kingdom_id == 3  # kingdom 3 contributed 2 of 3 armies
