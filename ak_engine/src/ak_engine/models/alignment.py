"""Kingdom/monster alignment, transcribed from the tags used in `Mostri.md`
(Anti-Holy, Evil, Pagan, Good, Neutral, Divine, Druid) in the parent
project's game-design docs.

This is a minimal enum -- just enough to support the rulebook's
fanaticism formula (`turn/strength.py roll_fanaticism`). A full kingdom
alignment model (multi-tag combinations, alignment shifts, diplomacy
effects) is a separate, much larger system this project hasn't built.
"""

from __future__ import annotations

from enum import Enum


class Alignment(Enum):
    DIVINE = "Divine"
    GOOD = "Good"
    NEUTRAL = "Neutral"
    EVIL = "Evil"
    ANTI_HOLY = "Anti-Holy"
    PAGAN = "Pagan"
    DRUID = "Druid"
