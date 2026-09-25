from __future__ import annotations

import random

import pytest

from ak_engine.models.army_type import ArmyType
from ak_engine.turn.battle_line import BattleUnit
from ak_engine.turn.battle_luck import luck_strength_multiplier
from ak_engine.turn.battle_resolution import _apply_alignment_king_bonus, _apply_duellist_bonus, resolve_battle
from ak_engine.turn.combat import column_bres

from _helpers import ScriptedRandom


def unit(strength: float, army_type: ArmyType = ArmyType.BOWMEN, *, druidic_rear_targeting_blocked: bool = False) -> BattleUnit:
    return BattleUnit(
        army_type=army_type,
        effective_strength=strength,
        druidic_rear_targeting_blocked=druidic_rear_targeting_blocked,
    )


def _luck_draws(num_columns: int, *, g1: float = 0.5, g2: float = 0.5, local: float = 0.5) -> list[float]:
    """A whole-battle global draw pair plus one local draw pair per
    column (Phase 370's real, always-applied luck consumption order),
    followed by a 2-value safety pair (`0.1, 0.9`) appended at the end:
    if a scripted battle's own summed `BRES` nets to exactly zero,
    `break_bres_tie` needs a couple more draws, and `0.1, 0.9` guarantees
    an immediate mismatch (side1 heads, side2 tails) on its first round
    rather than running the scripted rng dry.
    """

    draws = [g1, g2]
    for _ in range(num_columns):
        draws.extend([local, local])
    draws.extend([0.1, 0.9])
    return draws


def test_resolve_battle_neutral_luck_matches_the_real_bres_formula():
    # All four luck draws at 0.0 -> r1 = r2 = 1 (identity multiplier, see
    # turn/battle_luck.py luck_strength_multiplier's own R_s = 1 +
    # k*(g+l) formula) -- what decides the column (and, with only one
    # column, the whole battle) is then column_bres's own deterministic
    # sign over the raw strength ratio.
    rng = ScriptedRandom([0.0, 0.0, 0.0, 0.0])

    result = resolve_battle([unit(20)], [unit(10)], rng=rng)

    expected_bres = column_bres(20, 10, 1.0, 1.0)
    assert expected_bres > 0  # attacker is twice as strong
    assert result.columns[0].attacker_strength == 20
    assert result.columns[0].defender_strength == 10
    assert result.columns[0].bres == expected_bres
    assert result.columns[0].attacker_won is True
    assert result.total_bres == expected_bres
    assert result.winner == "attacker"
    assert result.attacker_columns_won == 1
    assert result.defender_columns_won == 0


def test_resolve_battle_neutral_luck_favors_the_defender_when_the_ratio_is_reversed():
    rng = ScriptedRandom([0.0, 0.0, 0.0, 0.0])

    result = resolve_battle([unit(10)], [unit(20)], rng=rng)

    expected_bres = column_bres(10, 20, 1.0, 1.0)
    assert expected_bres < 0
    assert result.columns[0].bres == expected_bres
    assert result.columns[0].attacker_won is False
    assert result.winner == "defender"


# -- Phase 453: Druidic monster battle assistance column bonus --------------


def test_resolve_battle_attacker_column_bonus_adds_directly_to_that_columns_strength():
    rng = ScriptedRandom([0.0, 0.0, 0.0, 0.0])

    result = resolve_battle([unit(10)], [unit(10)], attacker_column_bonus={0: 15}, rng=rng)

    assert result.columns[0].attacker_strength == 25
    assert result.columns[0].defender_strength == 10
    assert result.winner == "attacker"


def test_resolve_battle_defender_column_bonus_adds_directly_to_that_columns_strength():
    rng = ScriptedRandom([0.0, 0.0, 0.0, 0.0])

    result = resolve_battle([unit(10)], [unit(10)], defender_column_bonus={0: 15}, rng=rng)

    assert result.columns[0].attacker_strength == 10
    assert result.columns[0].defender_strength == 25
    assert result.winner == "defender"


def test_resolve_battle_column_bonus_out_of_range_index_is_ignored():
    # Equal raw strength with no real bonus applied nets to a BRES tie,
    # needing break_bres_tie()'s own extra draws -- same 0.1/0.9 safety
    # pair convention as this module's own _luck_draws() helper.
    rng = ScriptedRandom([0.0, 0.0, 0.0, 0.0, 0.1, 0.9])

    result = resolve_battle([unit(10)], [unit(10)], attacker_column_bonus={5: 100}, rng=rng)

    assert result.columns[0].attacker_strength == 10


def test_resolve_battle_no_column_bonus_by_default():
    rng = ScriptedRandom([0.0, 0.0, 0.0, 0.0, 0.1, 0.9])

    result = resolve_battle([unit(10)], [unit(10)], rng=rng)

    assert result.columns[0].attacker_strength == 10
    assert result.columns[0].defender_strength == 10


def test_resolve_battle_global_luck_favors_a_side_when_raw_strength_is_equal():
    # g1=0.9 lifts R1 well above R2=1 (g2=l1=l2=0) -- enough to flip an
    # otherwise-tied 10-vs-10 raw strength column in the attacker's
    # favor via column_bres's own real formula, not a probability roll
    # (Phase 370 no longer has one).
    rng = ScriptedRandom([0.9, 0.0, 0.0, 0.0])

    result = resolve_battle([unit(10)], [unit(10)], rng=rng)

    r1 = luck_strength_multiplier(0.9, 0.0, is_first_turn=True)
    r2 = luck_strength_multiplier(0.0, 0.0, is_first_turn=True)
    expected_bres = column_bres(10, 10, r1, r2)
    assert expected_bres > 0
    assert result.columns[0].bres == expected_bres
    assert result.winner == "attacker"
    # The column's own *reported* strength stays the deterministic,
    # pre-luck value -- luck only feeds column_bres, it never mutates
    # attacker_strength/defender_strength (unlike the pre-Phase-370
    # model, which replaced the front-line BattleUnit outright).
    assert result.columns[0].attacker_strength == 10
    assert result.columns[0].defender_strength == 10


def test_resolve_battle_local_luck_is_drawn_fresh_per_column():
    # Two equal-raw-strength columns, neutral global luck (g1=g2=0) --
    # any difference between the two columns' own outcomes must come
    # from their own separate local draws.
    attacker_units = [unit(10), unit(10)]
    defender_units = [unit(10), unit(10)]
    # g1, g2, col1: l1=0.9/l2=0.0, col2: l1=0.0/l2=0.3
    rng = ScriptedRandom([0.0, 0.0, 0.9, 0.0, 0.0, 0.3])

    result = resolve_battle(attacker_units, defender_units, rng=rng)

    assert len(result.columns) == 2
    assert result.columns[0].bres == 1  # attacker's own local draw favored it
    assert result.columns[0].attacker_won is True
    assert result.columns[1].bres == 0  # defender's own local draw wasn't enough to flip an exact tie
    assert result.columns[1].attacker_won is False
    assert result.attacker_columns_won == 1
    assert result.defender_columns_won == 0
    assert result.total_bres == 1
    assert result.winner == "attacker"


def test_resolve_battle_rejects_empty_side():
    with pytest.raises(ValueError):
        resolve_battle([], [unit(10)], rng=random.Random(0))


def test_resolve_battle_structural_invariants_with_real_rng_multi_column():
    attacker = [unit(s) for s in [12, 10, 8, 6, 4]]
    defender = [unit(s) for s in [11, 9, 7, 5]]
    rng = random.Random(2026)

    result = resolve_battle(attacker, defender, rng=rng)

    line_length = min(len(attacker), len(defender))
    assert len(result.columns) == line_length
    # A per-column BRES of exactly 0 is a genuine tie -- it contributes to
    # neither side's own column count (Phase 370), so the two counts only
    # bound line_length from above, they don't have to sum to it.
    assert result.attacker_columns_won + result.defender_columns_won <= line_length
    assert result.total_bres == sum(column.bres for column in result.columns)
    if result.total_bres > 0:
        assert result.winner == "attacker"
    elif result.total_bres < 0:
        assert result.winner == "defender"
    else:
        # break_bres_tie always resolves an exact-zero sum to one side or
        # the other -- resolve_battle itself never reports "tie".
        assert result.winner in ("attacker", "defender")
    for column in result.columns:
        assert column.attacker_strength >= 0
        assert column.defender_strength >= 0


def test_resolve_battle_applies_nemesis_penalty_before_column_strength_is_reported():
    # Phalanx is Legion's nemesis-victim (see turn/battle_line.py's
    # apply_nemesis_penalties) -- the attacker's reported column strength
    # should already reflect the 2/3 penalty, before any luck is rolled.
    rng = ScriptedRandom(_luck_draws(1))

    result = resolve_battle([unit(10, ArmyType.PHALANX)], [unit(10, ArmyType.LEGION)], rng=rng)

    assert result.columns[0].attacker_strength == pytest.approx(10 * 2 / 3)
    assert result.columns[0].defender_strength == 10


def test_resolve_battle_runs_tactical_switches_before_nemesis_penalties_and_luck():
    # Same nemesis chain as test_battle_line.py's
    # test_apply_tactical_switches_defenders_decision_uses_the_attackers_post_switch_front:
    # both sides are nemesis-eligible to switch once ability lets them, and
    # the defender's switch only makes sense reading the attacker's
    # already-switched front. terrain_line_length_cap=1 forces both units
    # per side into one stacked column instead of two separate ones.
    attacker_units = [unit(10, ArmyType.PHALANX), unit(9, ArmyType.HVY_CAVALRY)]
    defender_units = [unit(10, ArmyType.LEGION), unit(9, ArmyType.BOWMEN)]
    # atk-switch-roll, def-switch-roll, then the real global+local luck draws.
    rng = ScriptedRandom([0.0, 0.0, *_luck_draws(1)])

    result = resolve_battle(
        attacker_units,
        defender_units,
        terrain_line_length_cap=1,
        attacker_tactical_ability=1,
        defender_tactical_ability=1,
        rng=rng,
    )

    column = result.columns[0]
    assert column.attacker_switched is True
    assert column.defender_switched is True
    assert [u.army_type for u in column.attacker_units] == [ArmyType.HVY_CAVALRY, ArmyType.PHALANX]
    assert [u.army_type for u in column.defender_units] == [ArmyType.BOWMEN, ArmyType.LEGION]
    # Post-switch, the defender's rearward Legion is nemesis-weak against
    # the attacker's new front (Heavy Cavalry) -- apply_nemesis_penalties
    # ran against the final lineup, not the original one.
    assert column.attacker_strength == pytest.approx(9 * 1.0 + 10 * 0.5)
    assert column.defender_strength == pytest.approx(9 * 1.0 + (10 * 2 / 3) * 0.5)


def test_resolve_battle_defaults_to_no_switching():
    # attacker_tactical_ability/defender_tactical_ability default to 0 --
    # switch_chance is 0, so even a nemesis-eligible column never swaps.
    attacker_units = [unit(10, ArmyType.PHALANX), unit(9, ArmyType.HVY_CAVALRY)]
    defender_units = [unit(10, ArmyType.LEGION)]
    rng = ScriptedRandom([0.0, *_luck_draws(1)])  # atk-switch-roll (consumed, fails), then real luck

    result = resolve_battle(attacker_units, defender_units, terrain_line_length_cap=1, rng=rng)

    assert result.columns[0].attacker_switched is False
    assert [u.army_type for u in result.columns[0].attacker_units] == [ArmyType.PHALANX, ArmyType.HVY_CAVALRY]


def test_resolve_battle_opposing_overflight_unit_boosts_second_line_to_full_strength():
    # Rulebook [7.2]: an overflight attacker "will attack the rear unit
    # instead (the non-human unit and the rearward unit will both be at
    # 100% strength in this case.)" -- the defender's own second-line
    # Axemen goes from 50% to 100% because the attacker's Whales unit is
    # present, regardless of column depth on either side. (Whales, not
    # Dragon/Eagle Wing or Mermen, to avoid an incidental nemesis
    # matchup against Bowmen muddying the numbers -- NEMESIS[Whales] is
    # Mermen, not Bowmen.)
    attacker_units = [unit(10, ArmyType.WHALES)]
    defender_units = [unit(10, ArmyType.BOWMEN), unit(9, ArmyType.AXEMEN)]
    rng = ScriptedRandom(_luck_draws(1))

    result = resolve_battle(attacker_units, defender_units, terrain_line_length_cap=1, rng=rng)

    assert result.columns[0].attacker_strength == pytest.approx(10)
    assert result.columns[0].defender_strength == pytest.approx(10 * 1.0 + 9 * 1.0)


def test_resolve_battle_druidic_blocked_overflight_unit_does_not_trigger_rear_targeting():
    # Phase 43: same setup as the boost test above, but the attacker's
    # Whales unit is held back (insufficient Druidic ability) -- the
    # defender's second-line Axemen stays at ordinary 50%, not boosted.
    attacker_units = [unit(10, ArmyType.WHALES, druidic_rear_targeting_blocked=True)]
    defender_units = [unit(10, ArmyType.BOWMEN), unit(9, ArmyType.AXEMEN)]
    rng = ScriptedRandom(_luck_draws(1))

    result = resolve_battle(attacker_units, defender_units, terrain_line_length_cap=1, rng=rng)

    # The blocked Whales unit also loses its own 100%-regardless-of-depth
    # treatment, but it's alone at depth 0 so that part reads the same
    # either way (100%) -- the defender side is where the difference shows.
    assert result.columns[0].attacker_strength == pytest.approx(10)
    assert result.columns[0].defender_strength == pytest.approx(10 * 1.0 + 9 * 0.5)


def test_resolve_battle_numeric_superiority_boosts_second_line_to_full_strength():
    # RULES.AK ~line 1362: "If a battle line is shorter than the terrain
    # allows, the flanking second-line units of a force which is superior
    # in numbers may outflank the enemy force... 100% strength instead of
    # 50%." Attacker has 4 units against defender's 2 -- line_length is
    # capped at 2 (the smaller side's count), strictly less than the
    # terrain_line_length_cap of 5, so the line is "shorter than the
    # terrain allows" and the attacker (numerically superior) is eligible.
    attacker_units = [unit(10), unit(10), unit(10), unit(10)]
    defender_units = [unit(10), unit(10)]
    # Phase 905: the attacker being outflank-eligible also makes each
    # column's own rearward unit an eligible nemesis-inflictor candidate
    # against the defender's lone front-line unit there -- two identical
    # BOWMEN candidates, ambiguous, one rng.choice per column (2 columns).
    # Neither candidate is ever a real nemesis match here, so the choice
    # is outcome-neutral -- this is purely about not starving the script.
    rng = ScriptedRandom(_luck_draws(2), choice_indices=[0, 0])

    result = resolve_battle(attacker_units, defender_units, terrain_line_length_cap=5, rng=rng)

    assert len(result.columns) == 2
    for column in result.columns:
        # Depth 0 (100%) + depth 1 boosted from 50% to 100%, instead of
        # the ordinary 10*1.0 + 10*0.5 = 15.
        assert column.attacker_strength == pytest.approx(20)
        assert column.defender_strength == pytest.approx(10)


def test_resolve_battle_outflanking_legion_inflicts_nemesis_on_the_opposing_front_line():
    # Phase 905, user-confirmed 2026-09-25 (superseding Phase 904's own
    # disassembly-based "not modeled" conclusion -- see turn/battle_
    # line.py apply_nemesis_penalties()'s own docstring for the full
    # history): a front-line Phalanx facing a front-line Bowmen whose own
    # second line is an outflanking Legion (numerically superior, terrain
    # permits a shorter line) DOES take the nemesis penalty from that
    # Legion, even though Bowmen itself isn't Phalanx's nemesis -- rule
    # 1/2 alone would find no eligible inflictor here at all.
    attacker_units = [unit(90, ArmyType.BOWMEN), unit(80, ArmyType.LEGION)]  # column 0: front + outflanking rear
    defender_units = [unit(50, ArmyType.PHALANX)]  # column 0: lone front line
    rng = ScriptedRandom(_luck_draws(1), choice_indices=[1])  # the outflanking Legion (index 1) is chosen

    result = resolve_battle(attacker_units, defender_units, terrain_line_length_cap=5, rng=rng)

    # Outflanking's own pre-existing strength effect still fires too
    # (90 + 80*1.0, not *0.5) -- the two mechanics are independent.
    assert result.columns[0].attacker_strength == pytest.approx(170)
    assert result.columns[0].defender_strength == pytest.approx(50 * 2 / 3)


def test_resolve_battle_outflanking_never_doubles_an_already_applied_nemesis_penalty():
    # Same worked example, second half: a front-line Legion already
    # penalizes an opposing Phalanx via rule 1 alone; a second Legion in
    # the same column's own second line, also outflanking-eligible, does
    # NOT double that penalty (50*2/3, never 50*(2/3)**2) -- exactly one
    # inflictor is ever chosen and checked per own-column unit, however
    # many candidates were eligible.
    attacker_units = [unit(90, ArmyType.LEGION), unit(80, ArmyType.LEGION)]  # column 0: front + outflanking rear
    defender_units = [unit(50, ArmyType.PHALANX)]
    rng = ScriptedRandom(_luck_draws(1), choice_indices=[0])  # either candidate is the identical type

    result = resolve_battle(attacker_units, defender_units, terrain_line_length_cap=5, rng=rng)

    assert result.columns[0].defender_strength == pytest.approx(50 * 2 / 3)


def test_resolve_battle_numeric_superiority_not_eligible_when_terrain_is_the_binding_cap():
    # Same 4-vs-2 imbalance, but terrain_line_length_cap=2 equals the
    # already-capped line_length -- the line is exactly as long as the
    # terrain allows, not shorter, so the outflanking boost doesn't apply.
    attacker_units = [unit(10), unit(10), unit(10), unit(10)]
    defender_units = [unit(10), unit(10)]
    rng = ScriptedRandom(_luck_draws(2))

    result = resolve_battle(attacker_units, defender_units, terrain_line_length_cap=2, rng=rng)

    for column in result.columns:
        assert column.attacker_strength == pytest.approx(10 * 1.0 + 10 * 0.5)


def test_resolve_battle_numeric_superiority_not_eligible_with_no_terrain_cap():
    # No terrain_line_length_cap at all (None, the default) means "shorter
    # than the terrain allows" is unanswerable, not assumed true -- see
    # this module's own docstring. The attacker stays at ordinary 50% on
    # its second line despite being numerically superior.
    attacker_units = [unit(10), unit(10), unit(10), unit(10)]
    defender_units = [unit(10), unit(10)]
    rng = ScriptedRandom(_luck_draws(2))

    result = resolve_battle(attacker_units, defender_units, rng=rng)

    for column in result.columns:
        assert column.attacker_strength == pytest.approx(10 * 1.0 + 10 * 0.5)


def test_resolve_battle_combined_arms_boosts_second_line_when_first_two_units_differ():
    # Phase 513: Tactical Combined Arms lets a column's first two units,
    # if different army types, both fight at 100% -- the same numeric
    # effect as numeric-superiority outflanking, gated on the ability
    # plus differing types instead of numeric superiority.
    attacker_units = [unit(10, ArmyType.BOWMEN), unit(10, ArmyType.LEGION)]
    defender_units = [unit(10)]
    rng = ScriptedRandom(_luck_draws(1))

    result = resolve_battle(attacker_units, defender_units, attacker_combined_arms=True, rng=rng)

    # Depth 0 (100%) + depth 1 boosted from 50% to 100%, instead of the
    # ordinary 10*1.0 + 10*0.5 = 15.
    assert result.columns[0].attacker_strength == pytest.approx(20)


def test_resolve_battle_combined_arms_has_no_effect_when_first_two_units_share_a_type():
    attacker_units = [unit(10, ArmyType.BOWMEN), unit(10, ArmyType.BOWMEN)]
    defender_units = [unit(10)]
    rng = ScriptedRandom(_luck_draws(1))

    result = resolve_battle(attacker_units, defender_units, attacker_combined_arms=True, rng=rng)

    assert result.columns[0].attacker_strength == pytest.approx(15)


def test_resolve_battle_combined_arms_requires_the_side_own_flag():
    attacker_units = [unit(10, ArmyType.BOWMEN), unit(10, ArmyType.LEGION)]
    defender_units = [unit(10)]
    rng = ScriptedRandom(_luck_draws(1))

    result = resolve_battle(attacker_units, defender_units, rng=rng)  # attacker_combined_arms defaults False

    assert result.columns[0].attacker_strength == pytest.approx(15)


def test_resolve_battle_column_results_expose_the_actual_units_for_bookkeeping():
    attacker = [BattleUnit(ArmyType.BOWMEN, 10, source_id=101)]
    defender = [BattleUnit(ArmyType.AXEMEN, 5, source_id=202)]

    result = resolve_battle(attacker, defender, rng=random.Random(0))

    assert [u.source_id for u in result.columns[0].attacker_units] == [101]
    assert [u.source_id for u in result.columns[0].defender_units] == [202]


# -- Phase 471: Duellist / "Captain of the Musketeers" front-line bonus -----


def test_apply_duellist_bonus_no_op_when_no_unit_is_eligible():
    columns = [[BattleUnit(ArmyType.BOWMEN, 10)], [BattleUnit(ArmyType.AXEMEN, 10)]]
    strengths = [10.0, 10.0]
    rng = ScriptedRandom([])  # any .choice() call here would raise IndexError

    _apply_duellist_bonus(columns, strengths, rng)

    assert strengths == [10.0, 10.0]


def test_apply_duellist_bonus_adds_the_selected_units_own_delta():
    columns = [
        [BattleUnit(ArmyType.BOWMEN, 10, duellist_bonus_if_selected=4.0)],
        [BattleUnit(ArmyType.AXEMEN, 10, duellist_bonus_if_selected=7.0)],
    ]
    strengths = [10.0, 10.0]
    rng = ScriptedRandom([], choice_indices=[1])  # picks the second eligible column (index 1)

    _apply_duellist_bonus(columns, strengths, rng)

    assert strengths == [10.0, 17.0]


def test_apply_duellist_bonus_only_considers_the_front_line_depth_0_unit():
    # Depth-1 (rear) unit's own field is irrelevant -- only the front-line
    # (depth 0) unit's eligibility and delta matter for this column.
    columns = [
        [
            BattleUnit(ArmyType.BOWMEN, 10, duellist_bonus_if_selected=None),
            BattleUnit(ArmyType.AXEMEN, 5, duellist_bonus_if_selected=99.0),
        ]
    ]
    strengths = [10.0]
    rng = ScriptedRandom([])  # no eligible front-line unit -> no choice() call

    _apply_duellist_bonus(columns, strengths, rng)

    assert strengths == [10.0]


def test_apply_duellist_bonus_selects_among_eligible_columns_only():
    columns = [
        [BattleUnit(ArmyType.BOWMEN, 10, duellist_bonus_if_selected=None)],
        [BattleUnit(ArmyType.AXEMEN, 10, duellist_bonus_if_selected=3.0)],
        [BattleUnit(ArmyType.PHALANX, 10, duellist_bonus_if_selected=5.0)],
    ]
    strengths = [10.0, 10.0, 10.0]
    # eligible_indices == [1, 2] -- choice_indices picks position 0 of that
    # filtered list, i.e. column 1, not column 0.
    rng = ScriptedRandom([], choice_indices=[0])

    _apply_duellist_bonus(columns, strengths, rng)

    assert strengths == [10.0, 13.0, 10.0]


def test_apply_duellist_bonus_zero_delta_is_a_valid_real_outcome():
    # An already-fanatical or already-Elite front-line unit has a real,
    # computed delta of exactly 0.0 -- still a valid selection outcome,
    # per SS17.7's own "a random front-line unit", not "the most
    # valuable eligible one."
    columns = [[BattleUnit(ArmyType.BOWMEN, 10, duellist_bonus_if_selected=0.0)]]
    strengths = [10.0]
    rng = ScriptedRandom([], choice_indices=[0])

    _apply_duellist_bonus(columns, strengths, rng)

    assert strengths == [10.0]


def test_resolve_battle_applies_the_duellist_bonus_to_the_chosen_front_line_column():
    attacker = [
        BattleUnit(ArmyType.BOWMEN, 10, duellist_bonus_if_selected=6.0),
        BattleUnit(ArmyType.AXEMEN, 10, duellist_bonus_if_selected=2.0),
    ]
    defender = [BattleUnit(ArmyType.PHALANX, 5), BattleUnit(ArmyType.PHALANX, 5)]
    # choice_indices: [attacker's own pick, defender's own pick] -- the
    # defender call finds zero eligible columns (every defender unit's
    # own field is None) and never consumes a choice_indices entry, so
    # only one entry is needed for the attacker's own call.
    rng = ScriptedRandom(_luck_draws(2), choice_indices=[1])

    result = resolve_battle(attacker, defender, rng=rng)

    assert result.columns[0].attacker_strength == 10
    assert result.columns[1].attacker_strength == 10 + 2.0


# -- Phase 661: the 7 alignment-King titles' own shared front-line bonus ----


def test_apply_alignment_king_bonus_no_op_when_no_unit_is_eligible():
    columns = [[BattleUnit(ArmyType.BOWMEN, 10)], [BattleUnit(ArmyType.AXEMEN, 10)]]
    strengths = [10.0, 10.0]
    rng = ScriptedRandom([])  # any .choice() call here would raise IndexError

    _apply_alignment_king_bonus(columns, strengths, rng)

    assert strengths == [10.0, 10.0]


def test_apply_alignment_king_bonus_adds_the_selected_units_own_delta():
    columns = [
        [BattleUnit(ArmyType.BOWMEN, 10, alignment_king_bonus_if_selected=4.0)],
        [BattleUnit(ArmyType.AXEMEN, 10, alignment_king_bonus_if_selected=7.0)],
    ]
    strengths = [10.0, 10.0]
    rng = ScriptedRandom([], choice_indices=[1])

    _apply_alignment_king_bonus(columns, strengths, rng)

    assert strengths == [10.0, 17.0]


def test_apply_alignment_king_bonus_is_independent_of_the_duellist_bonus():
    # A column eligible for both grants (a Supreme Commander holding both
    # Duellist and an alignment-King title) gets both, via two genuinely
    # separate rng.choice() calls -- see BattleUnit.alignment_king_bonus_
    # if_selected's own docstring for why the two aren't merged.
    columns = [[BattleUnit(ArmyType.BOWMEN, 10, duellist_bonus_if_selected=3.0, alignment_king_bonus_if_selected=5.0)]]
    strengths = [10.0]
    rng = ScriptedRandom([], choice_indices=[0, 0])

    _apply_duellist_bonus(columns, strengths, rng)
    _apply_alignment_king_bonus(columns, strengths, rng)

    assert strengths == [18.0]


def test_resolve_battle_applies_the_alignment_king_bonus_to_the_chosen_front_line_column():
    attacker = [
        BattleUnit(ArmyType.BOWMEN, 10, alignment_king_bonus_if_selected=6.0),
        BattleUnit(ArmyType.AXEMEN, 10, alignment_king_bonus_if_selected=2.0),
    ]
    defender = [BattleUnit(ArmyType.PHALANX, 5), BattleUnit(ArmyType.PHALANX, 5)]
    rng = ScriptedRandom(_luck_draws(2), choice_indices=[1])

    result = resolve_battle(attacker, defender, rng=rng)

    assert result.columns[0].attacker_strength == 10
    assert result.columns[1].attacker_strength == 10 + 2.0
