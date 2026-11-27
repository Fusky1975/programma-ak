"""Feature type and instance model (rulebook [3.2] Explore, [3.3] Search,
``HostAK/TP/CTBOTH.PAS`` `feature` enum) -- Phase 75, "Feature model
foundations". Replaces the earlier, never-populated ``models/map.py
Feature`` stub from Phase 1.

**Rulebook [3.2] Explore, quoted in full where relevant**: "The
character may Explore the province he is in, which allows a chance of
finding a feature such as a dungeon or pyramid. There can sometimes be
more than 1 feature in a province. The character is told the name of
the feature, the treasure that legend says lies within, and the
monster guarding the treasure... Sometimes you get rumours of
previously unheard-of features in your turn reports. About half of
these rumours are true, but the rest are false in some respect: the
treasure may not actually be there, and/or the feature may be in a
different province."

**Rulebook [3.3] Search feature, quoted in full**: "A character may
Search any feature that has been discovered by his kingdom, or that he
hears about from another King. When a character Searches a feature, he
must face the guardian monster first. He specifies an Encounter Plan.
If he defeats the monster, the treasure in the feature is his...
Searching a feature can also trigger a special event... A character may
Search a feature in a province he does not own, or a feature they have
not discovered yet, if they know the location and feature number.
Characters must Search features as individuals; it is a point of honor
to defeat a monster in single combat. Armies may not Search features,
although a character may Search a feature while leading an army."

**The Pascal `feature` type is an enum of feature *kinds*, not a
record** (``CTBOTH.PAS`` ~line 781-788) -- confirmed there is no
``featrec``/``TFeature`` record type anywhere in the available source.
32 declared values (31 real kinds + ``Noftype``, itself a real "generic
encounter area" sentinel -- its own printable name is literally
"encounter area", not a placeholder) plus 10 unused extension slots
(``ef1``-``ef10``) omitted here, the same convention ``models/map.py
Terrain``/``models/monster.py Monster`` already use for their own
unreferenced extension slots.

**A feature *instance* ("this specific dungeon at this specific spot")
is a set of parallel global arrays indexed by a feature-instance number
``fn`` (``featrange = 0..230``, ``CTBOTH.PAS`` line 28/36), never
declared as a record either -- the same "flat parallel arrays, not a
class" shape this project has already translated into a dict-by-id for
every other Pascal entity (``GameState.provinces``/``armies``). No
Pascal source anywhere in the archive *creates* a feature instance
(assigns ``fx``/``fy``/``ftype``/``fmonst``) -- world generation (which
~230 features exist, where, what kind, guarded by what) lived
exclusively in the missing main turn-processor, the same "missing
main file" gap this project has already declared for hex adjacency
(``turn/movement.py``) and magic-item-instance creation
(``turn/use_mi_decode.py``). **Not attempted here**: this phase builds
the *type* and *instance shape*, not a way to populate a fresh game's
feature roster from nothing.

**Confirmed fields, from `REPORTS.PAS`'s own feature-report-printing
code (~line 2032-2080), the only place any of these arrays are ever
*read*** (quoted structure, not verbatim Pascal):

- ``fx[fn]``/``fy[fn]``: the feature's own province coordinate --
  **not** a property of ``ProvinceState``. Confirmed directly:
  ``REPORTS.PAS`` scans *every* feature instance filtering by matching
  coordinate (``IF fx[fn] = px THEN IF fy[fn] = py THEN ...``), and a
  province only carries a *presence bitflag*
  (``provpres[px,py] and 16``, "this province has >=1 feature") --
  the report-printing loop explicitly handles more than one feature
  sharing a coordinate, matching [3.2]'s own "can sometimes be more
  than 1 feature in a province."
- ``ftype[fn]``: the feature's own ``feature`` enum value (kind).
- ``fmonst[fn]``: the guardian's ``monster`` enum value
  (``models/monster.py Monster``).
- ``fstate[fn]``: only one value was referenced in the source available
  at the time this note was written, ``Dead`` -- printed as "sacked &
  looted" when true, and used to gate whether the guardian's name is
  shown at all -- modeled as ``looted: bool``. **Stale as of Phase
  670**: ``Desktop/THUNDERBIRD.md`` (2026-08-28) recovers the full
  8-value ``fstate`` enum (Dead/Hired/Mercenary/Zomboid/Bold/Sold/
  Loser/Calm) and the monster-raid state machine that drives it --
  already modeled verbatim as ``models/monster.py
  MonsterEngagementState``. ``Feature.guardian_state`` below tracks it,
  kept independent of ``looted`` (still the one true "is this guardian
  dead" bit) rather than folding Dead into the new enum's own live
  value.
- ``fdisc^[playking,fn]``: a **per-kingdom** discovery level, ``CASE``
  -dispatched to exactly 3 meaningful values: ``1`` = detected but
  riches unknown (prints "?"), ``2`` = a magic-power hint is known
  (a parity-disambiguated half of a "effect/other_effect"-joined
  string, see ``report/prose.py``'s own ``/F`` marker note -- this
  project's own earlier-flagged mystery, now confirmed to be exactly
  this), ``3`` = fully known. ``0`` (the implicit "no case matched"
  default) is undiscovered. Modeled as ``discovered_by_kingdom:
  dict[int, int]``, the same per-kingdom-dict-with-0-default shape
  ``models/game_state.py ProvinceState.explored_percent_by_kingdom``
  already uses.

**A separate, distinct discovery-eligibility check exists in the same
Pascal code** (``IF fdis[fn] > 0``, a different array from
``fdisc[playking,fn]`` above) that gates whether the report entry
appears *at all* -- its exact relationship to the per-kingdom
``fdisc`` array (e.g. "has *any* kingdom ever discovered this") isn't
fully resolved from the available source and isn't modeled here as a
separate field; a future phase that needs it can revisit.

**Explicitly out of scope, confirmed structural gaps, not choices**:

- ~~**World generation**~~ -- **populating a fresh ``GameState`` with a
  feature roster now exists as of Phase 242** (``turn/world_generation.py
  generate_world_features()``), project-original throughout (no Pascal
  source survives -- ``AKGEN.EXE``, the real world-generator, is
  compiled-only, confirmed by an exhaustive archive listing). Reuses
  ``MONSTER_GUARDED_FEATURE_TYPES`` below (inverted) for guardian
  selection wherever it has real coverage; see that module's own
  docstring for the full density/terrain/guardian/treasure design and
  which numbers were confirmed directly with the user (project author).
- ~~**Rumor generation** ([3.2]'s "about half... false" mechanic) --
  still out of scope: the prose templates exist
  (``HostAK/TP/PROSE/FRUMOR.X``) but the selection/falsification logic
  doesn't, and Phase 242 only wired the *direct*-discovery half of
  [3.2] (``turn/exploration.py discover_features()``), not the
  separate "hear about a feature in another province" channel.~~ --
  **closed by Phase 243** (``turn/rumor.py``): the separate "hear
  about a feature in another province" channel is now a real,
  sourced-where-possible mechanic (trigger chance by order type,
  distance-2 eligibility, 70/30 monster-vs-treasure content split,
  50/50 truth roll), wired into ``plan_dispatch.py`` right alongside
  each order's own real effect.
- ~~**Search resolution**~~ **now exists as of Phase 132**
  (``turn/search_execution.py``), including treasure being actually
  granted to the winning leader as of Phase 242 (``GameState.
  add_item()``, Phase 140's own registry) rather than just a
  ``looted`` flag flip.
- ~~**Treasure *instances***: a feature's own treasure content isn't
  modeled here at all~~ **the full ``Treasure`` type catalog exists as
  of Phase 77** (``models/treasure.py``), and a feature's own treasure
  *instance* field (``Feature.treasure``) exists as of Phase 242,
  populated by world generation and consumed by a Search win.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from ak_engine.models.alignment import Alignment
from ak_engine.models.magic_feature import MagicFeature
from ak_engine.models.map import HexCoord
from ak_engine.models.monster import Monster, MonsterEngagementState
from ak_engine.models.power import Power
from ak_engine.models.treasure import Treasure


class FeatureType(Enum):
    PYRAMID = 0
    TOMB = 1
    CATACOMBS = 2
    CRYPT = 3
    CAVE = 4
    CAVERN = 5
    VOLC_TUNNEL = 6
    DUNGEON = 7
    MAZE = 8
    LABYRINTH = 9
    TOWER = 10
    CASTLE = 11
    GREAT_HALL = 12
    MONASTERY = 13
    TEMPLE = 14
    PET_FOREST = 15
    SACRED_ROCK = 16
    AS_MONUMENT = 17
    ALTAR = 18
    DES_RUINS = 19
    SUNK_CITY = 20
    LOST_CITY = 21
    LOST_TEMPLE = 22
    HOLLOW_TREE = 23
    GLADE = 24
    HANG_VALLEY = 25
    MOUNT_PEAK = 26
    MAG_POOL = 27
    LOCH = 28
    UND_CAVERN = 29
    MAELSTROM = 30
    NOFTYPE = 31


# CTBOTH.PAS `ftname`, verbatim, positional with the `FeatureType` ordinals above.
FEATURE_TYPE_NAMES: dict[FeatureType, str] = {
    FeatureType.PYRAMID: "Pyramid",
    FeatureType.TOMB: "Tomb",
    FeatureType.CATACOMBS: "Catacombs",
    FeatureType.CRYPT: "Crypt",
    FeatureType.CAVE: "Cave",
    FeatureType.CAVERN: "Cavern",
    FeatureType.VOLC_TUNNEL: "Volcanic Tunnel",
    FeatureType.DUNGEON: "Dungeon",
    FeatureType.MAZE: "Maze",
    FeatureType.LABYRINTH: "Labyrinth",
    FeatureType.TOWER: "Tower",
    FeatureType.CASTLE: "Castle",
    FeatureType.GREAT_HALL: "Great Hall",
    FeatureType.MONASTERY: "Monastery",
    FeatureType.TEMPLE: "Temple",
    FeatureType.PET_FOREST: "Petrified Forest",
    FeatureType.SACRED_ROCK: "Sacred Rock",
    FeatureType.AS_MONUMENT: "Ancient Megaliths",
    FeatureType.ALTAR: "Altar",
    FeatureType.DES_RUINS: "Desert Ruins",
    FeatureType.SUNK_CITY: "Sunken City",
    FeatureType.LOST_CITY: "Lost City",
    FeatureType.LOST_TEMPLE: "Lost Temple",
    FeatureType.HOLLOW_TREE: "Hollow Tree",
    FeatureType.GLADE: "Glade",
    FeatureType.HANG_VALLEY: "Hanging Valley",
    FeatureType.MOUNT_PEAK: "Mountain Peak",
    FeatureType.MAG_POOL: "Magic Pool",
    FeatureType.LOCH: "Loch",
    FeatureType.UND_CAVERN: "Undersea Cavern",
    FeatureType.MAELSTROM: "Maelstrom",
    FeatureType.NOFTYPE: "encounter area",
}


@dataclass(slots=True)
class Feature:
    feature_id: int  # index into the Pascal fx/fy/ftype/fmonst/fstate arrays, 0..230 (featrange)
    coord: HexCoord
    kind: FeatureType
    guardian_monster: Monster | None = None
    looted: bool = False  # fstate[fn] = Dead ("sacked & looted")
    # per-kingdom discovery level: 0 (default/undiscovered) .. 3 (fully known) -- see module docstring
    discovered_by_kingdom: dict[int, int] = field(default_factory=dict)
    # Phase 242: the treasure this feature holds -- world-generation-side
    # data (`turn/world_generation.py` assigns it), consumed by a
    # successful Search (`turn/search_execution.py` grants it to the
    # winning leader via `GameState.add_item()`, Phase 140's own
    # registry). `None` for a feature created without going through
    # world generation (e.g. most existing tests), matching this
    # project's established "no source, no silent default" convention.
    treasure: Treasure | None = None
    # Phase 246: the guardian's own Alignment -- `models/monster.py
    # roll_monster_alignment()` (Phase 176) existed as a pure, callable,
    # fully-tested mechanism with nothing to wire it to ("this project
    # still has none" of a world-generation pipeline, per that phase's
    # own note); `turn/world_generation.py` (Phase 242) closed that gap,
    # so `_create_feature()` now calls it here. `None` for a feature with
    # no guardian, or one created outside world generation (most existing
    # tests) -- same "no source, no silent default" convention `treasure`
    # above already established.
    guardian_alignment: Alignment | None = None
    # Phase 193: Hide Feature [4.23.3] ("This feature will become magically
    # hidden" -- models/power.py CAST_SPELL_FEATURE_DESCRIPTION corroborates
    # the same wording). No sourced duration exists anywhere (permanent vs.
    # "for the rest of the turn" vs. some other window is not stated). This
    # note's original "no consumer reads this flag yet" claim is stale --
    # `turn/exploration.py`/`turn/rumor.py` already read it, and Phase 670
    # (`Desktop/THUNDERBIRD.md`) reuses it as the monster-raid mechanic's own
    # "F_Hid gates a raid" gate, plus a genuinely new 10%-per-turn
    # dissipation roll (`turn/monster_raids.py maybe_dissipate_hidden_
    # feature()`).
    magically_hidden: bool = False
    # Phase 258: which leader (if any) currently holds a Talk-secured
    # "deal" with this feature's own guardian, pending a later turn's
    # Fulfill -- rulebook [5.6]/[5.7]'s own "dopo aver accettato le sue
    # condizioni" ("after accepting its conditions") reads as a deal
    # persisting *across* turns, not within the same Encounter Plan
    # ("Talk and Fulfill can't both be used in the same Encounter Plan").
    # Set by `turn/search_execution.py`'s own Talk `DEAL` reaction branch,
    # consumed (cleared either way) by its Fulfill branch -- see `turn/
    # encounter.py resolve_fulfill_honored()`'s own module comment for
    # the honor-roll formula. `None` means no deal is currently pending.
    pending_deal_leader_id: int | None = None
    # The turn from which the pending deal can be fulfilled, for the one agreement that is tied to a date: the old
    # monster who asks for someone to look after it "for the rest of my life ... I have, perhaps, 2 years left to live"
    # (``MonsterTalkReply.R_SLAVE``) and agrees to be fulfilled "in one phase of the year of the death" -- the turn of
    # Talk plus two. ``None``: no such date (every other agreement, or one set by hand).
    pending_deal_ready_turn: int | None = None
    # The hero the monster wants dead, for the two quests of vengeance (``MonsterTalkReply.R_FREVENGE`` /
    # ``R_PREVENGE``): chosen when the monster asks (the "quest-character" of ``MTALK.X2``), kept for the Fulfill.
    quest_target_leader_id: int | None = None
    # For the travel quest (``MonsterTalkReply.R_VISIT``): the land province the hero must go to ("The Gods will deem this
    # quest completed if he will simply undertake the journey and return to Fulfill"), chosen when the monster asks,
    # and whether the hero has been there since. ``None``: no destination (a map without a province that far), the
    # quest asks nothing of the journey.
    quest_visit_coord: HexCoord | None = None
    quest_visit_done: bool = False
    # The magic item a monster wants brought to it (``MonsterTalkReply.R_REGAIN``: its clan's lost artifact;
    # ``R_TRADE``: the one it would rather have than its own treasure) -- the "treasure-2" of ``MTALK.X2``.
    quest_required_treasure: Treasure | None = None
    # 2026-11-20 bug fix, user-confirmed via a deep audit: Office.
    # PSYCHIC_MAGE's own "will sense whether the monster intends to keep
    # its end of the bargain" perk (`models/office.py OFFICE_TITLE_
    # DESCRIPTION[Office.PSYCHIC_MAGE]`) had no implementation anywhere.
    # Whether the guardian will actually honor this specific pending
    # deal is only ever decided by one real roll (`turn/encounter.py
    # resolve_fulfill_honored()`'s own `rng.random() < threshold/100`);
    # sensing it ahead of time means rolling that same real outcome
    # early, at Talk, rather than at the later Fulfill it would
    # otherwise roll at -- not a second, independent coin flip (which
    # could disagree with the first and make the "sense" a lie). `None`
    # unless Talk's own caster held the office at the moment the deal
    # was struck; cleared alongside `pending_deal_leader_id` either way
    # (sensed or not) once Fulfill consumes it.
    psychic_mage_sensed_fulfill_honor: bool | None = None
    # Phase 528: which of the 24 real `MonsterTalkReply` ids (`turn/
    # encounter.py`) this feature's own guardian has been assigned to
    # give on Talk -- stored as a raw ordinal, not the enum itself, to
    # avoid a `models/` -> `turn/` import (this module only ever imports
    # other `models/` modules; `MonsterTalkReply` lives in `turn/
    # encounter.py`, which already imports `Feature`). `AKGEN_reverse_
    # engineering_report (3).md` SS64 confirms the real engine also
    # assigns this once, seeded from a deterministic combination of the
    # feature's own id and its guardian's monster id, then reuses it for
    # every subsequent Talk against the same guardian ("per una tana
    # concreta l'esito e pertanto fissato"). **Phase 727**: the exact
    # seed formula is now real, not project-original -- `Desktop/
    # NOARMY.md`'s own disassembly of `Get_Reply` gives it in full
    # (`turn/monster_raids.py resolve_monster_raid_reply()`, Phase 679),
    # and `turn/search_execution.py`'s own Talk branch resolves the
    # first roll via that real, deterministic function rather than the
    # turn's own live `rng`. Persisting the result here is no longer
    # substituting for an unknown formula -- a fresh call would
    # reproduce the identical reply regardless -- it's kept purely to
    # avoid recomputing the same deterministic roll on every subsequent
    # Talk attempt against the same guardian.
    # `None` means "not yet resolved" (or the feature has no guardian at
    # all) -- set by `turn/search_execution.py`'s own Talk branch.
    guardian_talk_reply_id: int | None = None
    # Phase 365: this feature's own internal magical location/power --
    # ``worldgen.internal_magical_locations.resolve_visible_location()``/
    # ``resolve_power()`` (Phase 361), first wired to a real feature
    # roster here (``worldgen.generate_new_game``). Both formulas are
    # unconditional (they always resolve, never skipped), so a feature
    # created through that pipeline always carries a real
    # ``MagicFeature``/``Power`` value here -- including the "no
    # location" (``MagicFeature.NONE``) case itself, which is a real
    # resolved answer, not a missing one. ``None`` (the default) means
    # only "never run through that pipeline", the same convention
    # ``treasure``/``guardian_alignment`` above already use.
    magic_location: MagicFeature | None = None
    magic_power: Power | None = None
    # Phase 616: PowerCondition.G_TURN's own "one activation per
    # gameturn" scope -- per-Feature, not per-Kingdom (`Special
    # Features.md` section 4.2, user-supplied 2026-08-22). The turn
    # number this Feature's own power was last successfully used on;
    # `None` means never used. Set by `turn/feature_power_execution.py
    # resolve_feature_power_attempt()`.
    power_used_turn: int | None = None
    # Phase 670: `fstate[fn]`'s real, full guardian-engagement state
    # (`Desktop/THUNDERBIRD.md`) -- `MERCENARY` ("alive, ordinary
    # guardian, not yet Bold") is the sensible default every existing
    # fixture and `turn/world_generation.py _create_feature()`
    # picks up automatically. Deliberately independent of `looted`
    # (still the one true "is this guardian dead" bit) -- raid/
    # maturation logic in `turn/monster_raids.py` checks `not looted`
    # as its own separate precondition rather than folding Dead into
    # this enum's own live value.
    guardian_state: MonsterEngagementState = MonsterEngagementState.MERCENARY

    def discovery_level(self, kingdom_id: int) -> int:
        return self.discovered_by_kingdom.get(kingdom_id, 0)


@dataclass(frozen=True, slots=True)
class RaidEvent:
    """A single monster-raid outcome resolved this turn (Phase 670,
    ``Desktop/THUNDERBIRD.md`` sections 9-12) -- either an ordinary raid
    (damage subtracted from this turn's collected income only, never the
    persisted tax base) or a Thunderbird intervention (Divine King's own
    perk, zero damage, at most one per turn across the whole game).
    Placed here rather than in ``turn/`` specifically to avoid a circular
    import: ``GameState`` needs this type on ``turn_raid_events``, and
    ``turn/monster_raids.py`` needs ``GameState`` types -- the same
    ``models/`` -> ``turn/`` layering this project already keeps
    elsewhere.
    """

    kind: str  # "raid" or "thunderbird"
    province_coord: HexCoord
    feature_id: int
    monster: Monster
    damage: int


# CTBOTH.PAS `mfeat1`/`mfeat2` (``type monfeat = array[monster] of feature``,
# ~line 803-833), inside a ``{$IFDEF Moderator}`` block -- confirming this is
# world-generation-side data (which feature *type* a monster is placed to
# guard), not anything the player-turn-processing code ever reads. Each real
# monster species gets a (primary, secondary) preferred `FeatureType` pair;
# transcribed verbatim and positionally against `Monster`'s own declaration
# order (61 real+sentinel entries in the Pascal array; this project's own 10
# unused `em1`-`em10` monster extension slots at the array's tail are
# dropped, the same convention used everywhere else in this project).
# `Monster.NOMONSTER` is deliberately excluded too: its own array entry
# (`Tomb, Tomb`) is a degenerate positional filler for the "no monster"
# sentinel, not a real guardian preference -- nothing in the Pascal source
# ever assigns Nomonster to guard a feature.
MONSTER_GUARDED_FEATURE_TYPES: dict[Monster, tuple[FeatureType, FeatureType]] = {
    Monster.ROC: (FeatureType.PET_FOREST, FeatureType.MOUNT_PEAK),
    Monster.GRYPHON: (FeatureType.PET_FOREST, FeatureType.MOUNT_PEAK),
    Monster.COUATL: (FeatureType.LOST_CITY, FeatureType.LOST_TEMPLE),
    Monster.GI_EAGLE: (FeatureType.PET_FOREST, FeatureType.MOUNT_PEAK),
    Monster.SPHINX: (FeatureType.PET_FOREST, FeatureType.SUNK_CITY),
    Monster.R_DRAGON: (FeatureType.PYRAMID, FeatureType.LABYRINTH),
    Monster.B_DRAGON: (FeatureType.PYRAMID, FeatureType.LABYRINTH),
    Monster.GR_DRAGON: (FeatureType.PYRAMID, FeatureType.LABYRINTH),
    Monster.S_DRAGON: (FeatureType.TOWER, FeatureType.LOST_TEMPLE),
    Monster.GO_DRAGON: (FeatureType.TOWER, FeatureType.LOST_TEMPLE),
    Monster.GI_WORM: (FeatureType.PYRAMID, FeatureType.MOUNT_PEAK),
    Monster.TITAN: (FeatureType.TOWER, FeatureType.TEMPLE),
    Monster.GIANT: (FeatureType.PET_FOREST, FeatureType.MOUNT_PEAK),
    Monster.BIGFOOT: (FeatureType.PET_FOREST, FeatureType.MOUNT_PEAK),
    Monster.ARCHER: (FeatureType.PET_FOREST, FeatureType.MOUNT_PEAK),
    Monster.SWORDSMAN: (FeatureType.PYRAMID, FeatureType.MOUNT_PEAK),
    Monster.WHITE_MAGE: (FeatureType.PYRAMID, FeatureType.MOUNT_PEAK),
    Monster.NEC_MAGE: (FeatureType.PYRAMID, FeatureType.MOUNT_PEAK),
    Monster.ELE_MAGE: (FeatureType.PYRAMID, FeatureType.MOUNT_PEAK),
    Monster.PSY_MAGE: (FeatureType.PYRAMID, FeatureType.MOUNT_PEAK),
    Monster.ILL_MAGE: (FeatureType.PYRAMID, FeatureType.MOUNT_PEAK),
    Monster.WITCH: (FeatureType.PYRAMID, FeatureType.MOUNT_PEAK),
    Monster.DRYAD: (FeatureType.HOLLOW_TREE, FeatureType.HANG_VALLEY),
    Monster.CENTAUR: (FeatureType.HOLLOW_TREE, FeatureType.HANG_VALLEY),
    Monster.GENIE: (FeatureType.TOWER, FeatureType.TEMPLE),
    Monster.GOLEM: (FeatureType.PYRAMID, FeatureType.LOST_TEMPLE),
    Monster.GARGOYLE: (FeatureType.PYRAMID, FeatureType.LOST_TEMPLE),
    Monster.BASILISK: (FeatureType.PYRAMID, FeatureType.HANG_VALLEY),
    Monster.MEDUSA: (FeatureType.PYRAMID, FeatureType.MOUNT_PEAK),
    Monster.BAL_DEMON: (FeatureType.PYRAMID, FeatureType.DUNGEON),
    Monster.MAR_DEMON: (FeatureType.PYRAMID, FeatureType.DUNGEON),
    Monster.SUCCUBUS: (FeatureType.PYRAMID, FeatureType.DUNGEON),
    Monster.RAKSHASHA: (FeatureType.PYRAMID, FeatureType.DUNGEON),
    Monster.ICE_DEVIL: (FeatureType.PYRAMID, FeatureType.DUNGEON),
    Monster.BONE_DEVIL: (FeatureType.PYRAMID, FeatureType.DUNGEON),
    Monster.IMP: (FeatureType.PYRAMID, FeatureType.DUNGEON),
    Monster.WEREWOLF: (FeatureType.PYRAMID, FeatureType.MOUNT_PEAK),
    Monster.CHIMERA: (FeatureType.PYRAMID, FeatureType.HANG_VALLEY),
    Monster.HYDRA: (FeatureType.PYRAMID, FeatureType.HANG_VALLEY),
    Monster.BEHOLDER: (FeatureType.PYRAMID, FeatureType.HANG_VALLEY),
    Monster.TROLL: (FeatureType.PYRAMID, FeatureType.MOUNT_PEAK),
    Monster.MINOTAUR: (FeatureType.MAZE, FeatureType.LABYRINTH),
    Monster.GI_WOLVERINE: (FeatureType.HOLLOW_TREE, FeatureType.HANG_VALLEY),
    Monster.TREANT: (FeatureType.HOLLOW_TREE, FeatureType.HANG_VALLEY),
    Monster.GI_AMOEBA: (FeatureType.PET_FOREST, FeatureType.HANG_VALLEY),
    Monster.GI_P_MANTIS: (FeatureType.PET_FOREST, FeatureType.HANG_VALLEY),
    Monster.GI_SCORPION: (FeatureType.PET_FOREST, FeatureType.HANG_VALLEY),
    Monster.GI_WASP: (FeatureType.PET_FOREST, FeatureType.HANG_VALLEY),
    Monster.GI_SPIDER: (FeatureType.PET_FOREST, FeatureType.HANG_VALLEY),
    Monster.GHOST: (FeatureType.PYRAMID, FeatureType.CRYPT),
    Monster.VAMPIRE: (FeatureType.PYRAMID, FeatureType.CRYPT),
    Monster.MUMMY: (FeatureType.PYRAMID, FeatureType.CRYPT),
    Monster.BANSHEE: (FeatureType.PYRAMID, FeatureType.CRYPT),
    Monster.LICH: (FeatureType.PYRAMID, FeatureType.CRYPT),
    Monster.SPECTRE: (FeatureType.PYRAMID, FeatureType.CRYPT),
    Monster.GI_OCTOPUS: (FeatureType.MAG_POOL, FeatureType.MAELSTROM),
    Monster.GI_CLAM: (FeatureType.MAG_POOL, FeatureType.MAELSTROM),
    Monster.ELASMOSAURUS: (FeatureType.MAG_POOL, FeatureType.MAELSTROM),
    Monster.GW_WHALE: (FeatureType.MAG_POOL, FeatureType.MAELSTROM),
    Monster.MERMAID: (FeatureType.MAG_POOL, FeatureType.MAELSTROM),
}
