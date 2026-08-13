"""``ACost``/``LCost`` aggregation -- a kingdom's total expected per-turn
upkeep, the FINANCES section's "Expected Expenses" line -- Phase 276.

**Both identifiers are called but never *defined* anywhere in the 13
available ``.PAS`` files** (``describe_finances_report()``'s own Phase 275
audit note, ``report/turn_report.py compose_letter_report()``). This
module's combination formula is project-original in the same sense
``turn/tax_base.py compute_tax_base()`` already is for the FINANCES
section's other unsourced-formula line -- flagged per this project's own
standing rule for confirmed-absent design choices -- but each of the two
*inputs* below is independently sourced and, unlike ``Tax_Base``'s own
per-province figure, was verified directly against real generated turn
reports rather than only against a Pascal source citation.

**Army maintenance (``ACost``), verified exact against four real
``SE3__T*.K*`` sample files (user-supplied, 2026-07-29)**: for every
"Hired" army a kingdom owns (``ArmyState.kingdom_id == kingdom_id`` --
independent mercenaries, listed separately in the real ARMIES table, are
never a kingdom's own upkeep), sum ``ARMY_TABLE[army_type].pay``
(``models/army_type.py``, RULES.AK [6.3]'s own "Pay" column, that
module's own docstring already labels "recruit/maintenance cost" even
though only recruit pricing had a real consumer before this phase). Cross-
checked against ``SE3__T0.K2``/``K3``/``K5``/``T1.K2``: subtracting each
file's own printed per-leader "Ini" pay total (see below) from its own
printed "Expected Expenses" always leaves exactly the sum of ``pay``
across that kingdom's own Hired armies, with zero discrepancy across all
four files -- Legion(2)+Legion(2)+Lt_Cavalry(2)=6, Legion(2)+Legion(2)+
Hvy_Cavalry(3)=7, and a six-army 13-gold case, all reproduced exactly.

**Leader maintenance (``LCost``), reuses ``turn/hire_pay.py
required_pay()`` rather than a new formula.** Rulebook [3.5]: "The Hero
is paid when he signs up and at the end of each gameturn" -- the *same*
gold figure a King agreed to at Hire time recurs every turn thereafter.

**Phase 505 supersedes the earlier alignment+temper approximation with
the real, disassembly-sourced formula** (``turn/hire_pay.py``'s own
module docstring) -- which also *explains*, rather than merely observes,
the one real-sample mismatch this section used to flag (Garin, Pagan/
Brave/Dwarf under a Neutral/Brave/presumably-Human King: the old formula
predicted 2, the real sample showed 1): race only matters when the
Hero's own hidden ``borny & 1`` bit enables it, exactly the kind of
"sometimes race matters, sometimes it doesn't" behavior the old
always/never race-blind formula could never reproduce. The real formula
also adds a genuine, deterministic per-leader-index ``bias`` term this
project's own leader ids have no relationship to a specific historical
game's own internal indices -- so the *exact* real-sample values
(Adele/Indra's own real prices in a specific historical game) can no
longer be asserted from this project's own synthetic fixtures the way
the old, bias-free approximation happened to allow; what the tests below
verify instead is the formula's own structural correctness (its
distance ladder, its personal-bit gates, its conquest surcharge), with
worked numeric examples matching ``turn/hire_pay.py``'s own tests.

**A leader's own upkeep is 0, not ``required_pay()``'s own result, in
two structural cases**, both confirmed directly from the sample data
(every King's own row always prints an "Ini" of 0; a Valhalla-visiting
Hero -- e.g. ``SE3__T0.K3``'s own "Kitralus" -- prints 0 despite a real
Alignment/Temperament match that would otherwise price non-zero):
- The King himself (``LeaderState.is_king``) -- a King doesn't pay
  himself a salary; calling ``required_pay(king, king)`` on the King's
  own row would incorrectly return a nonzero "matches itself" price, so
  this is checked explicitly rather than left to fall out of the
  formula.
- The Valhalla visitor (``leader_id == VALHALLA_VISITOR_LEADER_ID``,
  ``models/valhalla.py``) -- a temporarily-summoned guest, not a hired
  Hero at all; nothing in the available source states this explicitly,
  but it's the only reading consistent with the sample data, the same
  "structurally obvious, not merely unstated" reasoning this project
  already applies elsewhere (e.g. ``turn/search_execution.py``'s own
  "a dead leader can't scout" note).

**Phase 280** extracts this per-leader logic into its own ``leader_pay()``
function so `report/turn_report.py describe_characters_report()`'s own
"Pay" column (the real table's own "Ini" header) can reuse the identical
formula and King/Valhalla-visitor exclusions, rather than the CHARACTERS
composer re-deriving them.

**Phase 404 -- ``apply_turn_maintenance()``, the real treasury debit.**
Through Phase 280, ``compute_expected_expenses()`` only ever fed a
report line -- nothing in this project actually subtracted it from
``KingdomState.treasury``, even though rulebook [3.5] ("The Hero is
paid ... at the end of each gameturn") and [6.3]'s own Pay column both
describe a real, recurring cost, not merely a forecast. Wired here at
the user's own direct request, once per ``turn/turn_processor.py
run_turn()`` call -- both halves together (``ACost`` armies, ``LCost``
leaders), not leader pay alone, so a kingdom's treasury never "forgets"
to pay for its armies while genuinely paying its Heroes.

**Deliberately unclamped**: ``KingdomState.treasury`` can go negative.
No bankruptcy/default consequence (forced disbanding, blocked Hires,
...) is modeled -- nothing in the available source describes one, and
this project's standing policy is to leave a genuinely unsourced
consequence undocumented rather than invent one, the same restraint
Phase 162 already applied to the required-pay formula itself.
"""

from __future__ import annotations

from ak_engine.models.army_type import ARMY_TABLE
from ak_engine.models.game_state import GameState, LeaderState
from ak_engine.models.valhalla import VALHALLA_VISITOR_LEADER_ID
from ak_engine.turn.hire_pay import required_pay


def compute_army_maintenance(state: GameState, kingdom_id: int) -> int:
    """``ACost(kingdom_id)``: the sum of ``ARMY_TABLE[army_type].pay``
    across every Hired army this kingdom owns -- see module docstring for
    the real-sample cross-check.
    """

    return sum(
        ARMY_TABLE[army.army_type].pay
        for army in state.armies.values()
        if army.kingdom_id == kingdom_id
    )


def leader_pay(state: GameState, leader: LeaderState, king: LeaderState | None) -> int:
    """One leader's own real recurring per-turn pay ("Ini" in the real
    CHARACTERS table) -- 0 for the King himself or a Valhalla visitor,
    otherwise ``required_pay()``. Extracted (Phase 280) so both this
    module's own ``compute_leader_maintenance()`` sum and `report/
    turn_report.py describe_characters_report()`'s own "Pay" column
    share the identical exclusion logic instead of duplicating it.
    """

    if leader.is_king or leader.leader_id == VALHALLA_VISITOR_LEADER_ID:
        return 0
    return required_pay(state, leader, king)


def compute_leader_maintenance(state: GameState, kingdom_id: int) -> int:
    """``LCost(kingdom_id)``: the sum of ``leader_pay()`` across every
    leader this kingdom owns -- see module docstring for the real-sample
    cross-check and the one known mismatch (now exactly explained, not
    just observed, by ``turn/hire_pay.py``'s own Phase 505 real formula).
    """

    king = next(
        (leader for leader in state.leaders.values() if leader.kingdom_id == kingdom_id and leader.is_king),
        None,
    )
    return sum(
        leader_pay(state, leader, king) for leader in state.leaders.values() if leader.kingdom_id == kingdom_id
    )


def compute_expected_expenses(state: GameState, kingdom_id: int) -> int:
    """``ACost(kingdom_id) + LCost(kingdom_id)``: the FINANCES section's
    "Expected Expenses" line -- see module docstring.
    """

    return compute_army_maintenance(state, kingdom_id) + compute_leader_maintenance(state, kingdom_id)


def apply_turn_maintenance(state: GameState) -> dict[int, int]:
    """Debits every kingdom's own ``compute_expected_expenses()`` from its
    treasury, once per turn -- see module docstring's Phase 404 section
    for why this was a display-only figure through Phase 280 and what's
    deliberately not modeled (bankruptcy consequences, clamping).

    Returns the amount debited per kingdom, keyed by ``kingdom_id`` --
    callers/tests that want to verify a specific debit don't need to
    re-derive ``compute_expected_expenses()`` themselves.
    """

    debited: dict[int, int] = {}
    for kingdom_id, kingdom in state.kingdoms.items():
        amount = compute_expected_expenses(state, kingdom_id)
        kingdom.treasury -= amount
        debited[kingdom_id] = amount
    return debited
