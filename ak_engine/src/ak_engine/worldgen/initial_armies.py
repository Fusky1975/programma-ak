"""Recruit slots + initial armies (Phase 358): ``AKGEN.EXE``'s per-province
army generation (``province_army_routine`` 0B57:A400).

Sixth phase of the world-generation sub-plan. Source:
``world_generation.province_recruit_slots`` and
``world_generation.initial_armies``.

**Confirmed exactly** and implemented here:

- ``BEST_ATYPE``: Human->Legion, Elf->Bowmen, Dwarf->Axemen,
  Orc->Phalanx. This directly closes the gap Phase 357's own
  `king_home_effects()` deliberately left open ("first recruit slot
  becomes best_atype[king race]" -- the table wasn't sourced yet at
  that point). `home_first_slot()` wraps it for that exact use.
- ``NATIVE_ARMY_TYPE``: "special_races: direct native unit type" for
  Dragons/Eagles/Whales/Mermen/Ents/Trolls/Werefolk/Vampires -- built by
  inverting this project's own pre-existing
  ``models.army_type.MONSTROUS_ARMY_RACE`` (Phase 26/31/383), which now
  covers all eight of the source's own named races. Vampires were
  originally a documented gap here ("this project's ``ArmyType`` enum
  has no Vampire-native entry") -- closed by Phase 383's own
  ``ArmyType.VAMPIRES``/``MONSTROUS_ARMY_RACE[ArmyType.VAMPIRES] =
  Race.VAMPISH`` addition, sourced from this exact ``special_races``
  field. `NATIVE_ARMY_TYPE` now includes ``Race.VAMPISH`` automatically,
  with no change needed here.
- ``second_slot_gate()``: "``tax > (IRand AND 7)``" -- realized
  literally as ``tax > (rng.irand() & 7)``. Cross-checked against the
  source's own separately-stated ``probability_before_other_filters =
  min(tax,8)/8`` by hand before coding: ``IRand AND 7`` is uniform
  over ``0..7``, so ``P(tax > X) == (number of the 8 values below
  tax)/8 == min(tax,8)/8`` exactly.
- Budget formulas (``initial_armies.budget_by_race_or_owner``):
  ``KING_HOME_BUDGET = 7``; ``ordinary_humanoid_budget()`` (``1 +
  trunc(0.9*tax*U)``); ``draw_r4()`` (uniform integer ``1..4``, the
  source's own named "R4" primitive); ``whale_budget()`` (``tax + 1 +
  R4``); ``flying_or_special_budget()`` (``tax + R4a - R4b``, two
  independent R4 draws, left unclamped exactly as the source gives
  it -- a low-tax province can get a small or even negative budget,
  which `build_initial_armies()` naturally resolves to zero armies
  rather than needing a special case).
- ``build_initial_armies()``: the confirmed creation loop -- "start
  with recruit slot 0, create its army if affordable, subtract that
  type's strength, toggle 0/1; toggle back if the other slot is
  noarmy; stop when the next strength exceeds the remaining budget or
  after four armies." "That type's strength" is realized via this
  project's own pre-existing ``models.army_type.BASE_STRENGTH`` (Phase
  26), matching the source's own literal word choice ("strength", not
  "cost" or "pay" -- a separate field this table also has).
  ``MAX_ARMIES_PER_PROVINCE_PASS = 4``, matching
  ``maximum_armies_per_province_pass``.
- ``resolve_commander()``: "lord_owned_province: province owner leader
  id", "King_Home: 255", "unowned_province: 255" -- ``COMMANDER_NONE =
  255`` is the sentinel for both fixed cases.
- ``INITIAL_ARMY_QUALITY``: reuses this project's own pre-existing
  ``turn.combat.Quality.AVERAGE`` (value ``2``) -- confirms the
  source's own "Average (2)" exactly, zero new enum needed.

**Deliberately NOT implemented here**, each a genuine, separately
documented gap:

- ``humanoid_first_slot``'s own "terrain-weighted infantry" table --
  the source names that such a table exists and gates it with a 50%
  ``best_atype`` override, but doesn't give the actual per-terrain
  infantry weights anywhere in the material available to this
  project, so it can't be built without guessing.
- The ``necromantic_home_exception`` ("a qualifying King property can
  mark the first Home army Zomboid/Skeletal") -- the source never
  states what makes a King property "qualifying", so there is no rule
  to implement.
- The ``extra_mercenary_band`` (one per King, found via "radii 1..6"
  radial search from Home with up to 100 retries) -- this needs the
  whole generated map plus a real distance-radius search, a spatial
  algorithm in the same vein as `place_map` (Phase 354) and the
  special-race overwrite pass (Phase 355's own documented gap); not
  requested to be turned into a project-original algorithm this
  time, so left as a documented gap like Phase 357's independent-lord
  placement order.

**Verification**: `second_slot_gate()` is Monte Carlo-checked against
the hand-derived `min(tax,8)/8` probability for several tax values.
`build_initial_armies()` is checked against hand-worked traces (a
two-slot alternation that exhausts the budget exactly, a single-slot
repeat when the second slot is ``None``, and the four-army cap firing
before the budget would otherwise allow a fifth). The budget formulas
are checked for their documented ranges/means the same way this
project's other ``PascalRandom``-based formulas already are (e.g.
`province_tax.ordinary_land_tax`).
"""

from __future__ import annotations

from collections.abc import Callable

from ak_engine.models.army_type import BASE_STRENGTH, MONSTROUS_ARMY_RACE, ArmyType
from ak_engine.models.race import Race
from ak_engine.turn.combat import Quality
from ak_engine.worldgen.pascal_random import PascalRandom

# -- Recruit slots ---------------------------------------------------------

BEST_ATYPE: dict[Race, ArmyType] = {
    Race.HUMAN: ArmyType.LEGION,
    Race.ELVEN: ArmyType.BOWMEN,
    Race.DWARVEN: ArmyType.AXEMEN,
    Race.ORCISH: ArmyType.PHALANX,
}

NATIVE_ARMY_TYPE: dict[Race, ArmyType] = {race: army_type for army_type, race in MONSTROUS_ARMY_RACE.items()}


def home_first_slot(king_race: Race) -> ArmyType:
    """"home_first_slot: forced best_atype[king race]"."""

    return BEST_ATYPE[king_race]


def special_race_recruit_slot(race: Race) -> ArmyType:
    """"special_races: direct native unit type"."""

    return NATIVE_ARMY_TYPE[race]


def second_slot_gate_probability(tax: int) -> float:
    """The source's own separately-stated ``min(tax,8)/8``, kept for cross-checking."""

    return min(tax, 8) / 8


def second_slot_gate(tax: int, rng: PascalRandom) -> bool:
    """"condition: tax > (IRand AND 7)"."""

    return tax > (rng.irand() & 7)


# -- Initial army budgets ---------------------------------------------------

KING_HOME_BUDGET = 7


def draw_r4(rng: PascalRandom) -> int:
    """The source's own named "R4" primitive: uniform integer 1..4."""

    return 1 + (rng.irand() % 4)


def ordinary_humanoid_budget(tax: int, rng: PascalRandom) -> int:
    """"Human_Elf_Dwarf_Orc_nonhome: 1 + trunc(0.9*tax*U)"."""

    return 1 + int(0.9 * tax * rng.random())


def whale_budget(tax: int, rng: PascalRandom) -> int:
    """"Whale: tax + 1 + R4"."""

    return tax + 1 + draw_r4(rng)


def flying_or_special_budget(tax: int, rng: PascalRandom) -> int:
    """"Eagle_Dragon_Merman_Ent_Werefolk: tax + R4a - R4b"."""

    return tax + draw_r4(rng) - draw_r4(rng)


MAX_ARMIES_PER_PROVINCE_PASS = 4


def _base_strength_lookup(army_type: ArmyType) -> int:
    return BASE_STRENGTH[army_type]


def build_initial_armies(
    slot0: ArmyType | None,
    slot1: ArmyType | None,
    budget: int,
    strength_of: Callable[[ArmyType], int] | None = None,
) -> list[ArmyType]:
    """The confirmed creation loop: alternate slots, spend budget, stop at 4 or when unaffordable."""

    if strength_of is None:
        strength_of = _base_strength_lookup

    if slot0 is None:
        return []

    slots: list[ArmyType | None] = [slot0, slot1]
    current = 0
    remaining = budget
    armies: list[ArmyType] = []

    while len(armies) < MAX_ARMIES_PER_PROVINCE_PASS:
        candidate = slots[current]
        cost = strength_of(candidate)
        if cost > remaining:
            break
        armies.append(candidate)
        remaining -= cost
        other = 1 - current
        current = current if slots[other] is None else other

    return armies


# -- Commander + defaults ---------------------------------------------------

COMMANDER_NONE = 255
INITIAL_ARMY_QUALITY = Quality.AVERAGE


def resolve_commander(owner_leader_id: int | None, is_king_home: bool) -> int:
    """"lord_owned_province: owner leader id"; "King_Home"/"unowned_province": 255."""

    if is_king_home or owner_leader_id is None:
        return COMMANDER_NONE
    return owner_leader_id
