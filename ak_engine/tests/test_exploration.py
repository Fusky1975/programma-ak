from __future__ import annotations

import random

import pytest

from ak_engine.models.alignment import Alignment
from ak_engine.models.discovery import Discovery
from ak_engine.models.feature import Feature, FeatureType
from ak_engine.models.game_state import GameState, KingdomState
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.monster import Monster
from ak_engine.models.race import Race
from ak_engine.turn.exploration import discover_features, resolve_explore

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
