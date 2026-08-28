"""Tests for turn/monster_raids.py -- see its module docstring for the
full, THUNDERBIRD.md-sourced maturation/raid/Thunderbird formulas these
exercise.
"""

from __future__ import annotations

from ak_engine.models.alignment import Alignment
from ak_engine.models.feature import Feature, FeatureType
from ak_engine.models.game_state import GameState, KingdomState, ProvinceState
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.monster import Monster, MonsterEngagementState
from ak_engine.models.race import Race
from ak_engine.turn.monster_raids import (
    age_all_feature_guardians,
    age_feature_guardian,
    apply_fulfill_pacification,
    guardian_intimidated_by_combat_damage,
    maybe_dissipate_hidden_feature,
    resolve_province_raids,
)
from _helpers import ScriptedRandom

HOME = HexCoord(0, 0)


def _state_with_owned_province(coord: HexCoord = HOME, owner_kingdom_id: int | None = 1) -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, HOME))
    state.add_province(ProvinceState(coord, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=owner_kingdom_id))
    return state


def _feature(**overrides) -> Feature:
    defaults = dict(
        feature_id=1,
        coord=HOME,
        kind=FeatureType.DUNGEON,
        guardian_monster=Monster.CHIMERA,
        guardian_alignment=Alignment.NEUTRAL,
    )
    defaults.update(overrides)
    return Feature(**defaults)


# -- age_feature_guardian() --------------------------------------------


def test_age_feature_guardian_no_guardian_is_a_no_op_and_rolls_nothing():
    state = _state_with_owned_province()
    feature = _feature(guardian_monster=None)
    age_feature_guardian(state, feature, ScriptedRandom([]))
    assert feature.guardian_state is MonsterEngagementState.MERCENARY


def test_age_feature_guardian_unowned_province_never_rolls():
    state = _state_with_owned_province(owner_kingdom_id=None)
    feature = _feature(guardian_state=MonsterEngagementState.CALM)
    age_feature_guardian(state, feature, ScriptedRandom([]))
    assert feature.guardian_state is MonsterEngagementState.CALM


def test_age_feature_guardian_no_province_recorded_never_rolls():
    state = GameState()
    feature = _feature(guardian_state=MonsterEngagementState.CALM)
    age_feature_guardian(state, feature, ScriptedRandom([]))
    assert feature.guardian_state is MonsterEngagementState.CALM


def test_age_feature_guardian_3_percent_miss_consumes_no_threshold_roll():
    state = _state_with_owned_province()
    feature = _feature(guardian_state=MonsterEngagementState.CALM)
    # 0.5 >= 0.03 -> miss. A single-element script proves no second
    # (threshold) roll is consumed -- ScriptedRandom raises IndexError on
    # any extra .random() call.
    age_feature_guardian(state, feature, ScriptedRandom([0.5]))
    assert feature.guardian_state is MonsterEngagementState.CALM


def test_age_feature_guardian_worldly_threshold_passes_neutral_alignment():
    state = _state_with_owned_province()
    feature = _feature(guardian_state=MonsterEngagementState.CALM, guardian_alignment=Alignment.NEUTRAL)
    # 0.02 < 0.03 -> hit; 0.1 < 0.5 -> Worldly (Neutral) threshold.
    age_feature_guardian(state, feature, ScriptedRandom([0.02, 0.1]))
    assert feature.guardian_state is MonsterEngagementState.MERCENARY


def test_age_feature_guardian_worldly_threshold_fails_good_alignment():
    state = _state_with_owned_province()
    feature = _feature(guardian_state=MonsterEngagementState.CALM, guardian_alignment=Alignment.GOOD)
    age_feature_guardian(state, feature, ScriptedRandom([0.02, 0.1]))
    assert feature.guardian_state is MonsterEngagementState.CALM


def test_age_feature_guardian_worldly_threshold_fails_druidic_alignment():
    state = _state_with_owned_province()
    feature = _feature(guardian_state=MonsterEngagementState.CALM, guardian_alignment=Alignment.DRUID)
    age_feature_guardian(state, feature, ScriptedRandom([0.02, 0.1]))
    assert feature.guardian_state is MonsterEngagementState.CALM


def test_age_feature_guardian_animal_threshold_fails_neutral_alignment():
    state = _state_with_owned_province()
    feature = _feature(guardian_state=MonsterEngagementState.CALM, guardian_alignment=Alignment.NEUTRAL)
    # 0.02 < 0.03 -> hit; 0.9 >= 0.5 -> Animal (Pagan) threshold.
    age_feature_guardian(state, feature, ScriptedRandom([0.02, 0.9]))
    assert feature.guardian_state is MonsterEngagementState.CALM


def test_age_feature_guardian_animal_threshold_passes_pagan_alignment():
    state = _state_with_owned_province()
    feature = _feature(guardian_state=MonsterEngagementState.CALM, guardian_alignment=Alignment.PAGAN)
    age_feature_guardian(state, feature, ScriptedRandom([0.02, 0.9]))
    assert feature.guardian_state is MonsterEngagementState.MERCENARY


def test_age_feature_guardian_no_alignment_recorded_never_transitions():
    state = _state_with_owned_province()
    feature = _feature(guardian_state=MonsterEngagementState.CALM, guardian_alignment=None)
    age_feature_guardian(state, feature, ScriptedRandom([0.02, 0.1]))
    assert feature.guardian_state is MonsterEngagementState.CALM


def test_age_feature_guardian_mercenary_to_bold_transition():
    state = _state_with_owned_province()
    feature = _feature(guardian_state=MonsterEngagementState.MERCENARY, guardian_alignment=Alignment.NEUTRAL)
    age_feature_guardian(state, feature, ScriptedRandom([0.02, 0.1]))
    assert feature.guardian_state is MonsterEngagementState.BOLD


def test_age_feature_guardian_bold_guardian_has_no_further_step():
    state = _state_with_owned_province()
    feature = _feature(guardian_state=MonsterEngagementState.BOLD, guardian_alignment=Alignment.NEUTRAL)
    age_feature_guardian(state, feature, ScriptedRandom([0.02, 0.1]))
    assert feature.guardian_state is MonsterEngagementState.BOLD


def test_age_feature_guardian_looted_feature_consumes_rolls_but_never_transitions():
    state = _state_with_owned_province()
    feature = _feature(guardian_state=MonsterEngagementState.CALM, guardian_alignment=Alignment.NEUTRAL, looted=True)
    age_feature_guardian(state, feature, ScriptedRandom([0.02, 0.1]))
    assert feature.guardian_state is MonsterEngagementState.CALM


def test_age_all_feature_guardians_processes_every_feature_in_id_order():
    state = _state_with_owned_province()
    feature_a = _feature(feature_id=2, guardian_state=MonsterEngagementState.CALM, guardian_alignment=Alignment.NEUTRAL)
    feature_b = _feature(feature_id=1, guardian_state=MonsterEngagementState.CALM, guardian_alignment=Alignment.NEUTRAL)
    state.add_feature(feature_a)
    state.add_feature(feature_b)
    # Two identical (hit, Worldly) draws, one per feature, in id order.
    age_all_feature_guardians(state, ScriptedRandom([0.02, 0.1, 0.02, 0.1]))
    assert feature_a.guardian_state is MonsterEngagementState.MERCENARY
    assert feature_b.guardian_state is MonsterEngagementState.MERCENARY


# -- maybe_dissipate_hidden_feature() ------------------------------------


def test_maybe_dissipate_hidden_feature_not_hidden_rolls_nothing():
    feature = _feature(magically_hidden=False)
    maybe_dissipate_hidden_feature(feature, ScriptedRandom([]))
    assert feature.magically_hidden is False


def test_maybe_dissipate_hidden_feature_hit():
    feature = _feature(magically_hidden=True)
    maybe_dissipate_hidden_feature(feature, ScriptedRandom([0.05]))
    assert feature.magically_hidden is False


def test_maybe_dissipate_hidden_feature_miss():
    feature = _feature(magically_hidden=True)
    maybe_dissipate_hidden_feature(feature, ScriptedRandom([0.5]))
    assert feature.magically_hidden is True


# -- resolve_province_raids() --------------------------------------------


def test_resolve_province_raids_skips_looted_hidden_and_non_bold_features():
    state = _state_with_owned_province()
    province = state.provinces[HOME]
    state.add_feature(_feature(feature_id=1, guardian_state=MonsterEngagementState.BOLD, looted=True))
    state.add_feature(_feature(feature_id=2, guardian_state=MonsterEngagementState.BOLD, magically_hidden=True))
    state.add_feature(_feature(feature_id=3, guardian_state=MonsterEngagementState.MERCENARY))

    income, thunder_used, events = resolve_province_raids(state, 1, province, 100, None, False, ScriptedRandom([]))

    assert income == 100
    assert thunder_used is False
    assert events == []


def test_resolve_province_raids_activity_check_cowardly_25_percent_boundary():
    state = _state_with_owned_province()
    province = state.provinces[HOME]
    # Gr. Dragon: Temper.COWARDLY (25% active).
    state.add_feature(_feature(guardian_monster=Monster.GR_DRAGON, guardian_state=MonsterEngagementState.BOLD))

    # Just below the 25% cutoff -> active, proceeds to a real raid (no
    # Thunderbird holder configured).
    _, _, events = resolve_province_raids(state, 1, province, 700, None, False, ScriptedRandom([0.24]))
    assert len(events) == 1
    assert events[0].kind == "raid"

    state2 = _state_with_owned_province()
    province2 = state2.provinces[HOME]
    state2.add_feature(_feature(guardian_monster=Monster.GR_DRAGON, guardian_state=MonsterEngagementState.BOLD))
    # At/above the 25% cutoff -> inactive, no raid.
    _, _, events2 = resolve_province_raids(state2, 1, province2, 700, None, False, ScriptedRandom([0.25]))
    assert events2 == []


def test_resolve_province_raids_activity_check_berserk_always_active():
    state = _state_with_owned_province()
    province = state.provinces[HOME]
    # Gryphon: Temper.BERSERK (100% active).
    state.add_feature(_feature(guardian_monster=Monster.GRYPHON, guardian_state=MonsterEngagementState.BOLD))
    _, _, events = resolve_province_raids(state, 1, province, 700, None, False, ScriptedRandom([0.999]))
    assert len(events) == 1


def test_resolve_province_raids_thunderbird_blocks_only_the_matching_kingdom():
    state = _state_with_owned_province()
    province = state.provinces[HOME]
    state.add_feature(_feature(guardian_monster=Monster.GRYPHON, guardian_state=MonsterEngagementState.BOLD))
    # active (0.0 < 1.0), Thunderbird roll 0.1 < 0.40 -> blocked.
    income, thunder_used, events = resolve_province_raids(state, 1, province, 700, 1, False, ScriptedRandom([0.0, 0.1]))
    assert income == 700
    assert thunder_used is True
    assert len(events) == 1
    assert (events[0].kind, events[0].province_coord, events[0].feature_id, events[0].monster, events[0].damage) == (
        "thunderbird",
        HOME,
        1,
        Monster.GRYPHON,
        0,
    )
    assert state.features[1].guardian_state is MonsterEngagementState.MERCENARY


def test_resolve_province_raids_thunderbird_does_not_block_a_different_kingdom():
    state = _state_with_owned_province()
    province = state.provinces[HOME]
    state.add_feature(_feature(guardian_monster=Monster.GRYPHON, guardian_state=MonsterEngagementState.BOLD))
    # divine_archangel_kingdom_id=2, but this province's raid is against kingdom 1.
    income, thunder_used, events = resolve_province_raids(state, 1, province, 700, 2, False, ScriptedRandom([0.0]))
    assert thunder_used is False
    assert len(events) == 1
    assert events[0].kind == "raid"
    assert income < 700


def test_resolve_province_raids_thunderbird_already_used_this_turn_does_not_reroll():
    state = _state_with_owned_province()
    province = state.provinces[HOME]
    state.add_feature(_feature(guardian_monster=Monster.GRYPHON, guardian_state=MonsterEngagementState.BOLD))
    # thunder_used already True -> no Thunderbird roll consumed, straight to damage.
    income, thunder_used, events = resolve_province_raids(state, 1, province, 700, 1, True, ScriptedRandom([0.0]))
    assert thunder_used is True
    assert len(events) == 1
    assert events[0].kind == "raid"


def test_resolve_province_raids_damage_formula_worked_example():
    state = _state_with_owned_province()
    province = state.provinces[HOME]
    # Gargoyle: average_hit_points=15 (per THUNDERBIRD.md's own worked
    # example table), Temper checked separately below.
    from ak_engine.models.monster import MONSTER_RUNTIME_PROFILE

    profile = MONSTER_RUNTIME_PROFILE[Monster.GARGOYLE]
    state.add_feature(_feature(guardian_monster=Monster.GARGOYLE, guardian_state=MonsterEngagementState.BOLD))
    income, _, events = resolve_province_raids(state, 1, province, 10, None, False, ScriptedRandom([0.0]))
    expected_damage = profile.average_hit_points * 10 // 70 + 1
    assert events[0].damage == expected_damage
    assert income == 10 - expected_damage


def test_resolve_province_raids_damage_stacks_across_two_bold_features():
    state = _state_with_owned_province()
    province = state.provinces[HOME]
    state.add_feature(_feature(feature_id=1, guardian_monster=Monster.GRYPHON, guardian_state=MonsterEngagementState.BOLD))
    state.add_feature(_feature(feature_id=2, guardian_monster=Monster.SPHINX, guardian_state=MonsterEngagementState.BOLD))
    income, _, events = resolve_province_raids(state, 1, province, 700, None, False, ScriptedRandom([0.0, 0.0]))
    assert len(events) == 2
    # The second feature's damage is computed against the already-reduced income.
    assert events[1].damage <= events[0].damage
    assert income == 700 - events[0].damage - events[1].damage


# -- Phase 671: the 2 deferred pacification triggers --------------------


def test_apply_fulfill_pacification_bold_becomes_mercenary():
    feature = _feature(guardian_state=MonsterEngagementState.BOLD)
    assert apply_fulfill_pacification(feature) is True
    assert feature.guardian_state is MonsterEngagementState.MERCENARY


def test_apply_fulfill_pacification_mercenary_becomes_calm():
    feature = _feature(guardian_state=MonsterEngagementState.MERCENARY)
    assert apply_fulfill_pacification(feature) is True
    assert feature.guardian_state is MonsterEngagementState.CALM


def test_apply_fulfill_pacification_already_calm_is_a_no_op():
    feature = _feature(guardian_state=MonsterEngagementState.CALM)
    assert apply_fulfill_pacification(feature) is False
    assert feature.guardian_state is MonsterEngagementState.CALM


def test_apply_fulfill_pacification_other_states_also_pacify_to_calm():
    # THUNDERBIRD.md's own compiled snippet: any state other than Calm or
    # Bold falls into the "ELSE -> Calm" branch too.
    feature = _feature(guardian_state=MonsterEngagementState.ZOMBOID)
    assert apply_fulfill_pacification(feature) is True
    assert feature.guardian_state is MonsterEngagementState.CALM


def test_guardian_intimidated_by_combat_damage_non_bold_never_transitions():
    feature = _feature(guardian_state=MonsterEngagementState.MERCENARY)
    assert guardian_intimidated_by_combat_damage(feature, 10, 0) is False
    assert feature.guardian_state is MonsterEngagementState.MERCENARY


def test_guardian_intimidated_by_combat_damage_exactly_at_threshold_transitions():
    # 10 starting HP: threshold is 10 // 2 + 1 == 6 lost. Losing exactly
    # 6 (down to 4 remaining) triggers.
    feature = _feature(guardian_state=MonsterEngagementState.BOLD)
    assert guardian_intimidated_by_combat_damage(feature, 10, 4) is True
    assert feature.guardian_state is MonsterEngagementState.MERCENARY


def test_guardian_intimidated_by_combat_damage_one_short_of_threshold_does_not_transition():
    feature = _feature(guardian_state=MonsterEngagementState.BOLD)
    assert guardian_intimidated_by_combat_damage(feature, 10, 5) is False
    assert feature.guardian_state is MonsterEngagementState.BOLD


def test_guardian_intimidated_by_combat_damage_total_loss_transitions():
    feature = _feature(guardian_state=MonsterEngagementState.BOLD)
    assert guardian_intimidated_by_combat_damage(feature, 10, 0) is True
    assert feature.guardian_state is MonsterEngagementState.MERCENARY


def test_guardian_intimidated_by_combat_damage_no_damage_at_all_does_not_transition():
    feature = _feature(guardian_state=MonsterEngagementState.BOLD)
    assert guardian_intimidated_by_combat_damage(feature, 10, 10) is False
    assert feature.guardian_state is MonsterEngagementState.BOLD
