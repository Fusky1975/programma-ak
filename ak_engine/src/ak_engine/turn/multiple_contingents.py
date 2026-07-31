"""Multiple Contingents (rulebook [7.8]).

"If two characters who are controlled by the same King (or, two
characters employed by different Kings who are allied with each other)
attack the same province in the same action phase, they may fight
together in the same battle. If they moved from the same province in
making the attack, the chances of uniting for the battle are very good,
but if they attacked the province from opposite directions they probably
will fight the defenders in separate battles."

**Phase 307: replaces the invented ``SAME_ORIGIN_UNITE_CHANCE``/
``DIFFERENT_ORIGIN_UNITE_CHANCE`` constants with the real MARCH TABLE.**
[7.8]'s own prose gives no numbers for "very good chance"/"probably
separate", but a dedicated table exists in both available sources --
`RULES.AK [4.12] MARCH TABLE` (English) and Regolamento AK.txt's own
"TABELLA DELLA MARCIA" (Italian), word-for-word the same figures:

    Ability   Extra moves for...     Contingents Unify %
     Level    Speed 1-2   Speed 3+   Distance to 2nd force: 0   1   2
       0         0           0                               80  50  20
       1         0           1                               90  60  30
       2         1           1                              100  70  40
       3         1           2                              100  80  50
       4         2           2                              100  90  60

    "Eagles and Dragons are not affected by March ability."
    "Contingent Unity shows the chance that two leaders invading a
    province will join together for the battle, depending on whether
    they invade from the same province, adjacent provinces or
    non-adjacent provinces."

``MARCH_UNITE_CHANCE`` below models only the "Contingents Unify %" half
of this table -- the "Extra moves for..." half is [4.12]'s own separate
land-movement-range bonus (`turn/movement.py`'s own hex-distance budget),
a distinct, still-unmodeled gap this phase doesn't attempt to close.

**Whose March level applies, and what "distance" means, when the table
itself only ever describes one character's own advantage**: [4.12]'s
prose reads "the character with Forced March ability has a *better*
chance of uniting with another character" -- singular, about the one
character's own advantage, not a combined figure from both sides. Read
here as: each attacker's own chance of successfully joining an
already-forming group is driven by *that attacker's own* March skill
level (``roll_unite_for_battle(a, b, rng)`` uses ``a``'s own
``march_level`` -- ``a`` is always the character being asked "does this
one manage to unite", per ``group_attackers_into_battles()``'s own
call site), not the group's founding member's level or some combined
figure. "Distance to 2nd force" is read literally as ``hex_distance()``
between the two attackers' own origin provinces at the start of the
invasion -- the same real distance metric this project's movement code
already uses elsewhere, not a guessed proxy. The table gives no data
past distance 2; a real distance beyond that clamps to the distance-2
column rather than guessing at further decay, the same "clamp to the
last known value" convention this project's own skill-level caps
already use (e.g. ``PERSONAL_COMBAT_SPELL_LEVEL_CAP``).

**Naval's own analogous bonus** ([4.13]: "when invading a province, the
character has a better chance of joining with another character... in a
manner similar to March ability") has no numeric table of its own in
either source -- left unmodeled, the same "confirmed mechanic, no
sourced magnitude" treatment this project gives every other such gap.
``Attacker.march_level`` is read unconditionally regardless of whether
the invasion was a land or sea move; a caller invading by sea still
supplies their own March level (typically 0, since it's irrelevant to
them), which is the documented, conservative fallback rather than
inventing a Naval-keyed table.

**Eagles/Dragons' own carve-out** ("not affected by March ability") is
not modeled -- ``Attacker`` has no army-composition field to check
whether a given attacker's forces are entirely Eagles/Dragons, and
guessing which army-type mix should bypass the table is out of scope
for this phase.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from ak_engine.models.map import HexCoord
from ak_engine.turn.movement import hex_distance

# RULES.AK [4.12] MARCH TABLE / Regolamento AK.txt's own "TABELLA DELLA
# MARCIA" -- "Contingents Unify %" half only (see module docstring).
# Keyed by March ability level (0-4); each value is (distance 0, 1, 2+).
MARCH_UNITE_CHANCE: dict[int, tuple[float, float, float]] = {
    0: (0.80, 0.50, 0.20),
    1: (0.90, 0.60, 0.30),
    2: (1.00, 0.70, 0.40),
    3: (1.00, 0.80, 0.50),
    4: (1.00, 0.90, 0.60),
}
MARCH_UNITE_MAX_LEVEL = 4
MARCH_UNITE_MAX_DISTANCE = 2


def march_unite_chance(march_level: int, distance_provinces: int) -> float:
    """The MARCH TABLE's own "Contingents Unify %" lookup, clamped at both
    ends (see module docstring for why beyond-table inputs clamp rather
    than extrapolate).
    """

    level = min(max(march_level, 0), MARCH_UNITE_MAX_LEVEL)
    distance = min(max(distance_provinces, 0), MARCH_UNITE_MAX_DISTANCE)
    return MARCH_UNITE_CHANCE[level][distance]


@dataclass(slots=True)
class Attacker:
    leader_id: int
    kingdom_id: int
    origin_province: HexCoord
    # Phase 307: the attacker's own effective March ability level -- see
    # module docstring for why this attacker's own level (not the other
    # side's) drives their own chance of uniting. Defaults to 0 (the
    # table's own floor) for any caller that doesn't look one up.
    march_level: int = 0


def eligible_to_unite(a: Attacker, b: Attacker, allied_kingdoms: set[frozenset[int]]) -> bool:
    """Same King, or two Kings allied with each other."""

    if a.kingdom_id == b.kingdom_id:
        return True
    return frozenset({a.kingdom_id, b.kingdom_id}) in allied_kingdoms


def roll_unite_for_battle(a: Attacker, b: Attacker, rng: random.Random) -> bool:
    distance = hex_distance(a.origin_province, b.origin_province)
    chance = march_unite_chance(a.march_level, distance)
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
