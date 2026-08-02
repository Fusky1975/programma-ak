from __future__ import annotations

from ak_engine.models.map import HexCoord
from ak_engine.models.race import Race
from ak_engine.worldgen.pascal_random import PascalRandom
from ak_engine.worldgen.leader_placement import (
    COMPANIONS_PER_KING,
    RESERVED_ROSTER_COUNT,
    IndependentLordEffects,
    KingHomeEffects,
    companion_count,
    draw_mercenary_relocation_coordinate,
    draw_second_companion_race,
    independent_lord_effects,
    king_home_effects,
    owner_leader_count,
    remaining_mercenary_count,
)
from ak_engine.worldgen.province_tax import HOME_OVERRIDE_TAX

# -- GW900_K4: fully self-contained real example -----------------------
GW900_K4_HUMANOID_PROVINCES = 45
GW900_K4_KING_COUNT = 4
GW900_K4_LEADER_COUNT = 100  # owner(45) + companions(8) + reserved(1) + mercenaries(46)
GW900_K4_OWNER_LEADERS = 45
GW900_K4_COMPANIONS = 8
GW900_K4_REMAINING_MERCENARIES = 46

# -- GW3_T1_K10: leader_count reconstructed from the source's own counts
GW3_T1_K10_KING_COUNT = 10
GW3_T1_K10_LEADER_COUNT = 79 + 20 + 1 + 0
GW3_T1_K10_OWNER_LEADERS = 79
GW3_T1_K10_COMPANIONS = 20
GW3_T1_K10_REMAINING_MERCENARIES = 0


def test_owner_leader_count_matches_gw900_k4():
    result = owner_leader_count(
        GW900_K4_HUMANOID_PROVINCES, GW900_K4_LEADER_COUNT, GW900_K4_KING_COUNT
    )
    assert result == GW900_K4_OWNER_LEADERS


def test_owner_leader_count_matches_gw3_t1_k10_reconstructed_leader_count():
    # humanoid_province_count isn't given directly for this example, but
    # any value >= 79 reproduces the confirmed 79 via the min() -- use 79
    # itself as the tightest consistent value.
    result = owner_leader_count(79, GW3_T1_K10_LEADER_COUNT, GW3_T1_K10_KING_COUNT)
    assert result == GW3_T1_K10_OWNER_LEADERS


def test_companion_count_matches_both_examples():
    assert companion_count(GW900_K4_KING_COUNT) == GW900_K4_COMPANIONS
    assert companion_count(GW3_T1_K10_KING_COUNT) == GW3_T1_K10_COMPANIONS
    assert COMPANIONS_PER_KING == 2


def test_remaining_mercenary_count_matches_both_examples():
    assert (
        remaining_mercenary_count(GW900_K4_LEADER_COUNT, GW900_K4_OWNER_LEADERS, GW900_K4_COMPANIONS)
        == GW900_K4_REMAINING_MERCENARIES
    )
    assert (
        remaining_mercenary_count(
            GW3_T1_K10_LEADER_COUNT, GW3_T1_K10_OWNER_LEADERS, GW3_T1_K10_COMPANIONS
        )
        == GW3_T1_K10_REMAINING_MERCENARIES
    )


def test_reserved_roster_count_is_always_one():
    assert RESERVED_ROSTER_COUNT == 1


def test_king_home_effects_matches_the_confirmed_mutation_set():
    home = HexCoord(3, 4)
    effects = king_home_effects(king_leader_id=7, king_race=Race.DWARVEN, home_coord=home)
    assert effects == KingHomeEffects(
        province_owner_id=7,
        province_tax=HOME_OVERRIDE_TAX,
        province_race=Race.DWARVEN,
        leader_current_coord=home,
        leader_born_coord=home,
    )


def test_independent_lord_effects_matches_the_confirmed_mutation_set():
    coord = HexCoord(9, 2)
    effects = independent_lord_effects(leader_id=42, province_coord=coord, province_race=Race.ELVEN)
    assert effects == IndependentLordEffects(
        province_owner_id=42,
        leader_current_coord=coord,
        leader_born_coord=coord,
        leader_race=Race.ELVEN,
    )


def test_draw_second_companion_race_never_matches_the_kings_race():
    rng = PascalRandom(seed=1)
    for king_race in (Race.HUMAN, Race.ELVEN, Race.DWARVEN, Race.ORCISH):
        for _ in range(500):
            assert draw_second_companion_race(king_race, rng) is not king_race


def test_draw_second_companion_race_is_roughly_uniform_over_the_other_three():
    from collections import Counter

    rng = PascalRandom(seed=2)
    counts = Counter(draw_second_companion_race(Race.HUMAN, rng) for _ in range(30_000))
    assert set(counts) == {Race.ELVEN, Race.DWARVEN, Race.ORCISH}
    for race in (Race.ELVEN, Race.DWARVEN, Race.ORCISH):
        assert abs(counts[race] / 30_000 - 1 / 3) < 0.02


def test_draw_mercenary_relocation_coordinate_never_lands_on_sea_or_king_owned():
    rng = PascalRandom(seed=3)
    sea_coord = HexCoord(1, 1)
    king_owned_coord = HexCoord(2, 2)

    def is_sea(c: HexCoord) -> bool:
        return c == sea_coord

    def is_king_owned(c: HexCoord) -> bool:
        return c == king_owned_coord

    for _ in range(2000):
        result = draw_mercenary_relocation_coordinate(rng, 5, 5, is_sea, is_king_owned)
        assert result != sea_coord
        assert result != king_owned_coord
        assert 0 <= result.x < 5
        assert 0 <= result.y < 5
