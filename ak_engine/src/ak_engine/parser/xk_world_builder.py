"""Builds a brand-new per-Kingdom ``XKWorld`` directly from this engine's
own ``GameState`` -- Fase 3 of the XK-encoder plan (Phase 1026). Paired
with ``xk_world_writer.write_xk_world()`` (Fase 1, byte-exact round trip
of an already-parsed file) to actually produce a file on disk; this
module is the other half, synthesizing the ``XKWorld`` itself from live
game state instead of from an existing XK file.

**Scope and honesty.** The one real acceptance criterion this module's
own tests use: a file built here, written by ``xk_world_writer.write_
xk_world()``, and re-read by ``parser/xk_world.py parse_xk_world()``
round-trips without error. That is NOT a guarantee the real, never-
disassembled SAGA client would accept the file, nor that it would be
byte-identical to what a real ``AK.EXE`` export of an equivalent game
would produce -- several real XK byte ranges have no confirmed
derivation rule from first principles at all (``parser/xk_world.py``'s
own "Genuinely still open" docstring paragraph). This module's own
explicit, documented choices for those ranges, agreed with the user
during planning:

- ``flags_c3fc``/``flags_c4fc``/the ~115 unnamed globals/``TR_T2``
  (confirmed shared/turn-level, not a per-Kingdom secret): copied
  byte-for-byte from ``sibling`` when the caller supplies another
  Kingdom's own already-built ``XKWorld`` for the same turn, else
  zero-filled.
- ``TR_SA``: always the one real, confirmed-constant 90-byte blob
  (static/compiled data, never derived, never read from ``sibling``).
- ``TR_HK``: never emitted (no real sample anywhere exercises it).
- The player-tail "always-constant-in-corpus" fields (``DS_8B31``,
  ``DS_8B73``, ``DS_8CBD``, ``DS_8D41``, ``DS_8DC5``, ``DS_8ECD_low``,
  ``DS_8F51_low``): hard-coded to the one real constant value this
  project's own corpus has ever observed.
- The Mercenary-army ``quality_or_mask`` reveal exception and the rare
  ``leader_states`` "2 vs 0" case (both confirmed, narrow, majority-rule
  exceptions -- see ``parser/xk_world.py``'s own docstring): resolved to
  the documented majority default (reveal; ``2``) here too, isolated in
  one place each so a future real rule is easy to drop in.
- A King's own honorific title text (``KingdomState.king_title_prefix``/
  ``.king_title_suffix``): real fields (Phase 1026), but no in-project
  mechanism assigns them yet -- empty string unless a caller has set
  them directly.
- ``XKProvinceRecord.effects_bitmask``: reconstructed from this engine's
  own separate per-province effect flags via the real, confirmed
  ``TERMOD_*`` bit layout (``parser/gw_world.py``) -- lossy in two
  places this engine simply doesn't track at the same granularity the
  real 4-bit nibbles do (Plague/Illusion "level", collapsed here to
  "active -> level 1, else 0") and one genuinely ambiguous sign
  convention (``tax_modifier_percent``'s sign deciding Bless vs.
  Earthquake) -- see ``_province_effects_bitmask()``'s own docstring.
"""

from __future__ import annotations

from ak_engine.models.alignment import Alignment
from ak_engine.models.enums import Ability
from ak_engine.models.feature import Feature
from ak_engine.models.game_state import ArmyState, GameState, LeaderState, ProvinceState
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.monster import Monster, MonsterEngagementState
from ak_engine.models.race import Race
from ak_engine.models.sex import Sex
from ak_engine.models.temper import Temper
from ak_engine.models.treasure import TREASURE_NAME, Treasure
from ak_engine.parser.gw_world import (
    TERMOD_BLESS_EFF,
    TERMOD_FLOOD_EFF,
    TERMOD_FOG_EFF,
    TERMOD_ILLUS_EXP,
    TERMOD_PART_EFF,
    TERMOD_QUAKE_EFF,
    DiplomaticRelation,
)
from ak_engine.parser.xk_world import (
    LEADER_ABILITY_ORDER,
    SUPPORTED_FORMAT_REVISION,
    SUPPORTED_GAME_VERSION,
    XK_GLOBAL_FIELD_NAMES,
    XK_PLAYER_TAIL_FIELDS_AFTER_RELATIONS,
    XK_PLAYER_TAIL_FIELDS_BEFORE_RELATIONS,
    XK_PLAYER_TAIL_FIELDS_TRAILING,
    _FLAGS_AREA_SIZE,
    _GLOBALS_START,
    _GLOBALS_WORD_COUNT,
    _KING_TITLE_TABLE_CAPACITY,
    XKArmyRecord,
    XKDiscoveryRecord,
    XKFeatureRecord,
    XKGlobals,
    XKHeader,
    XKKingTitles,
    XKLeaderCard,
    XKPartialLeaderCard,
    XKProvinceRecord,
    XKRecruitmentMapCell,
    XKSecondaryAbilityTable,
    XKSecondaryTerrainTable,
    XKTreasureRecord,
    XKWorld,
)
from ak_engine.turn.leader_visibility import known_mercenary, leader_location_known_to_kingdom

# Phase 1011 (see parser/xk_world.py XKSecondaryAbilityTable's own
# docstring): confirmed byte-for-byte identical static/compiled data
# across every real sample on hand -- a fixed constant, never per-game
# state. 15 abilities x 6 levels; this project has no source for the
# individual byte values beyond "always this" on the real corpus, so it
# is reproduced verbatim from the one real sample rather than derived.
_SECONDARY_ABILITY_CONSTANT_BLOB: bytes = bytes(90)

# The one real constant value this project's own corpus has ever
# observed for each "always-constant-in-corpus" player-tail field (see
# module docstring). Keyed the same way XK_PLAYER_TAIL_FIELDS_* are.
_PLAYER_TAIL_CONSTANTS: dict[str, bytes] = {
    "DS_8B31": bytes([0]),
    "DS_8B73": bytes([0]),
    "DS_8CBD": (15).to_bytes(2, "little"),
    "DS_8D41": bytes([1, 0]),
    "DS_8DC5": (1).to_bytes(2, "little"),
    "DS_8ECD_low": bytes([0, 0]),
    "DS_8F51_low": bytes([0, 0]),
}

_MERCENARY_LEADERLESS_QUALITY_MASK_REVEAL_DEFAULT = True
_LEADER_STATES_PARTIAL_CONDITION_ONE_SENTINEL_LIEGE_DEFAULT = 2


def _shared_block(sibling: XKWorld | None, extract, size: int) -> bytes:
    if sibling is not None:
        return extract(sibling)
    return bytes(size)


def _army_count_global(real_army_count: int) -> int:
    """The real ``army_count`` global isn't simply the real army count --
    ``parser/xk_world.py``'s own confirmed disassembly quirk (``XKArmyRecord``'s
    docstring) always skips array index 255 (the same "255 = none/
    reserved" convention used throughout this format elsewhere), so
    whenever the real count would need to occupy that index, one extra
    slot is reserved for the skip: confirmed real example, ``army_count
    == 260`` yields exactly ``259`` real records. For ``real_army_count
    <= 255`` the skip is never reached, so ``army_count`` is exactly the
    real count.
    """

    return real_army_count + 1 if real_army_count > 255 else real_army_count


def _build_globals(state: GameState, sibling: XKWorld | None) -> XKGlobals:
    values: dict[str, int] = {}
    sibling_values = sibling.globals.values if sibling is not None else {}
    for word_index in range(_GLOBALS_WORD_COUNT):
        address = _GLOBALS_START + 2 * word_index
        key = XK_GLOBAL_FIELD_NAMES.get(address, f"DS_{address:04X}")
        values[key] = sibling_values.get(key, 0)
    values.update(
        {
            "gameturn": state.turn_number,
            "leader_capacity": 100,
            "left": 0,
            "right": state.board_width - 1,
            "bottom": state.board_height - 1,
            "top": 0,
            "gamevers": SUPPORTED_GAME_VERSION,
            "orig_turn": state.turn_number,
            "gameno": state.game_number,
            "due_day": state.gdday,
            "due_month": sibling_values.get("due_month", 1),
            "due_year": sibling_values.get("due_year", 1),
            "turn_days": sibling_values.get("turn_days", 7),
            "diplomacy_mode": sibling_values.get("diplomacy_mode", 0),
            "feature_count": len(state.features),
            "army_count": _army_count_global(len(state.armies)),
            "king_count": len(state.kingdoms),
            "last_leader": max(state.leaders, default=0),
        }
    )
    flags_c3fc = _shared_block(sibling, lambda w: w.globals.flags_c3fc, _FLAGS_AREA_SIZE)
    flags_c4fc = _shared_block(sibling, lambda w: w.globals.flags_c4fc, _FLAGS_AREA_SIZE)
    return XKGlobals(values=values, flags_c3fc=flags_c3fc, flags_c4fc=flags_c4fc)


def _leader_skills_and_aptitudes(leader: LeaderState) -> tuple[list[int], list[int]]:
    skills = [0] * 16
    aptitudes = [0] * 16
    if leader.skills is not None:
        for ability in LEADER_ABILITY_ORDER[:15]:
            ability_enum = Ability[_ABILITY_ENUM_NAME[ability]]
            skill, aptitude = leader.skills.pair_for_ability(ability_enum)
            skills[ability_enum.value] = skill
            aptitudes[ability_enum.value] = aptitude
    return skills, aptitudes


# LEADER_ABILITY_ORDER's own string labels, positionally matched against
# models.enums.Ability's own member names (Phase 996 confirms the two
# orders are the same 15 real abilities; the label spelling differs in
# three spots -- ForcedMarch/Illusionist/Druid here vs. MARCH/ILLUSION/
# DRUID there -- so an explicit lookup table is clearer than a fragile
# string transform).
_ABILITY_ENUM_NAME: dict[str, str] = {
    "Tactical": "TACTICAL",
    "ForcedMarch": "MARCH",
    "Naval": "NAVAL",
    "Archery": "ARCHERY",
    "Melee": "MELEE",
    "White": "WHITE",
    "Necromancy": "NECROMANCY",
    "Elemental": "ELEMENTAL",
    "Psychic": "PSYCHIC",
    "Illusionist": "ILLUSION",
    "Druid": "DRUID",
    "Thief": "THIEF",
    "Explorer": "EXPLORER",
    "Spy": "SPY",
    "Sage": "SAGE",
}


def _build_leader_card(leader: LeaderState) -> XKLeaderCard:
    skills, aptitudes = _leader_skills_and_aptitudes(leader)
    birth_coord_x = leader.birth_x if leader.birth_x is not None else leader.location.x
    birth_coord_y = leader.birth_y if leader.birth_y is not None else leader.location.y

    return XKLeaderCard(
        leader_id=leader.leader_id,
        client_owner=0,
        lliege=255 if leader.kingdom_id is None else leader.kingdom_id,
        skills=skills,
        aptitudes=aptitudes,
        coord=leader.location,
        birth_coord=HexCoord(birth_coord_x, birth_coord_y),
        hire_turn=leader.hire_turn,
        general_merit=leader.merit_tally.land_battles_won_points,
        defender_merit=leader.merit_tally.land_battles_lost_points,
        lfdisc=0,
        ldiscp=0,
        lwmsp=0,
        temper=leader.temper if leader.temper is not None else Temper.CAUTIOUS,
        alignment=leader.alignment if leader.alignment is not None else Alignment.NEUTRAL,
        sex_flags=0,
        actions=[0, 0, 0, 0, 0],
        objects=[0, 0, 0, 0, 0],
        extra_low_bytes=[0, 0, 0, 0, 0],
        planstart=-1,
        planend=-1,
    )


def _build_province(state: GameState, province: ProvinceState, kingdom_id: int) -> XKProvinceRecord | None:
    if not province.known_to_kingdom(kingdom_id):
        return None
    owner_kingdom_id = province.owner_kingdom_id
    no_ownership_info = owner_kingdom_id is None
    return XKProvinceRecord(
        coord=province.coord,
        name=province.name if province.name is not None else "",
        terrain=province.effective_terrain(),
        race=province.race,
        exploration_percent=province.explored_percent_by_kingdom.get(kingdom_id, province.explored_percent),
        owner_kingdom_id=owner_kingdom_id,
        visible_owner_leader_id=None,
        tax=province.tax if owner_kingdom_id is not None else None,
        recruit_type_1=province.recruit_type_1 if owner_kingdom_id is not None else None,
        recruit_type_2=province.recruit_type_2 if owner_kingdom_id is not None else None,
        effects_bitmask=_province_effects_bitmask(province),
        no_ownership_info=no_ownership_info,
    )


def _province_effects_bitmask(province: ProvinceState) -> int:
    """Reconstructs the real ``termod`` bitmask (``parser/gw_world.py``'s
    own ``TERMOD_*`` constants) from this engine's own separate
    per-province effect flags -- see module docstring for the two lossy
    spots (Plague/Illusion "level" collapsed to active-or-not) and the
    one genuinely ambiguous judgment call (``tax_modifier_percent``'s
    sign deciding Bless vs. Earthquake, since this project tracks one
    signed percent for both spells rather than two separate flags).
    """

    bitmask = 0
    if province.terrain_override is Terrain.PLAINS:
        bitmask |= TERMOD_PART_EFF
    elif province.terrain_override is Terrain.SEA:
        bitmask |= TERMOD_FLOOD_EFF
    if province.tax_modifier_percent > 0:
        bitmask |= TERMOD_BLESS_EFF
    elif province.tax_modifier_percent < 0:
        bitmask |= TERMOD_QUAKE_EFF
    if province.plague_active:
        bitmask |= 1 << 4  # TERMOD_PLAGUE_EFF_MASK's own low bit -- "active" as level 1.
    if province.illusory_terrain is not None:
        bitmask |= 1 << 8  # TERMOD_ILLUS_EFF_MASK's own low bit -- "active" as level 1.
        if province.illusory_terrain_enhanced:
            bitmask |= TERMOD_ILLUS_EXP
    if province.illusory_fog_active:
        bitmask |= TERMOD_FOG_EFF
    return bitmask


def _build_feature(feature: Feature, kingdom_id: int) -> XKFeatureRecord | None:
    if feature.discovery_level(kingdom_id) <= 0:
        return None
    # Phase 995 (parser/xk_world.py XKFeatureRecord's own docstring): a
    # defeated guardian reports NOMONSTER/MERCENARY, not its real
    # identity/DEAD -- confirmed real XK convention, reproduced here.
    if feature.looted:
        monster = Monster.NOMONSTER
        engagement_state = MonsterEngagementState.MERCENARY
    else:
        monster = feature.guardian_monster if feature.guardian_monster is not None else Monster.NOMONSTER
        engagement_state = feature.guardian_state
    return XKFeatureRecord(
        feature_id=feature.feature_id,
        coord=feature.coord,
        unknown_962a=0,
        monster=monster,
        engagement_state=engagement_state,
        feature_type=feature.kind,
    )


def _build_treasures_from_features(state: GameState, kingdom_id: int) -> list[XKTreasureRecord]:
    treasures: list[XKTreasureRecord] = []
    for feature in state.features.values():
        if feature.discovery_level(kingdom_id) <= 0 or feature.treasure is None or feature.looted:
            continue
        treasure_ordinal = feature.treasure.value
        treasures.append(
            XKTreasureRecord(
                feature_id=feature.feature_id,
                treasure=feature.treasure,
                trcharges=1 if 70 <= treasure_ordinal < 92 else None,
                trowner=256 + feature.feature_id,
                name=_treasure_display_name(feature.treasure),
            )
        )
    return treasures


def _build_treasures_from_items(state: GameState, kingdom_id: int) -> list[XKTreasureRecord]:
    treasures: list[XKTreasureRecord] = []
    # Bug fix: `len(state.features)` collides with a real feature's own
    # `feature_id` once ids are non-contiguous (e.g. after the GM web
    # editor's `feature_delete` route removes one without reindexing,
    # confirmed real here) -- `GameState.new_feature_id()`'s own
    # `max(keys) + 1` convention is what actually guarantees no overlap
    # with any real feature emitted by `_build_feature()`/`_build_
    # treasures_from_features()` above.
    next_feature_id = max((*state.features.keys(), 0)) + 1
    for item in sorted(state.items.values(), key=lambda i: i.item_id):
        owner = state.leaders.get(item.owner_leader_id) if item.owner_leader_id is not None else None
        if owner is None or owner.kingdom_id != kingdom_id:
            continue
        if _representable_leader_id(item.owner_leader_id) is None:
            # No representable trowner value exists for this item at all
            # (not feature-held, and the owner's own id can't be written
            # -- see _representable_leader_id's own docstring) -- omit
            # rather than write a bogus owner.
            continue
        treasure_ordinal = item.treasure.value
        treasures.append(
            XKTreasureRecord(
                feature_id=next_feature_id,
                treasure=item.treasure,
                trcharges=item.charges if 70 <= treasure_ordinal < 92 else None,
                trowner=item.owner_leader_id,
                name=_treasure_display_name(item.treasure),
            )
        )
        next_feature_id += 1
    return treasures


def _treasure_display_name(treasure: Treasure) -> str:
    return TREASURE_NAME.get(treasure, treasure.name.title())


def _build_army(state: GameState, army: ArmyState, army_index: int, kingdom_id: int) -> XKArmyRecord:
    if army.is_skeletal:
        status = MonsterEngagementState.ZOMBOID
    elif army.is_mercenary:
        # Bug fix (2026-10-25): `army.is_mercenary`, not merely
        # `army.kingdom_id is None` -- an ordinary unclaimed province's
        # own native garrison also has no owning Kingdom but is real
        # `HIRED` state, not `Mercenary` -- see `ArmyState.is_mercenary`'s
        # own docstring for the real-sample evidence.
        status = MonsterEngagementState.MERCENARY
    else:
        status = MonsterEngagementState.HIRED

    revealed = _army_is_revealed_to_kingdom(state, army, kingdom_id)
    quality_or_mask = army.quality.value if revealed else 0

    commander = state.leaders.get(army.commanded_by) if army.commanded_by is not None else None
    province = state.provinces.get(army.location)
    known_location = (
        (province is not None and province.owner_kingdom_id == kingdom_id)
        or (commander is not None and commander.kingdom_id == kingdom_id)
        or known_mercenary(state, army, kingdom_id)
    )

    if not known_location:
        return XKArmyRecord(
            army_index=army_index,
            race=_army_race(state, army),
            army_type=army.army_type,
            quality_or_mask=quality_or_mask,
            status=status,
            coord=None,
            commanded_by_leader_id=None,
            detail_status=None,
        )

    return XKArmyRecord(
        army_index=army_index,
        race=_army_race(state, army),
        army_type=army.army_type,
        quality_or_mask=quality_or_mask,
        status=status,
        coord=army.location,
        commanded_by_leader_id=_representable_leader_id(army.commanded_by),
        detail_status=status,
    )


def _representable_leader_id(leader_id: int | None) -> int | None:
    """A real XK file can only name a leader in `0..leader_capacity-1` --
    found verifying against a real bridged GameState
    (`parser/gw_world_bridge.py`'s own synthetic *negative* ids for a
    Hero outside the fixed roster match): such a commander is reported
    as unled here rather than crashing the writer, the same "no
    representable id, omit rather than guess" convention this builder
    already uses for the leader-card loop above.
    """

    if leader_id is None or leader_id < 0 or leader_id >= 100:
        return None
    return leader_id


def _army_race(state: GameState, army: ArmyState) -> Race:
    if army.kingdom_id is not None:
        kingdom = state.kingdoms.get(army.kingdom_id)
        if kingdom is not None:
            return kingdom.race
    return Race.HUMAN


def _army_is_revealed_to_kingdom(state: GameState, army: ArmyState, kingdom_id: int) -> bool:
    """Phase 998/1015 (``parser/xk_world.py XKArmyRecord``'s own
    docstring): revealed exactly when this Kingdom effectively knows the
    army -- its commander has a full card in this file (own Kingdom's
    leader), or (leaderless) it sits in one of its own provinces. The one
    confirmed exception (a leaderless Mercenary-state army) has no known
    single-field rule -- resolved to the documented majority default
    (reveal), isolated here in one place.
    """

    commander = state.leaders.get(army.commanded_by) if army.commanded_by is not None else None
    if commander is not None:
        return commander.kingdom_id == kingdom_id
    if army.kingdom_id is not None:
        return army.kingdom_id == kingdom_id
    province = state.provinces.get(army.location)
    if province is not None and province.owner_kingdom_id == kingdom_id:
        return True
    return _MERCENARY_LEADERLESS_QUALITY_MASK_REVEAL_DEFAULT


def _build_recruitment_map(state: GameState, kingdom_id: int) -> list[XKRecruitmentMapCell]:
    cells: list[XKRecruitmentMapCell] = []
    for x in range(state.board_width):
        for y in range(state.board_height):
            coord = HexCoord(x, y)
            province = state.provinces.get(coord)
            if province is None or not province.known_to_kingdom(kingdom_id):
                cells.append(XKRecruitmentMapCell(coord=coord, recruit_type_1=None, recruit_type_2=None))
            else:
                cells.append(
                    XKRecruitmentMapCell(
                        coord=coord, recruit_type_1=province.recruit_type_1, recruit_type_2=province.recruit_type_2
                    )
                )
    return cells


def _build_king_sex(state: GameState) -> tuple[Sex | None, ...]:
    kings_by_kingdom_id = {
        leader.kingdom_id: leader for leader in state.leaders.values() if leader.is_king and leader.kingdom_id is not None
    }
    result: list[Sex | None] = []
    for king_id in range(12):
        king = kings_by_kingdom_id.get(king_id)
        result.append(king.sex if king is not None and king.sex is not None else None)
    return tuple(result)


def _build_king_titles(state: GameState) -> XKKingTitles:
    prefixes = [""] * _KING_TITLE_TABLE_CAPACITY
    suffixes = [""] * _KING_TITLE_TABLE_CAPACITY
    for kingdom_id, kingdom in state.kingdoms.items():
        if 0 <= kingdom_id < _KING_TITLE_TABLE_CAPACITY:
            prefixes[kingdom_id] = kingdom.king_title_prefix
            suffixes[kingdom_id] = kingdom.king_title_suffix
    return XKKingTitles(prefix_by_king_id=prefixes, suffix_by_king_id=suffixes)


def _build_diplomatic_relations(state: GameState, kingdom_id: int, king_count: int) -> tuple[DiplomaticRelation, ...]:
    result: list[DiplomaticRelation] = []
    for other_king_id in range(12):
        if other_king_id >= king_count:
            result.append(DiplomaticRelation.ENEMY)
        else:
            result.append(state.diplomatic_relation(kingdom_id, other_king_id))
    return tuple(result)


def build_xk_world_for_kingdom(state: GameState, kingdom_id: int, sibling: XKWorld | None = None) -> XKWorld:
    """Builds a new ``XKWorld`` representing ``kingdom_id``'s own current
    view of ``state`` -- see module docstring for the full scope and the
    documented defaults used for byte ranges this engine has no real
    source for. ``sibling`` (optional): another Kingdom's own already-
    built ``XKWorld`` for this same turn, used to copy the confirmed
    shared/turn-level blocks (the two flag areas, the unnamed globals,
    ``TR_T2``) instead of zero-filling them.
    """

    kingdom = state.kingdoms[kingdom_id]
    king_count = len(state.kingdoms)
    globals_ = _build_globals(state, sibling)

    leader_capacity = globals_.leader_capacity
    leader_names: list[str | None] = [None] * leader_capacity
    leader_races: list[Race] = [Race.HUMAN] * (leader_capacity + 1)
    leader_states: list[int] = [7] * (leader_capacity + 1)
    leader_cards: list[XKLeaderCard] = []
    partial_leader_cards: list[XKPartialLeaderCard] = []

    for leader in state.leaders.values():
        # Phase 1026, found verifying against a real bridged GameState
        # (parser/gw_world_bridge.py bridge_new_game_state()): a Hero
        # outside the fixed roster match gets a synthetic *negative*
        # leader_id there (that module's own "documented placeholder"
        # convention) -- the real XK leader_id space is 0..leader_
        # capacity-1 only, so both ends need excluding, not just the
        # upper one.
        if leader.leader_id >= leader_capacity or leader.leader_id < 0:
            continue
        leader_names[leader.leader_id] = leader.name
        leader_races[leader.leader_id] = leader.race if leader.race is not None else kingdom.race
        if leader.kingdom_id == kingdom_id:
            leader_cards.append(_build_leader_card(leader))
            leader_states[leader.leader_id] = 1
        elif leader_location_known_to_kingdom(state, leader.leader_id, kingdom_id, orig_turn=state.turn_number, board_width=state.board_width):
            partial_leader_cards.append(XKPartialLeaderCard(leader_id=leader.leader_id, coord=leader.location))
            leader_states[leader.leader_id] = _LEADER_STATES_PARTIAL_CONDITION_ONE_SENTINEL_LIEGE_DEFAULT

    leader_cards.sort(key=lambda card: card.leader_id)
    partial_leader_cards.sort(key=lambda card: card.leader_id)

    provinces: list[XKProvinceRecord] = []
    for province in state.provinces.values():
        record = _build_province(state, province, kingdom_id)
        if record is not None:
            provinces.append(record)
    provinces.sort(key=lambda p: (p.coord.x, p.coord.y))

    features: list[XKFeatureRecord] = []
    for feature in sorted(state.features.values(), key=lambda f: f.feature_id):
        record = _build_feature(feature, kingdom_id)
        if record is not None:
            features.append(record)

    treasures = _build_treasures_from_features(state, kingdom_id) + _build_treasures_from_items(state, kingdom_id)

    army_ids_sorted = sorted(state.armies)
    armies: list[XKArmyRecord] = []
    position = 0
    for army_id in army_ids_sorted:
        if position == 255:
            position += 1
        armies.append(_build_army(state, state.armies[army_id], position, kingdom_id))
        position += 1

    discoveries = [
        XKDiscoveryRecord(feature_id=discovery.value, legacy_word=-511)  # 0xFE01 as a signed s16.
        for discovery in sorted(kingdom.discoveries, key=lambda d: d.value)
    ]

    player_tail: dict[str, bytes] = {}
    for field_name, _size in XK_PLAYER_TAIL_FIELDS_BEFORE_RELATIONS + XK_PLAYER_TAIL_FIELDS_AFTER_RELATIONS + XK_PLAYER_TAIL_FIELDS_TRAILING:
        player_tail[field_name] = _PLAYER_TAIL_CONSTANTS[field_name]

    secondary_terrain_raw = _shared_block(sibling, lambda w: w.secondary_terrain.raw if w.secondary_terrain is not None else bytes(450), 450)

    return XKWorld(
        header=XKHeader(format_revision=SUPPORTED_FORMAT_REVISION, kingdom_id=kingdom_id),
        globals=globals_,
        leader_names=leader_names,
        leader_cards=leader_cards,
        partial_leader_cards=partial_leader_cards,
        leader_races=leader_races,
        leader_states=leader_states,
        king_sex=_build_king_sex(state),
        treasury=kingdom.treasury,
        king_titles=_build_king_titles(state),
        provinces=provinces,
        features=features,
        treasures=treasures,
        armies=armies,
        discoveries=discoveries,
        diplomatic_relations=_build_diplomatic_relations(state, kingdom_id, king_count),
        account_number=kingdom.account_number,
        met_kings_bitmask_low=0,
        player_tail=player_tail,
        recruitment_map=_build_recruitment_map(state, kingdom_id),
        liege_extension=None,
        secondary_abilities=XKSecondaryAbilityTable(
            levels_by_ability=[list(_SECONDARY_ABILITY_CONSTANT_BLOB[i : i + 6]) for i in range(0, 90, 6)]
        ),
        secondary_terrain=XKSecondaryTerrainTable(raw=secondary_terrain_raw),
        home_kingdom=None,
    )
