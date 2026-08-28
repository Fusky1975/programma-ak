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

**Deliberately out of scope this phase** (user-approved, "solo il
nucleo ora"): quest/Fulfill-triggered and intimidating-attack-triggered
pacification (THUNDERBIRD.md section 4.2's other two ways to calm a
raider) -- both need hooking into other already-existing subsystems
(quest fulfillment, Search/Challenge combat resolution) with their own
trigger logic, a separate follow-up. Also out of scope: ``Maybe_Repopulate_
Dead_Feature`` (no precise algorithm given) and seeding *initial* Bold
guardians at world generation (this document covers per-turn maturation
only -- every world-generated feature starts at ``MERCENARY`` and matures
naturally via real turns' own Fall/Early-Winter rolls).
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
