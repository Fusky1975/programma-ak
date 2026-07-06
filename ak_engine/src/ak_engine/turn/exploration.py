"""Explore action resolution (rulebook [3.2]).

Formula, verbatim from the rulebook: an Explore order raises a province's
cumulative exploration percentage by (Basic Exploration Number for the
terrain x (Explorer skill + 1))%, capped at 100% ("A character must
Explore 100% of the province to make sure that everything in the province
has been found").

Feature discovery (dungeons, pyramids, guardian monsters, treasures),
rumors, and battlefield reports are stochastic content generation tied to
the game's monster/treasure tables and prose templates -- out of scope for
this phase, which only implements the deterministic percentage math.
"""

from __future__ import annotations

from dataclasses import dataclass

from ak_engine.models.map import TERRAIN_EXPLORATION_NUMBER, Terrain

MIN_EXPLORER_SKILL = 0
MAX_EXPLORER_SKILL = 9  # CTBOTH.PAS `skillrange = 0..9`


@dataclass(slots=True)
class ExploreResult:
    new_percent: int
    delta_applied: int
    fully_explored: bool


def resolve_explore(
    current_percent: int,
    terrain: Terrain,
    explorer_skill: int,
    *,
    partial: bool = False,
) -> ExploreResult:
    """Apply one Explore action, or a Move's partial-exploration side effect.

    ``partial=True`` reproduces the rulebook [3.1] Move side effect:
    "Moving into a province also counts as a partial exploration of the
    province, with half the effect of an Explore order".
    """

    if not 0 <= current_percent <= 100:
        raise ValueError(f"current_percent must be 0-100, got {current_percent}")
    if not MIN_EXPLORER_SKILL <= explorer_skill <= MAX_EXPLORER_SKILL:
        raise ValueError(
            f"explorer_skill must be {MIN_EXPLORER_SKILL}-{MAX_EXPLORER_SKILL}, got {explorer_skill}"
        )

    exploration_number = TERRAIN_EXPLORATION_NUMBER[terrain] * (explorer_skill + 1)
    if partial:
        exploration_number //= 2

    new_percent = min(100, current_percent + exploration_number)
    return ExploreResult(
        new_percent=new_percent,
        delta_applied=new_percent - current_percent,
        fully_explored=new_percent >= 100,
    )
