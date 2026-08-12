"""Ties parsing, dispatch, and reporting into one real "process a turn"
pipeline (Phase 424) -- the piece this project never had, even though
every individual stage (parser, ``turn_processor.run_turn()``,
``report/turn_report.py describe_turn_results()``) was already real and
tested.

**Scope, and what this deliberately does NOT do**: a real King's own
letter is personalized -- ``report/turn_report.py``'s own Phase 96/108
addenda already document real ``^B``/``^E`` King-exclusion markers this
project elides rather than guesses at, because building the real
per-recipient "narrator perspective" system (whose lines a given King
does/doesn't see) is a separate, larger, unbuilt feature. So
``process_turn()`` produces exactly one combined turn narrative (every
line ``describe_turn_results()`` would produce for the whole turn), not
one personalized letter per kingdom -- an honest simplification, not a
silent one.

``run_turn()`` itself expects every leader submitting orders *this
turn*, across *every* kingdom, in one flat list -- it's the only place
same-phase Multiple Contingents detection (several kings' armies
converging on one province) can happen (see ``turn/turn_processor.py``'s
own module docstring). So ``process_turn()`` parses every order file
first, then dispatches one combined ``run_turn()`` call, not one call
per kingdom.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from pathlib import Path

from ak_engine.models.game_state import GameState
from ak_engine.models.kingdom import KingdomMoveHeader
from ak_engine.parser.k1_moves import parse_k1_moves_file
from ak_engine.report.turn_report import describe_turn_results
from ak_engine.turn.emperor_election import ElectionCallOutcome, ElectionResult, process_election_turn
from ak_engine.turn.final_standings import FinalStandingsReport, compose_final_standings_report
from ak_engine.turn.kingdom_bridge import KingdomBridgeReport, sync_leaders_from_kingdom
from ak_engine.turn.turn_processor import PhaseDispatchResult, TurnLeader, run_turn


@dataclass(slots=True)
class TurnOutcome:
    """Everything one ``process_turn()`` call produced, for a caller to
    inspect, write to files, or feed into the next turn.
    """

    results: list[PhaseDispatchResult]
    report_lines: list[str]
    bridge_reports: dict[int, KingdomBridgeReport] = field(default_factory=dict)  # kingdom_id -> report
    # Phase 466: whichever of the two `turn/emperor_election.py
    # process_election_turn()` shapes this turn produced -- an
    # `ElectionResult` if a pending vote was tallied this turn, or an
    # `ElectionCallOutcome` otherwise (whether or not it actually
    # scheduled/crowned anything). See that function's own docstring.
    election_outcome: ElectionResult | ElectionCallOutcome | None = None
    # Phase 476: `turn/final_standings.py compose_final_standings_report()`'s
    # own result -- `None` before any Emperor exists, otherwise the real
    # "unified world" standings/points/all-star/Valhalla snapshot SS14.1
    # says gets computed every post-turn from coronation onward. See that
    # function's own docstring for why no report prose is composed for it
    # here (same split `election_outcome` above already established).
    final_standings: FinalStandingsReport | None = None


def process_turn(
    state: GameState,
    order_file_paths: list[Path],
    *,
    board_width: int,
    rng: random.Random | None = None,
) -> TurnOutcome:
    """Parses every ``.K1`` move file in ``order_file_paths``, syncs each
    kingdom's real move-file data (``kingdom_id``/``skills``/``is_king``)
    into ``state`` via ``turn/kingdom_bridge.py sync_leaders_from_kingdom()``,
    dispatches the whole turn in one ``run_turn()`` call, and narrates the
    result. Mutates ``state`` in place (the same convention ``run_turn()``
    itself already has); the caller is responsible for persisting it
    afterward (see ``persistence.py``).

    A leader named in an order file with no existing ``LeaderState`` in
    ``state`` is skipped -- see ``kingdom_bridge.py``'s own docstring for
    why this project has no way to fabricate one (a move file carries no
    location/race/treasury). Its own kingdom's ``KingdomBridgeReport``
    (returned in ``TurnOutcome.bridge_reports``) records exactly which
    leader ids were skipped, so a caller can surface that to the user
    instead of it silently vanishing.

    **Phase 466**: after the five phases run, evaluates the Emperor
    election exactly where report SS13.1's own routine does -- after
    "effetti e consolidamenti di fine turno" but before report
    generation -- via ``turn/emperor_election.py process_election_turn()``,
    fed with every Kingdom's own real ``KingdomMoveHeader`` collected
    during the same parsing loop above (no second parse needed). The
    result is returned as ``TurnOutcome.election_outcome``; state
    mutations (a fresh ``state.emperor_kingdom_id``, an ``election_
    pending_turn`` scheduled for next turn, or a just-tallied vote's own
    result) happen inside that function, not here.

    **Phase 476**: immediately after that same election step, computes
    ``turn/final_standings.py compose_final_standings_report()`` -- SS14.1
    (real disassembly source): coronation, the final report, and the
    "unified world" standings all land in the *same* post-turn, never a
    turn later, so this call belongs right alongside ``process_election_
    turn()``'s own, not deferred to some later step. Returns ``None``
    before any Emperor exists; from the coronation turn onward, every
    later turn recomputes it fresh (the real engine's own behavior, not a
    one-time "game over" snapshot).
    """

    if rng is None:
        rng = random.Random()

    turn_leaders: list[TurnLeader] = []
    bridge_reports: dict[int, KingdomBridgeReport] = {}
    kingdom_headers: dict[int, KingdomMoveHeader] = {}

    for path in order_file_paths:
        kingdom = parse_k1_moves_file(path)
        # kingdom_number is confirmed (Phase 464) to actually be a global
        # interpreter-version constant, not a per-Kingdom identifier -- see
        # KingdomMoveHeader.kingdom_number's own docstring for the sourced
        # proof and the still-open follow-up to find the real per-Kingdom id.
        kingdom_id = kingdom.header.kingdom_number
        bridge_report = sync_leaders_from_kingdom(kingdom, state)
        bridge_reports[kingdom_id] = bridge_report
        kingdom_headers[kingdom_id] = kingdom.header

        for leader in kingdom.leaders:
            if leader.leader_id in bridge_report.not_found_leader_ids:
                continue
            turn_leaders.append(TurnLeader(leader, kingdom_id))

    results = run_turn(turn_leaders, state, board_width=board_width, rng=rng)
    election_outcome = process_election_turn(state, kingdom_headers, state.turn_number)
    final_standings_report = compose_final_standings_report(state)
    report_lines = describe_turn_results(results, state, rng, board_width=board_width)

    return TurnOutcome(
        results=results,
        report_lines=report_lines,
        bridge_reports=bridge_reports,
        election_outcome=election_outcome,
        final_standings=final_standings_report,
    )
