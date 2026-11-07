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
damage points per swing." -- flat 50% *hit chance*, **not** skill-scaled
(unlike Fire Arrow); the Melee `Ability` level still matters for
initiative ordering per [5.0]'s generic rule. **Damage, however, does
scale with skill** (sourced directly from the user, 2026-10-28, who
corrected this module's own prior reading): "+1 per differenza nel
Talento Melee tra chi attacca e chi difende" -- on a successful hit,
``roll_melee_attack()``'s own ``skill_difference_bonus`` parameter adds
``max(0, attacker's effective Melee skill - defender's)`` to the die
roll, so a more-skilled attacker hits harder but a less-skilled one
never does less than the base 1-6 die.

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
phase**, for the same reason as Phase 179's own primitives: this is
the first of an unknown-sized set of Personal-Combat spells the user
is walking through "nelle prossime sessioni" (across future sessions) --
wiring a real `CAST`-tactic combat engine before more of that set is
known would mean redesigning it repeatedly as each new spell arrives.
**Stale as of a later phase**: a real `CAST`-tactic engine was in fact
built once the full spell set was known -- `holy_symbol_hit_chance()`/
`roll_holy_symbol_undead_damage()` are both real, wired call sites in
`turn/challenge_execution.py`/`turn/search_execution.py` today.

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
phase**, for the same reason as Holy Symbol (Phase 180): more
Personal-Combat spells are still to come across future sessions.
**Stale as of a later phase**: `spiritwrack_melee_damage_reduction()`
is a real, wired call site in `turn/challenge_execution.py`/`turn/
search_execution.py` today, alongside Holy Symbol.

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
phase**, same reason as every other Personal-Combat spell above -- and
the narration itself ("(eroe o mostro) incanta...") belongs in
`report/turn_report.py` alongside `render_flee_failure()` when a real
CAST-tactic engine exists to call it, not in this module (which never
renders prose). **Stale as of a later phase**: both `turn/challenge_
execution.py` and `turn/search_execution.py` now dispatch `Spell.CHARM`
directly to a guaranteed `fled=True` outcome ("the caster flees, same
outcome as a successful `Maneuver.FLEE`"), the exact mechanic this
constant names -- implemented as an unconditional branch at the real
call site rather than by referencing `CHARM_FLEE_ALWAYS_SUCCEEDS`
itself.

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
opponent can't act during?) is left to a future tactic-walk engine,
same "not wired into `turn/search_execution.py` yet" scoping as every
other Personal-Combat spell above -- **stale as of a later phase**:
`roll_psychic_blast_stun_rounds()` is a real, wired call site in
`turn/challenge_execution.py`/`turn/search_execution.py` today,
crediting the returned round count onto `Combatant.bonus_unanswered_
attacks` (the same "extra Melee swings" reading this addendum itself
already anticipated).

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
- Invisibility's own effect on a Steal attempt is now the real formula's
  own `I`/`E` terms directly (`steal_success_chance()`, module
  docstring's own Phase 506 addendum) -- superseding the earlier flat
  +15-percentage-point placeholder this addendum used to describe.

**Correction (Phase 881)**: `invisibility_reduced_hit_chance()` itself
was never actually called anywhere -- the real halving is applied
directly to `Combatant.defensive_hit_multiplier` at the two real
Invisibility-cast sites (`turn/challenge_execution.py`/`turn/search_
execution.py`), reaching `fire_arrow_hit_chance()`/`resolve_one_melee_
round()` through that shared field the same way every other personal-
combat defensive buff does (Holy Symbol, etc.) -- not through this
standalone helper, which stays unused. Same phase wires `Discovery.
INFRARED_GOGGLES` in at those same two sites: "defensive protection
will be only 20%, not 50%" for whoever's fighting the invisible caster,
when that character's own Kingdom holds the Discovery -- see
`INFRARED_GOGGLES_HIT_CHANCE_MULTIPLIER`'s own comment.

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

**The full outcome tree** (now fully executed by `resolve_mirror_image_
duel()`, Phase 210 -- see below):

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

**What this phase itself models**: the two disbelief-chance formulas
only (`MirrorImageIntelligenceTier`, `MIRROR_IMAGE_DISBELIEF_BASE_
CHANCE`, `mirror_image_disbelief_chance()`, `resolve_mirror_image_
disbelief()`, and the Stage-2 `MIRROR_IMAGE_MASTER_DISBELIEF_BASE_
CHANCE`) -- these are the same "clean, testable primitive" shape every
other spell in this file already uses. At the time this addendum was
written, the actual duel resolution (illusion-vs-opponent, then
caster-vs-illusion) and the round-by-round state transitions between
the three outcome branches above were not modeled -- but both duels
*do* reuse this module's own existing `Combatant` machinery (the
illusion is explicitly "an exact stat-copy of the opponent," so a
cloned `Combatant` resolves it faithfully), orchestrated by `resolve_
mirror_image_duel()` (Phase 210, below) -- a real, wired call site in
`turn/challenge_execution.py`/`turn/search_execution.py` today. **Stale
as of Phase 210**: this addendum's own "not wired into `turn/search_
execution.py` yet" framing. **Also stale, corrected here**: the "a
normal `resolve_melee_duel()` call resolve it faithfully" claim --
`resolve_mirror_image_duel()`/`resolve_illusory_hero_duel()` (below)
each use their own small, hand-rolled per-round Melee loop (no hit-
chance roll, no `offensive_hit_multiplier`/`defensive_hit_multiplier`/
weapon procs -- only `melee_skill`, `melee_damage_range`, `always_acts_
first`, and `damage_reduction` are ever consulted), never `resolve_
melee_duel()`/`resolve_one_melee_round()` -- a deliberate, still-
standing simplification (see Phase 783 addendum below), not a stale
claim about *this* specific mechanism being unwired.

**The "double dissipation" rule** ("if another Mirror-Image spell is
cast while the illusion is fighting, both illusions will dissipate")
is likewise left as a documented fact only, not code -- it has no
numeric magnitude to model and no consuming engine to hook into yet.

**Phase 783 addendum -- `AKGEN_reverse_engineering_report (2).md`
SS21.2/21.4/21.7 gives the real compiled disbelief formula and illusion-
copy semantics in full, resolving two real bugs in the code above/below**
(SS21.4's own `D` term had already been mined once, Phase 463, for
`DETECT_ILLUSIONS_DISBELIEF_BONUS` -- this addendum is the first full
read of the section). The real formula: `T = 20(I+1) + 25D + 25R -
15(Le+H)`, `P = clamp(T, 0, 100)%` (`I`=intelligence ordinal, `D`=1 if
the current disbeliever holds Detect Illusions, `R`=1 only in Stage 2,
`Le`=min(effective Illusionist level, 4), `H`=0 for Mirror-Image, 1 for
Illusory Hero). Every Mirror-Image-only figure (both stages, with or
without Detect Illusions) already matched this formula exactly, hand-
verified against SS21.4/21.5's own worked tables -- no bug there. Two
real, fixed bugs: (1) `illusory_hero_disbelief_chance()` used to clamp
the Mirror-Image value first, then subtract Illusory Hero's own `H`
malus and clamp again -- a double clamp that under-valued the true
chance whenever the raw threshold exceeded 100% before the malus (e.g.
Divine/Superhuman intelligence at low caster skill used to read 85%
instead of the correct 100%); fixed by combining the level reduction
and the `H` malus into one subtraction before a single clamp. (2)
`resolve_mirror_image_duel()`/`resolve_illusory_hero_duel()`'s own
`illusion` `Combatant` used to copy only 3 fields (`hit_points`,
`melee_skill`, `melee_damage_range`) instead of the full record SS21.2
confirms the real engine memcpy's wholesale (178 bytes, "gli altri
campi già materializzati... vengono copiati", explicitly naming already-
active Invisibility/Holy Symbol as examples); fixed via `dataclasses.
replace()`, with `always_acts_first` explicitly reset to False
afterward (a fresh illusion is never the ILLUS_MAGE titleholder itself).
Since the hand-rolled melee loop above only ever reads `damage_
reduction` besides the 3 already-copied fields, this bug had one real
consequence: an opponent/hero's own Imperial Defender armor didn't
protect their illusion. Deliberately not attempted: rewriting the
hand-rolled melee loop itself to use the full combat engine (a separate,
larger redesign question), and SS21.7's own "bersaglio non distinto"
edge case (no valid distinct opponent refuses the cast outright,
`_LSpIneff`) -- a real, separate, smaller finding.

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
`PERSONAL_COMBAT_SPELL_CAST_CHANCE_CAP` -- **corrected to `1.00` at
Phase 467**: originally set to the same 0.95 ceiling `turn/cast_
execution.py`'s own `ACTION_SPELL_CHANCE_CAP` uses for Action-Cast
spells, on the assumption both caps were "one shared universal rule."
`AKGEN_reverse_engineering_report (2).md` SS21.1 now gives the real
compiled Personal-Combat-spell formula (`AK.OVR 0x18A75`,
`clamp_0^100(30+15*L_c+10*P)`) and its own worked table showing a
level-4 Pagan caster reaching exactly 100%, not 95% -- so the "shared
rule" assumption was wrong for this side specifically (`ACTION_SPELL_
CHANCE_CAP`'s own 95% is untouched: the disassembly evidence here only
covers the Personal-Combat branch, not Action-Cast, so "no source, no
guess" leaves that constant as-is). `personal_combat_spell_cast_chance(
skill_level, *, caster_is_pagan=False)` computes the base+per-level
chance, adds `PERSONAL_COMBAT_PAGAN_MAGE_ORDER_BONUS` (0.10) when
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

**Also confirmed, now both wired**: the quoted text also describes
per-turn Action-Cast quotas (1 cast/turn, 2 at skill level 3, 3 at
level 4) -- live since before this session (`turn/cast_execution.py
action_cast_slots()`/`_consume_action_cast_slot()`, `GameState.
action_casts_used`) -- and a per-encounter "not twice with the same
Personal-Combat spell" limit, plus its own `combat_slots_per_school`
sibling rule -- both wired by Phase 732 (`try_consume_combat_cast_
slot()` below), scoped to a purely local, per-encounter pair of
trackers rather than any `GameState`-level state (the per-*turn* half
above is the one that genuinely needed `GameState` persistence; the
per-*encounter* half never did).

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
spell already uses is passed and the cast succeeds.

**Phase 655 correction, kept for the record**: this paragraph used to
also claim `spell_disruption_chance()` itself "is still never rolled
anywhere in `turn/search_execution.py`'s own tactic walk" -- false,
and already stale by Phase 654's own edit of it (which only reframed
the comparison to Challenge/Pursue without re-checking this module's
own code): `turn/search_execution.py _resolve_melee_range_round()`
(Phase 293, predating this correction by a wide margin) already rolls
`resolve_spell_disruption()`/`resolve_spell_disruption_from_missed_
attack()` bidirectionally every time a `CAST` tactic is reached at
`CombatRange.MELEE_RANGE`, on either side.

**Phase 730 -- the narrower gap this correction itself flagged is now
closed too**: both `turn/search_execution.py _resolve_melee_range_
round()` and `turn/challenge_execution.py resolve_challenge_combat()`
now call a small, per-module `_resolve_cast_disruption(pending_cast,
damage, rng)` helper at every real disruption-roll call site instead
of `resolve_spell_disruption()`/`resolve_spell_disruption_from_missed_
attack()` directly -- it checks whether the tactic actually being
disrupted (`Spell(pending_cast.sub_object)`) is `Spell.HEAL` and, if
so, rolls `words_of_healing_disruption_chance()`'s own halved formula
via `resolve_words_of_healing_disruption()`/`resolve_words_of_healing_
disruption_from_missed_attack()` instead of the generic one. Every
other spell (and a `None`/unresolvable `pending_cast`) still reaches
the ordinary, un-halved roll unchanged.

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
   (Phase 202 addendum) -- at the time this addendum was written, no
   orchestration engine existed yet to consume either clone. **Stale
   as of Phase 210**: `resolve_illusory_hero_duel()` (below) builds
   exactly this clone from `hero`'s own stats and consumes it directly.
4. **The actual duel outcome tree**, the same "clean, testable
   primitives only" boundary as Mirror-Image's own three-stage outcome
   tree above (disbelief -> duel -> possible Stage-2 duel) -- this
   spell only changes two of Mirror-Image's own numeric inputs (the
   disbelief reduction and the master-disbelief precondition), so it
   reuses `resolve_mirror_image_duel()`'s own engine rather than adding
   a new one -- see `resolve_illusory_hero_duel()` (Phase 210, below).

**Wired into `turn/search_execution.py`'s and `turn/challenge_
execution.py`'s combat resolution as of Phase 210** -- both real,
production call sites use `resolve_illusory_hero_duel()` directly.
This addendum's own earlier "not wired... same reason as every other
Personal-Combat spell above" framing is stale.

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

**Stale as of Phase 898, two of these three claims deep.** "Implorare
pietà" closed at Phase 749 (`mercy_chance()`/`resolve_beg_for_mercy()`
below -- a real, disassembled formula, not the "~50%" guess this
paragraph still names); the Cautious flee bonus closed at Phase 743
(`WEAK_TEMPER_FLEE_CHANCE_BONUS`, `turn/challenge_execution.py`/`turn/
search_execution.py`). This phase closes the *refusal*-to-Meet half of
the remaining pair too -- see `refusal_to_meet_chance()`/`resolve_
refusal_to_meet()` below, and `turn/challenge_execution.py execute_
challenge()`'s/`turn/battle_orchestrator.py _maybe_fight_duel()`'s own
Phase 898 addenda for the two real consumers this unblocks (the second
of which, `_maybe_fight_duel()`'s `coward_bluff`, had been naming this
exact primitive as its own missing dependency since Phase 389).
**Still genuinely open, narrower than this paragraph originally scoped
it**: only the *involuntary automatic flee* half survives -- a weak-
tempered character fleeing without being ordered to at all
("indipendentemente dal Piano d'Incontro"), gated on "when the risk of
a mortal blow appears significant" (Cautious) / "when death is
possible" (Cowardly). Unlike an explicit `Maneuver.FLEE` tactic, Beg, or
the refusal-to-Meet check below (each resolved once, at a single,
caller-chosen point in the tactic walk or dispatch), this needs a
per-round "is death/a mortal blow currently at stake" risk measure this
project has no primitive for anywhere -- a real, separate, still-open
follow-up, not attempted here.

**Phase 516 addendum -- `AdvancedAbility.MELEE_HIT_POINTS`.**
`models/advanced_ability.py`'s own sourced text: "The Gods grant 1-5
additional hit points in any encounter." `MELEE_HIT_POINTS_ABILITY_
BONUS_RANGE = (1, 5)`, `roll_melee_hit_points_ability_bonus(rng)`, and a
new `Combatant.has_melee_hit_points_ability: bool = False` field --
exactly the same shape as Furia's own bonus above (a flat, one-time roll
added to a combatant's starting `hit_points`), so it is applied inside
`apply_temper_melee_setup()`'s own per-combatant loop rather than via a
new call site: real coverage through that function's existing three real
callers (`resolve_melee_duel()`'s internal default call, plus
`challenge_execution.py`'s/`search_execution.py`'s own direct calls for
their round-stepping engines). The new `Combatant` field is set by each
of the six per-consumer `_leader_combatant()`/`_commander_combatant()`/
`_kill_enemy_combatant()` builders (`battle_orchestrator.py`,
`cast_execution.py`, `challenge_execution.py`, `patrol_execution.py`,
`pursue_execution.py`, `search_execution.py`) via `AdvancedAbility.
MELEE_HIT_POINTS in leader.advanced_abilities`, mirroring `temper=leader.
temper`'s own Phase 284 wiring -- full, real coverage in a single phase,
unlike most other Melee Advanced Abilities unwired *at the time this
addendum was written* (Duellists Medal, Mastery, True Mastery), which
needed a new "+damage dealt" `Combatant` field this module had never
had before -- all three are wired now (Phase 517/518 addenda below).

**Phase 517 addendum -- `AdvancedAbility.MELEE_MASTERY`/`MELEE_TRUE_
MASTERY`.** `models/advanced_ability.py`'s own sourced text: Mastery
"gains a plus 10% chance to hit and plus 1 damage (the opponent in
melee does not get a -10% chance or less damage)"; True Mastery "gains
a plus 2 damage (the opponent in melee does not get a -10% chance or
less damage)" -- the explicit "no opponent penalty" clause distinguishes
both from Duellists Medal, which *does* apply a symmetric penalty but
only against humanoid targets (needed an "is the opponent humanoid"
check this module had no other reason to have yet, so it stayed out of
scope in *this* addendum -- wired the very next phase, see the Phase
518 addendum below).

New `Combatant.melee_damage_dealt_bonus: int = 0` field (the attacker-
side counterpart to `melee_damage_dealt_reduction` above), plus two pure
functions -- `melee_mastery_offensive_hit_multiplier(advanced_abilities)`
(the "+10%" read multiplicatively, same convention as Slancio) and
`melee_mastery_damage_bonus(advanced_abilities)` (the flat "+1"/"+2") --
called once, at `Combatant` construction time, by each of the six
per-consumer builders (mirroring Phase 516's own wiring across the same
six files), seeding `offensive_hit_multiplier`/`melee_damage_dealt_
bonus` directly rather than adding a new boolean flag: unlike Melee Hit
Points' one-time setup roll, these two abilities are static per-swing
modifiers with no RNG of their own, so there is no "roll once, at
setup" step to hook into -- the numbers are simply already correct the
moment the `Combatant` is built. A leader only ever holds one Advanced
Ability per category (this module's own module docstring, Phase 128),
so Mastery and True Mastery are mutually exclusive in practice;
`melee_mastery_damage_bonus()` still resolves deterministically if that
assumption were ever violated (True Mastery's own higher bonus wins).

The two real per-swing damage sites (`resolve_one_melee_round`,
`resolve_reactive_melee_swing`) now share a new `_melee_landed_damage()`
helper instead of duplicating the modifier arithmetic -- a pure
refactor when `melee_damage_dealt_bonus` is 0 (every pre-Phase-517
caller), and the one place the new bonus is applied, gated behind
`raw_damage > 0` so a flat bonus can never turn a miss into a hit. The
Mirror-Image/Illusory-Hero illusion duels (`resolve_mirror_image_duel`/
`resolve_illusory_hero_duel`) are deliberately NOT threaded through this
helper -- same Phase 516 scope boundary: those functions fight with
freshly-built `Combatant`s that never carry a real leader's own Advanced
Ability data in the first place.

**Stale as of Phase 1050 -- this paragraph's own claim was wrong.**
Directly checking both real call sites (`turn/challenge_execution.py`,
`turn/search_execution.py`) shows `caster`/`opponent` passed into these
two duels are always real leader `Combatant`s built by the same
`_leader_combatant()` every ordinary Melee duel uses, and the
throwaway `illusion` itself is a full-record copy of one of them
(Phase 783 below) -- not a stripped-down placeholder. There was never
a real reason these two duels couldn't call the shared helpers; they
simply never had. Closed by routing both duels' own melee exchanges
through `resolve_one_melee_round()` itself (not just `_melee_landed_
damage()` in isolation), which also closes the matching gaps this
same stale reasoning left in weapon on-hit procs and end-of-round
regeneration -- see each function's own Phase 1050 addendum.

**Phase 518 addendum -- `AdvancedAbility.MELEE_DUELLISTS_MEDAL`.**
`models/advanced_ability.py`'s own sourced text: "When fighting against
humanoid creatures, the character has a plus 10% chance to hit and plus
1 damage in melee, while the opponent has -10% chance to hit and -1
damage." Unlike Mastery/True Mastery, this one *does* carry an opponent
penalty, but conditionally: only when the opponent is humanoid
(`models/race.py HUMANOID_RACES` -- "men, elves, orcs and dwarves"),
which the previous phase's own addendum flagged as the reason this
ability stayed out of scope until now.

New `Combatant.is_humanoid: bool = False` and `Combatant.has_duellists_
medal_ability: bool = False` fields, both set by each of the same six
per-consumer builders from `leader.race if leader.race is not None else
kingdom.race` (the exact resolution `report/turn_report.py`/`turn/
hire_pay.py` already use for "this leader's own effective race" --
Phase 196's own precedent) checked against `HUMANOID_RACES`. A monster
combatant's own builder never sets `is_humanoid`, leaving the correct
default (`False` -- no monster is ever humanoid).

Wired into `apply_temper_melee_setup()`'s own per-combatant loop (see
that function's own Phase 518 addendum) rather than the two Mastery
functions' "seed at construction time" shape, because this ability's
effect depends on the *opponent's* own property (humanoid or not) --
the same reason Intimidazione (Phase 284) already lives in that loop
instead of at construction time. Reads "the character has..., while the
opponent has..." as two separate *offensive* swings (this combatant's
own `offensive_hit_multiplier`/`melee_damage_dealt_bonus`, not a
defensive multiplier on incoming hits) -- both sides described in the
source are the medal-bearer's opponent's own hit chance/damage, not a
change to how easy either side is to hit.

Fifth of six Melee category Advanced Abilities wired (5/6) -- only
Control Temper remains, and its own sourced text ("the temper is
usually adjusted to whatever temper gains the most favorable benefits
in combat") gives no concrete trigger or magnitude to model, a
candidate for "documented, not modeled" rather than a guess.

**Phase 519 addendum -- `AdvancedAbility.MELEE_CONTROL_TEMPER`, closing
out the Melee category.** `models/advanced_ability.py`'s own sourced
text: "With this ability, the Berserk temper is used initially to gain
the extra 1-4 hit points, then the temper is usually adjusted to
whatever temper gains the most favorable benefits in combat." Split in
two by this phase, per the project's own "no source, no guess" policy:

1. **Modeled.** "The Berserk temper is used initially to gain the extra
   1-4 hit points" is concrete and unambiguous -- the same numeric range
   and mechanic Furia (Phase 284) already uses. New `Combatant.has_
   control_temper_ability: bool = False` field, set by the same six
   per-consumer builders, consulted by `apply_temper_melee_setup()`'s
   own per-combatant loop: one `berserk_fury_bonus_hit_points(rng)` roll
   added to `hit_points`, independent of this combatant's own real
   `.temper` (the ability grants this regardless of what temper, if any,
   is actually recorded -- "used initially" reads as "at the start of
   combat, as if Berserk," not "only if genuinely Berserk"). If a
   combatant happens to hold this ability *and* have a genuinely-Berserk
   `.temper`, both rolls apply and stack; no source disambiguates that
   overlap, so it stays a deliberate, documented quirk.
2. **Not modeled.** "Then the temper is usually adjusted to whatever
   temper gains the most favorable benefits in combat" names no trigger
   (when does the adjustment happen -- every round? once, at setup?)
   and no algorithm for "most favorable" (favorable against what --
   the opponent's current temper? their own hit points? a lookahead
   simulation, the way Augur Combat's own silent-simulation mechanic
   works?). Guessing any of these would be exactly the kind of
   unsourced magnitude/trigger this project's own module docstring
   (Phase 128) declines to invent. Left undone, documented here rather
   than silently dropped.

With this phase, all six Melee category Advanced Abilities have been
addressed: Evasion, Hit Points, Mastery, True Mastery, and Duellists
Medal fully wired; Control Temper partially wired with its ambiguous
residual explicitly documented as out of scope.

**Phase 520 addendum -- Archery category, "Free Attack" tiers.**
`models/advanced_ability.py`'s own sourced text for `AdvancedAbility.
ARCHERY_FREE_ATTACK`/`ARCHERY_FREE_ATTACK_MASTERY`/`ARCHERY_FREE_ATTACK_
TRUE_MASTERY` is identical across all three: "One more free attack is
gained when using the Fire tactic in personal combat." Unlike Melee's
Mastery/True Mastery pair (Phase 517), which had two distinct
magnitudes, these three tiers share one -- a leader only ever holds one
Advanced Ability per category (Phase 128), so holding any one of the
three is mutually exclusive with the other two and grants the same flat
`ARCHERY_FREE_ATTACK_BONUS = 1`. New pure function `archery_free_attack_
bonus(advanced_abilities)` and `Combatant.archery_free_attack_bonus: int
= 0`, seeded once at `Combatant` construction time by the same six
per-consumer builders (static, opponent-independent, RNG-free -- same
"seed at construction" shape as Melee Mastery, not `apply_temper_melee_
setup()`'s per-combatant loop). `resolve_fire_arrow_duel()`'s own shot
counts (`shots_a`/`shots_b`) now add this bonus on top of `fire_arrow_
free_attacks(archery_skill)`.

Deliberately **not** addressed this phase: `AdvancedAbility.SHORT_RANGE_
ARCHERY`/`LONG_RANGE_ARCHERY` (the category's other two members) --
"the Archer may now use the Fire tactic at Melee Range, with the normal
chance to hit" / "at Spell Range, with half the normal chance to hit."
This project's own existing range-gating logic (`turn/challenge_
execution.py`/`turn/search_execution.py`'s own `CombatRange` state
machines) already lets a Fire order transparently close from any
starting range to Bow Range and fire from there in the same tactic-step
-- it only ever blocks Fire outright at Melee Range. Whether these two
abilities are meant to unlock firing *without* closing in (staying at
Melee/Spell Range) or something else the existing model doesn't already
allow is genuinely ambiguous without the real Pascal source for that
specific interaction -- left undone rather than guessed, same "no
source, no guess" boundary as Melee Control Temper's own residual.

**Phase 700 addendum -- `LONG_RANGE_ARCHERY` resolved.** Re-reading
`turn/challenge_execution.py resolve_challenge_combat()`'s own `SHOOT`
branch precisely (not just by inference) confirmed the ambiguity above:
that branch unconditionally closes to Bow Range before firing, so the
ability's own text only describes a real behavior change if it lets
the archer skip that step and fire from Spell Range itself, at half
accuracy. The user directly confirmed the one remaining open question
(what the target does in return): the exchange is one-sided -- the
target gets no return fire (no Archery is possible at Spell Range
without the ability) and no melee counter (too far away), only a Cast
counter, which this project's shared function already resolves
independently and upfront regardless of range. `resolve_fire_arrow_
duel()`'s new `long_range_archer` parameter (below) implements exactly
this.

**Phase 701 addendum -- `SHORT_RANGE_ARCHERY` resolved.** The user
directly confirmed the open question above: a target at Melee Range
does get a reactive Melee counter-swing against the archer (mirroring
this project's own existing Cast-at-Melee-Range reactive-swing
pattern), then the archer's own shot resolves one-sided (the target
gets no return fire in kind) at the *normal* chance to hit, per this
ability's own text ("with the normal chance to hit," no halving the way
Long Range Archery has). `resolve_fire_arrow_duel()`'s new `short_
range_archer` parameter (below) implements the one-sided-shots half;
the reactive Melee swing itself is resolved by the caller, in `turn/
challenge_execution.py`'s own `SHOOT` branch, before this function is
ever called.

**Phase 719 -- `turn/search_execution.py`'s own separate, duplicated
`CombatRange`/`SHOOT` state machine (leader-vs-monster Search combat)
now wires both abilities too**, via the exact same `long_range_archer`/
`short_range_archer` kwargs on `resolve_fire_arrow_duel()` above -- see
that module's own Phase 719 addendum for the one real structural
difference (no intermediate Bow-Range step exists in that engine).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, replace
from enum import Enum
from typing import Literal

from ak_engine.models.advanced_ability import AdvancedAbility
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
from ak_engine.models.treasure import (
    BOW_OF_ELVEN_KINGS_ARCHERY_DAMAGE_BONUS,
    BOW_OF_ELVEN_KINGS_ARCHERY_HIT_BONUS,
    HOLY_SWORD_DAMAGE_BONUS_VS_UNDEAD,
    HOLY_SWORD_HIT_BONUS_VS_UNDEAD,
    WEAPON_DAMAGE_BONUS,
    WEAPON_HIT_BONUS,
    Treasure,
)

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

# Phase 516: AdvancedAbility.MELEE_HIT_POINTS -- "The Gods grant 1-5
# additional hit points in any encounter" (models/advanced_ability.py
# ADVANCED_ABILITY_DESCRIPTION). Same shape as Furia's own bonus above --
# a flat, one-time roll added to the holder's starting hit points -- so it
# is applied alongside Furia in apply_temper_melee_setup() rather than
# via a new call site.
MELEE_HIT_POINTS_ABILITY_BONUS_RANGE = (1, 5)

# Phase 517: AdvancedAbility.MELEE_MASTERY -- "A character gains a plus
# 10% chance to hit and plus 1 damage (the opponent in melee does not
# get a -10% chance or less damage)" -- and AdvancedAbility.MELEE_TRUE_
# MASTERY -- "A character gains a plus 2 damage (the opponent in melee
# does not get a -10% chance or less damage)" (models/advanced_ability.py
# ADVANCED_ABILITY_DESCRIPTION). The stated "+10%" reads multiplicatively,
# the same convention this module's own Phase 284 addendum already
# established for Slancio ("base * (1 + 0.10)", not "base + 10
# percentage points").
MELEE_MASTERY_HIT_CHANCE_BONUS = 0.10
MELEE_MASTERY_DAMAGE_BONUS = 1
MELEE_TRUE_MASTERY_DAMAGE_BONUS = 2

# Phase 518: AdvancedAbility.MELEE_DUELLISTS_MEDAL -- "When fighting
# against humanoid creatures, the character has a plus 10% chance to hit
# and plus 1 damage in melee, while the opponent has -10% chance to hit
# and -1 damage" (models/advanced_ability.py ADVANCED_ABILITY_
# DESCRIPTION). Same +-10%-is-multiplicative convention as Mastery above.
MELEE_DUELLISTS_MEDAL_HIT_CHANCE_BONUS = 0.10
MELEE_DUELLISTS_MEDAL_DAMAGE_BONUS = 1

# Phase 520: Archery category, all three "Free Attack" tiers
# (AdvancedAbility.ARCHERY_FREE_ATTACK / _MASTERY / _TRUE_MASTERY) share
# the identical sourced text -- "One more free attack is gained when
# using the Fire tactic in personal combat" (models/advanced_ability.py
# ADVANCED_ABILITY_DESCRIPTION). A leader only ever holds one Advanced
# Ability per category (Phase 128), so the three tiers are mutually
# exclusive in practice and all grant the same flat bonus -- unlike Melee
# Mastery/True Mastery, there's no per-tier magnitude to distinguish.
ARCHERY_FREE_ATTACK_BONUS = 1

# Phase 700: AdvancedAbility.LONG_RANGE_ARCHERY -- "the Archer may now
# use the Fire tactic at Spell Range, with half the normal chance to
# hit the target."
LONG_RANGE_ARCHERY_HIT_MULTIPLIER = 0.5

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


def hand_of_death_cast_and_archery_block(target_is_immune: bool, target_has_artificial_organs: bool) -> tuple[bool, bool]:
    """Hand of Death's own real baseline block (see ``blocks_cast_and_
    archery()`` above -- "confirmed to share this exact same victim
    effect, word for word" with Spiritwrack), narrowed by ``Discovery.
    ARTIFICIAL_ORGANS``'s own second, real clause: "No damage is caused
    to the target, and archery can be used (but not spells.)"

    Returns ``(blocked_from_cast, blocked_from_archery)``. For a target
    without the Discovery, both reduce to the identical base value
    (spells and archery blocked or not, together, exactly like
    Spiritwrack). For a target whose own Kingdom holds it, archery is
    additionally exempted -- but only when the base block would have
    applied at all: an immune target (``target_is_immune``, already
    excluded from the squeeze itself) has nothing to exempt, so both
    values are ``False`` regardless of ``target_has_artificial_organs``.
    """

    blocked = blocks_cast_and_archery(target_is_immune=target_is_immune)
    return blocked, blocked and not target_has_artificial_organs


def _round_randomly(exact: float, rng: random.Random) -> int:
    """Phase 1051: the "random rounding when fractional" convention
    Spiritwrack's own Melee damage reduction established (Phase 182) and
    Hand of Death's own attack damage (``roll_hand_of_death_damage``
    below) later reused word for word -- a whole exact value resolves
    without a roll, a fractional part is a weighted coin flip (e.g. a
    0.5 fractional part is a 50/50 flip) between rounding down and up.
    Extracted once both call sites were confirmed byte-identical, to
    stop the formula from drifting between them.
    """

    whole = int(exact)
    fraction = exact - whole
    if fraction <= 0.0:
        return whole
    return whole + 1 if rng.random() < fraction else whole


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

    return _round_randomly(rate * effective_level, rng)


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

# Discovery.LEAD_LINED_HELMET (models/discovery.py, real design-doc
# text): "The spell will allow only 1-2 free attack rounds" for a
# target whose own Kingdom holds it -- a narrower range, not a
# multiplier on the ordinary roll. Wired at the same two real Psychic-
# Blast-cast call sites as every other spell-specific Discovery ward,
# Phase 883.
LEAD_LINED_HELMET_STUN_ROUNDS_RANGE = (1, 2)


def roll_psychic_blast_stun_rounds(rng: random.Random, *, target_has_lead_lined_helmet: bool = False) -> int:
    """Psychic Blast's own stun effect: "stordisce il nemico guadagnando
    da 2 a 5 round supplementari d'attacco" -- one uniform roll in
    ``PSYCHIC_BLAST_STUN_ROUNDS_RANGE``, unaffected by the caster's own
    skill level (unlike Holy Symbol/Spiritwrack).

    ``target_has_lead_lined_helmet`` (Phase 883) narrows the roll to
    ``LEAD_LINED_HELMET_STUN_ROUNDS_RANGE`` (1-2) instead -- ``Discovery.
    LEAD_LINED_HELMET``'s own real effect, see module docstring's own
    constant comment.
    """

    stun_rounds_range = LEAD_LINED_HELMET_STUN_ROUNDS_RANGE if target_has_lead_lined_helmet else PSYCHIC_BLAST_STUN_ROUNDS_RANGE
    return rng.randint(*stun_rounds_range)


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

# Discovery.INFRARED_GOGGLES (models/discovery.py, real design-doc text):
# "the defensive protection will be only 20%, not 50%" when the character
# fighting an Invisible opponent belongs to a Kingdom holding this
# Discovery -- a weaker override of the ordinary 50% halving above, not a
# full bypass (unlike AdvancedAbility.WITCHSIGHT_TALENT/the Crystal of
# True Seeing, both of which make the opponent completely unaffected).
# Wired at the same two real Invisibility-cast call sites as those two
# carve-outs (`turn/challenge_execution.py`/`turn/search_execution.py`),
# Phase 881. Deliberately NOT wired into `weapon_defensive_hit_
# multiplier()`'s own Invisible Sword branch below -- that function runs
# at `Combatant`-construction time, before any specific opponent is
# known, so it has no "who's fighting this" data to check a Discovery
# against; a real, separate, smaller residual, not attempted here.
INFRARED_GOGGLES_HIT_CHANCE_MULTIPLIER = 0.8


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

# Phase 463 -- AKGEN_reverse_engineering_report (2).md SS21.4's own `D`
# term: "+25 punti percentuali a ogni cella" for whichever combatant is
# rolling to disbelieve, if they hold the advanced ability Detect
# Illusions (`models/advanced_ability.py AdvancedAbility.DETECT_
# ILLUSIONS_TALENT`, ordinal 84 -- "gives the Illusionist a plus 25%
# chance to disbelieve a magical illusion"). SS21.7 confirms this is
# checked fresh on every single roll ("interrogato nuovamente a ogni
# prova") and applies to *whichever* combatant is currently the
# disbeliever, not only the caster: the real opponent in Stage 1, the
# caster themselves in Stage 2 ("opera anche sui personaggi che non
# sono il lanciatore").
DETECT_ILLUSIONS_DISBELIEF_BONUS = 0.25


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
    the chance to disbelieve."

    Phase 783 -- `AKGEN_reverse_engineering_report (2).md` SS21.4 gives
    the real compiled formula shared by both spells: `T = 20(I+1) + 25D
    + 25R - 15(Le+H)`, `P = clamp(T, 0, 100)%`, where `H` (this spell's
    own extra 15-point malus, 0 for Mirror-Image, 1 for Illusory Hero)
    sits inside the SAME pre-clamp expression as `Le`'s per-level
    reduction -- a single combined clamp, not two sequential ones. The
    previous version of this function called through to `mirror_image_
    disbelief_chance()` (which already clamps to [0,1]) and only then
    subtracted `ILLUSORY_HERO_DISBELIEF_REDUCTION`, double-clamping and
    under-valuing the true chance whenever the raw threshold exceeded
    100% before the Illusory Hero malus was applied (e.g. Divine/
    Superhuman intelligence at low caster skill used to read 85% instead
    of the byte-verified 100%). Fixed here by combining the level
    reduction and the Illusory Hero malus into one subtraction before a
    single clamp.
    """

    reduction = min(MIRROR_IMAGE_DISBELIEF_REDUCTION_PER_LEVEL * caster_skill_level, MIRROR_IMAGE_DISBELIEF_REDUCTION_CAP)
    return max(0.0, min(1.0, base_chance - reduction - ILLUSORY_HERO_DISBELIEF_REDUCTION))


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

# Discovery.ASBESTOS_CLOTHING (models/discovery.py, real design-doc
# text): "the damage caused will be reduced by 67%" for a character
# employed by the Kingdom holding it. Applied after the ordinary roll,
# rounded the same "no source for Trunc-vs-round, reuse this project's
# own established round() default" way already used elsewhere for an
# unsourced percentage-rounding choice (Phase 656's own Election Report
# note). Wired at the same two real Fireball-cast call sites as the
# submarine-monster immunity above, Phase 882.
ASBESTOS_CLOTHING_DAMAGE_MULTIPLIER = 1 - 0.67


def roll_fireball_damage(
    skill_level: int, rng: random.Random, *, target_is_immune: bool = False, target_has_asbestos_clothing: bool = False
) -> int:
    """Fireball's own damage: "da 1 a 8 punti danno, più 1 punto danno
    per livello (max 4)". Returns 0 without consuming a roll if
    ``target_is_immune`` (a submarine monster -- see ``models/monster
    .py SUBMARINE_MONSTERS``, shared with Telekinetic Storm since Phase
    188 confirmed both spells mean the exact same real-world category).
    ``skill_level`` is capped at ``PERSONAL_COMBAT_SPELL_LEVEL_CAP``
    (Phase 181), same as Holy Symbol/Spiritwrack.

    ``target_has_asbestos_clothing`` (Phase 882) reduces the rolled
    damage by 67% -- ``Discovery.ASBESTOS_CLOTHING``'s own real effect,
    see module docstring's own constant comment.
    """

    if target_is_immune:
        return 0

    effective_level = min(skill_level, PERSONAL_COMBAT_SPELL_LEVEL_CAP)
    damage = rng.randint(*FIREBALL_DAMAGE_RANGE) + FIREBALL_DAMAGE_PER_LEVEL * effective_level
    if target_has_asbestos_clothing:
        damage = round(damage * ASBESTOS_CLOTHING_DAMAGE_MULTIPLIER)
    return damage


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


def roll_hand_of_death_damage(
    skill_level: int, rng: random.Random, *, target_is_immune: bool = False, target_has_artificial_organs: bool = False
) -> int:
    """Hand of Death's own attack: "1 punto danno più ½ punto per
    livello in magia nera" -- ``HAND_OF_DEATH_BASE_DAMAGE`` (1) plus
    ``HAND_OF_DEATH_DAMAGE_PER_LEVEL`` (0.5) per level, uncapped.
    Uses the same random-rounding-when-fractional convention
    Spiritwrack's own melee damage reduction established (Phase 182) --
    extracted into the shared ``_round_randomly()`` helper above at
    Phase 1051, once both call sites were confirmed byte-identical: a
    whole exact value resolves without a roll, a 0.5 fractional part
    is a 50/50 coin flip. Returns 0 without a roll when
    ``target_is_immune`` (mechanical, Undead, or anti-holy -- see
    ``models/monster.py HAND_OF_DEATH_IMMUNE_MONSTERS``).

    Phase 884: ``target_has_artificial_organs`` (``Discovery.
    ARTIFICIAL_ORGANS``, real text: "No damage is caused to the
    target, and archery can be used (but not spells.)") also zeroes
    this roll, the same way ``target_is_immune`` does -- but, unlike
    full immunity, it does NOT skip the surrounding channel in
    ``resolve_hand_of_death_channel()``: the victim's own halved-
    hit-chance Melee counter-attack, and the caster's own "loses
    concentration when hit" rule, both still apply unchanged. Only
    the caster's own squeeze damage is zeroed every round -- a
    Discovery-holding Kingdom's character can never be killed by Hand
    of Death, but the caster is still exposed to being hit back.

    Phase 887: Hand of Death's own baseline "victim cannot cast spells
    nor shoot with a bow" restriction (module docstring's own Phase 190
    addendum) is now wired at both real callers too, via ``blocks_cast_
    and_archery(target_is_immune=target_is_immune)`` -- the exact same
    helper Spiritwrack's own call sites already use.

    Phase 889: the Discovery's own narrower "archery can still be used
    (but not spells)" exemption is now wired too, via ``hand_of_death_
    cast_and_archery_block()`` (right below ``blocks_cast_and_archery()``
    above) -- ``Combatant.blocked_from_cast``/``blocked_from_archery``
    are now two independent flags instead of one shared boolean, letting
    this exact Discovery relax archery specifically while leaving spells
    blocked.
    """

    if target_is_immune or target_has_artificial_organs:
        return 0

    exact = HAND_OF_DEATH_BASE_DAMAGE + HAND_OF_DEATH_DAMAGE_PER_LEVEL * skill_level
    return _round_randomly(exact, rng)


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


def control_undead_anti_holy_resist_chance(hit_points: int) -> float:
    """``AdvancedAbility.ENHANCED_COMBAT_NE_SPELLS`` (Phase 502): "if you use
    'Control Undead' against anti-holies, there is a percentage chance
    that they will resist the spell, equal to half their current hit
    points." Read as a literal percentage -- ``hit_points / 2`` percent,
    i.e. ``hit_points / 200`` as a probability -- consulted only for a
    target that's Anti-Holy but not also Undead (an ordinary Undead
    target never resists, matching the source's own "in addition to
    affecting the Undead" phrasing, which names anti-holies as the new
    class this resist chance applies to, not the original one).
    """

    return hit_points / 200


# Personal-Combat spell cast success chance, module docstring's own
# Phase 192 addendum -- Regolamento AK.txt [3.10], retroactively
# confirmed for all ten Personal-Combat spells.
#
# **Phase 467 correction**: the rulebook prose above claims a 95% cap
# ("Le probabilità di successo... non possono mai superare il 95%"), but
# `AKGEN_reverse_engineering_report (2).md` SS21.1 gives the real
# compiled formula from `AK.OVR 0x18A75` directly: `P_cast = clamp_0^100
# (30 + 15*L_c + 10*P)`, `L_c = min(level, 4)`, `P = 1` for a Pagan
# caster. At level 4 a Pagan caster's own chance is exactly `30 + 60 +
# 10 = 100`, not 95 -- the report's own worked table ("Ai livelli 1-4...
# per un Pagan diventano 55%, 70%, 85%, 100%") confirms the clamp is
# genuinely `100`, not the rulebook prose's own `95`. The cap is kept as
# its own named constant (not simply removed) since `clamp_0^100` is
# still a real ceiling, just a different number than first quoted.
PERSONAL_COMBAT_SPELL_CAST_BASE_CHANCE = 0.30
PERSONAL_COMBAT_SPELL_CAST_CHANCE_PER_LEVEL = 0.15
PERSONAL_COMBAT_SPELL_CAST_CHANCE_CAP = 1.00

# "I Reami Pagani... un modificatore +10%... fuorché quelli di Magia
# Bianca." Caller decides applicability (see docstring): pass
# ``caster_is_pagan=False`` for White Magic spells regardless of the
# caster's own kingdom.
PERSONAL_COMBAT_PAGAN_MAGE_ORDER_BONUS = 0.10

# Phase 617: Power.DAMP_MAGIC (Special Features.md section 5.2,
# user-supplied 2026-08-22): "dimezza la probabilità di lancio di ogni
# incantesimo" -- halves the cast success chance of every spell,
# location-wide, no skill-level scaling stated (same "flat, no
# scaling" shape as INVISIBILITY_HIT_CHANCE_MULTIPLIER below).
DAMP_MAGIC_CAST_CHANCE_MULTIPLIER = 0.5

# Phase 617: Power.WARP_SPACE (same source, same section, POWMSG.X2 id
# 10 quoted in full in turn_report.py's own Phase 617 addendum): "75%
# of all arrows to miss their mark, as well as 50% of all swings in
# Melee." Read as a flat hit-chance multiplier (0.25 for archery, 0.5
# for melee) applied to *both* combatants at a Warp-Space Feature via
# their own offensive_hit_multiplier/archery_hit_multiplier fields --
# the identical mechanism and "halved, no skill scaling" phrasing
# INVISIBILITY_HIT_CHANCE_MULTIPLIER already established for this same
# style of rulebook wording, rather than a brand-new "flat override"
# mechanic found nowhere else in this project.
WARP_SPACE_ARCHERY_HIT_CHANCE_MULTIPLIER = 0.25
WARP_SPACE_MELEE_HIT_CHANCE_MULTIPLIER = 0.5

# Phase 703: the 5 "_PLACES" Advanced Abilities (HOLY/DARK/ELEMENTAL/
# PSYCHIC/ILLUSORY_PLACES) -- each identically worded, e.g. HOLY_PLACES
# (`models/advanced_ability.py`): "At any Monastery, Altar or Great
# Hall, the success chance to cast a White Magic spell is increased by
# 20%... For Search Feature actions, the 20% bonus is applied when
# that type of feature is searched." A separate, same-valued constant
# from `turn/cast_execution.py`'s own `PLACES_BONUS_PERCENT` (Action-
# Cast's own consumer), matching this project's own established
# per-module citation convention (`PAGAN_MAGE_ORDER_BONUS`/`PERSONAL_
# COMBAT_PAGAN_MAGE_ORDER_BONUS` are likewise two separate 0.10
# constants, one per system).
PERSONAL_COMBAT_PLACES_BONUS_PERCENT = 0.20


def personal_combat_spell_cast_chance(
    skill_level: int,
    *,
    caster_is_pagan: bool = False,
    damp_magic: bool = False,
    places_bonus: bool = False,
    success_chance_multiplier: float = 1.0,
) -> float:
    """"Gli Incantesimi di Combattimento Individuale hanno una
    probabilità di riuscita del 30% più 15% per livello," capped at
    ``PERSONAL_COMBAT_SPELL_CAST_CHANCE_CAP`` -- **100%, corrected at
    Phase 467** from the rulebook's own claimed 95%; see
    ``AKGEN_reverse_engineering_report (2).md`` SS21.1 and this
    constant's own module-level citation. Adds
    ``PERSONAL_COMBAT_PAGAN_MAGE_ORDER_BONUS`` when ``caster_is_pagan``
    -- the caller must already have excluded White Magic spells from
    setting this flag (see module docstring's Phase 192 addendum).

    **Bug fix (this phase)**: SS21.1's own real compiled formula is
    ``P_cast = clamp_0^100(30 + 15*L_c + 10*P)``, ``L_c = min(level,
    4)`` -- the per-level term's own ``level`` is itself capped at
    ``PERSONAL_COMBAT_SPELL_LEVEL_CAP`` (4), the exact same cap every
    individual Personal-Combat spell *effect* in this module already
    applies (``holy_symbol_hit_chance()``, ``roll_fireball_damage()``,
    etc. -- Phase 181's own "come tutti" ["like all of them"] rule).
    This function's own implementation previously fed the raw,
    uncapped ``skill_level`` straight into the per-level term and only
    clamped the *final* percentage at 100% -- for a non-Pagan caster at
    skill level 5+ (a real, reachable value: ``MAX_SKILL_LEVEL`` is 9),
    this silently gave 100% instead of the correct, capped 90%
    (``30 + 15*4``). Both real production call sites (`turn/challenge_
    execution.py`/`turn/search_execution.py`) pass an uncapped
    ``effective_skill_level()`` result straight through, so this was a
    real, live discrepancy, not just a theoretical one -- fixed by
    capping ``skill_level`` here, matching every sibling formula in
    this same module.

    Phase 617: ``damp_magic`` (``Power.DAMP_MAGIC``, ``Special
    Features.md`` section 5.2, user-supplied 2026-08-22: "dimezza la
    probabilità di lancio di ogni incantesimo" -- halves the cast
    probability of every spell) is applied last, after the pagan bonus
    and the cap, matching this project's own ``_roll_cast_success()``
    (``turn/cast_execution.py``) precedent for a late-applied
    probability multiplier.

    Phase 703: ``places_bonus`` (default ``False``, every pre-Phase-703
    caller unaffected) adds ``PERSONAL_COMBAT_PLACES_BONUS_PERCENT`` in
    the same additive block as the Pagan bonus, before the cap -- the
    caller (``turn/search_execution.py``'s own Cast-tactic resolver)
    has already confirmed the caster holds the matching ``_PLACES``
    Advanced Ability and the Feature currently being searched is one of
    that ability's own 3 named types; this function itself has no
    Feature concept to check.

    **2026-10-31**: ``success_chance_multiplier`` (default 1.0, every
    earlier caller unaffected) is a per-attempt multiplier applied
    before the cap, in the same additive-then-cap block as the two
    bonuses above -- mirrors ``cast_execution.py``'s own
    ``_roll_cast_success()`` ``success_chance_multiplier`` parameter
    exactly (same name, same "before the cap" placement, same
    reasoning: keeps the cap the one final ceiling regardless of any
    spell-specific modifier).
    Kill Enemy's own Personal-Combat halving (``turn/search_
    execution.py``/``turn/challenge_execution.py``'s own Kill Enemy
    branches) is the first real caller.
    """

    effective_level = min(skill_level, PERSONAL_COMBAT_SPELL_LEVEL_CAP)
    chance = PERSONAL_COMBAT_SPELL_CAST_BASE_CHANCE + PERSONAL_COMBAT_SPELL_CAST_CHANCE_PER_LEVEL * effective_level
    if caster_is_pagan:
        chance += PERSONAL_COMBAT_PAGAN_MAGE_ORDER_BONUS
    if places_bonus:
        chance += PERSONAL_COMBAT_PLACES_BONUS_PERCENT
    chance *= success_chance_multiplier
    chance = min(chance, PERSONAL_COMBAT_SPELL_CAST_CHANCE_CAP)
    if damp_magic:
        chance *= DAMP_MAGIC_CAST_CHANCE_MULTIPLIER
    return chance


def resolve_personal_combat_spell_cast(
    skill_level: int,
    rng: random.Random,
    *,
    caster_is_pagan: bool = False,
    damp_magic: bool = False,
    places_bonus: bool = False,
    success_chance_multiplier: float = 1.0,
) -> bool:
    """Rolls whether a Personal-Combat spell attempt succeeds, using
    ``personal_combat_spell_cast_chance()``'s own formula. Governs all
    ten Personal-Combat spells above uniformly -- this is the missing
    piece Control Undead's own Phase 191 addendum explicitly declined
    to invent, now supplied generically rather than per-spell.
    """

    return rng.random() < personal_combat_spell_cast_chance(
        skill_level,
        caster_is_pagan=caster_is_pagan,
        damp_magic=damp_magic,
        places_bonus=places_bonus,
        success_chance_multiplier=success_chance_multiplier,
    )


# Phase 732: AKGEN's own confirmed `combat_slots_per_school` -- 1
# Personal-Combat cast attempt per Ability per encounter at skill level
# 1, 2 at level 2 and up (`AKGEN_embedded_catalogs.json.txt`'s own
# `spellcasting` block: `"combat_slots_per_school": {"level_1": 1,
# "level_2_plus": 2}`) -- and its tightly-coupled sibling rule,
# `"same_combat_spell_may_repeat_in_encounter": false`: the exact same
# Spell can never be attempted twice in one encounter, even with slots
# still free for its own Ability (the opposite of the sourced Action-
# Cast rule, `"same_action_spell_may_repeat": true`). Mirrors `turn/
# cast_execution.py action_cast_slots()`/`_consume_action_cast_slot()`
# -- the Action-Cast sibling of this exact mechanic -- in shape, but
# per-encounter-local rather than per-turn-`GameState`: this system has
# no persistent state of its own at all, only whatever `slots_used`/
# `spells_attempted` its own caller keeps for the lifetime of a single
# encounter resolution, one pair per real caster identity (a leader, or
# -- per the user's own direct confirmation this session -- a guardian
# monster too).
COMBAT_CAST_SLOTS_LEVEL_1 = 1
COMBAT_CAST_SLOTS_LEVEL_2_PLUS = 2


def combat_cast_slots(level: int) -> int:
    """1 slot at skill level 1 (or below -- moot in practice, the same
    floor `turn/cast_execution.py action_cast_slots()` uses), 2 at
    level 2 and up.
    """

    return COMBAT_CAST_SLOTS_LEVEL_1 if level <= 1 else COMBAT_CAST_SLOTS_LEVEL_2_PLUS


def try_consume_combat_cast_slot(
    ability: Ability, spell: Spell, level: int, slots_used: dict[Ability, int], spells_attempted: set[Spell]
) -> bool:
    """Attempts to spend one of this caster's own per-Ability, per-
    encounter combat-cast slots for `spell`. `failed_attempt_consumes_
    slot` is confirmed true (the same rule `_consume_action_cast_slot()`
    already honors for Action-Cast), so this must be called once every
    other precondition/eligibility check has already passed -- right
    before the real success roll, not after -- and only for a genuine
    Personal-Combat cast attempt; a wand-cast (`[3.11]`'s own automatic-
    success rule) is a separate mechanic entirely and must never reach
    this function at all (see each real caller's own bypass).

    `slots_used`/`spells_attempted` are mutated in place and must be
    the caller's own per-caster-identity, per-encounter pair (never
    shared across two different casters, and never reused across two
    different encounters) -- this function itself holds no state.
    Returns `False` (nothing mutated) when this exact Spell was already
    attempted this encounter, or this Ability's own slots are already
    exhausted for it.
    """

    if spell in spells_attempted:
        return False
    if slots_used.get(ability, 0) >= combat_cast_slots(level):
        return False
    slots_used[ability] = slots_used.get(ability, 0) + 1
    spells_attempted.add(spell)
    return True


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
    # Kill Enemy [4.25.2] (2026-10-31, user-requested Personal-Combat
    # build): tied to Ability.NECROMANCY -- same [4.25] citation block
    # as Hand of Death/Control Undead above, and the same Ability its
    # own Action-Cast form uses (`cast_execution.py _SPELL_ABILITY`).
    Spell.KILL_ENEMY: Ability.NECROMANCY,
}


# Phase 530: the 3 Personal-Combat-capable spells whose entire effect
# reads/mutates only the *caster's* own state -- Augur_Combat's silent
# flee-simulation (throwaway clone combat, decides whether the caster
# flees), Invisibility (buffs the caster's own defensive_hit_multiplier/
# is_invisible), and Words of Healing (heals the caster). None of the
# three ever reads or writes the opposing combatant's own state, unlike
# every other Personal-Combat spell (even Psychic Blast, structurally
# caster-side-coded as a bonus-attack buff, is still cast *at* the
# opponent by rulebook description and dossier confirmation -- see
# ``turn/discovery_effects.py holder_is_immune_to_spell()``'s own Phase
# 531 addendum). Used to exclude these three from the Anti-Magic Amulet
# immunity check -- an amulet protecting its wearer "from spells" has
# nothing to negate for a spell that was never cast at them.
PERSONAL_COMBAT_SPELL_SELF_ONLY: frozenset[Spell] = frozenset({Spell.AUGUR_COMBAT, Spell.INVISIBILITY, Spell.HEAL})


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
    # Hit points regenerated at the end of each qualifying round this
    # combatant survives -- 0 for every existing caller. Troll's own
    # regeneration rule (Phase 155 addendum above) is the only real,
    # sourced user so far; `turn/search_execution.py` sets it for a
    # Troll's own monster combatant.
    regenerates_hp: int = 0
    # Which rounds ``regenerates_hp`` actually applies on -- default `1`
    # (every round, Troll's own established cadence, so every pre-
    # Phase-666 caller is unaffected). Office.NECRO_MAGE's own Imp
    # familiar (Phase 666, ``models/office.py OFFICE_TITLE_DESCRIPTION``:
    # "help <2 regenerate 1 hit point per 2 rounds of combat") sets this
    # to `2` instead -- `_apply_end_of_round_regeneration()` only fires
    # when ``round_number % regenerates_hp_interval == 0``, so round 1
    # is skipped and every even round regenerates, the literal reading
    # of "per 2 rounds."
    regenerates_hp_interval: int = 1
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
    #
    # Phase 889: split into two independent flags -- previously one bare
    # `blocked_from_cast_and_archery` boolean gated both actions
    # identically, which was correct for Spiritwrack (both are always
    # blocked together) but couldn't represent Discovery.ARTIFICIAL_
    # ORGANS's own real Hand of Death exemption: "No damage is caused to
    # the target, and archery can be used (but not spells.)" -- spells
    # stay blocked, archery specifically doesn't. Every write site sets
    # both to the same value except Hand of Death's own Artificial-
    # Organs-aware composition (`hand_of_death_cast_and_archery_block()`
    # below); every CAST-tactic dispatch checks `blocked_from_cast`,
    # every SHOOT-tactic dispatch checks `blocked_from_archery`.
    blocked_from_cast: bool = False
    blocked_from_archery: bool = False
    # Phase 209 -- free, unanswered Melee swings this combatant has banked
    # from a successful Psychic Blast or Ice Suspension cast, consumed by
    # `turn/search_execution.py`/`turn/challenge_execution.py _consume_
    # bonus_attacks()` immediately after the CAST tactic resolves. Phase
    # 767: a landed Psychic Flail hit's own 50% stun chance (`apply_
    # weapon_on_hit_effects()`) feeds this exact same counter -- drained
    # by `resolve_one_melee_round()` itself, within the same round, for
    # the Melee-vs-Melee case (see that function's own Phase 767 addendum;
    # `resolve_reactive_melee_swing()` deliberately still doesn't drain it).
    bonus_unanswered_attacks: int = 0
    # Phase 1050 -- whether this combatant is (or has been, this same
    # encounter -- see below) the TARGET of a successful Psychic Blast
    # cast, i.e. the stunned side, not the caster who banks `bonus_
    # unanswered_attacks` above. The only real consumer is Psychic
    # Flail's own on-hit proc (`apply_weapon_on_hit_effects()`): `models/
    # treasure.py`'s sourced text grants an extra stunned round "if the
    # opponent is already under the effects of the Psychic Blast spell"
    # on top of the weapon's own base one-round stun -- unreadable
    # before this field existed, since Psychic Blast's own stun is
    # otherwise modeled entirely as the CASTER's `bonus_unanswered_
    # attacks`, fully drained by `_consume_bonus_attacks()` before any
    # Melee round (where Psychic Flail could land a hit) ever runs -- no
    # state survived on the stunned side itself for a later Melee swing
    # to observe. **No source gives an expiration for "already under the
    # effects"** -- rather than invent an unsourced stun-round countdown
    # this project has no other precedent for, this flag is simply never
    # cleared once set: once a combatant has been hit by a real Psychic
    # Blast cast this encounter, Psychic Flail's own stacking bonus can
    # fire against them for the rest of it. A real, if generous,
    # approximation of "currently stunned" -- not a guess at an invented
    # decay rule.
    stunned_by_psychic_blast: bool = False
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
    # Phase 489 -- Imperial Defender's own perk ("CARICHE E ABLITÀ.txt":
    # "The Armor will reduce any strike against you in personal combat
    # (including magical damage) by one damage point"). Subtracted from
    # every incoming hit this combatant takes -- Melee, Fire Arrow, and
    # Hand of Death's own psychic damage alike -- floored at 0 the same
    # way `melee_damage_dealt_reduction` already is. Default 0 leaves
    # every pre-Phase-489 caller unaffected; only a leader confirmed
    # (via `turn/office_holder.py resolve_office_holder`) to hold
    # `Office.DEFENDER` gets 1 here, set by each consumer's own
    # `_leader_combatant`-style builder (this project's established
    # per-consumer lookup precedent, not a shared helper -- see e.g.
    # `challenge_execution.py _leader_combatant`'s own docstring).
    damage_reduction: int = 0
    # Phase 516 -- AdvancedAbility.MELEE_HIT_POINTS ("The Gods grant 1-5
    # additional hit points in any encounter"). Set by each consumer's
    # own `_leader_combatant`-style builder when the leader holds the
    # ability (same per-consumer lookup precedent as `damage_reduction`
    # above). `apply_temper_melee_setup()` rolls and applies the actual
    # bonus once, at setup -- see that function's own Phase 516 addendum.
    has_melee_hit_points_ability: bool = False
    # Phase 517 -- AdvancedAbility.MELEE_MASTERY/MELEE_TRUE_MASTERY's own
    # flat "+1"/"+2 damage" bonus. Set by each consumer's own `_leader_
    # combatant`-style builder from `melee_mastery_damage_bonus()` below
    # (same per-consumer lookup precedent as `damage_reduction` above).
    # Added to this combatant's own landed Melee damage -- the attacker-
    # side counterpart to `melee_damage_dealt_reduction` above -- but
    # only under a landed-hit gate (see `_melee_landed_damage()` below),
    # since a flat bonus must never turn a miss into a hit. Default 0
    # leaves every pre-Phase-517 caller unaffected.
    melee_damage_dealt_bonus: int = 0
    # Phase 518 -- this combatant's own race is one of `models/race.py
    # HUMANOID_RACES` ("men, elves, orcs and dwarves"). Set by each
    # consumer's own `_leader_combatant`-style builder from `leader.race`/
    # the leader's own Kingdom race (same resolution `report/turn_
    # report.py`/`turn/hire_pay.py` already use); a monster combatant is
    # never humanoid, so its own builder never sets this, leaving the
    # default `False` -- the correct answer. Read from the *opponent's*
    # own side by `apply_temper_melee_setup()`'s own AdvancedAbility.
    # MELEE_DUELLISTS_MEDAL check (see that function's own Phase 518
    # addendum) -- this combatant's own `has_duellists_medal_ability`
    # below is irrelevant to how this field is read.
    is_humanoid: bool = False
    # Phase 518 -- AdvancedAbility.MELEE_DUELLISTS_MEDAL. Set by each
    # consumer's own builder the same way `has_melee_hit_points_ability`
    # is. Consulted by `apply_temper_melee_setup()` against the
    # *opponent's* own `is_humanoid` -- see that function's own Phase 518
    # addendum for the full symmetric hit-chance/damage swing this
    # applies.
    has_duellists_medal_ability: bool = False
    # Phase 519 -- AdvancedAbility.MELEE_CONTROL_TEMPER's own confirmed,
    # unambiguous half ("the Berserk temper is used initially to gain
    # the extra 1-4 hit points") -- set by each consumer's own builder
    # the same way `has_melee_hit_points_ability` is. Independent of
    # this combatant's own real `.temper` field: the ability grants the
    # bonus regardless of what temper (if any) is actually recorded, and
    # composes additively with a genuinely-Berserk combatant's own Furia
    # roll if both happen to apply (no source disambiguates that overlap
    # -- see `apply_temper_melee_setup()`'s own Phase 519 addendum for
    # why this stays a deliberate, documented quirk rather than a
    # guessed de-duplication rule). The ability's own second half ("then
    # the temper is usually adjusted to whatever temper gains the most
    # favorable benefits") is NOT modeled -- no trigger or algorithm is
    # given for "most favorable," so this project's own "no source, no
    # guess" policy leaves it undone; see that same addendum.
    has_control_temper_ability: bool = False
    # Phase 520 -- Archery category, all three "Free Attack" tiers
    # (`AdvancedAbility.ARCHERY_FREE_ATTACK`/`_MASTERY`/`_TRUE_MASTERY`)
    # share the identical sourced text ("One more free attack is gained
    # when using the Fire tactic in personal combat") -- since a leader
    # only ever holds one Advanced Ability per category (Phase 128), the
    # three tiers are mutually exclusive in practice and all grant the
    # same flat +1, so they collapse into one int field rather than
    # needing per-tier magnitudes the way Melee's Mastery/True Mastery
    # did. Static, opponent-independent, RNG-free -- seeded once at
    # `Combatant` construction time via `archery_free_attack_bonus()`
    # below (same "seed at construction" precedent as `melee_damage_
    # dealt_bonus`/`offensive_hit_multiplier`, Phase 517), not inside
    # `apply_temper_melee_setup()`'s per-combatant loop.
    archery_free_attack_bonus: int = 0
    # Phase 535 -- the Bow of the Elven Kings' own Archery-only to-hit
    # bonus (AKGEN_reverse_engineering_report (4).md SS7.2's own
    # ``attack_is_archery`` branch) -- the attacker-side counterpart to
    # ``offensive_hit_multiplier`` above, but scoped to Fire Arrow only
    # since Melee's own ``offensive_hit_multiplier`` already has real
    # non-weapon sources (Slancio, Melee Mastery) that must stay Melee-
    # only. Set by each consumer's own builder via ``turn/discovery_
    # effects.py holds_bow_of_elven_kings()``. Default 1.0 leaves every
    # pre-Phase-535 caller unaffected.
    archery_hit_multiplier: float = 1.0
    # Phase 535 -- the flat damage counterpart to ``archery_hit_
    # multiplier`` above (SS7.2's own ``damage += 2`` in the same
    # branch) -- the attacker-side equivalent of ``melee_damage_dealt_
    # bonus`` but for Fire Arrow, which had no such field before this
    # phase (no weapon bonus existed for it yet). Added to a landed
    # shot's damage only, same "never turns a miss into a hit" gating
    # ``melee_damage_dealt_bonus`` already established. Default 0 leaves
    # every pre-Phase-535 caller unaffected.
    missile_damage_dealt_bonus: int = 0
    # Phase 536 -- which of the ``COMBAT_WEAPON_SLOT_TREASURES`` weapons
    # (if any) this combatant has equipped, needed by ``apply_weapon_on_
    # hit_effects()`` to know which per-swing proc (if any) to roll: the
    # hit/damage bonus Phase 535 already baked into ``offensive_hit_
    # multiplier``/``melee_damage_dealt_bonus`` alone can't distinguish
    # Shadow Sword from Holy Sword. Set by each consumer's own builder
    # from the same ``equipped_combat_weapon(...)`` lookup Phase 535
    # already performs. ``None`` (every monster combatant, and any
    # leader with nothing equipped) is a no-op.
    equipped_weapon: Treasure | None = None
    # Phase 682 -- this combatant's own nature: `True` iff its own
    # alignment (a leader) or species (a monster) is Undead/Anti-Holy.
    # Read from the *opponent's* own side by `apply_temper_melee_
    # setup()`'s own Holy Sword check (same "read from the opponent's
    # own side" precedent `is_humanoid` above already established for
    # Duellist's Medal, Phase 518) -- a combatant never needs to know
    # its own opponent to set this about itself. Set by each consumer's
    # own builder from `leader.alignment in (Alignment.UNDEAD, Alignment.
    # ANTI_HOLY)` or `monster_species in (HAND_OF_DEATH_ANTI_HOLY_
    # MONSTERS | SPIRITWRACK_UNDEAD_MONSTERS)`. Default `False` leaves
    # every pre-Phase-682 caller unaffected.
    is_undead_or_anti_holy: bool = False
    # Office.ELE_MAGE's own personal-combat sibling perk (Phase 665,
    # ``models/office.py OFFICE_TITLE_DESCRIPTION``): "The Chameleon can
    # transmit its camouflage ability to <2, which gives <2 the ability
    # to always make the first move in combat, even if opponent has
    # greater skill." Set by each consumer's own `_leader_combatant`-
    # style builder for the ``Office.ILLUS_MAGE`` titleholder specifically
    # (same per-consumer lookup precedent as `damage_reduction` above) --
    # never set on a synthetic illusion/monster `Combatant`, so it only
    # ever wins the `_acts_first()` roll for the real titleholder, on
    # whichever side of whichever duel he's actually fighting in (a
    # Mirror-Image/Illusory-Hero construct included). Default `False`
    # leaves every pre-Phase-665 caller unaffected.
    always_acts_first: bool = False


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


def archery_free_attack_bonus(advanced_abilities: "set[AdvancedAbility]") -> int:
    """``AdvancedAbility.ARCHERY_FREE_ATTACK``/``_MASTERY``/``_TRUE_MASTERY`` --
    see module constant ``ARCHERY_FREE_ATTACK_BONUS``'s own Phase 520
    addendum for why all three tiers collapse into one flat bonus.
    """

    if advanced_abilities & {
        AdvancedAbility.ARCHERY_FREE_ATTACK,
        AdvancedAbility.ARCHERY_FREE_ATTACK_MASTERY,
        AdvancedAbility.ARCHERY_FREE_ATTACK_TRUE_MASTERY,
    }:
        return ARCHERY_FREE_ATTACK_BONUS
    return 0


def berserk_fury_bonus_hit_points(rng: random.Random) -> int:
    """"Furia": a Berserk combatant's own 1-4 bonus starting Hit Points --
    see module docstring's own Phase 284 addendum.
    """

    return rng.randint(*BERSERK_FURY_BONUS_HIT_POINTS_RANGE)


def roll_melee_hit_points_ability_bonus(rng: random.Random) -> int:
    """AdvancedAbility.MELEE_HIT_POINTS's own 1-5 bonus starting Hit
    Points -- see module docstring's own Phase 516 addendum.
    """

    return rng.randint(*MELEE_HIT_POINTS_ABILITY_BONUS_RANGE)


def melee_mastery_offensive_hit_multiplier(advanced_abilities: "set[AdvancedAbility]") -> float:
    """AdvancedAbility.MELEE_MASTERY's own "+10% chance to hit" -- same
    stated-percentage-is-multiplicative convention as Slancio (Brave)
    above. MELEE_TRUE_MASTERY grants no hit-chance change (the source's
    own confirmed omission -- only the flat damage bonus is shared), so
    this only ever returns something other than 1.0 for MELEE_MASTERY.
    Meant to seed a builder's own ``Combatant(offensive_hit_multiplier=
    ...)`` at construction time -- ``apply_temper_melee_setup()`` still
    multiplies a Brave combatant's own Slancio bonus on top afterward, so
    the two compose correctly regardless of call order.
    """

    if AdvancedAbility.MELEE_MASTERY in advanced_abilities:
        return 1.0 + MELEE_MASTERY_HIT_CHANCE_BONUS
    return 1.0


def melee_mastery_damage_bonus(advanced_abilities: "set[AdvancedAbility]") -> int:
    """The flat "+1"/"+2 damage" bonus of AdvancedAbility.MELEE_MASTERY/
    MELEE_TRUE_MASTERY. A leader only ever holds one Advanced Ability per
    category (models/advanced_ability.py's own module docstring), so
    these two are mutually exclusive in practice -- True Mastery's own
    higher bonus is checked first only as defensive ordering, not
    because both could really be held by the same leader at once. Meant
    to seed a builder's own ``Combatant(melee_damage_dealt_bonus=...)``.
    """

    if AdvancedAbility.MELEE_TRUE_MASTERY in advanced_abilities:
        return MELEE_TRUE_MASTERY_DAMAGE_BONUS
    if AdvancedAbility.MELEE_MASTERY in advanced_abilities:
        return MELEE_MASTERY_DAMAGE_BONUS
    return 0


def weapon_offensive_hit_multiplier(weapon: "Treasure | None") -> float:
    """Phase 535: the equipped sword-slot weapon's own to-hit bonus
    (``models/treasure.py WEAPON_HIT_BONUS``, AKGEN_reverse_engineering_
    report (4).md SS7.2), as a multiplier -- same stated-percentage-is-
    multiplicative convention ``melee_mastery_offensive_hit_multiplier()``
    above already uses. ``weapon`` is the caller's own ``turn/discovery_
    effects.py equipped_combat_weapon()`` result; ``None`` (no weapon
    equipped, every pre-Phase-535 caller) leaves the multiplier at 1.0.
    Meant to seed a builder's own ``Combatant(offensive_hit_multiplier=
    ...)`` the same way the Melee Mastery helper above is.
    """

    if weapon is None:
        return 1.0
    return 1.0 + WEAPON_HIT_BONUS.get(weapon, 0) / 100


def weapon_melee_damage_bonus(weapon: "Treasure | None") -> int:
    """The flat damage counterpart to ``weapon_offensive_hit_multiplier()``
    above (``models/treasure.py WEAPON_DAMAGE_BONUS``). Meant to seed a
    builder's own ``Combatant(melee_damage_dealt_bonus=...)``.
    """

    if weapon is None:
        return 0
    return WEAPON_DAMAGE_BONUS.get(weapon, 0)


def bow_of_elven_kings_archery_hit_multiplier(holds_bow: bool) -> float:
    """Phase 535: Bow of the Elven Kings' own Archery-only to-hit bonus
    (SS7.2's separate ``if attack_is_archery`` branch), as a multiplier.
    ``holds_bow`` is the caller's own ``turn/discovery_effects.py holds_
    bow_of_elven_kings()`` result. Meant to seed a builder's own
    ``Combatant(archery_hit_multiplier=...)``.
    """

    return 1.0 + BOW_OF_ELVEN_KINGS_ARCHERY_HIT_BONUS / 100 if holds_bow else 1.0


def bow_of_elven_kings_archery_damage_bonus(holds_bow: bool) -> int:
    """The flat damage counterpart to ``bow_of_elven_kings_archery_hit_
    multiplier()`` above. Meant to seed a builder's own ``Combatant
    (missile_damage_dealt_bonus=...)``.
    """

    return BOW_OF_ELVEN_KINGS_ARCHERY_DAMAGE_BONUS if holds_bow else 0


# Phase 536 -- AKGEN_reverse_engineering_report (4).md SS7.3's own
# automatic, no-Use_MI-required equip effects. Holy Sword grants a
# level-4 Holy Symbol protection "automatica e senza danno" ("automatic
# and without [bonus] damage") -- so only the hit-chance-reduction half
# of Holy Symbol applies, not the Undead/Anti-Holy bonus-damage roll,
# which also matches this project's own constraint that a builder never
# knows the opponent at Combatant-construction time (unlike the real
# Holy Symbol *spell*'s own CAST-time target lookup, which does). Invisible
# Sword grants a level-2 Invisibility -- this project's own Invisibility
# mechanic has no skill-level scaling at all (module docstring's own Phase
# 186 addendum), so "level 2" applies identically to the spell's own flat
# ``INVISIBILITY_HIT_CHANCE_MULTIPLIER``.
HOLY_SWORD_AUTO_PROTECTION_LEVEL = PERSONAL_COMBAT_SPELL_LEVEL_CAP  # 4


def weapon_defensive_hit_multiplier(weapon: "Treasure | None") -> float:
    """Meant to seed a builder's own ``Combatant(defensive_hit_
    multiplier=...)`` outright -- covers *both* auto-equip defensive
    effects (Holy Sword's level-4 Holy Symbol protection, Invisible
    Sword's flat Invisibility halving) in one call, since the two
    weapons share the same equip slot and can therefore never both apply
    at once. A no-op (``1.0``) for every other weapon or ``None``.
    """

    if weapon is Treasure.WEAPON_1:
        return holy_symbol_hit_chance(1.0, HOLY_SWORD_AUTO_PROTECTION_LEVEL)
    if weapon is Treasure.WEAPON_5:
        return INVISIBILITY_HIT_CHANCE_MULTIPLIER
    return 1.0


def weapon_grants_auto_invisibility(weapon: "Treasure | None") -> bool:
    """Meant to seed a builder's own ``Combatant(is_invisible=...)`` --
    paired with ``weapon_defensive_hit_multiplier()`` above (which already
    applies ``INVISIBILITY_HIT_CHANCE_MULTIPLIER`` for this same weapon),
    the same two fields the real Invisibility spell sets together
    (Phase 286).
    """

    return weapon is Treasure.WEAPON_5


# Phase 536 -- AKGEN_reverse_engineering_report (4).md SS7.4's own
# per-landed-hit weapon procs. Only Shadow Sword/Flaming Scimitar/Psychic
# Flail have one; the other six weapons in COMBAT_WEAPON_SLOT_TREASURES
# (including the Bow, which never occupies this equip slot at all) do
# not. Since all three share the single equip slot Phase 535 established,
# at most one of these three can ever be a given attacker's own
# ``equipped_weapon`` at once -- no RNG-ordering ambiguity between them.
SHADOW_SWORD_LIFE_DRAIN_FRACTION = 0.5
FLAMING_SCIMITAR_INSTAKILL_CHANCE = 0.05
PSYCHIC_FLAIL_STUN_CHANCE = 0.50

# Phase 740 -- report-layer narration for Shadow Sword's/Flaming
# Scimitar's own on-hit procs (`report/turn_report.py render_shadow_
# sword_drain()`/`render_flaming_scimitar_proc()`, Phase 588, sourced
# and render-tested but never called from anywhere until now).
#
# **Phase 767** -- Psychic Flail's own stun joins them as a third,
# narratable proc. The real mechanical gap this comment used to flag
# (`Combatant.bonus_unanswered_attacks`, what a successful Flail stun
# sets, was only ever *consumed* right after a CAST tactic resolves --
# `turn/challenge_execution.py`/`turn/search_execution.py _consume_
# bonus_attacks()`, built for Psychic Blast/Ice Suspension -- so an
# ordinary Melee-only duel had no consumption point for it at all) is
# now closed: `resolve_one_melee_round()` (below) drains it directly,
# within the very round that triggered it, for every real Melee-vs-
# Melee caller in this project (both the atomic `resolve_melee_duel()`
# and every round-stepped engine funnel through that one function).
# **Deliberately still out of scope**: `resolve_reactive_melee_swing()`
# (one side meleeing, the other casting) can still set the counter via
# its own `apply_weapon_on_hit_effects()` call, but nothing drains it
# there -- "stunning the opponent for one round" has no sourced meaning
# when the opponent wasn't going to swing back anyway (they're
# casting), and inventing a stun-vs-cast interaction rule would be a
# real, unsourced guess this project's own standard doesn't support.
WeaponOnHitProc = Literal["shadow_sword_drain", "flaming_scimitar_instakill", "psychic_flail_stun"]


def apply_weapon_on_hit_effects(
    attacker: "Combatant", defender: "Combatant", damage_dealt: int, rng: random.Random
) -> WeaponOnHitProc | None:
    """Applies Shadow Sword's life drain, Flaming Scimitar's instant-kill
    chance, and Psychic Flail's stun -- see module docstring's own Phase
    536 addendum for the quoted dossier pseudocode. Called immediately
    after a landed Melee swing's own net damage is known, from both
    ``resolve_one_melee_round()`` and ``resolve_reactive_melee_swing()``.

    **Stale as of Phase 1050**: this used to also list the Mirror-Image/
    Illusory-Hero phantasm duels as deliberately out of scope here,
    alongside Hand of Death's own victim counter-swing -- both
    ``resolve_mirror_image_duel()``/``resolve_illusory_hero_duel()`` now
    call ``resolve_one_melee_round()`` for their own melee exchanges
    (see each one's own Phase 1050 addendum), which already calls this
    function, so they're real callers now too, not an exception. Hand of
    Death's victim counter-swing remains the one real gap: no sourced
    text describes a weapon proc firing from that specific defensive
    reflex, so it's deliberately not wired here. A no-op (returns
    ``None``) when ``attacker.equipped_weapon`` is not one of the three
    weapons with an on-hit effect, or when ``damage_dealt`` is 0 (a
    miss, or a hit reduced to net 0 by Spiritwrack/``damage_reduction``,
    procs nothing).

    ``CHARACTER_HIT_POINTS`` is Shadow Sword's own healing cap (dossier's
    ``attacker.maxhp``), used unconditionally: these weapons only ever
    reach a real leader's ``Combatant`` (``state.items_held_by()`` is
    never consulted for a monster), so ``attacker`` always has the
    standard 10-hit-point character maximum here, never a monster's own
    stat-block total.

    Phase 740: the return value (``None`` for every pre-Phase-740
    caller, since none of them capture it) reports which of the
    narratable procs above fired, if any, for real callers to attach to
    their own ``MeleeSwing``/``ReactiveMeleeSwingResult``. Phase 767:
    Psychic Flail's own stun is now one of them too -- its own real
    effect (``attacker.bonus_unanswered_attacks += 1``) is unchanged,
    but the caller finds out via the return value now, the same as the
    other two, rather than having to notice the counter changed.

    **Phase 1050 bug fix**: Psychic Flail's own sourced text has a
    second clause this function never implemented at all -- "if the
    opponent is already under the effects of the Psychic Blast spell,
    he is stunned for an additional round." Closed via ``Combatant.
    stunned_by_psychic_blast`` (see that field's own docstring for the
    full design and its own honestly-flagged "no source for an
    expiration" simplification): a successful stun now credits 2 bonus
    rounds instead of 1 when ``defender.stunned_by_psychic_blast`` is
    set, matching the dossier's own "+1 additional round" wording
    exactly (1 base + 1 additional).
    """

    if damage_dealt <= 0:
        return None
    weapon = attacker.equipped_weapon
    if weapon is Treasure.WEAPON_2:  # Shadow Sword
        # Phase 1050 bug fix -- no source gives a Trunc-vs-round direction
        # for this 50% fraction (`models/treasure.py`'s own text: "Half
        # the hit points... are used to restore..."), the same unsourced-
        # rounding situation `Discovery.ASBESTOS_CLOTHING`'s own comment
        # above documents this project's real default for: "reuse this
        # project's own established round() default." This was the one
        # unsourced-percentage site in this module still using `int()`
        # truncation instead.
        drain = round(damage_dealt * SHADOW_SWORD_LIFE_DRAIN_FRACTION)
        attacker.hit_points = min(CHARACTER_HIT_POINTS, attacker.hit_points + drain)
        return "shadow_sword_drain"
    elif weapon is Treasure.WEAPON_3:  # Flaming Scimitar
        if rng.random() < FLAMING_SCIMITAR_INSTAKILL_CHANCE:
            defender.hit_points = 0
            return "flaming_scimitar_instakill"
    elif weapon is Treasure.WEAPON_4:  # Psychic Flail
        if rng.random() < PSYCHIC_FLAIL_STUN_CHANCE:
            attacker.bonus_unanswered_attacks += 2 if defender.stunned_by_psychic_blast else 1
            return "psychic_flail_stun"
    return None


def _melee_landed_damage(raw_damage: int, attacker: "Combatant", defender: "Combatant") -> int:
    """Applies every additive/subtractive Melee-damage modifier in a
    single place, so both real per-swing call sites (``resolve_one_
    melee_round``/``resolve_reactive_melee_swing``) stay in lockstep.
    ``raw_damage`` is ``roll_melee_attack()``'s own return value -- 0 on
    a miss, which this function preserves outright: Phase 209's
    ``melee_damage_dealt_reduction``/the defender's own ``damage_
    reduction`` already only ever reduce a landed hit (the pre-existing
    ``max(0, ...)`` floor), and Phase 517's own ``melee_damage_dealt_
    bonus`` is gated behind the identical ``raw_damage > 0`` check so a
    flat damage bonus alone can never turn a miss into a hit.
    """

    if raw_damage <= 0:
        return 0
    return max(
        0, raw_damage + attacker.melee_damage_dealt_bonus - attacker.melee_damage_dealt_reduction - defender.damage_reduction
    )


def _fire_arrow_landed_damage(raw_damage: int, attacker: "Combatant", defender: "Combatant") -> int:
    """Phase 535 -- the Fire Arrow counterpart to ``_melee_landed_damage()``
    above, for ``attacker.missile_damage_dealt_bonus`` (the Bow of the
    Elven Kings' own flat damage bonus; 0 for every pre-Phase-535
    caller). Same landed-hit gate: a flat bonus alone can never turn a
    miss into a hit.
    """

    if raw_damage <= 0:
        return 0
    return max(0, raw_damage + attacker.missile_damage_dealt_bonus - defender.damage_reduction)


def apply_temper_melee_setup(a: "Combatant", b: "Combatant", rng: random.Random) -> None:
    """Mutates ``a``/``b`` in place per the Temper Table's own melee-specific
    mechanics (Furia, Intimidazione, Slancio, Schivare) -- see module
    docstring's own Phase 284 addendum for the full quoted source and
    derivation. Reads each combatant's own ``.temper`` field (``None`` is
    a documented no-effect); called once, internally, at the very start
    of ``resolve_melee_duel()`` -- not meant to be called directly by
    other callers.

    Phase 516: also applies ``AdvancedAbility.MELEE_HIT_POINTS``'s own
    flat 1-5 bonus starting Hit Points, for either combatant whose own
    ``has_melee_hit_points_ability`` is set -- the same "once, at setup"
    shape as Furia's own bonus above, so it rides this function's own
    three real call sites (``resolve_melee_duel()``'s internal default
    call, plus ``challenge_execution.py``'s/``search_execution.py``'s own
    direct calls for their round-stepping engines) rather than adding a
    fourth. Default ``False`` leaves every pre-Phase-516 caller unaffected.

    Phase 518: also applies ``AdvancedAbility.MELEE_DUELLISTS_MEDAL``'s own
    symmetric swing -- for either combatant whose own ``has_duellists_
    medal_ability`` is set *and* whose opponent's own ``is_humanoid`` is
    True, the holder's own ``offensive_hit_multiplier``/``melee_damage_
    dealt_bonus`` go up (+10%/+1) and the opponent's own go down
    (-10%/-1) -- both are this combatant's own numbers being changed, not
    a defensive multiplier on the opponent's incoming hits, matching the
    source's own "the character has..., while the opponent has..."
    wording (each side's own hit chance/damage, not who's harder to
    hit). No RNG consumed, no ordering dependency with the Temper
    branches below (multiplication/addition compose regardless of order),
    so it's placed first in the loop purely for readability. Defaults
    (``False``) leave every pre-Phase-518 caller unaffected.

    Phase 519: also applies AdvancedAbility.MELEE_CONTROL_TEMPER's own
    confirmed, unambiguous half ("the Berserk temper is used initially
    to gain the extra 1-4 hit points") -- for either combatant whose own
    ``has_control_temper_ability`` is set, one ``berserk_fury_bonus_hit_
    points(rng)`` roll is added to ``hit_points``, the exact same
    mechanic Furia already uses, and independent of that combatant's own
    real ``.temper`` (this ability grants the bonus regardless of what
    temper, if any, is actually recorded). If a combatant happens to
    hold this ability *and* have a genuinely-Berserk ``.temper``, both
    rolls apply and stack -- no source disambiguates that overlap, so it
    stays a deliberate, documented quirk rather than a guessed
    de-duplication rule. The ability's own second half ("then the temper
    is usually adjusted to whatever temper gains the most favorable
    benefits in combat") is deliberately NOT modeled here: no trigger or
    algorithm is given for "most favorable," so per this project's own
    "no source, no guess" policy it stays undone -- this closes out the
    Melee category's own six Advanced Abilities with five fully wired
    and this one partially wired plus its ambiguous residual documented.

    Phase 682: Holy Sword's own vs-Undead combat bonus (``models/
    treasure.py`` SS7.1: "+20%; +40% vs Undead" / "+3; +5 vs Undead").
    The flat, non-Undead values are already baked into a Holy-Sword-
    wielding combatant's own ``offensive_hit_multiplier``/``melee_
    damage_dealt_bonus`` at builder time (Phase 535) -- composed there
    with e.g. Melee Mastery, since neither builder knows the opponent
    yet. Here, once both combatants ARE known, that already-baked
    weapon-only contribution is *swapped* for the vs-Undead one rather
    than stacked on top of it: the damage side is a simple additive
    delta (bonuses compose additively), but the hit-chance side must
    divide out the old multiplicative factor before multiplying in the
    new one, or the already-included +20% would be double-counted
    (1.2 * 1.2 = 1.44, not the correct 1.4) -- dividing first isolates
    exactly the weapon's own contribution regardless of what else
    (Melee Mastery) is already composed into the same multiplier.

    **Phase 1050 bug fix**: the identical swap was missing for the
    weapon's own *defensive* side. ``models/treasure.py`` sources Holy
    Sword's auto-protection as "the same as a Holy Symbol spell cast at
    skill level 4, except it causes no damage" -- a real Holy Symbol
    cast doubles its hit-chance reduction to 20%/level against an
    Undead/Anti-Holy opponent (``holy_symbol_hit_chance()``'s own
    ``target_is_undead_or_anti_holy`` parameter, module docstring's own
    Phase 180 addendum), but ``weapon_defensive_hit_multiplier()`` (Phase
    535, builder time) always calls it with that parameter left at its
    default ``False``, since a builder never knows the opponent yet --
    exactly the same "builder-time, opponent-blind" gap the offensive
    side above already has a real fix for. Nothing else ever composes
    into ``defensive_hit_multiplier`` at builder time for this weapon
    (confirmed: every builder sets it to ``weapon_defensive_hit_
    multiplier(weapon)`` directly, no further multiplication), but the
    same divide-out-then-multiply-in shape as the offensive fix above is
    used anyway, for the identical robustness reason -- correct
    regardless of what else might already be composed into this
    multiplier.
    """

    for combatant, opponent in ((a, b), (b, a)):
        if combatant.equipped_weapon is Treasure.WEAPON_1 and opponent.is_undead_or_anti_holy:
            base_hit_multiplier = 1.0 + WEAPON_HIT_BONUS[Treasure.WEAPON_1] / 100
            undead_hit_multiplier = 1.0 + HOLY_SWORD_HIT_BONUS_VS_UNDEAD / 100
            combatant.offensive_hit_multiplier = combatant.offensive_hit_multiplier / base_hit_multiplier * undead_hit_multiplier
            combatant.melee_damage_dealt_bonus += HOLY_SWORD_DAMAGE_BONUS_VS_UNDEAD - WEAPON_DAMAGE_BONUS[Treasure.WEAPON_1]
            base_defensive_multiplier = holy_symbol_hit_chance(1.0, HOLY_SWORD_AUTO_PROTECTION_LEVEL)
            undead_defensive_multiplier = holy_symbol_hit_chance(
                1.0, HOLY_SWORD_AUTO_PROTECTION_LEVEL, target_is_undead_or_anti_holy=True
            )
            combatant.defensive_hit_multiplier = (
                combatant.defensive_hit_multiplier / base_defensive_multiplier * undead_defensive_multiplier
            )
        if combatant.has_duellists_medal_ability and opponent.is_humanoid:
            combatant.offensive_hit_multiplier *= 1.0 + MELEE_DUELLISTS_MEDAL_HIT_CHANCE_BONUS
            combatant.melee_damage_dealt_bonus += MELEE_DUELLISTS_MEDAL_DAMAGE_BONUS
            opponent.offensive_hit_multiplier *= 1.0 - MELEE_DUELLISTS_MEDAL_HIT_CHANCE_BONUS
            opponent.melee_damage_dealt_bonus -= MELEE_DUELLISTS_MEDAL_DAMAGE_BONUS
        if combatant.has_control_temper_ability:
            combatant.hit_points += berserk_fury_bonus_hit_points(rng)
        if combatant.has_melee_hit_points_ability:
            combatant.hit_points += roll_melee_hit_points_ability_bonus(rng)
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
    rng: random.Random,
    damage_range: tuple[int, int] = MELEE_DAMAGE_RANGE,
    *,
    hit_chance_multiplier: float = 1.0,
    skill_difference_bonus: int = 0,
) -> int:
    """Rulebook [5.3]: one Melee swing. Returns damage dealt (0 on a miss).

    ``damage_range`` defaults to the character rule; pass an attacker's
    own ``Combatant.melee_damage_range`` for a species-specific die
    (Phase 132 addendum, module docstring). ``hit_chance_multiplier``
    defaults to 1.0 (every pre-Phase-209 caller unaffected); pass a
    defender's own ``Combatant.defensive_hit_multiplier`` (Phase 209) to
    apply Holy Symbol's/Invisibility's own hit-chance reduction.

    ``skill_difference_bonus`` -- sourced directly from the user
    (2026-10-28): "infligge 1-6 punti danno per colpo più 1 per
    differenza nel Talento Melee tra chi attacca e chi difende."
    Defaults to 0 (every earlier caller unaffected -- this project's
    own prior sourced reading of [5.3] had no such term at all, see
    this module's own docstring). Added only on a successful hit (a
    miss stays 0, never turned into damage); callers pass ``max(0,
    effective_melee_skill(attacker) - effective_melee_skill(defender))``
    -- floored at 0 per the user's own confirmation, so a less-skilled
    attacker never deals *less* than the base die roll, only ever a
    bonus when more skilled than the defender.
    """

    if rng.random() < MELEE_HIT_CHANCE * hit_chance_multiplier:
        return rng.randint(*damage_range) + skill_difference_bonus
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


def _acts_first(
    skill_a: int, skill_b: int, rng: random.Random, *, a_always_first: bool = False, b_always_first: bool = False
) -> bool:
    """Rulebook [5.0]: "The character with the greater skill level relevant to the
    tactic he is using generally goes first in the combat round... If
    the skill is the same, the characters go in random order." Returns
    True if the first combatant (by caller's own ordering) acts first.

    ``a_always_first``/``b_always_first`` (``Combatant.always_acts_
    first``, Phase 665 -- Office.ILLUS_MAGE's own Chameleon Familiar):
    checked before the skill comparison, since the real text overrides
    it outright ("always... even if opponent has greater skill"), not
    just another tie-break input. Only one side can realistically be
    ``True`` at a time (a leader holds at most one Office), but if both
    somehow are, this falls through to the ordinary skill comparison
    rather than guessing which title wins. Both default to ``False``
    for every pre-Phase-665 caller.
    """

    if a_always_first and not b_always_first:
        return True
    if b_always_first and not a_always_first:
        return False
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

    Phase 740: ``weapon_proc``/``weapon_proc_hit_points`` carry
    ``apply_weapon_on_hit_effects()``'s own real result -- ``None``/
    ``None`` for every swing that didn't proc one of the two narratable
    weapons (or wasn't even a landed hit), matching every pre-Phase-740
    swing's own implicit shape.
    """

    attacker: str  # "a" / "b"
    hit: bool
    damage: int  # net, post-reduction -- 0 on a miss, possibly also 0 on a reduced hit
    weapon_proc: "WeaponOnHitProc | None" = None
    weapon_proc_hit_points: int | None = None  # the wielder's own new total, only for "shadow_sword_drain"


@dataclass(slots=True)
class ReactiveMeleeSwingResult:
    """``resolve_reactive_melee_swing()``'s own hit-vs-damage detail
    (Phase 416), mirroring ``MeleeSwing``'s own Phase 415 split for the
    same reason -- Spiritwrack can floor a real hit's own net ``damage``
    to 0, so ``damage > 0`` alone can't stand in for ``hit``. Kept
    separate from ``MeleeSwing`` itself because this function has no
    ``"a"``/``"b"`` side label of its own (only the caller, matching
    ``leader_combatant``/``monster_combatant`` to a side, knows that) --
    a caller narrating this swing wraps it into a real ``MeleeSwing``
    itself, supplying the label.

    Phase 740: ``weapon_proc``/``weapon_proc_hit_points`` mirror
    ``MeleeSwing``'s own new fields of the same name -- a caller
    wrapping this into a real ``MeleeSwing`` copies both across too.
    """

    hit: bool
    damage: int  # net, post-reduction -- 0 on a miss, possibly also 0 on a reduced hit
    weapon_proc: "WeaponOnHitProc | None" = None
    weapon_proc_hit_points: int | None = None


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

    Phase 767: right after an attacker's own regular swing, if it left
    the defender still standing, any ``bonus_unanswered_attacks`` that
    swing's own weapon proc (Psychic Flail's stun) just banked are
    resolved immediately, within this same round -- one-sided bonus
    swings against the same defender, no counter-swing, mirroring
    ``turn/challenge_execution.py``/``turn/search_execution.py``'s own
    established ``_consume_bonus_attacks()`` shape (same roll formula,
    no re-triggered weapon proc on the bonus swing itself). Since
    ``resolve_melee_duel()`` is only ever a loop around this function,
    the fix reaches every atomic AND round-stepped Melee caller in this
    project at once. A pre-existing counter value from a Psychic Blast/
    Ice Suspension cast is never observable here -- both of those are
    always drained by their own caller's immediate ``_consume_bonus_
    attacks()`` call before any Melee round can run, so this is a
    provable no-op for every case except a fresh Psychic Flail proc.
    """

    skill_a, skill_b = effective_melee_skill(a), effective_melee_skill(b)
    first, second = (
        (a, b) if _acts_first(skill_a, skill_b, rng, a_always_first=a.always_acts_first, b_always_first=b.always_acts_first) else (b, a)
    )
    outcome = MeleeRoundOutcome(result=None)
    swings: list[MeleeSwing] = []
    for attacker, defender in ((first, second), (second, first)):
        if attacker.hit_points <= 0 or defender.hit_points <= 0:
            continue
        # Phase 1051: both already computed once, above, as skill_a/
        # skill_b -- reused here instead of calling effective_melee_
        # skill() again for every swing (regular and bonus alike) this
        # round, since neither side's melee_skill/neutral_duelist_bonus
        # changes mid-round.
        attacker_skill = skill_a if attacker is a else skill_b
        defender_skill = skill_b if attacker is a else skill_a
        raw_damage = roll_melee_attack(
            rng,
            damage_range=attacker.melee_damage_range,
            hit_chance_multiplier=attacker.offensive_hit_multiplier * defender.defensive_hit_multiplier,
            skill_difference_bonus=max(0, attacker_skill - defender_skill),
        )
        damage = _melee_landed_damage(raw_damage, attacker, defender)
        defender.hit_points -= damage
        proc = apply_weapon_on_hit_effects(attacker, defender, damage, rng)
        proc_hit_points = attacker.hit_points if proc == "shadow_sword_drain" else None
        attacker_side = "a" if attacker is a else "b"
        swings.append(
            MeleeSwing(
                attacker=attacker_side, hit=raw_damage > 0, damage=damage, weapon_proc=proc, weapon_proc_hit_points=proc_hit_points
            )
        )
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
        # Phase 767 -- Psychic Flail's own stun, drained immediately: see
        # this function's own docstring addendum above.
        while attacker.bonus_unanswered_attacks > 0:
            attacker.bonus_unanswered_attacks -= 1
            bonus_raw_damage = roll_melee_attack(
                rng,
                damage_range=attacker.melee_damage_range,
                hit_chance_multiplier=attacker.offensive_hit_multiplier * defender.defensive_hit_multiplier,
                skill_difference_bonus=max(0, attacker_skill - defender_skill),
            )
            bonus_damage = _melee_landed_damage(bonus_raw_damage, attacker, defender)
            defender.hit_points -= bonus_damage
            swings.append(MeleeSwing(attacker=attacker_side, hit=bonus_raw_damage > 0, damage=bonus_damage))
            if attacker is a:
                outcome.damage_dealt_to_b += bonus_damage
            else:
                outcome.damage_dealt_to_a += bonus_damage
            if defender.hit_points <= 0:
                outcome.result = EncounterCombatResult(winner=("a" if defender is b else "b"), rounds=round_number)
                outcome.swings = tuple(swings)
                return outcome
    _apply_end_of_round_regeneration(a, b, round_number)
    outcome.swings = tuple(swings)
    return outcome


def resolve_reactive_melee_swing(attacker: Combatant, defender: Combatant, rng: random.Random) -> ReactiveMeleeSwingResult:
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

    Returns a ``ReactiveMeleeSwingResult`` (Phase 416) -- ``.damage`` is
    this function's own original return value (0 on a miss), so the
    caller can still feed it straight into ``resolve_spell_disruption``/
    ``resolve_spell_disruption_from_missed_attack`` exactly as before
    (unchanged: disruption's own "hit" reading stays ``damage > 0``, not
    ``.hit`` -- see that call site's own Phase 416 note for why); ``.hit``
    is new, for narration callers that need the raw roll the same way
    ``MeleeSwing`` already does. Mutates ``defender.hit_points`` in
    place; the caller checks for death itself (the same convention every
    other Personal-Combat spell effect in this module already follows
    for its own target/caster hit-point checks).
    """

    raw_damage = roll_melee_attack(
        rng,
        damage_range=attacker.melee_damage_range,
        hit_chance_multiplier=attacker.offensive_hit_multiplier * defender.defensive_hit_multiplier,
        skill_difference_bonus=max(0, effective_melee_skill(attacker) - effective_melee_skill(defender)),
    )
    damage = _melee_landed_damage(raw_damage, attacker, defender)
    defender.hit_points -= damage
    proc = apply_weapon_on_hit_effects(attacker, defender, damage, rng)
    proc_hit_points = attacker.hit_points if proc == "shadow_sword_drain" else None
    return ReactiveMeleeSwingResult(hit=raw_damage > 0, damage=damage, weapon_proc=proc, weapon_proc_hit_points=proc_hit_points)


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


def _apply_end_of_round_regeneration(a: Combatant, b: Combatant, round_number: int) -> None:
    """Phase 155 addendum (module docstring): a surviving combatant with
    ``regenerates_hp`` set (Troll's own rule -- 0 for everyone else)
    heals that much at the end of each qualifying combat round, uncapped.

    Phase 666 -- ``regenerates_hp_interval`` (default `1`, Troll's own
    established every-round cadence) gates this to rounds where
    ``round_number % regenerates_hp_interval == 0``, needed by
    Office.NECRO_MAGE's own "1 hit point per 2 rounds" perk.
    """

    if a.hit_points > 0 and round_number % a.regenerates_hp_interval == 0:
        a.hit_points += a.regenerates_hp
    if b.hit_points > 0 and round_number % b.regenerates_hp_interval == 0:
        b.hit_points += b.regenerates_hp


@dataclass(slots=True)
class _FireArrowSide:
    """Phase 1051: one side's own per-call Fire Arrow bookkeeping inside
    ``resolve_fire_arrow_duel()`` below -- introduced once the function's
    own ``if combatant is a: ... else: ...`` blocks were confirmed to be
    the same shot-resolution logic twice over, differing only by which
    side is shooting/shot-at. ``used`` is the only mutable field (the
    shot count consumed so far this duel); everything else is fixed for
    the whole call.
    """

    label: str  # "a" / "b", matching EncounterCombatResult.winner's own convention
    shooter: Combatant
    target: Combatant
    skill: int
    shots_allowed: int
    long_range_multiplier: float
    used: int = 0


def resolve_fire_arrow_duel(
    a: Combatant,
    b: Combatant,
    rng: random.Random,
    *,
    long_range_archer: str | None = None,
    short_range_archer: str | None = None,
    closing_side: str | None = None,
) -> EncounterCombatResult:
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

    Phase 520: each side's own shot count also adds ``archery_free_
    attack_bonus`` (AdvancedAbility.ARCHERY_FREE_ATTACK/_MASTERY/_TRUE_
    MASTERY, default 0) -- see module docstring's own Phase 520 addendum.

    Phase 700 (``AdvancedAbility.LONG_RANGE_ARCHERY``): ``long_range_
    archer`` (default ``None``, every pre-Phase-700 caller unaffected)
    names whichever side is firing from Spell Range under this ability
    -- the *other* side's own shot count is forced to ``0`` (no Archery
    is possible at Spell Range without the ability, so it never fires
    back at all -- confirmed one-sided, see ``turn/challenge_
    execution.py``'s own Phase 700 addendum), and the named side's own
    hit chance gains an extra ``LONG_RANGE_ARCHERY_HIT_MULTIPLIER``
    factor ("half the normal chance to hit").

    Phase 701 (``AdvancedAbility.SHORT_RANGE_ARCHERY``): ``short_range_
    archer`` (default ``None``) works exactly like ``long_range_archer``
    for shot-count one-sidedness -- the other side never fires back --
    but applies no hit-chance multiplier at all, matching this ability's
    own real text ("with the normal chance to hit"), unlike Long Range
    Archery's own halved chance. The two parameters are mutually
    exclusive in practice (a single Fire tactic is only ever resolved
    from one range at a time) but are independent flags here so neither
    accidentally implies the other's own multiplier.

    **2026-11-04 -- RULES.AK [5.2]**: "Se un personaggio riceve l'ordine
    di attaccare con armi da lancio a portata d'incantesimo, si avvicina
    a portata d'arco, consumando così un round e tira quindi nel round
    successivo." ``closing_side`` (default ``None``, every pre-existing
    caller unaffected) names whichever side is closing from Spell Range
    to Bow Range this call -- confirmed with the user: *that* side
    alone skips round 1 entirely (no shot at all that round, not even a
    reduced one -- the round is simply spent moving), while the *other*
    side fires completely normally from round 1 onward, exactly as if
    neither side were closing. The closing side's own total shot count
    is unchanged; it only starts one round later, so the duel runs one
    round longer than it otherwise would whenever that extra round is
    actually needed (never shortened, never fewer rounds than either
    side's own real total requires). Mutually exclusive with ``long_
    range_archer``/``short_range_archer`` in practice (those model a
    caster who skips closing entirely, firing from Spell Range itself,
    the opposite situation) -- not enforced here, since no real caller
    ever passes both.
    """

    skill_a, skill_b = effective_archery_skill(a), effective_archery_skill(b)
    shots_a = fire_arrow_free_attacks(skill_a) + a.archery_free_attack_bonus
    shots_b = fire_arrow_free_attacks(skill_b) + b.archery_free_attack_bonus
    if long_range_archer == "a" or short_range_archer == "a":
        shots_b = 0
    elif long_range_archer == "b" or short_range_archer == "b":
        shots_a = 0
    long_range_multiplier_a = LONG_RANGE_ARCHERY_HIT_MULTIPLIER if long_range_archer == "a" else 1.0
    long_range_multiplier_b = LONG_RANGE_ARCHERY_HIT_MULTIPLIER if long_range_archer == "b" else 1.0
    side_a = _FireArrowSide("a", a, b, skill_a, shots_a, long_range_multiplier_a)
    side_b = _FireArrowSide("b", b, a, skill_b, shots_b, long_range_multiplier_b)
    rounds_needed_a = shots_a + (1 if closing_side == "a" else 0)
    rounds_needed_b = shots_b + (1 if closing_side == "b" else 0)
    total_rounds = max(rounds_needed_a, rounds_needed_b)
    shots: list[FireArrowShot] = []

    round_number = 0
    for round_number in range(1, total_rounds + 1):
        order = (
            (side_a, side_b)
            if _acts_first(skill_a, skill_b, rng, a_always_first=a.always_acts_first, b_always_first=b.always_acts_first)
            else (side_b, side_a)
        )
        for side in order:
            if a.hit_points <= 0 or b.hit_points <= 0:
                break
            if closing_side == side.label and round_number == 1:
                continue  # spent this round closing to Bow Range, not shooting
            if side.used >= side.shots_allowed:
                continue
            side.used += 1
            raw_damage = roll_fire_arrow_attack(
                side.skill,
                rng,
                damage_range=side.shooter.missile_damage_range,
                hit_chance_multiplier=side.shooter.archery_hit_multiplier * side.target.defensive_hit_multiplier * side.long_range_multiplier,
            )
            damage = _fire_arrow_landed_damage(raw_damage, side.shooter, side.target)
            shots.append(FireArrowShot(shooter=side.label, hit=raw_damage > 0, damage=damage))
            side.target.hit_points -= damage
        if a.hit_points <= 0 or b.hit_points <= 0:
            break
        _apply_end_of_round_regeneration(a, b, round_number)

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
    target_has_artificial_organs: bool = False,
    max_rounds: int = 1000,
) -> EncounterCombatResult:
    """Rulebook (module docstring's Phase 190 addendum), the channeled
    Necromancy duel: the caster's own attack always lands (``roll_hand_
    of_death_damage()`` has no hit-chance roll of its own -- it is a
    psychic, not physical, blow) for ``1 + 0.5*level`` damage, uncapped;
    the victim's own Melee counter-attack uses their normal damage die,
    composed exactly like every other Melee swing in this module
    (``victim.offensive_hit_multiplier * caster.defensive_hit_multiplier``
    -- Berserk/Duellist's-Medal/Invisibility etc.), then further halved
    by ``HAND_OF_DEATH_VICTIM_HIT_CHANCE_MULTIPLIER``.
    Initiative uses the caster's own Necromancy skill level in place of
    Melee (``hand_of_death_caster_melee_defense_skill()``, [5.0]'s
    generic rule) against the victim's own real effective Melee skill.

    **Bug fix**: the victim's counter-attack used to be rolled at a flat
    ``HAND_OF_DEATH_VICTIM_HIT_CHANCE_MULTIPLIER`` only, silently
    dropping the composed multiplier above -- an Invisible caster (or a
    Berserk/Duellist's-Medal-equipped victim) was never consulted for
    this one roll, unlike every other Melee swing in this module.

    ``winner="a"`` (the caster) only when the victim's hit points reach 0
    -- "chi lancia questo incantesimo" wins outright, same convention as
    every other instant-resolution Personal-Combat spell. Returns
    ``winner=None`` the instant the victim lands *any* hit on the caster
    that does NOT itself drop the caster's own hit points to 0 or below
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

    **Phase 1050 bug fix -- ``winner="b"`` (the victim) when that same
    disrupting counter-attack is itself lethal.** The disruption-ends-
    the-channel text above only describes a caster who survives the hit
    (the sourced "loses concentration, spell fades" framing presumes
    there's a caster left to lose concentration); it was previously
    returning ``winner=None`` unconditionally, with no check on
    ``caster.hit_points`` at all, unlike every other branch in this
    function (and every other round-based duel resolver in this module)
    that checks the side it just damaged before deciding the outcome.
    Both real callers (``turn/challenge_execution.py``'s and ``turn/
    search_execution.py``'s own ``Spell.HAND_OF_DEATH`` dispatch) trust
    ``winner is None`` to mean "the caster is still a live combatant,
    continue the encounter with a normal tactic" -- with the old
    unconditional ``None``, a caster the counter-attack had just reduced
    to 0 HP or below was carried forward as if still alive, through
    ``_consume_bonus_attacks()`` and into the rest of the encounter
    loop, which could go on to resolve the opponent's own queued tactic
    against an already-dead combatant. Both call sites updated to treat
    ``winner="b"`` the same way they already treat a Melee-duel loss.

    **Phase 884**: ``target_has_artificial_organs`` (``Discovery.
    ARTIFICIAL_ORGANS``) does NOT skip the channel the way ``target_is_
    immune`` does -- it is threaded through to ``roll_hand_of_death_
    damage()`` instead, so the channel still runs (the victim's own
    halved-hit-chance counter-attack can still end it, and the caster
    is still exposed to being hit), but the caster's own squeeze always
    deals 0 damage. See that function's own Phase 884 addendum for why
    the Discovery's own "archery can still be used" clause is
    deliberately not wired here.

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

    **Phase 631 -- closed for good.** The user directly reconfirmed
    this reading ("lo squeeze e' il prose dello spell Hand of Death")
    while `turn/search_execution.py` was being re-checked for a
    separate, unrelated question ("is `Maneuver.SQUEEZE` a real,
    unwired player Search tactic?"). It isn't: `CSqueeze` is CTBOTH.
    PAS's own *only* reference to that maneuver anywhere in the
    surviving source, `Regolamento AK.txt` never documents "Squeeze" as
    a player action, and no real sample `.K1` Encounter Plan ever
    writes `SQ`. The two `Death`-enum and `maneuver`-enum "Squeeze"
    entries are the same underlying narration concept, not competing
    theories -- Hand of Death borrows Giant Octopus's own natural-
    weapon damage-narration category (a category with a genuine
    monster-species owner, `weapkill[Tentacles]`) to narrate its own
    spell attack, exactly as this module already implements.
    """

    if target_is_immune:
        return EncounterCombatResult(winner=None, rounds=0)

    caster_skill = hand_of_death_caster_melee_defense_skill(skill_level)
    victim_skill = effective_melee_skill(victim)
    squeeze_hits: list[int] = []
    round_number = 0
    for round_number in range(1, max_rounds + 1):
        order = (
            (caster, victim)
            if _acts_first(
                caster_skill, victim_skill, rng, a_always_first=caster.always_acts_first, b_always_first=victim.always_acts_first
            )
            else (victim, caster)
        )
        for actor in order:
            if caster.hit_points <= 0 or victim.hit_points <= 0:
                continue
            if actor is caster:
                damage = max(
                    0,
                    roll_hand_of_death_damage(skill_level, rng, target_has_artificial_organs=target_has_artificial_organs)
                    - victim.damage_reduction,
                )
                squeeze_hits.append(damage)
                victim.hit_points -= damage
                if victim.hit_points <= 0:
                    return EncounterCombatResult(winner="a", rounds=round_number, squeeze_hits=tuple(squeeze_hits))
            else:
                raw_damage = roll_melee_attack(
                    rng,
                    damage_range=victim.melee_damage_range,
                    # Bug fix: this used to pass only the flat Hand-of-
                    # Death halving (0.5) as the whole hit_chance_
                    # multiplier, silently dropping victim.offensive_
                    # hit_multiplier/caster.defensive_hit_multiplier --
                    # the same composition every other Melee swing in
                    # this module applies (resolve_one_melee_round above:
                    # attacker.offensive_hit_multiplier * defender.
                    # defensive_hit_multiplier). An Invisible caster (or
                    # a Berserk/Duellist's-Medal victim) was therefore
                    # never consulted for this one roll.
                    hit_chance_multiplier=(
                        victim.offensive_hit_multiplier
                        * caster.defensive_hit_multiplier
                        * HAND_OF_DEATH_VICTIM_HIT_CHANCE_MULTIPLIER
                    ),
                )
                if raw_damage > 0:
                    # Phase 1050 bug fix -- this used to hand-roll `max(0,
                    # raw_damage - caster.damage_reduction)`, the same kind
                    # of composition gap the hit-chance side above was
                    # already fixed for: it silently dropped victim.melee_
                    # damage_dealt_bonus/melee_damage_dealt_reduction (e.g.
                    # Melee Mastery, Spiritwrack), unlike every other real
                    # Melee swing in this module, which routes through the
                    # shared _melee_landed_damage() helper.
                    damage = _melee_landed_damage(raw_damage, victim, caster)
                    caster.hit_points -= damage
                    if caster.hit_points <= 0:
                        return EncounterCombatResult(winner="b", rounds=round_number, squeeze_hits=tuple(squeeze_hits))
                    return EncounterCombatResult(winner=None, rounds=round_number, squeeze_hits=tuple(squeeze_hits))
        _apply_end_of_round_regeneration(caster, victim, round_number)
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
# Stage 1 disbelief roll.
#
# **Phase 470 correction.** Originally set to High Human, confirmed
# directly by the user (project author) pre-disassembly: "L'intelligenza
# di RE ed eroi (per quanto riguarda la difesa dall'incantesimo mirror
# image) e' sempre High Human." ``AKGEN_reverse_engineering_report
# (2).md`` SS21.4 later gave the real compiled answer, with certain
# confidence, directly contradicting that verbal note: "Tutti i
# personaggi giocanti sono codificati direttamente come Medium Human: se
# l'ID del combattente e' inferiore a 256, `AK.OVR 0x1DCAC-0x1DCB7`
# scrive (I=3)... l'intelligenza dei personaggi non va dedotta dalle loro
# abilita', razza o aptitude; e' sempre Medium." Per this project's own
# sourcing hierarchy (a disassembly-certain finding outranks an earlier
# unverified verbal note, the same precedent Phase 467's spell-cap fix
# already established off this same report), the default is corrected to
# Medium Human here.
MIRROR_IMAGE_LEADER_INTELLIGENCE_TIER_DEFAULT = MirrorImageIntelligenceTier.MEDIUM_HUMAN

# On top of that Medium Human base, a King or Hero's own real Sage and
# Illusion skill levels add a further flat bonus to their own chance of
# disbelieving the illusion -- confirmed by the user: "C'e' un bonus di
# +2% sulla tabella per ogni livello in SA e +1% per ogni livello in
# IL." Applied directly on top of the table value, before the caster's
# own -15%/level (max 60%) reduction -- see ``resolve_mirror_image_
# duel()``'s own ``opponent_disbelief_bonus`` parameter. SS21.4 doesn't
# address this bonus at all (it only covers the base intelligence
# classification, ``I``) -- so unlike the tier default just above, it
# isn't contradicted by the new disassembly finding and stays unchanged
# (Phase 470 only re-anchors which table value it's added on top of).
MIRROR_IMAGE_LEADER_SAGE_DISBELIEF_BONUS_PER_LEVEL = 0.02
MIRROR_IMAGE_LEADER_ILLUSION_DISBELIEF_BONUS_PER_LEVEL = 0.01


def mirror_image_leader_disbelief_bonus(sage_level: int, illusion_level: int) -> float:
    """A King or Hero's own flat bonus to their chance of disbelieving a
    Mirror-Image illusion cast against them: +2% per Sage level, +1% per
    Illusion level, added directly to the ``MEDIUM_HUMAN`` table value
    (Phase 470 -- see ``MIRROR_IMAGE_LEADER_INTELLIGENCE_TIER_DEFAULT``'s
    own docstring for why the base tier changed from High Human; see
    ``MIRROR_IMAGE_LEADER_SAGE_DISBELIEF_BONUS_PER_LEVEL``/``MIRROR_
    IMAGE_LEADER_ILLUSION_DISBELIEF_BONUS_PER_LEVEL``'s own docstring for
    the bonus's own source). Monster opponents don't get this bonus --
    it's specific to Kings/Heroes, confirmed by the user.
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
    opponent_has_detect_illusions: bool = False,
    caster_has_detect_illusions: bool = False,
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
    own Sage/Illusion-driven bonus, 0.0 for every other caller -- and
    ``DETECT_ILLUSIONS_DISBELIEF_BONUS`` if ``opponent_has_detect_
    illusions``, Phase 463's own SS21.4 `D` term) may end the illusion's
    power outright. Only ``opponent``'s and the throwaway illusion's own
    hit points change here -- ``caster`` isn't in the fight yet ("the
    caster must concentrate on his illusion, performing no other
    actions"). If the illusion is disbelieved or loses the duel, this
    returns ``winner=None`` (3a: "the caster must continue the fight at
    the current combat range") -- whatever damage the real opponent took
    from the illusion before it lost carries over into that next fight.

    **Stage 2** -- only reached if the illusion *wins* Stage 1 (opponent
    mentally slain). The illusion now turns on the real caster; the same
    per-round disbelief roll applies, this time at ``MIRROR_IMAGE_
    MASTER_DISBELIEF_BASE_CHANCE`` (Medium Human's own 80% base + a flat
    25-point bonus) plus ``DETECT_ILLUSIONS_DISBELIEF_BONUS`` if
    ``caster_has_detect_illusions`` -- the *caster* is the one rolling to
    disbelieve here, so it's their own Detect Illusions that matters, not
    the opponent's (Phase 463's own SS21.7 "opera anche sui personaggi
    che non sono il lanciatore" -- Detect Illusions belongs to whoever is
    currently the disbeliever, not fixed to one role). Interleaved with a
    real Melee duel between
    ``caster`` and the illusion. ``winner="a"`` (the caster) if the
    illusion is disbelieved or slain -- "the caster automatically
    finishes off the already-mentally-slain monster and claims the
    treasure." ``winner="b"`` if the illusion instead reduces the
    caster's own hit points to 0 -- "the illusion fades out, and the real
    monster revives and slays the fallen illusionist" (the *magnitude* of
    the opponent's own revival isn't given anywhere in the source, and
    doesn't change this function's own reported winner, so it isn't
    modeled as a hit-points change here).

    **Phase 1050 bug fix**: each stage's own melee exchange used to
    hand-roll a bare-bones swing (``defender.hit_points -= max(0,
    roll_melee_attack(rng, damage_range=attacker.melee_damage_range) -
    defender.damage_reduction)``) instead of calling this module's own
    ``resolve_one_melee_round()`` -- the single shared per-round Melee
    resolver every other real duel in this file goes through. That
    hand-rolled version silently dropped ``offensive_hit_multiplier``/
    ``defensive_hit_multiplier`` (Temper, Melee Mastery, Duellist's
    Medal, equipped-weapon bonuses, Invisibility/Holy Symbol),
    ``skill_difference_bonus``, ``melee_damage_dealt_bonus``/
    ``_reduction`` (Mastery, Spiritwrack), every weapon on-hit proc
    (Shadow Sword, Flaming Scimitar, Psychic Flail), and end-of-round
    regeneration (Troll, Necro-Mage office) -- for real leaders with
    real stats (``illusion`` is a full-record copy of a real combatant,
    per the Phase 783 addendum below, and ``caster``/``opponent`` are
    always real), not placeholder stat blocks. A nearby comment had
    claimed this was deliberate because these combatants "never carry a
    real leader's own Advanced Ability data in the first place" -- false
    for the real combatants involved, confirmed by directly checking
    both real call sites. Fixed by routing each round's own exchange
    through ``resolve_one_melee_round()`` instead, the same way
    ``resolve_melee_duel()`` already does -- its own internal "who acts
    first" computation (``effective_melee_skill``/``_acts_first``)
    reproduces exactly what this function used to compute inline, so no
    existing RNG-ordering assumption changes beyond what fixing the
    dropped mechanics themselves requires.
    """

    # Phase 783 -- `AKGEN_reverse_engineering_report (2).md` SS21.2
    # confirms the real engine does a single 178-byte memcpy of the
    # opponent's ENTIRE operational combat record, not just hit points/
    # melee stats -- "gli altri campi già materializzati nel record di
    # combattimento vengono copiati" (explicitly naming already-active
    # Invisibility/Holy Symbol effects as examples). `dataclasses.
    # replace()` reproduces this snapshot-at-cast-time copy for every
    # field at once. The one field this project's own simplified melee
    # loop below already consults besides `melee_skill`/`melee_damage_
    # range` is `damage_reduction` (Imperial Defender's armor) -- before
    # this phase, an opponent's own armor protection didn't carry over
    # to their illusion, a real, not just cosmetic, gap.
    illusion = replace(opponent, name=f"{opponent.name}'s Illusion", always_acts_first=False)
    # `illusion` is a fresh construct -- never the ILLUS_MAGE titleholder
    # himself, so `always_acts_first` is explicitly reset to False above
    # regardless of whether `opponent` (Phase 665) holds that title.
    base_chance = MIRROR_IMAGE_DISBELIEF_BASE_CHANCE[opponent_tier] + opponent_disbelief_bonus
    if opponent_has_detect_illusions:
        base_chance += DETECT_ILLUSIONS_DISBELIEF_BONUS

    total_rounds = 0
    stage1_resolved = False
    for round_number in range(1, max_rounds + 1):
        total_rounds = round_number
        if resolve_mirror_image_disbelief(base_chance, skill_level, rng):
            return EncounterCombatResult(winner=None, rounds=total_rounds)
        resolve_one_melee_round(illusion, opponent, rng, round_number=round_number)
        if illusion.hit_points <= 0:
            return EncounterCombatResult(winner=None, rounds=total_rounds)
        if opponent.hit_points <= 0:
            stage1_resolved = True
            break
    if not stage1_resolved:
        return EncounterCombatResult(winner=None, rounds=total_rounds)

    master_chance = MIRROR_IMAGE_MASTER_DISBELIEF_BASE_CHANCE
    if caster_has_detect_illusions:
        master_chance += DETECT_ILLUSIONS_DISBELIEF_BONUS
    for _ in range(1, max_rounds + 1):
        total_rounds += 1
        if resolve_mirror_image_disbelief(master_chance, skill_level, rng):
            return EncounterCombatResult(winner="a", rounds=total_rounds)
        resolve_one_melee_round(caster, illusion, rng, round_number=total_rounds)
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
    opponent_has_detect_illusions: bool = False,
    caster_has_detect_illusions: bool = False,
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
    opponent's own Sage/Illusion bonus, plus ``DETECT_ILLUSIONS_
    DISBELIEF_BONUS`` if ``opponent_has_detect_illusions`` -- same
    convention as ``resolve_mirror_image_duel()``). Disbelieved or lost
    -> ``winner=None`` (the caster resumes fighting for real).

    **Stage 2** -- only reached if the illusion wins Stage 1 *and*
    ``turns_on_master`` is True (the caller's own ``illusory_hero_
    alignments_are_implacably_hostile()`` check -- "the illusory hero
    will usually not turn on its master"). If ``turns_on_master`` is
    False, winning Stage 1 is an outright ``winner="a"`` (caster) with no
    further duel at all. If True, Stage 2 proceeds exactly like Mirror-
    Image's own second stage (the same ``MIRROR_IMAGE_MASTER_DISBELIEF_
    BASE_CHANCE`` plus ``DETECT_ILLUSIONS_DISBELIEF_BONUS`` if
    ``caster_has_detect_illusions``, since no separate number is given
    for Illusory Hero's own version of this branch): ``winner="a"`` if
    the caster disbelieves or slays the illusion, ``winner="b"`` if the
    illusion kills the caster instead.

    **Phase 1050 bug fix**: same hand-rolled-swing gap as ``resolve_
    mirror_image_duel()`` above, and the identical fix -- see that
    function's own Phase 1050 addendum for the full explanation. Both
    melee exchanges below now route through ``resolve_one_melee_round()``
    instead of a bare-bones inline swing.
    """

    # Phase 783 -- same SS21.2 full-record-copy fix as `resolve_mirror_
    # image_duel()` above, applied to `hero` (the current Valhalla
    # visitor) instead of `opponent`; `hit_points` is still explicitly
    # reset to full (an image, not a snapshot of the visitor's own
    # current wounds) and `always_acts_first` explicitly reset to False
    # (never the ILLUS_MAGE titleholder himself, regardless of whether
    # the visiting hero happens to hold that title).
    illusion = replace(hero, name=f"Illusory {hero.name}", hit_points=CHARACTER_HIT_POINTS, always_acts_first=False)
    base_chance = MIRROR_IMAGE_DISBELIEF_BASE_CHANCE[opponent_tier] + opponent_disbelief_bonus
    if opponent_has_detect_illusions:
        base_chance += DETECT_ILLUSIONS_DISBELIEF_BONUS

    total_rounds = 0
    stage1_resolved = False
    for round_number in range(1, max_rounds + 1):
        total_rounds = round_number
        if resolve_illusory_hero_disbelief(base_chance, skill_level, rng):
            return EncounterCombatResult(winner=None, rounds=total_rounds)
        resolve_one_melee_round(illusion, opponent, rng, round_number=round_number)
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
    if caster_has_detect_illusions:
        master_chance += DETECT_ILLUSIONS_DISBELIEF_BONUS
    for _ in range(1, max_rounds + 1):
        total_rounds += 1
        if resolve_illusory_hero_disbelief(master_chance, skill_level, rng):
            return EncounterCombatResult(winner="a", rounds=total_rounds)
        resolve_one_melee_round(caster, illusion, rng, round_number=total_rounds)
        if illusion.hit_points <= 0:
            return EncounterCombatResult(winner="a", rounds=total_rounds)
        if caster.hit_points <= 0:
            return EncounterCombatResult(winner="b", rounds=total_rounds)
    return EncounterCombatResult(winner=None, rounds=total_rounds)


# Steal [ST], rulebook [5.4]/[5.5] -- Phase 239/305, superseded by
# Phase 506 with the real formula, recovered by a disassembly-based
# reverse-engineering pass the user supplied directly (AKGEN_reverse_
# engineering_report (3).md, Part III, "reverse engineering completo
# del comando STEAL"), not the earlier manual-text-only approximation.
#
# The real success formula, from AK.OVR:0x1AADA-0x1AB94:
#
#     raw      = 15 * (1 + min(4,S) + M + I*(1+E)) + P
#     divisor  = 1 + H + R*G
#     chance   = min(95, raw // divisor) / 100
#
# S = effective Thief skill level; M = 1 if the thief holds any Thief
# Mastery tier; I = 1 if Invisibility is active; E = 1 if Enhanced
# Invisibility is also held (only matters when I=1); H = 1 against a
# King or an army-leading Hero; P (SA_Mod, a generic percentage hook)
# is confirmed 0 in ordinary play -- kept at 0 here since nothing
# catalogued feeds it. R*G (Treasury Raiding's own active-flag times
# its own per-King guard counter) is now modeled directly as an
# additive `treasury_raid_guard_counter` term in the divisor below --
# see Phase 786 (`AKGEN_reverse_engineering_report (3).md` SS39.2),
# which also resolves a real manual-vs-binary conflict on the guard's
# own increment trigger: the manual says the guard doubles after ANY
# attempt (success or failure), but the disassembled binary only shows
# it incrementing after a *successful* raid. Per this project's own
# standing "manual vs. AKGEN-report conflict -- ask the user" rule, the
# user confirmed following the binary. This supersedes Phase 702's own
# multiplicative `2 ** attempts` reading, chosen before this binary
# evidence existed.
#
# The integer-division-then-cap order matters: the 95% cap applies
# after raw // divisor, not before.
STEAL_SUCCESS_MAX_CHANCE = 0.95

# Thief Mastery I-V (models/advanced_ability.py) all grant the
# identical "+15% Stealing Bonus" -- any one held is M=1 above,
# regardless of tier. Public (not module-private) since both
# turn/search_execution.py and turn/challenge_execution.py need it to
# derive their own `has_thief_mastery` signal for `resolve_steal_
# attempt()`.
STEAL_THIEF_MASTERY_ABILITIES = frozenset(
    {
        AdvancedAbility.THIEF_MASTERY_I,
        AdvancedAbility.THIEF_MASTERY_II,
        AdvancedAbility.THIEF_MASTERY_III,
        AdvancedAbility.THIEF_MASTERY_IV,
        AdvancedAbility.THIEF_MASTERY_V,
    }
)


def steal_success_chance(
    level: int,
    *,
    has_thief_mastery: bool = False,
    is_invisible: bool = False,
    has_enhanced_invisibility: bool = False,
    target_leads_army_or_is_king: bool = False,
    treasury_raid_guard_counter: int = 0,
) -> float:
    """The thief's own real chance of a successful Steal attempt -- see
    module docstring's own Phase 506 addendum for the full formula and
    its source.

    Phase 786 (``AdvancedAbility.THIEF_TREASURY_RAIDS``, ``AKGEN_
    reverse_engineering_report (3).md`` SS39.2): the real, disassembly-
    confirmed divisor term for Treasury Raiding's own guard counter is
    additive (``1 + H + G``), not multiplicative -- ``treasury_raid_
    guard_counter`` (default ``0``, every pre-Phase-786 caller
    unaffected) is the caller-supplied real per-King guard counter
    ``G``, added directly alongside the existing King/army-leader
    halving term ``H`` rather than multiplying the whole divisor.
    Supersedes Phase 702's own ``treasury_raid_guard_multiplier``
    (``2 ** attempts``), chosen before this binary evidence existed.
    """

    raw = 15 * (
        1
        + min(4, level)
        + int(has_thief_mastery)
        + int(is_invisible) * (1 + int(has_enhanced_invisibility))
    )
    divisor = 1 + int(target_leads_army_or_is_king) + treasury_raid_guard_counter
    return min(STEAL_SUCCESS_MAX_CHANCE, (raw // divisor) / 100)


def resolve_steal_attempt(
    level: int,
    rng: random.Random,
    *,
    has_thief_mastery: bool = False,
    is_invisible: bool = False,
    has_enhanced_invisibility: bool = False,
    target_leads_army_or_is_king: bool = False,
    treasury_raid_guard_counter: int = 0,
) -> bool:
    return rng.random() < steal_success_chance(
        level,
        has_thief_mastery=has_thief_mastery,
        is_invisible=is_invisible,
        has_enhanced_invisibility=has_enhanced_invisibility,
        target_leads_army_or_is_king=target_leads_army_or_is_king,
        treasury_raid_guard_counter=treasury_raid_guard_counter,
    )


def treasury_raid_amount(treasury: int, rng: random.Random) -> int:
    """``AdvancedAbility.THIEF_TREASURY_RAIDS``: "the thief gets away
    with up to half of the treasury".

    Phase 785 -- `AKGEN_reverse_engineering_report (3).md` SS39.2 gives
    the real compiled formula: ``B = treasury // 2``, ``amount = round(B
    * (0.25 + 0.75 * U))`` for a uniform ``U`` in [0, 1) -- a real range
    of 12.5% to 50% of the current treasury (average ~31.25%), not a
    uniform 0%-50% draw. The rulebook's own "up to half" phrasing turns
    out to be literal only as an upper bound; the floor is 12.5%, not
    0%. Supersedes the Phase 702 guess this function's own docstring
    used to describe here ("no exact formula survives... reads 'up to
    half' as a uniform random fraction between 0% and 50%").
    """

    b = treasury // 2
    return round(b * (0.25 + 0.75 * rng.random()))


# The real evasion-after-failure formula, from AK.OVR:0x1AC3C-0x1AC88:
# 0.10 + 0.075 * S, where S is the thief's own effective Thief skill
# level -- explicitly not capped to 4 the way the success formula's own
# S term is (the dossier's own worked table runs the ladder up to
# level 9, 77.5%, with no ceiling named). Supersedes Phase 239's own
# project-original 30%+10%/level approximation.
def steal_evasion_chance(level: int) -> float:
    return min(1.0, 0.10 + 0.075 * level)


def resolve_steal_evasion(level: int, rng: random.Random) -> bool:
    return rng.random() < steal_evasion_chance(level)


# The real per-item transfer-probability decay, from AK.EXE:0x1CAF8-
# 0x1D154: a character target's own eligible treasures are scanned in
# a randomly-rotated order; each one independently rolls against a
# threshold that starts at 75% and is halved via an integer right-shift
# after every item actually transferred (not merely attempted) --
# 75,37,18,9,4,2,1,0%, not a naive float halving (which would give
# 75,37.5,18.75,... instead). Supersedes the single-item-only transfer
# this project used before Phase 506.
def steal_character_item_transfer_chance(items_already_stolen: int) -> float:
    return (75 >> items_already_stolen) / 100


def resolve_steal_character_item_transfer(items_already_stolen: int, rng: random.Random) -> bool:
    return rng.random() < steal_character_item_transfer_chance(items_already_stolen)


# The real ransom amount for a King-vs-King capture, from AK.OVR:
# 0x1AC8D-0x1AF99: half the thief's own treasury, rounded up
# ((treasury + 1) // 2) -- transferred to the victim King's own
# kingdom, not merely subtracted from the thief's. Supersedes the
# earlier "keep the floor half, credit nobody" behavior.
def steal_ransom_amount(thief_treasury: int) -> int:
    return (thief_treasury + 1) // 2


# The real monster item-hiding formula, from the same scan routine:
# trova = 100 - (100 >> (6 - intelligence_ordinal)), then halved via
# the identical integer right-shift after each item transferred.
# Reuses models/monster.py MONSTER_INTELLIGENCE_ORDINAL (Phase 504's
# own fix) directly -- the dossier's own worked table (Mech 99%, Semi
# 97%, Low 94%, Medium 88%, High 75%, Godlike 50%) matches this formula
# exactly only with Mech at ordinal 0, independently confirming Phase
# 504's own correction. Supersedes Phase 239's own three-bucket
# StealTargetCunning approximation, which also checked the wrong thing
# at the wrong point in the sequence -- monster intelligence never
# affects the initial success roll above ("L'intelligenza dei mostri
# interviene soltanto al punto 2" -- only the post-success item scan),
# so this is no longer consulted as a pre-roll gate the way a "monster
# hides its treasure" check used to be.
def steal_monster_item_transfer_chance(intelligence_ordinal: int, items_already_stolen: int) -> float:
    base = 100 - (100 >> (6 - intelligence_ordinal))
    return (base >> items_already_stolen) / 100


def resolve_steal_monster_item_transfer(intelligence_ordinal: int, items_already_stolen: int, rng: random.Random) -> bool:
    return rng.random() < steal_monster_item_transfer_chance(intelligence_ordinal, items_already_stolen)


# The real "gold if no item was stolen" magnitude per monster species,
# from CTME.PAS's own basegold table via AK.EXE:0x1CAF8-0x1D154
# (G_MSteal's own "inc; shr 1" -- ceil(basegold/2)): only consulted
# when the character-item scan above found nothing to transfer
# (monsters hold no ItemInstance in this project's model at all, so
# this branch is always the one that would fire). **Phase 731**: wired
# into `turn/search_execution.py _resolve_steal()` -- credited to the
# thief's own Kingdom treasury, a documented no-op for a kingdomless
# Hero. See that function's own docstring for the full account,
# including why this counts as a real "successful theft result" for
# merit/Add_Experience purposes just like an item transfer would.
MONSTER_STEAL_GOLD_IF_NO_ITEM: dict[Monster, int] = {
    Monster.ROC: 1,
    Monster.GRYPHON: 1,
    Monster.COUATL: 2,
    Monster.GI_EAGLE: 1,
    Monster.SPHINX: 3,
    Monster.R_DRAGON: 5,
    Monster.B_DRAGON: 4,
    Monster.GR_DRAGON: 3,
    Monster.S_DRAGON: 5,
    Monster.GO_DRAGON: 6,
    Monster.GI_WORM: 3,
    Monster.TITAN: 6,
    Monster.GIANT: 2,
    Monster.BIGFOOT: 1,
    Monster.ARCHER: 2,
    Monster.SWORDSMAN: 2,
    Monster.WHITE_MAGE: 2,
    Monster.NEC_MAGE: 3,
    Monster.ELE_MAGE: 2,
    Monster.PSY_MAGE: 3,
    Monster.ILL_MAGE: 2,
    Monster.WITCH: 3,
    Monster.DRYAD: 1,
    Monster.CENTAUR: 1,
    Monster.GENIE: 3,
    Monster.GOLEM: 3,
    Monster.GARGOYLE: 1,
    Monster.BASILISK: 1,
    Monster.MEDUSA: 2,
    Monster.BAL_DEMON: 4,
    Monster.MAR_DEMON: 5,
    Monster.SUCCUBUS: 3,
    Monster.RAKSHASHA: 2,
    Monster.ICE_DEVIL: 5,
    Monster.BONE_DEVIL: 4,
    Monster.IMP: 1,
    Monster.WEREWOLF: 1,
    Monster.CHIMERA: 3,
    Monster.HYDRA: 4,
    Monster.BEHOLDER: 3,
    Monster.TROLL: 2,
    Monster.MINOTAUR: 2,
    Monster.GI_WOLVERINE: 1,
    Monster.TREANT: 1,
    Monster.GI_AMOEBA: 1,
    Monster.GI_P_MANTIS: 1,
    Monster.GI_SCORPION: 1,
    Monster.GI_WASP: 1,
    Monster.GI_SPIDER: 1,
    Monster.GHOST: 2,
    Monster.VAMPIRE: 3,
    Monster.MUMMY: 4,
    Monster.BANSHEE: 1,
    Monster.LICH: 4,
    Monster.SPECTRE: 3,
    Monster.GI_OCTOPUS: 4,
    Monster.GI_CLAM: 3,
    Monster.ELASMOSAURUS: 2,
    Monster.GW_WHALE: 1,
    Monster.MERMAID: 1,
}


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
# Cross-checked against `Desktop/TALK SAY FULFILL.txt`'s own "Ecco una
# tabella di quando livello di DR ci vuole per parlare con i mostri"
# table (identified as the specific source file, Phase 549, during a
# fresh Talk-mechanic audit): 43 of 60 species agreed exactly; where
# the two disagreed (17 species: Beholder, Black Dragon, Chimera,
# Elemental Sorceror, Gargoyle, Ghost, Giant, Giant Clam, Giant Worm,
# Green Dragon, Hydra, Imp, Mermaid, Mummy, Spectre, Troll, Werewolf),
# the user (project author) confirmed directly that the Pascal table
# wins -- see `tests/test_encounter.py test_talk_monster_druid_level_
# required_documented_disagreements_with_user_compiled_list()` for the
# pinned per-species comparison against that file's own values.
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


def resolve_talk_reaction(
    rng: random.Random, *, caster_is_druidic: bool = False, caster_is_silver_tongue: bool = False
) -> TalkReaction:
    """**Phase 468 addendum**: `caster_is_silver_tongue` -- report SS18.4,
    "un mostro non reagisce violentemente a TALK" (a monster never
    reacts violently to Talk for the Silver Tongue titleholder). Applied
    as a post-roll override, not a reweighted probability split: the
    roll still runs against the same (project-original, unsourced)
    Attack/Ignore/Deal split above, but a would-be `ATTACK` is
    downgraded to `IGNORE` for this caster -- the sourced guarantee is
    only "never violent," not "always offered a deal," so `DEAL` stays
    exactly as likely as it already was. Layered this way so the
    override composes cleanly with whichever generator is live here (see
    the `MonsterTalkReply` addendum above) rather than being tied to
    this specific placeholder formula's own internals.
    """

    attack_chance = TALK_DRUIDIC_ATTACK_CHANCE if caster_is_druidic else TALK_ATTACK_CHANCE
    roll = rng.random()
    if roll < attack_chance:
        return TalkReaction.IGNORE if caster_is_silver_tongue else TalkReaction.ATTACK
    if roll < attack_chance + TALK_IGNORE_CHANCE:
        return TalkReaction.IGNORE
    return TalkReaction.DEAL


# **Phase 382 -- the real 24-reply Talk selector, `runtime_mechanics.
# monster_talk` (`AK.OVR TALK branch`/`AK.EXE reply selector`, a real
# static disassembly).** **Stale as of Phase 528, and again as of Phase
# 727 -- frozen at the moment of writing, corrected here.** This
# comment used to say `TalkReaction`/`resolve_talk_reaction()` above
# were still the live mechanism `search_execution.py`'s own Talk branch
# calls, with the reply selector below being additive but "not yet
# wired." Both claims are long superseded: Phase 528 replaced the live
# call with `select_monster_talk_reply()`/`MONSTER_TALK_REPLY_OUTCOME`
# (the reply selector this same comment block introduces), and Phase
# 727 replaced *that* in turn with `turn/monster_raids.py resolve_
# monster_raid_reply()` (a real, deterministic, per-(monster,feature)
# reseed) -- see `search_execution.py _resolve_talk()`'s own docstring
# for the full, accurate account of both supersessions. `TalkReaction`/
# `resolve_talk_reaction()` above are retained for their own existing
# tests only; neither has a production caller anymore.
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

# Phase 1051: hoisted out of `select_monster_talk_reply()`'s own
# rejection loop below, which otherwise rebuilt this identical list from
# the `MonsterTalkReply` enum on every single call -- the uniform-id-
# propose step itself (not the per-call `eligible` filter, which
# genuinely does vary by `monster`) needs no re-deriving.
ALL_MONSTER_TALK_REPLIES: list[MonsterTalkReply] = list(MonsterTalkReply)

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
# source for each one's own request/reward text -- MONSTER_TALK_OFFER_
# TEXT/_FULFILL_TEXT/_ACCEPT_TEXT below transcribe it, Phase 581).
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
# Phase 581: HostAK/TP/PROSE/MTALK.X2 (header "24 3", SAY.PAS:763
# _MReply) -- the monster's own initial quest/agreement offer. Unlike
# FULFILL.X2/MACCEPT.X2 below, every one of the 24 replies has real
# text here, including R_PUZZLED/R_CHARGE/R_WARN/R_MADVANCE despite
# their own non-quest TalkReplyOutcome -- MTALK is shown for every
# reply, not just the quest ones. Sourced from a byte-faithful third-
# party reverse-engineering pass over the full 162-file prose corpus
# (AKPROSE_reverse_engineering_report.md, supplied directly by the
# user) -- the "not transcribed here, out of scope" gap MONSTER_TALK_
# REPLY_OUTCOME's own comment previously flagged.
# Stored as raw template text: the </>/[/]/[1/\ pronoun and item-name
# markers, {...}/R alternation syntax, and CTRL-byte codes (report/
# prose.py's own module docstring covers the render-time meaning of
# each) are kept literal, not resolved -- this project's own pronoun-
# substitution system remains explicitly out of scope, same posture
# models/office.py OFFICE_TITLE_DESCRIPTION already took.
MONSTER_TALK_OFFER_TEXT: dict[MonsterTalkReply, str] = {
    MonsterTalkReply.R_PUZZLED: 'but [1 just looked at <2 in puzzlement/Rconfusion, {apparently }unable to comprehend/Runderstand > words/Rspeech.',
    MonsterTalkReply.R_CHARGE: '[1 attacked without warning.',
    MonsterTalkReply.R_WARN: '[1 looked at <2 sternly and said "You have not been invited here.Away with you, before I decide to take more drastic action!"',
    MonsterTalkReply.R_REGAIN: 'sayeth/RReplieth [1, "I long to regain ⟦CTRL-A:a/an⟧ certain magic item, one which my clan had possessed for years but was unjustly/Rwrongfully taken from us.That artifact is called the ⟦CTRL-T:treasure-2⟧.if you bring it here to me, I will reward you by giving you the \\."(The Gods will deem/Rconsider this quest/Rmission completed/Raccomplished by ⟦CTRL-A:a/an⟧ character who brings the ⟦CTRL-T:treasure-2⟧ to [ in the & and FU-lfills the quest).',
    MonsterTalkReply.R_VISIT: '[1 looked at <2 {whimsically, yet }thoughtfully/Rmeditatively.Spake/RSayeth [1, "In the {faraway }province of ⟦CTRL-X:province-3⟧, ⟦CTRL-U:visit⟧When you have accomplished/Rcompleted your quest/Rmission, you can/Rmay take/Rhave the \\.i\'m_afraid/Runfortuantely I can\'t give_you_directions/Rtell_you_how_to_get_there, because {all of }my maps were stolen/Rlost some/Ra_long time ago."(The Gods will deem/Rconsider this quest/Rmission completed/Raccomplished if < will simply undertake the journey and return to FU-lfill the quest with [ in the &.No exploration or other special action need be performed).',
    MonsterTalkReply.R_RIDDLE: 'asketh [1, ⟦CTRL-G:riddle⟧If you are smart/Rclever enough to answer/Rsolve this riddle{ (and from the looks of you, I sincerely/Rreally doubt/Rquestion that)} you may/Rcan have/Rtake the \\.Go, and do not return/Rcome_back without the answer/Rsolution!"(The Gods will deem/Rconsider this riddle/Rpuzzle solved/Ranswered if ⟦CTRL-A:a/an⟧ character who possesses the riddle and the answer returns/Rcomes_back to SA-y the answer and then FU-lfill with [ in the &.Take as many guesses in your next visit as you want).',
    MonsterTalkReply.R_FREVENGE: 'sayeth/RReplied [1, "I have long sought to gain/Rtake my revenge on ⟦CTRL-C:quest-character⟧, who killed/Rmurdered my father/Sbrother.Bring the slimeball\'s/Rscoundrel\'s head/Rscalp to me, and I will see {to it }that you are_given/Rreceive ⟦CTRL-A:a/an⟧ just/Rfitting reward."(The Gods will deem/Rconsider this quest/Rmission completed/Raccomplished if < will {find and }kill ⟦CTRL-C:quest-character⟧ and return/Rcome_back to FU-lfill the quest with [ in the &.)',
    MonsterTalkReply.R_PAIN: 'sayeth/RSpake [1, "I have ⟦CTRL-A:a/an⟧ terrible/Rexcruciating pain in my foot/Sside.{I cannot sleep while this pain afflicts me.}you, who are {so much }wiser/Rsmarter than I{ can ever hope to be}, {please }come closer/Rhither, so that you may {find the cause/Rsource of my pain and }relieve my suffering."(The Gods will deem/Rconsider this request/Rplea agreed to by any character who returns to FU-lfill the agreement/Rbargain with [ in the &).',
    MonsterTalkReply.R_SLAVE: 'spake/RSayeth [1, "I have need of someone to take care of me in my old age.Stay here for the rest of my life as my slave/Rservant, and you shall be generously included in my will.I have, perhaps, 2 years left to live."(The Gods, looking down from on high, will deem/Rconsider this request/Rplea agreed to by any character who returns/Rcomes to FU-lfill the bargain with [ in one phase of the year of the death of [, whenever that may be).',
    MonsterTalkReply.R_MATE: 'replied/RSpake [1, "I {am devastated/Rburdened with loneliness and }have need of ⟦CTRL-A:a/an⟧ {loving }mate.Outcasts like me/Rmyself rarely enjoy/Rhave {romantic }company and can only find/Rachieve {real }happiness with someone/Ranother of our own kind.if you can bring_me_a_map_showing/Rfind_me ⟦CTRL-A:a/an⟧ feature/Rplace inhabited/Rheld by a monster like me, you may/Rcan have/Rtake the \\, as well as my profound/Rsincere thanks/Rgratitude."(The Gods will deem/Rconsider this quest/Rmission completed/Raccomplished if ⟦CTRL-K:king-title⟧ locates such ⟦CTRL-A:a/an⟧ feature and one of the Kingdom\'s characters returns/Rcomes_back to FU-lfill the quest with [ in the &).',
    MonsterTalkReply.R_TRADE: 'spake/RReplied [1, "There is ⟦CTRL-A:a/an⟧ {certain }magic item/Rartifact which I prefer_to/Rwould_rather_have_than the \\ in my ownership/Rpossession.If/RWhen you can bring/Rshow me the ⟦CTRL-T:treasure-2⟧, I will trade/Rexchange my \\ for it."(The Gods will deem/Rconsider this quest/Rmission completed/Raccomplished when any character who possesses/Rhas the ⟦CTRL-T:treasure-2⟧ returns/Rcomes to FU-lfill the bargain/Ragreement with [ in the &).',
    MonsterTalkReply.R_WISH: 'spake/Rreplied [1, "It is within my power to grant you one wish.You may have any magic item in the whole world-- you need but ask and thou shalt receive."(The Gods whisper ⟦CTRL-A:a/an⟧ hint in the ear of <:  Any character need only SA-y the magic item\'s name and FU-lfill with [, and [1 will give him the magic item in this world which most closely resembles the wished-for item.[1 will then depart this earth.)',
    MonsterTalkReply.R_SELL: 'spake/RSayeth [1, "I will let_you/Rallow_you_to buy/Rpurchase the/Rmy \\.But you must {be willing to }pay {me }the sum of # gold for it."(The Gods will deem/Rconsider this bargain/Rdeal agreed/Rconsented to by any character whose Kingdom/Rrealm has sufficient/Renough gold to buy/Rpurchase the \\, and returns/Rcomes to FU-lfill the bargain/Rdeal with [ in the &).',
    MonsterTalkReply.R_SOUL: 'spake/RSayeth [1, "I will gladly sell you the \\.But I doubt if you are willing to pay the price!You must GIVE ME YOUR SOUL!HA HA-HA-HA-HA!Merely/RJust sign this contract I give you, and the deal/Rbargain will be done/Rmade!"(your patron Deity whispers ⟦CTRL-A:a/an⟧ caution:  Only a King may sell his soul, because none of your characters would ever willingly do so.Never again can the King practice White Magic.[1 also grabs your children\'s souls, so that if the king dies, you have no heir and you are out of the game.To accept this diabolical contract, go to [ in the & and FU-lfill the bargain!)',
    MonsterTalkReply.R_SACH: 'sayeth [1, "You may have the \\.It means little to ⟦CTRL-A:a/an⟧ being such as I, who craves only the wickedly tangy taste of a helpless humanoid soul.If you want the \\, then bring me a character of the Kingdom of ⟦CTRL-K:king-title⟧, so that I may devour his contemptible soul!"(The Gods then whispered in > ear: you must send ⟦CTRL-A:a/an⟧ ruthless character with one of your trusting characters to Search the & on the same phase.He must FU-lfill the bargain, while the other character must use no encounter plan.he will be thrust into the lair of [ and devoured).',
    MonsterTalkReply.R_WFREE: 'sayeth [1, "Many years ago, I was magically chained here by {a curse thrown upon me by }a {terrible }sorcerer.Only ⟦CTRL-A:a/an⟧ renowned White Magician may free me.Should the day {ever }come when I am {once }again free, I will reward my savior with the \\."(The Gods will deem/Rconsider this bargain/Rdeal agreed/Rconsented to by any character with ⟦CTRL-A:a/an⟧ skill/Rlevel of 3 or higher/Rbetter in White Magic who comes/Rreturns to FU-lfill the bargain/Ragreement with [ in the &).',
    MonsterTalkReply.R_JUNDEAD: 'replied/RSayeth [1, "Only if you join/Runite_with the ranks of the Undead may you wield/Rhave the \\.Come, touch/Rtake my hand and I will wither/Rdrain your soul away to total_hollowness/Rnothingness.It won\'t hurt{ much}, I promise{ you}!"(The High Gods whisper in your ear... Only ⟦CTRL-A:a/an⟧ King may become Undead, as no ordinary character will chance it.To gain the \\, a King must come/Rreturn to the & to FU-lfill the bargain/Ragreement.a King who becomes Undead will have lost the last shreds of humanity left to him by the end of the gameturn.He then wanders off into the blackness of the night, never to be seen nor heard from again.His heir gains his treasures, including the \\).',
    MonsterTalkReply.R_PREVENGE: 'replied/RSpake [, "Years ago, I was terribly wronged by ⟦CTRL-C:quest-character⟧, who felled me with ⟦CTRL-A:a/an⟧ treacherous backstab and left me for dead.I survived, but now I live {only }for revenge.If you {find ⟦CTRL-C:quest-character⟧ and }slay the {despicable }slimebag/Rsleazeball, the \\ is yours."(The Gods will deem/Rconsider this quest/Rmission completed/Raccomplished if < {finds and }kills ⟦CTRL-C:quest-character⟧ and returns/Rcomes_back to FU-lfill the quest with [ in the &.',
    MonsterTalkReply.R_DRAIN: 'replied/RSayeth [1, "I can/Rwill let you have/Rtake the \\.But first, you must quench/Rsatisfy my desire/Rthirst for your {heroic }{life-}essence.Come{ here}.I promise/Rgive_you_my_word_that I will drain/Rsuck_away only half of your {life }energy."(The Gods will deem/Rconsider this bargain agreed/Rconsented to by any character who returns/Rcomes to FU-lfill the bargain with [ in the &.if [1 keeps ] promise, all abilities and aptitudes will be halved.When halving odd abilities, there is ⟦CTRL-A:a/an⟧ 50% chance each of rounding upwards or downwards).',
    MonsterTalkReply.R_CIRCNAV: 'spake/RSayeth [1, "I am willing to give/Raward the \\ as ⟦CTRL-A:a/an⟧ honor/Rtrophy to the Explorer who proves_to/Rconvinces me that the world is ⟦CTRL-A:a/an⟧ globe."(The Gods will deem/Rconsider this quest/Rmission completed/Raccomplished when ⟦CTRL-A:a/an⟧ character with {some }Explorer ability who is with a Kingdom which has at least 2% exploration of at least 1 province in each longitude comes/Rreturns to FU-lfill the quest with [ in the &).',
    MonsterTalkReply.R_2POLES: 'spake/RSayeth [1, "Legends say/Rhave_it that {both }the northern and southern hemispheres/Rpoles are covered/Roverlain by great icecaps.I will give this \\ {only }to the Explorer who gains knowledge of both icecaps and reports to me of their nature."(The Gods will deem/Rconsider this quest/Rmission completed/Raccomplished when ⟦CTRL-A:a/an⟧ character with some Explorer ability who is with a Kingdom which has at least 2% exploration in at least one province in both the northernmost and southernmost rows of provinces returns to FU-lfill the quest with [ in the &).',
    MonsterTalkReply.R_1TERR: 'spake [1, "I have ⟦CTRL-A:a/an⟧ special interest in the ⟦CTRL-H:terrain-2⟧ terrain of the/Rthis world.In fact, I hope to write a book on the ⟦CTRL-H:terrain-2⟧ provinces{ of the world}.I will award/Rgive the \\ to the Explorer who maps every ⟦CTRL-H:terrain-2⟧ province {in the world }and reports back to me."(The Gods will deem/Rconsider this quest/Rmission completed/Raccomplished when ⟦CTRL-A:a/an⟧ character with some Explorer ability who is with a Kingdom which has at least 1% exploration of each ⟦CTRL-H:terrain-2⟧ province in the world returns to FU-lfill the quest with [ in the &).',
    MonsterTalkReply.R_EXPALL: 'replied/RSpake [1, "I wish to learn/Rknow all there is to know/Rlearn of this land/Rprovince and adjacent provinces.Explore 100% of @ and its/Rthe adjacent provinces and you may come_back/Rreturn to report and claim/Rreceive the \\!"(The Gods will deem/Rconsider this quest/Rmission completed/Raccomplished when ⟦CTRL-A:a/an⟧ character with some Explorer ability who is with a Kingdom which has explored 100% of @ and the provinces surrounding it returns to FU-lfill the quest with [ in the &).',
    MonsterTalkReply.R_MADVANCE: '[1 advanced, ] hollow/Rlifeless eyes filled/Rglowering with ⟦CTRL-A:a/an⟧ eerily/Rstrangely luminous/Riridescent darkness.',
}
# HostAK/TP/PROSE/FULFILL.X2 (header "24 1", SAY.PAS:764 _LSpake) -- the
# questing character's own line when returning to claim the reward.
# Choices 1-3 and 24 (R_PUZZLED/R_CHARGE/R_WARN/R_MADVANCE) are the
# source's own literal "na" -- these four replies never reach a real
# quest to fulfill, mapped to the empty string, same sentinel-blank
# convention as MONSTER_TALK_OFFER_TEXT's own R_MADVANCE above.
# R_WISH is genuinely blank in the source (not "na") -- REPORTS.PAS's
# own agreements table has the hero's wish spoken via a separate SAY
# order instead, per this project's own already-documented finding
# (report/turn_report.py's own Phase 129 addendum, choice 12).
MONSTER_TALK_FULFILL_TEXT: dict[MonsterTalkReply, str] = {
    MonsterTalkReply.R_PUZZLED: '',
    MonsterTalkReply.R_CHARGE: '',
    MonsterTalkReply.R_WARN: '',
    MonsterTalkReply.R_REGAIN: 'Spake/RSayeth <, "I have brought {you }the ⟦CTRL-T:treasure-2⟧, which you claimed to be rightfully thine.Now, I claim the \\ as my reward!"',
    MonsterTalkReply.R_VISIT: 'sayeth/RSpake <, "I have accomplished the important {and difficult }task/Rmission you asked/Rrequested of me.May/RMight I now claim/Rtake the \\ as my reward/Rpayment?"',
    MonsterTalkReply.R_RIDDLE: 'sayeth/RSpake <, "Now that I have answered your clever/Rdevious riddle{ and proved that I am the cleverer/Rsmarter of the two of us}, let me have that \\!"',
    MonsterTalkReply.R_FREVENGE: 'sayeth/RSpake <, "I have dealt/Rmeted_out the Justice of the Sword to ⟦CTRL-C:quest-character⟧, who slew/Rkilled your father/Sbrother.Though my_heart_be/RI_am_truly sickened by this feud, I now claim/Rdemand the \\ as my payment/Rreward!"',
    MonsterTalkReply.R_PAIN: "filled with compassion/Rpity, < approached [.< spotted/Respied the cause of ['s affliction/Rpain almost immediately:  A {nasty }thorn was protruding/Rsticking_out_of ] foot/Sside. < bent over to remove the thorn.",
    MonsterTalkReply.R_SLAVE: '< visited [, bringing/Roffering food/Rprovisions, and {for ⟦CTRL-A:a/an⟧ time }cared after [{, a fierce/Rstrong but waning/Raged creature/Rbeing}.',
    MonsterTalkReply.R_MATE: 'sayeth/RSpake <, "Painstakingly have I consulted our Royal Archives, and with great success!We do indeed know of ⟦CTRL-A:a/an⟧ lair where dwells another monster such as thee.And with this map I have drawn, you will soon find the way to your true love!"',
    MonsterTalkReply.R_TRADE: 'sayeth/RSpake <, "Behold!I have secured/Robtained the ⟦CTRL-T:treasure-2⟧, the greatest desire of thy dreams.I offer ⟦CTRL-A:a/an⟧ trade:  the ⟦CTRL-T:treasure-2⟧ for the \\!"',
    MonsterTalkReply.R_WISH: '',
    MonsterTalkReply.R_SELL: 'sayeth/RSpake <, "Our magnificent Kingdom has more than gold enough to pay for the \\.Have you honor enough to keep your end of the bargain?"',
    MonsterTalkReply.R_SOUL: 'sayeth/RSpake <, "What does ⟦CTRL-A:a/an⟧ mere mortal soul matter, when I can possess the power of the \\?I want it!Just show me where to sign my name so we can be done with it and I can be off to conquer the world!Everything will be mine, mine, mine!"',
    MonsterTalkReply.R_SACH: '< dragged > "friend" into the & and threw the poor soul at [\'s feet.< watched calmly as [1 greedily devoured ] meal.When [1 was finished, < said "I trust that you enjoyed your meal?Now, how about giving me that \\?"',
    MonsterTalkReply.R_WFREE: 'overcome by compassion/Rpity at the plight/Rpredicament of [, < walked up to [.Waving > hands high in the air, < invoked divine magical forces to free [ from ] sorcerous prison.',
    MonsterTalkReply.R_JUNDEAD: 'sayeth/RSpake <, "I have determined to throw my lot in with the ranks of the Undead.Why not, when ⟦CTRL-A:a/an⟧ short and painful life is the miserable lot of mortal man?Wither my soul away to nothingness, only let me have the \\ to give to my heirs!"',
    MonsterTalkReply.R_PREVENGE: 'sayeth/RSpake <, "I have slain/Rkilled the vile/Rtreacherous ⟦CTRL-C:quest-character⟧.No doubt the scoundrel/Rrascal hath passed to ⟦CTRL-A:a/an⟧ plane of existence as dark and vile as ⟦CTRL-C:quest-character⟧\'s morbid soul!Now that justice has been done, I claim the \\ as my reward!"',
    MonsterTalkReply.R_DRAIN: 'Spake <, "Drastic though the loss of half my soul would be, it is well worth the risk for the power of the \\!On your honor, you will drain only half my soul?""You can trust me," replied [.[1 then gripped <2 and slowly drained away half > essence.',
    MonsterTalkReply.R_CIRCNAV: 'sayeth/RSpake <, "Great distances have I travelled and long hours have I spent researching the map room of the Royal Library.But I must confess that I have failed to prove the world to be ⟦CTRL-A:a/an⟧ globe.Nay, instead it seems to be a cylinder!"',
    MonsterTalkReply.R_2POLES: 'sayeth/RSpake <, "Great distances have I travelled and long hours have I spent researching the map room of the Royal Library.I found the world to be indeed capped by ⟦CTRL-A:a/an⟧ frozen wasteland in the north and cradled by glacial fingers in the south."',
    MonsterTalkReply.R_1TERR: 'spake <, "Great distances have I travelled and long hours have I spent researching the map room of the Royal Library.I have visited ⟦CTRL-H:terrain-2⟧s all over the world until I can\'t stand the sight of them anymore!Um-- You mentioned something about ⟦CTRL-A:a/an⟧ reward?"',
    MonsterTalkReply.R_EXPALL: 'sayeth/RSpake <, "Our Kingdom has sent its explorers throughout @ and the provinces adjoining it.With great thoroughness we have explored these provinces.No effort has been spared and no vale nor dale has been overlooked!"',
    MonsterTalkReply.R_MADVANCE: '',
}
# HostAK/TP/PROSE/MACCEPT.X2 (header "24 2", SAY.PAS:788 _MFulf) -- the
# monster's own reply once the quest/agreement is fulfilled, granting
# the reward. Same "na" sentinel convention as MONSTER_TALK_FULFILL_
# TEXT above for R_PUZZLED/R_CHARGE/R_WARN/R_MADVANCE.
MONSTER_TALK_ACCEPT_TEXT: dict[MonsterTalkReply, str] = {
    MonsterTalkReply.R_PUZZLED: '',
    MonsterTalkReply.R_CHARGE: '',
    MonsterTalkReply.R_WARN: '',
    MonsterTalkReply.R_REGAIN: 'replied [1, "Well done, {my }friend.I{, and my clan also,} will always be/Rremain grateful for your righteous/Rheroic deeds/Ractions!Here is your {well-deserved }reward."< extended > hand{s} and {reverently/Rthankfully }accepted the \\ from [.< then left/Rdeparted_from the &, proud to have succeeded_in/Raccomplished such ⟦CTRL-A:a/an⟧ worthy/Rrighteous quest/Rmission.',
    MonsterTalkReply.R_VISIT: 'replied [1, "I didn\'t expect you to survive/Rmake_it_through the perils/Rhazards of the journey/Rmission{ so quickly/Reasily}, yet/Rbut {nevertheless }I will honor/Rrespect our agreement/Rcontract."saying this, [1 gave_up/Rsurrendered the \\.< ran > hands/Rfingers lovingly/Raffectionately over the \\, bowed_before/Rthanked [ and left/Rdeparted_from the &.',
    MonsterTalkReply.R_RIDDLE: '[1 glared/Rglowered{ in anger} at <2, but managed to hold ] temper in check."Take the \\," said [1, "{But }I never/Rdon\'t want to see your {ugly/Rstupid }face {in here }again!"< proudly/Rarrogantly took/Rgrabbed the \\ and departed_from/Rleft the &.',
    MonsterTalkReply.R_FREVENGE: 'replied [1, "Revenge at last,{ sweet, sweet revenge}!You may have the \\, as well as my sincere/Rprofound gratitude/Rthanks."< accepted/Rreceived the \\ from [ and {reverently }kissed/Rfondled > new {prized }possession.Thanking [ profusely, < then left/Rdeparted_from the & whistling ⟦CTRL-A:a/an⟧ light-hearted song/Rditty.',
    MonsterTalkReply.R_PAIN: '[1 breathed/Rlet_out ⟦CTRL-A:a/an⟧ sigh of {joyous }relief and said to <2, "Thank you, my friend.You may certainly take/Rhave the \\.I don\'t really know/Rsee what good it is/Rwould_do_me{ anyway}, nor do I {even }know how to use it{\'s power}!"< laughed and picked up the \\."Farewell, and may you stay in good health", said <.[1 smiled with ] ferocious maw and < almost fell down backwards.< departed > new friend somewhat reluctantly.',
    MonsterTalkReply.R_SLAVE: '[1 fell tragically ill that season.Breathing ] last gasps of air, [1 spoke to <2, offering ] thanks for > kind assistance.] final strained words were, "I leave to you all that I own, including the \\.Take good care of it!And long live great ⟦CTRL-K:king-title⟧!"< buried [ with deep sadness in > heart and almost reluctantly entered [\'s treasure room to find the \\.',
    MonsterTalkReply.R_MATE: '[1 wasted no time in departing on ] romantic pilgrimage.< walked over to the \\ and bagged it.',
    MonsterTalkReply.R_TRADE: '[1 reluctantly pulled out ] \\ and spoke slowly.  "I will part with the \\, though I treasure it greatly.Use it well!"[1 extended the \\, < held forth the ⟦CTRL-T:treasure-2⟧ and the exchange was made."it\'s been ⟦CTRL-A:a/an⟧ pleasure doing business with you," < said.< then left/Rdeparted_from the & in a self-congratulatory mood, overjoyed to have obtained the \\ for a minor sacrifice like the ⟦CTRL-T:treasure-2⟧.',
    MonsterTalkReply.R_WISH: '[1 looked keenly at <2, nodded sagaciously and deeply intoned ] edict."So be it!You shall have the \\, and may it serve you well."There was ⟦CTRL-A:a/an⟧ blinding flash, and [1 was gone.In ] place was the \\!< dived on it and grabbed > prize.',
    MonsterTalkReply.R_SELL: '[1 held forth ] \\ and nodded.  "Honor enough, and more.Show me your gold."< unpacked ⟦CTRL-A:a/an⟧ chest filled with treasure and displayed the great hoard of gems within.[1\'s eyes sparkled with greed as [1 let the gems run through ] fingers.[1 let drop the \\.< walked over to the \\ and picked it up, fighting off ⟦CTRL-A:a/an⟧ sudden impulse to stab [ while ] back was turned and grab ] gold too.< left the & with > \\.',
    MonsterTalkReply.R_SOUL: '[1 grinned evilly and placed ] copy of the contract on the table, lovingly smoothing out the wrinkles in the paper."Just sign on the dotted line," said [1, proffering ⟦CTRL-A:a/an⟧ pen.< took the pen and signed it, already quivering with anticipation for the \\."and here is your \\," spake [."Enjoy!"< picked up the \\ and examined it, hands shaking with wanton avarice.< didn\'t bother to listen to [\'s evil cackling as [1 faded out into ] own hellish plane of existence.',
    MonsterTalkReply.R_SACH: '[1 licked ] chops while it spoke."An excellent meal, if I do say so myself!Here\'s your \\," said [1, "And I do hope we can do business again someday."< picked up the \\."Don\'t forget to finish your plate," said <, stepping over > friend\'s corpse.< walked away from the &, whistling while he walked away from the gory scene of > friend\'s demise.',
    MonsterTalkReply.R_WFREE: '[1 laughed and cavorted about, reveling in ] new-found freedom.< had to put up with these antics for what seemed like forever, but finally [1 calmed down."You have earned both the \\ and my enduring gratitude," said [1, and proffered the \\ to <2.< accepted the \\, and the twain parted with ⟦CTRL-A:a/an⟧ friendly handshake.< left the & and examined the \\ absent-mindedly, almost too exhilarated from > deeds that day to take much interest in it.',
    MonsterTalkReply.R_JUNDEAD: '[1 twisted ] mouth into ⟦CTRL-A:a/an⟧ evil grin."I assure you," said [1, "that you have made an excellent decision.Now, this won\'t hurt but ⟦CTRL-A:a/an⟧ little."[1 touched the forehead of < with a single finger and dreamily drained <2 of the essence of > soul.< mechanically picked up the \\ and turned to go, all > interest in life totally extinguished.',
    MonsterTalkReply.R_PREVENGE: 'sayeth [1, "Yea, I have heard the news of thy deeds.The bards shall sing of thy adventures for centuries to come.Take then this \\ as your reward.Use it to cleanse the world of all evildoers!"< extended > hands and thankfully accepted the \\ from [.< bowed deeply, then left/Rdeparted_from the &, head held high with pride in > great/Rworthy accomplishments/Rdeeds.',
    MonsterTalkReply.R_DRAIN: 'When [1 was done/Rfinished, [1 reluctantly retreated to ] dark bedchamber for ⟦CTRL-A:a/an⟧ long rest.< soon found the \\ and picked it up.< left the & feeling somewhat drained, but happy to have possession of the \\.',
    MonsterTalkReply.R_CIRCNAV: 'replied [1, "Hmm!This I did not expect!What kind of God would make the world ⟦CTRL-A:a/an⟧ little cylinder with empty space in the middle?The Gods must truly be crazy!But for your valiant efforts, I nevertheless award you the \\."Thus said, [ gave the \\ to <2.relieved, < accepted the \\ from [1.< departed from the & excited with > newly-won prize and dreaming of the greatness < would achieve with it, though to be sure, > confidence in the gods was somewhat shaken.',
    MonsterTalkReply.R_2POLES: 'replied [1, "Well done!You have enriched the world with your bold expeditions and sagely researches.Here is the \\, your well-earned reward."< was guided to ⟦CTRL-A:a/an⟧ treasure room by [, where the \\ rested on a velvet pillow.< accepted the \\ gratefully.[ and < exchanged mutual thanks and well-wishings and parted company.< left the & with ⟦CTRL-A:a/an⟧ a song in > heart!',
    MonsterTalkReply.R_1TERR: '[1 peered at <2 through ] spectacles and smiled glowingly.Sayeth [, "Ah!With this new information I shall write ⟦CTRL-A:a/an⟧ compendium of the world\'s ⟦CTRL-H:terrain-2⟧s which will thrill the world of scholarship!I owe you my profound thanks, as well as, I believe, the \\!"< soon had the \\ in > possession and left the & and [, who was muttering something about ⟦CTRL-A:a/an⟧ "Nobel prize" (whatever that is.)',
    MonsterTalkReply.R_EXPALL: '[ looked suspiciously at <2.For hours, [ questioned <2 and examined > maps, comparing them with ] own records.Finally, [ pronounced ] satisfaction and led <2 to ⟦CTRL-A:a/an⟧ treasure room where lay the \\.Reluctantly [1 handed the \\ to <2 and bade <2farewell.< left the &, so overjoyed at owning the \\ that it felt like ⟦CTRL-A:a/an⟧ feather in > hands.',
    MonsterTalkReply.R_MADVANCE: '',
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

    Phase 1051: reviewed as a possible efficiency cleanup -- rejection
    sampling over all replies, restricted to the ones ``eligible`` for
    this ``monster``, is indeed more rolls on average than the closed-
    form weighted choice this docstring's own opening paragraph already
    names as mathematically equivalent. Left as the real described loop
    anyway, deliberately, per this project's own stated convention
    above; only ``ALL_MONSTER_TALK_REPLIES`` (this function's own
    previously-rebuilt-every-call ``list(MonsterTalkReply)``) was hoisted
    to a module constant, since that part varies with nothing.
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

    while True:
        candidate = rng.choice(ALL_MONSTER_TALK_REPLIES)
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
# **`resolve_fulfill_honored()` below WAS project-original** (the
# original paragraph, kept for history): the rulebook quote above is
# entirely qualitative (no numeric formula, no definition of what the
# deal's own "conditions" concretely are) -- so, rather than invent deal
# *content* (an item, a gold amount, ...) with nothing to source it
# from, this project modeled only the abstract "was the deal honored"
# roll the quote actually describes, the same narrow-but-honest slice
# `turn/plan_dispatch.py`'s own Recruit/Hire co-location checks already
# take for similarly under-specified mechanics. The old formula reused
# `models/alignment.py ALIGNMENT_ORDINAL` for "how far apart" the two
# alignments were, plus a flat penalty when the guardian was Evil -- all
# three of its constants were unsourced, confirmed design choices, the
# same "no numeric split given anywhere" category
# `TALK_ATTACK_CHANCE`/`TALK_IGNORE_CHANCE`/`TALK_DRUIDIC_ATTACK_CHANCE`
# above document for Talk's own reaction roll.
#
# **Phase 525 addendum: the dossier supersedes the above with the exact
# formula.** `AKGEN_reverse_engineering_report (3).md`'s "Dossier
# FULFILL (FU)" section disassembles the real `WillHonor` routine
# (`AK.OVR:0x194E4-0x1963B`):
#
#     roll = random_0_99()
#     divisor = 1 + Ord(bonus > 0)                     ; 1 or 2
#     natural   = 20 * abs(6 - monster_align)           ; 6 = Hellish ordinal
#     mismatch  = 15 * abs(monster_align - hero_align)
#     threshold = (natural + bonus - mismatch) div divisor   ; Pascal `div`,
#                                                              ; truncated
#                                                              ; toward zero
#     honors = roll < threshold
#
# `bonus` varies by which of the dossier's 24 Quest/reply branches fired
# (SS79): `100` for the large majority (RRegain, RRiddle, RFRevenge,
# RPain, RTrade, RSell, RSacH, RWFree, RPRevenge, the 4 Explorer
# Quests -- the dossier's own "formula comune"), `0` for RDrain (also
# gates the intelligence veto below), `125` for RVisit, `1000` for
# RWish (effectively always honored). This project deliberately does
# not model those 24 distinct branches (Phase 258's own scope note --
# Fulfill here is only the abstract "was the prior Talk's deal
# honored" roll) so every call uses the dossier's own common-formula
# default, `FULFILL_COMMON_BONUS = 100`.
#
# RDrain's intelligence veto (SS82, `0x195C0-0x19622`): "if the
# defender is a Feature's guardian monster, bonus <= 0, and the
# monster's intelligence is above Semi (`Mech=0, Semi=1, Low=2,
# Medium=3, High=4, Godlike=5`), honor is vetoed outright, no roll."
# Implemented on the general-purpose `fulfill_monster_honors()` below
# for fidelity to "the exact formula," even though this project's own
# one real call site always uses `bonus=100` (never <= 0) and so never
# triggers it -- kept reachable/testable in isolation as the sourced
# foundation for any future phase that adds real RDrain-specific
# Fulfill support.
#
# Silver Tongue (`HonorOrBetray`, SS83-84, `0x19816`/`0x19828-0x1983E`):
# "if actor is the Diplomat titleholder, always honors" -- short-
# circuits before `WillHonor` is even called, bypassing the roll *and*
# the intelligence veto (already `resolve_fulfill_honored()`'s own
# `caster_is_silver_tongue` short-circuit below, unchanged by this
# addendum).
#
# Worked examples straight from the dossier (SS80, bonus=100):
# Worldly(3) monster vs Worldly(3) hero: threshold=(60+100-0)/2=80 ->
# betrayal 20%. Hellish(6) monster vs Heavenly(0) hero:
# threshold=(0+100-90)/2=5 -> betrayal 95%. Evil(5) monster vs Evil(5)
# hero: threshold=(20+100-0)/2=60 -> betrayal 40%.
#
# `FULFILL_UNRECORDED_ALIGNMENT_FALLBACK = Alignment.NEUTRAL` remains a
# project-original (NOT dossier-sourced) substitute for a missing
# `guardian_alignment`/`character_alignment` -- Neutral sits at the
# ordinal midpoint (3 of 0-9), introducing no systematic directional
# bias, mirroring this project's broader "unrecorded data reads as the
# least-consequential default" convention. The dossier's own formula
# has no `None`-handling of its own (the real engine always has both
# alignments recorded), so this fallback is this project's own
# graceful-degradation choice, exactly like the old code's admittedly
# unsourced "skip the term" convenience it replaces.
FULFILL_HELLISH_REFERENCE_ORDINAL = ALIGNMENT_ORDINAL[Alignment.ANTI_HOLY]  # 6, dossier's "Hellish" reference point
FULFILL_COMMON_BONUS = 100  # dossier SS79's own "formula comune" bonus
FULFILL_UNRECORDED_ALIGNMENT_FALLBACK = Alignment.NEUTRAL  # project-original, NOT dossier-sourced


def _trunc_div(numerator: int, divisor: int) -> int:
    """Pascal `div` truncates toward zero; Python's `//` floors -- this
    matters for the FULFILL threshold formula's `natural + bonus -
    mismatch` numerator, which can go negative."""

    quotient = abs(numerator) // divisor
    return quotient if numerator >= 0 else -quotient


def fulfill_honor_threshold(monster_alignment: Alignment, hero_alignment: Alignment, bonus: int) -> int:
    """The dossier's `WillHonor` threshold (SS78) compared against a 0-99
    roll -- see the module comment above `FULFILL_HELLISH_REFERENCE_ORDINAL`
    for the full sourcing and worked examples."""

    monster_ordinal = ALIGNMENT_ORDINAL[monster_alignment]
    hero_ordinal = ALIGNMENT_ORDINAL[hero_alignment]
    natural = 20 * abs(FULFILL_HELLISH_REFERENCE_ORDINAL - monster_ordinal)
    mismatch = 15 * abs(monster_ordinal - hero_ordinal)
    divisor = 2 if bonus > 0 else 1
    return _trunc_div(natural + bonus - mismatch, divisor)


def fulfill_monster_honors(
    monster_alignment: Alignment,
    hero_alignment: Alignment,
    bonus: int,
    rng: random.Random,
    *,
    monster_intelligence: MonsterIntelligence | None = None,
) -> bool:
    """The dossier's `WillHonor` (SS78, SS82) -- threshold-vs-roll plus the
    RDrain intelligence veto. See the module comment above
    `FULFILL_HELLISH_REFERENCE_ORDINAL` for full sourcing."""

    threshold = fulfill_honor_threshold(monster_alignment, hero_alignment, bonus)
    if (
        bonus <= 0
        and monster_intelligence is not None
        and MONSTER_INTELLIGENCE_ORDINAL[monster_intelligence] > MONSTER_INTELLIGENCE_ORDINAL[MonsterIntelligence.SEMI]
    ):
        return False
    return rng.random() < threshold / 100


def resolve_fulfill_honored(
    guardian_alignment: Alignment | None,
    character_alignment: Alignment | None,
    rng: random.Random,
    *,
    caster_is_silver_tongue: bool = False,
    bonus: int = FULFILL_COMMON_BONUS,
    guardian_intelligence: MonsterIntelligence | None = None,
) -> bool:
    """Whether the guardian honors a deal a prior Talk secured -- see the
    module comment above for the formula's own sourcing and constants.

    **Phase 468 addendum**: `caster_is_silver_tongue` -- report SS18.4,
    "[il titolare] ... onora sempre un accordo completato" (the Silver
    Tongue titleholder's own deals are *always* honored). Short-circuits
    to `True` before the threshold formula runs at all -- an
    unconditional guarantee, not a boosted chance, and consumes no `rng`
    roll (nothing to roll for a certainty).

    **Phase 525 addendum**: `bonus`/`guardian_intelligence` expose the
    dossier's own `WillHonor` parameters; see the module comment above
    for full sourcing. `guardian_alignment`/`character_alignment` of
    `None` fall back to `FULFILL_UNRECORDED_ALIGNMENT_FALLBACK`
    (project-original, not dossier-sourced).
    """

    if caster_is_silver_tongue:
        return True

    monster_alignment = guardian_alignment if guardian_alignment is not None else FULFILL_UNRECORDED_ALIGNMENT_FALLBACK
    hero_alignment = character_alignment if character_alignment is not None else FULFILL_UNRECORDED_ALIGNMENT_FALLBACK
    return fulfill_monster_honors(monster_alignment, hero_alignment, bonus, rng, monster_intelligence=guardian_intelligence)


# Beg [BE], rulebook [5.8] -- Phase 241 originally shipped this as
# project-original ("No Pascal source and no rulebook text survive for
# this tactic... designed collaboratively with the user"), keyed on
# monster intelligence tier. **Phase 749 supersedes that placeholder**:
# `Desktop/SE+SC.md` SS40 (raw `AK.OVR 0x1C8A8-0x1C9BF`, graded CERTO)
# recovers the real, disassembled mercy formula --
#
#   A = ALIGNMENT_ORDINAL[target_alignment]      { the one being begged }
#   H = ALIGNMENT_ORDINAL[beggar_alignment]
#   threshold = 20 * abs(6 - A) - 15 * abs(A - H)   { percent, no explicit clamp in the compiled code }
#   mercy <=> IRand100 < threshold
#
# -- keyed on *alignment distance*, not intelligence, with `6` the
# Hellish/Anti-Holy reference point (`FULFILL_HELLISH_REFERENCE_
# ORDINAL`, already defined above for an unrelated formula, reused
# verbatim here). Verified by hand against every one of SS40's own
# worked examples: Heavenly/Heavenly=120->100%, Worldly/Worldly=60->
# 60%, Evil/Evil=20->20%, Hellish/anything except zero distance-><0->
# 0%, Undead/Undead=20->20%, Mechanical/Mechanical=40->40% -- all match
# exactly against this project's own `ALIGNMENT_ORDINAL` (`models/
# alignment.py`), which already uses the real Pascal `outlook` ordinal
# sequence this formula needs.
#
# Two of the original three Phase 241 design points still stand,
# undisturbed by the new document (which is silent on both): Beg is
# only meaningful once the character has already taken damage this
# same encounter (checked by the caller, `turn/search_execution.py
# _resolve_beg()`, via `Combatant.hit_points < CHARACTER_HIT_POINTS`),
# and a successful plea ends the encounter exactly like a successful
# Flee -- SE+SC.md SS40/43 independently reconfirm this exact outcome.
# `None` alignments (unrecorded) fall back to `FULFILL_UNRECORDED_
# ALIGNMENT_FALLBACK`, the same convention `resolve_fulfill_honored()`
# already uses for the identical situation.
def mercy_chance(target_alignment: Alignment | None, beggar_alignment: Alignment | None) -> float:
    target = target_alignment if target_alignment is not None else FULFILL_UNRECORDED_ALIGNMENT_FALLBACK
    beggar = beggar_alignment if beggar_alignment is not None else FULFILL_UNRECORDED_ALIGNMENT_FALLBACK
    a = ALIGNMENT_ORDINAL[target]
    h = ALIGNMENT_ORDINAL[beggar]
    raw = 20 * abs(FULFILL_HELLISH_REFERENCE_ORDINAL - a) - 15 * abs(a - h)
    return max(0.0, min(100.0, raw)) / 100


def resolve_beg_for_mercy(
    target_alignment: Alignment | None, beggar_alignment: Alignment | None, rng: random.Random
) -> bool:
    return rng.random() < mercy_chance(target_alignment, beggar_alignment)


# Rulebook [5.6]/TABELLA DEI TEMPERAMENTI's own "refusal to Meet" half of
# the flee-probability/refusal-to-Meet mechanic this module's own Phase
# 284 addendum (module docstring, above) deferred as "a natural, distinct
# follow-up phase" -- Phase 898 closes it. Quoted in full:
#
#   I personaggi Codardi e Cauti che non siano Re possono persino
#   rifiutare l'ordine di Incontrare un personaggio o un mostro, a
#   seconda della forza dell'avversario.
#   [TABELLA DEI TEMPERAMENTI -- "Fuga dal combattimento" / "Rifiuto"]
#     Cauto     1-50%
#     Codardo   51-100%
#   N.B. Un Re Codardo o Cauto non rifiuterà mai il combattimento, benché
#   possa sempre fuggire dopo essere stato colpito.
#
# Berserk/Brave carry no entry at all in the table's own Refusal column
# (never refuse, 0%), and a King of any Temper never refuses either (the
# N.B. above) -- both checked unconditionally, before Temper is even
# consulted.
#
# **How "the strength of the opponent" picks a value inside each named
# range is not stated anywhere and is this project's own documented
# design choice**, the same treatment `turn/combat.py estimate_win_
# probability`'s own two-anchor curve, and the pre-disassembly Battle-
# luck/Multiple-Contingents percentages, already received (see this
# project's README "Known-unresolved semantics" precedent): at the point
# an Encounter is accepted or refused, no `Combatant` (and therefore no
# strength/quality figure) exists yet for either side -- only each
# `LeaderState` and whether either one commands an army. `opponent_
# leads_army` reuses the exact same binary "is this a serious threat"
# signal [3.12]'s own neighboring King/Hero acceptance rules already key
# their own restrictions on, picking the range's low end (no army led) or
# high end (leads an army) rather than inventing a continuous ratio this
# project has no real input to compute. Revisit if a real AKGEN
# disassembly of this exact mechanic ever surfaces, matching every other
# design-choice bullet in this project's own history.
REFUSAL_TO_MEET_CHANCE_RANGE: dict[Temper, tuple[float, float]] = {
    Temper.CAUTIOUS: (0.01, 0.50),
    Temper.COWARDLY: (0.51, 1.00),
}


def refusal_to_meet_chance(temper: Temper | None, *, is_king: bool, opponent_leads_army: bool) -> float:
    """[5.6]'s own "refusal to Meet" chance for a non-King Cautious/Cowardly
    character. Returns 0.0 for a King (any Temper), Berserk, Brave, or an
    unrecorded (``None``) Temper -- see the module comment just above for
    the ``opponent_leads_army`` design choice.
    """

    if is_king or temper not in REFUSAL_TO_MEET_CHANCE_RANGE:
        return 0.0
    low, high = REFUSAL_TO_MEET_CHANCE_RANGE[temper]
    return high if opponent_leads_army else low


def resolve_refusal_to_meet(
    temper: Temper | None, *, is_king: bool, opponent_leads_army: bool, rng: random.Random
) -> bool:
    """Rolls ``refusal_to_meet_chance()`` -- ``True`` means the character
    refuses the order to Meet outright, per [5.6].

    No ``rng`` consumed when the chance is a guaranteed 0.0 (a King, an
    unrecorded Temper, or Berserk/Brave) -- the same "no roll needed for
    a certain outcome" convention this project's own guaranteed-escape
    Flee-first branches already established, and the only way every
    pre-Phase-898 test's own scripted RNG sequence (built for a
    Temper-less fixture) stays unaffected by this new check.
    """

    chance = refusal_to_meet_chance(temper, is_king=is_king, opponent_leads_army=opponent_leads_army)
    return chance > 0.0 and rng.random() < chance


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
