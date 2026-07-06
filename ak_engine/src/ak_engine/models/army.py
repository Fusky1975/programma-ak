"""Army model — stub for a future phase, not populated by the move parser."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class Army:
    army_id: int
    leader_id: int
    hex_coord: tuple[int, int]
    unit_counts: dict[str, int] = field(default_factory=dict)
