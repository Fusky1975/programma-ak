"""Magic item / treasure model — stub for a future phase, not populated by the move parser."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class MagicItem:
    item_id: int
    name: str
    category: str
