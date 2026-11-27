"""Arch-Mage's own "Sense Magic Items in Province" perk -- Phase 490.

``CARICHE E ABLITÀ.txt``'s full real text for ``Office.MAGE`` (already
quoted in ``models/office.py OFFICE_PERK_DESCRIPTION``, Phase 103):
"The Wand has the power to sense the presence of other magic items in
the same province: whenever you move into a province, it will tell you
which magic items are present, but not where they are."

**What counts as "present in the province" (2026-11-27)**: the real
reports (``SE3__T8.K1``) show the Wand naming an item right next to the
Special Place that holds it ("a Volcanic Tunnel (#101) ... Legend says the
Cloak of Stealth is hidden here. ... The Platinum Wand senses the Cloak of
Stealth in Cretacia."), so the treasure still lying in an unlooted
Feature of the province counts, found or not. So do the magic items carried
by *other* leaders standing there (the perk's own "other magic items"
wording excludes the sensing leader's own inventory).

**Excluded treasure categories**: ``GOLD_HOARD`` (a gold-value tier,
not a magic item), ``QUEST_ITEM`` (scenario-tracking flags), ``SENTINEL``
(``NO_TREASURE``, a placeholder), and ``UNUSED_EXTENSION`` (declared,
never-referenced ordinals) -- every other ``TreasureCategory`` reads as
a genuine magic item (``models/treasure.py``'s own category table).

The report tells each item with the original sentence (``SAY.PAS _LPWand``:
"The Platinum Wand senses the \\ in @.").
"""

from __future__ import annotations

from ak_engine.models.game_state import GameState
from ak_engine.models.map import HexCoord
from ak_engine.models.office import Office
from ak_engine.models.treasure import TREASURE_CATEGORY, Treasure, TreasureCategory
from ak_engine.turn.office_holder import resolve_office_holder

_NON_MAGIC_CATEGORIES = frozenset(
    {
        TreasureCategory.GOLD_HOARD,
        TreasureCategory.QUEST_ITEM,
        TreasureCategory.SENTINEL,
        TreasureCategory.UNUSED_EXTENSION,
    }
)


def sense_magic_items_in_province(state: GameState, leader_id: int, province: HexCoord) -> list[Treasure] | None:
    """``None`` if ``leader_id`` doesn't currently hold ``Office.MAGE`` --
    the caller (``turn/plan_dispatch.py``'s own LMOVE branch) only calls
    this at all for a leader who just moved, but the office check still
    lives here rather than at the call site, matching this project's own
    per-consumer ``resolve_office_holder()`` lookup convention (Phase
    488/489) rather than requiring every future caller to duplicate it.

    Otherwise returns the magic treasure of every unlooted Feature in
    ``province``, then every *other* leader's magic item currently there --
    ``[]``, not ``None``, when the Arch-Mage senses nothing (a real, empty
    result, distinct from "not the Arch-Mage").
    """

    mage_holder = resolve_office_holder(state, Office.MAGE)
    if mage_holder is None or mage_holder.leader_id != leader_id:
        return None

    sensed: list[Treasure] = []
    for feature in state.features.values():
        if feature.coord != province or feature.looted or feature.treasure is None:
            continue
        if TREASURE_CATEGORY.get(feature.treasure) in _NON_MAGIC_CATEGORIES:
            continue
        sensed.append(feature.treasure)
    for item in state.items.values():
        if item.owner_leader_id is None or item.owner_leader_id == leader_id:
            continue
        owner = state.leaders.get(item.owner_leader_id)
        if owner is None or owner.location != province:
            continue
        if TREASURE_CATEGORY.get(item.treasure) in _NON_MAGIC_CATEGORIES:
            continue
        sensed.append(item.treasure)
    return sensed
