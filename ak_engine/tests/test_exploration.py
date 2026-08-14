from __future__ import annotations

import random

import pytest

from ak_engine.models.alignment import Alignment
from ak_engine.models.discovery import Discovery
from ak_engine.models.feature import Feature, FeatureType
from ak_engine.models.game_state import GameState, KingdomState, ProvinceState
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.monster import Monster
from ak_engine.models.race import Race
from ak_engine.turn.exploration import (
    SOCIETY_MAPS_REVEAL_PERCENT,
    discover_features,
    receive_society_maps,
    resolve_explore,
    resolve_find_mines,
)

from _helpers import ScriptedRandom

LOCATION = HexCoord(4, 4)


def test_full_exploration_number_matches_rulebook_formula():
    # Plains basic exploration number is 50; skill 1 -> 50 * (1+1) = 100%.
    result = resolve_explore(0, Terrain.PLAINS, explorer_skill=1)
    assert result.new_percent == 100
    assert result.delta_applied == 100
    assert result.fully_explored is True


def test_low_skill_low_terrain_does_not_fully_explore():
    # Jungle basic exploration number is 10; skill 0 -> 10 * (0+1) = 10%.
    result = resolve_explore(0, Terrain.JUNGLE, explorer_skill=0)
    assert result.new_percent == 10
    assert result.delta_applied == 10
    assert result.fully_explored is False


def test_exploration_percent_is_capped_at_100():
    result = resolve_explore(90, Terrain.PLAINS, explorer_skill=9)
    assert result.new_percent == 100
    assert result.delta_applied == 10  # only 10 points were needed to reach the cap
    assert result.fully_explored is True


def test_partial_exploration_from_move_is_half_effect():
    full = resolve_explore(0, Terrain.FOREST, explorer_skill=2)
    partial = resolve_explore(0, Terrain.FOREST, explorer_skill=2, partial=True)
    assert partial.new_percent == full.new_percent // 2


@pytest.mark.parametrize("bad_percent", [-1, 101])
def test_invalid_current_percent_raises(bad_percent):
    with pytest.raises(ValueError):
        resolve_explore(bad_percent, Terrain.PLAINS, explorer_skill=0)


@pytest.mark.parametrize("bad_skill", [-1, 10])
def test_invalid_explorer_skill_raises(bad_skill):
    with pytest.raises(ValueError):
        resolve_explore(0, Terrain.PLAINS, explorer_skill=bad_skill)


# -- Phase 507: real formula (min(4,S)+1, Military Maps, Difficult Terrain) --


def test_skill_multiplier_stops_growing_past_level_4():
    # Real formula: E = min(4,S)+1 -- SAL.X2:26/AK.EXE:0xA909-0xA9D0.
    # Desert (B=25): level 4 -> 25*5=125% (capped to 100); level 5 gives
    # the identical raw number, not 25*6=150 the old uncapped formula
    # would have produced -- both still cap to 100, so use delta_applied
    # against a higher starting percent to see the real ceiling directly.
    at_level_4 = resolve_explore(0, Terrain.JUNGLE, explorer_skill=4)
    at_level_5 = resolve_explore(0, Terrain.JUNGLE, explorer_skill=5)
    at_level_9 = resolve_explore(0, Terrain.JUNGLE, explorer_skill=9)
    # Jungle B=10: level 4 -> 10*5=50; level 5-9 all also give 10*5=50,
    # not 10*6=60/10*10=100 the old uncapped skill+1 formula would give.
    assert at_level_4.new_percent == 50
    assert at_level_5.new_percent == 50
    assert at_level_9.new_percent == 50


def test_difficult_terrain_adds_10_flat_to_the_basic_exploration_number():
    # Plain: 50 -> 60 with Difficult Terrain, not a 10% multiplier.
    without = resolve_explore(0, Terrain.PLAINS, explorer_skill=0)
    with_difficult_terrain = resolve_explore(0, Terrain.PLAINS, explorer_skill=0, has_difficult_terrain=True)
    assert without.new_percent == 50
    assert with_difficult_terrain.new_percent == 60


def test_military_maps_raises_the_cap_to_200():
    result = resolve_explore(150, Terrain.PLAINS, explorer_skill=4, has_military_maps=True)
    assert result.new_percent == 200
    assert result.fully_explored is True  # still >= 100, the ordinary completion threshold


def test_military_maps_alone_adds_no_points():
    # Military Maps only raises the cap -- the per-order gain is unaffected.
    without = resolve_explore(0, Terrain.PLAINS, explorer_skill=0)
    with_military_maps = resolve_explore(0, Terrain.PLAINS, explorer_skill=0, has_military_maps=True)
    assert without.new_percent == with_military_maps.new_percent == 50


def test_current_percent_above_100_is_invalid_without_military_maps():
    with pytest.raises(ValueError):
        resolve_explore(150, Terrain.PLAINS, explorer_skill=0)


def test_current_percent_up_to_200_is_valid_with_military_maps():
    result = resolve_explore(150, Terrain.PLAINS, explorer_skill=0, has_military_maps=True)
    assert result.new_percent == 200


# -- Phase 509: resolve_find_mines --


def test_resolve_find_mines_success_returns_gold_in_range():
    # A successful roll consumes a second .random() call internally, via
    # rng.randint()'s own _randbelow() -- padded with a second value.
    rng = ScriptedRandom([0.0, 0.5])  # always < any positive chance
    gold = resolve_find_mines(Terrain.MTNS, attempts_so_far=0, current_bonus=0, rng=rng)
    assert 1 <= gold <= 3


def test_resolve_find_mines_failure_returns_zero():
    rng = ScriptedRandom([0.99])
    assert resolve_find_mines(Terrain.MTNS, attempts_so_far=0, current_bonus=0, rng=rng) == 0


def test_resolve_find_mines_mountains_base_chance_is_35_percent():
    just_under = ScriptedRandom([0.34, 0.5])
    assert resolve_find_mines(Terrain.MTNS, attempts_so_far=0, current_bonus=0, rng=just_under) >= 1
    at_threshold = ScriptedRandom([0.35])
    assert resolve_find_mines(Terrain.MTNS, attempts_so_far=0, current_bonus=0, rng=at_threshold) == 0


def test_resolve_find_mines_other_land_base_chance_is_15_percent():
    for terrain in (Terrain.PLAINS, Terrain.DESERT, Terrain.JUNGLE, Terrain.FOREST):
        just_under = ScriptedRandom([0.14, 0.5])
        assert resolve_find_mines(terrain, attempts_so_far=0, current_bonus=0, rng=just_under) >= 1
        at_threshold = ScriptedRandom([0.15])
        assert resolve_find_mines(terrain, attempts_so_far=0, current_bonus=0, rng=at_threshold) == 0


def test_resolve_find_mines_chance_halves_per_prior_attempt():
    # Mountains base 0.35 -> after 1 prior attempt, effective chance 0.175.
    just_under = ScriptedRandom([0.17, 0.5])
    assert resolve_find_mines(Terrain.MTNS, attempts_so_far=1, current_bonus=0, rng=just_under) >= 1
    at_threshold = ScriptedRandom([0.175])
    assert resolve_find_mines(Terrain.MTNS, attempts_so_far=1, current_bonus=0, rng=at_threshold) == 0


def test_resolve_find_mines_sea_and_no_terrain_never_yield_a_mine():
    assert resolve_find_mines(Terrain.SEA, attempts_so_far=0, current_bonus=0, rng=ScriptedRandom([0.0])) == 0
    assert resolve_find_mines(Terrain.NO_TERRAIN, attempts_so_far=0, current_bonus=0, rng=ScriptedRandom([0.0])) == 0


def test_resolve_find_mines_returns_zero_once_cap_reached():
    rng = ScriptedRandom([0.0])
    assert resolve_find_mines(Terrain.MTNS, attempts_so_far=0, current_bonus=10, rng=rng) == 0


def test_resolve_find_mines_caps_gold_at_the_remaining_headroom():
    rng = ScriptedRandom([0.0, 0.5])
    gold = resolve_find_mines(Terrain.MTNS, attempts_so_far=0, current_bonus=9, rng=rng)
    assert gold == 1


# -- Phase 510: receive_society_maps --


def _state_with_provinces(count: int) -> GameState:
    state = GameState()
    for i in range(count):
        state.add_province(ProvinceState(HexCoord(i, 0), Terrain.PLAINS, Race.HUMAN))
    return state


def test_receive_society_maps_reveals_requested_count():
    state = _state_with_provinces(5)
    revealed = receive_society_maps(state, kingdom_id=1, count=3, rng=random.Random(0))
    assert len(revealed) == 3
    for coord in revealed:
        assert state.provinces[coord].explored_percent_by_kingdom[1] == SOCIETY_MAPS_REVEAL_PERCENT


def test_receive_society_maps_zero_count_reveals_nothing():
    state = _state_with_provinces(5)
    assert receive_society_maps(state, kingdom_id=1, count=0, rng=random.Random(0)) == []


def test_receive_society_maps_never_picks_an_already_known_province():
    state = _state_with_provinces(3)
    coords = list(state.provinces)
    state.provinces[coords[0]].explored_percent_by_kingdom[1] = 100  # already known
    state.provinces[coords[1]].explored_percent_by_kingdom[1] = 5  # already known, low %

    revealed = receive_society_maps(state, kingdom_id=1, count=5, rng=random.Random(0))

    assert revealed == [coords[2]]


def test_receive_society_maps_caps_at_available_unknown_provinces():
    state = _state_with_provinces(2)
    revealed = receive_society_maps(state, kingdom_id=1, count=10, rng=random.Random(0))
    assert len(revealed) == 2


def test_receive_society_maps_is_per_kingdom():
    state = _state_with_provinces(3)
    receive_society_maps(state, kingdom_id=1, count=3, rng=random.Random(0))
    # A different kingdom's own knowledge is untouched -- still 0 known.
    revealed_for_2 = receive_society_maps(state, kingdom_id=2, count=3, rng=random.Random(1))
    assert len(revealed_for_2) == 3


# -- Phase 242: discover_features --


def _state_with_feature(**feature_kwargs) -> tuple[GameState, Feature]:
    state = GameState()
    feature = Feature(
        feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER, **feature_kwargs
    )
    state.add_feature(feature)
    return state, feature


def test_discover_features_success_sets_full_disclosure():
    state, feature = _state_with_feature()
    discovered = discover_features(state, LOCATION, kingdom_id=1, exploration_percent=100, rng=random.Random(0))
    assert discovered == [feature]
    assert feature.discovery_level(1) == 3


def test_discover_features_zero_percent_never_discovers():
    state, feature = _state_with_feature()
    discovered = discover_features(state, LOCATION, kingdom_id=1, exploration_percent=0, rng=random.Random(0))
    assert discovered == []
    assert feature.discovery_level(1) == 0


def test_discover_features_skips_already_discovered():
    state, feature = _state_with_feature()
    feature.discovered_by_kingdom[1] = 3
    discovered = discover_features(state, LOCATION, kingdom_id=1, exploration_percent=100, rng=random.Random(0))
    assert discovered == []


def test_discover_features_skips_magically_hidden():
    state, feature = _state_with_feature(magically_hidden=True)
    discovered = discover_features(state, LOCATION, kingdom_id=1, exploration_percent=100, rng=random.Random(0))
    assert discovered == []
    assert feature.discovery_level(1) == 0


def test_discover_features_hand_held_radar_bypasses_magically_hidden():
    # Phase 270: Hand-Held Radar (Discovery.txt) -- a kingdom that owns
    # it finds a feature regardless of Hide Feature.
    state, feature = _state_with_feature(magically_hidden=True)
    state.add_kingdom(KingdomState(1, "Radaria", Race.HUMAN, Alignment.NEUTRAL, LOCATION))
    state.kingdoms[1].discoveries.add(Discovery.HAND_HELD_RADAR)

    discovered = discover_features(state, LOCATION, kingdom_id=1, exploration_percent=100, rng=random.Random(0))

    assert discovered == [feature]
    assert feature.discovery_level(1) == 3


def test_discover_features_is_per_kingdom():
    state, feature = _state_with_feature()
    discover_features(state, LOCATION, kingdom_id=1, exploration_percent=100, rng=random.Random(0))
    assert feature.discovery_level(1) == 3
    assert feature.discovery_level(2) == 0  # a different kingdom hasn't discovered it yet


def test_discover_features_boundary_uses_strict_less_than():
    state, feature = _state_with_feature()
    # exploration_percent=50, roll exactly 0.5 -> 0.5*100=50, not < 50 -> fails.
    discovered = discover_features(state, LOCATION, kingdom_id=1, exploration_percent=50, rng=ScriptedRandom([0.5]))
    assert discovered == []
    state2, feature2 = _state_with_feature()
    discovered2 = discover_features(
        state2, LOCATION, kingdom_id=1, exploration_percent=50, rng=ScriptedRandom([0.49])
    )
    assert discovered2 == [feature2]
