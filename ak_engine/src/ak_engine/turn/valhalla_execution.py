"""Spawning the turn's Valhalla visitor, once Gate Angel's own reservoir-
sampling winner is final -- Phase 196.

``turn/cast_execution.py _execute_gate_angel`` (Phase 194, corrected
Phase 195) already resolves *who* gets this turn's Valhalla visit
(``GameState.last_gate_angel_kingdom``/``last_gate_angel_turn``,
possibly overwritten more than once within one turn as later same-
alignment candidates win the reservoir swap -- see that module's own
"Phase 195 addendum"). This module is the second, separate stage: once
that winner is truly final (i.e. every leader's Cast phase has been
dispatched for the turn), pick a real hero from ``models/valhalla.py
VALHALLA_ROSTER`` and materialize it as a genuine ``LeaderState``.

**Phase 756 -- the ordinary, per-turn automatic visit (independent of
Gate Angel).** ``Desktop/AKGEN 0xEB8A.md`` (2026-09-06) and this
project's own ``Desktop/VALHALLA.txt`` rule 1 both confirm the real
mechanic is broader than "Gate Angel produces a visitor": *every* turn,
regardless of any spell being cast, one Kingdom of the turn's own due
alignment receives a visit -- "Ciascun allineamento da Buono a
Malvagio... riceverà una visita una volta ogni cinque turni." Before
this phase, ``finalize_gate_angel_visit()`` below was the *only* spawn
path wired into ``turn/turn_processor.py run_turn()``, gated entirely
on a successful Gate Angel cast -- a game with no Gate Angel caster
anywhere would never see a single Valhalla visit, contradicting this
unconditional guarantee. ``finalize_ordinary_valhalla_visit()`` (new
this phase) is the second, independent trigger: it runs whenever the
Gate-Angel path didn't already claim this turn's one visit
(``VALHALLA.txt`` rule 2, "solo un visitatore... a turno"), using the
real per-King selection formula the new document supplies (``select_
ordinary_valhalla_recipient()``). Both paths share the same hero-
materialization body (``_spawn_valhalla_visitor()``, extracted this
phase) and the same "last visited"/"visit count" bookkeeping
(``_record_valhalla_visit()``) -- see each function's own docstring.

**Wired into ``turn/turn_processor.py``'s own ``run_turn()`` as of
Phase 199** (its own "GATE ANGEL / VALHALLA VISIT" docstring section):
``finalize_gate_angel_visit()`` below is called exactly once per turn,
after every leader's Cast phase has been dispatched -- calling it any
earlier would risk picking the wrong kingdom's hero, since a later
same-turn, same-due-alignment cast can still steal the reservoir-
sampling win. This mirrors the "implement the execution function, wire
it into the real dispatch loop in a later phase" split this project
already used for Cast execution itself (Phase 172 implemented
``_execute_charm``/``_execute_kill_enemy`` as standalone, tested
functions; Phase 173 wired them into ``plan_dispatch.py``).

**Phase 386 correction**: "reservoir sampling" above is legacy
terminology -- ``turn/cast_execution.py _gate_angel_register_candidate``
no longer does that (see its own docstring for the real, non-uniform
contention rule); the *shape* described here (later same-turn candidates
can still overwrite the current winner, so this module must run last)
is unchanged. This phase also replaces this module's own ``rng.choice(
roster)`` hero pick with the real ``visitor_selection`` algorithm --
see ``_select_visitor_template()`` below.

**The recipient is the winning Kingdom's own King** ("I personaggi
appariranno a fianco del Re" -- the visitor spawns at the King's own
current location), found via ``LeaderState.is_king``. If the winning
Kingdom genuinely has no King on record (a state this project's own
``LeaderState.is_king`` convention doesn't otherwise guard against),
the visitor spawns at the Kingdom's own ``home_province`` instead --
an unsourced but reasonable fallback location, not a documented rule.

**The fixed magic item** (rulebook: "un oggetto magico prefissato...
che non possono dare a nessuno") is created via ``GameState.add_item()``
-- ``models/treasure.py``'s own module docstring already flags this as
the *only* real Pascal call site ``Add_Tr`` (the routine
``GameState.add_item()`` mirrors) is confirmed to have, a narrow
Valhalla-visitor special case, not a general item-generation pipeline.
Skipped entirely for the two heroes whose own ``fixed_item`` is
``None`` (see ``models/valhalla.py``'s own docstring for the two
unresolved item names) -- no item is fabricated in their place.

**Phase 546**: a monster/Valhalla audit re-found this module's own
prior "not modeled" list -- the escalating per-visit phase allowance
and the fixed item's own tracked ``item_id`` are now recorded at spawn
time (``LeaderState.valhalla_active_turn``/``valhalla_allowed_phase_
count``/``valhalla_fixed_item_id`` -- see ``models/valhalla.py
_valhalla_stay_phase_count()`` for the escalating table itself).
**Stale as of Phase 689 -- this used to list all of the below as "not
yet enforced," but Phase 547/548 closed every one of them the very
next phase, and nobody came back to correct this paragraph:**
``turn/plan_dispatch.py`` caps phases at dispatch (`valhalla_cap_
active`/`valhalla_allowed_phase_count`, including the "only one
Practice phase" rule); ``turn/cast_execution.py`` grants spell-immunity
except Resurrection to the active visitor; ``turn/trade_execution.py``
blocks Give specifically on ``valhalla_fixed_item_id``; and this same
module's own ``process_valhalla_departure()``/``_reassign_visitor_
armies()`` (below) fully handle army hand-off (King -> co-located
leader -> adjacent garrison -> disband) and item/loot routing, wired
live into ``turn/turn_processor.py`` alongside ``finalize_gate_angel_
visit()``. **Turn-deadline voiding stays confirmed out of scope
entirely**: this codebase has no in-engine "did this Kingdom miss the
deadline" detector at all (``turn/missed_deadline.py``'s own module
docstring -- it's an external, caller-level fact nothing in
``GameState`` tracks), so there's no hook to attach this rule to
without inventing an external contract this project doesn't otherwise
have.

**`VALHALLA_VISIT_ANNOUNCEMENT_TEMPLATE` (Phase 585)**: this project
never had the real narration text for a Valhalla visit at all --
`SAY.PAS:46-52 Get_VFN` dispatches each of the 5 alignment-pool
catalogs (`GOOD.X2`/`EVIL.X2`/`NEUTRAL.X2`/`PAGAN.X2`/`DRUIDIC.X2`,
paired with a `...2.X2` data half each), and a byte-faithful third-
party reverse-engineering pass over the full 162-file prose corpus
(`AKPROSE_reverse_engineering_report.md`, supplied directly by the
user) reconstructs their real content. **These catalogs are not
reusable game design content, though** -- confirmed by
`AKPROSE_reverse_engineering_report.md`'s own §7.8 ("I dieci cataloghi
Valhalla sono un database mutabile a coppie") and directly by the
content itself: every real entry names a specific historical hero by
its own real player-chosen nickname ("Santa", "SWK", "Balin", "Baron
Shadowrunner") and a specific real past game number ("Game 52", "from
game 165", "from game 8001225") -- `REPORTS.PAS Write_VF` (~lines
1358-1410) confirms these files are genuinely persistent and
append-only, growing by one real record every time an actual historical
game crowned a winner. This is personal history belonging to real
people who played this game over the years, not fictional in-universe
content -- **deliberately not transcribed here**, matching every other
real name/game-number instance found while surveying the corpus.

What *is* transcribed is the one clean, reusable template sentence
confirmed to repeat identically (modulo the per-hero substitution)
across every alignment pool checked (`GOOD.X2`/`EVIL.X2`, at minimum):
"`< was visited by a hero from Valhalla, named =!The characteristics
for this great King from Game # are given in your "CHARACTERS"
report.`" -- `<` is the visited King (already-established convention),
`=` the hero's own name (`ValhallaHero.name`, matching `models/
valhalla.py`'s own already-transcribed 137-hero roster -- a completely
separate, user-supplied, genuinely fictional source, not these
catalogs). `#` is the specific historical game number each real record
carries -- this project's own single-simulation-instance `GameState`
has no such concept and never will (there is no "which numbered game is
this" field to fill it with), so it's kept as the literal, unresolved
`#` marker rather than invented or dropped. No render wrapper is built
here (unlike this module's own other confirmed mechanics) precisely
because of that missing field -- a future phase that decides what (if
anything) `#` should render as can build one.
"""

from __future__ import annotations

import math
import random

from ak_engine.models.alignment import Alignment
from ak_engine.models.game_state import GameState, LeaderState
from ak_engine.models.valhalla import (
    VALHALLA_ROSTER,
    VALHALLA_VISITOR_LEADER_ID,
    ValhallaHero,
    _valhalla_stay_phase_count,
)
from ak_engine.turn.battle_orchestrator import find_king_of_kingdom
from ak_engine.turn.cast_execution import GATE_ANGEL_ELIGIBLE_ALIGNMENTS, gate_angel_due_alignment
from ak_engine.turn.movement import MapBounds, neighbors

# HostAK/TP/PROSE/GOOD.X2 (and identically, EVIL.X2) choice 1's own real
# template sentence, redacted of every real historical name/game number
# -- see module docstring's own Phase 585 addendum for why. `<` the
# visited King, `=` the hero's own name, `#` the historical game number
# (no consumer in this project -- kept literal, not resolved).
VALHALLA_VISIT_ANNOUNCEMENT_TEMPLATE = (
    '< was visited by a hero from Valhalla, named =!The characteristics '
    'for this great King from Game # are given in your "CHARACTERS" report.'
)

# HostAK/TP/PROSE/VALINT.X2 -- the rulebook explanation of the Valhalla
# visiting-Hero mechanic, shown alongside the announcement above
# (Phase 606). `SAY.PAS:1212 _LValHal: FD('valint.x2',S_Red,1)`. Plain
# `[`/`[1`/`]` pronoun markers throughout, no `/R`/`{...}`/`^A` at all
# ("nessun token speciale rilevato").
#
# **A real, confirmed anomaly, not a transcription choice**: the file's
# own header declares `1 9` (one choice, 9 lines), but the real payload
# has 10 real lines plus a trailing blank one -- `FD()` only ever reads
# the header's own declared 9, so the 10th line below was **never
# actually printed by the original engine**, confirmed independently by
# this module's own pre-existing Phase 527-era docstring note above
# ("Turn-deadline voiding stays confirmed out of scope entirely...no
# hook to attach this rule to"). Kept here anyway, clearly separated and
# labeled, matching this project's own established precedent of
# preserving every real byte found (Phase 580's `TREASURE_NAME` gap,
# Phase 590's `GMSPOILS.X` overflow) rather than silently truncating to
# the declared header.
VALHALLA_VISITOR_RULES_TEMPLATE: tuple[str, ...] = (
    "If [1 searches a feature, any monetary treasure [1 captures will be given to you.",
    "If [1 captures a magic treasure, [1 will give it to your King when he departs "
    "for Valhalla, or you can order [ to Give it to one of your characters.",
    "You can do anything you want with the magic item [1 came with, but the item "
    "will leave at the end of ] stay with you.",
    "Except for the rules given in this paragraph, [1 can generally be treated just "
    "like your other Heroes, and can be affected by any spell except Resurrection.",
    "The main limitation in using [ is that [1 has only enough patience to practice "
    "with you for one of the phase(s) [1 is with you.",
    "[1 will leave at the end of the last phase [1 is scheduled to serve you, after "
    "all battles have been fought.",
    "[1 can lead armies, but when [1 returns to Valhalla, the armies will normally "
    "be left leaderless in the province they are in.",
    "If [1 has the armies in a province you don't own, they will be transferred to "
    "your lowest-numbered leader in the same province, or at last resort, the "
    "garrison commander in an adjacent province owned by you.",
    "If no leader is available, the armies will be disbanded.",
)

# The file's real, 10th physical line -- confirmed never printed by the
# original engine's own 9-line header limit (see the comment above).
# Kept as a separate, clearly-unreachable constant rather than appended
# to `VALHALLA_VISITOR_RULES_TEMPLATE`, so nothing renders it by accident.
VALHALLA_VISITOR_RULES_UNREACHABLE_DEADLINE_LINE = (
    "If you miss the turn deadline, [1 will disappear and your orders for [ will be voided."
)


def _select_visitor_template(
    state: GameState, alignment: Alignment, roster: tuple[ValhallaHero, ...], rng: random.Random
) -> ValhallaHero:
    """AKGEN's own confirmed ``visitor_selection`` (Phase 386, replacing
    the earlier ``rng.choice(roster)`` placeholder): "turns 1-5 always
    [use the] final roster record" -- confirmed by name, not just shape:
    every one of this project's own 5 ``VALHALLA_ROSTER`` alignment
    lists already ends with exactly the hero the source's own
    ``distributed_defaults`` names for that alignment (Good/Quintilian,
    Druidic/Bo, Neutral/Kitralus, Pagan/Kelderek, Evil/Dietrich) -- a
    5-for-5 exact match. From turn 6 on: "(IRand MOD choices)+1 on first
    invocation," then "advance with a randomly signed coprime stride,
    producing a full permutation before repetition" -- the stride is
    drawn once (uniformly among the roster-size's own coprime residues)
    the first time this alignment is selected after turn 5, then reused
    every later call, guaranteeing (by the standard modular-arithmetic
    fact that a coprime step cycles through every residue before
    repeating) that no hero repeats until the whole roster has been
    visited. The source doesn't pin down exactly *how* the coprime
    stride itself is chosen among the valid candidates -- picked
    uniformly among them here, an honest, undocumented parameter choice
    in an otherwise exactly-confirmed algorithm shape.
    """

    if state.turn_number <= 5:
        return roster[-1]

    n = len(roster)
    if n == 1:
        return roster[0]

    sequence = state.valhalla_visitor_sequence.get(alignment)
    if sequence is None:
        index = rng.randrange(n)
        coprime_strides = [s for s in range(1, n) if math.gcd(s, n) == 1]
        stride = rng.choice(coprime_strides) if coprime_strides else 1
        step = rng.choice((1, -1)) * stride
    else:
        previous_index, step = sequence
        index = (previous_index + step) % n

    state.valhalla_visitor_sequence[alignment] = (index, step)
    return roster[index]


def _spawn_valhalla_visitor(
    state: GameState, kingdom_id: int, alignment: Alignment, rng: random.Random, board_width: int
) -> LeaderState | None:
    """Materializes a real Valhalla visitor for ``kingdom_id``, drawn
    from ``alignment``'s own roster -- the shared hero-synthesis body
    both real trigger paths use (Gate Angel and, since Phase 756, the
    ordinary per-turn rotation). Returns ``None`` (defensively; shouldn't
    happen once all 5 ``turn/cast_execution.py GATE_ANGEL_ELIGIBLE_
    ALIGNMENTS`` have a real roster, as they now do) if ``alignment``'s
    own roster is empty.

    **Phase 548 bug fix** (pre-dates the Phase 756 extraction): this
    function used to overwrite ``state.leaders[VALHALLA_VISITOR_LEADER_
    ID]`` unconditionally -- if a prior visitor was still present (their
    own ``valhalla_active_turn`` hasn't been reached/processed yet this
    same turn), their identity was silently clobbered while any items/
    armies still referencing leader 199 kept pointing at it, now
    misattributed to the new hero. A stale occupant is now sent through
    ``process_valhalla_departure()`` first -- the same army hand-off/
    item transfer a normal on-schedule departure gets -- before the new
    hero is ever assigned. ``board_width`` is required here (not
    defaulted) since both real callers already have a real value in
    scope.
    """

    roster = VALHALLA_ROSTER.get(alignment, ())
    if not roster:
        return None

    if VALHALLA_VISITOR_LEADER_ID in state.leaders:
        process_valhalla_departure(state, board_width=board_width)

    template = _select_visitor_template(state, alignment, roster, rng)

    kingdom = state.kingdoms[kingdom_id]
    king = find_king_of_kingdom(state, kingdom_id)
    location = king.location if king is not None else kingdom.home_province

    # Phase 546 -- the visitor's own one active turn is the turn *after*
    # this one: this function runs in run_turn()'s own end-of-turn tail,
    # after this turn's own phase-dispatch loop already ran, so the
    # visitor genuinely can't act until state.turn_number + 1. See
    # models/valhalla.py _valhalla_stay_phase_count()'s own docstring
    # for the escalating phase-count table this turn number drives.
    active_turn = state.turn_number + 1
    visitor = LeaderState(
        leader_id=VALHALLA_VISITOR_LEADER_ID,
        kingdom_id=kingdom_id,
        name=template.name,
        location=location,
        skills=template.skills,
        temper=template.temper,
        alignment=template.true_alignment,
        race=template.race,
        valhalla_active_turn=active_turn,
        valhalla_allowed_phase_count=_valhalla_stay_phase_count(active_turn),
    )
    state.leaders[visitor.leader_id] = visitor

    if template.fixed_item is not None:
        item = state.add_item(template.fixed_item, owner_leader_id=visitor.leader_id)
        visitor.valhalla_fixed_item_id = item.item_id

    return visitor


def _record_valhalla_visit(state: GameState, kingdom_id: int) -> None:
    """Phase 756 -- updates the shared "last visited"/"visit count"
    state both trigger paths feed, right after a real spawn. The GW
    field this reuses (``m_values[B+0]``) is one counter shared across
    both trigger types -- see module docstring's own Phase 756 addendum
    for why a Gate-Angel-triggered visit counts here too."""

    state.last_valhalla_visited_kingdom_id = kingdom_id
    state.kingdoms[kingdom_id].valhalla_visit_count += 1


def finalize_gate_angel_visit(state: GameState, rng: random.Random, *, board_width: int | None = None) -> LeaderState | None:
    """Spawns this turn's Valhalla visitor, if Gate Angel produced one.

    Returns ``None`` (no state mutation at all) when no Gate Angel cast
    succeeded this turn, or (see ``_spawn_valhalla_visitor()``'s own
    docstring) the winning turn's due alignment has no roster entries.
    ``board_width`` (Phase 780, default ``None``) falls back to ``state.
    board_width`` -- the real value the world was actually built at --
    since departure processing only needs it for the adjacent-province
    leg of that hand-off chain.
    """

    board_width = board_width if board_width is not None else state.board_width

    if state.last_gate_angel_turn != state.turn_number:
        return None
    kingdom_id = state.last_gate_angel_kingdom
    if kingdom_id is None:
        return None

    visitor = _spawn_valhalla_visitor(state, kingdom_id, state.gate_angel_due_alignment, rng, board_width)
    if visitor is not None:
        _record_valhalla_visit(state, kingdom_id)
    return visitor


def select_ordinary_valhalla_recipient(state: GameState, alignment: Alignment, rng: random.Random) -> int | None:
    """`Desktop/AKGEN 0xEB8A.md`'s own confirmed per-King selection
    within the turn's due ``alignment`` (Phase 756): for every Kingdom of
    that alignment except ``state.last_valhalla_visited_kingdom_id`` (the
    immediately preceding visit's own recipient),

        score(k) = (IRand AND 1023) - 1024 * kingdom.valhalla_visit_count

    realized here as ``int(rng.random() * 1024) - 1024 * ...`` (the same
    "ordinary ``random.Random`` reduction matching the Pascal formula's
    statistical shape" convention every other ``turn/``-scoped formula
    in this project already uses -- a plain ``.random()`` scale rather
    than ``rng.randrange()``, whose own ``_randbelow`` fallback can
    consume a variable, not-easily-predictable number of ``.random()``
    calls on a class that overrides ``random()`` but not
    ``getrandbits()``, exactly this project's own ``ScriptedRandom``). The 1024-point-wide bands never
    overlap, so a King with strictly fewer visits always outscores one
    with more -- this is a real priority order, not just a statistical
    lean. Ties (same visit count, same drawn value) go to the **lower**
    ``kingdom_id`` -- realized by only replacing the running best on a
    *strict* ``>``, iterating candidates in ascending id order, matching
    the source's own confirmed ``>``-comparison behavior exactly.

    Returns ``None`` when no candidate remains (no Kingdom of this
    alignment at all, or the only one is excluded) -- the caller falls
    back to ``select_valhalla_fallback_recipient()``.
    """

    best_kingdom_id: int | None = None
    best_score: int | None = None
    for kingdom in sorted(state.kingdoms.values(), key=lambda k: k.kingdom_id):
        if kingdom.alignment is not alignment or kingdom.kingdom_id == state.last_valhalla_visited_kingdom_id:
            continue
        score = int(rng.random() * 1024) - 1024 * kingdom.valhalla_visit_count
        if best_score is None or score > best_score:
            best_score = score
            best_kingdom_id = kingdom.kingdom_id
    return best_kingdom_id


def select_valhalla_fallback_recipient(state: GameState, rng: random.Random) -> int | None:
    """The source's own confirmed fallback, "``viskng = IRand MOD king_
    count``", reached when ``select_ordinary_valhalla_recipient()``
    finds no candidate at all (Phase 756).

    **A documented, rulebook-over-disassembly interpretation, not a
    literal port**: the source's own pseudocode ignores alignment
    entirely at this point, which read literally could select a
    Divine/Undead King -- but this project's own primary source,
    ``Desktop/VALHALLA.txt`` rule 5, states plainly "I re Non-Morti e
    Divini... non ricevono visite dal Vahlalla" (do not receive
    visits). Resolved in the rulebook's favor: this still draws only
    from Kingdoms whose alignment is one of the 5 rotation-eligible
    ones (``GATE_ANGEL_ELIGIBLE_ALIGNMENTS``), uniformly, just without
    the per-King score/repeat-ban filters -- not literally any Kingdom
    in the game.

    Returns ``None`` only if no such Kingdom exists at all (e.g. an
    empty test fixture).
    """

    candidates = sorted(k.kingdom_id for k in state.kingdoms.values() if k.alignment in GATE_ANGEL_ELIGIBLE_ALIGNMENTS)
    if not candidates:
        return None
    return candidates[int(rng.random() * len(candidates))]


def finalize_ordinary_valhalla_visit(
    state: GameState, rng: random.Random, *, board_width: int | None = None
) -> LeaderState | None:
    """Phase 756 -- the ordinary, per-turn automatic Valhalla visit,
    independent of Gate Angel. ``Desktop/VALHALLA.txt`` rule 1: "Ciascun
    allineamento da Buono a Malvagio... riceverà una visita una volta
    ogni cinque turni" -- an unconditional, per-turn guarantee, not
    contingent on anyone casting the secret Gate Angel spell.

    **"Only one visitor per turn" (``VALHALLA.txt`` rule 2)**: returns
    ``None`` immediately if a Gate-Angel-triggered visit already
    happened this turn (``state.last_gate_angel_turn == state.turn_
    number``) -- Gate Angel's own forced pick always wins over the
    ordinary rotation for that turn; this function is only ever the one
    that actually spawns a visitor when nobody cast Gate Angel.

    Calling ``gate_angel_due_alignment()`` here (idempotent, cached per
    ``turn_number``) is what guarantees the rotation itself advances
    even in a turn with zero Gate Angel casts anywhere in the game --
    see that function's own Phase 756 addendum.

    ``board_width`` (Phase 780, default ``None``) falls back to ``state.
    board_width``.
    """

    board_width = board_width if board_width is not None else state.board_width
    if state.last_gate_angel_turn == state.turn_number:
        return None

    alignment = gate_angel_due_alignment(state, rng)
    kingdom_id = select_ordinary_valhalla_recipient(state, alignment, rng)
    if kingdom_id is None:
        kingdom_id = select_valhalla_fallback_recipient(state, rng)
        if kingdom_id is None:
            return None
        fallback_alignment = state.kingdoms[kingdom_id].alignment
        if fallback_alignment in GATE_ANGEL_ELIGIBLE_ALIGNMENTS:
            # The source's own confirmed detail: the fallback still marks
            # the *actually drawn* King's own real alignment as used this
            # cycle, not the turn's own originally-due one.
            state.gate_angel_cycle_visited.add(fallback_alignment)
        alignment = fallback_alignment

    visitor = _spawn_valhalla_visitor(state, kingdom_id, alignment, rng, board_width)
    if visitor is not None:
        _record_valhalla_visit(state, kingdom_id)
    return visitor


def _reassign_visitor_armies(state: GameState, kingdom_id: int, location, board_width: int) -> None:
    """Phase 548 -- ``VALHALLA.txt`` rule 5: "Vahlalla visitor can lead
    armies, but when Vahlalla visitor returns to Valhalla, the armies
    will normally be left leaderless... transferred to your lowest-
    numbered leader in the same province, or at last resort, the
    garrison commander in an adjacent province owned by you. If no
    leader is available, the armies will be disbanded." No existing
    helper implements this chain (confirmed by research) -- this
    project has no modeled "garrison commander" attribute at all
    (``models/game_state.py ArmyState.commanded_by``'s own comment:
    "an army may also be unled, under the rulebook's 'garrison
    commander'" -- a concept, not a field), so "an adjacent province's
    own garrison commander" is read the same honest way as ``LeaderState.
    is_king``-first ordering below: the lowest-``leader_id`` same-
    Kingdom leader physically present there. Rule 5's own King-first
    wording isn't explicit, but every other departure rule already
    routes to the King first (rule 2's item hand-off) -- reused here for
    consistency rather than treating "lowest-numbered leader" as if it
    always meant a non-King.
    """

    armies = state.armies_commanded_by(VALHALLA_VISITOR_LEADER_ID)
    if not armies:
        return

    king = find_king_of_kingdom(state, kingdom_id)
    new_commander_id = king.leader_id if king is not None else None

    if new_commander_id is None:
        # Phase (bug fix): "your lowest-numbered leader in the same
        # province" -- this must be scoped to `kingdom_id`, the same way
        # the King branch above and the adjacent-province branch below
        # already are. Without this filter, a co-located leader of ANY
        # Kingdom (including a hostile one sharing the province during an
        # active encounter) could inherit command of the departing
        # visitor's armies, leaving `army.kingdom_id` (still `kingdom_id`)
        # and `army.commanded_by`'s own real owner permanently
        # inconsistent -- reproduced directly: a co-located foreign leader
        # with no same-Kingdom leader present ended up commanding an army
        # whose own `kingdom_id` never changed to match.
        co_located = sorted(
            (
                leader
                for leader in state.leaders_at(location)
                if leader.leader_id != VALHALLA_VISITOR_LEADER_ID and leader.kingdom_id == kingdom_id
            ),
            key=lambda leader: leader.leader_id,
        )
        if co_located:
            new_commander_id = co_located[0].leader_id

    if new_commander_id is None:
        bounds = MapBounds(board_width, state.board_height)
        for neighbor_coord in neighbors(location, bounds):
            province = state.provinces.get(neighbor_coord)
            if province is None or province.owner_kingdom_id != kingdom_id:
                continue
            candidates = sorted(
                (leader for leader in state.leaders_at(neighbor_coord) if leader.kingdom_id == kingdom_id),
                key=lambda leader: leader.leader_id,
            )
            if candidates:
                new_commander_id = candidates[0].leader_id
                break

    for army in armies:
        if new_commander_id is not None:
            army.commanded_by = new_commander_id
        else:
            # "the armies will be disbanded" -- same mutation turn/
            # plan_dispatch.py _dispatch_disband() itself performs.
            army.kingdom_id = None
            army.commanded_by = None


def process_valhalla_departure(state: GameState, *, board_width: int | None = None) -> None:
    """Phase 548 -- resolves the Valhalla visitor's own departure, once
    their one active turn (``LeaderState.valhalla_active_turn``, Phase
    546) has passed. Called from ``run_turn()``'s own end-of-turn tail,
    immediately after ``finalize_gate_angel_visit()`` -- see that
    function's own Phase 548 addendum for why a stale occupant is also
    routed through here before a new visitor is ever spawned.

    **Peaceful departure** (the visitor is still alive in ``state.
    leaders``): rule 5's army hand-off (``_reassign_visitor_armies()``)
    plus rule 2's own item hand-off -- every item still held by the
    visitor (their own fixed item, and any Search-loot magic item not
    already Given away -- rule 2 covers both the same way) transfers to
    the Kingdom's own King. No King on record: the items simply stay
    with the now-removed leader id, an honest edge case (this project
    has no alternative recipient named by any source for this specific
    case, unlike the army hand-off's own documented fallback chain).
    Leader 199 is then removed from ``state.leaders`` entirely -- a
    fresh hero only replaces them on the next successful Gate Angel
    cast.

    **Death departure** (the visitor died this turn -- ``GameState.
    remove_leader()`` already popped them into ``state.dead_leaders``,
    which preserves the full archived ``LeaderState``, Valhalla fields
    included, before this tail even runs): rule 7's own "l'oggetto
    sparisce" -- only the fixed item specifically is dropped (removed
    from ``state.items`` outright, given to nobody). Any other item the
    visitor happened to hold is left alone -- a real Search/Challenge/
    Pursue combat death already runs ``turn/encounter.py loot_defeated_
    leader()``, which transfers everything to the winner before this
    tail ever sees it, and Kill_Enemy (this project's other real leader-
    death spell) is itself blocked by Phase 547's own spell immunity --
    so no other death path exists to invent handling for. Armies still
    ``commanded_by`` the now-dead visitor are reassigned exactly like
    the peaceful case (death doesn't release army command on its own --
    confirmed via ``GameState.remove_leader()``'s own docstring, which
    never touches ``ArmyState``).

    ``board_width`` (Phase 780, default ``None``) falls back to ``state.
    board_width``.
    """

    board_width = board_width if board_width is not None else state.board_width
    visitor = state.leaders.get(VALHALLA_VISITOR_LEADER_ID)
    if visitor is not None and visitor.valhalla_active_turn == state.turn_number:
        _reassign_visitor_armies(state, visitor.kingdom_id, visitor.location, board_width)
        king = find_king_of_kingdom(state, visitor.kingdom_id)
        if king is not None:
            for item in state.items_held_by(VALHALLA_VISITOR_LEADER_ID):
                state.transfer_item(item.item_id, king.leader_id)
        del state.leaders[VALHALLA_VISITOR_LEADER_ID]
        return

    dead = state.dead_leaders.get(VALHALLA_VISITOR_LEADER_ID)
    if dead is not None and dead.valhalla_active_turn == state.turn_number:
        if dead.kingdom_id is not None:
            _reassign_visitor_armies(state, dead.kingdom_id, dead.location, board_width)
        if dead.valhalla_fixed_item_id is not None:
            state.items.pop(dead.valhalla_fixed_item_id, None)
