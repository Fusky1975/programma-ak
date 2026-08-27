"""Executing a Cast order end-to-end (rulebook [3.10]/[4.21]-[4.25]).

Of the 25 base ``Spell``s, 15 get real execution here as of Phase 193
(13 as of Phase 60):

- **Charm** and **Kill_Enemy** (Phase 29): see their own helpers below.
  Charm gained a real "target must command no armies" precondition and
  an Undead-caster Necromancy-instead-of-Psychic override in Phase 183
  -- see ``_execute_charm``'s own docstring.
- **Resurrect, Part_Sea, Bless, Flood, Tornado, Earthquake, Oratory,
  Plague, Illus_Terrain, Illus_Armies** (Phase 59): each spell's exact
  numeric mechanics were unavailable to this project until Regolamento
  AK.txt (a more detailed Italian-language rulebook the user supplied)
  spelled out precise percentages, ranges, and targeting rules that the
  English ``RULES.AK``/``ADDEND.AK`` sources never gave -- Phase 29's own
  docstring explicitly named this as the blocker for exactly these ten
  spells ("gives no numeric effect magnitude for any of them"). See each
  ``_execute_*`` helper below for its citation.
- **Skeletal_Army** (Phase 60): unblocked by
  ``GameState.battle_graveyard`` (a new per-province "what died here in
  a battle" registry, populated by ``turn/battle_orchestrator.py``'s
  four real destruction sites) -- the exact registry Phase 59's own
  docstring said this spell needed and didn't have. **Bless's own
  addendum rule** ("now also removes dead units from a province,
  10%+10%/level in White Magic") is implemented the same phase, for the
  same reason: it reads/clears the same registry.
- **Hide_Feature** ([4.23.3]) and **Clairvoyance** ([4.22.3])** (Phase
  193): see the "Phase 193 addendum" further down for exactly what
  unblocked each -- the "Still unexecuted" bullets for both spells
  immediately below are now stale, kept verbatim as the historical
  record of what blocked them through Phase 192, not deleted, per this
  project's own "correct via addendum, don't rewrite history"
  convention.

**Still unexecuted, each for its own documented reason** (10 of the 25
as of Phase 193; see the note just above for why the Hide_Feature/
Clairvoyance entries here are stale -- **the "10 Personal-Combat-only
spells" and Charm-combat-form bullets below are now equally stale as of
Phase 289**: the general tactic-sequence engine they claim blocks all
eleven was in fact built, one spell at a time, entirely inside ``turn/
search_execution.py _resolve_cast_tactic()`` across Phase 209-238 and
289 -- not here, since (as this same bullet correctly notes) none of
these spells ever appear as a top-level ``ActionCode.CAST`` phase this
module handles, only inside a Search encounter's own tactic list. Kept
verbatim below as the historical record of what blocked them through
Phase 208, per this project's own "correct via addendum, don't rewrite
history" convention; see ``turn/search_execution.py``'s own module
docstring and ``turn/encounter.py``'s own per-spell addenda for what
actually unblocked each one and when):

- **Hide_Feature** ([4.23.3]): targets a "Special Location" in a
  province, but ``models/map.py``'s ``Feature`` is an unpopulated stub
  (Phase 1's own scope note) -- no per-province feature list exists to
  hide an entry from.
- **Clairvoyance** ([4.22.3]): "for the rest of the turn, the caster
  knows everything that happens to the target" needs a per-character
  event feed -- the "story event" model ``ak_engine/report/prose.py``'s
  own Phase 58 docstring already named as a distinct, not-yet-attempted
  future piece.
- **The 10 Personal-Combat-*only* spells** (Holy_Symbol, Spiritwrack,
  Psychic_Blast, Telek_Storm, Invisibility, Mirror_Image, Fireball,
  Ice_Suspend, Hand_of_Death, Control_Undead -- [4.21.4]-[4.21.5],
  [4.22.4]-[4.22.5], [4.23.4]-[4.23.5], [4.24.4]-[4.24.5],
  [4.25.4]-[4.25.5]): every one of these only ever appears inside an
  encounter's own tactic list (``Maneuver.CAST``, decoded by
  ``turn/search_decode.py`` -- never a top-level ``ActionCode.CAST``
  phase, confirmed by ``turn/cast_decode.py``'s own validation against
  all 108 real sample Cast phases), and casting them requires the
  general tactic-sequence combat engine ``turn/encounter.py``'s own
  docstring explicitly scopes out ("Casting spells / using magic items
  in combat -- no spell-effect or magic-item system exists anywhere in
  this project," plus the missing range-transition state machine and
  monster-HP model a real Piano d'Incontro needs). None of these ten can
  be attempted without building that engine first. This also means
  **Invisibility's own addendum** ("now gives +30% chance to flee") stays
  unmodeled along with the base spell -- there is no Flee tactic
  resolver to apply the bonus to either.
- **Charm is the one spell confirmed (Phase 183) to have *both* an
  Action-Cast form (``_execute_charm`` above) and a Personal-Combat
  form** -- unlike the ten spells above, which are Personal-Combat-
  *only*. Real ``models/monster_encounter_plan.py`` data already used
  ``CA-CH`` (e.g. the Dryad's own encounter plan, Phase 178) before this
  dual nature was explicitly confirmed. The Personal-Combat form --
  "praticamente se usato in combattimento equivale a un comando FL che
  riesce sempre" (a guaranteed-success Flee) -- is modeled as
  ``turn/encounter.py CHARM_FLEE_ALWAYS_SUCCEEDS``, not here, and is
  equally unwired into any real tactic-walk engine for the same reason
  as the ten Personal-Combat-only spells above.
- **Words of Healing** (``Spell.HEAL``, one of the ten secret-ordinal
  spells [2.0], Personal-Combat-only) was added in ``turn/encounter.py``'s
  own Phase 200 addendum -- an eleventh Personal-Combat spell alongside
  the ten above, granted via ``AdvancedAbility.WORDS_OF_HEALING_SPELL``
  (White Magic skill 5+) rather than the base-skill-1+ gate the other
  ten use. **Wired into ``turn/search_execution.py``'s own
  ``_resolve_cast_tactic()`` as of Phase 289** -- see that module's own
  Phase 289 addendum -- alongside every other Personal-Combat-only spell
  named above, all of which were wired there across Phase 209-238. The
  broader "no real tactic-walk engine exists" framing this paragraph
  used through Phase 288 is stale for Search specifically (it still
  holds for Challenge/Pursue, which don't reuse that dispatch yet).

**Every province-targeted spell here shares one targeting mechanism**:
``CastRequest.target`` is a raw hex number (rulebook: "the province you
are in, or one adjacent to it," except Bless, which has no such
restriction). ``_resolve_province_target`` decodes it via
``turn/hex_numbering.py``'s empirically-derived scheme (Phase 11 -- not
100% validated against real adjacency, see that module's own docstring)
and enforces each spell's own same-or-adjacent rule. ``execute_cast``
now takes an optional ``board_width`` (default: the standard 30-wide
board, ``turn/movement.py NORMAL_MAP_BOUNDS``), the same value
``turn/plan_dispatch.py`` already threads through for Move's own hex
decoding.

**The success/failure roll (Phase 30, updated Phase 192)**: rulebook
[3.10], "The chance that an action spell will succeed is 15% plus 15%
per level," and "A character may cast a spell in a Magical ability only
if he has a skill level of 1 or higher in that ability." Resolved via
``LeaderState.skills`` when the caster has it recorded; ``skills is
None`` (no ability data at all) makes every cast succeed outright, same
placeholder convention as Phase 29.

**Phase 192 addendum -- the user directly re-quoted Regolamento AK.txt
[3.10] in full, confirming two facts this module had gotten wrong or
left unconfirmed:**

1. **The 95% cap is universal, not just a theoretical ceiling.**
   "Le probabilità di successo per incantesimi non possono mai superare
   il 95%." Previously `_roll_cast_success()` computed `chance`
   uncapped -- at skill level 6+ (15% + 15%*6 = 105%), `rng.random() <
   chance` was *always* true since `random()` never reaches 1.0, so in
   practice the cap was already 100% by accident, not the confirmed
   95%. `ACTION_SPELL_CHANCE_CAP = 0.95` now clamps `chance` for real,
   meaning a level-6+ caster now has a genuine (if small) 5% chance of
   failure that didn't exist before this phase. No existing test
   relied on the old uncapped behavior (every success-path test
   already scripted an explicit roll rather than assuming a guaranteed,
   no-roll outcome), confirmed non-breaking.
2. **Pagan Kingdoms get +10% on every spell except White Magic.** "I
   Reami Pagani... sono coadiuvati da un Ordine di Maghi. Tutti i
   personaggi appartenenti a quel Reame hanno quindi un modificatore
   +10% nei loro tentativi di lanciare qualsiasi incantesimo fuorché
   quelli di Magia Bianca." `PAGAN_MAGE_ORDER_BONUS = 0.10`, applied
   inside `_roll_cast_success()` via the new `_caster_kingdom_is_pagan()`
   helper -- the same "look up ``state.kingdoms[caster.kingdom_id]``'s
   own ``alignment``" pattern `turn/encounter.py`'s own
   `NEUTRAL_DUELIST_BONUS` (Neutral Kingdoms' Order of Duelists, [5.0])
   already established for a structurally identical rule, just for
   spellcasting instead of Melee/Archery. `_roll_cast_success()` now
   takes `state: GameState` as its own first parameter (every one of
   its 13 call sites already had `state` in scope, since `execute_cast`
   threads it through every `_execute_*` helper).

**Not modeled this phase, confirmed facts only** (the same Regolamento
AK.txt [3.10] excerpt also covers two turn-level quota mechanics this
project has no state to enforce yet): "Si può usare un Talento magico
per lanciare un Incantesimo di Azione per turno di gioco (al livello 3
due, al livello 4 tre)... Un personaggio può usare un Talento Magico
per lanciare un Incantesimo di Combattimento Individuale per qualsiasi
numero di incontri... ma non può lanciare due volte lo stesso
incantesimo nel medesimo incontro." Enforcing either limit needs a
per-turn Action-Cast counter and a per-encounter Personal-Combat-cast
history that neither `GameState` nor `turn/turn_processor.py` track
today -- recorded here as a confirmed, sourced gap, not implemented.
Likewise "Ogni Talento magico comprende cinque incantesimi di base" is
descriptive flavor text with no new numeric fact to model (the five
spells per Talent are exactly the ones `_SPELL_ABILITY`/`turn/
encounter.py`'s own ten Personal-Combat spells already enumerate).

**Phase 193 addendum -- Clairvoyance and Hide_Feature now execute,
correcting two Phase 60-era blocker claims above:**

1. **Hide_Feature's own "unpopulated `Feature` stub" claim above is
   stale.** Phase 75 (long before this project reached Hide_Feature)
   replaced `models/map.py`'s never-populated `Feature` stub with a
   real, populated model (`models/feature.py`) plus a real
   `GameState.features`/`features_at(coord)` registry -- nobody
   circled back to re-attempt this spell once that landed. [4.23.3]'s
   rulebook section maps to `Ability.ILLUSION` (confirmed by
   cross-referencing `_SPELL_ABILITY`'s existing `Illus_Terrain`/
   `Illus_Armies` entries, both drawn from the same [4.23] block).
   `CastRequest.target` for Hide_Feature only ever decodes to a
   *province* coordinate (`turn/cast_decode.py PROVINCE_TARGET_SPELLS`
   -- confirmed against all 108 real sample Cast phases, none carries a
   feature-instance id the way Illus_Terrain's own `phase.extra[1]`
   does). Since [3.2] itself says "There can sometimes be more than 1
   feature in a province," and nothing in the decode layer can name
   *which* one, `_execute_hide_feature` hides **every** `Feature` at
   the resolved coordinate -- a deliberate, unsourced judgment call
   (documented on the function itself), not a guess at a
   disambiguation mechanism this project has no data to build. Sets
   the new `Feature.magically_hidden` flag; no consuming Explore/Search
   discovery-roll reads it yet, the same "spell writes real state,
   nothing reads it yet" situation as `ProvinceState.illusory_terrain`.
2. **Clairvoyance's blocker is real, but the "`report/prose.py`'s own
   Phase 58 docstring" citation above was never accurate** -- a direct
   read of that docstring confirms the phrase "story event" appears
   nowhere in it; the framing originated and stayed local to this
   module. The underlying gap (no game-state mechanism recording "what
   a character did this turn, visible to another kingdom") is still
   real and still unbuilt this phase. [4.22.3] maps to
   `Ability.PSYCHIC` (same cross-referencing method as Hide_Feature,
   via `Charm`/`Oratory`'s existing [4.22]-block entries). What Phase
   193 *does* model is only the confirmed half of the sentence -- see
   `LeaderState.clairvoyance_watchers` in `models/game_state.py`'s own
   docstring: a successful cast adds the caster's `kingdom_id` to the
   target's watcher set. No event feed exists to actually surface
   anything to that watcher yet. **Phase 408**: traced this gap to its
   real Pascal mechanism (`RUMORS.PAS Set_Intel`'s own Clairvoyance
   block) and confirmed it's unreachable dead code in the available
   archive -- see `LeaderState.clairvoyance_watchers`'s own Phase 408
   addendum and `turn/world_events.py`'s module docstring for the full
   citation trail. No event-feed reader is planned; this isn't a "not
   yet built" gap anymore, it's a "the source never really did this"
   finding.

Neither spell gained a co-location/adjacency precondition beyond what
was already sourced: Hide_Feature reuses the standard same-or-adjacent
province rule every other province-targeted spell here already
enforces; Clairvoyance's own sourced text names no such restriction, so
none was invented (unlike Kill_Enemy's own explicit "not co-located"
check, which is Kill_Enemy-specific).

**Secret spells (ordinals 25-34), outside the 25 documented ``Spell``
members counted above**: 10 further spells ``models/advanced_ability.py``
already confirmed real via its own ``ADVANCED_ABILITY_GRANTS_SPELL``
table (Phase 128) -- each granted once a caster reaches skill 5+ in its
base ``Ability`` (``AdvancedAbility``'s own skill-5-and-up mechanic),
and none of them had any ``SPNOTE.X2``/rulebook text anywhere in this
project's archive until the user began supplying each one's own rule
text directly, one at a time.

- **Gate Angel** (``AdvancedAbility.GATE_ANGEL_SPELL``, ``Ability.WHITE``,
  Phase 194, corrected Phase 195) -- the user's own quoted rule text
  (verbatim, matching ``models/advanced_ability.py
  ADVANCED_ABILITY_DESCRIPTION`` word for word): "a hero of the same
  alignment as the spellcaster passes [through a gate to Valhalla]...
  The hero appears at the end of the current gameturn. Only one
  Valhalla hero can visit the world during a turn, so no other king
  will receive a visitor from Valhalla. Each alignment from Good to
  Evil can still be visited only once in each 5-turn period (for this
  spell, Divine kingdoms are treated as Good, and Undead as Evil). If
  more than one player casts the Gate Angel spell, one of the spells
  will be nullified. The spellcaster has no control over which hero
  arrives from Valhalla."

  1. **"The spellcaster" reads as the acting Kingdom's own alignment**
     (``state.kingdoms[kingdom_id].alignment``) -- the same "which
     Kingdom this cast concerns" convention ``_execute_charm``'s
     ``target.kingdom_id = kingdom_id`` write already establishes, not
     ``LeaderState.alignment`` (frequently unrecorded/``None``, and this
     rule names no fallback for that case). Unchanged by Phase 195.
  2. *(Phase 194's original judgment calls 2 and 3 -- "first-come-
     first-served" tie-break and "per-alignment independent 5-turn
     cooldown" -- are both superseded by the "Phase 195 addendum"
     below, which the user's own follow-up message corrected with the
     real VALHALLA mechanic. Kept here, struck through in spirit not in
     text, per this project's "correct via addendum, don't rewrite
     history" convention.)*

  **Phase 195 addendum -- the user supplied the full VALHALLA mechanic
  this spell draws its hero from, quoted in full (Italian original,
  the user's own words) plus a following English-language paragraph
  matching this project's usual ADDEND.AK-style source text:**

  "Ciascun allineamento da Buono a Malvagio (quindi non Divine o
  Undead) riceverà una visita una volta ogni cinque turni (se c'è più
  di un giocatore in un allineamento, la scelta verrà fatta a caso)...
  Solo un visitatore dal Vahlalla a turno... I personaggi appariranno a
  fianco del Re... I re Non-Morti e Divini possono entrare nel Vahlalla
  come Buoni o Malvagi, ma non ricevono visite dal Vahlalla... Il
  numero d'ordine del visitatore dal Vahlalla sarà sempre #199."

  This corrects two Phase 194 design errors and confirms new facts:

  1. **The "per-alignment independent 5-turn cooldown"
     (``_gate_angel_alignment_group()``/``gate_angel_alignment_cooldown``)
     was wrong -- replaced by the real mechanic, a rotating exclusion
     cycle over exactly 5 alignments.** "Da Buono a Malvagio" is exactly
     the 5 ``Alignment`` members strictly between ``DIVINE`` (ordinal 0)
     and ``UNDEAD`` (ordinal 7) in ``models/alignment.py``'s own
     ``ALIGNMENT_ORDINAL`` table -- ``GOOD``, ``DRUID``, ``NEUTRAL``,
     ``PAGAN``, ``EVIL`` (``GATE_ANGEL_ELIGIBLE_ALIGNMENTS``), excluding
     not just ``DIVINE``/``UNDEAD`` but also ``ANTI_HOLY``,
     ``MECHANICAL``, ``SPECIAL``. Each 5-turn cycle randomly orders
     these 5 without repetition (``GameState.gate_angel_cycle_visited``,
     cleared once all 5 have had their turn) -- ``_gate_angel_due_
     alignment()`` picks (and caches, once per ``turn_number``) which
     alignment is "due" the first time any Gate Angel cast is attempted
     that turn, exactly mirroring the user's own worked example (turn 0
     Druid, turn 1 not-Druid picks Evil, ..., turn 5 restarts with all 5
     eligible again).
  2. **Divine and Undead kingdoms never receive a visit at all** -- "ma
     non ricevono visite dal Vahlalla" is unconditional, contradicting a
     literal reading of the original Gate Angel spell text's own
     "Divine kingdoms are treated as Good, and Undead as Evil" as
     meaning they share the Good/Evil visit slot. The user's newer,
     more detailed text is authoritative: that phrase instead describes
     which roster a Divine/Undead King's *own* future legendary
     character joins if *they* achieve Valhalla entry -- a fact about
     Valhalla's own membership, not about who can *receive* a visit.
     Since ``GATE_ANGEL_ELIGIBLE_ALIGNMENTS`` never contains ``DIVINE``
     or ``UNDEAD``, a Divine/Undead kingdom's cast always fails with
     "not this alignment's turn for a Valhalla visit" -- no special-case
     check needed.
  3. **"If more than one player casts... one is nullified" /
     "la scelta verrà fatta a caso" is now modeled as genuine uniform
     randomness**, via reservoir sampling (``_gate_angel_register_
     candidate()``): every due-alignment caster whose own roll succeeds
     is a candidate, and each new candidate replaces the current
     ``GameState.last_gate_angel_kingdom``/``last_gate_angel_turn``
     with probability ``1/N`` (``N`` = candidates seen so far this
     turn) -- a well-known single-pass algorithm that produces a
     uniformly random winner among all of a turn's candidates without
     needing new end-of-turn batch-resolution machinery (the concern
     Phase 194's own addendum raised and initially declined to build).
     **This means ``CastExecutionResult.applied=True`` reflects "this
     cast's own roll succeeded and it entered the drawing," not
     necessarily "this kingdom's hero is the one that actually
     arrived"** -- the same distinction this project's contested-
     province Move orders already draw (a successful order can still
     lose a later contest); the authoritative "who actually got the
     visit" fact is ``GameState.last_gate_angel_kingdom`` after the
     whole turn's dispatch completes, not any single ``CastExecutionResult``.
  4. **Confirmed but genuinely out of scope this phase** -- each
     requires either data this project doesn't have or a subsystem this
     project has never built, cited so a future phase can pick them up
     without re-deriving them:
     - **The Valhalla hero itself is still not synthesized as a real
       ``LeaderState``.** The user's own plan is 5 per-alignment roster
       files (Good/Druid/Neutral/Pagan/Evil) of named legendary heroes
       to draw from -- not yet supplied. Once supplied, the confirmed
       structural facts to apply are already known: **leader id is
       always ``199``** ("Il numero d'ordine... sarà sempre #199" --
       every other ``LeaderState`` in this project gets its id via
       ``GameState.new_army_id()``-style monotonic allocation; a
       Valhalla visitor does not), and **spawns at the recipient King's
       own location** ("appariranno a fianco del Re" -- found via
       ``is_king=True`` among the winning kingdom's leaders, not
       necessarily the casting leader).
     - **Escalating per-visit action allowance** (1 action turns 1-2, 2
       actions turns 3-4, ... 5 actions from turn 9 on) is a
       plan-*authoring* constraint (how many phases the visitor's own
       plan may contain), and this project has no plan-authoring system
       at all anywhere -- it only decodes/executes plans that already
       exist as parsed ``K1`` files. No consumer exists to enforce this
       even if modeled.
     - **The visitor's fixed, always-the-same, non-transferable magic
       item** ("un oggetto magico prefissato... che non possono dare a
       nessuno... Se muoiono... l'oggetto sparisce alla fine del
       turno") depends on the same unsupplied per-hero roster data
       above (which fixed item goes with which named hero).
     - **Practice limited to one phase of the stay, spell-immunity
       except Resurrection, army hand-off to the lowest-numbered
       leader (or adjacent-province garrison commander) on departure,
       and turn-deadline voiding** (the trailing English-language
       paragraph the user quoted) are all real, specific, and
       eventually implementable rules -- but every one of them
       presupposes the hero actually exists as a ``LeaderState`` with a
       real ``leader_id=199`` and a real stay-duration, which doesn't
       exist yet per the point above. Recorded here as confirmed,
       sourced facts awaiting that prerequisite, not silently dropped.

  ``Spell.GATE_ANGEL`` is added to ``turn/cast_decode.py``'s
  ``NO_TARGET_SPELLS`` -- the rulebook text names no target field at all
  ("the spellcaster has no control over which hero arrives"), matching
  Skeletal_Army's own precedent. No real sample data exists to validate
  this decode against (``cast_decode.py``'s own docstring already notes
  the Trade->Cast rewrite for secret spells 25-34 is "deliberately not
  handled" anywhere in this project), so this is a structural inference
  from the rule text, not confirmed against real Cast phases the way the
  25 documented spells are.

- **Scar Terrain** (``AdvancedAbility.SCAR_TERRAIN_SPELL``,
  ``Ability.NECROMANCY``, Phase 201) -- the user's own quoted rule text
  (verbatim): "-2 Taxation, Change Race at 0. New spell (can be casted
  using the command CA-ST): By the horrible power of this spell, a
  co-located or adjacent province is scarred and mangled, and its tax
  base is reduced by 2 gold immediately and permanently. When the tax
  base reaches 0 gold, the province becomes incapable of supporting
  normal life forms. If it's a land province, the racial type will
  change to Orcs, Dragons or Trolls (usually by immigration from an
  adjacent province) and the army type will change to something
  suitable to the new racial type. Sea provinces will just lose
  whatever provincial racial and army type they may have." Unlike Gate
  Angel, this one names a real target ("a co-located or adjacent
  province"), the same shape as every other province-targeted spell
  here -- added to ``turn/cast_decode.py PROVINCE_TARGET_SPELLS``, not
  ``NO_TARGET_SPELLS``.

  1. **The -2 gold reduction is fully modeled**: ``_execute_scar_
     terrain`` increments the new ``ProvinceState.scar_terrain_gold_
     reduction`` field by ``SCAR_TERRAIN_TAX_REDUCTION`` (2) on every
     successful cast, uncapped (no maximum is stated, the same
     "uncapped when no cap is given" treatment ``turn/encounter.py
     roll_hand_of_death_damage()`` established) and cumulative
     ("immediately and permanently" -- an add, not a set, unlike
     Earthquake's own ``tax_modifier_percent`` which is explicitly "not
     cumulative"). No terrain restriction and no skill-level scaling --
     the text gives neither, unlike Tornado's per-level destroy chance.
  2. **"When the tax base reaches 0 gold" is a real, sourced trigger
     this project genuinely cannot fire from real state yet.** This
     project has no tax/revenue-collection system anywhere (same gap
     ``ProvinceState.tax_modifier_percent``'s own docstring already
     flags) -- no province anywhere carries a real starting gold-value
     tax base to subtract ``scar_terrain_gold_reduction`` from, so
     there is no way to know from real ``GameState`` data whether any
     given province's tax base has actually reached zero.
     ``scar_terrain_is_exhausted(remaining_tax_base)`` models the
     *check itself* as a pure function (the same "caller supplies the
     otherwise-unavailable precondition" pattern ``turn/encounter.py``
     uses throughout, e.g. Ice Suspension's own ``victim_hit_points``
     parameter) so a future revenue-system phase can call it directly
     once a real remaining-tax-base value exists -- **not auto-invoked
     inside ``_execute_scar_terrain`` itself**, since nothing in this
     project can supply that value today.
  3. **The collapse effect itself is modeled as a second pure
     function, ``scar_terrain_collapse``, deliberately not
     auto-triggered for the same reason.** Sea provinces ("will just
     lose whatever provincial racial and army type they may have")
     unconditionally become ``Race.NO_RACE`` -- the enum's own
     dedicated "no race" member, confirmed to already suppress every
     ``ArmyType``'s recruit-compatibility check (``turn/recruit.py
     is_army_type_compatible_with_race`` returns ``False`` for every
     ``ArmyType`` against a province race that's neither in
     ``HUMANOID_RACES`` nor a ``MONSTROUS_ARMY_RACE`` key), so no
     separate "clear the province's army type" state is needed at all.
     Land provinces need a caller-chosen ``new_land_race`` from
     ``SCAR_TERRAIN_LAND_COLLAPSE_RACES`` (``Race.ORCISH``,
     ``Race.DRAGONS``, ``Race.TROLLISH``) -- **which of the three is
     genuinely unspecified**: "usually by immigration from an adjacent
     province" describes an external, caller-known fact (what races
     border this province), not a formula this function can compute
     from the province alone, so the choice is left to the caller
     rather than guessed (e.g. via ``rng.choice``, which the text never
     suggests). **"The army type will change to something suitable to
     the new racial type" needs no new state either**, for Dragons and
     Trolls specifically: ``models/army_type.py MONSTROUS_ARMY_RACE``
     already maps ``Race.DRAGONS``/``Race.TROLLISH`` to exactly one
     compatible ``ArmyType`` each (``DRAGON_WING``/``TROLLS``) via the
     same recruit-compatibility check above -- changing
     ``ProvinceState.race`` alone is sufficient, the existing recruit
     machinery reflects the new eligibility automatically. Orcish has
     no such single dedicated ``ArmyType`` (it's a ``HUMANOID_RACES``
     member, compatible with every non-monstrous type at once) -- "the"
     suitable army type for an Orc collapse is left unresolved, a
     genuine gap with no formula given, not silently guessed.
  4. **Phase 411 addendum -- the bystander report notice for this
     collapse was investigated and confirmed permanently unreachable,
     not merely unwired.** ``SAY.PAS`` ``_STZero``/``_STFite`` (~747-748)
     are real, fully-sourced inline ``Say()`` strings (no missing
     ``PROSE/*.X2`` file) for GENERAL INTELLIGENCE REPORT's own
     bystander view of a collapsed province -- but since ``scar_terrain_
     collapse()`` above is never called from any real dispatch path (the
     same tax-base precondition this addendum's own point 2 already
     established this project can't check), no ``report/turn_report.py``
     world-events recorder has anything to call it from. Wiring the
     notice itself would be trivial; the blocker is entirely upstream,
     in the missing tax/revenue system. See ``report/turn_report.py
     describe_general_intelligence_report()``'s own docstring for the
     full citation.

- **Mystic Winds** (``AdvancedAbility.MYSTIC_WINDS_SPELL``,
  ``Ability.ELEMENTAL``, Phase 204) -- the user's own quoted rule text
  (verbatim, matching ``models/advanced_ability.py
  ADVANCED_ABILITY_DESCRIPTION`` word for word): "Wind-Walking Armies.
  By the mysterious power of the 'Mystic Winds' spell, the great Wind
  Spirits of the heavens carry the mage or a co-located character into
  the sky, his fleets propelled through the air by magic breezes, his
  armies effortlessly wind-walking through the clouds. Each unit led
  by the affected leader has its movement set at 5 while the spell
  lasts and moves as an air unit. No fleet transport or air transport
  takes place: that is, each unit will use up movement points while
  under the effect of this spell. The spell ends just before the
  leader gets involved in any military battle between armies." Unlike
  Gate Angel/Scar Terrain (the two prior secret spells), this one is
  explicitly not a combat spell ("questo non è un incantesimo da
  combattimento," the user's own framing) and targets "the mage or a
  co-located character" -- a character target, the same shape as
  Oratory/Phantasmal Armies (``Spell.ILLUS_ARMIES``) above, not a
  province or no-target spell. Added to ``turn/cast_decode.py
  CHARACTER_TARGET_SPELLS``.

  1. **The movement-points effect is fully modeled, mirroring Oratory's
     own "direct persistent state write" precedent rather than a
     strength-pipeline multiplier**: on a successful cast,
     ``_execute_mystic_winds`` sets ``target.mystic_winds_active =
     True`` and, for every ``ArmyState`` the target currently commands
     (``state.armies_commanded_by``, evaluated once at cast time, the
     same "currently commanded" snapshot Oratory/Phantasmal Armies
     already use), sets ``ArmyState.movement_points =
     MYSTIC_WINDS_MOVEMENT_POINTS`` (5) -- a hard *set*, matching "has
     its movement set at 5" verbatim, not an addition. No idempotency
     guard is needed (unlike Oratory's own ``oratory_boosted_this_turn``
     check): setting an absolute value twice has the same effect as
     once, so repeated casts are naturally non-cumulative without extra
     state. An army the leader picks up *after* the cast is not
     retroactively affected, the same "snapshot at cast time" reading
     Oratory's own army-quality bump already established.
  2. **"Moves as an air unit" is a confirmed fact, not modeled.** This
     project's only existing "air unit" classification
     (``models/army_type.py OVERFLIGHT_AIR``) is a static, per-
     ``ArmyType`` property (Dragon Wing/Eagle Wing) consumed by combat
     rear-targeting and ``turn/movement.py``'s own terrain-cost rules --
     neither pipeline has a per-leader, per-cast override mechanism, and
     mutating ``ArmyState.army_type`` itself to fake it would corrupt
     every other lookup keyed by that field (quality, nemesis, recruit
     eligibility). ``MYSTIC_WINDS_MOVES_AS_AIR_UNIT = True`` records the
     fact for whichever future phase builds that override, the same
     "confirmed, not modeled" treatment Gate Demon's own "double
     dissipation" facts got.
  3. **"No fleet transport or air transport takes place" is likewise
     confirmed but has no subsystem to negate.** This project has never
     built a fleet-transport or air-transport mechanic anywhere (the
     term only otherwise appears in ``report/turn_report.py``'s own
     Illegal-Move narration template, never as executable logic), so
     this sentence is recorded as ``MYSTIC_WINDS_USES_MOVEMENT_POINTS_
     NORMALLY = True`` with nothing left to actually disable.
  4. **"The spell ends just before the leader gets involved in any
     military battle between armies" is wired as of Phase 250.** Every
     real army-vs-army battle in this project turned out to funnel
     through a single real function -- ``turn/battle_orchestrator.py
     fight_battle()`` -- confirmed by grepping every call site
     (``move_execution.py``, ``pursue_execution.py``, ``turn_
     processor.py``'s forced-rebattle path, and ``fight_multi_attacker_
     battle()``, which itself calls ``fight_battle()`` once per group),
     so clearing ``mystic_winds_active`` there once, for both sides,
     covers every one of those entry points without touching any of
     them -- a much narrower fix than this addendum originally
     estimated. See ``fight_battle()``'s own ``_clear_mystic_winds_
     before_battle()`` helper docstring for the exact mechanics,
     including why ``ArmyState.movement_points`` is deliberately left
     untouched (nothing in this project derives a per-``ArmyType``
     normal value to reset it to).
     ``MYSTIC_WINDS_ENDS_BEFORE_ARMY_BATTLE = True`` still records the
     underlying fact. Also cross-referenced by ``models/advanced_
     ability.py``'s own Illusory Fog description ("All air units...
     and those affected by 'Mystic Winds' Spell... have their strength
     halved", wired Phase 249) -- since the flag is now cleared
     *before* ``_build_battle_units()`` reads it for that very battle,
     a leader entering combat this turn no longer gets Illusory Fog's
     Mystic-Winds-affected treatment from an about-to-end cast, only
     from being a naturally static air unit -- the literal reading of
     "ends just before," not a guess.

- **Locate Object** (`AdvancedAbility.LOCATE_OBJECT_SPELL`,
  `Ability.PSYCHIC`, Phase 206) -- the user's own quoted rule text
  (verbatim, matching `models/advanced_ability.py
  ADVANCED_ABILITY_DESCRIPTION` word for word): "By the enchanting
  power of this spell, the provincial location of any magic item will
  be revealed to the spellcaster, as well as who is guarding the item,
  if anyone. If the magic item was lost to a wandering monster, it
  will be seen as guarded by a monster. The Psychic must specify the
  identifying number of the magic item, not the treasure name itself
  -- this is because there is sometimes more than one of the same
  magic item in the game." Not a combat spell (confirmed by the user's
  own framing) and, unlike every spell above, its target is an
  item-instance id (`models/item.py ItemInstance.item_id`) rather than
  a character, province, or nothing -- added to `turn/cast_decode.py`'s
  new `ITEM_TARGET_SPELLS`, the fourth target-shape category.

  1. **The cast-success roll is fully modeled, the same as every other
     spell** -- `_execute_locate_object` gates on
     `_roll_cast_success()` and mutates nothing (this is a pure
     information query, unlike every mutating spell above).
  2. **The actual query is a separate primitive, `locate_object(state,
     item_id)`, deliberately outside `CastExecutionResult`'s own
     applied/reason shape** -- `CastExecutionResult` is shared across
     every spell in this module and carries no per-spell payload field
     by design; a successful cast is the gate a future report layer
     would check before calling this query, mirroring how every other
     "confirmed effect, not yet wired to the report layer" spell above
     keeps its own real primitive separate from `execute_cast()`'s own
     side-effect-free dispatch. Returns `LocateObjectResult(location,
     holder_leader_id)` for a leader-held item, `None` otherwise.
  3. **Only the leader-held half of "who is guarding the item, if
     anyone" is answerable at all -- confirmed absent, not guessed.**
     `models/item.py`'s own module docstring already scopes
     `ItemInstance` to leader-held items only: the real Pascal
     structure also tracks feature/monster-guarded treasure via a
     `feature_id + 256` owner-array convention, but that half was
     explicitly never modeled ("this project has no monster/feature
     loot-generation pipeline at all"). So `locate_object()` returns
     `None` for any `item_id` that doesn't exist in `GameState.items`
     or whose `owner_leader_id` is `None` -- which covers both "unknown
     item" and "guarded by a monster/lost to a wandering monster,"
     since this project has no data to distinguish those two cases
     from each other. Confirmed as a real, sourced gap (the same
     `item.py` scope boundary this project already accepted for
     Trade/Give, Phase 133), not silently guessed at.

- **Illusory Fog** (`AdvancedAbility.ILLUSORY_FOG_SPELL`,
  `Ability.ILLUSION`, Phase 207) -- the user's own quoted rule text
  (verbatim, matching `models/advanced_ability.py
  ADVANCED_ABILITY_DESCRIPTION` word for word): "Slow and Weaken Air
  Armies. By the murky power of the 'Illusory Fog' spell, the
  Illusionist summons a dense fog to blanket a province, reaching up
  to the very heavens. All air units (Dragon Wings, Eagle Wings and
  those affected by 'Mystic Winds' Spell) have their strength halved
  for any battle in the affected province, and must expend 1
  additional movement point when entering or leaving it. The movement
  point is deducted after the unit(s) have already moved. The spell
  must be cast on an adjacent or co-located province, and it
  dissipates at the end of the gameturn." Not a combat spell
  (confirmed by the user's own framing), and a province target -- the
  same shape Scar Terrain already established -- added to
  `turn/cast_decode.py PROVINCE_TARGET_SPELLS`.

  1. **The cast itself is fully modeled, the same "co-located or
     adjacent province" pattern `_execute_scar_terrain` already
     established**: `_execute_illus_fog` resolves the target via
     `_resolve_province_target`, rolls cast success, and on success
     sets the new `ProvinceState.illusory_fog_active = True` -- a
     persistent flag, the same "spell writes real state, no consuming
     pipeline exists yet" shape `illusory_terrain`/`scar_terrain_gold_
     reduction` already use above.
  2. **The strength-halving effect has a real, testable primitive,
     wired into the battle-strength pipeline as of Phase 249.**
     `ILLUSORY_FOG_STRENGTH_MULTIPLIER = 0.5` and
     `is_illusory_fog_affected_air_unit(army_type, mystic_winds_
     active)` combine the static `models/army_type.py OVERFLIGHT_AIR`
     membership with a per-army Mystic Winds flag -- resolved, as of
     Phase 249, by `turn/battle_orchestrator.py _mystic_winds_active_
     for()` the same "derive from the commanding leader, 0/False for an
     unled army" pattern `_phantasmal_armies_level_for()` already
     established, closing the "no per-army way to derive that flag"
     gap this addendum originally flagged. `illusory_fog_strength(base_
     strength, affected=...)` applies the halving, called from
     `turn/strength.py compute_effective_strength()`'s own new
     `illusory_fog_affected` parameter. `_build_battle_units()` looks
     up `state.provinces.get(province_coord).illusory_fog_active`
     once per side and combines it with each army's own Mystic-Winds-
     derived affected flag -- see that function's own docstring.
  3. **The movement surcharge is wired (Phase 651); end-of-turn
     dissipation is still not.** `ILLUSORY_FOG_EXTRA_MOVEMENT_COST = 1`
     ("must expend 1 additional movement point when entering or
     leaving it... deducted after the unit(s) have already moved") is
     applied in `turn/move_execution.py execute_move()`, right
     alongside `turn/conquest.py movement_cost_for_move()`'s own
     deduction -- kept separate since it targets only `is_illusory_fog_
     affected_air_unit()` units, not the whole moving party, using
     `turn/battle_orchestrator.py mystic_winds_active_for()` (made
     public this same phase) for the per-army Mystic Winds check, the
     identical derivation the strength-halving effect above already
     uses. `ILLUSORY_FOG_DISSIPATES_AT_END_OF_GAMETURN = True` records
     "it dissipates at the end of the gameturn" -- still the same
     unresolved "when does a persistent province-level spell flag get
     cleared" gap this project's own `tax_modifier_percent`/`illusory_
     terrain` fields already carry, with no end-of-turn cleanup pass
     built for any of them yet.

**Level-dependent magnitudes with no recorded caster skill** (Tornado's
per-unit destroy chance, Plague's per-unit destroy chance, Illus_Armies'
strength bonus): fall back to level 0 (no effect), the same "no data ->
no numeric effect" convention ``turn/battle_orchestrator.py``'s
``compute_druidic_shortfall`` already uses, not a guessed level -- see
``_caster_level``.

**``wand_skill_level`` (Phase 141)**: every one of the 20 spell-casting
wands (``models/treasure.py Treasure.SPELL_WAND``) has its own
``TREASAB.X2`` label reading ``"Cast '<Spell>' at skill-2"`` -- e.g.
``Treasure.WAND_FIREBALL``'s own ``TREASURE_LABEL`` entry, transcribed
verbatim in Phase 77. Combined with rulebook [3.11]'s "A spell cast
from a magic item is automatically successful," a wand-triggered cast
is a genuinely different mechanic from a real Cast order: no success
roll at all, and every level-dependent magnitude computed as if the
caster had exactly skill level 2 in the relevant ability, regardless of
what (if anything) ``LeaderState.skills`` actually records. ``turn/
use_mi_execution.py`` (Phase 141) is the only caller that ever passes
this; every existing Cast caller/test leaves it ``None`` and gets the
prior behavior unchanged.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from ak_engine.models.advanced_ability import AdvancedAbility
from ak_engine.models.alignment import ALIGNMENT_BY_ORDINAL, ALIGNMENT_ORDINAL, Alignment
from ak_engine.models.army_type import OVERFLIGHT_AIR, ArmyType
from ak_engine.models.discovery import Discovery
from ak_engine.models.enums import Ability, Spell
from ak_engine.models.game_state import ArmyState, GameState, LeaderState, ProvinceState
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.office import Office
from ak_engine.models.race import HUMANOID_RACES, Race
from ak_engine.models.temper import Temper
from ak_engine.models.treasure import ENHANCED_CHARM_ELIGIBLE_CATEGORIES, TREASURE_CATEGORY
from ak_engine.models.valhalla import VALHALLA_VISITOR_LEADER_ID
from ak_engine.turn.cast_decode import CHARACTER_TARGET_SPELLS, CastRequest
from ak_engine.turn.combat import Quality
from ak_engine.turn.discovery_effects import effective_skill_level, holder_is_immune_to_spell, province_halves_spell_chance
from ak_engine.turn.encounter import (
    CHARACTER_HIT_POINTS,
    Combatant,
    MeleeSwing,
    archery_free_attack_bonus,
    loot_defeated_leader,
    melee_mastery_damage_bonus,
    melee_mastery_offensive_hit_multiplier,
    resolve_melee_duel,
)
from ak_engine.turn.experience import add_experience
from ak_engine.turn.hex_numbering import decode_hex_number
from ak_engine.turn.movement import NORMAL_MAP_BOUNDS, MapBounds, is_adjacent
from ak_engine.turn.office_holder import resolve_all_office_holders, resolve_office_holder

ACTION_SPELL_BASE_CHANCE = 0.15
ACTION_SPELL_CHANCE_PER_LEVEL = 0.15

# Regolamento AK.txt [3.10] (Phase 192): "Le probabilita' di successo per
# incantesimi non possono mai superare il 95%" -- a universal cap on every
# spell-cast success chance, not just Action-Cast's own formula.
ACTION_SPELL_CHANCE_CAP = 0.95

# [3.10]: "I Reami Pagani... sono coadiuvati da un Ordine di Maghi... un
# modificatore +10% nei loro tentativi di lanciare qualsiasi incantesimo
# fuorche' quelli di Magia Bianca."
PAGAN_MAGE_ORDER_BONUS = 0.10

# Office.PAGAN_KING's own second, unique perk (models/office.py
# OFFICE_TITLE_DESCRIPTION, Phase 664): "The League will supply all
# your Pagan characters with charms which will add 10% to their chance
# to cast a White Magic spell." Genuinely separate from PAGAN_MAGE_
# ORDER_BONUS above -- that one is alignment-based (any Pagan Kingdom,
# every school except White) and pre-existing; this one is title-gated
# (only while a leader of this Kingdom holds PAGAN_KING) and White-
# Magic-only, the opposite polarity. The two branches are mutually
# exclusive (``ability is not Ability.WHITE`` vs. ``ability is Ability.
# WHITE``), so a Pagan Kingdom holding the title never double-counts.
PAGAN_KING_WHITE_MAGIC_BONUS = 0.10

# Office.GOOD_KING's own second, unique perk: "the Plague spell has a
# -15% chance of affecting any unit owned by your Kingdom or in its
# territory." Applied inside ``apply_plague_exposure()``.
GOOD_KING_PLAGUE_PROTECTION = 0.15

# AKGEN runtime_mechanics.spellcasting.action_slots_per_school (Phase 387):
# how many real Cast orders a leader may attempt per Ability, per turn,
# keyed by their own skill level in that Ability -- independent of the
# success-chance formula above, and independent of *which* spell in that
# Ability's own pool is attempted each time ("same_action_spell_may_
# repeat": true -- confirmed by scoping the slot counter to (leader,
# Ability) below, never to the specific Spell requested).
ACTION_CAST_SLOTS_LEVEL_1_TO_2 = 1
ACTION_CAST_SLOTS_LEVEL_3 = 2
ACTION_CAST_SLOTS_LEVEL_4_PLUS = 3

# The same AKGEN source also confirms 4 more real spellcasting rules,
# deliberately NOT wired here (Phase 387) -- each needs real plumbing
# this project doesn't have yet, not just a formula:
# - `combat_slots_per_school` (1 slot at level 1, 2 at level 2+, per
#   encounter): `turn/encounter.py resolve_personal_combat_spell_cast()`
#   is a single, stateless roll with no per-encounter, per-(leader,
#   Ability) call counter threaded through its own callers (`turn/
#   search_execution.py`, `turn/challenge_execution.py`) to gate against.
# - `places_of_power_bonus_percentage_points` (+20% to the roll): no
#   code anywhere checks whether a caster's own current location is a
#   Place of Power -- `models/power.py`'s own vocabulary exists, but
#   there's no live "this province/feature currently grants this real
#   bonus" state to consult.
# - `damp_magic` (halves the roll) / `damp_college` (blocks a specific
#   Ability's combat spells entirely inside that feature): same gap --
#   `Power.DAMP_MAGIC`/`Power.DAMP_COLLEGE` exist as pure vocabulary
#   (Phase 95), but no ProvinceState/Feature field records "this power
#   is the one currently active here" the way a live game would need.
# All 4 are real, confirmed rules -- left for a real follow-up phase
# that builds the underlying state each one actually needs.

# Regolamento AK.txt [4.25.3]: "10% di probabilita' di essere distrutte, piu'
# un 10% per livello dell'autore dell'incantesimo" (Plague).
PLAGUE_BASE_DESTROY_CHANCE = 0.10
PLAGUE_DESTROY_CHANCE_PER_LEVEL = 0.10

# [4.24.2]: "un 10% di probabilita' per livello del mago di essere distrutte" (Tornado).
TORNADO_DESTROY_CHANCE_PER_LEVEL = 0.10

# [4.22.1]: "+60% for one turn" (Bless) / [4.24.3]: zeroes revenue (Earthquake).
BLESS_TAX_BONUS_PERCENT = 60
EARTHQUAKE_TAX_MODIFIER_PERCENT = -100

# Discovery.txt (Phase 270, anti-spell ward Discoveries -- see module
# docstring's own Phase 270 addendum): each of these replaces the base
# spell's own effect for the defended side, rather than reducing it by a
# formula this project has any source for.
# Penicillin (vs Plague): "affected armies will have a 50% chance of
# losing one level of quality" -- flat, in place of the caster-level-scaled
# destroy chance.
PENICILLIN_QUALITY_DOWNGRADE_CHANCE = 0.50
# Giant Fan (vs Tornado): "a 50% chance of losing one level of quality" --
# in place of the caster-level-scaled destroy chance.
GIANT_FAN_QUALITY_DOWNGRADE_CHANCE = 0.50
# Reinforced Concrete (vs Earthquake): "income ... will only decrease by
# 3 gold" -- a flat gold reduction, replacing the -100%-revenue effect
# entirely (see ProvinceState.tax_flat_reduction).
REINFORCED_CONCRETE_TAX_REDUCTION = 3
# Propaganda Megaphones (vs Oratory, Phase 391 -- AKGEN's own confirmed
# `battle_engine.special_events` row, independently corroborated by
# this project's own pre-existing Discovery.txt flavor text, both
# saying the exact same "33%" figure): "each opposing army will have
# only a 33% chance of being affected by their leader's Oratory" --
# checked per army (not per caster/target pair), against *that army's
# own* kingdom_id, the same Giant-Fan-style per-army convention above.
PROPAGANDA_MEGAPHONES_AFFECTED_CHANCE = 0.33

# Scar Terrain (Phase 201, secret spell, user-supplied): "-2 Taxation...
# reduced by 2 gold immediately and permanently." An add, not a set --
# see module docstring's own Scar Terrain addendum for why this differs
# from Earthquake's own (not-cumulative) tax_modifier_percent.
SCAR_TERRAIN_TAX_REDUCTION = 2

# "the racial type will change to Orcs, Dragons or Trolls" -- which of
# the three is left to the caller (see module docstring); this is only
# the reference set of valid choices.
SCAR_TERRAIN_LAND_COLLAPSE_RACES = (Race.ORCISH, Race.DRAGONS, Race.TROLLISH)

# "NUOVE REGOLE E MODIFICHE": "L'incantesimo Benedizione (Bless) ora rimuove
# le unita' morte in una provincia. La probabilita' e' del 10% + 10% per
# livello in Magia Bianca di chi lancia l'incantesimo." (Phase 60.)
BLESS_GRAVEYARD_CLEAR_BASE_CHANCE = 0.10
BLESS_GRAVEYARD_CLEAR_CHANCE_PER_LEVEL = 0.10

# [4.24.1]: eligible for Flood -- land, non-mountain (Sea is already water;
# Mountain is explicitly excluded by the rulebook's own wording).
_FLOOD_ELIGIBLE_TERRAIN = frozenset({Terrain.PLAINS, Terrain.DESERT, Terrain.JUNGLE, Terrain.FOREST})

# Gate Angel (Phase 195, user-supplied VALHALLA text): "Ciascun allineamento
# da Buono a Malvagio (quindi non Divine o Undead)" -- the 5 Alignment
# members strictly between DIVINE (ordinal 0) and UNDEAD (ordinal 7) in
# models/alignment.py's own ALIGNMENT_ORDINAL table.
GATE_ANGEL_ELIGIBLE_ALIGNMENTS = (
    Alignment.GOOD,
    Alignment.DRUID,
    Alignment.NEUTRAL,
    Alignment.PAGAN,
    Alignment.EVIL,
)


def _gate_angel_clamped_alignment(alignment: Alignment) -> Alignment:
    """AKGEN's own confirmed ``validation_alignment_mapping``: "clamp to
    1..5, so Divine counts as Good and Undead as Evil" (Phase 386) --
    ``Max(1, Min(5, Ord(alignment)))`` on this project's own real
    ``ALIGNMENT_ORDINAL`` sequence. A Divine or Undead Kingdom is
    therefore genuinely eligible for a Gate Angel visit on its clamped
    alignment's own turn, not excluded outright as an earlier version of
    this module assumed.
    """

    ordinal = max(1, min(5, ALIGNMENT_ORDINAL[alignment]))
    return ALIGNMENT_BY_ORDINAL[ordinal]

# Mystic Winds (Phase 204, user-supplied): "Each unit led by the affected
# leader has its movement set at 5" -- a hard set, not a bonus. See the
# module docstring's own Phase 204 addendum for the remaining three
# confirmed-but-unmodeled facts.
MYSTIC_WINDS_MOVEMENT_POINTS = 5
MYSTIC_WINDS_MOVES_AS_AIR_UNIT = True
MYSTIC_WINDS_USES_MOVEMENT_POINTS_NORMALLY = True
MYSTIC_WINDS_ENDS_BEFORE_ARMY_BATTLE = True

_SPELL_ABILITY: dict[Spell, Ability] = {
    Spell.CHARM: Ability.PSYCHIC,
    Spell.KILL_ENEMY: Ability.NECROMANCY,
    Spell.RESURRECTION: Ability.WHITE,
    Spell.PART_SEA: Ability.WHITE,
    Spell.BLESS: Ability.WHITE,
    Spell.FLOOD: Ability.ELEMENTAL,
    Spell.TORNADO: Ability.ELEMENTAL,
    Spell.EARTHQUAKE: Ability.ELEMENTAL,
    Spell.ORATORY: Ability.PSYCHIC,
    Spell.PLAGUE: Ability.NECROMANCY,
    Spell.ILLUS_TERRAIN: Ability.ILLUSION,
    Spell.ILLUS_ARMIES: Ability.ILLUSION,
    Spell.SKELETAL_ARMY: Ability.NECROMANCY,
    Spell.CLAIRVOYANCE: Ability.PSYCHIC,
    Spell.HIDE_FEATURE: Ability.ILLUSION,
    Spell.GATE_ANGEL: Ability.WHITE,
    Spell.SCAR_TERRAIN: Ability.NECROMANCY,
    Spell.MYSTIC_WINDS: Ability.ELEMENTAL,
    Spell.LOCATE_OBJECT: Ability.PSYCHIC,
    Spell.ILLUS_FOG: Ability.ILLUSION,
}


@dataclass(slots=True)
class CastExecutionResult:
    request: CastRequest
    applied: bool
    reason: str | None = None  # set when applied is False
    # Phase 270: set when the defending side's own anti-spell ward
    # Discovery changed the spell's effect (see module docstring's own
    # Phase 270 addendum) -- ``applied`` stays True (the spell *was*
    # cast/resolved), this only flags that its outcome isn't the base,
    # un-defended one.
    discovery_defended: Discovery | None = None
    # Phase 310: Kill_Enemy's own [4.25.2] Berserk-retaliation-on-
    # failure -- "a" (caster survived, the retaliating target died in
    # the melee) / "b" (target survived, the caster died) / None (no
    # melee -- every spell but a failed Kill_Enemy, or the exhausted-
    # max_rounds draw). See ``_execute_kill_enemy``'s own docstring.
    kill_enemy_berserk_winner: str | None = None
    # Phase 313: item ids the Berserk retaliation's loser owned, transferred
    # to the winner via `turn/encounter.py loot_defeated_leader()` -- [5.9]'s
    # "looting a vanquished foe's treasure, magic items changing hands".
    # Empty unless `kill_enemy_berserk_winner` is set and the loser owned
    # something.
    looted_item_ids: list[int] = field(default_factory=list)
    # Phase 612: every Melee swing of the Berserk-retaliation duel itself
    # (`resolve_melee_duel()`'s own `EncounterCombatResult.melee_swings`,
    # discarded before this phase), for narrating each individually --
    # the same `ChallengeExecutionResult`/`PursueExecutionResult` field
    # `report/turn_report.py describe_kill_enemy_berserk_retaliation()`
    # now reads. `"a"` = the caster, `"b"` = the target (the same order
    # `resolve_melee_duel(caster_combatant, target_combatant, rng)` is
    # called in below). Empty unless `kill_enemy_berserk_winner` is set.
    melee_swings: tuple[MeleeSwing, ...] = ()
    # Phase 492: High Chancellor's own Crystal Ball addendum -- "It will
    # also list all offices and titles held by the kingdom of the
    # spied-upon character." Set only by a Chancellor-cast Clairvoyance
    # (``_execute_clairvoyance()``'s own Phase 492 addendum); ``None`` for
    # every other spell, and for an ordinary (non-Chancellor) Clairvoyance
    # cast -- this payload is the Crystal Ball's own extra benefit, not
    # something base Clairvoyance grants on its own.
    clairvoyance_target_offices: list[Office] | None = None


def execute_cast(
    state: GameState,
    kingdom_id: int,
    leader_id: int,
    request: CastRequest,
    rng: random.Random | None = None,
    *,
    board_width: int = NORMAL_MAP_BOUNDS[0],
    wand_skill_level: int | None = None,
) -> CastExecutionResult:
    """Apply a decoded Cast request to ``state``, for the spells this project can execute.

    See the module docstring for exactly which spells that is and why.
    ``rng`` is only ever consumed when the caster has real ``skills``
    data recorded (see the module docstring's success-roll section) --
    every existing caller/test that doesn't set it is unaffected.
    ``board_width`` only matters for the province-targeted spells; every
    other spell ignores it. ``wand_skill_level`` is Phase 141's own
    Use_MI wand-cast override -- see the module docstring's own
    "wand_skill_level" section; ``None`` (every existing caller) leaves
    this function's prior behavior unchanged.

    **Phase 547** -- ``VALHALLA.txt``'s own "can be affected by any
    spell except Resurrection" gates every real character-targeted
    spell here (``turn/cast_decode.py CHARACTER_TARGET_SPELLS``, minus
    ``Spell.RESURRECTION`` itself) when the target is the current
    Valhalla visitor (``LeaderState.valhalla_active_turn`` set --
    guards against a stale/departed leader still sitting at id 199).
    Every province/item-targeted spell is untouched -- their own
    ``request.target`` never resolves to a leader id at all.
    """

    rng = rng if rng is not None else random.Random()
    spell = request.spell

    if spell in CHARACTER_TARGET_SPELLS and spell is not Spell.RESURRECTION and request.target == VALHALLA_VISITOR_LEADER_ID:
        visitor = state.leaders.get(VALHALLA_VISITOR_LEADER_ID)
        if visitor is not None and visitor.valhalla_active_turn is not None:
            return CastExecutionResult(request, applied=False, reason="the Valhalla visitor is immune to this spell")

    if spell is Spell.CHARM:
        result = _execute_charm(state, kingdom_id, leader_id, request, rng, wand_skill_level)
    elif spell is Spell.KILL_ENEMY:
        result = _execute_kill_enemy(state, leader_id, request, rng, wand_skill_level)
    elif spell is Spell.RESURRECTION:
        result = _execute_resurrection(state, kingdom_id, leader_id, request, rng, wand_skill_level)
    elif spell is Spell.PART_SEA:
        result = _execute_part_sea(state, leader_id, request, rng, board_width, wand_skill_level)
    elif spell is Spell.FLOOD:
        result = _execute_flood(state, leader_id, request, rng, board_width, wand_skill_level)
    elif spell is Spell.TORNADO:
        result = _execute_tornado(state, leader_id, request, rng, board_width, wand_skill_level)
    elif spell is Spell.EARTHQUAKE:
        result = _execute_earthquake(state, leader_id, request, rng, board_width, wand_skill_level)
    elif spell is Spell.BLESS:
        result = _execute_bless(state, leader_id, request, rng, board_width, wand_skill_level)
    elif spell is Spell.ILLUS_TERRAIN:
        result = _execute_illus_terrain(state, leader_id, request, rng, board_width, wand_skill_level)
    elif spell is Spell.ILLUS_ARMIES:
        result = _execute_illus_armies(state, leader_id, request, rng, wand_skill_level)
    elif spell is Spell.ORATORY:
        result = _execute_oratory(state, leader_id, request, rng, wand_skill_level)
    elif spell is Spell.PLAGUE:
        result = _execute_plague(state, leader_id, request, rng, board_width, wand_skill_level)
    elif spell is Spell.SCAR_TERRAIN:
        result = _execute_scar_terrain(state, leader_id, request, rng, board_width, wand_skill_level)
    elif spell is Spell.SKELETAL_ARMY:
        result = _execute_skeletal_army(state, kingdom_id, leader_id, request, rng, wand_skill_level)
    elif spell is Spell.CLAIRVOYANCE:
        result = _execute_clairvoyance(state, kingdom_id, leader_id, request, rng, wand_skill_level)
    elif spell is Spell.HIDE_FEATURE:
        result = _execute_hide_feature(state, leader_id, request, rng, board_width, wand_skill_level)
    elif spell is Spell.GATE_ANGEL:
        result = _execute_gate_angel(state, kingdom_id, leader_id, request, rng, wand_skill_level)
    elif spell is Spell.MYSTIC_WINDS:
        result = _execute_mystic_winds(state, leader_id, request, rng, wand_skill_level)
    elif spell is Spell.LOCATE_OBJECT:
        result = _execute_locate_object(state, leader_id, request, rng, wand_skill_level)
    elif spell is Spell.ILLUS_FOG:
        result = _execute_illus_fog(state, leader_id, request, rng, board_width, wand_skill_level)
    else:
        return CastExecutionResult(request, applied=False, reason="spell effect not modeled")

    if result.applied:
        _award_cast_experience(state, leader_id, spell, rng)
        _award_royal_title_spell_merit(state, leader_id, spell)
    return result


def _award_cast_experience(state: GameState, leader_id: int, spell: Spell, rng: random.Random) -> None:
    """Phase 460: AKGEN_reverse_engineering_report (2).md SS3.3's own
    spell-school row (base 10, "lancio pertinente riuscito; skill 0 resta
    esclusa" -- a relevant successful cast; skill 0 stays excluded).
    ``execute_cast()``'s own ``result.applied`` already means "this spell
    genuinely resolved" -- the real trigger this row names -- for every
    spell this project executes, in one choke point, rather than
    threading a separate call into each of the ~19 ``_execute_*``
    handlers individually.

    The "skill 0 excluded" clause needs an explicit check here even
    though ``_roll_cast_success()`` already refuses ``level < 1`` for the
    ordinary case -- ``wand_skill_level is not None`` (Phase 141, a
    wand-triggered cast always succeeds) and ``caster.skills is None``
    (unrecorded, treated as an automatic success) both bypass that gate
    entirely, and neither represents the caster's own real skill genuinely
    being 1+, so both must still be excluded from credit here.
    """

    caster = state.leaders[leader_id]
    ability = _spell_ability(caster, spell)
    natural_skill = caster.skills.pair_for_ability(ability)[0] if caster.skills is not None else 0
    if natural_skill < 1:
        return
    add_experience(caster, ability, 10, rng)


def _spell_ability(caster: LeaderState, spell: Spell) -> Ability:
    """``_SPELL_ABILITY[spell]``, with Charm's own Phase 183 addendum
    override: "Per i personaggi Non-Morti questo incantesimo appartiene
    alla magia Negromantica (e non alla magia Psichica)" -- an Undead
    caster's Charm draws on Necromancy instead of Psychic. No other
    spell here has a caster-dependent ability.
    """

    if spell is Spell.CHARM and caster.alignment is Alignment.UNDEAD:
        return Ability.NECROMANCY
    return _SPELL_ABILITY[spell]


# Phase 630: the 4 magic-school royal titles' own MeritTally field
# (`models/game_state.py`, Phase 379) -- `AKGEN_embedded_catalogs.
# json.txt gw_format.royal_title_system` entries 16/21/28/46 (Master of
# Elements/Amazing Houdini/Sorceror of Black Magic/Master Mind).
# `Ability.WHITE` deliberately absent -- the Priest office's own formula
# ("2*(Druid + White)", `turn/merit_points.py`) is a live ability-sum,
# not a `Tit_Pts` cumulative counter, so it has no matching field.
_TITLE_MAGIC_SCHOOL_FIELD: dict[Ability, str] = {
    Ability.ELEMENTAL: "elemental_spell_casts",
    Ability.ILLUSION: "illusionist_spell_casts",
    Ability.NECROMANCY: "necromancy_spell_casts",
    Ability.PSYCHIC: "psychic_spell_casts",
}


def _award_royal_title_spell_merit(state: GameState, leader_id: int, spell: Spell) -> None:
    """``royal_title_system`` entries 16/21/28/46: "+1 cumulative point
    when a successful [school]-school spell reaches the compiled
    title-award branch" -- ``execute_cast()``'s own ``result.applied``
    is that branch, the same "genuinely resolved" trigger ``_award_
    cast_experience()`` already uses for XP (Phase 460), but
    **deliberately without that function's own separate "skill 0
    excluded" gate** -- this counter's own sourced text names no such
    exclusion, so applying one here would be an unsourced guess.
    Recomputes ``_spell_ability()`` independently (cheap, pure lookup)
    rather than threading it through from ``_award_cast_experience``,
    since the two functions have genuinely different gating rules and
    shouldn't be coupled. Reuses ``_spell_ability()`` (not the more
    generic ``worldgen/internal_magical_locations.py spell_college()``)
    specifically to inherit Charm's own Undead-caster Necromancy
    override for free.
    """

    caster = state.leaders[leader_id]
    ability = _spell_ability(caster, spell)
    field = _TITLE_MAGIC_SCHOOL_FIELD.get(ability)
    if field is not None:
        setattr(caster.merit_tally, field, getattr(caster.merit_tally, field) + 1)


def _caster_kingdom_is_pagan(state: GameState, caster: LeaderState) -> bool:
    """Regolamento AK.txt [3.10]: "I Reami Pagani... sono coadiuvati da
    un Ordine di Maghi. Tutti i personaggi appartenenti a quel Reame
    hanno quindi un modificatore +10%..." -- True only when the
    caster's own kingdom is recorded and its alignment is
    ``Alignment.PAGAN``. Independent Heroes (``kingdom_id is None``) or
    kingdoms not yet present in ``state.kingdoms`` never get the bonus.
    """

    if caster.kingdom_id is None:
        return False
    kingdom = state.kingdoms.get(caster.kingdom_id)
    return kingdom is not None and kingdom.alignment is Alignment.PAGAN


def _caster_kingdom_holds_pagan_king_title(state: GameState, caster: LeaderState) -> bool:
    """Office.PAGAN_KING's own White-Magic-only perk (Phase 664): "The
    League will supply all your Pagan characters with charms..." --
    True whenever the current PAGAN_KING titleholder belongs to the
    same Kingdom as ``caster`` (any leader of that Kingdom benefits,
    not just the titleholder himself -- unlike Undead King's Skeletal
    Army bonus below, which is scoped to the caster being the
    titleholder specifically).
    """

    if caster.kingdom_id is None:
        return False
    holder = resolve_office_holder(state, Office.PAGAN_KING)
    if holder is None:
        return False
    holder_leader = state.leaders.get(holder.leader_id)
    return holder_leader is not None and holder_leader.kingdom_id == caster.kingdom_id


def action_cast_slots(level: int) -> int:
    """AKGEN's own confirmed ``action_slots_per_school``: 1 slot at
    skill level 1-2, 2 at level 3, 3 at level 4 and up. ``level`` values
    below 1 (untrained) get the same 1-slot floor as level 1-2 -- moot
    in practice, since ``_roll_cast_success`` already rejects level < 1
    with "insufficient skill" before this is ever consulted.
    """

    if level <= 2:
        return ACTION_CAST_SLOTS_LEVEL_1_TO_2
    if level == 3:
        return ACTION_CAST_SLOTS_LEVEL_3
    return ACTION_CAST_SLOTS_LEVEL_4_PLUS


def _consume_action_cast_slot(state: GameState, leader_id: int, ability: Ability, level: int) -> bool:
    """Spends one of this leader's own per-``Ability``, per-turn action-
    cast slots. AKGEN's own confirmed ``failed_attempt_consumes_slot``
    is true, so this is called (and the slot spent) whenever a real
    success roll is about to happen -- win or lose -- not only on
    success; a Cast order that never reaches a roll at all (e.g. an
    invalid target, checked before ``_roll_cast_success`` by every
    ``_execute_*`` handler's own "check applicability first" order)
    never touches this counter. Returns ``False`` (no state mutated)
    once ``action_cast_slots(level)`` is already exhausted for this
    turn.
    """

    key = (leader_id, ability)
    used = state.action_casts_used.get(key, 0)
    if used >= action_cast_slots(level):
        return False
    state.action_casts_used[key] = used + 1
    return True


def _roll_cast_success(
    state: GameState,
    caster: LeaderState,
    spell: Spell,
    rng: random.Random,
    wand_skill_level: int | None = None,
    *,
    success_chance_multiplier: float = 1.0,
) -> tuple[bool, str | None]:
    """Rulebook [3.10]: 15% + 15%/level, requiring skill >= 1, capped at
    ``ACTION_SPELL_CHANCE_CAP`` (95% -- "Le probabilità di successo per
    incantesimi non possono mai superare il 95%," confirmed to be a
    universal cap, not Action-Cast-specific). Pagan Kingdoms add a
    further ``PAGAN_MAGE_ORDER_BONUS`` (+10%) to every spell except
    White Magic ("un modificatore +10% nei loro tentativi di lanciare
    qualsiasi incantesimo fuorché quelli di Magia Bianca"). See module
    docstring for the ``skills is None`` fallback and the
    ``wand_skill_level`` override (rulebook [3.11]: a wand-triggered
    cast is always successful).

    ``success_chance_multiplier`` (default 1.0, every pre-Phase-310
    caller unaffected): a per-attempt multiplier applied *before* the
    95% cap, at the same point the Pagan bonus is already added --
    Kill_Enemy's own [4.25.2] halving ("la possibilità di riuscita è
    ridotta alla metà in un incontro in un Luogo Speciale o contro un
    Eroe che comanda unità militari") is the first real caller
    (``_execute_kill_enemy``). No order between "halve" and "cap at
    95%" is stated anywhere in the source; applying the halving before
    the cap (like the Pagan bonus) keeps 95% as the one, final,
    universal ceiling regardless of any spell-specific modifier, rather
    than letting a halved-then-uncapped value exceed what a normal cast
    could ever reach.
    """

    if wand_skill_level is not None:
        return True, None
    if caster.skills is None:
        return True, None

    ability = _spell_ability(caster, spell)
    level = effective_skill_level(state, caster, ability)
    if level < 1:
        return False, "insufficient skill"

    if not _consume_action_cast_slot(state, caster.leader_id, ability, level):
        return False, "no action-cast slots remaining this turn for this ability"

    chance = ACTION_SPELL_BASE_CHANCE + ACTION_SPELL_CHANCE_PER_LEVEL * level
    if ability is not Ability.WHITE and _caster_kingdom_is_pagan(state, caster):
        chance += PAGAN_MAGE_ORDER_BONUS
    if ability is Ability.WHITE and _caster_kingdom_holds_pagan_king_title(state, caster):
        chance += PAGAN_KING_WHITE_MAGIC_BONUS
    chance *= success_chance_multiplier
    chance = min(chance, ACTION_SPELL_CHANCE_CAP)
    if rng.random() < chance:
        return True, None
    return False, "spell failed"


def _caster_level(
    state: GameState, caster: LeaderState, ability: Ability, wand_skill_level: int | None = None
) -> int:
    """Real skill level (Discovery ability bonuses included, see
    ``turn/discovery_effects.py``) if recorded, else 0 -- see module
    docstring's "level-dependent magnitudes" section. ``wand_skill_level``,
    when given, overrides unconditionally (Phase 141: a wand always casts
    "at skill-2").
    """

    if wand_skill_level is not None:
        return wand_skill_level
    return effective_skill_level(state, caster, ability)


def _resolve_province_target(state: GameState, caster: LeaderState, target_number: int, board_width: int, *, require_adjacent: bool = True):
    """Decodes+validates a province-targeted spell's raw target. See module docstring.

    Returns ``(None, None)`` if the decoded province is unknown to
    ``state`` or (when ``require_adjacent``) isn't the caster's own
    province or one adjacent to it.
    """

    coord = decode_hex_number(target_number, board_width)
    province = state.provinces.get(coord)
    if province is None:
        return None, None
    if require_adjacent and coord != caster.location:
        bounds = MapBounds(board_width, NORMAL_MAP_BOUNDS[1])
        if not is_adjacent(caster.location, coord, bounds):
            return None, None
    return coord, province


def _execute_charm(
    state: GameState,
    kingdom_id: int,
    leader_id: int,
    request: CastRequest,
    rng: random.Random,
    wand_skill_level: int | None = None,
) -> CastExecutionResult:
    """Rulebook [4.22.1] / Phase 183 addendum: "se lanciato su un Eroe che si trova
    nella stessa provincia e che non comanda unita' militari permette a
    chi lo usa di assoldare l'Eroe gratuitamente (fatti salvi i costi di
    mantenimento che vanno comunque pagati)" -- a co-located Hero
    commanding no armies is hired for free; this project has no
    separate "free hire" flag, so upkeep is simply whatever the normal
    per-turn treasury accounting already charges for that Hero's
    commanded armies (there are none here) -- nothing extra to apply.
    See module docstring for why this still differs from Hire in having
    no "must already be independent" requirement.

    **A co-located Hero who commands armies is not a free-hire target**
    -- newly required this phase, since the source's own condition
    ("che non comanda unita' militari") was previously unchecked. The
    quoted text's own "Altrimenti" ("otherwise") branch -- "consente a
    chi lancia l'incantesimo di ingraziarsi il suo avversario e sfuggire
    incolume al combattimento" -- describes Charm's *other* usage mode
    instead: a Personal-Combat cast against an armed opponent, modeled
    separately in ``turn/encounter.py``'s own Phase 183 addendum
    (``CHARM_FLEE_ALWAYS_SUCCEEDS``), not this Action-Cast function.

    **Undead-King "Seduzione" branch, confirmed but not modeled here**:
    when an Undead King (not a Hero) casts Charm on a Hero purely as an
    Action Spell, the source says it gradually transforms the target
    into Undead instead of hiring them (alignment shifts 1-3 ordinal
    positions per successful cast, per ``models/alignment.py
    ALIGNMENT_ORDINAL`` -- Phase 162's own table), with the target's
    own resistance growing with skill level even though the spell's
    base success chance itself doesn't drop. Left unimplemented: the
    resistance formula (how skill level actually reduces the
    transformation, distinct from -- and coexisting with -- the
    unaffected base success roll) isn't specified precisely enough to
    model without guessing, the same category of gap as this file's own
    Resurrection King-Heir case above.

    **Phase 522 addendum -- the paragraph above is now stale**:
    ``AKGEN_reverse_engineering_report (3).md`` SS88-96 (disassembly of
    ``AK.EXE:0x11224-0x11320``, the one physical branch that performs
    this conversion) supplies the exact, deterministic step-budget
    formula the previous paragraph said wasn't sourced precisely enough
    to model: not a random roll and not a flat "1-3 ordinal positions"
    -- New Rules gives ``12 div max(1, Total_USkill(target))`` (this
    project has no Old/New Rules toggle, so -- the same "New Rules,
    unconditionally" convention as Phase 439's alignment-decay formula
    and Phase 450's election-vote-weight formula -- this is simply *the*
    formula here), where ``Total_USkill`` sums the target's own raw
    skill level (not aptitude) across all 15 ``Ability`` members
    (``REPORTS.PAS``'s own ``Total_USkill(ldr) < 7`` King-points check
    reuses the identical helper, confirming what it measures). See
    ``_total_usable_skill()``/``_apply_undead_king_alignment_
    conversion()`` below for the implementation: gated on the caster
    being a King (``LeaderState.is_king`` -- an Undead Hero caster never
    converts, confirmed by ``RQ.TXT:3248-3249``), the target not already
    Undead, and no pending Analytical Psychology return recorded for the
    target. The step loop always takes at least one alignment-ordinal
    increment and is forced to take one more if it lands on
    ``Alignment.ANTI_HOLY`` -- Hellish can never be the final resting
    alignment of a successful conversion.

    Fixing this also required a small correction just below: this
    function used to set ``target.analytical_psychology_revert_
    kingdom_id`` whenever the target's *pre-charm* Kingdom owned the
    Discovery, even on a same-Kingdom Charm that doesn't actually change
    ``target.kingdom_id`` at all. The dossier's own SS90 (gate 4) is
    explicit that "on one's own Hero, ``LKing`` doesn't change and no
    return-King is recorded" -- and an Undead King charming their own
    already-loyal Hero purely to trigger conversion (the dossier's own
    case 6) is exactly the scenario the old, over-eager marker would
    have wrongly blocked. The marker is now only set on a genuine
    cross-Kingdom reassignment.

    **Phase 302 (Discovery.ANALYTICAL_PSYCHOLOGY, a real bug found in a
    dedicated bug-hunt audit)**: the source text is explicit that this
    Discovery does *not* block Charm outright -- "the spell will work,
    but it wears off at the end of the turn, and the charmed character
    will never Search features or risk combat." So when the target's
    own (pre-charm) kingdom owns this Discovery, the reassignment below
    still happens exactly as normal, but ``target.analytical_
    psychology_revert_kingdom_id`` is set to the target's own original
    kingdom -- ``turn/turn_processor.py run_turn()``'s own end-of-turn
    sweep reverts ``kingdom_id`` back to it and clears the field.
    "Never Search" is enforced by ``turn/search_execution.py
    execute_search()`` itself refusing to run while this field is set;
    "risk combat" needs no separate enforcement here, since Search is
    the only combat-risking action this project's Charm precondition
    above (co-located, army-less target) leaves the caster able to
    order the newly-charmed character into.

    **Phase 499 -- ``AdvancedAbility.ENHANCED_CHARM``**: "In addition to
    its other effects, the victim of a Charm spell now will also hand
    over one magic item, if available." Wired here only, not into the
    Personal-Combat Charm-as-Flee usage (``turn/encounter.py
    CHARM_FLEE_ALWAYS_SUCCEEDS``) -- that usage has no failure path
    modeled in this project at all (it always succeeds, no roll), so
    the source's own "if it's used as an encounter spell and it fails"
    qualifier never applies there, and "one magic item" reads most
    naturally as this Action-Cast hiring effect's own addendum, not the
    Flee escape. On a successful cast, if the caster holds the ability
    and the target owns at least one eligible item (``GameState.
    items_held_by``, filtered to ``models/treasure.py ENHANCED_CHARM_
    ELIGIBLE_CATEGORIES`` -- Phase 539, ``AKGEN_reverse_engineering_
    report (4).md`` SS12.1: only ordinals 0-66 are eligible, never Gold
    Hoards/Quest items/the sentinel/the 93-98 Named Uniques), the
    highest-``item_id`` eligible one transfers to the caster via
    ``GameState.transfer_item`` -- SS12.1's own ``NT_Owned`` pseudocode
    always overwrites its ``index`` result on every match while scanning
    ascending, so the *last* (highest-index) eligible instance is the one
    actually picked, not an arbitrary one. (Before Phase 539 this used an
    unfiltered, first-item pick -- a real bug, not a deliberate
    simplification; see that phase's own commit for the fix.) Same
    transfer primitive ``turn/encounter.py loot_defeated_leader()``
    already uses for looting.

    **Phase 529 -- King targets are not Action-Charm-acquirable**:
    ``AKGEN_reverse_engineering_report (3).md`` SS6.1/SS15.1 (``AK.EXE:
    0x11064``'s own eligibility gate, "target non e' un King da
    acquisire") is explicit that a King target -- unlike an ordinary
    Hero -- is excluded from Action Charm's free-hire effect outright,
    while remaining fully charmable in Personal Combat (SS15.1's own
    "non immune al Charm usato negli incontri"). This project's
    ``LeaderState.is_king`` flag (Phase 40) is the exact same signal
    already used by ``turn/hire_fire_decode.py``'s "cannot-hire-a-King"
    check, reused here rather than invented -- checked alongside the
    existing co-location/army-count preconditions above, before the
    cast roll (a King target never even attempts the roll, matching the
    source's own "eleggibilita'" gate ordering).
    """

    caster = state.leaders[leader_id]
    target = state.leaders.get(request.target)
    if target is None:
        return CastExecutionResult(request, applied=False, reason="target character not found")
    if target.location != caster.location:
        return CastExecutionResult(request, applied=False, reason="not co-located")
    if state.armies_commanded_by(request.target):
        return CastExecutionResult(request, applied=False, reason="target commands military units")
    if target.is_king:
        return CastExecutionResult(request, applied=False, reason="a King cannot be acquired by Action Charm")

    succeeded, reason = _roll_cast_success(state, caster, request.spell, rng, wand_skill_level)
    if not succeeded:
        return CastExecutionResult(request, applied=False, reason=reason)

    # Phase 531: AKGEN_reverse_engineering_report (4).md SS8 -- a target
    # holding the Helm of Psychic Dampening (models/treasure.py AMULET_
    # BLOCKED_SPELLS) is immune to Charm outright, regardless of which
    # school the caster drew on to cast it (the amulet blocks the named
    # spell, not "whatever school this particular cast used") -- checked
    # independent of and before Analytical Psychology's own separate
    # revert-later mechanic.
    if holder_is_immune_to_spell(state, request.target, request.spell):
        return CastExecutionResult(request, applied=False, reason="target is immune (anti-magic amulet)")

    if (
        target.kingdom_id is not None
        and target.kingdom_id != kingdom_id
        and Discovery.ANALYTICAL_PSYCHOLOGY in state.kingdoms[target.kingdom_id].discoveries
    ):
        target.analytical_psychology_revert_kingdom_id = target.kingdom_id
    target.kingdom_id = kingdom_id
    if caster.alignment is Alignment.UNDEAD:
        _apply_undead_king_alignment_conversion(caster, target)
    if AdvancedAbility.ENHANCED_CHARM in caster.advanced_abilities:
        eligible_items = [
            item
            for item in state.items_held_by(request.target)
            if TREASURE_CATEGORY.get(item.treasure) in ENHANCED_CHARM_ELIGIBLE_CATEGORIES
        ]
        if eligible_items:
            stolen = max(eligible_items, key=lambda item: item.item_id)
            state.transfer_item(stolen.item_id, leader_id)
    return CastExecutionResult(request, applied=True)


# Phase 522: AKGEN_reverse_engineering_report (3).md SS90/SS94's own gate-1
# numerator -- "12 div max(1, Total_USkill(target))". Named after the
# source's own identifier (35EB:1EA9), not renamed to this project's usual
# snake_case style, since it's quoted directly in several docstrings above
# and below and a mismatch would make cross-referencing the dossier harder.
UNDEAD_CONVERSION_STEP_BUDGET_NUMERATOR = 12


def _total_usable_skill(leader: LeaderState) -> int:
    """AKGEN_reverse_engineering_report (3).md SS93: ``Total_USkill`` sums a
    character's own raw skill level (not aptitude) across all 15 ``Ability``
    members, ``Tactical`` through ``Sage`` -- confirmed via ``REPORTS.PAS``'s
    own ``Total_USkill(ldr) < 7`` initial-King-points check reusing the
    identical helper (same dossier section, independent call site).

    ``leader.skills is None`` (unrecorded) reads as 0 for every ability,
    the same "unrecorded means weakest case" fallback this module's own
    ``_award_cast_experience()`` already uses for its ``natural_skill``
    read.
    """

    if leader.skills is None:
        return 0
    return sum(leader.skills.pair_for_ability(ability)[0] for ability in Ability)


def is_unfinalized_royal_heir(leader: LeaderState) -> bool:
    """Whether ``leader`` is still eligible for Royal-Heir-specific treatment
    (Resurrection-restores-the-dead-King, the "Royal Heir" report-name
    substitution) -- **Phase 553**, ``AKGEN_reverse_engineering_report
    (5).md`` SS6.2/SS11.1 (``REPORTS.PAS Get_HName``, machine-verified):
    the real engine gates both on ``Total_USkill(ldr) < 7`` every time,
    not on an edge-triggered "has Practice ever raised a skill" flag.
    ``leader.is_royal_heir`` still marks "occupies the Royal-Heir slot,
    not yet finalized into a real King by ``turn/succession.py
    create_king()``" -- this function adds the numeric half of the real
    eligibility check on top of it.
    """

    return leader.is_royal_heir and _total_usable_skill(leader) < 7


def _apply_undead_king_alignment_conversion(caster: LeaderState, target: LeaderState) -> None:
    """AKGEN_reverse_engineering_report (3).md SS88-96 (``Undead_Action_
    Charm``, ``AK.EXE:0x11224-0x11320``) -- see ``_execute_charm``'s own
    Phase 522 addendum for the full citation and design rationale. Call
    site already confirmed ``caster.alignment is Alignment.UNDEAD`` and a
    successful cast; this function applies the remaining three gates and,
    if all pass, the deterministic step loop.
    """

    if not caster.is_king:
        return
    if target.alignment is None or target.alignment is Alignment.UNDEAD:
        return
    if target.analytical_psychology_revert_kingdom_id is not None:
        return

    step_budget = UNDEAD_CONVERSION_STEP_BUDGET_NUMERATOR // max(1, _total_usable_skill(target))
    undead_ordinal = ALIGNMENT_ORDINAL[Alignment.UNDEAD]
    anti_holy_ordinal = ALIGNMENT_ORDINAL[Alignment.ANTI_HOLY]

    ordinal = ALIGNMENT_ORDINAL[target.alignment]
    while True:
        ordinal += 1
        step_budget -= 1
        if ordinal == undead_ordinal:
            break
        if ordinal == anti_holy_ordinal:
            continue
        if step_budget <= 0:
            break
    target.alignment = ALIGNMENT_BY_ORDINAL[ordinal]


def _kill_enemy_combatant(state: GameState, leader: LeaderState, *, temper: Temper | None) -> Combatant:
    """Same construction as ``challenge_execution.py _leader_combatant()`` (Phase 50),
    duplicated rather than shared -- see that function's own docstring for
    why. ``temper`` is an explicit override, not ``leader.temper``: the
    Berserk retaliator below fights with a temperament "assumed for the
    occasion" ([4.25.2]'s own wording), not their own permanently
    recorded one, so the caller decides what to pass.
    """

    melee_skill = effective_skill_level(state, leader, Ability.MELEE)
    archery_skill = effective_skill_level(state, leader, Ability.ARCHERY)

    neutral_bonus = False
    if leader.kingdom_id is not None:
        kingdom = state.kingdoms.get(leader.kingdom_id)
        neutral_bonus = kingdom is not None and kingdom.alignment is Alignment.NEUTRAL

    defender_office = resolve_office_holder(state, Office.DEFENDER)
    damage_reduction = 1 if defender_office is not None and defender_office.leader_id == leader.leader_id else 0
    has_melee_hit_points_ability = AdvancedAbility.MELEE_HIT_POINTS in leader.advanced_abilities
    effective_race = leader.race
    if effective_race is None and leader.kingdom_id is not None:
        leader_kingdom = state.kingdoms.get(leader.kingdom_id)
        effective_race = leader_kingdom.race if leader_kingdom is not None else None
    is_humanoid = effective_race in HUMANOID_RACES

    return Combatant(
        name=leader.name,
        hit_points=CHARACTER_HIT_POINTS,
        melee_skill=melee_skill,
        archery_skill=archery_skill,
        neutral_duelist_bonus=neutral_bonus,
        temper=temper,
        damage_reduction=damage_reduction,
        has_melee_hit_points_ability=has_melee_hit_points_ability,
        offensive_hit_multiplier=melee_mastery_offensive_hit_multiplier(leader.advanced_abilities),
        melee_damage_dealt_bonus=melee_mastery_damage_bonus(leader.advanced_abilities),
        is_humanoid=is_humanoid,
        has_duellists_medal_ability=AdvancedAbility.MELEE_DUELLISTS_MEDAL in leader.advanced_abilities,
        has_control_temper_ability=AdvancedAbility.MELEE_CONTROL_TEMPER in leader.advanced_abilities,
        archery_free_attack_bonus=archery_free_attack_bonus(leader.advanced_abilities),
    )


def _execute_kill_enemy(
    state: GameState, leader_id: int, request: CastRequest, rng: random.Random, wand_skill_level: int | None = None
) -> CastExecutionResult:
    """Rulebook [4.25.2] (quoted in full): "il mago costruisce una statuetta
    dell'avversario di cui desidera la morte, quindi 'uccide' la
    statuetta... Se l'incantesimo riesce, la vittima viene uccisa nello
    stesso modo in cui era stata distrutta la statuetta. Se fallisce, la
    vittima designata attaccherà l'autore dell'incantesimo assumendo per
    l'occasione un temperamento Berserk, se necessario anche
    aggredendolo in quella stessa fase. ... la possibilità di riuscita è
    ridotta alla metà in un incontro in un Luogo Speciale o contro un
    Eroe che comanda unità militari... I Re sono immuni a questo
    incantesimo."

    **Phase 310 -- four gaps closed, all sourced from the same passage
    above (previously undocumented as gaps at all -- Phase 29's own
    version only ever modeled the base "succeeds -> dies" case)**:

    1. **King immunity** ("I Re sono immuni"): checked before any
       success roll, the same "check applicability first" order every
       other precondition here uses.
    2. **Halved chance** ("ridotta alla metà in un incontro in un Luogo
       Speciale o contro un Eroe che comanda unità militari"): read as
       two independent triggers, either one halving the roll --
       ``state.features_at(caster.location)`` non-empty (a Special
       Place feature at the shared province, regardless of who's
       targeted) OR the target leads at least one army
       (``state.armies_commanded_by``). The rulebook's other named
       condition for this same clause -- casting at a monster guarding
       a Special Place -- is structurally unreachable here: this
       project's Kill_Enemy only ever targets a ``LeaderState``
       (``cast_decode.py CHARACTER_TARGET_SPELLS``), never a Monster,
       so that half of the disjunction has no consumer to wire yet.
       Passed to ``_roll_cast_success`` as ``success_chance_multiplier``.
    3. **Coma instead of death** ("Se viene utilizzato come incantesimo
       d'Azione può succedere che, invece di morire, la vittima cada in
       coma profondo... i suoi Talenti sono ridotti a livello zero, ma
       possono essere ripristinati con un incantesimo di
       Resurrezione"): this project's Kill_Enemy is *only* ever cast as
       an Action spell (via ``ActionCode.CAST`` -- there is no
       Individual-Combat-mode dispatch path for it anywhere in this
       project, the same structural gap as point 2's monster case), so
       a success here always produces the Action-cast outcome. No
       percentage for "può succedere" ("can happen") is sourced
       anywhere (English ``RULES.AK`` doesn't mention the coma variant
       at all), so rather than invent one, a success is read as always
       producing coma for this project's one real cast path --
       ``target.is_comatose = True`` (see ``LeaderState.is_comatose``'s
       own docstring for exactly what that zeroes and how it's cured).
       The target is never removed from ``state.leaders`` -- a coma
       victim keeps acting normally, per the user's own 2026-07-31
       clarification ("potrà comunque fare tutte le azioni").
    4. **Berserk counterattack on failure**: a real, immediate
       ``resolve_melee_duel`` between the target (Combatant.temper
       forced to ``Temper.BERSERK`` "for the occasion" -- their own
       recorded ``LeaderState.temper`` is never touched) and the caster
       (their own real temper, ordinary construction) -- "quella stessa
       fase" (that same phase) read as resolving inline, right here,
       not deferred to a later phase the way Pursue/Trail's own
       persistent chases are. Whoever loses is removed via
       ``state.remove_leader()``, same convention as every other
       personal-combat winner/loser this project already has
       (``turn/challenge_execution.py``). ``kill_enemy_berserk_winner``
       records which side won ("a" caster / "b" target / ``None`` for
       the vanishingly rare ``max_rounds``-exhausted draw); ``melee_
       swings`` (Phase 612) carries the duel's own per-round detail
       through too, both now consumed by ``report/turn_report.py
       describe_kill_enemy_berserk_retaliation()``.

    **Hidden Tattoos** (Discovery.txt, Phase 270): "neutralize the Kill
    Enemy spell of Necromancers... All characters of the Kingdom are
    protected. Instead of being killed, the target character will be
    sick for the remainder of the gameturn and will spend his time
    practicing abilities somewhat randomly." Only the confirmed core
    effect -- the target survives (now: doesn't fall comatose either,
    reusing the same ward for the Phase 310 coma outcome) -- is
    modeled; the "sick, practices randomly" secondary effect has no
    consumer this project could wire it into without inventing a new
    sickness/forced-Practice mechanic the source doesn't specify the
    parameters of (same "don't guess" convention as Flood's own
    unmodeled land-units-trapped clause).
    """

    caster = state.leaders[leader_id]
    target = state.leaders.get(request.target)
    if target is None:
        return CastExecutionResult(request, applied=False, reason="target character not found")
    if target.location != caster.location:
        return CastExecutionResult(request, applied=False, reason="not co-located")
    if target.is_king:
        return CastExecutionResult(request, applied=False, reason="target is a King, immune to Kill Enemy")

    halving_applies = bool(state.features_at(caster.location)) or bool(state.armies_commanded_by(target.leader_id))
    multiplier = 0.5 if halving_applies else 1.0
    succeeded, reason = _roll_cast_success(
        state, caster, request.spell, rng, wand_skill_level, success_chance_multiplier=multiplier
    )
    if not succeeded:
        caster_combatant = _kill_enemy_combatant(state, caster, temper=caster.temper)
        target_combatant = _kill_enemy_combatant(state, target, temper=Temper.BERSERK)
        combat_result = resolve_melee_duel(caster_combatant, target_combatant, rng)
        if combat_result.winner == "a":  # caster survived the Berserk retaliation
            state.remove_leader(request.target)
            looted_items = loot_defeated_leader(state, winner_id=leader_id, loser_id=request.target)
            return CastExecutionResult(
                request,
                applied=False,
                reason=reason,
                kill_enemy_berserk_winner="a",
                looted_item_ids=[item.item_id for item in looted_items],
                melee_swings=combat_result.melee_swings,
            )
        if combat_result.winner == "b":  # the retaliating target killed the caster
            state.remove_leader(leader_id)
            looted_items = loot_defeated_leader(state, winner_id=request.target, loser_id=leader_id)
            return CastExecutionResult(
                request,
                applied=False,
                reason=reason,
                kill_enemy_berserk_winner="b",
                looted_item_ids=[item.item_id for item in looted_items],
                melee_swings=combat_result.melee_swings,
            )
        return CastExecutionResult(request, applied=False, reason=reason)

    # Phase 531: AKGEN_reverse_engineering_report (4).md SS8 -- a target
    # holding The True Cross (models/treasure.py AMULET_BLOCKED_SPELLS)
    # is immune to Kill_Enemy, checked before (and independent of) the
    # Hidden Tattoos Discovery ward just below.
    if holder_is_immune_to_spell(state, request.target, request.spell):
        return CastExecutionResult(request, applied=False, reason="target is immune (anti-magic amulet)")

    if target.kingdom_id is not None and Discovery.HIDDEN_TATTOOS in state.kingdoms[target.kingdom_id].discoveries:
        return CastExecutionResult(request, applied=True, discovery_defended=Discovery.HIDDEN_TATTOOS)

    # Phase 447: Grandfather of Assassins (Office.ASSASSIN, id 43) merit
    # -- AKGEN_reverse_engineering_report (2).md SS20.5-10 -- credits the
    # caster only at this real lethal branch (success roll passed, not
    # Hidden-Tattoos-defended). Not credited on spell failure (the
    # Berserk-counterattack branch above is a different combat entirely)
    # or on a Hidden Tattoos defense (disease, no kill).
    caster.merit_tally.successful_assassinations += 1
    target.is_comatose = True
    return CastExecutionResult(request, applied=True)


def _execute_resurrection(
    state: GameState,
    kingdom_id: int,
    leader_id: int,
    request: CastRequest,
    rng: random.Random,
    wand_skill_level: int | None = None,
) -> CastExecutionResult:
    """Rulebook [4.21.1]: "a character in the same province as a dead one can attempt to
    bring him back to life... with all his Talents but not the items he
    owned... and joins the service of the Kingdom that resurrected him."

    **Phase 259 -- the King-via-Heir case is now modeled too**, sourced
    from the same [4.21.1] passage: "After your King dies, you can cast
    a Resurrection spell on your Royal Heir and get your old King back
    (you're actually casting the spell on the bones carried around by
    the Heir.) If another player casts a Resurrection spell on your
    Royal Heir, you still get your old King back." ``request.target``
    referencing a *living* ``LeaderState`` still flagged
    ``is_royal_heir`` (``GameState.remove_leader()``'s own Phase 259
    addendum installs one under the dead King's own ``leader_id`` the
    instant he dies) routes here instead of the ordinary dead-leader
    path below: on success, the exact archived King (``dead_leaders``,
    keyed by that same ``leader_id`` since the Heir never changed it) is
    restored verbatim, with his own original ``kingdom_id`` intact --
    "resumes his own throne," not the caster's Kingdom, unlike an
    ordinary Hero revival, exactly matching the quote regardless of
    which King's own priest casts it.

    **Phase 251**: a successful cast increments the caster's own
    ``LeaderState.merit_tally.resurrection_bless_casts`` -- see
    ``turn/merit_points.py``'s own "Gran Sacerdote / Priest" section for
    the +1-per-cast formula this feeds, previously never incremented by
    any consumer.

    **Phase 310 -- curing a Kill_Enemy coma is also a Resurrection cast**
    ([4.25.2]: "[i Talenti] possono essere ripristinati con un
    incantesimo di Resurrezione"), checked first, before the Royal-Heir
    branch below: ``request.target`` resolving to a *living*,
    ``is_comatose`` ``LeaderState`` clears the flag on success and
    stops there -- unlike every other branch here, ``target.kingdom_id``
    is deliberately left untouched. The user's own 2026-07-31
    clarification: "Se l'incantesimo viene lanciato da un eroe o un RE
    di un altro reame, l'eroe in coma torna normale ma non cambia
    reame" (if cast by a hero or King of another kingdom, the comatose
    hero returns to normal but doesn't change kingdom) -- the one
    explicit way this project's Resurrection now differs from its own
    base "joins the service of the Kingdom that resurrected him" rule
    quoted above. No skill restoration logic is needed: comatose
    ``LeaderState.skills`` was never mutated in the first place (see
    that field's own docstring) -- clearing the flag alone un-hides the
    real, untouched values everywhere ``effective_skill_level()`` reads
    them.

    **Phase 498 -- ``AdvancedAbility.ENHANCED_RESURRECTION``**: "A
    resurrected character becomes the same alignment as the
    spellcaster's king." Applies only to the ordinary dead-Hero branch
    below (a fresh Kingdom-affiliation, matching the ability's own
    "joins the service" case) -- deliberately excluded from the
    comatose-cure branch above (no Kingdom change happens there at all,
    so there's nothing to re-align) and the King-via-Heir branch above
    (restores the archived King's own original alignment verbatim, a
    different documented rule, not a "revival" in the sense this perk
    describes).
    """

    caster = state.leaders[leader_id]

    comatose_target = state.leaders.get(request.target)
    if comatose_target is not None and comatose_target.is_comatose:
        if comatose_target.location != caster.location:
            return CastExecutionResult(request, applied=False, reason="not co-located")
        succeeded, reason = _roll_cast_success(state, caster, request.spell, rng, wand_skill_level)
        if not succeeded:
            return CastExecutionResult(request, applied=False, reason=reason)
        comatose_target.is_comatose = False
        caster.merit_tally.resurrection_bless_casts += 1
        return CastExecutionResult(request, applied=True)

    heir = state.leaders.get(request.target)
    if heir is not None and heir.is_royal_heir:
        if not is_unfinalized_royal_heir(heir):
            # Phase 553: the flag alone (heir.is_royal_heir) no longer
            # means the Resurrection option is still open -- see
            # is_unfinalized_royal_heir()'s own docstring. Once
            # Total_USkill(heir) reaches 7, the option is gone even
            # though the Heir is still alive and occupying this slot
            # (falling through to the ordinary dead_leaders branch below
            # would incorrectly resurrect the stale archived King on top
            # of a living occupant).
            return CastExecutionResult(request, applied=False, reason="Royal Heir has trained past the Resurrection threshold")
        old_king = state.dead_leaders.get(request.target)
        if old_king is None:
            return CastExecutionResult(request, applied=False, reason="target character not found")
        if heir.location != caster.location:
            return CastExecutionResult(request, applied=False, reason="not co-located")
        succeeded, reason = _roll_cast_success(state, caster, request.spell, rng, wand_skill_level)
        if not succeeded:
            return CastExecutionResult(request, applied=False, reason=reason)
        del state.dead_leaders[request.target]
        state.leaders[request.target] = old_king
        caster.merit_tally.resurrection_bless_casts += 1
        return CastExecutionResult(request, applied=True)

    target = state.dead_leaders.get(request.target)
    if target is None:
        return CastExecutionResult(request, applied=False, reason="target character not found")
    if target.location != caster.location:
        return CastExecutionResult(request, applied=False, reason="not co-located")

    succeeded, reason = _roll_cast_success(state, caster, request.spell, rng, wand_skill_level)
    if not succeeded:
        return CastExecutionResult(request, applied=False, reason=reason)

    del state.dead_leaders[request.target]
    target.kingdom_id = kingdom_id
    if AdvancedAbility.ENHANCED_RESURRECTION in caster.advanced_abilities:
        kingdom = state.kingdoms.get(kingdom_id)
        if kingdom is not None:
            target.alignment = kingdom.alignment
    state.leaders[request.target] = target
    caster.merit_tally.resurrection_bless_casts += 1
    return CastExecutionResult(request, applied=True)


def _execute_part_sea(
    state: GameState,
    leader_id: int,
    request: CastRequest,
    rng: random.Random,
    board_width: int,
    wand_skill_level: int | None = None,
) -> CastExecutionResult:
    """Rulebook [4.21.2]: "a Sea province is transformed into a Plain for the rest of
    the turn... only the caster's own province, or one adjacent to it,
    can be targeted."
    """

    caster = state.leaders[leader_id]
    _coord, province = _resolve_province_target(state, caster, request.target, board_width)
    if province is None:
        return CastExecutionResult(request, applied=False, reason="province not found or not in range")
    if province.effective_terrain() is not Terrain.SEA:
        return CastExecutionResult(request, applied=False, reason="target province is not Sea")

    part_sea_multiplier = 0.5 if province_halves_spell_chance(state, _coord, Ability.WHITE) else 1.0
    succeeded, reason = _roll_cast_success(
        state, caster, request.spell, rng, wand_skill_level, success_chance_multiplier=part_sea_multiplier
    )
    if not succeeded:
        return CastExecutionResult(request, applied=False, reason=reason)

    province.terrain_override = Terrain.PLAINS
    return CastExecutionResult(request, applied=True)


def _execute_flood(
    state: GameState,
    leader_id: int,
    request: CastRequest,
    rng: random.Random,
    board_width: int,
    wand_skill_level: int | None = None,
) -> CastExecutionResult:
    """Rulebook [4.24.1]: "can only be cast on the non-mountain land province you're in,
    or one adjacent to it, turning it into Sea." The secondary "land
    units trapped there" effect is deliberately not modeled: this
    project has no first-class "is this a land unit" classification
    (only per-``ArmyType`` favorable/adverse terrain lists), and flying
    units' status under this specific rule is genuinely ambiguous in the
    rulebook text -- left for a later phase rather than guessed.
    """

    caster = state.leaders[leader_id]
    _coord, province = _resolve_province_target(state, caster, request.target, board_width)
    if province is None:
        return CastExecutionResult(request, applied=False, reason="province not found or not in range")
    if province.effective_terrain() not in _FLOOD_ELIGIBLE_TERRAIN:
        return CastExecutionResult(request, applied=False, reason="target province is not a non-mountain land province")

    flood_multiplier = 0.5 if province_halves_spell_chance(state, _coord, Ability.ELEMENTAL) else 1.0
    succeeded, reason = _roll_cast_success(
        state, caster, request.spell, rng, wand_skill_level, success_chance_multiplier=flood_multiplier
    )
    if not succeeded:
        return CastExecutionResult(request, applied=False, reason=reason)

    province.terrain_override = Terrain.SEA
    return CastExecutionResult(request, applied=True)


def _execute_tornado(
    state: GameState,
    leader_id: int,
    request: CastRequest,
    rng: random.Random,
    board_width: int,
    wand_skill_level: int | None = None,
) -> CastExecutionResult:
    """Rulebook [4.24.2]: "cast on an enemy province you're in or adjacent to it: every
    unit present (even your own or allied ones) has a 10%-per-mage-level
    chance of being destroyed." No ownership/allegiance check on which
    units get caught in the blast -- the rulebook explicitly says own
    and allied units aren't exempt.

    **Giant Fan** (Discovery.txt, Phase 270): "Armies hit by Tornadoes
    will have a 50% chance of losing one level of quality" instead of
    being destroyed -- checked per army, against *that army's own*
    ``kingdom_id`` (the rulebook's "own and allied units aren't exempt"
    reading applies equally to which armies get the *defended* outcome:
    each army's own Kingdom decides, not the province owner's).
    """

    caster = state.leaders[leader_id]
    coord, province = _resolve_province_target(state, caster, request.target, board_width)
    if province is None:
        return CastExecutionResult(request, applied=False, reason="province not found or not in range")

    tornado_multiplier = 0.5 if province_halves_spell_chance(state, coord, Ability.ELEMENTAL) else 1.0
    succeeded, reason = _roll_cast_success(
        state, caster, request.spell, rng, wand_skill_level, success_chance_multiplier=tornado_multiplier
    )
    if not succeeded:
        return CastExecutionResult(request, applied=False, reason=reason)

    chance = TORNADO_DESTROY_CHANCE_PER_LEVEL * _caster_level(state, caster, Ability.ELEMENTAL, wand_skill_level)
    defended = False
    for army in list(state.armies_at(coord)):
        if army.kingdom_id is not None and Discovery.GIANT_FAN in state.kingdoms[army.kingdom_id].discoveries:
            defended = True
            if rng.random() < GIANT_FAN_QUALITY_DOWNGRADE_CHANCE:
                army.quality = quality_one_level_down(army.quality)
            continue
        if rng.random() < chance:
            state.remove_army(army.army_id)
    return CastExecutionResult(
        request, applied=True, discovery_defended=Discovery.GIANT_FAN if defended else None
    )


def _execute_earthquake(
    state: GameState,
    leader_id: int,
    request: CastRequest,
    rng: random.Random,
    board_width: int,
    wand_skill_level: int | None = None,
) -> CastExecutionResult:
    """Rulebook [4.24.3]: "zeroes the tax revenue of an enemy land province you're in or
    adjacent to it, for one turn." "Not cumulative" -- stored as a
    ``ProvinceState.tax_modifier_percent`` -100 (a set, not an add),
    same convention as Bless's +60.

    **Reinforced Concrete** (Discovery.txt, Phase 270): when the
    province's own owner Kingdom owns it, "income from the affected
    province will only decrease by 3 gold" -- replaces the -100% effect
    entirely with ``ProvinceState.earthquake_flat_reduction`` (see
    ``turn/tax_base.py province_tax_yield()``), rather than stacking
    both.
    """

    caster = state.leaders[leader_id]
    _coord, province = _resolve_province_target(state, caster, request.target, board_width)
    if province is None:
        return CastExecutionResult(request, applied=False, reason="province not found or not in range")
    if province.effective_terrain() is Terrain.SEA:
        return CastExecutionResult(request, applied=False, reason="target province is not land")

    earthquake_multiplier = 0.5 if province_halves_spell_chance(state, _coord, Ability.ELEMENTAL) else 1.0
    succeeded, reason = _roll_cast_success(
        state, caster, request.spell, rng, wand_skill_level, success_chance_multiplier=earthquake_multiplier
    )
    if not succeeded:
        return CastExecutionResult(request, applied=False, reason=reason)

    owner_kingdom_id = province.owner_kingdom_id
    if owner_kingdom_id is not None and Discovery.REINFORCED_CONCRETE in state.kingdoms[owner_kingdom_id].discoveries:
        province.earthquake_flat_reduction = REINFORCED_CONCRETE_TAX_REDUCTION
        return CastExecutionResult(request, applied=True, discovery_defended=Discovery.REINFORCED_CONCRETE)

    province.tax_modifier_percent = EARTHQUAKE_TAX_MODIFIER_PERCENT
    return CastExecutionResult(request, applied=True)


def _execute_bless(
    state: GameState,
    leader_id: int,
    request: CastRequest,
    rng: random.Random,
    board_width: int,
    wand_skill_level: int | None = None,
) -> CastExecutionResult:
    """Rulebook [4.21.3]: "the tax revenue of any province on the map (regardless of
    where the caster is) is increased 60% for one turn. Repeated casts
    aren't cumulative." Unlike every other province-targeted spell here,
    Bless has no same-or-adjacent restriction -- ``require_adjacent=False``.

    **Addendum (Phase 60)**: "L'incantesimo Benedizione (Bless) ora
    rimuove le unita' morte in una provincia. La probabilita' e' del 10%
    + 10% per livello in Magia Bianca di chi lancia l'incantesimo." --
    rolled independently, *after* the spell itself has already succeeded
    (a separate roll, not folded into the main 15%+15%/level cast-success
    check): on a hit, every ``GraveyardEntry`` recorded for the target
    province is cleared, so it can no longer be raised as a Skeletal
    Army. On a miss, nothing happens to the graveyard, but the tax bonus
    still applies -- the two effects are independent, per the addendum's
    own wording ("also removes," not "instead of").

    **Phase 251**: a successful cast increments the caster's own
    ``LeaderState.merit_tally.resurrection_bless_casts`` -- see
    ``_execute_resurrection``'s own Phase 251 note; the rulebook's Merit
    Point table doesn't distinguish which of the two spells scores the
    +1, and the graveyard-cleanup roll's own outcome has no bearing on
    whether the cast itself counts.
    """

    caster = state.leaders[leader_id]
    coord, province = _resolve_province_target(state, caster, request.target, board_width, require_adjacent=False)
    if province is None:
        return CastExecutionResult(request, applied=False, reason="province not found")

    bless_multiplier = 0.5 if province_halves_spell_chance(state, coord, Ability.WHITE) else 1.0
    succeeded, reason = _roll_cast_success(
        state, caster, request.spell, rng, wand_skill_level, success_chance_multiplier=bless_multiplier
    )
    if not succeeded:
        return CastExecutionResult(request, applied=False, reason=reason)

    province.tax_modifier_percent = BLESS_TAX_BONUS_PERCENT

    cleanup_level = _caster_level(state, caster, Ability.WHITE, wand_skill_level)
    cleanup_chance = BLESS_GRAVEYARD_CLEAR_BASE_CHANCE + BLESS_GRAVEYARD_CLEAR_CHANCE_PER_LEVEL * cleanup_level
    if rng.random() < cleanup_chance:
        state.battle_graveyard.pop(coord, None)

    caster.merit_tally.resurrection_bless_casts += 1
    return CastExecutionResult(request, applied=True)


def _execute_illus_terrain(
    state: GameState,
    leader_id: int,
    request: CastRequest,
    rng: random.Random,
    board_width: int,
    wand_skill_level: int | None = None,
) -> CastExecutionResult:
    """Rulebook [4.23.1]: "makes the province you're in (or one adjacent) appear to be a
    different terrain type of your choosing, to anyone examining it from
    an adjacent province." Only the fake-terrain *record* is stored
    (``ProvinceState.illusory_terrain``) -- the "who currently believes
    the illusion," 15%/turn dissolve chance, and blended real/illusory
    combat strength all need exploration/movement-side consumers that
    don't exist yet (see ``models/game_state.py``'s field docstring).
    """

    caster = state.leaders[leader_id]
    _coord, province = _resolve_province_target(state, caster, request.target, board_width)
    if province is None:
        return CastExecutionResult(request, applied=False, reason="province not found or not in range")
    if not isinstance(request.terrain, Terrain):
        return CastExecutionResult(request, applied=False, reason="fake terrain not specified")

    illus_terrain_multiplier = 0.5 if province_halves_spell_chance(state, _coord, Ability.ILLUSION) else 1.0
    succeeded, reason = _roll_cast_success(
        state, caster, request.spell, rng, wand_skill_level, success_chance_multiplier=illus_terrain_multiplier
    )
    if not succeeded:
        return CastExecutionResult(request, applied=False, reason=reason)

    province.illusory_terrain = request.terrain
    return CastExecutionResult(request, applied=True)


def _execute_illus_armies(
    state: GameState, leader_id: int, request: CastRequest, rng: random.Random, wand_skill_level: int | None = None
) -> CastExecutionResult:
    """Rulebook [4.23.2] (Phantasmal Armies): "summons phantom armies that travel with
    him (or with a co-located character) for the rest of the turn,
    increasing the strength of the units he commands 15% per skill
    level. Not cumulative." Target may be the caster himself (the
    generic character-target decode already allows ``request.target ==
    leader_id``). See ``turn/strength.py phantasmal_armies_multiplier``
    for where the stored level is actually consumed in battle.
    """

    caster = state.leaders[leader_id]
    target = state.leaders.get(request.target)
    if target is None:
        return CastExecutionResult(request, applied=False, reason="target character not found")
    if target.location != caster.location:
        return CastExecutionResult(request, applied=False, reason="not co-located")

    succeeded, reason = _roll_cast_success(state, caster, request.spell, rng, wand_skill_level)
    if not succeeded:
        return CastExecutionResult(request, applied=False, reason=reason)

    target.phantasmal_armies_level = _caster_level(state, caster, Ability.ILLUSION, wand_skill_level)
    return CastExecutionResult(request, applied=True)


def _execute_oratory(
    state: GameState, leader_id: int, request: CastRequest, rng: random.Random, wand_skill_level: int | None = None
) -> CastExecutionResult:
    """Rulebook [4.22.2]: "cast on yourself or a co-located character: every unit he
    commands is heartened and its rank rises one level for the rest of
    the turn (Green becomes Average, Average becomes Veteran, and so
    on). Repeated casts aren't cumulative." Applied as a direct,
    persistent ``ArmyState.quality`` bump (capped at Elite) rather than a
    strength-pipeline multiplier -- see ``turn/strength.py``'s own module
    docstring for why that's the more faithful reading of "becomes"
    Average/Veteran/etc.

    **Propaganda Megaphones** (Phase 391): "each opposing army will have
    only a 33% chance of being affected by their leader's Oratory" --
    checked per army against *that army's own* ``kingdom_id``, the same
    Giant-Fan-style per-army convention this module already uses for
    Tornado. ``target.oratory_boosted_this_turn`` still gates the whole
    cast to once per turn regardless of how many (if any) armies the
    megaphones end up shielding.
    """

    caster = state.leaders[leader_id]
    target = state.leaders.get(request.target)
    if target is None:
        return CastExecutionResult(request, applied=False, reason="target character not found")
    if target.location != caster.location:
        return CastExecutionResult(request, applied=False, reason="not co-located")

    succeeded, reason = _roll_cast_success(state, caster, request.spell, rng, wand_skill_level)
    if not succeeded:
        return CastExecutionResult(request, applied=False, reason=reason)

    defended = False
    if not target.oratory_boosted_this_turn:
        for army in state.armies_commanded_by(request.target):
            if army.kingdom_id is not None and Discovery.PROPAGANDA_MEGAPHONES in state.kingdoms[army.kingdom_id].discoveries:
                defended = True
                if rng.random() >= PROPAGANDA_MEGAPHONES_AFFECTED_CHANCE:
                    continue
            army.quality = Quality(min(int(army.quality) + 1, Quality.ELITE))
        target.oratory_boosted_this_turn = True
    return CastExecutionResult(
        request, applied=True, discovery_defended=Discovery.PROPAGANDA_MEGAPHONES if defended else None
    )


def _execute_mystic_winds(
    state: GameState, leader_id: int, request: CastRequest, rng: random.Random, wand_skill_level: int | None = None
) -> CastExecutionResult:
    """"Each unit led by the affected leader has its movement set at 5 while the
    spell lasts" -- cast on yourself or a co-located character, the same
    target shape as Oratory/Illus_Armies above. Sets ``LeaderState.
    mystic_winds_active`` and every currently-commanded army's
    ``movement_points`` to ``MYSTIC_WINDS_MOVEMENT_POINTS``. See the
    module docstring's own Phase 204 addendum for what "moves as an air
    unit," "no fleet/air transport," and "ends before army battle" mean
    and why none of the three is wired into a consuming system yet.
    """

    caster = state.leaders[leader_id]
    target = state.leaders.get(request.target)
    if target is None:
        return CastExecutionResult(request, applied=False, reason="target character not found")
    if target.location != caster.location:
        return CastExecutionResult(request, applied=False, reason="not co-located")

    succeeded, reason = _roll_cast_success(state, caster, request.spell, rng, wand_skill_level)
    if not succeeded:
        return CastExecutionResult(request, applied=False, reason=reason)

    target.mystic_winds_active = True
    for army in state.armies_commanded_by(request.target):
        army.movement_points = MYSTIC_WINDS_MOVEMENT_POINTS
    return CastExecutionResult(request, applied=True)


@dataclass(slots=True, frozen=True)
class LocateObjectResult:
    location: HexCoord
    holder_leader_id: int


def locate_object(state: GameState, item_id: int) -> LocateObjectResult | None:
    """"the provincial location of any magic item will be revealed to the
    spellcaster, as well as who is guarding the item, if anyone." Only
    answerable for a currently leader-held item (``models/item.py
    ItemInstance.owner_leader_id`` set) -- see the module docstring's
    own Phase 206 addendum for why feature/monster-guarded items
    (``item_id`` unknown, or known but ``owner_leader_id is None``)
    return ``None`` here rather than a guess. A caller only reaches this
    once the spell's own cast-success roll (``_execute_locate_object``)
    has already succeeded.
    """

    item = state.items.get(item_id)
    if item is None or item.owner_leader_id is None:
        return None
    holder = state.leaders.get(item.owner_leader_id)
    if holder is None:
        return None
    return LocateObjectResult(location=holder.location, holder_leader_id=item.owner_leader_id)


def _execute_locate_object(
    state: GameState, leader_id: int, request: CastRequest, rng: random.Random, wand_skill_level: int | None = None
) -> CastExecutionResult:
    """A pure information spell -- mutates nothing in ``state``, unlike every
    other spell above. Only gates the cast-success roll; the actual
    "where is item X" answer is ``locate_object(state, request.target)``,
    a separate query kept outside ``CastExecutionResult``'s own shared
    applied/reason shape (see the module docstring's own Phase 206
    addendum for why).
    """

    caster = state.leaders[leader_id]
    succeeded, reason = _roll_cast_success(state, caster, request.spell, rng, wand_skill_level)
    if not succeeded:
        return CastExecutionResult(request, applied=False, reason=reason)

    return CastExecutionResult(request, applied=True)


# Illusory Fog [IF], module docstring's own Phase 207 addendum -- tied to
# Ability.ILLUSION. No skill-level scaling given in the rule text.
ILLUSORY_FOG_STRENGTH_MULTIPLIER = 0.5
ILLUSORY_FOG_EXTRA_MOVEMENT_COST = 1
ILLUSORY_FOG_DISSIPATES_AT_END_OF_GAMETURN = True


def _execute_illus_fog(
    state: GameState,
    leader_id: int,
    request: CastRequest,
    rng: random.Random,
    board_width: int,
    wand_skill_level: int | None = None,
) -> CastExecutionResult:
    """"the Illusionist summons a dense fog to blanket a province... The spell
    must be cast on an adjacent or co-located province." See the module
    docstring's own Phase 207 addendum for the full quoted rule text and
    why the strength/movement effects below aren't wired into a
    consuming pipeline from here.
    """

    caster = state.leaders[leader_id]
    _coord, province = _resolve_province_target(state, caster, request.target, board_width)
    if province is None:
        return CastExecutionResult(request, applied=False, reason="province not found or not in range")

    illus_fog_multiplier = 0.5 if province_halves_spell_chance(state, _coord, Ability.ILLUSION) else 1.0
    succeeded, reason = _roll_cast_success(
        state, caster, request.spell, rng, wand_skill_level, success_chance_multiplier=illus_fog_multiplier
    )
    if not succeeded:
        return CastExecutionResult(request, applied=False, reason=reason)

    province.illusory_fog_active = True
    return CastExecutionResult(request, applied=True)


def is_illusory_fog_affected_air_unit(army_type: ArmyType, mystic_winds_active: bool) -> bool:
    """"All air units (Dragon Wings, Eagle Wings and those affected by 'Mystic
    Winds' Spell)..." -- combines the static per-``ArmyType``
    ``models/army_type.py OVERFLIGHT_AIR`` membership with a caller-
    supplied Mystic Winds flag, since this project has no per-army way
    to derive that flag itself yet (see ``turn/cast_execution.py``'s own
    Phase 204 addendum, ``MYSTIC_WINDS_MOVES_AS_AIR_UNIT``).
    """

    return army_type in OVERFLIGHT_AIR or mystic_winds_active


def illusory_fog_strength(base_strength: float, *, affected: bool) -> float:
    """"have their strength halved for any battle in the affected province."
    ``affected`` is the caller's own ``is_illusory_fog_affected_air_
    unit()`` result (and, implicitly, whether the battle's own province
    has ``ProvinceState.illusory_fog_active`` set). Called from
    ``turn/strength.py compute_effective_strength()`` as of Phase 249,
    via its own ``illusory_fog_affected`` parameter -- see that
    function's own docstring.
    """

    if not affected:
        return base_strength
    return base_strength * ILLUSORY_FOG_STRENGTH_MULTIPLIER


def quality_one_level_down(quality: Quality) -> Quality:
    """One quality level below ``quality``, clamped at ``Quality.DEPLETED``
    -- rulebook [4.25.3]'s own "(it may instead drop a level in quality.)"
    for a plague-immune army, Phase 233. Not the same mechanic as
    ``turn/combat.py roll_quality_change()`` (a battle-outcome step
    function with its own win/loss-conditioned odds) -- this is a flat
    one-level drop, the plague rule's own entire description of the
    effect.
    """

    return Quality(max(Quality.DEPLETED.value, quality.value - 1))


def apply_plague_exposure(state: GameState, coord: HexCoord, chance: float, rng: random.Random) -> None:
    """Tests every eligible army at ``coord`` against one Plague exposure --
    rulebook [4.25.3], shared by the initial cast (``_execute_plague()``)
    and the spread mechanic (``turn/plague_spread.py resolve_plague_
    spread()``, Phase 233) so both apply the exact same army-eligibility
    and immunity rules. "Only the four humanoid races can be infected" --
    armies with no recorded ``kingdom_id`` (mercenaries) are skipped, the
    same "no race to check" gap the original cast-only version already
    had.

    **Immunity** ("If a unit survives a plague, it's immunized from
    dying in future plagues (it may instead drop a level in quality.)"):
    an army not yet marked ``plague_immune`` rolls the ordinary destroy
    chance -- destroyed on a hit, marked immune on a miss (it "survived
    a plague"). An already-immune army instead rolls the *same* `chance`
    for a one-level quality downgrade (`quality_one_level_down()`) --
    the rulebook names no separate probability for this "may instead"
    clause, so reusing the destroy chance is a documented, unsourced
    choice, not a recovered formula.

    **Penicillin** (Discovery.txt, Phase 270): "affected armies will
    have a 50% chance of losing one level of quality" -- an army whose
    own ``kingdom_id`` owns Penicillin always takes this flat,
    non-destroy outcome (the same shape as the immunity branch above,
    but at ``PENICILLIN_QUALITY_DOWNGRADE_CHANCE`` regardless of
    ``chance`` or prior ``plague_immune`` status), never the destroy
    roll. **Phase 300 fix**: the source text has a second clause this
    project's own bug-hunt audit found silently dropped -- "all armies
    (yours and your ally's) are protected in your provinces." An army
    whose *own* kingdom lacks Penicillin is still protected here if
    ``coord``'s owning kingdom has it and is allied with (or the same
    as) the army's kingdom -- previously this project only ever
    consulted the army's own kingdom, so an allied army garrisoned in a
    Penicillin-owning kingdom's own territory could be destroyed by the
    ordinary roll instead of only ever risking the flat downgrade.

    **Good King** (Phase 664, ``models/office.py OFFICE_TITLE_
    DESCRIPTION``): "due to their hospitals, the Plague spell has a
    -15% chance of affecting any unit owned by your Kingdom or in its
    territory." A per-army reduction (floored at 0) to the same
    ``chance`` used by both the fresh-exposure and the already-immune
    quality-downgrade rolls below -- "your Kingdom" is the current
    Good King titleholder's own Kingdom; an army is protected if it
    belongs to that Kingdom, or sits in a province that Kingdom owns,
    regardless of the army's own owner.
    """

    province = state.provinces.get(coord)
    province_owner_id = province.owner_kingdom_id if province is not None else None
    province_owner_has_penicillin = (
        province_owner_id is not None and Discovery.PENICILLIN in state.kingdoms[province_owner_id].discoveries
    )

    good_king_holder = resolve_office_holder(state, Office.GOOD_KING)
    good_king_kingdom_id = None
    if good_king_holder is not None:
        good_king_leader = state.leaders.get(good_king_holder.leader_id)
        good_king_kingdom_id = good_king_leader.kingdom_id if good_king_leader is not None else None

    for army in list(state.armies_at(coord)):
        if army.kingdom_id is None:
            continue
        kingdom = state.kingdoms[army.kingdom_id]
        if kingdom.race not in HUMANOID_RACES:
            continue
        protected_by_penicillin = Discovery.PENICILLIN in kingdom.discoveries or (
            province_owner_has_penicillin and state.is_allied(army.kingdom_id, province_owner_id)
        )
        if protected_by_penicillin:
            if rng.random() < PENICILLIN_QUALITY_DOWNGRADE_CHANCE:
                army.quality = quality_one_level_down(army.quality)
            continue
        army_chance = chance
        if good_king_kingdom_id is not None and (
            army.kingdom_id == good_king_kingdom_id or province_owner_id == good_king_kingdom_id
        ):
            army_chance = max(0.0, chance - GOOD_KING_PLAGUE_PROTECTION)
        if army.plague_immune:
            if rng.random() < army_chance:
                army.quality = quality_one_level_down(army.quality)
            continue
        if rng.random() < army_chance:
            state.remove_army(army.army_id)
        else:
            army.plague_immune = True


def _execute_plague(
    state: GameState,
    leader_id: int,
    request: CastRequest,
    rng: random.Random,
    board_width: int,
    wand_skill_level: int | None = None,
) -> CastExecutionResult:
    """Rulebook [4.25.3]: "cast on a province you're in or adjacent to it: every unit
    there has a 10%+10%/level chance of being destroyed. Only the four
    humanoid races can be infected."

    **"Casting more than one Plague spell does not have a cumulative
    effect" (Phase 233)**: if ``province.plague_active`` is already
    ``True``, the cast still succeeds (``applied=True``) but skips
    ``apply_plague_exposure()`` entirely -- the province is already
    afflicted, so a second cast adds nothing. A fresh affliction sets
    ``plague_active = True`` (the spread mechanic's own entry point --
    see ``turn/plague_spread.py``'s module docstring for "the next
    phase, 15%-per-adjacent-province" propagation this now feeds) and
    applies the caster-level-boosted exposure chance via the shared
    ``apply_plague_exposure()``.
    """

    caster = state.leaders[leader_id]
    coord, province = _resolve_province_target(state, caster, request.target, board_width)
    if province is None:
        return CastExecutionResult(request, applied=False, reason="province not found or not in range")

    plague_multiplier = 0.5 if province_halves_spell_chance(state, coord, Ability.NECROMANCY) else 1.0
    succeeded, reason = _roll_cast_success(
        state, caster, request.spell, rng, wand_skill_level, success_chance_multiplier=plague_multiplier
    )
    if not succeeded:
        return CastExecutionResult(request, applied=False, reason=reason)

    if province.plague_active:
        return CastExecutionResult(request, applied=True)

    province.plague_active = True
    chance = PLAGUE_BASE_DESTROY_CHANCE + PLAGUE_DESTROY_CHANCE_PER_LEVEL * _caster_level(
        state, caster, Ability.NECROMANCY, wand_skill_level
    )
    apply_plague_exposure(state, coord, chance, rng)
    return CastExecutionResult(request, applied=True)


def _execute_scar_terrain(
    state: GameState,
    leader_id: int,
    request: CastRequest,
    rng: random.Random,
    board_width: int,
    wand_skill_level: int | None = None,
) -> CastExecutionResult:
    """"a co-located or adjacent province is scarred and mangled, and its tax base
    is reduced by 2 gold immediately and permanently." See module
    docstring's own Scar Terrain addendum for the full quoted rule text
    and why the "tax base reaches 0" collapse (``scar_terrain_is_
    exhausted``/``scar_terrain_collapse`` below) is deliberately not
    triggered from here.
    """

    caster = state.leaders[leader_id]
    _coord, province = _resolve_province_target(state, caster, request.target, board_width)
    if province is None:
        return CastExecutionResult(request, applied=False, reason="province not found or not in range")

    scar_terrain_multiplier = 0.5 if province_halves_spell_chance(state, _coord, Ability.NECROMANCY) else 1.0
    succeeded, reason = _roll_cast_success(
        state, caster, request.spell, rng, wand_skill_level, success_chance_multiplier=scar_terrain_multiplier
    )
    if not succeeded:
        return CastExecutionResult(request, applied=False, reason=reason)

    province.scar_terrain_gold_reduction += SCAR_TERRAIN_TAX_REDUCTION
    return CastExecutionResult(request, applied=True)


def scar_terrain_is_exhausted(remaining_tax_base: int) -> bool:
    """"When the tax base reaches 0 gold, the province becomes incapable of
    supporting normal life forms." True once the remaining tax base
    (caller-supplied -- this project has no revenue system tracking a
    real starting value yet, see module docstring) is at or below zero.
    """

    return remaining_tax_base <= 0


def scar_terrain_collapse(province: ProvinceState, *, new_land_race: Race | None = None) -> None:
    """Applies Scar Terrain's own tax-exhaustion collapse to ``province``, once a
    future revenue-system phase determines ``scar_terrain_is_exhausted``
    is True (never called automatically by this module -- see its own
    docstring).

    A Sea province ("will just lose whatever provincial racial and army
    type they may have") unconditionally becomes ``Race.NO_RACE`` -- no
    ``ArmyType`` is compatible with it (``turn/recruit.py
    is_army_type_compatible_with_race`` returns False for every type
    against a race that's neither in ``HUMANOID_RACES`` nor a
    ``MONSTROUS_ARMY_RACE`` key), so nothing else needs clearing.

    A land province needs ``new_land_race`` from ``SCAR_TERRAIN_LAND_
    COLLAPSE_RACES`` -- which of the three ("usually by immigration from
    an adjacent province") is the caller's own decision, not something
    this function can determine from the province alone; raises
    ``ValueError`` if omitted or invalid, rather than silently guessing.
    Changing ``province.race`` alone is sufficient for Dragons/Trolls to
    become the only recruitable ``ArmyType`` there too (``models/
    army_type.py MONSTROUS_ARMY_RACE`` already ties each to exactly one
    type) -- see module docstring for why Orcish has no single such type.
    """

    if province.effective_terrain() is Terrain.SEA:
        province.race = Race.NO_RACE
        return
    if new_land_race not in SCAR_TERRAIN_LAND_COLLAPSE_RACES:
        raise ValueError(f"new_land_race must be one of {SCAR_TERRAIN_LAND_COLLAPSE_RACES}, got {new_land_race!r}")
    province.race = new_land_race


def _execute_skeletal_army(
    state: GameState,
    kingdom_id: int,
    leader_id: int,
    request: CastRequest,
    rng: random.Random,
    wand_skill_level: int | None = None,
) -> CastExecutionResult:
    """Rulebook [4.25.1] (Phase 60): "if the caster is in a province where a battle
    was previously fought and armies were destroyed, he can recruit a
    horde of skeletons... one army per skill level, provided enough
    units died in battle... identical in every way to the dead army,
    with all its movement points... the caster has no way to choose
    which unit type answers the call." No target field (``cast_decode.py``'s
    ``NO_TARGET_SPELLS``) -- operates on the caster's own current
    province.

    Draws from ``GameState.battle_graveyard`` (Phase 60), consuming one
    entry per army raised (arbitrary order -- "no way to choose," so
    which specific entry is picked doesn't matter). Capped at
    ``min(caster's Necromancy level, entries available)``; if the
    graveyard is empty for this province, the precondition itself fails
    before any success roll, the same "check applicability first" order
    every other spell here uses. "All its movement points" is
    approximated as ``movement_points=0``, the same fresh-unit default
    every newly-recruited ``ArmyState`` gets (``turn/
    recruit_execution.py``) -- carrying over the exact remaining
    movement the original army had at the moment of its own death has no
    precedent anywhere else in this project's state model. Every raised
    army gets ``is_skeletal=True`` (Phase 236) -- the real `Zomboid`
    army-state marker (`turn/army_naming.py`'s own docstring), driving
    the " Skel " tag in the real Army List table's own name column. The
    global 350-unit world cap and ~10%/turn decomposition past it are
    now enforced -- see ``turn/skeletal_decay.py decompose_graveyard()``
    (Phase 309) and ``GameState.battle_graveyard``'s own docstring. That
    decay only ever removes graveyard entries (dead, not yet raised);
    it never touches an army this function has already raised.

    Office.UNDEAD_KING's own second, unique perk (Phase 664, ``models/
    office.py OFFICE_TITLE_DESCRIPTION``): "when < casts the Skeletal
    Armies spell, the maximum number of units that can be raised by <2
    increases by 1." Scoped to "<" -- the titleholder personally
    casting, not every leader of his Kingdom (unlike Pagan King's own
    White-Magic bonus above) -- so this checks ``leader_id`` against
    the resolved holder directly, before capping at graveyard size.
    """

    caster = state.leaders[leader_id]
    graveyard = state.battle_graveyard.get(caster.location) or []
    if not graveyard:
        return CastExecutionResult(request, applied=False, reason="no dead units in this province to raise")

    succeeded, reason = _roll_cast_success(state, caster, request.spell, rng, wand_skill_level)
    if not succeeded:
        return CastExecutionResult(request, applied=False, reason=reason)

    necromancy_level = _caster_level(state, caster, Ability.NECROMANCY, wand_skill_level)
    undead_king_holder = resolve_office_holder(state, Office.UNDEAD_KING)
    if undead_king_holder is not None and undead_king_holder.leader_id == leader_id:
        necromancy_level += 1
    raised_count = min(necromancy_level, len(graveyard))
    for _ in range(raised_count):
        entry = graveyard.pop()
        state.add_army(
            ArmyState(
                state.new_army_id(),
                kingdom_id,
                entry.army_type,
                entry.quality,
                caster.location,
                commanded_by=leader_id,
                is_skeletal=True,
            )
        )
    if not graveyard:
        del state.battle_graveyard[caster.location]

    return CastExecutionResult(request, applied=True)


def _offices_held_by_kingdom(state: GameState, kingdom_id: int) -> list[Office]:
    """Every Office (including Emperor) currently held by a leader
    belonging to ``kingdom_id`` -- High Chancellor's own Crystal Ball
    addendum needs exactly this list. Reuses ``resolve_all_office_
    holders()`` (Phase 475) rather than re-deriving each office's own
    resolution logic.
    """

    held: list[Office] = []
    for office, holder in resolve_all_office_holders(state).items():
        if holder is None:
            continue
        holder_leader = state.leaders.get(holder.leader_id)
        if holder_leader is not None and holder_leader.kingdom_id == kingdom_id:
            held.append(office)
    return held


def _execute_clairvoyance(
    state: GameState,
    kingdom_id: int,
    leader_id: int,
    request: CastRequest,
    rng: random.Random,
    wand_skill_level: int | None = None,
) -> CastExecutionResult:
    """Rulebook [4.22.3] (Phase 193): "for the rest of the turn, the caster
    knows everything that happens to the target" -- see the module
    docstring's "Phase 193 addendum" for exactly what this does and
    doesn't model: only the confirmed "who gets to know" half, via
    ``LeaderState.clairvoyance_watchers`` (``models/game_state.py``'s
    own docstring) -- no event feed exists yet to surface anything to
    that watcher. Records ``kingdom_id`` (the acting Kingdom, the same
    parameter ``_execute_charm``'s own "target.kingdom_id = kingdom_id"
    line uses), not ``caster.kingdom_id`` -- identical in every real
    caller, but this is the value the rest of ``execute_cast`` already
    threads through. No co-location/adjacency precondition -- the
    sourced text names none, unlike ``_execute_kill_enemy``'s own
    Kill_Enemy-specific "not co-located" check.

    **Phase 492 addendum -- High Chancellor's own Crystal Ball**
    (``OFFICE_PERK_DESCRIPTION[Office.CHANCELLOR]``, ``CARICHE E
    ABLITÀ.txt``'s real text): "just cast a Clairvoyance spell (CA-CL),
    which will automatically be successful even if you have no skill in
    psychic magic. Using the Crystal Ball will not use up a Psychic
    Magic spell." When ``leader_id`` currently holds the office
    (``resolve_office_holder()``, the established Phase 488-491 lookup
    convention), the whole ``_roll_cast_success()`` gate is skipped
    outright -- not just its own outcome forced to success, since
    "will not use up a Psychic Magic spell" means the per-turn action-
    cast slot ``_roll_cast_success()`` would otherwise consume must
    never be touched at all. The same Chancellor cast also gets the
    Crystal Ball's own extra payload, ``CastExecutionResult.
    clairvoyance_target_offices`` -- "it will also list all offices and
    titles held by the kingdom of the spied-upon character."

    **Phase 637 addendum -- ``Was_Clairved``'s own CHARACTERS-report
    reveal** (``REPORTS.PAS Rep_Leaders``, a *different* real mechanic
    from the Phase 193/408 watcher-feed above): every successful cast
    also records ``caster.clairvoyance_cast_target = target.leader_id``
    (``LeaderState.clairvoyance_cast_target``, mirroring the real
    ``lspec[l2]``'s single packed ``clobj`` value) -- unconditionally,
    not gated on ``AdvancedAbility.ENHANCED_CLAIRVOYANCE`` here. The
    ability gate is checked separately at read time by ``report/
    turn_report.py _was_clairved()``, exactly mirroring how the real
    ``Was_Clairved`` checks ``Has_SA(l2,Expand_Clair)`` against the
    already-written value rather than gating the write.
    """

    caster = state.leaders[leader_id]
    target = state.leaders.get(request.target)
    if target is None:
        return CastExecutionResult(request, applied=False, reason="target character not found")

    chancellor_holder = resolve_office_holder(state, Office.CHANCELLOR)
    is_chancellor = chancellor_holder is not None and chancellor_holder.leader_id == leader_id

    if is_chancellor:
        succeeded, reason = True, None
    else:
        succeeded, reason = _roll_cast_success(state, caster, request.spell, rng, wand_skill_level)
    if not succeeded:
        return CastExecutionResult(request, applied=False, reason=reason)

    target.clairvoyance_watchers.add(kingdom_id)
    caster.clairvoyance_cast_target = target.leader_id

    target_offices = None
    if is_chancellor and target.kingdom_id is not None:
        target_offices = _offices_held_by_kingdom(state, target.kingdom_id)

    return CastExecutionResult(request, applied=True, clairvoyance_target_offices=target_offices)


def _execute_hide_feature(
    state: GameState,
    leader_id: int,
    request: CastRequest,
    rng: random.Random,
    board_width: int,
    wand_skill_level: int | None = None,
) -> CastExecutionResult:
    """Rulebook [4.23.3] (Phase 193): "This feature will become magically
    hidden" (``models/power.py CAST_SPELL_FEATURE_DESCRIPTION`` corroborates
    the same wording). ``CastRequest.target`` for Hide_Feature only ever
    decodes to a *province* coordinate, never a specific feature-instance
    id (``turn/cast_decode.py PROVINCE_TARGET_SPELLS`` -- confirmed
    against all 108 real sample Cast phases, none carries a feature id
    the way Illus_Terrain's own ``phase.extra[1]`` does). Since [3.2]
    itself says "There can sometimes be more than 1 feature in a
    province," and the decode layer gives no way to name which one,
    this hides **every** ``Feature`` at the resolved coordinate -- a
    deliberate, unsourced judgment call (see the module docstring's
    "Phase 193 addendum"), not a guess at a disambiguation mechanism
    this project has no data to build. An empty-features province fails
    the same "check applicability first" way every other province spell
    here does, before any success roll.
    """

    caster = state.leaders[leader_id]
    coord, province = _resolve_province_target(state, caster, request.target, board_width)
    if province is None:
        return CastExecutionResult(request, applied=False, reason="province not found or not in range")
    features = state.features_at(coord)
    if not features:
        return CastExecutionResult(request, applied=False, reason="no feature to hide")

    hide_feature_multiplier = 0.5 if province_halves_spell_chance(state, coord, Ability.ILLUSION) else 1.0
    succeeded, reason = _roll_cast_success(
        state, caster, request.spell, rng, wand_skill_level, success_chance_multiplier=hide_feature_multiplier
    )
    if not succeeded:
        return CastExecutionResult(request, applied=False, reason=reason)

    for feature in features:
        feature.magically_hidden = True
    return CastExecutionResult(request, applied=True)


def _gate_angel_due_alignment(state: GameState, rng: random.Random) -> Alignment:
    """The VALHALLA rotation (Phase 195, user-supplied): "Ciascun
    allineamento da Buono a Malvagio... riceverà una visita una volta
    ogni cinque turni" -- lazily determines (and caches, once per
    ``turn_number``) which of the 5 ``GATE_ANGEL_ELIGIBLE_ALIGNMENTS``
    is due a visit this turn, the first time any Gate Angel cast is
    attempted that turn. Once all 5 have been used in the current
    5-turn cycle, the cycle resets and all 5 become eligible again --
    exactly the user's own worked example (turn 0 Druid, turn 1 picks
    from the remaining 4, ..., turn 5 restarts).

    **Phase 386 correction**: AKGEN's own confirmed
    ``recipient_selection.alignment_rotation`` gives this same "pick
    uniformly among the alignments not yet used this cycle" behavior via
    literal rejection sampling on a 5-bit mask (`choose (IRand MOD 5)+1
    by rejection among bits not present`) -- mathematically identical to
    ``rng.choice(remaining)`` below, so that part needed no change. But
    it also names a **second, independent** reset condition this project
    had missed: "clear... also on the internal gameturn MOD 5 = 4
    boundary" -- the cycle now force-resets on that turn-count boundary
    regardless of how many alignments have actually been visited (e.g. a
    turn with no Gate Angel cast at all still advances the boundary).
    """

    if state.gate_angel_due_alignment_turn == state.turn_number:
        return state.gate_angel_due_alignment

    if (
        len(state.gate_angel_cycle_visited) >= len(GATE_ANGEL_ELIGIBLE_ALIGNMENTS)
        or state.turn_number % 5 == 4
    ):
        state.gate_angel_cycle_visited.clear()

    remaining = [a for a in GATE_ANGEL_ELIGIBLE_ALIGNMENTS if a not in state.gate_angel_cycle_visited]
    chosen = rng.choice(remaining)
    state.gate_angel_cycle_visited.add(chosen)
    state.gate_angel_due_alignment = chosen
    state.gate_angel_due_alignment_turn = state.turn_number
    state.gate_angel_candidates_this_turn = 0
    return chosen


def _gate_angel_register_candidate(state: GameState, kingdom_id: int, rng: random.Random) -> None:
    """**Phase 386 correction**: AKGEN's own confirmed ``gate_angel.
    multiple_casts``/``more_than_two_quirk`` replace what this function
    used to do (reservoir sampling for a *uniformly* random winner) with
    the real, much simpler -- and non-uniform -- rule: "first cast
    occupies the slot; every later cast has 50% to be nullified and 50%
    to replace the current incumbent." For ``n`` same-turn, same-due-
    alignment candidates this makes the *last* candidate win with
    probability 1/2, the second-to-last 1/4, and so on geometrically
    back to the *first* candidate, who ties the second one at the tail
    (1/2^(n-1) each) since it never gets an own "replace" roll, only
    survival rolls -- confirmed by hand-deriving these exact fractions
    from the rule before coding it, matching the source's own quoted
    "last has 1/2, preceding 1/4, earlier decay geometrically."
    """

    state.gate_angel_candidates_this_turn += 1
    n = state.gate_angel_candidates_this_turn
    won = n == 1 or rng.random() < 0.5
    if won:
        state.last_gate_angel_kingdom = kingdom_id
        state.last_gate_angel_turn = state.turn_number


def _execute_gate_angel(
    state: GameState,
    kingdom_id: int,
    leader_id: int,
    request: CastRequest,
    rng: random.Random,
    wand_skill_level: int | None = None,
) -> CastExecutionResult:
    """``AdvancedAbility.GATE_ANGEL_SPELL`` (Phase 194, corrected Phase
    195 -- see module docstring's "Secret spells" section for the full
    quote and design rationale).

    Checks whether the caster's own Kingdom alignment (clamped through
    ``_gate_angel_clamped_alignment`` -- Phase 386: Divine counts as
    Good, Undead as Evil, rather than being excluded outright) matches
    this turn's due alignment *before* rolling (the same "check
    applicability first" order every other spell here uses); a
    successful roll enters the contention drawing for who actually gets
    the visit (``_gate_angel_register_candidate``).
    """

    caster = state.leaders[leader_id]
    kingdom = state.kingdoms[kingdom_id]

    due_alignment = _gate_angel_due_alignment(state, rng)
    if _gate_angel_clamped_alignment(kingdom.alignment) is not due_alignment:
        return CastExecutionResult(request, applied=False, reason="not this alignment's turn for a Valhalla visit")

    succeeded, reason = _roll_cast_success(state, caster, request.spell, rng, wand_skill_level)
    if not succeeded:
        return CastExecutionResult(request, applied=False, reason=reason)

    _gate_angel_register_candidate(state, kingdom_id, rng)
    return CastExecutionResult(request, applied=True)
