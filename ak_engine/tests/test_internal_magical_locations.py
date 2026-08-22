from __future__ import annotations

from ak_engine.models.enums import Spell
from ak_engine.models.feature import FeatureType
from ak_engine.models.magic_feature import MagicFeature
from ak_engine.models.map import Terrain
from ak_engine.models.power import Power
from ak_engine.worldgen.internal_magical_locations import (
    FORCED_NONE_CANDIDATES,
    LOCATION_RANGE,
    POWER_RANGE,
    candidate_location,
    candidate_power,
    resolve_power,
    resolve_terrain_spell_candidate,
    resolve_visible_location,
)


def test_candidate_location_matches_the_hand_worked_first_example():
    assert candidate_location(FeatureType.PYRAMID, 0) == MagicFeature.CUP


def test_candidate_location_stays_within_its_own_confirmed_range():
    for feature_type, (first, last) in LOCATION_RANGE.items():
        for feature_index in range(50):
            result = candidate_location(feature_type, feature_index)
            assert first.value <= result.value <= last.value


def test_candidate_location_covers_the_full_range_over_one_period():
    first, last = LOCATION_RANGE[FeatureType.PYRAMID]
    span = last.value - first.value + 1
    seen = {candidate_location(FeatureType.PYRAMID, i) for i in range(span)}
    assert seen == {MagicFeature(v) for v in range(first.value, last.value + 1)}


def test_candidate_location_single_choice_range_is_constant():
    # LOCH has choices=1 (Fountain..Fountain) -- always the same regardless of index.
    for feature_index in range(20):
        assert candidate_location(FeatureType.LOCH, feature_index) == MagicFeature.FOUNTAIN


def test_resolve_visible_location_forces_none_on_odd_parity():
    assert resolve_visible_location(FeatureType.PYRAMID, 0, 1) == MagicFeature.NONE
    assert resolve_visible_location(FeatureType.PYRAMID, 2, 5) == MagicFeature.NONE


def test_resolve_visible_location_shows_the_candidate_on_even_parity():
    assert resolve_visible_location(FeatureType.PYRAMID, 0, 0) == MagicFeature.CUP


def test_resolve_visible_location_forces_none_for_gastrap_and_seal_candidates():
    # DUNGEON's range (Pool..Seal) reaches Seal at offset 18 (span 19):
    # feature_index + 7 (DUNGEON ordinal) == 18 (mod 19) -> feature_index == 11.
    feature_index = 11
    assert candidate_location(FeatureType.DUNGEON, feature_index) == MagicFeature.SEALED_ENTRANCE
    # Pick a feature_x whose sum with feature_index is even, so the parity
    # gate alone wouldn't hide it.
    feature_x = 1
    assert (feature_index + feature_x) % 2 == 0
    assert resolve_visible_location(FeatureType.DUNGEON, feature_index, feature_x) == MagicFeature.NONE


def test_resolve_visible_location_matches_special_features_gw3_t1_catalog():
    # ``Special Features.md`` section 8 (user-supplied 2026-08-22), real
    # rows from the GW3__T1 world's 128 Features -- (feature_index,
    # feature_x, feature_type) -> expected visible MagicFeature. Byte-
    # for-byte oracle rows, not formula-shape tests; confirms both the
    # parity polarity and the candidate_location table (including the
    # exact alternate-form display names, "Prayer Rug"/"Director's
    # Chair") with zero feature_index offset.
    cases = [
        (0, 12, FeatureType.TOMB, MagicFeature.ALTAR),  # "Prayer Rug"
        (1, 10, FeatureType.ALTAR, MagicFeature.NONE),
        (2, 3, FeatureType.CAVE, MagicFeature.NONE),
        (5, 3, FeatureType.TEMPLE, MagicFeature.POOL),
        (7, 17, FeatureType.PYRAMID, MagicFeature.PENTAGRAM),
        (8, 2, FeatureType.SACRED_ROCK, MagicFeature.THRONE),  # "Director's Chair"
        (9, 17, FeatureType.CATACOMBS, MagicFeature.ROULETTE_WHEEL),
        (16, 10, FeatureType.HOLLOW_TREE, MagicFeature.PENTAGRAM),
        (17, 3, FeatureType.CRYPT, MagicFeature.BOOK),
    ]
    for feature_index, feature_x, feature_type, expected in cases:
        assert resolve_visible_location(feature_type, feature_index, feature_x) == expected


def test_resolve_power_matches_special_features_gw3_t1_catalog():
    # Same source and rows as above, carried through to the resulting Power.
    cases = [
        (MagicFeature.ALTAR, 0, FeatureType.TOMB, Power.WARP_SPACE),
        (MagicFeature.POOL, 5, FeatureType.TEMPLE, Power.UP_SKILL),
        (MagicFeature.PENTAGRAM, 7, FeatureType.PYRAMID, Power.UP_SKILL),
        (MagicFeature.THRONE, 8, FeatureType.SACRED_ROCK, Power.ORAC_ALIGN),
        (MagicFeature.ROULETTE_WHEEL, 9, FeatureType.CATACOMBS, Power.CHANCE),
        (MagicFeature.PENTAGRAM, 16, FeatureType.HOLLOW_TREE, Power.UP_SKILL),
        (MagicFeature.BOOK, 17, FeatureType.CRYPT, Power.CAST_SPELL),
    ]
    for location, feature_index, feature_type, expected in cases:
        assert resolve_power(location, feature_index, feature_type.value) == expected


def test_forced_none_candidates_are_exactly_gastrap_and_seal():
    assert FORCED_NONE_CANDIDATES == {MagicFeature.GAS_TRAP, MagicFeature.SEALED_ENTRANCE}


def test_candidate_power_stays_within_its_own_confirmed_range():
    for location, (first, last) in POWER_RANGE.items():
        for feature_index in range(10):
            for feature_type in range(10):
                for tries in range(3):
                    result = candidate_power(location, feature_index, feature_type, tries)
                    assert first.value <= result.value <= last.value


def test_resolve_power_stops_early_on_a_tries_zero_cast_spell_hit():
    # GAS_TRAP's range is CastSpell..CastSpell (span 1) -- always an
    # immediate early-stop hit regardless of feature_index/feature_type.
    result = resolve_power(MagicFeature.GAS_TRAP, feature_index=3, feature_type=7)
    assert result == Power.CAST_SPELL


def test_resolve_power_exhausts_all_three_tries_when_no_early_stop_is_possible():
    # POOL's range (NewSex..DnSkill) never includes CastSpell or AnsPrayer,
    # so resolve_power must fall through to the tries=2 candidate.
    location = MagicFeature.POOL
    feature_index, feature_type = 4, 1
    expected = candidate_power(location, feature_index, feature_type, 2)
    assert resolve_power(location, feature_index, feature_type) == expected


def test_resolve_power_never_returns_a_power_outside_its_own_location_range():
    for location, (first, last) in POWER_RANGE.items():
        for feature_index in range(5):
            for feature_type in range(5):
                result = resolve_power(location, feature_index, feature_type)
                assert first.value <= result.value <= last.value


# -- Phase 620: resolve_terrain_spell_candidate() (Set_Spell) --


def test_resolve_terrain_spell_candidate_part_sea_valid_off_mountains():
    # PYRAMID's own ordinal is 0, so modval == feature_index directly:
    # fn=1 -> setval=1 == Spell.PART_SEA.
    assert resolve_terrain_spell_candidate(FeatureType.PYRAMID, 1, Terrain.SEA) is Spell.PART_SEA
    assert resolve_terrain_spell_candidate(FeatureType.PYRAMID, 1, Terrain.PLAINS) is Spell.PART_SEA


def test_resolve_terrain_spell_candidate_part_sea_invalid_on_mountains():
    assert resolve_terrain_spell_candidate(FeatureType.PYRAMID, 1, Terrain.MTNS) is None


def test_resolve_terrain_spell_candidate_flood_valid_off_mountains():
    assert resolve_terrain_spell_candidate(FeatureType.PYRAMID, 8, Terrain.SEA) is Spell.FLOOD
    assert resolve_terrain_spell_candidate(FeatureType.PYRAMID, 8, Terrain.MTNS) is None


def test_resolve_terrain_spell_candidate_earthquake_valid_off_sea():
    assert resolve_terrain_spell_candidate(FeatureType.PYRAMID, 10, Terrain.PLAINS) is Spell.EARTHQUAKE
    assert resolve_terrain_spell_candidate(FeatureType.PYRAMID, 10, Terrain.MTNS) is Spell.EARTHQUAKE


def test_resolve_terrain_spell_candidate_earthquake_invalid_on_sea():
    assert resolve_terrain_spell_candidate(FeatureType.PYRAMID, 10, Terrain.SEA) is None


def test_resolve_terrain_spell_candidate_excludes_the_12_extra_spells():
    # fn=0 -> setval=0 == Spell.RESURRECTION, one of the always-excluded
    # "extra spells" -- None regardless of terrain.
    assert resolve_terrain_spell_candidate(FeatureType.PYRAMID, 0, Terrain.SEA) is None
    assert resolve_terrain_spell_candidate(FeatureType.PYRAMID, 0, Terrain.PLAINS) is None


def test_resolve_terrain_spell_candidate_unresolved_without_miscwrit():
    # fn=2 -> setval=2 == Spell.BLESS -- a real, non-excluded ordinal,
    # but not one of the 3 territory-filtered spells, so it needs the
    # unsourced miscwrit flag and stays unresolved.
    assert resolve_terrain_spell_candidate(FeatureType.PYRAMID, 2, Terrain.SEA) is None
    assert resolve_terrain_spell_candidate(FeatureType.PYRAMID, 2, Terrain.PLAINS) is None
