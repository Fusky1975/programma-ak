from __future__ import annotations

import pytest

from ak_engine.models.army_type import ArmyType
from ak_engine.turn.battle_line import BattleUnit
from ak_engine.turn.duel import (
    Commander,
    apply_duel_demoralization,
    provincial_garrison_commander,
    select_supreme_commander,
)


def test_select_supreme_commander_picks_largest_contingent():
    candidates = [
        Commander(leader_id=1, contingent_size=3, tactical_ability=5),
        Commander(leader_id=2, contingent_size=7, tactical_ability=1),
    ]
    assert select_supreme_commander(candidates).leader_id == 2


def test_select_supreme_commander_breaks_ties_with_tactical_ability():
    candidates = [
        Commander(leader_id=1, contingent_size=5, tactical_ability=2),
        Commander(leader_id=2, contingent_size=5, tactical_ability=8),
    ]
    assert select_supreme_commander(candidates).leader_id == 2


def test_select_supreme_commander_empty_returns_none():
    assert select_supreme_commander([]) is None


def test_provincial_garrison_commander_has_no_abilities():
    commander = provincial_garrison_commander(contingent_size=4)
    assert commander.leader_id is None
    assert commander.tactical_ability == 0
    assert commander.contingent_size == 4


def test_apply_duel_demoralization_reduces_strength_25_percent():
    units = [BattleUnit(ArmyType.BOWMEN, 10), BattleUnit(ArmyType.AXEMEN, 20)]
    demoralized = apply_duel_demoralization(units)
    assert [u.effective_strength for u in demoralized] == pytest.approx([7.5, 15.0])
    # original list untouched
    assert units[0].effective_strength == 10
