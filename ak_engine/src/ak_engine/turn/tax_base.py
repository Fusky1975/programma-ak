"""Tax_Base(kng) aggregation -- a kingdom's total expected per-turn tax revenue.

``Tax_Base`` is called from ``REPORTS.PAS Rep_Econ`` (the FINANCES section's
"Expected Revenues" line) but, like ``ACost``/``LCost``/``Inv_Bonus``, is
never *defined* anywhere in the 13 available ``.PAS`` files -- confirmed
absent, the same citation ``describe_finances_report()``'s own docstring and
``turn/plan_dispatch.py``'s Phase 158 note already established. **This
module's combination formula is therefore project-original, not
transcribed** -- flagged per this project's own standing rule for
confirmed-absent design choices.

What Phase 222-224 changed: this project used to have no per-province base
tax value at all (``describe_provinces_report()``'s own docstring, Phase 220,
still says so). ``parser/gw_world.py``/``gw_world_bridge.py`` now recover the
real ``ptax[px,py]`` value and the real owning kingdom straight from a
``GW3``-family world file, populating ``ProvinceState.tax`` and
``ProvinceState.owner_kingdom_id``. That's exactly the missing input
``Tax_Base`` needed -- what was missing before wasn't a summing formula (that
part's trivial), it was the per-province figure to sum.

Two other fields already exist on ``ProvinceState`` with **no consumer
before this module** (their own docstrings say so explicitly):
``tax_modifier_percent`` (Bless +60% / Earthquake -100%, "for one turn," a
set not an add) and ``scar_terrain_gold_reduction`` (Scar Terrain's -2 gold,
cumulative, permanent). Combining all three into one per-province revenue
figure is this module's own design, in this order:

1. Start from the real base, ``ProvinceState.tax``.
2. Subtract the permanent, cumulative ``scar_terrain_gold_reduction``,
   floored at 0 gold -- Scar Terrain's own rulebook text ("reduced ... When
   the tax base reaches 0 gold") describes a floor, not a value that can go
   negative.
3. Apply the turn's ``tax_modifier_percent`` (``base * (100 + pct) / 100``,
   integer division), floored at 0 gold again -- Earthquake's own "zeroes
   the tax revenue" (-100%) must land on exactly 0, never negative.
4. Subtract the turn's ``earthquake_flat_reduction`` (Phase 270's
   Reinforced Concrete Discovery: a flat 3-gold Earthquake replacement,
   not a percent), floored at 0 gold again.

Permanent damage is applied before the turn's temporary modifier because
Scar Terrain describes an actual, lasting change to the province's own tax
base ("permanently"), while Bless/Earthquake only describe a one-turn
adjustment on top of whatever that base currently is -- no source orders the
two explicitly, this is the natural reading of "permanent" vs. "for one
turn."

**A province with no recorded ``tax`` (``None``, e.g. never bridged from a
real ``GW3`` file) contributes nothing and isn't counted as 0** -- the same
"no data isn't a true zero" stance ``turn/aspy_execution.py``'s own docstring
already took for the identical gap. ``compute_tax_base`` only sums
provinces this kingdom actually owns (``ProvinceState.owner_kingdom_id ==
kingdom_id``), not allied provinces -- ``Tax_Base`` is real Pascal
terminology for one specific kingdom's own revenue, the same single-kingdom
scope ``KingdomState.treasury`` already has, not the broader "friendly"
(owned-or-allied) scope ``GameState.friendly_provinces_for`` uses for
military purposes.

**Phase 412 -- the missing half: revenue was computed but never
collected.** Rulebook [9] (quoted verbatim): "Alla fine del turno si
incassano le rendite, quindi si paga il mantenimento degli Eroi e poi
quello delle unità militari" -- collect revenue, *then* pay Hero
upkeep, *then* pay military upkeep. [9.1]: "Se un Re controlla una
provincia alla fine del turno, le tasse vengono aggiunte al suo
tesoro" -- a province's tax is added to its owner's treasury, no
formula beyond that. Through Phase 411, ``compute_tax_base()`` was
only ever read by report composers (Financial Report, ASpy's tax
estimate, the PROVINCES report's own Tax column) -- ``turn/expenses.py
apply_turn_maintenance()`` (Phase 404) really debits the matching
expense side every turn, but nothing on the credit side ever mutated
``KingdomState.treasury``. ``apply_turn_revenue()`` below closes that:
called once per turn, before ``apply_turn_maintenance()`` (matching
[9]'s own explicit ordering), it credits each kingdom's own
``compute_tax_base()`` plus ``compute_office_gold_bonus()`` (the real,
named "5-gold bonus"/"10-gold bonus" for King of Pain/Prince of
Thieves, ``models/office.py OFFICE_PERK_DESCRIPTION`` -- the same two
office holders ``report/turn_report.py describe_finances_report()``'s
own "(Including +5 Black Knights)"/"(Including +10 Thieves Guild)"
notes already reference, now made true for the first time).

**Deliberately not folded into the credited amount: `Inv_Bonus`
(`compute_invention_bonus_percent()`) and the two, separately-confirmed
-unsourced adjacent mechanics** (a per-race `Racial_Tax` ability
declared but never dispatched anywhere in the available `.PAS` files,
and [9.2]'s own monster-devastation tax reduction, named in the
rulebook prose with no recoverable trigger probability or magnitude
anywhere in the source). `Inv_Bonus` is real Pascal (`REPORTS.PAS`:
`IF Inv_Bonus(kng) > 0 THEN WRITELN(...,Inv_Bonus(kng):3,'%')`), but
nothing in the available source confirms it modifies the actual gold
credited rather than being a report-only percentage -- Phase 268's own
design choice to keep it "additive to (not folded into)
`compute_tax_base()`'s own return value" for *display* purposes is
preserved here for the *real credit* too, rather than silently
broadening its scope to a formula this project can't source. All three
are confirmed, not merely undiscovered -- see the user's own research
session for `Racial_Tax` and the monster-devastation reduction.
"""

from __future__ import annotations

from ak_engine.models.discovery import DISCOVERY_REVENUE_BONUS_PERCENT
from ak_engine.models.game_state import GameState, KingdomState, ProvinceState
from ak_engine.models.office import Office


def province_tax_yield(province: ProvinceState) -> int | None:
    """This province's own real expected tax revenue this turn, or ``None``
    if its base ``tax`` was never recorded -- see module docstring for the
    exact scar-reduction-then-percent-modifier formula and why an unknown
    base isn't treated as a zero yield.
    """

    if province.tax is None:
        return None

    after_scar = max(0, province.tax - province.scar_terrain_gold_reduction)
    after_modifier = after_scar * (100 + province.tax_modifier_percent) // 100
    after_earthquake_flat = after_modifier - province.earthquake_flat_reduction
    return max(0, after_earthquake_flat)


def compute_tax_base(state: GameState, kingdom_id: int) -> int:
    """``Tax_Base(kingdom_id)``: the sum of ``province_tax_yield()`` across
    every province this kingdom owns with a known base tax value -- see
    module docstring for the full derivation and its documented gaps.
    """

    return sum(
        yield_ for province in state.provinces.values()
        if province.owner_kingdom_id == kingdom_id
        and (yield_ := province_tax_yield(province)) is not None
    )


def compute_invention_bonus_percent(kingdom: KingdomState) -> int:
    """``Inv_Bonus(kng)``: the sum of every revenue-bonus ``Discovery``
    (``crunch0``-``crunch27``) this kingdom owns -- REPORTS.PAS's own
    ``IF Inv_Bonus(kng) > 0 THEN WRITELN(... Inv_Bonus(kng):3,'%')``
    confirms this is a bare percentage, not a gold figure, and therefore
    additive to (not folded into) ``compute_tax_base()``'s own return
    value -- see ``models/discovery.py``'s own Phase 268 note.
    """

    return sum(
        DISCOVERY_REVENUE_BONUS_PERCENT[discovery]
        for discovery in kingdom.discoveries
        if discovery in DISCOVERY_REVENUE_BONUS_PERCENT
    )


# Phase 412 -- `models/office.py OFFICE_PERK_DESCRIPTION`'s own real text:
# "Order of Black Knights; 1 fanatical unit, 5-gold bonus" (Office.EVIL_KING)
# and "Thieves Guild, 10-gold bonus" (Office.THIEF_PRINCE) -- the same two
# offices `report/turn_report.py describe_finances_report()` already
# recognizes for its own "(Including +N ...)" notes.
OFFICE_GOLD_BONUS: dict[Office, int] = {
    Office.EVIL_KING: 5,
    Office.THIEF_PRINCE: 10,
}


def compute_office_gold_bonus(state: GameState, kingdom_id: int) -> int:
    """Sum of ``OFFICE_GOLD_BONUS`` for every real-gold-bonus office whose
    current holder's own King belongs to ``kingdom_id`` -- mirrors
    ``describe_finances_report()``'s own "(Including +N ...)" note logic
    exactly (same holder resolution, same "belongs to this kingdom" check),
    so the note and the real credit always agree.
    """

    # Deferred import: `turn/office_holder.py` already imports this module
    # (`compute_tax_base` feeds Treasurer's own Merit Points) -- a
    # module-level import here would close that into a real circular
    # import, the same situation `office_holder.py resolve_army_office_
    # holder()`'s own docstring already documents and works around the
    # same way.
    from ak_engine.turn.office_holder import resolve_office_holder

    total = 0
    for office, bonus in OFFICE_GOLD_BONUS.items():
        holder = resolve_office_holder(state, office)
        if holder is not None and state.leaders[holder.leader_id].kingdom_id == kingdom_id:
            total += bonus
    return total


def apply_turn_revenue(state: GameState) -> dict[int, int]:
    """Credits every kingdom's own ``compute_tax_base()`` plus
    ``compute_office_gold_bonus()`` to its treasury, once per turn -- see
    module docstring's Phase 412 section for the rulebook citation, why
    this was a display-only figure through Phase 411, and what's
    deliberately not folded in (``Inv_Bonus``, ``Racial_Tax``, monster
    devastation).

    Returns the amount credited per kingdom, keyed by ``kingdom_id`` --
    the same "callers/tests that want to verify a specific credit don't
    need to re-derive the formula themselves" convention ``turn/
    expenses.py apply_turn_maintenance()`` already established for the
    debit side.

    **Must be called before ``apply_turn_maintenance()``** -- rulebook
    [9]'s own explicit ordering ("si incassano le rendite, quindi si
    paga il mantenimento").
    """

    credited: dict[int, int] = {}
    for kingdom_id, kingdom in state.kingdoms.items():
        amount = compute_tax_base(state, kingdom_id) + compute_office_gold_bonus(state, kingdom_id)
        kingdom.treasury += amount
        credited[kingdom_id] = amount
    return credited
