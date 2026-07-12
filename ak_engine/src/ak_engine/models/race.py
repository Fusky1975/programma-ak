"""Race enum, transcribed from ``HostAK/TP/CTBOTH.PAS`` (``race`` type, line 573).

``HUMANOID_RACES`` matches the rulebook's explicit definition (``RULES.AK``
[3.4]): "humanoids being men, elves, orcs and dwarves."

**`RACE_NAME`/`RACE_ADJECTIVE` (Phase 87)**, found continuing to mine
`CTBOTH.PAS` the way Phases 79-84/86 found their own real data:
`CTBOTH.PAS`'s own `rname`/`radj` tables (`rstrs` type, 23 entries each
-- 15 real + 8 unused `er3`-`er10` extension slots, the same convention
already used for every other enum's own unused tail). `radj[_race]` is
confirmed to be `PROSE.TXT`'s own documented `"$R: Race name ('Elven',
'Dwarven' etc.)"` marker via `RUMORS.PAS`'s own `WW(radj[_race])` --
both example strings verbatim entries here. `rname[...]` is directly
referenced too (e.g. `Concat('(a ', rname[lrace[ldr]], ' ', ...)'` --
"a Human warrior"), matching `PROSE.TXT`'s separate `"^R (): Race
('Humans', 'Dragons', etc.)"` marker (this project models the singular
noun form `rname` actually stores, not a pluralized string). Both
tables line up exactly, positionally, with `Race`'s own 15 ordinals.
"""

from __future__ import annotations

from enum import Enum


class Race(Enum):
    HUMAN = 0
    ELVEN = 1
    DWARVEN = 2
    ORCISH = 3
    DRAGONS = 4
    EAGLES = 5
    WHALES = 6
    NO_RACE = 7
    MERMISH = 8
    ENTISH = 9
    TROLLISH = 10
    WEREFOLK = 11
    SAURIAN = 12
    VAMPISH = 13
    ROHAN = 14


HUMANOID_RACES = frozenset({Race.HUMAN, Race.ELVEN, Race.DWARVEN, Race.ORCISH})

# CTBOTH.PAS `rname`, verbatim, positional with `Race`'s own ordinals above.
RACE_NAME: dict[Race, str] = {
    Race.HUMAN: "Human",
    Race.ELVEN: "Elf",
    Race.DWARVEN: "Dwarf",
    Race.ORCISH: "Orc",
    Race.DRAGONS: "Dragon",
    Race.EAGLES: "Eagle",
    Race.WHALES: "Whale",
    Race.NO_RACE: "no race",
    Race.MERMISH: "Merman",
    Race.ENTISH: "Ent",
    Race.TROLLISH: "Troll",
    Race.WEREFOLK: "Were",
    Race.SAURIAN: "Dinosaur",
    Race.VAMPISH: "Vampire",
    Race.ROHAN: "Rohan",
}

# CTBOTH.PAS `radj`, verbatim, positional with `Race`'s own ordinals above --
# confirmed to be the real "$R: Race name" prose marker (see module docstring).
RACE_ADJECTIVE: dict[Race, str] = {
    Race.HUMAN: "Human",
    Race.ELVEN: "Elven",
    Race.DWARVEN: "Dwarven",
    Race.ORCISH: "Orcish",
    Race.DRAGONS: "serpentine",
    Race.EAGLES: "feather-brained",
    Race.WHALES: "aquatic",
    Race.NO_RACE: "no race",
    Race.MERMISH: "Mermanic",
    Race.ENTISH: "forest-folk",
    Race.TROLLISH: "Trollish",
    Race.WEREFOLK: "shape-changing",
    Race.SAURIAN: "Saurian",
    Race.VAMPISH: "Vampiric",
    Race.ROHAN: "Rohan",
}
