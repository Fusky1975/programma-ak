"""Executing a Search order (rulebook [3.3] Search feature) -- Phase 132.

**Rulebook [3.3], quoted in full** (also quoted in ``turn/search_decode
.py``'s own docstring): "A character may Search any feature that has
been discovered by his kingdom, or that he hears about from another
King. When a character Searches a feature, he must face the guardian
monster first. He specifies an Encounter Plan. If he defeats the
monster, the treasure in the feature is his... Characters must Search
features as individuals; it is a point of honor to defeat a monster in
single combat."

This module closes the gap ``turn/search_decode.py`` and ``models/
feature.py`` both flagged as blocking Search's own resolution: "needs a
personal, non-army Encounter/combat resolver... that this project
doesn't have yet." ``turn/encounter.py`` (Phase 48) built exactly that
core, and Phase 132 extends it (``Combatant.melee_damage_range``) so a
guardian monster can fight with its own species-specific damage die
instead of the character-only one.

**Scope, and why it stays narrower than "every Search always
resolves"**:

- **Guardian combat stats.** Draws from ``models/monster.py
  MONSTER_COMBAT_STATS`` (Phase 154), a project-original, user-compiled
  table covering all 60 real monster species -- see that module's own
  Phase 154 addendum for full provenance. Hit points are rolled per
  encounter via ``rng.randint(*stats.hit_points_range)``, since the
  source gives a range (not a fixed value) for every species. A feature
  guarded by ``Monster.NOMONSTER`` (the sentinel, not a real species)
  still reports ``combat_resolved=False`` rather than inventing stats.
- **Encounter Plan tactics execute in strict list order (Phase 170
  correction).** Regolamento AK.txt's own worked examples ([11.3],
  "ESEMPI DI PIANI D'INCONTRO") settle this precisely: "FI, FL.
  Significato: Tirare con l'Arco, poi fuggire" ("Shoot with the bow,
  then flee") -- Fire Arrow is attempted *first*, and Flee is only
  attempted if it doesn't end the fight. Phase 169 originally rolled a
  ``Maneuver.FLEE`` tactic unconditionally *before* Melee regardless of
  its position in the plan; this real example proves that was wrong in
  general (it only ever matched by coincidence, since every tested plan
  happened to list Flee before Melee already). ``execute_search()`` now
  walks ``request.tactics`` in order, running each wired tactic until
  one resolves the encounter (or, for Fire Arrow, exhausts its free
  attacks with nobody dead) before moving to the next.
  ``turn/search_decode.py``'s own docstring found, empirically, that
  "every real Search order ends in Melee and/or Scout" across all 12
  real Search phases in the sample files -- ``Maneuver.MELEE``,
  ``Maneuver.FLEE``, and (as of this phase) ``Maneuver.SHOOT`` (Fire
  Arrow) are wired to a real resolution; at the time, every other tactic
  (Steal, Talk, Say, Give, Fulfill, Scout, Cast, Use_MI, Beg) was
  silently skipped in the walk rather than aborting it, since a plan
  mixing a wired and an unwired tactic is exactly what the real examples
  above show ("ST, CA-FI, ME, SC" mixes Steal and Cast, both unwired at
  the time, with Melee). **Since wired up through Phase 274**: Steal
  (Phase 239), Cast (Phase 209/210/211/237/238), Talk/Say (Phase 240),
  Beg (Phase 241), Fulfill (Phase 258), Use_MI (Phase 274, see that
  phase's own addendum below), and Scout (Phase 274, resolved as a
  post-processing step -- see ``_apply_scout()``'s own docstring) all
  now resolve for real; the "unwired tactic, keep walking" fallback
  below still applies to whatever remains unwired (**Give only** --
  confirmed directly by the user, project author: Give has exactly one
  real use, passing an item to another Hero or King, never to a
  monster, so it's structurally inapplicable to Search's own
  monster-only target, not merely unresearched).
  If no wired tactic is present at all, or the walk finishes without
  resolving (Fire Arrow's shots ran out and nothing else followed),
  ``combat_resolved`` reflects that honestly (see ``execute_search()``'s
  own body). **Confirmed directly by the user (Phase 173, project
  author)**: only a single Fire Arrow order can ever appear in an
  Encounter Plan, and once its shots are exhausted "i combattenti
  passano alla fase successiva che dipende dall'elenco di ordini messi
  nel piano d'incontro" ("combatants move to the next phase, determined
  by the tactic list in the Encounter Plan") -- exactly this walk's own
  design, now sourced rather than inferred solely from [11.3]'s worked
  examples. See ``turn/encounter.py``'s own module docstring (Phase 48's
  "What happens after Fire Arrow's free attacks run out" bullet, the
  same user clarification quoted there directly, not a separate,
  Phase-173-tagged addendum -- that number is this module's own, for
  reusing the fact here) for the full quote.
- **Fire Arrow (Phase 170, rulebook [5.2]).** "The base chance to hit is
  30%, plus 10% per Archery level, and the damage is 1-6 hit points."
  Previously left unwired specifically because "nothing in any available
  source says a monster's own ``missile_skill`` drives an equivalent
  formula" -- but ``models/monster.py``'s own Monster Table quote sits
  directly beneath [5.2]'s formula and gives every species an explicit
  Missile Skill/Damage column (e.g. Giant `1/1-7`), which *is* the
  source for exactly that: a monster's ``missile_skill`` plugs into the
  same [5.2] formula a character's Archery level does, and its own
  ``missile_damage`` (``models/monster.py MonsterCombatStats
  .missile_damage``) feeds ``Combatant.missile_damage_range`` (``turn/
  encounter.py``'s own Phase 170 addendum) the same way melee damage
  already did (Phase 132). A monster with ``missile_skill=0`` (no
  ranged attack at all) simply gets zero free attacks
  (``fire_arrow_free_attacks(0) == 0``) -- a natural consequence of the
  formula, not a special-cased exclusion.
- **Flee (Phase 169, rulebook [5.6]).** "The character can declare to
  prefer flight over combat. The chance of fleeing from fast monsters is
  20%, from medium-speed monsters or other characters 50%, and slow
  monsters can be escaped from 80% of the time." Sourced verbatim,
  including all three percentages, in ``models/monster.py``'s own [5.6]
  quote (``FLEE_CHANCE`` below is keyed by the same ``MonsterSpeed`` tier
  already sourced there). A successful roll ends the Search with no
  combat and no loot; a failed roll falls through to the plan's next
  wired tactic, per the ordering correction above.
  **Weak-Temperament and Invisibility flee bonuses (Phase 286)**: the
  rulebook's own text at [5.6] reads, verbatim, "(NOVITA') I personaggi
  Cauti hanno il 30% in più di possibilità di fuggire" -- naming only
  the **Cautious** Temperament. The user (project author) confirmed
  extending this same +30% to **Cowardly** as well is a deliberate,
  project-original design choice, not a literal reading of the quoted
  text -- Cowardly already sits at the far end of the Temper Table's own
  flee-inclination spectrum (51-100% refusal range, vs. Cautious' own
  1-50%), so a Cowardly character being at least as flee-prone as a
  Cautious one is a reasonable extension, but it is documented here as
  exactly that (an extension), not conflated with the sourced text.
  **Phase 312 addendum -- the rulebook contradicts itself on this exact
  number, now consciously resolved.** `Regolamento AK.txt`'s own closing
  "NUOVE REGOLE E MODIFICHE" appendix (line 3533) restates the same rule
  as "I Cauti hanno il +20% di possibilità alla fuga" -- ten points
  lower than the body text's own [5.6] figure quoted above, and this
  project had been implementing the body text's +30% since Phase 286
  without that conflict ever having been noticed or a choice made
  between the two consciously. The user (project author), asked
  directly, confirmed **+30% is correct** -- `WEAK_TEMPER_FLEE_CHANCE_
  BONUS` stays unchanged at `0.30`; this addendum exists purely so the
  discrepancy and the resolution are on record, not silently sitting in
  two contradictory places in the source text.
  ``effective_flee_chance()`` below adds ``WEAK_TEMPER_FLEE_CHANCE_
  BONUS`` for ``Temper.CAUTIOUS`` or ``Temper.COWARDLY``, and separately
  adds ``INVISIBILITY_FLEE_CHANCE_BONUS`` (``turn/cast_execution.py``'s
  own docstring: "Invisibility's own addendum ('now gives +30% chance to
  flee')") when the fleeing leader is currently invisible (``Combatant.
  is_invisible``, set by the ``Spell.INVISIBILITY`` branch below). Both
  bonuses are **additive percentage points** on the base ``FLEE_CHANCE``
  (not a multiplicative scaling of it) -- the rulebook's own phrasing,
  "30% in più" ("30% more"), reads as a flat probability addition the
  same way the three base percentages themselves are flat, not as "30%
  of the existing chance"; this is a documented interpretation (the same
  "no sourced formula for the exact stacking, pick the plain reading"
  category ``exploration_advantage_multiplier()``'s own docstring already
  uses), not a guess at an alternative formula. The combined result is
  clamped to 100% -- a probability can't exceed certainty. Both bonuses
  can stack together (e.g. a Cautious, currently-invisible leader gets
  both), since nothing in either source excludes the other.
  **Phase 515 addendum -- Melee Evasion (Advanced Ability):** quoted
  directly from ``models/advanced_ability.py ADVANCED_ABILITY_
  DESCRIPTION[MELEE_EVASION]``: "A character becomes expert at evading
  opponents when using the Flee tactic and gains +30% to the chances of
  fleeing a combat." A third additive bonus, same reading and same
  stacking rule as the two above -- ``effective_flee_chance()``'s new
  ``has_melee_evasion`` parameter (both call sites below pass
  ``AdvancedAbility.MELEE_EVASION in leader.advanced_abilities``).
- ~~**Victory's own aftermath is minimal, by design**: rulebook [5.9]
  ("looting a vanquished foe's treasure, magic items changing hands")
  needs a treasure-*instance* and magic-item-ownership model this
  project doesn't have... ``models/item.py`` is a never-populated
  stub. A win only sets ``Feature.looted = True`` (``fstate[fn] =
  Dead``, "sacked & looted") -- the one confirmed, modeled
  consequence.~~ -- **stale as of Phase 242**: the item-ownership
  registry has been real since Phase 140 (``GameState.add_item()``/
  ``ItemInstance``, ``models/item.py``), and a feature's own treasure
  *instance* field (``Feature.treasure``, set by world generation) has
  existed since Phase 242, which also wired the actual grant -- a
  Search win now calls ``state.add_item(feature.treasure, leader_id)``
  right alongside the ``Feature.looted = True`` flag (see
  ``_outcome_from()`` below), whenever world generation gave this
  feature a treasure to begin with. ``models/feature.py``'s own
  docstring already carries the corrected version of this note; this
  copy was simply never updated to match.
- **A loss kills the searching leader**, no special carve-out: personal
  combat's generic rule ([5.0]: "until one combatant is killed") applies
  in full here, the same reasoning ``turn/challenge_execution.py``'s own
  docstring already gives for why a Challenge loser (unlike a Duel
  commander, [7.1]'s own special case) dies for real.
- **Troll regeneration** (Phase 155, ``turn/encounter.py``'s own
  addendum): a Troll's own monster combatant gets
  ``regenerates_hp=TROLL_REGENERATION_PER_COMBAT_ROUND``, so
  ``resolve_melee_duel()`` heals it 1 hit point at the end of every
  round it survives. The FIREBALL-negates-regeneration clause stays
  unwired here too, for the same reason ``turn/encounter.py``'s own
  addendum gives (blocked on the Cast-tactic-spell-id gap).
- **Co-location is enforced** (``leader.location == feature.coord``):
  not literally quoted in [3.3] (which is about *knowledge* of a
  feature's location/number, not physical presence), but single combat
  against a guardian monster obviously needs the searcher to actually be
  there -- the same "must be co-located to act in person" pattern this
  project already enforces for Challenge, Hire/Fire, and Recruit's
  target-leader check.
- **A winning leader's Defender Merit Points are credited (Phase 255)**:
  ``turn/merit_points.py``'s own "TABELLA DELLE CARICHE IMPERIALI"
  formula had no writer anywhere in this project for
  ``MeritTally.monster_hp_defeated``/``monster_hp_neutralized``.
  ``_outcome_from()`` -- the single point every real "leader wins"
  branch in this module funnels through, whether from Melee, Fire
  Arrow, or one of ``_resolve_cast_tactic()``'s own instant-kill spell
  branches -- now credits the guardian's own *starting* hit points
  (captured before combat mutates them) to ``monster_hp_defeated``.
  **The other half -- "metà dei punti se neutralizzato con trattative"
  (half credit for a monster *negotiated* into standing down rather
  than killed) -- is wired as of Phase 258**: a successful Fulfill (see
  ``_resolve_fulfill()`` below) credits ``monster_hp_neutralized`` with
  half the guardian's own starting hit points instead.

**Not wired into ``plan_dispatch.py``'s existing scripted-rng test
suite as a silent behavior change without review**: unlike Challenge/
Pursue (opt-in only at the caller's choice, Phase 49/50), Search's own
dispatch *is* switched to real execution this phase (see ``turn/
plan_dispatch.py``'s own updated docstring) -- there is no legacy
decode-only consumer left to preserve, since Search was never wired to
mutate ``GameState`` before.

**Phase 175 addendum -- carrying the Fire Arrow shot log out to the
report layer.** ``turn/encounter.py``'s own Phase 175 addendum gives
``resolve_fire_arrow_duel()`` a per-shot log (``EncounterCombatResult
.shots``) so ``report/turn_report.py`` can narrate each shot
individually, including the dragon-breath/boulder-throw/petrifying-gaze
flavor variants from ``Desktop/MOSTRI con statistiche.txt``'s own
footnotes. ``SearchExecutionResult`` gains ``fire_arrow_shots`` (that
same log, copied out of whichever ``EncounterCombatResult`` a Shoot
tactic produced -- empty if the plan never fires an arrow) and
``guardian_monster`` (the species fought, needed by the report layer to
look up ``models/weapon.py MONSTER_RANGED_WEAPON`` and dispatch to a
flavored renderer or the generic one). Both are attached to whichever
``SearchExecutionResult`` this walk eventually returns, whether that's
the Shoot tactic's own terminal outcome, a later Melee tactic's outcome
(if Fire Arrow's shots ran out first without a winner), or the
walk-exhausted fallback -- a shot fired earlier in the plan is still
worth narrating even if it didn't end the fight.

**Phase 178 addendum -- the guardian gets its own Special Encounter
Plan too, and an exhausted tactic list now correctly defaults to
Melee.** Two corrections, both confirmed directly by the user (project
author) before ``models/monster_encounter_plan.py`` was even supplied:

- **"When the list runs out, default to Melee until someone dies."**
  Quoted in full: "Quando finiscono le azioni che vengono messe nel
  piano d'incontro il personaggio inizia a usare automaticamente il
  comando ME ... Il personaggio di default continua a usare il comando
  ME a mischia finche' muore lui o il mostro." Previously, if the
  leader's own plan resolved a ``SHOOT`` tactic that ran out of arrows
  with nobody dead and had no further tactic afterward, the walk fell
  through to the end-of-loop fallback and reported ``winner=None``
  ("inconclusive") -- contradicting this confirmed default. The
  fallback now resolves one full ``resolve_melee_duel()`` call (which
  already fights to the death in a single call, Phase 48) instead of
  reporting an inconclusive draw. This only changes behavior for a plan
  that resolves *some* wired tactic (``combat_attempted=True``) without
  ever reaching an explicit ``MELEE`` tactic of its own -- a plan with
  no wired tactic at all still reports honestly unresolved, since no
  combat was ever attempted in the first place.
- **The guardian's own plan is independent of the leader's.** Per the
  user's own confirmation, each side follows its own Special Encounter
  Plan -- so ``models/monster_encounter_plan.py roll_monster_encounter_
  plan()`` is rolled for the guardian (using ``leader.alignment is
  Alignment.UNDEAD`` for the "attacker is Undead" override condition)
  purely to answer one question: does the guardian's own plan contain a
  bare ``SHOOT`` tactic before its own terminal Melee? If so, a Fire
  Arrow phase happens even when the *leader's* own submitted plan never
  lists ``SHOOT`` at all (previously, Fire Arrow only ever happened if
  the leader's plan asked for it -- meaning species like Titan or Red
  Dragon, whose entire identity is "shoots/breathes before closing to
  melee," never got to use that attack unless the human player happened
  to also write `FI` into their own plan). This still resolves through
  the same single, symmetric ``resolve_fire_arrow_duel()`` call (Phase
  170) -- at most one Fire Arrow phase per encounter either way, so the
  already-confirmed "only a single FI order can ever appear" rule
  (Phase 173) still holds; it's now triggered by *either* side wanting
  it rather than only the leader's own plan. The guardian's own ``CAST``
  entries (most species' plans open with 0-3 of them) are rolled but
  never inspected here -- they remain exactly as unwired as a leader's
  own ``CAST`` tactic always has been, per the user's own explicit
  scoping decision this phase (no personal-combat spell-effect engine
  exists yet for any of the 11 spells these plans reference).

**Phase 274 addendum -- Use_MI wired; Scout wired, project-original,
Give re-confirmed still inapplicable.** The gap this project previously
flagged for Use_MI -- "needs a magic-item-instance -> spell-effect
mapping this project doesn't model" -- has been closed since Phase
140/141 (``GameState.items``, ``models/treasure.py TREASURE_WAND_
SPELL``); that note was simply never updated. Give's own note is
re-confirmed accurate as-is (see above); Scout was re-examined directly
against RULES.AK [5.8] and found real and distinct after all -- the
project author's prior note calling it "'non esiste' as a distinct
mechanic" is now corrected below.

- **Use_MI [US], rulebook [5.1]/[3.11].** "Some magic items can cast
  spells in combat... A spell cast from a magic item is automatically
  successful." Only the 20 spell-casting wands
  (``models/treasure.py TreasureCategory.SPELL_WAND``) are combat-
  relevant -- reading a Skill Book mid-fight isn't a "cast," mirroring
  ``turn/use_mi_execution.py``'s own two branches (only its wand one
  applies here). ``tactic.sub_object`` is the item-instance id
  (``turn/search_decode.py``'s own docstring: "a magic-item id"),
  resolved through the same ``GameState.items`` registry Trade/Give's
  own item path and ``turn/use_mi_execution.py`` both already read. An
  id the leader doesn't actually own, isn't a spell wand, or is out of
  charges is a documented no-op (the plan keeps walking) -- the same
  "clear, honest reason" precedent ``execute_use_mi()`` itself already
  established for an invalid target.

  Reuses ``_resolve_cast_tactic()``'s own full 16-spell effect dispatch
  directly via a new ``forced_level`` parameter -- ``SEARCH_USE_MI_
  WAND_SKILL_LEVEL`` (2, ``TREASAB.X2``'s own "at skill-2" label on
  every wand, matching ``turn/use_mi_execution.py``'s own
  ``USE_MI_WAND_SKILL_LEVEL`` constant, duplicated rather than
  cross-imported per this project's own established "same shared fact,
  independent citation per consumer module" convention, e.g.
  ``PERSONAL_COMBAT_SPELL_CAST_CHANCE_CAP``) instead of the caster's
  real ability level, and no ``personal_combat_spell_cast_chance()``
  roll at all ([3.11]'s own "automatically successful"). A charge is
  spent only when the wand's own spell was actually eligible to be
  attempted (the new ``cast_attempt_applied`` flag, set the instant
  ``_resolve_cast_tactic()`` gets past every precondition check -- Spell
  Undead-target eligibility, Illusory Hero's own known-level gate,
  ``blocked_from_cast`` -- regardless of the spell's own
  further success/failure branches beyond that point), not on a
  rejected/ineligible target -- the same "spend only on a genuine cast"
  rule ``execute_use_mi()``'s own wand branch already follows.

- **Scout [SC], rulebook [5.8], real and distinct after all.** "When
  searching a feature, a character can use the Scout tactic to explore
  the feature looking for any special function or event... It makes no
  difference where you put the Scout tactic in your encounter plan...
  the computer will simply do your Scout tactic after all other
  encounter tactics are completed." Resolved as a genuine
  post-processing step (``_apply_scout()``, called once by
  ``execute_search()`` after the tactic-walk below settles its own
  outcome) rather than at Scout's own position in the plan -- the
  cleanest way to honor "position doesn't matter, always last" without
  threading a post-hoc hook through this function's own dozen-plus
  return sites. A dead leader can't Scout anything (not stated
  explicitly, but structurally obvious).

  **Success-chance gating -- Phase 274's own set-membership reading
  superseded by Phase 750 (`Desktop/SE+SC.md` SS7/SS9, CERTO)**: [5.8]'s
  own text ("an attempt will be made to discover" for Talk/Fulfill/
  Attacking; Steal 33%-miss; Flee 67%-miss; "some other type of
  tactical plan... told it is there, but not find out what it does" for
  everything else) turns out to be the exact same real classification
  `turn/sep_decode.py plan_intent()` already ports byte-for-byte from
  ``RUMORS.PAS Plan_Intent()`` for an unrelated purpose (the Special
  Encounter Plan Duel trigger) -- reused directly here rather than
  reimplemented. `plan_intent()` walks the tactic list in real first-
  match-wins order (not "does X appear anywhere in the plan", Phase
  274's own bug -- a `[Flee, Melee]` plan used to read as guaranteed);
  its own unconditional `CMelee` fallback means there is, in fact, no
  "genuinely unresolved" bucket in the real engine at all -- a bare
  Scout, Give-only, Beg-only (`CBeg` has no case arm at all, a silent
  no-op just like Scout), or a Cast/Use_MI-only plan with a non-exempt
  spell/item are ALL real guaranteed discoveries. Only a plan actually
  led by Flee or Steal (per `plan_intent()`'s own real semantics) stays
  probabilistic, at the named percentages above. A guardian already
  dead (`Feature.looted`, including one killed during this very
  encounter) forces a guaranteed discovery unconditionally, regardless
  of the plan's own classified intent -- checked first, in `_apply_
  scout()` below.

  **Only the discovery *level* is modeled**
  (``Feature.discovered_by_kingdom``, real since Phase 75/242): the
  guaranteed branch reaches level 3 ("fully known"); a successful
  partial branch (Steal's/Flee's own named chance) reaches level 2 ("a
  magic-power hint is known," per that field's own docstring) --
  matching "told... it is there, but not find out what it does"
  literally. Never lowers an already-higher level. **Stale as of Phase
  688 -- this used to say "no `Feature` in this project is ever
  assigned a `Power`/`PowerCondition`," confirmed with the user as a
  deliberate narrower scope.** Phases 616-623 closed that gap in full:
  every real `Feature` now resolves a real `Power`/`PowerCondition` via
  `turn/feature_power_execution.py derive_feature_event()`, called
  right below for a full discovery.

  **Two Scout orders, sourced from ``PROSE/PCOND.X2`` (user-supplied,
  project-original)**: the game's own PowerCondition-rejection prose
  confirms, for exactly 3 of ``PowerCondition``'s 6 real conditions --
  ``PayUp``, ``DrainSkill``, ``DrainCourage``, the three that cost the
  character something to use a feature's Power -- "to accept these
  terms, a character must give two Scout orders when Searching this
  feature" (quoted three times, once per condition, verbatim except for
  the specific cost named). ``SearchExecutionResult.scout_orders_given``
  records the real count (>=2 meaning "consent given"). **Stale as of
  Phase 688 -- this used to say "nothing to consume it yet."** Both
  real call sites below now pass it through as `resolve_feature_power_
  attempt()`'s own `scout_orders_given` keyword, and `turn/feature_
  power_execution.py _apply_condition_gate()` refuses a `PayUp`/
  `DrainSkill`/`DrainCourage` attempt outright below that threshold.

**Phase 289 addendum -- Words of Healing wired, completing the
Personal-Combat spell engine's own spell coverage; spell disruption's
own remaining gap re-scoped precisely.** Re-examined directly against
``turn/encounter.py``'s own docstring (which documents 16 real
Personal-Combat spell mechanics in total: the ten base spells, Charm's
own combat form, and five secret spells) after a broader gap survey
mischaracterized this project's "Personal-Combat spell engine" as
largely unbuilt. That characterization was stale: ``_resolve_cast_
tactic()`` above has dispatched 15 of those 16 spells since Phase 238,
each with its own full, sourced mechanic -- only Words of Healing
(``Spell.HEAL``, ``turn/encounter.py``'s own Phase 200 addendum) was
missing, a plain oversight (every other secret spell added since Phase
202 got its own dispatch branch the same phase its primitives landed;
Words of Healing's own primitives landed in Phase 200, before Gate
Demon/Lava Pool/Augur Combat established the "secret spell, `elif spell
is Spell.X`" pattern this function now uses, and nobody circled back).
Closed here: the new ``Spell.HEAL`` branch (self-only, no target
interaction) calls ``words_of_healing_heal()`` outright once the same
secret-spell skill-5+ eligibility gate every other secret spell already
uses (``WORDS_OF_HEALING_KNOWN_ABILITY_LEVEL = 5``, mirroring
``ILLUS_HERO_KNOWN_ABILITY_LEVEL``) is passed and the cast succeeds. A
monster caster's own healing ceiling is ``monster_starting_hit_points``
(already captured for the Phase 255 Merit Points credit, reused here
rather than re-derived); a leader caster's is the fixed
``CHARACTER_HIT_POINTS``.

**Phase 297 addendum -- a real Temper-setup double-apply bug, found in a
dedicated bug-hunt audit (the same one that found Phase 296's terrain-
line-length-cap gap).** Every place this module still calls the atomic
``resolve_melee_duel()`` (the two "fast path" branches -- the ``MELEE``
tactic's own last-tactic shortcut and the exhausted-tactic-list
fallback -- plus ``_resolve_steal()``'s own caught-at-Melee-range
branch) called it unconditionally, and ``resolve_melee_duel()`` itself
always applies Temper setup internally -- so a plan where an earlier
non-last ``MELEE`` tactic already ran real setup via round-stepping
(``melee_setup_done`` already ``True``) and then later reached one of
these atomic paths (e.g. ``[MELEE, TALK, MELEE]``, or a non-last
``MELEE`` followed by a ``STEAL`` that gets caught into Melee range)
really did double-apply -- confirmed live: a Cautious leader's own
defensive multiplier compounded 1.0 -> 0.9 -> 0.81, and a Berserk
leader's own bonus hit points could apply twice. Fixed the same way as
``turn/challenge_execution.py``'s own identical Phase 297 fix: all
three sites now pass ``skip_temper_setup=melee_setup_done`` to
``resolve_melee_duel()`` (``turn/encounter.py``'s own new parameter) --
inert whenever ``melee_setup_done`` is still ``False`` (every ordinary,
pre-Phase-297 plan shape), since that's exactly when the atomic path's
own internal setup call is still the *first* and only one.

**Phase 655 correction, kept for the record -- both halves of the
previous "What is still genuinely open" section here were themselves
stale, including this docstring's own Phase 654 edit of them.** That
edit only corrected the comparison to Challenge/Pursue's own status
(confirming their Phase 290/292 `resolve_challenge_combat()` was real)
without re-verifying the *primary* claim -- that this module's own
walk "still never rolls spell disruption" -- against this module's own
code, one screen above this note: **`_resolve_melee_range_round()`
(Phase 293, cited in full just above) already rolls real spell
disruption**, bidirectionally, every time a `CAST` tactic is reached at
`CombatRange.MELEE_RANGE` on either side (`resolve_spell_disruption()`/
`resolve_spell_disruption_from_missed_attack()`, lines documented in
that function's own docstring). Phase 293's own docstring there says so
explicitly: it "generalizes `turn/challenge_execution.py`'s own Phase
292 CAST-at-melee-range disruption design to a genuinely bidirectional
encounter" -- i.e. Search's own engine came *after*, and *builds on*,
Challenge's, not the other way around, and both have worked
independently and correctly since long before this session. There is
nothing left to reuse in either direction: Search never needed
`resolve_challenge_combat()` (which has no monster-target support at
all, confirmed above) because it already had its own, more general,
bidirectional equivalent. This whole "still genuinely open" framing --
in every version, including the Phase 654 one -- was simply never
re-checked against `_resolve_melee_range_round()`'s own arrival here.

**Phase 459 -- Add_Experience's own Druid call site.** ``AKGEN_reverse_
engineering_report (2).md`` SS3.3's own Druid row gives a fixed base
value (10) for "evento druidico qualificante" (a qualifying druidic
event); SS3.4 names the real trigger explicitly: "interazioni druidiche
con creature/mostri" (druidic interactions with creatures/monsters).
``_resolve_talk()``'s own DR gate (``can_talk_to_monster()``) is exactly
that interaction -- the leader's own Druid skill is what lets them
communicate with a feature's guardian at all -- so ``turn/experience.py
add_experience(leader, Ability.DRUID, 10, rng)`` now fires the instant
that gate passes, regardless of which reaction (Attack/Ignore/Deal)
follows. This is the only real, gameplay-consequential ``Ability.DRUID``
skill check anywhere in this project (confirmed by grep) -- every other
consumer is either a strength-penalty formula or a title-scoring
formula, not an action a leader takes.

**Phase 719 -- ``AdvancedAbility.LONG_RANGE_ARCHERY``/``SHORT_RANGE_
ARCHERY`` wired into this module's own ``CombatRange`` engine.**
``turn/challenge_execution.py``'s own Phase 700/701 addenda and ``turn/
encounter.py resolve_fire_arrow_duel()``'s own docstring both used to
flag this module's separate, duplicated ``SHOOT`` dispatch as
deliberately still untouched -- closed here. One genuine structural
difference from Challenge/Pursue's engine: this module's own
``current_range`` only ever tracks ``SPELL_RANGE`` vs. ``MELEE_RANGE``
(no intermediate ``BOW_RANGE`` step exists anywhere in this file), so
an ordinary ``SHOOT`` tactic at Spell Range already fires at full
accuracy, fully bidirectionally, with no ability needed -- Long Range
Archery's real effect here is trading that full accuracy and the
guardian's own return fire for half accuracy and a one-sided shot, via
the identical ``resolve_fire_arrow_duel(..., long_range_archer="a")``
kwarg Phase 700 already built. Short Range Archery ports directly
(a free reactive Melee swing against the archer first, then a
one-sided shot at normal accuracy), since the Melee-Range gate here
already matches Challenge's own shape exactly. Both are wired only at
the leader's own explicit ``SHOOT`` tactic -- deliberately **not**
threaded into the separate ``monster_wants_shoot`` pre-emptive-shot
branch (inside the ``Maneuver.MELEE`` tactic), since both abilities
describe how the leader personally fires when the leader's own order
calls for it, not a monster-initiated shot the leader never ordered
(and the leader's own tactic there is ``MELEE``, not ``SHOOT``, ruling
out Long Range Archery's "fire from Spell Range" framing on its own
terms). A third candidate call site, ``_resolve_steal()``'s own
caught-thief branch, was checked and confirmed genuinely inapplicable:
tracing its random ``combat_range`` roll shows its own ``resolve_fire_
arrow_duel()`` call is only ever reached at ``CombatRange.BOW_RANGE``
(``SPELL_RANGE`` returns ``None`` outright, ``MELEE_RANGE`` routes to
``resolve_melee_duel()`` instead) -- neither ability's own gating
condition can ever be true there, confirmed directly by the existing
``test_execute_search_steal_caught_bow_range_resolves_fire_arrow_duel``
test's own scripted ``choice_indices``.

**Phase 748 (``Desktop/FDISCKNGFN.md``) -- the Search order registers
its target's bare existence, unconditionally.** A real, previously
entirely unmodeled step this project didn't know it was missing: the
instant a Search order validly targets a Feature this Kingdom knows
*nothing* about (``discovery_level`` 0), the real engine records that
it exists at all (level 1) before the encounter itself even starts --
independent of every tactic, Scout included -- and, if no other Kingdom
in the world had found it either, credits the acting character's own
Chancellor merit (``MeritTally.features_discovered_first``, already
live for Explore's own discovery path since Phase 256, never for
Search until now). See ``_register_search_target_known()``'s own
docstring for the full disassembly citation.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, replace

from ak_engine.models.advanced_ability import LAVA_POOL_IMMUNE_MONSTERS, AdvancedAbility
from ak_engine.models.alignment import ALIGNMENT_ORDINAL, Alignment
from ak_engine.models.discovery import Discovery
from ak_engine.models.enums import Ability, Maneuver, Spell
from ak_engine.models.game_state import GameState, LeaderState
from ak_engine.models.magic_feature import MagicFeature
from ak_engine.models.map import HexCoord
from ak_engine.models.monster import (
    DUEL_MERIT_MONSTERS,
    HAND_OF_DEATH_ANTI_HOLY_MONSTERS,
    HAND_OF_DEATH_IMMUNE_MONSTERS,
    ICE_SUSPENSION_FLYING_MONSTERS,
    ICE_SUSPENSION_IMMUNE_MONSTERS,
    MONSTER_COMBAT_STATS,
    MONSTER_INTELLIGENCE_ORDINAL,
    MONSTER_MAGIC_ABILITIES,
    MONSTER_NAMES,
    MONSTER_RUNTIME_PROFILE,
    SPIRITWRACK_ANIMAL_INTELLIGENCE_MONSTERS,
    SPIRITWRACK_MECHANICAL_MONSTERS,
    SPIRITWRACK_UNDEAD_MONSTERS,
    SUBMARINE_MONSTERS,
    Monster,
    MonsterSpeed,
    monster_intelligence_at_least_medium,
    roll_gate_demon_type,
    roll_monster_alignment,
)
from ak_engine.models.monster_encounter_plan import roll_monster_encounter_plan
from ak_engine.models.office import Office
from ak_engine.models.power import Power
from ak_engine.models.race import HUMANOID_RACES
from ak_engine.models.temper import Temper
from ak_engine.models.valhalla import VALHALLA_VISITOR_LEADER_ID
from ak_engine.turn.cast_execution import PLACES_ABILITY_FOR_ABILITY, PLACES_FEATURE_TYPES
from ak_engine.turn.discovery_effects import (
    arcane_valor_hit_points_bonus,
    effective_skill_level,
    equipped_combat_weapon,
    holder_is_immune_to_spell,
    holds_bow_of_elven_kings,
    holds_monster_command_item_for,
)
from ak_engine.turn.encounter import (
    SUMMON_SPELLS,
    CHARACTER_HIT_POINTS,
    DAMP_MAGIC_CAST_CHANCE_MULTIPLIER,
    FIRE_ARROW_DAMAGE_RANGE,
    INFRARED_GOGGLES_HIT_CHANCE_MULTIPLIER,
    INVISIBILITY_HIT_CHANCE_MULTIPLIER,
    MIRROR_IMAGE_LEADER_INTELLIGENCE_TIER_DEFAULT,
    MIRROR_IMAGE_MONSTER_INTELLIGENCE_TIER,
    STEAL_THIEF_MASTERY_ABILITIES,
    PERSONAL_COMBAT_SPELL_ABILITY,
    PERSONAL_COMBAT_SPELL_SELF_ONLY,
    WARP_SPACE_ARCHERY_HIT_CHANCE_MULTIPLIER,
    WARP_SPACE_MELEE_HIT_CHANCE_MULTIPLIER,
    Combatant,
    CombatRange,
    EncounterCombatResult,
    FireArrowShot,
    MeleeSwing,
    MirrorImageIntelligenceTier,
    MonsterTalkReply,
    MONSTER_STEAL_GOLD_IF_NO_ITEM,
    MONSTER_TALK_REPLY_OUTCOME,
    TalkReplyOutcome,
    apply_temper_melee_setup,
    archery_free_attack_bonus,
    blocks_cast_and_archery,
    hand_of_death_cast_and_archery_block,
    bow_of_elven_kings_archery_damage_bonus,
    bow_of_elven_kings_archery_hit_multiplier,
    melee_mastery_damage_bonus,
    melee_mastery_offensive_hit_multiplier,
    weapon_melee_damage_bonus,
    weapon_offensive_hit_multiplier,
    can_talk_to_monster,
    control_undead_anti_holy_resist_chance,
    control_undead_failure_new_hit_points,
    effective_melee_skill,
    weapon_defensive_hit_multiplier,
    holy_symbol_hit_chance,
    ice_suspension_is_frozen,
    ice_suspension_slowed_bonus_rounds,
    illusory_hero_alignments_are_implacably_hostile,
    mirror_image_leader_disbelief_bonus,
    resolve_augur_combat,
    resolve_beg_for_mercy,
    resolve_fire_arrow_duel,
    resolve_fulfill_honored,
    resolve_gate_demon_refusal,
    weapon_grants_auto_invisibility,
    resolve_hand_of_death_channel,
    resolve_illusory_hero_duel,
    resolve_lava_pool_escape,
    resolve_melee_duel,
    resolve_mirror_image_duel,
    resolve_one_melee_round,
    resolve_personal_combat_spell_cast,
    resolve_reactive_melee_swing,
    resolve_spell_disruption,
    resolve_spell_disruption_from_missed_attack,
    resolve_steal_attempt,
    resolve_steal_evasion,
    resolve_steal_monster_item_transfer,
    try_consume_combat_cast_slot,
    roll_fireball_damage,
    roll_holy_symbol_undead_damage,
    roll_ice_suspension_flying_bonus_rounds,
    roll_ice_suspension_flying_crash_damage,
    roll_melee_attack,
    roll_psychic_blast_stun_rounds,
    roll_telekinetic_storm_caster_damage,
    roll_telekinetic_storm_victim_damage,
    spiritwrack_melee_damage_reduction,
    resolve_words_of_healing_disruption,
    resolve_words_of_healing_disruption_from_missed_attack,
    words_of_healing_heal,
)
from ak_engine.models.treasure import TREASURE_CATEGORY, TREASURE_WAND_SPELL, Treasure, TreasureCategory
from ak_engine.turn.command_experience import award_talk_experience
from ak_engine.turn.sickness import make_sick
from ak_engine.turn.experience import add_experience
from ak_engine.turn.feature_power_execution import (
    SA_ARGUMENT_POWERS,
    TERRAIN_SPELL_POWERS,
    TRACTABLE_POWERS,
    FeaturePowerAttemptResult,
    derive_feature_event,
    parse_sa_argument,
    resolve_feature_power_attempt,
)
from ak_engine.turn.leader_queries import find_king_of_kingdom
from ak_engine.turn.monster_raids import (
    apply_fulfill_pacification,
    guardian_undeterred,
    resolve_monster_raid_reply,
    roll_guardian_intimidation,
)
from ak_engine.turn.move_execution import credit_terrain_king_title
from ak_engine.turn.office_holder import resolve_office_holder
from ak_engine.turn.search_decode import SearchRequest, SearchTactic
from ak_engine.turn.sep_decode import plan_intent
from ak_engine.worldgen.internal_magical_locations import resolve_visible_location

# Desktop/MOSTRI con statistiche.txt footnote (*): "The Troll regenerates
# 1 hit point every combat round." See turn/encounter.py's own Phase 155
# addendum for the full quote and Combatant.regenerates_hp's own mechanics.
TROLL_REGENERATION_PER_COMBAT_ROUND = 1

# Phase 211: secret spells (ordinals 25-34) are granted once a caster
# reaches skill 5+ in their own base Ability -- `turn/cast_execution.py`'s
# own docstring and `models/advanced_ability.py
# AdvancedAbility.ILLUSORY_HERO_SPELL` confirm this for Illusory Hero
# specifically. Below this threshold, the leader simply doesn't know the
# spell yet -- casting it has no effect at all, no roll consumed.
ILLUS_HERO_KNOWN_ABILITY_LEVEL = 5

# Phase 289: same secret-spell skill-5+ gate as Illusory Hero above --
# `AdvancedAbility.WORDS_OF_HEALING_SPELL` (White Magic skill 5+),
# `turn/cast_execution.py`'s own docstring and `turn/encounter.py`'s own
# Phase 200 addendum.
WORDS_OF_HEALING_KNOWN_ABILITY_LEVEL = 5

# Phase 761: the identical secret-spell skill-5+ gate, for the 3
# remaining secret Personal-Combat spells this module dispatches --
# `models/advanced_ability.py`'s own module docstring confirms the same
# "reaching skill level 5... awards one Advanced Ability... that can be
# gained only once" mechanic applies uniformly to all 10 secret spells
# (`AdvancedAbility.GATE_DEMON_SPELL`/`LAVA_POOL_SPELL`/`AUGUR_COMBAT_
# SPELL`, `Ability.NECROMANCY`/`ELEMENTAL`/`PSYCHIC` respectively, same
# as their own `ability` resolution just above) -- Illusory Hero/Words
# of Healing were never a special case, just the first two wired.
# Checked unconditionally regardless of caster, matching Illusory Hero/
# Words of Healing's own exact shape -- see the real check's own
# comment below for why a monster caster is unaffected in practice.
GATE_DEMON_KNOWN_ABILITY_LEVEL = 5
LAVA_POOL_KNOWN_ABILITY_LEVEL = 5
AUGUR_COMBAT_KNOWN_ABILITY_LEVEL = 5

# Gate Angel's own Personal-Combat duel -- **project-original, not
# sourced from any rulebook or Pascal text** (sourced directly from the
# user, 2026-10-28, who asked for it deliberately as a design choice,
# after this project's own investigation confirmed Gate Angel's real,
# documented effect -- `AdvancedAbility.GATE_ANGEL_SPELL`'s own
# description, `models/advanced_ability.py` -- is purely a world-level
# "a Valhalla hero visits your Kingdom at the end of this turn"
# lottery, with zero combat content, unlike Gate Demon's own
# description, which explicitly describes a fight). Mirrors Gate
# Demon's own shape exactly (same `Ability.WHITE`-ladder secret-spell
# skill-5+ gate below, matching this spell's own existing Action-Cast
# gate, `turn/cast_execution.py SECRET_ACTION_SPELL_KNOWN_ABILITY_
# LEVEL`), except: the summoned combatant is whichever hero is
# currently visiting Valhalla (`models/valhalla.py
# VALHALLA_VISITOR_LEADER_ID`, the same "no hero currently visiting ->
# no effect" convention `Spell.ILLUS_HERO` above already uses) rather
# than a randomly rolled demon species, since no "angel" entity exists
# anywhere in this project's own bestiary to invent stats for; and
# there is no refusal roll, since Gate Demon's own "a Demon may refuse
# an Evil-to-Undead opponent" mechanic has no stated analog anywhere in
# Gate Angel's own rule text.
GATE_ANGEL_KNOWN_ABILITY_LEVEL = 5

# Rulebook [5.6] Flee, transcribed verbatim -- see this module's own
# docstring addendum and models/monster.py's own [5.6] quote.
FLEE_CHANCE: dict[MonsterSpeed, float] = {
    MonsterSpeed.FAST: 0.20,
    MonsterSpeed.MEDIUM: 0.50,
    MonsterSpeed.SLOW: 0.80,
}

# Rulebook [5.6] "(NOVITA') I personaggi Cauti hanno il 30% in piu' di
# possibilita' di fuggire" -- Cautious only per the literal text; extended
# to Cowardly as a confirmed project-original design choice (see module
# docstring's own Phase 286 addendum for the full reasoning).
# Phase 312: the rulebook's own closing "NUOVE REGOLE E MODIFICHE" appendix
# restates this same rule as +20% instead -- a genuine, previously-unnoticed
# internal contradiction. The user (project author), asked directly,
# confirmed +30% (the body-text figure already implemented here) is correct
# -- this value is intentionally unchanged; see the module docstring's own
# Phase 312 addendum for the full note.
WEAK_TEMPER_FLEE_CHANCE_BONUS = 0.30
WEAK_FLEE_TEMPERS = frozenset({Temper.CAUTIOUS, Temper.COWARDLY})

# turn/cast_execution.py's own docstring: Invisibility's addendum "now
# gives +30% chance to flee".
INVISIBILITY_FLEE_CHANCE_BONUS = 0.30

# Melee Evasion (Advanced Ability, Phase 515) -- quoted from
# models/advanced_ability.py ADVANCED_ABILITY_DESCRIPTION[MELEE_EVASION]:
# "A character becomes expert at evading opponents when using the Flee
# tactic and gains +30% to the chances of fleeing a combat." Same
# "additive percentage point on the base [5.6] chance" reading as the
# Weak-Temperament/Invisibility bonuses above -- the ability's own
# wording ("+30% to the chances") mirrors theirs exactly, not a distinct
# formula.
MELEE_EVASION_FLEE_CHANCE_BONUS = 0.30


def effective_flee_chance(
    base_chance: float,
    *,
    temper: Temper | None,
    is_invisible: bool,
    has_melee_evasion: bool = False,
    has_air_elemental_familiar: bool = False,
) -> float:
    """Phase 286: applies the Weak-Temperament and Invisibility flee bonuses to a base [5.6] chance.

    Both bonuses are additive percentage points, not a multiplicative
    scaling of ``base_chance`` -- see module docstring's own Phase 286
    addendum for the full sourcing and reasoning. Clamped to 1.0 (a
    probability can't exceed certainty).

    ``has_melee_evasion`` (Advanced Ability, Phase 515): a third,
    independent additive bonus -- see this module's own Phase 515
    addendum above. Stacks with the other two (nothing in any of the
    three sources excludes another), same as Invisibility already
    stacks with Weak Temperament. Defaults to ``False`` for every
    pre-Phase-515 caller.

    ``has_air_elemental_familiar`` (Office.ELE_MAGE, Phase 665, ``models/
    office.py OFFICE_TITLE_DESCRIPTION``): "Whenever < flees combat, the
    Air Elemental will form a whirlwind and whisk <2 away. Thus, all
    flee attempts are automatically successful." An unconditional
    override, not another additive bonus -- checked first and short-
    circuits the whole formula, since the real text names no partial
    case. Defaults to ``False`` for every pre-Phase-665 caller.
    """

    if has_air_elemental_familiar:
        return 1.0
    bonus = WEAK_TEMPER_FLEE_CHANCE_BONUS if temper in WEAK_FLEE_TEMPERS else 0.0
    if is_invisible:
        bonus += INVISIBILITY_FLEE_CHANCE_BONUS
    if has_melee_evasion:
        bonus += MELEE_EVASION_FLEE_CHANCE_BONUS
    return min(1.0, base_chance + bonus)


def _has_air_elemental_familiar(state: GameState, leader_id: int) -> bool:
    """Office.ELE_MAGE's own Air Elemental familiar (Phase 665) -- "<2",
    the titleholder personally, not his whole Kingdom (unlike Pagan
    King's own White-Magic perk).
    """

    holder = resolve_office_holder(state, Office.ELE_MAGE)
    return holder is not None and holder.leader_id == leader_id


# Office.NECRO_MAGE's own Imp familiar (Phase 666, `models/office.py
# OFFICE_TITLE_DESCRIPTION`): "25% magic resistance, meaning that 25% of
# the spells cast against <2 will fail."
NECROMANCER_MAGE_SPELL_RESIST_CHANCE = 0.25


def _necromancer_mage_resists_spell(state: GameState, target_leader_id: int, rng: random.Random) -> bool:
    """Same single checkpoint `holder_is_immune_to_spell()` already
    established here (post-success, pre-effect, excluding `PERSONAL_
    COMBAT_SPELL_SELF_ONLY` and a non-leader target) -- the caller
    checks the Anti-Magic Amulet first (a static, rng-free fact) and
    only calls this when it doesn't already explain the miss, so a
    non-titleholder never consumes a roll (every pre-Phase-666 caller/
    test unaffected). Duplicated in `turn/challenge_execution.py`'s own
    identical function, this project's own established "small per-
    consumer lookup" convention.
    """

    holder = resolve_office_holder(state, Office.NECRO_MAGE)
    if holder is None or holder.leader_id != target_leader_id:
        return False
    return rng.random() < NECROMANCER_MAGE_SPELL_RESIST_CHANCE


def _resolve_cast_disruption(pending_cast: SearchTactic | None, damage: int, rng: random.Random) -> bool:
    """Phase 730: rolls whether a queued ``CAST`` tactic is disrupted this
    round by damage (or a missed/dodged attack, ``damage <= 0``) --
    ``resolve_spell_disruption()``/``resolve_spell_disruption_from_
    missed_attack()`` for every spell except Words of Healing, whose own
    halved rate (``turn/encounter.py``'s Phase 200 addendum) was computed
    but never actually reached either roll (Phase 655's own correction,
    kept accurate here at last). ``pending_cast`` may be ``None`` (no
    cast queued -- never actually called in that shape by this module's
    own call sites, but kept total rather than assuming a caller always
    filters first).
    """

    is_words_of_healing = False
    if pending_cast is not None:
        try:
            is_words_of_healing = Spell(pending_cast.sub_object) is Spell.HEAL
        except ValueError:
            is_words_of_healing = False
    if is_words_of_healing:
        if damage > 0:
            return resolve_words_of_healing_disruption(damage, rng)
        return resolve_words_of_healing_disruption_from_missed_attack(rng)
    if damage > 0:
        return resolve_spell_disruption(damage, rng)
    return resolve_spell_disruption_from_missed_attack(rng)


# TREASAB.X2: every one of the 20 wands' own label reads "Cast '<Spell>' at
# skill-2" -- same real fact as turn/use_mi_execution.py's own USE_MI_WAND_
# SKILL_LEVEL, duplicated per this project's own "independent citation per
# consumer module" convention (module docstring's own Phase 274 addendum).
SEARCH_USE_MI_WAND_SKILL_LEVEL = 2

# Rulebook [5.8] Scout -- module docstring's own Phase 274 addendum has the
# full quote and reasoning behind the constants below. Phase 750 removed
# `SCOUT_GUARANTEED_MANEUVERS` (the old set-membership guess) in favor of
# `turn/sep_decode.py plan_intent()`'s own real, tested classification.
SCOUT_STEAL_ONLY_SUCCESS_CHANCE = 1.0 - 0.33  # "if you Steal and Scout, there is a 33% chance of not finding out"
SCOUT_FLEE_ONLY_SUCCESS_CHANCE = 1.0 - 0.67  # "if you Flee and Scout, this chance is 67%"
# "you may be told that the Special is there, but not find out what it
# does" -- models/feature.py's own fdisc=2 ("a magic-power hint is known").
SCOUT_PARTIAL_DISCOVERY_LEVEL = 2
SCOUT_FULL_DISCOVERY_LEVEL = 3  # "an attempt will be made to discover" -- no stated failure chance, read as guaranteed

# Phase 751 (`Desktop/SE+SC.md` SS9-11): the real engine's own 3-value
# "esito" -- see `_apply_scout()`'s own Phase 751 docstring addendum for
# the full derivation. `SCOUT_OUTCOME_PARTIAL`=1 (object only, never a
# power attempt), `SCOUT_OUTCOME_FULL`=2 (full description, `fdisc`
# reaches 3 in this same Search, power attempted unless a cost/consent
# gate refuses), `SCOUT_OUTCOME_BLIND_USE`=3 (2+ Scout orders on a
# guaranteed-intent plan: the power is attempted WITHOUT ever showing
# the full description, `fdisc` caps at `max(current, SCOUT_PARTIAL_
# DISCOVERY_LEVEL)`). Named to match this project's own "outcome ==
# SCOUT_OUTCOME_FULL" readability, not the raw 1/2/3 the source uses.
SCOUT_OUTCOME_PARTIAL = 1
SCOUT_OUTCOME_FULL = 2
SCOUT_OUTCOME_BLIND_USE = 3


def _leader_combatant(state: GameState, leader: LeaderState) -> Combatant:
    """Same construction as ``challenge_execution.py``'s own private helper (Phase 50),
    duplicated rather than shared -- see that module's own docstring for
    why (a different concept that happens to need the same small lookup).
    Search doesn't have a "Neutral Kingdom" bonus concern the way a
    character-vs-character Encounter does (the bonus is about characters
    aiding each other, [5.0]'s "Order of Duelists" -- not sourced as
    applying against monsters), so it's omitted here rather than guessed.
    """

    melee_skill = effective_skill_level(state, leader, Ability.MELEE)
    archery_skill = effective_skill_level(state, leader, Ability.ARCHERY)
    defender_office = resolve_office_holder(state, Office.DEFENDER)
    damage_reduction = 1 if defender_office is not None and defender_office.leader_id == leader.leader_id else 0
    illus_mage_office = resolve_office_holder(state, Office.ILLUS_MAGE)
    always_acts_first = illus_mage_office is not None and illus_mage_office.leader_id == leader.leader_id
    necro_mage_office = resolve_office_holder(state, Office.NECRO_MAGE)
    is_necro_mage = necro_mage_office is not None and necro_mage_office.leader_id == leader.leader_id
    has_melee_hit_points_ability = AdvancedAbility.MELEE_HIT_POINTS in leader.advanced_abilities
    effective_race = leader.race
    if effective_race is None and leader.kingdom_id is not None:
        leader_kingdom = state.kingdoms.get(leader.kingdom_id)
        effective_race = leader_kingdom.race if leader_kingdom is not None else None
    is_humanoid = effective_race in HUMANOID_RACES
    weapon = equipped_combat_weapon(state, leader.leader_id)
    holds_bow = holds_bow_of_elven_kings(state, leader.leader_id)
    return Combatant(
        name=leader.name,
        hit_points=CHARACTER_HIT_POINTS + arcane_valor_hit_points_bonus(state, leader),
        melee_skill=melee_skill,
        archery_skill=archery_skill,
        temper=leader.temper,
        damage_reduction=damage_reduction,
        has_melee_hit_points_ability=has_melee_hit_points_ability,
        offensive_hit_multiplier=(
            melee_mastery_offensive_hit_multiplier(leader.advanced_abilities) * weapon_offensive_hit_multiplier(weapon)
        ),
        melee_damage_dealt_bonus=(
            melee_mastery_damage_bonus(leader.advanced_abilities) + weapon_melee_damage_bonus(weapon)
        ),
        archery_hit_multiplier=bow_of_elven_kings_archery_hit_multiplier(holds_bow),
        missile_damage_dealt_bonus=bow_of_elven_kings_archery_damage_bonus(holds_bow),
        is_humanoid=is_humanoid,
        has_duellists_medal_ability=AdvancedAbility.MELEE_DUELLISTS_MEDAL in leader.advanced_abilities,
        has_control_temper_ability=AdvancedAbility.MELEE_CONTROL_TEMPER in leader.advanced_abilities,
        archery_free_attack_bonus=archery_free_attack_bonus(leader.advanced_abilities),
        defensive_hit_multiplier=weapon_defensive_hit_multiplier(weapon),
        is_invisible=weapon_grants_auto_invisibility(weapon),
        equipped_weapon=weapon,
        always_acts_first=always_acts_first,
        regenerates_hp=(1 if is_necro_mage else 0),
        regenerates_hp_interval=(2 if is_necro_mage else 1),
        is_undead_or_anti_holy=leader.alignment in (Alignment.UNDEAD, Alignment.ANTI_HOLY),
    )


@dataclass(slots=True)
class SearchExecutionResult:
    accepted: bool
    reason: str | None = None
    combat_resolved: bool = False
    # "leader" / "monster" / None (both survived). Phase 258: "leader" with
    # `combat_resolved=False` is now also possible -- a successful Fulfill
    # ends the Search peacefully, with no duel ever fought.
    winner: str | None = None
    feature_looted: bool = False
    leader_killed: bool = False
    fled: bool = False
    # Phase 175: per-shot Fire Arrow detail (empty unless a Shoot tactic
    # actually fired), plus the guardian's own species -- both needed by
    # report/turn_report.py's own Phase 175 addendum to dispatch each shot
    # to the right narrative renderer (species-flavored or generic).
    fire_arrow_shots: tuple[FireArrowShot, ...] = ()
    # Phase 413: per-round Hand of Death damage (empty unless a Cast
    # tactic actually channeled Hand of Death to a kill) -- see
    # `turn/encounter.py resolve_hand_of_death_channel()`'s own Phase
    # 413 addendum and `report/turn_report.py render_squeeze_attack()`.
    # Only the winning (killing) channel is captured here -- a channel
    # interrupted mid-squeeze (the caster gets hit and falls through to
    # a normal tactic) returns `None` from `_resolve_cast_tactic()`
    # without a terminal `SearchExecutionResult` to attach to, the same
    # documented limit `fire_arrow_shots` above already accepts for its
    # own inconclusive case.
    squeeze_hits: tuple[int, ...] = ()
    # Phase 415: per-swing Melee detail, chronological across every round
    # actually fought at MELEE_RANGE (round-stepped or the atomic
    # resolve_melee_duel() fast path alike) -- see `turn/encounter.py
    # MeleeSwing`'s own Phase 415 addendum for the hit-vs-damage split.
    # `_resolve_steal()`'s own combat-range fallback populates this too
    # (a self-contained atomic duel, not part of the tactic-walk's own
    # accumulator).
    melee_swings: tuple[MeleeSwing, ...] = ()
    # Phase 858: see `turn/challenge_execution.py ChallengeCombatOutcome.
    # fizzled_spells`'s own docstring -- the identical real, sourced
    # SBUNGLE.X trigger, populated by `_resolve_cast_tactic()`'s own
    # `if not succeeded:` branch below. Each entry is `("leader"/
    # "monster", spell)` -- a side label matching this dataclass's own
    # `winner` field convention, not a raw name (unlike the challenge_
    # execution.py sibling field, which has no equivalent "leader"/
    # "monster" concept to borrow).
    fizzled_spells: tuple[tuple[str, Spell], ...] = ()
    # 2026-11-21: every Hand of Death cast that engaged but did NOT end the
    # fight, one ``(caster side "leader"/"monster", squeeze hits dealt
    # before the end, interrupting damage)`` entry each -- the victim's own
    # counter-hit broke the channel ("l'incantesimo svanisce"). An
    # ``interrupting damage`` of ``None`` means the spell never engaged
    # because the target is immune. Previously both left no trace in the
    # report at all, so a real, slot-consuming cast looked like it had
    # never been attempted (the squeeze damage already dealt was silent
    # too). A winning channel is still reported via ``squeeze_hits``.
    hand_of_death_aborts: tuple[tuple[str, tuple[int, ...], int | None], ...] = ()
    guardian_monster: Monster | None = None
    # Phase 213: the originating request, so a caller (report/turn_report.py
    # describe_turn_results()) can resolve the searched feature's own id.
    # Set by plan_dispatch.py's own dispatcher, not by execute_search()
    # itself -- same convention/reasoning as PursueExecutionResult.request's
    # own Phase 213 note.
    request: SearchRequest | None = None
    # Phase 274: how many Scout tactics the plan actually listed -- set by
    # `_apply_scout()` regardless of whether Scout itself found anything.
    # >=2 is PCOND.X2's own confirmed "consent given" signal for a
    # PayUp/DrainSkill/DrainCourage Power condition -- wired into that
    # real gate since Phase 688, see `_apply_scout()`'s own docstring.
    scout_orders_given: int = 0
    # Phase 748 (Desktop/FDISCKNGFN.md): whether this Search order just
    # registered the target Feature's bare existence for the first time
    # (``discovered_by_kingdom`` 0 -> 1) -- see ``_register_search_
    # target_known()``'s own docstring. ``False`` when the Feature was
    # already known at any level, or when this Kingdom already had an
    # entry (however low).
    target_newly_registered: bool = False
    # Phase 544: a Talk tactic's own Druid DR gate failed against a
    # guardian too unintelligent to be silently ignored (``mintel <
    # Medium`` -- see ``_apply_talk_language_failure()``'s own Phase 544
    # docstring for the full citation).
    talk_language_failure: bool = False
    # 2026-11-20, user-confirmed (live AK0 playtest -- a hero sent to
    # Talk to a black and a red dragon produced no report trace at
    # all): the two distinct ways a Talk attempt observably goes
    # nowhere, from the player's own perspective -- ``_LIgnore`` (the DR
    # gate failed, but the guardian is smart enough to just ignore the
    # attempt rather than look puzzled) and the real 24-reply table's
    # own ``TalkReplyOutcome.IGNORE`` category (the DR gate *passed*,
    # the hero and guardian understood each other fine, but the
    # guardian's own rolled reply was simply to ignore it). Both were
    # previously silent by design ("matches this project's own IGNORE
    # convention" -- see ``_apply_talk_language_failure()``'s own
    # updated docstring); user's own explicit choice, asked directly:
    # project-original text for both, same as every other such gap this
    # session. Collapsed into one field rather than two: neither case
    # has (or ever had) its own distinguishable sourced text, and the
    # player-facing effect is identical either way -- nothing happened,
    # the guardian paid no attention.
    talk_ignored: bool = False
    # 2026-11-20 bug fix, user-confirmed via a deep audit:
    # ``Office.PSYCHIC_MAGE``'s own "senses whether the monster intends
    # to keep its end of the bargain" perk -- set only when ``_resolve_
    # talk()``'s own QUEST_OR_AGREEMENT branch struck a new deal *and*
    # the caster held the office at that moment (``None`` otherwise,
    # including every Talk that doesn't result in a deal at all). See
    # ``models/feature.py Feature.psychic_mage_sensed_fulfill_honor``'s
    # own docstring for why this is a real, single advance roll, not a
    # second, independent one that could disagree with Fulfill's own.
    sensed_fulfill_honor: bool | None = None
    # Phase 616: the Feature->Power [5.8] outcome from a full ("fully
    # known", level 3) Scout discovery, when the Feature's own derived
    # power is one of this phase's 9 `TRACTABLE_POWERS`. `None` covers
    # "no Scout discovery this Search", "the Feature has no power at
    # all" (`Power.PNONE`), and "the power exists but isn't wired yet"
    # (e.g. the 5 Oracles, Cast Spell -- a later phase's own scope)
    # alike -- see `_apply_scout()`'s own Phase 616 addendum below.
    feature_power_outcome: FeaturePowerAttemptResult | None = None
    # Phase 672: whether this encounter actually pacified the guardian --
    # see `turn/monster_raids.py apply_fulfill_pacification()`/`guardian_
    # intimidated_by_combat_damage()`'s own docstrings for the two
    # distinct mechanisms. Both default `False` for every pre-Phase-671
    # caller/test.
    guardian_pacified_by_fulfill: bool = False
    guardian_intimidated: bool = False
    # Phase 673 (Desktop/BOLD OK.txt): the real "_MUnDt" outcome -- the
    # guardian took damage this encounter but no intimidation packet
    # ever succeeded, and it's still Bold. No state change.
    guardian_undeterred: bool = False
    # Phase 790 (MAGFEAT.X2, Phase 96): the real magic-feature-discovery
    # sentence's own trigger -- the exact `current_level <
    # SCOUT_PARTIAL_DISCOVERY_LEVEL` crossing already used above to
    # credit a terrain-King title (Phase 749/751), the moment a
    # Kingdom's own `fdisc` first reaches 2. `resolve_visible_location()`
    # gives the real, deterministic `MagicFeature` to narrate --
    # `MagicFeature.NONE` is itself a real, meaningful value ("saw
    # nothing special"); the outer `None` default means "no crossing
    # occurred this call," independent of whether a province is
    # registered (unlike the terrain-King credit, which still needs
    # one). See `report/turn_report.py render_magic_feature_discovery()`.
    magic_feature_discovered: MagicFeature | None = None
    # Phase 855 (SAY.PAS _LShIce, module docstring's own Phase 123
    # addendum): Ice Suspend's own "fully frozen" branch (`turn/
    # encounter.py ice_suspension_is_frozen()`) already ends the
    # encounter as an immediate win ("Confirmed by the user: the frozen
    # branch simplifies to a win," that module's own Phase 189 addendum)
    # -- but nothing ever narrated *why*. This flags exactly that one
    # real, reachable branch so `report/turn_report.py describe_search()`
    # can render the real `_LShIce` sentence. The sibling "slowed"/
    # "flying crash"/"ghost immune" branches stay unflagged here on
    # purpose: unlike this one, none of them terminates the encounter at
    # the same call site, so capturing them would need a nonlocal
    # accumulator threaded through every one of this function's several
    # other exit points (Flee/Beg/Talk success, the exhausted-tactics
    # fallback, ...) -- a real, separate, larger follow-up, not attempted
    # here.
    ice_suspend_immobilized: bool = False
    # Phase 1027: which of the 7 real `report/turn_report.py
    # QUEST_RIDDLE_TEXT` entries this guardian poses, set only when a
    # Talk's own resolved reply is `MonsterTalkReply.R_RIDDLE` -- see
    # `_select_guardian_riddle()`'s own docstring for why this is a
    # project-original, explicitly-unsourced stand-in (the real
    # selector byte, `Get_Reply`'s own `rep2`, is never read by any
    # caller this project has disassembly access to) rather than a
    # ported algorithm, unlike every other field on this dataclass.
    # `None` for every other reply, including the other 19 `QUEST_OR_
    # AGREEMENT` replies -- this project still doesn't narrate those,
    # only Riddle's own already-transcribed prose is wired here.
    guardian_riddle: Treasure | None = None
    # Phase 1028: the direct sibling of `guardian_riddle` above, for
    # `MonsterTalkReply.R_VISIT` and the 5 real `report/turn_report.py
    # QUEST_VISIT_TEXT` entries -- see `_select_guardian_quest_
    # location()`'s own docstring. `None` for every other reply,
    # including Riddle's own and the other 18 `QUEST_OR_AGREEMENT`
    # replies this project still doesn't narrate.
    guardian_quest_location: Treasure | None = None
    # 2026-11-21, user-reported (a hero Talked to a Titan and the report had
    # no trace of what the Titan said or that it offered a quest): the
    # guardian's own MTALK.X2 reply for any deal/quest outcome, plus the
    # facts its offer text names (the feature's treasure and province), so
    # `report/turn_report.py describe_search()` can narrate the offer.
    guardian_talk_reply: MonsterTalkReply | None = None
    guardian_talk_treasure: Treasure | None = None
    guardian_talk_coord: HexCoord | None = None


def execute_search(
    state: GameState,
    leader_id: int,
    request: SearchRequest,
    rng: random.Random | None = None,
) -> SearchExecutionResult:
    """Resolve a Search order end-to-end, then apply Scout as a final
    post-processing step (Phase 274) -- see `_apply_scout()`'s own
    docstring for why Scout can't simply resolve inline at its own
    position in the tactic walk like every other tactic below.

    **Phase 302 (Discovery.ANALYTICAL_PSYCHOLOGY)**: a leader currently
    under a protected Charm (``LeaderState.analytical_psychology_revert_
    kingdom_id`` set -- see ``turn/cast_execution.py _execute_charm()``'s
    own Phase 302 addendum) never Searches for the rest of the turn the
    Discovery text promises, rejected here before any real encounter
    resolution runs.
    """

    rng = rng if rng is not None else random.Random()
    leader = state.leaders.get(leader_id)
    if leader is not None and leader.analytical_psychology_revert_kingdom_id is not None:
        return SearchExecutionResult(
            accepted=False, reason="protected by Analytical Psychology -- a charmed character never Searches"
        )
    result = _resolve_search_encounter(state, leader_id, request, rng)
    if result.accepted:
        _register_search_target_known(state, leader, request, result)
        if leader is not None:
            # Phase 686: AKGEN_reverse_engineering_report (2).md SS3.3's
            # own Melee/Archery rows -- "evento di mischia/duello
            # qualificante"/"evento di tiro riuscito" -- a landed hit,
            # credited once per encounter, independent of who wins.
            if any(s.hit for s in result.melee_swings if s.attacker == "a"):
                add_experience(leader, Ability.MELEE, 10, rng)
            if any(s.hit for s in result.fire_arrow_shots if s.shooter == "a"):
                add_experience(leader, Ability.ARCHERY, 10, rng)
        _apply_scout(state, leader_id, request, result, rng)
        _apply_talk_language_failure(state, leader, request, result)
    return result


def _apply_talk_language_failure(
    state: GameState,
    leader: LeaderState | None,
    request: SearchRequest,
    result: SearchExecutionResult,
) -> None:
    """Phase 544 -- ``AKGEN_reverse_engineering_report (3).md`` SS60-62
    (``resolve_TA_to_monster()``'s own DR-gate-failure branch, SS62.1
    "Fallimento linguistico", quoted in full):

    "Il requisito talkdiff non e' una probabilita'. E' una soglia
    deterministica sul livello effettivo M_Skill(hero,Druid). Se la
    soglia non e' raggiunta, il ramo... usa l'intelligenza del mostro
    per scegliere la narrazione «ignora» oppure RPuzzled; non assegna
    una Quest. Un eventuale attacco successivo nasce dalla tattica di
    riserva o dalla prosecuzione dell'incontro, non da un tiro Quest
    nascosto."

    ``_resolve_talk()`` (this module's own real Talk resolver, Phase
    240/528) already applies the DR gate and returns ``None`` either
    way when it fails -- the walk always continues to the next tactic,
    exactly like the dossier's own ``continue_with_next_tactic()``. What
    was missing (the gap this phase closes) is the *narrative*
    distinction the dossier's own pseudocode draws between the two
    ways that failure can go: ``_LIgnore`` (silent, ``mintel >=
    Medium``) or ``_MReply``/``RPuzzled`` (``mintel < Medium``).

    Both the DR gate and the mintel check are pure/deterministic (no
    RNG involved), so this can be re-evaluated once, after the whole
    tactic walk finishes, without risk of diverging from what
    ``_resolve_talk()`` itself computed inline -- the same "evaluate
    once, after the walk, off the plan's own tactic list" shape
    ``_apply_scout()``'s own Phase 274 docstring already established
    for this module (Scout "makes no difference where you put it...
    the computer will simply do your Scout tactic after all other
    encounter tactics are completed").

    ``_LIgnore`` (``mintel >= Medium``) sets ``result.talk_ignored``;
    the ``mintel < Medium`` "puzzled" branch sets ``result.talk_
    language_failure`` instead -- ``MTALK.X2``'s own literal reply text
    is unsourced everywhere in this project (see ``report/turn_
    report.py``'s own docstring), so both stay bare booleans rather
    than fabricated prose; any report-layer text for either is a
    project-original placeholder, the same "mechanic sourced, text is
    not" split Phase 543's own Arcane's Valor unification line already
    established.

    **2026-11-20 addendum**: also re-derives the real 24-reply table's
    own outcome for a DR-gate-*passed* Talk, off ``Feature.guardian_
    talk_reply_id`` -- the exact same real value ``_resolve_talk()``
    itself (this module's own, Phase 240/528/727) already generated or
    reused earlier in this very call's own tactic walk, so this is a
    free re-read, not a second roll. Sets ``result.talk_ignored`` when
    that reply's own ``TalkReplyOutcome`` category is ``IGNORE`` --
    the real guardian understood the hero fine, just didn't react. Any
    other category (``ATTACK``, suppressed or not, and every real
    ``QUEST_OR_AGREEMENT`` reply) already produced its own real,
    distinguishable outcome earlier in the same walk (forced combat, or
    ``_resolve_talk()``'s own early, non-``None`` return respectively),
    so this addendum only ever adds a new, previously-silent fact --
    never contradicts or duplicates one already recorded.

    **Bug fix**: ``leader`` used to be re-derived here via ``state.
    leaders.get(leader_id)`` instead of being passed in as the caller's
    own pre-encounter object -- the exact same King-succession hazard
    ``_register_search_target_known()``'s own docstring already warns
    about. If the searching King dies in an earlier tactic before this
    plan's TALK tactic is ever reached, ``GameState.remove_leader()``
    has already installed a brand-new Royal Heir under the same
    ``leader_id`` with baseline skills (Druid included, at 0) -- the DR
    gate above was then being evaluated against the Heir's skill, not
    the dead King's, fabricating a "puzzled" failure narrative for a
    Talk that was never actually attempted.
    """

    feature = state.features.get(request.feature_id)
    if feature is None or feature.guardian_monster is None:
        return
    if not any(tactic.maneuver is Maneuver.TALK for tactic in request.tactics):
        return
    if leader is None:
        return
    if holds_monster_command_item_for(state, leader.leader_id, feature.guardian_monster):
        return  # Phase 537 carve-out -- Talk's own social roll never runs at all
    druid_level = effective_skill_level(state, leader, Ability.DRUID)
    if not can_talk_to_monster(feature.guardian_monster, druid_level):
        if monster_intelligence_at_least_medium(feature.guardian_monster):
            result.talk_ignored = True  # _LIgnore
        else:
            result.talk_language_failure = True  # RPuzzled
        return

    # The DR gate passed -- re-derive the real reply-table outcome from
    # the same persisted value _resolve_talk() itself already set this
    # same call (see this function's own 2026-11-20 addendum above).
    # None means Talk never actually reached the reply roll this call --
    # nothing to re-derive.
    if feature.guardian_talk_reply_id is None:
        return
    reply = MonsterTalkReply(feature.guardian_talk_reply_id)
    if MONSTER_TALK_REPLY_OUTCOME[reply] is TalkReplyOutcome.IGNORE:
        result.talk_ignored = True


def _register_search_target_known(
    state: GameState,
    leader: LeaderState | None,
    request: SearchRequest,
    result: SearchExecutionResult,
) -> None:
    """``Reveal_Feature`` (a descriptive label -- no symbol survives),
    the compiled ``AK.EXE`` helper the real ``Search`` resolver calls
    whenever its target Feature is still completely unknown to the
    searching character's own Kingdom -- ``Desktop/FDISCKNGFN.md``
    (user-supplied disassembly, 2026-09-05, CERTO throughout), a
    byte-exact trace of raw offsets ``0xDACC``-``0xDBA4`` (the ``Search``
    resolver itself) and ``0x249EC``-``0x24B78`` (the shared helper).

    **What the disassembly proves, verbatim**: once the resolver's own
    coordinate check passes (the character really is co-located with
    the Feature -- ``execute_search()``'s own ``result.accepted``,
    below), it reads ``fdisc^[LKing(ldr),fn]``; if that cell is still
    exactly ``0``, it calls the shared helper, which does two things
    *unconditionally*, independent of any Encounter Plan tactic
    (Scout included) and *before* the encounter itself even starts:

    1. ``fdisc^[kng,fn] := 1`` -- the Feature's bare existence becomes
       known ("luogo noto; colonna Special ancora '?'", ``models/
       feature.py``'s own already-documented level 1). A single literal
       ``mov byte ptr es:[di],01h`` (raw ``0x24B4D``) -- never a `2`/`3`,
       and never reached at all when the cell is already nonzero (the
       gate itself prevents ever *downgrading* a higher level).
    2. **Chancellor's "+2 per first-in-the-world discovery" merit**
       (``lfdisc[ldr]``, already modeled as ``MeritTally.features_
       discovered_first`` since Phase 256 -- but, until this phase,
       only ever credited from ``turn/plan_dispatch.py``'s own EXPLORE
       branch): the helper scans every Kingdom's own row for this same
       Feature, and increments the *acting character's own* (not the
       Kingdom's) tally only when none of them already had a positive
       entry -- i.e. this Search is genuinely the first anyone, anywhere,
       has ever found this Feature. Exactly the same "no other row is
       positive yet" check ``plan_dispatch.py``'s own Explore-side
       credit already performs via ``len(feature.discovered_by_kingdom)
       == 1`` right after the write -- reused verbatim here, not a new
       formula.

    A kingdomless (independent Hero) leader is skipped, same reasoning
    ``_apply_scout()``'s own docstring already gives for the identical
    situation: discovery is tracked per ``kingdom_id``, and there's
    nowhere to record it for one. Scoped to whatever ``execute_search()``
    already accepts as a valid target (Phase 132's own pre-existing
    "must have a recorded guardian" boundary included) -- a genuinely
    guardian-less Feature never reaches this function at all today, a
    separate, pre-existing limit this phase doesn't touch.

    Deliberately **not** gated on ``result.leader_killed``, unlike
    ``_apply_scout()`` -- the disassembly places this registration
    *before* ``Start_Encounter`` runs, so a character who dies fighting
    the guardian moments later has already, unconditionally, made the
    Feature's existence known. This is also *why* the caller passes the
    already-resolved ``leader`` object (captured at the top of
    ``execute_search()``, before the encounter runs) rather than a bare
    ``leader_id`` for this function to look up itself: a leader who dies
    during the encounter is already gone from ``state.leaders`` (and, for
    a King, immediately succeeded by a Royal Heir under the same id) by
    the time this runs -- the object captured earlier is still the real
    searcher, with the real ``kingdom_id``/``merit_tally`` to credit.
    """

    feature = state.features.get(request.feature_id)
    if leader is None or feature is None or leader.kingdom_id is None:
        return
    if feature.discovery_level(leader.kingdom_id) != 0:
        return
    feature.discovered_by_kingdom[leader.kingdom_id] = 1
    result.target_newly_registered = True
    if len(feature.discovered_by_kingdom) == 1:
        leader.merit_tally.features_discovered_first += 1


def _apply_scout(
    state: GameState,
    leader_id: int,
    request: SearchRequest,
    result: SearchExecutionResult,
    rng: random.Random,
) -> None:
    """Scout [SC], rulebook [5.8] -- Phase 274, quoted in full:

    "When searching a feature, a character can use the 'Scout' tactic to
    explore the feature looking for any special function or event...
    It makes no difference where you put the Scout tactic in your
    encounter plan. The Scout tactic has no effect on the success of
    your other tactics, and the computer will simply do your Scout
    tactic after all other encounter tactics are completed. When the
    Scout tactic is part of an encounter plan which calls for Talking,
    Fulfilling or Attacking... an attempt will be made to discover any
    special function or event... If you use some other type of tactical
    plan, you may be told that the Special is there, but not find out
    what it does. For example, if you Steal and Scout, there is a 33%
    chance of not finding out. If you Flee and Scout, this chance is
    67%."

    **Stale as of Phase 616 -- frozen from Phase 274, corrected here.**
    This paragraph used to say the project had no "special function or
    event" system at all to trigger, and that the Feature->Power link
    (``models/power.py``/``models/magic_feature.py``) was never wired
    anywhere. That link has been fully live since Phases 616-623 --
    ``Feature.magic_power``, resolved via ``turn/feature_power_
    execution.py resolve_feature_power_attempt()``, called directly a
    few dozen lines below in this very function (see the Phase 616
    addendum there). Only the ~55% of real Features with no power at
    all (``Power.PNONE``) and [5.8]'s own generic "beneficial/
    detrimental Special" narrative *flavor* (as opposed to the real,
    already-modeled mechanical effect) stay unmodeled. The one real,
    already-modeled effect Scout can drive is [5.8]'s own "gain
    information on what treasure is in the feature," i.e. a
    discovery-level bump on ``Feature.discovered_by_kingdom`` (Phase 75)
    from a partial "a magic-power hint is known" (2) to a full "fully
    known" (3) reveal -- the exact two non-zero, non-"riches unknown"
    levels that array's own docstring documents. Runs unconditionally
    last (per the quote above), independent of every other tactic's own
    return-early control flow -- which is exactly why this can't be just
    another branch inside the main tactic walk above, and needs its own
    post-processing pass in ``execute_search()`` instead.

    **The success/failure split -- Phase 750 (``Desktop/SE+SC.md`` SS7/
    SS9, CERTO)**: superseded Phase 274's own set-membership guess
    (which combos count as "guaranteed") with a direct reuse of ``turn/
    sep_decode.py plan_intent()`` -- the exact real ``RUMORS.PAS Plan_
    Intent()`` function, already ported and tested for the Special
    Encounter Plan's own Duel-trigger classification, and provably the
    *same* real function Scout's own outcome dispatch consults (SS9.3-
    9.4's own worked branches match this function's own real cases
    exactly: ``Maneuver.FLEE`` -> the documented 33%, ``Maneuver.STEAL``
    -> the documented 67%, everything else -- ``Maneuver.TALK``/
    ``MELEE``, and critically also the function's own unconditional
    ``CMelee`` fallback -- guaranteed, no roll). ``plan_intent()`` walks
    the tactic list in real first-match-wins order (not "does X appear
    anywhere", Phase 274's own bug: a plan like ``[Flee, Melee]`` used
    to read as guaranteed via the old set-membership check, when the
    real engine resolves Flee first and never even reaches Melee),
    correctly folds ``Give``/a terminal-only ``Say`` into the same
    guaranteed bucket as Talk/Fulfill (Phase 274 missed ``Give``
    entirely), and -- since its own final fallback is unconditionally
    ``CMelee`` -- means a Cast-only (non-exempt spell), Use_MI-only
    (non-exempt wand), Beg-only, or even a bare Scout-only plan are ALL
    real guaranteed discoveries in the true engine, not "genuinely
    unresolved" as this project claimed from Phase 274 through Phase
    749. There is, in fact, no "genuinely unresolved, no effect" bucket
    at all in the real engine -- every Search with a real Scout tactic
    resolves to either a probabilistic (Flee/Steal-led) or a guaranteed
    discovery.

    One further real wrinkle, also directly from SS9.2: a guardian
    already dead (``Feature.looted`` -- ``fstate[fn]=Dead``, including
    a guardian killed *during this same encounter*, since ``_apply_
    scout()`` always runs after combat resolution) forces a guaranteed
    discovery unconditionally, regardless of what the plan's own real
    ``plan_intent()`` would otherwise resolve to (even a genuinely
    Flee-led plan against an already-dead guardian is guaranteed) --
    checked first, before consulting the plan's own intent at all.

    **Phase 751 -- the real 3-outcome model (SS9-11, CERTO) and the
    access-denied clamp (SS9.5, RICOSTRUITO byte-observable, user-
    confirmed interpretation)**. The real engine computes a numeric
    ``esito`` (1, 2, or 3), not a bare discovered/not boolean:

    - **esito 1** (a probabilistic *miss*, Flee/Steal-intent only, or a
      forced clamp -- see below): the object alone becomes known
      (``fdisc`` -> max 2), no power ever attempted.
    - **esito 2** (a probabilistic *hit*, OR any guaranteed-intent plan
      with exactly one Scout tactic): the FULL description is shown and
      ``fdisc`` reaches 3 *in the same Search* -- even starting fresh
      from level 1, both the 1->2 and 2->3 promotions fire (SS25's own
      "esito 2 partendo da fdisc=1 può eseguire entrambe le promozioni
      ... e assegnare due punti" -- both real terrain-title credits
      apply here, not just one).
    - **esito 3** (a guaranteed-intent plan with 2+ Scout tactics, "an
      authentic blind acceptance"): the power is used WITHOUT ever
      showing the full description -- ``fdisc`` caps at ``max(current,
      2)``, never reaching 3 this way (SS10.4/25: "promuove soltanto a
      2 e assegna un punto, poi usa il potere senza promuovere a 3").
      Only the FIRST terrain-title credit applies here.

    **The access-denied clamp** (SS9.5): "if the guardian survived and
    no real access was granted, `outcome := Min(1, outcome)`" -- the
    real Pascal condition this reads (a single boolean byte in the
    encounter frame) has no surviving name or exact trigger formula
    (SS21: "il nome Pascal originale resta ignoto"). **User-confirmed
    interpretation, not derived from source, resolved in two passes**:
    the first draft read "access" as *only* a combat win or a
    successful Talk/Fulfill deal -- but that directly contradicted the
    plain rulebook text this whole mechanic is built on ([5.8]: "if you
    Steal and Scout, there is a 33% chance of not finding out," which
    only makes sense if a plain, uncaught Steal -- no combat, no deal --
    already grants the *other* 67% a real reveal). **Final, corrected
    reading**: for a Flee- or Steal-classified intent, the clamp doesn't
    apply separately at all -- the tactic's own probabilistic roll
    above (33%/67%) already *is* the access check, one shared roll for
    both questions. The clamp only ever reduces the *guaranteed*-intent
    branch (``Maneuver.TALK``/``MELEE`` per ``plan_intent()``, including
    its own unconditional fallback): there, "access" means the
    character actually won outright -- a combat victory, or a
    successful Talk/Fulfill deal, both of which ``SearchExecutionResult.
    winner == "leader"`` already captures uniformly (Phase 258). A
    Talk-only/Give-only/Beg-only/bare-Scout-only plan that never
    actually wins anything (nothing to fight, nothing granted) now
    correctly clamps to the partial level, not a guaranteed full reveal
    -- a real, intuitive tightening: examining a feature you never
    genuinely engaged only gets you a partial glimpse. A guardian
    already ``looted`` bypasses this clamp entirely regardless of
    intent (SS9.5's own ``fstate[fn]<>Dead`` guard, matching the
    guardian-dead override above).

    A dead leader can't scout anything afterward -- skipped outright
    when ``result.leader_killed``. Also skipped for a kingdomless
    (independent Hero) leader: discovery is tracked per-``kingdom_id``
    (``Feature.discovered_by_kingdom``), so there's nowhere to record it.

    ``result.scout_orders_given`` is set to how many Scout tactics the
    plan actually listed (real Search phases only ever carry one, per
    ``search_decode.py``'s own docstring, but nothing prevents encoding
    more) regardless of whether this function finds anything -- PCOND.
    X2's own confirmed reading is that *two* Scout orders on the same
    feature is this game's explicit consent mechanism for a Power
    condition ("PayUp"/"DrainSkill"/"DrainCourage"). **Stale as of Phase
    688**: this paragraph used to say this project had no Feature->Power
    wiring to actually apply that consent yet -- the Feature->Power
    system itself has existed since Phase 616-623, and Phase 688 wired
    this exact count straight into it: the call below passes
    ``scout_orders_given=scout_count`` into
    ``resolve_feature_power_attempt()``, which refuses PayUp/DrainSkill/
    DrainCourage outright below two Scout orders (see
    ``turn/feature_power_execution.py _apply_condition_gate()``).
    """

    scout_count = sum(1 for tactic in request.tactics if tactic.maneuver is Maneuver.SCOUT)
    result.scout_orders_given = scout_count
    if scout_count == 0 or result.leader_killed:
        return

    leader = state.leaders.get(leader_id)
    feature = state.features.get(request.feature_id)
    if leader is None or feature is None or leader.kingdom_id is None:
        return

    if feature.looted:
        # SS9.2: a guardian already dead (including one killed during
        # this very encounter, resolved before this function ever runs)
        # bypasses both the intent classification AND the access-denied
        # clamp below -- only `scout_count` still decides esito 2 vs 3.
        outcome = SCOUT_OUTCOME_BLIND_USE if scout_count >= 2 else SCOUT_OUTCOME_FULL
    else:
        intent = plan_intent(request.tactics, state)
        if intent is Maneuver.FLEE:
            # The Flee-led roll IS the access check here -- no separate
            # clamp (see docstring: this is the corrected reading, not
            # the first draft's blanket combat/Talk-only interpretation).
            outcome = SCOUT_OUTCOME_FULL if rng.random() < SCOUT_FLEE_ONLY_SUCCESS_CHANCE else SCOUT_OUTCOME_PARTIAL
        elif intent is Maneuver.STEAL:
            outcome = SCOUT_OUTCOME_FULL if rng.random() < SCOUT_STEAL_ONLY_SUCCESS_CHANCE else SCOUT_OUTCOME_PARTIAL
        elif result.winner == "leader":
            outcome = SCOUT_OUTCOME_BLIND_USE if scout_count >= 2 else SCOUT_OUTCOME_FULL
        else:
            # SS9.5: guaranteed-intent plan that never actually won
            # anything (no fight to win, no deal struck) -- Min(1, outcome).
            outcome = SCOUT_OUTCOME_PARTIAL

    current_level = feature.discovery_level(leader.kingdom_id)
    if outcome == SCOUT_OUTCOME_FULL:
        new_level = SCOUT_FULL_DISCOVERY_LEVEL
    else:  # SCOUT_OUTCOME_PARTIAL or SCOUT_OUTCOME_BLIND_USE both cap at the partial level
        new_level = max(current_level, SCOUT_PARTIAL_DISCOVERY_LEVEL)
    feature.discovered_by_kingdom[leader.kingdom_id] = new_level
    discovered = outcome != SCOUT_OUTCOME_PARTIAL

    # Phase 749 (`Desktop/SE+SC.md` SS25/12.1, CERTO): the same two
    # routines that promote `fdisc` in the real engine (`0x114FF` for
    # 1->2, `0x11371` for 2->3) also each credit +1 to the feature's own
    # province terrain-King royal title (`turn/move_execution.py
    # credit_terrain_king_title()`) -- a second, independent trigger for
    # the exact counters Explore already credits (Phase 630). The first
    # credit is unconditional (matches `0x114FF`'s own unconditional
    # `PNone` short-circuit, and still fires on a partial-outcome
    # attempt, since `new_level` is already >= 2 either way). The second
    # (Phase 751) is gated on `outcome == SCOUT_OUTCOME_FULL` specifically
    # -- the real `0x11371` promotion only ever runs for esito 2, never
    # for esito 3's own "blind use" (`SCOUT_OUTCOME_BLIND_USE`, which
    # routes through `0x12AB0` instead, confirmed not an `Inc_Tit`-
    # calling routine) -- plus a real `Power` existing (`event.power is
    # not Power.PNONE`): the real `0x11371` promotion is never reached
    # at all for a `PNone` Feature, so crediting it there would be a
    # real overcount. Both credits need a real registered province to
    # read a terrain from -- `None` (no data) means no credit, not a
    # guess.
    province = state.provinces.get(feature.coord)
    if current_level < SCOUT_PARTIAL_DISCOVERY_LEVEL:
        result.magic_feature_discovered = resolve_visible_location(feature.kind, feature.feature_id, feature.coord.x)
        if province is not None:
            credit_terrain_king_title(leader, province.effective_terrain())

    # Phase 616: a full discovery is real "special function or event"
    # knowledge per the rulebook quote above -- resolve and apply the
    # Feature->Power outcome now. Every real `Power` is tractable as of
    # Phase 623 (`MAP_PROV`, the last one, closed then) -- only
    # `Power.PNONE` (no power at all, the ~55% of real Features with
    # none) reaches `derive_feature_event()` with nothing to resolve.
    if discovered:
        event = derive_feature_event(feature, state=state)
        if province is not None and outcome == SCOUT_OUTCOME_FULL and current_level < SCOUT_FULL_DISCOVERY_LEVEL and event.power is not Power.PNONE:
            credit_terrain_king_title(leader, province.effective_terrain())
        if event.power in TRACTABLE_POWERS or event.power in TERRAIN_SPELL_POWERS or event.power is Power.CHANCE:
            # Phase 620/621: CAST_SPELL/ANS_PRAYER land here too --
            # tractable whenever `event.spell_parameter` resolved (all
            # 13 real `Set_Spell` candidates as of Phase 621, not just
            # Part_Sea/Flood/Earthquake); `resolve_feature_power_
            # attempt()` itself refuses cleanly ("power not yet wired")
            # on the one remaining honest gap -- an unknown province
            # (`state.provinces` has no entry for the Feature's coord).
            # Phase 622: CHANCE always resolves once `state` is given
            # (`GameState.gdday` always has a real value, even if a
            # placeholder default), so it needs no such fallback.
            result.feature_power_outcome = resolve_feature_power_attempt(
                state, leader_id, feature, event, rng, scout_orders_given=scout_count
            )
            result.feature_power_outcome = replace(result.feature_power_outcome, feature_id=feature.feature_id)
        elif event.power in SA_ARGUMENT_POWERS:
            # Phase 619: the 5 Oracles/Recharge/Grant Wish/Gamble need
            # the Encounter Plan's own SAY tactic argument -- "just
            # SA-y the ... number" (Special Features.md sections
            # 5.4-5.7). The *first* SAY tactic in the plan (real Search
            # phases only ever carry one, same convention `scout_
            # orders_given`'s own docstring already established for
            # Scout); `None` when no SAY tactic was given at all, which
            # `resolve_feature_power_attempt()` refuses cleanly on its
            # own ("no SA argument given").
            say_tactic = next((t for t in request.tactics if t.maneuver is Maneuver.SAY), None)
            sa_argument = parse_sa_argument(say_tactic.say_text) if say_tactic is not None and say_tactic.say_text else None
            result.feature_power_outcome = resolve_feature_power_attempt(
                state, leader_id, feature, event, rng, sa_argument=sa_argument, scout_orders_given=scout_count
            )
            result.feature_power_outcome = replace(result.feature_power_outcome, feature_id=feature.feature_id)


def _apply_monster_duel_merit(
    state: GameState,
    leader: LeaderState,
    guardian_monster: Monster,
    *,
    leader_won: bool,
    leader_combatant: Combatant,
) -> None:
    """Phase 462: Duellist (id 44), Cravenest/King of Cowards (id 49), and
    Bravest of the Brave (id 50) merit's own monster-opponent branch --
    ``AKGEN_reverse_engineering_report (2).md`` SS17.3 quotes the exact
    compiled filter: these three merit tallies are also updated against
    "un mostro nel gruppo compilato 12..21" (``DUEL_MERIT_MONSTERS``,
    ``models/monster.py``), one-sided, since ``Inc_Tit`` rejects any ID
    outside the real leader range -- the monster side of the encounter
    never receives or loses merit, only the leader does. Mirrors ``turn/
    challenge_execution.py _apply_duel_encounter_merit()``'s own formula
    exactly (Phase 443), just reduced to its one-sided monster-opponent
    half: no ``target``/``accepted=False`` branch exists here, since a
    Search encounter against a guardian has no leader-vs-leader
    "refused" concept to replicate.

    ``leader_won=True``: decisive win, stake 2 -- ``duel_merit_net += 2``
    plus Bravest's own protagonist-only, winner-only credit (the leader's
    own real starting hit points -- ``CHARACTER_HIT_POINTS`` plus
    whatever ``arcane_valor_hit_points_bonus()`` gave them, the same
    total ``_leader_combatant()`` seeded them with -- minus
    ``leader_combatant.hit_points``, 0 for an unscathed win, per SS18.7 --
    the leader executing this SEARCH order is always the encounter's own
    "protagonist" against a monster, there being no separate challenger/
    target split to resolve as there is in a real Challenge). **Phase
    1052 bug fix**: this used to subtract from the bare ``CHARACTER_
    HIT_POINTS`` constant instead, crediting a negative ``bravery_merit``
    to any Scepter-of-Life-boosted leader who won cleanly -- the exact
    bug ``turn/challenge_execution.py _apply_duel_encounter_merit()``
    was already fixed for (its own "mirrors ... exactly" claim above was
    never actually kept in sync). A leader who wins unscathed is
    credited 0, not skipped. Cravenest's dispatcher always skips the
    winner's own branch (SS18.5), so no courage-merit change here
    either.

    ``leader_won=False``: decisive loss (the guardian killed the leader)
    -- ``duel_merit_net -= 2`` and ``courage_encounter_merit -= 1``
    (SS18.5's "penalizzato di un punto qualunque leader perda un
    incontro ordinario", regardless of temperament). No bravery merit --
    that credit is winner-only.
    """

    if guardian_monster not in DUEL_MERIT_MONSTERS:
        return

    if leader_won:
        leader.merit_tally.duel_merit_net += 2
        starting_hit_points = CHARACTER_HIT_POINTS + arcane_valor_hit_points_bonus(state, leader)
        bravery_gain = starting_hit_points - leader_combatant.hit_points
        leader.merit_tally.bravery_merit += bravery_gain
    else:
        leader.merit_tally.duel_merit_net -= 2
        leader.merit_tally.courage_encounter_merit -= 1


_GUARDIAN_RIDDLES: tuple[Treasure, ...] = (
    Treasure.QUEST_RA_RIDDLE,
    Treasure.QUEST_RA_COFFIN,
    Treasure.QUEST_RA_BRIDGE,
    Treasure.QUEST_RA_CANDLE,
    Treasure.QUEST_RA_SMOKE,
    Treasure.QUEST_RA_OWNER,
    Treasure.QUEST_RA_MAN,
)


def _select_guardian_riddle(monster: Monster, feature_id: int) -> Treasure:
    """Which of the 7 real ``report/turn_report.py QUEST_RIDDLE_TEXT``
    entries a guardian poses on a ``MonsterTalkReply.R_RIDDLE`` Talk
    reply.

    **Not a ported algorithm -- project-original, explicitly unsourced.**
    The real engine's own reply selector, ``Get_Reply`` (``turn/
    monster_raids.py resolve_monster_raid_reply()``'s own Phase 679
    docstring), returns a second output byte (``rep2``, "a dialogue/
    quest-fallback byte") that is almost certainly the real selector for
    this -- but it is never read by any caller this project has
    disassembly access to, so its real meaning/range stays an open,
    already-tracked gap. Rather than leave every Riddle guardian mute
    (the status quo before this function existed: the real, already-
    transcribed riddle text sat in ``QUEST_RIDDLE_TEXT`` with "no
    consumer wired yet"), this picks one deterministically per
    ``(monster, feature_id)`` purely so the same guardian always poses
    the same riddle on a repeat Talk. It has zero effect on any real
    game mechanic -- SA/Fulfill stay exactly as undocumented as they
    were before this function existed (see ``_resolve_fulfill()``'s own
    docstring).
    """

    return _select_guardian_item(monster, feature_id, _GUARDIAN_RIDDLES)


_GUARDIAN_QUEST_LOCATIONS: tuple[Treasure, ...] = (
    Treasure.QUEST_SNOW_QUEST,
    Treasure.QUEST_SAPPH_RING,
    Treasure.QUEST_LUCKY_PENNY,
    Treasure.QUEST_GODS_QUEST,
    Treasure.QUEST_MERMAID_AMULET,
)


def _select_guardian_quest_location(monster: Monster, feature_id: int) -> Treasure:
    """Which of the 5 real ``report/turn_report.py QUEST_VISIT_TEXT``
    entries a guardian proposes on a ``MonsterTalkReply.R_VISIT`` Talk
    reply.

    **Not a ported algorithm -- project-original, explicitly unsourced**,
    the exact sibling of ``_select_guardian_riddle()`` above for this
    different reply/catalog pair -- see that function's own docstring
    for why no real selector byte is recoverable. Deterministic per
    ``(monster, feature_id)`` so the same guardian always proposes the
    same quest on a repeat Talk; zero effect on any real game mechanic.
    """

    return _select_guardian_item(monster, feature_id, _GUARDIAN_QUEST_LOCATIONS)


def _select_guardian_item(monster: Monster, feature_id: int, items: tuple[Treasure, ...]) -> Treasure:
    """Phase 1053: the deterministic ``(monster.value * len(items) +
    feature_id) % len(items)`` selection formula shared, confirmed
    identical, by ``_select_guardian_riddle()``/``_select_guardian_quest_
    location()`` above -- each simply names its own catalog.
    """

    index = (monster.value * len(items) + feature_id) % len(items)
    return items[index]


def _grant_search_treasure(state: GameState, leader_id: int, treasure: Treasure) -> None:
    """Phase 548 -- ``VALHALLA.txt`` rule 1: "If Vahlalla visitor
    searches a feature, any monetary treasure Vahlalla visitor captures
    will be given to you" -- an immediate hand-off to the Kingdom's own
    King, distinct from rule 2's magic treasure (stays with the visitor
    until departure, see ``turn/valhalla_execution.py process_valhalla_
    departure()``). This project has no "convert a held Gold Hoard item
    into ``KingdomState.treasury``" mechanic anywhere -- Gold Hoards are
    ``TreasureCategory.GOLD_HOARD`` items like any other (confirmed via
    ``turn/cast_execution.py ENHANCED_CHARM_ELIGIBLE_CATEGORIES``/``turn/
    use_mi_execution.py USE_MI_TARGET_CATEGORIES``, both of which
    exclude it). The honest, sourced reading: route the item itself to
    the King immediately, the same item hand-off idiom departure already
    uses for everything else. Every other leader (and the visitor on any
    other turn, or for any other treasure category) is unaffected --
    falls straight through to the ordinary grant.
    """

    visitor = state.leaders.get(leader_id)
    is_active_visitor = (
        leader_id == VALHALLA_VISITOR_LEADER_ID and visitor is not None and visitor.valhalla_active_turn == state.turn_number
    )
    if is_active_visitor and TREASURE_CATEGORY.get(treasure) is TreasureCategory.GOLD_HOARD:
        king = find_king_of_kingdom(state, visitor.kingdom_id)
        if king is not None:
            state.add_item(treasure, king.leader_id)
            return
    state.add_item(treasure, leader_id)


def _melee_swing_from_reactive(attacker: str, result: ReactiveMeleeSwingResult) -> MeleeSwing:
    """Phase 1053: wraps a ``resolve_reactive_melee_swing()`` result into
    a real ``MeleeSwing`` -- confirmed byte-identical at all 3 call sites
    inside ``_resolve_search_encounter()`` below (the Melee-vs-Cast
    branches and the Short Range Archery pre-shot swing), differing only
    by which side ``attacker`` ("a"/"b") names.
    """

    return MeleeSwing(
        attacker=attacker,
        hit=result.hit,
        damage=result.damage,
        weapon_proc=result.weapon_proc,
        weapon_proc_hit_points=result.weapon_proc_hit_points,
    )


def _resolve_search_encounter(
    state: GameState,
    leader_id: int,
    request: SearchRequest,
    rng: random.Random,
) -> SearchExecutionResult:
    """The real Search-encounter resolution body -- see module docstring
    for exactly which cases resolve real combat and which honestly
    report ``combat_resolved=False`` instead. Split out from
    ``execute_search()`` (Phase 274) so Scout's own "always resolves
    last, whatever else happened" rule can wrap this function's result
    without threading a post-hoc hook through every return site below.
    """

    leader = state.leaders.get(leader_id)
    if leader is None:
        return SearchExecutionResult(accepted=False, reason="leader not found")

    feature = state.features.get(request.feature_id)
    if feature is None:
        return SearchExecutionResult(accepted=False, reason="feature not found")

    if feature.looted:
        return SearchExecutionResult(accepted=False, reason="feature already looted")

    if feature.guardian_monster is None:
        return SearchExecutionResult(accepted=False, reason="feature has no guardian recorded")

    if leader.location != feature.coord:
        return SearchExecutionResult(accepted=False, reason="not co-located with feature")

    stats = MONSTER_COMBAT_STATS.get(feature.guardian_monster)
    if stats is None:
        monster_name = MONSTER_NAMES.get(feature.guardian_monster, "guardian")
        return SearchExecutionResult(
            accepted=True,
            combat_resolved=False,
            reason=f"no combat stats for guardian ({monster_name}) -- see models/monster.py MONSTER_COMBAT_STATS",
        )

    leader_combatant = _leader_combatant(state, leader)
    monster_combatant = Combatant(
        name=MONSTER_NAMES.get(feature.guardian_monster, "guardian"),
        hit_points=rng.randint(*stats.hit_points_range),
        melee_skill=stats.melee_skill,
        melee_damage_range=stats.melee_damage,
        archery_skill=stats.missile_skill,
        missile_damage_range=stats.missile_damage if stats.missile_damage is not None else FIRE_ARROW_DAMAGE_RANGE,
        regenerates_hp=TROLL_REGENERATION_PER_COMBAT_ROUND if feature.guardian_monster is Monster.TROLL else 0,
        is_undead_or_anti_holy=feature.guardian_monster in (HAND_OF_DEATH_ANTI_HOLY_MONSTERS | SPIRITWRACK_UNDEAD_MONSTERS),
    )

    # Phase 617: this Feature's own passive battle field, if any --
    # Power.DAMP_COLLEGE/DAMP_MAGIC/WARP_SPACE ("Special Features.md"
    # section 5.2, user-supplied 2026-08-22: "questi poteri... sono
    # campi del luogo... l'effetto deve essere consultato durante
    # magia/combattimento nel Feature", i.e. always live for whoever
    # fights here, independent of whether Scout has ever revealed it --
    # unlike Phase 616's own 9 TRACTABLE_POWERS, which are a Scout-
    # granted *reveal*, these three are never gated on discovery at
    # all). Computed once per encounter and closed over by
    # `_resolve_cast_tactic()` below for DAMP_COLLEGE/DAMP_MAGIC;
    # WARP_SPACE is applied immediately here since it's a static
    # per-combatant multiplier, not a per-roll check.
    feature_power_event = derive_feature_event(feature)
    if feature_power_event.power is Power.WARP_SPACE:
        leader_combatant.archery_hit_multiplier *= WARP_SPACE_ARCHERY_HIT_CHANCE_MULTIPLIER
        leader_combatant.offensive_hit_multiplier *= WARP_SPACE_MELEE_HIT_CHANCE_MULTIPLIER
        monster_combatant.archery_hit_multiplier *= WARP_SPACE_ARCHERY_HIT_CHANCE_MULTIPLIER
        monster_combatant.offensive_hit_multiplier *= WARP_SPACE_MELEE_HIT_CHANCE_MULTIPLIER

    # Phase 255: the Defender Merit Point formula ([TABELLA DELLE CARICHE
    # IMPERIALI], `turn/merit_points.py defender_merit_points()`) credits
    # "il totale Punti Ferita del mostro" -- the monster's own *starting*
    # hit points, not whatever's left when it dies (always <=0 by then).
    # Captured once, right after roll, before any combat mutates it.
    monster_starting_hit_points = monster_combatant.hit_points

    # Phase 178: the guardian's own Special Encounter Plan, independent
    # of the leader's -- only consulted for whether it wants to Shoot
    # before Melee (its own CAST entries stay unwired). See module
    # docstring's own Phase 178 addendum.
    monster_plan = roll_monster_encounter_plan(
        feature.guardian_monster, rng, attacker_is_undead=leader.alignment is Alignment.UNDEAD
    )
    monster_wants_shoot = monster_plan is not None and any(t.maneuver is Maneuver.SHOOT for t in monster_plan)
    # Phase 209: the guardian's own CAST entries, resolved once, right
    # before the first real combat phase -- same injection point already
    # established for `monster_wants_shoot` above (Phase 178). See module
    # docstring's own Phase 209 addendum. `_resolve_monster_casts()`
    # below walks `monster_plan` directly (Phase 238) rather than a
    # pre-filtered tuple, so Augur Combat can see its own true position.

    # Phase 293: the guardian's own cursor into `monster_plan` -- shared
    # between `_resolve_monster_casts()`'s own pre-melee burst (which now
    # stops at the guardian's own first Melee tactic instead of bursting
    # past it) and `_resolve_melee_range_round()`'s own round-by-round
    # walk once real Melee begins. `current_range` starts at `SPELL_
    # RANGE` ([5.0]'s own "Encounters usually begin at spell range") and
    # is set to `MELEE_RANGE` exactly once, the moment real Melee combat
    # is first engaged (either the leader's own Melee tactic or the
    # exhausted-tactic-list default) -- never reverts. `melee_setup_done`
    # guards the one real `apply_temper_melee_setup()` call this module
    # now makes directly (Phase 293), since round-stepped Melee no longer
    # ever goes through `resolve_melee_duel()`'s own internal call to it
    # -- see module docstring's own Phase 293 addendum.
    monster_tactic_index = 0
    current_range = CombatRange.SPELL_RANGE
    melee_setup_done = False
    # Summons that dissolved each other (turn/encounter.py SUMMON_SPELLS): the leader's tactics
    # used up as the answer to the guardian's own summon, where the leader stands in his plan,
    # and the one-shot flag a probing cast reports back through.
    consumed_leader_tactics: set[int] = set()
    leader_tactic_cursor = 0
    summon_probe_ready = False

    # Phase 732: this encounter's own Personal-Combat cast-slot trackers
    # (`turn/encounter.py try_consume_combat_cast_slot()`'s own docstring
    # has the full sourced rule) -- one pair per real caster identity,
    # leader and guardian monster alike (user-confirmed both are in
    # scope), never persisted beyond this one call.
    leader_cast_slots_used: dict[Ability, int] = {}
    leader_cast_spells_attempted: set[Spell] = set()
    monster_cast_slots_used: dict[Ability, int] = {}
    monster_cast_spells_attempted: set[Spell] = set()

    def _outcome_from(combat_result: EncounterCombatResult) -> SearchExecutionResult | None:
        outcome = _outcome_from_raw(combat_result)
        if outcome is not None:
            outcome.hand_of_death_aborts = tuple(hand_of_death_aborts)
        return outcome

    def _outcome_from_raw(combat_result: EncounterCombatResult) -> SearchExecutionResult | None:
        """Translate a resolved duel into a terminal result, or None if the
        encounter isn't over yet (only possible for Fire Arrow -- Melee
        always ends in a winner, see resolve_melee_duel's own docstring).

        Every real combat-resolution call site in this module always
        passes the leader as side "a" and the guardian as side "b" (see
        the module's own combat-call sites), so this is the single,
        centralized point every kill/death in this module funnels
        through -- including the instant-win/instant-death branches
        ``_resolve_cast_tactic()`` synthesizes for its various spells.

        Phase 462: also the single centralized point for the Duellist/
        Cravenest/Bravest of the Brave monster-opponent merit branch
        (``_apply_monster_duel_merit()`` below) -- see that helper's own
        docstring.
        """

        if combat_result.winner == "a":
            feature.looted = True
            # Phase 242: grant the feature's own treasure (if world
            # generation set one -- `None` for features created outside
            # that pipeline, e.g. most existing tests) to the winning
            # leader via the existing item registry (Phase 140).
            if feature.treasure is not None:
                _grant_search_treasure(state, leader_id, feature.treasure)
            # Phase 255: every "a" win here is a real combat defeat of the
            # guardian (melee, fire arrow, or a spell's own instant-kill
            # branch) -- never the rulebook's separate "neutralized via
            # negotiation" case, which needs Fulfill/Talk-Say's own
            # not-yet-wired mechanic (see module docstring). Full HP
            # credited, not the halved figure -- that halving is
            # `defender_merit_points()`'s own job, not this raw tally's.
            leader.merit_tally.monster_hp_defeated += monster_starting_hit_points
            _apply_monster_duel_merit(state, leader, feature.guardian_monster, leader_won=True, leader_combatant=leader_combatant)
            return SearchExecutionResult(accepted=True, combat_resolved=True, winner="leader", feature_looted=True)
        if combat_result.winner == "b":
            _apply_monster_duel_merit(state, leader, feature.guardian_monster, leader_won=False, leader_combatant=leader_combatant)
            # Phase 671/673: the guardian survived this encounter --
            # check the real intimidation/undeterred outcome. See
            # _resolve_guardian_pacification()'s own docstring.
            intimidated, undeterred = _resolve_guardian_pacification()
            state.remove_leader(leader_id)
            return SearchExecutionResult(
                accepted=True,
                combat_resolved=True,
                winner="monster",
                leader_killed=True,
                guardian_intimidated=intimidated,
                guardian_undeterred=undeterred,
            )
        return None

    cast_attempt_applied = False

    def _resolve_cast_tactic(
        tactic,
        *,
        caster_is_leader: bool,
        is_first_tactic: bool = False,
        forced_level: int | None = None,
        summon_probe: bool = False,
    ) -> SearchExecutionResult | None:
        """Applies one of the ten Personal-Combat-only spells (or Charm's
        combat form) to the encounter: the 8 non-channeled, one-roll
        spells from Phase 209 (see that phase's own module docstring
        addendum for the full per-spell design and the rulebook citations
        behind ``PERSONAL_COMBAT_SPELL_ABILITY``), Hand of Death and
        Mirror-Image Phantasm from Phase 210 (both of which delegate their
        own round-based sub-loop to ``resolve_hand_of_death_channel()``/
        ``resolve_mirror_image_duel()``, ``turn/encounter.py``'s own
        Phase 210 addendum), and Illusory Hero from Phase 211 (``resolve_
        illusory_hero_duel()`` -- Mirror-Image's own duel shape, but the
        illusion is built from whichever hero is currently visiting
        Valhalla, ``models/valhalla.py VALHALLA_VISITOR_LEADER_ID``,
        rather than a clone of the opponent, and Stage 2 only fires when
        the hero's and caster's own alignments are confirmed "implacably
        hostile"), Gate Demon/Lava Pool from Phase 237 (a summoned
        demon fights the opponent in Gate Demon's own place via a fresh
        ``resolve_melee_duel()``; Lava Pool is a flat, speed-keyed
        instant-kill-or-escape roll), Augur Combat from Phase 238
        (``is_first_tactic`` -- true position within the caster's own
        full plan, not just among its own ``CAST`` entries -- decides
        whether this runs the real "silent simulation" (a throwaway
        ``resolve_melee_duel()`` on cloned combatants, discarded after
        reading only its winner) or acts as an attempted Flee, per
        ``turn/encounter.py``'s own Phase 205 addendum), Words of
        Healing from Phase 289 (``words_of_healing_heal()`` -- self-only,
        gated by the same secret-spell skill-5+ eligibility check as
        Illusory Hero, no target interaction at all -- this closed the
        gap in this function's own spell coverage of all 16 real,
        rulebook/Pascal-sourced Personal-Combat spell mechanics ``turn/
        encounter.py`` documents), and **Gate Angel, project-original,
        not sourced from any rulebook or Pascal text** (sourced
        directly from the user, 2026-10-28, who asked for this duel
        deliberately even after this project's own investigation found
        Gate Angel's real, documented effect is a world-level Valhalla-
        visit lottery with zero combat content -- see ``GATE_ANGEL_
        KNOWN_ABILITY_LEVEL``'s own docstring above for the full
        rationale): mirrors Gate Demon's own shape exactly, but the
        summoned combatant is whichever hero is currently visiting
        Valhalla rather than a randomly rolled demon species, and there
        is no refusal roll. Returns a terminal
        ``SearchExecutionResult`` (a kill, a neutralization, Charm's own
        guaranteed Flee, or nothing terminal for a self-only effect like
        Words of Healing), or ``None`` if the encounter continues (a
        failed cast, a stat-modifier effect, or a spell whose target
        isn't eligible).

        **``forced_level`` (Phase 274)**: when given, skips
        ``resolve_personal_combat_spell_cast()``'s own roll entirely
        (automatic success, [3.11]/[5.1]'s own rule for a wand-cast
        spell) and uses this value instead of the caster's real ability
        level -- ``turn/search_execution.py``'s own ``_resolve_use_mi_
        tactic()`` is the only caller. ``cast_attempt_applied`` (an
        enclosing-scope flag, not a return value, since most of this
        function's own real spell effects return ``None`` on a genuine
        success too) is set the instant every precondition check below
        is passed, letting a Use_MI caller know whether to spend a
        charge regardless of which further branch the spell's own
        effect takes.

        **Kill Enemy [4.25.2] (2026-10-31, user-requested Personal-
        Combat build)**: joins the 16 spells above as a 17th branch --
        King immunity, Undead-target immunity (reachable against a real
        Monster target here, unlike the Action-Cast sibling in
        ``cast_execution.py``), the Special-Place/army-leading halving
        (always true in this module, since a Search encounter is
        definitionally "in un Luogo Speciale"), Hidden Tattoos' survival
        ward, and a real outright kill on success (not the Action-Cast
        form's coma substitute) or an inline Berserk-retaliation
        ``resolve_melee_duel()`` on failure -- see this branch's own
        inline comments below for the full citation trail. The
        rulebook's own "un negromante non può usarlo per difendere sé
        stesso in un piano incontro" restriction has no analog here --
        Search has no defensive-queue concept distinct from each side's
        own offensive tactic list, unlike Challenge/Pursue's target-side
        defensive Cast; see ``challenge_execution.py``'s own Kill Enemy
        addendum for where that restriction is actually enforced.
        """

        nonlocal cast_attempt_applied, summon_probe_ready
        cast_attempt_applied = False
        # Phase 1052: Kill Enemy's retaliation duel and Gate Demon/Gate
        # Angel's summoned-combatant duels below all call resolve_melee_
        # duel() directly -- this function's own three other call sites
        # (none; those live in the enclosing function, further down)
        # pass skip_temper_setup=melee_setup_done and merge melee_swings
        # into the outer accumulator, and these three sub-duels now do
        # the same, closing a gap confirmed to otherwise double-apply
        # Temper/Ability setup and drop these duels' own swings from
        # Melee-XP crediting and report narration (see the module
        # docstring's own Phase 1052 addendum, and `turn/challenge_
        # execution.py`'s own identical "Phase 1042 bug fix" for the
        # Kill Enemy/Gate Demon half of this).
        nonlocal melee_setup_done
        nonlocal melee_swings

        caster = leader_combatant if caster_is_leader else monster_combatant
        target = monster_combatant if caster_is_leader else leader_combatant
        if caster.blocked_from_cast:
            return None
        try:
            spell = Spell(tactic.sub_object)
        except ValueError:
            return None

        target_is_monster = caster_is_leader
        monster_species = feature.guardian_monster
        # Phase 1053: the "a"/"b" slot translation below -- the caster
        # occupies "a" when target_is_monster, "b" otherwise, and the
        # target occupies the opposite slot -- was re-derived inline via
        # the same two-value ternary at ~18 separate return sites in this
        # function. Computed once here and reused everywhere instead,
        # the same "compute once, reuse the two names" pattern Hand of
        # Death's own branch already used locally (caster_slot/target_
        # slot) before this phase generalized it to the whole function.
        caster_slot = "a" if target_is_monster else "b"
        target_slot = "b" if target_is_monster else "a"
        # Phase 1053: "does the target's own Kingdom hold Discovery X"
        # (a monster target has no Kingdom either way) was re-derived via
        # this same None-guarded lookup for 4 separate Discoveries below
        # (Psychic Blast/Invisibility/Fireball/Hand of Death). The lookup
        # itself depends on nothing those spells vary -- only on this
        # function's own fixed target_is_monster -- so it's computed once
        # here and reused as `target_kingdom` everywhere (replacing the
        # Invisibility branch's own separately-named but equivalent
        # `opponent_kingdom`, guarded on `not caster_is_leader` --
        # identical to `not target_is_monster` since target_is_monster is
        # just caster_is_leader under another name).
        target_kingdom = state.kingdoms.get(leader.kingdom_id) if not target_is_monster else None

        # Charm's own Phase 183 addendum: an Undead caster draws on
        # Necromancy instead of Psychic. Replicated here rather than
        # imported from `cast_execution.py._spell_ability` (private, tied
        # to `LeaderState`) -- same "duplicate the small lookup" precedent
        # as `_leader_combatant()` above. For a monster caster, "Undead"
        # means its own species is in `SPIRITWRACK_UNDEAD_MONSTERS`
        # (monsters have no `alignment` field to check).
        caster_is_undead = (
            (leader.alignment is Alignment.UNDEAD)
            if caster_is_leader
            else (monster_species in SPIRITWRACK_UNDEAD_MONSTERS)
        )
        if spell is Spell.CHARM:
            ability = Ability.NECROMANCY if caster_is_undead else Ability.PSYCHIC
        elif spell is Spell.ILLUS_HERO:
            # Phase 211: not in PERSONAL_COMBAT_SPELL_ABILITY (that table
            # is only the ten base Personal-Combat spells) -- Illusory
            # Hero is one of the ten secret spells, tied to Ability.
            # ILLUSION (module docstring's own Phase 208/211 addenda).
            ability = Ability.ILLUSION
        elif spell is Spell.GATE_DEMON:
            # Phase 237: secret spell, tied to Ability.NECROMANCY
            # (`turn/encounter.py`'s own Phase 202 addendum).
            ability = Ability.NECROMANCY
        elif spell is Spell.GATE_ANGEL:
            # Project-original Personal-Combat duel (see
            # GATE_ANGEL_KNOWN_ABILITY_LEVEL's own docstring above) --
            # tied to Ability.WHITE, matching this spell's real,
            # existing Action-Cast gate (`turn/cast_execution.py`'s own
            # `SECRET_ACTION_SPELLS`/`Ability.WHITE` ladder).
            ability = Ability.WHITE
        elif spell is Spell.LAVA_POOL:
            # Phase 237: secret spell, tied to Ability.ELEMENTAL
            # (`turn/encounter.py`'s own Phase 203 addendum).
            ability = Ability.ELEMENTAL
        elif spell is Spell.AUGUR_COMBAT:
            # Phase 238: secret spell, tied to Ability.PSYCHIC
            # (`turn/encounter.py`'s own Phase 205 addendum).
            ability = Ability.PSYCHIC
        elif spell is Spell.HEAL:
            # Phase 289: secret spell (Words of Healing), tied to
            # Ability.WHITE (`turn/encounter.py`'s own Phase 200
            # addendum).
            ability = Ability.WHITE
        elif spell in PERSONAL_COMBAT_SPELL_ABILITY:
            ability = PERSONAL_COMBAT_SPELL_ABILITY[spell]
        else:
            return None  # not modeled (any spell outside the 16 Personal-Combat spells this function covers)

        # Phase 617: Power.DAMP_COLLEGE ("Special Features.md" section
        # 5.2/3.2: "impedisce di lanciare incantesimi della scuola _abil
        # selezionata" -- prevents casting any spell of the selected
        # school outright). An absolute local ban, not a probability
        # reduction, so it's checked before even a wand's own automatic-
        # success rule (`forced_level is not None` below) -- a wand
        # can't cast a spell school the location itself blocks. No roll,
        # no `cast_attempt_applied`, same "ineligible means nothing
        # happened" shape as `caster.blocked_from_cast` above.
        if feature_power_event.power is Power.DAMP_COLLEGE and ability is feature_power_event.ability_parameter:
            return None

        # Control Undead's own eligibility precondition -- checked before
        # any roll, same as every other spell's `target_is_immune` guard,
        # except here an ineligible target means no roll at all rather
        # than a roll that simply has no effect.
        if spell is Spell.CONTROL_UNDEAD:
            if target_is_monster:
                target_is_undead = monster_species in SPIRITWRACK_UNDEAD_MONSTERS
                # Phase 502: AdvancedAbility.ENHANCED_COMBAT_NE_SPELLS --
                # "'Control Undead' will work against anti-holy
                # creatures, in addition to affecting the Undead." Only
                # reachable here (a monster caster can't hold an
                # Advanced Ability, so the `else` branch below never has
                # a caster to check).
                control_undead_target_is_anti_holy_only = (
                    not target_is_undead
                    and AdvancedAbility.ENHANCED_COMBAT_NE_SPELLS in leader.advanced_abilities
                    and monster_species in HAND_OF_DEATH_ANTI_HOLY_MONSTERS
                )
                eligible = target_is_undead or control_undead_target_is_anti_holy_only
            else:
                control_undead_target_is_anti_holy_only = False
                eligible = leader.alignment is Alignment.UNDEAD
            if not eligible:
                return None

        # Kill Enemy's own eligibility precondition, same "ineligible
        # means no roll at all" pattern as Control Undead above: Kings
        # are immune ("I Re sono immuni a questo incantesimo"), and
        # Undead targets are immune ("inefficace contro Non-Morti,
        # fantasmi, demoni e simili, perche' queste creature esistono
        # solo parzialmente nel mondo materiale") -- for a monster
        # target, read as the same SPIRITWRACK_UNDEAD_MONSTERS set
        # every other Undead-eligibility check in this module already
        # uses. This Personal-Combat path is the one place Kill Enemy
        # can actually reach a Monster target -- `cast_execution.py`'s
        # own Action-Cast sibling only ever targets a LeaderState, so
        # its docstring flags the "fantasmi, demoni" half of the
        # immunity clause as structurally unreachable there; here it
        # is reachable, and checked.
        if spell is Spell.KILL_ENEMY:
            if target_is_monster:
                if monster_species in SPIRITWRACK_UNDEAD_MONSTERS:
                    return None
            elif leader.is_king or leader.alignment is Alignment.UNDEAD:
                return None

        if forced_level is not None:
            # Phase 274: a wand-cast spell -- TREASAB.X2's own fixed
            # "at skill-2" label overrides the caster's real ability
            # level entirely, and there's no Pagan-Realm concept to
            # apply to an item's own automatic success.
            level = forced_level
            caster_is_pagan = False
        elif caster_is_leader:
            level = effective_skill_level(state, leader, ability)
            kingdom = state.kingdoms.get(leader.kingdom_id) if leader.kingdom_id is not None else None
            # White Magic never gets the Pagan-Realm bonus (Phase 192).
            caster_is_pagan = (
                ability is not Ability.WHITE and kingdom is not None and kingdom.alignment is Alignment.PAGAN
            )
        else:
            level = MONSTER_MAGIC_ABILITIES.get(monster_species, {}).get(ability, 0)
            caster_is_pagan = False  # a monster has no Kingdom

        # Illusory Hero is exclusively leader-cast (never appears in any
        # real monster_encounter_plan.py species plan) and requires
        # ILLUS_HERO_KNOWN_ABILITY_LEVEL -- checked before the roll, same
        # "ineligible means no roll at all" pattern as Control Undead.
        if spell is Spell.ILLUS_HERO and level < ILLUS_HERO_KNOWN_ABILITY_LEVEL:
            return None
        if spell is Spell.HEAL and level < WORDS_OF_HEALING_KNOWN_ABILITY_LEVEL:
            return None
        # Phase 761: the same secret-spell skill-5+ gate for the other 3
        # secret Personal-Combat spells this module dispatches -- checked
        # unconditionally regardless of caster, matching Illusory Hero/
        # Words of Healing's own exact shape above (and, like Words of
        # Healing's own real ``MONSTER_MAGIC_ABILITIES`` data, no real
        # monster in that table reaches level 5 for any Ability -- a
        # monster genuinely can't cast any of these today, the same as
        # Words of Healing already was; a synthetic ``patch.dict`` test
        # fixture is how this project already exercises that hypothetical
        # path, see this module's own test suite).
        if spell is Spell.GATE_DEMON and level < GATE_DEMON_KNOWN_ABILITY_LEVEL:
            return None
        if spell is Spell.GATE_ANGEL and level < GATE_ANGEL_KNOWN_ABILITY_LEVEL:
            return None
        if spell is Spell.LAVA_POOL and level < LAVA_POOL_KNOWN_ABILITY_LEVEL:
            return None
        if spell is Spell.AUGUR_COMBAT and level < AUGUR_COMBAT_KNOWN_ABILITY_LEVEL:
            return None

        # Phase 732: a wand-cast (`forced_level` set) is [3.11]'s own
        # separate automatic-success mechanic and never consumes a
        # combat-cast slot at all (user-confirmed) -- only a genuine
        # Personal-Combat cast attempt does, right before its own real
        # success roll, once every other precondition above has passed.
        if forced_level is None:
            slots_used = leader_cast_slots_used if caster_is_leader else monster_cast_slots_used
            spells_attempted = leader_cast_spells_attempted if caster_is_leader else monster_cast_spells_attempted
            if not try_consume_combat_cast_slot(ability, spell, level, slots_used, spells_attempted):
                return None

        cast_attempt_applied = True  # every real precondition above is now passed
        if forced_level is not None:
            succeeded = True  # [3.11]/[5.1]: "a spell cast from a magic item is automatically successful"
        else:
            damp_magic = feature_power_event.power is Power.DAMP_MAGIC
            # Phase 703: "For Search Feature actions, the 20% bonus is
            # applied when that type of feature is searched" -- unlike
            # `cast_execution.py`'s own Action-Cast half, there's no
            # "not occupied by a monster" clause here: Searching a
            # Feature already means targeting that exact one, guarded
            # or not. A monster caster can't hold an Advanced Ability,
            # so `caster_is_leader` gates this the same way `caster_is_
            # pagan` above already does.
            places_ability = PLACES_ABILITY_FOR_ABILITY.get(ability)
            places_bonus = (
                caster_is_leader
                and places_ability is not None
                and places_ability in leader.advanced_abilities
                and feature.kind in PLACES_FEATURE_TYPES[places_ability]
            )
            # Kill Enemy [4.25.2]: "la possibilita' di riuscita e'
            # ridotta alla metà in un incontro in un Luogo Speciale o
            # contro un Eroe che comanda unità militari" -- a Search
            # encounter is, by construction, always an encounter at a
            # Feature (`feature = state.features.get(request.feature_
            # id)`, set once at the top of `execute_search()`), so the
            # "in un Luogo Speciale" half of this OR is unconditionally
            # true here; the army-leading half is therefore redundant
            # with it in this module (unlike `challenge_execution.py`,
            # where neither side is ever at a searched Feature and the
            # army-leading check is the only trigger) and isn't checked
            # separately.
            kill_enemy_multiplier = 0.5 if spell is Spell.KILL_ENEMY else 1.0
            succeeded = resolve_personal_combat_spell_cast(
                level,
                rng,
                caster_is_pagan=caster_is_pagan,
                damp_magic=damp_magic,
                places_bonus=places_bonus,
                success_chance_multiplier=kill_enemy_multiplier,
            )

        # Phase 531: AKGEN_reverse_engineering_report (4).md SS8 -- only
        # reachable here when the *leader* is the one being cast at (a
        # hostile monster's own spell attempt, `target_is_monster is
        # False`); a monster target never holds an item in this
        # project's model, so there is nothing to check on that side.
        # Same per-spell (not per-college) immunity, self-only exclusion,
        # and single-checkpoint placement as ``challenge_execution.py``'s
        # own Phase 531 addendum.
        if (
            succeeded
            and not target_is_monster
            and spell not in PERSONAL_COMBAT_SPELL_SELF_ONLY
            and (
                holder_is_immune_to_spell(state, leader_id, spell)
                or _necromancer_mage_resists_spell(state, leader_id, rng)
            )
        ):
            return None

        if spell is Spell.CONTROL_UNDEAD:
            if succeeded:
                # Phase 502: an anti-holy-only target (not also Undead)
                # gets the resist roll; an ordinary Undead target never
                # does. Confirmed by the user: "neutralizes" equals a win.
                if control_undead_target_is_anti_holy_only and rng.random() < control_undead_anti_holy_resist_chance(
                    target.hit_points
                ):
                    return None
                return _outcome_from(EncounterCombatResult(winner=caster_slot, rounds=0))
            target.hit_points = control_undead_failure_new_hit_points(target.hit_points, rng)
            return None

        if spell is Spell.KILL_ENEMY:
            if succeeded:
                # Hidden Tattoos (Discovery.txt, Phase 270): "neutralize
                # the Kill Enemy spell of Necromancers... All characters
                # of the Kingdom are protected" -- only reachable for a
                # leader target (a monster has no Kingdom). Checked
                # after the generic Anti-Necromancy-Amulet immunity
                # above (lines 2129-2138), same order as `cast_
                # execution.py _execute_kill_enemy()`'s own True-Cross-
                # then-Hidden-Tattoos sequence.
                target_has_hidden_tattoos = (
                    not target_is_monster
                    and leader.kingdom_id is not None
                    and Discovery.HIDDEN_TATTOOS in state.kingdoms[leader.kingdom_id].discoveries
                )
                if target_has_hidden_tattoos:
                    make_sick(state, leader.leader_id)
                    return None
                # "Se l'incantesimo riesce, la vittima viene uccisa" --
                # unlike the Action-Cast form (which substitutes a coma,
                # [4.25.2]'s own documented Action-only exception), a
                # Personal-Combat success is the real kill the rulebook
                # describes as the spell's primary effect.
                return _outcome_from(EncounterCombatResult(winner=caster_slot, rounds=0))
            # "Se fallisce, la vittima designata attaccherà l'autore
            # dell'incantesimo assumendo per l'occasione un
            # temperamento Berserk, se necessario anche aggredendolo in
            # quella stessa fase" -- an immediate `resolve_melee_duel()`
            # between the designated victim (temper forced to Berserk
            # "for the occasion", mirroring `cast_execution.py
            # _kill_enemy_combatant()`'s own Action-Cast precedent) and
            # the caster, resolved inline rather than deferred. The
            # retaliator is passed first (this sub-duel's own local
            # "a"=retaliator/"b"=caster convention), then translated
            # back into this function's outer "a"=leader/"b"=monster
            # convention exactly like Gate Demon/Gate Angel's own demon/
            # angel duels above.
            # Phase 1052 bug fix -- this used to duel a `replace(target,
            # ...)` COPY ("retaliator") instead of the real `target`
            # object, while `caster` was passed directly.
            # `resolve_melee_duel()` mutates both its arguments in place,
            # so on the "vanishingly rare" draw below, the real `target.
            # hit_points` silently never reflected the damage exchanged
            # (only the disposable copy took it) while `caster.hit_
            # points` was correctly reduced -- giving the target an
            # unearned HP advantage for the rest of the encounter.
            # Mirrors `turn/challenge_execution.py`'s own identical
            # "Phase 1042 bug fix" for this same mechanic: duel the real
            # `target`, temporarily overriding/restoring its own
            # `.temper` instead of `replace()`-ing a throwaway copy.
            original_temper = target.temper
            target.temper = Temper.BERSERK
            duel_result = resolve_melee_duel(target, caster, rng, skip_temper_setup=melee_setup_done)
            target.temper = original_temper
            melee_swings.extend(duel_result.melee_swings)
            if not melee_setup_done:
                melee_setup_done = True
            if duel_result.winner == "a":  # the designated victim's Berserk retaliation kills the caster
                outcome = _outcome_from(EncounterCombatResult(winner=target_slot, rounds=0))
            elif duel_result.winner == "b":  # the caster survives and wins the retaliation
                outcome = _outcome_from(EncounterCombatResult(winner=caster_slot, rounds=0))
            else:
                return None  # the vanishingly rare max-rounds-exhausted draw -- the encounter continues
            if outcome is not None:
                outcome.melee_swings = tuple(melee_swings)
            return outcome

        if not succeeded:
            # Phase 858: SBUNGLE.X's own real "personal-combat Cast that
            # just fizzles" text -- see the enclosing function's own
            # `fizzled_spells` accumulator comment. Stored as the same
            # "leader"/"monster" side label this module's own `winner`
            # field already uses, not a raw name, so the report layer can
            # resolve display names itself (`character_name`/`monster_
            # name`) without relying on `Combatant.name` matching exactly.
            fizzled_spells.append(("leader" if caster_is_leader else "monster", spell))
            return None

        if spell is Spell.CHARM:
            # Confirmed by the user: the *caster* flees, same outcome as a
            # successful Maneuver.FLEE.
            return _flee_outcome()

        if spell is Spell.HOLY_SYMBOL:
            if target_is_monster:
                target_is_undead_or_anti_holy = monster_species in (HAND_OF_DEATH_ANTI_HOLY_MONSTERS | SPIRITWRACK_UNDEAD_MONSTERS)
                # Phase 497: AdvancedAbility.ENHANCED_HOLY_SYMBOL -- "the
                # same effect against opponents who have an Evil
                # alignment as it does against Undead creatures." Only
                # reachable here since target_is_monster == caster_is_
                # leader in this function (a monster caster can't hold
                # an Advanced Ability). A monster has no persisted
                # alignment anywhere in this project -- rolled fresh via
                # roll_monster_alignment(), the same real per-species
                # distribution already reused for Gate Demon's own
                # eligibility check a few branches below, only rolled
                # when it can actually matter (not already Undead/Anti-
                # Holy, and the caster actually holds the ability).
                if not target_is_undead_or_anti_holy and AdvancedAbility.ENHANCED_HOLY_SYMBOL in leader.advanced_abilities:
                    target_is_undead_or_anti_holy = roll_monster_alignment(monster_species, rng) is Alignment.EVIL
            else:
                target_is_undead_or_anti_holy = leader.alignment in (Alignment.UNDEAD, Alignment.ANTI_HOLY)
            caster.defensive_hit_multiplier *= holy_symbol_hit_chance(
                1.0, level, target_is_undead_or_anti_holy=target_is_undead_or_anti_holy
            )
            if target_is_undead_or_anti_holy:
                target.hit_points -= roll_holy_symbol_undead_damage(level, rng)
                if target.hit_points <= 0:
                    return _outcome_from(EncounterCombatResult(winner=caster_slot, rounds=0))
            return None

        if spell is Spell.SPIRITWRACK:
            if target_is_monster:
                target_is_immune = monster_species in (SPIRITWRACK_UNDEAD_MONSTERS | SPIRITWRACK_MECHANICAL_MONSTERS)
                target_is_animal = monster_species in SPIRITWRACK_ANIMAL_INTELLIGENCE_MONSTERS
            else:
                target_is_immune = leader.alignment is Alignment.UNDEAD
                target_is_animal = False
            target.melee_damage_dealt_reduction += spiritwrack_melee_damage_reduction(
                level, rng, target_is_immune=target_is_immune, target_is_animal_intelligence=target_is_animal
            )
            target.blocked_from_cast = target.blocked_from_archery = blocks_cast_and_archery(target_is_immune=target_is_immune)
            return None

        if spell is Spell.PSYCHIC_BLAST:
            # Phase 883: Discovery.LEAD_LINED_HELMET -- same narrower
            # free-attack-round roll as turn/challenge_execution.py's
            # own Psychic Blast branch, for a leader target (a monster
            # target has no Kingdom either way).
            target_has_lead_lined_helmet = target_kingdom is not None and Discovery.LEAD_LINED_HELMET in target_kingdom.discoveries
            caster.bonus_unanswered_attacks += roll_psychic_blast_stun_rounds(
                rng, target_has_lead_lined_helmet=target_has_lead_lined_helmet
            )
            # Phase 1050 -- records that `target` is now a real Psychic-
            # Blast stun victim, for Psychic Flail's own "+1 additional
            # round if already under Psychic Blast" stacking clause
            # (`turn/encounter.py Combatant.stunned_by_psychic_blast`'s
            # own docstring).
            target.stunned_by_psychic_blast = True
            return None

        if spell is Spell.TELEK_STORM:
            target_is_immune = target_is_monster and monster_species in SUBMARINE_MONSTERS
            target.hit_points -= roll_telekinetic_storm_victim_damage(rng, target_is_immune=target_is_immune)
            caster.hit_points -= roll_telekinetic_storm_caster_damage(
                CombatRange.SPELL_RANGE, rng, target_is_immune=target_is_immune
            )
            # Phase 1042 -- reviewed and confirmed intentional (user-decided,
            # same review as turn/challenge_execution.py's own identical
            # TELEK_STORM branch): on a genuine double-KO (both sides drop
            # to <= 0 HP from this same cast), the target's own death is
            # checked first and credited as the winning side -- the engine
            # has no "both combatants die" outcome to return here, and
            # defender-dies-first priority is the one this project keeps.
            if target.hit_points <= 0:
                return _outcome_from(EncounterCombatResult(winner=caster_slot, rounds=0))
            if caster.hit_points <= 0:
                return _outcome_from(EncounterCombatResult(winner=target_slot, rounds=0))
            return None

        if spell is Spell.INVISIBILITY:
            # Phase 496: same AdvancedAbility.WITCHSIGHT_TALENT wiring as
            # turn/challenge_execution.py's own Invisibility branch --
            # the Necromancer fighting the invisible caster needs
            # Witchsight, not the caster themselves. `leader` is the
            # only real LeaderState in a Search encounter, so it only
            # matters when the leader is playing the opponent role
            # (caster_is_leader is False -- a monster cast Invisibility).
            opponent_has_witchsight = (
                not caster_is_leader
            ) and AdvancedAbility.WITCHSIGHT_TALENT in leader.advanced_abilities
            # Phase 532: same Crystal of True Seeing carve-out as
            # challenge_execution.py's own Invisibility branch -- only
            # relevant when the leader is the opponent (not the caster).
            opponent_sees_through_illusion = (not caster_is_leader) and holder_is_immune_to_spell(
                state, leader.leader_id, spell
            )
            # Phase 881: Discovery.INFRARED_GOGGLES -- same weaker,
            # partial carve-out as turn/challenge_execution.py's own
            # Invisibility branch (see that module's own Phase 881
            # comment). Only relevant when the leader plays the
            # opponent role (a monster caster has no Kingdom to hold
            # the Discovery either way) -- the same `target_kingdom`
            # computed once at the top of this function, since `not
            # caster_is_leader` is just `not target_is_monster` by
            # another name.
            opponent_has_infrared_goggles = (
                target_kingdom is not None and Discovery.INFRARED_GOGGLES in target_kingdom.discoveries
            )
            if not opponent_has_witchsight and not opponent_sees_through_illusion:
                multiplier = (
                    INFRARED_GOGGLES_HIT_CHANCE_MULTIPLIER
                    if opponent_has_infrared_goggles
                    else INVISIBILITY_HIT_CHANCE_MULTIPLIER
                )
                caster.defensive_hit_multiplier *= multiplier
            caster.is_invisible = True
            return None

        if spell is Spell.HEAL:
            # "The character is completely healed... gaining back all
            # lost hit points" -- self-only, no target interaction, no
            # skill-level scaling (only the eligibility gate above uses
            # `level`). A monster caster's own max is its starting roll
            # (`monster_starting_hit_points`, captured before this
            # encounter began mutating it); a leader caster's own max is
            # their own real starting hit points.
            #
            # Phase 1052 bug fix: this used to cap a leader caster at the
            # bare CHARACTER_HIT_POINTS constant instead. _leader_
            # combatant() seeds a leader's real starting hit points as
            # CHARACTER_HIT_POINTS + arcane_valor_hit_points_bonus(...),
            # which under GameType.ARCANES can exceed the bare constant
            # for a Scepter-of-Life-benefiting leader -- so a "complete"
            # heal left such a leader up to that bonus short of their
            # own real max, contradicting the spell's own quoted
            # "gaining back all lost hit points" text.
            max_hit_points = (
                CHARACTER_HIT_POINTS + arcane_valor_hit_points_bonus(state, leader)
                if caster_is_leader
                else monster_starting_hit_points
            )
            words_of_healing_heal(caster, max_hit_points)
            return None

        if spell is Spell.FIREBALL:
            # Phase 501: AdvancedAbility.ENHANCED_COMBAT_EL_SPELLS --
            # "Fireball can be cast against underwater monsters." Only
            # reachable here (target_is_monster == caster_is_leader in
            # this function, so a monster caster -- which can't hold an
            # Advanced Ability -- never reaches this branch with the
            # ability set).
            if target_is_monster and AdvancedAbility.ENHANCED_COMBAT_EL_SPELLS in leader.advanced_abilities:
                target_is_immune = False
            else:
                target_is_immune = target_is_monster and monster_species in SUBMARINE_MONSTERS
            # Phase 882: Discovery.ASBESTOS_CLOTHING -- reduces the
            # damage by 67% when the target is the leader (not a
            # monster, which has no Kingdom) and their own Kingdom
            # holds it.
            target_has_asbestos_clothing = target_kingdom is not None and Discovery.ASBESTOS_CLOTHING in target_kingdom.discoveries
            target.hit_points -= roll_fireball_damage(
                level, rng, target_is_immune=target_is_immune, target_has_asbestos_clothing=target_has_asbestos_clothing
            )
            if target.hit_points <= 0:
                return _outcome_from(EncounterCombatResult(winner=caster_slot, rounds=0))
            return None

        if spell is Spell.ICE_SUSPEND:
            # Phase 501: AdvancedAbility.ENHANCED_COMBAT_EL_SPELLS --
            # "Ice Suspension will work against any monster." Same
            # reachability note as Fireball above.
            ice_suspend_immune = target_is_monster and monster_species in ICE_SUSPENSION_IMMUNE_MONSTERS
            if ice_suspend_immune and AdvancedAbility.ENHANCED_COMBAT_EL_SPELLS in leader.advanced_abilities:
                ice_suspend_immune = False
            if ice_suspend_immune:
                return None
            if ice_suspension_is_frozen(target.hit_points, level):
                # Confirmed by the user: the frozen branch simplifies to a win.
                outcome = _outcome_from(EncounterCombatResult(winner=caster_slot, rounds=0))
                # Phase 855: flags the real _LShIce narration -- see
                # SearchExecutionResult.ice_suspend_immobilized's own
                # docstring for why only this one branch is captured.
                if outcome is not None:
                    outcome.ice_suspend_immobilized = True
                return outcome
            if target_is_monster and monster_species in ICE_SUSPENSION_FLYING_MONSTERS:
                target.hit_points -= roll_ice_suspension_flying_crash_damage(rng)
                caster.bonus_unanswered_attacks += roll_ice_suspension_flying_bonus_rounds(rng)
                if target.hit_points <= 0:
                    return _outcome_from(EncounterCombatResult(winner=caster_slot, rounds=0))
                return None
            caster.bonus_unanswered_attacks += ice_suspension_slowed_bonus_rounds(target.hit_points, level)
            return None

        if spell is Spell.HAND_OF_DEATH:
            if target_is_monster:
                # Phase 500: AdvancedAbility.ENHANCED_COMBAT_NE_SPELLS --
                # "'Hand of Death' now works against all creatures."
                # Only reachable here (a monster caster can't hold an
                # Advanced Ability, so the `else` branch below -- a
                # monster casting on a leader target -- never has a
                # caster to check).
                if AdvancedAbility.ENHANCED_COMBAT_NE_SPELLS in leader.advanced_abilities:
                    target_is_immune = False
                else:
                    target_is_immune = monster_species in HAND_OF_DEATH_IMMUNE_MONSTERS
            else:
                target_is_immune = leader.alignment in (Alignment.UNDEAD, Alignment.ANTI_HOLY)
            # Phase 884: Discovery.ARTIFICIAL_ORGANS -- zeroes the
            # caster's own squeeze damage for a leader target whose own
            # Kingdom holds it (a monster target never has one). Also
            # (Phase 889) relaxes the archery half of the baseline block
            # right below, per the Discovery's own real second clause.
            target_has_artificial_organs = target_kingdom is not None and Discovery.ARTIFICIAL_ORGANS in target_kingdom.discoveries
            # Phase 887/889: Hand of Death's own baseline "victim cannot
            # cast spells nor shoot with a bow" restriction -- confirmed
            # word-for-word identical to Spiritwrack's own victim effect
            # (the Spiritwrack branch right above this one already sets
            # both fields the same way) -- narrowed by Discovery.
            # ARTIFICIAL_ORGANS's own real "archery can be used (but not
            # spells)" clause via hand_of_death_cast_and_archery_block().
            # Reuses the exact same target_is_immune value just computed
            # above for both the target_is_monster and leader-target
            # branches.
            target.blocked_from_cast, target.blocked_from_archery = hand_of_death_cast_and_archery_block(
                target_is_immune, target_has_artificial_organs
            )
            channel_result = resolve_hand_of_death_channel(
                caster, target, level, rng, target_is_immune=target_is_immune, target_has_artificial_organs=target_has_artificial_organs
            )
            if channel_result.winner is None:
                hand_of_death_aborts.append(
                    (
                        "leader" if caster_is_leader else "monster",
                        channel_result.squeeze_hits,
                        None if target_is_immune else channel_result.interrupt_damage,
                    )
                )
            if channel_result.winner is not None:
                # "a" in resolve_hand_of_death_channel's own convention means
                # the caster won; "b" (Phase 1050 bug fix) means the
                # victim's own disrupting counter-attack was itself lethal
                # to the caster -- either way, translate to the leader/
                # monster "a"/"b" convention _outcome_from() expects (the
                # winning side's own slot is whichever one actually won,
                # not always the caster's) -- caster_slot/target_slot
                # computed once at the top of this function (Phase 1053).
                winner_slot = caster_slot if channel_result.winner == "a" else target_slot
                outcome = _outcome_from(EncounterCombatResult(winner=winner_slot, rounds=0))
                if outcome is not None and channel_result.winner == "a":
                    # Phase 413: the winning channel's own per-round damage,
                    # for report/turn_report.py render_squeeze_attack() --
                    # see SearchExecutionResult.squeeze_hits's own Phase 413
                    # note for why an interrupted (non-winning) channel isn't
                    # captured here.
                    #
                    # Phase 1052 bug fix: this used to copy squeeze_hits
                    # unconditionally, including the Phase-1050 winner="b"
                    # case (the victim's own counter-attack killed the
                    # caster) -- squeeze_hits is always the CASTER's own
                    # hits, but report/turn_report.py derives "who did the
                    # squeezing" from the overall winner, which in that
                    # case is the victim, not the caster. Narrating the
                    # caster's pre-death hits as the victim's own squeeze
                    # attack would be backwards, so only the caster's own
                    # real win (winner=="a") attaches squeeze_hits now --
                    # consistent with this field's own stated "only the
                    # winning (killing) channel is captured" design.
                    outcome.squeeze_hits = channel_result.squeeze_hits
                return outcome
            return None

        if spell in SUMMON_SPELLS:
            # Two summons meeting dissolve each other (turn/encounter.py SUMMON_SPELLS).
            # ``summon_probe`` is the opponent's side of that meeting: every precondition,
            # slot and roll above has been settled, and the effect is not carried out.
            if summon_probe:
                summon_probe_ready = True
                return None
            opponent_spell = _opponent_counters_summon(caster_is_leader)
            if opponent_spell is not None:
                state.summon_nullifications.append(
                    (
                        caster.name,
                        spell,
                        target.name,
                        opponent_spell,
                        (leader.kingdom_id,) if leader.kingdom_id is not None else (),
                    )
                )
                return None

        if spell is Spell.MIRROR_IMAGE:
            if target_is_monster:
                opponent_tier = MIRROR_IMAGE_MONSTER_INTELLIGENCE_TIER[monster_species]
                opponent_disbelief_bonus = 0.0
            else:
                # Confirmed by the user: a King/Hero opponent is always
                # High Human, plus a further +2%/Sage level + +1%/Illusion
                # level bonus on top of the table -- monster opponents
                # don't get this bonus.
                opponent_tier = MIRROR_IMAGE_LEADER_INTELLIGENCE_TIER_DEFAULT
                sage_level = effective_skill_level(state, leader, Ability.SAGE)
                illusion_level = effective_skill_level(state, leader, Ability.ILLUSION)
                opponent_disbelief_bonus = mirror_image_leader_disbelief_bonus(sage_level, illusion_level)
            # Phase 494: Detect Illusions (AdvancedAbility.DETECT_ILLUSIONS_
            # TALENT) belongs to whichever combatant is currently rolling to
            # disbelieve, not fixed to caster/opponent -- see resolve_mirror_
            # image_duel()'s own Phase 463 docstring. `leader` is the only
            # real LeaderState in a Search encounter (the other side is
            # always a monster, which can never hold an Advanced Ability),
            # so the bonus applies to whichever role `leader` is playing.
            leader_has_detect_illusions = AdvancedAbility.DETECT_ILLUSIONS_TALENT in leader.advanced_abilities
            duel_result = resolve_mirror_image_duel(
                caster,
                target,
                opponent_tier,
                level,
                rng,
                opponent_disbelief_bonus=opponent_disbelief_bonus,
                opponent_has_detect_illusions=(not caster_is_leader) and leader_has_detect_illusions,
                caster_has_detect_illusions=caster_is_leader and leader_has_detect_illusions,
            )
            if duel_result.winner == "a":
                # The caster disbelieves/slays their own illusion and
                # finishes off the already-mentally-slain opponent.
                return _outcome_from(EncounterCombatResult(winner=caster_slot, rounds=0))
            if duel_result.winner == "b":
                # The illusion kills the caster; the opponent "revives".
                return _outcome_from(EncounterCombatResult(winner=target_slot, rounds=0))
            return None

        if spell is Spell.ILLUS_HERO:
            hero = state.leaders.get(VALHALLA_VISITOR_LEADER_ID)
            if hero is None:
                # No confirmed rule for casting this with nobody currently
                # visiting Valhalla -- no effect, same "precondition can't
                # be met" convention as every other spell above.
                return None
            hero_combatant = _leader_combatant(state, hero)
            if target_is_monster:
                opponent_tier = MIRROR_IMAGE_MONSTER_INTELLIGENCE_TIER[monster_species]
                opponent_disbelief_bonus = 0.0
            else:
                opponent_tier = MIRROR_IMAGE_LEADER_INTELLIGENCE_TIER_DEFAULT
                sage_level = effective_skill_level(state, leader, Ability.SAGE)
                illusion_level = effective_skill_level(state, leader, Ability.ILLUSION)
                opponent_disbelief_bonus = mirror_image_leader_disbelief_bonus(sage_level, illusion_level)
            # "Unless the alignments of the illusion and the spellcaster
            # are implacably hostile" -- both alignments must be recorded
            # for the check to ever fire; unrecorded (None) defaults to
            # not-hostile, same as every other alignment gate above.
            turns_on_master = (
                hero.alignment is not None
                and leader.alignment is not None
                and illusory_hero_alignments_are_implacably_hostile(hero.alignment, leader.alignment)
            )
            # Phase 494: same Detect Illusions wiring as Mirror-Image above.
            leader_has_detect_illusions = AdvancedAbility.DETECT_ILLUSIONS_TALENT in leader.advanced_abilities
            duel_result = resolve_illusory_hero_duel(
                caster,
                target,
                hero_combatant,
                opponent_tier,
                level,
                rng,
                opponent_disbelief_bonus=opponent_disbelief_bonus,
                opponent_has_detect_illusions=(not caster_is_leader) and leader_has_detect_illusions,
                caster_has_detect_illusions=caster_is_leader and leader_has_detect_illusions,
                turns_on_master=turns_on_master,
            )
            if duel_result.winner == "a":
                return _outcome_from(EncounterCombatResult(winner=caster_slot, rounds=0))
            if duel_result.winner == "b":
                return _outcome_from(EncounterCombatResult(winner=target_slot, rounds=0))
            return None

        if spell is Spell.GATE_DEMON:
            # "A Demon may refuse to fight an opponent of Evil to Undead
            # alignment" -- the refusal roll is only even attempted
            # against an eligible opponent (Alignment.EVIL/ANTI_HOLY/
            # UNDEAD, ALIGNMENT_ORDINAL 5-7). A monster target has no
            # persisted alignment anywhere in this project (`models/
            # feature.py Feature` carries none) -- rolled fresh here via
            # `roll_monster_alignment()`, the same real, sourced
            # per-species distribution `models/monster.py` already uses
            # for world generation, rather than guessed or left unusable.
            target_alignment = (
                roll_monster_alignment(monster_species, rng) if target_is_monster else leader.alignment
            )
            opponent_eligible_for_refusal = (
                target_alignment is not None and ALIGNMENT_ORDINAL[target_alignment] >= ALIGNMENT_ORDINAL[Alignment.EVIL]
            )
            if opponent_eligible_for_refusal and resolve_gate_demon_refusal(rng):
                return None  # the gate opened, but the demon refused to fight
            demon_species = roll_gate_demon_type(rng)
            demon_stats = MONSTER_COMBAT_STATS.get(demon_species)
            if demon_stats is None:
                return None
            demon = Combatant(
                name=MONSTER_NAMES.get(demon_species, "demon"),
                hit_points=rng.randint(*demon_stats.hit_points_range),
                melee_skill=demon_stats.melee_skill,
                melee_damage_range=demon_stats.melee_damage,
                archery_skill=demon_stats.missile_skill,
                missile_damage_range=demon_stats.missile_damage
                if demon_stats.missile_damage is not None
                else FIRE_ARROW_DAMAGE_RANGE,
                is_undead_or_anti_holy=demon_species in (HAND_OF_DEATH_ANTI_HOLY_MONSTERS | SPIRITWRACK_UNDEAD_MONSTERS),
            )
            # "The Demon fights in place of the spellcaster" -- Melee
            # only, the same "mixed tactics/range transitions aren't
            # modeled" scope every duel in this module already carries
            # (`resolve_melee_duel`'s own docstring). The demon's own
            # spellcasting (real per the `SE3__T11.K1` worked example)
            # would need this same CAST-tactic engine recursively --
            # explicitly out of scope, the same "confirmed but not
            # modeled" stance `turn/encounter.py`'s own Phase 202
            # addendum already takes.
            # Phase 1052 bug fix -- threads the same skip_temper_setup/
            # melee_swings this function's own docstring addendum
            # describes, mirroring the identical fix on Kill Enemy's own
            # retaliation duel just above (and `turn/challenge_
            # execution.py`'s own "Phase 1042 bug fix" for this same
            # Gate Demon duel).
            duel_result = resolve_melee_duel(demon, target, rng, skip_temper_setup=melee_setup_done)
            melee_swings.extend(duel_result.melee_swings)
            if not melee_setup_done:
                melee_setup_done = True
            if duel_result.winner == "a":
                # GATE_DEMON_WINNER_RETURNS_TO_ABYSS -- the caster is
                # credited with the win, same as every other spell above.
                outcome = _outcome_from(EncounterCombatResult(winner=caster_slot, rounds=0))
                if outcome is not None:
                    outcome.melee_swings = tuple(melee_swings)
                return outcome
            # GATE_DEMON_LOSS_CASTER_RESUMES_FIGHT_AT_CURRENT_RANGE -- no
            # direct penalty on the caster; the plan simply continues.
            return None

        if spell is Spell.GATE_ANGEL:
            # Project-original (see GATE_ANGEL_KNOWN_ABILITY_LEVEL's own
            # docstring above): mirrors Gate Demon's own shape exactly,
            # but the combatant is the hero currently visiting Valhalla
            # (same "no hero currently visiting -> no effect" fetch
            # ILLUS_HERO above already uses) rather than a randomly
            # rolled demon, and there's no refusal roll (no stated
            # analog for an angel refusing anywhere in this spell's own
            # rule text).
            hero = state.leaders.get(VALHALLA_VISITOR_LEADER_ID)
            if hero is None:
                return None
            angel = _leader_combatant(state, hero)
            # "The Angel fights in place of the spellcaster" -- Melee
            # only, the same scope Gate Demon's own duel above carries.
            # Phase 1052 bug fix -- same skip_temper_setup/melee_swings
            # threading as Gate Demon's own duel just above (Gate Angel
            # is project-original, so there is no prior challenge_
            # execution.py fix to mirror here -- this gap was never
            # fixed anywhere until now).
            duel_result = resolve_melee_duel(angel, target, rng, skip_temper_setup=melee_setup_done)
            melee_swings.extend(duel_result.melee_swings)
            if not melee_setup_done:
                melee_setup_done = True
            if duel_result.winner == "a":
                # The caster is credited with the win, same as Gate
                # Demon's own win above.
                outcome = _outcome_from(EncounterCombatResult(winner=caster_slot, rounds=0))
                if outcome is not None:
                    outcome.melee_swings = tuple(melee_swings)
                return outcome
            # No direct penalty on the caster; the plan simply continues.
            return None

        if spell is Spell.LAVA_POOL:
            if target_is_monster and monster_species in LAVA_POOL_IMMUNE_MONSTERS:
                return None
            if target_is_monster:
                target_speed = MONSTER_COMBAT_STATS[monster_species].speed
            else:
                # Rulebook [5.6] (already quoted in `turn/encounter.py`'s
                # own module docstring): "medium-speed monsters OR OTHER
                # CHARACTERS is a 50-50 proposition" -- a character
                # target defaults to MEDIUM, the same tier the rulebook's
                # own Flee text already groups characters into.
                target_speed = MonsterSpeed.MEDIUM
            if resolve_lava_pool_escape(target_speed, rng):
                return None  # escaped
            # LAVA_POOL_KILLS_INSTANTLY -- a failed escape is a full kill.
            return _outcome_from(EncounterCombatResult(winner=caster_slot, rounds=0))

        if spell is Spell.AUGUR_COMBAT:
            if not caster_is_leader:
                # Never appears in any real `monster_encounter_plan.py`
                # species plan (the same "not reachable" situation
                # Illusory Hero's own docstring already documents), and
                # no monster has a `Temper` to shirk with -- a documented
                # no-effect, not a guess.
                return None
            if not is_first_tactic:
                # AUGUR_COMBAT_ACTS_AS_FLEE_WHEN_CAST_LATER -- "if it
                # comes later, then the result will be an attempt to
                # flee," reusing the exact real Flee mechanic
                # `Maneuver.FLEE` itself already uses (Phase 286: now
                # including that same mechanic's own flee-chance bonuses).
                flee_chance = effective_flee_chance(
                    FLEE_CHANCE[stats.speed], temper=leader.temper, is_invisible=caster.is_invisible,
                    has_melee_evasion=AdvancedAbility.MELEE_EVASION in leader.advanced_abilities,
                    has_air_elemental_familiar=_has_air_elemental_familiar(state, leader_id),
                )
                if rng.random() < flee_chance:
                    return _flee_outcome()
                return None
            if leader.temper is None:
                # No recorded Temper -- no basis to model the courage-
                # gated shirk roll, so (the same "insufficient data, no
                # effect" convention every spell above uses) nothing
                # happens.
                return None
            # "The computer will estimate the percentage chance of
            # victory, if combat were to occur" -- the user's own
            # clarification confirms this is a silent, binary outcome,
            # not a displayed percentage (module docstring's own Phase
            # 205 addendum). Modeled here as one real, throwaway
            # `resolve_melee_duel()` on cloned combatants -- reusing the
            # exact mechanic that would actually decide the encounter,
            # rather than inventing a separate estimator formula. The
            # clones are discarded after reading only the winner; the
            # real `caster`/`target` are untouched.
            simulated_caster = replace(caster)
            simulated_target = replace(target)
            simulated_result = resolve_melee_duel(simulated_caster, simulated_target, rng)
            would_lose_simulated_combat = simulated_result.winner == "b"
            if resolve_augur_combat(would_lose_simulated_combat, leader.temper, rng):
                return _flee_outcome()
            return None

        return None

    def _consume_bonus_attacks(attacker: Combatant, defender: Combatant, *, defender_is_monster: bool) -> SearchExecutionResult | None:
        """Phase 209: Psychic Blast's/Ice Suspension's own "bonus attack
        rounds" -- free, unanswered Melee swings, resolved immediately
        after the CAST tactic that granted them. Interpretation, not a
        literal citation: the source text says only "supplementary attack
        rounds," not Melee specifically -- Melee is the natural fit since
        each bonus swing is immediate, unlike Fire Arrow's own separate
        free-attack-count cycle. See module docstring's own Phase 209
        addendum.
        """

        # Phase 1053: hoisted out of the loop below -- neither side's
        # melee_skill/neutral_duelist_bonus changes across these bonus
        # swings, so effective_melee_skill() needs computing only once
        # per call, not once per bonus round.
        skill_difference_bonus = max(0, effective_melee_skill(attacker) - effective_melee_skill(defender))
        while attacker.bonus_unanswered_attacks > 0:
            attacker.bonus_unanswered_attacks -= 1
            damage = roll_melee_attack(
                rng,
                damage_range=attacker.melee_damage_range,
                hit_chance_multiplier=defender.defensive_hit_multiplier,
                skill_difference_bonus=skill_difference_bonus,
            )
            damage = max(0, damage - attacker.melee_damage_dealt_reduction)
            defender.hit_points -= damage
            if defender.hit_points <= 0:
                return _outcome_from(EncounterCombatResult(winner=("a" if defender_is_monster else "b"), rounds=0))
        return None

    def _resolve_cast(tactic, *, caster_is_leader: bool, is_first_tactic: bool = False) -> SearchExecutionResult | None:
        outcome = _resolve_cast_tactic(tactic, caster_is_leader=caster_is_leader, is_first_tactic=is_first_tactic)
        if outcome is not None:
            return outcome
        caster = leader_combatant if caster_is_leader else monster_combatant
        target = monster_combatant if caster_is_leader else leader_combatant
        return _consume_bonus_attacks(caster, target, defender_is_monster=caster_is_leader)

    def _resolve_use_mi_tactic(tactic) -> SearchExecutionResult | None:
        """Use_MI [UM], rulebook [5.1]/[3.11] -- Phase 274. ``tactic.sub_
        object`` is a magic-item-instance id (``search_decode.py``'s own
        docstring, sourced from ``DEF2.PAS``'s ``W_List`` -- the same
        opaque-id shape Phase 141's top-level Use_MI ACTION already reads
        via ``GameState.items``), looked up directly; a missing item, one
        this leader doesn't own, or one with no charges left is a
        documented no-effect (same "can't use what you don't have/it's
        empty" rejections Phase 141's own ``execute_use_mi()`` uses),
        never a guess at what the player meant.

        Only the 20 ``TreasureCategory.SPELL_WAND`` items are meaningful
        inside a personal Encounter -- the other 15 legitimate Use_MI
        targets (the skill books) "operate automatically" outside combat
        per [5.9] and have no Encounter-Plan role at all, so any other
        category is a documented no-effect here too (this tactic, unlike
        the top-level ACTION, never reads/mutates ``LeaderState.skills``).

        A wand's spell is dispatched through ``_resolve_cast_tactic()``
        itself (``forced_level=SEARCH_USE_MI_WAND_SKILL_LEVEL``, TREASAB.
        X2's own fixed "at skill-2" label) rather than duplicating any of
        its 16 Personal-Combat spell effects here -- this is the same
        "reuse the real dispatcher" precedent ``_resolve_monster_casts()``
        already established for the guardian's own CAST entries. A wand
        holding a spell outside those 16 (``cast_attempt_applied`` stays
        ``False``) is a documented no-effect, not a charge-consuming
        misfire -- nothing was actually cast. Charge consumption always
        follows ``cast_attempt_applied`` regardless of the spell's own
        success/failure, same rule as Phase 141's own charge rule ("spent
        only when the cast genuinely happens").

        A wand-cast miss (no terminal outcome, no free attacks landed)
        still spends the leader's own bonus-archery-attack budget for
        this tactic, same as an ordinary hand-cast spell falling through
        to ``_consume_bonus_attacks()`` in ``_resolve_cast()`` above.
        """

        item = state.items.get(tactic.sub_object)
        if item is None or item.owner_leader_id != leader_id:
            return None
        if TREASURE_CATEGORY.get(item.treasure) is not TreasureCategory.SPELL_WAND:
            return None
        if item.charges <= 0:
            return None

        spell = TREASURE_WAND_SPELL[item.treasure]
        synthetic_tactic = SearchTactic(maneuver=Maneuver.CAST, sub_object=spell.value)
        outcome = _resolve_cast_tactic(
            synthetic_tactic, caster_is_leader=True, is_first_tactic=False, forced_level=SEARCH_USE_MI_WAND_SKILL_LEVEL
        )
        if cast_attempt_applied:
            item.charges -= 1
        if outcome is not None:
            return outcome
        return _consume_bonus_attacks(leader_combatant, monster_combatant, defender_is_monster=True)

    def _peek_monster_action() -> SearchTactic | None:
        """Phase 293: peeks (without consuming) the guardian's own next
        Melee-range action from ``monster_plan`` starting at
        ``monster_tactic_index``, skipping any ``SHOOT`` entry (already
        resolved, if wanted at all, via the shared Fire Arrow phase
        earlier in the encounter -- ``monster_wants_shoot`` already
        checked the whole plan for one). Returns the next ``CAST``
        tactic (not yet consumed -- the caller advances the cursor via
        ``_advance_monster_tactic()`` once it's actually been resolved),
        or ``None`` once the guardian's own plan calls for Melee or has
        run out entirely -- "ME fino alla fine" (``models/monster_
        encounter_plan.py``'s own module docstring), read here as "keep
        answering Melee."
        """

        nonlocal monster_tactic_index
        plan = monster_plan or ()
        while monster_tactic_index < len(plan):
            current = plan[monster_tactic_index]
            if current.maneuver is Maneuver.SHOOT:
                monster_tactic_index += 1
                continue
            if current.maneuver is Maneuver.MELEE:
                return None
            if current.maneuver is Maneuver.CAST:
                return current
            monster_tactic_index += 1  # not a shape this data table ever uses -- skip defensively
        return None

    def _advance_monster_tactic() -> None:
        nonlocal monster_tactic_index
        if monster_plan is not None and monster_tactic_index < len(monster_plan):
            monster_tactic_index += 1

    def _is_summon_cast(tactic) -> bool:
        if tactic.maneuver is not Maneuver.CAST or tactic.sub_object is None:
            return False
        try:
            return Spell(tactic.sub_object) in SUMMON_SPELLS
        except ValueError:
            return False

    def _opponent_counters_summon(caster_is_leader: bool) -> Spell | None:
        """One side is summoning: if the other side's next queued tactic is a summon that also
        takes effect, both dissolve -- returns the other side's spell then."""

        nonlocal summon_probe_ready, cast_attempt_applied
        if caster_is_leader:
            pending = _peek_monster_action()
            if pending is None or not _is_summon_cast(pending):
                return None
            is_first = monster_tactic_index == 0
            _advance_monster_tactic()
        else:
            cursor = leader_tactic_cursor
            if (
                cursor >= len(request.tactics)
                or cursor in consumed_leader_tactics
                or not _is_summon_cast(request.tactics[cursor])
            ):
                return None
            pending = request.tactics[cursor]
            is_first = cursor == 0
            consumed_leader_tactics.add(cursor)
        applied_before = cast_attempt_applied
        summon_probe_ready = False
        _resolve_cast_tactic(
            pending, caster_is_leader=not caster_is_leader, is_first_tactic=is_first, summon_probe=True
        )
        ready, summon_probe_ready = summon_probe_ready, False
        cast_attempt_applied = applied_before
        return Spell(pending.sub_object) if ready else None

    def _monster_has_more_casts_pending() -> bool:
        """Phase 293: True if the guardian's own plan, from ``monster_
        tactic_index`` onward, contains any ``CAST`` tactic still to
        come -- even if its own *immediate* next action is Melee (e.g.
        Dryad's/Mermaid's own ``MELEE, MELEE, ..., CAST(Charm), MELEE``
        shape). Deciding whether the atomic fast path is safe needs this
        broader lookahead, not just ``_peek_monster_action()``'s own
        "what does it want to do this exact round" answer -- a guardian
        whose immediate next tactic is Melee can still have a real cast
        waiting a few rounds later.
        """

        return any(t.maneuver is Maneuver.CAST for t in (monster_plan or ())[monster_tactic_index:])

    monster_cast_resolved = False

    def _resolve_monster_casts() -> SearchExecutionResult | None:
        """Phase 178 (burst model) / **Phase 293 addendum**: resolves the
        guardian's own ``CAST`` tactics from ``monster_tactic_index``
        onward, stopping (without consuming) at its own first ``MELEE``
        tactic or once its plan runs out -- called once, before the
        first real combat phase (Fire Arrow or Melee) begins. Everything
        from that first ``MELEE`` tactic onward is now walked one round
        at a time by ``_resolve_melee_range_round()`` instead of being
        burst-resolved here too -- see module docstring's own Phase 293
        addendum for why (letting a guardian's own later ``CAST`` entry,
        e.g. Dryad's/Mermaid's own mid-plan Charm, actually fire only
        after the Melee rounds preceding it, rather than in the same
        upfront burst as everything else). For every guardian whose own
        plan has at most one trailing ``MELEE`` (the overwhelming
        majority), this produces byte-identical behavior to the old
        burst-everything model, since there was nothing after that
        ``MELEE`` to begin with.
        """

        nonlocal monster_cast_resolved
        if monster_cast_resolved:
            return None
        monster_cast_resolved = True
        while True:
            tactic = _peek_monster_action()
            if tactic is None:
                return None
            is_first_tactic = monster_tactic_index == 0
            outcome = _resolve_cast(tactic, caster_is_leader=False, is_first_tactic=is_first_tactic)
            _advance_monster_tactic()
            if outcome is not None:
                return outcome

    combat_attempted = False
    fire_arrow_resolved = False
    fire_arrow_shots: tuple[FireArrowShot, ...] = ()
    # Phase 415: accumulates across every round actually fought at melee
    # range in this tactic walk -- both the round-stepping path (`_resolve_
    # melee_range_round()`'s own Melee-vs-Melee branch, extended on EVERY
    # call, decisive or not) and the atomic `resolve_melee_duel()` fast
    # path (extended once, from the duel's own already-aggregated result),
    # mirroring `fire_arrow_shots`'s own accumulator pattern above.
    melee_swings: list[MeleeSwing] = []
    # Phase 858: see `turn/challenge_execution.py ChallengeCombatOutcome.
    # fizzled_spells`'s own docstring -- the identical, real, sourced
    # SBUNGLE.X "personal-combat Cast that just fizzles" trigger, wired
    # into this module's own leader-vs-monster Cast dispatch too (`if not
    # succeeded:` inside `_resolve_cast_tactic()` below).
    fizzled_spells: list[tuple[str, Spell]] = []
    hand_of_death_aborts: list[tuple[str, tuple[int, ...], int | None]] = []

    def _resolve_guardian_pacification() -> tuple[bool, bool]:
        """Phase 673 (``Desktop/BOLD OK.txt``): called once, whenever this
        encounter closes with the guardian still alive -- rolls the real
        per-packet intimidation formula (``turn/monster_raids.py roll_
        guardian_intimidation()``) against every Melee swing/Fire Arrow
        shot the leader landed on the monster this encounter, then (if
        not intimidated) checks the real ``_MUnDt`` "wounded but
        undeterred" precondition. Returns ``(intimidated, undeterred)``.
        Deliberately doesn't include spell-based damage (Fireball, Ice
        Suspension, Telekinetic Storm, Holy Symbol, Spiritwrack) as
        packets -- those spells resolve as outright kill-or-continue in
        this module's own combat model, never a discrete non-fatal
        damage number, so retrofitting them is a separate, larger
        follow-up, not attempted here.
        """

        combat_temper = MONSTER_RUNTIME_PROFILE[feature.guardian_monster].temper
        packets = [swing.damage for swing in melee_swings if swing.attacker == "a"]
        packets += [shot.damage for shot in fire_arrow_shots if shot.shooter == "a"]
        if roll_guardian_intimidation(feature, packets, combat_temper, rng):
            return True, False
        took_damage = monster_combatant.hit_points != monster_starting_hit_points
        return False, guardian_undeterred(feature, took_damage)

    def _flee_outcome() -> SearchExecutionResult:
        """Phase 1053: the shared "character flees/withdraws, encounter
        ends peacefully" terminal result -- Charm's forced-flee branch,
        both Augur Combat shirk branches, Beg's success branch, and the
        plan-level Flee tactic all reconstructed this identical
        ``SearchExecutionResult`` by hand; extracted once confirmed
        byte-identical across all five call sites.
        """

        intimidated, undeterred = _resolve_guardian_pacification()
        return SearchExecutionResult(
            accepted=True, combat_resolved=False, fled=True, guardian_intimidated=intimidated, guardian_undeterred=undeterred
        )

    def _finish_melee_outcome(combat_result: EncounterCombatResult) -> SearchExecutionResult:
        """Wraps ``_outcome_from()`` for a genuinely concluded Melee duel
        (winner always set, in every real call site below) and attaches
        the fire-arrow/guardian bookkeeping every terminal Melee outcome
        has always carried. ``_outcome_from()`` returning ``None`` (a
        winner-less draw -- only reachable via ``resolve_melee_duel()``'s
        own defensive ``max_rounds`` cap, astronomically unlikely in real
        play) still produces a real, honest ``winner=None`` result here,
        matching this module's own pre-Phase-293 fallback exactly.
        """

        outcome = _outcome_from(combat_result) or SearchExecutionResult(accepted=True, combat_resolved=True, winner=None)
        outcome.fire_arrow_shots = fire_arrow_shots
        outcome.melee_swings = tuple(melee_swings)
        outcome.fizzled_spells = tuple(fizzled_spells)
        outcome.hand_of_death_aborts = tuple(hand_of_death_aborts)
        outcome.guardian_monster = feature.guardian_monster
        return outcome

    def _resolve_melee_range_round(
        leader_tactic: SearchTactic, *, leader_tactic_index: int
    ) -> SearchExecutionResult | None:
        """Phase 293: one round of real combat once both sides are
        confirmed at ``CombatRange.MELEE_RANGE``. ``leader_tactic`` is
        the leader's own tactic driving this round (``Maneuver.CAST`` or
        ``Maneuver.MELEE`` only -- every other caller filters everything
        else). Peeks/advances the guardian's own cursor
        (``_peek_monster_action()``/``_advance_monster_tactic()``) for
        its own action this same round. Generalizes ``turn/challenge_
        execution.py``'s own Phase 292 CAST-at-melee-range disruption
        design to a genuinely bidirectional encounter -- unlike
        Challenge/Pursue's one-directional-target scoping, the guardian
        here has a real Encounter Plan of its own, so it can be the side
        disrupted too:

        - **Melee vs Melee**: an ordinary mutual ``resolve_one_melee_
          round()``.
        - **Melee vs Cast**: the melee side's own swing is the *other*
          side's reactive attack (``resolve_reactive_melee_swing()``) --
          a landed hit rolls ``resolve_spell_disruption()`` against the
          actual damage; a miss rolls ``resolve_spell_disruption_from_
          missed_attack()``'s own flat 30% instead. A disrupted cast
          never reaches ``_resolve_cast()`` at all ("the caster loses a
          turn"). **Phase 416**: this swing is now also appended to the
          nonlocal ``melee_swings`` accumulator (as a real ``MeleeSwing``,
          reading ``.hit``/``.damage`` off ``resolve_reactive_melee_
          swing()``'s own ``ReactiveMeleeSwingResult``) -- disruption
          itself is unchanged, still keyed off ``.damage > 0`` exactly as
          before, not ``.hit`` (a reduced-to-zero hit still disrupts
          nothing, the same pre-existing behavior Phase 416 doesn't
          touch).
        - **Cast vs Cast**: both sides attempt their own cast, no
          swings, no disruption check (neither side is attacking this
          round).

        Returns a terminal ``SearchExecutionResult`` on a decisive kill/
        flee, or ``None`` once the round ends without one (the walk
        continues).
        """

        nonlocal melee_setup_done
        if not melee_setup_done:
            apply_temper_melee_setup(leader_combatant, monster_combatant, rng)
            melee_setup_done = True

        monster_tactic = _peek_monster_action()

        if leader_tactic.maneuver is Maneuver.MELEE and monster_tactic is None:
            round_outcome = resolve_one_melee_round(leader_combatant, monster_combatant, rng)
            melee_swings.extend(round_outcome.swings)
            # This Melee entry in the guardian's own plan has now been
            # "used" for this round -- advance past it so a later CAST
            # further down its plan (e.g. Dryad's/Mermaid's own trailing
            # Charm) is eventually reached instead of the peek landing on
            # this same Melee entry forever. Safe even when this genuinely
            # is the guardian's own last tactic: advancing past it just
            # moves from "at the last index" to "past the end," which
            # `_peek_monster_action()` already reads identically ("ME
            # fino alla fine").
            _advance_monster_tactic()
            return _finish_melee_outcome(round_outcome.result) if round_outcome.result is not None else None

        if leader_tactic.maneuver is Maneuver.MELEE:
            # Phase 1052 bug fix -- mirrors `turn/challenge_execution.py`'s
            # own identical "Phase 1042 bug fix": a guardian already
            # blocked_from_cast (e.g. by an earlier Spiritwrack/Hand of
            # Death) has a guaranteed no-op CAST coming, but this branch
            # used to give the leader a full reactive swing anyway --
            # which could even kill the already-harmless-casting
            # guardian outright -- before that guaranteed no-op was ever
            # discovered.
            if not monster_combatant.blocked_from_cast:
                swing_result = resolve_reactive_melee_swing(leader_combatant, monster_combatant, rng)
                damage = swing_result.damage
                melee_swings.append(_melee_swing_from_reactive("a", swing_result))
                if monster_combatant.hit_points <= 0:
                    return _finish_melee_outcome(EncounterCombatResult(winner="a", rounds=0))
                disrupted = _resolve_cast_disruption(monster_tactic, damage, rng)
            else:
                disrupted = False
            is_first_tactic = monster_tactic_index == 0
            _advance_monster_tactic()
            if disrupted:
                return None
            return _resolve_cast(monster_tactic, caster_is_leader=False, is_first_tactic=is_first_tactic)

        # leader_tactic.maneuver is Maneuver.CAST from here on
        if monster_tactic is None:
            # Phase 1052 bug fix -- symmetric guard to the Melee-vs-Cast
            # branch above: a leader already blocked_from_cast has a
            # guaranteed no-op CAST coming, so the guardian's own
            # reactive swing (which could kill the leader outright) is
            # skipped instead of landing before that no-op is discovered.
            if not leader_combatant.blocked_from_cast:
                swing_result = resolve_reactive_melee_swing(monster_combatant, leader_combatant, rng)
                damage = swing_result.damage
                melee_swings.append(_melee_swing_from_reactive("b", swing_result))
                if leader_combatant.hit_points <= 0:
                    return _finish_melee_outcome(EncounterCombatResult(winner="b", rounds=0))
                disrupted = _resolve_cast_disruption(leader_tactic, damage, rng)
            else:
                disrupted = False
            _advance_monster_tactic()  # this Melee entry has now been "used" too -- see the Melee-vs-Melee branch above
            if disrupted:
                return None
            return _resolve_cast(leader_tactic, caster_is_leader=True, is_first_tactic=(leader_tactic_index == 0))

        outcome = _resolve_cast(leader_tactic, caster_is_leader=True, is_first_tactic=(leader_tactic_index == 0))
        if outcome is not None:
            return outcome
        is_first_tactic = monster_tactic_index == 0
        _advance_monster_tactic()
        return _resolve_cast(monster_tactic, caster_is_leader=False, is_first_tactic=is_first_tactic)

    def _resolve_fire_arrow_phase(
        *, long_range_archer: str | None = None, short_range_archer: str | None = None
    ) -> SearchExecutionResult | None:
        nonlocal fire_arrow_shots, fire_arrow_resolved
        fire_arrow_resolved = True
        outcome = _resolve_monster_casts()
        if outcome is not None:
            return outcome
        # long_range_archer/short_range_archer are only ever passed when
        # a real ability applies (both `None` otherwise) -- matches
        # turn/challenge_execution.py's own Phase 700/701 convention of
        # calling resolve_fire_arrow_duel() with no such kwarg at all in
        # the ordinary case, keeping every pre-Phase-719 call/mock byte-
        # for-byte identical.
        kwargs: dict[str, str] = {}
        if long_range_archer is not None:
            kwargs["long_range_archer"] = long_range_archer
        if short_range_archer is not None:
            kwargs["short_range_archer"] = short_range_archer
        duel_result = resolve_fire_arrow_duel(leader_combatant, monster_combatant, rng, **kwargs)
        fire_arrow_shots = duel_result.shots
        outcome = _outcome_from(duel_result)
        if outcome is not None:
            outcome.fire_arrow_shots = fire_arrow_shots
            outcome.fizzled_spells = tuple(fizzled_spells)
            outcome.hand_of_death_aborts = tuple(hand_of_death_aborts)
            outcome.guardian_monster = feature.guardian_monster
        return outcome

    def _resolve_steal() -> SearchExecutionResult | None:
        """Steal [ST], rulebook [5.4] -- Phase 239, superseded by Phase 506
        with the real disassembly-sourced formula (``turn/encounter.py``'s
        own Phase 506 addendum has the full formula and its source).
        Search's target is always the guardian monster, never a King/
        Hero, so only one of the rulebook's three caught-thief
        consequences ever applies here: "si ha un combattimento
        individuale, a una distanza scelta a caso" (personal combat at a
        random range) -- and no ``target_leads_army_or_is_king`` halving
        either, since a guardian monster never commands an army or is a
        King in this project's model.

        Two separate rolls, in the real formula's own order: the success
        roll (``resolve_steal_attempt()``) is monster-intelligence-blind;
        only *after* it succeeds does a second, intelligence-based roll
        (``resolve_steal_monster_item_transfer()``) decide whether an
        item actually transfers.

        **Phase 731**: a failed item-transfer roll is *not* a no-effect
        (this project's own guardian monsters never hold an
        ``ItemInstance`` at all, so the roll can never really "find" an
        item either way) -- ``turn/encounter.py``'s own ``MONSTER_
        STEAL_GOLD_IF_NO_ITEM`` addendum (``CTME.PAS``'s real basegold
        table via ``AK.EXE``'s ``G_MSteal``) confirms this branch always
        grants a real, sourced gold consolation instead, credited to the
        thief's own Kingdom treasury (a kingdomless Hero has nowhere to
        credit it -- a documented no-op, matching every other gold-gain
        mechanic in this project, e.g. ``THIEF_TREASURY_RAIDS``/Practice
        Make Gems). Per ``turn/merit_points.py thiefprince_merit_
        points()``'s own Phase 369 addendum ("+1 per successful theft
        result... no distinction between gold and item stolen"), both
        outcomes below are equally real "successful theft results" and
        credit the Prince of Thieves merit point and the real
        ``Add_Experience`` credit identically -- neither branch actually
        hands the leader a real item object either way (no ``state.
        add_item(...)`` call on either path), so gold-vs-item was never
        more than which loot bucket applies. The gold branch still
        doesn't end the encounter or loot the feature's own separate
        ``treasure`` (``_outcome_from()``'s own side effect) -- that
        stays scoped to a real combat win, unchanged.
        """

        nonlocal combat_attempted
        level = effective_skill_level(state, leader, Ability.THIEF)
        has_thief_mastery = bool(leader.advanced_abilities & STEAL_THIEF_MASTERY_ABILITIES)
        has_enhanced_invisibility = AdvancedAbility.ENHANCED_INVISIBILITY in leader.advanced_abilities
        if resolve_steal_attempt(
            level,
            rng,
            has_thief_mastery=has_thief_mastery,
            is_invisible=leader_combatant.is_invisible,
            has_enhanced_invisibility=has_enhanced_invisibility,
            target_leads_army_or_is_king=False,
        ):
            intelligence_ordinal = MONSTER_INTELLIGENCE_ORDINAL[MONSTER_RUNTIME_PROFILE[feature.guardian_monster].intelligence]
            item_transferred = resolve_steal_monster_item_transfer(intelligence_ordinal, 0, rng)
            # Phase 442 / Phase 731: one of the real compiled formula's
            # own "two separate success paths that award the [Prince of
            # Thieves] point" (turn/merit_points.py thiefprince_merit_
            # points()'s own Phase 369 addendum) -- this one, Search's
            # own Steal against a guarded feature's hoard, credited
            # identically regardless of whether the item-transfer roll
            # below passes or fails (see this function's own docstring).
            leader.merit_tally.successful_thefts += 1
            # Phase 457: the same real Add_Experience credit (base 15,
            # AKGEN_reverse_engineering_report (2).md SS3.3's own Thief
            # row) turn/challenge_execution.py _apply_successful_theft()
            # awards for the character-vs-character Steal path -- see
            # that function's own Phase 457 addendum for why this and
            # that are the two real "qualifying theft event" triggers.
            add_experience(leader, Ability.THIEF, 15, rng)
            if not item_transferred:
                gold = MONSTER_STEAL_GOLD_IF_NO_ITEM.get(feature.guardian_monster, 0)
                if leader.kingdom_id is not None:
                    state.kingdoms[leader.kingdom_id].treasury += gold
                return None  # gold taken, but the feature itself isn't looted -- plan continues
            return _outcome_from(EncounterCombatResult(winner="a", rounds=0))
        if resolve_steal_evasion(level, rng):
            return None  # failed, but not caught -- plan continues
        # Caught. Spell range has no resolvable outcome (no spell-effect
        # system exists anywhere in this project) -- a documented
        # no-effect, not a silent substitution for one of the other two
        # ranges, the same "unresolvable roll outcome, no guess"
        # convention `_resolve_cast_tactic()`'s own AUGUR_COMBAT branch
        # already uses above.
        combat_range = rng.choice((CombatRange.SPELL_RANGE, CombatRange.BOW_RANGE, CombatRange.MELEE_RANGE))
        if combat_range is CombatRange.SPELL_RANGE:
            return None
        combat_attempted = True
        outcome = _resolve_monster_casts()
        if outcome is not None:
            return outcome
        if combat_range is CombatRange.MELEE_RANGE:
            melee_duel_result = resolve_melee_duel(leader_combatant, monster_combatant, rng, skip_temper_setup=melee_setup_done)
            melee_swings.extend(melee_duel_result.melee_swings)
            outcome = _outcome_from(melee_duel_result)
            if outcome is not None:
                outcome.melee_swings = tuple(melee_swings)
                outcome.fizzled_spells = tuple(fizzled_spells)
                outcome.hand_of_death_aborts = tuple(hand_of_death_aborts)
                outcome.guardian_monster = feature.guardian_monster
            return outcome
        # Phase 1052 bug fix: this used to call resolve_fire_arrow_duel()
        # directly, bypassing _resolve_fire_arrow_phase() entirely, so it
        # never set fire_arrow_resolved=True -- an inconclusive duel here
        # left the later `monster_wants_shoot and not fire_arrow_resolved`
        # guard still True, firing a second, independent Fire Arrow phase
        # for a `monster_wants_shoot` guardian (e.g. Titan/Red Dragon)
        # later in the same encounter, violating this module's own
        # documented "at most one Fire Arrow phase per encounter"
        # invariant (Phase 178 addendum). Also merges into the nonlocal
        # `fire_arrow_shots` accumulator, same as `_resolve_fire_arrow_
        # phase()` itself does, so an inconclusive duel's shots aren't
        # lost from `_resolve_guardian_pacification()`'s own intimidation-
        # packet accounting or from a later `_finish_melee_outcome()`.
        nonlocal fire_arrow_resolved, fire_arrow_shots
        fire_arrow_resolved = True
        duel_result = resolve_fire_arrow_duel(leader_combatant, monster_combatant, rng)
        fire_arrow_shots = duel_result.shots
        outcome = _outcome_from(duel_result)
        if outcome is not None:
            outcome.fire_arrow_shots = fire_arrow_shots
            outcome.fizzled_spells = tuple(fizzled_spells)
            outcome.hand_of_death_aborts = tuple(hand_of_death_aborts)
            outcome.guardian_monster = feature.guardian_monster
        return outcome

    def _resolve_talk() -> SearchExecutionResult | None:
        """Talk [TA], rulebook [5.5] -- Phase 240, **superseded by Phase 528**
        with the real 24-reply selector (``turn/encounter.py``'s own
        Phase 382 addendum has the full sourcing: ``MonsterTalkReply``,
        ``MONSTER_TALK_REPLY_OUTCOME``), **and again by Phase 727** (see
        that addendum below -- the reply is now resolved via ``turn/
        monster_raids.py resolve_monster_raid_reply()``, the real,
        disassembly-verified algorithm, not ``turn/encounter.py select_
        monster_talk_reply()``'s own less-accurate approximation).
        If the leader's own Druid skill doesn't meet the guardian's own
        ``talkdiff`` requirement, no effect -- the character simply can't
        communicate with this species (unchanged from Phase 240).

        **Phase 528 addendum -- the real reply selector, wired in.**
        ``AKGEN_reverse_engineering_report (3).md`` SS60-72 (the TALK
        dossier) confirms the old placeholder's own project-original
        Attack/Ignore/Deal split (``resolve_talk_reaction()``, Phase 240)
        was never the real mechanism, and that a Druidic caster's own
        "more inclined to help" bonus -- the rulebook quote the old
        formula built its Druidic split around -- is itself "a designed
        but absent/disabled rule" in the real compiled build (SS70: "non
        e' collegata... a uno stato letto dalla routine di assistenza"),
        not a hidden percentage this project should keep approximating.
        ``resolve_talk_reaction()``/``TalkReaction`` stay defined in
        ``turn/encounter.py`` (their own tests are untouched, and no
        other production call site exists) but are no longer called from
        here.

        The real selector generates one of 24 replies **once per
        guardian, not once per Talk attempt** (SS62: "per la stessa
        feature e lo stesso guardiano la risposta e normalmente
        ripetibile") -- persisted on ``Feature.guardian_talk_reply_id``.
        Each reply's own ``TalkReplyOutcome`` category (``MONSTER_TALK_
        REPLY_OUTCOME``) then drives exactly the old three-way branch's
        own shape: ``ATTACK`` (``RCharge``/``RMAdvance``) forces combat
        unless Silver Tongue suppresses it (unchanged Phase 468
        behavior, just re-anchored to the real reply instead of a raw
        roll); ``IGNORE`` (``RPuzzled``/``RWarn``) is a no-op, same as
        before; ``QUEST_OR_AGREEMENT`` (the other 20) sets ``pending_
        deal_leader_id`` exactly like the old ``DEAL`` branch did -- this
        project still doesn't model each Quest's own distinct completion
        condition (Phase 258's own scope note), only which of the three
        real outcome categories fires.

        **Phase 727 addendum -- the real, deterministic selector, wired
        in.** ``turn/monster_raids.py resolve_monster_raid_reply()``
        (Phase 679, ``Desktop/NOARMY.md``'s own disassembly of `Get_
        Reply`) is a *more* accurate port of this exact same real
        algorithm than ``turn/encounter.py select_monster_talk_reply()``
        (Phase 382/528, used here until now) ever was, in three real
        ways this phase closes: (a) it's fully deterministic per
        ``(monster, feature_id)`` -- reseeding a self-contained
        generator rather than drawing from the turn's own live, shared
        ``rng`` -- matching the real engine's own save/reseed/restore
        behavior around this call, and matching how ``Feature.guardian_
        talk_reply_id``'s own persistence *already* assumed a real reply
        is stable per guardian, not merely cached for convenience; (b)
        it walks the real per-feature ``Agent_Align``-derived effective
        alignment (fixed in Phase 726) rather than the monster's own
        static ``base_view``; (c) it derives ``has_purchasable_treasure``
        for real from ``Feature.treasure`` (``feature_treasure.value <
        67``, ``Treasure.GOLD_HOARD_LARGE``) instead of the previous
        hardcoded ``False`` -- that hardcoding's own justification ("no
        concept of a purchasable item anywhere in this project's model")
        was stale the moment Phase 679 built exactly this derivation for
        the raid path; ``RSell`` is now genuinely reachable here. User-
        confirmed directly (2026-09-03): the resulting loss of one live-
        ``rng`` draw from this dispatch path is the correct trade for
        real-algorithm accuracy, not a regression -- every real test
        exercising this call site already mocks the reply selector
        outright (never scripts a real roll for it), so no test needed
        its own ``rng`` sequence re-counted.
        """

        nonlocal combat_attempted

        # Phase 537: AKGEN_reverse_engineering_report (4).md SS9 -- holding
        # the racial-command item matching this guardian's own Dragon/
        # Eagle/Whale family skips the normal social roll entirely ("non
        # effettua il tiro sociale normale: il mostro consegna il tesoro
        # e non si apre il combattimento"). A wholly separate mechanism
        # from Druidic Talk (the event is `_LMCharm`, "used the item to
        # command the monster," not the real Charm spell) -- no Druid
        # skill/`talkdiff` gate, no roll consumed, and (undocumented by
        # any source) no merit-tally credit either, since this isn't a
        # combat win or a negotiated Fulfill.
        if holds_monster_command_item_for(state, leader_id, feature.guardian_monster):
            feature.looted = True
            if feature.treasure is not None:
                _grant_search_treasure(state, leader_id, feature.treasure)
            return SearchExecutionResult(accepted=True, combat_resolved=False, winner="leader", feature_looted=True)

        druid_level = effective_skill_level(state, leader, Ability.DRUID)
        if not can_talk_to_monster(feature.guardian_monster, druid_level):
            return None
        # Phase 459: AKGEN_reverse_engineering_report (2).md SS3.3's own
        # Druid row (base 10, "evento druidico qualificante") -- SS3.4
        # names the real trigger explicitly: "interazioni druidiche con
        # creature/mostri" (druidic interactions with creatures/
        # monsters). The DR gate just passed *is* that interaction --
        # the leader's own Druid skill was what let them communicate
        # with this guardian at all -- so this fires regardless of which
        # reply follows.
        award_talk_experience(state, leader, feature.feature_id)

        if feature.guardian_talk_reply_id is None:
            reply = resolve_monster_raid_reply(feature.guardian_monster, feature.feature_id, feature.treasure)
            feature.guardian_talk_reply_id = reply.value
        reply = MonsterTalkReply(feature.guardian_talk_reply_id)

        outcome_category = MONSTER_TALK_REPLY_OUTCOME[reply]
        if outcome_category is TalkReplyOutcome.ATTACK:
            silver_tongue_holder = resolve_office_holder(state, Office.DIPLOMAT)
            caster_is_silver_tongue = silver_tongue_holder is not None and silver_tongue_holder.leader_id == leader_id
            if caster_is_silver_tongue:
                return None  # suppressed -- no special effect, not converted to a deal
            combat_attempted = True
            return None  # combat continues via the next tactic, or the tail's default-to-Melee
        if outcome_category is TalkReplyOutcome.IGNORE:
            return None
        feature.pending_deal_leader_id = leader_id
        # 2026-11-20 bug fix, user-confirmed via a deep audit:
        # Office.PSYCHIC_MAGE's own "senses whether the monster intends
        # to keep its end of the bargain" perk. Rolls the *same* real
        # honor-outcome Fulfill would otherwise roll later, now instead
        # of then, and persists it for Fulfill to consume -- see
        # Feature.psychic_mage_sensed_fulfill_honor's own docstring for
        # why this isn't a second, independent roll.
        sensed_fulfill_honor = None
        psychic_mage_holder = resolve_office_holder(state, Office.PSYCHIC_MAGE)
        if psychic_mage_holder is not None and psychic_mage_holder.leader_id == leader_id:
            silver_tongue_holder = resolve_office_holder(state, Office.DIPLOMAT)
            caster_is_silver_tongue = silver_tongue_holder is not None and silver_tongue_holder.leader_id == leader_id
            sensed_fulfill_honor = resolve_fulfill_honored(
                feature.guardian_alignment, leader.alignment, rng, caster_is_silver_tongue=caster_is_silver_tongue
            )
            feature.psychic_mage_sensed_fulfill_honor = sensed_fulfill_honor
        intimidated, undeterred = _resolve_guardian_pacification()
        guardian_riddle = (
            _select_guardian_riddle(feature.guardian_monster, feature.feature_id) if reply is MonsterTalkReply.R_RIDDLE else None
        )
        guardian_quest_location = (
            _select_guardian_quest_location(feature.guardian_monster, feature.feature_id)
            if reply is MonsterTalkReply.R_VISIT
            else None
        )
        return SearchExecutionResult(
            accepted=True,
            combat_resolved=False,
            reason="the guardian proposes a deal -- honor it with Fulfill on a later Search",
            guardian_intimidated=intimidated,
            guardian_undeterred=undeterred,
            guardian_riddle=guardian_riddle,
            guardian_quest_location=guardian_quest_location,
            guardian_monster=feature.guardian_monster,
            sensed_fulfill_honor=sensed_fulfill_honor,
            guardian_talk_reply=reply,
            guardian_talk_treasure=feature.treasure,
            guardian_talk_coord=feature.coord,
        )

    def _resolve_fulfill() -> SearchExecutionResult | None:
        """Fulfill [FU], rulebook [5.7] -- Phase 258. Honors a deal a prior
        turn's Talk secured on this feature (``Feature.pending_deal_
        leader_id``) -- no effect if this leader holds no pending deal
        here. The attempt (success or failure) always consumes the
        pending flag -- rulebook [5.6]'s own "Talk and Fulfill can't both
        be used in the same Encounter Plan" reads as a one-shot honor
        attempt, not a repeatable check. See ``turn/encounter.py resolve_
        fulfill_honored()``'s own module comment for the honor-roll
        formula and its sourcing.

        Success ends the Search peacefully -- the guardian is neutralized
        via negotiation, not killed, so ``monster_hp_neutralized`` (the
        rulebook's own "metà dei punti se neutralizzato con trattative"
        half-credit) is credited instead of ``monster_hp_defeated``, and
        no treasure is granted -- unlike a combat win, nothing in the
        available source ties Fulfill's own success to looting the
        feature. Failure leaves the encounter unresolved; the plan
        continues to its next tactic, no combat forced.

        **Phase 301 fix**: credits the *raw*, unhalved
        ``monster_starting_hit_points`` -- ``MeritTally.monster_hp_
        neutralized``'s own docstring (``models/game_state.py``) and
        ``turn/merit_points.py``'s own module docstring both document
        this field as a raw count, with the negotiated half-credit
        applied once, by ``defender_merit_points()`` itself. This
        function used to pre-halve the value here too, so a negotiated
        neutralization ended up quartered (halved twice) by the time
        ``defender_merit_points()`` read it -- a real bug found in a
        dedicated bug-hunt audit, confirmed by tracing both the writer
        and reader together (each had its own test validating only its
        own half of the pipeline).
        """

        if feature.pending_deal_leader_id != leader_id:
            return None
        feature.pending_deal_leader_id = None
        # 2026-11-20 bug fix: if Talk's own Psychic Mage sensing already
        # rolled this exact deal's real honor outcome (see Feature.
        # psychic_mage_sensed_fulfill_honor's own docstring), reuse it
        # rather than rolling a second, independent one that could
        # disagree with what was sensed.
        sensed_fulfill_honor = feature.psychic_mage_sensed_fulfill_honor
        feature.psychic_mage_sensed_fulfill_honor = None
        # Phase 468: Silver Tongue (Office.DIPLOMAT) always honors a
        # completed deal -- report SS18.4's own "onora sempre un accordo
        # completato".
        silver_tongue_holder = resolve_office_holder(state, Office.DIPLOMAT)
        caster_is_silver_tongue = silver_tongue_holder is not None and silver_tongue_holder.leader_id == leader_id
        honored = (
            sensed_fulfill_honor
            if sensed_fulfill_honor is not None
            else resolve_fulfill_honored(
                feature.guardian_alignment, leader.alignment, rng, caster_is_silver_tongue=caster_is_silver_tongue
            )
        )
        if honored:
            leader.merit_tally.monster_hp_neutralized += monster_starting_hit_points
            # Phase 671: THUNDERBIRD.md section 4.2's own compiled
            # pacification snippet -- see turn/monster_raids.py apply_
            # fulfill_pacification()'s own docstring for why this applies
            # to any honored deal, not a narrower "stop raiding" one.
            pacified = apply_fulfill_pacification(feature)
            return SearchExecutionResult(
                accepted=True, combat_resolved=False, winner="leader", guardian_pacified_by_fulfill=pacified
            )
        return None  # not honored -- the plan continues to its next tactic

    def _resolve_give_tactic(tactic: SearchTactic) -> SearchExecutionResult | None:
        """Give [GI] inside a Search Encounter Plan -- Phase 734,
        ``AdvancedAbility.DRUIDIC_TRADES``'s own real text (``models/
        advanced_ability.py``): "The Druid can trade any magic item he
        possesses for one treasure held by a monster occupying a
        feature. This is done by just using the 'GI-ve' order. If there
        is a specific treasure number you want to trade for, just use
        the 'Say' tactic to say the item number." ``tactic.sub_object``
        is the offered item's own id -- ``turn/search_decode.py``'s own
        confirmed "gift-item id" reading, the same ``TACTICS_WITH_SUB_
        OBJECT`` shape ``CAST``/``USE_MI`` already use. ``Maneuver.GIVE``
        itself has carried this exact wire format since the original
        decode (Phase 46-ish) with zero dispatch anywhere until now --
        confirmed the *only* real sourced use of it inside a Search plan
        (an earlier docstring paragraph right below this function's own
        call site used to call Give "structurally inapplicable" to a
        monster target -- stale, corrected here).

        A trailing ``SAY`` tactic anywhere in the plan may name a
        specific treasure number the Druid wants in return (reuses
        ``parse_sa_argument()``, Phase 619, the same "SA-y the number"
        primitive Oracle/Recharge/Grant Wish/Gamble already use). This
        project's own ``Feature`` model holds only one real ``treasure``
        at a time -- no multi-item hoard concept anywhere (confirmed
        during the Phase 731 Steal investigation: monsters hold no
        ``ItemInstance`` at all in this project's model either) -- so a
        stated number that doesn't match the feature's own real treasure
        refuses the whole trade outright (user-confirmed directly),
        rather than silently substituting whatever treasure is really
        there.

        A documented no-effect whenever any precondition fails -- no
        ability, no live guardian/real treasure to trade for, no real
        item owned by this leader, or a stated-but-mismatched treasure
        number -- nothing in the source describes a caught-cheater
        consequence for a failed trade attempt, unlike Steal. On
        success: the given item is destroyed outright (``state.remove_
        item()`` -- a monster never actually holds it, matching the
        Phase 731 "monsters hold no items" finding), the feature's own
        treasure is granted via the same ``_grant_search_treasure()``
        primitive a combat win already uses, and the feature's own
        ``treasure`` is cleared (user-confirmed: the monster has now
        given up its one and only treasure, not re-tradeable or re-
        lootable afterward). No sourced report text survives for either
        outcome (checked ``AKPROSE_reverse_engineering_report.md``
        directly -- only the ability's own description text itself
        matches) -- the mechanism is silent, matching this project's own
        established "mechanism now, narration only when sourced"
        convention.
        """

        if AdvancedAbility.DRUIDIC_TRADES not in leader.advanced_abilities:
            return None
        if feature.guardian_monster is None or feature.looted or feature.treasure is None:
            return None
        item = state.items.get(tactic.sub_object) if tactic.sub_object is not None else None
        if item is None or item.owner_leader_id != leader_id:
            return None
        say_tactic = next((t for t in request.tactics if t.maneuver is Maneuver.SAY), None)
        if say_tactic is not None and say_tactic.say_text:
            requested_treasure = parse_sa_argument(say_tactic.say_text)
            if requested_treasure is not None and requested_treasure != feature.treasure.value:
                return None  # asked for a specific treasure the monster doesn't have
        state.remove_item(item.item_id)
        _grant_search_treasure(state, leader_id, feature.treasure)
        feature.treasure = None
        return None  # peaceful -- the plan continues to its next tactic

    def _resolve_beg() -> SearchExecutionResult | None:
        """Beg [BE] -- ``Desktop/SE+SC.md`` SS40/43 (Phase 749) supersedes
        the old Phase 241 project-original framing: a real, disassembled
        mercy formula now exists, keyed on the guardian's own ``Alignment``
        (``Feature.guardian_alignment``) vs. the begging leader's own
        (``LeaderState.alignment``), not monster intelligence -- see
        ``turn/encounter.py resolve_beg_for_mercy()``'s own docstring for
        the formula and its worked-example cross-check. Only meaningful
        once the leader has already taken damage this same encounter
        (``leader_combatant.hit_points`` below the leader's own real
        starting hit points -- an undamaged leader has nothing to beg
        about, a documented no-effect rather than an oversight); this
        precondition is untouched by the new document, which is silent
        on Beg's own availability gate. A successful plea ends the
        Search exactly like a successful Flee (independently
        reconfirmed by SS40/43).

        **Phase 1052 bug fix**: the "undamaged" check used to compare
        against the bare ``CHARACTER_HIT_POINTS`` constant, on the
        premise that "every combatant starts at the flat rulebook
        value." That premise is false whenever ``arcane_valor_hit_
        points_bonus()`` is nonzero (``GameType.ARCANES``, a Scepter-
        of-Life-benefiting leader) -- ``_leader_combatant()`` seeds such
        a leader's real starting hit points above the bare constant, so
        a leader who has genuinely taken some damage (but whose current
        HP is still >= the bare constant, because their real starting
        HP was higher) was wrongly treated as undamaged, silently
        making Beg do nothing. Now compares against the same real
        starting-HP total ``_apply_monster_duel_merit()``'s own Bravest-
        of-the-Brave credit (also fixed at Phase 1052) uses.
        """

        starting_hit_points = CHARACTER_HIT_POINTS + arcane_valor_hit_points_bonus(state, leader)
        if leader_combatant.hit_points >= starting_hit_points:
            return None  # undamaged -- nothing to beg about yet
        if resolve_beg_for_mercy(feature.guardian_alignment, leader.alignment, rng):
            return _flee_outcome()
        return None

    for tactic_index, tactic in enumerate(request.tactics):
        if tactic_index in consumed_leader_tactics:
            continue  # dissolved together with the guardian's own summon
        leader_tactic_cursor = tactic_index + 1
        if tactic.maneuver is Maneuver.FLEE:
            flee_chance = effective_flee_chance(
                FLEE_CHANCE[stats.speed], temper=leader.temper, is_invisible=leader_combatant.is_invisible,
                has_melee_evasion=AdvancedAbility.MELEE_EVASION in leader.advanced_abilities,
                has_air_elemental_familiar=_has_air_elemental_familiar(state, leader_id),
            )
            if rng.random() < flee_chance:
                return _flee_outcome()
            continue
        if tactic.maneuver is Maneuver.CAST:
            if current_range is CombatRange.MELEE_RANGE:
                # Phase 293: once real Melee is underway, a CAST tactic is
                # one round of the round engine below (the guardian's own
                # reactive swing can disrupt it), not an unconditional cast.
                outcome = _resolve_melee_range_round(tactic, leader_tactic_index=tactic_index)
                if outcome is not None:
                    return outcome
                continue
            outcome = _resolve_cast(tactic, caster_is_leader=True, is_first_tactic=(tactic_index == 0))
            if outcome is not None:
                return outcome
            continue
        if tactic.maneuver is Maneuver.SHOOT:
            if current_range is CombatRange.MELEE_RANGE:
                # Phase 719: AdvancedAbility.SHORT_RANGE_ARCHERY -- "may
                # now use the Fire tactic at Melee Range, with the normal
                # chance to hit." Mirrors turn/challenge_execution.py's
                # own Phase 701 wiring exactly: the guardian gets a free
                # reactive Melee swing against the archer first (this
                # module's own established Cast-at-Melee-Range reactive-
                # swing pattern, lines above), then the shot itself
                # resolves one-sided at normal accuracy.
                if (
                    not leader_combatant.blocked_from_archery
                    and AdvancedAbility.SHORT_RANGE_ARCHERY in leader.advanced_abilities
                ):
                    swing_result = resolve_reactive_melee_swing(monster_combatant, leader_combatant, rng)
                    melee_swings.append(_melee_swing_from_reactive("b", swing_result))
                    if leader_combatant.hit_points <= 0:
                        return _finish_melee_outcome(EncounterCombatResult(winner="b", rounds=0))
                    combat_attempted = True
                    outcome = _resolve_fire_arrow_phase(short_range_archer="a")
                    if outcome is not None:
                        # _resolve_fire_arrow_phase() never sets
                        # melee_swings itself (safe everywhere else it's
                        # called -- this is the only path where a real
                        # Melee round, and now this reactive swing, could
                        # already have populated the shared accumulator
                        # before Fire Arrow ends the encounter).
                        outcome.melee_swings = tuple(melee_swings)
                        return outcome
                    continue
                continue  # [5.0]: only spells or Melee are usable in the melee zone
            if leader_combatant.blocked_from_archery:
                continue
            combat_attempted = True
            # Phase 719: AdvancedAbility.LONG_RANGE_ARCHERY -- "may now use
            # the Fire tactic at Spell Range, with half the normal chance
            # to hit." This engine has no explicit "close to Bow Range"
            # step the way turn/challenge_execution.py's own SHOOT branch
            # does (current_range only ever tracks SPELL_RANGE vs. MELEE_
            # RANGE here) -- an ordinary shot at Spell Range already fires
            # at full accuracy, bidirectionally. The ability instead trades
            # that full accuracy and the guardian's own return fire for
            # half accuracy and a one-sided shot, via the same real
            # `resolve_fire_arrow_duel()` kwarg Phase 700 already built.
            if current_range is CombatRange.SPELL_RANGE and AdvancedAbility.LONG_RANGE_ARCHERY in leader.advanced_abilities:
                outcome = _resolve_fire_arrow_phase(long_range_archer="a")
            else:
                outcome = _resolve_fire_arrow_phase()
            if outcome is not None:
                return outcome
            continue  # free attacks exhausted, nobody dead -- fall through
        if tactic.maneuver is Maneuver.MELEE:
            combat_attempted = True
            # Phase 887: a monster blocked_from_archery (a leader's own
            # Spiritwrack/Hand of Death cast on it earlier in the same
            # encounter) no longer preempts with its own canned Fire
            # Arrow tactic either -- the identical rule this phase
            # already wires for the leader's own SHOOT tactic (this
            # file's own gate a few lines above, and turn/challenge_
            # execution.py's newly-fixed equivalent), applied here to
            # the guardian's own monster_wants_shoot trigger.
            if monster_wants_shoot and not fire_arrow_resolved and not monster_combatant.blocked_from_archery:
                outcome = _resolve_fire_arrow_phase()
                if outcome is not None:
                    return outcome
                # nobody died from the guardian's own shots -- fall through to melee
            outcome = _resolve_monster_casts()
            if outcome is not None:
                return outcome
            current_range = CombatRange.MELEE_RANGE
            # Phase 293: mirrors turn/challenge_execution.py's own Phase
            # 292 last-vs-non-last MELEE split -- a plan's own *last*
            # tactic (or its only one, every real caller/pre-Phase-293
            # test's own shape) still loops until death ("melee once
            # reached loops until death"); a MELEE tactic followed by
            # more tactics (a genuinely new plan shape) fights only one
            # round before falling through, letting a following CAST see
            # the guardian's own reactive swing. A trailing Scout doesn't
            # count as "more tactics" -- it "makes no difference where
            # you put" it and always resolves separately, after this
            # whole walk finishes (`_apply_scout()`'s own docstring), so
            # `MELEE, SCOUT` is exactly the "MELEE is really last" shape,
            # not a genuinely new one.
            is_last_leader_tactic = all(t.maneuver is Maneuver.SCOUT for t in request.tactics[tactic_index + 1 :])
            if is_last_leader_tactic and not _monster_has_more_casts_pending():
                # Fast path: the guardian's own plan has nothing left but
                # Melee too -- the atomic resolve_melee_duel() is RNG-
                # identical to looping resolve_one_melee_round() (Phase
                # 292's own proven parity), so every pre-Phase-293 caller
                # (and every test mocking resolve_melee_duel() directly)
                # is completely unaffected. Phase 297: skip_temper_setup=
                # melee_setup_done guards against double-applying Temper
                # setup for a genuinely new plan shape where an earlier
                # non-last MELEE already ran it via round-stepping (e.g.
                # `[MELEE, TALK, MELEE]`) -- inert (False) for every
                # ordinary plan, where this is the first Melee reached.
                duel_result = resolve_melee_duel(leader_combatant, monster_combatant, rng, skip_temper_setup=melee_setup_done)
                melee_swings.extend(duel_result.melee_swings)
                return _finish_melee_outcome(duel_result)
            while True:
                outcome = _resolve_melee_range_round(tactic, leader_tactic_index=tactic_index)
                if outcome is not None:
                    return outcome
                if not is_last_leader_tactic:
                    break
            continue
        if tactic.maneuver is Maneuver.STEAL:
            outcome = _resolve_steal()
            if outcome is not None:
                return outcome
            continue
        if tactic.maneuver is Maneuver.TALK:
            outcome = _resolve_talk()
            if outcome is not None:
                return outcome
            continue
        if tactic.maneuver is Maneuver.FULFILL:
            outcome = _resolve_fulfill()
            if outcome is not None:
                return outcome
            continue
        if tactic.maneuver is Maneuver.SAY:
            # Phase 240: "non fa consumare tempo di combattimento" --
            # a documented no-op, not an oversight (see `turn/
            # encounter.py`'s own Phase 240 addendum).
            continue
        if tactic.maneuver is Maneuver.BEG:
            outcome = _resolve_beg()
            if outcome is not None:
                return outcome
            continue
        if tactic.maneuver is Maneuver.USE_MI:
            outcome = _resolve_use_mi_tactic(tactic)
            if outcome is not None:
                return outcome
            continue
        if tactic.maneuver is Maneuver.GIVE:
            outcome = _resolve_give_tactic(tactic)
            if outcome is not None:
                return outcome
            continue
        # Every other maneuver isn't wired -- skip it and keep walking
        # the plan, matching how real Encounter Plans mix wired and
        # unwired tactics (module docstring's own quoted examples).
        # - **Give** (Phase 274, corrected Phase 734): the earlier claim
        #   here -- "has exactly one real use, passing an item to another
        #   Hero or King, never a monster... structurally inapplicable" --
        #   was stale, found and fixed while implementing `AdvancedAbility.
        #   DRUIDIC_TRADES`'s own real "trade with a monster via the GI-ve
        #   order" text (see `_resolve_give_tactic()`'s own docstring,
        #   right above this loop). Give now has exactly one real,
        #   sourced monster-facing use too.
        # - **Scout** (Phase 274): resolved separately, *after* this
        #   tactic walk finishes -- see `_apply_scout()`'s own docstring
        #   for why it can't simply take a branch here like every other
        #   tactic above.
        # - **Squeeze** (`Maneuver.SQUEEZE`, `manab`'s own `'SQ'`) --
        #   **closed, Phase 631**: not a player-selectable tactic at all.
        #   `SAY.PAS`'s `_LSquee: FD2('squeeze',S_PCom,5)` prose (Phase
        #   413) is Hand of Death's own per-round attack narration,
        #   wired via `resolve_hand_of_death_channel()`'s own `squeeze_
        #   hits` + `report/turn_report.py render_squeeze_attack()` --
        #   the user directly reconfirmed this ("lo squeeze e' il prose
        #   dello spell Hand of Death") when this comment's own earlier,
        #   more hedged framing was re-checked this phase. `CTBOTH.PAS`'s
        #   own `maneuver` enum declares `CSqueeze` as a real, distinct
        #   value, but it is the *only* reference to it anywhere in the
        #   13 surviving `.PAS` files -- no dispatch/resolution logic for
        #   it survives, `Regolamento AK.txt` never once mentions
        #   "Squeeze" as a player action, and none of this project's own
        #   22 real sample `.K1` Encounter Plans ever writes `SQ`. Read
        #   together with the user's own confirmation, `CSqueeze`'s
        #   membership in the shared `maneuver` type is an internal
        #   narration-category marker the compiled engine reuses while
        #   resolving Hand of Death (matching `CTME.PAS`'s own `Death`
        #   enum, a per-weapon damage-narration category with `weapkill
        #   [Tentacles] = Squeeze`, Giant Octopus's own natural weapon --
        #   the same "squeeze" narration concept, reused, not two
        #   unrelated mechanics), not real Encounter Plan input syntax.
        #   There is nothing left here to dispatch on.

    if combat_attempted:
        # Phase 178: the plan's own tactic list ran out without a winner
        # (only reachable when Fire Arrow exhausted its shots and no
        # further tactic followed) -- default to Melee until someone
        # dies, per the user's own confirmed default. See module
        # docstring's own Phase 178 addendum. Phase 293: this is real
        # "ME fino alla fine" territory -- the round engine loops
        # forever (a synthetic bare Melee tactic drives the leader's own
        # side), still letting the guardian's own remaining plan (if any
        # CAST tactics are left past its own first Melee) interleave.
        outcome = _resolve_monster_casts()
        if outcome is not None:
            return outcome
        current_range = CombatRange.MELEE_RANGE
        if not _monster_has_more_casts_pending():
            # Fast path -- see the Melee tactic branch's own identical
            # comment above (including the Phase 297 skip_temper_setup
            # note).
            duel_result = resolve_melee_duel(leader_combatant, monster_combatant, rng, skip_temper_setup=melee_setup_done)
            melee_swings.extend(duel_result.melee_swings)
            return _finish_melee_outcome(duel_result)
        synthetic_leader_tactic = SearchTactic(maneuver=Maneuver.MELEE)
        while True:
            outcome = _resolve_melee_range_round(synthetic_leader_tactic, leader_tactic_index=len(request.tactics))
            if outcome is not None:
                return outcome
    return SearchExecutionResult(
        accepted=True,
        combat_resolved=False,
        reason="no Melee or Fire Arrow tactic in encounter plan -- see module docstring for what's wired",
    )
