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
  race-leadership bonus (Human/Elven/Dwarven/Orcish) instead. **Phase
  535 correction**: this category split describes the *army*-facing
  bonus shape only. On the *personal* to-hit/damage side, AKGEN_reverse_
  engineering_report (4).md SS7.2 confirms all 8 of these weapons except
  ``LEADERSHIP_ELVEN`` (Bow of the Elven Kings) share one mutually-
  exclusive "equipped weapon" slot -- see ``WEAPON_HIT_BONUS``'s own
  addendum below, not two separate mechanisms.
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
  below) for all 99 real ordinals (0-98). Beyond ordinal 98 the file
  pads out with generic ``"it is not a magic item"`` filler text
  (consistent with its own header line, ``"199 3"``, allocating more
  template slots than the 113-member enum actually uses) -- none of
  that filler is transcribed here. The file's own literal typos (e.g.
  ``"Seamansip"`` for "Seamanship", ``"GOds Quest"``) are kept
  verbatim, not silently corrected.
- **Phase 77's own original pass believed ordinals 50-52 and 94-96 were
  genuinely absent from ``TREASURE.X2``** ("confirmed real gaps"),
  based on the raw copy of the file available at the time -- the
  paragraph immediately after ordinal 49's "Crown of Dragon Command"
  appeared to jump straight to ordinal 53's "Manual of Speedy Marches",
  seemingly skipping three entries. Phases 196-198 filled those three
  (``MONSTER_AID_EAGLE``/``MONSTER_AID_WHALE``/``BOOK_TACTICAL``) from
  independent sources instead -- ``models/valhalla.py``'s own hero
  roster and user-supplied text -- and the other three
  (``NAMED_UNIQUE_AMULET_POWER``/``SCEPTER_LIFE``/``MAP_MARAUDERS``)
  were left with no name at all.
- **Phase 580 correction**: a byte-faithful, independent third-party
  reconstruction of the full 162-file prose corpus
  (``AKPROSE_reverse_engineering_report.md``, supplied directly by the
  user) reproduces ``TREASURE.X2`` in full, and all six "missing"
  ordinals are present in it, at exactly the positions the Pascal enum
  predicts -- choice 51 ("The Feather of the Great Eagle gives the
  bearer..."), 52 ("The Horn of Neptune gives the bearer..."), and 53
  ("Hannibal's Grimoire raises...") independently confirm the exact
  same three names Phases 196-198 had already sourced elsewhere; choice
  95 ("The Amulet of Power will increase..."), 96 ("The Scepter of Life
  adds..."), and 97 ("The Map of the Marauders adds...") fill the three
  that had no name at all before. Every one of the file's other 93
  already-extracted names was independently cross-checked against this
  new reconstruction too, with zero further discrepancies found -- the
  original "confirmed gap" conclusion is now understood to have been
  drawn from an incomplete copy of the file, not a real property of
  ``TREASURE.X2`` itself.
- ``TREASURE_DESCRIPTION`` (Phase 580, below) is the full paragraph for
  each of the same 99 ordinals, from the same corrected reconstruction
  -- the "further, separate follow-up" Phase 77's own docstring had
  originally deferred.
- ``TREASURE_ABILITY_ITEM``/``TREASURE_WAND_SPELL``/
  ``TREASURE_BOOK_ABILITY`` expose the three confirmed 1:1 positional
  mappings above as real ``Ability``/``Spell`` lookups, derived
  mechanically from each group's starting ordinal rather than
  hand-copied, so they can't drift out of sync with ``Ability``/
  ``Spell`` if either ever gains a member.

**Explicitly out of scope**: automatically *creating* item instances
during world generation (needs the still-missing item-instance-creation
pipeline, see this module's own opening paragraph -- a real, still-open
gap, unrelated to the point below).

**Phase 652 correction, kept for the record**: an earlier version of
this note also claimed "there is still no way to resolve a real
``UseMIRequest.item_instance_id`` to a ``Treasure`` at all" and left
wiring ``USE_MI_TARGET_CATEGORIES`` into a resolver as unattempted --
stale even when written: ``turn/use_mi_execution.py`` (Phase 141) is
exactly that resolver, looking up ``request.item_instance_id`` in
``GameState.items`` directly and dispatching on the resulting
``ItemInstance.treasure``. What's still genuinely missing is only the
*creation* half above, not the resolution half.
"""

from __future__ import annotations

from enum import Enum

from ak_engine.models.enums import Ability, Spell
from ak_engine.models.monster import Monster
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

# Phase 539: AKGEN_reverse_engineering_report (4).md SS12.1 -- Enhanced
# Charm's own item-theft side effect ("NT_Owned(victim,treasure(0),
# treasure(66),picked_slot)") is only eligible for ordinals 0-66:
# passives, spell wands, combat/leadership weapons, anti-magic amulets,
# monster-command items, and skill books. Gold Hoards, Quest items, the
# sentinel, and the 93-98 Named Uniques ("non sono eleggibili hoard,
# quest, contratto o artefatti 93..98") are explicitly excluded.
ENHANCED_CHARM_ELIGIBLE_CATEGORIES = frozenset({
    TreasureCategory.ABILITY_ITEM,
    TreasureCategory.SPELL_WAND,
    TreasureCategory.COMBAT_WEAPON,
    TreasureCategory.LEADERSHIP_WEAPON,
    TreasureCategory.ANTI_MAGIC_AMULET,
    TreasureCategory.MONSTER_COMMAND_ITEM,
    TreasureCategory.SKILL_BOOK,
})


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
# See ``turn/discovery_effects.py holder_is_immune_to_spell()`` (renamed
# from ``holds_anti_magic_amulet()`` by that same function's own Phase
# 531 correction, never updated here) for the actual immunity check
# wired into cast resolution.
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
# province_halves_spell_chance()``.
#
# Phase 532: ``AMULET_ANTI_ILLUSION`` (Crystal of True Seeing) joins this
# table too -- SS8 point 3's "the possessor is unaffected by/sees through"
# wording for Invisibility/Illusory Terrain/Hide Feature is the same
# personal-immunity shape ``holder_is_immune_to_spell()`` already models
# for the other 4 amulets, so it's a direct reuse rather than a new
# mechanism. Phantasmal Armies is deliberately *not* in this amulet's own
# blocked set -- SS8 point 3 treats it separately, as a battle-wide
# strength-bonus halving rather than a personal immunity (see
# ``turn/battle_orchestrator.py``'s own Phase 532 addendum).
AMULET_BLOCKED_SPELLS: dict[Treasure, frozenset[Spell]] = {
    Treasure.AMULET_ANTI_WHITE: frozenset({Spell.HOLY_SYMBOL}),
    Treasure.AMULET_ANTI_NECROMANCY: frozenset({Spell.KILL_ENEMY, Spell.HAND_OF_DEATH}),
    Treasure.AMULET_ANTI_ELEMENTAL: frozenset({Spell.FIREBALL}),
    Treasure.AMULET_ANTI_PSYCHIC: frozenset({Spell.CHARM, Spell.PSYCHIC_BLAST}),
    Treasure.AMULET_ANTI_ILLUSION: frozenset({Spell.INVISIBILITY, Spell.ILLUS_TERRAIN, Spell.HIDE_FEATURE}),
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

# Phase 535: AKGEN_reverse_engineering_report (4).md SS7.1/SS7.2 -- the 9
# magic weapons' personal to-hit/damage bonuses, from the disassembled
# resolver's own two ``case`` blocks (SS7.2). All 8 non-Bow weapons share
# a single mutually-exclusive "equipped weapon" slot -- confirmed by the
# dossier's own single combined ``case equipped of`` covering WEAPON_1..5
# *and* LEADERSHIP_HUMAN/DWARVEN/ORCISH together, not two separate
# mechanisms the way this project's own ``COMBAT_WEAPON``/``LEADERSHIP_
# WEAPON`` category split (Phase 77) might suggest. ``LEADERSHIP_ELVEN``
# (Bow of the Elven Kings) is the sole exception -- SS7.2's own ``if
# attack_is_archery and NT_Owned(...)>0`` branch is a separate, Archery-
# only, possession-gated bonus that never occupies the equip slot (SS7.1
# point 5, verbatim: "Il Bow of the Elven Kings...è un'eccezione: per il
# tiro con l'arco basta possederne almeno uno e il bonus non si
# moltiplica con le copie"). Kept here, not folded into WEAPON_HIT_BONUS/
# WEAPON_DAMAGE_BONUS below, since it's read through a different helper
# (``turn/discovery_effects.py holds_bow_of_elven_kings()``).
WEAPON_HIT_BONUS: dict[Treasure, int] = {
    Treasure.WEAPON_1: 20,  # Holy Sword -- +40 vs Undead, see HOLY_SWORD_HIT_BONUS_VS_UNDEAD
    Treasure.WEAPON_2: 15,  # Shadow Sword
    Treasure.WEAPON_3: 20,  # Flaming Scimitar
    Treasure.WEAPON_4: 20,  # Psychic Flail
    Treasure.WEAPON_5: 10,  # Invisible Sword
    Treasure.LEADERSHIP_HUMAN: 25,  # Excalibur
    Treasure.LEADERSHIP_DWARVEN: 20,  # Axe of the Dwarven Lords
    Treasure.LEADERSHIP_ORCISH: 20,  # Scimitar of Orc Mastery
}
WEAPON_DAMAGE_BONUS: dict[Treasure, int] = {
    Treasure.WEAPON_1: 3,  # Holy Sword -- +5 vs Undead, see HOLY_SWORD_DAMAGE_BONUS_VS_UNDEAD
    Treasure.WEAPON_2: 1,  # Shadow Sword
    Treasure.WEAPON_3: 3,  # Flaming Scimitar
    Treasure.WEAPON_4: 3,  # Psychic Flail
    Treasure.WEAPON_5: 2,  # Invisible Sword
    Treasure.LEADERSHIP_HUMAN: 4,  # Excalibur
    Treasure.LEADERSHIP_DWARVEN: 3,  # Axe of the Dwarven Lords
    Treasure.LEADERSHIP_ORCISH: 2,  # Scimitar of Orc Mastery
}
# Holy Sword's own vs-Undead variant (SS7.1 row 35: "+20%; +40% vs Undead"
# / "+3; +5 vs Undead"). Phase 682 -- now wired: ``turn/encounter.py
# Combatant.is_undead_or_anti_holy`` records each combatant's own nature
# (set by each builder from its own leader's alignment or monster's own
# species, no opponent needed at construction time), and ``apply_temper_
# melee_setup()`` -- the shared, once-both-sides-are-known setup step --
# swaps a Holy-Sword-wielder's already-baked flat bonus for this vs-Undead
# one when the opponent's flag is set. Not auto-applied at the builder's
# own construction time (before this phase's own fix, the blocker was
# real: a builder only ever sees its own side, never the opponent).
HOLY_SWORD_HIT_BONUS_VS_UNDEAD = 40
HOLY_SWORD_DAMAGE_BONUS_VS_UNDEAD = 5

# Bow of the Elven Kings' own Archery-only bonus (SS7.2's separate ``if
# attack_is_archery`` branch) -- see ``WEAPON_HIT_BONUS``'s own addendum
# above for why it's not folded into that dict.
BOW_OF_ELVEN_KINGS_ARCHERY_HIT_BONUS = 25
BOW_OF_ELVEN_KINGS_ARCHERY_DAMAGE_BONUS = 2

# The 8 weapons that share one mutually-exclusive "equipped" slot (every
# ``WEAPON_HIT_BONUS``/``WEAPON_DAMAGE_BONUS`` key) -- ``LEADERSHIP_ELVEN``
# is excluded, per the same addendum.
COMBAT_WEAPON_SLOT_TREASURES: frozenset[Treasure] = frozenset(WEAPON_HIT_BONUS)

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


# Phase 537 -- AKGEN_reverse_engineering_report (4).md SS9's own "TA-lk
# skips the normal social roll" mechanic needs to know which individual
# guardian *species* (``models/monster.py Monster``) count as the
# "Dragon"/"Eagle"/"Whale" family ``MONSTER_SUMMONING_TREASURE`` above
# already keys by ``Race`` -- a different axis than that dict's own army-
# unit-race concern, so it's a separate table, not folded in. Self-
# evident from each species' own real (non-obfuscated) English name, the
# same "no guess needed" confidence ``HAND_OF_DEATH_ANTI_HOLY_MONSTERS``'s
# own real-species enumeration already relies on: all 5 real Dragon
# species, the one real Eagle species, and the one real Whale species.
MONSTER_COMMAND_RACE: dict[Monster, Race] = {
    Monster.R_DRAGON: Race.DRAGONS,
    Monster.B_DRAGON: Race.DRAGONS,
    Monster.GR_DRAGON: Race.DRAGONS,
    Monster.S_DRAGON: Race.DRAGONS,
    Monster.GO_DRAGON: Race.DRAGONS,
    Monster.GI_EAGLE: Race.EAGLES,
    Monster.GW_WHALE: Race.WHALES,
}


class _CuratedNameTable(dict):
    """A ``dict`` that falls back to a title-cased identifier for a key
    with no curated entry, instead of raising ``KeyError`` on ``[...]``.

    Bug fix (crash): ``TREASURE_NAME``/``TREASURE_LABEL`` deliberately
    exclude several reserved ``Treasure`` ordinals (``UNUSED_*``, and
    for ``TREASURE_LABEL`` also the ``NAMED_UNIQUE_*`` artifacts -- see
    this module's own comments) -- a correct, honest gap when every
    caller reads them with ``.get()``, but several real callers across
    report/turn_report.py use bare ``TREASURE_NAME[treasure]``/
    ``TREASURE_LABEL[treasure]`` instead, and the webapp's own feature/
    item editors let a GM set a treasure field to any of these directly
    (``treasure=list(Treasure)``, no filtering) -- an entirely ordinary
    editor action. The very next turn's report generation then crashed
    with an unhandled ``KeyError``. The fallback reuses this project's
    own already-established, tested convention for exactly this
    situation: ``webapp/app.py``'s ``display_name()`` filter already
    falls back to ``value.name.replace("_", " ").title()`` for an
    uncurated enum member (confirmed by its own test,
    ``test_display_name_falls_back_to_the_bare_identifier_when_uncurated``).
    """

    def __missing__(self, key):
        return key.name.replace("_", " ").title()


# HostAK/TP/PROSE/TREASAB.X2, verbatim, ordinals 0-92 (93 lines -- the file
# ends exactly at "no treasure"; see module docstring for why ordinals
# 93-112 have no line here).
TREASURE_LABEL: dict[Treasure, str] = _CuratedNameTable({
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
})


# HostAK/TP/PROSE/TREASURE.X2-derived proper names, all 99 real ordinals
# (0-98) -- see module docstring's Phase 580 correction for why ordinals
# 50-52/94-96 are no longer treated as gaps, and why nothing past 98 is
# transcribed. The file's own literal typos are kept verbatim.
TREASURE_NAME: dict[Treasure, str] = _CuratedNameTable({
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
    # Phase 196: originally sourced from models/valhalla.py's own
    # VALHALLA_ROSTER (Otto, Fafnir), believed at the time to be this
    # ordinal's only source since TREASURE.X2 itself was thought to skip
    # it. Phase 580 found this to be wrong -- the file's own choice 51
    # ("The Feather of the Great Eagle gives the bearer...") independently
    # confirms the identical name; both sources now agree.
    Treasure.MONSTER_AID_EAGLE: "Feather of the Great Eagle",
    # Phase 197: user-supplied directly (Italian TREASURE.X2-equivalent
    # table row): "Horn of Neptune | Balene | Comando sulle Balene: la
    # Tattica determina la resa; 33% di probabilita' di diserzione" --
    # "Balene" = Whales, and "33% di diserzione" matches
    # MONSTER_COMMAND_ITEM's own confirmed "33% defections" formula
    # exactly. Independently corroborated by a VALHALLA hero (Gelenor,
    # PAGAN) carrying this same item -- see models/valhalla.py. Phase 580
    # found TREASURE.X2's own choice 52 agrees too (see Phase 196's own
    # note above for the same correction, now a third confirmation).
    Treasure.MONSTER_AID_WHALE: "Horn of Neptune",
    # Phase 198: user-supplied directly -- "Hannibal's Grimoire se letto
    # aumenta il talento Tattica (TA) di un livello" ("if read, raises
    # Tactical by one level"), matching SKILL_BOOK's own "+1 Ability when
    # read" mechanic and TREASURE_LABEL's own "+1 Tactical when read" for
    # this exact ordinal. Corroborated by a VALHALLA hero (Xerxes, PAGAN)
    # carrying this same item -- see models/valhalla.py. Phase 580 found
    # TREASURE.X2's own choice 53 agrees too, same correction as above.
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
    # Phase 580: previously believed to have no TREASURE.X2 entry at all
    # ("confirmed gap") -- corrected once a byte-faithful, independent
    # reconstruction of the full file (unavailable to the earlier phase)
    # showed real, matching content at exactly these three ordinals. See
    # module docstring's own Phase 580 addendum for the full account.
    Treasure.NAMED_UNIQUE_AMULET_POWER: "Amulet of Power",
    Treasure.NAMED_UNIQUE_SCEPTER_LIFE: "Scepter of Life",
    Treasure.NAMED_UNIQUE_MAP_MARAUDERS: "Map of the Marauders",
    Treasure.NAMED_UNIQUE_FANG_VAMPIRE: "Fang of the Vampire Lord",
    Treasure.NAMED_UNIQUE_HAMMER_POWER: "Hammer of Power",
})

# HostAK/TP/PROSE/TREASURE.X2, verbatim, positional with Treasure's own
# 99 real ordinals (0-98) -- module docstring's Phase 580 addendum.
# Nothing beyond ordinal 98 is included (generic filler, see module
# docstring). The file's own literal typos are kept verbatim, same
# convention TREASURE_NAME already established.
TREASURE_DESCRIPTION: dict[Treasure, str] = {
    Treasure.ABILITY_TACTICAL: 'The Standard of Command raises your Tactical ability by one level while it is in your possession.  A skill level of 0 would rise to skill level 1.',
    Treasure.ABILITY_MARCH: 'The Magical Register of Marching Orders raises your Force March ability by one level while it is in your possession.  A skill level of 0 would rise to skill level 1.',
    Treasure.ABILITY_NAVAL: 'The Conch of Seamansip raises your Naval ability by one level while it is in your possession.  A skill level of 0 would rise to skill level 1.',
    Treasure.ABILITY_ARCHERY: 'The Longbow of Accuracy raises your Archery ability by one level while it is in your possession.  A skill level of 0 would rise to skill level 1.  You do not have to actually wield the Bow in combat to gain the benefit of its modifiers.',
    Treasure.ABILITY_MELEE: 'The Bracelets of Swordsmanship raise your Melee ability by one level while they are in your possession.  A skill level of 0 would rise to skill level 1.',
    Treasure.ABILITY_WHITE: 'The Holy Grail raises your White Magic ability by one level while it is in your possession.  A skill level of 0 would rise to skill level 1.',
    Treasure.ABILITY_NECROMANCY: 'The Amulet of Orgoth raises your Necromantic ability by one level while it is in your possession.  A skill level of 0 would rise to skill level 1.',
    Treasure.ABILITY_ELEMENTAL: 'The Crucible of Elements raises your Elemental Magic ability by one level while it is in your possession.  A skill level of 0 would rise to skill level 1.',
    Treasure.ABILITY_PSYCHIC: 'The Helm of Psychic Projection raises your Psychic Magic ability by one level while it is in your possession.  A skill level of 0 would rise to skill level 1.',
    Treasure.ABILITY_ILLUSION: 'The Spectral Crystal raises your Illusionist ability by one level while it is in your possession.  A skill level of 0 would rise to skill level 1.',
    Treasure.ABILITY_DRUID: 'The Everlasting Mistletoe raises your Druidic ability by one level while it is in your possession.  A skill level of 0 would rise to skill level 1.',
    Treasure.ABILITY_THIEF: 'The Cloak of Stealth raises your Thief ability by one level while it is in your possession.  A skill level of 0 would rise to skill level 1.',
    Treasure.ABILITY_EXPLORER: 'The Crystal of Direction raises your Explorer ability by one level while it is in your possession.  A skill level of 0 would rise to skill level 1.',
    Treasure.ABILITY_SPY: 'The X-Ray Spyglass raises your Spying ability by one level while it is in your possession.  A skill level of 0 would rise to skill level 1.',
    Treasure.ABILITY_SAGE: "The Portable Laboratory of Qua'al Naggoth raises your Sage ability by one level while it is in your possession.  A skill level of 0 would rise to skill level 1.",
    Treasure.WAND_RESURRECTION: 'The Rod of Resurrection enables you to cast the Resurrection spell of the college of White Magic.  There is a certain number of charges in this item, and each time you cast the spell you use up a charge.  When all charges are used up, the item becomes useless.  The spell normally will take effect as if a magician with a skill level of 2 had cast the spell.',
    Treasure.WAND_PART_SEA: 'The Staff of Sea Mastery enables you to cast the Part Sea spell of the college of White Magic.  There is a certain number of charges in this item, and each time you cast the spell you use up a charge.  When all charges are used up, the item becomes useless.  The spell normally will take effect as if a magician with a skill level of 2 had cast the spell.',
    Treasure.WAND_BLESS: 'The Tome of Blessings enables you to cast the Bless spell of the college of White Magic.  There is a certain number of charges in this item, and each time you cast the spell you use up a charge.  When all charges are used up, the item becomesuseless.  The spell normally will take effect as if a magician with a skill level of 2 had cast the spell.',
    Treasure.WAND_HOLY_SYMBOL: 'The Golden Cross enables you to cast the Holy Symbol spell of the college of White Magic.  There is a certain number of charges in this item, and each time you cast the spell you use up a charge.  When all charges are used up, the item becomes useless.  The spell normally will take effect as if a magician with a skill level of 2 had cast the spell.',
    Treasure.WAND_SKELETAL_ARMY: 'The Horn of Ghastly Revenge enables you to cast the Skeletal Army spell of the college of Necromancy.  There is a certain number of charges in this item, and each time you cast the spell you use up a charge.  When all charges are used up, the item becomes useless.  The spell normally will take effect as if a magician with a skill level of 2 had cast the spell.',
    Treasure.WAND_KILL_ENEMY: 'The Needles of the Black Mage enable you to cast the Kill Enemy spell of the college of Necromancy.  There is a certain number of charges in this item, and each time you cast the spell you use up a charge.  When all charges are used up, the item becomes useless.  The spell normally will take effect as if a magician with a skill level of 2 had cast the spell.',
    Treasure.WAND_PLAGUE: 'The Obsidian Vermin enable you to cast the Plague spell of the college of Necromancy.  There is a certain number of charges in this item, and each time you cast the spell you use up a charge.  When all charges are used up, the item becomes useless.  The spell normally will take effect as if a magician with a skill level of 2 had cast the spell.',
    Treasure.WAND_HAND_OF_DEATH: 'The Glove of Death enables you to cast the Hand of Death spell of the college of Necromancy.  There is a certain number of charges in this item, and each time you cast the spell you use up a charge.  When all charges are used up, the item becomes useless.  The spell normally will take effect as if a magician with a skill level of 2 had cast the spell.',
    Treasure.WAND_FLOOD: 'The Feathers of Rain-Dancing enable you to cast the Flood Province spell of the college of Elemental Magic.  There is a certain number of charges in this item, and each time you cast the spell you use up a charge.  When all charges are used up, the item becomes useless.  The spell normally will take effect as if a magician with a skill level of 2 had cast the spell.',
    Treasure.WAND_TORNADO: 'The Bag of Dust-Devil Seeds enables you to cast the Tornado spell of the college of Elemental Magic.  There is a certain number of charges in this item, and each time you cast the spell you use up a charge.  When all charges are used up, the item becomes useless.  The spell normally will take effect as if a magician with a skill level of 2 had cast the spell.',
    Treasure.WAND_EARTHQUAKE: 'The Stone of Shaking enables you to cast the Earthquake spell of the college of Elemental Magic.  There is a certain number of charges in this item, and each time you cast the spell you use up a charge.  When all charges are used up, the item becomes useless.  The spell normally will take effect as if a magician with a skill level of 2 had cast the spell.',
    Treasure.WAND_FIREBALL: 'The Wand of Fire enables you to cast the Fireball spell of the college of Elemental Magic.  There is a certain number of charges in this item, and each time you cast the spell you use up a charge.  When all charges are used up, the item becomes useless.  The spell normally will take effect as if a magician with a skill level of 2 had cast the spell.',
    Treasure.WAND_CHARM: 'The Cologne of Charming enables you to cast the Charm spell of the college of Psychic Magic.  There is a certain number of charges in this item, and each time you cast the spell you use up a charge.  When all charges are used up, the item becomes useless.  The spell normally will take effect as if a magician with a skill level of 2 had cast the spell.',
    Treasure.WAND_ORATORY: 'The Silver Horn of Oratory enables you to cast the Oratory spell of the college of Psychic Magic.  There is a certain number of charges in this item, and each time you cast the spell you use up a charge.  When all charges are used up, the item becomes useless.  The spell normally will take effect as if a magician with a skill level of 2 had cast the spell.',
    Treasure.WAND_CLAIRVOYANCE: 'The Crystal of Seeing enables you to cast the Clairvoyance spell of the college of Psychic Magic.  There is a certain number of charges in this item, and each time you cast the spell you use up a charge.  When all charges are used up, the item becomes useless.  The spell normally will take effect as if a magician with a skill level of 2 had cast the spell.',
    Treasure.WAND_PSYCHIC_BLAST: 'The Antennae of Psychic Blasting enable you to cast the Psychic Blast spell of the college of Psychic Magic.  There is a certain number of charges in this item, and each time you cast the spell you use up a charge.  When all charges are used up, the item becomes useless.  The spell normally will take effect as if a magician with a skill level of 2 had cast the spell.',
    Treasure.WAND_ILLUS_TERRAIN: 'The Projector of Scenic Illusions enables you to cast the Illusory Terrain spell of the college of Illusory Magic.  There is a certain number of charges in this item, and each time you cast the spell you use up a charge.  When all charges are used up, the item becomes useless.  The spell normally will take effect as if a magician with a skill level of 2 had cast the spell.',
    Treasure.WAND_ILLUS_ARMIES: 'The Reflector of Armies enables you to cast the Phantasmal Armies spell of the college of Illusory Magic.  There is a certain number of charges in this item, and each time you cast the spell you use up a charge.  When all charges are used up, the item becomes useless.  The spell normally will take effect as if a magician with a skill level of 2 had cast the spell.',
    Treasure.WAND_HIDE_FEATURE: 'The Dome of Opacity enables you to cast the Hide Feature spell of the college of Illusory Magic.  There is a certain number of charges in this item, and each time you cast the spell you use up a charge.  When all charges are used up, the item becomes useless.  The spell normally will take effect as if a magician with a skill level of 2 had cast the spell.',
    Treasure.WAND_INVISIBILITY: 'The Ring of Invisibility enables you to cast the Invisibility spell of the college of Illusory Magic.  There is a certain number of charges in this item, and each time you cast the spell you use up a charge.  When all charges are used up, the item becomes useless.  The spell normally will take effect as if a magician with a skill level of 2 had cast the spell.',
    Treasure.WEAPON_1: 'The Holy Sword has a +20% chance to hit and does +3 damage against normal opponents, and +40%/+5 against undead creatures.  In addition, the sword confers the protection of the gods upon its wielder.  This protection operates automatically in all encounters.  The effect is the same as a Holy Symbol spell cast at skill level 4, except it causes no damage.',
    Treasure.WEAPON_2: 'The Shadow Sword has a +15% chance to hit and does +1 damage.  In addition, it drains life from any victim it strikes and channels it into the life-energy of its wielder.  Half the hit points subtracted from the victim when the sword hits are used to restore lost hit points to the wielder.',
    Treasure.WEAPON_3: 'The Flaming Scimitar has a +20% chance to hit and does +3 damage.  Each time it hits an opponent, there is a 5% chance that the tip of the sword will release a fireball which implodes in the innards of that opponent, resulting in instant death.',
    Treasure.WEAPON_4: 'The Psychic Flail has a +20% chance to hit and does +3 damage.  Each time it hits, it has a 50% chance of stunning the opponent for one round.  If the opponent is already under the effects of the Psychic Blast spell, he is stunned for an additional round.',
    Treasure.WEAPON_5: 'The Invisible Sword has a +10% chance to hit and does +2 damage.  It also confers invisibility on the wielder as if the Invisibility spell were cast on him at skill level 2.  This protection operates automatically in all encounters.',
    Treasure.LEADERSHIP_HUMAN: 'Excalibur has a +25% chance to hit and does +4 damage.  In addition, it confers extraordinary powers of leadership over members of the human race:  any human army following a leader who wields Excalibur has its quality increased by 1 level.  Green armies become Average, Crack armies become Elite and so on.',
    Treasure.LEADERSHIP_ELVEN: 'The Bow of the Elven Kings has a +25% chance to hit and does +2 damage.  In addition, it confers extraordinary powers of leadership over members of the elven race:  any elven army following a leader who wields this Bow has its quality increased by 1 level.  Green armies become Average, Crack armies become Elite and so on.',
    Treasure.LEADERSHIP_DWARVEN: 'The Axe of the Dwarven Lords has a +20% chance to hit and does +3 damage.  In addition, it confers extraordinary powers of leadership over members of the dwarven race:  any dwarven army following a leader who wields this Axe has its quality increased by 1 level.  Green armies become Average, Crack armies become Elite and so on.',
    Treasure.LEADERSHIP_ORCISH: 'The Scimitar of Orc Mastery has a +20% chance to hit and does +2 damage.  In addition, it confers extraordinary powers of leadership over members of the orcish race:  any orcish army following a leader who wields this Scimitar has its quality increased by 1 level.  Green armies become Average, Crack armies become Elite and so on.',
    Treasure.AMULET_ANTI_WHITE: 'The Shrunken-Head Amulet protects its owner from the effects of White Magic spells.  It totally negates the Holy Symbol spell, and spells cast on provinces owned by the wearer will have half their normal chance of succeeding.  This protection operates automatically in all encounters.',
    Treasure.AMULET_ANTI_NECROMANCY: 'The True Cross protects its owner from the effects of Necromancy spells.  It totally negates the Hand of Death and Kill Enemy spells, and spells cast against provinces owned by the bearer will have half their normal chance of succeeding.  This protection operates automatically in all encounters.',
    Treasure.AMULET_ANTI_ELEMENTAL: 'The Golden Orb of Elemental Stability protects its owner from the effects of Elemental Magic spells.  It totally negates the Fireball spell, and spells cast against provinces owned by the bearer will have half their normal chance of succeeding.  This protection operates automatically in all encounters.',
    Treasure.AMULET_ANTI_PSYCHIC: 'The Helm of Psychic Dampening protects its owner from the effects of Psychic Magic spells.  It totally negates the Charm spell and the Psychic Blast spell, and spells cast against provinces owned by the wearer of the Helm will have half their normal chance of succeeding.  This protection operates automatically in all encounters.',
    Treasure.AMULET_ANTI_ILLUSION: 'The Crystal of True Seeing protects its owner from the effects of Illusory Magic spells.  The possessor of the Crystal is unaffected by the spells of Invisibility, Illusory Terrain and Hide Feature.  The Illusory Armies spell has only half its normal effect when the bearer of the Crystal is present at a battle on the opposite side.  This protection operates automatically in all encounters.',
    Treasure.MONSTER_AID_DRAGON: 'The Crown of Dragon Command gives the bearer the power of command over dragons:  when encountering a dragon in its lair, the treasure is taken without a fight merely by using the TA-lk tactic.  When the bearer leads an army into battle, any unled dragons in adjacent provinces will fight on his side, and then fly home.  If he invades a dragon province, an average of 33% of the dragons will defect to his side.  This defection rate is halved against player-led dragons.',
    Treasure.MONSTER_AID_EAGLE: 'The Feather of the Great Eagle gives the bearer the power of command over eagles:  when encountering a eagle in its lair, the treasure is taken without a fight merely by using the TA-lk tactic.  When the bearer leads an army into battle, any unled eagles in adjacent provinces will fight on his side, and then fly home.  If he invades a eagle province, an average of 33% of the eagles will defect to his side.  This defection rate is halved against player-led eagles.',
    Treasure.MONSTER_AID_WHALE: 'The Horn of Neptune gives the bearer the power of command over whales:  when encountering a whale in its lair, the treasure is taken without a fight merely by using the TA-lk tactic.  When the bearer leads an army into battle, any unled whales in adjacent provinces will fight on his side, and then go home.  If he invades a whale province, an average of 33% of the whales will defect to his side.  This defection rate is halved against player-led whales.',
    Treasure.BOOK_TACTICAL: 'Hannibal\'s Grimoire raises your Tactical ability by one level.  For example, a skill level of 0 would rise to skill level 1.  The reader of this strangely compelling work becomes completely engrossed with it,and after this book is perused, it crumbles to dust and merges with the sands of time.  Use the "Use Item" Action to invoke its powers.',
    Treasure.BOOK_MARCH: 'The Manual of Speedy Marches raises your Forced March ability by one level.  For example, a skill level of 0 would rise to skill level 1.  The reader of this strangely compelling work becomes completely engrossed with it, and after this book is perused, it crumbles to dust and merges with the sands of time.  Use the "Use Item" Action to invoke its powers.',
    Treasure.BOOK_NAVAL: 'The Ship\'s Log of Nautilus III raises your Naval ability by one level.  For example, a skill level of 0 would rise to skill level 1.  The reader of this strangely compelling work becomes completely engrossed with it, and after this book is perused, it crumbles to dust and merges with the sands of time.  Use the "Use Item" Action to invoke its powers.',
    Treasure.BOOK_ARCHERY: 'The Manual of Archery raises your Archery ability by one level.  For example, a skill level of 0 would rise to skill level 1.  The reader of this strangely compelling work becomes completely engrossed with it, and after this book is perused, it crumbles to dust and merges with the sands of time.  Use the "Use Item" Action to invoke its powers.',
    Treasure.BOOK_MELEE: 'The Handbook of Swordsmanship raises your Melee ability by one level.  For example, a skill level of 0 would rise to skill level 1.  The reader of this strangely compelling work becomes completely engrossed with it, and after this book is perused, it crumbles to dust and merges with the sands of time.  Use the "Use Item" Action to invoke its powers.',
    Treasure.BOOK_WHITE: 'The Scriptures of Holy Thoughts raise your White Magic ability by one level.  For example, a skill level of 0 would rise to skill level 1.  The reader of this strangely compelling work becomes completely engrossed with it, and after this book is perused, it crumbles to dust and merges with the sands of time.  Use the "Use Item" Action to invoke its powers.',
    Treasure.BOOK_NECROMANCY: 'The Necronomicon raises your Necromancy ability by one level.  For example, a skill level of 0 would rise to skill level 1.  The reader of this strangely compelling work becomes completely engrossed with it, and after this book is perused, it crumbles to dust and merges with the sands of time.  Use the "Use Item" Action to invoke its powers.',
    Treasure.BOOK_ELEMENTAL: 'The Periodic Table of Elements raises your Elemental Magic ability by one level.  For example, a skill level of 0 would rise to skill level 1.  The reader of this strangely compelling work becomes completely engrossed with it, and after this book is perused, it crumbles to dust and merges with the sands of time.  Use the "Use Item" Action to invoke its powers.',
    Treasure.BOOK_PSYCHIC: 'The Codex of Mental Prowess raises your Psychic Magic ability by one level.  For example, a skill level of 0 would rise to skill level 1.  The reader of this strangely compelling work becomes completely engrossed with it, and after this book is perused, it crumbles to dust and merges with the sands of time.  Use the "Use Item" Action to invoke its powers.',
    Treasure.BOOK_ILLUSION: 'The Libram of Illusions raises your Illusory Magic ability by one level.  For example, a skill level of 0 would rise to skill level 1.  The reader of this strangely compelling work becomes completely engrossed with it, and after this book is perused, it crumbles to dust and merges with the sands of time.  Use the "Use Item" Action to invoke its powers.',
    Treasure.BOOK_DRUID: 'The Book of Druidic Incantations raises your Druidic ability by one level.  For example, a skill level of 0 would rise to skill level 1.  The reader of this strangely compelling work becomes completely engrossed with it, and after this book is perused, it crumbles to dust and merges with the sands of time.  Use the "Use Item" Action to invoke its powers.',
    Treasure.BOOK_THIEF: 'The Black Notebook of Thievery raises your Thief ability by one level.  For example, a skill level of 0 would rise to skill level 1.  The reader of this strangely compelling work becomes completely engrossed with it, and after this book is perused, it crumbles to dust and merges with the sands of time.  Use the "Use Item" Action to invoke its powers.',
    Treasure.BOOK_EXPLORER: 'The Journal of Many Wanderings raises your Explorer ability by one level.  For example, a skill level of 0 would rise to skill level 1.  The reader of this strangely compelling work becomes completely engrossed with it, and after this book is perused, it crumbles to dust and merges with the sands of time.  Use the "Use Item" Action to invoke its powers.',
    Treasure.BOOK_SPY: 'The Manual of Spying raises your Spying ability by one level.  For example, a skill level of 0 would rise to skill level 1.  The reader of this strangely compelling work becomes completely engrossed with it, and after this book is perused, it crumbles to dust and merges with the sands of time.  Use the "Use Item" Action to invoke its powers.',
    Treasure.BOOK_SAGE: 'The Library of Science raises your Sage ability by one level.  For example, a skill level of 0 would rise to skill level 1.  The reader of this strangely compelling work becomes completely engrossed with it, and after this book is perused, it crumbles to dust and merges with the sands of time.  Use the "Use Item" Action to invoke its powers.',
    Treasure.GOLD_HOARD_LARGE: 'the Hoard is not a magic item.',
    Treasure.GOLD_HOARD_HUGE: 'the Hoard is not a magic item.',
    Treasure.GOLD_HOARD_FABULOUS: 'the Hoard is not a magic item.',
    Treasure.QUEST_SNOW_QUEST: 'The Snowball Quest is not a magic item.',
    Treasure.QUEST_SNOWBALL: 'The Snowball is not a magic item.',
    Treasure.QUEST_SNOW_FULFILL: 'The Fulfilled Snowball Quest is not a magic item.',
    Treasure.QUEST_SAPPH_RING: 'The Sapphire Ring is not a magic item.',
    Treasure.QUEST_SAPPH_FULFILL: 'The Fulfilled Sapphire Quest is not a magic item.',
    Treasure.QUEST_LUCKY_PENNY: 'The Lucky Penny is not a magic item.',
    Treasure.QUEST_LUCK_FULFILL: 'The Fulfilled Penny Quest is not a magic item.',
    Treasure.QUEST_GODS_QUEST: 'The GOds Quest is not a magic item.',
    Treasure.QUEST_GODS_FULFILL: 'THe Fulffilled Gods Quest is not a magic item.',
    Treasure.QUEST_MERMAID_AMULET: 'The Amulet is not a magic item.',
    Treasure.QUEST_MERMAID_FULFILL: 'The Fulfilled Mermaid Quest is not a magic item.',
    Treasure.QUEST_RA_RIDDLE: 'the Riddle is not a magic item.',
    Treasure.QUEST_RA_COFFIN: 'the Riddle is not a magic item.',
    Treasure.QUEST_RA_BRIDGE: 'the Riddle is not a magic item.',
    Treasure.QUEST_RA_CANDLE: 'the Riddle is not a magic item.',
    Treasure.QUEST_RA_SMOKE: 'the Riddle is not a magic item.',
    Treasure.QUEST_RA_OWNER: 'the Riddle is not a magic item.',
    Treasure.QUEST_RA_MAN: 'the Riddle is not a magic item.',
    Treasure.QUEST_KILL_QUEST: 'The Kill Quest is not a magic item.',
    Treasure.QUEST_KILL_FULFILL: 'The fulfilled Kill Quest is not a magic item.',
    Treasure.QUEST_CONTRACT: 'The Contract is not a magic item.',
    Treasure.QUEST_CONTRACT_FULFILL: 'The Signed Contract is not a magic item.',
    Treasure.NO_TREASURE: 'No treasure.',
    Treasure.NAMED_UNIQUE_CROWN_ROHAN: "The Crown of Rohan will increase March and Tactical abilities by one level for its holder.  If it is combined with the Amulet of Power in the personal possession of a King, one level is added to the Tactical ability of all the King's characters.  When combined with Scepter of Life in the personal possession of a King, it adds one additional point of Illusionist ability to all of the King's characters.",
    Treasure.NAMED_UNIQUE_AMULET_POWER: "The Amulet of Power will increase the skill levels of the character who owns it by one point in White, Elemental and Psychic magic.  When combined with the Scepter of Life in the personal possession of a King, one level of Melee ability and 2 hit points are added to all the King's characters.  If it is combined with the Crown of Rohan personally possessed by a King, one level is added to the Tactical ability of all the King's characters.",
    Treasure.NAMED_UNIQUE_SCEPTER_LIFE: "The Scepter of Life adds one skill level to the holder's Sage ability and 5 hit points in combat.  When combined with Crown of Rohan personally possessed by a King, it adds one additional point of Illusionist ability to all of the King's characters.  When combined with the Amulet of Power personally possessed by a King, one level of Melee ability and 2 hit points are added to all the King's characters.",
    Treasure.NAMED_UNIQUE_MAP_MARAUDERS: 'The Map of the Marauders adds one Naval skill level to its possessor.  It also increases by one hex the distance in sea hexes a character can see when he moves.',
    Treasure.NAMED_UNIQUE_FANG_VAMPIRE: 'The Fang of the Vampire Lord adds one level of Melee skill to its wielder.  For Undead characters, it also increases Necromantic ability by one level.',
    Treasure.NAMED_UNIQUE_HAMMER_POWER: 'The Hammer of Power adds one level of Melee skill to its wielder.  For a dwarf, it also increases Druidic skill by one point.',
}
