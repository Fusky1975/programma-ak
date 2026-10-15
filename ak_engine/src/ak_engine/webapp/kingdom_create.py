"""Shared Kingdom-creation logic for the GM world editor (Phase 1029).

Factored out of ``webapp/app.py kingdom_create()`` so the exact same
validation and Home-seating effects (see this module's own docstring
for what's replicated from ``worldgen/generate_new_game.py`` and what's
deliberately not) are reachable from two different entry points: the
original "type in a coordinate" form on the World Created screen, and
the "Create Kingdom Here" link scoped to one specific province -- see
``app.py``'s own ``kingdom_create``/``province_kingdom_create`` routes.
"""

from __future__ import annotations

from ak_engine.models.alignment import Alignment
from ak_engine.models.enums import Ability
from ak_engine.models.game_state import GameState, KingdomState, LeaderState
from ak_engine.models.map import HexCoord
from ak_engine.models.race import Race
from ak_engine.models.temper import Temper
from ak_engine.worldgen.generate_new_game import STARTING_TREASURY
from ak_engine.worldgen.king_talent import build_king_skill_table
from ak_engine.worldgen.province_tax import HOME_OVERRIDE_TAX


class NoProvinceAtCoordError(Exception):
    """Raised when the chosen coordinate has no province at all."""


class ProvinceAlreadyOwnedError(Exception):
    """Raised when the chosen province already belongs to another Kingdom."""

    def __init__(self, owner_name: str):
        self.owner_name = owner_name
        super().__init__(owner_name)


class ProvinceAlreadyAHomeError(Exception):
    """Raised when the chosen province is already some Kingdom's own Home."""


def create_kingdom(
    state: GameState,
    *,
    name: str,
    race: Race,
    alignment: Alignment,
    temper: Temper,
    talent_allocation: dict[Ability, int],
    coord: HexCoord,
) -> int:
    """Creates a new Kingdom and its King at ``coord``, returning the new
    ``kingdom_id`` (always equal to the King's own ``leader_id``, the
    project-wide invariant every Kingdom relies on). ``coord`` must name
    an existing, currently-unowned province that isn't already another
    Kingdom's own Home -- stealing a province out from under its real
    owner is not something this should do silently.

    Matches ``worldgen/generate_new_game.py``'s own King Home seating
    (ownership, the fixed ``HOME_OVERRIDE_TAX``, native race becomes the
    King's own, 100% exploration -- confirmed real across every Turn-0
    PROVINCES sample, that module's own Phase 428 addendum) --
    deliberately NOT replicated: the RNG-dependent recruit-slot formulas
    and initial-army budget, which need the whole-map generation context
    a single-Kingdom action doesn't have. Add Army / edit the recruit
    types by hand afterward if this new Kingdom needs either.
    """

    province = state.provinces.get(coord)
    if province is None:
        raise NoProvinceAtCoordError(coord)
    if province.owner_kingdom_id is not None:
        raise ProvinceAlreadyOwnedError(state.kingdoms[province.owner_kingdom_id].name)
    if any(kingdom.home_province == coord for kingdom in state.kingdoms.values()):
        raise ProvinceAlreadyAHomeError(coord)

    kingdom_id = state.new_kingdom_id()
    skills = build_king_skill_table(talent_allocation, alignment)
    state.add_kingdom(
        KingdomState(
            kingdom_id=kingdom_id,
            name=name,
            race=race,
            alignment=alignment,
            home_province=coord,
            treasury=STARTING_TREASURY,
        )
    )
    state.add_leader(
        LeaderState(
            leader_id=kingdom_id,
            kingdom_id=kingdom_id,
            name=name,
            location=coord,
            skills=skills,
            is_king=True,
            temper=temper,
            alignment=alignment,
            race=race,
            birth_x=coord.x,
            birth_y=coord.y,
        )
    )
    province.owner_kingdom_id = kingdom_id
    province.tax = HOME_OVERRIDE_TAX
    province.race = race
    province.explored_percent = 100
    province.explored_percent_by_kingdom[kingdom_id] = 100
    return kingdom_id
