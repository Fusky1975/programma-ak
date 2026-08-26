"""[8.4] Scientific Treaties -- RULES.AK, quoted below. This is the
second, Kingdom-level effect of a "Treat" order -- Phase 261's own
``GameState.treat_permissions`` docstring already flagged the first
([3.4]'s Recruit-in-ally-territory permission gate).

    [8.4]  Scientific Treaties
      To exchange Sage discoveries, players need to have become Allies on a
    previous gameturn.  From then on, a mutual "Treat" order is interpreted as a
    scientific exchange.  The only requirement is that at the end of the turn, the
    2 Kingdoms are adjacent, or else a character from one Kingdom must be inside
    the other Kingdom.  The two nations will exchange 1 secret for each mutual
    Treat order.  Generally speaking, the secrets exchanged are the most military-
    oriented ones.  The exchange takes place after finances are computed.  The
    discoveries listed in your turn report will be shown in the order of their
    priority for scientific exchanges.  If only one of the Kingdoms has a secret
    unknown to the other, one secret will still be given away.

**Why this was previously marked blocked, and what unblocks it now**:
earlier surveys of this gap flagged the underlying "Treat" order itself
as unparseable -- true, and still true (same "no real order-file shape
ever seen" category as Break Treaty/Call-For-Vote, ``turn/
emperor_election.py``'s own docstring) -- but Phase 261 already solved
the identical problem for [3.4]'s own half of the same order:
``GameState.treat_permissions`` is populated directly by the caller,
not decoded from a move file. [8.4] reuses that exact field -- a
*mutual* Treat order is just ``(a, b)`` and ``(b, a)`` both present in
``treat_permissions`` in the same gameturn -- rather than inventing a
second, parallel permission model for what the rulebook itself
describes as one order with two effects.

**"Have become Allies on a previous gameturn"**: this project has no
alliance-formation timestamp anywhere. ``GameState.allied_kingdoms``
(like ``treat_permissions``) is a bare set with no in-project mechanism
that ever adds to it -- the "Ally" order itself is equally unparsed --
it is entirely populated by the caller ahead of time, with no record of
*when* an alliance began. Distinguishing "became allied last turn" from
"became allied this turn" is therefore not information this engine has
anywhere to read, so this precondition checks *current*
``is_allied()`` status only, not its duration -- a documented
limitation, not a silent guess, the same spirit as ``treat_
permissions``'s own "caller's job" convention.

**Adjacency-or-presence** ("the 2 Kingdoms are adjacent, or else a
character from one Kingdom must be inside the other Kingdom"): read
literally as *either* (a) some province Kingdom A owns is hex-adjacent
to some province Kingdom B owns (``turn/movement.py is_adjacent()``,
the same primitive every other adjacency check in this project already
uses), *or* (b) at least one of Kingdom A's own leaders is physically
located in a province Kingdom B owns, or vice versa -- "inside the
other Kingdom" read as "inside a province that Kingdom owns," the same
reading ``GameState.friendly_provinces_for()`` already gives
"territory."

**Exchange priority** ("the most military-oriented ones" / "the order
of their priority for scientific exchanges"): ``models/discovery.py
sorted_kingdom_discoveries()`` (Phase 268) already sorts a kingdom's
own discoveries by descending ``DISCOVERY_DISPLAY_VALUE`` -- the real,
sourced ``discval`` field ``CTBOTH.PAS`` uses for exactly one purpose,
this same "Discoveries of the Sages" report ordering. Since the
rulebook text explicitly says the report's own ordering *is* the
scientific-exchange priority ordering, ``sorted_kingdom_discoveries()``
is reused directly rather than inventing a second, unsourced
military-ness ranking -- the highest-priority Discovery the *other*
Kingdom doesn't already hold is the one given away, independently for
each direction.

**"If only one Kingdom has a secret unknown to the other, one secret
will still be given away"**: this falls out naturally from computing
each direction's exchange independently rather than needing a special
case -- read as a clarification that a lopsided exchange still
happens, not as a description of a separate mechanic.

**No Merit Point credit**: the rulebook's own printed Chancellor Merit
Point table (``turn/merit_points.py``'s own module docstring) lists
three specific Discovery-attribution sources -- personal invention
(first or not) and "obtained via espionage" -- and Scientific Treaty
exchange is none of the three. ``MeritTally.discoveries_via_espionage``
is deliberately not touched here despite the superficial "received a
Discovery you didn't invent" similarity: that field is scoped to
espionage specifically (``turn/aspy_execution.py``'s own Phase 267
note, "+1 per Invention obtained via espionage"), and folding a
mutually-agreed ally exchange into it would misrepresent both.
``GameState.discoveries_first_found_by`` is likewise untouched -- a
Kingdom receiving a Discovery via Treaty didn't invent it, so it can
never become that Discovery's own first-finder, mirroring exactly how
an espionage-obtained Discovery already behaves (``turn/
practice_execution.py``'s own SAGE branch is the only writer of that
registry).

**Phase 643 -- exchange attribution now recorded**: `REPORTS.PAS`'s
own "Discoveries of the Sages" list (`Rep_Econ`, lines 348-392) prints
"(Received from player(s) #k1... by scientific treaty)"/"(Sent to
player(s) #k1... by scientific treaty)" for a Discovery whose real
`kexch[giver,receiver]` entry names this exchange -- confirmed to be
*only* about this mechanic (the text is unconditionally "by scientific
treaty"), not espionage. `execute_scientific_treaties()` now writes
`GameState.discovery_exchanged_from[(giver_id, receiver_id)]` alongside
each `KingdomState.discoveries.add(...)` call -- see that field's own
docstring for the exact shape and the real "single value per directed
pair" limitation it reproduces. Rendered by `report/turn_report.py
describe_finances_report()`.

**No ``turn_processor.py`` wiring**: "The exchange takes place after
finances are computed" describes a sequencing point this project has
no equivalent hook for -- ``turn/tax_base.py``'s own revenue/
``Inv_Bonus`` formulas are computed on demand for report rendering,
never applied as a mutating step inside ``turn/turn_processor.py
run_turn()`` itself (there is no "apply this turn's revenue to the
treasury" phase to sequence after). ``execute_scientific_treaties()``
is therefore a standalone resolver the caller invokes directly,
alongside their own end-of-turn financial step -- the same "caller's
job" convention ``treat_permissions`` itself established, not a gap.

**Phase 474 -- the real alignment-distance success gate (``AKGEN_
reverse_engineering_report (2).md`` SS4.5/SS18.3, real disassembly
source)**: the rulebook text quoted above says nothing about the
exchange ever *failing* once the adjacency/contact preconditions hold
-- this module originally modeled it as unconditional. The disassembly
source corrects that: "superamento del controllo d'allineamento: stessa
classe senza penalità, altrimenti probabilità ridotta di 40 punti
percentuali per ogni passo di distanza" (passing the alignment check:
same class, no penalty; otherwise the probability is reduced by 40
percentage points per step of distance) -- i.e. ``P = max(0, 1 -
0.40*distance)``, rolled **once per Kingdom pair** (gating the whole
pair's own exchange opportunity this turn, not each direction
separately -- SS18.3 frames it as one of the "normal scientific treaty
rules" a *pair* must satisfy before *any* exchange happens, alongside
adjacency/contact, not as a separate per-direction hurdle). "The two
Kings" ``distance`` reuses ``turn/hire_pay.py``'s own established
proxy, ``KingdomState.alignment`` (not ``LeaderState.alignment``,
which is usually unrecorded for a King) -- the same "a King's own real
alignment" convention that module's own docstring already documents.
Distance 0 needs no roll at all (``P=1.0`` -- the gate can never fail),
so every pre-Phase-474 test fixture (all same-alignment Kingdoms)
stays exactly as deterministic as before.

**Long-Range Trade Routes** (Advanced Ability, Phase 511 -- quoted
directly from ``models/advanced_ability.py ADVANCED_ABILITY_DESCRIPTION
[EXPLORERS_LONG_RANGE_TRADE_ROUTES]``): "for each explorer of this
level employed by your kingdom, you can use the scientific-treaty rule
to trade Sage Inventions with a faraway foreign kingdom, even if your
kingdoms aren't adjacent and no character is there to make the trade."

**Why this was previously marked blocked, and what unblocks it now**:
this module used to say the missing piece was "a genuine per-leader
'which Advanced Ability do you actually have' possession registry this
project has never built" -- true when that was written, but Phase 508
(``worldgen/explorer_ability_level_schedule.py``, the real, doubly-
cross-validated ``spabord[Explorer]`` schedule) and Phase 510 (wiring
that schedule into ``turn/practice_execution.py``'s own Advanced-
Ability-grant path) together built exactly that registry: ``LeaderState.
advanced_abilities`` is now a real, sourced, per-leader possession set
for Explorer's own six Advanced Abilities, not a guess. ``_kingdoms_in_
contact()`` below now checks a third path -- either Kingdom employing at
least one leader who already holds ``EXPLORERS_LONG_RANGE_TRADE_ROUTES``
-- alongside the two original sourced-and-buildable ones (adjacency,
leader presence).

**"For each explorer of this level" -- not modeled as a per-exchange
consumable**: the rulebook's own wording could be read as capping how
many *simultaneous* non-adjacent exchanges a Kingdom's Explorers can
sustain at once (one "slot" per qualifying Explorer). This module has no
existing concept of a per-turn exchange budget anywhere -- every mutual
Treat pair already gets its own independent resolution, with no limit on
how many pairs one Kingdom can simultaneously treaty with -- and
inventing a consumable-slot mechanic to give that phrase teeth would be
exactly the kind of unsourced magnitude this project's "no source, no
guess" policy avoids. Read instead as the qualitative permission this
project *can* build: owning at least one qualifying Explorer unlocks the
adjacency/presence bypass for all of that Kingdom's pairs this turn, not
a counted, exhaustible resource.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from ak_engine.models.advanced_ability import AdvancedAbility
from ak_engine.models.alignment import ALIGNMENT_ORDINAL, Alignment
from ak_engine.models.discovery import Discovery, sorted_kingdom_discoveries
from ak_engine.models.game_state import GameState
from ak_engine.turn.movement import MapBounds, is_adjacent

# AKGEN_reverse_engineering_report (2).md SS4.5/SS18.3: "probabilità
# ridotta di 40 punti percentuali per ogni passo di distanza."
ALIGNMENT_PENALTY_PER_STEP = 0.40


@dataclass(slots=True, frozen=True)
class ScientificTreatyResult:
    """One resolved [8.4] exchange between two Kingdoms with a mutual
    Treat order this gameturn. Either ``discovery_to_a``/``discovery_to_b``
    may be ``None`` (the lopsided-exchange case) but never both -- see
    module docstring.
    """

    kingdom_a_id: int
    kingdom_b_id: int
    discovery_to_a: Discovery | None
    discovery_to_b: Discovery | None


def _mutual_treat_pairs(state: GameState) -> set[frozenset[int]]:
    pairs: set[frozenset[int]] = set()
    for owner_id, recruiter_id in state.treat_permissions:
        if owner_id == recruiter_id:
            continue
        if (recruiter_id, owner_id) in state.treat_permissions:
            pairs.add(frozenset({owner_id, recruiter_id}))
    return pairs


def _kingdom_has_long_range_trade_routes_explorer(state: GameState, kingdom_id: int) -> bool:
    """Phase 511: does ``kingdom_id`` employ at least one leader who
    already holds ``AdvancedAbility.EXPLORERS_LONG_RANGE_TRADE_ROUTES``
    -- see module docstring for why ``LeaderState.advanced_abilities``
    is now a real, sourced registry for this check.
    """

    return any(
        leader.kingdom_id == kingdom_id
        and AdvancedAbility.EXPLORERS_LONG_RANGE_TRADE_ROUTES in leader.advanced_abilities
        for leader in state.leaders.values()
    )


def _kingdoms_in_contact(state: GameState, kingdom_a_id: int, kingdom_b_id: int, bounds: MapBounds) -> bool:
    if _kingdom_has_long_range_trade_routes_explorer(
        state, kingdom_a_id
    ) or _kingdom_has_long_range_trade_routes_explorer(state, kingdom_b_id):
        return True
    provinces_a = [p for p in state.provinces.values() if p.owner_kingdom_id == kingdom_a_id]
    provinces_b = [p for p in state.provinces.values() if p.owner_kingdom_id == kingdom_b_id]
    if any(is_adjacent(pa.coord, pb.coord, bounds) for pa in provinces_a for pb in provinces_b):
        return True
    coords_a = {p.coord for p in provinces_a}
    coords_b = {p.coord for p in provinces_b}
    for leader in state.leaders.values():
        if leader.kingdom_id == kingdom_a_id and leader.location in coords_b:
            return True
        if leader.kingdom_id == kingdom_b_id and leader.location in coords_a:
            return True
    return False


def _highest_priority_unknown(source: set[Discovery], other: set[Discovery]) -> Discovery | None:
    candidates = source - other
    if not candidates:
        return None
    return sorted_kingdom_discoveries(candidates)[0]


def alignment_check_success_chance(kingdom_a_alignment: Alignment, kingdom_b_alignment: Alignment) -> float:
    """AKGEN_reverse_engineering_report (2).md SS4.5/SS18.3 (Phase 474):
    "stessa classe senza penalità, altrimenti probabilità ridotta di 40
    punti percentuali per ogni passo di distanza" -- same alignment class,
    no penalty (1.0); otherwise ``1 - ALIGNMENT_PENALTY_PER_STEP`` per
    step of ``ALIGNMENT_ORDINAL`` distance, floored at 0.0 (never negative).
    """

    distance = abs(ALIGNMENT_ORDINAL[kingdom_a_alignment] - ALIGNMENT_ORDINAL[kingdom_b_alignment])
    return max(0.0, 1.0 - ALIGNMENT_PENALTY_PER_STEP * distance)


def execute_scientific_treaties(
    state: GameState, *, board_width: int, board_height: int, rng: random.Random | None = None
) -> list[ScientificTreatyResult]:
    """Resolve every mutual Treat order between currently-Allied Kingdoms
    in contact this gameturn -- see module docstring for each
    precondition's own sourcing and this project's documented limits.
    """

    rng = rng if rng is not None else random.Random()
    bounds = MapBounds(board_width, board_height)
    results: list[ScientificTreatyResult] = []
    for pair in _mutual_treat_pairs(state):
        kingdom_a_id, kingdom_b_id = sorted(pair)
        if not state.is_allied(kingdom_a_id, kingdom_b_id):
            continue
        kingdom_a = state.kingdoms.get(kingdom_a_id)
        kingdom_b = state.kingdoms.get(kingdom_b_id)
        if kingdom_a is None or kingdom_b is None:
            continue
        if not _kingdoms_in_contact(state, kingdom_a_id, kingdom_b_id, bounds):
            continue
        success_chance = alignment_check_success_chance(kingdom_a.alignment, kingdom_b.alignment)
        if success_chance < 1.0 and rng.random() >= success_chance:
            continue

        discovery_to_b = _highest_priority_unknown(kingdom_a.discoveries, kingdom_b.discoveries)
        discovery_to_a = _highest_priority_unknown(kingdom_b.discoveries, kingdom_a.discoveries)
        if discovery_to_a is None and discovery_to_b is None:
            continue

        if discovery_to_b is not None:
            kingdom_b.discoveries.add(discovery_to_b)
            state.discovery_exchanged_from[(kingdom_a_id, kingdom_b_id)] = discovery_to_b
        if discovery_to_a is not None:
            kingdom_a.discoveries.add(discovery_to_a)
            state.discovery_exchanged_from[(kingdom_b_id, kingdom_a_id)] = discovery_to_a

        results.append(
            ScientificTreatyResult(
                kingdom_a_id=kingdom_a_id,
                kingdom_b_id=kingdom_b_id,
                discovery_to_a=discovery_to_a,
                discovery_to_b=discovery_to_b,
            )
        )
    return results
