"""End-to-end battle orchestration on top of a persistent ``GameState``.

Wires together, in order: ``turn/strength.py`` (per-army effective
strength) -> ``turn/battle_resolution.py`` (line-up, luck, column
winners) -> ``turn/aftermath.py`` (quality changes) -> ``turn/retreat.py``
(retreat/disband for a clean-swept loser) -> province ownership.

**Simplifications made to keep this tractable, all documented in
ak_engine/README.md:**

- Outcome is judged at the *side* level from ``BattleResult.winner`` and
  each side's columns-won count, not per-column elimination: a side that
  loses every column is "clean swept" (destroyed, or retreats/disbands);
  any other losing outcome (a mixed result, including a tie) leaves the
  province **contested** -- no eliminations, just a quality-change roll,
  matching the rulebook's [7.5]/[7.6] framing around "the defeated army"
  and "contested provinces" rather than individual units.
- The exploration-advantage and Tactical/Naval-ability special factors,
  fanaticism, and the desert-without-camels penalty are NOT wired in here
  -- they need per-battle context (leader ability values, a camel-unit
  check, alignment-based fanaticism rolls) this orchestrator doesn't
  collect yet. Strength here is race + terrain + quality + defender bonus
  only.
- The nemesis penalty is NOT applied: it depends on which specific unit
  ends up paired against which in a column, and that pairing only exists
  *inside* `resolve_battle` (after line-up) -- by the time this module
  calls `compute_effective_strength`, the pairing isn't known yet. Fixing
  this needs `resolve_battle` to support a post-hoc strength adjustment
  pass, which doesn't exist yet.
- A clean-swept loser's retreat destination always uses
  ``find_retreat_destination`` (nearest friendly neighboring province),
  even for an attacker forced to retreat -- the more precise "back to the
  province it invaded from, or adjacent to that" rule
  (``retreat.attacker_retreat_candidates``) is used when
  ``attacker_origin`` is supplied, and skipped otherwise.
- **Whether a losing side even attempts to retreat vs. fights on** is a
  rulebook decision with no formula (capital status, wealth, retreat path,
  etc. -- see `turn/retreat.py`); exposed here as ``loser_retreats: bool``,
  the caller's call.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from ak_engine.models.army_type import ArmyType
from ak_engine.models.game_state import ArmyState, GameState
from ak_engine.models.map import HexCoord
from ak_engine.turn.aftermath import roll_quality_change
from ak_engine.turn.battle_line import BattleUnit
from ak_engine.turn.battle_resolution import BattleResult, resolve_battle
from ak_engine.turn.combat import Quality
from ak_engine.turn.movement import NORMAL_MAP_BOUNDS, MapBounds
from ak_engine.turn.retreat import attacker_retreat_candidates, find_retreat_destination
from ak_engine.turn.strength import compute_effective_strength, roll_elephants_strength


@dataclass(slots=True)
class BattleReport:
    battle_result: BattleResult
    conquered: bool
    destroyed_army_ids: list[int] = field(default_factory=list)
    retreated_army_ids: list[int] = field(default_factory=list)
    disbanded_army_ids: list[int] = field(default_factory=list)
    mercenary_army_ids: list[int] = field(default_factory=list)
    quality_changes: dict[int, Quality] = field(default_factory=dict)


def _build_battle_units(
    armies: list[ArmyState],
    state: GameState,
    *,
    is_defender: bool,
    terrain,
    province_coord: HexCoord,
    rng: random.Random,
) -> list[BattleUnit]:
    """Build BattleUnits for one side of a battle at ``province_coord``.

    "Home province" is judged against ``province_coord`` -- the province
    the battle is actually happening in -- not ``army.location``. Before a
    Move that triggers a battle completes, an attacking army's
    ``location`` is still its *origin*, not the contested province, so
    comparing against ``army.location`` would ask the wrong question.
    """

    units = []
    for army in armies:
        kingdom = state.kingdoms[army.kingdom_id]
        is_home = province_coord == kingdom.home_province
        override = roll_elephants_strength(rng) if army.army_type is ArmyType.ELEPHANTS else None
        strength = compute_effective_strength(
            army.army_type,
            kingdom.race,
            army.quality,
            terrain,
            is_defender=is_defender,
            is_home_province=is_home,
            base_strength_override=override,
        )
        units.append(BattleUnit(army.army_type, strength, source_id=army.army_id))
    return units


def _retreat_or_disband(
    army: ArmyState,
    state: GameState,
    report: BattleReport,
    rng: random.Random,
    *,
    destination: HexCoord | None,
) -> None:
    if destination is not None:
        army.location = destination
        army.quality = roll_quality_change(army.quality, rng, is_winner=False, retreated=True)
        report.quality_changes[army.army_id] = army.quality
        report.retreated_army_ids.append(army.army_id)
        return

    if army.quality in (Quality.GREEN, Quality.DEPLETED):
        report.disbanded_army_ids.append(army.army_id)
        state.remove_army(army.army_id)
    else:
        army.kingdom_id = None
        army.commanded_by = None
        army.unhireable_this_turn = True
        report.mercenary_army_ids.append(army.army_id)


def fight_battle(
    state: GameState,
    attacker_kingdom_id: int,
    province_coord: HexCoord,
    attacker_army_ids: list[int],
    *,
    loser_retreats: bool = True,
    attacker_origin: HexCoord | None = None,
    rng: random.Random | None = None,
) -> BattleReport:
    """Resolve one battle at ``province_coord`` and apply its consequences to ``state``."""

    rng = rng if rng is not None else random.Random()
    province = state.provinces[province_coord]

    attacker_armies = [state.armies[army_id] for army_id in attacker_army_ids]
    defender_armies = [
        army
        for army in state.armies_at(province_coord)
        if army.army_id not in attacker_army_ids
        and army.kingdom_id is not None
        and not state.is_allied(army.kingdom_id, attacker_kingdom_id)
    ]
    if not attacker_armies:
        raise ValueError("no attacking armies given")
    if not defender_armies:
        raise ValueError("no defending armies at this province to fight")

    attacker_units = _build_battle_units(
        attacker_armies, state, is_defender=False, terrain=province.terrain, province_coord=province_coord, rng=rng
    )
    defender_units = _build_battle_units(
        defender_armies, state, is_defender=True, terrain=province.terrain, province_coord=province_coord, rng=rng
    )

    battle_result = resolve_battle(attacker_units, defender_units, rng=rng)

    defender_clean_swept = battle_result.winner == "attacker" and battle_result.defender_columns_won == 0
    attacker_clean_swept = battle_result.winner == "defender" and battle_result.attacker_columns_won == 0

    report = BattleReport(battle_result=battle_result, conquered=defender_clean_swept)

    for army in attacker_armies:
        if battle_result.winner == "attacker":
            army.quality = roll_quality_change(army.quality, rng, is_winner=True)
            report.quality_changes[army.army_id] = army.quality
        elif attacker_clean_swept and loser_retreats:
            bounds = MapBounds(*NORMAL_MAP_BOUNDS)
            if attacker_origin is not None:
                destination = attacker_retreat_candidates(attacker_origin, bounds)[0]
            else:
                friendly = state.friendly_provinces_for(attacker_kingdom_id) - {province_coord}
                destination = find_retreat_destination(army.location, bounds, friendly)
            _retreat_or_disband(army, state, report, rng, destination=destination)
        elif attacker_clean_swept:
            report.destroyed_army_ids.append(army.army_id)
            state.remove_army(army.army_id)
        else:
            army.quality = roll_quality_change(army.quality, rng, is_winner=False, retreated=False)
            report.quality_changes[army.army_id] = army.quality

    for army in defender_armies:
        if battle_result.winner == "defender":
            army.quality = roll_quality_change(army.quality, rng, is_winner=True)
            report.quality_changes[army.army_id] = army.quality
        elif defender_clean_swept and loser_retreats:
            bounds = MapBounds(*NORMAL_MAP_BOUNDS)
            friendly = state.friendly_provinces_for(army.kingdom_id) - {province_coord}
            destination = find_retreat_destination(army.location, bounds, friendly)
            _retreat_or_disband(army, state, report, rng, destination=destination)
        elif defender_clean_swept:
            report.destroyed_army_ids.append(army.army_id)
            state.remove_army(army.army_id)
        else:
            army.quality = roll_quality_change(army.quality, rng, is_winner=False, retreated=False)
            report.quality_changes[army.army_id] = army.quality

    if defender_clean_swept:
        province.owner_kingdom_id = attacker_kingdom_id
        province.contested_by_kingdom_id = None
    elif attacker_clean_swept:
        # Invasion cleanly repelled -- defender keeps the province outright,
        # no ongoing contest.
        province.contested_by_kingdom_id = None
    else:
        # Mixed result (including a tie): attacker failed to take the
        # province outright, but wasn't destroyed either -- contested [7.6].
        province.contested_by_kingdom_id = attacker_kingdom_id

    return report
