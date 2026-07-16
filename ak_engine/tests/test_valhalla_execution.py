from __future__ import annotations

from ak_engine.models.alignment import Alignment
from ak_engine.models.game_state import GameState, KingdomState, LeaderState
from ak_engine.models.map import HexCoord
from ak_engine.models.race import Race
from ak_engine.models.valhalla import VALHALLA_ROSTER, VALHALLA_VISITOR_LEADER_ID
from ak_engine.turn.valhalla_execution import finalize_gate_angel_visit

from _helpers import ScriptedRandom

HOME = HexCoord(3, 9)
KING_LOCATION = HexCoord(5, 5)


def _state_with_winner(due_alignment=Alignment.GOOD, king_location=KING_LOCATION):
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.GOOD, HOME))
    state.add_leader(LeaderState(1, 1, "King Foo", king_location, is_king=True))
    state.last_gate_angel_turn = state.turn_number
    state.last_gate_angel_kingdom = 1
    state.gate_angel_due_alignment = due_alignment
    return state


def test_finalize_returns_none_when_no_gate_angel_succeeded_this_turn():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.GOOD, HOME))

    result = finalize_gate_angel_visit(state, ScriptedRandom([]))

    assert result is None
    assert VALHALLA_VISITOR_LEADER_ID not in state.leaders


def test_finalize_returns_none_when_the_win_is_from_a_previous_turn():
    state = _state_with_winner()
    state.turn_number = 5
    state.last_gate_angel_turn = 4  # stale -- not this turn's winner

    result = finalize_gate_angel_visit(state, ScriptedRandom([]))

    assert result is None


def test_finalize_spawns_a_leader_with_the_fixed_visitor_id():
    state = _state_with_winner()
    rng = ScriptedRandom([], choice_indices=[0])  # first GOOD hero: Basil

    visitor = finalize_gate_angel_visit(state, rng)

    assert visitor is not None
    assert visitor.leader_id == VALHALLA_VISITOR_LEADER_ID
    assert state.leaders[VALHALLA_VISITOR_LEADER_ID] is visitor
    assert visitor.kingdom_id == 1
    assert visitor.name == VALHALLA_ROSTER[Alignment.GOOD][0].name


def test_finalize_spawns_the_visitor_beside_the_king():
    state = _state_with_winner(king_location=KING_LOCATION)
    rng = ScriptedRandom([], choice_indices=[0])

    visitor = finalize_gate_angel_visit(state, rng)

    assert visitor.location == KING_LOCATION


def test_finalize_falls_back_to_home_province_when_no_king_is_on_record():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.GOOD, HOME))
    state.last_gate_angel_turn = state.turn_number
    state.last_gate_angel_kingdom = 1
    state.gate_angel_due_alignment = Alignment.GOOD
    rng = ScriptedRandom([], choice_indices=[0])

    visitor = finalize_gate_angel_visit(state, rng)

    assert visitor.location == HOME


def test_finalize_grants_the_visitors_fixed_item():
    state = _state_with_winner()
    rng = ScriptedRandom([], choice_indices=[0])  # Basil -> Treasure.WEAPON_2

    visitor = finalize_gate_angel_visit(state, rng)

    items = state.items_held_by(visitor.leader_id)
    assert len(items) == 1
    assert items[0].treasure == VALHALLA_ROSTER[Alignment.GOOD][0].fixed_item


def test_finalize_grants_no_item_when_the_heros_own_item_has_no_treasure_match():
    state = _state_with_winner(due_alignment=Alignment.PAGAN)
    assert VALHALLA_ROSTER[Alignment.PAGAN][9].name == "Gelenor"
    assert VALHALLA_ROSTER[Alignment.PAGAN][9].fixed_item is None
    rng = ScriptedRandom([], choice_indices=[9])

    visitor = finalize_gate_angel_visit(state, rng)

    assert state.items_held_by(visitor.leader_id) == []


def test_finalize_copies_the_heros_skills_temper_alignment_and_race():
    state = _state_with_winner()
    rng = ScriptedRandom([], choice_indices=[0])
    template = VALHALLA_ROSTER[Alignment.GOOD][0]

    visitor = finalize_gate_angel_visit(state, rng)

    assert visitor.skills is template.skills
    assert visitor.temper is template.temper
    assert visitor.alignment is template.true_alignment
    assert visitor.race is template.race
