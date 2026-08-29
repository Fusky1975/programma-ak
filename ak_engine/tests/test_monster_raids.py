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
from ak_engine.models.temper import Temper
from ak_engine.models.treasure import Treasure
from ak_engine.turn.encounter import MonsterTalkReply
from ak_engine.turn.monster_raids import (
    age_all_feature_guardians,
    age_feature_guardian,
    apply_fulfill_pacification,
    guardian_undeterred,
    intimidation_packet_chance,
    maybe_dissipate_hidden_feature,
    resolve_monster_raid_reply,
    resolve_province_raids,
    roll_guardian_intimidation,
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


# -- Phase 673 (Desktop/BOLD OK.txt): the real per-packet intimidation --
# -- formula, superseding Phase 671's own project-original total-loss --
# -- approximation ------------------------------------------------------


def test_intimidation_packet_chance_zero_or_negative_damage_is_zero():
    assert intimidation_packet_chance(0, Temper.COWARDLY, 10) == 0.0
    assert intimidation_packet_chance(-1, Temper.BERSERK, 10) == 0.0


def test_intimidation_packet_chance_matches_bold_ok_worked_table_mtbasehp_10():
    # BOLD OK.txt section 9.6's own worked table, 1 point of damage.
    assert intimidation_packet_chance(1, Temper.COWARDLY, 10) == 0.4
    assert intimidation_packet_chance(1, Temper.CAUTIOUS, 10) == 0.3
    assert intimidation_packet_chance(1, Temper.BRAVE, 10) == 0.2
    assert intimidation_packet_chance(1, Temper.BERSERK, 10) == 0.1


def test_intimidation_packet_chance_matches_bold_ok_worked_table_mtbasehp_20():
    assert intimidation_packet_chance(1, Temper.COWARDLY, 20) == 0.2
    assert intimidation_packet_chance(1, Temper.CAUTIOUS, 20) == 0.15
    assert intimidation_packet_chance(1, Temper.BRAVE, 20) == 0.10
    assert intimidation_packet_chance(1, Temper.BERSERK, 20) == 0.05


def test_intimidation_packet_chance_certain_damage_matches_bold_ok_section_9_7():
    # mtbasehp=10's own d_certo row: Cowardly 3, Cautious 4, Brave 5, Berserk 10.
    assert intimidation_packet_chance(3, Temper.COWARDLY, 10) == 1.0
    assert intimidation_packet_chance(2, Temper.COWARDLY, 10) < 1.0
    assert intimidation_packet_chance(4, Temper.CAUTIOUS, 10) == 1.0
    assert intimidation_packet_chance(3, Temper.CAUTIOUS, 10) < 1.0
    assert intimidation_packet_chance(5, Temper.BRAVE, 10) == 1.0
    assert intimidation_packet_chance(10, Temper.BERSERK, 10) == 1.0


def test_intimidation_packet_chance_clamps_above_1():
    assert intimidation_packet_chance(100, Temper.COWARDLY, 10) == 1.0


def test_roll_guardian_intimidation_non_bold_never_rolls():
    feature = _feature(guardian_state=MonsterEngagementState.MERCENARY, guardian_monster=Monster.CHIMERA)
    assert roll_guardian_intimidation(feature, [5, 5, 5], Temper.BRAVE, ScriptedRandom([])) is False
    assert feature.guardian_state is MonsterEngagementState.MERCENARY


def test_roll_guardian_intimidation_no_packets_never_rolls():
    feature = _feature(guardian_state=MonsterEngagementState.BOLD, guardian_monster=Monster.CHIMERA)
    assert roll_guardian_intimidation(feature, [], Temper.BRAVE, ScriptedRandom([])) is False
    assert feature.guardian_state is MonsterEngagementState.BOLD


def test_roll_guardian_intimidation_zero_damage_packet_consumes_no_roll():
    feature = _feature(guardian_state=MonsterEngagementState.BOLD, guardian_monster=Monster.CHIMERA)
    assert roll_guardian_intimidation(feature, [0], Temper.BRAVE, ScriptedRandom([])) is False
    assert feature.guardian_state is MonsterEngagementState.BOLD


def test_roll_guardian_intimidation_single_packet_success_transitions_to_mercenary():
    # Chimera: average_hit_points=25, Temper.BRAVE (factor 4-2=2).
    # damage=13 -> p = 13*2/25 = 1.04 -> clamped to 1.0, certain success.
    feature = _feature(guardian_state=MonsterEngagementState.BOLD, guardian_monster=Monster.CHIMERA)
    assert roll_guardian_intimidation(feature, [13], Temper.BRAVE, ScriptedRandom([0.5])) is True
    assert feature.guardian_state is MonsterEngagementState.MERCENARY


def test_roll_guardian_intimidation_single_packet_failure_stays_bold():
    # damage=1 -> p = 1*2/25 = 0.08 -- a 0.5 roll misses.
    feature = _feature(guardian_state=MonsterEngagementState.BOLD, guardian_monster=Monster.CHIMERA)
    assert roll_guardian_intimidation(feature, [1], Temper.BRAVE, ScriptedRandom([0.5])) is False
    assert feature.guardian_state is MonsterEngagementState.BOLD


def test_roll_guardian_intimidation_every_packet_rolls_independently_even_after_success():
    # First packet succeeds (roll 0.0 < certain chance); a second,
    # low-damage packet still consumes its own roll (0.9, a miss) --
    # proving no early exit once intimidated, per BOLD OK.txt section 9.8.
    feature = _feature(guardian_state=MonsterEngagementState.BOLD, guardian_monster=Monster.CHIMERA)
    rng = ScriptedRandom([0.0, 0.9])
    assert roll_guardian_intimidation(feature, [13, 1], Temper.BRAVE, rng) is True
    assert feature.guardian_state is MonsterEngagementState.MERCENARY
    assert rng._randoms == []  # both packets' own rolls were actually consumed


# -- guardian_undeterred() -----------------------------------------------


def test_guardian_undeterred_took_damage_and_still_bold():
    feature = _feature(guardian_state=MonsterEngagementState.BOLD)
    assert guardian_undeterred(feature, took_damage=True) is True


def test_guardian_undeterred_no_damage_taken():
    feature = _feature(guardian_state=MonsterEngagementState.BOLD)
    assert guardian_undeterred(feature, took_damage=False) is False


def test_guardian_undeterred_not_bold():
    feature = _feature(guardian_state=MonsterEngagementState.MERCENARY)
    assert guardian_undeterred(feature, took_damage=True) is False


# -- Phase 679: resolve_monster_raid_reply() -- NOARMY.md's own 5 real
# worked examples, fully deterministic (no rng involved at all).


def test_resolve_monster_raid_reply_basilisk_feature_121_is_wfree():
    assert resolve_monster_raid_reply(Monster.BASILISK, 121, Treasure(67)) is MonsterTalkReply.R_WFREE


def test_resolve_monster_raid_reply_giant_octopus_feature_115_is_wfree():
    assert resolve_monster_raid_reply(Monster.GI_OCTOPUS, 115, Treasure(68)) is MonsterTalkReply.R_WFREE


def test_resolve_monster_raid_reply_basilisk_feature_112_is_wfree():
    assert resolve_monster_raid_reply(Monster.BASILISK, 112, Treasure(67)) is MonsterTalkReply.R_WFREE


def test_resolve_monster_raid_reply_imp_feature_31_is_circnav_not_wfree():
    assert resolve_monster_raid_reply(Monster.IMP, 31, Treasure(44)) is MonsterTalkReply.R_CIRCNAV


def test_resolve_monster_raid_reply_great_white_whale_feature_39_is_sell_not_wfree():
    assert resolve_monster_raid_reply(Monster.GW_WHALE, 39, Treasure(48)) is MonsterTalkReply.R_SELL


# -- Phase 679: resolve_province_raids()'s own new Build_Raid_Profile/noarmy
# gate, wired in before the Thunderbird check --


def test_resolve_province_raids_wfree_gate_cancels_the_raid_before_thunderbird():
    state = _state_with_owned_province()
    province = state.provinces[HOME]
    state.add_feature(
        _feature(
            feature_id=121, guardian_monster=Monster.BASILISK, guardian_state=MonsterEngagementState.BOLD,
            treasure=Treasure(67),
        )
    )
    # A single scripted value for the (Basilisk, Brave, 75%) activity
    # check -- if the code tried to consume a further Thunderbird roll
    # after the new gate, ScriptedRandom would raise on an empty list,
    # proving the gate short-circuits before Thunderbird is ever reached.
    income, thunder_used, events = resolve_province_raids(state, 1, province, 700, 1, False, ScriptedRandom([0.0]))

    assert income == 700
    assert thunder_used is False
    assert events == []
    assert state.features[121].guardian_state is MonsterEngagementState.BOLD


def test_resolve_province_raids_non_gated_reply_raids_normally():
    state = _state_with_owned_province()
    province = state.provinces[HOME]
    state.add_feature(
        _feature(
            feature_id=31, guardian_monster=Monster.IMP, guardian_state=MonsterEngagementState.BOLD,
            treasure=Treasure(44),
        )
    )
    # Imp is Temper.CAUTIOUS (50% active); divine_archangel_kingdom_id=None
    # short-circuits the Thunderbird roll, so only the activity check's own
    # single value is scripted.
    income, thunder_used, events = resolve_province_raids(state, 1, province, 700, None, False, ScriptedRandom([0.0]))

    assert thunder_used is False
    assert len(events) == 1
    assert events[0].kind == "raid"
    assert income < 700
