"""The GM webapp's own "compose moves" editor -- lets the GM build a
Kingdom's move submission for the next turn directly from the
interface, instead of always having to upload a real ``.K1`` file
(sourced directly from the user, 2026-10-26).

**The base, deliberately generic**: every phase (``P0``..``P4``) takes
a plain ``ActionCode`` + an ``obj`` integer + a list of ``extra``
integers -- the exact same three values a real move file's own ``P<n>
: <action> <obj> <extra...>`` line carries, with no command-specific
guidance (a friendlier "Move to province X"/"Recruit 3 Bowmen" form per
action is deliberately left for a later round, decided one command at a
time with the user -- see this module's own commit message). A Special
Encounter Plan (``PlanSegment.sp``) and a nested Hire/Charm/Resurrection
plan (``PlanPhase.nested_plan``) aren't exposed here yet either, for the
same reason -- every composed leader gets the plain ``(10, -1)``
"nothing special configured" ``SP:`` value every real sample already
shows by default, and no nested plan.

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

from ak_engine.models.enums import ActionCode
from ak_engine.models.game_state import GameState, LeaderState
from ak_engine.models.kingdom import Kingdom, KingdomMoveHeader
from ak_engine.models.leader import Leader
from ak_engine.models.plan import ActionPlan, PlanPhase, PlanSegment

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


def parse_phase_inputs(form: dict[str, str], leader_id: int) -> list[ComposedPhaseInput]:
    """Reads this one leader's own ``action_<leader_id>_<n>``/``obj_<leader_id>_<n>``/
    ``extra_<leader_id>_<n>`` form fields (``n`` in ``0..PHASE_COUNT-1``)
    into ``PHASE_COUNT`` validated phase inputs, in ``P0..P4`` order.
    """

    phases: list[ComposedPhaseInput] = []
    for n in range(PHASE_COUNT):
        action = _parse_action(form.get(f"action_{leader_id}_{n}", ""))
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
        phase_inputs = parse_phase_inputs(form, leader_state.leader_id)
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
