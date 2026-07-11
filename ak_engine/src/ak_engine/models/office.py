"""Kingdom/King "office" (achievement-based rank/title) model.

``HostAK/TP/CTBOTH.PAS``'s `office` enum (~line 249-260, 52 members)
and its four parallel tables -- `ofcname` (real display strings),
`minpts`/`ofcval`/`ofcuse` (all `{$IFDEF Moderator}`, world/scoring-
side only) -- found while continuing to mine `CTBOTH.PAS` for real,
sourced data not yet transcribed, the same way Phase 79
(`MONSTER_GUARDED_FEATURE_TYPES`) and Phase 80 (`Alignment`'s real
source) were found.

**Confirmed to be `PROSE.TXT`'s own documented "$O" marker**: "$O:
Office name ('World Emperor', 'Arch-Mage Palatine', etc.)" -- both
example strings PROSE.TXT itself gives are verbatim `ofcname` entries
here (`Office.EMPEROR` and `Office.MAGE` respectively), not just a
plausible-sounding match.

**A ruled-out red herring, found while researching this**: a second,
much smaller `office` enum (`Pope, Caliph, Shaman, Emperor, King, Duke,
Prince, Notitle`) appears at `CTBOTH.PAS` ~line 1741, immediately after
a comment banner reading `"****Not implemented yet:"` -- dead,
never-compiled placeholder code, not a real alternate definition. This
project's own `models/kingdom.py Kingdom.king_title` (a move file's own
free-text king-title line, e.g. "Shaman" in the real `AK3__T1.K1`
sample) is **not** connected to either `office` enum -- confirmed by
checking whether "Shaman" (or any real sample's own king-title text)
appears in the real, active 52-member `ofcname` list below; it doesn't.
`king_title` remains exactly what Phase 1 already documented it as: an
unparsed, unvalidated free-text field.

**Confirmed real usage** (`REPORTS.PAS` ~line 624-632, the only place
in the available source that reads these tables): for each `office`
except `NO_OFFICE`, gated by `ofcuse[office]` (an eligibility flag,
"is this office usable under the current game-version rules") unless
`gamevers >= 4`, a kingdom's accumulated points for that office
(`Ofc_Pts(...)`, not available in this project's source -- lives in
the missing main program) are compared against `minpts[office]` --
meeting the threshold and ranking #1 among all kingdoms for that
office (`Rank(...) = 1`) is what earns the King the right to display
that office's own name in his turn report, printed via the
`ioname.x2` prose file (``FD('c:\\tp\\prose\\ioname.x2', ..., 1001+ord(
office))``). `ofcval[office]` feeds a separate points-decay formula
(`ofcpoints[ofc] := ofcval[ofc] * (1.0 - reduct)`) whose own `reduct`
term isn't traced further here.

**Explicitly out of scope**: the actual points-accumulation formula
(`Ofc_Pts`) and cross-kingdom ranking (`Rank`) live in the missing main
program, so nothing in this module can compute which office a real
`KingdomState` currently holds -- this is a type/threshold catalog
only, the same category of "real, sourced, but not a complete
algorithm" as Phase 79's `MONSTER_GUARDED_FEATURE_TYPES`.
"""

from __future__ import annotations

from enum import Enum


class Office(Enum):
    EMPEROR = 0
    CHANCELLOR = 1
    TREASURER = 2
    MARSHAL = 3
    ADMIRAL = 4
    DEFENDER = 5
    PRIEST = 6
    MAGE = 7
    NO_OFFICE = 8
    HUMAN_KING = 9
    ELVEN_KING = 10
    DWARVEN_KING = 11
    ORC_LORD = 12
    DRAGON_LORD = 13
    EAGLE_KING = 14
    WHALE_KING = 15
    ELE_MAGE = 16
    MERMAN_KING = 17
    ENT_KING = 18
    TROLL_KING = 19
    WERE_KING = 20
    ILLUS_MAGE = 21
    DIVINE_KING = 22
    GOOD_KING = 23
    DRUID_KING = 24
    NEUTRAL_KING = 25
    PAGAN_KING = 26
    EVIL_KING = 27
    NECRO_MAGE = 28
    UNDEAD_KING = 29
    PLAINS_KING = 30
    DESERT_KING = 31
    JUNGLE_KING = 32
    FOREST_KING = 33
    MOUNTAIN_KING = 34
    SEA_KING = 35
    THIEF_PRINCE = 36
    BATTLE_FOOL = 37
    AIR_FORCE = 38
    CHIEF_OF_STAFF = 39
    CURATOR = 40
    DIPLOMAT = 41
    TEACHER = 42
    ASSASSIN = 43
    DUELLIST = 44
    PRAETOR = 45
    PSYCHIC_MAGE = 46
    FLAGSHIP = 47
    WINGMAN = 48
    CRAVENEST = 49
    BRAVEST = 50
    NO_TITLE = 51


# CTBOTH.PAS `ofcname`, verbatim, positional with the `Office` ordinals above.
OFFICE_NAME: dict[Office, str] = {
    Office.EMPEROR: "World Emperor",
    Office.CHANCELLOR: "Esteemed High Chancellor",
    Office.TREASURER: "Imperial Treasurer",
    Office.MARSHAL: "Imperial Grand Marshal",
    Office.ADMIRAL: "Imperial Grand Admiral",
    Office.DEFENDER: "Lord High Defender",
    Office.PRIEST: "High Priest Palatine",
    Office.MAGE: "Arch-Mage Palatine",
    Office.NO_OFFICE: "no office",
    Office.HUMAN_KING: "Savior of Humankind",
    Office.ELVEN_KING: "First Elder of Elvenkind",
    Office.DWARVEN_KING: "King Under the Mountain",
    Office.ORC_LORD: "Khan of the Orcish Hordes",
    Office.DRAGON_LORD: "Dragon Lord",
    Office.EAGLE_KING: "Ace of Eagles",
    Office.WHALE_KING: "Whale League Commissioner",
    Office.ELE_MAGE: "Master of Elements",
    Office.MERMAN_KING: "King of Atlantis",
    Office.ENT_KING: "Tsar of the Trees",
    Office.TROLL_KING: "High Mucky-Muck of Trolls",
    Office.WERE_KING: "Lord of Lycanthropes",
    Office.ILLUS_MAGE: "Amazing Houdini",
    Office.DIVINE_KING: "Divine Archangel",
    Office.GOOD_KING: "Most Blessed of Kings",
    Office.DRUID_KING: "Great Druid of Life",
    Office.NEUTRAL_KING: "Defender of Freedom",
    Office.PAGAN_KING: "Warlock of the Pagan Gods",
    Office.EVIL_KING: "King of Pain",
    Office.NECRO_MAGE: "Sorceror of Black Magic",
    Office.UNDEAD_KING: "Angel of Death",
    Office.PLAINS_KING: "Ranger of the Plains",
    Office.DESERT_KING: "Desert Rat",
    Office.JUNGLE_KING: "Lord of the Jungle",
    Office.FOREST_KING: "Warden of the Forests",
    Office.MOUNTAIN_KING: "Mountain Man",
    Office.SEA_KING: "Ruler of the Waves",
    Office.THIEF_PRINCE: "Prince of Thieves",
    Office.BATTLE_FOOL: "Fool of Battles",
    Office.AIR_FORCE: "Royal Air Force",
    Office.CHIEF_OF_STAFF: "Chief of Staff",
    Office.CURATOR: "Curator of Artifacts",
    Office.DIPLOMAT: "Silver Tongue",
    Office.TEACHER: "Professor Whizdumb",
    Office.ASSASSIN: "Grandfather of Assassins",
    Office.DUELLIST: "Captain of the Musketeers",
    Office.PRAETOR: "Praetorian Guard",
    Office.PSYCHIC_MAGE: "Master Mind",
    Office.FLAGSHIP: "Imperial Flag Squadron",
    Office.WINGMAN: "Air Force Commander",
    Office.CRAVENEST: "King of Cowards",
    Office.BRAVEST: "Bravest of the Brave",
    Office.NO_TITLE: "no title",
}

# CTBOTH.PAS `minpts` -- the minimum accumulated points needed to hold this
# office (see module docstring for the full "Ofc_Pts >= minpts and Rank = 1"
# check this feeds, in REPORTS.PAS).
OFFICE_MIN_POINTS: dict[Office, int] = {
    Office.EMPEROR: 1,
    Office.CHANCELLOR: 1,
    Office.TREASURER: 1,
    Office.MARSHAL: 1,
    Office.ADMIRAL: 1,
    Office.DEFENDER: 1,
    Office.PRIEST: 1,
    Office.MAGE: 1,
    Office.NO_OFFICE: 0,
    Office.HUMAN_KING: 15,
    Office.ELVEN_KING: 10,
    Office.DWARVEN_KING: 10,
    Office.ORC_LORD: 10,
    Office.DRAGON_LORD: 6,
    Office.EAGLE_KING: 6,
    Office.WHALE_KING: 4,
    Office.ELE_MAGE: 20,
    Office.MERMAN_KING: 4,
    Office.ENT_KING: 4,
    Office.TROLL_KING: 4,
    Office.WERE_KING: 4,
    Office.ILLUS_MAGE: 20,
    Office.DIVINE_KING: 25,
    Office.GOOD_KING: 25,
    Office.DRUID_KING: 25,
    Office.NEUTRAL_KING: 25,
    Office.PAGAN_KING: 25,
    Office.EVIL_KING: 25,
    Office.NECRO_MAGE: 20,
    Office.UNDEAD_KING: 25,
    Office.PLAINS_KING: 4,
    Office.DESERT_KING: 4,
    Office.JUNGLE_KING: 4,
    Office.FOREST_KING: 4,
    Office.MOUNTAIN_KING: 4,
    Office.SEA_KING: 2,
    Office.THIEF_PRINCE: 2,
    Office.BATTLE_FOOL: 2,
    Office.AIR_FORCE: 1,
    Office.CHIEF_OF_STAFF: 7,
    Office.CURATOR: 3,
    Office.DIPLOMAT: 50,
    Office.TEACHER: 5,
    Office.ASSASSIN: 2,
    Office.DUELLIST: 5,
    Office.PRAETOR: 1,
    Office.PSYCHIC_MAGE: 20,
    Office.FLAGSHIP: 1,
    Office.WINGMAN: 5,
    Office.CRAVENEST: 5,
    Office.BRAVEST: 15,
    Office.NO_TITLE: 0,
}

# CTBOTH.PAS `ofcval` -- feeds a separate points-decay formula this project
# hasn't traced further (see module docstring).
OFFICE_VALUE: dict[Office, int] = {
    Office.EMPEROR: 20,
    Office.CHANCELLOR: 10,
    Office.TREASURER: 10,
    Office.MARSHAL: 10,
    Office.ADMIRAL: 10,
    Office.DEFENDER: 10,
    Office.PRIEST: 10,
    Office.MAGE: 10,
    Office.NO_OFFICE: 0,
    Office.HUMAN_KING: 4,
    Office.ELVEN_KING: 3,
    Office.DWARVEN_KING: 3,
    Office.ORC_LORD: 3,
    Office.DRAGON_LORD: 2,
    Office.EAGLE_KING: 2,
    Office.WHALE_KING: 2,
    Office.ELE_MAGE: 2,
    Office.MERMAN_KING: 2,
    Office.ENT_KING: 2,
    Office.TROLL_KING: 2,
    Office.WERE_KING: 2,
    Office.ILLUS_MAGE: 2,
    Office.DIVINE_KING: 3,
    Office.GOOD_KING: 4,
    Office.DRUID_KING: 4,
    Office.NEUTRAL_KING: 4,
    Office.PAGAN_KING: 4,
    Office.EVIL_KING: 4,
    Office.NECRO_MAGE: 2,
    Office.UNDEAD_KING: 3,
    Office.PLAINS_KING: 2,
    Office.DESERT_KING: 2,
    Office.JUNGLE_KING: 2,
    Office.FOREST_KING: 2,
    Office.MOUNTAIN_KING: 2,
    Office.SEA_KING: 2,
    Office.THIEF_PRINCE: 2,
    Office.BATTLE_FOOL: 1,
    Office.AIR_FORCE: 2,
    Office.CHIEF_OF_STAFF: 2,
    Office.CURATOR: 2,
    Office.DIPLOMAT: 2,
    Office.TEACHER: 2,
    Office.ASSASSIN: 2,
    Office.DUELLIST: 2,
    Office.PRAETOR: 2,
    Office.PSYCHIC_MAGE: 2,
    Office.FLAGSHIP: 2,
    Office.WINGMAN: 3,
    Office.CRAVENEST: 1,
    Office.BRAVEST: 2,
    Office.NO_TITLE: 0,
}

# CTBOTH.PAS `ofcuse` -- whether this office is usable under the current
# game-version rules (`(gamevers >= 4) or ofcuse[office]` gates each check
# in REPORTS.PAS; see module docstring).
OFFICE_ENABLED_BY_DEFAULT: dict[Office, bool] = {
    Office.EMPEROR: True,
    Office.CHANCELLOR: True,
    Office.TREASURER: True,
    Office.MARSHAL: True,
    Office.ADMIRAL: True,
    Office.DEFENDER: True,
    Office.PRIEST: True,
    Office.MAGE: True,
    Office.NO_OFFICE: False,
    Office.HUMAN_KING: True,
    Office.ELVEN_KING: True,
    Office.DWARVEN_KING: True,
    Office.ORC_LORD: True,
    Office.DRAGON_LORD: True,
    Office.EAGLE_KING: True,
    Office.WHALE_KING: True,
    Office.ELE_MAGE: True,
    Office.MERMAN_KING: True,
    Office.ENT_KING: True,
    Office.TROLL_KING: True,
    Office.WERE_KING: True,
    Office.ILLUS_MAGE: False,
    Office.DIVINE_KING: True,
    Office.GOOD_KING: True,
    Office.DRUID_KING: True,
    Office.NEUTRAL_KING: True,
    Office.PAGAN_KING: True,
    Office.EVIL_KING: True,
    Office.NECRO_MAGE: False,
    Office.UNDEAD_KING: True,
    Office.PLAINS_KING: False,
    Office.DESERT_KING: False,
    Office.JUNGLE_KING: False,
    Office.FOREST_KING: False,
    Office.MOUNTAIN_KING: False,
    Office.SEA_KING: False,
    Office.THIEF_PRINCE: True,
    Office.BATTLE_FOOL: False,
    Office.AIR_FORCE: True,
    Office.CHIEF_OF_STAFF: False,
    Office.CURATOR: True,
    Office.DIPLOMAT: False,
    Office.TEACHER: False,
    Office.ASSASSIN: False,
    Office.DUELLIST: False,
    Office.PRAETOR: True,
    Office.PSYCHIC_MAGE: False,
    Office.FLAGSHIP: True,
    Office.WINGMAN: False,
    Office.CRAVENEST: True,
    Office.BRAVEST: True,
    Office.NO_TITLE: False,
}
