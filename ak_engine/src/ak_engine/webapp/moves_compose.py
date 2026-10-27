"""The GM webapp's own "compose moves" editor -- lets the GM build a
Kingdom's move submission for the next turn directly from the
interface, instead of always having to upload a real ``.K1`` file
(sourced directly from the user, 2026-10-26).

**The base, deliberately generic**: every phase (``P0``..``P4``) takes
a plain ``ActionCode`` + an ``obj`` integer + a list of ``extra``
integers -- the exact same three values a real move file's own ``P<n>
: <action> <obj> <extra...>`` line carries, with no command-specific
guidance. A friendlier form per action is being decided one command at
a time with the user; **Move (``ActionCode.LMOVE``) is the first one**
(2026-10-26, the user's own choice -- rulebook's own first-listed
action): confirmed directly from ``turn/plan_dispatch.py``'s own LMOVE
branch that ``obj`` is the *only* field Move reads (``turn/hex_
numbering.py decode_hex_number(phase.obj, board_width)``, the target
province) -- ``extra`` is never consulted; every army the moving leader
already commands (``GameState.armies_commanded_by(leader_id)``) moves
together automatically, nothing to list. The GM's own chosen syntax
(2026-10-26): a province-name dropdown (``province_options()`` below)
replaces the raw Object field for a Move phase specifically. **Explore
(``ActionCode.EXPLORE``) is the second one** (2026-10-26, the user's own
choice -- rulebook's own second-listed action, and their own direct
observation): confirmed directly from ``turn/plan_dispatch.py``'s own
EXPLORE branch that neither ``obj`` nor ``extra`` is read at all --
``province = state.provinces[state.leaders[leader_id].location]``, the
acting leader's own current province, always. Explore needs no input
whatsoever; ``obj``/``extra`` are simply forced to ``0``/``[]``.
**Search (``ActionCode.SEARCH``) is the third, and the user's own
explicit "telaio" (skeleton/frame) request** (2026-10-26): the target
feature number, via a dedicated feature dropdown (``feature_options()``
below) -- confirmed directly from ``turn/search_decode.py``'s own
module docstring/``SearchRequest``: ``obj`` is the target feature's own
number, ``extra[0]`` ("tl") is an unconfirmed, always-``0``-in-every-
real-sample slot, and the remainder of ``extra`` is a ``-1``-terminated
**Encounter Plan** tactic list (Cast, Use Item, Talk, Say, Give,
Fulfill, Steal, Shoot, Melee, Flee, Beg, Scout -- rulebook [5.1]-[5.8]),
designed with the user one tactic at a time, via ``TACTIC_SLOT_COUNT``
(``7``, the longest real ``AK3__T*.K1`` sample's own tactic list)
dedicated ``tactic_<leader>_<n>_<slot>`` dropdowns per Search phase,
each with an optional ``tactic_sub_<leader>_<n>_<slot>`` sub-object
field for a ``TACTICS_WITH_SUB_OBJECT`` maneuver (Cast/Use Item/Give).
An empty slot stops the list there -- a later non-empty slot after one
is rejected, not silently dropped. ``Say``'s own free-text argument
isn't composable yet (not offered in the dropdown at all -- see
``parser/k1_moves_writer.py``'s own matching "SAY not supported"
decision), nor is ``Maneuver.NONE`` (a sentinel, never a real tactic).

**Talk ([5.5]), the user's own first tactic to design** (2026-10-26,
sourced directly from them): "può essere usata solo all'inizio del
piano d'incontro. Se viene usata dopo un'altra tattica viene
semplicemente ignorata" -- confirmed structurally impossible to even
select here instead of silently inert: Talk is only ever offered in
slot 0's own dropdown, and ``_parse_search_tactics()`` rejects it
outright at any other slot (a direct, tampered POST bypassing the
dropdown) rather than letting a real-but-inert tactic through quietly.
"Come da regolamento, Non è possibile usare sia la tattica Talk che
Fulfill nello stesso Piano d'Incontro" -- independently confirmed from
``turn/search_execution.py``'s own ``_resolve_fulfill()`` docstring
(rulebook [5.6]): rejected if both appear in the same tactic list.

**Fulfill ([5.7]), the second tactic designed** (2026-10-27, sourced
directly from the user): "Funziona solo se un eroe o un re ha
ricevuto da un mostro nei turni precedenti dopo una tattica TALK una
quest (numerata col numero d'ordine del feature). Se la quest è
risolta l'eroe o il re riceve il premio" -- independently confirmed
from ``turn/search_execution.py``'s own ``_resolve_fulfill()``:
``feature.pending_deal_leader_id`` (set by a *prior* turn's successful
Talk, ``_resolve_talk()``) must equal the acting leader's own id, and
the targeted feature is already exactly the one this same Search
phase's own ``obj`` names -- there is no separate "quest id" to pick,
only the feature dropdown already built for Search itself.
**Nothing new to compose for Fulfill, structurally**: it carries no
sub-object (confirmed absent from ``TACTICS_WITH_SUB_OBJECT``) and has
no position restriction of its own (unlike Talk) -- it was already
fully selectable, in any slot, the moment ``_COMPOSABLE_MANEUVERS`` and
the Talk/Fulfill exclusion above existed. The one real, useful addition
here is informational: ``feature_options()``'s own ``leader_id``
parameter flags a feature this leader already holds a pending deal on
("-- pending quest for this leader"), so the GM can actually tell,
right in the Search dropdown, which feature a Fulfill tactic would do
something on this turn.

A Search phase composed here always gets the immediately-terminated
empty tactic list ``[0, -1]`` ("tl=0, no tactics") when every slot is
left empty, matching the previous round's own placeholder default.

Every other not-yet-designed action still falls back to the plain
Object/Extra integers. A Special Encounter Plan (``PlanSegment.sp``)
and a nested Hire/Charm/Resurrection plan (``PlanPhase.nested_plan``)
aren't exposed here yet either, for the same reason -- every composed
leader gets the plain ``(10, -1)`` "nothing special configured" ``SP:``
value every real sample already shows by default, and no nested plan.

**Why this goes through a real ``Kingdom`` + ``parser/k1_moves_writer.py``
rather than writing straight to ``GameState``**: the exact same shape a
future player-facing "create your own moves" UI will need to produce
(per the user's own explicit request) -- building both producers around
the same ``Kingdom`` dataclass and the same writer is what guarantees
they stay in sync, rather than two independent guesses at "the same
format" drifting apart. The composed file is saved through the exact
same ``save_uploaded_move_file()`` path a real upload uses, so turn
processing can't tell the difference.
"""

from __future__ import annotations

from dataclasses import dataclass

from ak_engine.models.enums import TACTICS_WITH_SUB_OBJECT, ActionCode, Maneuver
from ak_engine.models.feature import FEATURE_TYPE_NAMES
from ak_engine.models.game_state import GameState, LeaderState
from ak_engine.models.kingdom import Kingdom, KingdomMoveHeader
from ak_engine.models.leader import Leader
from ak_engine.models.map import HexCoord
from ak_engine.models.monster import MONSTER_NAMES
from ak_engine.models.plan import ActionPlan, PlanPhase, PlanSegment
from ak_engine.report.turn_report import real_province_number
from ak_engine.turn.hex_numbering import encode_hex_number

# Search's own "tl" slot (``turn/search_decode.py SearchRequest.
# unconfirmed_extra0``, always 0 in every real sample) followed by the
# Encounter Plan's own -1 terminator with no tactics in between --
# "nothing composed yet", the default when every tactic slot is empty.
EMPTY_SEARCH_EXTRA: list[int] = [0, -1]

# The longest real Encounter Plan tactic list across every AK3__T*.K1
# sample (``AK3__T10.K1`` leader 72's own 7-tactic CAST/CAST/CAST/CAST/
# CAST/MELEE/SCOUT plan) -- a generous, real-data-sourced slot count,
# not an arbitrary round number.
TACTIC_SLOT_COUNT = 7

# Every Maneuver a GM can compose here -- Maneuver.SAY is excluded (its
# own free-text argument isn't composable yet, see this module's own
# docstring) and Maneuver.NONE is a sentinel, never a real tactic.
_COMPOSABLE_MANEUVERS: tuple[Maneuver, ...] = tuple(
    maneuver for maneuver in Maneuver if maneuver not in (Maneuver.SAY, Maneuver.NONE)
)

PHASE_COUNT = 5  # P0..P4 -- every real AK3__T*.K1 sample's own leader block shape.

# "Nothing special configured" -- the one Special Encounter Plan value
# every leader in this project's own real sample files shows (sourced
# directly: no sample has ever shown a different SP: value). Composing
# a real Special Encounter Plan is deferred to a later round.
DEFAULT_SP: tuple[int, ...] = (10, -1)

# A safe, real-sample-matched default for the move file's own header
# line -- confirmed unused by turn processing (turn/kingdom_bridge.py
# never reads a single field of it), so any valid-shaped value works.
DEFAULT_HEADER_RAW_FIELDS: list[int] = [27, 1, 0, 101, 1, 15, 1]


class InvalidComposedMovesError(ValueError):
    """Raised when the GM's own composed-moves form can't be turned into a valid ``Kingdom``."""


def kingdom_leaders_for_compose(state: GameState, kingdom_id: int) -> list[LeaderState]:
    """Every leader this Kingdom would need to submit a move-file entry
    for this turn: the King first, then every Hero currently in this
    Kingdom's service (``kingdom_id`` match) -- the exact same roster a
    real move file's own leader blocks list, by this project's own
    established ``is_king`` convention.
    """

    leaders = [leader for leader in state.leaders.values() if leader.kingdom_id == kingdom_id]
    leaders.sort(key=lambda leader: (not leader.is_king, leader.leader_id))
    return leaders


def province_options(state: GameState) -> list[tuple[str, str]]:
    """Every province as a ``(value, label)`` pair for a Move phase's own
    destination dropdown -- ``value`` is ``"x,y"`` (parsed back by
    ``_parse_move_target()``), ``label`` is the province's own real name
    where one exists (else just its coordinate), its ``(x, y)``
    coordinate, and its real "#<N>" province number (``report/turn_
    report.py real_province_number()``, the same ``x*100+y`` convention
    real reports already show, e.g. "Mongu (#305)" -- sourced directly
    from the user, 2026-10-26, who asked for it alongside the name/
    coordinates "come nell'AK originale"). This is purely a display
    label: the dropdown's own submitted ``value``, and the destination
    this module actually encodes into the move file, is still the
    plain ``x,y`` coordinate -- see this module's own docstring for why
    the real province number is a different, display-only scheme from
    the internal Move-order encoding. Sorted in map reading order (row
    by row, left to right).
    """

    provinces = sorted(state.provinces.values(), key=lambda province: (province.coord.y, province.coord.x))
    options = []
    for province in provinces:
        value = f"{province.coord.x},{province.coord.y}"
        name_part = province.name if province.name else ""
        number = real_province_number(province.coord)
        label = f"{name_part} ({province.coord.x}, {province.coord.y}) #{number}".strip()
        options.append((value, label))
    return options


def feature_options(state: GameState, *, leader_id: int | None = None) -> list[tuple[str, str]]:
    """Every feature as a ``(value, label)`` pair for a Search phase's own
    target-feature dropdown -- ``value`` is the feature's own real
    ``feature_id`` (exactly what ``obj`` is for Search, so no separate
    encoding step is needed the way Move's own coordinate needs
    ``encode_hex_number()``). ``label`` names its kind, the province
    it sits in (name where one exists, else coordinate), and its
    guardian monster where one is known and the feature hasn't already
    been looted -- e.g. "#3 Altar -- Numenor (3, 9) -- Necromancer".
    Sorted by ``feature_id``, the same "#<N>" a GM would already look
    the feature up by on a PROVINCES report's own "Features and F#"
    column.

    ``leader_id`` (sourced directly from the user, 2026-10-27, as part
    of designing the Fulfill tactic): when given, a feature this leader
    currently holds a pending deal on (``Feature.pending_deal_leader_id``
    -- the one a prior turn's successful Talk set, per ``turn/search_
    execution.py``'s own ``_resolve_talk()``/``_resolve_fulfill()``) is
    flagged "-- pending quest for this leader", since Fulfill (this
    module's own docstring has its full sourcing) always resolves
    *whichever* feature the same Search phase's own ``obj`` already
    names -- there's no separate quest id to pick, only this same
    feature dropdown, so surfacing the one feature Fulfill would
    actually do something on here is the whole point.
    """

    features = sorted(state.features.values(), key=lambda feature: feature.feature_id)
    options = []
    for feature in features:
        province = state.provinces.get(feature.coord)
        place = province.name if province is not None and province.name else f"({feature.coord.x}, {feature.coord.y})"
        label = f"#{feature.feature_id} {FEATURE_TYPE_NAMES[feature.kind]} -- {place}"
        if feature.guardian_monster is not None and not feature.looted:
            label += f" -- {MONSTER_NAMES.get(feature.guardian_monster, feature.guardian_monster.name.title())}"
        if leader_id is not None and feature.pending_deal_leader_id == leader_id:
            label += " -- pending quest for this leader"
        options.append((str(feature.feature_id), label))
    return options


def tactic_options(slot: int) -> list[tuple[int, str]]:
    """Every composable ``Maneuver`` for one Encounter Plan tactic slot,
    as ``(value, display_name)`` pairs -- ``Maneuver.TALK`` is only ever
    included for ``slot == 0`` (see this module's own docstring for the
    user-sourced "Talk can only be the first tactic" rule); every other
    slot gets the same ``_COMPOSABLE_MANEUVERS`` list minus Talk.
    """

    return [
        (int(maneuver), maneuver.name.replace("_", " ").title())
        for maneuver in _COMPOSABLE_MANEUVERS
        if maneuver is not Maneuver.TALK or slot == 0
    ]


def compose_filename(game_label: str, turn_number: int, kingdom_id: int) -> str:
    """Same Game+Turn+Kingdom naming convention as the XK/SE downloads
    (``webapp/app.py``'s own ``turn_zero_download_xk()``/``turn_report_
    download()``) -- ``.K<kingdom_id>`` is also what ``Kingdom.
    kingdom_id`` itself parses the real Kingdom id back out of.
    """

    return f"AK{game_label}T{turn_number}.K{kingdom_id}"


@dataclass(slots=True)
class ComposedPhaseInput:
    """One phase's own raw form input, already validated to this shape
    by the caller -- see ``build_composed_kingdom()``.
    """

    action: ActionCode
    obj: int
    extra: list[int]


def _parse_action(raw: str) -> ActionCode:
    try:
        return ActionCode(int(raw))
    except (TypeError, ValueError) as exc:
        raise InvalidComposedMovesError(f"{raw!r} is not a valid Action.") from exc


def _parse_int(raw: str, *, field_label: str) -> int:
    try:
        return int(raw)
    except (TypeError, ValueError) as exc:
        raise InvalidComposedMovesError(f"{field_label} must be a whole number, got {raw!r}.") from exc


def _parse_extra(raw: str) -> list[int]:
    stripped = raw.strip()
    if not stripped:
        return []
    values: list[int] = []
    for token in stripped.replace(",", " ").split():
        values.append(_parse_int(token, field_label="Extra"))
    return values


def _parse_move_target(raw: str, *, board_width: int, phase_label: str) -> int:
    if not raw:
        raise InvalidComposedMovesError(f"{phase_label}: choose a Move destination.")
    x_str, _, y_str = raw.partition(",")
    x = _parse_int(x_str, field_label=f"{phase_label} Move destination")
    y = _parse_int(y_str, field_label=f"{phase_label} Move destination")
    return encode_hex_number(HexCoord(x, y), board_width)


def _parse_search_feature(raw: str, *, phase_label: str) -> int:
    if not raw:
        raise InvalidComposedMovesError(f"{phase_label}: choose a Feature to Search.")
    return _parse_int(raw, field_label=f"{phase_label} Search feature")


def _parse_search_tactics(form: dict[str, str], leader_id: int, n: int, *, phase_label: str) -> list[int]:
    """Reads this Search phase's own ``tactic_<leader_id>_<n>_<slot>``/
    ``tactic_sub_<leader_id>_<n>_<slot>`` fields (``slot`` in
    ``0..TACTIC_SLOT_COUNT-1``) into a real, ``-1``-terminated Encounter
    Plan tactic list -- see this module's own docstring for the Talk-
    position and Talk/Fulfill-exclusion rules enforced here.
    """

    tokens: list[int] = []
    has_talk = False
    has_fulfill = False
    stopped_at: int | None = None
    for slot in range(TACTIC_SLOT_COUNT):
        raw = form.get(f"tactic_{leader_id}_{n}_{slot}", "")
        if not raw:
            if stopped_at is None:
                stopped_at = slot
            continue
        if stopped_at is not None:
            raise InvalidComposedMovesError(
                f"{phase_label}: tactic slot {slot + 1} follows empty slot {stopped_at + 1} -- "
                "fill the Encounter Plan without gaps."
            )
        try:
            maneuver = Maneuver(int(raw))
        except (TypeError, ValueError) as exc:
            raise InvalidComposedMovesError(f"{phase_label}: tactic slot {slot + 1} is not a valid tactic.") from exc
        if maneuver not in _COMPOSABLE_MANEUVERS:
            # Defense in depth: Say/None are never offered in the
            # dropdown, but a direct, tampered POST could still name
            # their real ordinal.
            raise InvalidComposedMovesError(f"{phase_label}: tactic slot {slot + 1} isn't composable here yet.")
        if maneuver is Maneuver.TALK:
            if slot != 0:
                raise InvalidComposedMovesError(
                    f"{phase_label}: Talk can only be the first tactic in the Encounter Plan."
                )
            has_talk = True
        if maneuver is Maneuver.FULFILL:
            has_fulfill = True
        tokens.append(int(maneuver))
        if maneuver in TACTICS_WITH_SUB_OBJECT:
            sub_raw = form.get(f"tactic_sub_{leader_id}_{n}_{slot}", "0")
            tokens.append(_parse_int(sub_raw or "0", field_label=f"{phase_label} tactic {slot + 1} sub-object"))

    if has_talk and has_fulfill:
        raise InvalidComposedMovesError(
            f"{phase_label}: Talk and Fulfill can't both be used in the same Encounter Plan."
        )

    tokens.append(-1)
    return tokens


def parse_phase_inputs(form: dict[str, str], leader_id: int, *, board_width: int) -> list[ComposedPhaseInput]:
    """Reads this one leader's own ``action_<leader_id>_<n>``/``obj_<leader_id>_<n>``/
    ``extra_<leader_id>_<n>`` form fields (``n`` in ``0..PHASE_COUNT-1``)
    into ``PHASE_COUNT`` validated phase inputs, in ``P0..P4`` order.

    A Move (``ActionCode.LMOVE``) phase reads its own dedicated
    ``move_target_<leader_id>_<n>`` dropdown field instead of the
    generic Object field (see this module's own docstring for why) --
    ``extra`` is always empty for Move, matching ``turn/plan_dispatch.py``'s
    own confirmed "Move's extra is never read" finding. An Explore
    (``ActionCode.EXPLORE``) phase needs no field at all -- ``obj``/
    ``extra`` are forced to ``0``/``[]`` regardless of whatever the
    generic form fields happen to hold, since Explore always targets
    the acting leader's own current province (same module docstring). A
    Search (``ActionCode.SEARCH``) phase reads its own dedicated
    ``search_feature_<leader_id>_<n>`` dropdown field for ``obj`` (the
    target feature's own ``feature_id``) and its own Encounter Plan
    tactic slots (``_parse_search_tactics()``) for ``extra`` (same
    module docstring).
    """

    phases: list[ComposedPhaseInput] = []
    for n in range(PHASE_COUNT):
        action = _parse_action(form.get(f"action_{leader_id}_{n}", ""))
        if action is ActionCode.LMOVE:
            obj = _parse_move_target(
                form.get(f"move_target_{leader_id}_{n}", ""), board_width=board_width, phase_label=f"P{n}"
            )
            extra: list[int] = []
        elif action is ActionCode.EXPLORE:
            obj = 0
            extra = []
        elif action is ActionCode.SEARCH:
            obj = _parse_search_feature(form.get(f"search_feature_{leader_id}_{n}", ""), phase_label=f"P{n}")
            extra = [0, *_parse_search_tactics(form, leader_id, n, phase_label=f"P{n}")]
        else:
            obj = _parse_int(form.get(f"obj_{leader_id}_{n}", "0") or "0", field_label=f"P{n} Object")
            extra = _parse_extra(form.get(f"extra_{leader_id}_{n}", ""))
        phases.append(ComposedPhaseInput(action=action, obj=obj, extra=extra))
    return phases


def build_composed_kingdom(
    state: GameState,
    *,
    game_label: str,
    turn_number: int,
    kingdom_id: int,
    form: dict[str, str],
) -> Kingdom:
    """Builds the real ``Kingdom`` this Kingdom's composed-moves form
    describes -- one ``Leader``/``ActionPlan`` per ``kingdom_leaders_
    for_compose()`` entry, each read via ``parse_phase_inputs()``.

    Raises ``InvalidComposedMovesError`` if the King can't be identified
    or any phase's own input doesn't parse.
    """

    roster = kingdom_leaders_for_compose(state, kingdom_id)
    king = next((leader for leader in roster if leader.is_king), None)
    if king is None:
        raise InvalidComposedMovesError("This Kingdom has no King on record -- create the world first.")

    leaders: list[Leader] = []
    for leader_state in roster:
        phase_inputs = parse_phase_inputs(form, leader_state.leader_id, board_width=state.board_width)
        phases = {
            f"P{n}": PlanPhase(label=f"P{n}", action=phase_input.action, obj=phase_input.obj, extra=phase_input.extra)
            for n, phase_input in enumerate(phase_inputs)
        }
        segment = PlanSegment(plan_start=0, plan_end=PHASE_COUNT - 1, sp=DEFAULT_SP, phases=phases)
        plan = ActionPlan(leader_id=leader_state.leader_id, segments=[segment])
        leaders.append(Leader(leader_id=leader_state.leader_id, name=leader_state.name, plan=plan))

    skills = king.skills
    if skills is None:
        raise InvalidComposedMovesError(f"{king.name}: this King has no skill table on record yet.")

    return Kingdom(
        source_filename=compose_filename(game_label, turn_number, kingdom_id),
        king_name=king.name,
        king_title=None,
        header=KingdomMoveHeader(raw_fields=list(DEFAULT_HEADER_RAW_FIELDS), sex=king.sex.value if king.sex is not None else "M"),
        skills=skills,
        leaders=leaders,
    )
