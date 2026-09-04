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

**Phase 747 -- `Inv_Bonus` really credits gold, resolved by `Desktop/
INVBONUS.md` (user-supplied disassembly, 2026-09-04).** This note used
to say nothing in the available source confirmed `Inv_Bonus` modified
the actual gold credited rather than being a report-only percentage --
that's now resolved. `AK.EXE`'s own real economic resolver (quoted
byte-for-byte in the document) reads:

```pascal
eligible_revenue := lgold[kng] - old_gold;   { "B": the delta this turn's
                                                own province income + the
                                                +5/+10 office bonus already
                                                produced }
invention_gold := Trunc(Inv_Bonus(kng) * 0.01 * eligible_revenue + Random);
lgold[kng]      := lgold[kng] + invention_gold;
```

`amount` below (after the existing per-province raid-adjusted income,
the blackmail-penalty deduction, and `compute_office_gold_bonus()`) is
already exactly this "B" -- no reordering of those three existing steps
was needed. `Random` (`[0,1)`) is drawn **unconditionally**, even when
`Inv_Bonus(kng) = 0` (INVBONUS.md's own explicit point: skipping that
draw "disallinea tutti i tiri casuali successivi") -- the same RNG-
order-fidelity choice already made for THUNDERBIRD.md's coin-always-
drawn Scar-protection gate and BOLD OK.txt's every-packet-always-rolls
intimidation formula. `Trunc(x+U)` is an unbiased stochastic rounding
(not `round()`, not a floor-only `DIV`), matching Python's `int()`
truncation-toward-zero exactly since `amount`/`percent` are always
non-negative here. The resulting per-kingdom total is stashed on
`state.turn_revenue_credited` for `report/turn_report.py describe_
finances_report()`'s own new `_LRev` narration line (Phase 747) --
see that composer's own docstring.

**`Racial_Tax` -- confirmed NOT a real mechanic, Phase 680,
`Desktop/RACIALTAX.md` (user-supplied disassembly/source audit,
2026-08-29).** Earlier phases' own notes here treated `Racial_Tax` as
"a per-race ability declared but never dispatched" -- i.e. a real,
sourced-but-unwired mechanic, the same class of gap as `Inv_Bonus`.
That framing is now confirmed wrong: the name's only appearance in any
of the 13 surviving `.PAS` files is `CTBOTH.PAS:387`, inside a large
`{...}` **comment** -- an incomplete, non-compiling design-notes list
of candidate special-ability names (several entries in the same list
have no assigned ordinal at all, e.g. `Race_Recruit`). There is no
compiled `const`/routine anywhere in `AK.EXE`/`AKE.EXE`/`AKGEN.EXE`/
`AK.OVR`, no GW field, and no report text for it. The real, compiled
`Tax_Base(kng)` -- disassembled and quoted byte-for-byte in the same
document across all three executables -- sums `ptax[x,y]` filtered
only by `powner[x,y]=kng`; it never reads `prace`/`lrace`/any racial
title. A turn-by-turn cross-check against 11 real `GW3`/`SE3` samples
(an Elven King with a racially mixed empire, up to ~80% of tax base
foreign-race by turn 12) confirms `Expected Revenues` always equals
the unfiltered `ptax` sum, with no racial bonus, penalty, or rounding
anywhere. `compute_tax_base()`/`province_tax_yield()` above already
implement exactly this unfiltered sum -- no code change was needed or
made; this is a closed, confirmed-absent gap, not an open one.

**Phase 670 -- [9.2]'s own monster-devastation tax reduction, resolved.**
This note used to say the mechanic was "named in the rulebook prose with
no recoverable trigger probability or magnitude anywhere in the source"
-- ``Desktop/THUNDERBIRD.md`` (user-supplied, 2026-08-28) fully resolves
it: a real formula, real probabilities, real damage (``turn/monster_
raids.py``). Unlike `Inv_Bonus`/`Racial_Tax`, this one genuinely does
reduce the actual gold credited -- but only the turn's own *collected*
income, never the persisted `ProvinceState.tax`/`compute_tax_base()`
figure itself (THUNDERBIRD.md's own point 9: "il danno riduce soltanto
le entrate riscosse in quel turno... non cambia `ptax`") -- so every
other consumer (FINANCES' own "Expected Revenues" line, the PROVINCES
report's Tax column, ASpy's estimate) keeps showing the pre-raid
*expected* figure unchanged.

**Phase 721 -- Scar Terrain's own tax-exhaustion collapse is checked at
cast-time, not from `apply_turn_revenue()` here.** `turn/cast_
execution.py apply_scar_terrain_collapse()` (user-supplied `Desktop/
SCAR.md`) fires immediately inside `_execute_scar_terrain()`'s own
success branch, not from this module's per-turn loop -- deliberately:
this loop only iterates each kingdom's own *owned* provinces, so an
unowned/neutral scarred province would never be checked here at all.
`province_tax_yield()`'s own `scar_terrain_gold_reduction` subtraction
above is unaffected either way -- it already correctly reflects
whatever the collapse mechanic leaves `ProvinceState.tax` implying,
regardless of when the exhaustion check itself runs.
"""

from __future__ import annotations

import random

from ak_engine.models.discovery import DISCOVERY_REVENUE_BONUS_PERCENT
from ak_engine.models.game_state import GameState, KingdomState, ProvinceState, UnpaidBlackmailPenalty
from ak_engine.models.office import Office
from ak_engine.turn.blackmail import resolve_unpaid_blackmail
from ak_engine.turn.monster_raids import resolve_province_raids


def province_tax_yield(province: ProvinceState) -> int | None:
    """This province's own real expected tax revenue this turn, or ``None``
    if its base ``tax`` was never recorded -- see module docstring for the
    exact scar-reduction-then-percent-modifier formula and why an unknown
    base isn't treated as a zero yield.

    Phase 509 -- Find Mines' own ``mine_gold_bonus`` (cumulative, permanent,
    capped at 10 gold -- see ``models/game_state.py ProvinceState``'s own
    docstring) is combined at the same step as ``scar_terrain_gold_
    reduction``, both being permanent changes to the base rather than the
    turn's own temporary ``tax_modifier_percent``/``earthquake_flat_
    reduction`` adjustments.
    """

    if province.tax is None:
        return None

    after_scar_and_mines = max(0, province.tax - province.scar_terrain_gold_reduction + province.mine_gold_bonus)
    after_modifier = after_scar_and_mines * (100 + province.tax_modifier_percent) // 100
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


def apply_turn_revenue(state: GameState, rng: random.Random) -> dict[int, int]:
    """Credits every kingdom's own province-by-province tax yield (each
    province run through ``turn/monster_raids.py resolve_province_raids()``
    first, Phase 670) plus ``compute_office_gold_bonus()`` to its treasury,
    once per turn -- see module docstring's Phase 412 section for the
    rulebook citation and why this was a display-only figure through
    Phase 411 (see also the Phase 680 note on ``Racial_Tax``, confirmed
    never a real mechanic at all).

    **Phase 747**: also folds ``compute_invention_bonus_percent()``'s
    own real gold credit into ``amount``, per ``Desktop/INVBONUS.md`` --
    see the module docstring's own Phase 747 section for the exact
    formula and the unconditional-``rng.random()``-draw fidelity choice.
    The final per-kingdom total is stashed on ``state.turn_revenue_
    credited`` for ``report/turn_report.py describe_finances_report()``'s
    own ``_LRev`` line.

    Returns the amount credited per kingdom, keyed by ``kingdom_id`` --
    the same "callers/tests that want to verify a specific credit don't
    need to re-derive the formula themselves" convention ``turn/
    expenses.py apply_turn_maintenance()`` already established for the
    debit side.

    **Must be called before ``apply_turn_maintenance()``** -- rulebook
    [9]'s own explicit ordering ("si incassano le rendite, quindi si
    paga il mantenimento").

    **Phase 713** folds in ``turn/blackmail.py resolve_unpaid_
    blackmail()``'s own real "3 times that much in tax revenues"
    penalty, per Kingdom, floored at 0 -- applied after the province
    loop (province-level income is unaffected; this is a Kingdom-level
    deduction, not tied to any one province) and before the office gold
    bonus.

    **Phase 741**: the real penalty amount actually deducted (floored at
    whatever province income was available that turn -- the same "can't
    lose more revenue than you had" cap the rest of this loop already
    applies) is recorded onto ``state.turn_blackmail_penalties`` for
    ``report/turn_report.py describe_finances_report()`` to narrate --
    see ``UnpaidBlackmailPenalty``'s own docstring. The blackmailer's own
    Kingdom id is read off ``kingdom.active_blackmail`` *before*
    ``resolve_unpaid_blackmail()`` clears it.
    """

    # Deferred import: same circular-import workaround `compute_office_
    # gold_bonus()` above already needs and documents.
    from ak_engine.turn.office_holder import resolve_office_holder

    state.turn_raid_events = []
    state.turn_blackmail_penalties = []
    state.turn_revenue_credited = {}
    divine_archangel_holder = resolve_office_holder(state, Office.DIVINE_KING)
    divine_archangel_kingdom_id = (
        state.leaders[divine_archangel_holder.leader_id].kingdom_id if divine_archangel_holder is not None else None
    )
    thunder_used = False

    credited: dict[int, int] = {}
    for kingdom_id, kingdom in state.kingdoms.items():
        owned_provinces = sorted(
            (province for province in state.provinces.values() if province.owner_kingdom_id == kingdom_id),
            key=lambda province: (province.coord.x, province.coord.y),
        )
        amount = 0
        for province in owned_provinces:
            income = province_tax_yield(province)
            if income is None:
                continue
            income, thunder_used, events = resolve_province_raids(
                state, kingdom_id, province, income, divine_archangel_kingdom_id, thunder_used, rng
            )
            state.turn_raid_events.extend(events)
            amount += income
        active_claim = kingdom.active_blackmail
        penalty = resolve_unpaid_blackmail(state, kingdom_id)
        if penalty > 0 and active_claim is not None:
            state.turn_blackmail_penalties.append(
                UnpaidBlackmailPenalty(
                    kingdom_id=kingdom_id,
                    blackmailer_kingdom_id=active_claim.spy_kingdom_id,
                    amount=min(penalty, amount),
                )
            )
        amount = max(0, amount - penalty)
        amount += compute_office_gold_bonus(state, kingdom_id)
        percent = compute_invention_bonus_percent(kingdom)
        invention_gold = int(percent * 0.01 * amount + rng.random())
        amount += invention_gold
        kingdom.treasury += amount
        credited[kingdom_id] = amount
    state.turn_revenue_credited = credited
    return credited
