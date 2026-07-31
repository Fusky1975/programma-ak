"""Tests for turn/skeletal_decay.py -- see its module docstring for the
350-unit world cap / ~10%-per-turn graveyard decomposition rule
(Regolamento AK.txt [4.2.5], Phase 309).
"""

from __future__ import annotations

from ak_engine.models.army_type import ArmyType
from ak_engine.models.game_state import ArmyState, GameState
from ak_engine.models.map import HexCoord
from ak_engine.turn.combat import Quality
from ak_engine.turn.skeletal_decay import GRAVEYARD_DECAY_FRACTION, WORLD_UNIT_CAP, decompose_graveyard

HOME = HexCoord(0, 0)
FIELD = HexCoord(1, 1)


def _fill_graveyard(state: GameState, coord: HexCoord, count: int) -> None:
    for _ in range(count):
        state.record_battle_death(coord, ArmyType.HVY_CAVALRY, Quality.AVERAGE, kingdom_id=1)


def _fill_armies(state: GameState, count: int) -> None:
    for _ in range(count):
        state.add_army(ArmyState(state.new_army_id(), 1, ArmyType.HVY_CAVALRY, Quality.AVERAGE, HOME))


def test_decompose_graveyard_does_nothing_under_the_cap():
    state = GameState()
    _fill_armies(state, 100)
    _fill_graveyard(state, FIELD, 50)  # 150 total, well under 350

    removed = decompose_graveyard(state)

    assert removed == 0
    assert len(state.battle_graveyard[FIELD]) == 50


def test_decompose_graveyard_removes_roughly_10_percent_oldest_first():
    state = GameState()
    _fill_armies(state, WORLD_UNIT_CAP - 40)  # leaves room for 40 dead, still over cap by 10 with them
    _fill_graveyard(state, FIELD, 50)  # (350 - 40) + 50 = 360 > 350
    oldest_entries = list(state.battle_graveyard[FIELD][:5])  # lowest death_seq -- inserted first

    removed = decompose_graveyard(state)

    assert removed == round(50 * GRAVEYARD_DECAY_FRACTION) == 5
    remaining = state.battle_graveyard[FIELD]
    assert len(remaining) == 45
    for entry in oldest_entries:
        assert entry not in remaining


def test_decompose_graveyard_prunes_across_provinces_oldest_first_globally():
    state = GameState()
    _fill_armies(state, WORLD_UNIT_CAP)
    _fill_graveyard(state, HOME, 10)  # death_seq 0..9, older
    _fill_graveyard(state, FIELD, 10)  # death_seq 10..19, newer
    # 350 + 20 = 370 > 350; ~10% of 20 = 2, both from the older province.

    removed = decompose_graveyard(state)

    assert removed == 2
    assert len(state.battle_graveyard[HOME]) == 8
    assert len(state.battle_graveyard[FIELD]) == 10


def test_decompose_graveyard_deletes_an_emptied_province_key():
    state = GameState()
    _fill_armies(state, WORLD_UNIT_CAP)
    _fill_graveyard(state, HOME, 1)  # tiny province, gets fully consumed
    _fill_graveyard(state, FIELD, 19)  # bulk of the decay comes from here instead
    # 350 + 20 = 370 > 350; ~10% of 20 = 2 -- the 2 globally-oldest are
    # HOME's lone entry (death_seq 0) plus FIELD's first (death_seq 1).

    removed = decompose_graveyard(state)

    assert removed == 2
    assert HOME not in state.battle_graveyard
    assert len(state.battle_graveyard[FIELD]) == 18


def test_decompose_graveyard_can_round_down_to_zero_for_a_small_graveyard():
    state = GameState()
    _fill_armies(state, WORLD_UNIT_CAP - 2)
    _fill_graveyard(state, FIELD, 3)  # (350 - 2) + 3 = 351 > 350, but round(3 * 0.10) == 0

    removed = decompose_graveyard(state)

    assert removed == 0
    assert len(state.battle_graveyard[FIELD]) == 3


def test_decompose_graveyard_never_touches_live_armies_including_a_commanded_skeletal_army():
    state = GameState()
    _fill_armies(state, WORLD_UNIT_CAP - 40)
    skeletal = ArmyState(state.new_army_id(), 1, ArmyType.HVY_CAVALRY, Quality.CRACK, HOME, commanded_by=7, is_skeletal=True)
    state.add_army(skeletal)
    _fill_graveyard(state, FIELD, 50)

    decompose_graveyard(state)

    assert state.armies[skeletal.army_id] is skeletal
    assert len(state.armies) == (WORLD_UNIT_CAP - 40) + 1


def test_record_battle_death_stamps_a_monotonic_death_seq():
    state = GameState()

    state.record_battle_death(HOME, ArmyType.LEGION, Quality.VETERAN, kingdom_id=1)
    state.record_battle_death(FIELD, ArmyType.BOWMEN, Quality.GREEN, kingdom_id=2)

    assert state.battle_graveyard[HOME][0].death_seq == 0
    assert state.battle_graveyard[FIELD][0].death_seq == 1
    assert state.graveyard_death_counter == 2
