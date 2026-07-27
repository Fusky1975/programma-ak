"""Explore action resolution (rulebook [3.2]).

Formula, verbatim from the rulebook: an Explore order raises a province's
cumulative exploration percentage by (Basic Exploration Number for the
terrain x (Explorer skill + 1))%, capped at 100% ("A character must
Explore 100% of the province to make sure that everything in the province
has been found").

Feature discovery (dungeons, pyramids, guardian monsters, treasures) is
now wired below (``discover_features()``, Phase 242) once a feature
roster exists (``turn/world_generation.py``). Rumors (the [3.2] "sometimes
you get rumours of previously unheard-of features... about half of these
rumours are true" mechanic -- a *separate* discovery channel from direct
Explore) and battlefield reports remain out of scope: no selection/
falsification logic for rumors survives anywhere in the archive (see
``turn/world_generation.py``'s own docstring for the parallel "no
surviving source" finding for world generation itself).

**``discover_features()``, project-original, confirmed directly with the
user (project author)**: no formula for *when* a feature gets discovered
survives anywhere in the archive either (``models/feature.py``'s own
docstring already confirmed this -- ``fdisc``/``nfeatures`` are only ever
*read* by ``REPORTS.PAS``, never written, anywhere in the available
source). The confirmed design: discovery chance for a still-undiscovered
feature equals the kingdom's own cumulative exploration percentage of
that province *as of this action* -- monotonically increasing, and
guaranteed once that percentage reaches 100, directly matching the
rulebook's own "must Explore 100%... to make sure everything... has been
found" text quoted above. Each undiscovered feature in the province rolls
independently. A feature already discovered by this kingdom
(``discovery_level(kingdom_id) != 0``) or magically hidden (``Feature.
magically_hidden``, Phase 193 -- confirmed as this flag's own first real
consumer) is skipped, not rerolled.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from ak_engine.models.feature import Feature
from ak_engine.models.game_state import GameState
from ak_engine.models.map import TERRAIN_EXPLORATION_NUMBER, HexCoord, Terrain

MIN_EXPLORER_SKILL = 0
MAX_EXPLORER_SKILL = 9  # CTBOTH.PAS `skillrange = 0..9`


@dataclass(slots=True)
class ExploreResult:
    new_percent: int
    delta_applied: int
    fully_explored: bool
    # Phase 245: populated by dispatch_phase()'s own EXPLORE branch from
    # record_kingdom_exploration()'s own KingdomExplorationResult, not by
    # resolve_explore() itself (a pure percent-only function that has no
    # GameState/rng to roll discovery with) -- see turn/plan_dispatch.py.
    discovered_features: list[Feature] = field(default_factory=list)


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


def discover_features(
    state: GameState, coord: HexCoord, kingdom_id: int, exploration_percent: int, rng: random.Random
) -> list[Feature]:
    """Roll discovery for every still-undiscovered feature at ``coord``, for
    ``kingdom_id`` specifically, after its own cumulative exploration
    of this province reached ``exploration_percent``. See module
    docstring for the full design and its sourcing. A successful roll
    sets full disclosure (``discovery_level`` 3 -- [3.2]'s own "told the
    name of the feature, the treasure... and the monster guarding"),
    matching Explore's own direct-find text rather than the partial
    levels 1/2 (see ``models/feature.py``'s own docstring for what
    those mean).
    """

    discovered: list[Feature] = []
    for feature in state.features_at(coord):
        if feature.magically_hidden:
            continue
        if feature.discovery_level(kingdom_id) != 0:
            continue
        if rng.random() * 100 < exploration_percent:
            feature.discovered_by_kingdom[kingdom_id] = 3
            discovered.append(feature)
    return discovered
