from __future__ import annotations

import random
from unittest.mock import patch

import pytest

from ak_engine.models.advanced_ability import AdvancedAbility
from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.discovery import Discovery
from ak_engine.models.enums import Ability, Maneuver, Spell
from ak_engine.models.feature import Feature, FeatureType
from ak_engine.models.game_state import ArmyState, GameState, KingdomState, LeaderState, ProvinceState, RaceTitleTally
from ak_engine.models.kingdom import SkillTable
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.monster import Monster
from ak_engine.models.race import Race
from ak_engine.models.temper import Temper
from ak_engine.models.treasure import Treasure
from ak_engine.turn.battle_line import BattleUnit
from ak_engine.turn.aftermath import FORMATION_DIVISOR
from ak_engine.turn.battle_orchestrator import (
    MONSTER_SUMMONING_INVASION_DEFECTION_CHANCE,
    MONSTER_SUMMONING_PLAYER_LED_DEFECTION_CHANCE,
    MultiAttackerParty,
    _apply_monster_summoning_aid,
    _apply_werebeast_bites,
    _apply_wingman_merit,
    _build_battle_units,
    _column_bres_by_army_id,
    _commander_combatant,
    _direct_destruction_probabilities,
    _formation_divisors,
    _maybe_fight_duel,
    _record_battle_merit,
    _select_side_commander,
    _side_has_present_leader_with_ability,
    fight_battle,
    fight_multi_attacker_battle,
)
from ak_engine.turn.battle_resolution import BattleColumnResult, BattleResult
from ak_engine.turn.combat import Quality
from ak_engine.turn.duel import Commander, provincial_garrison_commander
from ak_engine.turn.encounter import CHARACTER_HIT_POINTS
from ak_engine.turn.movement import NORMAL_MAP_BOUNDS, MapBounds
from ak_engine.turn.search_decode import SearchTactic
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
    # Phase 296: the leading 0.9 accounts for fight_battle()'s own new
    # roll_terrain_line_length_cap() call, right before resolve_battle()
    # -- ScriptedRandom overrides .random(), which flips CPython's own
    # randint()/randrange() over to the _randbelow_without_getrandbits()
    # path (consumes exactly one .random() draw for these small ranges,
    # not the real bit-generator) -- see that phase's own README note.
    # The rolled cap itself never matters here (Plains' own 5-10 range
    # always exceeds every test army's own line_length), only that one
    # extra draw is consumed before the next real one.
    return ScriptedRandom(
        [0.9, 0.9, 0.9, 0.9, win_roll, pursuit_attempt_roll, winner_quality_roll, loser_quality_roll]
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


# -- Phase 409: attacker forced-retreat destination + ProvinceState.contested_from_coord --


def test_attacker_forced_retreat_uses_the_origin_when_supplied():
    # Rulebook [7.4]: "If the attacker was forced to retreat, his armies
    # must retreat into the same province they invaded from." seed=1 is a
    # decisive defender win (GREEN attacker vs. ELITE defender) found by
    # search -- deterministic under real_random.Random(1).
    origin = HexCoord(0, 1)
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, origin))
    state.add_kingdom(KingdomState(2, "Defendia", Race.HUMAN, Alignment.NEUTRAL, DEFENDER_HOME))
    state.add_province(ProvinceState(FIELD, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2))
    state.add_province(ProvinceState(origin, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_province(ProvinceState(DEFENDER_HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2))
    # Pre-set as if this were a forced rebattle continuing an earlier
    # contest, to also verify a clean sweep clears both fields.
    state.provinces[FIELD].contested_by_kingdom_id = 1
    state.provinces[FIELD].contested_from_coord = origin
    state.add_army(ArmyState(101, 1, ArmyType.GARRISON, Quality.GREEN, FIELD))
    state.add_army(ArmyState(201, 2, ArmyType.HVY_CAVALRY, Quality.ELITE, FIELD))

    report = fight_battle(
        state, attacker_kingdom_id=1, province_coord=FIELD, attacker_army_ids=[101],
        attacker_origin=origin, rng=random.Random(1),
    )

    assert 101 in report.retreated_army_ids
    assert state.armies[101].location == origin
    assert state.provinces[FIELD].contested_by_kingdom_id is None
    assert state.provinces[FIELD].contested_from_coord is None


def test_fight_battle_records_contested_from_coord_on_a_mixed_result():
    # seed=32 is a genuine mixed/contested result (neither side clean
    # swept) found by search for this 3-vs-3 multi-type battle -- see
    # ProvinceState.contested_from_coord's own docstring for why this
    # needs persisting (a later forced rebattle has no other way to learn
    # the original invasion origin).
    origin = HexCoord(0, 1)
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, origin))
    state.add_kingdom(KingdomState(2, "Defendia", Race.HUMAN, Alignment.NEUTRAL, DEFENDER_HOME))
    state.add_province(ProvinceState(FIELD, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2))
    state.add_province(ProvinceState(origin, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_province(ProvinceState(DEFENDER_HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2))
    state.add_army(ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.AVERAGE, FIELD))
    state.add_army(ArmyState(102, 1, ArmyType.BOWMEN, Quality.AVERAGE, FIELD))
    state.add_army(ArmyState(103, 1, ArmyType.GARRISON, Quality.AVERAGE, FIELD))
    state.add_army(ArmyState(201, 2, ArmyType.HVY_CAVALRY, Quality.AVERAGE, FIELD))
    state.add_army(ArmyState(202, 2, ArmyType.BOWMEN, Quality.AVERAGE, FIELD))
    state.add_army(ArmyState(203, 2, ArmyType.GARRISON, Quality.AVERAGE, FIELD))

    fight_battle(
        state, attacker_kingdom_id=1, province_coord=FIELD, attacker_army_ids=[101, 102, 103],
        attacker_origin=origin, rng=random.Random(32),
    )

    assert state.provinces[FIELD].contested_by_kingdom_id == 1
    assert state.provinces[FIELD].contested_from_coord == origin


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
    # Phase 296: leading 0.9 accounts for the new terrain-line-length-cap
    # roll -- see no_luck_overwhelming_attacker_rng()'s own Phase 296 note.
    rng = ScriptedRandom([0.9, 0.9, 0.9, 0.9, 0.5, 0.99, 0.99])

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


def test_fight_battle_reads_province_is_island_into_strength():
    # Integration: fight_battle wires ProvinceState.is_island (Phase 282)
    # into _build_battle_units for both sides -- same rng seed, only the
    # province's own is_island flag differs, so any strength difference
    # is attributable to the new wiring alone. HVY_CAVALRY: base 4, home
    # Plains (+1) = 5 on land; adverse Sea (/2) = 2 -- island averages to
    # 3.5, genuinely different from the ordinary 5.
    state_ordinary = build_state()
    state_island = build_state()
    state_island.provinces[FIELD].is_island = True

    report_ordinary = fight_battle(state_ordinary, attacker_kingdom_id=1, province_coord=FIELD, attacker_army_ids=[101], rng=random.Random(3))
    report_island = fight_battle(state_island, attacker_kingdom_id=1, province_coord=FIELD, attacker_army_ids=[101], rng=random.Random(3))

    assert report_island.battle_result.columns[0].attacker_strength == pytest.approx(
        report_ordinary.battle_result.columns[0].attacker_strength * 3.5 / 5
    )


def test_build_battle_units_applies_is_island_blend():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, home_province=HexCoord(9, 9)))
    army = ArmyState(101, 1, ArmyType.PHALANX, Quality.AVERAGE, location=FIELD)
    state.add_army(army)

    ordinary = _build_battle_units(
        [army], state, is_defender=False, terrain=Terrain.PLAINS, province_coord=FIELD, rng=random.Random(0)
    )
    island = _build_battle_units(
        [army], state, is_defender=False, terrain=Terrain.PLAINS, province_coord=FIELD, rng=random.Random(0),
        is_island=True,
    )

    assert island[0].effective_strength != ordinary[0].effective_strength
    assert island[0].effective_strength == compute_effective_strength(
        ArmyType.PHALANX, Race.HUMAN, Quality.AVERAGE, Terrain.PLAINS, is_island=True
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


# -- Phase 511: Find Water --------------------------------------------


def test_build_battle_units_find_water_suppresses_desert_penalty():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.NEUTRAL, home_province=HexCoord(9, 9)))
    bowmen = ArmyState(101, 1, ArmyType.BOWMEN, Quality.AVERAGE, location=FIELD)
    state.add_army(bowmen)

    without_find_water = _build_battle_units(
        [bowmen], state, is_defender=False, terrain=Terrain.DESERT, province_coord=FIELD, rng=random.Random(0)
    )
    with_find_water = _build_battle_units(
        [bowmen], state, is_defender=False, terrain=Terrain.DESERT, province_coord=FIELD, rng=random.Random(0),
        explorer_find_water=True,
    )

    # Same "no penalty" result as a present Camel Corps -- no thirst
    # penalty at all with Find Water, matching a doubled strength vs the
    # penalized baseline.
    assert with_find_water[0].effective_strength == pytest.approx(without_find_water[0].effective_strength * 2)


def test_build_battle_units_find_water_no_effect_outside_desert():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.NEUTRAL, home_province=HexCoord(9, 9)))
    bowmen = ArmyState(101, 1, ArmyType.BOWMEN, Quality.AVERAGE, location=FIELD)
    state.add_army(bowmen)

    without_find_water = _build_battle_units(
        [bowmen], state, is_defender=False, terrain=Terrain.PLAINS, province_coord=FIELD, rng=random.Random(0)
    )
    with_find_water = _build_battle_units(
        [bowmen], state, is_defender=False, terrain=Terrain.PLAINS, province_coord=FIELD, rng=random.Random(0),
        explorer_find_water=True,
    )

    assert with_find_water[0].effective_strength == without_find_water[0].effective_strength


def test_side_has_present_leader_with_ability_true_when_present_and_qualified():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.NEUTRAL, home_province=HexCoord(9, 9)))
    leader = LeaderState(1, kingdom_id=1, name="Scout", location=FIELD)
    leader.advanced_abilities.add(AdvancedAbility.EXPLORER_FIND_WATER)
    state.add_leader(leader)

    assert _side_has_present_leader_with_ability(
        state, FIELD, frozenset({1}), AdvancedAbility.EXPLORER_FIND_WATER
    )


def test_side_has_present_leader_with_ability_false_when_elsewhere():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.NEUTRAL, home_province=HexCoord(9, 9)))
    leader = LeaderState(1, kingdom_id=1, name="Scout", location=HexCoord(5, 5))
    leader.advanced_abilities.add(AdvancedAbility.EXPLORER_FIND_WATER)
    state.add_leader(leader)

    assert not _side_has_present_leader_with_ability(
        state, FIELD, frozenset({1}), AdvancedAbility.EXPLORER_FIND_WATER
    )


def test_side_has_present_leader_with_ability_false_for_a_different_kingdom():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.NEUTRAL, home_province=HexCoord(9, 9)))
    leader = LeaderState(1, kingdom_id=2, name="Scout", location=FIELD)
    leader.advanced_abilities.add(AdvancedAbility.EXPLORER_FIND_WATER)
    state.add_leader(leader)

    assert not _side_has_present_leader_with_ability(
        state, FIELD, frozenset({1}), AdvancedAbility.EXPLORER_FIND_WATER
    )


def test_side_has_present_leader_with_ability_false_without_the_ability():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.NEUTRAL, home_province=HexCoord(9, 9)))
    leader = LeaderState(1, kingdom_id=1, name="Scout", location=FIELD)
    state.add_leader(leader)

    assert not _side_has_present_leader_with_ability(
        state, FIELD, frozenset({1}), AdvancedAbility.EXPLORER_FIND_WATER
    )


def test_fight_battle_find_water_present_leader_removes_desert_penalty():
    # Integration: attacker has no Camel Corps but a present Explorer
    # with Find Water; defender is unaffected (no such leader). Compares
    # against an identical battle minus the ability, holding the RNG
    # seed fixed so the only difference is the ability's own effect.
    def make_state():
        state = GameState()
        state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.NEUTRAL, home_province=HexCoord(9, 9)))
        state.add_kingdom(KingdomState(2, "Defendia", Race.HUMAN, Alignment.NEUTRAL, home_province=HexCoord(8, 8)))
        state.add_province(ProvinceState(FIELD, Terrain.DESERT, Race.HUMAN, owner_kingdom_id=2))
        state.add_army(ArmyState(101, 1, ArmyType.BOWMEN, Quality.AVERAGE, location=FIELD))
        state.add_army(ArmyState(201, 2, ArmyType.BOWMEN, Quality.AVERAGE, location=FIELD))
        return state

    without_ability = make_state()
    report_without = fight_battle(without_ability, 1, FIELD, [101], rng=random.Random(0))

    with_ability = make_state()
    scout = LeaderState(1, kingdom_id=1, name="Scout", location=FIELD)
    scout.advanced_abilities.add(AdvancedAbility.EXPLORER_FIND_WATER)
    with_ability.add_leader(scout)
    report_with = fight_battle(with_ability, 1, FIELD, [101], rng=random.Random(0))

    # Both battles are otherwise identical (same seed, same armies) -- the
    # attacker's own column strength doubles (2.0 -> 4.0) once the Desert
    # penalty is removed, flipping that column's own BRES from a tie
    # (attacker_won=False) to a clear attacker win.
    assert report_without.battle_result.columns[0].attacker_strength == pytest.approx(2.0)
    assert report_with.battle_result.columns[0].attacker_strength == pytest.approx(4.0)
    assert report_without.battle_result.columns[0].attacker_won is False
    assert report_with.battle_result.columns[0].attacker_won is True


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


# -- Title-based fanaticism (Phase 390) -----------------------------------


def _human_king_state() -> tuple[GameState, ArmyState]:
    state = GameState()
    state.turn_number = 4  # HUMAN_KING's own turn gate (RACE_TITLE_TURN_GATE)
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.NEUTRAL, home_province=HexCoord(9, 9)))
    king = LeaderState(
        501, kingdom_id=1, name="King", location=FIELD, race=Race.HUMAN, is_king=True,
        race_title_tally={Race.HUMAN: RaceTitleTally(front_line_battles_won_points=10)},
    )
    state.add_leader(king)
    army = ArmyState(101, 1, ArmyType.BOWMEN, Quality.AVERAGE, location=FIELD, commanded_by=501)
    state.add_army(army)
    return state, army


def test_build_battle_units_title_fanaticism_rolls_the_office_perk_descriptions_own_20_percent():
    # Cross-confirmed independently by OFFICE_PERK_DESCRIPTION[Office.
    # HUMAN_KING] == "20% Human Fanaticism" (Phase 103). Alignment.NEUTRAL
    # has no alignment-fanaticism chance (0%), so the first roll_
    # fanaticism() draw always happens but never succeeds -- only then
    # does the title check consume a second draw.
    state, army = _human_king_state()

    succeeds = _build_battle_units(
        [army], state, is_defender=False, terrain=Terrain.PLAINS, province_coord=FIELD,
        rng=ScriptedRandom([0.99, 0.1]), apply_fanaticism=True,
    )
    fails = _build_battle_units(
        [army], state, is_defender=False, terrain=Terrain.PLAINS, province_coord=FIELD,
        rng=ScriptedRandom([0.99, 0.9]), apply_fanaticism=True,
    )

    fanatical_strength = compute_effective_strength(
        ArmyType.BOWMEN, Race.HUMAN, Quality.AVERAGE, Terrain.PLAINS, is_fanatical=True
    )
    baseline = compute_effective_strength(ArmyType.BOWMEN, Race.HUMAN, Quality.AVERAGE, Terrain.PLAINS)
    assert succeeds[0].effective_strength == fanatical_strength
    assert fails[0].effective_strength == baseline


def test_build_battle_units_title_fanaticism_never_rolled_for_an_unled_army():
    state, army = _human_king_state()
    army.commanded_by = None
    rng = ScriptedRandom([0.99])  # only the alignment draw -- a second draw raises IndexError

    units = _build_battle_units(
        [army], state, is_defender=False, terrain=Terrain.PLAINS, province_coord=FIELD, rng=rng, apply_fanaticism=True,
    )

    baseline = compute_effective_strength(ArmyType.BOWMEN, Race.HUMAN, Quality.AVERAGE, Terrain.PLAINS)
    assert units[0].effective_strength == baseline


def test_build_battle_units_title_fanaticism_never_rolled_when_the_commander_isnt_the_title_holder():
    state, army = _human_king_state()
    army.commanded_by = 999  # some other leader, not the HUMAN_KING title holder
    rng = ScriptedRandom([0.99])  # only the alignment draw

    units = _build_battle_units(
        [army], state, is_defender=False, terrain=Terrain.PLAINS, province_coord=FIELD, rng=rng, apply_fanaticism=True,
    )

    baseline = compute_effective_strength(ArmyType.BOWMEN, Race.HUMAN, Quality.AVERAGE, Terrain.PLAINS)
    assert units[0].effective_strength == baseline


def test_build_battle_units_title_fanaticism_off_by_default_never_touches_a_second_rng_draw():
    state, army = _human_king_state()
    rng = ScriptedRandom([0.99])  # apply_fanaticism defaults False -- no draw at all

    units = _build_battle_units(
        [army], state, is_defender=False, terrain=Terrain.PLAINS, province_coord=FIELD, rng=rng,
    )

    baseline = compute_effective_strength(ArmyType.BOWMEN, Race.HUMAN, Quality.AVERAGE, Terrain.PLAINS)
    assert units[0].effective_strength == baseline


# -- Duellist / "Captain of the Musketeers" (Phase 471) --------------------


def test_build_battle_units_duellist_side_off_by_default_leaves_the_field_none():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, home_province=HexCoord(9, 9)))
    army = ArmyState(101, 1, ArmyType.BOWMEN, Quality.AVERAGE, location=FIELD)
    state.add_army(army)
    rng = ScriptedRandom([])

    units = _build_battle_units([army], state, is_defender=False, terrain=Terrain.PLAINS, province_coord=FIELD, rng=rng)

    assert units[0].duellist_bonus_if_selected is None


def test_build_battle_units_duellist_side_sets_the_exact_fanatic_delta():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, home_province=HexCoord(9, 9)))
    army = ArmyState(101, 1, ArmyType.BOWMEN, Quality.AVERAGE, location=FIELD)
    state.add_army(army)
    rng = ScriptedRandom([])

    units = _build_battle_units(
        [army], state, is_defender=False, terrain=Terrain.PLAINS, province_coord=FIELD, rng=rng, duellist_side=True,
    )

    baseline = compute_effective_strength(ArmyType.BOWMEN, Race.HUMAN, Quality.AVERAGE, Terrain.PLAINS)
    fanatical = compute_effective_strength(
        ArmyType.BOWMEN, Race.HUMAN, Quality.AVERAGE, Terrain.PLAINS, is_fanatical=True
    )
    assert units[0].effective_strength == baseline
    assert units[0].duellist_bonus_if_selected == fanatical - baseline
    assert units[0].duellist_bonus_if_selected > 0


def test_build_battle_units_duellist_side_delta_is_zero_when_already_fanatical():
    # apply_fanaticism's own alignment roll already made this unit
    # fanatical -- forcing is_fanatical=True a second time (for the
    # Duellist delta) changes nothing, so the real, computed delta is
    # exactly 0.0 -- SS17.7's own "non si accumulano più incrementi di
    # qualità sulla stessa concessione", for free.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, home_province=HexCoord(9, 9)))
    army = ArmyState(101, 1, ArmyType.BOWMEN, Quality.AVERAGE, location=FIELD)
    state.add_army(army)
    rng = ScriptedRandom([0.1])  # succeeds the 40% Alignment.GOOD roll

    units = _build_battle_units(
        [army], state, is_defender=False, terrain=Terrain.PLAINS, province_coord=FIELD, rng=rng,
        apply_fanaticism=True, duellist_side=True,
    )

    fanatical = compute_effective_strength(
        ArmyType.BOWMEN, Race.HUMAN, Quality.AVERAGE, Terrain.PLAINS, is_fanatical=True
    )
    assert units[0].effective_strength == fanatical
    assert units[0].duellist_bonus_if_selected == 0.0


def test_fight_battle_wires_duellist_side_into_the_titleholders_own_commanded_side():
    state = build_state()
    leader = LeaderState(501, kingdom_id=1, name="Duellist", location=FIELD, is_king=True)
    leader.merit_tally.duel_merit_net = 5  # meets OFFICE_MIN_POINTS[Office.DUELLIST]
    state.add_leader(leader)
    state.armies[101].commanded_by = 501
    battle_result = BattleResult(columns=[], winner="attacker", total_bres=1)

    with patch("ak_engine.turn.battle_orchestrator.resolve_battle", return_value=battle_result) as mock_resolve:
        fight_battle(
            state, attacker_kingdom_id=1, province_coord=FIELD, attacker_army_ids=[101],
            rng=_generously_padded_rng(),
        )

    attacker_units, defender_units = mock_resolve.call_args.args[0], mock_resolve.call_args.args[1]
    assert all(u.duellist_bonus_if_selected is not None for u in attacker_units)
    assert all(u.duellist_bonus_if_selected is None for u in defender_units)


def test_fight_battle_grants_no_duellist_bonus_when_neither_side_is_commanded_by_the_titleholder():
    state = build_state()
    battle_result = BattleResult(columns=[], winner="attacker", total_bres=1)

    with patch("ak_engine.turn.battle_orchestrator.resolve_battle", return_value=battle_result) as mock_resolve:
        fight_battle(
            state, attacker_kingdom_id=1, province_coord=FIELD, attacker_army_ids=[101],
            rng=_generously_padded_rng(),
        )

    attacker_units, defender_units = mock_resolve.call_args.args[0], mock_resolve.call_args.args[1]
    assert all(u.duellist_bonus_if_selected is None for u in attacker_units)
    assert all(u.duellist_bonus_if_selected is None for u in defender_units)


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
    # Phase 298: the same shortfall also flags this unit for aftermath.py's
    # own led_by_insufficient_druid quality-improve-chance penalty.
    assert units[0].led_by_insufficient_druid is True


def test_build_battle_units_race_item_bonus_boosts_a_matching_led_army():
    # Phase 285: the same +1 legendary-leadership-item bonus the ARMIES
    # report's own "Modified Quality" column has computed since Phase 279
    # (turn/army_quality.py) now also reaches real combat strength.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Humania", Race.HUMAN, Alignment.NEUTRAL, home_province=HexCoord(9, 9)))
    state.add_leader(LeaderState(1, kingdom_id=1, name="Hero", location=FIELD))
    state.add_item(Treasure.LEADERSHIP_HUMAN, owner_leader_id=1)
    army = ArmyState(101, 1, ArmyType.BOWMEN, Quality.AVERAGE, location=FIELD, commanded_by=1)
    state.add_army(army)

    units = _build_battle_units(
        [army], state, is_defender=False, terrain=Terrain.PLAINS, province_coord=FIELD, rng=random.Random(0)
    )

    expected = compute_effective_strength(ArmyType.BOWMEN, Race.HUMAN, Quality.AVERAGE, Terrain.PLAINS, race_item_bonus=1)
    assert units[0].effective_strength == pytest.approx(expected)


def test_build_battle_units_race_item_bonus_requires_the_item_to_match_the_armys_own_race():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Humania", Race.HUMAN, Alignment.NEUTRAL, home_province=HexCoord(9, 9)))
    state.add_leader(LeaderState(1, kingdom_id=1, name="Hero", location=FIELD))
    state.add_item(Treasure.LEADERSHIP_ELVEN, owner_leader_id=1)  # wrong race's item
    army = ArmyState(101, 1, ArmyType.BOWMEN, Quality.AVERAGE, location=FIELD, commanded_by=1)
    state.add_army(army)

    units = _build_battle_units(
        [army], state, is_defender=False, terrain=Terrain.PLAINS, province_coord=FIELD, rng=random.Random(0)
    )

    expected = compute_effective_strength(ArmyType.BOWMEN, Race.HUMAN, Quality.AVERAGE, Terrain.PLAINS)
    assert units[0].effective_strength == pytest.approx(expected)


def test_build_battle_units_race_item_bonus_not_applied_to_an_unled_army():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Humania", Race.HUMAN, Alignment.NEUTRAL, home_province=HexCoord(9, 9)))
    state.add_leader(LeaderState(1, kingdom_id=1, name="Hero", location=FIELD))
    state.add_item(Treasure.LEADERSHIP_HUMAN, owner_leader_id=1)
    army = ArmyState(101, 1, ArmyType.BOWMEN, Quality.AVERAGE, location=FIELD)  # commanded_by=None
    state.add_army(army)

    units = _build_battle_units(
        [army], state, is_defender=False, terrain=Terrain.PLAINS, province_coord=FIELD, rng=random.Random(0)
    )

    expected = compute_effective_strength(ArmyType.BOWMEN, Race.HUMAN, Quality.AVERAGE, Terrain.PLAINS)
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


def test_build_battle_units_observation_balloons_reduces_the_phantasmal_bonus():
    # Phase 270: Observation Balloons (Discovery.txt) -- an opposing
    # Kingdom that owns it reduces Phantasmal Armies' own bonus from
    # 15%/level to 5%/level for this battle.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Illusia", Race.HUMAN, Alignment.NEUTRAL, home_province=HexCoord(9, 9)))
    state.add_kingdom(KingdomState(2, "Balloonia", Race.HUMAN, Alignment.NEUTRAL, home_province=HexCoord(8, 8)))
    state.kingdoms[2].discoveries.add(Discovery.OBSERVATION_BALLOONS)
    state.add_leader(LeaderState(1, kingdom_id=1, name="Illusionist", location=FIELD, phantasmal_armies_level=2))
    army = ArmyState(101, 1, ArmyType.LEGION, Quality.AVERAGE, location=FIELD, commanded_by=1)
    state.add_army(army)

    units = _build_battle_units(
        [army], state, is_defender=False, terrain=Terrain.PLAINS, province_coord=FIELD, rng=random.Random(0),
        opponent_kingdom_ids=frozenset({2}),
    )

    expected = compute_effective_strength(
        ArmyType.LEGION, Race.HUMAN, Quality.AVERAGE, Terrain.PLAINS,
        phantasmal_armies_level=2, phantasmal_armies_bonus_per_level=0.05,
    )
    assert units[0].effective_strength == pytest.approx(expected)


def test_build_battle_units_osteopathic_germ_warfare_downgrades_skeletal_quality():
    # Phase 270: Osteopathic Germ Warfare (Discovery.txt) -- an opposing
    # Kingdom that owns it reduces a Skeletal Army unit by one quality
    # level in this battle, before strength is computed.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Necropolis", Race.HUMAN, Alignment.EVIL, home_province=HexCoord(9, 9)))
    state.add_kingdom(KingdomState(2, "Osteopathia", Race.HUMAN, Alignment.NEUTRAL, home_province=HexCoord(8, 8)))
    state.kingdoms[2].discoveries.add(Discovery.OSTEOPATHIC_GERM_WARFARE)
    army = ArmyState(101, 1, ArmyType.LEGION, Quality.AVERAGE, location=FIELD, is_skeletal=True)
    state.add_army(army)

    units = _build_battle_units(
        [army], state, is_defender=False, terrain=Terrain.PLAINS, province_coord=FIELD, rng=random.Random(0),
        opponent_kingdom_ids=frozenset({2}),
    )

    expected = compute_effective_strength(ArmyType.LEGION, Race.HUMAN, Quality.GREEN, Terrain.PLAINS)
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
    # No ProvinceState registered for FIELD at all -> king_druidic_shortfall_for
    # can't resolve an owning kingdom, so no King-substitution penalty applies
    # (insufficient data, not a guessed one -- see king_druidic_shortfall_for).
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
    # Phase 296: extra 0.9 right after the duel roll accounts for the new
    # terrain-line-length-cap roll (consumed after the duel, before the
    # 3 luck rolls) -- see no_luck_overwhelming_attacker_rng()'s own note.
    rng = ScriptedRandom([0.05, 0.9, 0.9, 0.9, 0.9, 0.1, 0.99, 0.99, 0.99])

    report = fight_battle(state, attacker_kingdom_id=1, province_coord=FIELD, attacker_army_ids=[101], rng=rng)

    assert report.attacker_commander_leader_id == 1
    assert report.duel_loser_side == "defender"
    assert report.conquered is True


# --- Pursuit (rulebook [7.3]) -------------------------------------------


def test_pursuit_destroys_a_caught_retreating_army():
    state = build_state()
    # 3 luck, win_roll (decisive attacker win), pursuit-attempt (0.1 < the
    # 75% cavalry chance -> the winning HVY_CAVALRY attempts pursuit),
    # Phase 349: pursuit's own random_multiplier_each_unit draw (any
    # value -- the pursuer already overwhelms the target so r_p
    # saturates the destruction curve regardless), pursuit-standstill
    # (0.1 -> destroys the far-weaker retreating GARRISON/GREEN target),
    # attacker's own winner_quality_roll. The defender never reaches
    # _retreat_or_disband at all, so no further rolls are consumed.
    # Phase 296: leading 0.9 accounts for the new terrain-line-length-cap
    # roll -- see no_luck_overwhelming_attacker_rng()'s own Phase 296 note.
    rng = ScriptedRandom([0.9, 0.9, 0.9, 0.9, 0.1, 0.1, 0.1, 0.1, 0.99])

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


def test_commander_combatant_reads_real_temper():
    # Phase 284: the Temper Table's own melee mechanics need each
    # combatant's real Temper threaded through -- LeaderState.temper has
    # existed since Phase 82, only the wiring here was missing.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Braveland", Race.HUMAN, Alignment.GOOD, HexCoord(0, 0)))
    state.add_leader(LeaderState(501, kingdom_id=1, name="Commander", location=FIELD, temper=Temper.BRAVE))
    commander = Commander(leader_id=501, contingent_size=1, tactical_ability=0)

    combatant = _commander_combatant(commander, state)

    assert combatant.temper is Temper.BRAVE


def test_commander_combatant_garrison_commander_has_no_temper():
    state = GameState()
    commander = provincial_garrison_commander(contingent_size=3)

    combatant = _commander_combatant(commander, state)

    assert combatant.temper is None


def test_commander_combatant_reads_real_archery_skill():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Archeria", Race.HUMAN, Alignment.GOOD, HexCoord(0, 0)))
    state.add_leader(
        LeaderState(501, kingdom_id=1, name="Commander", location=FIELD, skills=_skills_with(Ability.ARCHERY, 4, 9))
    )
    commander = Commander(leader_id=501, contingent_size=1, tactical_ability=0)

    combatant = _commander_combatant(commander, state)

    assert combatant.archery_skill == 4


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


def test_commander_combatant_gives_the_imperial_defender_a_damage_reduction_of_one():
    # Phase 489: CARICHE E ABLITA.txt's own Office.DEFENDER perk ("reduce
    # any strike against you in personal combat ... by one damage point").
    state = GameState()
    state.add_kingdom(KingdomState(1, "Braveland", Race.HUMAN, Alignment.GOOD, HexCoord(0, 0)))
    leader = LeaderState(501, kingdom_id=1, name="Commander", location=FIELD)
    leader.merit_tally.monster_hp_defeated = 1  # meets OFFICE_MIN_POINTS[Office.DEFENDER]
    state.add_leader(leader)
    commander = Commander(leader_id=501, contingent_size=1, tactical_ability=0)

    combatant = _commander_combatant(commander, state)

    assert combatant.damage_reduction == 1


def test_commander_combatant_garrison_commander_has_no_damage_reduction():
    state = GameState()
    commander = provincial_garrison_commander(contingent_size=3)

    combatant = _commander_combatant(commander, state)

    assert combatant.damage_reduction == 0


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


# -- Fire Arrow (Phase 273): duel_maneuvers, opt-in Special Encounter Plan --
# (the "no duel_maneuvers given -> always Melee, unchanged" default is
# already exercised by every real-combat duel test above, none of which
# pass duel_maneuvers -- and the full suite's own non-breaking check
# confirmed their behavior/RNG consumption is unaffected.)


def test_maybe_fight_duel_resolves_fire_arrow_first_when_duel_maneuvers_given():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, FIELD))
    state.add_kingdom(KingdomState(2, "Defendia", Race.HUMAN, Alignment.GOOD, FIELD))
    state.add_leader(
        LeaderState(501, kingdom_id=1, name="A", location=FIELD, skills=_skills_with(Ability.ARCHERY, 10, 9))
    )
    state.add_leader(
        LeaderState(502, kingdom_id=2, name="B", location=FIELD, skills=_skills_with(Ability.MELEE, 9, 9))
    )
    attacker_armies = [ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, FIELD, commanded_by=501)]
    defender_armies = [ArmyState(201, 2, ArmyType.GARRISON, Quality.GREEN, FIELD, commanded_by=502)]
    attacker_units = [BattleUnit(ArmyType.HVY_CAVALRY, 100.0, source_id=101)]
    defender_units = [BattleUnit(ArmyType.GARRISON, 10.0, source_id=201)]
    attacker_commander = Commander(leader_id=501, contingent_size=1, tactical_ability=0)
    defender_commander = Commander(leader_id=502, contingent_size=1, tactical_ability=0)
    # Same reasoning as challenge_execution.py's own Phase 273 test: A's 10
    # guaranteed archery hits (minimum 1 damage each) always total at least
    # 10, guaranteeing B's death via Fire Arrow alone even though B's own
    # Melee skill (9) would otherwise dominate a Melee-only duel.
    rng = ScriptedRandom([0.01] * 25)

    outcome = _maybe_fight_duel(
        attacker_commander, defender_commander, attacker_armies, defender_armies, attacker_units, defender_units, rng,
        state=state, use_real_duel_combat=True, duel_maneuvers=[Maneuver.SHOOT],
    )

    assert outcome.loser_side == "defender"


# -- Personal-Combat spells (Phase 291): duel_maneuvers may carry a CAST SearchTactic --


def test_maybe_fight_duel_cast_charm_success_is_read_as_no_duel_occurring():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, FIELD))
    state.add_kingdom(KingdomState(2, "Defendia", Race.HUMAN, Alignment.GOOD, FIELD))
    state.add_leader(
        LeaderState(501, kingdom_id=1, name="A", location=FIELD, skills=_skills_with(Ability.PSYCHIC, 5, 9))
    )
    state.add_leader(LeaderState(502, kingdom_id=2, name="B", location=FIELD))
    attacker_armies = [ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, FIELD, commanded_by=501)]
    defender_armies = [ArmyState(201, 2, ArmyType.GARRISON, Quality.GREEN, FIELD, commanded_by=502)]
    attacker_units = [BattleUnit(ArmyType.HVY_CAVALRY, 100.0, source_id=101)]
    defender_units = [BattleUnit(ArmyType.GARRISON, 10.0, source_id=201)]
    attacker_commander = Commander(leader_id=501, contingent_size=1, tactical_ability=0)
    defender_commander = Commander(leader_id=502, contingent_size=1, tactical_ability=0)
    rng = ScriptedRandom([0.1])  # the cast's own success roll -- Charm needs no further roll

    outcome = _maybe_fight_duel(
        attacker_commander, defender_commander, attacker_armies, defender_armies, attacker_units, defender_units, rng,
        state=state, use_real_duel_combat=True,
        duel_maneuvers=[SearchTactic(Maneuver.CAST, Spell.CHARM.value)],
    )

    assert outcome.loser_side is None
    assert defender_units[0].effective_strength == 10.0
    assert attacker_units[0].effective_strength == 100.0


# -- Maneuver.FLEE as the attacker's own first tactic (Phase 389) --------


def test_maybe_fight_duel_flee_as_first_tactic_always_escapes_no_rng_consumed():
    attacker_armies = [ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, FIELD, commanded_by=501)]
    defender_armies = [ArmyState(201, 2, ArmyType.GARRISON, Quality.GREEN, FIELD, commanded_by=502)]
    attacker_units = [BattleUnit(ArmyType.HVY_CAVALRY, 100.0, source_id=101)]
    defender_units = [BattleUnit(ArmyType.GARRISON, 10.0, source_id=201)]
    attacker_commander = Commander(leader_id=501, contingent_size=1, tactical_ability=0)
    defender_commander = Commander(leader_id=502, contingent_size=1, tactical_ability=0)
    rng = ScriptedRandom([])  # a guaranteed escape -- no roll, no combat resolved

    outcome = _maybe_fight_duel(
        attacker_commander, defender_commander, attacker_armies, defender_armies, attacker_units, defender_units, rng,
        duel_maneuvers=[Maneuver.FLEE],
    )

    assert outcome.attacker_commander_leader_id == 501
    assert outcome.defender_commander_leader_id == 502
    assert outcome.loser_side == "attacker"
    assert attacker_units[0].effective_strength == 100.0 * 0.75  # DUEL_DEMORALIZATION_MULTIPLIER
    assert defender_units[0].effective_strength == 10.0  # untouched -- attacker never landed a blow


def test_maybe_fight_duel_flee_as_a_searchtactic_wrapper_is_also_honored():
    attacker_armies = [ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, FIELD, commanded_by=501)]
    defender_armies = [ArmyState(201, 2, ArmyType.GARRISON, Quality.GREEN, FIELD, commanded_by=502)]
    attacker_units = [BattleUnit(ArmyType.HVY_CAVALRY, 100.0, source_id=101)]
    defender_units = [BattleUnit(ArmyType.GARRISON, 10.0, source_id=201)]
    attacker_commander = Commander(leader_id=501, contingent_size=1, tactical_ability=0)
    defender_commander = Commander(leader_id=502, contingent_size=1, tactical_ability=0)
    rng = ScriptedRandom([])

    outcome = _maybe_fight_duel(
        attacker_commander, defender_commander, attacker_armies, defender_armies, attacker_units, defender_units, rng,
        duel_maneuvers=[SearchTactic(Maneuver.FLEE)],
    )

    assert outcome.loser_side == "attacker"


def test_maybe_fight_duel_flee_only_matters_as_the_first_tactic():
    # A later Flee "attempts combat first" per AKGEN -- but this
    # project has no standing Special Encounter Plan source to know a
    # tactic list's real ordering intent beyond "first entry", so a
    # non-first FLEE is simply not special-cased at all and falls
    # through to the ordinary (approximated) duel resolution.
    attacker_armies = [ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, FIELD, commanded_by=501)]
    defender_armies = [ArmyState(201, 2, ArmyType.GARRISON, Quality.GREEN, FIELD, commanded_by=502)]
    attacker_units = [BattleUnit(ArmyType.HVY_CAVALRY, 100.0, source_id=101)]
    defender_units = [BattleUnit(ArmyType.GARRISON, 10.0, source_id=201)]
    attacker_commander = Commander(leader_id=501, contingent_size=1, tactical_ability=0)
    defender_commander = Commander(leader_id=502, contingent_size=1, tactical_ability=0)
    rng = ScriptedRandom([0.01])  # attacker's huge strength edge -> wins the approximated duel

    outcome = _maybe_fight_duel(
        attacker_commander, defender_commander, attacker_armies, defender_armies, attacker_units, defender_units, rng,
        duel_maneuvers=[Maneuver.MELEE, Maneuver.FLEE],
    )

    assert outcome.loser_side == "defender"


def test_maybe_fight_duel_cast_fireball_kill_demoralizes_the_loser():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, FIELD))
    state.add_kingdom(KingdomState(2, "Defendia", Race.HUMAN, Alignment.GOOD, FIELD))
    state.add_leader(
        LeaderState(501, kingdom_id=1, name="A", location=FIELD, skills=_skills_with(Ability.ELEMENTAL, 4, 9))
    )
    state.add_leader(LeaderState(502, kingdom_id=2, name="B", location=FIELD))
    attacker_armies = [ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, FIELD, commanded_by=501)]
    defender_armies = [ArmyState(201, 2, ArmyType.GARRISON, Quality.GREEN, FIELD, commanded_by=502)]
    attacker_units = [BattleUnit(ArmyType.HVY_CAVALRY, 100.0, source_id=101)]
    defender_units = [BattleUnit(ArmyType.GARRISON, 10.0, source_id=201)]
    attacker_commander = Commander(leader_id=501, contingent_size=1, tactical_ability=0)
    defender_commander = Commander(leader_id=502, contingent_size=1, tactical_ability=0)

    with patch("ak_engine.turn.challenge_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.challenge_execution.roll_fireball_damage", return_value=99
    ):
        outcome = _maybe_fight_duel(
            attacker_commander, defender_commander, attacker_armies, defender_armies, attacker_units, defender_units,
            ScriptedRandom([]), state=state, use_real_duel_combat=True,
            duel_maneuvers=[SearchTactic(Maneuver.CAST, Spell.FIREBALL.value)],
        )

    assert outcome.loser_side == "defender"
    assert defender_units[0].effective_strength == 10.0 * 0.75


def test_maybe_fight_duel_cast_control_undead_ineligible_against_a_garrison_commander_target():
    # The defender is the provincial garrison commander -- no real
    # LeaderState exists for it, so `target_leader` is None. Control
    # Undead's own eligibility check must treat that as "not eligible"
    # rather than crash, and the walk falls through to Melee.
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
    rng = ScriptedRandom([0.1, 0.5, 0.9] * 15)  # A always hits, B always misses, once Melee starts

    with patch("ak_engine.turn.challenge_execution.resolve_personal_combat_spell_cast") as mock_roll:
        outcome = _maybe_fight_duel(
            attacker_commander, defender_commander, attacker_armies, defender_armies, attacker_units, defender_units,
            rng, state=state, use_real_duel_combat=True,
            duel_maneuvers=[SearchTactic(Maneuver.CAST, Spell.CONTROL_UNDEAD.value), Maneuver.MELEE],
        )

    assert not mock_roll.called
    assert outcome.loser_side == "defender"


def test_maybe_fight_duel_cast_from_a_leaderless_attacker_is_a_silent_no_op():
    # Defensive case: an attacker Commander with no real LeaderState
    # (never produced by this project's own commander-selection logic,
    # which requires attackers to be led -- but `_resolve_personal_
    # combat_cast()` must not crash if ever handed one). A CAST tactic
    # simply has no effect, and the walk falls through to Melee.
    state = GameState()
    state.add_kingdom(KingdomState(2, "Defendia", Race.HUMAN, Alignment.GOOD, FIELD))
    state.add_leader(
        LeaderState(502, kingdom_id=2, name="B", location=FIELD, skills=_skills_with(Ability.MELEE, 0, 9))
    )
    attacker_armies = [ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, FIELD)]  # unled
    defender_armies = [ArmyState(201, 2, ArmyType.GARRISON, Quality.GREEN, FIELD, commanded_by=502)]
    attacker_units = [BattleUnit(ArmyType.HVY_CAVALRY, 100.0, source_id=101)]
    defender_units = [BattleUnit(ArmyType.GARRISON, 10.0, source_id=201)]
    attacker_commander = Commander(leader_id=None, contingent_size=1, tactical_ability=0)
    defender_commander = Commander(leader_id=502, contingent_size=1, tactical_ability=0)
    # B's own melee skill (0) ties the garrison-style attacker's own
    # (also 0) -- initiative goes to a coin flip each round; scripted so
    # the attacker always wins that flip, always hits, B always misses.
    rng = ScriptedRandom([0.1, 0.1, 0.9] * 15)

    with patch("ak_engine.turn.challenge_execution.resolve_personal_combat_spell_cast") as mock_roll:
        outcome = _maybe_fight_duel(
            attacker_commander, defender_commander, attacker_armies, defender_armies, attacker_units, defender_units,
            rng, state=state, use_real_duel_combat=True,
            duel_maneuvers=[SearchTactic(Maneuver.CAST, Spell.CHARM.value), Maneuver.MELEE],
        )

    assert not mock_roll.called
    assert outcome.loser_side == "defender"


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
    # sequence. Phase 296: extra leading 0.9 in the second group accounts
    # for the new terrain-line-length-cap roll (consumed right after the
    # duel, before the 3 luck rolls).
    rng = ScriptedRandom([0.1, 0.5, 0.9, 0.1, 0.5] + [0.9, 0.9, 0.9, 0.9, 0.1, 0.99, 0.99, 0.99])

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
    # Phase 296: extra 0.9 right after the duel roll accounts for the new
    # terrain-line-length-cap roll.
    rng = ScriptedRandom([0.01, 0.9, 0.9, 0.9, 0.9, 0.1, 0.99, 0.99, 0.99])

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
    # 0.1 < the MARCH TABLE's own same-origin (distance 0), March-level-0
    # chance (80%, `multiple_contingents.py march_unite_chance()`, Phase
    # 307) -> unites into one battle; the rest are generic, repeated
    # "safe" rolls so the 2-vs-1 battle that follows never runs out of
    # scripted values regardless of exactly how many luck/quality rolls
    # its own resolution consumes.
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
    # 0.99 >= the MARCH TABLE's own beyond-distance-2 (clamped),
    # March-level-0 chance (20%, Phase 307) -> stays split into two
    # separate battles against the same (overwhelmingly strong, so it
    # survives both) defender.
    rng = ScriptedRandom([0.99] + [0.5] * 40, choice_indices=[0] * 40)

    battles = fight_multi_attacker_battle(state, FIELD, parties, rng=rng)

    assert len(battles) == 2
    assert sorted(battle.leader_ids[0] for battle in battles) == [10, 20]  # each fought its own battle


def test_fight_multi_attacker_battle_looks_up_each_leaders_own_march_skill():
    # Phase 307: the same far-apart origins as the "splits" test above,
    # but the joining party's own leader now has a real March-4 skill in
    # `state.leaders` -- proves `fight_multi_attacker_battle()` actually
    # looks it up (via `effective_skill_level`) rather than always
    # defaulting `Attacker.march_level` to 0. At distance 2+, level 0 is
    # 20% and level 4 is 60% -- a 0.5 roll fails the former and succeeds
    # the latter.
    state = build_state(attacker_quality=Quality.GREEN, defender_quality=Quality.ELITE)
    state.armies[201].army_type = ArmyType.HVY_CAVALRY  # overwhelmingly strong defender
    state.add_army(ArmyState(102, 1, ArmyType.BOWMEN, Quality.GREEN, FIELD))
    state.add_leader(
        LeaderState(20, kingdom_id=1, name="Marcher", location=HexCoord(9, 9), skills=_skills_with(Ability.MARCH, 4, 9))
    )
    parties = [
        MultiAttackerParty(leader_id=10, kingdom_id=1, army_ids=[101], origin_province=HexCoord(5, 5)),
        MultiAttackerParty(leader_id=20, kingdom_id=1, army_ids=[102], origin_province=HexCoord(9, 9)),
    ]
    rng = ScriptedRandom([0.5] + [0.5] * 40, choice_indices=[0] * 40)

    battles = fight_multi_attacker_battle(state, FIELD, parties, rng=rng)

    assert len(battles) == 1  # united, thanks to leader 20's own real March-4 skill
    assert sorted(battles[0].leader_ids) == [10, 20]


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
    # 0.99 >= the MARCH TABLE's own beyond-distance-2 (clamped),
    # March-level-0 chance (20%, Phase 307) -> stays split into two
    # separate battles; the first group's own overwhelming, no-luck rolls
    # (same shape as no_luck_overwhelming_attacker_rng()) clean-sweep the
    # lone defender before the second group's own turn.
    # Phase 296: extra 0.9 right after the unite-chance roll accounts for
    # the first group's own new terrain-line-length-cap roll.
    rng = ScriptedRandom([0.99, 0.9, 0.9, 0.9, 0.9, 0.1, 0.99, 0.99, 0.99])

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


# --- Contested-province priority for a double simultaneous neutral
# invasion (rulebook [7.6], Phase 311) --------------------------------------


def _neutral_invasion_state(*, field_owner_kingdom_id: int | None) -> GameState:
    # A single kingdom, two of its own leaders each leading a separate army
    # already sitting at FIELD (post-movement, pre-orchestration -- the same
    # convention every other multi-attacker test above uses) from far-apart
    # origins, so `group_attackers_into_battles` never unites them (Phase
    # 307's own MARCH TABLE, distance-clamped, at March level 0). Same
    # kingdom_id -> `state.is_allied()` treats the two groups as friendly to
    # each other, so with no third-party defender present, each group's own
    # claim is uncontested regardless of processing order -- letting these
    # tests isolate the Phase 311 *ordering* itself instead of a battle's
    # outcome. (A genuinely rival, non-allied double invasion of the very
    # same empty province would mean the two forces fighting each other
    # directly -- a real scenario, but one `fight_multi_attacker_battle()`
    # doesn't yet handle for a group whose own army is destroyed acting as
    # the "defender" in an earlier group's battle; out of this phase's
    # scope, since it's the *ordering* being added here, not that gap.)
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, HexCoord(0, 0)))
    state.add_province(ProvinceState(FIELD, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=field_owner_kingdom_id))
    state.add_army(ArmyState(101, 1, ArmyType.BOWMEN, Quality.GREEN, FIELD))
    state.add_army(ArmyState(102, 1, ArmyType.BOWMEN, Quality.GREEN, FIELD))
    return state


def test_fight_multi_attacker_battle_neutral_province_gives_priority_to_higher_initiative():
    state = _neutral_invasion_state(field_owner_kingdom_id=None)
    # Leader 10 has no skill data at all -> Initiative 0. Leader 20 has
    # real, high non-March skills -> Initiative well above 0. March itself
    # is left at 0 for both so neither leader's own union chance is
    # affected (irrelevant here regardless, since same-kingdom groups never
    # fight each other).
    state.add_leader(
        LeaderState(20, kingdom_id=1, name="Highstrung", location=HexCoord(20, 20), skills=_skills_with(Ability.MELEE, 9, 9))
    )
    parties = [
        # Given in low-initiative-first order -- priority must reorder this.
        MultiAttackerParty(leader_id=10, kingdom_id=1, army_ids=[101], origin_province=HexCoord(0, 0)),
        MultiAttackerParty(leader_id=20, kingdom_id=1, army_ids=[102], origin_province=HexCoord(20, 20)),
    ]
    rng = ScriptedRandom([0.99] * 10, choice_indices=[0] * 10)

    battles = fight_multi_attacker_battle(state, FIELD, parties, rng=rng)

    assert len(battles) == 2
    assert battles[0].leader_ids == [20]  # higher-Initiative leader's group fights (claims) first
    assert battles[1].leader_ids == [10]


def test_fight_multi_attacker_battle_neutral_province_tiebreaks_on_unit_count():
    state = _neutral_invasion_state(field_owner_kingdom_id=None)
    state.add_army(ArmyState(103, 1, ArmyType.BOWMEN, Quality.GREEN, FIELD))  # 2nd army for leader 20's group
    # Neither leader has any skill data -> both Initiative 0 -> tiebreak on
    # each group's own total unit count instead.
    parties = [
        MultiAttackerParty(leader_id=10, kingdom_id=1, army_ids=[101], origin_province=HexCoord(0, 0)),  # 1 unit
        MultiAttackerParty(leader_id=20, kingdom_id=1, army_ids=[102, 103], origin_province=HexCoord(20, 20)),  # 2 units
    ]
    rng = ScriptedRandom([0.99] * 10, choice_indices=[0] * 10)

    battles = fight_multi_attacker_battle(state, FIELD, parties, rng=rng)

    assert len(battles) == 2
    assert battles[0].leader_ids == [20]  # more units -> claims first


def test_fight_multi_attacker_battle_enemy_owned_province_keeps_arbitrary_order():
    # Same higher-Initiative-leader setup as the neutral-province test
    # above, but FIELD now belongs to a (third) kingdom -- [7.6]'s own
    # priority rule is scoped to a "provincia neutrale", so this case must
    # NOT be reordered: the groups stay in the order the caller supplied.
    state = _neutral_invasion_state(field_owner_kingdom_id=99)
    state.add_leader(
        LeaderState(20, kingdom_id=1, name="Highstrung", location=HexCoord(20, 20), skills=_skills_with(Ability.MELEE, 9, 9))
    )
    parties = [
        MultiAttackerParty(leader_id=10, kingdom_id=1, army_ids=[101], origin_province=HexCoord(0, 0)),
        MultiAttackerParty(leader_id=20, kingdom_id=1, army_ids=[102], origin_province=HexCoord(20, 20)),
    ]
    rng = ScriptedRandom([0.99] * 10, choice_indices=[0] * 10)

    battles = fight_multi_attacker_battle(state, FIELD, parties, rng=rng)

    assert len(battles) == 2
    assert battles[0].leader_ids == [10]  # unchanged input order, despite leader 20's higher Initiative
    assert battles[1].leader_ids == [20]


# --- Merit Point battle-outcome recording (rulebook page 51, Phase 254) ---


def _merit_state() -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, HexCoord(0, 0)))
    state.add_kingdom(KingdomState(2, "Defendia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(9, 9)))
    state.add_leader(LeaderState(1, 1, "Attacker Commander", FIELD))
    state.add_leader(LeaderState(2, 2, "Defender Commander", FIELD))
    return state


def _armies(*specs: tuple[ArmyType, Quality]) -> list[ArmyState]:
    """A throwaway list of ``ArmyState``s for `_record_battle_merit()`'s own
    quality-table lookup -- ids/kingdom/location are irrelevant here,
    only ``army_type``/``quality`` feed `battle_quality_points()`.
    """

    return [ArmyState(i, 1, army_type, quality, FIELD) for i, (army_type, quality) in enumerate(specs)]


def test_record_battle_merit_credits_winning_land_commander_and_debits_losing_one():
    state = _merit_state()
    # Defender (the losing side) fields a Veteran (2 points) and a Crack
    # (3 points) -- 5 points total, same shape the old flat-count test
    # used, now quality-weighted instead of a bare unit count.
    defender_armies = _armies((ArmyType.HVY_CAVALRY, Quality.VETERAN), (ArmyType.HVY_CAVALRY, Quality.CRACK))

    _record_battle_merit(state, Terrain.PLAINS, BattleResult(winner="attacker"), 1, 2, [], defender_armies)

    assert state.leaders[1].merit_tally.land_battles_won_points == 5
    assert state.leaders[2].merit_tally.land_battles_lost_points == 5
    assert state.leaders[1].merit_tally.land_battles_lost_points == 0
    assert state.leaders[2].merit_tally.land_battles_won_points == 0


def test_record_battle_merit_credits_winning_naval_commander():
    state = _merit_state()
    # Attacker (the losing side) fields two Elite (4 points each) -- 8
    # points total.
    attacker_armies = _armies((ArmyType.FLEET, Quality.ELITE), (ArmyType.FLEET, Quality.ELITE))

    _record_battle_merit(state, Terrain.SEA, BattleResult(winner="defender"), 1, 2, attacker_armies, [])

    assert state.leaders[2].merit_tally.naval_battles_won_points == 8
    assert state.leaders[1].merit_tally.naval_battles_lost_points == 8
    # Naval and land counters are kept fully separate.
    assert state.leaders[2].merit_tally.land_battles_won_points == 0


def test_record_battle_merit_applies_the_attacking_garrison_modifier():
    # NUOVE REGOLE's own worked example: a Crack Garrison that attacks
    # and is destroyed gives only 2 points (3 - 1), not 3.
    state = _merit_state()
    attacker_armies = _armies((ArmyType.GARRISON, Quality.CRACK))

    _record_battle_merit(state, Terrain.PLAINS, BattleResult(winner="defender"), 1, 2, attacker_armies, [])

    assert state.leaders[2].merit_tally.land_battles_won_points == 2


def test_record_battle_merit_records_nothing_for_a_tie():
    state = _merit_state()
    defender_armies = _armies((ArmyType.HVY_CAVALRY, Quality.CRACK))

    _record_battle_merit(state, Terrain.PLAINS, BattleResult(winner="tie"), 1, 2, [], defender_armies)

    assert state.leaders[1].merit_tally.land_battles_won_points == 0
    assert state.leaders[2].merit_tally.land_battles_lost_points == 0


def test_record_battle_merit_skips_an_unled_winning_side():
    state = _merit_state()
    attacker_armies = _armies((ArmyType.HVY_CAVALRY, Quality.CRACK))
    defender_armies = _armies((ArmyType.HVY_CAVALRY, Quality.ELITE))

    # The winning side (defender) has no commander (garrison fallback,
    # leader_id=None) -- no one to credit -- but the losing side (attacker,
    # leader 1) is still a real "battaglia comandata" for its own leader.
    _record_battle_merit(
        state, Terrain.PLAINS, BattleResult(winner="defender"), 1, None, attacker_armies, defender_armies
    )

    assert state.leaders[1].merit_tally.land_battles_lost_points == 3
    assert state.leaders[1].merit_tally.land_battles_won_points == 0


def test_record_battle_merit_skips_an_unled_losing_side():
    state = _merit_state()
    attacker_armies = _armies((ArmyType.HVY_CAVALRY, Quality.CRACK))
    defender_armies = _armies((ArmyType.HVY_CAVALRY, Quality.ELITE))

    # The losing side (defender) has no commander -- nothing to debit --
    # but the winning side (attacker, leader 1) still earns its credit.
    _record_battle_merit(
        state, Terrain.PLAINS, BattleResult(winner="attacker"), 1, None, attacker_armies, defender_armies
    )

    assert state.leaders[1].merit_tally.land_battles_won_points == 4
    assert state.leaders[1].merit_tally.land_battles_lost_points == 0


def test_fight_battle_wires_merit_points_for_a_led_winning_attacker():
    # Same fixture/rng shape as
    # test_fight_battle_reads_a_led_attackers_real_tactical_skill_end_to_end:
    # attacker leader 1 wins outright, defender falls back to an unled
    # garrison commander (leader_id=None) -- only the attacker's own
    # commander has a real leader to credit. build_state()'s own lone
    # defending army (201) is a GARRISON/GREEN -- 0 points, no attacking-
    # Garrison modifier (it's the defender here).
    state = build_state()
    state.add_leader(LeaderState(1, 1, "Skilled Commander", FIELD, skills=SkillTable(raw_values=[5] * 30 + [0])))
    state.armies[101].commanded_by = 1
    # Phase 296: extra 0.9 right after the duel roll accounts for the new
    # terrain-line-length-cap roll (consumed after the duel, before the
    # 3 luck rolls) -- see no_luck_overwhelming_attacker_rng()'s own note.
    rng = ScriptedRandom([0.05, 0.9, 0.9, 0.9, 0.9, 0.1, 0.99, 0.99, 0.99])

    fight_battle(state, attacker_kingdom_id=1, province_coord=FIELD, attacker_army_ids=[101], rng=rng)

    assert state.leaders[1].merit_tally.land_battles_won_points == 0  # GARRISON/GREEN defender scores 0
    assert state.leaders[1].merit_tally.land_battles_lost_points == 0


# -- Phase 296: terrain line-length cap now really rolled and forwarded --


def test_fight_battle_rolls_and_forwards_the_terrain_line_length_cap():
    # Bug fix: roll_terrain_line_length_cap() (rulebook [1.6]) existed
    # since Phase 6 but fight_battle() -- the sole production caller of
    # resolve_battle() -- never actually called it, so the Terrain Table
    # line-length shortening (and the Phase 64 numeric-superiority
    # outflanking bonus that depends on it) never applied in any real
    # battle. Proven here via mocking, the same wiring-verification
    # pattern this project already uses elsewhere: the roll is made
    # against the province's own real terrain, and its result is
    # forwarded to resolve_battle() rather than silently defaulting to
    # None.
    state = build_state()
    rng = no_luck_overwhelming_attacker_rng()

    with patch("ak_engine.turn.battle_orchestrator.roll_terrain_line_length_cap", return_value=7) as mock_roll, patch(
        "ak_engine.turn.battle_orchestrator.resolve_battle"
    ) as mock_resolve:
        mock_resolve.return_value = BattleResult(winner="attacker")
        fight_battle(state, attacker_kingdom_id=1, province_coord=FIELD, attacker_army_ids=[101], rng=rng)

    assert mock_roll.call_args.args[0] is Terrain.PLAINS  # build_state()'s own province terrain
    assert mock_resolve.call_args.kwargs["terrain_line_length_cap"] == 7


def test_fight_battle_numeric_superiority_outflanking_now_applies_end_to_end():
    # Same rule as test_resolve_battle_numeric_superiority_boosts_second_
    # line_to_full_strength (test_battle_resolution.py, Phase 64) but
    # proven reachable through the real fight_battle() orchestrator this
    # time, not just a direct resolve_battle() call -- the whole point of
    # this fix. Two identical attacker armies (so the front-line and
    # second-line units share the same effective_strength) against a
    # single defender army on Plains ([1.6]: line-length range 5-10,
    # always > line_length=1 here) -- the attacker's own numeric
    # superiority (2 armies > 1) makes its second-line unit eligible for
    # the 100%-instead-of-50% outflanking boost.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, HexCoord(0, 0)))
    state.add_kingdom(KingdomState(2, "Defendia", Race.HUMAN, Alignment.NEUTRAL, DEFENDER_HOME))
    state.add_province(ProvinceState(FIELD, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2))
    state.add_army(ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, FIELD))
    state.add_army(ArmyState(102, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, FIELD))
    state.add_army(ArmyState(201, 2, ArmyType.GARRISON, Quality.GREEN, FIELD))
    # terrain-cap roll (any value >=2 works, Plains' own 5-10 range always
    # does), no luck either side, decisive attacker win, pursuit-decline,
    # then one winner_quality_roll per surviving attacker army (two here).
    rng = ScriptedRandom([0.9, 0.9, 0.9, 0.9, 0.1, 0.99, 0.99, 0.99, 0.99])

    report = fight_battle(state, attacker_kingdom_id=1, province_coord=FIELD, attacker_army_ids=[101, 102], rng=rng)

    assert len(report.battle_result.columns) == 1
    column = report.battle_result.columns[0]
    # A control single-HVY_CAVALRY/ELITE-vs-Plains unit's own effective
    # strength (front-line unit -- always 100%, regardless of outflanking).
    single_unit_strength = compute_effective_strength(ArmyType.HVY_CAVALRY, Race.HUMAN, Quality.ELITE, Terrain.PLAINS)
    # Boosted: both units count at 100% (front + outflanked second line),
    # not the ordinary 100% + 50%.
    assert column.attacker_strength == pytest.approx(2 * single_unit_strength)


# -- Phase 298: Druidic insufficient-ability quality-improve penalty now
# reaches real post-battle roll_quality_change() calls --


def test_fight_battle_winning_army_led_by_insufficient_druid_passes_the_penalty_flag():
    # Bug fix: turn/aftermath.py roll_quality_change()'s own led_by_
    # insufficient_druid parameter (rulebook [7.5]) was fully implemented
    # but never actually passed by any real call site in this module,
    # even though the same druidic_shortfall value is already computed
    # per-army in _build_battle_units() for the strength-side penalty.
    # Same fixture shape as test_build_battle_units_druidic_shortfall_
    # penalizes_a_foreign_race_led_army: a Human leader (Druid skill 0)
    # commands a Dragon army -- DRUID_TABLE[Dragons] == 4, full shortfall.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Humania", Race.HUMAN, Alignment.NEUTRAL, home_province=HexCoord(9, 9)))
    state.add_kingdom(KingdomState(2, "Dragonia", Race.DRAGONS, Alignment.NEUTRAL, home_province=HexCoord(8, 8)))
    state.add_kingdom(KingdomState(3, "Weakland", Race.HUMAN, Alignment.NEUTRAL, home_province=HexCoord(7, 7)))
    state.add_province(ProvinceState(FIELD, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=3))
    state.add_leader(LeaderState(1, kingdom_id=1, name="Hero", location=FIELD))
    state.add_army(ArmyState(101, 2, ArmyType.DRAGON_WING, Quality.ELITE, location=FIELD, commanded_by=1))
    state.add_army(ArmyState(201, 3, ArmyType.GARRISON, Quality.GREEN, location=FIELD))
    # A real, unscripted seeded rng -- the attacker leader triggers a real
    # Duel against the defender's own provisional garrison commander (an
    # extra roll no simple scripted sequence accounts for), so a plain
    # seed verified deterministic for this exact fixture (attacker wins)
    # is simpler than hand-scripting every intermediate roll.
    rng = random.Random(1)

    with patch("ak_engine.turn.battle_orchestrator.roll_quality_change") as mock_roll:
        mock_roll.return_value = Quality.ELITE
        report = fight_battle(state, attacker_kingdom_id=1, province_coord=FIELD, attacker_army_ids=[101], rng=rng)

    assert report.battle_result.winner == "attacker"
    # Phase 423: score= is the attacker's own column's real BRES (a
    # documented, unconfirmed interpretation -- see aftermath.py's own
    # docstring), threaded alongside formation_divisor now.
    mock_roll.assert_called_once_with(
        Quality.ELITE, rng, is_winner=True, led_by_insufficient_druid=True, formation_divisor=1, score=1
    )


# -- Phase 371: real, confirmed per-column direct destruction wired into
# the non-clean-swept per-army loss branch --


def _direct_destruction_column(
    bres: int, attacker_type: ArmyType, defender_type: ArmyType, attacker_id: int = 101, defender_id: int = 201
) -> BattleColumnResult:
    return BattleColumnResult(
        attacker_strength=20.0,
        defender_strength=5.0,
        bres=bres,
        attacker_won=bres > 0,
        cluck_index=20,
        attacker_units=[BattleUnit(attacker_type, 20.0, source_id=attacker_id)],
        defender_units=[BattleUnit(defender_type, 5.0, source_id=defender_id)],
    )


def test_direct_destruction_probabilities_reads_the_losing_front_line_unit_only():
    # bres > 0 -- attacker won the column, so the defender's own front
    # unit (not the attacker's) is the eligible "first-line loser".
    # HVY_CAVALRY (speed 3) beats GARRISON (speed 1): speed_delta clamps
    # to +1, so direct_destruction_probability(5, 3, 1) == 1.0.
    column = _direct_destruction_column(5, ArmyType.HVY_CAVALRY, ArmyType.GARRISON)
    battle_result = BattleResult(columns=[column], winner="attacker", total_bres=5)

    probabilities = _direct_destruction_probabilities(battle_result)

    assert probabilities == {201: 1.0}


def test_direct_destruction_probabilities_flips_the_loser_when_bres_favors_the_defender():
    column = _direct_destruction_column(-5, ArmyType.GARRISON, ArmyType.HVY_CAVALRY)
    battle_result = BattleResult(columns=[column], winner="defender", total_bres=-5)

    probabilities = _direct_destruction_probabilities(battle_result)

    # Now the attacker's own front unit (101) is the loser.
    assert probabilities == {101: 1.0}


def test_direct_destruction_probabilities_skips_a_genuine_column_tie():
    column = _direct_destruction_column(0, ArmyType.HVY_CAVALRY, ArmyType.GARRISON)
    battle_result = BattleResult(columns=[column], winner="attacker", total_bres=0)

    assert _direct_destruction_probabilities(battle_result) == {}


# -- Phase 444: Wingman (air_combat_merit) --------------------------------


def _wingman_state(attacker_type: ArmyType, defender_type: ArmyType) -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, HexCoord(0, 0)))
    state.add_kingdom(KingdomState(2, "Defendia", Race.HUMAN, Alignment.NEUTRAL, DEFENDER_HOME))
    state.add_leader(LeaderState(1, kingdom_id=1, name="Attacker Leader", location=FIELD))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Defender Leader", location=FIELD))
    state.add_army(ArmyState(101, 1, attacker_type, Quality.ELITE, FIELD, commanded_by=1))
    state.add_army(ArmyState(201, 2, defender_type, Quality.GREEN, FIELD, commanded_by=2))
    return state


def test_apply_wingman_merit_credits_winning_air_unit_and_ignores_losing_non_air():
    state = _wingman_state(ArmyType.DRAGON_WING, ArmyType.GARRISON)
    column = _direct_destruction_column(5, ArmyType.DRAGON_WING, ArmyType.GARRISON)
    battle_result = BattleResult(columns=[column], winner="attacker", total_bres=5)

    _apply_wingman_merit(state, battle_result)

    assert state.leaders[1].merit_tally.air_combat_merit == 1
    assert state.leaders[2].merit_tally.air_combat_merit == 0


def test_apply_wingman_merit_docks_losing_air_unit_and_ignores_winning_non_air():
    state = _wingman_state(ArmyType.GARRISON, ArmyType.DRAGON_WING)
    column = _direct_destruction_column(5, ArmyType.GARRISON, ArmyType.DRAGON_WING)
    battle_result = BattleResult(columns=[column], winner="attacker", total_bres=5)

    _apply_wingman_merit(state, battle_result)

    assert state.leaders[1].merit_tally.air_combat_merit == 0
    assert state.leaders[2].merit_tally.air_combat_merit == -1


def test_apply_wingman_merit_air_vs_air_credits_both_oppositely():
    state = _wingman_state(ArmyType.DRAGON_WING, ArmyType.EAGLE_WING)
    column = _direct_destruction_column(5, ArmyType.DRAGON_WING, ArmyType.EAGLE_WING)
    battle_result = BattleResult(columns=[column], winner="attacker", total_bres=5)

    _apply_wingman_merit(state, battle_result)

    assert state.leaders[1].merit_tally.air_combat_merit == 1
    assert state.leaders[2].merit_tally.air_combat_merit == -1


def test_apply_wingman_merit_non_air_vs_non_air_is_a_no_op():
    state = _wingman_state(ArmyType.HVY_CAVALRY, ArmyType.GARRISON)
    column = _direct_destruction_column(5, ArmyType.HVY_CAVALRY, ArmyType.GARRISON)
    battle_result = BattleResult(columns=[column], winner="attacker", total_bres=5)

    _apply_wingman_merit(state, battle_result)

    assert state.leaders[1].merit_tally.air_combat_merit == 0
    assert state.leaders[2].merit_tally.air_combat_merit == 0


def test_apply_wingman_merit_excludes_vampires():
    # The real Wingman predicate is called with a literal `false` for its
    # include_vampires flag -- unlike some other overflight checks in
    # this project, Vampires never count here.
    state = _wingman_state(ArmyType.VAMPIRES, ArmyType.GARRISON)
    column = _direct_destruction_column(5, ArmyType.VAMPIRES, ArmyType.GARRISON)
    battle_result = BattleResult(columns=[column], winner="attacker", total_bres=5)

    _apply_wingman_merit(state, battle_result)

    assert state.leaders[1].merit_tally.air_combat_merit == 0
    assert state.leaders[2].merit_tally.air_combat_merit == 0


def test_apply_wingman_merit_skips_a_unit_with_no_commanding_leader():
    state = _wingman_state(ArmyType.DRAGON_WING, ArmyType.GARRISON)
    state.armies[101].commanded_by = None
    column = _direct_destruction_column(5, ArmyType.DRAGON_WING, ArmyType.GARRISON)
    battle_result = BattleResult(columns=[column], winner="attacker", total_bres=5)

    _apply_wingman_merit(state, battle_result)  # must not raise

    assert state.leaders[1].merit_tally.air_combat_merit == 0


def test_apply_wingman_merit_skips_a_genuine_column_tie():
    state = _wingman_state(ArmyType.DRAGON_WING, ArmyType.EAGLE_WING)
    column = _direct_destruction_column(0, ArmyType.DRAGON_WING, ArmyType.EAGLE_WING)
    battle_result = BattleResult(columns=[column], winner="attacker", total_bres=0)

    _apply_wingman_merit(state, battle_result)

    assert state.leaders[1].merit_tally.air_combat_merit == 0
    assert state.leaders[2].merit_tally.air_combat_merit == 0


def test_fight_battle_destroys_a_non_clean_swept_defenders_front_line_column_loser():
    # A hand-built BattleResult double (not a real resolve_battle() output --
    # defender_columns_won=1 is asserted directly rather than derived from
    # the single injected column, purely to make the top-level winner/
    # columns_won fields say "the defender wasn't clean swept" without
    # needing a second real column) exercises exactly the one branch that
    # previously had no destruction path at all: an army that lost the
    # battle without its own side being clean swept.
    state = build_state()  # attacker army 101 (HVY_CAVALRY), defender army 201 (GARRISON)
    column = _direct_destruction_column(5, ArmyType.HVY_CAVALRY, ArmyType.GARRISON)
    battle_result = BattleResult(
        columns=[column], winner="attacker", total_bres=5, attacker_columns_won=1, defender_columns_won=1
    )

    with patch("ak_engine.turn.battle_orchestrator.resolve_battle", return_value=battle_result):
        report = fight_battle(state, attacker_kingdom_id=1, province_coord=FIELD, attacker_army_ids=[101], rng=_generously_padded_rng())

    assert 201 in report.destroyed_army_ids
    assert 201 not in state.armies
    assert state.battle_graveyard[FIELD][0].army_type is ArmyType.GARRISON


def test_fight_battle_falls_back_to_quality_change_when_direct_destruction_misses():
    # bres=-1 with the defender (GARRISON, speed 1) as winner and the
    # attacker (HVY_CAVALRY, speed 3) as loser: speed_delta clamps to -1,
    # so direct_destruction_probability(1, 1, 3) == 0.0 -- a guaranteed
    # miss regardless of the rng draw, falling through to the ordinary
    # is_winner=False quality-change roll unchanged.
    state = build_state()
    column = _direct_destruction_column(-1, ArmyType.HVY_CAVALRY, ArmyType.GARRISON)
    battle_result = BattleResult(
        columns=[column], winner="defender", total_bres=-1, attacker_columns_won=1, defender_columns_won=1
    )

    with patch("ak_engine.turn.battle_orchestrator.resolve_battle", return_value=battle_result):
        report = fight_battle(state, attacker_kingdom_id=1, province_coord=FIELD, attacker_army_ids=[101], rng=_generously_padded_rng())

    assert 101 not in report.destroyed_army_ids
    assert 101 in state.armies
    assert 101 in report.quality_changes


# -- Phase 372: real, confirmed post-battle quality-change formula wired
# into roll_quality_change via formation_divisor --


def test_formation_divisors_reads_each_units_own_index_as_its_depth():
    column = BattleColumnResult(
        attacker_strength=30.0,
        defender_strength=10.0,
        bres=3,
        attacker_won=True,
        cluck_index=20,
        attacker_units=[
            BattleUnit(ArmyType.HVY_CAVALRY, 10.0, source_id=1),  # front
            BattleUnit(ArmyType.HVY_CAVALRY, 10.0, source_id=2),  # second
            BattleUnit(ArmyType.HVY_CAVALRY, 5.0, source_id=3),  # third
            BattleUnit(ArmyType.HVY_CAVALRY, 5.0, source_id=4),  # fourth_and_later
            BattleUnit(ArmyType.HVY_CAVALRY, 5.0, source_id=5),  # also fourth_and_later
        ],
        defender_units=[BattleUnit(ArmyType.GARRISON, 10.0, source_id=201)],
    )
    battle_result = BattleResult(columns=[column], winner="attacker", total_bres=3)

    divisors = _formation_divisors(battle_result)

    assert divisors[1] == FORMATION_DIVISOR["front"]
    assert divisors[2] == FORMATION_DIVISOR["second"]
    assert divisors[3] == FORMATION_DIVISOR["third"]
    assert divisors[4] == FORMATION_DIVISOR["fourth_and_later"]
    assert divisors[5] == FORMATION_DIVISOR["fourth_and_later"]
    assert divisors[201] == FORMATION_DIVISOR["front"]


def test_formation_divisors_covers_both_sides_across_multiple_columns():
    column_one = BattleColumnResult(
        attacker_strength=10.0, defender_strength=10.0, bres=1, attacker_won=True, cluck_index=20,
        attacker_units=[BattleUnit(ArmyType.HVY_CAVALRY, 10.0, source_id=101)],
        defender_units=[
            BattleUnit(ArmyType.GARRISON, 5.0, source_id=201),
            BattleUnit(ArmyType.GARRISON, 5.0, source_id=202),
        ],
    )
    column_two = BattleColumnResult(
        attacker_strength=10.0, defender_strength=10.0, bres=-1, attacker_won=False, cluck_index=20,
        attacker_units=[BattleUnit(ArmyType.HVY_CAVALRY, 10.0, source_id=102)],
        defender_units=[BattleUnit(ArmyType.GARRISON, 5.0, source_id=203)],
    )
    battle_result = BattleResult(columns=[column_one, column_two], winner="attacker", total_bres=0)

    divisors = _formation_divisors(battle_result)

    assert divisors == {
        101: FORMATION_DIVISOR["front"],
        102: FORMATION_DIVISOR["front"],
        201: FORMATION_DIVISOR["front"],
        202: FORMATION_DIVISOR["second"],
        203: FORMATION_DIVISOR["front"],
    }


# -- Phase 423: score= for roll_quality_change's own gain-side merit
# multiplier -- a documented, unconfirmed interpretation of column_bres
# as the source's own unnamed "P" (see _column_bres_by_army_id's own
# docstring), not a recovered formula --


def test_column_bres_by_army_id_orients_score_by_side():
    # bres favors the attacker (+3): the attacker's own army keeps that
    # sign ("my side did well"), the defender's own army gets the
    # opposite sign ("my side did poorly in this column").
    column = BattleColumnResult(
        attacker_strength=20.0, defender_strength=5.0, bres=3, attacker_won=True, cluck_index=20,
        attacker_units=[BattleUnit(ArmyType.HVY_CAVALRY, 20.0, source_id=101)],
        defender_units=[BattleUnit(ArmyType.GARRISON, 5.0, source_id=201)],
    )
    battle_result = BattleResult(columns=[column], winner="attacker", total_bres=3)

    scores = _column_bres_by_army_id(battle_result)

    assert scores == {101: 3, 201: -3}


def test_column_bres_by_army_id_covers_both_sides_across_multiple_columns():
    column_one = BattleColumnResult(
        attacker_strength=10.0, defender_strength=10.0, bres=2, attacker_won=True, cluck_index=20,
        attacker_units=[BattleUnit(ArmyType.HVY_CAVALRY, 10.0, source_id=101)],
        defender_units=[BattleUnit(ArmyType.GARRISON, 5.0, source_id=201)],
    )
    column_two = BattleColumnResult(
        attacker_strength=10.0, defender_strength=10.0, bres=-4, attacker_won=False, cluck_index=20,
        attacker_units=[BattleUnit(ArmyType.HVY_CAVALRY, 10.0, source_id=102)],
        defender_units=[BattleUnit(ArmyType.GARRISON, 5.0, source_id=202)],
    )
    battle_result = BattleResult(columns=[column_one, column_two], winner="attacker", total_bres=-2)

    scores = _column_bres_by_army_id(battle_result)

    assert scores == {101: 2, 201: -2, 102: -4, 202: 4}


def test_fight_battle_uses_real_per_column_bres_as_the_gain_side_merit_score():
    # Two winning attacker armies, each front-line in its own column: 101's
    # own column went well (bres=+5, score=5 -> full 1.0 merit multiplier),
    # 102's own column went badly despite the overall attacker win
    # (bres=-3, score=-3 -> the source's own "P<=-3" 0.0 multiplier, no
    # gain possible at all regardless of the roll). AVERAGE's own real
    # front-line improve chance is 30% -- a scripted roll of 0.25 clears
    # 101's own (unmodified) 30% chance but can never clear 102's own
    # forced-to-zero chance, proving score reaches roll_quality_change
    # through a real fight_battle() call with the right per-army sign.
    state = build_state()
    state.armies[101].quality = Quality.AVERAGE
    state.add_army(ArmyState(102, 1, ArmyType.HVY_CAVALRY, Quality.AVERAGE, FIELD))
    column_one = BattleColumnResult(
        attacker_strength=20.0, defender_strength=5.0, bres=5, attacker_won=True, cluck_index=20,
        attacker_units=[BattleUnit(ArmyType.HVY_CAVALRY, 20.0, source_id=101)],
        defender_units=[BattleUnit(ArmyType.GARRISON, 5.0, source_id=201)],
    )
    column_two = BattleColumnResult(
        attacker_strength=8.0, defender_strength=10.0, bres=-3, attacker_won=False, cluck_index=20,
        attacker_units=[BattleUnit(ArmyType.HVY_CAVALRY, 8.0, source_id=102)],
        defender_units=[BattleUnit(ArmyType.GARRISON, 10.0, source_id=202)],
    )
    battle_result = BattleResult(
        columns=[column_one, column_two], winner="attacker", total_bres=2,
        attacker_columns_won=1, defender_columns_won=0,
    )
    # One draw for fight_battle's own terrain-line-length-cap roll (value
    # irrelevant -- resolve_battle is patched), then the two scripted
    # improve rolls.
    rng = ScriptedRandom([0.9, 0.25, 0.25])

    with patch("ak_engine.turn.battle_orchestrator.resolve_battle", return_value=battle_result):
        fight_battle(
            state, attacker_kingdom_id=1, province_coord=FIELD, attacker_army_ids=[101, 102],
            loser_retreats=False, rng=rng,
        )

    assert state.armies[101].quality == Quality.VETERAN  # score=5: full 30% chance, 0.25 < 0.30 -- improved
    assert state.armies[102].quality == Quality.AVERAGE  # score=-3: 0% chance -- unchanged regardless of roll


def test_fight_battle_uses_real_formation_depth_for_a_winning_seconds_line_army():
    # A hand-built BattleResult double (not a real resolve_battle() output
    # -- see the Phase 371 direct-destruction tests above for the same
    # pattern) puts army 101 at the front of its column and army 102
    # second, both on the winning attacker side. AVERAGE's own real
    # improve chance is 30% front, 15% second (score=0) -- a scripted
    # roll of 0.20 clears the front-line chance but not the second-line
    # one, proving formation_divisor actually reaches roll_quality_change
    # through a real fight_battle() call, not just a direct unit test.
    state = build_state()
    state.armies[101].quality = Quality.AVERAGE
    state.add_army(ArmyState(102, 1, ArmyType.HVY_CAVALRY, Quality.AVERAGE, FIELD))
    column = BattleColumnResult(
        attacker_strength=20.0, defender_strength=5.0, bres=5, attacker_won=True, cluck_index=20,
        attacker_units=[
            BattleUnit(ArmyType.HVY_CAVALRY, 20.0, source_id=101),
            BattleUnit(ArmyType.HVY_CAVALRY, 10.0, source_id=102),
        ],
        defender_units=[BattleUnit(ArmyType.GARRISON, 5.0, source_id=201)],
    )
    battle_result = BattleResult(
        columns=[column], winner="attacker", total_bres=5, attacker_columns_won=1, defender_columns_won=0
    )
    # One draw for fight_battle's own terrain-line-length-cap roll (value
    # irrelevant -- resolve_battle is patched, so its own cap argument is
    # never read), then the two scripted improve rolls.
    rng = ScriptedRandom([0.9, 0.20, 0.20])

    with patch("ak_engine.turn.battle_orchestrator.resolve_battle", return_value=battle_result):
        fight_battle(
            state, attacker_kingdom_id=1, province_coord=FIELD, attacker_army_ids=[101, 102],
            loser_retreats=False, rng=rng,
        )

    assert state.armies[101].quality == Quality.VETERAN  # front: 0.20 < 0.30 -- improved
    assert state.armies[102].quality == Quality.AVERAGE  # second: 0.20 >= 0.15 -- unchanged


# -- Druidic monster battle assistance wiring (Phase 453) -------------------


def test_fight_battle_wires_druidic_monster_assistance_into_the_attackers_column_bonus():
    # Kingdom 1 (attacker) is Druidic; a Silver Dragon guards a Feature
    # at the battle province. feature_id=2 + Monster.S_DRAGON.value(8)
    # -> q=266 (even) -> Agent_Align never walks, so the dragon's own
    # effective alignment stays exactly its base_view (Druidic) -- the
    # source's own d_D==0 case, always eligible (probability 1.0)
    # regardless of the padded rng's own 0.9 filler value. build_state()
    # is a 1-vs-1 battle (line_length==1), so find_druidic_monster_
    # assistance's own randrange(1) can only ever land on column 0.
    # Silver Dragon's own real stats (hp=30, melee=9, missile=10) give a
    # (30*19)//50 == 11 strength bonus.
    state = build_state()
    state.kingdoms[1].alignment = Alignment.DRUID
    state.add_feature(Feature(2, FIELD, FeatureType.CAVE, guardian_monster=Monster.S_DRAGON))
    battle_result = BattleResult(columns=[], winner="attacker", total_bres=1)

    with patch("ak_engine.turn.battle_orchestrator.resolve_battle", return_value=battle_result) as mock_resolve:
        fight_battle(
            state, attacker_kingdom_id=1, province_coord=FIELD, attacker_army_ids=[101],
            rng=_generously_padded_rng(),
        )

    assert mock_resolve.call_args.kwargs["attacker_column_bonus"] == {0: 11}
    assert mock_resolve.call_args.kwargs["defender_column_bonus"] is None


def test_fight_battle_grants_no_druidic_assistance_to_a_non_druidic_side():
    # Same guarded Feature as above, but Kingdom 1 stays its own default
    # (non-Druidic) Alignment -- neither side qualifies, so both bonus
    # dicts stay None, proving the wiring is conditional on the real
    # Alignment check, not unconditionally on/off.
    state = build_state()
    state.add_feature(Feature(2, FIELD, FeatureType.CAVE, guardian_monster=Monster.S_DRAGON))
    battle_result = BattleResult(columns=[], winner="attacker", total_bres=1)

    with patch("ak_engine.turn.battle_orchestrator.resolve_battle", return_value=battle_result) as mock_resolve:
        fight_battle(
            state, attacker_kingdom_id=1, province_coord=FIELD, attacker_army_ids=[101],
            rng=_generously_padded_rng(),
        )

    assert mock_resolve.call_args.kwargs["attacker_column_bonus"] is None
    assert mock_resolve.call_args.kwargs["defender_column_bonus"] is None


# -- Werebeast bite-transform, battle-time half (Phase 392) ---------------


def test_apply_werebeast_bites_queues_the_defeated_humanoid_armys_id_on_a_hit():
    state = GameState()
    column = BattleColumnResult(
        attacker_strength=10.0, defender_strength=5.0, bres=3, attacker_won=True, cluck_index=20,
        attacker_units=[BattleUnit(ArmyType.WEREBEASTS, 10.0, source_id=101)],
        defender_units=[BattleUnit(ArmyType.LEGION, 5.0, source_id=201, is_humanoid_race=True)],
    )
    battle_result = BattleResult(
        columns=[column], winner="attacker", total_bres=3, attacker_columns_won=1, defender_columns_won=0
    )
    rng = ScriptedRandom([0.1])  # < 0.40 -- the bite hits

    _apply_werebeast_bites(battle_result, state, rng)

    assert state.werebeast_bitten_army_ids == {201}


def test_apply_werebeast_bites_does_not_queue_on_a_miss():
    state = GameState()
    column = BattleColumnResult(
        attacker_strength=10.0, defender_strength=5.0, bres=3, attacker_won=True, cluck_index=20,
        attacker_units=[BattleUnit(ArmyType.WEREBEASTS, 10.0, source_id=101)],
        defender_units=[BattleUnit(ArmyType.LEGION, 5.0, source_id=201, is_humanoid_race=True)],
    )
    battle_result = BattleResult(
        columns=[column], winner="attacker", total_bres=3, attacker_columns_won=1, defender_columns_won=0
    )
    rng = ScriptedRandom([0.99])  # >= 0.40 -- the bite misses

    _apply_werebeast_bites(battle_result, state, rng)

    assert state.werebeast_bitten_army_ids == set()


def test_apply_werebeast_bites_never_rolled_for_a_non_humanoid_loser():
    state = GameState()
    column = BattleColumnResult(
        attacker_strength=10.0, defender_strength=5.0, bres=3, attacker_won=True, cluck_index=20,
        attacker_units=[BattleUnit(ArmyType.WEREBEASTS, 10.0, source_id=101)],
        defender_units=[BattleUnit(ArmyType.DRAGON_WING, 5.0, source_id=201, is_humanoid_race=False)],
    )
    battle_result = BattleResult(
        columns=[column], winner="attacker", total_bres=3, attacker_columns_won=1, defender_columns_won=0
    )
    rng = ScriptedRandom([])  # no roll should be attempted -- IndexError if one is

    _apply_werebeast_bites(battle_result, state, rng)

    assert state.werebeast_bitten_army_ids == set()


def test_apply_werebeast_bites_excludes_fleets_even_if_humanoid_owned():
    state = GameState()
    column = BattleColumnResult(
        attacker_strength=10.0, defender_strength=5.0, bres=3, attacker_won=True, cluck_index=20,
        attacker_units=[BattleUnit(ArmyType.WEREBEASTS, 10.0, source_id=101)],
        defender_units=[BattleUnit(ArmyType.FLEET, 5.0, source_id=201, is_humanoid_race=True)],
    )
    battle_result = BattleResult(
        columns=[column], winner="attacker", total_bres=3, attacker_columns_won=1, defender_columns_won=0
    )
    rng = ScriptedRandom([])

    _apply_werebeast_bites(battle_result, state, rng)

    assert state.werebeast_bitten_army_ids == set()


def test_apply_werebeast_bites_never_rolled_without_a_werebeast_on_the_winning_side():
    state = GameState()
    column = BattleColumnResult(
        attacker_strength=10.0, defender_strength=5.0, bres=3, attacker_won=True, cluck_index=20,
        attacker_units=[BattleUnit(ArmyType.HVY_CAVALRY, 10.0, source_id=101)],
        defender_units=[BattleUnit(ArmyType.LEGION, 5.0, source_id=201, is_humanoid_race=True)],
    )
    battle_result = BattleResult(
        columns=[column], winner="attacker", total_bres=3, attacker_columns_won=1, defender_columns_won=0
    )
    rng = ScriptedRandom([])

    _apply_werebeast_bites(battle_result, state, rng)

    assert state.werebeast_bitten_army_ids == set()


def test_apply_werebeast_bites_skips_a_genuine_column_tie():
    state = GameState()
    column = BattleColumnResult(
        attacker_strength=10.0, defender_strength=10.0, bres=0, attacker_won=False, cluck_index=20,
        attacker_units=[BattleUnit(ArmyType.WEREBEASTS, 10.0, source_id=101)],
        defender_units=[BattleUnit(ArmyType.LEGION, 10.0, source_id=201, is_humanoid_race=True)],
    )
    battle_result = BattleResult(columns=[column], winner="tie", total_bres=0, attacker_columns_won=0, defender_columns_won=0)
    rng = ScriptedRandom([])

    _apply_werebeast_bites(battle_result, state, rng)

    assert state.werebeast_bitten_army_ids == set()


def test_apply_werebeast_bites_checks_the_defender_side_when_the_defender_wins_the_column():
    state = GameState()
    column = BattleColumnResult(
        attacker_strength=5.0, defender_strength=10.0, bres=-3, attacker_won=False, cluck_index=20,
        attacker_units=[BattleUnit(ArmyType.LEGION, 5.0, source_id=101, is_humanoid_race=True)],
        defender_units=[BattleUnit(ArmyType.WEREBEASTS, 10.0, source_id=201)],
    )
    battle_result = BattleResult(
        columns=[column], winner="defender", total_bres=-3, attacker_columns_won=0, defender_columns_won=1
    )
    rng = ScriptedRandom([0.1])

    _apply_werebeast_bites(battle_result, state, rng)

    assert state.werebeast_bitten_army_ids == {101}


# -- Dragon/Eagle/Whale summoning-item aid (Phase 393) ---------------------


def _bearer_state(matching_treasure: Treasure) -> tuple[GameState, Commander]:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Beareria", Race.HUMAN, Alignment.NEUTRAL, home_province=HexCoord(9, 9)))
    state.add_leader(LeaderState(1, kingdom_id=1, name="Bearer", location=FIELD))
    state.add_item(matching_treasure, owner_leader_id=1)
    commander = Commander(leader_id=1, contingent_size=1, tactical_ability=0)
    return state, commander


def _aid_kwargs(**overrides):
    kwargs = dict(
        is_defender=False, terrain=Terrain.PLAINS, combat_ability_level=0, apply_fanaticism=False,
        own_explored_percent=0, opponent_kingdom_ids=frozenset(), is_island=False,
    )
    kwargs.update(overrides)
    return kwargs


def test_apply_monster_summoning_aid_adds_an_adjacent_unled_matching_army():
    state, commander = _bearer_state(Treasure.MONSTER_AID_DRAGON)
    aiding_army = ArmyState(301, None, ArmyType.DRAGON_WING, Quality.AVERAGE, location=DEFENDER_HOME)
    state.add_army(aiding_army)
    units: list[BattleUnit] = []
    bounds = MapBounds(*NORMAL_MAP_BOUNDS)
    rng = ScriptedRandom([0.1])  # < 33% invasion chance -- hits

    _apply_monster_summoning_aid(units, commander, state, FIELD, bounds, rng=rng, **_aid_kwargs())

    assert len(units) == 1
    assert units[0].army_type is ArmyType.DRAGON_WING
    assert units[0].source_id == 301
    expected = compute_effective_strength(ArmyType.DRAGON_WING, Race.DRAGONS, Quality.AVERAGE, Terrain.PLAINS)
    assert units[0].effective_strength == pytest.approx(expected)


def test_apply_monster_summoning_aid_no_treasure_no_roll():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Beareria", Race.HUMAN, Alignment.NEUTRAL, home_province=HexCoord(9, 9)))
    state.add_leader(LeaderState(1, kingdom_id=1, name="Bearer", location=FIELD))
    commander = Commander(leader_id=1, contingent_size=1, tactical_ability=0)
    aiding_army = ArmyState(301, None, ArmyType.DRAGON_WING, Quality.AVERAGE, location=DEFENDER_HOME)
    state.add_army(aiding_army)
    units: list[BattleUnit] = []
    bounds = MapBounds(*NORMAL_MAP_BOUNDS)
    rng = ScriptedRandom([])  # no roll should be attempted -- IndexError if one is

    _apply_monster_summoning_aid(units, commander, state, FIELD, bounds, rng=rng, **_aid_kwargs())

    assert units == []


def test_apply_monster_summoning_aid_no_commander_no_roll():
    state = GameState()
    aiding_army = ArmyState(301, None, ArmyType.DRAGON_WING, Quality.AVERAGE, location=DEFENDER_HOME)
    state.add_army(aiding_army)
    units: list[BattleUnit] = []
    bounds = MapBounds(*NORMAL_MAP_BOUNDS)
    rng = ScriptedRandom([])

    _apply_monster_summoning_aid(units, None, state, FIELD, bounds, rng=rng, **_aid_kwargs())

    assert units == []


def test_apply_monster_summoning_aid_ignores_a_led_matching_army():
    state, commander = _bearer_state(Treasure.MONSTER_AID_DRAGON)
    state.add_leader(LeaderState(2, kingdom_id=1, name="Wrangler", location=DEFENDER_HOME))
    aiding_army = ArmyState(301, 1, ArmyType.DRAGON_WING, Quality.AVERAGE, location=DEFENDER_HOME, commanded_by=2)
    state.add_army(aiding_army)
    units: list[BattleUnit] = []
    bounds = MapBounds(*NORMAL_MAP_BOUNDS)
    rng = ScriptedRandom([])  # never rolled -- the army is led

    _apply_monster_summoning_aid(units, commander, state, FIELD, bounds, rng=rng, **_aid_kwargs())

    assert units == []


def test_apply_monster_summoning_aid_ignores_a_non_matching_army_type():
    state, commander = _bearer_state(Treasure.MONSTER_AID_DRAGON)
    aiding_army = ArmyState(301, None, ArmyType.EAGLE_WING, Quality.AVERAGE, location=DEFENDER_HOME)
    state.add_army(aiding_army)
    units: list[BattleUnit] = []
    bounds = MapBounds(*NORMAL_MAP_BOUNDS)
    rng = ScriptedRandom([])

    _apply_monster_summoning_aid(units, commander, state, FIELD, bounds, rng=rng, **_aid_kwargs())

    assert units == []


def test_apply_monster_summoning_aid_ignores_a_non_adjacent_province():
    state, commander = _bearer_state(Treasure.MONSTER_AID_DRAGON)
    far_coord = HexCoord(20, 20)
    aiding_army = ArmyState(301, None, ArmyType.DRAGON_WING, Quality.AVERAGE, location=far_coord)
    state.add_army(aiding_army)
    units: list[BattleUnit] = []
    bounds = MapBounds(*NORMAL_MAP_BOUNDS)
    rng = ScriptedRandom([])

    _apply_monster_summoning_aid(units, commander, state, FIELD, bounds, rng=rng, **_aid_kwargs())

    assert units == []


def test_apply_monster_summoning_aid_uses_the_invasion_rate_for_a_kingdomless_army():
    state, commander = _bearer_state(Treasure.MONSTER_AID_DRAGON)
    aiding_army = ArmyState(301, None, ArmyType.DRAGON_WING, Quality.AVERAGE, location=DEFENDER_HOME)
    state.add_army(aiding_army)
    bounds = MapBounds(*NORMAL_MAP_BOUNDS)
    just_under = MONSTER_SUMMONING_INVASION_DEFECTION_CHANCE - 0.01
    just_over = MONSTER_SUMMONING_INVASION_DEFECTION_CHANCE

    hit_units: list[BattleUnit] = []
    _apply_monster_summoning_aid(
        hit_units, commander, state, FIELD, bounds, rng=ScriptedRandom([just_under]), **_aid_kwargs()
    )
    assert len(hit_units) == 1

    miss_units: list[BattleUnit] = []
    _apply_monster_summoning_aid(
        miss_units, commander, state, FIELD, bounds, rng=ScriptedRandom([just_over]), **_aid_kwargs()
    )
    assert miss_units == []


def test_apply_monster_summoning_aid_uses_the_halved_player_led_rate():
    state, commander = _bearer_state(Treasure.MONSTER_AID_DRAGON)
    state.add_kingdom(KingdomState(2, "Dragonia", Race.DRAGONS, Alignment.NEUTRAL, home_province=HexCoord(8, 8)))
    aiding_army = ArmyState(301, 2, ArmyType.DRAGON_WING, Quality.AVERAGE, location=DEFENDER_HOME)
    state.add_army(aiding_army)
    bounds = MapBounds(*NORMAL_MAP_BOUNDS)
    just_under = MONSTER_SUMMONING_PLAYER_LED_DEFECTION_CHANCE - 0.01
    just_over = MONSTER_SUMMONING_PLAYER_LED_DEFECTION_CHANCE

    hit_units: list[BattleUnit] = []
    _apply_monster_summoning_aid(
        hit_units, commander, state, FIELD, bounds, rng=ScriptedRandom([just_under]), **_aid_kwargs()
    )
    assert len(hit_units) == 1

    miss_units: list[BattleUnit] = []
    _apply_monster_summoning_aid(
        miss_units, commander, state, FIELD, bounds, rng=ScriptedRandom([just_over]), **_aid_kwargs()
    )
    assert miss_units == []
