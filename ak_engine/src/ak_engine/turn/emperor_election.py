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

**Phase 465 (real per-turn call/coronation evaluation, sourced)**:
`evaluate_election_call()` (bottom of this module) is the real,
disassembly-sourced routine that decides -- **every turn**, automatically,
regardless of whether any King explicitly asked -- whether an election
gets scheduled or an Emperor gets crowned outright, per
`AKGEN_reverse_engineering_report (2).md` SS13.4/13.6. It supersedes
`can_request_election()` in spirit (that function's own rulebook-literal
"un singolo Re... alleanza" reading, Phase 228, turns out to be an
approximation of a routine with no alliance concept at all, plus an
immediate-coronation short-circuit and a pure Alignment-bloc trigger the
rulebook never mentions) -- see that new function's own docstring for the
full account. `can_request_election()` itself is kept, unchanged.

**Phase 464**: a genuinely *different* Vote mechanic -- `AKE.EXE`'s own
`V` command (report SS12, not the plan-action [1.3] above) -- is now
correctly decodable at the Kingdom-header level:
`models/kingdom.py KingdomMoveHeader.kprevgold`/`is_vote_turn()`.
**Stale as of Phase 687 -- this used to say "still not wired... this
project doesn't track [a world-level `req_vote` state] anywhere."**
`GameState.election_pending_turn` is exactly that state (SS12.1's own
`req_vote` global, see `process_election_turn()`'s own docstring
below), and `process_election_turn()` (Phase 466) fully assembles a
real per-turn `ballots` from it, called live every turn from
`orchestrator.py process_turn()` (`election_outcome = process_
election_turn(state, kingdom_headers, state.turn_number)`).

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
that voter's own `kingdom_election_vote_weight()` "alla fine di quel
turno" (the voting turn, not the request turn -- the caller passes a
`state` already advanced to that turn). `resolve_emperor_election()`
tallies and records the outcome onto `GameState` in one step.

**Phase 451 (real win condition, sourced)**: the win check itself is
rewritten off `AKGEN_reverse_engineering_report (2).md` SS13.3/SS13.5,
superseding this module's original design (Phase 228) of comparing a
candidate's share against the sum of *expressed* ballots only. The real
denominator is `V_world` -- every Kingdom's own `kingdom_election_vote_
weight()` summed, **including non-voters/abstainers** -- not the sum of
ballots actually cast. A candidate wins immediately once their running
share of `V_world` exceeds 50% (checked ballot-by-ballot, in ascending
voter-Kingdom-ID order, so the win can be detected as early as possible,
matching the real engine's own short-circuit). If nobody clears 50%
outright, the candidate with the single highest share that still clears
the **time-decaying** threshold `R` (`election_threshold_percent()`,
already correct and already used for the *request*-to-call-a-vote gate
-- directly reused here, no new formula needed) wins instead; ties in
that second pass are broken by whichever candidate's own share was the
first, scanning voters in ascending Kingdom-ID order, to reach the
eventual best value -- replicated here by only replacing `best_share`
on a strict `>` comparison, never on a tie, so the earliest-scanned
candidate to reach a given share keeps priority. A world with zero total
vote weight, or where nobody reaches even the decayed `R`, elects nobody
-- the same "se nessun giocatore supera il quorum" outcome. `ElectionResult.
total_votes_cast` now holds `V_world` (docstring updated, field name kept
to avoid a wider ripple).

**Phase 450 (real vote weight, sourced)**: `kingdom_election_vote_
weight()` supersedes this module's original bare-`compute_tax_base()`
ballot weight (Phase 228, the rulebook's own literal "un numero di voti
pari alla rendita" reading) now that `AKGEN_reverse_engineering_report
(2).md` SS13.2 gives the real, disassembly-confirmed formula: `V_k =
Tax_Base(k) + 5*office_points(k) + 5*treasure_points(k)`, for
`gamevers >= 4` ("new rules" -- this project has no old/new-rules
toggle, so this is simply *the* formula unconditionally, the same
precedent Phase 439's own alignment-decay formula set). `office_points`
sums the raw, undiscounted `models/office.py OFFICE_VALUE[office]` for
every real Imperial Office whose current winning holder (`turn/office_
holder.py resolve_all_office_holders()`) belongs to that Kingdom -- the
*raw* value, not `turn/victory_points.py office_victory_points()`'s own
alignment-discounted figure, since no Emperor exists yet during the vote
that elects one. `treasure_points` counts `turn/merit_points.py
LEGENDARY_ITEM_BONUS_TREASURES` (the real 10-item `trvic=1` set) owned
by any of that Kingdom's own leaders, reusing the exact set Phase 271's
own Discovery Merit Points formula already established.

## Alignment-based Victory Point reduction
The rulebook's own paragraph immediately after the vote result: every
King's own final Victory Point total is reduced by a percentage
proportional to their Alignment's own distance from the newly-elected
Emperor's Alignment -- "un Re Pagano perde il 45% dei suoi Punti
Vittoria se viene eletto Imperatore un Re Buono (15% x 3)".

**Phase 558**: `alignment_victory_point_reduction_percent()` now reuses
`turn/victory_points.py OUTLOOK_REDUCTION`/`_alignment_distance_capped_
at_hellish()` directly, instead of maintaining its own separate,
partial table and a plain uncapped ordinal distance. The user's own
`VITTORIA E FINE PARTITA.txt` explicitly says the office-level
reduction "viene poi modificato dalla differenza di Allineamento...
come viene spiegato nel paragrafo successivo" -- i.e. the SAME formula
this section describes for a King's overall total -- and `report/
turn_report.py describe_alignment_victory_point_reduction()`'s own
comment independently cites the identical real source
(`HostAK/TP/REPORTS.PAS` ~lines 1665-1690/1784, `outred[kalign] *
diff_steps`) that `victory_points.py`'s own Phase 439 docstring already
traced in full. The two modules had drifted apart before this phase:
this one's own `ALIGNMENT_VP_REDUCTION_PER_STEP` (now removed) only
covered 7 of the 10 `Alignment` members (the user-supplied "TABELLA
ALLINEAMENTI" reduction-per-step column, which doesn't mention
Anti-Holy at all) with a plain, uncapped ordinal distance, while
`victory_points.py`'s formula -- sourced from the actual disassembly,
`CTBOTH.PAS ~line 1673`'s real 10-entry `outred` array plus `diff_
steps:= abs(Min(ord(kalign),ord(Hellish)) - Min(ord(Hellish),
ord(empalign)))` -- covers all 10 and caps each Alignment's own ordinal
at Hellish's (`Alignment.ANTI_HOLY`'s) own position before
differencing. Both formulas reproduce every worked example in
`VITTORIA E FINE PARTITA.txt` identically (Good=1, Pagan=4, distance 3,
15 x 3 = 45%; Neutral=3, Good=1, distance 2, 12 x 2 = 24%; Divine=0,
Undead capped-to-Hellish=6, distance 6, 20 x 6 = 120% -> capped at
100%) -- none of those examples happen to exercise a pair where the
capping actually changes the result, which is exactly how this drift
went unnoticed until this audit. `alignment_victory_point_reduction_
percent()` no longer returns `None` for any `Alignment` -- the real
`outred` table has a genuine value for all 10, including Mechanical/
Special (confirmed real, not modeled as "never reachable" the way
`_ORDINARY_ALIGNMENTS` below still treats them for the separate
alignment-bloc-vote mechanic; a King simply never has one of those two
Alignments in this project's own data, so the value is inert in
practice, not wrong to have).

## Explicitly out of scope
Determining the game's total available Victory Points and attributing
the other 7 Imperial Offices' own shares (needs the full Merit Point
Rank contest -- who actually *wins* each office, resolved across every
leader in the game via `turn/merit_points.py`'s own formulas and
`merit_point_tiebreak_key()`) was the still-open gap this module left
when this docstring was first written (Phase 228). **Since closed,
just not by this module**: `turn/victory_points.py office_victory_
points()` (Phase 439) and `turn/final_standings.py kingdom_points()`/
`final_standings()` (Phase 454-476) now fully cover exactly this --
per-office Rank resolution via `turn/office_holder.py
resolve_all_office_holders()`, real Victory Point attribution, and a
composite Kingdom ranking. This module still only settles *who becomes
Emperor* and *how much each King's own Alignment costs them* directly,
but the larger ranking system this paragraph once called "a separate,
considerably larger follow-up" is no longer missing from the project
overall -- see those two modules' own docstrings for the full account.
"""

from __future__ import annotations

from dataclasses import dataclass

from ak_engine.models.alignment import ALIGNMENT_BY_ORDINAL, Alignment
from ak_engine.models.game_state import GameState
from ak_engine.models.kingdom import KingdomMoveHeader
from ak_engine.models.office import OFFICE_VALUE
from ak_engine.turn.merit_points import LEGENDARY_ITEM_BONUS_TREASURES
from ak_engine.turn.office_holder import resolve_all_office_holders
from ak_engine.turn.tax_base import compute_tax_base
from ak_engine.turn.victory_points import OUTLOOK_REDUCTION, _alignment_distance_capped_at_hellish

ELECTION_REQUEST_THRESHOLD_PERCENT = 55
ELECTION_WIN_THRESHOLD_PERCENT = 50


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


def _kingdom_office_vote_points(state: GameState, kingdom_id: int) -> int:
    """Sum of `OFFICE_VALUE[office]` for every real Imperial Office whose current
    winning holder belongs to `kingdom_id` -- Phase 450's own office-points
    term of `kingdom_election_vote_weight()`. Uses the raw, undiscounted
    `OFFICE_VALUE` table (not `turn/victory_points.py office_victory_
    points()`'s own alignment-discounted figure) since no Emperor exists
    yet during the very vote that elects one -- no alignment-distance term
    can apply at this point. See module docstring's Phase 450 note.
    """

    total = 0
    for office, holder in resolve_all_office_holders(state).items():
        if holder is None:
            continue
        leader = state.leaders.get(holder.leader_id)
        if leader is None or leader.kingdom_id != kingdom_id:
            continue
        total += OFFICE_VALUE[office]
    return total


def _kingdom_treasure_vote_points(state: GameState, kingdom_id: int) -> int:
    """Count of `LEGENDARY_ITEM_BONUS_TREASURES` (the real 10-item `trvic=1`
    set, rulebook page 51) owned by any of `kingdom_id`'s own leaders --
    Phase 450's own treasure-points term of `kingdom_election_vote_
    weight()`.
    """

    total = 0
    for item in state.items.values():
        if item.treasure not in LEGENDARY_ITEM_BONUS_TREASURES:
            continue
        if item.owner_leader_id is None:
            continue
        leader = state.leaders.get(item.owner_leader_id)
        if leader is None or leader.kingdom_id != kingdom_id:
            continue
        total += 1
    return total


def kingdom_election_vote_weight(state: GameState, kingdom_id: int) -> int:
    """`V_k = Tax_Base(k) + 5*office_points(k) + 5*treasure_points(k)` -- the
    real Emperor-election vote weight (AKGEN_reverse_engineering_report
    (2).md SS13.2, `gamevers >= 4` "new rules"; this project has no
    old/new-rules toggle, so this is simply *the* formula, unconditionally,
    matching how Phase 439's own alignment-decay formula was adopted).
    Supersedes this module's original bare-`compute_tax_base()` weight
    (Phase 228) now that a real source is available -- see module
    docstring's Phase 450 note.
    """

    return (
        compute_tax_base(state, kingdom_id)
        + 5 * _kingdom_office_vote_points(state, kingdom_id)
        + 5 * _kingdom_treasure_vote_points(state, kingdom_id)
    )


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
    # Phase 451: holds V_world (every Kingdom's own vote weight summed,
    # including abstainers) -- the real win-condition denominator, not
    # the sum of expressed ballots this field's own name might suggest.
    # Field name kept (not renamed) to avoid a wider ripple; see this
    # module's own Phase 451 docstring note.
    total_votes_cast: int
    # Phase 656: the exact {voter_kingdom_id: candidate_kingdom_id} map
    # this result was tallied from -- REPORTS.PAS's own ELECTION REPORT
    # table (Rep_Prov/Pray_Report, real per-King "Voted for King"
    # column) needs this, and it used to be discarded after tallying.
    # Empty for the world_total<=0 early return (no real ballots to
    # show for a vote that couldn't even be evaluated).
    ballots: dict[int, int]


def tally_emperor_vote(state: GameState, ballots: dict[int, int], current_turn: int) -> ElectionResult:
    """``ballots``: ``{voter_kingdom_id: candidate_kingdom_id}`` for every
    King who cast a preference this turn -- see module docstring for
    exactly what "votes" means here and why an abstention isn't counted
    as a vote for nobody. ``current_turn``: the turn the vote is being
    held on (used for the decaying threshold `R`, see module docstring's
    Phase 451 note).
    """

    world_total = sum(kingdom_election_vote_weight(state, kingdom_id) for kingdom_id in state.kingdoms)
    if world_total <= 0:
        return ElectionResult(None, {}, world_total, {})

    votes_by_candidate: dict[int, int] = {}
    for voter_kingdom_id in sorted(state.kingdoms):
        candidate_kingdom_id = ballots.get(voter_kingdom_id)
        if candidate_kingdom_id is None:
            continue
        weight = kingdom_election_vote_weight(state, voter_kingdom_id)
        votes_by_candidate[candidate_kingdom_id] = votes_by_candidate.get(candidate_kingdom_id, 0) + weight
        if votes_by_candidate[candidate_kingdom_id] * 100 > ELECTION_WIN_THRESHOLD_PERCENT * world_total:
            return ElectionResult(candidate_kingdom_id, votes_by_candidate, world_total, ballots)

    threshold_percent = election_threshold_percent(current_turn)
    best_candidate: int | None = None
    best_share = -1.0
    for voter_kingdom_id in sorted(state.kingdoms):
        candidate_kingdom_id = ballots.get(voter_kingdom_id)
        if candidate_kingdom_id is None:
            continue
        share = votes_by_candidate[candidate_kingdom_id] / world_total
        if share * 100 >= threshold_percent and share > best_share:
            best_candidate = candidate_kingdom_id
            best_share = share

    return ElectionResult(best_candidate, votes_by_candidate, world_total, ballots)


def resolve_emperor_election(state: GameState, ballots: dict[int, int], vote_turn: int) -> ElectionResult:
    """Tallies the vote (``tally_emperor_vote``) and records its outcome
    onto ``state``: ``last_emperor_vote_turn`` is always set to
    ``vote_turn`` (a vote was held, win or not -- this is what the "not
    two turns in a row" ban tracks), and ``emperor_kingdom_id`` is
    updated only on an actual win -- "se nessun giocatore supera il
    quorum, l'Imperatore non viene eletto" means an unresolved vote must
    not silently clear or overwrite a still-standing previous Emperor.
    """

    result = tally_emperor_vote(state, ballots, vote_turn)
    state.last_emperor_vote_turn = vote_turn
    if result.elected_emperor_kingdom_id is not None:
        state.emperor_kingdom_id = result.elected_emperor_kingdom_id
    return result


def alignment_victory_point_reduction_percent(king_alignment: Alignment, emperor_alignment: Alignment) -> int:
    """The percentage of ``king_alignment``'s own Victory Points lost
    because ``emperor_alignment`` now holds the Imperial throne --
    **Phase 558**: reuses `turn/victory_points.py OUTLOOK_REDUCTION`/
    `_alignment_distance_capped_at_hellish()` directly (the same real,
    disassembly-sourced formula `office_victory_points()` already
    applies to office-level Victory Points) instead of this module's own
    former partial table and uncapped distance -- see module docstring's
    own Phase 558 note for the full derivation and why the drift went
    unnoticed. Capped at 100 (a King can't lose more than the entirety
    of their own Victory Points). Always returns a real value now -- the
    real `outred` table covers all 10 `Alignment` members, not just the
    7 `VITTORIA E FINE PARTITA.txt`'s own shorter table names.
    """

    per_step = OUTLOOK_REDUCTION[king_alignment]
    distance = _alignment_distance_capped_at_hellish(king_alignment, emperor_alignment)
    return round(min(1.0, per_step * distance) * 100)


def _world_vote_weight(state: GameState) -> int:
    """Sum of `kingdom_election_vote_weight()` over every Kingdom -- the
    real `V_world` denominator (report SS13.2/13.4), distinct from
    `_world_tax_base()` (the older, bare-Tax_Base denominator `can_
    request_election()` still uses -- see this module's own Phase 465
    docstring note).
    """

    return sum(kingdom_election_vote_weight(state, kingdom_id) for kingdom_id in state.kingdoms)


def _highest_vote_weight_kingdom(state: GameState) -> tuple[int, int] | None:
    """The single Kingdom with the highest `V_k` -- report SS13.4 step 1.
    Ties keep whichever Kingdom was reached first while scanning in
    ascending Kingdom-ID order (the report's own "resta il Re incontrato
    per primo, quindi il numero di Re più basso"), replicated by only
    replacing the running best on a strict `>` comparison, never on a
    tie. Returns `None` if `state.kingdoms` is empty.
    """

    best: tuple[int, int] | None = None
    for kingdom_id in sorted(state.kingdoms):
        weight = kingdom_election_vote_weight(state, kingdom_id)
        if best is None or weight > best[1]:
            best = (kingdom_id, weight)
    return best


def _election_callers_weight(state: GameState, requesting_kingdom_ids: set[int]) -> int:
    """Sum of `V_k` for every Kingdom in `requesting_kingdom_ids` -- report
    SS13.4 step 3 ("somma il peso dei Regni che hanno richiesto
    l'elezione"). Unlike `can_request_election()`'s own rulebook-literal
    single-King-or-alliance reading (Phase 228), the real compiled routine
    has no alliance concept at all here -- it's a flat sum over every
    Kingdom whose own `kprevgold` currently holds `VOTE_TURN_SENTINEL`
    (`models/kingdom.py KingdomMoveHeader.is_vote_turn()`, Phase 464).
    The caller is responsible for assembling that set from each Kingdom's
    own parsed K1 file for this turn -- not done here, the same "mechanic
    before the plan-file wiring" order this module's own docstring already
    uses for the Call-for-Vote plan action.
    """

    return sum(
        kingdom_election_vote_weight(state, kingdom_id)
        for kingdom_id in requesting_kingdom_ids
        if kingdom_id in state.kingdoms
    )


# The 8 "ordinary" Alignments report SS13.6 accumulates world power for --
# every real Alignment except the two that were never a selectable
# Kingdom alignment (Mechanical/Special), the same exclusion this module's
# own ALIGNMENT_VP_REDUCTION_PER_STEP table already documents.
_ORDINARY_ALIGNMENTS: tuple[Alignment, ...] = tuple(
    member for member in ALIGNMENT_BY_ORDINAL if member not in (Alignment.MECHANICAL, Alignment.SPECIAL)
)


def alignment_bloc_vote_weights(state: GameState) -> dict[Alignment, int]:
    """Per-Alignment sum of `V_k` across every Kingdom sharing that
    Alignment -- report SS13.6's own `V_alignment[a]`, the world power
    accumulated per ordinary Alignment and used by the alignment-bloc
    election auto-trigger below. Only the 8 ordinary Alignments are keyed
    (Mechanical/Special excluded, see `_ORDINARY_ALIGNMENTS`); a Kingdom
    with one of those two Alignments (if this project's data ever
    produces one) still contributes to `V_world` but to no bloc here,
    matching the source's own "otto allineamenti ordinari" scope.
    """

    weights: dict[Alignment, int] = dict.fromkeys(_ORDINARY_ALIGNMENTS, 0)
    for kingdom_id, kingdom in state.kingdoms.items():
        if kingdom.alignment in weights:
            weights[kingdom.alignment] += kingdom_election_vote_weight(state, kingdom_id)
    return weights


def _alignment_auto_trigger(state: GameState, current_turn: int, world_total: int) -> Alignment | None:
    """Report SS13.6's own `alvote` sentinel mechanic: whichever ordinary
    Alignment's own world-power share reaches the (turn-decaying)
    threshold `R` **overwrites** a running `Mechanical`-sentinel value --
    not a "best share wins" comparison like the vote-candidate tie-break
    in `tally_emperor_vote()`, but a plain overwrite each time a
    qualifying Alignment is reached while scanning. Since the source
    doesn't specify the real Pascal enumeration order for this specific
    loop, `ALIGNMENT_ORDINAL` order is assumed (the same real Pascal
    ordinal sequence this project uses everywhere else an Alignment needs
    a canonical order, e.g. `hire_pay.py _alignment_distance()`) -- so the
    *last* qualifying Alignment in that order wins, not the first or the
    highest share. Returns `None` (the "still Mechanical" sentinel) if no
    ordinary Alignment reaches `R`, or if `world_total <= 0`.
    """

    if world_total <= 0:
        return None
    threshold_percent = election_threshold_percent(current_turn)
    weights = alignment_bloc_vote_weights(state)
    winner: Alignment | None = None
    for alignment in _ORDINARY_ALIGNMENTS:
        if weights[alignment] * 100 >= threshold_percent * world_total:
            winner = alignment
    return winner


@dataclass(slots=True)
class ElectionCallOutcome:
    """The real compiled result of report SS13.4's per-turn "does an
    election happen" evaluation -- see `evaluate_election_call()`.
    """

    world_total: int
    immediate_coronation_kingdom_id: int | None
    callers_qualify: bool
    alignment_trigger: Alignment | None

    @property
    def election_scheduled_next_turn(self) -> bool:
        """Whether `req_vote` would be set to `Vote_Turn` for next turn --
        true if the callers' combined weight reached `R`, or an Alignment
        bloc did (report SS13.4 steps 4-5), and nobody was already
        crowned immediately this turn (an immediate coronation
        short-circuits both, per step 3's own "soltanto se nessuno è
        stato incoronato").
        """

        return self.immediate_coronation_kingdom_id is None and (
            self.callers_qualify or self.alignment_trigger is not None
        )


def evaluate_election_call(
    state: GameState, requesting_kingdom_ids: set[int], current_turn: int
) -> ElectionCallOutcome:
    """The real, disassembly-sourced per-turn Emperor-election evaluation
    (report SS13.4/13.6, Phase 465) -- runs every turn automatically,
    regardless of whether any King explicitly asked, unlike `can_request_
    election()`'s own rulebook-literal reading (Phase 228, "un singolo
    Re... alleanza di Re... possono richiedere"). The real compiled
    routine has no alliance concept, and can trigger an election two ways
    `can_request_election()` never modeled at all: an immediate
    coronation that skips voting entirely (step 2 below), and a pure
    Alignment-bloc trigger with no Kingdom having "requested" anything
    (step 5). `can_request_election()` is kept, unchanged, as the
    rulebook-literal approximation it always was -- this function
    supersedes it in spirit, the same way Phase 450/451 superseded this
    module's own original vote-weight/win-condition formulas, without
    deleting the older one (it has its own tests, and neither function is
    called by any other module yet).

    ``requesting_kingdom_ids``: every Kingdom whose own `kprevgold`
    currently holds `VOTE_TURN_SENTINEL` (`models/kingdom.py
    KingdomMoveHeader.is_vote_turn()`, Phase 464) -- the caller's own
    responsibility to assemble from that turn's parsed K1 files; not
    wired here (see module docstring's own Phase 464 cross-reference).

    Implements report SS13.4's own numbered sequence exactly:
    1. find the Kingdom with the single highest `V_k`
    (`_highest_vote_weight_kingdom`);
    2. if its share of `V_world` already reaches `R`, crown it
    immediately -- no vote, no request needed at all;
    3.-4. otherwise, sum the weight of every requesting Kingdom
    (`_election_callers_weight`); if that share reaches `R`, an election
    is scheduled for next turn;
    5. independently, check whether any ordinary Alignment's own bloc
    share reaches `R` (`_alignment_auto_trigger`) -- also schedules next
    turn's election if so.

    Deliberately out of scope (report SS13.4's own text, not a gap in
    this project's data model): the `gametyp` special-case branches
    (Valhalla, `gametyp = 4`, skips normal convocation; Arcane's Valor,
    `gametyp = 10`, adds a separate 3-artifact win condition) -- this
    project has no `gametyp` concept anywhere, the same "no source, no
    guess" boundary `turn/final_standings.py`'s own Phase 454 docstring
    already drew around `kteam`.
    """

    world_total = _world_vote_weight(state)
    if world_total <= 0:
        return ElectionCallOutcome(world_total, None, False, None)

    threshold_percent = election_threshold_percent(current_turn)

    leader = _highest_vote_weight_kingdom(state)
    if leader is not None:
        leader_kingdom_id, leader_weight = leader
        if leader_weight * 100 >= threshold_percent * world_total:
            return ElectionCallOutcome(world_total, leader_kingdom_id, False, None)

    callers_weight = _election_callers_weight(state, requesting_kingdom_ids)
    callers_qualify = callers_weight * 100 >= threshold_percent * world_total
    alignment_trigger = _alignment_auto_trigger(state, current_turn, world_total)

    return ElectionCallOutcome(world_total, None, callers_qualify, alignment_trigger)


def process_election_turn(
    state: GameState,
    kingdom_headers: dict[int, KingdomMoveHeader],
    current_turn: int,
) -> ElectionResult | ElectionCallOutcome:
    """Phase 466 -- the real per-turn state machine tying `evaluate_
    election_call()` and `tally_emperor_vote()` together, modeling report
    SS12.1's own `req_vote` global as `GameState.election_pending_turn`
    (see that field's own docstring).

    ``kingdom_headers``: ``{kingdom_id: KingdomMoveHeader}`` for every
    Kingdom that submitted a move this turn -- the caller's own
    responsibility to assemble (mirrors `orchestrator.py process_turn()`'s
    own per-Kingdom K1-parsing loop; not done here, since this function
    doesn't otherwise need anything else that loop produces). A Kingdom
    missing from this dict submitted no order this turn, which this
    function treats as an abstention/non-request, exactly like a real
    missed-deadline turn would (see `turn/missed_deadline.py`).

    Two mutually exclusive branches, selected by whether a vote is
    already pending for exactly this turn:

    - **`state.election_pending_turn == current_turn`** (report SS12.1's
      ``req_vote = Vote_Turn``): tally it. Each Kingdom's own `kprevgold`
      now holds its candidate choice, not a request toggle -- collected
      into a `ballots` dict, filtering out any value that isn't a real
      Kingdom id in `state.kingdoms` (an abstention, a stale "No_King"
      reset, or any other non-candidate value -- see `KingdomMoveHeader.
      kprevgold`'s own docstring for why this project can't name the
      exact "No_King" sentinel value, and why it doesn't need to: any
      value that isn't a real Kingdom id is an abstention either way).
      `election_pending_turn` is cleared regardless of the vote's own
      outcome (a vote being *held* ends the pending state, win, loss, or
      no quorum).
    - **Otherwise**: evaluate whether this turn crowns someone outright
      or schedules a vote for `current_turn + 1`
      (`evaluate_election_call()`), using each Kingdom's own `kprevgold`
      as a request toggle this time (`KingdomMoveHeader.is_vote_turn()`).
      An immediate coronation sets `state.emperor_kingdom_id` directly
      (no vote to hold, so nothing gets scheduled); a scheduled election
      sets `state.election_pending_turn = current_turn + 1`.
    """

    if state.election_pending_turn == current_turn:
        ballots = {
            kingdom_id: header.kprevgold
            for kingdom_id, header in kingdom_headers.items()
            if header.kprevgold in state.kingdoms
        }
        result = resolve_emperor_election(state, ballots, current_turn)
        state.election_pending_turn = None
        return result

    requesting_kingdom_ids = {
        kingdom_id for kingdom_id, header in kingdom_headers.items() if header.is_vote_turn()
    }
    outcome = evaluate_election_call(state, requesting_kingdom_ids, current_turn)
    if outcome.immediate_coronation_kingdom_id is not None:
        state.emperor_kingdom_id = outcome.immediate_coronation_kingdom_id
        state.last_emperor_vote_turn = current_turn
    elif outcome.election_scheduled_next_turn:
        state.election_pending_turn = current_turn + 1
    return outcome
