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
  examples. See ``turn/encounter.py``'s own Phase 173 addendum for the
  full quote.
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
  ``blocked_from_cast_and_archery`` -- regardless of the spell's own
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

  **Success-chance gating, read directly from [5.8]'s own text**: "an
  attempt will be made to discover" when the plan "calls for Talking,
  Fulfilling, or Attacking" -- Melee and Fire Arrow are this project's
  own two real "Attacking" Encounter Plan tactics, so both qualify.
  That branch states no failure chance, so it's read as guaranteed.
  "If you use some other type of tactical plan, you may be told that
  the Special is there, but not find out what it does" -- only two
  named exceptions give an actual percentage: Steal (33% chance of not
  even that) and Flee (67%). A plan matching neither the guaranteed
  branch nor one of these two named exceptions (a bare Scout, or
  Give+Scout only) is left genuinely unresolved -- unsourced, not
  guessed.

  **Only the discovery *level* is modeled**
  (``Feature.discovered_by_kingdom``, real since Phase 75/242): the
  guaranteed branch reaches level 3 ("fully known"); a successful
  partial branch (Steal's/Flee's own named chance) reaches level 2 ("a
  magic-power hint is known," per that field's own docstring) --
  matching "told... it is there, but not find out what it does"
  literally. Never lowers an already-higher level. **What Scout would
  actually reveal (the Special's own real content) is not modeled at
  all**: no ``Feature`` in this project is ever assigned a ``Power``/
  ``PowerCondition`` (``models/power.py``'s own vocabulary is never
  wired to a real instance, and ``turn/world_generation.py`` never
  assigns one) -- confirmed directly with the user (project author),
  who chose this narrower scope explicitly rather than first building
  that missing link.

  **Two Scout orders, sourced from ``PROSE/PCOND.X2`` (user-supplied,
  project-original)**: the game's own PowerCondition-rejection prose
  confirms, for exactly 3 of ``PowerCondition``'s 6 real conditions --
  ``PayUp``, ``DrainSkill``, ``DrainCourage``, the three that cost the
  character something to use a feature's Power -- "to accept these
  terms, a character must give two Scout orders when Searching this
  feature" (quoted three times, once per condition, verbatim except for
  the specific cost named). ``SearchExecutionResult.scout_orders_given``
  records the real count (>=2 meaning "consent given") -- a confirmed,
  sourced fact with nothing to consume it yet, the same "confirmed
  mechanic, no consumer yet" scoping this module already uses elsewhere
  (e.g. Invisibility's own Steal bonus, module docstring's Phase 186
  note) -- since no ``Feature`` ever carries a ``Power``/
  ``PowerCondition`` to actually consent to in the first place.

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

**What is still genuinely open, precisely re-scoped (not "the engine is
unbuilt" -- two specific, narrower gaps):**

1. **Spell disruption (``spell_disruption_chance()``/``resolve_spell_
   disruption()``, ``turn/encounter.py``'s own Phase 179 addendum) is
   still never rolled anywhere in this walk.** Not an oversight like
   Words of Healing was -- it is structurally unwireable at this walk's
   own granularity. The formula needs "hits taken by the caster
   *this round*, before the cast is attempted," but this module's own
   tactics resolve as whole self-contained duels (``resolve_melee_
   duel()``/``resolve_fire_arrow_duel()`` each fight an entire encounter
   to its own conclusion in one call), not as a round-by-round loop a
   ``CAST`` tactic could be interleaved into mid-round. Meaningfully
   wiring disruption needs the same round-based, three-``CombatRange``
   state machine ``turn/encounter.py``'s own module docstring has
   flagged as unbuilt since Phase 60/179/209-211/237-238 -- this
   project's largest single remaining piece of unbuilt personal-combat
   machinery, not a small addition. A degenerate wiring (every ``CAST``
   tactic sees "0 hits taken so far," since nothing in the current walk
   ever precedes a ``CAST`` with a partial, still-in-progress duel)
   would technically compile but would always resolve to 0% disruption
   -- indistinguishable from not wiring it at all, so it is left
   honestly unattempted rather than faked.
2. **This dispatch is still Search-only.** ``_resolve_cast_tactic()``
   is a private closure inside ``execute_search()``, never exposed to
   ``turn/challenge_execution.py`` or ``turn/pursue_execution.py`` --
   both of which still resolve personal combat via Melee/Fire Arrow
   only (``turn/encounter.py resolve_encounter_combat()``), with no
   ``CAST`` tactic support at all. ``turn/challenge_execution.py``'s own
   docstring still says outright "classifying which spells count as
   personal combat spells needs a spell-effect system this project
   doesn't have" -- true when written (Phase 50), stale now that Phase
   209-238 built exactly that system, just never circled back to update
   the claim or extend the wiring. Generalizing ``_resolve_cast_
   tactic()`` into a shared, cross-consumer function (it currently reads
   Search-specific concepts throughout -- ``feature.guardian_monster``,
   ``MONSTER_MAGIC_ABILITIES`` lookups, a rolled monster combat stat
   block -- none of which apply to a Challenge/Pursue leader-vs-leader
   encounter) is real, scoped follow-up work, deliberately not attempted
   in this same phase alongside the narrower Words of Healing fix, the
   same "one clear gap per phase" discipline this project has followed
   throughout.

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
"""

from __future__ import annotations

import random
from dataclasses import dataclass, replace

from ak_engine.models.advanced_ability import LAVA_POOL_IMMUNE_MONSTERS, AdvancedAbility
from ak_engine.models.alignment import ALIGNMENT_ORDINAL, Alignment
from ak_engine.models.enums import Ability, Maneuver, Spell
from ak_engine.models.game_state import GameState, LeaderState
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
    roll_gate_demon_type,
    roll_monster_alignment,
)
from ak_engine.models.monster_encounter_plan import roll_monster_encounter_plan
from ak_engine.models.office import Office
from ak_engine.models.race import HUMANOID_RACES
from ak_engine.models.temper import Temper
from ak_engine.models.valhalla import VALHALLA_VISITOR_LEADER_ID
from ak_engine.turn.discovery_effects import effective_skill_level, holder_is_immune_to_spell
from ak_engine.turn.encounter import (
    BEG_MERCY_CHANCE,
    CHARACTER_HIT_POINTS,
    FIRE_ARROW_DAMAGE_RANGE,
    INVISIBILITY_HIT_CHANCE_MULTIPLIER,
    MIRROR_IMAGE_LEADER_INTELLIGENCE_TIER_DEFAULT,
    MIRROR_IMAGE_MONSTER_INTELLIGENCE_TIER,
    STEAL_THIEF_MASTERY_ABILITIES,
    PERSONAL_COMBAT_SPELL_ABILITY,
    PERSONAL_COMBAT_SPELL_SELF_ONLY,
    Combatant,
    CombatRange,
    EncounterCombatResult,
    FireArrowShot,
    MeleeSwing,
    MirrorImageIntelligenceTier,
    MonsterTalkReply,
    MONSTER_TALK_REPLY_OUTCOME,
    TalkReplyOutcome,
    apply_temper_melee_setup,
    archery_free_attack_bonus,
    blocks_cast_and_archery,
    melee_mastery_damage_bonus,
    melee_mastery_offensive_hit_multiplier,
    can_talk_to_monster,
    control_undead_anti_holy_resist_chance,
    control_undead_failure_new_hit_points,
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
    select_monster_talk_reply,
    roll_fireball_damage,
    roll_holy_symbol_undead_damage,
    roll_ice_suspension_flying_bonus_rounds,
    roll_ice_suspension_flying_crash_damage,
    roll_melee_attack,
    roll_psychic_blast_stun_rounds,
    roll_telekinetic_storm_caster_damage,
    roll_telekinetic_storm_victim_damage,
    spiritwrack_melee_damage_reduction,
    words_of_healing_heal,
)
from ak_engine.models.treasure import TREASURE_CATEGORY, TREASURE_WAND_SPELL, TreasureCategory
from ak_engine.turn.experience import add_experience
from ak_engine.turn.office_holder import resolve_office_holder
from ak_engine.turn.search_decode import SearchRequest, SearchTactic

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
    base_chance: float, *, temper: Temper | None, is_invisible: bool, has_melee_evasion: bool = False
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
    """

    bonus = WEAK_TEMPER_FLEE_CHANCE_BONUS if temper in WEAK_FLEE_TEMPERS else 0.0
    if is_invisible:
        bonus += INVISIBILITY_FLEE_CHANCE_BONUS
    if has_melee_evasion:
        bonus += MELEE_EVASION_FLEE_CHANCE_BONUS
    return min(1.0, base_chance + bonus)

# TREASAB.X2: every one of the 20 wands' own label reads "Cast '<Spell>' at
# skill-2" -- same real fact as turn/use_mi_execution.py's own USE_MI_WAND_
# SKILL_LEVEL, duplicated per this project's own "independent citation per
# consumer module" convention (module docstring's own Phase 274 addendum).
SEARCH_USE_MI_WAND_SKILL_LEVEL = 2

# Rulebook [5.8] Scout -- module docstring's own Phase 274 addendum has the
# full quote and reasoning behind every constant below.
SCOUT_GUARANTEED_MANEUVERS = frozenset({Maneuver.TALK, Maneuver.FULFILL, Maneuver.MELEE, Maneuver.SHOOT})
SCOUT_STEAL_ONLY_SUCCESS_CHANCE = 1.0 - 0.33  # "if you Steal and Scout, there is a 33% chance of not finding out"
SCOUT_FLEE_ONLY_SUCCESS_CHANCE = 1.0 - 0.67  # "if you Flee and Scout, this chance is 67%"
# "you may be told that the Special is there, but not find out what it
# does" -- models/feature.py's own fdisc=2 ("a magic-power hint is known").
SCOUT_PARTIAL_DISCOVERY_LEVEL = 2
SCOUT_FULL_DISCOVERY_LEVEL = 3  # "an attempt will be made to discover" -- no stated failure chance, read as guaranteed


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
        temper=leader.temper,
        damage_reduction=damage_reduction,
        has_melee_hit_points_ability=has_melee_hit_points_ability,
        offensive_hit_multiplier=melee_mastery_offensive_hit_multiplier(leader.advanced_abilities),
        melee_damage_dealt_bonus=melee_mastery_damage_bonus(leader.advanced_abilities),
        is_humanoid=is_humanoid,
        has_duellists_medal_ability=AdvancedAbility.MELEE_DUELLISTS_MEDAL in leader.advanced_abilities,
        has_control_temper_ability=AdvancedAbility.MELEE_CONTROL_TEMPER in leader.advanced_abilities,
        archery_free_attack_bonus=archery_free_attack_bonus(leader.advanced_abilities),
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
    guardian_monster: Monster | None = None
    # Phase 213: the originating request, so a caller (report/turn_report.py
    # describe_turn_results()) can resolve the searched feature's own id.
    # Set by plan_dispatch.py's own dispatcher, not by execute_search()
    # itself -- same convention/reasoning as PursueExecutionResult.request's
    # own Phase 213 note.
    request: SearchRequest | None = None
    # Phase 274: how many Scout tactics the plan actually listed -- set by
    # `_apply_scout()` regardless of whether Scout itself found anything.
    # >=2 is PCOND.X2's own confirmed "consent given" signal for a Power
    # condition this project has nothing yet to apply it to -- see
    # `_apply_scout()`'s own docstring.
    scout_orders_given: int = 0


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
        _apply_scout(state, leader_id, request, result, rng)
    return result


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

    This project has no "special function or event" system at all to
    trigger ([5.8]'s own beneficial/detrimental Specials need the
    Feature->Power link ``models/power.py``/``models/magic_feature.py``
    flag as never wired anywhere, see those modules' own docstrings) --
    the one real, already-modeled effect Scout can drive is [5.8]'s own
    "gain information on what treasure is in the feature," i.e. a
    discovery-level bump on ``Feature.discovered_by_kingdom`` (Phase 75)
    from a partial "a magic-power hint is known" (2) to a full "fully
    known" (3) reveal -- the exact two non-zero, non-"riches unknown"
    levels that array's own docstring documents. Runs unconditionally
    last (per the quote above), independent of every other tactic's own
    return-early control flow -- which is exactly why this can't be just
    another branch inside the main tactic walk above, and needs its own
    post-processing pass in ``execute_search()`` instead.

    **The success/failure split**, using ``request.tactics`` as a whole
    (not just position, since the rulebook says position never matters):
    a plan containing Talk, Fulfill, Melee, or Shoot ("Attacking" reads
    as [3.12]'s own combat-intent tactics, ``challenge_execution.py
    has_combat_intent()``'s own precedent) is a guaranteed reveal, no
    roll. Otherwise a bare Steal is 67%, a bare Flee is 33% -- the
    rulebook's own two named examples, both literal two-tactic plans
    ("Steal and Scout" / "Flee and Scout"); a plan with both and neither
    a guaranteed tactic resolves against Steal's own 67% first (the
    rulebook lists Steal first, and both tactics still "match one of the
    two named exceptions", just not disambiguated further). Every other
    combination the rulebook doesn't literally name (Cast-only, Beg-only,
    Say-only, or a bare Scout) matches *neither* the guaranteed branch
    nor either named exception -- left genuinely unresolved (no
    discovery-level change at all, not even a downgrade-safe partial),
    per this project's own standing "no source, no guess" convention,
    rather than inventing a percentage the rulebook never gave.

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
    condition ("PayUp"/"DrainSkill"/"DrainCourage") this project has no
    Feature->Power wiring to actually apply yet. Recorded now, honestly,
    as a fact the caller can act on later, rather than silently dropped.
    """

    scout_count = sum(1 for tactic in request.tactics if tactic.maneuver is Maneuver.SCOUT)
    result.scout_orders_given = scout_count
    if scout_count == 0 or result.leader_killed:
        return

    leader = state.leaders.get(leader_id)
    feature = state.features.get(request.feature_id)
    if leader is None or feature is None or leader.kingdom_id is None:
        return

    maneuvers = {tactic.maneuver for tactic in request.tactics}
    if maneuvers & SCOUT_GUARANTEED_MANEUVERS:
        discovered = True
    elif Maneuver.STEAL in maneuvers:
        discovered = rng.random() < SCOUT_STEAL_ONLY_SUCCESS_CHANCE
    elif Maneuver.FLEE in maneuvers:
        discovered = rng.random() < SCOUT_FLEE_ONLY_SUCCESS_CHANCE
    else:
        # Matches neither the guaranteed branch nor either of the
        # rulebook's two named exceptions (Cast-only, Beg-only, a bare
        # Scout, ...) -- genuinely unresolved by the source, so this
        # attempt has no effect at all rather than guessing a percentage.
        return

    current_level = feature.discovery_level(leader.kingdom_id)
    new_level = SCOUT_FULL_DISCOVERY_LEVEL if discovered else max(current_level, SCOUT_PARTIAL_DISCOVERY_LEVEL)
    feature.discovered_by_kingdom[leader.kingdom_id] = new_level


def _apply_monster_duel_merit(
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
    plus Bravest's own protagonist-only, winner-only credit (``CHARACTER_
    HIT_POINTS - leader_combatant.hit_points``, 0 for an unscathed win,
    per SS18.7 -- the leader executing this SEARCH order is always the
    encounter's own "protagonist" against a monster, there being no
    separate challenger/target split to resolve as there is in a real
    Challenge). Cravenest's dispatcher always skips the winner's own
    branch (SS18.5), so no courage-merit change here either.

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
        bravery_gain = CHARACTER_HIT_POINTS - leader_combatant.hit_points
        leader.merit_tally.bravery_merit += bravery_gain
    else:
        leader.merit_tally.duel_merit_net -= 2
        leader.merit_tally.courage_encounter_merit -= 1


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
    )
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

    def _outcome_from(combat_result: EncounterCombatResult) -> SearchExecutionResult | None:
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
                state.add_item(feature.treasure, leader_id)
            # Phase 255: every "a" win here is a real combat defeat of the
            # guardian (melee, fire arrow, or a spell's own instant-kill
            # branch) -- never the rulebook's separate "neutralized via
            # negotiation" case, which needs Fulfill/Talk-Say's own
            # not-yet-wired mechanic (see module docstring). Full HP
            # credited, not the halved figure -- that halving is
            # `defender_merit_points()`'s own job, not this raw tally's.
            leader.merit_tally.monster_hp_defeated += monster_starting_hit_points
            _apply_monster_duel_merit(leader, feature.guardian_monster, leader_won=True, leader_combatant=leader_combatant)
            return SearchExecutionResult(accepted=True, combat_resolved=True, winner="leader", feature_looted=True)
        if combat_result.winner == "b":
            _apply_monster_duel_merit(leader, feature.guardian_monster, leader_won=False, leader_combatant=leader_combatant)
            state.remove_leader(leader_id)
            return SearchExecutionResult(accepted=True, combat_resolved=True, winner="monster", leader_killed=True)
        return None

    cast_attempt_applied = False

    def _resolve_cast_tactic(
        tactic, *, caster_is_leader: bool, is_first_tactic: bool = False, forced_level: int | None = None
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
        instant-kill-or-escape roll), and Augur Combat from Phase 238
        (``is_first_tactic`` -- true position within the caster's own
        full plan, not just among its own ``CAST`` entries -- decides
        whether this runs the real "silent simulation" (a throwaway
        ``resolve_melee_duel()`` on cloned combatants, discarded after
        reading only its winner) or acts as an attempted Flee, per
        ``turn/encounter.py``'s own Phase 205 addendum), and Words of
        Healing from Phase 289 (``words_of_healing_heal()`` -- self-only,
        gated by the same secret-spell skill-5+ eligibility check as
        Illusory Hero, no target interaction at all -- this closes the
        last gap in this function's own spell coverage: all 16 real
        Personal-Combat spell mechanics ``turn/encounter.py`` documents
        are now dispatched here). Returns a terminal
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
        """

        nonlocal cast_attempt_applied
        cast_attempt_applied = False

        caster = leader_combatant if caster_is_leader else monster_combatant
        target = monster_combatant if caster_is_leader else leader_combatant
        if caster.blocked_from_cast_and_archery:
            return None
        try:
            spell = Spell(tactic.sub_object)
        except ValueError:
            return None

        target_is_monster = caster_is_leader
        monster_species = feature.guardian_monster

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

        cast_attempt_applied = True  # every real precondition above is now passed
        if forced_level is not None:
            succeeded = True  # [3.11]/[5.1]: "a spell cast from a magic item is automatically successful"
        else:
            succeeded = resolve_personal_combat_spell_cast(level, rng, caster_is_pagan=caster_is_pagan)

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
            and holder_is_immune_to_spell(state, leader_id, spell)
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
                return _outcome_from(EncounterCombatResult(winner=("a" if target_is_monster else "b"), rounds=0))
            target.hit_points = control_undead_failure_new_hit_points(target.hit_points, rng)
            return None

        if not succeeded:
            return None

        if spell is Spell.CHARM:
            # Confirmed by the user: the *caster* flees, same outcome as a
            # successful Maneuver.FLEE.
            return SearchExecutionResult(accepted=True, combat_resolved=False, fled=True)

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
                    return _outcome_from(EncounterCombatResult(winner=("a" if target_is_monster else "b"), rounds=0))
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
            target.blocked_from_cast_and_archery = blocks_cast_and_archery(target_is_immune=target_is_immune)
            return None

        if spell is Spell.PSYCHIC_BLAST:
            caster.bonus_unanswered_attacks += roll_psychic_blast_stun_rounds(rng)
            return None

        if spell is Spell.TELEK_STORM:
            target_is_immune = target_is_monster and monster_species in SUBMARINE_MONSTERS
            target.hit_points -= roll_telekinetic_storm_victim_damage(rng, target_is_immune=target_is_immune)
            caster.hit_points -= roll_telekinetic_storm_caster_damage(
                CombatRange.SPELL_RANGE, rng, target_is_immune=target_is_immune
            )
            if target.hit_points <= 0:
                return _outcome_from(EncounterCombatResult(winner=("a" if target_is_monster else "b"), rounds=0))
            if caster.hit_points <= 0:
                return _outcome_from(EncounterCombatResult(winner=("b" if target_is_monster else "a"), rounds=0))
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
            if not opponent_has_witchsight:
                caster.defensive_hit_multiplier *= INVISIBILITY_HIT_CHANCE_MULTIPLIER
            caster.is_invisible = True
            return None

        if spell is Spell.HEAL:
            # "The character is completely healed... gaining back all
            # lost hit points" -- self-only, no target interaction, no
            # skill-level scaling (only the eligibility gate above uses
            # `level`). A monster caster's own max is its starting roll
            # (`monster_starting_hit_points`, captured before this
            # encounter began mutating it); a leader caster's own max is
            # the fixed character value.
            max_hit_points = CHARACTER_HIT_POINTS if caster_is_leader else monster_starting_hit_points
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
            target.hit_points -= roll_fireball_damage(level, rng, target_is_immune=target_is_immune)
            if target.hit_points <= 0:
                return _outcome_from(EncounterCombatResult(winner=("a" if target_is_monster else "b"), rounds=0))
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
                return _outcome_from(EncounterCombatResult(winner=("a" if target_is_monster else "b"), rounds=0))
            if target_is_monster and monster_species in ICE_SUSPENSION_FLYING_MONSTERS:
                target.hit_points -= roll_ice_suspension_flying_crash_damage(rng)
                caster.bonus_unanswered_attacks += roll_ice_suspension_flying_bonus_rounds(rng)
                if target.hit_points <= 0:
                    return _outcome_from(EncounterCombatResult(winner=("a" if target_is_monster else "b"), rounds=0))
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
            channel_result = resolve_hand_of_death_channel(caster, target, level, rng, target_is_immune=target_is_immune)
            if channel_result.winner is not None:
                # "a" in resolve_hand_of_death_channel's own convention always
                # means the caster -- translate to the leader/monster "a"/"b"
                # convention _outcome_from() expects.
                outcome = _outcome_from(EncounterCombatResult(winner=("a" if target_is_monster else "b"), rounds=0))
                if outcome is not None:
                    # Phase 413: the winning channel's own per-round damage,
                    # for report/turn_report.py render_squeeze_attack() --
                    # see SearchExecutionResult.squeeze_hits's own Phase 413
                    # note for why an interrupted (non-winning) channel isn't
                    # captured here.
                    outcome.squeeze_hits = channel_result.squeeze_hits
                return outcome
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
                return _outcome_from(EncounterCombatResult(winner=("a" if target_is_monster else "b"), rounds=0))
            if duel_result.winner == "b":
                # The illusion kills the caster; the opponent "revives".
                return _outcome_from(EncounterCombatResult(winner=("b" if target_is_monster else "a"), rounds=0))
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
                return _outcome_from(EncounterCombatResult(winner=("a" if target_is_monster else "b"), rounds=0))
            if duel_result.winner == "b":
                return _outcome_from(EncounterCombatResult(winner=("b" if target_is_monster else "a"), rounds=0))
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
            duel_result = resolve_melee_duel(demon, target, rng)
            if duel_result.winner == "a":
                # GATE_DEMON_WINNER_RETURNS_TO_ABYSS -- the caster is
                # credited with the win, same as every other spell above.
                return _outcome_from(EncounterCombatResult(winner=("a" if target_is_monster else "b"), rounds=0))
            # GATE_DEMON_LOSS_CASTER_RESUMES_FIGHT_AT_CURRENT_RANGE -- no
            # direct penalty on the caster; the plan simply continues.
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
            return _outcome_from(EncounterCombatResult(winner=("a" if target_is_monster else "b"), rounds=0))

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
                )
                if rng.random() < flee_chance:
                    return SearchExecutionResult(accepted=True, combat_resolved=False, fled=True)
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
                return SearchExecutionResult(accepted=True, combat_resolved=False, fled=True)
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

        while attacker.bonus_unanswered_attacks > 0:
            attacker.bonus_unanswered_attacks -= 1
            damage = roll_melee_attack(
                rng, damage_range=attacker.melee_damage_range, hit_chance_multiplier=defender.defensive_hit_multiplier
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
            swing_result = resolve_reactive_melee_swing(leader_combatant, monster_combatant, rng)
            damage = swing_result.damage
            melee_swings.append(MeleeSwing(attacker="a", hit=swing_result.hit, damage=swing_result.damage))
            if monster_combatant.hit_points <= 0:
                return _finish_melee_outcome(EncounterCombatResult(winner="a", rounds=0))
            disrupted = (
                resolve_spell_disruption(damage, rng) if damage > 0 else resolve_spell_disruption_from_missed_attack(rng)
            )
            is_first_tactic = monster_tactic_index == 0
            _advance_monster_tactic()
            if disrupted:
                return None
            return _resolve_cast(monster_tactic, caster_is_leader=False, is_first_tactic=is_first_tactic)

        # leader_tactic.maneuver is Maneuver.CAST from here on
        if monster_tactic is None:
            swing_result = resolve_reactive_melee_swing(monster_combatant, leader_combatant, rng)
            damage = swing_result.damage
            melee_swings.append(MeleeSwing(attacker="b", hit=swing_result.hit, damage=swing_result.damage))
            if leader_combatant.hit_points <= 0:
                return _finish_melee_outcome(EncounterCombatResult(winner="b", rounds=0))
            disrupted = (
                resolve_spell_disruption(damage, rng) if damage > 0 else resolve_spell_disruption_from_missed_attack(rng)
            )
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

    def _resolve_fire_arrow_phase() -> SearchExecutionResult | None:
        nonlocal fire_arrow_shots, fire_arrow_resolved
        fire_arrow_resolved = True
        outcome = _resolve_monster_casts()
        if outcome is not None:
            return outcome
        duel_result = resolve_fire_arrow_duel(leader_combatant, monster_combatant, rng)
        fire_arrow_shots = duel_result.shots
        outcome = _outcome_from(duel_result)
        if outcome is not None:
            outcome.fire_arrow_shots = fire_arrow_shots
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
        (``resolve_steal_monster_item_transfer()``) decide whether the
        guardian's hoard was actually hidden from the thief -- a failure
        there is a documented no-effect (the thief got past the guardian
        but found nothing), not a caught-thief consequence.
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
            if not resolve_steal_monster_item_transfer(intelligence_ordinal, 0, rng):
                return None  # past the guardian, but the hoard was hidden -- plan continues
            # Phase 442: one of the real compiled formula's own "two
            # separate success paths that award the [Prince of Thieves]
            # point" (turn/merit_points.py thiefprince_merit_points()'s
            # own Phase 369 addendum) -- this one, Search's own Steal
            # against a guarded feature's hoard.
            leader.merit_tally.successful_thefts += 1
            # Phase 457: the same real Add_Experience credit (base 15,
            # AKGEN_reverse_engineering_report (2).md SS3.3's own Thief
            # row) turn/challenge_execution.py _apply_successful_theft()
            # awards for the character-vs-character Steal path -- see
            # that function's own Phase 457 addendum for why this and
            # that are the two real "qualifying theft event" triggers.
            add_experience(leader, Ability.THIEF, 15, rng)
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
            outcome = _outcome_from(melee_duel_result)
            if outcome is not None:
                outcome.melee_swings = melee_duel_result.melee_swings
                outcome.guardian_monster = feature.guardian_monster
            return outcome
        duel_result = resolve_fire_arrow_duel(leader_combatant, monster_combatant, rng)
        outcome = _outcome_from(duel_result)
        if outcome is not None:
            outcome.fire_arrow_shots = duel_result.shots
            outcome.guardian_monster = feature.guardian_monster
        return outcome

    def _resolve_talk() -> SearchExecutionResult | None:
        """Talk [TA], rulebook [5.5] -- Phase 240, **superseded by Phase 528**
        with the real 24-reply selector (``turn/encounter.py``'s own
        Phase 382 addendum has the full sourcing: ``MonsterTalkReply``,
        ``select_monster_talk_reply()``, ``MONSTER_TALK_REPLY_OUTCOME``).
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
        ripetibile") -- persisted on ``Feature.guardian_talk_reply_id``
        (see that field's own docstring for why persistence substitutes
        for the real, never-fully-specified per-tana seed formula). Each
        reply's own ``TalkReplyOutcome`` category (``MONSTER_TALK_REPLY_
        OUTCOME``) then drives exactly the old three-way branch's own
        shape: ``ATTACK`` (``RCharge``/``RMAdvance``) forces combat
        unless Silver Tongue suppresses it (unchanged Phase 468
        behavior, just re-anchored to the real reply instead of a raw
        roll); ``IGNORE`` (``RPuzzled``/``RWarn``) is a no-op, same as
        before; ``QUEST_OR_AGREEMENT`` (the other 20) sets ``pending_
        deal_leader_id`` exactly like the old ``DEAL`` branch did -- this
        project still doesn't model each Quest's own distinct completion
        condition (Phase 258's own scope note), only which of the three
        real outcome categories fires.

        ``has_purchasable_treasure`` is passed as ``False`` unconditionally:
        nothing in this project's own ``Feature``/``Treasure`` model
        distinguishes "a purchasable magic item" from any other treasure
        kind, and ``select_monster_talk_reply()``'s own docstring already
        flags this as a caller-supplied gate rather than something to
        guess -- ``RSell`` is simply never eligible here, a documented
        scope limitation, not a silent wrong default.
        """

        nonlocal combat_attempted
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
        add_experience(leader, Ability.DRUID, 10, rng)

        if feature.guardian_talk_reply_id is None:
            reply = select_monster_talk_reply(feature.guardian_monster, rng, has_purchasable_treasure=False)
            if reply is None:
                return None  # no eligible reply at all -- never observed for a real Monster, but not assumed impossible
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
        return SearchExecutionResult(
            accepted=True,
            combat_resolved=False,
            reason="the guardian proposes a deal -- honor it with Fulfill on a later Search",
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
        # Phase 468: Silver Tongue (Office.DIPLOMAT) always honors a
        # completed deal -- report SS18.4's own "onora sempre un accordo
        # completato".
        silver_tongue_holder = resolve_office_holder(state, Office.DIPLOMAT)
        caster_is_silver_tongue = silver_tongue_holder is not None and silver_tongue_holder.leader_id == leader_id
        if resolve_fulfill_honored(
            feature.guardian_alignment, leader.alignment, rng, caster_is_silver_tongue=caster_is_silver_tongue
        ):
            leader.merit_tally.monster_hp_neutralized += monster_starting_hit_points
            return SearchExecutionResult(accepted=True, combat_resolved=False, winner="leader")
        return None  # not honored -- the plan continues to its next tactic

    def _resolve_beg() -> SearchExecutionResult | None:
        """Beg [BE] -- Phase 241, project-original (no Pascal source, no
        rulebook text -- ``turn/encounter.py``'s own Phase 241 addendum
        has the full "why nothing survives" account and the three design
        decisions confirmed directly by the user/project author). Only
        meaningful once the leader has already taken damage this same
        encounter (``leader_combatant.hit_points < CHARACTER_HIT_POINTS``
        -- every combatant starts at the flat rulebook value, so this
        needs no new field); an undamaged leader has nothing to beg
        about, a documented no-effect rather than an oversight. Only
        monsters intelligent enough to understand a plea can grant mercy
        -- reuses ``MIRROR_IMAGE_MONSTER_INTELLIGENCE_TIER`` (Phase 187)
        directly, defaulting to ``ANIMAL`` (zero mercy) for any species
        missing from that table, same "can't grant it" treatment as a
        species explicitly mapped there. A successful plea ends the
        Search exactly like a successful Flee.
        """

        if leader_combatant.hit_points >= CHARACTER_HIT_POINTS:
            return None  # undamaged -- nothing to beg about yet
        tier = MIRROR_IMAGE_MONSTER_INTELLIGENCE_TIER.get(
            feature.guardian_monster, MirrorImageIntelligenceTier.ANIMAL
        )
        if resolve_beg_for_mercy(tier, rng):
            return SearchExecutionResult(accepted=True, combat_resolved=False, fled=True)
        return None

    for tactic_index, tactic in enumerate(request.tactics):
        if tactic.maneuver is Maneuver.FLEE:
            flee_chance = effective_flee_chance(
                FLEE_CHANCE[stats.speed], temper=leader.temper, is_invisible=leader_combatant.is_invisible,
                has_melee_evasion=AdvancedAbility.MELEE_EVASION in leader.advanced_abilities,
            )
            if rng.random() < flee_chance:
                return SearchExecutionResult(accepted=True, combat_resolved=False, fled=True)
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
                continue  # [5.0]: only spells or Melee are usable in the melee zone
            if leader_combatant.blocked_from_cast_and_archery:
                continue
            combat_attempted = True
            outcome = _resolve_fire_arrow_phase()
            if outcome is not None:
                return outcome
            continue  # free attacks exhausted, nobody dead -- fall through
        if tactic.maneuver is Maneuver.MELEE:
            combat_attempted = True
            if monster_wants_shoot and not fire_arrow_resolved:
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
        # Every other maneuver isn't wired -- skip it and keep walking
        # the plan, matching how real Encounter Plans mix wired and
        # unwired tactics (module docstring's own quoted examples).
        # - **Give** (Phase 274, re-confirmed): has exactly one real use
        #   -- passing an item to another Hero or King (any realm), never
        #   to a monster. Search's own target is always the guardian
        #   monster, so Give is structurally inapplicable here, not
        #   merely unresearched (Fulfill is the monster-facing
        #   counterpart -- see `turn/encounter.py`'s own Phase 240
        #   addendum for why that stays unwired too).
        # - **Scout** (Phase 274): resolved separately, *after* this
        #   tactic walk finishes -- see `_apply_scout()`'s own docstring
        #   for why it can't simply take a branch here like every other
        #   tactic above.
        # - **Squeeze** (`Maneuver.SQUEEZE`, `manab`'s own `'SQ'`, Phase
        #   401): `SAY.PAS`'s `_LSquee: FD2('squeeze',S_PCom,5)` prose
        #   itself is recovered as of Phase 413 and wired via
        #   `resolve_hand_of_death_channel()`'s own `squeeze_hits` +
        #   `report/turn_report.py render_squeeze_attack()`, on the
        #   theory it's Hand of Death's own per-round narration (real
        #   turn-report text across 8 files, confirmed by the user's own
        #   direct play experience). **Phase 414 correction**: this
        #   project's Pascal source turned out to still be reachable,
        #   and a direct check found `_LSquee` is formally declared as a
        #   per-*weapon* damage-narration category (`CTME.PAS`'s `Death`
        #   enum, `weapkill[Tentacles] = Squeeze`), whose only real owner
        #   is Giant Octopus -- not a spell. `_LSquee`'s real *caller*
        #   is still missing from the surviving source either way, so
        #   this stayed genuinely unconfirmed; the wiring is kept as
        #   Phase 413 built it, per the user's own explicit choice (the
        #   play-experience confirmation, not the Pascal source, is its
        #   real basis) -- see `report/turn_report.py
        #   render_squeeze_attack()`'s own Phase 414 note for the full
        #   citation. `Maneuver.SQUEEZE` the enum value itself remains
        #   genuinely unwired as a possible player-selectable tactic --
        #   `CTBOTH.PAS`'s own `maneuver` enum confirms `CSqueeze` really
        #   is a distinct value from `CCast`, not a spell-casting alias,
        #   which if anything favors the Giant-Octopus reading -- still
        #   nothing here dispatches on it, narrower than Phase 401 left
        #   it, not fully closed.

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
