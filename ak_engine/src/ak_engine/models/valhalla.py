"""VALHALLA hero roster (Gate Angel [AdvancedAbility.GATE_ANGEL_SPELL],
Phase 196) -- the user-supplied source for the Valhalla visitor Gate
Angel's own confirmed effect draws from.

**Sourced verbatim from 5 user-supplied files** (``VALHALLA GOOD.txt``,
``VALHALLA DRUID.txt``, ``VALHALLA NEUTRAL.txt``, ``VALHALLA PAGAN.txt``,
``VALHALLA EVIL.txt``, one per ``turn/cast_execution.py
GATE_ANGEL_ELIGIBLE_ALIGNMENTS`` bucket), 137 named legendary heroes
total. Each source line-block gives, per hero: a name; the hero's own
*true* ``Alignment`` (frequently ``DIVINE``/``UNDEAD`` even inside the
``GOOD``/``EVIL`` bucket files -- confirms the user's own VALHALLA rule
text directly: "I re Non-Morti e Divini possono entrare nel Vahlalla
come Buoni o Malvagi, ma non ricevono visite dal Vahlalla" describes
which *bucket* a Divine/Undead hero's own legendary character joins,
not who can *receive* a visit -- see ``turn/cast_execution.py``'s own
"Phase 195 addendum" for the full distinction); a ``Temper``; a race
(``M/F`` gender is present in the source but not transcribed here --
this project has no per-leader gender field anywhere, and nothing would
consume it); a ``Race``; and two rows of 15 numbers each in the exact
column order ``Ta Ma Na Ar Me Wh Ne El Ps Il Dr Th Ex Sp Sa`` --
confirmed to match ``models/enums.py Ability``'s own declared member
order exactly (``TACTICAL, MARCH, NAVAL, ARCHERY, MELEE, WHITE,
NECROMANCY, ELEMENTAL, PSYCHIC, ILLUSION, DRUID, THIEF, EXPLORER, SPY,
SAGE``) -- row 1 is each ability's current skill level, row 2 its
aptitude, interleaved directly into ``SkillTable.raw_values`` the same
``(skill, aptitude)`` pair format Phase 21 already resolved. Finally,
an ``Oggetto:`` line names the hero's own fixed, always-the-same magic
item ("Re Artù avrà sempre Excalibur" -- confirmed directly: the GOOD
file's own "Arthur" entry carries "Sword Excalibur").

**Two source typos, corrected to their obvious intent, not silently
dropped**: the GOOD file's "Kurator" has ``Temp: Breve`` (a typo for
"Brave" -- every other ``Temper`` value in this 137-hero corpus reads
cleanly); the EVIL file's Marius/Severius/Dietrich all read ``Race:
Humam`` (a typo for "Human").

**``fixed_item`` resolution against ``models/treasure.py``'s own
``TREASURE_NAME``**: all 63 distinct item names transcribed here now
resolve, either directly, via an obvious wording variant already
present in this corpus (e.g. "Sword Excalibur" -> ``LEADERSHIP_HUMAN``'s
own "Excalibur", "The True Cross" -> ``AMULET_ANTI_NECROMANCY``'s own
"True Cross", "Quaagoth's Portable Laboratory" -> ``ABILITY_SAGE``'s own
"Portable Laboratory of Qua'al Naggoth"), or via three items the user
confirmed directly once this project flagged them as unresolved:
**"Feather of the Great Eagle" filled ``MONSTER_AID_EAGLE``'s own
``TREASURE_NAME`` gap (Phase 196)**, **"Horn of Neptune" (Gelenor,
PAGAN) filled ``MONSTER_AID_WHALE``'s own gap (Phase 197)**, and
**"Hannibal's Grimoire" (Xerxes, PAGAN) filled ``BOOK_TACTICAL``'s own
gap (Phase 198)** -- see ``models/treasure.py``'s own docstring
addenda for each item's sourcing. No hero's own item is left
unresolved anymore.

**No new ``LeaderState`` is spawned by this module itself** -- see
``turn/valhalla_execution.py finalize_gate_angel_visit()`` for the
actual hero-synthesis consumer. **Phase 650 correction, kept for the
record**: an earlier version of this note called the ``turn_
processor.py`` integration "a future... not yet wired" -- stale even
when this correction was written: ``turn_processor.py`` has called
``finalize_gate_angel_visit()`` once per turn since Phase 199 (see that
module's own "GATE ANGEL / VALHALLA VISIT" section).

**Phase 551**: a fresh audit found 27 further real heroes in the same
AKGEN catalog, genuinely present in the game data but missing from
this module's own 137 -- see ``VALHALLA_ROSTER_UNCONFIRMED``'s own
docstring below for the full account of what's sourced (name/race/
temper/skills) versus not (true alignment, fixed item) and why they
stay deliberately excluded from real Gate Angel selection.

**Phase 560 -- the real roster is a 178-slot array, not 164 unique
heroes.** A second, independently-generated catalog of the same
underlying data (the user's own ``AKGEN_complete_name_lists.md``,
audited this phase) lists every one of the real ``GOOD2.X2``/
``DRUIDIC2.X2``/``NEUTRAL2.X2``/``PAGAN2.X2``/``EVIL2.X2`` roster
files' own raw entries by source index: 43/25/46/30/34 (178 total),
not the 32/23/34/21/27 (137) this module's own narrative-sourced
``VALHALLA_ROSTER`` had, nor the 164 unique names Phase 551 landed on
after its own by-name extraction. Cross-checked programmatically
against ``AKGEN_name_catalogs.json.txt valhalla_hero_rosters.rosters``
(the same JSON Phase 551 already used, which turns out to already
carry every one of the 178 raw records -- Phase 551 just deduplicated
by display name when it built ``VALHALLA_ROSTER_UNCONFIRMED``, losing
the real slot count): every single one of the 178 raw entries' own
*name* (case-normalized) already matched a name already present in
``VALHALLA_ROSTER`` or ``VALHALLA_ROSTER_UNCONFIRMED`` -- there are no
further hitherto-unseen hero identities to add. What was missing is
that **13 already-confirmed names occupy more than one real slot**
(``Winner`` x3 and ``Kalko``/``Swk`` x2 each in Good; ``Fire`` x2 in
Druidic; ``La-La`` x3 and ``Rogvold``/``Skilza`` x2 each in Neutral;
``Mary``/``Lancelot`` x2 each in Pagan; ``Skilza`` x3 in Evil), plus
one already-unconfirmed name (``Artur``, Neutral) occupying 2 slots --
confirmed by direct byte comparison of a sample duplicate's own
``skills_raw`` (two of ``Winner``'s three raw Good entries are
byte-identical; the third differs slightly, and ``Arthur``'s own
single raw entry differs from this module's narrative-sourced version
by exactly one point of Sage aptitude -- both patterns consistent with
real players independently reusing a common nickname, or the same
character's stats drifting slightly between whatever moment each
source document captured them, not a data error either way). This
matters because ``turn/valhalla_execution.py
_select_visitor_template()``'s own turn-6-onward selection picks a
**slot index** uniformly (``n = len(roster)``) -- a name occupying 3
real slots is 3x as likely to actually visit as one occupying 1,
information the deduplicated 137-hero list couldn't represent. Fixed
by repeating each affected hero's own already-fully-sourced
``ValhallaHero`` entry the correct additional number of times (never
touching each alignment's own final list entry -- SS386's own confirmed
"turns 1-5 always pick the last record" default must stay put), rather
than inventing new stat blocks: ``VALHALLA_ROSTER`` grows from 137 to
150 (32->36 Good, 23->24 Druidic, 34->38 Neutral, 21->23 Pagan, 27->29
Evil), and ``VALHALLA_ROSTER_UNCONFIRMED`` from 27 to 28 (Neutral
7->8, for ``Artur`` -- inert today since this dict is still never read
by real selection, kept only for the same future-completeness reason
Phase 551 itself already gives).
"""

from __future__ import annotations

from dataclasses import dataclass

from ak_engine.models.alignment import Alignment
from ak_engine.models.kingdom import SkillTable
from ak_engine.models.race import Race
from ak_engine.models.temper import Temper
from ak_engine.models.treasure import Treasure

# The Valhalla visitor's own leader id is always this fixed value
# ("Il numero d'ordine del visitatore dal Vahlalla sara' sempre #199"),
# never allocated via GameState.new_army_id()-style monotonic counting
# the way every other leader in this project is.
VALHALLA_VISITOR_LEADER_ID = 199


@dataclass(slots=True)
class ValhallaHero:
    name: str
    true_alignment: Alignment
    temper: Temper
    race: Race
    skills: SkillTable
    fixed_item: Treasure | None  # None for the 2 unresolved items -- see module docstring
    fixed_item_name: str  # raw "Oggetto:" source text, always populated


def _valhalla_stay_phase_count(active_turn: int) -> int:
    """Phase 546 -- ``VALHALLA.txt``'s own escalating action table,
    quoted in full: "Nei turni 1 e 2, i visitatori dal Vahlalla hanno
    diritto ad una sola azione e questa facolta' aumenta al ritmo di una
    azione ogni due turni. Quindi, due azioni [...] se il Vahlalla
    arriva nei turni 3-4. Tre azioni nei turni 5-6, quattro azioni nei
    turni 7-8, cinque nei turni dal 9 in poi."

    A real ``ActionPlan`` already has exactly 5 phases (P0-P4) within
    *one* game turn (``models/plan.py``/``turn/plan_dispatch.py run_
    leader_plan()``), and the table's own cap tops out at exactly 5 --
    confirmed (via the user's own explicit choice) to describe how many
    of the visitor's 5 phases in their *one* active turn may carry a
    real order, not a multi-turn stay. See ``turn/valhalla_execution.py
    finalize_gate_angel_visit()``'s own Phase 546 addendum for how
    ``active_turn`` itself is derived.
    """

    if active_turn <= 2:
        return 1
    if active_turn <= 4:
        return 2
    if active_turn <= 6:
        return 3
    if active_turn <= 8:
        return 4
    return 5


# Keyed by the VALHALLA bucket (turn/cast_execution.py's own
# GATE_ANGEL_ELIGIBLE_ALIGNMENTS) a hero appears under -- not necessarily
# the hero's own `true_alignment` (see module docstring).
VALHALLA_ROSTER: dict[Alignment, tuple[ValhallaHero, ...]] = {
    Alignment.GOOD: (
        ValhallaHero(
            name="Basil",
            true_alignment=Alignment.DIVINE,
            temper=Temper.BERSERK,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[2, 2, 2, 2, 0, 2, 1, 3, 1, 3, 6, 6, 0, 0, 5, 4, 2, 2, 1, 2, 2, 2, 0, 2, 0, 2, 0, 2, 1, 3]),
            fixed_item=Treasure.WEAPON_2,
            fixed_item_name="Shadow Sword",
        ),
        # Phase 560: "Winner" occupies 3 real raw slots (source indices
        # 1/3/5 in GOOD2.X2), not 1 -- repeated verbatim below rather
        # than deduplicated, so turn/valhalla_execution.py
        # _select_visitor_template()'s own by-index selection weighs it
        # correctly. See this module's own Phase 560 docstring note for
        # the full account (applies to every other repeated block in
        # this file too).
        ValhallaHero(
            name="Winner",
            true_alignment=Alignment.DIVINE,
            temper=Temper.BRAVE,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[1, 2, 2, 4, 0, 2, 1, 3, 3, 3, 7, 6, 0, 0, 2, 2, 1, 2, 0, 2, 2, 2, 0, 2, 0, 2, 0, 2, 3, 3]),
            fixed_item=Treasure.AMULET_ANTI_NECROMANCY,
            fixed_item_name="The True Cross",
        ),
        ValhallaHero(
            name="Winner",
            true_alignment=Alignment.DIVINE,
            temper=Temper.BRAVE,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[1, 2, 2, 4, 0, 2, 1, 3, 3, 3, 7, 6, 0, 0, 2, 2, 1, 2, 0, 2, 2, 2, 0, 2, 0, 2, 0, 2, 3, 3]),
            fixed_item=Treasure.AMULET_ANTI_NECROMANCY,
            fixed_item_name="The True Cross",
        ),
        ValhallaHero(
            name="Winner",
            true_alignment=Alignment.DIVINE,
            temper=Temper.BRAVE,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[1, 2, 2, 4, 0, 2, 1, 3, 3, 3, 7, 6, 0, 0, 2, 2, 1, 2, 0, 2, 2, 2, 0, 2, 0, 2, 0, 2, 3, 3]),
            fixed_item=Treasure.AMULET_ANTI_NECROMANCY,
            fixed_item_name="The True Cross",
        ),
        ValhallaHero(
            name="Kalko",
            true_alignment=Alignment.GOOD,
            temper=Temper.BRAVE,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[4, 4, 3, 4, 0, 2, 1, 3, 3, 3, 2, 4, 0, 2, 0, 2, 2, 2, 0, 2, 1, 2, 0, 2, 0, 2, 1, 2, 2, 5]),
            fixed_item=Treasure.WAND_ORATORY,
            fixed_item_name="Silver Horn of Oratory",
        ),
        ValhallaHero(
            name="Kalko",
            true_alignment=Alignment.GOOD,
            temper=Temper.BRAVE,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[4, 4, 3, 4, 0, 2, 1, 3, 3, 3, 2, 4, 0, 2, 0, 2, 2, 2, 0, 2, 1, 2, 0, 2, 0, 2, 1, 2, 2, 5]),
            fixed_item=Treasure.WAND_ORATORY,
            fixed_item_name="Silver Horn of Oratory",
        ),
        ValhallaHero(
            name="Kurator",
            true_alignment=Alignment.DIVINE,
            temper=Temper.BRAVE,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[4, 4, 2, 4, 0, 2, 3, 3, 1, 3, 7, 6, 0, 0, 0, 2, 0, 2, 0, 2, 3, 2, 0, 2, 0, 2, 0, 2, 1, 5]),
            fixed_item=Treasure.WAND_CLAIRVOYANCE,
            fixed_item_name="Crystal of Seeing",
        ),
        ValhallaHero(
            name="Alex",
            true_alignment=Alignment.GOOD,
            temper=Temper.BRAVE,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[5, 2, 3, 4, 1, 2, 2, 3, 3, 3, 7, 7, 0, 2, 5, 4, 0, 2, 0, 2, 2, 2, 0, 2, 0, 2, 0, 2, 1, 5]),
            fixed_item=Treasure.ABILITY_NECROMANCY,
            fixed_item_name="Amulet of Orgoth",
        ),
        ValhallaHero(
            name="Mactep",
            true_alignment=Alignment.GOOD,
            temper=Temper.BRAVE,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[3, 3, 3, 4, 0, 2, 1, 3, 3, 3, 8, 7, 5, 4, 6, 5, 3, 2, 6, 6, 1, 2, 0, 2, 0, 2, 0, 2, 1, 5]),
            fixed_item=Treasure.WAND_KILL_ENEMY,
            fixed_item_name="Needles of the Black Mage",
        ),
        ValhallaHero(
            name="Santa",
            true_alignment=Alignment.DIVINE,
            temper=Temper.CAUTIOUS,
            race=Race.DWARVEN,
            skills=SkillTable(raw_values=[2, 4, 0, 2, 0, 2, 1, 3, 1, 3, 3, 5, 0, 0, 0, 2, 0, 2, 0, 2, 0, 2, 0, 2, 0, 2, 0, 2, 1, 3]),
            fixed_item=Treasure.ABILITY_SAGE,
            fixed_item_name="Quaagoth's Portable Laboratory",
        ),
        ValhallaHero(
            name="Nataniel",
            true_alignment=Alignment.GOOD,
            temper=Temper.BRAVE,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[4, 2, 3, 4, 0, 2, 1, 3, 6, 3, 8, 6, 4, 2, 8, 7, 4, 2, 5, 2, 2, 2, 0, 2, 0, 2, 0, 2, 1, 5]),
            fixed_item=Treasure.BOOK_SAGE,
            fixed_item_name="Library of Science",
        ),
        ValhallaHero(
            name="Bouh",
            true_alignment=Alignment.GOOD,
            temper=Temper.BRAVE,
            race=Race.ORCISH,
            skills=SkillTable(raw_values=[4, 3, 3, 4, 0, 2, 1, 3, 2, 3, 5, 5, 3, 2, 2, 2, 2, 2, 0, 2, 3, 3, 0, 2, 0, 2, 1, 2, 3, 5]),
            fixed_item=Treasure.WAND_FIREBALL,
            fixed_item_name="Wand of Fire",
        ),
        ValhallaHero(
            name="Delirium",
            true_alignment=Alignment.DIVINE,
            temper=Temper.BRAVE,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[5, 4, 2, 4, 0, 2, 2, 3, 1, 3, 7, 6, 0, 0, 0, 2, 0, 2, 0, 2, 1, 2, 0, 2, 0, 2, 0, 2, 1, 5]),
            fixed_item=Treasure.WAND_HOLY_SYMBOL,
            fixed_item_name="Golden Cross",
        ),
        ValhallaHero(
            name="Endriel",
            true_alignment=Alignment.GOOD,
            temper=Temper.BRAVE,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[5, 4, 3, 4, 0, 2, 1, 3, 4, 3, 9, 7, 2, 2, 2, 2, 3, 2, 2, 2, 2, 3, 2, 2, 0, 2, 1, 2, 1, 5]),
            fixed_item=Treasure.WAND_CHARM,
            fixed_item_name="Cologne of Charming",
        ),
        ValhallaHero(
            name="Iosif",
            true_alignment=Alignment.GOOD,
            temper=Temper.BERSERK,
            race=Race.DWARVEN,
            skills=SkillTable(raw_values=[6, 6, 4, 3, 1, 2, 5, 4, 4, 3, 5, 5, 0, 2, 3, 2, 0, 2, 0, 2, 3, 3, 0, 2, 0, 2, 0, 2, 1, 5]),
            fixed_item=Treasure.WAND_PLAGUE,
            fixed_item_name="Obsidian Vermin",
        ),
        ValhallaHero(
            name="Lyvra",
            true_alignment=Alignment.GOOD,
            temper=Temper.BERSERK,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[4, 3, 3, 3, 1, 2, 2, 3, 3, 5, 6, 5, 2, 2, 2, 2, 2, 2, 0, 2, 2, 2, 0, 2, 0, 2, 0, 2, 1, 5]),
            fixed_item=Treasure.ABILITY_EXPLORER,
            fixed_item_name="Crystal of Direction",
        ),
        ValhallaHero(
            name="Xela",
            true_alignment=Alignment.DIVINE,
            temper=Temper.BRAVE,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[0, 2, 3, 4, 0, 2, 1, 3, 5, 4, 8, 7, 0, 0, 0, 2, 0, 2, 0, 2, 0, 2, 0, 2, 0, 2, 0, 2, 1, 5]),
            fixed_item=Treasure.WAND_BLESS,
            fixed_item_name="Tome of Blessings",
        ),
        ValhallaHero(
            name="Endriel",
            true_alignment=Alignment.GOOD,
            temper=Temper.BRAVE,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[1, 2, 2, 4, 0, 2, 4, 4, 5, 4, 8, 8, 0, 2, 0, 2, 6, 5, 0, 2, 0, 2, 0, 2, 0, 2, 0, 2, 1, 5]),
            fixed_item=Treasure.WAND_RESURRECTION,
            fixed_item_name="Rod of Resurrection",
        ),
        ValhallaHero(
            name="John",
            true_alignment=Alignment.GOOD,
            temper=Temper.BERSERK,
            race=Race.DWARVEN,
            skills=SkillTable(raw_values=[5, 3, 3, 4, 0, 2, 4, 3, 1, 3, 6, 6, 2, 2, 3, 2, 5, 6, 2, 2, 2, 2, 0, 2, 0, 2, 1, 2, 1, 5]),
            fixed_item=Treasure.ABILITY_WHITE,
            fixed_item_name="Holy Grail",
        ),
        ValhallaHero(
            name="Rumata",
            true_alignment=Alignment.DIVINE,
            temper=Temper.BERSERK,
            race=Race.ELVEN,
            skills=SkillTable(raw_values=[1, 2, 2, 2, 0, 2, 3, 3, 2, 3, 6, 6, 0, 0, 2, 2, 5, 4, 2, 2, 5, 3, 0, 2, 3, 2, 1, 2, 1, 3]),
            fixed_item=Treasure.ABILITY_ARCHERY,
            fixed_item_name="Longbow of Accuracy",
        ),
        ValhallaHero(
            name="Alf",
            true_alignment=Alignment.GOOD,
            temper=Temper.BERSERK,
            race=Race.ELVEN,
            skills=SkillTable(raw_values=[5, 4, 3, 2, 0, 2, 3, 4, 5, 5, 7, 6, 2, 2, 0, 2, 0, 2, 0, 2, 1, 2, 0, 2, 1, 3, 1, 2, 3, 5]),
            fixed_item=Treasure.AMULET_ANTI_WHITE,
            fixed_item_name="Shrunken-Head Amulet",
        ),
        ValhallaHero(
            name="Delvin",
            true_alignment=Alignment.GOOD,
            temper=Temper.BRAVE,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[5, 4, 4, 5, 0, 2, 2, 3, 2, 3, 7, 8, 0, 2, 0, 2, 0, 2, 0, 2, 0, 2, 0, 2, 1, 2, 0, 2, 1, 5]),
            fixed_item=Treasure.ABILITY_ELEMENTAL,
            fixed_item_name="Crucible of Elements",
        ),
        ValhallaHero(
            name="Swk",
            true_alignment=Alignment.DIVINE,
            temper=Temper.BRAVE,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[1, 2, 1, 2, 0, 2, 1, 3, 6, 5, 9, 8, 0, 0, 1, 2, 0, 2, 2, 2, 2, 2, 1, 3, 1, 2, 1, 2, 1, 3]),
            fixed_item=Treasure.BOOK_SPY,
            fixed_item_name="Manual of Spying",
        ),
        ValhallaHero(
            name="Swk",
            true_alignment=Alignment.DIVINE,
            temper=Temper.BRAVE,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[1, 2, 1, 2, 0, 2, 1, 3, 6, 5, 9, 8, 0, 0, 1, 2, 0, 2, 2, 2, 2, 2, 1, 3, 1, 2, 1, 2, 1, 3]),
            fixed_item=Treasure.BOOK_SPY,
            fixed_item_name="Manual of Spying",
        ),
        ValhallaHero(
            name="Mike",
            true_alignment=Alignment.GOOD,
            temper=Temper.BERSERK,
            race=Race.DWARVEN,
            skills=SkillTable(raw_values=[5, 4, 2, 3, 0, 2, 6, 5, 4, 3, 7, 6, 0, 0, 1, 2, 4, 5, 2, 2, 2, 2, 0, 2, 1, 2, 0, 2, 1, 5]),
            fixed_item=Treasure.LEADERSHIP_DWARVEN,
            fixed_item_name="Axe of the Dwarven Lords",
        ),
        ValhallaHero(
            name="Arthur",
            true_alignment=Alignment.GOOD,
            temper=Temper.BRAVE,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[2, 4, 2, 4, 1, 3, 1, 3, 3, 4, 1, 3, 0, 2, 0, 2, 0, 2, 0, 2, 1, 3, 0, 2, 1, 3, 0, 2, 2, 5]),
            fixed_item=Treasure.LEADERSHIP_HUMAN,
            fixed_item_name="Sword Excalibur",
        ),
        ValhallaHero(
            name="Nouvelle",
            true_alignment=Alignment.GOOD,
            temper=Temper.BERSERK,
            race=Race.ELVEN,
            skills=SkillTable(raw_values=[3, 2, 2, 2, 2, 2, 1, 3, 2, 3, 1, 4, 1, 2, 0, 2, 3, 4, 0, 2, 3, 3, 0, 2, 1, 2, 0, 2, 1, 5]),
            fixed_item=Treasure.WEAPON_5,
            fixed_item_name="Invisible Sword",
        ),
        ValhallaHero(
            name="Scipio",
            true_alignment=Alignment.GOOD,
            temper=Temper.BRAVE,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[5, 6, 2, 4, 2, 2, 1, 3, 1, 3, 1, 4, 0, 2, 3, 2, 1, 2, 0, 2, 3, 3, 1, 2, 0, 2, 0, 2, 1, 5]),
            fixed_item=Treasure.ABILITY_THIEF,
            fixed_item_name="Cloak of Stealth",
        ),
        ValhallaHero(
            name="Balin",
            true_alignment=Alignment.GOOD,
            temper=Temper.CAUTIOUS,
            race=Race.DWARVEN,
            skills=SkillTable(raw_values=[3, 2, 2, 2, 2, 3, 1, 3, 1, 3, 4, 4, 3, 4, 4, 3, 1, 2, 0, 2, 4, 4, 0, 2, 1, 2, 0, 2, 1, 5]),
            fixed_item=Treasure.WAND_SKELETAL_ARMY,
            fixed_item_name="Horn of Ghastly Revenge",
        ),
        ValhallaHero(
            name="Ambrosius",
            true_alignment=Alignment.GOOD,
            temper=Temper.CAUTIOUS,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[6, 5, 4, 5, 0, 3, 1, 3, 4, 3, 0, 4, 0, 2, 2, 2, 2, 2, 0, 2, 3, 3, 0, 2, 0, 2, 0, 2, 1, 5]),
            fixed_item=Treasure.WAND_PSYCHIC_BLAST,
            fixed_item_name="Antennae of Psychic Blasting",
        ),
        ValhallaHero(
            name="Gambit",
            true_alignment=Alignment.GOOD,
            temper=Temper.BRAVE,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[2, 3, 3, 3, 0, 2, 1, 3, 3, 3, 5, 4, 4, 6, 4, 3, 2, 4, 3, 2, 2, 2, 0, 2, 2, 2, 1, 2, 1, 5]),
            fixed_item=Treasure.ABILITY_ILLUSION,
            fixed_item_name="Spectral Crystal",
        ),
        ValhallaHero(
            name="Felix",
            true_alignment=Alignment.GOOD,
            temper=Temper.BRAVE,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[5, 3, 4, 3, 0, 2, 1, 3, 1, 3, 4, 4, 3, 2, 5, 4, 3, 3, 2, 2, 2, 2, 0, 2, 0, 2, 0, 2, 1, 5]),
            fixed_item=Treasure.WAND_SKELETAL_ARMY,
            fixed_item_name="Horn of Ghastly Revenge",
        ),
        ValhallaHero(
            name="Tornedain",
            true_alignment=Alignment.GOOD,
            temper=Temper.BERSERK,
            race=Race.DWARVEN,
            skills=SkillTable(raw_values=[3, 3, 3, 2, 0, 2, 1, 3, 3, 3, 4, 4, 0, 2, 0, 2, 1, 3, 2, 2, 2, 3, 0, 2, 0, 2, 1, 2, 1, 5]),
            fixed_item=Treasure.AMULET_ANTI_PSYCHIC,
            fixed_item_name="Helm of Psychic Dampening",
        ),
        ValhallaHero(
            name="Mazinga",
            true_alignment=Alignment.GOOD,
            temper=Temper.BRAVE,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[5, 4, 4, 3, 0, 2, 1, 3, 5, 3, 5, 5, 1, 2, 4, 2, 4, 4, 1, 2, 1, 2, 0, 2, 1, 2, 1, 2, 1, 5]),
            fixed_item=Treasure.WAND_EARTHQUAKE,
            fixed_item_name="Stone of Shaking",
        ),
        ValhallaHero(
            name="Balgran",
            true_alignment=Alignment.GOOD,
            temper=Temper.BRAVE,
            race=Race.ELVEN,
            skills=SkillTable(raw_values=[2, 2, 4, 4, 0, 2, 2, 3, 3, 3, 6, 7, 3, 3, 3, 3, 0, 2, 5, 2, 2, 2, 0, 2, 0, 2, 0, 2, 2, 5]),
            fixed_item=Treasure.LEADERSHIP_HUMAN,
            fixed_item_name="Sword Excalibur",
        ),
        ValhallaHero(
            name="Quintilian",
            true_alignment=Alignment.GOOD,
            temper=Temper.CAUTIOUS,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[4, 4, 5, 5, 0, 2, 2, 3, 3, 3, 0, 4, 0, 2, 0, 2, 4, 3, 0, 2, 4, 4, 0, 2, 1, 2, 0, 2, 2, 5]),
            fixed_item=Treasure.LEADERSHIP_HUMAN,
            fixed_item_name="Sword Excalibur",
        ),
    ),
    Alignment.DRUID: (
        ValhallaHero(
            name="Labutin",
            true_alignment=Alignment.DRUID,
            temper=Temper.BRAVE,
            race=Race.ELVEN,
            skills=SkillTable(raw_values=[4, 3, 2, 3, 0, 2, 1, 3, 3, 3, 4, 2, 3, 3, 6, 6, 4, 5, 0, 2, 1, 5, 0, 2, 0, 2, 0, 2, 1, 3]),
            fixed_item=Treasure.WAND_ORATORY,
            fixed_item_name="Silver Horn of Oratory",
        ),
        ValhallaHero(
            name="Smolit",
            true_alignment=Alignment.DRUID,
            temper=Temper.COWARDLY,
            race=Race.ELVEN,
            skills=SkillTable(raw_values=[5, 5, 4, 4, 0, 2, 1, 3, 1, 3, 0, 2, 0, 2, 2, 2, 4, 5, 2, 2, 3, 4, 0, 2, 0, 2, 0, 2, 1, 3]),
            fixed_item=Treasure.ABILITY_ARCHERY,
            fixed_item_name="Longbow of Accuracy",
        ),
        ValhallaHero(
            name="Tommy",
            true_alignment=Alignment.DRUID,
            temper=Temper.BRAVE,
            race=Race.ELVEN,
            skills=SkillTable(raw_values=[4, 4, 2, 2, 0, 2, 1, 3, 1, 3, 0, 2, 0, 2, 4, 3, 0, 4, 2, 2, 2, 5, 0, 2, 0, 2, 0, 2, 2, 3]),
            fixed_item=Treasure.ABILITY_SPY,
            fixed_item_name="X-Ray Spyglass",
        ),
        ValhallaHero(
            name="Fantir",
            true_alignment=Alignment.DRUID,
            temper=Temper.CAUTIOUS,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[5, 3, 4, 5, 0, 2, 1, 3, 2, 3, 1, 2, 4, 3, 0, 2, 2, 5, 0, 2, 2, 4, 0, 2, 1, 3, 0, 2, 3, 3]),
            fixed_item=Treasure.WAND_ORATORY,
            fixed_item_name="Silver Horn of Oratory",
        ),
        ValhallaHero(
            name="Fire",
            true_alignment=Alignment.DRUID,
            temper=Temper.BRAVE,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[2, 2, 2, 3, 1, 3, 3, 3, 3, 3, 5, 4, 3, 2, 3, 2, 4, 4, 0, 2, 3, 4, 2, 2, 0, 2, 0, 2, 1, 3]),
            fixed_item=Treasure.LEADERSHIP_HUMAN,
            fixed_item_name="Sword Excalibur",
        ),
        ValhallaHero(
            name="Fire",
            true_alignment=Alignment.DRUID,
            temper=Temper.BRAVE,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[2, 2, 2, 3, 1, 3, 3, 3, 3, 3, 5, 4, 3, 2, 3, 2, 4, 4, 0, 2, 3, 4, 2, 2, 0, 2, 0, 2, 1, 3]),
            fixed_item=Treasure.LEADERSHIP_HUMAN,
            fixed_item_name="Sword Excalibur",
        ),
        ValhallaHero(
            name="Gilgamesh",
            true_alignment=Alignment.DRUID,
            temper=Temper.BERSERK,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[2, 4, 1, 3, 1, 3, 1, 3, 3, 4, 3, 4, 2, 4, 0, 2, 1, 3, 0, 2, 2, 4, 0, 2, 1, 3, 0, 2, 1, 3]),
            fixed_item=Treasure.WEAPON_4,
            fixed_item_name="Psychic Flail",
        ),
        ValhallaHero(
            name="Phoenix",
            true_alignment=Alignment.DRUID,
            temper=Temper.CAUTIOUS,
            race=Race.ELVEN,
            skills=SkillTable(raw_values=[4, 2, 4, 4, 1, 2, 1, 3, 2, 3, 0, 2, 3, 4, 0, 2, 1, 4, 0, 2, 2, 4, 0, 2, 0, 2, 0, 2, 1, 3]),
            fixed_item=Treasure.LEADERSHIP_ELVEN,
            fixed_item_name="Bow of the Elven Kings",
        ),
        ValhallaHero(
            name="Gandalf",
            true_alignment=Alignment.DRUID,
            temper=Temper.BRAVE,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[0, 2, 0, 2, 0, 2, 1, 3, 3, 3, 5, 5, 2, 2, 2, 2, 5, 6, 2, 2, 4, 4, 0, 2, 0, 2, 0, 2, 1, 3]),
            fixed_item=Treasure.WEAPON_2,
            fixed_item_name="Shadow Sword",
        ),
        ValhallaHero(
            name="Tnstfl",
            true_alignment=Alignment.DRUID,
            temper=Temper.BRAVE,
            race=Race.ELVEN,
            skills=SkillTable(raw_values=[2, 2, 5, 4, 0, 2, 2, 3, 2, 3, 4, 4, 2, 3, 3, 2, 3, 4, 2, 2, 5, 4, 1, 2, 2, 2, 0, 2, 3, 3]),
            fixed_item=Treasure.BOOK_PSYCHIC,
            fixed_item_name="Codex of Mental Prowess",
        ),
        ValhallaHero(
            name="Fezbin",
            true_alignment=Alignment.DRUID,
            temper=Temper.CAUTIOUS,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[0, 2, 0, 2, 2, 3, 3, 3, 3, 4, 3, 4, 3, 2, 2, 4, 4, 3, 4, 2, 2, 4, 1, 2, 0, 2, 0, 2, 2, 3]),
            fixed_item=Treasure.WEAPON_2,
            fixed_item_name="Shadow Sword",
        ),
        ValhallaHero(
            name="Richard",
            true_alignment=Alignment.DRUID,
            temper=Temper.BRAVE,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[2, 2, 3, 2, 2, 3, 4, 3, 5, 5, 8, 6, 2, 2, 5, 4, 4, 5, 2, 2, 2, 4, 2, 2, 0, 2, 0, 2, 2, 3]),
            fixed_item=Treasure.AMULET_ANTI_ELEMENTAL,
            fixed_item_name="Golden Orb of Elemental Stability",
        ),
        ValhallaHero(
            name="Viridovix",
            true_alignment=Alignment.DRUID,
            temper=Temper.BERSERK,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[2, 2, 4, 5, 0, 2, 2, 3, 4, 4, 4, 4, 2, 2, 0, 2, 0, 4, 0, 2, 5, 4, 0, 2, 2, 2, 1, 2, 1, 3]),
            fixed_item=Treasure.LEADERSHIP_ORCISH,
            fixed_item_name="Scimitar of Orc Mastery",
        ),
        ValhallaHero(
            name="Quagga",
            true_alignment=Alignment.DRUID,
            temper=Temper.CAUTIOUS,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[2, 2, 1, 2, 2, 2, 4, 4, 2, 3, 3, 3, 3, 3, 2, 3, 3, 3, 4, 4, 3, 3, 0, 2, 1, 3, 1, 4, 1, 3]),
            fixed_item=Treasure.WEAPON_4,
            fixed_item_name="Psychic Flail",
        ),
        ValhallaHero(
            name="Alexander",
            true_alignment=Alignment.DRUID,
            temper=Temper.BERSERK,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[0, 2, 0, 2, 0, 2, 2, 3, 1, 3, 4, 4, 2, 2, 1, 2, 5, 5, 2, 2, 1, 5, 0, 2, 0, 2, 0, 2, 1, 3]),
            fixed_item=Treasure.BOOK_NECROMANCY,
            fixed_item_name="Necronomicon",
        ),
        ValhallaHero(
            name="Xerxes",
            true_alignment=Alignment.DRUID,
            temper=Temper.BRAVE,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[4, 2, 5, 3, 3, 3, 1, 3, 2, 3, 5, 4, 0, 2, 3, 3, 1, 4, 3, 2, 3, 5, 0, 2, 1, 3, 0, 2, 1, 3]),
            fixed_item=Treasure.WAND_ILLUS_TERRAIN,
            fixed_item_name="Projector of Scenic Illusions",
        ),
        ValhallaHero(
            name="Dredd",
            true_alignment=Alignment.DRUID,
            temper=Temper.BRAVE,
            race=Race.ELVEN,
            skills=SkillTable(raw_values=[3, 3, 2, 2, 5, 5, 1, 3, 2, 3, 0, 2, 0, 2, 4, 4, 4, 4, 1, 2, 6, 5, 0, 2, 3, 3, 2, 2, 1, 3]),
            fixed_item=Treasure.WAND_HAND_OF_DEATH,
            fixed_item_name="Glove of Death",
        ),
        ValhallaHero(
            name="Casanova",
            true_alignment=Alignment.DRUID,
            temper=Temper.BRAVE,
            race=Race.ELVEN,
            skills=SkillTable(raw_values=[4, 3, 6, 5, 1, 2, 3, 3, 1, 3, 3, 2, 0, 2, 1, 2, 3, 5, 0, 2, 4, 5, 1, 2, 2, 2, 2, 2, 2, 3]),
            fixed_item=Treasure.WAND_INVISIBILITY,
            fixed_item_name="Ring of Invisibility",
        ),
        ValhallaHero(
            name="Eugene",
            true_alignment=Alignment.DRUID,
            temper=Temper.CAUTIOUS,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[2, 2, 2, 2, 0, 2, 1, 3, 6, 5, 5, 2, 2, 2, 3, 2, 5, 5, 3, 2, 0, 4, 0, 2, 0, 2, 1, 3, 2, 4]),
            fixed_item=Treasure.ABILITY_MELEE,
            fixed_item_name="Bracelets of Swordsmanship",
        ),
        ValhallaHero(
            name="Bruenor",
            true_alignment=Alignment.DRUID,
            temper=Temper.BERSERK,
            race=Race.DWARVEN,
            skills=SkillTable(raw_values=[3, 3, 3, 3, 1, 2, 3, 3, 1, 3, 0, 2, 1, 2, 0, 2, 3, 5, 2, 2, 4, 5, 0, 2, 0, 2, 0, 2, 2, 3]),
            fixed_item=Treasure.ABILITY_ARCHERY,
            fixed_item_name="Longbow of Accuracy",
        ),
        ValhallaHero(
            name="Nixie",
            true_alignment=Alignment.DRUID,
            temper=Temper.BRAVE,
            race=Race.ELVEN,
            skills=SkillTable(raw_values=[2, 2, 1, 2, 5, 3, 1, 3, 2, 3, 4, 4, 0, 2, 0, 2, 3, 4, 0, 2, 4, 4, 0, 2, 1, 2, 0, 2, 1, 3]),
            fixed_item=Treasure.WAND_ILLUS_TERRAIN,
            fixed_item_name="Projector of Scenic Illusions",
        ),
        ValhallaHero(
            name="Nephiritie",
            true_alignment=Alignment.DRUID,
            temper=Temper.BRAVE,
            race=Race.ELVEN,
            skills=SkillTable(raw_values=[1, 2, 2, 3, 9, 6, 2, 3, 3, 3, 3, 3, 4, 2, 2, 2, 4, 4, 0, 2, 2, 5, 1, 2, 1, 2, 0, 2, 2, 4]),
            fixed_item=Treasure.WAND_KILL_ENEMY,
            fixed_item_name="Needles of the Black Mage",
        ),
        ValhallaHero(
            name="Gil-galad",
            true_alignment=Alignment.DRUID,
            temper=Temper.BRAVE,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[6, 5, 5, 5, 3, 2, 1, 3, 3, 3, 0, 2, 2, 2, 0, 2, 5, 6, 1, 2, 3, 5, 1, 2, 2, 2, 0, 2, 1, 4]),
            fixed_item=Treasure.AMULET_ANTI_ILLUSION,
            fixed_item_name="Crystal of True Seeing",
        ),
        ValhallaHero(
            name="Bo",
            true_alignment=Alignment.DRUID,
            temper=Temper.BRAVE,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[4, 3, 4, 2, 1, 2, 5, 3, 2, 3, 5, 6, 1, 2, 5, 4, 5, 5, 1, 2, 2, 5, 1, 2, 1, 2, 0, 2, 1, 3]),
            fixed_item=Treasure.BOOK_MELEE,
            fixed_item_name="Handbook of Swordsmanship",
        ),
    ),
    Alignment.NEUTRAL: (
        ValhallaHero(
            name="La-La",
            true_alignment=Alignment.NEUTRAL,
            temper=Temper.BRAVE,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[5, 5, 3, 3, 3, 3, 3, 4, 3, 3, 4, 4, 1, 2, 4, 3, 3, 2, 3, 4, 2, 3, 0, 2, 1, 2, 0, 4, 1, 3]),
            fixed_item=Treasure.LEADERSHIP_HUMAN,
            fixed_item_name="Sword Excalibur",
        ),
        ValhallaHero(
            name="La-La",
            true_alignment=Alignment.NEUTRAL,
            temper=Temper.BRAVE,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[5, 5, 3, 3, 3, 3, 3, 4, 3, 3, 4, 4, 1, 2, 4, 3, 3, 2, 3, 4, 2, 3, 0, 2, 1, 2, 0, 4, 1, 3]),
            fixed_item=Treasure.LEADERSHIP_HUMAN,
            fixed_item_name="Sword Excalibur",
        ),
        ValhallaHero(
            name="La-La",
            true_alignment=Alignment.NEUTRAL,
            temper=Temper.BRAVE,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[5, 5, 3, 3, 3, 3, 3, 4, 3, 3, 4, 4, 1, 2, 4, 3, 3, 2, 3, 4, 2, 3, 0, 2, 1, 2, 0, 4, 1, 3]),
            fixed_item=Treasure.LEADERSHIP_HUMAN,
            fixed_item_name="Sword Excalibur",
        ),
        ValhallaHero(
            name="Hercules",
            true_alignment=Alignment.NEUTRAL,
            temper=Temper.BERSERK,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[1, 3, 1, 3, 1, 3, 4, 4, 4, 4, 0, 2, 0, 2, 0, 2, 0, 2, 0, 4, 0, 2, 0, 2, 3, 2, 0, 2, 1, 3]),
            fixed_item=Treasure.ABILITY_MELEE,
            fixed_item_name="Bracelets of Swordsmanship",
        ),
        ValhallaHero(
            name="Dubrava",
            true_alignment=Alignment.NEUTRAL,
            temper=Temper.BRAVE,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[3, 4, 6, 4, 2, 3, 1, 3, 3, 3, 4, 4, 5, 4, 3, 2, 0, 2, 1, 4, 4, 3, 0, 2, 1, 3, 0, 4, 1, 3]),
            fixed_item=Treasure.AMULET_ANTI_PSYCHIC,
            fixed_item_name="Helm of Psychic Dampening",
        ),
        ValhallaHero(
            name="Otto",
            true_alignment=Alignment.NEUTRAL,
            temper=Temper.BERSERK,
            race=Race.DWARVEN,
            skills=SkillTable(raw_values=[4, 2, 3, 2, 3, 2, 2, 3, 2, 3, 0, 2, 0, 2, 1, 2, 4, 4, 0, 4, 4, 4, 0, 2, 1, 2, 0, 4, 1, 3]),
            fixed_item=Treasure.MONSTER_AID_EAGLE,
            fixed_item_name="Feather of the Great Eagle",
        ),
        ValhallaHero(
            name="Alex",
            true_alignment=Alignment.NEUTRAL,
            temper=Temper.CAUTIOUS,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[5, 3, 2, 3, 1, 3, 3, 3, 2, 3, 0, 2, 0, 2, 0, 2, 0, 2, 2, 4, 3, 3, 0, 2, 0, 2, 0, 4, 1, 3]),
            fixed_item=Treasure.LEADERSHIP_ELVEN,
            fixed_item_name="Bow of the Elven Kings",
        ),
        ValhallaHero(
            name="Rogvold",
            true_alignment=Alignment.NEUTRAL,
            temper=Temper.CAUTIOUS,
            race=Race.ORCISH,
            skills=SkillTable(raw_values=[7, 5, 2, 2, 0, 2, 3, 5, 3, 3, 3, 3, 0, 2, 0, 2, 9, 7, 0, 4, 3, 2, 0, 2, 1, 3, 0, 4, 1, 3]),
            fixed_item=Treasure.LEADERSHIP_ORCISH,
            fixed_item_name="Scimitar of Orc Mastery",
        ),
        ValhallaHero(
            name="Rogvold",
            true_alignment=Alignment.NEUTRAL,
            temper=Temper.CAUTIOUS,
            race=Race.ORCISH,
            skills=SkillTable(raw_values=[7, 5, 2, 2, 0, 2, 3, 5, 3, 3, 3, 3, 0, 2, 0, 2, 9, 7, 0, 4, 3, 2, 0, 2, 1, 3, 0, 4, 1, 3]),
            fixed_item=Treasure.LEADERSHIP_ORCISH,
            fixed_item_name="Scimitar of Orc Mastery",
        ),
        ValhallaHero(
            name="Ioan",
            true_alignment=Alignment.NEUTRAL,
            temper=Temper.COWARDLY,
            race=Race.ELVEN,
            skills=SkillTable(raw_values=[6, 5, 5, 5, 1, 2, 1, 3, 1, 3, 2, 2, 2, 2, 1, 2, 0, 2, 0, 4, 3, 2, 0, 2, 0, 2, 0, 4, 1, 3]),
            fixed_item=Treasure.ABILITY_MARCH,
            fixed_item_name="Magical Register of March Orders",
        ),
        ValhallaHero(
            name="Skilza",
            true_alignment=Alignment.NEUTRAL,
            temper=Temper.BRAVE,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[0, 2, 1, 2, 0, 2, 3, 3, 2, 3, 3, 2, 0, 2, 3, 3, 6, 5, 4, 5, 2, 2, 0, 2, 0, 2, 0, 4, 1, 3]),
            fixed_item=Treasure.BOOK_WHITE,
            fixed_item_name="Scriptures of Holy Thoughts",
        ),
        ValhallaHero(
            name="Skilza",
            true_alignment=Alignment.NEUTRAL,
            temper=Temper.BRAVE,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[0, 2, 1, 2, 0, 2, 3, 3, 2, 3, 3, 2, 0, 2, 3, 3, 6, 5, 4, 5, 2, 2, 0, 2, 0, 2, 0, 4, 1, 3]),
            fixed_item=Treasure.BOOK_WHITE,
            fixed_item_name="Scriptures of Holy Thoughts",
        ),
        ValhallaHero(
            name="Gvidon",
            true_alignment=Alignment.NEUTRAL,
            temper=Temper.COWARDLY,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[6, 6, 2, 4, 0, 2, 1, 3, 1, 3, 0, 2, 0, 2, 3, 3, 0, 2, 0, 4, 1, 2, 0, 2, 0, 2, 0, 4, 1, 3]),
            fixed_item=Treasure.WAND_FLOOD,
            fixed_item_name="Feathers of Rain-Dancing",
        ),
        ValhallaHero(
            name="Goat",
            true_alignment=Alignment.NEUTRAL,
            temper=Temper.BRAVE,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[5, 5, 4, 4, 0, 2, 4, 4, 5, 4, 7, 7, 9, 6, 6, 4, 4, 3, 5, 5, 2, 2, 0, 2, 0, 2, 0, 4, 1, 3]),
            fixed_item=Treasure.WAND_PSYCHIC_BLAST,
            fixed_item_name="Antennae of Psychic Blasting",
        ),
        ValhallaHero(
            name="Fess",
            true_alignment=Alignment.NEUTRAL,
            temper=Temper.BERSERK,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[2, 2, 1, 2, 0, 2, 2, 2, 3, 2, 3, 5, 5, 4, 5, 4, 3, 3, 5, 5, 1, 2, 0, 2, 0, 2, 0, 4, 1, 3]),
            fixed_item=Treasure.BOOK_MARCH,
            fixed_item_name="Manual of Speedy Marches",
        ),
        ValhallaHero(
            name="Metepompop",
            true_alignment=Alignment.NEUTRAL,
            temper=Temper.BRAVE,
            race=Race.ORCISH,
            skills=SkillTable(raw_values=[4, 4, 7, 6, 0, 2, 1, 3, 1, 3, 0, 2, 0, 2, 0, 2, 0, 2, 0, 4, 1, 3, 0, 2, 0, 2, 0, 4, 1, 3]),
            fixed_item=Treasure.LEADERSHIP_ELVEN,
            fixed_item_name="Bow of the Elven Kings",
        ),
        ValhallaHero(
            name="Kida",
            true_alignment=Alignment.NEUTRAL,
            temper=Temper.BERSERK,
            race=Race.ELVEN,
            skills=SkillTable(raw_values=[5, 4, 2, 4, 0, 2, 1, 3, 3, 3, 0, 2, 0, 2, 3, 2, 2, 2, 6, 5, 1, 2, 0, 2, 0, 2, 0, 4, 1, 3]),
            fixed_item=Treasure.LEADERSHIP_ELVEN,
            fixed_item_name="Bow of the Elven Kings",
        ),
        ValhallaHero(
            name="Neo",
            true_alignment=Alignment.NEUTRAL,
            temper=Temper.BRAVE,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[6, 5, 2, 4, 0, 2, 1, 3, 1, 3, 0, 2, 0, 2, 0, 2, 0, 2, 3, 4, 1, 2, 0, 2, 0, 2, 0, 4, 1, 3]),
            fixed_item=Treasure.ABILITY_SAGE,
            fixed_item_name="Quaagoth's Portable Laboratory",
        ),
        ValhallaHero(
            name="Minder",
            true_alignment=Alignment.NEUTRAL,
            temper=Temper.CAUTIOUS,
            race=Race.DWARVEN,
            skills=SkillTable(raw_values=[5, 4, 4, 4, 0, 2, 1, 3, 1, 3, 0, 2, 0, 2, 2, 2, 0, 2, 5, 5, 2, 3, 0, 2, 0, 2, 0, 4, 1, 3]),
            fixed_item=Treasure.ABILITY_TACTICAL,
            fixed_item_name="Standard of Command",
        ),
        ValhallaHero(
            name="July",
            true_alignment=Alignment.NEUTRAL,
            temper=Temper.BRAVE,
            race=Race.ELVEN,
            skills=SkillTable(raw_values=[3, 2, 2, 2, 0, 2, 3, 4, 3, 4, 4, 3, 1, 2, 2, 2, 2, 2, 0, 4, 2, 2, 0, 2, 0, 2, 0, 4, 2, 4]),
            fixed_item=Treasure.WAND_HIDE_FEATURE,
            fixed_item_name="Dome of Opacity",
        ),
        ValhallaHero(
            name="Rumata",
            true_alignment=Alignment.NEUTRAL,
            temper=Temper.BERSERK,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[0, 2, 2, 2, 0, 2, 5, 3, 5, 5, 3, 3, 3, 2, 7, 5, 4, 4, 4, 5, 1, 2, 0, 2, 1, 2, 0, 4, 1, 3]),
            fixed_item=Treasure.WEAPON_1,
            fixed_item_name="Holy Sword",
        ),
        ValhallaHero(
            name="Hassan",
            true_alignment=Alignment.NEUTRAL,
            temper=Temper.COWARDLY,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[6, 5, 4, 4, 0, 2, 2, 3, 1, 3, 2, 2, 0, 2, 0, 2, 0, 2, 6, 5, 3, 2, 0, 2, 2, 2, 0, 4, 1, 3]),
            fixed_item=Treasure.WAND_ILLUS_ARMIES,
            fixed_item_name="Reflector of Armies",
        ),
        ValhallaHero(
            name="Wilco",
            true_alignment=Alignment.NEUTRAL,
            temper=Temper.BRAVE,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[2, 2, 5, 5, 0, 2, 2, 3, 3, 3, 4, 5, 0, 2, 2, 2, 0, 2, 4, 4, 3, 2, 0, 2, 0, 2, 1, 4, 1, 3]),
            fixed_item=Treasure.AMULET_ANTI_PSYCHIC,
            fixed_item_name="Helm of Psychic Dampening",
        ),
        ValhallaHero(
            name="Durin",
            true_alignment=Alignment.NEUTRAL,
            temper=Temper.BERSERK,
            race=Race.DWARVEN,
            skills=SkillTable(raw_values=[2, 2, 2, 2, 0, 2, 1, 3, 3, 5, 3, 2, 0, 2, 0, 2, 3, 4, 1, 4, 1, 2, 0, 2, 0, 2, 0, 4, 1, 3]),
            fixed_item=Treasure.LEADERSHIP_HUMAN,
            fixed_item_name="Sword Excalibur",
        ),
        ValhallaHero(
            name="Alcore",
            true_alignment=Alignment.NEUTRAL,
            temper=Temper.BRAVE,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[2, 3, 3, 3, 0, 2, 3, 3, 2, 3, 2, 2, 3, 2, 2, 2, 5, 5, 2, 4, 4, 3, 0, 2, 0, 2, 0, 4, 1, 3]),
            fixed_item=Treasure.BOOK_MELEE,
            fixed_item_name="Handbook of Swordsmanship",
        ),
        ValhallaHero(
            name="Alazar",
            true_alignment=Alignment.NEUTRAL,
            temper=Temper.CAUTIOUS,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[2, 2, 2, 4, 0, 2, 1, 3, 4, 5, 6, 5, 3, 2, 2, 2, 3, 3, 4, 4, 2, 3, 1, 2, 0, 2, 1, 4, 1, 3]),
            fixed_item=Treasure.LEADERSHIP_DWARVEN,
            fixed_item_name="Axe of the Dwarven Lords",
        ),
        ValhallaHero(
            name="Hrolf",
            true_alignment=Alignment.NEUTRAL,
            temper=Temper.BRAVE,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[1, 2, 1, 4, 4, 4, 1, 3, 3, 4, 0, 2, 0, 2, 2, 3, 0, 2, 0, 4, 1, 3, 0, 2, 1, 2, 0, 4, 1, 3]),
            fixed_item=Treasure.WAND_RESURRECTION,
            fixed_item_name="Rod of Resurrection",
        ),
        ValhallaHero(
            name="Henry",
            true_alignment=Alignment.NEUTRAL,
            temper=Temper.BERSERK,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[3, 3, 2, 3, 4, 2, 2, 4, 2, 3, 3, 3, 2, 2, 0, 2, 2, 2, 2, 4, 3, 4, 0, 2, 1, 2, 0, 4, 1, 4]),
            fixed_item=Treasure.ABILITY_ILLUSION,
            fixed_item_name="Spectral Crystal",
        ),
        ValhallaHero(
            name="Lee",
            true_alignment=Alignment.NEUTRAL,
            temper=Temper.BERSERK,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[1, 2, 4, 4, 0, 2, 3, 3, 3, 3, 4, 4, 0, 2, 0, 2, 2, 2, 0, 4, 2, 2, 0, 2, 0, 2, 0, 4, 1, 3]),
            fixed_item=Treasure.LEADERSHIP_HUMAN,
            fixed_item_name="Sword Excalibur",
        ),
        ValhallaHero(
            name="Conan",
            true_alignment=Alignment.NEUTRAL,
            temper=Temper.BERSERK,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[5, 4, 2, 2, 1, 2, 1, 3, 4, 4, 2, 3, 2, 2, 2, 2, 1, 2, 1, 4, 3, 2, 0, 2, 0, 2, 1, 4, 1, 3]),
            fixed_item=Treasure.WEAPON_3,
            fixed_item_name="Flaming Scimitar",
        ),
        ValhallaHero(
            name="Ironhand",
            true_alignment=Alignment.NEUTRAL,
            temper=Temper.BRAVE,
            race=Race.ELVEN,
            skills=SkillTable(raw_values=[5, 3, 6, 4, 1, 2, 1, 3, 2, 3, 2, 3, 2, 2, 2, 2, 3, 3, 3, 4, 1, 3, 1, 2, 0, 2, 0, 4, 2, 3]),
            fixed_item=Treasure.AMULET_ANTI_WHITE,
            fixed_item_name="Shrunken-Head Amulet",
        ),
        ValhallaHero(
            name="Sinister",
            true_alignment=Alignment.NEUTRAL,
            temper=Temper.BRAVE,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[5, 4, 5, 3, 4, 2, 2, 4, 3, 4, 0, 2, 0, 2, 2, 2, 6, 5, 6, 5, 5, 2, 0, 2, 0, 2, 0, 4, 1, 3]),
            fixed_item=Treasure.BOOK_ILLUSION,
            fixed_item_name="Libram of Illusions",
        ),
        ValhallaHero(
            name="Koryo",
            true_alignment=Alignment.NEUTRAL,
            temper=Temper.BERSERK,
            race=Race.ORCISH,
            skills=SkillTable(raw_values=[0, 2, 2, 3, 1, 2, 1, 3, 1, 3, 2, 2, 0, 2, 0, 2, 3, 4, 0, 4, 2, 3, 0, 2, 0, 2, 1, 4, 1, 3]),
            fixed_item=Treasure.ABILITY_WHITE,
            fixed_item_name="Holy Grail",
        ),
        ValhallaHero(
            name="Haschish",
            true_alignment=Alignment.NEUTRAL,
            temper=Temper.BERSERK,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[7, 4, 7, 4, 2, 2, 1, 3, 1, 3, 0, 2, 1, 2, 0, 2, 2, 3, 2, 4, 0, 2, 0, 2, 0, 2, 0, 4, 2, 3]),
            fixed_item=Treasure.WAND_TORNADO,
            fixed_item_name="Bag of Dust-Devil Seeds",
        ),
        ValhallaHero(
            name="Bleys",
            true_alignment=Alignment.NEUTRAL,
            temper=Temper.BRAVE,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[5, 3, 4, 3, 2, 2, 3, 3, 2, 3, 5, 2, 2, 2, 2, 3, 2, 3, 3, 4, 4, 3, 1, 2, 3, 2, 3, 4, 4, 5]),
            fixed_item=Treasure.LEADERSHIP_HUMAN,
            fixed_item_name="Sword Excalibur",
        ),
        ValhallaHero(
            name="Orionair",
            true_alignment=Alignment.NEUTRAL,
            temper=Temper.BRAVE,
            race=Race.ORCISH,
            skills=SkillTable(raw_values=[0, 2, 1, 2, 0, 2, 1, 3, 3, 3, 4, 2, 4, 2, 4, 4, 4, 3, 4, 4, 3, 3, 0, 2, 0, 2, 0, 4, 2, 3]),
            fixed_item=Treasure.LEADERSHIP_DWARVEN,
            fixed_item_name="Axe of the Dwarven Lords",
        ),
        ValhallaHero(
            name="Dusty",
            true_alignment=Alignment.NEUTRAL,
            temper=Temper.BERSERK,
            race=Race.ORCISH,
            skills=SkillTable(raw_values=[3, 3, 1, 3, 1, 2, 3, 4, 6, 5, 6, 6, 0, 2, 0, 2, 0, 2, 0, 4, 2, 2, 0, 2, 1, 2, 0, 4, 1, 3]),
            fixed_item=Treasure.WAND_PART_SEA,
            fixed_item_name="Staff of Sea Mastery",
        ),
        ValhallaHero(
            name="Kitralus",
            true_alignment=Alignment.NEUTRAL,
            temper=Temper.BRAVE,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[3, 3, 6, 4, 3, 3, 3, 3, 3, 3, 3, 2, 3, 2, 4, 2, 4, 4, 4, 4, 2, 2, 1, 2, 2, 2, 2, 4, 2, 3]),
            fixed_item=Treasure.WEAPON_1,
            fixed_item_name="Holy Sword",
        ),
    ),
    Alignment.PAGAN: (
        ValhallaHero(
            name="Mary",
            true_alignment=Alignment.PAGAN,
            temper=Temper.BRAVE,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[3, 2, 3, 4, 0, 2, 3, 3, 3, 4, 4, 3, 1, 2, 6, 6, 7, 7, 1, 2, 2, 2, 0, 2, 0, 4, 0, 2, 1, 3]),
            fixed_item=Treasure.BOOK_ILLUSION,
            fixed_item_name="Libram of Illusions",
        ),
        ValhallaHero(
            name="Mary",
            true_alignment=Alignment.PAGAN,
            temper=Temper.BRAVE,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[3, 2, 3, 4, 0, 2, 3, 3, 3, 4, 4, 3, 1, 2, 6, 6, 7, 7, 1, 2, 2, 2, 0, 2, 0, 4, 0, 2, 1, 3]),
            fixed_item=Treasure.BOOK_ILLUSION,
            fixed_item_name="Libram of Illusions",
        ),
        ValhallaHero(
            name="Athar",
            true_alignment=Alignment.PAGAN,
            temper=Temper.BRAVE,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[4, 2, 5, 4, 1, 2, 1, 3, 2, 3, 2, 3, 2, 3, 1, 4, 3, 2, 0, 2, 3, 2, 0, 2, 0, 4, 1, 2, 1, 3]),
            fixed_item=Treasure.BOOK_ELEMENTAL,
            fixed_item_name="Periodic Table of Elements",
        ),
        ValhallaHero(
            name="Olaf",
            true_alignment=Alignment.PAGAN,
            temper=Temper.BERSERK,
            race=Race.DWARVEN,
            skills=SkillTable(raw_values=[3, 4, 2, 2, 2, 2, 1, 3, 4, 3, 6, 5, 0, 2, 9, 6, 0, 2, 0, 2, 3, 2, 0, 2, 0, 4, 2, 2, 1, 3]),
            fixed_item=Treasure.ABILITY_WHITE,
            fixed_item_name="Holy Grail",
        ),
        ValhallaHero(
            name="Dragkh",
            true_alignment=Alignment.PAGAN,
            temper=Temper.BRAVE,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[2, 2, 2, 4, 0, 2, 3, 3, 3, 3, 7, 7, 5, 3, 7, 5, 4, 3, 4, 4, 1, 2, 0, 2, 0, 4, 0, 2, 1, 3]),
            fixed_item=Treasure.BOOK_ARCHERY,
            fixed_item_name="Manual of Archery",
        ),
        ValhallaHero(
            name="Sredna",
            true_alignment=Alignment.PAGAN,
            temper=Temper.BRAVE,
            race=Race.DWARVEN,
            skills=SkillTable(raw_values=[1, 2, 2, 2, 0, 2, 4, 4, 5, 4, 9, 7, 5, 4, 9, 7, 5, 6, 7, 5, 0, 2, 0, 2, 0, 4, 0, 2, 2, 3]),
            fixed_item=Treasure.ABILITY_ILLUSION,
            fixed_item_name="Spectral Crystal",
        ),
        ValhallaHero(
            name="Blakes",
            true_alignment=Alignment.PAGAN,
            temper=Temper.CAUTIOUS,
            race=Race.ELVEN,
            skills=SkillTable(raw_values=[2, 2, 3, 2, 0, 2, 1, 3, 3, 3, 4, 3, 3, 2, 6, 7, 4, 3, 3, 3, 2, 3, 0, 2, 1, 4, 0, 2, 1, 3]),
            fixed_item=Treasure.ABILITY_PSYCHIC,
            fixed_item_name="Helm of Psychic Projection",
        ),
        ValhallaHero(
            name="Lancelot",
            true_alignment=Alignment.PAGAN,
            temper=Temper.BRAVE,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[3, 3, 2, 3, 0, 2, 2, 3, 2, 3, 6, 7, 2, 2, 0, 4, 6, 5, 0, 2, 3, 2, 0, 2, 1, 4, 0, 2, 1, 3]),
            fixed_item=Treasure.BOOK_SAGE,
            fixed_item_name="Library of Science",
        ),
        ValhallaHero(
            name="Lancelot",
            true_alignment=Alignment.PAGAN,
            temper=Temper.BRAVE,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[3, 3, 2, 3, 0, 2, 2, 3, 2, 3, 6, 7, 2, 2, 0, 4, 6, 5, 0, 2, 3, 2, 0, 2, 1, 4, 0, 2, 1, 3]),
            fixed_item=Treasure.BOOK_SAGE,
            fixed_item_name="Library of Science",
        ),
        ValhallaHero(
            name="Erinyes",
            true_alignment=Alignment.PAGAN,
            temper=Temper.BRAVE,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[4, 4, 0, 2, 0, 2, 1, 3, 2, 3, 2, 2, 3, 2, 3, 4, 4, 4, 3, 2, 3, 2, 0, 2, 0, 4, 0, 2, 1, 3]),
            fixed_item=Treasure.WEAPON_1,
            fixed_item_name="Holy Sword",
        ),
        ValhallaHero(
            name="Iguana",
            true_alignment=Alignment.PAGAN,
            temper=Temper.BRAVE,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[2, 2, 6, 5, 1, 2, 2, 3, 2, 3, 2, 2, 2, 2, 5, 4, 6, 5, 0, 2, 2, 2, 1, 2, 1, 4, 2, 2, 1, 3]),
            fixed_item=Treasure.BOOK_DRUID,
            fixed_item_name="Book of Druidic Incantations",
        ),
        ValhallaHero(
            name="Gelenor",
            true_alignment=Alignment.PAGAN,
            temper=Temper.BERSERK,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[3, 2, 5, 4, 2, 2, 4, 3, 5, 4, 4, 3, 0, 2, 7, 6, 5, 5, 0, 2, 3, 2, 1, 2, 2, 4, 1, 2, 1, 3]),
            fixed_item=Treasure.MONSTER_AID_WHALE,  # Phase 197: user-confirmed, see models/treasure.py's own gap note
            fixed_item_name="Horn of Neptune",
        ),
        ValhallaHero(
            name="Saruman",
            true_alignment=Alignment.PAGAN,
            temper=Temper.BERSERK,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[1, 3, 0, 2, 0, 2, 1, 3, 3, 4, 3, 2, 4, 2, 8, 6, 2, 3, 4, 2, 0, 2, 0, 2, 0, 4, 0, 2, 1, 3]),
            fixed_item=Treasure.WAND_HAND_OF_DEATH,
            fixed_item_name="Glove of Death",
        ),
        ValhallaHero(
            name="Dellums",
            true_alignment=Alignment.PAGAN,
            temper=Temper.BERSERK,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[1, 2, 0, 2, 0, 2, 1, 3, 2, 3, 3, 2, 3, 2, 4, 4, 3, 2, 4, 4, 3, 2, 0, 2, 0, 4, 0, 2, 1, 3]),
            fixed_item=Treasure.WEAPON_1,
            fixed_item_name="Holy Sword",
        ),
        ValhallaHero(
            name="Ganelon",
            true_alignment=Alignment.PAGAN,
            temper=Temper.CAUTIOUS,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[4, 3, 5, 5, 1, 2, 2, 3, 2, 3, 2, 2, 2, 2, 5, 4, 2, 2, 0, 2, 1, 3, 1, 2, 1, 4, 0, 2, 2, 3]),
            fixed_item=Treasure.LEADERSHIP_HUMAN,
            fixed_item_name="Sword Excalibur",
        ),
        ValhallaHero(
            name="Beowulf",
            true_alignment=Alignment.PAGAN,
            temper=Temper.BRAVE,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[2, 4, 1, 3, 3, 4, 2, 4, 5, 4, 0, 2, 0, 2, 1, 5, 0, 2, 0, 2, 0, 2, 1, 3, 2, 4, 0, 2, 1, 3]),
            fixed_item=Treasure.ABILITY_MELEE,
            fixed_item_name="Bracelets of Swordsmanship",
        ),
        ValhallaHero(
            name="Fafnir",
            true_alignment=Alignment.PAGAN,
            temper=Temper.BRAVE,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[3, 2, 3, 3, 0, 2, 1, 3, 1, 3, 2, 2, 1, 2, 5, 5, 2, 3, 2, 3, 1, 3, 0, 2, 0, 4, 0, 2, 1, 3]),
            fixed_item=Treasure.MONSTER_AID_EAGLE,
            fixed_item_name="Feather of the Great Eagle",
        ),
        ValhallaHero(
            name="Maverick",
            true_alignment=Alignment.PAGAN,
            temper=Temper.BERSERK,
            race=Race.ELVEN,
            skills=SkillTable(raw_values=[5, 5, 4, 2, 0, 2, 1, 3, 1, 3, 6, 4, 0, 2, 3, 4, 4, 2, 1, 2, 1, 3, 0, 2, 0, 4, 0, 2, 1, 3]),
            fixed_item=Treasure.ABILITY_TACTICAL,
            fixed_item_name="Standard of Command",
        ),
        ValhallaHero(
            name="Bryan",
            true_alignment=Alignment.PAGAN,
            temper=Temper.CAUTIOUS,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[4, 3, 3, 3, 2, 2, 4, 3, 1, 3, 1, 2, 0, 2, 2, 4, 4, 3, 2, 2, 3, 2, 0, 2, 1, 4, 0, 2, 1, 3]),
            fixed_item=Treasure.LEADERSHIP_HUMAN,
            fixed_item_name="Sword Excalibur",
        ),
        ValhallaHero(
            name="Xerxes",
            true_alignment=Alignment.PAGAN,
            temper=Temper.BRAVE,
            race=Race.DWARVEN,
            skills=SkillTable(raw_values=[2, 2, 1, 2, 2, 2, 1, 3, 3, 4, 4, 4, 3, 2, 2, 4, 5, 6, 1, 2, 0, 2, 0, 2, 1, 4, 0, 2, 1, 3]),
            fixed_item=Treasure.BOOK_TACTICAL,  # Phase 198: user-confirmed, see models/treasure.py's own gap note
            fixed_item_name="Hannibal's Grimoire",
        ),
        ValhallaHero(
            name="Taliesin",
            true_alignment=Alignment.PAGAN,
            temper=Temper.BERSERK,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[5, 3, 5, 3, 3, 2, 5, 3, 6, 4, 4, 4, 0, 2, 2, 4, 3, 3, 0, 2, 4, 3, 2, 2, 1, 4, 2, 2, 1, 3]),
            fixed_item=Treasure.WAND_RESURRECTION,
            fixed_item_name="Rod of Resurrection",
        ),
        ValhallaHero(
            name="Theodain",
            true_alignment=Alignment.PAGAN,
            temper=Temper.BERSERK,
            race=Race.DWARVEN,
            skills=SkillTable(raw_values=[3, 4, 3, 2, 0, 2, 3, 3, 5, 5, 4, 4, 0, 2, 0, 4, 1, 2, 0, 2, 2, 3, 0, 2, 1, 4, 1, 2, 1, 3]),
            fixed_item=Treasure.WAND_FLOOD,
            fixed_item_name="Feathers of Rain-Dancing",
        ),
        ValhallaHero(
            name="Kelderek",
            true_alignment=Alignment.PAGAN,
            temper=Temper.BRAVE,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[2, 2, 2, 3, 1, 2, 3, 3, 3, 3, 3, 3, 3, 4, 4, 4, 7, 5, 1, 2, 2, 2, 1, 2, 0, 4, 0, 2, 1, 3]),
            fixed_item=Treasure.WEAPON_2,
            fixed_item_name="Shadow Sword",
        ),
    ),
    Alignment.EVIL: (
        ValhallaHero(
            name="Theresa",
            true_alignment=Alignment.EVIL,
            temper=Temper.BRAVE,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[3, 3, 2, 4, 0, 2, 1, 3, 1, 3, 0, 2, 2, 4, 3, 3, 0, 2, 0, 2, 4, 3, 0, 4, 0, 2, 0, 2, 1, 3]),
            fixed_item=Treasure.WAND_HOLY_SYMBOL,
            fixed_item_name="Golden Cross",
        ),
        ValhallaHero(
            name="Randall",
            true_alignment=Alignment.UNDEAD,
            temper=Temper.BRAVE,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[4, 4, 3, 4, 0, 2, 1, 3, 2, 3, 0, 0, 8, 6, 2, 2, 0, 2, 1, 2, 2, 2, 0, 4, 0, 2, 0, 2, 1, 3]),
            fixed_item=Treasure.WAND_HAND_OF_DEATH,
            fixed_item_name="Glove of Death",
        ),
        ValhallaHero(
            name="Baltowyn",
            true_alignment=Alignment.EVIL,
            temper=Temper.BRAVE,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[4, 4, 3, 2, 0, 2, 1, 3, 1, 3, 3, 3, 4, 5, 2, 2, 6, 6, 1, 2, 1, 2, 0, 4, 0, 2, 0, 2, 1, 3]),
            fixed_item=Treasure.WAND_EARTHQUAKE,
            fixed_item_name="Stone of Shaking",
        ),
        ValhallaHero(
            name="Ukir",
            true_alignment=Alignment.UNDEAD,
            temper=Temper.BRAVE,
            race=Race.DWARVEN,
            skills=SkillTable(raw_values=[4, 3, 2, 2, 0, 2, 1, 3, 1, 3, 0, 0, 7, 6, 0, 2, 0, 2, 0, 2, 1, 3, 0, 2, 0, 2, 0, 2, 1, 3]),
            fixed_item=Treasure.WAND_TORNADO,
            fixed_item_name="Bag of Dust-Devil Seeds",
        ),
        ValhallaHero(
            name="Zarka",
            true_alignment=Alignment.UNDEAD,
            temper=Temper.BERSERK,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[5, 4, 3, 4, 0, 2, 1, 3, 1, 3, 0, 0, 6, 5, 0, 2, 0, 2, 0, 2, 1, 2, 0, 2, 0, 2, 0, 2, 1, 3]),
            fixed_item=Treasure.LEADERSHIP_ELVEN,
            fixed_item_name="Bow of the Elven Kings",
        ),
        ValhallaHero(
            name="Tim",
            true_alignment=Alignment.EVIL,
            temper=Temper.BRAVE,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[5, 3, 4, 4, 2, 2, 1, 3, 1, 3, 0, 2, 0, 4, 0, 2, 5, 4, 0, 2, 3, 2, 0, 4, 0, 2, 0, 2, 1, 3]),
            fixed_item=Treasure.BOOK_THIEF,
            fixed_item_name="Black Notebook of Thievery",
        ),
        ValhallaHero(
            name="Marihuana",
            true_alignment=Alignment.UNDEAD,
            temper=Temper.BRAVE,
            race=Race.DWARVEN,
            skills=SkillTable(raw_values=[3, 4, 4, 4, 0, 2, 1, 3, 1, 3, 0, 0, 7, 6, 0, 2, 0, 2, 2, 2, 2, 2, 0, 2, 1, 2, 2, 2, 1, 3]),
            fixed_item=Treasure.WAND_HAND_OF_DEATH,
            fixed_item_name="Glove of Death",
        ),
        ValhallaHero(
            name="Son",
            true_alignment=Alignment.EVIL,
            temper=Temper.BRAVE,
            race=Race.ELVEN,
            skills=SkillTable(raw_values=[4, 3, 0, 2, 5, 5, 1, 3, 1, 3, 1, 2, 4, 5, 5, 5, 0, 2, 0, 2, 3, 3, 0, 4, 0, 2, 0, 2, 1, 3]),
            fixed_item=Treasure.WAND_KILL_ENEMY,
            fixed_item_name="Needles of the Black Mage",
        ),
        ValhallaHero(
            name="Kirk",
            true_alignment=Alignment.EVIL,
            temper=Temper.BERSERK,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[3, 3, 2, 4, 0, 2, 1, 3, 1, 3, 4, 3, 7, 6, 4, 5, 3, 2, 5, 3, 3, 2, 0, 4, 0, 2, 0, 2, 1, 3]),
            fixed_item=Treasure.AMULET_ANTI_NECROMANCY,
            fixed_item_name="The True Cross",
        ),
        ValhallaHero(
            name="Ash",
            true_alignment=Alignment.EVIL,
            temper=Temper.BRAVE,
            race=Race.DWARVEN,
            skills=SkillTable(raw_values=[6, 5, 3, 4, 0, 2, 1, 3, 3, 3, 2, 2, 2, 4, 2, 2, 0, 2, 0, 3, 2, 2, 0, 4, 1, 2, 0, 2, 6, 4]),
            fixed_item=Treasure.WAND_FIREBALL,
            fixed_item_name="Wand of Fire",
        ),
        ValhallaHero(
            name="Skilza",
            true_alignment=Alignment.EVIL,
            temper=Temper.BRAVE,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[2, 2, 2, 2, 0, 2, 2, 3, 1, 3, 6, 5, 6, 4, 4, 4, 6, 5, 4, 4, 2, 2, 3, 4, 0, 2, 1, 2, 1, 4]),
            fixed_item=Treasure.WAND_ORATORY,
            fixed_item_name="Silver Horn of Oratory",
        ),
        ValhallaHero(
            name="Skilza",
            true_alignment=Alignment.EVIL,
            temper=Temper.BRAVE,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[2, 2, 2, 2, 0, 2, 2, 3, 1, 3, 6, 5, 6, 4, 4, 4, 6, 5, 4, 4, 2, 2, 3, 4, 0, 2, 1, 2, 1, 4]),
            fixed_item=Treasure.WAND_ORATORY,
            fixed_item_name="Silver Horn of Oratory",
        ),
        ValhallaHero(
            name="Skilza",
            true_alignment=Alignment.EVIL,
            temper=Temper.BRAVE,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[2, 2, 2, 2, 0, 2, 2, 3, 1, 3, 6, 5, 6, 4, 4, 4, 6, 5, 4, 4, 2, 2, 3, 4, 0, 2, 1, 2, 1, 4]),
            fixed_item=Treasure.WAND_ORATORY,
            fixed_item_name="Silver Horn of Oratory",
        ),
        ValhallaHero(
            name="Targhaz",
            true_alignment=Alignment.EVIL,
            temper=Temper.CAUTIOUS,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[5, 5, 4, 4, 0, 0, 5, 5, 4, 4, 0, 2, 4, 4, 7, 6, 2, 2, 3, 3, 2, 2, 0, 4, 0, 2, 0, 2, 1, 3]),
            fixed_item=Treasure.ABILITY_WHITE,
            fixed_item_name="Holy Grail",
        ),
        ValhallaHero(
            name="Wosha",
            true_alignment=Alignment.EVIL,
            temper=Temper.BRAVE,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[0, 2, 0, 2, 0, 2, 1, 3, 3, 3, 4, 3, 0, 4, 7, 8, 6, 4, 0, 2, 1, 2, 0, 4, 0, 2, 0, 2, 1, 3]),
            fixed_item=Treasure.WEAPON_2,
            fixed_item_name="Shadow Sword",
        ),
        ValhallaHero(
            name="Patz",
            true_alignment=Alignment.EVIL,
            temper=Temper.BRAVE,
            race=Race.DWARVEN,
            skills=SkillTable(raw_values=[7, 6, 4, 3, 0, 2, 1, 3, 2, 3, 3, 2, 7, 5, 2, 3, 2, 2, 0, 2, 3, 2, 0, 4, 1, 2, 0, 2, 2, 3]),
            fixed_item=Treasure.ABILITY_EXPLORER,
            fixed_item_name="Crystal of Direction",
        ),
        ValhallaHero(
            name="Typhon",
            true_alignment=Alignment.EVIL,
            temper=Temper.BRAVE,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[0, 2, 1, 2, 3, 4, 2, 3, 3, 3, 0, 2, 7, 6, 1, 2, 3, 2, 3, 2, 2, 2, 2, 4, 1, 2, 0, 2, 1, 3]),
            fixed_item=Treasure.LEADERSHIP_ORCISH,
            fixed_item_name="Scimitar of Orc Mastery",
        ),
        ValhallaHero(
            name="Gelenor",
            true_alignment=Alignment.EVIL,
            temper=Temper.BRAVE,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[4, 5, 4, 5, 0, 2, 1, 3, 1, 3, 0, 2, 5, 6, 0, 2, 0, 2, 0, 2, 1, 2, 0, 4, 0, 2, 0, 2, 4, 3]),
            fixed_item=Treasure.AMULET_ANTI_ELEMENTAL,
            fixed_item_name="Golden Orb of Elemental Stability",
        ),
        ValhallaHero(
            name="Dracula",
            true_alignment=Alignment.EVIL,
            temper=Temper.CAUTIOUS,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[2, 4, 1, 3, 0, 2, 1, 3, 3, 4, 0, 2, 4, 4, 0, 2, 3, 4, 2, 4, 1, 3, 2, 4, 1, 3, 1, 3, 1, 3]),
            fixed_item=Treasure.ABILITY_THIEF,
            fixed_item_name="Cloak of Stealth",
        ),
        ValhallaHero(
            name="Wooz",
            true_alignment=Alignment.EVIL,
            temper=Temper.COWARDLY,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[3, 3, 2, 4, 0, 2, 2, 3, 2, 3, 2, 2, 1, 4, 2, 2, 0, 2, 0, 2, 2, 3, 0, 4, 2, 2, 0, 2, 2, 3]),
            fixed_item=Treasure.ABILITY_DRUID,
            fixed_item_name="Everlasting Mistletoe",
        ),
        ValhallaHero(
            name="Enkil",
            true_alignment=Alignment.EVIL,
            temper=Temper.CAUTIOUS,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[1, 2, 5, 4, 0, 2, 1, 3, 3, 3, 5, 5, 3, 4, 1, 2, 5, 5, 2, 2, 2, 2, 0, 4, 1, 2, 0, 2, 3, 3]),
            fixed_item=Treasure.ABILITY_SPY,
            fixed_item_name="X-Ray Spyglass",
        ),
        ValhallaHero(
            name="Strahd",
            true_alignment=Alignment.EVIL,
            temper=Temper.BRAVE,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[2, 2, 5, 5, 2, 2, 2, 3, 2, 3, 2, 2, 2, 4, 3, 4, 0, 2, 2, 2, 2, 2, 0, 4, 3, 2, 0, 2, 1, 3]),
            fixed_item=Treasure.BOOK_PSYCHIC,
            fixed_item_name="Codex of Mental Prowess",
        ),
        ValhallaHero(
            name="Masha",
            true_alignment=Alignment.EVIL,
            temper=Temper.BERSERK,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[3, 2, 2, 2, 2, 2, 2, 3, 1, 3, 0, 2, 5, 6, 0, 2, 4, 4, 0, 2, 2, 2, 0, 4, 1, 2, 0, 2, 2, 3]),
            fixed_item=Treasure.WAND_CLAIRVOYANCE,
            fixed_item_name="Crystal of Seeing",
        ),
        ValhallaHero(
            name="Isabella",
            true_alignment=Alignment.EVIL,
            temper=Temper.BERSERK,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[5, 3, 6, 4, 2, 2, 2, 3, 1, 3, 0, 2, 1, 4, 0, 2, 0, 2, 0, 2, 5, 4, 0, 4, 2, 2, 0, 2, 6, 5]),
            fixed_item=Treasure.WAND_FIREBALL,
            fixed_item_name="Wand of Fire",
        ),
        ValhallaHero(
            name="Solomon",
            true_alignment=Alignment.EVIL,
            temper=Temper.BRAVE,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[6, 4, 7, 5, 1, 2, 3, 3, 3, 3, 2, 2, 4, 5, 2, 2, 2, 3, 2, 2, 3, 2, 2, 4, 2, 2, 2, 2, 1, 5]),
            fixed_item=Treasure.ABILITY_NECROMANCY,
            fixed_item_name="Amulet of Orgoth",
        ),
        ValhallaHero(
            name="Fist",
            true_alignment=Alignment.EVIL,
            temper=Temper.BRAVE,
            race=Race.ORCISH,
            skills=SkillTable(raw_values=[7, 5, 6, 3, 2, 2, 2, 3, 2, 3, 1, 2, 6, 5, 6, 5, 6, 5, 8, 7, 5, 3, 2, 4, 2, 2, 1, 2, 3, 3]),
            fixed_item=Treasure.WAND_PART_SEA,
            fixed_item_name="Staff of Sea Mastery",
        ),
        ValhallaHero(
            name="Marius",
            true_alignment=Alignment.EVIL,
            temper=Temper.CAUTIOUS,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[2, 2, 5, 4, 0, 2, 1, 3, 1, 3, 2, 2, 6, 6, 0, 2, 3, 2, 4, 4, 0, 2, 0, 2, 0, 2, 0, 2, 1, 3]),
            fixed_item=Treasure.ABILITY_PSYCHIC,
            fixed_item_name="Helm of Psychic Projection",
        ),
        ValhallaHero(
            name="Severius",
            true_alignment=Alignment.EVIL,
            temper=Temper.CAUTIOUS,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[2, 2, 4, 2, 1, 2, 1, 3, 2, 3, 4, 3, 5, 5, 5, 3, 2, 2, 1, 2, 2, 2, 0, 4, 0, 2, 0, 2, 1, 3]),
            fixed_item=Treasure.ABILITY_NECROMANCY,
            fixed_item_name="Amulet of Orgoth",
        ),
        ValhallaHero(
            name="Dietrich",
            true_alignment=Alignment.EVIL,
            temper=Temper.CAUTIOUS,
            race=Race.HUMAN,
            skills=SkillTable(raw_values=[6, 4, 9, 7, 2, 2, 2, 3, 2, 3, 2, 2, 0, 4, 0, 2, 0, 2, 0, 2, 2, 2, 0, 4, 1, 2, 0, 2, 1, 3]),
            fixed_item=Treasure.LEADERSHIP_HUMAN,
            fixed_item_name="Sword Excalibur",
        ),
    ),}


def _u(name: str, alignment: Alignment, temper: Temper, race: Race, skills: list[int]) -> ValhallaHero:
    """Phase 551 -- constructs one ``VALHALLA_ROSTER_UNCONFIRMED`` entry.
    See that dict's own docstring for exactly why ``true_alignment``/
    ``fixed_item``/``fixed_item_name`` are placeholders rather than
    sourced values.
    """

    return ValhallaHero(
        name=name,
        true_alignment=alignment,
        temper=temper,
        race=race,
        skills=SkillTable(raw_values=skills),
        fixed_item=None,
        fixed_item_name="(unresolved -- no VALHALLA GOOD.txt-equivalent narrative source exists for this hero)",
    )


# Phase 551 -- 27 further heroes found during a fresh Valhalla audit,
# real and present in the actual game data (`AKGEN_name_catalogs.json.txt
# valhalla_hero_rosters.rosters`, sourced from the real `GOOD2.X2`/
# `DRUIDIC2.X2`/`NEUTRAL2.X2`/`PAGAN2.X2`/`EVIL2.X2` files AKGEN reads),
# but **deliberately excluded from `VALHALLA_ROSTER`/real Gate Angel
# selection** -- see this dict's own module-level note below for why.
#
# **Why these exist at all.** `AKGEN_reverse_engineering_report.md`
# confirms the real roster is *not* closed: "Induct_Val incrementa il
# conteggio e appende ai due file dell'allineamento il personaggio
# ammesso in Valhalla" -- new legendary heroes get appended as real
# players earn them (`Roderoch` in the `GW3` corpus, `Clarissa` in
# `GW900`), so the distributed roster (178 raw records, 163 unique
# names) grew past whatever snapshot the user's own `VALHALLA GOOD.txt`/
# `VALHALLA DRUID.txt`/`VALHALLA NEUTRAL.txt`/`VALHALLA PAGAN.txt`/
# `VALHALLA EVIL.txt` files captured (137 heroes) before this audit.
# Cross-checked exhaustively: every one of the 137 heroes already in
# `VALHALLA_ROSTER` is present in the AKGEN catalog too (zero
# mismatches) -- these 27 are a clean, additive difference, not a
# correction to anything already there.
#
# **What's sourced here, and how**: `name`, `race`, `temper`, and
# `skills` -- decoded from each entry's own `stats_raw`/`skills_raw`
# fields, cross-checked against all 137 already-confirmed heroes before
# trusting the decode on new ones (every single one of ~20 independent
# checks matched exactly, zero exceptions): `stats_raw[2]` is Race
# (0=Human, 1=Elven, 2=Dwarven, 3=Orcish -- confirmed by a literal
# footer comment recovered from the same file, `"Race: 0=Human,
# 1=Elven, 2=Dwarven, 3=Orcish"`), `stats_raw[10]` is Temper (0-3,
# matching this project's own `Temper` enum ordinals exactly --
# confirmed by another literal footer comment, `"Tempers: 0=Cowardly,
# 3=Berserk"`), and `skills_raw`'s own first 30 values match `SkillTable.
# raw_values`'s format exactly (verified byte-for-byte against every
# one of the 137 already-transcribed heroes, e.g. Basil).
#
# **What's NOT sourced, and why these stay excluded from real
# selection**: `true_alignment` (Divine/Undead vs. the bucket's own
# Good/Evil -- for the existing 137, this always came from the
# original narrative text files' own prose, never from any numeric
# AKGEN field checked here) and `fixed_item` (searched `stats_raw` for
# a plausible Treasure-ordinal-range field; the closest candidates
# include negative numbers, ruling them out as a plain item index --
# the existing 137's own items likewise came only from the narrative
# files' own "Oggetto:" lines). Both fields are placeholders below
# (`true_alignment` defaults to the bucket's own alignment -- the
# majority case among the 137 anyway; `fixed_item=None`, matching this
# project's own pre-existing convention for the 2 of the original 137
# whose item was similarly unresolved). Per the user's own explicit
# choice: these 27 stay documented, sourced as far as the data allows,
# and reachable for a future phase that gets the missing narrative
# source -- but **`VALHALLA_ROSTER_UNCONFIRMED` is never read by
# `_select_visitor_template()`/`finalize_gate_angel_visit()`/anything
# else that actually runs a game** (confirmed: grep the whole codebase
# for this name outside this file and its own tests -- no hits), so
# none of these 27 can ever actually appear as a Gate Angel visitor.
#
# **Two anomalous entries, kept but flagged**: Pagan's `Royal Heir`
# and Evil's `Royal Heir 0` read as the game's own generic zero-skill
# throne-successor placeholder (`GameState.remove_leader()`'s own
# Phase 259 "Royal Heir" concept), not a genuine named legendary hero --
# transcribed here for completeness (the user's own explicit "27"
# count included them) rather than silently dropped, but almost
# certainly not real Valhalla characters.
VALHALLA_ROSTER_UNCONFIRMED: dict[Alignment, tuple[ValhallaHero, ...]] = {
    Alignment.GOOD: (
        _u("Paradigm", Alignment.GOOD, Temper.BRAVE, Race.HUMAN,
           [4, 3, 3, 4, 2, 2, 1, 2, 2, 3, 5, 3, 1, 4, 2, 2, 5, 2, 1, 5, 1, 2, 0, 3, 1, 2, 0, 2, 2, 2]),
        _u("Shadowrun", Alignment.GOOD, Temper.BRAVE, Race.HUMAN,
           [6, 4, 5, 3, 3, 2, 2, 3, 2, 3, 6, 5, 0, 2, 2, 2, 1, 3, 2, 2, 1, 3, 0, 2, 0, 2, 0, 2, 1, 5]),
        _u("James", Alignment.GOOD, Temper.BRAVE, Race.HUMAN,
           [4, 3, 5, 3, 0, 2, 2, 3, 2, 3, 4, 4, 2, 2, 2, 2, 5, 4, 3, 3, 1, 2, 0, 2, 0, 2, 0, 2, 1, 4]),
        _u("Pinotto", Alignment.GOOD, Temper.BRAVE, Race.HUMAN,
           [7, 5, 3, 4, 0, 2, 1, 3, 3, 3, 7, 5, 4, 3, 3, 3, 4, 4, 2, 2, 5, 2, 0, 2, 0, 2, 2, 2, 1, 5]),
        _u("Haile' Sel", Alignment.GOOD, Temper.BRAVE, Race.ORCISH,
           [6, 6, 5, 4, 0, 2, 1, 3, 1, 3, 0, 4, 1, 2, 0, 2, 2, 2, 0, 2, 4, 3, 0, 2, 1, 2, 1, 2, 3, 5]),
        _u("David", Alignment.GOOD, Temper.BRAVE, Race.HUMAN,
           [1, 2, 3, 2, 0, 2, 2, 3, 3, 3, 5, 5, 0, 0, 3, 2, 5, 5, 2, 2, 2, 2, 0, 2, 0, 2, 0, 2, 1, 3]),
        _u("Evelyn", Alignment.GOOD, Temper.CAUTIOUS, Race.ELVEN,
           [6, 4, 4, 2, 1, 2, 2, 3, 5, 3, 4, 4, 0, 2, 0, 2, 4, 3, 1, 2, 2, 3, 2, 2, 2, 2, 2, 2, 2, 4]),
    ),
    Alignment.DRUID: (
        _u("Kratos", Alignment.DRUID, Temper.BRAVE, Race.HUMAN,
           [9, 5, 6, 4, 2, 2, 1, 3, 3, 3, 2, 3, 2, 2, 2, 3, 0, 4, 0, 2, 6, 4, 2, 2, 2, 2, 1, 2, 2, 3]),
    ),
    Alignment.NEUTRAL: (
        _u("Artur", Alignment.NEUTRAL, Temper.BRAVE, Race.ELVEN,
           [6, 5, 5, 6, 4, 3, 1, 3, 1, 3, 2, 3, 0, 2, 0, 2, 0, 2, 0, 4, 4, 3, 0, 2, 0, 2, 1, 4, 1, 3]),
        # Phase 560: a second real "Artur" slot -- AKGEN_complete_
        # name_lists.md's own raw NEUTRAL2.X2 catalog has this name at
        # two distinct source indices (6 and 8); repeated verbatim here
        # (not independently re-decoded -- the source gives no second,
        # differing stats block for this one) purely so this bucket's
        # own true 2-slot multiplicity is preserved for whenever a
        # future phase promotes VALHALLA_ROSTER_UNCONFIRMED into real
        # selection.
        _u("Artur", Alignment.NEUTRAL, Temper.BRAVE, Race.ELVEN,
           [6, 5, 5, 6, 4, 3, 1, 3, 1, 3, 2, 3, 0, 2, 0, 2, 0, 2, 0, 4, 4, 3, 0, 2, 0, 2, 1, 4, 1, 3]),
        _u("Boland", Alignment.NEUTRAL, Temper.BRAVE, Race.ELVEN,
           [8, 6, 4, 4, 0, 2, 1, 3, 1, 3, 0, 2, 2, 2, 3, 2, 3, 2, 1, 4, 4, 3, 1, 2, 0, 2, 1, 4, 1, 3]),
        _u("BOuHCTBEHHAR", Alignment.NEUTRAL, Temper.BRAVE, Race.HUMAN,
           [3, 2, 3, 4, 0, 2, 3, 3, 2, 3, 4, 3, 0, 2, 3, 3, 0, 2, 0, 4, 2, 2, 2, 2, 0, 2, 0, 4, 1, 3]),
        _u("GaD", Alignment.NEUTRAL, Temper.CAUTIOUS, Race.ELVEN,
           [6, 4, 2, 3, 0, 2, 2, 4, 4, 4, 2, 2, 4, 2, 1, 2, 2, 2, 1, 4, 2, 2, 0, 2, 0, 2, 0, 4, 1, 3]),
        _u("Two-Headed_Eagl", Alignment.NEUTRAL, Temper.CAUTIOUS, Race.HUMAN,
           [4, 3, 2, 2, 0, 2, 3, 3, 3, 3, 4, 4, 2, 2, 3, 3, 3, 3, 3, 4, 4, 3, 4, 3, 0, 2, 7, 5, 3, 3]),
        _u("Tyresian", Alignment.NEUTRAL, Temper.BRAVE, Race.HUMAN,
           [3, 3, 4, 4, 2, 2, 4, 3, 2, 3, 2, 2, 2, 2, 2, 2, 4, 3, 2, 4, 2, 2, 1, 2, 2, 2, 2, 4, 3, 3]),
        _u("Anova", Alignment.NEUTRAL, Temper.BERSERK, Race.HUMAN,
           [4, 3, 3, 3, 1, 2, 1, 3, 3, 3, 4, 4, 4, 4, 5, 5, 1, 2, 2, 3, 1, 2, 0, 2, 1, 2, 0, 4, 1, 3]),
    ),
    Alignment.PAGAN: (
        _u("AMA3OHKA", Alignment.PAGAN, Temper.BRAVE, Race.ORCISH,
           [3, 4, 4, 4, 0, 2, 3, 3, 3, 3, 3, 3, 2, 2, 4, 4, 2, 2, 0, 2, 2, 3, 0, 2, 0, 4, 0, 2, 1, 3]),
        _u("Rulehard", Alignment.PAGAN, Temper.CAUTIOUS, Race.HUMAN,
           [3, 3, 5, 2, 0, 5, 3, 1, 3, 3, 2, 3, 1, 2, 4, 2, 2, 5, 3, 3, 2, 2, 0, 2, 0, 2, 0, 4, 1, 2]),
        _u("Sparafuci", Alignment.PAGAN, Temper.BRAVE, Race.ORCISH,
           [3, 3, 4, 3, 1, 2, 1, 3, 1, 3, 4, 3, 2, 2, 4, 4, 2, 4, 3, 2, 2, 3, 0, 2, 0, 4, 0, 2, 1, 3]),
        _u("Starfire", Alignment.PAGAN, Temper.BRAVE, Race.ELVEN,
           [2, 2, 2, 2, 5, 3, 1, 3, 2, 3, 4, 3, 2, 2, 0, 4, 3, 2, 0, 2, 4, 4, 0, 2, 0, 4, 0, 2, 1, 3]),
        _u("Bee-Bop", Alignment.PAGAN, Temper.CAUTIOUS, Race.DWARVEN,
           [2, 2, 3, 4, 0, 2, 2, 3, 1, 3, 5, 5, 3, 3, 5, 4, 5, 5, 2, 2, 3, 2, 0, 2, 0, 4, 0, 2, 1, 3]),
        _u("SWK", Alignment.PAGAN, Temper.BERSERK, Race.ORCISH,
           [6, 3, 4, 2, 4, 2, 2, 3, 5, 3, 3, 3, 5, 5, 6, 6, 4, 2, 1, 3, 6, 3, 1, 2, 0, 4, 1, 2, 1, 3]),
        # Anomalous -- see module comment above: almost certainly a
        # generic Royal Heir placeholder, not a real legendary hero.
        _u("Royal Heir", Alignment.PAGAN, Temper.BRAVE, Race.ELVEN,
           [2, 2, 0, 2, 5, 3, 3, 3, 1, 3, 2, 2, 1, 2, 6, 6, 4, 4, 0, 2, 1, 3, 0, 2, 1, 4, 1, 2, 1, 3]),
    ),
    Alignment.EVIL: (
        _u("RasAlGul", Alignment.EVIL, Temper.COWARDLY, Race.HUMAN,
           [5, 5, 5, 4, 1, 2, 1, 3, 1, 3, 0, 0, 6, 5, 0, 2, 0, 2, 0, 2, 3, 3, 0, 2, 0, 2, 0, 2, 2, 3]),
        _u("John", Alignment.EVIL, Temper.BERSERK, Race.DWARVEN,
           [6, 6, 2, 4, 0, 2, 1, 3, 1, 3, 2, 2, 5, 5, 0, 2, 3, 3, 0, 1, 1, 3, 5, 4, 0, 2, 0, 2, 1, 3]),
        _u("Aragorn", Alignment.EVIL, Temper.BERSERK, Race.ORCISH,
           [5, 4, 5, 4, 1, 2, 1, 3, 1, 3, 0, 2, 4, 4, 0, 2, 2, 2, 0, 2, 1, 2, 0, 4, 0, 2, 0, 2, 3, 3]),
        _u("TNSTFL", Alignment.EVIL, Temper.BRAVE, Race.ELVEN,
           [4, 2, 3, 4, 2, 2, 2, 3, 3, 3, 3, 3, 4, 4, 5, 5, 3, 2, 2, 2, 3, 3, 0, 4, 2, 2, 0, 2, 1, 3]),
        # Anomalous -- see module comment above.
        _u("Royal Heir 0", Alignment.EVIL, Temper.COWARDLY, Race.ORCISH,
           [4, 3, 2, 2, 0, 2, 1, 3, 1, 3, 4, 3, 0, 4, 2, 3, 1, 2, 3, 2, 3, 3, 0, 4, 2, 2, 0, 2, 1, 3]),
    ),
}
