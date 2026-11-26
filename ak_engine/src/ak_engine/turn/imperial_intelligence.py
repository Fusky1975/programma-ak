"""World Emperor's and Imperial Treasurer's own passive intelligence
perks -- Phase 491.

``CARICHE E ABLITÀ.txt``'s full real text for these two Offices (already
quoted in ``models/office.py OFFICE_PERK_DESCRIPTION``, Phase 103):

    WORLD EMPEROR: "The Crown will give you the ability to know the
    strength of all your rivals in your quest for Empire ... Only the
    tax bases of kings bordering your kingdom that you have known for
    at least one full turn will be shown."

    IMPERIAL TREASURER: "The Abacus allows you to see the Treasuries of
    all your rivals in your pursuit of wealth ... Only kings bordering
    your kingdom that you have known for a full turn will be shown."

Both share the exact same real gate -- "bordering, and known for at
least one full turn" -- differing only in *which* number gets reported
(``turn/tax_base.py compute_tax_base()`` vs. ``KingdomState.treasury``).
That gate needed genuinely new state (``GameState.kingdoms_met_since``,
this same phase's own addendum to ``turn/world_events.py record_
kingdom_contacts()``) since the pre-existing ``kingdoms_met`` set is a
pure boolean "have we ever met" ratchet with no time dimension.

**Phase 640 wires this in**: ``report/turn_report.py describe_
diplomacy_report()``/``_diplomacy_entry()`` call both functions below
once per report and render the real ``Write_List``/``Desc_Align``
enrichment text (``REPORTS.PAS`` lines 128-158) -- this module itself
stays the pure primitive, no rendering logic added here.
"""

from __future__ import annotations

from ak_engine.models.game_state import GameState
from ak_engine.models.office import Office
from ak_engine.turn.movement import MapBounds, neighbors
from ak_engine.turn.office_holder import emperor_best_hope, resolve_office_holder
from ak_engine.turn.tax_base import compute_tax_base


def bordering_kingdoms(state: GameState, bounds: MapBounds, kingdom_id: int) -> set[int]:
    """Every other kingdom currently owning a province adjacent to one of
    ``kingdom_id``'s own -- the real-time adjacency scan ``turn/world_
    events.py record_kingdom_contacts()`` already runs for *every* pair
    at once, narrowed here to one kingdom's own bordering set. A fresh
    scan, not a ``GameState.kingdoms_met`` lookup: that set is a
    monotone "ever bordered" ratchet, not "currently bordering" (a
    province can change hands, ending a real border `kingdoms_met`
    itself has no way to reflect).
    """

    result: set[int] = set()
    for coord, province in state.provinces.items():
        if province.owner_kingdom_id != kingdom_id:
            continue
        for neighbor_coord in neighbors(coord, bounds):
            neighbor = state.provinces.get(neighbor_coord)
            if (
                neighbor is not None
                and neighbor.owner_kingdom_id is not None
                and neighbor.owner_kingdom_id != kingdom_id
            ):
                result.add(neighbor.owner_kingdom_id)
    return result


def _known_bordering_kingdoms(state: GameState, bounds: MapBounds, office: Office, leader_id: int) -> set[int] | None:
    # The Crown is worn by the World Emperor "best hope" (the elected Emperor once there is one), not only by the elected.
    holder = emperor_best_hope(state) if office is Office.EMPEROR else resolve_office_holder(state, office)
    if holder is None or holder.leader_id != leader_id:
        return None
    kingdom_id = state.leaders[leader_id].kingdom_id
    if kingdom_id is None:
        return None
    return {
        other_id
        for other_id in bordering_kingdoms(state, bounds, kingdom_id)
        if state.has_met_for_full_turn(kingdom_id, other_id)
    }


def known_bordering_kingdom_tax_bases(
    state: GameState, bounds: MapBounds, leader_id: int
) -> dict[int, int] | None:
    """``None`` unless ``leader_id`` currently holds ``Office.EMPEROR``
    (always the King -- ``resolve_office_holder()``'s own Emperor special
    case). Otherwise every bordering, known-for-a-full-turn kingdom's own
    ``compute_tax_base()``, keyed by kingdom id.
    """

    known = _known_bordering_kingdoms(state, bounds, Office.EMPEROR, leader_id)
    if known is None:
        return None
    return {other_id: compute_tax_base(state, other_id) for other_id in known}


def known_bordering_kingdom_treasuries(
    state: GameState, bounds: MapBounds, leader_id: int
) -> dict[int, int] | None:
    """``None`` unless ``leader_id`` currently holds ``Office.TREASURER``.
    Otherwise every bordering, known-for-a-full-turn kingdom's own
    ``KingdomState.treasury``, keyed by kingdom id.
    """

    known = _known_bordering_kingdoms(state, bounds, Office.TREASURER, leader_id)
    if known is None:
        return None
    return {other_id: state.kingdoms[other_id].treasury for other_id in known}
