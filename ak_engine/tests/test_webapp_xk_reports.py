"""Tests for webapp/xk_reports.py -- Phase 1026, the real XK binary file
export wired into the GM web interface, alongside webapp/reports.py's
own text letter stand-in (kept, not replaced).
"""

from __future__ import annotations

from ak_engine.models.alignment import Alignment
from ak_engine.models.game_state import GameState, KingdomState, LeaderState
from ak_engine.models.map import HexCoord
from ak_engine.models.race import Race
from ak_engine.parser.xk_world import parse_xk_world
from ak_engine.webapp.xk_reports import build_xk_file_for_kingdom, build_xk_worlds_for_all_kingdoms
from ak_engine.worldgen.generate_new_game import KingSetup, generate_new_game
from ak_engine.worldgen.pascal_random import PascalRandom

import pathlib
import tempfile


def _generated_state():
    state = GameState()
    for kingdom_id, race in ((1, Race.HUMAN), (2, Race.ELVEN)):
        state.add_kingdom(KingdomState(kingdom_id, f"K{kingdom_id}", race, Alignment.NEUTRAL, HexCoord(0, 0)))
        state.add_leader(
            LeaderState(kingdom_id, kingdom_id=kingdom_id, name=f"K{kingdom_id}", location=HexCoord(0, 0), is_king=True, race=race)
        )
    kings = [KingSetup(leader_id=1, race=Race.HUMAN, home_coord=None), KingSetup(leader_id=2, race=Race.ELVEN, home_coord=None)]
    generate_new_game(PascalRandom(1), state, kings, width=18, height=9)
    return state


def _reparse(data: bytes):
    path = pathlib.Path(tempfile.mktemp())
    try:
        path.write_bytes(data)
        return parse_xk_world(path)
    finally:
        path.unlink(missing_ok=True)


def test_build_xk_file_for_kingdom_is_a_real_parseable_xk_file():
    state = _generated_state()

    data = build_xk_file_for_kingdom(state, 1)

    world = _reparse(data)
    assert world.header.kingdom_id == 1


def test_build_xk_file_for_kingdom_is_per_kingdom():
    state = _generated_state()

    data_1 = build_xk_file_for_kingdom(state, 1)
    data_2 = build_xk_file_for_kingdom(state, 2)

    assert data_1 != data_2


def test_build_xk_worlds_for_all_kingdoms_share_the_same_turn_level_blocks():
    # Each Kingdom after the first gets the previous one's own XKWorld as
    # `sibling` -- the confirmed shared/turn-level blocks (build_xk_world_
    # builder's own documented strategy) should therefore agree across
    # every Kingdom's own file for the same turn, not each independently
    # zero-filling them.
    state = _generated_state()

    worlds = build_xk_worlds_for_all_kingdoms(state)

    assert worlds[1].globals.flags_c3fc == worlds[2].globals.flags_c3fc
    assert worlds[1].globals.flags_c4fc == worlds[2].globals.flags_c4fc
    assert worlds[1].secondary_terrain.raw == worlds[2].secondary_terrain.raw


def test_build_xk_file_reflects_a_world_editor_change():
    state = _generated_state()
    home = state.leaders[1].location
    state.provinces[home].name = "Edited Capital"

    world = _reparse(build_xk_file_for_kingdom(state, 1))

    own_province = next(p for p in world.provinces if p.coord == home)
    assert own_province.name == "Edited Capital"
