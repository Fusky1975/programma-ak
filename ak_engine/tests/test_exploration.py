from __future__ import annotations

import pytest

from ak_engine.models.map import Terrain
from ak_engine.turn.exploration import resolve_explore


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
