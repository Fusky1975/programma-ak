"""Tests for webapp/moves_compose.py -- the GM webapp's "compose moves"
editor's own form-to-Kingdom logic. Move (``ActionCode.LMOVE``) is the
first action to get its own dedicated syntax (a province-name dropdown
instead of the raw, encoded Object field) -- see that module's own
docstring for the ``turn/plan_dispatch.py``-sourced confirmation that
Move reads only ``obj`` (never ``extra``). Explore (``ActionCode.
EXPLORE``) is the second (sourced directly from the user, 2026-10-26,
and independently confirmed from ``turn/plan_dispatch.py``'s own
EXPLORE branch): it reads neither ``obj`` nor ``extra`` at all, always
targeting the acting leader's own current province. Search
(``ActionCode.SEARCH``) is the third -- sourced directly from the user
(2026-10-26, their own explicit "telaio"/skeleton request) and
independently confirmed from ``turn/search_decode.py``'s own module
docstring: ``obj`` is the target feature's own number. Its own
Encounter Plan tactic list is being designed one tactic at a time;
Talk (``Maneuver.TALK``) is the first -- sourced directly from the
user (2026-10-26): "può essere usata solo all'inizio del piano
d'incontro. Se viene usata dopo un'altra tattica viene semplicemente
ignorata" and "Non è possibile usare sia la tattica Talk che Fulfill
nello stesso Piano d'Incontro" (independently confirmed from
``turn/search_execution.py``'s own ``_resolve_fulfill()`` docstring,
rulebook [5.6]).
"""

from __future__ import annotations

import pytest

import tempfile
from pathlib import Path

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ARMY_TYPE_BY_ORDINAL, NO_LEADER_SENTINEL, ArmyType
from ak_engine.models.enums import ABILITY_NAME, Ability, ActionCode, Maneuver, Spell
from ak_engine.models.feature import Feature, FeatureType
from ak_engine.models.game_state import ArmyState, BlackmailClaim, GameState, KingdomState, LeaderState, ProvinceState
from ak_engine.models.kingdom import SkillTable
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.monster import Monster
from ak_engine.models.race import Race
from ak_engine.models.treasure import Treasure
from ak_engine.parser.k1_moves import parse_k1_moves_file
from ak_engine.parser.k1_moves_writer import write_k1_moves_file
from ak_engine.turn.army_list_decode import ALL_ARMIES_SENTINEL
from ak_engine.turn.combat import Quality
from ak_engine.turn.hex_numbering import decode_hex_number
from ak_engine.webapp.moves_compose import (
    CAST_ACTION_SPELLS,
    CAST_CHARACTER_TARGET_SPELLS,
    CAST_ITEM_TARGET_SPELLS,
    CAST_NO_TARGET_SPELLS,
    CAST_PROVINCE_TARGET_SPELLS,
    DEFAULT_SP,
    DISBAND_ALL_VALUE,
    EMPTY_SEARCH_EXTRA,
    ENCOUNTER_PLAN_CASTABLE_SPELLS,
    HIRE_GOLD_OFFER_RANGE,
    LEAVE_ALL_VALUE,
    LEAVE_GARRISON_VALUE,
    PICK_UP_ALL_VALUE,
    InvalidComposedMovesError,
    build_composed_kingdom,
    cast_character_target_options,
    cast_spell_options,
    challenge_target_options,
    charm_target_options,
    disband_target_options,
    feature_options,
    fire_target_options,
    give_item_options,
    hire_target_options,
    item_options,
    kill_enemy_target_options,
    leave_army_target_options,
    leave_target_options,
    nested_hero_option_bundle,
    parse_phase_inputs,
    pick_up_army_target_options,
    practice_ability_options,
    province_options,
    pursue_target_options,
    recruit_target_options,
    recruit_type_options,
    resurrection_target_options,
    spell_options,
    tactic_options,
    trade_gift_options,
    trade_recipient_options,
    trail_target_options,
    use_mi_item_options,
    use_mi_item_spell_by_id,
)

_ORDINAL_BY_ARMY_TYPE = {army_type: ordinal for ordinal, army_type in ARMY_TYPE_BY_ORDINAL.items()}

BOARD_WIDTH = 6
BOARD_HEIGHT = 4
HOME = HexCoord(1, 1)
KING_ID = 1


def _state() -> GameState:
    state = GameState()
    state.board_width = BOARD_WIDTH
    state.board_height = BOARD_HEIGHT
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.GOOD, HOME))
    state.add_leader(
        LeaderState(
            leader_id=KING_ID,
            kingdom_id=1,
            name="Aldric",
            location=HOME,
            is_king=True,
            skills=SkillTable(raw_values=[0] * 30 + [3]),
        )
    )
    state.add_province(ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, name="Numenor"))
    state.add_province(ProvinceState(HexCoord(3, 2), Terrain.FOREST, Race.HUMAN, name=None))
    # 2026-11-15: known_to_kingdom()/discovery_level() filtering now
    # narrows province_options()/feature_options() to what this test
    # Kingdom actually knows -- matching webapp/kingdom_create.py's own
    # real "home province starts 100% explored" seeding (production
    # never auto-seeds feature discovery the same way; this fixture's
    # own feature is marked known too so the many existing Search tests
    # below keep exercising Search's own parsing, not this orthogonal
    # discovery concern).
    state.provinces[HOME].explored_percent_by_kingdom[1] = 100
    state.add_feature(
        Feature(
            feature_id=3,
            coord=HOME,
            kind=FeatureType.ALTAR,
            guardian_monster=Monster.NEC_MAGE,
            discovered_by_kingdom={1: 1},
        )
    )
    state.add_item(Treasure.WAND_FIREBALL, KING_ID, charges=3)
    return state


def _all_defend_form(leader_id: int) -> dict[str, str]:
    form = {}
    for n in range(5):
        form[f"action_{leader_id}_{n}"] = str(int(ActionCode.DEFEND))
        form[f"obj_{leader_id}_{n}"] = "0"
        form[f"extra_{leader_id}_{n}"] = ""
        # Defend now has its own dedicated, validated target dropdown
        # (_parse_defend_target()) -- HOME parses fine regardless of
        # whether this particular test's own state actually registered
        # that exact province (no existence check, same as Move's own
        # _parse_move_target()).
        form[f"defend_target_{leader_id}_{n}"] = f"{HOME.x},{HOME.y}"
    return form


def test_province_options_names_a_named_province_and_falls_back_for_an_unnamed_one():
    # Bug fix, sourced directly from the user (2026-10-26): the label
    # also carries the province's own real "#<N>" order number (the
    # same x*100+y convention real reports already show, e.g. "Mongu
    # (#305)") "come nell'AK originale" -- not just name/coordinates.
    state = _state()
    options = province_options(state)
    assert ("1,1", "Numenor (1, 1) #0101") in options
    assert ("3,2", "(3, 2) #0302") in options


def test_province_options_sorted_in_map_reading_order():
    state = _state()
    options = province_options(state)
    values = [value for value, _ in options]
    assert values.index("1,1") < values.index("3,2")  # row 1 before row 2


def test_move_phase_reads_its_own_dropdown_not_the_generic_object_field():
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_2"] = str(int(ActionCode.LMOVE))
    form[f"move_target_{KING_ID}_2"] = "3,2"
    form[f"obj_{KING_ID}_2"] = "999"  # must be ignored for a Move phase

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=_state())

    move_phase = phases[2]
    assert move_phase.action is ActionCode.LMOVE
    assert decode_hex_number(move_phase.obj, BOARD_WIDTH) == HexCoord(3, 2)
    assert move_phase.extra == []


def test_move_phase_without_a_chosen_destination_is_rejected():
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.LMOVE))
    form[f"move_target_{KING_ID}_0"] = ""

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=_state())
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "Move destination" in str(exc)


def test_parse_phase_inputs_rejects_succ_trail_even_via_a_direct_tampered_value():
    # 2026-11-07 bug fix: ActionCode.SUCC_TRAIL (ordinal 20) is the one
    # ActionCode plan_dispatch.py's own SUPPORTED_ACTIONS frozenset
    # deliberately excludes "by design." app.py's compose page no
    # longer offers it in the Action dropdown, but a direct, tampered
    # POST could still name it -- this used to compose a normal-
    # looking PlanPhase that only failed, opaquely, at real turn-
    # processing time.
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.SUCC_TRAIL))

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=_state())
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "isn't a composable Action" in str(exc)


def test_move_phase_rejects_when_a_commanded_army_has_no_movement_points():
    # Bug fix (2026-11-18, user-reported "MOVE doesn't work"): the King
    # (or any leader) commanding a mixed force with one army that
    # genuinely has no movement points left this gameturn (already
    # moved, or some other effect spent it -- NOT a freshly-Recruited
    # unit, which gets a full movement allowance, user-confirmed) used
    # to save this Move order fine, only to have it vanish completely
    # during turn processing with nothing anywhere to explain why
    # (turn/move_execution.py execute_move()'s own plain ValueError,
    # caught and discarded by plan_dispatch.py's intentionally-broad
    # per-phase handler). Confirmed via a live repro of the user's own
    # report; now rejected here instead, at compose time, with a clear
    # reason.
    state = _state()
    state.add_army(ArmyState(900, 1, ArmyType.LEGION, Quality.AVERAGE, HOME, commanded_by=KING_ID, movement_points=0))
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.LMOVE))
    form[f"move_target_{KING_ID}_0"] = "3,2"

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "no movement points left this gameturn" in str(exc)
        assert "Legion" in str(exc)


def test_move_phase_allows_when_every_commanded_army_has_movement_points():
    state = _state()
    state.add_army(ArmyState(900, 1, ArmyType.LEGION, Quality.AVERAGE, HOME, commanded_by=KING_ID, movement_points=2))
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.LMOVE))
    form[f"move_target_{KING_ID}_0"] = "3,2"

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)

    assert phases[0].action is ActionCode.LMOVE
    assert decode_hex_number(phases[0].obj, BOARD_WIDTH) == HexCoord(3, 2)


def test_move_phase_rejects_a_nonexistent_province_even_via_a_direct_tampered_value():
    # 2026-11-07 bug fix: _parse_move_target() used to encode whatever
    # x,y a POST carried with no existence check at all -- the real
    # crash path this closes is turn/move_execution.py execute_move()
    # raising an unhandled ValueError for an off-map/nonexistent
    # province, previously only caught by a generic per-phase handler.
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.LMOVE))
    form[f"move_target_{KING_ID}_0"] = "99,99"  # off-map, never offered in province_options()

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=_state())
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "real province to Move to" in str(exc)


def test_non_move_phase_is_unaffected_by_the_move_destination_field():
    # WAIT, not Defend -- Defend now has its own dedicated, validated
    # target field (_parse_defend_target()), no longer a generic
    # fallback action.
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_1"] = str(int(ActionCode.WAIT))
    form[f"obj_{KING_ID}_1"] = "42"
    form[f"extra_{KING_ID}_1"] = "1, 2 3"

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=_state())

    assert phases[1].action is ActionCode.WAIT
    assert phases[1].obj == 42
    assert phases[1].extra == [1, 2, 3]


def test_build_composed_kingdom_round_trips_a_move_order_to_the_real_target_coord():
    state = _state()
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.LMOVE))
    form[f"move_target_{KING_ID}_0"] = "3,2"

    kingdom = build_composed_kingdom(state, game_label="Testia", turn_number=1, kingdom_id=1, form=form)

    phase0 = kingdom.leaders[0].plan.segments[0].phases["P0"]
    assert decode_hex_number(phase0.obj, state.board_width) == HexCoord(3, 2)


def test_defend_phase_reads_its_own_dropdown_not_the_generic_object_field():
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_2"] = str(int(ActionCode.DEFEND))
    form[f"defend_target_{KING_ID}_2"] = "3,2"
    form[f"obj_{KING_ID}_2"] = "999"  # must be ignored for a Defend phase

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=_state())

    defend_phase = phases[2]
    assert defend_phase.action is ActionCode.DEFEND
    assert decode_hex_number(defend_phase.obj, BOARD_WIDTH) == HexCoord(3, 2)
    assert defend_phase.extra == [0]


def test_defend_phase_reads_a_hand_typed_province_number_when_the_dropdown_is_empty():
    # 2026-11-16, user-requested: defend_target_number is a sibling
    # free-text fallback to defend_target's own dropdown, same shape
    # as Move's own.
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_2"] = str(int(ActionCode.DEFEND))
    form[f"defend_target_{KING_ID}_2"] = ""
    form[f"defend_target_number_{KING_ID}_2"] = "0302"  # real_province_number(HexCoord(3, 2))

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=_state())

    assert decode_hex_number(phases[2].obj, BOARD_WIDTH) == HexCoord(3, 2)


def test_defend_phase_without_a_chosen_target_is_rejected():
    form = _all_defend_form(KING_ID)
    form[f"defend_target_{KING_ID}_0"] = ""

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=_state())
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "province to Defend" in str(exc)


def test_build_composed_kingdom_round_trips_a_defend_order_to_the_real_target_coord():
    state = _state()
    form = _all_defend_form(KING_ID)
    form[f"defend_target_{KING_ID}_0"] = "3,2"

    kingdom = build_composed_kingdom(state, game_label="Testia", turn_number=1, kingdom_id=1, form=form)

    phase0 = kingdom.leaders[0].plan.segments[0].phases["P0"]
    assert phase0.action is ActionCode.DEFEND
    assert decode_hex_number(phase0.obj, state.board_width) == HexCoord(3, 2)
    assert phase0.extra == [0]


def test_explore_phase_ignores_any_generic_object_or_extra_input():
    # Sourced directly from the user (2026-10-26): "non c'è bisogno di
    # mettere la provincia perché si può esplorare solo la provincia
    # dove si trova l'eroe o il Re" -- confirmed from turn/plan_
    # dispatch.py's own EXPLORE branch, which reads neither obj nor
    # extra at all. Stray values left over in the generic fields (e.g.
    # from switching the Action dropdown away from something else)
    # must be silently ignored, not written into the real move file.
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_3"] = str(int(ActionCode.EXPLORE))
    form[f"obj_{KING_ID}_3"] = "999"
    form[f"extra_{KING_ID}_3"] = "1 2 3"

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=_state())

    explore_phase = phases[3]
    assert explore_phase.action is ActionCode.EXPLORE
    assert explore_phase.obj == 0
    assert explore_phase.extra == []


def test_build_composed_kingdom_explore_phase_carries_no_object_or_extra():
    state = _state()
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.EXPLORE))
    form[f"obj_{KING_ID}_0"] = "999"
    form[f"extra_{KING_ID}_0"] = "1 2 3"

    kingdom = build_composed_kingdom(state, game_label="Testia", turn_number=1, kingdom_id=1, form=form)

    phase0 = kingdom.leaders[0].plan.segments[0].phases["P0"]
    assert phase0.action is ActionCode.EXPLORE
    assert phase0.obj == 0
    assert phase0.extra == []


def test_aspy_phase_ignores_any_generic_object_or_extra_input_and_always_targets_the_leaders_own_location():
    # Sourced directly from the user (2026-11-02): "Sintassi: SP
    # #(numero della provincia in cui si trova eroe o re)" -- a
    # character can only Spy on the province he's already in, so (like
    # Explore) there is no target to choose; stray generic-field values
    # must be silently ignored and the real wire obj must still encode
    # this leader's own current province (HOME = HexCoord(1, 1)), not 0.
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_3"] = str(int(ActionCode.ASPY))
    form[f"obj_{KING_ID}_3"] = "999"
    form[f"extra_{KING_ID}_3"] = "1 2 3"

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=_state())

    aspy_phase = phases[3]
    assert aspy_phase.action is ActionCode.ASPY
    assert decode_hex_number(aspy_phase.obj, BOARD_WIDTH) == HOME
    assert aspy_phase.extra == [0]


def test_build_composed_kingdom_round_trips_an_aspy_order_to_the_leaders_own_province():
    state = _state()
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.ASPY))
    form[f"obj_{KING_ID}_0"] = "999"

    kingdom = build_composed_kingdom(state, game_label="Testia", turn_number=1, kingdom_id=1, form=form)

    phase0 = kingdom.leaders[0].plan.segments[0].phases["P0"]
    assert phase0.action is ActionCode.ASPY
    assert decode_hex_number(phase0.obj, state.board_width) == HOME
    assert phase0.extra == [0]


def test_feature_options_names_the_kind_province_and_guardian():
    state = _state()
    options = feature_options(state)
    assert ("3", "#3 Altar -- Numenor -- Renegade Necromancer") in options


def test_feature_options_omits_guardian_for_a_looted_feature():
    state = _state()
    state.features[3].looted = True
    options = feature_options(state)
    assert ("3", "#3 Altar -- Numenor") in options


def test_feature_options_flags_a_pending_quest_for_this_leader():
    # Sourced directly from the user (2026-10-27, designing Fulfill):
    # "Funziona solo se un eroe o un re ha ricevuto da un mostro nei
    # turni precedenti dopo una tattica TALK una quest (numerata col
    # numero d'ordine del feature)" -- Fulfill always resolves whichever
    # feature the same Search phase's own obj already names, so
    # flagging which feature holds a pending deal for this leader is
    # what actually helps the GM use Fulfill correctly.
    state = _state()
    state.features[3].pending_deal_leader_id = KING_ID
    options = feature_options(state, leader_id=KING_ID)
    assert ("3", "#3 Altar -- Numenor -- Renegade Necromancer -- pending quest for this leader") in options


def test_feature_options_does_not_flag_a_pending_quest_for_a_different_leader():
    state = _state()
    state.features[3].pending_deal_leader_id = 999
    options = feature_options(state, leader_id=KING_ID)
    assert ("3", "#3 Altar -- Numenor -- Renegade Necromancer") in options


def test_feature_options_with_no_leader_id_never_flags_a_pending_quest():
    state = _state()
    state.features[3].pending_deal_leader_id = KING_ID
    options = feature_options(state)
    assert ("3", "#3 Altar -- Numenor -- Renegade Necromancer") in options


def test_search_phase_reads_its_own_dropdown_not_the_generic_object_field():
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_1"] = str(int(ActionCode.SEARCH))
    form[f"search_feature_{KING_ID}_1"] = "3"
    form[f"obj_{KING_ID}_1"] = "999"  # must be ignored for a Search phase
    form[f"extra_{KING_ID}_1"] = "7 8 9"  # must be ignored too -- not composable yet

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=_state())

    search_phase = phases[1]
    assert search_phase.action is ActionCode.SEARCH
    assert search_phase.obj == 3
    assert search_phase.extra == EMPTY_SEARCH_EXTRA


def test_search_phase_without_a_chosen_feature_is_rejected():
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.SEARCH))
    form[f"search_feature_{KING_ID}_0"] = ""

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=_state())
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "Feature to Search" in str(exc)


def test_search_phase_with_a_nonexistent_feature_is_rejected():
    # 2026-11-06 bug fix: _parse_search_feature() used to take no state
    # argument at all and therefore never checked the posted id against
    # state.features, unlike every sibling target field in this module.
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.SEARCH))
    form[f"search_feature_{KING_ID}_0"] = "999999"

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=_state())
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "real Feature" in str(exc)


def test_build_composed_kingdom_round_trips_a_search_order_to_the_real_feature_id():
    state = _state()
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.SEARCH))
    form[f"search_feature_{KING_ID}_0"] = "3"

    kingdom = build_composed_kingdom(state, game_label="Testia", turn_number=1, kingdom_id=1, form=form)

    phase0 = kingdom.leaders[0].plan.segments[0].phases["P0"]
    assert phase0.action is ActionCode.SEARCH
    assert phase0.obj == 3
    assert phase0.extra == EMPTY_SEARCH_EXTRA


# -- Encounter Plan tactic slots (Talk is the first tactic designed) --


def _search_form(
    feature_id: int = 3,
    tactics: dict[int, int] | None = None,
    subs: dict[int, int] | None = None,
    says: dict[int, str] | None = None,
    spells: dict[int, int] | None = None,
    items: dict[int, int] | None = None,
):
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.SEARCH))
    form[f"search_feature_{KING_ID}_0"] = str(feature_id)
    for slot, maneuver_value in (tactics or {}).items():
        form[f"tactic_{KING_ID}_0_{slot}"] = str(maneuver_value)
    for slot, sub_value in (subs or {}).items():
        form[f"tactic_sub_{KING_ID}_0_{slot}"] = str(sub_value)
    for slot, say_value in (says or {}).items():
        form[f"tactic_say_{KING_ID}_0_{slot}"] = say_value
    for slot, spell_value in (spells or {}).items():
        form[f"tactic_spell_{KING_ID}_0_{slot}"] = str(spell_value)
    for slot, item_value in (items or {}).items():
        form[f"tactic_item_{KING_ID}_0_{slot}"] = str(item_value)
    return form


def test_tactic_options_offers_talk_only_in_slot_zero():
    slot0_values = {value for value, _ in tactic_options(0)}
    slot1_values = {value for value, _ in tactic_options(1)}
    assert int(Maneuver.TALK) in slot0_values
    assert int(Maneuver.TALK) not in slot1_values


def test_tactic_options_includes_say_everywhere_but_excludes_none():
    # Unlike Talk, Say has no position restriction of its own (sourced
    # directly from the user, 2026-10-27) -- offered in every slot.
    for slot in (0, 1):
        values = {value for value, _ in tactic_options(slot)}
        assert int(Maneuver.SAY) in values
        assert int(Maneuver.NONE) not in values


def test_tactic_options_excludes_give_by_default():
    # tactic_options()'s own default (no allow_give) excludes Give --
    # each caller that offers it (Search/Challenge/Pursue, all active
    # plans) passes allow_give=True explicitly; the passive Special
    # Encounter Plan's own caller does not (2026-11-14, user-confirmed:
    # Give/Steal/Talk are each real only in an active plan, never a
    # leader's own standing one).
    for slot in (0, 1):
        values = {value for value, _ in tactic_options(slot)}
        assert int(Maneuver.GIVE) not in values


def test_search_phase_allows_give_as_a_tactic():
    # 2026-11-14 correction (user-confirmed): Give used to be rejected
    # here on the (stale) claim that it's real only after Challenge/
    # Pursue -- it's real after Search too, same as Talk/Steal, just
    # never in a leader's own standing Special Encounter Plan.
    state = _state()
    item = state.add_item(Treasure.ABILITY_MELEE, KING_ID)
    form = _search_form(tactics={0: int(Maneuver.GIVE)})
    form[f"tactic_give_item_{KING_ID}_0_0"] = str(item.item_id)

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)

    assert phases[0].extra == [0, int(Maneuver.GIVE), item.item_id, -1]


def test_tactic_options_excludes_beg_everywhere():
    # Beg isn't one of the rulebook's eight numbered Encounter Plan
    # tactics at all (sourced directly from the user, 2026-10-28) --
    # "Implorare pietà" is documented only as automatic Cowardly
    # Temperament behavior, never a tactic a player orders.
    for slot in (0, 1):
        values = {value for value, _ in tactic_options(slot)}
        assert int(Maneuver.BEG) not in values


def test_search_phase_rejects_beg_even_via_a_direct_tampered_value():
    form = _search_form(tactics={0: int(Maneuver.BEG)})

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=_state())
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "Beg isn't a real Encounter Plan tactic" in str(exc)


def test_tactic_options_excludes_squeeze_everywhere():
    # Squeeze (2026-11-14, user-confirmed) is only ever the Pascal
    # source's own internal narration label for the Hand of Death
    # spell's damage type (turn/encounter.py's own confirmed finding),
    # never a real player-orderable tactic -- excluded for every slot
    # and every caller, active or passive alike.
    for slot in (0, 1):
        for kwargs in ({}, {"allow_give": True}, {"allow_fulfill_scout": True}, {"passive": True}):
            values = {value for value, _ in tactic_options(slot, **kwargs)}
            assert int(Maneuver.SQUEEZE) not in values


def test_search_phase_rejects_squeeze_even_via_a_direct_tampered_value():
    form = _search_form(tactics={0: int(Maneuver.SQUEEZE)})

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=_state())
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "Squeeze isn't a real Encounter Plan tactic" in str(exc)


def test_tactic_options_excludes_talk_from_a_passive_plan():
    # 2026-11-14, user-confirmed: Talk is real only in an active plan
    # (generated after Search/Challenge/Trail/Pursue), never a leader's
    # own standing, passive Special Encounter Plan -- even at slot 0.
    values = {value for value, _ in tactic_options(0, passive=True)}
    assert int(Maneuver.TALK) not in values


def test_tactic_options_excludes_fulfill_and_scout_from_challenge_and_pursue():
    # 2026-11-14, user-confirmed: Fulfill/Scout are real only after a
    # Search (SE) order -- not Challenge/Pursue's own active plans, and
    # not the passive Special Encounter Plan either.
    for kwargs in ({"allow_give": True}, {"passive": True}, {}):
        values = {value for value, _ in tactic_options(0, **kwargs)}
        assert int(Maneuver.FULFILL) not in values
        assert int(Maneuver.SCOUT) not in values


def test_challenge_phase_rejects_fulfill_even_via_a_direct_tampered_value():
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=1, name="Bram", location=HOME))
    form = _challenge_form(tactics={0: int(Maneuver.FULFILL)})

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "Fulfill is only usable in a Search (SE) Encounter Plan" in str(exc)


def test_pursue_phase_rejects_scout_even_via_a_direct_tampered_value():
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=1, name="Bram", location=HOME))
    form = _pursue_form(tactics={0: int(Maneuver.SCOUT)})

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "Scout is only usable in a Search (SE) Encounter Plan" in str(exc)


def test_special_encounter_plan_rejects_talk_even_via_a_direct_tampered_value():
    state = _state()
    form = _all_defend_form(KING_ID)
    form[f"sep_tactic_{KING_ID}_0_0"] = str(int(Maneuver.TALK))

    try:
        build_composed_kingdom(state, game_label="Testia", turn_number=1, kingdom_id=1, form=form)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "Talk isn't usable in a standing Special Encounter Plan" in str(exc)


def test_special_encounter_plan_rejects_steal_even_via_a_direct_tampered_value():
    state = _state()
    form = _all_defend_form(KING_ID)
    form[f"sep_tactic_{KING_ID}_0_0"] = str(int(Maneuver.STEAL))

    try:
        build_composed_kingdom(state, game_label="Testia", turn_number=1, kingdom_id=1, form=form)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "Steal isn't usable in a standing Special Encounter Plan" in str(exc)


def test_special_encounter_plan_rejects_fulfill_even_via_a_direct_tampered_value():
    state = _state()
    form = _all_defend_form(KING_ID)
    form[f"sep_tactic_{KING_ID}_0_0"] = str(int(Maneuver.FULFILL))

    try:
        build_composed_kingdom(state, game_label="Testia", turn_number=1, kingdom_id=1, form=form)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "Fulfill is only usable in a Search (SE) Encounter Plan" in str(exc)


def test_spell_options_lists_exactly_the_18_encounter_plan_castable_spells():
    values = {value for value, _ in spell_options()}
    assert values == {int(spell) for spell in ENCOUNTER_PLAN_CASTABLE_SPELLS}
    assert len(ENCOUNTER_PLAN_CASTABLE_SPELLS) == 18
    assert Spell.GATE_ANGEL in ENCOUNTER_PLAN_CASTABLE_SPELLS
    assert Spell.KILL_ENEMY in ENCOUNTER_PLAN_CASTABLE_SPELLS


def test_search_phase_cast_an_encounter_plan_spell_is_included():
    form = _search_form(tactics={0: int(Maneuver.CAST)}, spells={0: int(Spell.FIREBALL)})

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=_state())

    assert phases[0].extra == [0, int(Maneuver.CAST), int(Spell.FIREBALL), -1]


def test_search_phase_cast_gate_angel_is_included():
    # 2026-11-14: Gate Angel is one of the 6 skill-gated secret spells
    # now -- needs White skill 5+ (SECRET_SPELL_SKILL_THRESHOLD).
    state = _state()
    state.leaders[KING_ID].skills.set_pair_for_ability(Ability.WHITE, 5, 5)
    form = _search_form(tactics={0: int(Maneuver.CAST)}, spells={0: int(Spell.GATE_ANGEL)})

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)

    assert phases[0].extra == [0, int(Maneuver.CAST), int(Spell.GATE_ANGEL), -1]


def test_search_phase_cast_rejects_gate_angel_even_via_a_direct_tampered_value():
    # 2026-11-14 bug fix (user-requested): the Encounter Plan's own Cast
    # tactic dropdown no longer offers Gate Angel (or the other 5
    # skill-gated secret spells) to a leader below the required skill --
    # but a direct, tampered POST could still name it.
    state = _state()
    form = _search_form(tactics={0: int(Maneuver.CAST)}, spells={0: int(Spell.GATE_ANGEL)})

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "hasn't discovered Gate Angel yet" in str(exc)


def test_spell_options_excludes_secret_spells_below_the_skill_threshold():
    state = _state()

    values = {value for value, _ in spell_options(state, KING_ID)}

    assert int(Spell.GATE_ANGEL) not in values
    assert int(Spell.GATE_DEMON) not in values
    assert int(Spell.HEAL) not in values
    assert int(Spell.LAVA_POOL) not in values
    assert int(Spell.AUGUR_COMBAT) not in values
    assert int(Spell.ILLUS_HERO) not in values
    assert int(Spell.FIREBALL) in values  # unaffected, ordinary spell


def test_spell_options_includes_secret_spells_at_the_skill_threshold():
    state = _state()
    state.leaders[KING_ID].skills.set_pair_for_ability(Ability.WHITE, 5, 5)
    state.leaders[KING_ID].skills.set_pair_for_ability(Ability.NECROMANCY, 5, 5)
    state.leaders[KING_ID].skills.set_pair_for_ability(Ability.ELEMENTAL, 5, 5)
    state.leaders[KING_ID].skills.set_pair_for_ability(Ability.PSYCHIC, 5, 5)
    state.leaders[KING_ID].skills.set_pair_for_ability(Ability.ILLUSION, 5, 5)

    values = {value for value, _ in spell_options(state, KING_ID)}

    assert int(Spell.GATE_ANGEL) in values
    assert int(Spell.GATE_DEMON) in values
    assert int(Spell.HEAL) in values
    assert int(Spell.LAVA_POOL) in values
    assert int(Spell.AUGUR_COMBAT) in values
    assert int(Spell.ILLUS_HERO) in values


def test_cast_spell_options_lists_the_same_19_spells_regardless_of_skill():
    # 2026-11-14: none of the 6 skill-gated secret spells are ever
    # members of CAST_ACTION_SPELLS (each is Encounter-Plan-only, like
    # Gate Angel -- see that frozenset's own docstring), so unlike
    # spell_options() this dropdown needs no per-leader skill
    # filtering, and takes no state/leader_id arguments at all.
    assert {value for value, _ in cast_spell_options()} == {int(spell) for spell in CAST_ACTION_SPELLS}


def test_search_phase_cast_kill_enemy_is_included():
    # Kill Enemy's own Personal-Combat dispatch branch (2026-10-31,
    # user-requested): no separate target field -- same implicit-
    # opponent shape every other Encounter Plan Cast tactic already has.
    form = _search_form(tactics={0: int(Maneuver.CAST)}, spells={0: int(Spell.KILL_ENEMY)})

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=_state())

    assert phases[0].extra == [0, int(Maneuver.CAST), int(Spell.KILL_ENEMY), -1]


def test_search_phase_cast_an_action_only_spell_is_rejected():
    # Resurrection is a real spell, but it's Action-Cast-only -- never
    # dispatched inside a Search Encounter Plan's own CAST tactic.
    form = _search_form(tactics={0: int(Maneuver.CAST)}, spells={0: int(Spell.RESURRECTION)})

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=_state())
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "can't be cast in an Encounter Plan" in str(exc)


def test_search_phase_cast_without_choosing_a_spell_is_rejected():
    form = _search_form(tactics={0: int(Maneuver.CAST)})

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=_state())
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "choose a spell to Cast" in str(exc)


def test_search_phase_cast_an_invalid_spell_ordinal_is_rejected():
    form = _search_form(tactics={0: int(Maneuver.CAST)}, spells={0: 9999})

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=_state())
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "choose a spell to Cast" in str(exc)


def test_item_options_lists_only_this_leaders_own_usable_wands():
    state = _state()
    usable_item = state.items_held_by(KING_ID)[0]  # WAND_FIREBALL, 3 charges, from _state()
    state.add_item(Treasure.WAND_ORATORY, KING_ID, charges=3)  # owned, but Oratory isn't composable here
    state.add_item(Treasure.WAND_FIREBALL, None, charges=3)  # usable spell, but nobody owns it
    other_leader_id = 2
    state.add_leader(LeaderState(leader_id=other_leader_id, kingdom_id=1, name="Other", location=HOME))
    state.add_item(Treasure.WAND_FIREBALL, other_leader_id, charges=3)  # usable spell, owned by someone else
    state.add_item(Treasure.WAND_FIREBALL, KING_ID, charges=0)  # usable spell, owned, but no charges left

    values = {value for value, _ in item_options(state, KING_ID)}

    assert values == {str(usable_item.item_id)}


def test_search_phase_use_item_a_usable_wand_is_included():
    state = _state()
    item = state.items_held_by(KING_ID)[0]
    form = _search_form(tactics={0: int(Maneuver.USE_MI)}, items={0: item.item_id})

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)

    assert phases[0].extra == [0, int(Maneuver.USE_MI), item.item_id, -1]


def test_search_phase_use_item_can_repeat_with_different_items():
    # "Se un personaggio ha due armi magiche, può... specificare quale
    # delle due intende adoperare" -- and "non hanno limite".
    state = _state()
    first_item = state.items_held_by(KING_ID)[0]
    second_item = state.add_item(Treasure.WAND_INVISIBILITY, KING_ID, charges=1)
    form = _search_form(
        tactics={0: int(Maneuver.USE_MI), 1: int(Maneuver.USE_MI)},
        items={0: first_item.item_id, 1: second_item.item_id},
    )

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)

    assert phases[0].extra == [0, int(Maneuver.USE_MI), first_item.item_id, int(Maneuver.USE_MI), second_item.item_id, -1]


def test_search_phase_use_item_without_choosing_an_item_is_rejected():
    form = _search_form(tactics={0: int(Maneuver.USE_MI)})

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=_state())
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "choose an item to Use" in str(exc)


def test_search_phase_use_item_an_item_not_owned_by_this_leader_is_rejected():
    state = _state()
    other_leader_id = 2
    state.add_leader(LeaderState(leader_id=other_leader_id, kingdom_id=1, name="Other", location=HOME))
    item = state.add_item(Treasure.WAND_FIREBALL, other_leader_id, charges=3)
    form = _search_form(tactics={0: int(Maneuver.USE_MI)}, items={0: item.item_id})

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "choose an item to Use" in str(exc)


def test_search_phase_use_item_a_nonexistent_item_id_is_rejected():
    form = _search_form(tactics={0: int(Maneuver.USE_MI)}, items={0: 999999})

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=_state())
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "choose an item to Use" in str(exc)


def test_search_phase_use_item_a_wand_with_an_unmodeled_spell_is_rejected():
    # Oratory is a real spell, but Action-Cast-only -- never dispatched
    # inside a Search Encounter Plan's own Use Item tactic either.
    state = _state()
    item = state.add_item(Treasure.WAND_ORATORY, KING_ID, charges=3)
    form = _search_form(tactics={0: int(Maneuver.USE_MI)}, items={0: item.item_id})

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "can't be used in an Encounter Plan" in str(exc)


def test_search_phase_use_item_a_non_wand_item_is_rejected():
    state = _state()
    item = state.add_item(Treasure.GOLD_HOARD_LARGE, KING_ID, charges=0)
    form = _search_form(tactics={0: int(Maneuver.USE_MI)}, items={0: item.item_id})

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "can't be used in an Encounter Plan" in str(exc)


def test_search_phase_use_item_a_wand_with_no_charges_left_is_rejected():
    state = _state()
    item = state.add_item(Treasure.WAND_FIREBALL, KING_ID, charges=0)
    form = _search_form(tactics={0: int(Maneuver.USE_MI)}, items={0: item.item_id})

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "has no charges left" in str(exc)


def test_tactic_options_offers_steal_in_every_slot():
    # Unlike Talk, Steal's own position rule depends on the *previous*
    # slot's own content (slot 0, or right after Cast Invisibility), not
    # the slot index alone -- so there's no static per-slot filtering to
    # apply here the way Talk's "slot 0 only" rule allows. Gated by
    # allow_give (2026-11-14, same as Give/Talk: real only in an active
    # plan, never the passive Special Encounter Plan).
    for slot in (0, 1, 3):
        values = {value for value, _ in tactic_options(slot, allow_give=True)}
        assert int(Maneuver.STEAL) in values


def test_search_phase_steal_as_the_first_tactic():
    form = _search_form(tactics={0: int(Maneuver.STEAL)})

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=_state())

    assert phases[0].extra == [0, int(Maneuver.STEAL), -1]


def test_search_phase_steal_right_after_cast_invisibility():
    form = _search_form(
        tactics={0: int(Maneuver.CAST), 1: int(Maneuver.STEAL)},
        spells={0: int(Spell.INVISIBILITY)},
    )

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=_state())

    assert phases[0].extra == [0, int(Maneuver.CAST), int(Spell.INVISIBILITY), int(Maneuver.STEAL), -1]


def test_search_phase_steal_after_a_different_spell_is_rejected():
    form = _search_form(
        tactics={0: int(Maneuver.CAST), 1: int(Maneuver.STEAL)},
        spells={0: int(Spell.SPIRITWRACK)},
    )

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=_state())
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "Steal can only be the first tactic" in str(exc)


def test_search_phase_steal_after_a_non_cast_tactic_is_rejected():
    form = _search_form(tactics={0: int(Maneuver.MELEE), 1: int(Maneuver.STEAL)})

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=_state())
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "Steal can only be the first tactic" in str(exc)


def test_search_phase_steal_as_a_later_tactic_with_no_predecessor_is_rejected():
    # Direct, tampered POST: slot 0 left empty but slot 1 holds Steal --
    # this is already rejected as a "gap", but confirms Steal doesn't
    # get a pass just because there's nothing recognizable before it.
    form = _search_form(tactics={1: int(Maneuver.STEAL)})

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=_state())
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "fill the Encounter Plan without gaps" in str(exc)


def test_search_phase_aggressive_tactics_can_follow_steal():
    form = _search_form(tactics={0: int(Maneuver.STEAL), 1: int(Maneuver.MELEE)})

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=_state())

    assert phases[0].extra == [0, int(Maneuver.STEAL), int(Maneuver.MELEE), -1]


def test_search_phase_steal_and_talk_together_is_rejected():
    form = _search_form(
        tactics={0: int(Maneuver.TALK), 1: int(Maneuver.CAST), 2: int(Maneuver.STEAL)},
        spells={1: int(Spell.INVISIBILITY)},
    )

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=_state())
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "Talk and Steal can't be used together" in str(exc)


def test_search_phase_steal_and_fulfill_together_is_rejected():
    form = _search_form(tactics={0: int(Maneuver.STEAL), 1: int(Maneuver.FULFILL)})

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=_state())
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "Fulfill and Steal can't be used together" in str(exc)


def test_tactic_options_offers_flee_in_every_slot():
    for slot in (0, 1, 3):
        values = {value for value, _ in tactic_options(slot)}
        assert int(Maneuver.FLEE) in values


def test_search_phase_flee_once_is_accepted():
    form = _search_form(tactics={0: int(Maneuver.MELEE), 1: int(Maneuver.FLEE)})

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=_state())

    assert phases[0].extra == [0, int(Maneuver.MELEE), int(Maneuver.FLEE), -1]


def test_search_phase_flee_twice_is_rejected():
    form = _search_form(tactics={0: int(Maneuver.FLEE), 1: int(Maneuver.MELEE), 2: int(Maneuver.FLEE)})

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=_state())
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "Flee can only be used once in the same Encounter Plan" in str(exc)


def test_tactic_options_labels_shoot_as_fire_arrow():
    # Maneuver.SHOOT's own Python name isn't the rulebook's name for it
    # (rulebook [5.2] "Fire Arrow [FI]") -- the dropdown says so.
    labels = dict(tactic_options(0))
    assert labels[int(Maneuver.SHOOT)] == "Fire Arrow"


def test_search_phase_shoot_once_is_accepted():
    form = _search_form(tactics={0: int(Maneuver.SHOOT)})

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=_state())

    assert phases[0].extra == [0, int(Maneuver.SHOOT), -1]


def test_search_phase_shoot_twice_is_rejected():
    form = _search_form(tactics={0: int(Maneuver.SHOOT), 1: int(Maneuver.MELEE), 2: int(Maneuver.SHOOT)})

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=_state())
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "Fire Arrow can only be used once in the same Encounter Plan" in str(exc)


def test_tactic_options_offers_scout_in_every_slot_with_no_restriction():
    # Unlike Talk/Steal (position) or Flee (at-most-once), Scout's own
    # position is irrelevant and a second occurrence is a real, distinct
    # input (the game's own consent signal for costed Feature Powers),
    # so nothing filters it out of any slot. Gated by allow_fulfill_scout
    # (2026-11-14): real only after a Search (SE) order, never Challenge/
    # Pursue's own active plan or the passive Special Encounter Plan.
    for slot in (0, 1, 3):
        values = {value for value, _ in tactic_options(slot, allow_fulfill_scout=True)}
        assert int(Maneuver.SCOUT) in values


def test_search_phase_scout_alone_is_accepted():
    form = _search_form(tactics={0: int(Maneuver.SCOUT)})

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=_state())

    assert phases[0].extra == [0, int(Maneuver.SCOUT), -1]


def test_search_phase_scout_twice_is_accepted_not_rejected():
    # A second Scout is the real, meaningful consent signal for costed
    # Feature Powers (Pay Up/Drain Skill/Drain Courage) -- not a repeat
    # to reject the way a second Flee is.
    form = _search_form(tactics={0: int(Maneuver.MELEE), 1: int(Maneuver.SCOUT), 2: int(Maneuver.SCOUT)})

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=_state())

    assert phases[0].extra == [0, int(Maneuver.MELEE), int(Maneuver.SCOUT), int(Maneuver.SCOUT), -1]


def test_search_phase_scout_combined_with_talk_is_accepted():
    form = _search_form(tactics={0: int(Maneuver.TALK), 1: int(Maneuver.SCOUT)})

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=_state())

    assert phases[0].extra == [0, int(Maneuver.TALK), int(Maneuver.SCOUT), -1]


def test_search_phase_scout_combined_with_steal_and_flee_is_accepted():
    form = _search_form(
        tactics={0: int(Maneuver.STEAL), 1: int(Maneuver.SCOUT), 2: int(Maneuver.FLEE)},
    )

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=_state())

    assert phases[0].extra == [0, int(Maneuver.STEAL), int(Maneuver.SCOUT), int(Maneuver.FLEE), -1]


def test_tactic_options_offers_melee_in_every_slot_with_no_restriction():
    for slot in (0, 1, 3):
        values = {value for value, _ in tactic_options(slot)}
        assert int(Maneuver.MELEE) in values


def test_search_phase_melee_twice_is_accepted_not_rejected():
    # Unlike Flee/Shoot, Melee has no "at most once" cap -- the engine
    # is explicitly written to support more than one explicit Melee
    # tactic in the same plan (each fights exactly one round unless
    # it's genuinely the plan's own last tactic).
    form = _search_form(tactics={0: int(Maneuver.MELEE), 1: int(Maneuver.SCOUT), 2: int(Maneuver.MELEE)})

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=_state())

    assert phases[0].extra == [0, int(Maneuver.MELEE), int(Maneuver.SCOUT), int(Maneuver.MELEE), -1]


def test_search_phase_with_a_simple_tactic_sequence():
    form = _search_form(tactics={0: int(Maneuver.MELEE), 1: int(Maneuver.SCOUT)})

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=_state())

    assert phases[0].extra == [0, int(Maneuver.MELEE), int(Maneuver.SCOUT), -1]


def test_search_phase_reads_more_tactics_than_a_real_phase_typically_has():
    # 2026-11-18, user-requested "add as many tactics as you like" for
    # the ordinary per-phase Encounter Plan too (previously only the
    # Special Encounter Plan got this) -- EXPANDABLE_TACTIC_SLOT_COUNT
    # (25) is well past TACTIC_SLOT_COUNT (7), the real-sample-sourced
    # typical max every actual Search phase's own table starts visible
    # with, confirming the parser itself (not just the UI's own hidden
    # extra rows) actually reads beyond slot 7.
    form = _search_form(tactics={slot: int(Maneuver.MELEE) for slot in range(10)})

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=_state())

    assert phases[0].extra == [0, *([int(Maneuver.MELEE)] * 10), -1]




def test_search_phase_talk_as_the_first_tactic_is_accepted():
    form = _search_form(tactics={0: int(Maneuver.TALK)})

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=_state())

    assert phases[0].extra == [0, int(Maneuver.TALK), -1]


def test_search_phase_talk_after_another_tactic_is_rejected():
    # Sourced directly from the user (2026-10-26): "può essere usata
    # solo all'inizio del piano d'incontro. Se viene usata dopo
    # un'altra tattica viene semplicemente ignorata" -- rejected here
    # rather than silently accepted-but-inert, so a direct/tampered
    # submission never produces a quietly-wrong file.
    form = _search_form(tactics={0: int(Maneuver.MELEE), 1: int(Maneuver.TALK)})

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=_state())
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "first tactic" in str(exc)


def test_search_phase_talk_and_fulfill_together_is_rejected():
    # Sourced directly from the user (2026-10-26): "Non è possibile
    # usare sia la tattica Talk che Fulfill nello stesso Piano
    # d'Incontro" -- independently confirmed from turn/search_
    # execution.py's own _resolve_fulfill() docstring (rulebook [5.6]).
    form = _search_form(tactics={0: int(Maneuver.TALK), 1: int(Maneuver.FULFILL)})

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=_state())
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "Talk and Fulfill" in str(exc)


def test_search_phase_fulfill_alone_is_accepted():
    form = _search_form(tactics={0: int(Maneuver.FULFILL)})

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=_state())

    assert phases[0].extra == [0, int(Maneuver.FULFILL), -1]


def test_search_phase_fulfill_has_no_position_restriction_unlike_talk():
    # Sourced directly from the user (2026-10-27): Fulfill has no
    # "first tactic only" rule of its own -- confirmed from turn/
    # search_execution.py's own _resolve_fulfill(), which never checks
    # a tactic's own position, unlike the module docstring's own
    # discussion of Talk.
    form = _search_form(tactics={0: int(Maneuver.MELEE), 1: int(Maneuver.SCOUT), 2: int(Maneuver.FULFILL)})

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=_state())

    assert phases[0].extra == [0, int(Maneuver.MELEE), int(Maneuver.SCOUT), int(Maneuver.FULFILL), -1]


def test_search_phase_fulfill_carries_no_sub_object():
    form = _search_form(tactics={0: int(Maneuver.FULFILL)}, subs={0: 42})  # must be ignored

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=_state())

    assert phases[0].extra == [0, int(Maneuver.FULFILL), -1]


def test_search_phase_fulfill_after_talk_slot_but_not_in_slot_zero_is_still_rejected():
    # Talk must be in slot 0 specifically -- Fulfill anywhere else is
    # fine on its own, but combining it with Talk (wherever Talk sits)
    # is still rejected by the Talk/Fulfill exclusion rule above.
    form = _search_form(tactics={0: int(Maneuver.TALK), 1: int(Maneuver.FULFILL)})

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=_state())
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "Talk and Fulfill" in str(exc)


def test_search_phase_rejects_a_gap_between_tactic_slots():
    form = _search_form(tactics={0: int(Maneuver.MELEE), 2: int(Maneuver.SCOUT)})  # slot 1 left empty

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=_state())
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "gaps" in str(exc)


def test_search_phase_rejects_none_even_via_a_direct_tampered_value():
    form = _search_form(tactics={0: int(Maneuver.NONE)})
    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=_state())
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "isn't composable" in str(exc)


def test_search_phase_say_tactic_text_is_included():
    form = _search_form(tactics={0: int(Maneuver.SAY)}, says={0: "Take that!"})

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=_state())

    assert phases[0].extra == [0, int(Maneuver.SAY), "Take that!", -1]


def test_search_phase_say_tactic_followed_by_another_tactic_is_included():
    # "La successiva tattica del personaggio è eseguita nello stesso
    # round di combattimento della tattica Say" -- confirms Say can be
    # followed by a real tactic in the same Encounter Plan.
    form = _search_form(
        tactics={0: int(Maneuver.SAY), 1: int(Maneuver.MELEE)},
        says={0: "Eccoti un bell'hot dog, muso gelato!"},
    )

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=_state())

    assert phases[0].extra == [0, int(Maneuver.SAY), "Eccoti un bell'hot dog, muso gelato!", int(Maneuver.MELEE), -1]


def test_search_phase_say_tactic_without_text_is_rejected():
    form = _search_form(tactics={0: int(Maneuver.SAY)})

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=_state())
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "Say's own text" in str(exc)


def test_search_phase_say_tactic_over_160_characters_is_rejected():
    form = _search_form(tactics={0: int(Maneuver.SAY)}, says={0: "x" * 161})

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=_state())
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "160 characters or fewer" in str(exc)


def test_search_phase_say_tactic_at_exactly_160_characters_is_accepted():
    text = "x" * 160
    form = _search_form(tactics={0: int(Maneuver.SAY)}, says={0: text})

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=_state())

    assert phases[0].extra == [0, int(Maneuver.SAY), text, -1]


def test_search_phase_say_tactic_can_repeat_for_riddle_attempts():
    # "il personaggio può fare tutti i tentativi che vuole utilizzando
    # la tattica Say" -- repeated Say tactics in the same plan.
    form = _search_form(
        tactics={0: int(Maneuver.SAY), 1: int(Maneuver.SAY)},
        says={0: "First guess", 1: "Second guess"},
    )

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=_state())

    assert phases[0].extra == [0, int(Maneuver.SAY), "First guess", int(Maneuver.SAY), "Second guess", -1]


def test_build_composed_kingdom_round_trips_an_encounter_plan():
    state = _state()
    form = _search_form(tactics={0: int(Maneuver.TALK)})

    kingdom = build_composed_kingdom(state, game_label="Testia", turn_number=1, kingdom_id=1, form=form)

    phase0 = kingdom.leaders[0].plan.segments[0].phases["P0"]
    assert phase0.extra == [0, int(Maneuver.TALK), -1]


def test_build_composed_kingdom_round_trips_a_say_tactic_through_the_real_writer():
    # Goes through write_k1_moves_file() + parse_k1_moves_file() for
    # real, not just an in-memory Kingdom assertion -- the whole point
    # of composing through a real Kingdom is that this exact file is
    # what turn processing would actually read back.
    state = _state()
    form = _search_form(tactics={0: int(Maneuver.SAY)}, says={0: "Take that!"})

    kingdom = build_composed_kingdom(state, game_label="Testia", turn_number=1, kingdom_id=1, form=form)
    text = write_k1_moves_file(kingdom)
    tmp = Path(tempfile.mktemp())
    tmp.write_text(text, encoding="utf-8")
    try:
        reparsed = parse_k1_moves_file(tmp)
    finally:
        tmp.unlink(missing_ok=True)

    phase0 = reparsed.leaders[0].plan.segments[0].phases["P0"]
    assert phase0.extra == [0, int(Maneuver.SAY), "Take that!", -1]


def test_build_composed_kingdom_round_trips_a_steal_after_cast_invisibility():
    state = _state()
    form = _search_form(
        tactics={0: int(Maneuver.CAST), 1: int(Maneuver.STEAL)},
        spells={0: int(Spell.INVISIBILITY)},
    )

    kingdom = build_composed_kingdom(state, game_label="Testia", turn_number=1, kingdom_id=1, form=form)
    text = write_k1_moves_file(kingdom)
    tmp = Path(tempfile.mktemp())
    tmp.write_text(text, encoding="utf-8")
    try:
        reparsed = parse_k1_moves_file(tmp)
    finally:
        tmp.unlink(missing_ok=True)

    phase0 = reparsed.leaders[0].plan.segments[0].phases["P0"]
    assert phase0.extra == [0, int(Maneuver.CAST), int(Spell.INVISIBILITY), int(Maneuver.STEAL), -1]


def test_build_composed_kingdom_round_trips_a_flee_after_melee():
    state = _state()
    form = _search_form(tactics={0: int(Maneuver.MELEE), 1: int(Maneuver.FLEE)})

    kingdom = build_composed_kingdom(state, game_label="Testia", turn_number=1, kingdom_id=1, form=form)
    text = write_k1_moves_file(kingdom)
    tmp = Path(tempfile.mktemp())
    tmp.write_text(text, encoding="utf-8")
    try:
        reparsed = parse_k1_moves_file(tmp)
    finally:
        tmp.unlink(missing_ok=True)

    phase0 = reparsed.leaders[0].plan.segments[0].phases["P0"]
    assert phase0.extra == [0, int(Maneuver.MELEE), int(Maneuver.FLEE), -1]


def test_build_composed_kingdom_round_trips_a_shoot_then_melee():
    state = _state()
    form = _search_form(tactics={0: int(Maneuver.SHOOT), 1: int(Maneuver.MELEE)})

    kingdom = build_composed_kingdom(state, game_label="Testia", turn_number=1, kingdom_id=1, form=form)
    text = write_k1_moves_file(kingdom)
    tmp = Path(tempfile.mktemp())
    tmp.write_text(text, encoding="utf-8")
    try:
        reparsed = parse_k1_moves_file(tmp)
    finally:
        tmp.unlink(missing_ok=True)

    phase0 = reparsed.leaders[0].plan.segments[0].phases["P0"]
    assert phase0.extra == [0, int(Maneuver.SHOOT), int(Maneuver.MELEE), -1]


def test_build_composed_kingdom_round_trips_a_double_scout_consent_signal():
    state = _state()
    form = _search_form(tactics={0: int(Maneuver.MELEE), 1: int(Maneuver.SCOUT), 2: int(Maneuver.SCOUT)})

    kingdom = build_composed_kingdom(state, game_label="Testia", turn_number=1, kingdom_id=1, form=form)
    text = write_k1_moves_file(kingdom)
    tmp = Path(tempfile.mktemp())
    tmp.write_text(text, encoding="utf-8")
    try:
        reparsed = parse_k1_moves_file(tmp)
    finally:
        tmp.unlink(missing_ok=True)

    phase0 = reparsed.leaders[0].plan.segments[0].phases["P0"]
    assert phase0.extra == [0, int(Maneuver.MELEE), int(Maneuver.SCOUT), int(Maneuver.SCOUT), -1]


def test_build_composed_kingdom_round_trips_a_cast_gate_angel():
    # 2026-11-14: Gate Angel is one of the 6 skill-gated secret spells
    # now -- needs White skill 5+ (SECRET_SPELL_SKILL_THRESHOLD).
    state = _state()
    state.leaders[KING_ID].skills.set_pair_for_ability(Ability.WHITE, 5, 5)
    form = _search_form(tactics={0: int(Maneuver.CAST)}, spells={0: int(Spell.GATE_ANGEL)})

    kingdom = build_composed_kingdom(state, game_label="Testia", turn_number=1, kingdom_id=1, form=form)
    text = write_k1_moves_file(kingdom)
    tmp = Path(tempfile.mktemp())
    tmp.write_text(text, encoding="utf-8")
    try:
        reparsed = parse_k1_moves_file(tmp)
    finally:
        tmp.unlink(missing_ok=True)

    phase0 = reparsed.leaders[0].plan.segments[0].phases["P0"]
    assert phase0.extra == [0, int(Maneuver.CAST), int(Spell.GATE_ANGEL), -1]


def test_build_composed_kingdom_round_trips_a_use_item_wand_of_fireball():
    state = _state()
    item = state.items_held_by(KING_ID)[0]
    form = _search_form(tactics={0: int(Maneuver.USE_MI)}, items={0: item.item_id})

    kingdom = build_composed_kingdom(state, game_label="Testia", turn_number=1, kingdom_id=1, form=form)
    text = write_k1_moves_file(kingdom)
    tmp = Path(tempfile.mktemp())
    tmp.write_text(text, encoding="utf-8")
    try:
        reparsed = parse_k1_moves_file(tmp)
    finally:
        tmp.unlink(missing_ok=True)

    phase0 = reparsed.leaders[0].plan.segments[0].phases["P0"]
    assert phase0.extra == [0, int(Maneuver.USE_MI), item.item_id, -1]


def test_recruit_target_options_lists_self_and_garrison_and_colocated_leaders():
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=1, name="Bram", location=HOME))
    state.add_leader(LeaderState(leader_id=3, kingdom_id=1, name="Elsewhere", location=HexCoord(3, 2)))

    options = recruit_target_options(state, KING_ID)

    assert options[0] == ("self", "Self (Aldric)")
    assert ("2", "Bram") in options
    assert not any(label == "Elsewhere" for _value, label in options)
    assert options[-1] == ("garrison", "Garrison (unled)")


def test_recruit_target_options_labels_a_different_kingdoms_colocated_leader():
    state = _state()
    state.add_kingdom(KingdomState(2, "Allyria", Race.HUMAN, Alignment.GOOD, HexCoord(5, 5)))
    state.add_leader(LeaderState(leader_id=9, kingdom_id=2, name="Guest", location=HOME, is_king=True))

    options = recruit_target_options(state, KING_ID)

    assert ("9", "Guest, Allyria") in options


def test_recruit_type_options_lists_native_type_at_base_cost():
    state = _state()
    options = recruit_type_options(state, KING_ID)
    values = dict(options)
    bowmen_value = str(_ORDINAL_BY_ARMY_TYPE[ArmyType.BOWMEN])
    assert "native, 2 gold" in values[bowmen_value]


def test_recruit_type_options_labels_non_native_type_at_double_cost_with_ownership_note():
    state = _state()
    state.provinces[HOME].recruit_type_1 = ArmyType.LEGION
    options = recruit_type_options(state, KING_ID)
    values = dict(options)
    bowmen_value = str(_ORDINAL_BY_ARMY_TYPE[ArmyType.BOWMEN])
    assert "non-native, 4 gold -- needs an existing unit of this type" in values[bowmen_value]


def test_recruit_type_options_labels_garrison_native_even_without_a_listed_slot():
    # 2026-11-15 bug fix (user-reported): Garrison is never itself one
    # of a province's 2 listed native slot types in real data, but
    # RULES.AK still makes it always recruitable, at base (1 gold)
    # cost, in any humanoid-race province -- turn/recruit_execution.py
    # execute_recruit()'s own real dispatch already exempts it
    # (Phase 1054); this preview used to miss that same exemption and
    # wrongly show "(non-native, 2 gold -- needs an existing unit of
    # this type)" instead.
    state = _state()
    state.provinces[HOME].recruit_type_1 = ArmyType.BOWMEN
    state.provinces[HOME].recruit_type_2 = ArmyType.AXEMEN
    options = recruit_type_options(state, KING_ID)
    values = dict(options)
    garrison_value = str(_ORDINAL_BY_ARMY_TYPE[ArmyType.GARRISON])
    assert "native, 1 gold" in values[garrison_value]
    assert "non-native" not in values[garrison_value]


def test_recruit_type_options_excludes_race_incompatible_types():
    state = _state()  # HOME is a Human province
    options = recruit_type_options(state, KING_ID)
    values = [value for value, _label in options]
    assert str(_ORDINAL_BY_ARMY_TYPE[ArmyType.DRAGON_WING]) not in values


def test_recruit_type_options_excludes_ordinals_with_no_cost_data():
    # Marauders (ordinal 22) has no ARMY_TABLE entry -- resolve_recruit()
    # always rejects it outright, so it's never offered here either.
    state = _state()
    options = recruit_type_options(state, KING_ID)
    values = [value for value, _label in options]
    assert str(_ORDINAL_BY_ARMY_TYPE[ArmyType.MARAUDERS]) not in values


def test_recruit_type_options_flags_mercenary_presence():
    state = _state()
    state.add_army(ArmyState(900, None, ArmyType.BOWMEN, Quality.VETERAN, HOME, is_mercenary=True))
    options = recruit_type_options(state, KING_ID)
    values = dict(options)
    bowmen_value = str(_ORDINAL_BY_ARMY_TYPE[ArmyType.BOWMEN])
    assert "1 mercenary unit present" in values[bowmen_value]


def test_recruit_type_options_offers_a_race_incompatible_mercenary_present_type():
    # Bug fix (2026-11-18, user-reported): a mercenary band whose own
    # type isn't race-compatible with this (Human) home province at
    # all -- the user's own K1 worked example, a mercenary Whales band
    # -- used to never appear in this dropdown, even though RULES.AK
    # [3.4] ("mercenaries can be Recruited in any province by any
    # character") and turn/recruit_execution.py execute_recruit()'s own
    # hiring_existing_mercenary=True bypass both already let it
    # actually be recruited at turn-processing time.
    state = _state()  # HOME is a Human province
    state.add_army(ArmyState(900, None, ArmyType.WHALES, Quality.VETERAN, HOME, is_mercenary=True))
    options = recruit_type_options(state, KING_ID)
    values = dict(options)
    whales_value = str(_ORDINAL_BY_ARMY_TYPE[ArmyType.WHALES])
    assert whales_value in values
    assert "mercenary only" in values[whales_value]
    assert "1 mercenary unit present" in values[whales_value]


def test_recruit_type_options_still_excludes_a_race_incompatible_type_with_no_mercenary():
    state = _state()  # HOME is a Human province, no Whales band present
    options = recruit_type_options(state, KING_ID)
    values = [value for value, _label in options]
    assert str(_ORDINAL_BY_ARMY_TYPE[ArmyType.WHALES]) not in values


def test_recruit_phase_reads_its_own_dropdowns_not_the_generic_object_field():
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.RECRUIT))
    form[f"recruit_target_{KING_ID}_0"] = "self"
    bowmen = str(_ORDINAL_BY_ARMY_TYPE[ArmyType.BOWMEN])
    form[f"recruit_type_{KING_ID}_0_0"] = bowmen
    form[f"obj_{KING_ID}_0"] = "999"  # must be ignored for a Recruit phase

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=_state())

    recruit_phase = phases[0]
    assert recruit_phase.action is ActionCode.RECRUIT
    assert recruit_phase.obj == KING_ID
    assert recruit_phase.extra == [0, int(_ORDINAL_BY_ARMY_TYPE[ArmyType.BOWMEN]), -1]


def test_recruit_phase_target_garrison_resolves_to_sentinel():
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.RECRUIT))
    form[f"recruit_target_{KING_ID}_0"] = "garrison"
    form[f"recruit_type_{KING_ID}_0_0"] = str(_ORDINAL_BY_ARMY_TYPE[ArmyType.BOWMEN])

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=_state())

    assert phases[0].obj == NO_LEADER_SENTINEL


def test_recruit_phase_target_another_leader_resolves_to_that_leader_id():
    # 2026-11-06: _parse_recruit_target() now validates the posted id
    # against state (see that function's own docstring) -- leader 2
    # must be real and co-located with the King for this to pass.
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=1, name="Borin", location=HOME))
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.RECRUIT))
    form[f"recruit_target_{KING_ID}_0"] = "2"
    form[f"recruit_type_{KING_ID}_0_0"] = str(_ORDINAL_BY_ARMY_TYPE[ArmyType.BOWMEN])

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)

    assert phases[0].obj == 2


def test_recruit_phase_target_nonexistent_leader_is_rejected():
    # 2026-11-06 bug fix: _parse_recruit_target() used to take no state
    # argument at all and therefore never checked the posted id against
    # real, co-located leaders.
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.RECRUIT))
    form[f"recruit_target_{KING_ID}_0"] = "999"
    form[f"recruit_type_{KING_ID}_0_0"] = str(_ORDINAL_BY_ARMY_TYPE[ArmyType.BOWMEN])

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=_state())
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "co-located" in str(exc)


def test_recruit_phase_target_noncolocated_leader_is_rejected():
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=1, name="Borin", location=HexCoord(3, 2)))
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.RECRUIT))
    form[f"recruit_target_{KING_ID}_0"] = "2"
    form[f"recruit_type_{KING_ID}_0_0"] = str(_ORDINAL_BY_ARMY_TYPE[ArmyType.BOWMEN])

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "co-located" in str(exc)


def test_recruit_phase_target_leader_255_is_rejected_even_when_real_and_colocated():
    # 2026-11-06 bug fix: NO_LEADER_SENTINEL (255) is wire-
    # indistinguishable from "garrison" once encoded -- a real,
    # co-located leader whose own id happens to be 255 can't be named
    # as a Recruit target at all.
    state = _state()
    state.add_leader(LeaderState(leader_id=NO_LEADER_SENTINEL, kingdom_id=1, name="Unlucky", location=HOME))
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.RECRUIT))
    form[f"recruit_target_{KING_ID}_0"] = str(NO_LEADER_SENTINEL)
    form[f"recruit_type_{KING_ID}_0_0"] = str(_ORDINAL_BY_ARMY_TYPE[ArmyType.BOWMEN])

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "indistinguishable" in str(exc)


def test_recruit_phase_self_default_is_rejected_when_the_recruiting_leader_is_255():
    # 2026-11-07 bug fix: the "self"/empty branch used to return
    # leader_id straight through with no NO_LEADER_SENTINEL check,
    # unlike the explicit-other-leader branch right below it -- a Hero
    # whose own real leader_id happens to be 255, leaving the Recruit
    # target dropdown on its default "Self," used to silently recruit
    # for the Garrison Commander instead of himself.
    state = _state()
    state.add_leader(
        LeaderState(leader_id=NO_LEADER_SENTINEL, kingdom_id=1, name="Unlucky", location=HOME, skills=None)
    )
    form = _all_defend_form(NO_LEADER_SENTINEL)
    form[f"action_{NO_LEADER_SENTINEL}_0"] = str(int(ActionCode.RECRUIT))
    form[f"recruit_target_{NO_LEADER_SENTINEL}_0"] = "self"
    form[f"recruit_type_{NO_LEADER_SENTINEL}_0_0"] = str(_ORDINAL_BY_ARMY_TYPE[ArmyType.BOWMEN])

    try:
        parse_phase_inputs(form, NO_LEADER_SENTINEL, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "indistinguishable" in str(exc)


def test_recruit_phase_rejects_a_type_excluded_from_its_own_dropdown():
    # 2026-11-07 bug fix: _parse_recruit_types() used to validate a
    # posted ordinal against the full ArmyType enum rather than
    # recruit_type_options()'s own narrower, cost-table-and-race-
    # filtered set -- Vampires has no ARMY_TABLE cost entry at all, so
    # it's never offered in the dropdown, but used to pass this check.
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.RECRUIT))
    form[f"recruit_target_{KING_ID}_0"] = "self"
    form[f"recruit_type_{KING_ID}_0_0"] = str(_ORDINAL_BY_ARMY_TYPE[ArmyType.VAMPIRES])

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=_state())
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "isn't a known army type" in str(exc)


def test_recruit_phase_accepts_a_race_incompatible_mercenary_present_type():
    # Bug fix (2026-11-18, user-reported): recruit_type_options() now
    # also offers a race-incompatible type (Whales, in this Human home
    # province) when a hireable mercenary band of that exact type is
    # physically present -- this composer's own parser used to reject
    # it anyway, unconditionally, even though it's exactly what the
    # now-fixed dropdown offers.
    state = _state()
    state.add_army(ArmyState(900, None, ArmyType.WHALES, Quality.VETERAN, HOME, is_mercenary=True))
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.RECRUIT))
    form[f"recruit_target_{KING_ID}_0"] = "self"
    form[f"recruit_type_{KING_ID}_0_0"] = str(_ORDINAL_BY_ARMY_TYPE[ArmyType.WHALES])

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)

    assert phases[0].extra == [0, int(_ORDINAL_BY_ARMY_TYPE[ArmyType.WHALES]), -1]


def test_recruit_phase_type_slot_accepts_a_hand_typed_sigla_code():
    # 2026-11-18, user-requested: a free-text fallback field next to
    # the type dropdown, for typing the army type's own real 2-letter
    # code ("sigla") directly -- here Whales ("WH"), a mercenary band
    # physically present but not necessarily yet listed by this
    # preview's own dropdown in every real scenario.
    state = _state()
    state.add_army(ArmyState(900, None, ArmyType.WHALES, Quality.VETERAN, HOME, is_mercenary=True))
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.RECRUIT))
    form[f"recruit_target_{KING_ID}_0"] = "self"
    form[f"recruit_type_code_{KING_ID}_0_0"] = "wh"

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)

    assert phases[0].extra == [0, int(_ORDINAL_BY_ARMY_TYPE[ArmyType.WHALES]), -1]


def test_recruit_phase_type_slot_dropdown_wins_over_a_hand_typed_code():
    state = _state()
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.RECRUIT))
    form[f"recruit_target_{KING_ID}_0"] = "self"
    form[f"recruit_type_{KING_ID}_0_0"] = str(_ORDINAL_BY_ARMY_TYPE[ArmyType.BOWMEN])
    form[f"recruit_type_code_{KING_ID}_0_0"] = "ax"

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=_state())

    assert phases[0].extra == [0, int(_ORDINAL_BY_ARMY_TYPE[ArmyType.BOWMEN]), -1]


def test_recruit_phase_type_slot_rejects_an_unrecognized_code_as_empty():
    state = _state()
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.RECRUIT))
    form[f"recruit_target_{KING_ID}_0"] = "self"
    form[f"recruit_type_code_{KING_ID}_0_0"] = "zz"

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "choose at least one army type to Recruit" in str(exc)


def test_recruit_phase_can_list_several_types_in_one_order():
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.RECRUIT))
    form[f"recruit_target_{KING_ID}_0"] = "self"
    form[f"recruit_type_{KING_ID}_0_0"] = str(_ORDINAL_BY_ARMY_TYPE[ArmyType.BOWMEN])
    form[f"recruit_type_{KING_ID}_0_1"] = str(_ORDINAL_BY_ARMY_TYPE[ArmyType.GARRISON])

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=_state())

    assert phases[0].extra == [
        0,
        int(_ORDINAL_BY_ARMY_TYPE[ArmyType.BOWMEN]),
        int(_ORDINAL_BY_ARMY_TYPE[ArmyType.GARRISON]),
        -1,
    ]


def test_recruit_phase_without_choosing_any_type_is_rejected():
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.RECRUIT))
    form[f"recruit_target_{KING_ID}_0"] = "self"

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=_state())
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "choose at least one army type" in str(exc)


def test_recruit_phase_rejects_a_gap_between_type_slots():
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.RECRUIT))
    form[f"recruit_target_{KING_ID}_0"] = "self"
    form[f"recruit_type_{KING_ID}_0_0"] = str(_ORDINAL_BY_ARMY_TYPE[ArmyType.BOWMEN])
    form[f"recruit_type_{KING_ID}_0_2"] = str(_ORDINAL_BY_ARMY_TYPE[ArmyType.GARRISON])

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=_state())
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "follows empty slot" in str(exc)


def test_recruit_phase_rejects_an_unknown_type_ordinal_even_via_a_direct_tampered_value():
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.RECRUIT))
    form[f"recruit_target_{KING_ID}_0"] = "self"
    form[f"recruit_type_{KING_ID}_0_0"] = "999"

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=_state())
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "isn't a known army type" in str(exc)


def test_build_composed_kingdom_round_trips_a_recruit_order():
    state = _state()
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.RECRUIT))
    form[f"recruit_target_{KING_ID}_0"] = "self"
    form[f"recruit_type_{KING_ID}_0_0"] = str(_ORDINAL_BY_ARMY_TYPE[ArmyType.BOWMEN])

    kingdom = build_composed_kingdom(state, game_label="Testia", turn_number=1, kingdom_id=1, form=form)
    text = write_k1_moves_file(kingdom)
    tmp = Path(tempfile.mktemp())
    tmp.write_text(text, encoding="utf-8")
    try:
        reparsed = parse_k1_moves_file(tmp)
    finally:
        tmp.unlink(missing_ok=True)

    phase0 = reparsed.leaders[0].plan.segments[0].phases["P0"]
    assert phase0.obj == KING_ID
    assert phase0.extra == [0, int(_ORDINAL_BY_ARMY_TYPE[ArmyType.BOWMEN]), -1]


def test_disband_target_options_lists_an_army_this_leader_commands():
    state = _state()
    state.add_army(ArmyState(50, 1, ArmyType.BOWMEN, Quality.AVERAGE, HOME, commanded_by=KING_ID))

    options = disband_target_options(state, KING_ID, slot=1)

    values = dict(options)
    assert "Bowmen (Average)" in values["50"]
    assert "Aldric" in values["50"]
    assert "Numenor" in values["50"]


def test_disband_target_options_labels_a_garrison_commanded_army():
    state = _state()
    state.add_army(ArmyState(50, 1, ArmyType.BOWMEN, Quality.AVERAGE, HOME, commanded_by=None))

    options = disband_target_options(state, KING_ID, slot=1)

    values = dict(options)
    assert "Garrison" in values["50"]


def test_disband_target_options_slot_zero_offers_disband_all():
    state = _state()
    options = disband_target_options(state, KING_ID, slot=0)
    assert (DISBAND_ALL_VALUE, "ALL") in options


def test_disband_target_options_other_slots_do_not_offer_disband_all():
    state = _state()
    options = disband_target_options(state, KING_ID, slot=1)
    values = [value for value, _label in options]
    assert DISBAND_ALL_VALUE not in values


def test_disband_target_options_excludes_a_different_kingdoms_army():
    state = _state()
    state.add_kingdom(KingdomState(2, "Rivalia", Race.HUMAN, Alignment.EVIL, HexCoord(9, 9)))
    state.add_army(ArmyState(50, 2, ArmyType.BOWMEN, Quality.AVERAGE, HOME, commanded_by=None))

    options = disband_target_options(state, KING_ID, slot=1)

    values = [value for value, _label in options]
    assert "50" not in values


def test_disband_target_options_for_a_hero_excludes_a_noncolocated_army():
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=1, name="Bram", location=HexCoord(3, 2), is_king=False))
    state.add_army(ArmyState(50, 1, ArmyType.BOWMEN, Quality.AVERAGE, HOME, commanded_by=KING_ID))

    options = disband_target_options(state, 2, slot=1)

    values = [value for value, _label in options]
    assert "50" not in values


def test_disband_target_options_for_a_king_includes_a_noncolocated_army():
    state = _state()
    state.add_army(ArmyState(50, 1, ArmyType.BOWMEN, Quality.AVERAGE, HexCoord(3, 2), commanded_by=None))

    options = disband_target_options(state, KING_ID, slot=1)

    values = [value for value, _label in options]
    assert "50" in values


def test_disband_phase_reads_its_own_dropdowns_not_the_generic_object_field():
    state = _state()
    state.add_army(ArmyState(50, 1, ArmyType.BOWMEN, Quality.AVERAGE, HOME, commanded_by=KING_ID))
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.DISBAND))
    form[f"disband_target_{KING_ID}_0_0"] = "50"
    form[f"obj_{KING_ID}_0"] = "999"  # must be ignored for a Disband phase

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)

    disband_phase = phases[0]
    assert disband_phase.action is ActionCode.DISBAND
    assert disband_phase.obj == 0
    assert disband_phase.extra == [0, 50, -1]


def test_disband_phase_disband_all_collapses_to_the_sentinel():
    state = _state()
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.DISBAND))
    form[f"disband_target_{KING_ID}_0_0"] = DISBAND_ALL_VALUE

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)

    assert phases[0].extra == [0, ALL_ARMIES_SENTINEL, -1]


def test_disband_phase_disband_all_combined_with_another_slot_is_rejected():
    state = _state()
    state.add_army(ArmyState(50, 1, ArmyType.BOWMEN, Quality.AVERAGE, HOME, commanded_by=KING_ID))
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.DISBAND))
    form[f"disband_target_{KING_ID}_0_0"] = DISBAND_ALL_VALUE
    form[f"disband_target_{KING_ID}_0_1"] = "50"

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "can't be combined" in str(exc)


def test_disband_phase_rejects_a_gap_between_slots():
    state = _state()
    state.add_army(ArmyState(50, 1, ArmyType.BOWMEN, Quality.AVERAGE, HOME, commanded_by=KING_ID))
    state.add_army(ArmyState(51, 1, ArmyType.AXEMEN, Quality.AVERAGE, HOME, commanded_by=KING_ID))
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.DISBAND))
    form[f"disband_target_{KING_ID}_0_0"] = "50"
    form[f"disband_target_{KING_ID}_0_2"] = "51"

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "follows empty slot" in str(exc)


def test_disband_phase_rejects_an_army_this_leader_cannot_disband_even_via_a_direct_tampered_value():
    state = _state()
    state.add_kingdom(KingdomState(2, "Rivalia", Race.HUMAN, Alignment.EVIL, HexCoord(9, 9)))
    state.add_army(ArmyState(50, 2, ArmyType.BOWMEN, Quality.AVERAGE, HOME, commanded_by=None))
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.DISBAND))
    form[f"disband_target_{KING_ID}_0_0"] = "50"  # a different Kingdom's army, never offered in the dropdown

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "isn't an army this leader can Disband" in str(exc)


def test_disband_phase_without_choosing_any_target_is_rejected():
    state = _state()
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.DISBAND))

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "choose at least one army to Disband" in str(exc)


def test_disband_phase_rejects_a_lone_army_255_as_a_wire_ambiguous_collision():
    # 2026-11-06 bug fix: a specific-list order of exactly [255] is
    # wire-indistinguishable from DISBAND_ALL_VALUE once encoded --
    # GameState.new_army_id() is an uncapped counter, so a real army
    # can genuinely reach id 255 in a long-running game.
    state = _state()
    state.add_army(ArmyState(ALL_ARMIES_SENTINEL, 1, ArmyType.BOWMEN, Quality.AVERAGE, HOME, commanded_by=KING_ID))
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.DISBAND))
    form[f"disband_target_{KING_ID}_0_0"] = str(ALL_ARMIES_SENTINEL)

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "indistinguishable" in str(exc)


def test_build_composed_kingdom_round_trips_a_disband_order():
    state = _state()
    state.add_army(ArmyState(50, 1, ArmyType.BOWMEN, Quality.AVERAGE, HOME, commanded_by=KING_ID))
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.DISBAND))
    form[f"disband_target_{KING_ID}_0_0"] = "50"

    kingdom = build_composed_kingdom(state, game_label="Testia", turn_number=1, kingdom_id=1, form=form)
    text = write_k1_moves_file(kingdom)
    tmp = Path(tempfile.mktemp())
    tmp.write_text(text, encoding="utf-8")
    try:
        reparsed = parse_k1_moves_file(tmp)
    finally:
        tmp.unlink(missing_ok=True)

    phase0 = reparsed.leaders[0].plan.segments[0].phases["P0"]
    assert phase0.action is ActionCode.DISBAND
    assert phase0.obj == 0
    assert phase0.extra == [0, 50, -1]


def test_leave_target_options_offers_a_colocated_leader_and_garrison():
    state = _state()
    state.add_army(ArmyState(50, 1, ArmyType.BOWMEN, Quality.AVERAGE, HOME, commanded_by=KING_ID))
    state.add_leader(LeaderState(leader_id=2, kingdom_id=1, name="Bram", location=HOME))

    options = leave_target_options(state, KING_ID)

    assert ("2", "Bram") in options
    assert (LEAVE_GARRISON_VALUE, "Garrison Commander") in options


def test_leave_target_options_excludes_a_noncolocated_leader():
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=1, name="Elsewhere", location=HexCoord(3, 2)))

    options = leave_target_options(state, KING_ID)

    values = [value for value, _label in options]
    assert "2" not in values


def test_leave_target_options_excludes_a_hostile_leader():
    state = _state()
    state.add_kingdom(KingdomState(2, "Rivalia", Race.HUMAN, Alignment.EVIL, HexCoord(9, 9)))
    state.add_leader(LeaderState(leader_id=2, kingdom_id=2, name="Hostile Hero", location=HOME))

    options = leave_target_options(state, KING_ID)

    values = [value for value, _label in options]
    assert "2" not in values


def test_leave_target_options_includes_an_allied_kingdoms_colocated_leader():
    state = _state()
    state.add_kingdom(KingdomState(2, "Allia", Race.HUMAN, Alignment.GOOD, HexCoord(9, 9)))
    state.allied_kingdoms.add(frozenset({1, 2}))
    state.add_leader(LeaderState(leader_id=2, kingdom_id=2, name="Allied Hero", location=HOME))

    options = leave_target_options(state, KING_ID)

    values = dict(options)
    assert values["2"] == "Allied Hero, Allia"


def test_leave_army_target_options_lists_an_army_this_leader_commands():
    state = _state()
    state.add_army(ArmyState(50, 1, ArmyType.BOWMEN, Quality.AVERAGE, HOME, commanded_by=KING_ID))

    options = leave_army_target_options(state, KING_ID, slot=1)

    values = [value for value, _label in options]
    assert "50" in values


def test_leave_army_target_options_includes_a_colocated_garrison_commanded_army():
    # The rulebook's own "novità": passing a Garrison-commanded army
    # along to another Hero.
    state = _state()
    state.add_army(ArmyState(50, 1, ArmyType.BOWMEN, Quality.AVERAGE, HOME, commanded_by=None))

    options = leave_army_target_options(state, KING_ID, slot=1)

    values = [value for value, _label in options]
    assert "50" in values


def test_leave_army_target_options_excludes_a_noncolocated_garrison_commanded_army():
    state = _state()
    state.add_army(ArmyState(50, 1, ArmyType.BOWMEN, Quality.AVERAGE, HexCoord(3, 2), commanded_by=None))

    options = leave_army_target_options(state, KING_ID, slot=1)

    values = [value for value, _label in options]
    assert "50" not in values


def test_leave_army_target_options_excludes_an_army_commanded_by_someone_else():
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=1, name="Bram", location=HOME))
    state.add_army(ArmyState(50, 1, ArmyType.BOWMEN, Quality.AVERAGE, HOME, commanded_by=2))

    options = leave_army_target_options(state, KING_ID, slot=1)

    values = [value for value, _label in options]
    assert "50" not in values


def test_leave_army_target_options_slot_zero_offers_leave_all():
    state = _state()
    options = leave_army_target_options(state, KING_ID, slot=0)
    assert (LEAVE_ALL_VALUE, "ALL") in options


def test_leave_army_target_options_other_slots_do_not_offer_leave_all():
    state = _state()
    options = leave_army_target_options(state, KING_ID, slot=1)
    values = [value for value, _label in options]
    assert LEAVE_ALL_VALUE not in values


def test_leave_phase_reads_its_own_dropdowns_not_the_generic_object_field():
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=1, name="Bram", location=HOME))
    state.add_army(ArmyState(50, 1, ArmyType.BOWMEN, Quality.AVERAGE, HOME, commanded_by=KING_ID))
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.LEAVE))
    form[f"leave_target_{KING_ID}_0"] = "2"
    form[f"leave_army_{KING_ID}_0_0"] = "50"
    form[f"obj_{KING_ID}_0"] = "999"  # must be ignored for a Leave phase

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)

    leave_phase = phases[0]
    assert leave_phase.action is ActionCode.LEAVE
    assert leave_phase.obj == 0
    assert leave_phase.extra == [2, 50, -1]


def test_leave_phase_garrison_target_resolves_to_sentinel():
    state = _state()
    state.add_army(ArmyState(50, 1, ArmyType.BOWMEN, Quality.AVERAGE, HOME, commanded_by=KING_ID))
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.LEAVE))
    form[f"leave_target_{KING_ID}_0"] = LEAVE_GARRISON_VALUE
    form[f"leave_army_{KING_ID}_0_0"] = "50"

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)

    assert phases[0].extra == [NO_LEADER_SENTINEL, 50, -1]


def test_leave_phase_rejects_a_hostile_target_even_via_a_direct_tampered_value():
    state = _state()
    state.add_kingdom(KingdomState(2, "Rivalia", Race.HUMAN, Alignment.EVIL, HexCoord(9, 9)))
    state.add_leader(LeaderState(leader_id=2, kingdom_id=2, name="Hostile Hero", location=HOME))
    state.add_army(ArmyState(50, 1, ArmyType.BOWMEN, Quality.AVERAGE, HOME, commanded_by=KING_ID))
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.LEAVE))
    form[f"leave_target_{KING_ID}_0"] = "2"
    form[f"leave_army_{KING_ID}_0_0"] = "50"

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "own Kingdom or an ally's" in str(exc)


def test_leave_phase_rejects_self_as_the_target():
    # 2026-11-06 bug fix: a Kingdom is trivially "allied" with itself,
    # so this used to pass straight through, even though leave_target_
    # options() already excludes the acting leader's own id from the
    # dropdown and every structurally analogous target parser
    # (Trail/Challenge/Hire/Charm/Kill Enemy) rejects self-targeting.
    state = _state()
    state.add_army(ArmyState(50, 1, ArmyType.BOWMEN, Quality.AVERAGE, HOME, commanded_by=KING_ID))
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.LEAVE))
    form[f"leave_target_{KING_ID}_0"] = str(KING_ID)
    form[f"leave_army_{KING_ID}_0_0"] = "50"

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "Leave an army to himself" in str(exc)


def test_leave_phase_rejects_target_leader_255_even_when_real_and_allied():
    # 2026-11-06 bug fix: NO_LEADER_SENTINEL (255) is wire-
    # indistinguishable from LEAVE_GARRISON_VALUE once encoded -- a
    # real, allied leader whose own id happens to be 255 can't be
    # named as a Leave target at all.
    state = _state()
    state.add_leader(LeaderState(leader_id=NO_LEADER_SENTINEL, kingdom_id=1, name="Unlucky", location=HOME))
    state.add_army(ArmyState(50, 1, ArmyType.BOWMEN, Quality.AVERAGE, HOME, commanded_by=KING_ID))
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.LEAVE))
    form[f"leave_target_{KING_ID}_0"] = str(NO_LEADER_SENTINEL)
    form[f"leave_army_{KING_ID}_0_0"] = "50"

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "indistinguishable" in str(exc)


def test_leave_phase_rejects_a_lone_army_255_as_a_wire_ambiguous_collision():
    # 2026-11-06 bug fix: a specific-list order of exactly [255] is
    # wire-indistinguishable from LEAVE_ALL_VALUE once encoded.
    state = _state()
    state.add_army(ArmyState(ALL_ARMIES_SENTINEL, 1, ArmyType.BOWMEN, Quality.AVERAGE, HOME, commanded_by=KING_ID))
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.LEAVE))
    form[f"leave_target_{KING_ID}_0"] = LEAVE_GARRISON_VALUE
    form[f"leave_army_{KING_ID}_0_0"] = str(ALL_ARMIES_SENTINEL)

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "indistinguishable" in str(exc)


def test_leave_phase_leave_all_collapses_to_the_sentinel():
    state = _state()
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.LEAVE))
    form[f"leave_target_{KING_ID}_0"] = LEAVE_GARRISON_VALUE
    form[f"leave_army_{KING_ID}_0_0"] = LEAVE_ALL_VALUE

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)

    assert phases[0].extra == [NO_LEADER_SENTINEL, ALL_ARMIES_SENTINEL, -1]


def test_leave_phase_leave_all_combined_with_another_slot_is_rejected():
    state = _state()
    state.add_army(ArmyState(50, 1, ArmyType.BOWMEN, Quality.AVERAGE, HOME, commanded_by=KING_ID))
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.LEAVE))
    form[f"leave_target_{KING_ID}_0"] = LEAVE_GARRISON_VALUE
    form[f"leave_army_{KING_ID}_0_0"] = LEAVE_ALL_VALUE
    form[f"leave_army_{KING_ID}_0_1"] = "50"

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "can't be combined" in str(exc)


def test_leave_phase_rejects_a_gap_between_slots():
    state = _state()
    state.add_army(ArmyState(50, 1, ArmyType.BOWMEN, Quality.AVERAGE, HOME, commanded_by=KING_ID))
    state.add_army(ArmyState(51, 1, ArmyType.AXEMEN, Quality.AVERAGE, HOME, commanded_by=KING_ID))
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.LEAVE))
    form[f"leave_target_{KING_ID}_0"] = LEAVE_GARRISON_VALUE
    form[f"leave_army_{KING_ID}_0_0"] = "50"
    form[f"leave_army_{KING_ID}_0_2"] = "51"

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "follows empty slot" in str(exc)


def test_leave_phase_rejects_an_army_this_leader_cannot_leave_even_via_a_direct_tampered_value():
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=1, name="Bram", location=HOME))
    state.add_army(ArmyState(50, 1, ArmyType.BOWMEN, Quality.AVERAGE, HOME, commanded_by=2))
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.LEAVE))
    form[f"leave_target_{KING_ID}_0"] = LEAVE_GARRISON_VALUE
    form[f"leave_army_{KING_ID}_0_0"] = "50"  # commanded by someone else, never offered in the dropdown

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "isn't an army this leader can Leave" in str(exc)


def test_leave_phase_without_choosing_any_target_is_rejected():
    state = _state()
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.LEAVE))
    form[f"leave_target_{KING_ID}_0"] = LEAVE_GARRISON_VALUE

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "choose at least one army to Leave" in str(exc)


def test_build_composed_kingdom_round_trips_a_leave_order():
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=1, name="Bram", location=HOME))
    state.add_army(ArmyState(50, 1, ArmyType.BOWMEN, Quality.AVERAGE, HOME, commanded_by=KING_ID))
    form = {**_all_defend_form(KING_ID), **_all_defend_form(2)}
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.LEAVE))
    form[f"leave_target_{KING_ID}_0"] = "2"
    form[f"leave_army_{KING_ID}_0_0"] = "50"

    kingdom = build_composed_kingdom(state, game_label="Testia", turn_number=1, kingdom_id=1, form=form)
    text = write_k1_moves_file(kingdom)
    tmp = Path(tempfile.mktemp())
    tmp.write_text(text, encoding="utf-8")
    try:
        reparsed = parse_k1_moves_file(tmp)
    finally:
        tmp.unlink(missing_ok=True)

    phase0 = reparsed.leaders[0].plan.segments[0].phases["P0"]
    assert phase0.action is ActionCode.LEAVE
    assert phase0.obj == 0
    assert phase0.extra == [2, 50, -1]


def test_pick_up_army_target_options_lists_a_colocated_army_of_either_commander():
    # The user's own explicit choice: unlike Leave/Disband, Pick Up may
    # take over an army actively commanded by anyone, as long as it's
    # of the acting leader's own Kingdom.
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=1, name="Bram", location=HOME))
    state.add_army(ArmyState(50, 1, ArmyType.BOWMEN, Quality.AVERAGE, HOME, commanded_by=2))

    options = pick_up_army_target_options(state, KING_ID, slot=1)

    values = [value for value, _label in options]
    assert "50" in values


def test_pick_up_army_target_options_excludes_a_different_kingdoms_colocated_army():
    state = _state()
    state.add_kingdom(KingdomState(2, "Rivalia", Race.HUMAN, Alignment.EVIL, HexCoord(9, 9)))
    state.add_army(ArmyState(50, 2, ArmyType.BOWMEN, Quality.AVERAGE, HOME, commanded_by=None))

    options = pick_up_army_target_options(state, KING_ID, slot=1)

    values = [value for value, _label in options]
    assert "50" not in values


def test_pick_up_army_target_options_excludes_a_noncolocated_army():
    state = _state()
    state.add_army(ArmyState(50, 1, ArmyType.BOWMEN, Quality.AVERAGE, HexCoord(3, 2), commanded_by=None))

    options = pick_up_army_target_options(state, KING_ID, slot=1)

    values = [value for value, _label in options]
    assert "50" not in values


def test_pick_up_army_target_options_excludes_an_army_recruited_this_turn():
    state = _state()
    state.add_army(ArmyState(50, 1, ArmyType.BOWMEN, Quality.AVERAGE, HOME, commanded_by=None, recruited_this_turn=True))

    options = pick_up_army_target_options(state, KING_ID, slot=1)

    values = [value for value, _label in options]
    assert "50" not in values


def test_pick_up_army_target_options_includes_a_mercenary_recruited_this_turn():
    state = _state()
    state.add_army(
        ArmyState(
            50, 1, ArmyType.BOWMEN, Quality.VETERAN, HOME, commanded_by=None,
            recruited_this_turn=True, is_mercenary=True,
        )
    )

    options = pick_up_army_target_options(state, KING_ID, slot=1)

    values = [value for value, _label in options]
    assert "50" in values


def test_pick_up_army_target_options_slot_zero_offers_pick_up_all():
    state = _state()
    options = pick_up_army_target_options(state, KING_ID, slot=0)
    assert (PICK_UP_ALL_VALUE, "ALL") in options


def test_pick_up_army_target_options_other_slots_do_not_offer_pick_up_all():
    state = _state()
    options = pick_up_army_target_options(state, KING_ID, slot=1)
    values = [value for value, _label in options]
    assert PICK_UP_ALL_VALUE not in values


def test_pick_up_phase_reads_its_own_dropdown_not_the_generic_object_field():
    state = _state()
    state.add_army(ArmyState(50, 1, ArmyType.BOWMEN, Quality.AVERAGE, HOME, commanded_by=None))
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.PICK_UP))
    form[f"pick_up_target_{KING_ID}_0_0"] = "50"
    form[f"obj_{KING_ID}_0"] = "999"  # must be ignored for a Pick Up phase

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)

    pick_up_phase = phases[0]
    assert pick_up_phase.action is ActionCode.PICK_UP
    assert pick_up_phase.obj == 0
    assert pick_up_phase.extra == [0, 50, -1]


def test_pick_up_phase_pick_up_all_collapses_to_the_sentinel():
    state = _state()
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.PICK_UP))
    form[f"pick_up_target_{KING_ID}_0_0"] = PICK_UP_ALL_VALUE

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)

    assert phases[0].extra == [0, ALL_ARMIES_SENTINEL, -1]


def test_pick_up_phase_pick_up_all_combined_with_another_slot_is_rejected():
    state = _state()
    state.add_army(ArmyState(50, 1, ArmyType.BOWMEN, Quality.AVERAGE, HOME, commanded_by=None))
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.PICK_UP))
    form[f"pick_up_target_{KING_ID}_0_0"] = PICK_UP_ALL_VALUE
    form[f"pick_up_target_{KING_ID}_0_1"] = "50"

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "can't be combined" in str(exc)


def test_pick_up_phase_rejects_a_gap_between_slots():
    state = _state()
    state.add_army(ArmyState(50, 1, ArmyType.BOWMEN, Quality.AVERAGE, HOME, commanded_by=None))
    state.add_army(ArmyState(51, 1, ArmyType.AXEMEN, Quality.AVERAGE, HOME, commanded_by=None))
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.PICK_UP))
    form[f"pick_up_target_{KING_ID}_0_0"] = "50"
    form[f"pick_up_target_{KING_ID}_0_2"] = "51"

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "follows empty slot" in str(exc)


def test_pick_up_phase_rejects_an_army_this_leader_cannot_pick_up_even_via_a_direct_tampered_value():
    state = _state()
    state.add_army(ArmyState(50, 1, ArmyType.BOWMEN, Quality.AVERAGE, HOME, commanded_by=None, recruited_this_turn=True))
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.PICK_UP))
    form[f"pick_up_target_{KING_ID}_0_0"] = "50"  # recruited this turn, never offered in the dropdown

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "isn't an army this leader can Pick Up" in str(exc)


def test_pick_up_phase_without_choosing_any_target_is_rejected():
    state = _state()
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.PICK_UP))

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "choose at least one army to Pick Up" in str(exc)


def test_pick_up_phase_rejects_a_lone_army_255_as_a_wire_ambiguous_collision():
    # 2026-11-06 bug fix: a specific-list order of exactly [255] is
    # wire-indistinguishable from PICK_UP_ALL_VALUE once encoded.
    state = _state()
    state.add_army(ArmyState(ALL_ARMIES_SENTINEL, 1, ArmyType.BOWMEN, Quality.AVERAGE, HOME, commanded_by=None))
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.PICK_UP))
    form[f"pick_up_target_{KING_ID}_0_0"] = str(ALL_ARMIES_SENTINEL)

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "indistinguishable" in str(exc)


def test_build_composed_kingdom_round_trips_a_pick_up_order():
    state = _state()
    state.add_army(ArmyState(50, 1, ArmyType.BOWMEN, Quality.AVERAGE, HOME, commanded_by=None))
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.PICK_UP))
    form[f"pick_up_target_{KING_ID}_0_0"] = "50"

    kingdom = build_composed_kingdom(state, game_label="Testia", turn_number=1, kingdom_id=1, form=form)
    text = write_k1_moves_file(kingdom)
    tmp = Path(tempfile.mktemp())
    tmp.write_text(text, encoding="utf-8")
    try:
        reparsed = parse_k1_moves_file(tmp)
    finally:
        tmp.unlink(missing_ok=True)

    phase0 = reparsed.leaders[0].plan.segments[0].phases["P0"]
    assert phase0.action is ActionCode.PICK_UP
    assert phase0.obj == 0
    assert phase0.extra == [0, 50, -1]


def test_trade_recipient_options_lists_a_colocated_leader_of_any_kingdom():
    state = _state()
    state.add_kingdom(KingdomState(2, "Allia", Race.HUMAN, Alignment.GOOD, HexCoord(9, 9)))
    state.add_leader(LeaderState(leader_id=2, kingdom_id=2, name="Guest", location=HOME))

    options = trade_recipient_options(state, KING_ID)

    values = dict(options)
    assert values["2"] == "Guest, Allia"


def test_trade_recipient_options_excludes_a_noncolocated_leader():
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=1, name="Elsewhere", location=HexCoord(3, 2)))

    options = trade_recipient_options(state, KING_ID)

    values = [value for value, _label in options]
    assert "2" not in values


def test_trade_recipient_options_includes_self_for_curator_titleholder():
    state = _state()
    # _state() already gives KING_ID one item (WAND_FIREBALL); two more
    # (BOOK_WHITE, ABILITY_MELEE) reach OFFICE_MIN_POINTS[Office.CURATOR]
    # (3), matching tests/test_plan_dispatch.py's own Curator fixture.
    state.add_item(Treasure.BOOK_WHITE, owner_leader_id=KING_ID)
    state.add_item(Treasure.ABILITY_MELEE, owner_leader_id=KING_ID)

    options = trade_recipient_options(state, KING_ID)

    values = dict(options)
    assert values[str(KING_ID)] == "Self (research an item's magical function)"


def test_trade_recipient_options_excludes_self_when_not_curator():
    state = _state()
    options = trade_recipient_options(state, KING_ID)
    values = [value for value, _label in options]
    assert str(KING_ID) not in values


def test_trade_recipient_options_includes_a_noncolocated_blackmail_king():
    state = _state()
    state.add_kingdom(KingdomState(2, "Spyria", Race.HUMAN, Alignment.EVIL, HexCoord(9, 9)))
    state.add_leader(LeaderState(leader_id=2, kingdom_id=2, name="Spymaster King", location=HexCoord(9, 9), is_king=True))
    state.kingdoms[1].active_blackmail = BlackmailClaim(spy_leader_id=2, spy_kingdom_id=2, amount=15)

    options = trade_recipient_options(state, KING_ID)

    values = dict(options)
    assert values["2"] == "Pay blackmail: Spymaster King, Spyria (15 gold owed)"


def test_trade_gift_options_lists_owned_items_and_gold():
    state = _state()
    options = trade_gift_options(state, KING_ID)
    item_id = state.items_held_by(KING_ID)[0].item_id
    values = dict(options)
    assert values["gold"] == "Gold (type an amount)"
    assert f"#{item_id}" in values[str(item_id)]


def test_trade_gift_options_excludes_the_valhalla_fixed_item():
    state = _state()
    item_id = state.items_held_by(KING_ID)[0].item_id
    state.leaders[KING_ID].valhalla_fixed_item_id = item_id

    options = trade_gift_options(state, KING_ID)

    values = [value for value, _label in options]
    assert str(item_id) not in values


def test_trade_phase_reads_its_own_dropdowns_for_an_item_gift():
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=1, name="Bram", location=HOME))
    item_id = state.items_held_by(KING_ID)[0].item_id
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.TRADE))
    form[f"trade_recipient_{KING_ID}_0"] = "2"
    form[f"trade_gift_{KING_ID}_0"] = str(item_id)
    form[f"obj_{KING_ID}_0"] = "999"  # must be ignored for a Give phase

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)

    trade_phase = phases[0]
    assert trade_phase.action is ActionCode.TRADE
    assert trade_phase.obj == item_id
    assert trade_phase.extra == [0, 2]


def test_trade_phase_reads_a_hand_typed_item_number_via_its_own_pseudo_option():
    # 2026-11-16, user-requested: selecting TRADE_ITEM_NUMBER_VALUE in
    # the gift dropdown reveals trade_gift_number, a sibling free-text
    # field naming the same item id the dropdown itself would.
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=1, name="Bram", location=HOME))
    item_id = state.items_held_by(KING_ID)[0].item_id
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.TRADE))
    form[f"trade_recipient_{KING_ID}_0"] = "2"
    form[f"trade_gift_{KING_ID}_0"] = "item_number"
    form[f"trade_gift_number_{KING_ID}_0"] = str(item_id)

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)

    trade_phase = phases[0]
    assert trade_phase.obj == item_id
    assert trade_phase.extra == [0, 2]


def test_trade_phase_gold_gift_reads_the_free_text_amount():
    state = _state()
    state.add_kingdom(KingdomState(2, "Allia", Race.HUMAN, Alignment.GOOD, HexCoord(9, 9)))
    state.add_leader(LeaderState(leader_id=2, kingdom_id=2, name="Bram", location=HOME, is_king=True))
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.TRADE))
    form[f"trade_recipient_{KING_ID}_0"] = "2"
    form[f"trade_gift_{KING_ID}_0"] = "gold"
    form[f"trade_gold_{KING_ID}_0"] = "5"

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)

    assert phases[0].obj == 5
    assert phases[0].extra == [0, 2]


def test_trade_phase_from_leader_zero_avoids_the_secret_spell_collision():
    # 2026-11-06 bug fix: extra[0] used to be hardcoded 0 unconditionally
    # -- turn/trade_decode.py rewrite_trade_as_secret_spell_cast() reads
    # extra[0] == leader_id as "this Give is really a self-targeted
    # secret-spell Cast in disguise," which a hardcoded 0 silently
    # satisfies for a King whose own leader_id is 0 (real in this
    # project's own 0-indexed original-format game imports). extra[0]
    # must differ from the acting leader's own id instead.
    state = GameState()
    state.board_width = BOARD_WIDTH
    state.board_height = BOARD_HEIGHT
    state.add_kingdom(KingdomState(0, "Zeroia", Race.HUMAN, Alignment.GOOD, HOME))
    state.add_kingdom(KingdomState(2, "Allia", Race.HUMAN, Alignment.GOOD, HexCoord(9, 9)))
    state.add_leader(LeaderState(leader_id=0, kingdom_id=0, name="King Zero", location=HOME, is_king=True))
    state.add_leader(LeaderState(leader_id=2, kingdom_id=2, name="Bram", location=HOME, is_king=True))
    form = _all_defend_form(0)
    form["action_0_0"] = str(int(ActionCode.TRADE))
    form["trade_recipient_0_0"] = "2"
    form["trade_gift_0_0"] = "gold"
    form["trade_gold_0_0"] = "5"

    phases = parse_phase_inputs(form, 0, board_width=BOARD_WIDTH, state=state)

    assert phases[0].extra == [1, 2]


def test_trade_phase_without_choosing_a_recipient_is_rejected():
    state = _state()
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.TRADE))
    form[f"trade_gift_{KING_ID}_0"] = "gold"
    form[f"trade_gold_{KING_ID}_0"] = "5"

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "choose a Give recipient" in str(exc)


def test_trade_phase_rejects_a_noncolocated_recipient_even_via_a_direct_tampered_value():
    # 2026-11-07 bug fix: _parse_trade_recipient() used to only check
    # that the posted id resolved to *some* real leader, unlike every
    # sibling target parser -- a real, non-co-located, non-Curator,
    # non-blackmail leader anywhere else in the game used to pass.
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=1, name="Elsewhere", location=HexCoord(3, 2)))
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.TRADE))
    form[f"trade_recipient_{KING_ID}_0"] = "2"
    form[f"trade_gift_{KING_ID}_0"] = "gold"
    form[f"trade_gold_{KING_ID}_0"] = "5"

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "choose a Give recipient" in str(exc)


def test_trade_phase_rejects_an_item_not_owned_even_via_a_direct_tampered_value():
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=1, name="Bram", location=HOME))
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.TRADE))
    form[f"trade_recipient_{KING_ID}_0"] = "2"
    form[f"trade_gift_{KING_ID}_0"] = "999999"  # never owned, never offered in the dropdown

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "choose an item this leader owns to Give" in str(exc)


def test_trade_phase_rejects_a_non_positive_gold_amount():
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=1, name="Bram", location=HOME, is_king=True))
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.TRADE))
    form[f"trade_recipient_{KING_ID}_0"] = "2"
    form[f"trade_gift_{KING_ID}_0"] = "gold"
    form[f"trade_gold_{KING_ID}_0"] = "0"

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "must be a positive number" in str(exc)


def test_trade_phase_rejects_a_gold_amount_that_collides_with_an_owned_item_id():
    # 2026-11-07 bug fix: RULES.AK [3.18]'s own documented warning --
    # turn/trade_execution.py execute_give() disambiguates obj by
    # checking item ownership FIRST, so "Give <N> gold" while owning
    # item #N would silently transfer the item instead of the gold.
    state = _state()  # already owns one item (WAND_FIREBALL) -- see _state()'s own setup
    item_id = next(iter(state.items))
    state.add_kingdom(KingdomState(2, "Allia", Race.HUMAN, Alignment.GOOD, HexCoord(9, 9)))
    state.add_leader(LeaderState(leader_id=2, kingdom_id=2, name="Bram", location=HOME, is_king=True))
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.TRADE))
    form[f"trade_recipient_{KING_ID}_0"] = "2"
    form[f"trade_gift_{KING_ID}_0"] = "gold"
    form[f"trade_gold_{KING_ID}_0"] = str(item_id)

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert f"owns item #{item_id}" in str(exc)


def test_trade_phase_rejects_a_gold_gift_to_the_givers_own_kingdom():
    # Bug fix, sourced directly from the user (2026-10-29), independently
    # confirmed in both RULES.AK and ADDEND.AK: a gold gift's recipient
    # must belong to a genuinely different Kingdom -- unlike the item
    # path, which crosses Kingdoms freely with no such restriction.
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=1, name="Bram", location=HOME, is_king=True))
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.TRADE))
    form[f"trade_recipient_{KING_ID}_0"] = "2"
    form[f"trade_gift_{KING_ID}_0"] = "gold"
    form[f"trade_gold_{KING_ID}_0"] = "5"

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "must belong to a different Kingdom" in str(exc)


def test_build_composed_kingdom_round_trips_a_trade_item_give():
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=1, name="Bram", location=HOME))
    item_id = state.items_held_by(KING_ID)[0].item_id
    form = {**_all_defend_form(KING_ID), **_all_defend_form(2)}
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.TRADE))
    form[f"trade_recipient_{KING_ID}_0"] = "2"
    form[f"trade_gift_{KING_ID}_0"] = str(item_id)

    kingdom = build_composed_kingdom(state, game_label="Testia", turn_number=1, kingdom_id=1, form=form)
    text = write_k1_moves_file(kingdom)
    tmp = Path(tempfile.mktemp())
    tmp.write_text(text, encoding="utf-8")
    try:
        reparsed = parse_k1_moves_file(tmp)
    finally:
        tmp.unlink(missing_ok=True)

    phase0 = reparsed.leaders[0].plan.segments[0].phases["P0"]
    assert phase0.action is ActionCode.TRADE
    assert phase0.obj == item_id
    assert phase0.extra == [0, 2]


def test_practice_ability_options_lists_every_ability_by_display_name():
    options = practice_ability_options()

    assert options[0] == (Ability.TACTICAL.value, ABILITY_NAME[Ability.TACTICAL])
    assert len(options) == len(list(Ability))
    assert (Ability.SAGE.value, ABILITY_NAME[Ability.SAGE]) in options


def test_practice_phase_reads_its_own_ability_dropdown():
    state = _state()
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.PRACTICE))
    form[f"practice_ability_{KING_ID}_0"] = str(Ability.SAGE.value)
    form[f"obj_{KING_ID}_0"] = "999"  # must be ignored for a Practice phase
    form[f"extra_{KING_ID}_0"] = "5"  # must be ignored too -- always [0]

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)

    practice_phase = phases[0]
    assert practice_phase.action is ActionCode.PRACTICE
    assert practice_phase.obj == Ability.SAGE.value
    assert practice_phase.extra == [0]


def test_practice_phase_without_choosing_an_ability_is_rejected():
    state = _state()
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.PRACTICE))

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "choose a Talent to Practice" in str(exc)


def test_practice_phase_rejects_an_out_of_range_ability_even_via_a_direct_tampered_value():
    state = _state()
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.PRACTICE))
    form[f"practice_ability_{KING_ID}_0"] = "999999"  # never offered in the dropdown

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "choose a Talent to Practice" in str(exc)


def test_build_composed_kingdom_round_trips_a_practice_order():
    state = _state()
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.PRACTICE))
    form[f"practice_ability_{KING_ID}_0"] = str(Ability.NECROMANCY.value)

    kingdom = build_composed_kingdom(state, game_label="Testia", turn_number=1, kingdom_id=1, form=form)
    text = write_k1_moves_file(kingdom)
    tmp = Path(tempfile.mktemp())
    tmp.write_text(text, encoding="utf-8")
    try:
        reparsed = parse_k1_moves_file(tmp)
    finally:
        tmp.unlink(missing_ok=True)

    phase0 = reparsed.leaders[0].plan.segments[0].phases["P0"]
    assert phase0.action is ActionCode.PRACTICE
    assert phase0.obj == Ability.NECROMANCY.value
    assert phase0.extra == [0]


def test_trail_target_options_lists_every_other_leader_any_kingdom_no_colocation_needed():
    state = _state()
    state.add_kingdom(KingdomState(2, "Allia", Race.HUMAN, Alignment.GOOD, HexCoord(9, 9)))
    state.add_leader(LeaderState(leader_id=2, kingdom_id=2, name="Bram", location=HexCoord(9, 9), is_king=True))
    state.add_leader(LeaderState(leader_id=3, kingdom_id=None, name="Wanda", location=HOME))

    options = trail_target_options(state, KING_ID)

    values = {value for value, _label in options}
    assert values == {"2", "3"}
    assert str(KING_ID) not in values  # never offers the acting leader himself


def test_trail_phase_reads_its_own_target_dropdown():
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=1, name="Bram", location=HexCoord(9, 9)))
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.TRAIL))
    form[f"trail_target_{KING_ID}_0"] = "2"
    form[f"obj_{KING_ID}_0"] = "999"  # must be ignored for a Trail phase
    form[f"extra_{KING_ID}_0"] = "5"  # must be ignored too -- always [0]

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)

    trail_phase = phases[0]
    assert trail_phase.action is ActionCode.TRAIL
    assert trail_phase.obj == 2
    assert trail_phase.extra == [0]


def test_trail_phase_reads_a_hand_typed_target_number_when_the_dropdown_is_empty():
    # 2026-11-16, user-requested: trail_target_number is a sibling
    # free-text fallback to trail_target's own dropdown.
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=1, name="Bram", location=HexCoord(9, 9)))
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.TRAIL))
    form[f"trail_target_number_{KING_ID}_0"] = "2"

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)

    assert phases[0].obj == 2


def test_trail_phase_without_choosing_a_target_is_rejected():
    state = _state()
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.TRAIL))

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "choose a Trail target" in str(exc)


def test_trail_phase_rejects_targeting_self_even_via_a_direct_tampered_value():
    state = _state()
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.TRAIL))
    form[f"trail_target_{KING_ID}_0"] = str(KING_ID)  # never offered in the dropdown

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "choose a Trail target" in str(exc)


def test_trail_phase_rejects_an_unknown_target_even_via_a_direct_tampered_value():
    state = _state()
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.TRAIL))
    form[f"trail_target_{KING_ID}_0"] = "999999"  # never offered in the dropdown

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "choose a Trail target" in str(exc)


def test_trail_phase_rejects_a_trailer_who_already_commands_an_army():
    # Rulebook [3.17]: "Un personaggio che comanda un'unita' militare non
    # puo' ricevere il comando Trail" -- enforced at compose time, not
    # just at turn-processing time (turn/trail_execution.py execute_
    # trail()'s own identical check).
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=1, name="Bram", location=HexCoord(9, 9)))
    state.add_army(ArmyState(50, 1, ArmyType.BOWMEN, Quality.AVERAGE, HOME, commanded_by=KING_ID))
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.TRAIL))
    form[f"trail_target_{KING_ID}_0"] = "2"

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "a character leading an army may not be ordered to Trail" in str(exc)


def test_build_composed_kingdom_round_trips_a_trail_order():
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=1, name="Bram", location=HexCoord(9, 9)))
    form = {**_all_defend_form(KING_ID), **_all_defend_form(2)}
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.TRAIL))
    form[f"trail_target_{KING_ID}_0"] = "2"

    kingdom = build_composed_kingdom(state, game_label="Testia", turn_number=1, kingdom_id=1, form=form)
    text = write_k1_moves_file(kingdom)
    tmp = Path(tempfile.mktemp())
    tmp.write_text(text, encoding="utf-8")
    try:
        reparsed = parse_k1_moves_file(tmp)
    finally:
        tmp.unlink(missing_ok=True)

    phase0 = reparsed.leaders[0].plan.segments[0].phases["P0"]
    assert phase0.action is ActionCode.TRAIL
    assert phase0.obj == 2
    assert phase0.extra == [0]


def test_tactic_options_includes_give_only_when_allow_give():
    # Rulebook [3.12]/[3.16]: Give is a real tactic only after Challenge
    # (EN) or Pursue (PU) -- never inside a Search Encounter Plan.
    for slot in (0, 1):
        assert int(Maneuver.GIVE) not in {value for value, _ in tactic_options(slot)}
        assert int(Maneuver.GIVE) in {value for value, _ in tactic_options(slot, allow_give=True)}


def test_tactic_options_excludes_beg_even_with_allow_give():
    for slot in (0, 1):
        assert int(Maneuver.BEG) not in {value for value, _ in tactic_options(slot, allow_give=True)}


def test_challenge_target_options_lists_only_co_located_leaders():
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=1, name="Bram", location=HOME))
    state.add_leader(LeaderState(leader_id=3, kingdom_id=1, name="Faraway", location=HexCoord(9, 9)))

    options = challenge_target_options(state, KING_ID)

    values = {value for value, _label in options}
    assert values == {"2"}


def _challenge_form(
    target_id: int = 2,
    tactics: dict[int, int] | None = None,
    subs: dict[int, int] | None = None,
    says: dict[int, str] | None = None,
    spells: dict[int, int] | None = None,
    items: dict[int, int] | None = None,
    give_items: dict[int, int] | None = None,
):
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.CHALLENGE))
    form[f"challenge_target_{KING_ID}_0"] = str(target_id)
    for slot, maneuver_value in (tactics or {}).items():
        form[f"challenge_tactic_{KING_ID}_0_{slot}"] = str(maneuver_value)
    for slot, sub_value in (subs or {}).items():
        form[f"challenge_tactic_sub_{KING_ID}_0_{slot}"] = str(sub_value)
    for slot, say_value in (says or {}).items():
        form[f"challenge_tactic_say_{KING_ID}_0_{slot}"] = say_value
    for slot, spell_value in (spells or {}).items():
        form[f"challenge_tactic_spell_{KING_ID}_0_{slot}"] = str(spell_value)
    for slot, item_value in (items or {}).items():
        form[f"challenge_tactic_item_{KING_ID}_0_{slot}"] = str(item_value)
    for slot, item_value in (give_items or {}).items():
        form[f"challenge_tactic_give_item_{KING_ID}_0_{slot}"] = str(item_value)
    return form


def test_challenge_phase_reads_its_own_target_and_tactics():
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=1, name="Bram", location=HOME))
    form = _challenge_form(tactics={0: int(Maneuver.TALK), 1: int(Maneuver.MELEE)})

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)

    challenge_phase = phases[0]
    assert challenge_phase.action is ActionCode.CHALLENGE
    assert challenge_phase.obj == 2
    assert challenge_phase.extra == [0, int(Maneuver.TALK), int(Maneuver.MELEE), -1]


def test_challenge_phase_allows_give_as_a_tactic():
    # Unlike Search, Give is a real tactic for Challenge/Pursue -- its
    # own dedicated item dropdown, ownership-filtered like Use Item's.
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=1, name="Bram", location=HOME))
    item = state.add_item(Treasure.ABILITY_MELEE, KING_ID)
    form = _challenge_form(tactics={0: int(Maneuver.GIVE)}, give_items={0: item.item_id})

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)

    assert phases[0].extra == [0, int(Maneuver.GIVE), item.item_id, -1]


def test_challenge_phase_allows_giving_several_items_in_one_plan():
    # Rulebook: "si può dare qualsiasi numero di oggetti... Si estende
    # cioè l'azione Dare permettendo di cedere più di un oggetto nella
    # stessa fase" -- composed as several separate GIVE slots, one item
    # each (the wire format carries only one item per slot).
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=1, name="Bram", location=HOME))
    first_item = state.add_item(Treasure.ABILITY_MELEE, KING_ID)
    second_item = state.add_item(Treasure.WAND_FIREBALL, KING_ID, charges=1)
    form = _challenge_form(
        tactics={0: int(Maneuver.GIVE), 1: int(Maneuver.GIVE)},
        give_items={0: first_item.item_id, 1: second_item.item_id},
    )

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)

    assert phases[0].extra == [0, int(Maneuver.GIVE), first_item.item_id, int(Maneuver.GIVE), second_item.item_id, -1]


def test_challenge_phase_give_tactic_without_a_chosen_item_is_rejected():
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=1, name="Bram", location=HOME))
    form = _challenge_form(tactics={0: int(Maneuver.GIVE)})

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "choose an item to Give" in str(exc)


def test_challenge_phase_give_tactic_rejects_an_unowned_item_even_via_a_direct_tampered_value():
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=1, name="Bram", location=HOME))
    item = state.add_item(Treasure.ABILITY_MELEE, owner_leader_id=2)  # not the acting leader's own item
    form = _challenge_form(tactics={0: int(Maneuver.GIVE)}, give_items={0: item.item_id})

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "choose an item to Give" in str(exc)


def test_give_item_options_excludes_the_valhalla_visitors_own_fixed_item():
    # Bug fix: unlike trade_gift_options() (the top-level Give Action's
    # own dropdown), give_item_options() (the Encounter Plan GIVE
    # tactic's own dropdown) used to offer the Valhalla visitor's own
    # fixed item -- rulebook VALHALLA.txt says it can never be given
    # away at all.
    state = _state()
    item = state.add_item(Treasure.ABILITY_MELEE, owner_leader_id=KING_ID)
    state.leaders[KING_ID].valhalla_fixed_item_id = item.item_id

    options = give_item_options(state, KING_ID)

    assert str(item.item_id) not in {value for value, _label in options}


def test_challenge_phase_give_tactic_rejects_the_valhalla_visitors_own_fixed_item():
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=1, name="Bram", location=HOME))
    item = state.add_item(Treasure.ABILITY_MELEE, owner_leader_id=KING_ID)
    state.leaders[KING_ID].valhalla_fixed_item_id = item.item_id
    form = _challenge_form(tactics={0: int(Maneuver.GIVE)}, give_items={0: item.item_id})

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "Valhalla" in str(exc)


def test_challenge_phase_rejects_beg_even_via_a_direct_tampered_value():
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=1, name="Bram", location=HOME))
    form = _challenge_form(tactics={0: int(Maneuver.BEG)})

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "Beg isn't a real Encounter Plan tactic" in str(exc)


def test_challenge_phase_without_choosing_a_target_is_rejected():
    state = _state()
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.CHALLENGE))

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "choose a Challenge target" in str(exc)


def test_challenge_phase_rejects_a_noncolocated_target_even_via_a_direct_tampered_value():
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=1, name="Faraway", location=HexCoord(9, 9)))
    form = _challenge_form(target_id=2)

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "choose a Challenge target" in str(exc)


def test_build_composed_kingdom_round_trips_a_challenge_order():
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=1, name="Bram", location=HOME))
    form = {**_all_defend_form(KING_ID), **_all_defend_form(2)}
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.CHALLENGE))
    form[f"challenge_target_{KING_ID}_0"] = "2"
    form[f"challenge_tactic_{KING_ID}_0_0"] = str(int(Maneuver.MELEE))

    kingdom = build_composed_kingdom(state, game_label="Testia", turn_number=1, kingdom_id=1, form=form)
    text = write_k1_moves_file(kingdom)
    tmp = Path(tempfile.mktemp())
    tmp.write_text(text, encoding="utf-8")
    try:
        reparsed = parse_k1_moves_file(tmp)
    finally:
        tmp.unlink(missing_ok=True)

    phase0 = reparsed.leaders[0].plan.segments[0].phases["P0"]
    assert phase0.action is ActionCode.CHALLENGE
    assert phase0.obj == 2
    assert phase0.extra == [0, int(Maneuver.MELEE), -1]


def test_build_composed_kingdom_round_trips_a_challenge_order_giving_two_items():
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=1, name="Bram", location=HOME))
    first_item = state.add_item(Treasure.ABILITY_MELEE, KING_ID)
    second_item = state.add_item(Treasure.WAND_FIREBALL, KING_ID, charges=1)
    form = {**_all_defend_form(KING_ID), **_all_defend_form(2)}
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.CHALLENGE))
    form[f"challenge_target_{KING_ID}_0"] = "2"
    form[f"challenge_tactic_{KING_ID}_0_0"] = str(int(Maneuver.GIVE))
    form[f"challenge_tactic_give_item_{KING_ID}_0_0"] = str(first_item.item_id)
    form[f"challenge_tactic_{KING_ID}_0_1"] = str(int(Maneuver.GIVE))
    form[f"challenge_tactic_give_item_{KING_ID}_0_1"] = str(second_item.item_id)

    kingdom = build_composed_kingdom(state, game_label="Testia", turn_number=1, kingdom_id=1, form=form)
    text = write_k1_moves_file(kingdom)
    tmp = Path(tempfile.mktemp())
    tmp.write_text(text, encoding="utf-8")
    try:
        reparsed = parse_k1_moves_file(tmp)
    finally:
        tmp.unlink(missing_ok=True)

    phase0 = reparsed.leaders[0].plan.segments[0].phases["P0"]
    assert phase0.action is ActionCode.CHALLENGE
    assert phase0.extra == [
        0,
        int(Maneuver.GIVE),
        first_item.item_id,
        int(Maneuver.GIVE),
        second_item.item_id,
        -1,
    ]


def test_pursue_target_options_lists_every_other_leader_no_co_location_needed():
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=1, name="Bram", location=HOME))
    state.add_kingdom(KingdomState(2, "Allia", Race.HUMAN, Alignment.GOOD, HexCoord(9, 9)))
    state.add_leader(LeaderState(leader_id=3, kingdom_id=2, name="Faraway", location=HexCoord(9, 9)))

    options = pursue_target_options(state, KING_ID)

    values = {value for value, _label in options}
    assert values == {str(KING_ID), "2", "3"}  # any Kingdom, no co-location needed, self included
    assert "Patrol (self)" in dict(options)[str(KING_ID)]


def _pursue_form(
    target_id: int = 2,
    tactics: dict[int, int] | None = None,
    subs: dict[int, int] | None = None,
    give_items: dict[int, int] | None = None,
):
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.PURSUE))
    form[f"pursue_target_{KING_ID}_0"] = str(target_id)
    for slot, maneuver_value in (tactics or {}).items():
        form[f"pursue_tactic_{KING_ID}_0_{slot}"] = str(maneuver_value)
    for slot, sub_value in (subs or {}).items():
        form[f"pursue_tactic_sub_{KING_ID}_0_{slot}"] = str(sub_value)
    for slot, item_value in (give_items or {}).items():
        form[f"pursue_tactic_give_item_{KING_ID}_0_{slot}"] = str(item_value)
    return form


def test_pursue_phase_reads_its_own_target_and_tactics():
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=1, name="Bram", location=HexCoord(9, 9)))
    form = _pursue_form(tactics={0: int(Maneuver.TALK), 1: int(Maneuver.MELEE)})

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)

    pursue_phase = phases[0]
    assert pursue_phase.action is ActionCode.PURSUE
    assert pursue_phase.obj == 2
    assert pursue_phase.extra == [0, int(Maneuver.TALK), int(Maneuver.MELEE), -1]


def test_pursue_phase_reads_a_hand_typed_target_number_when_the_dropdown_is_empty():
    # 2026-11-16, user-requested: pursue_target_number is a sibling
    # free-text fallback to pursue_target's own dropdown.
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=1, name="Bram", location=HexCoord(9, 9)))
    form = _pursue_form(tactics={0: int(Maneuver.MELEE)})
    form[f"pursue_target_{KING_ID}_0"] = ""
    form[f"pursue_target_number_{KING_ID}_0"] = "2"

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)

    assert phases[0].obj == 2


def test_pursue_phase_allows_give_as_a_tactic():
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=1, name="Bram", location=HexCoord(9, 9)))
    item = state.add_item(Treasure.ABILITY_MELEE, KING_ID)
    form = _pursue_form(tactics={0: int(Maneuver.GIVE)}, give_items={0: item.item_id})

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)

    assert phases[0].extra == [0, int(Maneuver.GIVE), item.item_id, -1]


def test_pursue_phase_without_choosing_a_target_is_rejected():
    state = _state()
    # Armyless King leads no army -- gets caught by the "choose a
    # target" check first regardless, since the target field is read
    # before the Encounter-Plan-required check.
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.PURSUE))

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "choose a Pursue target" in str(exc)


def test_pursue_phase_self_target_composes_a_patrol_declaration_when_armyless():
    # [3.16] "Characters On Patrol": self-targeting Pursue is a real,
    # sourced mechanic, not an invalid order -- legal here since this
    # King (the _state() fixture's own default) commands no army.
    state = _state()
    form = _pursue_form(target_id=KING_ID, tactics={0: int(Maneuver.MELEE)})

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)

    assert phases[0].action is ActionCode.PURSUE
    assert phases[0].obj == KING_ID


def test_pursue_phase_rejects_a_self_target_when_leading_an_army_even_via_a_direct_tampered_value():
    # [3.16]'s own Patrol text states its army precondition
    # unconditionally on the acting leader ("viene fatto da un Eroe
    # senza armate") -- unlike directed Pursue's own soft mismatch,
    # this one is enforced at compose time.
    state = _state()
    state.add_army(ArmyState(50, 1, ArmyType.BOWMEN, Quality.AVERAGE, HOME, commanded_by=KING_ID))
    form = _pursue_form(target_id=KING_ID, tactics={0: int(Maneuver.MELEE)})

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "may not be ordered to Patrol" in str(exc)


def test_pursue_phase_rejects_a_nonexistent_target_even_via_a_direct_tampered_value():
    state = _state()
    form = _pursue_form(target_id=999, tactics={0: int(Maneuver.MELEE)})

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "choose a Pursue target" in str(exc)


def test_pursue_phase_armyless_with_no_encounter_plan_is_rejected():
    # [3.16]: "Se l'inseguitore non comanda alcuna unità militare allora
    # bisogna indicare un Piano d'Incontro" -- enforced here at compose
    # time; the engine itself stays permissive (see moves_compose.py's
    # own inline comment on this check for why it's not retrofitted
    # there this round).
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=1, name="Bram", location=HexCoord(9, 9)))
    form = _pursue_form()  # no tactics at all

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "an armyless Pursue needs an Encounter Plan" in str(exc)


def test_pursue_phase_army_leading_pursuer_needs_no_encounter_plan():
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=1, name="Bram", location=HexCoord(9, 9)))
    state.add_army(ArmyState(50, 1, ArmyType.BOWMEN, Quality.AVERAGE, HOME, commanded_by=KING_ID))
    form = _pursue_form()  # no tactics at all -- legal, this pursuer leads an army

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)

    assert phases[0].extra == [0, -1]


def test_build_composed_kingdom_round_trips_a_pursue_order():
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=1, name="Bram", location=HexCoord(9, 9)))
    form = {**_all_defend_form(KING_ID), **_all_defend_form(2)}
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.PURSUE))
    form[f"pursue_target_{KING_ID}_0"] = "2"
    form[f"pursue_tactic_{KING_ID}_0_0"] = str(int(Maneuver.MELEE))

    kingdom = build_composed_kingdom(state, game_label="Testia", turn_number=1, kingdom_id=1, form=form)
    text = write_k1_moves_file(kingdom)
    tmp = Path(tempfile.mktemp())
    tmp.write_text(text, encoding="utf-8")
    try:
        reparsed = parse_k1_moves_file(tmp)
    finally:
        tmp.unlink(missing_ok=True)

    phase0 = reparsed.leaders[0].plan.segments[0].phases["P0"]
    assert phase0.action is ActionCode.PURSUE
    assert phase0.obj == 2
    assert phase0.extra == [0, int(Maneuver.MELEE), -1]


def test_hire_target_options_lists_only_colocated_free_non_king_heroes():
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=None, name="Free Hero", location=HOME))
    state.add_leader(LeaderState(leader_id=3, kingdom_id=1, name="Employed Hero", location=HOME))
    state.add_leader(LeaderState(leader_id=4, kingdom_id=None, name="Faraway Hero", location=HexCoord(9, 9)))
    state.add_kingdom(KingdomState(2, "Allia", Race.HUMAN, Alignment.GOOD, HexCoord(9, 9)))
    state.add_leader(LeaderState(leader_id=5, kingdom_id=2, name="A King", location=HOME, is_king=True))

    options = hire_target_options(state, KING_ID)

    values = {value for value, _label in options}
    assert values == {"2"}


def test_hire_phase_reads_its_own_target_and_gold_offer():
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=None, name="Free Hero", location=HOME))
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.HIRE))
    form[f"hire_target_{KING_ID}_0"] = "2"
    form[f"hire_gold_{KING_ID}_0"] = "3"
    form[f"obj_{KING_ID}_0"] = "999"  # must be ignored for a Hire phase
    form[f"extra_{KING_ID}_0"] = "5"  # must be ignored too

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)

    hire_phase = phases[0]
    assert hire_phase.action is ActionCode.HIRE
    assert hire_phase.obj == 2
    assert hire_phase.extra == [3]
    assert hire_phase.nested_plan is None


def test_hire_phase_reads_a_hand_typed_target_number_when_the_dropdown_is_empty():
    # 2026-11-15, user-requested: "posso provare a reclutare eroi
    # appena sconfitti in una provincia neutrale" -- hire_target's own
    # dropdown stays untouched, hire_target_number is a sibling free-
    # text fallback.
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=None, name="Free Hero", location=HOME))
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.HIRE))
    form[f"hire_target_number_{KING_ID}_0"] = "2"
    form[f"hire_gold_{KING_ID}_0"] = "3"

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)

    hire_phase = phases[0]
    assert hire_phase.obj == 2
    assert hire_phase.extra == [3]


def test_hire_phase_without_choosing_a_target_is_rejected():
    state = _state()
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.HIRE))
    form[f"hire_gold_{KING_ID}_0"] = "3"

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "choose a Hero to Hire" in str(exc)


def test_hire_phase_rejects_a_king_target_even_via_a_direct_tampered_value():
    state = _state()
    state.add_kingdom(KingdomState(2, "Allia", Race.HUMAN, Alignment.GOOD, HOME))
    state.add_leader(LeaderState(leader_id=2, kingdom_id=2, name="A King", location=HOME, is_king=True))
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.HIRE))
    form[f"hire_target_{KING_ID}_0"] = "2"
    form[f"hire_gold_{KING_ID}_0"] = "3"

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "choose a Hero to Hire" in str(exc)


def test_hire_phase_rejects_an_already_employed_hero_even_via_a_direct_tampered_value():
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=1, name="Employed Hero", location=HOME))
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.HIRE))
    form[f"hire_target_{KING_ID}_0"] = "2"
    form[f"hire_gold_{KING_ID}_0"] = "3"

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "choose a Hero to Hire" in str(exc)


def test_hire_phase_without_choosing_a_gold_offer_is_rejected():
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=None, name="Free Hero", location=HOME))
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.HIRE))
    form[f"hire_target_{KING_ID}_0"] = "2"

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "choose a gold offer" in str(exc)


def test_hire_phase_rejects_an_out_of_range_gold_offer_even_via_a_direct_tampered_value():
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=None, name="Free Hero", location=HOME))
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.HIRE))
    form[f"hire_target_{KING_ID}_0"] = "2"
    form[f"hire_gold_{KING_ID}_0"] = "7"  # never offered in the dropdown

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "must be 1-4" in str(exc)
    assert set(HIRE_GOLD_OFFER_RANGE) == {1, 2, 3, 4}


def test_hire_phase_nested_plan_only_offers_phases_strictly_after_the_hire():
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=None, name="Free Hero", location=HOME))
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_1"] = str(int(ActionCode.HIRE))
    form[f"hire_target_{KING_ID}_1"] = "2"
    form[f"hire_gold_{KING_ID}_1"] = "2"
    # A row at or before the Hire's own phase (P1) is never read at all --
    # only hire_nested_*_{leader}_1_{m} for m in 2..4 is consulted.
    form[f"hire_nested_action_{KING_ID}_1_0"] = str(int(ActionCode.LMOVE))
    form[f"hire_nested_obj_{KING_ID}_1_0"] = "999"
    form[f"hire_nested_action_{KING_ID}_1_2"] = str(int(ActionCode.WAIT))
    form[f"hire_nested_obj_{KING_ID}_1_2"] = "0"
    form[f"hire_nested_action_{KING_ID}_1_4"] = str(int(ActionCode.EXPLORE))
    form[f"hire_nested_obj_{KING_ID}_1_4"] = "0"

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)

    hire_phase = phases[1]
    assert hire_phase.nested_plan is not None
    assert hire_phase.nested_plan.leader_id == 2
    nested_segment = hire_phase.nested_plan.segments[0]
    assert nested_segment.plan_start == 2
    assert nested_segment.plan_end == 4
    assert set(nested_segment.phases) == {"P2", "P4"}
    assert nested_segment.phases["P2"].action is ActionCode.WAIT
    assert nested_segment.phases["P4"].action is ActionCode.EXPLORE


def test_hire_phase_with_every_nested_row_empty_has_no_nested_plan():
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=None, name="Free Hero", location=HOME))
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.HIRE))
    form[f"hire_target_{KING_ID}_0"] = "2"
    form[f"hire_gold_{KING_ID}_0"] = "2"

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)

    assert phases[0].nested_plan is None


def test_hire_phase_at_the_last_phase_has_no_nested_plan_slots():
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=None, name="Free Hero", location=HOME))
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_4"] = str(int(ActionCode.HIRE))
    form[f"hire_target_{KING_ID}_4"] = "2"
    form[f"hire_gold_{KING_ID}_4"] = "2"
    # Even if a tampered POST tried to set a nested row at or beyond P4,
    # there's no field name a real GM UI at P4 would ever emit for it,
    # and _parse_hire_nested_plan()'s own range(n+1, PHASE_COUNT) is empty.

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)

    assert phases[4].action is ActionCode.HIRE
    assert phases[4].nested_plan is None


def test_build_composed_kingdom_round_trips_a_hire_order_with_a_nested_plan():
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=None, name="Free Hero", location=HOME))
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.HIRE))
    form[f"hire_target_{KING_ID}_0"] = "2"
    form[f"hire_gold_{KING_ID}_0"] = "4"
    form[f"hire_nested_action_{KING_ID}_0_1"] = str(int(ActionCode.WAIT))

    kingdom = build_composed_kingdom(state, game_label="Testia", turn_number=1, kingdom_id=1, form=form)
    text = write_k1_moves_file(kingdom)
    tmp = Path(tempfile.mktemp())
    tmp.write_text(text, encoding="utf-8")
    try:
        reparsed = parse_k1_moves_file(tmp)
    finally:
        tmp.unlink(missing_ok=True)

    phase0 = reparsed.leaders[0].plan.segments[0].phases["P0"]
    assert phase0.action is ActionCode.HIRE
    assert phase0.obj == 2
    assert phase0.extra == [4]
    assert phase0.nested_plan is not None
    assert phase0.nested_plan.leader_id == 2
    assert phase0.nested_plan.segments[0].phases["P1"].action is ActionCode.WAIT


def test_hire_nested_plan_supports_a_full_move_order():
    # 2026-11-02: the nested-plan editor now reuses the *same* full
    # per-Action composer every top-level phase gets, not just the
    # plain generic Object/Extra fields -- confirmed here with a real
    # Move order for the newly-hired Hero's own P1.
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=None, name="Free Hero", location=HOME))
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.HIRE))
    form[f"hire_target_{KING_ID}_0"] = "2"
    form[f"hire_gold_{KING_ID}_0"] = "2"
    form[f"hire_nested_action_{KING_ID}_0_1"] = str(int(ActionCode.LMOVE))
    form[f"hire_nested_move_target_{KING_ID}_0_1"] = "3,2"

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)

    nested_move_phase = phases[0].nested_plan.segments[0].phases["P1"]
    assert nested_move_phase.action is ActionCode.LMOVE
    assert decode_hex_number(nested_move_phase.obj, BOARD_WIDTH) == HexCoord(3, 2)
    assert nested_move_phase.extra == []


def test_hire_nested_plan_rejects_an_invalid_move_destination_the_same_way_a_top_level_phase_does():
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=None, name="Free Hero", location=HOME))
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.HIRE))
    form[f"hire_target_{KING_ID}_0"] = "2"
    form[f"hire_gold_{KING_ID}_0"] = "2"
    form[f"hire_nested_action_{KING_ID}_0_1"] = str(int(ActionCode.LMOVE))
    # hire_nested_move_target_<king>_0_1 deliberately left unset.

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "choose a Move destination" in str(exc)


def test_hire_nested_plan_supports_a_full_search_order_with_tactics():
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=None, name="Free Hero", location=HOME))
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.HIRE))
    form[f"hire_target_{KING_ID}_0"] = "2"
    form[f"hire_gold_{KING_ID}_0"] = "2"
    form[f"hire_nested_action_{KING_ID}_0_1"] = str(int(ActionCode.SEARCH))
    form[f"hire_nested_search_feature_{KING_ID}_0_1"] = "3"
    form[f"hire_nested_tactic_{KING_ID}_0_1_0"] = str(int(Maneuver.FLEE))

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)

    nested_search_phase = phases[0].nested_plan.segments[0].phases["P1"]
    assert nested_search_phase.action is ActionCode.SEARCH
    assert nested_search_phase.obj == 3
    assert nested_search_phase.extra == [0, int(Maneuver.FLEE), -1]


def test_hire_nested_plan_supports_a_full_recruit_order_with_army_type_slots():
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=None, name="Free Hero", location=HOME))
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.HIRE))
    form[f"hire_target_{KING_ID}_0"] = "2"
    form[f"hire_gold_{KING_ID}_0"] = "2"
    form[f"hire_nested_action_{KING_ID}_0_1"] = str(int(ActionCode.RECRUIT))
    form[f"hire_nested_recruit_target_{KING_ID}_0_1"] = "self"
    ordinal = _ORDINAL_BY_ARMY_TYPE[ArmyType.BOWMEN]
    form[f"hire_nested_recruit_type_{KING_ID}_0_1_0"] = str(ordinal)

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)

    nested_recruit_phase = phases[0].nested_plan.segments[0].phases["P1"]
    assert nested_recruit_phase.action is ActionCode.RECRUIT
    assert nested_recruit_phase.extra == [0, ordinal, -1]


def test_cast_charm_nested_plan_supports_a_full_move_order():
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=None, name="Free Hero", location=HOME))
    form = _cast_form(cast_spell=str(int(Spell.CHARM)), cast_charm_target="2")
    form[f"cast_nested_action_{KING_ID}_0_1"] = str(int(ActionCode.LMOVE))
    form[f"cast_nested_move_target_{KING_ID}_0_1"] = "3,2"

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)

    nested_move_phase = phases[0].nested_plan.segments[0].phases["P1"]
    assert nested_move_phase.action is ActionCode.LMOVE
    assert decode_hex_number(nested_move_phase.obj, BOARD_WIDTH) == HexCoord(3, 2)


def test_use_mi_charm_wand_nested_plan_supports_a_full_move_order():
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=None, name="Free Hero", location=HOME))
    wand = state.add_item(Treasure.WAND_CHARM, KING_ID, charges=1)
    form = _use_mi_form(use_mi_item=str(wand.item_id), use_mi_charm_target="2")
    form[f"use_mi_nested_action_{KING_ID}_0_1"] = str(int(ActionCode.LMOVE))
    form[f"use_mi_nested_move_target_{KING_ID}_0_1"] = "3,2"

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)

    nested_move_phase = phases[0].nested_plan.segments[0].phases["P1"]
    assert nested_move_phase.action is ActionCode.LMOVE
    assert decode_hex_number(nested_move_phase.obj, BOARD_WIDTH) == HexCoord(3, 2)


def test_nested_plan_rich_fields_from_a_different_outer_phase_or_leader_are_never_cross_read():
    # Defense in depth: _remap_nested_fields() must key strictly off its
    # own (outer_leader_id, outer_n) pair -- a field posted for a
    # different leader or a different triggering phase must never leak
    # into this one's own remapped form.
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=None, name="Free Hero", location=HOME))
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_1"] = str(int(ActionCode.HIRE))
    form[f"hire_target_{KING_ID}_1"] = "2"
    form[f"hire_gold_{KING_ID}_1"] = "2"
    form[f"hire_nested_action_{KING_ID}_1_2"] = str(int(ActionCode.LMOVE))
    form[f"hire_nested_move_target_{KING_ID}_1_2"] = "3,2"
    # A decoy for a different outer phase (0, not 1) -- must be ignored.
    form[f"hire_nested_move_target_{KING_ID}_0_2"] = "9,9"

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)

    nested_move_phase = phases[1].nested_plan.segments[0].phases["P2"]
    assert decode_hex_number(nested_move_phase.obj, BOARD_WIDTH) == HexCoord(3, 2)


def test_build_composed_kingdom_round_trips_a_hire_nested_move_order():
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=None, name="Free Hero", location=HOME))
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.HIRE))
    form[f"hire_target_{KING_ID}_0"] = "2"
    form[f"hire_gold_{KING_ID}_0"] = "2"
    form[f"hire_nested_action_{KING_ID}_0_1"] = str(int(ActionCode.LMOVE))
    form[f"hire_nested_move_target_{KING_ID}_0_1"] = "3,2"

    kingdom = build_composed_kingdom(state, game_label="Testia", turn_number=1, kingdom_id=1, form=form)
    text = write_k1_moves_file(kingdom)
    tmp = Path(tempfile.mktemp())
    tmp.write_text(text, encoding="utf-8")
    try:
        reparsed = parse_k1_moves_file(tmp)
    finally:
        tmp.unlink(missing_ok=True)

    nested_move_phase = reparsed.leaders[0].plan.segments[0].phases["P0"].nested_plan.segments[0].phases["P1"]
    assert nested_move_phase.action is ActionCode.LMOVE
    assert decode_hex_number(nested_move_phase.obj, BOARD_WIDTH) == HexCoord(3, 2)


def test_nested_hero_option_bundle_includes_every_leader_scoped_dropdown():
    state = _state()
    item = state.add_item(Treasure.WAND_BLESS, KING_ID, charges=1)
    bundle = nested_hero_option_bundle(state, KING_ID)

    assert str(item.item_id) in {value for value, _label in bundle["use_mi_item"]}
    assert "search_feature" in bundle
    assert "recruit_target" in bundle
    assert "is_undead_king" in bundle


def test_nested_hero_option_bundle_resolves_a_dead_resurrection_candidate_by_its_own_last_location():
    # The candidate isn't in state.leaders at all -- nested_hero_option_
    # bundle() must temporarily reinsert the dead_leaders snapshot to
    # resolve leader-scoped choices (here: items the dead Hero still
    # owns, per GameState.remove_leader()'s own confirmed behavior) and
    # must leave state.leaders exactly as it found it afterwards.
    state = _state()
    dead_id = 99
    state.dead_leaders[dead_id] = LeaderState(leader_id=dead_id, kingdom_id=1, name="Dead Hero", location=HOME)
    item = state.add_item(Treasure.WAND_BLESS, dead_id, charges=1)

    bundle = nested_hero_option_bundle(state, dead_id)

    assert str(item.item_id) in {value for value, _label in bundle["use_mi_item"]}
    assert dead_id not in state.leaders


def test_fire_target_options_a_king_offers_any_own_kingdom_hero_regardless_of_location():
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=1, name="Colocated Hero", location=HOME))
    state.add_leader(LeaderState(leader_id=3, kingdom_id=1, name="Faraway Hero", location=HexCoord(9, 9)))
    state.add_kingdom(KingdomState(2, "Allia", Race.HUMAN, Alignment.GOOD, HexCoord(9, 9)))
    state.add_leader(LeaderState(leader_id=4, kingdom_id=2, name="Foreign Hero", location=HOME))
    state.add_leader(LeaderState(leader_id=5, kingdom_id=2, name="Foreign King", location=HOME, is_king=True))

    options = fire_target_options(state, KING_ID)

    values = {value for value, _label in options}
    assert values == {"2", "3"}


def test_fire_target_options_a_non_king_requires_colocation_and_own_kingdom():
    state = _state()
    state.add_leader(LeaderState(leader_id=50, kingdom_id=1, name="Acting Hero", location=HOME))
    state.add_leader(LeaderState(leader_id=3, kingdom_id=1, name="Faraway Hero", location=HexCoord(9, 9)))

    options = fire_target_options(state, 50)

    values = {value for value, _label in options}
    assert values == {"50"}  # only himself -- Faraway Hero isn't co-located


def test_fire_phase_reads_its_own_target():
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=1, name="Bram", location=HOME))
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.FIRE))
    form[f"fire_target_{KING_ID}_0"] = "2"
    form[f"obj_{KING_ID}_0"] = "999"  # must be ignored for a Fire phase
    form[f"extra_{KING_ID}_0"] = "5"  # must be ignored too -- always []

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)

    fire_phase = phases[0]
    assert fire_phase.action is ActionCode.FIRE
    assert fire_phase.obj == 2
    assert fire_phase.extra == []


def test_fire_phase_without_choosing_a_target_is_rejected():
    state = _state()
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.FIRE))

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "choose a Hero to Fire" in str(exc)


def test_fire_phase_rejects_a_king_target_even_via_a_direct_tampered_value():
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=1, name="Another King", location=HOME, is_king=True))
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.FIRE))
    form[f"fire_target_{KING_ID}_0"] = "2"

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "choose a Hero to Fire" in str(exc)


def test_fire_phase_rejects_a_different_kingdoms_hero_even_via_a_direct_tampered_value():
    state = _state()
    state.add_kingdom(KingdomState(2, "Allia", Race.HUMAN, Alignment.GOOD, HOME))
    state.add_leader(LeaderState(leader_id=2, kingdom_id=2, name="Foreign Hero", location=HOME))
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.FIRE))
    form[f"fire_target_{KING_ID}_0"] = "2"

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "choose a Hero to Fire" in str(exc)


def test_fire_phase_rejects_a_noncolocated_hero_for_a_non_king_even_via_a_direct_tampered_value():
    state = _state()
    state.add_leader(LeaderState(leader_id=50, kingdom_id=1, name="Acting Hero", location=HOME))
    state.add_leader(LeaderState(leader_id=3, kingdom_id=1, name="Faraway Hero", location=HexCoord(9, 9)))
    form = _all_defend_form(50)
    form["action_50_0"] = str(int(ActionCode.FIRE))
    form["fire_target_50_0"] = "3"

    try:
        parse_phase_inputs(form, 50, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "choose a Hero to Fire" in str(exc)


def test_fire_phase_allows_a_hero_to_fire_himself():
    state = _state()
    state.add_leader(LeaderState(leader_id=50, kingdom_id=1, name="Acting Hero", location=HOME))
    form = _all_defend_form(50)
    form["action_50_0"] = str(int(ActionCode.FIRE))
    form["fire_target_50_0"] = "50"

    phases = parse_phase_inputs(form, 50, board_width=BOARD_WIDTH, state=state)

    assert phases[0].action is ActionCode.FIRE
    assert phases[0].obj == 50


def test_build_composed_kingdom_round_trips_a_fire_order():
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=1, name="Bram", location=HOME))
    form = {**_all_defend_form(KING_ID), **_all_defend_form(2)}
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.FIRE))
    form[f"fire_target_{KING_ID}_0"] = "2"

    kingdom = build_composed_kingdom(state, game_label="Testia", turn_number=1, kingdom_id=1, form=form)
    text = write_k1_moves_file(kingdom)
    tmp = Path(tempfile.mktemp())
    tmp.write_text(text, encoding="utf-8")
    try:
        reparsed = parse_k1_moves_file(tmp)
    finally:
        tmp.unlink(missing_ok=True)

    phase0 = reparsed.leaders[0].plan.segments[0].phases["P0"]
    assert phase0.action is ActionCode.FIRE
    assert phase0.obj == 2
    assert phase0.extra == []


def test_cast_action_spells_is_19_spells_excluding_gate_angel():
    assert len(CAST_ACTION_SPELLS) == 19
    assert Spell.GATE_ANGEL not in CAST_ACTION_SPELLS
    assert Spell.RESURRECTION in CAST_ACTION_SPELLS
    assert Spell.SKELETAL_ARMY in CAST_ACTION_SPELLS  # the one spell left in CAST_NO_TARGET_SPELLS
    assert CAST_NO_TARGET_SPELLS == {Spell.SKELETAL_ARMY}
    assert Spell.RESURRECTION not in CAST_CHARACTER_TARGET_SPELLS  # gets its own dedicated field instead


def test_cast_spell_options_lists_every_action_spell_by_display_name():
    options = cast_spell_options()

    values = {value for value, _label in options}
    assert values == {int(spell) for spell in CAST_ACTION_SPELLS}
    assert int(Spell.GATE_ANGEL) not in values
    assert len(options) == 19


def test_cast_character_target_options_lists_every_leader_any_kingdom():
    state = _state()
    state.add_kingdom(KingdomState(2, "Allia", Race.HUMAN, Alignment.GOOD, HexCoord(9, 9)))
    state.add_leader(LeaderState(leader_id=2, kingdom_id=2, name="Foreign Hero", location=HexCoord(9, 9)))

    options = cast_character_target_options(state)

    values = {value for value, _label in options}
    assert values == {str(KING_ID), "2"}


def test_cast_character_target_options_excludes_the_active_valhalla_visitor():
    # 2026-11-07 bug fix: turn/cast_execution.py's own generic immunity
    # ("any CHARACTER_TARGET_SPELLS spell but Resurrection fizzles
    # against the Valhalla visitor") covers Oratory/Clairvoyance/
    # Phantasmal Armies/Mystic Winds too, not just Charm/Kill Enemy --
    # charm_target_options()/kill_enemy_target_options() already
    # exclude the visitor for this exact reason; this generic dropdown
    # didn't.
    from ak_engine.models.valhalla import VALHALLA_VISITOR_LEADER_ID

    state = _state()
    state.add_leader(
        LeaderState(
            leader_id=VALHALLA_VISITOR_LEADER_ID,
            kingdom_id=None,
            name="Valhalla Visitor",
            location=HOME,
            valhalla_active_turn=1,
        )
    )

    options = cast_character_target_options(state)

    values = {value for value, _label in options}
    assert str(VALHALLA_VISITOR_LEADER_ID) not in values


def test_resurrection_target_options_lists_comatose_heir_and_dead_colocated():
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=1, name="Comatose Hero", location=HOME, is_comatose=True))
    state.add_leader(LeaderState(leader_id=3, kingdom_id=1, name="The Heir", location=HOME, is_royal_heir=True))
    state.dead_leaders[3] = LeaderState(leader_id=3, kingdom_id=1, name="Old King", location=HOME, is_king=True)
    state.dead_leaders[4] = LeaderState(leader_id=4, kingdom_id=1, name="Dead Hero", location=HOME)
    state.add_leader(LeaderState(leader_id=5, kingdom_id=1, name="Faraway Hero", location=HexCoord(9, 9), is_comatose=True))
    state.dead_leaders[6] = LeaderState(leader_id=6, kingdom_id=1, name="Faraway Dead Hero", location=HexCoord(9, 9))

    options = resurrection_target_options(state, KING_ID)

    values = {value for value, _label in options}
    assert values == {"2", "3", "4"}  # not 5/6 -- not co-located


def test_charm_target_options_lists_colocated_army_less_non_king_any_kingdom():
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=1, name="Own Hero", location=HOME))
    state.add_kingdom(KingdomState(2, "Allia", Race.HUMAN, Alignment.GOOD, HexCoord(9, 9)))
    state.add_leader(LeaderState(leader_id=3, kingdom_id=2, name="Foreign Hero", location=HOME))
    state.add_leader(LeaderState(leader_id=4, kingdom_id=None, name="Free Hero", location=HOME))
    state.add_leader(LeaderState(leader_id=5, kingdom_id=1, name="Army Commander", location=HOME))
    state.add_army(ArmyState(50, 1, ArmyType.BOWMEN, Quality.AVERAGE, HOME, commanded_by=5))
    state.add_kingdom(KingdomState(3, "Farland", Race.HUMAN, Alignment.EVIL, HexCoord(9, 9)))
    state.add_leader(LeaderState(leader_id=6, kingdom_id=3, name="A Foreign King", location=HOME, is_king=True))
    state.add_leader(LeaderState(leader_id=7, kingdom_id=1, name="Faraway Hero", location=HexCoord(9, 9)))

    options = charm_target_options(state, KING_ID)

    values = {value for value, _label in options}
    assert values == {"2", "3", "4"}  # not 5 (leads an army), not 6 (a King), not 7 (not co-located), never self


def _cast_form(leader_id: int = KING_ID, **fields: str) -> dict[str, str]:
    form = _all_defend_form(leader_id)
    form[f"action_{leader_id}_0"] = str(int(ActionCode.CAST))
    for key, value in fields.items():
        form[f"{key}_{leader_id}_0"] = value
    return form


def test_cast_phase_reads_a_province_target_spell():
    state = _state()
    form = _cast_form(cast_spell=str(int(Spell.BLESS)), cast_province_target=f"{HOME.x},{HOME.y}")

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)

    cast_phase = phases[0]
    assert cast_phase.action is ActionCode.CAST
    assert cast_phase.obj == int(Spell.BLESS)
    assert len(cast_phase.extra) == 1
    assert decode_hex_number(cast_phase.extra[0], BOARD_WIDTH) == HOME
    assert cast_phase.nested_plan is None


def test_cast_phase_reads_a_hide_feature_target_as_a_feature_number():
    # 2026-11-16, user-requested: Hide Feature's own dropdown picks a
    # Feature (cast_feature_target), not a province -- the real wire
    # encoding (province coordinate) is unchanged, just derived here.
    state = _state()
    feature = state.features[3]
    form = _cast_form(cast_spell=str(int(Spell.HIDE_FEATURE)), cast_feature_target=str(feature.feature_id))

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)

    cast_phase = phases[0]
    assert cast_phase.obj == int(Spell.HIDE_FEATURE)
    assert decode_hex_number(cast_phase.extra[0], BOARD_WIDTH) == feature.coord


def test_cast_phase_rejects_an_unknown_hide_feature_target_even_via_a_direct_tampered_value():
    state = _state()
    form = _cast_form(cast_spell=str(int(Spell.HIDE_FEATURE)), cast_feature_target="99999")

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "choose a real Feature to Hide" in str(exc)


def test_cast_phase_illus_terrain_reads_target_and_terrain():
    state = _state()
    form = _cast_form(
        cast_spell=str(int(Spell.ILLUS_TERRAIN)),
        cast_province_target=f"{HOME.x},{HOME.y}",
        cast_terrain=str(int(Terrain.FOREST.value)),
    )

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)

    cast_phase = phases[0]
    assert cast_phase.obj == int(Spell.ILLUS_TERRAIN)
    assert decode_hex_number(cast_phase.extra[0], BOARD_WIDTH) == HOME
    assert cast_phase.extra[1] == Terrain.FOREST.value


def test_cast_phase_reads_a_no_target_spell():
    state = _state()
    form = _cast_form(cast_spell=str(int(Spell.SKELETAL_ARMY)))

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)

    assert phases[0].obj == int(Spell.SKELETAL_ARMY)
    assert phases[0].extra == [0]


def test_cast_phase_reads_an_item_target_spell():
    state = _state()
    item_id = state.items_held_by(KING_ID)[0].item_id
    form = _cast_form(cast_spell=str(int(Spell.LOCATE_OBJECT)), cast_item_target=str(item_id))

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)

    assert phases[0].obj == int(Spell.LOCATE_OBJECT)
    assert phases[0].extra == [item_id]


def test_cast_phase_reads_a_generic_character_target_spell():
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=1, name="Bram", location=HexCoord(9, 9)))
    form = _cast_form(cast_spell=str(int(Spell.ORATORY)), cast_character_target="2")

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)

    assert phases[0].obj == int(Spell.ORATORY)
    assert phases[0].extra == [2]
    assert phases[0].nested_plan is None


def test_cast_phase_reads_a_hand_typed_character_target_number_when_the_dropdown_is_empty():
    # 2026-11-15, user-requested: cast_character_target_number is a
    # sibling free-text fallback to cast_character_target's own
    # dropdown (Oratory/Phantasmal Armies/Clairvoyance/Mystic Winds).
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=1, name="Bram", location=HexCoord(9, 9)))
    form = _cast_form(cast_spell=str(int(Spell.ORATORY)), cast_character_target_number="2")

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)

    assert phases[0].extra == [2]


def test_cast_phase_rejects_the_active_valhalla_visitor_as_a_generic_character_target():
    from ak_engine.models.valhalla import VALHALLA_VISITOR_LEADER_ID

    state = _state()
    state.add_leader(
        LeaderState(
            leader_id=VALHALLA_VISITOR_LEADER_ID,
            kingdom_id=None,
            name="Valhalla Visitor",
            location=HOME,
            valhalla_active_turn=1,
        )
    )
    form = _cast_form(cast_spell=str(int(Spell.ORATORY)), cast_character_target=str(VALHALLA_VISITOR_LEADER_ID))

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "choose a Cast target character" in str(exc)


def test_cast_phase_charm_embeds_a_nested_plan():
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=None, name="Free Hero", location=HOME))
    form = _cast_form(cast_spell=str(int(Spell.CHARM)), cast_charm_target="2")
    form[f"cast_nested_action_{KING_ID}_0_1"] = str(int(ActionCode.WAIT))

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)

    cast_phase = phases[0]
    assert cast_phase.obj == int(Spell.CHARM)
    assert cast_phase.extra == [2]
    assert cast_phase.nested_plan is not None
    assert cast_phase.nested_plan.leader_id == 2
    assert cast_phase.nested_plan.segments[0].phases["P1"].action is ActionCode.WAIT


def test_cast_phase_reads_a_hand_typed_charm_target_number_when_the_dropdown_is_empty():
    # 2026-11-15, user-requested: cast_charm_target_number is a sibling
    # free-text fallback to cast_charm_target's own dropdown.
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=None, name="Free Hero", location=HOME))
    form = _cast_form(cast_spell=str(int(Spell.CHARM)), cast_charm_target_number="2")

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)

    assert phases[0].extra == [2]


def test_cast_phase_charm_can_poach_a_foreign_kingdoms_hero():
    # Confirmed real engine behavior (2026-11-01): unlike Hire, Charm's
    # free-hire branch has no "must already be independent" requirement.
    state = _state()
    state.add_kingdom(KingdomState(2, "Allia", Race.HUMAN, Alignment.GOOD, HexCoord(9, 9)))
    state.add_leader(LeaderState(leader_id=2, kingdom_id=2, name="Foreign Hero", location=HOME))
    form = _cast_form(cast_spell=str(int(Spell.CHARM)), cast_charm_target="2")

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)

    assert phases[0].obj == int(Spell.CHARM)
    assert phases[0].extra == [2]


def test_cast_phase_charm_rejects_a_king_target_even_via_a_direct_tampered_value():
    state = _state()
    state.add_kingdom(KingdomState(2, "Allia", Race.HUMAN, Alignment.GOOD, HOME))
    state.add_leader(LeaderState(leader_id=2, kingdom_id=2, name="A King", location=HOME, is_king=True))
    form = _cast_form(cast_spell=str(int(Spell.CHARM)), cast_charm_target="2")

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "choose a Charm target" in str(exc)


def test_cast_phase_charm_rejects_a_target_who_leads_an_army_even_via_a_direct_tampered_value():
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=1, name="Army Commander", location=HOME))
    state.add_army(ArmyState(50, 1, ArmyType.BOWMEN, Quality.AVERAGE, HOME, commanded_by=2))
    form = _cast_form(cast_spell=str(int(Spell.CHARM)), cast_charm_target="2")

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "choose a Charm target" in str(exc)


def test_cast_phase_charm_rejects_a_noncolocated_target_even_via_a_direct_tampered_value():
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=1, name="Faraway Hero", location=HexCoord(9, 9)))
    form = _cast_form(cast_spell=str(int(Spell.CHARM)), cast_charm_target="2")

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "choose a Charm target" in str(exc)


def test_charm_target_options_excludes_the_active_valhalla_visitor():
    # Bug fix: unlike kill_enemy_target_options() (its structural twin),
    # charm_target_options() used to offer the active Valhalla visitor
    # -- a target execute_cast()'s own generic cross-spell immunity
    # silently no-ops for every character-targeted spell but
    # Resurrection.
    from ak_engine.models.valhalla import VALHALLA_VISITOR_LEADER_ID

    state = _state()
    state.add_leader(
        LeaderState(leader_id=VALHALLA_VISITOR_LEADER_ID, kingdom_id=None, name="Valhalla Visitor", location=HOME, valhalla_active_turn=1)
    )

    options = charm_target_options(state, KING_ID)

    assert str(VALHALLA_VISITOR_LEADER_ID) not in {value for value, _label in options}


def test_cast_phase_charm_rejects_the_active_valhalla_visitor_even_via_a_direct_tampered_value():
    from ak_engine.models.valhalla import VALHALLA_VISITOR_LEADER_ID

    state = _state()
    state.add_leader(
        LeaderState(leader_id=VALHALLA_VISITOR_LEADER_ID, kingdom_id=None, name="Valhalla Visitor", location=HOME, valhalla_active_turn=1)
    )
    form = _cast_form(cast_spell=str(int(Spell.CHARM)), cast_charm_target=str(VALHALLA_VISITOR_LEADER_ID))

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "choose a Charm target" in str(exc)


def test_kill_enemy_target_options_lists_colocated_non_king_non_undead_any_kingdom():
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=1, name="Own Hero", location=HOME))
    state.add_kingdom(KingdomState(2, "Allia", Race.HUMAN, Alignment.GOOD, HexCoord(9, 9)))
    state.add_leader(LeaderState(leader_id=3, kingdom_id=2, name="Foreign Hero", location=HOME))
    state.add_leader(LeaderState(leader_id=4, kingdom_id=1, name="Army Commander", location=HOME))
    state.add_army(ArmyState(50, 1, ArmyType.BOWMEN, Quality.AVERAGE, HOME, commanded_by=4))
    state.add_leader(LeaderState(leader_id=5, kingdom_id=1, name="A King", location=HOME, is_king=True))
    state.add_leader(LeaderState(leader_id=6, kingdom_id=1, name="Undead Hero", location=HOME, alignment=Alignment.UNDEAD))
    state.add_leader(LeaderState(leader_id=7, kingdom_id=1, name="Faraway Hero", location=HexCoord(9, 9)))

    options = kill_enemy_target_options(state, KING_ID)

    values = {value for value, _label in options}
    assert values == {"2", "3", "4"}  # not 5 (King), 6 (Undead), 7 (not co-located), never self
    assert "halved chance" in dict(options)["4"]


def test_cast_phase_reads_a_kill_enemy_target():
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=1, name="Bram", location=HOME))
    form = _cast_form(cast_spell=str(int(Spell.KILL_ENEMY)), cast_kill_enemy_target="2")

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)

    cast_phase = phases[0]
    assert cast_phase.action is ActionCode.CAST
    assert cast_phase.obj == int(Spell.KILL_ENEMY)
    assert cast_phase.extra == [2]
    assert cast_phase.nested_plan is None


def test_cast_phase_reads_a_hand_typed_kill_enemy_target_number_when_the_dropdown_is_empty():
    # 2026-11-15, user-requested: cast_kill_enemy_target_number is a
    # sibling free-text fallback to cast_kill_enemy_target's own
    # dropdown.
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=1, name="Bram", location=HOME))
    form = _cast_form(cast_spell=str(int(Spell.KILL_ENEMY)), cast_kill_enemy_target_number="2")

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)

    assert phases[0].extra == [2]


def test_cast_phase_kill_enemy_allows_an_army_leading_target():
    # Legal but penalized (halved roll), not blocked outright -- unlike
    # Charm's own army-count precondition failure.
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=1, name="Army Commander", location=HOME))
    state.add_army(ArmyState(50, 1, ArmyType.BOWMEN, Quality.AVERAGE, HOME, commanded_by=2))
    form = _cast_form(cast_spell=str(int(Spell.KILL_ENEMY)), cast_kill_enemy_target="2")

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)

    assert phases[0].extra == [2]


def test_cast_phase_kill_enemy_rejects_a_king_target_even_via_a_direct_tampered_value():
    state = _state()
    state.add_kingdom(KingdomState(2, "Allia", Race.HUMAN, Alignment.GOOD, HOME))
    state.add_leader(LeaderState(leader_id=2, kingdom_id=2, name="A King", location=HOME, is_king=True))
    form = _cast_form(cast_spell=str(int(Spell.KILL_ENEMY)), cast_kill_enemy_target="2")

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "choose a Kill Enemy target" in str(exc)


def test_cast_phase_kill_enemy_rejects_an_undead_target_even_via_a_direct_tampered_value():
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=1, name="Undead Hero", location=HOME, alignment=Alignment.UNDEAD))
    form = _cast_form(cast_spell=str(int(Spell.KILL_ENEMY)), cast_kill_enemy_target="2")

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "choose a Kill Enemy target" in str(exc)


def test_cast_phase_kill_enemy_rejects_a_noncolocated_target_even_via_a_direct_tampered_value():
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=1, name="Faraway Hero", location=HexCoord(9, 9)))
    form = _cast_form(cast_spell=str(int(Spell.KILL_ENEMY)), cast_kill_enemy_target="2")

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "choose a Kill Enemy target" in str(exc)


def test_cast_phase_resurrection_embeds_a_nested_plan():
    state = _state()
    state.dead_leaders[2] = LeaderState(leader_id=2, kingdom_id=1, name="Dead Hero", location=HOME)
    form = _cast_form(cast_spell=str(int(Spell.RESURRECTION)), cast_resurrection_target="2")
    form[f"cast_nested_action_{KING_ID}_0_1"] = str(int(ActionCode.WAIT))

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)

    cast_phase = phases[0]
    assert cast_phase.obj == int(Spell.RESURRECTION)
    assert cast_phase.extra == [2]
    assert cast_phase.nested_plan is not None
    assert cast_phase.nested_plan.leader_id == 2
    assert cast_phase.nested_plan.segments[0].phases["P1"].action is ActionCode.WAIT


def test_cast_phase_reads_a_hand_typed_resurrection_target_number_when_the_dropdown_is_empty():
    # 2026-11-15, user-requested: cast_resurrection_target_number is a
    # sibling free-text fallback to cast_resurrection_target's own
    # dropdown.
    state = _state()
    state.dead_leaders[2] = LeaderState(leader_id=2, kingdom_id=1, name="Dead Hero", location=HOME)
    form = _cast_form(cast_spell=str(int(Spell.RESURRECTION)), cast_resurrection_target_number="2")

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)

    assert phases[0].extra == [2]


def test_cast_phase_resurrection_nested_spy_order_is_rejected_cleanly_not_a_crash():
    # Bug fix: the resurrected hero isn't in state.leaders yet at
    # compose time (still a dead_leaders entry) -- picking Spy for
    # their own nested P1 used to raise an unhandled KeyError instead
    # of a clean InvalidComposedMovesError.
    state = _state()
    state.dead_leaders[2] = LeaderState(leader_id=2, kingdom_id=1, name="Dead Hero", location=HOME)
    form = _cast_form(cast_spell=str(int(Spell.RESURRECTION)), cast_resurrection_target="2")
    form[f"cast_nested_action_{KING_ID}_0_1"] = str(int(ActionCode.ASPY))

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "Spy" in str(exc)


def test_cast_phase_resurrection_target_must_be_eligible():
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=1, name="Healthy Hero", location=HOME))
    form = _cast_form(cast_spell=str(int(Spell.RESURRECTION)), cast_resurrection_target="2")

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "choose a Resurrection target" in str(exc)


def test_cast_phase_without_choosing_a_spell_is_rejected():
    state = _state()
    form = _cast_form()

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "choose a spell to Cast" in str(exc)


def test_cast_phase_rejects_gate_angel_even_via_a_direct_tampered_value():
    state = _state()
    form = _cast_form(cast_spell=str(int(Spell.GATE_ANGEL)))

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "choose a spell to Cast" in str(exc)


def test_cast_phase_rejects_a_combat_only_spell_even_via_a_direct_tampered_value():
    state = _state()
    form = _cast_form(cast_spell=str(int(Spell.FIREBALL)))

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "choose a spell to Cast" in str(exc)


def test_build_composed_kingdom_round_trips_a_cast_order():
    state = _state()
    form = _cast_form(cast_spell=str(int(Spell.SKELETAL_ARMY)))

    kingdom = build_composed_kingdom(state, game_label="Testia", turn_number=1, kingdom_id=1, form=form)
    text = write_k1_moves_file(kingdom)
    tmp = Path(tempfile.mktemp())
    tmp.write_text(text, encoding="utf-8")
    try:
        reparsed = parse_k1_moves_file(tmp)
    finally:
        tmp.unlink(missing_ok=True)

    phase0 = reparsed.leaders[0].plan.segments[0].phases["P0"]
    assert phase0.action is ActionCode.CAST
    assert phase0.obj == int(Spell.SKELETAL_ARMY)
    assert phase0.extra == [0]


def _use_mi_form(leader_id: int = KING_ID, **fields: str) -> dict[str, str]:
    form = _all_defend_form(leader_id)
    form[f"action_{leader_id}_0"] = str(int(ActionCode.USE_MI))
    for key, value in fields.items():
        form[f"{key}_{leader_id}_0"] = value
    return form


def test_use_mi_item_options_lists_an_action_eligible_wand_and_a_book_but_not_a_combat_only_wand():
    # _state() already gives KING_ID a Wand of Fireball (Treasure.WAND_FIREBALL,
    # Spell.FIREBALL -- one of the 5 Personal-Combat-only wand spells) --
    # confirmed excluded here, unlike item_options()'s own Encounter Plan
    # dropdown where it's the one legitimate entry.
    state = _state()
    bless_wand = state.add_item(Treasure.WAND_BLESS, KING_ID, charges=2)
    book = state.add_item(Treasure.BOOK_MELEE, KING_ID)

    options = use_mi_item_options(state, KING_ID)

    values = {value for value, _label in options}
    assert values == {str(bless_wand.item_id), str(book.item_id)}
    labels = dict(options)
    assert "Bless" in labels[str(bless_wand.item_id)]
    assert "+1 Melee" in labels[str(book.item_id)]


def test_use_mi_item_options_excludes_an_uncharged_wand():
    state = _state()
    item = state.add_item(Treasure.WAND_BLESS, KING_ID, charges=0)

    options = use_mi_item_options(state, KING_ID)

    assert str(item.item_id) not in {value for value, _label in options}


def test_use_mi_item_spell_by_id_maps_a_wand_to_its_own_fixed_spell():
    state = _state()
    wand = state.add_item(Treasure.WAND_BLESS, KING_ID, charges=2)
    book = state.add_item(Treasure.BOOK_MELEE, KING_ID)

    mapping = use_mi_item_spell_by_id(state)

    assert mapping[wand.item_id] == int(Spell.BLESS)
    assert book.item_id not in mapping


def test_use_mi_phase_reads_a_province_target_wand():
    state = _state()
    wand = state.add_item(Treasure.WAND_BLESS, KING_ID, charges=2)
    form = _use_mi_form(use_mi_item=str(wand.item_id), use_mi_province_target=f"{HOME.x},{HOME.y}")

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)

    use_mi_phase = phases[0]
    assert use_mi_phase.action is ActionCode.USE_MI
    assert use_mi_phase.obj == wand.item_id
    assert decode_hex_number(use_mi_phase.extra[0], BOARD_WIDTH) == HOME
    assert use_mi_phase.nested_plan is None


def test_use_mi_phase_reads_a_hide_feature_wand_target_as_a_feature_number():
    # 2026-11-16, user-requested: same Feature-dropdown shape as the
    # top-level Cast action's own Hide Feature target, mirrored here
    # under its own use_mi_feature_target field.
    state = _state()
    feature = state.features[3]
    wand = state.add_item(Treasure.WAND_HIDE_FEATURE, KING_ID, charges=1)
    form = _use_mi_form(use_mi_item=str(wand.item_id), use_mi_feature_target=str(feature.feature_id))

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)

    use_mi_phase = phases[0]
    assert use_mi_phase.obj == wand.item_id
    assert decode_hex_number(use_mi_phase.extra[0], BOARD_WIDTH) == feature.coord


def test_use_mi_phase_illus_terrain_wand_reads_target_and_terrain():
    state = _state()
    wand = state.add_item(Treasure.WAND_ILLUS_TERRAIN, KING_ID, charges=2)
    form = _use_mi_form(
        use_mi_item=str(wand.item_id),
        use_mi_province_target=f"{HOME.x},{HOME.y}",
        use_mi_terrain=str(int(Terrain.FOREST.value)),
    )

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)

    use_mi_phase = phases[0]
    assert use_mi_phase.obj == wand.item_id
    assert decode_hex_number(use_mi_phase.extra[0], BOARD_WIDTH) == HOME
    assert use_mi_phase.extra[1] == Terrain.FOREST.value


def test_use_mi_phase_reads_a_no_target_wand():
    state = _state()
    wand = state.add_item(Treasure.WAND_SKELETAL_ARMY, KING_ID, charges=1)
    form = _use_mi_form(use_mi_item=str(wand.item_id))

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)

    assert phases[0].obj == wand.item_id
    assert phases[0].extra == [0]


def test_use_mi_phase_reads_a_hand_typed_item_number_when_the_dropdown_is_empty():
    # 2026-11-15, user-requested: use_mi_item_number is a sibling
    # free-text fallback to use_mi_item's own dropdown.
    state = _state()
    wand = state.add_item(Treasure.WAND_SKELETAL_ARMY, KING_ID, charges=1)
    form = _use_mi_form(use_mi_item_number=str(wand.item_id))

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)

    assert phases[0].obj == wand.item_id
    assert phases[0].extra == [0]


def test_use_mi_phase_reads_a_generic_character_target_wand():
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=1, name="Bram", location=HexCoord(9, 9)))
    wand = state.add_item(Treasure.WAND_ORATORY, KING_ID, charges=1)
    form = _use_mi_form(use_mi_item=str(wand.item_id), use_mi_character_target="2")

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)

    assert phases[0].obj == wand.item_id
    assert phases[0].extra == [2]
    assert phases[0].nested_plan is None


def test_use_mi_phase_charm_wand_embeds_a_nested_plan():
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=None, name="Free Hero", location=HOME))
    wand = state.add_item(Treasure.WAND_CHARM, KING_ID, charges=1)
    form = _use_mi_form(use_mi_item=str(wand.item_id), use_mi_charm_target="2")
    form[f"use_mi_nested_action_{KING_ID}_0_1"] = str(int(ActionCode.WAIT))

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)

    use_mi_phase = phases[0]
    assert use_mi_phase.obj == wand.item_id
    assert use_mi_phase.extra == [2]
    assert use_mi_phase.nested_plan is not None
    assert use_mi_phase.nested_plan.leader_id == 2
    assert use_mi_phase.nested_plan.segments[0].phases["P1"].action is ActionCode.WAIT


def test_use_mi_phase_resurrection_wand_embeds_a_nested_plan():
    state = _state()
    state.dead_leaders[2] = LeaderState(leader_id=2, kingdom_id=1, name="Dead Hero", location=HOME)
    wand = state.add_item(Treasure.WAND_RESURRECTION, KING_ID, charges=1)
    form = _use_mi_form(use_mi_item=str(wand.item_id), use_mi_resurrection_target="2")
    form[f"use_mi_nested_action_{KING_ID}_0_1"] = str(int(ActionCode.WAIT))

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)

    use_mi_phase = phases[0]
    assert use_mi_phase.obj == wand.item_id
    assert use_mi_phase.extra == [2]
    assert use_mi_phase.nested_plan is not None
    assert use_mi_phase.nested_plan.leader_id == 2


def test_use_mi_phase_reads_a_kill_enemy_wand():
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=1, name="Bram", location=HOME))
    wand = state.add_item(Treasure.WAND_KILL_ENEMY, KING_ID, charges=1)
    form = _use_mi_form(use_mi_item=str(wand.item_id), use_mi_kill_enemy_target="2")

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)

    use_mi_phase = phases[0]
    assert use_mi_phase.obj == wand.item_id
    assert use_mi_phase.extra == [2]
    assert use_mi_phase.nested_plan is None


def test_use_mi_phase_reads_a_skill_book_with_no_target_at_all():
    state = _state()
    book = state.add_item(Treasure.BOOK_MELEE, KING_ID)
    form = _use_mi_form(use_mi_item=str(book.item_id))

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)

    use_mi_phase = phases[0]
    assert use_mi_phase.action is ActionCode.USE_MI
    assert use_mi_phase.obj == book.item_id
    assert use_mi_phase.extra == []
    assert use_mi_phase.nested_plan is None


def test_use_mi_phase_without_a_chosen_item_is_rejected():
    form = _use_mi_form()

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=_state())
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "choose a Magic Item to Use" in str(exc)


def test_use_mi_phase_rejects_an_item_not_owned_by_this_leader_even_via_a_direct_tampered_value():
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=1, name="Bram", location=HOME))
    wand = state.add_item(Treasure.WAND_BLESS, 2, charges=2)
    form = _use_mi_form(use_mi_item=str(wand.item_id), use_mi_province_target=f"{HOME.x},{HOME.y}")

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "choose a Magic Item to Use" in str(exc)


def test_use_mi_phase_rejects_a_combat_only_wand_even_via_a_direct_tampered_value():
    # Treasure.WAND_FIREBALL (Spell.FIREBALL) is Personal-Combat-only --
    # never offered by use_mi_item_options(), but _parse_use_mi_phase()
    # itself must also reject a direct, tampered POST naming it.
    state = _state()
    wand = state.items_held_by(KING_ID)[0]
    assert wand.treasure is Treasure.WAND_FIREBALL
    form = _use_mi_form(use_mi_item=str(wand.item_id))

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "choose a Magic Item to Use" in str(exc)


def test_use_mi_phase_rejects_an_uncharged_wand_even_via_a_direct_tampered_value():
    state = _state()
    wand = state.add_item(Treasure.WAND_BLESS, KING_ID, charges=0)
    form = _use_mi_form(use_mi_item=str(wand.item_id), use_mi_province_target=f"{HOME.x},{HOME.y}")

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "choose a Magic Item to Use" in str(exc)


def test_build_composed_kingdom_round_trips_a_use_mi_wand_order():
    state = _state()
    wand = state.add_item(Treasure.WAND_BLESS, KING_ID, charges=2)
    form = _use_mi_form(use_mi_item=str(wand.item_id), use_mi_province_target=f"{HOME.x},{HOME.y}")

    kingdom = build_composed_kingdom(state, game_label="Testia", turn_number=1, kingdom_id=1, form=form)
    text = write_k1_moves_file(kingdom)
    tmp = Path(tempfile.mktemp())
    tmp.write_text(text, encoding="utf-8")
    try:
        reparsed = parse_k1_moves_file(tmp)
    finally:
        tmp.unlink(missing_ok=True)

    phase0 = reparsed.leaders[0].plan.segments[0].phases["P0"]
    assert phase0.action is ActionCode.USE_MI
    assert phase0.obj == wand.item_id
    assert decode_hex_number(phase0.extra[0], state.board_width) == HOME


def test_build_composed_kingdom_round_trips_a_use_mi_book_order():
    state = _state()
    book = state.add_item(Treasure.BOOK_MELEE, KING_ID)
    form = _use_mi_form(use_mi_item=str(book.item_id))

    kingdom = build_composed_kingdom(state, game_label="Testia", turn_number=1, kingdom_id=1, form=form)
    text = write_k1_moves_file(kingdom)
    tmp = Path(tempfile.mktemp())
    tmp.write_text(text, encoding="utf-8")
    try:
        reparsed = parse_k1_moves_file(tmp)
    finally:
        tmp.unlink(missing_ok=True)

    phase0 = reparsed.leaders[0].plan.segments[0].phases["P0"]
    assert phase0.action is ActionCode.USE_MI
    assert phase0.obj == book.item_id
    assert phase0.extra == []


def test_special_encounter_plan_defaults_to_flee_when_left_untouched():
    # Sourced directly from the user (2026-11-02): the Special Encounter
    # Plan table's own idle state (no sep_tactic_* fields posted at all)
    # must still compose the real DEFAULT_SP every sample file already
    # shows, not a genuinely empty plan -- an empty plan reads as
    # aggressive Melee intent per turn/sep_decode.py's own Plan_Intent()
    # port, which would silently flip every leader's own default posture
    # the moment this table first renders.
    state = _state()
    form = _all_defend_form(KING_ID)
    # No sep_tactic_* fields posted at all -- the same "field simply
    # never submitted" shape a real browser gives for an untouched table.

    kingdom = build_composed_kingdom(state, game_label="Testia", turn_number=1, kingdom_id=1, form=form)

    assert kingdom.leaders[0].plan.segments[0].sp == DEFAULT_SP


def test_special_encounter_plan_reads_a_composed_tactic():
    state = _state()
    form = _all_defend_form(KING_ID)
    form[f"sep_tactic_{KING_ID}_0_0"] = str(int(Maneuver.MELEE))

    kingdom = build_composed_kingdom(state, game_label="Testia", turn_number=1, kingdom_id=1, form=form)

    assert kingdom.leaders[0].plan.segments[0].sp == (int(Maneuver.MELEE), -1)


def test_special_encounter_plan_reads_more_tactics_than_a_real_phase_allows():
    # 2026-11-16, user-requested "add as many tactics as you like" --
    # EXPANDABLE_TACTIC_SLOT_COUNT (25) is well past TACTIC_SLOT_COUNT
    # (7), the real-sample-sourced cap every actual phase's own
    # Encounter Plan still uses.
    state = _state()
    form = _all_defend_form(KING_ID)
    for slot in range(10):
        form[f"sep_tactic_{KING_ID}_0_{slot}"] = str(int(Maneuver.MELEE))

    kingdom = build_composed_kingdom(state, game_label="Testia", turn_number=1, kingdom_id=1, form=form)

    assert kingdom.leaders[0].plan.segments[0].sp == tuple([int(Maneuver.MELEE)] * 10 + [-1])


def test_special_encounter_plan_rejects_give_even_via_a_direct_tampered_value():
    # 2026-11-14 correction (user-confirmed): this used to allow Give,
    # on the reasoning that turn/sep_decode.py's own Plan_Intent() port
    # classifies CGive as a real SEP tactic -- true for decoding an
    # already-submitted real plan, but Give/Steal/Talk are each real
    # only in an *active* plan (Search/Challenge/Trail/Pursue), never a
    # leader's own standing, passive one. The dropdown never offers it
    # here any more; this confirms a direct, tampered POST is rejected
    # too.
    state = _state()
    item = state.add_item(Treasure.WAND_FIREBALL, KING_ID, charges=1)
    form = _all_defend_form(KING_ID)
    form[f"sep_tactic_{KING_ID}_0_0"] = str(int(Maneuver.GIVE))
    form[f"sep_tactic_give_item_{KING_ID}_0_0"] = str(item.item_id)

    try:
        build_composed_kingdom(state, game_label="Testia", turn_number=1, kingdom_id=1, form=form)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "Give isn't usable in a standing Special Encounter Plan" in str(exc)


def test_special_encounter_plan_rejects_beg_even_via_a_direct_tampered_value():
    state = _state()
    form = _all_defend_form(KING_ID)
    form[f"sep_tactic_{KING_ID}_0_0"] = str(int(Maneuver.BEG))

    try:
        build_composed_kingdom(state, game_label="Testia", turn_number=1, kingdom_id=1, form=form)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "Special Encounter Plan" in str(exc)


def test_special_encounter_plan_is_independent_per_leader():
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=1, name="Bram", location=HOME))
    form = _all_defend_form(KING_ID)
    form.update(_all_defend_form(2))
    form[f"sep_tactic_{KING_ID}_0_0"] = str(int(Maneuver.MELEE))
    # sep_tactic_2_0_0 deliberately left unset -- Bram's own plan stays DEFAULT_SP.

    kingdom = build_composed_kingdom(state, game_label="Testia", turn_number=1, kingdom_id=1, form=form)

    king_block = next(leader for leader in kingdom.leaders if leader.leader_id == KING_ID)
    bram_block = next(leader for leader in kingdom.leaders if leader.leader_id == 2)
    assert king_block.plan.segments[0].sp == (int(Maneuver.MELEE), -1)
    assert bram_block.plan.segments[0].sp == DEFAULT_SP


def test_build_composed_kingdom_round_trips_a_special_encounter_plan():
    state = _state()
    form = _all_defend_form(KING_ID)
    form[f"sep_tactic_{KING_ID}_0_0"] = str(int(Maneuver.FLEE))
    form[f"sep_tactic_{KING_ID}_0_1"] = str(int(Maneuver.MELEE))

    kingdom = build_composed_kingdom(state, game_label="Testia", turn_number=1, kingdom_id=1, form=form)
    text = write_k1_moves_file(kingdom)
    tmp = Path(tempfile.mktemp())
    tmp.write_text(text, encoding="utf-8")
    try:
        reparsed = parse_k1_moves_file(tmp)
    finally:
        tmp.unlink(missing_ok=True)

    assert reparsed.leaders[0].plan.segments[0].sp == (int(Maneuver.FLEE), int(Maneuver.MELEE), -1)


# ---- Hand-typed targets of the character-targeted spells ---------------------------------------------------------


def test_a_hand_typed_charm_target_need_not_be_in_this_province_when_the_orders_are_written():
    # The point of typing a number: the hero the dropdown does not offer (yet) -- e.g. one who will be here only when this
    # phase comes. Where he stands at the start of the turn says nothing; the cast checks it when it is resolved.
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=None, name="Elsewhere", location=HexCoord(5, 5)))
    form = _cast_form(cast_spell=str(int(Spell.CHARM)), cast_charm_target_number="2")

    assert parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)[0].extra == [2]


def test_a_dropdown_charm_target_in_another_province_is_still_refused():
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=None, name="Elsewhere", location=HexCoord(5, 5)))
    form = _cast_form(cast_spell=str(int(Spell.CHARM)), cast_charm_target="2")

    with pytest.raises(InvalidComposedMovesError, match="choose a Charm target"):
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)


def test_a_hand_typed_charm_target_that_is_no_hero_says_so():
    state = _state()
    form = _cast_form(cast_spell=str(int(Spell.CHARM)), cast_charm_target_number="999")

    with pytest.raises(InvalidComposedMovesError, match=r"Charm target #999 is not a hero"):
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)


def test_a_hand_typed_charm_target_cannot_be_the_caster_himself():
    state = _state()
    form = _cast_form(cast_spell=str(int(Spell.CHARM)), cast_charm_target_number=str(KING_ID))

    with pytest.raises(InvalidComposedMovesError, match="can't Charm himself"):
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)


def test_a_hand_typed_kill_enemy_target_elsewhere_is_accepted():
    state = _state()
    state.add_leader(LeaderState(leader_id=2, kingdom_id=None, name="Elsewhere", location=HexCoord(5, 5)))
    form = _cast_form(cast_spell=str(int(Spell.KILL_ENEMY)), cast_kill_enemy_target_number="2")

    assert parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=state)[0].extra == [2]


def test_a_hand_typed_resurrection_target_must_be_a_known_hero_living_or_dead():
    state = _state()
    state.dead_leaders[7] = LeaderState(leader_id=7, kingdom_id=None, name="Late Hero", location=HexCoord(5, 5))
    accepted = _cast_form(cast_spell=str(int(Spell.RESURRECTION)), cast_resurrection_target_number="7")
    refused = _cast_form(cast_spell=str(int(Spell.RESURRECTION)), cast_resurrection_target_number="123")

    assert parse_phase_inputs(accepted, KING_ID, board_width=BOARD_WIDTH, state=state)[0].extra == [7]
    with pytest.raises(InvalidComposedMovesError, match="Resurrection target #123 is not a hero"):
        parse_phase_inputs(refused, KING_ID, board_width=BOARD_WIDTH, state=state)


def test_a_rejected_order_names_the_hero_it_belongs_to():
    from ak_engine.webapp.moves_compose import build_composed_kingdom

    state = _state()
    form = _cast_form(cast_spell=str(int(Spell.CHARM)))  # no Charm target at all

    with pytest.raises(InvalidComposedMovesError) as caught:
        build_composed_kingdom(state, game_label="G", turn_number=1, kingdom_id=1, form=form)

    assert caught.value.leader_id == KING_ID
    assert str(caught.value).startswith("King (#") or "(#" in str(caught.value)
    assert "P0: choose a Charm target." in str(caught.value)
