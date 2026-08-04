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
that group's army ids combined -- returning one ``MultiAttackerBattle``
per resulting battle (``leader_ids`` + its own ``BattleReport``), so a
caller driving several leaders at once can tell which report belongs to
which leader without re-deriving the (rng-consuming) grouping itself.
**Now reachable from real multi-leader play as of Phase 45**:
``turn/turn_processor.py run_turn()`` is a phase-by-phase (not
per-leader) orchestrator that detects same-phase LMOVEs converging on
one province and routes them through here -- see that module's
docstring for the detection rule and its own documented scope limits.
``execute_move()``/``plan_dispatch.py run_leader_plan()`` themselves are
unchanged and still only ever fight a single attacker's battle -- they
remain the right call for driving one leader's plan in isolation (most
of this project's own tests still do exactly that).

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
- **Fleets are a second, separate exception** (Phase 38, [7.2]):
  "Fleets fighting on land provinces would generally be reduced to
  Depleted status instead of being eliminated" -- unlike Whales, no
  forced retreat, just quality forced to ``DEPLETED`` *in place* instead
  of removal. Only the two branches that actually remove an army from
  ``state`` needed intercepting (``_fleet_avoids_elimination``): the
  outright "clean-swept, `loser_retreats=False`" destroy, and
  ``_retreat_or_disband``'s "no retreat destination, GREEN/DEPLETED"
  disband (now takes an ``avoid_elimination`` flag). A successful
  ordinary retreat already avoids elimination on its own, and becoming a
  mercenary already isn't elimination either, so neither needed
  changing. Same non-extension to Pursuit as Whales, for the same reason.
- **Whether a losing side even attempts to retreat vs. fights on** is a
  rulebook decision with no formula (capital status, wealth, retreat path,
  etc. -- see `turn/retreat.py`); exposed here as ``loser_retreats: bool``,
  the caller's call.
- **Every genuine battle death is recorded in ``GameState.battle_graveyard``**
  (Phase 60) -- the four sites here that actually remove an army from
  play (``_retreat_or_disband``'s no-retreat-destination disband,
  ``_apply_pursuit``'s catch-and-destroy, and each side's own
  clean-swept elimination) all call ``state.record_battle_death()``
  first, giving Skeletal Army and Bless's corpse-cleanup addendum
  (``turn/cast_execution.py``) something concrete to act on. A Fleet
  forced to ``DEPLETED`` in place, or a demoted-to-mercenary unit, isn't
  a death and isn't recorded -- only actual removal from ``state.armies``
  is.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ARMY_TABLE, ArmyType, is_overflight_unit
from ak_engine.models.discovery import Discovery
from ak_engine.models.enums import Ability, Maneuver
from ak_engine.models.game_state import ArmyState, GameState, LeaderState
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.race import Race
from ak_engine.models.treasure import RACE_LEADERSHIP_TREASURE
from ak_engine.turn.aftermath import roll_quality_change
from ak_engine.turn.battle_line import BattleUnit, estimate_win_probability, roll_terrain_line_length_cap
from ak_engine.turn.battle_resolution import BattleResult, resolve_battle
from ak_engine.turn.cast_execution import is_illusory_fog_affected_air_unit, quality_one_level_down
from ak_engine.turn.challenge_execution import resolve_challenge_combat
from ak_engine.turn.combat import Quality, direct_destruction_probability
from ak_engine.turn.discovery_effects import effective_skill_level
from ak_engine.turn.duel import Commander, apply_duel_demoralization, provincial_garrison_commander, select_supreme_commander
from ak_engine.turn.encounter import CHARACTER_HIT_POINTS, Combatant
from ak_engine.turn.initiative import character_initiative
from ak_engine.turn.merit_points import battle_quality_points
from ak_engine.turn.movement import NORMAL_MAP_BOUNDS, MapBounds
from ak_engine.turn.multiple_contingents import Attacker, group_attackers_into_battles
from ak_engine.turn.pursuit import select_pursuers, resolve_pursuit
from ak_engine.turn.retreat import attacker_retreat_candidates, find_retreat_destination
from ak_engine.turn.search_decode import SearchTactic
from ak_engine.turn.strength import (
    PHANTASMAL_ARMIES_BONUS_PER_LEVEL,
    compute_druidic_shortfall,
    compute_effective_strength,
    roll_elephants_strength,
    roll_fanaticism,
)

# Observation Balloons (Discovery.txt, Phase 270): "army strength is
# increased by only 5% per skill level" by Phantasmal Armies, instead of
# the base 15%, when the opposing Kingdom in a battle owns the
# Discovery -- see _build_battle_units's own Phase 270 addendum.
OBSERVATION_BALLOONS_PHANTASMAL_ARMIES_BONUS_PER_LEVEL = 0.05


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
    # Phase 231 -- GENERAL INTELLIGENCE REPORT's own raw material
    # (`report/turn_report.py record_battle_world_events()`). Both are
    # already computed locally in `fight_battle()` for its own
    # exploration-advantage lookup (`province_coord`/`defender_kingdom_id`
    # = `province.owner_kingdom_id` *before* any conquest this battle
    # causes) and its own parameter (`attacker_kingdom_id`) -- stored
    # here rather than re-derived, since a caller several layers away
    # (turn_report.py) has no other way to recover which two kingdoms
    # fought or where.
    province_coord: HexCoord | None = None
    attacker_kingdom_id: int | None = None
    defender_kingdom_id: int | None = None


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
    own_explored_percent: int = 0,
    enemy_explored_percent: int = 0,
    opponent_kingdom_ids: frozenset[int] = frozenset(),
    is_island: bool = False,
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

    **Exploration advantage** (Phase 69): ``own_explored_percent``/
    ``enemy_explored_percent`` are single side-level values (not
    per-army), computed once by ``fight_battle`` and applied uniformly
    to every unit on this side via ``turn/strength.py
    exploration_advantage_multiplier`` -- see ``fight_battle``'s own
    docstring for exactly which kingdom's ``ProvinceState.
    explored_percent_by_kingdom`` entry each side reads. Both default to
    0 (no advantage either way) for any caller that doesn't pass them.

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

    **Druidic ability** (Phase 41, rulebook [4.32]): a *led* army
    (``commanded_by`` is not ``None``) whose commander leads a race
    other than his own (both derived the same documented way as
    everywhere else in this project -- via each leader's own
    ``kingdom_id`` -> ``KingdomState.race``, since no per-character race
    is tracked) suffers a quality shortfall per ``turn/strength.py
    compute_druidic_shortfall``/``DRUID_TABLE`` if the commander's
    Druidic skill (``LeaderState.skills``, 0 if unrecorded) falls short
    of what the Druid Table requires for that race. Fully deterministic,
    no ``rng`` involved -- and structurally a no-op for same-kingdom
    commanding (the overwhelmingly common case), since a leader's own
    race always equals his own army's race unless the two came from
    *different* kingdoms (only reachable via Pick_Up attaching a
    co-located army regardless of ownership, or an army's owning
    kingdom changing after Leave/Disband).

    **Unled armies (under the garrison commander)** (Phase 42, same
    rulebook section): *"If a unit is under the garrison commander of a
    province, and is of a different race than the King, then the King's
    druidic ability is used"* -- ``king_druidic_shortfall_for`` resolves
    *which* King via ``province_coord``'s own ``ProvinceState.
    owner_kingdom_id`` (not necessarily the unled army's own
    ``kingdom_id`` -- an allied army defending alongside the owner's
    garrison is still judged against the *owning* kingdom's King, per
    the rulebook's literal wording), then finds that kingdom's King
    among ``state.leaders`` via the same ``is_king`` flag Phase 40 added
    for exactly this. No owning kingdom, or no King identified for it
    (an edge case this project's data can't always resolve, e.g. a
    captured province with no surviving King), falls back to 0 -- no
    penalty, not a guessed one. This closes the "held back" gap; unlike
    Phase 34's Duel garrison-commander fallback (which really has no
    ability data to draw on), an unled army's Druidic exposure runs
    through its province's King, not the garrison commander itself.

    **Illusory Fog** (Phase 207 addendum, wired Phase 249): looked up
    once per side via ``state.provinces.get(province_coord).
    illusory_fog_active`` (``False`` if the province is unknown), then
    combined per-army with ``turn/cast_execution.py is_illusory_fog_
    affected_air_unit(army.army_type, mystic_winds_active)`` --
    ``mystic_winds_active`` resolved by ``_mystic_winds_active_for()``,
    the same "derive from the commanding leader, ``False`` for an unled
    army" pattern ``_phantasmal_armies_level_for()`` already
    established. Fully deterministic, no ``rng`` involved.

    **Osteopathic Germ Warfare / Observation Balloons** (Discovery.txt,
    Phase 270): two anti-spell ward Discoveries whose own effect only
    applies *in battle, against the opposing side* -- not at Cast time,
    unlike every other anti-spell Discovery this project models (see
    ``turn/cast_execution.py``'s own Phase 270 addendum). ``opponent_
    kingdom_ids`` (the *other* side's own distinct ``kingdom_id`` set,
    resolved once by ``fight_battle()`` from its own ``attacker_armies``/
    ``defender_armies``) lets this function check, per army: Osteopathic
    Germ Warfare reduces a Skeletal Army unit (``ArmyState.is_skeletal``)
    by one quality level (``turn/cast_execution.py quality_one_level_
    down()``) before strength is computed, if any opposing Kingdom owns
    it; Observation Balloons reduces Phantasmal Armies' own strength
    bonus from 15% to 5% per level (``turn/strength.py
    phantasmal_armies_multiplier``'s own ``bonus_per_level`` override),
    same opposing-Kingdom check. Both default to inert (empty
    ``opponent_kingdom_ids``) for every pre-Phase-270 caller.

    **Island provinces** (Phase 282, ``is_island``): resolved once by
    ``fight_battle()`` from ``ProvinceState.is_island`` and passed
    straight through to ``turn/strength.py compute_effective_strength()``
    for every unit on this side -- see that function's own docstring for
    the land/Sea blend it runs. Defaults to ``False``, unaffected, for
    every pre-Phase-282 caller.

    **Race-matching legendary leadership item** (Phase 279 originally
    report-only, wired into real combat Phase 285): a *led* army
    (``commanded_by`` is not ``None``) whose commander holds the item
    from ``models/treasure.py RACE_LEADERSHIP_TREASURE`` matching this
    side's own ``kingdom.race`` (Excalibur for Human, etc.) gets a +1
    quality bonus via ``turn/strength.py compute_effective_strength()``'s
    own ``race_item_bonus`` parameter -- the same table and the same
    "commander only, no King-substitution carve-out for an unled army"
    rule ``turn/army_quality.py compute_army_modified_quality()`` already
    established for the ARMIES report's own peacetime display column
    (the user's own rulebook text names only the army's own commanding
    Hero or King). Checked once per unit via ``state.items_held_by()``,
    fully deterministic, no ``rng`` involved.
    """

    desert_without_camels = terrain is Terrain.DESERT and not any(
        army.army_type is ArmyType.CAMEL_CORPS for army in armies
    )
    province = state.provinces.get(province_coord)
    illusory_fog_active = province is not None and province.illusory_fog_active

    opponent_owns_osteopathic = any(
        Discovery.OSTEOPATHIC_GERM_WARFARE in state.kingdoms[kid].discoveries for kid in opponent_kingdom_ids
    )
    opponent_owns_balloons = any(
        Discovery.OBSERVATION_BALLOONS in state.kingdoms[kid].discoveries for kid in opponent_kingdom_ids
    )

    units = []
    for army in armies:
        kingdom = state.kingdoms[army.kingdom_id]
        is_home = province_coord == kingdom.home_province
        override = roll_elephants_strength(rng) if army.army_type is ArmyType.ELEPHANTS else None
        # Short-circuited: roll_fanaticism (and its rng.random() call) never
        # runs at all when apply_fanaticism is False -- see docstring.
        is_fanatical = apply_fanaticism and roll_fanaticism(kingdom.alignment, rng)
        druidic_shortfall = druidic_shortfall_for(army, state, kingdom.race, province_coord)
        phantasmal_armies_level = _phantasmal_armies_level_for(army, state)
        mystic_winds_active = _mystic_winds_active_for(army, state)
        illusory_fog_affected = illusory_fog_active and is_illusory_fog_affected_air_unit(
            army.army_type, mystic_winds_active
        )
        battle_quality = army.quality
        if army.is_skeletal and opponent_owns_osteopathic:
            battle_quality = quality_one_level_down(battle_quality)
        race_item_bonus = 0
        if army.commanded_by is not None:
            needed_treasure = RACE_LEADERSHIP_TREASURE.get(kingdom.race)
            if needed_treasure is not None and any(
                item.treasure == needed_treasure for item in state.items_held_by(army.commanded_by)
            ):
                race_item_bonus = 1
        phantasmal_armies_bonus_per_level = (
            OBSERVATION_BALLOONS_PHANTASMAL_ARMIES_BONUS_PER_LEVEL
            if phantasmal_armies_level > 0 and opponent_owns_balloons
            else PHANTASMAL_ARMIES_BONUS_PER_LEVEL
        )
        strength = compute_effective_strength(
            army.army_type,
            kingdom.race,
            battle_quality,
            terrain,
            is_defender=is_defender,
            is_home_province=is_home,
            is_fanatical=is_fanatical,
            desert_without_camels=desert_without_camels,
            druidic_shortfall=druidic_shortfall,
            race_item_bonus=race_item_bonus,
            base_strength_override=override,
            combat_ability_level=combat_ability_level,
            phantasmal_armies_level=phantasmal_armies_level,
            phantasmal_armies_bonus_per_level=phantasmal_armies_bonus_per_level,
            own_explored_percent=own_explored_percent,
            enemy_explored_percent=enemy_explored_percent,
            illusory_fog_affected=illusory_fog_affected,
            is_island=is_island,
        )
        rear_targeting_blocked = is_overflight_unit(army.army_type) and druidic_shortfall > 0
        units.append(
            BattleUnit(
                army.army_type,
                strength,
                source_id=army.army_id,
                druidic_rear_targeting_blocked=rear_targeting_blocked,
                led_by_insufficient_druid=druidic_shortfall > 0,
            )
        )
    return units


def druidic_shortfall_for(army: ArmyState, state: GameState, army_race: Race, province_coord: HexCoord) -> int:
    """Rulebook [4.32] Druid Table -- see ``_build_battle_units``'s docstring for scope.

    Public (Phase 279, dropped its leading underscore): the ARMIES
    report's own "Modified Quality" column (``turn/army_quality.py``)
    reuses this exact resolution outside of an active battle -- a
    peacetime army still has a real commander (or lacks one) the same
    way, so no logic changed, only visibility.
    """

    if army.commanded_by is not None:
        leader = state.leaders.get(army.commanded_by)
        if leader is None or leader.kingdom_id is None:
            return 0
        leader_race = state.kingdoms[leader.kingdom_id].race
        leader_druidic_skill = effective_skill_level(state, leader, Ability.DRUID)
        return compute_druidic_shortfall(leader_race, army_race, leader_druidic_skill)

    return king_druidic_shortfall_for(state, army_race, province_coord)


def king_druidic_shortfall_for(state: GameState, army_race: Race, province_coord: HexCoord) -> int:
    """Phase 42, rulebook [4.32]: "If a unit is under the garrison commander of a
    province, and is of a different race than the King, then the King's
    druidic ability is used" -- the province's *owning* kingdom's King
    (``ProvinceState.owner_kingdom_id`` + ``LeaderState.is_king``, Phase
    40), not necessarily the unled army's own kingdom. No owning kingdom,
    or no King identified for it, falls back to 0 -- insufficient data,
    not a guessed penalty. Public since Phase 279 -- see
    ``druidic_shortfall_for``'s own note.
    """

    province = state.provinces.get(province_coord)
    if province is None or province.owner_kingdom_id is None:
        return 0
    king = find_king_of_kingdom(state, province.owner_kingdom_id)
    if king is None or king.kingdom_id is None:
        return 0
    king_race = state.kingdoms[king.kingdom_id].race
    king_druidic_skill = effective_skill_level(state, king, Ability.DRUID)
    return compute_druidic_shortfall(king_race, army_race, king_druidic_skill)


def find_king_of_kingdom(state: GameState, kingdom_id: int) -> LeaderState | None:
    for leader in state.leaders.values():
        if leader.kingdom_id == kingdom_id and leader.is_king:
            return leader
    return None


def _phantasmal_armies_level_for(army: ArmyState, state: GameState) -> int:
    """Phase 59, Phantasmal Armies (Regolamento AK.txt [4.23.2]): an unled army has no
    commander to carry the buff, so it's simply 0 -- unlike Druidic
    ability, the rulebook gives no garrison-commander substitute for this
    spell.
    """

    if army.commanded_by is None:
        return 0
    commander = state.leaders.get(army.commanded_by)
    if commander is None:
        return 0
    return commander.phantasmal_armies_level


def _mystic_winds_active_for(army: ArmyState, state: GameState) -> bool:
    """Phase 249, Illusory Fog's "and those affected by 'Mystic Winds'" clause:
    an unled army has no commander to carry the flag, so it's simply
    ``False`` -- the same "no commander, no buff" shape ``_phantasmal_
    armies_level_for()`` already established, since ``LeaderState.
    mystic_winds_active`` (Phase 204) is only ever set on the leader a
    Mystic Winds cast targets.
    """

    if army.commanded_by is None:
        return False
    commander = state.leaders.get(army.commanded_by)
    if commander is None:
        return False
    return commander.mystic_winds_active


def _clear_mystic_winds_before_battle(armies: list[ArmyState], state: GameState) -> None:
    """Phase 250: clears ``LeaderState.mystic_winds_active`` for every commander
    of an army entering this battle -- "the spell ends just before the
    leader gets involved in any military battle between armies," rulebook
    text quoted in full in ``turn/cast_execution.py``'s own Phase 204
    addendum. Called from ``fight_battle()`` itself, both sides, before
    ``_build_battle_units()`` reads ``_mystic_winds_active_for()`` -- so a
    leader whose own army is *in* this battle never gets Illusory Fog's
    Mystic-Winds-affected treatment for it, even though the flag was true
    a moment ago.

    Deliberately does **not** touch ``ArmyState.movement_points`` --
    "re-deriving each affected army's movement" (the Phase 204 addendum's
    own words) has nothing to re-derive *to*: this project has no
    per-``ArmyType`` base movement table anywhere (``GameState``'s own
    module docstring already confirms ``ArmyState.movement_points`` has
    no real consumer), so freshly recruited armies default it to 0, not
    some army-type-specific normal value. Resetting it to any concrete
    number here would be a guess, not a sourced fact -- the same
    confirmed-absent boundary Part Sea's `terrain_override`/Bless's own
    `tax_modifier_percent` already carry for their own unbuilt consumers.
    """

    seen_leader_ids: set[int] = set()
    for army in armies:
        if army.commanded_by is None or army.commanded_by in seen_leader_ids:
            continue
        seen_leader_ids.add(army.commanded_by)
        commander = state.leaders.get(army.commanded_by)
        if commander is not None:
            commander.mystic_winds_active = False


def _retreat_or_disband(
    army: ArmyState,
    state: GameState,
    report: BattleReport,
    rng: random.Random,
    *,
    destination: HexCoord | None,
    avoid_elimination: bool = False,
    led_by_insufficient_druid: bool = False,
) -> None:
    """``avoid_elimination`` (Phase 38): the caller's way of saying this army must not be
    removed from ``state`` even if it would otherwise disband -- see
    ``_fleet_avoids_elimination``. Only changes the GREEN/DEPLETED
    "no retreat destination" branch, since that's the only branch here
    that actually removes the army; the mercenary branch already leaves
    it in ``state.armies``.

    ``led_by_insufficient_druid`` (Phase 298): forwarded to ``roll_
    quality_change()`` for completeness -- see that function's own
    docstring for why it's currently a no-op on this particular
    ``retreated=True`` call (the penalty only ever gates the "winner
    improves" branch), kept here so this call stays correct if that
    scope is ever widened.
    """

    if destination is not None:
        army.location = destination
        army.quality = roll_quality_change(
            army.quality, rng, is_winner=False, retreated=True, led_by_insufficient_druid=led_by_insufficient_druid
        )
        report.quality_changes[army.army_id] = army.quality
        report.retreated_army_ids.append(army.army_id)
        return

    if army.quality in (Quality.GREEN, Quality.DEPLETED):
        if avoid_elimination:
            army.quality = Quality.DEPLETED
            report.quality_changes[army.army_id] = army.quality
            return
        report.disbanded_army_ids.append(army.army_id)
        state.record_battle_death(army.location, army.army_type, army.quality, army.kingdom_id)
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


def _fleet_avoids_elimination(army: ArmyState, battle_terrain: Terrain) -> bool:
    """Rulebook [7.2]: "Fleets fighting on land provinces would generally be
    reduced to Depleted status instead of being eliminated."

    A different, separate special case from Whales' own (Phase 37):
    Fleets don't get a forced retreat, just quality-forced-to-DEPLETED
    survival in place -- so this only ever needs to intercept the two
    branches that actually remove an army from ``state`` (the outright
    "clean-swept, not retreating" destroy, and ``_retreat_or_disband``'s
    "no retreat destination, GREEN/DEPLETED" disband). A successful
    ordinary retreat already avoids elimination on its own (no special
    casing needed), and becoming a mercenary already isn't elimination
    either. Like Whales, this is **not** extended to Pursuit ([7.3]) --
    a separate mechanic from the battle-resolution elimination decision
    this rule is actually about; a retreating Fleet can still be caught
    and destroyed by ``_apply_pursuit``.
    """

    return army.army_type is ArmyType.FLEET and battle_terrain is not Terrain.SEA


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
        if leader is not None:
            level = effective_skill_level(state, leader, ability)
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


def _commander_combatant(commander: Commander, state: GameState) -> Combatant:
    """Build an ``encounter.Combatant`` for a Supreme Commander (Phase 49, opt-in real duel combat).

    ``leader_id=None`` (the provincial garrison commander, rulebook
    [7.1]: "has no abilities") gets Melee skill 0 and no Neutral-Kingdom
    bonus -- there's no real character to look either one up for.
    """

    if commander.leader_id is None:
        return Combatant(name="garrison commander", hit_points=CHARACTER_HIT_POINTS)

    leader = state.leaders.get(commander.leader_id)
    melee_skill = 0
    archery_skill = 0
    temper = None
    if leader is not None:
        melee_skill = effective_skill_level(state, leader, Ability.MELEE)
        archery_skill = effective_skill_level(state, leader, Ability.ARCHERY)
        temper = leader.temper

    neutral_bonus = False
    if leader is not None and leader.kingdom_id is not None:
        kingdom = state.kingdoms.get(leader.kingdom_id)
        neutral_bonus = kingdom is not None and kingdom.alignment is Alignment.NEUTRAL

    return Combatant(
        name=f"leader {commander.leader_id}",
        hit_points=CHARACTER_HIT_POINTS,
        melee_skill=melee_skill,
        archery_skill=archery_skill,
        neutral_duelist_bonus=neutral_bonus,
        temper=temper,
    )


def _maybe_fight_duel(
    attacker_commander: Commander | None,
    defender_commander: Commander | None,
    attacker_armies: list[ArmyState],
    defender_armies: list[ArmyState],
    attacker_units: list[BattleUnit],
    defender_units: list[BattleUnit],
    rng: random.Random,
    *,
    state: GameState | None = None,
    use_real_duel_combat: bool = False,
    duel_maneuvers: list[Maneuver | SearchTactic] | None = None,
) -> _DuelOutcome:
    """Rulebook [7.1]: mutates ``attacker_units``/``defender_units`` in place if a duel loser is decided.

    Takes the already-selected Supreme Commanders (``fight_battle`` picks
    them early now, for the strength bonus too -- see the module
    docstring) rather than re-deriving them, so there's one single source
    of truth for "who commands this side." No-op (and no rng consumed)
    unless both sides have a real commander -- attackers have no
    garrison-style fallback, so this is skipped whenever no attacking
    army is led.

    **``use_real_duel_combat`` (Phase 49, default ``False``)**: the
    duel's own outcome is still approximated via
    ``estimate_win_probability`` by default -- an opt-in flag, the same
    pattern Phase 35 used for fanaticism, to avoid perturbing every
    existing scripted-``rng`` test sequence in this project with a
    variable-length combat resolution. When ``True`` (and ``state`` is
    given), resolves a real ``turn/encounter.py`` duel between the two
    commanders instead. **Critically, the losing commander is never
    killed even though the encounter resolver tracks hit points reaching
    0** -- rulebook [7.1] only says "the armies which were led by the
    loser of the duel will become demoralized," never that the duel
    loser himself dies; character death is the *generic* Encounter
    combat rule ([5.0]), not this specific one, so this function reads
    only ``result.winner`` and otherwise ignores the resolved hit-point
    state. If the encounter resolver's own defensive round cap is
    somehow exhausted with neither combatant "dead" (astronomically
    unlikely at 10 hit points each), that's treated as no duel occurring
    at all (``loser_side=None``) -- an explicit, documented fallback, not
    a guess.

    **``duel_maneuvers`` (Phase 273)**: previously this always resolved
    Melee, since no Encounter Plan data exists anywhere in this project
    to know which tactic a Supreme Commander would actually choose --
    "Melee needs no skill prerequisite... making it the one defensible
    default" was this function's own prior reasoning. Rulebook [5.10]
    confirms a Duel *is* governed by "the Special Encounter Plans of the
    two supreme commanders" -- the same Fire-Arrow-then-Melee tactic
    list Challenge/Pursue already read from a real decoded order
    (``turn/challenge_execution.py``'s own Phase 273 note) -- but this
    project has no parser/decoder anywhere for a standing Special
    Encounter Plan tied to a leader (distinct from the one-off tactics a
    CHALLENGE/PURSUE order itself carries), the same "no real order-file
    shape ever seen" category already established for Treat/Break
    Treaty/Call-For-Vote. Rather than invent that data, ``duel_maneuvers``
    is an optional, caller-supplied tactic list -- ``None`` (the default,
    every existing caller) reproduces the exact prior always-Melee
    behavior and RNG consumption unchanged; a caller who does have real
    plan data for this Duel can supply it once a real source exists.

    **Personal-Combat spells (Phase 291)**: ``duel_maneuvers`` entries
    may now be either a bare ``Maneuver`` (Melee/Fire Arrow, unchanged
    from Phase 273) or a full ``turn/search_decode.py SearchTactic``
    (``CAST`` with its own spell id) -- normalized to ``SearchTactic``
    internally, then walked via ``turn/challenge_execution.py resolve_
    challenge_combat()``, the same Personal-Combat spell dispatch
    Challenge/Pursue already reuse (that module's own Phase 290/291
    addenda). ``_commander_combatant``'s own ``leader_id=None`` case
    (the garrison commander, "has no abilities") has no real
    ``LeaderState`` -- ``resolve_challenge_combat()`` accepts ``None``
    for either side and treats it exactly like Search/Challenge already
    treat missing skill/alignment data: a leaderless caster's ``CAST``
    tactic is a silent no-op, and a leaderless target is read as an
    ordinary, alignment-unrecorded opponent.

    **A successful Charm (or Augur Combat cast first and shirking) is
    read as no duel occurring at all** (``loser_side=None``, the exact
    same fallback the docstring above already uses for an exhausted
    round cap) -- [7.1] describes no "commander flees the duel" outcome,
    so this is a documented interpretation of an outcome the rulebook
    doesn't address here, not a guess at a new demoralization rule.
    Augur Combat's own "cast later -> acts as Flee" branch stays the
    same confirmed, unmodeled gap it already is for Challenge/Pursue (no
    Flee tactic/chance table exists for a Duel either).
    """

    if attacker_commander is None or defender_commander is None:
        return _DuelOutcome(None, None, None)

    attacker_commander_units = _units_led_by(attacker_armies, attacker_units, attacker_commander.leader_id)
    defender_commander_units = _units_led_by(defender_armies, defender_units, defender_commander.leader_id)

    if use_real_duel_combat and state is not None:
        attacker_combatant = _commander_combatant(attacker_commander, state)
        defender_combatant = _commander_combatant(defender_commander, state)
        attacker_leader = (
            state.leaders.get(attacker_commander.leader_id) if attacker_commander.leader_id is not None else None
        )
        defender_leader = (
            state.leaders.get(defender_commander.leader_id) if defender_commander.leader_id is not None else None
        )
        tactics = [tactic if isinstance(tactic, SearchTactic) else SearchTactic(tactic) for tactic in (duel_maneuvers or [])]
        combat_result = resolve_challenge_combat(
            tactics, attacker_leader, attacker_combatant, defender_leader, defender_combatant, state, rng
        )
        # `combat_result.winner is None` also covers a successful Charm/
        # Augur-Combat flee (`combat_result.fled`) -- see this function's
        # own Phase 291 addendum for why that's read as "no duel
        # occurred" rather than a new demoralization outcome.
        if combat_result.winner is None:
            return _DuelOutcome(attacker_commander.leader_id, defender_commander.leader_id, None)
        attacker_wins_duel = combat_result.winner == "a"
    else:
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
    *,
    is_island: bool = False,
) -> set[int]:
    """Rulebook [7.3]: chase down some of a clean-swept, retreating loser's armies before they escape.

    Returns the set of army ids caught and destroyed (already removed
    from ``state`` and recorded on ``report``) -- callers should skip
    ``_retreat_or_disband`` for those.

    ``is_island`` (Phase 282): the same province-level fact `fight_
    battle()` already resolved for the main battle itself, passed
    through unchanged so a retreating army's own strength during the
    chase honors it too -- see `turn/strength.py compute_effective_
    strength()`'s own docstring.
    """

    retreating_units = []
    for army in losing_armies:
        kingdom = state.kingdoms[army.kingdom_id]
        pursued_quality = Quality(max(int(Quality.DEPLETED), int(army.quality) - 1))
        strength = compute_effective_strength(
            army.army_type, kingdom.race, pursued_quality, terrain, is_defender=True, is_island=is_island
        )
        retreating_units.append(BattleUnit(army.army_type, strength, source_id=army.army_id))

    pursuers = select_pursuers(winner_units, rng)
    outcomes = resolve_pursuit(pursuers, retreating_units, rng)

    destroyed_ids = {o.target.source_id for o in outcomes if o.target_destroyed}
    for army_id in destroyed_ids:
        report.pursuit_destroyed_army_ids.append(army_id)
        destroyed_army = state.armies[army_id]
        state.record_battle_death(destroyed_army.location, destroyed_army.army_type, destroyed_army.quality, destroyed_army.kingdom_id)
        state.remove_army(army_id)
    return destroyed_ids


def _record_battle_merit(
    state: GameState,
    terrain: Terrain,
    battle_result: BattleResult,
    attacker_commander_leader_id: int | None,
    defender_commander_leader_id: int | None,
    attacker_armies: list[ArmyState],
    defender_armies: list[ArmyState],
) -> None:
    """Phase 254: rulebook page 51's Marshal/Admiral formula
    (``turn/merit_points.py``'s own module docstring, "TABELLA DELLE
    CARICHE IMPERIALI") -- credits the winning side's own commander,
    debits the losing side's, for a battle *commanded* by each. Closes
    the gap that formula's own docstring flagged: "no battle-outcome
    call site in this project attributes a fought battle to a specific
    commanding leader's cumulative Merit Point history yet."

    Only a side's own Supreme Commander (Phase 30/49's real duel-commander
    selection -- ``None`` for an unled side, e.g. the defender's own
    garrison-commander fallback, rulebook [7.1]: "has no abilities") has a
    ``LeaderState.merit_tally`` to credit or debit; an unled side's
    outcome simply isn't a "battaglia comandata" (a battle *commanded*)
    for anyone, so nothing is recorded for it -- not a guess, the
    rulebook phrase itself supplies the condition.

    A ``"tie"`` result (``BattleResult.winner``, ``turn/battle_resolution.py``)
    records nothing for either side: the rulebook's own "vinta"/"persa"
    wording doesn't address a tie, so this stays a documented no-op
    rather than a guessed reading -- the same category of gap
    ``merit_point_tiebreak_key()``'s own kingdom-less-Hero ``(0, 0)``
    fallback already documents.

    **Phase 308**: the flat "+1 per enemy unit if won, -1 per own unit
    if lost" rule quoted above is superseded by a real, sourced quality
    table (``turn/merit_points.py MARSHAL_QUALITY_POINTS``/
    ``battle_quality_points()``, Regolamento AK.txt's own "NUOVE REGOLE"
    appendix) -- this function now sums that table over the *entire*
    losing side's own committed ``ArmyState`` list, not just casualties:
    the rulebook text credits the quality of the army *fought*, and
    double-counting against the battle's own separate quality-change/
    elimination outcome would misread "la qualità delle unità sconfitte"
    as "casualties inflicted," a different, unstated claim -- the same
    "count everything fielded" reading this function's own pre-Phase-308
    version already established. The losing side's own armies (used for
    the winner's credit) and the same armies again (for the loser's own
    debit) are the same list by construction (one side's army *is* the
    other's enemy) -- a single ``points`` total serves both below.
    ``battle_quality_points()``'s own ``is_attacker`` flag reads whether
    the *losing* side was the attacker (needed for the Garrison
    modifier), independent of who won.
    """

    if battle_result.winner == "tie":
        return

    is_naval = terrain is Terrain.SEA
    if battle_result.winner == "attacker":
        winner_leader_id = attacker_commander_leader_id
        loser_leader_id = defender_commander_leader_id
        losing_armies, losing_side_is_attacker = defender_armies, False
    else:
        winner_leader_id = defender_commander_leader_id
        loser_leader_id = attacker_commander_leader_id
        losing_armies, losing_side_is_attacker = attacker_armies, True

    points = sum(
        battle_quality_points(army.army_type, army.quality, is_attacker=losing_side_is_attacker)
        for army in losing_armies
    )

    if winner_leader_id is not None:
        winner_leader = state.leaders.get(winner_leader_id)
        if winner_leader is not None:
            if is_naval:
                winner_leader.merit_tally.naval_battles_won_points += points
            else:
                winner_leader.merit_tally.land_battles_won_points += points

    if loser_leader_id is not None:
        loser_leader = state.leaders.get(loser_leader_id)
        if loser_leader is not None:
            if is_naval:
                loser_leader.merit_tally.naval_battles_lost_points += points
            else:
                loser_leader.merit_tally.land_battles_lost_points += points


def _direct_destruction_probabilities(battle_result: BattleResult) -> dict[int, float]:
    """Phase 371: for each column with a real winner, the real,
    confirmed probability (``turn/combat.py direct_destruction_
    probability``, Phase 347/348) that its losing side's own front-line
    unit -- "the alive, first-line loser of its column" the source's own
    eligibility rule names -- is destroyed outright in the direct
    contest, keyed by that unit's own ``army_id``.

    A per-column tie (``bres == 0``) has no loser and contributes
    nothing. Only each column's own front unit (index 0, the same unit
    ``turn/battle_line.py column_strength`` already treats as "first
    line") is eligible -- a second-line unit was never in contention for
    this column's own contest.
    """

    probabilities: dict[int, float] = {}
    for column in battle_result.columns:
        if column.bres == 0:
            continue
        attacker_front = column.attacker_units[0]
        defender_front = column.defender_units[0]
        attacker_speed = ARMY_TABLE[attacker_front.army_type].speed
        defender_speed = ARMY_TABLE[defender_front.army_type].speed
        if column.bres > 0:
            loser_unit, winner_speed, loser_speed = defender_front, attacker_speed, defender_speed
        else:
            loser_unit, winner_speed, loser_speed = attacker_front, defender_speed, attacker_speed
        if loser_unit.source_id is None:
            continue
        probabilities[loser_unit.source_id] = direct_destruction_probability(column.bres, winner_speed, loser_speed)
    return probabilities


def fight_battle(
    state: GameState,
    attacker_kingdom_id: int,
    province_coord: HexCoord,
    attacker_army_ids: list[int],
    *,
    loser_retreats: bool = True,
    attacker_origin: HexCoord | None = None,
    apply_fanaticism: bool = False,
    use_real_duel_combat: bool = False,
    duel_maneuvers: list[Maneuver | SearchTactic] | None = None,
    rng: random.Random | None = None,
) -> BattleReport:
    """Resolve one battle at ``province_coord`` and apply its consequences to ``state``.

    ``apply_fanaticism`` (Phase 35, default off) opts into real per-army
    fanaticism rolls -- see ``_build_battle_units``'s docstring for why
    this isn't on by default. ``use_real_duel_combat`` (Phase 49, default
    off) opts into a real duel between the two Supreme Commanders instead
    of the strength-ratio approximation -- see ``_maybe_fight_duel``'s
    docstring for why this isn't on by default either. ``duel_maneuvers``
    (Phase 273, default ``None``) optionally supplies the Special
    Encounter Plan tactic order for that real duel, so it can resolve
    Fire Arrow before Melee when the caller has real plan data -- see
    ``_maybe_fight_duel``'s own Phase 273 note; ``None`` reproduces the
    prior always-Melee behavior unchanged.
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

    # Phase 250, Mystic Winds' own Phase 204 addendum: "The spell ends just
    # before the leader gets involved in any military battle between
    # armies." Every real army-vs-army battle in this project funnels
    # through this one function -- move_execution.py, pursue_execution.py,
    # turn_processor.py's forced-rebattle path, and fight_multi_attacker_
    # battle() (which itself calls this function once per group) all call
    # fight_battle() directly, so clearing here covers every entry point
    # named in that addendum without needing to touch any of them.
    _clear_mystic_winds_before_battle(attacker_armies, state)
    _clear_mystic_winds_before_battle(defender_armies, state)

    # Phase 168: the province's real current terrain, honoring Part
    # Sea/Flood's own terrain_override if set -- see ProvinceState.
    # effective_terrain()'s own docstring for why every mechanics call
    # site in this function uses this instead of the raw .terrain.
    terrain = province.effective_terrain()
    # Island provinces (Phase 282) -- see turn/strength.py compute_
    # effective_strength()'s own docstring for the land/Sea blend this
    # feeds. Project-original, user-confirmed (2026-07-29) optional
    # Super AK variant rule; False (no effect) for every ordinary game.
    is_island = province.is_island

    ability = _combat_ability_for_terrain(terrain)
    attacker_commander = _select_side_commander(attacker_armies, state, ability, allow_garrison_fallback=False)
    defender_commander = _select_side_commander(defender_armies, state, ability, allow_garrison_fallback=True)
    attacker_ability_level = attacker_commander.tactical_ability if attacker_commander is not None else 0
    defender_ability_level = defender_commander.tactical_ability if defender_commander is not None else 0

    # Exploration advantage (Phase 69, rulebook [6.3]): each side's own
    # exploration reads province.explored_percent_by_kingdom for its own
    # kingdom_id (the attacker's, and the defending *province's owner*'s
    # -- an allied co-defender not the owner isn't separately tracked,
    # see models/game_state.py's own docstring). Missing entries default
    # to 0, a neutral "no advantage" default, not a guess.
    defender_kingdom_id = province.owner_kingdom_id
    attacker_explored = province.explored_percent_by_kingdom.get(attacker_kingdom_id, 0)
    defender_explored = (
        province.explored_percent_by_kingdom.get(defender_kingdom_id, 0) if defender_kingdom_id is not None else 0
    )

    attacker_kingdom_ids = frozenset(army.kingdom_id for army in attacker_armies if army.kingdom_id is not None)
    defender_kingdom_ids = frozenset(army.kingdom_id for army in defender_armies if army.kingdom_id is not None)

    attacker_units = _build_battle_units(
        attacker_armies, state, is_defender=False, terrain=terrain, province_coord=province_coord, rng=rng,
        combat_ability_level=attacker_ability_level, apply_fanaticism=apply_fanaticism,
        own_explored_percent=attacker_explored, enemy_explored_percent=defender_explored,
        opponent_kingdom_ids=defender_kingdom_ids, is_island=is_island,
    )
    defender_units = _build_battle_units(
        defender_armies, state, is_defender=True, terrain=terrain, province_coord=province_coord, rng=rng,
        combat_ability_level=defender_ability_level, apply_fanaticism=apply_fanaticism,
        own_explored_percent=defender_explored, enemy_explored_percent=attacker_explored,
        opponent_kingdom_ids=attacker_kingdom_ids, is_island=is_island,
    )

    duel = _maybe_fight_duel(
        attacker_commander, defender_commander, attacker_armies, defender_armies, attacker_units, defender_units, rng,
        state=state, use_real_duel_combat=use_real_duel_combat, duel_maneuvers=duel_maneuvers,
    )

    # Phase 296: rulebook [1.6]'s own Terrain Table line-length shortening
    # -- turn/battle_line.py roll_terrain_line_length_cap()'s own docstring
    # -- was implemented (Phase 6) but never actually rolled by this, the
    # sole production caller of resolve_battle(), so it (and the Phase 64
    # numeric-superiority outflanking bonus that depends on it) silently
    # never applied in any real battle. Rolled here, once, against the
    # same real terrain already resolved above.
    terrain_line_length_cap = roll_terrain_line_length_cap(terrain, rng)

    battle_result = resolve_battle(
        attacker_units,
        defender_units,
        terrain_line_length_cap=terrain_line_length_cap,
        attacker_tactical_ability=attacker_ability_level,
        defender_tactical_ability=defender_ability_level,
        is_first_turn=state.turn_number <= 1,
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
        province_coord=province_coord,
        attacker_kingdom_id=attacker_kingdom_id,
        defender_kingdom_id=defender_kingdom_id,
    )

    _record_battle_merit(
        state, terrain, battle_result,
        duel.attacker_commander_leader_id, duel.defender_commander_leader_id,
        attacker_armies, defender_armies,
    )

    # Phase 298: rulebook [7.5]'s own Druidic insufficient-ability quality-
    # improve-chance penalty (turn/aftermath.py roll_quality_change()'s
    # own led_by_insufficient_druid parameter) was fully implemented but
    # never actually threaded from here, even though druidic_shortfall is
    # already computed per-army above (BattleUnit.led_by_insufficient_
    # druid, set alongside the analogous druidic_rear_targeting_blocked
    # flag). One lookup, built once, covers every quality-change call
    # site below regardless of which side/branch an army falls into.
    led_by_insufficient_druid_by_army_id = {
        unit.source_id: unit.led_by_insufficient_druid for unit in (*attacker_units, *defender_units)
    }

    # Phase 371: real, confirmed per-column direct destruction (turn/
    # combat.py direct_destruction_probability, Phase 347/348) -- see
    # _direct_destruction_probabilities' own docstring. Only consulted
    # below for an army whose own side neither swept the battle nor won
    # it outright: a clean-swept side already has its own fully-modeled
    # fate (retreat, pursuit, Whale/Fleet special cases, or outright
    # elimination), and an overall-winning side's own per-army branch is
    # a quality-improve roll, not a loss -- reconciling a single column's
    # own bad result against either of those established paths is a
    # separate, larger design question, deliberately left for a future
    # phase (see ak_engine/README.md).
    direct_destruction_probability_by_army_id = _direct_destruction_probabilities(battle_result)

    attacker_pursuit_destroyed: set[int] = set()
    if attacker_clean_swept and loser_retreats:
        attacker_pursuit_destroyed = _apply_pursuit(
            attacker_armies, defender_units, state, terrain, report, rng, is_island=is_island
        )
    defender_pursuit_destroyed: set[int] = set()
    if defender_clean_swept and loser_retreats:
        defender_pursuit_destroyed = _apply_pursuit(
            defender_armies, attacker_units, state, terrain, report, rng, is_island=is_island
        )

    for army in attacker_armies:
        if army.army_id in attacker_pursuit_destroyed:
            continue
        led_by_insufficient_druid = led_by_insufficient_druid_by_army_id.get(army.army_id, False)
        if battle_result.winner == "attacker":
            army.quality = roll_quality_change(
                army.quality, rng, is_winner=True, led_by_insufficient_druid=led_by_insufficient_druid
            )
            report.quality_changes[army.army_id] = army.quality
        elif attacker_clean_swept and _whale_forced_retreat_applies(army, terrain):
            bounds = MapBounds(*NORMAL_MAP_BOUNDS)
            destination = _whale_sea_retreat_destination(army, state, bounds)
            _retreat_or_disband(
                army, state, report, rng, destination=destination,
                led_by_insufficient_druid=led_by_insufficient_druid,
            )
        elif attacker_clean_swept and loser_retreats:
            bounds = MapBounds(*NORMAL_MAP_BOUNDS)
            if attacker_origin is not None:
                destination = attacker_retreat_candidates(attacker_origin, bounds)[0]
            else:
                friendly = state.friendly_provinces_for(attacker_kingdom_id) - {province_coord}
                destination = find_retreat_destination(army.location, bounds, friendly)
            _retreat_or_disband(
                army, state, report, rng, destination=destination,
                avoid_elimination=_fleet_avoids_elimination(army, terrain),
                led_by_insufficient_druid=led_by_insufficient_druid,
            )
        elif attacker_clean_swept and _fleet_avoids_elimination(army, terrain):
            army.quality = Quality.DEPLETED
            report.quality_changes[army.army_id] = army.quality
        elif attacker_clean_swept:
            report.destroyed_army_ids.append(army.army_id)
            state.record_battle_death(province_coord, army.army_type, army.quality, army.kingdom_id)
            state.remove_army(army.army_id)
        elif rng.random() < direct_destruction_probability_by_army_id.get(army.army_id, 0.0):
            report.destroyed_army_ids.append(army.army_id)
            state.record_battle_death(province_coord, army.army_type, army.quality, army.kingdom_id)
            state.remove_army(army.army_id)
        else:
            army.quality = roll_quality_change(
                army.quality, rng, is_winner=False, retreated=False,
                led_by_insufficient_druid=led_by_insufficient_druid,
            )
            report.quality_changes[army.army_id] = army.quality

    for army in defender_armies:
        if army.army_id in defender_pursuit_destroyed:
            continue
        led_by_insufficient_druid = led_by_insufficient_druid_by_army_id.get(army.army_id, False)
        if battle_result.winner == "defender":
            army.quality = roll_quality_change(
                army.quality, rng, is_winner=True, led_by_insufficient_druid=led_by_insufficient_druid
            )
            report.quality_changes[army.army_id] = army.quality
        elif defender_clean_swept and _whale_forced_retreat_applies(army, terrain):
            bounds = MapBounds(*NORMAL_MAP_BOUNDS)
            destination = _whale_sea_retreat_destination(army, state, bounds)
            _retreat_or_disband(
                army, state, report, rng, destination=destination,
                led_by_insufficient_druid=led_by_insufficient_druid,
            )
        elif defender_clean_swept and loser_retreats:
            bounds = MapBounds(*NORMAL_MAP_BOUNDS)
            friendly = state.friendly_provinces_for(army.kingdom_id) - {province_coord}
            destination = find_retreat_destination(army.location, bounds, friendly)
            _retreat_or_disband(
                army, state, report, rng, destination=destination,
                avoid_elimination=_fleet_avoids_elimination(army, terrain),
                led_by_insufficient_druid=led_by_insufficient_druid,
            )
        elif defender_clean_swept and _fleet_avoids_elimination(army, terrain):
            army.quality = Quality.DEPLETED
            report.quality_changes[army.army_id] = army.quality
        elif defender_clean_swept:
            report.destroyed_army_ids.append(army.army_id)
            state.record_battle_death(province_coord, army.army_type, army.quality, army.kingdom_id)
            state.remove_army(army.army_id)
        elif rng.random() < direct_destruction_probability_by_army_id.get(army.army_id, 0.0):
            report.destroyed_army_ids.append(army.army_id)
            state.record_battle_death(province_coord, army.army_type, army.quality, army.kingdom_id)
            state.remove_army(army.army_id)
        else:
            army.quality = roll_quality_change(
                army.quality, rng, is_winner=False, retreated=False,
                led_by_insufficient_druid=led_by_insufficient_druid,
            )
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


@dataclass(slots=True)
class MultiAttackerBattle:
    """One resulting battle from ``fight_multi_attacker_battle``'s grouping.

    ``leader_ids`` (Phase 45) is every party's ``leader_id`` that ended up
    united into this specific battle -- added so a caller driving several
    leaders at once (``turn/turn_processor.py``) can look up which
    ``BattleReport`` its own post-battle bookkeeping (movement cost, army
    relocation) should read for a given leader, without re-deriving
    ``group_attackers_into_battles``' own rng-consuming grouping itself
    (which would desync the shared ``rng`` stream).
    """

    leader_ids: list[int]
    report: BattleReport


def fight_multi_attacker_battle(
    state: GameState,
    province_coord: HexCoord,
    parties: list[MultiAttackerParty],
    *,
    loser_retreats: bool = True,
    apply_fanaticism: bool = False,
    rng: random.Random | None = None,
) -> list[MultiAttackerBattle]:
    """Rulebook [7.8] Multiple Contingents: partition several leaders' simultaneous
    attacks on ``province_coord`` into one or more battles, then fight each.

    See the module docstring for how ``turn/turn_processor.py`` now
    reaches this from real multi-leader play (Phase 45).

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

    **Separate (non-united) groups sequentially claiming an already-
    cleared province (Phase 73)**: groups are fought one at a time
    against the same ``province_coord``, each mutating ``state`` before
    the next group's own turn. If an earlier group already cleanly
    swept -- or, for a non-allied later group, if the earlier group's
    own surviving forces are the only occupants left and happen to be
    allied with this later group -- there are no non-allied defenders
    left for this group to fight at all. ``fight_battle()`` itself
    would raise ``ValueError`` for an empty defender list (it has no
    other way to signal "nothing to fight"); here that's checked for
    up front and treated as an uncontested claim instead, the same
    "no defenders present -> uncontested" reading ``turn/
    move_execution.py execute_move()`` already gives a lone attacker
    walking into an empty enemy-owned province. The rulebook's own
    [7.8] text doesn't say how several simultaneous, unrelated
    invasions of the same province are meant to interact once one of
    them has already resolved -- a documented, unsourced-but-reasonable
    design choice (unlike ``multiple_contingents.py``'s own union-chance
    formula, which is real, sourced MARCH TABLE data as of Phase 307).

    **Phase 311 addendum -- ordering the groups for a neutral province**:
    [7.6]/[7.7] itself, for a "provincia neutrale" invaded by more than
    one separate (non-allied, non-united) force in the same turn, gives
    the fighting priority to "l'esercito guidato da chi ha piu
    iniziativa" (the army led by whoever has more Initiative), with
    unit count as the tiebreak when Initiative is equal -- both per the
    project owner's own clarification. That's implemented here as a
    pre-loop sort of ``groups`` (stable, so a full tie keeps the
    original arbitrary order from above) keyed on each group's own
    highest ``turn/initiative.py character_initiative()`` member, then
    that group's own total unit count, both descending -- but *only*
    when ``province_coord`` currently belongs to no kingdom at all
    (``ProvinceState.owner_kingdom_id is None``): the rulebook's own
    wording is scoped to a genuinely neutral province, so a multi-group
    invasion of an *enemy*-owned province still falls through to the
    unsourced arbitrary order documented in the paragraph above,
    unchanged.
    """

    rng = rng if rng is not None else random.Random()
    if not parties:
        raise ValueError("no attacking parties given")

    # Phase 307: each party's own real March skill drives its own chance
    # of uniting with another group (`multiple_contingents.py`'s own
    # MARCH TABLE) -- 0 (the table's own floor) for a party whose leader
    # isn't recorded in `state.leaders`, the same permissive-missing-data
    # convention used throughout this project.
    attackers = [
        Attacker(
            leader_id=p.leader_id,
            kingdom_id=p.kingdom_id,
            origin_province=p.origin_province,
            march_level=effective_skill_level(state, state.leaders[p.leader_id], Ability.MARCH)
            if p.leader_id in state.leaders
            else 0,
        )
        for p in parties
    ]
    groups = group_attackers_into_battles(attackers, state.allied_kingdoms, rng)
    parties_by_leader = {p.leader_id: p for p in parties}

    # Phase 311: a truly neutral province (owner_kingdom_id is None --
    # [7.6]'s own "provincia neutrale") reorders the separate groups by
    # priority before any of them fight, instead of leaving them in
    # whatever order the caller happened to supply -- see this
    # function's own Phase 311 addendum.
    target_province = state.provinces.get(province_coord)
    if target_province is not None and target_province.owner_kingdom_id is None and len(groups) > 1:

        def _group_priority_key(group: list[Attacker]) -> tuple[int, int]:
            max_initiative = max(
                character_initiative(state, state.leaders[member.leader_id]) if member.leader_id in state.leaders else 0
                for member in group
            )
            total_units = sum(len(parties_by_leader[member.leader_id].army_ids) for member in group)
            return (-max_initiative, -total_units)

        groups = sorted(groups, key=_group_priority_key)

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

        defenders_present = any(
            army.army_id not in combined_army_ids
            and army.kingdom_id is not None
            and not state.is_allied(army.kingdom_id, claiming_kingdom_id)
            for army in state.armies_at(province_coord)
        )
        if defenders_present:
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
        else:
            # An earlier group already cleared/claimed the province this
            # same call -- see module docstring's "Phase 73" note.
            report = BattleReport(battle_result=BattleResult(winner="attacker"), conquered=True)
        reports.append(MultiAttackerBattle(leader_ids=[member.leader_id for member in group], report=report))

    return reports
