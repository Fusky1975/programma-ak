"""Monster-raid resolution -- rulebook [9.2]'s own "monster devastation"
tax reduction, plus the underlying guardian-maturation state machine that
feeds it, and Divine King's own raid-blocking perk. Fully resolved by
``Desktop/THUNDERBIRD.md`` (user-supplied reverse-engineering document,
2026-08-28), closing two previously-confirmed-absent gaps at once: this
project's own royal-title system had "no monster-raid mechanic anywhere"
as the last blocker on Divine King's perk (see ``turn/office_holder.py``
alignment-King bonuses and ``project_royal_titles_phase630_closed``
memory), and ``turn/tax_base.py``'s own module docstring named this exact
mechanic as "no recoverable trigger probability or magnitude anywhere in
the source" -- both now resolved with real, sourced formulas.

**Season -> phase mapping, user-confirmed directly (2026-08-28)**: this
project has no ``Season``/calendar concept anywhere (``models/turn.py
Turn.season`` is an unused, never-instantiated stub). The 5 named seasons
(Spring/Early Summer/Late Summer/Fall/Early Winter) are simply this
project's own existing 5 phases per turn, in order -- ``P0=Spring,
P1=Early Summer, P2=Late Summer, P3=Fall, P4=Early Winter`` ("mimics
medieval reality: no fighting or moving in Winter"). Seasonal maturation
(``age_all_feature_guardians()``) is therefore gated on ``phase_index >=
3`` by its one caller, ``turn/turn_processor.py run_turn()`` -- not
modeled inside this module, which stays phase-agnostic.

**Guardian maturation** (``Age_Feature_Monsters``, THUNDERBIRD.md section
11): each turn, in Fall/Early Winter only, every feature with a real
guardian gets a 3% chance to attempt maturation; on a hit, a second roll
picks a "Worldly" or "Animal" alignment threshold (``models/alignment.py``
own docstring: "Worldly displays as Neutral... Animal displays as Pagan"
-- ``ALIGNMENT_ORDINAL[Alignment.NEUTRAL] == 3``/``[Alignment.PAGAN] ==
4``, exactly THUNDERBIRD.md's own two threshold values) that the
guardian's own ``Feature.guardian_alignment`` must meet or exceed; on a
pass, the guardian advances one step, ``Calm -> Mercenary -> Bold``
(every other state, including an already-``looted`` Dead feature, is a
no-op -- but the real Pascal consumes both rolls regardless, matching
that fidelity rather than adding an early-out this project's own sources
don't support).

**Raid resolution** (``Resolve_Feature_Raids``, THUNDERBIRD.md sections
9-10): only a ``BOLD``, non-looted, non-hidden guardian can raid. A
temperament-based activity check (Cowardly 25% / Cautious 50% / Brave
75% / Berserk 100%, via ``MONSTER_RUNTIME_PROFILE[monster].temper``) must
pass first. The ``Build_Raid_Profile``/``noarmy`` eligibility gate named
in the source has no recoverable algorithm for which monsters it would
exclude -- **deliberately not modeled**, every Bold+active monster is
treated as passing it, the same "confirmed real but unrecoverable
magnitude, treat as inert" precedent this project uses extensively
elsewhere. Then the Thunderbird check: 40% chance, blocked ONLY IF the
province's owning King currently holds ``Office.DIVINE_KING`` (Divine
Archangel) AND no Thunderbird intervention has happened yet this ENTIRE
turn (one single global flag, max 1 intervention per turn across the
whole game) -- on success, zero damage, guardian reverts to
``MERCENARY``; on an ordinary raid, damage ``= floor(mtbasehp * current_
province_income / 70) + 1``, subtracted from the turn's calculated
income ONLY (never the persisted ``ProvinceState.tax``/tax base -- see
``turn/tax_base.py``'s own module docstring), guardian stays ``BOLD``.

**Phase 671 closed the other two pacification triggers** section 4.2
names: ``apply_fulfill_pacification()`` (the exact compiled ``AK.OVR``
snippet, applied -- per the user's own direct 2026-08-29 choice -- to
ANY successfully-honored Fulfill deal against a Feature's guardian,
since this project's own Fulfill mechanic is already deliberately
abstract about deal content) and, at the time, a project-original
guess at the intimidation trigger (no recoverable algorithm survived
anywhere in THUNDERBIRD.md for it -- only the resulting report message
ids). Phase 672 added report narration for both, also project-original
for lack of the literal English ``Say()`` text.

**Phase 673 supersedes the intimidation guess with the real, sourced
formula.** A second reverse-engineering document, ``Desktop/BOLD
OK.txt`` (2026-08-29), fully recovers it: intimidation is a
**per-damage-packet, independent roll** (``AK.OVR`` raw
``0x1651A-0x16607``), not an end-of-combat total-loss check --
``p(d,t,m) = min(1, d*(4-t)/mtbasehp[m])`` for each packet of damage
``d`` a ``Bold`` guardian takes, where ``t`` is its current combat
Temper ordinal and ``mtbasehp[m]`` is the species' own base HP constant
(``MONSTER_RUNTIME_PROFILE[monster].average_hit_points``, the same
value Phase 670's own raid-damage formula already uses). The first
successful packet sets a sticky per-encounter flag, applied to
``guardian_state`` only at combat closure -- see ``roll_guardian_
intimidation()`` below. BOLD OK.txt also recovers a second real
outcome this project never modeled, ``_MUnDt`` ("wounded but
undeterred" -- no state change, stays ``Bold``, see ``guardian_
undeterred()`` below), and the literal English ``Say()`` text for all
three of Phase 672's own project-original report lines (now wired
verbatim in ``report/turn_report.py``).

**Independent confirmation, not just new claims**: BOLD OK.txt's own
seasonal-promotion algorithm (its section 6) reconstructs the exact
same 3%/Worldly-Animal/``Calm->Mercenary->Bold`` mechanism Phase 670
already built independently from THUNDERBIRD.md -- real, external
confirmation that ``age_feature_guardian()`` below needed no changes.

Also out of scope, still: ``Maybe_Repopulate_Dead_Feature`` (no precise
algorithm given), seeding *initial* Bold guardians at world generation
(every world-generated feature starts at ``MERCENARY`` and matures
naturally via real turns' own Fall/Early-Winter rolls), and threading
damage-dealing spells (Fireball, Ice Suspension, Telekinetic Storm,
Holy Symbol, Spiritwrack) into the intimidation packet list -- only
Melee swings and Fire Arrow shots are modeled as packets (see ``turn/
search_execution.py``'s own Phase 673 addendum for why).
"""

from __future__ import annotations

import random

from ak_engine.models.alignment import ALIGNMENT_ORDINAL, Alignment
from ak_engine.models.feature import Feature, RaidEvent
from ak_engine.models.game_state import GameState, ProvinceState
from ak_engine.models.monster import MONSTER_RUNTIME_PROFILE, MonsterEngagementState
from ak_engine.models.temper import Temper

MONSTER_MATURATION_ROLL_CHANCE = 0.03
# THUNDERBIRD.md section 11: the "Worldly" (Neutral) / "Animal" (Pagan)
# threshold roll, ``outlook(3 + RZero_One)`` -- a 50/50 pick, expressed as
# ``rng.random() < 0.5`` (this project's own established idiom for a
# binary roll, e.g. `turn/encounter.py`/`turn/battle_luck.py`) rather than
# `randrange(2)`, so `tests/_helpers.py ScriptedRandom` can control it.
MATURATION_THRESHOLD_ORDINALS = (ALIGNMENT_ORDINAL[Alignment.NEUTRAL], ALIGNMENT_ORDINAL[Alignment.PAGAN])
# THUNDERBIRD.md section 10: the temperament activity check (`mtemper >=
# (IRand AND 3)`) -- Cowardly 25% / Cautious 50% / Brave 75% / Berserk
# 100%, expressed here as a direct chance-per-`Temper` lookup (same
# `rng.random() >= chance` idiom as the other rolls in this module)
# rather than a die roll, for the same testability reason as above.
MONSTER_RAID_ACTIVITY_CHANCE: dict[Temper, float] = {
    Temper.COWARDLY: 0.25,
    Temper.CAUTIOUS: 0.50,
    Temper.BRAVE: 0.75,
    Temper.BERSERK: 1.0,
}
THUNDERBIRD_INTERVENTION_CHANCE = 0.40
RAID_DAMAGE_DIVISOR = 70
RAID_DAMAGE_FLAT_BONUS = 1
MONSTER_HIDE_DISSIPATION_CHANCE = 0.10

_MATURATION_STEPS: dict[MonsterEngagementState, MonsterEngagementState] = {
    MonsterEngagementState.CALM: MonsterEngagementState.MERCENARY,
    MonsterEngagementState.MERCENARY: MonsterEngagementState.BOLD,
}


def age_feature_guardian(state: GameState, feature: Feature, rng: random.Random) -> None:
    """``Age_Feature_Monsters``'s own per-feature body (THUNDERBIRD.md
    section 11) -- consumes the 3% roll always first, the Worldly/Animal
    threshold roll only on a hit, matching the real short-circuit exactly
    (including consuming both rolls even for an already-``looted`` Dead
    feature, or one with no guardian_alignment recorded).
    """

    if feature.guardian_monster is None:
        return

    province = state.provinces.get(feature.coord)
    if province is None or province.owner_kingdom_id is None:
        return

    if rng.random() >= MONSTER_MATURATION_ROLL_CHANCE:
        return

    threshold = MATURATION_THRESHOLD_ORDINALS[0 if rng.random() < 0.5 else 1]
    if feature.guardian_alignment is None:
        return
    if ALIGNMENT_ORDINAL[feature.guardian_alignment] < threshold:
        return
    if feature.looted:
        return

    next_state = _MATURATION_STEPS.get(feature.guardian_state)
    if next_state is not None:
        feature.guardian_state = next_state


def age_all_feature_guardians(state: GameState, rng: random.Random) -> None:
    """Calls ``age_feature_guardian()`` for every feature, in deterministic
    ``feature_id`` order (matching THUNDERBIRD.md's own "FOR fn := 0 TO
    nfeatures-1" loop)."""

    for feature_id in sorted(state.features):
        age_feature_guardian(state, state.features[feature_id], rng)


def maybe_dissipate_hidden_feature(feature: Feature, rng: random.Random) -> None:
    """THUNDERBIRD.md section 12.3's own genuinely new 10%-per-turn Hide
    Feature dissipation roll -- no roll consumed when the feature isn't
    currently hidden at all."""

    if not feature.magically_hidden:
        return
    if rng.random() < MONSTER_HIDE_DISSIPATION_CHANCE:
        feature.magically_hidden = False


def resolve_province_raids(
    state: GameState,
    kingdom_id: int,
    province: ProvinceState,
    income: int,
    divine_archangel_kingdom_id: int | None,
    thunder_used: bool,
    rng: random.Random,
) -> tuple[int, bool, list[RaidEvent]]:
    """``Resolve_Feature_Raids``'s own per-province body (THUNDERBIRD.md
    sections 9-10). Returns ``(possibly_reduced_income, thunder_used,
    events)``.
    """

    events: list[RaidEvent] = []
    for feature in sorted(state.features_at(province.coord), key=lambda f: f.feature_id):
        if feature.guardian_monster is None or feature.looted or feature.magically_hidden:
            continue
        if feature.guardian_state is not MonsterEngagementState.BOLD:
            continue

        profile = MONSTER_RUNTIME_PROFILE[feature.guardian_monster]
        if rng.random() >= MONSTER_RAID_ACTIVITY_CHANCE[profile.temper]:
            continue

        if not thunder_used and divine_archangel_kingdom_id == kingdom_id and rng.random() < THUNDERBIRD_INTERVENTION_CHANCE:
            feature.guardian_state = MonsterEngagementState.MERCENARY
            thunder_used = True
            events.append(RaidEvent("thunderbird", province.coord, feature.feature_id, feature.guardian_monster, 0))
            continue

        damage = profile.average_hit_points * income // RAID_DAMAGE_DIVISOR + RAID_DAMAGE_FLAT_BONUS
        income -= damage
        events.append(RaidEvent("raid", province.coord, feature.feature_id, feature.guardian_monster, damage))

    return income, thunder_used, events


def apply_fulfill_pacification(feature: Feature) -> bool:
    """THUNDERBIRD.md section 4.2's own compiled pacification snippet
    (``AK.OVR`` raw ``0x1987C-0x19937``): ``IF fstate<>Calm THEN (IF
    fstate=Bold THEN Mercenary ELSE Calm)``. Per the user's own direct
    2026-08-29 choice, applied to ANY successfully-honored ``turn/
    encounter.py resolve_fulfill_honored()`` deal against a Feature's
    guardian, not gated on the real game's own narrower "was this
    specifically a stop-raiding promise" negotiation branch (`RUMORS.PAS
    Check_Raid`'s own 25th Talk-reply, gated on `fstate=Bold`, that this
    project's `MonsterTalkReply`/`TalkReplyOutcome` enum doesn't model)
    -- this project's own Fulfill mechanic is already deliberately
    abstract about deal content (see `turn/encounter.py`'s own module
    comment above `FULFILL_HELLISH_REFERENCE_ORDINAL`), so this reuses
    that same simplification rather than inventing new deal-type state.

    Returns ``True`` iff a transition actually happened (``guardian_
    state`` wasn't already ``CALM``).
    """

    if feature.guardian_state is MonsterEngagementState.CALM:
        return False
    feature.guardian_state = (
        MonsterEngagementState.MERCENARY
        if feature.guardian_state is MonsterEngagementState.BOLD
        else MonsterEngagementState.CALM
    )
    return True


def intimidation_packet_chance(damage: int, combat_temper: Temper, monster_base_hp: int) -> float:
    """``BOLD OK.txt`` section 9.5's own exact formula for one damage
    packet against a ``Bold`` guardian: ``min(1, damage*(4-temper)/
    mtbasehp)``. ``damage <= 0`` is always `0.0` (a miss/no-op packet
    can't intimidate). No explicit `Min(1,...)` exists in the compiled
    binary -- since `Random` is always in `[0,1)`, a ratio `>= 1` is
    already certain success without one; the `min()` here is purely a
    defensive clamp for callers, not a behavior difference.
    """

    if damage <= 0:
        return 0.0
    return min(1.0, damage * (4 - combat_temper.value) / monster_base_hp)


def roll_guardian_intimidation(
    feature: Feature, damage_packets: list[int], combat_temper: Temper, rng: random.Random
) -> bool:
    """``Check_Monster_Intimidation``'s own real per-encounter rolling
    (``BOLD OK.txt`` sections 9.1-9.8): every damage packet against a
    ``Bold`` guardian rolls independently via ``intimidation_packet_
    chance()``; the first success sets a sticky flag applied to
    ``guardian_state`` (``Bold -> Mercenary``) only here, at the
    encounter's own closure -- never mid-fight. Every packet is rolled
    regardless of whether an earlier one already succeeded (section
    9.8's own "ogni pacchetto... indipendente," matching real fidelity
    rather than an early-exit optimization).

    ``False`` immediately, no rolls consumed, unless ``feature.
    guardian_state`` is currently ``BOLD`` (section 9.2's own real
    precondition).
    """

    if feature.guardian_state is not MonsterEngagementState.BOLD:
        return False
    base_hp = MONSTER_RUNTIME_PROFILE[feature.guardian_monster].average_hit_points
    intimidated = False
    for damage in damage_packets:
        chance = intimidation_packet_chance(damage, combat_temper, base_hp)
        if chance > 0.0 and rng.random() < chance:
            intimidated = True
    if intimidated:
        feature.guardian_state = MonsterEngagementState.MERCENARY
    return intimidated


def guardian_undeterred(feature: Feature, took_damage: bool) -> bool:
    """``BOLD OK.txt`` section 10.4's own real ``_MUnDt`` precondition:
    the guardian took real damage this encounter (``took_damage``) but
    no intimidation packet ever succeeded, and it's still ``Bold``. Pure
    predicate -- ``_MUnDt`` never writes any state, the guardian simply
    stays ``Bold`` and can keep raiding.
    """

    return took_damage and feature.guardian_state is MonsterEngagementState.BOLD
