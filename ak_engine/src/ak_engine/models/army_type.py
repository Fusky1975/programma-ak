"""Army Type Table, transcribed from ``RULES.AK`` [6.3].

``speed`` and ``pay`` (recruit/maintenance cost) support the Recruit
action (``turn/recruit.py``); ``BASE_STRENGTH`` and ``NEMESIS`` support
battle math (``turn/combat.py``). The quality-level multiplier system is
NOT army-type-specific and lives in ``turn/combat.py`` instead.

Garrison's "Str" is asymmetric in the rulebook (3 defending, 1 attacking)
and is handled as two named constants (``GARRISON_DEFENSE_STRENGTH``,
``GARRISON_ATTACK_STRENGTH``) rather than forced into ``BASE_STRENGTH``.
Elephants' "Str" is listed as "V" (variable) in the rulebook -- not a
plain number -- so it's excluded from ``BASE_STRENGTH`` entirely rather
than guessed; code that needs an Elephants base strength must handle that
gap explicitly.

``MONSTROUS_ARMY_RACE`` encodes which army types are tied to one specific
non-humanoid race (rulebook: "you can't recruit Dragons in a Human
province or vice versa"). Every other type here is a mundane/humanoid
military unit, recruitable in any humanoid province ("You CAN recruit any
humanoid army type in any humanoid province") -- this module treats that
as symmetric (non-humanoid provinces can't recruit humanoid-only types
either), which is an interpretation of the rulebook text, not a literal
quote.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ak_engine.models.map import Terrain
from ak_engine.models.race import Race


class ArmyType(Enum):
    GARRISON = "GA"
    BOWMEN = "BO"
    AXEMEN = "AX"
    PHALANX = "PH"
    LEGION = "LE"
    LT_CAVALRY = "LC"
    HVY_CAVALRY = "HC"
    CHARIOTS = "CH"
    ELEPHANTS = "EL"
    CAMEL_CORPS = "CC"
    WARG_RIDERS = "WR"
    DRAGON_WING = "DR"
    EAGLE_WING = "EA"
    WHALES = "WH"
    FLEET = "FL"
    MERMEN = "ME"
    ENTS = "EN"
    TROLLS = "TR"
    WEREBEASTS = "WE"


@dataclass(frozen=True, slots=True)
class ArmyTypeStats:
    speed: int
    pay: int
    home_terrain: tuple[Terrain, ...]
    adverse_terrain: tuple[Terrain, ...]


ARMY_TABLE: dict[ArmyType, ArmyTypeStats] = {
    ArmyType.GARRISON: ArmyTypeStats(1, 1, (), ()),
    ArmyType.BOWMEN: ArmyTypeStats(2, 2, (Terrain.FOREST, Terrain.JUNGLE), ()),
    ArmyType.AXEMEN: ArmyTypeStats(2, 2, (Terrain.FOREST, Terrain.MTNS), ()),
    ArmyType.PHALANX: ArmyTypeStats(2, 2, (Terrain.PLAINS,), (Terrain.FOREST, Terrain.JUNGLE, Terrain.SEA)),
    ArmyType.LEGION: ArmyTypeStats(2, 2, (), (Terrain.SEA,)),
    ArmyType.LT_CAVALRY: ArmyTypeStats(4, 2, (Terrain.PLAINS, Terrain.DESERT), ()),
    ArmyType.HVY_CAVALRY: ArmyTypeStats(3, 3, (Terrain.PLAINS,), (Terrain.FOREST, Terrain.JUNGLE, Terrain.MTNS, Terrain.SEA)),
    ArmyType.CHARIOTS: ArmyTypeStats(3, 3, (Terrain.PLAINS, Terrain.DESERT), (Terrain.FOREST, Terrain.JUNGLE, Terrain.MTNS, Terrain.SEA)),
    ArmyType.ELEPHANTS: ArmyTypeStats(2, 3, (Terrain.JUNGLE,), (Terrain.FOREST, Terrain.MTNS, Terrain.SEA)),
    ArmyType.CAMEL_CORPS: ArmyTypeStats(3, 3, (Terrain.DESERT,), (Terrain.FOREST, Terrain.JUNGLE, Terrain.SEA)),
    ArmyType.WARG_RIDERS: ArmyTypeStats(3, 3, (Terrain.FOREST,), (Terrain.SEA,)),
    ArmyType.DRAGON_WING: ArmyTypeStats(5, 4, (), ()),
    ArmyType.EAGLE_WING: ArmyTypeStats(5, 3, (Terrain.MTNS,), (Terrain.FOREST, Terrain.JUNGLE)),
    ArmyType.WHALES: ArmyTypeStats(4, 3, (Terrain.SEA,), (Terrain.PLAINS, Terrain.DESERT, Terrain.JUNGLE, Terrain.FOREST, Terrain.MTNS)),
    ArmyType.FLEET: ArmyTypeStats(2, 3, (Terrain.SEA,), (Terrain.PLAINS, Terrain.DESERT, Terrain.JUNGLE, Terrain.FOREST, Terrain.MTNS)),
    ArmyType.MERMEN: ArmyTypeStats(3, 2, (Terrain.SEA, Terrain.JUNGLE), (Terrain.DESERT, Terrain.MTNS)),
    ArmyType.ENTS: ArmyTypeStats(1, 3, (Terrain.FOREST, Terrain.JUNGLE), (Terrain.SEA, Terrain.DESERT)),
    ArmyType.TROLLS: ArmyTypeStats(2, 3, (Terrain.MTNS,), (Terrain.SEA,)),
    ArmyType.WEREBEASTS: ArmyTypeStats(3, 3, (Terrain.FOREST, Terrain.MTNS), (Terrain.SEA,)),
}

# Army types tied to one specific non-humanoid race (rulebook [3.4] example:
# "you can't recruit Dragons in a Human province or vice versa"). Any
# ArmyType not listed here is a mundane/humanoid military unit.
MONSTROUS_ARMY_RACE: dict[ArmyType, Race] = {
    ArmyType.DRAGON_WING: Race.DRAGONS,
    ArmyType.EAGLE_WING: Race.EAGLES,
    ArmyType.WHALES: Race.WHALES,
    ArmyType.MERMEN: Race.MERMISH,
    ArmyType.ENTS: Race.ENTISH,
    ArmyType.TROLLS: Race.TROLLISH,
    ArmyType.WEREBEASTS: Race.WEREFOLK,
}

# "Str" column of the Army Type Table. Garrison and Elephants are excluded;
# see the module docstring.
BASE_STRENGTH: dict[ArmyType, int] = {
    ArmyType.BOWMEN: 2,
    ArmyType.AXEMEN: 2,
    ArmyType.PHALANX: 3,
    ArmyType.LEGION: 3,
    ArmyType.LT_CAVALRY: 2,
    ArmyType.HVY_CAVALRY: 4,
    ArmyType.CHARIOTS: 3,
    ArmyType.CAMEL_CORPS: 2,
    ArmyType.WARG_RIDERS: 3,
    ArmyType.DRAGON_WING: 6,
    ArmyType.EAGLE_WING: 4,
    ArmyType.WHALES: 5,
    ArmyType.FLEET: 3,
    ArmyType.MERMEN: 2,
    ArmyType.ENTS: 6,
    ArmyType.TROLLS: 5,
    ArmyType.WEREBEASTS: 3,
}

GARRISON_DEFENSE_STRENGTH = 3
GARRISON_ATTACK_STRENGTH = 1

# Rulebook [6.3] "Nemesis" column: each key is 2/3 strength when fighting
# any type in its value set. "Beasts" (the rulebook doesn't define it
# elsewhere) is interpreted here as {Elephants, Camel Corps}, the table's
# two mounted "beast" types -- not a literal quote.
_BEASTS = frozenset({ArmyType.ELEPHANTS, ArmyType.CAMEL_CORPS})

NEMESIS: dict[ArmyType, frozenset[ArmyType]] = {
    ArmyType.PHALANX: frozenset({ArmyType.LEGION}),
    ArmyType.LEGION: frozenset({ArmyType.HVY_CAVALRY}),
    ArmyType.LT_CAVALRY: frozenset({ArmyType.CHARIOTS}) | _BEASTS,
    ArmyType.HVY_CAVALRY: frozenset({ArmyType.CHARIOTS}) | _BEASTS,
    ArmyType.CHARIOTS: _BEASTS,
    ArmyType.WARG_RIDERS: frozenset({ArmyType.EAGLE_WING}),
    ArmyType.DRAGON_WING: frozenset({ArmyType.BOWMEN}),
    ArmyType.EAGLE_WING: frozenset({ArmyType.BOWMEN}),
    ArmyType.WHALES: frozenset({ArmyType.MERMEN}),
    ArmyType.MERMEN: frozenset({ArmyType.BOWMEN}),
    ArmyType.ENTS: frozenset({ArmyType.AXEMEN, ArmyType.DRAGON_WING}),
    ArmyType.TROLLS: frozenset({ArmyType.AXEMEN}),
}


def is_nemesis_of(attacker_type: ArmyType, opponent_type: ArmyType) -> bool:
    """True if ``opponent_type`` is ``attacker_type``'s nemesis (2/3 strength)."""

    return opponent_type in NEMESIS.get(attacker_type, frozenset())


# Rulebook [7.2]: "Non-humanoid units (Eagles, Dragons, Whales and Mermen)
# can attack from above or below and contribute 100% of their strength to
# the battle" regardless of battle-line depth. This is a narrower set than
# `MONSTROUS_ARMY_RACE` -- Ents, Trolls and Werebeasts are non-humanoid
# *races* but fight as ordinary melee units in the line, not overflight
# attackers, so they're excluded here.
#
# "Non-humanoid air units, non-humanoid sea units and humanoid units are
# considered three separate groups when halving strength" for the
# multiple-units-attacking-the-same-target stacking penalty -- hence two
# groups, not one.
OVERFLIGHT_AIR = frozenset({ArmyType.DRAGON_WING, ArmyType.EAGLE_WING})
OVERFLIGHT_SEA = frozenset({ArmyType.WHALES, ArmyType.MERMEN})
OVERFLIGHT_TYPES = OVERFLIGHT_AIR | OVERFLIGHT_SEA


def is_overflight_unit(army_type: ArmyType) -> bool:
    return army_type in OVERFLIGHT_TYPES


def overflight_group(army_type: ArmyType) -> str | None:
    """'air', 'sea', or None if ``army_type`` isn't an overflight unit."""

    if army_type in OVERFLIGHT_AIR:
        return "air"
    if army_type in OVERFLIGHT_SEA:
        return "sea"
    return None
