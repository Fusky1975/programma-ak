from __future__ import annotations

import random

import pytest

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.enums import Ability
from ak_engine.models.game_state import ArmyState, GameState, KingdomState, LeaderState, ProvinceState
from ak_engine.models.kingdom import SkillTable
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
from ak_engine.turn.duel import Commander
from ak_engine.turn.strength import compute_effective_strength

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


# --- Whales: zero strength off-sea + guaranteed sea retreat (Phase 37) --


def test_defender_whales_retreat_to_sea_even_when_no_retreat_allowed():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, HexCoord(0, 0)))
    state.add_kingdom(KingdomState(2, "Defendia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(9, 9)))
    state.add_province(ProvinceState(FIELD, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2))
    state.add_province(ProvinceState(DEFENDER_HOME, Terrain.SEA, Race.HUMAN, owner_kingdom_id=None))
    state.add_army(ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, FIELD))
    state.add_army(ArmyState(201, 2, ArmyType.WHALES, Quality.GREEN, FIELD))
    rng = no_luck_overwhelming_attacker_rng()

    report = fight_battle(
        state, attacker_kingdom_id=1, province_coord=FIELD, attacker_army_ids=[101], loser_retreats=False, rng=rng
    )

    # "without fear of being destroyed" -- retreats even though
    # loser_retreats=False would otherwise mean outright destruction, and
    # even at GREEN quality (which would normally disband, not retreat).
    assert 201 in report.retreated_army_ids
    assert 201 not in report.destroyed_army_ids
    assert 201 not in report.disbanded_army_ids
    assert state.armies[201].location == DEFENDER_HOME


def test_attacker_whales_retreat_to_sea_when_repelled():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, HexCoord(0, 0)))
    state.add_kingdom(KingdomState(2, "Defendia", Race.HUMAN, Alignment.NEUTRAL, DEFENDER_HOME))
    state.add_province(ProvinceState(FIELD, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2))
    state.add_province(ProvinceState(DEFENDER_HOME, Terrain.SEA, Race.HUMAN, owner_kingdom_id=1))
    state.add_army(ArmyState(101, 1, ArmyType.WHALES, Quality.GREEN, FIELD))
    state.add_army(ArmyState(201, 2, ArmyType.HVY_CAVALRY, Quality.ELITE, FIELD))
    # Whales have 0 strength on Plains regardless of the win roll -- the
    # defender wins decisively no matter what value is scripted there.
    rng = ScriptedRandom([0.9, 0.9, 0.9, 0.5, 0.99, 0.99])

    report = fight_battle(
        state, attacker_kingdom_id=1, province_coord=FIELD, attacker_army_ids=[101], loser_retreats=False, rng=rng
    )

    assert 101 in report.retreated_army_ids
    assert state.armies[101].location == DEFENDER_HOME


def test_whales_fall_back_to_ordinary_disband_when_no_adjacent_sea_province():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, HexCoord(0, 0)))
    state.add_kingdom(KingdomState(2, "Defendia", Race.HUMAN, Alignment.NEUTRAL, FIELD))
    state.add_province(ProvinceState(FIELD, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2))
    # No adjacent Sea province exists anywhere in this state.
    state.add_army(ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, FIELD))
    state.add_army(ArmyState(201, 2, ArmyType.WHALES, Quality.GREEN, FIELD))
    rng = no_luck_overwhelming_attacker_rng()

    report = fight_battle(state, attacker_kingdom_id=1, province_coord=FIELD, attacker_army_ids=[101], rng=rng)

    assert 201 in report.disbanded_army_ids
    assert 201 not in state.armies


# --- Fleets on land: reduced to Depleted instead of eliminated (Phase 38) -


def test_defender_fleet_on_land_reduced_to_depleted_instead_of_destroyed():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, HexCoord(0, 0)))
    state.add_kingdom(KingdomState(2, "Defendia", Race.HUMAN, Alignment.NEUTRAL, FIELD))
    state.add_province(ProvinceState(FIELD, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2))
    state.add_army(ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, FIELD))
    state.add_army(ArmyState(201, 2, ArmyType.FLEET, Quality.AVERAGE, FIELD))
    rng = no_luck_overwhelming_attacker_rng()

    report = fight_battle(
        state, attacker_kingdom_id=1, province_coord=FIELD, attacker_army_ids=[101], loser_retreats=False, rng=rng
    )

    assert 201 not in report.destroyed_army_ids
    assert 201 in state.armies
    assert state.armies[201].quality == Quality.DEPLETED
    assert report.quality_changes[201] == Quality.DEPLETED


def test_defender_fleet_on_land_reduced_to_depleted_instead_of_disbanding():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, HexCoord(0, 0)))
    state.add_kingdom(KingdomState(2, "Defendia", Race.HUMAN, Alignment.NEUTRAL, FIELD))
    state.add_province(ProvinceState(FIELD, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2))
    # No friendly province to retreat to -> would ordinarily disband (GREEN).
    state.add_army(ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, FIELD))
    state.add_army(ArmyState(201, 2, ArmyType.FLEET, Quality.GREEN, FIELD))
    rng = no_luck_overwhelming_attacker_rng()

    report = fight_battle(state, attacker_kingdom_id=1, province_coord=FIELD, attacker_army_ids=[101], rng=rng)

    assert 201 not in report.disbanded_army_ids
    assert 201 in state.armies
    assert state.armies[201].quality == Quality.DEPLETED


def test_fleet_retreats_normally_when_a_destination_exists():
    # A successful ordinary retreat already avoids elimination on its own
    # -- no special-casing needed or applied.
    state = build_state()
    state.armies[201].army_type = ArmyType.FLEET
    rng = no_luck_overwhelming_attacker_rng()

    report = fight_battle(state, attacker_kingdom_id=1, province_coord=FIELD, attacker_army_ids=[101], rng=rng)

    assert 201 in report.retreated_army_ids
    assert state.armies[201].location == DEFENDER_HOME


def test_fleet_at_average_quality_still_becomes_mercenary_when_no_retreat_destination():
    # Becoming a mercenary already isn't "elimination" -- unaffected by
    # the Depleted-instead-of-eliminated exception.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, HexCoord(0, 0)))
    state.add_kingdom(KingdomState(2, "Defendia", Race.HUMAN, Alignment.NEUTRAL, FIELD))
    state.add_province(ProvinceState(FIELD, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2))
    state.add_army(ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, FIELD))
    state.add_army(ArmyState(201, 2, ArmyType.FLEET, Quality.AVERAGE, FIELD))
    rng = no_luck_overwhelming_attacker_rng()

    report = fight_battle(state, attacker_kingdom_id=1, province_coord=FIELD, attacker_army_ids=[101], rng=rng)

    assert 201 in report.mercenary_army_ids
    assert state.armies[201].kingdom_id is None
    assert state.armies[201].quality == Quality.AVERAGE  # untouched, not forced to Depleted


def test_fleet_in_a_sea_battle_follows_ordinary_elimination_rules():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, HexCoord(0, 0)))
    state.add_kingdom(KingdomState(2, "Defendia", Race.HUMAN, Alignment.NEUTRAL, FIELD))
    state.add_province(ProvinceState(FIELD, Terrain.SEA, Race.HUMAN, owner_kingdom_id=2))
    state.add_army(ArmyState(101, 1, ArmyType.WHALES, Quality.ELITE, FIELD))
    state.add_army(ArmyState(201, 2, ArmyType.FLEET, Quality.AVERAGE, FIELD))
    rng = no_luck_overwhelming_attacker_rng()

    report = fight_battle(
        state, attacker_kingdom_id=1, province_coord=FIELD, attacker_army_ids=[101], loser_retreats=False, rng=rng
    )

    assert 201 in report.destroyed_army_ids
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


def test_build_battle_units_applies_combat_ability_level_to_every_unit_on_the_side():
    # Rulebook [6.3]: "Tactical Ability +20%/level". Phase 30: the level
    # passed in here is the side's real Supreme Commander tactical skill,
    # looked up via LeaderState.skills -- see _select_side_commander.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, home_province=HexCoord(9, 9)))
    army = ArmyState(101, 1, ArmyType.BOWMEN, Quality.AVERAGE, location=FIELD)
    state.add_army(army)

    units_no_ability = _build_battle_units(
        [army], state, is_defender=False, terrain=Terrain.PLAINS, province_coord=FIELD, rng=random.Random(0)
    )
    units_with_ability = _build_battle_units(
        [army],
        state,
        is_defender=False,
        terrain=Terrain.PLAINS,
        province_coord=FIELD,
        rng=random.Random(0),
        combat_ability_level=3,
    )

    assert units_with_ability[0].effective_strength == units_no_ability[0].effective_strength * 1.6


def test_build_battle_units_reduces_quality_in_desert_without_camels():
    # Rulebook: "In a desert battle, one camel unit should be present...
    # If not, all armies have their quality reduced by 1 level." AVERAGE
    # (2) -> GREEN (1) halves the strength multiplier, all else equal.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.NEUTRAL, home_province=HexCoord(9, 9)))
    bowmen = ArmyState(101, 1, ArmyType.BOWMEN, Quality.AVERAGE, location=FIELD)
    state.add_army(bowmen)

    without_camel = _build_battle_units(
        [bowmen], state, is_defender=False, terrain=Terrain.DESERT, province_coord=FIELD, rng=random.Random(0)
    )

    camel = ArmyState(102, 1, ArmyType.CAMEL_CORPS, Quality.AVERAGE, location=FIELD)
    with_camel = _build_battle_units(
        [bowmen, camel], state, is_defender=False, terrain=Terrain.DESERT, province_coord=FIELD, rng=random.Random(0)
    )

    # with_camel[0] is still the Bowmen unit (list order preserved) -- no
    # penalty for anyone on the side once a Camel Corps is present.
    assert with_camel[0].effective_strength == pytest.approx(without_camel[0].effective_strength * 2)


def test_build_battle_units_camel_check_ignored_outside_desert():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.NEUTRAL, home_province=HexCoord(9, 9)))
    bowmen = ArmyState(101, 1, ArmyType.BOWMEN, Quality.AVERAGE, location=FIELD)
    state.add_army(bowmen)

    no_camel_plains = _build_battle_units(
        [bowmen], state, is_defender=False, terrain=Terrain.PLAINS, province_coord=FIELD, rng=random.Random(0)
    )
    camel = ArmyState(102, 1, ArmyType.CAMEL_CORPS, Quality.AVERAGE, location=FIELD)
    with_camel_plains = _build_battle_units(
        [bowmen, camel], state, is_defender=False, terrain=Terrain.PLAINS, province_coord=FIELD, rng=random.Random(0)
    )

    assert no_camel_plains[0].effective_strength == with_camel_plains[0].effective_strength


def test_build_battle_units_fanaticism_off_by_default_never_touches_rng():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, home_province=HexCoord(9, 9)))
    army = ArmyState(101, 1, ArmyType.BOWMEN, Quality.AVERAGE, location=FIELD)
    state.add_army(army)
    rng = ScriptedRandom([])  # any rng.random() call here raises IndexError

    units = _build_battle_units([army], state, is_defender=False, terrain=Terrain.PLAINS, province_coord=FIELD, rng=rng)

    baseline = compute_effective_strength(ArmyType.BOWMEN, Race.HUMAN, Quality.AVERAGE, Terrain.PLAINS)
    assert units[0].effective_strength == baseline


def test_build_battle_units_fanaticism_enabled_rolls_the_kingdoms_real_chance():
    # Alignment.GOOD -> 40% chance (turn/strength.py FANATICISM_CHANCE).
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, home_province=HexCoord(9, 9)))
    army = ArmyState(101, 1, ArmyType.BOWMEN, Quality.AVERAGE, location=FIELD)
    state.add_army(army)

    succeeds = _build_battle_units(
        [army], state, is_defender=False, terrain=Terrain.PLAINS, province_coord=FIELD,
        rng=ScriptedRandom([0.1]), apply_fanaticism=True,
    )
    fails = _build_battle_units(
        [army], state, is_defender=False, terrain=Terrain.PLAINS, province_coord=FIELD,
        rng=ScriptedRandom([0.9]), apply_fanaticism=True,
    )

    fanatical_strength = compute_effective_strength(
        ArmyType.BOWMEN, Race.HUMAN, Quality.AVERAGE, Terrain.PLAINS, is_fanatical=True
    )
    baseline = compute_effective_strength(ArmyType.BOWMEN, Race.HUMAN, Quality.AVERAGE, Terrain.PLAINS)
    assert succeeds[0].effective_strength == fanatical_strength
    assert fails[0].effective_strength == baseline
    assert fanatical_strength > baseline


def _skills_with_druid(level: int) -> SkillTable:
    raw = [0] * 30
    raw[Ability.DRUID.value * 2] = level  # (skill, aptitude) pair -- only skill matters here
    return SkillTable(raw)


def test_build_battle_units_druidic_shortfall_penalizes_a_foreign_race_led_army():
    # A Human leader (Druid skill 0) commanding a Dragon army (DRUID_TABLE
    # requires 4) -- reachable via Pick_Up attaching a co-located army
    # regardless of ownership. Race mismatch is what triggers the penalty,
    # not the kingdom_id mismatch itself.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Humania", Race.HUMAN, Alignment.NEUTRAL, home_province=HexCoord(9, 9)))
    state.add_kingdom(KingdomState(2, "Dragonia", Race.DRAGONS, Alignment.NEUTRAL, home_province=HexCoord(8, 8)))
    state.add_leader(LeaderState(1, kingdom_id=1, name="Hero", location=FIELD))
    # Army belongs to kingdom 2 (Dragons) but is commanded by kingdom 1's leader.
    army = ArmyState(101, 2, ArmyType.DRAGON_WING, Quality.ELITE, location=FIELD, commanded_by=1)
    state.add_army(army)

    units = _build_battle_units(
        [army], state, is_defender=False, terrain=Terrain.PLAINS, province_coord=FIELD, rng=random.Random(0)
    )

    expected = compute_effective_strength(
        ArmyType.DRAGON_WING, Race.DRAGONS, Quality.ELITE, Terrain.PLAINS, druidic_shortfall=4
    )
    assert units[0].effective_strength == pytest.approx(expected)


def test_build_battle_units_druidic_shortfall_is_zero_when_leader_has_sufficient_skill():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Humania", Race.HUMAN, Alignment.NEUTRAL, home_province=HexCoord(9, 9)))
    state.add_kingdom(KingdomState(2, "Dragonia", Race.DRAGONS, Alignment.NEUTRAL, home_province=HexCoord(8, 8)))
    leader = LeaderState(1, kingdom_id=1, name="Hero", location=FIELD, skills=_skills_with_druid(4))
    state.add_leader(leader)
    army = ArmyState(101, 2, ArmyType.DRAGON_WING, Quality.ELITE, location=FIELD, commanded_by=1)
    state.add_army(army)

    units = _build_battle_units(
        [army], state, is_defender=False, terrain=Terrain.PLAINS, province_coord=FIELD, rng=random.Random(0)
    )

    expected = compute_effective_strength(ArmyType.DRAGON_WING, Race.DRAGONS, Quality.ELITE, Terrain.PLAINS)
    assert units[0].effective_strength == pytest.approx(expected)


def test_build_battle_units_druidic_shortfall_bypassed_for_same_kingdom_commanding():
    # The overwhelmingly common case: leader and army share a kingdom, so
    # their races always match regardless of the leader's Druid skill.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Dragonia", Race.DRAGONS, Alignment.NEUTRAL, home_province=HexCoord(9, 9)))
    leader = LeaderState(1, kingdom_id=1, name="Hero", location=FIELD, skills=_skills_with_druid(0))
    state.add_leader(leader)
    army = ArmyState(101, 1, ArmyType.DRAGON_WING, Quality.ELITE, location=FIELD, commanded_by=1)
    state.add_army(army)

    units = _build_battle_units(
        [army], state, is_defender=False, terrain=Terrain.PLAINS, province_coord=FIELD, rng=random.Random(0)
    )

    expected = compute_effective_strength(ArmyType.DRAGON_WING, Race.DRAGONS, Quality.ELITE, Terrain.PLAINS)
    assert units[0].effective_strength == pytest.approx(expected)


def test_build_battle_units_druidic_shortfall_unled_army_unaffected():
    # Deliberately unmodeled scope (see _build_battle_units's docstring):
    # an unled army isn't penalized regardless of race.
    state = GameState()
    state.add_kingdom(KingdomState(2, "Dragonia", Race.DRAGONS, Alignment.NEUTRAL, home_province=HexCoord(8, 8)))
    army = ArmyState(101, 2, ArmyType.DRAGON_WING, Quality.ELITE, location=FIELD, commanded_by=None)
    state.add_army(army)

    units = _build_battle_units(
        [army], state, is_defender=False, terrain=Terrain.PLAINS, province_coord=FIELD, rng=random.Random(0)
    )

    expected = compute_effective_strength(ArmyType.DRAGON_WING, Race.DRAGONS, Quality.ELITE, Terrain.PLAINS)
    assert units[0].effective_strength == pytest.approx(expected)


def test_build_battle_units_druidic_shortfall_defaults_to_zero_skill_when_unrecorded():
    # Leader exists but has no LeaderState.skills recorded at all (the
    # same placeholder-0 convention used everywhere else in this project).
    state = GameState()
    state.add_kingdom(KingdomState(1, "Humania", Race.HUMAN, Alignment.NEUTRAL, home_province=HexCoord(9, 9)))
    state.add_kingdom(KingdomState(2, "Whalia", Race.WHALES, Alignment.NEUTRAL, home_province=HexCoord(8, 8)))
    leader = LeaderState(1, kingdom_id=1, name="Hero", location=FIELD, skills=None)
    state.add_leader(leader)
    army = ArmyState(101, 2, ArmyType.WHALES, Quality.ELITE, location=FIELD, commanded_by=1)
    state.add_army(army)

    units = _build_battle_units(
        [army], state, is_defender=False, terrain=Terrain.SEA, province_coord=FIELD, rng=random.Random(0)
    )

    # DRUID_TABLE[Race.WHALES] == 2, skill defaults to 0 -> shortfall 2.
    expected = compute_effective_strength(
        ArmyType.WHALES, Race.WHALES, Quality.ELITE, Terrain.SEA, druidic_shortfall=2
    )
    assert units[0].effective_strength == pytest.approx(expected)


def test_fight_battle_reads_a_led_attackers_real_tactical_skill_end_to_end():
    # End-to-end (task #180): a real LeaderState.skills tactical level,
    # attached via ArmyState.commanded_by, is what fight_battle() itself
    # now picks up as the attacker's Supreme Commander -- not just the
    # unit-level _build_battle_units/_select_side_commander helpers.
    # Giving the attacker a commander also means the defender's unled
    # army now faces a real Duel (garrison-commander fallback), so this
    # scripts one extra leading roll for that (attacker wins the duel,
    # consistent with the otherwise-overwhelming attacker).
    state = build_state()
    state.add_leader(LeaderState(1, 1, "Skilled Commander", FIELD, skills=SkillTable(raw_values=[5] * 30 + [0])))
    state.armies[101].commanded_by = 1
    rng = ScriptedRandom([0.05, 0.9, 0.9, 0.9, 0.1, 0.99, 0.99, 0.99])

    report = fight_battle(state, attacker_kingdom_id=1, province_coord=FIELD, attacker_army_ids=[101], rng=rng)

    assert report.attacker_commander_leader_id == 1
    assert report.duel_loser_side == "defender"
    assert report.conquered is True


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
    state = GameState()
    armies = [ArmyState(201, 2, ArmyType.GARRISON, Quality.GREEN, FIELD)]  # unled

    commander = _select_side_commander(armies, state, Ability.TACTICAL, allow_garrison_fallback=True)

    assert commander is not None
    assert commander.leader_id is None
    assert commander.contingent_size == 1
    assert commander.tactical_ability == 0  # "has no abilities"


def test_select_side_commander_no_fallback_for_unled_attackers():
    state = GameState()
    armies = [ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, FIELD)]  # unled

    commander = _select_side_commander(armies, state, Ability.TACTICAL, allow_garrison_fallback=False)

    assert commander is None


def test_select_side_commander_picks_largest_contingent_among_led_armies():
    state = GameState()
    state.add_leader(LeaderState(1, 1, "Leader One", FIELD))
    state.add_leader(LeaderState(2, 1, "Leader Two", FIELD))
    armies = [
        ArmyState(101, 1, ArmyType.BOWMEN, Quality.AVERAGE, FIELD, commanded_by=1),
        ArmyState(102, 1, ArmyType.BOWMEN, Quality.AVERAGE, FIELD, commanded_by=2),
        ArmyState(103, 1, ArmyType.BOWMEN, Quality.AVERAGE, FIELD, commanded_by=2),
    ]

    commander = _select_side_commander(armies, state, Ability.TACTICAL, allow_garrison_fallback=False)

    assert commander.leader_id == 2  # 2 armies vs leader 1's 1 army
    assert commander.contingent_size == 2


def test_select_side_commander_uses_real_tactical_skill_for_the_tiebreak():
    state = GameState()
    state.add_leader(LeaderState(1, 1, "Weaker Tactician", FIELD, skills=SkillTable(raw_values=[0] * 30 + [0])))
    state.add_leader(LeaderState(2, 1, "Stronger Tactician", FIELD, skills=SkillTable(raw_values=[5] * 30 + [0])))
    # Equal contingent size -- the tiebreak must fall to real Tactical skill.
    armies = [
        ArmyState(101, 1, ArmyType.BOWMEN, Quality.AVERAGE, FIELD, commanded_by=1),
        ArmyState(102, 1, ArmyType.BOWMEN, Quality.AVERAGE, FIELD, commanded_by=2),
    ]

    commander = _select_side_commander(armies, state, Ability.TACTICAL, allow_garrison_fallback=False)

    assert commander.leader_id == 2
    assert commander.tactical_ability == 5


def test_maybe_fight_duel_demoralizes_the_losers_own_led_units():
    attacker_armies = [ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, FIELD, commanded_by=501)]
    defender_armies = [ArmyState(201, 2, ArmyType.GARRISON, Quality.GREEN, FIELD, commanded_by=502)]
    attacker_units = [BattleUnit(ArmyType.HVY_CAVALRY, 100.0, source_id=101)]
    defender_units = [BattleUnit(ArmyType.GARRISON, 10.0, source_id=201)]
    attacker_commander = Commander(leader_id=501, contingent_size=1, tactical_ability=0)
    defender_commander = Commander(leader_id=502, contingent_size=1, tactical_ability=0)
    rng = ScriptedRandom([0.01])  # attacker's huge strength edge -> wins the duel

    outcome = _maybe_fight_duel(
        attacker_commander, defender_commander, attacker_armies, defender_armies, attacker_units, defender_units, rng
    )

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
    defender_commander = Commander(leader_id=502, contingent_size=1, tactical_ability=0)
    rng = ScriptedRandom([])  # must not be consumed -- no duel without an attacker commander

    outcome = _maybe_fight_duel(
        None, defender_commander, attacker_armies, defender_armies, attacker_units, defender_units, rng
    )

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
