from __future__ import annotations

import random

import pytest

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.map import Terrain
from ak_engine.models.race import Race
from ak_engine.turn.combat import Quality
from ak_engine.turn.strength import (
    DINOSAURS_STRENGTH_RANGE,
    DRUID_TABLE,
    ELEPHANTS_STRENGTH_RANGE,
    FANATICISM_CHANCE,
    combat_ability_multiplier,
    compute_druidic_shortfall,
    compute_effective_strength,
    exploration_advantage_multiplier,
    modified_quality,
    phantasmal_armies_multiplier,
    roll_dinosaurs_strength,
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


def test_adapt_tactics_to_terrain_reduces_the_adverse_terrain_penalty_to_75_percent():
    strength = compute_effective_strength(
        ArmyType.PHALANX, Race.HUMAN, Quality.GREEN, Terrain.SEA, adapt_tactics_to_terrain=True
    )
    assert strength == pytest.approx((3 * 0.75) * int(Quality.GREEN))


def test_adapt_tactics_to_terrain_has_no_effect_outside_adverse_terrain():
    normal = compute_effective_strength(ArmyType.PHALANX, Race.HUMAN, Quality.GREEN, Terrain.PLAINS)
    with_ability = compute_effective_strength(
        ArmyType.PHALANX, Race.HUMAN, Quality.GREEN, Terrain.PLAINS, adapt_tactics_to_terrain=True
    )
    assert with_ability == pytest.approx(normal)


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


def test_roll_dinosaurs_strength_within_range():
    rng = random.Random(0)
    for _ in range(200):
        value = roll_dinosaurs_strength(rng)
        assert DINOSAURS_STRENGTH_RANGE[0] <= value <= DINOSAURS_STRENGTH_RANGE[1]


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


def test_modified_quality_race_item_bonus_adds_a_level():
    assert modified_quality(Quality.AVERAGE, race_item_bonus=1) == Quality.VETERAN


def test_modified_quality_race_item_bonus_combines_in_one_clamp_pass_not_two():
    # Phase 279: a severe Druidic shortfall that would floor a unit at
    # Depleted on its own isn't rescued back up by a later +1 -- all
    # modifiers sum together before the single clamp, matching
    # modified_quality()'s own documented single-pass design.
    assert (
        modified_quality(Quality.GREEN, druidic_shortfall=5, race_item_bonus=1)
        == Quality.DEPLETED
    )


def test_compute_effective_strength_applies_druidic_shortfall_to_quality():
    penalized = compute_effective_strength(
        ArmyType.BOWMEN, Race.HUMAN, Quality.VETERAN, Terrain.PLAINS, druidic_shortfall=1
    )
    unpenalized = compute_effective_strength(ArmyType.BOWMEN, Race.HUMAN, Quality.VETERAN, Terrain.PLAINS)
    assert penalized == pytest.approx(unpenalized / int(Quality.VETERAN) * int(Quality.AVERAGE))


def test_compute_effective_strength_applies_race_item_bonus_to_quality():
    # Phase 285: race_item_bonus now passes through compute_effective_
    # strength() into modified_quality(), the same way druidic_shortfall
    # already does above.
    boosted = compute_effective_strength(
        ArmyType.BOWMEN, Race.HUMAN, Quality.AVERAGE, Terrain.PLAINS, race_item_bonus=1
    )
    unboosted = compute_effective_strength(ArmyType.BOWMEN, Race.HUMAN, Quality.AVERAGE, Terrain.PLAINS)
    assert boosted == pytest.approx(unboosted / int(Quality.AVERAGE) * int(Quality.VETERAN))


def test_desert_without_camels_reduces_quality_multiplier():
    strength = compute_effective_strength(
        ArmyType.CAMEL_CORPS, Race.HUMAN, Quality.AVERAGE, Terrain.DESERT, desert_without_camels=True
    )
    # base 2, home terrain Desert -> +1 = 3; quality AVERAGE(2) - 1 = GREEN(1); 3*1 = 3
    assert strength == pytest.approx(3)


def test_exploration_advantage_real_formula_per_own_side_only():
    # Phase 507: the real formula (1 + own_explored_percent * 0.0025)
    # reads only this side's own accumulated knowledge -- the enemy's
    # own exploration never enters it at all.
    assert exploration_advantage_multiplier(0) == 1.0
    assert exploration_advantage_multiplier(100) == pytest.approx(1.25)
    assert exploration_advantage_multiplier(50) == pytest.approx(1.125)
    # Military Maps raises the real cap to 200, reaching +50%.
    assert exploration_advantage_multiplier(200) == pytest.approx(1.50)


def test_combat_ability_multiplier_matches_20_percent_per_level():
    assert combat_ability_multiplier(0) == 1.0
    assert combat_ability_multiplier(3) == pytest.approx(1.6)


def test_combat_ability_multiplier_caps_the_automatic_scaling_at_level_4():
    # Phase 512: models/advanced_ability.py's own module docstring --
    # the automatic per-level bonus "discontinues" past level 4; a
    # level-5+ leader gets no further increase without a Mastery ability.
    assert combat_ability_multiplier(4) == pytest.approx(1.8)
    assert combat_ability_multiplier(5) == pytest.approx(1.8)
    assert combat_ability_multiplier(9) == pytest.approx(1.8)


def test_combat_ability_multiplier_adds_mastery_bonus_on_top_of_the_cap():
    assert combat_ability_multiplier(9, mastery_bonus=0.20) == pytest.approx(2.0)
    assert combat_ability_multiplier(0, mastery_bonus=0.10) == pytest.approx(1.10)


def test_compute_effective_strength_threads_combat_ability_mastery_bonus():
    boosted = compute_effective_strength(
        ArmyType.BOWMEN, Race.HUMAN, Quality.AVERAGE, Terrain.PLAINS,
        combat_ability_level=9, combat_ability_mastery_bonus=0.20,
    )
    capped_no_mastery = compute_effective_strength(
        ArmyType.BOWMEN, Race.HUMAN, Quality.AVERAGE, Terrain.PLAINS, combat_ability_level=9,
    )
    assert boosted == pytest.approx(capped_no_mastery / 1.8 * 2.0)


def test_phantasmal_armies_multiplier_matches_15_percent_per_level():
    # Phase 59, Regolamento AK.txt [4.23.2].
    assert phantasmal_armies_multiplier(0) == 1.0
    assert phantasmal_armies_multiplier(2) == pytest.approx(1.3)


def test_phantasmal_armies_level_stacks_into_compute_effective_strength():
    baseline = compute_effective_strength(ArmyType.LEGION, Race.HUMAN, Quality.AVERAGE, Terrain.PLAINS)
    boosted = compute_effective_strength(
        ArmyType.LEGION, Race.HUMAN, Quality.AVERAGE, Terrain.PLAINS, phantasmal_armies_level=2
    )
    assert boosted == pytest.approx(baseline * 1.3)


def test_illusory_fog_affected_halves_effective_strength():
    baseline = compute_effective_strength(ArmyType.DRAGON_WING, Race.HUMAN, Quality.AVERAGE, Terrain.PLAINS)
    fogged = compute_effective_strength(
        ArmyType.DRAGON_WING, Race.HUMAN, Quality.AVERAGE, Terrain.PLAINS, illusory_fog_affected=True
    )
    assert fogged == pytest.approx(baseline * 0.5)


def test_illusory_fog_unaffected_by_default():
    baseline = compute_effective_strength(ArmyType.DRAGON_WING, Race.HUMAN, Quality.AVERAGE, Terrain.PLAINS)
    unaffected = compute_effective_strength(
        ArmyType.DRAGON_WING, Race.HUMAN, Quality.AVERAGE, Terrain.PLAINS, illusory_fog_affected=False
    )
    assert unaffected == pytest.approx(baseline)


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


# -- Island provinces (Phase 282) -----------------------------------------


def test_is_island_averages_land_and_sea_terrain_component():
    # Phalanx: base 3, home Plains (+1) = 4 on land; adverse Sea (/2) =
    # 1.5 at sea. Island averages the two (2.75) before quality
    # multiplies -- see turn/strength.py's own Phase 282 docstring
    # section for the full derivation.
    island = compute_effective_strength(
        ArmyType.PHALANX, Race.HUMAN, Quality.AVERAGE, Terrain.PLAINS, is_island=True
    )
    assert island == pytest.approx(2.75 * int(Quality.AVERAGE))


def test_is_island_matches_plain_land_pass_when_land_and_sea_agree():
    # Bowmen have no home/adverse terrain entry for Plains or Sea, so the
    # land and sea passes are numerically identical (both just base
    # strength) -- the island average should equal the ordinary result.
    ordinary = compute_effective_strength(ArmyType.BOWMEN, Race.HUMAN, Quality.AVERAGE, Terrain.PLAINS)
    island = compute_effective_strength(
        ArmyType.BOWMEN, Race.HUMAN, Quality.AVERAGE, Terrain.PLAINS, is_island=True
    )
    assert island == pytest.approx(ordinary)


def test_is_island_whales_get_half_their_normal_sea_strength():
    # Emergent, not special-cased: averaging Whales' off-Sea zero with
    # their full Sea strength yields exactly half -- see the module
    # docstring's own Phase 282 note.
    normal_sea = compute_effective_strength(ArmyType.WHALES, Race.HUMAN, Quality.AVERAGE, Terrain.SEA)
    island = compute_effective_strength(
        ArmyType.WHALES, Race.HUMAN, Quality.AVERAGE, Terrain.PLAINS, is_island=True
    )
    assert island == pytest.approx(normal_sea / 2)


def test_is_island_overflight_air_units_are_unaffected():
    # The user's own words: "le province volanti... non hanno nessuna
    # variazione" -- Dragons/Eagles always take the single, ordinary
    # land-terrain pass, island or not.
    ordinary = compute_effective_strength(ArmyType.DRAGON_WING, Race.DRAGONS, Quality.AVERAGE, Terrain.PLAINS)
    island = compute_effective_strength(
        ArmyType.DRAGON_WING, Race.DRAGONS, Quality.AVERAGE, Terrain.PLAINS, is_island=True
    )
    assert island == ordinary


def test_is_island_false_by_default_matches_pre_phase_282_behavior():
    without_param = compute_effective_strength(ArmyType.PHALANX, Race.HUMAN, Quality.AVERAGE, Terrain.PLAINS)
    explicit_false = compute_effective_strength(
        ArmyType.PHALANX, Race.HUMAN, Quality.AVERAGE, Terrain.PLAINS, is_island=False
    )
    assert without_param == explicit_false


# -- Illusory Terrain (Phase 724) ------------------------------------------


def test_illusory_terrain_averages_real_and_illusory_terrain_component():
    # Phalanx: base 3, home Plains (+1) = 4 on the real terrain pass;
    # adverse Sea (/2) = 1.5 on the illusory pass. Averages to 2.75
    # before quality multiplies -- rulebook [4.23.1]'s own worked example
    # shape (plains illusorily made to look like sea).
    blended = compute_effective_strength(
        ArmyType.PHALANX, Race.HUMAN, Quality.AVERAGE, Terrain.PLAINS, illusory_terrain=Terrain.SEA
    )
    assert blended == pytest.approx(2.75 * int(Quality.AVERAGE))


def test_illusory_terrain_none_by_default_matches_pre_phase_724_behavior():
    without_param = compute_effective_strength(ArmyType.PHALANX, Race.HUMAN, Quality.AVERAGE, Terrain.PLAINS)
    explicit_none = compute_effective_strength(
        ArmyType.PHALANX, Race.HUMAN, Quality.AVERAGE, Terrain.PLAINS, illusory_terrain=None
    )
    assert without_param == explicit_none


def test_illusory_terrain_whales_get_half_their_normal_sea_strength_when_illusion_is_sea():
    # Same emergent mechanism as the Island blend: Whales' real-terrain
    # pass on Plains is 0.0 (off-Sea override), averaged with their full
    # Sea strength on the illusory pass yields exactly half.
    normal_sea = compute_effective_strength(ArmyType.WHALES, Race.HUMAN, Quality.AVERAGE, Terrain.SEA)
    illusory = compute_effective_strength(
        ArmyType.WHALES, Race.HUMAN, Quality.AVERAGE, Terrain.PLAINS, illusory_terrain=Terrain.SEA
    )
    assert illusory == pytest.approx(normal_sea / 2)


def test_illusory_terrain_affects_overflight_air_units_unlike_is_island():
    # Deliberate difference from is_island's own air-unit exemption --
    # the rulebook names no such carve-out for Illusory Terrain. Eagle
    # Wing: home Mountains (+1) = 5 real, adverse Forest (/2) = 2.0
    # illusory -- averages to 3.5, clearly below the unaffected 5.0.
    ordinary = compute_effective_strength(ArmyType.EAGLE_WING, Race.HUMAN, Quality.AVERAGE, Terrain.MTNS)
    illusory = compute_effective_strength(
        ArmyType.EAGLE_WING, Race.HUMAN, Quality.AVERAGE, Terrain.MTNS, illusory_terrain=Terrain.FOREST
    )
    assert illusory == pytest.approx(3.5 * int(Quality.AVERAGE))
    assert illusory != ordinary
    # is_island alone still exempts the same army type (unchanged Phase 282 behavior).
    island_only = compute_effective_strength(
        ArmyType.EAGLE_WING, Race.HUMAN, Quality.AVERAGE, Terrain.MTNS, is_island=True
    )
    assert island_only == ordinary


def test_illusory_terrain_nests_around_is_island_rather_than_flattening_a_three_way_average():
    # User-confirmed design: the real side of the illusory blend reuses
    # the full is_island land/Sea average; the illusory side stays a
    # single ordinary pass. Nested result: ((land+sea)/2 + illusory) / 2,
    # not (land+sea+illusory) / 3.
    nested = compute_effective_strength(
        ArmyType.PHALANX, Race.HUMAN, Quality.AVERAGE, Terrain.PLAINS, is_island=True, illusory_terrain=Terrain.SEA
    )
    # land=4, sea=1.5 (both the is_island land/sea pair and the illusory
    # terrain here happen to be the same Sea value) -> ((4+1.5)/2 + 1.5) / 2 = 2.125
    assert nested == pytest.approx(2.125 * int(Quality.AVERAGE))
    flattened_average = pytest.approx((4 + 1.5 + 1.5) / 3 * int(Quality.AVERAGE))
    assert nested != flattened_average


# -- Phase 351: cross-validation against the confirmed AK.EXE/AK.OVR ------
# battle_engine.column_resolution.confirmed_multipliers and
# battle_engine.special_events tables -- the exploration_max: 1.25 data
# point here is the *ordinary* 100%-cap case of the real Phase 507
# formula (own_explored_percent * 0.0025), not a separate confirmation
# in tension with it -- see that function's own Phase 507 addendum.


def test_exploration_advantage_maxes_out_at_the_confirmed_1_25():
    assert exploration_advantage_multiplier(100) == pytest.approx(1.25)


def test_tactical_or_naval_bonus_matches_the_confirmed_1_2_per_level():
    assert combat_ability_multiplier(1) == pytest.approx(1.2)


def test_phantasmal_armies_bonus_matches_the_confirmed_1_15_per_level():
    assert phantasmal_armies_multiplier(1) == pytest.approx(1.15)


def test_fanaticism_chance_matches_the_confirmed_special_events_table():
    assert FANATICISM_CHANCE[Alignment.DIVINE] == 0.50
    assert FANATICISM_CHANCE[Alignment.GOOD] == 0.40
    assert FANATICISM_CHANCE[Alignment.EVIL] == 0.25
