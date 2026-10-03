"""Phase 992: the real ``XK`` per-Kingdom "known world" file -- the
binary export a player's own separate Windows support program reads to
show that Kingdom's own map and prepare their next turn's moves.

**Supersedes Phases 988-991.** Those phases built this module from pure
known-plaintext cryptanalysis (searching for real GW/letter facts inside
the raw bytes, with no Pascal source or disassembly for this format in
the project) and got the header, the per-leader name table, and most of
the province/Feature/treasure records right -- but, lacking a ground
truth for byte *order*, mis-grouped a few adjacent fields (e.g. treating
a Feature record's real 2-byte ``DS:962A`` field as "two always-zero
unknown bytes"), and got the Army record's own field order wrong
entirely (swapping what are really separate ``race``/``type`` bytes for
a guessed, partly-duplicated ``quality``/``state`` layout that happened
to fit the 3 non-Mercenary samples available at the time but broke on
the 4th, Mercenary-state one).

**The user then supplied a real disassembly of ``AK.EXE``'s own XK
*writer* routine** (raw range ``0x1DCBF-0x1FE8A``, calling the real
``BlockWrite``/``3EE5:1C4B``), cross-checked against partial real Pascal
source (``CTBOTH.PAS`` excerpts: the ``ability``/``race``/``outlook``
enum orders, the ``TR_*`` extension-tag constants) and a 12-sample
corpus (this project's own 4 fixtures plus 8 more: the same campaign's
Kingdom 2, and Turns 3-4) -- a far stronger evidentiary basis than
cryptanalysis alone, since it reads the real field order and sizes
directly from the code that writes them rather than inferring them from
outcomes. This phase ports that work: every field and record shape
below is sourced to a specific disassembly address or Pascal excerpt,
not re-derived. Genuinely unconfirmed semantics (most global words, both
~256-byte flag areas, both 192-byte pointer blocks, the Feature record's
own ``DS:962A`` word, Army ``quality_or_mask``, every state/status bit)
are kept as raw ints under their own ``DS_xxxx`` address rather than
guessed at -- the same discipline ``parser/gw_world.py`` already applies
to its own undeciphered fields.

**What XK contains.** A snapshot of the world as known to one specific
Kingdom (the file's own ``kingdom_id``, 0-indexed -- the filename's own
``Kx`` suffix matches it in every sample, but isn't itself authoritative;
this module reads the real header field): names, full or partial
character cards, known provinces, Features, treasures, armies,
discoveries, player administrative data, a province-by-province
recruitable-type map, and race/alignment/ability lookups the real client
needs to render them -- not the GW world save, not an AK orders file.

**Confirmed exact file grammar**, in order:

1. **Header** (5 bytes): ``format_revision`` (``u16``, always ``30`` in
   every sample -- this strict decoder, matching the real disassembly's
   own validated branch, only supports this revision), 1 reserved byte
   (always ``0``), ``kingdom_id`` (``u16``, though every real value seen
   fits a single byte).
2. **Globals** (774 bytes): a verbatim copy of ``DS:C2F6..C5FB`` --
   131 words (262 bytes, ``DS:C2F6..C3FA``), then two 256-byte areas
   (``DS:C3FC``, ``DS:C4FC``). 16 of the 131 words are confirmed-named
   (``XK_GLOBAL_FIELD_NAMES`` below, e.g. ``gameturn``, ``king_count``);
   the rest are raw, keyed ``DS_xxxx`` by address. Both 256-byte areas
   are kept as raw bytes -- real per-bit flag meanings are undeciphered.
3. **Leader names** (always starting at the confirmed offset ``0x30B``,
   779 -- unchanged from Phase 988): ``leader_capacity`` (a named global,
   ``100`` in every real sample) Pascal ShortStrings, one per leader id.
4. **Full character cards**: 74 bytes each (``XKLeaderCard`` below),
   0xFE-terminated.
5. **Partial character cards**: ``id, x, y`` (3 bytes each), 0xFE-terminated.
6. **Leader races**, 7. **leader states**: ``leader_capacity + 1`` raw
   bytes each -- the ``+1`` (not just ``leader_capacity``) is real and
   confirmed in the disassembly; missing it misaligns everything after.
8. ``DS:89C7`` (12 raw bytes), 9. a per-recipient word at
   ``DS:8AE7 + 2*kingdom_id`` (kept raw), 10-11. two 192-byte **per-King
   title tables** from far pointers ``DS:8B29``/``DS:8B2D`` -- see the
   Phase 993 addendum below.
12. **Known provinces** (``XKProvinceRecord`` below), 0xFE-terminated.
13. **Features** (``XKFeatureRecord``, 8 bytes each), 0xFE-terminated.
14. **Treasures** (``XKTreasureRecord``, variable length), 0xFE-terminated.
15. **Armies** (``XKArmyRecord``, 4 or 8 bytes): index-implicit, looping
    the real ``army_count`` global but **skipping index 255** -- a real
    disassembly-confirmed quirk (``army_count=260`` yields 259 records).
16. **Discoveries**: ``id`` + a real ``0xFE01`` legacy word (not a plain
    ``0x0001``/``0x0000`` boolean -- the writer copies 2 bytes from a
    local variable whose own neighbor byte happens to be ``0xFE``),
    0xFE-terminated.
17. **Player tail** (28 raw bytes, ``XK_PLAYER_TAIL_FIELDS`` below).
18. ``TR_End`` (``16001`` as a ``u16``) -- **not EOF yet**.
19. **Recruitment map**: one ``(slot_1, slot_2)`` raw-byte pair per
    board cell, ``(right-left+1) * (bottom-top+1)`` cells, outer loop
    over ``x`` then inner over ``y``. ``0x0F`` (``NoArmy``/placeholder
    in ``MOD_PAT_ORDINAL_TO_ARMY_TYPE``) marks a cell this Kingdom
    doesn't actually know the recruit types for -- not proof the host
    province has none.
20. **Typed extensions**, each its own ``u16`` tag: ``TR_LLs`` (16004,
    id/lliege pairs, ``0xFF``-id-terminated -- a different sentinel than
    everywhere else in this format), ``TR_SA`` (16005, 90 raw bytes, 15
    abilities x 6 levels), ``TR_T2`` (16006, 450 raw bytes, a fixed
    30x15 secondary-terrain capacity -- **not** the played board's own
    size), ``TR_HK`` (16007, syntactically supported, no real sample
    exercises it).
21. **Final** ``TR_End`` (``16001``) -- true EOF; any trailing byte is
    rejected.

**Confirmed real enum/ordinal reuse** (no new lookup tables needed):
``Terrain``/``Race`` ordinals match a province record's raw
``terrain``/``race`` bytes directly (already established, Phase 988).
``parser/gw_world.py``'s own ``MOD_PAT_ORDINAL_TO_ARMY_TYPE`` is the real
ordinal table for a province's ``recruit_type_1``/``recruit_type_2`` AND
for an Army record's own ``army_type`` AND for a recruitment-map cell's
own slot -- one real table, three real call sites (the ``CTBOTH.PAS``
army-type ordinal list this new material supplies matches it exactly
through every ordinal checked, 0-19). ``models/monster.py Monster``/
``MonsterEngagementState`` and ``models/feature.py FeatureType`` match a
Feature record's own raw bytes directly (Phase 991, unchanged).
``models/treasure.py Treasure`` matches a Treasure record's own raw
``type`` byte directly (Phase 991, unchanged). ``models/temper.py
Temper``'s own ``.value`` and ``models/alignment.py
ALIGNMENT_BY_ORDINAL`` (the real ``CTBOTH.PAS outlook`` order, already
in this project) match a full leader card's own raw ``temper``/
``alignment`` bytes directly -- newly confirmed this phase (e.g. King
Babba Sissoko, real ``Alignment.UNDEAD``/``Temper.BERSERK``, reads
``alignment=7``/``temper=3``, exactly ``ALIGNMENT_BY_ORDINAL[7]``/
``Temper.BERSERK.value``).

**Phase 993 -- the two 192-byte ``DS:8B29``/``DS:8B2D`` blocks, fully
decoded.** Each is a fixed array of 12 slots, 16 bytes each (a 1-byte
length then a 15-byte char buffer -- the same truncate-at-15 ShortString
shape Phase 990 first noticed on 2 stray strings before their own
container was known), indexed by king id (``king_count`` real entries,
0-9 in this corpus, plus 2 always-blank reserve slots never observed
populated). ``DS:8B29`` is each King's own ``title_prefix``; ``DS:8B2D``
is each King's own ``title_suffix`` -- **exactly** this project's own
already-existing, already-named ``parser/gw_world.py GWKingExtension.
title_prefix``/``title_suffix`` fields, confirmed by direct cross-check
against both real ``GW3__T1`` and ``GW3__T4`` for both of this
campaign's 2 Kings who ever have non-blank titles: King 0 (Babba
Sissoko) reads ``prefix="Lord"``, ``suffix="Master of the s"`` at Turn 1
and ``suffix="Master orango"`` at Turn 4 (short enough this time to show
untruncated) in both XK *and* GW; King 1 (Uga-Buga Makumb) reads
``prefix="Shaman"``, ``suffix="Lord of the stu"`` (Turn 1) /
``"Stuffy doll"`` (Turn 4) in both, identically. Confirmed identical
across different Kingdoms' own XK files too (every King's title is
public, not per-recipient-filtered) -- this closes Phase 990's own
"two still-unattributed title strings" gap completely, and the
"per-leader status data" that pointer wasn't actually about: these 2
blocks are per-*King*, not per-leader at all.

**Phase 994 -- the Army record's own ``status``/``detail_status``/
``quality_or_mask``, cross-checked at scale.** Confirmed (Phase 992)
that a given XK file's own ``army_index`` (the ``0..army_count-1`` loop
position, ``255`` skipped) lines up *exactly* with ``parser/gw_world.py
parse_gw_armies()``'s own same-order list for the same real world file
(re-inserting the skipped index: ``gw_index = army_index if army_index
< 255 else army_index - 1``) -- this lets every Army record in the
entire 12-file corpus be paired with its own real ``GWArmyRecord``
directly, not just the handful at one Home. Across all 3015 armies this
produced real pairs for: ``race``/``army_type`` matched their own real
``GWArmyRecord`` fields with **zero exceptions**. ``status`` and
``detail_status`` (when present) matched ``GWArmyRecord.state``'s own
real ``MonsterEngagementState`` ordinal **exactly, zero exceptions**
each of the 3 non-``DEAD`` values actually observed (``HIRED``,
``MERCENARY``, ``ZOMBOID``) -- the real enum this project's
``parser/gw_world.py`` already defines, no new table needed; both
fields are now decoded as ``MonsterEngagementState``, not raw ints.
``quality_or_mask`` is **not** a clean 1:1 ordinal: every nonzero value
(``1``-``4``) matched ``GWArmyRecord.quality.value`` exactly in every
one of 190 such cases, but raw ``0`` mapped to **5 different** real
``Quality`` values (``0`` through ``4``, 2825 cases) -- a real masking
sentinel, not "this army's quality is ``Quality.DEPLETED``" (``0``):
most real ``Quality.AVERAGE`` armies happen to be masked to ``0`` too.
Kept as a raw int for exactly this reason -- converting ``0`` to either
``None`` or ``Quality.DEPLETED`` would silently discard real
information the format itself doesn't let a reader recover unambiguously.
A Mercenary-state army is masked less often than an ordinary one (102 of
111 real Mercenary armies reveal their real quality) but not
reliably enough to treat "Mercenary" as the real reveal rule --
genuinely still open.

**Genuinely still open** (kept raw rather than guessed, per the
delivered material's own stated limits): the ~115 unnamed globals and
both 256-byte flag areas; a full card's own ``sex_flags`` bitfield and
``skills``/``aptitudes``/``actions``/``objects``/``extra_low_bytes``
beyond their raw per-ability values; the leader-races/states vectors'
own full value range; a province record's ``unknown_9197_word``; a
Feature record's own ``unknown_962a``; an Army record's own
``quality_or_mask`` (see the Phase 994 addendum above -- a real masking
sentinel, confirmed, but its own reveal rule isn't); a Treasure's own
``trowner`` word beyond the observed ``256 + feature_id`` convention for
a feature-held item (a leader-held item's own convention is asserted,
not independently verified in these samples); why each King title table
reserves 12 slots for at most 10 real Kings (no real sample with
``king_count`` above 10 exists to test whether it's a true fixed cap or
simply never-observed to matter); the real SAGA client reader (only the
host *writer* was disassembled); and any ``gamevers`` other than ``3``
(the compiled client has other branches; this strict decoder
deliberately refuses them rather than extrapolate).
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

from ak_engine.models.alignment import ALIGNMENT_BY_ORDINAL, Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.feature import FeatureType
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.monster import Monster, MonsterEngagementState
from ak_engine.models.race import Race
from ak_engine.models.temper import Temper
from ak_engine.models.treasure import Treasure
from ak_engine.parser.gw_world import MOD_PAT_ORDINAL_TO_ARMY_TYPE

SUPPORTED_FORMAT_REVISION = 30
SUPPORTED_GAME_VERSION = 3
XK_NAME_TABLE_OFFSET = 0x30B

# DS:C2F6 word index -> confirmed real field name (the other 115 of 131
# words in this range are exposed raw, keyed "DS_xxxx" by address -- see
# module docstring).
XK_GLOBAL_FIELD_NAMES: dict[int, str] = {
    0xC302: "gameturn",
    0xC306: "leader_capacity",
    0xC30C: "left",
    0xC30E: "right",
    0xC310: "bottom",
    0xC312: "top",
    0xC314: "gamevers",
    0xC318: "orig_turn",
    0xC320: "gameno",
    0xC322: "due_day",
    0xC324: "due_month",
    0xC326: "due_year",
    0xC328: "turn_days",
    0xC32A: "diplomacy_mode",
    0xC32C: "feature_count",
    0xC338: "army_count",
    0xC33A: "king_count",
    0xC33C: "last_leader",
}

_GLOBALS_START = 0xC2F6
_GLOBALS_WORD_COUNT = 131  # DS:C2F6..C3FA
_FLAGS_AREA_SIZE = 256

# CTBOTH.PAS `ability` order (Tactical..noabil) -- the real index order
# of a full leader card's own 16-entry skills/aptitudes arrays. The 16th
# ("noabil") is a real array slot, not a playable ability.
LEADER_ABILITY_ORDER: tuple[str, ...] = (
    "Tactical",
    "ForcedMarch",
    "Naval",
    "Archery",
    "Melee",
    "White",
    "Necromancy",
    "Elemental",
    "Psychic",
    "Illusionist",
    "Druid",
    "Thief",
    "Explorer",
    "Spy",
    "Sage",
    "noabil",
)

_LEADER_CARD_SIZE = 74
_SENTINEL_END = 0xFE
_SENTINEL_NO_OWNER = 0xFF
_SENTINEL_NO_VISIBLE_OWNER = 0xFE
_TR_LLS_END = 0xFF

_TAG_TR_LLS = 16004
_TAG_TR_SA = 16005
_TAG_TR_T2 = 16006
_TAG_TR_HK = 16007
_TAG_TR_END = 16001

XK_PLAYER_TAIL_FIELDS: tuple[tuple[str, int], ...] = (
    ("DS_8B31", 1),
    ("DS_8B73", 1),
    ("relations_D1D4", 12),
    ("DS_8CBD", 2),
    ("DS_8D41", 2),
    ("DS_8D83", 2),
    ("DS_8E49_low", 2),
    ("DS_8DC5", 2),
    ("DS_8ECD_low", 2),
    ("DS_8F51_low", 2),
)


class XKParseError(ValueError):
    """Raised when an ``XK`` file doesn't match the confirmed shape above."""

    def __init__(self, message: str, *, byte_offset: int | None = None):
        self.byte_offset = byte_offset
        super().__init__(message if byte_offset is None else f"{message} (byte offset {byte_offset})")


class _Reader:
    """A sequential byte-string reader mirroring the real writer's own
    field order -- ports the delivered, roundtrip-verified decoder's
    internals, adapted to raise ``XKParseError`` and to not retain a
    flat leaf log (this module exposes typed dataclasses instead).
    """

    __slots__ = ("data", "offset")

    def __init__(self, data: bytes):
        self.data = data
        self.offset = 0

    def bytes_(self, name: str, length: int) -> bytes:
        start = self.offset
        end = start + length
        if length < 0 or end > len(self.data):
            raise XKParseError(f"{name}: truncated", byte_offset=start)
        self.offset = end
        return self.data[start:end]

    def u8(self, name: str) -> int:
        return self.bytes_(name, 1)[0]

    def u16(self, name: str) -> int:
        return struct.unpack_from("<H", self.bytes_(name, 2))[0]

    def s8(self, name: str) -> int:
        return struct.unpack_from("<b", self.bytes_(name, 1))[0]

    def s16(self, name: str) -> int:
        return struct.unpack_from("<h", self.bytes_(name, 2))[0]

    def peek(self, name: str) -> int:
        if self.offset >= len(self.data):
            raise XKParseError(f"{name}: unexpected EOF", byte_offset=self.offset)
        return self.data[self.offset]

    def pstring(self, name: str) -> str:
        length = self.u8(name + ".length")
        raw = self.bytes_(name, length)
        return raw.decode("cp850")

    def sentinel(self, name: str, expected: int) -> None:
        start = self.offset
        got = self.u8(name)
        if got != expected:
            raise XKParseError(f"{name}: expected {expected:#x}, got {got:#x}", byte_offset=start)


@dataclass(slots=True)
class XKHeader:
    format_revision: int
    kingdom_id: int


@dataclass(slots=True)
class XKGlobals:
    """The 774-byte global block (``DS:C2F6..C5FB``). ``values`` holds
    all 131 words, named where confirmed (``XK_GLOBAL_FIELD_NAMES``) and
    ``DS_xxxx``-keyed otherwise; the named-field properties below are
    thin lookups into it. ``flags_c3fc``/``flags_c4fc`` are the two
    256-byte areas that follow, kept raw -- see module docstring.
    """

    values: dict[str, int]
    flags_c3fc: bytes
    flags_c4fc: bytes

    @property
    def game_turn(self) -> int:
        return self.values["gameturn"]

    @property
    def leader_capacity(self) -> int:
        return self.values["leader_capacity"]

    @property
    def board_left(self) -> int:
        return self.values["left"]

    @property
    def board_right(self) -> int:
        return self.values["right"]

    @property
    def board_top(self) -> int:
        return self.values["top"]

    @property
    def board_bottom(self) -> int:
        return self.values["bottom"]

    @property
    def game_version(self) -> int:
        return self.values["gamevers"]

    @property
    def king_count(self) -> int:
        return self.values["king_count"]

    @property
    def army_count(self) -> int:
        return self.values["army_count"]

    @property
    def feature_count(self) -> int:
        return self.values["feature_count"]

    @property
    def last_leader_id(self) -> int:
        return self.values["last_leader"]


@dataclass(slots=True)
class XKLeaderCard:
    """One full, 74-byte character card -- see module docstring.
    ``skills``/``aptitudes`` are 16-entry raw lists, indexed by
    ``LEADER_ABILITY_ORDER`` (the real ``CTBOTH.PAS ability`` order);
    ``objects`` are 5 signed 16-bit item-instance ids (0 = none observed
    in every real sample); ``planstart``/``planend`` are signed bytes
    (``-1`` is a real, confirmed "no plan" value, not an error).
    """

    leader_id: int
    client_owner: int
    lliege: int
    skills: list[int]
    aptitudes: list[int]
    coord: HexCoord
    birth_coord: HexCoord
    hire_turn: int
    admiral_merit: int
    defender_merit: int
    lfdisc: int
    ldiscp: int
    lwmsp: int
    temper: Temper
    alignment: Alignment
    sex_flags: int
    actions: list[int]
    objects: list[int]
    extra_low_bytes: list[int]
    planstart: int
    planend: int


@dataclass(slots=True)
class XKPartialLeaderCard:
    leader_id: int
    coord: HexCoord


@dataclass(slots=True)
class XKProvinceRecord:
    """One known-province record -- see module docstring. Exactly one of
    the 3 real ownership shapes applies:

    - ``owner_kingdom_id`` set (and ``tax``/``recruit_type_1``/
      ``recruit_type_2`` with it): this Kingdom's own full economic view
      of a province it owns (``ownership_marker`` is itself the owning
      Kingdom's id).
    - ``visible_owner_leader_id`` set or ``None`` (``ownership_marker ==
      0xFF``): another province's owner is visible by leader id, with no
      economic data -- ``None`` means "visibly ungoverned", not
      "unknown".
    - All three ``None`` (``ownership_marker == 0xFE``): no ownership
      information at all.
    """

    coord: HexCoord
    name: str
    terrain: Terrain
    race: Race
    exploration_percent: int
    owner_kingdom_id: int | None
    visible_owner_leader_id: int | None
    tax: int | None
    recruit_type_1: ArmyType | None
    recruit_type_2: ArmyType | None
    unknown_9197_word: int


@dataclass(slots=True)
class XKFeatureRecord:
    """One Feature-summary record (8 bytes) -- see module docstring.
    ``unknown_962a`` is a real ``DS:962A`` word, always ``0`` in every
    sample so far, role unconfirmed.
    """

    feature_id: int
    coord: HexCoord
    unknown_962a: int
    monster: Monster
    engagement_state: MonsterEngagementState
    feature_type: FeatureType


@dataclass(slots=True)
class XKTreasureRecord:
    """One Treasure record -- see module docstring. ``trcharges`` is
    only present (real disassembly-proven predicate, ``0x40558``) when
    ``treasure`` has a raw ordinal in ``[70, 92)``; ``None`` otherwise,
    never defaulted to ``0``. ``trowner`` is kept raw (the real
    ``256 + feature_id`` convention for a feature-held item is confirmed
    by example, not derived here as a property, since a leader-held
    item's own convention isn't independently verified in these
    samples).
    """

    feature_id: int
    treasure: Treasure
    trcharges: int | None
    trowner: int
    name: str


@dataclass(slots=True)
class XKArmyRecord:
    """One Army record (4 or 8 bytes) -- see module docstring's own
    Phase 994 addendum for ``status``/``detail_status``/
    ``quality_or_mask``. ``army_index`` is this army's own position in
    the real ``0..army_count-1`` loop (with ``255`` always skipped), not
    a stored id -- confirmed (Phase 994) to be the *exact* same 0-based
    position this project's own ``parser/gw_world.py parse_gw_armies()``
    already returns for the same real world file, so the two can be
    zipped directly (after re-inserting the skipped index) for a real
    army's full detail. ``coord``/``commanded_by_leader_id``/
    ``detail_status`` are ``None`` when this record has no location
    details (a literal ``0xFE`` in that position, confirmed real, not
    merely "not yet observed").
    """

    army_index: int
    race: Race
    army_type: ArmyType | None
    quality_or_mask: int
    status: MonsterEngagementState
    coord: HexCoord | None
    commanded_by_leader_id: int | None
    detail_status: MonsterEngagementState | None


@dataclass(slots=True)
class XKDiscoveryRecord:
    feature_id: int
    legacy_word: int


@dataclass(slots=True)
class XKRecruitmentMapCell:
    coord: HexCoord
    recruit_type_1: ArmyType | None
    recruit_type_2: ArmyType | None


@dataclass(slots=True)
class XKSecondaryAbilityTable:
    """``TR_SA`` (tag 16005): 90 raw bytes, 15 real abilities x 6 levels
    (``LEADER_ABILITY_ORDER``'s own first 15 entries, excluding
    ``noabil``) -- associates special-ability codes with the real
    prose/name tables those abilities use, not a second skill array.
    """

    levels_by_ability: list[list[int]]


@dataclass(slots=True)
class XKLiegeExtension:
    """``TR_LLs`` (tag 16004): id/lliege pairs. A real ``0xFF`` in the
    ``lliege`` position does not end the list -- only ``0xFF`` in the
    ``id`` position does (a different sentinel than every other list in
    this format).
    """

    liege_by_leader_id: dict[int, int]


@dataclass(slots=True)
class XKSecondaryTerrainTable:
    """``TR_T2`` (tag 16006): a fixed 30x15 (450-byte) capacity table,
    indexed ``15*x + y`` -- **not** sized to the played board, and not
    proof every cell is a real, active province.
    """

    raw: bytes


@dataclass(slots=True)
class XKHomeKingdomExtension:
    """``TR_HK`` (tag 16007): syntactically supported, sourced from the
    writer's own branch and the real Pascal shield-record size -- no
    real sample in this project's own corpus exercises it yet.
    """

    king_leader_id: int
    shield_record: bytes


_KING_TITLE_TABLE_CAPACITY = 12
_KING_TITLE_SLOT_SIZE = 16


@dataclass(slots=True)
class XKKingTitles:
    """Both per-King title tables (``DS:8B29``/``DS:8B2D``) -- see the
    module docstring's own Phase 993 addendum. Each list has exactly
    ``_KING_TITLE_TABLE_CAPACITY`` (12) entries, indexed by king id; a
    king with no title (or a reserve slot beyond the real ``king_count``)
    reads ``""``, never absent. Confirmed public (identical across every
    Kingdom's own XK file), not filtered per recipient.
    """

    prefix_by_king_id: list[str]
    suffix_by_king_id: list[str]


@dataclass(slots=True)
class XKWorld:
    """The fully decoded contents of one ``XK`` file."""

    header: XKHeader
    globals: XKGlobals
    leader_names: list[str | None]
    leader_cards: list[XKLeaderCard]
    partial_leader_cards: list[XKPartialLeaderCard]
    leader_races: list[Race]
    leader_states: list[int]
    ds_89c7: bytes
    recipient_word: int
    king_titles: XKKingTitles
    provinces: list[XKProvinceRecord]
    features: list[XKFeatureRecord]
    treasures: list[XKTreasureRecord]
    armies: list[XKArmyRecord]
    discoveries: list[XKDiscoveryRecord]
    player_tail: dict[str, bytes]
    recruitment_map: list[XKRecruitmentMapCell]
    liege_extension: XKLiegeExtension | None
    secondary_abilities: XKSecondaryAbilityTable | None
    secondary_terrain: XKSecondaryTerrainTable | None
    home_kingdom: XKHomeKingdomExtension | None


def _read_globals(r: _Reader) -> XKGlobals:
    values: dict[str, int] = {}
    for word_index in range(_GLOBALS_WORD_COUNT):
        address = _GLOBALS_START + 2 * word_index
        key = XK_GLOBAL_FIELD_NAMES.get(address, f"DS_{address:04X}")
        values[key] = r.s16(f"globals.{key}")
    flags_c3fc = r.bytes_("flags_C3FC", _FLAGS_AREA_SIZE)
    flags_c4fc = r.bytes_("flags_C4FC", _FLAGS_AREA_SIZE)
    return XKGlobals(values=values, flags_c3fc=flags_c3fc, flags_c4fc=flags_c4fc)


def _read_king_title_table(r: _Reader, name: str) -> list[str]:
    """Reads one 192-byte per-King title table -- see module docstring's
    own Phase 993 addendum. Each of the 12 fixed-width 16-byte slots
    holds a length-prefixed string in its own first ``1 + length`` bytes;
    the rest of the slot is unused padding, discarded here.
    """

    titles: list[str] = []
    for king_id in range(_KING_TITLE_TABLE_CAPACITY):
        slot = r.bytes_(f"{name}[{king_id}]", _KING_TITLE_SLOT_SIZE)
        length = slot[0]
        titles.append(slot[1 : 1 + length].decode("cp850"))
    return titles


def _read_leader_names(r: _Reader, leader_capacity: int) -> list[str | None]:
    names: list[str | None] = []
    for leader_id in range(leader_capacity):
        name = r.pstring(f"leader_names[{leader_id}]")
        names.append(None if name == f"Ldr-{leader_id}" else name)
    return names


def _read_leader_card(r: _Reader) -> XKLeaderCard:
    leader_id = r.u8("leader.id")
    client_owner = r.u8(f"leader[{leader_id}].client_owner")
    lliege = r.u8(f"leader[{leader_id}].lliege")
    skills = list(r.bytes_(f"leader[{leader_id}].skills", 16))
    aptitudes = list(r.bytes_(f"leader[{leader_id}].aptitudes", 16))
    x = r.u8(f"leader[{leader_id}].x")
    y = r.u8(f"leader[{leader_id}].y")
    born_x = r.u8(f"leader[{leader_id}].born_x")
    born_y = r.u8(f"leader[{leader_id}].born_y")
    hire_turn = r.s16(f"leader[{leader_id}].hire_turn")
    admiral_merit = r.s16(f"leader[{leader_id}].admiral_merit")
    defender_merit = r.s16(f"leader[{leader_id}].defender_merit")
    lfdisc = r.u8(f"leader[{leader_id}].lfdisc")
    ldiscp = r.u8(f"leader[{leader_id}].ldiscp")
    lwmsp = r.u8(f"leader[{leader_id}].lwmsp")
    temper = r.u8(f"leader[{leader_id}].temper")
    alignment = r.u8(f"leader[{leader_id}].alignment")
    sex_flags = r.s16(f"leader[{leader_id}].sex_flags")
    actions = list(r.bytes_(f"leader[{leader_id}].actions", 5))
    objects = [struct.unpack("<h", r.bytes_(f"leader[{leader_id}].objects[{i}]", 2))[0] for i in range(5)]
    extra_low_bytes = list(r.bytes_(f"leader[{leader_id}].extra_low_bytes", 5))
    planstart = r.s8(f"leader[{leader_id}].planstart")
    planend = r.s8(f"leader[{leader_id}].planend")
    return XKLeaderCard(
        leader_id=leader_id,
        client_owner=client_owner,
        lliege=lliege,
        skills=skills,
        aptitudes=aptitudes,
        coord=HexCoord(x, y),
        birth_coord=HexCoord(born_x, born_y),
        hire_turn=hire_turn,
        admiral_merit=admiral_merit,
        defender_merit=defender_merit,
        lfdisc=lfdisc,
        ldiscp=ldiscp,
        lwmsp=lwmsp,
        temper=Temper(temper),
        alignment=ALIGNMENT_BY_ORDINAL[alignment],
        sex_flags=sex_flags,
        actions=actions,
        objects=objects,
        extra_low_bytes=extra_low_bytes,
        planstart=planstart,
        planend=planend,
    )


def _read_province(r: _Reader) -> XKProvinceRecord:
    x = r.u8("province.x")
    y = r.u8("province.y")
    key = f"province[{x},{y}]"
    name = r.pstring(key + ".name")
    terrain = Terrain(r.u8(key + ".terrain"))
    race = Race(r.u8(key + ".race"))
    unknown_9197_word = r.s16(key + ".unknown_9197_word")
    exploration_percent = r.u8(key + ".exploration")
    marker = r.u8(key + ".ownership_marker")
    owner_kingdom_id: int | None = None
    visible_owner_leader_id: int | None = None
    tax: int | None = None
    recruit_type_1: ArmyType | None = None
    recruit_type_2: ArmyType | None = None
    if marker == _SENTINEL_NO_OWNER:
        visible_owner = r.u8(key + ".visible_owner")
        visible_owner_leader_id = None if visible_owner == _SENTINEL_NO_OWNER else visible_owner
    elif marker == _SENTINEL_NO_VISIBLE_OWNER:
        pass
    else:
        owner_kingdom_id = marker
        tax = r.u8(key + ".ptax")
        recruit_type_1 = MOD_PAT_ORDINAL_TO_ARMY_TYPE.get(r.u8(key + ".recruit_1"))
        recruit_type_2 = MOD_PAT_ORDINAL_TO_ARMY_TYPE.get(r.u8(key + ".recruit_2"))
    return XKProvinceRecord(
        coord=HexCoord(x, y),
        name=name,
        terrain=terrain,
        race=race,
        exploration_percent=exploration_percent,
        owner_kingdom_id=owner_kingdom_id,
        visible_owner_leader_id=visible_owner_leader_id,
        tax=tax,
        recruit_type_1=recruit_type_1,
        recruit_type_2=recruit_type_2,
        unknown_9197_word=unknown_9197_word,
    )


def _read_feature(r: _Reader) -> XKFeatureRecord:
    feature_id = r.u8("feature.id")
    x = r.u8(f"feature[{feature_id}].x")
    y = r.u8(f"feature[{feature_id}].y")
    unknown_962a = r.s16(f"feature[{feature_id}].unknown_962a")
    monster = r.u8(f"feature[{feature_id}].monster")
    engagement_state = r.u8(f"feature[{feature_id}].engagement_state")
    feature_type = r.u8(f"feature[{feature_id}].feature_type")
    return XKFeatureRecord(
        feature_id=feature_id,
        coord=HexCoord(x, y),
        unknown_962a=unknown_962a,
        monster=Monster(monster),
        engagement_state=MonsterEngagementState(engagement_state),
        feature_type=FeatureType(feature_type),
    )


def _read_treasure(r: _Reader) -> XKTreasureRecord:
    feature_id = r.u8("treasure.id")
    treasure_ordinal = r.u8(f"treasure[{feature_id}].type")
    trcharges: int | None = None
    if 70 <= treasure_ordinal < 92:
        trcharges = r.u8(f"treasure[{feature_id}].trcharges")
    trowner = r.u16(f"treasure[{feature_id}].trowner")
    name = r.pstring(f"treasure[{feature_id}].name")
    return XKTreasureRecord(
        feature_id=feature_id,
        treasure=Treasure(treasure_ordinal),
        trcharges=trcharges,
        trowner=trowner,
        name=name,
    )


def _read_army(r: _Reader, army_index: int) -> XKArmyRecord:
    race = Race(r.u8(f"army[{army_index}].race"))
    army_type = MOD_PAT_ORDINAL_TO_ARMY_TYPE.get(r.u8(f"army[{army_index}].type"))
    quality_or_mask = r.u8(f"army[{army_index}].quality_or_mask")
    status = MonsterEngagementState(r.u8(f"army[{army_index}].status"))
    marker = r.u8(f"army[{army_index}].x_or_hidden")
    coord: HexCoord | None = None
    commanded_by_leader_id: int | None = None
    detail_status: MonsterEngagementState | None = None
    if marker != _SENTINEL_END:
        x = marker
        y = r.u8(f"army[{army_index}].y")
        leader = r.u8(f"army[{army_index}].leader")
        detail_status = MonsterEngagementState(r.u8(f"army[{army_index}].detail_status"))
        coord = HexCoord(x, y)
        commanded_by_leader_id = None if leader == _SENTINEL_NO_OWNER else leader
    return XKArmyRecord(
        army_index=army_index,
        race=race,
        army_type=army_type,
        quality_or_mask=quality_or_mask,
        status=status,
        coord=coord,
        commanded_by_leader_id=commanded_by_leader_id,
        detail_status=detail_status,
    )


def parse_xk_world(path: Path) -> XKWorld:
    """Fully decodes one ``XK`` file -- see module docstring for the
    complete grammar and sourcing. Raises ``XKParseError`` on anything
    that doesn't match the confirmed shape (an unsupported
    ``format_revision``/``gamevers``, a truncated file, or trailing
    bytes after the final ``TR_End``).
    """

    data = path.read_bytes()
    r = _Reader(data)

    format_revision = r.u16("format_revision")
    if format_revision != SUPPORTED_FORMAT_REVISION:
        raise XKParseError(f"unsupported format_revision {format_revision} (only {SUPPORTED_FORMAT_REVISION} is validated)")
    r.u8("prefix_reserved")
    kingdom_id = r.u16("kingdom_id")
    header = XKHeader(format_revision=format_revision, kingdom_id=kingdom_id)

    globals_ = _read_globals(r)
    if globals_.game_version != SUPPORTED_GAME_VERSION:
        raise XKParseError(f"unsupported gamevers {globals_.game_version} (only {SUPPORTED_GAME_VERSION} is validated)")

    leader_names = _read_leader_names(r, globals_.leader_capacity)

    leader_cards: list[XKLeaderCard] = []
    while r.peek("leaders") != _SENTINEL_END:
        leader_cards.append(_read_leader_card(r))
    r.sentinel("leaders.end", _SENTINEL_END)

    partial_leader_cards: list[XKPartialLeaderCard] = []
    while r.peek("partial_leaders") != _SENTINEL_END:
        leader_id = r.u8("partial_leader.id")
        x = r.u8(f"partial[{leader_id}].x")
        y = r.u8(f"partial[{leader_id}].y")
        partial_leader_cards.append(XKPartialLeaderCard(leader_id=leader_id, coord=HexCoord(x, y)))
    r.sentinel("partial_leaders.end", _SENTINEL_END)

    leader_races = [Race(r.u8(f"leader_races[{i}]")) for i in range(globals_.leader_capacity + 1)]
    leader_states = [r.u8(f"leader_states[{i}]") for i in range(globals_.leader_capacity + 1)]

    ds_89c7 = r.bytes_("DS_89C7", 12)
    recipient_word = r.s16("DS_8AE7_recipient_word")
    king_titles = XKKingTitles(
        prefix_by_king_id=_read_king_title_table(r, "king_title_prefixes"),
        suffix_by_king_id=_read_king_title_table(r, "king_title_suffixes"),
    )

    provinces: list[XKProvinceRecord] = []
    while r.peek("provinces") != _SENTINEL_END:
        provinces.append(_read_province(r))
    r.sentinel("provinces.end", _SENTINEL_END)

    features: list[XKFeatureRecord] = []
    while r.peek("features") != _SENTINEL_END:
        features.append(_read_feature(r))
    r.sentinel("features.end", _SENTINEL_END)

    treasures: list[XKTreasureRecord] = []
    while r.peek("treasures") != _SENTINEL_END:
        treasures.append(_read_treasure(r))
    r.sentinel("treasures.end", _SENTINEL_END)

    armies: list[XKArmyRecord] = []
    for army_index in range(globals_.army_count):
        if army_index == 255:
            continue
        armies.append(_read_army(r, army_index))

    discoveries: list[XKDiscoveryRecord] = []
    while r.peek("discoveries") != _SENTINEL_END:
        feature_id = r.u8("discovery.id")
        legacy_word = r.s16(f"discovery[{feature_id}].legacy_word")
        discoveries.append(XKDiscoveryRecord(feature_id=feature_id, legacy_word=legacy_word))
    r.sentinel("discoveries.end", _SENTINEL_END)

    player_tail: dict[str, bytes] = {}
    for field_name, size in XK_PLAYER_TAIL_FIELDS:
        player_tail[field_name] = r.bytes_(field_name, size)

    r.sentinel("base.end", _TAG_TR_END & 0xFF)
    r.sentinel("base.end.hi", _TAG_TR_END >> 8)

    recruitment_map: list[XKRecruitmentMapCell] = []
    for x in range(globals_.board_left, globals_.board_right + 1):
        for y in range(globals_.board_top, globals_.board_bottom + 1):
            slot1 = r.u8(f"recruit_map[{x},{y}].slot1")
            slot2 = r.u8(f"recruit_map[{x},{y}].slot2")
            recruitment_map.append(
                XKRecruitmentMapCell(
                    coord=HexCoord(x, y),
                    recruit_type_1=MOD_PAT_ORDINAL_TO_ARMY_TYPE.get(slot1),
                    recruit_type_2=MOD_PAT_ORDINAL_TO_ARMY_TYPE.get(slot2),
                )
            )

    liege_extension: XKLiegeExtension | None = None
    secondary_abilities: XKSecondaryAbilityTable | None = None
    secondary_terrain: XKSecondaryTerrainTable | None = None
    home_kingdom: XKHomeKingdomExtension | None = None
    saw_final_end = False
    while not saw_final_end:
        tag = r.u16("extension.tag")
        if tag == _TAG_TR_END:
            saw_final_end = True
        elif tag == _TAG_TR_LLS:
            liege_by_leader_id: dict[int, int] = {}
            while r.peek("TR_LLs") != _TR_LLS_END:
                leader_id = r.u8("TR_LLs.id")
                liege_by_leader_id[leader_id] = r.u8(f"TR_LLs[{leader_id}].lliege")
            r.sentinel("TR_LLs.end", _TR_LLS_END)
            liege_extension = XKLiegeExtension(liege_by_leader_id=liege_by_leader_id)
        elif tag == _TAG_TR_SA:
            flat = list(r.bytes_("TR_SA.spabord", 90))
            secondary_abilities = XKSecondaryAbilityTable(levels_by_ability=[flat[i : i + 6] for i in range(0, 90, 6)])
        elif tag == _TAG_TR_T2:
            secondary_terrain = XKSecondaryTerrainTable(raw=r.bytes_("TR_T2.pt2", 450))
        elif tag == _TAG_TR_HK:
            king_leader_id = r.u8("TR_HK.king")
            shield_record = r.bytes_("TR_HK.shield_record", 190)
            home_kingdom = XKHomeKingdomExtension(king_leader_id=king_leader_id, shield_record=shield_record)
        else:
            raise XKParseError(f"unsupported extension tag {tag}", byte_offset=r.offset - 2)

    if r.offset != len(data):
        raise XKParseError(f"{len(data) - r.offset} trailing bytes after the final TR_End", byte_offset=r.offset)

    return XKWorld(
        header=header,
        globals=globals_,
        leader_names=leader_names,
        leader_cards=leader_cards,
        partial_leader_cards=partial_leader_cards,
        leader_races=leader_races,
        leader_states=leader_states,
        ds_89c7=ds_89c7,
        recipient_word=recipient_word,
        king_titles=king_titles,
        provinces=provinces,
        features=features,
        treasures=treasures,
        armies=armies,
        discoveries=discoveries,
        player_tail=player_tail,
        recruitment_map=recruitment_map,
        liege_extension=liege_extension,
        secondary_abilities=secondary_abilities,
        secondary_terrain=secondary_terrain,
        home_kingdom=home_kingdom,
    )
