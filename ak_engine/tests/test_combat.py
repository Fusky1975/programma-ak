from __future__ import annotations

import pytest

from ak_engine.models.army_type import ArmyType, is_nemesis_of
from ak_engine.turn.combat import (
    DEFENDER_BONUS,
    NEMESIS_PENALTY,
    QUALITY_NAME,
    Quality,
    apply_defender_bonus,
    apply_nemesis_penalty,
    column_bres,
    line_contribution,
    win_probability,
)


def test_quality_multipliers_match_rulebook():
    assert Quality.DEPLETED == 0
    assert Quality.GREEN == 1
    assert Quality.AVERAGE == 2
    assert Quality.VETERAN == 3
    assert Quality.CRACK == 4
    assert Quality.ELITE == 5


def test_quality_name_covers_every_enum_value():
    assert set(QUALITY_NAME.keys()) == set(Quality)


def test_quality_name_matches_prose_txt_examples_verbatim():
    # PROSE.TXT: "^Q (): Quality ('Average', 'Elite' etc.)"
    assert QUALITY_NAME[Quality.AVERAGE] == "Average"
    assert QUALITY_NAME[Quality.ELITE] == "Elite"


def test_quality_name_remaining_verbatim_values():
    assert QUALITY_NAME[Quality.DEPLETED] == "Depleted"
    assert QUALITY_NAME[Quality.GREEN] == "Green"
    assert QUALITY_NAME[Quality.VETERAN] == "Veteran"
    assert QUALITY_NAME[Quality.CRACK] == "Crack"


def test_line_contribution_halves_per_depth():
    assert line_contribution(0) == 1.0
    assert line_contribution(1) == 0.5
    assert line_contribution(2) == 0.25
    assert line_contribution(3) == 0.125


def test_line_contribution_rejects_negative_depth():
    with pytest.raises(ValueError):
        line_contribution(-1)


def test_defender_bonus_is_25_percent():
    assert apply_defender_bonus(100) == pytest.approx(125)
    assert DEFENDER_BONUS == 1.25


def test_nemesis_matchup_from_rulebook_table():
    assert is_nemesis_of(ArmyType.PHALANX, ArmyType.LEGION)
    assert is_nemesis_of(ArmyType.LEGION, ArmyType.HVY_CAVALRY)
    assert is_nemesis_of(ArmyType.DRAGON_WING, ArmyType.BOWMEN)
    assert not is_nemesis_of(ArmyType.BOWMEN, ArmyType.DRAGON_WING)  # not symmetric
    assert not is_nemesis_of(ArmyType.PHALANX, ArmyType.BOWMEN)


def test_nemesis_penalty_applies_two_thirds():
    result = apply_nemesis_penalty(90, ArmyType.PHALANX, ArmyType.LEGION)
    assert result == pytest.approx(90 * NEMESIS_PENALTY)
    assert result == pytest.approx(60)


def test_nemesis_penalty_not_applied_to_non_nemesis():
    assert apply_nemesis_penalty(90, ArmyType.PHALANX, ArmyType.BOWMEN) == 90


def test_win_probability_matches_rulebook_even_odds_anchor():
    assert win_probability(1.0) == pytest.approx(0.5)


def test_win_probability_increases_with_ratio():
    assert win_probability(4.0) > win_probability(1.0)
    assert win_probability(0.25) < win_probability(1.0)


def test_win_probability_rejects_negative_ratio():
    with pytest.raises(ValueError):
        win_probability(-1)


# -- Phase 347: column_bres() -- the real AK.EXE/AK.OVR column score -----


def test_column_bres_is_zero_for_an_equal_fight_with_no_luck():
    assert column_bres(100.0, 100.0, r1=1.0, r2=1.0) == 0


def test_column_bres_matches_the_confirmed_4_to_1_worked_example():
    # Source: r1=r2=1 (no luck), r=4 -> BRES = round(1*2 - 1/2) = 2.
    assert column_bres(400.0, 100.0, r1=1.0, r2=1.0) == 2
    # r=1/4 (side 2 four times stronger) is the mirror image.
    assert column_bres(100.0, 400.0, r1=1.0, r2=1.0) == -2


def test_column_bres_clamps_to_the_documented_minus5_5_range():
    assert column_bres(1_000_000.0, 1.0, r1=4.0, r2=0.1) == 5
    assert column_bres(1.0, 1_000_000.0, r1=0.1, r2=4.0) == -5


def test_column_bres_luck_multipliers_can_swing_an_otherwise_even_fight():
    # An equal deterministic fight (r=1) is decided purely by the two
    # sides' own luck multipliers once they differ.
    assert column_bres(100.0, 100.0, r1=2.0, r2=1.0) > 0
    assert column_bres(100.0, 100.0, r1=1.0, r2=2.0) < 0


def test_column_bres_zero_strength_edge_cases():
    assert column_bres(0.0, 100.0, r1=1.0, r2=1.0) == -5
    assert column_bres(100.0, 0.0, r1=1.0, r2=1.0) == 5
    assert column_bres(0.0, 0.0, r1=1.0, r2=1.0) == 0
