"""Army Type Table, transcribed from ``RULES.AK`` [6.3].

Only ``speed`` and ``pay`` (recruit/maintenance cost) are modeled here --
what's needed for the Recruit action (``turn/recruit.py``). ``Str``
(strength), nemesis matchups, and the quality-level system belong to the
combat phase and are deliberately left out until that's built; Elephants'
strength is even listed as "V" (variable) in the rulebook, i.e. not a
plain number, another sign that table belongs with combat, not here.

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
