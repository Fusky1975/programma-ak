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
  ``attacker_origin`` is supplied, and skipped otherwise. **As of Phase
  409, every real caller supplies it**: ``move_execution.py``,
  ``pursue_execution.py``, and ``fight_multi_attacker_battle()`` already
  did; ``turn_processor.py _dispatch_contested_rebattles()`` was the one
  gap (a forced rebattle for an already-contested province had no
  origin to pass), now closed via ``ProvinceState.contested_from_coord``
  (see that field's own docstring) -- so the wrong-rule fallback is now
  dead code for every path this project drives, kept only as a defensive
  default for a hypothetical future caller that genuinely doesn't know
  the origin. **Still genuinely unresolved, left alone**: among the
  origin-or-adjacent candidates the rule allows, this project always
  picks the origin itself (``attacker_retreat_candidates(...)[0]``) --
  the rulebook names no "best" candidate among them, so no tie-break was
  invented. **Whales are
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

from ak_engine.models.advanced_ability import AdvancedAbility
from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ARMY_TABLE, MONSTROUS_ARMY_RACE, OVERFLIGHT_AIR, ArmyType, is_overflight_unit
from ak_engine.models.discovery import Discovery
from ak_engine.models.enums import Ability, Maneuver
from ak_engine.models.game_state import ArmyState, GameState, LeaderState
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.office import Office
from ak_engine.models.race import HUMANOID_RACES, Race
from ak_engine.models.temper import Temper
from ak_engine.models.treasure import MONSTER_SUMMONING_TREASURE, RACE_LEADERSHIP_TREASURE, Treasure
from ak_engine.turn.aftermath import FORMATION_DIVISOR, roll_quality_change
from ak_engine.turn.battle_line import BattleUnit, estimate_win_probability, line_length_for_battle, roll_terrain_line_length_cap
from ak_engine.turn.battle_resolution import BattleResult, resolve_battle
from ak_engine.turn.cast_execution import is_illusory_fog_affected_air_unit, quality_one_level_down
from ak_engine.turn.challenge_execution import resolve_challenge_combat
from ak_engine.turn.combat import Quality, direct_destruction_probability
from ak_engine.turn.discovery_effects import (
    arcane_valor_hit_points_bonus,
    effective_skill_level,
    equipped_combat_weapon,
    holds_bow_of_elven_kings,
)
from ak_engine.turn.druidic_monster_aid import DruidicMonsterAssistance, find_druidic_monster_assistance
from ak_engine.turn.duel import Commander, apply_duel_demoralization, provincial_garrison_commander, select_supreme_commander
from ak_engine.turn.encounter import (
    CHARACTER_HIT_POINTS,
    Combatant,
    archery_free_attack_bonus,
    bow_of_elven_kings_archery_damage_bonus,
    bow_of_elven_kings_archery_hit_multiplier,
    weapon_defensive_hit_multiplier,
    melee_mastery_damage_bonus,
    melee_mastery_offensive_hit_multiplier,
    weapon_grants_auto_invisibility,
    weapon_melee_damage_bonus,
    weapon_offensive_hit_multiplier,
)
from ak_engine.turn.experience import add_experience
from ak_engine.turn.initiative import character_initiative
from ak_engine.turn.merit_points import battle_quality_points
from ak_engine.turn.movement import MapBounds, neighbors
from ak_engine.turn.multiple_contingents import Attacker, group_attackers_into_battles, is_march_immune_party
from ak_engine.turn.office_holder import resolve_office_holder
from ak_engine.turn.pursuit import select_pursuers, resolve_pursuit
from ak_engine.turn.race_titles import RACE_TITLE_OFFICE
from ak_engine.turn.retreat import attacker_retreat_candidates, find_retreat_destination
from ak_engine.turn.sea_transport import apply_battle_carrier_destruction
from ak_engine.turn.search_decode import SearchTactic
from ak_engine.turn.sep_decode import sep_accepts_challenge, sep_is_aggressive
from ak_engine.turn.strength import (
    PHANTASMAL_ARMIES_BONUS_PER_LEVEL,
    compute_druidic_shortfall,
    compute_effective_strength,
    roll_dinosaurs_strength,
    roll_elephants_strength,
    roll_fanaticism,
    roll_title_fanaticism,
)

# Observation Balloons (Discovery.txt, Phase 270): "army strength is
# increased by only 5% per skill level" by Phantasmal Armies, instead of
# the base 15%, when the opposing Kingdom in a battle owns the
# Discovery -- see _build_battle_units's own Phase 270 addendum.
OBSERVATION_BALLOONS_PHANTASMAL_ARMIES_BONUS_PER_LEVEL = 0.05


@dataclass(slots=True, frozen=True)
class QualityChange:
    """An army's ``Quality`` before and after one battle-triggered change
    (``turn/aftermath.py roll_quality_change()``, or a direct DEPLETED
    demotion on avoiding elimination). ``old``/``new`` together are what
    ``report/turn_report.py describe_quality_changes()`` needs to pick
    between HostAK/TP/PROSE/DECQ.X (``new`` worse than ``old``) and
    INCQ.X (``new`` better) -- a bare post-change ``Quality`` value alone
    can't tell those apart once the mutation has already happened.
    """

    old: Quality
    new: Quality


@dataclass(slots=True)
class BattleReport:
    battle_result: BattleResult
    conquered: bool
    destroyed_army_ids: list[int] = field(default_factory=list)
    retreated_army_ids: list[int] = field(default_factory=list)
    disbanded_army_ids: list[int] = field(default_factory=list)
    mercenary_army_ids: list[int] = field(default_factory=list)
    pursuit_destroyed_army_ids: list[int] = field(default_factory=list)
    quality_changes: dict[int, QualityChange] = field(default_factory=dict)
    attacker_commander_leader_id: int | None = None
    defender_commander_leader_id: int | None = None
    duel_loser_side: str | None = None  # "attacker" / "defender" / None if no duel occurred
    # Phase 739: True only when the loser's own duel-ending Special
    # Encounter Plan led with Maneuver.FLEE (`_maybe_fight_duel()`'s own
    # dedicated branch) -- a real, structurally distinct "the commander
    # fled" outcome from an ordinary lost duel (the probability-estimate
    # roll, or a real-combat defeat via `use_real_duel_combat`), both of
    # which leave this `False`. `report/turn_report.py describe_battle()`
    # uses this to pick between `_ADishK` ("died") and `_ADishF` ("fled/
    # was cowardly") -- that composer's own docstring already states no
    # source distinguishes the two narrations, "the caller decides"; this
    # is that decision, grounded in the one real structural signal this
    # project actually has for it, not an arbitrary pick.
    duel_loser_fled: bool = False
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
    # Phase 649 -- SAY.PAS `_BLList`'s own per-side leader roster (BATLDR.X):
    # every distinct leader who commands at least one army actually
    # fighting on that side, sorted by leader_id (the real tent-assignment
    # order this project can't reconstruct -- see `fight_battle()`'s own
    # Phase 649 note). Includes the side's own Supreme Commander -- no
    # separate handling needed, they're just one more commanding leader.
    # Empty for the instant-conquest shortcut (no real battle fought).
    attacker_commanding_leader_ids: list[int] = field(default_factory=list)
    defender_commanding_leader_ids: list[int] = field(default_factory=list)
    # Phase 657 -- SAY.PAS `_BMonst`'s own MCOME.X/MFIGHT.X pair: a
    # Druidic side's own assisting Feature monster(s), keyed by which
    # battle column each one joined (turn/druidic_monster_aid.py
    # find_druidic_monster_assistance()). Empty for a non-Druidic battle
    # or the instant-conquest shortcut (no real battle fought).
    attacker_monster_assistance: dict[int, DruidicMonsterAssistance] = field(default_factory=dict)
    defender_monster_assistance: dict[int, DruidicMonsterAssistance] = field(default_factory=dict)
    # Phase 658 -- SAY.PAS `_BLList`'s other half: a leader present at
    # the battle province but commanding none of that side's own
    # fighting armies (`"< was there, leading no armies."`). Sorted by
    # leader_id, the same unsourced-but-reasonable tie-break the
    # commanding roster above already uses.
    attacker_present_leader_ids: list[int] = field(default_factory=list)
    defender_present_leader_ids: list[int] = field(default_factory=list)
    # Phase 711 -- `report/turn_report.py describe_battle()`'s own
    # `destination_names` parameter needs each retreating army's real
    # destination province -- `_retreat_or_disband()` already computes
    # it (to actually move the army) but used to discard it right after.
    # Keyed by `army_id`, only ever populated for ids also present in
    # `retreated_army_ids`.
    retreat_destination_coord: dict[int, HexCoord] = field(default_factory=dict)
    # Phase 712 -- SAY.PAS `_BTac`'s own real input (TACTICS.X2,
    # `report/turn_report.py render_tactical_comparison()`, already
    # sourced and render-tested since Phase 109 but never carried onto
    # this report). Already computed locally in `fight_battle()` as
    # `attacker_ability_level`/`defender_ability_level` for its own
    # `resolve_battle()` call -- stored here rather than re-derived.
    attacker_tactical_ability: int = 0
    defender_tactical_ability: int = 0


def _build_battle_units(
    armies: list[ArmyState],
    state: GameState,
    *,
    is_defender: bool,
    terrain,
    province_coord: HexCoord,
    rng: random.Random,
    combat_ability_level: int = 0,
    combat_ability_mastery_bonus: float = 0.0,
    apply_fanaticism: bool = False,
    own_explored_percent: int = 0,
    opponent_kingdom_ids: frozenset[int] = frozenset(),
    is_island: bool = False,
    illusory_terrain: Terrain | None = None,
    illusory_terrain_enhanced: bool = False,
    duellist_side: bool = False,
    alignment_king_office: Office | None = None,
    explorer_find_water: bool = False,
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

    ``combat_ability_mastery_bonus`` (Phase 512): the same Supreme
    Commander's flat Tactical/Naval Mastery Advanced Ability bonus (see
    ``_mastery_bonus_for``), applied alongside ``combat_ability_level``
    via ``turn/strength.py compute_effective_strength()``'s own
    parameter of the same name. Defaults to 0.0 (no change) for every
    pre-Phase-512 caller.

    **Exploration advantage** (Phase 69, real formula Phase 507):
    ``own_explored_percent`` is a single side-level value (not
    per-army), computed once by ``fight_battle`` and applied uniformly
    to every unit on this side via ``turn/strength.py
    exploration_advantage_multiplier`` -- see ``fight_battle``'s own
    docstring for exactly which kingdom's ``ProvinceState.
    explored_percent_by_kingdom`` entry each side reads. Defaults to 0
    (no advantage) for any caller that doesn't pass it. No longer takes
    the opposing side's own value (Phase 507 -- the real formula reads
    each side's own accumulated knowledge only, never a relative gap).

    **Desert without camels** (Phase 35): "In a desert battle, one camel
    unit should be present (it sees double duty as a supply train.) If
    not, all armies have their quality reduced by 1 level." -- checked
    once per side (not per unit): if the battle is in a Desert province
    and this side's ``armies`` include no ``ArmyType.CAMEL_CORPS``, every
    unit on the side gets the penalty, including any Elephants (the
    rulebook names "Camels" specifically here, not the broader "Beasts"
    grouping used for the nemesis table -- a confident reading, not a
    guess). Fully deterministic, no ``rng`` involved.

    **Find Water** (Advanced Ability, Phase 511 -- ``explorer_find_
    water``): quoted directly from ``models/advanced_ability.py
    ADVANCED_ABILITY_DESCRIPTION[EXPLORER_FIND_WATER]``: "If the
    Explorer is present at a battle, no units fighting with his side
    will suffer from thirst and penalties in a Desert province." This
    project has no separate "thirst" state -- the one Desert-province
    penalty this engine models is exactly the Desert-without-camels
    quality downgrade above, so Find Water is read as suppressing that
    same, already-real mechanic for this side, not a second unmodeled
    one. Resolved once by ``fight_battle()`` (any leader physically
    present at the battle province who belongs to this side and holds
    the Advanced Ability -- not necessarily the Supreme Commander, since
    the rulebook says "present," not "commanding") and passed through
    the same side-level-boolean convention as ``is_island``/
    ``duellist_side`` above.

    **Fanaticism** (Phase 35, ``apply_fanaticism``): "An army fighting
    for a Divine/Good/Evil kingdom has a 50%/40%/25% chance of becoming
    fanatical" -- rolled once per army via ``turn/strength.py
    roll_fanaticism(kingdom.alignment, rng)``. This function's own
    default stays ``False`` (unlike ``combat_ability_level``, there's no
    data-absence condition that keeps this naturally silent, since every
    ``KingdomState`` always has a concrete, often-nonzero-chance
    ``Alignment``) -- but **Phase 744 wires ``apply_fanaticism=True`` at
    every real production battle call site** (``turn/turn_processor.py``'s
    own forced-rebattle and multi-attacker-LMOVE dispatch, ``turn/
    move_execution.py execute_move()``, ``turn/pursue_execution.py
    execute_pursue()``), so real Fanaticism now applies in every turn
    this engine actually processes. Only *direct*, unit-level callers of
    this function (or ``fight_multi_attacker_battle()``/``_build_battle_
    units()``) -- i.e. tests exercising this function in isolation, not
    through the real dispatch path -- still get the quiet ``False``
    default, unaffected. Measured empirically at Phase 744: flipping the
    4 production call sites broke exactly 6 of 6335 existing tests (5
    needed 2 new leading scripted-RNG values per single-army-per-side
    fixture; 1 needed a reseeded ``random.Random`` since both kingdoms
    in that fixture are ``Alignment.GOOD`` and the roll is now a real,
    live coin-flip there) -- a materially smaller blast radius than this
    note originally feared.

    **Title-based fanaticism** (Phase 390, same ``apply_fanaticism`` opt-in,
    now also real in production as of Phase 744):
    AKGEN's own confirmed ``battle_engine.special_events`` rows for
    "Savior of Humankind"/"First Elder of Elvenkind"/"King Under the
    Mountain"/"Khan of the Orcish Hordes" (20%/35%/40%/45%) and the
    seven racial-monster titles Dragon/Eagle/Whale/Merman/Ent/Troll/
    Werebeast (50%, one shared row) -- a *directly led* army (``army.
    commanded_by`` not ``None``) whose own race (``kingdom.race``, the
    same "army's own race" this docstring's own Druidic-ability section
    already uses) matches a title its commander *currently holds*
    (``turn/office_holder.py resolve_office_holder``, resolved once per
    relevant office and cached for this call, not re-derived per unit)
    gets an independent, additive chance to be fanatical via
    ``turn/strength.py roll_title_fanaticism``. Only rolled when the
    alignment-based check above didn't already succeed (both fold into
    the same ``is_fanatical`` -- one real strength bonus, two independent
    ways to earn it) and only when a real title-race match exists, so a
    caller with no matching King/Lord anywhere doesn't pay a new
    ``rng.random()`` draw for this either. **Deliberately NOT modeled
    this phase**: the "supreme alignment title" and "Captain of the
    Imperial Musketeers" rows are unit *selection* ("one eligible random
    front-line unit"), not a per-unit percentage roll -- this function
    runs before battle-line assignment even exists, so there's no
    "front line" yet to select from; a real follow-up needs to run after
    ``assign_battle_lines`` instead, in ``turn/battle_resolution.py``,
    not here. **Phase 471 closes the "Captain of the Imperial
    Musketeers" (Duellist) half of this gap** -- see this function's own
    Phase 471 addendum below and ``turn/battle_resolution.py``'s own for
    the real front-line selection. The "supreme alignment title" row
    stays unmodeled: it's sourced from a different catalog
    (``battle_engine.special_events``, not ``AKGEN_reverse_engineering_
    report (2).md``, the report this project is currently working
    through) and names a title this project hasn't otherwise identified
    yet -- a separate, still-open follow-up.

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
    ``mystic_winds_active`` resolved by ``mystic_winds_active_for()``,
    the same "derive from the commanding leader, ``False`` for an unled
    army" pattern ``_phantasmal_armies_level_for()`` already
    established. Fully deterministic, no ``rng`` involved. Made public
    (Phase 651, dropped its own leading underscore) once ``turn/move_
    execution.py`` needed the identical derivation for the movement-
    surcharge half of the same spell.

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

    **Crystal of True Seeing** (``AKGEN_reverse_engineering_report
    (4).md`` SS8 point 3, Phase 532): a third, item-driven (not
    Discovery-driven) halving of Phantasmal Armies' own strength bonus,
    checked per-leader rather than per-Kingdom -- any leader on the
    opposing side holding ``Treasure.AMULET_ANTI_ILLUSION`` halves
    whichever ``phantasmal_armies_bonus_per_level`` rate the Balloons
    check above already selected. Stacks with Balloons multiplicatively
    (15% -> 5% -> 2.5%) since no source gives a combined formula for both
    wards applying at once.

    **Island provinces** (Phase 282, ``is_island``): resolved once by
    ``fight_battle()`` from ``ProvinceState.is_island`` and passed
    straight through to ``turn/strength.py compute_effective_strength()``
    for every unit on this side -- see that function's own docstring for
    the land/Sea blend it runs. Defaults to ``False``, unaffected, for
    every pre-Phase-282 caller.

    **Illusory Terrain** (Phase 724, ``illusory_terrain``): resolved
    once by ``fight_battle()`` from ``ProvinceState.illusory_terrain``
    the same way, right alongside ``is_island``, and passed straight
    through to ``compute_effective_strength()``'s own parameter of the
    same name -- see that function's docstring for the real/illusory
    blend it runs. Defaults to ``None``, unaffected, for every pre-
    Phase-724 caller.

    **Crystal of True Seeing's own Illusory Terrain immunity** (Phase
    773, ``models/treasure.py TREASURE_DESCRIPTION[AMULET_ANTI_
    ILLUSION]``): "The possessor of the Crystal is unaffected by the
    spells of ... Illusory Terrain" -- the mirror-image scope of
    ``opponent_owns_crystal_of_true_seeing`` just below (that one asks
    whether the *opponent* holds it, for Illusory Armies' own halving;
    this one asks whether *this side* holds it, since the text protects
    the holder's own side from being fooled by the illusion, not the
    opponent's). Resolved once per side-build-call, the same "any
    leader whose kingdom_id matches, present or not, mirroring the
    already-shipped Illusory-Armies precedent's own scope" convention
    -- see ``own_side_owns_crystal_of_true_seeing`` below. When a match
    is found, ``illusory_terrain`` is overridden to ``None`` for every
    unit on this side, so they fight at the real terrain's own strength
    only, with no illusory blend at all. Deliberately scoped no wider
    than the sibling Illusory-Armies clause already is: `_apply_
    pursuit()`'s own retreating-army strength and `turn/army_quality.py`'s
    peacetime "Modified Quality" display are both untouched, matching
    that clause's own existing boundary rather than widening past it.

    **Duellist / "Captain of the Musketeers"** (Phase 471, AKGEN_reverse_
    engineering_report (2).md SS17.7, ``duellist_side``): "Quando il
    titolare è comandante supremo in battaglia, una sua unità casuale
    della prima linea riceve l'assistenza degli Imperial Musketeers e
    combatte come fanatica" -- ``fight_battle()`` resolves once, before
    calling this function for either side, whether that side's own
    ``Commander.leader_id`` (already selected, per this function's own
    docstring intro) currently holds ``Office.DUELLIST`` (``turn/
    office_holder.py resolve_office_holder``), and passes the result as
    ``duellist_side``. When ``True``, every unit built for this side gets
    its own ``BattleUnit.duellist_bonus_if_selected`` set to the exact
    strength delta it would gain from being fanatic -- computed by
    calling ``compute_effective_strength()`` a second time with
    ``is_fanatical`` forced ``True`` and diffing against the value
    already computed above (naturally ``0.0``, not double-counted, for a
    unit that was already fanatical via the alignment/title rolls above
    -- forcing ``True`` on an already-``True`` value changes nothing,
    which is exactly SS17.7's own "non si accumulano più incrementi di
    qualità sulla stessa concessione" rule, for free). ``False`` (the
    default) leaves every unit's own field at ``None`` -- see that
    field's own docstring in ``turn/battle_line.py`` for why the real
    random *front-line* selection has to happen in ``turn/battle_
    resolution.py`` instead, not here (this function runs before ``assign_
    battle_lines``, so there's no front line yet to draw from -- the same
    structural gap this function's own Phase 390 addendum already flagged
    for exactly this follow-up).

    **The 7 alignment-King titles' own shared fanatic-front-line-unit
    bonus** (Phase 661, ``alignment_king_office``): Divine/Good/Druid/
    Neutral/Pagan/Evil/Undead King (`models/office.py OFFICE_TITLE_
    DESCRIPTION`) all share DUELLIST's own exact real mechanic --
    "when [holder] is the supreme commander at a battle, one [random]
    unit in the front line... become[s] fanatical" -- just naming a
    different in-world group (Thunderbird, Knights Hospitaller, the
    Druids, berserking freedom fighters, the Pagan Clerics, the Black
    Knights, the Circle of Wraiths) per title. ``fight_battle()``
    resolves once, before calling this function for either side, which
    (if any) of these 7 offices that side's own Supreme Commander
    currently holds -- these titles are mutually exclusive per leader
    (``turn/merit_points.py _alignment_king_merit_points()``'s own
    alignment gate means a leader can only ever qualify for the one
    office matching their own Kingdom's Alignment), so a single
    ``Office | None`` is enough, unlike a boolean. When given, every
    unit built for this side gets its own ``BattleUnit.alignment_king_
    bonus_if_selected`` set the same way ``duellist_bonus_if_selected``
    is -- see that field's own docstring in ``turn/battle_line.py`` for
    why a Supreme Commander holding *both* Duellist and an alignment-
    King title at once is intentionally allowed to grant two
    independent bonuses (two separate real in-world groups, no source
    treats them as one combined grant). **Undead King's own real
    "non-skeletal unit" restriction**: a skeletal army never gets this
    bonus even on an eligible Undead King side (stays ``None``) -- the
    *other* 6 titles have no such restriction, so this is checked here
    per-``office``, not baked into the shared computation. ``None``
    (the default) leaves every unit's own field at ``None``, same as
    ``duellist_side=False``.

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

    **Adapt Tactics to Terrain** (Advanced Ability, Phase 513): quoted
    directly from ``models/advanced_ability.py ADVANCED_ABILITY_
    DESCRIPTION[ADAPT_TACTICS_TO_TERRAIN]``: "When a character directly
    leads a unit at a battle, the effect of adverse terrain is reduced.
    The unit is reduced to 75% of normal strength, instead of 50%." --
    a *per-unit* check (unlike ``combat_ability_mastery_bonus``'s own
    side-wide Supreme-Commander-only resolution above): each army's own
    ``commanded_by`` leader, if any, is checked directly, since the
    rulebook says "a character directly leads a unit," not "the side's
    Supreme Commander." Passed straight through to ``turn/strength.py
    compute_effective_strength()``'s own parameter of the same name.
    """

    desert_without_camels = (
        terrain is Terrain.DESERT
        and not explorer_find_water
        and not any(army.army_type is ArmyType.CAMEL_CORPS for army in armies)
    )
    province = state.provinces.get(province_coord)
    illusory_fog_active = province is not None and province.illusory_fog_active

    opponent_owns_osteopathic = any(
        Discovery.OSTEOPATHIC_GERM_WARFARE in state.kingdoms[kid].discoveries for kid in opponent_kingdom_ids
    )
    opponent_owns_balloons = any(
        Discovery.OBSERVATION_BALLOONS in state.kingdoms[kid].discoveries for kid in opponent_kingdom_ids
    )
    # Phase 532: AKGEN_reverse_engineering_report (4).md SS8 point 3 -- a
    # Crystal of True Seeing holder on the opposing side halves the
    # caster's own Phantasmal Armies strength bonus, independent of and
    # stacking with Observation Balloons' own reduction above (no sourced
    # combined formula, so this halves whichever rate already applies --
    # same "no sourced stacking order, pick the plain reading" convention
    # this project already uses elsewhere).
    opponent_owns_crystal_of_true_seeing = any(
        leader.kingdom_id in opponent_kingdom_ids
        and any(item.treasure is Treasure.AMULET_ANTI_ILLUSION for item in state.items_held_by(leader.leader_id))
        for leader in state.leaders.values()
    )
    # Phase 773: the mirror-image scope of the check above -- "unaffected
    # by the spells of ... Illusory Terrain" protects the Crystal-
    # holder's own side, not the opponent's. See this function's own
    # Phase 773 docstring addendum.
    own_kingdom_ids = frozenset(army.kingdom_id for army in armies if army.kingdom_id is not None)
    own_side_owns_crystal_of_true_seeing = any(
        leader.kingdom_id in own_kingdom_ids
        and any(item.treasure is Treasure.AMULET_ANTI_ILLUSION for item in state.items_held_by(leader.leader_id))
        for leader in state.leaders.values()
    )
    effective_illusory_terrain = None if own_side_owns_crystal_of_true_seeing else illusory_terrain

    # Phase 390: memoized per office actually queried this call, since
    # resolve_office_holder() re-derives merit points across every
    # leader -- avoids repeating that work for every unit of a large
    # army sharing the same race/title.
    _title_office_holder_cache: dict[Office, int | None] = {}

    def _title_holder_leader_id(office: Office) -> int | None:
        if office not in _title_office_holder_cache:
            holder = resolve_office_holder(state, office)
            _title_office_holder_cache[office] = holder.leader_id if holder is not None else None
        return _title_office_holder_cache[office]

    units = []
    for army in armies:
        kingdom = state.kingdoms[army.kingdom_id]
        is_home = province_coord == kingdom.home_province
        if army.army_type is ArmyType.ELEPHANTS:
            override = roll_elephants_strength(rng)
        elif army.army_type is ArmyType.DINOSAURS:
            override = roll_dinosaurs_strength(rng)
        else:
            override = None
        # Short-circuited: roll_fanaticism (and its rng.random() call) never
        # runs at all when apply_fanaticism is False -- see docstring.
        is_fanatical = apply_fanaticism and roll_fanaticism(kingdom.alignment, rng)
        if apply_fanaticism and not is_fanatical and army.commanded_by is not None:
            # See this function's own Phase 390 addendum: an independent,
            # additive second chance, only rolled (consuming rng) when a
            # real title-race match exists.
            title_office = RACE_TITLE_OFFICE.get(kingdom.race)
            if title_office is not None and _title_holder_leader_id(title_office) == army.commanded_by:
                is_fanatical = roll_title_fanaticism(title_office, rng)
        druidic_shortfall = druidic_shortfall_for(army, state, kingdom.race, province_coord)
        phantasmal_armies_level = _phantasmal_armies_level_for(army, state)
        mystic_winds_active = mystic_winds_active_for(army, state)
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
        if phantasmal_armies_level > 0 and opponent_owns_crystal_of_true_seeing:
            phantasmal_armies_bonus_per_level /= 2
        adapt_tactics_to_terrain = False
        if army.commanded_by is not None:
            commanding_leader = state.leaders.get(army.commanded_by)
            adapt_tactics_to_terrain = (
                commanding_leader is not None
                and AdvancedAbility.ADAPT_TACTICS_TO_TERRAIN in commanding_leader.advanced_abilities
            )
        # Phase 696: AdvancedAbility.DRUIDIC_HORSE_CONTROL -- "cavalry
        # units directly led by the Druid" -- scoped to Light/Heavy
        # Cavalry, mirroring adapt_tactics_to_terrain's own "commanding
        # leader holds this Advanced Ability" resolution just above.
        has_druidic_horse_control = False
        if army.army_type in (ArmyType.LT_CAVALRY, ArmyType.HVY_CAVALRY) and army.commanded_by is not None:
            commanding_leader = state.leaders.get(army.commanded_by)
            has_druidic_horse_control = (
                commanding_leader is not None
                and AdvancedAbility.DRUIDIC_HORSE_CONTROL in commanding_leader.advanced_abilities
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
            combat_ability_mastery_bonus=combat_ability_mastery_bonus,
            phantasmal_armies_level=phantasmal_armies_level,
            phantasmal_armies_bonus_per_level=phantasmal_armies_bonus_per_level,
            own_explored_percent=own_explored_percent,
            illusory_fog_affected=illusory_fog_affected,
            is_island=is_island,
            illusory_terrain=effective_illusory_terrain,
            illusory_terrain_enhanced=illusory_terrain_enhanced,
            adapt_tactics_to_terrain=adapt_tactics_to_terrain,
        )
        duellist_bonus_if_selected = None
        alignment_king_bonus_if_selected = None
        alignment_king_eligible = alignment_king_office is not None and not (
            alignment_king_office is Office.UNDEAD_KING and army.is_skeletal
        )
        if duellist_side or alignment_king_eligible:
            fanatic_strength = compute_effective_strength(
                army.army_type,
                kingdom.race,
                battle_quality,
                terrain,
                is_defender=is_defender,
                is_home_province=is_home,
                is_fanatical=True,
                desert_without_camels=desert_without_camels,
                druidic_shortfall=druidic_shortfall,
                race_item_bonus=race_item_bonus,
                base_strength_override=override,
                combat_ability_level=combat_ability_level,
                combat_ability_mastery_bonus=combat_ability_mastery_bonus,
                phantasmal_armies_level=phantasmal_armies_level,
                phantasmal_armies_bonus_per_level=phantasmal_armies_bonus_per_level,
                own_explored_percent=own_explored_percent,
                illusory_fog_affected=illusory_fog_affected,
                is_island=is_island,
                illusory_terrain=effective_illusory_terrain,
                illusory_terrain_enhanced=illusory_terrain_enhanced,
                adapt_tactics_to_terrain=adapt_tactics_to_terrain,
            )
            bonus = fanatic_strength - strength
            if duellist_side:
                duellist_bonus_if_selected = bonus
            if alignment_king_eligible:
                alignment_king_bonus_if_selected = bonus
        rear_targeting_blocked = is_overflight_unit(army.army_type) and druidic_shortfall > 0
        units.append(
            BattleUnit(
                army.army_type,
                strength,
                source_id=army.army_id,
                druidic_rear_targeting_blocked=rear_targeting_blocked,
                led_by_insufficient_druid=druidic_shortfall > 0,
                is_humanoid_race=kingdom.race in HUMANOID_RACES,
                duellist_bonus_if_selected=duellist_bonus_if_selected,
                alignment_king_bonus_if_selected=alignment_king_bonus_if_selected,
                has_druidic_horse_control=has_druidic_horse_control,
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


def mystic_winds_active_for(army: ArmyState, state: GameState) -> bool:
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
    ``_build_battle_units()`` reads ``mystic_winds_active_for()`` -- so a
    leader whose own army is *in* this battle never gets Illusory Fog's
    Mystic-Winds-affected treatment for it, even though the flag was true
    a moment ago.

    Deliberately does **not** touch ``ArmyState.movement_points`` --
    "re-deriving each affected army's movement" (the Phase 204 addendum's
    own words) describes recomputing a movement *rate*, not resetting a
    remaining-this-turn *pool*: Mystic Winds affects Illusory Fog's own
    battle-strength penalty, not how far an army can still move this
    turn, so there is nothing about that pool this function needs to
    touch either way (unaffected by whether ``ArmyState.movement_points``
    has a real per-``ArmyType`` base rate, which it now does -- Phase
    573's own ``ARMY_TABLE[army_type].speed`` -- this paragraph predates
    that fix and was about a different concern).
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
    formation_divisor: int = FORMATION_DIVISOR["front"],
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

    ``formation_divisor`` (Phase 372): the real quality-change formula's
    own real input, forwarded straight through.
    """

    if destination is not None:
        army.location = destination
        old_quality = army.quality
        army.quality = roll_quality_change(
            army.quality, rng, is_winner=False, retreated=True,
            led_by_insufficient_druid=led_by_insufficient_druid, formation_divisor=formation_divisor,
        )
        report.quality_changes[army.army_id] = QualityChange(old=old_quality, new=army.quality)
        report.retreated_army_ids.append(army.army_id)
        report.retreat_destination_coord[army.army_id] = destination
        return

    if army.quality in (Quality.GREEN, Quality.DEPLETED):
        if avoid_elimination:
            old_quality = army.quality
            army.quality = Quality.DEPLETED
            report.quality_changes[army.army_id] = QualityChange(old=old_quality, new=army.quality)
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


# Phase 512: Tactical Mastery / Naval Mastery (Advanced Ability). Quoted
# from `models/advanced_ability.py ADVANCED_ABILITY_DESCRIPTION`:
# "The armies commanded by a character at a battle are increased in
# strength by 10%/15%/20%. Note: this bonus cancels [the lower tier(s)]."
# -- the three tiers of one category never stack (a leader can only ever
# be granted one Mastery ability from the same pool anyway, per that
# module's own "can be gained only once" wording), so only the highest
# tier held applies. See `turn/strength.py TACTICAL_BONUS_LEVEL_CAP`'s
# own docstring for why this bonus exists at all (the automatic +20%/
# level scaling this project already modeled stops at level 4).
_MASTERY_BONUS_BY_ABILITY: dict[Ability, dict[AdvancedAbility, float]] = {
    Ability.TACTICAL: {
        AdvancedAbility.TACTICAL_MASTERY_20: 0.20,
        AdvancedAbility.TACTICAL_MASTERY_15: 0.15,
        AdvancedAbility.TACTICAL_MASTERY_10: 0.10,
    },
    Ability.NAVAL: {
        AdvancedAbility.NAVAL_MASTERY_EXALTED_20: 0.20,
        AdvancedAbility.NAVAL_MASTERY_GREAT_15: 0.15,
        AdvancedAbility.NAVAL_MASTERY_10: 0.10,
    },
}


def _mastery_bonus_for(leader: LeaderState | None, ability: Ability) -> float:
    """The flat strength bonus from the highest Tactical/Naval Mastery
    tier ``leader`` actually holds for ``ability`` (0.0 if none, or if
    ``leader`` is ``None`` -- an unled side, or a Supreme Commander with
    no ``LeaderState`` on record, same "no data, no bonus" convention as
    every other per-leader lookup in this module).
    """

    if leader is None:
        return 0.0
    tiers = _MASTERY_BONUS_BY_ABILITY.get(ability)
    if tiers is None:
        return 0.0
    held = [bonus for grant, bonus in tiers.items() if grant in leader.advanced_abilities]
    return max(held, default=0.0)


# Phase 514: Naval Combined Arms is the exact sea-terrain twin of Phase
# 513's Tactical Combined Arms ("A character can use Naval Combined Arms
# when in supreme command at a sea battle..." vs "...at a land battle").
# `_combat_ability_for_terrain()` already answers "Tactical or Naval" from
# the terrain alone, so gating on this dict's own key naturally encodes
# "land battle" (Ability.TACTICAL) / "sea battle" (Ability.NAVAL) without
# a separate terrain check.
_COMBINED_ARMS_ABILITY_BY_CATEGORY: dict[Ability, AdvancedAbility] = {
    Ability.TACTICAL: AdvancedAbility.TACTICAL_COMBINED_ARMS,
    Ability.NAVAL: AdvancedAbility.NAVAL_COMBINED_ARMS,
}


def _combined_arms_for(leader: LeaderState | None, ability: Ability) -> bool:
    """Does ``leader`` hold the Combined Arms Advanced Ability matching
    ``ability`` (Tactical on land, Naval at sea)? Same "no data, no
    bonus" convention as ``_mastery_bonus_for``.
    """

    if leader is None:
        return False
    combined_arms_ability = _COMBINED_ARMS_ABILITY_BY_CATEGORY.get(ability)
    return combined_arms_ability is not None and combined_arms_ability in leader.advanced_abilities


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
    # Phase 739: True only for the Maneuver.FLEE-first branch below --
    # the loser's own Special Encounter Plan led with Flee, a real,
    # structurally distinct outcome from an ordinary lost duel (the
    # probability-estimate roll, or a real-combat defeat). See
    # BattleReport.duel_loser_fled's own docstring for how this picks
    # between _ADishK/_ADishF's two narrations.
    loser_fled: bool = False


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

    damage_reduction = 0
    always_acts_first = False
    regenerates_hp = 0
    regenerates_hp_interval = 1
    has_melee_hit_points_ability = False
    offensive_hit_multiplier = 1.0
    melee_damage_dealt_bonus = 0
    archery_hit_multiplier = 1.0
    missile_damage_dealt_bonus = 0
    is_humanoid = False
    has_duellists_medal_ability = False
    has_control_temper_ability = False
    defensive_hit_multiplier = 1.0
    is_invisible = False
    equipped_weapon = None
    hit_points_bonus = 0
    if leader is not None:
        hit_points_bonus = arcane_valor_hit_points_bonus(state, leader)
        defender_office = resolve_office_holder(state, Office.DEFENDER)
        if defender_office is not None and defender_office.leader_id == leader.leader_id:
            damage_reduction = 1
        illus_mage_office = resolve_office_holder(state, Office.ILLUS_MAGE)
        always_acts_first = illus_mage_office is not None and illus_mage_office.leader_id == leader.leader_id
        necro_mage_office = resolve_office_holder(state, Office.NECRO_MAGE)
        if necro_mage_office is not None and necro_mage_office.leader_id == leader.leader_id:
            regenerates_hp = 1
            regenerates_hp_interval = 2
        has_melee_hit_points_ability = AdvancedAbility.MELEE_HIT_POINTS in leader.advanced_abilities
        weapon = equipped_combat_weapon(state, leader.leader_id)
        holds_bow = holds_bow_of_elven_kings(state, leader.leader_id)
        defensive_hit_multiplier = weapon_defensive_hit_multiplier(weapon)
        is_invisible = weapon_grants_auto_invisibility(weapon)
        equipped_weapon = weapon
        offensive_hit_multiplier = melee_mastery_offensive_hit_multiplier(
            leader.advanced_abilities
        ) * weapon_offensive_hit_multiplier(weapon)
        melee_damage_dealt_bonus = melee_mastery_damage_bonus(leader.advanced_abilities) + weapon_melee_damage_bonus(
            weapon
        )
        archery_hit_multiplier = bow_of_elven_kings_archery_hit_multiplier(holds_bow)
        missile_damage_dealt_bonus = bow_of_elven_kings_archery_damage_bonus(holds_bow)
        effective_race = leader.race
        if effective_race is None and leader.kingdom_id is not None:
            leader_kingdom = state.kingdoms.get(leader.kingdom_id)
            effective_race = leader_kingdom.race if leader_kingdom is not None else None
        is_humanoid = effective_race in HUMANOID_RACES
        has_duellists_medal_ability = AdvancedAbility.MELEE_DUELLISTS_MEDAL in leader.advanced_abilities
        has_control_temper_ability = AdvancedAbility.MELEE_CONTROL_TEMPER in leader.advanced_abilities
        archery_bonus = archery_free_attack_bonus(leader.advanced_abilities)
        is_undead_or_anti_holy = leader.alignment in (Alignment.UNDEAD, Alignment.ANTI_HOLY)
    else:
        archery_bonus = 0
        is_undead_or_anti_holy = False

    return Combatant(
        name=f"leader {commander.leader_id}",
        hit_points=CHARACTER_HIT_POINTS + hit_points_bonus,
        melee_skill=melee_skill,
        archery_skill=archery_skill,
        neutral_duelist_bonus=neutral_bonus,
        temper=temper,
        damage_reduction=damage_reduction,
        has_melee_hit_points_ability=has_melee_hit_points_ability,
        offensive_hit_multiplier=offensive_hit_multiplier,
        melee_damage_dealt_bonus=melee_damage_dealt_bonus,
        archery_hit_multiplier=archery_hit_multiplier,
        missile_damage_dealt_bonus=missile_damage_dealt_bonus,
        is_humanoid=is_humanoid,
        has_duellists_medal_ability=has_duellists_medal_ability,
        has_control_temper_ability=has_control_temper_ability,
        archery_free_attack_bonus=archery_bonus,
        defensive_hit_multiplier=defensive_hit_multiplier,
        is_invisible=is_invisible,
        equipped_weapon=equipped_weapon,
        always_acts_first=always_acts_first,
        regenerates_hp=regenerates_hp,
        regenerates_hp_interval=regenerates_hp_interval,
        is_undead_or_anti_holy=is_undead_or_anti_holy,
    )


def _commander_governs_neutral_province(state: GameState, commander: Commander) -> LeaderState | None:
    """Rulebook [5.10]: "gli Eroi che sono al comando delle province
    neutrali non sfidano mai a duello e lo accettano sempre a meno che
    non siano di Temperamento Codardo" -- Phase 669, user-confirmed
    directly: a real Hero/King (never the garrison ``Commander(leader_
    id=None)`` fallback -- that one's own "has no abilities" text is a
    separate [7.1] concept) currently stationed in a province nobody
    owns. Returns that real ``LeaderState`` when the exception's own
    precondition holds; ``None`` otherwise (garrison commander,
    unresolvable leader, or a real owner on the province), meaning the
    ordinary SEP-based formula governs instead.
    """

    if commander.leader_id is None:
        return None
    leader = state.leaders.get(commander.leader_id)
    if leader is None:
        return None
    province = state.provinces.get(leader.location)
    if province is None or province.owner_kingdom_id is not None:
        return None
    return leader


def _side_special_encounter_plan(state: GameState, commander: Commander) -> list[SearchTactic]:
    """This side's own real, standing Special Encounter Plan (Phase 669,
    ``LeaderState.special_encounter_plan``) -- ``[]`` for the garrison
    fallback or an unresolvable leader, the same "no data recorded"
    empty-plan default ``turn/turn_processor.py run_turn()`` leaves for
    any leader it never populated this turn (reads as an aggressive
    Melee-intent SEP via ``sep_is_aggressive()``'s own real ``Plan_
    Intent`` fallback, matching this project's pre-Phase-669 always-duel
    default).
    """

    if commander.leader_id is None:
        return []
    leader = state.leaders.get(commander.leader_id)
    if leader is None:
        return []
    return list(leader.special_encounter_plan)


def _commander_challenges(
    state: GameState,
    challenger: Commander,
    challenger_sep: list[SearchTactic],
    target: Commander,
    target_sep: list[SearchTactic],
) -> bool:
    """One direction of rulebook [5.10]'s own bidirectional Duel trigger
    (Phase 669): "Se uno dei due ha un Piano Speciale d'Incontro che
    contiene un'azione aggressiva e nessun ordine Fuggire, allora quel
    comandante sfiderà l'altro a duello... il vostro leader accetterà
    sempre un'eventuale sfida prima di darsi alla fuga." ``_maybe_
    fight_duel()`` calls this once per direction and ORs the results,
    since either side's own aggression can trigger a challenge that the
    other side must then accept.

    Folds in the neutral-province Hero exception from the same rule
    text: as `challenger`, such a Hero never challenges (forced
    ``False``, unconditional -- "non sfidano mai"); as the responding
    `target`, forces acceptance ``True`` unless ``Temper.COWARDLY``, in
    which case the exception simply doesn't apply here and the ordinary
    ``sep_accepts_challenge()`` result governs instead (the rule gives
    no separate formula for a Cowardly neutral-province Hero).
    """

    if _commander_governs_neutral_province(state, challenger) is not None:
        is_aggressive = False
    else:
        is_aggressive = sep_is_aggressive(challenger_sep, state)
    if not is_aggressive:
        return False

    target_neutral_leader = _commander_governs_neutral_province(state, target)
    if target_neutral_leader is not None and target_neutral_leader.temper is not Temper.COWARDLY:
        return True
    return sep_accepts_challenge(target_sep, state)


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

    **Phase 389 addendum -- ``Maneuver.FLEE`` as the attacker's own first
    tactic, real and now wired.** AKGEN's own `battle_engine.
    preliminary_commander_duel` confirms the rest of the "escape"/
    "consequence" rules this docstring above already partially covers:
    "Flee as the first tactic refuses immediately" (no combat is
    resolved at all) and "Flee always succeeds at a battle duel...
    units led by the fleeing... commander fight at strength 0.75" -- the
    exact same ``apply_duel_demoralization`` penalty an ordinary duel
    loss already applies. When ``duel_maneuvers``' own first entry is
    ``Maneuver.FLEE``, this function now applies that penalty to the
    attacker's own side directly and returns immediately, no rng
    consumed (a guaranteed escape, not a roll) and no combat resolved.

    **Phase 669 -- the duel's own real trigger is now wired**, closing
    what this docstring previously named as the top blocker of this
    cluster. Rulebook [5.10] (``Regolamento AK.txt:1818-1832``): "Se
    uno dei due ha un Piano Speciale d'Incontro che contiene un'azione
    aggressiva e nessun ordine Fuggire, allora quel comandante sfiderà
    l'altro a duello... il vostro leader accetterà sempre un'eventuale
    sfida prima di darsi alla fuga" -- **genuinely bidirectional**,
    either side's own aggression can trigger a challenge the other side
    must then accept, not attacker-challenges/defender-accepts fixed
    roles. When ``state`` is given, ``_commander_challenges()`` is
    called once per direction (OR'd together) against each side's own
    real, per-turn ``LeaderState.special_encounter_plan`` (Phase 669,
    populated by ``turn/turn_processor.py run_turn()`` before phase 0
    from the leader's own real ``SP:`` block, decoded via ``turn/
    sep_decode.py decode_special_encounter_plan()``, Phase 659) --
    no challenge from either side means **no duel occurs at all**,
    the same ``_DuelOutcome(None, None, None)`` shape this function
    already returns for an unled side. An unset SEP (``()``, the
    default for any leader ``run_turn()`` never populated, or when
    ``state is None``) reproduces this project's pre-Phase-669
    always-duel default exactly -- ``sep_is_aggressive(())``/``sep_
    accepts_challenge(())`` both resolve `True` (`Plan_Intent`'s own
    real empty-plan fallback), so no existing caller's behavior changed.
    Also folds in [5.10]'s own further exception, user-confirmed
    directly: a real Hero/King (not the garrison fallback) currently
    commanding a province nobody owns never challenges, and always
    accepts unless Cowardly (``_commander_governs_neutral_province()``).

    **Phase 675 -- ``duel_maneuvers``-threading, the SEP roadmap's own
    last open item, now closed.** The *trigger* check above already
    resolves ``attacker_sep``/``defender_sep`` (each side's own real,
    per-turn ``special_encounter_plan``) purely to decide whether a
    duel happens at all; this data is now reused for the resolution
    too, instead of being thrown away. When the caller doesn't supply
    ``duel_maneuvers`` explicitly (``None``, still overridable), it
    defaults to the attacker's own ``attacker_sep`` -- and, when ``use_
    real_duel_combat`` is on, the defender's own ``defender_sep`` is
    threaded into ``resolve_challenge_combat()`` as ``target_tactics``,
    giving the defender the same genuine bidirectional Cast-timing
    agency Phase 674 already built for Challenge/Pursue (previously
    the defender was purely passive in a real-combat Duel regardless
    of its own plan). The Phase 389 Flee-first-tactic branch just above
    can never newly fire via this default: Phase 669's own trigger
    predicates (``sep_is_aggressive``/``sep_accepts_challenge``) already
    exclude a Flee-first SEP from ever reaching a triggered duel in the
    first place, verified by tracing both predicates directly.
    **Still genuinely out of scope**: ``use_real_duel_combat`` itself
    still defaults ``False`` for every production caller in this
    project (confirmed by grep) -- this is what keeps all of the above
    dormant in real games today, a separate, larger, already-repeatedly-
    deferred decision (``apply_fanaticism`` was once in this same bucket
    too, but Phase 744 resolved it -- see this module's own Phase 35/390
    addenda above), not flipped here. A later-than-first Flee's own
    "attempts combat first" refusal ordering during a triggered duel's
    own resolution remains the same still-unaddressed limitation it
    always was.

    **Deliberately still not modeled, two further real, AKGEN-confirmed,
    but genuinely blocked pieces of this same cluster:**
    - **``coward_bluff``** ("entering the duel and temper refusing
      combat, chance 2/3 to avoid the demoralization penalty") needs the
      Temper Table's own flee-probability/refusal-to-Meet mechanic --
      ``turn/encounter.py``'s own Phase 284 addendum already names this
      exact mechanic and explicitly defers it project-wide as "a natural,
      distinct follow-up phase," not something this function should
      invent a bespoke version of just for Duels.
    - A related, pre-existing (not new) ambiguity: **Charm's own "target
      flees" and Augur Combat's own "caster flees" branches both collapse
      into the same bare ``combat_result.fled`` boolean**, with no
      direction recorded -- applying AKGEN's now-confirmed "Charm escape
      has the same consequence" rule correctly would require knowing
      *which* side fled, and ``_resolve_personal_combat_cast`` doesn't
      carry that today. Safely disambiguating it needs a shared-code
      change touching Challenge/Pursue too, not a narrow Duel-only fix --
      left as its own explicit, documented follow-up rather than guessing
      a direction that would misattribute the penalty half the time.
    """

    if attacker_commander is None or defender_commander is None:
        return _DuelOutcome(None, None, None)

    attacker_sep: list[SearchTactic] = []
    defender_sep: list[SearchTactic] = []
    if state is not None:
        attacker_sep = _side_special_encounter_plan(state, attacker_commander)
        defender_sep = _side_special_encounter_plan(state, defender_commander)
        attacker_challenges = _commander_challenges(state, attacker_commander, attacker_sep, defender_commander, defender_sep)
        defender_challenges = _commander_challenges(state, defender_commander, defender_sep, attacker_commander, attacker_sep)
        if not (attacker_challenges or defender_challenges):
            return _DuelOutcome(None, None, None)

    attacker_commander_units = _units_led_by(attacker_armies, attacker_units, attacker_commander.leader_id)
    defender_commander_units = _units_led_by(defender_armies, defender_units, defender_commander.leader_id)

    # Phase 675: the attacker's own real Special Encounter Plan is now
    # the default `duel_maneuvers` whenever the caller doesn't supply
    # one explicitly -- see this function's own Phase 675 addendum.
    if duel_maneuvers is None and state is not None:
        duel_maneuvers = attacker_sep

    if duel_maneuvers:
        first_tactic = duel_maneuvers[0]
        first_maneuver = first_tactic if isinstance(first_tactic, Maneuver) else first_tactic.maneuver
        if first_maneuver is Maneuver.FLEE:
            demoralized_by_id = {u.source_id: u for u in apply_duel_demoralization(attacker_commander_units)}
            for index, unit in enumerate(attacker_units):
                if unit.source_id in demoralized_by_id:
                    attacker_units[index] = demoralized_by_id[unit.source_id]
            return _DuelOutcome(attacker_commander.leader_id, defender_commander.leader_id, "attacker", loser_fled=True)

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
        # Phase 675: the defender's own real Special Encounter Plan is
        # threaded in as `target_tactics`, giving it the same genuine
        # bidirectional Cast-timing agency Phase 674 already built for
        # Challenge/Pursue -- previously the defender was purely
        # passive in a real-combat Duel, regardless of its own plan.
        combat_result = resolve_challenge_combat(
            tactics, attacker_leader, attacker_combatant, defender_leader, defender_combatant, state, rng,
            target_tactics=defender_sep,
        )
        # Phase 686: AKGEN_reverse_engineering_report (2).md SS3.3's own
        # Melee/Archery rows -- "evento di mischia/duello qualificante"/
        # "evento di tiro riuscito" -- a landed hit, credited once per
        # encounter per side, independent of who wins. Dormant today
        # (this whole block only runs when a production caller opts into
        # `use_real_duel_combat=True`, which none do -- see this
        # function's own Phase 675 addendum), wired anyway for when it's
        # eventually flipped on. The garrison-commander fallback (`None`
        # leader) has no LeaderState to credit and is skipped.
        if attacker_leader is not None:
            if any(s.hit for s in combat_result.melee_swings if s.attacker == "a"):
                add_experience(attacker_leader, Ability.MELEE, 10, rng)
            if any(s.hit for s in combat_result.fire_arrow_shots if s.shooter == "a"):
                add_experience(attacker_leader, Ability.ARCHERY, 10, rng)
        if defender_leader is not None:
            if any(s.hit for s in combat_result.melee_swings if s.attacker == "b"):
                add_experience(defender_leader, Ability.MELEE, 10, rng)
            if any(s.hit for s in combat_result.fire_arrow_shots if s.shooter == "b"):
                add_experience(defender_leader, Ability.ARCHERY, 10, rng)
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
    illusory_terrain: Terrain | None = None,
    illusory_terrain_enhanced: bool = False,
) -> set[int]:
    """Rulebook [7.3]: chase down some of a clean-swept, retreating loser's armies before they escape.

    Returns the set of army ids caught and destroyed (already removed
    from ``state`` and recorded on ``report``) -- callers should skip
    ``_retreat_or_disband`` for those.

    ``is_island`` (Phase 282)/``illusory_terrain``+``illusory_terrain_
    enhanced`` (Phase 724/757): the same province-level facts
    `fight_battle()` already resolved for the main battle itself, passed
    through unchanged so a retreating army's own strength during the
    chase honors them too -- see `turn/strength.py compute_effective_
    strength()`'s own docstring.
    """

    retreating_units = []
    for army in losing_armies:
        kingdom = state.kingdoms[army.kingdom_id]
        pursued_quality = Quality(max(int(Quality.DEPLETED), int(army.quality) - 1))
        strength = compute_effective_strength(
            army.army_type, kingdom.race, pursued_quality, terrain, is_defender=True, is_island=is_island,
            illusory_terrain=illusory_terrain, illusory_terrain_enhanced=illusory_terrain_enhanced,
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


def _apply_wingman_merit(state: GameState, battle_result: BattleResult) -> None:
    """Phase 444: Air Force Commander (Office.WINGMAN, id 48) merit --
    ``AKGEN_reverse_engineering_report (2).md`` SS19. Per unit-vs-unit
    column contest resolved in battle (the same granularity ``_direct_
    destruction_probabilities`` already reads): ``+1`` to the leader
    commanding a winning Dragons/Eagles unit, ``-1`` to the leader
    commanding a losing one. ``OVERFLIGHT_AIR`` (Dragons + Eagles only,
    Vampires excluded) is an exact match for the real ``Air_Unit(army,
    false)`` predicate's own literal ``false`` flag -- no new constant
    needed. Independent per column; the opposing unit need not itself be
    an air unit, and neither side needs multipliers of any kind. A unit
    with no commanding leader (``ArmyState.commanded_by is None``, or no
    matching army/leader record at all) credits nobody, matching the
    real ``aleader = 255`` no-op.
    """

    for column in battle_result.columns:
        if column.bres == 0:
            continue
        attacker_front = column.attacker_units[0]
        defender_front = column.defender_units[0]
        if column.bres > 0:
            winner_unit, loser_unit = attacker_front, defender_front
        else:
            winner_unit, loser_unit = defender_front, attacker_front

        for unit, delta in ((winner_unit, 1), (loser_unit, -1)):
            if unit.army_type not in OVERFLIGHT_AIR or unit.source_id is None:
                continue
            army = state.armies.get(unit.source_id)
            if army is None or army.commanded_by is None:
                continue
            leader = state.leaders.get(army.commanded_by)
            if leader is None:
                continue
            leader.merit_tally.air_combat_merit += delta


_FORMATION_DIVISOR_BY_DEPTH = (
    FORMATION_DIVISOR["front"],
    FORMATION_DIVISOR["second"],
    FORMATION_DIVISOR["third"],
)


def _formation_divisor_for_depth(index: int) -> int:
    """`index` is a unit's own position in its column's `attacker_units`/
    `defender_units` list (0 = front) -- see `_formation_divisors`'
    own docstring. Any depth past third falls to `fourth_and_later`."""

    if index < len(_FORMATION_DIVISOR_BY_DEPTH):
        return _FORMATION_DIVISOR_BY_DEPTH[index]
    return FORMATION_DIVISOR["fourth_and_later"]


def _formation_divisors(battle_result: BattleResult) -> dict[int, int]:
    """Phase 372: every surviving-to-this-point army's own real
    formation depth, keyed by `army_id`, for `turn/aftermath.py
    roll_quality_change`'s own `formation_divisor` parameter.

    Nothing new to track -- `BattleColumnResult.attacker_units`/
    `defender_units` (`turn/battle_line.py assign_battle_lines`, Phase 6)
    were already ordered front-to-back for every column; a unit's own
    index in that list *is* its formation depth, unchanged since before
    this project's own real battle-resolution work began.
    """

    divisors: dict[int, int] = {}
    for column in battle_result.columns:
        for index, unit in enumerate(column.attacker_units):
            if unit.source_id is not None:
                divisors[unit.source_id] = _formation_divisor_for_depth(index)
        for index, unit in enumerate(column.defender_units):
            if unit.source_id is not None:
                divisors[unit.source_id] = _formation_divisor_for_depth(index)
    return divisors


def _column_bres_by_army_id(battle_result: BattleResult) -> dict[int, int]:
    """Phase 423: each army's own column's real `BRES` score (`turn/
    combat.py column_bres`), oriented to *that army's own side* and
    keyed by `army_id`, for `turn/aftermath.py roll_quality_change`'s
    own `score` parameter.

    **A documented, unconfirmed interpretation -- not a recovered
    formula.** `AKGEN_reverse_engineering_report.md`'s own battle-engine
    section (the same disassembly `column_bres` itself comes from)
    describes the quality-*gain* multiplier's own input as a value it
    calls `P` ("100% se il confronto effettivo restituisce P>=0, 60% con
    P=-1, 20% con P=-2, 0% con P<=-3"), sitting immediately after its own
    `BRES` writeup and sharing the same `-5..+5`-scale thresholds
    `MERIT_MULTIPLIER` already uses -- but the report never writes the
    equation "P = BRES" outright, and no raw `AK.EXE`/`AK.OVR` binary is
    available in this project to disassemble further and settle it. This
    function assumes the two are the same value, which is the only real
    per-column performance number this project has, rather than leaving
    `score` at its own neutral default forever -- explicitly flagged
    here (and in `roll_quality_change`'s own call sites below) so a
    future phase that finds a real, sourced answer can replace it
    outright, not silently build on top of a guess mistaken for fact.

    `BRES > 0` favors side 1 (attacker) in `column_bres`'s own
    convention (confirmed by `battle_resolution.py`'s own `winning_units
    = column.attacker_units if column.bres > 0 else column.defender_
    units`) -- so an attacker's own army keeps `bres` as-is, and a
    defender's own army gets `-bres`, both oriented so a positive value
    means "my own side did well in this column."
    """

    scores: dict[int, int] = {}
    for column in battle_result.columns:
        for unit in column.attacker_units:
            if unit.source_id is not None:
                scores[unit.source_id] = column.bres
        for unit in column.defender_units:
            if unit.source_id is not None:
                scores[unit.source_id] = -column.bres
    return scores


WEREBEAST_BITE_CHANCE = 0.40


def _apply_werebeast_bites(battle_result: BattleResult, state: GameState, rng: random.Random) -> None:
    """AKGEN's own confirmed `battle_engine.special_events` "Werebeasts
    defeat humanoids" row: "bite and end-of-turn transformation; fleets
    excluded" (Phase 392). Checked per column, per losing humanoid unit
    (`turn/battle_line.py BattleUnit.is_humanoid_race`): if the column's
    own winning side includes a Werebeast unit (`ArmyType.WEREBEASTS`)
    and a losing unit is both humanoid-race and not a Fleet, a confirmed
    40% chance queues that unit's own army id (`BattleUnit.source_id`)
    in `GameState.werebeast_bitten_army_ids` for the real end-of-turn
    transformation (`turn/turn_processor.py _apply_werebeast_
    transformations`) -- not applied immediately, since "end-of-turn" is
    explicit in the source and this project's own once-per-`run_turn()`
    housekeeping point is the one clean, consistent place to apply it
    regardless of which phase/battle triggered the bite.

    A genuine per-column tie (`column.bres == 0`) is skipped outright --
    nobody "defeated" anybody, so `BattleColumnResult.attacker_won`'s own
    "False for both a defender win and a tie" collapse can't be trusted
    to pick the real winning side here.
    """

    for column in battle_result.columns:
        if column.bres == 0:
            continue
        winning_units = column.attacker_units if column.bres > 0 else column.defender_units
        losing_units = column.defender_units if column.bres > 0 else column.attacker_units
        if not any(unit.army_type is ArmyType.WEREBEASTS for unit in winning_units):
            continue
        for unit in losing_units:
            if not unit.is_humanoid_race or unit.army_type is ArmyType.FLEET or unit.source_id is None:
                continue
            if rng.random() < WEREBEAST_BITE_CHANCE:
                state.werebeast_bitten_army_ids.add(unit.source_id)


MONSTER_SUMMONING_INVASION_DEFECTION_CHANCE = 0.33
MONSTER_SUMMONING_PLAYER_LED_DEFECTION_CHANCE = 0.165


def _side_has_present_leader_with_ability(
    state: GameState, province_coord: HexCoord, kingdom_ids: frozenset[int], ability: AdvancedAbility
) -> bool:
    """Find Water (Phase 511): "If the Explorer is present at a battle" --
    read literally as *any* leader physically located (``LeaderState.
    location``) in the battle province who belongs to one of this side's
    kingdoms and already holds ``ability``, not specifically the side's
    own Supreme Commander (the rulebook says "present," not
    "commanding," unlike ``combat_ability_level``/``duellist_side`` above).
    """

    return any(
        leader.kingdom_id in kingdom_ids and leader.location == province_coord and ability in leader.advanced_abilities
        for leader in state.leaders.values()
    )


def _apply_monster_summoning_aid(
    units: list[BattleUnit],
    commander: Commander | None,
    state: GameState,
    province_coord: HexCoord,
    bounds: MapBounds,
    *,
    is_defender: bool,
    terrain: Terrain,
    combat_ability_level: int,
    combat_ability_mastery_bonus: float = 0.0,
    apply_fanaticism: bool,
    own_explored_percent: int,
    opponent_kingdom_ids: frozenset[int],
    is_island: bool,
    illusory_terrain: Terrain | None = None,
    illusory_terrain_enhanced: bool = False,
    rng: random.Random,
    explorer_find_water: bool = False,
) -> None:
    """AKGEN's own confirmed `battle_engine.special_events` "Dragon/Eagle/
    Whale summoning item" row: "adjacent unled matching units aid the
    bearer" -- a side's Supreme Commander holding one of `models/
    treasure.py MONSTER_SUMMONING_TREASURE`'s three race-matching items
    (the same "commander only, no King-substitution carve-out" convention
    `RACE_LEADERSHIP_TREASURE`/`turn/army_quality.py` already established
    for this codebase) draws aid from every *unled* (`ArmyState.
    commanded_by is None`) army of the matching monstrous race
    (`models/army_type.py MONSTROUS_ARMY_RACE`) sitting in a province
    directly adjacent (`turn/movement.py neighbors`) to the battle
    province.

    Each eligible adjacent army rolls independently: AKGEN's own
    confirmed 33% chance during an "invasion" -- read here as
    `ArmyState.kingdom_id is None`, this project's own Phase 97 mercenary
    /unclaimed-army convention for a population with no strategic owner
    at all, since AKGEN never defines "invasion" any more precisely than
    that -- or half that, 16.5%, if the army is player-led (`kingdom_id
    is not None`: it belongs to a kingdom even though it currently has no
    personal field commander).

    A successful roll contributes that army's battle strength to this
    side for this battle only, then appends the resulting unit directly
    to `units`. A player-led aiding army is built via the same
    `_build_battle_units` machinery as every other unit on the side (it
    has a real owning `KingdomState` to derive terrain/ability/
    exploration/fanaticism/home-province context from, same as any other
    army of that kingdom). A truly wild (`kingdom_id is None`) aiding
    army has no `KingdomState` to derive any of that from, so it gets a
    bare `compute_effective_strength` call instead -- quality and terrain
    only, plus the same side-wide `combat_ability_level`/exploration
    figures already uniformly applied to every unit on the side, with no
    kingdom-derived bonuses (home province, race item, fanaticism,
    Druidic shortfall) since none of those have any meaning for a
    population that was never anyone's army.

    Either way, the aiding `ArmyState` is deliberately never added to
    `attacker_armies`/`defender_armies` (the lists `fight_battle` uses
    for post-battle quality-change/retreat/destruction) -- matching
    AKGEN's own "aid the bearer" wording, not "join the bearer's army":
    the aiding army experiences none of a real participant's post-battle
    consequences.
    """

    if commander is None or commander.leader_id is None:
        return
    held_treasures = {item.treasure for item in state.items_held_by(commander.leader_id)}
    matching_race = next(
        (race for race, treasure in MONSTER_SUMMONING_TREASURE.items() if treasure in held_treasures),
        None,
    )
    if matching_race is None:
        return
    matching_army_type = next(
        (army_type for army_type, race in MONSTROUS_ARMY_RACE.items() if race is matching_race),
        None,
    )
    if matching_army_type is None:
        return

    for neighbor_coord in neighbors(province_coord, bounds):
        for army in state.armies_at(neighbor_coord):
            if army.army_type is not matching_army_type or army.commanded_by is not None:
                continue
            if army.kingdom_id is None:
                defection_chance = MONSTER_SUMMONING_INVASION_DEFECTION_CHANCE
            else:
                defection_chance = MONSTER_SUMMONING_PLAYER_LED_DEFECTION_CHANCE
            if rng.random() >= defection_chance:
                continue
            if army.kingdom_id is None:
                strength = compute_effective_strength(
                    matching_army_type, matching_race, army.quality, terrain,
                    is_defender=is_defender, combat_ability_level=combat_ability_level,
                    combat_ability_mastery_bonus=combat_ability_mastery_bonus,
                    own_explored_percent=own_explored_percent,
                    is_island=is_island,
                    illusory_terrain=illusory_terrain,
                    illusory_terrain_enhanced=illusory_terrain_enhanced,
                )
                units.append(BattleUnit(matching_army_type, strength, source_id=army.army_id))
            else:
                units.extend(
                    _build_battle_units(
                        [army], state, is_defender=is_defender, terrain=terrain, province_coord=province_coord,
                        rng=rng, combat_ability_level=combat_ability_level,
                        combat_ability_mastery_bonus=combat_ability_mastery_bonus,
                        apply_fanaticism=apply_fanaticism,
                        own_explored_percent=own_explored_percent,
                        opponent_kingdom_ids=opponent_kingdom_ids, is_island=is_island,
                        illusory_terrain=illusory_terrain,
                        illusory_terrain_enhanced=illusory_terrain_enhanced,
                        explorer_find_water=explorer_find_water,
                    )
                )


# Phase 661: the 7 alignment-King titles' own "supreme commander ->
# fanatic front-line unit" bonus (see _build_battle_units()'s own Phase
# 661 addendum). `turn/merit_points.py _alignment_king_merit_points()`
# gates each office to exactly one real Alignment, matching this table.
_ALIGNMENT_KING_OFFICE: dict[Alignment, Office] = {
    Alignment.DIVINE: Office.DIVINE_KING,
    Alignment.GOOD: Office.GOOD_KING,
    Alignment.DRUID: Office.DRUID_KING,
    Alignment.NEUTRAL: Office.NEUTRAL_KING,
    Alignment.PAGAN: Office.PAGAN_KING,
    Alignment.EVIL: Office.EVIL_KING,
    Alignment.UNDEAD: Office.UNDEAD_KING,
}


def _alignment_king_office_for(state: GameState, commander_leader: LeaderState | None) -> Office | None:
    """Which of the 7 alignment-King offices (if any) ``commander_leader``
    currently holds -- ``None`` for a garrison commander (``leader_id=
    None``, no ``LeaderState``), a kingdomless leader, or a leader whose
    own Kingdom's Alignment isn't one of the 7 (e.g. Mechanical/Special)
    or who simply isn't the current title-holder. One real
    ``resolve_office_holder()`` call, not a 7-office scan -- since the
    offices are mutually exclusive per leader (see the module-level
    ``_ALIGNMENT_KING_OFFICE`` comment), the commander's own Kingdom
    Alignment already narrows it to at most one office to check.
    """

    if commander_leader is None or commander_leader.kingdom_id is None:
        return None
    kingdom = state.kingdoms.get(commander_leader.kingdom_id)
    if kingdom is None:
        return None
    office = _ALIGNMENT_KING_OFFICE.get(kingdom.alignment)
    if office is None:
        return None
    holder = resolve_office_holder(state, office)
    return office if holder is not None and holder.leader_id == commander_leader.leader_id else None


def _supreme_commander_exploration_override(
    state: GameState, commander_leader: LeaderState | None, terrain: Terrain
) -> int | None:
    """Phase 662: Admiral/Druid King's own shared "always 100% exploration
    for this side" bonus -- ``models/office.py OFFICE_TITLE_DESCRIPTION``:
    Admiral -- "in any sea battle where < is the supreme commander,
    provincial exploration will always be treated as being 100%";
    Druid King -- the identical clause for "any land battle." Same real
    land/sea split `_combat_ability_for_terrain()` already uses (Naval vs
    Tactical) -- Admiral's own text was outside the Phase 660 audit's own
    scope (it only checked the 39 non-core titles), found while wiring
    Druid King's half of this exact shared mechanic; shipping both
    together rather than leaving Admiral's own identical, equally-real
    clause unwired.

    Returns ``100`` (the real, sourced value -- confirmed against
    ``turn/strength.py exploration_advantage_multiplier()``'s own real
    formula, where `100` gives exactly the rulebook's own stated +25%
    maximum, not a guessed round number) when eligible, else ``None`` (no
    override -- the caller keeps this side's own real accumulated
    percentage).
    """

    if commander_leader is None:
        return None
    office = Office.ADMIRAL if terrain is Terrain.SEA else Office.DRUID_KING
    holder = resolve_office_holder(state, office)
    return 100 if holder is not None and holder.leader_id == commander_leader.leader_id else None


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
    ``_maybe_fight_duel``'s own Phase 273 note. Leaving it ``None``
    (every real caller today) now defaults to the attacker's own real,
    per-turn ``special_encounter_plan`` when ``state`` has one (Phase
    675) rather than always resolving Melee-only -- an explicit value
    still overrides it.
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

    # Phase 649: SAY.PAS `_BLeaders`/`_BLList` (BATLDR.X's own real
    # trigger, `SAY.PAS:1028-1048`) -- for each side, every distinct
    # leader who commands at least one army in `attacker_armies`/
    # `defender_armies`. Computed here (not inside `_select_side_
    # commander()`, which discards every candidate but the winning
    # Supreme Commander) since both army lists are already resolved.
    # A united multi-attacker battle (`fight_multi_attacker_battle()`
    # calls this function once per merged group, its own `combined_
    # army_ids` already spanning every party) naturally recovers every
    # commanding leader across the whole side, not just one party's --
    # no separate wiring needed there.
    attacker_commander_ids = {army.commanded_by for army in attacker_armies if army.commanded_by is not None}
    defender_commander_ids = {army.commanded_by for army in defender_armies if army.commanded_by is not None}
    attacker_commanding_leader_ids = sorted(attacker_commander_ids)
    defender_commanding_leader_ids = sorted(defender_commander_ids)

    # Phase 658: the real `_BLList`'s other half -- a leader present at
    # the battle but commanding no armies (`tentdex[fn] > cdrdex[fn]`,
    # `"< was there, leading no armies."`). The Phase 649 comment this
    # replaces called this unrepresentable ("no way to know a leader
    # was physically present without also commanding at least one of
    # the armies actually fighting") -- reconsidered: `LeaderState.
    # location` already tracks a leader's real position independently
    # of army command, so "present" is answerable directly: any leader
    # loyal to one of this side's own real Kingdoms (every distinct
    # `kingdom_id` actually represented in `attacker_armies`/`defender_
    # armies` -- the same multi-Kingdom-per-side shape `attacker_
    # commanding_leader_ids` above already tolerates for an allied
    # attack) whose own `location` is this exact battle province, and
    # who isn't already one of this side's own commanders. `ldrtent[fn]`'s
    # own real population logic doesn't survive (same "missing main
    # program" class of gap as the commanding roster's own tent order),
    # so which Kingdom(s) count as "this side" is this project's own
    # reasonable reading, not a literal citation.
    attacker_side_kingdom_ids = {army.kingdom_id for army in attacker_armies if army.kingdom_id is not None}
    defender_side_kingdom_ids = {army.kingdom_id for army in defender_armies if army.kingdom_id is not None}
    attacker_present_leader_ids = sorted(
        leader.leader_id
        for leader in state.leaders.values()
        if leader.location == province_coord
        and leader.kingdom_id in attacker_side_kingdom_ids
        and leader.leader_id not in attacker_commander_ids
    )
    defender_present_leader_ids = sorted(
        leader.leader_id
        for leader in state.leaders.values()
        if leader.location == province_coord
        and leader.kingdom_id in defender_side_kingdom_ids
        and leader.leader_id not in defender_commander_ids
    )

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
    # Illusory Terrain (Phase 724) -- see turn/strength.py compute_
    # effective_strength()'s own docstring for the real/illusory blend
    # this feeds. Rulebook [4.23.1]; None (no effect) unless a real spell
    # cast set it. illusory_terrain_enhanced (Phase 757) widens that same
    # blend from 50/50 to 33/67 when the caster held AdvancedAbility.
    # ENHANCED_ILLUSORY_TERRAIN -- meaningless (never read) when
    # illusory_terrain is None.
    illusory_terrain = province.illusory_terrain
    illusory_terrain_enhanced = province.illusory_terrain_enhanced

    ability = _combat_ability_for_terrain(terrain)
    attacker_commander = _select_side_commander(attacker_armies, state, ability, allow_garrison_fallback=False)
    defender_commander = _select_side_commander(defender_armies, state, ability, allow_garrison_fallback=True)
    attacker_ability_level = attacker_commander.tactical_ability if attacker_commander is not None else 0
    defender_ability_level = defender_commander.tactical_ability if defender_commander is not None else 0

    # Tactical/Naval Mastery (Phase 512): the same Supreme Commanders'
    # own flat Mastery bonus, resolved once per side -- see
    # _mastery_bonus_for's own docstring.
    attacker_commander_leader = (
        state.leaders.get(attacker_commander.leader_id)
        if attacker_commander is not None and attacker_commander.leader_id is not None
        else None
    )
    defender_commander_leader = (
        state.leaders.get(defender_commander.leader_id)
        if defender_commander is not None and defender_commander.leader_id is not None
        else None
    )
    attacker_mastery_bonus = _mastery_bonus_for(attacker_commander_leader, ability)
    defender_mastery_bonus = _mastery_bonus_for(defender_commander_leader, ability)

    # Tactical/Naval Combined Arms (Phase 513/514): "when in supreme
    # command at a land/sea battle" -- see _combined_arms_for's own Phase
    # 514 docstring for why gating on `ability` alone already encodes the
    # terrain condition, no separate check needed.
    attacker_combined_arms = _combined_arms_for(attacker_commander_leader, ability)
    defender_combined_arms = _combined_arms_for(defender_commander_leader, ability)

    # Duellist / "Captain of the Musketeers" (Phase 471, SS17.7): "Quando
    # il titolare è comandante supremo in battaglia" -- resolved once,
    # here, before _build_battle_units builds either side's own units
    # (both Supreme Commanders are already known -- see that function's
    # own Phase 471 addendum for why this can't be deferred to inside it).
    duellist_holder_id = resolve_office_holder(state, Office.DUELLIST)
    duellist_holder_id = duellist_holder_id.leader_id if duellist_holder_id is not None else None
    attacker_is_duellist_side = (
        duellist_holder_id is not None
        and attacker_commander is not None
        and attacker_commander.leader_id == duellist_holder_id
    )
    defender_is_duellist_side = (
        duellist_holder_id is not None
        and defender_commander is not None
        and defender_commander.leader_id == duellist_holder_id
    )

    # The 7 alignment-King titles' own shared fanatic-front-line-unit
    # bonus (Phase 661) -- resolved the same way and at the same point
    # as Duellist just above, reusing attacker_commander_leader/
    # defender_commander_leader (already resolved for the Mastery bonus).
    attacker_alignment_king_office = _alignment_king_office_for(state, attacker_commander_leader)
    defender_alignment_king_office = _alignment_king_office_for(state, defender_commander_leader)

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
    # Admiral/Druid King (Phase 662) -- see _supreme_commander_
    # exploration_override()'s own docstring. Overrides this side's own
    # real accumulated percentage outright (not additive), matching the
    # real text's own unconditional "will always be treated as being 100%".
    attacker_exploration_override = _supreme_commander_exploration_override(state, attacker_commander_leader, terrain)
    if attacker_exploration_override is not None:
        attacker_explored = attacker_exploration_override
    defender_exploration_override = _supreme_commander_exploration_override(state, defender_commander_leader, terrain)
    if defender_exploration_override is not None:
        defender_explored = defender_exploration_override

    attacker_kingdom_ids = frozenset(army.kingdom_id for army in attacker_armies if army.kingdom_id is not None)
    defender_kingdom_ids = frozenset(army.kingdom_id for army in defender_armies if army.kingdom_id is not None)

    # Find Water (Phase 511, Advanced Ability) -- see _side_has_present_
    # leader_with_ability's own docstring: any leader physically present
    # at this province who belongs to the side and already holds the
    # ability, not necessarily the side's own Supreme Commander.
    attacker_find_water = _side_has_present_leader_with_ability(
        state, province_coord, attacker_kingdom_ids, AdvancedAbility.EXPLORER_FIND_WATER
    )
    defender_find_water = _side_has_present_leader_with_ability(
        state, province_coord, defender_kingdom_ids, AdvancedAbility.EXPLORER_FIND_WATER
    )

    attacker_units = _build_battle_units(
        attacker_armies, state, is_defender=False, terrain=terrain, province_coord=province_coord, rng=rng,
        combat_ability_level=attacker_ability_level, combat_ability_mastery_bonus=attacker_mastery_bonus,
        apply_fanaticism=apply_fanaticism,
        own_explored_percent=attacker_explored,
        opponent_kingdom_ids=defender_kingdom_ids, is_island=is_island,
        illusory_terrain=illusory_terrain,
        illusory_terrain_enhanced=illusory_terrain_enhanced,
        duellist_side=attacker_is_duellist_side,
        alignment_king_office=attacker_alignment_king_office,
        explorer_find_water=attacker_find_water,
    )
    defender_units = _build_battle_units(
        defender_armies, state, is_defender=True, terrain=terrain, province_coord=province_coord, rng=rng,
        combat_ability_level=defender_ability_level, combat_ability_mastery_bonus=defender_mastery_bonus,
        apply_fanaticism=apply_fanaticism,
        own_explored_percent=defender_explored,
        opponent_kingdom_ids=attacker_kingdom_ids, is_island=is_island,
        illusory_terrain=illusory_terrain,
        illusory_terrain_enhanced=illusory_terrain_enhanced,
        duellist_side=defender_is_duellist_side,
        alignment_king_office=defender_alignment_king_office,
        explorer_find_water=defender_find_water,
    )

    # Phase 393: Dragon/Eagle/Whale summoning-item aid, checked for both
    # sides right after their own real units are built (so the aiding
    # units get the same terrain/ability/exploration treatment) and
    # before resolve_battle() runs -- see _apply_monster_summoning_aid's
    # own docstring.
    monster_summoning_bounds = MapBounds(state.board_width, state.board_height)
    _apply_monster_summoning_aid(
        attacker_units, attacker_commander, state, province_coord, monster_summoning_bounds,
        is_defender=False, terrain=terrain, combat_ability_level=attacker_ability_level,
        combat_ability_mastery_bonus=attacker_mastery_bonus,
        apply_fanaticism=apply_fanaticism, own_explored_percent=attacker_explored,
        opponent_kingdom_ids=defender_kingdom_ids,
        is_island=is_island, illusory_terrain=illusory_terrain,
        illusory_terrain_enhanced=illusory_terrain_enhanced, rng=rng,
        explorer_find_water=attacker_find_water,
    )
    _apply_monster_summoning_aid(
        defender_units, defender_commander, state, province_coord, monster_summoning_bounds,
        is_defender=True, terrain=terrain, combat_ability_level=defender_ability_level,
        combat_ability_mastery_bonus=defender_mastery_bonus,
        apply_fanaticism=apply_fanaticism, own_explored_percent=defender_explored,
        opponent_kingdom_ids=attacker_kingdom_ids,
        is_island=is_island, illusory_terrain=illusory_terrain,
        illusory_terrain_enhanced=illusory_terrain_enhanced, rng=rng,
        explorer_find_water=defender_find_water,
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

    # Druidic monster battle assistance (Phase 453, AKGEN_reverse_
    # engineering_report (2).md SS5) -- whichever side is Druidic-aligned
    # may get help from a Feature's own guardian monster at this
    # province. See turn/druidic_monster_aid.py's own module docstring
    # for the full formula; a Druidic side fighting another Druidic side
    # is a natural no-op via monster_join_probability's own d_D >= d_E
    # rule, so no special case is needed beyond computing it for
    # whichever side(s) actually qualify. The attacker's own Alignment is
    # always known (a real acting Kingdom); the defender's is the
    # province's owning Kingdom's own Alignment -- unclaimed/wilderness
    # provinces (no owner) simply can't supply an enemy_alignment for the
    # attacker's own assistance roll, matching how Exploration advantage
    # above already treats a None owner as "nothing to compare against".
    attacker_column_bonus: dict[int, int] | None = None
    defender_column_bonus: dict[int, int] | None = None
    # Phase 657: the rich per-column assistance (monster/feature_id, not
    # just the strength number) survives onto BattleReport below so the
    # report layer can narrate MCOME.X/MFIGHT.X with a real name -- see
    # turn/druidic_monster_aid.py's own Phase 657 docstring addendum.
    attacker_monster_assistance: dict[int, DruidicMonsterAssistance] = {}
    defender_monster_assistance: dict[int, DruidicMonsterAssistance] = {}
    attacker_alignment = state.kingdoms[attacker_kingdom_id].alignment
    defender_alignment = state.kingdoms[defender_kingdom_id].alignment if defender_kingdom_id is not None else None
    if Alignment.DRUID in (attacker_alignment, defender_alignment):
        line_length = line_length_for_battle(
            len(attacker_units), len(defender_units), terrain_line_length_cap=terrain_line_length_cap
        )
        if attacker_alignment is Alignment.DRUID and defender_alignment is not None:
            attacker_monster_assistance = find_druidic_monster_assistance(
                state, province_coord, defender_alignment, line_length, rng
            )
            attacker_column_bonus = {
                column: assistance.strength_bonus for column, assistance in attacker_monster_assistance.items()
            }
        if defender_alignment is Alignment.DRUID:
            defender_monster_assistance = find_druidic_monster_assistance(
                state, province_coord, attacker_alignment, line_length, rng
            )
            defender_column_bonus = {
                column: assistance.strength_bonus for column, assistance in defender_monster_assistance.items()
            }

    battle_result = resolve_battle(
        attacker_units,
        defender_units,
        terrain_line_length_cap=terrain_line_length_cap,
        attacker_tactical_ability=attacker_ability_level,
        defender_tactical_ability=defender_ability_level,
        is_first_turn=state.turn_number <= 1,
        attacker_column_bonus=attacker_column_bonus,
        defender_column_bonus=defender_column_bonus,
        attacker_combined_arms=attacker_combined_arms,
        defender_combined_arms=defender_combined_arms,
        rng=rng,
    )

    _apply_werebeast_bites(battle_result, state, rng)

    defender_clean_swept = battle_result.winner == "attacker" and battle_result.defender_columns_won == 0
    attacker_clean_swept = battle_result.winner == "defender" and battle_result.attacker_columns_won == 0

    report = BattleReport(
        battle_result=battle_result,
        conquered=defender_clean_swept,
        attacker_commander_leader_id=duel.attacker_commander_leader_id,
        defender_commander_leader_id=duel.defender_commander_leader_id,
        attacker_commanding_leader_ids=attacker_commanding_leader_ids,
        defender_commanding_leader_ids=defender_commanding_leader_ids,
        duel_loser_side=duel.loser_side,
        duel_loser_fled=duel.loser_fled,
        province_coord=province_coord,
        attacker_kingdom_id=attacker_kingdom_id,
        defender_kingdom_id=defender_kingdom_id,
        attacker_tactical_ability=attacker_ability_level,
        defender_tactical_ability=defender_ability_level,
        attacker_monster_assistance=attacker_monster_assistance,
        defender_monster_assistance=defender_monster_assistance,
        attacker_present_leader_ids=attacker_present_leader_ids,
        defender_present_leader_ids=defender_present_leader_ids,
    )

    _record_battle_merit(
        state, terrain, battle_result,
        duel.attacker_commander_leader_id, duel.defender_commander_leader_id,
        attacker_armies, defender_armies,
    )

    _apply_wingman_merit(state, battle_result)

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

    # Phase 770: `wargames_mastery_by_army_id` (Phase 513) removed from
    # here -- AdvancedAbility.TACTICAL_WARGAMES_MASTERY was mis-wired to
    # this post-battle quality-change roll; the ability's own real text
    # ("when Practicing Tactics (or Naval)") belongs to `turn/practice_
    # execution.py`'s own quality-training mechanic instead. See `turn/
    # aftermath.py roll_quality_change()`'s own Phase 770 addendum.

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

    # Phase 372: real, confirmed post-battle quality-change formula
    # (turn/aftermath.py roll_quality_change, base_quality_change_percent)
    # -- see _formation_divisors' own docstring for why this needed no
    # new state, just reading data this project already had.
    formation_divisor_by_army_id = _formation_divisors(battle_result)

    # Phase 423: score= for roll_quality_change's own gain-side merit
    # multiplier -- see _column_bres_by_army_id's own docstring for why
    # this is a documented, unconfirmed interpretation (BRES assumed to
    # be the source's own unnamed "P"), not a recovered formula.
    score_by_army_id = _column_bres_by_army_id(battle_result)

    attacker_pursuit_destroyed: set[int] = set()
    if attacker_clean_swept and loser_retreats:
        attacker_pursuit_destroyed = _apply_pursuit(
            attacker_armies, defender_units, state, terrain, report, rng, is_island=is_island,
            illusory_terrain=illusory_terrain, illusory_terrain_enhanced=illusory_terrain_enhanced,
        )
    defender_pursuit_destroyed: set[int] = set()
    if defender_clean_swept and loser_retreats:
        defender_pursuit_destroyed = _apply_pursuit(
            defender_armies, attacker_units, state, terrain, report, rng, is_island=is_island,
            illusory_terrain=illusory_terrain, illusory_terrain_enhanced=illusory_terrain_enhanced,
        )

    for army in attacker_armies:
        if army.army_id in attacker_pursuit_destroyed:
            continue
        led_by_insufficient_druid = led_by_insufficient_druid_by_army_id.get(army.army_id, False)
        formation_divisor = formation_divisor_by_army_id.get(army.army_id, FORMATION_DIVISOR["front"])
        score = score_by_army_id.get(army.army_id, 0)
        if battle_result.winner == "attacker":
            old_quality = army.quality
            army.quality = roll_quality_change(
                army.quality, rng, is_winner=True, led_by_insufficient_druid=led_by_insufficient_druid,
                formation_divisor=formation_divisor, score=score,
            )
            report.quality_changes[army.army_id] = QualityChange(old=old_quality, new=army.quality)
        elif attacker_clean_swept and _whale_forced_retreat_applies(army, terrain):
            bounds = MapBounds(state.board_width, state.board_height)
            destination = _whale_sea_retreat_destination(army, state, bounds)
            _retreat_or_disband(
                army, state, report, rng, destination=destination,
                led_by_insufficient_druid=led_by_insufficient_druid, formation_divisor=formation_divisor,
            )
        elif attacker_clean_swept and loser_retreats:
            bounds = MapBounds(state.board_width, state.board_height)
            if attacker_origin is not None:
                destination = attacker_retreat_candidates(attacker_origin, bounds)[0]
            else:
                friendly = state.friendly_provinces_for(attacker_kingdom_id) - {province_coord}
                destination = find_retreat_destination(army.location, bounds, friendly)
            _retreat_or_disband(
                army, state, report, rng, destination=destination,
                avoid_elimination=_fleet_avoids_elimination(army, terrain),
                led_by_insufficient_druid=led_by_insufficient_druid, formation_divisor=formation_divisor,
            )
        elif attacker_clean_swept and _fleet_avoids_elimination(army, terrain):
            old_quality = army.quality
            army.quality = Quality.DEPLETED
            report.quality_changes[army.army_id] = QualityChange(old=old_quality, new=army.quality)
        elif attacker_clean_swept:
            report.destroyed_army_ids.append(army.army_id)
            state.record_battle_death(province_coord, army.army_type, army.quality, army.kingdom_id)
            state.remove_army(army.army_id)
        elif rng.random() < direct_destruction_probability_by_army_id.get(army.army_id, 0.0):
            report.destroyed_army_ids.append(army.army_id)
            state.record_battle_death(province_coord, army.army_type, army.quality, army.kingdom_id)
            state.remove_army(army.army_id)
        else:
            old_quality = army.quality
            army.quality = roll_quality_change(
                army.quality, rng, is_winner=False, retreated=False,
                led_by_insufficient_druid=led_by_insufficient_druid, formation_divisor=formation_divisor,
                score=score,
            )
            report.quality_changes[army.army_id] = QualityChange(old=old_quality, new=army.quality)

    for army in defender_armies:
        if army.army_id in defender_pursuit_destroyed:
            continue
        led_by_insufficient_druid = led_by_insufficient_druid_by_army_id.get(army.army_id, False)
        formation_divisor = formation_divisor_by_army_id.get(army.army_id, FORMATION_DIVISOR["front"])
        score = score_by_army_id.get(army.army_id, 0)
        if battle_result.winner == "defender":
            old_quality = army.quality
            army.quality = roll_quality_change(
                army.quality, rng, is_winner=True, led_by_insufficient_druid=led_by_insufficient_druid,
                formation_divisor=formation_divisor, score=score,
            )
            report.quality_changes[army.army_id] = QualityChange(old=old_quality, new=army.quality)
        elif defender_clean_swept and _whale_forced_retreat_applies(army, terrain):
            bounds = MapBounds(state.board_width, state.board_height)
            destination = _whale_sea_retreat_destination(army, state, bounds)
            _retreat_or_disband(
                army, state, report, rng, destination=destination,
                led_by_insufficient_druid=led_by_insufficient_druid, formation_divisor=formation_divisor,
            )
        elif defender_clean_swept and loser_retreats:
            bounds = MapBounds(state.board_width, state.board_height)
            friendly = state.friendly_provinces_for(army.kingdom_id) - {province_coord}
            destination = find_retreat_destination(army.location, bounds, friendly)
            _retreat_or_disband(
                army, state, report, rng, destination=destination,
                avoid_elimination=_fleet_avoids_elimination(army, terrain),
                led_by_insufficient_druid=led_by_insufficient_druid, formation_divisor=formation_divisor,
            )
        elif defender_clean_swept and _fleet_avoids_elimination(army, terrain):
            old_quality = army.quality
            army.quality = Quality.DEPLETED
            report.quality_changes[army.army_id] = QualityChange(old=old_quality, new=army.quality)
        elif defender_clean_swept:
            report.destroyed_army_ids.append(army.army_id)
            state.record_battle_death(province_coord, army.army_type, army.quality, army.kingdom_id)
            state.remove_army(army.army_id)
        elif rng.random() < direct_destruction_probability_by_army_id.get(army.army_id, 0.0):
            report.destroyed_army_ids.append(army.army_id)
            state.record_battle_death(province_coord, army.army_type, army.quality, army.kingdom_id)
            state.remove_army(army.army_id)
        else:
            old_quality = army.quality
            army.quality = roll_quality_change(
                army.quality, rng, is_winner=False, retreated=False,
                led_by_insufficient_druid=led_by_insufficient_druid, formation_divisor=formation_divisor,
                score=score,
            )
            report.quality_changes[army.army_id] = QualityChange(old=old_quality, new=army.quality)

    if defender_clean_swept:
        province.owner_kingdom_id = attacker_kingdom_id
        province.contested_by_kingdom_id = None
        province.contested_from_coord = None
    elif attacker_clean_swept:
        # Invasion cleanly repelled -- defender keeps the province outright,
        # no ongoing contest.
        province.contested_by_kingdom_id = None
        province.contested_from_coord = None
    else:
        # Mixed result (including a tie): attacker failed to take the
        # province outright, but wasn't destroyed either -- contested [7.6].
        province.contested_by_kingdom_id = attacker_kingdom_id
        # Phase 409: persist attacker_origin (when known) so a later
        # forced-rebattle can still honor the real attacker-retreat rule --
        # see ProvinceState.contested_from_coord's own docstring.
        province.contested_from_coord = attacker_origin

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
    #
    # Phase 647: a party whose entire army composition is Eagle Wing/
    # Dragon Wing gets 0 too -- "not affected by March ability" at all,
    # not just excluded from the movement-bonus half (Phase 523) --
    # `is_march_immune_party()`'s own docstring for the full sourcing.
    #
    # Phase 754: `Desktop/MOVE.md` sections 5.3/6.4 (see `multiple_
    # contingents.py`'s own Phase 754 addendum for the full account)
    # supply the missing Naval half at ALTA confidence -- when the
    # invasion crosses water (either endpoint's own `effective_terrain()`
    # is Sea), the party's own Naval skill level drives the same MARCH
    # TABLE lookup instead of March. Mirrors this exact file's own
    # `_combat_ability_for_terrain()` -- terrain decides which ability
    # applies, same shape, different ability pair ([6.3] Tactical/Naval
    # there, [4.12]/[4.13] March/Naval here).
    def _party_effective_unite_level(party: MultiAttackerParty) -> int:
        army_types = [state.armies[aid].army_type for aid in party.army_ids if aid in state.armies]
        if is_march_immune_party(army_types):
            return 0
        if party.leader_id not in state.leaders:
            return 0
        origin = state.provinces.get(party.origin_province)
        target = state.provinces.get(province_coord)
        is_sea_move = (origin is not None and origin.effective_terrain() is Terrain.SEA) or (
            target is not None and target.effective_terrain() is Terrain.SEA
        )
        ability = Ability.NAVAL if is_sea_move else Ability.MARCH
        return effective_skill_level(state, state.leaders[party.leader_id], ability)

    attackers = [
        Attacker(
            leader_id=p.leader_id,
            kingdom_id=p.kingdom_id,
            origin_province=p.origin_province,
            march_level=_party_effective_unite_level(p),
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
            # Phase 736: snapshot army types before fight_battle() removes
            # any of them -- see move_execution.py's own identical note.
            army_types_before_battle = {army.army_id: army.army_type for army in state.armies.values()}
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
            # Phase 716: the cargo sinks with the carrier.
            apply_battle_carrier_destruction(
                state,
                report.destroyed_army_ids,
                report.disbanded_army_ids,
                report.pursuit_destroyed_army_ids,
                coord=province_coord,
                army_types_before_battle=army_types_before_battle,
            )
        else:
            # An earlier group already cleared/claimed the province this
            # same call -- see module docstring's "Phase 73" note.
            report = BattleReport(battle_result=BattleResult(winner="attacker"), conquered=True)
        reports.append(MultiAttackerBattle(leader_ids=[member.leader_id for member in group], report=report))

    return reports
