"""Top-level parsed representation of a player move-submission (.K1) file."""

from __future__ import annotations

from dataclasses import dataclass, field

from ak_engine.models.enums import Ability
from ak_engine.models.leader import Leader


@dataclass(slots=True)
class KingdomMoveHeader:
    """Raw fields from the ``M ...`` header line.

    Only ``kingdom_number`` (field 0) and the trailing constant fields are
    reasonably well understood from the available samples; the remaining
    fields are kept unvalidated pending cross-reference with
    ``HostAK/TP/DEF2.PAS`` (``Read_Moves``) and the game manuals.
    """

    raw_fields: list[int]

    @property
    def kingdom_number(self) -> int:
        # Stable at 27 across every AK3__T*.K1 sample -> likely a kingdom id.
        return self.raw_fields[0]


@dataclass(slots=True)
class SkillTable:
    """Raw integers from the skill-values line.

    Every sampled ``AK3__T*.K1`` file has exactly 31 integers on this line,
    not the 30 (15 pairs) originally expected -- kept as a flat raw list
    rather than forced into pairs, since the true structure (15 abilities *
    2 + one trailing value of unknown meaning?) is not yet confirmed against
    ``HostAK/TP/DEF2.PAS``.
    """

    raw_values: list[int]

    def pair_for_ability(self, ability: Ability) -> tuple[int, int]:
        i = ability.value * 2
        return (self.raw_values[i], self.raw_values[i + 1])


@dataclass(slots=True)
class Kingdom:
    """Everything parsed out of one player move-submission file."""

    source_filename: str
    king_name: str
    king_title: str | None
    header: KingdomMoveHeader
    skills: SkillTable
    leaders: list[Leader] = field(default_factory=list)
    trailer_comments: str = ""
