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
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from ak_engine.models.game_state import ArmyState, GameState, KingdomState, LeaderState, ProvinceState
from ak_engine.models.map import HexCoord
from ak_engine.parser.gw_world import GWArmyRecord, GWLeaderRecord, GWProvinceRecord

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
        provinces[coord] = ProvinceState(
            coord=coord,
            terrain=record.terrain,
            race=record.race,
            name=record.name,
            tax=record.tax,
            recruit_type_1=record.recruit_type_1,
            recruit_type_2=record.recruit_type_2,
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
    # A Hero's real leader_id was assigned a synthetic (negative) id --
    # see module docstring's Phase 338 addendum. Maps name -> synthetic id.
    hero_synthetic_ids: dict[str, int] = field(default_factory=dict)
    # Block B rows led by a Hero (not a King, not unled) -- their real
    # owning kingdom has no confirmed source, so they weren't bridged
    # into `GameState.armies` at all. Kept here so `apply_confirmed_hero_ids()`
    # can retry them once real Hero ids are supplied.
    unresolved_army_records: list[GWArmyRecord] = field(default_factory=list)


def bridge_new_game_state(
    leader_records: list[GWLeaderRecord],
    province_records: list[GWProvinceRecord],
    army_records: list[GWArmyRecord],
    *,
    turn_number: int = 1,
    height: int = CONFIRMED_BOARD_HEIGHT,
    hero_id_start: int = -1,
) -> tuple[GameState, NewGameStateReport]:
    """Builds a brand-new `GameState` directly from a single `GW3` file's
    own three already-parsed record lists -- see module docstring's
    Phase 338 addendum for exactly what's real here and what's a
    documented placeholder.

    Every King's own `KingdomState`/`LeaderState` is fully real
    (`leader_id == kingdom_id`, Phase 330). Every Hero's own
    `LeaderState` uses a synthetic, negative `leader_id` (real name,
    race, alignment, temper, skills, coord, and kingdom_id/Liege --
    just not the real numeric identity, which no `GW3` file alone can
    supply -- see the module docstring's own falsified-technique
    writeup). Provinces reuse `bridge_gw_world_provinces()`/
    `resolve_province_owners()` unchanged. Armies bridge for every
    unled row (owner = the province's own resolved owner) and every
    King-led row (owner = that King's own real id); a Hero-led row is
    left out and returned in the report instead of being bridged with
    a guessed owner.
    """

    kingdoms: dict[int, KingdomState] = {}
    leaders: dict[int, LeaderState] = {}
    hero_synthetic_ids: dict[str, int] = {}
    king_ids: set[int] = set()

    next_hero_id = hero_id_start
    for record in leader_records:
        if record.is_king:
            king_id = record.kingdom_id
            assert king_id is not None  # a King's own kingdom_id is never None (Phase 330)
            king_ids.add(king_id)
            kingdoms[king_id] = KingdomState(
                kingdom_id=king_id,
                name=record.name,
                race=record.race,
                alignment=record.alignment,
                home_province=record.coord,
            )
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
            hero_id = next_hero_id
            next_hero_id -= 1
            hero_synthetic_ids[record.name] = hero_id
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
            )

    state = GameState(turn_number=turn_number, kingdoms=kingdoms, leaders=leaders)

    provinces = bridge_gw_world_provinces(province_records, height=height)
    resolved_owners = resolve_province_owners(provinces, province_records, state, height=height)
    state.provinces = provinces

    armies_created = 0
    unresolved_army_records: list[GWArmyRecord] = []
    for record in army_records:
        if record.army_type is None:
            continue
        if record.is_mercenary:
            owner_kingdom_id: int | None = None
            commanded_by: int | None = None
        elif record.commanded_by_leader_id is None:
            province = provinces.get(record.coord)
            owner_kingdom_id = province.owner_kingdom_id if province is not None else None
            commanded_by = None
        elif record.commanded_by_leader_id in king_ids:
            owner_kingdom_id = record.commanded_by_leader_id
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
        heroes_created=len(hero_synthetic_ids),
        provinces_created=len(provinces),
        provinces_with_resolved_owner=resolved_owners,
        armies_created=armies_created,
        hero_synthetic_ids=hero_synthetic_ids,
        unresolved_army_records=unresolved_army_records,
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
