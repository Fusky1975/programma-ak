"""Multiple Contingents (rulebook [7.8]).

"If two characters who are controlled by the same King (or, two
characters employed by different Kings who are allied with each other)
attack the same province in the same action phase, they may fight
together in the same battle. If they moved from the same province in
making the attack, the chances of uniting for the battle are very good,
but if they attacked the province from opposite directions they probably
will fight the defenders in separate battles."

No numbers are given for "very good chance" / "probably separate" --
``SAME_ORIGIN_UNITE_CHANCE`` and ``DIFFERENT_ORIGIN_UNITE_CHANCE`` are
deliberate, documented design choices, not sourced rules.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from ak_engine.models.map import HexCoord

SAME_ORIGIN_UNITE_CHANCE = 0.85
DIFFERENT_ORIGIN_UNITE_CHANCE = 0.30


@dataclass(slots=True)
class Attacker:
    leader_id: int
    kingdom_id: int
    origin_province: HexCoord


def eligible_to_unite(a: Attacker, b: Attacker, allied_kingdoms: set[frozenset[int]]) -> bool:
    """Same King, or two Kings allied with each other."""

    if a.kingdom_id == b.kingdom_id:
        return True
    return frozenset({a.kingdom_id, b.kingdom_id}) in allied_kingdoms


def roll_unite_for_battle(a: Attacker, b: Attacker, rng: random.Random) -> bool:
    chance = SAME_ORIGIN_UNITE_CHANCE if a.origin_province == b.origin_province else DIFFERENT_ORIGIN_UNITE_CHANCE
    return rng.random() < chance


def group_attackers_into_battles(
    attackers: list[Attacker], allied_kingdoms: set[frozenset[int]], rng: random.Random
) -> list[list[Attacker]]:
    """Partition attackers targeting the same province into one or more battles.

    Greedy: each attacker joins the first eligible, already-formed group
    it rolls a successful "unite" check against; otherwise it starts a
    new group (a separate battle).
    """

    groups: list[list[Attacker]] = []
    for attacker in attackers:
        joined = False
        for group in groups:
            if eligible_to_unite(attacker, group[0], allied_kingdoms) and roll_unite_for_battle(
                attacker, group[0], rng
            ):
                group.append(attacker)
                joined = True
                break
        if not joined:
            groups.append([attacker])
    return groups
