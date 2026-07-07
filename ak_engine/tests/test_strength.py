from __future__ import annotations

import random

import pytest

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.map import Terrain
from ak_engine.models.race import Race
from ak_engine.turn.combat import Quality
from ak_engine.turn.strength import (
    ELEPHANTS_STRENGTH_RANGE,
    combat_ability_multiplier,
    compute_effective_strength,
    exploration_advantage_multiplier,
    modified_quality,
    roll_elephants_strength,
    roll_fanaticism,
)


def test_race_type_and_terrain_bonuses_stack_additively():
    # Elf Bowmen in Forest: base 2, +1 race-type (Elf/Bowmen), +1
    # race-terrain (Elf/Forest), +1 army home terrain (Bowmen/Forest) = 5.
    plain_dwarf_bowmen = compute_effective_strength(
        ArmyType.BOWMEN, Race.DWARVEN, Quality.GREEN, Terrain.PLAINS
    )
    elf_bowmen_forest = compute_effective_strength(
        ArmyType.BOWMEN, Race.ELVEN, Quality.GREEN, Terrain.FOREST
    )
    assert plain_dwarf_bowmen == pytest.approx(2 * int(Quality.GREEN))
    assert elf_bowmen_forest == pytest.approx(5 * int(Quality.GREEN))


def test_adverse_terrain_halves_the_terrain_modified_strength():
    # Phalanx (base 3, home Plains, adverse Forest/Jungle/Sea).
    strength = compute_effective_strength(ArmyType.PHALANX, Race.HUMAN, Quality.GREEN, Terrain.SEA)
    assert strength == pytest.approx((3 / 2) * int(Quality.GREEN))


def test_garrison_uses_asymmetric_attack_and_defense_strength():
    attack = compute_effective_strength(ArmyType.GARRISON, Race.HUMAN, Quality.GREEN, Terrain.PLAINS, is_defender=False)
    defense = compute_effective_strength(ArmyType.GARRISON, Race.HUMAN, Quality.GREEN, Terrain.PLAINS, is_defender=True)
    # Defense also gets the +25% Defense special factor on top of the higher base.
    assert attack == pytest.approx(1 * int(Quality.GREEN))
    assert defense == pytest.approx(3 * int(Quality.GREEN) * 1.25)


def test_elephants_require_base_strength_override():
    with pytest.raises(ValueError):
        compute_effective_strength(ArmyType.ELEPHANTS, Race.HUMAN, Quality.GREEN, Terrain.PLAINS)

    strength = compute_effective_strength(
        ArmyType.ELEPHANTS, Race.HUMAN, Quality.GREEN, Terrain.PLAINS, base_strength_override=4
    )
    assert strength == pytest.approx(4 * int(Quality.GREEN))


def test_roll_elephants_strength_within_range():
    rng = random.Random(0)
    for _ in range(200):
        value = roll_elephants_strength(rng)
        assert ELEPHANTS_STRENGTH_RANGE[0] <= value <= ELEPHANTS_STRENGTH_RANGE[1]


def test_modified_quality_stacks_and_clamps():
    assert modified_quality(Quality.AVERAGE, is_home_province=True) == Quality.VETERAN
    assert modified_quality(Quality.DEPLETED, desert_without_camels=True) == Quality.DEPLETED  # clamped at floor
    assert modified_quality(Quality.ELITE, is_home_province=True, is_fanatical=True) == Quality.ELITE  # clamped at ceiling
    assert modified_quality(Quality.AVERAGE, desert_without_camels=True, is_home_province=True, is_fanatical=True) == Quality.VETERAN


def test_desert_without_camels_reduces_quality_multiplier():
    strength = compute_effective_strength(
        ArmyType.CAMEL_CORPS, Race.HUMAN, Quality.AVERAGE, Terrain.DESERT, desert_without_camels=True
    )
    # base 2, home terrain Desert -> +1 = 3; quality AVERAGE(2) - 1 = GREEN(1); 3*1 = 3
    assert strength == pytest.approx(3)


def test_exploration_advantage_scales_linearly_up_to_max():
    assert exploration_advantage_multiplier(0, 0) == 1.0
    assert exploration_advantage_multiplier(100, 0) == pytest.approx(1.25)
    assert exploration_advantage_multiplier(50, 0) == pytest.approx(1.125)
    assert exploration_advantage_multiplier(0, 100) == 1.0  # never a penalty for being behind


def test_combat_ability_multiplier_matches_20_percent_per_level():
    assert combat_ability_multiplier(0) == 1.0
    assert combat_ability_multiplier(3) == pytest.approx(1.6)


def test_nemesis_penalty_applied_when_opponent_given():
    with_nemesis = compute_effective_strength(
        ArmyType.PHALANX, Race.HUMAN, Quality.AVERAGE, Terrain.PLAINS, opponent_army_type=ArmyType.LEGION
    )
    without_nemesis = compute_effective_strength(
        ArmyType.PHALANX, Race.HUMAN, Quality.AVERAGE, Terrain.PLAINS, opponent_army_type=ArmyType.BOWMEN
    )
    assert with_nemesis == pytest.approx(without_nemesis * (2 / 3))


def test_roll_fanaticism_matches_documented_chances():
    rng = random.Random(123)
    trials = 4000
    divine = sum(roll_fanaticism(Alignment.DIVINE, rng) for _ in range(trials)) / trials
    good = sum(roll_fanaticism(Alignment.GOOD, rng) for _ in range(trials)) / trials
    evil = sum(roll_fanaticism(Alignment.EVIL, rng) for _ in range(trials)) / trials
    neutral = sum(roll_fanaticism(Alignment.NEUTRAL, rng) for _ in range(trials)) / trials
    assert abs(divine - 0.50) < 0.03
    assert abs(good - 0.40) < 0.03
    assert abs(evil - 0.25) < 0.03
    assert neutral == 0.0


def test_roll_fanaticism_always_fanatical_override():
    rng = random.Random(0)
    assert roll_fanaticism(Alignment.NEUTRAL, rng, always_fanatical=True) is True
