"""GM-facing Kingdom deletion for the world editor.

Unlike Army/Leader/Feature/Province, a Kingdom's own id is one of the
most widely-depended-upon invariants in this engine: a direct grep of
every ``state.kingdoms[...]`` bracket-index in production code (not
``.get()``) finds dozens of real sites, all of them one of exactly four
shapes -- derived from a live ``Leader.kingdom_id``, a live ``Army.
kingdom_id``, a live ``Province.owner_kingdom_id``, or ``GameState.
emperor_kingdom_id``. The engine has no "Kingdom elimination" mechanic
of its own (a dying King always gets a Royal Heir, rulebook [2.1] --
this module's own deletion is purely an editor/GM power-tool action,
never a modeled gameplay event), so nothing already handles a Kingdom
simply vanishing out from under its own Leaders/Armies/Provinces.

``delete_kingdom()`` therefore cascades fully rather than leaving any
of those four reference shapes dangling:

- Every Leader (the King included) whose own ``kingdom_id`` matches is
  removed -- a plain dict pop, the same "not GameState.remove_leader()"
  choice ``leader_delete()`` already makes and for the same reason: that
  method is the real in-game death mechanic (Royal Heir succession,
  archival, merit penalty), none of which applies to a Kingdom that is
  itself being deleted.
- Every Army whose own ``kingdom_id`` matches is removed (``GameState.
  remove_army()``, already a plain, side-effect-free pop).
- Every Province this Kingdom owns is released to unowned (``owner_
  kingdom_id = None``) rather than deleted -- the land itself isn't
  this Kingdom's to take with it. Any contested-battle state pointing
  at this Kingdom is cleared the same way ``turn/battle_orchestrator.py``
  already clears it elsewhere (``contested_by_kingdom_id`` and its own
  ``contested_from_coord`` together), and this Kingdom's own stale
  per-Kingdom exploration entry is dropped.
- Every Feature's own ``discovered_by_kingdom`` entry for this Kingdom
  is dropped (cosmetic cleanup -- already read via ``.get()``, never a
  crash risk, but a deleted Kingdom shouldn't still look like it
  discovered something).
- Every pairwise diplomacy/contact collection keyed by this Kingdom's
  id -- ``allied_kingdoms``, ``diplomatic_relations``/``_since``,
  ``kingdoms_met``/``_since``, ``treat_permissions``, ``break_treat_
  orders`` -- has every entry naming this Kingdom removed. ``turn/
  emperor_election.py _alliance_component()``'s own real BFS over
  ``allied_kingdoms`` is the one confirmed live consumer that would
  otherwise hand a stale id back to a caller that *does* bracket-index
  ``state.kingdoms[...]`` with it.

Refuses outright (``KingdomHasEmperorError``) rather than silently
un-crowning when this Kingdom currently holds ``GameState.emperor_
kingdom_id`` -- confirmed directly indexed, unguarded, in both ``report/
turn_report.py`` and ``turn/victory_points.py`` (``state.kingdoms[state.
emperor_kingdom_id]``), so leaving a stale Emperor id would crash the
very next turn processed. Clearing the crown is a bigger decision than
a delete button should make on its own.
"""

from __future__ import annotations

from ak_engine.models.game_state import GameState


class KingdomHasEmperorError(Exception):
    """Raised when asked to delete the Kingdom currently crowned Emperor."""


def delete_kingdom(state: GameState, kingdom_id: int) -> None:
    if state.emperor_kingdom_id == kingdom_id:
        raise KingdomHasEmperorError(kingdom_id)

    for leader_id in [lid for lid, leader in state.leaders.items() if leader.kingdom_id == kingdom_id]:
        del state.leaders[leader_id]

    for army_id in [aid for aid, army in state.armies.items() if army.kingdom_id == kingdom_id]:
        state.remove_army(army_id)

    for province in state.provinces.values():
        if province.owner_kingdom_id == kingdom_id:
            province.owner_kingdom_id = None
        if province.contested_by_kingdom_id == kingdom_id:
            province.contested_by_kingdom_id = None
            province.contested_from_coord = None
        province.explored_percent_by_kingdom.pop(kingdom_id, None)

    for feature in state.features.values():
        feature.discovered_by_kingdom.pop(kingdom_id, None)

    state.allied_kingdoms = {pair for pair in state.allied_kingdoms if kingdom_id not in pair}
    state.diplomatic_relations = {
        pair: relation for pair, relation in state.diplomatic_relations.items() if kingdom_id not in pair
    }
    state.diplomatic_relations_since = {
        pair: turn for pair, turn in state.diplomatic_relations_since.items() if kingdom_id not in pair
    }
    state.kingdoms_met = {pair for pair in state.kingdoms_met if kingdom_id not in pair}
    state.kingdoms_met_since = {pair: turn for pair, turn in state.kingdoms_met_since.items() if kingdom_id not in pair}
    state.treat_permissions = {
        (a, b) for a, b in state.treat_permissions if kingdom_id not in (a, b)
    }
    state.break_treat_orders = {
        (a, b) for a, b in state.break_treat_orders if kingdom_id not in (a, b)
    }

    del state.kingdoms[kingdom_id]
