"""Plague's own spread-to-adjacent-provinces mechanic -- rulebook
[4.25.3] (quoted in full, ``RULES.AK`` ~line 968): "The caster names a
province to be afflicted... If successful, each army in the province
has a 10% chance of being destroyed, plus 10% per level of the
spellcaster. If a unit survives a plague, it's immunized from dying in
future plagues (it may instead drop a level in quality.) Only the four
humanoid races are affected. Be careful! The next phase, there is a
15% chance per adjacent province that the plague will spread, and it
can spread further each phase after that. Casting more than one Plague
spell does not have a cumulative effect."

Phase 233 -- the last unmodeled piece of this rule. The initial cast
(``turn/cast_execution.py _execute_plague()``) and the army-exposure/
immunity rules it shares with this module (``apply_plague_exposure()``)
were already real and sourced; only the propagation itself -- and the
persistent ``ProvinceState.plague_active`` flag it needs -- was
confirmed absent until now (that function's own Phase 232-era docstring
said so explicitly: "The 15%/phase spread to an adjacent province stays
unmodeled... a natural follow-up, not attempted this phase").

**"The next phase... it can spread further each phase after that"**:
read as one hop per call, not a same-call cascade -- ``resolve_plague_
spread()`` snapshots every currently-`plague_active` province *before*
rolling any spread, so a province infected during this same call never
also spreads within it; a second, newly-infected wave only becomes a
source the *next* time this function runs. That's a direct reading of
"the next phase" (propagation is gradual, phase by phase), not a
guessed rate-limit.

**Spread exposure uses the base 10% chance with no caster-level
bonus**, a documented, unsourced design choice, not a recovered
formula: the rulebook's own "+10% per level of the spellcaster" clause
is stated only for the original cast, where an actual caster and skill
level exist. A spread event has no caster to draw a level from, so the
natural reading is the disease's own baseline rate, undiluted by
anyone's skill -- `apply_plague_exposure()`'s own immunity/quality-
downgrade rules apply identically either way.

**Meant to be called once per phase boundary from ``turn/
turn_processor.py``**, the same "runs before every phase after the
first" convention `_dispatch_contested_rebattles` already established
(Phase 55) -- reusing that exact call site keeps "the next phase" as
literal as this project's own phase-by-phase turn loop allows.
"""

from __future__ import annotations

import random

from ak_engine.models.game_state import GameState
from ak_engine.models.map import HexCoord
from ak_engine.turn.cast_execution import PLAGUE_BASE_DESTROY_CHANCE, apply_plague_exposure
from ak_engine.turn.movement import MapBounds, neighbors

# [4.25.3]: "il 15% di probabilita' per ogni provincia adiacente che la
# pestilenza si propaghi."
PLAGUE_SPREAD_CHANCE = 0.15


def resolve_plague_spread(state: GameState, rng: random.Random, bounds: MapBounds) -> list[HexCoord]:
    """Rolls one spread attempt per (already-afflicted province, unafflicted
    neighbor) pair -- see module docstring for the "one hop per call" and
    "base chance, no caster-level bonus" design choices. Returns the
    coordinates newly infected this call (possibly empty), for a future
    caller to narrate if it chooses -- this function itself doesn't
    render anything (the same "compute, don't narrate" separation
    ``turn/battle_orchestrator.py fight_battle()`` already established
    for `report/turn_report.py`'s own recorders).
    """

    source_coords = [coord for coord, province in state.provinces.items() if province.plague_active]
    newly_infected: list[HexCoord] = []
    for coord in source_coords:
        for neighbor_coord in neighbors(coord, bounds):
            neighbor = state.provinces.get(neighbor_coord)
            if neighbor is None or neighbor.plague_active:
                continue
            if rng.random() < PLAGUE_SPREAD_CHANCE:
                neighbor.plague_active = True
                apply_plague_exposure(state, neighbor_coord, PLAGUE_BASE_DESTROY_CHANCE, rng)
                newly_infected.append(neighbor_coord)
    return newly_infected
