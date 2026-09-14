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
   itself. **Phase 755**: ``recompute_tax()`` now also threads the
   placed race through, so a Whales/Mermish province recomputed here
   correctly picks up the real ``sea_race_tax_bonus()`` (+1/+2).
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
   yield, not starting cash). **Phase 427 addendum**: ``KingSetup.
   home_coord`` is now optional -- ``None`` triggers automatic selection
   via ``worldgen.king_home_placement.choose_king_home()``, a project-
   original (user-confirmed, not Pascal-sourced) fill for the real,
   confirmed-but-undocumented "distance/giocabilità" constraints the
   AKGEN material only ever names, never specifies (re-verified
   directly: no distance formula or scan order exists anywhere in that
   material). See that module's own docstring for the exact rules
   (minimum 3-hex separation, terrain never Sea/Desert, Naval-talent-
   gated sea-adjacency) and which three points came from the user's own
   direct clarification rather than being invented. An explicit
   ``home_coord`` still bypasses all of it, unchanged. **Phase 428
   addendum**: every King Home's own ``ProvinceState.explored_percent``
   (the shared scalar) and ``explored_percent_by_kingdom[owner_kingdom_id]``
   (the King's own per-kingdom entry) are now set to ``100`` -- confirmed
   verbatim ("Expl% 100%") across the same four independent real Turn-0
   PROVINCES sections cited above for Phase 425, spotted directly by the
   user re-reading the playtest report against those same real files.
   `worldgen.feature_placement.place_all_features()`'s own
   `first_2k_home_index()` (Phase 364) already correctly guaranteed
   exactly 2 features per King Home (also confirmed against the same
   four reports, each showing exactly 2 ADVENTURE entries for the Home
   province) -- the features were always there, just not yet fully
   visible in the ADVENTURE section (see the Phase 429 addendum right
   below for the second, separate field that closes that). **Phase 429
   addendum**: each King Home's own 2 pre-placed features now also get
   `Feature.discovered_by_kingdom[owner_kingdom_id] = 1` at creation
   time. `report/turn_report.py describe_adventure_report()` turned out
   to gate on a *different* field than the Phase 428 fix above assumed
   -- `Feature.discovery_level(kingdom_id) > 0`, not
   `explored_percent_by_kingdom` (that field only feeds the "(X%
   explored)" display text once a province already qualifies) -- caught
   by actually re-running the playtest after Phase 428 and finding the
   ADVENTURE section still empty. Level `1` ("detected, riches unknown")
   is confirmed exactly right: the same four real Turn-0 reports show a
   literal `"?"` next to each Home feature's own guardian, matching
   `describe_adventure_report()`'s own `discovery_level(kingdom_id) ==
   1` rendering rule precisely.
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
   **Phase 430 addendum**: two more real gaps closed, both spotted by
   the user directly comparing a playtest run against real Turn-0
   reports again. First, a King Home's own first-2K features could
   share the same guardian monster (``place_feature()``'s own draw had
   no occupancy tracking at all) -- the real reports never show this,
   so ``place_all_features()`` now excludes a King Home's already-used
   monsters from that Home's remaining draws (see ``worldgen/
   feature_placement.py``'s own Phase 430 note; project-original, the
   AKGEN material's own confirmed "duplicate non-Home coordinates are
   allowed" note never says anything about *monster* duplication, and
   only ever describes later-placement features anyway). Second, a
   gold-slot feature (``feature_gets_item_slot()`` false) previously
   got `treasure=None` outright -- `magic_item_placement.py`'s own
   confirmed "the other half get gold" was never actually implemented,
   only documented. It now draws uniformly among the 3 `GOLD_HOARD`
   tiers (unsourced which tier -- no AKGEN note covers it -- so a plain
   project-original uniform draw, `_GOLD_HOARD_TIERS`).
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

9. **The King's own initial ``SkillTable`` (Phase 430)** -- unlike a
   Hero's, a King's own talent allocation is a genuine player choice at
   signup (rulebook [2.1], supplied verbatim by the user), not a
   Pascal-RNG draw, so it can't be rolled the way ``hero_talent_
   generation.py`` rolls a Hero's. ``worldgen.king_talent.
   build_king_skill_table()`` is a new, deliberately standalone pure
   function (no ``PascalRandom`` parameter -- the whole formula is
   deterministic) implementing that rule text exactly: the caller's own
   `talent_allocation` (<=4 points total, <=2 per Ability) plus every
   King's automatic +1 Melee/Archery/Sage, the Divine/Undead White<->
   Necromancy overrides, and aptitude = min(5, skill+2) with the same
   two overrides forced to 0. **Not called by ``generate_new_game()``
   itself** -- the same "caller sets ``KingSetup``'s own pre-existing
   ``LeaderState.skills`` before calling in" architecture already
   established for ``home_coord``/``race`` (this function's own
   docstring confirms `game_state.leaders[leader_id]` "must already
   exist" with real data). A caller (a real signup flow, or this
   project's own playtest script) calls ``build_king_skill_table()``
   directly and assigns the result before ever calling
   ``generate_new_game()``. **Independently corroborated, not a fresh
   guess**: ``models/kingdom.py SkillTable``'s own Phase-21 docstring
   already stated this exact formula (aptitude = skill+2 max 5, same
   Divine/Undead overrides) and had already verified it against a real
   ``AK3__T1.K1`` skill line -- this phase is the first time that
   already-confirmed formula became callable code.

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
- **Ordinary (non-Home, non-special-race) humanoid provinces' first
  recruit slot and army**: **closed, Phase 797** (backlog #22's own
  land-side half) -- ``worldgen/initial_armies.py humanoid_first_slot()``
  now supplies the real, terrain-weighted first-slot table
  (``Desktop/COASTFLEET.md``), wired via the new ``recruit1_grid``
  pass and the ``elif race in _HUMANOID_RACES:`` branch below. The
  *second* recruit slot for these provinces remains a real, separate,
  NOT-attempted-here gap -- see ``worldgen/initial_armies.py``'s own
  Phase 797 addendum for what it is and why, plus a newly-found,
  deliberately-NOT-fixed discrepancy in the already-shipped Phase 776
  ``fleet_second_slot_gate()`` (a flat uniform roll where the real
  engine uses a parity-biased draw).
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
a real magic-item ``Treasure`` to exactly the confirmed
``item_slot_count()`` of them, in a single shared cycling sequence, and
every other feature gets a real ``GOLD_HOARD`` tier instead (Phase
430 -- every feature now carries a real ``Treasure``, never `None`);
no King Home's own two features ever share a guardian monster (Phase
430); every King has exactly
``COMPANIONS_PER_KING`` companion ``LeaderState``s at their own Home,
each with a real name/``Alignment``/``SkillTable``, the first sharing
the King's own race and the second one of the other three humanoid
races; the independent-lord count matches
``owner_leader_count(...) - king_count`` exactly, each lord located at
a distinct free humanoid province with that province's own race.
Re-verified after Phase 427 with ``home_coord=None`` for every King on
the same 18x9/``king_count=10`` map: every pair of auto-selected Homes
is at least ``MIN_HOME_DISTANCE`` hexes apart, every Home's own terrain
is never Sea/Desert, a King pre-marked Naval (a nonzero
``Ability.NAVAL`` skill) always lands on a Home with a real Sea
neighbor and gets ``ArmyType.FLEET`` as its second recruit slot, and a
non-Naval King's second slot always matches the terrain rule (Jungle ->
Elephants, otherwise Light Cavalry/Heavy Cavalry/Chariots) -- including
the Jungle/Elephants case, which required its own real-but-previously-
unwired ``ELEPHANTS_STRENGTH_RANGE`` fix (see ``_king_home_strength_of()``'s
own docstring) since ``build_initial_armies()``'s default strength
lookup has no fixed entry for Elephants' rulebook "variable" Str.
Re-verified after Phase 428: every King Home's own
``explored_percent``/``explored_percent_by_kingdom[owner_kingdom_id]``
equal exactly ``100``, and each Home carries exactly 2 features (the
same real Turn-0 reports cited in Phase 428's own addendum above each
show exactly 2 ADVENTURE entries per Home). Re-verified after Phase
429: each of those 2 features' own ``discovery_level(owner_kingdom_id)``
equals exactly ``1`` -- and, end-to-end, an actual
``report.turn_report.compose_letter_report()`` call for a fresh Home
now renders both features under ADVENTURE with a real ``"?"``, matching
the real reports exactly, instead of "None at present".
"""

from __future__ import annotations

from dataclasses import dataclass

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ARMY_TABLE, BASE_STRENGTH, ArmyType
from ak_engine.models.feature import Feature
from ak_engine.models.game_state import ArmyState, GameState, LeaderState, ProvinceState
from ak_engine.models.hero_roster import LEADER_COUNT_BY_GAME_VERSION, STANDARD_HERO_ROSTER
from ak_engine.models.kingdom import SkillTable
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.monster import roll_monster_alignment
from ak_engine.models.race import Race
from ak_engine.models.treasure import Treasure
from ak_engine.turn.movement import MapBounds
from ak_engine.turn.strength import ELEPHANTS_STRENGTH_RANGE
from ak_engine.worldgen.feature_placement import place_all_features
from ak_engine.worldgen.hero_talent_generation import roll_alignment, roll_skill_and_aptitude_table
from ak_engine.worldgen.initial_armies import (
    COMMANDER_NONE,
    INITIAL_ARMY_QUALITY,
    KING_HOME_BUDGET,
    build_initial_armies,
    flying_or_special_budget,
    home_first_slot,
    humanoid_first_slot,
    ordinary_humanoid_budget,
    resolve_commander,
    special_race_recruit_slot,
    whale_budget,
)
from ak_engine.worldgen.internal_magical_locations import resolve_power, resolve_visible_location
from ak_engine.worldgen.king_home_placement import choose_king_home, king_is_naval, second_recruit_slot
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
    """One caller-supplied King: the interactively-chosen leader/race, and
    optionally a Home coordinate -- see module docstring.
    ``game_state.leaders[leader_id]`` must already exist with a real
    ``kingdom_id`` set (this orchestrator only mutates its
    ``location``/``birth_x``, never creates or reassigns kingdom
    membership).

    **Phase 427**: ``home_coord`` is now optional. ``None`` means "pick
    it automatically" via ``worldgen/king_home_placement.py``'s own
    project-original (user-confirmed, not Pascal-sourced) rules --
    terrain never Sea/Desert, at least ``MIN_HOME_DISTANCE`` hexes from
    every other King's Home, and (if this King's own pre-set
    ``LeaderState.skills`` show Naval training) at least one Sea-
    adjacent neighbor. An explicit ``home_coord`` bypasses all of that
    and is honored as-is (this project's original "interactively-chosen"
    convention, unchanged) -- it still only needs to satisfy whatever
    the caller already trusts it to.
    """

    leader_id: int
    race: Race
    home_coord: HexCoord | None = None


def _special_race_army_budget(race: Race, tax: int, rng: PascalRandom) -> int | None:
    """``None`` when this race's budget formula isn't sourced (Trollish)."""

    if race is Race.WHALES:
        return whale_budget(tax, rng)
    if race in _FLYING_OR_SPECIAL_BUDGET_RACES:
        return flying_or_special_budget(tax, rng)
    return None


# Phase 430: see the gold-tier-assignment call site's own comment below.
_GOLD_HOARD_TIERS: tuple[Treasure, ...] = (
    Treasure.GOLD_HOARD_LARGE,
    Treasure.GOLD_HOARD_HUGE,
    Treasure.GOLD_HOARD_FABULOUS,
)


def _king_home_strength_of(rng: PascalRandom):
    """Phase 427: ``build_initial_armies()``'s own default ``strength_of``
    (``BASE_STRENGTH`` lookup) has no entry for ``ArmyType.ELEPHANTS`` --
    its rulebook "Str" is listed as "V" (variable), deliberately excluded
    from that fixed table (see ``models/army_type.py``'s own docstring).
    King Home's own second recruit slot can now genuinely be Elephants
    (a Jungle-terrain, non-Naval King), so this closure -- unlike the
    module-level default -- resolves that one case via the already-
    confirmed, already-used-elsewhere ``turn/strength.py
    ELEPHANTS_STRENGTH_RANGE`` (``turn/battle_orchestrator.py``'s own
    ``roll_elephants_strength()``), reimplemented against this project's
    own ``PascalRandom`` rather than the ``random.Random`` that function
    expects -- the same "same real range, different RNG on hand"
    adaptation this project already used elsewhere (e.g. ``leader_
    placement.py draw_second_companion_race()``).
    """

    def strength_of(army_type: ArmyType) -> int:
        if army_type is ArmyType.ELEPHANTS:
            low, high = ELEPHANTS_STRENGTH_RANGE
            return low + rng.irand() % (high - low + 1)
        return BASE_STRENGTH[army_type]

    return strength_of


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

    # Phase 780: record the real board size this world was actually built
    # at, so downstream turn-engine code no longer has to fall back to
    # `turn/movement.py NORMAL_MAP_BOUNDS` (confirmed the *Super-AK* size,
    # `Regolamento AK.txt` 12.1) for a "normale" 18x9 game.
    game_state.board_width = width
    game_state.board_height = height

    king_count = len(kings)
    bounds = MapBounds(width, height)
    grid = generate_map(rng, width=width, height=height, king_count=king_count)

    race_grid: dict[HexCoord, Race] = {coord: draw_base_race(terrain, rng) for coord, terrain in grid.items()}

    # Phase 427: resolve each King's own Home coordinate -- an explicit
    # KingSetup.home_coord is honored as-is; None triggers the
    # project-original (user-confirmed) automatic selection. Kept as a
    # separate lookup rather than mutating the frozen KingSetup.
    home_coord_by_king: dict[int, HexCoord] = {}
    for king in kings:
        if king.home_coord is not None:
            home_coord_by_king[king.leader_id] = king.home_coord
            continue
        naval = king_is_naval(game_state.leaders[king.leader_id].skills)
        home_coord_by_king[king.leader_id] = choose_king_home(
            grid, race_grid, bounds, list(home_coord_by_king.values()), rng, naval=naval
        )

    king_homes = [home_coord_by_king[king.leader_id] for king in kings]
    king_home_set = frozenset(king_homes)
    king_by_coord = {home_coord_by_king[king.leader_id]: king for king in kings}

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

    for race, placed_coords in special_race_placements.items():
        for coord in placed_coords:
            tax_grid[coord] = recompute_tax(coord, grid[coord], grid, bounds, bounds.height - 1, rng, race)

    # Phase 797 (backlog #22, land-side half): the ordinary-humanoid-
    # province first recruit slot, `COASTFLEET.md`'s own real terrain-
    # weighted table. Run right after race_grid reflects every special-
    # race overwrite (above) and before any King Home overwrite (below)
    # -- King Home coordinates are excluded here entirely, since a King
    # Home's own first slot is already `home_first_slot(king.race)`
    # (Phase 358), an RNG-neutral identical result (see module docstring
    # of worldgen/initial_armies.py for the proof). A special-race-
    # overwritten coordinate's race_grid entry is already the special
    # race by this point, so it's naturally skipped with no extra
    # bookkeeping.
    recruit1_grid: dict[HexCoord, ArmyType] = {}
    for coord, terrain in grid.items():
        if coord in king_home_set:
            continue
        race = race_grid[coord]
        if race in _HUMANOID_RACES:
            recruit1_grid[coord] = humanoid_first_slot(terrain, race, coord.x, coord.y, rng)

    for king in kings:
        home_coord = home_coord_by_king[king.leader_id]
        effects = king_home_effects(king.leader_id, king.race, home_coord)
        race_grid[home_coord] = effects.province_race
        tax_grid[home_coord] = effects.province_tax
        leader = game_state.leaders[king.leader_id]
        leader.location = effects.leader_current_coord
        leader.birth_x = effects.leader_born_coord.x
        leader.birth_y = effects.leader_born_coord.y
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
                birth_y=lord_effects.leader_born_coord.y,
                alignment=alignment,
                race=lord_effects.leader_race,
            )
        )

    for king in kings:
        king_kingdom_id = game_state.leaders[king.leader_id].kingdom_id
        home_coord = home_coord_by_king[king.leader_id]
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
                    location=home_coord,
                    skills=skills,
                    birth_x=home_coord.x,
                    birth_y=home_coord.y,
                    alignment=alignment,
                    race=companion_race,
                )
            )

    for coord, terrain in grid.items():
        race = race_grid[coord]
        tax = tax_grid[coord]
        is_king_home = coord in king_home_set

        recruit_type_1: ArmyType | None = None
        recruit_type_2: ArmyType | None = None
        owner_kingdom_id: int | None = None
        army_types: list[ArmyType] = []
        explored_percent = 0
        explored_percent_by_kingdom: dict[int, int] = {}

        if is_king_home:
            king = king_by_coord[coord]
            recruit_type_1 = home_first_slot(king.race)
            # Phase 427: the Home province's own second recruit slot --
            # see worldgen/king_home_placement.py's own module docstring
            # for the user-confirmed terrain/Naval-talent rules.
            naval = king_is_naval(game_state.leaders[king.leader_id].skills)
            recruit_type_2 = second_recruit_slot(terrain, rng, naval=naval)
            owner_kingdom_id = game_state.leaders[king.leader_id].kingdom_id
            army_types = build_initial_armies(
                recruit_type_1, recruit_type_2, KING_HOME_BUDGET, strength_of=_king_home_strength_of(rng)
            )
            # Phase 428: every King Home starts 100% explored (confirmed
            # verbatim -- "Expl% 100%" -- across four independent real
            # Turn-0 PROVINCES sections: SE0__T0.K0.txt "Acacia", SE3__
            # T0.K1/K2/K3 "the Dolphin Sea"/"Mongu"/"Ngara"). Both the
            # shared scalar (PROVINCES table) and the King's own kingdom
            # entry in the per-kingdom tracker (ADVENTURE section) are
            # set -- see describe_provinces_report()/describe_adventure_
            # report()'s own read sites in report/turn_report.py.
            explored_percent = 100
            explored_percent_by_kingdom = {owner_kingdom_id: 100}
        elif race in SPECIAL_RACE_BASE_COUNT:
            recruit_type_1 = special_race_recruit_slot(race)
            budget = _special_race_army_budget(race, tax, rng)
            if budget is not None:
                army_types = build_initial_armies(recruit_type_1, None, budget)
        elif race in _HUMANOID_RACES:
            # Phase 797 (backlog #22, land-side half): an ordinary
            # (non-Home, non-special-race) humanoid province -- mirrors
            # the SPECIAL_RACE_BASE_COUNT branch's own exact shape.
            # recruit_type_2/owner_kingdom_id stay None, matching every
            # other non-Home, non-owned province today.
            recruit_type_1 = recruit1_grid.get(coord)
            if recruit_type_1 is not None:
                budget = ordinary_humanoid_budget(tax, rng)
                army_types = build_initial_armies(recruit_type_1, None, budget)

        game_state.provinces[coord] = ProvinceState(
            coord=coord,
            terrain=terrain,
            race=race,
            owner_kingdom_id=owner_kingdom_id,
            tax=tax,
            recruit_type_1=recruit_type_1,
            recruit_type_2=recruit_type_2,
            explored_percent=explored_percent,
            explored_percent_by_kingdom=explored_percent_by_kingdom,
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
                    # Real per-turn movement rate (RULES.AK [6.3]) -- a
                    # freshly created army starts with a full pool, same as
                    # every later turn's own replenishment (`turn_processor.py
                    # run_turn()`'s own start-of-turn housekeeping).
                    movement_points=ARMY_TABLE[army_type].speed,
                )
            )

    # Phase 429: which King's own kingdom owns each Home coordinate --
    # used below to seed that King Home's own 2 features as already
    # "detected" (Feature.discovered_by_kingdom, level 1: "?" -- riches
    # unknown) for their own kingdom, matching the same real Turn-0
    # reports Phase 428 already cited: each shows both Home features
    # with a "?" in the Special column, not "None at present".
    kingdom_id_by_home_coord = {
        coord: game_state.leaders[king.leader_id].kingdom_id for coord, king in king_by_coord.items()
    }

    placements = place_all_features(king_homes, king_count, grid, bounds, rng, gamevers=gamevers)
    cursor = initial_item_cursor(rng)
    for placement in placements:
        if feature_gets_item_slot(placement.feature_index):
            treasure = cursor_to_treasure(cursor)
            cursor = next_item_cursor(cursor)
        else:
            # Phase 430: `feature_gets_item_slot()` only ever says
            # *which* half of the 4-gold/4-item repeating pattern a
            # feature falls in (magic_item_placement.py's own docstring:
            # "the other half get gold") -- it never assigns the actual
            # gold-tier treasure. Which of the 3 GOLD_HOARD tiers a gold
            # feature gets is unsourced (no AKGEN reverse-engineering
            # note covers it), so this is a project-original uniform
            # draw across the 3 tiers -- the same "no source, uniform
            # default" convention already used elsewhere in this module
            # (e.g. `second_recruit_slot()`'s own cavalry/chariots draw).
            treasure = _GOLD_HOARD_TIERS[rng.irand() % len(_GOLD_HOARD_TIERS)]

        magic_location = resolve_visible_location(
            placement.feature_type, placement.feature_index, placement.coord.x
        )
        magic_power = resolve_power(magic_location, placement.feature_index, placement.feature_type.value)

        discovered_by_kingdom: dict[int, int] = {}
        home_kingdom_id = kingdom_id_by_home_coord.get(placement.coord)
        if home_kingdom_id is not None:
            discovered_by_kingdom[home_kingdom_id] = 1

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
                discovered_by_kingdom=discovered_by_kingdom,
            )
        )

    return game_state
