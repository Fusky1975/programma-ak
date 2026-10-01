from __future__ import annotations

import pytest

from ak_engine.models.map import HexCoord, Terrain
from ak_engine.turn.movement import (
    NORMAL_MAP_BOUNDS,
    DIRECTION_NAME,
    Direction,
    HexOwnershipTier,
    MapBounds,
    NonAdjacentMoveError,
    direction_between,
    hex_distance,
    is_adjacent,
    neighbor_in_direction,
    neighbor_in_direction_wrapped,
    neighbors,
    resolve_move,
    step_toward_non_adjacent_target,
)

BOUNDS = MapBounds(*NORMAL_MAP_BOUNDS)


def test_interior_hex_has_six_neighbors():
    assert len(neighbors(HexCoord(5, 5), BOUNDS)) == 6


def test_corner_hex_neighbors_are_bounds_filtered():
    result = neighbors(HexCoord(0, 0), BOUNDS)
    assert all(BOUNDS.contains(c) for c in result)
    assert len(result) < 6


@pytest.mark.parametrize(
    "x,y",
    [(x, y) for x in range(NORMAL_MAP_BOUNDS[0]) for y in range(NORMAL_MAP_BOUNDS[1])],
)
def test_adjacency_is_symmetric_across_the_whole_map(x, y):
    origin = HexCoord(x, y)
    for neighbor in neighbors(origin, BOUNDS):
        assert origin in neighbors(neighbor, BOUNDS)


def test_is_adjacent_matches_neighbors():
    origin = HexCoord(5, 5)
    for neighbor in neighbors(origin, BOUNDS):
        assert is_adjacent(origin, neighbor, BOUNDS)
    assert not is_adjacent(origin, HexCoord(20, 10), BOUNDS)


# -- Phase 704: neighbor_in_direction()/direction_between() --


def test_neighbor_in_direction_matches_neighbors_for_every_direction():
    origin = HexCoord(5, 5)
    real_neighbors = set(neighbors(origin, BOUNDS))
    found = {neighbor_in_direction(origin, direction, BOUNDS) for direction in Direction}
    assert found == real_neighbors


def test_neighbor_in_direction_returns_none_off_the_map():
    origin = HexCoord(0, 0)
    for direction in Direction:
        candidate = neighbor_in_direction(origin, direction, BOUNDS)
        assert candidate is None or BOUNDS.contains(candidate)
    # At least one direction from a corner must fall outside bounds.
    assert any(neighbor_in_direction(origin, d, BOUNDS) is None for d in Direction)


def test_direction_between_resolves_every_real_neighbor():
    origin = HexCoord(5, 5)
    for direction in Direction:
        neighbor = neighbor_in_direction(origin, direction, BOUNDS)
        assert neighbor is not None
        assert direction_between(origin, neighbor) is direction


def test_direction_between_returns_none_for_a_non_adjacent_pair():
    assert direction_between(HexCoord(5, 5), HexCoord(20, 10)) is None


# -- Phase 981: neighbor_in_direction_wrapped() --


def test_neighbor_in_direction_wrapped_matches_the_unwrapped_version_away_from_edges():
    origin = HexCoord(5, 5)
    for direction in Direction:
        assert neighbor_in_direction_wrapped(origin, direction, BOUNDS.width, BOUNDS.height) == neighbor_in_direction(
            origin, direction, BOUNDS
        )


def test_neighbor_in_direction_wrapped_wraps_x_at_the_left_edge():
    origin = HexCoord(0, 4)
    for direction in (Direction.W,):
        wrapped = neighbor_in_direction_wrapped(origin, direction, BOUNDS.width, BOUNDS.height)
        assert wrapped is not None
        assert wrapped.x == BOUNDS.width - 1


def test_neighbor_in_direction_wrapped_wraps_x_at_the_right_edge():
    origin = HexCoord(BOUNDS.width - 1, 4)
    wrapped = neighbor_in_direction_wrapped(origin, Direction.E, BOUNDS.width, BOUNDS.height)
    assert wrapped is not None
    assert wrapped.x == 0


def test_neighbor_in_direction_wrapped_returns_none_off_the_top_or_bottom():
    top = HexCoord(5, 0)
    bottom = HexCoord(5, BOUNDS.height - 1)
    assert neighbor_in_direction_wrapped(top, Direction.NE, BOUNDS.width, BOUNDS.height) is None
    assert neighbor_in_direction_wrapped(top, Direction.NW, BOUNDS.width, BOUNDS.height) is None
    assert neighbor_in_direction_wrapped(bottom, Direction.SE, BOUNDS.width, BOUNDS.height) is None
    assert neighbor_in_direction_wrapped(bottom, Direction.SW, BOUNDS.width, BOUNDS.height) is None


def test_resolve_move_to_adjacent_hex():
    origin = HexCoord(5, 5)
    target = neighbors(origin, BOUNDS)[0]

    result = resolve_move(
        origin, target, BOUNDS,
        target_terrain=Terrain.PLAINS, target_explored_percent=0, explorer_skill=0,
    )

    assert result.new_coord == target
    assert result.battle_expected is False
    # Plains (50) x (skill 0 + 1) halved for the Move side effect = 25.
    assert result.exploration.new_percent == 25
    assert result.exploration.fully_explored is False


def test_resolve_move_flags_expected_battle_when_target_is_enemy_occupied():
    origin = HexCoord(5, 5)
    target = neighbors(origin, BOUNDS)[0]

    result = resolve_move(
        origin, target, BOUNDS,
        target_terrain=Terrain.PLAINS, target_explored_percent=0, explorer_skill=0,
        occupied_by_enemy=True,
    )

    assert result.battle_expected is True


def test_resolve_move_to_non_adjacent_hex_raises():
    origin = HexCoord(5, 5)
    far_away = HexCoord(20, 10)

    with pytest.raises(NonAdjacentMoveError):
        resolve_move(
            origin, far_away, BOUNDS,
            target_terrain=Terrain.PLAINS, target_explored_percent=0, explorer_skill=0,
        )


def test_resolve_move_to_non_adjacent_hex_succeeds_with_require_adjacent_false():
    # Phase 524: turn/move_execution.py's own Naval Hug Coastline branch
    # is the one real caller -- it has already verified the hop's own
    # legality itself, so this guard would otherwise wrongly reject it.
    origin = HexCoord(5, 5)
    far_away = HexCoord(20, 10)

    result = resolve_move(
        origin, far_away, BOUNDS,
        target_terrain=Terrain.PLAINS, target_explored_percent=0, explorer_skill=0,
        require_adjacent=False,
    )

    assert result.new_coord == far_away


# -- hex_distance (Phase 51, used by turn/spy_table.py's Pursue formula) --


def test_hex_distance_to_self_is_zero():
    assert hex_distance(HexCoord(5, 5), HexCoord(5, 5)) == 0


@pytest.mark.parametrize(
    "x,y",
    [(x, y) for x in range(1, NORMAL_MAP_BOUNDS[0] - 1) for y in range(1, NORMAL_MAP_BOUNDS[1] - 1)],
)
def test_hex_distance_to_every_neighbor_is_one(x, y):
    origin = HexCoord(x, y)
    for neighbor in neighbors(origin, BOUNDS):
        assert hex_distance(origin, neighbor) == 1


def test_hex_distance_is_symmetric():
    a, b = HexCoord(2, 3), HexCoord(9, 11)
    assert hex_distance(a, b) == hex_distance(b, a)


@pytest.mark.parametrize(
    "a,b,expected",
    [
        (HexCoord(5, 5), HexCoord(7, 5), 2),  # same row, 2 columns over
        (HexCoord(0, 0), HexCoord(5, 0), 5),  # same row, 5 columns over
        (HexCoord(0, 0), HexCoord(0, 10), 10),  # same column, straight down
    ],
)
def test_hex_distance_known_multi_hex_cases(a, b, expected):
    assert hex_distance(a, b) == expected


def _all_neutral(_coord: HexCoord) -> HexOwnershipTier:
    return HexOwnershipTier.NEUTRAL


def test_step_toward_non_adjacent_target_returns_current_when_already_there():
    target = HexCoord(5, 0)
    assert step_toward_non_adjacent_target(target, target, BOUNDS, _all_neutral) == target


def test_step_toward_non_adjacent_target_picks_the_single_closer_neighbor():
    # From (0,0) toward (5,0): only (1,0) is strictly closer than (0,0)'s own
    # distance-5; (0,0)'s other neighbor, (0,1), is distance 5 -- not closer.
    result = step_toward_non_adjacent_target(HexCoord(0, 0), HexCoord(5, 0), BOUNDS, _all_neutral)
    assert result == HexCoord(1, 0)


def test_step_toward_non_adjacent_target_stops_chasing_when_no_neighbor_is_closer():
    # From (0,0), both reachable neighbors are farther from (-5,-5) than
    # (0,0) itself is -- rulebook [3.1]: "stop chasing... if he can't find
    # a legal way to move closer to it in one phase."
    result = step_toward_non_adjacent_target(HexCoord(0, 0), HexCoord(-5, -5), BOUNDS, _all_neutral)
    assert result is None


def test_step_toward_non_adjacent_target_breaks_ties_by_ownership_tier():
    # From (5,5) toward (5,0): (4,4) and (5,4) tie at distance 4, both
    # strictly closer than (5,5)'s own distance-5. (Phase 314: these
    # tied coordinates flipped along with neighbors()'s own real-data-
    # sourced parity fix -- see that module's docstring.)
    current, target = HexCoord(5, 5), HexCoord(5, 0)
    tied_candidates = {HexCoord(4, 4), HexCoord(5, 4)}

    def prefer_4_4(coord: HexCoord) -> HexOwnershipTier:
        return HexOwnershipTier.OWNED_OR_ALLIED if coord == HexCoord(4, 4) else HexOwnershipTier.NEUTRAL

    def prefer_5_4(coord: HexCoord) -> HexOwnershipTier:
        return HexOwnershipTier.OWNED_OR_ALLIED if coord == HexCoord(5, 4) else HexOwnershipTier.NEUTRAL

    assert step_toward_non_adjacent_target(current, target, BOUNDS, prefer_4_4) == HexCoord(4, 4)
    assert step_toward_non_adjacent_target(current, target, BOUNDS, prefer_5_4) == HexCoord(5, 4)
    # sanity: both really are the tied, strictly-closer candidate set
    assert {
        c for c in neighbors(current, BOUNDS) if hex_distance(c, target) < hex_distance(current, target)
    } == tied_candidates


def test_hex_ownership_tier_priority_order_matches_rulebook_31():
    assert (
        HexOwnershipTier.OWNED_OR_ALLIED
        < HexOwnershipTier.ENEMY
        < HexOwnershipTier.HERO_OWNED
        < HexOwnershipTier.NEUTRAL
    )


def test_direction_enum_has_6_declared_values():
    assert len(Direction) == 6
    assert Direction.NE.value == 0
    assert Direction.NW.value == 5


# -- Phase 314: real-data-sourced adjacency confirmation ---------------------
#
# `Desktop/SE3__T*.K*` turn-report narrative text explicitly names each of a
# real province's 6 neighbors by direction and hex number (see module
# docstring for the full quote). Splitting each real hex number as
# ``(number // 100, number % 100)`` gives the HexCoord literals below --
# independent, real ground truth for neighbors(), not a self-referential
# check against this module's own offset tables.


def test_neighbors_matches_mongus_own_6_real_neighbors():
    # Kingdom 2, Turn 0: Mongu (#305) -- odd HexCoord.y (col=5).
    mongu = HexCoord(3, 5)
    real_neighbors = {
        HexCoord(3, 4),  # NE: Shasta (#304)
        HexCoord(4, 5),  # E: Moongard (#405)
        HexCoord(3, 6),  # SE: Big Sky (#306)
        HexCoord(2, 6),  # SW: Transylvania (#206)
        HexCoord(2, 5),  # W: Macondo (#205)
        HexCoord(2, 4),  # NW: Orielle (#204)
    }
    assert set(neighbors(mongu, BOUNDS)) == real_neighbors


def test_neighbors_matches_moonshine_seas_own_3_real_neighbors():
    # Kingdom 8, Turn 4: Moonshine Sea (#706) -- even HexCoord.y (col=6),
    # the opposite parity from Mongu above.
    moonshine_sea = HexCoord(7, 6)
    real_neighbors = {
        HexCoord(8, 5),  # NE: the Valiant Sea (#805)
        HexCoord(8, 6),  # E: the Buccaneer Sea (#806)
        HexCoord(8, 7),  # SE: the Third Sea (#807)
    }
    assert real_neighbors <= set(neighbors(moonshine_sea, BOUNDS))


def test_neighbors_matches_limericks_own_3_real_neighbors():
    # Kingdom 3, Turn 1: Limerick (#703) -- odd HexCoord.y (col=3), same
    # parity as Mongu but a different real province/kingdom/turn.
    limerick = HexCoord(7, 3)
    real_neighbors = {
        HexCoord(7, 2),  # NE: the Daedalus Sea (#702)
        HexCoord(8, 3),  # E: Gafsa (#803)
        HexCoord(6, 2),  # NW: Berga (#602)
    }
    assert real_neighbors <= set(neighbors(limerick, BOUNDS))


def test_direction_name_covers_every_enum_value():
    assert set(DIRECTION_NAME.keys()) == set(Direction)


def test_direction_name_matches_prose_txt_marker_verbatim():
    # PROSE.TXT: "*: Direction"; RUMORS.PAS: Say(dirname[_dir], spytype).
    assert DIRECTION_NAME[Direction.NE] == "northeast"
    assert DIRECTION_NAME[Direction.E] == "east"
    assert DIRECTION_NAME[Direction.SE] == "southeast"
    assert DIRECTION_NAME[Direction.SW] == "southwest"
    assert DIRECTION_NAME[Direction.W] == "west"
    assert DIRECTION_NAME[Direction.NW] == "northwest"


def test_direction_ordinal_order_matches_the_offset_tuples_ne_e_se_sw_w_nw_order():
    # _EVEN_ROW_OFFSETS/_ODD_ROW_OFFSETS are declared in this exact NE, E,
    # SE, SW, W, NW order (see their own comment) -- Direction's own
    # ordinal values (0-5) must line up the same way for the two to stay
    # in sync.
    assert [d.value for d in Direction] == [0, 1, 2, 3, 4, 5]
    assert [d.name for d in Direction] == ["NE", "E", "SE", "SW", "W", "NW"]
