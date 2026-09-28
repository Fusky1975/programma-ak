"""Feature-generation formulas (Phase 359): the real ``AKGEN.EXE`` feature
generator (0006:5002 / 0x5062), correcting ``turn/world_generation.py``'s
own project-original density/terrain-gating guesses (Phase 242 -- written
when no source for this subsystem was known to survive at all).

Seventh phase of the world-generation sub-plan. Source:
``world_generation.features``.

**Confirmed exactly** and implemented here:

- ``feature_count()``: a *fixed total* feature count for the whole map --
  128 (``gamevers < 4``) or 230 (``gamevers >= 4``) -- not a per-province
  independent chance. This is a different generative model outright from
  Phase 242's own guessed 60%/20%/10% per-province probabilities (see the
  correction note in `turn/world_generation.py`'s own docstring).
- ``propose_monster()``: "IRand mod 60; with probability 0.1 perform one
  additional IRand mod 60 draw" -- realized as a first draw, replaced by a
  second independent draw 10% of the time (a redraw, not a combination --
  the source's own "the marginal proposal remains uniform at 1/60 per
  monster" note holds trivially once read this way, since a re-drawn
  uniform variable is still uniform). ``Monster``'s own pre-existing
  ordinals (Phase ~130s) already run ``0..59`` for the 60 real species
  plus ``NOMONSTER=60``, exactly matching "IRand mod 60" -- zero
  correction needed.
- ``MFEAT_RANGE`` / ``propose_feature_type()``: "uniform over the
  inclusive ordinal range mfeat1[monster]..mfeat2[monster]" -- the source
  gives this as a *name* range per monster (e.g. "Petrified Forest ..
  Mountain Peak"); this project's own pre-existing ``FeatureType`` enum
  (Phase 79/CTBOTH.PAS ``ftname``) already numbers every one of those 32
  names with the exact same ordinals the source's own ``feature_types``
  table declares (id 0=Pyramid .. 31=NOFTYPE/"encounter area" sentinel),
  so the range converts directly with no renumbering. Every one of the
  60 real monsters' own declared ``choices`` count (``last - first + 1``)
  was cross-checked against this ordinal arithmetic programmatically
  before this table was written, with zero mismatches.
- ``FEATURE_TERRAIN`` / ``is_terrain_compatible()``: the per-type terrain
  constraint from the source's own ``feature_types`` table. Most types
  are "any land 0..4"; several are gated to one specific land terrain
  (``DES_RUINS``->Desert, ``LOST_CITY``/``LOST_TEMPLE``->Jungle,
  ``HOLLOW_TREE``/``GLADE``->Forest, ``HANG_VALLEY``/``MOUNT_PEAK``->
  Mountains); ``UND_CAVERN``/``MAELSTROM`` are Sea-only; ``SUNK_CITY``
  ("Sunken City") is a special dual case -- "50% Desert proposal, 50%
  Sea proposal" -- resolved by drawing which single terrain applies
  before checking the coordinate against it.
- ``first_2k_home_index()``: "feature indexes 0..king_count-1 use the
  corresponding king Home; indexes king_count..2*king_count-1 use
  Home[(feature_index+5) mod king_count]".

**A genuine, concrete correction to Phase 242's own guesses**, found
here and documented in `turn/world_generation.py`'s own docstring
rather than silently overwritten: Phase 242 guessed ``MAG_POOL``
("Magic Pool") was a Sea-only type, inferred from the fact that every
sourced monster guarding it in `models.feature.
MONSTER_GUARDED_FEATURE_TYPES` happens to be one of this project's own
aquatic species. The real generator's own terrain table says otherwise
-- ``MAG_POOL`` (and ``LOCH``) are "any land 0..4", not Sea. The
monster-species/feature-terrain link Phase 242 assumed doesn't hold: an
aquatic monster's own ``mfeat1..mfeat2`` range spans both the land types
(``MAG_POOL``, ``LOCH``) and the true sea types (``UND_CAVERN``,
``MAELSTROM``) in one contiguous ordinal block, with terrain
compatibility checked as a wholly separate rejection step against
whichever coordinate actually gets proposed -- not baked into the
monster's own aquatic-ness. Only ``UND_CAVERN``/``MAELSTROM`` are
confirmed Sea-only; Phase 242's broader "27 remaining types are land-only
with no further terrain gating" was also incomplete -- several of those
27 are gated to one *specific* land terrain, not "any land", something
Phase 242 never modeled at all.

~~**Deliberately NOT implemented here**: the full spatial placement loop
(``later_placement``'s random-coordinate-with-King-Home-rejection draw,
and the ``rejection_rule``'s "propose everything again on terrain
mismatch" retry) -- this needs a live generated map (``place_map``,
Phase 354) plus per-coordinate occupancy tracking to run against, the
same category of integration work already deferred for the special-race
overwrite pass (Phase 355) and the extra mercenary band (Phase 358).
This phase supplies every formula that loop will need; wiring it into a
real placement loop is left for a later phase.~~ -- **closed in Phase
364** (``worldgen/feature_placement.py``, which calls this module's own
``propose_monster()``/``propose_feature_type()``/``is_terrain_
compatible()`` directly, the same "turn the narrative into an
algorithm" treatment ``place_map``/``special_race_placement``/
``mercenary_band`` already got): see that module's own docstring for
the full placement-loop derivation.

**Verification**: `propose_monster()` is Monte Carlo-checked for
uniformity over the 60 real species. `propose_feature_type()` is
checked per-monster against its own confirmed inclusive range (every
result falls within ``mfeat1..mfeat2``, and the full range is covered
given enough draws). `is_terrain_compatible()`'s ``SUNK_CITY`` special
case is Monte Carlo-checked for its own 50/50 split.
"""

from __future__ import annotations

from ak_engine.models.feature import FeatureType
from ak_engine.models.map import Terrain
from ak_engine.models.monster import Monster
from ak_engine.worldgen.pascal_random import PascalRandom

LAND_TERRAINS: tuple[Terrain, ...] = (
    Terrain.PLAINS,
    Terrain.DESERT,
    Terrain.JUNGLE,
    Terrain.FOREST,
    Terrain.MTNS,
)


def feature_count(gamevers: int) -> int:
    """"count_rule: gamevers<4 -> 128; gamevers>=4 -> 230"."""

    return 128 if gamevers < 4 else 230


def propose_monster(rng: PascalRandom) -> Monster:
    """"IRand mod 60; with probability 0.1 perform one additional IRand mod 60 draw"."""

    ordinal = rng.irand() % 60
    if rng.random() < 0.1:
        ordinal = rng.irand() % 60
    return Monster(ordinal)


# mfeat1[monster]..mfeat2[monster], converted from the source's own
# FeatureType *name* range to this project's own already-matching
# FeatureType ordinals -- see module docstring.
MFEAT_RANGE: dict[Monster, tuple[FeatureType, FeatureType]] = {
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


def propose_feature_type(monster: Monster, rng: PascalRandom) -> FeatureType:
    """Uniform draw over the inclusive ``mfeat1[monster]..mfeat2[monster]`` range."""

    first, last = MFEAT_RANGE[monster]
    span = last.value - first.value + 1
    offset = rng.irand() % span
    return FeatureType(first.value + offset)


# Per-type terrain constraint, from the source's own `feature_types` table.
# FeatureType.SUNK_CITY is deliberately absent -- its 50/50 Desert/Sea rule
# needs is_terrain_compatible()'s own extra draw, not a static set.
FEATURE_TERRAIN: dict[FeatureType, tuple[Terrain, ...]] = {
    FeatureType.PYRAMID: LAND_TERRAINS,
    FeatureType.TOMB: LAND_TERRAINS,
    FeatureType.CATACOMBS: LAND_TERRAINS,
    FeatureType.CRYPT: LAND_TERRAINS,
    FeatureType.CAVE: LAND_TERRAINS,
    FeatureType.CAVERN: LAND_TERRAINS,
    FeatureType.VOLC_TUNNEL: LAND_TERRAINS,
    FeatureType.DUNGEON: LAND_TERRAINS,
    FeatureType.MAZE: LAND_TERRAINS,
    FeatureType.LABYRINTH: LAND_TERRAINS,
    FeatureType.TOWER: LAND_TERRAINS,
    FeatureType.CASTLE: LAND_TERRAINS,
    FeatureType.GREAT_HALL: LAND_TERRAINS,
    FeatureType.MONASTERY: LAND_TERRAINS,
    FeatureType.TEMPLE: LAND_TERRAINS,
    FeatureType.PET_FOREST: LAND_TERRAINS,
    FeatureType.SACRED_ROCK: LAND_TERRAINS,
    FeatureType.AS_MONUMENT: LAND_TERRAINS,
    FeatureType.ALTAR: LAND_TERRAINS,
    FeatureType.DES_RUINS: (Terrain.DESERT,),
    FeatureType.LOST_CITY: (Terrain.JUNGLE,),
    FeatureType.LOST_TEMPLE: (Terrain.JUNGLE,),
    FeatureType.HOLLOW_TREE: (Terrain.FOREST,),
    FeatureType.GLADE: (Terrain.FOREST,),
    FeatureType.HANG_VALLEY: (Terrain.MTNS,),
    FeatureType.MOUNT_PEAK: (Terrain.MTNS,),
    FeatureType.MAG_POOL: LAND_TERRAINS,
    FeatureType.LOCH: LAND_TERRAINS,
    FeatureType.UND_CAVERN: (Terrain.SEA,),
    FeatureType.MAELSTROM: (Terrain.SEA,),
}

SUNKEN_CITY_TERRAIN_CHOICES: tuple[Terrain, Terrain] = (Terrain.DESERT, Terrain.SEA)


def is_terrain_compatible(feature_type: FeatureType, terrain: Terrain, rng: PascalRandom) -> bool:
    """The per-type terrain-compatibility check the source's own rejection rule tests."""

    if feature_type is FeatureType.SUNK_CITY:
        target = Terrain.DESERT if rng.random() < 0.5 else Terrain.SEA
        return terrain is target
    return terrain in FEATURE_TERRAIN.get(feature_type, ())


def first_2k_home_index(feature_index: int, king_count: int) -> int:
    """"indexes 0..king_count-1 use the corresponding king Home;
    indexes king_count..2*king_count-1 use Home[(feature_index+5) mod king_count]"."""

    if feature_index < king_count:
        return feature_index
    return (feature_index + 5) % king_count
