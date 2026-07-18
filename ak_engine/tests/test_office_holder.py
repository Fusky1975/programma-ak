"""Tests for turn/office_holder.py -- see its module docstring for the
full derivation (Emperor's special-cased resolution vs. the other 7
offices' genuine Merit Point Rank contest).
"""

from __future__ import annotations

from ak_engine.models.alignment import Alignment
from ak_engine.models.game_state import GameState, KingdomState, LeaderState, ProvinceState
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.office import Office
from ak_engine.models.race import Race
from ak_engine.turn.office_holder import (
    ALL_OFFICES,
    RANKED_OFFICES,
    resolve_all_office_holders,
    resolve_office_holder,
)

HOME = HexCoord(0, 0)


def make_state() -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, HOME, treasury=10))
    state.add_kingdom(KingdomState(2, "Defendia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(1, 1), treasury=5))
    return state


def test_resolve_office_holder_emperor_reads_the_real_election_result():
    state = make_state()
    state.add_leader(LeaderState(1, 1, "Aldric", HOME, is_king=True))
    state.emperor_kingdom_id = 1
    state.add_province(ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, tax=8))

    holder = resolve_office_holder(state, Office.EMPEROR)

    assert holder is not None
    assert holder.leader_id == 1
    assert holder.merit_points == 8  # emperor_merit_points == Tax_Base


def test_resolve_office_holder_emperor_none_before_any_election():
    state = make_state()
    state.add_leader(LeaderState(1, 1, "Aldric", HOME, is_king=True))

    assert resolve_office_holder(state, Office.EMPEROR) is None


def test_resolve_office_holder_treasurer_picks_the_wealthier_king():
    state = make_state()
    state.add_leader(LeaderState(1, 1, "Aldric", HOME, is_king=True))
    state.add_leader(LeaderState(2, 2, "Borin", HexCoord(1, 1), is_king=True))

    holder = resolve_office_holder(state, Office.TREASURER)

    assert holder is not None
    assert holder.leader_id == 1  # Attackia's own treasury (10) beats Defendia's (5)
    assert holder.merit_points == 10


def test_resolve_office_holder_treasurer_ineligible_for_independent_hero():
    state = make_state()
    state.add_leader(LeaderState(9, None, "Wanderer", HOME))  # no kingdom, no treasury

    assert resolve_office_holder(state, Office.TREASURER) is None


def test_resolve_office_holder_hero_can_win_an_office():
    # Rulebook [10.1]: "Anche un Eroe può aggiudicarsi una carica."
    state = make_state()
    state.add_leader(LeaderState(1, 1, "Aldric", HOME, is_king=True))
    hero = LeaderState(50, 1, "Wandering Sage", HOME)
    hero.merit_tally.resurrection_bless_casts = 5
    state.add_leader(hero)

    holder = resolve_office_holder(state, Office.PRIEST)

    assert holder is not None
    assert holder.leader_id == 50
    assert holder.merit_points == 5


def test_resolve_office_holder_none_when_nobody_meets_the_minimum():
    state = make_state()
    state.add_leader(LeaderState(1, 1, "Aldric", HOME, is_king=True))  # 0 Merit Points everywhere

    assert resolve_office_holder(state, Office.MARSHAL) is None


def test_resolve_office_holder_tiebreak_uses_treasury_then_tax_base():
    state = make_state()
    a = LeaderState(1, 1, "Aldric", HOME, is_king=True)
    a.merit_tally.monster_hp_defeated = 10
    b = LeaderState(2, 2, "Borin", HexCoord(1, 1), is_king=True)
    b.merit_tally.monster_hp_defeated = 10
    state.add_leader(a)
    state.add_leader(b)

    holder = resolve_office_holder(state, Office.DEFENDER)

    # Tied at 10 points each -- kingdom 1's own treasury (10) beats kingdom 2's (5).
    assert holder is not None
    assert holder.leader_id == 1


def test_resolve_office_holder_raises_for_a_non_office():
    state = make_state()
    import pytest

    with pytest.raises(ValueError):
        resolve_office_holder(state, "not-an-office")  # type: ignore[arg-type]


def test_resolve_all_office_holders_covers_every_real_office():
    state = make_state()
    state.add_leader(LeaderState(1, 1, "Aldric", HOME, is_king=True))

    holders = resolve_all_office_holders(state)

    assert set(holders.keys()) == set(ALL_OFFICES)
    assert len(ALL_OFFICES) == 8
    assert len(RANKED_OFFICES) == 7
