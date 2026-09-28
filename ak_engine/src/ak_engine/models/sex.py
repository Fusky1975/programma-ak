"""Character sex (Pascal `M/F`) -- Phase 260.

`REPORTS.PAS`'s own CHARACTERS-section column header (`models/enums.py
ABILITY_ABBREVIATION`'s own docstring quotes it in full) includes
`M/F` -- confirmed present in the real Pascal character record, but
never modeled in this project until now: `models/valhalla.py`'s own
Phase 195 docstring and `report/turn_report.py`'s own Phase 217/230
docstrings both explicitly flagged it "confirmed absent... no field
exists anywhere in this project; nothing computes or stores it,"
deliberately not guessed at for lack of a real consumer.

Phase 260's own King-creation mechanic is the first real writer:
RULES.AK [2.1] "Kings" says the player assigns "the King's name, race,
temper, alignment and four ability levels" at creation -- sex is not
listed in that specific sentence, but is confirmed directly with the
user (project author, drawing on first-hand game knowledge) as also
chosen at creation, alongside name and temperament, for a King created
via a Royal Heir succession (`turn/succession.py create_king()`).

**Phase 635**: `report/turn_report.py describe_characters_report()`'s
own real "M/F" column (`REPORTS.PAS`'s CHARACTERS-section header,
quoted above) now reads this field -- correcting that composer's own
Phase 432 claim that "no `Gender()` concept or field exists anywhere in
this project," stale even when written (Phase 260 predates Phase 432).
~~Blank for any leader whose own `sex` was never set (i.e. everyone but a
succession-created King)~~ -- **incomplete even at the time this was
written**: `parser/gw_world_bridge.py bridge_new_game_state()`'s own
Phase 339 addendum (chronologically earlier than this Phase 635 note)
is a second, real writer -- a roster-matched Hero (`STANDARD_HERO_
SEX_BY_NAME`, keyed by name) gets `sex` set directly when a `GameState`
is bridged from a real world file, not just a succession-created King.
Blank only for a leader covered by neither writer (an ordinary,
non-roster-matched Hero, or any leader in a hand-built `GameState` never
bridged from a real file) -- see `describe_characters_report()`'s own
Phase 635 addendum for why a *third* real Gender source, `parser/
gw_world.py GWKingExtension.is_male` (a King's own real save-file
Gender byte), stays deliberately unbridged into this field for now.
"""

from __future__ import annotations

from enum import Enum


class Sex(Enum):
    MALE = "M"
    FEMALE = "F"
