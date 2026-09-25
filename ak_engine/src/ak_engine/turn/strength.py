"""Effective-strength calculator (rulebook [6.3] "Summary of factors
affecting army strength").

The rulebook gives an exact, ordered pipeline:

    Strength of army type, modified by terrain:
      +1 if home terrain for race
      +1 if home terrain for army type
      Halve for adverse terrain
      (Illusory Terrain spell: averaged with real terrain -- SKIPPED, see
       the addendum below for why this is still a real, narrower gap)
    Multiply strength by modified unit quality:
      -1 if in desert without camels
      -? insufficient Druidic ability (see Druid Table) -- Phase 41,
       ``compute_druidic_shortfall``/``DRUID_TABLE`` below
      +1 if in home province
      +1 for fanatical units
      (+1 Oratory spell -- applied directly as a persistent ``Quality``
       rank bump at cast time, not threaded through here as a per-battle
       modifier: rulebook (Regolamento AK.txt [4.22.2]) describes Oratory
       as literally turning Green units Average, Average units Veteran,
       etc. -- the same discrete step ``Quality``'s own enum ordering
       already represents -- see ``turn/cast_execution.py``'s
       ``_execute_oratory``. +1 for a race-matching legendary leadership
       item (Phase 279, ``modified_quality()``'s own ``race_item_bonus``
       parameter; Phase 285, ``compute_effective_strength()``'s own
       ``race_item_bonus`` parameter passes it through) -- computed by
       the ARMIES report's "Modified Quality" column (``turn/
       army_quality.py``) and, since Phase 285, independently by
       ``battle_orchestrator.py _build_battle_units`` for real combat
       strength too, both against the shared ``models/treasure.py
       RACE_LEADERSHIP_TREASURE`` table)
    Multiply result by special factors (multiplied together, not added):
      Defense: +25%
      Exploration: +25% (maximum)
      Tactical Ability +20%/level (or Naval in Sea provinces)
      Phantasmal Armies +15%/level of caster (Phase 59, wired below via
       ``phantasmal_armies_multiplier``/``phantasmal_armies_level``)
      Nemesis encounter: -33% (== the 2/3 multiplier already in
       turn/combat.py -- confirms it, doesn't change it)
      Random Event: +/-% (applied later, in turn/battle_luck.py -- NOT
       part of this function, to avoid double-applying it)

This resolves the "unspecified stacking order" gap flagged in earlier
phases: the order above is a direct rulebook quote, not a guess.
Illusory Terrain's blended-strength averaging -- **wired as of Phase
724** (narrowed correctly by Phase 710, then closed in full): rulebook
[4.23.1] (``Regolamento AK.txt`` lines 1199-1211, repeated at ~line
3099-3100) says a unit that actually *enters* an illusorily-terrained
province discovers the trick, but still fights at a strength "a metà
strada" (halfway) between what it would have on the real terrain and on
the illusory one -- worked example: a plains province illusorily turned
to sea, entering units get the average of their plains-strength and
their "embarked" (Sea) strength. Implemented as a second, independent
blend layered on top of whatever the ordinary (possibly already
Island-blended, see below) pipeline already produces -- see ``compute_
effective_strength()``'s own ``illusory_terrain`` parameter docstring.
The rulebook names no air-unit exemption for this blend (unlike
Island's own, below) -- Dragons/Eagles are affected the same as every
other army type, a deliberate difference, not an oversight. A separate
new 15%/turn dissolve roll (``turn/cast_execution.py maybe_dissolve_
illusory_terrain()``) clears the illusion at the same real-turn
boundary Hide Feature's own dissipation roll already uses. ``Advanced
Ability.ENHANCED_ILLUSORY_TERRAIN``'s own 67/33 blend ratio -- **wired
as of Phase 757**, see ``compute_effective_strength()``'s own
``illusory_terrain_enhanced`` parameter docstring. That ability's other
clause (a random race/army-type shown to an outside observer) is a
report-layer effect, not a combat one, and stays unmodeled.

**Phase 925 addendum -- the rulebook's own bare "+? per gli oggetti
magici" ("+? for magic items") quality-modifier line, [6.3], is fully
and exhaustively covered by ``race_item_bonus`` above, not a separate,
still-open gap as a Phase 758 aside once called it.** The rulebook
gives no item names or numbers for this line (the same shape as the
Druidic-shortfall "-?" two lines above it in the source) -- but this
project's own complete, real magic-item catalog (``models/treasure.py``,
99 real ``Treasure`` entries once the 14 ``UNUSED_*`` placeholders are
excluded) has exactly 4 items anywhere that grant a quality-level
effect, and they're precisely the 4 already wired above:
``LEADERSHIP_HUMAN``/``_ELVEN``/``_DWARVEN``/``_ORCISH``. Checked
programmatically against every real item's own description text for
"quality" -- no other item, common or ultra-rare, touches it. With the
complete real item list in hand, "which magic items give a quality
bonus" is no longer an open question.

**Island provinces (Phase 282, ``is_island``)** -- a different kind of
blended-terrain averaging from Illusory Terrain's, and NOT part of the
rulebook pipeline above: the optional Super AK
variant (games up to 24 players, project-original per the user's own
explicit domain knowledge -- no Pascal source describes it) where a
province is half Sea, half its own land terrain. ``compute_effective_
strength()``'s ``is_island`` flag runs the terrain-dependent portion of
the pipeline above (base strength, race/army-type terrain bonuses,
adverse-terrain halving, Whales' off-Sea zero-strength override) twice
-- once against the province's own land ``terrain``, once against
``Terrain.SEA`` -- and averages the two, before quality/defender-bonus/
multiplier steps run once as normal. Overflight-air units (Dragons,
Eagles, ``models/army_type.py OVERFLIGHT_AIR``) are exempt -- the
user's own words, "le province volanti... non hanno nessuna
variazione" -- and always use the single, ordinary land-terrain pass.
One useful emergent consequence, not special-cased separately: a Whale
unit on an Island now nets exactly half its normal Sea strength (0, the
off-Sea override, averaged with its full Sea value), matching "half
strength as if at sea" without this function needing to know Whales are
special here at all.
"""

from __future__ import annotations

import random

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import (
    ARMY_TABLE,
    BASE_STRENGTH,
    GARRISON_ATTACK_STRENGTH,
    GARRISON_DEFENSE_STRENGTH,
    OVERFLIGHT_AIR,
    RACE_TERRAIN_BONUS,
    RACE_TYPE_BONUS,
    ArmyType,
    is_nemesis_of,
)
from ak_engine.models.map import Terrain
from ak_engine.models.office import Office
from ak_engine.models.race import Race
from ak_engine.turn.cast_execution import illusory_fog_strength
from ak_engine.turn.combat import DEFENDER_BONUS, NEMESIS_PENALTY, Quality

# Rulebook: "Elephants are unpredictable in battle and can have a strength
# of anywhere between 2 and 5." No formula for the exact value -- rolled
# uniformly, a documented choice.
ELEPHANTS_STRENGTH_RANGE = (2, 5)

# Phase 691: `AdvancedAbility.DRUIDIC_DINOSAURS`'s own real description
# (`models/advanced_ability.py`) -- "Strength: Unpredictable (5 to 10)."
# Same "excluded from BASE_STRENGTH, rolled per-battle" treatment as
# Elephants above.
DINOSAURS_STRENGTH_RANGE = (5, 10)

# Rulebook: "An army fighting for a Divine kingdom has a 50% chance of
# becoming fanatical... Good kingdom... 40%... Evil kingdom... 25%." Every
# other alignment has no stated chance (treated as 0, not guessed higher).
# "A Skeletal army fighting under an Undead character has will always be
# fanatical" is modeled as the separate ``always_fanatical`` override.
# Phase 351 addendum: the same AK.EXE/AK.OVR source's own
# `battle_engine.special_events` table independently confirms these
# three exact percentages ("Divine fanaticism": 50, "Good fanaticism":
# 40, "Evil fanaticism": 25) from the compiled engine's own code.
FANATICISM_CHANCE: dict[Alignment, float] = {
    Alignment.DIVINE: 0.50,
    Alignment.GOOD: 0.40,
    Alignment.EVIL: 0.25,
}

# Phase 390: the same `battle_engine.special_events` table's own
# title-based fanaticism rows -- a *directly led* (``commanded_by`` is
# not ``None``) army of the matching race has this per-unit chance of
# becoming fanatical when its commander currently holds the
# race-matching title (``turn/race_titles.py RACE_TITLE_OFFICE``, the
# same "Savior of Humankind"/"First Elder of Elvenkind"/"King Under the
# Mountain"/"Khan of the Orcish Hordes"/racial-monster-King titles
# ``models/office.py OFFICE_NAME`` already carries flavor text for).
# Independent of and additive with ``FANATICISM_CHANCE`` above (that
# one keys off the *kingdom's* alignment; this one off the *army's own
# race* and its *commander's* title). The seven racial-monster titles
# (Dragon/Eagle/Whale/Merman/Ent/Troll/Werebeast) all share AKGEN's own
# single "50%" row ("Dragon/Eagle/Whale/Merman/Ent/Troll/Werebeast
# racial title"); Human/Elven/Dwarven/Orcish each have their own
# distinct, lower confirmed percentage.
TITLE_FANATICISM_CHANCE: dict[Office, float] = {
    Office.HUMAN_KING: 0.20,
    Office.ELVEN_KING: 0.35,
    Office.DWARVEN_KING: 0.40,
    Office.ORC_LORD: 0.45,
    Office.DRAGON_LORD: 0.50,
    Office.EAGLE_KING: 0.50,
    Office.WHALE_KING: 0.50,
    Office.MERMAN_KING: 0.50,
    Office.ENT_KING: 0.50,
    Office.TROLL_KING: 0.50,
    Office.WERE_KING: 0.50,
}

# Phase 351 addendum: the same AK.EXE/AK.OVR static reverse engineering
# as Phase 346-350's own battle-resolution corrections independently
# confirms all three of these rulebook-sourced numbers from the
# compiled battle engine's own code, not just the rulebook's text --
# `battle_engine.column_resolution.confirmed_multipliers` gives
# `exploration_max: 1.25` (== 1 + 0.25 here), `tactical_or_naval_per_
# level: 1.2` (== 1 + 0.20/level here), and `phantasmal_per_caster_
# level: 1.15` (== 1 + 0.15/level here). Zero correction needed -- all
# three already matched exactly.
# Phase 507: the real per-point rate (RUMORS.PAS's own `kexp * 0.0025`),
# superseding the pre-507 `MAX_EXPLORATION_ADVANTAGE = 0.25` gap-based
# cap this constant's own name described -- see exploration_advantage_
# multiplier()'s own Phase 507 addendum for why both figures agree at
# the ordinary 100% cap.
MAX_EXPLORATION_ADVANTAGE_PER_POINT = 0.0025
TACTICAL_BONUS_PER_LEVEL = 0.20
PHANTASMAL_ARMIES_BONUS_PER_LEVEL = 0.15

# Phase 757: AdvancedAbility.ENHANCED_ILLUSORY_TERRAIN's own real text --
# "armies fighting there will have their strength affected 67% by the
# illusory terrain, instead of 50%" -- the illusory side's own share of
# compute_effective_strength()'s Illusory Terrain blend when the caster
# held this ability (the real side gets the complementary 33%).
ENHANCED_ILLUSORY_TERRAIN_BLEND_WEIGHT = 0.67

# Phase 512: ``models/advanced_ability.py``'s own module docstring --
# "for each of the 15 Ability categories, reaching skill level 5...
# discontinues that ability's usual automatic per-level bonus (e.g.
# Tactical's 20%-per-level army-strength increase) and instead awards
# ONE Advanced Ability" -- so the +20%/level scaling below stops
# increasing past level 4; any further strength bonus comes only from
# actually holding a Tactical/Naval Mastery Advanced Ability (Tactical
# Mastery 10/15/20, Naval Mastery 10/Great 15/Exalted 20 -- see
# ``turn/battle_orchestrator.py``'s own ``_mastery_bonus_for``), not
# from the raw skill level continuing past 4. A leader at level 5+ who
# was instead awarded a *different* Advanced Ability from the same
# pool (e.g. Combined Arms) gets no further strength bonus at all here,
# matching the source's own "discontinues... and instead awards ONE"
# wording -- not every level-5+ character holds a Mastery tier.
TACTICAL_BONUS_LEVEL_CAP = 4

# Rulebook [4.32] DRUID TABLE, transcribed verbatim:
#   Level 1: Humans, Elves, Dwarves, Orcs, Mermen, Werebeasts
#   Level 2: Whales, Trolls
#   Level 3: Eagles, Ents
#   Level 4: Dragons
# Races with no entry (NO_RACE, SAURIAN, VAMPISH, ROHAN) aren't listed in
# the rulebook text available to this project -- treated as requiring no
# special Druidic skill (0), not guessed at a higher value.
DRUID_TABLE: dict[Race, int] = {
    Race.HUMAN: 1,
    Race.ELVEN: 1,
    Race.DWARVEN: 1,
    Race.ORCISH: 1,
    Race.MERMISH: 1,
    Race.WEREFOLK: 1,
    Race.WHALES: 2,
    Race.TROLLISH: 2,
    Race.EAGLES: 3,
    Race.ENTISH: 3,
    Race.DRAGONS: 4,
}


def roll_elephants_strength(rng: random.Random) -> int:
    return rng.randint(*ELEPHANTS_STRENGTH_RANGE)


def roll_dinosaurs_strength(rng: random.Random) -> int:
    return rng.randint(*DINOSAURS_STRENGTH_RANGE)


def compute_druidic_shortfall(leader_race: Race | None, army_race: Race, leader_druidic_skill: int) -> int:
    """Rulebook [4.32]: "With each level, Druids gain the ability to lead armies of
    races other than their own, as listed in the Druid Table. If a
    character attempts to lead an army when he has insufficient Druidic
    ability, the quality of the army suffers a decrease equal to his
    shortfall in Druidic ability."

    Leading an army of your *own* race never needs Druidic skill at all
    -- the rulebook's own framing is specifically about "races other
    than their own" -- so ``leader_race == army_race`` always returns 0,
    even for a race the Druid Table itself lists (e.g. a Whale leading
    Whales needs no Druidic skill, despite the table saying "Whales
    requires level 2" -- that entry is for a *non*-Whale leader).
    ``leader_race=None`` (no race data available for the leader, e.g. an
    independent Hero with no kingdom to derive one from) also returns 0
    -- insufficient data to judge a shortfall, not a guessed penalty.
    """

    if leader_race is None or leader_race == army_race:
        return 0
    required = DRUID_TABLE.get(army_race, 0)
    return max(0, required - leader_druidic_skill)


def roll_fanaticism(alignment: Alignment, rng: random.Random, *, always_fanatical: bool = False) -> bool:
    if always_fanatical:
        return True
    return rng.random() < FANATICISM_CHANCE.get(alignment, 0.0)


def roll_title_fanaticism(office: Office | None, rng: random.Random) -> bool:
    """Phase 390: the title-holder's own per-unit fanaticism roll --
    ``office`` is the title (if any) this army's own commander currently
    holds that matches the army's own race, resolved by the caller (see
    ``turn/battle_orchestrator.py _build_battle_units``'s own Phase 390
    addendum). ``None`` -- no matching title held, or the army is unled
    -- is a deterministic no-roll, matching ``roll_fanaticism``'s own
    "no chance recorded" convention.
    """

    if office is None:
        return False
    return rng.random() < TITLE_FANATICISM_CHANCE.get(office, 0.0)


def modified_quality(
    base_quality: Quality,
    *,
    desert_without_camels: bool = False,
    is_home_province: bool = False,
    is_fanatical: bool = False,
    druidic_shortfall: int = 0,
    race_item_bonus: int = 0,
) -> Quality:
    """Shift a quality level per the rulebook's quality-modifier list, clamped to Quality's range.

    ``race_item_bonus`` (Phase 279): a +1 for a race-matching legendary
    leadership item (Excalibur for Human, etc. -- see ``models/
    treasure.py RACE_LEADERSHIP_TREASURE`` and ``turn/army_quality.py``'s
    own docstring for the full derivation). Folded into the ARMIES
    report's "Modified Quality" column (``turn/army_quality.py``) and,
    since Phase 285, into real combat strength too, via
    ``compute_effective_strength()``'s own ``race_item_bonus`` parameter
    below. All modifiers are summed *before* the single clamp below,
    not applied in separate clamped steps -- a severe Druidic shortfall
    that would otherwise floor a unit at Depleted isn't rescued back up
    by a later +1 that a two-step clamp would let through. Defaults to
    0 so every pre-Phase-279 call site is unaffected.
    """

    level = int(base_quality)
    if desert_without_camels:
        level -= 1
    level -= druidic_shortfall
    if is_home_province:
        level += 1
    if is_fanatical:
        level += 1
    level += race_item_bonus
    level = max(int(Quality.DEPLETED), min(int(Quality.ELITE), level))
    return Quality(level)


def exploration_advantage_multiplier(own_explored_percent: int) -> float:
    """Rulebook: "the side with the better exploration... will also have up to a 25% advantage.

    **Phase 507**: superseded by the real formula (``RUMORS.PAS:389-403``,
    the user's third reverse-engineering dossier Part IV SS50.2):
    ``1 + own_explored_percent * 0.0025``, applied to *each side
    independently* off its own accumulated province knowledge -- not a
    relative "gap between the two sides" bonus the way the pre-507
    project-original interpolation modeled it (the enemy's own
    exploration never entered the real formula at all). At the ordinary
    100% cap this gives exactly the rulebook's own +25% -- the number
    Phase 351's own separate disassembly pass had already confirmed
    (``exploration_max: 1.25``) without yet knowing *how* the formula
    reached it; Military Maps (``turn/exploration.py``'s own Phase 507
    addendum) raising the cap to 200 is what unlocks the further +50%
    this same real formula allows, resolving what looked like two
    conflicting sourced maxima as one formula viewed at two different
    caps, not a contradiction.
    """

    return 1 + MAX_EXPLORATION_ADVANTAGE_PER_POINT * own_explored_percent


def combat_ability_multiplier(ability_level: int, *, mastery_bonus: float = 0.0) -> float:
    """Rulebook: "Tactical Ability +20% per level (or Naval ability in Sea provinces)".

    Caller picks which ability's level to pass in based on terrain.

    **Phase 512**: the per-level term is capped at ``TACTICAL_BONUS_
    LEVEL_CAP`` (4) -- see that constant's own docstring for why the
    automatic scaling stops there. ``mastery_bonus`` (default 0.0, so
    every pre-Phase-512 caller is unaffected for a level <=4 leader) is
    the flat bonus from actually holding a Tactical/Naval Mastery
    Advanced Ability, added on top of the capped per-level term -- the
    caller resolves which one, if any, applies (see ``turn/battle_
    orchestrator.py _mastery_bonus_for``).
    """

    return 1 + TACTICAL_BONUS_PER_LEVEL * min(ability_level, TACTICAL_BONUS_LEVEL_CAP) + mastery_bonus


def phantasmal_armies_multiplier(
    caster_illusion_level: int, *, bonus_per_level: float = PHANTASMAL_ARMIES_BONUS_PER_LEVEL
) -> float:
    """Rulebook (Regolamento AK.txt [4.23.2]): "la forza delle unita' militari che
    egli comanda aumenta del 15% per livello d'abilita'" -- Phantasmal
    Armies' strength bonus, keyed by the *caster's* Illusionist skill
    level at cast time (not the commanding leader's, if different --
    "chi lo lancia evoca eserciti fantasma" (evoked by the caster) "che
    viaggiano con lui (o con un personaggio situato nella stessa
    provincia)": the phantom armies travel with whoever the spell
    targets, but their number/potency is the caster's own). "L'uso
    ripetuto di questo incantesimo non ha effetto cumulativo" (repeated
    casts don't stack) is enforced by the caller storing (not adding)
    ``LeaderState.phantasmal_armies_level`` -- see ``turn/
    cast_execution.py``'s ``_execute_illus_armies``.

    ``bonus_per_level`` (Phase 270): Observation Balloons (Discovery.txt)
    -- "army strength is increased by only 5% per skill level" instead
    of the base 15%, when the *opposing* Kingdom in this particular
    battle owns the Discovery. The caller (``turn/battle_orchestrator.py
    _build_battle_units``) resolves which value applies; this function
    stays agnostic to Discoveries, same as every other strength-pipeline
    step here.
    """

    return 1 + bonus_per_level * caster_illusion_level


def _base_strength(army_type: ArmyType, *, is_defender: bool, base_strength_override: float | None) -> float:
    if base_strength_override is not None:
        return base_strength_override
    if army_type is ArmyType.GARRISON:
        return GARRISON_DEFENSE_STRENGTH if is_defender else GARRISON_ATTACK_STRENGTH
    if army_type is ArmyType.ELEPHANTS:
        raise ValueError(
            "Elephants have variable strength (2-5); roll it with roll_elephants_strength() "
            "and pass it as base_strength_override"
        )
    return BASE_STRENGTH[army_type]


def _terrain_strength(
    army_type: ArmyType,
    race: Race,
    terrain: Terrain,
    *,
    is_defender: bool,
    base_strength_override: float | None,
    adapt_tactics_to_terrain: bool = False,
) -> float:
    """The terrain-dependent portion of the strength pipeline only -- base
    strength, race/army-type terrain bonuses, adverse-terrain halving, and
    Whales' off-Sea zero-strength override. Extracted (Phase 282) so
    ``compute_effective_strength()`` can call this twice (once per
    terrain) and average the results for an Island-province battle --
    see that function's own ``is_island`` parameter and the module
    docstring's Phase 282 section.

    ``adapt_tactics_to_terrain`` (Advanced Ability, Phase 513): "When a
    character directly leads a unit at a battle, the effect of adverse
    terrain is reduced. The unit is reduced to 75% of normal strength,
    instead of 50%." -- a per-unit override of the ordinary adverse-
    terrain halving below (0.75 instead of 0.5), resolved by the caller
    from whether *this specific army's own commander* (not necessarily
    the side's Supreme Commander) holds the ability. Defaults to
    ``False`` (unchanged 50% halving) for every pre-Phase-513 caller.
    """

    if army_type is ArmyType.WHALES and terrain is not Terrain.SEA:
        return 0.0

    strength = _base_strength(army_type, is_defender=is_defender, base_strength_override=base_strength_override)

    if RACE_TYPE_BONUS.get((race, army_type)):
        strength += 1
    if RACE_TERRAIN_BONUS.get((race, terrain)):
        strength += 1
    stats = ARMY_TABLE.get(army_type)
    if stats is not None and terrain in stats.home_terrain:
        strength += 1
    if stats is not None and terrain in stats.adverse_terrain:
        strength *= 0.75 if adapt_tactics_to_terrain else 0.5

    return strength


def compute_effective_strength(
    army_type: ArmyType,
    race: Race,
    base_quality: Quality,
    terrain: Terrain,
    *,
    is_defender: bool = False,
    is_home_province: bool = False,
    is_fanatical: bool = False,
    desert_without_camels: bool = False,
    druidic_shortfall: int = 0,
    race_item_bonus: int = 0,
    own_explored_percent: int = 0,
    combat_ability_level: int = 0,
    combat_ability_mastery_bonus: float = 0.0,
    phantasmal_armies_level: int = 0,
    phantasmal_armies_bonus_per_level: float = PHANTASMAL_ARMIES_BONUS_PER_LEVEL,
    opponent_army_type: ArmyType | None = None,
    base_strength_override: float | None = None,
    illusory_fog_affected: bool = False,
    is_island: bool = False,
    illusory_terrain: Terrain | None = None,
    illusory_terrain_enhanced: bool = False,
    adapt_tactics_to_terrain: bool = False,
) -> float:
    """Full effective-strength pipeline, in the rulebook's documented order.

    Does NOT apply the random-event factor -- that's rolled once per
    front-line unit / once per battle in ``turn/battle_luck.py`` and
    applied in ``turn/battle_resolution.py``, to keep randomness in one
    place.

    **Whales off-sea** (Phase 37): "Whales: When fighting in any terrain
    other than Sea, they have zero strength." An unconditional override,
    not the generic adverse-terrain halving ``ARMY_TABLE``'s own
    ``adverse_terrain`` entry for Whales would otherwise apply -- checked
    first and short-circuits the rest of this pipeline (quality,
    defender bonus, etc. would all still multiply a nonzero base by
    something, and the rule says exactly zero, not "reduced").

    **Illusory Fog** (Phase 207 addendum, wired Phase 249): "All air
    units... have their strength halved for any battle in the affected
    province." ``illusory_fog_affected`` is the caller's own combined
    "is this unit an air unit (or Mystic-Winds-affected) AND is this
    province's ``ProvinceState.illusory_fog_active`` set" answer -- see
    ``turn/cast_execution.py illusory_fog_strength()``/``is_illusory_
    fog_affected_air_unit()``, whose own docstrings note neither was
    called from here until now. Defaults to ``False`` (no effect) for
    every pre-Phase-249 caller.

    **Island provinces** (Phase 282, ``is_island``): see the module
    docstring's own Phase 282 section for the full derivation. Runs
    ``_terrain_strength()`` twice (land ``terrain`` and ``Terrain.SEA``)
    and averages when ``True`` and ``army_type`` isn't an overflight-air
    unit; a single ordinary pass otherwise. Defaults to ``False`` for
    every pre-Phase-282 caller, unaffected.

    **Illusory Terrain** (Phase 724, ``illusory_terrain``): rulebook
    [4.23.1] -- see the module docstring's own Phase 724 section. When
    set to a real ``Terrain``, a *second*, independent blend runs on top
    of whatever the step above already produced (the ordinary single
    pass, or the Island land/Sea average) -- an ordinary single pass
    against ``illusory_terrain`` itself (no Island-style blending on
    this side; the illusion presents one chosen terrain, not two), then
    the two results are averaged 50/50. No air-unit exemption, unlike
    ``is_island``. Defaults to ``None`` (no effect) for every pre-Phase-
    724 caller, unaffected.

    **Enhanced Illusory Terrain** (Phase 757, ``illusory_terrain_
    enhanced``): ``AdvancedAbility.ENHANCED_ILLUSORY_TERRAIN``'s own
    text -- "armies fighting there will have their strength affected
    67% by the illusory terrain, instead of 50%" -- widens the blend
    above from an even split to ``ENHANCED_ILLUSORY_TERRAIN_BLEND_
    WEIGHT`` (0.67) on the illusory side / 0.33 on the real side.
    Meaningless when ``illusory_terrain is None`` (no blend to widen);
    defaults to ``False`` (the base 50/50 split) for every pre-Phase-757
    caller, unaffected. The ability's own other clause (a random race/
    army-type illusion shown to an outside observer) is a report-layer
    effect, not a combat one -- not modeled here.

    **Race-matching legendary leadership item** (Phase 279/285,
    ``race_item_bonus``): passed straight through to ``modified_
    quality()``'s own parameter of the same name -- see that function's
    docstring. Defaults to 0 for every pre-Phase-285 caller, unaffected.

    **Adapt Tactics to Terrain** (Advanced Ability, Phase 513,
    ``adapt_tactics_to_terrain``): passed straight through to
    ``_terrain_strength()``'s own parameter of the same name -- see that
    function's docstring. Defaults to ``False`` for every pre-Phase-513
    caller, unaffected.
    """

    if is_island and army_type not in OVERFLIGHT_AIR:
        land_strength = _terrain_strength(
            army_type, race, terrain, is_defender=is_defender, base_strength_override=base_strength_override,
            adapt_tactics_to_terrain=adapt_tactics_to_terrain,
        )
        sea_strength = _terrain_strength(
            army_type, race, Terrain.SEA, is_defender=is_defender, base_strength_override=base_strength_override,
            adapt_tactics_to_terrain=adapt_tactics_to_terrain,
        )
        real_strength = (land_strength + sea_strength) / 2
    else:
        real_strength = _terrain_strength(
            army_type, race, terrain, is_defender=is_defender, base_strength_override=base_strength_override,
            adapt_tactics_to_terrain=adapt_tactics_to_terrain,
        )

    if illusory_terrain is not None:
        illusory_strength = _terrain_strength(
            army_type, race, illusory_terrain, is_defender=is_defender, base_strength_override=base_strength_override,
            adapt_tactics_to_terrain=adapt_tactics_to_terrain,
        )
        illusory_weight = ENHANCED_ILLUSORY_TERRAIN_BLEND_WEIGHT if illusory_terrain_enhanced else 0.5
        strength = real_strength * (1.0 - illusory_weight) + illusory_strength * illusory_weight
    else:
        strength = real_strength

    quality = modified_quality(
        base_quality,
        desert_without_camels=desert_without_camels,
        is_home_province=is_home_province,
        is_fanatical=is_fanatical,
        druidic_shortfall=druidic_shortfall,
        race_item_bonus=race_item_bonus,
    )
    strength *= int(quality)

    if is_defender:
        strength *= DEFENDER_BONUS
    strength *= exploration_advantage_multiplier(own_explored_percent)
    strength *= combat_ability_multiplier(combat_ability_level, mastery_bonus=combat_ability_mastery_bonus)
    strength *= phantasmal_armies_multiplier(phantasmal_armies_level, bonus_per_level=phantasmal_armies_bonus_per_level)
    strength = illusory_fog_strength(strength, affected=illusory_fog_affected)
    if opponent_army_type is not None and is_nemesis_of(army_type, opponent_army_type):
        strength *= NEMESIS_PENALTY

    return strength
