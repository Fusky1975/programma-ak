"""Feature -> Power [5.8] "special function or event" execution -- Phase 616.

`Special Features.md` (a user-supplied direct `AK.EXE`/`AKE.EXE`/
`AK.OVR`/`AKGEN.EXE` disassembly reverse-engineering report, 2026-08-22)
resolved the blocker Phase 613's own investigation found: "per-feature
target data ... is modeled nowhere at all." The real answer is that
nothing is stored per-Feature at all -- `magfeat`/`power`/its ability-
or-race-or-temper-or-spell parameter/its `PowerCondition`/its cost are
all a pure deterministic function of `(feature_index, feature_type,
feature_x, feature_y)`, recomputed by `Set_Event` every time, never a
stored byte. `worldgen/internal_magical_locations.py`'s own Phase
361/365 formulas (independently built, months earlier) already matched
this new document's own `Set_Event` formulas exactly when cross-checked
directly -- strong confirmation the document is trustworthy, not just
another claim to take on faith. This module is the genuine *new* half:
Phase 616 only wired the *derivation*, never its *execution*.

**Scope of this phase (9 of the 25 real `Power`s)**: every `Power` whose
real effect is a direct, already-modeled `LeaderState` mutation or a
discovery-reveal with an existing consumer, and no player-supplied
argument -- `NEW_SEX`, `NEW_TEMP`, `NEW_RACE`, `UP_SKILL`, `UP_APT`,
`DN_SKILL`, `DN_APT`, `MAP_FEAT`, `SAGE_DISC`. The full `PowerCondition`/
cost/consent gating (`resolve_feature_power_attempt()`'s own early
section) is built completely, all 7 conditions, since every later phase
needs the same system -- built once, correctly, here, even though this
phase's own 9 powers only ever reach `PC_NONE`/`PAY_UP`/`SAME_ALIGN`/
`DRAIN_COURAGE` in practice (confirmed by checking `POWER_CONDITION_
PAIRS` for exactly these 9 keys).

**`MAP_PROV` deliberately excluded from this phase's own "tractable"
bucket, despite being scoped in there originally**: the real effect
("reveal 3-5 unknown lands, their inhabitants, location and ruler")
needs a per-Kingdom "which provinces are currently known" tracking
concept -- confirmed absent anywhere in this project (`GameState`'s own
`kingdoms_met`/`kingdoms_met_since` track diplomatic contact only,
nothing at the province level; `ProvinceState.owner_kingdom_id` is
ownership, not a visibility/knowledge flag). Wiring `MAP_PROV` for real
needs that tracking concept built first -- left for a later phase
rather than inventing one here.

**`SAGE_DISC`'s own selection is a documented simplification, not a
guess**: the source says "privilegiando il valore/difficoltà minore
osservato" (favoring the lowest observed difficulty), but this project
has no `Discovery` difficulty/value table anywhere (confirmed absent by
grep) -- `Discovery`'s own enum declaration order has no confirmed
correspondence to real in-game difficulty. Rather than invent an
ordering, `_reveal_sage_discoveries()` below picks uniformly at random
among the Kingdom's own not-yet-known `Discovery` members -- the
"how many" count (`1 + IRand & 3`) and the "no Chancellor merit credit"
rule are both fully sourced and implemented exactly; only the specific
tie-break ordering among candidates is a stand-in.

**Not credited to any `MeritTally`**: `MAP_FEAT`/`SAGE_DISC` explicitly
grant no Chancellor-office merit (`FPDESC.X2`'s own text, corroborated
by section 5.3) -- this module never touches `MeritTally.features_
discovered_first`/`.discoveries_found_first`, both scoped to Explore's
own and Practice's own separate, already-wired mechanics.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, replace

from ak_engine.models.alignment import Alignment
from ak_engine.models.discovery import Discovery
from ak_engine.models.enums import Ability
from ak_engine.models.feature import Feature
from ak_engine.models.game_state import GameState, LeaderState
from ak_engine.models.magic_feature import MagicFeature
from ak_engine.models.power import Power, PowerCondition
from ak_engine.models.race import Race
from ak_engine.models.sex import Sex
from ak_engine.models.temper import Temper
from ak_engine.worldgen.internal_magical_locations import (
    POWER_CONDITION_PAIRS,
    damp_college_ability_parameter,
    power_ability_parameter,
    power_condition_cost,
    power_race_parameter,
    power_temper_parameter,
    resolve_power,
    resolve_power_condition,
    resolve_required_alignment,
    resolve_visible_location,
)

# FPDESC.X2's own "up to a maximum of 4" -- real for UP_SKILL, source-
# confirmed stale for UP_APT (see power_condition_cost's own module).
MAX_SKILL_LEVEL = 4
# AK.OVR:0x12828's own real binary cap, overriding FPDESC.X2's stale
# "maximum of 4" text for UP_APT specifically (Special Features.md
# section 3.1, "il limite da usare è 5; il testo è obsoleto/incoerente").
MAX_APTITUDE_LEVEL = 5

TRACTABLE_POWERS = frozenset(
    {
        Power.NEW_SEX,
        Power.NEW_TEMP,
        Power.NEW_RACE,
        Power.UP_SKILL,
        Power.UP_APT,
        Power.DN_SKILL,
        Power.DN_APT,
        Power.MAP_FEAT,
        Power.SAGE_DISC,
    }
)


@dataclass(slots=True, frozen=True)
class FeaturePowerEvent:
    """One `Feature`'s own fully-derived `Set_Event` outcome -- the
    "closed at algorithm/data level" claim `Special Features.md` makes,
    finally assembled end to end. Always resolvable for *any* real
    `Feature` (this is what "nothing is stored, always recompute" means
    in practice) -- `power` is `Power.PNONE` for the ~55% of real
    Features with no power at all (parity/Gastrap-Seal, see
    `resolve_visible_location()`), not a missing value.
    """

    power: Power
    magic_feature: MagicFeature
    ability_parameter: Ability | None = None
    race_parameter: Race | None = None
    temper_parameter: Temper | None = None
    condition: PowerCondition = PowerCondition.PC_NONE
    cost: int = 0
    required_alignment: Alignment | None = None


def derive_feature_event(feature: Feature) -> FeaturePowerEvent:
    """The real `Set_Event` derivation, recomputed fresh from `feature`'s
    own immutable identity (`feature_id`, `kind`, `coord.x`) every call
    -- deliberately never reads `feature.magic_location`/`.magic_power`
    (Phase 365's own *cached* copy of the same two formulas), matching
    the real engine's own "never trust a stored value" semantics exactly
    rather than a project-specific optimization's side effect. Cross-
    checked directly against 6 of `Special Features.md`'s own section 8
    real-`GW3__T1` rows (F#5/7/16/27/42/51/62/85/91/113 across multiple
    powers) -- see `tests/test_feature_power_execution.py`.
    """

    location = resolve_visible_location(feature.kind, feature.feature_id, feature.coord.x)
    power = resolve_power(location, feature.feature_id, feature.kind.value)

    ability_parameter: Ability | None = None
    race_parameter: Race | None = None
    temper_parameter: Temper | None = None
    if power in (Power.UP_SKILL, Power.UP_APT, Power.DN_SKILL, Power.DN_APT):
        ability_parameter = power_ability_parameter(feature.kind, feature.feature_id)
    elif power is Power.DAMP_COLLEGE:
        ability_parameter = damp_college_ability_parameter(feature.kind, feature.feature_id)
    elif power is Power.NEW_TEMP:
        temper_parameter = power_temper_parameter(feature.kind, feature.feature_id)
    elif power is Power.NEW_RACE:
        race_parameter = power_race_parameter(feature.kind, feature.feature_id)

    condition = PowerCondition.PC_NONE
    cost = 0
    required_alignment: Alignment | None = None
    pair = POWER_CONDITION_PAIRS.get(power)
    if pair is not None:
        condition = resolve_power_condition(power, feature.kind, feature.feature_id, feature.coord.x)
        cost = power_condition_cost(condition, pair[2])
        if condition is PowerCondition.SAME_ALIGN:
            required_alignment = resolve_required_alignment(feature.kind, feature.feature_id, feature.coord.x)

    return FeaturePowerEvent(
        power=power,
        magic_feature=location,
        ability_parameter=ability_parameter,
        race_parameter=race_parameter,
        temper_parameter=temper_parameter,
        condition=condition,
        cost=cost,
        required_alignment=required_alignment,
    )


@dataclass(slots=True, frozen=True)
class FeaturePowerAttemptResult:
    """One resolved attempt to use a `Feature`'s own power -- `applied`
    tells the caller whether the real effect happened at all; the rest
    are populated only for the specific `power`/outcome that occurred,
    for `report/turn_report.py` to narrate.
    """

    power: Power
    applied: bool
    reason: str | None = None  # set when applied is False
    already_matched: bool = False  # NEW_TEMP/NEW_RACE's own real no-op (already that value)
    at_limit: bool = False  # UP_SKILL/UP_APT/DN_SKILL/DN_APT's own real no-op (already capped/floored)
    ability: Ability | None = None
    new_skill_level: int | None = None
    new_aptitude_level: int | None = None
    new_temper: Temper | None = None
    new_race: Race | None = None
    new_sex: Sex | None = None
    revealed_feature_id: int | None = None
    revealed_discoveries: tuple[Discovery, ...] = ()
    # Phase 616: the Feature's own derived `MagicFeature` (``POWMSG.X2``'s
    # own ``$\`` marker, see ``report/turn_report.py describe_feature_
    # power_attempt()``) -- always populated by ``resolve_feature_power_
    # attempt()`` regardless of outcome, since every real POWMSG message
    # this project reaches names the magic object itself.
    magic_feature: MagicFeature | None = None


def _apply_condition_gate(
    state: GameState, leader_id: int, feature: Feature, event: FeaturePowerEvent, rng: random.Random
) -> str | None:
    """Checks/applies `event.condition` -- returns a real refusal reason
    string, or `None` if the attempt may proceed. Mutates `state`
    (treasury debit, skill drain, temper drain) only on a real accepted
    cost; a refusal never partially applies a cost.
    """

    leader = state.leaders[leader_id]

    if event.condition is PowerCondition.NEED_KING and not leader.is_king:
        return "only a King may use this power"
    if event.condition is PowerCondition.SAME_ALIGN and leader.alignment is not event.required_alignment:
        return "wrong alignment"
    if event.condition is PowerCondition.G_TURN and feature.power_used_turn == state.turn_number:
        return "already used this gameturn"

    if event.condition is PowerCondition.PAY_UP:
        kingdom = state.kingdoms.get(leader.kingdom_id) if leader.kingdom_id is not None else None
        if kingdom is None or kingdom.treasury < event.cost:
            return "insufficient gold"
        kingdom.treasury -= event.cost
    elif event.condition is PowerCondition.DRAIN_SKILL:
        if leader.skills is None:
            return "insufficient skill levels"
        drained = 0
        skills = leader.skills
        for _ in range(event.cost):
            candidates = [ability for ability in Ability if skills.pair_for_ability(ability)[0] > 0]
            if not candidates:
                break
            ability = candidates[rng.randrange(len(candidates))]
            skill, aptitude = skills.pair_for_ability(ability)
            skills.set_pair_for_ability(ability, skill - 1, aptitude)
            drained += 1
        if drained < event.cost:
            return "insufficient skill levels"
    elif event.condition is PowerCondition.DRAIN_COURAGE:
        if leader.temper is None or leader.temper is Temper.COWARDLY:
            return "a Coward may not use this feature"
        leader.temper = Temper(leader.temper.value - 1)

    return None


def resolve_feature_power_attempt(
    state: GameState, leader_id: int, feature: Feature, event: FeaturePowerEvent, rng: random.Random
) -> FeaturePowerAttemptResult:
    """Applies `event`'s own real effect for `leader_id`, gating on
    `event.condition` first (`_apply_condition_gate()`). Only the 9
    `TRACTABLE_POWERS` have a real effect branch below -- called by
    `turn/search_execution.py _apply_scout()` only for those 9 (see
    that module's own Phase 616 addendum); any other `Power` reaching
    here (a future phase's own bug, not a real caller today) returns an
    unapplied result rather than guessing an effect.

    Thin wrapper around `_resolve_feature_power_attempt_effect()`: stamps
    `event.magic_feature` onto every real outcome (POWMSG.X2's own
    ``$\\`` marker, see `report/turn_report.py describe_feature_power_
    attempt()`) without every one of that function's own many early
    returns having to repeat it.
    """

    result = _resolve_feature_power_attempt_effect(state, leader_id, feature, event, rng)
    return replace(result, magic_feature=event.magic_feature)


def _resolve_feature_power_attempt_effect(
    state: GameState, leader_id: int, feature: Feature, event: FeaturePowerEvent, rng: random.Random
) -> FeaturePowerAttemptResult:
    power = event.power
    if power not in TRACTABLE_POWERS:
        return FeaturePowerAttemptResult(power=power, applied=False, reason="power not yet wired")

    refusal = _apply_condition_gate(state, leader_id, feature, event, rng)
    if refusal is not None:
        return FeaturePowerAttemptResult(power=power, applied=False, reason=refusal)

    if event.condition is PowerCondition.G_TURN:
        feature.power_used_turn = state.turn_number

    leader = state.leaders[leader_id]

    if power is Power.NEW_SEX:
        # A leader whose sex was never recorded (`None`, e.g. most Heroes
        # -- only King creation writes this field, Phase 260) has no real
        # "current value" to invert; toggling from an assumed MALE is a
        # low-stakes default (either starting point is a real, symmetric
        # outcome), not a sourced magnitude.
        leader.sex = Sex.FEMALE if leader.sex is Sex.MALE else Sex.MALE
        return FeaturePowerAttemptResult(power=power, applied=True, new_sex=leader.sex)

    if power is Power.NEW_TEMP:
        if leader.temper is event.temper_parameter:
            return FeaturePowerAttemptResult(
                power=power, applied=True, already_matched=True, new_temper=event.temper_parameter
            )
        leader.temper = event.temper_parameter
        return FeaturePowerAttemptResult(power=power, applied=True, new_temper=event.temper_parameter)

    if power is Power.NEW_RACE:
        if leader.race is event.race_parameter:
            return FeaturePowerAttemptResult(
                power=power, applied=True, already_matched=True, new_race=event.race_parameter
            )
        leader.race = event.race_parameter
        return FeaturePowerAttemptResult(power=power, applied=True, new_race=event.race_parameter)

    if power in (Power.UP_SKILL, Power.UP_APT, Power.DN_SKILL, Power.DN_APT):
        ability = event.ability_parameter
        assert ability is not None
        if leader.skills is None:
            return FeaturePowerAttemptResult(power=power, applied=False, reason="no skill data recorded")
        skill, aptitude = leader.skills.pair_for_ability(ability)

        if power is Power.UP_SKILL:
            if skill >= MAX_SKILL_LEVEL:
                return FeaturePowerAttemptResult(power=power, applied=True, at_limit=True, ability=ability)
            deficiency = max(0, skill - aptitude + 1)
            if rng.random() >= (0.5**deficiency):
                return FeaturePowerAttemptResult(power=power, applied=False, reason="the roll failed", ability=ability)
            leader.skills.set_pair_for_ability(ability, skill + 1, aptitude)
            return FeaturePowerAttemptResult(power=power, applied=True, ability=ability, new_skill_level=skill + 1)

        if power is Power.UP_APT:
            if aptitude >= MAX_APTITUDE_LEVEL:
                return FeaturePowerAttemptResult(power=power, applied=True, at_limit=True, ability=ability)
            leader.skills.set_pair_for_ability(ability, skill, aptitude + 1)
            return FeaturePowerAttemptResult(power=power, applied=True, ability=ability, new_aptitude_level=aptitude + 1)

        if power is Power.DN_SKILL:
            if skill <= 0:
                return FeaturePowerAttemptResult(power=power, applied=True, at_limit=True, ability=ability)
            leader.skills.set_pair_for_ability(ability, skill - 1, aptitude)
            return FeaturePowerAttemptResult(power=power, applied=True, ability=ability, new_skill_level=skill - 1)

        # Power.DN_APT
        if aptitude <= 0:
            return FeaturePowerAttemptResult(power=power, applied=True, at_limit=True, ability=ability)
        leader.skills.set_pair_for_ability(ability, skill, aptitude - 1)
        return FeaturePowerAttemptResult(power=power, applied=True, ability=ability, new_aptitude_level=aptitude - 1)

    if power is Power.MAP_FEAT:
        return _reveal_unknown_feature(state, leader, rng)

    # Power.SAGE_DISC
    return _reveal_sage_discoveries(state, leader, rng)


def _reveal_unknown_feature(state: GameState, leader: LeaderState, rng: random.Random) -> FeaturePowerAttemptResult:
    """`MAP_FEAT` (section 5.3): "tell you of one previously unknown
    feature in your Kingdom" -- bumps one still-undiscovered (`fdisc ==
    0`) Feature to `fdisc == 1` ("Feature noto", a `?` in the Special
    column -- knowing it exists, not its power), the weakest real
    non-zero tier, matching the text's own "tell you of" (existence)
    rather than a stronger reveal the text doesn't claim.
    """

    if leader.kingdom_id is None:
        return FeaturePowerAttemptResult(power=Power.MAP_FEAT, applied=False, reason="no Kingdom to record this for")
    unknown = [f for f in state.features.values() if f.discovery_level(leader.kingdom_id) == 0]
    if not unknown:
        return FeaturePowerAttemptResult(power=Power.MAP_FEAT, applied=False, reason="no more features to reveal")
    feature = unknown[rng.randrange(len(unknown))]
    feature.discovered_by_kingdom[leader.kingdom_id] = 1
    return FeaturePowerAttemptResult(power=Power.MAP_FEAT, applied=True, revealed_feature_id=feature.feature_id)


def _reveal_sage_discoveries(state: GameState, leader: LeaderState, rng: random.Random) -> FeaturePowerAttemptResult:
    """`SAGE_DISC` (section 5.3): "reveal one discovery" per scout,
    `1 + (IRand AND 3)` selections (1-4) -- see module docstring for why
    the real "lowest difficulty first" tie-break is a documented
    uniform-random substitute here, not a guess at the missing
    ordering. No Chancellor merit credit (confirmed, not touched).
    """

    if leader.kingdom_id is None:
        return FeaturePowerAttemptResult(power=Power.SAGE_DISC, applied=False, reason="no Kingdom to record this for")
    kingdom = state.kingdoms.get(leader.kingdom_id)
    if kingdom is None:
        return FeaturePowerAttemptResult(power=Power.SAGE_DISC, applied=False, reason="no Kingdom to record this for")
    unknown = [d for d in Discovery if d not in kingdom.discoveries]
    if not unknown:
        return FeaturePowerAttemptResult(power=Power.SAGE_DISC, applied=False, reason="no more discoveries to reveal")
    count = min(len(unknown), 1 + rng.randrange(4))
    rng.shuffle(unknown)
    revealed = tuple(unknown[:count])
    kingdom.discoveries.update(revealed)
    return FeaturePowerAttemptResult(power=Power.SAGE_DISC, applied=True, revealed_discoveries=revealed)
