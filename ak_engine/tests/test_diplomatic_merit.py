from __future__ import annotations

from ak_engine.models.alignment import Alignment
from ak_engine.models.discovery import Discovery
from ak_engine.models.game_state import GameState, KingdomState, LeaderState, ProvinceState
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.race import Race
from ak_engine.turn.diplomatic_merit import apply_diplomatic_merit
from ak_engine.turn.scientific_treaty import ScientificTreatyResult

BOUNDS = {"board_width": 30, "board_height": 15}
HOME_A = HexCoord(3, 3)
HOME_B = HexCoord(4, 3)  # adjacent to HOME_A
FAR = HexCoord(20, 10)
FAR2 = HexCoord(21, 10)  # a second, distinct non-adjacent-to-HOME_A coord


def build_state(*, adjacent: bool = True) -> GameState:
    state = GameState()
    home_b = HOME_B if adjacent else FAR
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.GOOD, HOME_A))
    state.add_kingdom(KingdomState(2, "Rivalia", Race.HUMAN, Alignment.GOOD, home_b))
    state.add_province(ProvinceState(HOME_A, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_province(ProvinceState(home_b, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2))
    state.add_leader(LeaderState(1, kingdom_id=1, name="King A", location=HOME_A, is_king=True))
    state.add_leader(LeaderState(2, kingdom_id=2, name="King B", location=home_b, is_king=True))
    return state


def test_apply_diplomatic_merit_allied_only_credits_plus_one():
    state = build_state(adjacent=False)
    state.allied_kingdoms.add(frozenset({1, 2}))

    apply_diplomatic_merit(state, [], **BOUNDS)

    assert state.leaders[1].merit_tally.diplomatic_merit_points == 1
    assert state.leaders[2].merit_tally.diplomatic_merit_points == 1


def test_apply_diplomatic_merit_allied_and_adjacent_credits_plus_three():
    state = build_state(adjacent=True)
    state.allied_kingdoms.add(frozenset({1, 2}))

    apply_diplomatic_merit(state, [], **BOUNDS)

    assert state.leaders[1].merit_tally.diplomatic_merit_points == 3
    assert state.leaders[2].merit_tally.diplomatic_merit_points == 3


def test_apply_diplomatic_merit_allied_adjacent_and_transfer_credits_plus_eight():
    # Matches the dossier's own worked example: an allied, adjacent
    # partner that also transfers a Discovery this turn is worth +8.
    state = build_state(adjacent=True)
    state.allied_kingdoms.add(frozenset({1, 2}))
    treaty_results = [
        ScientificTreatyResult(kingdom_a_id=1, kingdom_b_id=2, discovery_to_a=Discovery.TELESCOPE, discovery_to_b=None)
    ]

    apply_diplomatic_merit(state, treaty_results, **BOUNDS)

    assert state.leaders[1].merit_tally.diplomatic_merit_points == 8
    # Kingdom 2 received nothing this turn (discovery_to_b is None).
    assert state.leaders[2].merit_tally.diplomatic_merit_points == 3


def test_apply_diplomatic_merit_credits_the_other_direction_of_a_transfer():
    state = build_state(adjacent=False)
    state.allied_kingdoms.add(frozenset({1, 2}))
    treaty_results = [
        ScientificTreatyResult(kingdom_a_id=1, kingdom_b_id=2, discovery_to_a=None, discovery_to_b=Discovery.COMPASS)
    ]

    apply_diplomatic_merit(state, treaty_results, **BOUNDS)

    assert state.leaders[1].merit_tally.diplomatic_merit_points == 1
    assert state.leaders[2].merit_tally.diplomatic_merit_points == 1 + 5


def test_apply_diplomatic_merit_non_allied_credits_nothing():
    state = build_state(adjacent=True)

    apply_diplomatic_merit(state, [], **BOUNDS)

    assert state.leaders[1].merit_tally.diplomatic_merit_points == 0
    assert state.leaders[2].merit_tally.diplomatic_merit_points == 0


def test_apply_diplomatic_merit_credits_only_the_kings_own_leader():
    state = build_state(adjacent=True)
    state.allied_kingdoms.add(frozenset({1, 2}))
    state.add_leader(LeaderState(3, kingdom_id=1, name="A Hero", location=HOME_A, is_king=False))

    apply_diplomatic_merit(state, [], **BOUNDS)

    assert state.leaders[3].merit_tally.diplomatic_merit_points == 0


def test_apply_diplomatic_merit_skips_a_kingless_kingdom():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.GOOD, HOME_A))
    state.add_kingdom(KingdomState(2, "Rivalia", Race.HUMAN, Alignment.GOOD, HOME_B))
    state.add_province(ProvinceState(HOME_A, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_province(ProvinceState(HOME_B, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2))
    state.add_leader(LeaderState(2, kingdom_id=2, name="King B", location=HOME_B, is_king=True))
    state.allied_kingdoms.add(frozenset({1, 2}))

    apply_diplomatic_merit(state, [], **BOUNDS)  # must not raise despite Kingdom 1 having no King

    assert state.leaders[2].merit_tally.diplomatic_merit_points == 3


def test_apply_diplomatic_merit_accumulates_across_multiple_allied_partners():
    state = build_state(adjacent=False)
    state.add_kingdom(KingdomState(3, "Thirdia", Race.HUMAN, Alignment.GOOD, FAR2))
    state.add_province(ProvinceState(FAR2, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=3))
    state.add_leader(LeaderState(3, kingdom_id=3, name="King C", location=FAR2, is_king=True))
    state.allied_kingdoms.add(frozenset({1, 2}))
    state.allied_kingdoms.add(frozenset({1, 3}))

    apply_diplomatic_merit(state, [], **BOUNDS)

    assert state.leaders[1].merit_tally.diplomatic_merit_points == 2
