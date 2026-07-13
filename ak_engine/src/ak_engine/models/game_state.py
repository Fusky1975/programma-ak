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
  boundary -- same "caller's job" convention as ``recruited_this_turn``/
  ``ArmyState.movement_points`` -- and, as of Phase 59, **not yet read
  by any consumer** (``turn/movement.py``, ``turn/strength.py``, etc.
  still use ``ProvinceState.terrain`` directly): the spells write real
  state, a later phase still needs to make movement/battle honor it.
- ``ProvinceState.tax_modifier_percent`` (Bless, Earthquake): a signed
  percent (+60 / -100, matching each spell's exact rulebook number, and
  each spell *sets* rather than adds since both are documented "not
  cumulative"). **No tax/revenue-collection system exists anywhere in
  this project yet** (recruit/hire spend from ``KingdomState.treasury``,
  but nothing computes or credits per-turn tax income), so this field
  currently has no consumer either -- same "spell writes real state,
  nothing reads it yet" situation as ``terrain_override``.
- ``ProvinceState.illusory_terrain`` (Illusory Terrain): the fake
  terrain an outside observer would be told the province is. Same "no
  consumer yet" situation -- no exploration/movement code distinguishes
  real vs. illusory terrain today.
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
  rank twice; not auto-cleared at a turn boundary, same convention as
  every other "caller's job to reset" field in this dataclass.

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
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.feature import Feature
from ak_engine.models.item import ItemInstance
from ak_engine.models.kingdom import SkillTable
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.race import Race
from ak_engine.models.temper import Temper
from ak_engine.models.treasure import Treasure
from ak_engine.turn.combat import Quality


@dataclass(slots=True)
class KingdomState:
    kingdom_id: int
    name: str
    race: Race
    alignment: Alignment
    home_province: HexCoord
    treasury: int = 0


@dataclass(slots=True)
class ArmyState:
    army_id: int
    kingdom_id: int | None  # None = unowned mercenary
    army_type: ArmyType
    quality: Quality
    location: HexCoord
    unhireable_this_turn: bool = False
    # Remaining this gameturn. Not auto-reset at turn start and not derived
    # from ARMY_TABLE speed + March/Naval ability -- the caller sets it.
    movement_points: int = 0
    # Which leader currently leads this army, if any (rulebook: an army may
    # also be unled, under the "garrison commander"). Set/cleared by
    # Leave/Pick_Up (turn/plan_dispatch.py); None means unled.
    commanded_by: int | None = None


@dataclass(slots=True)
class LeaderState:
    leader_id: int
    kingdom_id: int | None  # None = independent Hero, not in any kingdom's service
    name: str
    location: HexCoord
    # None = no ability data recorded for this leader -- see module docstring.
    skills: SkillTable | None = None
    # King/Hero distinction (Phase 40) -- see module docstring.
    is_king: bool = False
    # Phantasmal Armies' strength bonus level (Phase 59) -- see module docstring.
    phantasmal_armies_level: int = 0
    # Oratory idempotency flag (Phase 59) -- see module docstring.
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


@dataclass(slots=True)
class ProvinceState:
    coord: HexCoord
    terrain: Terrain
    race: Race
    owner_kingdom_id: int | None = None
    explored_percent: int = 0
    contested_by_kingdom_id: int | None = None
    # How many of each ArmyType have been recruited from this province so
    # far this gameturn (rulebook [3.4]: normally 1 per type per province
    # per turn, 2 in a King's home province). Not auto-reset at turn start
    # -- the caller clears it, same convention as ArmyState.movement_points.
    recruited_this_turn: dict[ArmyType, int] = field(default_factory=dict)
    # Part Sea / Flood Province (Phase 59) -- see module docstring.
    terrain_override: Terrain | None = None
    # Bless / Earthquake (Phase 59) -- see module docstring.
    tax_modifier_percent: int = 0
    # Illusory Terrain (Phase 59) -- see module docstring.
    illusory_terrain: Terrain | None = None
    # Per-kingdom exploration progress (Phase 69) -- see module docstring.
    # Distinct from `explored_percent` above (a single shared scalar,
    # unable to answer "how much has *this* kingdom explored" for the
    # rulebook [6.3] exploration-advantage strength bonus).
    explored_percent_by_kingdom: dict[int, int] = field(default_factory=dict)


@dataclass(slots=True)
class GraveyardEntry:
    army_type: ArmyType
    quality: Quality  # rank at time of death
    kingdom_id: int | None  # who owned it -- reference only, not read by any consumer yet


@dataclass(slots=True)
class GameState:
    turn_number: int = 1
    kingdoms: dict[int, KingdomState] = field(default_factory=dict)
    provinces: dict[HexCoord, ProvinceState] = field(default_factory=dict)
    armies: dict[int, ArmyState] = field(default_factory=dict)
    leaders: dict[int, LeaderState] = field(default_factory=dict)
    # Archived by remove_leader() (Phase 59) -- see module docstring. Keyed
    # by the same leader_id, so a resurrection can look it up directly.
    dead_leaders: dict[int, LeaderState] = field(default_factory=dict)
    # Battle deaths only (Phase 60) -- see module docstring.
    battle_graveyard: dict[HexCoord, list[GraveyardEntry]] = field(default_factory=dict)
    allied_kingdoms: set[frozenset[int]] = field(default_factory=set)
    # Feature instances (Phase 75) -- see models/feature.py's own docstring
    # for why this is a flat dict-by-id, mirroring `armies`/`provinces`,
    # not a per-province list (Pascal's own `fx`/`fy` arrays are keyed by
    # feature-instance number, not by province).
    features: dict[int, Feature] = field(default_factory=dict)
    # Leader-held magic-item instances (Phase 140) -- see models/item.py's
    # own docstring for the RUMORS.PAS Add_Tr/treaslist/trowner/trcharges
    # source and its deliberate leader-only scope.
    items: dict[int, ItemInstance] = field(default_factory=dict)

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
        """

        self.battle_graveyard.setdefault(coord, []).append(GraveyardEntry(army_type, quality, kingdom_id))

    def remove_leader(self, leader_id: int) -> None:
        """Removes a leader from play, archiving it into ``dead_leaders`` (Phase 59) so a
        later Resurrection has something to revive -- see module docstring.
        """

        leader = self.leaders.pop(leader_id, None)
        if leader is not None:
            self.dead_leaders[leader_id] = leader

    def armies_at(self, coord: HexCoord) -> list[ArmyState]:
        return [army for army in self.armies.values() if army.location == coord]

    def leaders_at(self, coord: HexCoord) -> list[LeaderState]:
        return [leader for leader in self.leaders.values() if leader.location == coord]

    def add_feature(self, feature: Feature) -> None:
        self.features[feature.feature_id] = feature

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

    def friendly_provinces_for(self, kingdom_id: int) -> set[HexCoord]:
        """Provinces owned by ``kingdom_id`` or one of its allies."""

        return {
            province.coord
            for province in self.provinces.values()
            if province.owner_kingdom_id is not None and self.is_allied(province.owner_kingdom_id, kingdom_id)
        }
