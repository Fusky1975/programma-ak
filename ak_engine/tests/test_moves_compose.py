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

import tempfile
from pathlib import Path

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ARMY_TYPE_BY_ORDINAL, NO_LEADER_SENTINEL, ArmyType
from ak_engine.models.enums import ActionCode, Maneuver, Spell
from ak_engine.models.feature import Feature, FeatureType
from ak_engine.models.game_state import ArmyState, GameState, KingdomState, LeaderState, ProvinceState
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
    DISBAND_ALL_VALUE,
    EMPTY_SEARCH_EXTRA,
    ENCOUNTER_PLAN_CASTABLE_SPELLS,
    LEAVE_ALL_VALUE,
    LEAVE_GARRISON_VALUE,
    InvalidComposedMovesError,
    build_composed_kingdom,
    disband_target_options,
    feature_options,
    item_options,
    leave_army_target_options,
    leave_target_options,
    parse_phase_inputs,
    province_options,
    recruit_target_options,
    recruit_type_options,
    spell_options,
    tactic_options,
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
    state.add_feature(Feature(feature_id=3, coord=HOME, kind=FeatureType.ALTAR, guardian_monster=Monster.NEC_MAGE))
    state.add_item(Treasure.WAND_FIREBALL, KING_ID, charges=3)
    return state


def _all_defend_form(leader_id: int) -> dict[str, str]:
    form = {}
    for n in range(5):
        form[f"action_{leader_id}_{n}"] = str(int(ActionCode.DEFEND))
        form[f"obj_{leader_id}_{n}"] = "0"
        form[f"extra_{leader_id}_{n}"] = ""
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


def test_non_move_phase_is_unaffected_by_the_move_destination_field():
    form = _all_defend_form(KING_ID)
    form[f"obj_{KING_ID}_1"] = "42"
    form[f"extra_{KING_ID}_1"] = "1, 2 3"

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=_state())

    assert phases[1].action is ActionCode.DEFEND
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


def test_tactic_options_excludes_give_everywhere():
    # Give isn't a Search Encounter Plan tactic at all (sourced directly
    # from the user, 2026-10-28): it's used only after Challenge (EN) or
    # Pursue (PU), never against a monster encountered in a Feature.
    for slot in (0, 1):
        values = {value for value, _ in tactic_options(slot)}
        assert int(Maneuver.GIVE) not in values


def test_search_phase_rejects_give_even_via_a_direct_tampered_value():
    form = _search_form(tactics={0: int(Maneuver.GIVE)}, subs={0: 7})

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=_state())
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "Give isn't usable in a Search Encounter Plan" in str(exc)


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


def test_spell_options_lists_exactly_the_17_encounter_plan_castable_spells():
    values = {value for value, _ in spell_options()}
    assert values == {int(spell) for spell in ENCOUNTER_PLAN_CASTABLE_SPELLS}
    assert len(ENCOUNTER_PLAN_CASTABLE_SPELLS) == 17
    assert Spell.GATE_ANGEL in ENCOUNTER_PLAN_CASTABLE_SPELLS


def test_search_phase_cast_an_encounter_plan_spell_is_included():
    form = _search_form(tactics={0: int(Maneuver.CAST)}, spells={0: int(Spell.FIREBALL)})

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=_state())

    assert phases[0].extra == [0, int(Maneuver.CAST), int(Spell.FIREBALL), -1]


def test_search_phase_cast_gate_angel_is_included():
    form = _search_form(tactics={0: int(Maneuver.CAST)}, spells={0: int(Spell.GATE_ANGEL)})

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=_state())

    assert phases[0].extra == [0, int(Maneuver.CAST), int(Spell.GATE_ANGEL), -1]


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
    # apply here the way Talk's "slot 0 only" rule allows.
    for slot in (0, 1, 3):
        values = {value for value, _ in tactic_options(slot)}
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
    # so nothing filters it out of any slot.
    for slot in (0, 1, 3):
        values = {value for value, _ in tactic_options(slot)}
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
    state = _state()
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
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.RECRUIT))
    form[f"recruit_target_{KING_ID}_0"] = "2"
    form[f"recruit_type_{KING_ID}_0_0"] = str(_ORDINAL_BY_ARMY_TYPE[ArmyType.BOWMEN])

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH, state=_state())

    assert phases[0].obj == 2


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
    assert (DISBAND_ALL_VALUE, "Disband ALL I command") in options


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
    assert (LEAVE_ALL_VALUE, "Leave ALL I command") in options


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
