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
- ~~**Temper's effect on Melee**~~ -- **closed, Phase 284.** The original
  claim here ("this project has no `Temper` model anywhere") was already
  stale by the time it was written: `models/temper.py`'s `Temper` enum
  and `LeaderState.temper` have existed since Phase 82/139. The real gap
  was only the Temper Table's own melee mechanics themselves -- see the
  "Phase 284 addendum" below.
- **Victory and Death's aftermath** ([5.9]): looting a vanquished foe's
  treasure, magic items changing hands, and (for a slain King) his
  eldest son taking over with *player-chosen* starting ability levels --
  the last of these needs interactive player choice this automated
  engine has no channel for at all, not just missing game-state logic.
  ~~Looting a vanquished foe's own treasure/magic items~~ -- **closed by
  Phase 313**: `loot_defeated_leader()` below transfers every
  `ItemInstance` (`models/item.py`) the loser owned to the winner via
  `GameState.transfer_item()` (Phase 140's own item registry) --
  distinct from `turn/search_execution.py`'s own Phase 242 grant of a
  guarded *feature*'s own `Feature.treasure` on a Search win, which
  covers a monster guardian's hoard, not another character's personal
  inventory. Wired into every site where character-vs-character personal
  combat kills the loser: `turn/challenge_execution.py execute_challenge()`,
  `turn/patrol_execution.py execute_patrol()`, `turn/pursue_execution.py`'s
  own armyless-combat branch, and `turn/cast_execution.py`'s Kill_Enemy
  Berserk-retaliation-on-failure (both outcomes). **Not** wired into
  army-vs-army battle deaths (`turn/battle_orchestrator.py`) -- [5.9] is
  explicitly personal-combat vocabulary ("a vanquished foe"), and a
  defeated *army*'s own commanding leader, if any, survives that defeat
  (armies rout/disband; only a personal duel kills the leader
  themselves) -- so this gap was scoped to leader-vs-leader death only,
  matching where the rulebook's own "Victory and Death" section [5.0]-
  [5.9] actually lives. King succession's own *player-choice* half
  stays unaddressed, unchanged -- a distinct, still-open gap (see the
  paragraph above).

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
`blocks_cast_and_archery()` (renamed from `spiritwrack_blocks_cast_
and_archery()` in Phase 190, when Hand of Death was confirmed to share
this exact same victim effect) doesn't take that flag at all, by
design -- only `target_is_immune` (Undead or Mechanical) suppresses it.

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
  precedes a Steal tactic in the same Encounter Plan. **The Steal-
  success formula this modifies now exists** (`steal_success_chance()`,
  module docstring's own Phase 239 addendum) -- this bonus itself isn't
  consumed by that formula yet, since Phase 239 only wires Search's own
  monster-target case, which never precedes Steal with Invisibility in
  any real sample data; left as the same "confirmed, sourced fact
  recorded now" placeholder for whichever future phase wires
  Invisibility-then-Steal specifically.

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

**Phase 190 addendum -- Hand of Death [HA], tied to Ability.NECROMANCY,
project-original (user-supplied), the first Necromancy Personal-Combat
spell.** Quoted in full: "chi lancia questo incantesimo fa
ripetutamente il gesto di stringere forte il pugno come se strizzasse
qualcosa e, per magia, il suo avversario avrà la sensazione che il suo
cuore (o un altro organo sensibile) venga ridotto in poltiglia. Chi sta
usando la Mano della Morte non può lanciare altri incantesimi né
attaccare a mischia e si difende nel combattimento a corpo a corpo al
livello di abilità che ha in Necromancy e non a quello che ha in Melee.
Ogni attacco sferrato da chi lancia l'incantesimo provoca 1 punto danno
più ½ punto per livello in magia nera. La vittima non può lanciare
incantesimi né tirare con l'arco e le sue probabilità di colpire nel
combattimento corpo a corpo sono dimezzate. Quando chi lancia
l'incantesimo viene colpito perde la concentrazione e l'incantesimo
svanisce. La Mano della Morte è inefficace contro mostri meccanici
[Gargoyle, Golem], Non-Morti [Spectre, Ghost, Vampire, Mummy, Banshee,
Lich] o anti-holy [Balrog Demon, Marilith Demon, Succubus, Rakshasha,
Ice Devil, Bone Devil, Imp]." ("Magia nera" is this project's own
established synonym for Necromancy -- `models/office.py`'s own
`Office.NECRO_MAGE: "Sorceror of Black Magic"` confirms the pairing.)

**No level cap this time.** Unlike Holy Symbol/Spiritwrack (Phase
180/182, capped at `PERSONAL_COMBAT_SPELL_LEVEL_CAP = 4`, confirmed
Phase 181) or Fireball (Phase 188, explicitly stated "max 4" matching
that same cap), the user's own text states no maximum at all for Hand
of Death's damage formula -- so `roll_hand_of_death_damage()` applies
`HAND_OF_DEATH_DAMAGE_PER_LEVEL` uncapped, the same uncapped treatment
Charm/Psychic Blast/Telekinetic Storm/Invisibility already received
for the same reason (no cap stated).

**The caster's own three self-imposed constraints while channeling**
are recorded as confirmed facts, not wired into any combat loop (this
project has no CAST-tactic orchestration engine yet, same scoping as
every Personal-Combat spell above): `HAND_OF_DEATH_BLOCKS_CASTER_
OTHER_CASTS = True`, `HAND_OF_DEATH_BLOCKS_CASTER_MELEE_ATTACK = True`,
and `hand_of_death_caster_melee_defense_skill(necromancy_skill_level)`
(a documented identity substitution -- the caster's own melee-defense
initiative uses their Necromancy skill level in place of their Melee
skill level, per `_acts_first()`'s generic rule from [5.0]).
`HAND_OF_DEATH_ENDS_WHEN_CASTER_IS_HIT = True` records "perde la
concentrazione e l'incantesimo svanisce" -- a confirmed fact only, no
consuming combat loop to end.

**The caster's own attack**: `roll_hand_of_death_damage(skill_level,
rng, *, target_is_immune=False)` -- `HAND_OF_DEATH_BASE_DAMAGE = 1`
plus `HAND_OF_DEATH_DAMAGE_PER_LEVEL = 0.5` per level, using the same
random-rounding-when-fractional convention Spiritwrack's own melee
damage reduction established (Phase 182): a whole exact value resolves
without a roll, a `.5` fractional part is a 50/50 coin flip. Returns 0
without a roll when `target_is_immune`.

**The victim's own two effects**: "non può lanciare incantesimi né
tirare con l'arco" is the *exact same restriction, word for word*, as
Spiritwrack's own victim effect (Phase 182 addendum: "the victim cannot
cast spells nor shoot with a bow") -- confirmed as one shared game rule
applied by two different spells, the same "same real category" test
Phase 188 used for `SUBMARINE_MONSTERS`. `spiritwrack_blocks_cast_and_
archery()` is therefore **renamed to `blocks_cast_and_archery()`** in
this phase (dropping the spell prefix); Spiritwrack's own call sites
and docstring cross-reference are updated to the new name, its
behavior unchanged. Hand of Death's second victim effect -- "le sue
probabilità di colpire nel combattimento corpo a corpo sono dimezzate"
-- is **not** the same mechanic as Invisibility's own hit-chance
halving (Phase 186): Invisibility halves the *chance of the invisible
caster being hit*; here it is the *victim's own chance of landing a
hit* that is halved. Same 0.5 multiplier, opposite direction and
opposite party, so `hand_of_death_victim_hit_chance()` is kept as its
own spell-prefixed constant/function pair (`HAND_OF_DEATH_VICTIM_HIT_
CHANCE_MULTIPLIER = 0.5`) rather than reused or merged with
Invisibility's -- conflating the two under one name would obscure
which side of the combat each one actually modifies.

**Immunity -- two exact reuses, one new set.** "Mostri meccanici"
[Gargoyle, Golem] and "Non-Morti" [Spectre, Ghost, Vampire, Mummy,
Banshee, Lich] are, species-for-species, *identical* to `models/
monster.py`'s existing `SPIRITWRACK_MECHANICAL_MONSTERS`/
`SPIRITWRACK_UNDEAD_MONSTERS` (Phase 182) -- reused directly rather
than duplicated, the same reasoning as `SUBMARINE_MONSTERS` (Phase
188). "Anti-holy" [Balrog Demon, Marilith Demon, Succubus, Rakshasha,
Ice Devil, Bone Devil, Imp] is a genuinely new seven-species set --
new `HAND_OF_DEATH_ANTI_HOLY_MONSTERS` (spell-prefixed, since it is a
strict *subset* of Phase 189's own `ICE_SUSPENSION_IMMUNE_MONSTERS`,
not identical to it -- that set also includes Spectre/Genie/Ghost/
Banshee, which the user places under "Non-Morti" here instead, so
reusing it would silently misclassify four species). `HAND_OF_DEATH_
IMMUNE_MONSTERS` is the union of all three, provided as one convenience
set matching every other spell's single immune-set name.

**Single `target_is_immune` flag, not caller-side branch selection.**
Unlike Ice Suspension (Phase 189), which has three *different* effects
selected by monster type, Hand of Death has exactly one effect
suppressed uniformly when immune -- so it follows Telekinetic Storm/
Fireball's style (Phase 185/188): `target_is_immune` threads through
`roll_hand_of_death_damage()`, `blocks_cast_and_archery()` (already
took this flag), and `hand_of_death_victim_hit_chance()`.

**Phase 191 addendum -- Control Undead [CO], tied to Ability.
NECROMANCY, project-original (user-supplied), the second and final
Necromancy Personal-Combat spell** (completing the ten Personal-Combat-
only spells `turn/cast_execution.py`'s own Phase 60 docstring already
named: Holy_Symbol, Spiritwrack, Psychic_Blast, Telek_Storm,
Invisibility, Mirror_Image, Fireball, Ice_Suspend, Hand_of_Death,
Control_Undead). Quoted in full: "chi lancia questo incantesimo può
tenere sotto controllo qualunque mostro (ma anche eroe o RE) Non-Morto
(Spectre, Ghost, Vampire, Mummy, Banshee, Lich) per il tempo necessario
a piantargli un paletto nel cuore (o neutralizzarlo in un altro modo).
Se però l'incantesimo fallisce, nella vittima designata si scatenerà
una furia omicida che farà aumentare i suoi Punti Ferita del 50-100%."

**Targeting**: the same six species as `SPIRITWRACK_UNDEAD_MONSTERS`
(Phase 182) -- reused directly, not duplicated under a new spell
prefix (the same exact-species-match test Phase 188 established for
`SUBMARINE_MONSTERS`). "(ma anche eroe o RE)" confirms the Undead
qualifier extends to characters too (an Undead Hero or King, not just
monsters) -- recorded as a confirmed fact only; `models/game_state.py
LeaderState` has no "is this leader Undead" field to check, so there is
nothing to gate a function parameter on yet.

**No success-chance formula was given in the text quoted at the time**
-- unlike every numeric roll in this project, which always comes from a
directly quoted rulebook percentage or range, whether the control
attempt succeeds was left entirely undetermined here. Inventing one
(e.g. reusing `turn/cast_execution.py`'s own `ACTION_SPELL_BASE_CHANCE`/
`ACTION_SPELL_CHANCE_PER_LEVEL`, rulebook [3.10]'s general Action-Cast
formula) would have been exactly the kind of guess this project avoids
-- that formula is textually scoped to top-level Action-Cast spells
([3.10]), not the Personal-Combat-only spells [4.2x.4]-[4.2x.5]
documents separately, and nothing confirmed the two shared a formula
*at the time*. **Corrected in Phase 192**: the user directly re-quoted
[3.10] in full, confirming Personal-Combat spells have their own
distinct success formula after all -- see the Phase 192 addendum below
for `resolve_personal_combat_spell_cast()`, which now supplies exactly
the roll this paragraph originally declined to invent. So, the same way
Ice Suspension left "flee or wait" as "a tactical decision for whatever
future orchestration layer calls this" (Phase 189) and Mirror-Image
left its entire duel outcome tree unresolved (Phase 187), **this module
still models only the two branches' own confirmed magnitudes, not which
branch is taken** -- only the *success-chance roll itself* was the
missing piece, now filled in generically for all ten Personal-Combat
spells rather than added just here:

- **Success**: `CONTROL_UNDEAD_SUCCESS_NEUTRALIZES_TARGET = True` --
  "per il tempo necessario a piantargli un paletto nel cuore" reads as
  the target being removed from combat outright; a confirmed,
  qualitative fact with no numeric magnitude and no consuming combat
  loop yet, the same scoping every other Personal-Combat spell above
  received.
- **Failure**: `CONTROL_UNDEAD_FAILURE_HP_INCREASE_RANGE = (0.50,
  1.00)` (a fraction, "50-100%"). `roll_control_undead_failure_hp_
  increase(rng)` uses `rng.uniform()` rather than `rng.randint()` --
  the only continuous (non-integer-die) roll range in this project so
  far, since "50-100%" is a percentage, not a die. `control_undead_
  failure_new_hit_points(hit_points, rng)` applies it: `round(hit_points
  * (1 + increase))`.

**Phase 192 addendum -- the general Personal-Combat spell cast success
formula, retroactively confirmed for all ten Personal-Combat spells.**
The user directly re-quoted Regolamento AK.txt [3.10] in full: "Un
personaggio può lanciare un incantesimo solo se ha un livello di
abilità di almeno 1 nel relativo Talento. La probabilità di riuscita di
un Incantesimo d'Azione è del 15% più 15% per livello. Gli Incantesimi
di Combattimento Individuale hanno una probabilità di riuscita del 30%
più 15% per livello. Le probabilità di successo per incantesimi non
possono mai superare il 95%. Se l'incantesimo fallisce non ci sono
conseguenze dirette. Gli Incantesimi di Combattimento individuale
funzionano esattamente nella maniera descritta e non hanno altre
conseguenze di rilievo. Ad esempio l'incantesimo Raffica Psichica non
accresce le probabilità di colpire in un combattimento corpo a corpo,
né permette di abbandonare il combattimento. I Reami Pagani... sono
coadiuvati da un Ordine di Maghi. Tutti i personaggi appartenenti a
quel Reame hanno quindi un modificatore +10% nei loro tentativi di
lanciare qualsiasi incantesimo fuorché quelli di Magia Bianca."

This resolves Control Undead's own Phase 191 gap (above) and applies
uniformly to Holy Symbol, Spiritwrack, Psychic Blast, Telekinetic
Storm, Invisibility, Mirror-Image, Fireball, Ice Suspension, Hand of
Death, and Control Undead alike -- none of them needed their own
success-chance formula individually; this is the one shared roll that
gates whether *any* of their already-modeled effects apply at all.

`PERSONAL_COMBAT_SPELL_CAST_BASE_CHANCE = 0.30`,
`PERSONAL_COMBAT_SPELL_CAST_CHANCE_PER_LEVEL = 0.15`,
`PERSONAL_COMBAT_SPELL_CAST_CHANCE_CAP = 0.95` (the same 95% ceiling
`turn/cast_execution.py`'s own `ACTION_SPELL_CHANCE_CAP` uses for
Action-Cast spells -- confirmed as one shared universal rule, but kept
as its own citation-backed constant in each module rather than a
cross-import, since the two modules serve genuinely different tactic
layers). `personal_combat_spell_cast_chance(skill_level, *,
caster_is_pagan=False)` computes the base+per-level chance, adds
`PERSONAL_COMBAT_PAGAN_MAGE_ORDER_BONUS` (0.10) when
`caster_is_pagan`, and clamps at the cap.
`resolve_personal_combat_spell_cast(skill_level, rng, *,
caster_is_pagan=False)` rolls it. Same "pure function, boolean-flag,
not internal lookup" pattern every spell above uses: the caller decides
`caster_is_pagan` (looking up the caster's own `KingdomState.alignment
is Alignment.PAGAN`, mirroring `NEUTRAL_DUELIST_BONUS`'s own lookup)
and must pass `False` for White Magic spells (Holy Symbol, Spiritwrack)
regardless of the caster's own kingdom, since the bonus explicitly
excludes Magia Bianca -- this module has no `Ability` parameter to
gate that internally, by the same design choice already used
throughout.

**Also confirmed, not modeled**: the quoted text also describes
per-turn Action-Cast quotas (1 cast/turn, 2 at skill level 3, 3 at
level 4) and a per-encounter "not twice with the same Personal-Combat
spell" limit -- see `turn/cast_execution.py`'s own Phase 192 addendum
for why neither is wired in yet (no per-turn/per-encounter cast-count
state exists anywhere in this project).

**Phase 200 addendum -- Words of Healing [WH], tied to Ability.WHITE,
project-original (user-supplied), the eleventh Personal-Combat spell
and the first of the ten secret-ordinal spells (`Spell.HEAL = 26`,
[2.0]'s "secret special spells and capabilities... attainable at high
levels of ability") to actually get its mechanic modeled.** Quoted in
full: "WORDS OF HEALING SPELL: New Special Combat Heal (can be casted
using the command CA-WH): A new Combat Spell is gained called "Words
of Healing". With this spell, a White Magician is able to heal himself
even in the heat of battle (before now, healing is not possible in
combat situations). The character is completely healed when the Words
of Healing are spoken, gaining back all lost hit points. The spell is
also half as likely to be disrupted by your opponent's tactics as
other spells."

Unlike "the ten" Phase 60/191's own docstrings enumerate (Holy_Symbol
through Control_Undead), Words of Healing is granted via
`models/advanced_ability.py AdvancedAbility.WORDS_OF_HEALING_SPELL`
(White Magic skill 5+) rather than the base-Ability-skill-1+ gate the
other ten use -- already fully documented at the model/metadata layer
(`Spell.HEAL`, `SPELL_NAME`/`SPELL_ABBREVIATION["WH"]`,
`ADVANCED_ABILITY_GRANTS_SPELL[WORDS_OF_HEALING_SPELL] = Spell.HEAL`)
before this phase; only the actual combat mechanic was missing.

**Two independent effects, no skill-level scaling on either** (so
`PERSONAL_COMBAT_SPELL_LEVEL_CAP` doesn't apply here, matching
Charm/Psychic Blast/Telekinetic Storm/Invisibility's own uncapped,
non-scaling effects):

- **"Completely healed... gaining back all lost hit points."**
  `words_of_healing_heal(combatant, max_hit_points)` sets
  `combatant.hit_points = max_hit_points` outright. `Combatant` has
  only a single `hit_points` field (the current value) with no
  separate "starting/max" field to heal back up to -- the same gap
  Troll regeneration's own Phase 155 addendum already flagged for the
  identical reason -- so the caller supplies the combatant's own
  known max explicitly (`CHARACTER_HIT_POINTS` for a normal character,
  or a monster's own stat-block total), rather than this module
  guessing at or silently adding a new persistent field.
- **"Half as likely to be disrupted... as other spells."** A direct,
  spell-specific override of `spell_disruption_chance()`'s own Phase
  179 formula (20% cumulative per hit landed, capped at 95%) --
  `spell_disruption_chance()`/`resolve_spell_disruption()` now both
  take an optional `chance_per_hit` keyword (defaulting to
  `SPELL_DISRUPTION_CHANCE_PER_HIT`, so every existing caller is
  unaffected), and `words_of_healing_disruption_chance()`/`resolve_
  words_of_healing_disruption()` call through with
  `chance_per_hit=SPELL_DISRUPTION_CHANCE_PER_HIT *
  WORDS_OF_HEALING_DISRUPTION_CHANCE_MULTIPLIER` (0.5) -- half the
  per-hit rate, same 95% cap, rather than halving the already-computed
  final chance (which would cap differently at high hit counts).

**Wired into `turn/search_execution.py`'s combat resolution as of
Phase 289** (`_resolve_cast_tactic()`'s own `Spell.HEAL` branch -- the
last of this module's 16 documented Personal-Combat spells to get real
dispatch there; every other spell above already had it since Phase
209-238). Self-only, no target interaction: heals the caster outright
once the same secret-spell skill-5+ eligibility gate every other secret
spell already uses is passed and the cast succeeds. Its own halved
disruption rate (`words_of_healing_disruption_chance()`) stays unused
by any real caller -- `spell_disruption_chance()` itself is still never
rolled anywhere in `turn/search_execution.py`'s own tactic walk (see
that module's own Phase 289 addendum for precisely why: it needs a
round-based combat engine this project still doesn't have, not a small
addition).

**Phase 202 addendum -- Gate Demon [GD], tied to Ability.NECROMANCY,
project-original (user-supplied), the second Necromancy secret spell
and the twelfth Personal-Combat spell overall -- confirmed by the user
to be structurally similar to Mirror-Image [MI] (Phase 187), and
confirmed against real worked examples in this project's own sample
turn reports (`SE3__T10.K1`, `SE3__T11.K1`).** Quoted in full: "By the
dark power of this spell, an extra-dimensional gate is opened to the
nether worlds, from where a demon is summoned to fight in place of the
spellcaster. The caster has no control over what type of demon will
appear. If the Demon wins, it will return to the Abyss from whence it
came. If it loses, the caster must continue the fight at the current
combat range. If another Mirror Image or Gate Demon spell is cast
against it, both spells will be nullified. A Demon may refuse to fight
an opponent of Evil to Undead alignment (50% chance)." The demon roster
is the same seven Anti-Holy species `models/monster.py
HAND_OF_DEATH_ANTI_HOLY_MONSTERS` (Phase 190) already enumerates
(Balrog Demon, Marilith Demon, Succubus, Rakshasha, Ice Devil, Bone
Devil, Imp), picked via `models/monster.py roll_gate_demon_type()`'s
own d100 table (Phase 202 addendum there).

**Two real worked examples, not just the rulebook's own generic
description:**

- `SE3__T10.K1` (refusal case): "I incanted my strange words of magic
  and cast a Gate Demon spell but the Demon refused to fight against an
  opponent of the Chimera's alignment." -- confirms the refusal check
  is against the *opponent's* own alignment (the Chimera's, not the
  demon's), matching the quoted rule's own "an opponent of Evil to
  Undead alignment" wording exactly.
- `SE3__T11.K1` (a full encounter): "Uga-Buga Makumb let fly a Gate
  Demon spell and a flaming portal appeared, through which stepped a
  horrible demon!" -- a Rakshasha, which then fights the entire rest of
  the encounter *as the caster's own stand-in*: it casts Invisibility
  and Mirror-Image Phantasm using its own magic (`models/monster.py
  MONSTER_MAGIC_ABILITIES[Monster.RAKSHASHA] == {Ability.ILLUSION: 3,
  Ability.NECROMANCY: 2}`), duels the Medusa across three combat
  ranges, and finally wins: "The Rakshasha thrust at the Medusa with
  all its strength and walloped the Medusa with 4 damage points. The
  Medusa dropped to the ground, fatally pierced. The Rakshasha
  disappeared to whence the Rakshasha came." ("returns to the Abyss," a
  narrated instance of the rule's own win clause.) The caster, not the
  demon, is credited with the loot afterward ("Uga-Buga Makumb sacked
  the treasure of the Medusa") -- the demon fights *in place of* the
  caster, but the caster remains the effective combatant of record.

**What this phase actually models, the same "clean, testable
primitives, not the orchestration engine" scope every Personal-Combat
spell above uses:**

1. **The demon-type roll** -- `models/monster.py
   roll_gate_demon_type()`, not duplicated here (see that module's own
   Phase 202 addendum).
2. **The 50% refusal roll**: `GATE_DEMON_REFUSAL_CHANCE = 0.5` and
   `resolve_gate_demon_refusal(rng)` -- a flat, unconditional coin
   flip, no skill-level scaling (so `PERSONAL_COMBAT_SPELL_LEVEL_CAP`
   doesn't apply). **The opponent's own alignment eligibility check is
   the caller's job, not this function's** -- this module imports
   nothing from `models.alignment` by design (every other spell here
   keeps the same "caller supplies the otherwise-unavailable
   precondition as a bool" pattern, e.g. Holy Symbol's own
   `target_is_undead_or_anti_holy`). The real-worked-example match
   above confirms "Evil to Undead" is `models/alignment.py
   ALIGNMENT_ORDINAL`'s own inclusive ordinal range 5-7 (`Alignment.
   EVIL`, `Alignment.ANTI_HOLY`, `Alignment.UNDEAD`) -- computed via
   ordinals, never `tuple(Alignment)`'s own declaration order, per that
   module's own documented Gate-Angel-adjacent warning about the two
   orders diverging.

**Confirmed facts, not modeled** (same category as Mirror-Image's own
"double dissipation" and Charm's own "Undead-King Seduzione"):
`GATE_DEMON_WINNER_RETURNS_TO_ABYSS = True`, `GATE_DEMON_LOSS_CASTER_
RESUMES_FIGHT_AT_CURRENT_RANGE = True` (the *exact same* "3a" outcome
Mirror-Image's own losing-illusion branch already describes -- "the
caster must continue the fight at the current combat range," word for
word), and `GATE_DEMON_NULLIFIED_BY_SIMULTANEOUS_MIRROR_IMAGE_OR_GATE_
DEMON = True` (Mirror-Image's own "double dissipation" rule, extended
to a Gate-Demon-vs-Gate-Demon or Gate-Demon-vs-Mirror-Image pairing).

**Building the demon's own real `Combatant` is confirmed but not
attempted here either** -- the worked example above shows a summoned
demon fights with its own full stat block (melee, and its own
`MONSTER_MAGIC_ABILITIES`-driven spellcasting), the same "clone a
`Combatant` from `models/monster.py MONSTER_COMBAT_STATS`, rolling
`hit_points` from its own `hit_points_range`" pattern `turn/
search_execution.py`'s own guardian-monster construction already
established (inline there, not extracted into a shared helper) -- no
new reusable function is added here since, like every Personal-Combat
spell above, nothing yet consumes it.

**Wired into `turn/search_execution.py`'s combat resolution as of
Phase 237** (`_resolve_cast_tactic()`'s own `Spell.GATE_DEMON` branch):
the demon's own `Combatant` is built there, using this exact "clone
from `MONSTER_COMBAT_STATS`, roll `hit_points`" pattern. The demon's own
spellcasting stays out of scope -- it fights Melee only, the same
"mixed tactics aren't modeled" limit `resolve_melee_duel()` already
carries for every other duel in this project.

**Phase 203 addendum -- Lava Pool [LP], tied to Ability.ELEMENTAL,
project-original (user-supplied), the first Elemental secret spell and
the thirteenth Personal-Combat spell overall.** Quoted in full: "The
'Lava Pool of Fiery Death' spell enables the Elemental Mage to call
upon the elemental spirits of Fire and Earth to cause the magma
beneath the earth's surface to rise up and break apart the earth
beneath the victim, who is sucked into a fiery whirlpool of death and
sucked down into the very bowels of the earth. The spell won't work
against flying, underwater, ghostly or anti-holy monsters, and there
is usually a chance to escape it (from 5% to 60%)." The user's own
paraphrase of the escape-chance range was cross-checked against this
project's own sample turn reports and found in `SE3__T9.K6` with the
*exact* two percentages the rulebook itself quotes, in context (the
level-6 Elemental Magic Advanced-Ability grant announcement): "there is
usually a chance to escape it (30% chance for medium-speed opponents,
60% for fast opponents)." That real source, not the user's own rounder
paraphrase, is what `LAVA_POOL_ESCAPE_CHANCE` below transcribes.

**The immune-species set is not new this phase** -- `models/
advanced_ability.py LAVA_POOL_IMMUNE_MONSTERS` (29 species: 12 flying,
5 underwater, 8 anti-holy, 4 ghostly) already existed from an earlier
phase, pre-transcribed verbatim from the same rule text before this
spell's mechanic was buildable, and matches the user's own list in
this phase's request name-for-name. This module still imports nothing
from it (same "caller supplies the otherwise-unavailable precondition
as a bool" pattern as Holy Symbol/Gate Demon above) -- checking
`target_is_immune` against that set is the caller's job.

**What `SE3__T9.K6`'s own real source text does *not* state: a
Slow-speed percentage.** Only "medium-speed" (30%) and "fast" (60%)
are quoted; Slow is never mentioned at all, in either this project's
sample text or the user's own paraphrase. `LAVA_POOL_ESCAPE_CHANCE`
below deliberately models Slow as `0.0` -- **an inference, not a
direct quote**: the source text's own framing ("there is usually a
chance to escape it") introduces an escape chance only for the two
speed tiers it goes on to name, so a Slow opponent (the one tier the
text is silent on) is read as having none. This is flagged explicitly
rather than left to look like a third sourced data point.

**What this phase actually models:**

1. `LAVA_POOL_ESCAPE_CHANCE: dict[MonsterSpeed, float]` and
   `lava_pool_escape_chance(speed)`/`resolve_lava_pool_escape(speed,
   rng)` -- the victim's own speed-keyed escape roll, no skill-level
   scaling on the caster's side (so `PERSONAL_COMBAT_SPELL_LEVEL_CAP`
   doesn't apply here either -- the rulebook ties this chance to the
   *victim's* speed, not the caster's own skill level, unlike every
   scaled spell above).
2. `LAVA_POOL_KILLS_INSTANTLY = True` -- "Instant Death if successful"
   (this spell's own one-line Advanced-Ability summary, `models/
   advanced_ability.py ADVANCED_ABILITY_TAGLINE`), recorded as a
   confirmed fact: a failed escape roll is a full, immediate kill, not
   a damage roll of any kind -- there is no `LAVA_POOL_DAMAGE_*`
   constant to invent.

**Wired into `turn/search_execution.py`'s combat resolution as of
Phase 237** (`_resolve_cast_tactic()`'s own `Spell.LAVA_POOL` branch).
A monster target's speed comes straight from `MONSTER_COMBAT_STATS`; a
leader target has no sourced speed of its own, so it defaults to
`MonsterSpeed.MEDIUM` -- the same tier this module's own [5.6] Flee
quote above already groups "other characters" into ("medium-speed
monsters or other characters is a 50-50 proposition").

**Phase 205 addendum -- Augur Combat [AC], tied to Ability.PSYCHIC,
project-original (user-supplied), the first Psychic secret spell and
the fourteenth Personal-Combat spell overall.** Quoted in full: "The
Psychic Mage performs a powerful augury (forecast), whereby he divines
the probable outcome of the combat. The computer will estimate the
percentage chance of victory, if combat were to occur. If the plan
following the spell is a combat-oriented plan, then if the chances are
too low for the character's courage, he will shirk combat (Coward 80%,
Cautious 60%, Brave 40%, Berserk 20%). Any encounter plan can be stated
after casting this spell. Usually this spell should be the first
tactic ordered, when it won't cost you a combat round; if it comes
later, then the result will be an attempt to flee." The user's own
follow-up clarification (Italian original): "Praticamente il programma
simula la battaglia in maniera silenziosa poi se il risultato vede
l'eroe che lancia l'incantesimo perdere (e quindi morire) questo può
non partecipare allo scontro secondo le percentuali date" -- confirming
the "estimate" is not a number shown to the player but a binary
internal outcome from a silent simulation: only a *simulated loss*
triggers the courage-gated shirk roll at all; a simulated win never
does.

**What this phase actually models:**

1. `AUGUR_COMBAT_SHIRK_CHANCE: dict[Temper, float]` (Coward 80%,
   Cautious 60%, Brave 40%, Berserk 20%, `models/temper.py`'s own
   `Temper` enum, Phase 82) and `augur_combat_shirk_chance(temper)`/
   `resolve_augur_combat_shirk(temper, rng)` -- the courage-gated roll
   itself, monotonically decreasing with `Temper`'s own ordinal
   (`COWARDLY=0` highest shirk chance, `BERSERK=3` lowest), no skill-
   level scaling (so `PERSONAL_COMBAT_SPELL_LEVEL_CAP` doesn't apply):
   the rulebook ties this chance to the caster's *Temper*, not to
   Psychic skill level.
2. `resolve_augur_combat(would_lose_simulated_combat, temper, rng)` --
   the composed effect: returns `False` immediately (never shirks)
   when the caller-supplied simulated outcome is a win, otherwise rolls
   `resolve_augur_combat_shirk`. **The silent battle simulation itself
   is the caller's job, not this function's** -- this project already
   has real combat resolvers (`resolve_melee_duel`, `turn/
   battle_orchestrator.py fight_battle`), but "simulate the probable
   outcome of the combat" names no specific one of them (a single
   personal duel? a full army battle? how many rounds?), and there is
   no Cast-tactic orchestration engine anywhere in this project to make
   that choice from real plan/state data -- the same "caller supplies
   the otherwise-unavailable precondition" pattern every spell above
   uses (e.g. Gate Demon's own opponent-alignment check), just for a
   richer precondition than a single boolean fact about the world.
3. **The "first tactic in the plan" position rule is a confirmed fact,
   not modeled**: `AUGUR_COMBAT_FREE_WHEN_CAST_FIRST = True` records
   "when it won't cost you a combat round," and
   `AUGUR_COMBAT_ACTS_AS_FLEE_WHEN_CAST_LATER = True` records "the
   result will be an attempt to flee" otherwise. Both require knowing
   this cast's own position within a Special Encounter Plan's tactic
   list (`models/monster_encounter_plan.py`) -- the same already-
   confirmed gap `turn/search_execution.py`'s own docstring flags for
   every `CAST` entry in a guardian's plan ("no personal-combat
   spell-effect engine exists yet for any of the... spells these plans
   reference").

**Wired into `turn/search_execution.py`'s combat resolution as of
Phase 238** (`_resolve_cast_tactic()`'s own `Spell.AUGUR_COMBAT`
branch, threaded a new `is_first_tactic` parameter to answer point 3
above from real plan data). The "silent battle simulation" itself is
one throwaway `resolve_melee_duel()` call on cloned combatants,
discarded after reading only its winner -- reusing the real mechanic
rather than inventing a separate estimator. A caster with no recorded
`LeaderState.temper` skips the courage-gated shirk roll entirely (no
data, no effect, the same convention every other spell above uses for
an unresolvable precondition); a monster caster is a documented
no-effect, since Augur Combat never appears in any real
`monster_encounter_plan.py` species plan and monsters have no Temper
to shirk with.

**Phase 208 addendum -- Illusory Hero [IH], tied to Ability.ILLUSION,
project-original (user-supplied), the second and last Illusion secret
spell (Illusory Fog, Phase 207, was the first) and the last of all ten
secret spells (25-34) -- Personal-Combat, explicitly "similar to
Mirror-Image Phantasm."** Quoted in full: "By the wondrous magic power
of this spell, the Illusionist creates an image of whatever Valhalla
hero is currently in the world, to fight in his place. It is similar
to 'Mirror-Image Phantasm', except that 15% is subtracted from the
chance to disbelieve, and the illusory hero will usually not turn on
its master if the illusion wins (unless the alignments of the illusion
and the spellcaster are implacably hostile, for example Good versus
Evil)."

**What this phase actually models:**

1. `ILLUSORY_HERO_DISBELIEF_REDUCTION = 0.15` and
   `illusory_hero_disbelief_chance(base_chance, caster_skill_level)`/
   `resolve_illusory_hero_disbelief(base_chance, caster_skill_level,
   rng)` -- reuse `mirror_image_disbelief_chance()`'s own formula
   verbatim (same `MIRROR_IMAGE_DISBELIEF_BASE_CHANCE` table, same
   per-level reduction) and then subtract one further flat 15
   percentage points, clamped to [0%, 100%] -- "except that 15% is
   subtracted from the chance to disbelieve" reads as a modifier on top
   of Mirror-Image's own already-computed chance, not a replacement
   formula, so this module deliberately calls through to the existing
   function rather than duplicating its table.
2. `ILLUSORY_HERO_TURNS_ON_MASTER_BY_DEFAULT = False` -- "will usually
   not turn on its master if the illusion wins" inverts Mirror-Image's
   own unconditional Stage-2 "the illusion then turns on the caster
   himself" rule (this module's own Mirror-Image section above). The
   "unless... implacably hostile" exception (only one worked example
   given, "Good versus Evil") is recorded as a confirmed exception, not
   modeled as a general alignment-hostility classifier: `models/
   alignment.py`'s own `Alignment`/`ALIGNMENT_ORDINAL` has no existing
   "implacably hostile pair" table to draw on, and inventing one from a
   single example would be guessing the boundary (is Good-vs-Anti-Holy
   "implacably hostile" too? Neutral-vs-Evil?) rather than transcribing
   a sourced rule.
3. **"Whatever Valhalla hero is currently in the world" is a confirmed
   fact, not a lookup this phase performs.** This project's own VALHALLA
   subsystem (Phases 194-199) already establishes that at most one
   visiting hero exists at a time, always as `LeaderState(leader_id=
   models.valhalla.VALHALLA_VISITOR_LEADER_ID)` (199) once spawned by
   `turn/valhalla_execution.py finalize_gate_angel_visit()` -- so "the"
   current Valhalla hero, when one exists, is `state.leaders.get(199)`.
   Building the illusion's own `Combatant` from that hero's stats is
   the same "clone a `Combatant` from a real stat source" pattern this
   module already leaves unbuilt for Gate Demon's own summoned monster
   (Phase 202 addendum) -- no orchestration engine exists yet to
   consume either clone.
4. **The actual duel outcome tree is not modeled**, the same "clean,
   testable primitives only" boundary as Mirror-Image's own three-stage
   outcome tree above (disbelief -> duel -> possible Stage-2 duel) --
   this spell only changes two of Mirror-Image's own numeric inputs
   (the disbelief reduction and the master-disbelief precondition), it
   doesn't add a new engine to execute.

**Not wired into `turn/search_execution.py`'s combat resolution this
phase either**, same reason as every other Personal-Combat spell
above.

**Phase 284 addendum -- the Temper Table's own melee mechanics ("Il
Temperamento non influisce sul combattimento Melee", closed per the
user's own explicit request).** `Regolamento AK.txt`'s own "TABELLA DEI
TEMPERAMENTI", quoted in full (only the melee-relevant columns; flee
probability and encounter-refusal are a separate, still-unwired
mechanic -- see below):

    Berserk    Furia, Intimidazione
    Coraggioso Slancio
    Cauto      Schivare
    Codardo    Implorare pietà (not melee -- a death-avoidance roll)

    FURIA il Berserk non avverte realmente i colpi ricevuti e questa sua
    forza psicologica gli vale da 1 a 4 Punti Ferita supplementari.
    INTIMIDAZIONE gli avversari sono atterriti e hanno minori probabilità
    di colpire nel combattimento corpo a corpo (Coraggioso -5%, Cauto
    -10%, Codardo -15%).
    SLANCIO chi possiede questa caratteristica... Le sue probabilità di
    colpire aumentano del 10%.
    SCHIVARE il personaggio Cauto è un esperto nel parare, quindi i suoi
    avversari hanno un -10% di probabilità di colpire.

Four real, sourced mechanics, all specific to Melee (Fire Arrow's own
hit chance is governed solely by Archery skill, [5.2] -- the Temper
Table is never invoked there):
1. **Furia (Berserk)** -- `BERSERK_FURY_BONUS_HIT_POINTS_RANGE = (1, 4)`,
   `berserk_fury_bonus_hit_points(rng)`. Added once to a Berserk
   combatant's own starting `hit_points`, applied the first (and only)
   time `resolve_melee_duel()` runs for that combatant -- see that
   function's own docstring for why this is the one safe, unambiguous
   "start of melee" moment even when Fire Arrow shots came first in the
   same encounter (`resolve_encounter_combat()`'s SHOOT-then-fall-
   through-to-MELEE case never calls `resolve_melee_duel()` more than
   once on the same pair of `Combatant`s, so there's no double-
   application risk to guard against).
2. **Intimidazione (Berserk)** -- `BERSERK_INTIMIDATION_HIT_CHANCE_
   REDUCTION: dict[Temper, float]` (Brave 5%, Cautious 10%, Cowardly
   15%; Berserk itself is never listed -- one Berserk facing another
   isn't intimidated, a confirmed omission, not a guess). Reduces the
   *opponent's* chance to land a hit on the Berserk -- modeled as a
   multiplier on the Berserk's own `defensive_hit_multiplier`, the
   exact same field/convention Holy Symbol's/Invisibility's own
   defensive buffs already established (Phase 209) -- keyed by the
   *opponent's* own Temper, not the Berserk's.
3. **Slancio (Brave)** -- `BRAVE_MOMENTUM_HIT_CHANCE_BONUS = 0.10`, a
   +10% multiplier on the Brave combatant's own chance to land a hit.
   This is the first *attacker*-side hit-chance modifier this module
   has needed -- every prior one (Holy Symbol, Invisibility) was
   defender-side -- so `Combatant` gains a new `offensive_hit_
   multiplier: float = 1.0` field, mirrored on `defensive_hit_
   multiplier`'s own shape, and `resolve_melee_duel()`'s own
   `hit_chance_multiplier` is now `attacker.offensive_hit_multiplier *
   defender.defensive_hit_multiplier` (defaults to 1.0 for both, so
   every pre-Phase-284 caller is unaffected).
4. **Schivare (Cautious)** -- `CAUTIOUS_DODGE_HIT_CHANCE_REDUCTION =
   0.10`, folded into the Cautious combatant's own `defensive_hit_
   multiplier` the same way Intimidazione is, but flat (no opponent-
   Temper dependency -- the rulebook's own text names none for this
   one).

All four multiplicative on the base 50% Melee hit chance, the same
convention `holy_symbol_hit_chance()`'s own worked example already
established (a stated "-10%" reads as `base * (1 - 0.10)`, not
`base - 10 percentage points`) -- kept consistent across every hit-
chance modifier in this module rather than mixing conventions.

**`Combatant.temper: Temper | None = None`** (new field) is how a
caller supplies each side's own Temper -- `None` (every monster
combatant, and any leader with no recorded `LeaderState.temper`) is a
documented no-effect, the same permissive-missing-data convention this
project uses everywhere else (e.g. `druidic_shortfall_for()`'s own
`leader_race is None` case). Threaded through this project's five
duplicated `_leader_combatant()`/`_commander_combatant()` helpers
(`turn/challenge_execution.py`, `turn/patrol_execution.py`, `turn/
pursue_execution.py`, `turn/search_execution.py`, `turn/
battle_orchestrator.py`) via `temper=leader.temper`, each a one-line
addition to an existing lookup -- the data was already on `LeaderState`
(Phase 82/139), only the wiring was missing.

**Deliberately NOT modeled this phase** (a different rulebook mechanic
from "affects melee," even though it shares the same Temper Table):
flee probability/refusal-to-Meet (Berserk never/never, Brave "when the
odds look bad and mortal-blow risk is high"/never, Cautious "when
mortal-blow risk is significant"/1-50%, Cowardly "when death is
possible"/51-100%, a King of either of the last two never refuses) and
Cowardly's own "Implorare pietà" (beg for mercy, ~50% success, better
against Good-aligned opponents) death-avoidance roll -- both are
decision/tactic-selection mechanics for `turn/search_execution.py`'s
own tactic walk, not melee hit-chance math, and the Cautious flee bonus
half of this ("(NOVITA') I personaggi Cauti hanno il 30% in più di
possibilità di fuggire") was already flagged and deliberately deferred
separately (this module's own "mixed-tactic range transitions" bullet
above cross-references it). A natural, distinct follow-up phase.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum

from ak_engine.models.alignment import ALIGNMENT_ORDINAL, Alignment
from ak_engine.models.enums import Ability, Maneuver, Spell
from ak_engine.models.game_state import GameState
from ak_engine.models.item import ItemInstance
from ak_engine.models.monster import (
    MONSTER_INTELLIGENCE_ORDINAL,
    MONSTER_RUNTIME_PROFILE,
    Monster,
    MonsterIntelligence,
    MonsterSpeed,
)
from ak_engine.models.temper import Temper

# [5.0]: "In combat, all characters have 10 hit points. Monsters may
# have anywhere from 7 to 50 hit points." -- this module's own
# Combatant.hit_points defaults to the character value; a monster
# combatant supplies its own value explicitly.
CHARACTER_HIT_POINTS = 10

# [5.3] Melee: flat 50% base chance, 1-6 damage -- not skill-scaled.
MELEE_HIT_CHANCE = 0.50
MELEE_DAMAGE_RANGE = (1, 6)

# [Tabella dei Temperamenti] ("Temper Table"), Regolamento AK.txt -- see
# module docstring's own Phase 284 addendum for the full quoted source
# and the four melee-specific mechanics these back.
BERSERK_FURY_BONUS_HIT_POINTS_RANGE = (1, 4)  # "Furia"
BERSERK_INTIMIDATION_HIT_CHANCE_REDUCTION: dict[Temper, float] = {  # "Intimidazione"
    Temper.BRAVE: 0.05,
    Temper.CAUTIOUS: 0.10,
    Temper.COWARDLY: 0.15,
}
BRAVE_MOMENTUM_HIT_CHANCE_BONUS = 0.10  # "Slancio"
CAUTIOUS_DODGE_HIT_CHANCE_REDUCTION = 0.10  # "Schivare"

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


# Rulebook [5.1] (RULES.AK, `C:\Users\Andrea\Desktop\Gioco\HostAK\MS\
# RULES.AK`, confirmed identically in `ADDEND.AK`/`Regolamento AK.txt`'s
# own translation) -- **corrects this module's own Phase 179 addendum**,
# whose "20% cumulative per hit" formula was a paraphrase that doesn't
# match the real source text once located and read directly (Phase 292).
# Quoted in full: "In combat, whenever a character attempting to cast a
# spell takes damage or is stunned, the spell is checked for disruption.
# If it is disrupted, the caster loses a turn. For example, 3 hit points
# will disrupt your spell 50% of the time, while a missed swing will
# disrupt you 30% of the time because you may lose your spell-
# concentration while evading the blow." Two distinct triggers, two
# distinct formulas -- not one "per hit" count:
#
# 1. **Damage taken**: scales with the actual damage dealt, not a flat
#    per-hit rate. Only one worked data point is given (3 points -> 50%)
#    -- **confirmed directly by the user via AskUserQuestion** as a
#    straight linear rate, `50% / 3 ≈ 16.67%` per damage point, capped
#    at 95% (the same universal spell-success cap `turn/cast_execution.
#    py ACTION_SPELL_CHANCE_CAP`/this project's own `PERSONAL_COMBAT_
#    SPELL_CAST_CHANCE_CAP` already use elsewhere, reused here as the
#    same real ceiling rather than a fresh guess).
# 2. **A missed/dodged attack**: a flat 30%, independent of damage
#    (there was none) -- "you may lose concentration while evading the
#    blow" is a distinct mechanism, not a zero-damage case of formula 1.
#
# **"Or is stunned" is a confirmed, real, third trigger with no example
# given anywhere in the source** -- deliberately left unquantified
# rather than guessed. In this project's own current combat model it
# never actually applies to the caster this module's round engine
# checks disruption for: a caster's own opponent has no CAST tactic of
# their own to stun them with (see `turn/challenge_execution.py`'s own
# Phase 292 addendum for the full "target never casts" scoping this
# round engine relies on), so the case is structurally unreachable
# today, not silently ignored.
SPELL_DISRUPTION_CHANCE_PER_DAMAGE_POINT = 0.50 / 3  # "3 hit points... 50%"
SPELL_DISRUPTION_MISSED_ATTACK_CHANCE = 0.30  # "a missed swing... 30%"
SPELL_DISRUPTION_CHANCE_CAP = 0.95


def spell_disruption_chance(
    damage_points: int, *, chance_per_point: float = SPELL_DISRUPTION_CHANCE_PER_DAMAGE_POINT
) -> float:
    """The chance a spellcast attempt fails this round because the caster
    took ``damage_points`` of damage before attempting the cast --
    linear in damage, capped at 95%. See the module-level constants just
    above for the full sourced formula and why it replaces the earlier
    "20% cumulative per hit" version.

    ``chance_per_point`` defaults to ``SPELL_DISRUPTION_CHANCE_PER_
    DAMAGE_POINT`` (every existing caller unaffected); Words of
    Healing's own halved rate (module docstring's Phase 200 addendum)
    overrides it via ``words_of_healing_disruption_chance()`` rather
    than duplicating this formula.
    """

    return min(damage_points * chance_per_point, SPELL_DISRUPTION_CHANCE_CAP)


def resolve_spell_disruption(
    damage_points: int, rng: random.Random, *, chance_per_point: float = SPELL_DISRUPTION_CHANCE_PER_DAMAGE_POINT
) -> bool:
    """Rolls whether a spellcast attempt is disrupted this round because
    the caster took damage -- see ``spell_disruption_chance()``'s own
    docstring for the formula. Returns True if disrupted (the cast
    fails, the round is lost).

    With zero damage taken this round, the chance is exactly 0% -- this
    returns False directly without consuming a roll, the same no-roll-
    when-the-outcome-is-fixed convention ``models/monster.py roll_
    monster_alignment()`` (Phase 176) already established. A missed
    attack (no damage, but still an attack) has its own separate,
    non-zero chance -- see ``resolve_spell_disruption_from_missed_
    attack()``, not this function.
    """

    if damage_points <= 0:
        return False
    return rng.random() < spell_disruption_chance(damage_points, chance_per_point=chance_per_point)


def spell_disruption_chance_from_missed_attack(
    *, chance: float = SPELL_DISRUPTION_MISSED_ATTACK_CHANCE
) -> float:
    """The flat disruption chance when the caster was attacked but the
    attack missed (or was dodged) -- "you may lose your spell-
    concentration while evading the blow." Not damage-scaled, since no
    damage was dealt; see the module-level constants above for the full
    sourced formula.
    """

    return chance


def resolve_spell_disruption_from_missed_attack(
    rng: random.Random, *, chance: float = SPELL_DISRUPTION_MISSED_ATTACK_CHANCE
) -> bool:
    """Rolls whether a spellcast attempt is disrupted this round because
    an attack against the caster missed -- see
    ``spell_disruption_chance_from_missed_attack()``. Returns True if
    disrupted.
    """

    return rng.random() < spell_disruption_chance_from_missed_attack(chance=chance)


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


def blocks_cast_and_archery(*, target_is_immune: bool = False) -> bool:
    """Spiritwrack's own "the victim cannot cast spells nor shoot with a
    bow" effect (Phase 182). Always True unless ``target_is_immune`` (an
    Undead or Mechanical target -- see ``models/monster.py SPIRITWRACK_
    UNDEAD_MONSTERS``/``SPIRITWRACK_MECHANICAL_MONSTERS``), in which case
    the spell has no effect at all. Deliberately does **not** take an
    Animal-Intelligence flag: the user confirmed only the numeric Melee
    damage reduction is halved against those targets, not this block
    (module docstring's Phase 182 addendum). Renamed from
    ``spiritwrack_blocks_cast_and_archery`` in Phase 190, when Hand of
    Death was confirmed to share this exact same victim effect,
    word for word.
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


# Illusory Hero [IH], module docstring's own Phase 208 addendum -- tied
# to Ability.ILLUSION. "Similar to Mirror-Image Phantasm" -- reuses that
# spell's own disbelief-chance formula/table rather than duplicating it.
ILLUSORY_HERO_DISBELIEF_REDUCTION = 0.15
ILLUSORY_HERO_TURNS_ON_MASTER_BY_DEFAULT = False


def illusory_hero_disbelief_chance(base_chance: float, caster_skill_level: int) -> float:
    """"similar to Mirror-Image Phantasm, except that 15% is subtracted from
    the chance to disbelieve." Calls through to `mirror_image_disbelief_
    chance()` for the base Mirror-Image formula, then subtracts one
    further flat `ILLUSORY_HERO_DISBELIEF_REDUCTION`, clamped to [0%,
    100%].
    """

    return max(0.0, min(1.0, mirror_image_disbelief_chance(base_chance, caster_skill_level) - ILLUSORY_HERO_DISBELIEF_REDUCTION))


def resolve_illusory_hero_disbelief(base_chance: float, caster_skill_level: int, rng: random.Random) -> bool:
    """Rolls whether the illusory hero is disbelieved -- see
    ``illusory_hero_disbelief_chance()``'s own docstring for the
    formula. Returns True if disbelieved. No roll is consumed when the
    chance is already fixed at 0% or 100%, the same convention
    ``resolve_mirror_image_disbelief()`` established.
    """

    chance = illusory_hero_disbelief_chance(base_chance, caster_skill_level)
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


# Hand of Death [HA], module docstring's own Phase 190 addendum --
# project-original, user-supplied, the first Necromancy Personal-Combat
# spell. The caster's own three self-imposed constraints while
# channeling -- confirmed facts, no consuming combat loop yet.
HAND_OF_DEATH_BLOCKS_CASTER_OTHER_CASTS = True
HAND_OF_DEATH_BLOCKS_CASTER_MELEE_ATTACK = True
HAND_OF_DEATH_ENDS_WHEN_CASTER_IS_HIT = True

# "1 punto danno più ½ punto per livello in magia nera" -- no stated
# cap this time (unlike Holy Symbol/Spiritwrack/Fireball), so applied
# uncapped, same as Charm/Psychic Blast/Telekinetic Storm/Invisibility.
HAND_OF_DEATH_BASE_DAMAGE = 1
HAND_OF_DEATH_DAMAGE_PER_LEVEL = 0.5

# "le sue probabilità di colpire nel combattimento corpo a corpo sono
# dimezzate" -- the victim's own chance of landing a melee hit, halved.
# Not the same direction as Invisibility's own hit-chance halving
# (Phase 186, which halves the chance of *being* hit) -- kept as its
# own spell-prefixed pair rather than merged, see module docstring.
HAND_OF_DEATH_VICTIM_HIT_CHANCE_MULTIPLIER = 0.5


def hand_of_death_caster_melee_defense_skill(necromancy_skill_level: int) -> int:
    """"si difende nel combattimento a corpo a corpo al livello di
    abilità che ha in Necromancy e non a quello che ha in Melee" -- a
    documented identity substitution: the caster's own melee-defense
    initiative (``_acts_first()``'s generic [5.0] rule) uses this
    Necromancy skill level in place of their Melee skill level while
    channeling Hand of Death.
    """

    return necromancy_skill_level


def roll_hand_of_death_damage(skill_level: int, rng: random.Random, *, target_is_immune: bool = False) -> int:
    """Hand of Death's own attack: "1 punto danno più ½ punto per
    livello in magia nera" -- ``HAND_OF_DEATH_BASE_DAMAGE`` (1) plus
    ``HAND_OF_DEATH_DAMAGE_PER_LEVEL`` (0.5) per level, uncapped.
    Uses the same random-rounding-when-fractional convention
    Spiritwrack's own melee damage reduction established (Phase 182):
    a whole exact value resolves without a roll, a 0.5 fractional part
    is a 50/50 coin flip. Returns 0 without a roll when
    ``target_is_immune`` (mechanical, Undead, or anti-holy -- see
    ``models/monster.py HAND_OF_DEATH_IMMUNE_MONSTERS``).
    """

    if target_is_immune:
        return 0

    exact = HAND_OF_DEATH_BASE_DAMAGE + HAND_OF_DEATH_DAMAGE_PER_LEVEL * skill_level
    whole = int(exact)
    fraction = exact - whole
    if fraction <= 0.0:
        return whole
    return whole + 1 if rng.random() < fraction else whole


def hand_of_death_victim_hit_chance(base_hit_chance: float, *, target_is_immune: bool = False) -> float:
    """Halves the victim's own chance of landing a melee hit while
    ensnared by Hand of Death. Returns ``base_hit_chance`` unchanged
    when ``target_is_immune`` -- the spell has no effect at all against
    those targets.
    """

    if target_is_immune:
        return base_hit_chance
    return base_hit_chance * HAND_OF_DEATH_VICTIM_HIT_CHANCE_MULTIPLIER


# Control Undead [CO], module docstring's own Phase 191 addendum --
# project-original, user-supplied, the second and final Necromancy
# Personal-Combat spell. See the module docstring for why no
# success-chance formula is modeled: the source text never gives one.
CONTROL_UNDEAD_SUCCESS_NEUTRALIZES_TARGET = True

# "farà aumentare i suoi Punti Ferita del 50-100%" -- a fraction, not a die.
CONTROL_UNDEAD_FAILURE_HP_INCREASE_RANGE = (0.50, 1.00)


def roll_control_undead_failure_hp_increase(rng: random.Random) -> float:
    """The failure branch's HP-increase fraction: "50-100%". Uses
    ``rng.uniform()`` rather than ``rng.randint()`` -- a percentage, not
    a die roll.
    """

    return rng.uniform(*CONTROL_UNDEAD_FAILURE_HP_INCREASE_RANGE)


def control_undead_failure_new_hit_points(hit_points: int, rng: random.Random) -> int:
    """Applies the failure branch's rage: the victim's hit points
    increase by ``roll_control_undead_failure_hp_increase()``'s own
    fraction, rounded to the nearest whole point.
    """

    increase = roll_control_undead_failure_hp_increase(rng)
    return round(hit_points * (1 + increase))


# Personal-Combat spell cast success chance, module docstring's own
# Phase 192 addendum -- Regolamento AK.txt [3.10], retroactively
# confirmed for all ten Personal-Combat spells.
PERSONAL_COMBAT_SPELL_CAST_BASE_CHANCE = 0.30
PERSONAL_COMBAT_SPELL_CAST_CHANCE_PER_LEVEL = 0.15
PERSONAL_COMBAT_SPELL_CAST_CHANCE_CAP = 0.95

# "I Reami Pagani... un modificatore +10%... fuorché quelli di Magia
# Bianca." Caller decides applicability (see docstring): pass
# ``caster_is_pagan=False`` for White Magic spells regardless of the
# caster's own kingdom.
PERSONAL_COMBAT_PAGAN_MAGE_ORDER_BONUS = 0.10


def personal_combat_spell_cast_chance(skill_level: int, *, caster_is_pagan: bool = False) -> float:
    """"Gli Incantesimi di Combattimento Individuale hanno una
    probabilità di riuscita del 30% più 15% per livello," capped at
    ``PERSONAL_COMBAT_SPELL_CAST_CHANCE_CAP`` (95%). Adds
    ``PERSONAL_COMBAT_PAGAN_MAGE_ORDER_BONUS`` when ``caster_is_pagan``
    -- the caller must already have excluded White Magic spells from
    setting this flag (see module docstring's Phase 192 addendum).
    """

    chance = PERSONAL_COMBAT_SPELL_CAST_BASE_CHANCE + PERSONAL_COMBAT_SPELL_CAST_CHANCE_PER_LEVEL * skill_level
    if caster_is_pagan:
        chance += PERSONAL_COMBAT_PAGAN_MAGE_ORDER_BONUS
    return min(chance, PERSONAL_COMBAT_SPELL_CAST_CHANCE_CAP)


def resolve_personal_combat_spell_cast(skill_level: int, rng: random.Random, *, caster_is_pagan: bool = False) -> bool:
    """Rolls whether a Personal-Combat spell attempt succeeds, using
    ``personal_combat_spell_cast_chance()``'s own formula. Governs all
    ten Personal-Combat spells above uniformly -- this is the missing
    piece Control Undead's own Phase 191 addendum explicitly declined
    to invent, now supplied generically rather than per-spell.
    """

    return rng.random() < personal_combat_spell_cast_chance(skill_level, caster_is_pagan=caster_is_pagan)


# Phase 209 -- the Spell -> Ability mapping for the ten Personal-Combat-only
# spells, sourced directly from `turn/cast_execution.py`'s own docstring
# (lines 48-52): "Holy_Symbol, Spiritwrack, Psychic_Blast, Telek_Storm,
# Invisibility, Mirror_Image, Fireball, Ice_Suspend, Hand_of_Death,
# Control_Undead -- [4.21.4]-[4.21.5], [4.22.4]-[4.22.5], [4.23.4]-[4.23.5],
# [4.24.4]-[4.24.5], [4.25.4]-[4.25.5]" -- five citation blocks of two spells
# each, in the same order as the name list. Cross-referencing each block
# number against `cast_execution.py _SPELL_ABILITY`'s own confirmed entries
# for the *other* spells sharing that same block ([4.21]=Resurrection/
# Part_Sea/Bless/Gate_Angel=WHITE, [4.22]=Charm/Oratory/Clairvoyance/
# Locate_Object=PSYCHIC, [4.23]=Illus_Terrain/Illus_Armies/Hide_Feature/
# Illus_Fog=ILLUSION, [4.24]=Flood/Tornado/Earthquake/Mystic_Winds=ELEMENTAL,
# [4.25]=Kill_Enemy/Plague/Skeletal_Army/Scar_Terrain=NECROMANCY) gives a
# sequential pairing that is both unique and thematically obvious (Holy
# Symbol/Spiritwrack -> White; Psychic Blast/Telekinetic Storm -> Psychic;
# Invisibility/Mirror-Image -> Illusion; Fireball/Ice Suspension ->
# Elemental; Hand of Death/Control Undead -> Necromancy). Mirror-Image and
# Hand of Death are included here for completeness even though
# `turn/search_execution.py`'s own Phase 209 dispatcher doesn't consume them
# yet -- both are deferred to Phase 210 (channeled/illusion sub-loop).
PERSONAL_COMBAT_SPELL_ABILITY: dict[Spell, Ability] = {
    Spell.HOLY_SYMBOL: Ability.WHITE,
    Spell.SPIRITWRACK: Ability.WHITE,
    Spell.PSYCHIC_BLAST: Ability.PSYCHIC,
    Spell.TELEK_STORM: Ability.PSYCHIC,
    Spell.INVISIBILITY: Ability.ILLUSION,
    Spell.MIRROR_IMAGE: Ability.ILLUSION,
    Spell.FIREBALL: Ability.ELEMENTAL,
    Spell.ICE_SUSPEND: Ability.ELEMENTAL,
    Spell.HAND_OF_DEATH: Ability.NECROMANCY,
    Spell.CONTROL_UNDEAD: Ability.NECROMANCY,
}


# Words of Healing [WH], module docstring's own Phase 200 addendum --
# tied to `Ability.WHITE`, granted via `AdvancedAbility.WORDS_OF_
# HEALING_SPELL` (White Magic skill 5+). No skill-level scaling on
# either effect, so `PERSONAL_COMBAT_SPELL_LEVEL_CAP` doesn't apply.
WORDS_OF_HEALING_HEALS_TO_FULL = True
WORDS_OF_HEALING_DISRUPTION_CHANCE_MULTIPLIER = 0.5


def words_of_healing_disruption_chance(damage_points: int) -> float:
    """Words of Healing's own disruption chance when the caster took
    damage -- "half as likely to be disrupted... as other spells": half
    ``SPELL_DISRUPTION_CHANCE_PER_DAMAGE_POINT``, same 95% cap. See
    module docstring's Phase 200 addendum and this module's own Phase
    292 addendum (corrected formula).
    """

    return spell_disruption_chance(
        damage_points,
        chance_per_point=SPELL_DISRUPTION_CHANCE_PER_DAMAGE_POINT * WORDS_OF_HEALING_DISRUPTION_CHANCE_MULTIPLIER,
    )


def resolve_words_of_healing_disruption(damage_points: int, rng: random.Random) -> bool:
    """Rolls Words of Healing's own halved disruption chance for a landed
    hit -- see ``words_of_healing_disruption_chance()``. Same
    no-roll-at-zero-damage shortcut as ``resolve_spell_disruption()``.
    """

    if damage_points <= 0:
        return False
    return rng.random() < words_of_healing_disruption_chance(damage_points)


def words_of_healing_disruption_chance_from_missed_attack() -> float:
    """Words of Healing's own halved disruption chance for a missed/
    dodged attack -- half ``SPELL_DISRUPTION_MISSED_ATTACK_CHANCE``. Same
    halving convention as the damage-taken case above.
    """

    return SPELL_DISRUPTION_MISSED_ATTACK_CHANCE * WORDS_OF_HEALING_DISRUPTION_CHANCE_MULTIPLIER


def resolve_words_of_healing_disruption_from_missed_attack(rng: random.Random) -> bool:
    """Rolls Words of Healing's own halved disruption chance for a missed
    attack -- see ``words_of_healing_disruption_chance_from_missed_
    attack()``.
    """

    return rng.random() < words_of_healing_disruption_chance_from_missed_attack()


def words_of_healing_heal(combatant: "Combatant", max_hit_points: int = CHARACTER_HIT_POINTS) -> None:
    """"The character is completely healed when the Words of Healing are
    spoken, gaining back all lost hit points." Sets ``combatant.hit_points``
    to ``max_hit_points`` outright. ``Combatant`` has no separate "starting/
    max" hit-points field distinct from its current one (the same gap
    Troll regeneration's own Phase 155 addendum already flagged), so the
    caller supplies the combatant's own known max explicitly --
    ``CHARACTER_HIT_POINTS`` for a normal character, or a monster's own
    stat-block total.
    """

    combatant.hit_points = max_hit_points


# Gate Demon [GD], module docstring's own Phase 202 addendum -- tied to
# Ability.NECROMANCY. No skill-level scaling (so PERSONAL_COMBAT_SPELL_
# LEVEL_CAP doesn't apply), matching Charm/Psychic Blast/Telekinetic
# Storm/Invisibility/Words of Healing's own uncapped effects.
GATE_DEMON_REFUSAL_CHANCE = 0.5
GATE_DEMON_WINNER_RETURNS_TO_ABYSS = True
GATE_DEMON_LOSS_CASTER_RESUMES_FIGHT_AT_CURRENT_RANGE = True
GATE_DEMON_NULLIFIED_BY_SIMULTANEOUS_MIRROR_IMAGE_OR_GATE_DEMON = True


def resolve_gate_demon_refusal(rng: random.Random) -> bool:
    """"A Demon may refuse to fight an opponent of Evil to Undead alignment (50%
    chance)." Only call this when the opponent's own alignment is
    eligible -- this module doesn't import ``models.alignment`` (see
    module docstring's own Phase 202 addendum for the confirmed "Evil
    to Undead" ordinal range, ``models/alignment.py ALIGNMENT_ORDINAL``
    5-7), the same "caller supplies the otherwise-unavailable
    precondition" pattern every other spell above uses. Returns True if
    the demon refuses (matching the real worked example in
    ``SE3__T10.K1``: "the Demon refused to fight against an opponent of
    the Chimera's alignment").
    """

    return rng.random() < GATE_DEMON_REFUSAL_CHANCE


# Lava Pool [LP], module docstring's own Phase 203 addendum -- tied to
# Ability.ELEMENTAL. FAST/MEDIUM sourced verbatim from SE3__T9.K6's own
# in-game ability-grant text; SLOW is an inference (0.0), not a direct
# quote -- see the docstring addendum for why. No skill-level scaling
# (the chance is keyed to the *victim's* speed, not the caster's own
# skill), so PERSONAL_COMBAT_SPELL_LEVEL_CAP doesn't apply here either.
LAVA_POOL_ESCAPE_CHANCE: dict[MonsterSpeed, float] = {
    MonsterSpeed.FAST: 0.60,
    MonsterSpeed.MEDIUM: 0.30,
    MonsterSpeed.SLOW: 0.0,
}
LAVA_POOL_KILLS_INSTANTLY = True


def lava_pool_escape_chance(speed: MonsterSpeed) -> float:
    """The victim's own chance to escape a successfully-cast Lava Pool,
    keyed by its ``MonsterSpeed`` tier. See ``LAVA_POOL_ESCAPE_CHANCE``
    above and the module docstring's own Phase 203 addendum for sourcing.
    """

    return LAVA_POOL_ESCAPE_CHANCE[speed]


def resolve_lava_pool_escape(speed: MonsterSpeed, rng: random.Random) -> bool:
    """Returns True if the victim escapes (survives); False means the
    spell kills instantly (``LAVA_POOL_KILLS_INSTANTLY``). Only call this
    once the spell's own cast-success roll has already succeeded and the
    target is confirmed not immune (``models/advanced_ability.py
    LAVA_POOL_IMMUNE_MONSTERS``) -- both are the caller's job, same
    "caller supplies the otherwise-unavailable precondition" pattern
    every other spell above uses.
    """

    return rng.random() < lava_pool_escape_chance(speed)


# Augur Combat [AC], module docstring's own Phase 205 addendum -- tied to
# Ability.PSYCHIC. No skill-level scaling (the chance is keyed to the
# caster's own Temper, not Psychic skill), so PERSONAL_COMBAT_SPELL_
# LEVEL_CAP doesn't apply here either.
AUGUR_COMBAT_SHIRK_CHANCE: dict[Temper, float] = {
    Temper.COWARDLY: 0.80,
    Temper.CAUTIOUS: 0.60,
    Temper.BRAVE: 0.40,
    Temper.BERSERK: 0.20,
}
AUGUR_COMBAT_FREE_WHEN_CAST_FIRST = True
AUGUR_COMBAT_ACTS_AS_FLEE_WHEN_CAST_LATER = True


def augur_combat_shirk_chance(temper: Temper) -> float:
    """The caster's own chance to shirk combat after a simulated loss,
    keyed by its ``Temper``. See ``AUGUR_COMBAT_SHIRK_CHANCE`` above and
    the module docstring's own Phase 205 addendum for sourcing.
    """

    return AUGUR_COMBAT_SHIRK_CHANCE[temper]


def resolve_augur_combat_shirk(temper: Temper, rng: random.Random) -> bool:
    """Returns True if the caster shirks combat. Only call this once a
    silent battle simulation (the caller's own job -- see the module
    docstring's own Phase 205 addendum) has already predicted a loss;
    ``resolve_augur_combat`` below composes that precondition in.
    """

    return rng.random() < augur_combat_shirk_chance(temper)


def resolve_augur_combat(would_lose_simulated_combat: bool, temper: Temper, rng: random.Random) -> bool:
    """"if the chances are too low for the character's courage, he will shirk
    combat" -- only rolls at all when ``would_lose_simulated_combat`` is
    True (the caller's own silent-simulation result); a simulated win
    never shirks. Returns True if the caster shirks combat.
    """

    if not would_lose_simulated_combat:
        return False
    return resolve_augur_combat_shirk(temper, rng)


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
    # Phase 209 -- multiplies the chance an *opponent* lands a hit against
    # this combatant, in either Melee or Fire Arrow. Composed
    # multiplicatively when more than one Personal-Combat spell applies
    # (Holy Symbol's own self-buff, Invisibility's flat halving) -- default
    # 1.0 leaves every pre-Phase-209 caller's behavior unchanged.
    defensive_hit_multiplier: float = 1.0
    # Phase 209 -- subtracted from this combatant's own landed Melee damage
    # (Spiritwrack's effect on its *target*, i.e. set on the victim, not the
    # caster). Default 0 is a no-op for every existing caller.
    melee_damage_dealt_reduction: int = 0
    # Phase 209 -- Spiritwrack's "the victim cannot cast spells nor shoot
    # with a bow" effect. `turn/search_execution.py`'s own CAST/SHOOT
    # handling consults this before letting the affected side act.
    blocked_from_cast_and_archery: bool = False
    # Phase 209 -- free, unanswered Melee swings this combatant has banked
    # from a successful Psychic Blast or Ice Suspension cast, consumed by
    # `turn/search_execution.py` immediately after the CAST tactic resolves.
    bonus_unanswered_attacks: int = 0
    # Phase 284 -- multiplies the chance THIS combatant lands a hit (the
    # attacker-side counterpart to defensive_hit_multiplier above) --
    # Slancio's own +10% for a Brave combatant. Default 1.0 leaves every
    # pre-Phase-284 caller unaffected.
    offensive_hit_multiplier: float = 1.0
    # Phase 284 -- this combatant's own real Temper ([Tabella dei
    # Temperamenti]), if known. `None` (a monster, or a leader with no
    # recorded `LeaderState.temper`) is a documented no-effect -- see
    # module docstring's own Phase 284 addendum.
    temper: Temper | None = None
    # Phase 286 -- set by `turn/search_execution.py` alongside
    # `defensive_hit_multiplier *= INVISIBILITY_HIT_CHANCE_MULTIPLIER`
    # when this combatant casts Invisibility. A separate explicit flag
    # rather than inferring invisibility from the multiplier's own value
    # (fragile once more than one multiplier composes) -- read by that
    # same module's own `effective_flee_chance()` for [5.6]'s "+30%
    # chance to flee" addendum, which `defensive_hit_multiplier` alone
    # can't drive since it isn't a flee-roll input. Default `False`
    # leaves every pre-Phase-286 caller unaffected.
    is_invisible: bool = False


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


def berserk_fury_bonus_hit_points(rng: random.Random) -> int:
    """"Furia": a Berserk combatant's own 1-4 bonus starting Hit Points --
    see module docstring's own Phase 284 addendum.
    """

    return rng.randint(*BERSERK_FURY_BONUS_HIT_POINTS_RANGE)


def apply_temper_melee_setup(a: "Combatant", b: "Combatant", rng: random.Random) -> None:
    """Mutates ``a``/``b`` in place per the Temper Table's own melee-specific
    mechanics (Furia, Intimidazione, Slancio, Schivare) -- see module
    docstring's own Phase 284 addendum for the full quoted source and
    derivation. Reads each combatant's own ``.temper`` field (``None`` is
    a documented no-effect); called once, internally, at the very start
    of ``resolve_melee_duel()`` -- not meant to be called directly by
    other callers.
    """

    for combatant, opponent in ((a, b), (b, a)):
        if combatant.temper is Temper.BERSERK:
            combatant.hit_points += berserk_fury_bonus_hit_points(rng)
            reduction = (
                BERSERK_INTIMIDATION_HIT_CHANCE_REDUCTION.get(opponent.temper)
                if opponent.temper is not None
                else None
            )
            if reduction is not None:
                combatant.defensive_hit_multiplier *= 1.0 - reduction
        elif combatant.temper is Temper.BRAVE:
            combatant.offensive_hit_multiplier *= 1.0 + BRAVE_MOMENTUM_HIT_CHANCE_BONUS
        elif combatant.temper is Temper.CAUTIOUS:
            combatant.defensive_hit_multiplier *= 1.0 - CAUTIOUS_DODGE_HIT_CHANCE_REDUCTION


def roll_melee_attack(
    rng: random.Random, damage_range: tuple[int, int] = MELEE_DAMAGE_RANGE, *, hit_chance_multiplier: float = 1.0
) -> int:
    """Rulebook [5.3]: one Melee swing. Returns damage dealt (0 on a miss).

    ``damage_range`` defaults to the character rule; pass an attacker's
    own ``Combatant.melee_damage_range`` for a species-specific die
    (Phase 132 addendum, module docstring). ``hit_chance_multiplier``
    defaults to 1.0 (every pre-Phase-209 caller unaffected); pass a
    defender's own ``Combatant.defensive_hit_multiplier`` (Phase 209) to
    apply Holy Symbol's/Invisibility's own hit-chance reduction.
    """

    if rng.random() < MELEE_HIT_CHANCE * hit_chance_multiplier:
        return rng.randint(*damage_range)
    return 0


def roll_fire_arrow_attack(
    archery_skill: int,
    rng: random.Random,
    damage_range: tuple[int, int] = FIRE_ARROW_DAMAGE_RANGE,
    *,
    hit_chance_multiplier: float = 1.0,
) -> int:
    """Rulebook [5.2]: one Fire Arrow shot. Returns damage dealt (0 on a miss).

    ``damage_range`` defaults to the character rule; pass an attacker's
    own ``Combatant.missile_damage_range`` for a species-specific die
    (Phase 170 addendum, module docstring). ``hit_chance_multiplier``
    defaults to 1.0 (every pre-Phase-209 caller unaffected); pass a
    defender's own ``Combatant.defensive_hit_multiplier`` (Phase 209) to
    apply Holy Symbol's/Invisibility's own hit-chance reduction.
    """

    if rng.random() < fire_arrow_hit_chance(archery_skill) * hit_chance_multiplier:
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
    populates these; ``resolve_melee_duel()`` has its own analogous
    ``MeleeSwing``/``melee_swings`` log instead (Phase 415).
    """

    shooter: str  # "a" / "b"
    hit: bool
    damage: int


@dataclass(slots=True)
class MeleeSwing:
    """One Melee swing's outcome (Phase 415), in chronological order --
    ``attacker`` is ``"a"``/``"b"``, matching ``EncounterCombatResult.
    winner``'s own convention. ``hit`` reads the *attack roll* itself
    (``roll_melee_attack()``'s own return, before ``melee_damage_dealt_
    reduction`` is subtracted) -- Spiritwrack can floor a real hit's own
    net ``damage`` to 0, so ``damage > 0`` alone can't stand in for
    ``hit`` the way it safely can for Fire Arrow's own default damage
    range. Only ``resolve_melee_duel()``/``resolve_one_melee_round()``
    populate these; every other resolver's own ``melee_swings`` stays
    empty.
    """

    attacker: str  # "a" / "b"
    hit: bool
    damage: int  # net, post-reduction -- 0 on a miss, possibly also 0 on a reduced hit


@dataclass(slots=True)
class EncounterCombatResult:
    winner: str | None  # "a" / "b" / None (both survived -- see each resolver's docstring)
    rounds: int
    # Phase 175: per-shot Fire Arrow detail, for narrating each shot
    # individually (see report/turn_report.py's own Phase 175 addendum).
    # Empty for every Melee duel and for every existing caller before
    # this phase.
    shots: tuple[FireArrowShot, ...] = ()
    # Phase 413: per-round Hand of Death damage, one entry per successful
    # squeeze (the caster's own attack always lands -- no hit/miss flag
    # needed, unlike `shots` above). Always the caster's own side; the
    # victim's own Melee counter-attack that ends the channel is not
    # logged here. Empty for every other resolver. See
    # `resolve_hand_of_death_channel()`'s own Phase 413 addendum and
    # `report/turn_report.py render_squeeze_attack()`.
    squeeze_hits: tuple[int, ...] = ()
    # Phase 415: every Melee swing across every round, in order, for
    # narrating each individually -- the same per-swing-detail role
    # `shots` plays for Fire Arrow. Only `resolve_melee_duel()` (via
    # `resolve_one_melee_round()`) populates this; empty for every other
    # resolver. See `report/turn_report.py render_melee_attack()`'s own
    # Phase 415 addendum.
    melee_swings: tuple[MeleeSwing, ...] = ()


@dataclass(slots=True)
class MeleeRoundOutcome:
    """One Melee round's full outcome (Phase 292 extraction from
    ``resolve_melee_duel``'s own loop body) -- lets a round-based caller
    (``turn/challenge_execution.py``'s own round engine) both step Melee
    one round at a time AND read each side's own per-round damage/miss
    detail, needed to feed ``resolve_spell_disruption``/
    ``resolve_spell_disruption_from_missed_attack`` for a combatant that
    is CASTing while the other side swings at it in Melee range.

    ``a_attacked``/``b_attacked`` is ``False`` when that side never got
    to swing this round (it died to the other side's first strike, per
    initiative). ``damage_dealt_to_a``/``damage_dealt_to_b`` is 0 both
    when the attacker missed AND when the attacker never attacked --
    callers that need to tell those apart use the corresponding
    ``*_attacked`` flag alongside the damage figure.

    ``swings`` (Phase 415) is the same round's own detail again, but in
    chronological attack order and shaped as ``MeleeSwing`` for a
    narration caller (``report/turn_report.py``) that wants to render
    each swing as its own sentence -- the two representations coexist
    because ``damage_dealt_to_a``/``b`` already has real callers
    (``resolve_spell_disruption``) that read it by *side*, not in order.
    """

    result: EncounterCombatResult | None  # set once a combatant's hit points reach 0 this round
    damage_dealt_to_a: int = 0  # b's landed Melee damage against a this round
    damage_dealt_to_b: int = 0  # a's landed Melee damage against b this round
    a_attacked: bool = False
    b_attacked: bool = False
    swings: tuple[MeleeSwing, ...] = ()


def resolve_one_melee_round(
    a: Combatant, b: Combatant, rng: random.Random, *, round_number: int = 1
) -> MeleeRoundOutcome:
    """Rulebook [5.3]: one Melee round only.

    Extracted (Phase 292) from ``resolve_melee_duel``'s own internal
    per-round loop so a round-based caller can interleave Melee rounds
    with other combat ranges (Spell/Bow) instead of only ever running a
    Melee duel to its own atomic conclusion. Consumes RNG in exactly the
    same order ``resolve_melee_duel`` always has, so wrapping this in a
    loop (below) changes no existing caller's behavior.

    Does NOT call ``apply_temper_melee_setup`` -- that is a once-per-
    encounter setup step (Furia/Intimidazione/Slancio/Schivare), left to
    the caller to run exactly once before the first round, not on every
    round.
    """

    skill_a, skill_b = effective_melee_skill(a), effective_melee_skill(b)
    first, second = (a, b) if _acts_first(skill_a, skill_b, rng) else (b, a)
    outcome = MeleeRoundOutcome(result=None)
    swings: list[MeleeSwing] = []
    for attacker, defender in ((first, second), (second, first)):
        if attacker.hit_points <= 0 or defender.hit_points <= 0:
            continue
        raw_damage = roll_melee_attack(
            rng,
            damage_range=attacker.melee_damage_range,
            hit_chance_multiplier=attacker.offensive_hit_multiplier * defender.defensive_hit_multiplier,
        )
        damage = max(0, raw_damage - attacker.melee_damage_dealt_reduction)
        defender.hit_points -= damage
        attacker_side = "a" if attacker is a else "b"
        swings.append(MeleeSwing(attacker=attacker_side, hit=raw_damage > 0, damage=damage))
        if attacker is a:
            outcome.damage_dealt_to_b = damage
            outcome.a_attacked = True
        else:
            outcome.damage_dealt_to_a = damage
            outcome.b_attacked = True
        if defender.hit_points <= 0:
            outcome.result = EncounterCombatResult(winner=("a" if defender is b else "b"), rounds=round_number)
            outcome.swings = tuple(swings)
            return outcome
    _apply_end_of_round_regeneration(a, b)
    outcome.swings = tuple(swings)
    return outcome


def resolve_reactive_melee_swing(attacker: Combatant, defender: Combatant, rng: random.Random) -> int:
    """One one-directional Melee swing (Phase 292) -- ``attacker`` swings at
    ``defender``, who does not swing back this round because it is
    casting instead of fighting. Models rulebook [5.1]'s own "melee
    attacks always take precedence" over a simultaneous cast (module
    docstring's own Phase 179 addendum, quoted in full there): once both
    combatants are at ``CombatRange.MELEE_RANGE`` and the *target* has no
    Encounter Plan of its own (this project's established scoping -- see
    ``turn/challenge_execution.py``'s own module docstring), it is
    assumed to keep swinging Melee every round the caster spends
    casting instead of answering in kind.

    Returns the damage dealt (0 on a miss) so the caller can feed it
    straight into ``resolve_spell_disruption``/``resolve_spell_
    disruption_from_missed_attack`` -- the damage-taken-or-missed-swing
    disruption check this exists to make possible. Mutates ``defender.
    hit_points`` in place; the caller checks for death itself (the same
    convention every other Personal-Combat spell effect in this module
    already follows for its own target/caster hit-point checks).
    """

    damage = roll_melee_attack(
        rng,
        damage_range=attacker.melee_damage_range,
        hit_chance_multiplier=attacker.offensive_hit_multiplier * defender.defensive_hit_multiplier,
    )
    damage = max(0, damage - attacker.melee_damage_dealt_reduction)
    defender.hit_points -= damage
    return damage


def resolve_melee_duel(
    a: Combatant, b: Combatant, rng: random.Random, *, max_rounds: int = 1000, skip_temper_setup: bool = False
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

    Phase 209: each swing consults the *defender's* own
    ``defensive_hit_multiplier`` (Holy Symbol/Invisibility) and the
    *attacker's* own ``melee_damage_dealt_reduction`` (Spiritwrack,
    floored at 0 -- a debuffed attacker can never deal negative damage).
    Both default to a no-op (1.0 / 0), so every pre-Phase-209 caller is
    unaffected.

    Phase 284: ``apply_temper_melee_setup(a, b, rng)`` runs once, first,
    reading each side's own ``.temper`` (Furia/Intimidazione/Slancio/
    Schivare -- see module docstring's own Phase 284 addendum) --
    ``None`` on both is a no-op, so every pre-Phase-284 caller is
    unaffected. Each swing then also consults the *attacker's* own
    ``offensive_hit_multiplier`` (Slancio) alongside the defender's own
    ``defensive_hit_multiplier``.

    Phase 292: now a thin loop over ``resolve_one_melee_round`` -- same
    RNG consumption order, same return value, zero behavior change.

    Phase 297: ``skip_temper_setup`` (default ``False``, every pre-Phase-
    297 caller unaffected) lets a caller that already applied ``a``/``b``'s
    own Temper setup itself -- via a real, direct ``apply_temper_melee_
    setup()`` call, e.g. ``turn/challenge_execution.py``'s/``turn/
    search_execution.py``'s own round-stepping engines (Phase 292/293) --
    skip this function's own internal call, avoiding the real, confirmed
    double-apply bug (found in a dedicated bug-hunt audit) where a
    non-last ``MELEE`` tactic's round-stepping already ran the real setup
    once, and this function's own atomic fallback (the last-tactic path,
    or the exhausted-tactic-list default) ran it again, compounding
    Berserk's own bonus hit points and Cautious'/Slancio's own hit-chance
    multipliers.

    **Phase 415**: the returned ``EncounterCombatResult.melee_swings``
    now carries every swing across every round, in order -- the same
    per-swing-detail role ``shots`` already plays for Fire Arrow, needed
    to feed ``report/turn_report.py render_melee_attack()``. Collected
    by concatenating each round's own ``MeleeRoundOutcome.swings`` (see
    ``resolve_one_melee_round()``'s own Phase 415 addendum); every pre-
    Phase-415 caller is unaffected since nothing previously read this
    field.
    """

    if not skip_temper_setup:
        apply_temper_melee_setup(a, b, rng)
    all_swings: list[MeleeSwing] = []
    for round_number in range(1, max_rounds + 1):
        outcome = resolve_one_melee_round(a, b, rng, round_number=round_number)
        all_swings.extend(outcome.swings)
        if outcome.result is not None:
            outcome.result.melee_swings = tuple(all_swings)
            return outcome.result
    return EncounterCombatResult(winner=None, rounds=max_rounds, melee_swings=tuple(all_swings))


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

    Phase 209: each shot consults the *target's* own
    ``defensive_hit_multiplier`` (Holy Symbol/Invisibility) -- defaults to
    a no-op (1.0), so every pre-Phase-209 caller is unaffected.
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
                damage = roll_fire_arrow_attack(
                    skill_a, rng, damage_range=a.missile_damage_range, hit_chance_multiplier=b.defensive_hit_multiplier
                )
                shots.append(FireArrowShot(shooter="a", hit=damage > 0, damage=damage))
                b.hit_points -= damage
            else:
                if used_b >= shots_b:
                    continue
                used_b += 1
                damage = roll_fire_arrow_attack(
                    skill_b, rng, damage_range=b.missile_damage_range, hit_chance_multiplier=a.defensive_hit_multiplier
                )
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


def resolve_encounter_combat(
    maneuvers: list[Maneuver], a: Combatant, b: Combatant, rng: random.Random
) -> EncounterCombatResult:
    """[5.10]/[5.2]/[3.16]: walk an Encounter Plan's own tactic list in
    order, the same "Fire Arrow first if listed, fall through to Melee
    once its shots exhaust with nobody dead, or once the list runs out"
    rule ``turn/search_execution.py``'s own docstring already establishes
    for Search (Phase 170/178 corrections) -- reused here directly for
    every other Encounter consumer (Challenge, Pursue, Duel) rather than
    re-derived, since [5.10] governs them identically: "All rules listed
    under the Encounter action apply to Pursuit encounters" ([3.16]), and
    a battle Duel is explicitly "given in the Special Encounter Plan
    rules [5.10]" too ([7.1]).

    A ``Maneuver.SHOOT`` entry resolves a Fire Arrow duel first; if it
    ends with nobody dead (shots exhausted, ``winner is None``), the walk
    continues to the next entry. A ``Maneuver.MELEE`` entry always
    resolves the whole encounter on its own (Melee never leaves both
    combatants standing, Phase 48). Any other maneuver in the list is
    skipped, the same "unwired tactic, keep walking" convention Search's
    own tactic walk already uses. If the list is exhausted with nobody
    dead -- including an empty list, e.g. no Encounter Plan data
    available at all -- resolves one Melee duel: "the character
    automatically starts using ME" (module docstring's own Phase 178
    quote, a general Special Encounter Plan rule, not Search-specific),
    and also the one defensible default when there's no plan to read
    from in the first place (``resolve_melee_duel``'s own Phase 48
    reasoning: "no skill prerequisite").

    Both combatants are still assumed to fight with the *same* tactic for
    the whole encounter, same as ``resolve_melee_duel``/``resolve_fire_
    arrow_duel`` individually -- this project has no per-side, mixed-
    tactic range-transition state machine (see this module's own
    "Explicitly out of scope" note above).
    """

    for maneuver in maneuvers:
        if maneuver is Maneuver.SHOOT:
            result = resolve_fire_arrow_duel(a, b, rng)
            if result.winner is not None:
                return result
            continue
        if maneuver is Maneuver.MELEE:
            return resolve_melee_duel(a, b, rng)
    return resolve_melee_duel(a, b, rng)


# Phase 210 addendum -- Hand of Death [HA] and Mirror-Image Phantasm [MI],
# the two Personal-Combat spells Phase 209 deliberately deferred because
# each needs a genuine round-based sub-loop rather than a single roll.
# Both new resolvers below follow `resolve_melee_duel()`'s own shape
# exactly (mutate the real `Combatant`s in place, return an
# `EncounterCombatResult`), so `turn/search_execution.py`'s dispatcher can
# reuse the same `_outcome_from()` translation every other spell already
# uses.


def resolve_hand_of_death_channel(
    caster: Combatant,
    victim: Combatant,
    skill_level: int,
    rng: random.Random,
    *,
    target_is_immune: bool = False,
    max_rounds: int = 1000,
) -> EncounterCombatResult:
    """Rulebook (module docstring's Phase 190 addendum), the channeled
    Necromancy duel: the caster's own attack always lands (``roll_hand_
    of_death_damage()`` has no hit-chance roll of its own -- it is a
    psychic, not physical, blow) for ``1 + 0.5*level`` damage, uncapped;
    the victim's own Melee counter-attack uses their normal damage die at
    ``HAND_OF_DEATH_VICTIM_HIT_CHANCE_MULTIPLIER`` (halved) hit chance.
    Initiative uses the caster's own Necromancy skill level in place of
    Melee (``hand_of_death_caster_melee_defense_skill()``, [5.0]'s
    generic rule) against the victim's own real effective Melee skill.

    ``winner="a"`` (the caster) only when the victim's hit points reach 0
    -- "chi lancia questo incantesimo" wins outright, same convention as
    every other instant-resolution Personal-Combat spell. Returns
    ``winner=None`` the instant the victim lands *any* hit on the caster
    ("quando chi lancia l'incantesimo viene colpito perde la
    concentrazione e l'incantesimo svanisce") -- the caster still takes
    that hit's real damage; the channel simply ends there and the caller
    falls through to a normal tactic (typically Melee), the hit points
    both sides have taken so far carrying over unchanged. Returns
    ``winner=None, rounds=0`` without consuming any roll when
    ``target_is_immune`` (``models/monster.py HAND_OF_DEATH_IMMUNE_
    MONSTERS`` for a monster target, or ``leader.alignment in {UNDEAD,
    ANTI_HOLY}`` for a leader target) -- "inefficace contro" mechanical/
    Undead/anti-holy targets, the spell simply never engages.

    **Phase 413**: the caster's own damage from every round is now also
    recorded, in order, into the returned ``EncounterCombatResult.
    squeeze_hits`` -- the same "per-round detail for narrating each hit
    individually" role ``FireArrowShot``/``EncounterCombatResult.shots``
    already plays for Fire Arrow, needed to feed
    ``report/turn_report.py render_squeeze_attack()``. Only the caster's
    own squeeze lands here (Hand of Death's own attack always hits, see
    above); the victim's own Melee counter-attack that ends the channel
    isn't a squeeze and isn't logged.

    **Phase 414 correction**: Phase 413's own citation for `_LSquee`
    (SAY.PAS) said this project's Pascal source was no longer available
    to check. It was -- just not at the path searched. Re-checked
    directly: `CTME.PAS` declares `Death = (Squeeze,Batter,Crush,...)`,
    a per-weapon damage-narration category (`weapkill: weapdeath =
    array[weapon] of death`), and `weapkill`'s own entry for weapon
    `Tentacles` -- `mtweap1`'s sole owner of that weapon -- is **Giant
    Octopus** (`monster` index 55), not any spell. `_LSquee` is
    therefore confirmed, formally, to be a weapon/species damage-
    narration category first, not spell-specific in its own
    declaration. Its real *caller* (the code that decides when
    `Say(_LSquee,...)` fires, and whether Hand of Death's own attack
    ever routes through it) is still missing from the 13 surviving
    `.PAS` files, same as many other gaps this project already
    documents -- genuinely unconfirmed either way from source alone.
    No real turn-report combat log against a Giant Octopus was found in
    this project's own sample files to test the alternate reading
    against (every real Giant Octopus encounter found either fled or
    never reached combat). This module's own wiring is kept exactly as
    Phase 413 built it -- the user's own direct play experience is the
    basis, not the Pascal source -- see `report/turn_report.py
    render_squeeze_attack()`'s own Phase 414 note for the full citation.
    """

    if target_is_immune:
        return EncounterCombatResult(winner=None, rounds=0)

    caster_skill = hand_of_death_caster_melee_defense_skill(skill_level)
    victim_skill = effective_melee_skill(victim)
    squeeze_hits: list[int] = []
    round_number = 0
    for round_number in range(1, max_rounds + 1):
        order = (caster, victim) if _acts_first(caster_skill, victim_skill, rng) else (victim, caster)
        for actor in order:
            if caster.hit_points <= 0 or victim.hit_points <= 0:
                continue
            if actor is caster:
                damage = roll_hand_of_death_damage(skill_level, rng)
                squeeze_hits.append(damage)
                victim.hit_points -= damage
                if victim.hit_points <= 0:
                    return EncounterCombatResult(winner="a", rounds=round_number, squeeze_hits=tuple(squeeze_hits))
            else:
                damage = roll_melee_attack(
                    rng,
                    damage_range=victim.melee_damage_range,
                    hit_chance_multiplier=HAND_OF_DEATH_VICTIM_HIT_CHANCE_MULTIPLIER,
                )
                if damage > 0:
                    caster.hit_points -= damage
                    return EncounterCombatResult(winner=None, rounds=round_number, squeeze_hits=tuple(squeeze_hits))
        _apply_end_of_round_regeneration(caster, victim)
    return EncounterCombatResult(winner=None, rounds=round_number, squeeze_hits=tuple(squeeze_hits))


# Phase 210 -- Mirror-Image Phantasm [MI]'s own per-species intelligence
# tier, all 60 real species, project-original (user-supplied, "Intelligenza
# MOSTRI" via a Desktop text file). **Confirmed to diverge from Spiritwrack's
# own `SPIRITWRACK_ANIMAL_INTELLIGENCE_MONSTERS`/`SPIRITWRACK_MECHANICAL_
# MONSTERS` (Phase 182) for three species** -- Giant Worm, Giant Amoeba, and
# Giant Clam are Spiritwrack-Animal but Mirror-Image-Mechanical -- so this is
# a genuinely new, standalone table, not a reuse of those two sets (the
# module docstring's own Phase 187 addendum already flagged this exact risk:
# "Cross-reference, not reuse... this spell's other four tiers... have no
# existing species classification in this project to draw on at all").
MIRROR_IMAGE_MONSTER_INTELLIGENCE_TIER: dict[Monster, MirrorImageIntelligenceTier] = {
    Monster.COUATL: MirrorImageIntelligenceTier.DIVINE_OR_SUPERHUMAN,
    Monster.GO_DRAGON: MirrorImageIntelligenceTier.DIVINE_OR_SUPERHUMAN,
    Monster.TITAN: MirrorImageIntelligenceTier.DIVINE_OR_SUPERHUMAN,
    Monster.GENIE: MirrorImageIntelligenceTier.DIVINE_OR_SUPERHUMAN,
    Monster.BAL_DEMON: MirrorImageIntelligenceTier.DIVINE_OR_SUPERHUMAN,
    Monster.LICH: MirrorImageIntelligenceTier.DIVINE_OR_SUPERHUMAN,
    Monster.SPHINX: MirrorImageIntelligenceTier.HIGH_HUMAN,
    Monster.R_DRAGON: MirrorImageIntelligenceTier.HIGH_HUMAN,
    Monster.B_DRAGON: MirrorImageIntelligenceTier.HIGH_HUMAN,
    Monster.S_DRAGON: MirrorImageIntelligenceTier.HIGH_HUMAN,
    Monster.GR_DRAGON: MirrorImageIntelligenceTier.HIGH_HUMAN,
    Monster.WHITE_MAGE: MirrorImageIntelligenceTier.HIGH_HUMAN,
    Monster.NEC_MAGE: MirrorImageIntelligenceTier.HIGH_HUMAN,
    Monster.ELE_MAGE: MirrorImageIntelligenceTier.HIGH_HUMAN,
    Monster.PSY_MAGE: MirrorImageIntelligenceTier.HIGH_HUMAN,
    Monster.ILL_MAGE: MirrorImageIntelligenceTier.HIGH_HUMAN,
    Monster.WITCH: MirrorImageIntelligenceTier.HIGH_HUMAN,
    Monster.MAR_DEMON: MirrorImageIntelligenceTier.HIGH_HUMAN,
    Monster.SUCCUBUS: MirrorImageIntelligenceTier.HIGH_HUMAN,
    Monster.RAKSHASHA: MirrorImageIntelligenceTier.HIGH_HUMAN,
    Monster.ICE_DEVIL: MirrorImageIntelligenceTier.HIGH_HUMAN,
    Monster.BONE_DEVIL: MirrorImageIntelligenceTier.HIGH_HUMAN,
    Monster.IMP: MirrorImageIntelligenceTier.HIGH_HUMAN,
    Monster.BEHOLDER: MirrorImageIntelligenceTier.HIGH_HUMAN,
    Monster.VAMPIRE: MirrorImageIntelligenceTier.HIGH_HUMAN,
    Monster.SPECTRE: MirrorImageIntelligenceTier.MEDIUM_HUMAN,
    Monster.GI_EAGLE: MirrorImageIntelligenceTier.MEDIUM_HUMAN,
    Monster.ARCHER: MirrorImageIntelligenceTier.MEDIUM_HUMAN,
    Monster.SWORDSMAN: MirrorImageIntelligenceTier.MEDIUM_HUMAN,
    Monster.DRYAD: MirrorImageIntelligenceTier.MEDIUM_HUMAN,
    Monster.CENTAUR: MirrorImageIntelligenceTier.MEDIUM_HUMAN,
    Monster.MEDUSA: MirrorImageIntelligenceTier.MEDIUM_HUMAN,
    Monster.TREANT: MirrorImageIntelligenceTier.MEDIUM_HUMAN,
    Monster.GHOST: MirrorImageIntelligenceTier.MEDIUM_HUMAN,
    Monster.MUMMY: MirrorImageIntelligenceTier.MEDIUM_HUMAN,
    Monster.BANSHEE: MirrorImageIntelligenceTier.MEDIUM_HUMAN,
    Monster.MERMAID: MirrorImageIntelligenceTier.MEDIUM_HUMAN,
    Monster.GIANT: MirrorImageIntelligenceTier.LOW_HUMAN,
    Monster.TROLL: MirrorImageIntelligenceTier.LOW_HUMAN,
    Monster.GARGOYLE: MirrorImageIntelligenceTier.LOW_HUMAN,
    Monster.BIGFOOT: MirrorImageIntelligenceTier.LOW_HUMAN,
    Monster.WEREWOLF: MirrorImageIntelligenceTier.LOW_HUMAN,
    Monster.MINOTAUR: MirrorImageIntelligenceTier.LOW_HUMAN,
    Monster.GRYPHON: MirrorImageIntelligenceTier.ANIMAL,
    Monster.ELASMOSAURUS: MirrorImageIntelligenceTier.ANIMAL,
    Monster.ROC: MirrorImageIntelligenceTier.ANIMAL,
    Monster.BASILISK: MirrorImageIntelligenceTier.ANIMAL,
    Monster.CHIMERA: MirrorImageIntelligenceTier.ANIMAL,
    Monster.HYDRA: MirrorImageIntelligenceTier.ANIMAL,
    Monster.GI_WOLVERINE: MirrorImageIntelligenceTier.ANIMAL,
    Monster.GI_P_MANTIS: MirrorImageIntelligenceTier.ANIMAL,
    Monster.GI_SCORPION: MirrorImageIntelligenceTier.ANIMAL,
    Monster.GI_WASP: MirrorImageIntelligenceTier.ANIMAL,
    Monster.GI_SPIDER: MirrorImageIntelligenceTier.ANIMAL,
    Monster.GI_OCTOPUS: MirrorImageIntelligenceTier.ANIMAL,
    Monster.GW_WHALE: MirrorImageIntelligenceTier.ANIMAL,
    Monster.GI_WORM: MirrorImageIntelligenceTier.MECHANICAL,
    Monster.GOLEM: MirrorImageIntelligenceTier.MECHANICAL,
    Monster.GI_AMOEBA: MirrorImageIntelligenceTier.MECHANICAL,
    Monster.GI_CLAM: MirrorImageIntelligenceTier.MECHANICAL,
}

# A King or Hero opponent's own intelligence tier for Mirror-Image's
# Stage 1 disbelief roll -- confirmed directly by the user (project
# author), not an inferred default: "L'intelligenza di RE ed eroi (per
# quanto riguarda la difesa dall'incantesimo mirror image) e' sempre High
# Human."
MIRROR_IMAGE_LEADER_INTELLIGENCE_TIER_DEFAULT = MirrorImageIntelligenceTier.HIGH_HUMAN

# On top of that fixed High Human base, a King or Hero's own real Sage
# and Illusion skill levels add a further flat bonus to their own chance
# of disbelieving the illusion -- confirmed by the user: "C'e' un bonus
# di +2% sulla tabella per ogni livello in SA e +1% per ogni livello in
# IL." Applied directly on top of the table value, before the caster's
# own -15%/level (max 60%) reduction -- see ``resolve_mirror_image_
# duel()``'s own ``opponent_disbelief_bonus`` parameter.
MIRROR_IMAGE_LEADER_SAGE_DISBELIEF_BONUS_PER_LEVEL = 0.02
MIRROR_IMAGE_LEADER_ILLUSION_DISBELIEF_BONUS_PER_LEVEL = 0.01


def mirror_image_leader_disbelief_bonus(sage_level: int, illusion_level: int) -> float:
    """A King or Hero's own flat bonus to their chance of disbelieving a
    Mirror-Image illusion cast against them: +2% per Sage level, +1% per
    Illusion level, added directly to the ``HIGH_HUMAN`` table value (see
    ``MIRROR_IMAGE_LEADER_SAGE_DISBELIEF_BONUS_PER_LEVEL``/``MIRROR_
    IMAGE_LEADER_ILLUSION_DISBELIEF_BONUS_PER_LEVEL``'s own docstring for
    the source). Monster opponents don't get this bonus -- it's specific
    to Kings/Heroes, confirmed by the user.
    """

    return (
        MIRROR_IMAGE_LEADER_SAGE_DISBELIEF_BONUS_PER_LEVEL * sage_level
        + MIRROR_IMAGE_LEADER_ILLUSION_DISBELIEF_BONUS_PER_LEVEL * illusion_level
    )


def resolve_mirror_image_duel(
    caster: Combatant,
    opponent: Combatant,
    opponent_tier: MirrorImageIntelligenceTier,
    skill_level: int,
    rng: random.Random,
    *,
    opponent_disbelief_bonus: float = 0.0,
    max_rounds: int = 1000,
) -> EncounterCombatResult:
    """The full two-stage outcome tree quoted in the module docstring's
    Phase 187 addendum, now actually executed rather than just
    catalogued.

    **Stage 1** -- a throwaway ``illusion`` (an exact stat-copy of
    ``opponent`` at cast time) fights the *real* ``opponent`` in Melee,
    one round at a time; before each round, ``resolve_mirror_image_
    disbelief()`` (keyed by ``opponent_tier``, plus ``opponent_
    disbelief_bonus`` added directly onto the table value -- see
    ``mirror_image_leader_disbelief_bonus()`` for a King/Hero opponent's
    own Sage/Illusion-driven bonus, 0.0 for every other caller) may end
    the illusion's power outright. Only ``opponent``'s and the throwaway
    illusion's own hit points change here -- ``caster`` isn't in the
    fight yet ("the caster must concentrate on his illusion, performing
    no other actions"). If the illusion is disbelieved or loses the
    duel, this returns ``winner=None`` (3a: "the caster must continue the
    fight at the current combat range") -- whatever damage the real
    opponent took from the illusion before it lost carries over into
    that next fight.

    **Stage 2** -- only reached if the illusion *wins* Stage 1 (opponent
    mentally slain). The illusion now turns on the real caster; the same
    per-round disbelief roll applies, this time at ``MIRROR_IMAGE_
    MASTER_DISBELIEF_BASE_CHANCE`` (Medium Human's own 80% base + a flat
    25-point bonus), interleaved with a real Melee duel between
    ``caster`` and the illusion. ``winner="a"`` (the caster) if the
    illusion is disbelieved or slain -- "the caster automatically
    finishes off the already-mentally-slain monster and claims the
    treasure." ``winner="b"`` if the illusion instead reduces the
    caster's own hit points to 0 -- "the illusion fades out, and the real
    monster revives and slays the fallen illusionist" (the *magnitude* of
    the opponent's own revival isn't given anywhere in the source, and
    doesn't change this function's own reported winner, so it isn't
    modeled as a hit-points change here).
    """

    illusion = Combatant(
        name=f"{opponent.name}'s Illusion",
        hit_points=opponent.hit_points,
        melee_skill=opponent.melee_skill,
        melee_damage_range=opponent.melee_damage_range,
    )
    base_chance = MIRROR_IMAGE_DISBELIEF_BASE_CHANCE[opponent_tier] + opponent_disbelief_bonus

    total_rounds = 0
    stage1_resolved = False
    for round_number in range(1, max_rounds + 1):
        total_rounds = round_number
        if resolve_mirror_image_disbelief(base_chance, skill_level, rng):
            return EncounterCombatResult(winner=None, rounds=total_rounds)
        skill_a, skill_b = effective_melee_skill(illusion), effective_melee_skill(opponent)
        first, second = (illusion, opponent) if _acts_first(skill_a, skill_b, rng) else (opponent, illusion)
        for attacker, defender in ((first, second), (second, first)):
            if attacker.hit_points <= 0 or defender.hit_points <= 0:
                continue
            defender.hit_points -= roll_melee_attack(rng, damage_range=attacker.melee_damage_range)
        if illusion.hit_points <= 0:
            return EncounterCombatResult(winner=None, rounds=total_rounds)
        if opponent.hit_points <= 0:
            stage1_resolved = True
            break
    if not stage1_resolved:
        return EncounterCombatResult(winner=None, rounds=total_rounds)

    master_chance = MIRROR_IMAGE_MASTER_DISBELIEF_BASE_CHANCE
    for _ in range(1, max_rounds + 1):
        total_rounds += 1
        if resolve_mirror_image_disbelief(master_chance, skill_level, rng):
            return EncounterCombatResult(winner="a", rounds=total_rounds)
        skill_a, skill_b = effective_melee_skill(caster), effective_melee_skill(illusion)
        first, second = (caster, illusion) if _acts_first(skill_a, skill_b, rng) else (illusion, caster)
        for attacker, defender in ((first, second), (second, first)):
            if attacker.hit_points <= 0 or defender.hit_points <= 0:
                continue
            defender.hit_points -= roll_melee_attack(rng, damage_range=attacker.melee_damage_range)
        if illusion.hit_points <= 0:
            return EncounterCombatResult(winner="a", rounds=total_rounds)
        if caster.hit_points <= 0:
            return EncounterCombatResult(winner="b", rounds=total_rounds)
    return EncounterCombatResult(winner=None, rounds=total_rounds)


# Phase 211 addendum -- Illusory Hero [IH] (module docstring's own Phase 208
# addendum quoted the rule in full: "the Illusionist creates an image of
# whatever Valhalla hero is currently in the world, to fight in his place.
# It is similar to 'Mirror-Image Phantasm', except that 15% is subtracted
# from the chance to disbelieve, and the illusory hero will usually not
# turn on its master if the illusion wins (unless the alignments of the
# illusion and the spellcaster are implacably hostile, for example Good
# versus Evil)."). The last of the ten secret spells (25-34) to be wired
# into real Search combat -- see `turn/search_execution.py`'s own
# dispatcher for the ``AdvancedAbility.ILLUSORY_HERO_SPELL`` (Ability.
# ILLUSION skill 5+) precondition and the Valhalla-visitor lookup
# (`models/valhalla.py VALHALLA_VISITOR_LEADER_ID`).

# The "implacably hostile" alignment pairs, project-original (user-
# supplied) -- the rulebook itself only confirms one worked example
# ("Good versus Evil"), and this module's own Phase 187 addendum already
# declined to invent a general hostility classifier from a single
# example. Stored as unordered pairs (symmetric: if A is hostile to B, B
# is hostile to A) via `frozenset({a, b})` membership.
ILLUSORY_HERO_HOSTILE_ALIGNMENT_PAIRS: frozenset[frozenset[Alignment]] = frozenset(
    {
        frozenset({Alignment.DIVINE, Alignment.PAGAN}),
        frozenset({Alignment.DIVINE, Alignment.EVIL}),
        frozenset({Alignment.DIVINE, Alignment.UNDEAD}),
        frozenset({Alignment.GOOD, Alignment.EVIL}),
        frozenset({Alignment.GOOD, Alignment.UNDEAD}),
        frozenset({Alignment.UNDEAD, Alignment.DRUID}),
    }
)


def illusory_hero_alignments_are_implacably_hostile(a: Alignment, b: Alignment) -> bool:
    """True if ``a``/``b`` are one of the confirmed "implacably hostile"
    alignment pairs -- see ``ILLUSORY_HERO_HOSTILE_ALIGNMENT_PAIRS``'s own
    docstring for the source. Every other alignment combination (Anti-
    Holy, Neutral, Mechanical, Special included) is not confirmed hostile
    to anything, so this returns False for them.
    """

    return frozenset({a, b}) in ILLUSORY_HERO_HOSTILE_ALIGNMENT_PAIRS


def resolve_illusory_hero_duel(
    caster: Combatant,
    opponent: Combatant,
    hero: Combatant,
    opponent_tier: MirrorImageIntelligenceTier,
    skill_level: int,
    rng: random.Random,
    *,
    opponent_disbelief_bonus: float = 0.0,
    turns_on_master: bool = False,
    max_rounds: int = 1000,
) -> EncounterCombatResult:
    """Mirror-Image Phantasm's own outcome tree (``resolve_mirror_image_
    duel()``), with the two confirmed differences: the illusion is a
    fresh image of ``hero`` (the current Valhalla visitor, at full
    ``CHARACTER_HIT_POINTS`` -- an image, not a snapshot of the real
    visitor's own current wounds) rather than a clone of ``opponent``,
    and every disbelief roll uses ``resolve_illusory_hero_disbelief()``
    (the same table plus caster-level reduction, minus a further flat
    15%) instead of the base Mirror-Image formula.

    **Stage 1** -- the hero-illusion fights the real ``opponent`` in
    Melee, gated each round by the opponent's own chance to disbelieve
    (``opponent_tier``, plus ``opponent_disbelief_bonus`` for a King/Hero
    opponent's own Sage/Illusion bonus, same convention as ``resolve_
    mirror_image_duel()``). Disbelieved or lost -> ``winner=None`` (the
    caster resumes fighting for real).

    **Stage 2** -- only reached if the illusion wins Stage 1 *and*
    ``turns_on_master`` is True (the caller's own ``illusory_hero_
    alignments_are_implacably_hostile()`` check -- "the illusory hero
    will usually not turn on its master"). If ``turns_on_master`` is
    False, winning Stage 1 is an outright ``winner="a"`` (caster) with no
    further duel at all. If True, Stage 2 proceeds exactly like Mirror-
    Image's own second stage (the same ``MIRROR_IMAGE_MASTER_DISBELIEF_
    BASE_CHANCE``, since no separate number is given for Illusory Hero's
    own version of this branch): ``winner="a"`` if the caster disbelieves
    or slays the illusion, ``winner="b"`` if the illusion kills the
    caster instead.
    """

    illusion = Combatant(
        name=f"Illusory {hero.name}",
        hit_points=CHARACTER_HIT_POINTS,
        melee_skill=hero.melee_skill,
        melee_damage_range=hero.melee_damage_range,
    )
    base_chance = MIRROR_IMAGE_DISBELIEF_BASE_CHANCE[opponent_tier] + opponent_disbelief_bonus

    total_rounds = 0
    stage1_resolved = False
    for round_number in range(1, max_rounds + 1):
        total_rounds = round_number
        if resolve_illusory_hero_disbelief(base_chance, skill_level, rng):
            return EncounterCombatResult(winner=None, rounds=total_rounds)
        skill_a, skill_b = effective_melee_skill(illusion), effective_melee_skill(opponent)
        first, second = (illusion, opponent) if _acts_first(skill_a, skill_b, rng) else (opponent, illusion)
        for attacker, defender in ((first, second), (second, first)):
            if attacker.hit_points <= 0 or defender.hit_points <= 0:
                continue
            defender.hit_points -= roll_melee_attack(rng, damage_range=attacker.melee_damage_range)
        if illusion.hit_points <= 0:
            return EncounterCombatResult(winner=None, rounds=total_rounds)
        if opponent.hit_points <= 0:
            stage1_resolved = True
            break
    if not stage1_resolved:
        return EncounterCombatResult(winner=None, rounds=total_rounds)

    if not turns_on_master:
        return EncounterCombatResult(winner="a", rounds=total_rounds)

    master_chance = MIRROR_IMAGE_MASTER_DISBELIEF_BASE_CHANCE
    for _ in range(1, max_rounds + 1):
        total_rounds += 1
        if resolve_illusory_hero_disbelief(master_chance, skill_level, rng):
            return EncounterCombatResult(winner="a", rounds=total_rounds)
        skill_a, skill_b = effective_melee_skill(caster), effective_melee_skill(illusion)
        first, second = (caster, illusion) if _acts_first(skill_a, skill_b, rng) else (illusion, caster)
        for attacker, defender in ((first, second), (second, first)):
            if attacker.hit_points <= 0 or defender.hit_points <= 0:
                continue
            defender.hit_points -= roll_melee_attack(rng, damage_range=attacker.melee_damage_range)
        if illusion.hit_points <= 0:
            return EncounterCombatResult(winner="a", rounds=total_rounds)
        if caster.hit_points <= 0:
            return EncounterCombatResult(winner="b", rounds=total_rounds)
    return EncounterCombatResult(winner=None, rounds=total_rounds)


# Steal [ST], rulebook [5.4] -- Phase 239. Quoted in full by the user
# (project author): "Il personaggio tenta di rubare il suo avversario,
# Re, Eroe o mostro che sia. Ci sono due possibilita': o ci riesce
# oppure viene scoperto... La probabilita' base di riuscita e' del 15%
# piu' 15% per livello di abilita', ma si applicano le seguenti
# modifiche. 1) Se il ladro prende di mira un personaggio che e' alla
# guida di un esercito le sue probabilita' di riuscita sono dimezzate.
# 2) Se la vittima e' un Re, c'e' la possibilita' di sottrargli una
# certa quantita' di oro (dipende da quanto ha nella tesoreria in quel
# momento)." The King-gold-theft magnitude (2) has no numeric formula
# anywhere in the quoted text -- confirmed absent, not modeled here (no
# Search target is ever a King, so this doesn't block Search's own
# wiring; a future Challenge/Pursue-side Steal would still need it).
STEAL_BASE_SUCCESS_CHANCE = 0.15
STEAL_SUCCESS_CHANCE_PER_LEVEL = 0.15
# "The Thief adds 15% to his chance to Steal (however, the maximum
# chance is always 95%)" -- Thief Mastery I-V's own tooltip text
# (`models/advanced_ability.py`), read as the cap on the overall
# base+modifiers chance, not just that ability's own bonus.
STEAL_MAX_SUCCESS_CHANCE = 0.95
STEAL_ARMY_COMMANDER_TARGET_MULTIPLIER = 0.5


def steal_success_chance(level: int, *, target_leads_army: bool = False) -> float:
    """The thief's own chance of a successful Steal attempt: 15% base +
    15%/level, halved if the target is leading an army, capped at 95%.
    """

    chance = STEAL_BASE_SUCCESS_CHANCE + STEAL_SUCCESS_CHANCE_PER_LEVEL * level
    if target_leads_army:
        chance *= STEAL_ARMY_COMMANDER_TARGET_MULTIPLIER
    return min(chance, STEAL_MAX_SUCCESS_CHANCE)


def resolve_steal_attempt(level: int, rng: random.Random, *, target_leads_army: bool = False) -> bool:
    return rng.random() < steal_success_chance(level, target_leads_army=target_leads_army)


# "Se il ladro fallisce nei suoi tentativi di furto non verra'
# necessariamente arrestato: le probabilita' di evitare la cattura sono
# in funzione del livello di abilita' del ladro" -- no numeric formula
# given anywhere. Confirmed directly with the user (project author):
# project-original values, not sourced -- structured the same way as
# the sourced Steal-success formula above (a flat base plus a per-level
# scaling, capped short of certainty) for internal consistency, but
# distinct numbers: a higher base (evading detection after a failed
# attempt reads as inherently easier than the theft itself) and a lower
# cap (90%, not 95%, kept deliberately distinguishable from the sourced
# Thief Mastery cap above).
STEAL_EVASION_BASE_CHANCE = 0.30
STEAL_EVASION_CHANCE_PER_LEVEL = 0.10
STEAL_EVASION_MAX_CHANCE = 0.90


def steal_evasion_chance(level: int) -> float:
    return min(STEAL_EVASION_BASE_CHANCE + STEAL_EVASION_CHANCE_PER_LEVEL * level, STEAL_EVASION_MAX_CHANCE)


def resolve_steal_evasion(level: int, rng: random.Random) -> bool:
    return rng.random() < steal_evasion_chance(level)


class StealTargetCunning(Enum):
    """A monster's own hiding-treasure sophistication tier for each
    Steal attempt's own countermeasure roll. Three buckets, not
    ``MirrorImageIntelligenceTier``'s six -- the source text below only
    ever names three ("media intelligenza", "piu' furbo... 25%",
    "...50%").
    """

    AVERAGE = "Average"
    CLEVER = "Clever"
    MASTER = "Master"


# "Se si tenta di derubare un mostro, questi tentera' di nascondere il
# suo tesoro dove non puo' essere trovato (ad esempio dormendoci
# sopra). Se il mostro e' di media intelligenza, ogni suo tentativo di
# sventare il furto avra' il 10% di probabilita' di riuscita, se e'
# piu' furbo la probabilita' puo' salire fino al 25% o al 50%." --
# quoted in full, the user's own rulebook text.
STEAL_MONSTER_HIDE_TREASURE_CHANCE: dict[StealTargetCunning, float] = {
    StealTargetCunning.AVERAGE: 0.10,
    StealTargetCunning.CLEVER: 0.25,
    StealTargetCunning.MASTER: 0.50,
}

# Collapses the existing, real per-species ``MIRROR_IMAGE_MONSTER_
# INTELLIGENCE_TIER`` (Phase 187, six tiers) down to Steal's own three
# buckets -- an interpretive mapping (the Steal rulebook text above
# gives no per-species breakdown of its own), not a guess at the
# 10%/25%/50% figures themselves, which are quoted verbatim above.
# Medium Human and everything below it (Low Human, Animal, Mechanical)
# reads as "average intelligence" (10%); High Human as "more clever"
# (25%); Divine/Superhuman as the ceiling case (50%).
MONSTER_STEAL_CUNNING: dict[Monster, StealTargetCunning] = {
    monster: (
        StealTargetCunning.MASTER
        if tier is MirrorImageIntelligenceTier.DIVINE_OR_SUPERHUMAN
        else StealTargetCunning.CLEVER
        if tier is MirrorImageIntelligenceTier.HIGH_HUMAN
        else StealTargetCunning.AVERAGE
    )
    for monster, tier in MIRROR_IMAGE_MONSTER_INTELLIGENCE_TIER.items()
}


def resolve_monster_hides_treasure(cunning: StealTargetCunning, rng: random.Random) -> bool:
    return rng.random() < STEAL_MONSTER_HIDE_TREASURE_CHANCE[cunning]


# Talk [TA], rulebook [5.5] -- Phase 240. Quoted in full by the user
# (project author): "Quando un personaggio parla (Talk) con un mostro
# che difende un Luogo Speciale, il mostro o lo attaccherà, o lo
# ignorerà, o gli proporrà un accordo come ad esempio una ricerca che
# verrà ricompensata con il dono di un oggetto magico ... Quando un
# personaggio di allineamento Druidico riesce a parlare con un mostro,
# quest'ultimo può dimostrarsi maggiormente disposto ad aiutarlo di
# quando non lo sarebbe nei confronti di personaggi di diverso
# allineamento." A second case the user's own text also covers --
# talking to an independent character (a wandering Hero) reveals their
# Alignment/Temperament/hire cost -- is confirmed out of scope here:
# Search's own target is always the guardian monster, never a
# character (see `turn/search_execution.py`'s own Phase 240 addendum).
#
# **The DR (Druid-skill) gate**: `TALK_MONSTER_DRUID_LEVEL_REQUIRED`,
# sourced from `HostAK/TP/CTME.PAS`'s own `talkdiff` table ("DR" is
# that table's own column header, confirmed as the Druid ability's
# abbreviation at `CTBOTH.PAS` line 151: `'DR','TH','EX','SP','SA'`).
# Cross-checked against the user's own supplied rulebook table: 43 of
# 60 species agreed exactly; where the two disagreed (17 species:
# Beholder, Black Dragon, Chimera, Elemental Sorceror, Gargoyle, Ghost,
# Giant, Giant Clam, Giant Worm, Green Dragon, Hydra, Imp, Mermaid,
# Mummy, Spectre, Troll, Werewolf), the user (project author) confirmed
# directly that the Pascal table wins.
TALK_MONSTER_DRUID_LEVEL_REQUIRED: dict[Monster, int] = {
    Monster.ROC: 1,
    Monster.GRYPHON: 1,
    Monster.COUATL: 0,
    Monster.GI_EAGLE: 1,
    Monster.SPHINX: 0,
    Monster.R_DRAGON: 0,
    Monster.B_DRAGON: 0,
    Monster.GR_DRAGON: 0,
    Monster.S_DRAGON: 0,
    Monster.GO_DRAGON: 0,
    Monster.GI_WORM: 3,
    Monster.TITAN: 0,
    Monster.GIANT: 0,
    Monster.BIGFOOT: 1,
    Monster.ARCHER: 0,
    Monster.SWORDSMAN: 0,
    Monster.WHITE_MAGE: 0,
    Monster.NEC_MAGE: 0,
    Monster.ELE_MAGE: 0,
    Monster.PSY_MAGE: 0,
    Monster.ILL_MAGE: 0,
    Monster.WITCH: 0,
    Monster.DRYAD: 0,
    Monster.CENTAUR: 0,
    Monster.GENIE: 0,
    Monster.GOLEM: 4,
    Monster.GARGOYLE: 2,
    Monster.BASILISK: 2,
    Monster.MEDUSA: 0,
    Monster.BAL_DEMON: 0,
    Monster.MAR_DEMON: 0,
    Monster.SUCCUBUS: 0,
    Monster.RAKSHASHA: 0,
    Monster.ICE_DEVIL: 0,
    Monster.BONE_DEVIL: 0,
    Monster.IMP: 0,
    Monster.WEREWOLF: 0,
    Monster.CHIMERA: 4,
    Monster.HYDRA: 4,
    Monster.BEHOLDER: 2,
    Monster.TROLL: 0,
    Monster.MINOTAUR: 1,
    Monster.GI_WOLVERINE: 1,
    Monster.TREANT: 0,
    Monster.GI_AMOEBA: 4,
    Monster.GI_P_MANTIS: 3,
    Monster.GI_SCORPION: 3,
    Monster.GI_WASP: 3,
    Monster.GI_SPIDER: 3,
    Monster.GHOST: 0,
    Monster.VAMPIRE: 0,
    Monster.MUMMY: 0,
    Monster.BANSHEE: 0,
    Monster.LICH: 0,
    Monster.SPECTRE: 0,
    Monster.GI_OCTOPUS: 2,
    Monster.GI_CLAM: 2,
    Monster.ELASMOSAURUS: 2,
    Monster.GW_WHALE: 2,
    Monster.MERMAID: 0,
}


def can_talk_to_monster(monster_species: Monster, druid_level: int) -> bool:
    """Whether a character's own Druid skill level meets `talkdiff`'s own
    per-species requirement to communicate with this monster at all.
    """

    return druid_level >= TALK_MONSTER_DRUID_LEVEL_REQUIRED.get(monster_species, 0)


class TalkReaction(Enum):
    """The three outcomes the rulebook names for a successful Talk (DR
    gate met): the monster attacks, ignores the character, or proposes
    a deal.
    """

    ATTACK = "Attack"
    IGNORE = "Ignore"
    DEAL = "Deal"


# No numeric split between Attack/Ignore/Deal is given anywhere --
# confirmed directly with the user (project author): project-original
# values, not sourced. A Druidic-aligned caster shifts probability mass
# from Attack to Deal, per the rulebook's own "maggiormente disposto ad
# aiutarlo" ("more inclined to help") text -- Ignore's own chance stays
# fixed either way.
TALK_ATTACK_CHANCE = 0.40
TALK_IGNORE_CHANCE = 0.35
TALK_DRUIDIC_ATTACK_CHANCE = 0.20


def resolve_talk_reaction(rng: random.Random, *, caster_is_druidic: bool = False) -> TalkReaction:
    attack_chance = TALK_DRUIDIC_ATTACK_CHANCE if caster_is_druidic else TALK_ATTACK_CHANCE
    roll = rng.random()
    if roll < attack_chance:
        return TalkReaction.ATTACK
    if roll < attack_chance + TALK_IGNORE_CHANCE:
        return TalkReaction.IGNORE
    return TalkReaction.DEAL


# **Phase 382 -- the real 24-reply Talk selector, `runtime_mechanics.
# monster_talk` (`AK.OVR TALK branch`/`AK.EXE reply selector`, a real
# static disassembly).** `TalkReaction`/`resolve_talk_reaction()` above
# stay exactly as they are -- confirmed directly with the user
# (project author) as project-original, and already the live mechanism
# `turn/search_execution.py`'s own Talk branch calls. What follows is
# **additive, not a replacement**: the real compiled selector this
# source names, given real per-reply data this project didn't have
# before, but not yet wired into live Talk execution -- swapping
# `search_execution.py`'s own Talk branch over to it is a separate,
# larger follow-up decision (the same "confirmed real, not unilaterally
# swapped into live behavior" stance Phase 381's own `MONSTER_RUNTIME_
# PROFILE` addendum already takes for `MONSTER_COMBAT_STATS`).
#
# The 24 real reply identifiers (`RPuzzled`..`RMAdvance`), each with a
# real `repfreq` (0-10, the reply's own acceptance chance out of 10),
# `repint`/`rivar` (an eligibility band on the monster's own `mintel`,
# reusing `models/monster.py MonsterIntelligence`/`MONSTER_
# INTELLIGENCE_ORDINAL`, Phase 382's own addendum there), `repview`/
# `rvvar` (the same band on the monster's own `mview`, reusing
# `models/alignment.py Alignment`/`ALIGNMENT_ORDINAL`), and which of
# the three narrative outcomes (Ignore/Attack/Quest-or-Agreement) it
# belongs to.
class MonsterTalkReply(Enum):
    R_PUZZLED = 0
    R_CHARGE = 1
    R_WARN = 2
    R_REGAIN = 3
    R_VISIT = 4
    R_RIDDLE = 5
    R_FREVENGE = 6
    R_PAIN = 7
    R_SLAVE = 8
    R_MATE = 9
    R_TRADE = 10
    R_WISH = 11
    R_SELL = 12
    R_SOUL = 13
    R_SACH = 14
    R_WFREE = 15
    R_JUNDEAD = 16
    R_PREVENGE = 17
    R_DRAIN = 18
    R_CIRCNAV = 19
    R_2POLES = 20
    R_1TERR = 21
    R_EXPALL = 22
    R_MADVANCE = 23


MONSTER_TALK_REPLY_NAME: dict[MonsterTalkReply, str] = {
    MonsterTalkReply.R_PUZZLED: "RPuzzled",
    MonsterTalkReply.R_CHARGE: "RCharge",
    MonsterTalkReply.R_WARN: "RWarn",
    MonsterTalkReply.R_REGAIN: "RRegain",
    MonsterTalkReply.R_VISIT: "RVisit",
    MonsterTalkReply.R_RIDDLE: "RRiddle",
    MonsterTalkReply.R_FREVENGE: "RFRevenge",
    MonsterTalkReply.R_PAIN: "RPain",
    MonsterTalkReply.R_SLAVE: "RSlave",
    MonsterTalkReply.R_MATE: "RMate",
    MonsterTalkReply.R_TRADE: "RTrade",
    MonsterTalkReply.R_WISH: "RWish",
    MonsterTalkReply.R_SELL: "RSell",
    MonsterTalkReply.R_SOUL: "RSoul",
    MonsterTalkReply.R_SACH: "RSacH",
    MonsterTalkReply.R_WFREE: "RWFree",
    MonsterTalkReply.R_JUNDEAD: "RJUndead",
    MonsterTalkReply.R_PREVENGE: "RPRevenge",
    MonsterTalkReply.R_DRAIN: "RDrain",
    MonsterTalkReply.R_CIRCNAV: "RCircNav",
    MonsterTalkReply.R_2POLES: "R2Poles",
    MonsterTalkReply.R_1TERR: "R1Terr",
    MonsterTalkReply.R_EXPALL: "RExpAll",
    MonsterTalkReply.R_MADVANCE: "RMAdvance",
}

MONSTER_TALK_REPLY_FREQUENCY: dict[MonsterTalkReply, int] = {
    MonsterTalkReply.R_PUZZLED: 5,
    MonsterTalkReply.R_CHARGE: 10,
    MonsterTalkReply.R_WARN: 7,
    MonsterTalkReply.R_REGAIN: 5,
    MonsterTalkReply.R_VISIT: 10,
    MonsterTalkReply.R_RIDDLE: 7,
    MonsterTalkReply.R_FREVENGE: 8,
    MonsterTalkReply.R_PAIN: 3,
    MonsterTalkReply.R_SLAVE: 5,
    MonsterTalkReply.R_MATE: 3,
    MonsterTalkReply.R_TRADE: 7,
    MonsterTalkReply.R_WISH: 10,
    MonsterTalkReply.R_SELL: 10,
    MonsterTalkReply.R_SOUL: 8,
    MonsterTalkReply.R_SACH: 5,
    MonsterTalkReply.R_WFREE: 4,
    MonsterTalkReply.R_JUNDEAD: 10,
    MonsterTalkReply.R_PREVENGE: 9,
    MonsterTalkReply.R_DRAIN: 8,
    MonsterTalkReply.R_CIRCNAV: 4,
    MonsterTalkReply.R_2POLES: 4,
    MonsterTalkReply.R_1TERR: 4,
    MonsterTalkReply.R_EXPALL: 4,
    MonsterTalkReply.R_MADVANCE: 10,
}

MONSTER_TALK_REPLY_INTELLIGENCE: dict[MonsterTalkReply, MonsterIntelligence] = {
    MonsterTalkReply.R_PUZZLED: MonsterIntelligence.SEMI,
    MonsterTalkReply.R_CHARGE: MonsterIntelligence.MEDIUM,
    MonsterTalkReply.R_WARN: MonsterIntelligence.MEDIUM,
    MonsterTalkReply.R_REGAIN: MonsterIntelligence.MEDIUM,
    MonsterTalkReply.R_VISIT: MonsterIntelligence.MEDIUM,
    MonsterTalkReply.R_RIDDLE: MonsterIntelligence.HIGH,
    MonsterTalkReply.R_FREVENGE: MonsterIntelligence.MEDIUM,
    MonsterTalkReply.R_PAIN: MonsterIntelligence.SEMI,
    MonsterTalkReply.R_SLAVE: MonsterIntelligence.MEDIUM,
    MonsterTalkReply.R_MATE: MonsterIntelligence.LOW,
    MonsterTalkReply.R_TRADE: MonsterIntelligence.HIGH,
    MonsterTalkReply.R_WISH: MonsterIntelligence.GODLIKE,
    MonsterTalkReply.R_SELL: MonsterIntelligence.MEDIUM,
    MonsterTalkReply.R_SOUL: MonsterIntelligence.HIGH,
    MonsterTalkReply.R_SACH: MonsterIntelligence.HIGH,
    MonsterTalkReply.R_WFREE: MonsterIntelligence.LOW,
    MonsterTalkReply.R_JUNDEAD: MonsterIntelligence.MEDIUM,
    MonsterTalkReply.R_PREVENGE: MonsterIntelligence.MEDIUM,
    MonsterTalkReply.R_DRAIN: MonsterIntelligence.MEDIUM,
    MonsterTalkReply.R_CIRCNAV: MonsterIntelligence.GODLIKE,
    MonsterTalkReply.R_2POLES: MonsterIntelligence.GODLIKE,
    MonsterTalkReply.R_1TERR: MonsterIntelligence.GODLIKE,
    MonsterTalkReply.R_EXPALL: MonsterIntelligence.GODLIKE,
    MonsterTalkReply.R_MADVANCE: MonsterIntelligence.MEDIUM,
}

MONSTER_TALK_REPLY_INTELLIGENCE_VARIANCE: dict[MonsterTalkReply, int] = {
    MonsterTalkReply.R_PUZZLED: 0,
    MonsterTalkReply.R_CHARGE: 2,
    MonsterTalkReply.R_WARN: 3,
    MonsterTalkReply.R_REGAIN: 1,
    MonsterTalkReply.R_VISIT: 1,
    MonsterTalkReply.R_RIDDLE: 1,
    MonsterTalkReply.R_FREVENGE: 1,
    MonsterTalkReply.R_PAIN: 0,
    MonsterTalkReply.R_SLAVE: 1,
    MonsterTalkReply.R_MATE: 2,
    MonsterTalkReply.R_TRADE: 2,
    MonsterTalkReply.R_WISH: 1,
    MonsterTalkReply.R_SELL: 1,
    MonsterTalkReply.R_SOUL: 1,
    MonsterTalkReply.R_SACH: 1,
    MonsterTalkReply.R_WFREE: 1,
    MonsterTalkReply.R_JUNDEAD: 2,
    MonsterTalkReply.R_PREVENGE: 1,
    MonsterTalkReply.R_DRAIN: 2,
    MonsterTalkReply.R_CIRCNAV: 2,
    MonsterTalkReply.R_2POLES: 2,
    MonsterTalkReply.R_1TERR: 2,
    MonsterTalkReply.R_EXPALL: 2,
    MonsterTalkReply.R_MADVANCE: 3,
}

MONSTER_TALK_REPLY_VIEW: dict[MonsterTalkReply, Alignment] = {
    MonsterTalkReply.R_PUZZLED: Alignment.SPECIAL,
    MonsterTalkReply.R_CHARGE: Alignment.EVIL,
    MonsterTalkReply.R_WARN: Alignment.EVIL,
    MonsterTalkReply.R_REGAIN: Alignment.PAGAN,
    MonsterTalkReply.R_VISIT: Alignment.DRUID,
    MonsterTalkReply.R_RIDDLE: Alignment.NEUTRAL,
    MonsterTalkReply.R_FREVENGE: Alignment.NEUTRAL,
    MonsterTalkReply.R_PAIN: Alignment.NEUTRAL,
    MonsterTalkReply.R_SLAVE: Alignment.NEUTRAL,
    MonsterTalkReply.R_MATE: Alignment.NEUTRAL,
    MonsterTalkReply.R_TRADE: Alignment.NEUTRAL,
    MonsterTalkReply.R_WISH: Alignment.DIVINE,
    MonsterTalkReply.R_SELL: Alignment.NEUTRAL,
    MonsterTalkReply.R_SOUL: Alignment.ANTI_HOLY,
    MonsterTalkReply.R_SACH: Alignment.ANTI_HOLY,
    MonsterTalkReply.R_WFREE: Alignment.NEUTRAL,
    MonsterTalkReply.R_JUNDEAD: Alignment.UNDEAD,
    MonsterTalkReply.R_PREVENGE: Alignment.NEUTRAL,
    MonsterTalkReply.R_DRAIN: Alignment.UNDEAD,
    MonsterTalkReply.R_CIRCNAV: Alignment.NEUTRAL,
    MonsterTalkReply.R_2POLES: Alignment.NEUTRAL,
    MonsterTalkReply.R_1TERR: Alignment.NEUTRAL,
    MonsterTalkReply.R_EXPALL: Alignment.NEUTRAL,
    MonsterTalkReply.R_MADVANCE: Alignment.MECHANICAL,
}

MONSTER_TALK_REPLY_VIEW_VARIANCE: dict[MonsterTalkReply, int] = {
    MonsterTalkReply.R_PUZZLED: 0,
    MonsterTalkReply.R_CHARGE: 2,
    MonsterTalkReply.R_WARN: 4,
    MonsterTalkReply.R_REGAIN: 3,
    MonsterTalkReply.R_VISIT: 2,
    MonsterTalkReply.R_RIDDLE: 1,
    MonsterTalkReply.R_FREVENGE: 2,
    MonsterTalkReply.R_PAIN: 2,
    MonsterTalkReply.R_SLAVE: 2,
    MonsterTalkReply.R_MATE: 2,
    MonsterTalkReply.R_TRADE: 4,
    MonsterTalkReply.R_WISH: 1,
    MonsterTalkReply.R_SELL: 2,
    MonsterTalkReply.R_SOUL: 0,
    MonsterTalkReply.R_SACH: 1,
    MonsterTalkReply.R_WFREE: 3,
    MonsterTalkReply.R_JUNDEAD: 0,
    MonsterTalkReply.R_PREVENGE: 2,
    MonsterTalkReply.R_DRAIN: 0,
    MonsterTalkReply.R_CIRCNAV: 3,
    MonsterTalkReply.R_2POLES: 3,
    MonsterTalkReply.R_1TERR: 3,
    MonsterTalkReply.R_EXPALL: 3,
    MonsterTalkReply.R_MADVANCE: 1,
}

MONSTER_TALK_REPLY_INVOLVES_CHARACTER: dict[MonsterTalkReply, bool] = {
    MonsterTalkReply.R_PUZZLED: False,
    MonsterTalkReply.R_CHARGE: False,
    MonsterTalkReply.R_WARN: False,
    MonsterTalkReply.R_REGAIN: False,
    MonsterTalkReply.R_VISIT: False,
    MonsterTalkReply.R_RIDDLE: False,
    MonsterTalkReply.R_FREVENGE: True,
    MonsterTalkReply.R_PAIN: False,
    MonsterTalkReply.R_SLAVE: False,
    MonsterTalkReply.R_MATE: False,
    MonsterTalkReply.R_TRADE: False,
    MonsterTalkReply.R_WISH: False,
    MonsterTalkReply.R_SELL: False,
    MonsterTalkReply.R_SOUL: False,
    MonsterTalkReply.R_SACH: False,
    MonsterTalkReply.R_WFREE: False,
    MonsterTalkReply.R_JUNDEAD: False,
    MonsterTalkReply.R_PREVENGE: True,
    MonsterTalkReply.R_DRAIN: False,
    MonsterTalkReply.R_CIRCNAV: False,
    MonsterTalkReply.R_2POLES: False,
    MonsterTalkReply.R_1TERR: False,
    MonsterTalkReply.R_EXPALL: False,
    MonsterTalkReply.R_MADVANCE: False,
}


class TalkReplyOutcome(Enum):
    IGNORE = "Ignore"
    ATTACK = "Attack"
    QUEST_OR_AGREEMENT = "Quest or Agreement"


# `outcome_categories`: ids {0, 2} ignore, {1, 23} attack, the remaining
# 20 ids each a distinct quest/agreement (see `agreements` in the
# source for each one's own request/reward text -- not transcribed
# here, out of scope for this vocabulary-level phase).
MONSTER_TALK_REPLY_OUTCOME: dict[MonsterTalkReply, TalkReplyOutcome] = {
    MonsterTalkReply.R_PUZZLED: TalkReplyOutcome.IGNORE,
    MonsterTalkReply.R_CHARGE: TalkReplyOutcome.ATTACK,
    MonsterTalkReply.R_WARN: TalkReplyOutcome.IGNORE,
    MonsterTalkReply.R_REGAIN: TalkReplyOutcome.QUEST_OR_AGREEMENT,
    MonsterTalkReply.R_VISIT: TalkReplyOutcome.QUEST_OR_AGREEMENT,
    MonsterTalkReply.R_RIDDLE: TalkReplyOutcome.QUEST_OR_AGREEMENT,
    MonsterTalkReply.R_FREVENGE: TalkReplyOutcome.QUEST_OR_AGREEMENT,
    MonsterTalkReply.R_PAIN: TalkReplyOutcome.QUEST_OR_AGREEMENT,
    MonsterTalkReply.R_SLAVE: TalkReplyOutcome.QUEST_OR_AGREEMENT,
    MonsterTalkReply.R_MATE: TalkReplyOutcome.QUEST_OR_AGREEMENT,
    MonsterTalkReply.R_TRADE: TalkReplyOutcome.QUEST_OR_AGREEMENT,
    MonsterTalkReply.R_WISH: TalkReplyOutcome.QUEST_OR_AGREEMENT,
    MonsterTalkReply.R_SELL: TalkReplyOutcome.QUEST_OR_AGREEMENT,
    MonsterTalkReply.R_SOUL: TalkReplyOutcome.QUEST_OR_AGREEMENT,
    MonsterTalkReply.R_SACH: TalkReplyOutcome.QUEST_OR_AGREEMENT,
    MonsterTalkReply.R_WFREE: TalkReplyOutcome.QUEST_OR_AGREEMENT,
    MonsterTalkReply.R_JUNDEAD: TalkReplyOutcome.QUEST_OR_AGREEMENT,
    MonsterTalkReply.R_PREVENGE: TalkReplyOutcome.QUEST_OR_AGREEMENT,
    MonsterTalkReply.R_DRAIN: TalkReplyOutcome.QUEST_OR_AGREEMENT,
    MonsterTalkReply.R_CIRCNAV: TalkReplyOutcome.QUEST_OR_AGREEMENT,
    MonsterTalkReply.R_2POLES: TalkReplyOutcome.QUEST_OR_AGREEMENT,
    MonsterTalkReply.R_1TERR: TalkReplyOutcome.QUEST_OR_AGREEMENT,
    MonsterTalkReply.R_EXPALL: TalkReplyOutcome.QUEST_OR_AGREEMENT,
    MonsterTalkReply.R_MADVANCE: TalkReplyOutcome.ATTACK,
}


def monster_talk_reply_eligible(
    reply: MonsterTalkReply, monster: Monster, *, has_purchasable_treasure: bool = False
) -> bool:
    """Whether `reply` passes the source's own 4 eligibility gates for
    `monster`'s own real `MONSTER_RUNTIME_PROFILE` view/intelligence.
    `RMate` reuses `MonsterRuntimeProfile.can_offer_mate_quest`
    directly (Phase 381's own `mtmate` field) rather than a caller
    argument; `RSell`'s own "a purchasable magic-item treasure" gate is
    a real-world-state question this module has no access to, so it's
    threaded in by the caller instead of guessed.
    """

    profile = MONSTER_RUNTIME_PROFILE[monster]
    view_distance = abs(ALIGNMENT_ORDINAL[profile.base_view] - ALIGNMENT_ORDINAL[MONSTER_TALK_REPLY_VIEW[reply]])
    if view_distance > MONSTER_TALK_REPLY_VIEW_VARIANCE[reply]:
        return False
    intel_distance = abs(
        MONSTER_INTELLIGENCE_ORDINAL[profile.intelligence]
        - MONSTER_INTELLIGENCE_ORDINAL[MONSTER_TALK_REPLY_INTELLIGENCE[reply]]
    )
    if intel_distance > MONSTER_TALK_REPLY_INTELLIGENCE_VARIANCE[reply]:
        return False
    if reply is MonsterTalkReply.R_MATE and not profile.can_offer_mate_quest:
        return False
    if reply is MonsterTalkReply.R_SELL and not has_purchasable_treasure:
        return False
    return True


def select_monster_talk_reply(
    monster: Monster, rng: random.Random, *, has_purchasable_treasure: bool = False
) -> MonsterTalkReply | None:
    """The real reply selector: Sphinx's own confirmed 50%-forced
    `RRiddle` special case, then a uniform-id-propose/`repfreq`-accept
    rejection loop restricted to the eligible replies -- mathematically
    the same `repfreq[r] / sum(repfreq[q] for q in eligible)` weighted
    choice the source itself gives as the closed form, but implemented
    as the real described loop rather than the reduction, matching this
    project's own convention of modelling the real algorithm shape
    where one is given. Returns `None` only if no reply is eligible at
    all (never observed for any real `Monster`, but not assumed
    impossible). Uses `random.Random`, not `PascalRandom` -- like
    `resolve_talk_reaction()` above, this is Monte-Carlo-verified
    against the source's own stated frequencies, not a byte-exact
    reproduction of a real captured trace (none exists for this
    routine).
    """

    if monster is Monster.SPHINX and rng.random() < 0.5:
        return MonsterTalkReply.R_RIDDLE

    eligible = [
        reply
        for reply in MonsterTalkReply
        if monster_talk_reply_eligible(reply, monster, has_purchasable_treasure=has_purchasable_treasure)
    ]
    if not eligible:
        return None

    all_replies = list(MonsterTalkReply)
    while True:
        candidate = rng.choice(all_replies)
        if candidate not in eligible:
            continue
        if rng.random() < MONSTER_TALK_REPLY_FREQUENCY[candidate] / 10:
            return candidate


# Say [SA] and Fulfill [FU], rulebook [5.6]/[5.7] -- Phase 240.
#
# **Say**: "Un personaggio può dire (Say) tutte le parole indicate dal
# giocatore, entro un limite di 160 caratteri. Questa azione non fa
# consumare tempo di combattimento. La successiva tattica del
# personaggio è eseguita nello stesso round di combattimento della
# tattica Say." A flat-out no-op for this project's own tactic walk --
# already exactly what `turn/search_execution.py`'s existing "unwired
# maneuvers are silently skipped, keep walking" fallback does (skipping
# consumes no round and immediately proceeds to the next tactic, the
# same behavior "doesn't consume combat time" describes). Given its own
# explicit `Maneuver.SAY` branch as of this phase purely to document
# that this is deliberate, not incidental.
#
# **Fulfill**: "Quando un mostro propone un accordo, il personaggio può
# onorarlo (Fulfill) dopo aver accettato le sue condizioni ... Non
# sempre però il mostro tiene fede al suo impegno, specialmente se è un
# mostro Malvagio e/o se il suo Allineamento è molto differente da
# quello del personaggio." "Dopo aver accettato le sue condizioni"
# ("after accepting its conditions") -- together with "Non è possibile
# usare sia la tattica Talk che Fulfill nello stesso Piano d'Incontro"
# ("Talk and Fulfill can't both be used in the same Encounter Plan") --
# reads as Fulfill honoring a deal a *previous turn's* Talk already
# secured, not one from later in the same plan. Needed a "this Feature
# has a pending deal with this leader" state persisted on `Feature`
# across turns -- added as of Phase 258 (`Feature.pending_deal_leader_id`,
# `models/feature.py`; set by `turn/search_execution.py`'s own Talk
# `DEAL` branch, consumed and cleared by its new Fulfill branch).
#
# **`resolve_fulfill_honored()` below is project-original, confirmed
# directly with the user (project author)**: the rulebook quote above
# is entirely qualitative (no numeric formula, no definition of what
# the deal's own "conditions" concretely are) -- so, rather than invent
# deal *content* (an item, a gold amount, ...) with nothing to source it
# from, this project models only the abstract "was the deal honored"
# roll the quote actually describes, the same narrow-but-honest slice
# `turn/plan_dispatch.py`'s own Recruit/Hire co-location checks already
# take for similarly under-specified mechanics. The formula reuses
# `models/alignment.py ALIGNMENT_ORDINAL` (already load-bearing for
# Hire's ">2 ordinal positions apart" rule and `Align_Est`) for "how far
# apart" the two alignments genuinely are, plus a flat penalty when the
# guardian is Evil (`Feature.guardian_alignment`, Phase 246) -- both
# constants (`FULFILL_BASE_HONOR_CHANCE`, `FULFILL_ALIGNMENT_DISTANCE
# _PENALTY_PER_STEP`, `FULFILL_EVIL_PENALTY`) are unsourced, confirmed
# design choices, the same "no numeric split given anywhere" category
# `TALK_ATTACK_CHANCE`/`TALK_IGNORE_CHANCE`/`TALK_DRUIDIC_ATTACK_CHANCE`
# above already document for Talk's own reaction roll. A `None`
# alignment on either side (a guardian with no `guardian_alignment` set,
# or a leader with no `LeaderState.alignment` recorded) skips the
# distance term entirely rather than guessing a substitute value.
FULFILL_BASE_HONOR_CHANCE = 0.75
FULFILL_ALIGNMENT_DISTANCE_PENALTY_PER_STEP = 0.05
FULFILL_EVIL_PENALTY = 0.20


def resolve_fulfill_honored(
    guardian_alignment: Alignment | None, character_alignment: Alignment | None, rng: random.Random
) -> bool:
    """Whether the guardian honors a deal a prior Talk secured -- see the
    module comment above for the formula's own sourcing and constants.
    """

    chance = FULFILL_BASE_HONOR_CHANCE
    if guardian_alignment is not None and character_alignment is not None:
        distance = abs(ALIGNMENT_ORDINAL[guardian_alignment] - ALIGNMENT_ORDINAL[character_alignment])
        chance -= distance * FULFILL_ALIGNMENT_DISTANCE_PENALTY_PER_STEP
    if guardian_alignment is Alignment.EVIL:
        chance -= FULFILL_EVIL_PENALTY
    return rng.random() < max(0.0, min(1.0, chance))


# Beg [BE], rulebook [5.8] -- Phase 241. No Pascal source and no
# rulebook text survive for this tactic (confirmed: `CBeg` appears only
# in `CTBOTH.PAS`'s own `maneuver` enum declaration, never referenced
# by name anywhere else in the available archive). Designed
# collaboratively with the user (project author), who confirmed the
# concept directly: a Cowardly-tempered character (or any character, in
# extremis) begging a monster or another Hero for mercy to avoid being
# killed.
#
# Three design questions, all answered directly by the user:
# 1. **Only meaningful after the character has already taken damage
#    this same encounter** -- an undamaged character has nothing to
#    beg about. Checked via `Combatant.hit_points < CHARACTER_HIT_
#    POINTS` (every combatant starts at the flat rulebook value, [5.0]
#    "In combat, all characters have 10 hit points" -- no per-leader
#    starting-HP variation exists to complicate this check).
# 2. **Only monsters intelligent enough to understand a plea can grant
#    mercy** -- reuses the existing, real per-species `MIRROR_IMAGE_
#    MONSTER_INTELLIGENCE_TIER` (Phase 187) directly rather than a new
#    mapping, since all six of its tiers are meaningful here (not
#    collapsed to three buckets the way Steal's own cunning table was
#    -- see that table's own Phase 239 addendum for why that collapse
#    was appropriate there but isn't needed here).
# 3. **A successful plea ends the encounter exactly like a successful
#    Flee** -- the character escapes unharmed, no further combat, no
#    loot.
#
# The per-tier mercy chances themselves are project-original -- no
# source gives numbers, only the qualitative "sufficiently intelligent"
# gate above. Animal/Mechanical tiers get a flat 0%: they're confirmed
# unable to even understand a plea, not merely unlikely to grant one.
BEG_MERCY_CHANCE: dict[MirrorImageIntelligenceTier, float] = {
    MirrorImageIntelligenceTier.DIVINE_OR_SUPERHUMAN: 0.60,
    MirrorImageIntelligenceTier.HIGH_HUMAN: 0.45,
    MirrorImageIntelligenceTier.MEDIUM_HUMAN: 0.30,
    MirrorImageIntelligenceTier.LOW_HUMAN: 0.15,
    MirrorImageIntelligenceTier.ANIMAL: 0.0,
    MirrorImageIntelligenceTier.MECHANICAL: 0.0,
}


def resolve_beg_for_mercy(tier: MirrorImageIntelligenceTier, rng: random.Random) -> bool:
    return rng.random() < BEG_MERCY_CHANCE[tier]


def loot_defeated_leader(state: GameState, *, winner_id: int, loser_id: int) -> list[ItemInstance]:
    """[5.9] "Victory and Death": "looting a vanquished foe's treasure, magic
    items changing hands" -- transfers every item ``loser_id`` owned to
    ``winner_id``. See module docstring's own Phase 313 addendum for which
    call sites wire this in (every character-vs-character death) and which
    deliberately don't (army-vs-army battle deaths). Called *after*
    ``GameState.remove_leader(loser_id)`` at every real call site, but order
    doesn't actually matter -- item ownership (``ItemInstance.owner_leader_id``)
    is tracked independently of ``GameState.leaders``, so a dead leader's own
    items simply sit orphaned-but-still-owned by their id until reassigned.
    Returns the transferred items (for a caller that wants to narrate the
    loot later), or an empty list if the loser owned nothing.
    """

    looted = state.items_held_by(loser_id)
    for item in looted:
        state.transfer_item(item.item_id, winner_id)
    return looted
