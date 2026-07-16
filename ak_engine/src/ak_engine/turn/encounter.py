"""Personal combat resolution core (rulebook [5.0]-[5.3], [5.9]) -- Phase 48.

Encounters (Search vs. a feature's monster, Challenge/Pursue between
characters, or a battle's own Duel) all bottom out in the same personal
combat system: "two combatants alternately attack each other in combat
rounds, inflicting damage points with each attack, until one combatant
is killed because the damage points he sustains equals or exceeds his
hit points" ([5.0]). This module builds *only* that core -- the
two best-sourced tactics, Melee and Fire Arrow -- as a first, narrow
slice, the same incremental approach this project already used for the
army-battle system (Phase 5's combat primitives, built up over several
more phases before Phase 9 wired a full `fight_battle()`). **Not yet
wired into Search/Challenge/Pursue/Duel** -- those still resolve
combat the way they always have (Duel via `estimate_win_probability`
approximation; Search/Challenge/Pursue decode-only) until a later phase
connects them.

**[5.0] core resolved here**:
- "In combat, all characters have 10 hit points." (`CHARACTER_HIT_POINTS`)
- "The character with the greater skill level relevant to the tactic he
  is using generally goes first in the combat round... If the skill is
  the same, the characters go in random order." (`_acts_first`)
- "Neutral Kingdoms are aided by an Order of Duelists. All Neutral
  characters... fight with a +1 modifier to their Melee and Archery
  abilities." (`Combatant.neutral_duelist_bonus`)

**[5.3] Melee**: "You can enter melee even if you have no skill in melee
combat... A character has a base chance to hit of 50%, and does 1-6
damage points per swing." -- flat 50%, **not** skill-scaled (unlike Fire
Arrow); the Melee `Ability` level still matters for initiative ordering
per [5.0]'s generic rule, just not for the hit chance itself.

**[5.2] Fire Arrow**: "You can have a number of free attacks equal to
the level of archery skill... The base chance to hit is 30%, plus 10%
per Archery level, and the damage is 1-6 hit points." Each combatant
gets exactly that many attacks this module's own duel resolver, then
stops (see "Explicitly out of scope" below for what real combat would
do next).

**Phase 132 addendum -- monster-specific melee damage.** Wiring this
core into Search (rulebook [3.3], guardian-monster combat) needs a
*monster* combatant, not just a character one. The rulebook's own
Monster Table (quoted above) gives each species its own melee damage
die -- Giant `1-7`, Elasmosaurus `1-7`, vs. the character-only `1-6`
from [5.3] -- so a monster combatant can't just reuse
`MELEE_DAMAGE_RANGE` unmodified without silently flattening real,
sourced per-species data. `Combatant.melee_damage_range` (default
`MELEE_DAMAGE_RANGE`, so every existing character-vs-character caller
-- Duel, Challenge, Pursue -- is unaffected) lets `turn/
search_execution.py` populate a monster's own die from `models/monster
.py MONSTER_STATS`. The hit-chance formula itself (flat 50%) stays the
single sourced rule from [5.3], applied symmetrically to both
combatants -- no monster-specific hit-chance alternative exists in any
available source, so inventing one would be exactly the kind of guess
this project avoids; reusing the only sourced formula, for both sides,
is the documented, narrower choice.

**Explicitly out of scope this phase** (each is a real, sourced
rulebook mechanic, just not attempted yet):
- **Steal, Negotiate/Talk/Say/Fulfill, Flee, Scout, Give** ([5.4]-[5.8])
  -- every tactic except Melee and Fire Arrow.
- **Casting spells / using magic items in combat** ([5.1]) -- no
  spell-effect or magic-item system exists anywhere in this project.
- **Mixed-tactic range transitions**: real combat starts at Spell range
  and both combatants' *different* preferred tactics can force closing
  through Bow range to Melee range, each closing move consuming a round
  for whoever orders it. This module's two duel resolvers each assume
  *both* combatants use the *same* tactic for the whole encounter (a
  Melee duel or a Fire Arrow duel), sidestepping the range-transition
  state machine entirely -- a documented scope-narrowing choice, not a
  claim that mixed tactics don't matter.
- **"About double" free attacks when both combatants have Archery
  skill** ([5.2]): "if two characters with archery skill fight each
  other, they will both get about double their usual number of free
  attacks. However, there is some random chance involved" -- no
  concrete formula given ("about double", "some random chance"). **Not
  a real gap** (confirmed by the user, project author, who supplied the
  original rulebook design directly): only a single Fire Arrow (``FI``)
  order can appear in an Encounter Plan at all, so this "if two
  characters with archery skill fight each other" doubling clause never
  actually applies to how a single ``FI`` tactic itself resolves --
  `resolve_fire_arrow_duel` correctly uses each combatant's own,
  undoubled `archery_skill` free-attack count regardless of the other
  combatant's own skill, exactly as it already does.
- **What happens after Fire Arrow's free attacks run out with nobody
  dead** ([5.2]) -- **confirmed, not a gap** (same user clarification):
  "Si puo dare un solo ordine di FI durante un piano speciale di
  incontro. Una volta usato, si esauriscono le frecce e i combattenti
  passano alla fase successiva che dipende dall'elenco di ordini messi
  nel piano d'incontro, che quindi puo essere un CA (cast a spell)
  oppure ME oppure FL." ("Only one FI order can be given in a Special
  Encounter Plan. Once used, the arrows run out and combatants move to
  the next phase, determined by the tactic list in the Encounter Plan,
  which can then be CA/Cast, ME/Melee, or FL/Flee.") `resolve_fire_arrow
  _duel`'s own `winner=None` (both survived, shots exhausted) is exactly
  the signal `turn/search_execution.py`'s own Phase 170 tactic-walk
  already reads as "fall through to the plan's next tactic" -- this
  module's own scope stays deliberately narrower (a single-tactic duel
  primitive; see the "mixed-tactic range transitions" bullet above for
  why), with the actual plan-level fall-through correctly living one
  layer up, in the caller.
- **Temper's effect on Melee** ("A character's Temper affects melee
  according to the Temper Table"): this project has no `Temper` model
  anywhere (no enum, no per-leader field) -- an entirely separate,
  unstarted piece of character data, not merely an unwired mechanic.
- **Victory and Death's aftermath** ([5.9]): looting a vanquished foe's
  treasure, magic items changing hands, and (for a slain King) his
  eldest son taking over with *player-chosen* starting ability levels --
  the last of these needs interactive player choice this automated
  engine has no channel for at all, not just missing game-state logic.

**Phase 170 addendum -- monster-specific missile damage, mirroring Phase
132's melee precedent.** Wiring Fire Arrow into Search (see ``turn/
search_execution.py``'s own Phase 170 addendum) needs a monster's own
missile damage die too -- the Monster Table gives species-specific
values (Giant `1-7`, Archer `3-9`, etc.) via ``models/monster.py
MonsterCombatStats.missile_damage``, distinct from the character-only
``FIRE_ARROW_DAMAGE_RANGE`` (`1-6`) from [5.2]. `Combatant
.missile_damage_range` (default `FIRE_ARROW_DAMAGE_RANGE`, so every
existing character-vs-character caller is unaffected) lets a monster
combatant supply its own die; `roll_fire_arrow_attack` and
`resolve_fire_arrow_duel` now read each attacker's own field instead of
the module-level constant, the same pattern `roll_melee_attack`/
`resolve_melee_duel` already established.

**Phase 155 addendum -- Troll regeneration, project-original.**
`Desktop/MOSTRI con statistiche.txt` (Phase 154's own combat-stats
source, confirmed by the user to be their own compilation) footnote
``(*)`` reads, quoted in full (translated from the user's own Italian):
"The Troll regenerates 1 hit point every combat round. The combat
message reads: 'Horror! The Troll is regenerating its wounds.' A
FIREBALL spell completely negates the regeneration ability."
`Combatant.regenerates_hp` (default `0`, so every existing caller is
unaffected) models the mechanical half: both `resolve_melee_duel()` and
`resolve_fire_arrow_duel()` add it to a surviving combatant's hit points
at the end of each round they're still alive, uncapped (the rule gives
no maximum, and this project doesn't model a combatant's own "starting"
hit points as a value distinct from its current one to cap against
-- reading the literal text rather than inventing a ceiling). `turn/
search_execution.py` sets it for a Troll's own monster combatant.

**Deliberately not wired, a real but currently unreachable exception**:
the FIREBALL-negates-regeneration clause. Applying it needs to know
whether a FIREBALL was cast as part of the same Search encounter's own
Encounter Plan -- but a Cast tactic's own spell id is, per this
project's own confirmed gap (`turn/search_decode.py`'s own docstring),
still just an unresolved raw int with no decoded `Spell` anywhere in a
`SearchTactic`. Wiring the exception is blocked on that gap, not
attempted here as a guess.

**Phase 179 addendum -- the three combat ranges, and spell disruption.**
Confirmed directly by the user (project author), quoting the rulebook
in full: "Ci sono tre distanze nel combattimento: portata d'incantesimo,
portata d'arco e zona di mischia. La prima e' la distanza maggiore e
consente solo l'uso di incantesimi o attacchi con armi da lancio. In
zona di mischia solo incantesimi o attacchi corpo a corpo (quest'ultimi
avranno comunque sempre la precedenza). Gli Incontri solitamente
iniziano a portata di incantesimo. In combattimento tutti gli Eroi hanno
10 Punti Ferita." ("There are three ranges in combat: spell range, bow
range, and melee zone. The first is the greatest distance and allows
only the use of spells or thrown-weapon attacks. In the melee zone,
only spells or hand-to-hand attacks [the latter always take
precedence]. Encounters usually begin at spell range. In combat, all
Heroes have 10 hit points.") `CombatRange` below models the three-tier
vocabulary this confirms, ordered farthest-to-closest -- matching both
the confirmed default starting range and a real worked example's own
progression ("Marzials loped along steadily and closed to bow range" /
"Marzials charged into melee range", each its own narrated beat).

The user also confirmed the exact formula for a second real mechanic
glimpsed in that same worked example ("Marzials's spell was disrupted
by the event" / "His spell was disrupted by the event"), quoted in
full: "questo succede quando si subiscono dei danni prima di provare a
lanciare un incantesimo. Ogni danno da' il 20% comulativo (95%
massimo) di non riuscire a lanciare l'incantesimo perdendo il round di
combattimento." ("This happens when you take damage before attempting
to cast a spell. Each hit taken gives a cumulative 20% chance [95%
maximum] of failing to cast the spell, losing that combat round.")
`spell_disruption_chance()`/`resolve_spell_disruption()` model this
formula directly, counting *hits landed*, not damage points -- "ogni
danno" reads as "every hit", matching the worked example, where
Ablamor's own cast attempt was disrupted immediately after taking
exactly one landed hit (Marzials's own 8-point Melee attack) earlier
that same round.

**Deliberately not wired any further this phase, by the user's own
explicit direction** ("progetta e implementa, poi nelle prossime
sessioni ti illustrero' gli incantesimi" -- "design and implement,
then in future sessions I'll walk you through the spells"): neither
`CombatRange` nor the disruption roll is threaded into `turn/
search_execution.py`'s own tactic walk yet. Wiring a real `CAST` tactic
still needs to know what each of the 10 "Personal-Combat-only" spells
actually *does* when it lands (`turn/cast_execution.py`'s own docstring
already names this exact gap) -- disruption only ever matters as a
precondition to a cast that, today, still has no effect to disrupt.
Both are modeled now as clean, independently-testable primitives ready
for that future phase, the same "confirmed mechanic modeled before its
consuming pipeline exists" pattern `models/monster.py roll_monster_
alignment()` (Phase 176) and `models/monster_encounter_plan.py roll_
monster_encounter_plan()` (Phase 178) already established.

**Phase 180 addendum -- Holy Symbol [HO], the first Personal-Combat
spell effect, project-original (user-supplied, project author).**
Quoted in full: "Holy Symbol [HO] (Incantesimo di Combattimento
Individuale): il Simbolo Sacro serve ad invocare la protezione divina
e riduce le probabilita' dell'avversario di colpire nel tiro con
l'arco e nel corpo a corpo del 10% per livello di abilita'. Ad esempio,
se un giocatore che e' al livello 1 combatte contro un avversario che
ha la probabilita' base di colpire pari al 50%, la ridurra' del 5% (il
10% del 50% equivale al 5%). Se usato contro un personaggio o un
mostro Non-Morto, come un vampiro o un fantasma, oppure contro un
mostro anti-holy come un demone, questo incantesimo riduce la
probabilita' di colpire del 20% per livello di abilita' e infligge 1-4
punti ferita di danno per livello di abilita'." ("Holy Symbol invokes
divine protection, reducing the opponent's own chance to hit -- both
Fire Arrow and Melee -- by 10% of that base chance per caster skill
level [worked example: level 1 against a 50% base chance reduces it by
5%, since 10% of 50% is 5%]. Against an Undead character or monster
[e.g. a vampire or ghost] or an Anti-Holy monster [e.g. a demon], the
reduction is 20% per level instead, and the spell also inflicts 1-4
damage points per skill level.")

`holy_symbol_hit_chance()` applies the reduction as a multiplier on the
opponent's own base hit chance (`base_hit_chance * (1 - rate *
skill_level)`, matching the worked example exactly), floored at 0% --
an engineering safeguard against a level high enough to reduce the
chance below zero, not a guessed game-balance rule. `roll_holy_symbol_
undead_damage()` rolls the Undead/Anti-Holy bonus damage as one
independent 1-4 die per skill level, summed -- **confirmed directly by
the user** (asked directly, since "1-4 per level" is genuinely
ambiguous between several real conventions): level 2 rolls two separate
1-4 dice and adds them (range 2-8), not a single roll scaled or
multiplied by level.

**Who counts as "Undead or Anti-Holy" is left to the caller**, not
computed inside these functions: `models/alignment.py Alignment.
ANTI_HOLY` already covers exactly this category in this project's own
data (`models/monster.py MONSTER_ALIGNMENT_DISTRIBUTION` -- every
species the source names as an example, Ghost/Vampire/Banshee/Mummy/
Lich/Spectre and every demon, Balrog/Marilith/Succubus/Rakshasha/Ice_
Devil/Bone_Devil/Imp, is a 100%-`ANTI_HOLY` species there), so a future
wiring phase can pass `target.alignment is Alignment.ANTI_HOLY`
directly -- these pure functions just take a `target_is_undead_or_
anti_holy: bool` flag rather than reaching into `GameState` themselves.

**Not wired into `turn/search_execution.py`'s combat resolution this
phase either**, for the same reason as Phase 179's own primitives: this
is the first of an unknown-sized set of Personal-Combat spells the user
is walking through "nelle prossime sessioni" (across future sessions) --
wiring a real `CAST`-tactic combat engine before more of that set is
known would mean redesigning it repeatedly as each new spell arrives.

**Phase 181 addendum -- Holy Symbol's talent + the level-4 cap on every
Personal-Combat spell.** Quoted in full: "E' un incantesimo legato al
talento magia bianca (WH). Comunque questo incantesimo, come tutti
quelli di combattimento ha il CAP al livello 4. Quindi se ha il talento
WH a 5 questo incantesimo -- come tutti -- ha gli stessi effetti del
livello 4." ("It's a spell tied to the White Magic talent [WH].
However, this spell, like all combat spells, is capped at level 4. So
if a character has WH at 5, this spell -- like all of them -- has the
same effects as level 4.") Two confirmed facts: (1) Holy Symbol's own
`skill_level` parameter is meant to be fed from `Ability.WHITE`
(`models/enums.py`), not a generic ability; (2) **every** individual
Personal-Combat spell effect -- not just Holy Symbol -- caps its own
skill-level scaling at level 4, per the new `PERSONAL_COMBAT_SPELL_
LEVEL_CAP` constant. `holy_symbol_hit_chance()` and `roll_holy_symbol_
undead_damage()` both clamp their own `skill_level` input to this cap
internally before using it, so a WH-5 (or higher) caster gets exactly
the WH-4 result. Future Personal-Combat spells arriving in later
sessions should apply this same cap, per the user's own "come tutti"
("like all of them") wording.

**Phase 182 addendum -- Spiritwrack [SP], the second White Magic (WH)
Personal-Combat spell effect, project-original (user-supplied).**
Quoted in full: "Spiritwrack [SP] (Incantesimo di Combattimento
Individuale): chi lancia l'incantesimo pronuncia parole sacre che
provocano nell'avversario violenti spasimi che lo indeboliscono nello
spirito e nel corpo. La vittima non puo' lanciare incantesimi ne'
tirare con l'arco e il danno che procura nel corpo a corpo e' ridotto
di 1/2 punto danno per livello di abilita' di chi lancia l'incantesimo,
arrotondato casualmente per eccesso o per difetto. Questo incantesimo
e' inefficace contro mostri Non-Morti (questi sono: Spectre, Ghost,
Vampire, Mummy, Banshee, Lich) o meccanici (che non hanno anima,
questi sono: Golem, Gargoyle) e i suoi effetti sono dimezzati contro
mostri di intelligenza animale." ("Spiritwrack: the caster speaks
sacred words that provoke violent spasms in the opponent, weakening
them in spirit and body. The victim cannot cast spells nor shoot with
a bow, and the Melee damage they deal is reduced by 1/2 point per the
caster's own skill level, randomly rounded up or down. This spell is
ineffective against Undead monsters [Spectre/Ghost/Vampire/Mummy/
Banshee/Lich] or mechanical ones [no soul: Golem/Gargoyle], and its
effects are halved against Animal-Intelligence monsters" -- the full
12-species list is quoted in `models/monster.py`'s own Phase 182
addendum, alongside the new `SPIRITWRACK_UNDEAD_MONSTERS`/
`SPIRITWRACK_MECHANICAL_MONSTERS`/`SPIRITWRACK_ANIMAL_INTELLIGENCE_
MONSTERS` reference sets that back the `target_is_immune`/`target_is_
animal_intelligence` flags below).

Same WH talent link and level-4 cap as Holy Symbol (Phase 181):
`spiritwrack_melee_damage_reduction()`'s own `skill_level` is capped at
`PERSONAL_COMBAT_SPELL_LEVEL_CAP` internally, same as Holy Symbol.

**The random-rounding formula**: `1/2 point per level` isn't always a
whole number (level 1 = 0.5, level 3 = 1.5), so the exact reduction is
rounded up or down at random, weighted by the fractional part -- e.g.
level 1's own 0.5 rounds up to 1 exactly half the time and down to 0
the other half; level 2's own exact 1.0 has no fractional part at all
and always resolves to 1 without consuming a roll (the same no-roll-
when-the-outcome-is-fixed convention this module's own `resolve_spell_
disruption()` and `roll_holy_symbol_undead_damage()` already
established).

**The "halved effects against Animal-Intelligence" ambiguity, resolved
directly with the user via `AskUserQuestion`**: Spiritwrack's other
effect -- blocking spellcasting and archery -- is a binary yes/no, not
a number, so "halved" can't apply to it literally. Three readings were
offered; the user picked the recommended one: **only the numeric Melee
damage reduction is halved against Animal-Intelligence targets; the
spellcasting/archery block still applies at full strength** (in
practice mostly moot, since none of the twelve Animal-Intelligence
species listed actually cast spells or shoot bows anyway).
`spiritwrack_melee_damage_reduction()`'s own `target_is_animal_
intelligence` flag only affects its own numeric formula;
`spiritwrack_blocks_cast_and_archery()` doesn't take that flag at all,
by design -- only `target_is_immune` (Undead or Mechanical) suppresses
it.

**Not wired into `turn/search_execution.py`'s combat resolution this
phase either**, for the same reason as Holy Symbol (Phase 180): more
Personal-Combat spells are still to come across future sessions.

**Phase 183 addendum -- Charm [CH]'s Personal-Combat effect, tied to
Ability.PSYCHIC (PS), project-original (user-supplied).** Charm is the
first spell confirmed to have *both* an Action-Cast form (`turn/
cast_execution.py _execute_charm`, Phase 29/183) and a Personal-Combat
form -- unlike every spell already covered in this module's own
addenda, which are Personal-Combat-*only*. Quoted in full: "Charm [CH]
(Incantesimo d'Azione o di Combattimento Individuale): ... Altrimenti
consente a chi lancia l'incantesimo di ingraziarsi il suo avversario e
sfuggire incolume al combattimento. ... Praticamente se usato in
combattimento equivale a un comando FL che riesce sempre con la
dicitura: (eroe o mostro) incanta (eroe o mostro) e questo lo lascia
andare via senza problemi." ("Charm [CH] (Action or Personal-Combat
spell): ... Otherwise it lets the caster ingratiate himself with his
opponent and escape unharmed from combat. ... In practice, used in
combat it's equivalent to an FL [Flee] command that always succeeds,
with the narration: (hero or monster) charms (hero or monster) and
this lets them leave without trouble.")

`CHARM_FLEE_ALWAYS_SUCCEEDS = True` is the entire mechanic: unlike a
normal Flee attempt (`turn/search_execution.py FLEE_CHANCE`, keyed by
`MonsterSpeed` and never guaranteed), a Charm-as-Flee always succeeds,
no roll consumed. There is no skill-level-scaled numeric magnitude
here at all -- `PERSONAL_COMBAT_SPELL_LEVEL_CAP` (Phase 181) doesn't
apply to Charm's combat effect, unlike Holy Symbol/Spiritwrack.

**Not wired into `turn/search_execution.py`'s combat resolution this
phase either**, same reason as every other Personal-Combat spell above
-- and the narration itself ("(eroe o mostro) incanta...") belongs in
`report/turn_report.py` alongside `render_flee_failure()` when a real
CAST-tactic engine exists to call it, not in this module (which never
renders prose).

**Two further confirmed Charm facts, both about the Action-Cast form,
documented in `turn/cast_execution.py _execute_charm`'s own docstring
instead of here** (that's where the mechanic actually lives): an
Undead caster's Charm draws on Necromancy instead of Psychic, and a
co-located Hero must command no armies to be a valid free-hire target
(a real precondition this phase -- previously unchecked). The Undead-
King "Seduzione" branch (gradually turning a Hero Undead via repeated
casts) is confirmed but deliberately left unmodeled -- see that same
docstring for exactly why.

**Phase 184 addendum -- Psychic Blast [PS], tied to Ability.PSYCHIC
(PS), project-original (user-supplied).** Quoted in full: "Psychic
Blast [PS] (Incantesimo di Combattimento Individuale): chi lancia
l'incantesimo proietta una raffica di energia mentale con cui stordisce
il nemico guadagnando da 2 a 5 round supplementari d'attacco." ("The
caster projects a burst of mental energy that stuns the enemy, gaining
2 to 5 bonus attack rounds.") Unlike every spell modeled so far in this
family, there's no skill-level scaling at all -- a flat 2-5 roll
regardless of the caster's own Psychic level, so
`PERSONAL_COMBAT_SPELL_LEVEL_CAP` doesn't apply here either.
`roll_psychic_blast_stun_rounds()` is the entire mechanic: one uniform
roll in `PSYCHIC_BLAST_STUN_ROUNDS_RANGE = (2, 5)`. What a caller does
with the returned round count (extra Melee swings? a stun status the
opponent can't act during?) is left to a future tactic-walk engine --
same "not wired into `turn/search_execution.py` yet" scoping as every
other Personal-Combat spell above.

**Phase 185 addendum -- Telekinetic Storm [TE], tied to Ability.
PSYCHIC (PS), project-original (user-supplied).** Quoted in full:
"Telekinetic Storm [TE] (Incantesimo di Combattimento Individuale):
chi lancia l'incantesimo provoca una tempesta telecinetica, con
epicentro vicino alla vittima, che solleva in aria piccoli oggetti e
li fa ruotare vorticosamente in tutte le direzioni. L'incantesimo
infligge da 4 a 16 punti danno alla vittima. Alcuni oggetti colpiscono
anche chi lancia l'incantesimo: se egli si trova in zona di mischia,
riceve da 4 a 16 punti danno; da 2 a 8 se e' a portata d'arco e da 1 a
4 se e' a portata di incantesimo. La Tempesta Telecinetica e'
inefficace contro i mostri sottomarini." ("The caster provokes a
telekinetic storm, centered near the victim, that lifts small objects
into the air and spins them wildly in every direction. The spell
deals 4-16 damage to the victim. Some objects also strike the caster:
4-16 damage if he's in the melee zone, 2-8 if at bow range, and 1-4 if
at spell range. The spell has no effect against submarine monsters.")

No skill-level scaling at all, same as Charm/Psychic Blast --
`PERSONAL_COMBAT_SPELL_LEVEL_CAP` doesn't apply here either. The
caster's own self-damage range is keyed directly by this module's own
`CombatRange` (Phase 179): `roll_telekinetic_storm_caster_damage()`
takes the caster's *own* current `CombatRange` (not the victim's) and
looks up `TELEKINETIC_STORM_CASTER_DAMAGE_RANGE_BY_COMBAT_RANGE`.
`roll_telekinetic_storm_victim_damage()` and `roll_telekinetic_storm_
caster_damage()` both take a `target_is_immune: bool` flag (backed by
the new `models/monster.py SUBMARINE_MONSTERS`, renamed from
`TELEKINETIC_STORM_SUBMARINE_MONSTERS` in Phase 188 -- see that
module's own docstring addendum for why):
"inefficace contro i mostri sottomarini" reads as the storm not
manifesting at all against them, so both the victim's own damage *and*
the caster's own self-damage are suppressed together when immune --
unlike Spiritwrack's own Undead/Mechanical immunity (Phase 182), which
only ever affected the target's side, never the caster's.

**Phase 186 addendum -- Invisibility [IN], tied to Ability.ILLUSION
(IL), project-original (user-supplied).** Quoted in full: "Invisibility
[IN] (Incantesimo di Combattimento Individuale): la probabilita' di
essere colpiti con l'arco o nel corpo a corpo viene dimezzata per la
durata del combattimento. Usato nel Piano d'Incontro prima di rubare,
questo incantesimo vale come un modificatore di +15% al tentativo di
furto." ("Invisibility [IN] (Personal-Combat spell): the chance of
being hit with a bow or in melee is halved for the duration of
combat. Used in the Encounter Plan before stealing, this spell counts
as a +15% modifier to the theft attempt.")

Two independent effects, no skill-level scaling on either:

- `INVISIBILITY_HIT_CHANCE_MULTIPLIER = 0.5` and
  `invisibility_reduced_hit_chance(base_hit_chance)` halve *whatever*
  base hit chance the opponent would otherwise have against the
  invisible combatant -- applies equally to `fire_arrow_hit_chance()`
  and the flat `MELEE_HIT_CHANCE`, "per la durata del combattimento"
  ("for the duration of combat") reading as a persistent status rather
  than a single-round effect, though no per-round status-tracking
  exists in this project to actually carry that duration yet (same gap
  as everywhere else in this file).
- `INVISIBILITY_STEAL_ATTEMPT_BONUS = 0.15`: a flat +15 percentage-
  point bonus to a Steal attempt's own success chance, when Invisibility
  precedes a Steal tactic in the same Encounter Plan. **Confirmed to
  have no numeric formula to modify yet**: `turn/search_execution.py`'s
  own docstring already documents `Maneuver.STEAL` as decoded but
  entirely unwired (no resolution function exists), and a direct search
  confirms no Steal success-chance formula exists anywhere in this
  project -- only narrative-only renderers (`report/turn_report.py
  render_take_gold()`/`render_steal_caught_and_ransomed()`/
  `render_ice_steal_blocked()`) and purely descriptive ability-tooltip
  strings (`models/advanced_ability.py`'s own "the Thief adds 15% to
  his chance to Steal" text, never backed by code). This constant is
  therefore modeled the same way Charm's own Undead-King "Seduzione"
  branch was (Phase 183): a confirmed, sourced fact recorded now,
  ready for whichever future phase actually builds a real Steal-success
  formula to consume it.

**Phase 187 addendum -- Mirror-Image Phantasm (MI), tied to Ability.
ILLUSION (IL), project-original (user-supplied).** By far the most
elaborate Personal-Combat spell covered so far -- a genuine two-stage
state machine, not a single formula. Quoted in full: "The caster
creates a mirror-image illusion of his opponent and sends the
phantasm into combat. To his opponent, the phantasm is real and
initially has exactly the same characteristics as when the spell was
cast. The two mirror images then fight it out, while the caster must
concentrate on his illusion, performing no other actions. If another
Mirror-Image spell is cast while the illusion is fighting, both
illusions will dissipate. Before each combat round, there is a chance
that the victim will disbelieve the illusion, in which case the
illusion loses its power. The chance of disbelief for each type of
intelligence level is listed below. 15% per level of the spellcaster
(max 60%) is subtracted from the listed chance. Divine or Superhuman
120% / High Human 100% / Medium Human 80% / Low Human 60% / Animal
40% / Mechanical 20%. If the mirror image loses, the caster must
continue the fight at the current combat range. If it wins, the real
monster is mentally slain and falls to the ground. The illusion then
turns on its master, who is in such a deeply involved trance-state
that his own sense of reality is distorted. The illusion must be
disbelieved (at a bonus of 25% above Medium intelligence) or slain. If
the illusion wins, it fades out, and the real monster revives and
slays the fallen illusionist. If the illusion loses, the caster
automatically finishes off the mentally-slain monster and claims the
treasure."

**The full outcome tree, for reference (not executed by this phase --
see below for why):**

1. Each round, roll disbelief (base % by the *opponent's own*
   intelligence tier, minus `min(15%*IL_level, 60%)`).
   - Disbelieved -> same outcome as "mirror image loses" (3a).
   - Not disbelieved -> the illusion (an exact stat-copy of the
     opponent) duels the real opponent for that round.
2. If the illusion ever loses that duel -> (3a): the caster resumes
   fighting for real, at whatever `CombatRange` the fictional duel had
   reached.
3. If the illusion wins the duel (3b): the real opponent is mentally
   slain and falls; the illusion then turns on the caster himself.
   - The caster must disbelieve his own illusion (base = Medium Human
     80% + a flat 25% bonus = 105%, reduced by the *same*
     `min(15%*IL_level, 60%)` formula -- **confirmed directly by the
     user via `AskUserQuestion`**, since the source text doesn't
     restate the reduction explicitly for this second roll) or slay it
     in a second duel.
   - Illusion disbelieved/slain (caster wins) -> caster automatically
     finishes off the already-mentally-slain monster and claims the
     treasure.
   - Illusion wins (caster fails) -> the illusion fades, the real
     monster revives, and it slays the caster.

**What this phase actually models**: the two disbelief-chance formulas
only (`MirrorImageIntelligenceTier`, `MIRROR_IMAGE_DISBELIEF_BASE_
CHANCE`, `mirror_image_disbelief_chance()`, `resolve_mirror_image_
disbelief()`, and the Stage-2 `MIRROR_IMAGE_MASTER_DISBELIEF_BASE_
CHANCE`) -- these are the same "clean, testable primitive" shape every
other spell in this file already uses. **Not modeled**: the actual
duel resolution (illusion-vs-opponent, then caster-vs-illusion) and
the round-by-round state transitions between the three outcome
branches above. Both duels *could* reuse this module's own existing
`Combatant`/`resolve_melee_duel()` (the illusion is explicitly "an
exact stat-copy of the opponent," so a cloned `Combatant` and a normal
`resolve_melee_duel()` call would resolve it faithfully), but
orchestrating the actual round-by-round disbelief-then-duel state
machine is a new mini-engine this phase doesn't attempt to build --
same "not wired into `turn/search_execution.py` yet" scoping as every
Personal-Combat spell above, and the same reasoning Phase 179 gave for
not building a general CAST-tactic engine before more spells were
known.

**The "double dissipation" rule** ("if another Mirror-Image spell is
cast while the illusion is fighting, both illusions will dissipate")
is likewise left as a documented fact only, not code -- it has no
numeric magnitude to model and no consuming engine to hook into yet.

**Cross-reference, not reuse**: `MirrorImageIntelligenceTier.ANIMAL`/
`.MECHANICAL` happen to describe the same real-world categories
`models/monster.py SPIRITWRACK_ANIMAL_INTELLIGENCE_MONSTERS`/
`SPIRITWRACK_MECHANICAL_MONSTERS` (Phase 182) already enumerate by
species, but this module deliberately takes the tier as a caller-
supplied enum value rather than importing `Monster` to look it up
itself, the same "pure function, boolean-flag/enum-not-internal-
lookup" pattern Holy Symbol established (Phase 180) -- and unlike
those two Spiritwrack sets, this spell's other four tiers (Divine/
Superhuman, High/Medium/Low Human) have no existing species
classification in this project to draw on at all.

**Phase 188 addendum -- Fireball [FI], tied to Ability.ELEMENTAL,
project-original (user-supplied).** Quoted in full: "se usato in un
combattimento, provoca da 1 a 8 punti danno, più 1 punto danno per
livello (max 4). Questo incantesimo è inefficace contro i mostri
sottomarini." A straightforward damage roll: `FIREBALL_DAMAGE_RANGE`
(1-8) plus `FIREBALL_DAMAGE_PER_LEVEL` (1) per skill level, capped at
`PERSONAL_COMBAT_SPELL_LEVEL_CAP` (Phase 181) -- the user's own "max 4"
phrasing matches that existing project-wide cap exactly, so
`roll_fireball_damage()` reuses it rather than introducing a
Fireball-specific constant.

**The submarine-monster immunity, and the `SUBMARINE_MONSTERS`
rename.** The user reused "mostri sottomarini" here without re-listing
species, unlike Phase 185's Telekinetic Storm, which supplied the five
species explicitly (Elasmosaurus, Giant Octopus, Giant Clam, Great
White Whale, Mermaid). Read together, this is the same real-world
category referenced by a second spell, not a fresh list -- so
`models/monster.py`'s own `TELEKINETIC_STORM_SUBMARINE_MONSTERS` is
renamed to `SUBMARINE_MONSTERS` in this phase (dropping the spell
prefix) and both Telekinetic Storm's and Fireball's `target_is_immune`
flags are meant to be backed by this one shared set. This deliberately
breaks the spell-prefixed convention Phase 182 established for
Spiritwrack's three classification sets (kept prefixed there because
Undead/Mechanical/Animal-Intelligence are three conceptually distinct
reasons for the same outcome) -- see `models/monster.py`'s own module
docstring for the full rationale.

**Phase 189 addendum -- Ice Suspension [IC], tied to Ability.ELEMENTAL,
project-original (user-supplied).** Quoted in full: "chi lo lancia
rinchiude la sua vittima in un guscio magico di ghiaccio che lo blocca
o lo rallenta per alcuni round. Può rimanere bloccato un mostro o un
Eroe a cui restano fino a 4 punti ferita per livello di magia
elementare di chi lancia l'incantesimo. (max 16). In questo caso, il
mago elementale si impossesserà di tutti gli oggetti magici che la
vittima non porta con sé al momento e potrà scegliere tra fuggire (con
successo automatico) o attendere che il ghiaccio si sciolga a
sufficienza da permettere alla vittima di liberarsi. In questo caso
guadagnerà 3 round supplementari d'attacco (partendo da qualsiasi
distanza sia più conveniente per la successiva mossa di combattimento).
Se l'incantesimo non blocca il bersaglio, quest'ultimo verrà
rallentato. Il mago guadagnerà così da 1 a 3 round supplementari
d'attacco, a seconda di quanta parte del corpo del mostro è racchiusa
nel ghiaccio... Questo incantesimo è inefficace contro fantasmi, demoni
e simili... perché queste creature esistono solo parzialmente nel
mondo materiale e funziona in maniera differente contro mostri
volanti... Contro questi provocherà da 5 a 10 punti danno (la creatura
si schianta al suolo) e darà a chi ha lanciato l'incantesimo da 1 a 3
round supplementari d'attacco (indipendentemente dal livello nella
magia)."

By far the most branching Personal-Combat spell modeled so far -- three
mutually-exclusive outcome categories selected by the *target's own
type*, not by a single roll:

1. **Ghost/demon-like targets (`models/monster.py ICE_SUSPENSION_
   IMMUNE_MONSTERS`: Spectre, Genie, Balrog Demon, Marilith Demon,
   Succubus, Rakshasha, Ice Devil, Bone Devil, Imp, Ghost, Banshee) --
   the spell has no effect at all** (these creatures "exist only
   partially in the material world"). No function in this module is
   meant to be called for this category; the caller filters on it
   before dispatching to any of the two branches below, the same
   caller-side branch-selection this module already uses for Melee's
   monster-specific damage die (Phase 132 addendum) rather than a
   `target_is_immune` flag threaded through every function -- there
   isn't one shared formula to suppress here, there are two entirely
   different ones (frozen/slowed vs. flying).
2. **Flying monsters (`models/monster.py ICE_SUSPENSION_FLYING_
   MONSTERS`: Vampire, Giant Wasp, Beholder, Green/Gold/Silver/Black/
   Red Dragon, Giant Eagle, Couatl, Roc, Gargoyle, Gryphon) -- crash to
   the ground instead of freezing/slowing.** `ICE_SUSPENSION_FLYING_
   CRASH_DAMAGE_RANGE = (5, 10)` and `ICE_SUSPENSION_FLYING_BONUS_
   ROUNDS_RANGE = (1, 3)`, both flat rolls "indipendentemente dal
   livello" -- no skill-level scaling, unlike the ground case below.
3. **Everything else -- freeze-or-slow, by an HP threshold.**
   `ice_suspension_freeze_threshold(skill_level)` = `min(4 *
   skill_level, 16)` ("fino a 4 punti ferita per livello... max 16").
   `ice_suspension_is_frozen(victim_hit_points, skill_level)` is True
   when the victim's remaining HP is at or below that threshold.
   - **Frozen**: the caster seizes all magic items the victim isn't
     currently carrying (`ICE_SUSPENSION_SEIZES_UNCARRIED_MAGIC_ITEMS
     = True` -- a confirmed, sourced fact recorded with no consuming
     code yet, the same "confirmed fact, no formula to hook into"
     scoping Invisibility's own Steal bonus used, Phase 186; this
     project's item-ownership registry, Phase 140, tracks *who holds
     what* but has no "seize an item the holder isn't carrying"
     transfer operation to wire this into). The caster then chooses
     between fleeing (`ICE_SUSPENSION_FROZEN_FLEE_ALWAYS_SUCCEEDS =
     True`, the same always-succeeds pattern Charm's own Flee
     established, Phase 183) or waiting for the ice to melt
     (`ICE_SUSPENSION_FROZEN_BONUS_ROUNDS = 3`, a fixed count, no
     roll) -- which of the two the caster picks is a tactical
     decision for whatever future orchestration layer calls this, not
     something this module decides.
   - **Slowed** (not frozen): `ice_suspension_slowed_bonus_rounds(
     victim_hit_points, skill_level)` = `floor(4 * threshold /
     victim_hit_points)`, where `threshold` is the same freeze
     threshold above. **This formula was reverse-engineered from the
     user's own worked example and confirmed directly via
     `AskUserQuestion`** -- the example as literally written ("16
     punti ferita... livello 1... 16 diviso 4, fa ovviamente 1") is
     arithmetically inconsistent (16/4 = 4, not 1), but `floor(4 *
     min(4*1, 16) / 16)` = `floor(16/16)` = `1` reproduces the stated
     result exactly, and the user confirmed this is the intended
     formula. Only meaningful when the victim is *not* frozen (the
     precondition `victim_hit_points > threshold` guarantees the
     result is naturally in [0, 3], matching "da 1 a 3" as the typical
     non-zero case, with 0 explicitly allowed per "se questa divisione
     è 0 virgola non ci sono round supplementari d'attacco").
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum

# [5.0]: "In combat, all characters have 10 hit points. Monsters may
# have anywhere from 7 to 50 hit points." -- this module's own
# Combatant.hit_points defaults to the character value; a monster
# combatant supplies its own value explicitly.
CHARACTER_HIT_POINTS = 10

# [5.3] Melee: flat 50% base chance, 1-6 damage -- not skill-scaled.
MELEE_HIT_CHANCE = 0.50
MELEE_DAMAGE_RANGE = (1, 6)

# [5.2] Fire Arrow: 30% + 10%/Archery level, 1-6 damage.
FIRE_ARROW_BASE_HIT_CHANCE = 0.30
FIRE_ARROW_HIT_CHANCE_PER_LEVEL = 0.10
FIRE_ARROW_DAMAGE_RANGE = (1, 6)

# [5.0]: Neutral Kingdom characters' "Order of Duelists" +1 Melee/Archery.
NEUTRAL_DUELIST_BONUS = 1


class CombatRange(Enum):
    """Rulebook [5.0]'s three combat ranges -- see module docstring's own
    Phase 179 addendum for the full quoted rulebook text. Ordered
    farthest-to-closest, matching both "Encounters usually begin at
    spell range" and a real worked example's own progression (spell
    range -> "closed to bow range" -> "charged into melee range").
    """

    SPELL_RANGE = 0
    BOW_RANGE = 1
    MELEE_RANGE = 2


# Rulebook [5.0], quoted in the module docstring's own Phase 179
# addendum: spell disruption's cumulative-per-hit chance and its cap.
SPELL_DISRUPTION_CHANCE_PER_HIT = 0.20
SPELL_DISRUPTION_CHANCE_CAP = 0.95


def spell_disruption_chance(hits_taken_this_round: int) -> float:
    """The chance a spellcast attempt fails this round, per the user's own
    confirmed formula (module docstring's Phase 179 addendum): 20% per
    hit already landed on the caster this round, before the cast is
    attempted, capped at 95%. Counts *hits*, not damage points -- "ogni
    danno" ("every hit") -- matching the worked example, where a single
    landed Melee hit alone was enough to disrupt the very next cast.
    """

    return min(hits_taken_this_round * SPELL_DISRUPTION_CHANCE_PER_HIT, SPELL_DISRUPTION_CHANCE_CAP)


def resolve_spell_disruption(hits_taken_this_round: int, rng: random.Random) -> bool:
    """Rolls whether a spellcast attempt is disrupted this round -- see
    ``spell_disruption_chance()``'s own docstring for the formula.
    Returns True if disrupted (the cast fails, the round is lost).

    With zero hits taken this round, the chance is exactly 0% -- this
    returns False directly without consuming a roll, the same no-roll-
    when-the-outcome-is-fixed convention ``models/monster.py roll_
    monster_alignment()`` (Phase 176) already established.
    """

    if hits_taken_this_round <= 0:
        return False
    return rng.random() < spell_disruption_chance(hits_taken_this_round)


# Holy Symbol [HO], module docstring's own Phase 180 addendum -- project-
# original, user-supplied. 10%/level normally, 20%/level against an
# Undead or Anti-Holy target; 1-4 damage per level, Undead/Anti-Holy only.
# Tied to `Ability.WHITE` (White Magic) -- callers supply that ability's
# own skill level as `skill_level` below.
HOLY_SYMBOL_HIT_CHANCE_REDUCTION_PER_LEVEL = 0.10
HOLY_SYMBOL_UNDEAD_HIT_CHANCE_REDUCTION_PER_LEVEL = 0.20
HOLY_SYMBOL_UNDEAD_DAMAGE_RANGE_PER_LEVEL = (1, 4)

# Phase 181 addendum: every individual Personal-Combat spell effect caps
# out at skill level 4 -- the user's own words: "questo incantesimo, come
# tutti quelli di combattimento ha il CAP al livello 4. Quindi se ha il
# talento WH a 5 questo incantesimo -- come tutti -- ha gli stessi effetti
# del livello 4." ("this spell, like all combat spells, is capped at
# level 4. So a character with WH at 5 gets the same effect as level 4.")
# Stated as a rule covering *all* Personal-Combat spells, not just Holy
# Symbol -- future spells in this same family should apply this same
# cap, not just this one.
PERSONAL_COMBAT_SPELL_LEVEL_CAP = 4


def holy_symbol_hit_chance(
    base_hit_chance: float, skill_level: int, *, target_is_undead_or_anti_holy: bool = False
) -> float:
    """Holy Symbol's own reduction of the *opponent's* hit chance -- see
    module docstring's Phase 180 addendum for the quoted source and the
    worked example this matches exactly (level 1 vs. a 50% base chance
    -> 45%). Floored at 0% so an unusually high skill level can't drive
    the result negative. ``skill_level`` is capped at
    ``PERSONAL_COMBAT_SPELL_LEVEL_CAP`` (Phase 181): a caster with WH 5
    gets the exact same reduction as WH 4.
    """

    effective_level = min(skill_level, PERSONAL_COMBAT_SPELL_LEVEL_CAP)
    rate = (
        HOLY_SYMBOL_UNDEAD_HIT_CHANCE_REDUCTION_PER_LEVEL
        if target_is_undead_or_anti_holy
        else HOLY_SYMBOL_HIT_CHANCE_REDUCTION_PER_LEVEL
    )
    return max(0.0, base_hit_chance * (1.0 - rate * effective_level))


def roll_holy_symbol_undead_damage(skill_level: int, rng: random.Random) -> int:
    """Holy Symbol's bonus damage against an Undead or Anti-Holy target --
    one independent 1-4 roll per skill level, summed (module docstring's
    Phase 180 addendum: confirmed directly by the user). ``skill_level``
    0 returns 0 without consuming a roll, the same no-roll-when-the-
    outcome-is-fixed convention ``resolve_spell_disruption()`` above
    already established. ``skill_level`` is capped at
    ``PERSONAL_COMBAT_SPELL_LEVEL_CAP`` (Phase 181): a caster with WH 5
    rolls exactly 4 dice, the same as WH 4.
    """

    effective_level = min(skill_level, PERSONAL_COMBAT_SPELL_LEVEL_CAP)
    return sum(rng.randint(*HOLY_SYMBOL_UNDEAD_DAMAGE_RANGE_PER_LEVEL) for _ in range(effective_level))


# Spiritwrack [SP], module docstring's own Phase 182 addendum -- project-
# original, user-supplied. 1/2 point of Melee damage reduction per level
# normally, 1/4 point per level (halved) against an Animal-Intelligence
# target; no effect at all against an Undead or Mechanical target.
SPIRITWRACK_MELEE_DAMAGE_REDUCTION_PER_LEVEL = 0.5
SPIRITWRACK_ANIMAL_INTELLIGENCE_DAMAGE_RATE_MULTIPLIER = 0.5


def spiritwrack_blocks_cast_and_archery(*, target_is_immune: bool = False) -> bool:
    """Spiritwrack's own "the victim cannot cast spells nor shoot with a
    bow" effect. Always True unless ``target_is_immune`` (an Undead or
    Mechanical target -- see ``models/monster.py SPIRITWRACK_UNDEAD_
    MONSTERS``/``SPIRITWRACK_MECHANICAL_MONSTERS``), in which case the
    spell has no effect at all. Deliberately does **not** take an
    Animal-Intelligence flag: the user confirmed only the numeric Melee
    damage reduction is halved against those targets, not this block
    (module docstring's Phase 182 addendum).
    """

    return not target_is_immune


def spiritwrack_melee_damage_reduction(
    skill_level: int,
    rng: random.Random,
    *,
    target_is_immune: bool = False,
    target_is_animal_intelligence: bool = False,
) -> int:
    """Spiritwrack's own Melee damage reduction -- 1/2 point per skill
    level, randomly rounded up or down when the exact reduction isn't a
    whole number (see module docstring's Phase 182 addendum for the
    worked cases). Returns 0 without consuming any roll if
    ``target_is_immune`` (Undead or Mechanical -- fully ineffective).
    Halved (1/4 point per level) if ``target_is_animal_intelligence``.
    ``skill_level`` is capped at ``PERSONAL_COMBAT_SPELL_LEVEL_CAP``
    (Phase 181), same as Holy Symbol.
    """

    if target_is_immune:
        return 0

    effective_level = min(skill_level, PERSONAL_COMBAT_SPELL_LEVEL_CAP)
    rate = SPIRITWRACK_MELEE_DAMAGE_REDUCTION_PER_LEVEL
    if target_is_animal_intelligence:
        rate *= SPIRITWRACK_ANIMAL_INTELLIGENCE_DAMAGE_RATE_MULTIPLIER

    exact = rate * effective_level
    whole = int(exact)
    fraction = exact - whole
    if fraction <= 0.0:
        return whole
    return whole + 1 if rng.random() < fraction else whole


# Charm [CH], module docstring's own Phase 183 addendum -- project-
# original, user-supplied. Used mid-combat, Charm is unconditionally
# equivalent to a Flee command that always succeeds -- no roll, no
# skill-level-scaled magnitude, unlike every other Personal-Combat
# spell above.
CHARM_FLEE_ALWAYS_SUCCEEDS = True


# Psychic Blast [PS], module docstring's own Phase 184 addendum --
# project-original, user-supplied. A flat 2-5 bonus-attack-round roll,
# no skill-level scaling at all.
PSYCHIC_BLAST_STUN_ROUNDS_RANGE = (2, 5)


def roll_psychic_blast_stun_rounds(rng: random.Random) -> int:
    """Psychic Blast's own stun effect: "stordisce il nemico guadagnando
    da 2 a 5 round supplementari d'attacco" -- one uniform roll in
    ``PSYCHIC_BLAST_STUN_ROUNDS_RANGE``, unaffected by the caster's own
    skill level (unlike Holy Symbol/Spiritwrack).
    """

    return rng.randint(*PSYCHIC_BLAST_STUN_ROUNDS_RANGE)


# Telekinetic Storm [TE], module docstring's own Phase 185 addendum --
# project-original, user-supplied. Flat damage ranges, no skill-level
# scaling at all.
TELEKINETIC_STORM_VICTIM_DAMAGE_RANGE = (4, 16)

# The caster's own self-damage range, keyed by the caster's own
# current CombatRange (Phase 179) at the moment of casting.
TELEKINETIC_STORM_CASTER_DAMAGE_RANGE_BY_COMBAT_RANGE: dict[CombatRange, tuple[int, int]] = {
    CombatRange.MELEE_RANGE: (4, 16),
    CombatRange.BOW_RANGE: (2, 8),
    CombatRange.SPELL_RANGE: (1, 4),
}


def roll_telekinetic_storm_victim_damage(rng: random.Random, *, target_is_immune: bool = False) -> int:
    """Telekinetic Storm's own damage to the victim -- "infligge da 4 a
    16 punti danno alla vittima." Returns 0 without consuming a roll if
    ``target_is_immune`` (a submarine monster -- see module docstring's
    Phase 185 addendum and ``models/monster.py TELEKINETIC_STORM_
    SUBMARINE_MONSTERS``).
    """

    if target_is_immune:
        return 0
    return rng.randint(*TELEKINETIC_STORM_VICTIM_DAMAGE_RANGE)


def roll_telekinetic_storm_caster_damage(
    caster_combat_range: CombatRange, rng: random.Random, *, target_is_immune: bool = False
) -> int:
    """Telekinetic Storm's own self-damage to the caster -- "se egli si
    trova in zona di mischia, riceve da 4 a 16 punti danno; da 2 a 8 se
    e' a portata d'arco e da 1 a 4 se e' a portata di incantesimo."
    ``caster_combat_range`` is the *caster's own* current `CombatRange`
    at the moment of casting, not the victim's. Returns 0 without
    consuming a roll if ``target_is_immune`` -- the storm doesn't
    manifest against a submarine monster at all, so the caster takes no
    self-damage either (module docstring's Phase 185 addendum).
    """

    if target_is_immune:
        return 0
    return rng.randint(*TELEKINETIC_STORM_CASTER_DAMAGE_RANGE_BY_COMBAT_RANGE[caster_combat_range])


# Invisibility [IN], module docstring's own Phase 186 addendum --
# project-original, user-supplied. No skill-level scaling on either of
# its two independent effects.
INVISIBILITY_HIT_CHANCE_MULTIPLIER = 0.5

# A flat +15 percentage-point bonus to a Steal attempt's own success
# chance -- confirmed but not yet backed by any real Steal-success
# formula anywhere in this project (see module docstring's Phase 186
# addendum for why).
INVISIBILITY_STEAL_ATTEMPT_BONUS = 0.15


def invisibility_reduced_hit_chance(base_hit_chance: float) -> float:
    """Invisibility's own defensive effect: "la probabilita' di essere
    colpiti con l'arco o nel corpo a corpo viene dimezzata" -- halves
    whatever base hit chance the opponent would otherwise have against
    the invisible combatant. Applies equally to `fire_arrow_hit_
    chance()` and the flat `MELEE_HIT_CHANCE`.
    """

    return base_hit_chance * INVISIBILITY_HIT_CHANCE_MULTIPLIER


class MirrorImageIntelligenceTier(Enum):
    """The six intelligence tiers Mirror-Image Phantasm's own disbelief
    table is keyed by. See module docstring's Phase 187 addendum for
    the full quote and why this is a standalone enum rather than a
    lookup against `Monster`/`Race` (only two of the six tiers --
    Animal, Mechanical -- have any existing species classification in
    this project at all).
    """

    DIVINE_OR_SUPERHUMAN = "Divine or Superhuman"
    HIGH_HUMAN = "High Human"
    MEDIUM_HUMAN = "Medium Human"
    LOW_HUMAN = "Low Human"
    ANIMAL = "Animal"
    MECHANICAL = "Mechanical"


# Mirror-Image Phantasm (MI), module docstring's own Phase 187
# addendum -- project-original, user-supplied. Base disbelief chances
# by intelligence tier -- note several exceed 100%; that's the source
# text's own figures, clamped to [0, 1] only inside the roll function
# below, never here.
MIRROR_IMAGE_DISBELIEF_BASE_CHANCE: dict[MirrorImageIntelligenceTier, float] = {
    MirrorImageIntelligenceTier.DIVINE_OR_SUPERHUMAN: 1.20,
    MirrorImageIntelligenceTier.HIGH_HUMAN: 1.00,
    MirrorImageIntelligenceTier.MEDIUM_HUMAN: 0.80,
    MirrorImageIntelligenceTier.LOW_HUMAN: 0.60,
    MirrorImageIntelligenceTier.ANIMAL: 0.40,
    MirrorImageIntelligenceTier.MECHANICAL: 0.20,
}

MIRROR_IMAGE_DISBELIEF_REDUCTION_PER_LEVEL = 0.15
MIRROR_IMAGE_DISBELIEF_REDUCTION_CAP = 0.60

# Stage 2 (the illusion turning on its own caster): "a bonus of 25%
# above Medium intelligence" -- Medium Human's own 80% base, plus a
# flat 25 percentage points.
MIRROR_IMAGE_MASTER_DISBELIEF_BONUS = 0.25
MIRROR_IMAGE_MASTER_DISBELIEF_BASE_CHANCE = (
    MIRROR_IMAGE_DISBELIEF_BASE_CHANCE[MirrorImageIntelligenceTier.MEDIUM_HUMAN] + MIRROR_IMAGE_MASTER_DISBELIEF_BONUS
)


def mirror_image_disbelief_chance(base_chance: float, caster_skill_level: int) -> float:
    """Mirror-Image's own per-round disbelief-chance formula: "15% per
    level of the spellcaster (max 60%) is subtracted from the listed
    chance." ``base_chance`` is one of `MIRROR_IMAGE_DISBELIEF_BASE_
    CHANCE`'s own values for Stage 1, or `MIRROR_IMAGE_MASTER_
    DISBELIEF_BASE_CHANCE` for Stage 2 (module docstring's Phase 187
    addendum confirms the same reduction applies to both). Clamped to
    [0%, 100%] -- several of the source's own base chances exceed 100%
    before this reduction is applied.
    """

    reduction = min(MIRROR_IMAGE_DISBELIEF_REDUCTION_PER_LEVEL * caster_skill_level, MIRROR_IMAGE_DISBELIEF_REDUCTION_CAP)
    return max(0.0, min(1.0, base_chance - reduction))


def resolve_mirror_image_disbelief(base_chance: float, caster_skill_level: int, rng: random.Random) -> bool:
    """Rolls whether the illusion is disbelieved this round -- see
    ``mirror_image_disbelief_chance()``'s own docstring for the
    formula. Returns True if disbelieved. No roll is consumed when the
    chance is already fixed at 0% or 100% (the same no-roll-when-the-
    outcome-is-fixed convention this module's own `resolve_spell_
    disruption()` established).
    """

    chance = mirror_image_disbelief_chance(base_chance, caster_skill_level)
    if chance <= 0.0:
        return False
    if chance >= 1.0:
        return True
    return rng.random() < chance


# Fireball [FI], module docstring's own Phase 188 addendum -- project-
# original, user-supplied. 1-8 base damage, +1 per skill level, capped
# at PERSONAL_COMBAT_SPELL_LEVEL_CAP (Phase 181) -- same cap as Holy
# Symbol/Spiritwrack, this time reused rather than reinvented since the
# user's own "max 4" phrasing matches it exactly.
FIREBALL_DAMAGE_RANGE = (1, 8)
FIREBALL_DAMAGE_PER_LEVEL = 1


def roll_fireball_damage(skill_level: int, rng: random.Random, *, target_is_immune: bool = False) -> int:
    """Fireball's own damage: "da 1 a 8 punti danno, più 1 punto danno
    per livello (max 4)". Returns 0 without consuming a roll if
    ``target_is_immune`` (a submarine monster -- see ``models/monster
    .py SUBMARINE_MONSTERS``, shared with Telekinetic Storm since Phase
    188 confirmed both spells mean the exact same real-world category).
    ``skill_level`` is capped at ``PERSONAL_COMBAT_SPELL_LEVEL_CAP``
    (Phase 181), same as Holy Symbol/Spiritwrack.
    """

    if target_is_immune:
        return 0

    effective_level = min(skill_level, PERSONAL_COMBAT_SPELL_LEVEL_CAP)
    return rng.randint(*FIREBALL_DAMAGE_RANGE) + FIREBALL_DAMAGE_PER_LEVEL * effective_level


# Ice Suspension [IC], module docstring's own Phase 189 addendum --
# project-original, user-supplied. The ground-target freeze/slow
# branch: "fino a 4 punti ferita per livello... (max 16)".
ICE_SUSPENSION_FREEZE_POINTS_PER_LEVEL = 4
ICE_SUSPENSION_FREEZE_THRESHOLD_CAP = 16

# "potrà scegliere tra fuggire (con successo automatico)" -- same
# always-succeeds pattern as CHARM_FLEE_ALWAYS_SUCCEEDS (Phase 183),
# a separate constant since it is this spell's own confirmed fact.
ICE_SUSPENSION_FROZEN_FLEE_ALWAYS_SUCCEEDS = True

# "guadagnerà 3 round supplementari d'attacco" -- fixed, no roll.
ICE_SUSPENSION_FROZEN_BONUS_ROUNDS = 3

# "il mago elementale si impossesserà di tutti gli oggetti magici che
# la vittima non porta con sé al momento" -- a confirmed, sourced fact
# with no consuming code yet (this project's item-ownership registry,
# Phase 140, has no "seize an item its holder isn't carrying" transfer
# operation to hook into).
ICE_SUSPENSION_SEIZES_UNCARRIED_MAGIC_ITEMS = True

# The flying-monster branch: flat rolls, "indipendentemente dal
# livello nella magia" -- no skill-level scaling.
ICE_SUSPENSION_FLYING_CRASH_DAMAGE_RANGE = (5, 10)
ICE_SUSPENSION_FLYING_BONUS_ROUNDS_RANGE = (1, 3)


def ice_suspension_freeze_threshold(skill_level: int) -> int:
    """"fino a 4 punti ferita per livello di magia elementare... (max
    16)" -- the maximum remaining HP a target can have and still be
    frozen solid, capped at 16 regardless of how high the caster's own
    skill level climbs.
    """

    return min(ICE_SUSPENSION_FREEZE_POINTS_PER_LEVEL * skill_level, ICE_SUSPENSION_FREEZE_THRESHOLD_CAP)


def ice_suspension_is_frozen(victim_hit_points: int, skill_level: int) -> bool:
    """True when the victim's remaining HP is at or below this
    caster's own ``ice_suspension_freeze_threshold()`` -- the target is
    fully encased and helpless. False means the "slowed" branch
    applies instead (see ``ice_suspension_slowed_bonus_rounds()``).
    """

    return victim_hit_points <= ice_suspension_freeze_threshold(skill_level)


def ice_suspension_slowed_bonus_rounds(victim_hit_points: int, skill_level: int) -> int:
    """The "rallentato" branch's bonus-attack-round count: ``floor(4 *
    threshold / victim_hit_points)``, where ``threshold`` is this
    caster's own ``ice_suspension_freeze_threshold()``. Reverse-
    engineered from the user's own worked example (16 HP remaining,
    skill level 1 -> 1 bonus round: ``floor(4 * 4 / 16)`` = 1) and
    confirmed directly by the user via ``AskUserQuestion``, since the
    example as literally stated ("16 diviso 4, fa ovviamente 1") is
    arithmetically inconsistent taken at face value. Only meaningful
    when ``ice_suspension_is_frozen()`` is False for the same inputs --
    that precondition (``victim_hit_points > threshold``) is what keeps
    the result naturally within [0, 3].
    """

    threshold = ice_suspension_freeze_threshold(skill_level)
    return (ICE_SUSPENSION_FREEZE_POINTS_PER_LEVEL * threshold) // victim_hit_points


def roll_ice_suspension_flying_crash_damage(rng: random.Random) -> int:
    """The flying-monster branch's crash damage: "da 5 a 10 punti
    danno (la creatura si schianta al suolo)" -- flat, no skill-level
    scaling.
    """

    return rng.randint(*ICE_SUSPENSION_FLYING_CRASH_DAMAGE_RANGE)


def roll_ice_suspension_flying_bonus_rounds(rng: random.Random) -> int:
    """The flying-monster branch's bonus-attack-round count: "da 1 a 3
    round supplementari d'attacco (indipendentemente dal livello nella
    magia)" -- flat, no skill-level scaling.
    """

    return rng.randint(*ICE_SUSPENSION_FLYING_BONUS_ROUNDS_RANGE)


@dataclass(slots=True)
class Combatant:
    name: str
    hit_points: int = CHARACTER_HIT_POINTS
    # Ability.MELEE level -- only feeds initiative ordering ([5.0]), not
    # the flat 50% Melee hit chance itself ([5.3]).
    melee_skill: int = 0
    # Ability.ARCHERY level -- feeds both Fire Arrow's hit chance and its
    # free-attack count ([5.2]).
    archery_skill: int = 0
    neutral_duelist_bonus: bool = False
    # This combatant's own Melee damage die -- defaults to the character
    # rule ([5.3]: "does 1-6 damage points per swing"). A monster
    # combatant overrides it with its own species die from
    # `models/monster.py MONSTER_STATS` -- see Phase 132 addendum above.
    melee_damage_range: tuple[int, int] = MELEE_DAMAGE_RANGE
    # This combatant's own Fire Arrow damage die -- defaults to the
    # character rule ([5.2]: "the damage is 1-6 hit points"). A monster
    # combatant overrides it with its own species die from
    # `models/monster.py MonsterCombatStats.missile_damage` -- see
    # Phase 170 addendum above.
    missile_damage_range: tuple[int, int] = FIRE_ARROW_DAMAGE_RANGE
    # Hit points regenerated at the end of each round this combatant
    # survives -- 0 for every existing caller. Troll's own regeneration
    # rule (Phase 155 addendum above) is the only real, sourced user so
    # far; `turn/search_execution.py` sets it for a Troll's own
    # monster combatant.
    regenerates_hp: int = 0


def effective_melee_skill(combatant: Combatant) -> int:
    return combatant.melee_skill + (NEUTRAL_DUELIST_BONUS if combatant.neutral_duelist_bonus else 0)


def effective_archery_skill(combatant: Combatant) -> int:
    return combatant.archery_skill + (NEUTRAL_DUELIST_BONUS if combatant.neutral_duelist_bonus else 0)


def fire_arrow_hit_chance(archery_skill: int) -> float:
    """Rulebook [5.2]: "The base chance to hit is 30%, plus 10% per Archery level."."""

    return FIRE_ARROW_BASE_HIT_CHANCE + FIRE_ARROW_HIT_CHANCE_PER_LEVEL * archery_skill


def fire_arrow_free_attacks(archery_skill: int) -> int:
    """Rulebook [5.2]: "a number of free attacks equal to the level of archery skill."."""

    return archery_skill


def roll_melee_attack(rng: random.Random, damage_range: tuple[int, int] = MELEE_DAMAGE_RANGE) -> int:
    """Rulebook [5.3]: one Melee swing. Returns damage dealt (0 on a miss).

    ``damage_range`` defaults to the character rule; pass an attacker's
    own ``Combatant.melee_damage_range`` for a species-specific die
    (Phase 132 addendum, module docstring).
    """

    if rng.random() < MELEE_HIT_CHANCE:
        return rng.randint(*damage_range)
    return 0


def roll_fire_arrow_attack(
    archery_skill: int, rng: random.Random, damage_range: tuple[int, int] = FIRE_ARROW_DAMAGE_RANGE
) -> int:
    """Rulebook [5.2]: one Fire Arrow shot. Returns damage dealt (0 on a miss).

    ``damage_range`` defaults to the character rule; pass an attacker's
    own ``Combatant.missile_damage_range`` for a species-specific die
    (Phase 170 addendum, module docstring).
    """

    if rng.random() < fire_arrow_hit_chance(archery_skill):
        return rng.randint(*damage_range)
    return 0


def _acts_first(skill_a: int, skill_b: int, rng: random.Random) -> bool:
    """Rulebook [5.0]: "The character with the greater skill level relevant to the
    tactic he is using generally goes first in the combat round... If
    the skill is the same, the characters go in random order." Returns
    True if the first combatant (by caller's own ordering) acts first.
    """

    if skill_a > skill_b:
        return True
    if skill_b > skill_a:
        return False
    return rng.random() < 0.5


@dataclass(slots=True)
class FireArrowShot:
    """One Fire Arrow shot's outcome (Phase 175) -- ``shooter`` is ``"a"``/``"b"``,
    matching ``EncounterCombatResult.winner``'s own convention.
    ``damage`` is ``0`` on a miss. Only ``resolve_fire_arrow_duel()``
    populates these; ``resolve_melee_duel()`` has no per-swing log and
    always returns an empty ``shots`` tuple.
    """

    shooter: str  # "a" / "b"
    hit: bool
    damage: int


@dataclass(slots=True)
class EncounterCombatResult:
    winner: str | None  # "a" / "b" / None (both survived -- see each resolver's docstring)
    rounds: int
    # Phase 175: per-shot Fire Arrow detail, for narrating each shot
    # individually (see report/turn_report.py's own Phase 175 addendum).
    # Empty for every Melee duel and for every existing caller before
    # this phase.
    shots: tuple[FireArrowShot, ...] = ()


def resolve_melee_duel(
    a: Combatant, b: Combatant, rng: random.Random, *, max_rounds: int = 1000
) -> EncounterCombatResult:
    """Rulebook [5.3]: repeated Melee rounds until one combatant's hit points reach 0.

    Mutates ``a``/``b`` in place (``hit_points`` decreases as damage
    lands, using each attacker's own ``melee_damage_range`` -- Phase 132
    addendum). Both combatants are assumed to fight with Melee only for
    the whole encounter -- see module docstring for why mixed tactics and
    range transitions aren't modeled. ``max_rounds`` is a defensive
    engineering cap, not a rulebook rule -- with a 50% hit chance and
    1-6 damage against 10 hit points, a real duel ends in a handful of
    rounds; 1000 only guards against a pathological caller-supplied
    ``rng`` that never lands a hit.
    """

    skill_a, skill_b = effective_melee_skill(a), effective_melee_skill(b)
    for round_number in range(1, max_rounds + 1):
        first, second = (a, b) if _acts_first(skill_a, skill_b, rng) else (b, a)
        for attacker, defender in ((first, second), (second, first)):
            if attacker.hit_points <= 0 or defender.hit_points <= 0:
                continue
            defender.hit_points -= roll_melee_attack(rng, damage_range=attacker.melee_damage_range)
            if defender.hit_points <= 0:
                return EncounterCombatResult(winner=("a" if defender is b else "b"), rounds=round_number)
        _apply_end_of_round_regeneration(a, b)
    return EncounterCombatResult(winner=None, rounds=max_rounds)


def _apply_end_of_round_regeneration(a: Combatant, b: Combatant) -> None:
    """Phase 155 addendum (module docstring): a surviving combatant with
    ``regenerates_hp`` set (Troll's own rule -- 0 for everyone else)
    heals that much at the end of each combat round, uncapped.
    """

    if a.hit_points > 0:
        a.hit_points += a.regenerates_hp
    if b.hit_points > 0:
        b.hit_points += b.regenerates_hp


def resolve_fire_arrow_duel(a: Combatant, b: Combatant, rng: random.Random) -> EncounterCombatResult:
    """Rulebook [5.2]: each combatant fires up to ``fire_arrow_free_attacks(archery_skill)``
    shots, interleaved round-by-round by initiative (higher Archery
    skill first, tie random -- see ``_acts_first``). Stops once one
    combatant dies, or once both have exhausted their free attacks with
    neither dead (``winner=None`` -- confirmed (module docstring's Phase
    173 addendum) to mean "fall through to the Encounter Plan's next
    tactic," resolved one layer up by the caller, not here -- only a
    single Fire Arrow order can ever appear in a plan, so this duel
    itself never needs to know what comes next).

    Mutates ``a``/``b`` in place. The round-by-round interleaving for
    *unequal* free-attack counts is itself a documented design choice
    (the rulebook gives each combatant's total count, not how two
    different counts interleave against each other) -- implemented as
    "whoever still has shots left fires this round, in initiative
    order," which naturally lets the higher-Archery combatant keep
    firing solo once the other runs out.
    """

    skill_a, skill_b = effective_archery_skill(a), effective_archery_skill(b)
    shots_a, shots_b = fire_arrow_free_attacks(skill_a), fire_arrow_free_attacks(skill_b)
    used_a = used_b = 0
    total_rounds = max(shots_a, shots_b)
    shots: list[FireArrowShot] = []

    round_number = 0
    for round_number in range(1, total_rounds + 1):
        order = (a, b) if _acts_first(skill_a, skill_b, rng) else (b, a)
        for combatant in order:
            if a.hit_points <= 0 or b.hit_points <= 0:
                break
            if combatant is a:
                if used_a >= shots_a:
                    continue
                used_a += 1
                damage = roll_fire_arrow_attack(skill_a, rng, damage_range=a.missile_damage_range)
                shots.append(FireArrowShot(shooter="a", hit=damage > 0, damage=damage))
                b.hit_points -= damage
            else:
                if used_b >= shots_b:
                    continue
                used_b += 1
                damage = roll_fire_arrow_attack(skill_b, rng, damage_range=b.missile_damage_range)
                shots.append(FireArrowShot(shooter="b", hit=damage > 0, damage=damage))
                a.hit_points -= damage
        if a.hit_points <= 0 or b.hit_points <= 0:
            break
        _apply_end_of_round_regeneration(a, b)

    if b.hit_points <= 0:
        return EncounterCombatResult(winner="a", rounds=round_number, shots=tuple(shots))
    if a.hit_points <= 0:
        return EncounterCombatResult(winner="b", rounds=round_number, shots=tuple(shots))
    return EncounterCombatResult(winner=None, rounds=round_number, shots=tuple(shots))
