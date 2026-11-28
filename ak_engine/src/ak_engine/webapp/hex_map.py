"""SVG hex-grid geometry and coloring for the Provinces page's visual map
(GM interface, Phase 981) -- a purely presentational helper, no game
logic: it only turns an already-built ``GameState`` into draw-ready
``HexCell`` records, the same "webapp is a presentation layer over the
engine" separation every other ``webapp/`` module already follows.

**Grid geometry**: pointy-top hexagons, offset rows -- **even** ``y`` rows
shifted right by half a hex-width -- matches ``turn/movement.py
neighbors()``'s own real adjacency table exactly: since Phase 314 an even
row's upper neighbors are ``(x, y-1)`` and ``(x+1, y-1)``, so an even row
sits half a hex to the right of the odd rows around it. (Until 2026-11-28
this drew the odd rows shifted instead, so the map showed Couatlia, not
Kalabo, next to a Home the engine -- and every report -- puts Kalabo beside;
``tests/test_hex_map.py`` now checks every engine neighbor is drawn touching.) The map's own real horizontal
wraparound (``turn/movement.py hex_distance_wrapped()``) is not drawn
specially here -- same "flat rectangle" convention the existing ASCII
map (``report/ascii_map.py``) already uses, not a cylinder projection.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from ak_engine.models.feature import FEATURE_TYPE_NAMES
from ak_engine.models.game_state import GameState, KingdomState
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.race import RACE_NAME

HEX_SIZE = 22.0  # center-to-vertex radius, px -- large enough to stay clickable at 30 hexes wide

TERRAIN_COLOR: dict[Terrain, str] = {
    Terrain.PLAINS: "#d9c88f",
    Terrain.FOREST: "#3f6b35",
    Terrain.JUNGLE: "#1f5c2e",
    Terrain.MTNS: "#8a8378",
    Terrain.DESERT: "#e0b96a",
    Terrain.SEA: "#4a7fa8",
    # NO_TERRAIN never actually appears on a generated map (worldgen/
    # place_map.py's own docstring), but every Terrain member needs an
    # entry so a hand-built/test province never KeyErrors here.
    Terrain.NO_TERRAIN: "#bbbbbb",
}

TERRAIN_LABEL: dict[Terrain, str] = {
    Terrain.PLAINS: "Plains",
    Terrain.FOREST: "Forest",
    Terrain.JUNGLE: "Jungle",
    Terrain.MTNS: "Mountains",
    Terrain.DESERT: "Desert",
    Terrain.SEA: "Sea",
    Terrain.NO_TERRAIN: "No Terrain",
}

_UNOWNED_STROKE = "#9c8c6e"

# A 12-color qualitative palette (one slot per rulebook [1.0] max player
# count), cycled by kingdom_id for the >12 case rather than erroring --
# chosen for mutual contrast against both the muted terrain fills above
# and the parchment page background, not reused from any existing
# in-project palette (none of this project's other CSS needed 12
# simultaneously-distinct hues before this map).
_KINGDOM_COLORS: tuple[str, ...] = (
    "#c0392b",  # red
    "#2471a3",  # blue
    "#1e8449",  # green
    "#b9770e",  # orange
    "#6c3483",  # purple
    "#17a2a2",  # teal
    "#b7950b",  # mustard
    "#922b21",  # brick
    "#1a5276",  # navy
    "#196f3d",  # forest green
    "#a04000",  # burnt orange
    "#4a235a",  # plum
)


def kingdom_color(kingdom_id: int) -> str:
    return _KINGDOM_COLORS[kingdom_id % len(_KINGDOM_COLORS)]


@dataclass(slots=True)
class HexCell:
    x: int
    y: int
    points: str  # SVG <polygon points="..."> value
    fill: str
    stroke: str
    stroke_width: float
    is_home: bool
    home_marker: tuple[float, float] | None  # (cx, cy) for the home-province dot, else None
    feature_marker: tuple[float, float] | None  # (cx, cy) for the special-feature marker, else None
    first_feature_id: int | None  # for the Features map's own click-through, None if no feature here
    title: str  # tooltip text


@dataclass(slots=True)
class HexMap:
    cells: list[HexCell]
    width: float
    height: float


def _hex_center(x: int, y: int, size: float) -> tuple[float, float]:
    hex_width = math.sqrt(3) * size
    hex_height = 2 * size
    x_offset = 0.0 if y % 2 else hex_width / 2  # even rows are the shifted ones (see the module docstring)
    cx = size + x * hex_width + x_offset
    cy = size + y * (hex_height * 0.75)
    return cx, cy


def _hex_points(cx: float, cy: float, size: float) -> str:
    corners = []
    for i in range(6):
        angle = math.radians(60 * i - 30)
        corners.append(f"{cx + size * math.cos(angle):.1f},{cy + size * math.sin(angle):.1f}")
    return " ".join(corners)


def build_hex_map(state: GameState, *, size: float = HEX_SIZE) -> HexMap:
    """One ``HexCell`` per ``state.provinces`` entry, ready for an SVG
    template to draw directly -- fill by terrain, stroke by owning
    Kingdom (``kingdom_color()``) or a neutral tone when unowned, plus a
    small marker on each Kingdom's own current ``home_province``.
    """

    home_coords: dict[HexCoord, list[KingdomState]] = {}
    for kingdom in state.kingdoms.values():
        home_coords.setdefault(kingdom.home_province, []).append(kingdom)

    features_by_coord: dict[HexCoord, list[int]] = {}
    for feature_id, feature in state.features.items():
        features_by_coord.setdefault(feature.coord, []).append(feature_id)

    cells: list[HexCell] = []
    max_x = max_y = 0
    for coord, province in state.provinces.items():
        cx, cy = _hex_center(coord.x, coord.y, size)
        max_x = max(max_x, coord.x)
        max_y = max(max_y, coord.y)

        owner = state.kingdoms.get(province.owner_kingdom_id) if province.owner_kingdom_id is not None else None
        stroke = kingdom_color(owner.kingdom_id) if owner is not None else _UNOWNED_STROKE
        stroke_width = 3.0 if owner is not None else 1.0

        homes_here = home_coords.get(coord, [])
        feature_ids_here = features_by_coord.get(coord, [])
        # The province's name too (and its 4-digit code, as the reports print it: "Kalabo (#1203)"), so a place read in a
        # report can be found on the map.
        title_parts = [
            f"{province.name} (#{coord.x:02d}{coord.y:02d})" if province.name else f"({coord.x}, {coord.y})",
            TERRAIN_LABEL.get(province.terrain, province.terrain.name),
            RACE_NAME.get(province.race, province.race.name),
            owner.name if owner is not None else "Unowned",
        ]
        if homes_here:
            title_parts.append("Home of " + ", ".join(k.name for k in homes_here))
        if feature_ids_here:
            kinds = [FEATURE_TYPE_NAMES.get(state.features[fid].kind, state.features[fid].kind.name) for fid in feature_ids_here]
            title_parts.append("Feature: " + ", ".join(kinds))

        cells.append(
            HexCell(
                x=coord.x,
                y=coord.y,
                points=_hex_points(cx, cy, size),
                fill=TERRAIN_COLOR.get(province.terrain, TERRAIN_COLOR[Terrain.NO_TERRAIN]),
                stroke=stroke,
                stroke_width=stroke_width,
                is_home=bool(homes_here),
                home_marker=(cx, cy) if homes_here else None,
                # Offset toward the hex's own top-right corner, not dead
                # center, so it stays visible alongside a home_marker on
                # the same cell -- every King Home carries exactly 2
                # real Features (worldgen/feature_generation.py
                # first_2k_home_index()), so the two markers coexist on
                # a real cell often enough to need their own positions.
                feature_marker=(cx + size * 0.45, cy - size * 0.45) if feature_ids_here else None,
                first_feature_id=feature_ids_here[0] if feature_ids_here else None,
                title=" · ".join(title_parts),
            )
        )

    hex_width = math.sqrt(3) * size
    hex_height = 2 * size
    total_width = hex_width * (max_x + 1) + hex_width / 2 + size
    total_height = hex_height * 0.75 * (max_y + 1) + hex_height / 4 + size
    return HexMap(cells=cells, width=total_width, height=total_height)
