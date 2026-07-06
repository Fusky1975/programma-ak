"""Turn/season model — stub for a future phase, not populated by the move parser."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Turn:
    number: int
    season: str
