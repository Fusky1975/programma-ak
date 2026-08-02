from __future__ import annotations

from ak_engine.models.army_type import ArmyType, MONSTROUS_ARMY_RACE
from ak_engine.models.race import Race
from ak_engine.turn.combat import Quality
from ak_engine.worldgen.initial_armies import (
    BEST_ATYPE,
    COMMANDER_NONE,
    INITIAL_ARMY_QUALITY,
    KING_HOME_BUDGET,
    MAX_ARMIES_PER_PROVINCE_PASS,
    NATIVE_ARMY_TYPE,
    build_initial_armies,
    draw_r4,
    flying_or_special_budget,
    home_first_slot,
    ordinary_humanoid_budget,
    resolve_commander,
    second_slot_gate,
    second_slot_gate_probability,
    special_race_recruit_slot,
    whale_budget,
)
from ak_engine.worldgen.pascal_random import PascalRandom


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


def test_native_army_type_covers_every_race_the_source_names_except_vampires():
    named_races = {
        Race.DRAGONS,
        Race.EAGLES,
        Race.WHALES,
        Race.MERMISH,
        Race.ENTISH,
        Race.TROLLISH,
        Race.WEREFOLK,
    }
    assert named_races <= set(NATIVE_ARMY_TYPE)
    assert Race.VAMPISH not in NATIVE_ARMY_TYPE


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


def test_draw_r4_stays_within_1_to_4():
    rng = PascalRandom(seed=2)
    for _ in range(3000):
        assert 1 <= draw_r4(rng) <= 4


def test_ordinary_humanoid_budget_stays_within_documented_range():
    rng = PascalRandom(seed=3)
    for tax in range(0, 11):
        for _ in range(500):
            budget = ordinary_humanoid_budget(tax, rng)
            assert 1 <= budget <= 1 + int(0.9 * tax) + 1


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
