"""Tests for webapp/kingdom_create.py -- Phase 1029, the shared Kingdom-
creation logic reachable from both the World Created screen's own
"type in a coordinate" form and the new "Create Kingdom Here" link
scoped to one specific province (see webapp/app.py's own kingdom_
create()/province_kingdom_create() routes)."""

from __future__ import annotations

import pytest

from ak_engine.models.alignment import Alignment
from ak_engine.models.enums import Ability
from ak_engine.models.game_state import GameState, KingdomState, ProvinceState
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.race import Race
from ak_engine.models.temper import Temper
from ak_engine.webapp.kingdom_create import (
    NoProvinceAtCoordError,
    ProvinceAlreadyAHomeError,
    ProvinceAlreadyOwnedError,
    create_kingdom,
)


def _talents():
    return {Ability.MELEE: 2, Ability.SAGE: 2}


def test_create_kingdom_builds_a_real_kingdom_and_king():
    state = GameState()
    state.add_province(ProvinceState(coord=HexCoord(3, 4), terrain=Terrain.PLAINS, race=Race.ORCISH))

    kingdom_id = create_kingdom(
        state,
        name="Sir Newling",
        race=Race.DWARVEN,
        alignment=Alignment.EVIL,
        temper=Temper.CAUTIOUS,
        talent_allocation=_talents(),
        coord=HexCoord(3, 4),
    )

    kingdom = state.kingdoms[kingdom_id]
    assert kingdom.name == "Sir Newling"
    assert kingdom.race == Race.DWARVEN
    assert kingdom.home_province == HexCoord(3, 4)

    king = state.leaders[kingdom_id]
    assert king.leader_id == kingdom_id  # the project-wide King invariant
    assert king.is_king is True

    province = state.provinces[HexCoord(3, 4)]
    assert province.owner_kingdom_id == kingdom_id
    assert province.race == Race.DWARVEN  # overwritten to the King's own
    assert province.explored_percent == 100
    # Phase 1038: the Home province seeds the new Kingdom's own tracked
    # primary map region.
    assert kingdom.map_primary_region_columns == {3}


def test_create_kingdom_rejects_a_coordinate_with_no_province():
    state = GameState()

    with pytest.raises(NoProvinceAtCoordError):
        create_kingdom(
            state,
            name="Someone",
            race=Race.HUMAN,
            alignment=Alignment.GOOD,
            temper=Temper.BRAVE,
            talent_allocation=_talents(),
            coord=HexCoord(99, 99),
        )
    assert state.kingdoms == {}


def test_create_kingdom_rejects_an_already_owned_province():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Existing", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_province(ProvinceState(coord=HexCoord(0, 0), terrain=Terrain.PLAINS, race=Race.HUMAN, owner_kingdom_id=1))

    with pytest.raises(ProvinceAlreadyOwnedError) as excinfo:
        create_kingdom(
            state,
            name="Usurper",
            race=Race.HUMAN,
            alignment=Alignment.GOOD,
            temper=Temper.BRAVE,
            talent_allocation=_talents(),
            coord=HexCoord(0, 0),
        )
    assert excinfo.value.owner_name == "Existing"
    assert len(state.kingdoms) == 1


def test_create_kingdom_rejects_an_already_home_province():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Existing", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    # Unowned (province_set_home only moves the Home marker, confirmed in
    # its own route docstring) but already a Home -- the rarer of the two
    # real collision shapes this function must still catch.
    state.add_province(ProvinceState(coord=HexCoord(0, 0), terrain=Terrain.PLAINS, race=Race.HUMAN))

    with pytest.raises(ProvinceAlreadyAHomeError):
        create_kingdom(
            state,
            name="Someone",
            race=Race.HUMAN,
            alignment=Alignment.GOOD,
            temper=Temper.BRAVE,
            talent_allocation=_talents(),
            coord=HexCoord(0, 0),
        )
    assert len(state.kingdoms) == 1
