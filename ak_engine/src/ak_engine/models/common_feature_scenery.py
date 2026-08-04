"""Common feature scenery vocabulary (Phase 383): the mundane, non-magical
set-dressing found inside a geographic ``Feature`` (Pyramid, Tomb, Cave,
etc.), distinct from -- and explicitly not to be confused with -- the
already-implemented ``models.magic_feature.MagicFeature`` magical
landmarks (Phase 92/361).

Source: the AKGEN reverse-engineering material's own
``tables.common_feature_scenery`` catalog -- ``HostAK/TP/CTME.PAS``'s own
``comfeat`` enum, 27 real members, confirmed by the Italian summary in
``AKGEN_reverse_engineering_report.md`` ("Esiste anche un secondo
livello, la scenografia comune `comfeat`... Non vanno confusi con i
luoghi magici della tabella precedente").

**Deliberately NOT implemented here: the selection formula itself.**
The catalog's own ``selection_formula`` field gives the shape --
``cf1[feature_type] + ((feature_index + feature_type) mod
(cff[feature_type] - cf1[feature_type] + 1))``, structurally identical
to ``worldgen/internal_magical_locations.py candidate_location()``'s own
deterministic formula (Phase 361) -- but, unlike that phase's own
``location_ranges`` table, no per-``FeatureType`` ``cf1``/``cff`` numeric
range pairs are present anywhere in the available catalog or report
material. Implementing ``candidate_scenery()`` would require guessing
32 ``FeatureType`` range pairs out of thin air, which this project's own
standing rule (verify against real source data before writing a formula)
forbids. This is an honest, documented gap -- the same kind of
non-result Phase 382 recorded for the Advanced Ability Schedule -- left
for a real follow-up phase with more disassembly context.
"""

from __future__ import annotations

from enum import Enum


class CommonFeatureScenery(Enum):
    """``CTME.PAS``'s own ``comfeat`` enum, verbatim order (27 members)."""

    NONE = 0
    SEAWEED = 1
    WHIRLPOOL = 2
    TREES = 3
    CLIFF = 4
    LAVA_POOL = 5
    STALACS = 6
    MINE = 7
    QUICKSAND = 8
    CORNER = 9
    PIT = 10
    CPOOL = 11
    STAIRS = 12
    TABLE = 13
    GAMETABLE = 14
    HAMMOCK = 15
    RUG = 16
    FIREPLACE = 17
    PIANO = 18
    CHANDELIER = 19
    CWINDOW = 20
    HIWINDOW = 21
    PASSAGES = 22
    COFFIN = 23
    GONG = 24
    PILLAR = 25
    WELL = 26


# CTME.PAS `comfeat` display strings, verbatim, positional with
# `CommonFeatureScenery`'s own ordinals above.
COMMON_FEATURE_SCENERY_NAME: dict[CommonFeatureScenery, str] = {
    CommonFeatureScenery.NONE: "CFNone",
    CommonFeatureScenery.SEAWEED: "Seaweed",
    CommonFeatureScenery.WHIRLPOOL: "Whirlpool",
    CommonFeatureScenery.TREES: "Trees",
    CommonFeatureScenery.CLIFF: "Cliff",
    CommonFeatureScenery.LAVA_POOL: "LavaPool",
    CommonFeatureScenery.STALACS: "Stalacs",
    CommonFeatureScenery.MINE: "Mine",
    CommonFeatureScenery.QUICKSAND: "Quicksand",
    CommonFeatureScenery.CORNER: "Corner",
    CommonFeatureScenery.PIT: "Pit",
    CommonFeatureScenery.CPOOL: "CPool",
    CommonFeatureScenery.STAIRS: "Stairs",
    CommonFeatureScenery.TABLE: "Table",
    CommonFeatureScenery.GAMETABLE: "Gametable",
    CommonFeatureScenery.HAMMOCK: "Hammock",
    CommonFeatureScenery.RUG: "Rug",
    CommonFeatureScenery.FIREPLACE: "Fireplace",
    CommonFeatureScenery.PIANO: "Piano",
    CommonFeatureScenery.CHANDELIER: "Chandelier",
    CommonFeatureScenery.CWINDOW: "CWindow",
    CommonFeatureScenery.HIWINDOW: "HiWindow",
    CommonFeatureScenery.PASSAGES: "Passages",
    CommonFeatureScenery.COFFIN: "Coffin",
    CommonFeatureScenery.GONG: "Gong",
    CommonFeatureScenery.PILLAR: "Pillar",
    CommonFeatureScenery.WELL: "Well",
}
