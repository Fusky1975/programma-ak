"""Peacetime "Modified Quality" resolution for the ARMIES report (Phase 279).

The real ``Qual_Modfr`` column has no surviving Pascal declaration --
confirmed absent by Phase 275's own systematic re-check, and re-confirmed
here (see ``report/turn_report.py describe_armies_report()``'s own Phase
279 note). What Phase 275's audit didn't have was the user's own real-file
cross-check of what the column actually shows: every one of its five
modifiers is a rulebook mechanic this project already implements
elsewhere, real and sourced -- only the specific act of *combining them
outside of an active battle, for a report line* is project-original
composition, the same "formula lost, inputs sourced" category Phase 277's
King of Pain/Prince of Thieves point formulas and Phase 278's PROVINCES
columns both closed before it.

**The five modifiers, and where each one already lives**:

1. **Home-province +1** and **desert-without-camels -1**
   (rulebook, ``turn/battle_orchestrator.py _build_battle_units``'s own
   Phase 35/41 wiring) -- resolved here the same way, but against
   ``army.location`` directly (there is no "battle province" distinct
   from the army's own current province in peacetime).
2. **Druidic-ability shortfall** (rulebook [4.32], `turn/strength.py
   DRUID_TABLE`/``compute_druidic_shortfall``, `turn/battle_orchestrator.py
   druidic_shortfall_for()`/``king_druidic_shortfall_for()`` -- Phase
   41/42's own King-substitution carve-out for an unled army). Both
   functions were made public (dropped their leading underscore) in this
   phase specifically so this module could reuse them verbatim instead
   of re-deriving the same commander/King lookup a second time.
3. **Race-matching legendary leadership item, +1** (the user's own rules
   3-6: Excalibur for Human, Bow of the Elven Kings for Elf, Axe of the
   Dwarven Lords for Dwarf, Scimitar of Orc Mastery for Orc) -- genuinely
   new wiring; `models/treasure.py` only ever named these four items
   (`TREASURE_NAME`) and scored them for an unrelated Merit Point bonus
   (`turn/merit_points.py LEGENDARY_ITEM_BONUS_TREASURES`), neither of
   which is a combat-quality effect. Unlike Druidic ability, the
   rulebook text the user quoted names only the army's own commanding
   Hero or King -- no King-substitution carve-out for an unled army,
   so ``army.commanded_by is None`` always contributes 0 here.

All four numeric modifiers are combined via `turn/strength.py
modified_quality()`'s own single-pass clamp (its new Phase 279
``race_item_bonus`` parameter) -- summed together before clamping to
``Quality``'s range, not applied as separate clamped steps, so a severe
Druidic shortfall that floors a unit at Depleted isn't wrongly rescued
back up by a later +1.

**No longer report-only (Phase 285)**: `_build_battle_units` in
`turn/battle_orchestrator.py` now computes this same `race_item_bonus`
independently (same `RACE_LEADERSHIP_TREASURE` table, now hoisted to
`models/treasure.py` so both modules can share it without a circular
import) and threads it into `turn/strength.py compute_effective_
strength()` for real combat -- see that function's own Phase 285 note.
This module's own `compute_army_modified_quality()` still exists
unchanged for the ARMIES report's peacetime display column; it does not
call the battle path, it just computes the same bonus a second time
against `army.location` instead of a live battle's province.
"""

from __future__ import annotations

from ak_engine.models.army_type import ArmyType, MONSTROUS_ARMY_RACE
from ak_engine.models.game_state import ArmyState, GameState
from ak_engine.models.map import Terrain
from ak_engine.models.treasure import RACE_LEADERSHIP_TREASURE
from ak_engine.turn.battle_orchestrator import druidic_shortfall_for
from ak_engine.turn.combat import Quality
from ak_engine.turn.strength import modified_quality


def compute_army_modified_quality(state: GameState, army: ArmyState) -> Quality:
    """The ARMIES report's own "Modified Quality" for one owned army.

    Assumes ``army.kingdom_id`` is a real, owned kingdom (the report only
    ever calls this for a kingdom's own armies) -- ``state.kingdoms[...]``
    is indexed directly, not defensively looked up, the same assumption
    every other owned-army consumer in this project already makes.
    """

    kingdom = state.kingdoms[army.kingdom_id]
    province = state.provinces.get(army.location)
    terrain = province.effective_terrain() if province is not None else None

    is_home = army.location == kingdom.home_province
    desert_without_camels = terrain is Terrain.DESERT and not any(
        other.army_type is ArmyType.CAMEL_CORPS
        for other in state.armies.values()
        if other.kingdom_id == army.kingdom_id and other.location == army.location
    )

    army_race = MONSTROUS_ARMY_RACE.get(army.army_type, kingdom.race)
    druidic_shortfall = druidic_shortfall_for(army, state, army_race, army.location)

    race_item_bonus = 0
    if army.commanded_by is not None:
        needed_treasure = RACE_LEADERSHIP_TREASURE.get(army_race)
        if needed_treasure is not None and any(
            item.treasure == needed_treasure for item in state.items_held_by(army.commanded_by)
        ):
            race_item_bonus = 1

    return modified_quality(
        army.quality,
        desert_without_camels=desert_without_camels,
        is_home_province=is_home,
        druidic_shortfall=druidic_shortfall,
        race_item_bonus=race_item_bonus,
    )
