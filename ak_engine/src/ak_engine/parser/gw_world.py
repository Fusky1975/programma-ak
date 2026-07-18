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
- Line 3: two more integers, undecoded (e.g. `3 0  15 0` for Macondo,
  `4 0  15 0` for the neighboring Orielle) -- doesn't correlate with the
  province's own coordinate ID (a genuinely open question, not attempted
  here; see the module-level "Known gaps" note below).
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
  needed `ptax`/terrain/race/`governor_leader_id`.
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
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from ak_engine.models.map import Terrain
from ak_engine.models.race import Race
from ak_engine.parser.errors import K1ParseError

_PROVINCE_HEADER_RE = re.compile(r"^(\d+) (\d+) 0 (\d+) 0 6$")


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
        owner_idx = i + 2
        if owner_idx >= len(lines):
            raise GWParseError(
                "province record truncated before its owner line",
                line_number=i + 1,
                line=lines[i],
            )

        name = lines[name_idx].strip()
        tax, terrain_ordinal, race_ordinal = (int(g) for g in match.groups())
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
            )
        )
        i = owner_idx + 1

    return records
