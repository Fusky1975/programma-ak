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
required_pay()`` (Phase 162/163/264) rather than a new formula.**
Rulebook [3.5]: "The Hero is paid when he signs up and at the end of
each gameturn" -- the *same* gold figure a King agreed to at Hire time
recurs every turn thereafter, so the Hire-time formula this project
already built from the real manual text is the natural, already-sourced
source for the recurring figure too, not a new guess. Verified against
three of four real Heroes in the same sample files, using each Hero's
own printed Alignment/Temperament against their King's: Adele (Good/
Brave under a Good/Caut King, distance 0) -> 1 gold, matches; Indra
(Good/Caut, same King, distance 0, same temper) -> 1 gold, matches;
Samantha (Pagan/Brave under a Neutral/Brave King, distance 1, same
temper) -> 2 gold, matches. **One real case does not match**: Garin
(Pagan/Brave, Dwarf) under a Neutral/Brave, presumably-Human King --
``required_pay()`` predicts 2 gold, the real sample shows 1. Rulebook
[3.5] itself names a third factor this formula has always deliberately
omitted: "It helps if the Hero has the same temper, same race and
similar alignment" -- at the time ``required_pay()`` was designed,
``LeaderState`` had no ``.race`` field to source race from at all (that
module's own docstring says so); it does now (Phase 87-era), so a race
term is very plausibly the missing piece, but nailing its exact shape
needs more real data points than the one available mismatch -- **not
attempted here, on the user's own explicit direction (2026-07-29): wire
Expected Expenses now with ``required_pay()`` exactly as it stands,
documented as not yet historically exact in every case, rather than
block the whole line on a still-underdetermined refinement.**

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
"""

from __future__ import annotations

from ak_engine.models.army_type import ARMY_TABLE
from ak_engine.models.game_state import GameState
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


def compute_leader_maintenance(state: GameState, kingdom_id: int) -> int:
    """``LCost(kingdom_id)``: the sum of ``required_pay()`` across every
    leader this kingdom owns, with the King and any Valhalla visitor
    always contributing 0 -- see module docstring for the real-sample
    cross-check and the one known mismatch.
    """

    king = next(
        (leader for leader in state.leaders.values() if leader.kingdom_id == kingdom_id and leader.is_king),
        None,
    )
    total = 0
    for leader in state.leaders.values():
        if leader.kingdom_id != kingdom_id:
            continue
        if leader.is_king or leader.leader_id == VALHALLA_VISITOR_LEADER_ID:
            continue
        total += required_pay(leader, king)
    return total


def compute_expected_expenses(state: GameState, kingdom_id: int) -> int:
    """``ACost(kingdom_id) + LCost(kingdom_id)``: the FINANCES section's
    "Expected Expenses" line -- see module docstring.
    """

    return compute_army_maintenance(state, kingdom_id) + compute_leader_maintenance(state, kingdom_id)
