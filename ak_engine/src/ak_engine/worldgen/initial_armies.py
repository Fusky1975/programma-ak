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
  ``KING_HOME_BUDGET = 7`` (the original disassembly-confirmed value --
  see this constant's own Phase 987 docstring for why Phase 985's
  brief ``8`` correction was actually masking a different bug);
  ``draw_r4()`` (uniform integer ``1..4``, the
  source's own named "R4" primitive); ``whale_budget()`` (``tax + 1 +
  R4``); ``flying_or_special_budget()`` (``tax + R4a - R4b``, two
  independent R4 draws, left unclamped exactly as the source gives
  it -- a low-tax province can get a small or even negative budget,
  which `build_initial_armies()` naturally resolves to zero armies
  rather than needing a special case).

  **``ordinary_humanoid_budget()``, corrected by Phase 902 (``TROLL.md``,
  2026-09-25, a byte-level disassembly of this exact ``province_army_
  routine`` 0B57:A400's own default budget branch, raw 216B0-21723)**:
  the real formula is ``Trunc(ptax * (0.9 - 0.25*Random)) + 1`` --
  **subtraction from a constant, not multiplication by a uniform
  fraction**. The previously-shipped ``1 + trunc(0.9*tax*U)`` (undated,
  inherited from this module's own original Phase 358 sourcing) was
  never independently verified against the compiled bytes and is wrong:
  it lets the factor range over the full ``[0, 0.9)``, while the real
  factor is confined to ``[0.65, 0.9)`` -- a materially narrower, always-
  generous range. Confirmed instruction-by-instruction, including the
  sign of the subtraction (``TROLL.md``'s own "Verifica decisiva del
  segno" section, tracing the real runtime's operand-swap convention at
  raw 599AB) and the real ``0.9`` constant's own exact Real48 value
  (``494780232499/549755813888``, indistinguishable from the plain
  float ``0.9`` at any realistic tax magnitude). ``Random`` here is the
  bare ``PascalRandom.random()`` call (the runtime's own real-valued
  ``Random``, not ``IRand``'s further integer scaling) -- matching the
  "no dedicated caller reduction" convention this file's own ``draw_r4()``
  already established for a different real primitive.

  **This same disassembly also closes the separate, previously-genuine
  "Trollish has no budget formula" gap** (see ``worldgen/generate_
  new_game.py``'s own Phase 902 addendum): race code 10 (Trollish) has
  no dedicated ``CASE`` branch in this routine's own race dispatcher at
  all -- it falls through to the exact same default branch as an
  ordinary humanoid province (races 0-3, never special-cased either).
  ``ordinary_humanoid_budget()`` is therefore the real, byte-confirmed
  formula for Trollish too, not a separate one -- the function's own
  name stays humanoid-flavored (its primary, original use), but a
  Trollish caller reusing it is not a mismatch; it is the same compiled
  code path.
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
- ``fleet_second_slot_chance()``/``fleet_second_slot_gate()`` (Phase
  776, backlog item #22): ``Desktop/AKGEN 0xEB8A.md`` reveals a second
  mechanism inside the same tax routine's own tail (``0xEB8A`` calls
  ``0B57:9CD8``, raw ``0xF223-0xF243``, the real initializer of a
  province's two recruit slots, ``pat[x,y,0..1]``) -- once ``second_
  slot_gate()`` above has already decided a second unit exists at all,
  a real Real48 table decides whether that unit specifically becomes a
  Fleet (``ArmyType.FLEET``), indexed by the *same* ``effective_sea_
  neighbors`` value ``worldgen/province_tax.py compute_edge_score()``
  already computes (called ``edge_score`` there) -- "È essenziale
  passare alla seconda routine lo stesso `effective_sea_neighbors` già
  calcolato, senza ricontare i vicini o consumare un nuovo `Random` di
  bordo," so this function takes that same int directly, no new
  computation: ``{0: 0%, 1: 0%, 2: 50%, 3: 70%, 4: 100%, 5: 50%, 6:
  70%}``. **Deliberately shipped as a standalone primitive, not wired
  into ``generate_new_game.py``'s own pipeline** -- the exact same
  status ``second_slot_gate()``/``ordinary_humanoid_budget()``/
  ``draw_r4()`` immediately above already have, for the identical
  reason: the land-side ``humanoid_first_slot`` table below remains
  genuinely unsourced, so no ordinary-humanoid-province recruit-slot
  pipeline exists yet for this to plug into either. See ``worldgen/
  province_tax.py``'s own Phase 776 addendum for the sibling half of
  this same finding. **Superseded, Phase 798**: the table itself
  (``FLEET_SECOND_SLOT_CHANCE``/``fleet_second_slot_chance()``) was
  always correct -- only ``fleet_second_slot_gate()``'s own comparison
  mechanism (a flat ``rng.random() < chance`` roll) was wrong; see the
  Phase 798 bullet below for the real, corrected comparison.
- ``humanoid_first_slot()``/``province_random()``/``_draw_humanoid_
  terrain_ordinal()`` (Phase 797, closes the land-side half of backlog
  #22 the bullet above left open): ``Desktop/COASTFLEET.md``
  (2026-09-13), a disassembly of ``AKGEN.EXE`` raw ``0x20E18-0x214FF``
  (``0B57:9CD8``, the *same* real routine the bullet above already
  cites for the Fleet-second-slot table), supplies the missing first-
  slot formula for Human/Elven/Dwarven/Orcish provinces:
  ``if OwnerField[x,y] < KingCountField then first := best_atype[race]
  else begin case effective_terrain of Plains: first :=
  Trunc(4*ProvinceRandom(x,y))+1; Jungle,Forest,Mtns: repeat first :=
  Trunc(4*ProvinceRandom(x,y))+1 until first<>Phalanx; Desert: repeat
  first := Trunc(4*ProvinceRandom(x,y)+1) until first<>Axemen; end;
  coin := Trunc(2*Random); if coin=1 then first := best_atype[race];
  end;``. ``ProvinceRandom(x,y)`` (section 3, raw ``0x20A08-0x20AB5``)
  is not uniform -- 2% plain ``Random``, 98% biased by ``(x mod 2, y
  mod 2)`` quadrant parity -- but two real facts simplify it here
  without approximating it: (1) every call inside the terrain ``case``
  above only ever happens in the *already-known-False* branch of the
  outer ``OwnerField<KingCountField`` check, so ``ProvinceRandom``'s
  own internal copy of that same check can never fire from this call
  site, reducing it to a clean two-branch draw -- the primitive is
  still built with the full, faithful ``initially_owned_by_king``
  signature rather than hand-simplified, it just never needs ``True``
  from this one call site; (2) ``OwnerField[x,y] < KingCountField`` is
  provably RNG-consumption-neutral for this project's own pipeline
  regardless of its unconfirmed literal AKGEN identity -- a King Home
  coordinate is a zero-draw short-circuit on both sides of the mapping
  question (``home_first_slot()``, Phase 358, already gives an
  identical result with zero draws), so King Home coordinates are
  simply excluded from the new call site entirely
  (``worldgen/generate_new_game.py``'s own new ``recruit1_grid`` pass).
  ``ARMY_TYPE_BY_ORDINAL`` (``models/army_type.py``) already gives
  exactly COASTFLEET's own ``1:Bowmen,2:Axemen,3:Phalanx,4:Legion``
  table -- no new lookup needed. The coin flip (raw ``0x4A08A``) is a
  single plain ``Random`` draw, not ``IRand``, matching this project's
  own existing "moneta" idiom (e.g. ``draw_second_companion_race()``).
  **Race scope**: ``HUMANOID_FIRST_SLOT_RACES`` is the real
  ``race<=Orcish`` domain with Rohan (``race=14``) excluded per the
  user's own direct request ("è di una variante di gioco che non mi
  interessa al momento") -- a deliberate scope cut, not a sourcing gap;
  ``draw_base_race()`` never produces ``Race.ROHAN`` for an ordinary
  province anyway, so excluding it costs nothing. **Structurally
  inapplicable, not implemented**: the Swamp/``DS:C3DA=10``/coin=0 ->
  Marauders exception (section 5) -- this project's ``Terrain`` enum
  has exactly 7 members, no ``SWAMP``, the same "structurally
  unreachable" precedent already used in ``turn/random_encounter.py
  habitat_accepts()`` (Phase 707); the primary-Sea-with-secondary-
  terrain (``pt2``) redirect (section 2) -- moot here, since
  ``draw_base_race()`` never assigns a humanoid race to Sea terrain in
  this project, so ``humanoid_first_slot()`` is only ever reached for
  the 5 ordinary land terrains already in ``province_tax.py
  ORDINARY_LAND_MAX``. **Deliberately still open, a real, separate,
  NOT-attempted-here gap**: the *second* recruit slot for an ordinary
  humanoid province, and the newly-found fact (COASTFLEET.md section 9)
  that the real Fleet-second-slot comparison is ``ProvinceRandom(x,y) <
  fleetThreshold[index]`` rather than a plain uniform roll -- which
  would make the already-shipped Phase 776 ``fleet_second_slot_gate()``
  (built from a *different* document, ``AKGEN 0xEB8A.md``) an
  approximation of the real per-coordinate-parity probability. Not
  touched this phase: ``fleet_second_slot_gate()`` is still unwired
  into any real pipeline today, so there is no live behavior to
  regress; correcting it is separate, future work. **Corrected, Phase
  798** -- see that phase's own bullet below. **The second recruit
  slot's own "ordinary" type itself is no longer open either, Phase
  799** -- see ``ordinary_second_army()``'s own bullet below.
- ``fleet_second_slot_gate()`` (Phase 798) -- corrects Phase 776's own
  flat-probability approximation with COASTFLEET.md's real, parity-
  biased comparison: ``ProvinceRandom(x,y) < fleetThreshold[index]``
  (sections 9.2/10.3), plus a real Desert exception (0%, zero draws,
  terrain checked before any ``ProvinceRandom`` call). See ``fleet_
  second_slot_gate()``'s own docstring for the full account.
- ``ordinary_second_army()``/``humanoid_second_slot()`` (Phase 799,
  closes backlog #22 in full): ``Desktop/SECONDARMY.md`` (2026-09-14)
  supplies the real, previously-unsourced "ordinary second army" type
  for when a humanoid province's second recruit slot exists (Phase
  358's ``second_slot_gate()``, "B") but isn't a Fleet (Phase 776/798's
  ``fleet_second_slot_gate()``, "F") -- both of which had never had a
  real caller anywhere in this project until this phase. The document's
  own worked "B" probability table matches ``second_slot_gate()``'s own
  ``min(tax,8)/8`` exactly, confirming the two are the same gate; its
  own base-draw ordinals (5-10) match ``models/army_type.py ARMY_TYPE_
  BY_ORDINAL`` exactly (Lt Cavalry/Hvy Cavalry/Chariots/Elephants/Camel
  Corps/Wargriders), needing no new lookup table. ``humanoid_second_
  slot()`` combines all three primitives (B, then F, then the ordinary
  helper) and is wired into ``generate_new_game.py``'s own ``recruit1_
  grid`` pass (renamed in spirit to also build ``recruit2_grid``), this
  phase, closing backlog item #22's own last open piece. Rohan, Swamp,
  and this same helper's own Sea-forcing sub-branch stay unimplemented,
  for the same already-established reasons documented on ``humanoid_
  first_slot()``/``fleet_second_slot_gate()`` above (no Rohan-race
  provinces, no Swamp terrain, no humanoid race ever on Sea terrain in
  this project's own generator).

- ``necromantic_home_first_army_is_skeletal()`` (Phase 903, closes the
  ``necromantic_home_exception`` gap): user-confirmed, 2026-09-25 --
  "un Re di allineamento UNDEAD ottiene un primo esercito Scheletrico"
  (the Home province's own first recruit slot, i.e.
  ``home_first_slot(king.race)``/``army_types[0]`` from
  ``build_initial_armies()``'s own slot-0-first alternation -- a
  Human Undead King's is a Skeletal Legion, an Elf Undead King's a
  Skeletal Bowmen, and so on for Dwarven/Orcish). The "qualifying King
  property" is the King's own Kingdom's ``Alignment`` being ``UNDEAD``
  -- this project's own pre-existing "Re Non-Morto" concept ([4.2.5],
  ``turn/plan_dispatch.py _is_undead_king()``), not a new one invented
  for this. Independently corroborated (not just user say-so) by
  ``models/game_state.py ArmyState.is_skeletal``'s own pre-existing
  docstring, which already cites ``RUMORS.PAS:354``'s own
  ``lalign[armykng] = Undead`` check sitting right alongside the real
  ``Zomboid`` army-state marker -- this is that exact same check,
  simply newly wired to a real caller. Only the ``is_skeletal`` marker
  changes; the army's own type/quality/budget are unaffected -- neither
  the user's confirmation nor the source material names any other
  change.

**Deliberately NOT implemented here**, each a genuine, separately
documented gap:

- ~~The ``extra_mercenary_band`` (one per King, found via "radii 1..6"
  radial search from Home with up to 100 retries) -- this needs the
  whole generated map plus a real distance-radius search, a spatial
  algorithm in the same vein as `place_map` (Phase 354) and the
  special-race overwrite pass (Phase 355's own documented gap); not
  requested to be turned into a project-original algorithm this
  time, so left as a documented gap like Phase 357's independent-lord
  placement order.~~ -- **stale as of Phase 900 (this sibling bullet
  was never revisited)**: `worldgen/mercenary_band.py find_mercenary_
  recruit_type()` (Phase 363) is exactly that spatial algorithm, and
  `generate_new_game.py` wires it in as of Phase 892 -- see that
  module's own Phase 892 addendum for the full derivation. Nothing
  left open in this bullet.

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

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ARMY_TYPE_BY_ORDINAL, BASE_STRENGTH, MONSTROUS_ARMY_RACE, ArmyType
from ak_engine.models.map import Terrain
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


# Phase 776 (backlog item #22): `Desktop/AKGEN 0xEB8A.md`'s own real
# Real48 table for placing `ArmyType.FLEET` in a province's second
# recruit slot -- see module docstring's own Phase 776 addendum for
# the full sourcing, RNG-reuse note, and deliberately-unwired scope.
FLEET_SECOND_SLOT_CHANCE: dict[int, float] = {0: 0.0, 1: 0.0, 2: 0.5, 3: 0.7, 4: 1.0, 5: 0.5, 6: 0.7}


def fleet_second_slot_chance(effective_sea_neighbors: int) -> float:
    """The real table above, keyed by the same ``effective_sea_neighbors``
    (``edge_score``) value ``worldgen/province_tax.py compute_edge_
    score()`` already computes -- reuse it, don't recompute it. Defaults
    to ``0.0`` for any value outside the confirmed real ``0..6`` domain.
    """

    return FLEET_SECOND_SLOT_CHANCE.get(effective_sea_neighbors, 0.0)


def fleet_second_slot_gate(
    terrain: Terrain,
    x: int,
    y: int,
    effective_sea_neighbors: int,
    rng: PascalRandom,
) -> bool:
    """Whether an already-gated second recruit slot (``second_slot_
    gate()`` above) specifically becomes a Fleet.

    Phase 798, ``Desktop/COASTFLEET.md`` sections 9.2/10.3: the real
    comparison is ``ProvinceRandom(x,y) < fleetThreshold[index]`` -- the
    same parity-biased helper as ``province_random()`` above, not a
    flat uniform roll -- superseding Phase 776's own flat-probability
    approximation (``rng.random() < chance``, built from a *different*
    document, ``AKGEN 0xEB8A.md``). ``fleet_second_slot_chance()``'s
    own table needed no change -- only the comparison mechanism was
    wrong, not the table itself.

    Desert never places Fleet in the second slot (section 10.3's own
    confirmed flat 0%) -- the real terrain check happens *before* any
    ``ProvinceRandom`` call, so Desert consumes zero draws for this
    decision, mirroring ``_draw_humanoid_terrain_ordinal()``'s own
    "unsupported terrain raises" convention for Sea/``NO_TERRAIN``:
    this function is only ever reachable, by construction, for the
    same 5 ordinary land terrains ``humanoid_first_slot()`` already
    covers (no humanoid race ever lands on Sea terrain in this
    project's own generator).

    One thing COASTFLEET.md also describes but is structurally
    inapplicable to this project's own pipeline (documented, not
    implemented, mirroring the exact "moot here" reasoning already
    used for the ``pt2``/Sea-humanoid-race exclusion): the "alternate
    helper" (raw ``20ACE``, section 10.1) can deterministically force
    Fleet for a Sea province with a valid secondary terrain and
    ``race<=Orcish``, with no ``ProvinceRandom`` draw at all -- never
    reachable here, since ``draw_base_race()`` never assigns a
    humanoid race to Sea terrain.

    **Wired, Phase 799**: this function is no longer a standalone,
    unwired primitive -- ``humanoid_second_slot()`` (below) combines it
    with ``second_slot_gate()`` and the now-real ``ordinary_second_
    army()`` (``Desktop/SECONDARMY.md``) into the full second-slot
    chain, called from ``generate_new_game.py``'s own per-province
    pipeline for every ordinary humanoid province.
    """

    if terrain is Terrain.DESERT:
        return False
    if terrain in (Terrain.PLAINS, Terrain.JUNGLE, Terrain.FOREST, Terrain.MTNS):
        return province_random(x, y, rng) < fleet_second_slot_chance(effective_sea_neighbors)
    raise ValueError(f"fleet_second_slot_gate: unsupported terrain {terrain!r}")


# Phase 797 (backlog item #22, land-side half): `Desktop/COASTFLEET.md`'s
# own real terrain-weighted first-slot table for an ordinary (non-Home,
# non-special-race) humanoid province -- see module docstring's own
# Phase 797 addendum for the full sourcing (`ProvinceRandom`'s parity
# bias, the Rohan exclusion, the Swamp/Marauders structural-
# inapplicability note).
def province_random(x: int, y: int, rng: PascalRandom, *, initially_owned_by_king: bool = False) -> float:
    """"ProvinceRandom(x,y)": a real, non-uniform draw -- 2% plain, 98%
    biased into the ``(x mod 2, y mod 2)`` quadrant. Always consumes
    exactly one or two ``rng.random()`` calls, never ``irand()``, per
    the real function's own shape. ``initially_owned_by_king`` is part
    of the faithful port of the real signature, but this project's own
    call site (``humanoid_first_slot`` below) never needs ``True`` --
    King Home coordinates are excluded from that call site entirely
    (see module docstring).
    """

    test = rng.random()
    if test < 0.02 or initially_owned_by_king:
        return rng.random()
    u = rng.random()
    parity = (x & 1) + 2 * (y & 1)
    return (u + parity) * 0.25


# The ordinal each terrain's own rejection loop excludes -- Phalanx=3
# for Jungle/Forest/Mtns, Axemen=2 for Desert; Plains has no entry (no
# rejection).
_TERRAIN_ORDINAL_REJECT: dict[Terrain, int] = {
    Terrain.JUNGLE: 3,
    Terrain.FOREST: 3,
    Terrain.MTNS: 3,
    Terrain.DESERT: 2,
}


def _draw_humanoid_terrain_ordinal(terrain: Terrain, x: int, y: int, rng: PascalRandom) -> int:
    """The per-terrain first-slot ordinal draw, before the coin-flip
    override -- see ``humanoid_first_slot()``. Only ever reached for
    the 5 ordinary land terrains (see module docstring for why Sea
    never reaches this).
    """

    if terrain is Terrain.PLAINS:
        return int(4 * province_random(x, y, rng)) + 1
    reject = _TERRAIN_ORDINAL_REJECT.get(terrain)
    if reject is None:
        raise ValueError(f"humanoid_first_slot: unsupported terrain {terrain!r}")
    if terrain is Terrain.DESERT:
        while True:
            ordinal = int(4 * province_random(x, y, rng) + 1)
            if ordinal != reject:
                return ordinal
    while True:
        ordinal = int(4 * province_random(x, y, rng)) + 1
        if ordinal != reject:
            return ordinal


# The real `race<=Orcish` domain -- Rohan excluded per the user's own
# direct request (a game variant not currently of interest), not a
# sourcing gap; see module docstring.
HUMANOID_FIRST_SLOT_RACES: tuple[Race, ...] = (Race.HUMAN, Race.ELVEN, Race.DWARVEN, Race.ORCISH)


def ordinary_second_army(
    terrain: Terrain,
    race: Race,
    x: int,
    y: int,
    rng: PascalRandom,
    *,
    special: bool = False,
) -> ArmyType:
    """"SECONDARMY.md" sections 3-8 -- the ordinary (non-Fleet) second
    recruit slot for a humanoid province, once ``second_slot_gate()``
    has already decided a second army exists and ``fleet_second_slot_
    gate()`` has already decided it isn't a Fleet. Always draws a base
    type from Lt Cavalry/Hvy Cavalry/Chariots (``ARMY_TYPE_BY_ORDINAL``
    indices 5-7), consumed unconditionally even when a later
    substitution overwrites it, then applies race/terrain substitutions
    in the real fixed order: Orcish -> Wargriders (a coin, terminates
    the chain), Jungle -> Elephants, Desert -> Camel Corps, Plains/Mtns
    on map rows 2/3/5/6 -> Camel Corps (a fresh threshold draw, not a
    coin), Forest -> no substitution. ``special`` is always ``False``
    for this project's own one real call path (the document's own
    section 0 confirms the external caller always passes ``false``) --
    kept as a faithful, documented parameter rather than hand-simplified
    away, mirroring ``province_random()``'s own ``initially_owned_by_
    king`` precedent (Phase 797).
    """

    second = ARMY_TYPE_BY_ORDINAL[int(3 * province_random(x, y, rng)) + 5]
    if race is Race.ORCISH:
        coin = int(2 * rng.random())
        if special or coin == 1:
            return ArmyType.WARG_RIDERS
    if terrain is Terrain.JUNGLE:
        coin = int(2 * rng.random())
        return ArmyType.ELEPHANTS if coin == 1 else second
    if terrain is Terrain.DESERT:
        coin = int(2 * rng.random())
        return ArmyType.CAMEL_CORPS if (coin == 1 and not special) else second
    if terrain in (Terrain.PLAINS, Terrain.MTNS):
        if not special and y in (2, 3, 5, 6) and province_random(x, y, rng) < 0.20:
            return ArmyType.CAMEL_CORPS
        return second
    if terrain is Terrain.FOREST:
        return second
    raise ValueError(f"ordinary_second_army: unsupported terrain {terrain!r}")


def humanoid_second_slot(
    terrain: Terrain,
    race: Race,
    x: int,
    y: int,
    tax: int,
    effective_sea_neighbors: int,
    rng: PascalRandom,
) -> ArmyType | None:
    """"SECONDARMY.md" section 2 -- the real B-then-F-then-helper chain
    for a humanoid province's second recruit slot, combining three
    already-real primitives: ``second_slot_gate()`` (Phase 358, "B" --
    does a second army exist at all), ``fleet_second_slot_gate()``
    (Phase 776/798, "F" -- is it a Fleet), and ``ordinary_second_army()``
    above (the real, previously-unsourced remainder). ``None`` means the
    second slot stays noarmy (B failed).
    """

    if not second_slot_gate(tax, rng):
        return None
    if fleet_second_slot_gate(terrain, x, y, effective_sea_neighbors, rng):
        return ArmyType.FLEET
    return ordinary_second_army(terrain, race, x, y, rng)


def humanoid_first_slot(
    terrain: Terrain,
    race: Race,
    x: int,
    y: int,
    rng: PascalRandom,
    *,
    initially_owned_by_king: bool = False,
) -> ArmyType:
    """"COASTFLEET.md" sections 2/4/5/7 -- the ordinary-humanoid-province
    first recruit slot. ``initially_owned_by_king=True`` short-circuits
    to ``BEST_ATYPE[race]`` with zero draws; otherwise draws a terrain-
    weighted ordinal (rejecting Phalanx on Jungle/Forest/Mtns, Axemen on
    Desert), converts it via ``models.army_type.ARMY_TYPE_BY_ORDINAL``,
    then a single plain coin flip (``int(2*rng.random())``, not
    ``irand()``) can override the result to ``BEST_ATYPE[race]``. A
    ``race`` outside ``HUMANOID_FIRST_SLOT_RACES`` raises via the plain
    ``BEST_ATYPE[race]`` ``KeyError``, matching ``home_first_slot()``'s
    own existing no-guard style.
    """

    if initially_owned_by_king:
        return BEST_ATYPE[race]
    ordinal = _draw_humanoid_terrain_ordinal(terrain, x, y, rng)
    first = ARMY_TYPE_BY_ORDINAL[ordinal]
    coin = int(2 * rng.random())
    if coin == 1:
        return BEST_ATYPE[race]
    return first


# -- Initial army budgets ---------------------------------------------------

# Phase 985 had bumped this from 7 to 8, reasoning from only 2 real
# samples ("Legion, Light Cavalry, Legion" and "Bowmen, Heavy Cavalry,
# Bowmen") while assuming the King Home budget check spends each
# army's `BASE_STRENGTH` ("Str"), the same field the confirmed generic
# `build_initial_armies()` loop uses for ordinary/special-race
# provinces. Phase 987 found that assumption was the real bug, not the
# budget: every `BEST_ATYPE` (the Home's own first recruit slot) has
# `ARMY_TABLE[...].pay == 2`, and every real Home second-slot option
# (`LT_CAVALRY`/`HVY_CAVALRY`/`CHARIOTS`/`ELEPHANTS`/`FLEET`) has
# `pay` of 2 or 3 -- so spending `pay`, not `Str`, against a budget of
# **7** (2*2+2=6 or 2*2+3=7, either way too little remains for a 4th
# army) reproduces *both* real shapes exactly, and -- unlike Str-based
# spending -- provably reproduces exactly 3 armies for *every* possible
# King race x Home second-slot combination, not just the 2 directly
# observed. The original disassembly-confirmed ``7`` was right all
# along; see ``generate_new_game.py``'s own King Home call site for the
# ``pay``-based ``strength_of`` this budget is now paired with.
KING_HOME_BUDGET = 7


def draw_r4(rng: PascalRandom) -> int:
    """The source's own named "R4" primitive: uniform integer 1..4."""

    return 1 + (rng.irand() % 4)


def ordinary_humanoid_budget(tax: int, rng: PascalRandom) -> int:
    """The default budget branch of ``province_army_routine`` (0B57:A400)
    -- "Human_Elf_Dwarf_Orc_nonhome" and, per ``TROLL.md`` (Phase 902),
    Trollish too: ``Trunc(ptax * (0.9 - 0.25*Random)) + 1``. See module
    docstring's own Phase 902 addendum for the byte-level correction
    this replaced (the previous formula's ``0.9*tax*U`` was never
    independently verified and had the wrong shape).
    """

    return int(tax * (0.9 - 0.25 * rng.random())) + 1


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


def necromantic_home_first_army_is_skeletal(kingdom_alignment: Alignment) -> bool:
    """The ``necromantic_home_exception``, Phase 903 -- see module
    docstring's own Phase 903 addendum for the full derivation. Whether
    the King Home province's own first recruit-slot army (``army_types[0]``)
    should be raised Zomboid/Skeletal (``ArmyState.is_skeletal=True``)
    instead of an ordinary Hired one: exactly when the King's own
    Kingdom's ``Alignment`` is ``UNDEAD``.
    """

    return kingdom_alignment is Alignment.UNDEAD
