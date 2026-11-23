"""Hidden Tattoos sickness (project design, specified by the user 2026-11-23).

A Kill Enemy that succeeds against a character of a Kingdom owning Hidden
Tattoos does not kill: "the target character will be sick for the remainder of
the gameturn and will spend his time practicing abilities somewhat randomly."

While sick, the character's orders change by themselves from the next order they
carry out (the phase they have not yet acted in, or the one after if they already
did):

- a Practice stays as it is;
- every other order becomes a Practice in the character's highest-level talent
  (ties at random) when they lead no army;
- when they lead armies it becomes Practice Tactical on land, Practice Naval in
  a sea province.

The sickness ends with the turn (``clear_sickness()``, called from the end-of-turn
reset).
"""

from __future__ import annotations

import random

from ak_engine.models.enums import Ability, ActionCode
from ak_engine.models.game_state import GameState
from ak_engine.models.map import Terrain
from ak_engine.models.plan import PlanPhase


def make_sick(state: GameState, leader_id: int) -> None:
    leader = state.leaders.get(leader_id)
    if leader is not None:
        leader.sick_this_turn = True


def clear_sickness(state: GameState) -> None:
    for leader in state.leaders.values():
        leader.sick_this_turn = False


def _practice_ability(state: GameState, leader_id: int, label: str) -> Ability:
    leader = state.leaders[leader_id]
    if state.armies_commanded_by(leader_id):
        province = state.provinces.get(leader.location)
        at_sea = province is not None and province.effective_terrain() is Terrain.SEA
        return Ability.NAVAL if at_sea else Ability.TACTICAL

    def level(ability: Ability) -> int:
        return leader.skills.pair_for_ability(ability)[0] if leader.skills is not None else 0

    best = max(level(ability) for ability in Ability)
    candidates = sorted((ability for ability in Ability if level(ability) == best), key=lambda a: a.value)
    # Its own stream, so the draw never shifts the turn's other random numbers
    # and the same phase always gets the same answer.
    stream = random.Random(f"sick:{state.game_number}:{state.turn_number}:{leader_id}:{label}")
    return stream.choice(candidates)


def apply_sickness(state: GameState, leader_id: int, phase: PlanPhase) -> PlanPhase:
    """``phase`` as the sick character will really carry it out."""

    leader = state.leaders.get(leader_id)
    if leader is None or not getattr(leader, "sick_this_turn", False) or phase.action is ActionCode.PRACTICE:
        return phase
    ability = _practice_ability(state, leader_id, phase.label)
    return PlanPhase(label=phase.label, action=ActionCode.PRACTICE, obj=ability.value, extra=[])
