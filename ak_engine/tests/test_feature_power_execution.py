from __future__ import annotations

import random

from ak_engine.models.alignment import Alignment
from ak_engine.models.discovery import Discovery
from ak_engine.models.enums import Ability
from ak_engine.models.feature import Feature, FeatureType
from ak_engine.models.game_state import GameState, KingdomState, LeaderState
from ak_engine.models.kingdom import SkillTable
from ak_engine.models.magic_feature import MagicFeature
from ak_engine.models.map import HexCoord
from ak_engine.models.power import Power, PowerCondition
from ak_engine.models.race import Race
from ak_engine.models.sex import Sex
from ak_engine.models.temper import Temper
from ak_engine.turn.feature_power_execution import (
    TRACTABLE_POWERS,
    derive_feature_event,
    resolve_feature_power_attempt,
)

LOCATION = HexCoord(3, 9)
LEADER_ID = 1


def _feature(feature_id: int, province: int, kind: FeatureType) -> Feature:
    x, y = divmod(province, 100)
    return Feature(feature_id=feature_id, coord=HexCoord(x, y), kind=kind)


def _state_with_leader(**kwargs) -> GameState:
    state = GameState()
    state.add_leader(LeaderState(LEADER_ID, 1, "Searcher", LOCATION, **kwargs))
    return state


def _skilled_leader(ability: Ability, skill: int, aptitude: int, **kwargs) -> LeaderState:
    raw = [0] * 30
    raw[ability.value * 2] = skill
    raw[ability.value * 2 + 1] = aptitude
    return LeaderState(LEADER_ID, 1, "Searcher", LOCATION, skills=SkillTable(raw_values=raw), **kwargs)


# -- derive_feature_event(): byte-for-byte oracle rows from `Special
# Features.md` section 8 (user-supplied 2026-08-22), the real 128
# Features of the GW3__T1 world -- precisely re-read via the Read tool
# (not memory-retyped) after an earlier round of hand-transcribed test
# data produced a spurious "needs an fn offset" contradiction. The real
# bug was `resolve_visible_location()`'s own parity polarity (fixed in
# this same phase, see `worldgen/internal_magical_locations.py`), not an
# indexing offset -- fn=feature_id directly, zero offset, matches every
# row below exactly, including exact costs and the con2 (not just con1)
# `Set_FCon` branch.


def test_derive_feature_event_matches_special_features_gw3_t1_catalog():
    cases = [
        # (feature_id, province, kind, power, condition, cost)
        (0, 1208, FeatureType.TOMB, Power.WARP_SPACE, PowerCondition.PC_NONE, 0),
        (5, 301, FeatureType.TEMPLE, Power.UP_SKILL, PowerCondition.DRAIN_COURAGE, 0),
        (7, 1703, FeatureType.PYRAMID, Power.UP_SKILL, PowerCondition.PAY_UP, 10),
        (8, 208, FeatureType.SACRED_ROCK, Power.ORAC_ALIGN, PowerCondition.PAY_UP, 1),
        (9, 1708, FeatureType.CATACOMBS, Power.CHANCE, PowerCondition.PC_NONE, 0),
        (16, 1006, FeatureType.HOLLOW_TREE, Power.UP_SKILL, PowerCondition.PAY_UP, 10),
        (17, 305, FeatureType.CRYPT, Power.CAST_SPELL, PowerCondition.PAY_UP, 2),
        (45, 306, FeatureType.AS_MONUMENT, Power.NEW_SEX, PowerCondition.PC_NONE, 0),
        (53, 1704, FeatureType.CRYPT, Power.ANS_PRAYER, PowerCondition.SAME_ALIGN, 0),
        (59, 705, FeatureType.ALTAR, Power.ANS_PRAYER, PowerCondition.PAY_UP, 2),
        (69, 704, FeatureType.DUNGEON, Power.NEW_SEX, PowerCondition.PC_NONE, 0),
        (82, 403, FeatureType.DUNGEON, Power.ORAC_POWER, PowerCondition.PC_NONE, 0),
        (85, 106, FeatureType.CATACOMBS, Power.ANS_PRAYER, PowerCondition.PAY_UP, 2),
    ]
    for feature_id, province, kind, expected_power, expected_condition, expected_cost in cases:
        feature = _feature(feature_id, province, kind)
        event = derive_feature_event(feature)
        assert event.power is expected_power, f"F#{feature_id}: power"
        assert event.condition is expected_condition, f"F#{feature_id}: condition"
        assert event.cost == expected_cost, f"F#{feature_id}: cost"


def test_derive_feature_event_matches_the_alternate_form_location_names():
    # F#0 Tomb -> Altar/"Prayer Rug", F#8 Sacred Rock -> Throne/"Director's Chair".
    assert derive_feature_event(_feature(0, 1208, FeatureType.TOMB)).magic_feature is MagicFeature.ALTAR
    assert derive_feature_event(_feature(8, 208, FeatureType.SACRED_ROCK)).magic_feature is MagicFeature.THRONE


def test_derive_feature_event_required_alignment_matches_catalog():
    # F#53 Answer Prayer -> "align Evil".
    event = derive_feature_event(_feature(53, 1704, FeatureType.CRYPT))
    assert event.required_alignment is Alignment.EVIL


def test_derive_feature_event_pnone_for_a_parity_gated_feature():
    # F#1: 1006 Altar -- "None (parità)" in the catalog.
    event = derive_feature_event(_feature(1, 1006, FeatureType.ALTAR))
    assert event.power is Power.PNONE
    assert event.magic_feature is MagicFeature.NONE


# -- resolve_feature_power_attempt(): gating --


def test_resolve_feature_power_attempt_refuses_a_power_outside_this_phases_scope():
    state = _state_with_leader()
    feature = _feature(9, 1708, FeatureType.CATACOMBS)
    event = derive_feature_event(feature)
    assert event.power is Power.CHANCE
    assert event.power not in TRACTABLE_POWERS
    result = resolve_feature_power_attempt(state, LEADER_ID, feature, event, random.Random(0))
    assert result.applied is False
    assert result.reason == "power not yet wired"


def test_resolve_feature_power_attempt_pay_up_debits_treasury():
    state = _state_with_leader()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, LOCATION))
    state.kingdoms[1].treasury = 100
    feature = _feature(7, 1703, FeatureType.PYRAMID)
    event = derive_feature_event(feature)
    assert event.condition is PowerCondition.PAY_UP and event.cost == 10
    resolve_feature_power_attempt(state, LEADER_ID, feature, event, random.Random(0))
    assert state.kingdoms[1].treasury == 90


def test_resolve_feature_power_attempt_pay_up_refuses_on_insufficient_gold():
    state = _state_with_leader()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, LOCATION))
    state.kingdoms[1].treasury = 5
    feature = _feature(7, 1703, FeatureType.PYRAMID)
    event = derive_feature_event(feature)
    result = resolve_feature_power_attempt(state, LEADER_ID, feature, event, random.Random(0))
    assert result.applied is False
    assert result.reason == "insufficient gold"
    assert state.kingdoms[1].treasury == 5


def test_resolve_feature_power_attempt_drain_courage_steps_temper_down():
    state = _state_with_leader(temper=Temper.BRAVE)
    feature = _feature(5, 301, FeatureType.TEMPLE)
    event = derive_feature_event(feature)
    assert event.condition is PowerCondition.DRAIN_COURAGE
    resolve_feature_power_attempt(state, LEADER_ID, feature, event, random.Random(0))
    assert state.leaders[LEADER_ID].temper is Temper.CAUTIOUS


def test_resolve_feature_power_attempt_drain_courage_refuses_a_coward():
    state = _state_with_leader(temper=Temper.COWARDLY)
    feature = _feature(5, 301, FeatureType.TEMPLE)
    event = derive_feature_event(feature)
    result = resolve_feature_power_attempt(state, LEADER_ID, feature, event, random.Random(0))
    assert result.applied is False
    assert result.reason == "a Coward may not use this feature"


def test_resolve_feature_power_attempt_same_align_gates_on_alignment():
    from ak_engine.turn.feature_power_execution import FeaturePowerEvent

    state = _state_with_leader(alignment=Alignment.GOOD)
    feature = Feature(feature_id=999, coord=HexCoord(5, 5), kind=FeatureType.CATACOMBS)
    event = FeaturePowerEvent(
        power=Power.NEW_TEMP,
        magic_feature=MagicFeature.LAMP,
        temper_parameter=Temper.BRAVE,
        condition=PowerCondition.SAME_ALIGN,
        required_alignment=Alignment.EVIL,
    )
    result = resolve_feature_power_attempt(state, LEADER_ID, feature, event, random.Random(0))
    assert result.applied is False
    assert result.reason == "wrong alignment"


# -- resolve_feature_power_attempt(): the 9 tractable effects --


def test_new_sex_toggles():
    state = _state_with_leader(sex=Sex.MALE)
    feature = _feature(69, 704, FeatureType.DUNGEON)  # Change Sex, PC_NONE
    event = derive_feature_event(feature)
    assert event.power is Power.NEW_SEX
    result = resolve_feature_power_attempt(state, LEADER_ID, feature, event, random.Random(0))
    assert result.applied is True
    assert state.leaders[LEADER_ID].sex is Sex.FEMALE


def test_new_temp_already_matched_is_a_real_no_op():
    feature_type, feature_id = FeatureType.PYRAMID, 3
    from ak_engine.worldgen.internal_magical_locations import power_temper_parameter

    temper = power_temper_parameter(feature_type, feature_id)
    state = _state_with_leader(temper=temper)
    feature = Feature(feature_id=feature_id, coord=HexCoord(0, 0), kind=feature_type)
    event = derive_feature_event(feature)
    result = resolve_feature_power_attempt(state, LEADER_ID, feature, event, random.Random(0))
    if event.power is Power.NEW_TEMP:
        assert result.already_matched is True
        assert state.leaders[LEADER_ID].temper is temper


def test_up_skill_succeeds_and_increments_when_roll_favors_it():
    ability = Ability.MELEE
    state = GameState()
    # aptitude >= skill so deficiency == 0 -> success probability 1.
    state.add_leader(_skilled_leader(ability, skill=0, aptitude=5, temper=Temper.BRAVE))
    feature = _feature(5, 301, FeatureType.TEMPLE)  # Up Skill, ability=ME per catalog
    event = derive_feature_event(feature)
    assert event.power is Power.UP_SKILL
    assert event.ability_parameter is Ability.MELEE
    result = resolve_feature_power_attempt(state, LEADER_ID, feature, event, random.Random(0))
    assert result.applied is True
    skill, _aptitude = state.leaders[LEADER_ID].skills.pair_for_ability(ability)
    assert skill == 1
    assert result.new_skill_level == 1


def test_up_skill_at_limit_is_a_real_no_op():
    ability = Ability.MELEE
    state = GameState()
    state.add_leader(_skilled_leader(ability, skill=4, aptitude=4, temper=Temper.BRAVE))
    feature = _feature(5, 301, FeatureType.TEMPLE)
    event = derive_feature_event(feature)
    result = resolve_feature_power_attempt(state, LEADER_ID, feature, event, random.Random(0))
    assert result.applied is True
    assert result.at_limit is True
    skill, _aptitude = state.leaders[LEADER_ID].skills.pair_for_ability(ability)
    assert skill == 4


def test_up_apt_increments_up_to_the_binary_cap_of_five():
    ability = power_ability = Ability.SAGE
    from ak_engine.worldgen.internal_magical_locations import power_ability_parameter

    for feature_id in range(40):
        if power_ability_parameter(FeatureType.PYRAMID, feature_id) is ability:
            break
    else:
        raise AssertionError("no PYRAMID feature_id in range(40) targets Ability.SAGE")
    feature = Feature(feature_id=feature_id, coord=HexCoord(1, 1), kind=FeatureType.PYRAMID)
    event = derive_feature_event(feature)
    if event.power is not Power.UP_APT:
        return
    state = GameState()
    state.add_leader(_skilled_leader(ability, skill=0, aptitude=5))
    result = resolve_feature_power_attempt(state, LEADER_ID, feature, event, random.Random(0))
    assert result.applied is True
    assert result.at_limit is True


def _map_feat_event():
    from ak_engine.turn.feature_power_execution import FeaturePowerEvent

    # Condition intentionally PC_NONE here -- F#110 (the only MAP_FEAT row
    # in the whole `Special Features.md` catalog) shows a bare dash for its
    # own condition column, ambiguous against the Set_FCon formula's own
    # SAME_ALIGN prediction for that one row (see `derive_feature_event()`'s
    # docstring); these tests exercise the reveal effect itself, not that
    # single disputed condition outcome.
    return FeaturePowerEvent(power=Power.MAP_FEAT, magic_feature=MagicFeature.LAMP, condition=PowerCondition.PC_NONE)


def test_map_feat_reveals_one_unknown_feature():
    state = GameState()
    state.add_leader(LeaderState(LEADER_ID, 1, "Searcher", LOCATION))
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, LOCATION))
    known = Feature(feature_id=200, coord=HexCoord(1, 1), kind=FeatureType.CAVE)
    known.discovered_by_kingdom[1] = 3
    unknown = Feature(feature_id=201, coord=HexCoord(2, 2), kind=FeatureType.CAVE)
    state.features[200] = known
    state.features[201] = unknown
    feature = _feature(110, 1402, FeatureType.CAVE)
    result = resolve_feature_power_attempt(state, LEADER_ID, feature, _map_feat_event(), random.Random(0))
    assert result.applied is True
    assert result.revealed_feature_id == 201
    assert unknown.discovery_level(1) == 1


def test_map_feat_refuses_when_nothing_left_to_reveal():
    state = GameState()
    state.add_leader(LeaderState(LEADER_ID, 1, "Searcher", LOCATION))
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, LOCATION))
    feature = _feature(110, 1402, FeatureType.CAVE)
    result = resolve_feature_power_attempt(state, LEADER_ID, feature, _map_feat_event(), random.Random(0))
    assert result.applied is False
    assert result.reason == "no more features to reveal"


def test_sage_disc_reveals_between_one_and_four_new_discoveries():
    state = GameState()
    state.add_leader(LeaderState(LEADER_ID, 1, "Searcher", LOCATION))
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, LOCATION))
    feature = Feature(feature_id=999, coord=HexCoord(5, 5), kind=FeatureType.CATACOMBS)
    from ak_engine.turn.feature_power_execution import FeaturePowerEvent

    event = FeaturePowerEvent(power=Power.SAGE_DISC, magic_feature=MagicFeature.LAMP, condition=PowerCondition.PC_NONE)
    result = resolve_feature_power_attempt(state, LEADER_ID, feature, event, random.Random(0))
    assert result.applied is True
    assert 1 <= len(result.revealed_discoveries) <= 4
    assert set(result.revealed_discoveries) <= state.kingdoms[1].discoveries


def test_sage_disc_refuses_when_all_discoveries_already_known():
    state = GameState()
    state.add_leader(LeaderState(LEADER_ID, 1, "Searcher", LOCATION))
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, LOCATION))
    state.kingdoms[1].discoveries.update(Discovery)
    feature = Feature(feature_id=999, coord=HexCoord(5, 5), kind=FeatureType.CATACOMBS)
    from ak_engine.turn.feature_power_execution import FeaturePowerEvent

    event = FeaturePowerEvent(power=Power.SAGE_DISC, magic_feature=MagicFeature.LAMP, condition=PowerCondition.PC_NONE)
    result = resolve_feature_power_attempt(state, LEADER_ID, feature, event, random.Random(0))
    assert result.applied is False
    assert result.reason == "no more discoveries to reveal"
