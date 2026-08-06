"""Master world-generation orchestrator (Phase 365): ``AKGEN.EXE``'s own
confirmed top-level pipeline order (``world_generation.
province_population_order``), tying every phase-352-364 formula
together into a real, populated ``GameState``.

Tenth and final phase of the pipeline-integration sub-plan (Phase
362-365), which itself closed the spatial gaps the original 352-361
world-generation sub-plan had deliberately left open.

**Confirmed exactly** -- the pipeline's own stage order, quoted
verbatim from ``world_generation.province_population_order``:

    "initialize every province as Sea, Norace, owner 255, tax 0 and
    two noarmy recruit slots", "generate/import terrain", "assign base
    native race, automatic tax and recruit slots per province",
    "overwrite accepted provinces with the seven special-race
    populations and recompute their tax", "place Kings, independent
    lords, companions and remaining mercenary heroes", "create
    province armies and one extra mercenary band per King", "create
    features and their feature-bound treasure/magic-item records"

``generate_new_game()`` realizes every one of those seven stages that
this project has a real, sourced formula for:

1. ``worldgen.place_map.generate_map()`` (Phase 354) -- terrain.
2. ``worldgen.province_races.draw_base_race()`` (Phase 355) -- base
   native race, for every province.
3. Tax: ``worldgen.province_tax.ordinary_land_tax()``/``true_sea_tax()``
   (Phase 356), dispatched by terrain (Sea vs. the five ordinary land
   terrains -- ``place_map`` never produces ``Terrain.NO_TERRAIN``, so
   ``NOTERR_TAX`` never actually applies to a generated map).
4. ``worldgen.special_race_placement.place_all_special_races()``
   (Phase 362) overwrites accepted provinces' race, then
   ``recompute_tax()`` overwrites their tax -- run as two full passes
   (placement, then a second pass recomputing tax for every accepted
   coordinate) rather than interleaved with placement's own attempts,
   since ``special_race_placement.py`` already made ``recompute_tax()``
   a standalone caller-invoked step, not part of ``place_special_race()``
   itself.
5. King Home placement: for each caller-supplied ``KingSetup``,
   ``worldgen.leader_placement.king_home_effects()`` (Phase 357)
   overwrites the Home province's owner/tax/race and the King leader's
   own ``location``/``birth_x`` (the ``leader_born_coord`` this formula
   returns -- ``LeaderState`` has no full born-*coordinate* field, only
   the birth *x* Phase 139 already modeled for Temper_Est, so only that
   component is set). **Phase 425 addendum**: also sets that King's own
   ``KingdomState.treasury`` to ``STARTING_TREASURY`` -- a real, sourced
   fact this pipeline never set at all before this phase (every
   ``KingdomState`` a caller builds defaults to ``treasury=0``), caught
   by an actual multi-turn playtest showing 0 gold at "turn 0" when the
   user's own real reference reports all show 10. Confirmed across four
   independent real Turn-0 "BIRTHRIGHT REPORT"/FINANCES sections
   (`SE0__T0.K0.txt` "Mathlon the Newby", `SE3__T0.K1`/`K2`/`K3`), every
   one showing "Gold in treasury: 10" verbatim -- distinct from
   `HOME_OVERRIDE_TAX=10` (Phase 356/357), which is those same reports'
   own separate "Expected Revenues: 10" line (the Home province's tax
   yield, not starting cash).
6. Initial armies: King Home provinces via
   ``worldgen.initial_armies.home_first_slot()`` + the confirmed
   ``KING_HOME_BUDGET=7`` (Phase 358); special-race provinces via
   ``special_race_recruit_slot()`` plus whichever of
   ``whale_budget()``/``flying_or_special_budget()`` covers that race
   (see the scoped-out Trollish gap below). Both feed the same
   confirmed ``build_initial_armies()`` creation loop.
7. Features: ``worldgen.feature_placement.place_all_features()``
   (Phase 364) for coordinates/monsters/types; the magic-item cursor
   (``worldgen.magic_item_placement.py``, Phase 360) in real
   feature-index order; internal magical location/power
   (``worldgen.internal_magical_locations.py``, Phase 361) against each
   feature's own real ``feature_index``/``feature_x``
   (``coord.x``)/``feature_type``; guardian Alignment via this
   project's own pre-existing ``models.monster.roll_monster_alignment()``
   (Phase 176), the same "confirmed, tested, previously unwired"
   mechanism ``turn/world_generation.py`` (Phase 246) already reuses
   for its own, unrelated feature-generation path.
8. **Independent lords + King companions (Phase 426)** -- "place Kings,
   independent lords, companions and remaining mercenary heroes"'s own
   remaining two roles, closing the gap Phase 365 originally left open
   (it had blocked on "no roster leader" and "no name generator"; both
   were closed in between by ``models.hero_roster.py`` (Phase 366, real
   ``LNAMES.PAS`` names) and ``worldgen.hero_talent_generation.py``
   (Phase 385, the real "Init Tr" alignment/skill/aptitude formula) but
   never wired back into this pipeline until now). For every id in
   ``range(leader_count)`` except the King ids and the reserved last
   slot, rolls a real ``Alignment``/``SkillTable`` via ``roll_alignment()``
   + ``roll_skill_and_aptitude_table()`` (matching the source's own
   "Init Tr runs before Place L" order: the *entire* pool's talents are
   rolled before any placement happens) and looks up its real
   ``STANDARD_HERO_ROSTER`` name. Independent lords then take the free
   humanoid provinces (``leader_placement.owner_leader_count()`` minus
   ``king_count``, via ``independent_lord_effects()`` -- ``kingdom_id=
   None``, the same "independent Hero" convention Phase 104 already
   established, since ``ProvinceState`` has no leader-level ownership
   field of its own to set separately from ``owner_kingdom_id``'s
   kingdom-level one). Each King then gets exactly
   ``COMPANIONS_PER_KING=2`` companions at their own Home
   (``kingdom_id`` = that King's own kingdom, first companion the
   King's own race, second via the already-confirmed
   ``draw_second_companion_race()``).

**Two selection-order details are project-original, not recovered**
(both already flagged as unsourced narratives by Phase 357, not newly
discovered gaps): which of the free humanoid provinces each lord lands
on, and which unused roster id fills which role. This project resolves
both deterministically -- provinces in this function's own existing
``grid`` iteration order (the same order the province-building loop
below already uses), roster ids in ascending numeric order -- rather
than leaving lords/companions unplaced. Treat the *identity* of which
specific Hero ends up where as a project-original convention, not a
recovered fact; the *counts*, *race rules*, and *talent formula* are
all real and sourced as described above.

**Deliberately NOT implemented here**, each a genuine, separately
documented gap carried over from the phases that already found it --
none invented past here:

- **Remaining mercenary heroes**: after lords and companions, any
  leftover roster ids (``remaining_mercenary_count()``) are simply never
  materialized as a ``LeaderState`` -- their non-``Earth_V`` "resting"
  location is confirmed absent from the source (only the ``Earth_V``-
  mode *repositioning* rule survived, not where an ordinary-mode
  mercenary starts before it), so inventing one would be a guess.
- **The reserved last roster id**: excluded from ``hero_pool`` entirely
  (no talents rolled, no ``LeaderState`` created) -- its own "attached
  separately to a Home" placement rule was already flagged by Phase 357
  as too ambiguous to code (this is the Valhalla-visitor-reserved slot,
  ``models/valhalla.py``'s own separate mechanic, not a King-loadable
  Hero).
- **Ordinary (non-Home, non-special-race) humanoid provinces' recruit
  slots and armies**: ``humanoid_first_slot``'s terrain-weighted
  infantry table was never sourced (Phase 358's own documented gap) --
  these provinces get a real race/tax but no recruit slot or army from
  this pipeline.
- **Trollish special-race armies**: ``budget_by_race_or_owner`` only
  covers King_Home, Human/Elf/Dwarf/Orc-nonhome, Whale, and
  Eagle/Dragon/Merman/Ent/Werefolk -- Trollish provinces get their
  correct recruit slot (``special_race_recruit_slot(Race.TROLLISH)``)
  but no budget formula to spend, so no army.
- **The ``necromantic_home_exception``** (a "qualifying King property"
  can mark the first Home army Zomboid/Skeletal) -- the source never
  states what makes a King property "qualifying" (Phase 358's own gap).
- **The extra mercenary band** (``worldgen.mercenary_band.py``, Phase
  363) -- its own "compatible recruit type" test and fallback type are
  caller-supplied by design, and the natural real inputs for both (the
  ordinary-province recruit-slot table above) are exactly the still-
  missing piece, so wiring it here would mean guessing both.

**Verification**: checked against a full, real-sized generation (18x9,
``king_count=10``) for internal consistency -- every one of the 162
provinces gets a real terrain/race/tax; every King Home has tax 10,
the King's own race, and a real initial-army list starting with
``BEST_ATYPE[king race]``; every King's own ``KingdomState.treasury``
is exactly ``STARTING_TREASURY`` (Phase 425); every special-race province's race matches
one of the seven confirmed special races and carries that race's own
native recruit slot; ``feature_count(gamevers)`` features exist, each
with a real coordinate/monster/type/alignment and a real (possibly
``MagicFeature.NONE``) magic location; the magic-item cursor assigns
treasures to exactly the confirmed ``item_slot_count()`` of them, in a
single shared cycling sequence; every King has exactly
``COMPANIONS_PER_KING`` companion ``LeaderState``s at their own Home,
each with a real name/``Alignment``/``SkillTable``, the first sharing
the King's own race and the second one of the other three humanoid
races; the independent-lord count matches
``owner_leader_count(...) - king_count`` exactly, each lord located at
a distinct free humanoid province with that province's own race.
"""

from __future__ import annotations

from dataclasses import dataclass

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.feature import Feature
from ak_engine.models.game_state import ArmyState, GameState, LeaderState, ProvinceState
from ak_engine.models.hero_roster import LEADER_COUNT_BY_GAME_VERSION, STANDARD_HERO_ROSTER
from ak_engine.models.kingdom import SkillTable
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.monster import roll_monster_alignment
from ak_engine.models.race import Race
from ak_engine.turn.movement import MapBounds
from ak_engine.worldgen.feature_placement import place_all_features
from ak_engine.worldgen.hero_talent_generation import roll_alignment, roll_skill_and_aptitude_table
from ak_engine.worldgen.initial_armies import (
    COMMANDER_NONE,
    INITIAL_ARMY_QUALITY,
    KING_HOME_BUDGET,
    build_initial_armies,
    flying_or_special_budget,
    home_first_slot,
    resolve_commander,
    special_race_recruit_slot,
    whale_budget,
)
from ak_engine.worldgen.internal_magical_locations import resolve_power, resolve_visible_location
from ak_engine.worldgen.leader_placement import (
    COMPANIONS_PER_KING,
    draw_second_companion_race,
    independent_lord_effects,
    king_home_effects,
    owner_leader_count,
)
from ak_engine.worldgen.magic_item_placement import (
    cursor_to_treasure,
    feature_gets_item_slot,
    initial_item_cursor,
    next_item_cursor,
)
from ak_engine.worldgen.pascal_random import PascalRandom
from ak_engine.worldgen.place_map import DEFAULT_HEIGHT, DEFAULT_WIDTH, generate_map
from ak_engine.worldgen.province_races import draw_base_race
from ak_engine.worldgen.province_tax import (
    compute_edge_score,
    coast_score,
    ordinary_land_tax,
    true_sea_tax,
)
from ak_engine.worldgen.special_race_placement import (
    SPECIAL_RACE_BASE_COUNT,
    place_all_special_races,
    recompute_tax,
)

# Phase 425: every King's own starting treasury -- confirmed verbatim
# ("Gold in treasury: 10") across four independent real Turn-0 reports
# (SE0__T0.K0.txt, SE3__T0.K1/K2/K3). See module docstring's own Phase
# 425 addendum for why this is distinct from HOME_OVERRIDE_TAX (that
# same reports' own separate "Expected Revenues: 10" line).
STARTING_TREASURY = 10

# Special-race army budget formula, by race -- see module docstring for
# why Trollish has no entry (no sourced budget formula).
_FLYING_OR_SPECIAL_BUDGET_RACES: frozenset[Race] = frozenset(
    {Race.DRAGONS, Race.EAGLES, Race.MERMISH, Race.ENTISH, Race.WEREFOLK}
)

# Phase 426: the four humanoid races -- provinces bearing one of these
# (after special-race overwrite and King Home overwrite) are the "H"
# province count leader_placement.owner_leader_count() takes, and the
# pool independent lords are placed into. Same set leader_placement.py's
# own private _HUMANOID_RACES already uses for draw_second_companion_race().
_HUMANOID_RACES: frozenset[Race] = frozenset({Race.HUMAN, Race.ELVEN, Race.DWARVEN, Race.ORCISH})

# Phase 426: default hero-roster size -- models.hero_roster's own
# confirmed "100 for game version 3 and earlier" (LNAMES.PAS's own
# leader_count by game version). This project's generate_new_game()
# only ever models the pre-Arcanes_V/pre-v4 pipeline (no gametyp
# parameter), so this is the only one of the three real values that
# applies here; a caller may still override it via leader_count=.
_DEFAULT_LEADER_COUNT = LEADER_COUNT_BY_GAME_VERSION["game_version_3_or_earlier"]


@dataclass(frozen=True, slots=True)
class KingSetup:
    """One caller-supplied King: the interactively-chosen leader/race/Home
    coordinate this project has no automatic generation for -- see module
    docstring. ``game_state.leaders[leader_id]`` must already exist with a
    real ``kingdom_id`` set (this orchestrator only mutates its
    ``location``/``birth_x``, never creates or reassigns kingdom
    membership).
    """

    leader_id: int
    race: Race
    home_coord: HexCoord


def _special_race_army_budget(race: Race, tax: int, rng: PascalRandom) -> int | None:
    """``None`` when this race's budget formula isn't sourced (Trollish)."""

    if race is Race.WHALES:
        return whale_budget(tax, rng)
    if race in _FLYING_OR_SPECIAL_BUDGET_RACES:
        return flying_or_special_budget(tax, rng)
    return None


def generate_new_game(
    rng: PascalRandom,
    game_state: GameState,
    kings: list[KingSetup],
    *,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    gamevers: int = 1,
    new_rules: bool = True,
    leader_count: int = _DEFAULT_LEADER_COUNT,
) -> GameState:
    """Runs the full sourced pipeline in-place against ``game_state``, returning it."""

    king_count = len(kings)
    bounds = MapBounds(width, height)
    grid = generate_map(rng, width=width, height=height, king_count=king_count)

    race_grid: dict[HexCoord, Race] = {coord: draw_base_race(terrain, rng) for coord, terrain in grid.items()}

    king_homes = [king.home_coord for king in kings]
    king_home_set = frozenset(king_homes)
    king_by_coord = {king.home_coord: king for king in kings}

    special_race_placements = place_all_special_races(
        grid, race_grid, bounds, king_home_set, rng, new_rules=new_rules
    )

    tax_grid: dict[HexCoord, int] = {}
    for coord, terrain in grid.items():
        if terrain is Terrain.SEA:
            coast = coast_score(coord, grid, bounds)
            is_edge_row = coord.y in (0, bounds.height - 1)
            edge = compute_edge_score(coast, is_edge_row, rng)
            tax_grid[coord] = true_sea_tax(edge, rng)
        else:
            tax_grid[coord] = ordinary_land_tax(terrain, rng)

    for placed_coords in special_race_placements.values():
        for coord in placed_coords:
            tax_grid[coord] = recompute_tax(coord, grid[coord], grid, bounds, bounds.height - 1, rng)

    for king in kings:
        effects = king_home_effects(king.leader_id, king.race, king.home_coord)
        race_grid[king.home_coord] = effects.province_race
        tax_grid[king.home_coord] = effects.province_tax
        leader = game_state.leaders[king.leader_id]
        leader.location = effects.leader_current_coord
        leader.birth_x = effects.leader_born_coord.x
        game_state.kingdoms[leader.kingdom_id].treasury = STARTING_TREASURY

    # Phase 426: independent lords + King companions ("place Kings,
    # independent lords, companions and remaining mercenary heroes",
    # world_generation.province_population_order stage 5) -- see module
    # docstring's own Phase 426 addendum for exactly what's implemented
    # here versus still deferred (mercenaries, the reserved roster slot).
    king_leader_ids = frozenset(king.leader_id for king in kings)
    reserved_roster_id = leader_count - 1
    hero_pool: dict[int, tuple[Alignment, SkillTable]] = {}
    for hero_id in range(leader_count):
        if hero_id in king_leader_ids or hero_id == reserved_roster_id:
            continue
        alignment = roll_alignment(rng)
        hero_pool[hero_id] = (alignment, roll_skill_and_aptitude_table(hero_id, alignment, rng))
    unused_hero_ids = iter(sorted(hero_pool))

    humanoid_coords = [coord for coord in grid if race_grid[coord] in _HUMANOID_RACES]
    lord_count = max(0, owner_leader_count(len(humanoid_coords), leader_count, king_count) - king_count)
    lord_coords = [coord for coord in humanoid_coords if coord not in king_home_set][:lord_count]

    for coord in lord_coords:
        hero_id = next(unused_hero_ids, None)
        if hero_id is None:
            break
        alignment, skills = hero_pool[hero_id]
        lord_effects = independent_lord_effects(hero_id, coord, race_grid[coord])
        game_state.add_leader(
            LeaderState(
                leader_id=hero_id,
                kingdom_id=None,
                name=STANDARD_HERO_ROSTER[hero_id],
                location=lord_effects.leader_current_coord,
                skills=skills,
                birth_x=lord_effects.leader_born_coord.x,
                alignment=alignment,
                race=lord_effects.leader_race,
            )
        )

    for king in kings:
        king_kingdom_id = game_state.leaders[king.leader_id].kingdom_id
        for companion_index in range(COMPANIONS_PER_KING):
            hero_id = next(unused_hero_ids, None)
            if hero_id is None:
                break
            alignment, skills = hero_pool[hero_id]
            companion_race = king.race if companion_index == 0 else draw_second_companion_race(king.race, rng)
            game_state.add_leader(
                LeaderState(
                    leader_id=hero_id,
                    kingdom_id=king_kingdom_id,
                    name=STANDARD_HERO_ROSTER[hero_id],
                    location=king.home_coord,
                    skills=skills,
                    birth_x=king.home_coord.x,
                    alignment=alignment,
                    race=companion_race,
                )
            )

    for coord, terrain in grid.items():
        race = race_grid[coord]
        tax = tax_grid[coord]
        is_king_home = coord in king_home_set

        recruit_type_1: ArmyType | None = None
        owner_kingdom_id: int | None = None
        army_types: list[ArmyType] = []

        if is_king_home:
            king = king_by_coord[coord]
            recruit_type_1 = home_first_slot(king.race)
            owner_kingdom_id = game_state.leaders[king.leader_id].kingdom_id
            army_types = build_initial_armies(recruit_type_1, None, KING_HOME_BUDGET)
        elif race in SPECIAL_RACE_BASE_COUNT:
            recruit_type_1 = special_race_recruit_slot(race)
            budget = _special_race_army_budget(race, tax, rng)
            if budget is not None:
                army_types = build_initial_armies(recruit_type_1, None, budget)

        game_state.provinces[coord] = ProvinceState(
            coord=coord,
            terrain=terrain,
            race=race,
            owner_kingdom_id=owner_kingdom_id,
            tax=tax,
            recruit_type_1=recruit_type_1,
        )

        commander = resolve_commander(None, is_king_home)
        commanded_by = None if commander == COMMANDER_NONE else commander
        for army_type in army_types:
            game_state.add_army(
                ArmyState(
                    army_id=game_state.new_army_id(),
                    kingdom_id=owner_kingdom_id,
                    army_type=army_type,
                    quality=INITIAL_ARMY_QUALITY,
                    location=coord,
                    commanded_by=commanded_by,
                )
            )

    placements = place_all_features(king_homes, king_count, grid, bounds, rng, gamevers=gamevers)
    cursor = initial_item_cursor(rng)
    for placement in placements:
        treasure = None
        if feature_gets_item_slot(placement.feature_index):
            treasure = cursor_to_treasure(cursor)
            cursor = next_item_cursor(cursor)

        magic_location = resolve_visible_location(
            placement.feature_type, placement.feature_index, placement.coord.x
        )
        magic_power = resolve_power(magic_location, placement.feature_index, placement.feature_type.value)

        game_state.add_feature(
            Feature(
                feature_id=game_state.new_feature_id(),
                coord=placement.coord,
                kind=placement.feature_type,
                guardian_monster=placement.monster,
                treasure=treasure,
                guardian_alignment=roll_monster_alignment(placement.monster, rng),
                magic_location=magic_location,
                magic_power=magic_power,
            )
        )

    return game_state
