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
