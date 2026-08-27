"""Druidic monster battle assistance -- AKGEN_reverse_engineering_report (2).md
SS5: a Feature's own guardian monster may join a Druidic-aligned side's
battle line, strengthening one column, without ever being recruited or
placed under anyone's command. Phase 452 implements the three pure
formulas plus the per-battle-province scan that ties them together;
Phase 453 wires the result into real combat (`turn/battle_resolution.py
resolve_battle()`/`turn/battle_orchestrator.py fight_battle()`).

**Effective alignment (`Agent_Align`)**: a monster's own `base_view`
Alignment (`models/monster.py MonsterRuntimeProfile.base_view`) isn't
necessarily how it perceives *this* specific battle -- the source's own
`Agent_Align` formula walks the Alignment ordinal line a deterministic,
feature/monster-specific number of steps away from `base_view`, seeded by
`q = 256 + feature_id + monster_id` (`monster_id` being the guardian
species' own `Monster.value`). `direction` is fixed by `q`'s own bit 3
(`q & 8`); the walk runs up to `view_variation` steps
(`MonsterRuntimeProfile.view_variation`), stopping early the first time
`q` goes even, and clamped to ordinals 0-8 (`Alignment.DIVINE` through
`Alignment.MECHANICAL`) -- `Alignment.SPECIAL` (ordinal 9, confirmed
never a selectable Kingdom Alignment anywhere in this project, e.g.
`turn/emperor_election.py _ORDINARY_ALIGNMENTS`'s own exclusion) is
never a reachable walk endpoint here either.

**Join probability**: `d_D` is the effective alignment's own ordinal
distance from `Alignment.DRUID` (ordinal 2, the Druidic side doing the
recruiting); `d_E` is its distance from the *enemy* side's own Alignment.
`d_D >= d_E` means the monster is no more sympathetic to Druids than to
the enemy (or exactly as far from both) -- not eligible, probability
0.0, matching the source's own "distanza pari o maggiore = non
eleggibile" (this also covers the degenerate case of two Druidic
Kingdoms fighting each other, where `d_E == 0` always wins the `>=`
check via a zero denominator that's never reached). Otherwise
`1 - d_D/d_E`: the closer the monster's effective alignment sits to pure
Druidic relative to how far it sits from the enemy, the more likely it
joins.

**Strength bonus**: `floor(hit_points * (melee_damage + missile_damage)
/ 50)`, using `MonsterRuntimeProfile.average_hit_points`/
`melee_damage_parameter`/`missile_damage_parameter` -- e.g. the Gold
Dragon (`average_hit_points=40`, `melee_damage_parameter=12`,
`missile_damage_parameter=15`) gives `(40*(12+15))//50 == 21`, the
source's own worked example.

**Per-province scan**: `find_druidic_monster_assistance()` walks every
unlooted, guardian-bearing `Feature` at the battle province in ascending
`feature_id` order (matching this project's other feature-ordering
conventions, e.g. `turn/discovery_effects.py`), rolls each eligible
monster's own join probability once, and on success assigns it a random
battle column (0-based, matching this project's own column-indexing
convention everywhere else -- the source's own 1-based `1 + IRand MOD
line_length` is a Pascal-ism, not a game-rule). A column that already
has an assisting monster from an earlier feature in this same scan
discards the later monster outright -- no retry, no alternate column,
exactly as the source describes.

**Phase 657**: `find_druidic_monster_assistance()` now returns
`DruidicMonsterAssistance` values (still keyed by column) instead of a
bare `int` -- the strength bonus alone, with no record of which
monster/Feature earned it. `turn/battle_orchestrator.py fight_battle()`
consumed the bonus straight into `resolve_battle()`'s own combat math
and discarded the rest, so there was no way to narrate MCOME.X/
MFIGHT.X (`report/turn_report.py render_monster_reinforcement_arrives()`/
`_helped()`, Phase 604 -- sourced and render-tested but never wired,
see that module's own comment) with a real monster/army name after the
fact. `strength_bonus` is unchanged in meaning and is what still feeds
`resolve_battle()`'s own `{column: bonus}` parameter (extracted by the
caller); `monster`/`feature_id` are new, carried through purely for
report-layer identity.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from ak_engine.models.alignment import ALIGNMENT_BY_ORDINAL, ALIGNMENT_ORDINAL, Alignment
from ak_engine.models.game_state import GameState
from ak_engine.models.map import HexCoord
from ak_engine.models.monster import MONSTER_RUNTIME_PROFILE, Monster

# The walk's own clamp bound -- Alignment.MECHANICAL (ordinal 8), not
# Alignment.SPECIAL (ordinal 9). See module docstring.
_WALK_MAX_ORDINAL = ALIGNMENT_ORDINAL[Alignment.MECHANICAL]


def monster_effective_alignment(
    feature_id: int, monster_id: int, base_view: Alignment, view_variation: int
) -> Alignment:
    """The real `Agent_Align` formula -- see module docstring for the full derivation."""

    q = 256 + feature_id + monster_id
    direction = 1 if (q & 8) else -1
    ordinal = ALIGNMENT_ORDINAL[base_view]

    for _ in range(view_variation):
        if q % 2 == 0:
            break
        ordinal = max(0, min(_WALK_MAX_ORDINAL, ordinal + direction))
        q >>= 1

    return ALIGNMENT_BY_ORDINAL[ordinal]


def monster_join_probability(effective_alignment: Alignment, enemy_alignment: Alignment) -> float:
    """Chance this monster joins the Druidic side against `enemy_alignment` -- see
    module docstring's "Join probability" section.
    """

    d_druid = abs(ALIGNMENT_ORDINAL[effective_alignment] - ALIGNMENT_ORDINAL[Alignment.DRUID])
    d_enemy = abs(ALIGNMENT_ORDINAL[effective_alignment] - ALIGNMENT_ORDINAL[enemy_alignment])
    if d_druid >= d_enemy:
        return 0.0
    return 1 - d_druid / d_enemy


def monster_strength_bonus(hit_points: int, melee_damage: int, missile_damage: int) -> int:
    """`floor(hit_points * (melee_damage + missile_damage) / 50)` -- see module
    docstring's Gold Dragon worked example.
    """

    return (hit_points * (melee_damage + missile_damage)) // 50


@dataclass(slots=True, frozen=True)
class DruidicMonsterAssistance:
    """One assisting monster's real contribution to a single battle column
    (Phase 657) -- `strength_bonus` still feeds `resolve_battle()`'s own
    numeric-only `{column: bonus}` parameter; `monster`/`feature_id` are
    carried purely for report-layer identity (MCOME.X/MFIGHT.X).
    """

    strength_bonus: int
    monster: Monster
    feature_id: int


def find_druidic_monster_assistance(
    state: GameState,
    province_coord: HexCoord,
    enemy_alignment: Alignment,
    line_length: int,
    rng: random.Random,
) -> dict[int, DruidicMonsterAssistance]:
    """Scans every unlooted, guardian-bearing Feature at `province_coord` (ascending
    `feature_id` order) for Druidic monster battle assistance against
    `enemy_alignment` -- see module docstring's "Per-province scan"
    section. Returns `{column: DruidicMonsterAssistance}` for every
    monster that both rolled successfully and landed on a column no
    earlier monster in this same scan already claimed.
    """

    assistance: dict[int, DruidicMonsterAssistance] = {}
    features = sorted(state.features_at(province_coord), key=lambda feature: feature.feature_id)

    for feature in features:
        if feature.looted or feature.guardian_monster is None:
            continue
        profile = MONSTER_RUNTIME_PROFILE.get(feature.guardian_monster)
        if profile is None:
            continue

        effective_alignment = monster_effective_alignment(
            feature.feature_id, feature.guardian_monster.value, profile.base_view, profile.view_variation
        )
        probability = monster_join_probability(effective_alignment, enemy_alignment)
        if probability <= 0.0:
            continue
        if rng.random() >= probability:
            continue

        column = rng.randrange(line_length)
        if column in assistance:
            continue

        strength_bonus = monster_strength_bonus(
            profile.average_hit_points, profile.melee_damage_parameter, profile.missile_damage_parameter
        )
        assistance[column] = DruidicMonsterAssistance(
            strength_bonus=strength_bonus, monster=feature.guardian_monster, feature_id=feature.feature_id
        )

    return assistance
