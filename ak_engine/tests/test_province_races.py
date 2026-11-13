from __future__ import annotations

from collections import Counter

from ak_engine.models.map import Terrain
from ak_engine.models.race import Race
from ak_engine.worldgen.pascal_random import PascalRandom
from ak_engine.worldgen.province_races import draw_base_race

# base_percent_before_special_overwrites, straight from the AKGEN source.
_CONFIRMED_FINAL_PERCENT: dict[Terrain, dict[Race, float]] = {
    Terrain.PLAINS: {Race.HUMAN: 77.5, Race.ELVEN: 7.5, Race.DWARVEN: 7.5, Race.ORCISH: 7.5},
    Terrain.DESERT: {Race.HUMAN: 77.5, Race.ELVEN: 7.5, Race.DWARVEN: 7.5, Race.ORCISH: 7.5},
    Terrain.JUNGLE: {Race.HUMAN: 77.5, Race.ELVEN: 7.5, Race.DWARVEN: 7.5, Race.ORCISH: 7.5},
    Terrain.FOREST: {Race.HUMAN: 46.5, Race.ELVEN: 44.5, Race.DWARVEN: 4.5, Race.ORCISH: 4.5},
    Terrain.MTNS: {
        Race.HUMAN: 46.1125,
        Race.ELVEN: 4.4625,
        Race.DWARVEN: 34.4625,
        Race.ORCISH: 14.9625,
    },
}


def test_draw_base_race_matches_the_confirmed_final_percentages_per_terrain():
    rng = PascalRandom(seed=1)
    n = 200_000
    for terrain, expected in _CONFIRMED_FINAL_PERCENT.items():
        counts = Counter(draw_base_race(terrain, rng) for _ in range(n))
        for race, expected_pct in expected.items():
            actual_pct = counts.get(race, 0) / n * 100
            assert abs(actual_pct - expected_pct) < 0.4, (terrain, race)


def test_draw_base_race_is_always_norace_on_sea():
    rng = PascalRandom(seed=2)
    for _ in range(2000):
        assert draw_base_race(Terrain.SEA, rng) is Race.NO_RACE


def test_draw_base_race_is_always_norace_on_no_terrain():
    rng = PascalRandom(seed=3)
    for _ in range(2000):
        assert draw_base_race(Terrain.NO_TERRAIN, rng) is Race.NO_RACE


def test_draw_base_race_is_confined_to_the_four_mix_races_on_plains():
    # Bug fix: this used to claim Plains "never produces Orcish or
    # Elven" -- false for the real draw_base_race(): the humanoid-mix
    # layer it applies on top of Plains' own Human-only provisional
    # roll confirms Elven/Dwarven/Orcish each at 7.5%
    # (_CONFIRMED_FINAL_PERCENT[Terrain.PLAINS] above). The old
    # assertion's own allowed set already included all four races, so
    # it passed trivially regardless and never caught this
    # contradiction between the comment and the real distribution.
    # What IS a real, checkable invariant: a land terrain like Plains
    # never yields NO_RACE or any race outside this confirmed 4-race
    # set -- and (using == rather than <=) every one of the four must
    # actually appear, so a regression that silently made one of them
    # impossible (e.g. a broken humanoid-mix layer) would be caught too.
    rng = PascalRandom(seed=4)
    results = {draw_base_race(Terrain.PLAINS, rng) for _ in range(3000)}
    assert results == {Race.HUMAN, Race.ELVEN, Race.DWARVEN, Race.ORCISH}


def test_draw_base_race_forest_never_produces_dwarves_above_the_mix_share():
    # Forest's provisional draw is only ever Human or Elf -- Dwarf/Orc can
    # only come from the humanoid mix layer, so their combined share
    # should stay well under Human/Elf's.
    rng = PascalRandom(seed=5)
    counts = Counter(draw_base_race(Terrain.FOREST, rng) for _ in range(50_000))
    assert counts[Race.DWARVEN] < counts[Race.HUMAN]
    assert counts[Race.ORCISH] < counts[Race.ELVEN]


def test_draw_base_race_is_deterministic_for_a_given_seed():
    a = PascalRandom(seed=777)
    b = PascalRandom(seed=777)
    sequence_a = [draw_base_race(Terrain.MTNS, a) for _ in range(100)]
    sequence_b = [draw_base_race(Terrain.MTNS, b) for _ in range(100)]
    assert sequence_a == sequence_b
