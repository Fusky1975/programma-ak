"""Autonomous wandering of unemployed Heroes and mercenary armies.

Sourced from the user-supplied disassembly dossier ``Desktop/MERCHERO.md``
(2026-09-10, CERTO-graded), resolving backlog item #20: the real resolver
at ``AK.OVR:0xD6C5`` that lets an unemployed Hero or a mercenary army
relocate on its own initiative between turns -- a mechanic previously
confirmed to have real, sourced, fully-transcribed report text
(``report/turn_report.py render_mercenary_army_wanders_away/in()``,
``render_character_wanders_away/in()``, Phase 591) but zero underlying
trigger/probability/destination logic anywhere. Phase 781.

Three genuinely unsourced design points were resolved directly with the
user (see the plan file's own Phase 781 section for the full reasoning):
mercenary armies get NO ``avoid_owner`` tracking at all (unlike Heroes,
which reuse ``LeaderState.birth_x``/``.birth_y``); the ``DS:8B52``
King-orders-flag gate is implemented faithfully (see ``turn/turn_
processor.py _kingdom_submitted_real_orders()``). The armies-only quality
change/dissolution (``roll_mercenary_quality_change()`` below) was first an
approximation of an under-characterized branch of the source document; since
2026-11-24 it follows the user's own table of per-turn chances instead
(``MERCENARY_QUALITY_CHANGE_CHANCE``), with the original SAY.PAS texts
(``_MInc``/``_MDec``/``_MSplut``) narrated in the report.

The shared hex-stepper (``_wander_step_hex()``) is a deliberate,
duplicated copy of ``turn/cast_execution.py _scar_terrain_step_hex()``
-- this project's own established "small, duplicated per-consumer"
convention rather than promoting a shared helper across two
independently-sourced modules. A real byte-level conflict between
MERCHERO.md and SCAR.md over this exact routine's own recursive-retry
behavior was investigated and resolved (both documents describe the
same function correctly; the already-shipped simplification here is
externally equivalent to the real behavior for every confirmed caller).
"""

from __future__ import annotations

import random

from ak_engine.models.army_type import ArmyType, SEA_ARMY_TYPES
from ak_engine.models.game_state import ArmyState, GameState, LeaderState
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.office import Office
from ak_engine.models.race import Race
from ak_engine.turn.combat import Quality
from ak_engine.turn.leader_queries import find_king_of_kingdom
from ak_engine.turn.movement import MapBounds, hex_distance_wrapped
from ak_engine.turn.office_holder import resolve_office_holder

# MERCHERO.md section 6/13.2's own real Real48 constants, transcribed
# verbatim.
WANDER_AVOID_OWNER_ACCEPT_CHANCE = 0.005
WANDER_ATTRACTOR_ROLL_THRESHOLD = 0.2

# MERCHERO.md section 12.4's own confirmed per-object initial-access
# rolls -- a Hero's own draw is a plain ``rng.random() < 0.5``; an
# army's own real formula is ``(IRand(6) - 2*int(marker>0)) < 3``, but
# ``marker`` (the B514 avoid-owner marker) is always absent per the
# user's own confirmed design choice (armies get no avoid_owner at all),
# so it always reduces to the same 3-of-6 draw -- see ``turn/turn_
# processor.py`` for both real call sites.
HERO_WANDER_ACCESS_CHANCE = 0.5

# MERCHERO.md section 3's own confirmed 5-step cap for a wandering Hero.
HERO_WANDER_MAX_STEPS = 5

# MERCHERO.md's own confirmed continuation mask -- a land Hero keeps
# stepping while ``(IRand(100) AND 4) != 0`` (48/100, roughly 1/2 odds --
# Phase 1194 correction, this used to misstate it as "roughly 5/8"; the
# mask constant below was always correct, only this comment's own figure
# was wrong), a Sea Hero while ``(IRand(100) AND 7) != 0`` (87/100,
# roughly 7/8 odds).
_LAND_CONTINUATION_MASK = 4
_SEA_CONTINUATION_MASK = 7

# MERCHERO.md section 4's own decoded ``35EB:079E`` race predicate
# (``race<=3 or race==14``) plus the separate ``race==7`` carve-out,
# transcribed as one combined set.
WANDER_ELIGIBLE_RACES = frozenset(
    {Race.HUMAN, Race.ELVEN, Race.DWARVEN, Race.ORCISH, Race.ROHAN, Race.NO_RACE}
)


def _wander_step_hex(coord: HexCoord, direction: int, board_width: int, board_height: int) -> HexCoord | None:
    """``AK.EXE:0x41786`` ``StepHex`` -- SCAR.md section 7.2/MERCHERO.md
    section 5, a duplicated copy of ``turn/cast_execution.py
    _scar_terrain_step_hex()`` (see that function's own docstring for
    the full byte-level sourcing and this phase's own conflict-
    resolution note in the module docstring above). ``direction`` is a
    real ``Rand6`` roll, 1-6.

    Horizontal wraparound is unconditional. A step off the vertical
    board edge returns ``None`` -- the caller still counts this as one
    of its own consumed attempts, not a free retry.
    """

    odd = coord.y & 1
    dx, dy = {
        1: (odd, -1),
        2: (1, 0),
        3: (odd, 1),
        4: (odd - 1, 1),
        5: (-1, 0),
        6: (odd - 1, -1),
    }[direction]
    nx, ny = coord.x + dx, coord.y + dy
    if nx == -1:
        nx = board_width - 1
    elif nx == board_width:
        nx = 0
    if ny < 0 or ny >= board_height:
        return None
    return HexCoord(nx, ny)


def _roll_main_direction(rng: random.Random) -> int:
    """``Trunc(RandomReal*6)+1`` -- a real direction, 1-6."""

    return 1 + int(rng.random() * 6)


def _circular_direction_distance(a: int, b: int) -> int:
    """Distance between two 1-6 directions on the wrapping 6-cycle
    (difference 4 wraps to 2, 5 wraps to 1, per MERCHERO's own
    confirmed table)."""

    diff = abs(a - b) % 6
    return min(diff, 6 - diff)


def _roll_step_direction(rng: random.Random, main_direction: int) -> int:
    """Re-rolls a direction 1-6 until its circular distance from
    ``main_direction`` is <= 1."""

    while True:
        candidate = 1 + int(rng.random() * 6)
        if _circular_direction_distance(candidate, main_direction) <= 1:
            return candidate


def _kingdom_has_king(state: GameState, kingdom_id: int) -> bool:
    return find_king_of_kingdom(state, kingdom_id) is not None


def _accept_wander_direction(
    state: GameState,
    coord: HexCoord,
    direction: int,
    avoid_owner: int | None,
    attractor_leader_id: int | None,
    bounds: MapBounds,
    rng: random.Random,
) -> HexCoord | None:
    """The real ``AcceptDirection``/political filter (MERCHERO section
    6/13.2 pseudocode, transcribed directly).

    ``None`` immediately on an off-board step. If the neighbor's own
    ``owner_kingdom_id == avoid_owner`` (may be ``None == None``, a
    real, literal consequence of an unowned reference province --
    documented, not special-cased away), accept iff a roll clears
    ``WANDER_AVOID_OWNER_ACCEPT_CHANCE``. Otherwise, a second roll
    above ``WANDER_ATTRACTOR_ROLL_THRESHOLD`` with a real attractor
    accepts iff the neighbor is strictly closer to it than the current
    coord; otherwise a third, independent roll accepts below the same
    threshold, or when the neighbor's own owner is a real King's
    Kingdom.
    """

    neighbor = _wander_step_hex(coord, direction, bounds.width, bounds.height)
    if neighbor is None:
        return None
    province = state.provinces.get(neighbor)
    neighbor_owner = province.owner_kingdom_id if province is not None else None

    if neighbor_owner == avoid_owner:
        return neighbor if rng.random() < WANDER_AVOID_OWNER_ACCEPT_CHANCE else None

    second_roll = rng.random()
    if second_roll > WANDER_ATTRACTOR_ROLL_THRESHOLD and attractor_leader_id is not None:
        attractor = state.leaders.get(attractor_leader_id)
        if attractor is not None:
            current_distance = hex_distance_wrapped(coord, attractor.location, board_width=bounds.width)
            neighbor_distance = hex_distance_wrapped(neighbor, attractor.location, board_width=bounds.width)
            if neighbor_distance < current_distance:
                return neighbor

    third_roll = rng.random()
    if third_roll < WANDER_ATTRACTOR_ROLL_THRESHOLD:
        return neighbor
    if neighbor_owner is not None and _kingdom_has_king(state, neighbor_owner):
        return neighbor
    return None


def _wander_density(state: GameState, coord: HexCoord) -> int:
    """The ``BP-0x1FE`` array (MERCHERO section 2/12) -- a count of
    every *employed* leader/army standing at ``coord``. Mercenaries and
    independent Heroes are excluded by construction (they always have
    ``kingdom_id is None``)."""

    leaders = sum(1 for leader in state.leaders.values() if leader.location == coord and leader.kingdom_id is not None)
    armies = sum(1 for army in state.armies.values() if army.location == coord and army.kingdom_id is not None)
    return leaders + armies


def _army_type_terrain_excluded(army_type: ArmyType, destination_terrain: Terrain) -> bool:
    """``ARMY_TYPE_BY_ORDINAL``-confirmed exclusion sets (MERCHERO
    section 4): Whales/Fleet/Mermen (``SEA_ARMY_TYPES``) can never
    leave Sea; Ents can never enter it."""

    if army_type in SEA_ARMY_TYPES and destination_terrain is not Terrain.SEA:
        return True
    if army_type is ArmyType.ENTS and destination_terrain is Terrain.SEA:
        return True
    return False


def _resolve_attractor_leader_id(state: GameState) -> int | None:
    holder = resolve_office_holder(state, Office.NEUTRAL_KING)
    return holder.leader_id if holder is not None else None


def hero_eligible_for_wander(state: GameState, leader: LeaderState, orders_flag: dict[int, bool]) -> bool:
    """``leader.kingdom_id is None``, commands no armies, a real-race
    check (``WANDER_ELIGIBLE_RACES``), and -- only when the origin
    province's own owner is a real King -- the King-orders-flag gate."""

    if leader.kingdom_id is not None:
        return False
    if leader.race is not None and leader.race not in WANDER_ELIGIBLE_RACES:
        return False
    if state.armies_commanded_by(leader.leader_id):
        return False
    province = state.provinces.get(leader.location)
    owner_kingdom_id = province.owner_kingdom_id if province is not None else None
    if owner_kingdom_id is not None and _kingdom_has_king(state, owner_kingdom_id):
        return orders_flag.get(owner_kingdom_id, False)
    return True


def army_eligible_for_wander(state: GameState, army: ArmyState, orders_flag: dict[int, bool]) -> bool:
    """``army.kingdom_id is None`` and the same King-orders-flag check
    against the army's own current province owner."""

    if army.kingdom_id is not None:
        return False
    if army.commanded_by is not None:
        return False  # "le unita' militari non possono muovere senza personaggi" -- and not away from theirs
    if not army.is_mercenary:
        return False  # user ruling 2026-11-26: only mercenary bands wander; a native garrison stays where it defends
    province = state.provinces.get(army.location)
    owner_kingdom_id = province.owner_kingdom_id if province is not None else None
    if owner_kingdom_id is not None and _kingdom_has_king(state, owner_kingdom_id):
        return orders_flag.get(owner_kingdom_id, False)
    return True


def resolve_hero_wander(state: GameState, leader: LeaderState, rng: random.Random) -> HexCoord:
    """The Hero path (MERCHERO section 3). Resolves ``avoid_owner``
    from ``leader.birth_x``/``.birth_y`` (skipping the political filter
    for the very first direction pick only when that reference
    coordinate is missing/out of range, matching MERCHERO's own
    confirmed branch split); walks up to ``HERO_WANDER_MAX_STEPS``
    successful steps, re-rolling a step direction from the current
    position each time; continues only while a real mask roll succeeds
    (land/sea), steps remain, and the destination's own density hasn't
    grown past the starting density.

    Returns the Hero's own real, final coordinate -- does not mutate
    ``leader`` itself; the caller decides whether/how to apply it.
    """

    bounds = MapBounds(state.board_width, state.board_height)
    attractor_leader_id = _resolve_attractor_leader_id(state)

    skip_filter_first_step = (
        leader.birth_x is None or leader.birth_y is None or leader.birth_x > state.board_width - 1
    )
    avoid_owner: int | None = None
    if not skip_filter_first_step:
        birth_province = state.provinces.get(HexCoord(leader.birth_x, leader.birth_y))
        avoid_owner = birth_province.owner_kingdom_id if birth_province is not None else None

    initial_density = _wander_density(state, leader.location)
    current = leader.location
    main_direction = _roll_main_direction(rng)
    steps_taken = 0

    while steps_taken < HERO_WANDER_MAX_STEPS:
        direction = _roll_step_direction(rng, main_direction)
        if steps_taken == 0 and skip_filter_first_step:
            destination = _wander_step_hex(current, direction, bounds.width, bounds.height)
        else:
            destination = _accept_wander_direction(
                state, current, direction, avoid_owner, attractor_leader_id, bounds, rng
            )
        if destination is None:
            break
        current = destination
        steps_taken += 1

        if steps_taken >= HERO_WANDER_MAX_STEPS:
            break
        province = state.provinces.get(current)
        terrain = province.effective_terrain() if province is not None else Terrain.NO_TERRAIN
        mask = _SEA_CONTINUATION_MASK if terrain is Terrain.SEA else _LAND_CONTINUATION_MASK
        if (int(rng.random() * 100) & mask) == 0:
            break
        if _wander_density(state, current) > initial_density:
            break

    return current


def resolve_army_wander(state: GameState, army: ArmyState, rng: random.Random) -> HexCoord:
    """The mercenary-army path (MERCHERO section 4). Same direction/
    filter/density shape as ``resolve_hero_wander()``, ``avoid_owner``
    always ``None`` (user-confirmed), each candidate checked against
    ``_army_type_terrain_excluded()`` before it's accepted, movement
    budget read from and decremented on ``army.movement_points``
    directly (the same field ordinary Move already uses -- no new
    field), continuation gated purely on the *current* terrain being
    Sea (MERCHERO's own explicit "no equivalent continuation roll for
    armies").

    Returns the army's own real, final coordinate -- does not mutate
    ``army.location`` itself; the caller decides whether/how to apply
    it. Does mutate ``army.movement_points`` directly, matching how an
    ordinary Move already spends this same field.
    """

    bounds = MapBounds(state.board_width, state.board_height)
    attractor_leader_id = _resolve_attractor_leader_id(state)

    current = army.location
    main_direction = _roll_main_direction(rng)

    while army.movement_points > 0:
        direction = _roll_step_direction(rng, main_direction)
        destination = _accept_wander_direction(state, current, direction, None, attractor_leader_id, bounds, rng)
        if destination is None:
            break
        destination_province = state.provinces.get(destination)
        destination_terrain = (
            destination_province.effective_terrain() if destination_province is not None else Terrain.NO_TERRAIN
        )
        if _army_type_terrain_excluded(army.army_type, destination_terrain):
            break
        current = destination
        army.movement_points -= 1

        current_province = state.provinces.get(current)
        current_terrain = current_province.effective_terrain() if current_province is not None else Terrain.NO_TERRAIN
        if current_terrain is not Terrain.SEA:
            break

    return current


# User ruling 2026-11-24 (replaces the earlier MERCHERO.md "decay" approximation, which had no
# increase branch): every turn each free mercenary band may rise or sink one quality level --
# ``(chance to rise, chance to sink)`` per current quality. Veteran -> Crack is the ceiling of
# this rule (a band never rises above Crack); a Depleted band can only dissolve.
MERCENARY_QUALITY_CHANGE_CHANCE: dict[Quality, tuple[float, float]] = {
    Quality.GREEN: (0.07, 0.07),  # -> Average / -> Depleted
    Quality.AVERAGE: (0.07, 0.07),  # -> Veteran / -> Green
    Quality.VETERAN: (0.02, 0.07),  # -> Crack / -> Average
    Quality.CRACK: (0.0, 0.05),  # -> (ceiling) / -> Veteran
}
# A Depleted mercenary band disbands for good with this chance each turn ("_MSplut").
DEPLETED_MERCENARY_DISSOLVE_CHANCE = 0.20


class MercenaryQualityEvent:
    """One free mercenary band's quality change (``kind`` "up"/"down") or dissolution
    ("dissolved"), for the report layer -- SAY.PAS ``_MInc``/``_MDec``/``_MSplut``."""

    __slots__ = ("army_id", "army_type", "coord", "kind", "new_quality")

    def __init__(
        self, army_id: int, army_type: ArmyType, coord: HexCoord, kind: str, new_quality: Quality | None
    ) -> None:
        self.army_id = army_id
        self.army_type = army_type
        self.coord = coord
        self.kind = kind
        self.new_quality = new_quality


def roll_mercenary_quality_change(state: GameState, army: ArmyState, rng: random.Random) -> MercenaryQualityEvent | None:
    """One draw decides: a Depleted band dissolves (and is removed) with
    ``DEPLETED_MERCENARY_DISSOLVE_CHANCE``; any other band rises with its first chance, sinks with
    the next one (see ``MERCENARY_QUALITY_CHANGE_CHANCE``), else nothing happens. Returns the
    event, or ``None`` when nothing changed."""

    roll = rng.random()
    if army.quality is Quality.DEPLETED:
        if roll < DEPLETED_MERCENARY_DISSOLVE_CHANCE:
            event = MercenaryQualityEvent(army.army_id, army.army_type, army.location, "dissolved", None)
            state.remove_army(army.army_id)
            return event
        return None
    chances = MERCENARY_QUALITY_CHANGE_CHANCE.get(army.quality)
    if chances is None:
        return None
    rise, sink = chances
    if roll < rise:
        army.quality = Quality(int(army.quality) + 1)
        kind = "up"
    elif roll < rise + sink:
        army.quality = Quality(int(army.quality) - 1)
        kind = "down"
    else:
        return None
    return MercenaryQualityEvent(army.army_id, army.army_type, army.location, kind, army.quality)


class WanderRelocation:
    """A real net displacement recorded by ``resolve_wandering()`` for
    the report layer -- see ``report/turn_report.py record_wandering_
    world_events()``."""

    __slots__ = ("kind", "entity_id", "origin", "destination")

    def __init__(self, kind: str, entity_id: int, origin: HexCoord, destination: HexCoord) -> None:
        self.kind = kind
        self.entity_id = entity_id
        self.origin = origin
        self.destination = destination


def resolve_wandering(
    state: GameState,
    orders_flag: dict[int, bool],
    rng: random.Random,
    quality_events: list[MercenaryQualityEvent] | None = None,
) -> list[WanderRelocation]:
    """The once-per-turn end-of-turn tail step (called from ``turn/
    turn_processor.py run_turn()``): rolls the real per-object initial-
    access chance for every independent Hero and mercenary army across
    the whole map, sorted by id for determinism -- **unconditionally,
    even for an object the eligibility gates will reject** (MERCHERO
    section 12.4 point 4's own RNG-fidelity warning) -- then resolves a
    real wander for whichever ones both pass the roll and are eligible.
    Every free mercenary band also rolls its own quality change each turn
    (``roll_mercenary_quality_change()``, user ruling 2026-11-24), appended
    to ``quality_events`` when given.

    Returns only the real net displacements (initial != final
    coordinate) -- callers already apply the corresponding location
    mutation on the Hero/army themselves and use this list purely for
    report-layer narration.
    """

    relocations: list[WanderRelocation] = []

    heroes = sorted(
        (leader for leader in state.leaders.values() if leader.kingdom_id is None),
        key=lambda leader: leader.leader_id,
    )
    for leader in heroes:
        accessed = rng.random() < HERO_WANDER_ACCESS_CHANCE
        if not accessed:
            continue
        if not hero_eligible_for_wander(state, leader, orders_flag):
            continue
        origin = leader.location
        destination = resolve_hero_wander(state, leader, rng)
        if destination != origin:
            leader.location = destination
            relocations.append(WanderRelocation("hero", leader.leader_id, origin, destination))

    armies = sorted(
        (army for army in state.armies.values() if army.kingdom_id is None and army.is_mercenary),
        key=lambda army: army.army_id,
    )
    for army in armies:
        accessed = int(rng.random() * 6) < 3
        if army.is_mercenary and not army.unhireable_this_turn:  # (just disbanded this turn: not yet)
            event = roll_mercenary_quality_change(state, army, rng)
            if event is not None and quality_events is not None:
                quality_events.append(event)
            if event is not None and event.kind == "dissolved":
                continue
        if not accessed or not army_eligible_for_wander(state, army, orders_flag):
            continue
        origin = army.location
        destination = resolve_army_wander(state, army, rng)
        if destination != origin:
            army.location = destination
            relocations.append(WanderRelocation("army", army.army_id, origin, destination))

    return relocations
