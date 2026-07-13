"""Monster type model (rulebook [3.2]/[5.9], ``HostAK/TP/CTBOTH.PAS`` `monster` enum) --
Phase 75, part of "Feature model foundations".

**The `monster` enum and its printable names are fully sourced and
transcribed verbatim** (``CTBOTH.PAS`` ~line 493-523): 61 declared
values, ``Roc``..``Mermaid`` (60 real species) plus ``Nomonster``
itself, a real "no monster" sentinel used elsewhere in the Pascal
source (not a placeholder this project invented) -- ``nmonsters = 60``
apparently counts only the species, excluding the sentinel. 10 unused
extension slots (``em1``-``em10``) are omitted here -- the same
convention ``models/map.py Terrain`` already uses for its own
unreferenced extension slots (``SWAMP``, ``LAVA``, ``ET1``-``ET5``).

**Rulebook [3.2] Explore, quoted in full where relevant**: "Monsters
are described when they are first discovered, as follows":

    Weak:            7-12 hit points
    - :             13-19 hit points
    Large/Strong    20-29 hit points
    Powerful:       30-44 hit points
    Very Powerful:  45+ hit points

Transcribed verbatim into ``MONSTER_HP_BANDS`` below, including the
rulebook's own unlabeled second row (literally "``- :``" in the
source -- not a transcription error, and not force-labeled here with
an invented name like "Average").

**Rulebook [5.6] Flee, quoted for the part relevant to monster speed**:
"His chance of fleeing from fast monsters is 20%. Fleeing from
medium-speed monsters or other characters is a 50-50 proposition, and
slow monsters can be escaped from 80% of the time." Confirms exactly
three speed tiers (``MonsterSpeed``), matching the "Fast"/"Medium"
values already seen in the Monster Table below (no "Slow" example
happens to appear in that partial table, but the tier itself is
directly sourced here).

**Rulebook's own "Monster Table", quoted in full** (``RULES.AK``,
labelled "[5.9]" in the source itself -- a duplicate section number:
the table of contents' own [5.9] is "Victory and Death", a distinct
section; not a transcription error on this project's part, the
rulebook file itself repeats the number):

    The following table is a partial listing of monsters that you may encounter:

                 Average
                 Hit      Melee           Missile
    Monster      Points   Skill  Damage   Skill  Damage   Speed
    Gryphon       25        2      1-6      0      -      Fast
    Giant         25        1      1-7      1     1-7     Medium
    Gargoyle      15        1      1-6      0      -      Medium
    Demon         30        3      1-8      0      -      Fast
    Troll         25        1      1-6      0      -      Medium
    Spectre       20        1      1-6      0      -      Medium
    Elasmosaurus  25        2      1-7      0      -      Fast

Transcribed into ``MONSTER_STATS`` below for the 6 rows that map
**unambiguously** to a single ``Monster`` enum member (``Gryphon``,
``Giant``, ``Gargoyle``, ``Troll``, ``Spectre``, ``Elasmosaurus``).
**"Demon" is deliberately excluded, not guessed**: the Pascal enum has
no plain ``Demon`` member -- only ``BalDemon`` ("Balrog Demon") and
``MarDemon`` ("Marilith Demon") -- and the rulebook's own table row
doesn't say which one (or whether it means either/both) its stats
describe. Rather than arbitrarily picking one, that row is left
unmapped; a future phase with a clearer source for the distinction can
add it.

**Explicitly out of scope**: per-monster missile/melee stats for the
other 53 real monsters aren't in any available source (rulebook,
Pascal, or the 10 real move files -- monsters are never referenced in
move-file data at all, since only a feature's own ``feature_id`` is
ever an order target, never its guardian directly). `CTBOTH.PAS`'s own
``monfeat``/``mfeat1``/``mfeat2`` tables (which monster tends to guard
which feature *type*, for world generation) are a separate, unrelated
concern -- see ``models/feature.py``'s own docstring for why world
generation itself stays unbuilt.

**Phase 130 addendum -- monster engagement state.** Found while
scanning `RUMORS.PAS` for un-mined narrative content past `SAY.PAS`'s
own now-fully-scanned dispatch code: `RUMORS.PAS`'s `Check_Raid`
procedure (~lines 2279-2286) references `fstate[_feat1-256] = Bold`
(a guarding monster's own negotiation state), which is `CTBOTH.PAS`'s
`state = (Dead,Hired,Mercenary,Zomboid,Bold,Sold,Loser,Calm)`
(~line 1260), with real display names confirmed via `CTBOTH.PAS`'s own
``statname: ststrs = ('Dead','Hired','Mercenary','Skeletal',
'Emboldened','Sold Soul','Loser','Calmed')`` (~line 1527) -- an
8-member enum tracking whether a monster guarding a feature has been
Hired, become a Mercenary, turned Skeletal (Necromantic control),
"Sold" its soul, become a sore Loser, been Calmed, or -- the one this
narrative fragment cares about -- become `Bold`/"Emboldened" enough to
negotiate a quest (`Check_Raid`'s own real `Say(...)` sentence:
"[ also offered to stop raiding/Rplundering @ if this quest be/Rwere
accomplished/Rcompleted.", dispatched only when the monster's own
`fstate` is `Bold`). Ties directly to `report/turn_report.py`'s own
Monster Quest Fulfillment cluster (Phase 129).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Monster(Enum):
    ROC = 0
    GRYPHON = 1
    COUATL = 2
    GI_EAGLE = 3
    SPHINX = 4
    R_DRAGON = 5
    B_DRAGON = 6
    GR_DRAGON = 7
    S_DRAGON = 8
    GO_DRAGON = 9
    GI_WORM = 10
    TITAN = 11
    GIANT = 12
    BIGFOOT = 13
    ARCHER = 14
    SWORDSMAN = 15
    WHITE_MAGE = 16
    NEC_MAGE = 17
    ELE_MAGE = 18
    PSY_MAGE = 19
    ILL_MAGE = 20
    WITCH = 21
    DRYAD = 22
    CENTAUR = 23
    GENIE = 24
    GOLEM = 25
    GARGOYLE = 26
    BASILISK = 27
    MEDUSA = 28
    BAL_DEMON = 29
    MAR_DEMON = 30
    SUCCUBUS = 31
    RAKSHASHA = 32
    ICE_DEVIL = 33
    BONE_DEVIL = 34
    IMP = 35
    WEREWOLF = 36
    CHIMERA = 37
    HYDRA = 38
    BEHOLDER = 39
    TROLL = 40
    MINOTAUR = 41
    GI_WOLVERINE = 42
    TREANT = 43
    GI_AMOEBA = 44
    GI_P_MANTIS = 45
    GI_SCORPION = 46
    GI_WASP = 47
    GI_SPIDER = 48
    GHOST = 49
    VAMPIRE = 50
    MUMMY = 51
    BANSHEE = 52
    LICH = 53
    SPECTRE = 54
    GI_OCTOPUS = 55
    GI_CLAM = 56
    ELASMOSAURUS = 57
    GW_WHALE = 58
    MERMAID = 59
    NOMONSTER = 60


# CTBOTH.PAS `mtname`, verbatim, positional with the `Monster` ordinals above.
MONSTER_NAMES: dict[Monster, str] = {
    Monster.ROC: "Roc",
    Monster.GRYPHON: "Gryphon",
    Monster.COUATL: "Couatl",
    Monster.GI_EAGLE: "Giant Eagle",
    Monster.SPHINX: "Sphinx",
    Monster.R_DRAGON: "Red Dragon",
    Monster.B_DRAGON: "Black Dragon",
    Monster.GR_DRAGON: "Green Dragon",
    Monster.S_DRAGON: "Silver Dragon",
    Monster.GO_DRAGON: "Gold Dragon",
    Monster.GI_WORM: "Giant Worm",
    Monster.TITAN: "Titan",
    Monster.GIANT: "Giant",
    Monster.BIGFOOT: "Bigfoot",
    Monster.ARCHER: "Renegade Archer",
    Monster.SWORDSMAN: "Renegade Swordsman",
    Monster.WHITE_MAGE: "Renegade Priest",
    Monster.NEC_MAGE: "Renegade Necromancer",
    Monster.ELE_MAGE: "Elemental Sorceror",
    Monster.PSY_MAGE: "Renegade Psychic",
    Monster.ILL_MAGE: "Renegade Illusionist",
    Monster.WITCH: "Witch",
    Monster.DRYAD: "Dryad",
    Monster.CENTAUR: "Centaur",
    Monster.GENIE: "Genie",
    Monster.GOLEM: "Golem",
    Monster.GARGOYLE: "Gargoyle",
    Monster.BASILISK: "Basilisk",
    Monster.MEDUSA: "Medusa",
    Monster.BAL_DEMON: "Balrog Demon",
    Monster.MAR_DEMON: "Marilith Demon",
    Monster.SUCCUBUS: "Succubus",
    Monster.RAKSHASHA: "Rakshasha",
    Monster.ICE_DEVIL: "Ice Devil",
    Monster.BONE_DEVIL: "Bone Devil",
    Monster.IMP: "Imp",
    Monster.WEREWOLF: "Werewolf",
    Monster.CHIMERA: "Chimera",
    Monster.HYDRA: "Hydra",
    Monster.BEHOLDER: "Beholder",
    Monster.TROLL: "Troll",
    Monster.MINOTAUR: "Minotaur",
    Monster.GI_WOLVERINE: "Giant Wolverine",
    Monster.TREANT: "Treant",
    Monster.GI_AMOEBA: "Giant Amoeba",
    Monster.GI_P_MANTIS: "Giant Praying Mantis",
    Monster.GI_SCORPION: "Giant Scorpion",
    Monster.GI_WASP: "Giant Wasp",
    Monster.GI_SPIDER: "Giant Spider",
    Monster.GHOST: "Ghost",
    Monster.VAMPIRE: "Vampire",
    Monster.MUMMY: "Mummy",
    Monster.BANSHEE: "Banshee",
    Monster.LICH: "Lich",
    Monster.SPECTRE: "Spectre",
    Monster.GI_OCTOPUS: "Giant Octopus",
    Monster.GI_CLAM: "Giant Clam",
    Monster.ELASMOSAURUS: "Elasmosaurus",
    Monster.GW_WHALE: "Great White Whale",
    Monster.MERMAID: "Mermaid",
    Monster.NOMONSTER: "no monster",
}


class MonsterSpeed(Enum):
    FAST = "fast"
    MEDIUM = "medium"
    SLOW = "slow"


@dataclass(frozen=True, slots=True)
class MonsterStats:
    hit_points: int
    melee_skill: int
    melee_damage: tuple[int, int]
    missile_skill: int
    missile_damage: tuple[int, int] | None
    speed: MonsterSpeed


# RULES.AK's own Monster Table -- see module docstring for the exact
# quoted text and why "Demon" is excluded rather than guessed.
MONSTER_STATS: dict[Monster, MonsterStats] = {
    Monster.GRYPHON: MonsterStats(25, 2, (1, 6), 0, None, MonsterSpeed.FAST),
    Monster.GIANT: MonsterStats(25, 1, (1, 7), 1, (1, 7), MonsterSpeed.MEDIUM),
    Monster.GARGOYLE: MonsterStats(15, 1, (1, 6), 0, None, MonsterSpeed.MEDIUM),
    Monster.TROLL: MonsterStats(25, 1, (1, 6), 0, None, MonsterSpeed.MEDIUM),
    Monster.SPECTRE: MonsterStats(20, 1, (1, 6), 0, None, MonsterSpeed.MEDIUM),
    Monster.ELASMOSAURUS: MonsterStats(25, 2, (1, 7), 0, None, MonsterSpeed.FAST),
}


@dataclass(frozen=True, slots=True)
class MonsterHitPointBand:
    label: str  # verbatim from RULES.AK, including the unlabeled "-" row
    low: int
    high: int | None  # None = "45+", open-ended


# RULES.AK [3.2]'s own descriptor table, quoted in full in the module docstring.
MONSTER_HP_BANDS: tuple[MonsterHitPointBand, ...] = (
    MonsterHitPointBand("Weak", 7, 12),
    MonsterHitPointBand("-", 13, 19),
    MonsterHitPointBand("Large/Strong", 20, 29),
    MonsterHitPointBand("Powerful", 30, 44),
    MonsterHitPointBand("Very Powerful", 45, None),
)


class MonsterEngagementState(Enum):
    """Mirrors CTBOTH.PAS's own ``state`` enum (~line 1260) -- a
    guarding monster's own negotiation/service status. See module
    docstring's Phase 130 addendum.
    """

    DEAD = 0
    HIRED = 1
    MERCENARY = 2
    ZOMBOID = 3
    BOLD = 4
    SOLD = 5
    LOSER = 6
    CALM = 7


# CTBOTH.PAS `statname` (~line 1527), verbatim, positional with
# `MonsterEngagementState`'s own ordinals above.
MONSTER_ENGAGEMENT_STATE_NAME: dict[MonsterEngagementState, str] = {
    MonsterEngagementState.DEAD: "Dead",
    MonsterEngagementState.HIRED: "Hired",
    MonsterEngagementState.MERCENARY: "Mercenary",
    MonsterEngagementState.ZOMBOID: "Skeletal",
    MonsterEngagementState.BOLD: "Emboldened",
    MonsterEngagementState.SOLD: "Sold Soul",
    MonsterEngagementState.LOSER: "Loser",
    MonsterEngagementState.CALM: "Calmed",
}
