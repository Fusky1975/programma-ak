"""Army model — stub for a future phase, not populated by the move parser."""

from __future__ import annotations

from dataclasses import dataclass, field

from ak_engine.models.map import HexCoord


@dataclass(slots=True)
class Army:
    army_id: int
    leader_id: int
    hex_coord: HexCoord
    unit_counts: dict[str, int] = field(default_factory=dict)
