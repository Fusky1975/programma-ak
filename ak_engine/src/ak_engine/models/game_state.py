"""Persistent, mutable game-state containers.

Every module through Phase 8 operates on caller-supplied snapshots (lists
of ``BattleUnit``, raw ``HexCoord``/``MapBounds`` parameters, etc.) -- none
of them remember anything across calls. This module is the first actual
session state: kingdoms, armies, and provinces that persist across turns
and battles, for ``turn/battle_orchestrator.py`` to read and mutate.

Intentionally minimal -- just enough to orchestrate a battle end-to-end
and (as of Phase 14) track which leader commands which army. Not a full
game database: ``LeaderState`` here is a persistent, minimal stand-in
for a character's position and command relationships -- it does NOT
carry Phase 1's parsed ``ActionPlan`` (``models.kingdom.Leader`` is a
parsed *move submission*, a different concept from the persistent
leader here; the two are linked only by sharing a ``leader_id``). No
diplomacy/treaty tracking beyond a flat alliance set, no turn-history
log.

``LeaderState.skills`` (Phase 30) reuses ``models/kingdom.py``'s
already-resolved ``SkillTable``. ``skills`` defaults to ``None`` ("no
ability data recorded for this leader"), and every consumer
(``turn/battle_orchestrator.py``'s Tactical/Naval strength bonus and
Duel commander selection, ``turn/cast_execution.py``'s Cast success
roll) falls back to its pre-Phase-30 placeholder behavior in that case
-- a real skill level only changes anything once it's set.

``turn/kingdom_bridge.py`` (Phase 31) is the one piece of code that sets
it from real data: given a parsed ``Kingdom`` (Phase 1) and a
``GameState`` that **already has** matching ``LeaderState``s (created by
whatever turn-0 setup the caller already did), it attaches the King's
real ``SkillTable`` to his ``LeaderState`` and syncs everyone's
``kingdom_id``. It's deliberately narrow: a move file carries no
location/race/alignment/treasury for anyone, so it can only enrich
``LeaderState``s that already exist, never create a ``KingdomState`` or
a new ``LeaderState`` from nothing -- see that module's docstring for
why. Building the missing piece (populating a brand-new ``GameState``
from turn 0, with no existing entries to enrich) remains a distinct,
unsolved, larger future task.

``ArmyState.kingdom_id`` is nullable (Phase 16): ``None`` means an
unowned mercenary army (rulebook [3.6]: Disband "releases the army(s)
into mercenary status... will wander around as unemployed mercenaries
until hired"). ``is_allied()`` treats ``None`` as allied with nobody,
including another mercenary army -- two masterless bands aren't each
other's allies just because both have no owner.

``LeaderState.kingdom_id`` is nullable too (Phase 17), same convention:
``None`` means an independent Hero, not yet in anyone's service (rulebook
[3.5] Hire, [3.7] Fire: "The Hero will wander around until hired by
another King").

``LeaderState.is_king`` (Phase 40) is the King/Hero distinction earlier
phases repeatedly flagged as missing (Disband [3.6], Fire [3.7], Hire
[3.5] all give a King broader authority than an ordinary Hero -- see
``turn/plan_dispatch.py``). Defaults to ``False``, same "no data yet"
convention as ``skills``: a hand-built ``LeaderState`` in a test is a
Hero unless the caller says otherwise. ``turn/kingdom_bridge.py``
(Phase 31) is the one piece of code that sets it from real data,
reusing the same King-identification (name match against
``kingdom.king_name``) it already uses for ``skills``.

**Fields added for Phase 59's Cast spell execution** (``turn/
cast_execution.py``, Regolamento AK.txt [4.21]-[4.25]):

- ``GameState.dead_leaders`` is a graveyard: ``remove_leader`` now
  archives into it instead of discarding, so Resurrection has something
  concrete to revive. Only deaths that go through ``remove_leader``
  itself are archived -- any code that instead does
  ``state.leaders.pop(...)`` directly bypasses the graveyard (no such
  call site exists in this project as of Phase 59, confirmed by grep,
  but a future one should call ``remove_leader`` to stay resurrectable).
- ``ProvinceState.terrain_override`` (Part Sea, Flood): "for the rest of
  the turn" province-terrain replacement. Not auto-cleared at a turn
  boundary -- unlike ``recruited_this_turn``/``ArmyState.movement_
  points`` (which Phase 573's own ``turn/turn_processor.py
  _replenish_turn_scoped_state()`` now resets every ``run_turn()`` call),
  this field still has no reset call anywhere. **Stale as of Phase 683 --
  as of Phase 59 this had no consumer, but ``ProvinceState.effective_
  terrain()`` (below) has read it since Phase 225/226, over 166 phases
  later** (already correctly noted where `MeritTally`'s own analogous
  fields are discussed, further down in this file -- nobody had gone
  back to fix the claim at its own original site until now).
- ``ProvinceState.tax_modifier_percent`` (Bless, Earthquake): a signed
  percent (+60 / -100, matching each spell's exact rulebook number, and
  each spell *sets* rather than adds since both are documented "not
  cumulative"). **Stale as of Phase 683 -- as of Phase 59 no tax/
  revenue-collection system existed anywhere in this project, so this
  field had no consumer; ``turn/tax_base.py compute_tax_base()`` has
  read it since Phase 412/222-224.**
- ``ProvinceState.illusory_terrain`` (Illusory Terrain): the fake
  terrain an outside observer would be told the province is. **Stale as
  of Phase 683 -- as of Phase 59 nothing read this; `report/turn_
  report.py record_spell_world_events()` has rendered a real world-
  event narration line from it since Phase 232.** As of **Phase 724**,
  this is also a real gameplay effect, not just narration: `turn/
  strength.py compute_effective_strength()`'s own `illusory_terrain`
  parameter blends real/illusory combat strength for a unit that enters
  (rulebook [4.23.1]), and `turn/cast_execution.py maybe_dissolve_
  illusory_terrain()` clears this field on a real 15%/turn roll, called
  once per turn from `turn/turn_processor.py run_turn()`.
- ``LeaderState.phantasmal_armies_level`` (Phantasmal Armies): unlike
  the three fields above, this one *is* wired into a real consumer the
  same phase it's added -- see ``turn/strength.py
  phantasmal_armies_multiplier`` and ``turn/battle_orchestrator.py``'s
  ``_build_battle_units``.
- ``LeaderState.oratory_boosted_this_turn`` (Oratory): Oratory's effect
  (bump every commanded army's ``Quality`` one rank) is applied directly
  and immediately rather than stored as a multiplier, since ``Quality``
  is already a first-class field every strength calculation reads. This
  flag exists purely so a second Oratory cast on the same leader the
  same turn is the required "not cumulative" no-op instead of bumping
  rank twice; cleared to ``False`` at the end of every ``run_turn()``
  call (Phase 573's own ``_replenish_turn_scoped_state()``) -- this
  paragraph is Phase 59-era and predates that fix.
- ``LeaderState.clairvoyance_watchers`` (Clairvoyance [4.22.3], Phase
  193): the rulebook's own confirmed sentence ("for the rest of the
  turn, the caster knows everything that happens to the target",
  corroborated word-for-word by ``models/power.py
  CAST_SPELL_FEATURE_DESCRIPTION``'s "everything he does for the rest
  of the turn will be known to you") only ever names *who* gets to
  know, never *how* that knowledge reaches them -- no per-character
  event feed exists anywhere in this project to actually surface "what
  the target did this turn" to a watching kingdom. This field records
  only the confirmed half: which kingdom id(s) currently hold a
  successful watch on this leader. A successful cast adds the caster's
  own ``kingdom_id`` here; nothing yet reads the set (same "spell
  writes real state, nothing reads it yet" situation as
  ``terrain_override``/``illusory_terrain`` above). Not auto-cleared at
  a turn boundary -- unlike ``oratory_boosted_this_turn`` (fixed by
  Phase 573), this field has no real reader (see the Phase 408 addendum
  right below), so there is no live mechanic for a stale value to break.
  **Phase 408 addendum**: the real mechanism that would have surfaced
  this to the watcher was found and traced all the way down --
  ``RUMORS.PAS Set_Intel(x,y)``'s own Clairvoyance/``Counter_Science``
  block, the thing that would grant the caster's kingdom `S_Priv`-tier
  ("everything") visibility on the target -- and it turned out to be
  dead code: its only call site is inside a branch its own author
  marked "no longer in use" and gated behind a debug halt, unreachable
  from every caller in the available archive. See ``turn/world_events.py``'s
  own module docstring for the full citation trail. This field
  therefore stays exactly as Phase 193 left it, now with a confirmed
  reason no reader will be built: not "not yet implemented," but "the
  sourced mechanism is dead code."

**Gate Angel / VALHALLA fields (Phase 194, corrected Phase 195)**: a
secret spell (``AdvancedAbility.GATE_ANGEL_SPELL``, ordinal 25, outside
the 25 documented ``Spell`` members) whose rule text the user supplied
directly, then substantially extended in a follow-up message describing
the real VALHALLA mechanic it draws its hero from. See ``turn/
cast_execution.py``'s own module docstring ("Secret spells" section)
for the full rule text and design rationale; summarized here:

- ``gate_angel_cycle_visited: set[Alignment]``: which of the 5
  ``turn/cast_execution.py GATE_ANGEL_ELIGIBLE_ALIGNMENTS`` (Good,
  Druid, Neutral, Pagan, Evil -- explicitly *not* Divine or Undead,
  per "Ciascun allineamento da Buono a Malvagio (quindi non Divine o
  Undead)... I re Non-Morti e Divini... non ricevono visite dal
  Vahlalla") have already been visited in the current 5-turn rotation
  cycle; cleared once all 5 have had their turn.
- ``gate_angel_due_alignment``/``gate_angel_due_alignment_turn``: this
  turn's randomly-chosen due alignment (see
  ``_gate_angel_due_alignment()``), cached once per ``turn_number`` so
  multiple same-turn casters all see the same answer -- **replaces**
  Phase 194's original ``gate_angel_alignment_cooldown: dict[Alignment,
  int]`` (an independent-per-alignment 5-turn cooldown), which modeled
  the wrong mechanic; the real rule is a rotating *exclusion* cycle
  over exactly 5 alignments, not an independent cooldown per alignment,
  and Divine/Undead never participate at all (not "folded into"
  Good/Evil's own slot, as Phase 194 had incorrectly modeled).
- ``gate_angel_candidates_this_turn: int``: reservoir-sampling counter
  (see ``_gate_angel_register_candidate()``) -- how many successful
  due-alignment casters have been seen so far this turn, used to give
  every one of them a uniformly random ``1/N`` chance of being *the*
  visit, honoring "se c'è più di un giocatore in un allineamento, la
  scelta verrà fatta a caso" / "If more than one player casts the Gate
  Angel spell, one of the spells will be nullified" without new
  end-of-turn batch-resolution machinery.
- ``last_gate_angel_turn``/``last_gate_angel_kingdom``: the *current*
  reservoir winner -- unlike every other per-turn flag in this
  dataclass (each scoped to one leader/army/province), this is a
  genuinely *global* fact, and may be overwritten more than once within
  a single turn as later candidates win the reservoir swap; the value
  after a turn's dispatch fully completes is authoritative.

**Phase 386 correction**: the field comment above still says
"reservoir winner" for historical continuity, but ``_gate_angel_
register_candidate()`` no longer actually does reservoir sampling --
AKGEN's own confirmed rule is simpler and non-uniform (see that
function's own docstring). ``valhalla_visitor_sequence`` (below) is new
this phase, backing the real post-turn-5 visitor-selection algorithm in
``turn/valhalla_execution.py``.

**Phase 196 addendum -- the user supplied all 5 per-alignment roster
files** (``models/valhalla.py VALHALLA_ROSTER``, 137 named heroes
total), unblocking real hero synthesis: ``turn/valhalla_execution.py
finalize_gate_angel_visit()`` now builds a genuine ``LeaderState`` (a
random pick from the winning turn's due-alignment roster) once the
reservoir-sampling winner is final. This is the reason
``LeaderState.race`` exists (see that field's own comment below) -- a
VALHALLA visitor's race is independent of the Kingdom they join, unlike
every other leader in this project.

**``GameState.battle_graveyard`` (Phase 60)**: rulebook (Regolamento
AK.txt [4.25.1]/addendum): Skeletal Army needs to know "an army was
destroyed in a battle fought in this province," and the Bless addendum
("now also removes dead units from a province") needs the same fact to
act on -- both were left unmodeled in Phase 59 for exactly this missing
registry. ``GraveyardEntry`` records only what Skeletal Army's own
rulebook text says matters (the dead unit's ``ArmyType`` and ``Quality``
at death -- "identical to the dead army") plus ``kingdom_id`` for
reference; ``GameState.record_battle_death()`` appends one per
destroyed army. **Populated only from genuine battle deaths**
(``turn/battle_orchestrator.py``'s four real destruction sites: a
retreat with nowhere to go, a post-battle pursuit kill, and a clean-swept
side's own elimination), **not** from a spell directly destroying units
(Tornado, Plague in ``turn/cast_execution.py``) -- the rulebook's own
wording is specifically "battaglia" (battle), and a spell isn't one.
Entries aren't turn-stamped (nothing else in this project tracks battle
recency either) and aren't automatically pruned -- the rulebook's
own "roughly 10%/turn decomposition past a 350-unit world cap" is a
soft world-balance rule this project doesn't enforce (would need a
live global army count and a turn-scheduled decay pass, out of scope
for spell execution).

**Phase 309 addendum -- the 350-cap decay above is now enforced.**
`Regolamento AK.txt` [4.2.5] (quoted in full): "Il numero totale di
unità militari consentito nel gioco (sia viventi che morte) è di 350,
perciò dopo le prime fasi, a ogni turno un 10% circa delle unità
distrutte in precedenza è destinato alla decomposizione. Quando si
supera il limite di 350, le unità distrutte da più lungo tempo si
decompongono automaticamente." `turn/skeletal_decay.py
decompose_graveyard()` implements this: the world total is `len(state.
armies)` ("viventi" -- every currently-live army, including an already-
risen, still-commanded Skeletal Army, see that module's own docstring
for why a risen army never itself decomposes) plus every
`battle_graveyard` entry ("morte" -- destroyed, not yet raised); once
that total exceeds 350, roughly 10% of the graveyard's own entries
decompose (removed permanently, no longer raisable), oldest-destroyed
first. `GraveyardEntry.death_seq` (new field below) and
`GameState.graveyard_death_counter` close the "entries aren't turn-
stamped" gap noted above -- not a real turn number, just a monotonic
insertion-order counter, exactly enough to answer "which of these died
longest ago" without inventing a broader turn-history log this project
doesn't otherwise keep.

**``ProvinceState.explored_percent_by_kingdom`` (Phase 69)**: `RULES.AK`'s
[6.3] "ARMY STRENGTH NOTES" (quoted in full): "The side with the better
exploration of the contested province will also have up to a 25%
advantage, if they have explored 100% of the province and the other
side has not explored it." `turn/strength.py
exploration_advantage_multiplier` has implemented this formula since
Phase 9, but `turn/battle_orchestrator.py` could never call it with
real data -- the pre-existing `explored_percent` field above is a
*single* scalar per province, with no way to ask "how much has *this*
kingdom specifically explored it" (a structural gap documented since
Phase 35). This new field is purely additive: every write site that
already updates `explored_percent` (`turn/move_execution.py
execute_move`, `turn/plan_dispatch.py`'s EXPLORE branch, `turn/
turn_processor.py`'s multi-attacker LMOVE branch) now *also* records
each acting kingdom's own cumulative percentage here, independently
seeded from that kingdom's own prior entry (default 0), via
`turn/move_execution.py record_kingdom_exploration()`. **A kingdom
that owns a province is not automatically seeded at 100%** -- there is
no data anywhere in this project for "how long has this kingdom held
it" or "did they explore it before this simulation's own tracked
history began," and guessing either would contradict this project's
own no-guessing convention; a longtime owner who never issued an
explicit Explore/Move-into order into their own province in a
recorded turn reads as 0% here, same as anyone else with no history.
Missing entries for *both* sides default to 0, which
`exploration_advantage_multiplier(0, 0)` reads as no advantage either
way -- a neutral, not a guessed, default.

**"Known provinces" (Phase 623)**: the user specified this concept
directly (not from a reverse-engineering source): a province is
"known" to a Kingdom once that Kingdom has at least `KNOWN_PROVINCE_
MIN_PERCENT` (1%) recorded exploration of it -- reusing `Province
State.explored_percent_by_kingdom` (Phase 69, above) rather than a new
field, since that field already tracks exactly the right per-kingdom
quantity. `ProvinceState.known_to_kingdom()` is the query side.
`turn/move_execution.py reveal_adjacent_provinces()` is the write
side: entering a province reveals its own neighbors at exactly this
1% floor (the province actually entered already gets far more than 1%
from the pre-existing partial-exploration formula, confirmed by
reading `turn/exploration.py resolve_explore()`'s own numbers -- the
smallest possible partial result, Jungle at skill 0, is 5). This
closes the tracking gap `Power.MAP_PROV`'s own Phase 616 addendum
flagged as missing (`turn/feature_power_execution.py`).

**`LeaderState.is_comatose` (Phase 310)**: Kill_Enemy's own [4.25.2]
Action-cast alternative to killing the target outright -- see
`turn/cast_execution.py _execute_kill_enemy()`'s own Phase 310
addendum for the full sourced quote and design reasoning, and this
field's own docstring below for exactly what being comatose changes
(every ability reads 0, Practice is blocked, but every other action
stays available) and how it's cured (a Resurrection cast, which -- the
one deliberate divergence from an ordinary dead-Hero revival -- never
changes `kingdom_id`, even cast by a foreign hero/King).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ak_engine.models.advanced_ability import AdvancedAbility
from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.discovery import Discovery
from ak_engine.models.enums import Ability
from ak_engine.models.feature import Feature, RaidEvent
from ak_engine.models.game_type import GameType
from ak_engine.models.item import ItemInstance
from ak_engine.models.kingdom import SkillTable
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.office import Office
from ak_engine.models.race import Race
from ak_engine.models.rumor import Rumor
from ak_engine.models.sex import Sex
from ak_engine.models.temper import Temper
from ak_engine.models.treasure import Treasure
from ak_engine.turn.combat import Quality
from ak_engine.turn.search_decode import SearchTactic


@dataclass(slots=True, frozen=True)
class BlackmailClaim:
    """One outstanding `AdvancedAbility.SPY_BLACKMAIL` demand against a
    Kingdom -- see `turn/blackmail.py`'s own module docstring (Phase
    713) for the full mechanic. `spy_leader_id`/`spy_kingdom_id`
    identify who is owed; `amount` is the real gold figure that was
    demanded (already adjusted for the target's own alignment/treasury
    and the spy's own halving-on-non-payment history at the moment the
    demand was made).
    """

    spy_leader_id: int
    spy_kingdom_id: int
    amount: int


@dataclass(slots=True)
class KingdomState:
    kingdom_id: int
    name: str
    race: Race
    alignment: Alignment
    home_province: HexCoord
    treasury: int = 0
    # Sage's "Discoveries" (Phase 266) -- CTBOTH.PAS's own `dknow` is a
    # per-kingdom `array[discovery] of boolean` ("does this kingdom know
    # this Discovery"), never a count or per-leader value, so a plain
    # per-kingdom set matches the real data shape exactly. See
    # `turn/practice_execution.py`'s own module docstring (Phase 266) for
    # how a Discovery gets added here.
    discoveries: set[Discovery] = field(default_factory=set)
    # Phase 702 (AdvancedAbility.THIEF_TREASURY_RAIDS): "the guard is
    # doubled for that kingdom against further attempts in the same
    # turn" -- a per-turn counter of how many Treasury Raid attempts
    # (successful or not) have already targeted this kingdom this turn,
    # consulted by `turn/challenge_execution.py _resolve_steal_tactic()`
    # to compute a cumulative `2 ** attempts` guard multiplier. Reset to
    # 0 by `turn/turn_processor.py _replenish_turn_scoped_state()`
    # (Phase 573), the same turn-boundary sweep every other "not auto-
    # reset -- the caller's job" field in this project uses.
    treasury_raid_attempts_this_turn: int = 0
    # Phase 713 (AdvancedAbility.SPY_BLACKMAIL): mirrors the real parsed
    # `GWKingExtension.pending_blackmailer_king_id`/`active_blackmailer_
    # king_id` field PAIR exactly (`parser/gw_world.py`) -- a demand
    # delivered this turn sits in `pending_blackmail` (not yet due);
    # `turn/blackmail.py advance_blackmail_claims()` promotes it into
    # `active_blackmail` (due this turn) at the very start of the next
    # `run_turn()` call. At most one live claim of either kind can exist
    # per Kingdom at a time -- this is also what implements the real
    # "usable once per turn on a kingdom" cap (no new demand can be
    # created while either is still set). See `turn/blackmail.py`.
    pending_blackmail: BlackmailClaim | None = None
    active_blackmail: BlackmailClaim | None = None


@dataclass(slots=True)
class ArmyState:
    army_id: int
    kingdom_id: int | None  # None = unowned mercenary
    army_type: ArmyType
    quality: Quality
    location: HexCoord
    # Reset to False at the end of every `run_turn()` call, alongside
    # `movement_points`'s own replenishment (Phase 573).
    unhireable_this_turn: bool = False
    # Remaining this gameturn. The dataclass default (0) is only ever seen
    # before this army's own first `run_turn()` call -- `worldgen.
    # generate_new_game()` sets a real freshly-created army's own initial
    # value to `ARMY_TABLE[army_type].speed`, and `turn/turn_processor.py
    # run_turn()`'s own end-of-turn `_replenish_turn_scoped_state()`
    # (Phase 573) refills every army back to that same real rate after
    # each turn's dispatch finishes. The one-time March/Naval movement
    # bonus (`turn/move_execution.py execute_move()`) still applies
    # dynamically on top of whatever this field holds when an army
    # actually moves, per rulebook [6.2]'s own "always calculated at the
    # moment an army moves" -- not folded into the replenished base rate.
    movement_points: int = 0
    # Which leader currently leads this army, if any (rulebook: an army may
    # also be unled, under the "garrison commander"). Set/cleared by
    # Leave/Pick_Up (turn/plan_dispatch.py); None means unled.
    commanded_by: int | None = None
    # Plague immunity (Phase 233) -- rulebook [4.25.3]: "If a unit
    # survives a plague, it's immunized from dying in future plagues (it
    # may instead drop a level in quality.)" Set the first time this army
    # is exposed to a Plague-destroy roll and survives
    # (`turn/cast_execution.py apply_plague_exposure()`); every later
    # exposure (a recast, or the spread mechanic reaching this army's own
    # province again) rolls a quality-downgrade chance instead of a
    # destroy chance.
    plague_immune: bool = False
    # Raised-as-skeletons marker (Phase 236) -- `CTBOTH.PAS:1260`'s own
    # `astate` enum (`Dead,Hired,Mercenary,Zomboid,Bold,Sold,Loser,Calm`)
    # has a `Zomboid` value that `REPORTS.PAS:988-992`'s real Army List
    # table checks to prepend " Skel " before the army-type designation
    # (`turn/army_naming.py make_army_display_name()`) -- confirmed
    # against real letter data (`SE3__T0.K1:135`, "108th Skel Bowmen").
    # No real `astate[an]:= Zomboid` assignment site exists anywhere in
    # the extracted source (grep across the full tree comes back empty,
    # the same "lost with the missing main driver" gap this project has
    # documented many times before) -- but `Zomboid`'s own name, the
    # literal "Skel" text tied to it, and `RUMORS.PAS:354`'s own
    # `lalign[armykng] = Undead` check alongside it all agree it marks an
    # army raised via the Skeletal_Army spell, so `turn/cast_execution.py
    # _execute_skeletal_army()` sets this field on every army it raises.
    is_skeletal: bool = False
    # Phase 521: AdvancedAbility.MARCH_CAVALRY/_INFANTRY (+ Mastery tiers)
    # -- rulebook [6.2]: "The increased army-movement allowed by the March
    # and Naval abilities is always calculated at the moment an army
    # moves." Granted at most once per gameturn by `turn/move_execution.py
    # execute_move()`'s own Phase 521 addendum, the first time this army
    # moves this turn under a March-ability-holding leader. Reset to
    # False at the end of every `run_turn()` call, alongside `unhireable_
    # this_turn`/`movement_points` (Phase 573).
    march_bonus_applied_this_turn: bool = False
    # Phase 523: the Naval sibling of `march_bonus_applied_this_turn` above --
    # AKGEN_reverse_engineering_report (3).md SS99's own `M_Skill(leader,
    # Naval)` movement bonus for Whale League/Fleet/Mermen, granted at most
    # once per gameturn by `turn/move_execution.py execute_move()`'s own
    # Phase 523 addendum. Reset the same way and at the same point as
    # `march_bonus_applied_this_turn` above.
    naval_bonus_applied_this_turn: bool = False
    # Phase 714 -- Fleet/Whale cargo-capacity subsystem: the carrying
    # Fleet/Whale's own `army_id`, or `None` if this army isn't
    # currently boarded on anything. Mirrors `commanded_by`'s own
    # nullable-int-cross-reference style; set/cleared by `turn/sea_
    # transport.py board_army()`/`disembark_army()`. Not kept in sync
    # with the carrier's own `location` as the carrier moves -- that's
    # real move-integration work, a separate, not-yet-started follow-up
    # (see `turn/sea_transport.py`'s own module docstring).
    transported_by: int | None = None


@dataclass(slots=True)
class MeritTally:
    """Cumulative, game-long inputs to the Imperial Office Merit Point
    formulas (Phase 227, ``turn/merit_points.py`` -- rulebook page 51's
    "TABELLA DELLE CARICHE IMPERIALI"). ``resurrection_bless_casts``
    (``turn/cast_execution.py``'s ``_execute_resurrection``/
    ``_execute_bless``, Phase 251), the four land/naval battle counters
    (``turn/battle_orchestrator.py _record_battle_merit()``, Phase 254),
    ``monster_hp_defeated`` (``turn/search_execution.py
    execute_search()``'s ``_outcome_from()``, Phase 255),
    ``features_discovered_first`` (``turn/plan_dispatch.py``'s own
    ``ActionCode.EXPLORE`` branch, Phase 256), ``monster_hp_neutralized``
    (a successful Fulfill, ``turn/search_execution.py
    _resolve_fulfill()``, Phase 258), and ``discoveries_via_espionage``
    (``turn/aspy_execution.py execute_aspy()``'s own espionage-Discovery
    roll, Phase 267) now have real writers.

    **Phase 271**: ``discoveries_found_first``/``discoveries_found_not_
    first`` are now live too, via ``GameState.discoveries_first_found_
    by`` (the global first-inventor registry this docstring's own prior
    note said was missing) -- see ``turn/practice_execution.py
    execute_practice()``'s own SAGE branch and ``turn/merit_points.py``'s
    own module docstring for the point values these two feed (a
    user-specified, project-original scoring rule, confirmed 2026-07-29,
    that supersedes the rulebook's own flat "+2 per Invention found
    first" figure -- see that module's own note).

    **Phase 369 correction**: `AKGEN_reverse_engineering_report.md`/
    `AKGEN_embedded_catalogs.json` (a real static disassembly of
    `AKGEN.EXE`/`AK.EXE`/`AK.OVR`, verified against the 12 `GW3__T1..
    T12` historical saves) proved `CARICHE E ABILITÀ.txt` -- the
    user-supplied source Phases 277/367/368 all built their own "cariche
    minori" formulas from -- does **not** match the real compiled
    formulas for King of Pain, Prince of Thieves, the 6 other
    alignment-King titles, Chief of Staff, or Silver Tongue. Every
    field those four phases added for those titles' own elaborate,
    now-disproven terms (`monsters_killed_in_realm_province`,
    `successful_thief_tactics`, `gold_stolen`, `magic_items_stolen`,
    the 3 alignment-filtered monster-kill counters, `ch_undead_
    transformations`, `military_units_recruited`, `alliances_formed`,
    `alliance_upkeep_points`, `discoveries_traded`) is removed here --
    see `turn/merit_points.py`'s own Phase 369 addendum for the real,
    disassembly-confirmed formulas that replace them (`successful_
    thefts`, `diplomatic_merit_points`, and plain `Tax_Base` reuse for
    all 7 alignment-King titles, no tally at all).

    All default to 0: a leader who has fought no battles,
    killed no monsters, cast no Resurrection/Bless, or been the first to
    find any Special Place/Discovery legitimately starts here, the same
    "field exists, no populating consumer yet" convention this project
    has used since Phase 59's own `tax_modifier_percent`/
    `terrain_override` (only wired up 166+ phases later, Phase 225/226).

    Two fields per office needing a win/loss split (Marshal, Admiral) are
    kept as separate won/lost totals rather than a single running total,
    so `turn/merit_points.py`'s own formula can apply the sign itself;
    pre-signing here would hide the raw totals a future battle-outcome
    wiring phase needs.

    **Phase 308**: these four fields were originally named `..._enemy_
    units`/`..._own_units` and held a flat per-unit count (`turn/
    merit_points.py`'s own original "+1 per enemy unit if won, -1 per
    own unit if lost" formula). Renamed to `..._points` now that
    `turn/battle_orchestrator.py _record_battle_merit()` sums a real,
    sourced quality-weighted table (`turn/merit_points.py
    MARSHAL_QUALITY_POINTS`/`battle_quality_points()`, Regolamento
    AK.txt's own "NUOVE REGOLE" appendix) instead of a flat +1/-1 per
    unit -- the old names would have silently misdescribed what these
    totals hold.
    """

    land_battles_won_points: int = 0
    land_battles_lost_points: int = 0
    naval_battles_won_points: int = 0
    naval_battles_lost_points: int = 0
    # Defender: monster Hit Points -- full for a kill, half (per the
    # rulebook's own "metà dei punti se neutralizzato con trattative")
    # for a monster talked/negotiated into stopping, applied by the
    # formula function itself so this field stays a real, unhalved HP
    # count.
    monster_hp_defeated: int = 0
    monster_hp_neutralized: int = 0
    # Priest: successful Resurrection or Bless casts (either spell, same
    # +1 each -- the rulebook doesn't distinguish between them).
    resurrection_bless_casts: int = 0
    # Chancellor: features_discovered_first is live as of Phase 256 (see
    # turn/plan_dispatch.py's own EXPLORE branch, keyed off Feature.
    # discovered_by_kingdom, Phase 75). discoveries_found_first/
    # discoveries_found_not_first are live as of Phase 271 -- see this
    # class's own Phase 271 note above.
    features_discovered_first: int = 0
    # Discoveries this leader personally discovered via Practice's own
    # SAGE branch that were the world's first instance (worth 3 points
    # each in the Chancellor formula) vs. not (worth 2 each) -- see
    # GameState.discoveries_first_found_by's own docstring for how
    # "first" is determined.
    discoveries_found_first: int = 0
    discoveries_found_not_first: int = 0
    discoveries_via_espionage: int = 0
    # Prince of Thieves (Office.THIEF_PRINCE, Phase 277, reformulated
    # Phase 369): +1 per successful theft result -- the disassembly's
    # own `Tit_Pts(leader,title)`, "two separate compiled success paths
    # award the point" (`AKGEN_embedded_catalogs.json gw_format.
    # royal_title_system` id 36). No writer yet -- turn/search_
    # execution.py's own Steal tactic doesn't feed MeritTally.
    successful_thefts: int = 0
    # Silver Tongue (Office.DIPLOMAT, Phase 277-adjacent, reformulated
    # Phase 369): a single cumulative `Tit_Pts`-style diplomatic-merit
    # counter -- the disassembly confirms +1/+2/+5 award sites in
    # contact/relationship/treaty routines but can't prove which of the
    # two higher values names which real event (same source, id 41), so
    # this stays one undifferentiated running total rather than inventing
    # named sub-events. No writer yet -- this project has no Treat/
    # alliance execution mechanic at all.
    diplomatic_merit_points: float = 0.0

    # Phase 379 -- 16 new `Tit_Pts`-style counters for the 18 remaining
    # real `royal_title_system` titles (`AKGEN_embedded_catalogs.json.txt
    # gw_format.royal_title_system.entries`, ids 16/21/28/30-35/37/40/
    # 42-44/46/48-50), the same "field exists, no populating consumer
    # yet" convention this class has used since Phase 59 -- see
    # `turn/merit_points.py`'s own Phase 379 addendum for each title's
    # real formula and which of these already has a live writer.
    # Master of Elements/Amazing Houdini/Sorceror of Black Magic/Master
    # Mind: +1 per successful cast of the matching spell school that
    # reaches the compiled title-award branch (ids 16/21/28/46).
    elemental_spell_casts: int = 0
    illusionist_spell_casts: int = 0
    necromancy_spell_casts: int = 0
    psychic_spell_casts: int = 0
    # The 6 terrain-King titles (ids 30-35): +1 per Explore result
    # recorded in the matching terrain.
    plains_explorations: int = 0
    desert_explorations: int = 0
    jungle_explorations: int = 0
    forest_explorations: int = 0
    mountain_explorations: int = 0
    sea_explorations: int = 0
    # Professor Whizdumb (Office.TEACHER, id 42): +1 per another
    # character's own effective Practice/teaching interaction with this
    # leader as the higher-skilled co-practicer.
    teaching_interactions: int = 0
    # Grandfather of Assassins (Office.ASSASSIN, id 43): +1 per
    # successful assassination -- this project has no Assassinate
    # mechanic yet, so this field has no writer at all (not even a
    # partial one), unlike most of this class's own "no writer yet"
    # fields.
    successful_assassinations: int = 0
    # Captain of the Musketeers (Office.DUELLIST, id 44): "duel merit is
    # transferred: the winner gains the duel's own merit value and the
    # loser loses the same value" -- the disassembly never names that
    # per-duel magnitude, so this stays a raw running total a future
    # phase can increment once (if ever) that value is sourced.
    duel_merit_net: int = 0
    # Air Force Commander (Office.WINGMAN, id 48): the source's own
    # *confirmed* term only -- "+1 for an air-unit victory and -1 for an
    # air-unit defeat"; its own "other encounter awards can add larger
    # values" is left unsourced and not reflected here.
    air_combat_merit: int = 0
    # King of Cowards (Office.CRAVENEST, id 49): the disassembly's own
    # signed courage/encounter scorer "suppresses a positive winner
    # award for this title and subtracts merit from the loser" -- the
    # real corpus itself only ever shows negative values here (no real
    # positive-award event has ever been observed, let alone sourced),
    # so this field is expected to only ever decrease in practice.
    courage_encounter_merit: int = 0
    # Bravest of the Brave (Office.BRAVEST, id 50): "cumulative bravery
    # merit from high-risk personal encounters/challenges" -- real,
    # observed range 0..28 in the source's own corpus, but no per-event
    # magnitude rule survives to reproduce it from a specific encounter
    # outcome.
    bravery_merit: int = 0

    def apply_death_penalty(self) -> None:
        """Phase 377 -- a leader who dies loses 25% of their own
        accumulated office merit (`AKGEN_embedded_catalogs.json.txt`
        `gw_format.imperial_office_system.death_penalty`, a real static
        disassembly of `AKGEN.EXE`/`AK.EXE`/`AK.OVR`): `new = old -
        (old div 4)`, confirmed against two real examples the source
        itself quotes -- Teleko `lgenp` 23->18 and `lmhpp` 21->16, both
        exactly `old - old div 4`. Called by `GameState.remove_leader()`
        on every leader death, matching the source's own unconditional
        "a leader who dies" framing (no exemption for a King's own
        succession, which `remove_leader()` already models separately).

        This project splits several of the real, single Pascal
        accumulators (`lgenp`, `ladmp`) into two non-negative won/lost
        counters (Phase 254/308's own design, not a source requirement)
        rather than one running signed total -- so this method applies
        the same `old - old div 4` formula to each stored counter
        independently, which is this project's own reasonable reading of
        "the accumulated total", not a byte-for-byte replica of a single
        `lgenp` field's own haircut (no real corpus example with a
        split representation exists to test against). Pascal's own
        `div` truncates toward zero, unlike Python's `//` (floors toward
        negative infinity) -- irrelevant for this project's own fields,
        which are never negative, but implemented correctly regardless
        since the source's own examples include a negative case
        (Adele's `lgenp` -17->-13, which only matches truncating
        division: `-17 - (-17 div 4)` = `-17 - (-4)` = `-13`).

        Scoped to exactly the fields that back the 4 offices
        `imperial_office_system` itself marks `cumulative`/`mixed
        cumulative` (Marshal, Admiral, Defender, Chancellor's own
        discovery terms, Priest's own cast-count term) -- Emperor/
        Treasurer/Mage's own formulas are `current` (tax base, treasury,
        live skills), not stored accumulators, so nothing here applies
        to them. Deliberately NOT touched: `successful_thefts`/
        `diplomatic_merit_points` (Phase 369's own `royal_title_system`
        formulas, a separate title system this same JSON source doesn't
        state the same death-penalty rule for) and `RaceTitleTally`
        (Phase 367's own separate race-fanaticism title system) -- both
        left as an honest "not verified for these" gap rather than an
        assumed blanket rule. **Phase 379's own 16 new fields (the
        remaining `royal_title_system` titles) are excluded for the
        exact same reason, now with the source's own explicit
        confirmation**: `gw_format.royal_title_system.death_rule` states
        outright that "the separate 25% death reduction documented for
        lgenp/ladmp/lmhpp is not generalized to Tit_Pts" -- every title
        this method skips is a `Tit_Pts`-style counter, so this isn't a
        guess extended from the two examples above, it's the source
        directly ruling the exclusion in.
        """

        for field_name in (
            "land_battles_won_points",
            "land_battles_lost_points",
            "naval_battles_won_points",
            "naval_battles_lost_points",
            "monster_hp_defeated",
            "monster_hp_neutralized",
            "resurrection_bless_casts",
            "features_discovered_first",
            "discoveries_found_first",
            "discoveries_found_not_first",
            "discoveries_via_espionage",
        ):
            old_value: int = getattr(self, field_name)
            pascal_div4 = old_value // 4 if old_value >= 0 else -((-old_value) // 4)
            setattr(self, field_name, old_value - pascal_div4)


@dataclass(slots=True)
class RaceTitleTally:
    """Cumulative input to the 11 race-fanaticism title Merit Point
    formulas (Phase 367, ``turn/race_titles.py``). One instance per race
    a leader has ever accrued points for (``LeaderState.race_title_
    tally``, a ``dict[Race, RaceTitleTally]``).

    **Phase 369 correction**: this class originally had five fields,
    built from ``CARICHE E ABILITÀ.txt`` (crack-units-commanded,
    heroes-in-service, provinces-owned, rival-race kills, monster-in-
    province kills, named-monster kills, legendary-item bonus -- several
    computed live rather than stored, see that phase's own docstring).
    `AKGEN_embedded_catalogs.json gw_format.royal_title_system` (a real
    disassembly of ``AK.EXE``/``AK.OVR``, verified against the 12
    ``GW3__T1..T12`` historical saves) proved the real compiled formula
    is far simpler: a single cumulative ``Tit_Pts`` counter (+1 per won
    battle, -2 per lost battle -- not the -1 this project had guessed),
    doubled outright when the candidate's own race matches the title's
    race. None of the other five terms exist in the real formula, so
    they're removed rather than kept as unused flavor. The source also
    names one more real term this project can't yet build: "an
    additional positive battle award in a proportional/random branch" --
    an honest, documented gap, not folded into the two fields below by
    guesswork.

    Default 0, the same "field exists, no populating consumer yet"
    convention ``MeritTally`` uses -- no battle call site increments
    these yet.
    """

    front_line_battles_won_points: int = 0
    front_line_battles_lost_points: int = 0


@dataclass(slots=True)
class LeaderState:
    leader_id: int
    kingdom_id: int | None  # None = independent Hero, not in any kingdom's service
    name: str
    location: HexCoord
    # Phase 729: AdvancedAbility.SPY_DOUBLE_AGENT -- the foreign
    # Kingdom's own id, when this leader's own real kingdom_id (above,
    # left unchanged) was "apparently" hired by a different Kingdom this
    # turn (`turn/plan_dispatch.py _dispatch_hire()`'s own Double Agent
    # bypass). Read and cleared the same turn by `turn/turn_processor.py
    # run_turn()`'s own end-of-turn intel-grant hook -- never persists
    # past the turn it's set on, so it needs no `_replenish_turn_scoped_
    # state()` reset. `None` = not apparently hired by anyone this turn.
    double_agent_hired_by_kingdom_id: int | None = None
    # None = no ability data recorded for this leader -- see module docstring.
    skills: SkillTable | None = None
    # King/Hero distinction (Phase 40) -- see module docstring.
    is_king: bool = False
    # Phantasmal Armies' strength bonus level (Phase 59) -- see module docstring.
    phantasmal_armies_level: int = 0
    # Oratory idempotency flag (Phase 59) -- see module docstring. Reset
    # to False at the end of every `run_turn()` call (Phase 573).
    oratory_boosted_this_turn: bool = False
    # Phase 139: the leader's own Temper (models/temper.py, Phase 82).
    # None = not recorded, the same "no data" convention as `skills`.
    temper: Temper | None = None
    # Phase 139: the leader's own birth x-coordinate (REPORTS.PAS
    # `bornx[agent]`, Phase 136's own Temper_Est noise term) -- None =
    # not recorded; this project has no character-creation/world-
    # generation source for it, same category of gap as `skills`
    # before Phase 30/31 gave it a real populating consumer.
    birth_x: int | None = None
    # Phase 505: the leader's own birth y-coordinate (REPORTS.PAS
    # `borny[agent]`), `birth_x`'s missing other half -- `turn/hire_pay.py
    # required_pay()`'s own real `LCost` formula is the first consumer
    # that needs both halves of the birth coordinate at once (as a real
    # `HexCoord` for a province-ownership lookup, not just a lone noise
    # bit). Same "None = not recorded" convention as `birth_x`.
    birth_y: int | None = None
    # Phase 162: the leader's own true Alignment (models/alignment.py),
    # mirroring `temper`'s own Phase 139 precedent -- None = not
    # recorded, the same "no data" convention. Previously only
    # `KingdomState.alignment` existed; `turn/hire_pay.py`'s
    # required-pay formula is this field's first real consumer.
    alignment: Alignment | None = None
    # Phase 193: kingdom ids currently watching this leader via a successful
    # Clairvoyance cast -- see module docstring. Not auto-cleared.
    clairvoyance_watchers: set[int] = field(default_factory=set)
    # Phase 637: this leader's own most-recently-cast Clairvoyance target
    # (the caster's side of the same successful cast that writes the
    # *target's* `clairvoyance_watchers` above) -- mirrors `RUMORS.PAS`/
    # `REPORTS.PAS`'s own `lspec[l2]`'s single packed `clobj` value, so a
    # later cast simply overwrites it. Written unconditionally by every
    # successful `_execute_clairvoyance()` call, regardless of whether
    # this caster has `AdvancedAbility.ENHANCED_CLAIRVOYANCE` -- the
    # ability gate is checked separately at read time (`report/turn_
    # report.py _was_clairved()`), exactly mirroring how the real
    # `Was_Clairved` checks `Has_SA(l2,Expand_Clair)` against the
    # already-written `lspec` value rather than gating the write itself.
    # Not auto-cleared at a turn boundary -- no source states a duration
    # limit for this specific CHARACTERS-report reveal (distinct from the
    # confirmed "for the rest of the turn" watcher-feed sentence above).
    clairvoyance_cast_target: int | None = None
    # Phase 196: the leader's own individual Race, mirroring `temper`'s own
    # Phase 139 "None = not recorded" precedent. Unlike every other leader
    # in this project (whose race is always implicitly their serving
    # Kingdom's own `KingdomState.race`), a VALHALLA visitor (models/
    # valhalla.py) keeps their own race independent of the Kingdom they're
    # visiting -- the first real consumer that needs this field at all.
    race: Race | None = None
    # Phase 204: set by a successful Mystic Winds cast (turn/cast_execution.py
    # _execute_mystic_winds) -- same "persistent for the rest of the turn,
    # caller clears it" convention as oratory_boosted_this_turn/
    # phantasmal_armies_level above. See that function's own docstring for
    # what this flag is a marker for (three of the spell's own effects are
    # confirmed facts, not yet wired to any consumer).
    mystic_winds_active: bool = False
    # Phase 227: this leader's own cumulative Merit Point inputs -- see
    # MeritTally's own docstring and turn/merit_points.py.
    merit_tally: MeritTally = field(default_factory=MeritTally)
    # Phase 367: cumulative inputs to the 11 race-fanaticism title Merit
    # Point formulas, one entry per race this leader has ever accrued
    # points for -- see RaceTitleTally's own docstring and turn/
    # race_titles.py.
    race_title_tally: dict[Race, RaceTitleTally] = field(default_factory=dict)
    # Phase 259: True for a Royal Heir automatically installed on the
    # throne by remove_leader() when a King dies, until turn/
    # succession.py create_king() finalizes it into a real King (clears
    # this flag) -- see remove_leader()'s own Phase 259 addendum.
    # **Phase 553 correction**: this flag alone does NOT mean the Heir
    # is still Resurrection-eligible/still displays as "Royal Heir" in
    # reports. RULES.AK [4.21.1]'s own quote ("as soon as you assign
    # your Heir his new skill levels, or improve any of his abilities by
    # practice or experience, you lose the resurrection option") reads
    # as an edge-triggered rule, but AKGEN_reverse_engineering_report
    # (5).md SS6.2/SS11.1 (REPORTS.PAS Get_HName, machine-verified) shows
    # the real engine checks a *numeric* threshold instead, every time:
    # Total_USkill(leader) < 7 (turn/cast_execution.py
    # is_unfinalized_royal_heir()). turn/practice_execution.py no longer
    # clears this flag on a skill/aptitude rise -- a Heir who trains one
    # ability while still under the threshold stays eligible, matching
    # the real engine; crossing the threshold closes eligibility via the
    # numeric check alone, with no flag mutation needed. This flag itself
    # is cleared only by turn/succession.py create_king() (finalized into
    # a real King) or by turn/cast_execution.py
    # _execute_resurrection()'s own Royal-Heir branch (Resurrection
    # consumed).
    is_royal_heir: bool = False
    # Phase 260: models/sex.py's own Sex -- "confirmed absent" since
    # Phases 195/217/230, now given its first real writer
    # (turn/succession.py create_king()). None = not recorded, the same
    # "no data" convention as temper/alignment/race above.
    sex: Sex | None = None
    # Phase 302 (Discovery.ANALYTICAL_PSYCHOLOGY, rulebook text quoted in
    # models/discovery.py): set by a successful Charm cast against a
    # target whose own kingdom owns this Discovery -- the spell still
    # works (kingdom_id reassigned as normal), but this records the
    # target's own *original* kingdom_id so turn/turn_processor.py
    # run_turn()'s own end-of-turn sweep can revert kingdom_id back to
    # it and clear this field. Unlike every other "persistent for the
    # rest of the turn, caller clears it" flag in this project
    # (oratory_boosted_this_turn, mystic_winds_active, ...), this one
    # IS auto-cleared, by that end-of-turn sweep -- the first field in
    # this project that needs a real revert-to-prior-value, not just a
    # flag reset, so it gets its own dedicated turn-boundary consumer
    # instead of reusing that convention. None = not currently under a
    # protected Charm.
    analytical_psychology_revert_kingdom_id: int | None = None
    # Phase 310 (Kill_Enemy [4.25.2]'s coma variant, user-clarified
    # 2026-07-31): True while this leader is in a deep coma. Every
    # ability reads 0 for as long as this is set -- see
    # ``turn/discovery_effects.py effective_skill_level()``'s own
    # unconditional short-circuit -- covering every real consumer of a
    # leader's own skill level (Cast success rolls, battle Tactical/
    # Naval bonuses, Duel commander selection, Merit Points, ...) with
    # one choke point, without ever mutating the real, underlying
    # ``skills`` -- there is nothing to "restore" on cure beyond
    # clearing this flag. ``turn/practice_execution.py`` additionally
    # gates Practice itself outright (comatose ⇒ cannot raise a skill
    # through experience, the one consumer that reads ``skills``
    # directly rather than through ``effective_skill_level()``).
    # Deliberately does NOT remove the leader from ``state.leaders`` or
    # block any action -- the user's own clarification: "potrà comunque
    # fare tutte le azioni (muoversi, reclutare armate eccetera)... come
    # se fosse su un letto, trasportato dai suoi scudieri" (can still do
    # every action -- as if lying on a bed, carried by their own
    # squires). Cleared only by a successful Resurrection cast targeting
    # this leader (``turn/cast_execution.py _execute_resurrection()``'s
    # own Phase 310 addendum) -- unlike an ordinary dead-Hero
    # resurrection, curing a coma never changes ``kingdom_id``, even
    # when cast by a hero/King of a different kingdom (same source).
    is_comatose: bool = False
    # Phase 477: AKGEN_reverse_engineering_report (2).md SS20.9's own
    # "Grandfather of Assassins" title-perk guard escalation -- "Ogni
    # fallimento raddoppia la guardia e dimezza la probabilità normale
    # del tentativo seguente" (every failure doubles the guard and
    # halves the normal chance of the following attempt). Counts every
    # resolved Assassins Guild attempt against this specific leader (not
    # the titleholder's own tally, and unrelated to `MeritTally`'s own
    # Assassin counter -- see `turn/assassin_guild.py`'s own module
    # docstring for why a successful Guild kill never touches that
    # counter either). Never reset by anything in this project -- no
    # source names a condition that clears it, so it stays a strictly
    # monotonic "N attempts have been resolved against this specific
    # target" record. **Phase 614 correction**: a direct disassembly
    # reverse-engineering (`AK.EXE:0x18F0F-0x18F1D`, user-supplied
    # 2026-08-22) confirmed the real byte increments after *every*
    # resolved attempt, not only a failed one -- renamed from
    # `assassination_guild_failed_attempts` accordingly (the old name
    # was accurate before this correction, misleading after it; a
    # successful attempt's own increment is normally invisible since the
    # target dies, but matters if they're later resurrected).
    assassination_guild_attempts: int = 0
    # Phase 456 (corrects Phase 449's own per-ability dict): the real
    # engine keeps **one shared byte per leader**, not one per ability --
    # AKGEN_reverse_engineering_report (2).md SS2.2's own words, "un
    # singolo byte per personaggio, condiviso con l'esperienza" (a single
    # byte per character, shared with experience). Practice's own
    # aptitude-gated credit (turn/practice_execution.py) and Add_
    # Experience's own triangular-distribution gain (turn/experience.py)
    # both accumulate into this exact same counter; whichever ability's
    # event happens to push it past 100 is the one that rises -- a real,
    # documented "occult rule" (SS3.3: credit earned practicing one
    # ability can produce a level in a completely different ability
    # practiced/used next). Deliberately NOT merged into SkillTable.
    # raw_values (which mirrors real GW file bytes, including an already-
    # documented unexplained 31st trailing value) -- this counter has no
    # confirmed real-file representation of its own to preserve, so it
    # stays a pure in-memory simulation field. Phase 449 originally
    # modeled this as a dict[int, int] keyed by Ability.value, since only
    # Practice fed it at the time and per-ability bookkeeping happened to
    # look equivalent for every single-ability test written against it --
    # this field's own rename to a bare int, and every call site/test
    # that read or wrote it, is Phase 456's own correction now that Add_
    # Experience's SS2.2/SS3.3 text makes the sharing explicit.
    experience_credit: int = 0
    # Phase 493 -- which of the 89 catalogued Advanced Abilities (Phase
    # 128) this leader has actually been granted. A flat set, not keyed
    # by Ability category: the source excerpt's own rule (``models/
    # advanced_ability.py``'s module docstring) grants one *per level*
    # reaching 5-9 within a category, not one per category overall, so a leader
    # who trains a single Ability all the way up can hold several
    # members from that same category at once -- and every ordinal
    # across all 89 is already globally unique, so a flat set loses no
    # information a `dict[Ability, ...]` shape would have preserved.
    # Written by ``turn/practice_execution.py``'s own skill-rise path
    # (currently only the 5 magic colleges -- see that module's Phase
    # 493 addendum for why the other 10 categories aren't wired yet).
    advanced_abilities: set[AdvancedAbility] = field(default_factory=set)
    # Phase 546 -- Valhalla visitor lifecycle (Desktop/VALHALLA.txt).
    # None for every leader except the current Valhalla visitor
    # (VALHALLA_VISITOR_LEADER_ID). ``valhalla_active_turn`` is the one
    # game turn on which the visitor is allowed to act at all (set at
    # spawn to the turn after the one Gate Angel succeeded on --
    # ``turn/valhalla_execution.py finalize_gate_angel_visit()`` runs in
    # ``run_turn()``'s own end-of-turn tail, after that turn's own
    # phase-dispatch loop already ran). ``valhalla_allowed_phase_count``
    # is how many of that turn's up-to-5 phases (P0-P4) may carry a real
    # order -- VALHALLA.txt's own escalating table, see ``models/
    # valhalla.py _valhalla_stay_phase_count()``. ``valhalla_fixed_item_id``
    # is the ``ItemInstance.item_id`` of the visitor's own fixed magic
    # item (``ValhallaHero.fixed_item``), so it can be blocked from Give
    # (``turn/trade_execution.py execute_give()``) and specifically
    # identified for hand-off/drop on departure (``turn/valhalla_
    # execution.py process_valhalla_departure()``) -- None for the 2
    # heroes whose own item is unresolved (see ``models/valhalla.py``'s
    # docstring) or once the visitor has departed.
    valhalla_active_turn: int | None = None
    valhalla_allowed_phase_count: int | None = None
    valhalla_fixed_item_id: int | None = None
    # Phase 669 -- rulebook [5.10]: this leader's own real, standing
    # Special Encounter Plan for the current game turn, decoded from
    # the real ``SP:`` block their own move submission carried (``turn/
    # sep_decode.py decode_special_encounter_plan()``, Phase 659).
    # Populated once per turn, before any phase dispatches, by ``turn/
    # turn_processor.py run_turn()`` -- see that function's own Phase
    # 669 addendum. Defaults to ``()`` for any leader with no SP: data
    # recorded (or never processed by ``run_turn()`` at all) -- the
    # real, sourced empty-plan fallback (``Plan_Intent``'s own `IF int
    # = CNone THEN int:= CMelee`), not a placeholder: an empty plan
    # reads as an aggressive Melee-intent SEP, matching this project's
    # own pre-Phase-669 always-duel default exactly.
    special_encounter_plan: tuple[SearchTactic, ...] = ()
    # Phase 713 -- AdvancedAbility.SPY_BLACKMAIL. Mirrors the real
    # parsed `GWLeaderRecord.unpaid_blackmail_penalty_exponent` field
    # exactly (`parser/gw_world.py`, "an unpaid-blackmail counter that
    # halves the next demand each time it's incremented") -- scoped to
    # this Spy (the character), not to any particular target Kingdom.
    # Incremented by `turn/blackmail.py resolve_unpaid_blackmail()`
    # whenever one of this leader's own demands goes unpaid; reset to 0
    # by `turn/trade_execution.py execute_give()` when a matching
    # payment clears the claim. Never reset by `_replenish_turn_scoped_
    # state()` -- a real, monotonic-until-paid counter, not a per-turn
    # value.
    unpaid_blackmail_penalty_exponent: int = 0


@dataclass(slots=True)
class ProvinceState:
    coord: HexCoord
    terrain: Terrain
    race: Race
    owner_kingdom_id: int | None = None
    explored_percent: int = 0
    contested_by_kingdom_id: int | None = None
    # Phase 409 -- the coordinate `contested_by_kingdom_id`'s attacker
    # originally invaded from, so a later forced-rebattle (turn/turn_
    # processor.py _dispatch_contested_rebattles()) can still honor
    # rulebook [7.4]'s real forced-attacker-retreat rule ("must retreat
    # into the same province they invaded from, or a province adjacent
    # to it") instead of falling back to the wrong, defender-style
    # nearest-friendly-neighbor rule for lack of an origin to pass. Set
    # alongside `contested_by_kingdom_id` in `turn/battle_orchestrator.py
    # fight_battle()`'s own [7.6] "mixed result" branch, cleared in the
    # same two branches that clear `contested_by_kingdom_id`.
    contested_from_coord: HexCoord | None = None
    # How many of each ArmyType have been recruited from this province so
    # far this gameturn (rulebook [3.4]: normally 1 per type per province
    # per turn, 2 in a King's home province). Cleared at the end of every
    # `run_turn()` call, alongside `ArmyState.movement_points`'s own
    # replenishment (`turn/turn_processor.py _replenish_turn_scoped_
    # state()`, Phase 573).
    recruited_this_turn: dict[ArmyType, int] = field(default_factory=dict)
    # Phase 691: `AdvancedAbility.DRUIDIC_DINOSAURS`'s own real
    # description -- "no further units may be recruited in the province
    # that turn" after a successful Dinosaur recruit. A hard lockout
    # regardless of ArmyType, distinct from `recruited_this_turn`'s own
    # per-type counter. Cleared at the same turn-boundary sweep as
    # `recruited_this_turn` above.
    recruit_locked_this_turn: bool = False
    # Part Sea / Flood Province (Phase 59) -- see module docstring.
    terrain_override: Terrain | None = None
    # Bless / Earthquake (Phase 59) -- see module docstring.
    tax_modifier_percent: int = 0
    # Illusory Terrain (Phase 59) -- see module docstring.
    illusory_terrain: Terrain | None = None
    # Per-kingdom exploration progress (Phase 69) -- see module docstring.
    # Distinct from `explored_percent` above (a single shared scalar,
    # unable to answer "how much has *this* kingdom explored" for the
    # rulebook [6.3] exploration-advantage strength bonus). Also the
    # backing store for "known provinces" (Phase 623) -- see module
    # docstring's own Phase 623 addendum and `known_to_kingdom()` below.
    explored_percent_by_kingdom: dict[int, int] = field(default_factory=dict)
    # Province display name (Phase 150) -- models DEF2.PAS's own
    # `pname^[x,y]` global array directly. Never synthesized: the real
    # host engine never generates a province name at runtime either (it
    # reads one already baked into the world-generated map by
    # `AKGEN.EXE`, whose own source isn't in this archive) -- `None`
    # until a caller sets it, e.g. via `turn/rename_province.py
    # rename_home_province()`, the one real, sourced runtime exception
    # (`DEF2.PAS Read_T1Names`, turn-1 capital rename).
    name: str | None = None
    # Scar Terrain (Phase 201) -- see module docstring. Cumulative,
    # permanent gold reduction the spell has inflicted on this
    # province's own tax base so far, in `turn/cast_execution.py
    # SCAR_TERRAIN_TAX_REDUCTION` (2) increments. Distinct from
    # `tax_modifier_percent` above (a percent Bless/Earthquake *set*,
    # not cumulative) -- this is an absolute gold amount that only ever
    # grows.
    scar_terrain_gold_reduction: int = 0
    # Reinforced Concrete vs. Earthquake (Phase 270, Discovery.txt) --
    # "income from the affected province will only decrease by 3 gold,"
    # a flat replacement for Earthquake's own -100%
    # ``tax_modifier_percent`` when the province owner's Kingdom owns
    # the Discovery. Set (not accumulated) by a defended Earthquake cast
    # (``turn/cast_execution.py _execute_earthquake``); a *for one turn*
    # figure, unlike the cumulative/permanent ``scar_terrain_gold_
    # reduction`` above -- the caller resets it the same "no auto-clear
    # yet" way it already leaves ``tax_modifier_percent``/
    # ``illusory_terrain`` between turns.
    earthquake_flat_reduction: int = 0
    # Illusory Fog (Phase 207) -- see module docstring. Set by a
    # successful cast (turn/cast_execution.py _execute_illus_fog).
    # Cleared to False at the end of every run_turn() call (Phase 576) --
    # the rulebook's own quoted text says the spell "dissipates at the
    # end of the gameturn," and unlike tax_modifier_percent/illusory_
    # terrain above, this one already has a real, live consumer (turn/
    # battle_orchestrator.py/turn/strength.py halve air-unit strength
    # while it's set), so leaving it uncleared was a real bug, not just
    # unconsumed data.
    illusory_fog_active: bool = False
    # Real per-province tax value (Phase 222 `parser/gw_world.py`'s own
    # `GWProvinceRecord.tax` -- the real `ptax[px,py]` this project has
    # needed since Phase 220's own `describe_provinces_report()` gap,
    # confirmed absent from every surviving `.PAS` file since Phase 158).
    # Baked into the world file at world-generation time by the lost
    # `AKGEN.EXE`, the same "world-gen-only, no runtime formula" category
    # as `name`'s own `pname` above -- `None` until a caller populates it
    # (currently `parser/gw_world_bridge.py bridge_gw_world_provinces()`,
    # the one real, sourced populating path).
    tax: int | None = None
    # Real per-province Recruiting Types, Mod_PAT(px,py,0)/Mod_PAT(px,py,1)
    # (Phase 278 `parser/gw_world.py`'s own decode -- see that module's
    # "Recruiting Types (Mod_PAT)" docstring section for the full
    # derivation). Baked into the world file at world-generation time,
    # same as `tax` above -- `None` until a caller populates it (currently
    # `parser/gw_world_bridge.py bridge_gw_world_provinces()`). Every real
    # province observed so far has a genuine `recruit_type_1`;
    # `recruit_type_2` is `None` both when unbridged AND for the real "no
    # second recruit type" case (the real table's own "None" cell) --
    # the two cases render identically (nothing to show), so this field
    # doesn't need to distinguish them, unlike `tax`.
    recruit_type_1: ArmyType | None = None
    recruit_type_2: ArmyType | None = None
    # Plague spread (Phase 233) -- rulebook [4.25.3]: "the next phase,
    # there is a 15% chance per adjacent province that the plague will
    # spread, and it can spread further each phase after that." Set by
    # a successful Plague cast (`turn/cast_execution.py _execute_plague()`)
    # or by `turn/plague_spread.py resolve_plague_spread()` itself
    # reaching this province from a neighbor; never cleared automatically
    # -- the rulebook describes no "the plague dies out" end condition,
    # so an afflicted province stays a spread source for the rest of the
    # game, the same "no consuming cleanup pass exists" convention
    # `illusory_terrain`/`scar_terrain_gold_reduction` above already use.
    # Also doubles as the "casting more than one Plague spell does not
    # have a cumulative effect" guard: a recast on an already-`True`
    # province is a no-op beyond confirming `applied=True`.
    plague_active: bool = False
    # Type 2 terrain "Island" (Phase 282, pt2). **Phase 723 correction**:
    # `pt2` is a real, parsed field after all -- `parser/gw_world.py
    # GWProvinceRecord.alternate_terrain` has decoded it since Phase 373
    # (`AKGEN_reverse_engineering_report (5).md`), just never bridged
    # into `ProvinceState` until `parser/gw_world_bridge.py bridge_gw_
    # world_provinces()`'s own Phase 723 addendum. An Island province is
    # half-Sea/half-its-own-land-terrain; `terrain` above still holds
    # the *land* half (an Island is never `Terrain.SEA` itself -- that
    # would just be an ordinary Sea province), this flag marks the Sea
    # half layered on top -- confirmed the correct orientation for this
    # project's own bridged data directly with the user (2026-09-03),
    # against a real, older reverse-engineering report that models the
    # opposite orientation for its own separate world-generation tax
    # formula (see `worldgen/province_tax.py`'s own docstring). See
    # `turn/strength.py compute_effective_strength()`'s own `is_island`
    # parameter for the one real gameplay consequence the user specified
    # (armies fight at half land-strength/half Sea-strength here;
    # overflight-air units -- Dragons, Eagles -- are unaffected) and
    # `turn/island_provinces.py` for the separate, still-needed opt-in,
    # exact-count moderator tool for a hand-built/synthetic world with
    # no real `GWProvinceRecord` to bridge from. `False` for every
    # bridged province whose own real `pt2` reads the `NO_TERRAIN`
    # sentinel -- true of every real `GW3__T1`-`T12` sample on hand.
    is_island: bool = False
    # Find Mines (Phase 509, Advanced Ability -- see models/advanced_
    # ability.py ADVANCED_ABILITY_DESCRIPTION[EXPLORER_FIND_MINES] for
    # the quoted rulebook text this mechanic implements). Both are
    # province-global (not per-kingdom, unlike `explored_percent_by_
    # kingdom`) -- the rulebook describes mines as a property of the
    # province itself, and the halving applies regardless of which
    # kingdom's Explorer found the previous one.
    # Cumulative, permanent gold added to this province's own tax base
    # by successful Find Mines rolls so far, capped at 10 (rulebook's
    # own "maximum of 10 gold") -- combined into `turn/tax_base.py
    # province_tax_yield()` the same way `scar_terrain_gold_reduction`
    # already is, just additive instead of subtractive.
    mine_gold_bonus: int = 0
    # How many Find Mines rolls (successful or not) have already been
    # made in this province -- each one halves the next roll's own
    # chance (rulebook: "each time he explores a province, the chance
    # of finding another mine in that province is halved").
    mine_find_attempts: int = 0

    def effective_terrain(self) -> Terrain:
        """The province's real current terrain for gameplay mechanics --
        Part Sea/Flood's own ``terrain_override`` (Phase 59) if set,
        the base ``terrain`` otherwise.

        Phase 168: every real-mechanics call site that used to read
        ``.terrain`` directly (movement cost, exploration, combat
        ability/strength/nemesis, Whale/Fleet retreat rules) now reads
        this instead, so a cast Part Sea/Flood actually has gameplay
        effect -- previously it mutated ``terrain_override`` with no
        consumer anywhere, confirmed by grep before this phase.
        Deliberately distinct from ``illusory_terrain`` (Illusory
        Terrain): that field only deceives what an outside observer is
        *told*, and must never feed into a real mechanics calculation
        here -- conflating the two would let a bluff spell silently
        change real movement costs or combat outcomes.
        """

        return self.terrain_override if self.terrain_override is not None else self.terrain

    def known_to_kingdom(self, kingdom_id: int) -> bool:
        """"Known provinces" (Phase 623, see module docstring's own
        addendum): `kingdom_id` has at least `KNOWN_PROVINCE_MIN_
        PERCENT` recorded exploration of this province -- reads
        `explored_percent_by_kingdom` (Phase 69), no new field.
        """

        return self.explored_percent_by_kingdom.get(kingdom_id, 0) >= KNOWN_PROVINCE_MIN_PERCENT


# "Known provinces" (Phase 623) -- the flat exploration-percent floor a
# province is revealed at when a Kingdom merely learns it exists (e.g.
# `turn/move_execution.py reveal_adjacent_provinces()`, `turn/feature_
# power_execution.py _reveal_unknown_provinces()`), as opposed to the
# much larger amounts real exploration (Move/Explore) actually grants.
KNOWN_PROVINCE_MIN_PERCENT = 1


@dataclass(slots=True)
class GraveyardEntry:
    army_type: ArmyType
    quality: Quality  # rank at time of death
    kingdom_id: int | None  # who owned it -- reference only, not read by any consumer yet
    # Phase 309: monotonic insertion order, assigned by GameState.record_
    # battle_death() from GameState.graveyard_death_counter -- not a real
    # turn number (see module docstring's Phase 309 addendum), just
    # enough to answer turn/skeletal_decay.py's "which died longest ago."
    # Defaults to 0 so pre-existing direct-construction call sites (tests
    # that don't care about decay ordering) keep working unchanged.
    death_seq: int = 0


@dataclass(slots=True)
class WorldEvent:
    """One cross-kingdom-visible happening (Phase 231) -- the real raw
    material for GENERAL INTELLIGENCE REPORT's own "Kingdom of X (#N):"
    grouped feed (``report/turn_report.py describe_general_intelligence_
    report()``). ``coord`` is where it happened -- both the visibility
    test's own anchor (``turn/world_events.py is_visible_to()``) and the
    grouping key (the province's *current* ``owner_kingdom_id`` at
    render time, confirmed against real fixture text where a battle's
    own province ends up owned by the side the letter groups it under,
    win or lose -- see that composer's own docstring). ``lines`` is
    already-rendered narrative text, reusing this project's own existing
    renderers rather than storing raw event data to re-render later.
    """

    coord: HexCoord
    lines: list[str]


@dataclass(slots=True)
class GameState:
    turn_number: int = 1
    # Phase 493 -- AKGEN.EXE's own per-game seed source for the real
    # `spabord` Advanced Ability level-schedule build (``worldgen/
    # special_ability_level_schedule.py``, Phase 384: `RandSeed = 50 *
    # game_number`). No consumer set this before this phase -- see that
    # module's own docstring for why the schedule it builds had no
    # caller until now. Default `1` is an arbitrary placeholder (the
    # real game-number value depends on data this project has no
    # bridge for yet), matching this field's own "nothing derives a
    # real value from parsed data" status, not a sourced default.
    game_number: int = 1
    # Phase 538 -- the world header's own `gametyp` (`models/game_type.py
    # GameType`), needed to gate the Arcane's Valor artifacts (93-98,
    # AKGEN_reverse_engineering_report (4).md SS11) behind `GameType.
    # ARCANES`, per the user's own explicit instruction that this variant
    # isn't currently played. `None` for every existing game/test --
    # `turn/kingdom_bridge.py` (or any other header-consuming bridge
    # point) is the natural place to set this from a real `GWHeader.
    # game_type` once one exists for this specific field; none does yet
    # (this project's own header-to-GameState bridge only ever carried
    # leader/kingdom data, never header-level fields), so this stays
    # settable only via direct construction for now -- a real, narrower
    # scope than a full bridge, not a guessed pipeline.
    game_type: GameType | None = None
    # Phase 621 -- the `GW` header's own field #33, a persistent 16-bit
    # bitmask (`miscwrit`, user-supplied reverse-engineering report
    # "miscwrit.md", 2026-08-22). Only bit `0x0002` has a live consumer
    # in this project (`worldgen/internal_magical_locations.py
    # resolve_spell_candidate()`'s own `Set_Spell` derivation for
    # `Power.CAST_SPELL`/`ANS_PRAYER`) -- bits `0x0001`/`0x0004` (two
    # legacy `totfees` migration markers) and `0x0008` (a diplomacy
    # contact-distribution revision flag) are real but belong to
    # entirely unrelated subsystems, not modeled here. Default `2`
    # matches `AKGEN.EXE`'s own unconditional startup `miscwrit :=
    # miscwrit OR 2` (CERTO in the report) -- the correct sourced value
    # for a freshly-generated world, and also what every real observed
    # `GW3__T1`-`T12` file already carries (`6`/`0x0006` and `14`/
    # `0x000E` respectively, both with this same bit set).
    miscwrit: int = 2
    # Phase 622 -- the `GW` header's own field index 13 (zero-based),
    # `due_day`: the real day-of-month of the turn's own "Due" date
    # (user-supplied reverse-engineering report "gdday.md", 2026-08-22).
    # Already parsed by `parser/gw_world.py GWHeader.due_day` (an
    # earlier, independent "Phase 318/342 calendar finding"), but never
    # loaded into `GameState` -- there is no "build a live `GameState`
    # from a real `GWHeader`" bridge yet, the same status `miscwrit`
    # (Phase 621) had before this field. Only consumer in this project:
    # `worldgen/internal_magical_locations.py derive_chance_sub_power()`
    # (`Power.CHANCE`'s own `(gameturn + gdday) AND 7` sub-power roll).
    # `gdmonth`/`gdyear`/`gturnlen` are real (`GWHeader.due_month`/
    # `.due_year`/`.turn_length_days`) but out of scope -- `Chance`
    # "ignora completamente gdmonth e gdyear" (CERTO), and this project
    # has no due-date report line or Quote-of-the-Week composer yet to
    # consume them. Default `1` is a generic placeholder, the same class
    # as `turn_number`/`game_number`'s own `1` defaults -- unlike
    # `miscwrit`'s `OR 2`, real `gdday` is calendar data with no fixed
    # "freshly-generated world" constant to source a better default from.
    gdday: int = 1
    # Phase 670 -- this turn's own resolved monster-raid/Thunderbird
    # outcomes (`Desktop/THUNDERBIRD.md`), reset and repopulated once per
    # turn by `turn/tax_base.py apply_turn_revenue()`. Read directly by
    # `report/turn_report.py describe_finances_report()` -- the same
    # "per-turn fact lives on `GameState`, no signature threading needed"
    # convention already used for `LeaderState.mystic_winds_active`/
    # `ProvinceState.plague_active`.
    turn_raid_events: list[RaidEvent] = field(default_factory=list)
    kingdoms: dict[int, KingdomState] = field(default_factory=dict)
    provinces: dict[HexCoord, ProvinceState] = field(default_factory=dict)
    armies: dict[int, ArmyState] = field(default_factory=dict)
    leaders: dict[int, LeaderState] = field(default_factory=dict)
    # Archived by remove_leader() (Phase 59) -- see module docstring. Keyed
    # by the same leader_id, so a resurrection can look it up directly.
    dead_leaders: dict[int, LeaderState] = field(default_factory=dict)
    # Battle deaths only (Phase 60) -- see module docstring.
    battle_graveyard: dict[HexCoord, list[GraveyardEntry]] = field(default_factory=dict)
    # Phase 309: next GraveyardEntry.death_seq to hand out -- see module
    # docstring's Phase 309 addendum. Monotonic, never reset.
    graveyard_death_counter: int = 0
    allied_kingdoms: set[frozenset[int]] = field(default_factory=set)
    # Phase 261: RULES.AK [3.4] "In order for you to Recruit in your
    # ally's territory, he MUST issue a 'Treat' order with you (even
    # though you may already be allied.)" -- a directed permission,
    # separate from the alliance relationship itself: the territory
    # *owner* grants a specific recruiter permission to recruit there
    # this gameturn. Pairs are ``(owner_kingdom_id, recruiter_kingdom_id)``.
    # No parser/decoder exists for a Treat order anywhere in this project
    # (same "no real order-file shape ever seen" category as Break Treaty
    # and Call-For-Vote -- see turn/emperor_election.py's own docstring),
    # so this is populated directly by the caller, not decoded from a
    # move file -- still "caller's job to clear at a turn boundary," not
    # auto-cleared by anything here, unlike recruited_this_turn/
    # ArmyState.movement_points, which Phase 573's own `turn/turn_
    # processor.py _replenish_turn_scoped_state()` now resets instead.
    treat_permissions: set[tuple[int, int]] = field(default_factory=set)
    # Feature instances (Phase 75) -- see models/feature.py's own docstring
    # for why this is a flat dict-by-id, mirroring `armies`/`provinces`,
    # not a per-province list (Pascal's own `fx`/`fy` arrays are keyed by
    # feature-instance number, not by province).
    features: dict[int, Feature] = field(default_factory=dict)
    # Global first-inventor registry for Discoveries (Phase 271) -- see
    # MeritTally's own docstring for why this was the missing piece
    # blocking discoveries_found_first/discoveries_found_not_first.
    # Unlike Feature.discovered_by_kingdom (per-instance, since many
    # Kingdoms can each hold their own copy of the same feature-type
    # knowledge independently), a Discovery is one shared, world-wide
    # invention -- Discovery.LAND_SHIP either has a first inventor or it
    # doesn't, game-wide. Written once, permanently, the instant any
    # Kingdom's own KingdomState.discoveries gains an entry no other
    # Kingdom's own set already held (turn/practice_execution.py
    # execute_practice()'s own SAGE branch) -- never overwritten
    # afterward, even if that Kingdom is later destroyed.
    discoveries_first_found_by: dict[Discovery, int] = field(default_factory=dict)
    # Leader-held magic-item instances (Phase 140) -- see models/item.py's
    # own docstring for the RUMORS.PAS Add_Tr/treaslist/trowner/trcharges
    # source and its deliberate leader-only scope.
    items: dict[int, ItemInstance] = field(default_factory=dict)
    # Rumors heard (Phase 243) -- see models/rumor.py's own docstring
    # and turn/rumor.py's own trigger/selection/falsification logic.
    # Append-only, mirroring the battle-death graveyard's own "no
    # turn-events log yet" registry pattern.
    rumors: dict[int, Rumor] = field(default_factory=dict)
    # Gate Angel / VALHALLA (Phase 194, corrected Phase 195) -- see module
    # docstring. The current reservoir-sampling winner: which kingdom
    # gets this turn's Valhalla visit, and when. May be overwritten
    # more than once within a single turn as later candidates win the
    # swap -- the value once a turn's dispatch fully completes is
    # authoritative.
    last_gate_angel_turn: int | None = None
    last_gate_angel_kingdom: int | None = None
    # Which of the 5 GATE_ANGEL_ELIGIBLE_ALIGNMENTS have already had
    # their turn in the current 5-turn rotation cycle -- cleared once
    # all 5 have been used.
    gate_angel_cycle_visited: set[Alignment] = field(default_factory=set)
    # This turn's due alignment, decided (and cached) the first time any
    # Gate Angel cast is attempted that turn.
    gate_angel_due_alignment: Alignment | None = None
    gate_angel_due_alignment_turn: int | None = None
    # Reservoir-sampling counter: how many successful due-alignment
    # candidates have been seen so far this turn.
    gate_angel_candidates_this_turn: int = 0
    # Phase 386: per-alignment (current_roster_index, signed_stride) for
    # turn/valhalla_execution.py's own post-turn-5 visitor selection --
    # AKGEN's confirmed "advance with a randomly signed coprime stride,
    # producing a full permutation before repetition." Lazily populated
    # on that alignment's first post-turn-5 visit; absent entries mean
    # "not yet started" (turns 1-5 use the roster's own final record
    # instead, needing no sequence state at all).
    valhalla_visitor_sequence: dict[Alignment, tuple[int, int]] = field(default_factory=dict)
    # Phase 387: how many of this (leader, Ability) pair's own per-turn
    # action-cast slots (``turn/cast_execution.py action_cast_slots()``,
    # AKGEN's confirmed ``action_slots_per_school``) have already been
    # consumed this turn. Cleared to ``{}`` at the end of every
    # ``run_turn()`` call, alongside ``recruited_this_turn``/``ArmyState.
    # movement_points``'s own replenishment (Phase 575 -- audited and
    # fixed after Phase 573 missed it).
    action_casts_used: dict[tuple[int, Ability], int] = field(default_factory=dict)
    # Phase 392: army ids a Werebeast column-win's own confirmed 40%
    # "bite" roll (AKGEN's `battle_engine.special_events` "Werebeasts
    # defeat humanoids") has queued for the real, real-formula-confirmed
    # end-of-turn race transformation into Werebeasts (fleets excluded,
    # per AKGEN's own text) -- see ``turn/battle_orchestrator.py``'s own
    # Phase 392 addendum for where this is populated (mid-battle, at
    # ``resolve_battle``'s own per-column granularity) and ``turn/
    # turn_processor.py _apply_werebeast_transformations()`` for where
    # it's drained, once, at the very end of ``run_turn()``.
    werebeast_bitten_army_ids: set[int] = field(default_factory=set)
    # Emperor election (Phase 228, turn/emperor_election.py) -- rulebook
    # [10.2]. `emperor_kingdom_id` persists once a vote actually elects
    # someone (a failed/no-quorum vote never clears it -- see that
    # module's own docstring); `last_emperor_vote_turn` records the turn
    # a vote was last *held* (win or not), the state the "not two turns
    # in a row" ban is checked against.
    emperor_kingdom_id: int | None = None
    last_emperor_vote_turn: int | None = None
    # Phase 466: this project's own reading of the real Pascal `req_vote`
    # global (report SS12.1/13.4-13.5) -- the turn a vote will actually
    # be *tallied* on, if `turn/emperor_election.py evaluate_election_
    # call()` scheduled one (`election_scheduled_next_turn`). `None`
    # means no election is currently pending. Cleared back to `None` by
    # `process_election_turn()` once that turn's vote is tallied (win,
    # loss, or no quorum -- a vote being *held* clears the pending state
    # regardless of its own outcome, same as `Refresh_Moves`'s own
    # per-Kingdom `kprevgold` reset described in report SS12.2).
    election_pending_turn: int | None = None
    # GENERAL INTELLIGENCE REPORT's own raw material (Phase 231) -- see
    # WorldEvent's own docstring. Populated by a caller (``report/
    # turn_report.py record_battle_world_events()`` today, the one real
    # populating path so far) once per turn, *before* any
    # ``compose_letter_report()`` call for that turn -- every King's own
    # report reads the same shared list, filtered by ``is_visible_to()``.
    world_events: list[WorldEvent] = field(default_factory=list)
    # Phase 711 -- the ACTION REPORT's own richer, per-Kingdom battle
    # narrative (`report/turn_report.py describe_battle()`, wired via
    # the new `record_battle_narratives()`), keyed by `kingdom_id`.
    # Distinct from `world_events` above: this is real, sourced detail
    # (leader roster, per-column clashes, retreats, ...) visible only to
    # the two Kingdoms actually involved in each battle, not a turn-
    # global broadcast -- both mechanisms coexist, populated from the
    # same underlying `BattleReport`s. Same "accumulates for the turn,
    # no explicit reset, no multi-turn game loop exists yet for it to
    # matter" convention as `world_events`/`rumors`/`turn_raid_events`.
    battle_narratives_by_kingdom: dict[int, list[str]] = field(default_factory=dict)
    # Phase 713 -- AdvancedAbility.SPY_BLACKMAIL's own demand-delivery
    # notice, keyed by kingdom_id -- both the blackmailer's own Kingdom
    # and the victim Kingdom receive the identical rendered text (one
    # shared `render_blackmail_demand()` call, same "both sides get the
    # same rendered lines" reasoning as `battle_narratives_by_kingdom`
    # above). Populated once per turn by `report/turn_report.py record_
    # blackmail_narratives()`, the same "before any `compose_letter_
    # report()` call" contract as that sibling dict.
    blackmail_narratives_by_kingdom: dict[int, list[str]] = field(default_factory=dict)
    # Phase 408 -- mirrors `RUMORS.PAS`/`REPORTS.PAS`'s own `kkmet` bitmask
    # (`Check_KKSugg`, `REPORTS.PAS` ~173-202): once two kingdoms' own
    # territories have ever bordered each other, `frozenset({a, b})` is
    # added here and never removed -- a monotone "have we ever had
    # diplomatic contact" fact, distinct from `allied_kingdoms` (an
    # alliance is a separate, revocable relationship; this is a one-way
    # ratchet). See `turn/world_events.py record_kingdom_contacts()`'s
    # own docstring for the real `Get_News()` clause this feeds and for
    # why only this one clause of that function is implemented.
    kingdoms_met: set[frozenset[int]] = field(default_factory=set)
    # Phase 491 -- a turn-stamped companion to ``kingdoms_met`` above:
    # the turn number each pair was *first* added there. ``kingdoms_met``
    # alone is a pure boolean ratchet with no time dimension, but the
    # World Emperor/Imperial Treasurer perks (``OFFICE_PERK_DESCRIPTION``,
    # Phase 103: "Only the tax bases/Treasuries of kings bordering your
    # kingdom that you have known for at least one full turn will be
    # shown") need exactly that -- see ``has_met_for_full_turn()`` below
    # and ``turn/world_events.py record_kingdom_contacts()``'s own Phase
    # 491 addendum, the only write site. A pair present here is always
    # also present in ``kingdoms_met`` (written together, same call),
    # but never removed once set, same one-way-ratchet convention.
    kingdoms_met_since: dict[frozenset[int], int] = field(default_factory=dict)
    # Phase 643 -- ``RUMORS.PAS``'s own ``kexch[giver,receiver]``: which
    # Discovery was most recently exchanged in this *directed* pair via
    # a Scientific Treaty ([8.4], ``turn/scientific_treaty.py execute_
    # scientific_treaties()``, the only writer). Keyed by an ordered
    # ``(giver_kingdom_id, receiver_kingdom_id)`` tuple -- not a
    # ``frozenset`` like ``kingdoms_met`` above, since direction matters
    # here ("received from" vs. "sent to" are different report lines).
    # A single value per pair, matching the real Pascal's own single-
    # slot 2D array: a later exchange between the same two Kingdoms
    # silently overwrites an earlier one rather than accumulating, a
    # real, sourced limitation reproduced here, not a design choice of
    # this port's own. Feeds the FINANCES report's own "(Received from
    # player(s) #k1... by scientific treaty)"/"(Sent to player(s) #k1...
    # by scientific treaty)" lines (``report/turn_report.py describe_
    # finances_report()``) -- confirmed *not* related to espionage-
    # obtained Discoveries at all (``MeritTally.discoveries_via_
    # espionage`` is a separate, already-modeled counter with no
    # per-source text of its own -- see ``turn/scientific_treaty.py``'s
    # own module docstring).
    discovery_exchanged_from: dict[tuple[int, int], Discovery] = field(default_factory=dict)
    # Phase 475: AKGEN_reverse_engineering_report (2).md SS14.4's own
    # tier-1 tie-break, "per i titoli avanzati, il titolare precedente
    # conserva precedenza se è fra i pari" (for advanced titles, the
    # previous titleholder retains precedence if tied) -- the last
    # Office resolution's own winner, keyed by Office, leader_id valued.
    # Written by ``turn/office_holder.py commit_office_holders()``, read
    # by ``resolve_office_holder()``'s own tie-break -- see that
    # function's docstring for why this is a caller-invoked commit step
    # rather than something ``resolve_office_holder()`` updates itself
    # (reading and writing the same "current" state in one resolution
    # pass would make the tie-break see this turn's own still-in-
    # progress winner instead of last turn's settled one). Never cleared
    # automatically -- a title that currently has no qualifying
    # candidate keeps its last known holder here (a title doesn't lose
    # its "was recently held by" precedent just because nobody
    # qualifies for a turn or two), the same "stale until overwritten"
    # convention as `discoveries_first_found_by`.
    office_holders: dict[Office, int] = field(default_factory=dict)
    # Phase 633: the same Phase 475 tier-1 stickiness tie-break, for the
    # 3 army-scoped Royal Titles (`turn/office_holder.py ARMY_RANKED_
    # OFFICES` -- Airforce/Praetor/Flagship, Phase 394) -- **not** folded
    # into `office_holders` above, deliberately: that dict is `leader_id`
    # valued, and leader ids/army ids are separate integer namespaces
    # that can collide numerically, so mixing both kinds of id under one
    # untyped `dict[Office, int]` risks a future reader assuming every
    # entry is a `leader_id` and mis-resolving (or crashing) for one of
    # these 3. Written by `commit_army_office_holders()`, read by
    # `resolve_army_office_holder()`'s own tie-break -- same "caller-
    # invoked commit step, never cleared automatically" shape as
    # `office_holders` itself.
    army_office_holders: dict[Office, int] = field(default_factory=dict)
    # Phase 614: the Grandfather of Assassins title's own free-attempt
    # queue -- `turn/plan_dispatch.py _dispatch_fire()` sets this instead
    # of running an ordinary Fire when the order-giver holds Office.
    # ASSASSIN and the FI target is a non-King leader in a different
    # Kingdom (a disassembly-confirmed reinterpretation of the FI order,
    # `AK.EXE:0xCD0D-0xCD39`, user-supplied 2026-08-22). A single global
    # slot, not a list -- the real engine keeps exactly one turn-scoped
    # target (`AK.EXE:0x17851`'s own `mov word [EE30h],00FFh` reset), so
    # a second real FI interception the same turn simply overwrites the
    # first rather than queuing both ("l'ultimo bersaglio sovrascrive i
    # precedenti", a confirmed real anomaly, not a bug to fix here).
    # Read and always cleared back to `None` by `turn/assassin_guild.py
    # resolve_pending_guild_assassination()`, called once per turn from
    # `orchestrator.py process_turn()` right after `run_turn()` (battles
    # for the turn are already resolved by then, matching the real "end
    # of phase 5, after battles" resolution timing).
    pending_guild_target: int | None = None

    def add_kingdom(self, kingdom: KingdomState) -> None:
        self.kingdoms[kingdom.kingdom_id] = kingdom

    def add_province(self, province: ProvinceState) -> None:
        self.provinces[province.coord] = province

    def add_army(self, army: ArmyState) -> None:
        self.armies[army.army_id] = army

    def remove_army(self, army_id: int) -> None:
        self.armies.pop(army_id, None)

    def new_army_id(self) -> int:
        """Next unused army id (1 above the current highest, or 1 if none exist)."""

        return max((*self.armies.keys(), 0)) + 1

    def add_leader(self, leader: LeaderState) -> None:
        self.leaders[leader.leader_id] = leader

    def record_battle_death(self, coord: HexCoord, army_type: ArmyType, quality: Quality, kingdom_id: int | None) -> None:
        """Appends one ``GraveyardEntry`` for a genuine battle death at ``coord`` -- see
        module docstring for exactly which destruction sites call this.
        Stamps ``death_seq`` from ``graveyard_death_counter`` (Phase 309)
        so ``turn/skeletal_decay.py`` can later tell which entries died
        longest ago, then advances the counter.
        """

        self.battle_graveyard.setdefault(coord, []).append(
            GraveyardEntry(army_type, quality, kingdom_id, death_seq=self.graveyard_death_counter)
        )
        self.graveyard_death_counter += 1

    def remove_leader(self, leader_id: int) -> None:
        """Removes a leader from play, archiving it into ``dead_leaders`` (Phase 59) so a
        later Resurrection has something to revive -- see module docstring.

        **Phase 259 -- King succession**: sourced directly from RULES.AK
        [2.1] "Kings" and [4.21.1] "Resurrect character" (also SAY.PAS
        ``_LSucc``: "<3 was succeeded by > next-in-line (who will use >
        predecessor's name until next turn)."). If the removed leader was
        a King in active service (``is_king`` and ``kingdom_id is not
        None``), a Royal Heir is installed on the throne immediately,
        under the same ``leader_id`` (the "next-in-line" the quote
        describes) -- the Kingdom is never left permanently Kingless the
        way it silently was before this phase. The Heir starts with the
        same automatic training bonus a fresh King gets at creation
        (**Phase 552 correction**, sourced from
        ``AKGEN_reverse_engineering_report (5).md`` SS6.2, machine-verified
        against ``AK.EXE:0x1D8E8`` and ``AKE.EXE:0xC143-0xC191``):
        Melee/Archery/Sage each at skill 1, aptitude 3 (``min(1+2, 5)``,
        matching ``turn/succession.py``'s own ``KING_TRAINING_BONUS_
        ABILITIES``/``_ordinary_aptitude()`` for a freshly-created King),
        every other ability at 0 -- not the fully-zeroed table this phase
        used to install. This is also why the real "``Total_USkill < 7``"
        Resurrection/report-display threshold (``turn/cast_execution.py
        is_unfinalized_royal_heir()``) works out to 3 (this baseline) + 4
        (the player's later ``(K)g Ab`` points), not 0 + 7.

        **Phase 557 audit note**: the user's own ``SUCCESSIONE.txt``
        (project-original rules notes, Desktop root) describes this
        reset differently -- "un Royal Heir... con tutti talenti e
        potenzialità a zero" ("...with all Talents and Potentials at
        zero"), with the +1 training bonus described only as part of
        the *later* ``create_king()`` step, not the Heir's initial
        state. Flagged to the user as a direct conflict with SS6.2
        above; **confirmed by the user (project author): the
        disassembly-sourced report governs**, this Phase 552 baseline
        stays as implemented. Documented here so a future audit of
        ``SUCCESSIONE.txt`` doesn't re-flag the same already-resolved
        conflict.

        The Heir also keeps the dead King's own ``name`` (per the quote above),
        ``location``, ``temper``, ``alignment``, and ``race`` (race/
        alignment can't change across a succession -- the Heir carries
        the same lineage), and is flagged ``is_royal_heir=True`` -- see
        that field's own docstring for what reads/clears it. The
        player-facing order to actually assign the new King's own name/
        temper/skill distribution (RULES.AK [2.1]'s 4-point allocation)
        is handled separately by ``turn/succession.py create_king()``
        (Phase 260).

        A King with no ``kingdom_id`` isn't a reachable state in this
        project (``turn/kingdom_bridge.py`` only ever sets ``is_king``
        alongside a real ``kingdom_id``) -- an ordinary Hero (or such a
        King, if one somehow existed) simply vanishes, unchanged from
        before this phase.
        """

        leader = self.leaders.pop(leader_id, None)
        if leader is None:
            return
        # Phase 377: the real, disassembly-confirmed 25% office-merit
        # death penalty -- see MeritTally.apply_death_penalty()'s own
        # docstring. Applied to the archived leader's own tally so a
        # future Resurrection (this same leader, from dead_leaders)
        # reflects the real reduced total rather than a stale
        # pre-death one.
        leader.merit_tally.apply_death_penalty()
        self.dead_leaders[leader_id] = leader
        if leader.is_king and leader.kingdom_id is not None:
            heir_skills = SkillTable(raw_values=[0] * 31)
            for bonus_ability in (Ability.MELEE, Ability.ARCHERY, Ability.SAGE):
                heir_skills.set_pair_for_ability(bonus_ability, skill=1, aptitude=3)
            self.leaders[leader_id] = LeaderState(
                leader_id=leader_id,
                kingdom_id=leader.kingdom_id,
                name=leader.name,
                location=leader.location,
                skills=heir_skills,
                is_king=True,
                temper=leader.temper,
                alignment=leader.alignment,
                race=leader.race,
                is_royal_heir=True,
            )

    def armies_at(self, coord: HexCoord) -> list[ArmyState]:
        return [army for army in self.armies.values() if army.location == coord]

    def leaders_at(self, coord: HexCoord) -> list[LeaderState]:
        return [leader for leader in self.leaders.values() if leader.location == coord]

    def add_feature(self, feature: Feature) -> None:
        self.features[feature.feature_id] = feature

    def new_feature_id(self) -> int:
        """Next unused feature-instance id (1 above the current highest, or 1 if none
        exist) -- mirrors ``new_army_id()``/``new_item_id()``'s own monotonic
        allocation. Phase 242's own ``turn/world_generation.py`` is the first
        caller.
        """

        return max((*self.features.keys(), 0)) + 1

    def new_item_id(self) -> int:
        """Next unused item-instance id (1 above the current highest, or 1 if none exist) --
        mirrors ``new_army_id()``'s own monotonic allocation; see
        ``models/item.py``'s own docstring for why this doesn't replicate
        Pascal ``Add_Tr``'s free-slot-reuse scan.
        """

        return max((*self.items.keys(), 0)) + 1

    def add_item(self, treasure: Treasure, owner_leader_id: int | None, charges: int = 0) -> ItemInstance:
        """Create a new item instance, auto-assigning its id -- mirrors Pascal ``Add_Tr(tr,
        tow, tch)`` (see ``models/item.py``'s own docstring). ``charges`` is
        masked to a byte, matching the Pascal source's own ``tch and 255``.
        """

        item = ItemInstance(self.new_item_id(), treasure, owner_leader_id, charges & 255)
        self.items[item.item_id] = item
        return item

    def items_held_by(self, leader_id: int) -> list[ItemInstance]:
        """All item instances currently owned by ``leader_id`` -- mirrors Pascal's own
        ``FOR tn:= 0 TO ntreasures-1 DO IF trowner[tn] = tro`` inventory
        loop (``REPORTS.PAS``, ~line 540).
        """

        return [item for item in self.items.values() if item.owner_leader_id == leader_id]

    def remove_item(self, item_id: int) -> None:
        """Removes an item instance from play -- a self-consuming Skill Book's own fate
        after ``turn/use_mi_execution.py`` reads it (rulebook [5.9]; the
        Pascal source has no explicit "delete" analogue, but a consumed
        book has no owner and no further use, so dropping it from the
        registry entirely is the natural mirror of ``remove_army()``'s
        own "gone, not just unowned" convention).
        """

        self.items.pop(item_id, None)

    def transfer_item(self, item_id: int, new_owner_leader_id: int | None) -> None:
        """Reassign an item instance's owner -- mirrors a direct Pascal ``trowner[tn]:=
        ...`` assignment (e.g. Give's item path, or ``REPORTS.PAS``'s own
        quest-fulfillment cleanup setting ``trowner[tn]:= noleader``). A
        missing ``item_id`` is silently a no-op, the same "nothing to do"
        convention ``remove_army()`` already uses for an unknown id.
        """

        item = self.items.get(item_id)
        if item is not None:
            item.owner_leader_id = new_owner_leader_id

    def features_at(self, coord: HexCoord) -> list[Feature]:
        return [feature for feature in self.features.values() if feature.coord == coord]

    def new_rumor_id(self) -> int:
        """Next unused rumor id (1 above the current highest, or 1 if none exist) --
        mirrors ``new_army_id()``/``new_item_id()``/``new_feature_id()``'s
        own monotonic allocation. ``turn/rumor.py`` is the one caller.
        """

        return max((*self.rumors.keys(), 0)) + 1

    def add_rumor(self, rumor: Rumor) -> None:
        self.rumors[rumor.rumor_id] = rumor

    def rumors_heard_by(self, kingdom_id: int) -> list[Rumor]:
        return [rumor for rumor in self.rumors.values() if rumor.kingdom_id == kingdom_id]

    def armies_commanded_by(self, leader_id: int) -> list[ArmyState]:
        return [army for army in self.armies.values() if army.commanded_by == leader_id]

    def mercenaries_at(self, coord: HexCoord) -> list[ArmyState]:
        return [army for army in self.armies.values() if army.location == coord and army.kingdom_id is None]

    def independent_heroes_at(self, coord: HexCoord) -> list[LeaderState]:
        return [leader for leader in self.leaders.values() if leader.location == coord and leader.kingdom_id is None]

    def is_allied(self, kingdom_a: int | None, kingdom_b: int | None) -> bool:
        if kingdom_a is None or kingdom_b is None:
            return False
        if kingdom_a == kingdom_b:
            return True
        return frozenset({kingdom_a, kingdom_b}) in self.allied_kingdoms

    def has_met(self, kingdom_a: int | None, kingdom_b: int | None) -> bool:
        """Phase 408 -- mirrors ``kkmet``'s own read side (``SAY.PAS`` ~101,
        ``Get_News``'s ``kkmet[Min(kng,playking)] and (1 Shl Max(kng,playking))``
        test). See ``kingdoms_met``'s own field docstring.
        """

        if kingdom_a is None or kingdom_b is None:
            return False
        if kingdom_a == kingdom_b:
            return True
        return frozenset({kingdom_a, kingdom_b}) in self.kingdoms_met

    def has_met_for_full_turn(self, kingdom_a: int | None, kingdom_b: int | None) -> bool:
        """Phase 491 -- World Emperor/Imperial Treasurer's own "known for
        at least one full turn" gate. ``True`` for the same-kingdom case
        (mirrors ``has_met()``'s own convention), ``False`` if either is
        ``None`` or the pair has no recorded first-contact turn yet.
        """

        if kingdom_a is None or kingdom_b is None:
            return False
        if kingdom_a == kingdom_b:
            return True
        first_contact_turn = self.kingdoms_met_since.get(frozenset({kingdom_a, kingdom_b}))
        if first_contact_turn is None:
            return False
        return self.turn_number - first_contact_turn >= 1

    def has_treat_permission(self, owner_kingdom_id: int, recruiter_kingdom_id: int) -> bool:
        """Whether ``owner_kingdom_id`` has issued a Treat order this turn
        permitting ``recruiter_kingdom_id`` to recruit in his territory --
        see ``treat_permissions``'s own docstring."""

        return (owner_kingdom_id, recruiter_kingdom_id) in self.treat_permissions

    def friendly_provinces_for(self, kingdom_id: int) -> set[HexCoord]:
        """Provinces owned by ``kingdom_id`` or one of its allies."""

        return {
            province.coord
            for province in self.provinces.values()
            if province.owner_kingdom_id is not None and self.is_allied(province.owner_kingdom_id, kingdom_id)
        }

    def record_world_event(self, coord: HexCoord, lines: list[str]) -> None:
        """Appends one ``WorldEvent`` at ``coord`` -- see that class's own
        docstring for GENERAL INTELLIGENCE REPORT's own real raw material
        (Phase 231).
        """

        self.world_events.append(WorldEvent(coord, lines))
