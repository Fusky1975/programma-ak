from __future__ import annotations

import random

from ak_engine.models.alignment import Alignment
from ak_engine.models.discovery import DISCOVERY_DISPLAY_VALUE, Discovery
from ak_engine.models.enums import Ability, Spell
from ak_engine.models.feature import Feature, FeatureType
from ak_engine.models.game_state import ArmyState, GameState, KingdomState, LeaderState, ProvinceState
from ak_engine.models.kingdom import SkillTable
from ak_engine.models.magic_feature import MagicFeature
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.power import Power, PowerCondition
from ak_engine.models.race import Race
from ak_engine.models.sex import Sex
from ak_engine.models.temper import Temper
from ak_engine.models.army_type import ArmyType
from ak_engine.models.office import Office
from ak_engine.models.treasure import Treasure
from ak_engine.turn.combat import Quality
from ak_engine.turn.feature_power_execution import (
    SA_ARGUMENT_POWERS,
    TERRAIN_SPELL_POWERS,
    TRACTABLE_POWERS,
    FeaturePowerEvent,
    derive_feature_event,
    parse_sa_argument,
    resolve_feature_power_attempt,
)
from _helpers import ScriptedRandom

LOCATION = HexCoord(3, 9)
LEADER_ID = 1


def _draw_for_index(index: int) -> float:
    """The `.random()` value that `int(x * 64)` decodes back to `index`."""

    return (index + 0.5) / 64


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
    resolve_feature_power_attempt(state, LEADER_ID, feature, event, random.Random(0), scout_orders_given=2)
    assert state.kingdoms[1].treasury == 90


def test_resolve_feature_power_attempt_pay_up_refuses_on_insufficient_gold():
    state = _state_with_leader()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, LOCATION))
    state.kingdoms[1].treasury = 5
    feature = _feature(7, 1703, FeatureType.PYRAMID)
    event = derive_feature_event(feature)
    result = resolve_feature_power_attempt(state, LEADER_ID, feature, event, random.Random(0), scout_orders_given=2)
    assert result.applied is False
    assert result.reason == "insufficient gold"
    assert result.condition_refused is PowerCondition.PAY_UP  # Phase 782
    assert state.kingdoms[1].treasury == 5


def test_resolve_feature_power_attempt_drain_courage_steps_temper_down():
    state = _state_with_leader(temper=Temper.BRAVE)
    feature = _feature(5, 301, FeatureType.TEMPLE)
    event = derive_feature_event(feature)
    assert event.condition is PowerCondition.DRAIN_COURAGE
    resolve_feature_power_attempt(state, LEADER_ID, feature, event, random.Random(0), scout_orders_given=2)
    assert state.leaders[LEADER_ID].temper is Temper.CAUTIOUS


def test_resolve_feature_power_attempt_drain_courage_refuses_a_coward():
    state = _state_with_leader(temper=Temper.COWARDLY)
    feature = _feature(5, 301, FeatureType.TEMPLE)
    event = derive_feature_event(feature)
    result = resolve_feature_power_attempt(state, LEADER_ID, feature, event, random.Random(0), scout_orders_given=2)
    assert result.applied is False
    assert result.reason == "a Coward may not use this feature"
    assert result.condition_refused is PowerCondition.DRAIN_COURAGE  # Phase 782


# -- Phase 688: the two-Scout-orders consent gate (PCOND.X2) --


def test_apply_condition_gate_pay_up_refuses_without_two_scout_orders():
    state = _state_with_leader()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, LOCATION))
    state.kingdoms[1].treasury = 100
    feature = Feature(feature_id=999, coord=HexCoord(5, 5), kind=FeatureType.CATACOMBS)
    event = FeaturePowerEvent(
        power=Power.NEW_TEMP, magic_feature=MagicFeature.LAMP, condition=PowerCondition.PAY_UP, cost=10
    )
    for scout_orders_given in (0, 1):
        result = resolve_feature_power_attempt(
            state, LEADER_ID, feature, event, random.Random(0), scout_orders_given=scout_orders_given
        )
        assert result.applied is False
        assert result.reason == "needs two Scout orders to accept these terms"
    assert state.kingdoms[1].treasury == 100  # refused -- no partial cost applied


def test_apply_condition_gate_drain_courage_refuses_without_two_scout_orders():
    state = _state_with_leader(temper=Temper.BRAVE)
    feature = Feature(feature_id=999, coord=HexCoord(5, 5), kind=FeatureType.CATACOMBS)
    event = FeaturePowerEvent(
        power=Power.NEW_TEMP, magic_feature=MagicFeature.LAMP, condition=PowerCondition.DRAIN_COURAGE, cost=0
    )
    result = resolve_feature_power_attempt(state, LEADER_ID, feature, event, random.Random(0), scout_orders_given=1)
    assert result.applied is False
    assert result.reason == "needs two Scout orders to accept these terms"
    assert state.leaders[LEADER_ID].temper is Temper.BRAVE  # refused -- no partial cost applied


def test_apply_condition_gate_drain_skill_refuses_without_two_scout_orders():
    state = _state_with_leader(skills=_skilled_leader(Ability.MELEE, 3, 9).skills)
    feature = Feature(feature_id=999, coord=HexCoord(5, 5), kind=FeatureType.CATACOMBS)
    event = FeaturePowerEvent(
        power=Power.UP_SKILL,
        magic_feature=MagicFeature.LAMP,
        ability_parameter=Ability.MELEE,
        condition=PowerCondition.DRAIN_SKILL,
        cost=1,
    )
    result = resolve_feature_power_attempt(state, LEADER_ID, feature, event, random.Random(0), scout_orders_given=0)
    assert result.applied is False
    assert result.reason == "needs two Scout orders to accept these terms"
    skill, _aptitude = state.leaders[LEADER_ID].skills.pair_for_ability(Ability.MELEE)
    assert skill == 3  # refused -- no partial drain applied


def test_apply_condition_gate_drain_skill_succeeds_with_two_scout_orders():
    # Phase 688: DRAIN_SKILL had zero dedicated tests anywhere before this
    # phase -- the one branch in _apply_condition_gate() with real
    # internal looping/rng logic (skill-candidate selection). Uses
    # NEW_SEX (unrelated to skills) so the drain itself isn't confounded
    # by UP_SKILL's own separate, possibly-skill-increasing effect.
    state = _state_with_leader(skills=_skilled_leader(Ability.MELEE, 3, 9).skills, sex=Sex.MALE)
    feature = Feature(feature_id=999, coord=HexCoord(5, 5), kind=FeatureType.CATACOMBS)
    event = FeaturePowerEvent(
        power=Power.NEW_SEX, magic_feature=MagicFeature.LAMP, condition=PowerCondition.DRAIN_SKILL, cost=1
    )
    result = resolve_feature_power_attempt(state, LEADER_ID, feature, event, random.Random(0), scout_orders_given=2)
    assert result.reason != "needs two Scout orders to accept these terms"
    assert result.reason != "insufficient skill levels"
    assert result.applied is True
    skill, _aptitude = state.leaders[LEADER_ID].skills.pair_for_ability(Ability.MELEE)
    assert skill == 2  # the only ability with any skill to drain


def test_apply_condition_gate_pay_up_succeeds_with_more_than_two_scout_orders():
    # Proves ">= 2", not "== 2".
    state = _state_with_leader()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, LOCATION))
    state.kingdoms[1].treasury = 100
    feature = Feature(feature_id=999, coord=HexCoord(5, 5), kind=FeatureType.CATACOMBS)
    event = FeaturePowerEvent(
        power=Power.NEW_TEMP, magic_feature=MagicFeature.LAMP, condition=PowerCondition.PAY_UP, cost=10
    )
    result = resolve_feature_power_attempt(state, LEADER_ID, feature, event, random.Random(0), scout_orders_given=3)
    assert result.reason != "needs two Scout orders to accept these terms"
    assert state.kingdoms[1].treasury == 90


def test_apply_condition_gate_scout_orders_never_affect_unrelated_conditions():
    # NEED_KING/SAME_ALIGN/G_TURN/PC_NONE are untouched by this gate --
    # only PAY_UP/DRAIN_SKILL/DRAIN_COURAGE need consent.
    state = _state_with_leader(alignment=Alignment.GOOD, is_king=True)
    feature = Feature(feature_id=999, coord=HexCoord(5, 5), kind=FeatureType.CATACOMBS)
    for condition, kwargs in (
        (PowerCondition.NEED_KING, {}),
        (PowerCondition.SAME_ALIGN, {"required_alignment": Alignment.GOOD}),
        (PowerCondition.PC_NONE, {}),
    ):
        event = FeaturePowerEvent(power=Power.NEW_TEMP, magic_feature=MagicFeature.LAMP, condition=condition, **kwargs)
        result = resolve_feature_power_attempt(state, LEADER_ID, feature, event, random.Random(0), scout_orders_given=0)
        assert result.reason != "needs two Scout orders to accept these terms"


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
    assert result.condition_refused is PowerCondition.SAME_ALIGN  # Phase 782


def test_resolve_feature_power_attempt_need_king_refuses_a_non_king():
    from ak_engine.turn.feature_power_execution import FeaturePowerEvent

    state = _state_with_leader(is_king=False)
    feature = Feature(feature_id=999, coord=HexCoord(5, 5), kind=FeatureType.CATACOMBS)
    event = FeaturePowerEvent(power=Power.NEW_TEMP, magic_feature=MagicFeature.LAMP, condition=PowerCondition.NEED_KING)
    result = resolve_feature_power_attempt(state, LEADER_ID, feature, event, random.Random(0))
    assert result.applied is False
    assert result.reason == "only a King may use this power"
    assert result.condition_refused is PowerCondition.NEED_KING


def test_resolve_feature_power_attempt_g_turn_refuses_a_repeat_use_the_same_turn():
    from ak_engine.turn.feature_power_execution import FeaturePowerEvent

    state = _state_with_leader()
    feature = Feature(feature_id=999, coord=HexCoord(5, 5), kind=FeatureType.CATACOMBS, power_used_turn=state.turn_number)
    event = FeaturePowerEvent(power=Power.NEW_TEMP, magic_feature=MagicFeature.LAMP, condition=PowerCondition.G_TURN)
    result = resolve_feature_power_attempt(state, LEADER_ID, feature, event, random.Random(0))
    assert result.applied is False
    assert result.reason == "already used this gameturn"
    assert result.condition_refused is PowerCondition.G_TURN


def test_resolve_feature_power_attempt_drain_skill_refuses_with_insufficient_skill_levels():
    from ak_engine.turn.feature_power_execution import FeaturePowerEvent

    state = _state_with_leader(skills=None)  # no skill data recorded at all
    feature = Feature(feature_id=999, coord=HexCoord(5, 5), kind=FeatureType.CATACOMBS)
    event = FeaturePowerEvent(power=Power.NEW_SEX, magic_feature=MagicFeature.LAMP, condition=PowerCondition.DRAIN_SKILL, cost=1)
    result = resolve_feature_power_attempt(state, LEADER_ID, feature, event, random.Random(0), scout_orders_given=2)
    assert result.applied is False
    assert result.reason == "insufficient skill levels"
    assert result.condition_refused is PowerCondition.DRAIN_SKILL


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
    result = resolve_feature_power_attempt(state, LEADER_ID, feature, event, random.Random(0), scout_orders_given=2)
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
    result = resolve_feature_power_attempt(state, LEADER_ID, feature, event, random.Random(0), scout_orders_given=2)
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


def _sage_disc_state(known: set[Discovery]) -> GameState:
    state = GameState()
    state.add_leader(LeaderState(LEADER_ID, 1, "Searcher", LOCATION))
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, LOCATION))
    state.kingdoms[1].discoveries.update(known)
    return state


def _sage_disc_feature() -> Feature:
    return Feature(feature_id=999, coord=HexCoord(5, 5), kind=FeatureType.CATACOMBS)


def _sage_disc_event():
    from ak_engine.turn.feature_power_execution import FeaturePowerEvent

    return FeaturePowerEvent(power=Power.SAGE_DISC, magic_feature=MagicFeature.LAMP, condition=PowerCondition.PC_NONE)


def test_sage_disc_grants_exactly_one_discovery_the_single_lowest_discval_seen():
    # rounds=1 (first draw < 0.25); 99 draws of an already-known
    # candidate (LAND_SHIP, index 0), 1 draw of the real, unknown,
    # lowest-discval candidate in the sample (HIEROGLYPHIC_TRANSLATION,
    # discval=1). Every other Discovery is pre-known so it can never be
    # accidentally drawn as a lower-discval competitor.
    known = {d for d in Discovery if d is not Discovery.HIEROGLYPHIC_TRANSLATION}
    state = _sage_disc_state(known)
    draws = [0.1] + [_draw_for_index(Discovery.LAND_SHIP.value)] * 100
    draws[50] = _draw_for_index(Discovery.HIEROGLYPHIC_TRANSLATION.value)
    result = resolve_feature_power_attempt(state, LEADER_ID, _sage_disc_feature(), _sage_disc_event(), ScriptedRandom(draws))
    assert result.applied is True
    assert result.revealed_discoveries == (Discovery.HIEROGLYPHIC_TRANSLATION,)
    assert state.kingdoms[1].discoveries == known | {Discovery.HIEROGLYPHIC_TRANSLATION}


def test_sage_disc_keeps_the_running_minimum_within_one_round():
    # Two unknown candidates land in the SAME round: COMPOSITE_BOW
    # (discval=3) first, then the lower HIEROGLYPHIC_TRANSLATION
    # (discval=1) later -- the later, lower-discval draw must win,
    # proving a running minimum, not "first found."
    assert DISCOVERY_DISPLAY_VALUE[Discovery.HIEROGLYPHIC_TRANSLATION] < DISCOVERY_DISPLAY_VALUE[Discovery.COMPOSITE_BOW]
    known = {d for d in Discovery if d not in (Discovery.COMPOSITE_BOW, Discovery.HIEROGLYPHIC_TRANSLATION)}
    state = _sage_disc_state(known)
    draws = [0.1] + [_draw_for_index(Discovery.LAND_SHIP.value)] * 100
    draws[10] = _draw_for_index(Discovery.COMPOSITE_BOW.value)
    draws[60] = _draw_for_index(Discovery.HIEROGLYPHIC_TRANSLATION.value)
    result = resolve_feature_power_attempt(state, LEADER_ID, _sage_disc_feature(), _sage_disc_event(), ScriptedRandom(draws))
    assert result.applied is True
    assert result.revealed_discoveries == (Discovery.HIEROGLYPHIC_TRANSLATION,)


def test_sage_disc_best_value_persists_across_rounds():
    # rounds=2 (first draw in [0.25, 0.5)); round 1's own best
    # (COMPOSITE_BOW, discval=3) must still be beaten by round 2's own
    # better candidate (HIEROGLYPHIC_TRANSLATION, discval=1), proving
    # `best_value` is initialized once, outside the round loop.
    known = {d for d in Discovery if d not in (Discovery.COMPOSITE_BOW, Discovery.HIEROGLYPHIC_TRANSLATION)}
    state = _sage_disc_state(known)
    filler = _draw_for_index(Discovery.LAND_SHIP.value)
    round1 = [filler] * 100
    round1[5] = _draw_for_index(Discovery.COMPOSITE_BOW.value)
    round2 = [filler] * 100
    round2[5] = _draw_for_index(Discovery.HIEROGLYPHIC_TRANSLATION.value)
    draws = [0.3] + round1 + round2
    result = resolve_feature_power_attempt(state, LEADER_ID, _sage_disc_feature(), _sage_disc_event(), ScriptedRandom(draws))
    assert result.applied is True
    assert result.revealed_discoveries == (Discovery.HIEROGLYPHIC_TRANSLATION,)


def test_sage_disc_already_known_candidate_is_skipped_not_a_stop():
    # An already-known candidate drawn first must NOT halt the sample --
    # a later, real, unknown candidate still gets found and granted.
    known = {d for d in Discovery if d is not Discovery.HIEROGLYPHIC_TRANSLATION}
    state = _sage_disc_state(known)
    draws = [0.1] + [_draw_for_index(Discovery.LAND_SHIP.value)] * 100  # LAND_SHIP is already known throughout
    draws[99] = _draw_for_index(Discovery.HIEROGLYPHIC_TRANSLATION.value)
    result = resolve_feature_power_attempt(state, LEADER_ID, _sage_disc_feature(), _sage_disc_event(), ScriptedRandom(draws))
    assert result.applied is True
    assert result.revealed_discoveries == (Discovery.HIEROGLYPHIC_TRANSLATION,)


def test_sage_disc_refuses_with_zero_draws_when_everything_is_already_known():
    state = _sage_disc_state(set(Discovery))
    result = resolve_feature_power_attempt(state, LEADER_ID, _sage_disc_feature(), _sage_disc_event(), ScriptedRandom([]))
    assert result.applied is False
    assert result.reason == "no more discoveries to reveal"


def test_sage_disc_exhausted_when_the_whole_sample_misses_the_one_real_candidate():
    # Only SEXTANT is unknown; rounds=1, and every one of the 100 draws
    # lands on the already-known LAND_SHIP -- the sample never finds
    # the one real candidate, matching the real, low-probability
    # "bad luck across the whole sample" exhaustion fallthrough.
    known = {d for d in Discovery if d is not Discovery.SEXTANT}
    state = _sage_disc_state(known)
    draws = [0.1] + [_draw_for_index(Discovery.LAND_SHIP.value)] * 100
    result = resolve_feature_power_attempt(state, LEADER_ID, _sage_disc_feature(), _sage_disc_event(), ScriptedRandom(draws))
    assert result.applied is False
    assert result.reason == "no more discoveries to reveal"
    assert Discovery.SEXTANT not in state.kingdoms[1].discoveries


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


# -- Phase 619: parse_sa_argument() --


def test_parse_sa_argument_bare_number():
    assert parse_sa_argument("1") == 1
    assert parse_sa_argument("  42  ") == 42


def test_parse_sa_argument_full_sentence():
    assert parse_sa_argument("Tell me about character 1.") == 1
    assert parse_sa_argument("SA Recharge item 12.") == 12


def test_parse_sa_argument_no_digits_returns_none():
    assert parse_sa_argument("Take that!") is None
    assert parse_sa_argument("") is None


# -- Phase 619: the 8 SA-argument powers --


def _sa_event(power: Power) -> FeaturePowerEvent:
    return FeaturePowerEvent(power=power, magic_feature=MagicFeature.LAMP, condition=PowerCondition.PC_NONE)


def test_orac_align_success():
    state = GameState()
    state.add_leader(LeaderState(LEADER_ID, 1, "Searcher", LOCATION))
    state.add_leader(LeaderState(2, 1, "Sir Roland", LOCATION, alignment=Alignment.GOOD))
    result = resolve_feature_power_attempt(
        state, LEADER_ID, Feature(feature_id=1, coord=LOCATION, kind=FeatureType.PYRAMID),
        _sa_event(Power.ORAC_ALIGN), random.Random(0), sa_argument=2,
    )
    assert result.applied is True
    assert result.oracle_target_leader_id == 2
    assert result.oracle_alignment is Alignment.GOOD


def test_orac_align_invalid_target():
    state = _state_with_leader()
    result = resolve_feature_power_attempt(
        state, LEADER_ID, Feature(feature_id=1, coord=LOCATION, kind=FeatureType.PYRAMID),
        _sa_event(Power.ORAC_ALIGN), random.Random(0), sa_argument=999,
    )
    assert result.applied is False
    assert result.reason == "invalid target"


def test_orac_power_reveals_commanded_armies():
    state = GameState()
    state.add_leader(LeaderState(LEADER_ID, 1, "Searcher", LOCATION))
    state.add_leader(LeaderState(2, 1, "General", LOCATION))
    state.add_army(
        ArmyState(army_id=1, kingdom_id=1, army_type=ArmyType.BOWMEN, quality=Quality.AVERAGE, location=LOCATION, commanded_by=2)
    )
    result = resolve_feature_power_attempt(
        state, LEADER_ID, Feature(feature_id=1, coord=LOCATION, kind=FeatureType.PYRAMID),
        _sa_event(Power.ORAC_POWER), random.Random(0), sa_argument=2,
    )
    assert result.applied is True
    assert len(result.oracle_armies) == 1
    assert result.oracle_armies[0].army_type is ArmyType.BOWMEN


def test_orac_power_no_armies_is_a_real_answer_not_a_failure():
    state = _state_with_leader()
    state.add_leader(LeaderState(2, 1, "Hermit", LOCATION))
    result = resolve_feature_power_attempt(
        state, LEADER_ID, Feature(feature_id=1, coord=LOCATION, kind=FeatureType.PYRAMID),
        _sa_event(Power.ORAC_POWER), random.Random(0), sa_argument=2,
    )
    assert result.applied is True
    assert result.oracle_armies == ()


def test_orac_office_reveals_the_holder():
    state = GameState()
    state.add_leader(LeaderState(LEADER_ID, 1, "Searcher", LOCATION))
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, LOCATION))
    king = LeaderState(2, 1, "King Testerman", LOCATION, is_king=True)
    state.add_leader(king)
    state.emperor_kingdom_id = 1
    result = resolve_feature_power_attempt(
        state, LEADER_ID, Feature(feature_id=1, coord=LOCATION, kind=FeatureType.PYRAMID),
        _sa_event(Power.ORAC_OFFICE), random.Random(0), sa_argument=Office.EMPEROR.value,
    )
    assert result.applied is True
    assert result.oracle_office is Office.EMPEROR
    assert result.oracle_office_holder_leader_id == 2


def test_orac_office_vacant_is_a_real_answer_not_a_failure():
    state = _state_with_leader()
    result = resolve_feature_power_attempt(
        state, LEADER_ID, Feature(feature_id=1, coord=LOCATION, kind=FeatureType.PYRAMID),
        _sa_event(Power.ORAC_OFFICE), random.Random(0), sa_argument=Office.EMPEROR.value,
    )
    assert result.applied is True
    assert result.oracle_office_holder_leader_id is None


def test_orac_office_out_of_range_is_invalid():
    state = _state_with_leader()
    result = resolve_feature_power_attempt(
        state, LEADER_ID, Feature(feature_id=1, coord=LOCATION, kind=FeatureType.PYRAMID),
        _sa_event(Power.ORAC_OFFICE), random.Random(0), sa_argument=99,
    )
    assert result.applied is False
    assert result.reason == "invalid target"


def test_orac_gold_reveals_a_kings_treasury():
    state = GameState()
    state.add_leader(LeaderState(LEADER_ID, 1, "Searcher", LOCATION))
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, LOCATION, treasury=250))
    state.add_leader(LeaderState(2, 1, "King Testerman", LOCATION, is_king=True))
    result = resolve_feature_power_attempt(
        state, LEADER_ID, Feature(feature_id=1, coord=LOCATION, kind=FeatureType.PYRAMID),
        _sa_event(Power.ORAC_GOLD), random.Random(0), sa_argument=2,
    )
    assert result.applied is True
    assert result.oracle_treasury == 250


def test_orac_gold_refuses_a_non_king_target():
    state = _state_with_leader()
    state.add_leader(LeaderState(2, 1, "Sir Roland", LOCATION))
    result = resolve_feature_power_attempt(
        state, LEADER_ID, Feature(feature_id=1, coord=LOCATION, kind=FeatureType.PYRAMID),
        _sa_event(Power.ORAC_GOLD), random.Random(0), sa_argument=2,
    )
    assert result.applied is False
    assert result.reason == "not a King"
    assert result.oracle_target_leader_id == 2


def test_orac_treas_reveals_the_hidden_treasure():
    state = _state_with_leader()
    target_feature = Feature(feature_id=42, coord=HexCoord(5, 5), kind=FeatureType.PYRAMID, treasure=Treasure.GOLD_HOARD_LARGE)
    state.features[42] = target_feature
    result = resolve_feature_power_attempt(
        state, LEADER_ID, Feature(feature_id=1, coord=LOCATION, kind=FeatureType.PYRAMID),
        _sa_event(Power.ORAC_TREAS), random.Random(0), sa_argument=42,
    )
    assert result.applied is True
    assert result.oracle_treasure is Treasure.GOLD_HOARD_LARGE


def test_orac_treas_invalid_feature():
    state = _state_with_leader()
    result = resolve_feature_power_attempt(
        state, LEADER_ID, Feature(feature_id=1, coord=LOCATION, kind=FeatureType.PYRAMID),
        _sa_event(Power.ORAC_TREAS), random.Random(0), sa_argument=999,
    )
    assert result.applied is False
    assert result.reason == "invalid target"


def test_recharge_success_increments_charges():
    state = _state_with_leader()
    item = state.add_item(Treasure.WAND_RESURRECTION, owner_leader_id=LEADER_ID, charges=2)
    result = resolve_feature_power_attempt(
        state, LEADER_ID, Feature(feature_id=1, coord=LOCATION, kind=FeatureType.PYRAMID),
        _sa_event(Power.RECHARGE), random.Random(0), sa_argument=item.item_id,
    )
    assert result.applied is True
    assert item.charges == 3
    assert result.recharged_item_id == item.item_id


def test_recharge_refuses_an_item_not_owned_by_the_scouting_character():
    state = _state_with_leader()
    item = state.add_item(Treasure.WAND_RESURRECTION, owner_leader_id=999, charges=2)
    result = resolve_feature_power_attempt(
        state, LEADER_ID, Feature(feature_id=1, coord=LOCATION, kind=FeatureType.PYRAMID),
        _sa_event(Power.RECHARGE), random.Random(0), sa_argument=item.item_id,
    )
    assert result.applied is False
    assert result.reason == "item not owned"
    assert item.charges == 2


def test_recharge_refuses_a_non_spell_casting_item():
    state = _state_with_leader()
    item = state.add_item(Treasure.GOLD_HOARD_LARGE, owner_leader_id=LEADER_ID, charges=0)
    result = resolve_feature_power_attempt(
        state, LEADER_ID, Feature(feature_id=1, coord=LOCATION, kind=FeatureType.PYRAMID),
        _sa_event(Power.RECHARGE), random.Random(0), sa_argument=item.item_id,
    )
    assert result.applied is False
    assert result.reason == "not a spell-casting item"


def test_grant_wish_success_raises_skill_by_one():
    state = GameState()
    state.add_leader(_skilled_leader(Ability.MELEE, skill=1, aptitude=3))
    result = resolve_feature_power_attempt(
        state, LEADER_ID, Feature(feature_id=1, coord=LOCATION, kind=FeatureType.PYRAMID),
        _sa_event(Power.GRANT_WISH), random.Random(0), sa_argument=Ability.MELEE.value,
    )
    assert result.applied is True
    assert result.new_skill_level == 2
    skill, _aptitude = state.leaders[LEADER_ID].skills.pair_for_ability(Ability.MELEE)
    assert skill == 2


def test_grant_wish_refuses_when_skill_already_at_aptitude():
    state = GameState()
    state.add_leader(_skilled_leader(Ability.MELEE, skill=3, aptitude=3))
    result = resolve_feature_power_attempt(
        state, LEADER_ID, Feature(feature_id=1, coord=LOCATION, kind=FeatureType.PYRAMID),
        _sa_event(Power.GRANT_WISH), random.Random(0), sa_argument=Ability.MELEE.value,
    )
    assert result.applied is True
    assert result.at_limit is True


def test_gamble_win_or_loss_moves_the_treasury_consistently():
    state = _state_with_leader()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, LOCATION, treasury=100))
    result = resolve_feature_power_attempt(
        state, LEADER_ID, Feature(feature_id=1, coord=LOCATION, kind=FeatureType.PYRAMID),
        _sa_event(Power.GAMBLE), random.Random(1), sa_argument=10,
    )
    assert result.applied is True
    assert result.gamble_amount == 10
    if result.gamble_won:
        assert state.kingdoms[1].treasury == 110
    else:
        assert state.kingdoms[1].treasury == 90


def test_gamble_tie_is_a_loss():
    # rng.randint(1,6) via ScriptedRandom-free direct seeding is awkward
    # for forcing an exact tie, so this checks the documented rule
    # directly instead: a tie must never be treated as a win.
    state = _state_with_leader()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, LOCATION, treasury=100))
    for seed in range(30):
        result = resolve_feature_power_attempt(
            state, LEADER_ID, Feature(feature_id=1, coord=LOCATION, kind=FeatureType.PYRAMID),
            _sa_event(Power.GAMBLE), random.Random(seed), sa_argument=1,
        )
        if result.gamble_character_roll == result.gamble_house_roll:
            assert result.gamble_won is False
            return
    raise AssertionError("no tie rolled across 30 seeds -- widen the seed range")


def test_gamble_refuses_on_insufficient_treasury():
    state = _state_with_leader()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, LOCATION, treasury=5))
    result = resolve_feature_power_attempt(
        state, LEADER_ID, Feature(feature_id=1, coord=LOCATION, kind=FeatureType.PYRAMID),
        _sa_event(Power.GAMBLE), random.Random(0), sa_argument=1000,
    )
    assert result.applied is False
    assert result.reason == "insufficient gold"
    assert state.kingdoms[1].treasury == 5


def test_sa_argument_powers_refuse_cleanly_with_no_sa_argument_given():
    state = _state_with_leader()
    result = resolve_feature_power_attempt(
        state, LEADER_ID, Feature(feature_id=1, coord=LOCATION, kind=FeatureType.PYRAMID),
        _sa_event(Power.ORAC_ALIGN), random.Random(0), sa_argument=None,
    )
    assert result.applied is False
    assert result.reason == "no SA argument given"


def test_sa_argument_powers_set_membership():
    assert SA_ARGUMENT_POWERS == {
        Power.ORAC_ALIGN,
        Power.ORAC_POWER,
        Power.ORAC_OFFICE,
        Power.ORAC_GOLD,
        Power.ORAC_TREAS,
        Power.RECHARGE,
        Power.GRANT_WISH,
        Power.GAMBLE,
    }
    assert SA_ARGUMENT_POWERS.isdisjoint(TRACTABLE_POWERS)


# -- Phase 620: CAST_SPELL/ANS_PRAYER's Part_Sea/Flood/Earthquake subset --


def test_derive_feature_event_cast_spell_without_state_leaves_spell_parameter_none():
    # F#7 Tomb at x=3 -> Cast Spell / Flood, but no `state` means the
    # terrain can't be resolved at all.
    feature = _feature(7, 307, FeatureType.TOMB)
    event = derive_feature_event(feature)
    assert event.power is Power.CAST_SPELL
    assert event.spell_parameter is None


def test_derive_feature_event_cast_spell_with_unknown_province_leaves_spell_parameter_none():
    feature = _feature(7, 307, FeatureType.TOMB)
    state = GameState()
    event = derive_feature_event(feature, state=state)
    assert event.spell_parameter is None


def test_derive_feature_event_cast_spell_resolves_the_terrain_spell_with_state():
    feature = _feature(7, 307, FeatureType.TOMB)
    state = GameState()
    state.provinces[feature.coord] = ProvinceState(coord=feature.coord, terrain=Terrain.SEA, race=Race.HUMAN)
    event = derive_feature_event(feature, state=state)
    assert event.spell_parameter is Spell.FLOOD


def _terrain_spell_event(spell: Spell) -> FeaturePowerEvent:
    return FeaturePowerEvent(
        power=Power.CAST_SPELL, magic_feature=MagicFeature.CRYSTAL_BALL, condition=PowerCondition.PC_NONE, spell_parameter=spell
    )


def test_resolve_feature_power_attempt_terrain_spell_success():
    state = _state_with_leader()
    feature = Feature(feature_id=1, coord=LOCATION, kind=FeatureType.PYRAMID)
    state.add_feature(feature)
    state.provinces[LOCATION] = ProvinceState(coord=LOCATION, terrain=Terrain.SEA, race=Race.HUMAN)

    result = resolve_feature_power_attempt(state, LEADER_ID, feature, _terrain_spell_event(Spell.PART_SEA), random.Random(0))

    assert result.applied is True
    assert result.cast_spell is Spell.PART_SEA
    assert state.provinces[LOCATION].effective_terrain() is Terrain.PLAINS


def test_resolve_feature_power_attempt_terrain_spell_cast_time_mismatch_fails():
    # Part_Sea passes the derivation-time "not Mountains" filter on
    # Plains, but its own real cast-time precondition needs Sea
    # specifically -- a real, sourced applied=False, not a bug.
    state = _state_with_leader()
    feature = Feature(feature_id=1, coord=LOCATION, kind=FeatureType.PYRAMID)
    state.add_feature(feature)
    state.provinces[LOCATION] = ProvinceState(coord=LOCATION, terrain=Terrain.PLAINS, race=Race.HUMAN)

    result = resolve_feature_power_attempt(state, LEADER_ID, feature, _terrain_spell_event(Spell.PART_SEA), random.Random(0))

    assert result.applied is False
    assert state.provinces[LOCATION].effective_terrain() is Terrain.PLAINS


def test_resolve_feature_power_attempt_terrain_spell_unresolved_is_power_not_wired():
    state = _state_with_leader()
    feature = Feature(feature_id=1, coord=LOCATION, kind=FeatureType.PYRAMID)
    state.add_feature(feature)
    event = FeaturePowerEvent(power=Power.CAST_SPELL, magic_feature=MagicFeature.CRYSTAL_BALL, spell_parameter=None)

    result = resolve_feature_power_attempt(state, LEADER_ID, feature, event, random.Random(0))

    assert result.applied is False
    assert result.reason == "power not yet wired"


def test_terrain_spell_powers_set_membership():
    assert TERRAIN_SPELL_POWERS == {Power.CAST_SPELL, Power.ANS_PRAYER}
    assert TERRAIN_SPELL_POWERS.isdisjoint(TRACTABLE_POWERS)
    assert TERRAIN_SPELL_POWERS.isdisjoint(SA_ARGUMENT_POWERS)


# -- Phase 621: CAST_SPELL/ANS_PRAYER's full Set_Spell (13 real
# candidates, not just Part_Sea/Flood/Earthquake) -- and the target-
# resolution fix (province- vs. character- vs. no-target spells), all
# real `(feature_id, FeatureType)` combos confirmed via a standalone
# script directly against `resolve_spell_candidate()` at province x=3
# (matching this file's own `LOCATION`), not hand-traced.


def test_derive_feature_event_default_miscwrit_resolves_a_non_territory_spell():
    # F#13/PYRAMID at x=3 -> Oratory, only resolvable now that
    # `GameState.miscwrit` defaults to its real sourced value (2).
    feature = _feature(13, 309, FeatureType.PYRAMID)
    state = GameState()
    state.provinces[feature.coord] = ProvinceState(coord=feature.coord, terrain=Terrain.PLAINS, race=Race.HUMAN)
    event = derive_feature_event(feature, state=state)
    assert event.power is Power.CAST_SPELL
    assert event.spell_parameter is Spell.ORATORY


def test_resolve_feature_power_attempt_character_target_spell_self_casts():
    # Oratory is character-targeted (`cast_decode.py
    # CHARACTER_TARGET_SPELLS`) -- the scouting leader is a real,
    # rulebook-sanctioned target ("cast on yourself"), not a guess.
    state = _state_with_leader()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, LOCATION))
    feature = Feature(feature_id=13, coord=LOCATION, kind=FeatureType.PYRAMID)
    state.add_feature(feature)
    state.add_army(ArmyState(army_id=1, kingdom_id=1, army_type=ArmyType.BOWMEN, quality=Quality.AVERAGE, location=LOCATION, commanded_by=LEADER_ID))

    result = resolve_feature_power_attempt(state, LEADER_ID, feature, _terrain_spell_event(Spell.ORATORY), random.Random(0))

    assert result.applied is True
    assert result.cast_spell is Spell.ORATORY
    assert state.armies[1].quality is Quality.VETERAN


def test_resolve_feature_power_attempt_no_target_spell_uses_zero_target():
    # Skeletal_Army is no-target (`cast_decode.py NO_TARGET_SPELLS`) --
    # target=0, operates on the caster's own province. No graveyard
    # entries here, so it fails on its own real precondition (not a
    # targeting crash), proving target=0 reaches `execute_cast()`
    # cleanly rather than being mistaken for a province/character id.
    state = _state_with_leader()
    feature = Feature(feature_id=3, coord=LOCATION, kind=FeatureType.PYRAMID)
    state.add_feature(feature)

    result = resolve_feature_power_attempt(state, LEADER_ID, feature, _terrain_spell_event(Spell.SKELETAL_ARMY), random.Random(0))

    assert result.applied is False
    assert result.reason == "no dead units in this province to raise"
    assert result.cast_spell is Spell.SKELETAL_ARMY


def test_resolve_feature_power_attempt_kill_enemy_refuses_cleanly():
    # Kill_Enemy needs a specific, player-chosen enemy per rulebook
    # [4.25.2] -- no sensible automatic target exists in this
    # automatic-cast context, so it's refused honestly rather than
    # self-targeting it (never a valid use) or inventing an enemy.
    state = _state_with_leader()
    feature = Feature(feature_id=5, coord=LOCATION, kind=FeatureType.PYRAMID)
    state.add_feature(feature)

    result = resolve_feature_power_attempt(state, LEADER_ID, feature, _terrain_spell_event(Spell.KILL_ENEMY), random.Random(0))

    assert result.applied is False
    assert result.reason == "no automatic target for Kill_Enemy"
    assert result.cast_spell is Spell.KILL_ENEMY


# -- Phase 622: Power.CHANCE's own full sub-power resolution ("gdday.md",
# user-supplied 2026-08-22). F#9/Catacombs is the same real Chance
# Feature the byte-for-byte oracle test above already uses (province
# 1708 -- see that test's own `Power.CHANCE`/`PC_NONE`/`0` row), also
# independently confirmed by gdday.md section 9.3 as one of GW3__T1's
# own 3 real Chance Features -- modval = 9 + FeatureType.CATACOMBS.value
# (2) = 11, so UpSkill/DnSkill target Ability.THIEF (11 MOD 15) and
# NewTemp targets Temper.BERSERK ((11 MOD 3)+1), both directly computed
# from the already-confirmed power_ability_parameter()/power_temper_
# parameter() formulas, not independently re-derived here.


def test_derive_feature_event_chance_resolves_up_skill_parameters():
    # gameturn=1, gdday=10 -> residue 3 -> UpSkill (gdday.md section 9.1).
    feature = _feature(9, 1708, FeatureType.CATACOMBS)
    state = GameState(turn_number=1, gdday=10)
    event = derive_feature_event(feature, state=state)
    assert event.power is Power.CHANCE
    assert event.chance_sub_power is Power.UP_SKILL
    assert event.ability_parameter is Ability.THIEF


def test_derive_feature_event_chance_resolves_new_temp_parameters():
    # gameturn=6, gdday=27 -> residue 1 -> NewTemp (gdday.md section 11.3).
    feature = _feature(9, 1708, FeatureType.CATACOMBS)
    state = GameState(turn_number=6, gdday=27)
    event = derive_feature_event(feature, state=state)
    assert event.chance_sub_power is Power.NEW_TEMP
    assert event.temper_parameter is Temper.BERSERK


def test_derive_feature_event_chance_without_state_leaves_chance_sub_power_none():
    feature = _feature(9, 1708, FeatureType.CATACOMBS)
    event = derive_feature_event(feature)
    assert event.power is Power.CHANCE
    assert event.chance_sub_power is None


def _chance_event(sub_power: Power, **kwargs) -> FeaturePowerEvent:
    return FeaturePowerEvent(
        power=Power.CHANCE, magic_feature=MagicFeature.ROULETTE_WHEEL, chance_sub_power=sub_power, **kwargs
    )


def test_resolve_feature_power_attempt_chance_unresolved_is_power_not_wired():
    state = _state_with_leader()
    feature = Feature(feature_id=9, coord=LOCATION, kind=FeatureType.CATACOMBS)
    state.add_feature(feature)
    event = FeaturePowerEvent(power=Power.CHANCE, magic_feature=MagicFeature.ROULETTE_WHEEL, chance_sub_power=None)

    result = resolve_feature_power_attempt(state, LEADER_ID, feature, event, random.Random(0))

    assert result.applied is False
    assert result.reason == "power not yet wired"


def test_resolve_feature_power_attempt_chance_new_sex():
    state = _state_with_leader(sex=Sex.MALE)
    feature = Feature(feature_id=9, coord=LOCATION, kind=FeatureType.CATACOMBS)
    state.add_feature(feature)

    result = resolve_feature_power_attempt(state, LEADER_ID, feature, _chance_event(Power.NEW_SEX), random.Random(0))

    assert result.applied is True
    assert result.power is Power.NEW_SEX
    assert state.leaders[LEADER_ID].sex is Sex.FEMALE


def test_resolve_feature_power_attempt_chance_new_temp():
    state = _state_with_leader(temper=Temper.COWARDLY)
    feature = Feature(feature_id=9, coord=LOCATION, kind=FeatureType.CATACOMBS)
    state.add_feature(feature)
    event = _chance_event(Power.NEW_TEMP, temper_parameter=Temper.BERSERK)

    result = resolve_feature_power_attempt(state, LEADER_ID, feature, event, random.Random(0))

    assert result.applied is True
    assert result.power is Power.NEW_TEMP
    assert state.leaders[LEADER_ID].temper is Temper.BERSERK


def test_resolve_feature_power_attempt_chance_up_skill():
    ability = Ability.THIEF
    state = GameState()
    state.add_leader(_skilled_leader(ability, skill=0, aptitude=5))
    feature = Feature(feature_id=9, coord=LOCATION, kind=FeatureType.CATACOMBS)
    state.add_feature(feature)
    event = _chance_event(Power.UP_SKILL, ability_parameter=ability)

    result = resolve_feature_power_attempt(state, LEADER_ID, feature, event, random.Random(0))

    assert result.applied is True
    assert result.power is Power.UP_SKILL
    skill, _aptitude = state.leaders[LEADER_ID].skills.pair_for_ability(ability)
    assert skill == 1


def test_resolve_feature_power_attempt_chance_dn_skill():
    ability = Ability.THIEF
    state = GameState()
    state.add_leader(_skilled_leader(ability, skill=2, aptitude=2))
    feature = Feature(feature_id=9, coord=LOCATION, kind=FeatureType.CATACOMBS)
    state.add_feature(feature)
    event = _chance_event(Power.DN_SKILL, ability_parameter=ability)

    result = resolve_feature_power_attempt(state, LEADER_ID, feature, event, random.Random(0))

    assert result.applied is True
    assert result.power is Power.DN_SKILL
    skill, _aptitude = state.leaders[LEADER_ID].skills.pair_for_ability(ability)
    assert skill == 1


def test_resolve_feature_power_attempt_chance_sage_disc():
    state = _state_with_leader()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, LOCATION))
    feature = Feature(feature_id=9, coord=LOCATION, kind=FeatureType.CATACOMBS)
    state.add_feature(feature)

    result = resolve_feature_power_attempt(state, LEADER_ID, feature, _chance_event(Power.SAGE_DISC), random.Random(0))

    assert result.applied is True
    assert result.power is Power.SAGE_DISC
    assert len(result.revealed_discoveries) >= 1


def test_resolve_feature_power_attempt_chance_cast_spell():
    # random.Random(0)'s first randrange(8) call (no prior rng draws --
    # Chance's own condition is always PC_NONE, so `_apply_condition_
    # gate()` never touches `rng`) picks index 6 -> Spell.TORNADO,
    # confirmed via a standalone script against `CHANCE_SPELL_TABLE`
    # directly, not hand-traced.
    state = _state_with_leader()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, LOCATION, treasury=100))
    feature = Feature(feature_id=9, coord=LOCATION, kind=FeatureType.CATACOMBS)
    state.add_feature(feature)
    state.provinces[LOCATION] = ProvinceState(coord=LOCATION, terrain=Terrain.PLAINS, race=Race.HUMAN)

    result = resolve_feature_power_attempt(state, LEADER_ID, feature, _chance_event(Power.CAST_SPELL), random.Random(0))

    assert result.applied is True
    assert result.power is Power.CAST_SPELL
    assert result.cast_spell is Spell.TORNADO


# -- Phase 623: Power.MAP_PROV, "known provinces" ----------------------------


def test_map_prov_is_tractable():
    assert Power.MAP_PROV in TRACTABLE_POWERS


def _map_prov_event() -> FeaturePowerEvent:
    return FeaturePowerEvent(power=Power.MAP_PROV, magic_feature=MagicFeature.CRYSTAL_BALL)


def test_resolve_feature_power_attempt_map_prov_no_kingdom_refuses():
    state = GameState()
    state.add_leader(LeaderState(LEADER_ID, None, "Wanderer", LOCATION))
    feature = Feature(feature_id=1, coord=LOCATION, kind=FeatureType.PYRAMID)
    state.add_feature(feature)

    result = resolve_feature_power_attempt(state, LEADER_ID, feature, _map_prov_event(), random.Random(0))

    assert result.applied is False
    assert result.reason == "no Kingdom to record this for"


def test_resolve_feature_power_attempt_map_prov_exhausted_when_every_province_is_known():
    state = _state_with_leader()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, LOCATION))
    feature = Feature(feature_id=1, coord=LOCATION, kind=FeatureType.PYRAMID)
    state.add_feature(feature)
    only_province = ProvinceState(coord=LOCATION, terrain=Terrain.PLAINS, race=Race.HUMAN)
    only_province.explored_percent_by_kingdom[1] = 1
    state.provinces[LOCATION] = only_province

    result = resolve_feature_power_attempt(state, LEADER_ID, feature, _map_prov_event(), random.Random(0))

    assert result.applied is False
    assert result.reason == "no more provinces to reveal"


def test_resolve_feature_power_attempt_map_prov_reveals_three_to_five_unknown_provinces():
    state = _state_with_leader()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, LOCATION))
    feature = Feature(feature_id=1, coord=LOCATION, kind=FeatureType.PYRAMID)
    state.add_feature(feature)
    coords = [HexCoord(x, 0) for x in range(10)]
    for coord in coords:
        state.provinces[coord] = ProvinceState(coord=coord, terrain=Terrain.PLAINS, race=Race.HUMAN)

    result = resolve_feature_power_attempt(state, LEADER_ID, feature, _map_prov_event(), random.Random(0))

    assert result.applied is True
    assert result.power is Power.MAP_PROV
    assert 3 <= len(result.revealed_province_coords) <= 5
    assert len(set(result.revealed_province_coords)) == len(result.revealed_province_coords)
    for coord in result.revealed_province_coords:
        assert state.provinces[coord].known_to_kingdom(1) is True


def test_resolve_feature_power_attempt_map_prov_caps_reveal_count_when_few_provinces_are_unknown():
    state = _state_with_leader()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, LOCATION))
    feature = Feature(feature_id=1, coord=LOCATION, kind=FeatureType.PYRAMID)
    state.add_feature(feature)
    only_unknown = HexCoord(0, 0)
    already_known = HexCoord(1, 0)
    state.provinces[only_unknown] = ProvinceState(coord=only_unknown, terrain=Terrain.PLAINS, race=Race.HUMAN)
    known_province = ProvinceState(coord=already_known, terrain=Terrain.PLAINS, race=Race.HUMAN)
    known_province.explored_percent_by_kingdom[1] = 1
    state.provinces[already_known] = known_province

    result = resolve_feature_power_attempt(state, LEADER_ID, feature, _map_prov_event(), random.Random(0))

    assert result.applied is True
    assert result.revealed_province_coords == (only_unknown,)
