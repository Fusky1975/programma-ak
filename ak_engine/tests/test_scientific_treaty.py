from __future__ import annotations

import pytest

from ak_engine.models.alignment import Alignment
from ak_engine.models.discovery import Discovery
from ak_engine.models.game_state import GameState, KingdomState, LeaderState, ProvinceState
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.race import Race
from ak_engine.turn.scientific_treaty import alignment_check_success_chance, execute_scientific_treaties

from _helpers import ScriptedRandom

BOUNDS = {"board_width": 30, "board_height": 15}
HOME_A = HexCoord(3, 3)
HOME_B = HexCoord(4, 3)  # adjacent to HOME_A
FAR = HexCoord(20, 10)


def build_state(*, adjacent: bool = True) -> GameState:
    state = GameState()
    home_b = HOME_B if adjacent else FAR
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.GOOD, HOME_A))
    state.add_kingdom(KingdomState(2, "Rivalia", Race.HUMAN, Alignment.GOOD, home_b))
    state.add_province(ProvinceState(HOME_A, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_province(ProvinceState(home_b, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2))
    state.allied_kingdoms.add(frozenset({1, 2}))
    state.treat_permissions.add((1, 2))
    state.treat_permissions.add((2, 1))
    return state


def test_mutual_treat_between_allies_in_contact_exchanges_each_direction():
    state = build_state()
    state.kingdoms[1].discoveries.add(Discovery.COMPASS)
    state.kingdoms[2].discoveries.add(Discovery.TELESCOPE)

    results = execute_scientific_treaties(state, **BOUNDS)

    assert len(results) == 1
    result = results[0]
    assert {result.kingdom_a_id, result.kingdom_b_id} == {1, 2}
    assert Discovery.TELESCOPE in state.kingdoms[1].discoveries
    assert Discovery.COMPASS in state.kingdoms[2].discoveries


def test_no_exchange_when_treat_order_is_not_mutual():
    state = build_state()
    state.treat_permissions.discard((2, 1))  # only kingdom 1 issued Treat naming 2
    state.kingdoms[1].discoveries.add(Discovery.COMPASS)

    results = execute_scientific_treaties(state, **BOUNDS)

    assert results == []
    assert Discovery.COMPASS not in state.kingdoms[2].discoveries


def test_no_exchange_when_kingdoms_are_not_allied():
    state = build_state()
    state.allied_kingdoms.clear()
    state.kingdoms[1].discoveries.add(Discovery.COMPASS)

    results = execute_scientific_treaties(state, **BOUNDS)

    assert results == []


def test_no_exchange_when_kingdoms_are_not_in_contact():
    # RULES.AK [8.4]: "the 2 Kingdoms are adjacent, or else a character
    # from one Kingdom must be inside the other Kingdom" -- neither
    # holds here, so the mutual Treat order goes nowhere.
    state = build_state(adjacent=False)
    state.kingdoms[1].discoveries.add(Discovery.COMPASS)

    results = execute_scientific_treaties(state, **BOUNDS)

    assert results == []


def test_leader_presence_inside_the_other_kingdom_satisfies_contact():
    state = build_state(adjacent=False)
    state.add_leader(LeaderState(1, 1, "Envoy", FAR))  # kingdom 1's own leader, standing in kingdom 2's territory
    state.kingdoms[1].discoveries.add(Discovery.COMPASS)

    results = execute_scientific_treaties(state, **BOUNDS)

    assert len(results) == 1
    assert Discovery.COMPASS in state.kingdoms[2].discoveries


def test_only_one_kingdom_has_something_to_give_still_exchanges_that_one():
    state = build_state()
    state.kingdoms[1].discoveries.add(Discovery.COMPASS)
    # kingdom 2 has nothing kingdom 1 doesn't already effectively lack a match for

    results = execute_scientific_treaties(state, **BOUNDS)

    assert len(results) == 1
    result = results[0]
    a_gets, b_gets = (
        (result.discovery_to_a, result.discovery_to_b) if result.kingdom_a_id == 1 else (result.discovery_to_b, result.discovery_to_a)
    )
    assert b_gets == Discovery.COMPASS
    assert a_gets is None


def test_highest_priority_discovery_is_the_one_exchanged():
    # PONY_EXPRESS (DISCOVERY_DISPLAY_VALUE 20) outranks COMPASS (2) --
    # the higher-priority one is given away, matching the turn report's
    # own ordering per RULES.AK [8.4]'s own text.
    state = build_state()
    state.kingdoms[1].discoveries.add(Discovery.COMPASS)
    state.kingdoms[1].discoveries.add(Discovery.PONY_EXPRESS)

    results = execute_scientific_treaties(state, **BOUNDS)

    assert len(results) == 1
    result = results[0]
    given = result.discovery_to_b if result.kingdom_a_id == 1 else result.discovery_to_a
    assert given == Discovery.PONY_EXPRESS


def test_no_result_recorded_when_neither_side_has_anything_new():
    state = build_state()
    state.kingdoms[1].discoveries.add(Discovery.COMPASS)
    state.kingdoms[2].discoveries.add(Discovery.COMPASS)

    results = execute_scientific_treaties(state, **BOUNDS)

    assert results == []


def test_does_not_touch_merit_tally_or_first_found_registry():
    # See module docstring: neither discoveries_via_espionage nor
    # discoveries_first_found_by are the right bucket for a Treaty gift.
    state = build_state()
    state.add_leader(LeaderState(1, 1, "King", HOME_A))
    state.discoveries_first_found_by[Discovery.COMPASS] = 1
    state.kingdoms[1].discoveries.add(Discovery.COMPASS)

    execute_scientific_treaties(state, **BOUNDS)

    assert state.leaders[1].merit_tally.discoveries_via_espionage == 0
    assert Discovery.COMPASS not in state.discoveries_first_found_by or state.discoveries_first_found_by[Discovery.COMPASS] == 1


# -- Phase 474: real alignment-distance success gate (SS4.5/SS18.3) -------


def test_alignment_check_success_chance_same_class_is_guaranteed():
    assert alignment_check_success_chance(Alignment.GOOD, Alignment.GOOD) == 1.0


def test_alignment_check_success_chance_decays_by_40_points_per_step():
    assert alignment_check_success_chance(Alignment.GOOD, Alignment.DRUID) == pytest.approx(0.6)  # distance 1
    assert alignment_check_success_chance(Alignment.GOOD, Alignment.NEUTRAL) == pytest.approx(0.2)  # distance 2


def test_alignment_check_success_chance_floors_at_zero():
    assert alignment_check_success_chance(Alignment.GOOD, Alignment.PAGAN) == 0.0  # distance 3 -> 1 - 1.2


def test_distance_zero_pair_never_rolls_the_alignment_gate():
    # Both kingdoms default to Alignment.GOOD -- P=1.0, so the gate must
    # never call rng.random() at all; an empty ScriptedRandom would raise
    # IndexError if it did.
    state = build_state()
    state.kingdoms[1].discoveries.add(Discovery.COMPASS)

    results = execute_scientific_treaties(state, board_width=BOUNDS["board_width"], board_height=BOUNDS["board_height"], rng=ScriptedRandom([]))

    assert len(results) == 1


def test_alignment_distance_blocks_the_exchange_on_a_failed_roll():
    state = build_state()
    state.kingdoms[2].alignment = Alignment.DRUID  # distance 1 from Good -> 60% chance
    state.kingdoms[1].discoveries.add(Discovery.COMPASS)

    results = execute_scientific_treaties(
        state, board_width=BOUNDS["board_width"], board_height=BOUNDS["board_height"], rng=ScriptedRandom([0.6])
    )  # 0.6 >= 0.6 chance -> fails

    assert results == []
    assert Discovery.COMPASS not in state.kingdoms[2].discoveries


def test_alignment_distance_allows_the_exchange_on_a_successful_roll():
    state = build_state()
    state.kingdoms[2].alignment = Alignment.DRUID
    state.kingdoms[1].discoveries.add(Discovery.COMPASS)

    results = execute_scientific_treaties(
        state, board_width=BOUNDS["board_width"], board_height=BOUNDS["board_height"], rng=ScriptedRandom([0.59])
    )  # 0.59 < 0.6 chance -> succeeds

    assert len(results) == 1
    assert Discovery.COMPASS in state.kingdoms[2].discoveries


def test_alignment_distance_beyond_two_steps_always_blocks():
    state = build_state()
    state.kingdoms[2].alignment = Alignment.PAGAN  # distance 3 from Good -> P=0.0
    state.kingdoms[1].discoveries.add(Discovery.COMPASS)

    results = execute_scientific_treaties(
        state, board_width=BOUNDS["board_width"], board_height=BOUNDS["board_height"], rng=ScriptedRandom([0.0])
    )  # even the lowest possible roll still fails a P=0.0 gate

    assert results == []
