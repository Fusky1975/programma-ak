"""Ties parsing, dispatch, and reporting into one real "process a turn"
pipeline (Phase 424) -- the piece this project never had, even though
every individual stage (parser, ``turn_processor.run_turn()``,
``report/turn_report.py describe_turn_results()``/``compose_letter_
report()``) was already real and tested.

**Phase 608 -- real per-King letters, at last.** Until this phase,
``process_turn()`` called only ``describe_turn_results()`` once and
produced a single combined turn narrative for the whole turn -- not
because ``compose_letter_report()`` (the real, 11-section, per-King
letter assembler, wired section-by-section since Phase 215/231/561)
didn't exist, but because nothing had ever called it from here. That
gap is closed: ``process_turn()`` now calls every ``record_*_world_
events()`` recorder exactly once (their own shared, explicit "call once
per turn, before any ``compose_letter_report()`` call" contract --
``record_battle_world_events()``'s own docstring spells out why: world
events are turn-global, calling per-King would duplicate every entry),
then calls ``compose_letter_report()`` once per Kingdom in
``state.kingdoms``, returning ``TurnOutcome.letter_reports: dict[int,
list[str]]`` -- one real, section-rich letter per Kingdom, each showing
that Kingdom's own FINANCES/PROVINCES/CHARACTERS/ARMIES/etc., instead of
one undifferentiated blob every King previously received identically.

**What this still deliberately does NOT do**: the real ``^B``/``^E``
King-exclusion markers (``report/turn_report.py``'s own Phase 96/108
addenda) are a *finer-grained*, still-unbuilt privacy layer -- redacting
specific *lines* about another Kingdom's private affairs that leak into
a section a King *can* otherwise see (e.g. a rival's exact temper
reading inside a shared ASpy-adjacent narrative). That's a separate,
deeper "narrator perspective" system this phase doesn't attempt --
what's fixed here is the *section-level* per-Kingdom split
(``compose_letter_report()`` already reads FINANCES/PROVINCES/etc.
straight from ``state`` filtered to one ``kingdom_id``, which was
already correct), not a per-line redaction system within a section.

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
from ak_engine.report.turn_report import (
    compose_letter_report,
    record_battle_narratives,
    record_battle_world_events,
    record_blackmail_narratives,
    record_illusory_fog_foreign_entry_world_events,
    record_move_world_events,
    record_plague_spread_world_events,
    record_spell_world_events,
    record_sunk_cargo_world_events,
    record_uncontested_conquest_world_events,
    record_wandering_world_events,
)
from ak_engine.turn.assassin_guild import resolve_pending_guild_assassination
from ak_engine.turn.emperor_election import ElectionCallOutcome, ElectionResult, process_election_turn
from ak_engine.turn.final_standings import FinalStandingsReport, compose_final_standings_report
from ak_engine.turn.kingdom_bridge import KingdomBridgeReport, sync_leaders_from_kingdom
from ak_engine.turn.movement import MapBounds
from ak_engine.turn.office_holder import commit_army_office_holders, commit_office_holders
from ak_engine.turn.turn_processor import (
    PhaseDispatchResult,
    TurnLeader,
    build_missed_deadline_turn_leaders,
    run_turn,
)
from ak_engine.turn.world_events import record_kingdom_contacts


@dataclass(slots=True)
class TurnOutcome:
    """Everything one ``process_turn()`` call produced, for a caller to
    inspect, write to files, or feed into the next turn.
    """

    results: list[PhaseDispatchResult]
    # Phase 608: one real, section-rich `compose_letter_report()` letter
    # per Kingdom, keyed by `kingdom_id` -- replaces the old single
    # `report_lines: list[str]` combined narrative (see module docstring's
    # own Phase 608 addendum for why that was a documented simplification,
    # not a silent one, and exactly what's still open beyond it).
    letter_reports: dict[int, list[str]]
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
    board_width: int | None = None,
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

    **Phase 676**: right after that same election/final-standings step,
    ``turn/office_holder.py commit_office_holders()``/``commit_army_
    office_holders()`` settle this turn's own real Office winners into
    ``state.office_holders``/``state.army_office_holders`` -- the "no
    natural once-per-turn hook exists" gap both functions' own
    docstrings named (``turn_processor.py run_turn()`` runs once per
    *phase*, not once per real turn, so it was never the right place).
    Confirmed no production caller invoked either function before this
    phase (``turn/assassin_guild.py``'s own module docstring flagged it
    directly), leaving the real, sourced "previous titleholder retains
    ties" tie-break (SS14.4) permanently inert. Placed here, before
    ``compose_letter_report()`` below, deliberately: this turn's own
    just-computed winner can only reinforce itself when that report's
    own fresh ``resolve_office_holder()`` calls read it back moments
    later (it already won under yesterday's sticky reference, so
    marking it sticky now cannot un-select it) -- only the *next* real
    turn's own resolution is materially affected.

    **Phase 574**: any Kingdom in ``state.kingdoms`` with no order file in
    ``order_file_paths`` this turn gets the real ``REPORTS.PAS Set_Defend``
    missed-deadline auto-fill (``turn/missed_deadline.py`` via
    ``turn/turn_processor.py build_missed_deadline_turn_leaders()``)
    merged into the same ``run_turn()`` dispatch, instead of being
    silently absent from the turn.

    **Phase 608**: after the election/final-standings step, every real
    ``record_*_world_events()`` recorder runs exactly once, in the same
    order each was introduced (battle, spell, plague-spread, move,
    uncontested-conquest -- their own docstrings confirm order doesn't
    matter for correctness, only that each runs once, turn-globally,
    before any letter is composed). ``compose_letter_report()`` is then
    called once per ``state.kingdoms`` entry, producing ``TurnOutcome.
    letter_reports`` -- see module docstring's own Phase 608 addendum.

    ``board_width`` (Phase 780, default ``None``) falls back to
    ``state.board_width`` -- the real value the world was actually built
    at (``worldgen/generate_new_game.py``/``parser/gw_world_bridge.py``)
    -- when omitted, so a caller no longer has to separately track it
    alongside ``state`` just to avoid every downstream fallback silently
    defaulting to the wrong (Super-AK) constant.

    **Phase 872**: ``turn/world_events.py record_kingdom_contacts()``
    joins the Phase 608 recorder cluster above -- also turn-global,
    also previously uncalled from anywhere (its own docstring already
    said "must be called once per turn," but nothing ever did). See
    that function's own module docstring for the real downstream
    consumers this was silently starving.
    """

    if rng is None:
        rng = random.Random()
    board_width = board_width if board_width is not None else state.board_width

    turn_leaders: list[TurnLeader] = []
    bridge_reports: dict[int, KingdomBridgeReport] = {}
    kingdom_headers: dict[int, KingdomMoveHeader] = {}

    for path in order_file_paths:
        kingdom = parse_k1_moves_file(path)
        # Phase 574: kingdom.kingdom_id (derived from the file's own name)
        # replaced kingdom.header.kingdom_number here -- see that
        # property's own docstring for why the header field was
        # confirmed broken (Phase 464) and how the filename-derived
        # replacement was confirmed instead.
        kingdom_id = kingdom.kingdom_id
        bridge_report = sync_leaders_from_kingdom(kingdom, state)
        bridge_reports[kingdom_id] = bridge_report
        kingdom_headers[kingdom_id] = kingdom.header

        for leader in kingdom.leaders:
            if leader.leader_id in bridge_report.not_found_leader_ids:
                continue
            turn_leaders.append(TurnLeader(leader, kingdom_id))

    # Phase 574: a Kingdom tracked in state.kingdoms with no order file
    # among order_file_paths this turn (i.e. missing from kingdom_headers)
    # missed the move-submission deadline entirely -- REPORTS.PAS's own
    # Set_Defend auto-fill applies to it (turn/missed_deadline.py), same
    # as a real missed submission. Without this, such a Kingdom was simply
    # absent from run_turn()'s dispatch instead of getting its rulebook-
    # mandated Defend/Wait plan.
    for kingdom_id in state.kingdoms:
        if kingdom_id not in kingdom_headers:
            turn_leaders.extend(build_missed_deadline_turn_leaders(state, kingdom_id))

    results = run_turn(turn_leaders, state, board_width=board_width, rng=rng)

    # Phase 614: the Grandfather of Assassins title's own free attempt,
    # if a FI order queued one during this same run_turn() call
    # (turn/plan_dispatch.py _dispatch_fire()'s own interception) --
    # resolved exactly once here, right after battles for the turn are
    # done, matching the real "end of phase 5, after battles" timing
    # (see turn/assassin_guild.py resolve_pending_guild_assassination()'s
    # own docstring). Wrapped into the same sentinel-PhaseDispatchResult
    # convention turn_processor.py already established for plague-spread/
    # forced-rebattle entries (leader_id keyed to the *victim*, not the
    # titleholder, so compose_letter_report()'s own per-Kingdom filtering
    # routes the outcome to the victim's own Kingdom letter).
    guild_outcome = resolve_pending_guild_assassination(state, rng)
    if guild_outcome is not None:
        results.append(
            PhaseDispatchResult(
                leader_id=guild_outcome.target_leader_id,
                segment_index=-1,
                phase_label="guild-assassination",
                action=None,
                result=guild_outcome,
                error=None,
            )
        )

    election_outcome = process_election_turn(state, kingdom_headers, state.turn_number)
    final_standings_report = compose_final_standings_report(state)

    # Phase 676: settles this turn's real Office winners into `state.
    # office_holders`/`state.army_office_holders` for next turn's own
    # "previous titleholder retains ties" tie-break (`turn/office_
    # holder.py resolve_office_holder()`/`resolve_army_office_holder()`
    # SS14.4) -- the "caller's own explicit persist step" both commit
    # functions' own docstrings describe, with no natural hook anywhere
    # in `turn_processor.py run_turn()` (which runs once per phase, not
    # once per real turn). Placed here, before `compose_letter_report()`
    # below: this turn's own just-computed winner can only reinforce
    # itself when that report's own fresh `resolve_office_holder()`
    # calls read it back moments later (it already won under yesterday's
    # sticky reference, so marking it sticky now cannot un-select it) --
    # only the *next* real turn's own resolution is materially affected.
    commit_office_holders(state)
    commit_army_office_holders(state)

    # Phase 608: each recorder is turn-global (see record_battle_world_
    # events()'s own docstring) -- called exactly once here, never once
    # per Kingdom, or GENERAL INTELLIGENCE REPORT would show every event
    # duplicated once per Kingdom in the loop below.
    record_battle_world_events(state, results, rng)
    # Phase 711 -- same once-per-turn requirement as its sibling above;
    # populates the two involved Kingdoms' own ACTION REPORT narrative
    # (state.battle_narratives_by_kingdom), not GENERAL INTELLIGENCE.
    record_battle_narratives(state, results, rng)
    # Phase 736 -- same once-per-turn requirement; populates state.world_
    # events from state.sunk_cargo_events (recorded live during battle
    # resolution above, at each of the 4 real fight_battle() call sites).
    record_sunk_cargo_world_events(state, rng)
    # Phase 713 -- same once-per-turn requirement; populates both the
    # blackmailer's and the victim's own ACTION REPORT (state.
    # blackmail_narratives_by_kingdom), not GENERAL INTELLIGENCE.
    record_blackmail_narratives(state, results, rng)
    record_spell_world_events(state, results, rng, board_width=board_width)
    record_plague_spread_world_events(state, results, rng)
    record_move_world_events(state, results, rng)
    record_illusory_fog_foreign_entry_world_events(state, results, rng)
    record_uncontested_conquest_world_events(state, results, rng)
    # Phase 781 -- same once-per-turn requirement as its siblings above;
    # populates state.world_events from the wandering relocations `turn/
    # turn_processor.py run_turn()`'s own end-of-turn tail appended.
    record_wandering_world_events(state, results, rng)
    # Phase 872 -- same once-per-turn requirement as every recorder
    # above (`turn/world_events.py record_kingdom_contacts()`'s own
    # docstring: "must be called once per turn"), but genuinely never
    # had a caller anywhere before this phase -- confirmed by grep,
    # zero call sites outside its own definition and unit tests. Every
    # real game processed by this engine therefore left GameState.
    # kingdoms_met/kingdoms_met_since permanently empty, silently
    # starving World Emperor's/Imperial Treasurer's own real perks
    # (`turn/imperial_intelligence.py`) and describe_diplomacy_report()'s
    # own alignment sentence, all of which read that same state.
    record_kingdom_contacts(state, MapBounds(board_width, state.board_height))

    letter_reports = {
        kingdom_id: compose_letter_report(
            results, state, kingdom_id, rng, board_width=board_width, election_outcome=election_outcome
        )
        for kingdom_id in state.kingdoms
    }

    return TurnOutcome(
        results=results,
        letter_reports=letter_reports,
        bridge_reports=bridge_reports,
        election_outcome=election_outcome,
        final_standings=final_standings_report,
    )
