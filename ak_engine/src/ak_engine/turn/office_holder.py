"""Imperial Office holder resolution -- rulebook [10.1]'s own Rank
contest, Phase 230. Given a `GameState` with every leader's real
skills/treasury/Tax_Base/owned-items data (fully live per `turn/
merit_points.py`, Phase 227) plus whatever `MeritTally` counters a
caller has populated, this resolves *who currently holds* each of the 8
Imperial Offices -- closing the "needs the full Merit Point Rank contest
across every leader in the game" gap Phase 227/228's own docstrings both
flagged as a separate, considerably larger follow-up.

**Emperor is resolved differently from the other 7 offices.** The
rulebook's own table lists Emperor's Merit Points as the Kingdom's own
Tax_Base ("Ammontare della rendita di tasse alla fine del gioco"), but
the actual *winner* of the Emperor office isn't a Merit-Point-Rank
comparison at all -- it's decided by the real Call-for-Vote election
mechanic (rulebook [10.2], `turn/emperor_election.py`, Phase 228),
already resolved into `GameState.emperor_kingdom_id`. `resolve_office_
holder(state, Office.EMPEROR)` reads that field directly (resolving to
the elected Kingdom's own King, via `LeaderState.is_king`) rather than
re-deriving anything from `emperor_merit_points()`.

**The other 7 offices are a genuine Rank contest across every leader in
the game** -- "Anche un Eroe può aggiudicarsi una carica e uno stesso
personaggio può aggiudicarsene più di una" (rulebook [10.1]): a Hero can
win an office too, and the same character can hold more than one. Each
office iterates `state.leaders` (Kings and Heroes alike), computes that
leader's own Merit Points via the matching `turn/merit_points.py`
formula, and picks the strictly highest scorer who meets `models/
office.py OFFICE_MIN_POINTS[office]` (real, sourced Pascal `minpts`
threshold, Phase 81) -- a leader below threshold is not a genuine
office-holder yet, even if they're the highest scorer among a field of
zeros. Ties are broken via `turn/merit_points.py
merit_point_tiebreak_key()` (rulebook footnote 3: treasury, then
Tax_Base -- both of the tied leader's own serving Kingdom).

**Treasurer needs a per-leader wrapper.** `treasurer_merit_points()`
takes a `kingdom_id` (a King's own treasury is his Kingdom's), so a
leader with no Kingdom (`kingdom_id is None`, an independent Hero) is
never eligible for Treasurer -- there's no treasury to measure, not a
guessed 0.

**Still not attempted here, the same documented gap `turn/merit_points.py`
already names**: Chancellor's three discovery-attribution Merit Point
terms (`features_discovered_first`/`discoveries_found_first`/
`discoveries_via_espionage`) always read 0 from a fresh `MeritTally`
until some future phase wires real "who found this first" tracking --
this module resolves Chancellor using whatever `MeritTally` state a
caller has already populated (possibly all zeros), the same as every
other office. Likewise Marshal/Admiral/Defender/Priest's own tally
counters resolve from whatever a caller has populated; no battle/
encounter/cast call site increments them automatically yet.
"""

from __future__ import annotations

from dataclasses import dataclass

from ak_engine.models.game_state import GameState, LeaderState
from ak_engine.models.office import OFFICE_MIN_POINTS, Office
from ak_engine.turn.merit_points import (
    admiral_merit_points,
    chancellor_merit_points,
    defender_merit_points,
    emperor_merit_points,
    mage_merit_points,
    marshal_merit_points,
    merit_point_tiebreak_key,
    priest_merit_points,
    treasurer_merit_points,
)

# Every office except Emperor (resolved separately, see module docstring)
# is a genuine Merit Point Rank contest across every leader in the game.
RANKED_OFFICES: tuple[Office, ...] = (
    Office.CHANCELLOR,
    Office.TREASURER,
    Office.MARSHAL,
    Office.ADMIRAL,
    Office.DEFENDER,
    Office.PRIEST,
    Office.MAGE,
)

# All 8 real Imperial Offices this project models, in the rulebook's own
# table order.
ALL_OFFICES: tuple[Office, ...] = (Office.EMPEROR, *RANKED_OFFICES)


@dataclass(slots=True)
class OfficeHolder:
    leader_id: int
    merit_points: int


def _leader_merit_points(office: Office, state: GameState, leader: LeaderState) -> int:
    if office is Office.CHANCELLOR:
        return chancellor_merit_points(state, leader)
    if office is Office.TREASURER:
        return treasurer_merit_points(state, leader.kingdom_id) if leader.kingdom_id is not None else 0
    if office is Office.MARSHAL:
        return marshal_merit_points(leader)
    if office is Office.ADMIRAL:
        return admiral_merit_points(state, leader)
    if office is Office.DEFENDER:
        return defender_merit_points(leader)
    if office is Office.PRIEST:
        return priest_merit_points(state, leader)
    if office is Office.MAGE:
        return mage_merit_points(state, leader)
    raise ValueError(f"{office} is not a ranked office -- Emperor is resolved via resolve_office_holder() directly")


def _king_leader_id(state: GameState, kingdom_id: int) -> int | None:
    for leader in state.leaders.values():
        if leader.kingdom_id == kingdom_id and leader.is_king:
            return leader.leader_id
    return None


def resolve_office_holder(state: GameState, office: Office) -> OfficeHolder | None:
    """The leader who currently holds `office`, and their own Merit
    Points -- or `None` if nobody qualifies yet. See module docstring
    for Emperor's own special-cased resolution and the Rank-contest
    rules governing the other 7.
    """

    if office is Office.EMPEROR:
        if state.emperor_kingdom_id is None:
            return None
        leader_id = _king_leader_id(state, state.emperor_kingdom_id)
        if leader_id is None:
            return None
        return OfficeHolder(leader_id, emperor_merit_points(state, state.emperor_kingdom_id))

    if office not in RANKED_OFFICES:
        raise ValueError(f"{office} is not one of the 8 real Imperial Offices this project models")

    min_points = OFFICE_MIN_POINTS[office]
    best: OfficeHolder | None = None
    best_tiebreak: tuple[int, int] | None = None

    for leader_id, leader in state.leaders.items():
        points = _leader_merit_points(office, state, leader)
        if points < min_points:
            continue
        tiebreak = merit_point_tiebreak_key(state, leader)
        if best is None or points > best.merit_points or (points == best.merit_points and tiebreak > best_tiebreak):
            best = OfficeHolder(leader_id, points)
            best_tiebreak = tiebreak

    return best


def resolve_all_office_holders(state: GameState) -> dict[Office, OfficeHolder | None]:
    """All 8 real Imperial Offices at once, each resolved via
    `resolve_office_holder()`.
    """

    return {office: resolve_office_holder(state, office) for office in ALL_OFFICES}
