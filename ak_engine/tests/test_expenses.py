"""Tests for turn/expenses.py -- see its module docstring for the full
real-sample cross-check this exercises.
"""

from __future__ import annotations

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.game_state import ArmyState, GameState, KingdomState, LeaderState
from ak_engine.models.map import HexCoord
from ak_engine.models.race import Race
from ak_engine.models.temper import Temper
from ak_engine.models.valhalla import VALHALLA_VISITOR_LEADER_ID
from ak_engine.turn.combat import Quality
from ak_engine.turn.expenses import compute_army_maintenance, compute_expected_expenses, compute_leader_maintenance

HOME = HexCoord(3, 5)


def make_state() -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, HOME))
    state.add_kingdom(KingdomState(2, "Defendia", Race.HUMAN, Alignment.NEUTRAL, HOME))
    return state


# -- compute_army_maintenance --------------------------------------------


def test_compute_army_maintenance_sums_pay_across_owned_armies():
    state = make_state()
    state.add_army(ArmyState(1, 1, ArmyType.LEGION, Quality.AVERAGE, HOME))
    state.add_army(ArmyState(2, 1, ArmyType.LEGION, Quality.AVERAGE, HOME))
    state.add_army(ArmyState(3, 1, ArmyType.LT_CAVALRY, Quality.AVERAGE, HOME))

    # SE3__T0.K2 (real sample, 2026-07-29): 2x Legion + 1x Lt Cavalry = 6.
    assert compute_army_maintenance(state, 1) == 6


def test_compute_army_maintenance_ignores_mercenary_armies():
    state = make_state()
    state.add_army(ArmyState(1, 1, ArmyType.LEGION, Quality.AVERAGE, HOME))
    state.add_army(ArmyState(2, None, ArmyType.CAMEL_CORPS, Quality.AVERAGE, HOME))  # unowned mercenary

    assert compute_army_maintenance(state, 1) == 2


def test_compute_army_maintenance_ignores_other_kingdoms_armies():
    state = make_state()
    state.add_army(ArmyState(1, 1, ArmyType.LEGION, Quality.AVERAGE, HOME))
    state.add_army(ArmyState(2, 2, ArmyType.HVY_CAVALRY, Quality.AVERAGE, HOME))

    assert compute_army_maintenance(state, 1) == 2


def test_compute_army_maintenance_zero_with_no_armies():
    state = make_state()
    assert compute_army_maintenance(state, 1) == 0


# -- compute_leader_maintenance ------------------------------------------


def test_compute_leader_maintenance_king_contributes_zero():
    state = make_state()
    state.add_leader(LeaderState(1, 1, "King", HOME, is_king=True, alignment=Alignment.GOOD, temper=Temper.BRAVE))

    assert compute_leader_maintenance(state, 1) == 0


def test_compute_leader_maintenance_ordinary_hero_uses_required_pay():
    state = make_state()
    state.add_leader(LeaderState(1, 1, "King", HOME, is_king=True, alignment=Alignment.GOOD, temper=Temper.CAUTIOUS))
    state.add_leader(LeaderState(2, 1, "Adele", HOME, alignment=Alignment.GOOD, temper=Temper.BRAVE))

    # SE3__T1.K2 (real sample): Adele (Good/Brave) under a Good/Caut King,
    # alignment distance 0 -- required_pay() is 1 regardless of the temper
    # mismatch (no friction to amplify at distance 0).
    assert compute_leader_maintenance(state, 1) == 1


def test_compute_leader_maintenance_sums_multiple_heroes():
    state = make_state()
    state.add_leader(LeaderState(1, 1, "King", HOME, is_king=True, alignment=Alignment.GOOD, temper=Temper.CAUTIOUS))
    state.add_leader(LeaderState(2, 1, "Adele", HOME, alignment=Alignment.GOOD, temper=Temper.BRAVE))
    state.add_leader(LeaderState(3, 1, "Indra", HOME, alignment=Alignment.GOOD, temper=Temper.CAUTIOUS))

    # SE3__T1.K2 (real sample): Adele=1, Indra=1 -- total 2.
    assert compute_leader_maintenance(state, 1) == 2


def test_compute_leader_maintenance_valhalla_visitor_contributes_zero():
    state = make_state()
    state.add_leader(LeaderState(1, 1, "King", HOME, is_king=True, alignment=Alignment.NEUTRAL, temper=Temper.BRAVE))
    state.add_leader(
        LeaderState(
            VALHALLA_VISITOR_LEADER_ID, 1, "Kitralus", HOME, alignment=Alignment.NEUTRAL, temper=Temper.BRAVE
        )
    )

    # SE3__T0.K3 (real sample): Kitralus (the Valhalla visitor) prints 0
    # despite an alignment/temper match that would otherwise price non-zero.
    assert compute_leader_maintenance(state, 1) == 0


def test_compute_leader_maintenance_ignores_other_kingdoms_leaders():
    state = make_state()
    state.add_leader(LeaderState(1, 1, "King", HOME, is_king=True, alignment=Alignment.GOOD, temper=Temper.BRAVE))
    state.add_leader(LeaderState(2, 2, "Rival Hero", HOME, alignment=Alignment.GOOD, temper=Temper.BRAVE))

    assert compute_leader_maintenance(state, 1) == 0


# -- compute_expected_expenses -------------------------------------------


def test_compute_expected_expenses_matches_real_sample_file():
    # SE3__T1.K2 (real sample, 2026-07-29): King Bradipo I (Good/Cautious),
    # two Heroes (Adele Good/Brave, Indra Good/Caut, both distance 0 ->
    # 1 gold each), and six Hired armies -- 31st/33rd/225th Legion (2 each),
    # 32nd/226th Light Cavalry (2 each), 210th Camel Corps (3) -- summing
    # to 13. The file's own printed "Expected Expenses: 15" is exactly
    # 13 (armies) + 2 (leaders).
    state = make_state()
    state.add_leader(LeaderState(1, 1, "Bradipo I", HOME, is_king=True, alignment=Alignment.GOOD, temper=Temper.CAUTIOUS))
    state.add_leader(LeaderState(2, 1, "Adele", HOME, alignment=Alignment.GOOD, temper=Temper.BRAVE))
    state.add_leader(LeaderState(3, 1, "Indra", HOME, alignment=Alignment.GOOD, temper=Temper.CAUTIOUS))
    for army_id, army_type in enumerate(
        [
            ArmyType.LEGION,
            ArmyType.LEGION,
            ArmyType.LEGION,
            ArmyType.LT_CAVALRY,
            ArmyType.LT_CAVALRY,
            ArmyType.CAMEL_CORPS,
        ],
        start=1,
    ):
        state.add_army(ArmyState(army_id, 1, army_type, Quality.AVERAGE, HOME))

    assert compute_expected_expenses(state, 1) == 15
