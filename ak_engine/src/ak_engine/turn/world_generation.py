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

All other 28 real ``FeatureType`` members (``NOFTYPE``, the generic
wandering-encounter sentinel, excluded -- see ``models/feature.py``'s
own docstring -- leaving 31 real members total, 3 sea + 28 land) are
land-only. (Phase 1194 correction: this used to say "27"/"30" below,
off by one against the actual 32-member enum; the derived "16 sourced
+ 14 uncovered = 28 land" breakdown two paragraphs down was already
internally consistent with the real 28, so only these two summary
totals were wrong.)

**Guardian selection**: ``FEATURE_TYPE_CANDIDATE_MONSTERS`` inverts
``MONSTER_GUARDED_FEATURE_TYPES`` (a monster's own primary/secondary
type both make it a candidate for that type). Only 16 of the 31 real
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

**Phase 359 addendum**: the real generator (``AKGEN.EXE``, static
disassembly, ``world_generation.features`` in the source JSON) has since
been found after all -- see ``ak_engine.worldgen.feature_generation``
for its confirmed formulas. Comparing this module's own guesses above
against it:

- **Density is confirmed wrong.** The real generator produces a fixed
  *total* feature count for the whole map (128 or 230, by
  ``gamevers``), placed by rejection-sampled random coordinates -- not
  this module's own per-province independent 60%/20%/10% chances. ~~This
  module's density model has not been rewired to the real one yet
  (that needs a live generated map to place features onto, the same
  integration gap `worldgen.place_map`'s own callers still have).~~ --
  **see the Phase 364 correction below the three bullets**: that
  integration gap closed, just not by rewiring this module.
- **``MAG_POOL`` ("Magic Pool") is confirmed wrong as Sea-only.** This
  module's own inference (every sourced guardian monster for it is
  aquatic) doesn't hold: the real generator's own terrain table lists
  it "any land 0..4", alongside ``LOCH``. Only ``UND_CAVERN``/
  ``MAELSTROM`` are really Sea-only -- `SEA_FEATURE_TYPES` below should
  drop ``MAG_POOL`` once this module is rewired to the real generator.
- **The land/sea binary terrain split was always too coarse.** The real
  generator gates several types to one *specific* land terrain rather
  than "any land": ``DES_RUINS``->Desert, ``LOST_CITY``/
  ``LOST_TEMPLE``->Jungle, ``HOLLOW_TREE``/``GLADE``->Forest,
  ``HANG_VALLEY``/``MOUNT_PEAK``->Mountains, plus ``SUNK_CITY``'s own
  50/50 Desert/Sea split -- none of which this module's own
  `LAND_FEATURE_TYPES` (one undifferentiated land pool) models.
- **Guardian selection is a different mechanism than "candidates".**
  The real generator proposes a monster first (uniform over the 60 real
  species), then draws a feature type from *that monster's own*
  ``mfeat1..mfeat2`` ordinal range -- the reverse direction from this
  module's `FEATURE_TYPE_CANDIDATE_MONSTERS` (feature type -> monster
  candidates). The `AQUATIC_MONSTERS` 5-species list this module
  guessed, however, is confirmed **exactly right** -- those same 5
  species are exactly the ones whose real ``mfeat1..mfeat2`` range is
  ``MAG_POOL..MAELSTROM``.

~~This module's actual generator function (`generate_world_features`) is
deliberately left unchanged for now -- rewiring it to the real formulas
needs the whole spatial placement loop (`later_placement`/
`rejection_rule`), which itself needs a live generated map to run
against, consistent with every other worldgen phase's own "formulas
now, spatial wiring later" split (Phase 353/354, Phase 355's
special-race pass, Phase 358's extra mercenary band).~~

**Stale as of Phase 364 -- the "whole spatial placement loop" this
paragraph called a blocker was built, closing the integration gap in
full, but as an entirely separate module, not by rewiring this
function.** `worldgen/feature_placement.py place_all_features()`
implements `first_2k_placement`/`later_placement`/`rejection_rule`
directly against `worldgen/feature_generation.py`'s own already-confirmed
`propose_monster()`/`propose_feature_type()`/`is_terrain_compatible()`
(Phase 359), and `worldgen/generate_new_game.py` calls *that* function
(`from ak_engine.worldgen.feature_placement import place_all_features`)
for the real generation pipeline -- never this module's own
`generate_world_features()`, which today is exercised only by
`tests/test_world_generation.py` and has no live caller anywhere in
`ak_engine`. This module's own density/terrain/guardian-selection
formulas above were correctly superseded, not merely left pending --
`generate_world_features()` is this project's original, since-replaced
guess at the mechanic, kept for its own historical test coverage, not a
function still awaiting integration.

**Phase 360 addendum**: the real magic-item/treasure assignment has
also now been found (``world_generation.magic_item_province_placement``
-- see ``ak_engine.worldgen.magic_item_placement``), and it confirms
this module's own treasure draw was guessed wrong too:

- This module draws an **independent uniform ``Treasure`` choice for
  every single feature** (`_create_feature`'s own `rng.choice(
  TREASURE_POOL)`, over the full 113-member catalog). The real
  generator instead gives only roughly **half** of all features an
  actual item at all -- the other half get gold, per a confirmed
  4-gold/4-item repeating pattern over feature index -- and the items
  a map *does* receive are **not independently random**: they cycle
  through a 67-item pool via one shared, sequentially-advancing
  cursor (uniform start, then ``+1 mod 67`` per item-slot feature).
  This project's own pre-existing `Treasure` catalog already has
  *exactly* 67 members in a contiguous block at ordinals 0..66 (the
  ability-item/wand/weapon/amulet/command-item/skill-book categories)
  -- an item id from the source maps directly onto those ordinals with
  no new data needed.

~~As with the feature-terrain correction above, `generate_world_features`
itself is left unchanged -- wiring the shared cursor in needs features
processed in their real generation order, the same spatial-integration
gap already noted.~~ -- **stale as of Phase 365, the same "closed
elsewhere" shape as the Phase 364 correction above**: `worldgen/
magic_item_placement.py`'s own docstring records that `worldgen/
generate_new_game.py` (~lines 642-648) now calls `initial_item_cursor()`/
`feature_gets_item_slot()`/`cursor_to_treasure()`/`next_item_cursor()`
in sequence, iterating `placements` from `place_all_features()`'s own
real generation order -- exactly the wiring this paragraph called
missing, landed the very next phase, again in the separate real
pipeline rather than in this module.
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
from ak_engine.models.monster import Monster, roll_monster_alignment
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
    # Phase 246: models/monster.py roll_monster_alignment() (Phase 176)
    # existed as a pure, tested mechanism with nothing to wire it to --
    # that phase's own note: "nothing to wire it to yet... this project
    # still has none [of a world-generation pipeline]". This module now
    # is that pipeline, so the guardian's own Alignment is rolled here.
    guardian_alignment = roll_monster_alignment(guardian, rng)
    feature = Feature(
        state.new_feature_id(),
        coord,
        feature_type,
        guardian_monster=guardian,
        treasure=treasure,
        guardian_alignment=guardian_alignment,
    )
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
