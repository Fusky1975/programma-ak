"""Tests for webapp/diplomacy_orders.py -- Phase 1027, the GM-facing
Treat/Break Treat order submission that closes the gap `turn/
diplomacy.py`/`GameState.treat_permissions`'s own docstrings flagged:
nothing in production ever populated these fields before this module."""

from __future__ import annotations

import pytest

from ak_engine.models.alignment import Alignment
from ak_engine.models.game_state import GameState, KingdomState
from ak_engine.models.map import HexCoord
from ak_engine.models.race import Race
from ak_engine.webapp.diplomacy_orders import InvalidDiplomacyOrderError, set_turn_diplomacy_orders


def _state_with_kingdoms(*kingdom_ids: int) -> GameState:
    state = GameState()
    for kingdom_id in kingdom_ids:
        state.add_kingdom(
            KingdomState(kingdom_id, f"K{kingdom_id}", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0))
        )
    return state


def test_set_turn_diplomacy_orders_populates_both_fields():
    state = _state_with_kingdoms(1, 2, 3)

    set_turn_diplomacy_orders(state, treat_pairs={(1, 2), (2, 1)}, break_pairs={(3, 1)})

    assert state.treat_permissions == {(1, 2), (2, 1)}
    assert state.break_treat_orders == {(3, 1)}


def test_set_turn_diplomacy_orders_replaces_rather_than_merges():
    state = _state_with_kingdoms(1, 2)
    state.treat_permissions = {(1, 2)}
    state.break_treat_orders = {(2, 1)}

    set_turn_diplomacy_orders(state, treat_pairs=set(), break_pairs=set())

    assert state.treat_permissions == set()
    assert state.break_treat_orders == set()


def test_set_turn_diplomacy_orders_rejects_a_self_pair():
    state = _state_with_kingdoms(1, 2)

    with pytest.raises(InvalidDiplomacyOrderError):
        set_turn_diplomacy_orders(state, treat_pairs={(1, 1)}, break_pairs=set())


def test_set_turn_diplomacy_orders_rejects_an_unknown_kingdom():
    state = _state_with_kingdoms(1, 2)

    with pytest.raises(InvalidDiplomacyOrderError):
        set_turn_diplomacy_orders(state, treat_pairs=set(), break_pairs={(1, 99)})


def test_set_turn_diplomacy_orders_leaves_state_untouched_on_a_rejected_call():
    state = _state_with_kingdoms(1, 2)
    state.treat_permissions = {(1, 2)}

    with pytest.raises(InvalidDiplomacyOrderError):
        set_turn_diplomacy_orders(state, treat_pairs={(1, 99)}, break_pairs=set())

    assert state.treat_permissions == {(1, 2)}
