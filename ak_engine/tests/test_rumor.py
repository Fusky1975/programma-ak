from __future__ import annotations

import random

from ak_engine.models.enums import ActionCode
from ak_engine.models.feature import Feature, FeatureType
from ak_engine.models.game_state import GameState, ProvinceState
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.monster import Monster
from ak_engine.models.race import Race
from ak_engine.models.rumor import RumorContent
from ak_engine.models.treasure import TREASURE_NAME, Treasure
from ak_engine.turn.rumor import (
    RUMOR_CHANCE_BY_ACTION,
    RUMOR_MAX_DISTANCE,
    find_rumor_candidates,
    resolve_rumor_generation,
)

from _helpers import ScriptedRandom

ORIGIN = HexCoord(5, 5)
KINGDOM = 1
LEADER = 1


def _state_with_provinces(*coords: HexCoord) -> GameState:
    state = GameState()
    state.provinces[ORIGIN] = ProvinceState(ORIGIN, Terrain.PLAINS, Race.HUMAN)
    for coord in coords:
        state.provinces[coord] = ProvinceState(coord, Terrain.PLAINS, Race.HUMAN)
    return state


def _add_feature(state: GameState, feature_id: int, coord: HexCoord, **kwargs) -> Feature:
    feature = Feature(feature_id=feature_id, coord=coord, kind=FeatureType.DUNGEON, **kwargs)
    state.add_feature(feature)
    return feature


def test_rumor_chance_by_action_matches_confirmed_mapping():
    assert RUMOR_CHANCE_BY_ACTION == {
        ActionCode.LMOVE: 0.20,
        ActionCode.PURSUE: 0.20,
        ActionCode.TRAIL: 0.20,
        ActionCode.EXPLORE: 0.30,
        ActionCode.ASPY: 0.30,
        ActionCode.CAST: 0.05,
        ActionCode.PRACTICE: 0.05,
    }


# -- find_rumor_candidates --


def test_find_rumor_candidates_excludes_the_origin_province():
    state = _state_with_provinces()
    _add_feature(state, 1, ORIGIN, guardian_monster=Monster.ARCHER)
    assert find_rumor_candidates(state, ORIGIN, KINGDOM) == []


def test_find_rumor_candidates_includes_within_range():
    nearby = HexCoord(ORIGIN.x + RUMOR_MAX_DISTANCE, ORIGIN.y)
    state = _state_with_provinces(nearby)
    feature = _add_feature(state, 1, nearby, guardian_monster=Monster.ARCHER)
    assert find_rumor_candidates(state, ORIGIN, KINGDOM) == [feature]


def test_find_rumor_candidates_excludes_beyond_range():
    far = HexCoord(ORIGIN.x + RUMOR_MAX_DISTANCE + 5, ORIGIN.y)
    state = _state_with_provinces(far)
    _add_feature(state, 1, far, guardian_monster=Monster.ARCHER)
    assert find_rumor_candidates(state, ORIGIN, KINGDOM) == []


def test_find_rumor_candidates_excludes_already_discovered_by_this_kingdom():
    nearby = HexCoord(ORIGIN.x + 1, ORIGIN.y)
    state = _state_with_provinces(nearby)
    feature = _add_feature(state, 1, nearby, guardian_monster=Monster.ARCHER)
    feature.discovered_by_kingdom[KINGDOM] = 3
    assert find_rumor_candidates(state, ORIGIN, KINGDOM) == []
    # A different kingdom hasn't discovered it -- still a candidate for them.
    assert find_rumor_candidates(state, ORIGIN, 2) == [feature]


def test_find_rumor_candidates_excludes_magically_hidden():
    nearby = HexCoord(ORIGIN.x + 1, ORIGIN.y)
    state = _state_with_provinces(nearby)
    _add_feature(state, 1, nearby, guardian_monster=Monster.ARCHER, magically_hidden=True)
    assert find_rumor_candidates(state, ORIGIN, KINGDOM) == []


def test_find_rumor_candidates_excludes_features_with_neither_monster_nor_treasure():
    nearby = HexCoord(ORIGIN.x + 1, ORIGIN.y)
    state = _state_with_provinces(nearby)
    _add_feature(state, 1, nearby)
    assert find_rumor_candidates(state, ORIGIN, KINGDOM) == []


# -- resolve_rumor_generation --


def test_resolve_rumor_generation_no_candidates_consumes_no_randomness():
    state = _state_with_provinces()
    rng = ScriptedRandom([])  # would raise IndexError if anything were consumed
    result = resolve_rumor_generation(state, KINGDOM, LEADER, ORIGIN, ActionCode.EXPLORE, rng)
    assert result is None


def test_resolve_rumor_generation_unsupported_action_consumes_no_randomness():
    nearby = HexCoord(ORIGIN.x + 1, ORIGIN.y)
    state = _state_with_provinces(nearby)
    _add_feature(state, 1, nearby, guardian_monster=Monster.ARCHER)
    rng = ScriptedRandom([])
    result = resolve_rumor_generation(state, KINGDOM, LEADER, ORIGIN, ActionCode.RECRUIT, rng)
    assert result is None


def test_resolve_rumor_generation_trigger_boundary():
    nearby = HexCoord(ORIGIN.x + 1, ORIGIN.y)
    state = _state_with_provinces(nearby)
    _add_feature(state, 1, nearby, guardian_monster=Monster.ARCHER, treasure=Treasure.ABILITY_TACTICAL)
    # EXPLORE chance is 0.30 -- a roll exactly at the boundary fails (strict <).
    rng_fail = ScriptedRandom([0.30])
    assert resolve_rumor_generation(state, KINGDOM, LEADER, ORIGIN, ActionCode.EXPLORE, rng_fail) is None

    state2 = _state_with_provinces(nearby)
    _add_feature(state2, 1, nearby, guardian_monster=Monster.ARCHER, treasure=Treasure.ABILITY_TACTICAL)
    rng_succeed = ScriptedRandom([0.29] + [0.5] * 10, choice_indices=[0] * 5)
    assert resolve_rumor_generation(state2, KINGDOM, LEADER, ORIGIN, ActionCode.EXPLORE, rng_succeed) is not None


def test_resolve_rumor_generation_true_rumor_describes_the_real_feature():
    nearby = HexCoord(ORIGIN.x + 1, ORIGIN.y)
    state = _state_with_provinces(nearby)
    feature = _add_feature(state, 1, nearby, guardian_monster=Monster.ARCHER, treasure=Treasure.ABILITY_TACTICAL)
    # trigger succeeds (0.0 < 0.30), candidate chosen (index 0), content=FEATURE_AND_MONSTER
    # (0.0 < 0.70), is_true=True (0.0 < 0.50).
    rng = ScriptedRandom([0.0, 0.0, 0.0], choice_indices=[0])
    rumor = resolve_rumor_generation(state, KINGDOM, LEADER, ORIGIN, ActionCode.EXPLORE, rng)
    assert rumor is not None
    assert rumor.leader_id == LEADER
    assert rumor.feature_id == feature.feature_id
    assert rumor.is_true is True
    assert rumor.content is RumorContent.FEATURE_AND_MONSTER
    assert rumor.described_coord == nearby
    assert rumor.described_monster is Monster.ARCHER


def test_resolve_rumor_generation_item_content():
    nearby = HexCoord(ORIGIN.x + 1, ORIGIN.y)
    state = _state_with_provinces(nearby)
    feature = _add_feature(state, 1, nearby, guardian_monster=Monster.ARCHER, treasure=Treasure.ABILITY_TACTICAL)
    # trigger succeeds, candidate chosen, content roll 0.9 >= 0.70 -> ITEM, is_true roll 0.0 -> True.
    rng = ScriptedRandom([0.0, 0.9, 0.0], choice_indices=[0])
    rumor = resolve_rumor_generation(state, KINGDOM, LEADER, ORIGIN, ActionCode.EXPLORE, rng)
    assert rumor.content is RumorContent.ITEM
    assert rumor.described_treasure is Treasure.ABILITY_TACTICAL
    assert rumor.described_monster is None


def test_resolve_rumor_generation_false_rumor_corrupts_the_subject():
    nearby = HexCoord(ORIGIN.x + 1, ORIGIN.y)
    state = _state_with_provinces(nearby)
    feature = _add_feature(state, 1, nearby, guardian_monster=Monster.ARCHER, treasure=Treasure.ABILITY_TACTICAL)
    # trigger succeeds, content=FEATURE_AND_MONSTER, is_true=False (0.9 >= 0.50),
    # corrupt-subject roll 0.0 < 0.50 -> corrupt the monster, not the province.
    rng = ScriptedRandom([0.0, 0.0, 0.9, 0.0], choice_indices=[0, 0])
    rumor = resolve_rumor_generation(state, KINGDOM, LEADER, ORIGIN, ActionCode.EXPLORE, rng)
    assert rumor.is_true is False
    assert rumor.described_coord == nearby  # province stays correct
    assert rumor.described_monster is not None
    assert rumor.described_monster is not Monster.ARCHER


def test_resolve_rumor_generation_false_rumor_corrupts_the_province():
    other = HexCoord(ORIGIN.x + 1, ORIGIN.y)
    state = _state_with_provinces(other)
    feature = _add_feature(state, 1, other, guardian_monster=Monster.ARCHER, treasure=Treasure.ABILITY_TACTICAL)
    # trigger succeeds, content=FEATURE_AND_MONSTER, is_true=False, corrupt-subject
    # roll 0.9 >= 0.50 -> corrupt the province instead.
    rng = ScriptedRandom([0.0, 0.0, 0.9, 0.9], choice_indices=[0, 0])
    rumor = resolve_rumor_generation(state, KINGDOM, LEADER, ORIGIN, ActionCode.EXPLORE, rng)
    assert rumor.is_true is False
    assert rumor.described_monster is Monster.ARCHER  # monster stays correct
    assert rumor.described_coord != feature.coord


def test_resolve_rumor_generation_guardian_only_feature_always_uses_feature_content():
    nearby = HexCoord(ORIGIN.x + 1, ORIGIN.y)
    state = _state_with_provinces(nearby)
    _add_feature(state, 1, nearby, guardian_monster=Monster.ARCHER)  # no treasure
    rng = ScriptedRandom([0.0, 0.0], choice_indices=[0])
    rumor = resolve_rumor_generation(state, KINGDOM, LEADER, ORIGIN, ActionCode.EXPLORE, rng)
    assert rumor.content is RumorContent.FEATURE_AND_MONSTER


def test_resolve_rumor_generation_treasure_only_feature_always_uses_item_content():
    nearby = HexCoord(ORIGIN.x + 1, ORIGIN.y)
    state = _state_with_provinces(nearby)
    _add_feature(state, 1, nearby, treasure=Treasure.ABILITY_TACTICAL)  # no guardian
    rng = ScriptedRandom([0.0, 0.0], choice_indices=[0])
    rumor = resolve_rumor_generation(state, KINGDOM, LEADER, ORIGIN, ActionCode.EXPLORE, rng)
    assert rumor.content is RumorContent.ITEM


def test_resolve_rumor_generation_corrupted_treasure_never_an_unused_ordinal():
    # Regression: a false rumor's own "corrupt the treasure" branch used
    # to draw from every real Treasure member, including the 14
    # UNUSED_EXTENSION placeholder ordinals (99-112) that have no
    # TREASURE_NAME entry -- describe_rumor() crashes with a KeyError if
    # one is ever picked. Treasure.UNUSED_20 is literally the last real
    # Treasure member, so choice_indices=[-1] (negative indexing always
    # selects the list's own last element, whatever its length) forces
    # exactly that draw under the old, unfiltered list; the fix must
    # exclude it instead.
    nearby = HexCoord(ORIGIN.x + 1, ORIGIN.y)
    state = _state_with_provinces(nearby)
    _add_feature(state, 1, nearby, treasure=Treasure.ABILITY_TACTICAL)  # no guardian -> always ITEM content
    # trigger succeeds, candidate chosen, is_true=False (0.9 >= 0.50),
    # corrupt-subject roll 0.0 < 0.50 -> corrupt the treasure.
    rng = ScriptedRandom([0.0, 0.9, 0.0], choice_indices=[0, -1])
    rumor = resolve_rumor_generation(state, KINGDOM, LEADER, ORIGIN, ActionCode.EXPLORE, rng)
    assert rumor.is_true is False
    assert rumor.described_treasure in TREASURE_NAME
    assert rumor.described_treasure is not Treasure.ABILITY_TACTICAL
