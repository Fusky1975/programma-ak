"""The real alignment/team Imperial Office Victory Point decay formula --
`REPORTS.PAS Pray_Report` ~lines 1685-1693, Phase 439.

`models/office.py OFFICE_VALUE` (`ofcval`, Phase 81) already carries the
real per-office Victory Point quota, but its own docstring flagged the
formula that actually applies it, `ofcpoints[ofc]:= ofcval[ofc] * (1.0 -
reduct)`, as "a separate points-decay formula ... whose own `reduct` term
isn't traced further here." This module closes that.

**The real mechanic**: once an Emperor is elected (`emp <> No_King`), the
Kingdom that truly holds an office (the global Rank-1 winner, `turn/
office_holder.py resolve_office_holder()`) banks that office's own
`ofcval` Victory Points, discounted by how far its own King's Alignment
sits from the Emperor's own -- `reduct:= outred[kalign] * diff_steps`
(capped at `1.0`), where:

- `kalign`/`empalign` are each Kingdom's own `KingdomState.alignment`
  (the King's own real alignment), not a per-leader value -- the same
  established convention `turn/hire_pay.py`'s own docstring already
  uses ("A King's own real alignment/temper (`KingdomState.alignment`
  for alignment...)").
- `diff_steps:= abs(Min(ord(kalign),ord(Hellish)) - Min(ord(Hellish),
  ord(empalign)))` -- both Alignments clamped to `Hellish`'s own ordinal
  (`ALIGNMENT_ORDINAL[Alignment.ANTI_HOLY] == 6`) before differencing,
  via this project's own pre-existing `models/alignment.py
  ALIGNMENT_ORDINAL` (Phase 162's real Pascal `outlook` ordinal
  sequence, not this project's own enum declaration order).
- `outred` is real and now confirmed: `CTBOTH.PAS` ~line 1673,
  `outred: outreals = (0.20, 0.12, 0.15, 0.20, 0.15, 0.12, 0.20, 0.20,
  0.20, 0.20)`, indexed by that exact same real `outlook` ordinal
  sequence -- `OUTLOOK_REDUCTION` below reuses `ALIGNMENT_BY_ORDINAL`
  (not this project's own declaration order) to build the mapping
  correctly.

**No `kteam` (team) term.** The real formula also halves `diff_steps`
away entirely when the scoring Kingdom shares a "team" with the Emperor
(`IF kteam[bestlk] <> 0 THEN IF kteam[bestlk] MOD 100 = kteam[emp] MOD
100 THEN Dec(diff_steps)`). `kteam` was searched for across every `.PAS`
file in `Programma Pascal.zip` (all 14, re-extracted fresh this phase) --
it's read in several places (`REPORTS.PAS`, `RUMORS.PAS`) but never
declared or assigned anywhere in the surviving source, the same "missing
global" category Phase 137 already established for several other
`Ofc_Pts` inputs. This project has never modeled a multiplayer "team"
concept at all, so every Kingdom is implicitly `kteam = 0` -- the real
`IF kteam[...] <> 0` guard means the team discount simply never fires in
that case, which is the actual correct behavior for any non-team game,
not a guessed magnitude.

**Victory Points are global, not per-report-Kingdom.** The real
`ofcpoints`/`kingpoints` accumulation is keyed to the office's own true
winning Kingdom (`bestlk`) -- recomputed identically inside every King's
own `Pray_Report` call once an Emperor is elected (since the scan
becomes global for every caller at that point), not something each
Kingdom earns independently for its own candidate. `office_victory_
points()` below reflects this: it returns a nonzero award only when
`kingdom_id` is genuinely the office's own real holder (`resolve_office_
holder()`), `0.0` for every other Kingdom, and `0.0` outright before any
Emperor is elected (the entire `ofcpoints` block in the real source sits
inside `IF emp <> No_King`).
"""

from __future__ import annotations

from ak_engine.models.alignment import ALIGNMENT_BY_ORDINAL, ALIGNMENT_ORDINAL, Alignment
from ak_engine.models.game_state import GameState
from ak_engine.models.office import OFFICE_VALUE, Office
from ak_engine.turn.office_holder import resolve_office_holder

_HELLISH_ORDINAL = ALIGNMENT_ORDINAL[Alignment.ANTI_HOLY]

# CTBOTH.PAS `outred: outreals = (0.20, 0.12, 0.15, 0.20, 0.15, 0.12,
# 0.20, 0.20, 0.20, 0.20)`, keyed by the real `outlook` ordinal sequence
# (`ALIGNMENT_BY_ORDINAL`), not this project's own `Alignment` enum
# declaration order.
OUTLOOK_REDUCTION: dict[Alignment, float] = dict(
    zip(ALIGNMENT_BY_ORDINAL, (0.20, 0.12, 0.15, 0.20, 0.15, 0.12, 0.20, 0.20, 0.20, 0.20))
)


def _alignment_distance_capped_at_hellish(a: Alignment, b: Alignment) -> int:
    """Real `abs(Min(ord(a),ord(Hellish)) - Min(ord(Hellish),ord(b)))`."""

    return abs(min(ALIGNMENT_ORDINAL[a], _HELLISH_ORDINAL) - min(ALIGNMENT_ORDINAL[b], _HELLISH_ORDINAL))


def office_victory_points(state: GameState, office: Office, kingdom_id: int) -> float:
    """`kingdom_id`'s own real Victory Point award for `office` -- `0.0`
    before any Emperor is elected, or if `kingdom_id` doesn't genuinely
    hold `office` (`resolve_office_holder()`'s own real Rank-1 winner).
    See module docstring for the full derivation.
    """

    if state.emperor_kingdom_id is None:
        return 0.0

    holder = resolve_office_holder(state, office)
    if holder is None:
        return 0.0

    winner_kingdom_id = state.leaders[holder.leader_id].kingdom_id
    if winner_kingdom_id != kingdom_id:
        return 0.0

    kalign = state.kingdoms[kingdom_id].alignment
    empalign = state.kingdoms[state.emperor_kingdom_id].alignment
    reduct = min(1.0, OUTLOOK_REDUCTION[kalign] * _alignment_distance_capped_at_hellish(kalign, empalign))
    return OFFICE_VALUE[office] * (1.0 - reduct)
