"""ASpy (Spy Province) execution -- rulebook [3.14] (quoted in full,
``RULES.AK`` ~line 500): "A character Spying on a province will report on
its owner, owners of adjacent provinces, taxation of the province, army
types recruitable there, and whether the province is the capital province
of the Kingdom... A character may only Spy on a province he is actually
in."

Closes the report-generation half of Phase 26's ASpy gap (the decode-only
half, and the reasons it stayed decode-only, live in
``turn/aspy_defend_decode.py``): "intelligence-report content ... needs a
report-generation system this project doesn't have at all" was true when
that was written, but Phases 58/61 now give this project exactly that --
``report/prose.py``'s rendering engine and ``report/turn_report.py``'s
first real consumer. This module only builds the *data* a spy report
needs (mirroring the "data first, prose later" split those two phases
already established for battle outcomes and spells); rendering it into
English sentences is a natural, still-open follow-up, not attempted here.

**"A character may only Spy on a province he is actually in"** is read
literally: this module always reports on the caster's own current
``LeaderState.location``, never on ``SpyProvinceRequest.target_province``.
That raw field is deliberately *not* decoded or cross-checked here --
``turn/aspy_defend_decode.py``'s own docstring already flags that no
Pascal source confirms whether it shares ``turn/hex_numbering.py``'s
empirically-inferred numbering space or the host's separate internal
``x*XMULT+y`` arithmetic. Trusting the rule's own "he is actually in" text
over an unconfirmed number space is the same kind of documented,
conservative choice this project has made before (e.g. Recruit and
Practice already resolve against the acting leader's own location rather
than a player-typed target).

**Taxation of the province is not reported** -- there's still no
per-province tax-base model anywhere in this project.
``models/game_state.py ProvinceState.tax_modifier_percent`` is a
*modifier* (Bless/Earthquake's spell effect, Phase 59), not a base tax
figure; nothing computes an actual per-province gold amount the way
``turn/recruit_execution.py`` computes kingdom-level treasury deltas.
Reporting "no data" here would be indistinguishable from reporting a
true zero, so ``SpyReport`` simply omits the field rather than guessing
one.

Reuses ``turn/movement.py neighbors()`` (already the sourced hex-adjacency
primitive every other module needing "provinces around here" already
uses) for "owners of adjacent provinces", and
``turn/recruit.py is_army_type_compatible_with_race`` (the same
race-compatibility table Recruit itself already resolves against) for
"army types recruitable there" -- rulebook [3.4]'s race-native-unit rule,
not re-derived.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ak_engine.models.army_type import ArmyType
from ak_engine.models.game_state import GameState
from ak_engine.models.map import HexCoord
from ak_engine.turn.aspy_defend_decode import SpyProvinceRequest
from ak_engine.turn.movement import NORMAL_MAP_BOUNDS, MapBounds, neighbors
from ak_engine.turn.recruit import is_army_type_compatible_with_race


@dataclass(slots=True)
class SpyReport:
    province: HexCoord
    owner_kingdom_id: int | None
    adjacent_owners: dict[HexCoord, int | None] = field(default_factory=dict)
    recruitable_army_types: list[ArmyType] = field(default_factory=list)
    is_capital: bool = False


def execute_aspy(
    state: GameState,
    leader_id: int,
    request: SpyProvinceRequest,  # noqa: ARG001 -- see module docstring: target_province isn't trusted
    *,
    board_width: int = NORMAL_MAP_BOUNDS[0],
    board_height: int = NORMAL_MAP_BOUNDS[1],
) -> SpyReport | None:
    """Builds the intelligence report for the caster's own current province.

    Returns ``None`` if the caster's location isn't a known province (no
    ``GameState`` in this project's tests populates every hex -- the same
    "insufficient data, not a guessed result" convention used throughout).
    """

    del request  # see module docstring
    leader = state.leaders[leader_id]
    province = state.provinces.get(leader.location)
    if province is None:
        return None

    bounds = MapBounds(board_width, board_height)
    adjacent_owners: dict[HexCoord, int | None] = {}
    for neighbor_coord in neighbors(leader.location, bounds):
        neighbor_province = state.provinces.get(neighbor_coord)
        if neighbor_province is not None:
            adjacent_owners[neighbor_coord] = neighbor_province.owner_kingdom_id

    recruitable = [
        army_type for army_type in ArmyType if is_army_type_compatible_with_race(army_type, province.race)
    ]

    is_capital = False
    if province.owner_kingdom_id is not None:
        kingdom = state.kingdoms.get(province.owner_kingdom_id)
        is_capital = kingdom is not None and kingdom.home_province == leader.location

    return SpyReport(
        province=leader.location,
        owner_kingdom_id=province.owner_kingdom_id,
        adjacent_owners=adjacent_owners,
        recruitable_army_types=recruitable,
        is_capital=is_capital,
    )
