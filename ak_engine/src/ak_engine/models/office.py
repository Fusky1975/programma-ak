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

**Explicitly out of scope for this module**: the actual points-
accumulation formula (`Ofc_Pts`) and cross-kingdom ranking (`Rank`)
live in the missing main program, so nothing in *this file* computes
which office a real `KingdomState` currently holds -- it's a
type/threshold catalog only, the same category of "real, sourced, but
not a complete algorithm" as Phase 79's `MONSTER_GUARDED_FEATURE_TYPES`.
**Phase 650 addendum**: at the project level this is closed --
`turn/office_holder.py` (Phase 230+) independently reimplements the
real Rank contest (Merit Points per leader, compared against this
module's own `OFFICE_MIN_POINTS`, ties broken via `turn/merit_
points.py merit_point_tiebreak_key()`) and resolves who currently
holds each office. `resolve_office_holder()`/`resolve_all_office_
holders()` are the real answer to "which office does a Kingdom hold
right now" -- this module just supplies the threshold/name data those
functions consume.

**`GANG_TEMPLATE` (Phase 102)**: `HostAK/TP/PROSE/GANG.X2` (header
`"28 1"`), confirmed real via `SAY.PAS`'s own `Check_BFace` procedure,
the `_ATFan` branch: `FD('...gang.x2',S_Batt,1001+Rint-ord(Divineking))`
-- a title-based fanaticism narrative, sibling to `models/race.py
RACE_FANATICISM_TITLE`'s own race-based variant (both are branches of
the same `Check_BFace CASE` this project's own Phase 100 docstring
already quotes). The index is an `Office` offset counted *from*
`DIVINE_KING`, not a separate enum -- confirmed real content sits at
exactly `DIVINE_KING` (offset 0), `GOOD_KING` (1), `DRUID_KING` (2),
`NEUTRAL_KING` (3), `PAGAN_KING` (4), `EVIL_KING` (5), `NECRO_MAGE`
(6, blank -- not an alignment "king" title), `UNDEAD_KING` (7), and one
isolated entry far later at `DUELLIST` (offset 22, "Imperial
Musketeers") -- every single one of these 9 positions independently
confirms the exact `Office` ordinal arithmetic, since each entry's own
content matches its computed title exactly (e.g. offset 4 explicitly
names "the League of Pagan Clerics", offset 22 lands precisely on
`DUELLIST` and reads "Imperial Musketeers"). Only these 9 confirmed
entries are transcribed -- the large stretch between `UNDEAD_KING` and
`DUELLIST` (`PLAINS_KING` through `ASSASSIN`) is blank in the source
file too, but isn't included here as explicit empty-string entries,
unlike `RACE_FANATICISM_TITLE`'s own `NO_RACE`/`SAURIAN`: those two were
flanked immediately on both sides by real content within a short,
fully-populated 13-entry range, while this stretch is 14 slots of
unbroken blank space with no confirming context either side -- likely
simply unfinished/unused content in the original file, not a
confirmed "no text" design fact worth asserting.

**`OFFICE_PERK_DESCRIPTION` (Phase 103)**: `HostAK/TP/PROSE/IONAME.X2`
(header `"60 1"`, 52 real content lines) -- the exact file this module's
own pre-existing docstring already cited (`FD('...ioname.x2', ...,
1001+ord(office))`), now actually transcribed. Unlike `GANG_TEMPLATE`,
this file has **full, gapless 1:1 coverage of all 52 `Office`
members** -- only `NO_OFFICE`/`NO_TITLE` are blank, exactly the two
sentinel members with no real title at all.

Every entry reads `"TITLE: perk description"`. The title half is a
near-duplicate of `OFFICE_NAME` (same text, different casing --
`"WORLD EMPEROR"` here vs. `"World Emperor"` there), so only the perk
half -- the genuinely new information, a specific mechanical benefit
holding that office grants -- is modeled, as `OFFICE_PERK_DESCRIPTION`.
The title half also cross-confirms two other already-transcribed tables
at every one of their own populated positions: `models/race.py
RACE_FANATICISM_TITLE`'s race-king titles appear here verbatim
(`"SAVIOR OF HUMANKIND"`, `"FIRST ELDER OF ELVENKIND"`, `"KING UNDER
THE MOUNTAIN"`, ...), and `GANG_TEMPLATE`'s own alignment-king titles do
too (`"DIVINE ARCHANGEL"`/Thunderbird, `"MOST BLESSED OF GOOD
KINGS"`/Knights Hospitaller, `"CAPTAIN OF THE IMPERIAL
MUSKETEERS"`/`DUELLIST`) -- independent confirmation that both of those
phases' own `Office` positional mappings were correct.

`Office.NECRO_MAGE` has real content here (`"Imp Familiar, 25% Magic
Resistance"`) despite being the one blank gap inside `GANG_TEMPLATE`'s
own confirmed range -- no contradiction: `GANG.X2` is a separate,
sparser file specific to `Check_BFace`'s alignment-title fanaticism
narrative, and simply has nothing at that one position, while
`NECRO_MAGE` is a perfectly real `Office` with its own real perk here.

**Phase 137 research -- "who holds each office each turn" is a
confirmed, permanent dead end, not merely unattempted.**
``REPORTS.PAS``'s ``Ofc_Pts``/``Rank`` (~lines 1128-1250) is the real
per-turn scoring formula deciding office-holders (a King's own
Emperor/Chancellor/Treasurer/Priest/Mage/etc. points, with a
deterministic gold/tax-base/leader-index tie-break in ``Rank``) --
found while sweeping ``DEF2.PAS``/``REPORTS.PAS`` for further
unmodeled mechanics, per the user's own request. Unlike every other
formula recovered in that sweep, this one cannot be built: nearly
every office's own points formula reads at least one of
``lgenp``/``ladmp``/``lmhpp``/``lwmsp``/``oops``/``tipts``/``seatax``/
``alltax``/``lfdisc``/``ldiscp`` -- confirmed, by an exhaustive grep of
all 14 available ``.PAS`` files, to be **declared nowhere in the
archive**, only ever read/written from ``REPORTS.PAS``/``DEF2.PAS``
themselves. Their true declarations live in the same missing
compiled-only ``mboth``/``defines`` units already responsible for
``spabord``'s lost data (Phase 131) and ``Agent_Align``'s missing
source (Phase 136) -- except here it's eight-plus distinct per-leader
statistics simultaneously, not one. A handful of individual formula
terms *are* independently derivable (`M_Skill` from
``LeaderState.skills``; ``Treasurer``'s ``lgold[ldran]`` is plausibly
just that King's own ``KingdomState.treasury``) -- but building only
the 1-2 offices whose formulas happen to avoid the missing arrays,
while silently ignoring that the other 13+ offices remain permanently
unimplementable, would misrepresent partial coverage as a real office-
holder system. Recorded here, deliberately not implemented, so a
future sweep doesn't re-open this dead end.

**Phase 227 update -- the dead end above is specifically about the
missing *Pascal* globals; it is no longer the last word on the Merit
Point formulas themselves.** The user supplied the rulebook's own
printed "TABELLA DELLE CARICHE IMPERIALI" (page 51) -- a different, real
source describing the same 8 formulas in the game's own official terms,
not a Pascal transcription. `turn/merit_points.py` builds all 8 from it
directly; see that module's own docstring for exactly which terms are
live now (skills, treasury, Tax_Base, owned items) versus which still
need cumulative game-long tracking this project has never had (per-leader
battle outcomes, monster kills, successful Resurrection/Bless casts,
discovery-first attribution) via the new `LeaderState.merit_tally`
(`MeritTally`, `models/game_state.py`).

**`OFFICE_TITLE_DESCRIPTION`/`OFFICE_TITLE_KNOWLEDGE` (Phase 578)**:
completes the office-report prose trio `GANG_TEMPLATE`/`OFFICE_PERK_
DESCRIPTION` started -- `HostAK/TP/PROSE/TITLE.X2` (header `"60 3"`)
and `HostAK/TP/PROSE/TITKNOW.X2` (header `"60 1"`), transcribed from a
byte-faithful third-party reverse-engineering pass over the full 162-
file prose corpus (`AKPROSE_reverse_engineering_report.md`, supplied
directly by the user), cross-checked against this module's own already-
confirmed `Office` ordinal sequence (`SAY.PAS:694 _ODesc`/`SAY.PAS:696
_OAlert`, both `FD(path, S_Red, 1001+ord(_office))` -- the identical
`ord(office)+1` formula `IONAME.X2` already established). `TITLE.X2`
is `_ODesc`'s own full narrative ("An ethereal Emerald Crown appeared
on <'s head...") shown once when a King first attains an office;
`TITKNOW.X2` is `_OAlert`'s shorter "how this office is earned" blurb
("The title of \"Savior of Humankind\" is reserved for..."). Both
independently confirm the same `Office` ordinal mapping `OFFICE_PERK_
DESCRIPTION` already used -- `NO_OFFICE` (ordinal 8) reads literally
"(No Office)" in both catalogs, at the same position, matching neither
adjacent real office.

**Verbatim, including the source's own quirks**: several sentences run
two words together across an internal full stop with no space
(`"ago.It"`, `"other.The"`, `"gameturns).Only"`) -- confirmed present
in the byte-faithful reconstruction, not a transcription accident here;
kept exactly as sourced, the same "preserve real oddities" precedent
`OFFICE_PERK_DESCRIPTION`'s own `"Moutain"` typo (`MOUNTAIN_KING`)
already set. The `<`/`<2`/`>`/`=` pronoun and army-name markers are
stored as the raw literal characters `PROSE.TXT` defines them as (see
`report/prose.py`'s own module docstring for what each one means) --
**not resolved to real text**, since this project's own pronoun-
substitution system (`RUMORS.PAS Set_Person`/`Set_Alt`) is explicitly
out of scope there; a future consumer supplies real names/pronouns the
same way `render()`'s `values` parameter already does for every other
symbol.

**Both catalogs are physically short of their own declared 60-choice
header**: `TITLE.X2` has real content only through choice 52 (`Office`
ordinal 51, `NO_TITLE` -- present but blank, the file's own second real
sentinel gap, matching `OFFICE_PERK_DESCRIPTION`'s precedent exactly);
choices 53-60 are missing from the file entirely and don't correspond
to any real `Office` member (the enum only has 52), so this project
never needs them. `TITKNOW.X2` is shorter still: `NO_TITLE`'s own line
(choice 52) is missing from the file outright rather than present-but-
blank, but the effect is identical -- both dicts map it to `""`.
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

# HostAK/TP/PROSE/GANG.X2, verbatim, keyed by Office offset from
# DIVINE_KING (see module docstring's Phase 102 addendum). Raw,
# unrendered prose template, each meant to be appended directly after an
# army-name clause (leading space is part of the real text).
GANG_TEMPLATE: dict[Office, str] = {
    Office.DIVINE_KING: (
        " were aided/Rvisited by a {great/Rmighty }Thunderbird who "
        "flew_down/Rdescended from the heavens/Rstars to aid their "
        "{righteous/Rheroic }Divine/RHeavenly cause, and were "
        "inspired/Relevated to fanaticism by its divine/Rthunderous "
        "splendor/Rspectacle."
    ),
    Office.GOOD_KING: (
        " were joined/Rled_into_battle by ^A troop/Rsquadron of the "
        "Order of Knights_Hospitaller/Rthe_Knights_of_the_Hospital, who "
        "inspired/Rexhorted them to fanaticism with their Good and "
        "righteous/Rvaunted fury/Rleadership."
    ),
    Office.DRUID_KING: (
        " were exhorted/Renchanted into a fanatical state/Rfury by a "
        "circle/Rretinue of clerics/Rdruids from the Brotherhood of "
        "Druids, using_their/Rwho_awed_the_soldiers_with magical/Rmystical "
        "pyrotechnics/Rchanting."
    ),
    Office.NEUTRAL_KING: (
        " were joined/Rstiffened by a hardened/Rtough band/Routfit of "
        "mercenaries/Rfreedom_fighters of the Mercenaries Guild, who "
        "exhorted_them_to/Rled_them_into a fanatical fervor/Rcharge "
        "with/Rby_example_of their fearless/Rexperienced leadership/Relan."
    ),
    Office.PAGAN_KING: (
        " were blessed/Raided_in_the_battle by a band/Rretinue of "
        "medicine_men/Rpriests from/Rsent_by the League of Pagan "
        "Clerics, which inspired/Raroused them to a fanatical zeal/Rfury."
    ),
    Office.EVIL_KING: (
        " were egged_on/Raccompanied by a band/Rcompany of the Order of "
        "Black Knights, who urged/Rwhipped them into a fanatical "
        "terror/Rrage with their threats_and_curses/Rrabid_battle_lust."
    ),
    Office.NECRO_MAGE: "",
    Office.UNDEAD_KING: (
        " were overflown/Rdescended_upon by the Circle of Wraiths, who "
        "urged/Rgoaded them into mindless/Rrabid fanatical "
        "battle-lust/Rfury with their terrible_moaning/Rmaniacal_laughter."
    ),
    Office.DUELLIST: (
        " were joined/Raccompanied by ^A adventuresome_party/Rmerry_band "
        "of the Imperial Musketeers, who inspired/Rthrilled them to "
        "{the point of }fanaticism with their feats_of_derring-do/"
        "Runbelievable_panache."
    ),
}

# HostAK/TP/PROSE/IONAME.X2, the perk half of each "TITLE: perk" line,
# verbatim, positional with every one of Office's own 52 ordinals (see
# module docstring's Phase 103 addendum). NO_OFFICE/NO_TITLE are the
# empty string -- the file's own two real sentinel gaps, not missing data.
OFFICE_PERK_DESCRIPTION: dict[Office, str] = {
    Office.EMPEROR: "Know Tax Bases",
    Office.CHANCELLOR: "Crystal Ball Clairvoyance",
    Office.TREASURER: "Know Treasuries",
    Office.MARSHAL: "Recruit Extra Land Unit",
    Office.ADMIRAL: "Recruit Extra Naval Unit",
    Office.DEFENDER: "Reduce Damage 1 Point",
    Office.PRIEST: "Sense Nearby Alignments",
    Office.MAGE: "Sense Magic Items in Province",
    Office.NO_OFFICE: "",
    Office.HUMAN_KING: "20% Human Fanaticism",
    Office.ELVEN_KING: "35% Elven Fanaticism",
    Office.DWARVEN_KING: "40% Dwarven Fanaticism",
    Office.ORC_LORD: "45% Orcish Fanaticism",
    Office.DRAGON_LORD: "50% Dragon Fanaticism",
    Office.EAGLE_KING: "50% Eagle Fanaticism",
    Office.WHALE_KING: "50% Whale Fanaticism",
    Office.ELE_MAGE: "Air Elemental, all Flee attempts succeed.",
    Office.MERMAN_KING: "50% Mermen Fanaticism",
    Office.ENT_KING: "50% Entish Fanaticism",
    Office.TROLL_KING: "50% Troll Fanaticism",
    Office.WERE_KING: "50% Were-Beast Fanaticism",
    Office.ILLUS_MAGE: "Chameleon Familiar, always move first in combat.",
    Office.DIVINE_KING: "Thunderbird; 1 fanatical unit, fight marauding monsters",
    Office.GOOD_KING: "Knights Hospitaller; 1 fanatical unit, hospitals",
    Office.DRUID_KING: "Circle of Druids; 1 fanatical unit, 100% exploration",
    Office.NEUTRAL_KING: "Mercenaries Guild; 1 fanatical unit, attract mercenaries",
    Office.PAGAN_KING: "Pagan Clerics; 1 fanatical unit, 10% White bonus",
    Office.EVIL_KING: "Order of Black Knights; 1 fanatical unit, 5-gold bonus",
    Office.NECRO_MAGE: "Imp Familiar, 25% Magic Resistance",
    Office.UNDEAD_KING: "Circle of Wraiths; 1 fanatical unit, Plus 1 Skeletal Armies",
    Office.PLAINS_KING: "Double Plains Exploration Rate",
    Office.DESERT_KING: "Double Desert Exploration Rate",
    Office.JUNGLE_KING: "Double Jungle Exploration Rate",
    Office.FOREST_KING: "Double Forest Exploration Rate",
    Office.MOUNTAIN_KING: "Double Moutain Exploration Rate",
    Office.SEA_KING: "Double Sea Exploration Rate",
    Office.THIEF_PRINCE: "Thieves Guild, 10-gold bonus",
    Office.BATTLE_FOOL: "Increasing Tactical Aptitude",
    Office.AIR_FORCE: "Improved Training",
    Office.CHIEF_OF_STAFF: "Recruit Cost is -1 gold",
    Office.CURATOR: "Research Magic Item",
    Office.DIPLOMAT: "Monsters React Peacefully",
    Office.TEACHER: "Students Plus-1 Aptitude",
    Office.ASSASSIN: "Free Assassination Attempt",
    Office.DUELLIST: "1 Fanatical Unit",
    Office.PRAETOR: "Improved Training",
    Office.PSYCHIC_MAGE: "Telepathic Weapon; knows alignments, monster's deal intentions",
    Office.FLAGSHIP: "Improved Training",
    Office.WINGMAN: "Recruit Extra Air Unit",
    Office.CRAVENEST: "Improving Own Temper",
    Office.BRAVEST: "Improve Temper, by using Talk tactic",
    Office.NO_TITLE: "",
}


# HostAK/TP/PROSE/TITLE.X2, the office/title full narrative shown once
# when a King first attains it (SAY.PAS _ODesc), positional with every
# one of Office's own 52 ordinals (module docstring's Phase 578
# addendum). NO_TITLE is the empty string, present-but-blank in the
# real file, the same real sentinel gap OFFICE_PERK_DESCRIPTION already
# has -- choices 53-60 exist in the file's own declared header but have
# no physical content and no corresponding Office member, so they are
# not included here.
OFFICE_TITLE_DESCRIPTION: dict[Office, str] = {
    Office.EMPEROR: 'An ethereal Emerald Crown appeared on <\'s head, and a booming voice heard only by <2 ordained "This is the Crown of the Emperors of the Ancient Dynasty which ruled this world thousands of years ago.It is yours for as long as you are the best hope to become the next World Emperor, and can be given to no other.The Crown will give you the ability to know the strength of all your rivals in your quest for Empire".(This information will be shown in your Diplomacy report in future gameturns).Only the tax bases of kings bordering your kingdom that you have known for at least one full turn will be shown.',
    Office.CHANCELLOR: 'An eerily insubstantial Crystal Ball suddenly appeared in <\'s hands, and a soft voice that only < could hear whispered "This is the Crystal Ball of the Chancellors of the Ancient Dynasty, which governed this world many centuries ago.It will serve you for as long as you merit the title of Esteemed High Chancellor, and can not be transferred.With this Crystal Ball, you may conjure visions of the adventures of any character in this world.To use this magic power, just cast a Clairvoyance spell, which will automatically be successful even if you have no skill in magic.Using the Crystal Ball will not use up a Psychic Magic spell".It will also list all offices and titles held by the kingdom of the spied-upon character.',
    Office.TREASURER: 'A Golden Abacus mysteriously appeared on <\'s desk overnight.When < picked it up to examine it, a silky voice that only < could hear intoned, "This is the Golden Abacus of the Treasurers of the Ancient Dynasty which ruled the world millenia ago.You may have its use for as long as your treasury is the world\'s largest.The Abacus allows you to see the Treasuries of all your rivals in your pursuit of wealth (this information will be shown in your Diplomacy report in future gameturns).The Abacus can\'t be given to another character, and will disappear should your hoard ever lose its ranking as the world\'s richest treasury".Only kings bordering your kingdom that you have known for a full turn will be shown.',
    Office.MARSHAL: 'As < reviewed > troops in parade, < was startled by the sudden appearance of a Silver Baton in > right hand.A gruff voice which only < seemed to hear commanded, "You are to have the guardianship of this Marshal\'s Silver Baton, handed down from the Imperial Grand Marshals of the Ancient Dynasty who kept order in the Empire untold years ago, in an almost-forgotten era.It will allow you to recruit one extra unit of any army type which can move overland (except for flying units).For example, if a province has Legion and Chariot army types, you may recruit two of each type.The Baton cannot be transferred, and will remain yours only for as long as you remain the world\'s greatest general".',
    Office.ADMIRAL: 'As < laid in a new course for > flagship, < was startled by the sudden appearance of a Sapphire Compass in > right hand.A misty apparition arose from the swelling waves and spoke privately to <2: "This Compass will remain yours for as long as you are the world\'s greatest Admiral.It was used by the Grand Admirals of the Ancient Empire, which fell untold centuries ago.It will allow you to recruit one extra unit of any army type which can move from sea to sea (except for flying units).For example, if a province has a Fleet army type, you may recruit two Fleets instead of one.Also, in any sea battle where < is the supreme commander, provincial exploration will always be treated as being 100%".The Compass may not be transferred.',
    Office.DEFENDER: '< went to sleep one night and when < awakened, to > surprise he was encased in a suit of the finest mithril armor.A strong voice boomed from out of nowhere, saying "This is the Mithril Armor of the Lord High Defenders of the Ancient Empire which passed away uncounted years ago.It is yours for as long as you are the greatest hope to become the next Defender, and can be given to no other.The Armor will reduce any strike against you in personal combat (including magical damage) by one damage point".',
    Office.PRIEST: 'As < prayed to > god, an Ivory Rod appeared in between > clasped hands, and a divine voice that only < could hear echoed resonantly "Because you are the greatest hope to bring the souls of your world to deliverance, you may have this Ivory Rod.The Rod is an artifact which belonged to the High Priests Palatine of the Ancient Empire, which many years ago succumbed to decadence and petty bickering.It can be given to no other character, and you will have its use as long as you are the greatest of Priests.By its power, you can estimate the moral character of nearby Kings, along with nearby heroes whose location you is known to you (the accuracy decreases greatly with distance)".This data will be in your Characters report in future gameturns.',
    Office.MAGE: 'While studying > spells, < looked up to see that an incorporeal Platinum Wand had suddenly appeared and was floating in the air in front of <2.An enchanting voice spoke from some other dimension, saying "This is the Platinum Wand, once used by the Arch-Mages of the Ancient Empire which, as you know, collapsed many centuries ago.It is yours only for as long as you are the greatest Mage in the world, and can be given to no other character.The Wand has the power to sense the presence of other magic items in the same province: whenever you move into a province, it will tell you which magic items are present, but not where they are".',
    Office.NO_OFFICE: '(No Office)',
    Office.HUMAN_KING: 'As the Savior of Humankind, < has won the loyalty of the Human race.Each Human unit directly led by <2 has a 20% chance to become fanatical in battle, thus fighting at the next higher quality level.',
    Office.ELVEN_KING: 'As the First Elder of Elvenkind, < has won the loyalty of the Elven race.Each Elven unit directly led by <2 has a 35% chance to become fanatical in battle, thus fighting at the next higher quality level.',
    Office.DWARVEN_KING: 'As the King Under the Mountain, < has won the loyalty of the Dwarven race.Each Dwarven unit directly led by <2 has a 40% chance to become fanatical in battle, thus fighting at the next higher quality level.',
    Office.ORC_LORD: 'As the Khan of the Orcish Hordes, < has won the loyalty of the Orcish race.Each Orcish unit directly led by <2 has a 45% chance to become fanatical in battle, thus fighting at the next higher quality level.',
    Office.DRAGON_LORD: 'As the Dragon Lord, < has won the loyalty of the Dragon race.Each Dragon army directly led by <2 has a 50% chance to become fanatical in battle, thus fighting at the next higher quality level.',
    Office.EAGLE_KING: 'As the Ace of Eagles, < has won the loyalty of the Eagle race.Each Eagle wing directly led by <2 has a 50% chance to become fanatical in battle, thus fighting at the next higher quality level.',
    Office.WHALE_KING: 'As the League of Whales Commissioner, < has won the loyalty of the Whale race.Each Whale unit directly led by <2 has a 50% chance to become fanatical in battle, thus fighting at the next higher quality level.',
    Office.ELE_MAGE: "As the Master of Elements, < has attracted the loyalty of the Elemental Beings, which sometimes visit this plane.They have sent an Air Elemental to <2 as a Wizard's Familiar.Whenever < flees combat, the Air Elemental will form a whirlwind and whisk <2 away.Thus, all flee attempts are automatically successful.",
    Office.MERMAN_KING: 'As the King of Atlantis, < has won the loyalty of the Mermanic race.Each Merman army directly led by <2 has a 50% chance to become fanatical in battle, thus fighting at the next higher quality level.',
    Office.ENT_KING: 'As the Tsar of the Trees, < has won the loyalty of the Entish race.Each Entish army directly led by <2 has a 50% chance to become fanatical in battle, thus fighting at the next higher quality level.',
    Office.TROLL_KING: 'As the High Mucky-Muck of Trolls, < has won the loyalty of the Trollish race.Each Troll army directly led by <2 has a 50% chance to become fanatical in battle, thus fighting at the next higher quality level.',
    Office.WERE_KING: 'As the Lord of Lycanthropes, < has won the loyalty of the Werebeast race.Each Werebeast army directly led by <2 has a 50% chance to become fanatical in battle, thus fighting at the next higher quality level.',
    Office.ILLUS_MAGE: "As the Amazing Houdini, < has attracted the interest of the Illusionist's Guild.They have sent <2 a rare, specially-trained Magic Chameleon as a Wizard's Familiar.The Chameleon can transmit its camouflage ability to <2, which gives <2 the ability to always make the first move in combat, even if if > opponent has greater skill in magic.",
    Office.DIVINE_KING: '< has attained great renown as the most famous of Divine Kings, earning <2 the title of Divine Archangel.As > reward, the Thunderbird will sometimes descend from the heavens to aid <2 (in American Indian Mythology, the Thunderbird is a huge, highly intelligent and divine bird who is often found fighting evil creatures of great power who have joined forces with the enemies of good tribes).When < is the supreme commander at a battle, the Thunderbird will visit one unit in the front line, chosen at random, and inspire it to fanaticism with its beauty and thunder.Also, when monsters venture from their lairs to raid your lands, the Thunderbird will sometimes confront them and put a halt to their raids.',
    Office.GOOD_KING: 'As the Most Blessed of Good Kings, < has won recognition as the leader of the forces of Good, as well as the loyalty of the Knights Hospitaller.This knightly order is constituted of magnificent fighters who use their spare time to care for the sick and injured.When < is the supreme commander at a battle, one unit in the front line, chosen at random, will be joined by a troop of Knights and become fanatical.Also, due to their hospitals, the Plague spell has a -15% chance of affecting any unit owned by your Kingdom or in its territory.',
    Office.DRUID_KING: 'As the Great Druid of Life, < has been acclaimed as the greatest of Druidic Kings, and has earned the support of the Brotherhood of Druids.The Brotherhood considers itself the guardian of the forces of life and nature.The Druids have impressive rituals involving chanting and pyrotechnics: when < is the supreme commander at a battle, one unit in the front line, chosen at random, will be visited by the Druids and become fanatical.Also, in any land battle where < is the supreme commander, provincial exploration will always be treated as being 100% because of their ability to gather intelligence by talking to animals and communing with nature.',
    Office.NEUTRAL_KING: "As the Defender of Freedom, < leads the Neutral Kingdoms in their quest for a free world.The Mercenaries Guild has thrown in their lot with <2, and will allow <2's kingdom to recruit mercenaries for just one gold (although maintenance costs remain normal).When mercenary units wander, they will tend to work their way towards <'s kingdom.Also, when < is the supreme commander at a battle, one unit in the front line, chosen at random, will be joined by a band of berserking freedom fighters and become fanatical.",
    Office.PAGAN_KING: '< is the greatest conqueror among Pagan kings, earning <2 the title of Warlock of the Pagan Gods.> fame has even won the support of the League of Pagan Clerics.The League will supply all your Pagan characters with charms which will add 10% to their chance to cast a White Magic spell.They will help <2 in battle: when < is the supreme commander at a battle, one unit in the front line, chosen at random, will be blessed by the Clerics and become fanatical.',
    Office.EVIL_KING: '< has demonstrated that <, among all Evil kings, is the most ruthless conqueror of all.> infamy has attracted the service of the Order of Black Knights, made up of vicious fighters who hope to be rewarded with estates of their own after < becomes Emperor.When < is the supreme commander at a battle, one unit in the front line, chosen at random, will be joined by a gang of Black Knights and become fanatical.Also, the Black Knights control an underground criminal empire engaged in rackets such as blackmail and drug smuggling.In future gameturns, < will skim off 5 gold per turn from this nefarious activity.',
    Office.NECRO_MAGE: "As the Sorceror of Black Magic, < has attracted the interest of the Necromancer's Guild.They have conjured an Imp for <2 to act as a Wizard's Familiar.The Imp gives <2 25% magic resistance, meaning that 25% of the spells cast against <2 will fail.The Imp will also help <2 regenerate 1 hit point per 2 rounds of combat.",
    Office.UNDEAD_KING: 'As the Angel of Death, < has become the most powerful Undead King in the world.> infamy has attracted the service of Circle of Wraiths, a greatly feared band of wandering Undead wraiths who have banded together in the pursuit of greater power.When < is the supreme commander at a battle, one non-skeletal unit in the front line, chosen at random, will be joined by a flight of screaming Wraiths and become fanatical.Also, the Wraiths will help <2 in raising skeletal units: when < casts the Skeletal Armies spell, the maximum number of units that can be raised by <2 increases by 1.',
    Office.PLAINS_KING: 'As the Ranger of the Plains, < has won the favor of the inhabitants of Plains provinces.With their help, < can now explore Plains provinces at double > normal rate.',
    Office.DESERT_KING: 'As the Desert Rat, < has won the favor of the inhabitants of Desert provinces.With their help, < can now explore Desert provinces at double > normal rate.',
    Office.JUNGLE_KING: 'As the Lord of the Jungle, < has won the favor of the inhabitants of Jungle provinces.With their help, < can now explore Jungle provinces at double > normal rate.',
    Office.FOREST_KING: 'As the Warden of the Forests, < has won the favor of the inhabitants of Forest provinces.With their help, < can now explore Forest provinces at double > normal rate.',
    Office.MOUNTAIN_KING: 'As the Mountain Man, < has won the favor of the inhabitants of Mountain provinces.With their help, < can now explore Mountain provinces at double > normal rate.',
    Office.SEA_KING: 'As the Ruler of the Waves, < has won the favor of the inhabitants of Sea provinces.With their help, < can now explore Sea provinces at double > normal rate.',
    Office.THIEF_PRINCE: 'As the Prince of Thieves, < has proved worthy to be headmaster of the Thieves Guild.< will skim off 10 gold from their criminal activities each turn.',
    Office.BATTLE_FOOL: 'As the Fool of Battles, < has proved to be the most incompetent general on the face of the earth.< will now study harder to get this monkey off > back, and therefore > aptitude in Tactics will increase by 1 every turn (to a maximum of 5.)',
    Office.AIR_FORCE: 'As the Royal Air Force, = has won recognition as the greatest flying unit in the world.They command great respect from other flying units, who are inspired with a great desire to emulate them.Consequently, when = trains other flying units, their chance to improve in quality is doubled, and the chance for non-flying units is increased by half.',
    Office.CHIEF_OF_STAFF: 'As the Chief of Staff, < has become the ablest military officer of > time.The military-industrial complex of the world (such as it is) will show great favoritism to <2, because they look forward to a time when the world can be united under one Emperor, when they hope to get the inside track on fat military supply contracts.any unit recruited by <2 will get a discount on weapons and armor, so it will cost one less gold to recruit (but not to maintain.)Garrison units, for example, < can recruit for free.When recruiting a unit type not native to a province, the discount is taken before the recruitment cost is doubled.',
    Office.CURATOR: 'As the Curator of Artifacts, < has become the most renowned collector of magic artifacts in the world.This has attracted the attention of the Guild of Sages, who specialize in research.The Guild will research any item number in the world for <2, telling all about its magical function.To research a magic item number, the character must have an order to give the magic item number to himself.< can research items only by item number, not by magic item type.',
    Office.DIPLOMAT: "As the Silver Tongue, < has won renown as the world's smoothest talker and ablest diplomat.> reputation is such that even the monsters in their lairs have heard of <2.They will never respond violently when talked to, and will always honor any agreement made with <2 when < fulfills > end of it.",
    Office.TEACHER: "As Professor Whizdumb, < has become famous as the world's greatest teacher of men.> students have great respect for <2, and anyone practicing with <2 will gain a plus 1 modifier to their aptitude in whatever subject < is teaching.",
    Office.ASSASSIN: 'As the Grandfather of Assassins, < has risen to become the headmaster of the Assassins Guild.Once per turn, they will attempt an assassination of any non-King character.The attempt will occur at the end of the 5th phase after all battles have been fought.The chance of success is (50% - (5 x armies in same province) - (10 x melee skill)).Each time an attempt fails, the guard is doubled on the target and the next attempt will have half the normal chance.The target may be located anywhere in the world.To order the assassination of the character, give a "FI-re (character number)" order (note: if you Fire your own character, there won\'t be any assassination).The victim will know it was the work of the Guild, but not who leads it.',
    Office.DUELLIST: 'As the Captain of the Imperial Musketeers, < has won renown as the finest duellist in the land.> fame has also attracted a band of dashing adventuresome swordsmen who hope to become Imperial Musketeers once the world is united under one emperor. When < is the supreme commander at a battle, one unit in the front line, chosen at random, will be joined by a band of Musketeers and become fanatical.(Note: if < holds another Title giving a similar fanatical assist, the Musketeers will instead retire to a tavern instead, as they are loathe to share the limelight).',
    Office.PRAETOR: 'As the Praetorian Guard, = has won recognition as the land unit most qualified to protect the future World Emperor.Whenever they encamp with other armies, they spend their time telling stories of the great battles they have fought.Their gallantry inspires their fellow soldiers to train more intensively, so that when = trains other land units, their chance to improve in quality is doubled, and the chance for non-land units is increased by half.',
    Office.PSYCHIC_MAGE: "As the Master Mind, < has earned the attention of the Psychic's Guild.They have conjured an extra personality for <2, which takes up residence in > personal weapon.The personality is telepathic (it can read other people's minds).When < talks to any character or monster, < will know their exact alignment and temper.Also, when < talks to a monster who offers a deal for its magic item, < will sense whether the monster intends to keep its end of the bargain.",
    Office.FLAGSHIP: 'As the Imperial Flag Squadron, = has won acclaim as the greatest fighting navy in the world.Their legendary exploits greatly inspire the other navies who sail with =, so when = trains with other naval units (Mermen, Fleet, Whales), the chance to improve in quality is doubled, and the chance for non-naval units is increased by half.',
    Office.WINGMAN: 'As the Imperial Air Force Commander, < has become famous for > aerial exploits.> fame as an invincible aerial commander attracts thousands of new recruits, allowing <2 to recruit one extra unit of any flying army type in any province he visits that has a compatible race.',
    Office.CRAVENEST: 'As the King of Cowards, < has achieved infamy as the most cowardly skunk in the world, at least among those who would call themselves Heroes.So ashamed is < of the constant ridicule, > temper will improve by 1 level each gameturn.',
    Office.BRAVEST: "As the Bravest of the Brave, < has won fame as the Hero who has faced the greatest challenges with unyielding courage and self-sacrifice.Indeed, other men draw courage from > example: when < talks to any Hero, that Hero's temper will increase to the next higher level.Reminder: you can only list one Talk tactic per encounter.",
    Office.NO_TITLE: '',
}

# HostAK/TP/PROSE/TITKNOW.X2, the shorter "how this office/title is
# earned" blurb (SAY.PAS _OAlert), same positional convention as
# OFFICE_TITLE_DESCRIPTION above. NO_TITLE's own line is missing from
# the file outright rather than present-but-blank, mapped to the same
# empty string either way.
OFFICE_TITLE_KNOWLEDGE: dict[Office, str] = {
    Office.EMPEROR: '',
    Office.CHANCELLOR: '',
    Office.TREASURER: '',
    Office.MARSHAL: '',
    Office.ADMIRAL: '',
    Office.DEFENDER: '',
    Office.PRIEST: '',
    Office.MAGE: '',
    Office.NO_OFFICE: '(No Office)',
    Office.HUMAN_KING: 'The title of "Savior of Humankind" is reserved for the character who has best protected the Human race and led them to martial glory.',
    Office.ELVEN_KING: 'The title of "First Elder of Elvenkind" is given to the character who has best protected the Elven race and led them to martial glory.',
    Office.DWARVEN_KING: 'The title of "King Under the Mountain" is awarded to the character who has best protected the Dwarven race and led them to martial glory.',
    Office.ORC_LORD: 'The title of "Khan of the Orcish Hordes" is granted to the character who has best protected the Orcish race and led them to martial glory.',
    Office.DRAGON_LORD: 'The title of "Dragon Lord" is reserved for the character who has best protected the race of Dragons and led them to martial glory.',
    Office.EAGLE_KING: 'The title of "Ace of Eagles" is given to the character who has best protected the race of Eagles and led them to martial glory.',
    Office.WHALE_KING: 'The title of "League of Whales Commissioner" is awarded to the character who has best protected the race of Whales and led them to martial glory.',
    Office.ELE_MAGE: 'The title of "Master of Elements" is given to the character who most distinguishes himself in the art of Elemental Magic.',
    Office.MERMAN_KING: 'The title of "King of Atlantis" is granted to the character who has best protected the race of Mermen and led them to martial glory.',
    Office.ENT_KING: 'The title of "Tsar of the Trees" is reserved for the character who has best protected the race of Ents and led them to martial glory.',
    Office.TROLL_KING: 'The title of "High Mucky-Muck of Trolls" is given to the character who has best protected the race of Trolls and led them to martial glory.',
    Office.WERE_KING: 'The title of "Lord of Lycanthropes" is awarded to the character who has best protected the race of Werebeasts and led them to martial glory.',
    Office.ILLUS_MAGE: 'The title of "The Amazing Houdini" is granted to the character who most distinguishes himself in the art of Illusory Magic.',
    Office.DIVINE_KING: 'The title of "Divine Archangel" is reserved for the most powerful of Divine Kings.',
    Office.GOOD_KING: 'The title of "Most Blessed of Good Kings" is given to the most powerful of Good Kings.',
    Office.DRUID_KING: 'The title of "Great Druid of Life" is awarded to the most powerful of Druidic Kings.',
    Office.NEUTRAL_KING: 'The title of "Defender of Freedom" is granted to the most powerful of Neutral Kings.',
    Office.PAGAN_KING: 'The title of "Warlock of the Pagan Gods" is reserved for the most powerful of Pagan Kings.',
    Office.EVIL_KING: 'The title of "King of Pain" is given to the most powerful of Evil Kings.',
    Office.NECRO_MAGE: 'The title of "Sorceror of Black Magic" is awarded to the character who most distinguishes himself in the art of Necromancy.',
    Office.UNDEAD_KING: 'The title of "Angel of Death" is granted to the most powerful of Undead Kings.',
    Office.PLAINS_KING: 'The title of "Ranger of the Plains" is reserved for the greatest explorer of Plains provinces.',
    Office.DESERT_KING: 'The title of "Desert Rat" is given to the greatest explorer of Desert provinces.',
    Office.JUNGLE_KING: 'The title of "Lord of the Jungle" is awarded to the greatest explorer of Jungle provinces.',
    Office.FOREST_KING: 'The title of "Warden of the Forests" is granted to the greatest explorer of Forest provinces.',
    Office.MOUNTAIN_KING: 'The title of "Mountain Man" is reserved for the greatest explorer of Mountain provinces.',
    Office.SEA_KING: 'The title of "Ruler of the Waves" is given to the greatest explorer of Sea provinces.',
    Office.THIEF_PRINCE: 'The title of "Prince of Thieves" is awarded to the greatest of Thieves.',
    Office.BATTLE_FOOL: 'The title of "Fool of Battles" is reserved for the most incompetent general.',
    Office.AIR_FORCE: 'The title of "Royal Air Force" is granted to the air unit best suited to serve as the royal air guard for the emperor.',
    Office.CHIEF_OF_STAFF: 'The title of "Chief of Staff" is given to the ablest military officer in the world.',
    Office.CURATOR: 'The title of "Curator of Artifacts" is awarded to the most accomplished magic-item collector in the world.',
    Office.DIPLOMAT: 'The title of "The Silver Tongue" is reserved for the world\'s smoothest diplomat.',
    Office.TEACHER: 'The title of "Professor Whizdumb" is granted to the best teacher in the world.',
    Office.ASSASSIN: 'The title of "Grandfather of Assassins" is given to the world\'s deadliest assassin.',
    Office.DUELLIST: 'The title of "Captain of the Imperial Musketeers" is awarded to the best duellist in the world.',
    Office.PRAETOR: 'The title of "Praetorian Guard" is reserved for the military land unit best suited to serve as the imperial palace guard for the emperor.',
    Office.PSYCHIC_MAGE: 'The title of "Master Mind" is granted to the greatest Psychic magician in the world.',
    Office.FLAGSHIP: 'The title of "Imperial Flag Squadron" is given to the naval unit best suited to serve as a naval escort for the emperor.',
    Office.WINGMAN: 'The title of "Imperial Air Force Commander" is awarded to the world\'s greatest leader of airborne forces.',
    Office.CRAVENEST: 'The title of "King of Cowards" is reserved for the most cowardly hero known to this world.',
    Office.BRAVEST: 'The title of "Bravest of the Brave" is granted to the bravest hero in the world.',
    Office.NO_TITLE: '',
}
