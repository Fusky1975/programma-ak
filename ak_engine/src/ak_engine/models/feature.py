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
- ``fstate[fn]``: only one value is ever referenced in the available
  source, ``Dead`` -- printed as "sacked & looted" when true, and used
  to gate whether the guardian's name is shown at all. No other
  ``fstate`` value is ever referenced anywhere in the archive, so this
  project models only that one confirmed bit (``looted: bool``) rather
  than guessing a fuller status enum.
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

- **World generation** -- populating a fresh ``GameState`` with a
  realistic feature roster (which provinces get one, how many, what
  kind, where, what treasure) has no surviving Pascal source at all,
  the same category of gap as hex adjacency and item-instance
  creation. ~~What guardian~~ is a partial exception, as of Phase 79
  -- see ``MONSTER_GUARDED_FEATURE_TYPES`` below: one real piece of
  the world-gen puzzle *does* survive, in a ``{$IFDEF Moderator}``
  (world-generation-side, not player-turn-processing-side) compile
  block, giving each monster's own preferred feature type to guard --
  still not a full "assign a guardian to a fresh feature instance"
  algorithm (nothing says how the *feature*'s own kind gets decided
  first, or how ties/randomness among a feature's several eligible
  guardians resolve), but a real, sourced building block for
  whichever future phase attempts that.
- **Rumor generation** ([3.2]'s "about half... false" mechanic) --
  the prose templates exist (``HostAK/TP/PROSE/FRUMOR.X``) but the
  selection/falsification logic doesn't.
- **Search resolution** (fighting the guardian, awarding treasure) --
  needs the still-unbuilt personal/non-army Encounter-combat resolver
  ``turn/encounter.py``'s own docstring already scopes out (a monster
  HP/combat model, Steal/Flee/Scout tactic resolution).
- ~~**Treasure *instances***: a feature's own treasure content isn't
  modeled here at all -- ``turn/use_mi_decode.py``'s own docstring
  already reconstructed the full 113-member ``treasure`` type enum
  from ``CTBOTH.PAS``, but promoting it into an actual Python model
  (with the prose-file cross-referencing that needs) is a separate,
  sizable follow-up, not attempted in this phase.~~ **The full
  ``Treasure`` type catalog now exists as of Phase 77**
  (``models/treasure.py``) -- see that phase's own README note. A
  feature's own treasure *instance* (which specific ``Treasure`` a
  given feature actually holds) is still unmodeled -- world generation
  itself remains the blocking gap, not the type catalog anymore.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from ak_engine.models.map import HexCoord
from ak_engine.models.monster import Monster


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

    def discovery_level(self, kingdom_id: int) -> int:
        return self.discovered_by_kingdom.get(kingdom_id, 0)


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
