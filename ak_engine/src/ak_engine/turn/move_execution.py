"""Executing a Move order end-to-end (rulebook [3.1], [6.2], [7.7]).

Wires together, in order:

1. **Contested-province check** (Phase 36, rulebook [7.6]): "The leader
   who invaded the contested province will execute his orders in the
   next phase, except that it's illegal to move from a contested
   province to an adjacent enemy province." Raises ``ValueError`` via
   ``turn/contested_province.py is_illegal_move_from_contested()`` when
   the mover's *origin* province is currently contested *by the mover's
   own kingdom* (``ProvinceState.contested_by_kingdom_id == kingdom_id``
   -- not merely contested by anyone, since the rule is specifically
   about "the leader who invaded," i.e. the attacker still stuck there,
   not some third kingdom's army passing through) and the *target*
   province is enemy-owned. ``contested_by_kingdom_id`` has been
   correctly set/cleared by ``turn/battle_orchestrator.py fight_battle()``
   since Phase 9 -- this only adds the read side that was missing. "You
   can, however, move from a province owned by a neutral player-King to
   an enemy province" needs no separate handling: that's just the
   `origin_contested_by_mover=False` case, already legal.
2. ``turn/movement.py resolve_move()`` -- adjacency check + the partial-
   exploration side effect.
3. **Battle trigger**: if the target province holds any army not allied
   with the mover, calls ``turn/battle_orchestrator.py fight_battle()``.
4. ``turn/conquest.py movement_cost_for_move()`` -- movement-point
   deduction, including the single extra point owed for conquering the
   province or for a battle having taken place there (never both at
   once -- Phase 915). **Phase 651 addendum**: a separate, per-army-type
   deduction
   right alongside it for Illusory Fog's own "must expend 1 additional
   movement point when entering or leaving" the affected province
   (``turn/cast_execution.py ILLUSORY_FOG_EXTRA_MOVEMENT_COST``/``is_
   illusory_fog_affected_air_unit()``) -- see the call site's own
   comment for why this stays separate from ``movement_cost_for_move()``
   itself (it targets specific army types, not the whole moving party).
   The spell's own end-of-gameturn dissipation
   (``ILLUSORY_FOG_DISSIPATES_AT_END_OF_GAMETURN``) is already modeled
   too, since Phase 576 -- ``turn_processor.py _replenish_turn_scoped_
   state()`` unconditionally clears ``province.illusory_fog_active``
   every real turn (Phase 576 predates this Phase 651 addendum, whose
   own wording was never updated to reflect it; corrected Phase 794).
5. ``GameState`` mutation: army relocation (only if the move actually
   succeeds -- an unconquered, contested, or repelled battle leaves the
   mover's surviving armies where ``fight_battle()`` put them, not at the
   target) and the province's exploration-percent update.

**Phase 410 addendum -- uncontested conquest was never wired in until
now.** Steps 3-4 above describe the battle-driven path only
(``fight_battle()``'s own ``defender_clean_swept`` branch was, until
this phase, the *only* place in this project that ever set
``ProvinceState.owner_kingdom_id``). Rulebook [7.7] (quoted in the
module docstring's own citation) frames "conquering an enemy province"
as a property of *entering* it, not of winning a fight there -- and
``report/turn_report.py``'s own ``render_uncontested_conquest()``
(``HostAK/TP/PROSE/CONQ.X``, Phase 63, "a Move that conquers an
undefended enemy province -- no ``_BClash``/``_BWinner`` battle dispatch
involved at all") had been fully built and tested since Phase 63 with
nothing to actually feed it: no code path ever produced a real
uncontested conquest to render. Now, when the target holds no defenders
at all (the ``else`` branch below, not ``occupied_by_enemy``) and the
mover brought at least one army, entering an unowned or enemy-owned
province transfers ownership immediately, matching the same "own it the
instant you're standing in it unopposed" rule a battle-won conquest
already implements. ``turn/conquest.py movement_cost_for_move()``'s own
``conquered`` extra-cost point -- previously unreachable outside a
battle, despite its own module docstring's "conquering an enemy
province slows an army down" text never mentioning a fight as a
precondition -- now applies correctly here too, since it reads this
same ``conquered`` fact regardless of path.

Still out of scope: ``turn/contested_province.py``'s other two functions
-- ``attacker_can_force_rebattle``/``contested_battle_movement_cost`` --
since automatically forcing a rebattle "in the next phase" without a new
player order needs a caller that tracks state across phases for a given
province. ``turn/turn_processor.py run_turn()`` (Phase 45) *is* now a
genuinely phase-by-phase, multi-leader orchestrator -- the structural
gap this note used to point at -- but it doesn't wire this specific
mechanic in yet either; see that module's own docstring for what it
does wire in (Multiple Contingents) and what's still deferred.

**Chasing a non-adjacent target (Phase 85, rulebook [3.1])**: when
``target`` isn't adjacent to the mover's own ``current`` location,
``execute_move()`` no longer raises -- it computes one hex-step toward
``target`` via ``turn/movement.py step_toward_non_adjacent_target()``
(the pure pathfinding primitive Phase 78 built but didn't wire in),
classifying each candidate neighbor's ownership tier from real
``GameState`` data via ``_classify_hex_ownership()`` (Owned/Allied,
via ``state.is_allied()``; Enemy, an owned non-ally; otherwise
Neutral -- ``HexOwnershipTier.HERO_OWNED`` is never produced, the same
documented limitation Phase 78 already flagged: ``ProvinceState``
can't distinguish a Hero-ruled province from a genuinely wild one).

The chosen intermediate hex is, by construction, always adjacent to
``current`` (it's one of `current`'s own neighbors) -- so
``resolve_move()`` itself needed **no changes at all**: it's simply
called with the intermediate hex as its own target, exactly as if that
had been the player's own literal order this phase. This is what makes
exploration correct for a chase step: it's resolved against the
*intermediate* hex's own real province data, never the ultimate
target's (a wrong-terrain bug this design deliberately avoids, per
Phase 78's own note on why this couldn't be a `resolve_move()`-only
fix). If no neighbor is strictly closer than `current` already is --
rulebook: "The character will stop chasing the province if he can't
find a legal way to move closer to it in one phase" --
``MoveExecutionResult.stopped_chasing`` is `True`, `exploration` is
`None`, and nothing else happens (no cost, no relocation).

``MoveExecutionResult.reached_target`` is a purely geometric fact
(``actual_target == target``, i.e. "was this phase's own hop the final
one"), independent of whether the hop itself actually succeeds this
phase (a lost/contested battle at the intermediate hex still leaves
`reached_target=False` if the ultimate target was still further away,
or conversely `True` even for a repelled hop onto an already-adjacent
target -- callers that care whether the mover is *actually* there now
should check `moved` and `new_location` together with
`reached_target`, not `reached_target` alone). A chase step's
enemy-occupied intermediate hex triggers a battle exactly like any
ordinary Move -- the rulebook's chase-toward-target text doesn't
address this case explicitly, so this project treats a chase step as
mechanically identical to a directly-ordered Move to that same hex, a
documented consistency choice rather than a sourced special case.

**Cross-phase persistence -- closed, Phase 632.** The rulebook's own
multi-phase persistence rule -- "The movement order will override
orders in a subsequent phase only if the character is practicing in
that phase" -- has two grammatically plausible readings this project
couldn't disambiguate from the available source alone (narrow: only a
later Practice order is overridden, any other order type runs as
written and the chase doesn't auto-continue without a fresh Move
order; broad: blanket preemption of every subsequent order, mirroring
Pursue/Trail's own "for the rest of the turn" persistence, Phase 70,
exactly). **The user directly confirmed the broad reading.**
``turn/turn_processor.py run_turn()`` now wires it in, reusing the
exact same "PERSISTENT PURSUE/TRAIL CHASE" mechanism (see that
module's own "PERSISTENT MOVE CHASE" docstring section) -- genuinely
simpler than Pursue/Trail's own mirror, since Move's own chase-
stepping already lives entirely inside ``execute_move()`` itself: a
continuation is just redispatching the same ordinary LMOVE phase again
with the same ultimate target, no dedicated ``advance_*`` function
needed.

**Leader-only movement** (Phase 14): pass ``leader_id`` and an empty
``army_ids`` for a character moving without any army. Per rulebook [3.1]
("If the character has an army with him and the province is occupied by
a enemy army, combat occurs"), combat only triggers when the mover has
at least one army -- a lone character can walk into an enemy-held
province without a fight. Lone characters aren't subject to the
movement-point check either: that's an army property (rulebook [6.2],
"An army's speed determines how far it can move"), and this project
doesn't track a separate per-character movement budget.

**Mystic Winds wind-walking notice trigger -- closed, Phase 634.**
``report/turn_report.py record_move_world_events()`` had left `SAY.PAS`
``_LWWalk`` (the sibling of the already-wired ``_LFly`` "flew" notice)
unwired: its own real trigger, ``LeaderState.mystic_winds_active``, is
a single per-leader flag with no record of *which* move it was set
during, and the effect lasts until the leader's own next real battle
(``turn/battle_orchestrator.py fight_battle()``'s own Phase 250
clearing), not just one move -- so reading the flag's *current* value
post-turn can miss an earlier move that happened before an intervening
same-turn battle cleared it. ``MoveExecutionResult.wind_walking`` now
snapshots the flag at the *start* of each ``execute_move()`` call,
before that same call's own ``fight_battle()`` (if any) can clear it --
correct even when the move that triggers the notice is the very one
that ends the spell. Deliberately not extended to `turn/turn_
processor.py`'s own multi-attacker LMOVE path (a separate `resolve_
move()`/`fight_multi_attacker_battle()` route that never calls
``execute_move()`` at all).

**Wandering Mercenaries (Phase 746, corrected by Phase 754).**
``Desktop/MS/ADDEND.AK`` [3.6] (this addendum's own independent section
numbering -- unrelated to the main rulebook's own [3.6], Disband,
already cited elsewhere in this project): "If there are mercenary
armies in a hex when a general passes through it, they may follow that
general instead of staying behind. This counteracts the sneaky trick of
disbanding armies when faced with attack, then rehiring them when the
opposing general has passed through the hex." Confirmed genuinely
unwired before Phase 746: ``GameState.mercenaries_at()`` (already real,
Phase 642) had exactly one consumer anywhere in this project, the
ordinary Recruit dispatch -- nothing tied it to Move.

Phase 746 had only the rulebook's own prose to work from and had to
invent a magnitude (a 50% per-army coin flip) and a coordinate (the
general's own *destination*, absorbing the mercenary into his own
Kingdom on arrival). **`Desktop/MOVE.md` (2026-09-05) disassembles the
real routine directly** (`AK.EXE`'s own `Apply_Move`, raw
`0x3AF78-0x3B05D`) and corrects all three:

1. **Coordinate**: the routine "re-examines the armies remaining *at
   the origin*", not the destination -- matching the rule's own real
   intent (a general *departing* a hex sweeps along whatever mercenary
   was left there, rather than a general *arriving* somewhere absorbing
   whoever's already present).
2. **Deterministic, not probabilistic**: no coin flip anywhere in the
   disassembly. A real temporal gate (`Wandering_Mercenaries_Enabled =
   (game_year>=1993) OR (game_month>=7)`, true for most of any given
   year regardless of which one) is modeled as always-true here -- this
   project has no calendar concept anywhere to gate it on otherwise, and
   the real gate's own `OR` logic makes that a reasonable simplification,
   not a guess at the probability the rule never actually has. What
   *does* gate a specific mercenary army: its own movement points must
   be positive, and it must pass the same Fleet/Mermen/Whale coastal-
   transport legality any ordinary army making that same hop would need
   (`find_transport_illegality()`, Phase 737, reused directly -- no
   Druidic-ability flags, since a masterless mercenary has none). A
   second, real precondition applies to the *general's own* main
   contingent, not just his presence: at least one of his own armies
   must still have positive movement points after this move
   ("non basta la sola presenza del generale" -- the general's mere
   presence is not enough) -- an armyless leader moving alone therefore
   no longer triggers this at all, correcting Phase 746's own opposite
   assumption.
3. **No ownership change**: "la scelta non cambia lo stato sociale...
   l'armata continua a essere mercenaria." The mercenary is relocated
   (to the general's own new location) and pays movement -- the same
   base per-hex cost, `1`, not the caller's own possibly-surcharged
   `cost` (the real routine reuses the generic overland-movement helper
   with the wrapper's own base-cost argument, confirmed as `1` for an
   ordinary `MOVE`) -- through the exact same primitives an ordinary
   army uses, but `kingdom_id`/`commanded_by` are never touched. It
   remains genuinely ownerless; it has simply moved.

**Scope, unchanged from Phase 746's own confirmed decision**: applies
only to the ordinary ``ActionCode.LMOVE`` dispatch (``execute_move()``
below). Deliberately NOT extended to Pursue/Trail (which also relocate
a leader) or to ``turn/turn_processor.py``'s own separate multi-
attacker-LMOVE path (which never calls ``execute_move()`` at all) --
both real, separate, smaller follow-ups, not attempted here.

No report-layer narration is added -- no `SAY.PAS`/`.X2` text was found
anywhere describing this specific event (distinct from the still-
genuinely-blocked `AWANDFR`/`AWANDTO`/`LWANDFR`/`LWANDTO` cluster, which
narrates a mercenary's own *unprompted* self-relocation, a different
mechanic); mechanism only, matching this project's own repeated
"mechanic now, narration only when a real source exists" precedent.

**Foreign Illusory Fog entry note (Phase 754).** `MOVE.md` section 21.3
disassembles `AK.EXE` raw `0xB31A-0xB54A`, run only when the leader's
own Kingdom genuinely differs from the destination's real owner, and
names three bit-field-gated consequences. Two are deliberately NOT
built here: the `0700h` terrain-reveal note (`_LSeeI=3043`) has a real,
confirmed trigger but **no surviving English text anywhere** -- not in
`MOVE.md`, not previously transcribed by this project -- so building it
would mean inventing wording this project's own "no source, no guess"
convention forbids; the `0800h` race/army-type reveal (`_PFiteAs=7026`,
real text quoted in `MOVE.md`) belongs to `AdvancedAbility.ENHANCED_
ILLUSORY_TERRAIN`'s own still-unbuilt 67/33 blend (`turn/strength.py`'s
own Phase 724 addendum already defers this ability in full -- adding
just its narration ahead of the mechanic it describes would be
backwards). The third, `1000h`'s own Illusory Fog note, **is built**:
real text is quoted directly in `MOVE.md` ("@ was magically/
mysteriously shrouded in/clouded by a vast/disorienting phantasmal/
illusory fog/mist which slowed down/delayed and confused/disoriented
all/any air/flying units/armies"), and the underlying mechanic (Phase
651's own Illusory Fog movement surcharge) is already live. The
document's own "contains wings OR the owner differs" trigger reduces to
an unconditional fire inside this already-foreign-owner-gated branch
(the second disjunct is always true there) -- modeled as firing on
every such entry, not scoped to which army types the mover brought.
"Foreign" is evaluated against the destination's own owner *before*
this same call's own uncontested-conquest effect can transfer it --
walking into an empty enemy province you're about to conquer still
counts as entering foreign territory, matching a real-time observation
made upon arrival, not a retroactive one made after the province has
already changed hands.
`MoveExecutionResult.entered_foreign_illusory_fog` carries the flag;
`report/turn_report.py record_illusory_fog_foreign_entry_world_events()`
is the real, wired consumer.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Literal

from ak_engine.models.advanced_ability import AdvancedAbility
from ak_engine.models.army_type import ARMY_TABLE, OVERFLIGHT_AIR, SEA_ARMY_TYPES, ArmyType, is_land_army
from ak_engine.models.enums import Ability
from ak_engine.models.feature import Feature
from ak_engine.models.game_state import (
    KNOWN_PROVINCE_MIN_PERCENT,
    ArmyState,
    GameState,
    LeaderState,
    ProvinceState,
    record_newly_known_column,
)
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.office import Office
from ak_engine.models.treasure import Treasure
from ak_engine.parser.gw_world import DiplomaticRelation
from ak_engine.turn.battle_orchestrator import BattleReport, fight_battle, mystic_winds_active_for
from ak_engine.turn.cast_execution import ILLUSORY_FOG_EXTRA_MOVEMENT_COST, is_illusory_fog_affected_air_unit
from ak_engine.turn.conquest import movement_cost_for_move
from ak_engine.turn.contested_province import IllegalMoveFromContestedError, is_illegal_move_from_contested
from ak_engine.turn.diplomacy import is_attackable_at
from ak_engine.turn.experience import add_experience
from ak_engine.turn.exploration import ExploreResult, discover_features, resolve_explore, resolve_find_mines
from ak_engine.turn.office_holder import resolve_office_holder
from ak_engine.turn.sea_transport import apply_battle_carrier_destruction, board_army, cargo_aboard, disembark_army
from ak_engine.turn.movement import (
    HexOwnershipTier,
    MapBounds,
    is_adjacent,
    neighbors,
    resolve_move,
    step_toward_non_adjacent_target,
)
from ak_engine.worldgen.march_ability_level_schedule import build_march_ability_level_schedule
from ak_engine.worldgen.naval_ability_level_schedule import build_naval_ability_level_schedule


# Phase 521: AdvancedAbility.MARCH_CAVALRY/_INFANTRY (+ Mastery tiers) --
# see module docstring's own Phase 521 addendum for the full sourced
# quotes and the split between what's modeled here and what isn't.
#
# Phase 768: `Desktop/PROGRAMMA AK/MARCH.md` (a disassembly-level
# reverse-engineering pass) confirms AKGEN's own real `spabord` template
# for March (raw `0x604FA-0x604FF = 08 07 06 07 06 07`, levels 5-10)
# grants the Cavalry-effect ID (7) THREE times (levels 6, 8, 10) but the
# Infantry-effect ID (6) only twice (levels 7, 9) -- confirmed by direct
# disassembly of `SA_Num`, a real per-occurrence *counter*, not a
# boolean `Has_SA` wrapper. Our existing 2-tier Infantry model (+1/+2)
# already matches its own real 2-copy count exactly; Cavalry needed a
# 3rd, self-contained tier (+3 total) to match its own real 3-copy
# count. No literal 3rd-tier catalog text survives for this in `Desktop/
# PROGRAMMA AK/ABILITÀ SOPRA IL LIVELLO 4 OK.txt` (the canonical
# rulebook catalog this whole module's text is built from) -- but that
# same file's own Archery entry shows the identical "one real ID
# granted 3 times, 3 progressively-named catalog entries" shape ("ARCHERY
# FREE ATTACK" / "... MASTERY" / "... TRUE MASTERY"), a real, same-
# document precedent for this exact mechanic. User-confirmed directly
# (AskUserQuestion) to add the 3rd tier with clearly-labeled project-
# original text, mirroring Melee Mastery/True Mastery's own established
# "self-contained total effect per tier" convention (Phase 517).
MARCH_CAVALRY_MIN_MOVEMENT_POINTS = 3
MARCH_INFANTRY_MOVEMENT_POINTS_RANGE = (1, 2)
MARCH_ABILITY_BONUS = 1
MARCH_MASTERY_ABILITY_BONUS = 2
MARCH_TRUE_MASTERY_ABILITY_BONUS = 3


def march_movement_point_bonus(
    current_movement_points: int,
    *,
    has_march_cavalry: bool = False,
    has_march_cavalry_mastery: bool = False,
    has_march_cavalry_true_mastery: bool = False,
    has_march_infantry: bool = False,
    has_march_infantry_mastery: bool = False,
) -> int:
    """The flat movement-point bonus a land army qualifies for right now.

    ``current_movement_points`` is the army's own pool *before* this
    bonus -- Cavalry/Cavalry Mastery/Cavalry True Mastery only ever
    apply at 3+, Infantry/Infantry Mastery only at 1-2 (rulebook's own
    two disjoint bands). A leader only ever holds one Advanced Ability
    per category (Phase 128), so each tier's own kwarg is read as the
    ability's total, self-contained effect (+1/+2/+3), not additive on
    top of a lower tier you don't hold -- the same convention Melee
    Mastery/True Mastery (Phase 517) already established. Cavalry alone
    gets a 3rd tier (Phase 768) -- Infantry's real template only ever
    grants its own effect ID twice, already fully covered by the
    existing two tiers.
    """

    if has_march_cavalry_true_mastery and current_movement_points >= MARCH_CAVALRY_MIN_MOVEMENT_POINTS:
        return MARCH_TRUE_MASTERY_ABILITY_BONUS
    if has_march_cavalry_mastery and current_movement_points >= MARCH_CAVALRY_MIN_MOVEMENT_POINTS:
        return MARCH_MASTERY_ABILITY_BONUS
    if has_march_cavalry and current_movement_points >= MARCH_CAVALRY_MIN_MOVEMENT_POINTS:
        return MARCH_ABILITY_BONUS
    low, high = MARCH_INFANTRY_MOVEMENT_POINTS_RANGE
    if has_march_infantry_mastery and low <= current_movement_points <= high:
        return MARCH_MASTERY_ABILITY_BONUS
    if has_march_infantry and low <= current_movement_points <= high:
        return MARCH_ABILITY_BONUS
    return 0


# Phase 693: AdvancedAbility.MARCH_THROUGH_FLOODS's own real text --
# "One movement point is deducted from all units which have to use
# this ability, after they have moved." See module docstring's own
# Phase 693 addendum for the full reasoning.
MARCH_THROUGH_FLOODS_EXTRA_MOVEMENT_COST = 1


def is_flooded_province(province: ProvinceState) -> bool:
    """True when ``province``'s own current terrain was overridden to Sea by
    Flood (``turn/cast_execution.py _execute_flood()``), not because it's
    naturally Sea terrain. Unambiguous: Part Sea sets the opposite
    direction (``terrain_override = Terrain.PLAINS``), and ``_execute_
    flood()`` only ever succeeds starting from a non-Sea terrain
    (``_FLOOD_ELIGIBLE_TERRAIN``), so a real Sea-terrain province is
    never itself the target of a Flood cast.
    """

    return province.terrain_override is Terrain.SEA


def naval_movement_point_bonus(naval_skill_level: int) -> int:
    """AKGEN_reverse_engineering_report (3).md SS99 (`AKE.EXE:0x21F6A-
    0x22080 MovementBonus`): for Whale League/Fleet/Mermen (`models/
    army_type.py SEA_ARMY_TYPES`), the Naval movement bonus is simply the
    leader's own effective Naval skill level, added straight to whatever
    movement points the army already has -- "Non compare min(4,NA) nel
    ramo navale" (no cap here, unlike the battle-strength bonus's own
    ``min(4, NA)`` cap in ``turn/battle_orchestrator.py``). Unlike March's
    own ``march_movement_point_bonus()``, there's no movement-point band
    to qualify for and no separate Mastery tier -- the raw skill level
    *is* the bonus. Clamped at 0 defensively (``effective_skill_level()``
    should never return negative, but this keeps a stray direct caller
    from ever subtracting movement points here).
    """

    return max(0, naval_skill_level)


# Phase 764: [4.12] MARCH TABLE's own "Extra moves for..." columns (Ability
# Level 0-4) -- see turn/multiple_contingents.py's own module docstring for
# the full table, word-for-word identical in both available sources
# (`RULES.AK [4.12]`/Regolamento AK.txt's "TABELLA DELLA MARCIA"). Closes
# the half that same docstring flagged, since Phase 307, as "a distinct,
# still-unmodeled gap this phase doesn't attempt to close." Independently
# corroborated: `AKGEN_reverse_engineering_report (3).md` SS99's own
# disassembled `MovementBonus()` names a real `MarchBonus(army_id, leader)`
# call for exactly this land-army branch (the Naval sibling right above,
# `naval_movement_point_bonus()`, is the *other* branch of that same
# routine) -- its own body was never expanded in that document, but its
# existence confirms this is a real, single, per-army movement formula the
# compiled engine already computes, not an invented mechanic.
MARCH_TABLE_EXTRA_MOVES_SLOW: tuple[int, ...] = (0, 0, 1, 1, 2)  # Speed 1-2
MARCH_TABLE_EXTRA_MOVES_FAST: tuple[int, ...] = (0, 1, 1, 2, 2)  # Speed 3+
MARCH_TABLE_MAX_LEVEL = len(MARCH_TABLE_EXTRA_MOVES_SLOW) - 1
MARCH_TABLE_FAST_SPEED_THRESHOLD = 3


def march_table_extra_movement(march_skill_level: int, army_speed: int) -> int:
    """The MARCH TABLE's own base, raw-skill-level movement bonus.

    Genuinely distinct from, and stacks with, ``march_movement_point_
    bonus()``'s own separate Advanced-Ability-gated bonus (`MARCH_
    CAVALRY`/`_INFANTRY` + Mastery tiers, `models/advanced_ability.py`):
    this one is the base table every character gets from their own raw
    ``Ability.MARCH`` skill level (0 included -- no Advanced Ability
    needed at all), the other is a flat, separately-sourced bonus only
    for a leader who's been granted one specific Advanced Ability.
    ``march_skill_level`` is clamped to the table's own last known row
    (4) for anything higher -- the same "clamp to the last known value"
    convention ``turn/multiple_contingents.py``'s own sibling docstring
    already established for a real distance past that table's own known
    range. ``army_speed`` picks the column (``models/army_type.py
    ARMY_TABLE[army_type].speed`` -- 1-2 vs. 3+); a caller with no real
    speed on hand for a given ``ArmyType`` (the handful of members with
    no ``ARMY_TABLE`` entry at all) should pass a value ``<= 2`` --
    the smaller-or-equal "Speed 1-2" column, matching this project's own
    established "missing data never over-grants" fallback convention
    (``_boarding_priority_tier()``'s own precedent).
    """

    level = max(0, min(MARCH_TABLE_MAX_LEVEL, march_skill_level))
    table = MARCH_TABLE_EXTRA_MOVES_FAST if army_speed >= MARCH_TABLE_FAST_SPEED_THRESHOLD else MARCH_TABLE_EXTRA_MOVES_SLOW
    return table[level]


def _naval_hug_coastline_move_is_legal(
    state: GameState, origin: HexCoord, target: HexCoord, bounds: MapBounds
) -> bool:
    """AKGEN_reverse_engineering_report (3).md SS106 (`AdvancedAbility.
    NAVAL_HUG_COASTLINE`, `SA.X2:47-49`, `AKE.EXE:0x22153-0x222D0`):

    ```pascal
    if Has_SA(leader,Hug_Coast) and
       origin_is_land and destination_is_land and
       exists sea_hex adjacent_to(origin) and adjacent_to(destination)
    then
       allow_direct_coastal_move;
    ```

    True when ``origin`` and ``target`` are both land provinces (not
    ``Terrain.SEA``, and real province data exists for both -- an
    unexplored/unknown hex, ``Terrain.NO_TERRAIN``, never qualifies)
    that share at least one common neighbor whose own terrain is
    ``Terrain.SEA``. "The two land hexes must share a coastal adjacency
    through a sea hex" -- not a teleport and not an arbitrary route, so
    this is a direct neighbor-set intersection, not a pathfinding search.

    The dossier's own second paragraph, quoted in full: "Se accompagnano
    il leader sia Fleet sia unità terrestri, il motore assegna il
    trasporto al maggior numero possibile di unità" -- deterministic
    priority (speed 1-2 units first, tiebroken by lowest army
    designation) -- "Le unità trasportate restano soggette al divieto di
    usare anche movimento terrestre proprio nello stesso turno; quelle
    non imbarcate percorrono il normale passo terrestre, se legale e con
    punti sufficienti." The real engine genuinely splits a mixed group's
    fate: the carrier(s) plus whatever they manage to board make the
    coastal hop; land stragglers left without a slot travel separately,
    by the ordinary route.

    **Phase 720 -- the priority-allocation rule itself is now reused
    directly** (it's the identical rule already built and tested as
    ``turn/move_execution.py _auto_board_transport_group()``/
    ``_boarding_priority_tier()``, Phase 715): this function's own caller
    (``execute_move()``'s ``is_hug_coastline_hop``) grants the coastal
    shortcut to the boarded/carrier portion of a mixed group whenever
    *that* portion is legal for it (``ArmyState.transported_by is not
    None``, read straight off whatever boarding the same call's own
    earlier ``auto_board`` pass already performed -- no separate/
    duplicate boarding logic here).

    **Phase 763 -- the real "un-boarded stragglers still travel
    separately, by the ordinary route, while the rest hops" split is now
    modeled too.** Closing the gap this docstring used to flag needed
    exactly the architectural change anticipated at Phase 720: a second,
    genuinely independent ``MoveExecutionResult`` -- see
    ``MoveExecutionResult.straggler_result``'s own docstring. The caller
    (``execute_move()``) carves any unboarded land army out of the
    moving group *before* deciding ``is_hug_coastline_hop`` at all, so by
    the time that flag is computed the group it's evaluated against
    already has no stragglers left in it -- the all-or-nothing framing
    from Phase 720 above now describes the *narrowed* hop-only group,
    not the original order as submitted. The stragglers get their own,
    separate ``execute_move()`` call (``has_naval_hug_coastline=False``,
    the ordinary one-hex chase step toward the same ultimate target,
    exactly what any non-adjacent mover already gets without this
    ability) -- no leader travels with them, a documented modeling
    choice (the acting leader is assumed to travel with the hop group),
    not a fact this project's own sources confirm either way.

    **Phase 766 -- wired.** `turn/plan_dispatch.py run_leader_plan()`/
    `turn/turn_processor.py _continue_active_move_chases()` both now
    append `straggler_result` as its own sentinel `PhaseDispatchResult`
    (`segment_index=-1`, `action=None`), so every existing report-layer
    consumer that scans `results` for real consequences (`_battle_
    reports_from_results()`'s own `.battle_report` duck-typing) picks up
    the stragglers' own battle/exploration/conquest for free. `report/
    turn_report.py describe_naval_hug_coastline_stragglers()` adds the
    one genuinely new piece -- a project-original arrival sentence,
    explicitly user-authorized (no Pascal source describes this
    scenario at all, since the split itself was built this session, not
    recovered from disassembly).
    """

    origin_province = state.provinces.get(origin)
    target_province = state.provinces.get(target)
    if origin_province is None or target_province is None:
        return False
    if origin_province.effective_terrain() in (Terrain.SEA, Terrain.NO_TERRAIN):
        return False
    if target_province.effective_terrain() in (Terrain.SEA, Terrain.NO_TERRAIN):
        return False
    shared_neighbors = set(neighbors(origin, bounds)) & set(neighbors(target, bounds))
    return any(
        (province := state.provinces.get(coord)) is not None and province.effective_terrain() is Terrain.SEA
        for coord in shared_neighbors
    )


@dataclass(slots=True)
class MoveExecutionResult:
    moved: bool
    battle_report: BattleReport | None
    exploration: ExploreResult | None
    movement_points_spent: int
    new_location: HexCoord | None
    reached_target: bool = True
    stopped_chasing: bool = False
    # Phase 1026 -- RULES.AK [8.1]: "Se due Re hanno un rapporto di
    # neutralità, le loro unità militari non attaccano quando ricevono
    # l'ordine di muovere nelle province dell'altro e rimangono invece
    # dove si trovano." User-confirmed scope: blocks an army move only
    # (a lone character with no army always passes freely, including to
    # Recruit -- see ``turn/recruit_execution.py``'s own Phase 303
    # "populace levy needs ownership/ally territory, a mercenary hire
    # doesn't" gate, already correctly separate from this). ``True`` when
    # this call's own move was refused for exactly that reason (the mover
    # brought at least one army, and this Kingdom's relation with the
    # target province's owner is *explicitly* tracked as Neutral --
    # see the call site's own comment for why "explicitly tracked" is
    # the deliberately narrower condition actually checked here).
    # ``stopped_chasing`` is also set alongside this, so ``turn/
    # turn_processor.py``'s own multi-phase chase tracking correctly
    # treats the order as settled rather than retrying it every
    # subsequent phase against a relation that won't change again this
    # turn (diplomacy is resolved once, early in ``run_turn()``). A
    # mover left standing in foreign territory by this block is subject
    # to the exact same check on its own next move order -- there is no
    # separate "stuck" mechanic, it falls out of reapplying this same
    # rule phase after phase.
    blocked_by_neutral_relations: bool = False
    # Phase 410 -- True for *either* a battle-won conquest
    # (``battle_report.conquered``, mirrored here for a single flag
    # callers can check regardless of path) or a real, uncontested one
    # (``battle_report is None``, no defenders were present at all) --
    # see ``execute_move()``'s own Phase 410 addendum.
    conquered: bool = False
    # Phase 490 -- Arch-Mage's own "Sense Magic Items in Province" perk.
    # Never set by ``execute_move()`` itself (this function has no Office
    # context) -- ``None`` for every caller until ``turn/plan_dispatch.py``'s
    # own LMOVE branch fills it in via ``turn/sense_magic_items.py`` after a
    # successful move, the same "assign into the result after the fact"
    # convention the EXPLORE branch already uses for ``discovered_features``.
    sensed_magic_items: list[Treasure] | None = None
    # Phase 634: SAY.PAS `_LWWalk`'s own real trigger -- was the mover's
    # own leader under Mystic Winds (`LeaderState.mystic_winds_active`)
    # at the *start* of this specific `execute_move()` call, snapshotted
    # before this same call's own `fight_battle()` (if any) can clear it
    # -- see `report/turn_report.py record_move_world_events()`'s own
    # Phase 634 addendum for why the caller can't safely reconstruct
    # this after the fact from the leader's own current flag value.
    wind_walking: bool = False
    # Phase 715 -- Fleet/Whale cargo-capacity subsystem's own Phase B:
    # every army id `_auto_board_transport_group()` actually boarded
    # this call (empty when `auto_board` is `False`, the default).
    # Observability for tests and a future report-narration phase --
    # nothing renders this yet. See `turn/sea_transport.py`'s own
    # module docstring for the full mechanic.
    boarded_army_ids: list[int] = field(default_factory=list)
    # Phase 746/754: ADDEND.AK [3.6] "Wandering Mercenaries" -- every
    # mercenary army id that followed the general to `actual_target`
    # this call (empty when no main contingent army of the mover's own
    # had positive movement points left, or no eligible mercenary was
    # standing at the origin -- see this module's own Phase 754
    # addendum for the real, disassembly-sourced mechanism). These
    # armies are relocated but never change ownership; observability
    # for tests -- no report-layer narration is wired yet.
    followed_mercenary_army_ids: list[int] = field(default_factory=list)
    # Phase 754: `Desktop/MOVE.md` section 21.3 -- `True` when this Move
    # genuinely landed the leader in a foreign-owned province that is
    # currently under an active Illusory Fog (`_SANote` for `C_IF=56`,
    # real text quoted in this module's own Phase 754 addendum). See
    # `report/turn_report.py record_illusory_fog_foreign_entry_world_
    # events()` for the real, wired consumer.
    entered_foreign_illusory_fog: bool = False
    # Phase 763 -- Naval Hug Coastline's own real "unboarded stragglers
    # split" (see `_naval_hug_coastline_move_is_legal()`'s own Phase 720
    # addendum for the sourced dossier text this closes). `None` unless
    # this exact call resolved a genuinely mixed group -- a Fleet/Whale
    # carrying only some of the accompanying land armies -- in which case
    # this is the separate, real `MoveExecutionResult` for whichever land
    # armies didn't get a carrier slot, produced by a recursive call that
    # sends them toward the same ultimate `target` by the ordinary route
    # (a ``has_naval_hug_coastline=False`` chase step) while the boarded/
    # carrier portion above takes the coastal shortcut directly. The
    # straggler group never has its own leader (the acting leader is
    # modeled as traveling with the hop group -- a documented modeling
    # choice, not a sourced fact either way) and never re-runs boarding
    # or contested-move/transport-legality checks a second time. Phase
    # 766: wired into the report layer via a sentinel PhaseDispatchResult
    # -- see `_naval_hug_coastline_move_is_legal()`'s own Phase 766 note.
    straggler_result: MoveExecutionResult | None = None
    # Phase 769: MARCH.md section 12's own real dispatcher condition,
    # `CountArmies(leader) <= 0` -- `True` when this specific call's own
    # (pre-straggler-split) `army_ids` was empty, i.e. the leader moved
    # alone. Snapshotted at the top of `execute_move()`, not re-derived
    # from post-move state -- see `report/turn_report.py describe_move()`'s
    # own Phase 769 addendum for the real consumer (`_LMove`/TRAV.X).
    moved_without_armies: bool = False
    # Phase 787: the real, per-game `spabord[Naval]` schedule
    # (`worldgen/naval_ability_level_schedule.py`) grants a Naval
    # `AdvancedAbility` the moment this call's own Move-triggered Naval
    # XP credit crosses one of the schedule's own real levels (5-10) --
    # `None` unless that happened on this exact call. Observability for
    # tests; mirrors `practice_execution.py PracticeExecutionResult.
    # advanced_ability_granted`'s own shape. See this function's own
    # Phase 787 addendum for why this is the only real, reachable
    # trigger for a leader's own personal Naval skill to rise at all.
    naval_advanced_ability_granted: AdvancedAbility | None = None
    # Phase 901: the identical treatment for March -- the same Move-
    # triggered credit branch computes a March XP rise exactly like a
    # Naval one, but nothing granted the resulting AdvancedAbility until
    # `worldgen/march_ability_level_schedule.py` existed to call. See
    # this function's own Phase 901 addendum.
    march_advanced_ability_granted: AdvancedAbility | None = None


def _classify_hex_ownership(state: GameState, kingdom_id: int, coord: HexCoord) -> HexOwnershipTier:
    """Rulebook [3.1]'s tie-break tiers, from real ``GameState`` data (Phase 85).

    ``HERO_OWNED`` is never produced -- ``ProvinceState`` has no way to
    mark an unowned province as specifically Hero-ruled versus
    genuinely wild, the same documented limitation
    ``turn/movement.py HexOwnershipTier``'s own docstring already
    flagged (Phase 78). An unowned or unknown (no province data) hex
    is classified ``NEUTRAL``.
    """

    province = state.provinces.get(coord)
    if province is None or province.owner_kingdom_id is None:
        return HexOwnershipTier.NEUTRAL
    if province.owner_kingdom_id == kingdom_id or state.is_allied(province.owner_kingdom_id, kingdom_id):
        return HexOwnershipTier.OWNED_OR_ALLIED
    return HexOwnershipTier.ENEMY


@dataclass(slots=True)
class KingdomExplorationResult:
    new_percent: int
    discovered_features: list[Feature]


# Phase 630: the 6 terrain-King royal titles' own MeritTally field
# (`models/game_state.py`, Phase 379) -- `AKGEN_embedded_catalogs.
# json.txt gw_format.royal_title_system` entries 30-35 (Ranger of the
# Plains/Desert Rat/Lord of the Jungle/Warden of the Forests/Mountain
# Man/Ruler of the Waves). Same 6-member `Terrain` set `report/
# ascii_map.py TERRAIN_SYMBOL` already uses -- no 7th real terrain.
_TERRAIN_KING_FIELD: dict[Terrain, str] = {
    Terrain.PLAINS: "plains_explorations",
    Terrain.DESERT: "desert_explorations",
    Terrain.JUNGLE: "jungle_explorations",
    Terrain.FOREST: "forest_explorations",
    Terrain.MTNS: "mountain_explorations",
    Terrain.SEA: "sea_explorations",
}


def credit_terrain_king_title(leader: LeaderState, terrain: Terrain) -> None:
    """Credits +1 to the terrain-King royal-title ``MeritTally`` counter
    (``_TERRAIN_KING_FIELD``) for ``terrain`` -- a no-op for a terrain
    with no matching title (e.g. ``Terrain.NO_TERRAIN``). Shared by
    ``record_kingdom_exploration()`` (Explore results, Phase 630) and,
    since Phase 749 (``Desktop/SE+SC.md`` SS25), Scout's own ``fdisc``
    promotion (``turn/search_execution.py _apply_scout()``) -- the real
    ``Inc_Tit(ldr, 30+terrain, 1)`` call the disassembly confirms fires
    from *both* fdisc-promotion routines (``0x114FF`` for 1->2,
    ``0x11371`` for 2->3), a second, independent trigger for the exact
    same counters Explore already credits.
    """

    field = _TERRAIN_KING_FIELD.get(terrain)
    if field is not None:
        setattr(leader.merit_tally, field, getattr(leader.merit_tally, field) + 1)

# Phase 660: the same 6 terrain-King titles' own real "effect_while_held"
# bonus (`models/office.py OFFICE_TITLE_DESCRIPTION`: "can now explore
# [terrain] provinces at double [their] normal rate") -- same 6-member
# Terrain set as _TERRAIN_KING_FIELD above.
_TERRAIN_KING_OFFICE: dict[Terrain, Office] = {
    Terrain.PLAINS: Office.PLAINS_KING,
    Terrain.DESERT: Office.DESERT_KING,
    Terrain.JUNGLE: Office.JUNGLE_KING,
    Terrain.FOREST: Office.FOREST_KING,
    Terrain.MTNS: Office.MOUNTAIN_KING,
    Terrain.SEA: Office.SEA_KING,
}


def record_kingdom_exploration(
    province: ProvinceState,
    kingdom_id: int,
    explorer_skill: int,
    *,
    partial: bool,
    state: GameState | None = None,
    rng: random.Random | None = None,
    has_military_maps: bool = False,
    has_difficult_terrain: bool = False,
    has_find_mines: bool = False,
    leader_id: int | None = None,
) -> KingdomExplorationResult:
    """Advances ``kingdom_id``'s own cumulative exploration of ``province`` (Phase 69) --
    see ``models/game_state.py``'s own module docstring for why this is a
    separate, per-kingdom tracker from ``ProvinceState.explored_percent``.
    Seeded from that kingdom's own prior entry (0 if never recorded before),
    not the shared scalar.

    Phase 242: passing ``state`` also rolls feature discovery for this
    province/kingdom (``turn/exploration.py discover_features()``) using
    the newly-updated percentage. ``state=None`` (the default) skips
    this entirely, preserving every pre-Phase-242 caller's exact
    behavior -- discovery is opt-in, not silently added everywhere.

    Phase 245: returns ``KingdomExplorationResult`` (``new_percent`` plus
    ``discovered_features``, empty when ``state`` is ``None``) instead of
    a bare ``int`` -- previously ``discover_features()``'s own return
    value was computed and thrown away, leaving no way for a caller to
    know *which* features were just found in order to narrate them
    (``report/turn_report.py describe_feature_discovery()``, same phase).

    ``has_military_maps``/``has_difficult_terrain`` (Phase 507) pass
    straight through to ``resolve_explore()`` -- see that function's
    own docstring.

    ``has_find_mines`` (Phase 509): rolls ``turn/exploration.py
    resolve_find_mines()`` once, same ``state``-gated opt-in as feature
    discovery above (the "when exploring an enemy province, this ability
    is not used" check needs real ``GameState`` ownership data). Skipped
    entirely when ``province``'s owner is an enemy of ``kingdom_id`` --
    neutral/unowned and owned-or-allied provinces are both eligible, only
    ``HexOwnershipTier.ENEMY`` is excluded, matching the rulebook text
    exactly. A successful roll mutates ``province.mine_gold_bonus``/
    ``mine_find_attempts`` directly (both province-global, not per-
    kingdom -- see that field's own docstring).

    ``leader_id`` (Phase 630, default ``None``): when given alongside
    ``state``, credits the acting leader's own ``MeritTally`` terrain-
    King royal-title counter (`_TERRAIN_KING_FIELD`) for `province`'s
    own `effective_terrain()` -- "+1 cumulative point when an Explore
    result is recorded in [terrain] terrain" (`royal_title_system`
    entries 30-35). Applies unconditionally on every call this
    parameter is given for (partial or full explore alike, regardless
    of whether the percentage actually changed) -- the real source text
    names no such distinction, so none is invented here. ``None``
    (every pre-Phase-630 caller) leaves this function's prior behavior
    unchanged.

    Phase 660: the same ``state``/``leader_id`` pair also resolves
    whether the acting leader currently *holds* the matching terrain-
    King title (`_TERRAIN_KING_OFFICE`) -- if so, ``resolve_explore()``
    is called with ``has_terrain_king_title=True``, doubling this
    call's own exploration rate (see that function's own Phase 660
    docstring). The exact same gate as the merit credit above, so every
    caller that already passes `state`/`leader_id` for the counter gets
    this for free, no new plumbing needed.
    """

    terrain = province.effective_terrain()
    has_terrain_king_title = False
    if state is not None and leader_id is not None:
        office = _TERRAIN_KING_OFFICE.get(terrain)
        if office is not None:
            holder = resolve_office_holder(state, office)
            has_terrain_king_title = holder is not None and holder.leader_id == leader_id

    prior = province.explored_percent_by_kingdom.get(kingdom_id, 0)
    result = resolve_explore(
        prior,
        terrain,
        explorer_skill,
        partial=partial,
        has_military_maps=has_military_maps,
        has_difficult_terrain=has_difficult_terrain,
        has_terrain_king_title=has_terrain_king_title,
    )
    province.explored_percent_by_kingdom[kingdom_id] = result.new_percent
    if state is not None and prior < KNOWN_PROVINCE_MIN_PERCENT <= result.new_percent:
        kingdom = state.kingdoms.get(kingdom_id)
        if kingdom is not None:
            record_newly_known_column(kingdom, province.coord.x, state.board_width)
    if state is not None and leader_id is not None:
        leader = state.leaders.get(leader_id)
        if leader is not None:
            credit_terrain_king_title(leader, terrain)
    discovered: list[Feature] = []
    if state is not None:
        rng = rng if rng is not None else random.Random()
        if has_find_mines and _classify_hex_ownership(state, kingdom_id, province.coord) is not HexOwnershipTier.ENEMY:
            gold = resolve_find_mines(
                province.effective_terrain(), province.mine_find_attempts, province.mine_gold_bonus, rng
            )
            province.mine_find_attempts += 1
            province.mine_gold_bonus += gold
        discovered = discover_features(state, province.coord, kingdom_id, result.new_percent, rng)
    return KingdomExplorationResult(result.new_percent, discovered)


def reveal_adjacent_provinces(state: GameState, province: ProvinceState, kingdom_id: int, bounds: MapBounds) -> None:
    """"Known provinces" (Phase 623, `models/game_state.py`'s own
    module docstring addendum): entering `province` also reveals each
    of its own real neighbors to `kingdom_id` at the flat `KNOWN_
    PROVINCE_MIN_PERCENT` floor, if not already known -- the user's own
    example, "passing by way of an adjacent province." Never *lowers* a
    neighbor's own recorded percentage (`known_to_kingdom()` is already
    `True` for anything at or above the floor, so this only ever writes
    a neighbor that was still fully unknown). Called at every site that
    already calls `record_kingdom_exploration()` for a real province
    entry -- see this module's own Phase 623 addendum in each caller.
    """

    for neighbor in neighbors(province.coord, bounds):
        neighbor_province = state.provinces.get(neighbor)
        if neighbor_province is not None and not neighbor_province.known_to_kingdom(kingdom_id):
            neighbor_province.explored_percent_by_kingdom[kingdom_id] = KNOWN_PROVINCE_MIN_PERCENT
            kingdom = state.kingdoms.get(kingdom_id)
            if kingdom is not None:
                record_newly_known_column(kingdom, neighbor.x, state.board_width)


# Phase 754: the base per-hex movement cost `Apply_Move`'s own real
# routine consumes from a following mercenary -- `MOVE.md` section 18
# confirms the wrapper's own base-cost argument is `1` for an ordinary
# `MOVE`, not the caller's own possibly-surcharged `cost` (conquest/sea-
# battle/etc., which apply only to the invading force itself).
WANDERING_MERCENARY_FOLLOW_MOVEMENT_COST = 1


def resolve_wandering_mercenary_following(
    state: GameState,
    origin: HexCoord,
    target: HexCoord,
    origin_province: ProvinceState | None,
    target_province: ProvinceState,
) -> list[int]:
    """`Desktop/MS/ADDEND.AK` [3.6], real mechanism per `Desktop/MOVE.md`
    section 18.8-18.9 (see this module's own Phase 754 addendum for the
    full disassembly account) -- any mercenary army (`GameState.
    mercenaries_at()`, `ArmyState.kingdom_id is None`) left standing at
    `origin` when a general's Move genuinely departs it may follow that
    general to `target`. Deterministic, not a coin flip: eligible iff
    the mercenary's own `movement_points > 0` and `find_transport_
    illegality()` (Phase 737, reused directly) finds no legal-transport
    objection to that same hop for its own army type. Ownership is
    never touched (`kingdom_id`/`commanded_by` stay exactly as they
    were) -- only `location` and `movement_points` change, mirroring
    the real routine's own confirmed "astate is never written" finding.

    Every eligible mercenary follows, in a deterministic (`army_id`-
    sorted) order -- no `rng` needed. Returns the ids of every army that
    actually followed this call -- `[]` when none are present or none
    are eligible.
    """

    followed: list[int] = []
    for army in sorted(state.mercenaries_at(origin), key=lambda a: a.army_id):
        if army.movement_points <= 0:
            continue
        if find_transport_illegality([army], [army.army_id], origin_province, target_province) is not None:
            continue
        army.location = target
        army.movement_points -= WANDERING_MERCENARY_FOLLOW_MOVEMENT_COST
        followed.append(army.army_id)
    return followed


# Phase 715 -- the one real, sourced allocation-priority order found for
# this whole subsystem (`AKGEN_reverse_engineering_report (3).md` SS106,
# scoped there to `AdvancedAbility.NAVAL_HUG_COASTLINE` specifically):
# "prima unità con velocità base 1 o 2, a parità designazione/ID di
# armata più basso" -- reused directly here as the one real, documented
# priority, since no other source gives a different one for ordinary
# transport.
# Phase 717: Dragon Wing/Eagle Wing join as carriers too -- `Regolamento
# AK.txt`'s own "Possono trasportare un'unità di fanteria ciascuna,"
# an unconditional base rule (no Advanced Ability gate).
_CARRIER_ARMY_TYPES = (ArmyType.FLEET, ArmyType.WHALES, ArmyType.DRAGON_WING, ArmyType.EAGLE_WING)


def _boarding_priority_tier(army_type: ArmyType) -> int:
    """0 = "speed 1 or 2" (boards first); 1 = everything else, including
    the handful of `ArmyType` members with no `ARMY_TABLE` entry at all
    (Vampires, Marauders, Shamans, Crossbow, Javelins, Artillery,
    Spiders, D Turtle -- a real, pre-existing gap, confirmed by direct
    check) -- a safe, conservative fallback (never wrongly claims the
    high-priority tier for a type whose real speed isn't recorded),
    not a crash.
    """

    stats = ARMY_TABLE.get(army_type)
    return 0 if stats is not None and stats.speed <= 2 else 1


def _auto_board_transport_group(
    state: GameState,
    armies: list[ArmyState],
    *,
    caster_has_druidic_whale_transport: bool = False,
    caster_has_druidic_transport: bool = False,
) -> list[int]:
    """Automatically boards as many eligible land armies as fit onto
    whichever Fleet/Whale carriers are moving in the same group -- see
    ``execute_move()``'s own Phase 715 addendum. Returns every army id
    actually boarded this call.
    """

    carriers = sorted((army for army in armies if army.army_type in _CARRIER_ARMY_TYPES), key=lambda army: army.army_id)
    if not carriers:
        return []

    candidates = sorted(
        (army for army in armies if army.army_type not in _CARRIER_ARMY_TYPES and army.transported_by is None),
        key=lambda army: (_boarding_priority_tier(army.army_type), army.army_id),
    )

    boarded_army_ids: list[int] = []
    for candidate in candidates:
        for carrier in carriers:
            if board_army(
                state,
                candidate.army_id,
                carrier.army_id,
                caster_has_druidic_whale_transport=caster_has_druidic_whale_transport,
                caster_has_druidic_transport=caster_has_druidic_transport,
            ):
                boarded_army_ids.append(candidate.army_id)
                break
    return boarded_army_ids


# Phase 737 -- the real sea-transport movement-legality gate `execute_
# move()`'s own docstring long flagged as unenforced (`Regolamento
# AK.txt` lines 870-876): land units genuinely cannot cross onto/off
# Sea terrain without a same-move carrier with free capacity; a Fleet/
# Whale itself cannot hop directly between two land provinces; Ents/
# Dinosaurs additionally need a real, successful boarding (`DRUIDIC_
# TRANSPORT`) or an active Part Sea effect to cross Sea at all; Mermen
# need either an active Part Sea effect on the land endpoint
# specifically, or a same-move air-type carrier, to cross onto
# genuinely permanent land (`turn/sea_transport.py`'s own module
# docstring: "I Tritoni muovono come le Flotte, con l'eccezione che
# possono entrare ed uscire da una provincia colpita da un incantesimo
# Separare le Acque... possono essere trasportate da unità aeree").
#
# Twenty-ninth fresh codebase survey (2026-09-04), candidate #1. Four
# design decisions confirmed directly with the user: (1) broad scope --
# also enforce Ent/Dinosaur/Mermen, not just the two base rules; (2) the
# Whale-vs-Fleet conflict (rulebook says both may enter/exit land;
# `ILLMOVE_TEMPLATE[2]` forbids Whales specifically) is resolved in the
# rulebook's favor -- Whales and Fleets treated identically, choice `2`
# stays unattributed to any real scenario; (3) both real LMOVE dispatch
# paths are covered by this one shared, pure helper (`execute_move()`
# below, and `turn/turn_processor.py _dispatch_multi_attacker_lmove()`,
# which has its own entirely separate movement logic and would not
# otherwise inherit this gate); (4) `execute_move()`'s own new parameter
# defaults off, matching every prior Move feature's own opt-in rollout
# (`auto_board`, `has_naval_hug_coastline`, ...) -- wired True only at
# the real `turn/plan_dispatch.py` LMOVE dispatch call site.
#
# A key mechanical simplification, found by tracing the code, not
# assumed: `ProvinceState.effective_terrain()` already correctly
# resolves a Part-Sea'd province back to its land terrain (`turn/
# cast_execution.py _execute_part_sea()` sets `terrain_override =
# Terrain.PLAINS`) -- so a plain `effective_terrain() == Terrain.SEA`
# check at both endpoints already correctly permits an ordinary land
# army, Ent, or Dinosaur to cross during an active Part Sea effect, with
# no separate "is this province currently Parted" detection needed for
# them. Only Mermen need that distinction spelled out explicitly, since
# their own rule is about the province's *real* base terrain
# (`ProvinceState.terrain`), not just its current effective one.
#
# Phase 738 closed a real, adjacent gap this phase's own first version
# left open: `turn/sea_transport.py can_board()`'s own air-carrier
# branch didn't accept `ArmyType.MERMEN` cargo, so a real `board_army()`
# call could never actually seat a Mermen unit onto a Dragon/Eagle Wing
# -- meaning this gate's own Mermen-via-air-carrier exemption below
# (`"mermen_air_transport"`) was real and tested but unreachable via
# real automatic boarding. Now reachable -- see that module's own Phase
# 738 addendum.
TransportIllegalMoveReason = Literal[
    "insufficient_water_transport", "naval_land_hop", "ent_shoreline", "dinosaur_shoreline", "mermen_air_transport"
]


class TransportIllegalMoveError(ValueError):
    """Raised by `execute_move()` and `turn/turn_processor.py _dispatch_
    multi_attacker_lmove()` when `find_transport_illegality()` refuses a
    move -- a dedicated subclass (not a bare `ValueError`, which both
    real raise sites also use for an unrelated "no province data" case),
    mirroring `turn/contested_province.py IllegalMoveFromContestedError`'s
    own exact shape, so `report/turn_report.py describe_turn_results()`
    can narrate this one specific, sourced scenario without narrating
    every other exception type too. See the addendum right above this
    class for the full sourcing.
    """

    def __init__(self, reason: TransportIllegalMoveReason, *, origin_coord: HexCoord, destination_coord: HexCoord) -> None:
        super().__init__(reason)
        self.reason = reason
        # PhaseDispatchResult carries no raw target hex once dispatch
        # fails (result stays None) -- report/turn_report.py describe_
        # turn_results() reads these two fields directly off the
        # exception itself to resolve real province names, rather than
        # widening PhaseDispatchResult's own shape for one error type.
        self.origin_coord = origin_coord
        self.destination_coord = destination_coord


def _is_part_sea(province: ProvinceState | None) -> bool:
    """A province currently under a Part Sea effect: its own real base
    terrain is still Sea, but `terrain_override` has flipped it walkable
    (`turn/cast_execution.py _execute_part_sea()`). Distinct from
    `effective_terrain() != Terrain.SEA` alone, which can't tell a
    naturally-land province from a Part-Sea'd one -- only Mermen's own
    rule (see `find_transport_illegality()`) needs that distinction.
    """

    return province is not None and province.terrain is Terrain.SEA and province.terrain_override is Terrain.PLAINS


def _land_crossing_blocked(
    province: ProvinceState | None, is_sea: bool, has_march_through_floods: bool, *, flood_dams_exempt: bool = False
) -> bool:
    """Whether this one endpoint blocks an ordinary land-type army's own
    passage: Sea-effective (or `NO_TERRAIN`), and -- when it's a real
    Flood (`terrain_override = Terrain.SEA` on a province whose own base
    `.terrain` isn't Sea) rather than naturally Sea -- not excused by
    `AdvancedAbility.MARCH_THROUGH_FLOODS`'s own sourced text: "it
    becomes possible for armies to enter or leave any province affected
    by the Flood spell" (the ability's own real, separate movement-point
    surcharge, `turn/move_execution.py`'s own Phase 693 addendum, is
    unaffected by this -- it's a cost, not a legality question, and
    stays wired exactly as before), nor (Phase 888) by `flood_dams_
    exempt` -- `True` exactly for the specific army/province pair
    `turn/cast_execution.py _execute_flood()` already charged Discovery.
    FLOOD_DAMS's own one-time movement-point toll to. A genuinely
    natural Sea province is never excused either way -- no source
    claims either exemption helps against real ocean, only against the
    spell's own effect.
    """

    if not is_sea:
        return False
    if province is not None and province.terrain is not Terrain.SEA:
        if has_march_through_floods:
            return False  # a real Flood, excused by the ability
        if flood_dams_exempt:
            return False  # a real Flood, this army already paid the Flood Dams toll
    return True


def find_transport_illegality(
    armies: list[ArmyState],
    army_ids: list[int],
    origin_province: ProvinceState | None,
    target_province: ProvinceState,
    *,
    has_march_through_floods: bool = False,
    is_hug_coastline_hop: bool = False,
) -> TransportIllegalMoveReason | None:
    """The real sea-transport legality check -- see the module-level
    Phase 737 addendum right above `TransportIllegalMoveReason` for the
    full sourcing and design. Pure and side-effect-free: does not raise
    itself, does not mutate `armies`/either province -- both real
    callers (`execute_move()`, `turn_processor.py _dispatch_multi_
    attacker_lmove()`) decide what to do with the result.

    Returns the *first* violation found across `armies` -- an all-or-
    nothing refusal for the whole moving group, matching this project's
    own established Hug-Coastline-style "one blocker refuses the entire
    stack" convention. `None` means every army has legal passage for
    this specific hop. `Terrain.NO_TERRAIN` is treated like `Terrain.
    SEA` throughout (impassable without transport), mirroring `_naval_
    hug_coastline_move_is_legal()`'s own existing precedent -- the only
    prior movement-legality code to touch `NO_TERRAIN` at all.

    `has_march_through_floods` only ever *relaxes* the ordinary land-
    unit/Ent/Dinosaur checks below against a real Flood specifically
    (see `_land_crossing_blocked()`) -- it never affects Fleet/Whale's
    own land-to-land restriction (a Flooded endpoint already counts as
    Sea for their own purposes, so the question never arises) or
    Mermen's own rule (already sea-effective either way, flooded or
    natural). Phase 888: `ArmyState.flood_dams_exempt_at` is a second,
    independent (per-army, not per-caster) relaxation of the identical
    check, read fresh per army inside the loop below -- an army whose
    own Kingdom's Discovery.FLOOD_DAMS already charged it this turn's
    toll for exactly this coord is excused the same way `has_march_
    through_floods` excuses the whole moving party.

    `is_hug_coastline_hop` (Phase 819 bug fix): `execute_move()` passes
    `True` exactly when `_naval_hug_coastline_move_is_legal()` has
    already confirmed this specific hop is a legitimate `AdvancedAbility.
    NAVAL_HUG_COASTLINE` land-to-land jump across a shared coastal sea
    hex (Phase 524/720, extensively tested -- `test_execute_move_naval_
    hug_coastline_grants_the_hop_when_the_fleet_can_carry_every_land_
    army` has a real Fleet ending the hop at a land province alongside
    its boarded cargo). Before this fix, a Fleet/Whale making exactly
    this real, already-legal hop was unconditionally flagged
    `"naval_land_hop"` here -- neither endpoint of a Hug Coastline hop
    is ever `Terrain.SEA` by construction (that's the entire point of
    the shortcut), so `origin_is_sea or target_is_sea` was always False
    for it. This was live in production: `turn/plan_dispatch.py`'s own
    real LMOVE dispatch already passes `enforce_transport_legality=True`
    unconditionally (Phase 737) alongside a real `has_naval_hug_
    coastline` flag (Phase 524) for any leader holding the ability --
    every Fleet/Whale actually using this ability was silently blocked
    outright, with zero existing test ever combining the two flags to
    catch it. Only relaxes the Fleet/Whale branch immediately below --
    Mermen's own separate rule is checked first and never reaches this
    branch at all (see the dedicated branch above), and ordinary land
    units are already unaffected by a Hug Coastline hop (both endpoints
    are real land, so `_land_crossing_blocked()` never blocks them
    regardless of this flag).
    """

    origin_terrain = origin_province.effective_terrain() if origin_province is not None else Terrain.NO_TERRAIN
    target_terrain = target_province.effective_terrain()
    origin_is_sea = origin_terrain in (Terrain.SEA, Terrain.NO_TERRAIN)
    target_is_sea = target_terrain in (Terrain.SEA, Terrain.NO_TERRAIN)

    for army in armies:
        if army.transported_by is not None and army.transported_by in army_ids:
            continue  # legally aboard a same-move carrier
        if army.army_type in OVERFLIGHT_AIR:
            continue  # "can move by land and sea... can end a turn on the sea"
        if army.army_type is ArmyType.MERMEN:
            origin_passable = origin_is_sea or _is_part_sea(origin_province)
            target_passable = target_is_sea or _is_part_sea(target_province)
            if origin_passable and target_passable:
                continue
            return "mermen_air_transport"
        if army.army_type in SEA_ARMY_TYPES:  # Fleet, Whales
            if origin_is_sea or target_is_sea or is_hug_coastline_hop:
                continue  # entering/leaving land on its own is fine, or a real, already-verified Hug Coastline hop
            return "naval_land_hop"
        origin_flood_dams_exempt = origin_province is not None and army.flood_dams_exempt_at == origin_province.coord
        target_flood_dams_exempt = army.flood_dams_exempt_at == target_province.coord
        origin_blocked = _land_crossing_blocked(
            origin_province, origin_is_sea, has_march_through_floods, flood_dams_exempt=origin_flood_dams_exempt
        )
        target_blocked = _land_crossing_blocked(
            target_province, target_is_sea, has_march_through_floods, flood_dams_exempt=target_flood_dams_exempt
        )
        if not (origin_blocked or target_blocked):
            continue  # an ordinary land move, no unexcused Sea endpoint
        if army.army_type is ArmyType.ENTS:
            return "ent_shoreline"
        if army.army_type is ArmyType.DINOSAURS:
            return "dinosaur_shoreline"
        return "insufficient_water_transport"
    return None


# Phase 768: `Desktop/PROGRAMMA AK/MARCH.md` section 11, `AK.EXE:0xB5CF-
# 0xB65C` -- a Move with armies tries a real March/Naval experience
# credit, base "10", once per qualifying call (see `execute_move()`'s
# own Phase 768 addendum for the full gating/sourcing). The document
# names this helper "Try_Experience," at address `104A:1877` -- the
# *exact same* address `turn/experience.py`'s own docstring already
# cites for `Add_Experience` (Phase 456, already wired for Melee/
# Archery, Phase 686). Treated as the identical, already-proven
# routine/call-convention rather than a second, unrelated mechanic.
MOVE_MARCH_NAVAL_EXPERIENCE_BASE_POINTS = 10


def execute_move(
    state: GameState,
    kingdom_id: int,
    army_ids: list[int],
    target: HexCoord,
    *,
    leader_id: int | None = None,
    explorer_skill: int = 0,
    loser_retreats: bool = True,
    rng: random.Random | None = None,
    has_military_maps: bool = False,
    has_difficult_terrain: bool = False,
    has_find_mines: bool = False,
    has_march_cavalry: bool = False,
    has_march_cavalry_mastery: bool = False,
    has_march_cavalry_true_mastery: bool = False,
    has_march_infantry: bool = False,
    has_march_infantry_mastery: bool = False,
    has_march_through_floods: bool = False,
    march_skill_level: int = 0,
    naval_skill_level: int = 0,
    has_naval_hug_coastline: bool = False,
    auto_board: bool = False,
    caster_has_druidic_whale_transport: bool = False,
    caster_has_druidic_transport: bool = False,
    enforce_transport_legality: bool = False,
) -> MoveExecutionResult:
    """Move ``army_ids`` (all from the same province) toward ``target``.

    ``army_ids`` may be empty if ``leader_id`` is given -- a character
    moving alone. Fights a battle automatically if the hex actually
    entered this phase holds a non-allied army AND the mover brought at
    least one army of their own. Raises if the armies don't share a
    starting province, if any lacks a movement point, if neither
    ``army_ids`` nor ``leader_id`` is given, or if the hex actually
    entered this phase has no province data.

    **Phase 521 -- March category, `AdvancedAbility.MARCH_CAVALRY`/
    `_INFANTRY` (+ Mastery tiers).** `models/advanced_ability.py`'s own
    sourced text: Cavalry "adds one to the movement rate of land armies
    which start with 3 or more movement points"; Infantry, the same for
    "1-2 movement points"; each Mastery tier "adds one more" to its own
    band. Rulebook [6.2] itself frames this as dynamic, not a pre-turn
    recompute: "The increased army-movement allowed by the March and
    Naval abilities is always calculated at the moment an army moves."
    Rather than fold the bonus into a precomputed base rate, this phase
    reads the sourced quote literally:
    `execute_move()` grants the bonus as a one-time addition to the
    army's own *current* pool, right before this move's own cost is
    deducted, gated on `ArmyState.march_bonus_applied_this_turn` so a
    multi-phase turn (several Move orders) can't re-grant it. A leader
    only ever holds one Advanced Ability per category (Phase 128), so a
    Mastery tier's own "adds one more" is read as its own total,
    self-contained effect (+2), not "+1 on top of the base tier you
    don't hold" -- the same convention Melee Mastery/True Mastery
    (Phase 517) already established. "Land armies" excludes the three
    purely sea-going types (`models/army_type.py SEA_ARMY_TYPES` --
    Fleet, Whales, Mermen); air units (Dragon Wing/Eagle Wing) were
    originally left land-eligible here too, since no source at the time
    narrowed the wording to exclude them -- **corrected in Phase 523**,
    see that addendum below.

    **Phase 764 -- [4.12] MARCH TABLE's own separate, raw-skill-level
    movement bonus, closing `turn/multiple_contingents.py`'s own
    long-flagged "a distinct, still-unmodeled gap" note.** See
    `march_table_extra_movement()`'s own docstring for the full sourcing
    and why it's genuinely distinct from (and stacks with) the Advanced-
    Ability-gated bonus this Phase 521 addendum describes above -- this
    one applies to every land army from its own commander's raw
    `Ability.MARCH` skill level, `0` included, gated on `ArmyState.
    march_table_bonus_applied_this_turn` the same once-per-gameturn way.

    **Phase 693 -- `AdvancedAbility.MARCH_THROUGH_FLOODS`, closing the
    stale blocker directly above (kept for history, corrected here).**
    That note claimed this project's own `_execute_flood()` "never
    sets" a persistent per-province "currently flooded" flag -- stale
    since Phase 225/226, over 166 phases before this note was written:
    `_execute_flood()` (`turn/cast_execution.py`) sets `ProvinceState.
    terrain_override = Terrain.SEA`, and `effective_terrain()` has read
    it ever since. That override is unambiguously Flood's own signal --
    Part Sea sets the opposite direction (`terrain_override = Terrain.
    PLAINS`), and every real Flood target starts from `_FLOOD_ELIGIBLE_
    TERRAIN` (never a province already Sea) -- see `is_flooded_
    province()` below. The sourced text itself -- "it becomes possible
    for armies to enter or leave any province affected by the Flood
    spell. One movement point is deducted from all units which have to
    use this ability, after they have moved" -- is read the same way
    Phase 651 (Illusory Fog's own "must expend 1 additional movement
    point when entering or leaving it") already read an analogous
    clause: **at the time this note was written**, this project had no
    general terrain-movement-legality gate anywhere (no code blocked a
    land army from entering a Sea-terrain province, flooded or
    naturally Sea, at all), so "becomes possible" was modeled as a
    movement-point surcharge for land armies making such a move, not as
    an invented blocking mechanic for a restriction this project didn't
    otherwise model at the time. **Stale as of Phase 737** -- a real,
    general terrain-movement-legality gate now exists in this same
    module (`find_transport_illegality()`, below), enforced
    unconditionally by the real production LMOVE dispatch (`turn/plan_
    dispatch.py`, `enforce_transport_legality=True`). `has_march_
    through_floods` is precisely the parameter that ability now also
    threads into that gate, *relaxing* what would otherwise be a real
    refusal for crossing into/out of a Flooded province -- so "becomes
    possible" is no longer purely a surcharge-only reading: without the
    ability, the crossing is genuinely illegal today; with it, the
    crossing is legal AND still pays the movement-point surcharge this
    section originally modeled, both layers coexisting rather than one
    superseding the other. Naval's own movement-point bonus is closed
    in Phase 523, and both remaining Naval members (`NAVAL_LONG_DEFEND`,
    `NAVAL_HUG_COASTLINE`) are closed in Phase 524 -- see the addenda
    below.

    **Phase 523 -- Naval movement bonus + air-unit correction.**
    `AKGEN_reverse_engineering_report (3).md` SS97-99 (disassembly of
    `AKE.EXE:0x21F6A-0x22080 MovementBonus`) gives the real per-army-
    type dispatcher this project never had a source for before:

    ```pascal
    case at of
      Dragonwing, Eaglewing: MovementBonus := 0;
      WhaleLeague, Fleet, Mermen: MovementBonus := M_Skill(leader, Naval);
      else: MovementBonus := MarchBonus(army_id, leader);
    end;
    ```

    Two consequences: (1) Whale League/Fleet/Mermen (`SEA_ARMY_TYPES`)
    get a movement bonus equal to the leader's own effective Naval skill
    level, uncapped ("Non compare min(4,NA) nel ramo navale") -- wired
    exactly like March's own bonus, a one-time addition right before
    this move's cost is deducted, gated on the new `ArmyState.naval_
    bonus_applied_this_turn` flag; (2) Dragon Wing/Eagle Wing get a flat
    zero from *either* ability -- a real, sourced correction to the
    Phase 521 paragraph above, which had assumed air units stayed
    March-eligible for lack of a narrowing source. `models/army_type.py
    is_land_army()` now excludes `OVERFLIGHT_AIR` too, so this also
    quietly fixes March for air units at the same time. `naval_skill_
    level` (default 0, the acting leader's `effective_skill_level(state,
    leader, Ability.NAVAL)`, threaded in by `turn/plan_dispatch.py`)
    isn't itself Advanced-Ability-gated -- unlike March, Naval's
    movement bonus is a plain function of raw skill, no Mastery tier or
    band-of-current-movement-points qualifier involved.

    **Phase 524 -- `AdvancedAbility.NAVAL_HUG_COASTLINE`, the last
    Naval member.** (`NAVAL_LONG_DEFEND`, the other one, is closed the
    same phase but lives entirely in `turn/defend_execution.py` -- see
    that module's own Phase 524 addendum, not this one.) SS106's own
    compiled gate (`SA.X2:47-49`, `AKE.EXE:0x22153-0x222D0`): a leader
    holding this ability can hop directly between two land provinces
    that share a common sea-hex neighbor, "slipping in and out of
    shallows along the coast," without a separate order into that sea
    hex. `has_naval_hug_coastline=True` extends the adjacency check this
    function already makes before falling back to a multi-phase chase:
    if the target isn't geometrically adjacent but the hop is Hug-
    Coastline-legal (`_naval_hug_coastline_move_is_legal()`), it's
    resolved as an ordinary one-hex move to the real target instead of
    a chase step -- same cost formula, same battle trigger, same
    exploration update, no special-casing needed anywhere else in this
    function. Deliberately excluded (see that helper's own docstring):
    when a Fleet/Whale/Mermen unit travels in the same stack, the real
    engine's own transport-capacity allocation sub-mechanic would apply
    instead -- **Phase 715** built that capacity model (`turn/sea_
    transport.py`), but this specific shortcut still isn't wired to it
    (a different, more specific priority rule, see that helper's own
    docstring); the shortcut is still only granted when every
    accompanying army is land-based.

    If ``target`` isn't adjacent to the mover's own current location,
    this is a chase (Phase 85, rulebook [3.1]): one hex-step toward
    ``target`` is computed and resolved instead, and
    ``MoveExecutionResult.reached_target``/``stopped_chasing`` report
    how it went -- see this module's own docstring for the full
    behavior, including its own multi-phase persistence (closed,
    Phase 632 -- ``turn/turn_processor.py run_turn()`` now carries an
    unresolved chase across subsequent phases the same way Pursue/
    Trail's own persistence does).

    Phase 521: ``has_march_cavalry``/``has_march_cavalry_mastery``/
    ``has_march_infantry``/``has_march_infantry_mastery`` (default
    False) grant ``march_movement_point_bonus()`` to a qualifying land
    army, at most once per gameturn per army (``ArmyState.march_bonus_
    applied_this_turn``) -- see module docstring's own Phase 521
    addendum.

    Phase 523: ``naval_skill_level`` (default 0) grants ``naval_
    movement_point_bonus()`` to a Whale League/Fleet/Mermen army, at
    most once per gameturn per army (``ArmyState.naval_bonus_applied_
    this_turn``) -- see module docstring's own Phase 523 addendum.

    Phase 524: ``has_naval_hug_coastline`` (default False) lets a
    non-adjacent land-to-land hop that shares a coastal sea-hex
    neighbor resolve as an ordinary move instead of a chase step -- see
    module docstring's own Phase 524 addendum.

    **Phase 715 -- Fleet/Whale cargo-capacity subsystem, Phase B.**
    ``auto_board`` (default False) turns on automatic boarding: when the
    moving party contains a Fleet/Whale alongside eligible land armies,
    as many as fit are boarded onto it (``turn/sea_transport.py
    can_board()``'s own real capacity rules, ``caster_has_druidic_
    whale_transport``/``caster_has_druidic_transport`` gating the two
    Advanced-Ability extensions) before movement points are ever
    touched -- see ``_auto_board_transport_group()`` below. A boarded
    army spends none of its own movement points this call (rulebook:
    "cannot use a land movement point and be transported... in the same
    turn") -- only its carrier pays the ordinary cost. An army that was
    already boarded, moving without its own carrier this call (in
    either direction -- the cargo moving alone, or the carrier moving
    without some of its cargo), is disembarked first/left behind --
    see the real code for both checks, right below and near the end of
    this function. ``auto_board`` itself defaults False, so every pre-
    Phase-715 caller (including every direct test call) is completely
    unaffected; only ``turn/plan_dispatch.py dispatch_phase()``'s own
    real LMOVE dispatch passes ``True``.

    **Phase 737 -- the real transport-legality restriction, now
    enforced.** ``enforce_transport_legality`` (default False) raises
    ``TransportIllegalMoveError`` when ``find_transport_illegality()``
    (above) finds any army in ``army_ids`` lacking legal passage for
    this specific single-hex hop -- see that function's own docstring,
    and the module-level Phase 737 addendum right above it, for the
    full sourcing/design. Defaults False for the identical reason
    ``auto_board`` does: every existing test for an unrelated feature
    (Illusory Fog, March Through Floods, sea-conquest surcharges) that
    moves a land army onto Sea terrain unassisted stays unaffected;
    only ``turn/plan_dispatch.py dispatch_phase()``'s own real LMOVE
    dispatch passes ``True``.

    **Phase 768 -- Move-triggered March/Naval experience credit,
    `Desktop/PROGRAMMA AK/MARCH.md` section 11.** `AK.EXE:0xB5CF-
    0xB65C`: a Move made with real armies tries `Add_Experience(leader,
    Naval, 10)` when origin *or* destination terrain is Sea, else
    `Add_Experience(leader, ForcedMarch, 10)` -- excluding a majority-
    air-or-air-transportable force. **Phase 819 correction**: this is
    *not* the same test the `_LFly` narration branch uses (that one is a
    documented, unsourced, user-confirmed heuristic --
    `report/turn_report.py`'s own module-level comment above
    `_FLY_MOVE_TEMPLATE` -- "every army the mover brought is an
    overflight type," `all(is_overflight_unit(...))`, not a majority
    test at all) -- this citation was simply wrong; `2 * air_count <
    len(armies)` below is a real, independent formula used only here,
    confirmed genuinely ambiguous and kept as originally shipped (Phase
    784's own investigation, reverted, see that phase's own history).
    The document itself names this helper "Try_Experience," distinct
    from "Add_Experience" -- but it cites the *exact same* address,
    `104A:1877`, `turn/experience.py`'s own docstring already gives for
    `Add_Experience` (Phase 456). Treated as the identical, already-
    wired routine (`add_experience()`, the same call convention Melee/
    Archery already use, Phase 686), not a second, separately-gated
    percent-chance mechanic. Gated on `moved` (this call's own real
    hex-step) rather than on "one whole player order" -- faithful to
    the real engine's own architecture, since Move dispatch is always
    per-phase here too (Phase 632's own persistent-chase re-dispatch
    confirms this project's port and the original share that same
    shape), so a multi-phase chase's own repeated real hex-steps each
    trying this roll independently is the correct behavior, not an
    over-count. The Phase 763 straggler recursive call above passes
    `leader_id=None`, so it's naturally excluded, no special-casing
    needed. Deliberately out of scope: the multi-attacker LMOVE
    dispatch path (`turn/turn_processor.py
    _dispatch_multi_attacker_lmove()`) doesn't call this function at
    all (a separate `resolve_move()`/`fight_multi_attacker_battle()`
    path, Phase 754) -- this credit stays scoped to this function's own
    real callers, the same boundary several earlier Move-feature phases
    already accepted for that separate dispatch path.

    **Phase 769 -- `MoveExecutionResult.moved_without_armies`,
    MARCH.md section 12's own `CountArmies(leader) <= 0` dispatcher
    condition.** Snapshotted from this call's own (pre-straggler-split)
    `army_ids` right at the top of this function -- see that field's
    own docstring for the real consumer.
    """

    rng = rng if rng is not None else random.Random()
    if not army_ids and leader_id is None:
        raise ValueError("no armies and no leader given -- nothing to move")

    armies = [state.armies[army_id] for army_id in army_ids]
    moved_without_armies = not armies
    if armies:
        current = armies[0].location
        if any(army.location != current for army in armies):
            raise ValueError("all armies must move together from the same province")
        if any(army.movement_points < 1 for army in armies):
            raise ValueError("an army with no movement points left this gameturn can't move")
    else:
        current = state.leaders[leader_id].location

    # Phase 715 -- an army moving without its own current carrier (the
    # carrier's own id isn't part of this same move) naturally leaves
    # it. Unconditional (not gated on auto_board) -- a correctness fix,
    # not a new mechanic; a no-op for every army whose transported_by
    # is already None. See the docstring's own Phase 715 addendum.
    for army in armies:
        if army.transported_by is not None and army.transported_by not in army_ids:
            disembark_army(state, army.army_id)

    boarded_army_ids: list[int] = []
    if auto_board:
        boarded_army_ids = _auto_board_transport_group(
            state,
            armies,
            caster_has_druidic_whale_transport=caster_has_druidic_whale_transport,
            caster_has_druidic_transport=caster_has_druidic_transport,
        )

    # Phase 634: snapshotted here, before this same call's own
    # fight_battle() (below) can clear it -- see MoveExecutionResult.
    # wind_walking's own docstring for why this must happen now, not
    # read from the leader after the fact.
    leader_snapshot = state.leaders.get(leader_id) if leader_id is not None else None
    wind_walking = leader_snapshot is not None and leader_snapshot.mystic_winds_active

    bounds = MapBounds(state.board_width, state.board_height)
    # Phase 720/763: whether the shortcut is even geometrically/ability-
    # wise on the table at all, independent of this group's own boarding
    # composition -- reused below both to decide the split (Phase 763)
    # and to gate the final `is_hug_coastline_hop` flag.
    hug_coastline_geometrically_eligible = (
        has_naval_hug_coastline
        and current != target
        and not is_adjacent(current, target, bounds)
        and _naval_hug_coastline_move_is_legal(state, current, target, bounds)
    )
    # Phase 763: SS106's own "unboarded stragglers still travel
    # separately, by the ordinary route" split -- see
    # _naval_hug_coastline_move_is_legal()'s own Phase 763 addendum. Only
    # a genuinely mixed stack (a real carrier present) can strand a land
    # army at all; a pure land stack either takes the shortcut in full or
    # (if geometrically ineligible) falls through to the ordinary
    # whole-group chase below, unaffected by any of this.
    straggler_ids: list[int] = []
    if hug_coastline_geometrically_eligible and any(army.army_type in SEA_ARMY_TYPES for army in armies):
        straggler_ids = [
            army.army_id
            for army in armies
            if is_land_army(army.army_type)
            and not (army.transported_by is not None and army.transported_by in army_ids)
        ]
    straggler_result: MoveExecutionResult | None = None
    if straggler_ids:
        # The boarded/carrier portion (below) takes the coastal shortcut
        # directly to `target`; the stragglers get their own real,
        # independent resolution toward the same ultimate `target` --
        # ordinarily a one-hex chase step, exactly what this same
        # function already gives any non-adjacent mover once
        # `has_naval_hug_coastline` is off. No leader travels with them
        # (the acting leader is modeled as staying with the hop group --
        # a documented modeling choice, not a sourced fact either way),
        # and boarding/contested-move/transport-legality were already
        # resolved once, above, for the whole original group.
        straggler_result = execute_move(
            state,
            kingdom_id,
            straggler_ids,
            target,
            leader_id=None,
            explorer_skill=explorer_skill,
            loser_retreats=loser_retreats,
            rng=rng,
            has_military_maps=has_military_maps,
            has_difficult_terrain=has_difficult_terrain,
            has_find_mines=has_find_mines,
            has_march_cavalry=has_march_cavalry,
            has_march_cavalry_mastery=has_march_cavalry_mastery,
            has_march_cavalry_true_mastery=has_march_cavalry_true_mastery,
            has_march_infantry=has_march_infantry,
            has_march_infantry_mastery=has_march_infantry_mastery,
            has_march_through_floods=has_march_through_floods,
            march_skill_level=march_skill_level,
            naval_skill_level=naval_skill_level,
            has_naval_hug_coastline=False,
            auto_board=False,
            enforce_transport_legality=enforce_transport_legality,
        )
        army_ids = [army_id for army_id in army_ids if army_id not in straggler_ids]
        armies = [state.armies[army_id] for army_id in army_ids]

    # Phase 720: a mixed stack (a sea-going carrier present alongside
    # land units) still qualifies for the whole-group hop when every
    # land-type army in it ended up boarded by the auto_board pass
    # above (SS106's own capacity-allocation rule) -- guaranteed true by
    # construction for the narrowed `armies` once Phase 763's own split
    # above has already carved the unboarded stragglers out of it. A
    # pure land stack has no army needing transported_by at all, so this
    # is vacuously satisfied, unchanged from before.
    is_hug_coastline_hop = hug_coastline_geometrically_eligible and (
        not any(army.army_type in SEA_ARMY_TYPES for army in armies)
        or all(army.transported_by is not None for army in armies if is_land_army(army.army_type))
    )
    if current != target and not is_adjacent(current, target, bounds) and not is_hug_coastline_hop:
        next_hex = step_toward_non_adjacent_target(
            current, target, bounds, lambda c: _classify_hex_ownership(state, kingdom_id, c)
        )
        if next_hex is None or next_hex == current:
            return MoveExecutionResult(
                moved=False,
                battle_report=None,
                exploration=None,
                movement_points_spent=0,
                new_location=None,
                reached_target=False,
                stopped_chasing=True,
                wind_walking=wind_walking,
            )
        actual_target = next_hex
        reached_target = False
    else:
        actual_target = target
        reached_target = True

    target_province = state.provinces.get(actual_target)
    if target_province is None:
        raise ValueError(f"no province data for {actual_target}")

    # Phase 1026 -- RULES.AK [8.1]'s own Neutral-relation move block (see
    # MoveExecutionResult.blocked_by_neutral_relations's own docstring).
    # Deliberately checks ``diplomatic_relations`` directly, NOT the
    # lenient ``GameState.diplomatic_relation()`` query (whose own
    # "missing pair reads Neutral" default is correct for turn-1 RULES.AK
    # [8] semantics but would silently make every pre-existing Kingdom
    # pair in this project's entire test suite -- and any production
    # `GameState` built before a world-generation Phase explicitly
    # initializes this field -- Neutral too, blocking movement nothing
    # before this phase ever gated): only a pair this project's own
    # `turn/diplomacy.py apply_treat_orders()` (or a future world-gen
    # initializer / GM editor) has *actually written* a Neutral entry for
    # is blocked here. A pair with no entry at all keeps today's
    # pre-existing behavior unchanged (attackable, the same "not Allied"
    # default every other `is_allied()` caller already uses). Checked
    # before any other state mutation below (exploration, movement-point
    # cost, conquest, battle).
    if (
        armies
        and target_province.owner_kingdom_id is not None
        and target_province.owner_kingdom_id != kingdom_id
        and state.diplomatic_relations.get(frozenset({target_province.owner_kingdom_id, kingdom_id}))
        is DiplomaticRelation.NEUTRAL
    ):
        return MoveExecutionResult(
            moved=False,
            battle_report=None,
            exploration=None,
            movement_points_spent=0,
            new_location=None,
            reached_target=False,
            stopped_chasing=True,
            blocked_by_neutral_relations=True,
            wind_walking=wind_walking,
        )

    # Phase 754: snapshotted *before* an uncontested-conquest branch
    # below can overwrite `target_province.owner_kingdom_id` -- "foreign
    # territory" (MOVE.md section 21.3) means whoever owned it at the
    # moment of entry, not whoever owns it after this same call's own
    # conquest effect (see `entered_foreign_illusory_fog`'s own
    # computation near the end of this function).
    target_owner_before_move = target_province.owner_kingdom_id

    origin_province = state.provinces.get(current)
    origin_contested_by_mover = origin_province is not None and origin_province.contested_by_kingdom_id == kingdom_id
    target_owner_is_enemy = target_province.owner_kingdom_id is not None and not state.is_allied(
        target_province.owner_kingdom_id, kingdom_id
    )
    if is_illegal_move_from_contested(origin_contested_by_mover, target_owner_is_enemy):
        raise IllegalMoveFromContestedError("illegal to move from a contested province to an adjacent enemy province")

    if enforce_transport_legality and armies:
        transport_reason = find_transport_illegality(
            armies,
            army_ids,
            origin_province,
            target_province,
            has_march_through_floods=has_march_through_floods,
            is_hug_coastline_hop=is_hug_coastline_hop,
        )
        if transport_reason is not None:
            raise TransportIllegalMoveError(transport_reason, origin_coord=current, destination_coord=actual_target)

    defenders_present = [
        army
        for army in state.armies_at(actual_target)
        if army.kingdom_id is not None and is_attackable_at(state, army.kingdom_id, kingdom_id, target_province)
    ]
    occupied_by_enemy = bool(armies) and bool(defenders_present)

    move_result = resolve_move(
        current,
        actual_target,
        bounds,
        target_terrain=target_province.effective_terrain(),
        target_explored_percent=target_province.explored_percent,
        explorer_skill=explorer_skill,
        occupied_by_enemy=occupied_by_enemy,
        has_military_maps=has_military_maps,
        has_difficult_terrain=has_difficult_terrain,
        require_adjacent=not is_hug_coastline_hop,
    )
    target_province.explored_percent = move_result.exploration.new_percent
    record_kingdom_exploration(
        target_province,
        kingdom_id,
        explorer_skill,
        partial=True,
        state=state,
        rng=rng,
        has_military_maps=has_military_maps,
        has_difficult_terrain=has_difficult_terrain,
        has_find_mines=has_find_mines,
        leader_id=leader_id,
    )
    reveal_adjacent_provinces(state, target_province, kingdom_id, bounds)

    # Phase 541 -- Map of the Marauders "+1 hex to sea vision during
    # movement" (AKGEN_reverse_engineering_report (4).md SS11), a
    # **declared-original** mechanic, not reverse-engineered: this
    # project has no hex-radius vision/scouting concept anywhere to hook
    # a literal "+1 hex vision" into (exploration is purely a per-
    # province cumulative percentage). The closest honest mechanical
    # translation, reusing existing infrastructure rather than inventing
    # a new "visible hex" registry: a leader holding the item who just
    # entered a sea province also extends their own kingdom's partial-
    # exploration credit one hex further, to whichever sea neighbor of
    # the entered hex isn't the one just left (an approximation of
    # "continuing the same direction of travel" -- this call site has no
    # clean direction vector available, only the two endpoints).
    if leader_id is not None and target_province.effective_terrain() is Terrain.SEA:
        leader = state.leaders.get(leader_id)
        if leader is not None and any(
            item.treasure is Treasure.NAMED_UNIQUE_MAP_MARAUDERS for item in state.items_held_by(leader_id)
        ):
            for further_hex in neighbors(actual_target, bounds):
                if further_hex == current:
                    continue
                further_province = state.provinces.get(further_hex)
                if further_province is not None and further_province.effective_terrain() is Terrain.SEA:
                    record_kingdom_exploration(
                        further_province,
                        kingdom_id,
                        explorer_skill,
                        partial=True,
                        state=state,
                        rng=rng,
                        has_military_maps=has_military_maps,
                        has_difficult_terrain=has_difficult_terrain,
                        has_find_mines=has_find_mines,
                        leader_id=leader_id,
                    )
                    reveal_adjacent_provinces(state, further_province, kingdom_id, bounds)
                    break

    battle_report = None
    conquered = False
    if occupied_by_enemy:
        # Phase 736: snapshot army types *before* fight_battle() removes
        # any of them -- apply_battle_carrier_destruction() needs the
        # carrier's own type to record a real sinking event, but the
        # carrier is already gone from state.armies by the time it runs.
        army_types_before_battle = {army.army_id: army.army_type for army in state.armies.values()}
        battle_report = fight_battle(
            state,
            kingdom_id,
            actual_target,
            army_ids,
            loser_retreats=loser_retreats,
            attacker_origin=current,
            apply_fanaticism=True,
            use_real_duel_combat=True,
            rng=rng,
        )
        # Phase 716: the cargo sinks with the carrier.
        apply_battle_carrier_destruction(
            state,
            battle_report.destroyed_army_ids,
            battle_report.disbanded_army_ids,
            battle_report.pursuit_destroyed_army_ids,
            coord=actual_target,
            army_types_before_battle=army_types_before_battle,
        )
        conquered = battle_report.conquered
        moved = conquered
    else:
        moved = True
        # Phase 410 -- rulebook [7.7]: entering an enemy or unowned
        # province, uncontested (no defenders present at all -- a real
        # battle is handled above), still conquers it. `armies` (not
        # `army_ids`) gates this on a genuine military presence, matching
        # [7.7]'s own framing ("a military unit... enters an enemy
        # province") -- a leader moving alone conquers nothing.
        needs_conquest = target_province.owner_kingdom_id is None or (
            target_province.owner_kingdom_id != kingdom_id
            and not state.is_allied(target_province.owner_kingdom_id, kingdom_id)
        )
        if armies and needs_conquest:
            target_province.owner_kingdom_id = kingdom_id
            conquered = True

    cost = movement_cost_for_move(
        battle_occurred=occupied_by_enemy,
        conquered=conquered,
    )

    # Phase 651, Illusory Fog's own [3.11]-addendum text: "must expend 1
    # additional movement point when entering or leaving it" -- either
    # province being fogged triggers the surcharge (origin_province is
    # already resolved above); "the movement point is deducted after the
    # unit(s) have already moved," the same "may wind up with negative
    # movement points" convention turn/conquest.py's own module docstring
    # already established for the conquest/sea-battle surcharges -- kept
    # as a separate, per-army-type deduction rather than folded into
    # `cost` above, since (unlike those two) it applies only to affected
    # units (`turn/cast_execution.py is_illusory_fog_affected_air_unit()`),
    # not the whole moving party uniformly.
    fog_affected_move = (origin_province is not None and origin_province.illusory_fog_active) or (
        target_province.illusory_fog_active
    )

    # Phase 693: AdvancedAbility.MARCH_THROUGH_FLOODS -- see module
    # docstring's own Phase 693 addendum. Gated on the acting leader's
    # own Advanced Ability, applied to every land army in the moving
    # party (this project has no per-army-type gate for it, unlike
    # Illusory Fog's own air-unit-only scope above).
    flood_affected_move = has_march_through_floods and (
        (origin_province is not None and is_flooded_province(origin_province)) or is_flooded_province(target_province)
    )

    for army_id in army_ids:
        army = state.armies.get(army_id)
        if army is None:
            continue  # destroyed in the battle
        # Phase 715: an army actually being carried this move (boarded,
        # by this call or an earlier one, onto a carrier also part of
        # this same move) spends none of its own movement points --
        # rulebook: "cannot use a land movement point and be
        # transported... in the same turn" -- only its carrier pays.
        carried_this_move = army.transported_by is not None and army.transported_by in army_ids
        if not carried_this_move:
            if not army.march_bonus_applied_this_turn and is_land_army(army.army_type):
                bonus = march_movement_point_bonus(
                    army.movement_points,
                    has_march_cavalry=has_march_cavalry,
                    has_march_cavalry_mastery=has_march_cavalry_mastery,
                    has_march_cavalry_true_mastery=has_march_cavalry_true_mastery,
                    has_march_infantry=has_march_infantry,
                    has_march_infantry_mastery=has_march_infantry_mastery,
                )
                if bonus:
                    army.movement_points += bonus
                    army.march_bonus_applied_this_turn = True
            if not army.naval_bonus_applied_this_turn and army.army_type in SEA_ARMY_TYPES:
                naval_bonus = naval_movement_point_bonus(naval_skill_level)
                if naval_bonus:
                    army.movement_points += naval_bonus
                    army.naval_bonus_applied_this_turn = True
            # Phase 764: [4.12] MARCH TABLE's own separate, raw-skill-level
            # bonus -- stacks with march_movement_point_bonus() above, see
            # march_table_extra_movement()'s own docstring for why the two
            # are genuinely distinct, separately-sourced mechanics.
            if not army.march_table_bonus_applied_this_turn and is_land_army(army.army_type):
                army_stats = ARMY_TABLE.get(army.army_type)
                table_bonus = march_table_extra_movement(
                    march_skill_level, army_stats.speed if army_stats is not None else 1
                )
                if table_bonus:
                    army.movement_points += table_bonus
                    army.march_table_bonus_applied_this_turn = True
            army.movement_points -= cost
            if fog_affected_move and is_illusory_fog_affected_air_unit(army.army_type, mystic_winds_active_for(army, state)):
                army.movement_points -= ILLUSORY_FOG_EXTRA_MOVEMENT_COST
            if flood_affected_move and is_land_army(army.army_type):
                army.movement_points -= MARCH_THROUGH_FLOODS_EXTRA_MOVEMENT_COST
        if moved and army.location == current:
            army.location = actual_target

    if leader_id is not None and moved:
        leader = state.leaders.get(leader_id)
        if leader is not None and leader.location == current:
            leader.location = actual_target

    # Phase 715: cargo left behind when its carrier moves without it
    # this same call (the carrier's own id is in army_ids, but the
    # cargo's own isn't) -- disembarked, not silently left "aboard" a
    # carrier that's now elsewhere.
    for army_id in army_ids:
        carrier = state.armies.get(army_id)
        if carrier is None or carrier.army_type not in _CARRIER_ARMY_TYPES:
            continue
        for cargo in cargo_aboard(state, army_id):
            if cargo.army_id not in army_ids:
                disembark_army(state, cargo.army_id)

    # Phase 754: ADDEND.AK [3.6] "Wandering Mercenaries", real mechanism
    # (see this module's own Phase 754 addendum) -- the general genuinely
    # has to have departed the origin (`moved`) for anyone to follow, and
    # his own main contingent needs at least one army with positive
    # movement points left ("non basta la sola presenza del generale");
    # an armyless leader (`army_ids=[]`) therefore never triggers this.
    followed_mercenary_army_ids: list[int] = []
    if (
        moved
        and leader_id is not None
        and army_ids
        and any(state.armies[aid].movement_points > 0 for aid in army_ids if aid in state.armies)
    ):
        followed_mercenary_army_ids = resolve_wandering_mercenary_following(
            state, current, actual_target, origin_province, target_province
        )

    # Phase 754: `Desktop/MOVE.md` section 21.3 -- raw `0xB31A-0xB54A`
    # runs only when the leader's own Kingdom genuinely differs from the
    # destination's real owner; its own `1000h` bit-field branch fires
    # this note (real text, `_SANote` for `C_IF=56`) whenever that
    # foreign province is under an active Illusory Fog. Modeled as
    # firing unconditionally on that entry, independent of the moving
    # contingent's own army composition -- the document's own "contains
    # wings OR the owner differs" phrasing is a disjunction where the
    # second disjunct is already guaranteed true by the surrounding
    # foreign-owner gate, so it reduces to "always" inside this branch,
    # not a real additional restriction to reproduce.
    entered_foreign_illusory_fog = bool(
        moved
        and leader_id is not None
        and target_owner_before_move is not None
        and target_owner_before_move != kingdom_id
        and target_province.illusory_fog_active
    )

    # Phase 768: Move-triggered March/Naval experience credit -- see
    # `MOVE_MARCH_NAVAL_EXPERIENCE_BASE_POINTS`'s own citation above and
    # this function's own Phase 768 addendum for the full gating. Gated
    # on `moved` (this call's own real hex-step), a real leader
    # commanding at least one army in this same move, and excluding a
    # majority-air-or-air-transportable force -- a real, independent
    # formula (Phase 819 correction: NOT the same test the `_LFly`/wind-
    # walking narration branch uses, see this function's own Phase 768
    # addendum above) -- reproduces the real engine's own per-phase
    # re-dispatch faithfully rather than under/over-counting a
    # multi-phase chase. The Phase 763 straggler recursive call above
    # passes `leader_id=None`, so it's excluded here with no special
    # casing needed. `rng` is never actually `None` here -- the top of
    # this function already substitutes a fresh `random.Random()` for a
    # caller that omits it.
    naval_advanced_ability_granted: AdvancedAbility | None = None
    march_advanced_ability_granted: AdvancedAbility | None = None
    if moved and leader_id is not None and armies:
        air_count = sum(1 for army in armies if army.army_type in OVERFLIGHT_AIR)
        if 2 * air_count < len(armies):
            mover_leader = state.leaders.get(leader_id)
            if mover_leader is not None:
                is_sea_move = (origin_province is not None and origin_province.effective_terrain() is Terrain.SEA) or (
                    target_province is not None and target_province.effective_terrain() is Terrain.SEA
                )
                move_experience_ability = Ability.NAVAL if is_sea_move else Ability.MARCH
                outcome = add_experience(mover_leader, move_experience_ability, MOVE_MARCH_NAVAL_EXPERIENCE_BASE_POINTS, rng)
                # Phase 787: since Phase 644, Practicing Naval no longer
                # raises the leader's own personal Naval skill at all
                # (routed to `execute_practice_tactical()` instead) --
                # this Move-triggered credit is the ONLY real, reachable
                # trigger for a Naval `AdvancedAbility` grant. See
                # `worldgen/naval_ability_level_schedule.py`'s own module
                # docstring for the real, empirically-verified schedule
                # and its accepted `SA_Num`/`SA_Mod` under-count scope.
                if move_experience_ability is Ability.NAVAL and outcome.skill_rose:
                    naval_advanced_ability_granted = build_naval_ability_level_schedule(state.game_number).get(
                        outcome.new_skill
                    )
                    if naval_advanced_ability_granted is not None:
                        mover_leader.advanced_abilities.add(naval_advanced_ability_granted)
                # Phase 901: the identical treatment for March, previously
                # missing -- `Ability.MARCH` has no personal-Practice
                # trigger either (never in `_ARMY_TRAINING_ABILITIES`),
                # so this Move-triggered credit is its own only real,
                # reachable trigger too. See `worldgen/march_ability_
                # level_schedule.py`'s own module docstring for why its
                # schedule needs no `game_number` at all.
                elif move_experience_ability is Ability.MARCH and outcome.skill_rose:
                    march_advanced_ability_granted = build_march_ability_level_schedule(state.game_number).get(
                        outcome.new_skill
                    )
                    if march_advanced_ability_granted is not None:
                        mover_leader.advanced_abilities.add(march_advanced_ability_granted)

    return MoveExecutionResult(
        moved=moved,
        battle_report=battle_report,
        exploration=move_result.exploration,
        movement_points_spent=cost,
        new_location=actual_target if moved else None,
        reached_target=reached_target,
        stopped_chasing=False,
        conquered=conquered,
        wind_walking=wind_walking,
        boarded_army_ids=boarded_army_ids,
        followed_mercenary_army_ids=followed_mercenary_army_ids,
        entered_foreign_illusory_fog=entered_foreign_illusory_fog,
        straggler_result=straggler_result,
        moved_without_armies=moved_without_armies,
        naval_advanced_ability_granted=naval_advanced_ability_granted,
        march_advanced_ability_granted=march_advanced_ability_granted,
    )
