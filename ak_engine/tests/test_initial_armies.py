from __future__ import annotations

import pytest

from ak_engine.models.army_type import ARMY_TYPE_BY_ORDINAL, ArmyType, MONSTROUS_ARMY_RACE
from ak_engine.models.map import Terrain
from ak_engine.models.race import Race
from ak_engine.turn.combat import Quality
from ak_engine.worldgen.initial_armies import (
    BEST_ATYPE,
    COMMANDER_NONE,
    FLEET_SECOND_SLOT_CHANCE,
    HUMANOID_FIRST_SLOT_RACES,
    INITIAL_ARMY_QUALITY,
    KING_HOME_BUDGET,
    MAX_ARMIES_PER_PROVINCE_PASS,
    NATIVE_ARMY_TYPE,
    _draw_humanoid_terrain_ordinal,
    build_initial_armies,
    draw_r4,
    fleet_second_slot_chance,
    fleet_second_slot_gate,
    flying_or_special_budget,
    home_first_slot,
    humanoid_first_slot,
    humanoid_second_slot,
    ordinary_humanoid_budget,
    ordinary_second_army,
    province_random,
    resolve_commander,
    second_slot_gate,
    second_slot_gate_probability,
    special_race_recruit_slot,
    whale_budget,
)
from ak_engine.worldgen.pascal_random import PascalRandom


class _StubRandom:
    """A minimal ``.random()``-only stand-in, since ``province_random()``/
    ``humanoid_first_slot()`` never call ``irand()`` -- lets tests script
    an exact ``rng.random()`` sequence the way this project's own
    ``turn/``-scoped tests already do via ``ScriptedRandom``, without
    needing a real ``PascalRandom`` seed search for these pure-formula
    functions.
    """

    def __init__(self, values: list[float]) -> None:
        self._values = iter(values)

    def random(self) -> float:
        return next(self._values)


def test_best_atype_matches_the_confirmed_table():
    assert BEST_ATYPE == {
        Race.HUMAN: ArmyType.LEGION,
        Race.ELVEN: ArmyType.BOWMEN,
        Race.DWARVEN: ArmyType.AXEMEN,
        Race.ORCISH: ArmyType.PHALANX,
    }


def test_home_first_slot_matches_best_atype():
    for race, army_type in BEST_ATYPE.items():
        assert home_first_slot(race) == army_type


def test_native_army_type_is_the_exact_inverse_of_monstrous_army_race():
    assert NATIVE_ARMY_TYPE == {race: army_type for army_type, race in MONSTROUS_ARMY_RACE.items()}
    for race in NATIVE_ARMY_TYPE:
        assert special_race_recruit_slot(race) == NATIVE_ARMY_TYPE[race]


def test_native_army_type_covers_every_race_the_source_names_including_vampires():
    # Phase 383 closed the previously-documented Vampires gap (see
    # worldgen/initial_armies.py's own updated module docstring) --
    # `special_races` names exactly these 8 races, all now covered.
    named_races = {
        Race.DRAGONS,
        Race.EAGLES,
        Race.WHALES,
        Race.MERMISH,
        Race.ENTISH,
        Race.TROLLISH,
        Race.WEREFOLK,
        Race.VAMPISH,
    }
    assert named_races <= set(NATIVE_ARMY_TYPE)
    assert NATIVE_ARMY_TYPE[Race.VAMPISH] == ArmyType.VAMPIRES


def test_second_slot_gate_matches_the_hand_derived_probability():
    rng = PascalRandom(seed=1)
    n = 100_000
    for tax in (0, 1, 3, 5, 8, 10):
        successes = sum(1 for _ in range(n) if second_slot_gate(tax, rng))
        expected = second_slot_gate_probability(tax)
        assert abs(successes / n - expected) < 0.01


def test_second_slot_gate_probability_caps_at_tax_8():
    assert second_slot_gate_probability(8) == 1.0
    assert second_slot_gate_probability(20) == 1.0
    assert second_slot_gate_probability(0) == 0.0


def test_fleet_second_slot_chance_matches_the_real_table():
    assert fleet_second_slot_chance(0) == 0.0
    assert fleet_second_slot_chance(1) == 0.0
    assert fleet_second_slot_chance(2) == 0.5
    assert fleet_second_slot_chance(3) == 0.7
    assert fleet_second_slot_chance(4) == 1.0
    assert fleet_second_slot_chance(5) == 0.5
    assert fleet_second_slot_chance(6) == 0.7


def test_fleet_second_slot_chance_defaults_to_zero_outside_the_real_domain():
    assert fleet_second_slot_chance(-1) == 0.0
    assert fleet_second_slot_chance(7) == 0.0


def test_fleet_second_slot_gate_desert_never_places_fleet_with_zero_draws():
    for effective_sea_neighbors in FLEET_SECOND_SLOT_CHANCE:
        rng = _StubRandom([])  # zero draws -- terrain checked before any ProvinceRandom call
        assert fleet_second_slot_gate(Terrain.DESERT, 0, 0, effective_sea_neighbors, rng) is False


@pytest.mark.parametrize("terrain", [Terrain.PLAINS, Terrain.JUNGLE, Terrain.FOREST, Terrain.MTNS])
def test_fleet_second_slot_gate_matches_the_real_province_random_comparison(terrain):
    # x=1,y=0 -> parity=1, ProvinceRandom range [0.25, 0.5); effective_sea_neighbors=2 -> chance 0.5
    rng_below = _StubRandom([0.5, 0.99999])
    assert fleet_second_slot_gate(terrain, 1, 0, 2, rng_below) is True

    # x=0,y=1 -> parity=2, ProvinceRandom range [0.5, 0.75); effective_sea_neighbors=2 -> chance 0.5
    rng_above = _StubRandom([0.5, 0.00001])
    assert fleet_second_slot_gate(terrain, 0, 1, 2, rng_above) is False

    # same parity=2 range, effective_sea_neighbors=3 -> chance 0.7
    rng_below2 = _StubRandom([0.5, 0.79999])
    assert fleet_second_slot_gate(terrain, 0, 1, 3, rng_below2) is True
    rng_above2 = _StubRandom([0.5, 0.80001])
    assert fleet_second_slot_gate(terrain, 0, 1, 3, rng_above2) is False


def test_fleet_second_slot_gate_matches_the_real_section_9_3_formula():
    # P(ProvinceRandom < t) = 0.02*t + 0.98*clamp(4*t-q, 0, 1), q=(x&1)+2*(y&1)
    rng = PascalRandom(seed=4)
    n = 100_000
    x, y = 0, 1  # q = 0 + 2*1 = 2
    q = (x & 1) + 2 * (y & 1)
    for effective_sea_neighbors in (2, 3, 4):
        t = fleet_second_slot_chance(effective_sea_neighbors)
        expected = 0.02 * t + 0.98 * max(0.0, min(1.0, 4 * t - q))
        successes = sum(
            1 for _ in range(n) if fleet_second_slot_gate(Terrain.PLAINS, x, y, effective_sea_neighbors, rng)
        )
        assert abs(successes / n - expected) < 0.01


def test_fleet_second_slot_gate_raises_for_unsupported_terrain():
    with pytest.raises(ValueError):
        fleet_second_slot_gate(Terrain.SEA, 0, 0, 2, _StubRandom([]))


def test_draw_r4_stays_within_1_to_4():
    rng = PascalRandom(seed=2)
    for _ in range(3000):
        assert 1 <= draw_r4(rng) <= 4


def test_ordinary_humanoid_budget_stays_within_documented_range():
    # Phase 902 (TROLL.md): the real factor is confined to [0.65, 0.9),
    # not the full [0, 0.9) the previously-shipped formula allowed.
    rng = PascalRandom(seed=3)
    for tax in range(0, 11):
        for _ in range(500):
            budget = ordinary_humanoid_budget(tax, rng)
            assert int(tax * 0.65) + 1 <= budget <= int(tax * 0.9) + 1


class _FixedRandom:
    """Minimal ``PascalRandom``-compatible stub returning a fixed ``random()``."""

    def __init__(self, value: float) -> None:
        self._value = value

    def random(self) -> float:
        return self._value


def test_ordinary_humanoid_budget_matches_the_byte_verified_formula_exactly():
    # Trunc(ptax * (0.9 - 0.25*Random)) + 1 -- a subtraction from a
    # constant, not a multiplication by a uniform fraction (TROLL.md's
    # own "Verifica decisiva del segno" section).
    assert ordinary_humanoid_budget(10, _FixedRandom(0.0)) == int(10 * 0.9) + 1  # 10
    assert ordinary_humanoid_budget(10, _FixedRandom(1.0)) == int(10 * 0.65) + 1  # 7
    assert ordinary_humanoid_budget(0, _FixedRandom(0.5)) == 1


def test_whale_budget_stays_within_documented_range():
    rng = PascalRandom(seed=4)
    for tax in range(0, 11):
        for _ in range(500):
            budget = whale_budget(tax, rng)
            assert tax + 2 <= budget <= tax + 5


def test_flying_or_special_budget_stays_within_documented_range():
    rng = PascalRandom(seed=5)
    for tax in range(0, 11):
        for _ in range(500):
            budget = flying_or_special_budget(tax, rng)
            assert tax - 3 <= budget <= tax + 3


def test_king_home_budget_is_the_confirmed_fixed_value():
    assert KING_HOME_BUDGET == 7


def test_build_initial_armies_alternates_slots_and_spends_budget_exactly():
    # LEGION strength 3, BOWMEN strength 2 -- budget 5 exactly affords one
    # of each: 3 (LEGION) + 2 (BOWMEN) == 5, remaining 0 stops the loop.
    armies = build_initial_armies(ArmyType.LEGION, ArmyType.BOWMEN, budget=5)
    assert armies == [ArmyType.LEGION, ArmyType.BOWMEN]


def test_build_initial_armies_repeats_the_first_slot_when_the_second_is_none():
    # LEGION strength 3, budget 10 -> three LEGIONs (9 spent), a fourth
    # would need 12 total so it stops at 3, well under the 4-army cap.
    armies = build_initial_armies(ArmyType.LEGION, None, budget=10)
    assert armies == [ArmyType.LEGION, ArmyType.LEGION, ArmyType.LEGION]


def test_build_initial_armies_stops_at_the_four_army_cap():
    # BOWMEN strength 2, budget 100 -- budget alone would allow 50 armies,
    # but the cap stops it at 4.
    armies = build_initial_armies(ArmyType.BOWMEN, ArmyType.BOWMEN, budget=100)
    assert len(armies) == MAX_ARMIES_PER_PROVINCE_PASS


def test_build_initial_armies_returns_empty_when_slot0_is_none():
    assert build_initial_armies(None, ArmyType.BOWMEN, budget=100) == []


def test_build_initial_armies_returns_empty_when_budget_cannot_afford_slot0():
    assert build_initial_armies(ArmyType.LEGION, None, budget=2) == []


def test_resolve_commander_matches_the_confirmed_three_cases():
    assert resolve_commander(owner_leader_id=None, is_king_home=True) == COMMANDER_NONE
    assert resolve_commander(owner_leader_id=None, is_king_home=False) == COMMANDER_NONE
    assert resolve_commander(owner_leader_id=42, is_king_home=True) == COMMANDER_NONE
    assert resolve_commander(owner_leader_id=42, is_king_home=False) == 42


def test_initial_army_quality_matches_the_confirmed_average():
    assert INITIAL_ARMY_QUALITY == Quality.AVERAGE
    assert INITIAL_ARMY_QUALITY == 2


# -- Phase 797: the ordinary-humanoid-province first recruit slot -----------


def test_province_random_low_test_value_forces_the_plain_draw_branch():
    rng = _StubRandom([0.01, 0.5])
    assert province_random(0, 0, rng) == 0.5


def test_province_random_high_test_value_matches_the_parity_formula_for_all_4_quadrants():
    for x, y, u in ((0, 0, 0.3), (1, 0, 0.3), (0, 1, 0.3), (1, 1, 0.3)):
        rng = _StubRandom([0.5, u])
        parity = (x & 1) + 2 * (y & 1)
        assert province_random(x, y, rng) == (u + parity) * 0.25


def test_province_random_initially_owned_by_king_always_takes_the_plain_draw_branch():
    # Regardless of the (irrelevant, since it's never even checked once
    # initially_owned_by_king is True) test roll's own value.
    rng = _StubRandom([0.99, 0.7])
    assert province_random(5, 5, rng, initially_owned_by_king=True) == 0.7
    rng = _StubRandom([0.01, 0.4])
    assert province_random(5, 5, rng, initially_owned_by_king=True) == 0.4


def test_draw_humanoid_terrain_ordinal_plains_never_rejects():
    rng = _StubRandom([0.5, 0.1])
    assert _draw_humanoid_terrain_ordinal(Terrain.PLAINS, 0, 0, rng) == 1


def test_draw_humanoid_terrain_ordinal_jungle_forest_mtns_reject_phalanx_and_retry():
    # x=0,y=1 -> parity=2 -> the biased branch always lands on ordinal 3
    # (Phalanx) first; a scripted low second `test` forces the plain-
    # draw branch for the retry, landing on a different ordinal (4).
    for terrain in (Terrain.JUNGLE, Terrain.FOREST, Terrain.MTNS):
        rng = _StubRandom([0.5, 0.5, 0.01, 0.9])
        assert _draw_humanoid_terrain_ordinal(terrain, 0, 1, rng) == 4


def test_draw_humanoid_terrain_ordinal_desert_rejects_axemen_and_retries():
    # x=1,y=0 -> parity=1 -> the biased branch always lands on ordinal 2
    # (Axemen) first via Desert's own `Trunc(4*ProvinceRandom+1)` shape;
    # the scripted retry lands on a different ordinal (4).
    rng = _StubRandom([0.5, 0.5, 0.01, 0.9])
    assert _draw_humanoid_terrain_ordinal(Terrain.DESERT, 1, 0, rng) == 4


def test_draw_humanoid_terrain_ordinal_raises_for_an_unsupported_terrain():
    with pytest.raises(ValueError):
        _draw_humanoid_terrain_ordinal(Terrain.SEA, 0, 0, _StubRandom([]))


def test_humanoid_first_slot_races_is_the_real_race_orcish_domain_rohan_excluded():
    assert HUMANOID_FIRST_SLOT_RACES == (Race.HUMAN, Race.ELVEN, Race.DWARVEN, Race.ORCISH)
    assert Race.ROHAN not in HUMANOID_FIRST_SLOT_RACES


def test_humanoid_first_slot_initially_owned_by_king_returns_best_atype_with_zero_draws():
    for race in HUMANOID_FIRST_SLOT_RACES:
        rng = _StubRandom([])  # no IndexError/StopIteration -- zero rng consumption
        assert humanoid_first_slot(Terrain.PLAINS, race, 0, 0, rng, initially_owned_by_king=True) == BEST_ATYPE[race]


def test_humanoid_first_slot_coin_flip_of_1_overrides_to_best_atype():
    rng = _StubRandom([0.5, 0.1, 0.9])  # terrain draw lands on ordinal 1 (Bowmen), coin=1
    assert humanoid_first_slot(Terrain.PLAINS, Race.HUMAN, 0, 0, rng) == BEST_ATYPE[Race.HUMAN]
    assert BEST_ATYPE[Race.HUMAN] != ARMY_TYPE_BY_ORDINAL[1]


def test_humanoid_first_slot_coin_flip_of_0_keeps_the_terrain_drawn_army_type():
    rng = _StubRandom([0.5, 0.1, 0.2])  # same terrain draw (ordinal 1), coin=0
    assert humanoid_first_slot(Terrain.PLAINS, Race.HUMAN, 0, 0, rng) == ARMY_TYPE_BY_ORDINAL[1]


def test_humanoid_first_slot_plains_only_ever_produces_infantry_across_all_4_races():
    rng = PascalRandom(seed=7)
    infantry = {ArmyType.BOWMEN, ArmyType.AXEMEN, ArmyType.PHALANX, ArmyType.LEGION}
    for _ in range(2000):
        for race in HUMANOID_FIRST_SLOT_RACES:
            result = humanoid_first_slot(Terrain.PLAINS, race, 3, 4, rng)
            assert result in infantry


# -- Phase 799 ("SECONDARMY.md", backlog #22's own last piece) -------------


class _StubRandomWithIrand(_StubRandom):
    """Adds ``irand()`` on top of ``_StubRandom``'s own ``.random()`` --
    ``humanoid_second_slot()`` calls ``second_slot_gate()`` (Phase 358),
    the one piece of this new chain that needs an ``irand()`` draw.
    """

    def __init__(self, irand_values: list[int], random_values: list[float]) -> None:
        super().__init__(random_values)
        self._irand_values = iter(irand_values)

    def irand(self, *, irand_range: int = 0) -> int:
        del irand_range
        return next(self._irand_values)


def test_ordinary_second_army_base_draw_matches_the_three_real_ordinals():
    # Forest + a non-Orcish race never substitutes -- the plain base
    # draw (ordinals 5/6/7 = Lt Cavalry/Hvy Cavalry/Chariots) survives
    # unmodified, proving ARMY_TYPE_BY_ORDINAL's own real index scheme.
    assert ordinary_second_army(Terrain.FOREST, Race.HUMAN, 0, 0, _StubRandom([0.01, 0.1])) == ArmyType.LT_CAVALRY
    assert ordinary_second_army(Terrain.FOREST, Race.HUMAN, 0, 0, _StubRandom([0.01, 0.5])) == ArmyType.HVY_CAVALRY
    assert ordinary_second_army(Terrain.FOREST, Race.HUMAN, 0, 0, _StubRandom([0.01, 0.9])) == ArmyType.CHARIOTS


def test_ordinary_second_army_orcish_coin_hit_returns_wargriders_and_stops():
    # The base draw is still consumed even though it's about to be
    # overwritten (section 8's own fidelity note) -- exactly 3 values,
    # no StopIteration, proves no further terrain checks run afterward.
    rng = _StubRandom([0.01, 0.1, 0.9])  # base draw, then coin=1
    assert ordinary_second_army(Terrain.FOREST, Race.ORCISH, 0, 0, rng) == ArmyType.WARG_RIDERS


def test_ordinary_second_army_orcish_coin_miss_falls_through_to_terrain_checks():
    rng = _StubRandom([0.01, 0.1, 0.1])  # base draw (Lt Cavalry), coin=0
    assert ordinary_second_army(Terrain.FOREST, Race.ORCISH, 0, 0, rng) == ArmyType.LT_CAVALRY


def test_ordinary_second_army_jungle_coin_hit_and_miss():
    hit = _StubRandom([0.01, 0.1, 0.9])
    assert ordinary_second_army(Terrain.JUNGLE, Race.HUMAN, 0, 0, hit) == ArmyType.ELEPHANTS
    miss = _StubRandom([0.01, 0.1, 0.1])
    assert ordinary_second_army(Terrain.JUNGLE, Race.HUMAN, 0, 0, miss) == ArmyType.LT_CAVALRY


def test_ordinary_second_army_desert_coin_hit_and_miss():
    hit = _StubRandom([0.01, 0.1, 0.9])
    assert ordinary_second_army(Terrain.DESERT, Race.HUMAN, 0, 0, hit) == ArmyType.CAMEL_CORPS
    miss = _StubRandom([0.01, 0.1, 0.1])
    assert ordinary_second_army(Terrain.DESERT, Race.HUMAN, 0, 0, miss) == ArmyType.LT_CAVALRY


@pytest.mark.parametrize("terrain", [Terrain.PLAINS, Terrain.MTNS])
def test_ordinary_second_army_plains_mtns_camels_only_on_eligible_rows(terrain):
    hit = _StubRandom([0.01, 0.1, 0.01, 0.1])  # base draw, then a threshold draw < 0.20
    assert ordinary_second_army(terrain, Race.HUMAN, 0, 2, hit) == ArmyType.CAMEL_CORPS
    miss = _StubRandom([0.01, 0.1, 0.01, 0.5])  # threshold draw >= 0.20
    assert ordinary_second_army(terrain, Race.HUMAN, 0, 2, miss) == ArmyType.LT_CAVALRY
    non_eligible_row = _StubRandom([0.01, 0.1])  # y=0 -- zero extra draws, no StopIteration
    assert ordinary_second_army(terrain, Race.HUMAN, 0, 0, non_eligible_row) == ArmyType.LT_CAVALRY


def test_ordinary_second_army_forest_never_substitutes():
    rng = _StubRandom([0.01, 0.5])
    assert ordinary_second_army(Terrain.FOREST, Race.HUMAN, 0, 0, rng) == ArmyType.HVY_CAVALRY


def test_ordinary_second_army_raises_for_an_unsupported_terrain():
    with pytest.raises(ValueError):
        ordinary_second_army(Terrain.SEA, Race.HUMAN, 0, 0, _StubRandom([0.01, 0.1]))


def test_humanoid_second_slot_b_fails_returns_none_with_no_further_draws():
    rng = _StubRandomWithIrand(irand_values=[0], random_values=[])
    assert humanoid_second_slot(Terrain.PLAINS, Race.HUMAN, 0, 0, tax=0, effective_sea_neighbors=2, rng=rng) is None


def test_humanoid_second_slot_b_passes_f_succeeds_returns_fleet_without_the_helper():
    # tax=8 guarantees B; effective_sea_neighbors=4 -> fleet chance 1.0,
    # so any real ProvinceRandom value satisfies F -- ordinary_second_
    # army() is never reached, proven by the stub being fully consumed.
    rng = _StubRandomWithIrand(irand_values=[0], random_values=[0.01, 0.5])
    result = humanoid_second_slot(Terrain.PLAINS, Race.HUMAN, 0, 0, tax=8, effective_sea_neighbors=4, rng=rng)
    assert result is ArmyType.FLEET


def test_humanoid_second_slot_b_passes_f_fails_falls_through_to_the_helper():
    # effective_sea_neighbors=0 -> fleet chance 0.0, F always fails
    # regardless of the ProvinceRandom draw's own value.
    rng = _StubRandomWithIrand(irand_values=[0], random_values=[0.01, 0.5, 0.01, 0.1])
    result = humanoid_second_slot(Terrain.FOREST, Race.HUMAN, 0, 0, tax=8, effective_sea_neighbors=0, rng=rng)
    assert result == ArmyType.LT_CAVALRY


def test_humanoid_second_slot_desert_skips_f_with_zero_draws_then_runs_the_helper():
    # fleet_second_slot_gate() returns False for Desert with zero draws
    # -- the helper's own draws start immediately after B's irand() call.
    rng = _StubRandomWithIrand(irand_values=[0], random_values=[0.01, 0.3, 0.1])
    result = humanoid_second_slot(Terrain.DESERT, Race.HUMAN, 0, 0, tax=8, effective_sea_neighbors=3, rng=rng)
    assert result == ArmyType.LT_CAVALRY
