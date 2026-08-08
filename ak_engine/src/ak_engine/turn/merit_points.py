"""Imperial Office Merit Point formulas -- rulebook page 51's "TABELLA
DELLE CARICHE IMPERIALI" (user-supplied PDF, studied directly; quoted
below in the relevant sections), Phase 227.

**This closes the formula half of a gap Phase 137 called a "confirmed,
permanent dead end."** That phase found `REPORTS.PAS`'s real `Ofc_Pts`/
`Rank` scoring formulas but couldn't build them: nearly every office's
own points formula reads a global (`lgenp`/`ladmp`/`lmhpp`/`lwmsp`/`oops`/
`tipts`/`seatax`/`alltax`/`lfdisc`/`ldiscp`) declared nowhere in the
surviving 14 `.PAS` files -- their true declarations live in a missing
compiled-only unit. **That conclusion still stands for the Pascal source
itself** -- those globals are still unrecoverable, and this module makes
no claim to reproduce them bit-for-bit. What changed is the source: the
user supplied the rulebook's own printed "TABELLA DELLE CARICHE
IMPERIALI" (page 51), a different, independently authoritative
description of the same 8 formulas in the game's own official terms
("Attribuzione dei Punti Merito" per office) -- not a Pascal
transcription, but a real, sourced, directly-quoted rule, the same
standing this project already gives every other rulebook excerpt the
user has supplied (the Alignment-reduction table, the Emperor election
thresholds).

**The 8 offices and their real 20%/10%x7 Victory Point quotas already
matched `models/office.py OFFICE_VALUE` exactly before this phase** --
independent cross-confirmation the two sources describe the same system.

## Emperor (20%)
"Ammontare della rendita di tasse alla fine del gioco" -- the kingdom's
tax revenue at game end. This is exactly `turn/tax_base.py
compute_tax_base()` (Phase 225), reused directly rather than
reimplemented.

## Gran Cancelliere / Chancellor (10%)
- +1 per level in Explorer, Spy, and Sage
- +2 per Special Place (Feature) discovered first
- Invention (Discovery) attribution: **3 points to the world's first
  hero/King ever to discover a given Discovery, 2 points to every
  later, independent discoverer of that same Discovery** -- a
  user-specified, project-original scoring rule (confirmed 2026-07-29)
  that *supersedes* the rulebook's own flat "+2 per Invention found
  first" figure quoted above the fix (the rulebook itself gives no
  points at all for a non-first personal discovery; this project's own
  owner chose to score both cases, at these two values, rather than
  leave the non-first case at zero).
- +1 per Invention obtained via espionage

**All four terms are now live.** `features_discovered_first` is live
as of **Phase 256**: `models/feature.py Feature.discovered_by_kingdom`
(a per-kingdom dict, Phase 75) already exists and is written by
`turn/exploration.py discover_features()` every time a kingdom first
discovers a Special Place; `turn/plan_dispatch.py`'s own
`ActionCode.EXPLORE` branch checks, for each newly-discovered feature,
whether that kingdom's own entry is still the *only* one in the dict
(nobody else got there first) and credits the acting leader's own
`MeritTally.features_discovered_first` when so.

`discoveries_found_first`/`discoveries_found_not_first` (Phase 271)
and `discoveries_via_espionage` (Phase 267) are live too, now that a
real Discovery-acquisition mechanic exists (`KingdomState.discoveries`,
Phase 266): `turn/practice_execution.py execute_practice()`'s own SAGE
branch checks a new global registry, `GameState.discoveries_first_
found_by` (written once, permanently, the instant any Kingdom's own
`discoveries` set gains a Discovery no other Kingdom's own set already
held) to decide which of the two counters -- and therefore which of
the 3-point/2-point figures above -- a successful grant credits.

## Tesoriere Imperiale / Treasurer (10%)
"Il tesoro più sostanzioso alla fine del gioco" -- the kingdom's own
`KingdomState.treasury`. Fully live; Phase 137's own speculation
("`Treasurer`'s `lgold[ldran]` is plausibly just that King's own
treasury") is now confirmed by the rulebook's own text, not a guess.

## Gran Maresciallo / Marshal (10%)
Original page-51 rule (quoted verbatim, now **superseded** for the
per-unit magnitude -- see the Phase 308 addendum below): "Per ogni
battaglia terrestre comandata: se vinta, per ciascuna unità
dell'esercito nemico +1; se persa, per ciascuna unità nel proprio
esercito -1." `MeritTally.land_battles_won_points`/
`land_battles_lost_points` are **live as of Phase 254**:
`turn/battle_orchestrator.py _record_battle_merit()` credits/debits
each side's own Supreme Commander (`None` for an unled side -- not a
"battaglia comandata" for anyone) right after `fight_battle()` resolves
`battle_result.winner`, counting the *entire* opposing army fielded
(one `ArmyState` = one "unità", the project's own existing 1:1
army<->`BattleUnit` correspondence), not just casualties. A `"tie"`
records nothing for either side -- the rulebook's own "vinta"/"persa"
wording doesn't address one.

**Phase 308 addendum -- the flat +1/-1-per-unit rule above is replaced
by a quality-weighted table.** `Regolamento AK.txt`'s own "NUOVE REGOLE
E MODIFICHE" appendix (the same layer already mined for Patrol,
Bless's graveyard-clearing addendum, Invisibility's +30% flee bonus,
Defend-cancel-on-loss, and the real MARCH TABLE, Phase 307), quoted in
full: "Adesso per la Carica di Maresciallo conta la qualità delle unità
sconfitte secondo questa tabella: Reclute 0 punti / Medio 1 punto /
Veterani 2 punti / Crack 3 punti / Elite 4 punti. Una Garrison che
attacca ha un modificatore di -1 su questa tabella (una Garrison Crack
che attacca e viene distrutta dà solo 2 punti al generale che l'ha
vinta)."

`MARSHAL_QUALITY_POINTS`/`battle_quality_points()` implement this
directly -- "Reclute"/"Medio" are this project's own already-established
Italian<->English `Quality` mapping (`GREEN`/`AVERAGE`, `turn/combat.py
QUALITY_NAME` and every other consumer already use this pairing).
**`Quality.DEPLETED` has no entry of its own in the quoted
table** -- read as 0 (the table's own floor, the same "clamp rather
than extrapolate" convention `march_unite_chance()` established, Phase
307), which happens to make the whole table exactly
`max(0, int(quality) - 1)` -- a clean coincidence of this project's own
`Quality` ordinal values, not a formula the rulebook states directly, so
the explicit dict stays the source of truth rather than that shortcut.
**The Garrison modifier's own per-unit floor is unstated**: the
rulebook's own worked example only tests a Crack Garrison (3 points,
-1 -> 2, still positive) -- nothing rules out a weaker attacking
Garrison's own per-unit score going negative (e.g. a defeated Green
attacking Garrison scores -1, not 0), so `battle_quality_points()`
applies the literal subtraction with no invented floor.

`_record_battle_merit()` (`turn/battle_orchestrator.py`) now sums this
per-unit table over the real, defeated side's own `ArmyState` list
(``army_type``/``quality`` as fielded, matching this same function's
own pre-existing "count everything fielded, not just casualties"
reading) instead of a flat per-unit constant -- see that function's own
Phase 308 addendum.

## Grande Ammiraglio / Admiral (10%)
Same won/lost-unit formula as Marshal but for naval battles (also live
as of Phase 254, same `_record_battle_merit()` call, keyed off
`terrain is Terrain.SEA`), **plus**: "Per ogni livello di abilità
Navale +1" (live -- `LeaderState.skills`) and "Per ogni provincia di
mare con rendita di 2+ gold +1" -- footnote 1 confirms this last term
is a flat per-kingdom count applied to *every* character of that
kingdom, not per-leader-owned territory, so `admiral_merit_points()`
counts qualifying sea provinces once per `leader.kingdom_id` and adds
the same figure for every leader who shares that kingdom.

**Phase 308 addendum -- extended the same quality table.** The NUOVE
REGOLE text above names only "la Carica di Maresciallo" -- Admiral
isn't mentioned by name. Applied here anyway, for two reasons stated
plainly rather than assumed silently: this project's own pre-existing
docstring already treats Admiral's own battle term as "Same won/lost-
unit formula as Marshal... for naval battles" (one shared formula, two
offices, since the original page-51 text itself gives both offices the
identical wording); and the user's own request that prompted this phase
explicitly named both offices together ("Punteggio Gran Maresciallo/
Grande Ammiraglio"). `MeritTally.naval_battles_won_points`/
`naval_battles_lost_points` (renamed from `..._enemy_units`/`..._own_
units`, since they now hold quality points, not raw unit counts) feed
the same subtraction as Marshal's own formula; the Garrison-attacker
modifier applies here too, purely for uniformity -- a naval Garrison
attack isn't a shape this project's own data has ever shown, so the
modifier is expected to be inert here in practice, not a claim that
naval Garrisons are a real, attested unit shape.

## Gran Difensore / Defender (10%)
"Per ciascun mostro ucciso: totale Punti Ferita del mostro (metà dei
punti se neutralizzato con trattative)." Footnote 2: no points for a
Fulfilled quest agreement; a monster persuaded to stop raiding (rather
than killed) via negotiation/damage scores half. `MeritTally.
monster_hp_defeated`/`monster_hp_neutralized` store the raw, unhalved HP
sums the caller observed; `defender_merit_points()` applies the halving
(floor division) so the tally itself stays a faithful raw record.
`monster_hp_defeated` is **live as of Phase 255**: `turn/
search_execution.py execute_search()`'s own `_outcome_from()` credits
the guardian's starting hit points whenever the leader wins the
encounter (Melee, Fire Arrow, or a Cast-tactic instant kill). The
negotiated half, `monster_hp_neutralized`, is **also live, as of Phase
258** (bugfixed Phase 301 against a double-halving mistake, see that
function's own addendum): `_resolve_fulfill()`, same module, credits
the raw unhalved HP total when a prior turn's Talk-negotiated deal is
successfully honored. Both writers confirmed current as of Phase
441 -- this paragraph itself had drifted stale after Phase 258 landed,
still describing the pre-258 state until corrected.

## Gran Sacerdote / Priest (10%)
"Per ogni incantesimo Resurrection o Bless riuscito +1" (either spell,
same +1 -- the table doesn't distinguish) plus "+2 per ciascun livello
nei Talenti Druidico e Magia Bianca." Both terms are live as of Phase
251: `turn/cast_execution.py`'s own `_execute_resurrection`/
`_execute_bless` each increment `MeritTally.resurrection_bless_casts`
by 1 on success -- the project's first real `MeritTally` writer,
closing the gap this dataclass's own Phase 227 docstring flagged
("no action in this project is wired to increment yet").

## Arcimago di Palazzo / Mage (10%)
"Per ogni livello in tutti i Talenti Magici +1" (the 5 spell-casting
Abilities: White, Necromancy, Elemental, Psychic, Illusion -- Druidic is
its own separate Talent, already claimed by Priest above, not counted
here) plus "+1 per ciascun oggetto magico in grado di lanciare
incantesimi posseduto" -- `models/treasure.py TreasureCategory.
SPELL_WAND` is exactly "a Use_MI-castable wand" (the project's own
existing, sourced category for "operates by casting a spell"), not
`SKILL_BOOK` (a one-shot item consumed on read, not an ongoing
possession the rulebook's "posseduto" implies). Both terms are fully
live: skills via `LeaderState.skills`, wands via `GameState.
items_held_by()`.

## King of Pain / Office.EVIL_KING (Phase 277, reformulated Phase 369)
Phase 277 built this from `CARICHE E ABLITÀ.txt` (tasse + NE skill + TH
skill + monster kills + successful Steal tactics). **Phase 369 found
this doesn't match reality.** `AKGEN_embedded_catalogs.json gw_format.
royal_title_system` id 27 -- a real static disassembly of `AKGEN.EXE`/
`AK.EXE`/`AK.OVR`, verified against the 12 `GW3__T1..T12` historical
saves -- gives King of Pain's real compiled formula as `current Tax_
Base(King); no cumulative title record`: exactly Emperor's own formula
(`compute_tax_base()`), just restricted to the Evil-aligned King with
the highest current tax base. No skill terms, no monster-kill term, no
tally at all. `evilking_merit_points()` now reflects this directly.
**King-only, and Evil-alignment-only** still holds (`eligibility` in
the same JSON: `"Kings only, alignment exactly Evil"`) -- `_king_of_
alignment()` still gates it, the same idiom the other 6 alignment-King
titles below share.

## Prince of Thieves / Office.THIEF_PRINCE (Phase 277, reformulated Phase 369)
Phase 277 built this from `CARICHE E ABLITÀ.txt` (TH skill + gold
stolen + 5x magic items stolen). The same disassembly (id 36) gives the
real formula as plain `Tit_Pts(leader,title)`: **+1 per successful
theft result**, full stop -- "the compiled code contains two separate
success paths that award the point," no TH-skill term, no distinction
between gold and item stolen. `thiefprince_merit_points()` now reads a
single cumulative `MeritTally.successful_thefts` counter. Still open to
a King *or* a Hero (`"eligible": "leader (King or Hero)"`), no
eligibility gate needed.

## The "10 restanti Punti Merito" legendary-item bonus (not an office)
The table's own closing paragraph: 10 named artifacts (Excalibur, Arco
del Re degli Elfi, Ascia dei Signori dei Nani, Scimitarra del Dominio
degli Orchi, Corona del Comando dei Draghi, Penna della Grande Aquila,
Corno di Nettuno, Spada Santa, Spada Invisibile, Spada dell'Ombra) each
grant a flat share of a separate 10%-of-total Victory Point pool simply
for being possessed -- "questi punteggi non sono modificati
dall'eventuale differenza di Allineamento con l'Imperatore" (unlike
every one of the 8 offices' own points, per 10.2's own paragraph). This
is structurally different from a Merit Point/Rank contest (no
"highest wins" comparison at all), so it's modeled as its own function,
not folded into any of the 8 office formulas above. **A perfect 1:1
cross-check against this project's own pre-existing `models/treasure.py
TREASURE_NAME`**: all 10 named items already exist there under those
exact English names (`LEADERSHIP_HUMAN` = "Excalibur", `WEAPON_1` =
"Holy Sword", `MONSTER_AID_WHALE` = "Horn of Neptune", ...) --
independent confirmation the rulebook table and the already-transcribed
Pascal `treasure` enum describe the same 10 artifacts.

## The 6 alignment-King titles (Phase 368, reformulated Phase 369)
Phase 368 built these from `CARICHE E ABLITÀ.txt`: tasse + 1-2 `Ability`
skill terms + an alignment-filtered monster-kill tally, one elaborate
formula per title. **The same disassembly that fixed King of Pain above
shows all 7 alignment-King titles (King of Pain included) share one
real, much simpler compiled formula**: `current Tax_Base(King); no
cumulative title record` -- literally Emperor's own formula, restricted
to the King of the matching `Alignment` with the highest current tax
base. No skill terms, no monster-kill term, no tally, for any of the 7
(`AKGEN_embedded_catalogs.json gw_format.royal_title_system` ids 22-27,
29). `_king_of_alignment()` still factors out the one shared eligibility
gate ("Kings only, alignment exactly X" per the JSON's own `eligible`
field for each), and every one of the 6 new functions below is now a
thin wrapper: gate, then `compute_tax_base()`, nothing else. The now-
disproven skill/monster-kill `MeritTally` fields Phase 368 added were
removed in the same correction (see that class's own Phase 369 note).

## Chief of Staff / Office.CHIEF_OF_STAFF (Phase 368, reformulated Phase 369)
Phase 368 built this from `CARICHE E ABLITÀ.txt`: +1 per unit recruited
plus a live per-commanded-unit quality bonus. The disassembly (id 39)
gives a much simpler real formula: `M_Skill(Tactical)+M_Skill(Forced
March)+M_Skill(Naval)+M_Skill(Druidism)` -- "have the highest current
sum of those four modified skills," a plain live skill-level sum, no
recruitment counter and no commanded-unit term at all. `Forced March`
is this project's own `Ability.MARCH` (the "Ma" abbreviation `CTBOTH.
PAS anoun` already established). **Open to a King or a Hero**
(`"eligible": "leader (King or Hero)"`), unchanged from Phase 368.

## Silver Tongue / Office.DIPLOMAT (Phase 368, reformulated Phase 369)
Phase 368 built this from `CARICHE E ABLITÀ.txt`: alliances formed +
alliance upkeep + Druidic skill + Discoveries traded, and made it
King-only per the source's own "(solo per i RE)" title-line marker.
**Both the formula and the eligibility were wrong.** The disassembly
(id 41) gives `Tit_Pts(leader,title)`: a single cumulative diplomatic-
merit counter, no live skill term at all -- "+1, +2 and +5 award sites
in contact/relationship/treaty routines; +1 accompanies establishment
of contact," but the surviving symbol-free code can't prove which of
the two higher values names which real event, so this project keeps it
as one undifferentiated running total (`MeritTally.diplomatic_merit_
points`) rather than inventing named sub-events. **Open to a King or a
Hero** -- the JSON's own `general_assignment.multiple_titles` note is
explicit: "Heroes may hold titles except the seven alignment-King
titles," and Diplomat/id 41 isn't one of those seven.

## The 18 leader-scoped royal titles (Phase 379)
`AKGEN_embedded_catalogs.json.txt gw_format.royal_title_system.entries`
names 23 more Imperial Offices (`models/office.py Office`) this project
had never modeled at all: 2 blank sentinels (`NO_OFFICE`=8, `NO_TITLE`
=51, no formula needed) and 21 real titles. Three of those 21 --
`AIR_FORCE`, `PRAETOR`, `FLAGSHIP` -- are **deliberately not attempted
here**: they're ARMY-scoped, not leader-scoped (`"eligible": "army:
quality Crack or Elite..."`), and their shared `score_formula` term
("current Army_Str(...)") needs the effective-strength calculator
outside an actual battle context; `turn/strength.py
compute_effective_strength()` requires terrain/is_defender/other
battle-only parameters this project has no confirmed value for at rest,
so reproducing "Army_Str" here would mean guessing which subset applies
-- against this project's own standing rule. They also don't fit
`OfficeHolder`'s `leader_id`-only shape at all, a structural gap, not
just a missing formula; left for a future phase that can address both
honestly. The other 18 -- all leader-scoped, all `Tit_Pts(leader,
title)`-shaped cumulative counters or a live skill/holding count -- are
implemented below, each reading one of 16 new `MeritTally` fields
(`models/game_state.py`, Phase 379) or, for `BATTLE_FOOL`/`CURATOR`,
composed from data that already exists:

- **4 magic-school titles** (`ELE_MAGE`/`ILLUS_MAGE`/`NECRO_MAGE`/
  `PSYCHIC_MAGE`, ids 16/21/28/46): `Tit_Pts`, "+1 cumulative point when
  a successful [school]-school spell reaches the compiled title-award
  branch." No writer yet increments these counters (no cast-execution
  call site is touched this phase) -- same "field exists, no populating
  consumer yet" shape as Chancellor's own discovery terms above.
- **6 terrain-King titles** (`PLAINS_KING`/`DESERT_KING`/`JUNGLE_KING`/
  `FOREST_KING`/`MOUNTAIN_KING`/`SEA_KING`, ids 30-35): `Tit_Pts`, "+1
  cumulative point when an Explore result is recorded in [terrain]
  terrain." Also field-only for now.
- **`BATTLE_FOOL`** (id 37, "Fool of Battles"): `-(lgenp+ladmp)` --
  the *negative* of the combined land-and-naval battle-merit total,
  i.e. whoever has the *worst* combined record. Computed directly from
  the same `land_battles_won/lost_points`/`naval_battles_won/lost_
  points` fields `marshal_merit_points()`/`admiral_merit_points()`
  already read -- no new `MeritTally` field needed, and this one's
  fully live today (those fields already have real writers).
- **`CURATOR`** (id 40, "Curator of Artifacts"): `NT_Owned(leader,hla,
  rali)` -- "current count of magic items in the main hla..rali range."
  The exact Treasure-ordinal range bounds aren't named by the
  disassembly; this project approximates it as every held item *except*
  the four categories that clearly aren't "magic items" in the
  rulebook sense (`GOLD_HOARD`, `SENTINEL`, `UNUSED_EXTENSION`,
  `QUEST_ITEM`) -- a documented approximation, not the exact range.
- **`TEACHER`** (id 42, "Professor Whizdumb"): `Tit_Pts`, "+1 cumulative
  point when another character completes an effective Practice/teaching
  interaction with this teacher." Field-only; `turn/practice_
  execution.py execute_practice_group()` is the plausible future writer.
- **`ASSASSIN`** (id 43, "Grandfather of Assassins"): `Tit_Pts`, "+1
  per successful assassination." No Assassinate mechanic exists
  anywhere in this project -- field-only, no plausible writer yet.
- **`DUELLIST`** (id 44, "Captain of the Musketeers"): `Tit_Pts`, "duel
  merit is transferred: the winner gains the duel's own merit value and
  the loser loses the same value." The transferred magnitude is never
  named by the source -- field-only (`duel_merit_net`), no writer.
- **`WINGMAN`** (id 48, "Air Force Commander"): `Tit_Pts`, "cumulative
  air-combat merit: compiled army-result path awards +1 for an air-unit
  victory and -1 for an air-unit defeat; other encounter awards can add
  larger values" -- only the +1/-1 term is confirmed. Field-only
  (`air_combat_merit`) this phase; a future phase could wire the
  confirmed +1/-1 term via `turn/battle_orchestrator.py`.
- **`CRAVENEST`** (id 49, "King of Cowards") / **`BRAVEST`** (id 50,
  "Bravest of the Brave"): both `Tit_Pts`-shaped, both sourced from
  "high-risk personal encounters/challenges" scoring whose exact
  per-event magnitude isn't named -- field-only (`courage_encounter_
  merit`/`bravery_merit`), no writer.

**None of these 18 grant Victory Points** (`models/office.py
OFFICE_VALUE` already reflects this, Phase 81, same as every royal
title before them) and **none is exempted from the death penalty**:
`royal_title_system.death_rule` states plainly "the separate 25% death
reduction documented for lgenp/ladmp/lmhpp is not generalized to
Tit_Pts" -- confirming `MeritTally.apply_death_penalty()` (Phase 377)
is right to leave all `Tit_Pts`-style fields, these 16 included,
untouched on a leader's death. See `models/game_state.py`'s own Phase
379 addendum on `apply_death_penalty()`.

## Tie-break (rulebook footnote 3, extended Phase 377)
"Se due personaggi hanno pari punteggio per una Carica Imperiale, il
primo posto viene assegnato in base prima all'ammontare del tesoro e poi
alla rendita in tasse." Both tie-break figures are Kingdom-scoped (a
leader has no personal treasury or tax base of their own), so
`merit_point_tiebreak_key()` reads `leader.kingdom_id`'s own
`KingdomState.treasury` and `compute_tax_base()`. An independent Hero
(`kingdom_id is None`) has neither -- the rulebook's own "anche un Eroe
può aggiudicarsi una carica" confirms a Hero can win an office outright,
but says nothing about how *that* Hero would be ranked against a tied
rival, so both figures fall back to `0` for one.

**Phase 377**: the rulebook's own footnote only names these first two
tiers, but `AKGEN_embedded_catalogs.json.txt gw_format.imperial_office_
system.tie_breakers_major_offices` (the real disassembly) lists a third
and final one -- lower `leader_id` wins a tie that survives both
treasury and tax base. This also closes the "how would a tied
independent Hero be ranked" gap the rulebook's own text left open: two
kingdom-less Heroes tied on the first two (necessarily `0`/`0`) now
resolve by `leader_id` instead of falling through to undefined `dict`
iteration order.
"""

from __future__ import annotations

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.enums import Ability
from ak_engine.models.game_state import GameState, LeaderState
from ak_engine.models.map import Terrain
from ak_engine.models.treasure import Treasure, TreasureCategory, TREASURE_CATEGORY
from ak_engine.turn.combat import Quality
from ak_engine.turn.discovery_effects import effective_skill_level
from ak_engine.turn.tax_base import compute_tax_base

_CHANCELLOR_SKILL_ABILITIES: tuple[Ability, ...] = (Ability.EXPLORER, Ability.SPY, Ability.SAGE)
_PRIEST_SKILL_ABILITIES: tuple[Ability, ...] = (Ability.DRUID, Ability.WHITE)
_MAGE_SKILL_ABILITIES: tuple[Ability, ...] = (
    Ability.WHITE,
    Ability.NECROMANCY,
    Ability.ELEMENTAL,
    Ability.PSYCHIC,
    Ability.ILLUSION,
)

# Rulebook page 51's own closing paragraph -- see module docstring for the
# 1:1 cross-check against models/treasure.py TREASURE_NAME.
LEGENDARY_ITEM_BONUS_TREASURES: frozenset[Treasure] = frozenset(
    {
        Treasure.LEADERSHIP_HUMAN,  # Excalibur
        Treasure.LEADERSHIP_ELVEN,  # Bow of the Elven Kings
        Treasure.LEADERSHIP_DWARVEN,  # Axe of the Dwarven Lords
        Treasure.LEADERSHIP_ORCISH,  # Scimitar of Orc Mastery
        Treasure.MONSTER_AID_DRAGON,  # Crown of Dragon Command
        Treasure.MONSTER_AID_EAGLE,  # Feather of the Great Eagle
        Treasure.MONSTER_AID_WHALE,  # Horn of Neptune
        Treasure.WEAPON_1,  # Holy Sword
        Treasure.WEAPON_2,  # Shadow Sword
        Treasure.WEAPON_5,  # Invisible Sword
    }
)


def _skill_level_sum(state: GameState, leader: LeaderState, abilities: tuple[Ability, ...]) -> int:
    return sum(effective_skill_level(state, leader, ability) for ability in abilities)


def emperor_merit_points(state: GameState, kingdom_id: int) -> int:
    """"Ammontare della rendita di tasse alla fine del gioco" -- reuses
    Phase 225's `compute_tax_base()` directly.
    """

    return compute_tax_base(state, kingdom_id)


def chancellor_merit_points(state: GameState, leader: LeaderState) -> int:
    """See module docstring: all four terms are live. Discovery
    attribution uses the user-specified 3-for-world-first/2-for-not-
    first scoring (Phase 271), not the rulebook's own flat "+2 per
    Invention found first" figure.
    """

    tally = leader.merit_tally
    return (
        _skill_level_sum(state, leader, _CHANCELLOR_SKILL_ABILITIES)
        + 2 * tally.features_discovered_first
        + 3 * tally.discoveries_found_first
        + 2 * tally.discoveries_found_not_first
        + tally.discoveries_via_espionage
    )


def treasurer_merit_points(state: GameState, kingdom_id: int) -> int:
    """"Il tesoro più sostanzioso alla fine del gioco" -- `KingdomState.treasury`."""

    return state.kingdoms[kingdom_id].treasury


# NUOVE REGOLE E MODIFICHE (Regolamento AK.txt), quoted in full: "Adesso
# per la Carica di Maresciallo conta la qualità delle unità sconfitte
# secondo questa tabella: Reclute 0 punti / Medio 1 punto / Veterani 2
# punti / Crack 3 punti / Elite 4 punti. Una Garrison che attacca ha un
# modificatore di -1 su questa tabella (una Garrison Crack che attacca e
# viene distrutta dà solo 2 punti al generale che l'ha vinta)." See
# module docstring's own Phase 308 addendum for the full reasoning
# (Depleted's own unlisted score, Admiral's extension, the per-unit
# negative-score reading of the Garrison modifier).
MARSHAL_QUALITY_POINTS: dict[Quality, int] = {
    Quality.DEPLETED: 0,
    Quality.GREEN: 0,
    Quality.AVERAGE: 1,
    Quality.VETERAN: 2,
    Quality.CRACK: 3,
    Quality.ELITE: 4,
}
MARSHAL_ATTACKING_GARRISON_MODIFIER = -1


def battle_quality_points(army_type: ArmyType, quality: Quality, *, is_attacker: bool) -> int:
    """One defeated unit's own Marshal/Admiral Merit Point contribution --
    `MARSHAL_QUALITY_POINTS`, minus 1 if this unit was a Garrison on the
    attacking side. The result can go negative (a defeated Green
    attacking Garrison scores -1) -- the rulebook's own worked example
    only tests the Crack case (3 - 1 = 2, still positive), so nothing in
    the source rules out a weaker attacking Garrison's own score going
    below zero; no floor is invented here.
    """

    points = MARSHAL_QUALITY_POINTS[quality]
    if is_attacker and army_type is ArmyType.GARRISON:
        points += MARSHAL_ATTACKING_GARRISON_MODIFIER
    return points


def marshal_merit_points(leader: LeaderState) -> int:
    """Sum of `battle_quality_points()` over each won land battle's
    defeated enemy units, minus the same sum over each lost battle's own
    defeated units -- reads `MeritTally`'s raw won/lost point totals
    (`turn/battle_orchestrator.py _record_battle_merit()` computes them).
    """

    tally = leader.merit_tally
    return tally.land_battles_won_points - tally.land_battles_lost_points


def _rich_sea_province_count(state: GameState, kingdom_id: int | None) -> int:
    if kingdom_id is None:
        return 0
    return sum(
        1
        for province in state.provinces.values()
        if province.owner_kingdom_id == kingdom_id
        and province.effective_terrain() is Terrain.SEA
        and province.tax is not None
        and province.tax >= 2
    )


def admiral_merit_points(state: GameState, leader: LeaderState) -> int:
    """Same won/lost-unit formula as Marshal (naval battles), plus a live
    Naval-skill term and a live "rich sea province" per-kingdom bonus --
    see module docstring for footnote 1's "applies to every character of
    the Kingdom" reading.
    """

    tally = leader.merit_tally
    naval_skill = _skill_level_sum(state, leader, (Ability.NAVAL,))
    rich_sea_provinces = _rich_sea_province_count(state, leader.kingdom_id)
    return tally.naval_battles_won_points - tally.naval_battles_lost_points + naval_skill + rich_sea_provinces


def defender_merit_points(leader: LeaderState) -> int:
    """Full monster HP for a kill, half (floored) for a negotiated
    neutralization -- see module docstring for why `MeritTally` stores
    the raw, unhalved HP sums.
    """

    tally = leader.merit_tally
    return tally.monster_hp_defeated + tally.monster_hp_neutralized // 2


def priest_merit_points(state: GameState, leader: LeaderState) -> int:
    """+1 per successful Resurrection/Bless cast, +2 per level in Druidic
    and White Magic (live).
    """

    tally = leader.merit_tally
    return tally.resurrection_bless_casts + 2 * _skill_level_sum(state, leader, _PRIEST_SKILL_ABILITIES)


def mage_merit_points(state: GameState, leader: LeaderState) -> int:
    """+1 per level across the 5 spell-casting Abilities, +1 per owned
    Spell-Wand-category item -- both terms are fully live.
    """

    skill_sum = _skill_level_sum(state, leader, _MAGE_SKILL_ABILITIES)
    wand_count = sum(
        1
        for item in state.items_held_by(leader.leader_id)
        if TREASURE_CATEGORY.get(item.treasure) is TreasureCategory.SPELL_WAND
    )
    return skill_sum + wand_count


def evilking_merit_points(state: GameState, leader: LeaderState) -> int:
    """King of Pain (Office.EVIL_KING) -- King-only, Evil-alignment-only,
    reformulated Phase 369: plain `Tax_Base(King)`, nothing else. See
    module docstring's Phase 369 addendum.
    """

    return _alignment_king_merit_points(state, leader, Alignment.EVIL)


def thiefprince_merit_points(state: GameState, leader: LeaderState) -> int:
    """Prince of Thieves (Office.THIEF_PRINCE) -- open to a King or a
    Hero, reformulated Phase 369: `+1` per successful theft result.
    `successful_thefts` currently always reads 0 (no writer yet).
    """

    return leader.merit_tally.successful_thefts


def _king_of_alignment(state: GameState, leader: LeaderState, alignment: Alignment) -> bool:
    """The shared eligibility gate for all 7 alignment-King titles
    (King of Pain included) -- the acting King of a Kingdom whose own
    `Alignment` matches exactly. See module docstring's Phase 369
    addendum.
    """

    if not leader.is_king or leader.kingdom_id is None:
        return False
    return state.kingdoms[leader.kingdom_id].alignment is alignment


def _alignment_king_merit_points(state: GameState, leader: LeaderState, alignment: Alignment) -> int:
    """The one real formula shared by all 7 alignment-King titles: plain
    `Tax_Base(King)`, gated to the King of the matching `Alignment`. See
    module docstring's Phase 369 addendum.
    """

    if not _king_of_alignment(state, leader, alignment):
        return 0
    return compute_tax_base(state, leader.kingdom_id)


def divinearchangel_merit_points(state: GameState, leader: LeaderState) -> int:
    """Office.DIVINE_KING -- Divine-alignment Kings only. See module
    docstring's Phase 369 addendum.
    """

    return _alignment_king_merit_points(state, leader, Alignment.DIVINE)


def goodking_merit_points(state: GameState, leader: LeaderState) -> int:
    """Office.GOOD_KING (Most Blessed of Kings) -- Good-alignment Kings
    only. See module docstring's Phase 369 addendum.
    """

    return _alignment_king_merit_points(state, leader, Alignment.GOOD)


def druidking_merit_points(state: GameState, leader: LeaderState) -> int:
    """Office.DRUID_KING (Great Druid of Life) -- Druid-alignment Kings
    only. See module docstring's Phase 369 addendum.
    """

    return _alignment_king_merit_points(state, leader, Alignment.DRUID)


def neutralking_merit_points(state: GameState, leader: LeaderState) -> int:
    """Office.NEUTRAL_KING (Defender of Freedom) -- Neutral-alignment
    Kings only. See module docstring's Phase 369 addendum.
    """

    return _alignment_king_merit_points(state, leader, Alignment.NEUTRAL)


def paganking_merit_points(state: GameState, leader: LeaderState) -> int:
    """Office.PAGAN_KING (Warlock of the Pagan Gods) -- Pagan-alignment
    Kings only. See module docstring's Phase 369 addendum.
    """

    return _alignment_king_merit_points(state, leader, Alignment.PAGAN)


def undeadking_merit_points(state: GameState, leader: LeaderState) -> int:
    """Office.UNDEAD_KING (Angel of Death) -- Undead-alignment Kings
    only. See module docstring's Phase 369 addendum.
    """

    return _alignment_king_merit_points(state, leader, Alignment.UNDEAD)


def chiefofstaff_merit_points(state: GameState, leader: LeaderState) -> int:
    """Office.CHIEF_OF_STAFF -- open to a King or a Hero, reformulated
    Phase 369: `M_Skill(Tactical)+M_Skill(Forced March)+M_Skill(Naval)+
    M_Skill(Druidism)`, a plain live skill-level sum. See module
    docstring's Phase 369 addendum.
    """

    return _skill_level_sum(state, leader, (Ability.TACTICAL, Ability.MARCH, Ability.NAVAL, Ability.DRUID))


def silvertongue_merit_points(state: GameState, leader: LeaderState) -> float:
    """Office.DIPLOMAT (Silver Tongue) -- open to a King or a Hero,
    reformulated Phase 369: a single cumulative diplomatic-merit
    counter, no live skill term, no King-only gate. See module
    docstring's Phase 369 addendum.
    """

    return leader.merit_tally.diplomatic_merit_points


# Phase 379: the 4 magic-school title categories that clearly aren't
# "magic items" in Curator's own rulebook sense -- see module docstring.
_CURATOR_EXCLUDED_CATEGORIES: frozenset[TreasureCategory] = frozenset(
    {
        TreasureCategory.GOLD_HOARD,
        TreasureCategory.SENTINEL,
        TreasureCategory.UNUSED_EXTENSION,
        TreasureCategory.QUEST_ITEM,
    }
)


def elementalmage_merit_points(leader: LeaderState) -> int:
    """Master of Elements (Office.ELE_MAGE, id 16) -- see module
    docstring's Phase 379 addendum: field-only, no writer yet.
    """

    return leader.merit_tally.elemental_spell_casts


def illusionistmage_merit_points(leader: LeaderState) -> int:
    """Amazing Houdini (Office.ILLUS_MAGE, id 21) -- field-only."""

    return leader.merit_tally.illusionist_spell_casts


def necromancermage_merit_points(leader: LeaderState) -> int:
    """Sorceror of Black Magic (Office.NECRO_MAGE, id 28) -- field-only."""

    return leader.merit_tally.necromancy_spell_casts


def psychicmage_merit_points(leader: LeaderState) -> int:
    """Master Mind (Office.PSYCHIC_MAGE, id 46) -- field-only."""

    return leader.merit_tally.psychic_spell_casts


def plainsking_merit_points(leader: LeaderState) -> int:
    """Ranger of the Plains (Office.PLAINS_KING, id 30) -- field-only."""

    return leader.merit_tally.plains_explorations


def desertking_merit_points(leader: LeaderState) -> int:
    """Desert Rat (Office.DESERT_KING, id 31) -- field-only."""

    return leader.merit_tally.desert_explorations


def jungleking_merit_points(leader: LeaderState) -> int:
    """Lord of the Jungle (Office.JUNGLE_KING, id 32) -- field-only."""

    return leader.merit_tally.jungle_explorations


def forestking_merit_points(leader: LeaderState) -> int:
    """Warden of the Forests (Office.FOREST_KING, id 33) -- field-only."""

    return leader.merit_tally.forest_explorations


def mountainking_merit_points(leader: LeaderState) -> int:
    """Mountain Man (Office.MOUNTAIN_KING, id 34) -- field-only."""

    return leader.merit_tally.mountain_explorations


def seaking_merit_points(leader: LeaderState) -> int:
    """Ruler of the Waves (Office.SEA_KING, id 35) -- field-only."""

    return leader.merit_tally.sea_explorations


def battlefool_merit_points(leader: LeaderState) -> int:
    """Fool of Battles (Office.BATTLE_FOOL, id 37) -- the negative of the
    combined land-and-naval battle-merit total (`-(lgenp+ladmp)`,
    "worst combined cumulative land and naval battle merit"). Fully
    live: reuses the same `MeritTally` fields `marshal_merit_points()`/
    `admiral_merit_points()` already read.
    """

    tally = leader.merit_tally
    land = tally.land_battles_won_points - tally.land_battles_lost_points
    naval = tally.naval_battles_won_points - tally.naval_battles_lost_points
    return -(land + naval)


def curator_merit_points(state: GameState, leader: LeaderState) -> int:
    """Curator of Artifacts (Office.CURATOR, id 40) -- current count of
    held items outside the 4 clearly-non-magic-item categories. See
    module docstring's Phase 379 addendum for why this is a documented
    approximation of the source's own unconfirmed `hla..rali` range.
    """

    return sum(
        1
        for item in state.items_held_by(leader.leader_id)
        if TREASURE_CATEGORY.get(item.treasure) not in _CURATOR_EXCLUDED_CATEGORIES
    )


def teacher_merit_points(leader: LeaderState) -> int:
    """Professor Whizdumb (Office.TEACHER, id 42) -- field-only."""

    return leader.merit_tally.teaching_interactions


def assassin_merit_points(leader: LeaderState) -> int:
    """Grandfather of Assassins (Office.ASSASSIN, id 43) -- field-only,
    no Assassinate mechanic exists in this project yet.
    """

    return leader.merit_tally.successful_assassinations


def duellist_merit_points(leader: LeaderState) -> int:
    """Captain of the Musketeers (Office.DUELLIST, id 44) -- field-only,
    the transferred duel-merit magnitude is unconfirmed by the source.
    """

    return leader.merit_tally.duel_merit_net


def wingman_merit_points(leader: LeaderState) -> int:
    """Air Force Commander (Office.WINGMAN, id 48) -- field-only."""

    return leader.merit_tally.air_combat_merit


def cravenest_merit_points(leader: LeaderState) -> int:
    """King of Cowards (Office.CRAVENEST, id 49) -- field-only."""

    return leader.merit_tally.courage_encounter_merit


def bravest_merit_points(leader: LeaderState) -> int:
    """Bravest of the Brave (Office.BRAVEST, id 50) -- field-only."""

    return leader.merit_tally.bravery_merit


def legendary_item_victory_point_bonus_count(state: GameState, leader_id: int) -> int:
    """How many of the 10 rulebook-named legendary items (see module
    docstring) this leader currently holds -- **not** an Office Merit
    Point tally; the rulebook explicitly separates this flat, un-ranked
    Victory Point share from the 8-office Rank contest above.
    """

    return sum(1 for item in state.items_held_by(leader_id) if item.treasure in LEGENDARY_ITEM_BONUS_TREASURES)


def merit_point_tiebreak_key(state: GameState, leader: LeaderState) -> tuple[int, int, int]:
    """Rulebook footnote 3's own tie-break, as a sort key (higher wins):
    treasury first, then tax base -- both read from `leader.kingdom_id`'s
    own `KingdomState`, `0` for both when `leader.kingdom_id is None`
    (a kingdom-less independent Hero has neither).

    **Phase 377 addendum -- a real third tier, closing the independent-
    Hero gap this function's own pre-Phase-377 docstring flagged.**
    `AKGEN_embedded_catalogs.json.txt`'s own `gw_format.imperial_office_
    system.tie_breakers_major_offices` (a real static disassembly of
    `AKGEN.EXE`/`AK.EXE`/`AK.OVR`) lists a third, final tier past treasury
    and tax base: "lower character id" -- confirming the rulebook's own
    footnote 3 (which only names the first two) doesn't fully resolve a
    tie on its own. Encoded as `-leader.leader_id` so this stays a plain
    "higher tuple wins" sort key throughout: a lower `leader_id` produces
    a higher (less negative) third element. This also means two tied,
    kingdom-less independent Heroes -- previously an unresolved `(0, 0)`
    tie decided only by incidental `dict` iteration order -- now resolve
    deterministically by `leader_id`, same as any other tie.
    """

    if leader.kingdom_id is None:
        return (0, 0, -leader.leader_id)
    kingdom = state.kingdoms[leader.kingdom_id]
    return (kingdom.treasury, compute_tax_base(state, leader.kingdom_id), -leader.leader_id)
