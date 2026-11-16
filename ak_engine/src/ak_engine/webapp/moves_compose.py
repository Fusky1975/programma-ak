"""The GM webapp's own "compose moves" editor -- lets the GM build a
Kingdom's move submission for the next turn directly from the
interface, instead of always having to upload a real ``.K1`` file
(sourced directly from the user, 2026-10-26).

**The base, deliberately generic**: every phase (``P0``..``P4``) takes
a plain ``ActionCode`` + an ``obj`` integer + a list of ``extra``
integers -- the exact same three values a real move file's own ``P<n>
: <action> <obj> <extra...>`` line carries, with no command-specific
guidance. A friendlier form per action is being decided one command at
a time with the user; **Move (``ActionCode.LMOVE``) is the first one**
(2026-10-26, the user's own choice -- rulebook's own first-listed
action): confirmed directly from ``turn/plan_dispatch.py``'s own LMOVE
branch that ``obj`` is the *only* field Move reads (``turn/hex_
numbering.py decode_hex_number(phase.obj, board_width)``, the target
province) -- ``extra`` is never consulted; every army the moving leader
already commands (``GameState.armies_commanded_by(leader_id)``) moves
together automatically, nothing to list. The GM's own chosen syntax
(2026-10-26): a province-name dropdown (``province_options()`` below)
replaces the raw Object field for a Move phase specifically. **Explore
(``ActionCode.EXPLORE``) is the second one** (2026-10-26, the user's own
choice -- rulebook's own second-listed action, and their own direct
observation): confirmed directly from ``turn/plan_dispatch.py``'s own
EXPLORE branch that neither ``obj`` nor ``extra`` is read at all --
``province = state.provinces[state.leaders[leader_id].location]``, the
acting leader's own current province, always. Explore needs no input
whatsoever; ``obj``/``extra`` are simply forced to ``0``/``[]``.
**Search (``ActionCode.SEARCH``) is the third, and the user's own
explicit "telaio" (skeleton/frame) request** (2026-10-26): the target
feature number, via a dedicated feature dropdown (``feature_options()``
below) -- confirmed directly from ``turn/search_decode.py``'s own
module docstring/``SearchRequest``: ``obj`` is the target feature's own
number, ``extra[0]`` ("tl") is an unconfirmed, always-``0``-in-every-
real-sample slot, and the remainder of ``extra`` is a ``-1``-terminated
**Encounter Plan** tactic list (Cast, Use Item, Talk, Say, Give,
Fulfill, Steal, Shoot, Melee, Flee, Beg, Scout -- rulebook [5.1]-[5.8]),
designed with the user one tactic at a time, via ``TACTIC_SLOT_COUNT``
(``7``, the longest real ``AK3__T*.K1`` sample's own tactic list)
dedicated ``tactic_<leader>_<n>_<slot>`` dropdowns per Search phase,
each with an optional ``tactic_sub_<leader>_<n>_<slot>`` sub-object
field for a ``TACTICS_WITH_SUB_OBJECT`` maneuver composable here
(Cast/Use Item -- see below for why Give, also in that frozenset, is
excluded from Search specifically) or a ``tactic_say_<leader>_<n>_
<slot>`` free-text field for Say (see below). An empty slot stops the
list there -- a later non-empty slot after one is rejected, not
silently dropped. ``Maneuver.NONE`` is never composable (a sentinel,
never a real tactic).

**Talk ([5.5]), the user's own first tactic to design** (2026-10-26,
sourced directly from them): "può essere usata solo all'inizio del
piano d'incontro. Se viene usata dopo un'altra tattica viene
semplicemente ignorata" -- confirmed structurally impossible to even
select here instead of silently inert: Talk is only ever offered in
slot 0's own dropdown, and ``_parse_search_tactics()`` rejects it
outright at any other slot (a direct, tampered POST bypassing the
dropdown) rather than letting a real-but-inert tactic through quietly.
"Come da regolamento, Non è possibile usare sia la tattica Talk che
Fulfill nello stesso Piano d'Incontro" -- independently confirmed from
``turn/search_execution.py``'s own ``_resolve_fulfill()`` docstring
(rulebook [5.6]): rejected if both appear in the same tactic list.

**Fulfill ([5.7]), the second tactic designed** (2026-10-27, sourced
directly from the user): "Funziona solo se un eroe o un re ha
ricevuto da un mostro nei turni precedenti dopo una tattica TALK una
quest (numerata col numero d'ordine del feature). Se la quest è
risolta l'eroe o il re riceve il premio" -- independently confirmed
from ``turn/search_execution.py``'s own ``_resolve_fulfill()``:
``feature.pending_deal_leader_id`` (set by a *prior* turn's successful
Talk, ``_resolve_talk()``) must equal the acting leader's own id, and
the targeted feature is already exactly the one this same Search
phase's own ``obj`` names -- there is no separate "quest id" to pick,
only the feature dropdown already built for Search itself.
**Nothing new to compose for Fulfill, structurally**: it carries no
sub-object (confirmed absent from ``TACTICS_WITH_SUB_OBJECT``) and has
no position restriction of its own (unlike Talk) -- it was already
fully selectable, in any slot, the moment ``_COMPOSABLE_MANEUVERS`` and
the Talk/Fulfill exclusion above existed. The one real, useful addition
here is informational: ``feature_options()``'s own ``leader_id``
parameter flags a feature this leader already holds a pending deal on
("-- pending quest for this leader"), so the GM can actually tell,
right in the Search dropdown, which feature a Fulfill tactic would do
something on this turn.

**Say ([5.3]), the third tactic designed** (2026-10-27, sourced
directly from the user, rulebook text pasted verbatim): "Un personaggio
può dire tutte le parole indicate dal giocatore, entro un limite di
160 caratteri. Questa azione non fa consumare tempo di combattimento.
La successiva tattica del personaggio è eseguita nello stesso round di
combattimento della tattica Say" -- confirmed structurally from
``turn/search_execution.py``'s own ``Maneuver.SAY`` branch (a
documented no-op: ``continue``, never consumes a combat round, exactly
matching "non fa consumare tempo di combattimento"). Unlike Talk, Say
has no position restriction of its own -- the rulebook text the user
pasted never says otherwise, and "il personaggio può fare tutti i
tentativi che vuole" (repeated riddle attempts) implies it can appear
more than once in the same Encounter Plan, anywhere in the sequence,
including right before another real tactic in the same round. Its own
free-text argument -- a real on-disk exception, written on the line(s)
right after the SAY ordinal's own line rather than as a plain int (see
``parser/k1_moves_writer.py``'s own matching support) -- is read from
a dedicated ``tactic_say_<leader>_<n>_<slot>`` field instead of the
generic sub-object one, validated non-blank and at most 160 characters
(the rulebook's own stated limit) by ``_parse_search_tactics()``.

**Give, the fourth tactic considered -- deliberately excluded from
Search's own Encounter Plan here** (2026-10-28, sourced directly from
the user, rulebook text pasted verbatim): "si può dare qualsiasi
numero di oggetti a chiunque si incontra... Non è però possibile
scambiare oggetti per denaro... il comando GIVE non si usa in un piano
d'incontro quando si incontra un mostro in un feature. Ma solo quando
si crea un piano d'incontro dopo l'uso del comando EN (encounter) o il
comando PU (pursue)" -- independently investigated against ``turn/
search_execution.py``'s own ``_resolve_give_tactic()``: the *only*
real, wired effect ``Maneuver.GIVE`` has anywhere in the engine today
is a narrow, unrelated mechanic (the ``AdvancedAbility.DRUIDIC_TRADES``
Druid-trades-an-item-for-a-monster's-treasure special ability, gated
behind that specific ability and a live, un-looted guardian) that
happens to share the same ``GI`` wire token -- not the general
"hand over any number of items to whoever you meet" tactic the user
described. ``turn/challenge_execution.py`` (Challenge/``EN``) and
``turn/pursue_execution.py`` (Pursue/``PU``) don't dispatch ``Maneuver.
GIVE`` at all yet ("every other tactic is unwired -- skip it and keep
walking"), and neither has its own Encounter Plan editor here yet
either. Rather than offer a tactic that would either (a) silently
trigger the unrelated Druidic Trades mechanic when the user asked for
the general item-giving one, or (b) be a true no-op in a Challenge/
Pursue plan this editor can't even build yet, Give is excluded from
``tactic_options()``'s own Search dropdown entirely (and rejected
server-side on a direct, tampered POST) until Challenge/Pursue's own
Encounter Plan editor exists to give it a real home.

**Steal, the fifth tactic designed** (2026-10-28, sourced directly
from the user, rulebook text pasted verbatim): "si può rubare... o ci
riesce oppure viene scoperto... Le tattiche Steal, Talk, Fulfill si
escludono a vicenda e solo una di esse può essere usata in ciascun
Piano d'Incontro... il comando steal può essere usato solo all'inizio
o dopo un comando CA-IN (cast invisibility)" -- independently
investigated against ``turn/search_execution.py``'s own ``_resolve_
steal()``: in a Search-triggered encounter the target is always the
feature's own guardian monster (never a King/army-leading Hero, so the
rulebook's own army-halving/execution/ransom branches structurally
never apply here -- those only fire in a Challenge/Pursue encounter,
which has no composer of its own yet, same situation as Give above).
What *does* apply, and is already fully implemented and tested there:
the success roll, the monster's own intelligence-weighted item-hiding
scan, the evasion-on-failure roll, and (if caught) combat at a
randomly chosen range -- nothing new to execute, only to compose.
Carries no sub-object (absent from ``TACTICS_WITH_SUB_OBJECT``, like
Fulfill). Three rules enforced by ``_parse_search_tactics()``: (1) the
three-way Steal/Talk/Fulfill exclusion, generalizing the existing
Talk/Fulfill one above; (2) Steal's own position restriction --
slot 0, or immediately after a slot holding ``Maneuver.CAST`` with
``Spell.INVISIBILITY`` as its sub-object (confirmed: ``CAST``'s
sub-object *is* the spell id, and there is no other, separate
"Enhanced Invisibility" spell to also allow -- only ``Spell.
INVISIBILITY`` itself). This position rule is enforced server-side
only, unlike Talk's: whether a given slot is legal depends on the
*previous* slot's own two fields (its maneuver and its sub-object
text), not on the slot index alone, so there's no static per-slot
dropdown filtering to apply the way Talk's "slot 0 only" rule allows
-- Steal stays offered in every slot's dropdown, and a position
violation is only ever caught by posting the form.

**Flee, the sixth tactic designed** (2026-10-28, sourced directly from
the user, rulebook text pasted verbatim): "La probabilità di fuggire
davanti ai mostri veloci è del 20%, davanti a quelli di media velocità
o di altri personaggi è del 50%, mentre davanti a quelli lenti è
dell'80%... I personaggi Cauti hanno il 30% in più di possibilità di
fuggire... la tattica flee si può usare solo una volta a piano
d'incontro" -- independently investigated against ``turn/search_
execution.py``'s own ``FLEE_CHANCE``/``effective_flee_chance()``: the
speed-based 20/50/80% base chance and the Cautious +30% bonus are
*already fully implemented and tested* -- nothing new to execute, only
to compose (Flee carries no sub-object, like Fulfill/Steal/Scout). Two
pieces of the pasted text describe mechanics this investigation found
are **not** GM-composable at all, for two different reasons, so
neither gets anything added here: a weak-tempered character fleeing
*involuntarily, without being ordered to at all* ("indipendentemente
dal Piano d'Incontro") is a genuinely open engine gap today (confirmed
absent from both ``search_execution.py`` and ``challenge_execution.py``
-- there's nothing yet to compose against); a Cowardly/Cautious
non-King refusing an Encounter order outright is instead fully
implemented, but as an automatic, pre-tactic-list engine check run
before the Encounter Plan is ever consulted (``turn/encounter.py
resolve_refusal_to_meet()``), the same "automatic, zero GM-composable
surface" category as the pending-deal flag Fulfill's own dropdown
label surfaces, or the always-on no-op this module's own Say section
already identified for a different tactic. The one real, new rule
``_parse_search_tactics()`` enforces here: Flee can appear **at most
once** per Encounter Plan -- a genuine, currently *unenforced*
rulebook rule (same category Talk's and Steal's own position rules
were before this round), not merely redundant with Flee's own control
flow: a *successful* Flee always ends the Encounter Plan on the spot,
but a *failed* one falls through to whatever comes next, so nothing
in the engine's own tactic walk stops a second Flee entry later in the
same plan from being reached and rolled again.

**Beg, considered next -- deliberately excluded, like Give above**
(2026-10-28, the user's own question: "Questa tattica non esiste. Non
c'è nel regolamento e io per esperienza personale non l'ho mai usata e
vista usare... credo che con beg tu ti riferisca a quando un mostro o
un eroe codardo chieda di avere salva la vita"): independently
confirmed against ``Regolamento AK.txt`` itself -- Beg is genuinely
**not** one of the Encounter Plan's eight numbered [5.1]-[5.8]
tactics (Cast/Fire-Arrow/Melee/Negotiations/Steal/Flee/Give/Scout);
the rulebook instead documents "Implorare pietà" (beg for mercy)
purely as an *automatic* behavior of the Cowardly Temperament,
parallel to involuntary Flee, in the separate Temperament Table --
exactly the user's own guess. ``turn/search_execution.py``'s own
``_resolve_beg()``, however, *does* wire ``Maneuver.BEG`` as a genuine,
player-orderable Search tactic (damaged leader only, alignment-based
~50% mercy roll, ends the encounter like a successful Flee on
success) -- real, tested code, but sourced from reverse-engineering
the compiled game binary rather than from the rulebook text or any
surviving Pascal source the project has, and never exercised by any
real ``AK3__T*.K1`` sample. Offering a tactic the rulebook never lists
as composable, in a dropdown meant to mirror the rulebook's own
numbered list, would mislead the GM into thinking it's a real [5.x]
command -- so, per the user's own choice, Beg is excluded from
``tactic_options()``'s own Search dropdown (and rejected server-side
on a direct, tampered POST), the same shape as Give's own exclusion
above. ``turn/search_execution.py``'s own ``_resolve_beg()`` is left
untouched -- out of scope for this editor, not a correctness question.

**Scout, the seventh tactic designed -- needed no new validation code
at all** (2026-10-28, sourced directly from the user, rulebook text
pasted verbatim): "E' assolutamente irrilevante in che punto del Piano
d'Incontro si trova l'ordine relativo a questa tattica. Il computer si
limiterà a prender nota della tattica Perlustrare e la gestirà dopo
che tutte le altre tattiche di incontro sono state eseguite" --
independently confirmed structurally from ``turn/search_execution.py``'s
own ``_apply_scout()``: it's a genuine post-processing pass, applied
once *after* the whole tactic walk finishes, regardless of Scout's own
slot index, and ``turn/sep_decode.py plan_intent()`` (the classifier
that decides whether Scout *discovers* or *triggers* a Special
Location's event, based on which other tactics are in the plan) treats
``Maneuver.SCOUT`` itself as a transparent no-op in its own walk --
Scout genuinely never affects, or is affected by, its own position.
Carries no sub-object, like Fulfill/Steal/Flee. **Unlike Flee, Scout
has no "at most once" cap** -- a *second* Scout occurrence in the same
plan is a real, meaningful, different input (not a harmless repeat):
it's this game's own consent signal for a handful of costed Feature
Powers (Pay Up/Drain Skill/Drain Courage, confirmed in ``turn/
feature_power_execution.py``'s own condition gate, each requiring
``scout_orders_given >= 2`` to accept their own terms) and separately
caps Scout's own discovery depth at "blind use" rather than full
disclosure. So every slot already offers Scout with no filtering, and
``_parse_search_tactics()`` needed no new rule at all -- the existing,
generic per-slot walk already composes any number of Scout entries
correctly, by construction.

This also answers the user's own, explicitly-flagged-as-uncertain
gameplay memory about "a double Scout command (SC, SC) to activate a
Special Location later": confirmed, but not quite as recalled -- it's
not "discover now, then give two separate Scout orders on some future
turn to activate it." It's two Scout tactics in the *same* Encounter
Plan, for the *same* Search order, in the *same* turn, read as this
game's consent-to-pay signal for the three costed Powers named above
-- there's no code anywhere (engine or report generation) that frames
it as a later-turn reactivation ritual.

**Cast, the eighth tactic designed** (2026-10-28, sourced directly
from the user, rulebook text pasted verbatim): "Qualsiasi incantesimo
di combattimento può essere usato una sola volta in combattimento...
non tutti gli incantesimi possono essere usati in un piano
d'incontro" -- confirmed by direct investigation of ``turn/search_
execution.py``'s own ``_resolve_cast_tactic()``: exactly 17 of the 35
real spells are ever dispatched there (``ENCOUNTER_PLAN_CASTABLE_
SPELLS`` below) -- every other spell is an Action-Cast-only spell
(castable in one of the 5 regular phases, never in an Encounter Plan)
and falls through to a silent no-op there today. Offering every spell
in the sub-object field the way CAST's generic ``TACTICS_WITH_SUB_
OBJECT`` membership would otherwise invite -- a raw, unvalidated
integer -- would let the GM compose a spell that silently does
nothing; instead Cast gets its own dedicated ``tactic_spell_<leader>_
<n>_<slot>`` spell-name dropdown (``spell_options()`` below), and
``_parse_search_tactics()`` rejects any spell outside the allowed 17
server-side. The once-per-combat cap, the stacking defensive-hit-
reduction math, and the spell-dissolve-on-damage checks are all
already fully implemented and tested in the engine -- nothing new to
execute, only the allowed-spell list to compose against.

Gate Angel is the one spell on that list that needed new engine work,
not just composer wiring, **flagged here as project-original, not
sourced from any rulebook or Pascal text**: the user asked for it
alongside Gate Demon (2026-10-28) even after this project's own
investigation found Gate Angel's real, documented effect --
``AdvancedAbility.GATE_ANGEL_SPELL``'s own description -- is a
world-level "a Valhalla hero visits your Kingdom at the end of this
turn" lottery with zero combat content, unlike Gate Demon's own
description, which explicitly describes a fight. ``turn/search_
execution.py``'s own new ``Spell.GATE_ANGEL`` branch mirrors Gate
Demon's shape exactly (same ``Ability.WHITE``-ladder secret-spell
skill-5+ gate, matching this spell's own existing Action-Cast gate),
except the summoned combatant is whichever hero is currently visiting
Valhalla (the same "no hero currently visiting -> no effect"
convention ``Spell.ILLUS_HERO`` already uses) rather than a randomly
rolled demon species, since no "angel" entity exists anywhere in this
project's own bestiary, and there is no refusal roll, since Gate
Demon's own "a Demon may refuse an Evil-to-Undead opponent" mechanic
has no stated analog anywhere in Gate Angel's own rule text. See
``GATE_ANGEL_KNOWN_ABILITY_LEVEL``'s own docstring in ``turn/search_
execution.py`` for the full rationale.

**Use Item, the ninth tactic designed** (2026-10-28, sourced directly
from the user, rulebook text pasted verbatim): "Use Item requires the
item's own ordinal number... obviously only items that cast combat
spells usable in an Encounter Plan can be used in one... they succeed
automatically and have no limit (more than one can be cast in the
same combat plan)... if a character has two magic weapons, they can
specify which one to use" -- independently confirmed against ``turn/
search_execution.py``'s own ``_resolve_use_mi_tactic()``: ``sub_
object`` is a real item-instance id (``GameState.items``, the same
registry Give already reads), not a spell id, resolved through
``models/treasure.py TREASURE_WAND_SPELL`` to the one fixed spell that
item casts, then dispatched straight through ``_resolve_cast_tactic()``
with ``forced_level=SEARCH_USE_MI_WAND_SKILL_LEVEL`` -- automatic
success, no once-per-combat slot consumed, and no round consumed
(a plain ``continue`` in the tactic walk, same as Say/Cast) are all
*already* fully implemented and tested; nothing new to execute, only
to compose safely. Only 6 of the 20 real wand treasures map to one of
``ENCOUNTER_PLAN_CASTABLE_SPELLS`` (Golden Cross/Holy Symbol, Glove of
Death/Hand of Death, Wand of Fire/Fireball, Cologne of Charming/Charm,
Antennae of Psychic Blasting/Psychic Blast, Ring of Invisibility/
Invisibility) -- every other wand, and every non-wand item (Skill
Books have no Encounter-Plan role at all), is a documented engine-side
no-effect if named here, the same "offering it would mislead the GM"
reasoning Give/Beg were excluded for. Use Item therefore gets its own
dedicated ``tactic_item_<leader>_<n>_<slot>`` dropdown (``item_
options()`` below) listing only *this leader's own, currently-owned,
still-charged* wands whose spell is one of the 17 -- not a global item
catalog, since ``sub_object`` names a specific item instance this
leader must actually hold, and ``_parse_search_tactics()`` rejects a
direct, tampered POST naming an item this leader doesn't own, that
isn't a matching wand, or that's already out of charges. Unlike every
other tactic designed so far, this one needed ``state`` threaded all
the way through ``parse_phase_inputs()``/``_parse_search_tactics()``
to do that ownership/category/charge lookup -- every earlier tactic's
own validation was state-independent.

**Shoot, the tenth tactic designed** (2026-10-28, sourced directly
from the user, rulebook text pasted verbatim, who also flagged that
``Maneuver.SHOOT``'s own Python name is really rulebook [5.2]'s "Fire
Arrow [FI]" -- the dropdown now says "Fire Arrow", not the enum's own
internal "Shoot"): "La probabilità base di colpire è del 30% più 10%
per livello e il danno è 1-6 punti danno... alcuni mostri hanno punti
nel talento FIRE AN ARROW (FI) e fanno danni differenti" --
independently confirmed against ``turn/encounter.py``'s own
``fire_arrow_hit_chance()``/``fire_arrow_free_attacks()``/
``FIRE_ARROW_DAMAGE_RANGE``: unlike Steal/Flee, Fire Arrow's real
formula matches its rulebook paraphrase *exactly* (30%+10%/level,
1-6 damage, free attacks = Archery skill level, one-for-one). The
"both sides roughly double their free attacks, but randomness means
the better archer might get zero shots" behavior is a confirmed
*emergent* property of ``resolve_fire_arrow_duel()``'s own per-round,
both-sides-fire simultaneously loop, not a separate doubling formula
-- nothing to compose differently. Carries no sub-object, no position
restriction, and -- like Flee/Scout/Fulfill -- no rulebook mechanic
anywhere in it depends on player input beyond placing the tactic in a
slot. The one real rule enforced here: Fire Arrow can appear **at most
once** per Encounter Plan -- a rule this project's own code already
confirms directly from the user ("Si può dare un solo ordine di FI
durante un piano speciale di incontro", ``turn/search_execution.py``'s
own module docstring) but, like Flee's own cap before this round,
left completely unenforced in both the engine's tactic walk and this
composer -- fixed the same way, mirroring Flee's exact shape.

**2026-11-04 -- the ``_close_to()`` discrepancy this paragraph used to
flag is fixed.** It used to be a zero-cost, instant move bundled into
the same tactic-resolution step that then immediately fired, contrary
to the rulebook's own "closing to archery/melee range consumes a
round, then attacks the following round" text ([5.2]/[5.3]). Now
``_close_to()`` genuinely advances one tier per round, and both the
SHOOT and MELEE branches in ``turn/challenge_execution.py`` spend a
real round closing (no attack from the one closing that round) before
the real Fire Arrow duel/Melee round begins -- see that module's own
current docstrings on the SHOOT/MELEE branches for the full mechanics
and the confirmed "the other side still acts normally meanwhile" rule.
Still lives entirely in Challenge's own encounter resolution, which
has no composer of its own (same situation as Give/Beg's Challenge/
Pursue carve-outs above) -- nothing to compose differently here either
way.

**Melee, the eleventh and last Encounter Plan tactic designed** --
needed an engine fix, not a composer change (2026-10-28, sourced
directly from the user, rulebook text pasted verbatim): "Un personaggio
ha una probabilità di base di colpire del 50% e infligge 1-6 punti
danno per colpo più 1 per differenza nel Talento Melee tra chi attacca
e chi difende" -- independently investigated against ``turn/
encounter.py``'s own ``roll_melee_attack()``/``MELEE_HIT_CHANCE``/
``MELEE_DAMAGE_RANGE``: the 50% hit chance and 1-6 damage die matched
exactly, but this project's own prior sourced reading of [5.3]
(quoted verbatim in that module's own docstring) explicitly had *no*
skill-difference term on damage at all -- flagged to the user, who
confirmed the term is real and asked for it to be added. ``turn/
encounter.py``'s ``roll_melee_attack()`` now takes a
``skill_difference_bonus`` parameter (every real Melee-tactic caller
in ``turn/encounter.py``/``turn/search_execution.py``/``turn/
challenge_execution.py`` passes ``max(0, effective_melee_skill(
attacker) - effective_melee_skill(defender))`` -- floored at 0 per the
user's own confirmation, so a less-skilled attacker never deals less
than the base die roll, only ever a bonus when more skilled). Hand of
Death's own bonus swing and Mirror-Image/Illusory-Hero's own disbelief
duels, which happen to reuse the same flat melee-attack roll as a
building block for their own, separately-sourced spell mechanics,
were deliberately left untouched -- this change is scoped to the
actual [5.3] Melee tactic's own resolution, not every incidental
consumer of the same low-level roll function.

Like Flee/Scout/Shoot, nothing in Melee's own rulebook text depends
on player input beyond placing the tactic in a slot -- no sub-object,
no position restriction, and (confirmed directly from the engine's own
``is_last_leader_tactic``/``skip_temper_setup`` plumbing) no
"at most once" cap either, unlike Flee/Shoot: the engine is explicitly
written to support more than one explicit Melee tactic in the same
plan (e.g. ``[MELEE, SCOUT, MELEE]``), each one fighting exactly one
round unless it's genuinely the plan's own last tactic. So
``tactic_options()``/``_parse_search_tactics()`` needed no new code at
all for Melee, the same "zero validation needed" shape Scout's own
round already found.

A Search phase composed here always gets the immediately-terminated
empty tactic list ``[0, -1]`` ("tl=0, no tactics") when every slot is
left empty, matching the previous round's own placeholder default.

**Recruit Army(s) [RE], the first non-Search-tactic Action designed**
(2026-10-29, sourced directly from the user, rulebook [3.4] text pasted
verbatim): "si deve specificare il tipo di unità militare e il
personaggio che la comanderà... Le unità militari possono essere poste
sotto il comando del personaggio che esegue l'ordine di reclutamento,
oppure sotto quello di un qualsiasi personaggio presente nella
provincia (anche se appartenente a un Reame alleato), oppure essere
assegnate al Comando di Guarnigione... se non è possibile reclutare un
certo tipo di unità militare perché non previsto per la popolazione
nativa, si può comunque effettuare l'arruolamento se il comandante, o
il personaggio a favore del quale viene dato l'ordine, ha già ai suoi
ordini un'altra unità del tipo" -- independently confirmed against
``turn/recruit_decode.py decode_recruit_phase()``: ``obj`` is the
target commander's own leader id, or ``NO_LEADER_SENTINEL`` (255) for
the Garrison; ``extra`` is ``[0, <army-type ordinal>, ...,-1]`` (the
leading ``0`` unconfirmed but always present in every real sample,
exactly the same shape Search's own ``tl`` slot already uses). The
ownership precondition the last rulebook sentence above describes was a
genuine engine gap, not merely a composer one -- flagged to the user,
who confirmed it should be enforced and chose the "rich" composer
(showing native/non-native cost, mercenary presence, and per-type
turn limits already reached, right in the dropdown) over a bare integer
field; both are now built: ``turn/recruit.py resolve_recruit()`` gains
``commander_already_has_type``/``NonNativeTypeNotYetOwnedError`` (see
that module's own 2026-10-28 docstring addendum), and this module gets
a dedicated commander-target dropdown (``recruit_target_options()``)
plus a repeated, per-slot army-type dropdown
(``recruit_type_options()``, ``RECRUIT_TYPE_SLOT_COUNT`` slots, the
same no-gaps convention Search's own tactic slots already use) instead
of the generic Object/Extra integers.

A few things this round's own composer deliberately does *not* do,
each a documented, scoped-down choice rather than an oversight: (1) the
type dropdown's own cost/limit/mercenary preview is informational only
-- the real arbiter is still ``execute_recruit()`` at turn-processing
time (same "composer informs, engine enforces" split every richer
dropdown here already follows, e.g. Fulfill's own pending-quest flag);
(2) the per-type turn-limit shown is the plain ``recruit_limit()``
base value, not inflated by a King's home-province bonus or a
Wingman/Marshal/Admiral Office-holder's own extra slot -- those are
real, but correctly replicating them here would need re-deriving
Office-holder state this module has no other reason to carry, so the
preview is a conservative lower bound, never an overstatement that
would mislead the GM into under-recruiting; (3) the 8 real ``ArmyType``
ordinals with no ``ARMY_TABLE`` cost entry (Vampires, Marauders,
Shamans, Crossbow, Javelins, Artillery, Spiders, D_Turtle -- ``turn/
recruit.py``'s own docstring) are never offered at all, since
``resolve_recruit()`` always rejects them outright, with no cost to
preview in the first place; (4) Dinosaurs are still offered (Elven
provinces only, matching ``is_army_type_compatible_with_race()``), but
labelled with their own real preconditions (Druid ability, province
slot) rather than the generic non-native-ownership one, since
``turn/recruit_execution.py`` exempts them from that check entirely
(see that module's own 2026-10-28 docstring addendum for why layering
the new check on top would have made a first Dinosaur unit permanently
unrecruitable).

**Disband/Fire Army(s) [DI], the second non-Search-tactic Action
designed** (2026-10-29, sourced directly from the user, rulebook [3.6]
text pasted verbatim): "L'unità militare viene così sciolta e i suoi
soldati si trasformano in mercenari. Un Re può sciogliere qualsiasi
unità militare in qualunque momento. Un personaggio può sciogliere una
unità militare solo se si trova nella stessa provincia... Per
sciogliere tutte le unità militari che il personaggio comanda,
scrivere: '[DI]sband [All]'... Se il comando lo fa il RE può sciogliere
qualsiasi unità militare del regno anche quelle al garrison commander
di una provincia del regno o comandate da un altro eroe (sempre di
quel regno)" -- independently confirmed against ``turn/army_list_
decode.py decode_army_list_phase()`` (shared with Leave/Pick_Up) and
``turn/plan_dispatch.py _dispatch_disband()``: ``obj`` is always ``0``
and unconfirmed/unread (forced to ``0`` here, the same "Explore needs
no real obj" shape); ``extra`` is ``[0, <army id>, ..., -1]``, or
``[0, 255, -1]`` for "DI ALL" (``ArmyType``'s own ``NO_LEADER_
SENTINEL``/255-reuse, ``ALL_ARMIES_SENTINEL`` in that module) --
"every army this leader personally commands" (``GameState.armies_
commanded_by()``), confirmed distinct from "every army of the whole
Kingdom."

This investigation found two real engine bugs, not just a composer
gap -- fixed in ``turn/plan_dispatch.py`` (see ``_dispatch_disband()``'s
own 2026-10-29 docstring addendum for the full citations), both
confirmed with the user before fixing: (1) a disbanded army never got
``ArmyState.is_mercenary = True``, so it could never actually be
followed by a passing general (``turn/move_execution.py resolve_
wandering_mercenary_following()``, the exact mechanic this rulebook
paragraph's own "I mercenari possono seguire un generale" addendum
describes) or re-hired via Recruit -- the "turn mercenary" half of
Disband was silently inert; (2) neither a King's own co-location bypass
nor an ordinary Hero's co-location check verified the targeted army
actually belongs to the acting leader's own Kingdom, so either could
previously target *any* army anywhere in the game, including another
Kingdom's -- now both require ``army.kingdom_id == acting_leader.
kingdom_id``, and only co-location is ever bypassed for a King.

The composer gets a dedicated, repeated army-target dropdown
(``disband_target_options()``, ``DISBAND_SLOT_COUNT`` slots, the same
no-gaps convention Search/Recruit's own slots already use) instead of
raw Object/Extra integers -- pre-filtered to exactly what this leader
could actually disband post-fix (every army of this leader's own
Kingdom; a King's own list spans every province of the Kingdom, a
Hero's is narrowed further to the leader's own current location), so
there's no way to compose an order the engine would just silently skip
anyway. Slot 0 alone also offers a dedicated "Disband ALL I command"
pseudo-option (``DISBAND_ALL_VALUE``) -- mirroring Talk's own "only
slot 0" shape -- which, when chosen, must be the *only* thing filled in
(rejected otherwise, since a real order is either a specific list or
the lone ``255`` sentinel, never both at once).

**Leave Army(s) [LE], the third non-Search-tactic Action designed**
(2026-10-29, sourced directly from the user, rulebook [3.8] text pasted
verbatim): "L'unità militare specificata rimane nella provincia o ad un
altro generale. Un'unità lasciata a un generale o ad una provincia di
un altro Reame diventa di proprietà di quest'ultimo... LE #numero unità
(anche più di una) to #numero eroe o GC (garrison commander) oppure LE
ALL to #numero eroe o GC" -- shares ``turn/army_list_decode.py decode_
army_list_phase()`` with Disband/Pick_Up: ``extra[0]`` is the target
leader id (``NO_LEADER_SENTINEL`` for "GC"), the rest is a ``-1``-
terminated army-id list, or the lone ``255`` for "LE ALL."

This investigation found the same class of real engine gaps Disband's
own round found, fixed in ``turn/plan_dispatch.py`` ``_dispatch_leave()``
(see that function's own 2026-10-29 docstring addendum for the full
citations), all confirmed with the user before fixing: (1) a specific
army-id list previously reassigned command of *any* army in the game,
with no check that the acting leader actually commands it, is
co-located with it, or that it belongs to his own Kingdom -- fixed,
while deliberately preserving the rulebook's own "novità" (passing a
Garrison-commanded army along to another Hero, not just one's own
commanded armies); (2) leaving to a named Hero of a hostile/unrelated
Kingdom previously succeeded silently -- now requires ``GameState.
is_allied()`` and blocks the whole order otherwise ("anche di un altro
Reame, basta che sia alleato"); (3) "un generale... di un altro Reame
diventa di proprietà di quest'ultimo" is a second, independent
Kingdom-transfer trigger from the pre-existing province-ownership one,
now also implemented.

**2026-11-03 -- the engine mechanic this paragraph used to flag as
entirely unimplemented now exists.** When an order targets another
leader of the same or an allied Kingdom, the higher-
``character_initiative()`` leader's own same-phase action waits for the
lower-Initiative leader's targeting order to resolve first, even out of
ordinary Initiative order -- not just for Leave, but for Recruit's own
commander target, a character-targeted Cast, and Give alike. See
``turn/turn_processor.py _order_phase_entries_by_initiative()``'s own
docstring for the full mechanism; `_dispatch_leave()`'s own docstring
has the original citation this paragraph was sourced from.

The composer gets a dedicated, repeated army-target dropdown
(``leave_army_target_options()``, ``LEAVE_SLOT_COUNT`` slots, reusing
``_disband_army_label()`` for each option's own label -- the same
display shape already works for both) pre-filtered to exactly what
this leader could actually Leave post-fix, plus an "ALL"
pseudo-option in slot 0 (``LEAVE_ALL_VALUE``, the same mutually-
exclusive-with-a-specific-list shape ``DISBAND_ALL_VALUE`` already
uses), and a dedicated target dropdown (``leave_target_options()``) --
every co-located leader of this leader's own or an allied Kingdom,
plus "Garrison Commander" -- instead of raw Object/Extra integers, so
there's no way to compose an order the engine would just silently skip
or reject anyway.

**Pick Up Army(s) [PI], the fourth non-Search-tactic Action designed**
(2026-10-29, sourced directly from the user, rulebook [3.9] text
pasted verbatim): "Questo comando serve ad associare un personaggio a
una o più unità militari... Si può prendere un'unità militare
comandata da un personaggio che si trova nella stessa provincia...
Non è invece possibile usare questo ordine nello stesso turno in cui
un'unità militare viene reclutata... ad eccezione delle unità
mercenarie... Un personaggio non può utilizzare questo comando a
favore di un altro personaggio" -- shares ``turn/army_list_decode.py
decode_army_list_phase()`` with Leave/Disband, but ``_dispatch_pick_
up()`` never reads ``request.target_leader_id`` at all -- confirmed
structurally that Pick Up can never act on another character's
behalf, matching that last sentence exactly (Leave is the order for
that, per the rulebook's own text). ``obj`` and ``extra[0]`` are both
unconfirmed/unread (forced to ``0`` here, the same convention
Disband's own ``extra[0]`` already uses); the rest of ``extra`` is a
``-1``-terminated army-id list, or the lone ``255`` for "PI ALL."

Two bug fixes, sourced directly from the user, fixed in ``turn/plan_
dispatch.py _dispatch_pick_up()`` (see that function's own 2026-10-29
docstring addendum for the full citations): (1) a specific army-id
list previously had no Kingdom-boundary check at all (only
``all_armies`` restricted to unled armies, and even that had no
Kingdom check) -- investigated with the user whether a specific list
should also require the target to be unled, mirroring ``all_armies``;
their own call, unlike Leave/Disband: no, a specific Pick Up may still
take over an army actively commanded by *anyone* co-located (
reorganizing one's own forces), but now only within the acting
leader's own Kingdom, never a different one; (2) "non è possibile
usare questo ordine nello stesso turno in cui un'unità militare viene
reclutata" had no supporting engine state at all -- ``models/game_
state.py ArmyState`` gains ``recruited_this_turn`` (set only by a
fresh levy, never a mercenary hire, reset every turn), closing a real,
confirmed same-turn exploit (a move file listing Recruit then Pick Up
of the newly, predictably assigned id in a later phase of the same
turn previously succeeded).

The composer gets a dedicated, repeated army-target dropdown
(``pick_up_army_target_options()``, ``PICK_UP_SLOT_COUNT`` slots,
reusing ``_disband_army_label()``) pre-filtered to exactly what this
leader could actually Pick Up post-fix, plus an "ALL"
pseudo-option in slot 0 (``PICK_UP_ALL_VALUE``, the same
mutually-exclusive-with-a-specific-list shape ``DISBAND_ALL_VALUE``/
``LEAVE_ALL_VALUE`` already use) -- no separate target dropdown, since
Pick Up always and only acts for the ordering leader himself.

**Give [GI] (the engine's own ``ActionCode.TRADE``), the fifth
non-Search-tactic Action designed** (2026-10-29) -- a naming mismatch
the user themselves caught and asked about first: there is no rulebook
"Trade (TR)" at all; "TR" is actually Trail [3.17] (follow-and-spy, not
designed yet), and this project's internal ``ActionCode.TRADE`` (ordinal
14) is really the rulebook's own Give order [3.18] -- confirmed
directly in the Pascal source's own two-letter abbreviation table
(``actab[Trade] = 'GI'``, see ``turn/trade_decode.py``'s own docstring
for the full citation; there is no separate ``Give`` member in the
Pascal ``action`` enum at all). Everything about this Action was
already fully implemented and tested end-to-end across several
earlier phases (132/133/140/214/397/547/667/713, see ``turn/trade_
decode.py``/``turn/trade_execution.py``'s own docstrings for the full
history) before this round -- no engine bug found or fixed in *this*
round, only a composer UI built against already-correct, already-
sourced behavior. ``obj`` is overloaded: an item id the giver actually
owns (checked first, takes priority -- "si passa l'oggetto e non
l'oro"), or else a gold amount (giver must be a King, recipient must
belong to a genuinely different Kingdom, King or Hero either way,
capped at 10% of the giver's treasury with a real 10-gold floor -- see
below); ``extra`` is ``[0, recipient_leader_id]`` -- no ``-1``
terminator, confirmed from this project's own real-shaped test
fixtures (``tests/test_trade_decode.py``), unlike every List-shaped
action designed so far.

**2026-10-29 addendum -- the user's own fuller Italian rulebook text
for [3.18] found two real engine bugs in a follow-up round**, both
independently confirmed in RULES.AK/ADDEND.AK and fixed in ``turn/
trade_execution.py`` (see that module's own 2026-10-29 docstring
addendum for the full citations): the 10% gold cap gained a real
minimum floor of 10 gold (``GOLD_GIVE_MINIMUM_FLOOR``, never above
what the giver actually has), and the gold recipient check was
loosened from "must be a King" to "must belong to a genuinely
different Kingdom" (a Hero recipient is equally valid -- the earlier
reading over-read a shorter English excerpt). This composer's own
``_parse_trade_gift()`` now also enforces that same different-Kingdom
requirement for a gold gift specifically (the item path has no such
restriction), matching the engine rather than only discovering the
mismatch at turn-processing time. Still deliberately NOT touched: the
10% cap uses the giver's live treasury rather than a "treasury at the
start of the gameturn" snapshot (no such snapshot exists anywhere in
``GameState`` today) -- see ``turn/trade_execution.py``'s own docstring
for why that one isn't a quick fix. The real conditional/barter Give
("the gift is made only if the recipient Gives back a specified item
in the same phase") turned out to need no composer or execution-layer
support at all (2026-11-04, see that same module's own current
docstring): per the user's own explicit choice, a one-sided cross-
Kingdom Give always completes regardless of reciprocation, so a
"conditional" Give and an ordinary one are behaviorally identical --
nothing to compose differently here either way.

The composer gets a dedicated recipient dropdown (``trade_recipient_
options()``) and a dedicated gift dropdown (``trade_gift_options()``,
toggling a free-text gold-amount field, the same reveal-on-selection
shape Say's own free-text field already uses) instead of raw Object/
Extra integers. The recipient dropdown offers every co-located leader
(any Kingdom -- the item path explicitly crosses Kingdoms freely,
unlike Leave, so there's no alliance filter here; the gold path's own
different-Kingdom requirement is instead enforced at parse time, once
both the recipient and the gift are known), plus two further, real,
already-implemented cases worth surfacing rather than leaving the GM
to discover by trial and error: "Self," shown only when the acting
leader currently holds ``Office.CURATOR`` (rerouting to ``execute_
curator_research()`` -- "the Guild will research any item number in
the world"), and the blackmailer's own King, shown even when NOT
co-located, when the acting leader's own Kingdom carries an active
``KingdomState.active_blackmail`` claim (``AdvancedAbility.SPY_
BLACKMAIL``'s own documented co-location waiver for paying it off).
The gift dropdown lists this leader's own currently-owned items
(excluding a Valhalla visitor's own fixed item, which can never be
given away) plus a "Gold" option. Deliberately NOT exposed here:
``turn/trade_decode.py``'s own
Phase 397 Trade->Cast rewrite for the 10 secret spells (a self-targeted
Give naming one of their ordinals as ``obj`` silently becomes a Cast
instead) -- this composer always encodes ``extra[0]`` as ``0``, so that
rewrite's own trigger condition (``extra[0] == leader_id``) can never
fire through it; a GM who wants to Cast a secret spell has the actual
Cast composer for that, and this one should only ever produce a real
Give order.

**Practice [PR] (``ActionCode.PRACTICE``), the sixth Action designed**
(2026-10-29) -- confirmed against the user's own fuller Italian [3.13]
text and ``turn/practice_decode.py``/``turn/practice_execution.py``'s
own docstrings. Decode-wise this is this project's simplest Action:
``obj`` is just the ``Ability`` ordinal being practiced (0-14, this
project's own ``Ability`` enum -- no new mapping needed), and ``extra``
carries no real meaning at all (confirmed from real data: every one of
189 real Practice phases across the sample ``.K1`` files has
``extra == [0]``, see that module's own docstring). So the composer
needs only one dropdown -- ``practice_ability_options()``, every
``Ability`` member by its own ``ABILITY_NAME`` display string -- and
one parse function, ``_parse_practice_ability()``; ``extra`` is always
encoded as ``[0]``. This round's own fuller-rulebook-text check did
find one real engine gap -- a Practice skill/aptitude rise used to be
written into ``LeaderState.skills`` the instant it resolved, visible to
anything reading that same leader's skill level later in the *same*
phase, contradicting [3.13]'s own "L'avanzamento avrà effetto fin dalla
fase successiva" (takes effect starting the next phase, not this one).
Fixed directly in ``turn/practice_execution.py``/``turn/turn_processor.
py`` per the user's own explicit choice to fix it now rather than defer
it (see ``LeaderState.pending_skill_advancement``'s own docstring for
the full citation and mechanism) -- nothing about that fix touches this
composer, since the GM still just picks which Ability to practice.

**Trail [TR] (``ActionCode.TRAIL``), the seventh Action designed**
(2026-10-30) -- confirmed against the user's own full Italian [3.17]
text and ``turn/trail_decode.py``/``turn/trail_execution.py``'s own
docstrings. One of the most faithfully implemented Actions reviewed so
far: every element of the pasted rulebook paragraph (the target's own
Actions, race, Temperament, Alignment, treasures, armies commanded, plus
a King target's own treasury/alliances/controlled-provinces; the
trailer-leads-an-army rejection; "ends once reached and spied on for one
phase, needs re-issuing to continue"; no Encounter Plan, unlike Pursue)
has a direct, cited code path -- the one confirmed gap is the
rulebook's own "nemici" (enemies): ``turn/trail_execution.py``'s own
``KingIntelligence`` carries no enemies field at all, because this
project has no positive war/hostility registry anywhere (only a
friendly-pairs ``allied_kingdoms`` one) and deliberately refuses to
infer "not allied == enemy." Left deferred per the user's own explicit
choice -- not fixed in this round. ``obj`` is simply the target's own
real ``leader_id`` (confirmed from the Pascal source itself,
``RUMORS.PAS Set_Intel`` comparing this field directly against other
character ids -- *not* a roster-position ordinal, despite the Italian
syntax's own "numero d'ordine" phrasing); ``extra`` carries no decoded
meaning (``TrailRequest.unconfirmed_extra0``, always ``0`` in the one
real-ish sample). So the composer needs only one dropdown --
``trail_target_options()``, every *other* leader in the game, any
Kingdom, independent Heroes included (unlike Give/Leave, Trail needs no
co-location at all between trailer and target -- ``execute_trail()``
computes a distance-based catch-up chance instead) -- and one parse
function, ``_parse_trail_target()``; ``extra`` is always encoded as
``[0]``. ``_parse_trail_target()`` also enforces, at compose time rather
than only at turn-processing time, the one real restriction the
rulebook names: a leader who already commands an army can't be given a
Trail order at all (``GameState.armies_commanded_by()``, the same check
``execute_trail()`` itself makes).

**Challenge [EN] (``ActionCode.CHALLENGE``, real two-letter code
"Encounter Character"), the eighth Action designed** (2026-10-31) --
confirmed against the user's own full Italian [3.12] text and
``turn/challenge_execution.py``/``turn/challenge_pursue_decode.py``'s
own docstrings. No engine bug found this round -- every clause of the
pasted text has a direct, cited code path: same-province co-location
required at execution time (``execute_challenge()``'s own ``co_located``
check); an armyless Hero can't avoid another Hero's Challenge but
refuses a King's own 50%-ish; an army-leading Hero never accepts; a
King only accepts a non-peaceful encounter when both sides target each
other the same phase ("mutual encounter," detected entirely by ``turn/
turn_processor.py``'s own same-phase cross-leader pairing -- nothing
for this composer to expose, since issuing a Challenge back at the
same target in the same phase from the other side is itself already a
second, ordinary composed Challenge order); these restrictions are
waived entirely by a peaceful plan (no combat tactic/spell, Charm
included); a restricted encounter halves a Steal tactic's own success
chance. One real refinement beyond the pasted prose, not a bug: the
King's own "50%" isn't a coin flip at all once an explicit Melee
tactic drives the plan's own intent -- it's the disassembly-sourced
deterministic parity formula (turn/aptitude/turn-number based,
confirmed Phase 793), already correctly implemented; only a non-Melee-
driven combat plan (Cast- or Steal-only) falls back to a real 50/50
roll. ``obj`` is the target's own real ``leader_id`` (same convention
as every other targeted Action so far); ``extra`` is ``[0, ...]``
followed by the exact same ``-1``-terminated Encounter Plan tactic list
Search already uses (``turn/challenge_pursue_decode.py`` delegates
straight to ``turn/search_decode.py decode_tactic_tokens()`` -- no
Challenge-specific decode shape exists at all). So the composer gets a
target dropdown (``challenge_target_options()``, pre-filtered to
currently co-located leaders, same convention as ``trade_recipient_
options()``/``leave_target_options()``) plus the **exact same**
Encounter Plan tactic-slot editor Search's own composer already built
(``tactic_options()``/``_parse_search_tactics()``, now both carrying a
new ``allow_give``/``field_prefix`` parameter respectively) -- the one
real difference being that ``Maneuver.GIVE`` is a real tactic here
(rulebook [3.12]/[3.16]: valid only after Challenge/Pursue, never
Search -- confirmed by ``_parse_search_tactics()``'s own pre-existing
Give-rejection message, which already named Challenge/Pursue as Give's
real home before this round ever touched it) while ``Maneuver.BEG``
stays excluded everywhere, Challenge included (never a real Encounter
Plan tactic at all, confirmed in ``turn/challenge_execution.py``'s own
docstring). ``field_prefix="challenge_tactic"`` keeps Challenge's own
tactic-slot form fields from colliding with Search's own identically-
shaped ``tactic_*`` fields when both cells exist in the same composed
phase row. ``Maneuver.GIVE``'s own sub-object, when used as a Challenge/
Pursue tactic, now gets its own dedicated, ownership-filtered item
dropdown too (``give_item_options()``, 2026-11-01 -- see this module's
own docstring's Give section for the full "multiple items via multiple
slots" rationale).

**Hire Hero [HI] (``ActionCode.HIRE``), the ninth Action designed**
(2026-10-31) -- confirmed against the user's own full Italian [3.5]
text and ``turn/hire_fire_decode.py``/``turn/hire_pay.py``/``turn/
plan_dispatch.py _dispatch_hire()``'s own docstrings. No engine bug
found this round -- co-location, the "free Hero" requirement, the
King-can-never-be-hired exclusion, paying the Hero's own asking price
(never the raw offer, even when the offer is higher), Talent-
independence, and the >2-Alignment-positions "generally can't" gate
(a hard refusal, with a genuine, separately-sourced 15% rare-exception
roll forcing the price down to the legal 4-gold ceiling) are all
implemented exactly as the rulebook describes. Two real wage-formula
refinements exist beyond the pasted prose, already correctly
implemented in earlier rounds of this project, not bugs: an Undead-
aligned Hero always costs a flat 1 gold, and a +1 "conquest surcharge"
applies when a non-Divine King hires a differently-aligned Hero born in
a province the King's own Kingdom now owns. ``obj`` is the target
Hero's own real ``leader_id``; ``extra`` is simply ``[gold_offer]`` (no
terminator, no further payload) -- the 1-4 range is a real rulebook
syntax rule with **zero hard engine gate** (confirmed: neither decode
nor execution ever checks it, only the resulting required-pay
comparison), so this composer is what actually enforces it.

The structurally unusual part is ``PlanPhase.nested_plan``: per [3.5]'s
own "può ricevere ordini a partire dalla fase successiva," a
*successful* Hire immediately embeds the newly-hired Hero's own
``ActionPlan`` for the rest of this same turn (confirmed real,
byte-for-byte, in ``AK3__T2.K1``'s own leader 18 -- a Hire at ``P1``
immediately followed by the hired Hero's own ``AP: 2 4`` segment). The
engine itself enforces none of "must start strictly after the
triggering phase" -- that's a real-data convention ``parser/k1_moves.py``
happily round-trips either way, confirmed by this project's own writer
tests -- so **this composer is what enforces it**: ``_parse_hire_
nested_plan()`` only ever offers/reads phase slots strictly after the
Hire phase's own label, up to ``P4``. Per the user's own explicit
choice, this round builds a basic nested-plan editor now rather than
deferring it: for a Hire composed at phase ``P<n>``, the GM additionally
gets one row per remaining phase ``P<n+1>..P4`` (none at all if ``n``
is ``P4`` itself, matching ``parser/k1_moves_writer.py``'s own "a nested
plan can never attach to P4" rule). **2026-11-02**: each row now gets
the exact same full per-Action special-cell composer every ordinary
P0-P4 phase gets, not just the plain generic Action/Object/Extra
fields (see this module's own docstring's Special Encounter Plan
section's sibling, the Nested Plan Richness paragraph further below,
and ``_parse_nested_plan()``'s own docstring). A row left with no Action chosen is simply
omitted from the nested plan (no "no gaps" requirement, since
``PlanSegment.phases`` is a sparse label->phase mapping, not a list);
leaving every row empty is equivalent to the Hero receiving no orders
at all this turn (idle, same as any leader with no composed order for
a given phase), and produces no ``nested_plan`` at all, matching a
failed Hire's own "nothing embedded" outcome. The composer never
exposes the Spy Double-Agent carve-out (hiring an already-employed Spy
without actually changing its real employer) -- ``hire_target_
options()`` only ever lists genuinely free Heroes, matching the
pasted rulebook text's own plain "Eroe libero" requirement.

**Fire Hero [FI] (``ActionCode.FIRE``), the tenth Action designed**
(2026-11-01) -- confirmed against the user's own full Italian [3.7]
text and ``turn/hire_fire_decode.py``/``turn/plan_dispatch.py
_dispatch_fire()``'s own docstrings. Much simpler to decode than Hire:
``obj`` is just the target Hero's own real ``leader_id``, and ``extra``
is always empty (confirmed: the real Pascal reader has no ``CASE``
branch for Fire at all, unlike every other action). This round's own
investigation found two real engine gaps beyond the pasted text,
**both fixed this round per the user's own explicit choice, found
after an initial too-hasty analogy to Disband was itself reconsidered
and the user asked again directly**: (1) ``_dispatch_fire()`` had no
"can't Fire a King" guard at all, asymmetric with Hire's own explicit
"can't Hire a King" check -- a King (or a co-located Hero) could set
another Kingdom's own ruling King's ``kingdom_id`` to ``None``, with
nothing elsewhere in this project modeling what a Kingdom with no King
even means; (2) an ordinary Fire had no Kingdom-ownership check on the
target at all -- a King's own co-location bypass (rulebook [3.7]: "may
Fire a Hero at any time") was, exactly like Disband's own earlier,
separately-fixed bug, letting that bypass also cross the Kingdom
boundary, so *any* Kingdom's King (or co-located Hero) could Fire *any*
other Kingdom's Hero. Both are now hard-gated in ``_dispatch_fire()``
itself (see that function's own 2026-11-01 docstring addendum for the
full reasoning, including why the Disband analogy needed a second,
more careful look before confirming it -- a Hero is an independent
character, not a Kingdom-owned asset like an army, so the fix was a
genuine judgment call, not a mechanical copy). The composer's own
``fire_target_options()`` reflects both fixes directly: it only ever
offers a Hero of the *acting leader's own* Kingdom, never a King (which
also correctly excludes a King "firing himself," never a meaningful
order), with co-location additionally required unless the acting
leader is a King. A Hero's own entry in that same list doubles as the
rulebook's own "can always Fire himself" case, labelled "Self (<name>)"
-- no separate self-fire sentinel value is needed, since Fire's wire
encoding is just the real target id either way. Deliberately NOT
surfaced here: the separately-sourced Grandfather of Assassins
reinterpretation of a cross-Kingdom FI order (``turn/assassin_guild.py``,
Phase 614) -- the same "don't surface the rare Advanced-Ability/Office
carve-out" choice already made for Trail's and Hire's own Spy Double-
Agent cases.

**Cast [CA] (``ActionCode.CAST``), the eleventh Action designed**
(2026-11-01) -- confirmed against the user's own full Italian [3.10]
text and ``turn/cast_decode.py``/``turn/cast_execution.py``'s own
docstrings. Not to be confused with the Encounter Plan's own
``Maneuver.CAST`` tactic (Search/Challenge/Pursue's own Personal-Combat
Cast, already composed via ``tactic_spell_*``/``challenge_tactic_
spell_*`` and ``ENCOUNTER_PLAN_CASTABLE_SPELLS``) -- this is the
top-level Action, one leader's own whole ``P<n>`` phase, for an Action
Spell (never a Personal-Combat spell). No engine bug found this round:
the "must have skill ≥1 in the spell's own Magical ability," "Action
Spell, never Personal-Combat," and "don't confuse with Use Item" rules
are all exactly as described. One real refinement beyond the pasted
"15% + 15% per level," already correctly implemented, not a bug: the
real formula stacks a 95% cap, a Pagan-Kingdom +10% (non-White schools),
a Pagan-King-title +10% (White only), a +20% "Places of Power" bonus,
and per-spell multipliers on top of that base term -- the same category
of refinement Practice's "10%/5%" and Challenge's "50%" turned out to
need. The rulebook text also doesn't mention the separate per-(leader,
Ability)-per-turn cast-count limit ([4.2]: 1 slot at skill 1-2, 2 at
skill 3, 3 at skill 4+) -- real, enforced, but out of this composer's
own scope to preview (the engine remains the real arbiter of how many
slots are left).

``CAST_ACTION_SPELLS`` is 19 spells, not the engine's own full 20 --
**Gate Angel is deliberately excluded**, the user's own explicit choice
(2026-11-01) made with full information: Gate Angel's only *sourced*
rulebook effect (the user's own earlier-supplied text) is the Valhalla-
visitor-lottery Action-Cast effect; its Personal-Combat use in an
Encounter Plan is the project's own, explicitly-flagged-unsourced
addition from an earlier round. The user chose to keep Gate Angel
exposed only through the Encounter Plan's own Cast tactic, not here,
despite that being the less-sourced of the two uses -- a deliberate,
informed choice, not an oversight, so don't "fix" this by adding it
back without asking again.

The remaining 19 spells split into 4 target shapes (``turn/cast_
decode.py``'s own frozensets), each composed differently: a generic
character-target dropdown (``cast_character_target_options()``, every
leader in the game, no further per-spell eligibility filtering this
round -- Kill Enemy/Oratory/Clairvoyance/Phantasmal Armies/Mystic
Winds); a province-target dropdown (reusing Move's own ``province_
options()``/``_parse_move_target()`` directly -- Part Sea/Bless/Plague/
Flood/Tornado/Earthquake/Illusory Terrain/Hide Feature/Scar Terrain/
Illusory Fog, the first of these additionally getting a ``Terrain``
dropdown for its own fake terrain); no field at all (Skeletal Army, the
one no-target spell left after excluding Gate Angel); and a plain
free-text item-id field, no dropdown at all (Locate Object -- 2026-11-
15, user-requested: an earlier dropdown listing every item in the game
by name/owner, regardless of this leader's own, defeated the spell's
whole point of finding an item whose location isn't already known --
showing it *was* the location). Resurrection and Charm each get their
own, deliberately more elaborate target handling instead of the
generic character-target dropdown.
Resurrection's own (``resurrection_target_options()``/``_parse_
resurrection_target()``) merges all three of ``_execute_resurrection()``'s
own eligibility branches (comatose cure, Royal Heir restoration,
ordinary dead-Hero revival from ``GameState.dead_leaders``) into one
dropdown, each labelled by which branch it resolves to. Charm's own
(``charm_target_options()``/``_parse_charm_target()``, 2026-11-01,
confirmed against the user's own full Italian text) lists every co-
located, army-less, non-King leader of *any* Kingdom -- including an
enemy's or another independent character's own, a deliberate, user-
confirmed choice: Charm's own free-hire branch, unlike Hire, has no
"must already be independent" requirement, so poaching a foreign Hero
outright is real, tested engine behavior, not an extension of this
composer's own scope. When the acting leader is themself an Undead King
(``LeaderState.alignment is Alignment.UNDEAD`` and ``is_king``), the
template surfaces a conditional note next to this same dropdown about
the "Seduzione" Undead-conversion side effect (``turn/cast_execution.py
_apply_undead_king_alignment_conversion()``) -- a caster-conditional
*effect* layered on the identical target pool, not a second dropdown,
since the eligibility set never differs based on it. One correction
to the pasted rulebook text worth flagging, already correctly
implemented and disassembly-sourced in an earlier round, not a bug:
"l'allineamento cambierà di 1-3 posizioni" is superseded by a real
deterministic step-budget formula (``12 // max(1, Total_USkill(target))``
ordinal steps per successful cast) -- harsher on a weak target (a
single cast can go all the way to Undead), far gentler on a skilled one
(always exactly one step, however high skill climbs).

Kill Enemy (rulebook [4.25.2]) also gets its own dedicated target
handling (``kill_enemy_target_options()``/``_parse_kill_enemy_target()``,
2026-11-01), confirmed against the user's own full Italian text: co-
located, never a King, never Undead-aligned (a real engine gap found
and fixed this round, see ``turn/cast_execution.py _execute_kill_
enemy()``'s own 2026-11-01 docstring addendum -- the target's own
alignment was never checked at all before), never the active Valhalla
visitor; no allegiance restriction whatsoever (a necromancer may
legally target a co-located ally or even their own Kingdom's Hero).
Unlike Charm, an army-leading Hero is a *legal* target here, only
annotated with a "halved chance" note rather than excluded -- leading
an army only halves ``_execute_kill_enemy()``'s own success roll
(alongside an independent halving for a Special-Place Feature in the
caster's own province), it never blocks the cast outright. A target
holding the True Cross/Anti-Necromancy Amulet, or whose Kingdom owns
Hidden Tattoos, is deliberately NOT excluded either -- both are post-
roll wards, not preconditions, so the cast can still be rolled for and
fail normally against them, same "never pre-filter a merely-likely-to-
fail target" convention every other dropdown on this page follows.

Charm and Resurrection (``CAST_NESTED_PLAN_SPELLS``) are the two spells
whose successful cast embeds a ``PlanPhase.nested_plan`` for the newly-
(re)joined character, the exact same mechanism Hire uses -- generalized
here into a shared ``_parse_nested_plan()`` (``field_prefix`` parameter:
``"hire_nested"`` for Hire, ``"cast_nested"`` for Cast), reusing the
same "only offer/read phases strictly after this one, up to P4" design
and the same plain generic Action/Object/Extra fallback fields for the
newly-(re)joined character's own orders. Every other spell's own
``ComposedPhaseInput`` always carries ``nested_plan=None`` -- confirmed
necessary, not just unneeded: ``turn/plan_dispatch.py
_resolve_nested_plan_leader_id()`` doesn't itself check which spell was
cast, so a ``nested_plan`` wrongly attached to, say, a Plague cast would
still be dispatched if that cast happened to succeed.

**Defend [DE] (``ActionCode.DEFEND``)** (2026-11-01) -- confirmed
against the user's own full Italian [3.15] text and ``turn/defend_
execution.py``/``turn/turn_processor.py``'s own docstrings. ``obj`` is
the named province (``_parse_defend_target()``, same ``province_
options()`` dropdown and ``"x,y"`` wire shape as Move's own -- see that
function's own docstring for the still-open, but today harmless,
numbering-scheme caveat); ``extra`` is always ``[0]`` (``turn/aspy_
defend_decode.py``'s own confirmed, never-populated ``extra0``). No
Encounter Plan or further sub-fields -- Defend's own reactive battle-
joining is a background mechanism in ``turn/turn_processor.py``
(``active_defends``), not something this one composed phase itself
carries any further payload for.

**Spy [SP] (``ActionCode.ASPY``)** (2026-11-02) -- confirmed against
the user's own full Italian [3.14] text and the "Tabella dello
Spionaggio"/"Tabella dello Spiare" ([4.33]): a background research
round found ``turn/aspy_execution.py``/``turn/spy_table.py`` already
more complete than the rulebook's own base text (province/adjacency/
tax/recruitable-unit/capital reporting, the margin-of-error table,
Discovery-stealing, Pursue/Trail's own shared use of the same table --
all already wired), so this round is composer-only, no engine changes.
``obj`` is always this leader's own *current* province, auto-derived
via ``encode_hex_number()`` (same scheme Move/Defend's own dropdowns
already use) -- never a player choice, matching the rulebook's own
syntax ("SP #(numero della provincia in cui si trova eroe o re)")
literally: a character can only Spy on the province he's already in.
``extra`` is always ``[0]`` (``turn/aspy_defend_decode.py``'s own
confirmed, never-populated ``extra0``, same convention as Defend's).

**Use Magic Item [UM] (``ActionCode.USE_MI``)** (2026-11-02) -- the
top-level Action [3.11], not to be confused with ``Maneuver.USE_MI``,
the *Encounter Plan tactic* of the same raw ordinal already composed
via ``item_options()``/``tactic_item_*`` (a different Pascal reading
path with no top-level ``ActionCode`` of its own -- see ``turn/use_mi_
decode.py``'s own docstring). ``obj`` is a global item-instance id
(``use_mi_item_<leader_id>_<n>``'s own dropdown, ``use_mi_item_
options()`` -- every owned, still-charged wand whose fixed spell is
Action-Cast-eligible, plus every owned skill book), never a Spell
ordinal -- the one structural way this Action's wire shape differs
from Cast's own. A chosen wand then reads whichever target sub-field
matches its own fixed spell's shape into ``extra`` (``_parse_use_mi_
phase()``, reusing every one of Cast's own per-shape helpers --
``use_mi_character_target_``/``use_mi_province_target_``/``use_mi_
terrain_<leader_id>_<n>``, plus Resurrection's/Charm's/Kill Enemy's own
dedicated, eligibility-checked dropdowns, all under their own
``field_prefix="use_mi"`` fields so a Cast phase and a Use_MI phase
sharing the same row's underlying fields never collide), with the same
nested-plan editor Hire/Cast use for a successful wand-cast Charm or
Resurrection. A chosen skill book needs no target field at all --
``extra`` is always ``[]``. Five of the 20 wand-mappable spells (Holy
Symbol, Hand of Death, Fireball, Psychic Blast, Invisibility -- one per
Magical ``Ability``) are Personal-Combat-only and have no Action-Cast
target shape at all, so a wand carrying one of those is never offered
here, only via the Encounter Plan's own Use Item tactic (``item_
options()``'s own, narrower ``ENCOUNTER_PLAN_CASTABLE_SPELLS`` filter)
-- the two dropdowns' own wand sets are mutually exclusive, confirmed
by direct enumeration, not assumed.

Every other not-yet-designed action still falls back to the plain
Object/Extra integers.

**Special Encounter Plan [5.10] (``PlanSegment.sp``)** (2026-11-02) --
every leader now gets his own standing-posture tactic-slot table
(``_parse_special_encounter_plan()``), shown once per leader rather
than once per phase: this is the plan a commander falls back to
whenever he's drawn into an Encounter he didn't himself order this
turn (an enemy's Challenge/Pursue finding him, or -- per ``turn/sep_
decode.py target_uses_special_encounter_plan()`` -- *any* Encounter at
all, friendly or wandering-monster, if he commands no army). Reuses
the exact same tactic-slot UI and ``_parse_search_tactics()`` call
every phase's own Encounter Plan already uses (``field_prefix=
"sep_tactic"``, ``allow_give=True`` -- confirmed a real, Pascal-sourced
SEP tactic, see that function's own docstring), minus the leading
``tl``/``extra0`` slot every phase's own ``extra`` carries (``turn/
sep_decode.py``'s own confirmed wire format: SP: is a pure tactic
list, nothing else). Leaving every slot empty still composes the real
``DEFAULT_SP`` (``(10, -1)``, decoding to a lone Flee tactic) -- not a
placeholder kept around for this round, but the one real value every
sample file already showed, now reachable by simply not touching the
new table at all, same "the UI's own idle state already matches the
engine's own real default" property every other dropdown on this page
already has.

**Nested Plan Richness** (2026-11-02) -- a newly-(re)joined character's
own orders (after Hire, a Charm/Resurrection Cast, or a wand-cast
Charm/Resurrection via Use Magic Item) now get the exact same full
per-Action special-cell composer every ordinary P0-P4 phase gets
(``_parse_nested_plan()``), not the plain generic Action/Object/Extra
fields the very first Hire round shipped. The one real wrinkle: which
hero triggers a given nesting is only known once the GM actually picks
one in this *same* form, so this round's leader-scoped dropdowns
(``feature_options()``, ``recruit_target_options()``, and every other
``*_options()`` function that isn't globally scoped) can't be
precomputed the way the real roster's own choices already are. Solved
with a new JSON endpoint, ``/games/<slug>/turns/<kingdom_id>/compose/
hero_options`` (``nested_hero_option_bundle()``), called client-side
the moment a real target is chosen in the triggering dropdown -- a
dead Resurrection candidate (not in ``state.leaders`` at all) is
temporarily, safely reinserted from its own ``dead_leaders`` snapshot
for that one call, then removed again. ``_parse_nested_plan()`` itself
reuses every one of ``parse_phase_inputs()``'s own ~20 existing,
already-tested helper functions completely unchanged -- a remapping
pass (``_remap_nested_fields()``) rewrites this phase's own
``<field_prefix>``-namespaced posted fields into the plain names those
helpers already expect, then calls ``parse_phase_inputs()`` recursively
against the hero's own id, rather than threading a ``field_prefix``
through each of them. Deliberately caps at one level of nesting -- a
Hire/Charm/Resurrection chosen *inside* this nested row gets its own
target dropdown but no further nested editor of its own (see that
function's own docstring for why this loses no real expressiveness:
turn phases are too scarce for a third level to ever have room to
compose anything in).

**Why this goes through a real ``Kingdom`` + ``parser/k1_moves_writer.py``
rather than writing straight to ``GameState``**: the exact same shape a
future player-facing "create your own moves" UI will need to produce
(per the user's own explicit request) -- building both producers around
the same ``Kingdom`` dataclass and the same writer is what guarantees
they stay in sync, rather than two independent guesses at "the same
format" drifting apart. The composed file is saved through the exact
same ``save_uploaded_move_file()`` path a real upload uses, so turn
processing can't tell the difference.
"""

from __future__ import annotations

from collections import ChainMap
from dataclasses import dataclass

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ARMY_TABLE, ARMY_TYPE_BY_ORDINAL, ARMY_TYPE_NAME, NO_LEADER_SENTINEL, ArmyType
from ak_engine.models.enums import ABILITY_NAME, SPELL_NAME, TACTICS_WITH_SUB_OBJECT, Ability, ActionCode, Maneuver, Spell
from ak_engine.models.feature import FEATURE_TYPE_NAMES
from ak_engine.models.game_state import ArmyState, GameState, LeaderState
from ak_engine.models.kingdom import Kingdom, KingdomMoveHeader
from ak_engine.models.leader import Leader
from ak_engine.models.map import TERRAIN_NAME, HexCoord, Terrain
from ak_engine.models.monster import MONSTER_NAMES
from ak_engine.models.office import Office
from ak_engine.models.plan import ActionPlan, PlanPhase, PlanSegment
from ak_engine.models.race import HUMANOID_RACES
from ak_engine.models.treasure import (
    TREASURE_BOOK_ABILITY,
    TREASURE_CATEGORY,
    TREASURE_NAME,
    TREASURE_WAND_SPELL,
    TreasureCategory,
)
from ak_engine.models.valhalla import VALHALLA_VISITOR_LEADER_ID
from ak_engine.report.turn_report import real_province_number
from ak_engine.turn.army_list_decode import ALL_ARMIES_SENTINEL
from ak_engine.turn.cast_decode import (
    CHARACTER_TARGET_SPELLS as _CAST_CHARACTER_TARGET_SPELLS_RAW,
    ITEM_TARGET_SPELLS as CAST_ITEM_TARGET_SPELLS,
    NESTED_PLAN_SPELLS as CAST_NESTED_PLAN_SPELLS,
    NO_TARGET_SPELLS as _CAST_NO_TARGET_SPELLS_RAW,
    PROVINCE_TARGET_SPELLS as CAST_PROVINCE_TARGET_SPELLS,
)
from ak_engine.turn.cast_execution import is_unfinalized_royal_heir
from ak_engine.turn.combat import QUALITY_NAME, Quality
from ak_engine.turn.discovery_effects import effective_skill_level
from ak_engine.turn.hex_numbering import encode_hex_number
from ak_engine.turn.leader_queries import find_king_of_kingdom
from ak_engine.turn.office_holder import resolve_office_holder
from ak_engine.turn.plan_dispatch import SUPPORTED_ACTIONS
from ak_engine.turn.recruit import is_army_type_compatible_with_race, recruit_limit, resolve_recruit

# Search's own "tl" slot (``turn/search_decode.py SearchRequest.
# unconfirmed_extra0``, always 0 in every real sample) followed by the
# Encounter Plan's own -1 terminator with no tactics in between --
# "nothing composed yet", the default when every tactic slot is empty.
EMPTY_SEARCH_EXTRA: list[int] = [0, -1]

# The longest real Encounter Plan tactic list across every AK3__T*.K1
# sample (``AK3__T10.K1`` leader 72's own 7-tactic CAST/CAST/CAST/CAST/
# CAST/MELEE/SCOUT plan) -- a generous, real-data-sourced slot count,
# not an arbitrary round number.
TACTIC_SLOT_COUNT = 7

# A Special Encounter Plan [5.10] is this leader's own *standing*
# posture, not tied to any one real phase's own tactic list the way
# TACTIC_SLOT_COUNT above (a real-sample-sourced max) is -- nothing in
# the available source bounds how long it could be, so the user's own
# request (2026-11-16) for an "add/remove as many as you like" UI here
# needs a real, generous ceiling the backend will actually read beyond
# the first TACTIC_SLOT_COUNT rows this table starts visible with.
# This is a UI allowance, not a sourced number -- round and generous,
# nothing more.
SEP_TACTIC_SLOT_COUNT = 25

# A generous, round slot count for a Recruit phase's own repeated
# army-type dropdowns -- the rulebook's own worked example (a King's
# home province: up to 2 units of each of up to 2 native types, plus 2
# Garrisons, plus every mercenary present) can list more than a
# handful of types in one real order, but there's no fixed real-sample
# maximum the way TACTIC_SLOT_COUNT has one; 8 comfortably covers that
# worked example with room to spare.
RECRUIT_TYPE_SLOT_COUNT = 8

# A generous slot count for a Disband phase's own repeated army-target
# dropdowns -- a King's Kingdom-wide roster could plausibly list more
# than a few armies to dissolve at once, but there's no fixed
# real-sample maximum here either (only one real DISBAND sample exists
# at all, a single army id -- ``turn/army_list_decode.py``'s own
# docstring).
DISBAND_SLOT_COUNT = 6

# Slot 0's own dedicated "Disband every army I personally command"
# pseudo-option (rulebook [3.6]: "[DI]sband [All]") -- the real wire
# value this collapses to is the lone ``ALL_ARMIES_SENTINEL`` (255),
# never combined with a specific army id list (``turn/army_list_
# decode.py decode_army_list_phase()`` only recognizes ``ids == [255]``
# as ALL, not a list containing 255 alongside other ids).
DISBAND_ALL_VALUE = "all"

# Same reasoning as DISBAND_SLOT_COUNT -- the only real LEAVE sample
# available lists a single army id (``turn/army_list_decode.py``'s own
# docstring), so this is a generous, round number, not a real-sample
# maximum.
LEAVE_SLOT_COUNT = 6

# Slot 0's own dedicated "Leave every army I personally command"
# pseudo-option (rulebook [3.8]: "LE ALL to ...") -- same mutually-
# exclusive-with-a-specific-list shape as ``DISBAND_ALL_VALUE``.
LEAVE_ALL_VALUE = "all"

# "LE ... to #numero eroe o GC" -- the dedicated "to" target dropdown's
# own Garrison Commander sentinel value, parsed back to the real
# ``NO_LEADER_SENTINEL`` encoding by ``_parse_leave_target()``.
LEAVE_GARRISON_VALUE = "garrison"

# Same reasoning as DISBAND_SLOT_COUNT/LEAVE_SLOT_COUNT -- no real
# PICK_UP sample exists at all (``turn/army_list_decode.py``'s own
# docstring), so this is a generous, round number.
PICK_UP_SLOT_COUNT = 6

# Slot 0's own dedicated "Pick Up every unled army here" pseudo-option
# (rulebook [3.9]: "[PI]ck Up [All]") -- same mutually-exclusive-with-
# a-specific-list shape as ``DISBAND_ALL_VALUE``/``LEAVE_ALL_VALUE``.
PICK_UP_ALL_VALUE = "all"

# Give [GI]'s own gift dropdown's dedicated "give gold instead of an
# item" pseudo-option -- reveals a free-text gold-amount field, the
# same shape Say's own free-text field already uses.
TRADE_GOLD_VALUE = "gold"

# Give [GI]'s own gift dropdown's second dedicated pseudo-option
# (2026-11-16, user-requested): "give an item by its own hand-typed
# order number instead" -- reveals a sibling free-text field, the same
# reveal-on-selection shape ``TRADE_GOLD_VALUE`` above already uses --
# for an item this leader owns but that ``trade_gift_options()``'s own
# start-of-turn snapshot doesn't yet list.
TRADE_ITEM_NUMBER_VALUE = "item_number"

# Every Maneuver a GM can compose here -- Maneuver.NONE is a sentinel,
# never a real tactic, so it's the only one excluded.
_COMPOSABLE_MANEUVERS: tuple[Maneuver, ...] = tuple(maneuver for maneuver in Maneuver if maneuver is not Maneuver.NONE)

# Rulebook [5.3]'s own stated limit ("entro un limite di 160 caratteri").
SAY_TEXT_MAX_LENGTH = 160

# The exact 18 spells `turn/search_execution.py _resolve_cast_tactic()`
# dispatches inside a Search Encounter Plan -- every other real Spell
# is an Action-Cast-only spell (one of the 5 regular phases, never a
# Encounter Plan) and silently no-ops there today. Confirmed directly
# against that function's own exhaustive `if/elif ... else: return
# None` branch (2026-10-28 investigation) -- Gate Angel is the one
# entry added alongside this round, see this module's own docstring
# for its full, explicitly-project-original sourcing. Kill Enemy
# (2026-10-31) is the newest addition: a brand-new Personal-Combat
# dispatch branch, user-requested rather than deferred alongside its
# own Action-Cast handling -- see this module's own Cast docstring
# section for the full history.
ENCOUNTER_PLAN_CASTABLE_SPELLS: frozenset[Spell] = frozenset(
    {
        Spell.HOLY_SYMBOL,
        Spell.SPIRITWRACK,
        Spell.HEAL,
        Spell.HAND_OF_DEATH,
        Spell.CONTROL_UNDEAD,
        Spell.CHARM,
        Spell.GATE_DEMON,
        Spell.GATE_ANGEL,
        Spell.FIREBALL,
        Spell.ICE_SUSPEND,
        Spell.LAVA_POOL,
        Spell.PSYCHIC_BLAST,
        Spell.TELEK_STORM,
        Spell.AUGUR_COMBAT,
        Spell.INVISIBILITY,
        Spell.MIRROR_IMAGE,
        Spell.ILLUS_HERO,
        Spell.KILL_ENEMY,
    }
)

# Top-level Cast (``ActionCode.CAST``)'s own 19 Action-Cast spells --
# ``turn/cast_decode.py``'s own 4 target-shape frozensets, minus
# ``Spell.GATE_ANGEL`` (2026-11-01, the user's own deliberate choice:
# its only *sourced* rulebook effect is the Valhalla-visitor lottery,
# modeled by ``turn/cast_execution.py``'s own Action-Cast branch, but
# the user chose to keep it exposed only as the Encounter Plan's own
# Personal-Combat tactic -- see this module's own docstring's Cast
# section for the full history), and minus ``Spell.RESURRECTION``/
# ``Spell.CHARM``/``Spell.KILL_ENEMY`` from the generic character-target
# set -- all three get their own dedicated, more elaborate target
# handling below (co-located/army-less/non-King for Charm, confirmed
# 2026-11-01; co-located/non-King/non-Undead, army-leading legal but
# halved, for Kill Enemy, confirmed 2026-11-01; Resurrection's own
# three-branch handling from an earlier round), not the generic "any
# leader in the game" dropdown every other character-target spell gets.
CAST_CHARACTER_TARGET_SPELLS: frozenset[Spell] = frozenset(
    _CAST_CHARACTER_TARGET_SPELLS_RAW - {Spell.RESURRECTION, Spell.CHARM, Spell.KILL_ENEMY}
)
CAST_NO_TARGET_SPELLS: frozenset[Spell] = frozenset(_CAST_NO_TARGET_SPELLS_RAW - {Spell.GATE_ANGEL})
CAST_ACTION_SPELLS: frozenset[Spell] = (
    frozenset({Spell.RESURRECTION, Spell.CHARM, Spell.KILL_ENEMY})
    | CAST_CHARACTER_TARGET_SPELLS
    | CAST_PROVINCE_TARGET_SPELLS
    | CAST_NO_TARGET_SPELLS
    | CAST_ITEM_TARGET_SPELLS
)

# Hide Feature (2026-11-16, user-requested): the real wire shape
# (``turn/cast_decode.py PROVINCE_TARGET_SPELLS``, confirmed against
# every real sample) still only ever carries a province coordinate --
# that part is unchanged, and still what ``_parse_hide_feature_target()``
# below ultimately encodes into ``obj``. But composing it by picking a
# *province* let a GM target one with no feature in it at all (an
# always-dead order, silently rejected only once the turn actually
# runs), when what the GM really has in mind is a specific feature's
# own "#<N>" -- the same number a PROVINCES report's own "Features and
# F#" column already gives for Search. This UI-only split (``CAST_
# PROVINCE_TARGET_UI_SPELLS``/``CAST_FEATURE_TARGET_SPELLS``, used only
# for this module's own dropdown/cell wiring) lets Hide Feature keep
# its own dedicated feature dropdown while ``CAST_PROVINCE_TARGET_
# SPELLS`` above -- the real backend shape classification, feeding
# ``CAST_ACTION_SPELLS`` -- stays completely untouched.
CAST_PROVINCE_TARGET_UI_SPELLS: frozenset[Spell] = CAST_PROVINCE_TARGET_SPELLS - {Spell.HIDE_FEATURE}
CAST_FEATURE_TARGET_SPELLS: frozenset[Spell] = frozenset({Spell.HIDE_FEATURE})

# Bug fix (2026-11-14, user-requested): 6 of the 10 undocumented
# "secret" spells (``Spell`` class's own docstring, ordinals 25-34,
# ``ADDEND.AK`` [2.0]: "Secret special spells and capabilities are
# attainable at high levels of ability") used to appear in the Cast
# dropdown unconditionally, for every leader regardless of skill --
# these 6 are only real for a leader who's actually reached skill 5+
# in the governing magical Ability (``CTBOTH.PAS``'s own ``spdex``
# lookup table), confirmed by the user this round. The other 4 secret
# spells (Scar Terrain/Mystic Winds/Locate Object/Illusory Fog) are
# deliberately NOT included here -- each already has its own, real
# ``AdvancedAbility``-gated unlock mechanism (``turn/cast_execution.py``'s
# own ``SCAR_TERRAIN_SPELL``/``MYSTIC_WINDS_SPELL``/``LOCATE_OBJECT_
# SPELL``/``ILLUS_FOG_SPELL``), a one-time grant rather than a live
# skill-level re-check -- out of this round's narrower scope.
#
# Checking ``effective_skill_level()`` at compose time (rather than
# needing a separate "as of last turn" snapshot) already gives exactly
# that: the GM composes turn N's own moves against the skill level
# ``leader.skills`` held at the *end* of turn N-1, since turn N's own
# Practice/experience gains are only ever applied during that turn's
# own processing, strictly after this page is rendered.
SECRET_SPELL_SKILL_THRESHOLD = 5
SECRET_SPELL_ABILITY: dict[Spell, Ability] = {
    Spell.GATE_ANGEL: Ability.WHITE,
    Spell.HEAL: Ability.WHITE,
    Spell.GATE_DEMON: Ability.NECROMANCY,
    Spell.LAVA_POOL: Ability.ELEMENTAL,
    Spell.AUGUR_COMBAT: Ability.PSYCHIC,
    Spell.ILLUS_HERO: Ability.ILLUSION,
}


def _leader_knows_secret_spell(state: GameState, leader: LeaderState, spell: Spell) -> bool:
    """``True`` unless ``spell`` is one of ``SECRET_SPELL_ABILITY``'s own
    six gated spells and this leader's own current ``effective_skill_
    level()`` in its governing Ability falls short of ``SECRET_SPELL_
    SKILL_THRESHOLD`` -- every other spell is unconditionally available,
    unaffected by this check.
    """

    ability = SECRET_SPELL_ABILITY.get(spell)
    if ability is None:
        return True
    return effective_skill_level(state, leader, ability) >= SECRET_SPELL_SKILL_THRESHOLD


# Every real Terrain a GM could plausibly pick for Illusory Terrain's
# own fake-terrain field -- ``Terrain.NO_TERRAIN`` is a placeholder
# sentinel that "never actually appears on a generated map"
# (``webapp/hex_map.py``'s own comment), not a real terrain a GM would
# ever want an illusion to mimic.
CAST_TERRAIN_CHOICES: tuple[Terrain, ...] = tuple(terrain for terrain in Terrain if terrain is not Terrain.NO_TERRAIN)

PHASE_COUNT = 5  # P0..P4 -- every real AK3__T*.K1 sample's own leader block shape.

# User-sourced (2026-11-15) display names for this interface's own compose
# table row labels -- the real AK3__T*.K1 wire format's own "P0".."P4"
# phase-label convention stays completely unchanged everywhere else (every
# field name, every compose-time validation error's own ``phase_label``),
# this only renumbers what the GM actually *sees* in the table's own
# leftmost column, 1-indexed with the boardgame's own season name attached.
PHASE_DISPLAY_NAME: dict[int, str] = {
    0: "P1 -- Spring",
    1: "P2 -- Early Summer",
    2: "P3 -- Late Summer",
    3: "P4 -- Autumn",
    4: "P5 -- Early Winter",
}

# User-sourced rename (2026-11-15, second round): "Kill Enemy" (Spell
# ordinal 5) is relabeled "Kill an Enemy" in this interface's own Cast
# dropdowns only -- ``SPELL_NAME`` above stays the real, sourced
# ``CTBOTH.PAS spname[]`` text verbatim (what real report/rumor prose
# elsewhere actually prints), so this is a display-only override layered
# on top of it here, never a change to that sourced table itself.
_SPELL_UI_NAME_OVERRIDES: dict[Spell, str] = {
    Spell.KILL_ENEMY: "Kill an Enemy",
}


def _spell_display_name(spell: Spell) -> str:
    """``SPELL_NAME``'s own real display text, with this interface's own
    ``_SPELL_UI_NAME_OVERRIDES`` swapped in first where one exists --
    the one helper every Cast-spell dropdown builder below calls, so
    the override can never drift out of sync between them.
    """

    override = _SPELL_UI_NAME_OVERRIDES.get(spell)
    if override is not None:
        return override
    return SPELL_NAME.get(spell, spell.name.replace("_", " ").title())

# "Nothing special configured" -- the one Special Encounter Plan value
# every leader in this project's own real sample files shows (sourced
# directly: no sample has ever shown a different SP: value). Every
# real roster leader's own SP: is now composable (see this module's
# own docstring's Special Encounter Plan section) -- this default
# stays in use for a hero's own *nested* plan, where composing a real
# SP: is deliberately out of scope (see the Nested Plan Richness
# section's own closing paragraph).
DEFAULT_SP: tuple[int, ...] = (10, -1)

# A safe, real-sample-matched default for the move file's own header
# line -- confirmed unused by turn processing (turn/kingdom_bridge.py
# never reads a single field of it), so any valid-shaped value works.
DEFAULT_HEADER_RAW_FIELDS: list[int] = [27, 1, 0, 101, 1, 15, 1]


class InvalidComposedMovesError(ValueError):
    """Raised when the GM's own composed-moves form can't be turned into a valid ``Kingdom``."""


def kingdom_leaders_for_compose(state: GameState, kingdom_id: int) -> list[LeaderState]:
    """Every leader this Kingdom would need to submit a move-file entry
    for this turn: the King first, then every Hero currently in this
    Kingdom's service (``kingdom_id`` match) -- the exact same roster a
    real move file's own leader blocks list, by this project's own
    established ``is_king`` convention.
    """

    leaders = [leader for leader in state.leaders.values() if leader.kingdom_id == kingdom_id]
    leaders.sort(key=lambda leader: (not leader.is_king, leader.leader_id))
    return leaders


def province_options(state: GameState, leader_id: int | None = None) -> list[tuple[str, str]]:
    """Every province as a ``(value, label)`` pair for a Move phase's own
    destination dropdown -- ``value`` is ``"x,y"`` (parsed back by
    ``_parse_move_target()``), ``label`` is the province's own real name
    where one exists (else just its coordinate), its ``(x, y)``
    coordinate, and its real "#<N>" province number (``report/turn_
    report.py real_province_number()``, the same ``x*100+y`` convention
    real reports already show, e.g. "Mongu (#305)" -- sourced directly
    from the user, 2026-10-26, who asked for it alongside the name/
    coordinates "come nell'AK originale"). This is purely a display
    label: the dropdown's own submitted ``value``, and the destination
    this module actually encodes into the move file, is still the
    plain ``x,y`` coordinate -- see this module's own docstring for why
    the real province number is a different, display-only scheme from
    the internal Move-order encoding. Sorted in map reading order (row
    by row, left to right).

    ``leader_id`` (2026-11-15, optional, same shape as ``feature_
    options()``'s own ``leader_id``): when given and resolvable to a
    leader with a real ``kingdom_id``, narrows the list to provinces
    that Kingdom actually ``known_to_kingdom()`` (``models/game_state.py
    ProvinceState``, Phase 623's "known provinces") -- Move's own
    destination dropdown uses this (a GM composing one Kingdom's own
    moves shouldn't be shown the whole map's real province identities,
    a real information leak the user flagged this round). Every other
    province-target dropdown (Defend, Cast's/Use Item's own province-
    target spells) still calls this with no ``leader_id`` at all, out
    of this round's narrower scope, and keeps the full unfiltered list.
    """

    leader = state.leaders.get(leader_id) if leader_id is not None else None
    provinces = sorted(state.provinces.values(), key=lambda province: (province.coord.y, province.coord.x))
    options = []
    for province in provinces:
        if leader is not None and leader.kingdom_id is not None and not province.known_to_kingdom(leader.kingdom_id):
            continue
        value = f"{province.coord.x},{province.coord.y}"
        name_part = province.name if province.name else ""
        number = real_province_number(province.coord)
        label = f"{name_part} ({province.coord.x}, {province.coord.y}) #{number}".strip()
        options.append((value, label))
    return options


def feature_options(state: GameState, *, leader_id: int | None = None) -> list[tuple[str, str]]:
    """Every feature as a ``(value, label)`` pair for a Search phase's own
    target-feature dropdown -- ``value`` is the feature's own real
    ``feature_id`` (exactly what ``obj`` is for Search, so no separate
    encoding step is needed the way Move's own coordinate needs
    ``encode_hex_number()``). ``label`` names its kind, the province
    it sits in (name where one exists, else coordinate), and its
    guardian monster where one is known and the feature hasn't already
    been looted -- e.g. "#3 Altar -- Numenor (3, 9) -- Necromancer".
    Sorted by ``feature_id``, the same "#<N>" a GM would already look
    the feature up by on a PROVINCES report's own "Features and F#"
    column.

    ``leader_id`` (sourced directly from the user, 2026-10-27, as part
    of designing the Fulfill tactic): when given, a feature this leader
    currently holds a pending deal on (``Feature.pending_deal_leader_id``
    -- the one a prior turn's successful Talk set, per ``turn/search_
    execution.py``'s own ``_resolve_talk()``/``_resolve_fulfill()``) is
    flagged "-- pending quest for this leader", since Fulfill (this
    module's own docstring has its full sourcing) always resolves
    *whichever* feature the same Search phase's own ``obj`` already
    names -- there's no separate quest id to pick, only this same
    feature dropdown, so surfacing the one feature Fulfill would
    actually do something on here is the whole point.

    **Also used, 2026-11-15 at the user's own request, to filter the
    list down to features this leader's own Kingdom actually knows
    about** (``Feature.discovery_level(kingdom_id) > 0``, the same
    "known at all" floor ``describe_adventure_report()`` already uses
    -- see that function's own docstring): a GM composing this
    Kingdom's own moves shouldn't be able to target a feature that
    Kingdom's real player could never have learned the number of, even
    one sitting in a province that Kingdom doesn't own (a feature's own
    discovery is independent of who owns its province -- rumors, Spy,
    and Move/Explore's own passive reveal of a feature in an *adjacent*
    province can all name one well outside this Kingdom's own borders).
    A co-located Search against a feature this leader's Kingdom hasn't
    actually discovered yet is separately, already rejected for real at
    turn-processing time regardless of this dropdown (``turn/search_
    execution.py execute_search()``'s own co-location check runs
    against wherever the leader actually *is* once this phase dispatches,
    which this compose-time snapshot can't always know -- an earlier
    phase of the very same turn may still Move this leader there first
    -- so this module deliberately adds no matching compose-time
    co-location check of its own).
    """

    leader = state.leaders.get(leader_id) if leader_id is not None else None
    features = sorted(state.features.values(), key=lambda feature: feature.feature_id)
    options = []
    for feature in features:
        if leader is not None and leader.kingdom_id is not None and feature.discovery_level(leader.kingdom_id) <= 0:
            continue
        province = state.provinces.get(feature.coord)
        place = province.name if province is not None and province.name else f"({feature.coord.x}, {feature.coord.y})"
        label = f"#{feature.feature_id} {FEATURE_TYPE_NAMES[feature.kind]} -- {place}"
        if feature.guardian_monster is not None and not feature.looted:
            label += f" -- {MONSTER_NAMES.get(feature.guardian_monster, feature.guardian_monster.name.title())}"
        if leader_id is not None and feature.pending_deal_leader_id == leader_id:
            label += " -- pending quest for this leader"
        options.append((str(feature.feature_id), label))
    return options


def spell_options(state: GameState | None = None, leader_id: int | None = None) -> list[tuple[int, str]]:
    """Every spell a Cast tactic can actually use inside a Search
    Encounter Plan (``ENCOUNTER_PLAN_CASTABLE_SPELLS``), as ``(value,
    display_name)`` pairs for the Cast tactic's own dedicated spell
    dropdown -- see this module's own docstring for why Cast gets a
    named dropdown instead of the generic numeric sub-object field
    every other ``TACTICS_WITH_SUB_OBJECT`` maneuver uses. Sorted by
    the spell's own real ordinal.

    ``state``/``leader_id`` (2026-11-14, both optional): when given and
    resolvable, also drops any of ``SECRET_SPELL_ABILITY``'s own six
    gated spells this leader hasn't actually reached skill 5+ for yet
    (``_leader_knows_secret_spell()``) -- omitted (the nested-plan
    nested_hero/not-yet-resolvable case, where the real leader casting
    isn't known at render time) returns the full, unfiltered list, same
    as before this round.
    """

    leader = state.leaders.get(leader_id) if state is not None and leader_id is not None else None
    return [
        (int(spell), _spell_display_name(spell))
        for spell in sorted(ENCOUNTER_PLAN_CASTABLE_SPELLS, key=int)
        if leader is None or state is None or _leader_knows_secret_spell(state, leader, spell)
    ]


def item_options(state: GameState, leader_id: int) -> list[tuple[str, str]]:
    """Every magic item this leader could actually use via a Use Item
    tactic inside a Search Encounter Plan, as ``(value, display_name)``
    pairs for Use Item's own dedicated item dropdown -- see this
    module's own docstring for why this lists only *this leader's own,
    currently-owned, still-charged* wands whose own fixed spell is one
    of ``ENCOUNTER_PLAN_CASTABLE_SPELLS``, not a global item catalog:
    ``sub_object`` names a specific item instance this leader must
    actually hold (``GameState.items_held_by()``), and every other
    item (a non-wand, or a wand whose spell isn't composable here) is
    a documented engine-side no-effect if offered. Sorted by the
    item's own real id.
    """

    options = []
    for item in sorted(state.items_held_by(leader_id), key=lambda item: item.item_id):
        if TREASURE_CATEGORY.get(item.treasure) is not TreasureCategory.SPELL_WAND:
            continue
        spell = TREASURE_WAND_SPELL.get(item.treasure)
        if spell is None or spell not in ENCOUNTER_PLAN_CASTABLE_SPELLS or item.charges <= 0:
            continue
        item_name = TREASURE_NAME.get(item.treasure, item.treasure.name.replace("_", " ").title())
        spell_name = SPELL_NAME.get(spell, spell.name.replace("_", " ").title())
        charge_word = "charge" if item.charges == 1 else "charges"
        label = f"#{item.item_id} {item_name} -- casts {spell_name} ({item.charges} {charge_word} left)"
        options.append((str(item.item_id), label))
    return options


def use_mi_item_options(state: GameState, leader_id: int) -> list[tuple[str, str]]:
    """Every magic item this leader could actually Use via the
    top-level Use Magic Item Action [3.11] -- ``(value, display_name)``
    pairs for ``use_mi_item_<leader_id>_<n>``'s own dropdown.

    Not ``item_options()`` above (that one is the Search/Challenge/
    Pursue Encounter Plan's own Use Item *tactic*, restricted to
    ``ENCOUNTER_PLAN_CASTABLE_SPELLS`` -- the five Personal-Combat-only
    wand spells, one per Magical ``Ability``: Holy Symbol, Hand of
    Death, Fireball, Psychic Blast, Invisibility). This Action, by
    contrast, dispatches into ``turn/cast_execution.py execute_cast()``
    exactly like the top-level Cast Action does (``turn/use_mi_
    execution.py execute_use_mi()``'s own ``SPELL_WAND`` branch), so a
    wand is only offered here if its own fixed spell is one of
    ``CAST_ACTION_SPELLS`` -- the same 19-spell, Action-Cast-only
    restriction Cast's own dropdown already uses, which (since none of
    those five Personal-Combat spells has an Action-Cast target shape
    at all) happens to be this function's and ``item_options()``'s own
    mutually exclusive wand set: a given wand is offered by exactly one
    of the two dropdowns, never both.

    Also offers every owned skill book (``TreasureCategory.SKILL_BOOK``)
    -- rulebook [5.9]: "a one-shot, self-consuming +1 to one Ability
    when read," no charge concept and no target at all, so a book is
    listed regardless of any ``charges`` value. Sorted by the item's
    own real id, same convention as ``item_options()``.
    """

    options = []
    for item in sorted(state.items_held_by(leader_id), key=lambda item: item.item_id):
        category = TREASURE_CATEGORY.get(item.treasure)
        item_name = TREASURE_NAME.get(item.treasure, item.treasure.name.replace("_", " ").title())
        if category is TreasureCategory.SPELL_WAND:
            spell = TREASURE_WAND_SPELL.get(item.treasure)
            if spell is None or spell not in CAST_ACTION_SPELLS or item.charges <= 0:
                continue
            spell_name = SPELL_NAME.get(spell, spell.name.replace("_", " ").title())
            charge_word = "charge" if item.charges == 1 else "charges"
            label = f"#{item.item_id} {item_name} -- casts {spell_name} ({item.charges} {charge_word} left)"
        elif category is TreasureCategory.SKILL_BOOK:
            ability = TREASURE_BOOK_ABILITY.get(item.treasure)
            ability_name = ABILITY_NAME.get(ability, ability.name.title()) if ability is not None else "?"
            label = f"#{item.item_id} {item_name} -- +1 {ability_name} (self-consuming)"
        else:
            continue
        options.append((str(item.item_id), label))
    return options


def use_mi_item_spell_by_id(state: GameState) -> dict[int, int]:
    """Every wand in the whole game, as ``item_instance_id -> its own
    fixed Spell ordinal`` -- used only by the template's own Use Magic
    Item ``<option data-spell="...">`` attribute, so its client-side
    target-sub-field toggle (``updateUseMICell()``) can tell which of
    Cast's own 5 target shapes a *selected item* needs without a round
    trip, the same way Cast's own dropdown lets the browser read the
    shape straight off ``select.value`` (a Spell ordinal there already).
    Not filtered to any one leader, or to Action-Cast eligibility --
    ``use_mi_item_options()`` already did that filtering, so only ids
    that dropdown actually offers ever reach this lookup from the
    template; a skill book has no entry at all (the template's own
    ``.get(..., "")`` default renders an empty ``data-spell``, correctly
    showing no target cell).
    """

    return {
        item.item_id: int(TREASURE_WAND_SPELL[item.treasure])
        for item in state.items.values()
        if TREASURE_CATEGORY.get(item.treasure) is TreasureCategory.SPELL_WAND and item.treasure in TREASURE_WAND_SPELL
    }


def give_item_options(state: GameState, leader_id: int) -> list[tuple[str, str]]:
    """Every item this leader currently owns, as ``(value, display_name)``
    pairs for the GIVE tactic's own dedicated item dropdown inside a
    Challenge/Pursue/Patrol Encounter Plan -- rulebook (2026-11-01):
    "si può dare qualsiasi numero di oggetti a chiunque si incontra,"
    no wand/spell-eligibility restriction at all (unlike ``item_
    options()``'s own Use-Item-specific filtering above) -- any owned
    item is a legal gift, excluding a Valhalla visitor's own fixed item
    (``LeaderState.valhalla_fixed_item_id``), which rulebook VALHALLA.txt
    says can never be given away at all (same exclusion ``trade_gift_
    options()`` already applies to the top-level Give Action's own
    dropdown). Sorted by the item's own real id, same convention as
    ``item_options()``.
    """

    options = []
    leader = state.leaders.get(leader_id)
    fixed_item_id = leader.valhalla_fixed_item_id if leader is not None else None
    for item in sorted(state.items_held_by(leader_id), key=lambda item: item.item_id):
        if item.item_id == fixed_item_id:
            continue
        item_name = TREASURE_NAME.get(item.treasure, item.treasure.name.replace("_", " ").title())
        options.append((str(item.item_id), f"#{item.item_id} {item_name}"))
    return options


def recruit_target_options(state: GameState, leader_id: int) -> list[tuple[str, str]]:
    """Every valid commander choice for a Recruit phase's own target
    dropdown, as ``(value, label)`` pairs -- rulebook [3.4]: "Any
    character in the province may lead the armies [...] even if
    belonging to an allied Realm, or they can be placed under the
    garrison commander." Always offers "Self" first, then every other
    leader (any Kingdom) co-located with the acting leader, then
    "Garrison" last. ``value`` is ``"self"``, the other leader's own id
    as a string, or ``"garrison"`` -- parsed back by
    ``_parse_recruit_target()`` into the real ``obj`` encoding
    (``turn/recruit_decode.py``'s own leader id / ``NO_LEADER_SENTINEL``).
    """

    leader = state.leaders.get(leader_id)
    options: list[tuple[str, str]] = [("self", f"Self ({leader.name})" if leader is not None else "Self")]
    if leader is not None:
        others = sorted(
            (
                other
                for other in state.leaders.values()
                if other.leader_id != leader_id and other.location == leader.location
            ),
            key=lambda other: other.leader_id,
        )
        for other in others:
            kingdom = state.kingdoms.get(other.kingdom_id)
            ally_part = (
                f", {kingdom.name}" if kingdom is not None and kingdom.kingdom_id != leader.kingdom_id else ""
            )
            options.append((str(other.leader_id), f"{other.name}{ally_part}"))
    options.append(("garrison", "Garrison (unled)"))
    return options


def recruit_type_options(state: GameState, leader_id: int) -> list[tuple[str, str]]:
    """Every army type recruitable at this leader's own current
    location, as ``(value, label)`` pairs for a Recruit phase's own
    repeated type-slot dropdowns -- ``value`` is the type's own real
    ``army`` enum ordinal (``models/army_type.py ARMY_TYPE_BY_ORDINAL``,
    exactly what a real Recruit phase's own ``extra`` tail lists), so no
    separate encoding step is needed. Race-incompatible types
    (``is_army_type_compatible_with_race()``) and the 8 real ordinals
    with no ``ARMY_TABLE`` cost entry (``turn/recruit.py``'s own
    docstring) are never offered -- neither can ever actually be
    recruited, regardless of what this dropdown would show.

    The label previews, informationally only (the engine, not this
    dropdown, is the final arbiter at turn-processing time -- the same
    "composer informs, engine enforces" split every other richer
    dropdown here already follows, e.g. Fulfill's own pending-quest
    flag): whether the type is this province's own native type (real
    ``ProvinceState.recruit_type_1``/``recruit_type_2`` data when
    bridged from a real world file, else the broader race-compatibility
    approximation -- exactly ``turn/recruit_execution.py``'s own
    ``is_native`` logic), its per-unit cost (doubled if non-native,
    flagging that RULES.AK [3.4]'s own ownership precondition then
    applies -- see ``turn/recruit.py NonNativeTypeNotYetOwnedError``),
    how many of this type have already been recruited here this turn
    against the base per-turn limit (``ProvinceState.recruited_this_
    turn``/``turn/recruit.py recruit_limit()`` -- a conservative lower
    bound, since a King's home-province bonus is factored in but a
    Wingman/Marshal/Admiral Office-holder's own extra slot isn't, see
    this module's own docstring), and whether a hireable mercenary band
    of this type is already present (``GameState.mercenaries_at()``,
    the same ``quality >= Average``/``not unhireable_this_turn`` filter
    ``execute_recruit()`` itself uses).
    """

    leader = state.leaders.get(leader_id)
    if leader is None:
        return []
    province = state.provinces.get(leader.location)
    if province is None:
        return []
    kingdom = state.kingdoms.get(leader.kingdom_id)
    is_home_province = (
        kingdom is not None
        and leader.location == kingdom.home_province
        and province.owner_kingdom_id == kingdom.kingdom_id
    )

    options: list[tuple[str, str]] = []
    for ordinal in sorted(ARMY_TYPE_BY_ORDINAL):
        army_type = ARMY_TYPE_BY_ORDINAL[ordinal]
        if army_type not in ARMY_TABLE or not is_army_type_compatible_with_race(army_type, province.race):
            continue
        # Bug fix (2026-11-15, user-reported): this preview's own
        # ``is_native`` used to skip the exact 2 exemptions ``turn/
        # recruit_execution.py execute_recruit()``'s own real dispatch
        # already applies (Phase 1054) -- Garrison (never actually a
        # listed province slot type, but RULES.AK's own real "always
        # recruitable, 1 gold, in any humanoid province" unit, see that
        # function's own docstring) and Dinosaurs (an ability-gated
        # type the per-province native-slot mechanic was never meant
        # to price at all). Without this, the dropdown wrongly showed
        # Garrison as "(non-native, 2 gold -- needs an existing unit of
        # this type)" in every province whose own 2 listed slot types
        # just don't happen to include it -- which is every province,
        # since real data never lists it as one.
        if army_type is ArmyType.GARRISON and province.race in HUMANOID_RACES:
            is_native = True
        elif army_type is ArmyType.DINOSAURS:
            is_native = True
        elif province.recruit_type_1 is not None:
            is_native = army_type in (province.recruit_type_1, province.recruit_type_2)
        else:
            is_native = True
        # Reuses the real resolver's own gold_per_unit formula instead of
        # recomputing the native/non-native doubling by hand -- this is
        # a preview label only (the real eligibility check happens at
        # actual Recruit-order dispatch time), so commander_already_has_
        # type=True bypasses resolve_recruit()'s own NonNativeTypeNotYet
        # OwnedError just to read the cost it would charge.
        cost = resolve_recruit(
            army_type,
            province.race,
            is_home_province=is_home_province,
            is_native_to_province=is_native,
            commander_already_has_type=True,
        ).gold_per_unit
        label = f"{ARMY_TYPE_NAME[army_type]} ({'native' if is_native else 'non-native'}, {cost} gold"
        if not is_native:
            label += " -- needs an existing unit of this type"
        label += ")"
        already = province.recruited_this_turn.get(army_type, 0)
        limit = recruit_limit(army_type, is_home_province=is_home_province, province_race=province.race)
        if already:
            label += f" -- {already}/{limit}+ recruited this turn"
        mercenary_count = sum(
            1
            for army in state.mercenaries_at(leader.location)
            if army.army_type is army_type and army.quality >= Quality.AVERAGE and not army.unhireable_this_turn
        )
        if mercenary_count:
            unit_word = "unit" if mercenary_count == 1 else "units"
            label += f" -- {mercenary_count} mercenary {unit_word} present"
        options.append((str(ordinal), label))
    return options


def _disband_army_label(state: GameState, army: ArmyState) -> str:
    type_name = ARMY_TYPE_NAME[army.army_type]
    quality_name = QUALITY_NAME[army.quality]
    if army.commanded_by is not None:
        commander = state.leaders.get(army.commanded_by)
        commander_part = commander.name if commander is not None else f"leader #{army.commanded_by}"
    else:
        commander_part = "Garrison"
    province = state.provinces.get(army.location)
    place = (
        province.name
        if province is not None and province.name
        else f"({army.location.x}, {army.location.y})"
    )
    return f"#{army.army_id} {type_name} ({quality_name}) -- {commander_part} -- {place}"


def disband_target_options(state: GameState, leader_id: int, *, slot: int) -> list[tuple[str, str]]:
    """Every army this leader could actually Disband post-fix, as
    ``(value, label)`` pairs for a Disband phase's own repeated
    army-target dropdowns -- ``value`` is the army's own real
    ``army_id`` as a string (exactly what a real Disband phase's own
    ``extra`` tail lists), so no separate encoding step is needed.

    Pre-filtered to match ``turn/plan_dispatch.py _dispatch_disband()``'s
    own (now Kingdom-boundary-checked) rules exactly, so there's no way
    to compose an order the engine would just silently skip: every army
    of this leader's own Kingdom (``ArmyState.kingdom_id``), further
    narrowed to this leader's own current location unless this leader
    ``is_king`` (the real Phase 40 co-location bypass -- a King's own
    list spans the whole Kingdom's armies, garrison-commanded or
    commanded by another Hero included, exactly the rulebook's own
    "anche quelle al garrison commander... o comandate da un altro
    eroe"). Sorted by the army's own real id.

    ``slot`` controls whether the list's own dedicated ``DISBAND_ALL_
    VALUE`` pseudo-option ("ALL", shortened from "Disband ALL I
    command" 2026-11-15 at the user's own request -- the Disband label
    already says "Disband", so the dropdown option repeating it was
    redundant) is prepended -- only ever offered in slot 0, mirroring
    Talk's own "only the first slot" shape in Search's Encounter Plan --
    see this module's own docstring for why it can't be combined with a
    specific army list.
    """

    leader = state.leaders.get(leader_id)
    if leader is None:
        return []
    options: list[tuple[str, str]] = []
    if slot == 0:
        options.append((DISBAND_ALL_VALUE, "ALL"))
    for army in sorted(state.armies.values(), key=lambda army: army.army_id):
        if army.kingdom_id != leader.kingdom_id:
            continue
        if not leader.is_king and army.location != leader.location:
            continue
        options.append((str(army.army_id), _disband_army_label(state, army)))
    return options


def leave_target_options(state: GameState, leader_id: int) -> list[tuple[str, str]]:
    """Every valid "to" choice for a Leave phase's own target dropdown,
    as ``(value, label)`` pairs -- rulebook [3.8]: "LE ... to #numero
    eroe o GC." Offers every other leader (any Kingdom) co-located with
    the acting leader *and* of his own or an allied Kingdom
    (``GameState.is_allied()`` -- "anche di un altro Reame, basta che
    sia alleato"; a hostile/unrelated Kingdom's leader is never offered,
    matching ``turn/plan_dispatch.py _dispatch_leave()``'s own new
    alliance gate), then "Garrison Commander" last. ``value`` is the
    other leader's own id as a string, or ``LEAVE_GARRISON_VALUE`` --
    parsed back by ``_parse_leave_target()`` into the real ``obj``
    encoding (``turn/army_list_decode.py``'s own leader id/
    ``NO_LEADER_SENTINEL``).
    """

    leader = state.leaders.get(leader_id)
    options: list[tuple[str, str]] = []
    if leader is not None:
        others = sorted(
            (
                other
                for other in state.leaders.values()
                if other.leader_id != leader_id
                and other.location == leader.location
                and state.is_allied(leader.kingdom_id, other.kingdom_id)
            ),
            key=lambda other: other.leader_id,
        )
        for other in others:
            kingdom = state.kingdoms.get(other.kingdom_id)
            ally_part = (
                f", {kingdom.name}" if kingdom is not None and kingdom.kingdom_id != leader.kingdom_id else ""
            )
            options.append((str(other.leader_id), f"{other.name}{ally_part}"))
    options.append((LEAVE_GARRISON_VALUE, "Garrison Commander"))
    return options


def leave_army_target_options(state: GameState, leader_id: int, *, slot: int) -> list[tuple[str, str]]:
    """Every army this leader could actually Leave post-fix, as
    ``(value, label)`` pairs for a Leave phase's own repeated
    army-target dropdowns -- the same eligibility rule and
    ``_disband_army_label()`` display shape ``disband_target_options()``
    already uses, since ``turn/plan_dispatch.py _dispatch_leave()``'s
    own new ownership check is identical to Disband's: every army
    commanded by this leader, plus (the rulebook's own "novità")
    any Garrison-commanded (``commanded_by is None``) army of this
    leader's own Kingdom that's co-located with him -- this is the
    one real difference from Disband's own dropdown, which never
    offers a Garrison-commanded army at all for a non-King Hero.

    ``slot`` controls whether the list's own dedicated ``LEAVE_ALL_
    VALUE`` pseudo-option ("ALL", shortened from "Leave ALL I command"
    2026-11-15 at the user's own request, same reasoning as Disband's
    own "ALL" rename) is prepended -- only ever offered in slot 0, the
    same shape ``disband_target_options()`` already uses for
    ``DISBAND_ALL_VALUE``.
    """

    leader = state.leaders.get(leader_id)
    if leader is None:
        return []
    options: list[tuple[str, str]] = []
    if slot == 0:
        options.append((LEAVE_ALL_VALUE, "ALL"))
    for army in sorted(state.armies.values(), key=lambda army: army.army_id):
        if army.kingdom_id != leader.kingdom_id:
            continue
        if army.commanded_by != leader_id and not (army.commanded_by is None and army.location == leader.location):
            continue
        options.append((str(army.army_id), _disband_army_label(state, army)))
    return options


def pick_up_army_target_options(state: GameState, leader_id: int, *, slot: int) -> list[tuple[str, str]]:
    """Every army this leader could actually Pick Up post-fix, as
    ``(value, label)`` pairs for a Pick Up phase's own repeated
    army-target dropdowns, reusing ``_disband_army_label()`` for each
    option's own display -- matching ``turn/plan_dispatch.py
    _dispatch_pick_up()``'s own eligibility rule exactly: every
    co-located army of this leader's own Kingdom (commanded by anyone,
    or unled -- the user's own explicit choice, unlike Leave/Disband:
    Pick Up may reorganize command among one's own co-located forces,
    just never reach into a different Kingdom), except one that was
    freshly levied (not hired as a mercenary) this very turn
    (``ArmyState.recruited_this_turn``).

    ``slot`` controls whether the list's own dedicated ``PICK_UP_ALL_
    VALUE`` pseudo-option ("ALL", shortened from "Pick Up ALL unled
    armies here" 2026-11-15 at the user's own request, same reasoning
    as Disband's/Leave's own "ALL" rename) is prepended -- only ever
    offered in slot 0, the same shape ``disband_target_options()``/
    ``leave_army_target_options()`` already use.
    """

    leader = state.leaders.get(leader_id)
    if leader is None:
        return []
    options: list[tuple[str, str]] = []
    if slot == 0:
        options.append((PICK_UP_ALL_VALUE, "ALL"))
    for army in sorted(state.armies.values(), key=lambda army: army.army_id):
        if army.location != leader.location or army.kingdom_id != leader.kingdom_id:
            continue
        if army.recruited_this_turn and not army.is_mercenary:
            continue
        options.append((str(army.army_id), _disband_army_label(state, army)))
    return options


def _sorted_leaders(state: GameState) -> list[LeaderState]:
    """``sorted(state.leaders.values(), key=lambda other: other.leader_id)``
    -- every leader-target dropdown function below independently
    re-derived this exact same expression (2026-11-02 review finding).
    One shared place to read it from, rather than ten copies that could
    silently drift (e.g. a future one sorting by name instead of id).

    **Not memoized across calls**: ``GameState`` is an unhashable,
    ``slots=True`` dataclass (no ``__hash__``, no ad-hoc attributes),
    so neither a ``WeakKeyDictionary`` keyed by the ``state`` object
    nor caching the result directly on it is possible without a
    larger, separate change to that model -- this still re-sorts once
    per call, same real cost as before, just no longer ten different
    inline copies of the same expression to keep in sync.
    """

    return sorted(state.leaders.values(), key=lambda other: other.leader_id)


def _trade_recipient_blackmail_king(state: GameState, leader: LeaderState) -> LeaderState | None:
    """The blackmailer's own King a Give from ``leader`` may pay off
    even when not co-located -- the one non-co-located exception
    ``trade_recipient_options()``/``_parse_trade_recipient()`` both
    need, factored out so the two can never drift (see each function's
    own docstring for the full rule).
    """

    if not leader.is_king:
        return None
    giver_kingdom = state.kingdoms.get(leader.kingdom_id)
    claim = giver_kingdom.active_blackmail if giver_kingdom is not None else None
    if claim is None:
        return None
    return find_king_of_kingdom(state, claim.spy_kingdom_id)


def _trade_recipient_is_eligible(state: GameState, leader: LeaderState, candidate_id: int) -> bool:
    """**2026-11-07 bug fix.** The real eligibility rule ``trade_
    recipient_options()`` below already encodes for its own dropdown --
    extracted here so ``_parse_trade_recipient()`` can finally re-run
    the exact same check server-side ("defense in depth"), the one
    thing this module's own docstring already explicitly expects of
    every other target field. Previously ``_parse_trade_recipient()``
    only checked that ``candidate_id`` resolved to *some* real leader,
    with no co-location/Curator-self/blackmail-king re-check at all --
    a tampered or stale POST naming any other real, ineligible leader
    passed compose-time validation and was only caught much later and
    silently (``turn/trade_execution.py execute_give()``'s own co-
    location check returning ``applied=False``, not raising) at turn-
    processing time.

    True when ``candidate_id`` is: another leader (any Kingdom)
    co-located with ``leader``; ``leader``'s own id, when ``leader``
    currently holds ``Office.CURATOR`` (the "Self" research case); or
    the blackmailer's own King, when ``leader`` carries an active
    blackmail claim (the one non-co-located exception).
    """

    if candidate_id == leader.leader_id:
        curator_holder = resolve_office_holder(state, Office.CURATOR)
        return curator_holder is not None and curator_holder.leader_id == leader.leader_id

    candidate = state.leaders.get(candidate_id)
    if candidate is not None and candidate.location == leader.location:
        return True

    blackmail_king = _trade_recipient_blackmail_king(state, leader)
    return blackmail_king is not None and blackmail_king.leader_id == candidate_id


def trade_recipient_options(state: GameState, leader_id: int) -> list[tuple[str, str]]:
    """Every valid Give recipient for this leader, as ``(value, label)``
    pairs -- rulebook [3.18]: the recipient must be co-located ("che si
    trova nella stessa provincia"), with no Kingdom restriction at all
    (Give explicitly crosses Kingdoms freely, unlike Leave). ``value``
    is the recipient's own leader id as a string -- the real wire
    encoding already is a bare leader id, so no special sentinel is
    needed even for the two further cases below.

    Two further, already-implemented real cases are surfaced here too,
    rather than left for the GM to discover only by a failed order:
    "Self" (the acting leader's own id again), offered only when he
    currently holds ``Office.CURATOR`` (rerouting to ``execute_
    curator_research()`` instead of an ordinary Give -- see ``turn/
    plan_dispatch.py _dispatch_trade()``'s own Phase 667 addendum), and
    the blackmailer's own King, offered even when NOT co-located, when
    this leader's own Kingdom currently carries an active ``KingdomState.
    active_blackmail`` claim (``turn/trade_execution.py execute_give()``'s
    own Phase 713 co-location waiver for paying it off).

    **2026-11-07**: the co-location/Curator-self/blackmail-king
    eligibility rule above is now shared with ``_parse_trade_recipient()``
    via ``_trade_recipient_is_eligible()`` -- this function itself stays
    a plain loop (it also needs each candidate's own display label,
    which that boolean-only helper doesn't produce), but the two can no
    longer silently disagree about who's eligible.
    """

    leader = state.leaders.get(leader_id)
    if leader is None:
        return []
    options: list[tuple[str, str]] = []
    offered_ids: set[int] = set()
    for other in _sorted_leaders(state):
        if other.leader_id == leader_id or other.location != leader.location:
            continue
        kingdom = state.kingdoms.get(other.kingdom_id)
        kingdom_part = (
            f", {kingdom.name}" if kingdom is not None and kingdom.kingdom_id != leader.kingdom_id else ""
        )
        options.append((str(other.leader_id), f"{other.name}{kingdom_part}"))
        offered_ids.add(other.leader_id)

    curator_holder = resolve_office_holder(state, Office.CURATOR)
    if curator_holder is not None and curator_holder.leader_id == leader_id:
        options.append((str(leader_id), "Self (research an item's magical function)"))

    blackmail_king = _trade_recipient_blackmail_king(state, leader)
    if blackmail_king is not None and blackmail_king.leader_id not in offered_ids:
        claim = state.kingdoms[leader.kingdom_id].active_blackmail
        kingdom = state.kingdoms.get(claim.spy_kingdom_id)
        kingdom_name = kingdom.name if kingdom is not None else f"Kingdom {claim.spy_kingdom_id}"
        options.append(
            (
                str(blackmail_king.leader_id),
                f"Pay blackmail: {blackmail_king.name}, {kingdom_name} ({claim.amount} gold owed)",
            )
        )
    return options


def trade_gift_options(state: GameState, leader_id: int) -> list[tuple[str, str]]:
    """Every item this leader could actually Give, as ``(value, label)``
    pairs for Give's own gift dropdown, plus ``TRADE_GOLD_VALUE``
    ("Gold") first -- rulebook [3.18]: an owned item takes priority
    over gold whenever both could apply ("si passa l'oggetto e non
    l'oro"), so this dropdown only ever lists items this leader
    genuinely owns (``GameState.items_held_by()``), excluding a
    Valhalla visitor's own fixed item (``LeaderState.valhalla_fixed_
    item_id``), which rulebook VALHALLA.txt says can never be given
    away at all (``turn/trade_execution.py execute_give()``'s own
    Phase 547 addendum).

    ``TRADE_ITEM_NUMBER_VALUE`` (2026-11-16, user-requested) comes
    right after Gold -- an item this leader owns but that this
    dropdown's own start-of-turn snapshot doesn't yet list (looted
    earlier the very same turn), named by its own hand-typed order
    number instead.
    """

    options: list[tuple[str, str]] = [
        (TRADE_GOLD_VALUE, "Gold (type an amount)"),
        (TRADE_ITEM_NUMBER_VALUE, "Item # (type below)"),
    ]
    leader = state.leaders.get(leader_id)
    if leader is None:
        return options
    for item in sorted(state.items_held_by(leader_id), key=lambda item: item.item_id):
        if item.item_id == leader.valhalla_fixed_item_id:
            continue
        item_name = TREASURE_NAME.get(item.treasure, item.treasure.name.replace("_", " ").title())
        options.append((str(item.item_id), f"#{item.item_id} {item_name}"))
    return options


def practice_ability_options() -> list[tuple[int, str]]:
    """Every ``Ability`` a Practice order can target, as ``(value,
    display_name)`` pairs for Practice's own single dropdown -- rulebook
    [3.13]'s syntax is just "PR (sigla del talento)", one Talent per
    order, so this is the whole composer surface for this Action. Sorted
    by the ability's own real ordinal, matching ``ABILITY_NAME``'s own
    display strings used everywhere else in this project.
    """

    return [(ability.value, ABILITY_NAME[ability]) for ability in sorted(Ability, key=lambda a: a.value)]


def trail_target_options(state: GameState, leader_id: int) -> list[tuple[str, str]]:
    """Every other leader in the game as a ``(value, label)`` pair for
    Trail's own target dropdown -- rulebook [3.17]'s own "#(numero
    d'ordine del re o dell'eroe)" is the real target ``leader_id``
    (``turn/trail_decode.py``'s own docstring; despite the Italian
    phrasing, not a roster-position ordinal), and, unlike Give/Leave,
    Trail needs no co-location at all between trailer and target
    (``turn/trail_execution.py execute_trail()`` computes a distance-
    based catch-up chance instead of requiring the two already be
    together) -- so every other living leader in the world is a valid
    target, any Kingdom, independent Heroes included.
    """

    if leader_id not in state.leaders:
        return []
    options: list[tuple[str, str]] = []
    for other in _sorted_leaders(state):
        if other.leader_id == leader_id:
            continue
        kingdom = state.kingdoms.get(other.kingdom_id)
        kingdom_part = kingdom.name if kingdom is not None else "independent"
        title_part = "King" if other.is_king else "Hero"
        options.append((str(other.leader_id), f"{other.name} ({title_part}, {kingdom_part})"))
    return options


def pursue_target_options(state: GameState, leader_id: int) -> list[tuple[str, str]]:
    """Every other leader in the game as a ``(value, label)`` pair for
    Pursue's own target dropdown -- same "chase from a distance, no
    co-location needed" shape as ``trail_target_options()`` (rulebook
    [3.16]'s own "PU #(numero dell'eroe o del re da inseguire)";
    ``turn/pursue_execution.py execute_pursue()`` computes a distance-
    based Spy Table catch-up chance rather than requiring the two
    already be together) -- any Kingdom, independent Heroes included.

    **2026-11-01, no longer excludes the acting leader themself**:
    ``turn/challenge_pursue_decode.py``'s own docstring confirms
    targeting one's own character id turns a Pursue order into a
    standing "Patrol" declaration instead -- a real, sourced rulebook
    mechanic ([3.16] "Characters On Patrol": "è come un ordine Difendere,
    solo che viene fatto da un Eroe senza armate... Per farlo dare
    all'Eroe un ordine Inseguire su se stesso"), already fully modeled
    engine-side in ``turn/patrol_execution.py`` -- unlike a prior round's
    assessment, this is not an unrelated mechanic to avoid exposing, it
    is this exact field's own documented second meaning. Offered as the
    first option, labelled "Patrol (self)" rather than the ordinary
    name/title/Kingdom label, since selecting it composes a
    structurally different, self-targeting order -- the same "customize
    the one self-referential option's own label" convention ``fire_
    target_options()``'s own "Self (<name>)" entry already uses.
    ``_parse_pursue_target()`` enforces Patrol's own "senza armate"
    precondition on the acting leader at compose time (point (a) below).
    """

    if leader_id not in state.leaders:
        return []
    leader = state.leaders[leader_id]
    options: list[tuple[str, str]] = [(str(leader_id), f"Patrol (self) -- {leader.name}")]
    for other in _sorted_leaders(state):
        if other.leader_id == leader_id:
            continue
        kingdom = state.kingdoms.get(other.kingdom_id)
        kingdom_part = kingdom.name if kingdom is not None else "independent"
        title_part = "King" if other.is_king else "Hero"
        options.append((str(other.leader_id), f"{other.name} ({title_part}, {kingdom_part})"))
    return options


def challenge_target_options(state: GameState, leader_id: int) -> list[tuple[str, str]]:
    """Every co-located leader as a ``(value, label)`` pair for
    Challenge's own target dropdown -- rulebook [3.12]: "nella stessa
    provincia," confirmed as a real, enforced requirement at execution
    time (``turn/challenge_execution.py execute_challenge()``'s own
    ``co_located`` check, not just prose) -- unlike Trail/Pursue, which
    chase from a distance, Challenge needs the two already together
    right now. No Kingdom restriction, same as Give -- any co-located
    leader is a valid target, any Kingdom. Pre-filtered to this
    composer's own start-of-turn snapshot, same convention already used
    for ``trade_recipient_options()``/``leave_target_options()``: a
    later phase this same turn could move either leader before this
    phase actually runs, so turn-processing time remains the real
    arbiter either way.
    """

    leader = state.leaders.get(leader_id)
    if leader is None:
        return []
    options: list[tuple[str, str]] = []
    for other in _sorted_leaders(state):
        if other.leader_id == leader_id or other.location != leader.location:
            continue
        kingdom = state.kingdoms.get(other.kingdom_id)
        kingdom_part = kingdom.name if kingdom is not None else "independent"
        title_part = "King" if other.is_king else "Hero"
        options.append((str(other.leader_id), f"{other.name} ({title_part}, {kingdom_part})"))
    return options


HIRE_GOLD_OFFER_RANGE: tuple[int, ...] = (1, 2, 3, 4)


def hire_target_options(state: GameState, leader_id: int) -> list[tuple[str, str]]:
    """Every co-located, genuinely free Hero as a ``(value, label)`` pair
    for Hire's own target dropdown -- rulebook [3.5]: "un Eroe libero e
    nella stessa provincia," confirmed as real, enforced checks at
    execution time (``turn/plan_dispatch.py _dispatch_hire()``'s own
    "hero already in service"/"not co-located" refusals, not prose).
    A King can never be hired either (that same function's own explicit
    "cannot hire a King" check). Deliberately excludes the separately-
    sourced ``AdvancedAbility.SPY_DOUBLE_AGENT`` carve-out (hiring an
    already-employed Spy without changing its real employer) -- not
    part of the pasted rulebook text, and surfacing it here would make
    an ordinary Hire dropdown look like it offers to steal another
    Kingdom's own Heroes. Pre-filtered to this composer's own start-of-
    turn snapshot, same convention already used for every other
    co-location-dependent dropdown.
    """

    leader = state.leaders.get(leader_id)
    if leader is None:
        return []
    options: list[tuple[str, str]] = []
    for other in _sorted_leaders(state):
        if other.leader_id == leader_id or other.location != leader.location:
            continue
        if other.kingdom_id is not None or other.is_king:
            continue
        options.append((str(other.leader_id), other.name))
    return options


def fire_target_options(state: GameState, leader_id: int) -> list[tuple[str, str]]:
    """Every Hero this leader could actually Fire, as a ``(value,
    label)`` pair for Fire's own target dropdown -- rulebook [3.7]: a
    King may Fire a Hero of his own Kingdom at any time, anywhere; an
    ordinary Hero needs co-location too (confirmed as real, enforced
    checks in ``turn/plan_dispatch.py _dispatch_fire()``, not prose),
    and can always Fire himself (included here for free -- a Hero's own
    entry always matches his own Kingdom and his own location). A King
    is never offered, as both a target (confirmed: ``_dispatch_fire()``
    now explicitly refuses "cannot fire a King," a 2026-11-01 fix
    sourced directly from the user, symmetric with Hire's own "can't
    Hire a King") and implicitly as a "self" option (a King Firing
    himself is meaningless and already excluded by that same refusal).
    Also excludes a different Kingdom's Hero entirely -- a second
    2026-11-01 fix, the user's own deliberate choice after being asked
    directly, even though the pasted [3.7] text itself names no such
    restriction (see ``_dispatch_fire()``'s own docstring addendum for
    the full reasoning) -- deliberately NOT surfacing the separately-
    sourced Grandfather of Assassins reinterpretation of a cross-
    Kingdom FI order (``turn/assassin_guild.py``), the same choice
    already made for Trail's own Spy Double-Agent carve-out and Hire's
    own Spy Double-Agent carve-out. Pre-filtered to this composer's own
    start-of-turn snapshot, same convention already used for every
    other co-location-dependent dropdown.
    """

    leader = state.leaders.get(leader_id)
    if leader is None:
        return []
    options: list[tuple[str, str]] = []
    for other in _sorted_leaders(state):
        if other.is_king or other.kingdom_id != leader.kingdom_id:
            continue
        if not leader.is_king and other.location != leader.location:
            continue
        label = f"Self ({other.name})" if other.leader_id == leader_id else other.name
        options.append((str(other.leader_id), label))
    return options


def cast_spell_options() -> list[tuple[int, str]]:
    """Every top-level Action-Cast spell (``CAST_ACTION_SPELLS``, 19
    members this round), as ``(value, display_name)`` pairs for Cast's
    own spell dropdown -- rulebook [3.10]: "Deve trattarsi di un
    Incantesimo d'Azione e non di un Incantesimo di Combattimento
    Individuale," confirmed structurally: ``turn/cast_execution.py
    execute_cast()``'s own exhaustive dispatch only ever has a real
    branch for these spells, any other falling to a generic "spell
    effect not modeled" result. Sorted by the spell's own real ordinal.

    None of ``SECRET_SPELL_ABILITY``'s own six skill-gated secret
    spells are ever members of ``CAST_ACTION_SPELLS`` (every one of
    them is Encounter-Plan-only, like ``Spell.GATE_ANGEL`` -- see that
    frozenset's own docstring), so unlike ``spell_options()`` this
    dropdown needs no per-leader skill filtering at all.
    """

    return [(int(spell), _spell_display_name(spell)) for spell in sorted(CAST_ACTION_SPELLS, key=int)]


def cast_character_target_options(state: GameState) -> list[tuple[str, str]]:
    """Every leader in the game as a ``(value, label)`` pair for the
    generic character-target Cast spells (``CAST_CHARACTER_TARGET_
    SPELLS`` -- Oratory, Clairvoyance, Phantasmal Armies, Mystic
    Winds). Deliberately NOT scoped to each spell's own further
    eligibility rules -- that per-spell research hasn't been done yet
    for any of these four, so this round offers every leader
    generically, same "any leader in the world" shape Trail's own
    target dropdown already uses, and leaves turn-processing time as
    the real arbiter. Resurrection, Charm, and Kill Enemy each get
    their own, considerably more elaborate target handling instead
    (``resurrection_target_options()``/``charm_target_options()``/
    ``kill_enemy_target_options()`` below).

    **2026-11-07 bug fix**: the active Valhalla visitor is still
    excluded, though -- unlike the rest of this docstring's own
    "per-spell research hasn't been done yet" disclaimer, this one
    exclusion isn't per-spell at all: ``turn/cast_execution.py``'s own
    generic cross-spell immunity ("any ``CHARACTER_TARGET_SPELLS``
    spell but Resurrection fizzles against the Valhalla visitor")
    already covers these exact four spells, and ``charm_target_
    options()``/``kill_enemy_target_options()`` already exclude the
    visitor from their own dropdowns for the identical, already-
    confirmed reason. Leaving it offered here let a GM compose Oratory/
    Clairvoyance/Phantasmal Armies/Mystic Winds against the visitor
    with no warning, only to have it silently do nothing at turn-
    processing time.
    """

    options: list[tuple[str, str]] = []
    for other in _sorted_leaders(state):
        if other.leader_id == VALHALLA_VISITOR_LEADER_ID and other.valhalla_active_turn is not None:
            continue
        kingdom = state.kingdoms.get(other.kingdom_id)
        kingdom_part = kingdom.name if kingdom is not None else "independent"
        title_part = "King" if other.is_king else "Hero"
        options.append((str(other.leader_id), f"{other.name} ({title_part}, {kingdom_part})"))
    return options



def resurrection_target_options(state: GameState, leader_id: int) -> list[tuple[str, str]]:
    """Every co-located, legal Resurrection target as a ``(value,
    label)`` pair -- rulebook [4.21.1] plus two further, already-
    implemented real cases this composer surfaces rather than leaving
    the GM to discover by trial and error (``turn/cast_execution.py
    _execute_resurrection()``'s own three branches, checked in this
    same order there):

    1. A living, comatose leader ("cure" -- [4.25.2]).
    2. A living Royal Heir not yet trained past the restoration
       threshold (``is_unfinalized_royal_heir()``) -- "get your old
       King back."
    3. A dead character (``GameState.dead_leaders``) -- ordinary
       revival into this Kingdom's own service.

    All three require co-location with the caster (confirmed: every
    branch's own "not co-located" check uses the exact same comparison).
    A dead leader's own id is never offered twice: if it's also
    currently occupied by a living Royal Heir (the historical King/Heir
    bridge), only the Royal-Heir option is listed -- the one that
    actually resolves at execution time, since ``_execute_resurrection``
    checks ``state.leaders`` before ``state.dead_leaders``.
    """

    leader = state.leaders.get(leader_id)
    if leader is None:
        return []
    options: list[tuple[str, str]] = []
    for other in _sorted_leaders(state):
        if other.location != leader.location:
            continue
        if other.is_comatose:
            options.append((str(other.leader_id), f"{other.name} (comatose -- cure)"))
        elif other.is_royal_heir and is_unfinalized_royal_heir(other):
            options.append((str(other.leader_id), f"{other.name} (Royal Heir -- restore the old King)"))
    for dead in sorted(state.dead_leaders.values(), key=lambda dead: dead.leader_id):
        if dead.location != leader.location or dead.leader_id in state.leaders:
            continue
        options.append((str(dead.leader_id), f"{dead.name} (dead -- revive)"))
    return options


def charm_target_options(state: GameState, leader_id: int) -> list[tuple[str, str]]:
    """Every legal Charm target as a ``(value, label)`` pair -- rulebook
    [3.10]/Charm's own text: co-located, commands no military unit, and
    never a King (``turn/cast_execution.py _execute_charm()``'s own
    three preconditions, confirmed real, enforced checks, not prose).
    2026-11-01, confirmed directly against the engine and the user's own
    follow-up choice: **any Kingdom is a valid source**, including an
    enemy's or another independent Hero's own Kingdom -- Charm's free-
    hire branch, unlike Hire, has no "must already be independent"
    requirement (confirmed by ``turn/cast_execution.py``'s own test
    suite: Charm can poach an already-employed Hero of a different
    Kingdom outright). The acting leader's own self is never offered --
    nothing in Charm's own rule text or execution models self-targeting.
    Also excludes the active Valhalla visitor (``execute_cast()``'s own
    generic cross-spell immunity for every character-targeted spell but
    Resurrection, same exclusion ``kill_enemy_target_options()`` already
    makes).

    When the acting leader is themself an Undead King
    (``LeaderState.alignment is Alignment.UNDEAD`` and ``is_king``), a
    successful Charm against any of these same targets *additionally*
    attempts ``_apply_undead_king_alignment_conversion()`` -- the
    deterministic, skill-gated "Seduzione" alignment-shift mechanic.
    This is a caster-conditional *effect*, not a separate target pool
    (the eligible-target set is identical either way) -- the composer
    surfaces it as a conditional note next to this same dropdown rather
    than a second one.
    """

    leader = state.leaders.get(leader_id)
    if leader is None:
        return []
    options: list[tuple[str, str]] = []
    for other in _sorted_leaders(state):
        if other.leader_id == leader_id:
            continue
        if other.location != leader.location or other.is_king:
            continue
        if state.armies_commanded_by(other.leader_id):
            continue
        if other.leader_id == VALHALLA_VISITOR_LEADER_ID and other.valhalla_active_turn is not None:
            continue
        kingdom = state.kingdoms.get(other.kingdom_id)
        kingdom_part = kingdom.name if kingdom is not None else "independent"
        options.append((str(other.leader_id), f"{other.name} (Hero, {kingdom_part})"))
    return options


def kill_enemy_target_options(state: GameState, leader_id: int) -> list[tuple[str, str]]:
    """Every legal Kill Enemy target as a ``(value, label)`` pair --
    rulebook [4.25.2]'s own co-location requirement, King immunity, and
    (2026-11-01, sourced directly from the user) Undead immunity --
    confirmed real, enforced checks in ``turn/cast_execution.py
    _execute_kill_enemy()``, not prose. Also excludes the active
    Valhalla visitor (``execute_cast()``'s own generic cross-spell
    immunity for every character-targeted spell but Resurrection) and
    the acting leader's own self (nothing in Kill Enemy's own rule text
    or execution models self-targeting, same reasoning as Charm's own
    dropdown).

    Deliberately NOT excluded, unlike Charm's own "commands no military
    unit" precondition: an army-leading Hero is a *legal* target here,
    only penalized (the roll is halved, never blocked outright) -- the
    halving condition (army-leading, or a Special-Place Feature in this
    province) is annotated in the label instead of filtering the
    target out, since it's a global modifier on the roll, not a
    per-target legality gate. Also deliberately NOT excluded: a target
    holding the True Cross/Anti-Necromancy Amulet, or whose Kingdom
    owns Hidden Tattoos -- both are post-roll wards (the cast can still
    succeed, be rolled for, and fail normally against them), not a
    "never offer this target at all" precondition, same convention as
    every other composer dropdown on this page never pre-filtering a
    merely-likely-to-fail target.
    """

    leader = state.leaders.get(leader_id)
    if leader is None:
        return []
    options: list[tuple[str, str]] = []
    for other in _sorted_leaders(state):
        if other.leader_id == leader_id:
            continue
        if other.location != leader.location or other.is_king or other.alignment is Alignment.UNDEAD:
            continue
        if other.leader_id == VALHALLA_VISITOR_LEADER_ID and other.valhalla_active_turn is not None:
            continue
        kingdom = state.kingdoms.get(other.kingdom_id)
        kingdom_part = kingdom.name if kingdom is not None else "independent"
        army_leading_note = ", leads an army -- halved chance" if state.armies_commanded_by(other.leader_id) else ""
        options.append((str(other.leader_id), f"{other.name} (Hero, {kingdom_part}{army_leading_note})"))
    return options


def tactic_options(
    slot: int, *, allow_give: bool = False, allow_fulfill_scout: bool = False, passive: bool = False
) -> list[tuple[int, str]]:
    """Every composable ``Maneuver`` for one Encounter Plan tactic slot,
    as ``(value, display_name)`` pairs -- ``Maneuver.TALK`` is only ever
    included for ``slot == 0`` *and* an active plan (``passive=False``,
    see below); every other slot gets the same ``_COMPOSABLE_MANEUVERS``
    list minus Talk. ``Maneuver.BEG``/``Maneuver.SQUEEZE`` are excluded
    for every slot and every caller -- neither is a real, GM-composable
    Encounter Plan tactic anywhere: Beg per this module's own docstring
    (user-sourced rationale), Squeeze per ``turn/encounter.py``'s own
    confirmed finding that it's only ever the Pascal source's own
    internal narration label for the Hand of Death spell's damage type,
    never a real player-orderable tactic.

    **2026-11-14 correction (user-confirmed, supersedes the 2026-10-31
    note this docstring used to cite)**: Talk/Give/Steal are each real
    only in an *active* Encounter Plan -- one generated after a Search
    (SE), Challenge (EN), Trail (TR) or Pursue (PU) order -- never in a
    leader's own standing, *passive* Special Encounter Plan [5.10]
    (``passive=True``). Fulfill/Scout are narrower still: real only
    after a Search (SE) order specifically, gated by their own
    ``allow_fulfill_scout`` flag -- not Challenge/Pursue/Trail's own
    active plans, and not the passive one either. Every caller now
    passes the flags matching its own context (Search sets both
    ``allow_give`` and ``allow_fulfill_scout``; Challenge/Pursue set
    only ``allow_give``; the Special Encounter Plan sets neither and
    passes ``passive=True``).
    """

    return [
        (int(maneuver), "Fire Arrow" if maneuver is Maneuver.SHOOT else maneuver.name.replace("_", " ").title())
        for maneuver in _COMPOSABLE_MANEUVERS
        if maneuver is not Maneuver.BEG
        and maneuver is not Maneuver.SQUEEZE
        and (maneuver not in (Maneuver.GIVE, Maneuver.STEAL) or allow_give)
        and (maneuver is not Maneuver.TALK or (slot == 0 and not passive))
        and (maneuver not in (Maneuver.FULFILL, Maneuver.SCOUT) or allow_fulfill_scout)
    ]


def compose_filename(game_label: str, turn_number: int, kingdom_id: int) -> str:
    """Same Game+Turn+Kingdom naming convention as the XK/SE downloads
    (``webapp/app.py``'s own ``turn_zero_download_xk()``/``turn_report_
    download()``) -- ``.K<kingdom_id>`` is also what ``Kingdom.
    kingdom_id`` itself parses the real Kingdom id back out of.
    """

    return f"AK{game_label}T{turn_number}.K{kingdom_id}"


@dataclass(slots=True)
class ComposedPhaseInput:
    """One phase's own raw form input, already validated to this shape
    by the caller -- see ``build_composed_kingdom()``.
    """

    action: ActionCode
    obj: int
    extra: list[int | str]
    # Only ever set for a composed Hire phase (``PlanPhase.nested_plan``,
    # see this module's own docstring's Hire section) -- ``None`` for
    # every other Action.
    nested_plan: "ActionPlan | None" = None


def _parse_action(raw: str) -> ActionCode:
    """**2026-11-07 bug fix**: now also rejects ``ActionCode.SUCC_
    TRAIL`` -- the one ``ActionCode`` member ``turn/plan_dispatch.py``'s
    own ``SUPPORTED_ACTIONS`` frozenset deliberately excludes "by
    design." The compose page's own Action dropdown (``app.py``'s
    ``turns_compose()``) no longer offers it either, but a direct,
    tampered POST could still name it -- previously this composed a
    perfectly normal-looking ``PlanPhase`` that only failed, opaquely,
    at real turn-processing time.
    """

    try:
        action = ActionCode(int(raw))
    except (TypeError, ValueError) as exc:
        raise InvalidComposedMovesError(f"{raw!r} is not a valid Action.") from exc
    if action not in SUPPORTED_ACTIONS:
        raise InvalidComposedMovesError(f"{action.name} isn't a composable Action.")
    return action


def _parse_int(raw: str, *, field_label: str) -> int:
    try:
        return int(raw)
    except (TypeError, ValueError) as exc:
        raise InvalidComposedMovesError(f"{field_label} must be a whole number, got {raw!r}.") from exc


def _parse_extra(raw: str) -> list[int]:
    stripped = raw.strip()
    if not stripped:
        return []
    values: list[int] = []
    for token in stripped.replace(",", " ").split():
        values.append(_parse_int(token, field_label="Extra"))
    return values


def _resolve_province_target_raw(form: dict[str, str], *, primary_field: str, number_field: str) -> str:
    """Move's own destination field (2026-11-15, user-requested),
    generalized (2026-11-16) for Defend's own target field too: reads
    the dropdown's own ``primary_field`` first, same as always; if
    that's empty, falls back to the sibling ``number_field`` free-text
    field, a hand-typed real province "#<N>" ordinal (``report/turn_
    report.py real_province_number()``'s own ``x*100 + y`` convention)
    -- for a destination this Kingdom knows the number of (e.g. from a
    report) but ``province_options()``'s own now-filtered dropdown
    (``known_to_kingdom()``) doesn't currently offer by name. Converts
    it into the exact same ``"x,y"`` string the dropdown itself would
    have posted, so the one real parser the caller still uses
    afterward does all the real validation either way. Returns ``""``
    (unresolved) if neither field is filled in, or the number isn't a
    plain non-negative whole number -- the caller's own existing
    empty-destination/real-province checks already cover both cases
    with a clear error.
    """

    dropdown_raw = form.get(primary_field, "")
    if dropdown_raw:
        return dropdown_raw
    number_raw = form.get(number_field, "").strip().lstrip("#")
    if not number_raw.isdigit():
        return ""
    x, y = divmod(int(number_raw), 100)
    return f"{x},{y}"


def _resolve_target_raw(form: dict[str, str], *, primary_field: str, number_field: str) -> str:
    """The same "dropdown first, hand-typed id second" fallback
    ``_resolve_province_target_raw()`` above uses, generalized for
    every other leader/item-targeted field this round adds a free-text
    override to (2026-11-15, user-requested: Hire's own target, and
    Cast's/Use Item's own Resurrection/Charm/Kill Enemy/generic
    character targets) -- unlike Move's own destination, none of these
    need any further decoding: the dropdown's own value is already the
    bare real id (a ``leader_id``), exactly the same shape a hand-typed
    one would be, so this is a plain "first non-empty wins" read with
    no conversion step at all. Returns ``""`` (unresolved) if neither
    field is filled in -- the real parser's own existing empty-field
    check already covers that with a clear error.
    """

    primary = form.get(primary_field, "")
    if primary:
        return primary
    return form.get(number_field, "")


def _parse_move_target(raw: str, *, board_width: int, phase_label: str, state: GameState) -> int:
    """**2026-11-07 bug fix**: now validates the posted destination
    against ``state.provinces`` -- this used to be one of only two
    target-dropdown-backed fields in the whole module (the other being
    Defend's own province field, left as-is: see ``_parse_defend_
    target()``'s own docstring for why its decoded value is currently
    never read anywhere and this gap is harmless there) with no
    existence check at all. Unlike Defend, an off-map or nonexistent
    destination here is a real crash, not a harmless no-op: ``turn/
    move_execution.py execute_move()`` raises an unhandled ``ValueError``
    ("no province data for ...") when ``state.provinces.get()`` comes
    back empty, caught only by ``plan_dispatch.py run_leader_plan()``'s
    own intentionally-broad per-phase exception handler -- so a
    tampered or off-map destination used to surface as an opaque
    internal exception recorded against that phase, instead of a
    clean compose-time rejection like every other target field gives.
    Also reused by Cast's/Use Item's own province-target spells
    (Scar Terrain/Illusory Terrain/etc., same ``CAST_PROVINCE_TARGET_
    SPELLS`` call sites), which inherit this fix automatically.
    """

    if not raw:
        raise InvalidComposedMovesError(f"{phase_label}: choose a Move destination.")
    x_str, _, y_str = raw.partition(",")
    x = _parse_int(x_str, field_label=f"{phase_label} Move destination")
    y = _parse_int(y_str, field_label=f"{phase_label} Move destination")
    target = encode_hex_number(HexCoord(x, y), board_width)
    if state.provinces.get(HexCoord(x, y)) is None:
        # Defense in depth: every dropdown-offered coordinate is a real
        # province, but a direct, tampered POST could still name an
        # off-map or otherwise nonexistent one.
        raise InvalidComposedMovesError(f"{phase_label}: choose a real province to Move to.")
    return target


def _parse_defend_target(raw: str, *, board_width: int, phase_label: str) -> int:
    """Reads a Defend phase's own ``defend_target_<leader_id>_<n>``
    field (``province_options()``'s own ``"x,y"`` dropdown value, same
    field shape as Move's) into Defend's real wire ``obj``.

    **Open question, not resolved by this round** (``turn/aspy_defend_
    decode.py``'s own docstring): the real Pascal ``Set_Defend`` writes
    this field via its own ``x*XMULT+y`` arithmetic, and nothing in the
    available source confirms whether that's the same numbering space
    as ``hex_numbering.py``'s own ``encode_hex_number()`` (Move's own,
    itself only an inferred guess, never confirmed against real Pascal
    source either) or something else entirely -- there is no sample
    ``.K1`` file with a real Defend phase to cross-check against. This
    composer still encodes via ``encode_hex_number()``, the same
    scheme Move's own dropdown already uses, for two reasons: (1) it's
    the only numbering scheme already built and tested in this project
    (reusing it is strictly less new-guessing than inventing a second,
    unverified one), and (2) it is, today, **harmless either way**:
    ``turn/defend_execution.py defend_coverage_area()``'s own
    documented reinterpretation never actually reads the decoded
    ``target_province`` int at all -- coverage is computed purely from
    the general's own *current* location, so no real behavior depends
    on which numbering this field round-trips through yet. If a future
    round ever implements the rulebook's own narrower "adjacent to both
    the named province and the current one" rule, this encoding choice
    will need to be revisited together with that work, not before.
    """

    if not raw:
        raise InvalidComposedMovesError(f"{phase_label}: choose a province to Defend.")
    x_str, _, y_str = raw.partition(",")
    x = _parse_int(x_str, field_label=f"{phase_label} Defend target")
    y = _parse_int(y_str, field_label=f"{phase_label} Defend target")
    return encode_hex_number(HexCoord(x, y), board_width)


def _parse_search_feature(raw: str, *, phase_label: str, state: GameState) -> int:
    """Reads a Search phase's own ``search_feature_<leader_id>_<n>``
    field into the real ``obj`` encoding (a ``Feature.feature_id``).

    **2026-11-06 bug fix**: this used to be the one target-dropdown
    field in this module with no ``state`` argument at all and
    therefore no existence check against ``state.features`` --
    every structurally analogous target parser (``_parse_recruit_
    target()`` below, ``_parse_trail_target()``, ``_parse_pursue_
    target()``, etc.) already validates the posted id against real
    game state with the same "Defense in depth" reasoning: ``feature_
    options()`` already filters its own dropdown to real feature ids,
    but a direct, tampered POST could still name any other integer.
    Previously this reached ``turn/search_execution.py`` unchecked and
    only failed there, late, as a silently-rejected "feature not
    found" order -- caught here instead, at compose time, with a real
    error message.
    """

    if not raw:
        raise InvalidComposedMovesError(f"{phase_label}: choose a Feature to Search.")
    feature_id = _parse_int(raw, field_label=f"{phase_label} Search feature")
    if state.features.get(feature_id) is None:
        raise InvalidComposedMovesError(f"{phase_label}: choose a real Feature to Search.")
    return feature_id


def _parse_hide_feature_target(
    form: dict[str, str], leader_id: int, n: int, *, phase_label: str, state: GameState, board_width: int, field_prefix: str = "cast"
) -> int:
    """Reads Hide Feature's own ``<field_prefix>_feature_target_
    <leader_id>_<n>`` field (``feature_options()``'s own dropdown,
    same "known to this Kingdom" filtering Search's own feature
    dropdown already uses) -- a real ``Feature.feature_id`` -- and
    resolves it to *that feature's own province coordinate*, still
    encoded via ``encode_hex_number()`` exactly like every other
    province-target spell's own ``obj`` (2026-11-16, user-requested):
    the real wire shape ``turn/cast_decode.py PROVINCE_TARGET_SPELLS``
    confirms for Hide Feature is still a province, never a feature id
    directly -- this only changes what the GM *picks by* here, not
    what gets encoded.

    ``field_prefix`` defaults to ``"cast"``; Use_MI's own Hide-Feature-
    wand phase (``Treasure.WAND_HIDE_FEATURE`` is real) passes
    ``"use_mi"``, same reasoning as ``_parse_resurrection_target()``'s
    own docstring.

    No co-location check here -- same reasoning as ``_parse_search_
    feature()``'s own docstring (an earlier phase this same turn could
    still Move this leader into the feature's own province before this
    phase dispatches). The real, stricter-than-adjacency requirement
    the user asked for ("se l'eroe o il Re... non si trova nella
    provincia... l'incantesimo non parte") is enforced for real at
    turn-processing time instead, in ``turn/cast_execution.py
    _execute_hide_feature()`` itself.
    """

    raw = form.get(f"{field_prefix}_feature_target_{leader_id}_{n}", "")
    if not raw:
        raise InvalidComposedMovesError(f"{phase_label}: choose a Feature to Hide.")
    feature_id = _parse_int(raw, field_label=f"{phase_label} Hide Feature target")
    feature = state.features.get(feature_id)
    if feature is None:
        # Defense in depth: every dropdown-offered id is a real
        # feature, but a direct, tampered POST could still name any
        # other integer.
        raise InvalidComposedMovesError(f"{phase_label}: choose a real Feature to Hide.")
    return encode_hex_number(feature.coord, board_width)


def _parse_recruit_target(raw: str, *, leader_id: int, phase_label: str, state: GameState) -> int:
    """Reads a Recruit phase's own ``recruit_target_<leader>_<n>`` field
    into the real ``obj`` encoding -- ``"self"``/empty resolves to the
    acting leader's own id, ``"garrison"`` to ``NO_LEADER_SENTINEL``,
    anything else to another co-located leader's own id (``recruit_
    target_options()``'s own dropdown value), matching ``turn/recruit_
    decode.py``'s own leader-id-or-255 encoding.

    **2026-11-06, two bug fixes**:

    (1) This used to be the one target-dropdown field in this module
    with no ``state`` argument at all and therefore no existence/
    co-location check -- every other such parser validates the posted
    id, with the same "Defense in depth" reasoning: ``recruit_target_
    options()`` already filters its own dropdown to leaders co-located
    with the acting leader, but a direct, tampered POST could still
    name any other, non-co-located, or nonexistent leader id.
    ``turn/recruit_execution.py execute_recruit()`` already degrades
    this gracefully to an unled/garrison-commanded unit rather than
    granting unauthorized command, but the GM deserves the same clean
    compose-time rejection every sibling target field already gives.

    (2) A real, co-located leader whose own id happens to equal
    ``NO_LEADER_SENTINEL`` (255) is wire-indistinguishable from
    ``"garrison"`` once encoded -- ``decode_recruit_phase()`` reads raw
    ``255`` as "no leader" unconditionally. Rejected via the shared
    ``_reject_no_leader_sentinel_collision()`` helper, the same real
    wire-format limit ``_parse_leave_target()`` guards against too.

    **2026-11-07 bug fix (3)**: the "self"/empty branch used to return
    ``leader_id`` straight through with no equivalent check -- a Hero
    whose own real ``leader_id`` happens to be 255 leaving the Recruit
    target dropdown on its default "Self" selection hit the exact same
    collision bug (2) above closes for an explicitly-named *other*
    leader, just never checked on this branch: the new unit silently
    went to the Garrison Commander instead of the Hero who recruited
    it. Both branches now go through the one shared helper.
    """

    if not raw or raw == "self":
        _reject_no_leader_sentinel_collision(leader_id, phase_label, "Recruit")
        return leader_id
    if raw == "garrison":
        return NO_LEADER_SENTINEL
    target_id = _parse_int(raw, field_label=f"{phase_label} Recruit target")
    _reject_no_leader_sentinel_collision(target_id, phase_label, "Recruit")
    leader = state.leaders.get(leader_id)
    target_leader = state.leaders.get(target_id)
    if leader is None or target_leader is None or target_leader.location != leader.location:
        # Defense in depth: every dropdown-offered value is already
        # filtered to a co-located leader by recruit_target_options(),
        # but a direct, tampered POST could still name any other id.
        raise InvalidComposedMovesError(
            f"{phase_label}: choose a Recruit target that's co-located with this leader (or Self/Garrison)."
        )
    return target_id


def _parse_recruit_types(
    form: dict[str, str], leader_id: int, n: int, *, phase_label: str, state: GameState
) -> list[int]:
    """Reads this Recruit phase's own ``recruit_type_<leader_id>_<n>_
    <slot>`` fields (``slot`` in ``0..RECRUIT_TYPE_SLOT_COUNT-1``) into
    a list of real ``ArmyType`` ordinals -- the same no-gaps convention
    Search's own tactic slots already use (an empty slot stops the
    list there; a later non-empty slot after one is rejected). At least
    one type must be chosen -- a Recruit order with nothing to recruit
    isn't a real order.

    **2026-11-07 bug fix**: the "Defense in depth" check here used to
    only verify the posted ordinal was *some* real ``ArmyType``,
    against the full enum -- weaker than ``recruit_type_options()``'s
    own real offered set, which excludes the 8 ordinals with no
    ``ARMY_TABLE`` cost entry and any type incompatible with this
    leader's own current province's race. A tampered POST naming one
    of those excluded-but-real ordinals (e.g. Vampires) used to pass
    this check and only be rejected later, at turn-processing time, by
    ``turn/recruit.py resolve_recruit()``'s own ``IncompatibleRaceError``
    -- cleanly, not a crash, but later and less clearly than every
    other target field's own compose-time rejection.
    """

    leader = state.leaders.get(leader_id)
    province = state.provinces.get(leader.location) if leader is not None else None

    ordinals: list[int] = []
    stopped_at: int | None = None
    for slot in range(RECRUIT_TYPE_SLOT_COUNT):
        raw = form.get(f"recruit_type_{leader_id}_{n}_{slot}", "")
        if not raw:
            if stopped_at is None:
                stopped_at = slot
            continue
        if stopped_at is not None:
            raise InvalidComposedMovesError(
                f"{phase_label}: recruit type slot {slot + 1} follows empty slot {stopped_at + 1} -- "
                "fill the Recruit order without gaps."
            )
        ordinal = _parse_int(raw, field_label=f"{phase_label} Recruit type {slot + 1}")
        army_type = ARMY_TYPE_BY_ORDINAL.get(ordinal)
        if (
            army_type is None
            or province is None
            or army_type not in ARMY_TABLE
            or not is_army_type_compatible_with_race(army_type, province.race)
        ):
            # Defense in depth: every dropdown-offered ordinal is one
            # recruit_type_options() already filtered to a real,
            # costed, race-compatible type at this leader's own
            # current location, but a direct, tampered POST could
            # still name any other real ArmyType ordinal.
            raise InvalidComposedMovesError(f"{phase_label}: recruit type slot {slot + 1} isn't a known army type.")
        ordinals.append(ordinal)
    if not ordinals:
        raise InvalidComposedMovesError(f"{phase_label}: choose at least one army type to Recruit.")
    return ordinals


def _reject_single_army_sentinel_collision(army_ids: list[int], phase_label: str, order_label: str) -> None:
    """**2026-11-06 bug fix.** A single real army whose own ``army_id``
    happens to equal ``ALL_ARMIES_SENTINEL`` (255) is wire-
    indistinguishable from the dedicated "ALL" pseudo-option once
    encoded: ``decode_army_list_phase()`` strips the trailing ``-1``
    and compares what's left against ``[ALL_ARMIES_SENTINEL]`` to mean
    "every army this leader commands," with no way to tell that apart
    from a GM who really meant just that one army. ``GameState.new_
    army_id()`` is an uncapped running counter, so army id 255 is a
    perfectly real, reachable id in a long-running game -- not merely
    theoretical. Shared by ``_parse_disband_targets()``/``_parse_leave_
    army_targets()``/``_parse_pick_up_targets()`` below, called right
    after each one's own specific-list loop, before its own "at least
    one target" check (an empty list can't collide).
    """

    if army_ids == [ALL_ARMIES_SENTINEL]:
        raise InvalidComposedMovesError(
            f"{phase_label}: army #{ALL_ARMIES_SENTINEL} can't be the only {order_label} target in this order -- "
            "it's indistinguishable on the wire from the 'ALL' option. Add a second army to this order, or use "
            "'ALL' if that's really the intent."
        )


def _reject_no_leader_sentinel_collision(target_id: int, phase_label: str, order_label: str) -> None:
    """**2026-11-07 bug fix.** A real leader whose own ``leader_id``
    happens to equal ``NO_LEADER_SENTINEL`` (255) is wire-
    indistinguishable from "no leader" (Garrison Commander, or Recruit's
    own "self" default) once encoded: both ``decode_army_list_phase()``
    and ``decode_recruit_phase()`` read a raw ``255`` as ``None``
    unconditionally. ``GameState.new_leader_id()`` is an uncapped
    running counter, so leader id 255 is a perfectly real, reachable id
    in a long-running game -- not merely theoretical, the same reasoning
    ``_reject_single_army_sentinel_collision()`` right above already
    gives for the analogous army-id case.

    Unified here (2026-11-07) after the two Leave/Recruit guards that
    first closed this gap (2026-11-06) were each a separate, hand-
    written inline check -- unlike the army case above, which already
    had one shared helper from day one. Called for every leader id a
    Recruit/Leave order would otherwise compose as its own real target
    (including Recruit's own "self" default, which collides exactly
    the same way when the acting leader's own id happens to be 255 --
    the one case the original two inline guards didn't cover, since
    neither ever checked its own order's self/default branch).
    """

    if target_id == NO_LEADER_SENTINEL:
        raise InvalidComposedMovesError(
            f"{phase_label}: leader #{NO_LEADER_SENTINEL} can't be named as a {order_label} target -- "
            "it's indistinguishable on the wire from the Garrison Commander."
        )


def _parse_disband_targets(
    form: dict[str, str], leader_id: int, n: int, *, phase_label: str, state: GameState
) -> list[int]:
    """Reads this Disband phase's own ``disband_target_<leader_id>_<n>_
    <slot>`` fields (``slot`` in ``0..DISBAND_SLOT_COUNT-1``) into the
    real Disband army-id list -- the same no-gaps convention Search/
    Recruit's own slots already use. ``DISBAND_ALL_VALUE`` in slot 0
    collapses the whole order to the lone ``ALL_ARMIES_SENTINEL`` and
    must be the only thing filled in (see this module's own docstring
    for why a real order is either a specific list or the ALL
    sentinel, never both). At least one target must be chosen.

    **2026-11-06 bug fix**: see ``_reject_single_army_sentinel_
    collision()`` -- a lone army #255 in the specific-list branch used
    to silently compose identically to "ALL."
    """

    leader = state.leaders.get(leader_id)
    if form.get(f"disband_target_{leader_id}_{n}_0", "") == DISBAND_ALL_VALUE:
        for slot in range(1, DISBAND_SLOT_COUNT):
            if form.get(f"disband_target_{leader_id}_{n}_{slot}", ""):
                raise InvalidComposedMovesError(
                    f"{phase_label}: 'ALL' can't be combined with another army in the same order."
                )
        return [ALL_ARMIES_SENTINEL]

    army_ids: list[int] = []
    stopped_at: int | None = None
    for slot in range(DISBAND_SLOT_COUNT):
        raw = form.get(f"disband_target_{leader_id}_{n}_{slot}", "")
        if not raw:
            if stopped_at is None:
                stopped_at = slot
            continue
        if stopped_at is not None:
            raise InvalidComposedMovesError(
                f"{phase_label}: disband target slot {slot + 1} follows empty slot {stopped_at + 1} -- "
                "fill the Disband order without gaps."
            )
        army_id = _parse_int(raw, field_label=f"{phase_label} Disband target {slot + 1}")
        army = state.armies.get(army_id)
        if (
            army is None
            or leader is None
            or army.kingdom_id != leader.kingdom_id
            or (not leader.is_king and army.location != leader.location)
        ):
            # Defense in depth: every dropdown-offered army_id is one
            # disband_target_options() already filtered to exactly what
            # this leader could Disband, but a direct, tampered POST
            # could still name any other army id.
            raise InvalidComposedMovesError(
                f"{phase_label}: disband target slot {slot + 1} isn't an army this leader can Disband."
            )
        army_ids.append(army_id)
    _reject_single_army_sentinel_collision(army_ids, phase_label, "Disband")
    if not army_ids:
        raise InvalidComposedMovesError(f"{phase_label}: choose at least one army to Disband (or 'ALL').")
    return army_ids


def _parse_leave_target(form: dict[str, str], leader_id: int, n: int, *, phase_label: str, state: GameState) -> int:
    """Reads a Leave phase's own ``leave_target_<leader_id>_<n>`` field
    into the real ``obj`` encoding -- ``LEAVE_GARRISON_VALUE``/empty
    resolves to ``NO_LEADER_SENTINEL`` ("GC"), anything else to another
    leader's own id (``leave_target_options()``'s own dropdown value),
    matching ``turn/army_list_decode.py``'s own leader-id-or-255
    encoding. Rejects a target leader who isn't of this leader's own
    or an allied Kingdom -- defense in depth: every dropdown-offered
    value is already filtered this way, but a direct, tampered POST
    could still name a hostile/unrelated leader.

    **2026-11-06, two bug fixes**:

    (1) Never rejected the acting leader targeting himself --
    ``state.is_allied(leader.kingdom_id, leader.kingdom_id)`` is
    trivially ``True``, so a self-target silently passed this check,
    even though ``leave_target_options()`` itself already excludes the
    acting leader's own id from the dropdown (``other.leader_id !=
    leader_id``) and every structurally analogous target parser in
    this module (Trail/Challenge/Hire/Charm/Kill Enemy) explicitly
    rejects self-targeting. At runtime this used to resolve to a
    harmless no-op (the army stays commanded by the same leader), but
    it's the one target parser that was missing the guard its own
    siblings all enforce.

    (2) A real, allied leader whose own id happens to equal ``NO_
    LEADER_SENTINEL`` (255) is wire-indistinguishable from
    ``LEAVE_GARRISON_VALUE`` once encoded -- ``decode_army_list_
    phase()`` reads raw ``255`` as "no leader" (Garrison Commander)
    unconditionally, silently dropping both the named Hero and the
    Kingdom-transfer-to-an-ally effect the GM may have been relying on.
    Rejected via the shared ``_reject_no_leader_sentinel_collision()``
    helper, the same real wire-format limit ``_parse_recruit_target()``
    guards against too.
    """

    raw = form.get(f"leave_target_{leader_id}_{n}", "")
    if not raw or raw == LEAVE_GARRISON_VALUE:
        return NO_LEADER_SENTINEL
    target_id = _parse_int(raw, field_label=f"{phase_label} Leave target")
    if target_id == leader_id:
        raise InvalidComposedMovesError(f"{phase_label}: a leader can't Leave an army to himself.")
    _reject_no_leader_sentinel_collision(target_id, phase_label, "Leave")
    leader = state.leaders.get(leader_id)
    target_leader = state.leaders.get(target_id)
    if leader is None or target_leader is None or not state.is_allied(leader.kingdom_id, target_leader.kingdom_id):
        raise InvalidComposedMovesError(
            f"{phase_label}: choose a Leave target that's this leader's own Kingdom or an ally's."
        )
    return target_id


def _parse_leave_army_targets(
    form: dict[str, str], leader_id: int, n: int, *, phase_label: str, state: GameState
) -> list[int]:
    """Reads this Leave phase's own ``leave_army_<leader_id>_<n>_<slot>``
    fields (``slot`` in ``0..LEAVE_SLOT_COUNT-1``) into the real Leave
    army-id list -- the same no-gaps convention and ``LEAVE_ALL_VALUE``
    mutual-exclusivity shape ``_parse_disband_targets()`` already uses
    for ``DISBAND_ALL_VALUE``. At least one target must be chosen.

    **2026-11-06 bug fix**: see ``_reject_single_army_sentinel_
    collision()`` -- a lone army #255 in the specific-list branch used
    to silently compose identically to "ALL."
    """

    leader = state.leaders.get(leader_id)
    if form.get(f"leave_army_{leader_id}_{n}_0", "") == LEAVE_ALL_VALUE:
        for slot in range(1, LEAVE_SLOT_COUNT):
            if form.get(f"leave_army_{leader_id}_{n}_{slot}", ""):
                raise InvalidComposedMovesError(
                    f"{phase_label}: 'ALL' can't be combined with another army in the same order."
                )
        return [ALL_ARMIES_SENTINEL]

    army_ids: list[int] = []
    stopped_at: int | None = None
    for slot in range(LEAVE_SLOT_COUNT):
        raw = form.get(f"leave_army_{leader_id}_{n}_{slot}", "")
        if not raw:
            if stopped_at is None:
                stopped_at = slot
            continue
        if stopped_at is not None:
            raise InvalidComposedMovesError(
                f"{phase_label}: leave army slot {slot + 1} follows empty slot {stopped_at + 1} -- "
                "fill the Leave order without gaps."
            )
        army_id = _parse_int(raw, field_label=f"{phase_label} Leave army {slot + 1}")
        army = state.armies.get(army_id)
        if (
            army is None
            or leader is None
            or army.kingdom_id != leader.kingdom_id
            or (
                army.commanded_by != leader_id
                and not (army.commanded_by is None and army.location == leader.location)
            )
        ):
            # Defense in depth: every dropdown-offered army_id is one
            # leave_army_target_options() already filtered to exactly
            # what this leader could Leave, but a direct, tampered POST
            # could still name any other army id.
            raise InvalidComposedMovesError(
                f"{phase_label}: leave army slot {slot + 1} isn't an army this leader can Leave."
            )
        army_ids.append(army_id)
    _reject_single_army_sentinel_collision(army_ids, phase_label, "Leave")
    if not army_ids:
        raise InvalidComposedMovesError(f"{phase_label}: choose at least one army to Leave (or 'ALL').")
    return army_ids


def _parse_pick_up_targets(
    form: dict[str, str], leader_id: int, n: int, *, phase_label: str, state: GameState
) -> list[int]:
    """Reads this Pick Up phase's own ``pick_up_target_<leader_id>_<n>_
    <slot>`` fields (``slot`` in ``0..PICK_UP_SLOT_COUNT-1``) into the
    real Pick Up army-id list -- the same no-gaps convention and
    ``PICK_UP_ALL_VALUE`` mutual-exclusivity shape ``_parse_disband_
    targets()``/``_parse_leave_army_targets()`` already use. At least
    one target must be chosen.

    **2026-11-06 bug fix**: see ``_reject_single_army_sentinel_
    collision()`` -- a lone army #255 in the specific-list branch used
    to silently compose identically to "ALL."
    """

    leader = state.leaders.get(leader_id)
    if form.get(f"pick_up_target_{leader_id}_{n}_0", "") == PICK_UP_ALL_VALUE:
        for slot in range(1, PICK_UP_SLOT_COUNT):
            if form.get(f"pick_up_target_{leader_id}_{n}_{slot}", ""):
                raise InvalidComposedMovesError(
                    f"{phase_label}: 'ALL' can't be combined with another army in the same order."
                )
        return [ALL_ARMIES_SENTINEL]

    army_ids: list[int] = []
    stopped_at: int | None = None
    for slot in range(PICK_UP_SLOT_COUNT):
        raw = form.get(f"pick_up_target_{leader_id}_{n}_{slot}", "")
        if not raw:
            if stopped_at is None:
                stopped_at = slot
            continue
        if stopped_at is not None:
            raise InvalidComposedMovesError(
                f"{phase_label}: pick up target slot {slot + 1} follows empty slot {stopped_at + 1} -- "
                "fill the Pick Up order without gaps."
            )
        army_id = _parse_int(raw, field_label=f"{phase_label} Pick Up target {slot + 1}")
        army = state.armies.get(army_id)
        if (
            army is None
            or leader is None
            or army.location != leader.location
            or army.kingdom_id != leader.kingdom_id
            or (army.recruited_this_turn and not army.is_mercenary)
        ):
            # Defense in depth: every dropdown-offered army_id is one
            # pick_up_army_target_options() already filtered to exactly
            # what this leader could Pick Up, but a direct, tampered
            # POST could still name any other army id.
            raise InvalidComposedMovesError(
                f"{phase_label}: pick up target slot {slot + 1} isn't an army this leader can Pick Up."
            )
        army_ids.append(army_id)
    _reject_single_army_sentinel_collision(army_ids, phase_label, "Pick Up")
    if not army_ids:
        raise InvalidComposedMovesError(f"{phase_label}: choose at least one army to Pick Up (or 'ALL').")
    return army_ids


def _parse_trade_recipient(form: dict[str, str], leader_id: int, n: int, *, phase_label: str, state: GameState) -> int:
    """Reads a Give phase's own ``trade_recipient_<leader_id>_<n>``
    field into the real recipient leader id -- the wire encoding is
    already a bare leader id (``trade_recipient_options()``'s own
    dropdown value), so no sentinel decoding is needed, unlike Leave's
    own target field.

    **2026-11-07 bug fix**: this used to only check that the posted id
    resolved to *some* real leader, unlike every other target field in
    this module -- see ``_trade_recipient_is_eligible()``'s own
    docstring for the full gap this closes (co-location/Curator-self/
    blackmail-king re-validation, "defense in depth" against a
    tampered or stale POST).
    """

    raw = form.get(f"trade_recipient_{leader_id}_{n}", "")
    if not raw:
        raise InvalidComposedMovesError(f"{phase_label}: choose a Give recipient.")
    target_id = _parse_int(raw, field_label=f"{phase_label} Give recipient")
    leader = state.leaders.get(leader_id)
    if leader is None or not _trade_recipient_is_eligible(state, leader, target_id):
        raise InvalidComposedMovesError(f"{phase_label}: choose a Give recipient.")
    return target_id


def _parse_trade_gift(
    form: dict[str, str], leader_id: int, n: int, *, phase_label: str, state: GameState, recipient_id: int
) -> int:
    """Reads a Give phase's own ``trade_gift_<leader_id>_<n>`` dropdown
    (an owned item id, or ``TRADE_GOLD_VALUE``) and, for the gold case,
    its own ``trade_gold_<leader_id>_<n>`` free-text amount field, into
    the real ``obj`` encoding -- an item id the giver actually owns, or
    a positive gold amount. See ``trade_gift_options()``'s own
    docstring for why an owned item is never offered if it's a
    Valhalla visitor's own fixed item. ``recipient_id`` is the already-
    parsed ``_parse_trade_recipient()`` result, needed here only to
    enforce the gold path's own different-Kingdom requirement
    (``turn/trade_execution.py execute_give()``'s own 2026-10-29
    addendum) -- the item path has no such restriction.

    **2026-11-07 bug fix**: the gold branch now also rejects an amount
    that collides with an item id this same giver owns. ``obj`` is one
    shared, overloaded field for both the item and gold paths --
    ``turn/trade_execution.py execute_give()`` disambiguates it by
    checking item ownership *first* ("si passa l'oggetto e non
    l'oro"), a real rulebook warning (RULES.AK [3.18]: "don't Give an
    amount of gold that equals a magic item I.D. number carried by the
    King"). Previously a GM composing e.g. "Give 12 gold" while owning
    item #12 got no warning here at all -- the order would silently
    transfer the item instead of the gold at turn-processing time.

    **2026-11-16 (user-requested)**: the dropdown's own ``TRADE_ITEM_
    NUMBER_VALUE`` pseudo-option reveals a sibling ``trade_gift_number_
    <leader_id>_<n>`` free-text field (e.g. "#21") -- the same reveal-
    on-selection shape ``TRADE_GOLD_VALUE`` already uses for its own
    gold-amount field -- for an item this leader owns but that
    ``trade_gift_options()``'s own start-of-turn snapshot doesn't yet
    list (looted earlier the very same turn). Every ownership
    precondition below still applies identically either way: this is
    just a second way to name the same item id, not a bypass.
    """

    raw = form.get(f"trade_gift_{leader_id}_{n}", "")
    if raw == TRADE_ITEM_NUMBER_VALUE:
        raw = form.get(f"trade_gift_number_{leader_id}_{n}", "")
    if not raw or raw == TRADE_GOLD_VALUE:
        gold_raw = form.get(f"trade_gold_{leader_id}_{n}", "")
        if not gold_raw:
            raise InvalidComposedMovesError(f"{phase_label}: enter a gold amount to Give.")
        amount = _parse_int(gold_raw, field_label=f"{phase_label} Give gold amount")
        if amount <= 0:
            raise InvalidComposedMovesError(f"{phase_label}: Give gold amount must be a positive number.")
        owned_item = state.items.get(amount)
        if owned_item is not None and owned_item.owner_leader_id == leader_id:
            raise InvalidComposedMovesError(
                f"{phase_label}: can't Give {amount} gold -- this leader owns item #{amount}, and the engine "
                "would transfer the item instead of the gold (RULES.AK [3.18]). Choose a different amount."
            )
        leader = state.leaders.get(leader_id)
        recipient = state.leaders.get(recipient_id)
        if (
            leader is not None
            and recipient is not None
            and (recipient.kingdom_id is None or recipient.kingdom_id == leader.kingdom_id)
        ):
            raise InvalidComposedMovesError(
                f"{phase_label}: a gold gift's recipient must belong to a different Kingdom."
            )
        return amount

    item_id = _parse_int(raw, field_label=f"{phase_label} Give item")
    item = state.items.get(item_id)
    leader = state.leaders.get(leader_id)
    if item is None or item.owner_leader_id != leader_id:
        # Defense in depth: every dropdown-offered item id is one this
        # leader actually owns, but a direct, tampered POST could still
        # name any other item id.
        raise InvalidComposedMovesError(f"{phase_label}: choose an item this leader owns to Give.")
    if leader is not None and leader.valhalla_fixed_item_id == item_id:
        raise InvalidComposedMovesError(
            f"{phase_label}: the Valhalla visitor's own fixed item can't be given away."
        )
    return item_id


def _parse_practice_ability(raw: str, *, phase_label: str) -> int:
    """Reads a Practice phase's own ``practice_ability_<leader_id>_<n>``
    dropdown into the real ``obj`` encoding -- just the ``Ability``
    ordinal, matching ``practice_ability_options()``'s own dropdown
    value (and, in turn, ``turn/practice_decode.py``'s own ``Ability(phase.obj)``
    decode).
    """

    if not raw:
        raise InvalidComposedMovesError(f"{phase_label}: choose a Talent to Practice.")
    ability_ordinal = _parse_int(raw, field_label=f"{phase_label} Practice ability")
    try:
        Ability(ability_ordinal)
    except ValueError:
        # Defense in depth: every dropdown-offered value is a real
        # Ability ordinal, but a direct, tampered POST could still name
        # one outside the enum's own range.
        raise InvalidComposedMovesError(f"{phase_label}: choose a Talent to Practice.") from None
    return ability_ordinal


def _parse_trail_target(form: dict[str, str], leader_id: int, n: int, *, phase_label: str, state: GameState) -> int:
    """Reads a Trail phase's own ``trail_target_<leader_id>_<n>`` field
    into the real target ``leader_id`` -- the wire encoding is already a
    bare leader id (``trail_target_options()``'s own dropdown value), so
    no sentinel decoding is needed. Also enforces, at compose time
    rather than only at turn-processing time, rulebook [3.17]'s own "a
    character leading an army may not be ordered to Trail" -- the same
    check ``turn/trail_execution.py execute_trail()`` itself makes
    (``GameState.armies_commanded_by()``), restricting the *trailer*
    only -- the target may freely command an army.

    Falls back to the sibling ``trail_target_number_<leader_id>_<n>``
    free-text field (2026-11-16, user-requested) when the dropdown
    itself is empty -- ``_resolve_target_raw()``'s own generic shape.
    Every precondition above still applies identically either way.
    """

    raw = _resolve_target_raw(
        form, primary_field=f"trail_target_{leader_id}_{n}", number_field=f"trail_target_number_{leader_id}_{n}"
    )
    if not raw:
        raise InvalidComposedMovesError(f"{phase_label}: choose a Trail target.")
    target_id = _parse_int(raw, field_label=f"{phase_label} Trail target")
    if target_id == leader_id or state.leaders.get(target_id) is None:
        # Defense in depth: every dropdown-offered id is a real, other
        # leader, but a direct, tampered POST could still name the
        # acting leader himself or one that doesn't exist.
        raise InvalidComposedMovesError(f"{phase_label}: choose a Trail target.")
    if state.armies_commanded_by(leader_id):
        raise InvalidComposedMovesError(
            f"{phase_label}: a character leading an army may not be ordered to Trail."
        )
    return target_id


def _parse_pursue_target(form: dict[str, str], leader_id: int, n: int, *, phase_label: str, state: GameState) -> int:
    """Reads a Pursue phase's own ``pursue_target_<leader_id>_<n>`` field
    into the real target ``leader_id`` -- the wire encoding is already a
    bare leader id (``pursue_target_options()``'s own dropdown value),
    so no sentinel decoding is needed.

    Directed Pursue (any *other* leader as target) has no unconditional
    "an army-leading character may never be ordered to X" ban on the
    pursuer, unlike Trail -- [3.16]'s own army-leading-mismatch rule is
    a soft, execution-time "order ignored" outcome (``execute_pursue()``
    itself), not an invalid-order precondition, and can depend on either
    side's army status at the moment this phase actually runs (which
    could change by then) -- so this composer doesn't pre-reject on it.

    **Self-targeting (2026-11-01) composes a "Characters On Patrol"
    declaration instead** -- unlike directed Pursue, [3.16]'s own
    Patrol text states its army precondition unconditionally on the
    acting leader alone ("viene fatto da un Eroe senza armate"), the
    same shape as Trail's own unconditional ban, not Pursue's own soft
    mismatch -- so this one *is* enforced here, at compose time, same
    as ``_parse_trail_target()``'s own precedent.

    Falls back to the sibling ``pursue_target_number_<leader_id>_<n>``
    free-text field (2026-11-16, user-requested) when the dropdown
    itself is empty -- ``_resolve_target_raw()``'s own generic shape.
    """

    raw = _resolve_target_raw(
        form, primary_field=f"pursue_target_{leader_id}_{n}", number_field=f"pursue_target_number_{leader_id}_{n}"
    )
    if not raw:
        raise InvalidComposedMovesError(f"{phase_label}: choose a Pursue target.")
    target_id = _parse_int(raw, field_label=f"{phase_label} Pursue target")
    if state.leaders.get(target_id) is None:
        # Defense in depth: every dropdown-offered id is a real leader,
        # but a direct, tampered POST could still name one that doesn't
        # exist.
        raise InvalidComposedMovesError(f"{phase_label}: choose a Pursue target.")
    if target_id == leader_id and state.armies_commanded_by(leader_id):
        raise InvalidComposedMovesError(
            f"{phase_label}: a character leading an army may not be ordered to Patrol."
        )
    return target_id


def _parse_challenge_target(form: dict[str, str], leader_id: int, n: int, *, phase_label: str, state: GameState) -> int:
    """Reads a Challenge phase's own ``challenge_target_<leader_id>_<n>``
    field into the real target ``leader_id`` -- the wire encoding is
    already a bare leader id (``challenge_target_options()``'s own
    dropdown value), so no sentinel decoding is needed. Also enforces,
    at compose time rather than only at turn-processing time, rulebook
    [3.12]'s own "nella stessa provincia" co-location requirement -- the
    same check ``turn/challenge_execution.py execute_challenge()``
    itself makes.
    """

    raw = form.get(f"challenge_target_{leader_id}_{n}", "")
    if not raw:
        raise InvalidComposedMovesError(f"{phase_label}: choose a Challenge target.")
    target_id = _parse_int(raw, field_label=f"{phase_label} Challenge target")
    leader = state.leaders.get(leader_id)
    target = state.leaders.get(target_id)
    if target_id == leader_id or target is None or leader is None or target.location != leader.location:
        # Defense in depth: every dropdown-offered id is a real, other,
        # co-located leader, but a direct, tampered POST could still
        # name the acting leader himself, one that doesn't exist, or
        # one no longer co-located.
        raise InvalidComposedMovesError(f"{phase_label}: choose a Challenge target.")
    return target_id


def _parse_hire_target(form: dict[str, str], leader_id: int, n: int, *, phase_label: str, state: GameState) -> int:
    """Reads a Hire phase's own ``hire_target_<leader_id>_<n>`` field
    into the real target Hero's ``leader_id`` -- the wire encoding is
    already a bare leader id (``hire_target_options()``'s own dropdown
    value), so no sentinel decoding is needed. Also enforces, at
    compose time rather than only at turn-processing time, rulebook
    [3.5]'s own co-location + "free Hero" + "never a King" requirements
    -- the same checks ``turn/plan_dispatch.py _dispatch_hire()`` itself
    makes.

    Falls back to the sibling ``hire_target_number_<leader_id>_<n>``
    free-text field (2026-11-15, user-requested: "posso provare a
    reclutare eroi appena sconfitti in una provincia neutrale") when the
    dropdown itself is empty -- ``_resolve_target_raw()``'s own generic
    "dropdown first, hand-typed id second" shape. Every precondition
    above still applies identically either way.
    """

    raw = _resolve_target_raw(
        form, primary_field=f"hire_target_{leader_id}_{n}", number_field=f"hire_target_number_{leader_id}_{n}"
    )
    if not raw:
        raise InvalidComposedMovesError(f"{phase_label}: choose a Hero to Hire.")
    target_id = _parse_int(raw, field_label=f"{phase_label} Hire target")
    leader = state.leaders.get(leader_id)
    target = state.leaders.get(target_id)
    if (
        target_id == leader_id
        or target is None
        or leader is None
        or target.location != leader.location
        or target.kingdom_id is not None
        or target.is_king
    ):
        # Defense in depth: every dropdown-offered id is a real,
        # co-located, genuinely free non-King Hero, but a direct,
        # tampered POST could still name anything else.
        raise InvalidComposedMovesError(f"{phase_label}: choose a Hero to Hire.")
    return target_id


def _parse_hire_gold_offer(raw: str, *, phase_label: str) -> int:
    """Reads a Hire phase's own ``hire_gold_<leader_id>_<n>`` dropdown
    into the real gold-offer amount -- rulebook [3.5]'s own 1-4 range,
    which (confirmed directly in ``turn/hire_fire_decode.py``/``turn/
    plan_dispatch.py``) has zero hard engine gate anywhere: only this
    composer actually enforces it.
    """

    if not raw:
        raise InvalidComposedMovesError(f"{phase_label}: choose a gold offer (1-4) for Hire.")
    amount = _parse_int(raw, field_label=f"{phase_label} Hire gold offer")
    if amount not in HIRE_GOLD_OFFER_RANGE:
        # Defense in depth: every dropdown-offered value is 1-4, but a
        # direct, tampered POST could still name anything else.
        raise InvalidComposedMovesError(f"{phase_label}: Hire's own gold offer must be 1-4, got {amount}.")
    return amount


def nested_hero_option_bundle(state: GameState, hero_id: int) -> dict:
    """Every leader-scoped dropdown's own full set of ``(value, label)``
    choices for ``hero_id``, bundled as one JSON-ready ``dict`` for the
    ``/games/<slug>/turns/<n>/compose/hero_options`` endpoint.

    **Why this exists at all**: a newly-(re)joined character's own
    identity (who got Hired, Charmed, or Resurrected) is only known
    once the GM actually picks a target in that *same* form -- so the
    normal, server-rendered-at-page-load dropdowns this module gives
    every real roster leader (``feature_choices_by_leader``, etc.)
    can't be precomputed for "whoever ends up triggering this nesting"
    the same way. Instead, the nested-plan editor's own leader-scoped
    cells start empty and are populated client-side, via a fetch to
    this bundle, the moment the GM picks a real target in the
    triggering Hire/Charm/Resurrection dropdown (``updateNestedPlan()``
    in the template). Every *globally*-scoped dropdown (Move's
    ``province_choices``, Cast's generic character/item targets) needs
    no such fetch at all -- those render directly, identically, inside
    the nested editor too, the same real list every other row already
    uses.

    **A Resurrection candidate may not be in ``state.leaders`` at all**
    (a dead Hero, or one merely comatose stays in ``state.leaders`` and
    needs no special handling). For a genuinely dead one, every
    leader-scoped ``*_options()`` function below already guards with
    its own ``if leader_id not in state.leaders: return []`` (confirmed
    directly, e.g. ``trail_target_options()``'s own docstring) -- so,
    rather than accept that silent, misleadingly-empty degradation,
    this function temporarily swaps ``state.leaders`` itself for a
    read-only ``ChainMap`` overlaying the dead leader's own stored
    ``dead_leaders[hero_id]`` snapshot (location, kingdom, skills --
    exactly what a real resurrection restores) on top of the real dict,
    restoring the original dict reference again in a ``finally`` --
    the real ``state.leaders`` dict object is never written to at all
    (no window where any other reader of that same dict could observe
    the dead leader as a live entry), and an id that was already alive
    is never disturbed (``is_temp_insert`` guards that).
    """

    is_temp_insert = hero_id not in state.leaders and hero_id in state.dead_leaders
    real_leaders = state.leaders
    if is_temp_insert:
        state.leaders = ChainMap({hero_id: state.dead_leaders[hero_id]}, real_leaders)
    try:
        leader = state.leaders.get(hero_id)
        return {
            "search_feature": feature_options(state, leader_id=hero_id),
            "cast_feature_target": feature_options(state, leader_id=hero_id),
            "recruit_target": recruit_target_options(state, hero_id),
            "recruit_type": recruit_type_options(state, hero_id),
            "disband_target": [disband_target_options(state, hero_id, slot=slot) for slot in range(DISBAND_SLOT_COUNT)],
            "leave_target": leave_target_options(state, hero_id),
            "leave_army": [leave_army_target_options(state, hero_id, slot=slot) for slot in range(LEAVE_SLOT_COUNT)],
            "pick_up_target": [
                pick_up_army_target_options(state, hero_id, slot=slot) for slot in range(PICK_UP_SLOT_COUNT)
            ],
            "trade_recipient": trade_recipient_options(state, hero_id),
            "trade_gift": trade_gift_options(state, hero_id),
            "trail_target": trail_target_options(state, hero_id),
            "pursue_target": pursue_target_options(state, hero_id),
            "challenge_target": challenge_target_options(state, hero_id),
            "hire_target": hire_target_options(state, hero_id),
            "fire_target": fire_target_options(state, hero_id),
            "resurrection_target": resurrection_target_options(state, hero_id),
            "charm_target": charm_target_options(state, hero_id),
            "kill_enemy_target": kill_enemy_target_options(state, hero_id),
            "item": item_options(state, hero_id),
            "use_mi_item": use_mi_item_options(state, hero_id),
            "use_mi_item_spell_by_id": {str(k): v for k, v in use_mi_item_spell_by_id(state).items()},
            "give_item": give_item_options(state, hero_id),
            "is_undead_king": bool(leader is not None and leader.is_king and leader.alignment is Alignment.UNDEAD),
        }
    finally:
        if is_temp_insert:
            state.leaders = real_leaders


# Every plain (per leader+phase, no slot) top-level field template this
# module's own parse_phase_inputs() reads, used by _remap_nested_fields()
# below to rebuild the same field names, under the plain (non-nested)
# scheme, from whichever <field_prefix>-prefixed ones the nested-plan
# editor posted. "action"/"obj"/"extra" are the three every Action
# falls back to; the rest are each one specific Action's own dedicated
# field (see this module's own docstring for which Action reads which).
_NESTED_PLAIN_FIELD_TEMPLATES: tuple[str, ...] = (
    "action",
    "obj",
    "extra",
    "move_target",
    "defend_target",
    "search_feature",
    "recruit_target",
    "leave_target",
    "trade_recipient",
    "trade_gift",
    "trade_gold",
    "practice_ability",
    "trail_target",
    "challenge_target",
    "pursue_target",
    "hire_target",
    "hire_gold",
    "fire_target",
    "cast_spell",
    "cast_character_target",
    "cast_province_target",
    "cast_terrain",
    "cast_item_target",
    "cast_feature_target",
    "cast_resurrection_target",
    "cast_charm_target",
    "cast_kill_enemy_target",
    "use_mi_item",
    "use_mi_feature_target",
    "use_mi_character_target",
    "use_mi_province_target",
    "use_mi_terrain",
    "use_mi_resurrection_target",
    "use_mi_charm_target",
    "use_mi_kill_enemy_target",
)

# Every slotted (per leader+phase+slot) top-level field template, paired
# with its own real slot count.
_NESTED_SLOTTED_FIELD_TEMPLATES: tuple[tuple[str, int], ...] = (
    ("recruit_type", RECRUIT_TYPE_SLOT_COUNT),
    ("disband_target", DISBAND_SLOT_COUNT),
    ("leave_army", LEAVE_SLOT_COUNT),
    ("pick_up_target", PICK_UP_SLOT_COUNT),
)

# Every Encounter Plan tactic-slot field's own field_prefix (Search's
# own "tactic", Challenge's/Pursue's own "challenge_tactic"/
# "pursue_tactic", the Special Encounter Plan's own "sep_tactic") and
# the sub-field suffixes _parse_search_tactics() itself reads for each
# slot ("" is the slot's own base maneuver value). Kept in sync with
# parse_phase_inputs()/_parse_special_encounter_plan() by hand -- a new
# tactic-slot-bearing field_prefix added there needs a matching entry
# added here too, or that field is silently dropped for a nested hero
# specifically (see this function's own docstring).
_NESTED_TACTIC_FIELD_PREFIXES: tuple[str, ...] = ("tactic", "challenge_tactic", "pursue_tactic", "sep_tactic")
_NESTED_TACTIC_SUB_SUFFIXES: tuple[str, ...] = ("", "_say", "_spell", "_item", "_give_item", "_sub")


def _remap_nested_fields(
    form: dict[str, str], *, field_prefix: str, outer_leader_id: int, outer_n: int, hero_id: int
) -> dict[str, str]:
    """Rewrites every nested-plan field the template posts under its own
    ``<field_prefix>_<base>_<outer_leader_id>_<outer_n>_<m>[_<slot>]``
    naming into the plain ``<base>_<hero_id>_<m>[_<slot>]`` key
    ``parse_phase_inputs()`` (and every helper it calls) already
    expects for an ordinary top-level phase -- letting the newly-
    (re)joined character's own nested phases ``P<n+1>..P4`` be parsed
    by calling ``parse_phase_inputs()`` completely unchanged, rather
    than threading a ``field_prefix`` through every one of its ~20
    existing, already-tested helper functions.

    Every phase *outside* ``n+1..PHASE_COUNT-1``, **and** every phase
    inside it whose own ``<field_prefix>_action_..._<m>`` was posted
    empty ("-- no order --", the template's own default -- a real,
    GM-chosen "nothing this phase" rather than a missing field) gets a
    plain ``action_<hero_id>_<m> = WAIT`` filler instead -- ``parse_
    phase_inputs()`` always validates all 5 phases eagerly, and an
    entirely empty ``action`` field raises (``_parse_action("")``), so
    every phase it will ever look at needs *some* real, harmless
    value. ``_parse_nested_plan()`` below tells a real order apart from
    this filler by checking the original posted key directly, not by
    the remapped action's own value (both read back as ``ActionCode.
    WAIT`` otherwise).
    """

    remapped: dict[str, str] = {}
    for m in range(PHASE_COUNT):
        real_action_key = f"{field_prefix}_action_{outer_leader_id}_{outer_n}_{m}"
        if m <= outer_n or not form.get(real_action_key):
            remapped[f"action_{hero_id}_{m}"] = str(int(ActionCode.WAIT))
            continue
        for base in _NESTED_PLAIN_FIELD_TEMPLATES:
            posted_key = f"{field_prefix}_{base}_{outer_leader_id}_{outer_n}_{m}"
            if posted_key in form:
                remapped[f"{base}_{hero_id}_{m}"] = form[posted_key]
        for base, slot_count in _NESTED_SLOTTED_FIELD_TEMPLATES:
            for slot in range(slot_count):
                posted_key = f"{field_prefix}_{base}_{outer_leader_id}_{outer_n}_{m}_{slot}"
                if posted_key in form:
                    remapped[f"{base}_{hero_id}_{m}_{slot}"] = form[posted_key]
        for tactic_prefix in _NESTED_TACTIC_FIELD_PREFIXES:
            for slot in range(TACTIC_SLOT_COUNT):
                for suffix in _NESTED_TACTIC_SUB_SUFFIXES:
                    posted_key = f"{field_prefix}_{tactic_prefix}{suffix}_{outer_leader_id}_{outer_n}_{m}_{slot}"
                    if posted_key in form:
                        remapped[f"{tactic_prefix}{suffix}_{hero_id}_{m}_{slot}"] = form[posted_key]
    return remapped


def _parse_nested_plan(
    form: dict[str, str],
    leader_id: int,
    n: int,
    *,
    phase_label: str,
    field_prefix: str,
    hero_id: int,
    board_width: int,
    state: GameState,
) -> "ActionPlan | None":
    """Reads the newly-(re)joined character's own nested phases
    ``P<n+1>..P4`` with the exact same full, per-Action composer every
    ordinary top-level phase gets (``parse_phase_inputs()``, called
    recursively against ``hero_id`` once ``_remap_nested_fields()`` has
    rebuilt its own plain field names from this phase's own
    ``<field_prefix>``-prefixed ones -- see that function's own
    docstring). Shared, unchanged, by every Action that can embed a
    ``PlanPhase.nested_plan`` (Hire, rulebook [3.5]; a Cast or Use_MI-
    wand of Charm or Resurrection, rulebook [3.10]/[4.21.1]) -- all
    name the same "orders start the phase *after* this one" rule, and
    ``parser/k1_moves.py`` parses/round-trips all three identically
    (``models/plan.py``'s own "Nested plans" docstring). The engine
    itself enforces none of this ordering (confirmed: ``parser/k1_
    moves.py`` happily round-trips a nested plan starting at or before
    its own triggering phase) -- by only ever offering/reading phases
    strictly after ``n``, this composer is what actually guarantees it.

    A row left with no Action chosen is simply omitted (``PlanSegment.
    phases`` is a sparse label->phase mapping, not a list -- no "no
    gaps" requirement, unlike a Search Encounter Plan's own tactic
    slots); leaving every row empty returns ``None``, matching a failed
    attempt's own "nothing embedded" outcome and ``parser/k1_moves_
    writer.py``'s own "a nested plan never attaches to P4" rule for a
    triggering phase composed at ``P4`` itself (``range(n+1,
    PHASE_COUNT)`` is then empty, so this function is never even
    called there). **Deliberately caps at one level of nesting** -- a
    further Hire/Charm/Resurrection *within* this hero's own composed
    phases still gets no rich nested editor of its own (the template
    renders no third-level markup, so ``parse_phase_inputs()``'s own
    recursive ``_parse_nested_plan()`` call for *that* simply finds no
    matching fields and returns ``None``, the same safe "nothing
    embedded" degradation as an empty row) -- turn phases are too
    scarce for this to lose any real expressiveness in practice (a
    plan starting at P3 leaves only P4 for a further nesting trigger,
    which itself would then have zero phases left to nest into).
    """

    remapped_form = _remap_nested_fields(form, field_prefix=field_prefix, outer_leader_id=leader_id, outer_n=n, hero_id=hero_id)
    phase_inputs = parse_phase_inputs(remapped_form, hero_id, board_width=board_width, state=state)
    phases: dict[str, PlanPhase] = {}
    for nested_n in range(n + 1, PHASE_COUNT):
        phase_input = phase_inputs[nested_n]
        if phase_input.action is ActionCode.WAIT and not form.get(f"{field_prefix}_action_{leader_id}_{n}_{nested_n}"):
            # Missing entirely, or posted empty ("-- no order --", the
            # template's own default) -- _remap_nested_fields()'s own
            # WAIT filler, not a real, GM-chosen WAIT order.
            # Distinguishing the two needs the raw posted key, since
            # both decode to the exact same ComposedPhaseInput.
            continue
        label = f"P{nested_n}"
        phases[label] = PlanPhase(
            label=label,
            action=phase_input.action,
            obj=phase_input.obj,
            extra=phase_input.extra,
            nested_plan=phase_input.nested_plan,
        )
    if not phases:
        return None
    nested_labels = sorted(int(label[1:]) for label in phases)
    segment = PlanSegment(plan_start=nested_labels[0], plan_end=nested_labels[-1], sp=DEFAULT_SP, phases=phases)
    return ActionPlan(leader_id=hero_id, segments=[segment])


def _parse_fire_target(form: dict[str, str], leader_id: int, n: int, *, phase_label: str, state: GameState) -> int:
    """Reads a Fire phase's own ``fire_target_<leader_id>_<n>`` field
    into the real target Hero's ``leader_id`` -- the wire encoding is
    already a bare leader id (``fire_target_options()``'s own dropdown
    value, real even for the "Self" option), so no sentinel decoding is
    needed. Also enforces, at compose time rather than only at turn-
    processing time, rulebook [3.7]'s own King-any-province/Hero-needs-
    co-location rules plus the 2026-11-01 "can't Fire a King"/"must be
    this leader's own Kingdom" fixes -- the same checks ``turn/plan_
    dispatch.py _dispatch_fire()`` itself makes.
    """

    raw = form.get(f"fire_target_{leader_id}_{n}", "")
    if not raw:
        raise InvalidComposedMovesError(f"{phase_label}: choose a Hero to Fire.")
    target_id = _parse_int(raw, field_label=f"{phase_label} Fire target")
    leader = state.leaders.get(leader_id)
    target = state.leaders.get(target_id)
    if (
        leader is None
        or target is None
        or target.is_king
        or target.kingdom_id != leader.kingdom_id
        or (not leader.is_king and target.location != leader.location)
    ):
        # Defense in depth: every dropdown-offered id is a real,
        # eligible Hero, but a direct, tampered POST could still name
        # anything else.
        raise InvalidComposedMovesError(f"{phase_label}: choose a Hero to Fire.")
    return target_id


def _parse_resurrection_target(
    form: dict[str, str], leader_id: int, n: int, *, phase_label: str, state: GameState, field_prefix: str = "cast"
) -> int:
    """Reads a Resurrection Cast phase's own ``<field_prefix>_resurrection_
    target_<leader_id>_<n>`` field into the real target id -- the wire
    encoding is already a bare character id (``resurrection_target_options()``'s
    own dropdown value), so no sentinel decoding is needed. Also
    enforces, at compose time rather than only at turn-processing time,
    all three of ``_execute_resurrection()``'s own eligibility branches
    (comatose cure / Royal Heir restoration / ordinary dead-Hero
    revival) plus their shared co-location requirement.

    ``field_prefix`` defaults to ``"cast"`` (the top-level Cast Action's
    own field); Use_MI's standalone Resurrection-wand phase passes
    ``"use_mi"`` so its own target dropdown gets a distinct field name,
    never colliding with Cast's own same-row field were both offered
    (see this module's own docstring's Use Magic Item section).

    Falls back to the sibling ``<field_prefix>_resurrection_target_
    number_<leader_id>_<n>`` free-text field (2026-11-15, user-
    requested) when the dropdown itself is empty -- ``_resolve_target_
    raw()``'s own generic "dropdown first, hand-typed id second" shape.
    Every precondition above still applies identically either way.
    """

    raw = _resolve_target_raw(
        form,
        primary_field=f"{field_prefix}_resurrection_target_{leader_id}_{n}",
        number_field=f"{field_prefix}_resurrection_target_number_{leader_id}_{n}",
    )
    if not raw:
        raise InvalidComposedMovesError(f"{phase_label}: choose a Resurrection target.")
    target_id = _parse_int(raw, field_label=f"{phase_label} Resurrection target")
    leader = state.leaders.get(leader_id)
    if leader is None:
        raise InvalidComposedMovesError(f"{phase_label}: choose a Resurrection target.")
    living = state.leaders.get(target_id)
    eligible = False
    if living is not None and living.location == leader.location:
        if living.is_comatose or (living.is_royal_heir and is_unfinalized_royal_heir(living)):
            eligible = True
    elif living is None:
        dead = state.dead_leaders.get(target_id)
        if dead is not None and dead.location == leader.location:
            eligible = True
    if not eligible:
        # Defense in depth: every dropdown-offered id is a real,
        # co-located, eligible target, but a direct, tampered POST
        # could still name anything else.
        raise InvalidComposedMovesError(f"{phase_label}: choose a Resurrection target.")
    return target_id


def _parse_charm_target(
    form: dict[str, str], leader_id: int, n: int, *, phase_label: str, state: GameState, field_prefix: str = "cast"
) -> int:
    """Reads a Charm Cast phase's own ``<field_prefix>_charm_target_
    <leader_id>_<n>`` field into the real target id -- the wire encoding
    is already a bare character id (``charm_target_options()``'s own
    dropdown value), so no sentinel decoding is needed. Also enforces,
    at compose time rather than only at turn-processing time,
    ``_execute_charm()``'s own three preconditions (co-located,
    army-less, never a King), plus the active-Valhalla-visitor
    exclusion every character-targeted spell but Resurrection shares
    (same check ``_parse_kill_enemy_target()`` already makes) --
    deliberately NOT a same-Kingdom requirement, matching the engine's
    own confirmed "Charm can poach a foreign Hero" behavior.

    ``field_prefix`` defaults to ``"cast"``; Use_MI's standalone
    Charm-wand phase passes ``"use_mi"``, same reasoning as
    ``_parse_resurrection_target()``'s own docstring. Also falls back
    to the sibling ``<field_prefix>_charm_target_number_<leader_id>_
    <n>`` free-text field (2026-11-15, user-requested), same shape as
    that function's own.
    """

    raw = _resolve_target_raw(
        form,
        primary_field=f"{field_prefix}_charm_target_{leader_id}_{n}",
        number_field=f"{field_prefix}_charm_target_number_{leader_id}_{n}",
    )
    if not raw:
        raise InvalidComposedMovesError(f"{phase_label}: choose a Charm target.")
    target_id = _parse_int(raw, field_label=f"{phase_label} Charm target")
    leader = state.leaders.get(leader_id)
    target = state.leaders.get(target_id)
    if (
        leader is None
        or target is None
        or target.leader_id == leader_id
        or target.location != leader.location
        or target.is_king
        or state.armies_commanded_by(target.leader_id)
        or (target.leader_id == VALHALLA_VISITOR_LEADER_ID and target.valhalla_active_turn is not None)
    ):
        # Defense in depth: every dropdown-offered id is a real,
        # co-located, army-less, non-King leader, but a direct,
        # tampered POST could still name anything else.
        raise InvalidComposedMovesError(f"{phase_label}: choose a Charm target.")
    return target_id


def _parse_kill_enemy_target(
    form: dict[str, str], leader_id: int, n: int, *, phase_label: str, state: GameState, field_prefix: str = "cast"
) -> int:
    """Reads a Kill Enemy Cast phase's own ``<field_prefix>_kill_enemy_
    target_<leader_id>_<n>`` field into the real target id -- the wire
    encoding is already a bare character id (``kill_enemy_target_
    options()``'s own dropdown value). Also enforces, at compose time
    rather than only at turn-processing time, ``_execute_kill_enemy()``'s
    own co-location/King-immunity/Undead-immunity preconditions, plus
    the active-Valhalla-visitor exclusion every character-targeted
    spell but Resurrection shares. Deliberately does NOT reject an
    army-leading target -- that only halves the roll, it never blocks
    the cast outright (see ``kill_enemy_target_options()``'s own
    docstring).

    ``field_prefix`` defaults to ``"cast"``; Use_MI's standalone
    Kill-Enemy-wand phase passes ``"use_mi"``, same reasoning as
    ``_parse_resurrection_target()``'s own docstring. Also falls back
    to the sibling ``<field_prefix>_kill_enemy_target_number_
    <leader_id>_<n>`` free-text field (2026-11-15, user-requested),
    same shape as that function's own.
    """

    raw = _resolve_target_raw(
        form,
        primary_field=f"{field_prefix}_kill_enemy_target_{leader_id}_{n}",
        number_field=f"{field_prefix}_kill_enemy_target_number_{leader_id}_{n}",
    )
    if not raw:
        raise InvalidComposedMovesError(f"{phase_label}: choose a Kill Enemy target.")
    target_id = _parse_int(raw, field_label=f"{phase_label} Kill Enemy target")
    leader = state.leaders.get(leader_id)
    target = state.leaders.get(target_id)
    if (
        leader is None
        or target is None
        or target.leader_id == leader_id
        or target.location != leader.location
        or target.is_king
        or target.alignment is Alignment.UNDEAD
        or (target.leader_id == VALHALLA_VISITOR_LEADER_ID and target.valhalla_active_turn is not None)
    ):
        # Defense in depth: every dropdown-offered id is a real,
        # co-located, non-King, non-Undead, non-active-Valhalla-visitor
        # leader, but a direct, tampered POST could still name anything
        # else.
        raise InvalidComposedMovesError(f"{phase_label}: choose a Kill Enemy target.")
    return target_id


def _parse_cast_character_target(raw: str, *, phase_label: str, state: GameState) -> int:
    """**2026-11-07 bug fix**: now also rejects the active Valhalla
    visitor -- see ``cast_character_target_options()``'s own docstring
    for why this one exclusion isn't scoped to "per-spell research"
    the way the rest of this target's own eligibility is.
    """

    if not raw:
        raise InvalidComposedMovesError(f"{phase_label}: choose a Cast target character.")
    target_id = _parse_int(raw, field_label=f"{phase_label} Cast target")
    target = state.leaders.get(target_id)
    if target is None or (
        target.leader_id == VALHALLA_VISITOR_LEADER_ID and target.valhalla_active_turn is not None
    ):
        # Defense in depth: every dropdown-offered id is a real,
        # non-Valhalla-visitor leader, but a direct, tampered POST
        # could still name one that doesn't exist, or the visitor.
        raise InvalidComposedMovesError(f"{phase_label}: choose a Cast target character.")
    return target_id


def _parse_cast_item_target(raw: str, *, phase_label: str, state: GameState) -> int:
    if not raw:
        raise InvalidComposedMovesError(f"{phase_label}: choose an item for Locate Object.")
    item_id = _parse_int(raw, field_label=f"{phase_label} Locate Object target")
    if state.items.get(item_id) is None:
        # Defense in depth: every dropdown-offered id is a real item,
        # but a direct, tampered POST could still name one that doesn't
        # exist.
        raise InvalidComposedMovesError(f"{phase_label}: choose an item for Locate Object.")
    return item_id


def _parse_cast_terrain(raw: str, *, phase_label: str) -> int:
    if not raw:
        raise InvalidComposedMovesError(f"{phase_label}: choose Illusory Terrain's own fake terrain.")
    terrain_ordinal = _parse_int(raw, field_label=f"{phase_label} Illusory Terrain")
    try:
        Terrain(terrain_ordinal)
    except ValueError:
        # Defense in depth: every dropdown-offered value is a real
        # Terrain ordinal, but a direct, tampered POST could still name
        # one outside the enum's own range.
        raise InvalidComposedMovesError(f"{phase_label}: choose Illusory Terrain's own fake terrain.") from None
    return terrain_ordinal


def _parse_cast_phase(
    form: dict[str, str], leader_id: int, n: int, *, phase_label: str, state: GameState
) -> tuple[int, list[int | str], int | None]:
    """Reads a Cast phase's own ``cast_spell_<leader_id>_<n>`` dropdown
    plus whichever target sub-field matches that spell's own target
    shape (``cast_character_target_``/``cast_resurrection_target_``/
    ``cast_province_target_``/``cast_item_target_<leader_id>_<n>``, plus
    ``cast_terrain_<leader_id>_<n>`` for Illusory Terrain specifically)
    into the real ``obj``/``extra`` encoding -- see this module's own
    docstring's Cast section for the full per-shape rationale. Returns
    ``(obj, extra, nested_hero_id)``: ``nested_hero_id`` is the target
    id to build a ``nested_plan`` for for Charm/Resurrection
    (``CAST_NESTED_PLAN_SPELLS``), ``None`` for every other spell --
    telling ``parse_phase_inputs()`` not to even look for ``cast_
    nested_*`` fields, so a tampered POST can never smuggle a
    ``nested_plan`` onto a spell the engine's own ``_resolve_nested_
    plan_leader_id()`` would otherwise blindly splice in for (see that
    function's own docstring: it doesn't itself check which spell was
    cast).
    """

    raw_spell = form.get(f"cast_spell_{leader_id}_{n}", "")
    if not raw_spell:
        raise InvalidComposedMovesError(f"{phase_label}: choose a spell to Cast.")
    spell_ordinal = _parse_int(raw_spell, field_label=f"{phase_label} Cast spell")
    try:
        spell = Spell(spell_ordinal)
    except ValueError:
        spell = None
    if spell not in CAST_ACTION_SPELLS:
        # Defense in depth: every dropdown-offered value is one of the
        # 19 real Action-Cast spells, but a direct, tampered POST could
        # still name a Personal-Combat-only spell, Gate Angel, or
        # anything outside the Spell enum's own range.
        raise InvalidComposedMovesError(f"{phase_label}: choose a spell to Cast.")

    if spell is Spell.RESURRECTION:
        target = _parse_resurrection_target(form, leader_id, n, phase_label=phase_label, state=state)
        return int(spell), [target], target

    if spell is Spell.CHARM:
        target = _parse_charm_target(form, leader_id, n, phase_label=phase_label, state=state)
        return int(spell), [target], target

    if spell is Spell.KILL_ENEMY:
        target = _parse_kill_enemy_target(form, leader_id, n, phase_label=phase_label, state=state)
        return int(spell), [target], None

    if spell in CAST_CHARACTER_TARGET_SPELLS:
        # Falls back to a hand-typed leader id (2026-11-15, user-
        # requested, e.g. for Oratory/Phantasmal Armies) when the
        # dropdown itself is empty -- see _resolve_target_raw()'s own
        # docstring.
        raw_target = _resolve_target_raw(
            form,
            primary_field=f"cast_character_target_{leader_id}_{n}",
            number_field=f"cast_character_target_number_{leader_id}_{n}",
        )
        target = _parse_cast_character_target(raw_target, phase_label=phase_label, state=state)
        nested_hero_id = target if spell in CAST_NESTED_PLAN_SPELLS else None
        return int(spell), [target], nested_hero_id

    if spell is Spell.HIDE_FEATURE:
        target = _parse_hide_feature_target(
            form, leader_id, n, phase_label=phase_label, state=state, board_width=state.board_width
        )
        return int(spell), [target], None

    if spell in CAST_PROVINCE_TARGET_SPELLS:
        raw_target = form.get(f"cast_province_target_{leader_id}_{n}", "")
        target = _parse_move_target(raw_target, board_width=state.board_width, phase_label=phase_label, state=state)
        extra: list[int | str] = [target]
        if spell is Spell.ILLUS_TERRAIN:
            extra.append(_parse_cast_terrain(form.get(f"cast_terrain_{leader_id}_{n}", ""), phase_label=phase_label))
        return int(spell), extra, None

    if spell in CAST_ITEM_TARGET_SPELLS:
        raw_target = form.get(f"cast_item_target_{leader_id}_{n}", "")
        target = _parse_cast_item_target(raw_target, phase_label=phase_label, state=state)
        return int(spell), [target], None

    # CAST_NO_TARGET_SPELLS -- Skeletal Army, the one spell left after
    # excluding Gate Angel (2026-11-01, the user's own choice).
    return int(spell), [0], None


def _parse_use_mi_phase(
    form: dict[str, str], leader_id: int, n: int, *, phase_label: str, state: GameState
) -> tuple[int, list[int | str], int | None]:
    """Reads a Use Magic Item phase's own ``use_mi_item_<leader_id>_<n>``
    dropdown (``use_mi_item_options()``), plus -- for a wand -- whichever
    target sub-field matches its own fixed spell's target shape, reusing
    the exact same per-shape helpers ``_parse_cast_phase()`` uses, just
    under their own ``field_prefix="use_mi"`` fields so the two Actions'
    same-row cells never collide. Returns ``(obj, extra, nested_hero_id)``
    like ``_parse_cast_phase()`` -- but, per this module's own docstring's
    Use Magic Item section, ``obj`` here is the item-instance id
    (``UseMIRequest.item_instance_id``), never a Spell ordinal.

    A skill book needs no target field at all (rulebook [5.9]: a bare
    +1 to one Ability, self-consuming) -- ``extra`` is always ``[]``.

    Falls back to the sibling ``use_mi_item_number_<leader_id>_<n>``
    free-text field (2026-11-15, user-requested) when the dropdown
    itself is empty -- ``_resolve_target_raw()``'s own generic shape.
    Every precondition below still applies identically either way.
    """

    raw_item = _resolve_target_raw(
        form, primary_field=f"use_mi_item_{leader_id}_{n}", number_field=f"use_mi_item_number_{leader_id}_{n}"
    )
    if not raw_item:
        raise InvalidComposedMovesError(f"{phase_label}: choose a Magic Item to Use.")
    item_id = _parse_int(raw_item, field_label=f"{phase_label} Use Magic Item")
    item = state.items.get(item_id)
    if item is None or item.owner_leader_id != leader_id:
        raise InvalidComposedMovesError(f"{phase_label}: choose a Magic Item to Use.")

    category = TREASURE_CATEGORY.get(item.treasure)
    if category is TreasureCategory.SKILL_BOOK:
        return item_id, [], None

    if category is not TreasureCategory.SPELL_WAND:
        # Defense in depth: every dropdown-offered id is a real wand or
        # book, but a direct, tampered POST could still name an owned
        # item of any other category (combat weapon, passive ability
        # item, gold hoard, ...) -- all of which "operate automatically"
        # per [5.9] and are never a legitimate Use_MI target.
        raise InvalidComposedMovesError(f"{phase_label}: choose a Magic Item to Use.")
    spell = TREASURE_WAND_SPELL.get(item.treasure)
    if spell is None or spell not in CAST_ACTION_SPELLS or item.charges <= 0:
        # Defense in depth: use_mi_item_options() only ever offers a
        # charged wand whose spell is Action-Cast-eligible -- a direct,
        # tampered POST could still name an uncharged one, or (purely
        # defensively; no real wand maps to a non-Action-Cast-eligible
        # spell at all, since the five Personal-Combat-only wand spells
        # are filtered out above) one whose spell isn't.
        raise InvalidComposedMovesError(f"{phase_label}: choose a Magic Item to Use.")

    if spell is Spell.RESURRECTION:
        target = _parse_resurrection_target(form, leader_id, n, phase_label=phase_label, state=state, field_prefix="use_mi")
        return item_id, [target], target

    if spell is Spell.CHARM:
        target = _parse_charm_target(form, leader_id, n, phase_label=phase_label, state=state, field_prefix="use_mi")
        return item_id, [target], target

    if spell is Spell.KILL_ENEMY:
        target = _parse_kill_enemy_target(form, leader_id, n, phase_label=phase_label, state=state, field_prefix="use_mi")
        return item_id, [target], None

    if spell in CAST_CHARACTER_TARGET_SPELLS:
        raw_target = _resolve_target_raw(
            form,
            primary_field=f"use_mi_character_target_{leader_id}_{n}",
            number_field=f"use_mi_character_target_number_{leader_id}_{n}",
        )
        target = _parse_cast_character_target(raw_target, phase_label=phase_label, state=state)
        return item_id, [target], None

    if spell is Spell.HIDE_FEATURE:
        target = _parse_hide_feature_target(
            form, leader_id, n, phase_label=phase_label, state=state, board_width=state.board_width, field_prefix="use_mi"
        )
        return item_id, [target], None

    if spell in CAST_PROVINCE_TARGET_SPELLS:
        raw_target = form.get(f"use_mi_province_target_{leader_id}_{n}", "")
        target = _parse_move_target(raw_target, board_width=state.board_width, phase_label=phase_label, state=state)
        extra: list[int | str] = [target]
        if spell is Spell.ILLUS_TERRAIN:
            extra.append(_parse_cast_terrain(form.get(f"use_mi_terrain_{leader_id}_{n}", ""), phase_label=phase_label))
        return item_id, extra, None

    # CAST_NO_TARGET_SPELLS -- Skeletal Army, the only wand-mappable
    # member left (Gate Angel's own ordinal is outside the wand range
    # entirely, see this module's own docstring's Use Magic Item
    # section).
    return item_id, [0], None


def _parse_search_tactics(
    form: dict[str, str],
    leader_id: int,
    n: int,
    *,
    phase_label: str,
    state: GameState,
    field_prefix: str = "tactic",
    allow_give: bool = False,
    allow_fulfill_scout: bool = False,
    passive: bool = False,
    slot_count: int = TACTIC_SLOT_COUNT,
) -> list[int | str]:
    """Reads this phase's own ``<field_prefix>_<leader_id>_<n>_<slot>``/
    ``<field_prefix>_sub_<leader_id>_<n>_<slot>``/``<field_prefix>_say_
    <leader_id>_<n>_<slot>``/``<field_prefix>_spell_<leader_id>_<n>_
    <slot>``/``<field_prefix>_item_<leader_id>_<n>_<slot>`` fields
    (``slot`` in ``0..slot_count-1``) into a real, ``-1``-
    terminated Encounter Plan tactic list -- see this module's own
    docstring for the Talk-position, Steal-position, Steal/Talk/
    Fulfill-exclusion, Flee-at-most-once, Say free-text, Cast-spell-
    allowlist, and Use-Item-ownership rules enforced here, shared
    unchanged between every Encounter-Plan-bearing Action. ``field_
    prefix`` lets Challenge's own tactic slots (``"challenge_tactic"``)
    live in the same composed phase row as Search's own (``"tactic"``,
    the default) without colliding on the same POST field names --
    ``tactic_options()``'s own dropdown ``value``s are the same
    ``Maneuver`` ordinals either way, so no other change is needed per
    caller besides this, ``allow_give``, ``allow_fulfill_scout`` and
    ``passive`` (2026-11-14, see ``tactic_options()``'s own docstring
    for the full active-vs-passive rule each of these three flags now
    enforces here too, as defense in depth against a tampered POST
    naming an ordinal that caller's own dropdown never offers).
    ``slot_count`` defaults to ``TACTIC_SLOT_COUNT`` (every real phase's
    own Encounter Plan); the Special Encounter Plan's own call (2026-
    11-16, user-requested "add/remove as many as you like") passes
    ``SEP_TACTIC_SLOT_COUNT`` instead -- a much larger, unsourced UI
    ceiling, not a real-sample-confirmed one.
    ``state`` is only needed for Use Item's own ownership/category/charge
    lookup -- every
    other tactic's own validation is state-independent.
    """

    tokens: list[int | str] = []
    has_talk = False
    has_fulfill = False
    has_steal = False
    has_flee = False
    has_shoot = False
    stopped_at: int | None = None
    previous_maneuver: Maneuver | None = None
    previous_sub_object: int | None = None
    for slot in range(slot_count):
        raw = form.get(f"{field_prefix}_{leader_id}_{n}_{slot}", "")
        if not raw:
            if stopped_at is None:
                stopped_at = slot
            continue
        if stopped_at is not None:
            raise InvalidComposedMovesError(
                f"{phase_label}: tactic slot {slot + 1} follows empty slot {stopped_at + 1} -- "
                "fill the Encounter Plan without gaps."
            )
        try:
            maneuver = Maneuver(int(raw))
        except (TypeError, ValueError) as exc:
            raise InvalidComposedMovesError(f"{phase_label}: tactic slot {slot + 1} is not a valid tactic.") from exc
        if maneuver not in _COMPOSABLE_MANEUVERS:
            # Defense in depth: Maneuver.NONE is never offered in the
            # dropdown, but a direct, tampered POST could still name
            # its real ordinal.
            raise InvalidComposedMovesError(f"{phase_label}: tactic slot {slot + 1} isn't composable here yet.")
        if maneuver in (Maneuver.GIVE, Maneuver.STEAL) and not allow_give:
            # Defense in depth (2026-11-14): Give/Steal are never
            # offered in a passive Special Encounter Plan's own
            # dropdown (see tactic_options()), but a direct, tampered
            # POST could still name either real ordinal.
            raise InvalidComposedMovesError(
                f"{phase_label}: tactic slot {slot + 1}: {maneuver.name.title()} isn't usable in a standing "
                "Special Encounter Plan -- only in an active plan, generated after a Search (SE), Challenge "
                "(EN), Trail (TR) or Pursue (PU) order."
            )
        if maneuver in (Maneuver.BEG, Maneuver.SQUEEZE):
            # Defense in depth: neither Beg nor Squeeze is ever offered
            # in a tactic slot's own dropdown (see tactic_options()),
            # but a direct, tampered POST could still name either real
            # ordinal. Squeeze is only ever the Pascal source's own
            # internal narration label for the Hand of Death spell's
            # damage type (turn/encounter.py's own confirmed finding),
            # never a real player-orderable tactic.
            raise InvalidComposedMovesError(
                f"{phase_label}: tactic slot {slot + 1}: {maneuver.name.title()} isn't a real Encounter Plan tactic."
            )
        if maneuver in (Maneuver.FULFILL, Maneuver.SCOUT) and not allow_fulfill_scout:
            # Defense in depth (2026-11-14): Fulfill/Scout are only
            # ever offered after a Search (SE) order's own dropdown
            # (see tactic_options()), but a direct, tampered POST
            # could still name either real ordinal from a Challenge/
            # Pursue/Special Encounter Plan context.
            raise InvalidComposedMovesError(
                f"{phase_label}: tactic slot {slot + 1}: {maneuver.name.title()} is only usable in a Search "
                "(SE) Encounter Plan."
            )
        if maneuver is Maneuver.TALK:
            if passive:
                # Defense in depth (2026-11-14): Talk is never offered
                # in a passive Special Encounter Plan's own dropdown
                # (see tactic_options()), but a direct, tampered POST
                # could still name its real ordinal.
                raise InvalidComposedMovesError(
                    f"{phase_label}: tactic slot {slot + 1}: Talk isn't usable in a standing Special Encounter "
                    "Plan -- only in an active plan, generated after a Search (SE), Challenge (EN), Trail (TR) "
                    "or Pursue (PU) order."
                )
            if slot != 0:
                raise InvalidComposedMovesError(
                    f"{phase_label}: Talk can only be the first tactic in the Encounter Plan."
                )
            has_talk = True
        if maneuver is Maneuver.FULFILL:
            has_fulfill = True
        if maneuver is Maneuver.STEAL:
            cast_invisibility_precedes = (
                previous_maneuver is Maneuver.CAST and previous_sub_object == int(Spell.INVISIBILITY)
            )
            if slot != 0 and not cast_invisibility_precedes:
                raise InvalidComposedMovesError(
                    f"{phase_label}: tactic slot {slot + 1}: Steal can only be the first tactic in the "
                    "Encounter Plan, or come right after casting Invisibility."
                )
            has_steal = True
        if maneuver is Maneuver.FLEE:
            if has_flee:
                raise InvalidComposedMovesError(
                    f"{phase_label}: tactic slot {slot + 1}: Flee can only be used once in the same Encounter Plan."
                )
            has_flee = True
        if maneuver is Maneuver.SHOOT:
            if has_shoot:
                raise InvalidComposedMovesError(
                    f"{phase_label}: tactic slot {slot + 1}: Fire Arrow can only be used once in the same Encounter Plan."
                )
            has_shoot = True
        tokens.append(int(maneuver))
        sub_object: int | None = None
        if maneuver is Maneuver.SAY:
            say_text = form.get(f"{field_prefix}_say_{leader_id}_{n}_{slot}", "").strip()
            if not say_text:
                raise InvalidComposedMovesError(f"{phase_label}: tactic slot {slot + 1} needs Say's own text.")
            if len(say_text) > SAY_TEXT_MAX_LENGTH:
                raise InvalidComposedMovesError(
                    f"{phase_label}: tactic slot {slot + 1}'s Say text must be "
                    f"{SAY_TEXT_MAX_LENGTH} characters or fewer, got {len(say_text)}."
                )
            tokens.append(say_text)
        elif maneuver is Maneuver.CAST:
            spell_raw = form.get(f"{field_prefix}_spell_{leader_id}_{n}_{slot}", "")
            try:
                spell = Spell(int(spell_raw))
            except (TypeError, ValueError) as exc:
                raise InvalidComposedMovesError(f"{phase_label}: tactic slot {slot + 1}: choose a spell to Cast.") from exc
            if spell not in ENCOUNTER_PLAN_CASTABLE_SPELLS:
                raise InvalidComposedMovesError(
                    f"{phase_label}: tactic slot {slot + 1}: "
                    f"{SPELL_NAME.get(spell, spell.name)} can't be cast in an Encounter Plan."
                )
            tactic_caster = state.leaders.get(leader_id)
            if tactic_caster is not None and not _leader_knows_secret_spell(state, tactic_caster, spell):
                # Defense in depth (2026-11-14): same six skill-gated
                # secret spells as the top-level Cast dropdown -- this
                # leader hasn't reached skill 5+ in the governing
                # magical Ability yet.
                raise InvalidComposedMovesError(
                    f"{phase_label}: tactic slot {slot + 1}: this leader hasn't discovered "
                    f"{SPELL_NAME.get(spell, spell.name)} yet."
                )
            sub_object = int(spell)
            tokens.append(sub_object)
        elif maneuver is Maneuver.USE_MI:
            item_raw = form.get(f"{field_prefix}_item_{leader_id}_{n}_{slot}", "")
            item_id = _parse_int(item_raw, field_label=f"{phase_label} tactic {slot + 1} item") if item_raw else None
            item = state.items.get(item_id) if item_id is not None else None
            if item is None or item.owner_leader_id != leader_id:
                raise InvalidComposedMovesError(f"{phase_label}: tactic slot {slot + 1}: choose an item to Use.")
            item_spell = TREASURE_WAND_SPELL.get(item.treasure)
            if (
                TREASURE_CATEGORY.get(item.treasure) is not TreasureCategory.SPELL_WAND
                or item_spell is None
                or item_spell not in ENCOUNTER_PLAN_CASTABLE_SPELLS
            ):
                item_name = TREASURE_NAME.get(item.treasure, item.treasure.name)
                raise InvalidComposedMovesError(
                    f"{phase_label}: tactic slot {slot + 1}: {item_name} can't be used in an Encounter Plan."
                )
            if item.charges <= 0:
                item_name = TREASURE_NAME.get(item.treasure, item.treasure.name)
                raise InvalidComposedMovesError(
                    f"{phase_label}: tactic slot {slot + 1}: {item_name} has no charges left."
                )
            sub_object = item_id
            tokens.append(sub_object)
        elif maneuver is Maneuver.GIVE:
            # Rulebook (2026-11-01): "si può dare qualsiasi numero di
            # oggetti a chiunque si incontra" -- a dedicated, ownership-
            # filtered item dropdown (``give_item_options()``), same
            # "must actually hold this exact item" gate as Use Item's
            # own branch just above, but with no wand/spell-eligibility
            # restriction at all (any owned item is a legal gift) --
            # its own field name (``..._give_item_...``) so it never
            # collides with Use Item's own ``..._item_...`` field when
            # both are offered in the same Encounter Plan.
            item_raw = form.get(f"{field_prefix}_give_item_{leader_id}_{n}_{slot}", "")
            item_id = _parse_int(item_raw, field_label=f"{phase_label} tactic {slot + 1} item") if item_raw else None
            item = state.items.get(item_id) if item_id is not None else None
            if item is None or item.owner_leader_id != leader_id:
                raise InvalidComposedMovesError(f"{phase_label}: tactic slot {slot + 1}: choose an item to Give.")
            give_leader = state.leaders.get(leader_id)
            if give_leader is not None and give_leader.valhalla_fixed_item_id == item_id:
                raise InvalidComposedMovesError(
                    f"{phase_label}: tactic slot {slot + 1}: the Valhalla visitor's own fixed item can't be given away."
                )
            sub_object = item_id
            tokens.append(sub_object)
        elif maneuver in TACTICS_WITH_SUB_OBJECT:
            sub_raw = form.get(f"{field_prefix}_sub_{leader_id}_{n}_{slot}", "0")
            sub_object = _parse_int(sub_raw or "0", field_label=f"{phase_label} tactic {slot + 1} sub-object")
            tokens.append(sub_object)
        previous_maneuver = maneuver
        previous_sub_object = sub_object

    mutually_exclusive = [name for flag, name in [(has_talk, "Talk"), (has_fulfill, "Fulfill"), (has_steal, "Steal")] if flag]
    if len(mutually_exclusive) > 1:
        names = (
            " and ".join(mutually_exclusive)
            if len(mutually_exclusive) == 2
            else ", ".join(mutually_exclusive[:-1]) + ", and " + mutually_exclusive[-1]
        )
        raise InvalidComposedMovesError(f"{phase_label}: {names} can't be used together in the same Encounter Plan.")

    tokens.append(-1)
    return tokens


def _parse_special_encounter_plan(form: dict[str, str], leader_id: int, *, state: GameState) -> tuple[int | str, ...]:
    """Reads this leader's own standing Special Encounter Plan [5.10]
    (``sep_tactic_<leader_id>_0_<slot>``'s own repeated tactic slots,
    ``slot`` in ``0..SEP_TACTIC_SLOT_COUNT-1`` -- 2026-11-16, user-
    requested: a much larger ceiling than every real phase's own
    ``TACTIC_SLOT_COUNT``, since this table's own "add/remove as many
    as you like" UI needs the backend to actually read whatever the GM
    adds) into ``PlanSegment.sp``'s real wire shape.

    Reuses ``_parse_search_tactics()`` directly (``field_prefix=
    "sep_tactic"``, ``passive=True``). **2026-11-14 correction
    (user-confirmed)**: this used to pass ``allow_give=True`` instead,
    on the reasoning that ``turn/sep_decode.py``'s own ``Plan_Intent()``
    classifies ``CGive`` as a real SEP tactic -- true for *decoding* an
    already-submitted plan (a real player's own file could contain
    anything), but wrong for what the GM should be able to *compose*
    here: Talk/Give/Steal are each real only in an active plan generated
    after a Search/Challenge/Trail/Pursue order, never in a leader's own
    standing, passive Special Encounter Plan -- see ``tactic_options()``'s
    own docstring for the full rule. With a fixed ``n=0`` -- there is
    exactly one SEP
    per leader per turn, not one per phase, so ``n`` here is only ever
    used to keep this plan's own field names distinct from every real
    phase's (``_parse_search_tactics()`` never reads ``n`` for anything
    else, confirmed by that function's own docstring).

    **Unlike every phase's own Encounter Plan**, SP: has no leading
    ``tl``/``extra0`` slot at all (``turn/sep_decode.py``'s own
    docstring, confirmed against every real sample) -- so, unlike
    ``extra = [0, *_parse_search_tactics(...)]`` everywhere else in this
    module, this function's return value is used as ``PlanSegment.sp``
    completely unprefixed.

    A hired/charmed/resurrected character's own *nested* plan still
    gets the plain ``DEFAULT_SP`` placeholder (``_parse_nested_plan()``)
    -- composing a newly-joined character's own standing SEP is
    deliberately out of this round's scope, deferred alongside that
    function's own still-generic Object/Extra nested-order fields.

    **Leaving every slot untouched must still compose ``DEFAULT_SP``,
    not a genuinely empty plan** -- ``_parse_search_tactics()``'s own
    real "nothing filled in" result is the bare terminator ``[-1]``,
    which ``turn/sep_decode.py plan_intent()`` reads as *aggressive*
    Melee intent (`Plan_Intent`'s own "IF int = CNone THEN int:=
    CMelee" fallback), not Flee -- silently flipping every already-
    composed Kingdom's own leaders from the safe default every real
    sample shows to an aggressive one the moment this table first
    renders, with nobody having touched it. Special-cased back to
    ``DEFAULT_SP`` below so the new table's own idle state keeps
    matching the engine's real pre-existing default, the same property
    this function's own docstring above claims.
    """

    tactics = _parse_search_tactics(
        form,
        leader_id,
        0,
        phase_label="Special Encounter Plan",
        state=state,
        field_prefix="sep_tactic",
        passive=True,
        slot_count=SEP_TACTIC_SLOT_COUNT,
    )
    if tactics == [-1]:
        return DEFAULT_SP
    return tuple(tactics)


def parse_phase_inputs(
    form: dict[str, str], leader_id: int, *, board_width: int, state: GameState
) -> list[ComposedPhaseInput]:
    """Reads this one leader's own ``action_<leader_id>_<n>``/``obj_<leader_id>_<n>``/
    ``extra_<leader_id>_<n>`` form fields (``n`` in ``0..PHASE_COUNT-1``)
    into ``PHASE_COUNT`` validated phase inputs, in ``P0..P4`` order.

    A Move (``ActionCode.LMOVE``) phase reads its own dedicated
    ``move_target_<leader_id>_<n>`` dropdown field instead of the
    generic Object field (see this module's own docstring for why) --
    ``extra`` is always empty for Move, matching ``turn/plan_dispatch.py``'s
    own confirmed "Move's extra is never read" finding. A Defend
    (``ActionCode.DEFEND``) phase reads its own dedicated ``defend_
    target_<leader_id>_<n>`` dropdown field, same ``province_options()``
    choices and ``"x,y"`` wire shape as Move's own (``_parse_defend_
    target()``'s own docstring explains the still-unconfirmed, but
    today harmless, numbering-scheme choice this reuses). An Explore
    (``ActionCode.EXPLORE``) phase needs no field at all -- ``obj``/
    ``extra`` are forced to ``0``/``[]`` regardless of whatever the
    generic form fields happen to hold, since Explore always targets
    the acting leader's own current province (same module docstring). A
    Search (``ActionCode.SEARCH``) phase reads its own dedicated
    ``search_feature_<leader_id>_<n>`` dropdown field for ``obj`` (the
    target feature's own ``feature_id``) and its own Encounter Plan
    tactic slots (``_parse_search_tactics()``) for ``extra`` (same
    module docstring). ``state`` is threaded through to
    ``_parse_search_tactics()`` purely for Use Item's own ownership
    lookup -- see that function's own docstring. A Recruit
    (``ActionCode.RECRUIT``) phase reads its own dedicated
    ``recruit_target_<leader_id>_<n>`` commander dropdown for ``obj``
    and its own repeated ``recruit_type_<leader_id>_<n>_<slot>`` army-
    type dropdowns for ``extra`` (``_parse_recruit_target()``/
    ``_parse_recruit_types()``, same module docstring's own Recruit
    section). A Disband (``ActionCode.DISBAND``) phase needs no real
    ``obj`` (forced to ``0``, same as Explore) and reads its own
    repeated ``disband_target_<leader_id>_<n>_<slot>`` army-target
    dropdowns for ``extra`` (``_parse_disband_targets()``, same module
    docstring's own Disband section). A Leave (``ActionCode.LEAVE``)
    phase also needs no real ``obj`` (forced to ``0``) and reads its
    own ``leave_target_<leader_id>_<n>`` "to" dropdown plus its own
    repeated ``leave_army_<leader_id>_<n>_<slot>`` army-target
    dropdowns for ``extra`` (``_parse_leave_target()``/``_parse_leave_
    army_targets()``, same module docstring's own Leave section). A
    Pick Up (``ActionCode.PICK_UP``) phase also needs no real ``obj``
    (forced to ``0``) and reads its own repeated ``pick_up_target_
    <leader_id>_<n>_<slot>`` army-target dropdowns for ``extra``
    (``_parse_pick_up_targets()``, same module docstring's own Pick Up
    section) -- unlike Leave, it has no separate target dropdown, since
    Pick Up always acts for the ordering leader himself. A Give
    (``ActionCode.TRADE``) phase reads its own ``trade_recipient_
    <leader_id>_<n>`` dropdown for ``extra`` and its own ``trade_gift_
    <leader_id>_<n>``/``trade_gold_<leader_id>_<n>`` dropdown-plus-
    free-text pair for ``obj`` (``_parse_trade_recipient()``/``_parse_
    trade_gift()``, same module docstring's own Give section). A
    Practice (``ActionCode.PRACTICE``) phase reads its own single
    ``practice_ability_<leader_id>_<n>`` dropdown for ``obj`` (``_parse_
    practice_ability()``, same module docstring's own Practice section)
    and always encodes ``extra`` as ``[0]``. A Trail (``ActionCode.
    TRAIL``) phase reads its own single ``trail_target_<leader_id>_<n>``
    dropdown for ``obj`` (``_parse_trail_target()``, same module
    docstring's own Trail section) and always encodes ``extra`` as
    ``[0]``. A Challenge (``ActionCode.CHALLENGE``) phase reads its own
    single ``challenge_target_<leader_id>_<n>`` dropdown for ``obj``
    (``_parse_challenge_target()``) and its own repeated ``challenge_
    tactic_<leader_id>_<n>_<slot>`` Encounter Plan tactic slots for
    ``extra`` (``_parse_search_tactics()`` with ``field_prefix=
    "challenge_tactic", allow_give=True``, same module docstring's own
    Challenge section). A Hire (``ActionCode.HIRE``) phase reads its own
    single ``hire_target_<leader_id>_<n>`` dropdown for ``obj``, its own
    ``hire_gold_<leader_id>_<n>`` dropdown for ``extra`` (``_parse_hire_
    target()``/``_parse_hire_gold_offer()``), and its own repeated
    ``hire_nested_action_<leader_id>_<n>_<m>``/``hire_nested_obj_
    <leader_id>_<n>_<m>``/``hire_nested_extra_<leader_id>_<n>_<m>``
    fields for the hired Hero's own embedded ``nested_plan``
    (``_parse_hire_nested_plan()``, same module docstring's own Hire
    section) -- one of the two Actions in this composer whose own
    ``ComposedPhaseInput`` can carry a non-``None`` ``nested_plan``, the
    other being Cast of Charm/Resurrection below. A Fire (``ActionCode.
    FIRE``) phase reads its own single ``fire_target_<leader_id>_<n>``
    dropdown for ``obj`` (``_parse_fire_target()``, same module
    docstring's own Fire section) and always encodes ``extra`` as
    ``[]`` -- the one Action decoded with no payload at all. A Cast
    (``ActionCode.CAST``) phase reads its own ``cast_spell_<leader_id>_
    <n>`` dropdown plus whichever target sub-field matches that spell's
    own target shape into ``obj``/``extra`` (``_parse_cast_phase()``,
    same module docstring's own Cast section), and, for a successful-
    looking Charm/Resurrection composition, its own repeated ``cast_
    nested_action_<leader_id>_<n>_<m>``/``cast_nested_obj_<leader_id>_
    <n>_<m>``/``cast_nested_extra_<leader_id>_<n>_<m>`` fields for the
    newly-(re)joined character's own embedded ``nested_plan``
    (``_parse_nested_plan()`` with ``field_prefix="cast_nested"``). A
    Spy (``ActionCode.ASPY``) phase reads no field at all -- ``obj`` is
    always this leader's own current province, auto-derived via
    ``encode_hex_number(leader.location, board_width)`` (never a
    player choice, same module docstring's own Spy section), and
    ``extra`` is always ``[0]``. A Use Magic Item (``ActionCode.
    USE_MI``) phase reads its own ``use_mi_item_<leader_id>_<n>``
    dropdown for ``obj`` (an item-instance id, not a Spell ordinal --
    see this module's own docstring's Use Magic Item section) plus,
    for a wand, whichever target sub-field matches its own fixed
    spell's shape into ``extra`` (``_parse_use_mi_phase()``, reusing
    ``_parse_cast_phase()``'s own per-shape helpers under their own
    ``field_prefix="use_mi"`` fields) -- and, for a successful-looking
    Charm/Resurrection wand, its own repeated ``use_mi_nested_action_
    <leader_id>_<n>_<m>``/``use_mi_nested_obj_<leader_id>_<n>_<m>``/
    ``use_mi_nested_extra_<leader_id>_<n>_<m>`` fields for the
    newly-(re)joined character's own embedded ``nested_plan``
    (``_parse_nested_plan()`` with ``field_prefix="use_mi_nested"``),
    the third Action in this composer (after Hire and Cast) whose own
    ``ComposedPhaseInput`` can carry one.
    """

    phases: list[ComposedPhaseInput] = []
    for n in range(PHASE_COUNT):
        action = _parse_action(form.get(f"action_{leader_id}_{n}", ""))
        nested_plan: "ActionPlan | None" = None
        if action is ActionCode.LMOVE:
            obj = _parse_move_target(
                _resolve_province_target_raw(
                    form,
                    primary_field=f"move_target_{leader_id}_{n}",
                    number_field=f"move_target_number_{leader_id}_{n}",
                ),
                board_width=board_width,
                phase_label=f"P{n}",
                state=state,
            )
            extra: list[int | str] = []
        elif action is ActionCode.DEFEND:
            obj = _parse_defend_target(
                _resolve_province_target_raw(
                    form,
                    primary_field=f"defend_target_{leader_id}_{n}",
                    number_field=f"defend_target_number_{leader_id}_{n}",
                ),
                board_width=board_width,
                phase_label=f"P{n}",
            )
            extra = [0]
        elif action is ActionCode.EXPLORE:
            obj = 0
            extra = []
        elif action is ActionCode.SEARCH:
            obj = _parse_search_feature(
                form.get(f"search_feature_{leader_id}_{n}", ""), phase_label=f"P{n}", state=state
            )
            extra = [
                0,
                *_parse_search_tactics(
                    form, leader_id, n, phase_label=f"P{n}", state=state, allow_give=True, allow_fulfill_scout=True
                ),
            ]
        elif action is ActionCode.RECRUIT:
            obj = _parse_recruit_target(
                form.get(f"recruit_target_{leader_id}_{n}", ""), leader_id=leader_id, phase_label=f"P{n}", state=state
            )
            extra = [0, *_parse_recruit_types(form, leader_id, n, phase_label=f"P{n}", state=state), -1]
        elif action is ActionCode.DISBAND:
            obj = 0
            extra = [0, *_parse_disband_targets(form, leader_id, n, phase_label=f"P{n}", state=state), -1]
        elif action is ActionCode.LEAVE:
            obj = 0
            target = _parse_leave_target(form, leader_id, n, phase_label=f"P{n}", state=state)
            extra = [target, *_parse_leave_army_targets(form, leader_id, n, phase_label=f"P{n}", state=state), -1]
        elif action is ActionCode.PICK_UP:
            obj = 0
            extra = [0, *_parse_pick_up_targets(form, leader_id, n, phase_label=f"P{n}", state=state), -1]
        elif action is ActionCode.TRADE:
            trade_recipient_id = _parse_trade_recipient(form, leader_id, n, phase_label=f"P{n}", state=state)
            obj = _parse_trade_gift(
                form, leader_id, n, phase_label=f"P{n}", state=state, recipient_id=trade_recipient_id
            )
            # 2026-11-06 bug fix: extra[0] ("tl", the generic per-action
            # triple -- turn/trade_decode.py's own module docstring)
            # has no real meaning for an ordinary Give, so this has
            # always hardcoded a placeholder 0 -- the same convention
            # Disband/Leave/Pick_Up/Explore use for their own unused
            # obj/extra[0]. But turn/trade_decode.py rewrite_trade_as_
            # secret_spell_cast() reads extra[0] == leader_id as "this
            # Give is actually a self-targeted secret-spell Cast in
            # disguise" -- a hardcoded 0 silently satisfies that for a
            # King whose own leader_id is 0 (real: Kings import with
            # leader_id == kingdom_id, and kingdoms are 0-indexed in
            # this project's own original-format game data), turning
            # an ordinary gift of an item in the 25-34 secret-spell
            # ordinal range into a dropped gift and a bogus Cast. Any
            # placeholder guaranteed to differ from this leader_id
            # avoids the collision -- 1 only in that one exact case,
            # 0 (unchanged) otherwise.
            extra = [1 if leader_id == 0 else 0, trade_recipient_id]
        elif action is ActionCode.PRACTICE:
            obj = _parse_practice_ability(form.get(f"practice_ability_{leader_id}_{n}", ""), phase_label=f"P{n}")
            extra = [0]
        elif action is ActionCode.TRAIL:
            obj = _parse_trail_target(form, leader_id, n, phase_label=f"P{n}", state=state)
            extra = [0]
        elif action is ActionCode.CHALLENGE:
            obj = _parse_challenge_target(form, leader_id, n, phase_label=f"P{n}", state=state)
            extra = [
                0,
                *_parse_search_tactics(
                    form, leader_id, n, phase_label=f"P{n}", state=state, field_prefix="challenge_tactic", allow_give=True
                ),
            ]
        elif action is ActionCode.PURSUE:
            obj = _parse_pursue_target(form, leader_id, n, phase_label=f"P{n}", state=state)
            pursue_tactics = _parse_search_tactics(
                form, leader_id, n, phase_label=f"P{n}", state=state, field_prefix="pursue_tactic", allow_give=True
            )
            # [3.16]: "Se l'inseguitore non comanda alcuna unità militare
            # allora bisogna indicare un Piano d'Incontro" -- enforced
            # here, at compose time, on this leader's own current army
            # status (same compose-time-snapshot convention as every
            # other Action's own precondition check in this module;
            # turn-processing time remains the real arbiter if that
            # status changes before this phase actually runs). No
            # matching engine-side gate exists today (`turn/pursue_
            # execution.py execute_pursue()` happily resolves an
            # armyless, tactics-less Pursue as a silent peaceful catch-
            # up) -- deliberately not retrofitted there this round, the
            # same "this composer is what actually enforces it" choice
            # already made for Hire's own 1-4 gold-offer range, so as
            # not to retroactively reject the many already-existing,
            # already-tested persistent-chase scenarios that rely on
            # that permissive behavior.
            if pursue_tactics == [-1] and not state.armies_commanded_by(leader_id):
                raise InvalidComposedMovesError(
                    f"P{n}: an armyless Pursue needs an Encounter Plan -- add at least one tactic."
                )
            extra = [0, *pursue_tactics]
        elif action is ActionCode.HIRE:
            hero_id = _parse_hire_target(form, leader_id, n, phase_label=f"P{n}", state=state)
            obj = hero_id
            extra = [_parse_hire_gold_offer(form.get(f"hire_gold_{leader_id}_{n}", ""), phase_label=f"P{n}")]
            nested_plan = _parse_nested_plan(
                form, leader_id, n, phase_label=f"P{n}", field_prefix="hire_nested", hero_id=hero_id,
                board_width=board_width, state=state,
            )
        elif action is ActionCode.FIRE:
            obj = _parse_fire_target(form, leader_id, n, phase_label=f"P{n}", state=state)
            extra = []
        elif action is ActionCode.CAST:
            obj, extra, cast_nested_hero_id = _parse_cast_phase(form, leader_id, n, phase_label=f"P{n}", state=state)
            if cast_nested_hero_id is not None:
                nested_plan = _parse_nested_plan(
                    form, leader_id, n, phase_label=f"P{n}", field_prefix="cast_nested", hero_id=cast_nested_hero_id,
                    board_width=board_width, state=state,
                )
        elif action is ActionCode.ASPY:
            aspy_leader = state.leaders.get(leader_id)
            if aspy_leader is None:
                raise InvalidComposedMovesError(f"P{n}: Spy needs a leader who already exists this turn.")
            obj = encode_hex_number(aspy_leader.location, board_width)
            extra = [0]
        elif action is ActionCode.USE_MI:
            obj, extra, use_mi_nested_hero_id = _parse_use_mi_phase(form, leader_id, n, phase_label=f"P{n}", state=state)
            if use_mi_nested_hero_id is not None:
                nested_plan = _parse_nested_plan(
                    form, leader_id, n, phase_label=f"P{n}", field_prefix="use_mi_nested", hero_id=use_mi_nested_hero_id,
                    board_width=board_width, state=state,
                )
        else:
            obj = _parse_int(form.get(f"obj_{leader_id}_{n}", "0") or "0", field_label=f"P{n} Object")
            extra = _parse_extra(form.get(f"extra_{leader_id}_{n}", ""))
        phases.append(ComposedPhaseInput(action=action, obj=obj, extra=extra, nested_plan=nested_plan))
    return phases


def build_composed_kingdom(
    state: GameState,
    *,
    game_label: str,
    turn_number: int,
    kingdom_id: int,
    form: dict[str, str],
) -> Kingdom:
    """Builds the real ``Kingdom`` this Kingdom's composed-moves form
    describes -- one ``Leader``/``ActionPlan`` per ``kingdom_leaders_
    for_compose()`` entry, each read via ``parse_phase_inputs()`` for
    its own P0-P4 phases plus ``_parse_special_encounter_plan()`` for
    its own standing ``PlanSegment.sp`` (see this module's own
    docstring's Special Encounter Plan section).

    Raises ``InvalidComposedMovesError`` if the King can't be identified
    or any phase's own input doesn't parse.
    """

    roster = kingdom_leaders_for_compose(state, kingdom_id)
    king = next((leader for leader in roster if leader.is_king), None)
    if king is None:
        raise InvalidComposedMovesError("This Kingdom has no King on record -- create the world first.")

    leaders: list[Leader] = []
    for leader_state in roster:
        phase_inputs = parse_phase_inputs(form, leader_state.leader_id, board_width=state.board_width, state=state)
        phases = {
            f"P{n}": PlanPhase(
                label=f"P{n}",
                action=phase_input.action,
                obj=phase_input.obj,
                extra=phase_input.extra,
                nested_plan=phase_input.nested_plan,
            )
            for n, phase_input in enumerate(phase_inputs)
        }
        sp = _parse_special_encounter_plan(form, leader_state.leader_id, state=state)
        segment = PlanSegment(plan_start=0, plan_end=PHASE_COUNT - 1, sp=sp, phases=phases)
        plan = ActionPlan(leader_id=leader_state.leader_id, segments=[segment])
        leaders.append(Leader(leader_id=leader_state.leader_id, name=leader_state.name, plan=plan))

    skills = king.skills
    if skills is None:
        raise InvalidComposedMovesError(f"{king.name}: this King has no skill table on record yet.")

    return Kingdom(
        source_filename=compose_filename(game_label, turn_number, kingdom_id),
        king_name=king.name,
        king_title=None,
        header=KingdomMoveHeader(raw_fields=list(DEFAULT_HEADER_RAW_FIELDS), sex=king.sex.value if king.sex is not None else "M"),
        skills=skills,
        leaders=leaders,
    )
