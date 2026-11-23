"""Spies watching a province: what happens there in that phase reaches their Kingdom.

Rulebook [3.14]: "Quando un personaggio spia in una provincia, avrà anche la possibilità di
venire a conoscenza di tutto quello che vi avviene in quella fase. Gli avvenimenti verranno
riportati nel Rapporto Informativo, che è separato dal rapporto del personaggio (si trova alla
fine del turno)." And [4.3.3]: a Spy skill of at least 1 "può essere di grande aiuto nella
stesura del Rapporto Informativo Generale, anche se non gli è stato dato l'ordine di spiare".

In the original this is ``RUMORS.PAS Set_Intel``: for the province and phase of an event, every
character of a Kingdom adds to that Kingdom's "intel level" -- ``Add_Spy(1)`` for a Spy order
there or a Trail that caught its target, ``Add_Spy(2)`` for a Move/Explore there by a character
with Spy skill above 0 -- and the event is told to the Kingdom when its tier is at least the
threshold that intel level maps to. Every threshold for a level of 1 or more (tiers 3 to 8) is
at or below the lowest tier of the news the GENERAL INTELLIGENCE REPORT carries today (``S_Army``
and up), so the tier test never rejects anything here: any watch shows everything that happened
there in that phase, and the level only matters once lower-tier news is added.

A watch is recorded as ``(kingdom id, province, phase label)`` in ``GameState.spy_watches``;
``describe_general_intelligence_report()`` reads it (``GameState.spy_watched()``).
"""

from __future__ import annotations

from ak_engine.models.enums import Ability, ActionCode
from ak_engine.models.game_state import GameState
from ak_engine.models.plan import PlanPhase


def note_spy_watch(state: GameState, leader_id: int, phase: PlanPhase, result: object) -> None:
    """Records the watch (if any) that ``phase``, just carried out by ``leader_id`` with
    ``result``, gives the leader's Kingdom.
    """

    leader = state.leaders.get(leader_id)
    if leader is None or leader.kingdom_id is None or result is None:
        return

    coord = None
    action = phase.action
    if action is ActionCode.ASPY:
        coord = getattr(result, "province", None)
    elif action is ActionCode.TRAIL:
        if getattr(result, "spied_on", False):
            from ak_engine.turn.trail_decode import decode_trail_phase

            target = state.leaders.get(decode_trail_phase(phase).target_character_id)
            coord = target.location if target is not None else None
    elif action in (ActionCode.LMOVE, ActionCode.EXPLORE):
        from ak_engine.turn.discovery_effects import effective_skill_level

        if effective_skill_level(state, leader, Ability.SPY) > 0:
            if action is ActionCode.LMOVE:
                coord = result.new_location if getattr(result, "moved", False) else None
            else:
                coord = leader.location

    if coord is not None:
        state.spy_watches.append((leader.kingdom_id, coord, phase.label))
