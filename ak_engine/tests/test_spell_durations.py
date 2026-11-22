"""Action spells last for the turn they are cast in (rulebook [4.2x]):
Oratory ("per il resto del turno"), Phantasmal Armies, Plague's spread, and
Clairvoyance's watch must not outlive the turn."""

from __future__ import annotations

import random

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.enums import Ability, Spell
from ak_engine.models.game_state import ArmyState, GameState, KingdomState, LeaderState, ProvinceState
from ak_engine.models.kingdom import SkillTable
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.race import Race
from ak_engine.turn.cast_decode import CastRequest
from ak_engine.turn.cast_execution import execute_cast
from ak_engine.turn.combat import Quality
from ak_engine.turn.turn_processor import _replenish_turn_scoped_state, _revert_oratory_boosts, run_turn

PLACE = HexCoord(2, 2)


def _state() -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Humania", Race.HUMAN, Alignment.GOOD, HexCoord(0, 0)))
    state.add_province(ProvinceState(PLACE, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, name="Numenor"))
    state.add_leader(LeaderState(1, 1, "Mage", PLACE, is_king=True))
    state.add_leader(LeaderState(2, 1, "Captain", PLACE))
    raw = [0] * 31
    raw[Ability.PSYCHIC.value * 2] = 4
    raw[Ability.PSYCHIC.value * 2 + 1] = 4
    state.leaders[1].skills = SkillTable(raw_values=raw)
    return state


def _oratory(state: GameState) -> None:
    class Always(random.Random):
        def random(self):  # every roll succeeds
            return 0.0

    result = execute_cast(
        state, kingdom_id=1, leader_id=1, request=CastRequest(spell=Spell.ORATORY, target=2), rng=Always()
    )
    assert result.applied is True


def test_oratory_raises_the_rank_during_the_turn_and_takes_it_back_at_the_end():
    state = _state()
    state.add_army(ArmyState(10, 1, ArmyType.LEGION, Quality.AVERAGE, PLACE, commanded_by=2))

    _oratory(state)
    assert state.armies[10].quality is Quality.VETERAN

    _revert_oratory_boosts(state)
    assert state.armies[10].quality is Quality.AVERAGE
    assert state.armies[10].oratory_boost_levels == 0


def test_a_repeated_oratory_cast_is_not_cumulative_and_still_reverts_fully():
    state = _state()
    state.add_army(ArmyState(10, 1, ArmyType.LEGION, Quality.GREEN, PLACE, commanded_by=2))

    _oratory(state)
    _oratory(state)
    assert state.armies[10].quality is Quality.AVERAGE

    _revert_oratory_boosts(state)
    assert state.armies[10].quality is Quality.GREEN


def test_an_elite_army_gets_nothing_from_oratory_and_loses_nothing_at_the_end():
    state = _state()
    state.add_army(ArmyState(10, 1, ArmyType.LEGION, Quality.ELITE, PLACE, commanded_by=2))

    _oratory(state)
    _revert_oratory_boosts(state)

    assert state.armies[10].quality is Quality.ELITE


def test_a_rank_earned_in_battle_during_the_turn_survives_the_oratory_revert():
    state = _state()
    state.add_army(ArmyState(10, 1, ArmyType.LEGION, Quality.AVERAGE, PLACE, commanded_by=2))

    _oratory(state)  # Veteran, with the boost on record
    state.armies[10].quality = Quality(int(state.armies[10].quality) + 1)  # a victory raises it again

    _revert_oratory_boosts(state)
    # Average -> (Oratory) Veteran -> (victory) Crack -> (Oratory ends) Veteran:
    # the rank earned in battle stays, only Oratory's own level goes.
    assert state.armies[10].quality is Quality.VETERAN


def test_run_turn_ends_with_the_pre_oratory_rank():
    state = _state()
    state.kingdoms[1].treasury = 1000
    state.add_army(ArmyState(10, 1, ArmyType.LEGION, Quality.AVERAGE, PLACE, commanded_by=2))
    _oratory(state)

    run_turn([], state, board_width=10, rng=random.Random(1))

    assert state.armies[10].quality is Quality.AVERAGE


def test_phantasmal_armies_does_not_outlive_the_turn():
    state = _state()
    state.leaders[2].phantasmal_armies_level = 3

    _replenish_turn_scoped_state(state)

    assert state.leaders[2].phantasmal_armies_level == 0


def test_plague_does_not_stay_in_a_province_after_the_turn():
    state = _state()
    state.provinces[PLACE].plague_active = True

    _replenish_turn_scoped_state(state)

    assert state.provinces[PLACE].plague_active is False


def test_a_bless_tax_bonus_ends_with_the_turn():
    state = _state()
    state.provinces[PLACE].tax_modifier_percent = 60

    _replenish_turn_scoped_state(state)

    assert state.provinces[PLACE].tax_modifier_percent == 0


def test_clairvoyance_watches_are_cleared_when_the_next_turn_starts_not_before():
    state = _state()
    state.leaders[1].clairvoyance_cast_target = 2
    state.leaders[2].clairvoyance_watchers.add(1)

    _replenish_turn_scoped_state(state)
    # Still readable while the finished turn's reports are composed.
    assert state.leaders[1].clairvoyance_cast_target == 2

    state.reset_turn_spell_effects()
    assert state.leaders[1].clairvoyance_cast_target is None
    assert state.leaders[2].clairvoyance_watchers == set()
