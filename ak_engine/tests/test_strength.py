from __future__ import annotations

import random

import pytest

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.map import Terrain
from ak_engine.models.race import Race
from ak_engine.turn.combat import Quality
from ak_engine.turn.strength import (
    DRUID_TABLE,
    ELEPHANTS_STRENGTH_RANGE,
    combat_ability_multiplier,
    compute_druidic_shortfall,
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


def test_compute_druidic_shortfall_same_race_never_penalized_even_with_zero_skill():
    # Rulebook [4.32] is framed as "races OTHER than their own" -- a Whale
    # leader commanding Whales needs no Druidic skill at all, even though
    # DRUID_TABLE[Race.WHALES] == 2 (that entry is for a *non*-Whale leader).
    assert DRUID_TABLE[Race.WHALES] == 2
    assert compute_druidic_shortfall(Race.WHALES, Race.WHALES, 0) == 0
    assert compute_druidic_shortfall(Race.HUMAN, Race.HUMAN, 0) == 0


def test_compute_druidic_shortfall_none_leader_race_returns_zero():
    # No race data for the leader (e.g. an independent Hero with no
    # kingdom) -- insufficient data to judge a shortfall, not a guess.
    assert compute_druidic_shortfall(None, Race.DRAGONS, 0) == 0


def test_compute_druidic_shortfall_returns_exact_gap_when_insufficient():
    # DRUID_TABLE[Race.DRAGONS] == 4; a Human leader (skill 1) leading
    # Dragons is short by 3.
    assert compute_druidic_shortfall(Race.HUMAN, Race.DRAGONS, 1) == 3


def test_compute_druidic_shortfall_zero_when_skill_meets_or_exceeds_requirement():
    # DRUID_TABLE[Race.TROLLISH] == 2.
    assert compute_druidic_shortfall(Race.HUMAN, Race.TROLLISH, 2) == 0
    assert compute_druidic_shortfall(Race.HUMAN, Race.TROLLISH, 5) == 0  # never negative


def test_compute_druidic_shortfall_race_absent_from_table_requires_nothing():
    # NO_RACE/SAURIAN/VAMPISH/ROHAN aren't in the rulebook's Druid Table
    # text available to this project -- treated as requiring 0, not guessed.
    assert Race.SAURIAN not in DRUID_TABLE
    assert compute_druidic_shortfall(Race.HUMAN, Race.SAURIAN, 0) == 0


def test_modified_quality_druidic_shortfall_reduces_and_clamps_at_floor():
    assert modified_quality(Quality.VETERAN, druidic_shortfall=1) == Quality.AVERAGE
    assert modified_quality(Quality.GREEN, druidic_shortfall=4) == Quality.DEPLETED  # clamped, can't go negative
    # Stacks with the other modifiers, applied in the documented order:
    # AVERAGE(2) - 1 (shortfall) + 1 (home) + 1 (fanatical) = VETERAN(3).
    assert (
        modified_quality(Quality.AVERAGE, druidic_shortfall=1, is_home_province=True, is_fanatical=True)
        == Quality.VETERAN
    )


def test_compute_effective_strength_applies_druidic_shortfall_to_quality():
    penalized = compute_effective_strength(
        ArmyType.BOWMEN, Race.HUMAN, Quality.VETERAN, Terrain.PLAINS, druidic_shortfall=1
    )
    unpenalized = compute_effective_strength(ArmyType.BOWMEN, Race.HUMAN, Quality.VETERAN, Terrain.PLAINS)
    assert penalized == pytest.approx(unpenalized / int(Quality.VETERAN) * int(Quality.AVERAGE))


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


def test_whales_have_zero_strength_off_sea_regardless_of_bonuses():
    # Elven home terrain/race bonuses, ELITE quality, home province, a
    # Tactical bonus, fanaticism -- none of it should matter off-sea.
    for terrain in (Terrain.PLAINS, Terrain.FOREST, Terrain.MTNS, Terrain.DESERT, Terrain.JUNGLE):
        strength = compute_effective_strength(
            ArmyType.WHALES,
            Race.ELVEN,
            Quality.ELITE,
            terrain,
            is_defender=True,
            is_home_province=True,
            is_fanatical=True,
            combat_ability_level=5,
        )
        assert strength == 0.0


def test_whales_compute_normally_at_sea():
    strength = compute_effective_strength(ArmyType.WHALES, Race.HUMAN, Quality.AVERAGE, Terrain.SEA)
    assert strength > 0
