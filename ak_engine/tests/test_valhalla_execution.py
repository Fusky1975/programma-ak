from __future__ import annotations

import random

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.game_state import ArmyState, GameState, KingdomState, LeaderState, ProvinceState
from ak_engine.models.kingdom import SkillTable
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.race import Race
from ak_engine.models.temper import Temper
from ak_engine.models.treasure import Treasure
from ak_engine.models.valhalla import VALHALLA_ROSTER, VALHALLA_VISITOR_LEADER_ID, ValhallaHero
from ak_engine.turn.combat import Quality
from ak_engine.turn.cast_execution import GATE_ANGEL_ELIGIBLE_ALIGNMENTS
from ak_engine.turn.valhalla_execution import (
    VALHALLA_VISIT_ANNOUNCEMENT_TEMPLATE,
    VALHALLA_VISITOR_RULES_TEMPLATE,
    VALHALLA_VISITOR_RULES_UNREACHABLE_DEADLINE_LINE,
    _select_visitor_template,
    finalize_gate_angel_visit,
    finalize_ordinary_valhalla_visit,
    process_valhalla_departure,
    select_ordinary_valhalla_recipient,
    select_valhalla_fallback_recipient,
)

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


# -- Phase 546: visitor lifecycle -- spawn-time field population --


def test_finalize_sets_the_active_turn_to_the_turn_after_this_one():
    # finalize_gate_angel_visit() runs in run_turn()'s own end-of-turn
    # tail, after this turn's own phase-dispatch loop already ran -- the
    # visitor genuinely can't act until turn_number + 1.
    state = _state_with_winner()
    state.turn_number = 7
    state.last_gate_angel_turn = 7
    rng = random.Random(0)  # turn > 5 -- real visitor_selection consumes rng

    visitor = finalize_gate_angel_visit(state, rng)

    assert visitor.valhalla_active_turn == 8


def test_finalize_sets_the_allowed_phase_count_from_the_active_turn():
    # Active turn 8 falls in the "turni 7-8" band -- 4 phases allowed.
    state = _state_with_winner()
    state.turn_number = 7
    state.last_gate_angel_turn = 7
    rng = random.Random(0)  # turn > 5 -- real visitor_selection consumes rng

    visitor = finalize_gate_angel_visit(state, rng)

    assert visitor.valhalla_allowed_phase_count == 4


def test_finalize_tracks_the_fixed_items_own_item_id():
    state = _state_with_winner()
    rng = ScriptedRandom([])

    visitor = finalize_gate_angel_visit(state, rng)

    items = state.items_held_by(visitor.leader_id)
    assert len(items) == 1
    assert visitor.valhalla_fixed_item_id == items[0].item_id


def test_finalize_leaves_the_fixed_item_id_unset_when_the_heros_item_is_unresolved(monkeypatch):
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

    assert visitor.valhalla_fixed_item_id is None


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


# -- Phase 548: visitor departure --


def test_process_valhalla_departure_hands_off_armies_to_the_king():
    state = GameState()
    state.add_leader(LeaderState(1, 1, "King Foo", HOME, is_king=True))
    state.add_leader(LeaderState(VALHALLA_VISITOR_LEADER_ID, 1, "Visitor", HOME, valhalla_active_turn=1))
    state.add_army(ArmyState(9, 1, ArmyType.BOWMEN, Quality.AVERAGE, HOME, commanded_by=VALHALLA_VISITOR_LEADER_ID))

    process_valhalla_departure(state)

    assert state.armies[9].commanded_by == 1
    assert VALHALLA_VISITOR_LEADER_ID not in state.leaders


def test_process_valhalla_departure_hands_off_to_lowest_id_colocated_leader_without_a_king():
    state = GameState()
    state.add_leader(LeaderState(VALHALLA_VISITOR_LEADER_ID, 1, "Visitor", HOME, valhalla_active_turn=1))
    state.add_leader(LeaderState(7, 1, "Later Hero", HOME))
    state.add_leader(LeaderState(4, 1, "Earlier Hero", HOME))
    state.add_army(ArmyState(9, 1, ArmyType.BOWMEN, Quality.AVERAGE, HOME, commanded_by=VALHALLA_VISITOR_LEADER_ID))

    process_valhalla_departure(state)

    assert state.armies[9].commanded_by == 4


def test_process_valhalla_departure_never_hands_off_to_a_co_located_foreign_leader():
    # Regression: "your lowest-numbered leader in the same province" (rule
    # 5) must be scoped to the visitor's own host Kingdom -- a co-located
    # leader of a DIFFERENT Kingdom (e.g. sharing the province during an
    # active encounter) must never inherit command. Previously the
    # co-located branch had no Kingdom filter at all, unlike the King
    # branch and the adjacent-province branch right next to it.
    state = GameState()
    state.add_leader(LeaderState(VALHALLA_VISITOR_LEADER_ID, 1, "Visitor", HOME, valhalla_active_turn=1))
    state.add_leader(LeaderState(2, 2, "Enemy Hero", HOME))
    state.add_army(ArmyState(9, 1, ArmyType.BOWMEN, Quality.AVERAGE, HOME, commanded_by=VALHALLA_VISITOR_LEADER_ID))

    process_valhalla_departure(state)

    assert state.armies[9].commanded_by is None
    assert state.armies[9].kingdom_id is None


def test_process_valhalla_departure_prefers_a_same_kingdom_leader_over_a_lower_id_foreign_one():
    state = GameState()
    state.add_leader(LeaderState(VALHALLA_VISITOR_LEADER_ID, 1, "Visitor", HOME, valhalla_active_turn=1))
    state.add_leader(LeaderState(2, 2, "Enemy Hero", HOME))  # lower id, foreign Kingdom
    state.add_leader(LeaderState(7, 1, "Own Hero", HOME))  # higher id, same Kingdom as the visitor
    state.add_army(ArmyState(9, 1, ArmyType.BOWMEN, Quality.AVERAGE, HOME, commanded_by=VALHALLA_VISITOR_LEADER_ID))

    process_valhalla_departure(state)

    assert state.armies[9].commanded_by == 7


def test_process_valhalla_departure_hands_off_to_an_adjacent_owned_province_leader_as_last_resort():
    adjacent = HexCoord(4, 9)  # adjacent to HOME (3, 9) on the odd-r grid
    state = GameState()
    state.add_province(ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_province(ProvinceState(adjacent, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_leader(LeaderState(VALHALLA_VISITOR_LEADER_ID, 1, "Visitor", HOME, valhalla_active_turn=1))
    state.add_leader(LeaderState(5, 1, "Neighbor", adjacent))
    state.add_army(ArmyState(9, 1, ArmyType.BOWMEN, Quality.AVERAGE, HOME, commanded_by=VALHALLA_VISITOR_LEADER_ID))

    process_valhalla_departure(state)

    assert state.armies[9].commanded_by == 5


def test_process_valhalla_departure_disbands_the_army_when_nobody_is_available():
    state = GameState()
    state.add_leader(LeaderState(VALHALLA_VISITOR_LEADER_ID, 1, "Visitor", HOME, valhalla_active_turn=1))
    state.add_army(ArmyState(9, 1, ArmyType.BOWMEN, Quality.AVERAGE, HOME, commanded_by=VALHALLA_VISITOR_LEADER_ID))

    process_valhalla_departure(state)

    assert state.armies[9].commanded_by is None
    assert state.armies[9].kingdom_id is None


def test_process_valhalla_departure_transfers_held_items_to_the_king():
    state = GameState()
    state.add_leader(LeaderState(1, 1, "King Foo", HOME, is_king=True))
    state.add_leader(LeaderState(VALHALLA_VISITOR_LEADER_ID, 1, "Visitor", HOME, valhalla_active_turn=1))
    fixed = state.add_item(Treasure.LEADERSHIP_HUMAN, VALHALLA_VISITOR_LEADER_ID)
    looted = state.add_item(Treasure.WAND_FIREBALL, VALHALLA_VISITOR_LEADER_ID)

    process_valhalla_departure(state)

    assert state.items[fixed.item_id].owner_leader_id == 1
    assert state.items[looted.item_id].owner_leader_id == 1
    assert VALHALLA_VISITOR_LEADER_ID not in state.leaders


def test_process_valhalla_departure_drops_the_fixed_item_on_death():
    state = GameState()
    state.add_leader(
        LeaderState(VALHALLA_VISITOR_LEADER_ID, 1, "Visitor", HOME, valhalla_active_turn=1, valhalla_fixed_item_id=None)
    )
    fixed = state.add_item(Treasure.LEADERSHIP_HUMAN, VALHALLA_VISITOR_LEADER_ID)
    state.leaders[VALHALLA_VISITOR_LEADER_ID].valhalla_fixed_item_id = fixed.item_id
    state.remove_leader(VALHALLA_VISITOR_LEADER_ID)  # "killed" -- archived into dead_leaders

    process_valhalla_departure(state)

    assert fixed.item_id not in state.items


def test_process_valhalla_departure_is_a_noop_outside_the_active_turn():
    state = GameState()
    state.turn_number = 5
    state.add_leader(LeaderState(1, 1, "King Foo", HOME, is_king=True))
    state.add_leader(LeaderState(VALHALLA_VISITOR_LEADER_ID, 1, "Visitor", HOME, valhalla_active_turn=6))
    item = state.add_item(Treasure.LEADERSHIP_HUMAN, VALHALLA_VISITOR_LEADER_ID)

    process_valhalla_departure(state)

    assert VALHALLA_VISITOR_LEADER_ID in state.leaders
    assert state.items[item.item_id].owner_leader_id == VALHALLA_VISITOR_LEADER_ID


def test_finalize_processes_a_stale_occupants_departure_before_overwriting():
    # Phase 548 bug fix: a second successful Gate Angel cast, while a
    # prior visitor is still present and exactly at their own scheduled
    # active turn, must not silently clobber leader 199.
    state = _state_with_winner()
    state.add_leader(LeaderState(1, 1, "King Foo", KING_LOCATION, is_king=True))
    state.add_leader(
        LeaderState(VALHALLA_VISITOR_LEADER_ID, 1, "Stale Visitor", KING_LOCATION, valhalla_active_turn=state.turn_number)
    )
    stale_item = state.add_item(Treasure.WAND_FIREBALL, VALHALLA_VISITOR_LEADER_ID)
    rng = ScriptedRandom([])

    new_visitor = finalize_gate_angel_visit(state, rng)

    assert new_visitor is not None
    assert new_visitor.name != "Stale Visitor"
    assert state.items[stale_item.item_id].owner_leader_id == 1  # handed off to the King, not lost


# -- Phase 585: VALHALLA_VISIT_ANNOUNCEMENT_TEMPLATE --


def test_valhalla_visit_announcement_template_has_the_real_markers():
    assert "<" in VALHALLA_VISIT_ANNOUNCEMENT_TEMPLATE
    assert "=" in VALHALLA_VISIT_ANNOUNCEMENT_TEMPLATE
    assert "#" in VALHALLA_VISIT_ANNOUNCEMENT_TEMPLATE


def test_valhalla_visit_announcement_template_verbatim():
    assert VALHALLA_VISIT_ANNOUNCEMENT_TEMPLATE == (
        '< was visited by a hero from Valhalla, named =!The characteristics '
        'for this great King from Game # are given in your "CHARACTERS" report.'
    )


def test_valhalla_visit_announcement_template_carries_no_real_historical_names():
    # Deliberately redacted -- see module docstring's own Phase 585
    # addendum. Real names ("Santa", "SWK", "Balin") and game numbers
    # never appear here, only the reusable marker skeleton.
    assert "Game #" in VALHALLA_VISIT_ANNOUNCEMENT_TEMPLATE
    assert not any(char.isdigit() for char in VALHALLA_VISIT_ANNOUNCEMENT_TEMPLATE)


# -- Phase 606: VALHALLA_VISITOR_RULES_TEMPLATE --


def test_valhalla_visitor_rules_template_has_nine_real_reachable_lines():
    # VALINT.X2's own header declares "1 9" -- the file's real 10th line
    # is a confirmed, never-printed anomaly, kept separately below.
    assert len(VALHALLA_VISITOR_RULES_TEMPLATE) == 9


def test_valhalla_visitor_rules_template_first_and_last_lines_verbatim():
    assert VALHALLA_VISITOR_RULES_TEMPLATE[0] == (
        "If [1 searches a feature, any monetary treasure [1 captures will be given to you."
    )
    assert VALHALLA_VISITOR_RULES_TEMPLATE[-1] == "If no leader is available, the armies will be disbanded."


def test_valhalla_visitor_rules_unreachable_deadline_line_is_kept_but_separate():
    # Real content, but the original engine's own 9-line header limit
    # means it was never actually printed -- see this module's own
    # pre-existing "Turn-deadline voiding stays confirmed out of scope"
    # note for the independent confirmation.
    assert VALHALLA_VISITOR_RULES_UNREACHABLE_DEADLINE_LINE == (
        "If you miss the turn deadline, [1 will disappear and your orders for [ will be voided."
    )
    assert VALHALLA_VISITOR_RULES_UNREACHABLE_DEADLINE_LINE not in VALHALLA_VISITOR_RULES_TEMPLATE


# -- Phase 756: the ordinary, per-turn automatic Valhalla visit --------------


def test_valhalla_visit_count_and_last_visited_kingdom_default_correctly():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.GOOD, HOME))
    assert state.kingdoms[1].valhalla_visit_count == 0
    assert state.last_valhalla_visited_kingdom_id is None


def _kingdom_only_state(*kingdoms):
    state = GameState()
    for kingdom_id, alignment in kingdoms:
        state.add_kingdom(KingdomState(kingdom_id, f"K{kingdom_id}", Race.HUMAN, alignment, HexCoord(kingdom_id, kingdom_id)))
    return state


def test_finalize_gate_angel_visit_also_records_last_visited_and_visit_count():
    state = _state_with_winner()
    rng = ScriptedRandom([])

    visitor = finalize_gate_angel_visit(state, rng)

    assert visitor is not None
    assert state.last_valhalla_visited_kingdom_id == 1
    assert state.kingdoms[1].valhalla_visit_count == 1


def test_select_ordinary_valhalla_recipient_prefers_the_king_with_fewer_visits():
    # The 1024-point-band property: a lower visit_count always wins,
    # regardless of its own drawn roll, as long as the higher-visit-count
    # King's own roll can't close a 1024-point gap.
    state = _kingdom_only_state((1, Alignment.GOOD), (2, Alignment.GOOD))
    state.kingdoms[2].valhalla_visit_count = 1
    # Kingdom 1's own roll (scripted low) still beats kingdom 2's (scripted
    # near-max), since kingdom 2 starts 1024 points behind.
    rng = ScriptedRandom([0.0, 0.999])

    winner = select_ordinary_valhalla_recipient(state, Alignment.GOOD, rng)

    assert winner == 1


def test_select_ordinary_valhalla_recipient_breaks_an_exact_tie_toward_the_lower_id():
    state = _kingdom_only_state((1, Alignment.GOOD), (2, Alignment.GOOD))
    # Same visit_count (0) and the same scripted roll for both -> a real tie.
    rng = ScriptedRandom([0.5, 0.5])

    winner = select_ordinary_valhalla_recipient(state, Alignment.GOOD, rng)

    assert winner == 1


def test_select_ordinary_valhalla_recipient_excludes_the_previous_visits_recipient():
    state = _kingdom_only_state((1, Alignment.GOOD), (2, Alignment.GOOD))
    state.last_valhalla_visited_kingdom_id = 1
    # Only kingdom 2 is a real candidate; its own roll is the only draw.
    rng = ScriptedRandom([0.1])

    winner = select_ordinary_valhalla_recipient(state, Alignment.GOOD, rng)

    assert winner == 2


def test_select_ordinary_valhalla_recipient_returns_none_with_no_real_candidate():
    # No Kingdom of this alignment at all.
    state = _kingdom_only_state((1, Alignment.EVIL))
    assert select_ordinary_valhalla_recipient(state, Alignment.GOOD, ScriptedRandom([])) is None

    # The only Kingdom of this alignment is the excluded previous recipient.
    state2 = _kingdom_only_state((1, Alignment.GOOD))
    state2.last_valhalla_visited_kingdom_id = 1
    assert select_ordinary_valhalla_recipient(state2, Alignment.GOOD, ScriptedRandom([])) is None


def test_select_valhalla_fallback_recipient_never_picks_divine_or_undead():
    state = _kingdom_only_state((1, Alignment.DIVINE), (2, Alignment.UNDEAD), (3, Alignment.EVIL))
    for _ in range(20):
        assert select_valhalla_fallback_recipient(state, random.Random()) == 3


def test_select_valhalla_fallback_recipient_is_uniform_among_eligible_kingdoms():
    state = _kingdom_only_state((1, Alignment.GOOD), (2, Alignment.EVIL))
    # index 0 -> kingdom 1, index 1 -> kingdom 2 (sorted candidate order).
    assert select_valhalla_fallback_recipient(state, ScriptedRandom([0.0])) == 1
    assert select_valhalla_fallback_recipient(state, ScriptedRandom([0.99])) == 2


def test_select_valhalla_fallback_recipient_returns_none_with_no_eligible_kingdom():
    state = _kingdom_only_state((1, Alignment.DIVINE))
    assert select_valhalla_fallback_recipient(state, ScriptedRandom([])) is None


def test_finalize_ordinary_valhalla_visit_returns_none_when_gate_angel_already_visited():
    state = _state_with_winner()

    result = finalize_ordinary_valhalla_visit(state, ScriptedRandom([]))

    assert result is None


def test_finalize_ordinary_valhalla_visit_spawns_a_real_visitor_with_no_gate_angel_cast():
    state = _kingdom_only_state((1, Alignment.GOOD))
    state.add_leader(LeaderState(1, 1, "King Foo", KING_LOCATION, is_king=True))
    # [0] -> GOOD is due this turn (GATE_ANGEL_ELIGIBLE_ALIGNMENTS[0]).
    # Turn 1 (the GameState default) -> _select_visitor_template() needs
    # no further draw (turns 1-5 always pick the roster's own last record).
    rng = ScriptedRandom([0.0], choice_indices=[0])

    visitor = finalize_ordinary_valhalla_visit(state, rng)

    assert visitor is not None
    assert visitor.kingdom_id == 1
    assert state.leaders[VALHALLA_VISITOR_LEADER_ID] is visitor
    assert state.last_valhalla_visited_kingdom_id == 1
    assert state.kingdoms[1].valhalla_visit_count == 1


def test_finalize_ordinary_valhalla_visit_falls_back_when_the_due_alignment_has_no_king():
    # Only a NEUTRAL Kingdom exists; whichever of the 5 alignments comes up
    # due, the ordinary selector finds no GOOD/DRUID/etc. candidate and the
    # fallback still finds the one real, rotation-eligible Kingdom.
    state = _kingdom_only_state((1, Alignment.NEUTRAL))
    state.add_leader(LeaderState(1, 1, "King Bar", KING_LOCATION, is_king=True))
    rng = ScriptedRandom([0.0], choice_indices=[0])  # [0] -> GOOD due, no GOOD kingdom

    visitor = finalize_ordinary_valhalla_visit(state, rng)

    assert visitor is not None
    assert visitor.kingdom_id == 1


def test_gate_angel_due_alignment_advances_every_turn_with_no_gate_angel_caster_anywhere():
    # Desktop/VALHALLA.txt's own worked example, but driven entirely by
    # finalize_ordinary_valhalla_visit() -- proving the rotation itself
    # genuinely advances turn to turn even though nothing in this test
    # ever calls _execute_gate_angel(). Deliberately stays within turns
    # 1-3 (avoiding the real, already-confirmed `turn_number % 5 == 4`
    # force-reset boundary -- see test_cast_execution.py's own "also
    # resets on the turn mod 5 equals 4 boundary" test -- which can make
    # a *partial* 5-turn window legitimately repeat an alignment; that's
    # real, pre-existing behavior, not something this test re-litigates).
    state = _kingdom_only_state(*((kingdom_id, alignment) for kingdom_id, alignment in enumerate(GATE_ANGEL_ELIGIBLE_ALIGNMENTS, start=1)))
    for kingdom_id, _ in enumerate(GATE_ANGEL_ELIGIBLE_ALIGNMENTS, start=1):
        state.add_leader(LeaderState(kingdom_id, kingdom_id, f"King{kingdom_id}", HexCoord(kingdom_id, kingdom_id), is_king=True))

    seen_alignments = []
    for turn in (1, 2, 3):
        state.turn_number = turn
        visitor = finalize_ordinary_valhalla_visit(state, random.Random(turn))
        assert visitor is not None
        seen_alignments.append(state.gate_angel_due_alignment)

    # No repeats within this partial, reset-boundary-free window -- proof
    # the rotation genuinely advances turn to turn on its own.
    assert len(seen_alignments) == len(set(seen_alignments))
