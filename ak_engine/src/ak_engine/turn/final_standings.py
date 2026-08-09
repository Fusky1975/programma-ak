"""End-of-game standings -- `kingpoints`, the real composite sort key, and
Kingdom ranking. AKGEN_reverse_engineering_report (2).md SS14.6, Phase
454. Phase 455 extends this module with the all-star/Valhalla-induction
threshold checks the same source section also covers.

**Deliberately out of scope**: the real prize-money formula (`prcred`,
based on `totfees`/`prizeperc` -- real-money moderator turn-fee dues) is
moderator/real-money bookkeeping, not in-game state this project models
anywhere, the same documented scope boundary already established for
`kteam` (`turn/victory_points.py`'s own module docstring). Also
deliberately not replicated: the dossier's own confirmed **compiled bug**
in the real team-ranking code (`kingpoints[team2]` misreading a team
index as a Kingdom index) -- this project has never modeled a "team"
concept at all (same `kteam` boundary), so there is no team-ranking code
path to reproduce that bug in.

**`kingdom_points()`**: `0.0` before any Emperor is elected (mirrors
`turn/victory_points.py office_victory_points()`'s own "nothing until an
Emperor exists" gate -- this recomputes every turn after coronation, not
as a one-time "game over" event, matching the real engine's own
recompute-on-every-`Pray_Report` behavior; no separate "is this the last
turn" detection is needed). Otherwise, sums `office_victory_points()`
(the real Alignment-discounted award, see that module's own docstring)
over every one of `turn/office_holder.py ALL_OFFICES` (Office.EMPEROR
included -- the elected Emperor's own Kingdom banks its own Emperor
Victory Points too, the real source's own uniform `ofcpoints` loop, no
special case), plus this Kingdom's own `trvic=1` legendary-item count
(`turn/emperor_election.py _kingdom_treasure_vote_points()`, Phase 450's
own exact real 10-item set, reused directly -- "gli oggetti con trvic=1
... non subiscono la riduzione di allineamento", so this term stays
undiscounted unlike the office terms).

**`kingdom_sort_key()`**: the real composite integer key,
`int(kingdom_points*65536) + Tax_Base*256 + treasury` -- **not** a
lexicographic tuple comparison (a very high Tax_Base could otherwise
flip a naive `(points, tax_base, treasury)` ordering; the real key's own
fixed-width bit-shift-style weighting prevents that).

**`final_standings()`**: every Kingdom ID sorted descending by
`kingdom_sort_key()`, ties broken by original iteration order (the real
source's own "share the rank" behavior -- no further tie-break is named
anywhere in the dossier).
"""

from __future__ import annotations

from ak_engine.models.game_state import GameState
from ak_engine.turn.emperor_election import _kingdom_treasure_vote_points
from ak_engine.turn.office_holder import ALL_OFFICES
from ak_engine.turn.tax_base import compute_tax_base
from ak_engine.turn.victory_points import office_victory_points


def kingdom_points(state: GameState, kingdom_id: int) -> float:
    """`kingdom_id`'s own real end-of-game `kingpoints` -- see module docstring."""

    if state.emperor_kingdom_id is None:
        return 0.0

    office_points = sum(office_victory_points(state, office, kingdom_id) for office in ALL_OFFICES)
    return office_points + _kingdom_treasure_vote_points(state, kingdom_id)


def kingdom_sort_key(state: GameState, kingdom_id: int) -> int:
    """The real composite ranking key -- see module docstring for why this
    isn't a lexicographic tuple comparison.
    """

    points = kingdom_points(state, kingdom_id)
    tax_base = compute_tax_base(state, kingdom_id)
    treasury = state.kingdoms[kingdom_id].treasury
    return int(points * 65536) + tax_base * 256 + treasury


def final_standings(state: GameState) -> list[int]:
    """Every Kingdom ID, ranked descending by `kingdom_sort_key()` -- see
    module docstring for the tie-break convention.
    """

    return sorted(state.kingdoms, key=lambda kingdom_id: kingdom_sort_key(state, kingdom_id), reverse=True)
