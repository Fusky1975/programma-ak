"""Action spells last for the turn they are cast in (rulebook [4.2x]):
Oratory ("per il resto del turno"), Phantasmal Armies, Plague's spread, and
Clairvoyance's watch must not outlive the turn."""

from __future__ import annotations

import random

from ak_engine.models.advanced_ability import AdvancedAbility
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


# ---- Mystic Winds ----------------------------------------------------------


def _mystic_winds(state: GameState) -> None:
    class Always(random.Random):
        def random(self):
            return 0.0

    state.leaders[1].skills = None  # a caster with no skill data casts without the success roll
    state.leaders[1].advanced_abilities.add(AdvancedAbility.MYSTIC_WINDS_SPELL)
    result = execute_cast(
        state, kingdom_id=1, leader_id=1, request=CastRequest(spell=Spell.MYSTIC_WINDS, target=2), rng=Always()
    )
    assert result.applied is True


def test_mystic_winds_sets_movement_to_five_and_remembers_the_normal_movement():
    state = _state()
    state.add_army(ArmyState(10, 1, ArmyType.LEGION, Quality.AVERAGE, PLACE, commanded_by=2, movement_points=2))

    _mystic_winds(state)

    assert state.armies[10].movement_points == 5
    assert state.armies[10].mystic_winds_prior_movement == 2
    assert state.leaders[2].mystic_winds_active is True


def test_a_second_mystic_winds_cast_does_not_give_back_movement_already_spent():
    state = _state()
    state.add_army(ArmyState(10, 1, ArmyType.LEGION, Quality.AVERAGE, PLACE, commanded_by=2, movement_points=2))
    _mystic_winds(state)
    state.armies[10].movement_points = 3  # two provinces walked under the spell

    _mystic_winds(state)

    assert state.armies[10].movement_points == 3


def test_when_the_spell_ends_the_army_has_only_the_movement_it_would_normally_have_left():
    from ak_engine.turn.cast_execution import end_mystic_winds_movement

    state = _state()
    state.add_army(ArmyState(10, 1, ArmyType.LEGION, Quality.AVERAGE, PLACE, commanded_by=2, movement_points=2))
    _mystic_winds(state)
    state.armies[10].movement_points = 3  # 2 points spent under the spell

    end_mystic_winds_movement([state.armies[10]])

    assert state.armies[10].movement_points == 0  # speed 2, two provinces already walked
    assert state.armies[10].mystic_winds_prior_movement is None


def test_the_spell_ends_before_a_battle_and_takes_the_extra_movement_with_it():
    from ak_engine.turn.battle_orchestrator import _clear_mystic_winds_before_battle

    state = _state()
    state.add_army(ArmyState(10, 1, ArmyType.LEGION, Quality.AVERAGE, PLACE, commanded_by=2, movement_points=2))
    state.add_army(ArmyState(11, 1, ArmyType.BOWMEN, Quality.AVERAGE, PLACE, commanded_by=2, movement_points=2))
    _mystic_winds(state)

    _clear_mystic_winds_before_battle([state.armies[10]], state)

    assert state.leaders[2].mystic_winds_active is False
    # Every army the leader commands is back to its normal movement, not just
    # the one in the battle.
    assert state.armies[10].movement_points == 2
    assert state.armies[11].movement_points == 2


def test_mystic_winds_does_not_outlive_the_turn():
    state = _state()
    state.add_army(ArmyState(10, 1, ArmyType.LEGION, Quality.AVERAGE, PLACE, commanded_by=2, movement_points=2))
    _mystic_winds(state)

    _replenish_turn_scoped_state(state)

    assert state.leaders[2].mystic_winds_active is False
    assert state.armies[10].mystic_winds_prior_movement is None
    assert state.armies[10].movement_points == 2  # the army's normal speed again


# ---- Illusory Terrain and Hide Feature: they last until they dissolve -------


def test_illusory_terrain_survives_the_turn_boundary_and_dissolves_on_a_15_percent_roll():
    from ak_engine.turn.cast_execution import ILLUSORY_TERRAIN_DISSOLVE_CHANCE, maybe_dissolve_illusory_terrain

    assert ILLUSORY_TERRAIN_DISSOLVE_CHANCE == 0.15
    state = _state()
    province = state.provinces[PLACE]
    province.illusory_terrain = Terrain.SEA
    _replenish_turn_scoped_state(state)
    assert province.illusory_terrain is Terrain.SEA  # a new turn does not end it

    class Roll(random.Random):
        def __init__(self, value):
            super().__init__()
            self.value = value

        def random(self):
            return self.value

    maybe_dissolve_illusory_terrain(province, Roll(0.15))  # not below 15%
    assert province.illusory_terrain is Terrain.SEA
    maybe_dissolve_illusory_terrain(province, Roll(0.14))
    assert province.illusory_terrain is None


def test_hide_feature_survives_the_turn_boundary_and_dissipates_on_a_10_percent_roll():
    from ak_engine.models.feature import Feature, FeatureType
    from ak_engine.turn.monster_raids import MONSTER_HIDE_DISSIPATION_CHANCE, maybe_dissipate_hidden_feature

    assert MONSTER_HIDE_DISSIPATION_CHANCE == 0.10
    state = _state()
    feature = Feature(1, PLACE, FeatureType.CAVE)
    feature.magically_hidden = True
    state.features[1] = feature
    _replenish_turn_scoped_state(state)
    assert feature.magically_hidden is True

    class Roll(random.Random):
        def __init__(self, value):
            super().__init__()
            self.value = value

        def random(self):
            return self.value

    maybe_dissipate_hidden_feature(feature, Roll(0.10))
    assert feature.magically_hidden is True
    maybe_dissipate_hidden_feature(feature, Roll(0.09))
    assert feature.magically_hidden is False


def test_run_turn_rolls_the_two_dissolves_once_per_turn():
    from ak_engine.models.feature import Feature, FeatureType

    state = _state()
    state.provinces[PLACE].illusory_terrain = Terrain.SEA
    feature = Feature(1, PLACE, FeatureType.CAVE)
    feature.magically_hidden = True
    state.features[1] = feature
    draws = {"count": 0}

    class Counting(random.Random):
        def random(self):
            draws["count"] += 1
            return 0.99  # never dissolves

    run_turn([], state, board_width=10, rng=Counting(1))

    assert state.provinces[PLACE].illusory_terrain is Terrain.SEA
    assert feature.magically_hidden is True
