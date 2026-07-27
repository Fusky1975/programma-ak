"""Rumor generation (rulebook [3.2]) -- Phase 243.

See ``models/rumor.py``'s own docstring for the full quoted rulebook
text and the "prose templates survive, the logic doesn't" finding. Every
number below is project-original, confirmed directly with the user
(project author):

**Trigger chance, by the order that (potentially) generates a rumor**:
resolved from the user's own shorthand (MO/PU/TR, EX/SP, CA/PR) against
this project's own Pascal-sourced ``actab`` abbreviation table
(``CTBOTH.PAS``, positionally matched against the ``action`` enum --
confirmed unambiguous: MO=LMove, PU=Pursue, TR=Trail, EX=Explore,
SP=ASpy, CA=Cast, PR=Practice):

- Move [MO], Pursue [PU], Trail [TR]: 20%
- Explore [EX], ASpy [SP]: 30%
- Cast [CA], Practice [PR]: 5%

**Eligibility**: only features not yet discovered by the hearer's own
kingdom (rulebook's own "previously unheard-of"), not magically hidden
(``Feature.magically_hidden``, Phase 193), and within ``RUMOR_MAX_
DISTANCE`` (2) hexes of the order's own province -- excluding that
province itself (a feature right where the character already is would
just be found directly by Explore's own ``discover_features()``, Phase
242, not "heard about"). No candidate anywhere in range means no rumor
is even rolled for, regardless of the order's own trigger chance --
resolved before consuming any randomness, so this is a true no-op for
every caller whose ``GameState`` has no nearby features (i.e. every
caller that predates this phase).

**Content, once a rumor triggers**: 70% describes the feature's own
guardian monster, 30% its own treasure item -- both always naming a
province too. A feature missing one of the two (``guardian_monster``/
``treasure`` is ``None``, possible for features built outside world
generation) is only eligible for whichever content type it actually
has; a feature with neither is not a rumor candidate at all.

**Truth**: 50/50, matching the rulebook's own "about half... are true."
A false rumor corrupts exactly one detail (50/50 between the two),
matching "the treasure may not actually be there, and/or the feature
may be in a different province": either the monster/item is replaced
with a uniformly-random *different* one, or the province is replaced
with a uniformly-random *other* province on the map (no stated range
for how wrong a false province can be -- the rulebook only says "a
different province").
"""

from __future__ import annotations

import random

from ak_engine.models.enums import ActionCode
from ak_engine.models.feature import Feature
from ak_engine.models.game_state import GameState
from ak_engine.models.map import HexCoord
from ak_engine.models.monster import Monster
from ak_engine.models.rumor import Rumor, RumorContent
from ak_engine.models.treasure import Treasure
from ak_engine.turn.movement import hex_distance

RUMOR_CHANCE_BY_ACTION: dict[ActionCode, float] = {
    ActionCode.LMOVE: 0.20,
    ActionCode.PURSUE: 0.20,
    ActionCode.TRAIL: 0.20,
    ActionCode.EXPLORE: 0.30,
    ActionCode.ASPY: 0.30,
    ActionCode.CAST: 0.05,
    ActionCode.PRACTICE: 0.05,
}

RUMOR_MAX_DISTANCE = 2
RUMOR_TRUE_CHANCE = 0.50
RUMOR_FEATURE_CONTENT_CHANCE = 0.70  # vs item-content 0.30
RUMOR_CORRUPT_SUBJECT_CHANCE = 0.50  # vs corrupt-province 0.50


def find_rumor_candidates(state: GameState, origin: HexCoord, kingdom_id: int) -> list[Feature]:
    """Every feature eligible to be rumored about from ``origin``, for ``kingdom_id``
    specifically -- see module docstring for the exact eligibility rules.
    """

    return [
        feature
        for feature in state.features.values()
        if feature.discovery_level(kingdom_id) == 0
        and not feature.magically_hidden
        and (feature.guardian_monster is not None or feature.treasure is not None)
        and 1 <= hex_distance(origin, feature.coord) <= RUMOR_MAX_DISTANCE
    ]


def _build_rumor(state: GameState, kingdom_id: int, action: ActionCode, feature: Feature, rng: random.Random) -> Rumor:
    if feature.guardian_monster is not None and feature.treasure is not None:
        content = RumorContent.FEATURE_AND_MONSTER if rng.random() < RUMOR_FEATURE_CONTENT_CHANCE else RumorContent.ITEM
    elif feature.guardian_monster is not None:
        content = RumorContent.FEATURE_AND_MONSTER
    else:
        content = RumorContent.ITEM

    is_true = rng.random() < RUMOR_TRUE_CHANCE
    described_coord = feature.coord
    described_monster = feature.guardian_monster if content is RumorContent.FEATURE_AND_MONSTER else None
    described_treasure = feature.treasure if content is RumorContent.ITEM else None

    if not is_true:
        if rng.random() < RUMOR_CORRUPT_SUBJECT_CHANCE:
            if content is RumorContent.FEATURE_AND_MONSTER:
                other_monsters = [m for m in Monster if m is not Monster.NOMONSTER and m is not feature.guardian_monster]
                described_monster = rng.choice(other_monsters)
            else:
                other_treasures = [t for t in Treasure if t is not feature.treasure]
                described_treasure = rng.choice(other_treasures)
        else:
            other_provinces = [coord for coord in state.provinces.keys() if coord != feature.coord]
            if other_provinces:
                described_coord = rng.choice(other_provinces)

    return Rumor(
        rumor_id=state.new_rumor_id(),
        kingdom_id=kingdom_id,
        source_action=action,
        content=content,
        feature_id=feature.feature_id,
        is_true=is_true,
        described_coord=described_coord,
        described_monster=described_monster,
        described_treasure=described_treasure,
    )


def resolve_rumor_generation(
    state: GameState, kingdom_id: int, origin: HexCoord, action: ActionCode, rng: random.Random
) -> Rumor | None:
    """Roll whether ``action`` (issued from ``origin``, by ``kingdom_id``) generates a
    rumor this turn, and build it if so. Returns ``None`` -- consuming no
    randomness at all -- for any ``action`` outside ``RUMOR_CHANCE_BY_
    ACTION`` or when no eligible feature exists nearby; only then rolls
    the trigger chance itself. Does not add the result to ``state`` --
    callers do that (``GameState.add_rumor()``) so they can inspect it
    first.
    """

    chance = RUMOR_CHANCE_BY_ACTION.get(action)
    if chance is None:
        return None
    candidates = find_rumor_candidates(state, origin, kingdom_id)
    if not candidates:
        return None
    if rng.random() >= chance:
        return None
    feature = rng.choice(candidates)
    return _build_rumor(state, kingdom_id, action, feature, rng)
