"""Tests for turn/skeletal_decay.py -- see its module docstring for the 350-unit world cap and the
~10%-per-turn graveyard decomposition (Regolamento AK.txt [4.2.5])."""

from __future__ import annotations

from ak_engine.models.army_type import ArmyType
from ak_engine.models.game_state import ArmyState, GameState
from ak_engine.models.map import HexCoord
from ak_engine.turn.combat import Quality
from ak_engine.turn.skeletal_decay import (
    GRAVEYARD_DECAY_FIRST_TURN,
    GRAVEYARD_DECAY_FRACTION,
    WORLD_UNIT_CAP,
    decompose_graveyard,
)

from _helpers import ScriptedRandom

HOME = HexCoord(0, 0)
FIELD = HexCoord(1, 1)
OTHER = HexCoord(2, 2)


def _fill_graveyard(state: GameState, coord: HexCoord, count: int) -> None:
    for _ in range(count):
        state.record_battle_death(coord, ArmyType.HVY_CAVALRY, Quality.AVERAGE, kingdom_id=1)


def _fill_armies(state: GameState, count: int) -> None:
    for _ in range(count):
        state.add_army(ArmyState(state.new_army_id(), 1, ArmyType.HVY_CAVALRY, Quality.AVERAGE, HOME))


def test_nothing_rots_under_the_cap_without_the_per_turn_roll():
    state = GameState()
    _fill_armies(state, 100)
    _fill_graveyard(state, FIELD, 50)  # 150 total, well under 350

    assert decompose_graveyard(state) == 0
    assert len(state.battle_graveyard[FIELD]) == 50


def test_over_the_cap_the_oldest_dead_rot_until_the_total_is_350_again():
    state = GameState()
    _fill_armies(state, 300)
    _fill_graveyard(state, FIELD, 30)
    _fill_graveyard(state, OTHER, 30)  # 360 total: 10 over the cap

    removed = decompose_graveyard(state)

    assert removed == 10
    assert len(state.battle_graveyard[FIELD]) == 20  # the oldest 10 are all in FIELD
    assert len(state.battle_graveyard[OTHER]) == 30
    assert len(state.armies) + sum(len(v) for v in state.battle_graveyard.values()) == WORLD_UNIT_CAP


def test_an_emptied_province_key_is_deleted():
    state = GameState()
    _fill_armies(state, 349)
    _fill_graveyard(state, FIELD, 2)  # 351 total

    decompose_graveyard(state)

    assert len(state.battle_graveyard[FIELD]) == 1
    _fill_armies(state, 1)  # 351 again
    decompose_graveyard(state)
    assert FIELD not in state.battle_graveyard


def test_each_earlier_dead_army_rots_with_10_percent_chance_every_turn_after_the_first_ones():
    state = GameState()
    state.turn_number = GRAVEYARD_DECAY_FIRST_TURN
    state.turn_number = GRAVEYARD_DECAY_FIRST_TURN + 1
    state.record_battle_death(FIELD, ArmyType.LEGION, Quality.AVERAGE, kingdom_id=1)  # dies this turn: safe
    state.turn_number = GRAVEYARD_DECAY_FIRST_TURN + 2
    _fill_graveyard(state, FIELD, 3)  # three more dead of this turn: exempt
    # entries: [previous turn, this turn x3]
    state.battle_graveyard[FIELD][0].death_turn = GRAVEYARD_DECAY_FIRST_TURN
    rng = ScriptedRandom([GRAVEYARD_DECAY_FRACTION - 0.01])  # one roll, only for the earlier army: it rots

    removed = decompose_graveyard(state, rng)

    assert removed == 1
    assert len(state.battle_graveyard[FIELD]) == 3


def test_an_earlier_dead_army_survives_a_roll_above_10_percent():
    state = GameState()
    state.turn_number = GRAVEYARD_DECAY_FIRST_TURN
    state.record_battle_death(FIELD, ArmyType.LEGION, Quality.AVERAGE, kingdom_id=1)
    state.turn_number = GRAVEYARD_DECAY_FIRST_TURN + 1

    assert decompose_graveyard(state, ScriptedRandom([GRAVEYARD_DECAY_FRACTION + 0.01])) == 0
    assert len(state.battle_graveyard[FIELD]) == 1


def test_no_per_turn_rot_during_the_first_turns():
    state = GameState()
    state.turn_number = GRAVEYARD_DECAY_FIRST_TURN - 2
    state.record_battle_death(FIELD, ArmyType.LEGION, Quality.AVERAGE, kingdom_id=1)
    state.turn_number = GRAVEYARD_DECAY_FIRST_TURN - 1

    assert decompose_graveyard(state, ScriptedRandom([0.0])) == 0


def test_decompose_graveyard_never_touches_live_armies_including_a_commanded_skeletal_army():
    state = GameState()
    _fill_armies(state, 340)
    skeleton = ArmyState(state.new_army_id(), 1, ArmyType.LEGION, Quality.AVERAGE, HOME, commanded_by=1, is_skeletal=True)
    state.add_army(skeleton)
    _fill_graveyard(state, FIELD, 20)

    decompose_graveyard(state)

    assert skeleton.army_id in state.armies
    assert len(state.armies) == 341


def test_record_battle_death_stamps_a_monotonic_death_seq_and_the_turn():
    state = GameState()
    state.turn_number = 7
    _fill_graveyard(state, FIELD, 3)

    entries = state.battle_graveyard[FIELD]
    assert [entry.death_seq for entry in entries] == [0, 1, 2]
    assert {entry.death_turn for entry in entries} == {7}
