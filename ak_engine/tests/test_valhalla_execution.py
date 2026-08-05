from __future__ import annotations

import random

from ak_engine.models.alignment import Alignment
from ak_engine.models.game_state import GameState, KingdomState, LeaderState
from ak_engine.models.kingdom import SkillTable
from ak_engine.models.map import HexCoord
from ak_engine.models.race import Race
from ak_engine.models.temper import Temper
from ak_engine.models.valhalla import VALHALLA_ROSTER, VALHALLA_VISITOR_LEADER_ID, ValhallaHero
from ak_engine.turn.valhalla_execution import _select_visitor_template, finalize_gate_angel_visit

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
    # GameState.turn_number defaults to 1 -- Phase 386: turns 1-5 always
    # pick the roster's own final record (Quintilian for GOOD), no rng consumed.
    state = _state_with_winner()
    rng = ScriptedRandom([])

    visitor = finalize_gate_angel_visit(state, rng)

    assert visitor is not None
    assert visitor.leader_id == VALHALLA_VISITOR_LEADER_ID
    assert state.leaders[VALHALLA_VISITOR_LEADER_ID] is visitor
    assert visitor.kingdom_id == 1
    assert visitor.name == VALHALLA_ROSTER[Alignment.GOOD][-1].name


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
    rng = ScriptedRandom([])  # turn 1: deterministic final-roster-record pick

    visitor = finalize_gate_angel_visit(state, rng)

    items = state.items_held_by(visitor.leader_id)
    assert len(items) == 1
    assert items[0].treasure == VALHALLA_ROSTER[Alignment.GOOD][-1].fixed_item


def test_finalize_grants_no_item_when_the_heros_own_item_is_unresolved(monkeypatch):
    # Phase 198 closed the last real gap in VALHALLA_ROSTER (Hannibal's
    # Grimoire -> BOOK_TACTICAL), so no real hero exercises the
    # fixed_item=None branch anymore -- this uses a fabricated hero to
    # keep that branch of finalize_gate_angel_visit under test.
    synthetic_hero = ValhallaHero(
        name="Nobody",
        true_alignment=Alignment.PAGAN,
        temper=Temper.CAUTIOUS,
        race=Race.HUMAN,
        skills=SkillTable(raw_values=[0] * 30),
        fixed_item=None,
        fixed_item_name="Unresolved Trinket",
    )
    monkeypatch.setattr(
        "ak_engine.turn.valhalla_execution.VALHALLA_ROSTER",
        {Alignment.PAGAN: (synthetic_hero,)},
    )
    state = _state_with_winner(due_alignment=Alignment.PAGAN)
    rng = ScriptedRandom([], choice_indices=[0])

    visitor = finalize_gate_angel_visit(state, rng)

    assert state.items_held_by(visitor.leader_id) == []


def test_finalize_copies_the_heros_skills_temper_alignment_and_race():
    state = _state_with_winner()
    rng = ScriptedRandom([])
    template = VALHALLA_ROSTER[Alignment.GOOD][-1]

    visitor = finalize_gate_angel_visit(state, rng)

    assert visitor.skills is template.skills
    assert visitor.temper is template.temper
    assert visitor.alignment is template.true_alignment
    assert visitor.race is template.race


# -- Phase 386: real visitor_selection (turns 1-5 deterministic, post-turn-5
# coprime-stride full permutation) --

_SMALL_ROSTER = tuple(
    ValhallaHero(
        name=name,
        true_alignment=Alignment.GOOD,
        temper=Temper.CAUTIOUS,
        race=Race.HUMAN,
        skills=SkillTable(raw_values=[0] * 30),
        fixed_item=None,
        fixed_item_name="x",
    )
    for name in ("A", "B", "C")
)


def test_select_visitor_template_uses_the_final_roster_record_for_turns_1_through_5():
    state = GameState()
    for turn in range(1, 6):
        state.turn_number = turn
        template = _select_visitor_template(state, Alignment.GOOD, VALHALLA_ROSTER[Alignment.GOOD], ScriptedRandom([]))
        assert template is VALHALLA_ROSTER[Alignment.GOOD][-1]


def test_select_visitor_template_cycles_through_the_full_roster_before_repeating():
    state = GameState()
    state.turn_number = 6
    rng = random.Random(42)

    picks = [_select_visitor_template(state, Alignment.GOOD, _SMALL_ROSTER, rng).name for _ in range(9)]

    assert set(picks[:3]) == {"A", "B", "C"}  # a full permutation before any repeat
    assert picks[3:6] == picks[0:3]  # the same coprime stride repeats the cycle identically
    assert picks[6:9] == picks[0:3]


def test_select_visitor_template_single_hero_roster_always_returns_it():
    state = GameState()
    state.turn_number = 6
    rng = random.Random(1)
    only = _SMALL_ROSTER[:1]

    for _ in range(5):
        assert _select_visitor_template(state, Alignment.GOOD, only, rng) is only[0]


def test_select_visitor_template_persists_its_sequence_state_on_gamestate():
    state = GameState()
    state.turn_number = 6
    rng = random.Random(7)

    _select_visitor_template(state, Alignment.GOOD, _SMALL_ROSTER, rng)

    assert Alignment.GOOD in state.valhalla_visitor_sequence
