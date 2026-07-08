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

    Every sampled ``AK3__T*.K1`` file has exactly 31 integers on this line:
    15 ``Ability`` pairs (30 values) plus one trailing value.

    **The pair's meaning is now resolved (Phase 21): ``(current_skill_level,
    current_aptitude_level)``, each 0-9** (``CTBOTH.PAS``: ``skillrange =
    0..9``). Confirmed three ways: (1) ``HostAK/TP/CTME.PAS``'s ``power``
    enum has independently-adjustable ``UpSkill``/``UpApt``/``DnSkill``/
    ``DnApt`` members, proving the engine tracks skill and aptitude as two
    separate per-ability quantities; (2) the King-creation formula
    (``RULES.AK`` ~[2.x]: a King's starting aptitude is "always 2 higher
    than his initial skill, to a maximum of 5", with race/alignment
    overrides -- e.g. an Undead King gets a Necromancy skill +1 bonus but
    *zero* starting White Magic aptitude); (3) independently verified
    against ``AK3__T1.K1``'s real skill line -- every one of the 15 pairs
    matches the formula exactly, including both override cases
    (``WHITE = (0, 0)``, ``NECROMANCY = (3, 5)``). Skill *can* exceed
    aptitude after enough practice/experience rises (rulebook [3.13]: the
    rise chance is merely halved per level beyond aptitude, not blocked) --
    confirmed in the same sample Kingdom's Necromancy pair climbing to
    ``(7, 6)`` by turn 8.

    The 31st (trailing) value's meaning is still unconfirmed -- constant
    ``3`` across all 10 sample turns for this one Kingdom (never changes
    turn-to-turn despite several skill/aptitude pairs shifting), consistent
    with something fixed at character creation rather than a 16th ability
    slot. A plausible but **unverified** guess is a race ordinal
    (``CTBOTH.PAS``'s ``race`` enum has ``Orcish = 3``, and this Kingdom's
    character names read as tribal/orcish flavor) -- not asserted as fact
    since only one Kingdom's data is available to cross-check against.
    """

    raw_values: list[int]

    def pair_for_ability(self, ability: Ability) -> tuple[int, int]:
        """Return ``(skill_level, aptitude_level)`` for ``ability``, each 0-9."""

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
