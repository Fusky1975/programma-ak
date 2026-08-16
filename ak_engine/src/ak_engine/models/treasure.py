"""Treasure/magic-item type model (``HostAK/TP/CTBOTH.PAS`` `treasure`
enum, ``HostAK/TP/PROSE/TREASURE.X2``/``TREASAB.X2``) -- Phase 77.

This is the *type* catalog only (mirrors ``models/monster.py Monster``),
not a physical item instance (that would mirror ``models/feature.py
Feature`` -- see ``models/item.py ItemInstance``'s own docstring, Phase
140, for the real ``trowner``/``treaslist``/``trcharges`` registry this
project eventually built). **Automatic population is still a deeper gap
than Feature's own "no world generation" problem**, though: there's no
general item-instance-*creation* Pascal source at all, not even the
partial per-turn population Feature's own world-gen gap implies might
exist somewhere unseen -- confirmed in ``turn/use_mi_decode.py``'s own
docstring, the only call site for ``Add_Tr`` (the one Pascal routine
that ever creates an item instance) is a narrow Valhalla-visitor
special case, not a general pipeline. Phase 140 built the registry
*structure* and its creation *primitive* (``GameState.add_item()``,
mirroring ``Add_Tr`` directly) faithfully; nothing yet calls it
automatically during world generation.

**The Pascal `treasure` enum itself is 113 ordinals** (``CTBOTH.PAS``
lines 606-637, programmatically counted and cross-checked against this
module's own ``Treasure`` below -- ``len(Treasure) == 113``). Almost
every identifier in the declaration is a deliberately obfuscated
nonsense string (``hla``, ``lkdf``, ``wcp``, ``xle``, ...) -- confirmed
by the Pascal source having no naming pattern at all for most of the
list, unlike ``Monster``/``FeatureType``, whose Pascal identifiers are
already meaningful English words. Because of that, this module does
**not** use the raw Pascal identifiers as enum member names (they would
carry no information); instead each member is named systematically by
its confirmed category and position, and the *real* human-readable name
is looked up separately via ``TREASURE_NAME``/``TREASURE_LABEL`` below
-- the same separation ``MONSTER_NAMES``/``FEATURE_TYPE_NAMES`` already
use, just load-bearing here instead of a convenience.

**Category boundaries, confirmed directly from the Pascal declaration's
own blank-line grouping and one inline comment** (``{trcharges records
origin:}`` right before the quest-item block; ``{Arcane's Valor}``
right after the six named uniques):

- ``ABILITY_ITEM`` (ordinals 0-14, 15 items): permanent +1 to one
  ``Ability`` while held. 1:1 positional with ``Ability``'s own 15
  members, confirmed both by the Pascal group's size and by
  ``TREASAB.X2``'s first 15 lines (``"+1 Tactical"``, ``"+1
  ForcedMarch"``, ... ``"+1 Sage"``, exactly ``Ability``'s declared
  order) and ``TREASURE.X2``'s own prose (e.g. "The Standard of Command
  raises your Tactical ability by one level...").
- ``SPELL_WAND`` (15-34, 20 items): a Use_MI-castable wand, one per
  each of the **first 20** ``Spell`` ordinals (``RESURRECTION`` through
  ``INVISIBILITY``), 1:1 positional -- confirmed the same two ways
  (``TREASAB.X2``: ``'Cast "Resurrection" at skill-2'`` ...
  ``'Cast "Invisibility " at skill-2'``; ``TREASURE.X2``: "The Rod of
  Resurrection enables you to cast the Resurrection spell..." through
  "The Ring of Invisibility enables you to cast the Invisibility
  spell..."). This is exactly the ``wcp..pic`` range
  ``turn/use_mi_decode.py``'s own ``Read_More`` sub-read check already
  named without being able to enumerate it.
- ``COMBAT_WEAPON`` (35-39, 5 items) and ``LEADERSHIP_WEAPON`` (40-43,
  4 items): named weapons with a to-hit/damage bonus, the former with a
  special combat effect (e.g. life drain, stun), the latter with a
  race-leadership bonus (Human/Elven/Dwarven/Orcish) instead.
- ``ANTI_MAGIC_AMULET`` (44-48, 5 items): immunity to one Magical
  ``Ability``'s spells, 1:1 positional with the 5 Magical abilities
  (White, Necromancy, Elemental, Psychic, Illusion).
- ``MONSTER_COMMAND_ITEM`` (49-51, 3 items): "adjacent race aid, 33%
  defections" for Dragons, Eagles, and Whales respectively.
- ``SKILL_BOOK`` (52-66, 15 items): a **one-shot, self-consuming** +1
  to one ``Ability`` when read (unlike ``ABILITY_ITEM``, this *is* a
  legitimate Use_MI target -- rulebook [5.9] and ``TREASAB.X2``'s own
  "... when read" phrasing, vs. ability items' passive "operates
  automatically"). 1:1 positional with ``Ability`` again.
- ``GOLD_HOARD`` (67-69, 3 items): a gold-value tier only (``"10-25
  gold"``/``"25-50 gold"``/``"50-100 gold"``), no other mechanical
  effect.
- ``QUEST_ITEM`` (70-91, 22 items): scenario-specific quest-tracking
  items/flags -- explicitly marked by the Pascal comment
  ``{trcharges records origin:}`` right before this block, i.e. these
  ordinals exist so ``trcharges`` can record *where a quest item came
  from*, not to track spell-casting charges the way a wand's
  ``trcharges`` does. Each real quest item is paired with its own
  "_Fu" ("fulfill-ready") flag ordinal immediately after it.
- ``SENTINEL`` (92, 1 item): ``notreasure``, "no treasure" -- the
  empty/none marker.
- ``NAMED_UNIQUE`` (93-98, 6 items): one-of-a-kind artifacts the Pascal
  source's own trailing comment labels ``{Arcane's Valor}`` (a specific
  scenario/storyline, not the general random-treasure table). Unlike
  every other ordinal, these six Pascal identifiers (``Crown_Rohan``,
  ``Amulet_Power``, ``Scepter_Life``, ``Map_Marauders``,
  ``Fang_Vampire``, ``Hammer_Power``) are **not obfuscated** -- a
  further, independent confirmation this group is a distinct, later
  addition to the table rather than part of the original systematic
  design.
- ``UNUSED_EXTENSION`` (99-112, 14 items): ``etr7``..``etr20``,
  declared, never referenced anywhere in the available source -- the
  same "reserved extension slot" convention already excluded outright
  for ``Monster``/``FeatureType``'s own ``em1``-``em10``/``ef1``-
  ``ef10`` slots elsewhere in this project; kept here (rather than
  dropped) only because the surrounding real ordinals 93-98 need their
  own correct numeric position, and dropping the unused tail would
  silently misnumber nothing else -- included for completeness, not
  because any of the 14 carries real content.

**Two independent real-data sources, cross-checked against each other
and against the category boundaries above, with a perfect count match
at every boundary** (``15+20+5+4+5+3+15+3+22+1+6+14 == 113``):

- ``TREASAB.X2`` (93 non-empty lines) gives a short, purely mechanical
  label for ordinals 0-92 **verbatim** (``TREASURE_LABEL`` below) --
  every single line was checked against its expected category in
  order; no line needed to be skipped or re-aligned anywhere in this
  file. Ordinals 93-112 (the six named uniques and the 14 unused
  extension slots) have no ``TREASAB.X2`` line at all -- the file ends
  exactly at ordinal 92's "no treasure".
- ``TREASURE.X2`` gives a longer descriptive paragraph per ordinal,
  from which a real proper name was extracted (``TREASURE_NAME``
  below) for ordinals 0-49, 53-93, and 97-98 (93 ordinals total, a
  different 93 than ``TREASAB.X2``'s own coverage). **Confirmed real
  gaps, not extraction errors**: comparing the file's own paragraph
  content against the expected category at each position exposed two
  places where ``TREASURE.X2`` genuinely skips entries the Pascal enum
  and ``TREASAB.X2`` both still expect -- ordinals 50-52
  (``make1``/``make2``/the Eagle- and Whale-aid items, and
  ``BOOK_TACTICAL``) and 94-96 (``Amulet_Power``/``Scepter_Life``/
  ``Map_Marauders``, three of the six named uniques). Both gaps were
  found by the paragraph immediately after the gap explicitly naming a
  *different* ability/item than positional counting predicted (e.g.
  the paragraph right after ordinal 49's "Crown of Dragon Command"
  jumps straight to "Manual of Speedy Marches" -- Force March, i.e.
  ordinal 53 -- skipping the Eagle-aid, Whale-aid, and
  ``BOOK_TACTICAL`` entries entirely), not assumed. Beyond ordinal 98
  the file pads out with generic ``"it is not a magic item"`` filler
  text (consistent with its own header line, ``"199 3"``, allocating
  more template slots than the 113-member enum actually uses) -- none
  of that filler is transcribed here. The file's own literal typos
  (e.g. ``"Seamansip"`` for "Seamanship", ``"GOds Quest"``) are kept
  verbatim, not silently corrected.
- **``MONSTER_AID_EAGLE``'s own gap is now filled (Phase 196)**: the
  user's own VALHALLA hero roster (``models/valhalla.py``) names this
  item directly -- two different heroes (Otto, Fafnir) each carry
  "Feather of the Great Eagle" -- independently confirming both that
  this ordinal is real and its proper name, from a source outside
  ``TREASURE.X2``.
- **``MONSTER_AID_WHALE``'s own gap is now filled too (Phase 197)**:
  the user supplied its ``TREASURE.X2``-equivalent row directly --
  "Horn of Neptune | Balene | Comando sulle Balene: la Tattica
  determina la resa; 33% di probabilita' di diserzione" -- "Balene"
  (Whales) and the "33% di diserzione" figure match
  ``MONSTER_COMMAND_ITEM``'s own confirmed "33% defections" formula
  exactly. Independently corroborated by ``models/valhalla.py``'s own
  Gelenor (PAGAN), who carries this same item.
- **``BOOK_TACTICAL``'s own gap is now filled too (Phase 198), closing
  the last one below ordinal 93**: the user supplied its own
  description directly -- "Hannibal's Grimoire se letto aumenta il
  talento Tattica (TA) di un livello" ("if read, raises the Tactical
  talent by one level") -- matching ``SKILL_BOOK``'s own confirmed
  "one-shot +1 Ability when read" mechanic and ``TREASURE_LABEL``'s own
  "+1 Tactical when read" line for this exact ordinal. Independently
  corroborated by ``models/valhalla.py``'s own Xerxes (PAGAN), who
  carries this same item -- the last of the 63 distinct VALHALLA item
  names to resolve; none remain unmatched.
- ``TREASURE_ABILITY_ITEM``/``TREASURE_WAND_SPELL``/
  ``TREASURE_BOOK_ABILITY`` expose the three confirmed 1:1 positional
  mappings above as real ``Ability``/``Spell`` lookups, derived
  mechanically from each group's starting ordinal rather than
  hand-copied, so they can't drift out of sync with ``Ability``/
  ``Spell`` if either ever gains a member.

**Explicitly out of scope**: full ``TREASURE.X2`` flavor-text
transcription for every ordinal (only a name was extracted, not the
complete mechanical description -- a further, separate follow-up);
resolving a real item *instance* to its ``Treasure`` type (needs the
still-missing item-instance-creation pipeline, see this module's own
opening paragraph); wiring ``USE_MI_TARGET_CATEGORIES`` into
``turn/use_mi_decode.py``/a future Use_MI execution resolver (not
attempted this phase -- there is still no way to resolve a real
``UseMIRequest.item_instance_id`` to a ``Treasure`` at all, per that
module's own docstring, so a lookup table alone doesn't unblock
execution).
"""

from __future__ import annotations

from enum import Enum

from ak_engine.models.enums import Ability, Spell
from ak_engine.models.race import Race


class TreasureCategory(Enum):
    ABILITY_ITEM = "ability_item"
    SPELL_WAND = "spell_wand"
    COMBAT_WEAPON = "combat_weapon"
    LEADERSHIP_WEAPON = "leadership_weapon"
    ANTI_MAGIC_AMULET = "anti_magic_amulet"
    MONSTER_COMMAND_ITEM = "monster_command_item"
    SKILL_BOOK = "skill_book"
    GOLD_HOARD = "gold_hoard"
    QUEST_ITEM = "quest_item"
    SENTINEL = "sentinel"
    NAMED_UNIQUE = "named_unique"
    UNUSED_EXTENSION = "unused_extension"


# The only two categories Use_MI actually invokes -- rulebook [5.9]:
# everything else "operates automatically". See turn/use_mi_decode.py's
# own docstring for the same 20-wand/15-book count.
USE_MI_TARGET_CATEGORIES = frozenset({TreasureCategory.SPELL_WAND, TreasureCategory.SKILL_BOOK})


class Treasure(Enum):
    # -- Ability items (0-14): permanent +1 Ability while held. Pascal: hla, lkdf, ali, gil, abjil, alih, vile, abjle, bmweu, bnhum, aehnm, bjiue, aliue, blie, lhl (obfuscated by design)
    ABILITY_TACTICAL = 0
    ABILITY_MARCH = 1
    ABILITY_NAVAL = 2
    ABILITY_ARCHERY = 3
    ABILITY_MELEE = 4
    ABILITY_WHITE = 5
    ABILITY_NECROMANCY = 6
    ABILITY_ELEMENTAL = 7
    ABILITY_PSYCHIC = 8
    ABILITY_ILLUSION = 9
    ABILITY_DRUID = 10
    ABILITY_THIEF = 11
    ABILITY_EXPLORER = 12
    ABILITY_SPY = 13
    ABILITY_SAGE = 14

    # -- Spell wands (15-34): Use_MI casts the paired Spell automatically. Pascal: wcp, elia, biler, anhile, algh, aliemn, hgli, alzn, bfnmz, alien, alizb, xle, bnl, alxu, bnaw, bmen, azx, bneaz, amei, pic (obfuscated)
    WAND_RESURRECTION = 15
    WAND_PART_SEA = 16
    WAND_BLESS = 17
    WAND_HOLY_SYMBOL = 18
    WAND_SKELETAL_ARMY = 19
    WAND_KILL_ENEMY = 20
    WAND_PLAGUE = 21
    WAND_HAND_OF_DEATH = 22
    WAND_FLOOD = 23
    WAND_TORNADO = 24
    WAND_EARTHQUAKE = 25
    WAND_FIREBALL = 26
    WAND_CHARM = 27
    WAND_ORATORY = 28
    WAND_CLAIRVOYANCE = 29
    WAND_PSYCHIC_BLAST = 30
    WAND_ILLUS_TERRAIN = 31
    WAND_ILLUS_ARMIES = 32
    WAND_HIDE_FEATURE = 33
    WAND_INVISIBILITY = 34

    # -- Combat weapons (35-39): to-hit/damage bonus + a special combat effect. Pascal: helplev0-4
    WEAPON_1 = 35
    WEAPON_2 = 36
    WEAPON_3 = 37
    WEAPON_4 = 38
    WEAPON_5 = 39

    # -- Leadership weapons (40-43): to-hit/damage bonus + one race's leadership bonus. Pascal: rlev0-3
    LEADERSHIP_HUMAN = 40
    LEADERSHIP_ELVEN = 41
    LEADERSHIP_DWARVEN = 42
    LEADERSHIP_ORCISH = 43

    # -- Anti-magic amulets (44-48): immunity to one Magical Ability's spells. Pascal: kil0-4
    AMULET_ANTI_WHITE = 44
    AMULET_ANTI_NECROMANCY = 45
    AMULET_ANTI_ELEMENTAL = 46
    AMULET_ANTI_PSYCHIC = 47
    AMULET_ANTI_ILLUSION = 48

    # -- Monster-command items (49-51): adjacent-race aid + defection chance. Pascal: make0-2
    MONSTER_AID_DRAGON = 49
    MONSTER_AID_EAGLE = 50
    MONSTER_AID_WHALE = 51

    # -- Skill books (52-66): one-shot, self-consuming +1 Ability when read (a real Use_MI target, unlike ability items). Pascal: alr, vmoi, einb, klsi, vnia, aeli, bxai, zeil, jlsi, lmie, vmlia, lhjbi, bnmui, liem, rali (obfuscated)
    BOOK_TACTICAL = 52
    BOOK_MARCH = 53
    BOOK_NAVAL = 54
    BOOK_ARCHERY = 55
    BOOK_MELEE = 56
    BOOK_WHITE = 57
    BOOK_NECROMANCY = 58
    BOOK_ELEMENTAL = 59
    BOOK_PSYCHIC = 60
    BOOK_ILLUSION = 61
    BOOK_DRUID = 62
    BOOK_THIEF = 63
    BOOK_EXPLORER = 64
    BOOK_SPY = 65
    BOOK_SAGE = 66

    # -- Gold hoards (67-69): a gold-value tier only. Pascal: LargeTr, HugeTr, FabTr
    GOLD_HOARD_LARGE = 67
    GOLD_HOARD_HUGE = 68
    GOLD_HOARD_FABULOUS = 69

    # -- Quest items (70-91): scenario-specific quest-tracking items/flags, each paired with its own "_Fu" (fulfill-ready) flag ordinal. Pascal: Snow_Quest..Contract_Fu
    QUEST_SNOW_QUEST = 70
    QUEST_SNOWBALL = 71
    QUEST_SNOW_FULFILL = 72
    QUEST_SAPPH_RING = 73
    QUEST_SAPPH_FULFILL = 74
    QUEST_LUCKY_PENNY = 75
    QUEST_LUCK_FULFILL = 76
    QUEST_GODS_QUEST = 77
    QUEST_GODS_FULFILL = 78
    QUEST_MERMAID_AMULET = 79
    QUEST_MERMAID_FULFILL = 80
    QUEST_RA_RIDDLE = 81
    QUEST_RA_COFFIN = 82
    QUEST_RA_BRIDGE = 83
    QUEST_RA_CANDLE = 84
    QUEST_RA_SMOKE = 85
    QUEST_RA_OWNER = 86
    QUEST_RA_MAN = 87
    QUEST_KILL_QUEST = 88
    QUEST_KILL_FULFILL = 89
    QUEST_CONTRACT = 90
    QUEST_CONTRACT_FULFILL = 91

    # -- Sentinel (92): "no treasure". Pascal: notreasure
    NO_TREASURE = 92

    # -- Named uniques (93-98): "Arcane's Valor" scenario artifacts -- the only 6 ordinals whose Pascal identifiers are NOT obfuscated. Pascal: Crown_Rohan, Amulet_Power, Scepter_Life, Map_Marauders, Fang_Vampire, Hammer_Power
    NAMED_UNIQUE_CROWN_ROHAN = 93
    NAMED_UNIQUE_AMULET_POWER = 94
    NAMED_UNIQUE_SCEPTER_LIFE = 95
    NAMED_UNIQUE_MAP_MARAUDERS = 96
    NAMED_UNIQUE_FANG_VAMPIRE = 97
    NAMED_UNIQUE_HAMMER_POWER = 98

    # -- Unused extension slots (99-112): declared, never referenced anywhere in the available source. Pascal: etr7..etr20
    UNUSED_7 = 99
    UNUSED_8 = 100
    UNUSED_9 = 101
    UNUSED_10 = 102
    UNUSED_11 = 103
    UNUSED_12 = 104
    UNUSED_13 = 105
    UNUSED_14 = 106
    UNUSED_15 = 107
    UNUSED_16 = 108
    UNUSED_17 = 109
    UNUSED_18 = 110
    UNUSED_19 = 111
    UNUSED_20 = 112


_CATEGORY_RANGES: tuple[tuple[TreasureCategory, int, int], ...] = (
    (TreasureCategory.ABILITY_ITEM, 0, 14),
    (TreasureCategory.SPELL_WAND, 15, 34),
    (TreasureCategory.COMBAT_WEAPON, 35, 39),
    (TreasureCategory.LEADERSHIP_WEAPON, 40, 43),
    (TreasureCategory.ANTI_MAGIC_AMULET, 44, 48),
    (TreasureCategory.MONSTER_COMMAND_ITEM, 49, 51),
    (TreasureCategory.SKILL_BOOK, 52, 66),
    (TreasureCategory.GOLD_HOARD, 67, 69),
    (TreasureCategory.QUEST_ITEM, 70, 91),
    (TreasureCategory.SENTINEL, 92, 92),
    (TreasureCategory.NAMED_UNIQUE, 93, 98),
    (TreasureCategory.UNUSED_EXTENSION, 99, 112),
)

TREASURE_CATEGORY: dict[Treasure, TreasureCategory] = {
    t: category for category, lo, hi in _CATEGORY_RANGES for t in Treasure if lo <= t.value <= hi
}

# The three confirmed 1:1 positional mappings onto existing enums (see
# module docstring) -- derived from each group's starting ordinal so they
# can't drift out of sync with Ability/Spell.
TREASURE_ABILITY_ITEM: dict[Treasure, Ability] = {Treasure(i): ability for i, ability in enumerate(Ability)}
TREASURE_WAND_SPELL: dict[Treasure, Spell] = {
    Treasure(15 + spell.value): spell for spell in Spell if spell.value < 20
}
TREASURE_BOOK_ABILITY: dict[Treasure, Ability] = {Treasure(52 + ability.value): ability for ability in Ability}

# Phase 530: the 5 Anti-Magic Amulets (44-48), 1:1 positional with the 5
# Magical abilities in their own declared order (White=5..Illusion=9,
# offset by 39 -- AMULET_ANTI_WHITE=44 through AMULET_ANTI_ILLUSION=48).
# See ``turn/discovery_effects.py holds_anti_magic_amulet()`` for the
# actual immunity check wired into cast resolution.
ANTI_MAGIC_AMULET_BY_ABILITY: dict[Ability, Treasure] = {
    ability: Treasure(39 + ability.value)
    for ability in (Ability.WHITE, Ability.NECROMANCY, Ability.ELEMENTAL, Ability.PSYCHIC, Ability.ILLUSION)
}

# Phase 531: AKGEN_reverse_engineering_report (4).md SS8 -- each amulet's
# real *personal* immunity is to specific named spells only, not every
# spell of the matching magic college the way Phase 530 guessed (the only
# source available at that time gave detail for just the Psychic amulet).
# ``ANTI_MAGIC_AMULET_BY_ABILITY`` above is kept -- SS8's own separate,
# genuinely whole-college mechanic (halving the cast-success *chance* of a
# matching-college spell targeted at a province the amulet's holder owns)
# still needs the ability-keyed lookup; see ``turn/discovery_effects.py
# province_halves_spell_chance()``. ``AMULET_ANTI_ILLUSION`` (Crystal of
# True Seeing) is deliberately absent here -- SS8 point 3 makes it a
# structurally different mechanic (illusion detection + a Phantasmal
# Armies halving), not a spell block; see that module's own Phase 532
# addendum.
AMULET_BLOCKED_SPELLS: dict[Treasure, frozenset[Spell]] = {
    Treasure.AMULET_ANTI_WHITE: frozenset({Spell.HOLY_SYMBOL}),
    Treasure.AMULET_ANTI_NECROMANCY: frozenset({Spell.KILL_ENEMY, Spell.HAND_OF_DEATH}),
    Treasure.AMULET_ANTI_ELEMENTAL: frozenset({Spell.FIREBALL}),
    Treasure.AMULET_ANTI_PSYCHIC: frozenset({Spell.CHARM, Spell.PSYCHIC_BLAST}),
}

# The user's own rules 3-6 (Phase 279): one race-matching legendary
# leadership item per humanoid race -- moved here (Phase 285) from
# ``turn/army_quality.py``, its original single owner, so ``turn/
# battle_orchestrator.py`` can share the same table without a circular
# import (``army_quality.py`` itself imports from ``battle_orchestrator.py``).
# No entry for any non-humanoid race -- the user's rules only ever named
# these four ``LEADERSHIP_WEAPON`` ordinals.
RACE_LEADERSHIP_TREASURE: dict[Race, Treasure] = {
    Race.HUMAN: Treasure.LEADERSHIP_HUMAN,
    Race.ELVEN: Treasure.LEADERSHIP_ELVEN,
    Race.DWARVEN: Treasure.LEADERSHIP_DWARVEN,
    Race.ORCISH: Treasure.LEADERSHIP_ORCISH,
}

# Phase 430: the real ADVENTURE-report display name for a gold-hoard
# feature ("Large Hoard of Gold (#N): 10-25 gold" etc.), confirmed
# against real Turn-0 reports for the LARGE tier and directly from this
# module's own enum-member names (`GOLD_HOARD_HUGE`/`_FABULOUS`, in turn
# from the Pascal identifiers `HugeTr`/`FabTr`) for the other two --
# distinct from `TREASURE_NAME`'s own bare "Hoard" (TREASURE.X2's own
# flavor-name extraction, not what the report actually prints).
GOLD_HOARD_DISPLAY_NAME: dict[Treasure, str] = {
    Treasure.GOLD_HOARD_LARGE: "Large Hoard of Gold",
    Treasure.GOLD_HOARD_HUGE: "Huge Hoard of Gold",
    Treasure.GOLD_HOARD_FABULOUS: "Fabulous Hoard of Gold",
}


# Phase 393: the same "which race does this item favor" convention as
# ``RACE_LEADERSHIP_TREASURE`` above, for AKGEN's own confirmed
# `battle_engine.special_events` "Dragon/Eagle/Whale summoning item" row
# -- see ``turn/battle_orchestrator.py``'s own Phase 393 addendum for the
# "adjacent unled matching units aid the bearer" mechanic this feeds.
MONSTER_SUMMONING_TREASURE: dict[Race, Treasure] = {
    Race.DRAGONS: Treasure.MONSTER_AID_DRAGON,
    Race.EAGLES: Treasure.MONSTER_AID_EAGLE,
    Race.WHALES: Treasure.MONSTER_AID_WHALE,
}


# HostAK/TP/PROSE/TREASAB.X2, verbatim, ordinals 0-92 (93 lines -- the file
# ends exactly at "no treasure"; see module docstring for why ordinals
# 93-112 have no line here).
TREASURE_LABEL: dict[Treasure, str] = {
    Treasure.ABILITY_TACTICAL: "+1 Tactical",
    Treasure.ABILITY_MARCH: "+1 ForcedMarch",
    Treasure.ABILITY_NAVAL: "+1 Naval",
    Treasure.ABILITY_ARCHERY: "+1 Archery",
    Treasure.ABILITY_MELEE: "+1 Melee",
    Treasure.ABILITY_WHITE: "+1 White",
    Treasure.ABILITY_NECROMANCY: "+1 Necromancy",
    Treasure.ABILITY_ELEMENTAL: "+1 Elemental",
    Treasure.ABILITY_PSYCHIC: "+1 Psychic",
    Treasure.ABILITY_ILLUSION: "+1 Illusionist",
    Treasure.ABILITY_DRUID: "+1 Druid",
    Treasure.ABILITY_THIEF: "+1 Thief",
    Treasure.ABILITY_EXPLORER: "+1 Explorer",
    Treasure.ABILITY_SPY: "+1 Spy",
    Treasure.ABILITY_SAGE: "+1 Sage",
    Treasure.WAND_RESURRECTION: 'Cast "Resurrection" at skill-2',
    Treasure.WAND_PART_SEA: 'Cast "Part Sea" at skill-2',
    Treasure.WAND_BLESS: 'Cast "Bless" at skill-2',
    Treasure.WAND_HOLY_SYMBOL: 'Cast "Holy Symbol" at skill-2',
    Treasure.WAND_SKELETAL_ARMY: 'Cast "Skeletal Army" at skill-2',
    Treasure.WAND_KILL_ENEMY: 'Cast "Kill Enemy" at skill-2',
    Treasure.WAND_PLAGUE: 'Cast "Plague" at skill-2',
    Treasure.WAND_HAND_OF_DEATH: 'Cast "Hand of Death" at skill-2',
    Treasure.WAND_FLOOD: 'Cast "Flood" at skill-2',
    Treasure.WAND_TORNADO: 'Cast "Tornado" at skill-2',
    Treasure.WAND_EARTHQUAKE: 'Cast "Earthquake" at skill-2',
    Treasure.WAND_FIREBALL: 'Cast "Fireball" at skill-2',
    Treasure.WAND_CHARM: 'Cast "Charm" at skill-2',
    Treasure.WAND_ORATORY: 'Cast "Oratory" at skill-2',
    Treasure.WAND_CLAIRVOYANCE: 'Cast "Clairvoyance" at skill-2',
    Treasure.WAND_PSYCHIC_BLAST: 'Cast "Psychic Blast" at skill-2',
    Treasure.WAND_ILLUS_TERRAIN: 'Cast "Illusory Terrain" at skill-2',
    Treasure.WAND_ILLUS_ARMIES: 'Cast "Phantasmal Armies" at skill-2',
    Treasure.WAND_HIDE_FEATURE: 'Cast "Hide Feature" at skill-2',
    Treasure.WAND_INVISIBILITY: 'Cast "Invisibility " at skill-2',
    Treasure.WEAPON_1: '+20% to hit, +3 damage (+40%/+5 vs. Undead); Level-4 "Holy Symbol"',
    Treasure.WEAPON_2: '+15% to hit, +1 damage, 50% "life drain"',
    Treasure.WEAPON_3: '+20% to hit, +3 damage; 5% "instant death fireball"',
    Treasure.WEAPON_4: "+20% to hit, +3 damage; 50% stun per hit",
    Treasure.WEAPON_5: "+10% to hit, +2 damage; Level-2 Invisibility",
    Treasure.LEADERSHIP_HUMAN: "+25% to hit, +4 damage; Human Leadership",
    Treasure.LEADERSHIP_ELVEN: "+25% to hit, +2 damage; Elven Leadership",
    Treasure.LEADERSHIP_DWARVEN: "+20% to hit, +3 damage; Dwarven Leadership",
    Treasure.LEADERSHIP_ORCISH: "+20% to hit, +2 damage; Orcish Leadership",
    Treasure.AMULET_ANTI_WHITE: "Protection from White Magic spells",
    Treasure.AMULET_ANTI_NECROMANCY: "Protection from Necromancy spells",
    Treasure.AMULET_ANTI_ELEMENTAL: "Protection from Elemental spells",
    Treasure.AMULET_ANTI_PSYCHIC: "Protection from Psychic spells",
    Treasure.AMULET_ANTI_ILLUSION: "Protection from Illusionist spells",
    Treasure.MONSTER_AID_DRAGON: "Adjacent Dragon aid, 33% defections, TA-lk treasure",
    Treasure.MONSTER_AID_EAGLE: "Adjacent Eagle aid, 33% defections, TA-lk treasure",
    Treasure.MONSTER_AID_WHALE: "Adjacent Whale aid, 33% defections, TA-lk treasure",
    Treasure.BOOK_TACTICAL: "+1 Tactical when read",
    Treasure.BOOK_MARCH: "+1 ForcedMarch when read",
    Treasure.BOOK_NAVAL: "+1 Naval when read",
    Treasure.BOOK_ARCHERY: "+1 Archery when read",
    Treasure.BOOK_MELEE: "+1 Melee when read",
    Treasure.BOOK_WHITE: "+1 White when read",
    Treasure.BOOK_NECROMANCY: "+1 Necromancy when read",
    Treasure.BOOK_ELEMENTAL: "+1 Elemental when read",
    Treasure.BOOK_PSYCHIC: "+1 Psychic when read",
    Treasure.BOOK_ILLUSION: "+1 Illusionist when read",
    Treasure.BOOK_DRUID: "+1 Druid when read",
    Treasure.BOOK_THIEF: "+1 Thief when read",
    Treasure.BOOK_EXPLORER: "+1 Explorer when read",
    Treasure.BOOK_SPY: "+1 Spy when read",
    Treasure.BOOK_SAGE: "+1 Sage when read",
    Treasure.GOLD_HOARD_LARGE: "10-25 gold",
    Treasure.GOLD_HOARD_HUGE: "25-50 gold",
    Treasure.GOLD_HOARD_FABULOUS: "50-100 gold",
    Treasure.QUEST_SNOW_QUEST: "Must take to Icecap",
    Treasure.QUEST_SNOWBALL: "Must take to volcano",
    Treasure.QUEST_SNOW_FULFILL: "May Fulfill quest now",
    Treasure.QUEST_SAPPH_RING: "Must take to volcano",
    Treasure.QUEST_SAPPH_FULFILL: "May Fulfill quest now",
    Treasure.QUEST_LUCKY_PENNY: "Must take to wishing well",
    Treasure.QUEST_LUCK_FULFILL: "May Fulfill quest now",
    Treasure.QUEST_GODS_QUEST: "Must investigate strange Gods",
    Treasure.QUEST_GODS_FULFILL: "May Fulfill quest now",
    Treasure.QUEST_MERMAID_AMULET: "Must take to mermaids",
    Treasure.QUEST_MERMAID_FULFILL: "May Fulfill quest now",
    Treasure.QUEST_RA_RIDDLE: "May guess any possible answers",
    Treasure.QUEST_RA_COFFIN: "May guess any possible answers",
    Treasure.QUEST_RA_BRIDGE: "May guess any possible answers",
    Treasure.QUEST_RA_CANDLE: "May guess any possible answers",
    Treasure.QUEST_RA_SMOKE: "May guess any possible answers",
    Treasure.QUEST_RA_OWNER: "May guess any possible answers",
    Treasure.QUEST_RA_MAN: "May guess any possible answers",
    Treasure.QUEST_KILL_QUEST: "Must kill hero",
    Treasure.QUEST_KILL_FULFILL: "May Fulfill quest now",
    Treasure.QUEST_CONTRACT: "May sell soul",
    Treasure.QUEST_CONTRACT_FULFILL: "Soul is gone!",
    Treasure.NO_TREASURE: "no treasure",
}


# HostAK/TP/PROSE/TREASURE.X2-derived proper names, ordinals 0-49, 53-93,
# and 97-98 only (93 ordinals total -- see module docstring for the two
# confirmed real gaps at 50-52 and 94-96, and why nothing past 98 is
# transcribed). The file's own literal typos are kept verbatim.
TREASURE_NAME: dict[Treasure, str] = {
    Treasure.ABILITY_TACTICAL: "Standard of Command",
    Treasure.ABILITY_MARCH: "Magical Register of Marching Orders",
    Treasure.ABILITY_NAVAL: "Conch of Seamansip",
    Treasure.ABILITY_ARCHERY: "Longbow of Accuracy",
    Treasure.ABILITY_MELEE: "Bracelets of Swordsmanship",
    Treasure.ABILITY_WHITE: "Holy Grail",
    Treasure.ABILITY_NECROMANCY: "Amulet of Orgoth",
    Treasure.ABILITY_ELEMENTAL: "Crucible of Elements",
    Treasure.ABILITY_PSYCHIC: "Helm of Psychic Projection",
    Treasure.ABILITY_ILLUSION: "Spectral Crystal",
    Treasure.ABILITY_DRUID: "Everlasting Mistletoe",
    Treasure.ABILITY_THIEF: "Cloak of Stealth",
    Treasure.ABILITY_EXPLORER: "Crystal of Direction",
    Treasure.ABILITY_SPY: "X-Ray Spyglass",
    Treasure.ABILITY_SAGE: "Portable Laboratory of Qua'al Naggoth",
    Treasure.WAND_RESURRECTION: "Rod of Resurrection",
    Treasure.WAND_PART_SEA: "Staff of Sea Mastery",
    Treasure.WAND_BLESS: "Tome of Blessings",
    Treasure.WAND_HOLY_SYMBOL: "Golden Cross",
    Treasure.WAND_SKELETAL_ARMY: "Horn of Ghastly Revenge",
    Treasure.WAND_KILL_ENEMY: "Needles of the Black Mage",
    Treasure.WAND_PLAGUE: "Obsidian Vermin",
    Treasure.WAND_HAND_OF_DEATH: "Glove of Death",
    Treasure.WAND_FLOOD: "Feathers of Rain-Dancing",
    Treasure.WAND_TORNADO: "Bag of Dust-Devil Seeds",
    Treasure.WAND_EARTHQUAKE: "Stone of Shaking",
    Treasure.WAND_FIREBALL: "Wand of Fire",
    Treasure.WAND_CHARM: "Cologne of Charming",
    Treasure.WAND_ORATORY: "Silver Horn of Oratory",
    Treasure.WAND_CLAIRVOYANCE: "Crystal of Seeing",
    Treasure.WAND_PSYCHIC_BLAST: "Antennae of Psychic Blasting",
    Treasure.WAND_ILLUS_TERRAIN: "Projector of Scenic Illusions",
    Treasure.WAND_ILLUS_ARMIES: "Reflector of Armies",
    Treasure.WAND_HIDE_FEATURE: "Dome of Opacity",
    Treasure.WAND_INVISIBILITY: "Ring of Invisibility",
    Treasure.WEAPON_1: "Holy Sword",
    Treasure.WEAPON_2: "Shadow Sword",
    Treasure.WEAPON_3: "Flaming Scimitar",
    Treasure.WEAPON_4: "Psychic Flail",
    Treasure.WEAPON_5: "Invisible Sword",
    Treasure.LEADERSHIP_HUMAN: "Excalibur",
    Treasure.LEADERSHIP_ELVEN: "Bow of the Elven Kings",
    Treasure.LEADERSHIP_DWARVEN: "Axe of the Dwarven Lords",
    Treasure.LEADERSHIP_ORCISH: "Scimitar of Orc Mastery",
    Treasure.AMULET_ANTI_WHITE: "Shrunken-Head Amulet",
    Treasure.AMULET_ANTI_NECROMANCY: "True Cross",
    Treasure.AMULET_ANTI_ELEMENTAL: "Golden Orb of Elemental Stability",
    Treasure.AMULET_ANTI_PSYCHIC: "Helm of Psychic Dampening",
    Treasure.AMULET_ANTI_ILLUSION: "Crystal of True Seeing",
    Treasure.MONSTER_AID_DRAGON: "Crown of Dragon Command",
    # Phase 196: sourced from models/valhalla.py's VALHALLA_ROSTER (Otto,
    # Fafnir), not TREASURE.X2 -- see module docstring's own gap note above.
    Treasure.MONSTER_AID_EAGLE: "Feather of the Great Eagle",
    # Phase 197: user-supplied directly (Italian TREASURE.X2-equivalent
    # table row): "Horn of Neptune | Balene | Comando sulle Balene: la
    # Tattica determina la resa; 33% di probabilita' di diserzione" --
    # "Balene" = Whales, and "33% di diserzione" matches
    # MONSTER_COMMAND_ITEM's own confirmed "33% defections" formula
    # exactly. Independently corroborated by a VALHALLA hero (Gelenor,
    # PAGAN) carrying this same item -- see models/valhalla.py.
    Treasure.MONSTER_AID_WHALE: "Horn of Neptune",
    # Phase 198: user-supplied directly -- "Hannibal's Grimoire se letto
    # aumenta il talento Tattica (TA) di un livello" ("if read, raises
    # Tactical by one level"), matching SKILL_BOOK's own "+1 Ability when
    # read" mechanic and TREASURE_LABEL's own "+1 Tactical when read" for
    # this exact ordinal. Corroborated by a VALHALLA hero (Xerxes, PAGAN)
    # carrying this same item -- see models/valhalla.py.
    Treasure.BOOK_TACTICAL: "Hannibal's Grimoire",
    Treasure.BOOK_MARCH: "Manual of Speedy Marches",
    Treasure.BOOK_NAVAL: "Ship's Log of Nautilus III",
    Treasure.BOOK_ARCHERY: "Manual of Archery",
    Treasure.BOOK_MELEE: "Handbook of Swordsmanship",
    Treasure.BOOK_WHITE: "Scriptures of Holy Thoughts",
    Treasure.BOOK_NECROMANCY: "Necronomicon",
    Treasure.BOOK_ELEMENTAL: "Periodic Table of Elements",
    Treasure.BOOK_PSYCHIC: "Codex of Mental Prowess",
    Treasure.BOOK_ILLUSION: "Libram of Illusions",
    Treasure.BOOK_DRUID: "Book of Druidic Incantations",
    Treasure.BOOK_THIEF: "Black Notebook of Thievery",
    Treasure.BOOK_EXPLORER: "Journal of Many Wanderings",
    Treasure.BOOK_SPY: "Manual of Spying",
    Treasure.BOOK_SAGE: "Library of Science",
    Treasure.GOLD_HOARD_LARGE: "Hoard",
    Treasure.GOLD_HOARD_HUGE: "Hoard",
    Treasure.GOLD_HOARD_FABULOUS: "Hoard",
    Treasure.QUEST_SNOW_QUEST: "Snowball Quest",
    Treasure.QUEST_SNOWBALL: "Snowball",
    Treasure.QUEST_SNOW_FULFILL: "Fulfilled Snowball Quest",
    Treasure.QUEST_SAPPH_RING: "Sapphire Ring",
    Treasure.QUEST_SAPPH_FULFILL: "Fulfilled Sapphire Quest",
    Treasure.QUEST_LUCKY_PENNY: "Lucky Penny",
    Treasure.QUEST_LUCK_FULFILL: "Fulfilled Penny Quest",
    Treasure.QUEST_GODS_QUEST: "GOds Quest",
    Treasure.QUEST_GODS_FULFILL: "THe Fulffilled Gods Quest",
    Treasure.QUEST_MERMAID_AMULET: "Amulet",
    Treasure.QUEST_MERMAID_FULFILL: "Fulfilled Mermaid Quest",
    Treasure.QUEST_RA_RIDDLE: "Riddle",
    Treasure.QUEST_RA_COFFIN: "Riddle",
    Treasure.QUEST_RA_BRIDGE: "Riddle",
    Treasure.QUEST_RA_CANDLE: "Riddle",
    Treasure.QUEST_RA_SMOKE: "Riddle",
    Treasure.QUEST_RA_OWNER: "Riddle",
    Treasure.QUEST_RA_MAN: "Riddle",
    Treasure.QUEST_KILL_QUEST: "Kill Quest",
    Treasure.QUEST_KILL_FULFILL: "Fulfilled Kill Quest",
    Treasure.QUEST_CONTRACT: "Contract",
    Treasure.QUEST_CONTRACT_FULFILL: "Signed Contract",
    Treasure.NO_TREASURE: "No treasure",
    Treasure.NAMED_UNIQUE_CROWN_ROHAN: "Crown of Rohan",
    # NAMED_UNIQUE_AMULET_POWER, NAMED_UNIQUE_SCEPTER_LIFE, NAMED_UNIQUE_MAP_MARAUDERS: no TREASURE.X2 entry (confirmed gap, see module docstring)
    Treasure.NAMED_UNIQUE_FANG_VAMPIRE: "Fang of the Vampire Lord",
    Treasure.NAMED_UNIQUE_HAMMER_POWER: "Hammer of Power",
}
