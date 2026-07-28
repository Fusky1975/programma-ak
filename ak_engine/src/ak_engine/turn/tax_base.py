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
"""

from __future__ import annotations

from ak_engine.models.discovery import DISCOVERY_REVENUE_BONUS_PERCENT
from ak_engine.models.game_state import GameState, KingdomState, ProvinceState


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
    return max(0, after_modifier)


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
