"""End-to-end battle orchestration on top of a persistent ``GameState``.

Wires together, in order: ``turn/strength.py`` (per-army effective
strength) -> ``turn/duel.py`` (Supreme Commander selection + demoralization,
[7.1]) -> ``turn/battle_resolution.py`` (line-up, luck, column winners) ->
``turn/pursuit.py`` (chasing a clean-swept loser's retreaters, [7.3]) ->
``turn/aftermath.py`` (quality changes) -> ``turn/retreat.py`` (retreat/
disband for whoever pursuit doesn't catch) -> province ownership.

**Duel** ([7.1]): each side's armies are grouped by ``commanded_by`` into
``turn/duel.py`` ``Commander``s (contingent size = army count;
``tactical_ability`` is a real skill level read from
``LeaderState.skills`` as of Phase 30 -- 0 if that leader has no
``skills`` recorded, the same placeholder behavior this project used
before Phase 30 for every leader). Defenders fall back to
``provincial_garrison_commander()`` for any unled armies, per the
rulebook's explicit fallback ("has no abilities" -- always 0); attackers
have no such fallback (none is specified), so a duel only happens when
the attacker side has at least one led army. The duel *fight itself*
still isn't modeled (rulebook points to the unbuilt Special Encounter
Plan system, [5.10]) -- its outcome is instead approximated the same way
``turn/pursuit.py``'s own one-on-one standstill check already is:
``estimate_win_probability()`` compares the two commanders' own led
units' total strength, rng decides the loser, and
``apply_duel_demoralization()`` reduces that loser's own led units by
25% before the main battle resolves. Not a sourced mechanic -- a
documented approximation, same spirit and precedent as Pursuit's own.
Each side's Supreme Commander is now selected *before* ``_build_battle_units``
runs (Phase 30), specifically so their real ability level can also feed
the rulebook [6.3] "Tactical Ability +20%/level (or Naval in Sea
provinces)" strength bonus for their *entire* side, not just their own
led units -- previously always 0 (``turn/strength.py
compute_effective_strength``'s ``combat_ability_level`` parameter was
never passed by this module at all). That same ability level is now
also passed to ``resolve_battle``'s ``attacker_tactical_ability``/
``defender_tactical_ability`` (Phase 34), feeding the [7.2] front/rear
switch chance too -- one commander ability level driving three rulebook
effects (Duel tiebreak, strength bonus, switch chance) instead of three
independently-derived numbers.

**Pursuit** ([7.3]): once a side is judged clean-swept and
``loser_retreats=True``, before its armies retreat/disband, the winning
side's units get a chance (``turn/pursuit.py select_pursuers()``) to
catch and destroy some of them (``resolve_pursuit()``) -- per that
module's own documented requirement, each retreating army's strength for
this check is recomputed one quality level down, with the defender
bonus, via ``turn/strength.py compute_effective_strength()``. Caught
armies are removed outright (``BattleReport.pursuit_destroyed_army_ids``)
instead of reaching ``_retreat_or_disband`` at all.

**Multiple Contingents** ([7.8]): ``fight_battle()`` itself still only
ever fights one attacking party against one province's defenders.
``fight_multi_attacker_battle()`` is a separate, additional entry point
for when several leaders attack the *same* province in the *same*
phase: it partitions them into one or more actual battles via
``turn/multiple_contingents.py group_attackers_into_battles()`` (same
origin -> very likely to unite; different origins -> probably separate
battles) and calls ``fight_battle()`` once per resulting group, with
that group's army ids combined. **Not automatically invoked from
``execute_move()``/``plan_dispatch.py`` yet** -- this project's
per-leader plan processing (``run_leader_plan``) resolves one leader's
moves at a time and has no notion of "wait for every other leader's
same-phase move before resolving a battle", which is what real
Multiple-Contingents detection would need. ``fight_multi_attacker_battle``
is available for any caller that already has several simultaneous
attacks assembled (e.g. a future multi-leader turn processor), not
wired into the single-leader execution path.

**Simplifications made to keep this tractable, all documented in
ak_engine/README.md:**

- Outcome is judged at the *side* level from ``BattleResult.winner`` and
  each side's columns-won count, not per-column elimination: a side that
  loses every column is "clean swept" (destroyed, or retreats/disbands);
  any other losing outcome (a mixed result, including a tie) leaves the
  province **contested** -- no eliminations, just a quality-change roll,
  matching the rulebook's [7.5]/[7.6] framing around "the defeated army"
  and "contested provinces" rather than individual units.
- ~~The exploration-advantage special factor, fanaticism, and the
  desert-without-camels penalty are NOT wired in here~~ **fanaticism and
  desert-without-camels are wired in, as of Phase 35** -- see
  `_build_battle_units`'s docstring. **Exploration-advantage stays
  unwired**, and not for lack of trying: `models/game_state.py
  ProvinceState.explored_percent` is a single value per province, not
  per-kingdom, so there's no data anywhere in this project to compute a
  meaningful "own side's exploration vs. the enemy's" comparison for the
  same province -- a structural data-model gap, not a guess avoided.
  Fixing it would mean redesigning how every Explore/Move-triggered
  partial-exploration write updates state (`turn/move_execution.py`,
  `turn/plan_dispatch.py`'s own EXPLORE branch), out of scope here.
  ~~Tactical/Naval-ability~~ **is** wired in, as of Phase 30 (see
  `combat_ability_level` above). Strength here is race + terrain +
  quality + defender bonus + Tactical/Naval ability + fanaticism +
  desert-without-camels only.
- ~~The nemesis penalty is NOT applied~~ **fixed in Phase 33**: it
  depends on which specific unit ends up paired against which in a
  column, and that pairing only exists *inside* `resolve_battle` (after
  line-up) -- so it's applied there, not here, by
  `turn/battle_line.py apply_nemesis_penalties` right after line-up,
  before this module's `compute_effective_strength` output is used any
  further (luck, column contests, and whatever `BattleUnit`s a caller
  like `_apply_pursuit` keeps reading afterward).
- A clean-swept loser's retreat destination always uses
  ``find_retreat_destination`` (nearest friendly neighboring province),
  even for an attacker forced to retreat -- the more precise "back to the
  province it invaded from, or adjacent to that" rule
  (``retreat.attacker_retreat_candidates``) is used when
  ``attacker_origin`` is supplied, and skipped otherwise. **Whales are
  the one exception** (Phase 37): "When fighting in any terrain other
  than Sea, they have zero strength [``compute_effective_strength``'s
  own early-return]. However, if they lose a battle in such terrain,
  they can retreat into a Sea hex automatically without fear of being
  destroyed" -- a clean-swept Whale army in a non-Sea battle always
  retreats to the nearest adjacent Sea province (``_whale_sea_retreat_
  destination``, any ownership, not just friendly), bypassing both
  ``loser_retreats`` and the outright-destroy branch entirely. Two
  documented edge cases, not silently guessed around: if no adjacent
  province is Sea terrain at all, `_retreat_or_disband` falls back to
  its ordinary quality-based disband/mercenary rule (the rulebook's
  guarantee can't be literally honored by this project's map data); and
  Pursuit isn't exempted -- a retreating Whale can still be caught and
  destroyed by ``_apply_pursuit`` before reaching this branch at all,
  since the rulebook's guarantee is specifically about the *ordinary,
  no-retreat-destination* disband path, not about the separate [7.3]
  pursuit mechanic.
- **Whether a losing side even attempts to retreat vs. fights on** is a
  rulebook decision with no formula (capital status, wealth, retreat path,
  etc. -- see `turn/retreat.py`); exposed here as ``loser_retreats: bool``,
  the caller's call.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from ak_engine.models.army_type import ArmyType
from ak_engine.models.enums import Ability
from ak_engine.models.game_state import ArmyState, GameState
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.turn.aftermath import roll_quality_change
from ak_engine.turn.battle_line import BattleUnit, estimate_win_probability
from ak_engine.turn.battle_resolution import BattleResult, resolve_battle
from ak_engine.turn.combat import Quality
from ak_engine.turn.duel import Commander, apply_duel_demoralization, provincial_garrison_commander, select_supreme_commander
from ak_engine.turn.movement import NORMAL_MAP_BOUNDS, MapBounds
from ak_engine.turn.multiple_contingents import Attacker, group_attackers_into_battles
from ak_engine.turn.pursuit import select_pursuers, resolve_pursuit
from ak_engine.turn.retreat import attacker_retreat_candidates, find_retreat_destination
from ak_engine.turn.strength import compute_effective_strength, roll_elephants_strength, roll_fanaticism


@dataclass(slots=True)
class BattleReport:
    battle_result: BattleResult
    conquered: bool
    destroyed_army_ids: list[int] = field(default_factory=list)
    retreated_army_ids: list[int] = field(default_factory=list)
    disbanded_army_ids: list[int] = field(default_factory=list)
    mercenary_army_ids: list[int] = field(default_factory=list)
    pursuit_destroyed_army_ids: list[int] = field(default_factory=list)
    quality_changes: dict[int, Quality] = field(default_factory=dict)
    attacker_commander_leader_id: int | None = None
    defender_commander_leader_id: int | None = None
    duel_loser_side: str | None = None  # "attacker" / "defender" / None if no duel occurred


def _build_battle_units(
    armies: list[ArmyState],
    state: GameState,
    *,
    is_defender: bool,
    terrain,
    province_coord: HexCoord,
    rng: random.Random,
    combat_ability_level: int = 0,
    apply_fanaticism: bool = False,
) -> list[BattleUnit]:
    """Build BattleUnits for one side of a battle at ``province_coord``.

    "Home province" is judged against ``province_coord`` -- the province
    the battle is actually happening in -- not ``army.location``. Before a
    Move that triggers a battle completes, an attacking army's
    ``location`` is still its *origin*, not the contested province, so
    comparing against ``army.location`` would ask the wrong question.

    ``combat_ability_level`` (Phase 30) is this side's Supreme Commander's
    Tactical (or Naval, in Sea provinces) skill level -- rulebook [6.3]:
    "+20%/level", applied to every unit on the side, not just the
    commander's own led units (see ``fight_battle``'s docstring for why).

    **Desert without camels** (Phase 35): "In a desert battle, one camel
    unit should be present (it sees double duty as a supply train.) If
    not, all armies have their quality reduced by 1 level." -- checked
    once per side (not per unit): if the battle is in a Desert province
    and this side's ``armies`` include no ``ArmyType.CAMEL_CORPS``, every
    unit on the side gets the penalty, including any Elephants (the
    rulebook names "Camels" specifically here, not the broader "Beasts"
    grouping used for the nemesis table -- a confident reading, not a
    guess). Fully deterministic, no ``rng`` involved.

    **Fanaticism** (Phase 35, ``apply_fanaticism``): "An army fighting
    for a Divine/Good/Evil kingdom has a 50%/40%/25% chance of becoming
    fanatical" -- rolled once per army via ``turn/strength.py
    roll_fanaticism(kingdom.alignment, rng)``. Defaults to **off**
    (``False``): unlike ``combat_ability_level``, there's no data-absence
    condition that keeps this naturally silent, since every
    ``KingdomState`` always has a concrete, often-nonzero-chance
    ``Alignment`` -- an unconditional roll would consume a new ``rng``
    call for essentially every unit in every existing battle test (many
    already use ``Alignment.GOOD``, a real 40% chance), silently
    perturbing scripted RNG sequences across most of the pre-Phase-35
    test suite for a mechanic most callers don't need precision on. A
    caller that wants real fanaticism opts in explicitly.
    """

    desert_without_camels = terrain is Terrain.DESERT and not any(
        army.army_type is ArmyType.CAMEL_CORPS for army in armies
    )

    units = []
    for army in armies:
        kingdom = state.kingdoms[army.kingdom_id]
        is_home = province_coord == kingdom.home_province
        override = roll_elephants_strength(rng) if army.army_type is ArmyType.ELEPHANTS else None
        # Short-circuited: roll_fanaticism (and its rng.random() call) never
        # runs at all when apply_fanaticism is False -- see docstring.
        is_fanatical = apply_fanaticism and roll_fanaticism(kingdom.alignment, rng)
        strength = compute_effective_strength(
            army.army_type,
            kingdom.race,
            army.quality,
            terrain,
            is_defender=is_defender,
            is_home_province=is_home,
            is_fanatical=is_fanatical,
            desert_without_camels=desert_without_camels,
            base_strength_override=override,
            combat_ability_level=combat_ability_level,
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


def _combat_ability_for_terrain(terrain: Terrain) -> Ability:
    """Rulebook [6.3]: "Tactical Ability... (or Naval ability in Sea provinces)"."""

    return Ability.NAVAL if terrain is Terrain.SEA else Ability.TACTICAL


def _whale_forced_retreat_applies(army: ArmyState, battle_terrain: Terrain) -> bool:
    """Rulebook: "Whales... if they lose a battle in [a terrain other than Sea], they
    can retreat into a Sea hex automatically without fear of being destroyed."

    Only about the battle's own terrain, not the Whale army's own location
    otherwise -- a losing Whale army in a Sea-terrain battle follows the
    ordinary retreat/disband rules, same as anyone else.
    """

    return army.army_type is ArmyType.WHALES and battle_terrain is not Terrain.SEA


def _whale_sea_retreat_destination(army: ArmyState, state: GameState, bounds: MapBounds) -> HexCoord | None:
    """Nearest adjacent Sea-terrain province, regardless of ownership.

    Reuses ``find_retreat_destination``'s "first neighbor in this set"
    logic with a set of Sea provinces instead of friendly ones -- the
    rulebook says "into a Sea hex," not "into a *friendly* Sea hex."
    Returns ``None`` if no adjacent province is Sea terrain at all (not
    addressed by the rulebook; ``_retreat_or_disband`` falls back to its
    ordinary quality-based disband/mercenary rule in that case -- a
    documented limitation of this project's map data, not a guess).
    """

    sea_provinces = {coord for coord, p in state.provinces.items() if p.terrain is Terrain.SEA}
    return find_retreat_destination(army.location, bounds, sea_provinces)


def _select_side_commander(
    armies: list[ArmyState], state: GameState, ability: Ability, *, allow_garrison_fallback: bool
) -> Commander | None:
    """Group one side's armies by ``commanded_by`` and pick the Supreme Commander (rulebook [7.1]).

    Operates on ``armies`` alone (no ``BattleUnit``s needed) so this can
    run *before* ``_build_battle_units``, letting the winner's real
    ability level (Phase 30: read from ``LeaderState.skills``, 0 if that
    leader has none recorded) feed the strength formula, not just the
    duel. Unled armies are dropped unless ``allow_garrison_fallback`` --
    only the rulebook-specified defender fallback -- in which case they
    compete as a single "provincial garrison commander" candidate
    ("has no abilities", i.e. always level 0).
    """

    by_leader: dict[int | None, list[ArmyState]] = {}
    for army in armies:
        by_leader.setdefault(army.commanded_by, []).append(army)

    unled_armies = by_leader.pop(None, [])

    candidates = []
    for leader_id, led_armies in by_leader.items():
        level = 0
        leader = state.leaders.get(leader_id)
        if leader is not None and leader.skills is not None:
            level = leader.skills.pair_for_ability(ability)[0]
        candidates.append(Commander(leader_id=leader_id, contingent_size=len(led_armies), tactical_ability=level))
    if unled_armies and allow_garrison_fallback:
        candidates.append(provincial_garrison_commander(len(unled_armies)))

    return select_supreme_commander(candidates)


def _units_led_by(armies: list[ArmyState], units: list[BattleUnit], leader_id: int | None) -> list[BattleUnit]:
    """``armies``/``units`` must be the same length and order (as ``_build_battle_units`` produces)."""

    return [unit for army, unit in zip(armies, units) if army.commanded_by == leader_id]


@dataclass(slots=True)
class _DuelOutcome:
    attacker_commander_leader_id: int | None
    defender_commander_leader_id: int | None
    loser_side: str | None  # "attacker" / "defender" / None if no duel occurred


def _maybe_fight_duel(
    attacker_commander: Commander | None,
    defender_commander: Commander | None,
    attacker_armies: list[ArmyState],
    defender_armies: list[ArmyState],
    attacker_units: list[BattleUnit],
    defender_units: list[BattleUnit],
    rng: random.Random,
) -> _DuelOutcome:
    """Rulebook [7.1]: mutates ``attacker_units``/``defender_units`` in place if a duel loser is decided.

    Takes the already-selected Supreme Commanders (``fight_battle`` picks
    them early now, for the strength bonus too -- see the module
    docstring) rather than re-deriving them, so there's one single source
    of truth for "who commands this side." See the module docstring for
    why the duel's own outcome is approximated via
    ``estimate_win_probability`` rather than resolved (no Special
    Encounter Plan system exists). No-op (and no rng consumed) unless
    both sides have a real commander -- attackers have no garrison-style
    fallback, so this is skipped whenever no attacking army is led.
    """

    if attacker_commander is None or defender_commander is None:
        return _DuelOutcome(None, None, None)

    attacker_commander_units = _units_led_by(attacker_armies, attacker_units, attacker_commander.leader_id)
    defender_commander_units = _units_led_by(defender_armies, defender_units, defender_commander.leader_id)

    attacker_strength = sum(u.effective_strength for u in attacker_commander_units)
    defender_strength = sum(u.effective_strength for u in defender_commander_units)
    attacker_wins_duel = rng.random() < estimate_win_probability(attacker_strength, defender_strength)

    if attacker_wins_duel:
        loser_side, loser_units, target_list = "defender", defender_commander_units, defender_units
    else:
        loser_side, loser_units, target_list = "attacker", attacker_commander_units, attacker_units

    demoralized_by_id = {u.source_id: u for u in apply_duel_demoralization(loser_units)}
    for index, unit in enumerate(target_list):
        if unit.source_id in demoralized_by_id:
            target_list[index] = demoralized_by_id[unit.source_id]

    return _DuelOutcome(attacker_commander.leader_id, defender_commander.leader_id, loser_side)


def _apply_pursuit(
    losing_armies: list[ArmyState],
    winner_units: list[BattleUnit],
    state: GameState,
    terrain,
    report: BattleReport,
    rng: random.Random,
) -> set[int]:
    """Rulebook [7.3]: chase down some of a clean-swept, retreating loser's armies before they escape.

    Returns the set of army ids caught and destroyed (already removed
    from ``state`` and recorded on ``report``) -- callers should skip
    ``_retreat_or_disband`` for those.
    """

    retreating_units = []
    for army in losing_armies:
        kingdom = state.kingdoms[army.kingdom_id]
        pursued_quality = Quality(max(int(Quality.DEPLETED), int(army.quality) - 1))
        strength = compute_effective_strength(army.army_type, kingdom.race, pursued_quality, terrain, is_defender=True)
        retreating_units.append(BattleUnit(army.army_type, strength, source_id=army.army_id))

    pursuers = select_pursuers(winner_units, rng)
    outcomes = resolve_pursuit(pursuers, retreating_units, rng)

    destroyed_ids = {o.target.source_id for o in outcomes if o.target_destroyed}
    for army_id in destroyed_ids:
        report.pursuit_destroyed_army_ids.append(army_id)
        state.remove_army(army_id)
    return destroyed_ids


def fight_battle(
    state: GameState,
    attacker_kingdom_id: int,
    province_coord: HexCoord,
    attacker_army_ids: list[int],
    *,
    loser_retreats: bool = True,
    attacker_origin: HexCoord | None = None,
    apply_fanaticism: bool = False,
    rng: random.Random | None = None,
) -> BattleReport:
    """Resolve one battle at ``province_coord`` and apply its consequences to ``state``.

    ``apply_fanaticism`` (Phase 35, default off) opts into real per-army
    fanaticism rolls -- see ``_build_battle_units``'s docstring for why
    this isn't on by default.
    """

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

    ability = _combat_ability_for_terrain(province.terrain)
    attacker_commander = _select_side_commander(attacker_armies, state, ability, allow_garrison_fallback=False)
    defender_commander = _select_side_commander(defender_armies, state, ability, allow_garrison_fallback=True)
    attacker_ability_level = attacker_commander.tactical_ability if attacker_commander is not None else 0
    defender_ability_level = defender_commander.tactical_ability if defender_commander is not None else 0

    attacker_units = _build_battle_units(
        attacker_armies, state, is_defender=False, terrain=province.terrain, province_coord=province_coord, rng=rng,
        combat_ability_level=attacker_ability_level, apply_fanaticism=apply_fanaticism,
    )
    defender_units = _build_battle_units(
        defender_armies, state, is_defender=True, terrain=province.terrain, province_coord=province_coord, rng=rng,
        combat_ability_level=defender_ability_level, apply_fanaticism=apply_fanaticism,
    )

    duel = _maybe_fight_duel(
        attacker_commander, defender_commander, attacker_armies, defender_armies, attacker_units, defender_units, rng
    )

    battle_result = resolve_battle(
        attacker_units,
        defender_units,
        attacker_tactical_ability=attacker_ability_level,
        defender_tactical_ability=defender_ability_level,
        rng=rng,
    )

    defender_clean_swept = battle_result.winner == "attacker" and battle_result.defender_columns_won == 0
    attacker_clean_swept = battle_result.winner == "defender" and battle_result.attacker_columns_won == 0

    report = BattleReport(
        battle_result=battle_result,
        conquered=defender_clean_swept,
        attacker_commander_leader_id=duel.attacker_commander_leader_id,
        defender_commander_leader_id=duel.defender_commander_leader_id,
        duel_loser_side=duel.loser_side,
    )

    attacker_pursuit_destroyed: set[int] = set()
    if attacker_clean_swept and loser_retreats:
        attacker_pursuit_destroyed = _apply_pursuit(
            attacker_armies, defender_units, state, province.terrain, report, rng
        )
    defender_pursuit_destroyed: set[int] = set()
    if defender_clean_swept and loser_retreats:
        defender_pursuit_destroyed = _apply_pursuit(
            defender_armies, attacker_units, state, province.terrain, report, rng
        )

    for army in attacker_armies:
        if army.army_id in attacker_pursuit_destroyed:
            continue
        if battle_result.winner == "attacker":
            army.quality = roll_quality_change(army.quality, rng, is_winner=True)
            report.quality_changes[army.army_id] = army.quality
        elif attacker_clean_swept and _whale_forced_retreat_applies(army, province.terrain):
            bounds = MapBounds(*NORMAL_MAP_BOUNDS)
            destination = _whale_sea_retreat_destination(army, state, bounds)
            _retreat_or_disband(army, state, report, rng, destination=destination)
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
        if army.army_id in defender_pursuit_destroyed:
            continue
        if battle_result.winner == "defender":
            army.quality = roll_quality_change(army.quality, rng, is_winner=True)
            report.quality_changes[army.army_id] = army.quality
        elif defender_clean_swept and _whale_forced_retreat_applies(army, province.terrain):
            bounds = MapBounds(*NORMAL_MAP_BOUNDS)
            destination = _whale_sea_retreat_destination(army, state, bounds)
            _retreat_or_disband(army, state, report, rng, destination=destination)
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


@dataclass(slots=True)
class MultiAttackerParty:
    leader_id: int
    kingdom_id: int
    army_ids: list[int]
    origin_province: HexCoord


def fight_multi_attacker_battle(
    state: GameState,
    province_coord: HexCoord,
    parties: list[MultiAttackerParty],
    *,
    loser_retreats: bool = True,
    apply_fanaticism: bool = False,
    rng: random.Random | None = None,
) -> list[BattleReport]:
    """Rulebook [7.8] Multiple Contingents: partition several leaders' simultaneous
    attacks on ``province_coord`` into one or more battles, then fight each.

    See the module docstring for why this isn't automatically invoked
    from the single-leader execution path yet.

    **Which kingdom claims a jointly-won province** isn't specified by
    the rulebook for a united coalition of allied attackers -- resolved
    here as a documented heuristic: whichever kingdom contributed the
    largest combined contingent to that battle, the same "largest
    contingent" principle already used for [7.1]'s Supreme Commander
    selection. That kingdom's own party also supplies ``attacker_origin``
    for ``fight_battle()``'s forced-retreat-destination rule -- a
    simplification for a coalition that may not share one origin.

    **Also simplified**: ``fight_battle()`` itself only takes one
    ``attacker_kingdom_id`` to decide who a defender is allied with;
    for a united multi-kingdom group, that check runs only against the
    claiming kingdom's own alliances, not every coalition member's --
    generalizing it properly would need a broader change to
    ``fight_battle()``'s own signature, not attempted here.
    """

    rng = rng if rng is not None else random.Random()
    if not parties:
        raise ValueError("no attacking parties given")

    attackers = [Attacker(leader_id=p.leader_id, kingdom_id=p.kingdom_id, origin_province=p.origin_province) for p in parties]
    groups = group_attackers_into_battles(attackers, state.allied_kingdoms, rng)
    parties_by_leader = {p.leader_id: p for p in parties}

    reports = []
    for group in groups:
        combined_army_ids = [
            army_id for member in group for army_id in parties_by_leader[member.leader_id].army_ids
        ]

        contingent_sizes: dict[int, int] = {}
        for member in group:
            contingent_sizes[member.kingdom_id] = contingent_sizes.get(member.kingdom_id, 0) + len(
                parties_by_leader[member.leader_id].army_ids
            )
        claiming_kingdom_id = max(contingent_sizes, key=contingent_sizes.get)
        attacker_origin = next(
            parties_by_leader[member.leader_id].origin_province
            for member in group
            if member.kingdom_id == claiming_kingdom_id
        )

        report = fight_battle(
            state,
            claiming_kingdom_id,
            province_coord,
            combined_army_ids,
            loser_retreats=loser_retreats,
            attacker_origin=attacker_origin,
            apply_fanaticism=apply_fanaticism,
            rng=rng,
        )
        reports.append(report)

    return reports
