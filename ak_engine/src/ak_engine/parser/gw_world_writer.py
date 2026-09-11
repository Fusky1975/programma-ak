"""Writer for the original engine's "world file" format -- the inverse of
``parser/gw_world.py``'s seven confirmed reader record types
(``GWHeader``, ``GWProvinceRecord``, ``GWLeaderRecord``, ``GWFeatureRecord``,
``GWTreasureOnlyRecord``, ``GWArmyRecord``,
``GWOfficeMeritRecord``/``GWOfficeStateEntry``).

**Scope, Phase 374.** One writer function per confirmed record type, each
the exact byte-shape inverse of its own reader function -- verified by a
real round trip (write, then feed the written text back through the
matching ``parse_gw_*`` function, then assert the records compare equal)
rather than merely "looks plausible." `parse_gw_world`'s own province
regex (``_PROVINCE_HEADER_RE``, Phase 373) requires single-space-separated
tokens, so every writer here uses single spaces throughout, even where a
real Pascal-generated file shows irregular spacing (e.g. the module
docstring's own quoted Macondo record has a doubled space before a
province's second recruit-type token, ``" 3 0  15 0"``) -- reproducing
that exact irregular spacing isn't attempted, since no reader in this
project depends on it (`_parse_recruit_types` already just calls
``line3.split()``). This makes every writer here **data-exact**, not
byte-for-byte whitespace-exact, against a real file.

**What this phase deliberately does NOT cover**, because the reader
itself doesn't parse it yet (see `gw_world.py`'s own Phase 316-329
addenda) -- writing a "complete" file that the original engine could load
isn't attempted, and shouldn't be assumed possible from this module alone:

- The kingdom-level 33-field header that appears once per kingdom, before
  that kingdom's King's own record (Phase 318/321) -- distinct from
  `GWHeader`, the single whole-file header this module's own
  `write_gw_header` does cover.
- A leader's own ``"Action Plans:"`` block(s) -- real, and already
  parseable by `parser/k1_moves.py`'s own grammar, but not embedded by
  either the reader or this writer.
- The King-only Title/Epithet/player-name lines -- still real, still
  unparsed by any reader in this project. `write_gw_leader_record` below
  writes only a leader's confirmed base 3-line record (name / skill list
  / 25-field header) for both Kings and Heroes; a written King record is
  real and round-trips through `parse_gw_leaders`, but is not a complete
  King record the way a written Hero record is a complete Hero record.
  **Phase 380 correction**: the King-only Gender line and trailing
  dynamic-state block, previously listed here as uncovered, are now
  fully decoded (`GWKingExtension`/`parse_gw_king_extensions`/
  `write_gw_king_extension`, see `gw_world.py`'s own Phase 380
  addendum) -- removed from this exclusion list.
**Phase 375 correction -- the "15 `(min, max)` pairs" list is NOT a
separate excluded block.** An earlier draft of this docstring listed it
as one more not-yet-covered piece, carried over from Phase 321's own
still-open "kingdom-specific list" framing. Phase 325 (see
`gw_world.py`'s own addendum) already resolved that same list as the
leader's own doubled/single 15-`(skill_level, aptitude)`-pair skill
table -- exactly `GWLeaderRecord.skills`/`SkillTable`, which `write_gw_
leader_record` already writes (doubled for a King, single for a Hero).
There was never a second, still-missing "kingdom-specific" list; Phase
321's own "kingdom's own name" framing was itself later corrected (Phase
326) to just be the King's own name opening that kingdom's block.

**A leader header line's own 3 trailing tokens (positions 22-24 of 25)**
are never populated by `GWLeaderRecord` -- `parse_gw_leaders`/
`_build_leader_record` only ever reads positions 0-21 into named fields,
leaving those 3 undiscovered. `write_gw_leader_record` writes them as
literal ``0`` -- an honest placeholder, not a guessed real value (this
project's own "missing data defaults to neutral, not guessed" convention,
already used by `turn/aftermath.py roll_quality_change`'s own `score`
parameter, Phase 372). A round-tripped leader record is therefore
guaranteed equal on every field `GWLeaderRecord` actually models, but a
freshly-written record's own raw positions 22-24 will not match a real
file's own original values there.

**Phase 376 -- `write_gw_army_record` now writes `GWArmyRecord`'s own
`state`/`movement_points`/`death_or_transformation_marker`/`plague_
survival_count` fields directly** (see `gw_world.py`'s own Phase 376
addendum on `GWArmyRecord` for the full field-by-field derivation from
`AKGEN_embedded_catalogs.json.txt`'s own `gw_format.records.army.
ordered_storage`), superseding the earlier `raw_field7`-`raw_field10`
placeholder names this writer used before that record type was decoded
further.
"""

from __future__ import annotations

from ak_engine.models.alignment import ALIGNMENT_ORDINAL
from ak_engine.models.army_type import ArmyType
from ak_engine.models.discovery import Discovery
from ak_engine.parser.gw_world import (
    MOD_PAT_ORDINAL_TO_ARMY_TYPE,
    GWArmyRecord,
    GWFeatureRecord,
    GWHeader,
    GWKingExtension,
    GWLeaderRecord,
    GWOfficeMeritRecord,
    GWOfficeStateEntry,
    GWProvinceRecord,
    GWTreasureOnlyRecord,
)

# The inverse of `gw_world.MOD_PAT_ORDINAL_TO_ARMY_TYPE` -- every value in
# that table is a distinct `ArmyType` (or `None`, handled separately by
# each writer below via the real `15` "no type" sentinel), so this
# reversal is unambiguous.
ARMY_TYPE_TO_MOD_PAT_ORDINAL: dict[ArmyType, int] = {
    army_type: ordinal for ordinal, army_type in MOD_PAT_ORDINAL_TO_ARMY_TYPE.items() if army_type is not None
}

# The real "no second recruit type"/"no army type" sentinel ordinal --
# `MOD_PAT_ORDINAL_TO_ARMY_TYPE[15] is None`, see `gw_world.py`.
_NO_ARMY_TYPE_ORDINAL = 15

# The real "nobody"/"unowned" leader-id sentinel used throughout the
# world file (province governor, Block B `commanded_by_leader_id`, a
# leader header's own Liege field).
_NO_LEADER_SENTINEL = 255


def write_gw_header(header: GWHeader) -> str:
    """Writes a world file's own 33- (or 23-, if the extended fields are
    all absent) value header line -- the exact inverse of `parse_gw_
    header`.

    Raises `ValueError` if the extended fields are only *partially*
    populated: `GWHeader`'s own docstring documents them as an
    all-or-nothing block (present together from `header_revision > 17`
    onward, `None` together otherwise) -- a partial set can't be a real
    header and would silently write a malformed line if allowed through.
    """

    values: list[int] = [
        header.king_count,
        header.army_count,
        header.game_turn,
        header.raw_04,
        header.setup_fee_cents,
        header.treasure_count,
        header.feature_count,
        header.map_left_x,
        header.map_right_x,
        header.map_top_y,
        header.map_bottom_y,
        header.game_version,
        header.game_number,
        header.due_day,
        header.due_month,
        header.due_year,
        header.turn_length_days,
        header.diplomacy_type,
        header.header_revision,
        header.original_turn,
        header.turn_cost_cents,
        header.game_type.value,
        header.total_fees,
    ]

    extended = [
        header.last_leader_index,
        header.valhalla_alignment_rotation_mask,
        header.visiting_king,
        header.max_feature_index,
        header.setup_extra_1,
        header.office_merit_record_count,
        header.office_state_table_present,
        header.compatibility_revision_31,
        header.mine_write_flags,
        header.misc_write_flags,
    ]
    populated = [value is not None for value in extended]
    if all(populated):
        values.extend(value for value in extended if value is not None)
    elif any(populated):
        raise ValueError(
            "GWHeader's own extended fields (24-33) must be all-present or all-None, "
            "not a partial mix -- see GWHeader's own docstring"
        )

    return " ".join(str(value) for value in values)


def write_gw_province_record(record: GWProvinceRecord) -> str:
    """Writes one province's own 4-line record -- the exact inverse of
    the record shape `parse_gw_world` scans for (name line, 6-integer
    header line, 4-integer recruiting-types line, governor-id line).
    """

    header_line = " ".join(
        str(value)
        for value in (
            record.tax,
            record.terrain.value,
            record.effects_bitmask,
            record.race.value,
            record.exploitation_percent,
            record.alternate_terrain.value,
        )
    )

    type1_ord = _NO_ARMY_TYPE_ORDINAL if record.recruit_type_1 is None else ARMY_TYPE_TO_MOD_PAT_ORDINAL[record.recruit_type_1]
    type2_ord = _NO_ARMY_TYPE_ORDINAL if record.recruit_type_2 is None else ARMY_TYPE_TO_MOD_PAT_ORDINAL[record.recruit_type_2]
    recruit_line = f"{type1_ord} 0 {type2_ord} 0"

    governor_line = str(_NO_LEADER_SENTINEL if record.governor_leader_id is None else record.governor_leader_id)

    return "\n".join((record.name, header_line, recruit_line, governor_line))


def write_gw_leader_record(record: GWLeaderRecord) -> str:
    """Writes one King's or Hero's own base 3-line record (name / skill
    list / 25-field header) -- the exact inverse of the record shape
    `parse_gw_leaders` scans for. See this module's own docstring for
    what a King's record deliberately leaves out (Gender/Title/Epithet/
    player-name lines, the trailing ~128-token dynamic block) and for
    why header positions 22-24 are always written as `0`.

    A King's own record always doubles its 30-value skill list to 60
    (Phase 324/325) and always writes Liege `255` (a King has no liege
    above him, Phase 323/325) regardless of `record.kingdom_id` -- that
    field holds the King's *own* kingdom id for a King record, derived
    positionally by `parse_gw_leaders`, not a literal header token.
    """

    skill_tokens = [str(value) for value in record.skills.raw_values]
    skill_line = " ".join(skill_tokens + skill_tokens) if record.is_king else " ".join(skill_tokens)

    liege_raw = _NO_LEADER_SENTINEL if (record.is_king or record.kingdom_id is None) else record.kingdom_id

    header_values = [
        record.coord.x,
        record.coord.y,
        record.race.value,
        record.sex_raw,
        liege_raw,
        record.original_liege_raw,
        record.condition,
        record.birth_coord.x,
        record.birth_coord.y,
        ALIGNMENT_ORDINAL[record.alignment],
        record.temper.value,
        record.hiring_turn,
        record.general_merit,
        record.admiral_merit,
        record.defender_merit,
        record.feature_discoveries,
        record.discovery_points,
        record.white_magic_service_points,
        record.experience_progress,
        1 if record.sex_override_flag else 0,
        record.unpaid_blackmail_penalty_exponent,
        record.known_by_kings_mask,
        # Positions 22-24: never populated by GWLeaderRecord -- see this
        # module's own docstring.
        0,
        0,
        0,
    ]
    header_line = " ".join(str(value) for value in header_values)

    return "\n".join((record.name, skill_line, header_line))


def write_gw_king_extension(record: GWKingExtension) -> str:
    """Writes a King's own Gender + trailing dynamic-state line, plus
    the 3 short-string title/epithet/player-name lines that always
    immediately follow it (`GWKingExtension.title_prefix`/`title_
    suffix`/`player_name`, SS71.2) -- the exact inverse of `parse_gw_
    king_extensions`, in the confirmed field order `GWKingExtension`'s
    own docstring (Phase 380) lays out. Returns all 4 lines joined by
    `"\\n"` -- callers already join this module's own per-record output
    with `"\\n".join(...)` elsewhere (see `tests/test_gw_world_writer.py`),
    so embedding the newlines here keeps every one of those call sites
    unchanged. The diplomatic-relations count is taken from `len(record.
    diplomatic_relations)`, not passed separately, so this writer is
    self-contained -- a round trip only requires the header's own
    `king_count` to already match that length (`parse_gw_king_
    extensions` itself derives the count from `GWHeader.king_count`, so
    a mismatched write there would fail on re-parse, the same
    "malformed input surfaces as a parse error" contract every other
    writer in this module already follows).
    """

    discovered_flags = [1 if Discovery(index) in record.discovered else 0 for index in range(64)]
    values = [
        record.treasury,
        record.alliance_requests_bitmask,
        record.break_treaty_requests_bitmask,
        record.account_number,
        record.player_mode,
        record.met_kings_bitmask,
        record.send_method.value,
        record.election_request_or_previous_choice,
        record.payment_percent,
        record.miscellaneous_fee,
        record.turn_funds_received,
        record.consecutive_missed_turns,
        record.standby_state.value,
        record.standby_max_percent,
        record.prize_credit,
        record.raw_administrative_flag,
        1 if record.moves_read_success else 0,
        record.order_interpreter_version,
        *(relation.value for relation in record.diplomatic_relations),
        *discovered_flags,
        record.valhalla_visit_count,
        record.king_information_flags,
        record.disk_delivery_flags,
        record.king_power_or_votes_cast,
        1 if record.moves_insurance else 0,
        record.team_state,
        _NO_LEADER_SENTINEL if record.active_blackmailer_king_id is None else record.active_blackmailer_king_id,
        _NO_LEADER_SENTINEL if record.pending_blackmailer_king_id is None else record.pending_blackmailer_king_id,
        record.power_percent,
        *record.trailing_compatibility_zeros,
    ]
    gender_token = "M" if record.is_male else "F"
    extension_line = " ".join((gender_token, *(str(value) for value in values)))
    return "\n".join((extension_line, record.title_prefix, record.title_suffix, record.player_name))


def write_gw_feature_record(record: GWFeatureRecord) -> str:
    """Writes one Feature instance's own 9-integer Block A row -- the
    exact inverse of `parse_gw_features`, in the confirmed field order
    `fx, fy, treaslist, trowner, trcharges, fmonst, ftype, fdis, fstate`.
    """

    return " ".join(
        str(value)
        for value in (
            record.coord.x,
            record.coord.y,
            record.treasure.value,
            record.trowner_raw,
            record.trcharges,
            record.monster.value,
            record.feature_type.value,
            record.fdis_raw,
            record.engagement_state.value,
        )
    )


def write_gw_treasure_only_record(record: GWTreasureOnlyRecord) -> str:
    """Writes one "loose" treasure's own 3-integer row -- the exact
    inverse of `parse_gw_treasures_only` (Phase 378).
    """

    return " ".join(str(value) for value in (record.treasure.value, record.owner_raw, record.charges))


def write_gw_army_record(record: GWArmyRecord) -> str:
    """Writes one army's own 10-integer Block B row -- the exact inverse
    of `parse_gw_armies`. `record.state` is written directly (Phase 376);
    `is_skeletal`/`is_mercenary` are derived, read-only convenience flags
    on `GWArmyRecord`, not independent data, so they aren't consulted
    here.
    """

    leader_id = _NO_LEADER_SENTINEL if record.commanded_by_leader_id is None else record.commanded_by_leader_id
    army_type_ord = _NO_ARMY_TYPE_ORDINAL if record.army_type is None else ARMY_TYPE_TO_MOD_PAT_ORDINAL[record.army_type]

    return " ".join(
        str(value)
        for value in (
            leader_id,
            record.coord.x,
            record.coord.y,
            record.race.value,
            army_type_ord,
            record.quality.value,
            record.state.value,
            record.movement_points,
            record.death_or_transformation_marker,
            record.plague_survival_count,
        )
    )


def write_gw_office_records(
    merit_records: list[GWOfficeMeritRecord],
    state_entries: list[GWOfficeStateEntry],
) -> str:
    """Writes the office-merit-record block (one 3-integer line per
    entry) followed by the fixed 156-integer office-state table -- the
    exact inverse of `parse_gw_offices`.

    `state_entries` must supply exactly one entry per `Office` ordinal
    0-51 (`parse_gw_offices`'s own real, confirmed shape) -- a missing
    ordinal raises `KeyError` rather than silently writing a short table,
    since a real world file's own office-state line is always fixed-
    length.
    """

    lines = [
        " ".join(str(value) for value in (record.office_code.value, record.leader_or_army_id, record.merit_points))
        for record in merit_records
    ]

    state_by_office = {entry.office.value: entry for entry in state_entries}
    state_tokens: list[str] = []
    for ordinal in range(52):
        entry = state_by_office[ordinal]
        # The real third field of each triplet is a confirmed, always-0
        # literal that GWOfficeStateEntry doesn't expose -- see its own
        # docstring.
        state_tokens.extend((str(entry.previous_holder_raw), str(entry.known_by_kings_mask), "0"))
    lines.append(" ".join(state_tokens))

    return "\n".join(lines)
