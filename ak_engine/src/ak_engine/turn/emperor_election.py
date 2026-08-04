"""Emperor election mechanic -- rulebook [10.2] L'IMPERATORE, the
mechanism the rulebook itself frames as "cosa si deve fare per mettere
fine a una partita" ("what must be done to end a game"): reaching enough
combined tax revenue to call a vote, and winning that vote, IS how
Adventurer Kings actually concludes. Phase 228.

Full rulebook text (quoted verbatim, Italian, user-supplied and confirmed
correct over AKGEN.EXE's own conflicting 2%/4% threshold strings --
standing instruction: those are NOT the real rule, 55%/50% below are):

"Imperatore diventa il giocatore che, alla fine della partita, ha
accumulato il più alto numero di voti in base alla rendita di tasse.
[...] Alla fine di un turno qualsiasi, un singolo Re, o un'alleanza di
Re, che detengano più del 55% della rendita di tasse complessiva,
possono richiedere che venga eletto l'Imperatore. Nel turno successivo
tutti i Re hanno la facoltà di esprimere una preferenza [...] Ogni Re
dispone di un numero di voti pari alla rendita che ha accumulato alla
fine di quel turno. Se un Re ottiene più del 50% dei voti diventa
Imperatore. Se nessun giocatore supera il quorum, l'Imperatore non viene
eletto [...] Poiché la votazione avviene nel turno successivo a quello
in cui viene richiesta, non è possibile tenere votazioni per due turni
consecutivi."

**The "RICHIEDERE UNA VOTAZIONE" (Call for Vote) plan action [1.3]
itself** ("questa azione non occupa fasi di gioco") is not decoded
here -- like Treat/Break Treaty, this project has no parser/decoder for
it (no real `AK3__T*.K1` sample with this action has been seen). This
module models the underlying mechanic -- eligibility check, vote tally,
Alignment-based Victory Point reduction -- for a future decoder to call,
the same "mechanic before the plan-file wiring" order this project used
for `turn/tax_base.py` (built before its own FINANCES report wiring).

## Requesting a vote
`can_request_election()` -- a single King or an "alleanza di Re" (read
here as one connected component of `GameState.allied_kingdoms`, the same
mutual-alliance-network reading this project's other alliance-scoped
mechanics already use) qualifies once their *combined* `Tax_Base` (Phase
225's `compute_tax_base()`) exceeds 55% of every kingdom's `Tax_Base`
summed together. The "due turni consecutivi" ban is enforced via
`GameState.last_emperor_vote_turn`: a request is rejected if it would
schedule a vote on the turn immediately after the last one actually
held.

## The vote itself
`tally_emperor_vote()` -- `ballots` is a `{voter_kingdom_id:
candidate_kingdom_id}` mapping for every King who actually cast a
preference this turn. An abstaining King casts no ballot at all, so his
own revenue isn't "votes" for anyone -- the rulebook's own "più del 50%
dei voti" reads naturally as a share of votes actually *cast*, not of
every King's revenue whether cast or not. Each voter's ballot weight is
that voter's own `compute_tax_base()` "alla fine di quel turno" (the
voting turn, not the request turn -- the caller passes a `state` already
advanced to that turn). A candidate needs a strict majority (>50%) of
the total weight cast to win; a below-quorum spread across candidates
(or zero ballots) elects nobody, the same "se nessun giocatore supera il
quorum" no-Emperor outcome the rulebook describes. `resolve_emperor_
election()` tallies and records the outcome onto `GameState` in one
step.

## Alignment-based Victory Point reduction
The rulebook's own paragraph immediately after the vote result: every
King's own final Victory Point total is reduced by a percentage
proportional to their Alignment's own distance from the newly-elected
Emperor's Alignment -- "un Re Pagano perde il 45% dei suoi Punti
Vittoria se viene eletto Imperatore un Re Buono (15% x 3)".
`ALIGNMENT_VP_REDUCTION_PER_STEP` below is the user-supplied "TABELLA
ALLINEAMENTI" reduction-per-step column (7 of the 10 `Alignment`
members; Anti-Holy/Mechanical/Special are a confirmed gap, not a guess
-- the table simply doesn't cover them, presumably because they aren't
selectable Alignments for a King). `alignment_victory_point_reduction_
percent()` reuses `models/alignment.py ALIGNMENT_ORDINAL` for
"distance" -- the same real Pascal ordinal sequence (not this project's
own declaration order) `turn/hire_pay.py _alignment_distance()` already
established as load-bearing for an identical "N ordinal positions
apart" formula. The worked example above reproduces exactly: Good=1,
Pagan=4, distance 3, Pagan's own 15%-per-step row -> 15 x 3 = 45%.

## Explicitly out of scope
Determining the game's total available Victory Points and attributing
the other 7 Imperial Offices' own shares (needs the full Merit Point
Rank contest -- who actually *wins* each office, resolved across every
leader in the game via `turn/merit_points.py`'s own formulas and
`merit_point_tiebreak_key()`) is a separate, considerably larger
follow-up, not attempted here. This module only settles *who becomes
Emperor* and *how much each King's own Alignment costs them* -- two
self-contained rulebook mechanics that don't need that larger ranking
system.
"""

from __future__ import annotations

from dataclasses import dataclass

from ak_engine.models.alignment import ALIGNMENT_ORDINAL, Alignment
from ak_engine.models.game_state import GameState
from ak_engine.turn.tax_base import compute_tax_base

ELECTION_REQUEST_THRESHOLD_PERCENT = 55
ELECTION_WIN_THRESHOLD_PERCENT = 50

# User-supplied "TABELLA ALLINEAMENTI" reduction-per-step column -- see
# module docstring. Anti-Holy/Mechanical/Special are a confirmed gap.
ALIGNMENT_VP_REDUCTION_PER_STEP: dict[Alignment, int] = {
    Alignment.DIVINE: 20,
    Alignment.GOOD: 12,
    Alignment.DRUID: 15,
    Alignment.NEUTRAL: 20,
    Alignment.PAGAN: 15,
    Alignment.EVIL: 12,
    Alignment.UNDEAD: 20,
}


def _world_tax_base(state: GameState) -> int:
    return sum(compute_tax_base(state, kingdom_id) for kingdom_id in state.kingdoms)


def _alliance_component(state: GameState, kingdom_id: int) -> set[int]:
    """Every kingdom transitively reachable from ``kingdom_id`` via
    ``GameState.allied_kingdoms`` -- one connected component of the
    alliance graph, this module's own reading of "un'alleanza di Re"
    (see module docstring).
    """

    component = {kingdom_id}
    frontier = [kingdom_id]
    while frontier:
        current = frontier.pop()
        for pair in state.allied_kingdoms:
            if current in pair:
                other = next(iter(pair - {current}))
                if other not in component:
                    component.add(other)
                    frontier.append(other)
    return component


def election_threshold_percent(current_turn: int) -> int:
    """The real, turn-dependent version of `ELECTION_REQUEST_THRESHOLD_
    PERCENT` -- Phase 377, `AKGEN_embedded_catalogs.json.txt gw_format.
    imperial_office_system.emperor_election.time_limit` (a real static
    disassembly of `AKGEN.EXE`/`AK.EXE`/`AK.OVR`; the same JSON's own
    `call_threshold_standard_percent: 55` matches the user-confirmed
    rulebook figure this module's docstring already uses -- unlike the
    disassembly's own separately-flagged, rejected "2%/4%" strings, this
    turn-based erosion note comes from a field that already agrees with
    the trusted source before turn 25, lending it real credibility.

    "From turn 25 the call/become threshold falls by 5 percentage points
    per turn to 25% on turn 30": read as the erosion applying starting
    at turn 25 itself (`55 -> 50` at turn 25, ..., `55 -> 25` at turn 30,
    a clean 5-point-per-turn descent that lands exactly on the source's
    own "25% on turn 30" anchor), floored at 25% for every turn after.

    Deliberately scoped to only `ELECTION_REQUEST_THRESHOLD_PERCENT`
    (the 55% call threshold) -- the source's own "call/become" wording
    doesn't unambiguously say whether `ELECTION_WIN_THRESHOLD_PERCENT`
    (the 50% vote-winning threshold) eroded the same way, so that one is
    deliberately left untouched rather than guessed.
    """

    if current_turn < 25:
        return ELECTION_REQUEST_THRESHOLD_PERCENT
    erosion = 5 * (current_turn - 24)
    return max(25, ELECTION_REQUEST_THRESHOLD_PERCENT - erosion)


def can_request_election(state: GameState, requesting_kingdom_id: int, current_turn: int) -> bool:
    """Whether ``requesting_kingdom_id`` (together with its own allied
    "alleanza") can call for an Emperor vote this turn -- see module
    docstring for the 55% threshold and the "not two turns in a row" ban,
    and `election_threshold_percent()`'s own docstring (Phase 377) for
    why that 55% erodes turn-by-turn from turn 25 onward instead of
    staying flat for the whole game. ``current_turn`` is the turn the
    request is made in; the resulting vote would be held on
    ``current_turn + 1``.
    """

    world_total = _world_tax_base(state)
    if world_total <= 0:
        return False

    coalition = _alliance_component(state, requesting_kingdom_id)
    coalition_total = sum(compute_tax_base(state, kingdom_id) for kingdom_id in coalition)
    threshold_percent = election_threshold_percent(current_turn)
    if coalition_total * 100 <= threshold_percent * world_total:
        return False

    vote_turn = current_turn + 1
    if state.last_emperor_vote_turn is not None and vote_turn == state.last_emperor_vote_turn + 1:
        return False

    return True


@dataclass(slots=True)
class ElectionResult:
    elected_emperor_kingdom_id: int | None
    votes_by_candidate: dict[int, int]
    total_votes_cast: int


def tally_emperor_vote(state: GameState, ballots: dict[int, int]) -> ElectionResult:
    """``ballots``: ``{voter_kingdom_id: candidate_kingdom_id}`` for every
    King who cast a preference this turn -- see module docstring for
    exactly what "votes" means here and why an abstention isn't counted
    as a vote for nobody.
    """

    votes_by_candidate: dict[int, int] = {}
    for voter_kingdom_id, candidate_kingdom_id in ballots.items():
        weight = compute_tax_base(state, voter_kingdom_id)
        votes_by_candidate[candidate_kingdom_id] = votes_by_candidate.get(candidate_kingdom_id, 0) + weight

    total_votes_cast = sum(votes_by_candidate.values())
    winner: int | None = None
    if total_votes_cast > 0:
        for candidate_kingdom_id, votes in votes_by_candidate.items():
            if votes * 100 > ELECTION_WIN_THRESHOLD_PERCENT * total_votes_cast:
                winner = candidate_kingdom_id
                break

    return ElectionResult(winner, votes_by_candidate, total_votes_cast)


def resolve_emperor_election(state: GameState, ballots: dict[int, int], vote_turn: int) -> ElectionResult:
    """Tallies the vote (``tally_emperor_vote``) and records its outcome
    onto ``state``: ``last_emperor_vote_turn`` is always set to
    ``vote_turn`` (a vote was held, win or not -- this is what the "not
    two turns in a row" ban tracks), and ``emperor_kingdom_id`` is
    updated only on an actual win -- "se nessun giocatore supera il
    quorum, l'Imperatore non viene eletto" means an unresolved vote must
    not silently clear or overwrite a still-standing previous Emperor.
    """

    result = tally_emperor_vote(state, ballots)
    state.last_emperor_vote_turn = vote_turn
    if result.elected_emperor_kingdom_id is not None:
        state.emperor_kingdom_id = result.elected_emperor_kingdom_id
    return result


def alignment_victory_point_reduction_percent(king_alignment: Alignment, emperor_alignment: Alignment) -> int | None:
    """The percentage of ``king_alignment``'s own Victory Points lost
    because ``emperor_alignment`` now holds the Imperial throne --
    per-step percent (``king_alignment``'s own row) times ordinal
    distance from ``emperor_alignment``. Returns ``None``, not a guessed
    0, if ``king_alignment`` isn't one of the 7 the rulebook's own table
    covers (Anti-Holy/Mechanical/Special) -- a genuinely unknown
    reduction, distinct from a real "no reduction" (distance-0, same
    Alignment as the Emperor).
    """

    per_step = ALIGNMENT_VP_REDUCTION_PER_STEP.get(king_alignment)
    if per_step is None:
        return None
    distance = abs(ALIGNMENT_ORDINAL[king_alignment] - ALIGNMENT_ORDINAL[emperor_alignment])
    return per_step * distance
