"""Writer for the ``XK`` per-Kingdom binary format -- the exact inverse of
``parser/xk_world.py``'s ``parse_xk_world``/``_Reader``.

**Scope, Phase 1026.** One writer function per confirmed record type, each
the exact byte-shape inverse of its own ``_read_*`` counterpart --
verified by a real round trip (write a real file's own already-parsed
``XKWorld``, then feed the written bytes back through ``parse_xk_world``,
then assert *byte-identical* equality against the original file) rather
than merely "re-parses without error." Unlike ``gw_world_writer.py``
(a text format, data-exact but not whitespace-exact), this writer *is*
byte-for-byte exact against all 17 real fixtures -- every field
``parse_xk_world`` decodes, including the "genuinely still open" ones
(the two 256-byte flag areas, the ~115 unnamed globals, the player-tail
constants, ``TR_T2``), is already captured as raw bytes/ints inside
``XKWorld`` by the reader, so no new semantic discovery is needed here to
reproduce them exactly.

**Two real round-trip hazards found and fixed while building this
writer** (both genuine byte-identity blockers, not estimation calls):

- **Province ownership ambiguity** (Phase 1026): ``XKProvinceRecord``'s
  own ``owner_kingdom_id``/``visible_owner_leader_id`` collapse two
  distinct real marker bytes (``0xFF`` with a ``0xFF`` "visibly
  ungoverned" sub-byte, vs. plain ``0xFE``) to the same ``None``/``None``
  state -- confirmed to really occur both ways across the 17-file corpus
  (62 vs. 27 real records). ``XKProvinceRecord.no_ownership_info`` (added
  this phase, see ``xk_world.py``'s own addendum) resolves it.
- **Extension-block order**: the reader accepts ``TR_LLs``/``TR_SA``/
  ``TR_T2``/``TR_HK`` in any order via tag dispatch, and ``XKWorld``
  itself doesn't record which order a given file used. Checked directly:
  all 17 real fixtures emit the identical order ``TR_LLs, TR_SA, TR_T2,
  TR_End`` (``TR_HK`` never appears in any of them) -- this writer
  hardcodes that same order, which is therefore byte-exact against every
  fixture on hand, but is not independently confirmed to be the real
  writer's own *only* possible order (just the only one ever observed).

**What this deliberately does NOT cover**: a file this writer produces
re-parsing cleanly through ``parse_xk_world`` is a necessary check, not a
guarantee the real, never-disassembled SAGA client would accept it --
see ``xk_world.py``'s own module docstring, "Genuinely still open"
paragraph, for the byte ranges whose real semantic meaning (as opposed to
their confirmed raw shape) is still unknown.
"""

from __future__ import annotations

import struct

from ak_engine.models.alignment import ALIGNMENT_ORDINAL
from ak_engine.parser.gw_world_writer import ARMY_TYPE_TO_MOD_PAT_ORDINAL, _NO_ARMY_TYPE_ORDINAL
from ak_engine.parser.xk_world import (
    XK_GLOBAL_FIELD_NAMES,
    XK_PLAYER_TAIL_FIELDS_AFTER_RELATIONS,
    XK_PLAYER_TAIL_FIELDS_BEFORE_RELATIONS,
    XK_PLAYER_TAIL_FIELDS_TRAILING,
    _FLAGS_AREA_SIZE,
    _GLOBALS_START,
    _GLOBALS_WORD_COUNT,
    _KING_TITLE_SLOT_SIZE,
    _KING_TITLE_TABLE_CAPACITY,
    _SENTINEL_END,
    _SENTINEL_NO_OWNER,
    _SENTINEL_NO_VISIBLE_OWNER,
    _TAG_TR_END,
    _TAG_TR_HK,
    _TAG_TR_LLS,
    _TAG_TR_SA,
    _TAG_TR_T2,
    _TR_LLS_END,
    XKArmyRecord,
    XKFeatureRecord,
    XKGlobals,
    XKKingTitles,
    XKLeaderCard,
    XKPartialLeaderCard,
    XKProvinceRecord,
    XKTreasureRecord,
    XKWorld,
)


class _Writer:
    """A sequential byte-string writer mirroring ``xk_world._Reader`` --
    one method per reader method, writing instead of reading.
    """

    __slots__ = ("buffer",)

    def __init__(self) -> None:
        self.buffer = bytearray()

    def bytes_(self, data: bytes) -> None:
        self.buffer += data

    def u8(self, value: int) -> None:
        self.buffer += struct.pack("<B", value)

    def s8(self, value: int) -> None:
        self.buffer += struct.pack("<b", value)

    def u16(self, value: int) -> None:
        self.buffer += struct.pack("<H", value)

    def s16(self, value: int) -> None:
        self.buffer += struct.pack("<h", value)

    def pstring(self, value: str) -> None:
        encoded = value.encode("cp850")
        if len(encoded) > 255:
            raise ValueError(f"string too long for a Pascal ShortString: {value!r} ({len(encoded)} bytes)")
        self.u8(len(encoded))
        self.bytes_(encoded)

    def sentinel(self, value: int) -> None:
        self.u8(value)

    def getvalue(self) -> bytes:
        return bytes(self.buffer)


def _check_not_sentinel(value: int, name: str) -> None:
    if value == _SENTINEL_END:
        raise ValueError(f"{name} {value:#x} collides with this format's own list-end sentinel ({_SENTINEL_END:#x})")


def _write_globals(w: _Writer, globals_: XKGlobals) -> None:
    for word_index in range(_GLOBALS_WORD_COUNT):
        address = _GLOBALS_START + 2 * word_index
        key = XK_GLOBAL_FIELD_NAMES.get(address, f"DS_{address:04X}")
        w.s16(globals_.values[key])
    if len(globals_.flags_c3fc) != _FLAGS_AREA_SIZE or len(globals_.flags_c4fc) != _FLAGS_AREA_SIZE:
        raise ValueError("flags_c3fc/flags_c4fc must each be exactly 256 bytes")
    w.bytes_(globals_.flags_c3fc)
    w.bytes_(globals_.flags_c4fc)


def _write_king_title_slot(w: _Writer, title: str) -> None:
    encoded = title.encode("cp850")
    if len(encoded) > _KING_TITLE_SLOT_SIZE - 1:
        raise ValueError(f"king title too long for its fixed 16-byte slot: {title!r}")
    w.u8(len(encoded))
    w.bytes_(encoded)
    w.bytes_(bytes(_KING_TITLE_SLOT_SIZE - 1 - len(encoded)))


def _write_king_title_table(w: _Writer, titles: list[str]) -> None:
    if len(titles) != _KING_TITLE_TABLE_CAPACITY:
        raise ValueError(f"expected {_KING_TITLE_TABLE_CAPACITY} king title slots, got {len(titles)}")
    for title in titles:
        _write_king_title_slot(w, title)


def _write_leader_names(w: _Writer, names: list[str | None], leader_capacity: int) -> None:
    if len(names) != leader_capacity:
        raise ValueError(f"expected {leader_capacity} leader names, got {len(names)}")
    for leader_id, name in enumerate(names):
        w.pstring(name if name is not None else f"Ldr-{leader_id}")


def _write_leader_card(w: _Writer, card: XKLeaderCard) -> None:
    _check_not_sentinel(card.leader_id, "leader_id")
    w.u8(card.leader_id)
    w.u8(card.client_owner)
    w.u8(card.lliege)
    if len(card.skills) != 16 or len(card.aptitudes) != 16:
        raise ValueError("a leader card's skills/aptitudes must each be exactly 16 raw bytes")
    w.bytes_(bytes(card.skills))
    w.bytes_(bytes(card.aptitudes))
    w.u8(card.coord.x)
    w.u8(card.coord.y)
    w.u8(card.birth_coord.x)
    w.u8(card.birth_coord.y)
    w.s16(card.hire_turn)
    w.s16(card.general_merit)
    w.s16(card.defender_merit)
    w.u8(card.lfdisc)
    w.u8(card.ldiscp)
    w.u8(card.lwmsp)
    w.u8(card.temper.value)
    w.u8(ALIGNMENT_ORDINAL[card.alignment])
    w.s16(card.sex_flags)
    if len(card.actions) != 5:
        raise ValueError("a leader card's actions must be exactly 5 raw bytes")
    w.bytes_(bytes(card.actions))
    if len(card.objects) != 5:
        raise ValueError("a leader card's objects must be exactly 5 values")
    for value in card.objects:
        w.s16(value)
    if len(card.extra_low_bytes) != 5:
        raise ValueError("a leader card's extra_low_bytes must be exactly 5 raw bytes")
    w.bytes_(bytes(card.extra_low_bytes))
    w.s8(card.planstart)
    w.s8(card.planend)


def _write_partial_leader_card(w: _Writer, card: XKPartialLeaderCard) -> None:
    _check_not_sentinel(card.leader_id, "leader_id")
    w.u8(card.leader_id)
    w.u8(card.coord.x)
    w.u8(card.coord.y)


def _write_province(w: _Writer, province: XKProvinceRecord) -> None:
    _check_not_sentinel(province.coord.x, "province x coordinate")
    w.u8(province.coord.x)
    w.u8(province.coord.y)
    w.pstring(province.name)
    w.u8(province.terrain.value)
    w.u8(province.race.value)
    w.s16(province.effects_bitmask)
    w.u8(province.exploration_percent)
    if province.owner_kingdom_id is not None:
        if province.owner_kingdom_id in (_SENTINEL_NO_OWNER, _SENTINEL_NO_VISIBLE_OWNER):
            raise ValueError(f"owner_kingdom_id {province.owner_kingdom_id:#x} collides with a province ownership-marker sentinel")
        w.u8(province.owner_kingdom_id)
        if province.tax is None:
            raise ValueError("an owned province must have a tax value")
        w.u8(province.tax)
        w.u8(ARMY_TYPE_TO_MOD_PAT_ORDINAL.get(province.recruit_type_1, _NO_ARMY_TYPE_ORDINAL) if province.recruit_type_1 else _NO_ARMY_TYPE_ORDINAL)
        w.u8(ARMY_TYPE_TO_MOD_PAT_ORDINAL.get(province.recruit_type_2, _NO_ARMY_TYPE_ORDINAL) if province.recruit_type_2 else _NO_ARMY_TYPE_ORDINAL)
    elif province.no_ownership_info:
        w.u8(_SENTINEL_NO_VISIBLE_OWNER)
    else:
        w.u8(_SENTINEL_NO_OWNER)
        if province.visible_owner_leader_id is None:
            w.u8(_SENTINEL_NO_OWNER)
        else:
            if province.visible_owner_leader_id == _SENTINEL_NO_OWNER:
                raise ValueError(f"visible_owner_leader_id {province.visible_owner_leader_id:#x} collides with the 'no visible owner' sentinel")
            w.u8(province.visible_owner_leader_id)


def _write_feature(w: _Writer, feature: XKFeatureRecord) -> None:
    _check_not_sentinel(feature.feature_id, "feature_id")
    w.u8(feature.feature_id)
    w.u8(feature.coord.x)
    w.u8(feature.coord.y)
    w.s16(feature.unknown_962a)
    w.u8(feature.monster.value)
    w.u8(feature.engagement_state.value)
    w.u8(feature.feature_type.value)


def _write_treasure(w: _Writer, treasure: XKTreasureRecord) -> None:
    _check_not_sentinel(treasure.feature_id, "treasure feature_id")
    w.u8(treasure.feature_id)
    treasure_ordinal = treasure.treasure.value
    w.u8(treasure_ordinal)
    if 70 <= treasure_ordinal < 92:
        if treasure.trcharges is None:
            raise ValueError(f"treasure ordinal {treasure_ordinal} requires trcharges, got None")
        w.u8(treasure.trcharges)
    elif treasure.trcharges is not None:
        raise ValueError(f"treasure ordinal {treasure_ordinal} must not carry trcharges, got {treasure.trcharges}")
    w.u16(treasure.trowner)
    w.pstring(treasure.name)


def _write_army(w: _Writer, army: XKArmyRecord) -> None:
    w.u8(army.race.value)
    w.u8(ARMY_TYPE_TO_MOD_PAT_ORDINAL.get(army.army_type, _NO_ARMY_TYPE_ORDINAL) if army.army_type else _NO_ARMY_TYPE_ORDINAL)
    w.u8(army.quality_or_mask)
    w.u8(army.status.value)
    if army.coord is None:
        w.u8(_SENTINEL_END)
    else:
        _check_not_sentinel(army.coord.x, f"army[{army.army_index}] x coordinate")
        w.u8(army.coord.x)
        w.u8(army.coord.y)
        w.u8(_SENTINEL_NO_OWNER if army.commanded_by_leader_id is None else army.commanded_by_leader_id)
        if army.detail_status is None:
            raise ValueError("an army record with a coord must also carry detail_status")
        w.u8(army.detail_status.value)


def write_xk_world(world: XKWorld) -> bytes:
    """Writes one ``XK`` file's full contents -- the exact inverse of
    ``parse_xk_world``. See module docstring for the two real round-trip
    hazards this writer resolves and for what it does not guarantee.
    """

    w = _Writer()

    w.u16(world.header.format_revision)
    w.u8(0)  # prefix_reserved -- always 0 in every real sample.
    w.u16(world.header.kingdom_id)

    _write_globals(w, world.globals)

    _write_leader_names(w, world.leader_names, world.globals.leader_capacity)

    for card in world.leader_cards:
        _write_leader_card(w, card)
    w.sentinel(_SENTINEL_END)

    for partial in world.partial_leader_cards:
        _write_partial_leader_card(w, partial)
    w.sentinel(_SENTINEL_END)

    expected_leader_slots = world.globals.leader_capacity + 1
    if len(world.leader_races) != expected_leader_slots or len(world.leader_states) != expected_leader_slots:
        raise ValueError(f"leader_races/leader_states must each have {expected_leader_slots} entries (leader_capacity + 1)")
    for race in world.leader_races:
        w.u8(race.value)
    for state in world.leader_states:
        w.u8(state)

    if len(world.king_sex) != 12:
        raise ValueError("king_sex must have exactly 12 entries")
    for sex in world.king_sex:
        w.u8(0 if sex is None else ord(sex.value))

    w.s16(world.treasury)

    _write_king_title_table(w, world.king_titles.prefix_by_king_id)
    _write_king_title_table(w, world.king_titles.suffix_by_king_id)

    for province in world.provinces:
        _write_province(w, province)
    w.sentinel(_SENTINEL_END)

    for feature in world.features:
        _write_feature(w, feature)
    w.sentinel(_SENTINEL_END)

    for treasure in world.treasures:
        _write_treasure(w, treasure)
    w.sentinel(_SENTINEL_END)

    expected_army_indices = [i for i in range(world.globals.army_count) if i != 255]
    actual_army_indices = [army.army_index for army in world.armies]
    if actual_army_indices != expected_army_indices:
        raise ValueError(
            f"armies must cover exactly army_index 0..army_count-1 (skipping 255) in order; "
            f"expected {len(expected_army_indices)} entries, got {len(actual_army_indices)}"
        )
    for army in world.armies:
        _write_army(w, army)

    for discovery in world.discoveries:
        _check_not_sentinel(discovery.feature_id, "discovery feature_id")
        w.u8(discovery.feature_id)
        w.s16(discovery.legacy_word)
    w.sentinel(_SENTINEL_END)

    for field_name, size in XK_PLAYER_TAIL_FIELDS_BEFORE_RELATIONS:
        raw = world.player_tail[field_name]
        if len(raw) != size:
            raise ValueError(f"player_tail[{field_name!r}] must be exactly {size} bytes")
        w.bytes_(raw)
    if len(world.diplomatic_relations) != 12:
        raise ValueError("diplomatic_relations must have exactly 12 entries")
    for relation in world.diplomatic_relations:
        w.u8(relation.value)
    for field_name, size in XK_PLAYER_TAIL_FIELDS_AFTER_RELATIONS:
        raw = world.player_tail[field_name]
        if len(raw) != size:
            raise ValueError(f"player_tail[{field_name!r}] must be exactly {size} bytes")
        w.bytes_(raw)
    w.s16(world.account_number)
    w.s16(world.met_kings_bitmask_low)
    for field_name, size in XK_PLAYER_TAIL_FIELDS_TRAILING:
        raw = world.player_tail[field_name]
        if len(raw) != size:
            raise ValueError(f"player_tail[{field_name!r}] must be exactly {size} bytes")
        w.bytes_(raw)

    w.sentinel(_TAG_TR_END & 0xFF)
    w.sentinel(_TAG_TR_END >> 8)

    expected_cells = [
        (x, y)
        for x in range(world.globals.board_left, world.globals.board_right + 1)
        for y in range(world.globals.board_top, world.globals.board_bottom + 1)
    ]
    cells_by_coord = {(cell.coord.x, cell.coord.y): cell for cell in world.recruitment_map}
    if set(cells_by_coord) != set(expected_cells) or len(cells_by_coord) != len(world.recruitment_map):
        raise ValueError("recruitment_map must have exactly one entry per board cell within the globals' own bounds")
    for x, y in expected_cells:
        cell = cells_by_coord[(x, y)]
        w.u8(ARMY_TYPE_TO_MOD_PAT_ORDINAL.get(cell.recruit_type_1, _NO_ARMY_TYPE_ORDINAL) if cell.recruit_type_1 else _NO_ARMY_TYPE_ORDINAL)
        w.u8(ARMY_TYPE_TO_MOD_PAT_ORDINAL.get(cell.recruit_type_2, _NO_ARMY_TYPE_ORDINAL) if cell.recruit_type_2 else _NO_ARMY_TYPE_ORDINAL)

    if world.liege_extension is not None:
        w.u16(_TAG_TR_LLS)
        for leader_id, lliege in world.liege_extension.liege_by_leader_id.items():
            if leader_id == _TR_LLS_END:
                raise ValueError(f"TR_LLs leader_id {leader_id:#x} collides with its own list-end sentinel")
            w.u8(leader_id)
            w.u8(lliege)
        w.sentinel(_TR_LLS_END)

    if world.secondary_abilities is not None:
        w.u16(_TAG_TR_SA)
        flat = [value for levels in world.secondary_abilities.levels_by_ability for value in levels]
        if len(flat) != 90:
            raise ValueError("secondary_abilities must flatten to exactly 90 bytes")
        w.bytes_(bytes(flat))

    if world.secondary_terrain is not None:
        w.u16(_TAG_TR_T2)
        if len(world.secondary_terrain.raw) != 450:
            raise ValueError("secondary_terrain.raw must be exactly 450 bytes")
        w.bytes_(world.secondary_terrain.raw)

    if world.home_kingdom is not None:
        w.u16(_TAG_TR_HK)
        w.u8(world.home_kingdom.king_leader_id)
        if len(world.home_kingdom.shield_record) != 190:
            raise ValueError("home_kingdom.shield_record must be exactly 190 bytes")
        w.bytes_(world.home_kingdom.shield_record)

    w.u16(_TAG_TR_END)

    return w.getvalue()
