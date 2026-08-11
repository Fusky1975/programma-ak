"""End-of-game standings -- `kingpoints`, the real composite sort key, and
Kingdom ranking. AKGEN_reverse_engineering_report (2).md SS14.6, Phase
454. Phase 455 extends this module with the all-star/Valhalla-induction
threshold checks SS14.7 also covers.

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

**Phase 455 -- `qualifies_for_all_star()`/`qualifies_for_valhalla_
induction()`/`individual_king_points()`** (SS14.7). All-star qualification
is `kingpoints >= 15` under old rules or `kingpoints >= 7.5` under new
rules (the new-rules test literally doubles the points before comparing
against the old 15 threshold, per the dossier's own words -- the two are
mathematically the same cut, expressed as `>= 7.5` here). This project
has no old/new-rules toggle -- every other unconditional-formula phase
this session (Phase 439's own alignment decay, Phase 450's vote weight)
adopted the new-rules formula outright, and this phase does the same:
only `>= 7.5` is wired; the old-rules `>= 15` value is recorded here as
the sourced alternative for a hypothetical old-rules mode, not
implemented.

Valhalla induction is `individual_king_points >= 20` **or** the Kingdom
placed first in `final_standings()`. `individual_king_points()` is the
dossier's own stricter `k_indivpoints`, not a reuse of `kingdom_points()`:
"per i normali titoli conta la carica soltanto quando il vincitore e il
Re stesso" (a title counts only when its true winner is the Kingdom's own
King, not any Hero who might hold it instead) and "per gli oggetti,
soltanto quando e posseduto direttamente dal Re" (a `trvic` item counts
only when the King himself directly owns it, not any Hero of that
Kingdom). Both terms otherwise reuse the same real point values
`kingdom_points()` does -- `office_victory_points()` for a title genuinely
won by the King, `turn/merit_points.py
legendary_item_victory_point_bonus_count()` for the King's own item
holdings -- narrowed to "won/held by this specific leader," not merely
"won/held by someone in this Kingdom." A Kingdom with no registered King
(`LeaderState.is_king`) scores `0.0` -- there is no King to hold anything.

**Deliberately not replicated**: the dossier's own confirmed second
compiled bug in `k_indivpoints` -- after a military-office win the real
code checks only `bestldr < nkings`, but `bestldr` is an **army index**
in that branch, so an army whose numeric ID happens to be below the
Kingdom count can be miscredited as the King's own individual point by
mistake. Reproducing this would require modeling which offices are
army-scoped in a way `individual_king_points()` has no other reason to
know (this project's own `turn/office_holder.py ArmyOfficeHolder` path,
Phase 394, is a genuinely separate, `leader_id`-less resolution track
that never touches `resolve_office_holder()`'s own leader-scoped offices
at all) -- a deliberate, documented bug-compatibility decline, the same
posture Phase 454's own module docstring already took for the team-
ranking `kingpoints[team2]` bug.
"""

from __future__ import annotations

from ak_engine.models.game_state import GameState
from ak_engine.turn.emperor_election import _kingdom_treasure_vote_points
from ak_engine.turn.merit_points import legendary_item_victory_point_bonus_count
from ak_engine.turn.office_holder import ALL_OFFICES, resolve_office_holder
from ak_engine.turn.tax_base import compute_tax_base
from ak_engine.turn.victory_points import office_victory_points


def kingdom_points(state: GameState, kingdom_id: int) -> float:
    """`kingdom_id`'s own real end-of-game `kingpoints` -- see module docstring."""

    if state.emperor_kingdom_id is None:
        return 0.0

    office_points = sum(office_victory_points(state, office, kingdom_id) for office in ALL_OFFICES)
    return office_points + _kingdom_treasure_vote_points(state, kingdom_id)


def _find_king(state: GameState, kingdom_id: int) -> int | None:
    """`kingdom_id`'s own acting King's `leader_id`, or `None` if it has
    none currently registered -- the same `is_king` lookup pattern already
    used by `turn/expenses.py`/`turn/plan_dispatch.py`/`turn/valhalla_
    execution.py`.
    """

    king = next(
        (leader for leader in state.leaders.values() if leader.kingdom_id == kingdom_id and leader.is_king),
        None,
    )
    return king.leader_id if king is not None else None


def individual_king_points(state: GameState, kingdom_id: int) -> float:
    """`kingdom_id`'s own real `k_indivpoints` -- see module docstring for
    how this narrows `kingdom_points()` to the King's own personal wins
    and holdings.
    """

    if state.emperor_kingdom_id is None:
        return 0.0

    king_leader_id = _find_king(state, kingdom_id)
    if king_leader_id is None:
        return 0.0

    office_points = 0.0
    for office in ALL_OFFICES:
        holder = resolve_office_holder(state, office)
        if holder is not None and holder.leader_id == king_leader_id:
            office_points += office_victory_points(state, office, kingdom_id)

    return office_points + legendary_item_victory_point_bonus_count(state, king_leader_id)


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


def qualifies_for_all_star(state: GameState, kingdom_id: int) -> bool:
    """The real new-rules all-star qualification -- `kingpoints >= 7.5` --
    see module docstring for why the old-rules `>= 15` cut isn't wired.
    """

    return kingdom_points(state, kingdom_id) >= 7.5


def qualifies_for_valhalla_induction(state: GameState, kingdom_id: int) -> bool:
    """The real Valhalla induction test -- `individual_king_points >= 20`
    or first place in `final_standings()` -- see module docstring for
    `individual_king_points()`'s own narrower, King-only scope.
    """

    return individual_king_points(state, kingdom_id) >= 20 or final_standings(state)[0] == kingdom_id
