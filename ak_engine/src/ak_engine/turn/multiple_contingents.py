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
manner similar to March ability") had no numeric table of its own in
either source -- **Phase 754, `Desktop/MOVE.md`, closes this at ALTA
confidence, not CERTO**: section 5.3 presents one table titled "March e
Naval" carrying both the speed-bonus columns and the "Unione
contingenti" percentage column together, and section 6.4 states
directly "probabilità e distanza dipendono anche da March/Naval" --
strong enough to model Naval as driving this exact same table, not a
separate one, when the invasion crosses water. No disassembly isolates
a dedicated Naval-only unite-chance routine (hence ALTA, not a literal
quote) -- the same terrain dichotomy is independently confirmed for an
adjacent, disassembled mechanism in the same document (`MOVE.md`
section 21.5: Move's own post-move experience credit picks `Naval` vs
`March` on `Terrain(origin)=Sea or Terrain(destination)=Sea`, exactly
mirroring this project's own `turn/battle_orchestrator.py
_combat_ability_for_terrain()`). ``Attacker.march_level`` itself is
unchanged -- ``fight_multi_attacker_battle()``'s own caller now resolves
whichever ability applies (March or Naval) and passes *that* level in;
this module has no terrain/ability-choice logic of its own, by design
(it only ever consumes one integer "unite level").

**Eagles/Dragons' own carve-out** ("not affected by March ability",
Regolamento AK.txt's own "TABELLA DELLA MARCIA" addendum, word-for-
word the same as RULES.AK [4.12]) -- **Phase 647's own follow-up,
modeled now**: ``is_march_immune_party()`` below returns ``True`` only
when a party's *entire* army composition is Eagle Wing/Dragon Wing
(``models/army_type.py OVERFLIGHT_AIR``, the same set Phase 641's own
AIR_FORCE title-matching already uses for this exact "flying" category)
-- a mixed party (some flying, some not) still benefits from March
normally, since the rulebook's text narrows the carve-out to the units
themselves, not to a leader who merely commands some. The caller
(``turn/battle_orchestrator.py fight_multi_attacker_battle()``) supplies
``march_level=0`` for an immune party, reusing this module's own
already-established "0 is the table's own floor, and the documented
fallback for 'March doesn't apply here'" convention -- the same one
already used for a sea invasion's own March level above, not a new
mechanism invented for this case.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Iterable

from ak_engine.models.army_type import ArmyType, OVERFLIGHT_AIR
from ak_engine.models.map import HexCoord
from ak_engine.turn.movement import hex_distance


def is_march_immune_party(army_types: Iterable[ArmyType]) -> bool:
    """"Aquile e Draghi non sono influenzati dal Talento Marcia" -- True
    only when every army type given is Eagle Wing or Dragon Wing
    (``OVERFLIGHT_AIR``), and at least one type was given at all (an
    empty composition -- a leader invading with no army -- has no
    sourced reading either way, so it doesn't count as immune).
    """

    types = list(army_types)
    return bool(types) and all(army_type in OVERFLIGHT_AIR for army_type in types)

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
    # Phase 307: the attacker's own effective March (or, since Phase
    # 754, Naval when the invasion crosses water -- see module docstring)
    # ability level -- see module docstring for why this attacker's own
    # level (not the other side's) drives their own chance of uniting.
    # Defaults to 0 (the table's own floor) for any caller that doesn't
    # look one up.
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
