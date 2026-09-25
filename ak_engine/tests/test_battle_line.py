from __future__ import annotations

import random

import pytest

from ak_engine.models.army_type import ArmyType
from ak_engine.models.map import Terrain
from ak_engine.turn.battle_line import (
    TERRAIN_LINE_LENGTH_RANGE,
    BattleUnit,
    apply_nemesis_penalties,
    apply_tactical_switches,
    assign_battle_lines,
    column_has_overflight_unit,
    column_strength,
    line_length_for_battle,
    maybe_switch_front_line,
    roll_terrain_line_length_cap,
    switch_chance,
)

from _helpers import ScriptedRandom


def unit(
    army_type: ArmyType,
    strength: float,
    *,
    druidic_rear_targeting_blocked: bool = False,
    has_druidic_horse_control: bool = False,
    led_by_insufficient_druid: bool = False,
    is_humanoid_race: bool = False,
    duellist_bonus_if_selected: float | None = None,
    alignment_king_bonus_if_selected: float | None = None,
) -> BattleUnit:
    return BattleUnit(
        army_type=army_type,
        effective_strength=strength,
        druidic_rear_targeting_blocked=druidic_rear_targeting_blocked,
        has_druidic_horse_control=has_druidic_horse_control,
        led_by_insufficient_druid=led_by_insufficient_druid,
        is_humanoid_race=is_humanoid_race,
        duellist_bonus_if_selected=duellist_bonus_if_selected,
        alignment_king_bonus_if_selected=alignment_king_bonus_if_selected,
    )


def test_line_length_is_capped_by_smaller_force():
    assert line_length_for_battle(5, 3) == 3
    assert line_length_for_battle(2, 7) == 2


def test_line_length_respects_terrain_cap_when_given():
    assert line_length_for_battle(10, 10, terrain_line_length_cap=4) == 4


def test_line_length_ignores_terrain_cap_when_not_given():
    assert line_length_for_battle(10, 10) == 10


def test_assign_battle_lines_fills_front_line_across_columns_first():
    units = [unit(ArmyType.BOWMEN, s) for s in [7, 6, 5, 4, 3, 2, 1]]
    columns = assign_battle_lines(units, line_length=3)

    assert len(columns) == 3
    # Front line: units[0..2] go one per column.
    assert [c[0].effective_strength for c in columns] == [7, 6, 5]
    # Second line: units[3..5] go one per column.
    assert [c[1].effective_strength for c in columns] == [4, 3, 2]
    # Third line: only column 0 gets the leftover unit.
    assert columns[0][2].effective_strength == 1
    assert len(columns[1]) == 2
    assert len(columns[2]) == 2


def test_assign_battle_lines_rejects_non_positive_line_length():
    with pytest.raises(ValueError):
        assign_battle_lines([unit(ArmyType.BOWMEN, 1)], line_length=0)


def test_column_strength_halves_per_depth_for_ordinary_units():
    column = [unit(ArmyType.BOWMEN, 10), unit(ArmyType.AXEMEN, 10), unit(ArmyType.PHALANX, 10)]
    assert column_strength(column) == pytest.approx(10 * 1.0 + 10 * 0.5 + 10 * 0.25)


def test_column_strength_gives_overflight_units_full_strength_regardless_of_depth():
    column = [unit(ArmyType.BOWMEN, 10), unit(ArmyType.DRAGON_WING, 10)]
    # Dragon Wing is at depth 1 but is an overflight unit -> 100%, not 50%.
    assert column_strength(column) == pytest.approx(10 * 1.0 + 10 * 1.0)


def test_column_strength_halves_stacked_overflight_units_within_the_same_group():
    column = [unit(ArmyType.DRAGON_WING, 10), unit(ArmyType.EAGLE_WING, 10)]
    # Both are 'air' group -> first at 100%, second (same group) at 50%.
    assert column_strength(column) == pytest.approx(10 * 1.0 + 10 * 0.5)


def test_column_strength_keeps_air_and_sea_overflight_groups_independent():
    column = [unit(ArmyType.DRAGON_WING, 10), unit(ArmyType.WHALES, 10)]
    # Different groups (air vs sea) -> both count as the "first" in their group.
    assert column_strength(column) == pytest.approx(10 * 1.0 + 10 * 1.0)


def test_column_strength_outflank_boosts_second_line_to_full_strength():
    column = [unit(ArmyType.BOWMEN, 10), unit(ArmyType.AXEMEN, 10)]
    normal = column_strength(column)
    outflanked = column_strength(column, outflank_second_line=True)
    assert normal == pytest.approx(10 * 1.0 + 10 * 0.5)
    assert outflanked == pytest.approx(10 * 1.0 + 10 * 1.0)


def test_column_has_overflight_unit_detects_at_any_depth():
    assert column_has_overflight_unit([unit(ArmyType.BOWMEN, 10), unit(ArmyType.DRAGON_WING, 5)]) is True
    assert column_has_overflight_unit([unit(ArmyType.DRAGON_WING, 5), unit(ArmyType.BOWMEN, 10)]) is True
    assert column_has_overflight_unit([unit(ArmyType.BOWMEN, 10), unit(ArmyType.AXEMEN, 5)]) is False
    assert column_has_overflight_unit([]) is False


def test_column_strength_held_back_overflight_unit_gets_ordinary_depth_halving():
    # Phase 43, rulebook [4.32]/[7.2]: "held back... throws its low
    # strength into the attack on the front-line unit" -- a blocked
    # overflight unit at depth 1 is treated as an ordinary unit (50%),
    # not the unconditional overflight 100%.
    column = [
        unit(ArmyType.BOWMEN, 10),
        unit(ArmyType.DRAGON_WING, 10, druidic_rear_targeting_blocked=True),
    ]
    assert column_strength(column) == pytest.approx(10 * 1.0 + 10 * 0.5)


def test_column_strength_held_back_overflight_unit_does_not_join_the_overflight_stack():
    # A blocked overflight unit doesn't consume/share the overflight
    # group's stacking count with a genuinely eligible overflight unit.
    column = [
        unit(ArmyType.DRAGON_WING, 10, druidic_rear_targeting_blocked=True),
        unit(ArmyType.EAGLE_WING, 10),
    ]
    # Blocked Dragon Wing (depth 0) -> ordinary depth-0 = 100% anyway;
    # Eagle Wing (depth 1, air group) -> first *eligible* air unit -> 100%,
    # not the 50% it would get if it were counted as the group's second.
    assert column_strength(column) == pytest.approx(10 * 1.0 + 10 * 1.0)


def test_column_strength_unblocked_overflight_unit_still_gets_full_strength():
    column = [unit(ArmyType.BOWMEN, 10), unit(ArmyType.DRAGON_WING, 10, druidic_rear_targeting_blocked=False)]
    assert column_strength(column) == pytest.approx(10 * 1.0 + 10 * 1.0)


def test_column_has_overflight_unit_ignores_held_back_units():
    blocked_only = [unit(ArmyType.BOWMEN, 10), unit(ArmyType.DRAGON_WING, 5, druidic_rear_targeting_blocked=True)]
    assert column_has_overflight_unit(blocked_only) is False

    mixed = [
        unit(ArmyType.DRAGON_WING, 5, druidic_rear_targeting_blocked=True),
        unit(ArmyType.WHALES, 5),
    ]
    assert column_has_overflight_unit(mixed) is True


def test_switch_chance_matches_formula():
    assert switch_chance(tactical_ability=2, line_length=4) == pytest.approx(0.5)


def test_switch_chance_clamped_to_one():
    assert switch_chance(tactical_ability=10, line_length=2) == 1.0


def test_switch_chance_rejects_bad_inputs():
    with pytest.raises(ValueError):
        switch_chance(tactical_ability=1, line_length=0)
    with pytest.raises(ValueError):
        switch_chance(tactical_ability=-1, line_length=1)


def test_roll_terrain_line_length_cap_within_documented_range():
    rng = random.Random(1)
    for terrain, (low, high) in TERRAIN_LINE_LENGTH_RANGE.items():
        for _ in range(50):
            assert low <= roll_terrain_line_length_cap(terrain, rng) <= high


def test_roll_terrain_line_length_cap_none_for_no_terrain():
    assert roll_terrain_line_length_cap(Terrain.NO_TERRAIN, random.Random(0)) is None


def test_maybe_switch_front_line_swaps_when_rear_is_stronger_and_roll_succeeds():
    column = [unit(ArmyType.BOWMEN, 5), unit(ArmyType.AXEMEN, 20)]
    rng = random.Random()
    rng.random = lambda: 0.0  # forces the switch-chance check to succeed

    switched = maybe_switch_front_line(column, line_length=1, tactical_ability=1, rng=rng)

    assert switched is True
    assert column[0].effective_strength == 20
    assert column[1].effective_strength == 5


def test_maybe_switch_front_line_no_switch_when_front_already_strongest():
    column = [unit(ArmyType.BOWMEN, 20), unit(ArmyType.AXEMEN, 5)]
    rng = random.Random()
    rng.random = lambda: 0.0

    switched = maybe_switch_front_line(column, line_length=1, tactical_ability=1, rng=rng)

    assert switched is False
    assert column[0].effective_strength == 20


def test_maybe_switch_front_line_no_switch_when_roll_fails():
    column = [unit(ArmyType.BOWMEN, 5), unit(ArmyType.AXEMEN, 20)]
    rng = random.Random()
    rng.random = lambda: 0.99  # switch chance (1/1=1.0) still triggers unless roll >= chance

    switched = maybe_switch_front_line(column, line_length=1, tactical_ability=0, rng=rng)

    assert switched is False


def test_maybe_switch_front_line_single_unit_column_never_switches():
    column = [unit(ArmyType.BOWMEN, 5)]
    assert maybe_switch_front_line(column, line_length=1, tactical_ability=5, rng=random.Random(0)) is False


def test_apply_nemesis_penalties_reduces_the_weak_sides_front_line_only():
    # Phalanx is Legion's nemesis-victim (NEMESIS[Phalanx] == {Legion}), but
    # not the reverse (NEMESIS[Legion] == {Heavy Cavalry}) -- an asymmetric
    # pair, so only the Phalanx side should be penalized here.
    attacker_columns = [[unit(ArmyType.PHALANX, 10)]]
    defender_columns = [[unit(ArmyType.LEGION, 10)]]

    apply_nemesis_penalties(attacker_columns, defender_columns)

    assert attacker_columns[0][0].effective_strength == pytest.approx(10 * 2 / 3)
    assert defender_columns[0][0].effective_strength == 10


def test_apply_nemesis_penalties_checks_rearward_units_against_the_opposing_front_line():
    # The rearward Phalanx (depth 1) has no same-depth defender counterpart
    # at all (defender's column is a single unit) -- it's still checked
    # against the opposing column's front-line (depth 0) type, per this
    # function's documented pairing rule.
    attacker_columns = [[unit(ArmyType.LEGION, 10), unit(ArmyType.PHALANX, 5)]]
    defender_columns = [[unit(ArmyType.LEGION, 8)]]

    apply_nemesis_penalties(attacker_columns, defender_columns)

    assert attacker_columns[0][0].effective_strength == 10  # Legion vs Legion: no nemesis relation
    assert attacker_columns[0][1].effective_strength == pytest.approx(5 * 2 / 3)
    assert defender_columns[0][0].effective_strength == 8


def test_apply_nemesis_penalties_no_effect_for_unrelated_types():
    attacker_columns = [[unit(ArmyType.BOWMEN, 10)]]
    defender_columns = [[unit(ArmyType.GARRISON, 10)]]

    apply_nemesis_penalties(attacker_columns, defender_columns)

    assert attacker_columns[0][0].effective_strength == 10
    assert defender_columns[0][0].effective_strength == 10


# -- Phase 696: AdvancedAbility.DRUIDIC_HORSE_CONTROL --------------------


def test_apply_nemesis_penalties_horse_control_exempts_cavalry_from_beasts():
    attacker_columns = [[unit(ArmyType.LT_CAVALRY, 9, has_druidic_horse_control=True)]]
    defender_columns = [[unit(ArmyType.ELEPHANTS, 9)]]  # a real Beast

    apply_nemesis_penalties(attacker_columns, defender_columns)

    assert attacker_columns[0][0].effective_strength == 9  # no penalty


def test_apply_nemesis_penalties_horse_control_does_not_exempt_chariots():
    # Chariots stays a real nemesis for cavalry regardless of the
    # ability -- the sourced text names "Beasts" specifically.
    attacker_columns = [[unit(ArmyType.LT_CAVALRY, 9, has_druidic_horse_control=True)]]
    defender_columns = [[unit(ArmyType.CHARIOTS, 9)]]

    apply_nemesis_penalties(attacker_columns, defender_columns)

    assert attacker_columns[0][0].effective_strength == pytest.approx(9 * 2 / 3)


def test_apply_nemesis_penalties_heavy_cavalry_horse_control_also_exempted():
    attacker_columns = [[unit(ArmyType.HVY_CAVALRY, 9, has_druidic_horse_control=True)]]
    defender_columns = [[unit(ArmyType.DINOSAURS, 9)]]  # also a Beast (Phase 691)

    apply_nemesis_penalties(attacker_columns, defender_columns)

    assert attacker_columns[0][0].effective_strength == 9


def test_apply_nemesis_penalties_beasts_penalty_still_applies_without_horse_control():
    # Non-regression: an otherwise-identical cavalry unit without the
    # ability still takes the ordinary Beasts penalty.
    attacker_columns = [[unit(ArmyType.LT_CAVALRY, 9)]]
    defender_columns = [[unit(ArmyType.ELEPHANTS, 9)]]

    apply_nemesis_penalties(attacker_columns, defender_columns)

    assert attacker_columns[0][0].effective_strength == pytest.approx(9 * 2 / 3)


def test_apply_nemesis_penalties_preserves_the_druidic_rear_targeting_blocked_flag():
    # Regression (Phase 43): a nemesis-penalized unit gets replaced with a
    # new BattleUnit at reduced strength -- the held-back flag must
    # survive that replacement, or resolve_battle's later
    # column_has_overflight_unit check would see it reset to False.
    attacker_columns = [[unit(ArmyType.DRAGON_WING, 10, druidic_rear_targeting_blocked=True)]]
    defender_columns = [[unit(ArmyType.BOWMEN, 10)]]  # Dragon Wing's nemesis

    apply_nemesis_penalties(attacker_columns, defender_columns)

    penalized = attacker_columns[0][0]
    assert penalized.effective_strength == pytest.approx(10 * 2 / 3)
    assert penalized.druidic_rear_targeting_blocked is True


def test_apply_nemesis_penalties_preserves_is_humanoid_race():
    # Regression: a nemesis-penalized unit's own is_humanoid_race must
    # survive the replacement, or turn/battle_orchestrator.py's own
    # Werebeast-bite check (which reads BattleResult.columns' post-
    # nemesis units directly) would wrongly treat a genuinely humanoid
    # front-line unit as non-humanoid once it's nemesis-penalized.
    attacker_columns = [[unit(ArmyType.PHALANX, 10, is_humanoid_race=True)]]
    defender_columns = [[unit(ArmyType.LEGION, 10)]]

    apply_nemesis_penalties(attacker_columns, defender_columns)

    penalized = attacker_columns[0][0]
    assert penalized.effective_strength == pytest.approx(10 * 2 / 3)
    assert penalized.is_humanoid_race is True


def test_apply_nemesis_penalties_preserves_led_by_insufficient_druid():
    # Regression: turn/aftermath.py roll_quality_change()'s own
    # insufficient-Druidic-ability improve-chance penalty ([7.5]) reads
    # this flag; it must not reset to False just because the same unit
    # was also nemesis-penalized.
    attacker_columns = [[unit(ArmyType.PHALANX, 10, led_by_insufficient_druid=True)]]
    defender_columns = [[unit(ArmyType.LEGION, 10)]]

    apply_nemesis_penalties(attacker_columns, defender_columns)

    penalized = attacker_columns[0][0]
    assert penalized.effective_strength == pytest.approx(10 * 2 / 3)
    assert penalized.led_by_insufficient_druid is True


def test_apply_nemesis_penalties_preserves_duellist_bonus_if_selected():
    # Regression: turn/battle_resolution.py _apply_duellist_bonus() runs
    # *after* apply_nemesis_penalties and reads column[0]'s own
    # duellist_bonus_if_selected directly -- a nemesis-penalized front-
    # line unit on a Duellist-eligible side must not silently lose its
    # eligibility for the random fanatic-unit bonus.
    attacker_columns = [[unit(ArmyType.PHALANX, 10, duellist_bonus_if_selected=3.5)]]
    defender_columns = [[unit(ArmyType.LEGION, 10)]]

    apply_nemesis_penalties(attacker_columns, defender_columns)

    penalized = attacker_columns[0][0]
    assert penalized.effective_strength == pytest.approx(10 * 2 / 3)
    assert penalized.duellist_bonus_if_selected == 3.5


def test_apply_nemesis_penalties_preserves_alignment_king_bonus_if_selected():
    # Regression: the sibling check to the Duellist one above, for the 7
    # alignment-King titles' own identical "random front-line unit
    # becomes fanatic" bonus (turn/battle_resolution.py _apply_
    # alignment_king_bonus()).
    attacker_columns = [[unit(ArmyType.PHALANX, 10, alignment_king_bonus_if_selected=2.0)]]
    defender_columns = [[unit(ArmyType.LEGION, 10)]]

    apply_nemesis_penalties(attacker_columns, defender_columns)

    penalized = attacker_columns[0][0]
    assert penalized.effective_strength == pytest.approx(10 * 2 / 3)
    assert penalized.alignment_king_bonus_if_selected == 2.0


def test_apply_nemesis_penalties_ignores_an_empty_opposing_column():
    attacker_columns = [[unit(ArmyType.PHALANX, 10)]]
    defender_columns = [[]]

    apply_nemesis_penalties(attacker_columns, defender_columns)  # must not raise

    assert attacker_columns[0][0].effective_strength == 10


def test_apply_nemesis_penalties_overflight_rear_unit_widens_eligibility_but_not_for_the_front_line():
    # RULES.AK: "a unit is a nemesis to its opponent if it's on the front
    # line or it's an air unit flying against a unit behind the front
    # line." NEMESIS[ENTS] = {AXEMEN, DRAGON_WING} -- Ents are vulnerable
    # to Dragon Wing. Garrison isn't Ents' nemesis, so the front-line
    # Ents stays unpenalized (deterministic -- no rng draw needed at
    # all: its only eligible candidate is the opposing front line). The
    # rearward Dragon Wing IS Ents' nemesis and is an overflight type, so
    # it becomes an *additional* eligible candidate against the
    # attacker's own rearward Ents -- ambiguous (2 candidates), resolved
    # via rng.choice ("chosen at random"). Picking index 1 (Dragon Wing)
    # here triggers the penalty.
    attacker_columns = [[unit(ArmyType.ENTS, 10), unit(ArmyType.ENTS, 8)]]
    defender_columns = [[unit(ArmyType.GARRISON, 5), unit(ArmyType.DRAGON_WING, 6)]]
    rng = ScriptedRandom([], choice_indices=[1])

    apply_nemesis_penalties(attacker_columns, defender_columns, rng)

    assert attacker_columns[0][0].effective_strength == 10  # front line: unaffected, no ambiguity
    assert attacker_columns[0][1].effective_strength == pytest.approx(8 * 2 / 3)  # rear: penalized


def test_apply_nemesis_penalties_random_choice_can_land_on_the_non_overflight_candidate():
    # Same setup as above, but rng.choice picks index 0 (the non-nemesis
    # Garrison front line) instead -- proving this is a genuine random
    # pick among eligible candidates, not "overflight always wins".
    attacker_columns = [[unit(ArmyType.ENTS, 10), unit(ArmyType.ENTS, 8)]]
    defender_columns = [[unit(ArmyType.GARRISON, 5), unit(ArmyType.DRAGON_WING, 6)]]
    rng = ScriptedRandom([], choice_indices=[0])

    apply_nemesis_penalties(attacker_columns, defender_columns, rng)

    assert attacker_columns[0][1].effective_strength == 8  # rear: unaffected this time


def test_apply_nemesis_penalties_druidic_blocked_overflight_unit_does_not_widen_eligibility():
    # Phase 43's held-back carve-out applies here too: a Dragon Wing whose
    # controller lacks sufficient Druidic ability isn't "flying" at all
    # (_is_effective_overflight is False for it), so it never becomes an
    # eligible nemesis-inflictor against the rear Ents -- back to the
    # single-candidate (front-line-only) case, no rng draw consumed.
    attacker_columns = [[unit(ArmyType.ENTS, 10), unit(ArmyType.ENTS, 8)]]
    defender_columns = [
        [unit(ArmyType.GARRISON, 5), unit(ArmyType.DRAGON_WING, 6, druidic_rear_targeting_blocked=True)]
    ]
    rng = ScriptedRandom([], choice_indices=[])  # must not be consumed

    apply_nemesis_penalties(attacker_columns, defender_columns, rng)

    assert attacker_columns[0][1].effective_strength == 8


# -- Phase 905: outflanking widens nemesis eligibility (user-confirmed) --


def test_apply_nemesis_penalties_outflank_eligible_rear_unit_penalizes_the_opposing_front_line():
    # User-confirmed 2026-09-25: a front-line Bowmen isn't Phalanx's
    # nemesis, but its own outflanking second-line Legion is eligible
    # against the opposing front line too (unlike overflight, not
    # restricted to own_depth >= 1) -- the Phalanx gets penalized.
    attacker_columns = [[unit(ArmyType.PHALANX, 10)]]
    defender_columns = [[unit(ArmyType.BOWMEN, 9), unit(ArmyType.LEGION, 8)]]
    rng = ScriptedRandom([], choice_indices=[1])

    apply_nemesis_penalties(attacker_columns, defender_columns, rng, defender_outflank_eligible=True)

    assert attacker_columns[0][0].effective_strength == pytest.approx(10 * 2 / 3)


def test_apply_nemesis_penalties_outflank_eligible_flag_off_keeps_old_behavior():
    # Same lineup, but the outflank-eligibility flag defaults to False --
    # the rearward Legion never becomes a candidate, so the front-line
    # Bowmen (not Phalanx's nemesis) is the sole, unambiguous candidate
    # and no rng draw is consumed at all. Backward compatibility for
    # every pre-Phase-905 caller.
    attacker_columns = [[unit(ArmyType.PHALANX, 10)]]
    defender_columns = [[unit(ArmyType.BOWMEN, 9), unit(ArmyType.LEGION, 8)]]
    rng = ScriptedRandom([], choice_indices=[])  # must not be consumed

    apply_nemesis_penalties(attacker_columns, defender_columns, rng)

    assert attacker_columns[0][0].effective_strength == 10


def test_apply_nemesis_penalties_outflank_eligibility_never_doubles_an_existing_penalty():
    # A front-line Legion already penalizes the opposing Phalanx (rule 1
    # alone); a second, outflanking Legion in the same column's own
    # second line does not double it -- exactly one inflictor is chosen
    # and checked, whatever the candidate count.
    attacker_columns = [[unit(ArmyType.PHALANX, 10)]]
    defender_columns = [[unit(ArmyType.LEGION, 9), unit(ArmyType.LEGION, 8)]]
    rng = ScriptedRandom([], choice_indices=[0])

    apply_nemesis_penalties(attacker_columns, defender_columns, rng, defender_outflank_eligible=True)

    assert attacker_columns[0][0].effective_strength == pytest.approx(10 * 2 / 3)  # not (2/3)**2


def test_apply_nemesis_penalties_outflank_eligible_but_no_second_line_unit_is_a_no_op():
    # defender_outflank_eligible=True with a single-unit column (no index
    # 1 to speak of) must not raise or otherwise misbehave.
    attacker_columns = [[unit(ArmyType.PHALANX, 10)]]
    defender_columns = [[unit(ArmyType.BOWMEN, 9)]]
    rng = ScriptedRandom([], choice_indices=[])  # must not be consumed -- still unambiguous

    apply_nemesis_penalties(attacker_columns, defender_columns, rng, defender_outflank_eligible=True)

    assert attacker_columns[0][0].effective_strength == 10


def test_apply_tactical_switches_swaps_the_nemesis_weak_attacker_front_line():
    # Front is Phalanx(10) vs a Legion-fronted defender -- nemesis-adjusted
    # to 6.67, which the raw-9 Heavy Cavalry rear now beats, so the switch
    # is eligible; ability=1 with line_length=1 makes switch_chance 1.0.
    attacker_columns = [[unit(ArmyType.PHALANX, 10), unit(ArmyType.HVY_CAVALRY, 9)]]
    defender_columns = [[unit(ArmyType.LEGION, 10)]]
    rng = ScriptedRandom([0.0])  # attacker's roll succeeds; defender column has <2 units, no roll

    attacker_switched, defender_switched = apply_tactical_switches(
        attacker_columns, defender_columns, line_length=1, attacker_tactical_ability=1, defender_tactical_ability=1, rng=rng
    )

    assert attacker_switched == [True]
    assert defender_switched == [False]
    assert [u.army_type for u in attacker_columns[0]] == [ArmyType.HVY_CAVALRY, ArmyType.PHALANX]
    # Raw effective_strength is untouched -- apply_tactical_switches only
    # reorders; the persistent nemesis discount is apply_nemesis_penalties'
    # job, run separately (see turn/battle_resolution.py resolve_battle).
    assert [u.effective_strength for u in attacker_columns[0]] == [9, 10]


def test_apply_tactical_switches_no_swap_when_ability_is_zero_despite_nemesis_eligibility():
    # Same nemesis-eligible setup as above, but ability=0 -> switch_chance
    # is 0, so the roll (still consumed) always fails the ">=" check.
    attacker_columns = [[unit(ArmyType.PHALANX, 10), unit(ArmyType.HVY_CAVALRY, 9)]]
    defender_columns = [[unit(ArmyType.LEGION, 10)]]
    rng = ScriptedRandom([0.0])  # consumed, but switch_chance(0, 1) == 0 so 0.0 >= 0.0 is True -> no switch

    attacker_switched, _ = apply_tactical_switches(
        attacker_columns, defender_columns, line_length=1, attacker_tactical_ability=0, defender_tactical_ability=0, rng=rng
    )

    assert attacker_switched == [False]
    assert [u.army_type for u in attacker_columns[0]] == [ArmyType.PHALANX, ArmyType.HVY_CAVALRY]


def test_apply_tactical_switches_defenders_decision_uses_the_attackers_post_switch_front():
    # Defender's front (Legion) is safe against the attacker's ORIGINAL
    # front (Phalanx) -- NEMESIS[Legion] == {Heavy Cavalry}, not Phalanx --
    # but becomes nemesis-weak once the attacker switches its own front to
    # Heavy Cavalry. If the defender's decision used the attacker's
    # pre-switch front, it would never swap; this proves it uses the
    # post-switch (current) front instead, per "the defender always gets
    # the last chance to switch."
    attacker_columns = [[unit(ArmyType.PHALANX, 10), unit(ArmyType.HVY_CAVALRY, 9)]]
    defender_columns = [[unit(ArmyType.LEGION, 10), unit(ArmyType.BOWMEN, 9)]]
    rng = ScriptedRandom([0.0, 0.0])  # attacker's roll, then defender's roll

    attacker_switched, defender_switched = apply_tactical_switches(
        attacker_columns, defender_columns, line_length=1, attacker_tactical_ability=1, defender_tactical_ability=1, rng=rng
    )

    assert attacker_switched == [True]
    assert defender_switched == [True]
    assert attacker_columns[0][0].army_type == ArmyType.HVY_CAVALRY
    assert defender_columns[0][0].army_type == ArmyType.BOWMEN
