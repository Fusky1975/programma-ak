"""Tiny, dependency-free leader-lookup helpers shared across many turn/*
modules.

``find_king_of_kingdom()`` originally lived in ``turn/battle_orchestrator.py``,
but several of its would-be callers -- ``turn/office_holder.py``, ``turn/
discovery_effects.py``, ``turn/challenge_execution.py`` -- are themselves
imported *by* ``battle_orchestrator.py``, so importing it from there would
create a circular import. Kept here instead, at the bottom of the ``turn/``
dependency graph (this module imports nothing from ``turn/*``), so every
module can import it with zero cycle risk.

``turn/battle_orchestrator.py`` imports it from here too (not a redefinition),
so every pre-existing caller that already imports it from
``turn.battle_orchestrator`` (``turn/valhalla_execution.py``, ``report/
turn_report.py``) keeps working unchanged.
"""

from __future__ import annotations

from ak_engine.models.game_state import GameState, LeaderState


def find_king_of_kingdom(state: GameState, kingdom_id: int) -> LeaderState | None:
    for leader in state.leaders.values():
        if leader.kingdom_id == kingdom_id and leader.is_king:
            return leader
    return None


def release_armies_to_garrison(state: GameState, leader_id: int) -> list[int]:
    """The armies a leader commands pass to the Garrison Commander of where they stand
    (``commanded_by = None``) -- what happens when a Hero leaves a Kingdom's service (Fire,
    desertion): he wanders off alone and the Kingdom keeps its armies. Returns their ids."""

    released: list[int] = []
    for army in state.armies_commanded_by(leader_id):
        army.commanded_by = None
        released.append(army.army_id)
    return released
