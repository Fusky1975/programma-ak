"""Core enums transcribed from the original Pascal engine.

Order and values must match ``HostAK/TP/CTBOTH.PAS`` exactly, since move
files encode these as raw integers positional to the original Pascal
``action``/``ability`` enum declarations.
"""

from enum import Enum, IntEnum


class ActionCode(IntEnum):
    """Mirrors the Pascal ``action`` enum (CTBOTH.PAS lines 98-102)."""

    LMOVE = 0
    EXPLORE = 1
    SEARCH = 2
    RECRUIT = 3
    DISBAND = 4
    HIRE = 5
    FIRE = 6
    LEAVE = 7
    PICK_UP = 8
    CAST = 9
    USE_MI = 10
    CHALLENGE = 11
    PRACTICE = 12
    ASPY = 13
    TRADE = 14
    DEFEND = 15
    PURSUE = 16
    TRAIL = 17
    WAIT = 18
    NO_ACTION = 19
    SUCC_TRAIL = 20
    MOVE_ABORT = 21


class Ability(Enum):
    """Mirrors the Pascal ``ability`` enum (CTBOTH.PAS lines 130-132)."""

    TACTICAL = 0
    MARCH = 1
    NAVAL = 2
    ARCHERY = 3
    MELEE = 4
    WHITE = 5
    NECROMANCY = 6
    ELEMENTAL = 7
    PSYCHIC = 8
    ILLUSION = 9
    DRUID = 10
    THIEF = 11
    EXPLORER = 12
    SPY = 13
    SAGE = 14


# REPORTS.PAS `Rep_Leaders`'s own CHARACTERS-section column header
# (~line 811-812): "Character      Loc Align  Temp M/F  Race Ini
# TaMaNaArMe WhNeElPsIl DrThExSpSa" -- the last 30 characters are 15
# two-letter ability abbreviations, positionally verbatim against this
# module's own `Tactical..Sage` declaration order (Phase 220).
ABILITY_ABBREVIATION: dict[Ability, str] = {
    Ability.TACTICAL: "Ta",
    Ability.MARCH: "Ma",
    Ability.NAVAL: "Na",
    Ability.ARCHERY: "Ar",
    Ability.MELEE: "Me",
    Ability.WHITE: "Wh",
    Ability.NECROMANCY: "Ne",
    Ability.ELEMENTAL: "El",
    Ability.PSYCHIC: "Ps",
    Ability.ILLUSION: "Il",
    Ability.DRUID: "Dr",
    Ability.THIEF: "Th",
    Ability.EXPLORER: "Ex",
    Ability.SPY: "Sp",
    Ability.SAGE: "Sa",
}


# CTBOTH.PAS `anoun` (~line 143), verbatim, positional with this module's
# own `Tactical..Sage` declaration order -- the noun form used by real
# report text like "+1 skill in <ability>" (REPORTS.PAS's own Discoveries
# of the Sages section, Phase 268) and elsewhere (`RUMORS.PAS Get_AbDesc`).
# Distinct from `ABILITY_ABBREVIATION` (two-letter codes) and from the
# separate `adesc` array (adjective form, e.g. "Tactical" vs. "Tactics") --
# only `anoun` has a confirmed real caller so far.
ABILITY_NAME: dict[Ability, str] = {
    Ability.TACTICAL: "Tactics",
    Ability.MARCH: "Marches",
    Ability.NAVAL: "Navigation",
    Ability.ARCHERY: "Archery",
    Ability.MELEE: "Meleeing",
    Ability.WHITE: "White Magic",
    Ability.NECROMANCY: "Necromancy",
    Ability.ELEMENTAL: "Element Magic",
    Ability.PSYCHIC: "Psychic Magic",
    Ability.ILLUSION: "Illusions",
    Ability.DRUID: "Druidism",
    Ability.THIEF: "Thievery",
    Ability.EXPLORER: "Exploring",
    Ability.SPY: "Spying",
    Ability.SAGE: "Sageness",
}


# RUMORS.PAS `Get_AbDesc` (~line 481, found while researching Phase 87's own
# "^Y: Character Description" marker -- that marker turned out to be the
# already-modeled Alignment+Temper "nature/character" sentence, not this;
# `Get_AbDesc` is a separate, unlabeled narrative helper, not itself a named
# PROSE.TXT marker). Given a character's *best* Ability's own skill level
# (0-9), produces the fame descriptor phrase used to build sentences like
# "(a Human, famous for Necromancy)" -- confirmed real and used (also
# REPORTS.PAS ~line 733). Levels 6-9 all collapse to the same "worshipped
# for" string in the Pascal source itself (`6..9: s:= 'worshipped for '`),
# not a transcription shortcut taken here.
FAME_DESCRIPTOR: dict[int, str] = {
    0: "noted for",
    1: "well known for",
    2: "famous for",
    3: "renowned for",
    4: "world-famous for",
    5: "revered for",
    6: "worshipped for",
    7: "worshipped for",
    8: "worshipped for",
    9: "worshipped for",
}


def action_from_int(value: int) -> "ActionCode | int":
    """Map a raw action int to ``ActionCode`` where valid, else keep it raw.

    Guards against move files containing values outside the documented
    0-21 range so the parser never has to guess or raise on unknown codes.
    """

    try:
        return ActionCode(value)
    except ValueError:
        return value


class Maneuver(IntEnum):
    """Mirrors the Pascal ``maneuver`` enum (``CTBOTH.PAS``, the ``manab``
    abbreviation table: ``'CA','US','SQ','TA','SA','GI','FU','ST','FI',
    'ME','FL','BE','NM','SC'``) -- an Encounter Plan's ordered combat
    tactics (rulebook [5.1]-[5.8]), used by the Search and Challenge
    actions.
    """

    CAST = 0
    USE_MI = 1
    SQUEEZE = 2
    TALK = 3
    SAY = 4
    GIVE = 5
    FULFILL = 6
    STEAL = 7
    SHOOT = 8
    MELEE = 9
    FLEE = 10
    BEG = 11
    NONE = 12
    SCOUT = 13


# Phase 618: the Search Encounter Plan tactics followed by a sub-object
# token in the real ``Tac_Bytes`` list (``HostAK/TP/DEF2.PAS`` ``W_List``/
# ``R_List``) -- a spell/item/gift id for CAST/USE_MI/GIVE. ``SAY`` is
# deliberately excluded: its own argument is free text on its own
# line(s), not a token in this list at all (see ``turn/search_decode.py``
# ``SearchTactic.say_text`` and ``parser/k1_moves.py``'s own Phase 618
# addendum for how it's recovered instead). Defined here (not in
# ``turn/search_decode.py``, its only consumer before this phase) so
# ``parser/k1_moves.py`` -- a foundational file-format layer -- can share
# it without depending on `turn/`, a higher business-logic layer.
TACTICS_WITH_SUB_OBJECT = frozenset({Maneuver.CAST, Maneuver.USE_MI, Maneuver.GIVE})


def maneuver_from_int(value: int) -> "Maneuver | int":
    """Map a raw maneuver int to ``Maneuver`` where valid, else keep it raw."""

    try:
        return Maneuver(value)
    except ValueError:
        return value


class Spell(IntEnum):
    """Mirrors the Pascal ``spell`` enum (``CTBOTH.PAS`` lines 650-667).

    The 25 documented base spells (rulebook [4.21]-[4.25], ``RESURRECTION``
    = ordinal 0 through ``MIRROR_IMAGE`` = ordinal 24) are five per
    Magical ``Ability`` (White, Necromancy, Elemental, Psychic,
    Illusionist), packed as four contiguous "first four spells" blocks
    (ordinals 0-19, ability order White/Necromancy/Elemental/Psychic/
    Illusionist) followed by one "fifth spell" block (ordinals 20-24,
    same ability order) -- not five contiguous per-ability blocks.

    Ordinals 25-34 are 10 undocumented "secret" spells (``ADDEND.AK``
    [2.0]: "Secret special spells and capabilities are attainable at
    high levels of ability"), each gated behind a specific special
    ability granted at skill 5+ (``CTBOTH.PAS``'s ``spdex`` lookup
    table) -- confirmed to exist and be castable (via an encounter's
    ``Maneuver.CAST`` sub-object -- real example: ``AK3__T10.K1``
    leader 1's Special Plan casts spell 28, ``GATE_DEMON``), but never
    observed as a top-level ``ActionCode.CAST`` phase's ``obj`` in any
    of the 10 sample ``AK3__T*.K1`` files.

    Ordinal 35 is ``NOSPELL`` (a sentinel, never a real cast target).
    Ordinals 36-55 (``es1``..``es20`` in the Pascal source) are reserved/
    unused placeholder slots -- kept out of this enum entirely, since
    they're never observed anywhere and their very presence in the
    source looks unfinished (the Pascal display-name tables even list
    ``nospell`` *after* them, inconsistent with the type declaration's
    ordinal 35 -- flagged as a likely stale-table authoring artifact,
    not modeled here).
    """

    RESURRECTION = 0
    PART_SEA = 1
    BLESS = 2
    HOLY_SYMBOL = 3
    SKELETAL_ARMY = 4
    KILL_ENEMY = 5
    PLAGUE = 6
    HAND_OF_DEATH = 7
    FLOOD = 8
    TORNADO = 9
    EARTHQUAKE = 10
    FIREBALL = 11
    CHARM = 12
    ORATORY = 13
    CLAIRVOYANCE = 14
    PSYCHIC_BLAST = 15
    ILLUS_TERRAIN = 16
    ILLUS_ARMIES = 17
    HIDE_FEATURE = 18
    INVISIBILITY = 19
    SPIRITWRACK = 20
    CONTROL_UNDEAD = 21
    ICE_SUSPEND = 22
    TELEK_STORM = 23
    MIRROR_IMAGE = 24
    GATE_ANGEL = 25
    HEAL = 26
    SCAR_TERRAIN = 27
    GATE_DEMON = 28
    MYSTIC_WINDS = 29
    LAVA_POOL = 30
    LOCATE_OBJECT = 31
    AUGUR_COMBAT = 32
    ILLUS_FOG = 33
    ILLUS_HERO = 34
    NOSPELL = 35


# CTBOTH.PAS `spname` (~line 677), verbatim, positional with `Spell`'s own
# 35 real ordinals (0-34) -- confirmed real and actually used via
# RUMORS.PAS's own `Say(spname[_spell], spytype)`, matching PROSE.TXT's
# documented "~: Spell name" marker. `NOSPELL` (35) is deliberately
# excluded: `spname[35]` is `"Extra Spell 1"`, not `"No spell"` (which sits
# at the *end* of the table, index 55) -- the exact table-misalignment this
# class's own docstring already flagged ("the Pascal display-name tables
# even list nospell after [the unused es1-es20 slots], inconsistent with
# the type declaration's ordinal 35 -- a likely stale-table authoring
# artifact"), now confirmed directly rather than only inferred.
SPELL_NAME: dict[Spell, str] = {
    Spell.RESURRECTION: "Resurrection",
    Spell.PART_SEA: "Part Sea",
    Spell.BLESS: "Bless",
    Spell.HOLY_SYMBOL: "Holy Symbol",
    Spell.SKELETAL_ARMY: "Skeletal Army",
    Spell.KILL_ENEMY: "Kill Enemy",
    Spell.PLAGUE: "Plague",
    Spell.HAND_OF_DEATH: "Hand Of Death",
    Spell.FLOOD: "Flood",
    Spell.TORNADO: "Tornado",
    Spell.EARTHQUAKE: "Earthquake",
    Spell.FIREBALL: "Fireball",
    Spell.CHARM: "Charm",
    Spell.ORATORY: "Oratory",
    Spell.CLAIRVOYANCE: "Clairvoyance",
    Spell.PSYCHIC_BLAST: "Psychic Blast",
    Spell.ILLUS_TERRAIN: "Illusory Terrain",
    Spell.ILLUS_ARMIES: "Phantasmal Armies",
    Spell.HIDE_FEATURE: "Hide Feature",
    Spell.INVISIBILITY: "Invisibility",
    Spell.SPIRITWRACK: "Spiritwrack",
    Spell.CONTROL_UNDEAD: "Control Undead",
    Spell.ICE_SUSPEND: "Ice Suspension",
    Spell.TELEK_STORM: "Telekinetic Storm",
    Spell.MIRROR_IMAGE: "Mirror-Image Phantasm",
    Spell.GATE_ANGEL: "Gate Angel",
    Spell.HEAL: "Words of Healing",
    Spell.SCAR_TERRAIN: "Scar Terrain",
    Spell.GATE_DEMON: "Gate Demon",
    Spell.MYSTIC_WINDS: "Mystic Winds",
    Spell.LAVA_POOL: "Lava Pool",
    Spell.LOCATE_OBJECT: "Locate Object",
    Spell.AUGUR_COMBAT: "Augur Combat",
    Spell.ILLUS_FOG: "Illusory Fog",
    Spell.ILLUS_HERO: "Illusory Hero",
}


# CTBOTH.PAS `spab` (~lines 721-740), verbatim, positional with `Spell`'s
# own 35 real ordinals (0-34) -- the two-letter mnemonic `RUMORS.PAS
# Write_SEP` (~line 1019) writes after a `CA-` prefix when serializing an
# Encounter Plan's own Cast tactic (`WRITE(playfile,'-',spab[spell(...)])`),
# e.g. `CA-HA` = casting `HAND_OF_DEATH`. `NOSPELL` (35) is deliberately
# excluded, the same table-misalignment reason `SPELL_NAME`'s own docstring
# above already gives for excluding it there (`spab`'s own `'NS'` entry
# sits at index 55, after the 20 unused `es1`-`es20` extension-slot
# entries, not at index 35) -- never a real Cast target either way.
# Phase 178 -- built to decode Desktop/Piani speciali d'incontro dei
# mostri.txt's own `CA-XX` notation into `models/monster_encounter_plan.py
# MONSTER_ENCOUNTER_PLANS`.
SPELL_ABBREVIATION: dict[Spell, str] = {
    Spell.RESURRECTION: "RE",
    Spell.PART_SEA: "PA",
    Spell.BLESS: "BL",
    Spell.HOLY_SYMBOL: "HO",
    Spell.SKELETAL_ARMY: "SK",
    Spell.KILL_ENEMY: "KI",
    Spell.PLAGUE: "PL",
    Spell.HAND_OF_DEATH: "HA",
    Spell.FLOOD: "FL",
    Spell.TORNADO: "TO",
    Spell.EARTHQUAKE: "EA",
    Spell.FIREBALL: "FI",
    Spell.CHARM: "CH",
    Spell.ORATORY: "OR",
    Spell.CLAIRVOYANCE: "CL",
    Spell.PSYCHIC_BLAST: "PS",
    Spell.ILLUS_TERRAIN: "IL",
    Spell.ILLUS_ARMIES: "PH",
    Spell.HIDE_FEATURE: "HI",
    Spell.INVISIBILITY: "IN",
    Spell.SPIRITWRACK: "SP",
    Spell.CONTROL_UNDEAD: "CO",
    Spell.ICE_SUSPEND: "IC",
    Spell.TELEK_STORM: "TE",
    Spell.MIRROR_IMAGE: "MI",
    Spell.GATE_ANGEL: "GA",
    Spell.HEAL: "WH",
    Spell.SCAR_TERRAIN: "ST",
    Spell.GATE_DEMON: "GD",
    Spell.MYSTIC_WINDS: "MW",
    Spell.LAVA_POOL: "LP",
    Spell.LOCATE_OBJECT: "LO",
    Spell.AUGUR_COMBAT: "AC",
    Spell.ILLUS_FOG: "IF",
    Spell.ILLUS_HERO: "IH",
}

# Reverse lookup -- every value above is unique, so this inverts cleanly.
SPELL_BY_ABBREVIATION: dict[str, Spell] = {abbreviation: spell for spell, abbreviation in SPELL_ABBREVIATION.items()}


# HostAK/TP/SAY.PAS's `Sps(sp: spell; fam: integer)` (~line 241-242)
# dispatches `FD('c:\\tp\\prose\\spnote.x2', fam, 1001+ord(sp))` -- a
# deterministic `dex >= 1000` index directly on `Spell`'s own ordinal,
# the same confirmed-strongest evidence tier `MAGFEAT.X2`/`MCOND.X2`/
# `IONAME.X2` already established. `SPNOTE.X2` (header `"25 1"`) has
# exactly 25 real templates, matching `Spell`'s own 25 documented base
# spells (`RESURRECTION` = ordinal 0 through `MIRROR_IMAGE` = ordinal
# 24, see this class's own docstring) with a gapless, individually
# content-confirmed 1:1 positional match for every single entry (e.g.
# index 0 mentions being "resurrected", index 22 forms "a shell of ice"
# around the target for `ICE_SUSPEND`, index 24 mentions "a second
# image" for `MIRROR_IMAGE`). Ordinals 25-34 (the 10 undocumented
# "secret" spells) have no entry here -- `SPNOTE.X2` itself stops at 25.
#
# Many entries are real continuation clauses (leading space/comma/
# period, no capital first letter), meant to follow `_LCast1`'s own
# opening ("< cast a ~ spell." for `TORNADO`/`BLESS`/`PLAGUE`, "< cast
# a ~ spell and " for every other spell, see `CAST_SPELL_OPENING_*`
# below) -- documented here as the apparent intended relationship
# (`Say(...)` calls write sequentially with no separator, the same
# concatenation shape this project has confirmed many times), not
# force-composed into a single verified sentence for all 25 cases: the
# `CONTROL_UNDEAD` entry itself is genuinely truncated in the source
# (ends mid-word, "...mercilessly and_", no further text anywhere in
# the file), so no wrapper function asserts a always-grammatical
# combined render. Raw templates only; the caller composes.
SPELL_CAST_ANNOUNCEMENT: dict[Spell, str] = {
    Spell.RESURRECTION: "[1 was resurrected by the spell cast by <2.",
    Spell.PART_SEA: "the waters of @ were magically parted.",
    Spell.BLESS: "@ was magically blessed and prospered.",
    Spell.HOLY_SYMBOL: ".A golden mist in the shape of a cross formed around <2.",
    Spell.SKELETAL_ARMY: "^L= arose from the graves of the dead!",
    Spell.KILL_ENEMY: "[1 was magically killed by a dark Necromantic spell!",
    Spell.PLAGUE: "the plague struck ^L= in @ and destroyed them.",
    Spell.HAND_OF_DEATH: " and began making squeezing motions with > hands.",
    Spell.FLOOD: "the Flood slowed ^L= in @, causing them to lose one movement point.",
    Spell.TORNADO: "tornadoes sucked up ^L= in @ and destroyed them.",
    Spell.EARTHQUAKE: "@ was devastated by an earthquake!",
    Spell.FIREBALL: ", which proved useless in the underwater environs of the &.",
    Spell.CHARM: ".< befriended/Rcharmed [ and used > respite/Rgood_luck to escape/Rget_away.",
    Spell.ORATORY: "< cast a spell giving magical powers of oratory to [.",
    Spell.CLAIRVOYANCE: "< cast a ~ spell and could see everything that happened to [.",
    Spell.PSYCHIC_BLAST: ", projecting psychic waves of stunning force towards [.",
    Spell.ILLUS_TERRAIN: "@ had an illusion cast upon it.It was actually a ` province.",
    Spell.ILLUS_ARMIES: "illusory armies were formed for [.",
    Spell.HIDE_FEATURE: "the & in @ was magically hidden.",
    Spell.INVISIBILITY: ", fading into invisibility.",
    Spell.SPIRITWRACK: ", to make [1 quake and shiver with spiritual convulsions.",
    Spell.CONTROL_UNDEAD: (
        ", and brought [ under > control.< used > control to attack [ mercilessly and_"
    ),
    Spell.ICE_SUSPEND: ", and a shell/Rcrust of {frigid }ice formed/Rthickened around [.",
    Spell.TELEK_STORM: ", which proved useless in the underwater environs of the &.",
    Spell.MIRROR_IMAGE: " and an/Ra_second image/Rillusion of [ sprang/Rflashed into existence/Rbeing!",
}


# HostAK/TP/SAY.PAS _LCast1 (~lines 599-602): the opening clause
# SPELL_CAST_ANNOUNCEMENT's own entries are meant to follow (see its
# comment above). Two real, hardcoded variants (no file).
CAST_SPELL_OPENING_COMPLETE_TEMPLATE = "< cast a ~ spell."
CAST_SPELL_OPENING_CONTINUED_TEMPLATE = "< cast a ~ spell and "
# The 3 spells whose own SPNOTE.X2 entry is a separate sentence rather
# than a continuation of "...spell and " -- CASE Tornado,Bless,Plague
# in _LCast1's own source.
CAST_SPELL_OPENING_COMPLETE_SPELLS = frozenset({Spell.TORNADO, Spell.BLESS, Spell.PLAGUE})


class SpellLegalityClass(IntEnum):
    """Phase 395: the `splate` table, a second, *hidden* classification
    the AKGEN binary carries for each of the 35 real spells -- never
    shown to players, and confirmed by the source's own Pascal comment:
    "0 sempre legale; 1 illegale solo sulla terra di un altro giocatore;
    2 illegale solo sul personaggio di un altro giocatore; 3 illegale"
    (0 always legal; 1 illegal only on another player's land; 2 illegal
    only on another player's character; 3 illegal).

    **This is a moderatorial/late-move review classification, not a
    live effect-engine block** -- AKGEN's own text is explicit: "È una
    classificazione del controllo moderatoriale/late-move, non un
    divieto assoluto del motore d'effetto." It flags which casts a
    human moderator's late-move review tooling needs to check before
    letting a submitted turn process, not a rule the running game
    engine itself enforces at cast time. `ak_engine` reimplements the
    turn engine, not the PBM moderator's administrative front-end (the
    same "GM admin menu" scope line already drawn for `Approve`/`Find
    Account`/`Status Sheet`/`Transmit World` and the rest of the main
    menu, `## Menu principale ricostruito` in the AKGEN report) -- so
    `SPELL_LEGALITY_CLASS` below is captured as real, sourced vocabulary
    data, deliberately **not** wired into any live legality check in
    `turn/cast_execution.py` or `turn/cast_decode.py`: there is no
    engine-side rule to wire it into.
    """

    ALWAYS_LEGAL = 0
    ILLEGAL_ON_ANOTHER_PLAYERS_LAND = 1
    ILLEGAL_ON_ANOTHER_PLAYERS_CHARACTER = 2
    ILLEGAL = 3


# AKGEN report's own `splate` table (see `SpellLegalityClass`'s own
# docstring), all 35 real spells classified -- `NOSPELL` (35) excluded,
# same "sentinel, never a real cast target" reasoning `Spell`'s own
# docstring already gives for leaving it out of tables like this one.
SPELL_LEGALITY_CLASS: dict[Spell, SpellLegalityClass] = {
    Spell.RESURRECTION: SpellLegalityClass.ALWAYS_LEGAL,
    Spell.PART_SEA: SpellLegalityClass.ILLEGAL_ON_ANOTHER_PLAYERS_LAND,
    Spell.BLESS: SpellLegalityClass.ILLEGAL_ON_ANOTHER_PLAYERS_LAND,
    Spell.HOLY_SYMBOL: SpellLegalityClass.ALWAYS_LEGAL,
    Spell.SKELETAL_ARMY: SpellLegalityClass.ILLEGAL_ON_ANOTHER_PLAYERS_LAND,
    Spell.KILL_ENEMY: SpellLegalityClass.ILLEGAL_ON_ANOTHER_PLAYERS_CHARACTER,
    Spell.PLAGUE: SpellLegalityClass.ILLEGAL,
    Spell.HAND_OF_DEATH: SpellLegalityClass.ALWAYS_LEGAL,
    Spell.FLOOD: SpellLegalityClass.ILLEGAL,
    Spell.TORNADO: SpellLegalityClass.ILLEGAL_ON_ANOTHER_PLAYERS_LAND,
    Spell.EARTHQUAKE: SpellLegalityClass.ILLEGAL,
    Spell.FIREBALL: SpellLegalityClass.ALWAYS_LEGAL,
    Spell.CHARM: SpellLegalityClass.ILLEGAL_ON_ANOTHER_PLAYERS_CHARACTER,
    Spell.ORATORY: SpellLegalityClass.ILLEGAL_ON_ANOTHER_PLAYERS_CHARACTER,
    Spell.CLAIRVOYANCE: SpellLegalityClass.ILLEGAL,
    Spell.PSYCHIC_BLAST: SpellLegalityClass.ALWAYS_LEGAL,
    Spell.ILLUS_TERRAIN: SpellLegalityClass.ILLEGAL,
    Spell.ILLUS_ARMIES: SpellLegalityClass.ILLEGAL_ON_ANOTHER_PLAYERS_CHARACTER,
    Spell.HIDE_FEATURE: SpellLegalityClass.ALWAYS_LEGAL,
    Spell.INVISIBILITY: SpellLegalityClass.ALWAYS_LEGAL,
    Spell.SPIRITWRACK: SpellLegalityClass.ALWAYS_LEGAL,
    Spell.CONTROL_UNDEAD: SpellLegalityClass.ALWAYS_LEGAL,
    Spell.ICE_SUSPEND: SpellLegalityClass.ALWAYS_LEGAL,
    Spell.TELEK_STORM: SpellLegalityClass.ALWAYS_LEGAL,
    Spell.MIRROR_IMAGE: SpellLegalityClass.ALWAYS_LEGAL,
    Spell.GATE_ANGEL: SpellLegalityClass.ILLEGAL,
    Spell.HEAL: SpellLegalityClass.ALWAYS_LEGAL,
    Spell.SCAR_TERRAIN: SpellLegalityClass.ILLEGAL_ON_ANOTHER_PLAYERS_LAND,
    Spell.GATE_DEMON: SpellLegalityClass.ALWAYS_LEGAL,
    Spell.MYSTIC_WINDS: SpellLegalityClass.ILLEGAL_ON_ANOTHER_PLAYERS_CHARACTER,
    Spell.LAVA_POOL: SpellLegalityClass.ALWAYS_LEGAL,
    Spell.LOCATE_OBJECT: SpellLegalityClass.ALWAYS_LEGAL,
    Spell.AUGUR_COMBAT: SpellLegalityClass.ALWAYS_LEGAL,
    Spell.ILLUS_FOG: SpellLegalityClass.ALWAYS_LEGAL,
    Spell.ILLUS_HERO: SpellLegalityClass.ALWAYS_LEGAL,
}


def spell_from_int(value: int) -> "Spell | int":
    """Map a raw spell int to ``Spell`` where valid, else keep it raw."""

    try:
        return Spell(value)
    except ValueError:
        return value
