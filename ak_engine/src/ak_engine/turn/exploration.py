"""Explore action resolution (rulebook [3.2]).

**Phase 507**: the rulebook-only formula this module used to implement
(a flat, uncapped ``skill + 1`` multiplier) is superseded by the real
one recovered from a disassembly of ``AK.EXE:0xA780-0xAF3F`` (the
user's third reverse-engineering dossier, ``AKGEN_reverse_engineering_
report (3).md``, Part IV SS49-50): ``E = min(4, S) + 1`` -- confirming
``SAL.X2:26``'s own "from level 5 the ordinary multiplier stops
increasing" text is a hard *executable* cap, not just manual-text
color, and that the pre-507 code's own uncapped growth (``MAX_EXPLORER_
SKILL=9`` giving x10, not the real x5 ceiling) was a genuine, sourced
bug, not a documented approximation. Two Advanced Abilities the real
engine folds directly into this same formula are now real optional
parameters instead of unmodeled: ``has_difficult_terrain`` (``AK.EXE:
0xA97B-0xA9BE``, +10 flat to the terrain's own Basic Exploration Number
*before* multiplying by ``E`` -- not a 10% multiplier despite the
Advanced Ability's own tagline) and ``has_military_maps`` (``AK.EXE:
0xA799-0xA7B5``/``0xB559-0xB5CB``, raises the cap from 100 to 200 --
Military Maps adds no points itself, it only raises how far accumulated
knowledge can climb).

Formula, verbatim from the rulebook (still the base before the two
Phase 507 additions above): an Explore order raises a province's
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

**Hand-Held Radar** (Discovery.txt, Phase 270): "enable characters to
find features regardless of whether a Hide Feature spell has been cast
on the feature." A kingdom owning it bypasses the ``magically_hidden``
skip entirely -- the feature rolls for discovery exactly as if it were
never hidden.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from ak_engine.models.discovery import Discovery
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


EXPLORATION_CAP = 100
EXPLORATION_CAP_WITH_MILITARY_MAPS = 200
DIFFICULT_TERRAIN_BONUS = 10
EXPLORER_SKILL_MULTIPLIER_CAP = 4  # real E = min(4, S) + 1 -- SAL.X2:26, AK.EXE:0xA909-0xA9D0


def resolve_explore(
    current_percent: int,
    terrain: Terrain,
    explorer_skill: int,
    *,
    partial: bool = False,
    has_military_maps: bool = False,
    has_difficult_terrain: bool = False,
) -> ExploreResult:
    """Apply one Explore action, or a Move's partial-exploration side effect.

    ``partial=True`` reproduces the rulebook [3.1] Move side effect:
    "Moving into a province also counts as a partial exploration of the
    province, with half the effect of an Explore order".

    ``has_military_maps``/``has_difficult_terrain`` (Phase 507): the
    acting leader's own ``AdvancedAbility.EXPLORER_MILITARY_MAPS``/
    ``EXPLORING_DIFFICULT_TERRAIN`` possession -- see module docstring
    for the real formula each feeds. Both default to ``False`` (the
    pre-507 behavior minus the multiplier-cap fix) for any caller that
    doesn't pass them.
    """

    max_reachable = EXPLORATION_CAP_WITH_MILITARY_MAPS if has_military_maps else EXPLORATION_CAP
    if not 0 <= current_percent <= max_reachable:
        raise ValueError(f"current_percent must be 0-{max_reachable}, got {current_percent}")
    if not MIN_EXPLORER_SKILL <= explorer_skill <= MAX_EXPLORER_SKILL:
        raise ValueError(
            f"explorer_skill must be {MIN_EXPLORER_SKILL}-{MAX_EXPLORER_SKILL}, got {explorer_skill}"
        )

    basic_exploration_number = TERRAIN_EXPLORATION_NUMBER[terrain]
    if has_difficult_terrain:
        basic_exploration_number += DIFFICULT_TERRAIN_BONUS
    multiplier = min(EXPLORER_SKILL_MULTIPLIER_CAP, explorer_skill) + 1
    exploration_number = basic_exploration_number * multiplier
    if partial:
        exploration_number //= 2

    new_percent = min(max_reachable, current_percent + exploration_number)
    return ExploreResult(
        new_percent=new_percent,
        delta_applied=new_percent - current_percent,
        fully_explored=new_percent >= EXPLORATION_CAP,
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
    kingdom = state.kingdoms.get(kingdom_id)
    has_radar = kingdom is not None and Discovery.HAND_HELD_RADAR in kingdom.discoveries
    for feature in state.features_at(coord):
        if feature.magically_hidden and not has_radar:
            continue
        if feature.discovery_level(kingdom_id) != 0:
            continue
        if rng.random() * 100 < exploration_percent:
            feature.discovered_by_kingdom[kingdom_id] = 3
            discovered.append(feature)
    return discovered
