"""Phase 988: the real ``XK`` per-Kingdom "known world" file -- the
binary export a player's own separate Windows support program reads to
show that Kingdom's own map and prepare their next turn's moves.

**Genuinely new reverse engineering, started at the user's own explicit
request** (the GM-interface plan's own "Fuori scopo per questa prima
versione" section had deliberately deferred this: "un progetto di
reverse engineering a se, paragonabile per portata a quello gia fatto
per il formato GW"). Unlike the GW world-file reverse engineering (which
leaned heavily on a prior `AKGEN.EXE` static-disassembly document trail
already describing most fields by name), **no disassembly material for
XK exists yet in this project** -- every finding below comes from
directly cross-referencing 4 real sample files the user provided
(``XK3__T1.K0``, ``XK3__T1.K1``, ``XK3__T2.K0``, ``XK3__T2.K1`` -- two
successive turns, two different Kingdoms, same real campaign "3" this
project's own ``tests/fixtures/world/G3/GW3__T1``-``T12`` and
``SE3__T*.K1`` letters already come from) against this project's own
already-confirmed ``parser/gw_world.py`` ground truth for that same
campaign. This is **known-plaintext cryptanalysis**, not disassembly:
every confirmed field below was found by searching for a real, already-
known value (a Kingdom id, a turn number, a real province or hero name)
inside the raw bytes, not by reading Pascal source.

**Confirmed exactly, cross-checked against all 4 real samples:**

- Every XK file opens with a **fixed-size, 0x30B (779)-byte header
  block** -- the per-leader name table below always starts at exactly
  that offset in every sample, independent of total file size (which
  otherwise varies, 4534-4951 bytes across the 4 samples).
- Byte 0 reads **30** in all 4 files -- exactly this project's own
  already-confirmed ``GWHeader.header_revision`` value (every real
  ``GW3__T1``-``T12`` file in this project's corpus also reads
  ``header_revision == 30``). Real role beyond "the same save-format
  revision marker GW uses" not yet independently confirmed, but the
  exact value match across an unrelated file format is too specific to
  be coincidence. Bytes 1-2 read zero in every sample (part of a wider
  field, or simply unused) -- left unparsed since no real value has
  ever required more than byte 0's own single-byte range.
- Byte 3 (flanked by zero bytes on both sides) is this **file's own
  Kingdom id** (0-indexed): reads ``0`` in both ``*.K0`` samples and
  ``1`` in both ``*.K1`` samples, stable across both turns.
- Byte 0x11 (17), flanked by zero bytes, is the **game turn number**:
  reads ``1`` in both ``T1`` samples and ``2`` in both ``T2`` samples,
  stable across both Kingdoms -- matches ``GWHeader.game_turn`` for the
  same real campaign exactly.
- Byte 0x49 (73), flanked by zero bytes, is the **Kingdom count**:
  reads ``10`` in all 4 samples -- matches ``GWHeader.king_count`` for
  this real campaign (a 10-Kingdom game) exactly, and is turn-
  independent as expected.
- The remaining header bytes (roughly 0x04-0x48, 0x4a-0x30a) are
  **still genuinely undeciphered** -- some positions differ between the
  two Kingdoms' own files at the same turn (e.g. a short run around
  0x158-0x17f), suggesting small embedded per-Kingdom summary fields,
  but no real value from the GW/letter corpus has yet been matched
  against any of them. Left unparsed rather than guessed.

**The per-leader name table, immediately following the header
(0x30B):** exactly 100 consecutive Pascal ShortStrings (a 1-byte length
prefix followed by that many raw chars, this project's own already-
established idiom -- see ``parser/gw_world.py``'s own string handling),
one entry per leader id ``0``-``99`` -- the same id-space this project's
own ``LeaderState.leader_id``/``STANDARD_HERO_ROSTER`` already use.
Confirmed character-for-character against the real, already-parsed
``GW3__T1`` leader roster (``parser/gw_world.py parse_gw_leaders()``):
every single one of the 10 Kings' real names (``Babba Sissoko``, ``Uga-
Buga Makumb``, ``Bradipo I``, ``Kwoth``, ``Hokuto``, ``Prometeo``,
``Kahn``, ``Giovanna d'Arco``, ``Circe``, ``Agesilao``) appears
verbatim at their own real id in every one of the 4 samples -- **with
one genuine exception, not a parser quirk**: King id 2 reads
``"Bradibo I"`` in both real Turn 1 samples and ``"Bradipo I"`` in both
real Turn 2 samples, matching ``GW3__T1``'s own later-confirmed
spelling only from Turn 2 onward. A real, reproducible spelling
correction inside this one campaign's own data between turns 1 and 2,
kept exactly as found rather than normalized away. Every other
(non-King) leader id shows one of two things:

- its own **real, current name** (confirmed, e.g. id 18 ``Guerin`` and
  id 72 ``Teleko``, Kingdom 1's own two starting Companions, both
  placed at Kingdom 1's own Home coordinate in the real ``GW3__T1``
  data), when this specific Kingdom's file already "knows" that
  leader; or
- the fixed placeholder ``"Ldr-<id>"`` (e.g. id 10 reads exactly
  ``"Ldr-10"``) when it doesn't -- confirmed to be a literal, exact
  format (``f"Ldr-{id}"``) for every single one of the ~80-84
  placeholder entries across all 4 samples, zero exceptions.

The table always ends with a zero-length ShortString "fencepost" (a
lone ``0x00`` length byte) immediately followed by ``0xFF 0xFF`` -- a
real, confirmed end-of-table sentinel, present in all 4 samples.

**Genuinely open, discovered but not yet understood -- flagged here
rather than guessed at:**

- **The real "known leader" set at game start is wider than this
  project's own engine currently models.** For Kingdom 1 at Turn 1,
  besides the 10 Kings and its own 2 Companions, 5 further independent
  Heroes already show their real names (``Lallipugh``, ``Amalric``,
  ``Melantheus``, ``Tao-Li``, ``Riose``) -- 3 of those are the Heroes
  governing Kingdom 1's Home's own direct map-neighbor provinces (this
  project's own already-confirmed ``turn/move_execution.py
  reveal_adjacent_provinces()``, Phase 623/982), but the other 2
  (``Tao-Li`` at a 2nd-ring neighbor, ``Riose`` further out again) are
  not explained by that function at all. This project's own starting-
  visibility reveal may be narrower than the real game's -- a concrete
  follow-up worth investigating in ``worldgen/generate_new_game.py``'s
  own Phase 982 reveal call, separate from this module.
- **Not every direct map-neighbor Hero is known, even when closer ones
  are.** Kingdom 0's own Home (``Piratum``, (11,7)) has 6 real direct
  neighbors; the per-known-province table (see below) shows 4 of them
  by name (Florence, Redwood, Jutland's own neighbor Silvania/
  Tanglewood -- see below) but is missing exactly the 2 that are
  ``Race.DRAGONS`` (``Mare Tarkium``, ``the Sunshine Sea``) -- while a
  same-distance ``Race.TROLLISH`` neighbor (``Redwood``) *is* shown.
  Too small a sample (one Home, one race) to generalize into a rule;
  recorded here as a real, reproducible observation for a future,
  larger cross-check.
**The per-known-province record table, Phase 989 -- fully decoded one
record at a time, cross-checked against all 7+7+13+12 known-province
records across all 4 samples (26 ordinary + 2 Home records, zero
mismatches):**

Each record is, in order: ``[coord_x:1][coord_y:1][name_len:1][name:
name_len][terrain:1][race:1]`` -- ``terrain``/``race`` are this
project's own ``Terrain``/``Race`` enum ordinals directly (e.g. ``4`` is
always ``Terrain.MTNS``, confirmed identical to their already-existing
``.value``\\ s, no translation table needed) -- followed by one of
**two confirmed trailing shapes**, both opening with the same 2
still-undeciphered zero bytes in every single sample (``unknown_a``/
``unknown_b`` below; never observed nonzero, role unconfirmed):

- **Ordinary (not this Kingdom's own Home), 3 more bytes:** a constant
  ``0x01`` then a constant ``0xFF``, then the province's own real
  ``governor_leader_id`` -- or ``0xFF`` (255) again for the real
  "ungoverned" sentinel this project's own ``parser/gw_world.py`` already
  uses. Confirmed exactly against all 26 real ordinary records across
  all 4 samples (e.g. Kingdom 1's own neighbor ``the Mermaid Sea``
  trails real governor id ``11``; ``Falkenheim``, genuinely ungoverned,
  trails ``0xFF``) -- the constant ``0x01``/``0xFF`` pair before it never
  varies, consistent with "recruit types not shown at this exploration
  level" (never observed to carry real recruit data).
- **Owned by this Kingdom (its own Home, or any other province it has
  since taken), 5 more bytes:** ``explored_percent``, ``owner_kingdom_id``
  (always reads this file's own Kingdom id), ``tax``, ``recruit_type_1``,
  ``recruit_type_2`` -- the last two via this project's own already-
  confirmed ``parser/gw_world.py MOD_PAT_ORDINAL_TO_ARMY_TYPE`` table,
  no new lookup needed. Confirmed exactly against both real Home
  records available at Turn 1 (``Piratum``: ``explored_percent`` 100,
  tax 10, Phalanx/Warg Riders; ``the Dolphin Sea``: 100, tax 10,
  Bowmen/Heavy Cavalry) -- every field matches the real ``GW3__T1`` data
  exactly for both. **Confirmed to generalize beyond a literal Home
  too**: by Turn 2, Kingdom 0 has taken ``Redwood``/``Jutland``/
  ``Silvania``/``Tanglewood`` (real ``GW3__T2`` data), and all 4 now
  decode with this same expanded shape (``owner_kingdom_id`` ``0``, the
  same real tax/recruit values as their own unowned Turn 1 records) --
  including ``Redwood`` at ``explored_percent`` ``8``, proving this
  field is a real, independently varying percentage, not a Home-only
  fixed ``100``. The real discriminator is ownership by this Kingdom,
  not "is this the literal Home."

``parse_xk_province_record()`` below decodes one record (either shape,
auto-detected via the exact ``0x01, 0xFF`` ordinary marker) given its
own starting byte offset -- **not** a whole-file province-table scanner.

**Still genuinely open:** exactly where the province table *starts*.
A substantial block of further, still-undeciphered data (836 bytes for
both real Turn 1 samples; 913/839 bytes for the two real Turn 2
samples -- not a fixed size, and not simply proportional to this
Kingdom's own known-leader count either) sits between the end of the
per-leader name table and this Kingdom's own first known-province
record. Repeating small fixed-shape byte groups and a few embedded
ASCII fragments (e.g. ``"Lord"``, ``"Shaman"``) suggest this is a
further, real, structured section (most plausibly a per-army or per-
leader status table, mirroring ``parser/gw_world.py``'s own block
structure) rather than padding, but it is **not decoded, and this
module makes no attempt to locate the province table's own start from
a bare file path** -- a genuine, explicitly flagged gap, not a hidden
assumption. Everything *after* the province table (whatever follows
``Tanglewood``, this sample's own last province record) is equally
undeciphered.

This module intentionally exposes only what is fully confirmed above
(the header's 4 named fields, the per-leader name table, and the
province-record shape once its own start offset is already known) -- a
genuinely useful, tested building block (e.g. a GM-interface screen
could already show "which heroes does this Kingdom currently know
about"), not a claim that XK decoding is complete.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ak_engine.models.army_type import ArmyType
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.race import Race
from ak_engine.parser.gw_world import MOD_PAT_ORDINAL_TO_ARMY_TYPE

XK_HEADER_SIZE = 0x30B
XK_LEADER_ROSTER_COUNT = 100

# The exact 2-byte marker (Phase 989) distinguishing an "ordinary"
# province record (recruit types not revealed at this exploration
# level) from this Kingdom's own Home -- see module docstring.
_ORDINARY_RECORD_MARKER = (0x01, 0xFF)
_UNOWNED_GOVERNOR_SENTINEL = 0xFF


class XKParseError(ValueError):
    """Raised when an ``XK`` file doesn't match the confirmed shape above."""

    def __init__(self, message: str, *, byte_offset: int | None = None):
        self.byte_offset = byte_offset
        super().__init__(message if byte_offset is None else f"{message} (byte offset {byte_offset})")


@dataclass(slots=True)
class XKHeader:
    """The 4 confirmed fields of an ``XK`` file's fixed 0x30B-byte header.

    Every other header byte is genuinely undeciphered -- see the module
    docstring -- and deliberately absent from this dataclass rather
    than exposed as raw, unnamed data.
    """

    header_revision: int
    kingdom_id: int
    game_turn: int
    king_count: int


def _read_bytes(path: Path) -> bytes:
    data = path.read_bytes()
    if len(data) < XK_HEADER_SIZE:
        raise XKParseError(f"XK file too short for the confirmed {XK_HEADER_SIZE}-byte header (got {len(data)} bytes)")
    return data


def parse_xk_header(path: Path) -> XKHeader:
    """Parses the 4 confirmed header fields -- see module docstring."""

    data = _read_bytes(path)
    return XKHeader(
        header_revision=data[0],
        kingdom_id=data[3],
        game_turn=data[0x11],
        king_count=data[0x49],
    )


def parse_xk_known_leader_names(path: Path) -> dict[int, str | None]:
    """The 100-entry per-leader name table immediately after the header.

    Returns ``{leader_id: real_name}`` for every id this Kingdom's own
    file already knows, and ``{leader_id: None}`` for every id still
    showing the confirmed ``"Ldr-<id>"`` placeholder -- callers that want
    the raw placeholder text itself (e.g. to match a real letter
    verbatim) can reconstruct it as ``f"Ldr-{leader_id}"``, since the
    format is a confirmed, zero-exception constant (see module
    docstring), not reproduced as a magic string here.
    """

    data = _read_bytes(path)
    offset = XK_HEADER_SIZE
    names: dict[int, str | None] = {}
    for leader_id in range(XK_LEADER_ROSTER_COUNT):
        if offset >= len(data):
            raise XKParseError("XK file ended mid-way through the 100-entry leader name table", byte_offset=offset)
        length = data[offset]
        offset += 1
        raw = data[offset : offset + length]
        if len(raw) < length:
            raise XKParseError("XK file ended mid-way through a leader name entry", byte_offset=offset)
        name = raw.decode("latin-1")
        offset += length
        names[leader_id] = None if name == f"Ldr-{leader_id}" else name
    return names


@dataclass(slots=True)
class XKProvinceRecord:
    """One decoded province record from the province table -- see the
    module docstring's own Phase 989 addendum for the full derivation.

    ``governor_leader_id``, ``explored_percent``, ``owner_kingdom_id``,
    ``tax``, ``recruit_type_1``, and ``recruit_type_2`` are ``None`` when
    not present in this record's own confirmed shape: an "ordinary"
    record (not this Kingdom's own Home) only ever carries
    ``governor_leader_id``; a Home record only ever carries the other
    five.
    """

    coord: HexCoord
    name: str
    terrain: Terrain
    race: Race
    governor_leader_id: int | None
    explored_percent: int | None
    owner_kingdom_id: int | None
    tax: int | None
    recruit_type_1: ArmyType | None
    recruit_type_2: ArmyType | None


def parse_xk_province_record(data: bytes, offset: int) -> tuple[XKProvinceRecord, int]:
    """Decodes one province-table record starting at ``offset`` (its own
    ``coord_x`` byte) -- see the module docstring's own Phase 989
    addendum. Returns the decoded record and the byte offset immediately
    after it (the next record's own ``coord_x``, if any).

    This function does **not** locate the province table's own start in
    an arbitrary file -- see the module docstring for why that remains
    genuinely open. ``offset`` must already point at a real record.
    """

    if offset + 2 > len(data):
        raise XKParseError("XK file ended mid-way through a province record's own coordinate", byte_offset=offset)
    coord = HexCoord(data[offset], data[offset + 1])
    offset += 2

    if offset >= len(data):
        raise XKParseError("XK file ended mid-way through a province record's own name", byte_offset=offset)
    name_length = data[offset]
    offset += 1
    raw_name = data[offset : offset + name_length]
    if len(raw_name) < name_length:
        raise XKParseError("XK file ended mid-way through a province record's own name", byte_offset=offset)
    name = raw_name.decode("latin-1")
    offset += name_length

    if offset + 4 > len(data):
        raise XKParseError("XK file ended mid-way through a province record's own fields", byte_offset=offset)
    terrain = Terrain(data[offset])
    race = Race(data[offset + 1])
    # data[offset + 2], data[offset + 3] -- unknown_a/unknown_b, always 0
    # in every real sample so far; see module docstring.
    offset += 4

    if (data[offset], data[offset + 1]) == _ORDINARY_RECORD_MARKER:
        offset += 2
        if offset >= len(data):
            raise XKParseError("XK file ended mid-way through a province record's own governor id", byte_offset=offset)
        raw_governor = data[offset]
        offset += 1
        governor_leader_id = None if raw_governor == _UNOWNED_GOVERNOR_SENTINEL else raw_governor
        record = XKProvinceRecord(
            coord=coord,
            name=name,
            terrain=terrain,
            race=race,
            governor_leader_id=governor_leader_id,
            explored_percent=None,
            owner_kingdom_id=None,
            tax=None,
            recruit_type_1=None,
            recruit_type_2=None,
        )
        return record, offset

    if offset + 5 > len(data):
        raise XKParseError("XK file ended mid-way through a Home province record's own fields", byte_offset=offset)
    explored_percent, owner_kingdom_id, tax, recruit1_ordinal, recruit2_ordinal = data[offset : offset + 5]
    offset += 5
    record = XKProvinceRecord(
        coord=coord,
        name=name,
        terrain=terrain,
        race=race,
        governor_leader_id=None,
        explored_percent=explored_percent,
        owner_kingdom_id=owner_kingdom_id,
        tax=tax,
        recruit_type_1=MOD_PAT_ORDINAL_TO_ARMY_TYPE.get(recruit1_ordinal),
        recruit_type_2=MOD_PAT_ORDINAL_TO_ARMY_TYPE.get(recruit2_ordinal),
    )
    return record, offset
