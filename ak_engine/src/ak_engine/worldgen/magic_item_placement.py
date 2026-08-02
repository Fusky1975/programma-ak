"""Magic-item placement across features (Phase 360): the real ``AKGEN.EXE``
treasure/magic-item cursor, correcting `turn/world_generation.py`'s own
Phase 242 project-original treasure-draw guess for the same reason Phase
359 corrected its feature-terrain guesses.

Eighth phase of the world-generation sub-plan. Source:
``world_generation.magic_item_province_placement``.

**Confirmed exactly** and implemented here:

- ``MAGIC_ITEM_COUNT = 67``: "duplicates are allowed and unavoidable
  across 114 slots because only 67 item ids exist". This project's own
  pre-existing ``models.treasure.Treasure`` catalog (113 members, Phase
  77) already has *exactly* 67 members across its
  ``ABILITY_ITEM``/``SPELL_WAND``/``COMBAT_WEAPON``/
  ``LEADERSHIP_WEAPON``/``ANTI_MAGIC_AMULET``/``MONSTER_COMMAND_ITEM``/
  ``SKILL_BOOK`` categories -- and they are contiguous, occupying
  ordinals ``0..66`` at the very start of the enum. A real magic
  "item id" from the source is therefore literally
  ``Treasure(item_id)`` for ``item_id in 0..66`` -- zero new data
  needed, another exact cross-validation.
- ``item_slot_count()``: "4*floor(nfeatures/8) + max(0, min(4,
  nfeatures mod 8 - 4))" -- verified by hand against both of the
  source's own declared totals (128 features -> 64 slots, 230
  features -> 114 slots) before writing any code.
- ``feature_gets_item_slot()``: "four gold features followed by four
  magic-item features, repeating every eight indexes" -- realized as
  ``feature_index % 8 >= 4``. The item-slot count formula's own
  ``mod 8 - 4`` term only makes sense if the *item* positions are the
  latter four of each eight-block (confirmed by re-deriving
  `item_slot_count` from this exact rule and matching the source's own
  two totals before coding).
- ``initial_item_cursor()`` / ``next_item_cursor()`` / ``cursor_to_treasure()``:
  "uniform initial item id modulo 67, then advance cyclically modulo
  67" -- a single shared cursor across the whole feature array (not an
  independent per-feature random draw), stepped once per item-slot
  feature.
- ``coordinate_model``: magic items have no coordinates of their own --
  a feature's treasure simply inherits that feature's own ``fx``/``fy``.
  This means magic-item placement needs no *new* spatial logic beyond
  whatever already places the governing feature (Phase 359's own
  `first_2k_home_index`/placement-loop gap) -- confirmed here as a
  documentation note, not a new formula.

**A genuine, concrete correction to Phase 242's own guess**, documented
in `turn/world_generation.py`'s own docstring as a new "Phase 360
addendum" rather than silently overwritten: Phase 242 guessed every
feature's treasure was an independent uniform draw over the full
113-member ``Treasure`` catalog. The real generator instead (a) only
gives roughly half of all features an actual magic item at all -- the
other half get gold, per the confirmed 4-gold/4-item repeating pattern
-- and (b) the magic items a map does receive are **not independently
random per feature**: they cycle through the 67-item pool via one
shared, sequentially-advancing cursor, so which items appear together
on one map is far more constrained than 128 (or 230) independent
uniform draws would produce.

**Deliberately NOT implemented here**: wiring this cursor into
`generate_world_features()` -- that needs features processed in their
real generation *order* (index 0, 1, 2, ...) so the shared cursor
advances correctly and the gold/item pattern lines up, which in turn
needs the full spatial placement loop Phase 359 already left as an
integration gap. `standalone_treasures` (source records beyond
``nfeatures`` with no feature coordinate at all) is likewise a
documentation-only note -- this project has no other treasure-record
stream to apply it to yet.

**Verification**: `item_slot_count()` is checked against both of the
source's own declared totals exactly. `feature_gets_item_slot()` is
checked to produce exactly 4 gold + 4 item slots per full 8-block, and
its cumulative count is checked to equal `item_slot_count()` for both
128 and 230 features -- an independent consistency check between the
two confirmed formulas, not just trusting them separately. The cursor
functions are checked for the confirmed modulo-67 cyclic wraparound.
"""

from __future__ import annotations

from ak_engine.models.treasure import Treasure
from ak_engine.worldgen.pascal_random import PascalRandom

MAGIC_ITEM_COUNT = 67


def item_slot_count(feature_count: int) -> int:
    """"4*floor(nfeatures/8) + max(0, min(4, nfeatures mod 8 - 4))"."""

    return 4 * (feature_count // 8) + max(0, min(4, feature_count % 8 - 4))


def feature_gets_item_slot(feature_index: int) -> bool:
    """"four gold features followed by four magic-item features, repeating every eight indexes"."""

    return feature_index % 8 >= 4


def initial_item_cursor(rng: PascalRandom) -> int:
    """"uniform initial item id modulo 67"."""

    return rng.irand() % MAGIC_ITEM_COUNT


def next_item_cursor(cursor: int) -> int:
    """"advance cyclically modulo 67"."""

    return (cursor + 1) % MAGIC_ITEM_COUNT


def cursor_to_treasure(cursor: int) -> Treasure:
    """The cursor's own item id maps directly onto this project's ``Treasure`` ordinals 0..66."""

    return Treasure(cursor)
