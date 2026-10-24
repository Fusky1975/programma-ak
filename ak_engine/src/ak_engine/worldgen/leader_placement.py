"""Leader placement (Phase 357): ``AKGEN.EXE``'s roster-to-map assignment (0x12F3C).

Fifth phase of the world-generation sub-plan. Source:
``world_generation.leader_placement``.

**Confirmed exactly** and implemented here, each cross-checked against
the source's own two worked real-game examples (``GW3_T1_K10``:
``leader_count=100`` derived below, ``king_count=10``; ``GW900_K4``:
``humanoid_province_count=45``, ``king_count=4``, ``leader_count=100``):

- ``owner_leader_count()``: ``min(humanoid_province_count,
  leader_count - (2*king_count + 1))`` -- the total number of leaders
  who end up *owning* a province (Kings plus independent lords).
  Verified against ``GW900_K4`` directly (``min(45, 100-9) == 45``,
  matching its own stated ``owner_leaders: 45`` exactly) and against
  ``GW3_T1_K10`` by reconstructing ``leader_count=100`` from that
  example's own other confirmed counts (``79 + 20 companions + 1
  reserved + 0 remaining == 100``) and confirming the formula's
  ``min(X, 100-21) == 79`` is consistent with it.
- ``COMPANIONS_PER_KING = 2`` and ``companion_count()`` (``2 *
  king_count``): verified exactly against both examples (``2*10==20``,
  ``2*4==8``).
- ``RESERVED_ROSTER_COUNT = 1``: "excluded from the two-per-King
  selection and attached separately to a Home" -- always exactly one
  entry, confirmed in both examples' own ``reserved: 1``.
- ``remaining_mercenary_count()``: ``leader_count - owner_leader_count
  - companion_count - RESERVED_ROSTER_COUNT``. Verified against
  ``GW900_K4`` (``100-45-8-1 == 46``, matching its own ``remaining_
  mercenaries: 46`` exactly) and ``GW3_T1_K10`` (``100-79-20-1 == 0``,
  matching its own ``remaining_mercenaries: 0``).
- ``king_home_effects()``: the confirmed per-King province mutation --
  province owner becomes the King's leader id, province tax becomes
  the already-confirmed ``HOME_OVERRIDE_TAX`` (``province_tax.py``,
  Phase 356), province native race becomes the King's own race, and
  the King leader's own current/born coordinates become the Home
  province's coordinate. Returned as a plain, standalone dataclass --
  this module (like every worldgen phase since 352) does not mutate
  ``GameState``/``ProvinceState``/``LeaderState`` directly; a later
  integration phase would apply these values to whichever real state
  object represents the province and leader.
- ``draw_second_companion_race()``: "uniform Human/Elf/Dwarf/Orc,
  redraw while equal to King race" -- realized as a literal
  rejection-sampling loop (draw uniformly among the 4, reject and
  redraw on a match), the same "implement the real draw-and-reject
  mechanism, not just its equivalent simplified distribution" choice
  this project already made for `battle_luck.apply_bres_tie_correction`
  (Phase 933 -- which is itself a correction of Phase 347's own
  `break_bres_tie`, a plausible-looking coin-flip abstraction that
  turned out to be exactly the wrong kind of "equivalent simplified
  distribution" this citation warns against) and `place_map`'s own
  land-seed placement (Phase 354).
- ``independent_lord_effects()``: "province owner becomes leader id",
  "leader coordinates and born coordinates become province
  coordinates", "leader race is overwritten with province native
  race" -- again returned as a standalone dataclass, not applied to
  any live state.
- ``draw_mercenary_relocation_coordinate()``: "redraw coordinates
  while on Sea or in a King-owned province; sharing a lord-owned
  province is allowed" -- a second literal rejection-sampling loop,
  taking caller-supplied ``is_sea``/``is_king_owned`` predicates so
  this module stays decoupled from any particular map/ownership
  representation (mirroring `place_map`'s own predicate-free but
  analogous accept/reject cell-draw loops).

**Deliberately NOT implemented here**, each a genuine, separately
documented gap:

- The King roster selection itself ("interactive roster choice") --
  a human game-master action during setup, not automatic generation.
- The exact selection *order* for independent lords (which of the
  free humanoid provinces gets filled by which unused roster leader,
  and in what sequence) -- the source gives a target/selection/
  effects/stop narrative, not an exact algorithm, the same category
  of gap as `province_races.py`'s own special-race overwrite pass.
  Unlike Phase 354's `place_map` spatial pipeline, this one has not
  been asked to be turned into a project-original algorithm, so it's
  left as a documented narrative gap instead.
- "first recruit slot becomes best_atype[king race]" -- **closed since
  Phase 358, corrected Phase 892's own survey**: this bullet used to
  say ``best_atype`` was "a per-race 'best army type' table this
  project hasn't sourced yet" -- stale, the very next phase after this
  module shipped it (``worldgen/initial_armies.py BEST_ATYPE``, whose
  own docstring already says plainly "this directly closes the gap
  Phase 357's own ``king_home_effects()`` deliberately left open").
  ``king_home_effects()`` itself still omits this field on purpose,
  not for lack of a source any more -- ``worldgen/generate_new_game.py``
  calls ``home_first_slot(king.race)`` (= ``BEST_ATYPE[king.race]``)
  directly at its own King-Home province-building call site instead of
  routing it through this function.
- The reserved last roster entry's own attachment target ("attached
  separately to a Home" -- ambiguous which Home) -- only its *count*
  (always 1) is implemented; its placement rule isn't specified
  precisely enough to code.
- ~~The special-race tax recompute interaction, already deferred
  alongside the special-race placement pass itself (Phase 355/356).~~ --
  **closed in Phase 362** (already correctly recorded as closed in
  `worldgen/province_tax.py`'s own docstring, but never cross-linked
  back here): `worldgen/special_race_placement.py recompute_tax()`,
  wired from `worldgen/generate_new_game.py`, does exactly this.

**Verification**: the four count formulas above are checked directly
against both of the source's own worked examples (exact integers, no
Monte Carlo needed). `draw_second_companion_race()` and
`draw_mercenary_relocation_coordinate()` are Monte Carlo-checked: the
former never returns the King's own race and is roughly uniform over
the other three; the latter never lands on Sea or a King-owned
coordinate across a large sample.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from ak_engine.models.map import HexCoord
from ak_engine.models.race import Race
from ak_engine.worldgen.pascal_random import PascalRandom
from ak_engine.worldgen.province_tax import HOME_OVERRIDE_TAX

COMPANIONS_PER_KING = 2
RESERVED_ROSTER_COUNT = 1

_HUMANOID_RACES: tuple[Race, ...] = (Race.HUMAN, Race.ELVEN, Race.DWARVEN, Race.ORCISH)


def owner_leader_count(humanoid_province_count: int, leader_count: int, king_count: int) -> int:
    """``min(humanoid_province_count, leader_count - (2*king_count + 1))``."""

    return min(humanoid_province_count, leader_count - (2 * king_count + 1))


def companion_count(king_count: int) -> int:
    """``COMPANIONS_PER_KING * king_count``."""

    return COMPANIONS_PER_KING * king_count


def remaining_mercenary_count(leader_count: int, owner_leader_count_: int, companion_count_: int) -> int:
    """Roster entries left over as Mercenaries after Kings, lords, companions, and the reserved entry."""

    return leader_count - owner_leader_count_ - companion_count_ - RESERVED_ROSTER_COUNT


@dataclass(frozen=True, slots=True)
class KingHomeEffects:
    province_owner_id: int
    province_tax: int
    province_race: Race
    leader_current_coord: HexCoord
    leader_born_coord: HexCoord


def king_home_effects(king_leader_id: int, king_race: Race, home_coord: HexCoord) -> KingHomeEffects:
    """The confirmed province + leader mutations for a King's own Home province."""

    return KingHomeEffects(
        province_owner_id=king_leader_id,
        province_tax=HOME_OVERRIDE_TAX,
        province_race=king_race,
        leader_current_coord=home_coord,
        leader_born_coord=home_coord,
    )


def draw_second_companion_race(king_race: Race, rng: PascalRandom) -> Race:
    """Uniform draw among Human/Elf/Dwarf/Orc, rejecting and redrawing while it matches ``king_race``."""

    while True:
        candidate = _HUMANOID_RACES[rng.irand() & 3]
        if candidate is not king_race:
            return candidate


@dataclass(frozen=True, slots=True)
class IndependentLordEffects:
    province_owner_id: int
    leader_current_coord: HexCoord
    leader_born_coord: HexCoord
    leader_race: Race


def independent_lord_effects(
    leader_id: int, province_coord: HexCoord, province_race: Race
) -> IndependentLordEffects:
    """The confirmed province + leader mutations for an independent lord taking a free humanoid province."""

    return IndependentLordEffects(
        province_owner_id=leader_id,
        leader_current_coord=province_coord,
        leader_born_coord=province_coord,
        leader_race=province_race,
    )


MERCENARY_RELOCATION_ATTEMPT_CAP = 10_000


def draw_mercenary_relocation_coordinate(
    rng: PascalRandom,
    width: int,
    height: int,
    is_sea: Callable[[HexCoord], bool],
    is_king_owned: Callable[[HexCoord], bool],
) -> HexCoord:
    """Uniform coordinate draw, rejecting and redrawing while on Sea or in a King-owned province.

    Bug fix (crash/DoS): capped like every sibling rejection-sampling
    loop in this module (``feature_placement.place_feature``'s
    ``MAX_ATTEMPTS``, ``special_race_placement.place_special_race``'s
    ``ATTEMPT_CAP``) -- this was an uncapped ``while True``, which would
    spin forever if every cell were ever Sea or King-owned.
    """

    for _ in range(MERCENARY_RELOCATION_ATTEMPT_CAP):
        candidate = HexCoord(rng.irand() % width, rng.irand() % height)
        if not is_sea(candidate) and not is_king_owned(candidate):
            return candidate
    raise ValueError("No eligible mercenary relocation coordinate found -- map too small or too crowded.")
