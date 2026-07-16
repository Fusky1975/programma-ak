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
the new `models/monster.py TELEKINETIC_STORM_SUBMARINE_MONSTERS`):
"inefficace contro i mostri sottomarini" reads as the storm not
manifesting at all against them, so both the victim's own damage *and*
the caster's own self-damage are suppressed together when immune --
unlike Spiritwrack's own Undead/Mechanical immunity (Phase 182), which
only ever affected the target's side, never the caster's.
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
