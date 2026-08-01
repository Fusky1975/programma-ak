"""Parser for the original engine's "world file" format (e.g. ``GW3``,
``GW3__T1``).

**No surviving Pascal source declares this file's format** -- the same
"missing main program" situation as most of this project's other gaps
(`turn/movement.py`'s hex adjacency, `models/office.py`'s `Ofc_Pts`/`Rank`).
Unlike those, this format was recovered empirically (Phase 222), by
cross-referencing known real per-province values -- Tax, Race, Terrain --
quoted verbatim in a real King's own generated turn-report letter
(``SE3__T1.K2``'s "PROVINCES" section, e.g. Macondo: Tax 4, Orc, Jungle)
against the raw integers in the corresponding real world-file snapshot
(``GW3__T1``, the same game). This is the exact "real sourced evidence
substituting for a lost driver" precedent `report/turn_report.py
compose_letter_report()`'s own docstring already established for the
letter-report section order.

**Confirmed record shape**, one per province, four consecutive lines
(quoted verbatim from ``GW3__T1``, Macondo's own real record):

```
Macondo
4 2 0 3 0 6
 3 0  15 0
255
```

- Line 1: the province's own name (`ProvinceState.name`'s own `pname`
  source -- see that field's docstring in `models/game_state.py`).
- Line 2: six space-separated integers, `<tax> <terrain> 0 <race> 0 6`.
  `tax` is the real `ptax[px,py]` this project has needed since Phase 220
  (`report/turn_report.py describe_provinces_report()`'s own documented
  gap). `terrain` and `race` are the *exact* ordinal values this
  project's own `models/map.py Terrain` and `models/race.py Race` enums
  already use (confirmed across 20+ real records: Macondo `terrain=2`/
  Jungle, Transylvania `terrain=4`/Mountain, Kaluga `race=1`/Elf,
  Kerry `race=2`/Dwarf -- no new ordinal-mapping table is needed here,
  unlike e.g. `models/alignment.py`'s own `ALIGNMENT_ORDINAL`). The two
  literal `0`s and the trailing literal `6` are a fixed structural
  marker at this position in every one of the 162 confirmed records, not
  a data field -- do not confuse the trailing `6` with `Terrain.
  NO_TERRAIN`'s own ordinal value (unrelated, a different slot).
- Line 3: **the real `Mod_PAT(px,py,0)`/`Mod_PAT(px,py,1)` Recruiting
  Types pair, decoded, Phase 278** -- four space-separated integers,
  `<type1_ord> 0  <type2_ord> 0` (e.g. `3 0  15 0` for Macondo, `4 0  7 0`
  for the neighboring Orielle). The first and third integers are each a
  real `ArmyType` ordinal (or the `15` "no second type" sentinel, see
  `MOD_PAT_ORDINAL_TO_ARMY_TYPE` below); the second and fourth are always
  literal `0` in every one of 701 real cross-checked records (Phase 278's
  own recovery evidence), an unused/reserved slot, not a data field.
- Line 4: **the governing leader's own leader id**, or the sentinel
  `255` for an unowned province -- NOT directly a kingdom id, a real
  correction made after cross-checking against `SE3__T1.K2`'s own ASCII
  map legend (that letter's "Key" section prints each province as
  `"<Name>(<coord>)"` over `"<RulerName>(<RulerID>)"`): Transylvania's
  own real ruler is printed as `"Philo(70)"` -- Philo is a Hero, not a
  King, confirmed by his own leader id (70) being far outside the
  King-numbering range this project's own fixtures already use (Kings
  own low single-digit ids matching their kingdom id, e.g. `LeaderState(
  1, 1, "Aldric", ..., is_king=True)`). `GW3__T1`'s own Transylvania
  record trails `70`, matching Philo's id exactly -- not a kingdom id at
  all. For a province the King governs directly, this id happens to
  equal the kingdom id (the same "King's own leader_id == kingdom_id"
  convention already established project-wide), e.g. Mongu/Macondo are
  both governed by "Bradipo I(2)" in the letter and both trail `2` in
  `GW3__T1` once owned (Macondo trails `255` in this specific pre-turn-1
  snapshot -- see the note on snapshot timing below). Resolving a
  `governor_leader_id` to its true owning kingdom needs `GameState.
  leaders`/`LKing()`-equivalent lookup, not attempted by this parser.

**Recruiting Types (`Mod_PAT`), Phase 278.** `report/turn_report.py
describe_provinces_report()`'s own "Recruiting Types" columns (Type 1 /
Type 2) were confirmed absent as of Phase 220/275 for the same reason
`ptax` originally was: no surviving `.PAS` file declares `Mod_PAT`. That
audit only ever asked whether a *formula* survives (it doesn't) -- it
never re-checked whether the *data* was recoverable the same way `ptax`
itself was (Phase 222, this same file). It was: cross-referencing every
real "PROVINCES" table row across all 12 available `SE3__T*.K*` turns
(701 rows with a matching `GW3__T<n>` record, by province name) against
that turn's own `GW3__T<n>` file's line-3 tokens gives a **100% exact,
zero-conflict decode** for all 19 distinct ordinals actually observed:

```
 0  Garrison   (inferred by elimination -- see note below)
 1  Bowmen          8  Elephants        15  None (no 2nd type)
 2  Axemen          9  Camels           16  Mermen
 3  Phalanx        10  Wargs            17  Ents
 4  Legion         11  Dragons          18  Trolls
 5  Lt Cav         12  Eagles           19  Weres
 6  Hvy Cav        13  League (Whales)
 7  Chariots       14  Fleet
```

Ordinals 0-14 line up exactly, positionally, with this project's own
`models/army_type.py ArmyType` enum declaration order (`GARRISON`
through `FLEET`) -- but 16-19 (`MERMEN`/`ENTS`/`TROLLS`/`WEREBEASTS`) are
each **one higher** than this project's own enum ordinals for those same
four members (15/16/17/18). The real Pascal `ArmyType`-equivalent enum
therefore has one more member than this project's own model does,
sitting at ordinal 15 between `FLEET` and `MERMEN` -- confirmed
functionally (it always renders as "None," the real table's own way of
saying "no second recruit type here," e.g. every `Terrain.SEA`/
`Race.NO_RACE` record) even though its real Pascal *name* is unknown.
`MOD_PAT_ORDINAL_TO_ARMY_TYPE` below encodes this shift directly, not as
an "off by one" workaround, so callers never see raw ordinals.

**`0`/`Garrison` was never directly observed** in any of the 701
cross-checked rows -- inferred by elimination (it's the one ordinal in
the confirmed 0-14 run with no conflicting alternative) and because
Garrison, uniquely, is recruitable in *any* humanoid province regardless
of race (rulebook [3.4]/`turn/recruit.py is_army_type_compatible_with_
race()`), so a province-specific "which types recruit here" table
plausibly never needs to name it at all -- a plausible explanation, not
independently confirmed.

**Per-province, not a race/terrain formula.** The same `(race, terrain)`
pair maps to many different `(type1, type2)` combinations across the 701
rows (e.g. `Human`/`Forest` alone spans five different Type 2 values) --
confirming this, like `ptax`, is baked into the map at world-generation
time, not runtime-derivable, and must be read per-province the same way.

**A bonus discovery, not consumed by this parser**: the same map legend
prints each province's own real coordinate, `"<Name>(<XXYY>)"` -- e.g.
`"Macondo(0205)"` (x=02, y=05), `"Mongu(0305)"`, `"Transylvania(0206)"`.
Cross-referencing the letter's own row layout (Bam Yanga/Macondo/Mongu/
Moongard all share y=05, x=1..4 left to right) against `GW3__T1`'s own
on-disk record order (those exact 4 provinces appear consecutive,
followed immediately by the next row's Abu Matariq/Transylvania/Big Sky,
y=06) strongly suggests the world file's own record order is row-major
over (x, y) -- but this is only a promising lead, not independently
confirmed or implemented here (see "Known gaps" below).

**Known gaps, deliberately not attempted here**:
- **No coordinate field exists in a province's own 4-line record**, and
  while the row-major ordering lead above is promising, it isn't
  confirmed. This means `parse_gw_world()` returns records in the
  file's own on-disk order, not keyed by `HexCoord` -- bridging a
  `GWProvinceRecord` into `GameState.provinces` (a `dict[HexCoord,
  ProvinceState]`) is deferred to a future phase.
- Line 3's own two integers are unresolved (population? garrison
  strength? a resource id?) -- out of scope for this phase, which only
  needed `ptax`/terrain/race/`governor_leader_id`. **Resolved, Phase
  278** -- see the module's own "Recruiting Types" section below;
  this note is kept for its original historical context.
- `governor_leader_id` isn't resolved to an owning kingdom id here (see
  above) -- that needs a `GameState`-level leader/kingdom lookup this
  pure file parser deliberately doesn't perform.
- `GW3__T1` is a pre-turn-1 snapshot: some provinces the corresponding
  `SE3__T1.K*` letters show as already conquered/settled (e.g. Macondo,
  ruled by "Bradipo I(2)" per the letter) still read `255` (unowned)
  here -- plausible turn-1-processing timing, not independently
  confirmed against a still-earlier snapshot (none exists to check).
- This module only parses the province-record block. A `GW3` file also
  has substantial content before and after that block (kingdom headers,
  a differently-shaped record format after line ~2066 in the confirmed
  `GW3__T1` sample) that isn't touched here.

**Phase 316 addendum -- what's actually in the post-province-block
content, an initial research pass (not implemented, no new parser
code).** The content after the province-record block (`GW3__T1` lines
~2067-2415) splits into three sub-parts, separated by a 2-line marker
(`"0 255 0"` / `"35 99 0"`) and closed by a fixed-length `"255 0 0"` x 52
padding/terminator row:

- **128 rows, 9 space-separated integers each** (e.g. `"11 7 67 256 4
  51 1 0 2"`). **Tested and falsified**: this looked like a plausible
  Feature/Monster instance roster (`models/feature.py`'s own `fx`/`fy`/
  `ftype`/`fmonst`/`fn` shape) -- fields 1-2 are valid 0-indexed
  `HexCoord`s on the confirmed 18x9 board, and 230 is the right order of
  magnitude for `featrange`. Directly falsified against real ground
  truth: `SE3__T1.K2`'s own "ADVENTURE" section names 3 real feature
  instances with real `F#`s (Macondo's Monastery `F#114`/Genie;
  Mongu's Cave `F#2`/Swordsman and Crypt `F#17`/Gargoyle) -- **none of
  114, and no isolated 17, ever appears anywhere in `GW3__T1`**. Field 4
  (which looked like a sequential instance id, `256, 257, 258...`) is
  actually trivial: exactly `255 + row_number`, a file-position counter,
  not game data. Field 3's own distribution (64 distinct low values,
  0-25 and 29-66 skipping 26-28, each appearing exactly once, mixed with
  64 filler rows at value 67 or 68) doesn't correlate cleanly with
  coordinate or row order either. This 9-field block's real meaning is
  still unknown; the Feature/Monster-roster hypothesis is ruled out, not
  just unconfirmed.
- **218 rows, 10 space-separated integers each** (e.g. `"70 1 5 2 2 2 1
  2 0 0"`). **Confirmed, not just a lead**: field 1 is a governing
  Hero's own `leader_id` (`255` = empty slot, 104 of the 218 rows),
  fields 2-3 are that Hero's current `HexCoord` -- verified two ways:
  (a) the complete set of distinct real field-1 values (`10, 11, 12,
  14...97`) matches this same file's own confirmed
  `GWProvinceRecord.governor_leader_id` set *exactly*, except every
  single-digit id (0-9, this project's own "King's `leader_id` ==
  `kingdom_id`" range for a 9-kingdom game) is systematically absent --
  i.e. this table excludes Kings, Heroes only; (b) Philo (`leader_id`
  70, confirmed governing Transylvania at `HexCoord(1, 5)` since Phase
  222's own "Philo(70)" cross-check) appears at exactly `"70 1 5 ..."`,
  twice (duplicate rows, same trailing fields). Fields 4-10 (7 more
  integers) are still unresolved -- items carried, personal stats, or
  commanded units are all plausible given the duplicate-row pattern, but
  none is confirmed. Not implemented as a parser here; a future phase
  could extend this module with a `GWHeroRecord`-equivalent once the
  trailing fields are decoded.
- The 2-line marker between the two blocks (`"0 255 0"` / `"35 99 0"`)
  and the fixed 52-triple `"255 0 0"` terminator row are both unresolved
  structural boundaries, not data.

None of this is implemented in `parse_gw_world()` -- this addendum
records a research pass only, so a future phase doesn't re-walk the
already-falsified Feature/Monster hypothesis from scratch.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from ak_engine.models.army_type import ArmyType
from ak_engine.models.map import Terrain
from ak_engine.models.race import Race
from ak_engine.parser.errors import K1ParseError

_PROVINCE_HEADER_RE = re.compile(r"^(\d+) (\d+) 0 (\d+) 0 6$")

# Line 3's own two real ordinals, decoded (Phase 278) -- see the module
# docstring's "Recruiting Types (Mod_PAT)" section for the full
# derivation. `None` at ordinal 15 is the real "no second recruit type"
# sentinel (renders as "None" in the real table), not a missing mapping.
MOD_PAT_ORDINAL_TO_ARMY_TYPE: dict[int, ArmyType | None] = {
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
    15: None,
    16: ArmyType.MERMEN,
    17: ArmyType.ENTS,
    18: ArmyType.TROLLS,
    19: ArmyType.WEREBEASTS,
}


class GWParseError(K1ParseError):
    """Raised when a world file doesn't match the expected shape."""


@dataclass(slots=True)
class GWProvinceRecord:
    name: str
    tax: int
    terrain: Terrain
    race: Race
    # The governing leader's own leader id (`None` for the `255`
    # unowned sentinel) -- NOT a kingdom id; see the module docstring's
    # "Philo(70)" cross-check. Resolving this to an owning kingdom needs
    # a `GameState`-level leader/kingdom lookup this parser doesn't do.
    governor_leader_id: int | None
    # Mod_PAT(px,py,0)/Mod_PAT(px,py,1), decoded via
    # MOD_PAT_ORDINAL_TO_ARMY_TYPE (Phase 278). recruit_type_2 is `None`
    # for the real "no second recruit type" sentinel -- see the module
    # docstring; every real province observed so far has a genuine
    # recruit_type_1.
    recruit_type_1: ArmyType | None
    recruit_type_2: ArmyType | None


def parse_gw_world(path: Path) -> list[GWProvinceRecord]:
    """Parses every province record out of a world file.

    Scans the whole file for the province-header line's own fixed shape
    (`"<tax> <terrain> 0 <race> 0 6"`) rather than assuming a fixed byte
    offset, since that shape is confirmed unique to the province block
    (a file-wide regex scan against the real `GW3__T1` sample returns
    exactly 162 matches -- the real, user-confirmed province count per
    world -- with no false positives from the file's other, differently-
    shaped record blocks).
    """

    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    records: list[GWProvinceRecord] = []
    i = 1
    while i < len(lines):
        match = _PROVINCE_HEADER_RE.match(lines[i].strip())
        if match is None:
            i += 1
            continue

        name_idx = i - 1
        line3_idx = i + 1
        owner_idx = i + 2
        if owner_idx >= len(lines):
            raise GWParseError(
                "province record truncated before its owner line",
                line_number=i + 1,
                line=lines[i],
            )

        name = lines[name_idx].strip()
        tax, terrain_ordinal, race_ordinal = (int(g) for g in match.groups())
        recruit_type_1, recruit_type_2 = _parse_recruit_types(lines[line3_idx], line3_idx)
        governor_raw = lines[owner_idx].strip()
        if not governor_raw.lstrip("-").isdigit():
            raise GWParseError(
                "expected an integer governor id after the province record",
                line_number=owner_idx + 1,
                line=lines[owner_idx],
            )
        governor = int(governor_raw)

        records.append(
            GWProvinceRecord(
                name=name,
                tax=tax,
                terrain=Terrain(terrain_ordinal),
                race=Race(race_ordinal),
                governor_leader_id=None if governor == 255 else governor,
                recruit_type_1=recruit_type_1,
                recruit_type_2=recruit_type_2,
            )
        )
        i = owner_idx + 1

    return records


def _parse_recruit_types(line3: str, line_number: int) -> tuple[ArmyType | None, ArmyType | None]:
    """Decodes a province record's own line 3 (`"<t1> 0  <t2> 0"`) into
    `Mod_PAT(px,py,0)`/`Mod_PAT(px,py,1)` -- see the module docstring's
    "Recruiting Types (Mod_PAT)" section for the full derivation.
    """

    tokens = line3.split()
    if len(tokens) != 4 or not all(t.lstrip("-").isdigit() for t in tokens):
        raise GWParseError(
            "expected four integers on the recruiting-types line "
            '("<type1_ord> 0  <type2_ord> 0")',
            line_number=line_number + 1,
            line=line3,
        )

    type1_ord, type2_ord = int(tokens[0]), int(tokens[2])
    for ordv in (type1_ord, type2_ord):
        if ordv not in MOD_PAT_ORDINAL_TO_ARMY_TYPE:
            raise GWParseError(
                f"unrecognized Mod_PAT ordinal {ordv} (expected 0-19)",
                line_number=line_number + 1,
                line=line3,
            )

    return MOD_PAT_ORDINAL_TO_ARMY_TYPE[type1_ord], MOD_PAT_ORDINAL_TO_ARMY_TYPE[type2_ord]
