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

**9 more real `army` ordinals, 20-28 (Phase 383)**: the AKGEN
reverse-engineering material's own `tables.army_types` catalog gives real
`id`/`name`/`code` entries for these ordinals -- Dinosaurs(Di),
Vampires(Va), Marauders(Ma), Shamans(Sh), Crossbow(Cr), Javelins(Ja),
Artil'ry(Ar), Spiders(Sp), D-Turtle(Dt) -- closing the gap
`ARMY_TYPE_BY_ORDINAL`'s own docstring previously flagged as "aren't in
the rulebook's Army Type Table [6.3] and have no ArmyType here either."
That's still true for their rulebook mechanics: none of these 9 appear
in RULES.AK [6.3], so they get no `ArmyTypeStats`/`BASE_STRENGTH`/
`NEMESIS` entry, same as before. The catalog's own `name` field
cross-checks as `ARMY_TYPE_DESIGNATION` (the short `atdesig` form), not
`ARMY_TYPE_NAME` (`atname`) -- confirmed by 5 known ordinals that
disambiguate the two tables (`Lt Cav`/`Hvy Cav`/`Camels`/`Wargs`/
`League` are all `atdesig`, not `atname`'s own longer forms). 7 of the 9
new values read as complete, unabbreviated words already (Dinosaurs,
Vampires, Marauders, Shamans, Crossbow, Javelins, Spiders) and are
reused for `ARMY_TYPE_NAME` too, matching this module's own existing
convention wherever `atname`/`atdesig` coincide. The remaining 2
(`Artil'ry`, `D-Turtle`) are visibly abbreviated forms with no confirmed
full `atname` available, so `ARMY_TYPE_NAME` is deliberately left without
entries for them -- an honest gap, not a guess. `MONSTROUS_ARMY_RACE`
gains exactly 1 new entry, `ArmyType.VAMPIRES: Race.VAMPISH` -- not by
name-symmetry guesswork but by the same catalog's own separately-stated
``world_generation.province_recruit_slots.special_races`` field: "direct
native unit type: Dragons, Eagles, Whales, Mermen, Ents, Trolls,
Werefolk or Vampires" -- an exact, independently-sourced 8-item list
whose first 7 already match this dict's own pre-existing entries 1:1,
strongly confirming the 8th belongs too. That same list conspicuously
excludes Dinosaurs, so `ArmyType.DINOSAURS` is deliberately **not**
added here despite the tempting `Race.SAURIAN`/"Dinosaur" name match --
unconfirmed name-symmetry alone isn't this project's evidentiary bar.
The other 7 new types (Marauders, Shamans, Crossbow, Javelins, Artil'ry,
Spiders, D-Turtle) have no matching `Race` member and stay unmapped too.
This closes a gap ``worldgen/initial_armies.py``'s own docstring
previously flagged by name ("Vampires are named in the source's own
list too, but this project's `ArmyType` enum has no Vampire-native
entry") -- see that module's own updated docstring.

**Phase 691**: a completely separate, independent source --
``AdvancedAbility.DRUIDIC_DINOSAURS``'s own real description
(``models/advanced_ability.py``) -- resolves Dinosaurs directly:
"Race: Saurian," a full Speed/Pay/Terrain/Nemesis stat row (now in
``ARMY_TABLE``/``NEMESIS`` above), and a variable Strength (5-10, see
``turn/strength.py roll_dinosaurs_strength()``, the same "excluded
from ``BASE_STRENGTH``, rolled per-battle" treatment Elephants already
gets). Dinosaurs are **still not** added to ``MONSTROUS_ARMY_RACE`` --
that dict's own real semantic is "native to a race's own home
province, and excluded from every humanoid province" (Dragons/Eagles/
etc.), whereas Dinosaurs are Elven-*trained* ("trainable only by
skilled Elven riders"), a ``turn/recruit.py``-level gate checked
directly against ``Race.ELVEN``, not this dict.
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
    DINOSAURS = "DI"
    VAMPIRES = "VA"
    MARAUDERS = "MA"
    SHAMANS = "SH"
    CROSSBOW = "CR"
    JAVELINS = "JA"
    ARTILLERY = "AR"
    SPIDERS = "SP"
    D_TURTLE = "DT"


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
    # Phase 691: `AdvancedAbility.DRUIDIC_DINOSAURS`'s own real
    # description (`models/advanced_ability.py`) -- "Speed: 3; Pay: 3;
    # Home Terrain: None; Adverse Terrain: Sea."
    ArmyType.DINOSAURS: ArmyTypeStats(3, 3, (), (Terrain.SEA,)),
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
    # Phase 383: confirmed by `special_races`' own explicit 8-item list
    # (see module docstring) -- not name-symmetry guesswork.
    ArmyType.VAMPIRES: Race.VAMPISH,
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
# two mounted "beast" types -- not a literal quote. Phase 691:
# `AdvancedAbility.DRUIDIC_DINOSAURS`'s own real description
# independently confirms this reading directly -- "They qualify as
# 'Beasts', the nemesis to mounted units" -- so Dinosaurs join the set
# too, on real source confirmation rather than name-symmetry guesswork.
_BEASTS = frozenset({ArmyType.ELEPHANTS, ArmyType.CAMEL_CORPS, ArmyType.DINOSAURS})

NEMESIS: dict[ArmyType, frozenset[ArmyType]] = {
    ArmyType.PHALANX: frozenset({ArmyType.LEGION}),
    ArmyType.LEGION: frozenset({ArmyType.HVY_CAVALRY}),
    ArmyType.LT_CAVALRY: frozenset({ArmyType.CHARIOTS}) | _BEASTS,
    ArmyType.HVY_CAVALRY: frozenset({ArmyType.CHARIOTS}) | _BEASTS,
    ArmyType.CHARIOTS: _BEASTS,
    # Phase 691: `AdvancedAbility.DRUIDIC_DINOSAURS`'s own real
    # description -- "Nemesis: Phalanx".
    ArmyType.DINOSAURS: frozenset({ArmyType.PHALANX}),
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


# Phase 521: the three purely sea-going army types -- `OVERFLIGHT_SEA`'s
# own Whales/Mermen plus Fleet (not an overflight unit itself, since it
# has no strength-halving stacking rule, but equally not a "land army").
# Used to classify AdvancedAbility.MARCH_CAVALRY/_INFANTRY's own "land
# armies".
#
# **Phase 523 correction**: Phase 521 originally left Dragon Wing/Eagle
# Wing counted as land-eligible ("no source narrows March's own 'land
# armies' wording to exclude them"). `AKGEN_reverse_engineering_report
# (3).md` SS97/SS99 now supplies that source: the compiled `MovementBonus`
# dispatcher (`AKE.EXE:0x21F6A-0x22080`) has an explicit `Dragonwing,
# Eaglewing: MovementBonus := 0` branch *before* the March/Naval branches
# -- "Dragons ed Eagles ... non ricevono punti movimento da March o
# Naval." Air wings do use their commander's Naval strength multiplier in
# a sea battle (SS97/SS101), just never a March/Naval *movement-point*
# bonus -- a real speed-5 unit with a fixed rate, not a "land army" for
# this specific purpose. `is_land_army()` now excludes `OVERFLIGHT_AIR`
# too, superseding the stale Phase 521 reasoning above.
SEA_ARMY_TYPES = OVERFLIGHT_SEA | frozenset({ArmyType.FLEET})


def is_land_army(army_type: ArmyType) -> bool:
    return army_type not in SEA_ARMY_TYPES and army_type not in OVERFLIGHT_AIR


# Rulebook [6.3] "ARMY STRENGTH NOTES": race bonuses to basic strength.
# "Elves: +1 when fighting as Bowmen, +1 in Forest. Dwarves: +1 as Axemen,
# +1 in Mountains. Orcs: +1 as Phalanx, +1 in Mountains. Humans: +1 as
# Legion (no bonus for any terrain.)" Two independent bonuses per race:
# one tied to the army type being fielded, one tied to terrain (see
# turn/strength.py for how they combine with everything else).
RACE_TYPE_BONUS: dict[tuple[Race, ArmyType], int] = {
    (Race.ELVEN, ArmyType.BOWMEN): 1,
    (Race.DWARVEN, ArmyType.AXEMEN): 1,
    (Race.ORCISH, ArmyType.PHALANX): 1,
    (Race.HUMAN, ArmyType.LEGION): 1,
}

RACE_TERRAIN_BONUS: dict[tuple[Race, Terrain], int] = {
    (Race.ELVEN, Terrain.FOREST): 1,
    (Race.DWARVEN, Terrain.MTNS): 1,
    (Race.ORCISH, Terrain.MTNS): 1,
}

# Ordinal position in CTBOTH.PAS's `army` enum declaration (line 1239):
# "army = (garrison,bowmen,axemen,phalanx,legion,lcav,hcav,chariots,
# elephants,camels,wargriders,dragonwing,eaglewing,whaleleague,fleet,
# noarmy,mermen,ents,trolls,weres,dinosaurs,vampires,marauders,ea3..ea20)".
# This is what move-file Recruit phases use to list requested army types
# (see turn/recruit_decode.py) -- confirmed against real AK3__T*.K1 data,
# where every observed value decodes to a plausible type with no garbage.
# Ordinal 15 ("noarmy") is a sentinel, not a real type, and is omitted;
# ordinals 20+ (dinosaurs, vampires, marauders, ea3-ea20) aren't in the
# rulebook's Army Type Table [6.3] and have no ArmyType here either.
ARMY_TYPE_BY_ORDINAL: dict[int, ArmyType] = {
    0: ArmyType.GARRISON,
    1: ArmyType.BOWMEN,
    2: ArmyType.AXEMEN,
    3: ArmyType.PHALANX,
    4: ArmyType.LEGION,
    5: ArmyType.LT_CAVALRY,
    6: ArmyType.HVY_CAVALRY,
    7: ArmyType.CHARIOTS,
    8: ArmyType.ELEPHANTS,
    9: ArmyType.CAMEL_CORPS,
    10: ArmyType.WARG_RIDERS,
    11: ArmyType.DRAGON_WING,
    12: ArmyType.EAGLE_WING,
    13: ArmyType.WHALES,
    14: ArmyType.FLEET,
    16: ArmyType.MERMEN,
    17: ArmyType.ENTS,
    18: ArmyType.TROLLS,
    19: ArmyType.WEREBEASTS,
    20: ArmyType.DINOSAURS,
    21: ArmyType.VAMPIRES,
    22: ArmyType.MARAUDERS,
    23: ArmyType.SHAMANS,
    24: ArmyType.CROSSBOW,
    25: ArmyType.JAVELINS,
    26: ArmyType.ARTILLERY,
    27: ArmyType.SPIDERS,
    28: ArmyType.D_TURTLE,
}

# CTBOTH.PAS `noleader = 255` -- used in Recruit phases' `obj` field to
# mean "no specific leader" (e.g. assign to the garrison commander).
NO_LEADER_SENTINEL = 255


# CTBOTH.PAS `atname` (~line 1316), verbatim, positional with the `army`
# enum -- confirmed real and used via RUMORS.PAS's own
# `Say(Concat(tms,' ',atname[_atype]),spytype)`, matching PROSE.TXT's own
# documented marker `"|: Army type name (\"Legion\", \"Fleet\" etc.)"`
# (found continuing to mine CTBOTH.PAS the way Phases 79-89 found their
# own real data). Ordinal 15 (`noarmy`, a sentinel) and ordinals 20+
# (`dinosaurs`, `vampires`, `marauders`, `ea3`-`ea20`) are excluded, same
# as `ARMY_TYPE_BY_ORDINAL` above.
ARMY_TYPE_NAME: dict[ArmyType, str] = {
    ArmyType.GARRISON: "Garrison",
    ArmyType.BOWMEN: "Bowmen",
    ArmyType.AXEMEN: "Axemen",
    ArmyType.PHALANX: "Phalanx",
    ArmyType.LEGION: "Legion",
    ArmyType.LT_CAVALRY: "Light Cavalry",
    ArmyType.HVY_CAVALRY: "Heavy Cavalry",
    ArmyType.CHARIOTS: "Chariots",
    ArmyType.ELEPHANTS: "Elephants",
    ArmyType.CAMEL_CORPS: "Camel Corps",
    ArmyType.WARG_RIDERS: "Warg Riders",
    ArmyType.DRAGON_WING: "Dragons",
    ArmyType.EAGLE_WING: "Eagles",
    ArmyType.WHALES: "Whales",
    ArmyType.FLEET: "Fleet",
    ArmyType.MERMEN: "Mermen",
    ArmyType.ENTS: "Ents",
    ArmyType.TROLLS: "Trolls",
    ArmyType.WEREBEASTS: "Were-Beasts",
    # Phase 383: ordinals 20-28, confirmed only where the AKGEN catalog's
    # own designation value is already a complete, unabbreviated word --
    # see module docstring. `ARTILLERY`/`D_TURTLE` are deliberately
    # excluded (no confirmed full `atname` form for their abbreviated
    # `Artil'ry`/`D-Turtle` designations).
    ArmyType.DINOSAURS: "Dinosaurs",
    ArmyType.VAMPIRES: "Vampires",
    ArmyType.MARAUDERS: "Marauders",
    ArmyType.SHAMANS: "Shamans",
    ArmyType.CROSSBOW: "Crossbow",
    ArmyType.JAVELINS: "Javelins",
    ArmyType.SPIDERS: "Spiders",
}

# CTBOTH.PAS `atdesig` (~line 1288), verbatim, positional with the `army`
# enum -- a shorter, 9-char-max form distinct from `atname` above.
# Confirmed real and used via REPORTS.PAS's own army-listing line
# (`IF astate[an] = Zomboid THEN strx:= Concat(s,' Skel ',
# atdesig[Mod_AType(an)]) ELSE strx:= Concat(s,' ',atname[Mod_AType(an)])`
# -- `atdesig` for the compact "Skel <desig>" skeletal-army case,
# `atname` for the normal case) and SAY.PAS's own
# `astring:= atdesig[Mod_LAType(an)]`. Note `WHALES` diverges from
# `ARMY_TYPE_NAME` here (`'League'`, not `'Whales'`) -- a real, confirmed
# quirk of the Pascal source table itself (`whaleleague`'s own designator
# entry), not a transcription error.
ARMY_TYPE_DESIGNATION: dict[ArmyType, str] = {
    ArmyType.GARRISON: "Garrison",
    ArmyType.BOWMEN: "Bowmen",
    ArmyType.AXEMEN: "Axemen",
    ArmyType.PHALANX: "Phalanx",
    ArmyType.LEGION: "Legion",
    ArmyType.LT_CAVALRY: "Lt Cav",
    ArmyType.HVY_CAVALRY: "Hvy Cav",
    ArmyType.CHARIOTS: "Chariots",
    ArmyType.ELEPHANTS: "Elephants",
    ArmyType.CAMEL_CORPS: "Camels",
    ArmyType.WARG_RIDERS: "Wargs",
    ArmyType.DRAGON_WING: "Dragons",
    ArmyType.EAGLE_WING: "Eagles",
    ArmyType.WHALES: "League",
    ArmyType.FLEET: "Fleet",
    ArmyType.MERMEN: "Mermen",
    ArmyType.ENTS: "Ents",
    ArmyType.TROLLS: "Trolls",
    ArmyType.WEREBEASTS: "Weres",
    # Phase 383: ordinals 20-28, the AKGEN catalog's own confirmed
    # `atdesig` field (see module docstring's Phase 383 addendum for the
    # atname/atdesig disambiguation evidence).
    ArmyType.DINOSAURS: "Dinosaurs",
    ArmyType.VAMPIRES: "Vampires",
    ArmyType.MARAUDERS: "Marauders",
    ArmyType.SHAMANS: "Shamans",
    ArmyType.CROSSBOW: "Crossbow",
    ArmyType.JAVELINS: "Javelins",
    ArmyType.ARTILLERY: "Artil'ry",
    ArmyType.SPIDERS: "Spiders",
    ArmyType.D_TURTLE: "D-Turtle",
}
