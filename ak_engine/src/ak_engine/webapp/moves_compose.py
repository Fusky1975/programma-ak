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

Not touched here, out of scope for this round: ``turn/challenge_
execution.py``'s own range-closing helper, ``_close_to()``, is a
zero-cost, instant move bundled into the same tactic-resolution step
that then immediately fires -- unlike the rulebook text's own "closing
to archery range consumes a round, then shoots the following round"
reading, which this module's own earlier docstring aspired to but
never actually built this way. This is a real discrepancy, but it
lives in Challenge's own encounter resolution, which has no composer
of its own yet (same situation as Give/Beg's Challenge/Pursue
carve-outs above) -- nothing to compose differently here either way.

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

Every other not-yet-designed action still falls back to the plain
Object/Extra integers. A Special Encounter Plan (``PlanSegment.sp``)
and a nested Hire/Charm/Resurrection plan (``PlanPhase.nested_plan``)
aren't exposed here yet either, for the same reason -- every composed
leader gets the plain ``(10, -1)`` "nothing special configured" ``SP:``
value every real sample already shows by default, and no nested plan.

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

from dataclasses import dataclass

from ak_engine.models.army_type import ARMY_TABLE, ARMY_TYPE_BY_ORDINAL, ARMY_TYPE_NAME, NO_LEADER_SENTINEL
from ak_engine.models.enums import SPELL_NAME, TACTICS_WITH_SUB_OBJECT, ActionCode, Maneuver, Spell
from ak_engine.models.feature import FEATURE_TYPE_NAMES
from ak_engine.models.game_state import ArmyState, GameState, LeaderState
from ak_engine.models.kingdom import Kingdom, KingdomMoveHeader
from ak_engine.models.leader import Leader
from ak_engine.models.map import HexCoord
from ak_engine.models.monster import MONSTER_NAMES
from ak_engine.models.plan import ActionPlan, PlanPhase, PlanSegment
from ak_engine.models.treasure import TREASURE_CATEGORY, TREASURE_NAME, TREASURE_WAND_SPELL, TreasureCategory
from ak_engine.report.turn_report import real_province_number
from ak_engine.turn.army_list_decode import ALL_ARMIES_SENTINEL
from ak_engine.turn.combat import QUALITY_NAME, Quality
from ak_engine.turn.hex_numbering import encode_hex_number
from ak_engine.turn.recruit import is_army_type_compatible_with_race, recruit_limit

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

# Every Maneuver a GM can compose here -- Maneuver.NONE is a sentinel,
# never a real tactic, so it's the only one excluded.
_COMPOSABLE_MANEUVERS: tuple[Maneuver, ...] = tuple(maneuver for maneuver in Maneuver if maneuver is not Maneuver.NONE)

# Rulebook [5.3]'s own stated limit ("entro un limite di 160 caratteri").
SAY_TEXT_MAX_LENGTH = 160

# The exact 17 spells `turn/search_execution.py _resolve_cast_tactic()`
# dispatches inside a Search Encounter Plan -- every other real Spell
# is an Action-Cast-only spell (one of the 5 regular phases, never a
# Encounter Plan) and silently no-ops there today. Confirmed directly
# against that function's own exhaustive `if/elif ... else: return
# None` branch (2026-10-28 investigation) -- Gate Angel is the one
# entry added alongside this round, see this module's own docstring
# for its full, explicitly-project-original sourcing.
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
    }
)

PHASE_COUNT = 5  # P0..P4 -- every real AK3__T*.K1 sample's own leader block shape.

# "Nothing special configured" -- the one Special Encounter Plan value
# every leader in this project's own real sample files shows (sourced
# directly: no sample has ever shown a different SP: value). Composing
# a real Special Encounter Plan is deferred to a later round.
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


def province_options(state: GameState) -> list[tuple[str, str]]:
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
    """

    provinces = sorted(state.provinces.values(), key=lambda province: (province.coord.y, province.coord.x))
    options = []
    for province in provinces:
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
    """

    features = sorted(state.features.values(), key=lambda feature: feature.feature_id)
    options = []
    for feature in features:
        province = state.provinces.get(feature.coord)
        place = province.name if province is not None and province.name else f"({feature.coord.x}, {feature.coord.y})"
        label = f"#{feature.feature_id} {FEATURE_TYPE_NAMES[feature.kind]} -- {place}"
        if feature.guardian_monster is not None and not feature.looted:
            label += f" -- {MONSTER_NAMES.get(feature.guardian_monster, feature.guardian_monster.name.title())}"
        if leader_id is not None and feature.pending_deal_leader_id == leader_id:
            label += " -- pending quest for this leader"
        options.append((str(feature.feature_id), label))
    return options


def spell_options() -> list[tuple[int, str]]:
    """Every spell a Cast tactic can actually use inside a Search
    Encounter Plan (``ENCOUNTER_PLAN_CASTABLE_SPELLS``), as ``(value,
    display_name)`` pairs for the Cast tactic's own dedicated spell
    dropdown -- see this module's own docstring for why Cast gets a
    named dropdown instead of the generic numeric sub-object field
    every other ``TACTICS_WITH_SUB_OBJECT`` maneuver uses. Sorted by
    the spell's own real ordinal.
    """

    return [
        (int(spell), SPELL_NAME.get(spell, spell.name.replace("_", " ").title()))
        for spell in sorted(ENCOUNTER_PLAN_CASTABLE_SPELLS, key=int)
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
        if province.recruit_type_1 is not None:
            is_native = army_type in (province.recruit_type_1, province.recruit_type_2)
        else:
            is_native = True
        base_pay = ARMY_TABLE[army_type].pay
        cost = base_pay if is_native else base_pay * 2
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
    VALUE`` pseudo-option ("Disband ALL I command") is prepended --
    only ever offered in slot 0, mirroring Talk's own "only the first
    slot" shape in Search's Encounter Plan -- see this module's own
    docstring for why it can't be combined with a specific army list.
    """

    leader = state.leaders.get(leader_id)
    if leader is None:
        return []
    options: list[tuple[str, str]] = []
    if slot == 0:
        options.append((DISBAND_ALL_VALUE, "Disband ALL I command"))
    for army in sorted(state.armies.values(), key=lambda army: army.army_id):
        if army.kingdom_id != leader.kingdom_id:
            continue
        if not leader.is_king and army.location != leader.location:
            continue
        options.append((str(army.army_id), _disband_army_label(state, army)))
    return options


def tactic_options(slot: int) -> list[tuple[int, str]]:
    """Every composable ``Maneuver`` for one Search Encounter Plan tactic
    slot, as ``(value, display_name)`` pairs -- ``Maneuver.TALK`` is only
    ever included for ``slot == 0`` (see this module's own docstring for
    the user-sourced "Talk can only be the first tactic" rule); every
    other slot gets the same ``_COMPOSABLE_MANEUVERS`` list minus Talk.
    ``Maneuver.GIVE`` and ``Maneuver.BEG`` are excluded for every slot
    here -- neither is a real Search Encounter Plan tactic (see this
    module's own docstring for the user-sourced rationale for each).
    """

    return [
        (int(maneuver), "Fire Arrow" if maneuver is Maneuver.SHOOT else maneuver.name.replace("_", " ").title())
        for maneuver in _COMPOSABLE_MANEUVERS
        if maneuver not in (Maneuver.GIVE, Maneuver.BEG) and (maneuver is not Maneuver.TALK or slot == 0)
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


def _parse_action(raw: str) -> ActionCode:
    try:
        return ActionCode(int(raw))
    except (TypeError, ValueError) as exc:
        raise InvalidComposedMovesError(f"{raw!r} is not a valid Action.") from exc


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


def _parse_move_target(raw: str, *, board_width: int, phase_label: str) -> int:
    if not raw:
        raise InvalidComposedMovesError(f"{phase_label}: choose a Move destination.")
    x_str, _, y_str = raw.partition(",")
    x = _parse_int(x_str, field_label=f"{phase_label} Move destination")
    y = _parse_int(y_str, field_label=f"{phase_label} Move destination")
    return encode_hex_number(HexCoord(x, y), board_width)


def _parse_search_feature(raw: str, *, phase_label: str) -> int:
    if not raw:
        raise InvalidComposedMovesError(f"{phase_label}: choose a Feature to Search.")
    return _parse_int(raw, field_label=f"{phase_label} Search feature")


def _parse_recruit_target(raw: str, *, leader_id: int, phase_label: str) -> int:
    """Reads a Recruit phase's own ``recruit_target_<leader>_<n>`` field
    into the real ``obj`` encoding -- ``"self"``/empty resolves to the
    acting leader's own id, ``"garrison"`` to ``NO_LEADER_SENTINEL``,
    anything else to another co-located leader's own id (``recruit_
    target_options()``'s own dropdown value), matching ``turn/recruit_
    decode.py``'s own leader-id-or-255 encoding.
    """

    if not raw or raw == "self":
        return leader_id
    if raw == "garrison":
        return NO_LEADER_SENTINEL
    return _parse_int(raw, field_label=f"{phase_label} Recruit target")


def _parse_recruit_types(form: dict[str, str], leader_id: int, n: int, *, phase_label: str) -> list[int]:
    """Reads this Recruit phase's own ``recruit_type_<leader_id>_<n>_
    <slot>`` fields (``slot`` in ``0..RECRUIT_TYPE_SLOT_COUNT-1``) into
    a list of real ``ArmyType`` ordinals -- the same no-gaps convention
    Search's own tactic slots already use (an empty slot stops the
    list there; a later non-empty slot after one is rejected). At least
    one type must be chosen -- a Recruit order with nothing to recruit
    isn't a real order.
    """

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
        if ordinal not in ARMY_TYPE_BY_ORDINAL:
            # Defense in depth: every dropdown-offered ordinal is a real
            # key of ARMY_TYPE_BY_ORDINAL (recruit_type_options() only
            # ever lists those), but a direct, tampered POST could still
            # name an out-of-range value.
            raise InvalidComposedMovesError(f"{phase_label}: recruit type slot {slot + 1} isn't a known army type.")
        ordinals.append(ordinal)
    if not ordinals:
        raise InvalidComposedMovesError(f"{phase_label}: choose at least one army type to Recruit.")
    return ordinals


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
    """

    leader = state.leaders.get(leader_id)
    if form.get(f"disband_target_{leader_id}_{n}_0", "") == DISBAND_ALL_VALUE:
        for slot in range(1, DISBAND_SLOT_COUNT):
            if form.get(f"disband_target_{leader_id}_{n}_{slot}", ""):
                raise InvalidComposedMovesError(
                    f"{phase_label}: 'Disband ALL I command' can't be combined with another army in the same order."
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
    if not army_ids:
        raise InvalidComposedMovesError(
            f"{phase_label}: choose at least one army to Disband (or 'Disband ALL I command')."
        )
    return army_ids


def _parse_search_tactics(
    form: dict[str, str], leader_id: int, n: int, *, phase_label: str, state: GameState
) -> list[int | str]:
    """Reads this Search phase's own ``tactic_<leader_id>_<n>_<slot>``/
    ``tactic_sub_<leader_id>_<n>_<slot>``/``tactic_say_<leader_id>_<n>_
    <slot>``/``tactic_spell_<leader_id>_<n>_<slot>``/``tactic_item_
    <leader_id>_<n>_<slot>`` fields (``slot`` in
    ``0..TACTIC_SLOT_COUNT-1``) into a real, ``-1``-terminated
    Encounter Plan tactic list -- see this module's own docstring for
    the Talk-position, Steal-position, Steal/Talk/Fulfill-exclusion,
    Flee-at-most-once, Say free-text, Cast-spell-allowlist, and
    Use-Item-ownership rules enforced here. ``state`` is only needed
    for Use Item's own ownership/category/charge lookup -- every
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
    for slot in range(TACTIC_SLOT_COUNT):
        raw = form.get(f"tactic_{leader_id}_{n}_{slot}", "")
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
        if maneuver is Maneuver.GIVE:
            # Defense in depth: Give is never offered in a Search tactic
            # slot's own dropdown (see tactic_options()), but a direct,
            # tampered POST could still name its real ordinal.
            raise InvalidComposedMovesError(
                f"{phase_label}: tactic slot {slot + 1}: Give isn't usable in a Search Encounter Plan -- "
                "only after Challenge (EN) or Pursue (PU)."
            )
        if maneuver is Maneuver.BEG:
            # Defense in depth: Beg is never offered in a Search tactic
            # slot's own dropdown (see tactic_options()), but a direct,
            # tampered POST could still name its real ordinal.
            raise InvalidComposedMovesError(
                f"{phase_label}: tactic slot {slot + 1}: Beg isn't a real Encounter Plan tactic."
            )
        if maneuver is Maneuver.TALK:
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
            say_text = form.get(f"tactic_say_{leader_id}_{n}_{slot}", "").strip()
            if not say_text:
                raise InvalidComposedMovesError(f"{phase_label}: tactic slot {slot + 1} needs Say's own text.")
            if len(say_text) > SAY_TEXT_MAX_LENGTH:
                raise InvalidComposedMovesError(
                    f"{phase_label}: tactic slot {slot + 1}'s Say text must be "
                    f"{SAY_TEXT_MAX_LENGTH} characters or fewer, got {len(say_text)}."
                )
            tokens.append(say_text)
        elif maneuver is Maneuver.CAST:
            spell_raw = form.get(f"tactic_spell_{leader_id}_{n}_{slot}", "")
            try:
                spell = Spell(int(spell_raw))
            except (TypeError, ValueError) as exc:
                raise InvalidComposedMovesError(f"{phase_label}: tactic slot {slot + 1}: choose a spell to Cast.") from exc
            if spell not in ENCOUNTER_PLAN_CASTABLE_SPELLS:
                raise InvalidComposedMovesError(
                    f"{phase_label}: tactic slot {slot + 1}: "
                    f"{SPELL_NAME.get(spell, spell.name)} can't be cast in an Encounter Plan."
                )
            sub_object = int(spell)
            tokens.append(sub_object)
        elif maneuver is Maneuver.USE_MI:
            item_raw = form.get(f"tactic_item_{leader_id}_{n}_{slot}", "")
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
        elif maneuver in TACTICS_WITH_SUB_OBJECT:
            sub_raw = form.get(f"tactic_sub_{leader_id}_{n}_{slot}", "0")
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
    own confirmed "Move's extra is never read" finding. An Explore
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
    docstring's own Disband section).
    """

    phases: list[ComposedPhaseInput] = []
    for n in range(PHASE_COUNT):
        action = _parse_action(form.get(f"action_{leader_id}_{n}", ""))
        if action is ActionCode.LMOVE:
            obj = _parse_move_target(
                form.get(f"move_target_{leader_id}_{n}", ""), board_width=board_width, phase_label=f"P{n}"
            )
            extra: list[int | str] = []
        elif action is ActionCode.EXPLORE:
            obj = 0
            extra = []
        elif action is ActionCode.SEARCH:
            obj = _parse_search_feature(form.get(f"search_feature_{leader_id}_{n}", ""), phase_label=f"P{n}")
            extra = [0, *_parse_search_tactics(form, leader_id, n, phase_label=f"P{n}", state=state)]
        elif action is ActionCode.RECRUIT:
            obj = _parse_recruit_target(
                form.get(f"recruit_target_{leader_id}_{n}", ""), leader_id=leader_id, phase_label=f"P{n}"
            )
            extra = [0, *_parse_recruit_types(form, leader_id, n, phase_label=f"P{n}"), -1]
        elif action is ActionCode.DISBAND:
            obj = 0
            extra = [0, *_parse_disband_targets(form, leader_id, n, phase_label=f"P{n}", state=state), -1]
        else:
            obj = _parse_int(form.get(f"obj_{leader_id}_{n}", "0") or "0", field_label=f"P{n} Object")
            extra = _parse_extra(form.get(f"extra_{leader_id}_{n}", ""))
        phases.append(ComposedPhaseInput(action=action, obj=obj, extra=extra))
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
    for_compose()`` entry, each read via ``parse_phase_inputs()``.

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
            f"P{n}": PlanPhase(label=f"P{n}", action=phase_input.action, obj=phase_input.obj, extra=phase_input.extra)
            for n, phase_input in enumerate(phase_inputs)
        }
        segment = PlanSegment(plan_start=0, plan_end=PHASE_COUNT - 1, sp=DEFAULT_SP, phases=phases)
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
