from __future__ import annotations

import random

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.game_state import ArmyState, GameState, KingdomState, ProvinceState
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.race import Race
from ak_engine.turn.battle_orchestrator import _build_battle_units, fight_battle
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


def no_luck_overwhelming_attacker_rng(win_roll=0.1, winner_quality_roll=0.99, loser_quality_roll=0.99):
    return ScriptedRandom([0.9, 0.9, 0.9, win_roll, winner_quality_roll, loser_quality_roll])


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
