from __future__ import annotations

import random

import pytest

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.discovery import Discovery
from ak_engine.models.enums import Ability
from ak_engine.models.game_state import ArmyState, GameState, KingdomState, LeaderState, ProvinceState
from ak_engine.models.kingdom import SkillTable
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.race import Race
from ak_engine.turn.battle_line import BattleUnit
from ak_engine.turn.battle_orchestrator import (
    MultiAttackerParty,
    _build_battle_units,
    _commander_combatant,
    _maybe_fight_duel,
    _record_battle_merit,
    _select_side_commander,
    fight_battle,
    fight_multi_attacker_battle,
)
from ak_engine.turn.battle_resolution import BattleResult
from ak_engine.turn.combat import Quality
from ak_engine.turn.duel import Commander, provincial_garrison_commander
from ak_engine.turn.encounter import CHARACTER_HIT_POINTS
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


# -- Phase 231: BattleReport.province_coord/attacker_kingdom_id/defender_kingdom_id --


def test_fight_battle_report_carries_the_provinces_own_battle_identity():
    state = build_state()
    rng = no_luck_overwhelming_attacker_rng()

    report = fight_battle(state, attacker_kingdom_id=1, province_coord=FIELD, attacker_army_ids=[101], rng=rng)

    assert report.province_coord == FIELD
    assert report.attacker_kingdom_id == 1
    assert report.defender_kingdom_id == 2


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


def test_fight_battle_records_a_clean_swept_defenders_death_in_the_graveyard():
    # Phase 60, Regolamento AK.txt [4.25.1]: Skeletal Army/Bless's
    # corpse-cleanup addendum both read GameState.battle_graveyard --
    # this confirms a genuine clean-swept battle death actually reaches it.
    state = build_state()
    rng = no_luck_overwhelming_attacker_rng()

    fight_battle(
        state, attacker_kingdom_id=1, province_coord=FIELD, attacker_army_ids=[101],
        loser_retreats=False, rng=rng,
    )

    entries = state.battle_graveyard[FIELD]
    assert len(entries) == 1
    assert entries[0].army_type is ArmyType.GARRISON
    assert entries[0].quality is Quality.GREEN
    assert entries[0].kingdom_id == 2


# -- Phase 250: Mystic Winds ends before army battle --


def _generously_padded_rng() -> ScriptedRandom:
    # Clearing happens before any of fight_battle()'s own rng consumption
    # starts, so these tests don't care about the battle's actual outcome --
    # just that the function runs to completion without exhausting the
    # script. 0.9 clears every documented trigger threshold in this
    # project (column/battle luck at 0.75/0.55, etc.), so nothing fires.
    return ScriptedRandom([0.9] * 30, choice_indices=[0] * 10)


def test_fight_battle_clears_mystic_winds_for_the_attacking_commander():
    state = build_state()
    state.add_leader(
        LeaderState(1, kingdom_id=1, name="Windwalker", location=FIELD, mystic_winds_active=True)
    )
    state.armies[101].commanded_by = 1

    fight_battle(state, attacker_kingdom_id=1, province_coord=FIELD, attacker_army_ids=[101], rng=_generously_padded_rng())

    assert state.leaders[1].mystic_winds_active is False


def test_fight_battle_clears_mystic_winds_for_the_defending_commander():
    state = build_state()
    state.add_leader(
        LeaderState(2, kingdom_id=2, name="Skyrider", location=FIELD, mystic_winds_active=True)
    )
    state.armies[201].commanded_by = 2

    fight_battle(state, attacker_kingdom_id=1, province_coord=FIELD, attacker_army_ids=[101], rng=_generously_padded_rng())

    assert state.leaders[2].mystic_winds_active is False


def test_fight_battle_leaves_an_uninvolved_leaders_mystic_winds_untouched():
    # Only leaders actually commanding an army *in this battle* get cleared --
    # a leader elsewhere in the kingdom keeps the flag until their own battle.
    state = build_state()
    state.add_leader(LeaderState(3, kingdom_id=1, name="Elsewhere", location=HexCoord(9, 9), mystic_winds_active=True))
    rng = no_luck_overwhelming_attacker_rng()

    fight_battle(state, attacker_kingdom_id=1, province_coord=FIELD, attacker_army_ids=[101], rng=rng)

    assert state.leaders[3].mystic_winds_active is True


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
    # Phase 60: a no-retreat-destination disband is also a real battle
    # death, recorded the same as an outright clean-swept elimination.
    assert state.battle_graveyard[FIELD][0].army_type is ArmyType.GARRISON


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


def test_fleet_in_a_sea_battle_honors_terrain_override():
    # Phase 168: a province Part Sea'd to Sea (terrain_override) must fight
    # as a real sea battle -- Fleet's land-only Depleted-instead-of-destroyed
    # carve-out must NOT apply -- even though its base terrain is still
    # Plains. Mirrors test_fleet_in_a_sea_battle_follows_ordinary_elimination_rules
    # above, but via the override instead of the base terrain field.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, HexCoord(0, 0)))
    state.add_kingdom(KingdomState(2, "Defendia", Race.HUMAN, Alignment.NEUTRAL, FIELD))
    state.add_province(ProvinceState(FIELD, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2, terrain_override=Terrain.SEA))
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


def test_build_battle_units_applies_exploration_advantage_to_every_unit_on_the_side():
    # Rulebook [6.3]: "the side with the better exploration... up to a 25%
    # advantage" -- Phase 69, turn/strength.py exploration_advantage_multiplier.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, home_province=HexCoord(9, 9)))
    army = ArmyState(101, 1, ArmyType.BOWMEN, Quality.AVERAGE, location=FIELD)
    state.add_army(army)

    units_no_advantage = _build_battle_units(
        [army], state, is_defender=False, terrain=Terrain.PLAINS, province_coord=FIELD, rng=random.Random(0)
    )
    units_with_advantage = _build_battle_units(
        [army],
        state,
        is_defender=False,
        terrain=Terrain.PLAINS,
        province_coord=FIELD,
        rng=random.Random(0),
        own_explored_percent=100,
        enemy_explored_percent=0,
    )

    assert units_with_advantage[0].effective_strength == pytest.approx(units_no_advantage[0].effective_strength * 1.25)


def _exploration_battle_state(*, attacker_explored: int) -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, home_province=HexCoord(9, 9)))
    state.add_kingdom(KingdomState(2, "Defendia", Race.HUMAN, Alignment.GOOD, home_province=FIELD))
    province = ProvinceState(FIELD, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2)
    if attacker_explored:
        province.explored_percent_by_kingdom[1] = attacker_explored
    state.add_province(province)
    state.add_army(ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, location=FIELD))
    state.add_army(ArmyState(201, 2, ArmyType.GARRISON, Quality.GREEN, location=FIELD))
    return state


def test_fight_battle_reads_real_per_kingdom_exploration_from_the_province():
    # Integration: fight_battle wires ProvinceState.explored_percent_by_kingdom
    # into _build_battle_units for both sides -- same rng seed, only the
    # attacker's own recorded exploration differs (100% vs never recorded),
    # so any strength difference is attributable to the new wiring alone.
    state_without_advantage = _exploration_battle_state(attacker_explored=0)
    state_with_advantage = _exploration_battle_state(attacker_explored=100)

    report_without = fight_battle(state_without_advantage, 1, FIELD, [101], rng=random.Random(3))
    report_with = fight_battle(state_with_advantage, 1, FIELD, [101], rng=random.Random(3))

    assert report_with.battle_result.columns[0].attacker_strength == pytest.approx(
        report_without.battle_result.columns[0].attacker_strength * 1.25
    )


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


def test_build_battle_units_applies_the_commanders_phantasmal_armies_level():
    # Phase 59, Regolamento AK.txt [4.23.2]: +15%/level of the *caster*
    # (stored on the commanding LeaderState by cast_execution.py's
    # _execute_illus_armies), applied to every army that leader commands.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Illusia", Race.HUMAN, Alignment.NEUTRAL, home_province=HexCoord(9, 9)))
    state.add_leader(LeaderState(1, kingdom_id=1, name="Illusionist", location=FIELD, phantasmal_armies_level=2))
    army = ArmyState(101, 1, ArmyType.LEGION, Quality.AVERAGE, location=FIELD, commanded_by=1)
    state.add_army(army)

    units = _build_battle_units(
        [army], state, is_defender=False, terrain=Terrain.PLAINS, province_coord=FIELD, rng=random.Random(0)
    )

    expected = compute_effective_strength(
        ArmyType.LEGION, Race.HUMAN, Quality.AVERAGE, Terrain.PLAINS, phantasmal_armies_level=2
    )
    assert units[0].effective_strength == pytest.approx(expected)


def test_build_battle_units_unled_army_gets_no_phantasmal_armies_bonus():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Illusia", Race.HUMAN, Alignment.NEUTRAL, home_province=HexCoord(9, 9)))
    army = ArmyState(101, 1, ArmyType.LEGION, Quality.AVERAGE, location=FIELD)  # commanded_by=None
    state.add_army(army)

    units = _build_battle_units(
        [army], state, is_defender=False, terrain=Terrain.PLAINS, province_coord=FIELD, rng=random.Random(0)
    )

    expected = compute_effective_strength(ArmyType.LEGION, Race.HUMAN, Quality.AVERAGE, Terrain.PLAINS)
    assert units[0].effective_strength == pytest.approx(expected)


def test_build_battle_units_halves_air_unit_strength_in_illusory_fog():
    # Phase 249: Dragon Wing is a static OVERFLIGHT_AIR member -- halved in any
    # province with ProvinceState.illusory_fog_active, no Mystic Winds needed.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Draconia", Race.DRAGONS, Alignment.NEUTRAL, home_province=HexCoord(9, 9)))
    state.add_province(ProvinceState(FIELD, Terrain.PLAINS, Race.DRAGONS, illusory_fog_active=True))
    army = ArmyState(101, 1, ArmyType.DRAGON_WING, Quality.AVERAGE, location=FIELD)
    state.add_army(army)

    units = _build_battle_units(
        [army], state, is_defender=False, terrain=Terrain.PLAINS, province_coord=FIELD, rng=random.Random(0)
    )

    expected = compute_effective_strength(
        ArmyType.DRAGON_WING, Race.DRAGONS, Quality.AVERAGE, Terrain.PLAINS, illusory_fog_affected=True
    )
    assert units[0].effective_strength == pytest.approx(expected)


def test_build_battle_units_illusory_fog_does_not_affect_ground_units():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Humania", Race.HUMAN, Alignment.NEUTRAL, home_province=HexCoord(9, 9)))
    state.add_province(ProvinceState(FIELD, Terrain.PLAINS, Race.HUMAN, illusory_fog_active=True))
    army = ArmyState(101, 1, ArmyType.LEGION, Quality.AVERAGE, location=FIELD)
    state.add_army(army)

    units = _build_battle_units(
        [army], state, is_defender=False, terrain=Terrain.PLAINS, province_coord=FIELD, rng=random.Random(0)
    )

    expected = compute_effective_strength(ArmyType.LEGION, Race.HUMAN, Quality.AVERAGE, Terrain.PLAINS)
    assert units[0].effective_strength == pytest.approx(expected)


def test_build_battle_units_illusory_fog_halves_a_mystic_winds_led_ground_unit():
    # "...and those affected by 'Mystic Winds' Spell..." -- a Legion led by a
    # Mystic-Winds-active commander counts as an air unit for this purpose.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Humania", Race.HUMAN, Alignment.NEUTRAL, home_province=HexCoord(9, 9)))
    state.add_province(ProvinceState(FIELD, Terrain.PLAINS, Race.HUMAN, illusory_fog_active=True))
    state.add_leader(LeaderState(1, kingdom_id=1, name="Windrider", location=FIELD, mystic_winds_active=True))
    army = ArmyState(101, 1, ArmyType.LEGION, Quality.AVERAGE, location=FIELD, commanded_by=1)
    state.add_army(army)

    units = _build_battle_units(
        [army], state, is_defender=False, terrain=Terrain.PLAINS, province_coord=FIELD, rng=random.Random(0)
    )

    expected = compute_effective_strength(
        ArmyType.LEGION, Race.HUMAN, Quality.AVERAGE, Terrain.PLAINS, illusory_fog_affected=True
    )
    assert units[0].effective_strength == pytest.approx(expected)


def test_build_battle_units_no_fog_effect_when_province_not_fogged():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Draconia", Race.DRAGONS, Alignment.NEUTRAL, home_province=HexCoord(9, 9)))
    state.add_province(ProvinceState(FIELD, Terrain.PLAINS, Race.DRAGONS))  # illusory_fog_active defaults False
    army = ArmyState(101, 1, ArmyType.DRAGON_WING, Quality.AVERAGE, location=FIELD)
    state.add_army(army)

    units = _build_battle_units(
        [army], state, is_defender=False, terrain=Terrain.PLAINS, province_coord=FIELD, rng=random.Random(0)
    )

    expected = compute_effective_strength(ArmyType.DRAGON_WING, Race.DRAGONS, Quality.AVERAGE, Terrain.PLAINS)
    assert units[0].effective_strength == pytest.approx(expected)


def test_build_battle_units_marks_an_overflight_unit_rear_targeting_blocked_when_shortfall_is_positive():
    # Phase 43: same scenario as the test above (Dragon Wing shortfall of
    # 4) -- an overflight-type unit with a real shortfall also gets
    # BattleUnit.druidic_rear_targeting_blocked=True.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Humania", Race.HUMAN, Alignment.NEUTRAL, home_province=HexCoord(9, 9)))
    state.add_kingdom(KingdomState(2, "Dragonia", Race.DRAGONS, Alignment.NEUTRAL, home_province=HexCoord(8, 8)))
    state.add_leader(LeaderState(1, kingdom_id=1, name="Hero", location=FIELD))
    army = ArmyState(101, 2, ArmyType.DRAGON_WING, Quality.ELITE, location=FIELD, commanded_by=1)
    state.add_army(army)

    units = _build_battle_units(
        [army], state, is_defender=False, terrain=Terrain.PLAINS, province_coord=FIELD, rng=random.Random(0)
    )

    assert units[0].druidic_rear_targeting_blocked is True


def test_build_battle_units_rear_targeting_flag_false_when_shortfall_is_zero():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Dragonia", Race.DRAGONS, Alignment.NEUTRAL, home_province=HexCoord(9, 9)))
    leader = LeaderState(1, kingdom_id=1, name="Hero", location=FIELD, skills=_skills_with_druid(4))
    state.add_leader(leader)
    army = ArmyState(101, 1, ArmyType.DRAGON_WING, Quality.ELITE, location=FIELD, commanded_by=1)
    state.add_army(army)

    units = _build_battle_units(
        [army], state, is_defender=False, terrain=Terrain.PLAINS, province_coord=FIELD, rng=random.Random(0)
    )

    assert units[0].druidic_rear_targeting_blocked is False


def test_build_battle_units_rear_targeting_flag_never_set_for_a_non_overflight_unit():
    # A ground unit with a real Druidic shortfall still isn't "held back
    # from rear-targeting" -- that carve-out is specifically about the
    # rulebook's overflight ("non-human") rear-targeting rule, which
    # never applied to Bowmen in the first place.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Humania", Race.HUMAN, Alignment.NEUTRAL, home_province=HexCoord(9, 9)))
    state.add_kingdom(KingdomState(2, "Dragonia", Race.DRAGONS, Alignment.NEUTRAL, home_province=HexCoord(8, 8)))
    state.add_leader(LeaderState(1, kingdom_id=1, name="Hero", location=FIELD))
    army = ArmyState(101, 2, ArmyType.BOWMEN, Quality.ELITE, location=FIELD, commanded_by=1)
    state.add_army(army)

    units = _build_battle_units(
        [army], state, is_defender=False, terrain=Terrain.PLAINS, province_coord=FIELD, rng=random.Random(0)
    )

    assert units[0].druidic_rear_targeting_blocked is False


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


def test_build_battle_units_druidic_shortfall_unled_army_falls_back_to_zero_when_province_unregistered():
    # No ProvinceState registered for FIELD at all -> _king_druidic_shortfall_for
    # can't resolve an owning kingdom, so no King-substitution penalty applies
    # (insufficient data, not a guessed one -- see _king_druidic_shortfall_for).
    state = GameState()
    state.add_kingdom(KingdomState(2, "Dragonia", Race.DRAGONS, Alignment.NEUTRAL, home_province=HexCoord(8, 8)))
    army = ArmyState(101, 2, ArmyType.DRAGON_WING, Quality.ELITE, location=FIELD, commanded_by=None)
    state.add_army(army)

    units = _build_battle_units(
        [army], state, is_defender=False, terrain=Terrain.PLAINS, province_coord=FIELD, rng=random.Random(0)
    )

    expected = compute_effective_strength(ArmyType.DRAGON_WING, Race.DRAGONS, Quality.ELITE, Terrain.PLAINS)
    assert units[0].effective_strength == pytest.approx(expected)


def test_build_battle_units_druidic_shortfall_unled_army_falls_back_to_zero_when_province_unowned():
    # A registered province with no owner_kingdom_id at all -- same "no
    # King to resolve" fallback as the unregistered-province case above.
    state = GameState()
    state.add_kingdom(KingdomState(2, "Dragonia", Race.DRAGONS, Alignment.NEUTRAL, home_province=HexCoord(8, 8)))
    state.add_province(ProvinceState(FIELD, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=None))
    army = ArmyState(101, 2, ArmyType.DRAGON_WING, Quality.ELITE, location=FIELD, commanded_by=None)
    state.add_army(army)

    units = _build_battle_units(
        [army], state, is_defender=False, terrain=Terrain.PLAINS, province_coord=FIELD, rng=random.Random(0)
    )

    expected = compute_effective_strength(ArmyType.DRAGON_WING, Race.DRAGONS, Quality.ELITE, Terrain.PLAINS)
    assert units[0].effective_strength == pytest.approx(expected)


def test_build_battle_units_druidic_shortfall_unled_army_falls_back_to_zero_when_no_king_identified():
    # The owning kingdom exists and has a leader, but nobody is flagged
    # is_king -- same "insufficient data" fallback, not a guess at who
    # the King might be.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Humania", Race.HUMAN, Alignment.NEUTRAL, home_province=HexCoord(9, 9)))
    state.add_kingdom(KingdomState(2, "Dragonia", Race.DRAGONS, Alignment.NEUTRAL, home_province=HexCoord(8, 8)))
    state.add_province(ProvinceState(FIELD, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_leader(LeaderState(1, kingdom_id=1, name="Not The King", location=FIELD, is_king=False))
    army = ArmyState(101, 2, ArmyType.DRAGON_WING, Quality.ELITE, location=FIELD, commanded_by=None)
    state.add_army(army)

    units = _build_battle_units(
        [army], state, is_defender=False, terrain=Terrain.PLAINS, province_coord=FIELD, rng=random.Random(0)
    )

    expected = compute_effective_strength(ArmyType.DRAGON_WING, Race.DRAGONS, Quality.ELITE, Terrain.PLAINS)
    assert units[0].effective_strength == pytest.approx(expected)


def test_build_battle_units_druidic_shortfall_unled_army_uses_the_provinces_owning_kings_druidic_skill():
    # Rulebook [4.32] garrison-commander carve-out: an unled Dragon-race
    # army defending in Humania's own province is judged against
    # Humania's King -- a different kingdom entirely from the army's own
    # (Dragonia), which is the point: it's the *province owner's* King,
    # not the army's own kingdom, that matters here.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Humania", Race.HUMAN, Alignment.NEUTRAL, home_province=HexCoord(9, 9)))
    state.add_kingdom(KingdomState(2, "Dragonia", Race.DRAGONS, Alignment.NEUTRAL, home_province=HexCoord(8, 8)))
    state.add_province(ProvinceState(FIELD, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_leader(LeaderState(1, kingdom_id=1, name="The King", location=HexCoord(9, 9), is_king=True))
    army = ArmyState(101, 2, ArmyType.DRAGON_WING, Quality.ELITE, location=FIELD, commanded_by=None)
    state.add_army(army)

    units = _build_battle_units(
        [army], state, is_defender=False, terrain=Terrain.PLAINS, province_coord=FIELD, rng=random.Random(0)
    )

    # King's Druidic skill unrecorded (skills=None) -> defaults to 0;
    # DRUID_TABLE[Race.DRAGONS] == 4 -> full shortfall of 4.
    expected = compute_effective_strength(
        ArmyType.DRAGON_WING, Race.DRAGONS, Quality.ELITE, Terrain.PLAINS, druidic_shortfall=4
    )
    assert units[0].effective_strength == pytest.approx(expected)
    # Phase 43: the King-substitution shortfall feeds the same
    # rear-targeting-blocked flag as the led-army path, with no extra
    # wiring -- an unled overflight army held back by its province's own
    # King's insufficient Druidic ability is "held back" too.
    assert units[0].druidic_rear_targeting_blocked is True


def test_build_battle_units_druidic_shortfall_unled_army_same_race_as_king_needs_no_check():
    # The unled army's own race (via its own kingdom_id) happens to match
    # the province-owning King's race -- no shortfall regardless of the
    # King's actual Druidic skill, same same-race bypass as the led case.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Humania", Race.HUMAN, Alignment.NEUTRAL, home_province=HexCoord(9, 9)))
    state.add_province(ProvinceState(FIELD, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_leader(LeaderState(1, kingdom_id=1, name="The King", location=HexCoord(9, 9), is_king=True))
    army = ArmyState(101, 1, ArmyType.BOWMEN, Quality.AVERAGE, location=FIELD, commanded_by=None)
    state.add_army(army)

    units = _build_battle_units(
        [army], state, is_defender=False, terrain=Terrain.PLAINS, province_coord=FIELD, rng=random.Random(0)
    )

    expected = compute_effective_strength(ArmyType.BOWMEN, Race.HUMAN, Quality.AVERAGE, Terrain.PLAINS)
    assert units[0].effective_strength == pytest.approx(expected)


def test_build_battle_units_druidic_shortfall_unled_army_uses_kings_sufficient_skill():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Humania", Race.HUMAN, Alignment.NEUTRAL, home_province=HexCoord(9, 9)))
    state.add_kingdom(KingdomState(2, "Trollia", Race.TROLLISH, Alignment.NEUTRAL, home_province=HexCoord(8, 8)))
    state.add_province(ProvinceState(FIELD, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_leader(
        LeaderState(1, kingdom_id=1, name="The King", location=HexCoord(9, 9), is_king=True, skills=_skills_with_druid(2))
    )
    army = ArmyState(101, 2, ArmyType.TROLLS, Quality.ELITE, location=FIELD, commanded_by=None)
    state.add_army(army)

    units = _build_battle_units(
        [army], state, is_defender=False, terrain=Terrain.PLAINS, province_coord=FIELD, rng=random.Random(0)
    )

    # DRUID_TABLE[Race.TROLLISH] == 2, King's skill == 2 -> no shortfall.
    expected = compute_effective_strength(ArmyType.TROLLS, Race.TROLLISH, Quality.ELITE, Terrain.PLAINS)
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
    # Phase 60: a pursuit kill is also a real battle death.
    assert state.battle_graveyard[FIELD][0].army_type is ArmyType.GARRISON


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


def test_select_side_commander_reads_the_discovery_ability_bonus():
    # Phase 269: LAND_SHIP raises a Kingdom's own Tactical ability by 1 --
    # equal stored skill, so the tiebreak must fall to the leader whose
    # kingdom owns the Discovery.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Inventia", Race.HUMAN, Alignment.GOOD, FIELD))
    state.add_kingdom(KingdomState(2, "Plain Old Kingdom", Race.HUMAN, Alignment.GOOD, FIELD))
    state.kingdoms[1].discoveries.add(Discovery.LAND_SHIP)
    state.add_leader(LeaderState(1, 1, "Inventor's Tactician", FIELD, skills=_skills_with(Ability.TACTICAL, 3, 0)))
    state.add_leader(LeaderState(2, 2, "Plain Tactician", FIELD, skills=_skills_with(Ability.TACTICAL, 3, 0)))
    armies = [
        ArmyState(101, 1, ArmyType.BOWMEN, Quality.AVERAGE, FIELD, commanded_by=1),
        ArmyState(102, 2, ArmyType.BOWMEN, Quality.AVERAGE, FIELD, commanded_by=2),
    ]

    commander = _select_side_commander(armies, state, Ability.TACTICAL, allow_garrison_fallback=False)

    assert commander.leader_id == 1
    assert commander.tactical_ability == 4


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


# --- Real Melee duel combat (Phase 49, opt-in via use_real_duel_combat) --


def _skills_with(ability: Ability, skill: int, aptitude: int) -> SkillTable:
    raw = [0] * 30
    raw[ability.value * 2] = skill
    raw[ability.value * 2 + 1] = aptitude
    return SkillTable(raw)


def test_commander_combatant_reads_real_melee_skill_and_neutral_bonus():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Neutralia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_leader(
        LeaderState(501, kingdom_id=1, name="Commander", location=FIELD, skills=_skills_with(Ability.MELEE, 2, 9))
    )
    commander = Commander(leader_id=501, contingent_size=1, tactical_ability=0)

    combatant = _commander_combatant(commander, state)

    assert combatant.melee_skill == 2
    assert combatant.neutral_duelist_bonus is True
    assert combatant.hit_points == CHARACTER_HIT_POINTS


def test_commander_combatant_non_neutral_kingdom_gets_no_bonus():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Goodia", Race.HUMAN, Alignment.GOOD, HexCoord(0, 0)))
    state.add_leader(
        LeaderState(501, kingdom_id=1, name="Commander", location=FIELD, skills=_skills_with(Ability.MELEE, 2, 9))
    )
    commander = Commander(leader_id=501, contingent_size=1, tactical_ability=0)

    combatant = _commander_combatant(commander, state)

    assert combatant.neutral_duelist_bonus is False


def test_commander_combatant_defaults_skill_to_zero_when_unrecorded():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.GOOD, HexCoord(0, 0)))
    state.add_leader(LeaderState(501, kingdom_id=1, name="Commander", location=FIELD))  # skills=None
    commander = Commander(leader_id=501, contingent_size=1, tactical_ability=0)

    combatant = _commander_combatant(commander, state)

    assert combatant.melee_skill == 0


def test_commander_combatant_garrison_commander_has_no_skill_or_bonus():
    state = GameState()
    commander = provincial_garrison_commander(contingent_size=3)

    combatant = _commander_combatant(commander, state)

    assert combatant.melee_skill == 0
    assert combatant.neutral_duelist_bonus is False
    assert combatant.hit_points == CHARACTER_HIT_POINTS


def test_maybe_fight_duel_real_combat_decisive_winner_demoralizes_loser_not_kills_it():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, FIELD))
    state.add_kingdom(KingdomState(2, "Defendia", Race.HUMAN, Alignment.GOOD, FIELD))
    state.add_leader(
        LeaderState(501, kingdom_id=1, name="A", location=FIELD, skills=_skills_with(Ability.MELEE, 3, 9))
    )
    state.add_leader(
        LeaderState(502, kingdom_id=2, name="B", location=FIELD, skills=_skills_with(Ability.MELEE, 0, 9))
    )
    attacker_armies = [ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, FIELD, commanded_by=501)]
    defender_armies = [ArmyState(201, 2, ArmyType.GARRISON, Quality.GREEN, FIELD, commanded_by=502)]
    attacker_units = [BattleUnit(ArmyType.HVY_CAVALRY, 100.0, source_id=101)]
    defender_units = [BattleUnit(ArmyType.GARRISON, 10.0, source_id=201)]
    attacker_commander = Commander(leader_id=501, contingent_size=1, tactical_ability=0)
    defender_commander = Commander(leader_id=502, contingent_size=1, tactical_ability=0)
    # A(melee 3) always acts first over B(melee 0) -- no initiative roll
    # needed. Scripted so A always hits, B always misses.
    rng = ScriptedRandom([0.1, 0.5, 0.9] * 15)

    outcome = _maybe_fight_duel(
        attacker_commander, defender_commander, attacker_armies, defender_armies, attacker_units, defender_units, rng,
        state=state, use_real_duel_combat=True,
    )

    assert outcome.loser_side == "defender"
    assert defender_units[0].effective_strength == 10.0 * 0.75  # DUEL_DEMORALIZATION_MULTIPLIER
    assert attacker_units[0].effective_strength == 100.0
    # Rulebook [7.1]: only the loser's armies are demoralized -- the
    # losing commander himself is never killed, unlike the generic
    # Encounter combat rule this reuses under the hood.
    assert 502 in state.leaders


def test_maybe_fight_duel_real_combat_works_with_a_garrison_commander_defender():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, FIELD))
    state.add_leader(
        LeaderState(501, kingdom_id=1, name="A", location=FIELD, skills=_skills_with(Ability.MELEE, 3, 9))
    )
    attacker_armies = [ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, FIELD, commanded_by=501)]
    defender_armies = [ArmyState(201, 2, ArmyType.GARRISON, Quality.GREEN, FIELD)]  # unled
    attacker_units = [BattleUnit(ArmyType.HVY_CAVALRY, 100.0, source_id=101)]
    defender_units = [BattleUnit(ArmyType.GARRISON, 10.0, source_id=201)]
    attacker_commander = Commander(leader_id=501, contingent_size=1, tactical_ability=0)
    defender_commander = provincial_garrison_commander(contingent_size=1)
    rng = ScriptedRandom([0.1, 0.5, 0.9] * 15)

    outcome = _maybe_fight_duel(
        attacker_commander, defender_commander, attacker_armies, defender_armies, attacker_units, defender_units, rng,
        state=state, use_real_duel_combat=True,
    )

    assert outcome.loser_side == "defender"
    assert defender_units[0].effective_strength == 10.0 * 0.75


def test_maybe_fight_duel_real_combat_requires_state_or_falls_back_to_approximation():
    # use_real_duel_combat=True without a state given can't build
    # Combatants -- falls back to the strength-ratio approximation
    # rather than raising.
    attacker_armies = [ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, FIELD, commanded_by=501)]
    defender_armies = [ArmyState(201, 2, ArmyType.GARRISON, Quality.GREEN, FIELD, commanded_by=502)]
    attacker_units = [BattleUnit(ArmyType.HVY_CAVALRY, 100.0, source_id=101)]
    defender_units = [BattleUnit(ArmyType.GARRISON, 10.0, source_id=201)]
    attacker_commander = Commander(leader_id=501, contingent_size=1, tactical_ability=0)
    defender_commander = Commander(leader_id=502, contingent_size=1, tactical_ability=0)
    rng = ScriptedRandom([0.01])  # a single roll -- only valid for the approximation path

    outcome = _maybe_fight_duel(
        attacker_commander, defender_commander, attacker_armies, defender_armies, attacker_units, defender_units, rng,
        use_real_duel_combat=True,  # state defaults to None
    )

    assert outcome.loser_side == "defender"  # attacker's huge strength edge wins the approximation


def test_fight_battle_with_real_duel_combat_reports_a_loser_side():
    state = build_state()
    state.armies[101].commanded_by = 501
    state.armies[201].commanded_by = 502
    state.add_leader(
        LeaderState(501, kingdom_id=1, name="A", location=FIELD, skills=_skills_with(Ability.MELEE, 3, 9))
    )
    state.add_leader(
        LeaderState(502, kingdom_id=2, name="B", location=FIELD, skills=_skills_with(Ability.MELEE, 0, 9))
    )
    # Duel: A always hits, B always misses -- exactly 5 rolls to a
    # decisive 2-round kill with this scripted sequence (round 1: A's
    # hit-check + damage roll, B's miss-check; round 2: A's hit-check +
    # damage roll finishes B off, whose own swing is skipped since he's
    # already dead) -- confirmed empirically, not padded, so the
    # remaining values line up exactly with resolve_battle's own
    # luck/win rolls afterward. Then the usual no-luck-overwhelming
    # sequence.
    rng = ScriptedRandom([0.1, 0.5, 0.9, 0.1, 0.5] + [0.9, 0.9, 0.9, 0.1, 0.99, 0.99, 0.99])

    report = fight_battle(
        state, attacker_kingdom_id=1, province_coord=FIELD, attacker_army_ids=[101], rng=rng,
        use_real_duel_combat=True,
    )

    assert report.attacker_commander_leader_id == 501
    assert report.defender_commander_leader_id == 502
    assert report.duel_loser_side == "defender"


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

    battles = fight_multi_attacker_battle(state, FIELD, parties, rng=rng)

    assert len(battles) == 1
    assert sorted(battles[0].leader_ids) == [10, 20]  # both leaders united into the same battle
    report = battles[0].report
    all_ids = {
        *report.destroyed_army_ids,
        *report.retreated_army_ids,
        *report.disbanded_army_ids,
        *report.mercenary_army_ids,
        *report.pursuit_destroyed_army_ids,
        *report.quality_changes.keys(),
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

    battles = fight_multi_attacker_battle(state, FIELD, parties, rng=rng)

    assert len(battles) == 2
    assert sorted(battle.leader_ids[0] for battle in battles) == [10, 20]  # each fought its own battle


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

    battles = fight_multi_attacker_battle(state, FIELD, parties, rng=rng)

    assert len(battles) == 1
    assert sorted(battles[0].leader_ids) == [10, 20]
    if battles[0].report.conquered:
        assert state.provinces[FIELD].owner_kingdom_id == 3  # kingdom 3 contributed 2 of 3 armies


def test_fight_multi_attacker_battle_second_separate_group_claims_an_already_cleared_province():
    # Phase 73: previously, once the first separate group cleanly swept
    # the lone weak defender, the second group's own fight_battle() call
    # would raise ValueError against the now-empty defender list.
    state = build_state()  # weak GARRISON/GREEN defender, overwhelming HVY_CAVALRY/ELITE attacker
    state.add_army(ArmyState(102, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, FIELD))
    parties = [
        MultiAttackerParty(leader_id=10, kingdom_id=1, army_ids=[101], origin_province=HexCoord(5, 5)),
        MultiAttackerParty(leader_id=20, kingdom_id=1, army_ids=[102], origin_province=HexCoord(9, 9)),
    ]
    # 0.99 >= DIFFERENT_ORIGIN_UNITE_CHANCE (0.30) -> stays split into two
    # separate battles; the first group's own overwhelming, no-luck rolls
    # (same shape as no_luck_overwhelming_attacker_rng()) clean-sweep the
    # lone defender before the second group's own turn.
    rng = ScriptedRandom([0.99, 0.9, 0.9, 0.9, 0.1, 0.99, 0.99, 0.99])

    battles = fight_multi_attacker_battle(state, FIELD, parties, rng=rng)

    assert len(battles) == 2
    first_battle, second_battle = battles
    assert first_battle.leader_ids == [10]
    assert first_battle.report.conquered is True
    # The second group finds nothing left to fight -- treated as an
    # uncontested claim rather than raising.
    assert second_battle.leader_ids == [20]
    assert second_battle.report.conquered is True
    assert second_battle.report.battle_result.winner == "attacker"


# --- Merit Point battle-outcome recording (rulebook page 51, Phase 254) ---


def _merit_state() -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, HexCoord(0, 0)))
    state.add_kingdom(KingdomState(2, "Defendia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(9, 9)))
    state.add_leader(LeaderState(1, 1, "Attacker Commander", FIELD))
    state.add_leader(LeaderState(2, 2, "Defender Commander", FIELD))
    return state


def test_record_battle_merit_credits_winning_land_commander_and_debits_losing_one():
    state = _merit_state()

    _record_battle_merit(
        state, Terrain.PLAINS, BattleResult(winner="attacker"), 1, 2, attacker_unit_count=3, defender_unit_count=5
    )

    assert state.leaders[1].merit_tally.land_battles_won_enemy_units == 5
    assert state.leaders[2].merit_tally.land_battles_lost_own_units == 5
    assert state.leaders[1].merit_tally.land_battles_lost_own_units == 0
    assert state.leaders[2].merit_tally.land_battles_won_enemy_units == 0


def test_record_battle_merit_credits_winning_naval_commander():
    state = _merit_state()

    _record_battle_merit(
        state, Terrain.SEA, BattleResult(winner="defender"), 1, 2, attacker_unit_count=4, defender_unit_count=2
    )

    assert state.leaders[2].merit_tally.naval_battles_won_enemy_units == 4
    assert state.leaders[1].merit_tally.naval_battles_lost_own_units == 4
    # Naval and land counters are kept fully separate.
    assert state.leaders[2].merit_tally.land_battles_won_enemy_units == 0


def test_record_battle_merit_records_nothing_for_a_tie():
    state = _merit_state()

    _record_battle_merit(
        state, Terrain.PLAINS, BattleResult(winner="tie"), 1, 2, attacker_unit_count=3, defender_unit_count=5
    )

    assert state.leaders[1].merit_tally.land_battles_won_enemy_units == 0
    assert state.leaders[2].merit_tally.land_battles_lost_own_units == 0


def test_record_battle_merit_skips_an_unled_winning_side():
    state = _merit_state()

    # The winning side (defender) has no commander (garrison fallback,
    # leader_id=None) -- no one to credit -- but the losing side (attacker,
    # leader 1) is still a real "battaglia comandata" for its own leader.
    _record_battle_merit(
        state, Terrain.PLAINS, BattleResult(winner="defender"), 1, None, attacker_unit_count=3, defender_unit_count=5
    )

    assert state.leaders[1].merit_tally.land_battles_lost_own_units == 3
    assert state.leaders[1].merit_tally.land_battles_won_enemy_units == 0


def test_record_battle_merit_skips_an_unled_losing_side():
    state = _merit_state()

    # The losing side (defender) has no commander -- nothing to debit --
    # but the winning side (attacker, leader 1) still earns its credit.
    _record_battle_merit(
        state, Terrain.PLAINS, BattleResult(winner="attacker"), 1, None, attacker_unit_count=3, defender_unit_count=5
    )

    assert state.leaders[1].merit_tally.land_battles_won_enemy_units == 5
    assert state.leaders[1].merit_tally.land_battles_lost_own_units == 0


def test_fight_battle_wires_merit_points_for_a_led_winning_attacker():
    # Same fixture/rng shape as
    # test_fight_battle_reads_a_led_attackers_real_tactical_skill_end_to_end:
    # attacker leader 1 wins outright, defender falls back to an unled
    # garrison commander (leader_id=None) -- only the attacker's own
    # commander has a real leader to credit.
    state = build_state()
    state.add_leader(LeaderState(1, 1, "Skilled Commander", FIELD, skills=SkillTable(raw_values=[5] * 30 + [0])))
    state.armies[101].commanded_by = 1
    rng = ScriptedRandom([0.05, 0.9, 0.9, 0.9, 0.1, 0.99, 0.99, 0.99])

    fight_battle(state, attacker_kingdom_id=1, province_coord=FIELD, attacker_army_ids=[101], rng=rng)

    assert state.leaders[1].merit_tally.land_battles_won_enemy_units == 1  # the lone defending army (201)
    assert state.leaders[1].merit_tally.land_battles_lost_own_units == 0
