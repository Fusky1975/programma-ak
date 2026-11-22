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
   from the army's own current province in peacetime). The desert
   penalty's own Find Water carve-out (Advanced Ability, Phase 511) is
   reused verbatim via ``turn/battle_orchestrator.py side_has_present_
   leader_with_ability()``, scoped to this army's own kingdom at its own
   location -- the same "present, not necessarily commanding" reading
   ``_build_battle_units`` already uses for a real battle.
2. **Druidic-ability shortfall** (rulebook [4.32], `turn/strength.py
   DRUID_TABLE`/``compute_druidic_shortfall``, `turn/battle_orchestrator.py
   druidic_shortfall_for()`/``king_druidic_shortfall_for()`` -- Phase
   41/42's own King-substitution carve-out for an unled army). Both
   functions were made public (dropped their leading underscore) in this
   phase specifically so this module could reuse them verbatim instead
   of re-deriving the same commander/King lookup a second time.
3. **Race-matching legendary leadership item, +1** (the user's own rules
   3-6: Excalibur for Human, Bow of the Elven Kings for Elf, Axe of the
   Dwarven Lords for Dwarf, Scimitar of Orc Mastery for Orc). Unlike
   Druidic ability, the rulebook text the user quoted names only the
   army's own commanding Hero or King -- no King-substitution carve-out
   for an unled army, so ``army.commanded_by is None`` always
   contributes 0 here. Reused verbatim via `turn/battle_orchestrator.py
   race_item_bonus_for()`, the same single shared helper this module's
   two real-combat call sites (`_build_battle_units`,
   `_qual_modfr_score_by_army_id`) also call -- previously three
   separate, byte-identical copies.

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

from ak_engine.models.advanced_ability import AdvancedAbility
from ak_engine.models.army_type import ArmyType, MONSTROUS_ARMY_RACE
from ak_engine.models.enums import Ability
from ak_engine.models.game_state import ArmyState, GameState
from ak_engine.models.map import Terrain
from ak_engine.turn.battle_orchestrator import (
    druidic_shortfall_for,
    race_item_bonus_for,
    side_has_present_leader_with_ability,
)
from ak_engine.turn.combat import Quality
from ak_engine.turn.discovery_effects import effective_skill_level
from ak_engine.turn.strength import compute_effective_strength, modified_quality


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
    explorer_find_water = side_has_present_leader_with_ability(
        state, army.location, frozenset({army.kingdom_id}), AdvancedAbility.EXPLORER_FIND_WATER
    )
    desert_without_camels = (
        terrain is Terrain.DESERT
        and not explorer_find_water
        and not any(
            other.army_type is ArmyType.CAMEL_CORPS
            for other in state.armies.values()
            if other.kingdom_id == army.kingdom_id and other.location == army.location
        )
    )

    army_race = army.race if army.race is not None else MONSTROUS_ARMY_RACE.get(army.army_type, kingdom.race)
    druidic_shortfall = druidic_shortfall_for(army, state, army_race, army.location)

    race_item_bonus = race_item_bonus_for(state, army_race, army.commanded_by)

    return modified_quality(
        army.quality,
        desert_without_camels=desert_without_camels,
        is_home_province=is_home,
        druidic_shortfall=druidic_shortfall,
        race_item_bonus=race_item_bonus,
    )


def army_peacetime_strength(state: GameState, army: ArmyState, ability: Ability) -> float:
    """Phase 394's own "current `Army_Str`" -- the Royal Air Force/
    Praetorian Guard/Imperial Flag Squadron Royal Titles' shared score
    term (`turn/office_holder.py`'s own Phase 394 addendum), the same
    "rank the strongest qualifying army by its own effective strength,
    outside of any active battle" question `compute_army_modified_
    quality()` above already answers for the ARMIES report's peacetime
    quality column -- just carried one step further, into a real
    strength number instead of stopping at the discrete `Quality` tier.

    Reuses `compute_army_modified_quality()` verbatim for the quality
    input (so home-province/desert-without-camels/Druidic-shortfall/
    race-item bonuses are already baked in), then feeds that into
    `turn/strength.py compute_effective_strength()` with every other
    battle-only parameter left at its neutral default -- `modified_
    quality()` is idempotent when given no further deltas, so this
    doesn't double-apply any of those four. `combat_ability_level` is
    the one parameter this function adds beyond what `compute_army_
    modified_quality()` already covers: the commanding leader's own
    ``ability`` skill level (`Ability.TACTICAL` for Airforce/Praetor,
    `Ability.NAVAL` for Flagship -- the exact two terms AKGEN's own
    confirmed `score_formula` names, "Army_Str(... Tactical ...)"/
    "Army_Str(... Naval ...)"), 0 for an unled army -- the same "no
    commander, no bonus" default `_select_side_commander()`'s own
    garrison-fallback path already establishes for a real battle.

    This is deliberately narrower than a real battle's own strength
    calculation: `is_defender`, `is_fanatical`, exploration, Phantasmal
    Armies, an opponent's army type, and Illusory Fog all stay at their
    neutral off/0 defaults, since none of them has a coherent meaning
    outside an actual battle -- see `turn/office_holder.py`'s own Phase
    394 addendum for why this is the one subset of `compute_effective_
    strength()`'s many parameters that *does* have a real "at rest"
    value, closing the gap `turn/merit_points.py`'s own Phase 379
    addendum left open.
    """

    kingdom = state.kingdoms[army.kingdom_id]
    province = state.provinces.get(army.location)
    terrain = province.effective_terrain() if province is not None else Terrain.PLAINS
    is_island = province.is_island if province is not None else False
    illusory_terrain = province.illusory_terrain if province is not None else None
    illusory_terrain_enhanced = province.illusory_terrain_enhanced if province is not None else False
    army_race = army.race if army.race is not None else MONSTROUS_ARMY_RACE.get(army.army_type, kingdom.race)
    quality = compute_army_modified_quality(state, army)

    ability_level = 0
    if army.commanded_by is not None:
        leader = state.leaders.get(army.commanded_by)
        if leader is not None:
            ability_level = effective_skill_level(state, leader, ability)

    return compute_effective_strength(
        army.army_type, army_race, quality, terrain, combat_ability_level=ability_level, is_island=is_island,
        illusory_terrain=illusory_terrain, illusory_terrain_enhanced=illusory_terrain_enhanced,
    )
