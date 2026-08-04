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
negotiated half, `monster_hp_neutralized`, still has no writer -- it
needs the Fulfill/Talk-Say mechanic `turn/search_execution.py`'s own
docstring already flags as unwired.

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

## King of Pain / Office.EVIL_KING (Phase 277)
User-supplied reference text (`CARICHE E ABLITÀ.txt`, 2026-07-30, the
"cariche base" the user described as the same standing as the rulebook
page-51 table above), King of Pain's own "Come si ottiene" paragraph:
"Questo titolo lo possono ottenere solo i RE Evil. Si ottiene un punto
per ogni punto di tasse del Reame. In più si ottiene un punto per ogni
punto di magia NE del RE. In più si ottiene un punto per ogni punto di
TH del RE. Si ottiene un punto per ogni mostro che si uccide in una
provincia del reame. E si ottiene un punto per ogni volta che la
tattica TH ha successo (si ruba un tesoro a un mostro o un eroe di un
reame in cui si è in guerra)." **King-only, and Evil-alignment-only**
("Questo titolo lo possono ottenere solo i RE Evil") -- `evilking_
merit_points()` returns 0 outright for any leader who isn't the acting
King of an Evil-aligned Kingdom, the same "gate ineligible leaders to
0" idiom `_leader_merit_points()`'s own `Office.TREASURER` branch
already uses for a kingdomless leader, so this office's own eligibility
rule needs no special-casing in `office_holder.py`'s generic Rank-
contest loop. `monsters_killed_in_realm_province`/`successful_thief_
tactics` (`MeritTally`, Phase 277) have no writer yet -- see that
class's own Phase 277 note.

## Prince of Thieves / Office.THIEF_PRINCE (Phase 277)
Same user-supplied source: "Si ottiene un punto per ogni punto di TH
che possiede il RE o l'eroe. Si ottiene un punto per ogni pezzo d'oro
rubato a un mostro o un eroe o un RE. Si ottengono 5 punti per ogni
oggetto magico rubato a un mostro, un eroe o un RE." Open to a King
*or* a Hero (no alignment/office restriction stated, unlike King of
Pain) -- `thiefprince_merit_points()` needs no eligibility gate at all,
every leader can accumulate these points. `gold_stolen`/`magic_items_
stolen` (`MeritTally`, Phase 277) have no writer yet -- see that
class's own Phase 277 note.

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

## The 6 alignment-King titles (Phase 368)
Same user-supplied source (`CARICHE E ABLITÀ.txt`), the "cariche minori"
section shared with King of Pain/Prince of Thieves and the 11
`turn/race_titles.py` race titles -- these don't grant Victory Points
either, and each is **King-only, and gated to one specific `Alignment`**
("Questo titolo lo possono ottenere solo i RE Divini/Good/Druid/Neutral/
Pagan/Undead"), so every formula function below returns 0 outright for
a Hero or a King of the wrong Kingdom alignment, the exact same idiom
`evilking_merit_points()` already established. `_king_of_alignment()`
factors that one shared gate check out of all 6, since the point terms
themselves differ per title (different `Ability` pair, different
monster-kill filter) but the eligibility shape is identical.

Every one of the 6 shares "+1 per punto di tasse del Reame" (`compute_
tax_base()`, same as Emperor/King of Pain) plus two `Ability` skill-level
terms, plus one monster-kill-in-realm-province term with a per-title
alignment filter:

- **Divine Archangel** (`Office.DIVINE_KING`): White Magic (Wh) skill +
  kills of Anti-Holy monsters (`MeritTally.monsters_killed_anti_holy_
  in_realm_province`) -- only one skill term, not two, unlike the other
  5 (the source's own text names only "magia WH", no second ability).
- **Most Blessed of Kings** (`Office.GOOD_KING`): White Magic (Wh) +
  Sage (Sa) skill, kills of Anti-Holy-or-Evil monsters.
- **Great Druid of Life** (`Office.DRUID_KING`): Psychic (Ps) + Druidic
  (Dr) skill, kills of Anti-Holy-or-Evil monsters (**same field** as
  Most Blessed of Kings -- the source gives both titles the identical
  "anti-holy o Evil" filter verbatim).
- **Defender of Freedom** (`Office.NEUTRAL_KING`): Illusion (Il) +
  Melee (Me) skill, kills of *any* monster in a realm province -- reuses
  `MeritTally.monsters_killed_in_realm_province` as-is (the source's own
  wording here, "per ogni mostro che si uccide in una provincia del
  reame", is identical to King of Pain's own unfiltered term).
- **Warlock of the Pagan Gods** (`Office.PAGAN_KING`): Elemental (El) +
  Explorer (Ex) skill, same unfiltered monster-kill term as Defender of
  Freedom.
- **Angel of Death** (`Office.UNDEAD_KING`): Necromancy (Ne) skill only,
  kills of Good-or-Druid-or-Neutral monsters (`monsters_killed_good_
  druid_neutral_in_realm_province`), plus +1 per successful Charm (CH)
  cast that transforms a Hero into Undead (`ch_undead_transformations`)
  -- no writer for either counter yet, same as every other tally term
  this phase adds.

## Chief of Staff / Office.CHIEF_OF_STAFF (Phase 368)
"ogni unità militare reclutata vale 1 punto" (`MeritTally.military_
units_recruited`, cumulative, no writer yet) "+ ogni unità militare
comandata dà 0,25 punti" (**live**, a flat per-currently-commanded-unit
count via `GameState.armies`, the same "live, not tallied" shape `turn/
race_titles.py _crack_plus_units_commanded()` already established for
an analogous "unit(s) currently commanded" term) "+ per ogni unità
militare veteran/crack/elite o più si ottengono 0,10/0,20/0,30 punti"
(`CHIEF_OF_STAFF_QUALITY_BONUS`, an additional live per-unit bonus on
top of the flat 0.25, keyed by the commanded unit's own `Quality` --
Green/Average/Depleted score no bonus, since the source names only
Veteran/Crack/Elite explicitly; "Elite o più" reads as `Quality.ELITE`,
this project's own top modeled tier, since Super-Elite has no
precise rule of its own -- see `turn/combat.py Quality`'s own
docstring). **Open to a King or a Hero**, no eligibility gate stated,
the same as Prince of Thieves.

## Silver Tongue / Office.DIPLOMAT (Phase 368)
"per ogni comando Treat riuscito ... si ottiene 1 punto" (`MeritTally.
alliances_formed`) "+ ogni turno, per ogni alleanza mantenuta fino a
termine del turno stesso si ottiene 0,5 punti" (`alliance_upkeep_
points`, meant to accumulate +0.5 per still-active alliance at each
turn's own end -- a running total, not a live per-turn recount, since
this project has no standing Alliance/Treat model yet to recount
against) "+ ogni livello di DR si ottiene 1 punto" (**live**, Druidic
skill level) "+ per ogni discovery scambiata si ottiene 1 punto"
(`discoveries_traded`). **King-only** -- the title line's own "(solo
per i RE)" marker, unlike the un-marked Chief of Staff title line right
above it in the same source; no alignment restriction is stated for
Silver Tongue, unlike the 6 titles above. None of the four tally fields
has a writer yet -- this project has no Treat/alliance or Discovery-
trade execution mechanic at all.

## Tie-break (rulebook footnote 3)
"Se due personaggi hanno pari punteggio per una Carica Imperiale, il
primo posto viene assegnato in base prima all'ammontare del tesoro e poi
alla rendita in tasse." Both tie-break figures are Kingdom-scoped (a
leader has no personal treasury or tax base of their own), so
`merit_point_tiebreak_key()` reads `leader.kingdom_id`'s own
`KingdomState.treasury` and `compute_tax_base()`. An independent Hero
(`kingdom_id is None`) has neither -- the rulebook's own "anche un Eroe
può aggiudicarsi una carica" confirms a Hero can win an office outright,
but says nothing about how *that* Hero would be ranked against a tied
rival, so this falls back to `(0, 0)`, a documented gap rather than a
guess.
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
    """See module docstring: King-only, Evil-alignment-only -- 0 for any
    other leader. `monsters_killed_in_realm_province`/`successful_thief_
    tactics` currently always read 0 (no writer yet).
    """

    if not leader.is_king or leader.kingdom_id is None:
        return 0
    kingdom = state.kingdoms[leader.kingdom_id]
    if kingdom.alignment is not Alignment.EVIL:
        return 0

    tally = leader.merit_tally
    return (
        compute_tax_base(state, leader.kingdom_id)
        + _skill_level_sum(state, leader, (Ability.NECROMANCY,))
        + _skill_level_sum(state, leader, (Ability.THIEF,))
        + tally.monsters_killed_in_realm_province
        + tally.successful_thief_tactics
    )


def thiefprince_merit_points(state: GameState, leader: LeaderState) -> int:
    """See module docstring: open to a King or a Hero, no eligibility
    gate. `gold_stolen`/`magic_items_stolen` currently always read 0
    (no writer yet).
    """

    tally = leader.merit_tally
    return (
        _skill_level_sum(state, leader, (Ability.THIEF,))
        + tally.gold_stolen
        + 5 * tally.magic_items_stolen
    )


def _king_of_alignment(state: GameState, leader: LeaderState, alignment: Alignment) -> bool:
    """See module docstring's Phase 368 addendum: the shared eligibility
    gate for all 6 alignment-King titles -- the acting King of a Kingdom
    whose own `Alignment` matches exactly.
    """

    if not leader.is_king or leader.kingdom_id is None:
        return False
    return state.kingdoms[leader.kingdom_id].alignment is alignment


def divinearchangel_merit_points(state: GameState, leader: LeaderState) -> int:
    """Office.DIVINE_KING -- Divine-alignment Kings only. See module
    docstring's Phase 368 addendum.
    """

    if not _king_of_alignment(state, leader, Alignment.DIVINE):
        return 0
    tally = leader.merit_tally
    return (
        compute_tax_base(state, leader.kingdom_id)
        + _skill_level_sum(state, leader, (Ability.WHITE,))
        + tally.monsters_killed_anti_holy_in_realm_province
    )


def goodking_merit_points(state: GameState, leader: LeaderState) -> int:
    """Office.GOOD_KING (Most Blessed of Kings) -- Good-alignment Kings
    only. See module docstring's Phase 368 addendum.
    """

    if not _king_of_alignment(state, leader, Alignment.GOOD):
        return 0
    tally = leader.merit_tally
    return (
        compute_tax_base(state, leader.kingdom_id)
        + _skill_level_sum(state, leader, (Ability.WHITE, Ability.SAGE))
        + tally.monsters_killed_anti_holy_or_evil_in_realm_province
    )


def druidking_merit_points(state: GameState, leader: LeaderState) -> int:
    """Office.DRUID_KING (Great Druid of Life) -- Druid-alignment Kings
    only. Shares `monsters_killed_anti_holy_or_evil_in_realm_province`
    with Most Blessed of Kings -- see module docstring's Phase 368
    addendum.
    """

    if not _king_of_alignment(state, leader, Alignment.DRUID):
        return 0
    tally = leader.merit_tally
    return (
        compute_tax_base(state, leader.kingdom_id)
        + _skill_level_sum(state, leader, (Ability.PSYCHIC, Ability.DRUID))
        + tally.monsters_killed_anti_holy_or_evil_in_realm_province
    )


def neutralking_merit_points(state: GameState, leader: LeaderState) -> int:
    """Office.NEUTRAL_KING (Defender of Freedom) -- Neutral-alignment
    Kings only. Reuses `monsters_killed_in_realm_province` as-is -- see
    module docstring's Phase 368 addendum.
    """

    if not _king_of_alignment(state, leader, Alignment.NEUTRAL):
        return 0
    tally = leader.merit_tally
    return (
        compute_tax_base(state, leader.kingdom_id)
        + _skill_level_sum(state, leader, (Ability.ILLUSION, Ability.MELEE))
        + tally.monsters_killed_in_realm_province
    )


def paganking_merit_points(state: GameState, leader: LeaderState) -> int:
    """Office.PAGAN_KING (Warlock of the Pagan Gods) -- Pagan-alignment
    Kings only. See module docstring's Phase 368 addendum.
    """

    if not _king_of_alignment(state, leader, Alignment.PAGAN):
        return 0
    tally = leader.merit_tally
    return (
        compute_tax_base(state, leader.kingdom_id)
        + _skill_level_sum(state, leader, (Ability.ELEMENTAL, Ability.EXPLORER))
        + tally.monsters_killed_in_realm_province
    )


def undeadking_merit_points(state: GameState, leader: LeaderState) -> int:
    """Office.UNDEAD_KING (Angel of Death) -- Undead-alignment Kings
    only. See module docstring's Phase 368 addendum.
    """

    if not _king_of_alignment(state, leader, Alignment.UNDEAD):
        return 0
    tally = leader.merit_tally
    return (
        compute_tax_base(state, leader.kingdom_id)
        + _skill_level_sum(state, leader, (Ability.NECROMANCY,))
        + tally.monsters_killed_good_druid_neutral_in_realm_province
        + tally.ch_undead_transformations
    )


# "Per ogni unità militare veteran/crack/elite o più si ottengono
# 0,10/0,20/0,30 punti" -- an additional live bonus on top of Chief of
# Staff's own flat 0.25-per-commanded-unit term. See module docstring's
# Phase 368 addendum for why Green/Average/Depleted score no bonus and
# "Elite o più" reads as Quality.ELITE.
CHIEF_OF_STAFF_QUALITY_BONUS: dict[Quality, float] = {
    Quality.DEPLETED: 0.0,
    Quality.GREEN: 0.0,
    Quality.AVERAGE: 0.0,
    Quality.VETERAN: 0.10,
    Quality.CRACK: 0.20,
    Quality.ELITE: 0.30,
}


def chiefofstaff_merit_points(state: GameState, leader: LeaderState) -> float:
    """Office.CHIEF_OF_STAFF -- open to a King or a Hero, no eligibility
    gate. See module docstring's Phase 368 addendum.
    """

    tally = leader.merit_tally
    commanded = [army for army in state.armies.values() if army.commanded_by == leader.leader_id]
    return (
        tally.military_units_recruited
        + 0.25 * len(commanded)
        + sum(CHIEF_OF_STAFF_QUALITY_BONUS[army.quality] for army in commanded)
    )


def silvertongue_merit_points(state: GameState, leader: LeaderState) -> float:
    """Office.DIPLOMAT (Silver Tongue) -- King-only, no alignment
    restriction. See module docstring's Phase 368 addendum.
    """

    if not leader.is_king or leader.kingdom_id is None:
        return 0
    tally = leader.merit_tally
    return (
        tally.alliances_formed
        + tally.alliance_upkeep_points
        + _skill_level_sum(state, leader, (Ability.DRUID,))
        + tally.discoveries_traded
    )


def legendary_item_victory_point_bonus_count(state: GameState, leader_id: int) -> int:
    """How many of the 10 rulebook-named legendary items (see module
    docstring) this leader currently holds -- **not** an Office Merit
    Point tally; the rulebook explicitly separates this flat, un-ranked
    Victory Point share from the 8-office Rank contest above.
    """

    return sum(1 for item in state.items_held_by(leader_id) if item.treasure in LEGENDARY_ITEM_BONUS_TREASURES)


def merit_point_tiebreak_key(state: GameState, leader: LeaderState) -> tuple[int, int]:
    """Rulebook footnote 3's own tie-break, as a sort key (higher wins):
    treasury first, then tax base -- both read from `leader.kingdom_id`'s
    own `KingdomState`. `(0, 0)` for a kingdom-less independent Hero, a
    documented gap (see module docstring), not a guess.
    """

    if leader.kingdom_id is None:
        return (0, 0)
    kingdom = state.kingdoms[leader.kingdom_id]
    return (kingdom.treasury, compute_tax_base(state, leader.kingdom_id))
