"""Supreme Commander selection and duel demoralization (rulebook [7.1]).

"The two supreme commanders at the battles are the characters with the
largest troop contingents, the tiebreaker being the best Tactical
ability... If the defending armies aren't led by a character, they are
led by the 'provincial garrison commander', who has no abilities and is
present for that battle only. Before the battle, the two supreme
commanders may fight a duel. The armies which were led by the loser of
the duel will become demoralized and will be reduced in strength by 25%."

The duel *fight itself* is explicitly out of scope here: the rulebook
points to "the Special Encounter Plan rules [5.10]" for it, a whole
separate character-vs-character combat system (spells, weapon skills,
Encounter Plans) this project hasn't built. This module only provides
what's fully specified without that system: who the two commanders are,
and the fixed 25% strength penalty once a loser is known by some other
means.
"""

from __future__ import annotations

from dataclasses import dataclass

from ak_engine.turn.battle_line import BattleUnit

DUEL_DEMORALIZATION_MULTIPLIER = 0.75  # "reduced in strength by 25%"


@dataclass(slots=True)
class Commander:
    leader_id: int | None
    contingent_size: int
    tactical_ability: int


def provincial_garrison_commander(contingent_size: int) -> Commander:
    """Fallback commander for defending armies with no leading character.

    "Has no abilities and is present for that battle only" -- modeled as
    ``leader_id=None`` and ``tactical_ability=0``.
    """

    return Commander(leader_id=None, contingent_size=contingent_size, tactical_ability=0)


def select_supreme_commander(candidates: list[Commander]) -> Commander | None:
    """Largest contingent wins; ties broken by best Tactical ability."""

    if not candidates:
        return None
    return max(candidates, key=lambda c: (c.contingent_size, c.tactical_ability))


def apply_duel_demoralization(units: list[BattleUnit]) -> list[BattleUnit]:
    """Return a new list with the duel loser's armies reduced 25% in strength."""

    return [
        BattleUnit(u.army_type, u.effective_strength * DUEL_DEMORALIZATION_MULTIPLIER, source_id=u.source_id)
        for u in units
    ]
