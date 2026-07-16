from __future__ import annotations

from ak_engine.models.alignment import Alignment
from ak_engine.models.enums import Ability
from ak_engine.models.monster import (
    MONSTER_ALIGNMENT_DISTRIBUTION,
    MONSTER_COMBAT_STATS,
    MONSTER_ENGAGEMENT_STATE_NAME,
    MONSTER_HP_BANDS,
    MONSTER_MAGIC_ABILITIES,
    MONSTER_NAMES,
    MONSTER_STATS,
    SPIRITWRACK_ANIMAL_INTELLIGENCE_MONSTERS,
    SPIRITWRACK_MECHANICAL_MONSTERS,
    SPIRITWRACK_UNDEAD_MONSTERS,
    TELEKINETIC_STORM_SUBMARINE_MONSTERS,
    AlignmentOption,
    Monster,
    MonsterCombatStats,
    MonsterEngagementState,
    MonsterSpeed,
    MonsterStats,
    roll_monster_alignment,
)

from _helpers import ScriptedRandom


def test_monster_enum_has_61_declared_values():
    assert len(Monster) == 61
    assert Monster.ROC.value == 0
    assert Monster.NOMONSTER.value == 60


def test_monster_names_cover_every_enum_value():
    assert set(MONSTER_NAMES.keys()) == set(Monster)
    assert MONSTER_NAMES[Monster.GRYPHON] == "Gryphon"
    assert MONSTER_NAMES[Monster.NOMONSTER] == "no monster"
    assert MONSTER_NAMES[Monster.BAL_DEMON] == "Balrog Demon"
    assert MONSTER_NAMES[Monster.MAR_DEMON] == "Marilith Demon"


def test_monster_stats_covers_only_the_six_unambiguous_table_rows():
    assert set(MONSTER_STATS.keys()) == {
        Monster.GRYPHON,
        Monster.GIANT,
        Monster.GARGOYLE,
        Monster.TROLL,
        Monster.SPECTRE,
        Monster.ELASMOSAURUS,
    }


def test_demon_row_is_deliberately_excluded_from_monster_stats():
    assert Monster.BAL_DEMON not in MONSTER_STATS
    assert Monster.MAR_DEMON not in MONSTER_STATS


def test_monster_stats_giant_has_missile_attack():
    giant = MONSTER_STATS[Monster.GIANT]
    assert giant == MonsterStats(25, 1, (1, 7), 1, (1, 7), MonsterSpeed.MEDIUM)


def test_monster_stats_gryphon_has_no_missile_attack():
    gryphon = MONSTER_STATS[Monster.GRYPHON]
    assert gryphon.missile_skill == 0
    assert gryphon.missile_damage is None
    assert gryphon.speed is MonsterSpeed.FAST


# -- MonsterCombatStats / MONSTER_COMBAT_STATS (Phase 154, project-original) --


def test_monster_combat_stats_covers_every_real_species():
    all_real = {m for m in Monster if m is not Monster.NOMONSTER}
    assert set(MONSTER_COMBAT_STATS.keys()) == all_real


def test_monster_combat_stats_nomonster_sentinel_has_no_entry():
    assert Monster.NOMONSTER not in MONSTER_COMBAT_STATS


def test_monster_combat_stats_hp_ranges_are_all_valid():
    for stats in MONSTER_COMBAT_STATS.values():
        low, high = stats.hit_points_range
        assert 0 < low <= high


def test_monster_combat_stats_gryphon_matches_supplied_table():
    gryphon = MONSTER_COMBAT_STATS[Monster.GRYPHON]
    assert gryphon == MonsterCombatStats((20, 30), 2, (1, 6), 0, None, MonsterSpeed.FAST)


def test_monster_combat_stats_giant_has_missile_attack():
    giant = MONSTER_COMBAT_STATS[Monster.GIANT]
    assert giant == MonsterCombatStats((20, 30), 1, (1, 7), 1, (1, 7), MonsterSpeed.MEDIUM)


def test_monster_combat_stats_red_dragon_is_slow_and_powerful():
    red_dragon = MONSTER_COMBAT_STATS[Monster.R_DRAGON]
    assert red_dragon == MonsterCombatStats((30, 50), 3, (1, 7), 2, (3, 10), MonsterSpeed.SLOW)


def test_monster_combat_stats_corroborates_five_of_six_sourced_averages():
    # Gryphon/Giant/Gargoyle/Troll/Elasmosaurus: this table's own HP range
    # midpoint matches MONSTER_STATS's RULES.AK-sourced average exactly.
    for monster in (Monster.GRYPHON, Monster.GIANT, Monster.GARGOYLE, Monster.TROLL, Monster.ELASMOSAURUS):
        low, high = MONSTER_COMBAT_STATS[monster].hit_points_range
        assert (low + high) / 2 == MONSTER_STATS[monster].hit_points


def test_monster_combat_stats_spectre_disagrees_with_sourced_average():
    # Genuine cross-source discrepancy, transcribed as supplied rather
    # than silently reconciled -- see module docstring's Phase 154 note.
    low, high = MONSTER_COMBAT_STATS[Monster.SPECTRE].hit_points_range
    assert (low, high) == (12, 22)
    assert (low + high) / 2 != MONSTER_STATS[Monster.SPECTRE].hit_points


def test_monster_hp_bands_cover_the_full_range_including_unlabeled_row():
    labels = [band.label for band in MONSTER_HP_BANDS]
    assert labels == ["Weak", "-", "Large/Strong", "Powerful", "Very Powerful"]
    assert (MONSTER_HP_BANDS[0].low, MONSTER_HP_BANDS[0].high) == (7, 12)
    assert MONSTER_HP_BANDS[-1].high is None


# -- MonsterEngagementState (Phase 130) --


def test_monster_engagement_state_has_8_members():
    assert len(list(MonsterEngagementState)) == 8


def test_monster_engagement_state_name_covers_all_members():
    assert set(MONSTER_ENGAGEMENT_STATE_NAME.keys()) == set(MonsterEngagementState)


def test_monster_engagement_state_name_verbatim_samples():
    assert MONSTER_ENGAGEMENT_STATE_NAME[MonsterEngagementState.DEAD] == "Dead"
    assert MONSTER_ENGAGEMENT_STATE_NAME[MonsterEngagementState.ZOMBOID] == "Skeletal"
    assert MONSTER_ENGAGEMENT_STATE_NAME[MonsterEngagementState.BOLD] == "Emboldened"
    assert MONSTER_ENGAGEMENT_STATE_NAME[MonsterEngagementState.SOLD] == "Sold Soul"
    assert MONSTER_ENGAGEMENT_STATE_NAME[MonsterEngagementState.CALM] == "Calmed"


# -- MONSTER_ALIGNMENT_DISTRIBUTION / roll_monster_alignment (Phase 176,
# project-original, same Desktop/MOSTRI con statistiche.txt source as
# MONSTER_COMBAT_STATS) --


def test_monster_alignment_distribution_covers_every_real_species():
    all_real = {m for m in Monster if m is not Monster.NOMONSTER}
    assert set(MONSTER_ALIGNMENT_DISTRIBUTION.keys()) == all_real


def test_monster_alignment_distribution_nomonster_sentinel_has_no_entry():
    assert Monster.NOMONSTER not in MONSTER_ALIGNMENT_DISTRIBUTION


def test_monster_alignment_distribution_every_species_sums_to_100_percent():
    for monster, options in MONSTER_ALIGNMENT_DISTRIBUTION.items():
        assert sum(option.percent for option in options) == 100, monster


def test_monster_alignment_distribution_single_option_sample():
    assert MONSTER_ALIGNMENT_DISTRIBUTION[Monster.GRYPHON] == (AlignmentOption(Alignment.NEUTRAL, 100),)


def test_monster_alignment_distribution_two_option_sample():
    assert MONSTER_ALIGNMENT_DISTRIBUTION[Monster.GIANT] == (
        AlignmentOption(Alignment.NEUTRAL, 50),
        AlignmentOption(Alignment.PAGAN, 50),
    )


def test_monster_alignment_distribution_three_option_sample():
    # Renegade Priest -- Good (40%) / Druidic (30%) / Neutral (30%).
    assert MONSTER_ALIGNMENT_DISTRIBUTION[Monster.WHITE_MAGE] == (
        AlignmentOption(Alignment.GOOD, 40),
        AlignmentOption(Alignment.DRUID, 30),
        AlignmentOption(Alignment.NEUTRAL, 30),
    )


def test_roll_monster_alignment_returns_none_for_the_nomonster_sentinel():
    assert roll_monster_alignment(Monster.NOMONSTER, ScriptedRandom([])) is None


def test_roll_monster_alignment_single_option_species_never_consumes_a_roll():
    # The user's own confirmation scopes the roll to species with "due o
    # tre allineamenti" -- a single-option species must not call
    # rng.random() at all (ScriptedRandom([]) raises IndexError if it does).
    rng = ScriptedRandom([])
    assert roll_monster_alignment(Monster.GRYPHON, rng) is Alignment.NEUTRAL


def test_roll_monster_alignment_two_option_species_below_threshold():
    # Giant: Neutral (50%) / Pagan (50%) -- 0.49*100 = 49 < 50 -> Neutral.
    rng = ScriptedRandom([0.49])
    assert roll_monster_alignment(Monster.GIANT, rng) is Alignment.NEUTRAL


def test_roll_monster_alignment_two_option_species_at_and_above_threshold():
    # 0.5*100 = 50, not < 50 -> falls through to the second option.
    rng = ScriptedRandom([0.5])
    assert roll_monster_alignment(Monster.GIANT, rng) is Alignment.PAGAN

    rng = ScriptedRandom([0.99])
    assert roll_monster_alignment(Monster.GIANT, rng) is Alignment.PAGAN


def test_roll_monster_alignment_two_option_species_consumes_exactly_one_roll():
    # A second .random() call would raise IndexError if consumed.
    rng = ScriptedRandom([0.1])
    roll_monster_alignment(Monster.GIANT, rng)


def test_roll_monster_alignment_three_option_species_walks_cumulative_thresholds():
    # Renegade Priest: Good (40%) / Druidic (30%) / Neutral (30%).
    assert roll_monster_alignment(Monster.WHITE_MAGE, ScriptedRandom([0.0])) is Alignment.GOOD
    assert roll_monster_alignment(Monster.WHITE_MAGE, ScriptedRandom([0.39])) is Alignment.GOOD
    assert roll_monster_alignment(Monster.WHITE_MAGE, ScriptedRandom([0.40])) is Alignment.DRUID
    assert roll_monster_alignment(Monster.WHITE_MAGE, ScriptedRandom([0.69])) is Alignment.DRUID
    assert roll_monster_alignment(Monster.WHITE_MAGE, ScriptedRandom([0.70])) is Alignment.NEUTRAL
    assert roll_monster_alignment(Monster.WHITE_MAGE, ScriptedRandom([0.99])) is Alignment.NEUTRAL


# -- MONSTER_MAGIC_ABILITIES (Phase 177, project-original, same Desktop/
# MOSTRI con statistiche.txt source as MONSTER_COMBAT_STATS/MONSTER_
# ALIGNMENT_DISTRIBUTION) --


def test_monster_magic_abilities_covers_exactly_29_of_60_species():
    # The other 31 real species genuinely have no magic abilities at
    # all in the source -- absent, not a hidden zero-everything row.
    assert len(MONSTER_MAGIC_ABILITIES) == 29
    all_real = {m for m in Monster if m is not Monster.NOMONSTER}
    assert set(MONSTER_MAGIC_ABILITIES.keys()) <= all_real


def test_monster_magic_abilities_nomonster_sentinel_has_no_entry():
    assert Monster.NOMONSTER not in MONSTER_MAGIC_ABILITIES


def test_monster_magic_abilities_species_with_no_source_entry_are_absent():
    # Sampled from species whose Magic Abilities column was blank in the
    # source (Gryphon, Giant, Gargoyle, Troll -- the same four species
    # MONSTER_STATS's own 6-of-60 table covers).
    for monster in (Monster.GRYPHON, Monster.GIANT, Monster.GARGOYLE, Monster.TROLL):
        assert monster not in MONSTER_MAGIC_ABILITIES


def test_monster_magic_abilities_single_school_sample():
    # Spectre -- 1 NE.
    assert MONSTER_MAGIC_ABILITIES[Monster.SPECTRE] == {Ability.NECROMANCY: 1}


def test_monster_magic_abilities_four_school_sample():
    # Silver Dragon -- 3 WH, 3 PS, 3 EL, 2 IL.
    assert MONSTER_MAGIC_ABILITIES[Monster.S_DRAGON] == {
        Ability.WHITE: 3,
        Ability.PSYCHIC: 3,
        Ability.ELEMENTAL: 3,
        Ability.ILLUSION: 2,
    }


def test_monster_magic_abilities_matches_the_renegade_mages_own_school_names():
    # Each Renegade "mage" species' Monster enum name already names its
    # own primary magic school (WHITE_MAGE, NEC_MAGE, ELE_MAGE, PSY_MAGE,
    # ILL_MAGE) -- confirms the WH/NE/EL/PS/IL abbreviation mapping
    # against an independent cross-check, not just visual inspection.
    assert Ability.WHITE in MONSTER_MAGIC_ABILITIES[Monster.WHITE_MAGE]
    assert Ability.NECROMANCY in MONSTER_MAGIC_ABILITIES[Monster.NEC_MAGE]
    assert Ability.ELEMENTAL in MONSTER_MAGIC_ABILITIES[Monster.ELE_MAGE]
    assert Ability.PSYCHIC in MONSTER_MAGIC_ABILITIES[Monster.PSY_MAGE]
    assert Ability.ILLUSION in MONSTER_MAGIC_ABILITIES[Monster.ILL_MAGE]


def test_monster_magic_abilities_levels_are_all_positive():
    for monster, abilities in MONSTER_MAGIC_ABILITIES.items():
        for ability, level in abilities.items():
            assert level > 0, (monster, ability)


# -- Phase 182: Spiritwrack's Undead/Mechanical/Animal-Intelligence lists --


def test_spiritwrack_undead_monsters_matches_the_user_supplied_list():
    assert SPIRITWRACK_UNDEAD_MONSTERS == {
        Monster.SPECTRE,
        Monster.GHOST,
        Monster.VAMPIRE,
        Monster.MUMMY,
        Monster.BANSHEE,
        Monster.LICH,
    }


def test_spiritwrack_mechanical_monsters_matches_the_user_supplied_list():
    assert SPIRITWRACK_MECHANICAL_MONSTERS == {Monster.GOLEM, Monster.GARGOYLE}


def test_spiritwrack_animal_intelligence_monsters_matches_the_user_supplied_list():
    assert SPIRITWRACK_ANIMAL_INTELLIGENCE_MONSTERS == {
        Monster.GRYPHON,
        Monster.ELASMOSAURUS,
        Monster.GI_WORM,
        Monster.GI_WOLVERINE,
        Monster.GI_AMOEBA,
        Monster.GI_P_MANTIS,
        Monster.GI_SCORPION,
        Monster.GI_WASP,
        Monster.GI_SPIDER,
        Monster.GI_OCTOPUS,
        Monster.GI_CLAM,
        Monster.GW_WHALE,
    }


def test_spiritwrack_species_lists_are_pairwise_disjoint():
    # No species should appear in more than one of the three lists --
    # each represents a mutually-exclusive reason for Spiritwrack's own
    # effect to differ.
    assert not (SPIRITWRACK_UNDEAD_MONSTERS & SPIRITWRACK_MECHANICAL_MONSTERS)
    assert not (SPIRITWRACK_UNDEAD_MONSTERS & SPIRITWRACK_ANIMAL_INTELLIGENCE_MONSTERS)
    assert not (SPIRITWRACK_MECHANICAL_MONSTERS & SPIRITWRACK_ANIMAL_INTELLIGENCE_MONSTERS)


# -- Phase 185: Telekinetic Storm's submarine-monster list --


def test_telekinetic_storm_submarine_monsters_matches_the_user_supplied_list():
    assert TELEKINETIC_STORM_SUBMARINE_MONSTERS == {
        Monster.ELASMOSAURUS,
        Monster.GI_OCTOPUS,
        Monster.GI_CLAM,
        Monster.GW_WHALE,
        Monster.MERMAID,
    }


def test_telekinetic_storm_submarine_monsters_overlaps_but_is_not_identical_to_animal_intelligence():
    # Four species (Elasmosaurus/Giant Octopus/Giant Clam/Great White
    # Whale) are both submarine and animal-intelligence -- two
    # independent facts about the same species, not a mislabeled
    # duplicate list. Mermaid is submarine but NOT animal-intelligence,
    # proving the two lists are genuinely separate.
    overlap = TELEKINETIC_STORM_SUBMARINE_MONSTERS & SPIRITWRACK_ANIMAL_INTELLIGENCE_MONSTERS
    assert overlap == {Monster.ELASMOSAURUS, Monster.GI_OCTOPUS, Monster.GI_CLAM, Monster.GW_WHALE}
    assert Monster.MERMAID in TELEKINETIC_STORM_SUBMARINE_MONSTERS
    assert Monster.MERMAID not in SPIRITWRACK_ANIMAL_INTELLIGENCE_MONSTERS
