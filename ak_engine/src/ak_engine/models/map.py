"""Map/feature model — stub for a future phase, not populated by the move parser."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Feature:
    x: int
    y: int
    kind: str
    owner_kingdom: int | None = None
