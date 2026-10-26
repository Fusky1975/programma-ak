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

from ak_engine.models.alignment import Alignment
from ak_engine.models.enums import ActionCode, Maneuver
from ak_engine.models.feature import Feature, FeatureType
from ak_engine.models.game_state import GameState, KingdomState, LeaderState, ProvinceState
from ak_engine.models.kingdom import SkillTable
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.monster import Monster
from ak_engine.models.race import Race
from ak_engine.turn.hex_numbering import decode_hex_number
from ak_engine.webapp.moves_compose import (
    EMPTY_SEARCH_EXTRA,
    InvalidComposedMovesError,
    build_composed_kingdom,
    feature_options,
    parse_phase_inputs,
    province_options,
    tactic_options,
)

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

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH)

    move_phase = phases[2]
    assert move_phase.action is ActionCode.LMOVE
    assert decode_hex_number(move_phase.obj, BOARD_WIDTH) == HexCoord(3, 2)
    assert move_phase.extra == []


def test_move_phase_without_a_chosen_destination_is_rejected():
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.LMOVE))
    form[f"move_target_{KING_ID}_0"] = ""

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "Move destination" in str(exc)


def test_non_move_phase_is_unaffected_by_the_move_destination_field():
    form = _all_defend_form(KING_ID)
    form[f"obj_{KING_ID}_1"] = "42"
    form[f"extra_{KING_ID}_1"] = "1, 2 3"

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH)

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

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH)

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


def test_search_phase_reads_its_own_dropdown_not_the_generic_object_field():
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_1"] = str(int(ActionCode.SEARCH))
    form[f"search_feature_{KING_ID}_1"] = "3"
    form[f"obj_{KING_ID}_1"] = "999"  # must be ignored for a Search phase
    form[f"extra_{KING_ID}_1"] = "7 8 9"  # must be ignored too -- not composable yet

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH)

    search_phase = phases[1]
    assert search_phase.action is ActionCode.SEARCH
    assert search_phase.obj == 3
    assert search_phase.extra == EMPTY_SEARCH_EXTRA


def test_search_phase_without_a_chosen_feature_is_rejected():
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.SEARCH))
    form[f"search_feature_{KING_ID}_0"] = ""

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH)
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


def _search_form(feature_id: int = 3, tactics: dict[int, int] | None = None, subs: dict[int, int] | None = None):
    form = _all_defend_form(KING_ID)
    form[f"action_{KING_ID}_0"] = str(int(ActionCode.SEARCH))
    form[f"search_feature_{KING_ID}_0"] = str(feature_id)
    for slot, maneuver_value in (tactics or {}).items():
        form[f"tactic_{KING_ID}_0_{slot}"] = str(maneuver_value)
    for slot, sub_value in (subs or {}).items():
        form[f"tactic_sub_{KING_ID}_0_{slot}"] = str(sub_value)
    return form


def test_tactic_options_offers_talk_only_in_slot_zero():
    slot0_values = {value for value, _ in tactic_options(0)}
    slot1_values = {value for value, _ in tactic_options(1)}
    assert int(Maneuver.TALK) in slot0_values
    assert int(Maneuver.TALK) not in slot1_values


def test_tactic_options_excludes_say_and_none_everywhere():
    for slot in (0, 1):
        values = {value for value, _ in tactic_options(slot)}
        assert int(Maneuver.SAY) not in values
        assert int(Maneuver.NONE) not in values


def test_search_phase_with_a_simple_tactic_sequence():
    form = _search_form(tactics={0: int(Maneuver.MELEE), 1: int(Maneuver.SCOUT)})

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH)

    assert phases[0].extra == [0, int(Maneuver.MELEE), int(Maneuver.SCOUT), -1]


def test_search_phase_tactic_with_sub_object_is_included():
    form = _search_form(tactics={0: int(Maneuver.CAST)}, subs={0: 7})

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH)

    assert phases[0].extra == [0, int(Maneuver.CAST), 7, -1]


def test_search_phase_talk_as_the_first_tactic_is_accepted():
    form = _search_form(tactics={0: int(Maneuver.TALK)})

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH)

    assert phases[0].extra == [0, int(Maneuver.TALK), -1]


def test_search_phase_talk_after_another_tactic_is_rejected():
    # Sourced directly from the user (2026-10-26): "può essere usata
    # solo all'inizio del piano d'incontro. Se viene usata dopo
    # un'altra tattica viene semplicemente ignorata" -- rejected here
    # rather than silently accepted-but-inert, so a direct/tampered
    # submission never produces a quietly-wrong file.
    form = _search_form(tactics={0: int(Maneuver.MELEE), 1: int(Maneuver.TALK)})

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH)
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
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "Talk and Fulfill" in str(exc)


def test_search_phase_fulfill_alone_is_accepted():
    form = _search_form(tactics={0: int(Maneuver.FULFILL)})

    phases = parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH)

    assert phases[0].extra == [0, int(Maneuver.FULFILL), -1]


def test_search_phase_fulfill_after_talk_slot_but_not_in_slot_zero_is_still_rejected():
    # Talk must be in slot 0 specifically -- Fulfill anywhere else is
    # fine on its own, but combining it with Talk (wherever Talk sits)
    # is still rejected by the Talk/Fulfill exclusion rule above.
    form = _search_form(tactics={0: int(Maneuver.TALK), 1: int(Maneuver.FULFILL)})

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "Talk and Fulfill" in str(exc)


def test_search_phase_rejects_a_gap_between_tactic_slots():
    form = _search_form(tactics={0: int(Maneuver.MELEE), 2: int(Maneuver.SCOUT)})  # slot 1 left empty

    try:
        parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH)
        assert False, "expected InvalidComposedMovesError"
    except InvalidComposedMovesError as exc:
        assert "gaps" in str(exc)


def test_search_phase_rejects_say_and_none_even_via_a_direct_tampered_value():
    for maneuver in (Maneuver.SAY, Maneuver.NONE):
        form = _search_form(tactics={0: int(maneuver)})
        try:
            parse_phase_inputs(form, KING_ID, board_width=BOARD_WIDTH)
            assert False, "expected InvalidComposedMovesError"
        except InvalidComposedMovesError as exc:
            assert "isn't composable" in str(exc)


def test_build_composed_kingdom_round_trips_an_encounter_plan():
    state = _state()
    form = _search_form(tactics={0: int(Maneuver.TALK)})

    kingdom = build_composed_kingdom(state, game_label="Testia", turn_number=1, kingdom_id=1, form=form)

    phase0 = kingdom.leaders[0].plan.segments[0].phases["P0"]
    assert phase0.extra == [0, int(Maneuver.TALK), -1]
