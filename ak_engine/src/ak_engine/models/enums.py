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


def spell_from_int(value: int) -> "Spell | int":
    """Map a raw spell int to ``Spell`` where valid, else keep it raw."""

    try:
        return Spell(value)
    except ValueError:
        return value
