"""Race enum, transcribed from ``HostAK/TP/CTBOTH.PAS`` (``race`` type, line 573).

``HUMANOID_RACES`` matches the rulebook's explicit definition (``RULES.AK``
[3.4]): "humanoids being men, elves, orcs and dwarves."
"""

from __future__ import annotations

from enum import Enum


class Race(Enum):
    HUMAN = 0
    ELVEN = 1
    DWARVEN = 2
    ORCISH = 3
    DRAGONS = 4
    EAGLES = 5
    WHALES = 6
    NO_RACE = 7
    MERMISH = 8
    ENTISH = 9
    TROLLISH = 10
    WEREFOLK = 11
    SAURIAN = 12
    VAMPISH = 13
    ROHAN = 14


HUMANOID_RACES = frozenset({Race.HUMAN, Race.ELVEN, Race.DWARVEN, Race.ORCISH})
