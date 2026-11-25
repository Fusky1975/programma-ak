"""Advanced Abilities -- special talents gained above skill level 4 (Phase 128).

**Source and provenance.** This module's vocabulary and descriptions
are transcribed verbatim from a rulebook excerpt the user supplied
directly (a text file titled "ABILITA SOPRA IL LIVELLO 4 OK.txt",
2026-07-13) -- this content was **not** found anywhere in
``Programma Pascal.zip`` (checked: ``HostAK/MS/ADDEND.AK``,
``RULES.AK``, ``AKMAN.TXT``, ``INFO.AK``, ``TIPS.AK`` -- none contain
any of these ability names). It is therefore documented here as an
explicit, honestly-labeled external rulebook source, not a Pascal
-archive citation, per this project's standing rule to never blur the
two. Two independent empirical cross-checks against already-modeled,
Pascal-sourced data confirm the excerpt is authoritative rather than
an invented or mis-transcribed document (see below).

**Closes the ``spdex`` gap flagged since Phase 23.** ``models/enums.py
Spell``'s own docstring has said, since Phase 23, that ordinals 25-34
(the 10 "secret" spells) are "each gated behind a specific special
ability granted at skill 5+ (``CTBOTH.PAS``'s ``spdex`` lookup
table)" -- a real, confirmed mechanic with no further detail available
from the Pascal archive itself. This module's White/Necromancy/
Elemental/Psychic/Illusion magic pools each contain exactly two
"New spell" Advanced Abilities, and **all 10, by name, match 1:1**
against ``SPELL_NAME`` (Phase 84) for exactly ``Spell`` ordinals
25-34: "GATE ANGEL" SPELL -> ``Spell.GATE_ANGEL`` ("Gate Angel"),
"WORDS OF HEALING" SPELL -> ``Spell.HEAL`` ("Words of Healing"),
"SCAR TERRAIN" SPELL -> ``Spell.SCAR_TERRAIN``, "GATE DEMON" SPELL ->
``Spell.GATE_DEMON``, "LAVA POOL" SPELL -> ``Spell.LAVA_POOL``,
"MYSTIC WINDS" SPELL -> ``Spell.MYSTIC_WINDS``, "AUGUR COMBAT" SPELL
-> ``Spell.AUGUR_COMBAT``, "LOCATE OBJECT" SPELL -> ``Spell
.LOCATE_OBJECT``, "ILLUSORY FOG" SPELL -> ``Spell.ILLUS_FOG``,
"ILLUSORY HERO" SPELL -> ``Spell.ILLUS_HERO``. See
``ADVANCED_ABILITY_GRANTS_SPELL`` below -- this is not a coincidence,
it is direct confirmation that the excerpt describes the same real
game system ``spdex`` implements.

**A second independent cross-check**: the "GATE DEMON" SPELL's d100
demon table and the "LAVA POOL" SPELL's monster-immunity list both
name real creatures, and every single one of the 7 (demon table) + 29
(immunity list) names matches an existing ``models/monster.py
Monster`` member exactly (``MONSTER_NAMES``, Phase 75) -- see
``GATE_DEMON_TABLE``/``LAVA_POOL_IMMUNE_MONSTERS`` below.

**Mechanic, as described by the excerpt itself**: for each of the 15
``Ability`` categories, reaching skill level 5 (and again at each
level up to the ``MAX_SKILL_LEVEL = 9`` cap,
``turn/practice_execution.py``) discontinues that ability's usual
automatic per-level bonus (e.g. Tactical's 20%-per-level army-strength
increase) and instead awards **one** Advanced Ability, drawn from that
category's own pool, "that can be gained only once". Pool sizes are
**not** uniformly 5 (one per level 5-9): Thievery's pool has 8
candidates, most others have 5 or 6 -- meaning a character will never
gain every possible Advanced Ability in a category whose pool exceeds
5.

**2026-11-26 -- occurrences are counted.** Several templates hold the same ability in more than one slot
(Tactical/Naval Mastery 15% x3, Melee Mastery x3, Archery Free Attack, Super Sage), and the original engine's
``SA_Num`` counts them all, summing the effect per occurrence. ``AdvancedAbilities`` (below) is the set a leader
holds, remembering the slot each came from so ``advanced_ability_count()`` can answer that; the effects that
depend on it (Tactical/Naval Mastery, Melee Mastery, Archery Free Attack, Super Sage) add up per slot. The
"only one per category" sentence in older notes predates this.

**Phase 131 correction -- the selection is deterministic, not
random.** This module originally said the exact selection mechanic was
unsourced ("uniform random over the remaining pool? weighted?").
Sweeping the remaining ``.PAS`` files (past ``SAY.PAS``/``RUMORS.PAS``,
both now fully scanned) found the real mechanism: ``SAY.PAS``'s own
``Imp_Spab`` (~line 1338-1351) and ``SPEAK.PAS``'s ``PW_Spab`` (~line
33-40) both index a table, ``spabord[ability, level-4]``, to determine
*which* pool entry is awarded -- a fixed lookup, not a dice roll.
``REPORTS.PAS`` (~line 643) confirms the announcement is dispatched
deterministically too: ``FD('c:\\tp\\prose\\saname.x2', S_Red,
1001+spabord[ab,skil-4])``, the same `dex >= 1000` per-ordinal
dispatch pattern already established for ``SPNOTE.X2``/``MAGFEAT.X2``
(Phase 122/96). **The table's actual values are still unrecoverable**:
`spabord` is never declared in any ``.PAS`` file in the archive --
`SPEAK.PAS`'s own ``uses dos,crt,textseek,defines,yak,mboth,rumors,map``
names two units, ``defines`` and ``mboth``, that don't exist anywhere
in ``Programma Pascal.zip`` (only their compiled ``.TPU`` forms would
have contained the array). So: the mechanic is now correctly described
as deterministic-but-data-unavailable, not "possibly random" -- a real
correction, not just an elaboration.

**Phase 384 update -- `spabord` itself is now recovered, from a
different source.** The claim above ("unrecoverable") was true of the
``.PAS`` archive alone; it was never a claim about the AKGEN reverse-
engineering material (a separate, disassembly-derived source, not part
of ``Programma Pascal.zip``), which turned out to give the real
selection *algorithm* for ``spabord`` (not just its existence) and a
full worked example for one real game. See
``worldgen/special_ability_level_schedule.py`` -- verified to
reproduce that worked example exactly for the 5 magic colleges
(``Ability.WHITE``/``NECROMANCY``/``ELEMENTAL``/``PSYCHIC``/
``ILLUSION``). The other 10 categories' own real pool-selection order
(including ``ADVANCED_ABILITY_POOL``'s own tuple order in *this*
module, which is sourced from a different, user-supplied rulebook
excerpt and was never confirmed to match `spabord`'s real per-category
template order) remain unrecovered.

**Two further real, fully-recoverable mechanics found in the same
sweep** (``SPEAK.PAS Check_MSpab``/``Check_DSpab``, ~lines 66-90):

- Six named-unique ``Treasure`` items each trigger an eligibility
  *check* (not a free grant -- ``Check_ESpab`` only re-confirms/
  re-announces a level the leader already has) across multiple
  specific abilities while held. The other 15 ``ABILITY_ITEM``
  treasures (``Treasure.ABILITY_TACTICAL``..``ABILITY_SAGE``) check
  their own single already-implied ability via `Check_ESpab(ldr,
  ability(ord(tr)))` -- independent confirmation of `models/treasure
  .py`'s own already-established 1:1 ``ABILITY_ITEM``/``Ability``
  positional mapping (Phase 77), not new data. See
  ``UNIQUE_ITEM_ADVANCED_ABILITY_CHECKS`` below.
- The 20 ``fix``/``wreck`` ``Discovery`` members (ordinals 0-19) each
  trigger the same kind of check for one specific ``Ability``, two
  discoveries per ability: ``fix0``/``fix1`` (`LAND_SHIP`/
  `SCYTHED_CHARIOTS`) through ``fix8``/``fix9`` (`STRENGTH_ELIXIR`/
  `MITHRIL_CHAINMAIL`) cover Tactical/March/Naval/Archery/Melee;
  ``wreck0``/``wreck1`` (`MEDITATION_INCENSE`/`CLASSIFICATION_OF_LIFE`)
  through ``wreck8``/``wreck9`` (`HIEROGLYPHIC_TRANSLATION`/
  `SCIENTIFIC_METHOD`) cover Druid/Thief/Explorer/Spy/Sage (computed
  directly from the Pascal source's own `ability(ord(d) Shr 1)` /
  `ability(5+(ord(d) Shr 1))` arithmetic, not guessed). See
  ``DISCOVERY_ADVANCED_ABILITY_CHECKS`` below.

Ties directly to already-modeled mechanics without re-deriving them:
``models/enums.py Ability`` (the 15 skill categories, CTBOTH.PAS lines
130-132), ``turn/practice_execution.py MAX_SKILL_LEVEL`` (the level 9
cap), ``models/enums.py Spell``/``SPELL_NAME`` (the 10 secret spells,
Phase 84), ``models/monster.py Monster``/``MONSTER_NAMES`` (Phase 75),
``models/treasure.py Treasure`` (Phase 77), and ``models/discovery.py
Discovery`` (Phase 91/93).
"""

from __future__ import annotations

from enum import IntEnum

from ak_engine.models.discovery import Discovery
from ak_engine.models.enums import Ability, Spell
from ak_engine.models.monster import Monster
from ak_engine.models.treasure import Treasure


class AdvancedAbility(IntEnum):
    """89 Advanced Abilities from the source excerpt, grouped by the 15
    ``Ability`` categories in the exact order it presents them, plus one
    project-original member (``MARCH_CAVALRY_TRUE_MASTERY``, Phase 768 --
    appended out of category order, see its own comment above). Ordinals
    are this project's own assignment (the excerpt has no numbering) --
    stable within this module, not meaningful outside it.
    """

    # Tactical (TA)
    TACTICAL_WARGAMES_MASTERY = 0
    TACTICAL_MASTERY_10 = 1
    TACTICAL_MASTERY_15 = 2
    TACTICAL_MASTERY_20 = 3
    TACTICAL_COMBINED_ARMS = 4
    ADAPT_TACTICS_TO_TERRAIN = 5

    # March (MA)
    MARCH_THROUGH_FLOODS = 6
    MARCH_CAVALRY = 7
    MARCH_INFANTRY = 8
    MARCH_CAVALRY_MASTERY = 9
    MARCH_INFANTRY_MASTERY = 10

    # Naval (NA)
    NAVAL_LONG_DEFEND = 11
    NAVAL_MASTERY_10 = 12
    NAVAL_MASTERY_GREAT_15 = 13
    NAVAL_MASTERY_EXALTED_20 = 14
    NAVAL_HUG_COASTLINE = 15
    NAVAL_COMBINED_ARMS = 16

    # Archery (AR)
    ARCHERY_FREE_ATTACK = 17
    SHORT_RANGE_ARCHERY = 18
    ARCHERY_FREE_ATTACK_MASTERY = 19
    LONG_RANGE_ARCHERY = 20
    ARCHERY_FREE_ATTACK_TRUE_MASTERY = 21

    # Melee (ME)
    MELEE_DUELLISTS_MEDAL = 22
    MELEE_MASTERY = 23
    MELEE_CONTROL_TEMPER = 24
    MELEE_HIT_POINTS = 25
    MELEE_EVASION = 26
    MELEE_TRUE_MASTERY = 27

    # Druidism (DR)
    DRUIDIC_ANIMAL_SPIES = 28
    DRUIDIC_WHALE_TRANSPORT = 29
    DRUIDIC_TRANSPORT = 30
    DRUIDIC_HORSE_CONTROL = 31
    DRUIDIC_DINOSAURS = 32
    DRUIDIC_TRADES = 33

    # Thievery (ST)
    THIEF_MASTERY_I = 34
    THIEF_BANDITRY = 35
    THIEF_MASTERY_II = 36
    THIEF_PIRACY = 37
    THIEF_MASTERY_III = 38
    THIEF_TREASURY_RAIDS = 39
    THIEF_MASTERY_IV = 40
    THIEF_MASTERY_V = 41

    # Explorer (EX)
    EXPLORER_MILITARY_MAPS = 42
    EXPLORER_FIND_WATER = 43
    EXPLORERS_SOCIETY_MAPS = 44
    EXPLORERS_LONG_RANGE_TRADE_ROUTES = 45
    EXPLORING_DIFFICULT_TERRAIN = 46
    EXPLORER_FIND_MINES = 47

    # Spy (SP)
    SPY_BLACKMAIL = 48
    SPY_DOUBLE_AGENT = 49
    SPY_SUPER_SLEUTH = 50
    SPY_EXPANDED_SPYING = 51
    SPY_BRAINWASH = 52
    SPY_ASSASSINATE = 53

    # Sagesness (SA)
    SUPER_SAGE_I = 54
    SUPER_SAGE_II = 55
    SUPER_SAGE_III = 56
    SUPER_SAGE_IV = 57
    SUPER_SAGE_V = 58

    # White Magic (WH)
    ENHANCED_HOLY_SYMBOL = 59
    WORDS_OF_HEALING_SPELL = 60
    HOLY_PLACES = 61
    KNOW_ALIGNMENT_TALENT = 62
    ENHANCED_RESURRECTION = 63
    GATE_ANGEL_SPELL = 64

    # Necromancy (NE)
    DARK_PLACES = 65
    ENHANCED_SKELETAL_UNITS = 66
    WITCHSIGHT_TALENT = 67
    ENHANCED_COMBAT_NE_SPELLS = 68
    SCAR_TERRAIN_SPELL = 69
    GATE_DEMON_SPELL = 70

    # Elemental Magic (EL)
    ENHANCED_EARTHQUAKE = 71
    ELEMENTAL_PLACES = 72
    ENHANCED_COMBAT_EL_SPELLS = 73
    MAKE_GEMS_TALENT = 74
    LAVA_POOL_SPELL = 75
    MYSTIC_WINDS_SPELL = 76

    # Psychic Magic (PS)
    AUGUR_COMBAT_SPELL = 77
    PSYCHIC_PLACES = 78
    ENHANCED_CLAIRVOYANCE = 79
    SENSE_DANGER_TALENT = 80
    LOCATE_OBJECT_SPELL = 81
    ENHANCED_CHARM = 82

    # Illusion Magic (IL)
    ILLUSORY_PLACES = 83
    DETECT_ILLUSIONS_TALENT = 84
    ENHANCED_ILLUSORY_TERRAIN = 85
    ENHANCED_INVISIBILITY = 86
    ILLUSORY_FOG_SPELL = 87
    ILLUSORY_HERO_SPELL = 88

    # March (MA) -- Cavalry's own 3rd stacking tier (Phase 768). Appended
    # here with a fresh ordinal rather than renumbering the March (MA)
    # block above -- ordinals are this project's own assignment, never
    # serialized/compared anywhere (see this class's own docstring), so
    # an out-of-sequence ordinal costs nothing. `Desktop/PROGRAMMA
    # AK/MARCH.md` (a disassembly-level pass) confirms AKGEN's own real
    # `spabord` template for March grants the Cavalry-effect ID three
    # times (not twice, unlike Infantry) -- no literal 3rd-tier catalog
    # text survives in `Desktop/PROGRAMMA AK/ABILITÀ SOPRA IL LIVELLO 4
    # OK.txt` (the source for every other member's own text), but that
    # same file's own Archery entry shows the identical "one real ID
    # granted 3 times, 3 progressively-named entries" shape ("ARCHERY
    # FREE ATTACK" / "... MASTERY" / "... TRUE MASTERY") -- a real,
    # same-document precedent. User-confirmed directly to add this tier
    # with clearly-labeled project-original text (see its own dict
    # entries below), mirroring Melee Mastery/True Mastery's own
    # established "self-contained total per tier" convention.
    MARCH_CAVALRY_TRUE_MASTERY = 89


# The random-draw pool per Ability category, in source order.
ADVANCED_ABILITY_POOL: dict[Ability, tuple[AdvancedAbility, ...]] = {
    Ability.TACTICAL: (
        AdvancedAbility.TACTICAL_WARGAMES_MASTERY,
        AdvancedAbility.TACTICAL_MASTERY_10,
        AdvancedAbility.TACTICAL_MASTERY_15,
        AdvancedAbility.TACTICAL_MASTERY_20,
        AdvancedAbility.TACTICAL_COMBINED_ARMS,
        AdvancedAbility.ADAPT_TACTICS_TO_TERRAIN,
    ),
    Ability.MARCH: (
        AdvancedAbility.MARCH_THROUGH_FLOODS,
        AdvancedAbility.MARCH_CAVALRY,
        AdvancedAbility.MARCH_INFANTRY,
        AdvancedAbility.MARCH_CAVALRY_MASTERY,
        AdvancedAbility.MARCH_INFANTRY_MASTERY,
        # Phase 768: the real 6th slot MARCH.md's own byte-level template
        # confirms (Cavalry's own 3rd occurrence) -- see this member's
        # own comment on the enum above for the full sourcing.
        AdvancedAbility.MARCH_CAVALRY_TRUE_MASTERY,
    ),
    Ability.NAVAL: (
        AdvancedAbility.NAVAL_LONG_DEFEND,
        AdvancedAbility.NAVAL_MASTERY_10,
        AdvancedAbility.NAVAL_MASTERY_GREAT_15,
        AdvancedAbility.NAVAL_MASTERY_EXALTED_20,
        AdvancedAbility.NAVAL_HUG_COASTLINE,
        AdvancedAbility.NAVAL_COMBINED_ARMS,
    ),
    Ability.ARCHERY: (
        AdvancedAbility.ARCHERY_FREE_ATTACK,
        AdvancedAbility.SHORT_RANGE_ARCHERY,
        AdvancedAbility.ARCHERY_FREE_ATTACK_MASTERY,
        AdvancedAbility.LONG_RANGE_ARCHERY,
        AdvancedAbility.ARCHERY_FREE_ATTACK_TRUE_MASTERY,
    ),
    Ability.MELEE: (
        AdvancedAbility.MELEE_DUELLISTS_MEDAL,
        AdvancedAbility.MELEE_MASTERY,
        AdvancedAbility.MELEE_CONTROL_TEMPER,
        AdvancedAbility.MELEE_HIT_POINTS,
        AdvancedAbility.MELEE_EVASION,
        AdvancedAbility.MELEE_TRUE_MASTERY,
    ),
    Ability.DRUID: (
        AdvancedAbility.DRUIDIC_ANIMAL_SPIES,
        AdvancedAbility.DRUIDIC_WHALE_TRANSPORT,
        AdvancedAbility.DRUIDIC_TRANSPORT,
        AdvancedAbility.DRUIDIC_HORSE_CONTROL,
        AdvancedAbility.DRUIDIC_DINOSAURS,
        AdvancedAbility.DRUIDIC_TRADES,
    ),
    Ability.THIEF: (
        AdvancedAbility.THIEF_MASTERY_I,
        AdvancedAbility.THIEF_BANDITRY,
        AdvancedAbility.THIEF_MASTERY_II,
        AdvancedAbility.THIEF_PIRACY,
        AdvancedAbility.THIEF_MASTERY_III,
        AdvancedAbility.THIEF_TREASURY_RAIDS,
        AdvancedAbility.THIEF_MASTERY_IV,
        AdvancedAbility.THIEF_MASTERY_V,
    ),
    Ability.EXPLORER: (
        AdvancedAbility.EXPLORER_MILITARY_MAPS,
        AdvancedAbility.EXPLORER_FIND_WATER,
        AdvancedAbility.EXPLORERS_SOCIETY_MAPS,
        AdvancedAbility.EXPLORERS_LONG_RANGE_TRADE_ROUTES,
        AdvancedAbility.EXPLORING_DIFFICULT_TERRAIN,
        AdvancedAbility.EXPLORER_FIND_MINES,
    ),
    Ability.SPY: (
        AdvancedAbility.SPY_BLACKMAIL,
        AdvancedAbility.SPY_DOUBLE_AGENT,
        AdvancedAbility.SPY_SUPER_SLEUTH,
        AdvancedAbility.SPY_EXPANDED_SPYING,
        AdvancedAbility.SPY_BRAINWASH,
        AdvancedAbility.SPY_ASSASSINATE,
    ),
    Ability.SAGE: (
        AdvancedAbility.SUPER_SAGE_I,
        AdvancedAbility.SUPER_SAGE_II,
        AdvancedAbility.SUPER_SAGE_III,
        AdvancedAbility.SUPER_SAGE_IV,
        AdvancedAbility.SUPER_SAGE_V,
    ),
    Ability.WHITE: (
        AdvancedAbility.ENHANCED_HOLY_SYMBOL,
        AdvancedAbility.WORDS_OF_HEALING_SPELL,
        AdvancedAbility.HOLY_PLACES,
        AdvancedAbility.KNOW_ALIGNMENT_TALENT,
        AdvancedAbility.ENHANCED_RESURRECTION,
        AdvancedAbility.GATE_ANGEL_SPELL,
    ),
    Ability.NECROMANCY: (
        AdvancedAbility.DARK_PLACES,
        AdvancedAbility.ENHANCED_SKELETAL_UNITS,
        AdvancedAbility.WITCHSIGHT_TALENT,
        AdvancedAbility.ENHANCED_COMBAT_NE_SPELLS,
        AdvancedAbility.SCAR_TERRAIN_SPELL,
        AdvancedAbility.GATE_DEMON_SPELL,
    ),
    Ability.ELEMENTAL: (
        AdvancedAbility.ENHANCED_EARTHQUAKE,
        AdvancedAbility.ELEMENTAL_PLACES,
        AdvancedAbility.ENHANCED_COMBAT_EL_SPELLS,
        AdvancedAbility.MAKE_GEMS_TALENT,
        AdvancedAbility.LAVA_POOL_SPELL,
        AdvancedAbility.MYSTIC_WINDS_SPELL,
    ),
    Ability.PSYCHIC: (
        AdvancedAbility.AUGUR_COMBAT_SPELL,
        AdvancedAbility.PSYCHIC_PLACES,
        AdvancedAbility.ENHANCED_CLAIRVOYANCE,
        AdvancedAbility.SENSE_DANGER_TALENT,
        AdvancedAbility.LOCATE_OBJECT_SPELL,
        AdvancedAbility.ENHANCED_CHARM,
    ),
    Ability.ILLUSION: (
        AdvancedAbility.ILLUSORY_PLACES,
        AdvancedAbility.DETECT_ILLUSIONS_TALENT,
        AdvancedAbility.ENHANCED_ILLUSORY_TERRAIN,
        AdvancedAbility.ENHANCED_INVISIBILITY,
        AdvancedAbility.ILLUSORY_FOG_SPELL,
        AdvancedAbility.ILLUSORY_HERO_SPELL,
    ),
}


# The intro paragraph for each Ability category -- explains what
# automatic per-level bonus is discontinued once this system takes
# over at skill level 5.
ADVANCED_ABILITY_INTRO: dict[Ability, str] = {
    Ability.TACTICAL: (
        "At level 5 and up the automatic 20% per level increase in "
        "army strength is discontinued. Instead, you gain one of "
        "these abilities at random (that can be gained only once)."
    ),
    # Phase 768: this intro text is quoted verbatim and left unchanged --
    # `MARCH_CAVALRY_TRUE_MASTERY`'s own real 6th-slot status is a
    # disassembly finding (`Desktop/PROGRAMMA AK/MARCH.md`), not
    # something this catalog's own surviving text describes.
    Ability.MARCH: (
        'At level 5 and up the "Ability Level 4" on the March Table '
        "is used, and the usual increases in army speed on land are "
        "not necessarily continued. Instead, you gain one of these "
        "abilities at random (that can be gained only once)."
    ),
    Ability.NAVAL: (
        "At levels 5 and up, you keep the plus 1 Naval move per "
        "level, but the usual 20% per level increase in sea strength "
        "is gone. Instead, you gain one of these abilities at random "
        "(that can be gained only once)."
    ),
    Ability.ARCHERY: (
        "At levels 5 and up the usual 10% per level increase in the "
        "chance to hit with a Fire attack is reduced to 5% per level, "
        "and the automatic increase in the number of free attacks "
        "stops at 4 (however, skill level will still determine who "
        "attacks first in combat). Instead you gain one of these "
        "abilities at random (that can be gained only once)."
    ),
    Ability.MELEE: (
        "At levels 5 and up the usual 10% per level increase in the "
        "chance to hit in melee is discontinued, as well as the "
        "damage plus (however, skill level will still determine who "
        "Attacks first in combat). Instead, you gain one of these "
        "abilities at random (that can be gained only once)."
    ),
    Ability.DRUID: (
        "At levels 5 and up you gain no more abilities for druidism. "
        "Instead, you gain one of these abilities at random (that can "
        "be gained only once)."
    ),
    Ability.THIEF: (
        "At levels 5 and up the usual 15% per level increase in "
        "stealing ability is discontinued. Instead, you gain one of "
        "these abilities at random (that can be gained only once)."
    ),
    Ability.EXPLORER: (
        "At levels 5 and up the usual exploration increase by the "
        "Basic Exploration Number per level is discontinued. Instead, "
        "you gain one of these abilities at random (that can be "
        "gained only once)."
    ),
    Ability.SPY: (
        "At levels 5 and up there are no further increases in the "
        "Spy Table. Instead, you gain one of these abilities at "
        "random (that can be gained only once)."
    ),
    Ability.SAGE: (
        "At levels 5 and up there is not necessarily an increase in "
        "the chance to invent something. Instead, the Sage attracts a "
        "company of philosophers and builds a University in his "
        "province of birth."
    ),
    Ability.WHITE: (
        "At levels 5 and up the usual 15% per level increase in the "
        'cast chance is discontinued, and the number of spells you '
        'can cast in White Magic is capped at 3 Action, 2 Combat. The '
        'effects of the "Holy Symbol" and "Spiritwrack" spells are '
        "also capped at level 4 (however, skill level will still "
        "determine who attacks first in personal combat). Instead, "
        "you gain one of these abilities at random (that can be "
        "gained only once)."
    ),
    Ability.NECROMANCY: (
        "At levels 5 and up the usual 15% per level increase in the "
        "cast chance is discontinued, and the number of spells you "
        'can cast in Necromancy is capped at 3 Action, 2 Combat. The '
        'effects of the "Skeletal Armies", "Plague" and "Hand of '
        'Death" spells are also capped at level 4 (however, skill '
        "level will still determine who attacks first in personal "
        "combat). Instead, you gain one of these abilities at random "
        "(that can be gained only once)."
    ),
    Ability.ELEMENTAL: (
        "At levels 5 and up the usual 15% per level increase in the "
        "cast chance is discontinued and the number of spells you can "
        'cast in Elemental magic is capped at 3 Action, 2 Combat. The '
        'effects of the "Tornadoes", "Fireball" and "Ice Suspension" '
        "spells are also capped at level 4 (however, skill level will "
        "still determine who attacks first in personal combat). "
        "Instead, you gain one of these abilities at random (that can "
        "be gained only once)."
    ),
    Ability.PSYCHIC: (
        "At levels 5 and up the usual 15% per level increase in the "
        "cast chance is discontinued, and the number of spells you "
        "can cast in Psychic Magic is capped at 3 Action, 2 Combat "
        "(however, skill level will still determine who attacks first "
        "in personal combat). Instead, you gain one of these "
        "abilities at random (that can be gained only once)."
    ),
    Ability.ILLUSION: (
        "At levels 5 and up the usual 15% per level increase in the "
        "cast chance is discontinued, and the number of spells you "
        'can cast in Illusion is capped at 3 Action, 2 Combat. The '
        'effects of the "Mirror Image" and "Phantasmal Armies" spells '
        "are also capped at level 4 (however, skill level will still "
        "determine who attacks first in personal combat). Instead, "
        "you gain one of these abilities at random (that can be "
        "gained only once)."
    ),
}


ADVANCED_ABILITY_NAME: dict[AdvancedAbility, str] = {
    AdvancedAbility.TACTICAL_WARGAMES_MASTERY: "Tactical Wargames Mastery",
    AdvancedAbility.TACTICAL_MASTERY_10: "Tactical Mastery",
    AdvancedAbility.TACTICAL_MASTERY_15: "Tactical Mastery",
    AdvancedAbility.TACTICAL_MASTERY_20: "Tactical Mastery",
    AdvancedAbility.TACTICAL_COMBINED_ARMS: "Tactical Combined Arms",
    AdvancedAbility.ADAPT_TACTICS_TO_TERRAIN: "Adapt Tactics to Terrain",
    AdvancedAbility.MARCH_THROUGH_FLOODS: "March Through Floods",
    AdvancedAbility.MARCH_CAVALRY: "March Cavalry",
    AdvancedAbility.MARCH_INFANTRY: "March Infantry",
    AdvancedAbility.MARCH_CAVALRY_MASTERY: "March Cavalry Mastery",
    AdvancedAbility.MARCH_INFANTRY_MASTERY: "March Infantry Mastery",
    AdvancedAbility.MARCH_CAVALRY_TRUE_MASTERY: "March Cavalry True Mastery",
    AdvancedAbility.NAVAL_LONG_DEFEND: "Naval Long Defend",
    AdvancedAbility.NAVAL_MASTERY_10: "Naval Mastery",
    AdvancedAbility.NAVAL_MASTERY_GREAT_15: "Naval Mastery Great",
    AdvancedAbility.NAVAL_MASTERY_EXALTED_20: "Naval Mastery Exalted",
    AdvancedAbility.NAVAL_HUG_COASTLINE: "Naval Hug Coastline",
    AdvancedAbility.NAVAL_COMBINED_ARMS: "Naval Combined Arms",
    AdvancedAbility.ARCHERY_FREE_ATTACK: "Archery Free Attack",
    AdvancedAbility.SHORT_RANGE_ARCHERY: "Short-Range Archery",
    AdvancedAbility.ARCHERY_FREE_ATTACK_MASTERY: "Archery Free Attack Mastery",
    AdvancedAbility.LONG_RANGE_ARCHERY: "Long-Range Archery",
    AdvancedAbility.ARCHERY_FREE_ATTACK_TRUE_MASTERY: "Archery Free Attack True Mastery",
    AdvancedAbility.MELEE_DUELLISTS_MEDAL: "Melee, Duellists Medal",
    AdvancedAbility.MELEE_MASTERY: "Melee Mastery",
    AdvancedAbility.MELEE_CONTROL_TEMPER: "Melee, Control Temper",
    AdvancedAbility.MELEE_HIT_POINTS: "Melee, Hit Points",
    AdvancedAbility.MELEE_EVASION: "Melee, Evasion",
    AdvancedAbility.MELEE_TRUE_MASTERY: "Melee True Mastery",
    AdvancedAbility.DRUIDIC_ANIMAL_SPIES: "Druidic Animal Spies",
    AdvancedAbility.DRUIDIC_WHALE_TRANSPORT: "Druidic Whale Transport",
    AdvancedAbility.DRUIDIC_TRANSPORT: "Druidic Transport",
    AdvancedAbility.DRUIDIC_HORSE_CONTROL: "Druidic Horse Control",
    AdvancedAbility.DRUIDIC_DINOSAURS: "Druidic Dinosaurs",
    AdvancedAbility.DRUIDIC_TRADES: "Druidic Trades",
    AdvancedAbility.THIEF_MASTERY_I: "Thief Mastery I",
    AdvancedAbility.THIEF_BANDITRY: "Thief, Banditry",
    AdvancedAbility.THIEF_MASTERY_II: "Thief Mastery II",
    AdvancedAbility.THIEF_PIRACY: "Thief, Piracy",
    AdvancedAbility.THIEF_MASTERY_III: "Thief Mastery III",
    AdvancedAbility.THIEF_TREASURY_RAIDS: "Thief, Treasury Raids",
    AdvancedAbility.THIEF_MASTERY_IV: "Thief Mastery IV",
    AdvancedAbility.THIEF_MASTERY_V: "Thief Mastery V",
    AdvancedAbility.EXPLORER_MILITARY_MAPS: "Explorer, Military Maps",
    AdvancedAbility.EXPLORER_FIND_WATER: "Explorer, Find Water",
    AdvancedAbility.EXPLORERS_SOCIETY_MAPS: "Explorer's Society Maps",
    AdvancedAbility.EXPLORERS_LONG_RANGE_TRADE_ROUTES: "Explorer's Long-Range Trade Routes",
    AdvancedAbility.EXPLORING_DIFFICULT_TERRAIN: "Exploring Difficult Terrain",
    AdvancedAbility.EXPLORER_FIND_MINES: "Explorer, Find Mines",
    AdvancedAbility.SPY_BLACKMAIL: "Spy, Blackmail",
    AdvancedAbility.SPY_DOUBLE_AGENT: "Spy, Double Agent",
    AdvancedAbility.SPY_SUPER_SLEUTH: "Spy, Super Sleuth",
    AdvancedAbility.SPY_EXPANDED_SPYING: "Spy, Expanded Spying",
    AdvancedAbility.SPY_BRAINWASH: "Spy, Brainwash",
    AdvancedAbility.SPY_ASSASSINATE: "Spy, Assassinate",
    AdvancedAbility.SUPER_SAGE_I: "Super Sage I",
    AdvancedAbility.SUPER_SAGE_II: "Super Sage II",
    AdvancedAbility.SUPER_SAGE_III: "Super Sage III",
    AdvancedAbility.SUPER_SAGE_IV: "Super Sage IV",
    AdvancedAbility.SUPER_SAGE_V: "Super Sage V",
    AdvancedAbility.ENHANCED_HOLY_SYMBOL: "Enhanced Holy Symbol",
    AdvancedAbility.WORDS_OF_HEALING_SPELL: '"Words of Healing" Spell',
    AdvancedAbility.HOLY_PLACES: "Holy Places",
    AdvancedAbility.KNOW_ALIGNMENT_TALENT: '"Know Alignment" Talent',
    AdvancedAbility.ENHANCED_RESURRECTION: "Enhanced Resurrection",
    AdvancedAbility.GATE_ANGEL_SPELL: '"Gate Angel" Spell',
    AdvancedAbility.DARK_PLACES: "Dark Places",
    AdvancedAbility.ENHANCED_SKELETAL_UNITS: "Enhanced Skeletal Units",
    AdvancedAbility.WITCHSIGHT_TALENT: '"Witchsight" Talent',
    AdvancedAbility.ENHANCED_COMBAT_NE_SPELLS: 'Enhanced Combat "NE" Spells',
    AdvancedAbility.SCAR_TERRAIN_SPELL: '"Scar Terrain" Spell',
    AdvancedAbility.GATE_DEMON_SPELL: '"Gate Demon" Spell',
    AdvancedAbility.ENHANCED_EARTHQUAKE: "Enhanced Earthquake",
    AdvancedAbility.ELEMENTAL_PLACES: "Elemental Places",
    AdvancedAbility.ENHANCED_COMBAT_EL_SPELLS: 'Enhanced Combat "EL" Spells',
    AdvancedAbility.MAKE_GEMS_TALENT: '"Make Gems" Talent',
    AdvancedAbility.LAVA_POOL_SPELL: '"Lava Pool" Spell',
    AdvancedAbility.MYSTIC_WINDS_SPELL: '"Mystic Winds" Spell',
    AdvancedAbility.AUGUR_COMBAT_SPELL: 'Psychic Magic- "Augur Combat" Spell',
    AdvancedAbility.PSYCHIC_PLACES: "Psychic Places",
    AdvancedAbility.ENHANCED_CLAIRVOYANCE: "Enhanced Clairvoyance",
    AdvancedAbility.SENSE_DANGER_TALENT: '"Sense Danger" Talent',
    AdvancedAbility.LOCATE_OBJECT_SPELL: '"Locate Object" Spell',
    AdvancedAbility.ENHANCED_CHARM: "Enhanced Charm",
    AdvancedAbility.ILLUSORY_PLACES: "Illusory Places",
    AdvancedAbility.DETECT_ILLUSIONS_TALENT: '"Detect Illusions" Talent',
    AdvancedAbility.ENHANCED_ILLUSORY_TERRAIN: "Enhanced Illusory Terrain",
    AdvancedAbility.ENHANCED_INVISIBILITY: "Enhanced Invisibility",
    AdvancedAbility.ILLUSORY_FOG_SPELL: '"Illusory Fog" Spell',
    AdvancedAbility.ILLUSORY_HERO_SPELL: '"Illusory Hero" Spell',
}


# The short tag/headline after the name's colon in the source excerpt
# (e.g. "100% Training Bonus").
ADVANCED_ABILITY_TAGLINE: dict[AdvancedAbility, str] = {
    AdvancedAbility.TACTICAL_WARGAMES_MASTERY: "100% Training Bonus",
    AdvancedAbility.TACTICAL_MASTERY_10: "10% Tactical Bonus",
    AdvancedAbility.TACTICAL_MASTERY_15: "15% Tactical Bonus",
    AdvancedAbility.TACTICAL_MASTERY_20: "20% Tactical Bonus",
    AdvancedAbility.TACTICAL_COMBINED_ARMS: "2nd-Line 100% Bonus",
    AdvancedAbility.ADAPT_TACTICS_TO_TERRAIN: "75% Strength in Adverse Terrain",
    AdvancedAbility.MARCH_THROUGH_FLOODS: "Costs One MP",
    AdvancedAbility.MARCH_CAVALRY: "Extra Move for Cavalry",
    AdvancedAbility.MARCH_INFANTRY: "Extra Move for Infantry",
    AdvancedAbility.MARCH_CAVALRY_MASTERY: "Extra Move for Cavalry",
    AdvancedAbility.MARCH_INFANTRY_MASTERY: "Extra Move for Infantry",
    AdvancedAbility.MARCH_CAVALRY_TRUE_MASTERY: "Extra Move for Cavalry",
    AdvancedAbility.NAVAL_LONG_DEFEND: "2-Hex Defense Range",
    AdvancedAbility.NAVAL_MASTERY_10: "10% Naval Bonus",
    AdvancedAbility.NAVAL_MASTERY_GREAT_15: "15% Naval Bonus",
    AdvancedAbility.NAVAL_MASTERY_EXALTED_20: "20% Naval Bonus",
    AdvancedAbility.NAVAL_HUG_COASTLINE: "Move Land-to-Land on Coasts",
    AdvancedAbility.NAVAL_COMBINED_ARMS: "2nd-Line 100% Bonus",
    AdvancedAbility.ARCHERY_FREE_ATTACK: "Bonus Archery Shot",
    AdvancedAbility.SHORT_RANGE_ARCHERY: "Fire at Melee Range",
    AdvancedAbility.ARCHERY_FREE_ATTACK_MASTERY: "Bonus Archery Shot",
    AdvancedAbility.LONG_RANGE_ARCHERY: "Fire at Spell Range",
    AdvancedAbility.ARCHERY_FREE_ATTACK_TRUE_MASTERY: "Bonus Archery Shot",
    AdvancedAbility.MELEE_DUELLISTS_MEDAL: "Bonus for Duelling Humanoids",
    AdvancedAbility.MELEE_MASTERY: "10% Bonus, Plus 1 Damage",
    AdvancedAbility.MELEE_CONTROL_TEMPER: "Use Best Temper",
    AdvancedAbility.MELEE_HIT_POINTS: "1-5 Additional HP",
    AdvancedAbility.MELEE_EVASION: "Plus 30% Fleeing",
    AdvancedAbility.MELEE_TRUE_MASTERY: "Plus 2 Damage",
    AdvancedAbility.DRUIDIC_ANIMAL_SPIES: "Spy Adjacent Provinces",
    AdvancedAbility.DRUIDIC_WHALE_TRANSPORT: "Transport Infantry",
    AdvancedAbility.DRUIDIC_TRANSPORT: "Transport any unit on War Fleet",
    AdvancedAbility.DRUIDIC_HORSE_CONTROL: "No Beast Nemesis",
    AdvancedAbility.DRUIDIC_DINOSAURS: "Recruit Dinosaurs",
    AdvancedAbility.DRUIDIC_TRADES: "Trade with Monsters",
    AdvancedAbility.THIEF_MASTERY_I: "15% Stealing Bonus",
    AdvancedAbility.THIEF_BANDITRY: "Raid Land Provinces",
    AdvancedAbility.THIEF_MASTERY_II: "15% Stealing Bonus",
    AdvancedAbility.THIEF_PIRACY: "Raid Sea Provinces",
    AdvancedAbility.THIEF_MASTERY_III: "15% Stealing Bonus",
    AdvancedAbility.THIEF_TREASURY_RAIDS: "Against King or Capital Province",
    AdvancedAbility.THIEF_MASTERY_IV: "15% Stealing Bonus",
    AdvancedAbility.THIEF_MASTERY_V: "15% Stealing Bonus",
    AdvancedAbility.EXPLORER_MILITARY_MAPS: "200% Exploration",
    AdvancedAbility.EXPLORER_FIND_WATER: "No Desert Riders Needed in Desert",
    AdvancedAbility.EXPLORERS_SOCIETY_MAPS: "Learn New Provinces",
    AdvancedAbility.EXPLORERS_LONG_RANGE_TRADE_ROUTES: "Trade Sage Discoveries",
    AdvancedAbility.EXPLORING_DIFFICULT_TERRAIN: "10% Bonus to Basic Exploration Number",
    AdvancedAbility.EXPLORER_FIND_MINES: "Increase Tax Base in Province",
    AdvancedAbility.SPY_BLACKMAIL: "Trail 'n' Mail",
    AdvancedAbility.SPY_DOUBLE_AGENT: "Masquerade as Mercenary",
    AdvancedAbility.SPY_SUPER_SLEUTH: "Automatic Trail Success, Know Distance",
    AdvancedAbility.SPY_EXPANDED_SPYING: "Better Info (Features; Skills, Offices)",
    AdvancedAbility.SPY_BRAINWASH: "Talk to Change Alignment",
    AdvancedAbility.SPY_ASSASSINATE: "Encounter Kings, Army Leaders",
    AdvancedAbility.SUPER_SAGE_I: "plus 5% probability when researching there",
    AdvancedAbility.SUPER_SAGE_II: "plus 5% probability when researching there",
    AdvancedAbility.SUPER_SAGE_III: "plus 5% probability when researching there",
    AdvancedAbility.SUPER_SAGE_IV: "plus 5% probability when researching there",
    AdvancedAbility.SUPER_SAGE_V: "plus 5% probability when researching there",
    AdvancedAbility.ENHANCED_HOLY_SYMBOL: "Attack Evil Alignment",
    AdvancedAbility.WORDS_OF_HEALING_SPELL: "New Special Combat Heal",
    AdvancedAbility.HOLY_PLACES: "Altar, Monastery, Hall",
    AdvancedAbility.KNOW_ALIGNMENT_TALENT: "In Encounters",
    AdvancedAbility.ENHANCED_RESURRECTION: "Make Same Alignment",
    AdvancedAbility.GATE_ANGEL_SPELL: "Call Valhalla Hero",
    AdvancedAbility.DARK_PLACES: "Tomb, Crypt, Catacombs",
    AdvancedAbility.ENHANCED_SKELETAL_UNITS: "May Leave them anywhere",
    AdvancedAbility.WITCHSIGHT_TALENT: "See Invisibility",
    AdvancedAbility.ENHANCED_COMBAT_NE_SPELLS: "More Targets for Hand of Death, Control Undead",
    AdvancedAbility.SCAR_TERRAIN_SPELL: "-2 Taxation, Change Race at 0",
    AdvancedAbility.GATE_DEMON_SPELL: "Summon Demon",
    AdvancedAbility.ENHANCED_EARTHQUAKE: "Create Tidal Wave",
    AdvancedAbility.ELEMENTAL_PLACES: "Sacred Rock, Mountain Peak, Megaliths",
    AdvancedAbility.ENHANCED_COMBAT_EL_SPELLS: "Fireball, Ice Suspension always work",
    AdvancedAbility.MAKE_GEMS_TALENT: "1-3g if Practice Elemental",
    AdvancedAbility.LAVA_POOL_SPELL: "Instant Death if successful",
    AdvancedAbility.MYSTIC_WINDS_SPELL: "Wind-Walking Armies",
    AdvancedAbility.AUGUR_COMBAT_SPELL: "New spell",
    AdvancedAbility.PSYCHIC_PLACES: "Tower, Temple, Lost Temple",
    AdvancedAbility.ENHANCED_CLAIRVOYANCE: "Perceive Abilities",
    AdvancedAbility.SENSE_DANGER_TALENT: "Avoid Encounters",
    AdvancedAbility.LOCATE_OBJECT_SPELL: "Locate Magic Item",
    AdvancedAbility.ENHANCED_CHARM: "Gain Treasure",
    AdvancedAbility.ILLUSORY_PLACES: "Pool, Maze, Labyrinth",
    AdvancedAbility.DETECT_ILLUSIONS_TALENT: "Detect Illusions, plus 25% Disbelieve Mirror Image",
    AdvancedAbility.ENHANCED_ILLUSORY_TERRAIN: "Illusory Army, Race; 66% Strength",
    AdvancedAbility.ENHANCED_INVISIBILITY: "30% Fleee, 15% Steal Bonuses",
    AdvancedAbility.ILLUSORY_FOG_SPELL: "Slow and Weaken Air Armies",
    AdvancedAbility.ILLUSORY_HERO_SPELL: "Illusory Valhalla Hero",
}


ADVANCED_ABILITY_DESCRIPTION: dict[AdvancedAbility, str] = {
    AdvancedAbility.TACTICAL_WARGAMES_MASTERY: (
        "The chance for a unit to increase in quality when Practicing "
        "Tactics (or Naval) is increased by 100% (example: an Average "
        "unit now has a 10% chance to improve per phase)."
    ),
    AdvancedAbility.TACTICAL_MASTERY_10: (
        "The armies commanded by a character at a battle are "
        "increased in strength by 10%."
    ),
    AdvancedAbility.TACTICAL_MASTERY_15: (
        "The armies commanded by a character at a battle are "
        "increased in strength by 15%. Note: This bonus cancels "
        "Tactical Mastery: 10% Tactical Bonus."
    ),
    AdvancedAbility.TACTICAL_MASTERY_20: (
        "The armies commanded by a character at a battle are "
        "increased in strength by 20%. Note: This bonus cancels "
        "Tactical Mastery: 10% Tactical Bonus and Tactical Mastery: "
        "15% Tactical Bonus."
    ),
    AdvancedAbility.TACTICAL_COMBINED_ARMS: (
        "A character can use Combined Arms when in supreme command at "
        "a land battle. This allows the first two units in a column, "
        "if they are different army types, to complement each other's "
        "fighting abilities. They both fight at 100% strength. The "
        "commander will tend to make use of this ability by placing "
        "different army types in a battle column."
    ),
    AdvancedAbility.ADAPT_TACTICS_TO_TERRAIN: (
        "When a character directly leads a unit at a battle, the "
        "effect of adverse terrain is reduced. The unit is reduced to "
        "75% of normal strength, instead of 50%."
    ),
    AdvancedAbility.MARCH_THROUGH_FLOODS: (
        "By using pontoon bridges, ferries and so forth, it becomes "
        "possible for armies to enter or leave any province affected "
        "by the Flood spell. One movement point is deducted from all "
        "units which have to use this ability, after they have moved."
    ),
    AdvancedAbility.MARCH_CAVALRY: (
        "The character adds one to the movement rate of land armies "
        "which start with 3 or more movement points."
    ),
    AdvancedAbility.MARCH_INFANTRY: (
        "The character adds one to the movement rate of land armies "
        "which start with 1-2 movement points."
    ),
    AdvancedAbility.MARCH_CAVALRY_MASTERY: (
        "The character adds one more to the movement rate of land "
        "armies which start with 3 or more movement points."
    ),
    AdvancedAbility.MARCH_INFANTRY_MASTERY: (
        "The character adds one more to the movement rate of land "
        "armies which start with 1-2 movement points."
    ),
    # Phase 768: project-original text, clearly labeled -- no 3rd-tier
    # catalog entry survives for March Cavalry (see this ability's own
    # comment on the `AdvancedAbility` enum above for the full sourcing
    # and the Archery-precedent/user-confirmation this text is based
    # on). Mirrors MARCH_CAVALRY_MASTERY's own "adds one more" phrasing.
    AdvancedAbility.MARCH_CAVALRY_TRUE_MASTERY: (
        "The character adds yet one more to the movement rate of land "
        "armies which start with 3 or more movement points."
    ),
    AdvancedAbility.NAVAL_LONG_DEFEND: (
        'The "Long Naval Defend" ability increases the range for the '
        "Defend order for naval forces. The character will defend "
        "against an attack on any province that is: a) 2 or less "
        "hexes away from the leader, and b) 2 or less hexes away from "
        "the stated hex to defend. For example, if the character is "
        "in a land province, and an adjacent land province is "
        "invaded, he can respond to the invasion by moving into an "
        "adjacent friendly sea province, then into the province under "
        "attack. Even if the province is 2 hexes away, only 1 "
        "movement point is used. The character must lead at least 1 "
        "Fleet, Sea Folk or Whale unit to use this ability. Note: "
        'with the "Move" command, you can\'t use this ability to '
        '"skip" a province.'
    ),
    AdvancedAbility.NAVAL_MASTERY_10: (
        "The units commanded by a character at a sea battle are "
        "increased in strength by 10%."
    ),
    AdvancedAbility.NAVAL_MASTERY_GREAT_15: (
        "The units commanded by a character at a sea battle are "
        "increased in strength by 15%. Note: This bonus cancels Naval "
        "Mastery: 10% Naval Bonus."
    ),
    AdvancedAbility.NAVAL_MASTERY_EXALTED_20: (
        "The units commanded by a character at a sea battle are "
        "increased in strength by 20%. Note: This bonus cancels Naval "
        "Mastery: 10% Naval Bonus and Naval Mastery: 15% Naval Bonus."
    ),
    AdvancedAbility.NAVAL_HUG_COASTLINE: (
        "A character can now move along a coastline directly from one "
        "land province to another, slipping in and out of shallows "
        "along the coast, without having to move into the adjacent "
        "sea province. If both fleets and land units accompany the "
        "character, as many of them as possible are transported on "
        "ships (units with a speed of 1 or 2 have the highest "
        "priority for transport, the tiebreaker being won by the "
        "lowest-numbered unit designations)."
    ),
    AdvancedAbility.NAVAL_COMBINED_ARMS: (
        "A character can use Naval Combined Arms when in supreme "
        "command at a sea battle. This allows the first two units in "
        "a column, if they are different army types, to complement "
        "each other's fighting abilities. They both fight at 100% "
        "strength. The commander will tend to make use of this "
        "ability by placing different unit types in a battle column."
    ),
    AdvancedAbility.ARCHERY_FREE_ATTACK: (
        "One more free attack is gained when using the Fire tactic in "
        "personal combat."
    ),
    AdvancedAbility.SHORT_RANGE_ARCHERY: (
        "The Archer may now use the Fire tactic at Melee Range, with "
        "the normal chance to hit."
    ),
    AdvancedAbility.ARCHERY_FREE_ATTACK_MASTERY: (
        "One more free attack is gained when using the Fire tactic in "
        "personal combat."
    ),
    AdvancedAbility.LONG_RANGE_ARCHERY: (
        "The Archer may now use the Fire tactic at Spell Range, with "
        "half the normal chance to hit the target."
    ),
    AdvancedAbility.ARCHERY_FREE_ATTACK_TRUE_MASTERY: (
        "One more free attack is gained when using the Fire tactic in "
        "personal combat."
    ),
    AdvancedAbility.MELEE_DUELLISTS_MEDAL: (
        "When fighting against humanoid creatures, the character has "
        "a plus 10% chance to hit and plus 1 damage in melee, while "
        "the opponent has -10% chance to hit and -1 damage."
    ),
    AdvancedAbility.MELEE_MASTERY: (
        "A character gains a plus 10% chance to hit and plus 1 damage "
        "(the opponent in melee does not get a -10% chance or less "
        "damage)."
    ),
    AdvancedAbility.MELEE_CONTROL_TEMPER: (
        "With this ability, the Berserk temper is used initially to "
        "gain the extra 1-4 hit points, then the temper is usually "
        "adjusted to whatever temper gains the most favorable "
        "benefits in combat."
    ),
    AdvancedAbility.MELEE_HIT_POINTS: (
        "The Gods grant 1-5 additional hit points in any encounter "
        "(depending on how many of the Gods are betting on the "
        "character in their gambling sessions)."
    ),
    AdvancedAbility.MELEE_EVASION: (
        "A character becomes expert at evading opponents when using "
        "the Flee tactic and gains +30% to the chances of fleeing a "
        "combat."
    ),
    AdvancedAbility.MELEE_TRUE_MASTERY: (
        "A character gains a plus 2 damage (the opponent in melee "
        "does not get a -10% chance or less damage)."
    ),
    AdvancedAbility.DRUIDIC_ANIMAL_SPIES: (
        "The Druid is able to befriend the small animals and birds, "
        "who willingly serve as spies. When the Druid issues a Spy "
        "order (SP), animals will scout adjacent provinces, then come "
        "back and squeak their little reports in their own language "
        "to the comprehending Druid. However, only military forces "
        "are reported."
    ),
    AdvancedAbility.DRUIDIC_WHALE_TRANSPORT: (
        "The Druid can now train Whale Leagues to transport infantry "
        "armies overseas. Each Whale unit may transport one infantry "
        "unit."
    ),
    AdvancedAbility.DRUIDIC_TRANSPORT: (
        "The Druid can now coax onto fleets those army types which "
        "normally would never venture to board them, such as Ents "
        "and Dinosaurs. Each fleet may transport one such unit."
    ),
    AdvancedAbility.DRUIDIC_HORSE_CONTROL: (
        "The Druid is able to calm horses who are threatened in "
        "battle by the various beasts that frighten them. As a "
        "result, cavalry units directly led by the Druid no longer "
        'have the "Beasts" nemesis listed in the Army Type Table.'
    ),
    AdvancedAbility.DRUIDIC_DINOSAURS: (
        "The Druid can now recruit Dinosaur armies. Many dinosaurs "
        "roam this world, trainable only by skilled Elven riders (the "
        "only race with enough natural empathy to control these "
        "beasts). Their abilities are: Strength: Unpredictable (5 to "
        "10); Speed: 3; Pay: 3; Home Terrain: None; Adverse Terrain: "
        "Sea; Nemesis: Phalanx; Race: Saurian. For full quality, "
        'Druid level 5 is required. They qualify as "Beasts", the '
        "nemesis to mounted units. They can't be transported by sea "
        "or air, but each can transport one infantry unit. Only one "
        "can be recruited per province per turn, only in place of "
        "elven EL, LC or HC, and no further units may be recruited in "
        "the province that turn."
    ),
    AdvancedAbility.DRUIDIC_TRADES: (
        "Druid is now able to establish trade relations with "
        "monsters. The Druid can trade any magic item he possesses "
        "for one treasure held by a monster occupying a feature. This "
        'is done by just using the "GI-ve" order. If there is a '
        'specific treasure number you want to trade for, just use '
        'the "Say" tactic to say the item number (e.g., "Give me item '
        '100").'
    ),
    AdvancedAbility.THIEF_MASTERY_I: (
        "The Thief adds 15% to his chance to Steal (however, the "
        "maximum chance is always 95%)."
    ),
    AdvancedAbility.THIEF_BANDITRY: (
        "The Thief attracts a following among the bandit population "
        "of the world and can now carry out highway robbery on a "
        'humongous scale. Whenever he practices thievery (the "(PR) '
        'TH" action) in another king\'s land province, and no other '
        "character is practicing with him, he will ravage the "
        "countryside as a bandit, robbing and looting the population. "
        "The Thief will rake in about 15% of the province's tax base "
        "for each phase he acts as a bandit. Military units are not "
        'required to be with the character. This action also counts '
        'as a normal "Spy" action in all respects.'
    ),
    AdvancedAbility.THIEF_MASTERY_II: (
        "The Thief adds 15% to his chance to Steal (however, the "
        "maximum chance is always 95%)."
    ),
    AdvancedAbility.THIEF_PIRACY: (
        "The Thief attracts a following among the pirate population "
        "of the world, and can now carry out piracy on a large scale. "
        'Whenever he practices thievery (the "(PR) TH" action) in '
        "another king's sea province, and no other character is "
        "practicing with him, he will sail the seas with rogue pirate "
        "ships, chasing down and looting the seagoing commerce. The "
        "Thief will snare about 50% of the province's tax value for "
        "each phase he acts as a pirate, and the province owner's "
        "taxation will be reduced accordingly. In zero-taxation "
        "provinces, the Thief will still often loot 1 gold from the "
        "treasury of the province owner. Military units are not "
        'required to be with the character. This action also counts '
        'as a normal "Spy" action in all respects.'
    ),
    AdvancedAbility.THIEF_MASTERY_III: (
        "The Thief adds 15% to his chance to Steal (however, the "
        "maximum chance is always 95%)."
    ),
    AdvancedAbility.THIEF_TREASURY_RAIDS: (
        "The Raid Treasury targets the treasury of a foreign king. "
        "The thief must be in either the hex where the king is "
        "located, or his home province, if he still owns it. The Raid "
        "Treasury ability is activated by giving an order to "
        "Encounter that king number (even if the thief is in the "
        "king's home province while the king is elsewhere). Of "
        'course, there must be a ST-eal tactic in the encounter plan. '
        "The success chance is halved (normal when stealing from "
        "kings). If successful, the thief gets away with up to half "
        "of the treasury. If he fails, he suffers the fate described "
        "in the rules section on stealing. In either case, the guard "
        "is doubled for that kingdom against further attempts in the "
        "same turn and so further attempts in the same turn are "
        "halved in probability."
    ),
    AdvancedAbility.THIEF_MASTERY_IV: (
        "The Thief adds 15% to his chance to Steal (however, the "
        "maximum chance is always 95%)."
    ),
    AdvancedAbility.THIEF_MASTERY_V: (
        "The Thief adds 15% to his chance to Steal (however, the "
        "maximum chance is always 95%)."
    ),
    AdvancedAbility.EXPLORER_MILITARY_MAPS: (
        "The explorer can now make Military Maps. This ability "
        "enables the Explorer to explore provinces up to 200%, "
        "increasing the maximum effect of exploration on army "
        "strength from 25% to 50% (at maximum)."
    ),
    AdvancedAbility.EXPLORER_FIND_WATER: (
        "The Explorer is now able to find water even in the desert "
        "(at oases, by draining water from cacti, and so on). If the "
        "Explorer is present at a battle, no units fighting with his "
        "side will suffer from thirst and penalties in a Desert "
        "province."
    ),
    AdvancedAbility.EXPLORERS_SOCIETY_MAPS: (
        "The Explorer starts receiving maps from the Explorer's "
        "Society. Each time he Practices Exploration, he receives 1-3 "
        "maps telling about new provinces not yet found by your "
        "kingdom. If he Explores a province, 0-2 maps are received."
    ),
    AdvancedAbility.EXPLORERS_LONG_RANGE_TRADE_ROUTES: (
        "With Long-Range Trade Routes, for each explorer of this "
        "level employed by your kingdom, you can use the "
        "scientific-treaty rule to trade Sage Inventions with a "
        "faraway foreign kingdom, even if your kingdoms aren't "
        "adjacent and no character is there to make the trade."
    ),
    AdvancedAbility.EXPLORING_DIFFICULT_TERRAIN: (
        'With the Explore Difficult Terrain ability, every "Basic '
        'Exploration Number" on the terrain table is increased by '
        "10% for the Explorer. You gain +10% exploration in every "
        "province."
    ),
    AdvancedAbility.EXPLORER_FIND_MINES: (
        "With the Find Mines ability, whenever a province is "
        "explored, there is a chance to find a Mine which will "
        "increase the provincial tax base by 1-3 gold per turn "
        "(maximum of 10 gold). In mountains the base chance is 35%, "
        "in other land terrain 15%. Each time he explores a province, "
        "the chance of finding another mine in that province is "
        "halved. When exploring an enemy province, this ability is "
        "not used."
    ),
    AdvancedAbility.SPY_BLACKMAIL: (
        "When the Spy Trails (TR command) a foreign king and ends any "
        "phase in the same province, there is about a 20% chance of "
        "getting some dirt on him. If that happens, a message is "
        "delivered, with instructions to pay off your kingdom (the "
        "amount will average about 15 gold). If no payola is coughed "
        "up, he will lose 3 times that much in tax revenues when the "
        "dirt is given to the tabloids, causing great social turmoil. "
        "If the blackmail money isn't paid, the next attempt will be "
        "worth about half as much gold. Note: it's easier to find "
        "dirt on a king tending towards evil, harder for good kings; "
        "but evil kings pay less gold because their bad habits are "
        "already somewhat known; and, rich kings pay more gold. "
        "Blackmail is usable once per turn on a kingdom."
    ),
    AdvancedAbility.SPY_DOUBLE_AGENT: (
        "The Spy can now give the impression of being a wandering "
        "hero and will show up as such in any foreign king's turn "
        "report, if the spy is detected at all. If a foreign king "
        "tries to hire the Spy, the hiring will appear to be "
        "successful, but the spy will continue to execute the orders "
        "you give him, and at the end of the Spy's last action, you "
        "will gain spy reports on the province he occupies and the "
        "surrounding provinces, if they belong to the hiring king. "
        "Naturally, kings may not use this ability (because they "
        "cannot be wandering heroes and cannot be hired)."
    ),
    AdvancedAbility.SPY_SUPER_SLEUTH: (
        "When the Spy uses the Trail or Pursue actions, success is "
        "automatic, and the Spy can also guess how far away the "
        "target is (the guess may be off by one province)."
    ),
    AdvancedAbility.SPY_EXPANDED_SPYING: (
        "When using the Spy Province action, the Spy gains "
        "information on what features are known to the owning "
        "kingdom. With the Trail action, estimates are gained for "
        "skills, and for offices held."
    ),
    AdvancedAbility.SPY_BRAINWASH: (
        "When the spy uses the Talk tactic on any hero, that "
        "character will move one step closer in alignment to the "
        "Spy's alignment. Not usable on Kings."
    ),
    AdvancedAbility.SPY_ASSASSINATE: (
        "The spy can encounter kings and army leaders even if he has "
        "an attacking encounter plan. Also, King characters can now "
        "encounter other characters freely, without being avoided "
        "half the time."
    ),
    AdvancedAbility.SUPER_SAGE_I: (
        "The Sage gains an additional plus 5 when researching "
        "inventions if he is at his University (the location is shown "
        "in the Characters listing). All percentage bonuses are "
        "cumulative. The university is in the starting province of "
        "the hero or king. So the province where it was at Turn 0."
    ),
    AdvancedAbility.SUPER_SAGE_II: (
        "The Sage gains an additional plus 5 when researching "
        "inventions if he is at his University (the location is shown "
        "in the Characters listing). All percentage bonuses are "
        "cumulative. The university is in the starting province of "
        "the hero or king. So the province where it was at Turn 0."
    ),
    AdvancedAbility.SUPER_SAGE_III: (
        "The Sage gains an additional plus 5 when researching "
        "inventions if he is at his University (the location is shown "
        "in the Characters listing). All percentage bonuses are "
        "cumulative. The university is in the starting province of "
        "the hero or king. So the province where it was at Turn 0."
    ),
    AdvancedAbility.SUPER_SAGE_IV: (
        "The Sage gains an additional plus 5 when researching "
        "inventions if he is at his University (the location is shown "
        "in the Characters listing). All percentage bonuses are "
        "cumulative. The university is in the starting province of "
        "the hero or king. So the province where it was at Turn 0."
    ),
    AdvancedAbility.SUPER_SAGE_V: (
        "The Sage gains an additional plus 5 when researching "
        "inventions if he is at his University (the location is shown "
        "in the Characters listing). All percentage bonuses are "
        "cumulative. The university is in the starting province of "
        "the hero or king. So the province where it was at Turn 0."
    ),
    AdvancedAbility.ENHANCED_HOLY_SYMBOL: (
        "The Holy Symbol spell now has the same effect against "
        "opponents who have an Evil alignment as it does against "
        "Undead creatures."
    ),
    AdvancedAbility.WORDS_OF_HEALING_SPELL: (
        "A new Combat Spell is gained (command CA-WH). With this "
        "spell, a White Magician is able to heal himself even in the "
        "heat of battle (before now, healing is not possible in "
        "combat situations). The character is completely healed when "
        "the Words of Healing are spoken, gaining back all lost hit "
        "points. The spell is also half as likely to be disrupted by "
        "your opponent's tactics as other spells."
    ),
    AdvancedAbility.HOLY_PLACES: (
        "The White Magician can now use the magic of certain Holy "
        "Places of Power to increase the success chance of spells. At "
        "any Monastery, Altar or Great Hall, the success chance to "
        "cast a White Magic spell is increased by 20%. For Search "
        "Feature actions, the 20% bonus is applied when that type of "
        "feature is searched. For Action spells, the bonus is applied "
        "if that feature type is in the same province as the "
        "character, and is not occupied by a monster."
    ),
    AdvancedAbility.KNOW_ALIGNMENT_TALENT: (
        "This special White Magic Talent constantly operates by "
        "itself, without having to cast a spell. Whenever another "
        "character or monster is encountered, his exact alignment "
        "will immediately become apparent, as soon as the encounter "
        "or Search action is initiated. A temper estimate will also "
        "be made."
    ),
    AdvancedAbility.ENHANCED_RESURRECTION: (
        "A resurrected character becomes the same alignment as the "
        "spellcaster's king."
    ),
    AdvancedAbility.GATE_ANGEL_SPELL: (
        "A new Special Gate Angel spell is gained (command CA-GA): By "
        "the mystical power of this spell, an extra-dimensional gate "
        "is opened to Valhalla, through which a hero of the same "
        "alignment as the spellcaster passes. The hero appears at the "
        "end of the current gameturn. Only one Valhalla hero can "
        "visit the world during a turn, so no other king will receive "
        "a visitor from Valhalla. Each alignment from Good to Evil "
        "can still be visited only once in each 5-turn period (for "
        "this spell, Divine kingdoms are treated as Good, and Undead "
        "as Evil). If more than one player casts the Gate Angel "
        "spell, one of the spells will be nullified. The spellcaster "
        "has no control over which hero arrives from Valhalla."
    ),
    AdvancedAbility.DARK_PLACES: (
        "The Necromancer is now able to use the magic of certain Dark "
        "Places of Power to increase the success chance of spells. At "
        "any Tomb, Crypt or Catacombs, the success chance to cast a "
        "Necromancy spell is increased by 20%. For Search Feature "
        "actions, the 20% bonus is applied when that type of feature "
        "is searched. For Action spells, the bonus is applied if that "
        "feature type is in the same province as the character, and "
        "is not occupied by a monster."
    ),
    AdvancedAbility.ENHANCED_SKELETAL_UNITS: (
        "The necromancer may now Leave skeletal armies to another "
        "character or the garrison commander, even if there is no "
        "Undead leader to control the armies. He may also Pick Up "
        "skeletal armies freely, but other characters are not given "
        "the ability to pick up armies from the necromancer. The "
        "necromancer can use this ability even for skeletal armies "
        "that were raised before now."
    ),
    AdvancedAbility.WITCHSIGHT_TALENT: (
        "This special Necromancy Talent constantly operates by "
        "itself, without having to cast a spell. Whenever an opponent "
        "turns Invisible in combat, the Necromancer can still see his "
        "opponent and is unaffected by the spell."
    ),
    AdvancedAbility.ENHANCED_COMBAT_NE_SPELLS: (
        'The "Hand of Death" and "Control Undead" spells are '
        'enhanced. "Hand of Death" now works against all creatures '
        'and "Control Undead" will work against anti-holy creatures, '
        "in addition to affecting the Undead (but if you use the "
        '"Control Undead" against anti-holies, there is a percentage '
        "chance that they will resist the spell, equal to half their "
        "current hit points)."
    ),
    AdvancedAbility.SCAR_TERRAIN_SPELL: (
        "A new spell is gained (command CA-ST): By the horrible power "
        "of this spell, a co-located or adjacent province is scarred "
        "and mangled, and its tax base is reduced by 2 gold "
        "immediately and permanently. When the tax base reaches 0 "
        "gold, the province becomes incapable of supporting normal "
        "life forms. If it's a land province, the racial type will "
        "change to Orcs, Dragons or Trolls (usually by immigration "
        "from an adjacent province) and the army type will change to "
        "something suitable to the new racial type. Sea provinces "
        "will just lose whatever provincial racial and army type they "
        "may have."
    ),
    AdvancedAbility.GATE_DEMON_SPELL: (
        "A new spell is gained (command CA-GD): By the dark power of "
        "this spell, an extra-dimensional gate is opened to the "
        "nether worlds, from where a demon is summoned to fight in "
        "place of the spellcaster. The caster has no control over "
        "what type of demon will appear. If the Demon wins, it will "
        "return to the Abyss from whence it came. If it loses, the "
        "caster must continue the fight at the current combat range. "
        "If another Mirror Image or Gate Demon spell is cast against "
        "it, both spells will be nullified. A Demon may refuse to "
        "fight an opponent of Evil to Undead alignment (50% chance). "
        "See GATE_DEMON_TABLE below for the d100 roll table of which "
        "demon monster appears."
    ),
    AdvancedAbility.ENHANCED_EARTHQUAKE: (
        "When an Earthquake is cast on a Sea province, the upheaval "
        "on the ocean floor creates a humongous tidal wave. Every "
        "military unit in the province has a 5% chance per level of "
        "the spellcaster of being destroyed (except for Whales and "
        "Sea Folk, who just dive under the wave). The tidal wave will "
        "continue on, moving generally in the opposite direction from "
        "the spellcaster, destroying units in sea provinces as it "
        "moves along (but weakening by 5% upon entering each new "
        "province). When it finally hits a land province, it will end "
        "there, but will be effective against Fleets, Sea Folk and "
        "Whales (only) in that province, as they are washed ashore "
        "and beached. If the wave hits the Ice Cap, it simply ends "
        "there."
    ),
    AdvancedAbility.ELEMENTAL_PLACES: (
        "The Elemental Mage is now able to use the magic of certain "
        "Elemental Places of Power to increase the success chance of "
        "spells. At any Sacred Rock, Mountain Peak or Ancient "
        "Megaliths, the success chance to cast an Elemental Magic "
        "spell is increased by 20%. For Search actions, the 20% bonus "
        "is applied when that type of feature is searched. For Action "
        "spells, the bonus is applied if that feature type is in the "
        "same province as the character and is not occupied by a "
        "monster."
    ),
    AdvancedAbility.ENHANCED_COMBAT_EL_SPELLS: (
        'The "Fireball" and "Ice Suspension" spells are enhanced. '
        "They are now strong enough that Fireball can be cast against "
        "underwater monsters and Ice Suspension will work against "
        "any monster."
    ),
    AdvancedAbility.MAKE_GEMS_TALENT: (
        "Using this Elemental Talent, each time the mage practices "
        "elemental ability (PR EL), he makes gems as a natural "
        "byproduct of his researches, worth between 1-3 gold per "
        "practice session."
    ),
    AdvancedAbility.LAVA_POOL_SPELL: (
        'A new spell is gained (command CA-LP): The "Lava Pool of '
        'Fiery Death" spell enables the Elemental Mage to call upon '
        "the elemental spirits of Fire and Earth to cause the magma "
        "beneath the earth's surface to rise up and break apart the "
        "earth beneath the victim, who is sucked into a fiery "
        "whirlpool of death and sucked down into the very bowels of "
        "the earth. The spell won't work against flying, underwater, "
        "ghostly or anti-holy monsters (see LAVA_POOL_IMMUNE_MONSTERS "
        "below), and there is usually a chance to escape it (from 5% "
        "to 60%)."
    ),
    AdvancedAbility.MYSTIC_WINDS_SPELL: (
        "A new spell is gained (command CA-MW): By the mysterious "
        'power of the "Mystic Winds" spell, the great Wind Spirits of '
        "the heavens carry the mage or a co-located character into "
        "the sky, his fleets propelled through the air by magic "
        "breezes, his armies effortlessly wind-walking through the "
        "clouds. Each unit led by the affected leader has its "
        "movement set at 5 while the spell lasts and moves as an air "
        "unit. No fleet transport or air transport takes place: that "
        "is, each unit will use up movement points while under the "
        "effect of this spell. The spell ends just before the leader "
        "gets involved in any military battle between armies."
    ),
    AdvancedAbility.AUGUR_COMBAT_SPELL: (
        "A new spell is gained (command CA-AG). The Psychic Mage "
        "performs a powerful augury (forecast), whereby he divines "
        "the probable outcome of the combat. The computer will "
        "estimate the percentage chance of victory, if combat were to "
        "occur. If the plan following the spell is a combat-oriented "
        "plan, then if the chances are too low for the character's "
        "courage, he will shirk combat (Coward 80%, Cautious 60%, "
        "Brave 40%, Berserk 20%). Any encounter plan can be stated "
        "after casting this spell. Usually this spell should be the "
        "first tactic ordered, when it won't cost you a combat round; "
        "if it comes later, then the result will be an attempt to "
        "flee."
    ),
    AdvancedAbility.PSYCHIC_PLACES: (
        "The mage is now able to use the magic of certain Psychic "
        "Places of Power to increase the success chance of spells. At "
        "any Tower, Temple or Lost Temple, the success chance to cast "
        "a Psychic Magic spell is increased by 20%. For Search "
        "actions, the 20% bonus is applied when that type of feature "
        "is searched. For Action spells, the bonus is applied if that "
        "feature type is in the same province as the character, and "
        "is not occupied by a monster."
    ),
    AdvancedAbility.ENHANCED_CLAIRVOYANCE: (
        "In addition to gaining information on the character's "
        "actions, Clairvoyance spell gives the target's characteristic "
        "lines that are also printed out on your turn report."
    ),
    AdvancedAbility.SENSE_DANGER_TALENT: (
        'The "Sense Danger" Talent constantly operates by itself, '
        "without having to cast a spell. The Psychic is able to "
        "sense the approach of dangerous enemies. The Talent prevents "
        "having to enter combat in random encounters and encounters "
        "with unfriendly characters can be avoided 50% of the time. "
        "It is used only when the Flee tactic is the first one in "
        "the special encounter plan."
    ),
    AdvancedAbility.LOCATE_OBJECT_SPELL: (
        "A new spell is gained (command CA-LO). By the enchanting "
        "power of this spell, the provincial location of any magic "
        "item will be revealed to the spellcaster, as well as who is "
        "guarding the item, if anyone. If the magic item was lost to "
        "a wandering monster, it will be seen as guarded by a "
        "monster. The Psychic must specify the identifying number of "
        "the magic item, not the treasure name itself -- this is "
        "because there is sometimes more than one of the same magic "
        "item in the game. Notice also that the spell discovers what "
        "magic item is in a feature, by giving the ID number of that "
        "feature or item."
    ),
    AdvancedAbility.ENHANCED_CHARM: (
        "In addition to its other effects, the victim of a Charm "
        "spell now will also hand over one magic item, if available. "
        "If it's used as an encounter spell and it fails, of course "
        "the victim will be unhappy."
    ),
    AdvancedAbility.ILLUSORY_PLACES: (
        "The Illusionist can now use the magic of certain Illusory "
        "Places of Power to increase the success chance of spells. At "
        "any Maze, Labyrinth or Magic Pool, the success chance to "
        "cast an Illusory spell is increased by 20%. For Search "
        "actions, the 20% bonus is applied when that type of feature "
        "is searched. For Action spells, the bonus is applied if that "
        "feature type is in the same province as the character, and "
        "is not occupied by a monster."
    ),
    AdvancedAbility.DETECT_ILLUSIONS_TALENT: (
        "This Talent constantly operates by itself, without having to "
        "cast a spell. In combat, it gives the Illusionist a plus 25% "
        "chance to disbelieve a magical illusion. Also, the "
        "Phantasmal Armies spell has only half its normal effect when "
        "the Illusionist is present at a battle on the opposite side."
    ),
    AdvancedAbility.ENHANCED_ILLUSORY_TERRAIN: (
        "When another player sees the enhanced terrain illusion, he "
        "will also see a randomly generated race and army type. Also, "
        "armies fighting there will have their strength affected 67% "
        "by the illusory terrain, instead of 50%."
    ),
    AdvancedAbility.ENHANCED_INVISIBILITY: (
        "The spell now includes some masking of the senses of smell "
        "and hearing, giving the Illusionist an additional plus 15% "
        "chance when Stealing. Also, any attempt to Flee while "
        "Invisible will have a plus 30% chance to succeed."
    ),
    AdvancedAbility.ILLUSORY_FOG_SPELL: (
        "A new spell is gained (command CA-IF). By the murky power of "
        'the "Illusory Fog" spell, the Illusionist summons a dense '
        "fog to blanket a province, reaching up to the very heavens. "
        "All air units (Dragon Wings, Eagle Wings and those affected "
        'by "Mystic Winds" Spell) have their strength halved for any '
        "battle in the affected province, and must expend 1 "
        "additional movement point when entering or leaving it. The "
        "movement point is deducted after the unit(s) have already "
        "moved. The spell must be cast on an adjacent or co-located "
        "province, and it dissipates at the end of the gameturn."
    ),
    AdvancedAbility.ILLUSORY_HERO_SPELL: (
        "A new spell is gained (command CA-IH). By the wondrous magic "
        "power of this spell, the Illusionist creates an image of "
        "whatever Valhalla hero is currently in the world, to fight "
        "in his place. It is similar to Mirror-Image Phantasm, except "
        "that 15% is subtracted from the chance to disbelieve, and "
        "the illusory hero will usually not turn on its master if the "
        "illusion wins (unless the alignments of the illusion and the "
        "spellcaster are implacably hostile, for example Good versus "
        "Evil)."
    ),
}


# The 10 "New spell" Advanced Abilities each grant a specific already
# -modeled Spell (models/enums.py). Confirmed by exact name match
# against SPELL_NAME (Phase 84) for all of Spell's own ordinals 25-34
# -- closes the spdex gap flagged since Phase 23 (see module docstring).
ADVANCED_ABILITY_GRANTS_SPELL: dict[AdvancedAbility, Spell] = {
    AdvancedAbility.WORDS_OF_HEALING_SPELL: Spell.HEAL,
    AdvancedAbility.GATE_ANGEL_SPELL: Spell.GATE_ANGEL,
    AdvancedAbility.SCAR_TERRAIN_SPELL: Spell.SCAR_TERRAIN,
    AdvancedAbility.GATE_DEMON_SPELL: Spell.GATE_DEMON,
    AdvancedAbility.LAVA_POOL_SPELL: Spell.LAVA_POOL,
    AdvancedAbility.MYSTIC_WINDS_SPELL: Spell.MYSTIC_WINDS,
    AdvancedAbility.AUGUR_COMBAT_SPELL: Spell.AUGUR_COMBAT,
    AdvancedAbility.LOCATE_OBJECT_SPELL: Spell.LOCATE_OBJECT,
    AdvancedAbility.ILLUSORY_FOG_SPELL: Spell.ILLUS_FOG,
    AdvancedAbility.ILLUSORY_HERO_SPELL: Spell.ILLUS_HERO,
}


# "Gate Demon" spell's own d100 roll table for which demon monster
# appears -- every name matches an existing Monster member exactly
# (MONSTER_NAMES, Phase 75).
GATE_DEMON_TABLE: tuple[tuple[str, Monster], ...] = (
    ("1-20", Monster.IMP),
    ("20-40", Monster.SUCCUBUS),
    ("41-55", Monster.BONE_DEVIL),
    ("56-70", Monster.ICE_DEVIL),
    ("71-80", Monster.MAR_DEMON),
    ("81-90", Monster.RAKSHASHA),
    ("91-100", Monster.BAL_DEMON),
)


# "Lava Pool" spell's own list of monsters immune to it (flying,
# underwater, anti-holy or ghostly) -- every name matches an existing
# Monster member exactly (MONSTER_NAMES, Phase 75).
LAVA_POOL_IMMUNE_MONSTERS: frozenset[Monster] = frozenset(
    {
        # Flying
        Monster.BEHOLDER,
        Monster.B_DRAGON,
        Monster.COUATL,
        Monster.GENIE,
        Monster.GI_EAGLE,
        Monster.GI_WASP,
        Monster.GO_DRAGON,
        Monster.GR_DRAGON,
        Monster.GRYPHON,
        Monster.R_DRAGON,
        Monster.ROC,
        Monster.S_DRAGON,
        # Underwater
        Monster.ELASMOSAURUS,
        Monster.GI_CLAM,
        Monster.GI_OCTOPUS,
        Monster.GW_WHALE,
        Monster.MERMAID,
        # Anti-holy
        Monster.BAL_DEMON,
        Monster.ICE_DEVIL,
        Monster.IMP,
        Monster.LICH,
        Monster.MAR_DEMON,
        Monster.MUMMY,
        Monster.RAKSHASHA,
        Monster.SUCCUBUS,
        # Ghostly
        Monster.BANSHEE,
        Monster.GHOST,
        Monster.SPECTRE,
        Monster.VAMPIRE,
    }
)


# Six named-unique Treasure items each re-check a specific set of
# Abilities while held (SPEAK.PAS Check_MSpab, ~lines 66-78): each
# holding leader gets Check_ESpab(ldr, ability) called once per
# Ability in the tuple, re-confirming/re-announcing any level 5+
# talent already earned in that Ability. Identifiers resolved via
# CTBOTH.PAS lines 128-131 (ForcedMarch=Ability.MARCH,
# Illusionist=Ability.ILLUSION).
UNIQUE_ITEM_ADVANCED_ABILITY_CHECKS: dict[Treasure, tuple[Ability, ...]] = {
    Treasure.NAMED_UNIQUE_CROWN_ROHAN: (Ability.MARCH, Ability.TACTICAL),
    Treasure.NAMED_UNIQUE_AMULET_POWER: (Ability.PSYCHIC, Ability.WHITE, Ability.ELEMENTAL),
    Treasure.NAMED_UNIQUE_SCEPTER_LIFE: (Ability.SAGE, Ability.ILLUSION, Ability.MELEE),
    Treasure.NAMED_UNIQUE_MAP_MARAUDERS: (Ability.NAVAL,),
    Treasure.NAMED_UNIQUE_FANG_VAMPIRE: (Ability.MELEE, Ability.NECROMANCY),
    Treasure.NAMED_UNIQUE_HAMMER_POWER: (Ability.MELEE, Ability.DRUID),
}


# The 20 fix0-fix9/wreck0-wreck9 Discovery members each re-check a
# single specific Ability (SPEAK.PAS Check_DSpab, ~lines 80-90): the
# ordinal-to-Ability mapping is computed directly from the Pascal
# source's own `Check_It(ability(ord(d) Shr 1))` (fix0-fix9, ordinals
# 0-9) and `Check_It(ability(5+(ord(d) Shr 1)))` (wreck0-wreck9,
# ordinals 10-19) -- i.e. two Discoveries share each Ability, in
# Discovery-enum ordinal order.
DISCOVERY_ADVANCED_ABILITY_CHECKS: dict[Discovery, Ability] = {
    Discovery.LAND_SHIP: Ability.TACTICAL,
    Discovery.SCYTHED_CHARIOTS: Ability.TACTICAL,
    Discovery.PONY_EXPRESS: Ability.MARCH,
    Discovery.MACADAM_ROADS: Ability.MARCH,
    Discovery.GREEK_FIRE: Ability.NAVAL,
    Discovery.SEXTANT: Ability.NAVAL,
    Discovery.COMPOSITE_BOW: Ability.ARCHERY,
    Discovery.TUNGSTEN_TIPPED_ARROW: Ability.ARCHERY,
    Discovery.STRENGTH_ELIXIR: Ability.MELEE,
    Discovery.MITHRIL_CHAINMAIL: Ability.MELEE,
    Discovery.MEDITATION_INCENSE: Ability.DRUID,
    Discovery.CLASSIFICATION_OF_LIFE: Ability.DRUID,
    Discovery.MAGNETIZED_LOCK_PICKS: Ability.THIEF,
    Discovery.TRAP_FINDING_DUST: Ability.THIEF,
    Discovery.COMPASS: Ability.EXPLORER,
    Discovery.TELESCOPE: Ability.EXPLORER,
    Discovery.INVISIBLE_INK: Ability.SPY,
    Discovery.TWO_WAY_MIRRORS: Ability.SPY,
    Discovery.HIEROGLYPHIC_TRANSLATION: Ability.SAGE,
    Discovery.SCIENTIFIC_METHOD: Ability.SAGE,
}


class AdvancedAbilities(set):
    """A leader's Advanced Abilities: a plain ``set`` for membership, plus the slot each one came from.

    The original engine's ``SA_Num`` counts every ``spabord`` slot (one per skill level from 5 up) that holds a
    given ability, and the effects add up per occurrence: a template with Tactical Mastery 15% in three slots gives
    +15% for each one reached, not +15% once. A set alone loses that; ``slots`` remembers which slot of which Talent
    granted what (a slot is granted once, however many times its level is reached), and ``count()`` answers
    ``SA_Num``. A member with no recorded slot (set by hand, e.g. from the GM editor) counts once."""

    def __init__(self, *args) -> None:
        super().__init__(*args)
        self.slots: dict[tuple[Ability, int], AdvancedAbility] = {}

    def grant(self, ability: AdvancedAbility, talent: Ability | None = None, level: int | None = None) -> None:
        self.add(ability)
        if talent is not None and level is not None:
            self.slots[(talent, level)] = ability

    def count(self, ability: AdvancedAbility) -> int:  # type: ignore[override]
        if ability not in self:
            return 0
        return max(1, sum(1 for granted in self.slots.values() if granted is ability))


def grant_advanced_ability(leader, ability: AdvancedAbility, talent: Ability | None = None, level: int | None = None) -> None:
    """Records ``ability`` on ``leader`` from slot ``level`` of ``talent`` (a state saved before slots were tracked,
    holding a plain ``set``, is upgraded in place)."""

    if not isinstance(leader.advanced_abilities, AdvancedAbilities):
        leader.advanced_abilities = AdvancedAbilities(leader.advanced_abilities)
    leader.advanced_abilities.grant(ability, talent, level)


def advanced_ability_count(abilities: "set[AdvancedAbility]", ability: AdvancedAbility) -> int:
    """``SA_Num`` for any set of Advanced Abilities, plain ``set`` included (counts once if present)."""

    if isinstance(abilities, AdvancedAbilities):
        return abilities.count(ability)
    return 1 if ability in abilities else 0
