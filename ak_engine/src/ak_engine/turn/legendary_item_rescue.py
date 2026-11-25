"""What becomes of the legendary items of a hero who dies to a monster.

A monster that kills a hero (a wandering one, or a feature's guardian) has no use for what he carried
and is not a leader who could loot it. A minor magic item may be lost with its owner, but one of the
ten legendary items worth a share of the final 10% merit pool (``turn/merit_points.py
LEGENDARY_ITEM_BONUS_TREASURES``: Excalibur, the Horn of Neptune, the Holy Sword...) must not leave the
game. User ruling (2026-11-25):

* a living leader of the same Kingdom standing in the province where the hero fell takes it at once (a
  Hero before the King); otherwise
* the dead hero's squire carries it to the King at the end of the turn; and if it was the King who died,
  his squire carries it to the Royal Heir -- who appears at that same turn boundary.

``rescue_legendary_items()`` runs at the moment of death, ``deliver_squire_items()`` once at the end of
the turn, after the Royal Heirs have been installed. The squire is not a character of the game: only
the delivery is modelled.
"""

from __future__ import annotations

from dataclasses import dataclass

from ak_engine.models.game_state import GameState, LeaderState
from ak_engine.models.map import HexCoord
from ak_engine.models.treasure import Treasure
from ak_engine.turn.leader_queries import find_king_of_kingdom
from ak_engine.turn.merit_points import LEGENDARY_ITEM_BONUS_TREASURES


@dataclass(frozen=True)
class RescuedItem:
    treasure: Treasure
    taken_by_leader_id: int | None  # None: the squire will carry it to the King at the end of the turn


def _comrade_on_the_spot(state: GameState, kingdom_id: int, coord: HexCoord, dead_leader_id: int) -> LeaderState | None:
    comrades = [
        leader
        for leader in state.leaders.values()
        if leader.kingdom_id == kingdom_id
        and leader.location == coord
        and leader.leader_id != dead_leader_id
        and not leader.is_comatose
    ]
    comrades.sort(key=lambda leader: (leader.is_king, leader.leader_id))  # a Hero before the King
    return comrades[0] if comrades else None


def rescue_legendary_items(
    state: GameState, dead_leader_id: int, kingdom_id: int | None, coord: HexCoord
) -> list[RescuedItem]:
    if kingdom_id is None:
        return []  # an independent hero has no Kingdom to return the item to
    rescued: list[RescuedItem] = []
    for item in state.items_held_by(dead_leader_id):
        if item.treasure not in LEGENDARY_ITEM_BONUS_TREASURES:
            continue
        comrade = _comrade_on_the_spot(state, kingdom_id, coord, dead_leader_id)
        if comrade is not None:
            state.transfer_item(item.item_id, comrade.leader_id)
            rescued.append(RescuedItem(item.treasure, comrade.leader_id))
        else:
            state.pending_squire_deliveries.append((item.item_id, kingdom_id))
            rescued.append(RescuedItem(item.treasure, None))
    return rescued


def deliver_squire_items(state: GameState) -> None:
    """End of turn (after ``install_pending_royal_heirs()``): every squire reaches his King."""

    pending, state.pending_squire_deliveries = state.pending_squire_deliveries, []
    for item_id, kingdom_id in pending:
        king = find_king_of_kingdom(state, kingdom_id)
        if king is not None:
            state.transfer_item(item_id, king.leader_id)
