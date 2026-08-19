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

**Phase 154 addendum -- full combat-stats coverage, project-original.**
`MONSTER_STATS` above covers only 6 of 60 real species because
`RULES.AK`'s own "Monster Table" is explicitly "a partial listing".
Closing that gap for the other 54 needs real stats no available source
(rulebook, Pascal, or the 10 real move files) provides -- the same
"explicitly out of scope" conclusion this module already reached above.
The user closed it directly, the same "user authors replacement content
for a confirmed-unsourced gap" pattern already used for Phase 148's
skill-book narrative and Phase 152's province names: a self-compiled
document (`Desktop/MOSTRI con statistiche.txt`, supplied 2026-07-15,
confirmed by the user to be their own compilation, not a transcription
of any Pascal or rulebook source) giving Hit Point *ranges*, Melee/
Missile Skill and Damage, and Speed for all 60 real species.

`MonsterCombatStats`/`MONSTER_COMBAT_STATS` model this new data as a
separate table from the original, Pascal-sourced `MonsterStats`/
`MONSTER_STATS` -- deliberately not merged into or overwriting it, so
the one directly-cited RULES.AK quote above stays intact and
independently verifiable. The two corroborate each other well: for 5 of
the 6 species both tables cover, this table's own HP range has exactly
the same midpoint as `MONSTER_STATS`'s "Average Hit Points" column
(Gryphon/Giant/Gargoyle/Troll/Elasmosaurus: range midpoint == RULES.AK
average, exactly). **Spectre is the one exception, transcribed as
supplied rather than silently reconciled**: `MONSTER_STATS` gives 20,
but this table's own 12-22 range midpoints to 17 -- a genuine
cross-source discrepancy between the RULES.AK excerpt and the user's
own compiled document, left as an open, documented disagreement rather
than picked over the other.

`turn/search_execution.py execute_search()` now draws from
`MONSTER_COMBAT_STATS` (rolling actual hit points via
``rng.randint(*stats.hit_points_range)`` at combat time, matching every
other RNG-driven resolution already in this project) instead of the
6-entry `MONSTER_STATS`, closing the "only 6 of 61 monster species
have combat stats" limitation `search_execution.py`'s own docstring
previously flagged.

**Deliberately not modeled from this same source, out of scope for this
phase**: the source document also gives, per species, an Alignment
distribution (e.g. "Neutral (50%) / Pagan (50%)") and a count of Magic
Abilities by school, plus flavor-text descriptions and four numbered
combat footnotes -- Troll regenerates 1 HP/combat-round (negated by a
Fireball spell), dragons/Chimera's missile attack is reskinned breath
weapon narration, Giant/Treant/Titan's is a thrown-boulder narration,
and Basilisk/Medusa's is a petrifying-gaze narration (all four are real
mechanics/narrative hooks, not just flavor to discard, but each needs a
change to `turn/encounter.py`'s own combat loop or `report/
turn_report.py`'s own renderers beyond simple stat population -- left
for a future phase, not lost; see `Desktop/MOSTRI con statistiche.txt`
for the full table if that phase gets picked up). Troll regeneration and
the three missile-narration footnotes were later closed (Phases 155 and
175); Alignment distribution is closed below (Phase 176); Magic
Abilities counts are closed below (Phase 177). Flavor-text descriptions
remain unmodeled.

**Phase 176 addendum -- Alignment distribution, project-original,
same source.** Every one of the 60 real species' own Alignment column
in `Desktop/MOSTRI con statistiche.txt` is either a single fixed value
("Evil") or 2-3 weighted options summing to 100% ("Neutral (50%) /
Pagan (50%)", "Good (40%) / Druidic (30%) / Neutral (30%)"). Confirmed
directly by the user: "Ogni volta che si crea il mondo e si piazzano i
mostri per quelli che hanno due o tre allineamenti si tirano le
percentuali e si assegna l'allineamento" ("Every time the world is
created and monsters are placed, for those with two or three
alignments, the percentages are rolled and the alignment is assigned").
That statement fixes two design points directly:

- **The roll only happens for a 2-or-3-option species.** A single-
  option species (e.g. Gryphon: Neutral, no percentage shown) gets that
  one Alignment directly -- `roll_monster_alignment()` below returns it
  without ever calling `rng.random()`, mirroring how `resolve_fire_
  arrow_duel()` only rolls a monster's own missile attack when its
  `missile_skill` is nonzero (Phase 170) rather than always consuming a
  roll regardless of whether one is meaningful.
- **This is world-generation-time data, not a turn action.** The
  rulebook itself never re-rolls a placed monster's Alignment mid-game
  -- it's decided once, when "the world is created and monsters are
  placed." At the time of this phase, `roll_monster_alignment()` was a
  pure, callable mechanism with no wiring into an actual world-
  generation pipeline, because this project still had none
  (`models/feature.py`'s own docstring then: "world generation itself
  remains the blocking gap") -- nothing to connect it to yet, not a gap
  in this phase's own scope. ~~Deliberately not wired anywhere~~
  **wired into `turn/world_generation.py _create_feature()` as of
  Phase 246**, once that module's own Phase 242 existence closed the
  "nothing to connect it to" gap -- see that phase's own note in
  `ak_engine/README.md` for the wiring.

Every species' own alignment tuple sums to exactly 100 (`sum(o.percent
for o in options) == 100`), verified by `tests/test_monster.py`'s own
Phase 176 coverage test rather than trusted by inspection alone.
`AlignmentOption` percentages are listed in the same order the source
table gives them, so `roll_monster_alignment()`'s cumulative-threshold
walk reproduces the source's own ordering (matters only for which
option the final fallback covers, since floating-point roundoff always
resolves to *some* listed option, never an invented one).

**Phase 177 addendum -- Magic Abilities counts, project-original, same
source.** The source document's own last column reads, per species,
e.g. "1 NE" (Spectre), "3 WH, 3 PS, 3 EL, 2 IL" (Silver Dragon) -- a
skill level (1-4 observed) in one or more of the 5 magic-school
`Ability` members, abbreviated `WH`/`NE`/`EL`/`PS`/`IL`. Confirmed by
direct comparison against `models/enums.py Ability`'s own 5 magic-
school members (`WHITE`, `NECROMANCY`, `ELEMENTAL`, `PSYCHIC`,
`ILLUSION`) -- the same 5 schools `Monster.WHITE_MAGE`/`NEC_MAGE`/
`ELE_MAGE`/`PSY_MAGE`/`ILL_MAGE`'s own species names already echo, and
exactly the abbreviations this table's own entries use for those exact
species (e.g. Renegade Priest/`WHITE_MAGE` reads "3 WH, 2 NE, 2 IL").

Unlike Alignment, this is a **fixed fact per species, not a weighted
roll** -- every species either has one exact set of magic-ability
levels or has none at all (most of the 60: no magic abilities column
entry whatsoever, not a hidden zero-everything row). `MONSTER_MAGIC_
ABILITIES` below is therefore a plain `dict[Monster, dict[Ability,
int]]` covering only the 29 species the source actually lists a magic
ability for -- absent species genuinely have none, the same "don't
invent zero-rows" convention `MONSTER_STATS`'s own 6-of-60 coverage
already established (module docstring, above).

**At the time of this phase, also deliberately not wired anywhere**,
for the same reason Phase 176's `roll_monster_alignment()` wasn't: this
is exactly the data a future phase would need to let a spellcasting
monster guardian use its own `CAST` tactic in an Encounter Plan
(`turn/encounter.py`'s own Troll-regeneration addendum already flagged
that whole mechanic as "blocked on the Cast-tactic-spell-id gap") -- the
data was real and ready, but there was still no monster-side Cast-tactic
combat engine in this project to hand it to. ~~Deliberately not wired
anywhere~~ **wired into `turn/search_execution.py` as of Phase 209**,
once that phase built the CAST orchestration engine for Search
encounters -- see that phase's own note in `ak_engine/README.md`.

**Phase 182 addendum -- Spiritwrack's own Undead/Mechanical/Animal-
Intelligence species lists, project-original, user-supplied.** Spelled
out directly while defining `turn/encounter.py`'s Spiritwrack [SP]
spell effect: "Questo incantesimo e' inefficace contro mostri Non-
Morti (questi sono: Spectre, Ghost, Vampire, Mummy, Banshee, Lich) o
meccanici (che non hanno anima, questi sono: Golem, Gargoyle) e i suoi
effetti sono dimezzati contro mostri di intelligenza animale. Questi
sono: Gryphon, Elasmosaurus, Giant Worm, Giant Wolverine, Giant Amoeba,
Giant Praying Mantis, Giant Scorpion, Giant Wasp, Giant Spider, Giant
Octopus, Giant Clam, Great White Whale."

**Distinct from `Alignment.UNDEAD`/`Alignment.MECHANICAL`, confirmed
by direct grep before adding this**: neither existing enum member is
actually used anywhere in `MONSTER_ALIGNMENT_DISTRIBUTION` above (e.g.
Ghost/Vampire/Mummy/Banshee/Lich/Spectre are all 100%-`Alignment.
ANTI_HOLY` there, from the *outlook*/kingdom-alignment axis Phase 176
modeled; Golem is `NEUTRAL`, Gargoyle is `EVIL`). This new list is a
genuinely separate classification axis -- "is this species Undead-
type/Mechanical-type/Animal-Intelligence-type" for spell-targeting
purposes -- not a re-reading of the existing alignment/outlook data,
so it's kept as its own dedicated set below rather than overloading
`Alignment`.

`SPIRITWRACK_UNDEAD_MONSTERS` and `SPIRITWRACK_MECHANICAL_MONSTERS` are
kept as two separate frozensets (rather than merged into one "immune"
set) since they're conceptually distinct reasons for the same
Spiritwrack outcome (spirit-numbing magic finds no spirit to numb in
either an Undead creature or a soulless construct) -- a future spell
that only cares about one of the two reasons can still tell them
apart. `SPIRITWRACK_ANIMAL_INTELLIGENCE_MONSTERS` is the third,
independent list.

**Phase 185 addendum -- Telekinetic Storm's own submarine-monster
list, project-original, user-supplied.** Spelled out directly while
defining `turn/encounter.py`'s Telekinetic Storm [TE] spell effect:
"La Tempesta Telecinetica e' inefficace contro i mostri sottomarini.
Questi sono: Elasmosaurus, Giant Octopus, Giant Clam, Great White
Whale, Mermaid." A fourth new classification axis, same rationale as
Phase 182's own three: not a re-reading of `Alignment` (Mermaid alone
is enough to prove it -- `MONSTER_ALIGNMENT_DISTRIBUTION` has Mermaid
as 50% `GOOD`/50% `DRUID`, nothing about being submarine), and
partially overlapping but not identical to `SPIRITWRACK_ANIMAL_
INTELLIGENCE_MONSTERS` (Elasmosaurus/Giant Octopus/Giant Clam/Great
White Whale appear in both lists, for unrelated reasons -- being
animal-intelligence and being submarine are two independent facts
about the same four species; Mermaid is submarine but *not* listed as
animal-intelligence, confirming the lists are genuinely separate, not
one mislabeled as the other).

**Renamed from `TELEKINETIC_STORM_SUBMARINE_MONSTERS` to `SUBMARINE_
MONSTERS` in Phase 188**, when Fireball [FI] was confirmed to reuse
this exact same category ("mostri sottomarini," no new species list
given -- the user's own phrasing pointed back at the same, already-
established set rather than supplying a fresh one). Unlike Phase 182's
own three Spiritwrack sets (each kept spell-prefixed on purpose, since
"Undead"/"Mechanical" are conceptually distinct reasons for the same
outcome even when a future spell might care about only one), a single
shared, non-prefixed `SUBMARINE_MONSTERS` is the right call here: two
spells now genuinely mean the identical real-world category, not two
merely-overlapping ones.

**Phase 189 addendum -- Ice Suspension [IC]'s two classification axes.**
`turn/encounter.py`'s Ice Suspension spell (Phase 189 addendum there)
branches on target type before applying any freeze/slow formula:

- `ICE_SUSPENSION_IMMUNE_MONSTERS`: "fantasmi, demoni e simili...
  perché queste creature esistono solo parzialmente nel mondo
  materiale" -- Spectre, Genie, Balrog Demon, Marilith Demon, Succubus,
  Rakshasha, Ice Devil, Bone Devil, Imp, Ghost, Banshee.
- `ICE_SUSPENSION_FLYING_MONSTERS`: "mostri volanti" -- Vampire, Giant
  Wasp, Beholder, Green/Gold/Silver/Black/Red Dragon, Giant Eagle,
  Couatl, Roc, Gargoyle, Gryphon.

Both are spell-prefixed, following Phase 182's own convention (kept
separate axes even where they might partially overlap with existing
sets) rather than Phase 188's shared-set exception: no other spell in
this project references "partial materiality" or "flying" as a
category yet, so there is nothing to unify with. The two sets are
mutually exclusive (verified: no species appears in both), consistent
with the spell's own three-way branch (immune / flying / everything
else) never needing to resolve an overlap.

**Phase 190 addendum -- Hand of Death [HA]'s immunity, two exact
reuses and one new set.** `turn/encounter.py`'s Hand of Death spell
(Phase 190 addendum there) is inefficace against three categories:
"mostri meccanici" [Gargoyle, Golem] and "Non-Morti" [Spectre, Ghost,
Vampire, Mummy, Banshee, Lich] are, species-for-species, *identical* to
the existing `SPIRITWRACK_MECHANICAL_MONSTERS`/`SPIRITWRACK_UNDEAD_
MONSTERS` (Phase 182) -- reused directly, the same "same real category"
exception Phase 188 used for `SUBMARINE_MONSTERS`, rather than
duplicated under a new spell prefix. "Anti-holy" [Balrog Demon,
Marilith Demon, Succubus, Rakshasha, Ice Devil, Bone Devil, Imp] is a
genuinely new seven-species set: new `HAND_OF_DEATH_ANTI_HOLY_
MONSTERS`, spell-prefixed because it is a strict *subset* of Phase
189's own `ICE_SUSPENSION_IMMUNE_MONSTERS` (which also includes
Spectre/Genie/Ghost/Banshee -- species the user places under "Non-
Morti" here instead), not identical to it, so reusing that set would
silently misclassify four species. `HAND_OF_DEATH_IMMUNE_MONSTERS` is
the union of all three (two reused, one new), provided as a single
convenience set matching every other spell's own immune-set name.

**Phase 202 addendum -- Gate Demon [GD]'s own d100 demon-roster roll,
project-original, user-supplied.** `turn/encounter.py`'s Gate Demon
spell (Phase 202 addendum there) summons one of the same seven
Anti-Holy demon species `HAND_OF_DEATH_ANTI_HOLY_MONSTERS` (Phase 190)
already enumerates, via a d100 table: "1-20 Imp, 20-40 Succubus, 41-55
Bone Devil, 56-70 Ice Devil, 71-80 Marilith Demon, 81-90 Rakshasha,
91-100 Balrog Demon." `models/advanced_ability.py GATE_DEMON_TABLE`
already recorded this table as display-label strings (Phase 128,
before the mechanic itself was known); `GATE_DEMON_TYPE_PERCENT` and
`roll_gate_demon_type()` above restate it as a real, executable
cumulative-percentage roll, the same `roll_monster_alignment()` shape
this module already established (Phase 176) -- new here rather than in
`advanced_ability.py` itself, since that module is deliberately kept
100% declarative (no functions, no `random` import) and already
imports from this one, so the reverse import would be circular.

**Phase 462 addendum -- the "Duellist merit" monster group, SS17.3.**
`AKGEN_reverse_engineering_report (2).md` SS17.3 quotes the compiled
filter for Captain of the Musketeers/King of Cowards/Bravest of the
Brave merit (`turn/challenge_execution.py _apply_duel_encounter_merit()`,
Phase 443): a personal-combat opponent counts toward these three merit
tallies only when it's another leader, or a monster in the exact
compiled ordinal range `12..21` -- Giant through Witch. `Titan` (11) is
one ordinal short of the range and is deliberately excluded, matching
the source's own "resta fuori per un solo posto dall'intervallo" note.
`DUEL_MERIT_MONSTERS` names this group by species rather than by a bare
ordinal comparison, the same self-documenting convention every other
monster-group set in this module already follows.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum

from ak_engine.models.alignment import Alignment
from ak_engine.models.enums import Ability
from ak_engine.models.temper import Temper


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
class MonsterCombatStats:
    hit_points_range: tuple[int, int]
    melee_skill: int
    melee_damage: tuple[int, int]
    missile_skill: int
    missile_damage: tuple[int, int] | None
    speed: MonsterSpeed


# Phase 154 -- project-original, user-compiled (Desktop/MOSTRI con
# statistiche.txt, 2026-07-15), NOT a Pascal transcription. See module
# docstring's Phase 154 addendum for full provenance, the Spectre
# cross-source discrepancy, and what this table deliberately omits.
MONSTER_COMBAT_STATS: dict[Monster, MonsterCombatStats] = {
    Monster.GRYPHON: MonsterCombatStats((20, 30), 2, (1, 6), 0, None, MonsterSpeed.FAST),
    Monster.GIANT: MonsterCombatStats((20, 30), 1, (1, 7), 1, (1, 7), MonsterSpeed.MEDIUM),
    Monster.GARGOYLE: MonsterCombatStats((10, 20), 1, (1, 6), 0, None, MonsterSpeed.MEDIUM),
    Monster.TROLL: MonsterCombatStats((20, 30), 1, (1, 6), 0, None, MonsterSpeed.MEDIUM),
    Monster.SPECTRE: MonsterCombatStats((12, 22), 1, (1, 6), 0, None, MonsterSpeed.MEDIUM),
    Monster.ELASMOSAURUS: MonsterCombatStats((20, 30), 2, (1, 7), 0, None, MonsterSpeed.FAST),
    Monster.ROC: MonsterCombatStats((30, 35), 2, (1, 7), 0, None, MonsterSpeed.MEDIUM),
    Monster.COUATL: MonsterCombatStats((15, 20), 0, (1, 7), 0, None, MonsterSpeed.FAST),
    Monster.GI_EAGLE: MonsterCombatStats((15, 20), 1, (1, 6), 0, None, MonsterSpeed.FAST),
    Monster.SPHINX: MonsterCombatStats((27, 35), 0, (1, 7), 0, None, MonsterSpeed.MEDIUM),
    Monster.R_DRAGON: MonsterCombatStats((30, 50), 3, (1, 7), 2, (3, 10), MonsterSpeed.SLOW),
    Monster.B_DRAGON: MonsterCombatStats((24, 40), 2, (1, 8), 2, (3, 10), MonsterSpeed.MEDIUM),
    Monster.S_DRAGON: MonsterCombatStats((25, 35), 2, (1, 7), 2, (3, 10), MonsterSpeed.MEDIUM),
    Monster.GO_DRAGON: MonsterCombatStats((32, 38), 2, (1, 7), 2, (3, 10), MonsterSpeed.MEDIUM),
    Monster.GR_DRAGON: MonsterCombatStats((21, 31), 2, (1, 7), 1, (2, 9), MonsterSpeed.MEDIUM),
    Monster.GI_WORM: MonsterCombatStats((28, 42), 1, (1, 7), 0, None, MonsterSpeed.SLOW),
    Monster.TITAN: MonsterCombatStats((34, 50), 2, (1, 8), 2, (3, 8), MonsterSpeed.MEDIUM),
    Monster.BIGFOOT: MonsterCombatStats((18, 25), 1, (1, 7), 0, None, MonsterSpeed.MEDIUM),
    Monster.ARCHER: MonsterCombatStats((9, 12), 1, (1, 6), 3, (3, 9), MonsterSpeed.MEDIUM),
    Monster.SWORDSMAN: MonsterCombatStats((9, 12), 3, (1, 6), 0, None, MonsterSpeed.MEDIUM),
    Monster.WHITE_MAGE: MonsterCombatStats((9, 12), 0, (1, 6), 0, None, MonsterSpeed.MEDIUM),
    Monster.NEC_MAGE: MonsterCombatStats((9, 12), 0, (1, 6), 0, None, MonsterSpeed.MEDIUM),
    Monster.ELE_MAGE: MonsterCombatStats((8, 12), 0, (1, 6), 0, None, MonsterSpeed.MEDIUM),
    Monster.PSY_MAGE: MonsterCombatStats((9, 12), 0, (1, 6), 0, None, MonsterSpeed.MEDIUM),
    Monster.ILL_MAGE: MonsterCombatStats((9, 10), 0, (1, 6), 0, None, MonsterSpeed.MEDIUM),
    Monster.WITCH: MonsterCombatStats((9, 15), 0, (1, 6), 0, None, MonsterSpeed.SLOW),
    Monster.DRYAD: MonsterCombatStats((8, 10), 0, (1, 6), 0, None, MonsterSpeed.MEDIUM),
    Monster.CENTAUR: MonsterCombatStats((10, 16), 1, (1, 6), 2, (3, 8), MonsterSpeed.MEDIUM),
    Monster.GENIE: MonsterCombatStats((18, 23), 1, (1, 6), 0, None, MonsterSpeed.FAST),
    Monster.GOLEM: MonsterCombatStats((22, 40), 3, (1, 6), 0, None, MonsterSpeed.SLOW),
    Monster.BASILISK: MonsterCombatStats((16, 28), 1, (1, 6), 2, (3, 10), MonsterSpeed.SLOW),
    Monster.MEDUSA: MonsterCombatStats((10, 15), 0, (1, 6), 3, (4, 11), MonsterSpeed.MEDIUM),
    Monster.BAL_DEMON: MonsterCombatStats((30, 40), 2, (1, 7), 0, None, MonsterSpeed.MEDIUM),
    Monster.MAR_DEMON: MonsterCombatStats((19, 30), 2, (1, 7), 0, None, MonsterSpeed.MEDIUM),
    Monster.SUCCUBUS: MonsterCombatStats((15, 25), 0, (1, 6), 0, None, MonsterSpeed.FAST),
    Monster.RAKSHASHA: MonsterCombatStats((18, 27), 1, (1, 6), 0, None, MonsterSpeed.MEDIUM),
    Monster.ICE_DEVIL: MonsterCombatStats((28, 36), 2, (1, 6), 0, None, MonsterSpeed.MEDIUM),
    Monster.BONE_DEVIL: MonsterCombatStats((18, 27), 3, (1, 6), 0, None, MonsterSpeed.MEDIUM),
    Monster.IMP: MonsterCombatStats((12, 17), 0, (1, 6), 0, None, MonsterSpeed.FAST),
    Monster.WEREWOLF: MonsterCombatStats((14, 18), 1, (1, 6), 0, None, MonsterSpeed.FAST),
    Monster.CHIMERA: MonsterCombatStats((20, 35), 1, (1, 6), 3, (3, 10), MonsterSpeed.MEDIUM),
    Monster.HYDRA: MonsterCombatStats((14, 25), 1, (1, 7), 0, None, MonsterSpeed.MEDIUM),
    Monster.BEHOLDER: MonsterCombatStats((20, 25), 0, (1, 6), 0, None, MonsterSpeed.FAST),
    Monster.MINOTAUR: MonsterCombatStats((15, 25), 2, (1, 6), 0, None, MonsterSpeed.MEDIUM),
    Monster.GI_WOLVERINE: MonsterCombatStats((12, 17), 1, (1, 6), 0, None, MonsterSpeed.FAST),
    Monster.TREANT: MonsterCombatStats((20, 30), 2, (1, 6), 2, (3, 9), MonsterSpeed.SLOW),
    Monster.GI_AMOEBA: MonsterCombatStats((14, 20), 0, (1, 6), 0, None, MonsterSpeed.SLOW),
    Monster.GI_P_MANTIS: MonsterCombatStats((12, 19), 2, (1, 6), 0, None, MonsterSpeed.FAST),
    Monster.GI_SCORPION: MonsterCombatStats((10, 15), 0, (1, 6), 0, None, MonsterSpeed.MEDIUM),
    Monster.GI_WASP: MonsterCombatStats((8, 9), 1, (1, 6), 0, None, MonsterSpeed.FAST),
    Monster.GI_SPIDER: MonsterCombatStats((11, 12), 0, (1, 6), 0, None, MonsterSpeed.MEDIUM),
    Monster.GHOST: MonsterCombatStats((14, 22), 1, (1, 6), 0, None, MonsterSpeed.MEDIUM),
    Monster.VAMPIRE: MonsterCombatStats((12, 26), 1, (1, 6), 0, None, MonsterSpeed.FAST),
    Monster.MUMMY: MonsterCombatStats((15, 30), 1, (1, 6), 0, None, MonsterSpeed.SLOW),
    Monster.BANSHEE: MonsterCombatStats((10, 20), 1, (1, 6), 0, None, MonsterSpeed.MEDIUM),
    Monster.LICH: MonsterCombatStats((22, 30), 0, (1, 6), 0, None, MonsterSpeed.MEDIUM),
    Monster.GI_OCTOPUS: MonsterCombatStats((17, 18), 1, (1, 6), 0, None, MonsterSpeed.MEDIUM),
    Monster.GI_CLAM: MonsterCombatStats((14, 27), 0, (1, 6), 0, None, MonsterSpeed.SLOW),
    Monster.GW_WHALE: MonsterCombatStats((25, 35), 2, (1, 8), 0, None, MonsterSpeed.MEDIUM),
    Monster.MERMAID: MonsterCombatStats((8, 11), 0, (1, 6), 0, None, MonsterSpeed.MEDIUM),
}


class MonsterIntelligence(Enum):
    """CTME.PAS `mintel` -- a species' own compiled intelligence tier,
    six real values (`Semi`/`Low`/`Medium`/`High`/`Godlike`/`Mech`,
    ``MECH`` reserved for the sole mechanical species, `Golem`). See
    module docstring's own Phase 381 addendum. Distinct from `models/
    magic_feature.py`-style intelligence concepts elsewhere in this
    project -- this one is monster-specific runtime data.
    """

    SEMI = "Semi"
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    GODLIKE = "Godlike"
    MECH = "Mech"


# Phase 382 -- `runtime_mechanics.monster_talk.reply_selection`'s own
# eligibility test ("abs(monster_intelligence-repint[id]) <= rivar[id]")
# needs a numeric ordinal for `MonsterIntelligence`, the same way
# `models/alignment.py ALIGNMENT_ORDINAL` already gives `Alignment` one
# for the matching view-distance test. The 5 real tiers this table's
# own `repint` column actually uses (`Semi`..`Godlike`) form a genuine
# ladder, confirmed by which species land where (animals/beasts at
# `SEMI`/`LOW`, humans/centaurs at `MEDIUM`, most demons/dragons/undead
# at `HIGH`, the handful of named-genius species -- Couatl, Titan,
# Genie, Go Dragon, Lich, Balrog -- at `GODLIKE`).
#
# Phase 504 -- the real Pascal source (Desktop's Gioco/HostAK/TP/
# CTBOTH.PAS, `type intlevel = (Mech,Semi,Low,Medium,High,Godlike);`)
# confirms `MECH` is the enum's own *first* member, ordinal 0, not a
# placeholder tacked on after `GODLIKE`. `MECH` still never appears in
# `repint` (only `Golem`/`Giant Amoeba` carry it as their own `mintel`,
# confirmed against `CTME.PAS`'s own `mintel` array positions for those
# two species), so this only changes Talk-reply eligibility distance
# for those two species; the other 5 tiers keep the same relative
# spacing (uniformly shifted by +1), so no other species' behavior
# changes.
MONSTER_INTELLIGENCE_ORDINAL: dict[MonsterIntelligence, int] = {
    MonsterIntelligence.MECH: 0,
    MonsterIntelligence.SEMI: 1,
    MonsterIntelligence.LOW: 2,
    MonsterIntelligence.MEDIUM: 3,
    MonsterIntelligence.HIGH: 4,
    MonsterIntelligence.GODLIKE: 5,
}


@dataclass(frozen=True, slots=True)
class MonsterRuntimeProfile:
    average_hit_points: int
    melee_skill: int
    melee_damage_parameter: int
    missile_skill: int
    missile_damage_parameter: int
    speed: MonsterSpeed
    temper: Temper
    intelligence: MonsterIntelligence
    base_view: Alignment
    view_variation: int
    base_gold_parameter: int
    can_offer_mate_quest: bool


# **Phase 381** -- `AKGEN_embedded_catalogs.json.txt tables.monster_
# profiles` (a real static disassembly of AKGEN.EXE/AK.EXE, `CTME.PAS`'s
# own compiled `mt*`/`m*` runtime constants) gives real per-species data
# for all 60 species that `MONSTER_COMBAT_STATS`'s own Phase 154 module
# docstring explicitly says is "not in any available source (rulebook,
# Pascal, or the 10 real move files)" -- this table is that real source,
# now that it exists. **Deliberately additive, not a replacement**:
# `MONSTER_COMBAT_STATS` (Phase 154, project-original, user-compiled)
# is left completely untouched and still backs every existing combat
# consumer -- swapping live gameplay values to this newly-confirmed
# runtime layer is a separate, larger decision this phase does not make
# unilaterally, consistent with this project's own "empirically verify
# before changing live behavior" standard. Two fields the JSON's own
# `monster_profiles.entries` also carries are deliberately NOT
# duplicated here because this project already has them, cross-checked
# exact for every one of the 60 species before being left out:
# `minimum_druidism_to_talk_talkdiff` (== `turn/encounter.py TALK_
# MONSTER_DRUID_LEVEL_REQUIRED`) and `feature_range` (== `models/
# feature.py MONSTER_GUARDED_FEATURE_TYPES`, Phase 79). Likewise
# `melee_weapon_mtweap1`/`missile_weapon_mtrweap` are omitted -- both
# already match `models/weapon.py MONSTER_MELEE_WEAPON`/`MONSTER_
# RANGED_WEAPON` (Phase 94) exactly, confirmed species-by-species.
#
# `base_view_mview`'s own 9 real values (`Heavenly`/`Good`/`Druidic`/
# `Worldly`/`Animal`/`Evil`/`Hellish`/`Undead`/`Mechanical`) are an
# exact, independent match for `models/alignment.py Alignment`'s own
# 9-of-10 real Pascal `outlook` names (everything but `Special`,
# `models/alignment.py`'s own Phase 80 docstring) -- reused directly
# rather than inventing a parallel enum; `view_variation_mvvar` is the
# raw modifier CTME.PAS applies on top of that base view and is kept as
# a plain int, its own exact effect unconfirmed by this source.
# `temper_mtemper`'s 4 values and `speed`'s 3 values are likewise an
# exact match for this module's own pre-existing `Temper`/`MonsterSpeed`
# enums, reused directly.
#
# **30 of these 60 entries carry a real, sourced `source_conflicts` note
# in the JSON** where this runtime layer disagrees with the separate
# `documented_profile` layer (`Mostri.md`, the same lineage `MONSTER_
# COMBAT_STATS` itself descends from) -- e.g. Roc: runtime Melee skill 1
# vs. documented 2; Sphinx: runtime average HP 20 vs. documented range
# 13-16. Both sides are real, sourced numbers describing two different
# documented layers of the same compiled engine, not a typo in either
# -- this table stores only the `runtime`/CTME.PAS side; it makes no
# attempt to reconcile or silently prefer one over the other.
MONSTER_RUNTIME_PROFILE: dict[Monster, MonsterRuntimeProfile] = {
    Monster.ROC: MonsterRuntimeProfile(30, 1, 12, 0, 0, MonsterSpeed.FAST, Temper.BRAVE, MonsterIntelligence.SEMI, Alignment.PAGAN, 0, 2, True),
    Monster.GRYPHON: MonsterRuntimeProfile(25, 1, 8, 0, 0, MonsterSpeed.FAST, Temper.BERSERK, MonsterIntelligence.LOW, Alignment.PAGAN, 0, 1, True),
    Monster.COUATL: MonsterRuntimeProfile(20, 3, 6, 0, 0, MonsterSpeed.FAST, Temper.BRAVE, MonsterIntelligence.GODLIKE, Alignment.GOOD, 1, 4, True),
    Monster.GI_EAGLE: MonsterRuntimeProfile(15, 2, 6, 0, 0, MonsterSpeed.FAST, Temper.BRAVE, MonsterIntelligence.MEDIUM, Alignment.NEUTRAL, 1, 1, True),
    Monster.SPHINX: MonsterRuntimeProfile(25, 2, 8, 0, 0, MonsterSpeed.FAST, Temper.BERSERK, MonsterIntelligence.HIGH, Alignment.NEUTRAL, 1, 6, True),
    Monster.R_DRAGON: MonsterRuntimeProfile(35, 3, 10, 2, 12, MonsterSpeed.FAST, Temper.BRAVE, MonsterIntelligence.HIGH, Alignment.EVIL, 1, 10, True),
    Monster.B_DRAGON: MonsterRuntimeProfile(30, 2, 8, 2, 10, MonsterSpeed.FAST, Temper.CAUTIOUS, MonsterIntelligence.MEDIUM, Alignment.EVIL, 1, 8, True),
    Monster.GR_DRAGON: MonsterRuntimeProfile(25, 2, 6, 2, 7, MonsterSpeed.FAST, Temper.COWARDLY, MonsterIntelligence.HIGH, Alignment.PAGAN, 1, 6, True),
    Monster.S_DRAGON: MonsterRuntimeProfile(30, 2, 9, 2, 10, MonsterSpeed.FAST, Temper.CAUTIOUS, MonsterIntelligence.HIGH, Alignment.DRUID, 1, 9, True),
    Monster.GO_DRAGON: MonsterRuntimeProfile(40, 3, 12, 2, 15, MonsterSpeed.FAST, Temper.BRAVE, MonsterIntelligence.GODLIKE, Alignment.GOOD, 1, 12, True),
    Monster.GI_WORM: MonsterRuntimeProfile(35, 0, 15, 0, 0, MonsterSpeed.MEDIUM, Temper.BRAVE, MonsterIntelligence.SEMI, Alignment.PAGAN, 0, 6, True),
    Monster.TITAN: MonsterRuntimeProfile(40, 4, 20, 0, 0, MonsterSpeed.FAST, Temper.BRAVE, MonsterIntelligence.GODLIKE, Alignment.GOOD, 1, 12, True),
    Monster.GIANT: MonsterRuntimeProfile(25, 1, 10, 1, 10, MonsterSpeed.MEDIUM, Temper.BRAVE, MonsterIntelligence.LOW, Alignment.NEUTRAL, 1, 4, True),
    Monster.BIGFOOT: MonsterRuntimeProfile(18, 0, 8, 0, 0, MonsterSpeed.MEDIUM, Temper.CAUTIOUS, MonsterIntelligence.LOW, Alignment.PAGAN, 1, 1, True),
    Monster.ARCHER: MonsterRuntimeProfile(10, 1, 6, 3, 6, MonsterSpeed.MEDIUM, Temper.BRAVE, MonsterIntelligence.MEDIUM, Alignment.NEUTRAL, 2, 3, False),
    Monster.SWORDSMAN: MonsterRuntimeProfile(10, 3, 6, 0, 0, MonsterSpeed.MEDIUM, Temper.BERSERK, MonsterIntelligence.MEDIUM, Alignment.NEUTRAL, 2, 3, False),
    Monster.WHITE_MAGE: MonsterRuntimeProfile(10, 1, 6, 0, 0, MonsterSpeed.MEDIUM, Temper.CAUTIOUS, MonsterIntelligence.HIGH, Alignment.NEUTRAL, 2, 4, False),
    Monster.NEC_MAGE: MonsterRuntimeProfile(10, 1, 6, 0, 0, MonsterSpeed.MEDIUM, Temper.CAUTIOUS, MonsterIntelligence.HIGH, Alignment.NEUTRAL, 2, 5, False),
    Monster.ELE_MAGE: MonsterRuntimeProfile(10, 1, 6, 0, 0, MonsterSpeed.MEDIUM, Temper.CAUTIOUS, MonsterIntelligence.HIGH, Alignment.NEUTRAL, 2, 4, False),
    Monster.PSY_MAGE: MonsterRuntimeProfile(10, 1, 6, 0, 0, MonsterSpeed.MEDIUM, Temper.CAUTIOUS, MonsterIntelligence.HIGH, Alignment.NEUTRAL, 2, 5, False),
    Monster.ILL_MAGE: MonsterRuntimeProfile(10, 1, 6, 0, 0, MonsterSpeed.MEDIUM, Temper.CAUTIOUS, MonsterIntelligence.HIGH, Alignment.NEUTRAL, 2, 4, False),
    Monster.WITCH: MonsterRuntimeProfile(10, 1, 4, 0, 0, MonsterSpeed.SLOW, Temper.CAUTIOUS, MonsterIntelligence.HIGH, Alignment.PAGAN, 1, 6, False),
    Monster.DRYAD: MonsterRuntimeProfile(10, 0, 4, 0, 0, MonsterSpeed.MEDIUM, Temper.CAUTIOUS, MonsterIntelligence.HIGH, Alignment.NEUTRAL, 1, 2, False),
    Monster.CENTAUR: MonsterRuntimeProfile(12, 1, 6, 2, 6, MonsterSpeed.FAST, Temper.BRAVE, MonsterIntelligence.MEDIUM, Alignment.NEUTRAL, 1, 2, True),
    Monster.GENIE: MonsterRuntimeProfile(20, 2, 8, 0, 0, MonsterSpeed.MEDIUM, Temper.BRAVE, MonsterIntelligence.GODLIKE, Alignment.DIVINE, 1, 6, False),
    Monster.GOLEM: MonsterRuntimeProfile(25, 2, 10, 0, 0, MonsterSpeed.SLOW, Temper.BERSERK, MonsterIntelligence.MECH, Alignment.MECHANICAL, 0, 6, False),
    Monster.GARGOYLE: MonsterRuntimeProfile(15, 1, 8, 0, 0, MonsterSpeed.MEDIUM, Temper.BERSERK, MonsterIntelligence.LOW, Alignment.EVIL, 0, 2, True),
    Monster.BASILISK: MonsterRuntimeProfile(20, 1, 8, 2, 15, MonsterSpeed.SLOW, Temper.BRAVE, MonsterIntelligence.SEMI, Alignment.PAGAN, 0, 2, True),
    Monster.MEDUSA: MonsterRuntimeProfile(10, 0, 4, 2, 15, MonsterSpeed.SLOW, Temper.CAUTIOUS, MonsterIntelligence.MEDIUM, Alignment.PAGAN, 1, 3, False),
    Monster.BAL_DEMON: MonsterRuntimeProfile(30, 3, 12, 0, 0, MonsterSpeed.FAST, Temper.BERSERK, MonsterIntelligence.GODLIKE, Alignment.ANTI_HOLY, 0, 8, False),
    Monster.MAR_DEMON: MonsterRuntimeProfile(25, 4, 10, 0, 0, MonsterSpeed.MEDIUM, Temper.BRAVE, MonsterIntelligence.HIGH, Alignment.ANTI_HOLY, 0, 10, False),
    Monster.SUCCUBUS: MonsterRuntimeProfile(20, 1, 6, 0, 0, MonsterSpeed.FAST, Temper.CAUTIOUS, MonsterIntelligence.HIGH, Alignment.EVIL, 1, 5, False),
    Monster.RAKSHASHA: MonsterRuntimeProfile(25, 2, 8, 0, 0, MonsterSpeed.FAST, Temper.BRAVE, MonsterIntelligence.HIGH, Alignment.EVIL, 1, 4, True),
    Monster.ICE_DEVIL: MonsterRuntimeProfile(30, 3, 12, 0, 0, MonsterSpeed.SLOW, Temper.BERSERK, MonsterIntelligence.HIGH, Alignment.ANTI_HOLY, 0, 9, True),
    Monster.BONE_DEVIL: MonsterRuntimeProfile(20, 2, 8, 0, 0, MonsterSpeed.MEDIUM, Temper.BRAVE, MonsterIntelligence.HIGH, Alignment.ANTI_HOLY, 0, 7, False),
    Monster.IMP: MonsterRuntimeProfile(12, 1, 6, 0, 0, MonsterSpeed.MEDIUM, Temper.CAUTIOUS, MonsterIntelligence.HIGH, Alignment.ANTI_HOLY, 1, 1, False),
    Monster.WEREWOLF: MonsterRuntimeProfile(12, 1, 6, 0, 0, MonsterSpeed.MEDIUM, Temper.BERSERK, MonsterIntelligence.MEDIUM, Alignment.PAGAN, 1, 2, True),
    Monster.CHIMERA: MonsterRuntimeProfile(25, 2, 10, 2, 10, MonsterSpeed.FAST, Temper.BRAVE, MonsterIntelligence.SEMI, Alignment.EVIL, 0, 6, True),
    Monster.HYDRA: MonsterRuntimeProfile(20, 2, 6, 0, 0, MonsterSpeed.SLOW, Temper.BRAVE, MonsterIntelligence.HIGH, Alignment.PAGAN, 1, 7, True),
    Monster.BEHOLDER: MonsterRuntimeProfile(25, 1, 8, 0, 0, MonsterSpeed.SLOW, Temper.CAUTIOUS, MonsterIntelligence.SEMI, Alignment.PAGAN, 1, 5, True),
    Monster.TROLL: MonsterRuntimeProfile(25, 1, 8, 0, 0, MonsterSpeed.MEDIUM, Temper.BERSERK, MonsterIntelligence.LOW, Alignment.EVIL, 0, 3, True),
    Monster.MINOTAUR: MonsterRuntimeProfile(20, 1, 8, 0, 0, MonsterSpeed.SLOW, Temper.BERSERK, MonsterIntelligence.LOW, Alignment.PAGAN, 1, 4, False),
    Monster.GI_WOLVERINE: MonsterRuntimeProfile(20, 2, 8, 0, 0, MonsterSpeed.FAST, Temper.BERSERK, MonsterIntelligence.SEMI, Alignment.PAGAN, 1, 2, True),
    Monster.TREANT: MonsterRuntimeProfile(25, 1, 15, 0, 0, MonsterSpeed.MEDIUM, Temper.CAUTIOUS, MonsterIntelligence.HIGH, Alignment.DRUID, 1, 1, True),
    Monster.GI_AMOEBA: MonsterRuntimeProfile(15, 0, 4, 0, 0, MonsterSpeed.SLOW, Temper.BERSERK, MonsterIntelligence.MECH, Alignment.MECHANICAL, 0, 2, False),
    Monster.GI_P_MANTIS: MonsterRuntimeProfile(15, 2, 6, 0, 0, MonsterSpeed.MEDIUM, Temper.BRAVE, MonsterIntelligence.SEMI, Alignment.PAGAN, 1, 1, False),
    Monster.GI_SCORPION: MonsterRuntimeProfile(10, 1, 8, 0, 0, MonsterSpeed.MEDIUM, Temper.BERSERK, MonsterIntelligence.SEMI, Alignment.PAGAN, 1, 1, False),
    Monster.GI_WASP: MonsterRuntimeProfile(10, 1, 8, 0, 0, MonsterSpeed.FAST, Temper.BRAVE, MonsterIntelligence.SEMI, Alignment.PAGAN, 1, 1, False),
    Monster.GI_SPIDER: MonsterRuntimeProfile(10, 1, 6, 0, 0, MonsterSpeed.MEDIUM, Temper.CAUTIOUS, MonsterIntelligence.SEMI, Alignment.PAGAN, 1, 2, True),
    Monster.GHOST: MonsterRuntimeProfile(15, 1, 6, 0, 0, MonsterSpeed.MEDIUM, Temper.CAUTIOUS, MonsterIntelligence.HIGH, Alignment.UNDEAD, 0, 3, True),
    Monster.VAMPIRE: MonsterRuntimeProfile(20, 2, 8, 0, 0, MonsterSpeed.MEDIUM, Temper.BRAVE, MonsterIntelligence.HIGH, Alignment.UNDEAD, 0, 6, True),
    Monster.MUMMY: MonsterRuntimeProfile(20, 1, 8, 0, 0, MonsterSpeed.SLOW, Temper.BRAVE, MonsterIntelligence.HIGH, Alignment.UNDEAD, 0, 8, True),
    Monster.BANSHEE: MonsterRuntimeProfile(15, 1, 4, 2, 8, MonsterSpeed.MEDIUM, Temper.CAUTIOUS, MonsterIntelligence.HIGH, Alignment.UNDEAD, 0, 2, False),
    Monster.LICH: MonsterRuntimeProfile(25, 1, 6, 0, 0, MonsterSpeed.SLOW, Temper.CAUTIOUS, MonsterIntelligence.GODLIKE, Alignment.UNDEAD, 1, 8, True),
    Monster.SPECTRE: MonsterRuntimeProfile(20, 1, 6, 0, 0, MonsterSpeed.MEDIUM, Temper.BRAVE, MonsterIntelligence.HIGH, Alignment.UNDEAD, 0, 6, True),
    Monster.GI_OCTOPUS: MonsterRuntimeProfile(25, 1, 8, 0, 0, MonsterSpeed.MEDIUM, Temper.BRAVE, MonsterIntelligence.SEMI, Alignment.PAGAN, 0, 8, True),
    Monster.GI_CLAM: MonsterRuntimeProfile(20, 0, 8, 0, 0, MonsterSpeed.SLOW, Temper.CAUTIOUS, MonsterIntelligence.SEMI, Alignment.PAGAN, 0, 6, True),
    Monster.ELASMOSAURUS: MonsterRuntimeProfile(25, 2, 10, 0, 0, MonsterSpeed.FAST, Temper.BRAVE, MonsterIntelligence.SEMI, Alignment.PAGAN, 0, 4, True),
    Monster.GW_WHALE: MonsterRuntimeProfile(30, 3, 12, 0, 0, MonsterSpeed.FAST, Temper.BRAVE, MonsterIntelligence.LOW, Alignment.DRUID, 1, 2, True),
    Monster.MERMAID: MonsterRuntimeProfile(10, 1, 6, 0, 0, MonsterSpeed.FAST, Temper.CAUTIOUS, MonsterIntelligence.MEDIUM, Alignment.DRUID, 1, 1, False),
}


@dataclass(frozen=True, slots=True)
class AlignmentOption:
    alignment: Alignment
    percent: int  # e.g. 50 for "50%"; every species' own tuple sums to 100


# Phase 176 -- project-original, same Desktop/MOSTRI con statistiche.txt
# source as MONSTER_COMBAT_STATS (Phase 154). See module docstring's own
# Phase 176 addendum for the user's exact quote and design rationale.
MONSTER_ALIGNMENT_DISTRIBUTION: dict[Monster, tuple[AlignmentOption, ...]] = {
    Monster.GRYPHON: (AlignmentOption(Alignment.NEUTRAL, 100),),
    Monster.GIANT: (AlignmentOption(Alignment.NEUTRAL, 50), AlignmentOption(Alignment.PAGAN, 50)),
    Monster.GARGOYLE: (AlignmentOption(Alignment.EVIL, 100),),
    Monster.TROLL: (AlignmentOption(Alignment.EVIL, 100),),
    Monster.SPECTRE: (AlignmentOption(Alignment.ANTI_HOLY, 100),),
    Monster.ELASMOSAURUS: (AlignmentOption(Alignment.NEUTRAL, 100),),
    Monster.ROC: (AlignmentOption(Alignment.DRUID, 50), AlignmentOption(Alignment.NEUTRAL, 50)),
    Monster.COUATL: (AlignmentOption(Alignment.DIVINE, 100),),
    Monster.GI_EAGLE: (AlignmentOption(Alignment.DRUID, 50), AlignmentOption(Alignment.NEUTRAL, 50)),
    Monster.SPHINX: (AlignmentOption(Alignment.EVIL, 100),),
    Monster.R_DRAGON: (AlignmentOption(Alignment.EVIL, 100),),
    Monster.B_DRAGON: (AlignmentOption(Alignment.EVIL, 100),),
    Monster.S_DRAGON: (AlignmentOption(Alignment.GOOD, 50), AlignmentOption(Alignment.DRUID, 50)),
    Monster.GO_DRAGON: (AlignmentOption(Alignment.GOOD, 100),),
    Monster.GR_DRAGON: (AlignmentOption(Alignment.NEUTRAL, 50), AlignmentOption(Alignment.EVIL, 50)),
    Monster.GI_WORM: (AlignmentOption(Alignment.NEUTRAL, 100),),
    Monster.TITAN: (AlignmentOption(Alignment.DRUID, 100),),
    Monster.BIGFOOT: (AlignmentOption(Alignment.EVIL, 50), AlignmentOption(Alignment.PAGAN, 50)),
    Monster.ARCHER: (AlignmentOption(Alignment.EVIL, 100),),
    Monster.SWORDSMAN: (AlignmentOption(Alignment.NEUTRAL, 50), AlignmentOption(Alignment.EVIL, 50)),
    Monster.WHITE_MAGE: (
        AlignmentOption(Alignment.GOOD, 40),
        AlignmentOption(Alignment.DRUID, 30),
        AlignmentOption(Alignment.NEUTRAL, 30),
    ),
    Monster.NEC_MAGE: (
        AlignmentOption(Alignment.EVIL, 40),
        AlignmentOption(Alignment.PAGAN, 30),
        AlignmentOption(Alignment.NEUTRAL, 30),
    ),
    Monster.ELE_MAGE: (AlignmentOption(Alignment.NEUTRAL, 50), AlignmentOption(Alignment.DRUID, 50)),
    Monster.PSY_MAGE: (AlignmentOption(Alignment.GOOD, 100),),
    Monster.ILL_MAGE: (AlignmentOption(Alignment.DRUID, 100),),
    Monster.WITCH: (AlignmentOption(Alignment.EVIL, 100),),
    Monster.DRYAD: (AlignmentOption(Alignment.DRUID, 100),),
    Monster.CENTAUR: (AlignmentOption(Alignment.GOOD, 50), AlignmentOption(Alignment.DRUID, 50)),
    Monster.GENIE: (AlignmentOption(Alignment.GOOD, 100),),
    Monster.GOLEM: (AlignmentOption(Alignment.NEUTRAL, 100),),
    Monster.BASILISK: (AlignmentOption(Alignment.EVIL, 50), AlignmentOption(Alignment.PAGAN, 50)),
    Monster.MEDUSA: (AlignmentOption(Alignment.NEUTRAL, 100),),
    Monster.BAL_DEMON: (AlignmentOption(Alignment.ANTI_HOLY, 100),),
    Monster.MAR_DEMON: (AlignmentOption(Alignment.ANTI_HOLY, 100),),
    Monster.SUCCUBUS: (AlignmentOption(Alignment.ANTI_HOLY, 100),),
    Monster.RAKSHASHA: (AlignmentOption(Alignment.ANTI_HOLY, 100),),
    Monster.ICE_DEVIL: (AlignmentOption(Alignment.ANTI_HOLY, 100),),
    Monster.BONE_DEVIL: (AlignmentOption(Alignment.ANTI_HOLY, 100),),
    Monster.IMP: (AlignmentOption(Alignment.ANTI_HOLY, 100),),
    Monster.WEREWOLF: (AlignmentOption(Alignment.PAGAN, 100),),
    Monster.CHIMERA: (AlignmentOption(Alignment.EVIL, 100),),
    Monster.HYDRA: (AlignmentOption(Alignment.EVIL, 50), AlignmentOption(Alignment.PAGAN, 50)),
    Monster.BEHOLDER: (AlignmentOption(Alignment.EVIL, 100),),
    Monster.MINOTAUR: (AlignmentOption(Alignment.EVIL, 100),),
    Monster.GI_WOLVERINE: (AlignmentOption(Alignment.NEUTRAL, 100),),
    Monster.TREANT: (AlignmentOption(Alignment.DRUID, 100),),
    Monster.GI_AMOEBA: (AlignmentOption(Alignment.NEUTRAL, 100),),
    Monster.GI_P_MANTIS: (AlignmentOption(Alignment.EVIL, 100),),
    Monster.GI_SCORPION: (AlignmentOption(Alignment.NEUTRAL, 100),),
    Monster.GI_WASP: (AlignmentOption(Alignment.EVIL, 100),),
    Monster.GI_SPIDER: (AlignmentOption(Alignment.NEUTRAL, 100),),
    Monster.GHOST: (AlignmentOption(Alignment.ANTI_HOLY, 100),),
    Monster.VAMPIRE: (AlignmentOption(Alignment.ANTI_HOLY, 100),),
    Monster.MUMMY: (AlignmentOption(Alignment.ANTI_HOLY, 100),),
    Monster.BANSHEE: (AlignmentOption(Alignment.ANTI_HOLY, 100),),
    Monster.LICH: (AlignmentOption(Alignment.ANTI_HOLY, 100),),
    Monster.GI_OCTOPUS: (AlignmentOption(Alignment.NEUTRAL, 50), AlignmentOption(Alignment.PAGAN, 50)),
    Monster.GI_CLAM: (AlignmentOption(Alignment.NEUTRAL, 100),),
    Monster.GW_WHALE: (AlignmentOption(Alignment.DRUID, 50), AlignmentOption(Alignment.NEUTRAL, 50)),
    Monster.MERMAID: (AlignmentOption(Alignment.GOOD, 50), AlignmentOption(Alignment.DRUID, 50)),
}


def roll_monster_alignment(monster: Monster, rng: random.Random) -> Alignment | None:
    """Assigns a placed monster's Alignment per ``MONSTER_ALIGNMENT_DISTRIBUTION``.

    Returns ``None`` for a species with no recorded distribution (only
    ``Monster.NOMONSTER``, the sentinel). For a single-option species,
    returns that option directly **without consuming any roll** -- the
    user's own confirmation (module docstring's Phase 176 addendum)
    specifically scopes the roll to "quelli che hanno due o tre
    allineamenti" (those with two or three alignments). For a 2-or-3-
    option species, consumes exactly one ``rng.random()`` call and walks
    the options in the source's own listed order via cumulative
    percentage thresholds, so the last option always covers any
    floating-point roundoff at the top of the range instead of falling
    through to ``None``.
    """

    options = MONSTER_ALIGNMENT_DISTRIBUTION.get(monster)
    if options is None:
        return None
    if len(options) == 1:
        return options[0].alignment

    roll = rng.random() * 100
    cumulative = 0
    for option in options[:-1]:
        cumulative += option.percent
        if roll < cumulative:
            return option.alignment
    return options[-1].alignment


# "Gate Demon" spell's own d100 roster table (Phase 202, user-supplied,
# turn/encounter.py's own docstring addendum). Restates ``models/
# advanced_ability.py GATE_DEMON_TABLE`` (a display-label-only string
# table, e.g. ``("1-20", Monster.IMP)``) as cumulative percentages for
# ``roll_gate_demon_type()`` below -- imported the other way around
# would be circular (``advanced_ability.py`` already imports from this
# module). ``GATE_DEMON_TABLE``'s own "20-40" label for Succubus (one
# off from "21-40") is a source-text quirk, kept verbatim there per
# this project's convention; this table uses the real, non-overlapping
# 20/20/15/15/10/10/10 percentages the ranges actually describe, which
# sum to exactly 100.
GATE_DEMON_TYPE_PERCENT: tuple[tuple[Monster, float], ...] = (
    (Monster.IMP, 20),
    (Monster.SUCCUBUS, 20),
    (Monster.BONE_DEVIL, 15),
    (Monster.ICE_DEVIL, 15),
    (Monster.MAR_DEMON, 10),
    (Monster.RAKSHASHA, 10),
    (Monster.BAL_DEMON, 10),
)


def roll_gate_demon_type(rng: random.Random) -> Monster:
    """Which of the seven demon species Gate Demon summons -- same cumulative-
    percentage-walk shape as ``roll_monster_alignment()`` above
    (``rng.random() * 100``, strict ``<`` per step, last entry catches
    any floating-point roundoff at the top of the range).
    """

    roll = rng.random() * 100
    cumulative = 0.0
    for monster, percent in GATE_DEMON_TYPE_PERCENT[:-1]:
        cumulative += percent
        if roll < cumulative:
            return monster
    return GATE_DEMON_TYPE_PERCENT[-1][0]


# Phase 177 -- project-original, same Desktop/MOSTRI con statistiche.txt
# source as MONSTER_COMBAT_STATS (Phase 154) and MONSTER_ALIGNMENT_
# DISTRIBUTION (Phase 176). See module docstring's own Phase 177
# addendum for the WH/NE/EL/PS/IL abbreviation mapping and why only 29
# of the 60 species appear here (the other 31 genuinely have none).
MONSTER_MAGIC_ABILITIES: dict[Monster, dict[Ability, int]] = {
    Monster.SPECTRE: {Ability.NECROMANCY: 1},
    Monster.COUATL: {Ability.PSYCHIC: 3},
    Monster.SPHINX: {Ability.NECROMANCY: 2},
    Monster.B_DRAGON: {Ability.PSYCHIC: 2},
    Monster.S_DRAGON: {Ability.WHITE: 3, Ability.PSYCHIC: 3, Ability.ELEMENTAL: 3, Ability.ILLUSION: 2},
    Monster.GO_DRAGON: {Ability.WHITE: 4, Ability.NECROMANCY: 4},
    Monster.GR_DRAGON: {Ability.PSYCHIC: 3, Ability.ILLUSION: 2, Ability.ELEMENTAL: 1},
    Monster.TITAN: {Ability.WHITE: 4, Ability.ILLUSION: 3, Ability.ELEMENTAL: 3, Ability.NECROMANCY: 2},
    Monster.SWORDSMAN: {Ability.ILLUSION: 1},
    Monster.WHITE_MAGE: {Ability.WHITE: 3, Ability.NECROMANCY: 2, Ability.ILLUSION: 2},
    Monster.NEC_MAGE: {Ability.NECROMANCY: 3},
    Monster.ELE_MAGE: {Ability.ELEMENTAL: 3},
    Monster.PSY_MAGE: {Ability.PSYCHIC: 3, Ability.WHITE: 2, Ability.ILLUSION: 2},
    Monster.ILL_MAGE: {Ability.ILLUSION: 3, Ability.PSYCHIC: 2},
    Monster.WITCH: {Ability.NECROMANCY: 3, Ability.PSYCHIC: 2},
    Monster.DRYAD: {Ability.PSYCHIC: 3},
    Monster.GENIE: {Ability.ILLUSION: 3, Ability.PSYCHIC: 2},
    Monster.BAL_DEMON: {Ability.NECROMANCY: 3},
    Monster.MAR_DEMON: {Ability.PSYCHIC: 4, Ability.ILLUSION: 2},
    Monster.SUCCUBUS: {Ability.PSYCHIC: 3},
    Monster.RAKSHASHA: {Ability.ILLUSION: 3, Ability.NECROMANCY: 2},
    Monster.ICE_DEVIL: {Ability.PSYCHIC: 3, Ability.ELEMENTAL: 2},
    Monster.BONE_DEVIL: {Ability.NECROMANCY: 3},
    Monster.IMP: {Ability.ILLUSION: 2},
    Monster.BEHOLDER: {Ability.NECROMANCY: 4, Ability.PSYCHIC: 4},
    Monster.VAMPIRE: {Ability.PSYCHIC: 3},
    Monster.BANSHEE: {Ability.PSYCHIC: 2},
    Monster.LICH: {Ability.NECROMANCY: 4},
    Monster.MERMAID: {Ability.ELEMENTAL: 1, Ability.PSYCHIC: 1, Ability.NECROMANCY: 1},
}


# Phase 182 -- project-original, user-supplied while defining
# turn/encounter.py's Spiritwrack [SP] spell. See module docstring's
# own Phase 182 addendum for the full quote and why this is kept
# separate from `Alignment.UNDEAD`/`Alignment.MECHANICAL` (neither is
# actually used in MONSTER_ALIGNMENT_DISTRIBUTION above).
SPIRITWRACK_UNDEAD_MONSTERS: frozenset[Monster] = frozenset(
    {
        Monster.SPECTRE,
        Monster.GHOST,
        Monster.VAMPIRE,
        Monster.MUMMY,
        Monster.BANSHEE,
        Monster.LICH,
    }
)

SPIRITWRACK_MECHANICAL_MONSTERS: frozenset[Monster] = frozenset(
    {
        Monster.GOLEM,
        Monster.GARGOYLE,
    }
)

SPIRITWRACK_ANIMAL_INTELLIGENCE_MONSTERS: frozenset[Monster] = frozenset(
    {
        Monster.GRYPHON,
        Monster.ELASMOSAURUS,
        Monster.GI_WORM,
        Monster.GI_WOLVERINE,
        Monster.GI_AMOEBA,
        Monster.GI_P_MANTIS,
        Monster.GI_SCORPION,
        Monster.GI_WASP,
        Monster.GI_SPIDER,
        Monster.GI_OCTOPUS,
        Monster.GI_CLAM,
        Monster.GW_WHALE,
    }
)


# Phase 185 -- project-original, user-supplied while defining
# turn/encounter.py's Telekinetic Storm [TE] spell. See module
# docstring's own Phase 185 addendum for the full quote and why this
# is a fourth, independent classification axis. Renamed from
# TELEKINETIC_STORM_SUBMARINE_MONSTERS in Phase 188, when Fireball [FI]
# was confirmed to reuse this exact same category.
SUBMARINE_MONSTERS: frozenset[Monster] = frozenset(
    {
        Monster.ELASMOSAURUS,
        Monster.GI_OCTOPUS,
        Monster.GI_CLAM,
        Monster.GW_WHALE,
        Monster.MERMAID,
    }
)


# Phase 189 -- project-original, user-supplied while defining
# turn/encounter.py's Ice Suspension [IC] spell. See module docstring's
# own Phase 189 addendum for why this stays spell-prefixed (unlike
# Phase 188's SUBMARINE_MONSTERS unification).
ICE_SUSPENSION_IMMUNE_MONSTERS: frozenset[Monster] = frozenset(
    {
        Monster.SPECTRE,
        Monster.GENIE,
        Monster.BAL_DEMON,
        Monster.MAR_DEMON,
        Monster.SUCCUBUS,
        Monster.RAKSHASHA,
        Monster.ICE_DEVIL,
        Monster.BONE_DEVIL,
        Monster.IMP,
        Monster.GHOST,
        Monster.BANSHEE,
    }
)

ICE_SUSPENSION_FLYING_MONSTERS: frozenset[Monster] = frozenset(
    {
        Monster.VAMPIRE,
        Monster.GI_WASP,
        Monster.BEHOLDER,
        Monster.GR_DRAGON,
        Monster.GO_DRAGON,
        Monster.S_DRAGON,
        Monster.B_DRAGON,
        Monster.R_DRAGON,
        Monster.GI_EAGLE,
        Monster.COUATL,
        Monster.ROC,
        Monster.GARGOYLE,
        Monster.GRYPHON,
    }
)


# Phase 190 -- project-original, user-supplied while defining
# turn/encounter.py's Hand of Death [HA] spell. See module docstring's
# own Phase 190 addendum for why the Mechanical/Undead legs of Hand of
# Death's own immunity reuse SPIRITWRACK_MECHANICAL_MONSTERS/
# SPIRITWRACK_UNDEAD_MONSTERS directly instead of duplicating them here.
HAND_OF_DEATH_ANTI_HOLY_MONSTERS: frozenset[Monster] = frozenset(
    {
        Monster.BAL_DEMON,
        Monster.MAR_DEMON,
        Monster.SUCCUBUS,
        Monster.RAKSHASHA,
        Monster.ICE_DEVIL,
        Monster.BONE_DEVIL,
        Monster.IMP,
    }
)

HAND_OF_DEATH_IMMUNE_MONSTERS: frozenset[Monster] = (
    SPIRITWRACK_MECHANICAL_MONSTERS | SPIRITWRACK_UNDEAD_MONSTERS | HAND_OF_DEATH_ANTI_HOLY_MONSTERS
)

# Phase 462 -- AKGEN_reverse_engineering_report (2).md SS17.3's own
# compiled ordinal range 12..21 (Giant..Witch) for Duellist/Cravenest/
# Bravest of the Brave merit against a monster opponent. See module
# docstring's own Phase 462 addendum for why Titan (11) stays excluded.
DUEL_MERIT_MONSTERS: frozenset[Monster] = frozenset(
    {
        Monster.GIANT,
        Monster.BIGFOOT,
        Monster.ARCHER,
        Monster.SWORDSMAN,
        Monster.WHITE_MAGE,
        Monster.NEC_MAGE,
        Monster.ELE_MAGE,
        Monster.PSY_MAGE,
        Monster.ILL_MAGE,
        Monster.WITCH,
    }
)


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


def monster_intelligence_at_least_medium(monster: Monster) -> bool:
    """Phase 544 -- ``AKGEN_reverse_engineering_report (3).md`` SS60-62's
    own ``resolve_TA_to_monster()`` pseudocode: ``mintel[monster.type] >=
    Medium`` is the exact species classification that decides which
    narrative event fires when a Talk tactic's own Druid DR gate
    (``turn/encounter.py can_talk_to_monster()``) fails -- see ``turn/
    search_execution.py _apply_talk_language_failure()``'s own Phase 544
    addendum for the full branch. Reuses ``MONSTER_RUNTIME_PROFILE``'s
    own ``intelligence`` field (Phase 381, CTME.PAS-sourced) and
    ``MONSTER_INTELLIGENCE_ORDINAL``'s own confirmed enum order (Phase
    504) -- no new data, just the ordinal comparison the dossier's own
    pseudocode performs directly.
    """

    profile = MONSTER_RUNTIME_PROFILE.get(monster)
    if profile is None:
        return True  # unknown -- default to the silent _LIgnore branch, never fabricate RPuzzled text
    return MONSTER_INTELLIGENCE_ORDINAL[profile.intelligence] >= MONSTER_INTELLIGENCE_ORDINAL[MonsterIntelligence.MEDIUM]
