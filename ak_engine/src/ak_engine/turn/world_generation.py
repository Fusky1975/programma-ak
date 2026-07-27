"""World generation: populate a fresh ``GameState`` with a feature roster
(dungeons, guardians, treasure) -- Phase 242.

**No Pascal source survives for this at all.** The real world-generator,
``HostAK/TP/AKGEN.EXE``, is compiled-only -- confirmed by an exhaustive
listing of the entire available archive (``ls HostAK/TP``): every other
``.EXE`` in that directory has a matching ``.PAS``, but ``AKGEN.EXE``
does not. What survives instead is only the *reading* side
(``REPORTS.PAS``'s own ``fdisc``/``nfeatures`` report-printing code) and
one real moderator-side data table, ``models/feature.py
MONSTER_GUARDED_FEATURE_TYPES`` (Phase 79) -- see that module's own
docstring for the full "table survives, generator doesn't" account.

Every number and rule below is project-original, designed collaboratively
with the user (project author) via direct confirmation -- not sourced,
and not silently guessed. Cross-referenced against
``MONSTER_GUARDED_FEATURE_TYPES`` wherever possible rather than invented
from nothing.

**Density** (confirmed directly by the user):
- Land provinces: 60% get at least one feature; of those, 20% get a
  second (independently generated) feature.
- Sea provinces: 10% get one feature, always guarded by an aquatic
  monster (see below).
- ``Terrain.NO_TERRAIN`` provinces never get a feature (not a real,
  ownable province).

**Terrain-gating of feature type** (confirmed directly: yes, filter by
plausible terrain). Three ``FeatureType`` members are reserved for sea
provinces:
- ``MAG_POOL``/``MAELSTROM`` -- sourced directly: every monster
  ``MONSTER_GUARDED_FEATURE_TYPES`` ever pairs with either of these two
  types (``GI_OCTOPUS``, ``GI_CLAM``, ``ELASMOSAURUS``, ``GW_WHALE``,
  ``MERMAID``) is one of this project's own aquatic species.
- ``UND_CAVERN`` ("Undersea Cavern") -- added by name evidence alone
  (no monster in the sourced table guards it), a project-original
  inference rather than a guessed number.

All other 27 real ``FeatureType`` members (``NOFTYPE``, the generic
wandering-encounter sentinel, excluded -- see ``models/feature.py``'s
own docstring) are land-only.

**Guardian selection**: ``FEATURE_TYPE_CANDIDATE_MONSTERS`` inverts
``MONSTER_GUARDED_FEATURE_TYPES`` (a monster's own primary/secondary
type both make it a candidate for that type). Only 16 of the 30 real
types have any sourced candidate at all; ``UND_CAVERN`` is seeded with
the same aquatic candidates as ``MAG_POOL``/``MAELSTROM`` (both sea
types are always covered this way). For the 14 remaining, uncovered
*land* types, guardian selection falls back to a uniform draw over
every non-aquatic real monster (``LAND_MONSTER_POOL``) -- an explicit,
documented fallback, not a silent gap.

**Treasure**: a uniform-random draw over the full 113-member
``Treasure`` catalog (``models/treasure.py``, Phase 77). No source ties
treasure to feature type, monster, or any notion of "tier" -- confirmed
absent, not simplified away.
"""

from __future__ import annotations

import random

from ak_engine.models.feature import (
    MONSTER_GUARDED_FEATURE_TYPES,
    Feature,
    FeatureType,
)
from ak_engine.models.game_state import GameState
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.monster import Monster
from ak_engine.models.treasure import Treasure

LAND_FEATURE_CHANCE = 0.60
LAND_DOUBLE_FEATURE_CHANCE = 0.20
SEA_FEATURE_CHANCE = 0.10

# Sourced via MONSTER_GUARDED_FEATURE_TYPES cross-reference (MAG_POOL,
# MAELSTROM) plus one name-evidence inference (UND_CAVERN) -- see module
# docstring.
SEA_FEATURE_TYPES: tuple[FeatureType, ...] = (
    FeatureType.MAG_POOL,
    FeatureType.MAELSTROM,
    FeatureType.UND_CAVERN,
)

LAND_FEATURE_TYPES: tuple[FeatureType, ...] = tuple(
    ftype for ftype in FeatureType if ftype is not FeatureType.NOFTYPE and ftype not in SEA_FEATURE_TYPES
)

# The 5 real species MONSTER_GUARDED_FEATURE_TYPES ever pairs with
# MAG_POOL/MAELSTROM -- this project's own confirmed-aquatic set.
AQUATIC_MONSTERS: tuple[Monster, ...] = (
    Monster.GI_OCTOPUS,
    Monster.GI_CLAM,
    Monster.ELASMOSAURUS,
    Monster.GW_WHALE,
    Monster.MERMAID,
)

LAND_MONSTER_POOL: tuple[Monster, ...] = tuple(
    monster for monster in Monster if monster is not Monster.NOMONSTER and monster not in AQUATIC_MONSTERS
)

TREASURE_POOL: tuple[Treasure, ...] = tuple(Treasure)


def _invert_guarded_feature_types() -> dict[FeatureType, tuple[Monster, ...]]:
    inverted: dict[FeatureType, list[Monster]] = {}
    for monster, (primary, secondary) in MONSTER_GUARDED_FEATURE_TYPES.items():
        for ftype in (primary, secondary):
            inverted.setdefault(ftype, []).append(monster)
    inverted[FeatureType.UND_CAVERN] = list(AQUATIC_MONSTERS)
    return {ftype: tuple(monsters) for ftype, monsters in inverted.items()}


# FeatureType -> every monster whose own primary/secondary preference
# (MONSTER_GUARDED_FEATURE_TYPES) matches it, inverted once at import
# time. Only 16 of 30 real types are covered -- see module docstring for
# the land-only fallback used for the rest.
FEATURE_TYPE_CANDIDATE_MONSTERS: dict[FeatureType, tuple[Monster, ...]] = _invert_guarded_feature_types()


def _create_feature(state: GameState, coord: HexCoord, *, sea: bool, rng: random.Random) -> Feature:
    feature_type = rng.choice(SEA_FEATURE_TYPES if sea else LAND_FEATURE_TYPES)
    candidates = FEATURE_TYPE_CANDIDATE_MONSTERS.get(feature_type, LAND_MONSTER_POOL)
    guardian = rng.choice(candidates)
    treasure = rng.choice(TREASURE_POOL)
    feature = Feature(state.new_feature_id(), coord, feature_type, guardian_monster=guardian, treasure=treasure)
    state.add_feature(feature)
    return feature


def generate_world_features(state: GameState, rng: random.Random | None = None) -> list[Feature]:
    """Populate ``state.features`` for every province in ``state.provinces``,
    per this module's own docstring rules. Idempotent-unsafe: calling
    this twice on the same ``state`` adds a second, independent roster
    rather than replacing the first -- callers should only call this
    once, on a fresh ``GameState``.
    """

    rng = rng if rng is not None else random.Random()
    created: list[Feature] = []
    for province in state.provinces.values():
        if province.terrain is Terrain.SEA:
            if rng.random() < SEA_FEATURE_CHANCE:
                created.append(_create_feature(state, province.coord, sea=True, rng=rng))
        elif province.terrain is not Terrain.NO_TERRAIN:
            if rng.random() < LAND_FEATURE_CHANCE:
                created.append(_create_feature(state, province.coord, sea=False, rng=rng))
                if rng.random() < LAND_DOUBLE_FEATURE_CHANCE:
                    created.append(_create_feature(state, province.coord, sea=False, rng=rng))
    return created
