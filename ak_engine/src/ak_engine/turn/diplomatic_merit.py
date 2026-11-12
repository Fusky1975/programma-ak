"""Silver Tongue (Office.DIPLOMAT, id 41) merit -- Phase 445.

Sourced from a user-supplied reverse-engineering dossier,
``AKGEN_reverse_engineering_report (2).md`` SS18.3 (NOT a project file,
never committed): for every ordered pair of Kingdoms ``(receiver,
partner)`` with ``receiver != partner``, the receiver's own delta this
turn is

    delta_diplomatic_merit(receiver) = A + 2*B + 5*S

where, independently per ``partner``:

- ``A`` (``+1``): ``partner``'s relation to ``receiver`` is at least
  Allied (this project only models a binary ``allied_kingdoms`` relation
  -- no separate Enemy/Neutral/Allied/Teamed four-state, and no "Teamed"
  concept at all -- so ``GameState.is_allied()`` is the sourced, correct
  proxy for "relation >= Allied"; a documented simplification, the same
  category as Phase 137's other missing globals, not a silent guess).
- ``B`` (``+2``): at least one province ``receiver`` owns is hex-adjacent
  to a province ``partner`` owns. Deliberately narrower than
  ``turn/scientific_treaty.py _kingdoms_in_contact()``'s own "adjacent OR
  a leader is present" access rule for the Scientific Treaty exchange
  itself -- the dossier's own Silver Tongue text is adjacency-only, so
  ``_kingdoms_are_adjacent()`` below duplicates just that half rather
  than reusing the broader check.
- ``S`` (``+5`` per transfer): a Discovery was actually transferred to
  ``receiver`` from ``partner`` via Scientific Treaty this turn --
  reused directly from ``turn/scientific_treaty.py execute_scientific_
  treaties()``'s own already-computed ``ScientificTreatyResult`` list
  (that function must run first; this module never recomputes treaties).

**Credited to the receiving Kingdom's own King** (``Ofc_Pts``/``Tit_Pts``
are always leader-keyed, never Kingdom-keyed) -- a Kingdom with no
current King (an empty throne) simply receives no credit that turn, the
same "documented, permissive-missing-data" convention used throughout
this project rather than raising.
"""

from __future__ import annotations

from collections.abc import Sequence

from ak_engine.models.game_state import GameState
from ak_engine.turn.movement import MapBounds, is_adjacent
from ak_engine.turn.scientific_treaty import ScientificTreatyResult


def _king_leader_id(state: GameState, kingdom_id: int) -> int | None:
    for leader in state.leaders.values():
        if leader.kingdom_id == kingdom_id and leader.is_king:
            return leader.leader_id
    return None


def _kingdoms_are_adjacent(state: GameState, kingdom_a_id: int, kingdom_b_id: int, bounds: MapBounds) -> bool:
    provinces_a = [p for p in state.provinces.values() if p.owner_kingdom_id == kingdom_a_id]
    provinces_b = [p for p in state.provinces.values() if p.owner_kingdom_id == kingdom_b_id]
    return any(is_adjacent(pa.coord, pb.coord, bounds) for pa in provinces_a for pb in provinces_b)


def apply_diplomatic_merit(
    state: GameState,
    treaty_results: Sequence[ScientificTreatyResult],
    *,
    board_width: int,
    board_height: int,
) -> None:
    """Applies this turn's Silver Tongue delta to every eligible receiving
    Kingdom's own King -- see module docstring for the full sourced
    formula. ``treaty_results`` must be this same turn's own ``execute_
    scientific_treaties()`` output.
    """

    bounds = MapBounds(board_width, board_height)
    kingdom_ids = list(state.kingdoms.keys())

    for receiver_id in kingdom_ids:
        king_id = _king_leader_id(state, receiver_id)
        if king_id is None:
            continue
        king = state.leaders[king_id]

        for partner_id in kingdom_ids:
            if partner_id == receiver_id:
                continue

            # Phase 1191 bug fix: A and B are independent per-partner terms
            # (module docstring) -- B must still apply to a non-allied but
            # adjacent partner, not only when A also applies.
            if state.is_allied(receiver_id, partner_id):
                king.merit_tally.diplomatic_merit_points += 1

            if _kingdoms_are_adjacent(state, receiver_id, partner_id, bounds):
                king.merit_tally.diplomatic_merit_points += 2

        for result in treaty_results:
            if result.kingdom_a_id == receiver_id and result.discovery_to_a is not None:
                king.merit_tally.diplomatic_merit_points += 5
            elif result.kingdom_b_id == receiver_id and result.discovery_to_b is not None:
                king.merit_tally.diplomatic_merit_points += 5
