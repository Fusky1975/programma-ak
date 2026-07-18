"""Cross-kingdom event visibility -- GENERAL INTELLIGENCE REPORT's own
real visibility rule (Phase 231).

**Real content confirmed directly from real generated letters, not
guessed**: the Desktop's real `SE3__T*.K*` files show the section as one
`Kingdom of <Name> (#<id>):` block per foreign kingdom whose activity is
visible to the reader, each followed by narrative paragraphs (battles,
movement, plagues, terrain illusions, spell effects...). No
`Rep_Intel`-equivalent procedure survives in the available `.PAS`
archive (`grep -n "^PROCEDURE\\|^FUNCTION" REPORTS.PAS` shows only
`Rep_Allies`/`Rep_Econ`/`Rep_Provs`/`Rep_Leaders`/`Rep_Armies`) -- the
same "the caller is lost, not the callees" situation already
established for other gaps, so this module's own visibility rule is
built from the rulebook's own text plus the real fixture output, not
from a lost generating procedure.

**Visibility rule**, rulebook [1.4] (quoted directly): "un giocatore
viene informato quando una provincia adiacente al suo Reame cambia di
mano e può anche ricevere informazioni sulle attività di personaggi
controllati da un altro Re quando agiscono entro i confini del suo
Reame." Read as one combined test, covering both clauses at once:
``kingdom_id`` is informed of something that happened at ``coord`` if
``coord`` is a province it owns (the second clause -- activity *inside*
its own borders) or adjacent to one it owns (the first clause -- a
bordering province changing hands, or any other event there). See
``report/turn_report.py describe_general_intelligence_report()``'s own
docstring for how this feeds the real "Kingdom of X (#N):" grouped feed
and for the deliberately narrow slice of event *sources* this project
records today (battle results only -- see that module's docstring for
the full list of confirmed-real, still-deferred event types).
"""

from __future__ import annotations

from ak_engine.models.game_state import GameState
from ak_engine.models.map import HexCoord
from ak_engine.turn.movement import MapBounds, neighbors


def is_visible_to(state: GameState, kingdom_id: int, coord: HexCoord, bounds: MapBounds) -> bool:
    """Whether ``kingdom_id`` would be informed of an event at ``coord`` --
    see module docstring for the rulebook [1.4] rule this implements.
    """

    province = state.provinces.get(coord)
    if province is not None and province.owner_kingdom_id == kingdom_id:
        return True
    for neighbor_coord in neighbors(coord, bounds):
        neighbor = state.provinces.get(neighbor_coord)
        if neighbor is not None and neighbor.owner_kingdom_id == kingdom_id:
            return True
    return False
