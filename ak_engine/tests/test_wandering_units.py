"""Tests for Phase 781: autonomous wandering of unemployed Heroes and
mercenary armies (MERCHERO.md, backlog #20)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.game_state import ArmyState, GameState, KingdomState, LeaderState, ProvinceState
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.office import Office
from ak_engine.models.race import Race
from ak_engine.turn.combat import Quality
from ak_engine.turn.wandering_units import (
    HERO_WANDER_MAX_STEPS,
    WANDER_ATTRACTOR_ROLL_THRESHOLD,
    WANDER_AVOID_OWNER_ACCEPT_CHANCE,
    WANDER_ELIGIBLE_RACES,
    _accept_wander_direction,
    _army_type_terrain_excluded,
    _circular_direction_distance,
    _roll_main_direction,
    _roll_step_direction,
    _wander_density,
    _wander_step_hex,
    army_eligible_for_wander,
    hero_eligible_for_wander,
    MERCENARY_QUALITY_CHANGE_CHANCE,
    roll_mercenary_quality_change,
    resolve_army_wander,
    resolve_hero_wander,
    resolve_wandering,
)

from _helpers import ScriptedRandom

HOME = HexCoord(3, 9)


def build_state() -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.GOOD, HOME))
    state.add_kingdom(KingdomState(2, "Rivalia", Race.HUMAN, Alignment.EVIL, HexCoord(9, 9)))
    state.board_width = 5
    state.board_height = 5
    return state


def _province(coord: HexCoord, *, owner: int | None = None, terrain: Terrain = Terrain.PLAINS) -> ProvinceState:
    return ProvinceState(coord=coord, terrain=terrain, race=Race.HUMAN, owner_kingdom_id=owner)


# -- _wander_step_hex(): same worked examples as SCAR.md's own _scar_terrain_step_hex() --


def test_wander_step_hex_worked_examples_from_scar_md():
    assert _wander_step_hex(HexCoord(2, 2), 1, 5, 5) == HexCoord(2, 1)
    assert _wander_step_hex(HexCoord(2, 3), 1, 5, 5) == HexCoord(3, 2)
    assert _wander_step_hex(HexCoord(0, 2), 5, 5, 5) == HexCoord(4, 2)  # west wraps
    assert _wander_step_hex(HexCoord(4, 2), 2, 5, 5) == HexCoord(0, 2)  # east wraps
    assert _wander_step_hex(HexCoord(2, 0), 1, 5, 5) is None  # off the top edge


# -- direction rolls --


def test_roll_main_direction_uses_the_full_0_to_1_range():
    rng = ScriptedRandom([0.0])
    assert _roll_main_direction(rng) == 1
    rng = ScriptedRandom([0.999])
    assert _roll_main_direction(rng) == 6


def test_circular_direction_distance_wraps_at_4_and_5():
    assert _circular_direction_distance(1, 5) == 2  # |1-5|=4 -> wraps to 2
    assert _circular_direction_distance(1, 6) == 1  # |1-6|=5 -> wraps to 1
    assert _circular_direction_distance(2, 2) == 0
    assert _circular_direction_distance(1, 3) == 2


def test_roll_step_direction_rerolls_until_within_circular_distance_1():
    # main_direction=1: only 6, 1, 2 are within distance 1. Script a
    # rejected roll (direction 4, distance 2) then an accepted one (2).
    rng = ScriptedRandom([3 / 6, 1 / 6])
    assert _roll_step_direction(rng, 1) == 2


# -- _wander_density() --


def test_wander_density_counts_only_employed_leaders_and_armies():
    state = build_state()
    coord = HexCoord(2, 2)
    state.add_leader(LeaderState(1, 1, "Employed Hero", coord))
    state.add_leader(LeaderState(2, None, "Independent Hero", coord))
    state.add_army(ArmyState(1, 1, ArmyType.BOWMEN, Quality.AVERAGE, coord))
    state.add_army(ArmyState(2, None, ArmyType.BOWMEN, Quality.AVERAGE, coord))
    assert _wander_density(state, coord) == 2
    assert _wander_density(state, HexCoord(0, 0)) == 0


# -- _army_type_terrain_excluded() --


def test_army_type_terrain_excluded_sea_types_need_sea():
    assert _army_type_terrain_excluded(ArmyType.FLEET, Terrain.PLAINS) is True
    assert _army_type_terrain_excluded(ArmyType.WHALES, Terrain.PLAINS) is True
    assert _army_type_terrain_excluded(ArmyType.MERMEN, Terrain.PLAINS) is True
    assert _army_type_terrain_excluded(ArmyType.FLEET, Terrain.SEA) is False


def test_army_type_terrain_excluded_ents_need_land():
    assert _army_type_terrain_excluded(ArmyType.ENTS, Terrain.SEA) is True
    assert _army_type_terrain_excluded(ArmyType.ENTS, Terrain.PLAINS) is False


def test_army_type_terrain_excluded_ordinary_land_type_never_excluded():
    assert _army_type_terrain_excluded(ArmyType.BOWMEN, Terrain.PLAINS) is False
    assert _army_type_terrain_excluded(ArmyType.BOWMEN, Terrain.SEA) is False


# -- _accept_wander_direction(): MERCHERO's own worked probability table --


def test_accept_wander_direction_avoid_owner_match_is_harsh():
    state = build_state()
    state.add_province(_province(HexCoord(2, 2), owner=None))
    # direction=2 from (1,2) steps to (2,2); avoid_owner=None matches the
    # unowned neighbor's own owner_kingdom_id (None == None) -- the harsh branch.
    rng = ScriptedRandom([WANDER_AVOID_OWNER_ACCEPT_CHANCE - 0.001])
    result = _accept_wander_direction(state, HexCoord(1, 2), 2, None, None, _bounds(state), rng)
    assert result == HexCoord(2, 2)

    rng = ScriptedRandom([WANDER_AVOID_OWNER_ACCEPT_CHANCE + 0.001])
    result = _accept_wander_direction(state, HexCoord(1, 2), 2, None, None, _bounds(state), rng)
    assert result is None


def test_accept_wander_direction_no_reference_king_province_always_accepts():
    state = build_state()
    state.add_leader(LeaderState(1, 1, "King", HexCoord(2, 2), is_king=True))
    state.add_province(_province(HexCoord(2, 2), owner=1))
    # avoid_owner=99 (never matches the real neighbor owner 1) -- skips
    # the harsh branch; roll low on both remaining rolls so neither the
    # attractor branch nor the low-roll branch decide it -- falls to the
    # "neighbor owner is a real King" unconditional accept.
    rng = ScriptedRandom([0.0, 0.9])
    result = _accept_wander_direction(state, HexCoord(1, 2), 2, 99, None, _bounds(state), rng)
    assert result == HexCoord(2, 2)


def test_accept_wander_direction_no_reference_independent_province_20_percent():
    state = build_state()
    state.add_province(_province(HexCoord(2, 2), owner=1))  # owner has no King registered
    rng = ScriptedRandom([0.9, WANDER_ATTRACTOR_ROLL_THRESHOLD - 0.01])
    result = _accept_wander_direction(state, HexCoord(1, 2), 2, 99, None, _bounds(state), rng)
    assert result == HexCoord(2, 2)

    rng = ScriptedRandom([0.9, WANDER_ATTRACTOR_ROLL_THRESHOLD + 0.01])
    result = _accept_wander_direction(state, HexCoord(1, 2), 2, 99, None, _bounds(state), rng)
    assert result is None


def test_accept_wander_direction_reference_closer_always_accepts():
    # Bug fix: direction=2 steps purely horizontally (current and
    # neighbor both stay on y=2), so hex_distance_wrapped()'s own
    # per-row parity bit is identical on both sides of every distance
    # comparison this test makes and cancels out algebraically -- the
    # same (now-fixed) row-parity bug a previous round found in that
    # function would have produced byte-identical results here either
    # way, so this test could never catch a regression of that fix.
    # direction=3 steps diagonally (current (1,2) -> neighbor (1,3)),
    # putting them on different rows, and (0,3) is a real coordinate
    # (found by search) where the two conventions actually disagree:
    # the real convention says (1,3) is strictly closer to (0,3) than
    # (1,2) is (distances 1 vs 2), while the old, buggy convention saw
    # them as tied (1 vs 1) -- not closer -- and would have fallen
    # through to the third roll instead of accepting immediately here.
    state = build_state()
    attractor_id = 42
    state.add_leader(LeaderState(attractor_id, None, "Attractor", HexCoord(0, 3)))
    state.add_province(_province(HexCoord(1, 3), owner=None))
    rng = ScriptedRandom([WANDER_ATTRACTOR_ROLL_THRESHOLD + 0.01])
    result = _accept_wander_direction(state, HexCoord(1, 2), 3, 99, attractor_id, _bounds(state), rng)
    assert result == HexCoord(1, 3)


def test_accept_wander_direction_reference_farther_falls_through_to_third_roll():
    # Bug fix: same row-parity blind spot as the "closer" test above --
    # direction=2 keeps current and neighbor on the same row, so the
    # fixed and the old, buggy hex_distance_wrapped() conventions
    # always agreed here too. direction=3 (current (1,2) -> neighbor
    # (1,3)) and attractor (2,3) (found by search) make them disagree:
    # the real convention says (1,3) is NOT closer to (2,3) than (1,2)
    # is (both distance 1, a tie) -- falls through to the third roll,
    # as this test exercises -- while the old, buggy convention saw
    # (1,3) as strictly closer (1 vs 2) and would have accepted
    # immediately, skipping the third roll this test is actually about.
    state = build_state()
    attractor_id = 42
    state.add_leader(LeaderState(attractor_id, None, "Attractor", HexCoord(2, 3)))
    state.add_province(_province(HexCoord(1, 3), owner=None))
    rng = ScriptedRandom([WANDER_ATTRACTOR_ROLL_THRESHOLD + 0.01, WANDER_ATTRACTOR_ROLL_THRESHOLD - 0.01])
    result = _accept_wander_direction(state, HexCoord(1, 2), 3, 99, attractor_id, _bounds(state), rng)
    assert result == HexCoord(1, 3)

    rng = ScriptedRandom([WANDER_ATTRACTOR_ROLL_THRESHOLD + 0.01, WANDER_ATTRACTOR_ROLL_THRESHOLD + 0.01])
    result = _accept_wander_direction(state, HexCoord(1, 2), 3, 99, attractor_id, _bounds(state), rng)
    assert result is None


def test_accept_wander_direction_off_board_step_returns_none():
    state = build_state()
    rng = ScriptedRandom([])
    # direction=1 from y=0 steps off the top edge -- HexCoord(0,0) with board_height=5.
    result = _accept_wander_direction(state, HexCoord(0, 0), 1, None, None, _bounds(state), rng)
    assert result is None


def _bounds(state: GameState):
    from ak_engine.turn.movement import MapBounds

    return MapBounds(state.board_width, state.board_height)


# -- eligibility gates --


def test_hero_eligible_for_wander_requires_kingdomless_and_no_armies():
    state = build_state()
    state.add_leader(LeaderState(1, 1, "Employed", HOME))
    state.add_leader(LeaderState(2, None, "Independent", HOME))
    state.add_army(ArmyState(1, None, ArmyType.BOWMEN, Quality.AVERAGE, HOME, commanded_by=2))
    assert hero_eligible_for_wander(state, state.leaders[1], {}) is False  # employed
    assert hero_eligible_for_wander(state, state.leaders[2], {}) is False  # commands an army


def test_hero_eligible_for_wander_race_gate():
    state = build_state()
    state.add_leader(LeaderState(1, None, "Troll Hero", HOME, race=Race.TROLLISH))
    state.add_leader(LeaderState(2, None, "Human Hero", HOME, race=Race.HUMAN))
    assert hero_eligible_for_wander(state, state.leaders[1], {}) is False
    assert hero_eligible_for_wander(state, state.leaders[2], {}) is True


def test_hero_eligible_for_wander_king_orders_flag_gate():
    state = build_state()
    state.add_province(_province(HOME, owner=1))
    state.add_leader(LeaderState(99, 1, "King", HOME, is_king=True))
    state.add_leader(LeaderState(2, None, "Wanderer", HOME))
    assert hero_eligible_for_wander(state, state.leaders[2], {1: False}) is False
    assert hero_eligible_for_wander(state, state.leaders[2], {1: True}) is True
    # No province data at all -- no owner, no gate.
    state2 = build_state()
    state2.add_leader(LeaderState(2, None, "Wanderer", HOME))
    assert hero_eligible_for_wander(state2, state2.leaders[2], {}) is True


def test_army_eligible_for_wander_requires_kingdomless():
    state = build_state()
    state.add_army(ArmyState(1, 1, ArmyType.BOWMEN, Quality.AVERAGE, HOME))
    state.add_army(ArmyState(2, None, ArmyType.BOWMEN, Quality.AVERAGE, HOME))
    assert army_eligible_for_wander(state, state.armies[1], {}) is False
    assert army_eligible_for_wander(state, state.armies[2], {}) is True


def test_army_eligible_for_wander_king_orders_flag_gate():
    state = build_state()
    state.add_province(_province(HOME, owner=1))
    state.add_leader(LeaderState(99, 1, "King", HOME, is_king=True))
    state.add_army(ArmyState(1, None, ArmyType.BOWMEN, Quality.AVERAGE, HOME))
    assert army_eligible_for_wander(state, state.armies[1], {1: False}) is False
    assert army_eligible_for_wander(state, state.armies[1], {1: True}) is True


# -- resolve_hero_wander(): end-to-end on a small synthetic board --


def test_resolve_hero_wander_birth_coordinate_out_of_range_skips_filter_first_step():
    state = build_state()
    leader = LeaderState(1, None, "Wanderer", HexCoord(2, 2), birth_x=99, birth_y=0)
    state.add_leader(leader)
    # main_direction roll, then step-direction roll (direction 2, accepted
    # unconditionally since the filter is skipped this step), then the
    # continuation mask roll fails to stop further stepping.
    rng = ScriptedRandom([0.0, 1 / 6, 0.0])
    destination = resolve_hero_wander(state, leader, rng)
    assert destination == HexCoord(3, 2)


def test_resolve_hero_wander_exhausts_the_5_step_counter():
    state = build_state()
    leader = LeaderState(1, None, "Wanderer", HexCoord(0, 2), birth_x=99, birth_y=0)
    state.add_leader(leader)
    # Step east (direction 2) five times, wrapping around the 5-wide board.
    # main_direction=2 (roll 1/6) so every step-direction roll of 1/6
    # lands on 2 immediately (circular distance 0, no rerolling). Step 1
    # skips the political filter entirely (out-of-range birth); steps 2-5
    # apply it, and since avoid_owner=None and every neighbor here is
    # unowned (None == None), each lands in the harsh 0.5% branch --
    # scripted to accept (0.0). The continuation-mask roll (0.04 -> bit 2
    # set -> keep going) is consumed after every step except the 5th,
    # which breaks immediately on reaching the step cap.
    rolls = [1 / 6]  # main direction = 2
    for step in range(1, 6):
        rolls.append(1 / 6)  # step direction = 2
        if step > 1:
            rolls.append(0.0)  # harsh-branch accept (filter applies from step 2 on)
        if step < 5:
            rolls.append(0.04)  # continuation mask roll -- keep going
    rng = ScriptedRandom(rolls)
    destination = resolve_hero_wander(state, leader, rng)
    assert destination == HexCoord(0, 2)  # 5 steps east on a 5-wide board wraps home


def test_resolve_hero_wander_does_not_mutate_leader_location():
    state = build_state()
    leader = LeaderState(1, None, "Wanderer", HexCoord(2, 2))
    state.add_leader(leader)
    rng = ScriptedRandom([0.0] * 30)
    resolve_hero_wander(state, leader, rng)
    assert leader.location == HexCoord(2, 2)


# -- resolve_army_wander(): movement budget + sea-only continuation --


def test_resolve_army_wander_stops_when_movement_points_exhausted():
    state = build_state()
    army = ArmyState(1, None, ArmyType.BOWMEN, Quality.AVERAGE, HexCoord(2, 2), movement_points=0)
    state.add_army(army)
    rng = ScriptedRandom([0.0])
    destination = resolve_army_wander(state, army, rng)
    assert destination == HexCoord(2, 2)
    assert army.movement_points == 0


def test_resolve_army_wander_decrements_movement_points_and_stops_on_land():
    state = build_state()
    army = ArmyState(1, None, ArmyType.BOWMEN, Quality.AVERAGE, HexCoord(1, 2), movement_points=3)
    state.add_army(army)
    # main direction, step direction=2 (east, to (2,2), unowned -> harsh branch)
    rng = ScriptedRandom([0.0, 1 / 6, 0.0])
    destination = resolve_army_wander(state, army, rng)
    assert destination == HexCoord(2, 2)
    assert army.movement_points == 2  # decremented once, then stopped (land terrain)


def test_resolve_army_wander_sea_type_army_terrain_excluded_from_land():
    state = build_state()
    army = ArmyState(1, None, ArmyType.FLEET, Quality.AVERAGE, HexCoord(1, 2), movement_points=3)
    state.add_army(army)
    state.add_province(_province(HexCoord(2, 2), owner=None, terrain=Terrain.PLAINS))
    rng = ScriptedRandom([0.0, 1 / 6, 0.0])
    destination = resolve_army_wander(state, army, rng)
    assert destination == HexCoord(1, 2)  # rejected, stayed put
    assert army.movement_points == 3  # never spent


def test_resolve_army_wander_continues_across_sea():
    state = build_state()
    army = ArmyState(1, None, ArmyType.FLEET, Quality.AVERAGE, HexCoord(1, 2), movement_points=3)
    state.add_army(army)
    state.add_province(_province(HexCoord(2, 2), owner=None, terrain=Terrain.SEA))
    state.add_province(_province(HexCoord(3, 2), owner=None, terrain=Terrain.SEA))
    # avoid_owner is always None for an army, so every unowned neighbor
    # here (all of them) lands in the harsh 0.5% accept branch -- each
    # step consumes a direction roll + an accept roll. The 3rd attempt,
    # from (3,2) toward (4,2), finds no province data there (NO_TERRAIN,
    # not Sea) -- excluded outright for a Fleet, so the loop stops
    # without spending that 3rd movement point.
    rng = ScriptedRandom([1 / 6, 1 / 6, 0.0, 1 / 6, 0.0, 1 / 6, 0.0])
    destination = resolve_army_wander(state, army, rng)
    assert destination == HexCoord(3, 2)
    assert army.movement_points == 1


# -- roll_mercenary_quality_change() (user table of 2026-11-24) --


def _band(quality: Quality) -> tuple[GameState, ArmyState]:
    state = build_state()
    army = ArmyState(1, None, ArmyType.BOWMEN, quality, HOME, is_mercenary=True)
    state.add_army(army)
    return state, army


def test_the_mercenary_quality_table_matches_the_users_percentages():
    assert MERCENARY_QUALITY_CHANGE_CHANCE == {
        Quality.GREEN: (0.07, 0.07),
        Quality.AVERAGE: (0.07, 0.07),
        Quality.VETERAN: (0.02, 0.07),
        Quality.CRACK: (0.0, 0.05),
    }


def test_each_quality_rises_and_sinks_by_one_level_on_its_own_rolls():
    expectations = [
        (Quality.GREEN, 0.06, "up", Quality.AVERAGE),
        (Quality.GREEN, 0.13, "down", Quality.DEPLETED),
        (Quality.AVERAGE, 0.06, "up", Quality.VETERAN),
        (Quality.AVERAGE, 0.13, "down", Quality.GREEN),
        (Quality.VETERAN, 0.01, "up", Quality.CRACK),
        (Quality.VETERAN, 0.08, "down", Quality.AVERAGE),
        (Quality.CRACK, 0.04, "down", Quality.VETERAN),
    ]
    for start, roll, kind, end in expectations:
        state, army = _band(start)
        event = roll_mercenary_quality_change(state, army, ScriptedRandom([roll]))
        assert (event.kind, event.new_quality, army.quality) == (kind, end, end), (start, roll)
        assert (event.army_id, event.coord) == (1, HOME)


def test_a_roll_above_both_chances_changes_nothing():
    for start in (Quality.GREEN, Quality.AVERAGE, Quality.VETERAN, Quality.CRACK):
        state, army = _band(start)
        assert roll_mercenary_quality_change(state, army, ScriptedRandom([0.5])) is None
        assert army.quality is start


def test_crack_never_rises_and_veteran_needs_a_roll_under_two_percent():
    state, army = _band(Quality.CRACK)
    assert roll_mercenary_quality_change(state, army, ScriptedRandom([0.0])).kind == "down"  # no rise branch at all
    state, army = _band(Quality.VETERAN)
    assert roll_mercenary_quality_change(state, army, ScriptedRandom([0.03])).kind == "down"  # 3% is past the 2% rise


def test_a_depleted_band_dissolves_with_twenty_percent_each_turn():
    state, army = _band(Quality.DEPLETED)
    event = roll_mercenary_quality_change(state, army, ScriptedRandom([0.19]))
    assert event.kind == "dissolved" and event.new_quality is None
    assert 1 not in state.armies

    state, army = _band(Quality.DEPLETED)
    assert roll_mercenary_quality_change(state, army, ScriptedRandom([0.2])) is None
    assert 1 in state.armies and army.quality is Quality.DEPLETED


# -- resolve_wandering(): the once-per-turn dispatch loop --


def test_resolve_wandering_no_independent_entities_is_a_no_op():
    state = build_state()
    state.add_leader(LeaderState(1, 1, "Employed", HOME))
    relocations = resolve_wandering(state, {}, ScriptedRandom([0.9] * 5))
    assert relocations == []


def test_resolve_wandering_employed_hero_never_reaches_the_access_roll():
    # An employed Hero (kingdom_id is not None) is filtered out of the
    # candidate population before the access-roll loop even starts --
    # `resolve_wandering()`'s own docstring "unconditionally, even for an
    # object the eligibility gates will reject" scopes only to the
    # *independent* population it rolls over, not to employment itself.
    state = build_state()
    state.add_leader(LeaderState(1, 1, "Employed", HOME))
    rng = ScriptedRandom([])  # any .random() call here would raise IndexError
    relocations = resolve_wandering(state, {}, rng)
    assert relocations == []


def test_resolve_wandering_race_ineligible_independent_hero_still_consumes_its_access_roll():
    # MERCHERO section 12.4 point 4's own RNG-fidelity warning: the access
    # roll is drawn for every *independent* Hero, even one the later race
    # gate will reject -- Troll is independent but not in
    # WANDER_ELIGIBLE_RACES (see test_hero_eligible_for_wander_race_gate).
    state = build_state()
    state.add_leader(LeaderState(1, None, "Troll Hero", HOME, race=Race.TROLLISH))
    # A single accessed roll (< HERO_WANDER_ACCESS_CHANCE) -- a second
    # .random() call would raise IndexError.
    rng = ScriptedRandom([0.0])
    relocations = resolve_wandering(state, {}, rng)
    assert relocations == []
    # `relocations == []` alone would also hold if the access roll were
    # never drawn at all -- this confirms it genuinely was.
    assert rng._randoms == []


def test_resolve_wandering_relocates_an_eligible_hero_and_updates_location():
    state = build_state()
    leader = LeaderState(1, None, "Wanderer", HexCoord(2, 2))
    state.add_leader(leader)
    rolls = [0.0]  # access roll (< 0.5 -> accessed)
    rolls += [0.0, 1 / 6, 0.0]  # main direction, step direction, harsh-branch accept
    rolls += [0.99]  # continuation mask stops
    rng = ScriptedRandom(rolls)
    relocations = resolve_wandering(state, {}, rng)
    assert len(relocations) == 1
    assert relocations[0].kind == "hero"
    assert relocations[0].entity_id == 1
    assert leader.location == relocations[0].destination
    assert relocations[0].destination != HexCoord(2, 2)


def test_resolve_wandering_rolls_every_free_mercenary_band_for_a_quality_change():
    state = build_state()
    band = ArmyState(1, None, ArmyType.BOWMEN, Quality.DEPLETED, HOME, is_mercenary=True)
    state.add_army(band)
    events: list = []
    # access roll fails (int(0.9*6) >= 3), then the quality roll dissolves the Depleted band.
    relocations = resolve_wandering(state, {}, ScriptedRandom([0.9, 0.1]), events)

    assert relocations == []
    assert [(e.army_id, e.kind) for e in events] == [(1, "dissolved")]
    assert 1 not in state.armies


def test_resolve_wandering_leaves_an_unowned_native_garrison_alone():
    # A kingdomless army that is not a mercenary band (a province's own native garrison) takes no
    # part in the mercenary quality rule.
    state = build_state()
    state.add_army(ArmyState(1, None, ArmyType.BOWMEN, Quality.DEPLETED, HOME))
    events: list = []

    resolve_wandering(state, {}, ScriptedRandom([0.9]), events)  # only the access roll is drawn

    assert events == [] and 1 in state.armies


def test_resolve_wandering_skips_a_band_disbanded_this_turn():
    state = build_state()
    state.add_army(ArmyState(1, None, ArmyType.BOWMEN, Quality.DEPLETED, HOME, is_mercenary=True, unhireable_this_turn=True))
    events: list = []

    resolve_wandering(state, {}, ScriptedRandom([0.9]), events)

    assert events == [] and 1 in state.armies