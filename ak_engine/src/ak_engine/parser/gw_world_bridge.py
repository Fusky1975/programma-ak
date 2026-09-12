"""Bridges `parser/gw_world.py`'s own file-order `GWProvinceRecord`s into
real `HexCoord`-keyed `ProvinceState`s (Phase 223).

**The coordinate mapping is empirically confirmed, not a guess.** A GW
world file's own province record carries no coordinate field (see
`gw_world.py`'s own module docstring) -- but real King's own turn-report
letters (`SE3__T1.K*`) print each province's real coordinate in their
ASCII map legend, as `"<Name>(<XXYY>)"` (e.g. `"Macondo(0205)"`, meaning
x=02, y=05, both 1-indexed). Collecting every such `(name, x, y)` triple
findable across all 9 of game 3's real turn-1 letters (63 provinces'
worth, after de-duplicating name variants) and checking each one against
its own position in `GW3__T1`'s own on-disk record order gives a **100%
exact match, zero mismatches**, under the hypothesis:

    x (1-indexed) = record_index // 9 + 1
    y (1-indexed) = record_index %  9 + 1

i.e. the file's own record order is column-major -- outer loop over `x`
(18 values, 1..18), inner loop over `y` (9 values, 1..9), 18 x 9 = 162,
matching the confirmed real province count exactly. This mirrors
`REPORTS.PAS Rep_Provs`'s own real iteration order verbatim (`FOR px:=
left TO right DO FOR py:= top TO bottom DO`, px/x outer, py/y inner) --
strong corroborating evidence the world file itself was written by the
same nested-loop traversal Rep_Provs later reads it with.

Converting to this project's own 0-indexed `HexCoord`, this collapses to
`HexCoord(record_index // 9, record_index % 9)` directly -- no offset
arithmetic needed.

**Not claimed to be a universal board size for every possible world** --
confirmed specifically for `GW3__T1` (this project's one available real
fixture). The 162-province total is stated to be a fixed rule (the
user's own words), and 18 x 9 = 162 exactly, so a fixed board size across
every world is plausible, but this hasn't been cross-checked against a
second real `GW*` file (e.g. `GW6`) -- a `height` parameter is exposed
below rather than hardcoding this as an unconditional constant.

**Phase 224 adds `resolve_province_owners()`**: `GWProvinceRecord.
governor_leader_id` is a leader id, not a kingdom id (see `gw_world.py`'s
own "Philo(70)" cross-check). Resolving it needs a `GameState` whose
`leaders` dict is already populated (e.g. via `turn/kingdom_bridge.py
sync_leaders_from_kingdom()` from the matching `AK3__T*.K1` files) --
this project's own already-established real King's-own-leader_id-equals-
kingdom_id convention means a King-governed province resolves directly,
while a Hero-governed province resolves via that Hero's own `LeaderState.
kingdom_id` (or stays unresolved if that Hero is an independent
Valhalla visitor with no kingdom, or simply isn't in `state.leaders` at
all -- e.g. because only a subset of kingdoms' move files were ever
bridged). Unresolvable records are left at `owner_kingdom_id = None`
rather than raising -- a partially-bridged `GameState` (not every
kingdom's `AK3__T*.K1` available) is an expected, ordinary case, not an
error condition.

**Phase 278** adds `recruit_type_1`/`recruit_type_2` to the fields this
function copies straight across from `GWProvinceRecord` -- see
`gw_world.py`'s own "Recruiting Types (Mod_PAT)" docstring section for
their derivation. No new logic needed here: like `tax` before them,
they're already fully decoded on the `GWProvinceRecord` this function
reads, so bridging them is a direct copy, not a new computation.

**Phase 338 addendum -- ``bridge_new_game_state()``, the first real
"populate a ``GameState`` from nothing" path.** Every bridge above this
point (and `turn/kingdom_bridge.py`'s own two sync functions) only ever
*enriches* `LeaderState`s that already exist in a caller-supplied
`GameState` -- there was no path from "just a `GW3` file" to a brand
new `GameState` with real `KingdomState`/`LeaderState`/`ArmyState`
entries. This addendum closes that gap for the part of it that's
actually recoverable from a single `GW3` file alone, and is explicit
about the part that isn't.

**Tested and confirmed possible, without guessing, for every King**:
Phase 330's own "a King's own `leader_id` equals his `kingdom_id`,
derived from file order" finding (confirmed 8-for-8 against real
letter ids) means a King's real numeric identity, race, alignment,
temper, skills, and current coordinate are all independently confirmed
data already sitting on his own `GWLeaderRecord` -- enough to build a
real `KingdomState` and `LeaderState` for him from nothing.

**Tested and confirmed NOT possible, for an arbitrary Hero, from a
single `GW3` file alone.** Before writing any code, two candidate
recovery techniques were tried against the real, committed `GW3__T1`
fixture and checked against five independently-confirmed real Hero
ids from earlier phases (Philo=70, Guerin=18, Teleko=72, Ningarl=13,
Kokocala=50):

- **Match a Hero's own `coord` against the province he governs**
  (`GWProvinceRecord.governor_leader_id`, filtered to exclude every
  King-owned province): works for Philo (a genuinely
  personally-governing Hero, the same case Phase 222's own original
  cross-check used) but fails for Kokocala -- her own coordinate
  (`HexCoord(11, 5)`) is shared with a *different* Hero (the real
  governor, id `10`) who isn't her. Multiple Heroes legitimately share
  one coordinate (a King's own capital, a staging army, ...), so
  "coordinate implies unique identity" is false in general.
- **Match a Hero's own `coord` against Block B's own
  `commanded_by_leader_id`** (a confirmed-real id whenever a row is
  led): recovers a candidate for 69 of 90 real `GW3__T1` Heroes by raw
  coordinate count, but Guerin/Teleko/Ningarl (all independently
  confirmed by name in earlier phases) return no match or the wrong
  one at their own coordinate, for the same reason -- shared
  coordinates at turn 1, before armies have dispersed.

Both techniques were falsified, not merely inconclusive -- there is no
general, reliable source for an arbitrary Hero's own real `leader_id`
inside a single `GW3` file. This matches (and empirically confirms,
rather than just repeats) what `turn/kingdom_bridge.py`'s own module
docstring already says about a `GWLeaderRecord` carrying no
`leader_id`.

**Resolution used here (confirmed with the user, 2026-08-01)**: every
King gets his own real, confirmed `leader_id`; every Hero gets a
synthetic id (negative, so it can never collide with any real id,
which are always non-negative in every sample seen) -- explicitly
documented as **not** the game's own internal id. Every other field on
a Hero's own `LeaderState` (name, race, alignment, temper, skills,
coord, and `kingdom_id` -- the Liege field, independently confirmed
27-for-27 in Phase 325/327) is real, not synthetic; only the numeric
identity itself is a placeholder, pending the real per-Hero id list the
user has said they'll supply. `apply_confirmed_hero_ids()` (below)
re-keys a Hero's `LeaderState` from its synthetic id to a real one once
supplied, and re-attempts bridging any Block-B army row that had to be
left out for exactly this reason (see `NewGameStateReport.
unresolved_army_records`'s own docstring).

**Why a Hero-led Block B army row is skipped, not bridged with a
guessed owner.** `ArmyState.kingdom_id`'s own docstring reserves `None`
specifically for "unowned mercenary" -- Phase 337's own confirmed
`is_mercenary` marker already uses it correctly for that real case, so
reusing `None` here for "owner genuinely unknown to us" would silently
conflict with that meaning for any caller checking "is this army
poachable". An unled row's real owner is always resolvable (the
province's own owner, via the exact same `resolve_province_owners()`
already used below); a King-led row's real owner is always resolvable
(the King's own confirmed id); a mercenary row's real owner is `None`
by definition. Only a Hero-led row has no confirmed source at all for
who it belongs to -- so it's left out of the freshly-built `GameState`
entirely and counted, not silently misattributed.

**Phase 339 addendum -- most of Phase 338's own "Hero id" gap closes
after all, via a fixed name roster rather than any per-game
technique.** The user supplied a project-original reference document
(`"Nomi (eroi) fino a #99.txt"`) listing all 98 Hero names this
project's own AK game series draws from, each with a fixed numeric id
and sex, independent of which particular game/world it is --
`models/hero_roster.py`'s own `STANDARD_HERO_ROSTER`. Verified against
the real `GW3__T1` fixture before relying on it: **88 of its own 90
Hero names match the roster exactly**, at unique ids all in the
`10-98` range (this is a 10-kingdom game, so Kings already occupy ids
`0-9` -- Phase 330 -- and the roster's own `1-9` slots, Adam through
Enlil, never get to appear as Heroes here). The 2 unmatched names
(`Bagmore`, `Kitralus`) are both real entries in the user's own
separate `VALHALLA NEUTRAL.txt` -- exactly the roster's own documented
`#99` "arrived via VALHALLA" case, not a data error.

`bridge_new_game_state()` now assigns a roster-matched Hero his own
real `leader_id` and `sex` directly (Phase 338's synthetic negative-id
scheme becomes the fallback for the residual, genuinely un-rostered
case only). Army bridging's own King-only check
(`commanded_by_leader_id in king_ids`) generalizes to `in leaders`,
since `leaders` now holds real ids for both Kings and roster-matched
Heroes -- a Hero-led Block B row bridges immediately whenever that
Hero's own name was in the roster, no longer deferred to
`apply_confirmed_hero_ids()` at all. That function remains the correct
path for the true residual case (a name the roster doesn't cover).

**Phase 723 addendum -- `bridge_gw_world_provinces()` now bridges
`pt2`/`GWProvinceRecord.alternate_terrain` (parsed since Phase 373, but
silently discarded here until now) into `ProvinceState.is_island`.**
Confirmed correct against the user's own two explicit calls this
session (2026-09-03): a record is treated as an Island only when its
own primary `terrain` is `Terrain.SEA` and `alternate_terrain` is not
`Terrain.NO_TERRAIN` -- consistent with this project's own already-
shipped convention (`ProvinceState.terrain` always holds the *land*
half, `is_island` flags a Sea half layered on top) -- in which case the
bridged `ProvinceState.terrain` becomes `alternate_terrain` (the real
land half) rather than the record's own `Terrain.SEA`. A record whose
primary terrain is NOT Sea but still carries a non-`NO_TERRAIN`
`alternate_terrain` (never observed in any real sample, and neither
`Desktop/PROGRAMMA AK/AKGEN_reverse_engineering_report.md:582-586` nor
`Desktop/PROGRAMMA AK/SCAR.md` describes this shape) is conservatively
left as NOT an island. Every real `GW3__T1`-`T12` sample on hand reads
`Terrain.NO_TERRAIN` for `alternate_terrain`, so this is a provable
no-op for every existing fixture -- see `tests/test_gw_world_bridge.py`'s
own synthetic (never-observed-in-real-data, explicitly labeled) test
cases for the actual island-bridging behavior.

**Phase 366 addendum -- `models/hero_roster.py` itself was rewritten**
from a real Pascal source (`LNAMES.PAS`, found by a later
reverse-engineering pass) rather than the project-original document
this addendum originally described. The re-verification against this
same `GW3__T1` fixture now finds **89 of 90** Hero names matching (not
88): `Bagmore`, previously attributed to a Valhalla arrival, turned out
to be a real roster entry the old hand-typed table simply had wrong at
its own id 75. Only `Kitralus` remains a genuine synthetic-id case --
see `models/hero_roster.py`'s own module docstring for the full
writeup.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from ak_engine.models.game_state import ArmyState, GameState, KingdomState, LeaderState, ProvinceState
from ak_engine.models.hero_roster import STANDARD_HERO_ID_BY_NAME, STANDARD_HERO_SEX_BY_NAME
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.monster import MonsterEngagementState
from ak_engine.parser.gw_world import DiplomaticRelation, GWArmyRecord, GWKingExtension, GWLeaderRecord, GWProvinceRecord

# Rows per column, confirmed for GW3__T1 (see module docstring). 18
# columns x 9 rows = 162, the confirmed real province count.
CONFIRMED_BOARD_HEIGHT = 9


def _coord_for_index(index: int, height: int) -> HexCoord:
    return HexCoord(index // height, index % height)


def bridge_gw_world_provinces(
    records: list[GWProvinceRecord], *, height: int = CONFIRMED_BOARD_HEIGHT
) -> dict[HexCoord, ProvinceState]:
    """Assigns each record its real, column-major `HexCoord` and builds a
    `GameState.provinces`-ready dict.

    Raises `ValueError` if `records` isn't an exact multiple of `height`
    long, the same sanity check `Rep_Provs`'s own confirmed rectangular
    board shape implies -- a partial last column would mean either a
    wrong `height` or a truncated/corrupted `records` list, not a
    silently-mappable state.
    """

    if height <= 0:
        raise ValueError(f"height must be > 0, got {height}")
    if len(records) % height != 0:
        raise ValueError(
            f"{len(records)} records isn't an exact multiple of height={height} "
            "-- wrong height, or a truncated/corrupted records list"
        )

    provinces: dict[HexCoord, ProvinceState] = {}
    for index, record in enumerate(records):
        coord = _coord_for_index(index, height)
        is_island = record.terrain is Terrain.SEA and record.alternate_terrain is not Terrain.NO_TERRAIN
        terrain = record.alternate_terrain if is_island else record.terrain
        provinces[coord] = ProvinceState(
            coord=coord,
            terrain=terrain,
            race=record.race,
            name=record.name,
            tax=record.tax,
            recruit_type_1=record.recruit_type_1,
            recruit_type_2=record.recruit_type_2,
            is_island=is_island,
        )
    return provinces


def resolve_province_owners(
    provinces: dict[HexCoord, ProvinceState],
    records: list[GWProvinceRecord],
    state: GameState,
    *,
    height: int = CONFIRMED_BOARD_HEIGHT,
) -> int:
    """Sets each bridged province's real `owner_kingdom_id`, resolved
    from its own `GWProvinceRecord.governor_leader_id` via `state.
    leaders` (see module docstring for exactly what "resolved" means for
    a King vs. a Hero vs. an unknown leader id).

    Mutates `provinces` in place (the same dict `bridge_gw_world_provinces()`
    returned, keyed the same way via `records`' own index order) and
    returns the count of provinces whose owner was actually resolved
    (found in `state.leaders`) -- not the count set to a non-`None`
    kingdom id, since a resolved independent Hero legitimately resolves
    to `None`.
    """

    resolved = 0
    for index, record in enumerate(records):
        if record.governor_leader_id is None:
            continue
        leader = state.leaders.get(record.governor_leader_id)
        if leader is None:
            continue
        province = provinces.get(_coord_for_index(index, height))
        if province is None:
            continue
        province.owner_kingdom_id = leader.kingdom_id
        resolved += 1
    return resolved


@dataclass(slots=True)
class NewGameStateReport:
    kings_created: int
    heroes_created: int
    provinces_created: int
    provinces_with_resolved_owner: int
    armies_created: int
    # A Hero whose own name matched `models/hero_roster.py`'s fixed
    # 98-entry table (Phase 339) -- his own `leader_id` is fully real,
    # not a placeholder. Maps name -> real id.
    heroes_with_confirmed_id: dict[str, int] = field(default_factory=dict)
    # A Hero whose own name did NOT match the roster (e.g. a VALHALLA
    # arrival, id `99`, not a specific named roster entry) -- assigned a
    # synthetic (negative) id instead. See module docstring's Phase 338
    # addendum. Maps name -> synthetic id.
    heroes_with_synthetic_id: dict[str, int] = field(default_factory=dict)
    # Block B rows led by a leader id this bridge couldn't resolve to any
    # `LeaderState` it built (i.e. a synthetic-id Hero, Phase 338's
    # residual case) -- their real owning kingdom has no confirmed
    # source, so they weren't bridged into `GameState.armies` at all.
    # Kept here so `apply_confirmed_hero_ids()` can retry them once a
    # real id is supplied for that specific Hero.
    unresolved_army_records: list[GWArmyRecord] = field(default_factory=list)
    # Block B rows whose own `state` field is `MonsterEngagementState.
    # DEAD` -- confirmed (Phase 789, cross-referencing `GW6` against the
    # full `GW3__T1`-`T12` corpus) to be genuine historical dead armies,
    # not live/garrison units: `death_or_transformation_marker` (for a
    # non-250/non-251 value) is the literal real game-turn the army
    # died, and `251` is a distinct, strictly append-only terminal/
    # archival marker. These rows are excluded from `GameState.armies`
    # entirely -- counted here rather than bridged with a guessed live
    # state. See `parser/gw_world.py GWArmyRecord`'s own Phase 789
    # addendum for the full finding, including the two still-open
    # questions (the exact removal-timing rule for a numbered-marker
    # row, and whether removal converts to `251` or frees the slot for
    # reuse).
    dead_army_records_excluded: int = 0


def bridge_new_game_state(
    leader_records: list[GWLeaderRecord],
    province_records: list[GWProvinceRecord],
    army_records: list[GWArmyRecord],
    *,
    turn_number: int = 1,
    height: int = CONFIRMED_BOARD_HEIGHT,
    hero_id_start: int = -1,
    king_extensions: list[GWKingExtension] | None = None,
) -> tuple[GameState, NewGameStateReport]:
    """Builds a brand-new `GameState` directly from a single `GW3` file's
    own three already-parsed record lists -- see module docstring's
    Phase 338/339 addenda for exactly what's real here and what's a
    documented placeholder.

    Every King's own `KingdomState`/`LeaderState` is fully real
    (`leader_id == kingdom_id`, Phase 330). Every Hero whose own name
    matches `models/hero_roster.py`'s fixed roster (Phase 339) also gets
    his own fully real `leader_id` and `sex`; a Hero outside that roster
    (a VALHALLA arrival) falls back to a synthetic, negative `leader_id`
    -- either way, name, race, alignment, temper, skills, coord, and
    kingdom_id/Liege are all real. Provinces reuse
    `bridge_gw_world_provinces()`/`resolve_province_owners()` unchanged.
    Armies bridge for every unled row (owner = the province's own
    resolved owner) and every row led by any leader this bridge gave a
    real id (King or roster-matched Hero, owner = that leader's own real
    `kingdom_id`); a row led by a still-synthetic-id Hero is left out
    and returned in the report instead of being bridged with a guessed
    owner. A row whose own `state` is `MonsterEngagementState.DEAD` is
    excluded entirely (Phase 789) -- confirmed a genuine historical dead
    army, not a live/garrison unit; see `NewGameStateReport.dead_army_
    records_excluded`'s own docstring for the full finding.

    **`king_extensions` (Phase 788, optional, default `None`)** --
    `parser/gw_world.py GWKingExtension`/`parse_gw_king_extensions()`
    (Phase 380) already parses every King's own treasury, Discovery set,
    diplomatic history and Valhalla-visit count from the same world
    file, but nothing threaded it into a bridged `GameState` until now.
    Confirmed safe to correlate positionally: `parse_gw_king_extensions()`
    scans the file for King-shaped records in the exact same order
    `parse_gw_leaders()` does (Phase 330's own "the Nth King-shaped
    record encountered is Kingdom N" finding), so `king_extensions[N]`
    is always Kingdom N's own record -- the same file, same scan order,
    same index. When given (and `len(king_extensions) > kingdom_id`),
    a King's own bridged `KingdomState` gets its real `treasury`,
    `discoveries` (the parsed `frozenset[Discovery]` copied into a
    `set`), and `valhalla_visit_count` -- directly, no computation.
    `GameState.kingdoms_met`/`allied_kingdoms` (both pair-based, not
    per-Kingdom) are populated from `met_kings_bitmask` (a real "have
    these two ever made contact" bit, independent of the *quality* of
    the relation) and from `diplomatic_relations` respectively --
    **alliance is bridged only when both sides' own recorded view of
    each other is `DiplomaticRelation.ALLIED`**, a deliberately
    conservative reading: `kallst` is a *directed*, per-King array (this
    King's own view of every other King), so a one-sided value could be
    a still-pending request rather than a real, accepted alliance --
    requiring mutual agreement avoids bridging a pending request as if
    it were the real thing. Every other `GWKingExtension` field
    (`team_state`, blackmail state, `kpower`/`powperc`, standby, ...)
    has no matching `GameState`/`KingdomState` concept to receive it yet
    (this project models no "Team" relation at all, and a real
    `BlackmailClaim` needs an `amount`/`spy_leader_id` neither `GW` field
    supplies) -- left unbridged rather than guessed, same as every other
    "no source, no guess" gap in this module.
    """

    kingdoms: dict[int, KingdomState] = {}
    leaders: dict[int, LeaderState] = {}
    heroes_with_confirmed_id: dict[str, int] = {}
    heroes_with_synthetic_id: dict[str, int] = {}
    king_ids: set[int] = set()

    next_hero_id = hero_id_start
    for record in leader_records:
        if record.is_king:
            king_id = record.kingdom_id
            assert king_id is not None  # a King's own kingdom_id is never None (Phase 330)
            king_ids.add(king_id)
            kingdom = KingdomState(
                kingdom_id=king_id,
                name=record.name,
                race=record.race,
                alignment=record.alignment,
                home_province=record.coord,
            )
            if king_extensions is not None and king_id < len(king_extensions):
                extension = king_extensions[king_id]
                kingdom.treasury = extension.treasury
                kingdom.discoveries = set(extension.discovered)
                kingdom.valhalla_visit_count = extension.valhalla_visit_count
            kingdoms[king_id] = kingdom
            leaders[king_id] = LeaderState(
                leader_id=king_id,
                kingdom_id=king_id,
                name=record.name,
                location=record.coord,
                skills=record.skills,
                is_king=True,
                temper=record.temper,
                race=record.race,
                alignment=record.alignment,
            )
        else:
            roster_id = STANDARD_HERO_ID_BY_NAME.get(record.name)
            if roster_id is not None:
                hero_id = roster_id
                heroes_with_confirmed_id[record.name] = hero_id
                sex = STANDARD_HERO_SEX_BY_NAME[record.name]
            else:
                hero_id = next_hero_id
                next_hero_id -= 1
                heroes_with_synthetic_id[record.name] = hero_id
                sex = None
            leaders[hero_id] = LeaderState(
                leader_id=hero_id,
                kingdom_id=record.kingdom_id,
                name=record.name,
                location=record.coord,
                skills=record.skills,
                is_king=False,
                temper=record.temper,
                race=record.race,
                alignment=record.alignment,
                sex=sex,
            )

    state = GameState(turn_number=turn_number, kingdoms=kingdoms, leaders=leaders)

    if king_extensions is not None:
        for king_id, extension in enumerate(king_extensions):
            if king_id not in kingdoms:
                continue
            for other_king_id, relation in enumerate(extension.diplomatic_relations):
                if other_king_id == king_id or other_king_id not in kingdoms:
                    continue
                if extension.met_kings_bitmask & (1 << other_king_id):
                    state.kingdoms_met.add(frozenset({king_id, other_king_id}))
                if (
                    relation is DiplomaticRelation.ALLIED
                    and other_king_id < len(king_extensions)
                    and king_id < len(king_extensions[other_king_id].diplomatic_relations)
                    and king_extensions[other_king_id].diplomatic_relations[king_id] is DiplomaticRelation.ALLIED
                ):
                    state.allied_kingdoms.add(frozenset({king_id, other_king_id}))

    # Phase 780: record the real board size (column-major, so width is
    # simply the record count divided by the confirmed height) so
    # downstream turn-engine code no longer has to fall back to `turn/
    # movement.py NORMAL_MAP_BOUNDS` (confirmed the *Super-AK* size,
    # `Regolamento AK.txt` 12.1). Left at `GameState`'s own default when
    # there are no province records to derive a real width from at all.
    if province_records:
        state.board_width = len(province_records) // height
        state.board_height = height

    provinces = bridge_gw_world_provinces(province_records, height=height)
    resolved_owners = resolve_province_owners(provinces, province_records, state, height=height)
    state.provinces = provinces

    armies_created = 0
    dead_army_records_excluded = 0
    unresolved_army_records: list[GWArmyRecord] = []
    for record in army_records:
        if record.army_type is None:
            continue
        if record.state is MonsterEngagementState.DEAD:
            dead_army_records_excluded += 1
            continue
        if record.is_mercenary:
            owner_kingdom_id: int | None = None
            commanded_by: int | None = None
        elif record.commanded_by_leader_id is None:
            province = provinces.get(record.coord)
            owner_kingdom_id = province.owner_kingdom_id if province is not None else None
            commanded_by = None
        elif record.commanded_by_leader_id in leaders:
            # Any leader this bridge gave a real id -- a King, or a
            # roster-matched Hero (Phase 339) -- resolves directly via
            # his own real `kingdom_id` (the Liege field for a Hero,
            # `== leader_id` for a King -- never the leader_id itself,
            # see `apply_confirmed_hero_ids()`'s own docstring for the
            # bug class this distinction guards against).
            commander = leaders[record.commanded_by_leader_id]
            owner_kingdom_id = commander.kingdom_id
            commanded_by = record.commanded_by_leader_id
        else:
            unresolved_army_records.append(record)
            continue

        state.add_army(
            ArmyState(
                army_id=state.new_army_id(),
                kingdom_id=owner_kingdom_id,
                army_type=record.army_type,
                quality=record.quality,
                location=record.coord,
                commanded_by=commanded_by,
                is_skeletal=record.is_skeletal,
            )
        )
        armies_created += 1

    report = NewGameStateReport(
        kings_created=len(king_ids),
        heroes_created=len(heroes_with_confirmed_id) + len(heroes_with_synthetic_id),
        provinces_created=len(provinces),
        provinces_with_resolved_owner=resolved_owners,
        armies_created=armies_created,
        heroes_with_confirmed_id=heroes_with_confirmed_id,
        heroes_with_synthetic_id=heroes_with_synthetic_id,
        unresolved_army_records=unresolved_army_records,
        dead_army_records_excluded=dead_army_records_excluded,
    )
    return state, report


@dataclass(slots=True)
class AppliedHeroIdsReport:
    leaders_rekeyed: int
    not_found_names: list[str] = field(default_factory=list)
    armies_recovered: int = 0
    # Still-unattributable after applying the supplied names -- either the
    # name wasn't in `name_to_real_id`, or its real id still isn't a
    # commanded_by_leader_id seen in `unresolved_army_records`.
    still_unresolved_army_records: list[GWArmyRecord] = field(default_factory=list)


def apply_confirmed_hero_ids(
    state: GameState,
    name_to_real_id: dict[str, int],
    unresolved_army_records: list[GWArmyRecord],
) -> AppliedHeroIdsReport:
    """Re-keys `bridge_new_game_state()`'s own synthetic Hero ids to real
    ones once the caller has an independent source for them (e.g. a real
    `SE3__Tn.Kx` letter's own `"Name (#id)"` roster line, the same kind
    of cross-check earlier phases already used one Hero at a time).

    Also retries every `unresolved_army_records` entry whose own
    `commanded_by_leader_id` now matches a newly-applied real id --
    exactly the Block B rows `bridge_new_game_state()` had to leave out
    for having no confirmed owner. Does **not** re-run
    `resolve_province_owners()` -- call that again separately afterward
    if a newly-real-ided Hero also personally governs a province; it's
    already idempotent and safe to call again.
    """

    report = AppliedHeroIdsReport(leaders_rekeyed=0)
    old_id_by_real_id: dict[int, int] = {}

    for name, real_id in name_to_real_id.items():
        old_leader = next(
            (leader for leader in state.leaders.values() if leader.name == name and leader.leader_id < 0),
            None,
        )
        if old_leader is None:
            report.not_found_names.append(name)
            continue
        old_id = old_leader.leader_id
        del state.leaders[old_id]
        state.leaders[real_id] = replace(old_leader, leader_id=real_id)
        old_id_by_real_id[real_id] = old_id
        report.leaders_rekeyed += 1

    for army in state.armies.values():
        if army.commanded_by is not None and army.commanded_by in old_id_by_real_id.values():
            real_id = next(rid for rid, oid in old_id_by_real_id.items() if oid == army.commanded_by)
            army.commanded_by = real_id

    still_unresolved: list[GWArmyRecord] = []
    for record in unresolved_army_records:
        real_id = record.commanded_by_leader_id
        commander = state.leaders.get(real_id) if real_id in old_id_by_real_id else None
        if commander is not None:
            state.add_army(
                ArmyState(
                    army_id=state.new_army_id(),
                    # The army's own owner is the commanding Hero's serving
                    # kingdom (the Liege field, `commander.kingdom_id`) --
                    # NOT the Hero's own `leader_id`, which only coincides
                    # with kingdom_id for a King (Phase 330's own convention).
                    kingdom_id=commander.kingdom_id,
                    army_type=record.army_type,
                    quality=record.quality,
                    location=record.coord,
                    commanded_by=real_id,
                    is_skeletal=record.is_skeletal,
                )
            )
            report.armies_recovered += 1
        else:
            still_unresolved.append(record)
    report.still_unresolved_army_records = still_unresolved

    return report
