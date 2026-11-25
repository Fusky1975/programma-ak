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

**Army maintenance stays deliberately unclamped**: ``KingdomState.
treasury`` can still go negative from ``ACost`` alone. Nothing in the
available source describes an army-side bankruptcy/default consequence,
and this project's standing policy is to leave a genuinely unsourced
consequence undocumented rather than invent one, the same restraint
Phase 162 already applied to the required-pay formula itself.

**Phase 527 addendum -- Hero maintenance is no longer unclamped.**
The paragraph above used to say the same "no consequence modeled" for
*every* shortfall, leader pay included -- that was true only because no
source had been found yet. ``AKGEN_reverse_engineering_report (3).md``
SS28.1 ("Mancato pagamento e diserzione") gives the real compiled
consequence, disassembled from ``AK.EXE:0x1450D-0x14612``: when the
per-turn payment helper can't fund a specific Hero's own ``LCost``, the
engine rolls

    r = (IRand and 3) - 2       ; -2, -1, 0, +1, each 25%
    if r >= like(hero, king):
        hero deserts -- lliege := noleader, lstate := Mercenary
    else:
        hero stays unpaid this turn ("in standby"), no consequence

reusing the identical ``like`` value ``turn/hire_pay.py required_pay()``
already computes (now exposed as ``hero_liking()``), not a separate
roll. Desertion probability by ``like``: `+2` -> 0%, `+1` -> 25%, `0` ->
50%, `-1` -> 75%, `-2` -> 100% -- a Hero the King barely tolerates
almost always walks the moment a payment is missed; one he likes a lot
essentially never does.

``apply_turn_maintenance()`` below now pays each non-King, non-Valhalla
leader *individually*, in ascending ``leader_id`` order (the dossier
names no real ordering rule; ascending id is this project's own
established "no rule given" tie-break, e.g. Phase 451's own vote-order
convention) -- as soon as a kingdom's own running treasury can't cover
one Hero's own pay, that Hero rolls for desertion/standby instead of
being paid, and every later Hero in the same kingdom is evaluated
against whatever treasury remains (typically already empty, so they
roll too). Army maintenance (``ACost``) is still paid as one unconditional
lump sum first, unaffected by this per-Hero mechanic -- no source
describes armies deserting for unpaid ``ACost``.
"""

from __future__ import annotations

import random
from ak_engine.models.army_type import ARMY_TABLE
from ak_engine.models.game_state import GameState, LeaderState, MaintenanceResult
from ak_engine.models.valhalla import VALHALLA_VISITOR_LEADER_ID
from ak_engine.turn.combat import Quality
from ak_engine.turn.hire_pay import hero_liking, required_pay
from ak_engine.turn.leader_queries import find_king_of_kingdom, release_armies_to_garrison

# Phase 527: AKGEN_reverse_engineering_report (3).md SS28.1's own
# "(IRand and 3) - 2" -- 4 equally-likely values, -2..+1.
_DESERTION_ROLL_VALUES = (-2, -1, 0, 1)


def compute_army_maintenance(state: GameState, kingdom_id: int) -> int:
    """``ACost(kingdom_id)``: the sum of ``ARMY_TABLE[army_type].pay``
    across every Hired army this kingdom owns -- see module docstring for
    the real-sample cross-check.

    Phase 1054 bug fix: this used to index ``ARMY_TABLE[army.army_type]``
    with no guard. 8 real ``ArmyType`` ordinals (Vampires, Marauders,
    Shamans, Crossbow, Javelins, Artillery, Spiders, D_Turtle --
    ``models/army_type.py``'s own Phase 383 addendum) never appear in
    the rulebook's own Army Type Table [6.3], so ``ARMY_TABLE`` has no
    entry for them -- ``turn/recruit.py resolve_recruit()``'s own "Bug
    fix (crash)" comment already documents and guards this exact same
    lookup for the recruit-time path, but that guard only stops these
    types from being recruited *through* ``execute_recruit()``; it
    doesn't stop one from already existing in ``state.armies`` by other
    means (e.g. the GM army editor, which applies no ``ARMY_TABLE``
    filtering). Without this guard, a kingdom owning any such army
    crashed every subsequent turn's maintenance computation with an
    unhandled ``KeyError``. Treated the same honest "no rulebook data to
    charge maintenance by" gap ``resolve_recruit()`` already treats it
    as -- contributes 0, not a guessed cost.
    """

    return sum(
        ARMY_TABLE[army.army_type].pay
        for army in state.armies.values()
        if army.kingdom_id == kingdom_id and army.army_type in ARMY_TABLE
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

    king = find_king_of_kingdom(state, kingdom_id)
    return sum(
        leader_pay(state, leader, king) for leader in state.leaders.values() if leader.kingdom_id == kingdom_id
    )


def compute_expected_expenses(state: GameState, kingdom_id: int) -> int:
    """``ACost(kingdom_id) + LCost(kingdom_id)``: the FINANCES section's
    "Expected Expenses" line -- see module docstring.
    """

    return compute_army_maintenance(state, kingdom_id) + compute_leader_maintenance(state, kingdom_id)


def promote_recruits_and_depleted_armies(state: GameState, kingdom_id: int) -> list[int]:
    """[6.1]: "Le unità militari Reclute o Demoralizzate passano sempre al livello successivo alla
    fine del turno (solo se pagate regolarmente però)" -- Depleted becomes Green and Green becomes
    Average, automatically, for every army of a kingdom whose army upkeep the treasury covered. A
    freshly levied Green unit is therefore Average again by the next turn. Returns the promoted
    army ids. (Audit of 2026-11-24: this rule had no turn-boundary hook anywhere.)"""

    promoted: list[int] = []
    for army in state.armies.values():
        if army.kingdom_id != kingdom_id or army.is_mercenary:
            continue
        if army.quality is Quality.DEPLETED:
            army.quality = Quality.GREEN
        elif army.quality is Quality.GREEN:
            army.quality = Quality.AVERAGE
        else:
            continue
        promoted.append(army.army_id)
    return promoted


def apply_turn_maintenance(state: GameState, rng: random.Random | None = None) -> dict[int, MaintenanceResult]:
    """Debits every kingdom's own per-turn upkeep from its treasury, once per
    turn -- see module docstring's Phase 404 section for the original
    lump-sum design and its own Phase 527 addendum for the real per-Hero
    payment/desertion mechanic this now implements.

    Each non-King, non-Valhalla-visitor leader's own pay is attempted
    individually, in ascending ``leader_id`` order, against the treasury
    ([9.2]: "Si pagano prima gli Eroi, quindi le unita' militari" -- the
    Heroes come first, user audit 2026-11-26), then army maintenance
    (``ACost``) is paid as one unconditional lump sum, unclamped; a leader whose own pay the treasury
    can no longer cover rolls for desertion/standby (``hero_liking()``
    plus a fresh ``(IRand and 3) - 2`` roll) instead of being paid.

    Returns one ``MaintenanceResult`` per kingdom, keyed by ``kingdom_id``
    -- and (Phase 771, mirroring ``turn/tax_base.py apply_turn_revenue()``'s
    own ``state.turn_revenue_credited`` convention) also stores that same
    dict onto ``state.turn_maintenance_by_kingdom``, so `report/turn_
    report.py describe_finances_report()` can narrate `_LLCosts`/
    `_LACosts` without this function's own return value having to be
    threaded through the call chain.
    """

    rng = rng if rng is not None else random.Random()
    results: dict[int, MaintenanceResult] = {}
    for kingdom_id, kingdom in state.kingdoms.items():
        debited = 0

        king = find_king_of_kingdom(state, kingdom_id)
        heroes = sorted(
            (
                leader
                for leader in state.leaders.values()
                if leader.kingdom_id == kingdom_id
                and not leader.is_king
                and leader.leader_id != VALHALLA_VISITOR_LEADER_ID
            ),
            key=lambda leader: leader.leader_id,
        )

        deserted: list[int] = []
        standby: list[int] = []
        for hero in heroes:
            cost = required_pay(state, hero, king)
            # Missing King data defaults permissively (same convention as
            # turn/hire_pay.py's own required_pay()) -- no King recorded
            # means no `like()` to roll against, so pay unconditionally
            # rather than guessing a desertion outcome.
            if king is None or kingdom.treasury >= cost:
                kingdom.treasury -= cost
                debited += cost
                continue
            like = hero_liking(state, hero, king)
            roll = rng.choice(_DESERTION_ROLL_VALUES)
            if roll >= like:
                if hero.race is None:
                    hero.race = kingdom.race  # a hero with no kingdom keeps the race he served under
                hero.kingdom_id = None
                release_armies_to_garrison(state, hero.leader_id)  # he leaves alone, the Kingdom keeps the armies
                deserted.append(hero.leader_id)
            else:
                standby.append(hero.leader_id)

        # [9.2] "Si pagano prima gli Eroi, quindi le unita' militari": the armies' upkeep comes out of what the
        # Heroes left (still one unconditional lump sum, unclamped).
        army_upkeep = compute_army_maintenance(state, kingdom_id)
        kingdom.treasury -= army_upkeep
        debited += army_upkeep
        if kingdom.treasury >= 0:
            promote_recruits_and_depleted_armies(state, kingdom_id)

        results[kingdom_id] = MaintenanceResult(
            debited=debited, deserted_leader_ids=deserted, standby_leader_ids=standby
        )
    state.turn_maintenance_by_kingdom = results
    return results
