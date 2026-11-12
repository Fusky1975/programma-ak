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

**Phase 467 cross-check against `AKGEN_reverse_engineering_report
(2).md` SS14.2's own compact disassembly table** (the same globals Phase
137 found unrecoverable, now named alongside a one-line-each formula):
every term below was, at the time, either an exact match or a fully
consistent translation -- `lfdisc`/`ldiscp` were still bare global names
then, with no further disassembly detail in SS14.2, so this cross-check
found no confirmed discrepancy for Chancellor specifically. **That
assumption didn't survive Phase 795** (see below) --
- Emperor: `Tax_Base(Re)` -- exact match (`compute_tax_base()`).
- Chancellor: `Spy + Sage + Explorer + 2*lfdisc + ldiscp` -- the skill
  term and `lfdisc` ("+2 per Feature discovered first") still match
  exactly. `ldiscp` no longer merely "consistent" with a guess -- `turn/
  practice_execution.py`'s own Phase 795 addendum (`Desktop/DISCVAL.md`
  SS4.2/15.2-15.3) gives it a concrete formula, `2*discoveries_found_
  first + discoveries_via_espionage`, confirming a real discrepancy with
  this module's former Phase 271 user-specified 3/2/1-point scoring
  (3, not 2, points per world-first discovery; a nonzero 2 points, not 0,
  for a non-first one) -- corrected below, Phase 1189, user-confirmed.
- Treasurer: `lgold` -- exact match (`KingdomState.treasury`).
- Marshal: `lgenp` (bare global, no further SS14.2 detail) -- consistent
  with the Phase 308 quality-weighted battle table below (the accumulator
  that table increments).
- Admiral: `ladmp + Naval + seatax`, `seatax` = sea provinces with tax >
  1 -- the Naval-skill and sea-province terms match exactly (`tax > 1`
  and this module's own `tax >= 2` are the same integer threshold);
  `ladmp` (bare global) is consistent with the same Phase 308 battle
  table, Admiral's own side of it.
- Defender: `lmhpp` (bare global, no further SS14.2 detail) -- consistent
  with the monster-HP-defeated/neutralized terms below.
- Priest: `lwmsp + 2*(Druid + White)` -- the `2*(Druid+White)` term
  matches exactly; `lwmsp` (bare global) is consistent with this module's
  own Resurrection/Bless-cast counter.
- Mage: "numero di oggetti-incantesimo `wcp..pic`" + "somma delle cinque
  skill magiche" -- both terms match exactly (`SPELL_WAND` treasure count
  + the 5-magic-skill sum below).

## Emperor (20%)
"Ammontare della rendita di tasse alla fine del gioco" -- the kingdom's
tax revenue at game end. This is exactly `turn/tax_base.py
compute_tax_base()` (Phase 225), reused directly rather than
reimplemented.

## Gran Cancelliere / Chancellor (10%)
- +1 per level in Explorer, Spy, and Sage
- +2 per Special Place (Feature) discovered first
- Invention (Discovery) attribution, **Phase 1189 correction, user-
  confirmed**: **2 points to the world's first hero/King ever to
  discover a given Discovery, 0 to every later, independent discoverer
  of that same Discovery** -- the real compiled `ldiscp` accumulator
  (`turn/practice_execution.py`'s own Phase 795 addendum,
  `2*discoveries_found_first + discoveries_via_espionage`), which
  supersedes this module's own former Phase 271 user-specified 3/2/1
  scoring (itself a deliberate override of the rulebook's flat "+2 per
  Invention found first" figure, made before `ldiscp`'s own formula was
  pinned down). `discoveries_found_not_first` is still tracked on
  `MeritTally` for other consumers; it no longer earns Chancellor merit.
- +1 per Invention obtained via espionage

**All four terms are now live.** `features_discovered_first` is live
as of **Phase 256**: `models/feature.py Feature.discovered_by_kingdom`
(a per-kingdom dict, Phase 75) already exists and is written by
`turn/exploration.py discover_features()` every time a kingdom first
discovers a Special Place; `turn/plan_dispatch.py`'s own
`ActionCode.EXPLORE` branch checks, for each newly-discovered feature,
whether that kingdom's own entry is still the *only* one in the dict
(nobody else got there first) and credits the acting leader's own
`MeritTally.features_discovered_first` when so. **Phase 748** (`Desktop/
FDISCKNGFN.md`) extends the identical check to `turn/search_execution.py
_register_search_target_known()` -- the real compiled helper both
Explore's and Search's own discovery paths call credits this merit the
same way, not just Explore's.

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

## Silver Tongue / Office.DIPLOMAT (Phase 368, reformulated Phase 369, wired Phase 445)
Phase 368 built this from `CARICHE E ABLITÀ.txt`: alliances formed +
alliance upkeep + Druidic skill + Discoveries traded, and made it
King-only per the source's own "(solo per i RE)" title-line marker.
**Both the formula and the eligibility were wrong.** The disassembly
(id 41) gives `Tit_Pts(leader,title)`: a single cumulative diplomatic-
merit counter, no live skill term at all -- "+1, +2 and +5 award sites
in contact/relationship/treaty routines; +1 accompanies establishment
of contact," but at the time the surviving symbol-free code couldn't
prove which of the two higher values named which real event, so this
project kept it as one undifferentiated running total (`MeritTally.
diplomatic_merit_points`) rather than inventing named sub-events.
**Open to a King or a Hero** -- the JSON's own `general_assignment.
multiple_titles` note is explicit: "Heroes may hold titles except the
seven alignment-King titles," and Diplomat/id 41 isn't one of those
seven.

**Phase 445 resolves the ambiguity fully**: `AKGEN_reverse_engineering_
report (2).md` SS18.3 names the exact three sites and their real
per-partner deltas -- `+1` for an Allied-or-better relation, `+2` more
for territorial adjacency, `+5` per Discovery actually transferred via
Scientific Treaty -- verified exactly against a real 10-Kingdom GW
corpus transition. `turn/diplomatic_merit.py apply_diplomatic_merit()`
now writes the field per-turn; see `silvertongue_merit_points()`'s own
docstring below for the writer.

## The 18 leader-scoped royal titles (Phase 379)
`AKGEN_embedded_catalogs.json.txt gw_format.royal_title_system.entries`
names 23 more Imperial Offices (`models/office.py Office`) this project
had never modeled at all: 2 blank sentinels (`NO_OFFICE`=8, `NO_TITLE`
=51, no formula needed) and 21 real titles. Three of those 21 --
`AIR_FORCE`, `PRAETOR`, `FLAGSHIP` -- are ARMY-scoped, not leader-scoped
(`"eligible": "army: quality Crack or Elite..."`), and don't fit
`OfficeHolder`'s `leader_id`-only shape at all -- **this Phase 379 note
originally left them for a future phase**, since their shared `score_
formula` term ("current Army_Str(...)") needs the effective-strength
calculator outside an actual battle context, and `turn/strength.py
compute_effective_strength()` requires terrain/is_defender/other
battle-only parameters with no confirmed at-rest value. **Phase 394
resolves this in full** (`turn/office_holder.py ArmyOfficeHolder`,
`resolve_army_office_holder()`, `ARMY_RANKED_OFFICES`) via a dedicated,
parallel structure rather than forcing these three into `OfficeHolder`'s
own `leader_id`-only shape -- `turn/army_quality.py army_peacetime_
strength()` answers the "which battle-only parameters have a coherent
at-rest value" question this note raised, and Victory Point awarding
plus the sticky tie-break both followed in Phase 633. The other 18 --
all leader-scoped, all `Tit_Pts(leader, title)`-shaped cumulative
counters or a live skill/holding count -- are implemented below, each
reading one of 16 new `MeritTally` fields (`models/game_state.py`,
Phase 379) or, for `BATTLE_FOOL`/`CURATOR`, composed from data that
already exists:

- **4 magic-school titles** (`ELE_MAGE`/`ILLUS_MAGE`/`NECRO_MAGE`/
  `PSYCHIC_MAGE`, ids 16/21/28/46): `Tit_Pts`, "+1 cumulative point when
  a successful [school]-school spell reaches the compiled title-award
  branch." **Live as of Phase 630**, credited by `turn/cast_execution.py
  execute_cast()` via `_award_royal_title_spell_merit()` at the same
  `result.applied` choke point `_award_cast_experience()` already uses
  for XP -- deliberately *without* that function's own separate "skill
  0 excluded" gate, since this counter's own sourced text names no such
  exclusion.
- **6 terrain-King titles** (`PLAINS_KING`/`DESERT_KING`/`JUNGLE_KING`/
  `FOREST_KING`/`MOUNTAIN_KING`/`SEA_KING`, ids 30-35): `Tit_Pts`, "+1
  cumulative point when an Explore result is recorded in [terrain]
  terrain." **Live as of Phase 630**, credited by `turn/move_
  execution.py record_kingdom_exploration()`'s new `leader_id`
  parameter, applied unconditionally (partial or full Explore alike)
  at all 4 real call sites. Neither this nor the 4 magic-school titles
  above have their own `"effect_while_held"` bonus (auto-Flee, double-
  speed terrain exploration, etc.) wired -- deliberately deferred, the
  same "merit counter first, effect later" precedent Assassin's own
  still-unwired Guild free-attempt perk shows below. ~~Duellist below~~
  is no longer a fitting example of that precedent: Phase 471 wired its
  own real `"effect_while_held"` bonus too (`models/office.py
  GANG_TEMPLATE[Office.DUELLIST]`'s fanatic-unit battlefield effect,
  `turn/battle_orchestrator.py fight_battle()`), so Duellist now has
  both halves live, not just the merit tally this bullet's own sibling
  entry below describes.
- **`BATTLE_FOOL`** (id 37, "Fool of Battles"): `-(lgenp+ladmp)` --
  the *negative* of the combined land-and-naval battle-merit total,
  i.e. whoever has the *worst* combined record. Computed directly from
  the same `land_battles_won/lost_points`/`naval_battles_won/lost_
  points` fields `marshal_merit_points()`/`admiral_merit_points()`
  already read -- no new `MeritTally` field needed, and this one's
  fully live today (those fields already have real writers).
- **`CURATOR`** (id 40, "Curator of Artifacts"): `NT_Owned(leader,hla,
  rali)` -- "current count of magic items in the main hla..rali range."
  **Exactly sourced as of Phase 503**: `hla`=0, `rali`=66 (`Gioco/HostAK/
  TP/CTBOTH.PAS`'s own `treasure` enum declaration, cross-validated
  against this project's own pre-existing, independently-ordinal-aligned
  `models/treasure.py _CATEGORY_RANGES` -- `GOLD_HOARD_LARGE = 67`
  matches the enum's own `LargeTr` at ordinal 67 exactly), i.e. every
  category up through `SKILL_BOOK` and none past it -- `GOLD_HOARD`,
  `QUEST_ITEM`, `SENTINEL`, `NAMED_UNIQUE`, `UNUSED_EXTENSION` excluded.
- **`TEACHER`** (id 42, "Professor Whizdumb"): `Tit_Pts` -- **live as of
  Phase 446**, credited by `turn/practice_execution.py execute_practice_
  group()` via `_select_teacher()`: `+1` per real natural skill level a
  co-practicing student actually gains, to the selected teacher (current
  officeholder preferred among qualified candidates, else the
  highest-skill one) -- `AKGEN_reverse_engineering_report (2).md`
  SS20.1-2.
- **`ASSASSIN`** (id 43, "Grandfather of Assassins"): `Tit_Pts` --
  **live as of Phase 447**, credited by `turn/cast_execution.py
  _execute_kill_enemy()`: `+1` to the caster only at the real lethal
  branch (success roll passed, not neutralized by Hidden Tattoos) --
  the "Spy Assassination" ability and the title's own Guild free-attempt
  perk have no reachable merit credit of their own
  (`AKGEN_reverse_engineering_report (2).md` SS20.5-10).
- **`DUELLIST`** (id 44, "Captain of the Musketeers"): `Tit_Pts` -- **live
  as of Phase 443**, credited by `turn/challenge_execution.py
  _apply_duel_encounter_merit()` at the personal CHALLENGE encounter's
  own close point: winner +stake/loser -stake, stake 2 for a decisive
  combat or 1 for an ordinary refusal (`AKGEN_reverse_engineering_report
  (2).md` SS17). Its own separate `"effect_while_held"` battlefield bonus
  (§17.7's fanatic-unit assist) is live too, as of **Phase 471** --
  `models/office.py GANG_TEMPLATE[Office.DUELLIST]`, `turn/battle_
  orchestrator.py fight_battle()` -- the merit tally above and this
  bonus are two independently-wired halves of the same title.
- **`WINGMAN`** (id 48, "Air Force Commander"): `Tit_Pts` -- **live as of
  Phase 444**, credited by `turn/battle_orchestrator.py _apply_wingman_
  merit()`: +1 to the leader commanding a winning Dragons/Eagles unit in
  a resolved battle column, -1 to the leader commanding a losing one
  (Vampires excluded, `AKGEN_reverse_engineering_report (2).md` SS19).
- **`CRAVENEST`** (id 49, "King of Cowards") / **`BRAVEST`** (id 50,
  "Bravest of the Brave"): both `Tit_Pts`-shaped -- **live as of Phase
  443**, credited by the same `_apply_duel_encounter_merit()` call as
  Duellist. Cravenest is loser-only (`-1`, no winner credit -- the real
  dispatcher deliberately skips that branch, making the title's own
  positive `minpts=5` threshold structurally unreachable). Bravest
  credits only the CHALLENGE's own protagonist (the challenger) on a
  decisive win, equal to their own un-recovered hit points
  (`AKGEN_reverse_engineering_report (2).md` SS18).

**Phase 468 -- the three titles' own real gameplay *effects* (report
SS18.4/18.6/18.8), previously only the merit-accumulation half above**:
Silver Tongue's Talk-vs-monster guarantee ("un mostro non reagisce
violentemente... e onora sempre un accordo completato") is now live in
`turn/encounter.py resolve_talk_reaction()`/`resolve_fulfill_honored()`
(both gain a `caster_is_silver_tongue` flag), wired from `turn/search_
execution.py`'s own Talk/Fulfill resolvers via `resolve_office_holder(
state, Office.DIPLOMAT)`. King of Cowards' own real per-turn temperament
rise ("ne migliorerebbe il temperamento di un livello a ogni turno, fino
a Berserk") is now `turn/office_holder.py apply_cravenest_temperament_
escalation()`, called once per turn from `turn_processor.run_turn()` --
expected to be a permanent no-op given the structural-unreachability bug
two paragraphs above, modeled anyway since the effect itself is real.
**Bravest of the Brave's own effect ("quando parla a un Hero, il
temperamento di quel Hero sale di un livello") is wired** (Phase 469):
`turn/challenge_execution.py _apply_bravest_talk_inspiration()`, gated
on the `Office.BRAVEST` holder issuing a `Maneuver.TALK` tactic against
a Hero target.

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
    """See module docstring: all three terms are live. Discovery
    attribution formula corrected (Phase 1189, user-confirmed) to the
    real compiled ``ldiscp`` accumulator -- ``turn/practice_execution.py``
    own Phase 795 addendum gives it as ``2*discoveries_found_first +
    discoveries_via_espionage`` -- superseding this module's own former
    Phase 271 user-specified 3-for-world-first/2-for-not-first scoring,
    which Phase 467's cross-check had assumed (with no detail yet
    available for `ldiscp` at the time) was consistent with this real
    formula but wasn't: no points at all for a non-first personal
    discovery, and 2 (not 3) points for a world-first one.
    ``discoveries_found_not_first`` is still tracked on ``MeritTally``
    (other consumers, e.g. the webapp's own stats display, still read
    it) -- it just no longer feeds this merit formula.
    """

    tally = leader.merit_tally
    return (
        _skill_level_sum(state, leader, _CHANCELLOR_SKILL_ABILITIES)
        + 2 * tally.features_discovered_first
        + 2 * tally.discoveries_found_first
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
    `successful_thefts` is **live as of Phase 442**, credited at both of
    this project's own real Steal-success sites: `turn/challenge_
    execution.py _apply_successful_theft()` (character-vs-character
    Steal, Phase 305) and `turn/search_execution.py _resolve_steal()`
    (Steal against a guarded feature's hoard, Phase 132/239) -- the two
    places in this port that mirror the real compiled formula's own "two
    separate success paths that award the point."
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

    Credited by `turn/diplomatic_merit.py apply_diplomatic_merit()` --
    `+1` per allied Kingdom, `+2` more if adjacent, `+5` per Discovery
    actually transferred via Scientific Treaty (`AKGEN_reverse_
    engineering_report (2).md` SS18.3). Only the receiving Kingdom's own
    King is credited (the field is leader-keyed, not Kingdom-keyed); a
    Kingless Kingdom receives nothing that turn.

    **Phase 869 correction**: the applier function itself dates to Phase
    445, but this docstring's own earlier "Live as of Phase 445... called
    once per turn" claim was never actually true -- `apply_diplomatic_
    merit()` had no caller anywhere in the project until Phase 869 wired
    it (alongside `turn/scientific_treaty.py execute_scientific_
    treaties()`) into `turn_processor.py run_turn()`. Every game
    processed before Phase 869 credited zero Silver Tongue merit,
    regardless of alliance/Treat-order data.
    """

    return leader.merit_tally.diplomatic_merit_points


# Phase 503: the real Pascal source (Desktop's Gioco/HostAK/TP/CTBOTH.PAS,
# `type treasure = (hla,lkdf,ali,...,rali,LargeTr,HugeTr,FabTr,...)`) confirms
# the exact `hla..rali` range Curator's own `NT_Owned(leader,hla,rali)` call
# (REPORTS.PAS `Curator: pts:= NT_Owned(ldran,hla,rali,t);`) counts: ordinals
# 0-66, i.e. every category up through `SKILL_BOOK` and nothing past it.
# `models/treasure.py`'s own `_CATEGORY_RANGES` was already independently
# ordinal-aligned with this same enum (`GOLD_HOARD_LARGE = 67` matches
# `LargeTr` at ordinal 67 exactly), so the exact set is simply every
# category *after* `SKILL_BOOK` -- this project's own Phase 379 approximation
# excluded 4 of those 5 categories but missed `NAMED_UNIQUE` (93-98), which
# Phase 379 didn't isolate as its own category yet at the time.
_CURATOR_EXCLUDED_CATEGORIES: frozenset[TreasureCategory] = frozenset(
    {
        TreasureCategory.GOLD_HOARD,
        TreasureCategory.QUEST_ITEM,
        TreasureCategory.SENTINEL,
        TreasureCategory.NAMED_UNIQUE,
        TreasureCategory.UNUSED_EXTENSION,
    }
)


def elementalmage_merit_points(leader: LeaderState) -> int:
    """Master of Elements (Office.ELE_MAGE, id 16) -- **live as of Phase
    630**, credited by `turn/cast_execution.py execute_cast()` via
    `_award_royal_title_spell_merit()`: +1 per successful Elemental-
    school spell cast by this leader.
    """

    return leader.merit_tally.elemental_spell_casts


def illusionistmage_merit_points(leader: LeaderState) -> int:
    """Amazing Houdini (Office.ILLUS_MAGE, id 21) -- **live as of Phase
    630**, same `_award_royal_title_spell_merit()` writer as the other
    3 magic-school titles, keyed on `Ability.ILLUSION`.
    """

    return leader.merit_tally.illusionist_spell_casts


def necromancermage_merit_points(leader: LeaderState) -> int:
    """Sorceror of Black Magic (Office.NECRO_MAGE, id 28) -- **live as
    of Phase 630**; also credited by an Undead caster's own Charm
    (`turn/cast_execution.py _spell_ability()`'s Phase 183 override).
    """

    return leader.merit_tally.necromancy_spell_casts


def psychicmage_merit_points(leader: LeaderState) -> int:
    """Master Mind (Office.PSYCHIC_MAGE, id 46) -- **live as of Phase
    630**, same `_award_royal_title_spell_merit()` writer.
    """

    return leader.merit_tally.psychic_spell_casts


def plainsking_merit_points(leader: LeaderState) -> int:
    """Ranger of the Plains (Office.PLAINS_KING, id 30) -- **live as of
    Phase 630**, credited by `turn/move_execution.py record_kingdom_
    exploration()`: +1 per Explore result recorded in Plains terrain by
    this leader (any of the 4 real call sites -- Move's own partial
    exploration, a dedicated Explore order, or the multi-attacker LMOVE
    branch).
    """

    return leader.merit_tally.plains_explorations


def desertking_merit_points(leader: LeaderState) -> int:
    """Desert Rat (Office.DESERT_KING, id 31) -- **live as of Phase
    630**, same `record_kingdom_exploration()` writer, Desert terrain.
    """

    return leader.merit_tally.desert_explorations


def jungleking_merit_points(leader: LeaderState) -> int:
    """Lord of the Jungle (Office.JUNGLE_KING, id 32) -- **live as of
    Phase 630**, same `record_kingdom_exploration()` writer, Jungle
    terrain.
    """

    return leader.merit_tally.jungle_explorations


def forestking_merit_points(leader: LeaderState) -> int:
    """Warden of the Forests (Office.FOREST_KING, id 33) -- **live as
    of Phase 630**, same `record_kingdom_exploration()` writer, Forest
    terrain.
    """

    return leader.merit_tally.forest_explorations


def mountainking_merit_points(leader: LeaderState) -> int:
    """Mountain Man (Office.MOUNTAIN_KING, id 34) -- **live as of Phase
    630**, same `record_kingdom_exploration()` writer, Mountain terrain.
    """

    return leader.merit_tally.mountain_explorations


def seaking_merit_points(leader: LeaderState) -> int:
    """Ruler of the Waves (Office.SEA_KING, id 35) -- **live as of Phase
    630**, same `record_kingdom_exploration()` writer, Sea terrain.
    """

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
    """Professor Whizdumb (Office.TEACHER, id 42) -- **live as of Phase
    446**. Credited by `turn/practice_execution.py execute_practice_
    group()`, via `_select_teacher()`: `+1` to the selected teacher per
    real natural skill level a co-practicing student actually gains
    (never for an aptitude-only rise, never when all co-practicers are
    tied), preferring the current Teacher officeholder among qualified
    candidates (`AKGEN_reverse_engineering_report (2).md` SS20.1-2).
    """

    return leader.merit_tally.teaching_interactions


def assassin_merit_points(leader: LeaderState) -> int:
    """Grandfather of Assassins (Office.ASSASSIN, id 43) -- **live as of
    Phase 447**. Credited by `turn/cast_execution.py _execute_kill_
    enemy()`: `+1` to the caster only when Kill Enemy (Necromancy)
    actually kills its target -- not on spell failure (the Berserk
    counterattack is a different combat), not when Hidden Tattoos
    neutralizes the kill into disease instead. The separate Spy
    Assassination ability and the title's own Guild free-attempt perk
    have no reachable merit credit of their own -- Kill Enemy is the
    real, only reachable path (`AKGEN_reverse_engineering_report (2).md`
    SS20.5-10).
    """

    return leader.merit_tally.successful_assassinations


def duellist_merit_points(leader: LeaderState) -> int:
    """Captain of the Musketeers (Office.DUELLIST, id 44) -- **live as of
    Phase 443**. Credited by ``turn/challenge_execution.py
    _apply_duel_encounter_merit()`` at the personal CHALLENGE encounter's
    own close point: the winner gains and the loser loses a stake of 2
    for a decisive combat or 1 for an ordinary refused/avoided challenge
    -- see that function's own docstring for the full sourced formula
    (``AKGEN_reverse_engineering_report (2).md`` SS17).
    """

    return leader.merit_tally.duel_merit_net


def wingman_merit_points(leader: LeaderState) -> int:
    """Air Force Commander (Office.WINGMAN, id 48) -- **live as of Phase
    444**. Credited by `turn/battle_orchestrator.py _apply_wingman_
    merit()`, called from `fight_battle()`: +1 to the leader commanding
    a winning Dragons/Eagles unit in a resolved column contest, -1 to
    the leader commanding a losing one (Vampires excluded, matching the
    real `Air_Unit(army, false)` predicate's own literal flag) --
    `AKGEN_reverse_engineering_report (2).md` SS19.
    """

    return leader.merit_tally.air_combat_merit


def cravenest_merit_points(leader: LeaderState) -> int:
    """King of Cowards (Office.CRAVENEST, id 49) -- **live as of Phase
    443**. Credited by the same ``turn/challenge_execution.py
    _apply_duel_encounter_merit()`` call as Duellist: the *loser* of
    every ordinary personal-encounter result (refusal or decisive
    combat) is docked ``-1``; the real compiled dispatcher deliberately
    skips the winner's own branch for this title. That asymmetry makes
    this title structurally unreachable in the real build -- a
    negative-only accumulator can never cross the positive ``minpts=5``
    threshold (``AKGEN_reverse_engineering_report (2).md`` SS18.5-18.6) --
    and this port replicates that faithfully rather than "fixing" it.
    """

    return leader.merit_tally.courage_encounter_merit


def bravest_merit_points(leader: LeaderState) -> int:
    """Bravest of the Brave (Office.BRAVEST, id 50) -- **live as of Phase
    443**. Credited by the same ``turn/challenge_execution.py
    _apply_duel_encounter_merit()`` call, but only to the CHALLENGE's own
    protagonist (the challenger) when they win a decisive combat: the
    gain is however many of their own starting hit points they never got
    back (``CHARACTER_HIT_POINTS - challenger_combatant.hit_points``) --
    zero for an unscathed win, never credited on a loss, refusal, draw,
    or magical escape. Not a transfer -- the loser (or the target, if
    they were the one who won) never loses Bravest points
    (``AKGEN_reverse_engineering_report (2).md`` SS18.7).
    """

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
