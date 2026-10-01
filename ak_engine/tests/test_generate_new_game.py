from __future__ import annotations

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ARMY_TABLE, ArmyType
from ak_engine.models.enums import Ability
from ak_engine.models.game_state import GameState, KingdomState, LeaderState
from ak_engine.models.hero_roster import STANDARD_HERO_ROSTER
from ak_engine.models.kingdom import SkillTable
from ak_engine.models.magic_feature import MagicFeature
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.province_names import PROVINCE_NAME_POOLS
from ak_engine.models.power import Power
from ak_engine.models.race import Race
from ak_engine.turn.movement import MapBounds, hex_distance, neighbors
from ak_engine.worldgen.feature_generation import feature_count
from ak_engine.worldgen.generate_new_game import (
    STARTING_TREASURY,
    KingSetup,
    _special_race_army_budget,
    generate_new_game,
)
from ak_engine.worldgen.initial_armies import BEST_ATYPE, COMMANDER_NONE
from ak_engine.worldgen.king_home_placement import MIN_HOME_DISTANCE
from ak_engine.worldgen.leader_placement import COMPANIONS_PER_KING, owner_leader_count
from ak_engine.models.treasure import TREASURE_CATEGORY, TreasureCategory
from ak_engine.worldgen.magic_item_placement import item_slot_count
from ak_engine.worldgen.mercenary_band import hex_ring
from ak_engine.worldgen.pascal_random import PascalRandom
from ak_engine.worldgen.place_map import DEFAULT_HEIGHT, DEFAULT_WIDTH
from ak_engine.worldgen.province_tax import HOME_OVERRIDE_TAX
from ak_engine.worldgen.special_race_placement import SPECIAL_RACE_BASE_COUNT

_KING_RACES = [Race.HUMAN, Race.ELVEN, Race.DWARVEN, Race.ORCISH] * 3
_HUMANOID_RACES = {Race.HUMAN, Race.ELVEN, Race.DWARVEN, Race.ORCISH}
_NON_SEA_NON_DESERT_TERRAINS = {Terrain.PLAINS, Terrain.JUNGLE, Terrain.FOREST, Terrain.MTNS}


def _setup(king_count: int = 10) -> tuple[GameState, list[KingSetup]]:
    game_state = GameState()
    kings: list[KingSetup] = []
    for i in range(king_count):
        race = _KING_RACES[i % 4]
        home = HexCoord(i, 0)
        game_state.kingdoms[i] = KingdomState(
            kingdom_id=i, name=f"K{i}", race=race, alignment=Alignment.NEUTRAL, home_province=home
        )
        game_state.leaders[i] = LeaderState(
            leader_id=i, kingdom_id=i, name=f"King{i}", location=HexCoord(0, 0), is_king=True, race=race
        )
        kings.append(KingSetup(leader_id=i, race=race, home_coord=home))
    return game_state, kings


def test_generate_new_game_populates_every_province():
    game_state, kings = _setup()
    rng = PascalRandom(seed=1)
    result = generate_new_game(rng, game_state, kings, gamevers=1)

    assert len(result.provinces) == DEFAULT_WIDTH * DEFAULT_HEIGHT
    for coord, province in result.provinces.items():
        assert province.coord == coord
        assert province.terrain in Terrain
        assert province.race in Race
        assert province.tax >= 0


def test_generate_new_game_records_the_real_board_size_it_was_built_at():
    # Phase 780: the real "normale" default (18x9) must land on the
    # returned GameState itself, not just be used transiently to build
    # the map -- see turn/movement.py NORMAL_MAP_BOUNDS's own corrected
    # comment for why this used to matter (every downstream turn-engine
    # consumer fell back to the wrong, Super-AK 30x15 constant instead).
    game_state, kings = _setup()
    rng = PascalRandom(seed=1)
    result = generate_new_game(rng, game_state, kings, gamevers=1)

    assert result.board_width == DEFAULT_WIDTH
    assert result.board_height == DEFAULT_HEIGHT


def test_king_home_effects_are_applied_to_province_and_leader():
    game_state, kings = _setup()
    rng = PascalRandom(seed=2)
    result = generate_new_game(rng, game_state, kings, gamevers=1)

    for king in kings:
        province = result.provinces[king.home_coord]
        assert province.tax == HOME_OVERRIDE_TAX
        assert province.race is king.race
        assert province.owner_kingdom_id == king.leader_id
        assert province.recruit_type_1 == BEST_ATYPE[king.race]

        leader = result.leaders[king.leader_id]
        assert leader.location == king.home_coord
        assert leader.birth_x == king.home_coord.x


def test_undead_king_home_first_army_is_skeletal():
    # Phase 903 (necromantic_home_exception, user-confirmed 2026-09-25):
    # a King whose own Kingdom's Alignment is UNDEAD gets a Zomboid/
    # Skeletal first Home army (the Home province's own first recruit
    # slot, army_types[0]) instead of an ordinary Hired one. Every other
    # army at that same Home -- the second recruit-slot army, if any, and
    # the extra mercenary band (kingdom_id=None, excluded here the same
    # way test_king_home_gets_a_real_initial_army_using_best_atype()
    # excludes it) -- is unaffected.
    game_state, kings = _setup()
    game_state.kingdoms[0].alignment = Alignment.UNDEAD
    rng = PascalRandom(seed=3)
    result = generate_new_game(rng, game_state, kings, gamevers=1)

    undead_king = kings[0]
    undead_armies = [
        a for a in result.armies.values() if a.location == undead_king.home_coord and a.kingdom_id is not None
    ]
    assert undead_armies
    assert undead_armies[0].is_skeletal is True
    for army in undead_armies[1:]:
        assert army.is_skeletal is False

    ordinary_king = kings[1]
    ordinary_armies = [
        a for a in result.armies.values() if a.location == ordinary_king.home_coord and a.kingdom_id is not None
    ]
    assert ordinary_armies
    assert all(army.is_skeletal is False for army in ordinary_armies)


def test_king_home_gets_a_real_initial_army_using_best_atype():
    game_state, kings = _setup()
    rng = PascalRandom(seed=3)
    result = generate_new_game(rng, game_state, kings, gamevers=1)

    for king in kings:
        # Phase 892: the King's own Home coordinate can now also host that
        # King's own extra mercenary band (kingdom_id=None) -- excluded
        # here so this test keeps checking only the King's own armies; see
        # test_king_gets_a_real_extra_mercenary_band_at_home() below for
        # the mercenary band itself.
        armies = [a for a in result.armies.values() if a.location == king.home_coord and a.kingdom_id is not None]
        assert armies
        assert armies[0].army_type == BEST_ATYPE[king.race]
        for army in armies:
            assert army.commanded_by is None  # COMMANDER_NONE (255) translates to None
            assert army.kingdom_id == king.leader_id


def test_king_gets_a_real_extra_mercenary_band_at_home():
    # Phase 892: worldgen/mercenary_band.py's own extra-mercenary-band
    # search, wired into generate_new_game() for the first time -- one
    # real, uncommanded, kingdomless (this project's own established
    # "mercenary" convention) army per King, at that King's own Home.
    game_state, kings = _setup()
    rng = PascalRandom(seed=3)
    result = generate_new_game(rng, game_state, kings, gamevers=1)

    for king in kings:
        bands = [
            a for a in result.armies.values() if a.location == king.home_coord and a.kingdom_id is None
        ]
        assert len(bands) == 1
        band = bands[0]
        assert band.commanded_by is None
        assert isinstance(band.army_type, ArmyType)
        assert band.movement_points == ARMY_TABLE[band.army_type].speed


def test_extra_mercenary_band_type_is_compatible_or_fallback():
    # Phase 892: the band's own army_type must either be the documented
    # fallback (home_first_slot(king.race), i.e. BEST_ATYPE[king.race])
    # or a real recruit type actually present at some province within
    # the documented radius 1..6 search around that King's own Home --
    # proving the wiring genuinely consults real generated province data
    # rather than picking an arbitrary type.
    game_state, kings = _setup()
    rng = PascalRandom(seed=3)
    result = generate_new_game(rng, game_state, kings, gamevers=1)
    bounds = MapBounds(DEFAULT_WIDTH, DEFAULT_HEIGHT)

    for king in kings:
        band = next(a for a in result.armies.values() if a.location == king.home_coord and a.kingdom_id is None)
        nearby_types = set()
        for radius in range(1, 7):
            for coord in hex_ring(king.home_coord, radius, bounds):
                province = result.provinces.get(coord)
                if province is None:
                    continue
                if province.recruit_type_1 is not None:
                    nearby_types.add(province.recruit_type_1)
                if province.recruit_type_2 is not None:
                    nearby_types.add(province.recruit_type_2)
        assert band.army_type == BEST_ATYPE[king.race] or band.army_type in nearby_types


def test_every_generated_army_starts_with_a_full_movement_pool():
    # Phase 573: a freshly generated army used to start with
    # movement_points=0 (the dataclass default, never overridden here),
    # so its own very first real Move order would fail before a single
    # turn had even been processed. Every army generate_new_game()
    # creates should start with its own real per-turn rate instead.
    game_state, kings = _setup()
    rng = PascalRandom(seed=3)
    result = generate_new_game(rng, game_state, kings, gamevers=1)

    assert result.armies
    for army in result.armies.values():
        assert army.movement_points == ARMY_TABLE[army.army_type].speed


def test_special_race_provinces_get_their_own_native_recruit_slot():
    game_state, kings = _setup()
    rng = PascalRandom(seed=4)
    result = generate_new_game(rng, game_state, kings, gamevers=1)

    from ak_engine.worldgen.initial_armies import NATIVE_ARMY_TYPE

    found_any = False
    for province in result.provinces.values():
        if province.race in SPECIAL_RACE_BASE_COUNT:
            found_any = True
            assert province.recruit_type_1 == NATIVE_ARMY_TYPE[province.race]
            assert province.owner_kingdom_id is None
    assert found_any


def test_king_home_recruit_type_1_is_unaffected_by_the_new_ordinary_humanoid_pass():
    # Phase 797's own new recruit1_grid pass explicitly excludes King
    # Home coordinates -- proves the new pass doesn't clobber the
    # existing, real home_first_slot(king.race) result.
    from ak_engine.worldgen.initial_armies import home_first_slot

    game_state, kings = _setup()
    rng = PascalRandom(seed=2)
    result = generate_new_game(rng, game_state, kings, gamevers=1)

    for king in kings:
        province = result.provinces[king.home_coord]
        assert province.recruit_type_1 == home_first_slot(king.race)


def test_ordinary_humanoid_provinces_now_get_a_real_first_recruit_slot_and_army():
    # Phase 797 (backlog #22's land-side half): before this phase, an
    # ordinary (non-Home, non-special-race) humanoid province had a
    # real race/tax but recruit_type_1=None and no army at all.
    infantry = {ArmyType.BOWMEN, ArmyType.AXEMEN, ArmyType.PHALANX, ArmyType.LEGION}
    found_recruit_type = False
    found_army = False
    for seed in range(1, 15):
        gs, kings = _setup()
        rng = PascalRandom(seed=seed)
        result = generate_new_game(rng, gs, kings, gamevers=1)
        king_home_coords = {king.home_coord for king in kings}
        for coord, province in result.provinces.items():
            if coord in king_home_coords or province.race not in _HUMANOID_RACES:
                continue
            if province.recruit_type_1 is not None:
                found_recruit_type = True
                assert province.recruit_type_1 in infantry
                if [a for a in result.armies.values() if a.location == coord]:
                    found_army = True
        if found_recruit_type and found_army:
            break
    assert found_recruit_type
    assert found_army


def test_ordinary_humanoid_provinces_now_get_a_real_second_recruit_slot_too():
    # Phase 799 (backlog #22, closes it in full): before this phase, an
    # ordinary (non-Home, non-special-race) humanoid province's second
    # recruit slot always stayed None -- `Desktop/SECONDARMY.md` supplies
    # the real "ordinary" (non-Fleet) type, combined with the already-
    # real second_slot_gate()/fleet_second_slot_gate() into humanoid_
    # second_slot(), now wired into generate_new_game()'s own pipeline.
    ordinary_second_types = {
        ArmyType.LT_CAVALRY,
        ArmyType.HVY_CAVALRY,
        ArmyType.CHARIOTS,
        ArmyType.ELEPHANTS,
        ArmyType.CAMEL_CORPS,
        ArmyType.WARG_RIDERS,
    }
    found_second_slot = False
    found_army_with_second_type = False
    for seed in range(1, 30):
        gs, kings = _setup()
        rng = PascalRandom(seed=seed)
        result = generate_new_game(rng, gs, kings, gamevers=1)
        king_home_coords = {king.home_coord for king in kings}
        for coord, province in result.provinces.items():
            if coord in king_home_coords or province.race not in _HUMANOID_RACES:
                continue
            if province.recruit_type_2 is not None:
                found_second_slot = True
                assert province.recruit_type_2 is ArmyType.FLEET or province.recruit_type_2 in ordinary_second_types
                armies_here = [a for a in result.armies.values() if a.location == coord]
                if any(a.army_type == province.recruit_type_2 for a in armies_here):
                    found_army_with_second_type = True
        if found_second_slot and found_army_with_second_type:
            break
    assert found_second_slot
    assert found_army_with_second_type


def test_special_race_army_budget_now_grants_trollish_the_ordinary_humanoid_formula():
    # Phase 902 (TROLL.md): Trollish (race 10) has no dedicated CASE
    # branch in province_army_routine -- it shares the exact same
    # default budget branch as an ordinary humanoid province.
    rng = PascalRandom(seed=7)
    budget = _special_race_army_budget(Race.TROLLISH, tax=10, rng=rng)
    assert budget is not None
    assert int(10 * 0.65) + 1 <= budget <= int(10 * 0.9) + 1


def test_trollish_provinces_can_now_get_a_real_trolls_army():
    # Phase 902 (TROLL.md): Trollish falls through to the same default
    # budget branch as an ordinary humanoid province -- a low-tax
    # Trollish province can still legitimately end up with zero armies
    # (TROLLS costs 5 strength, and budget can be as low as 1), the same
    # already-established "cost > remaining budget, stop" rule every
    # other special race already lives with. This proves the wiring
    # actually fires at least once across a real spread of seeds/tax
    # values, not that every Trollish province gets one.
    found_trollish_army = False
    for seed in range(1, 30):
        gs, k = _setup()
        rng = PascalRandom(seed=seed)
        result = generate_new_game(rng, gs, k, gamevers=1)
        trollish = [p for p in result.provinces.values() if p.race is Race.TROLLISH]
        for province in trollish:
            armies_here = [a for a in result.armies.values() if a.location == province.coord]
            if any(a.army_type is ArmyType.TROLLS for a in armies_here):
                found_trollish_army = True
                break
        if found_trollish_army:
            break
    assert found_trollish_army


def test_feature_roster_matches_the_confirmed_count_and_carries_real_data():
    game_state, kings = _setup()
    rng = PascalRandom(seed=5)
    result = generate_new_game(rng, game_state, kings, gamevers=1)

    assert len(result.features) == feature_count(1)
    for feature in result.features.values():
        assert feature.guardian_monster is not None
        assert feature.guardian_alignment is not None
        assert isinstance(feature.magic_location, MagicFeature)
        assert isinstance(feature.magic_power, Power)


def test_magic_item_cursor_assigns_treasure_to_exactly_the_confirmed_slot_count():
    game_state, kings = _setup()
    rng = PascalRandom(seed=6)
    result = generate_new_game(rng, game_state, kings, gamevers=1)

    # Phase 430: every feature now carries a real Treasure -- the other
    # half (gold-slot features) used to get `treasure=None`.
    with_treasure = sum(1 for f in result.features.values() if f.treasure is not None)
    assert with_treasure == feature_count(1)

    magic_item_treasure = sum(
        1
        for f in result.features.values()
        if f.treasure is not None and TREASURE_CATEGORY[f.treasure] is not TreasureCategory.GOLD_HOARD
    )
    assert magic_item_treasure == item_slot_count(feature_count(1))


def test_generate_new_game_is_deterministic_for_a_fixed_seed():
    game_state_a, kings_a = _setup()
    game_state_b, kings_b = _setup()
    result_a = generate_new_game(PascalRandom(seed=99), game_state_a, kings_a, gamevers=1)
    result_b = generate_new_game(PascalRandom(seed=99), game_state_b, kings_b, gamevers=1)

    tax_a = {coord: p.tax for coord, p in result_a.provinces.items()}
    tax_b = {coord: p.tax for coord, p in result_b.provinces.items()}
    assert tax_a == tax_b
    assert len(result_a.armies) == len(result_b.armies)
    assert len(result_a.features) == len(result_b.features)


def test_commander_none_sentinel_matches_the_confirmed_value():
    assert COMMANDER_NONE == 255


def test_every_kings_treasury_starts_at_the_confirmed_real_value():
    # Phase 425: caught by an actual multi-turn playtest -- every real
    # Turn-0 "Gold in treasury" line (SE0__T0.K0.txt, SE3__T0.K1/K2/K3)
    # reads 10, but generate_new_game() never set KingdomState.treasury
    # at all before this phase, leaving every fresh game at the
    # dataclass default of 0.
    game_state, kings = _setup()
    rng = PascalRandom(seed=1)
    result = generate_new_game(rng, game_state, kings, gamevers=1)

    for king in kings:
        kingdom_id = result.leaders[king.leader_id].kingdom_id
        assert result.kingdoms[kingdom_id].treasury == STARTING_TREASURY


def test_every_king_gets_exactly_two_companions_at_their_own_home():
    # Phase 426: "per ogni Re vengono poi scelti due leader inutilizzati
    # e collocati nella sua Home. Il primo eredita la razza del Re; il
    # secondo riceve casualmente una delle quattro razze umanoidi" --
    # leader_placement.py's own already-confirmed companion rule, wired
    # here for the first time.
    game_state, kings = _setup()
    rng = PascalRandom(seed=1)
    result = generate_new_game(rng, game_state, kings, gamevers=1)

    for king in kings:
        king_kingdom_id = result.leaders[king.leader_id].kingdom_id
        companions = [
            leader
            for leader in result.leaders.values()
            if leader.leader_id != king.leader_id
            and leader.kingdom_id == king_kingdom_id
            and leader.location == king.home_coord
        ]
        assert len(companions) == COMPANIONS_PER_KING
        races = {companion.race for companion in companions}
        assert king.race in races
        assert len(races) == 2  # the second companion is never the King's own race
        for companion in companions:
            assert companion.race in _HUMANOID_RACES
            assert companion.skills is not None
            assert companion.alignment is not None
            assert companion.is_king is False
            assert companion.name == STANDARD_HERO_ROSTER[companion.leader_id]
            # Phase 984: gates turn/hire_pay.py required_pay()'s own
            # conquest surcharge off for a starting companion -- see
            # that function's own Phase 984 docstring addendum.
            assert companion.is_starting_companion is True


def _lords(result, kings):
    # Phase 979: generate_new_game() now also places "remaining mercenary
    # heroes" (kingdom_id=None, same as a lord) at coordinates not tied to
    # any humanoid province, so kingdom_id=None alone no longer uniquely
    # identifies a lord. Both roles draw from the same ascending-id
    # unused_hero_ids iterator, lords first, so a lord's own id is always
    # lower than every mercenary's -- the lowest lord_count independent
    # ids are exactly the lords.
    king_ids = {king.leader_id for king in kings}
    humanoid_count = sum(1 for province in result.provinces.values() if province.race in _HUMANOID_RACES)
    lord_count = owner_leader_count(humanoid_count, 100, len(kings)) - len(kings)
    independent_ids = sorted(
        leader.leader_id for leader in result.leaders.values() if leader.leader_id not in king_ids and leader.kingdom_id is None
    )
    return [result.leaders[leader_id] for leader_id in independent_ids[:lord_count]]


def test_independent_lords_govern_free_humanoid_provinces_as_independent_heroes():
    # Phase 426: "le altre province umanoidi libere ricevono un leader
    # non ancora usato. Il leader diventa Hired... la propria razza
    # viene resa uguale alla razza nativa della provincia" -- lords are
    # independent (kingdom_id=None, the Phase 104 "independent Hero"
    # convention), not owned by any King's kingdom.
    game_state, kings = _setup()
    rng = PascalRandom(seed=1)
    result = generate_new_game(rng, game_state, kings, gamevers=1)

    king_homes = {king.home_coord for king in kings}
    lords = _lords(result, kings)
    assert lords
    for lord in lords:
        assert lord.location not in king_homes
        province = result.provinces[lord.location]
        assert province.race in _HUMANOID_RACES
        assert lord.race == province.race
        assert lord.skills is not None
        assert lord.alignment is not None
        assert lord.name == STANDARD_HERO_ROSTER[lord.leader_id]
        # Phase 984: only a King's own two starting companions get this
        # flag -- an independent Lord was never placed into a King's
        # own service at all, so the question doesn't even arise.
        assert lord.is_starting_companion is False


def test_every_ordinary_hero_gets_a_real_temper_not_left_unknown():
    # Phase 982: no real source covers a generated hero's own starting
    # Temper (unlike Alignment, roll_alignment() above) -- user-
    # confirmed uniform-random roll_temper() over leaving it unset,
    # which previously rendered every ordinary hero's own CHARACTERS row
    # as "Unkn". Kings (player-chosen at setup) and the reserved roster
    # slot (a fixed real Valhalla stat, checked separately above) are
    # excluded -- this covers every lord/companion/mercenary instead.
    game_state, kings = _setup()
    rng = PascalRandom(seed=1)
    result = generate_new_game(rng, game_state, kings, gamevers=1)

    king_leader_ids = {king.leader_id for king in kings}
    reserved_roster_id = len(result.leaders) - 1
    for leader_id, leader in result.leaders.items():
        if leader_id in king_leader_ids or leader_id == reserved_roster_id:
            continue
        assert leader.temper is not None


def test_total_leader_count_matches_leader_count_exactly():
    # Phase 979 (+ its own addendum): "remaining mercenary heroes" and
    # the reserved last roster id are both materialized now, so for
    # leader_count=100 (this project's own default/only tier, with a
    # confirmed RESERVED_ROSTER_HERO_NAME entry) every one of the 100
    # roster slots is a real LeaderState -- independently confirmed
    # against real GW world files from different actual historical
    # games, each showing the full leader_count - king_count + 1
    # reserved slot (90 Heroes + 1 reserved for a 10-King/v3 game, 247 +
    # 1 for a 3-King/v4/250-slot game, the same +1 reconfirmed again by a
    # second, unrelated 250-slot game).
    game_state, kings = _setup()
    rng = PascalRandom(seed=1)
    result = generate_new_game(rng, game_state, kings, gamevers=1)

    # Kings occupy the same id range heroes otherwise would, one-for-one,
    # so the *total* materialized leader count (Kings + Heroes) is simply
    # leader_count, independent of king_count.
    assert len(result.leaders) == 100


def test_no_leader_id_is_reused_across_kings_lords_and_companions():
    game_state, kings = _setup()
    rng = PascalRandom(seed=1)
    result = generate_new_game(rng, game_state, kings, gamevers=1)

    king_ids = {king.leader_id for king in kings}
    non_king_count = sum(1 for leader_id in result.leaders if leader_id not in king_ids)
    lord_count = sum(
        1 for leader in result.leaders.values() if leader.leader_id not in king_ids and leader.kingdom_id is None
    )
    companion_count = COMPANIONS_PER_KING * len(kings)
    assert non_king_count == lord_count + companion_count


def _mercenaries(result, kings, *, leader_count=100):
    """The complement of `_lords()` among kingdom_id=None non-King leaders,
    also excluding the reserved last roster id (Phase 979 addendum -- its
    own name doesn't come from STANDARD_HERO_ROSTER, see `test_reserved_
    roster_id_gets_its_real_valhalla_name_and_stats` below) -- see
    `_lords()`'s own docstring comment for why id order distinguishes
    lords from mercenaries."""

    king_ids = {king.leader_id for king in kings}
    lord_ids = {lord.leader_id for lord in _lords(result, kings)}
    reserved_id = leader_count - 1
    return [
        leader
        for leader in result.leaders.values()
        if leader.leader_id not in king_ids
        and leader.kingdom_id is None
        and leader.leader_id not in lord_ids
        and leader.leader_id != reserved_id
    ]


def test_remaining_mercenary_heroes_are_placed_off_sea_and_off_king_homes():
    # Phase 979: closes the "remaining mercenary heroes" gap -- every
    # hero_pool id left over after lords and companions is now a real
    # LeaderState, independent (kingdom_id=None like a lord), placed via
    # worldgen/leader_placement.py's own confirmed draw_mercenary_
    # relocation_coordinate() ("redraw while on Sea or in a King-owned
    # province; sharing a lord-owned province is allowed").
    game_state, kings = _setup()
    rng = PascalRandom(seed=1)
    result = generate_new_game(rng, game_state, kings, gamevers=1)

    king_homes = {king.home_coord for king in kings}
    mercenaries = _mercenaries(result, kings)
    assert mercenaries
    for mercenary in mercenaries:
        assert mercenary.location not in king_homes
        assert result.provinces[mercenary.location].terrain is not Terrain.SEA
        assert mercenary.race == result.provinces[mercenary.location].race
        assert mercenary.skills is not None
        assert mercenary.alignment is not None
        assert mercenary.name == STANDARD_HERO_ROSTER[mercenary.leader_id]


def test_reserved_roster_id_gets_its_real_valhalla_name_and_stats():
    # Phase 979 addendum: for a 100-slot leader_count (this project's own
    # default/only tier, RESERVED_ROSTER_HERO_NAME[100] == "Kitralus"),
    # the reserved last roster id (99) is now a real LeaderState too,
    # with the full stat block of the matching VALHALLA_ROSTER entry --
    # confirmed real (same name) across a real GW world file, not an
    # invented identity.
    from ak_engine.models.valhalla import VALHALLA_HERO_BY_NAME

    game_state, kings = _setup()
    rng = PascalRandom(seed=1)
    result = generate_new_game(rng, game_state, kings, gamevers=1)

    reserved = result.leaders[99]
    kitralus = VALHALLA_HERO_BY_NAME["Kitralus"]
    assert reserved.name == "Kitralus"
    assert reserved.kingdom_id is None
    assert reserved.alignment is kitralus.true_alignment
    assert reserved.temper is kitralus.temper
    assert reserved.race is kitralus.race
    assert reserved.skills == kitralus.skills
    assert reserved.location not in {king.home_coord for king in kings}
    assert result.provinces[reserved.location].terrain is not Terrain.SEA


def _setup_naval(king_count: int = 3) -> tuple[GameState, list[KingSetup]]:
    # Phase 427: home_coord=None for every King, so generate_new_game()
    # auto-selects it. King 0 is pre-marked Naval (a nonzero Ability.NAVAL
    # skill level) via its own pre-created LeaderState.skills, matching
    # the "caller sets this up before calling generate_new_game()"
    # convention every other per-leader ability datum already uses.
    game_state = GameState()
    kings: list[KingSetup] = []
    for i in range(king_count):
        race = _KING_RACES[i % 4]
        skills = None
        if i == 0:
            skills = SkillTable(raw_values=[0] * 31)
            skills.set_pair_for_ability(Ability.NAVAL, 1, 0)
        game_state.kingdoms[i] = KingdomState(
            kingdom_id=i, name=f"K{i}", race=race, alignment=Alignment.NEUTRAL, home_province=HexCoord(0, 0)
        )
        game_state.leaders[i] = LeaderState(
            leader_id=i, kingdom_id=i, name=f"King{i}", location=HexCoord(0, 0), is_king=True, race=race, skills=skills
        )
        kings.append(KingSetup(leader_id=i, race=race, home_coord=None))
    return game_state, kings


def test_auto_selected_king_homes_respect_the_minimum_distance_and_terrain_rules():
    game_state, kings = _setup_naval()
    rng = PascalRandom(seed=1)
    result = generate_new_game(rng, game_state, kings, gamevers=1)

    homes = [result.leaders[king.leader_id].location for king in kings]
    for i, a in enumerate(homes):
        for b in homes[i + 1 :]:
            assert hex_distance(a, b) >= MIN_HOME_DISTANCE
        province = result.provinces[a]
        assert province.terrain in _NON_SEA_NON_DESERT_TERRAINS


def test_auto_selected_naval_king_home_has_a_sea_neighbor_and_a_fleet_second_slot():
    game_state, kings = _setup_naval()
    rng = PascalRandom(seed=1)
    result = generate_new_game(rng, game_state, kings, gamevers=1)

    naval_king = kings[0]
    home_coord = result.leaders[naval_king.leader_id].location
    province = result.provinces[home_coord]
    bounds = MapBounds(DEFAULT_WIDTH, DEFAULT_HEIGHT)

    assert any(result.provinces[n].terrain is Terrain.SEA for n in neighbors(home_coord, bounds))
    assert province.recruit_type_2 is ArmyType.FLEET
    assert province.recruit_type_1 == BEST_ATYPE[naval_king.race]


def test_auto_selected_non_naval_king_second_slot_matches_the_terrain_rule():
    game_state, kings = _setup_naval()
    rng = PascalRandom(seed=1)
    result = generate_new_game(rng, game_state, kings, gamevers=1)

    for king in kings[1:]:  # every King except the pre-marked Naval one
        home_coord = result.leaders[king.leader_id].location
        province = result.provinces[home_coord]
        if province.terrain is Terrain.JUNGLE:
            assert province.recruit_type_2 is ArmyType.ELEPHANTS
        else:
            assert province.recruit_type_2 in {ArmyType.LT_CAVALRY, ArmyType.HVY_CAVALRY, ArmyType.CHARIOTS}


def test_auto_selected_king_home_updates_the_kingdoms_own_home_province():
    # GM interface Phase 4: KingdomState.home_province must track the
    # real, auto-chosen Home -- not stay stuck at whatever placeholder
    # the caller constructed the Kingdom with before generate_new_game()
    # ever ran (every King here starts with home_province=(0, 0), per
    # _setup_naval(), which no real King's actual auto-placed Home ever
    # legitimately lands on -- MIN_HOME_DISTANCE keeps them apart, and a
    # (0, 0) corner is not a real placement candidate).
    game_state, kings = _setup_naval()
    rng = PascalRandom(seed=1)
    result = generate_new_game(rng, game_state, kings, gamevers=1)

    for king in kings:
        leader = result.leaders[king.leader_id]
        assert result.kingdoms[leader.kingdom_id].home_province == leader.location


def test_every_kings_home_starts_fully_explored():
    # Phase 428: confirmed verbatim ("Expl% 100%") across four independent
    # real Turn-0 PROVINCES sections -- SE0__T0.K0.txt "Acacia", SE3__
    # T0.K1/K2/K3 "the Dolphin Sea"/"Mongu"/"Ngara". Checks both the
    # shared scalar (PROVINCES table) and the King's own per-kingdom
    # entry (ADVENTURE section).
    game_state, kings = _setup()
    rng = PascalRandom(seed=1)
    result = generate_new_game(rng, game_state, kings, gamevers=1)

    for king in kings:
        home_coord = result.leaders[king.leader_id].location
        kingdom_id = result.leaders[king.leader_id].kingdom_id
        province = result.provinces[home_coord]
        assert province.explored_percent == 100
        assert province.explored_percent_by_kingdom.get(kingdom_id) == 100


def test_every_kings_home_also_reveals_its_own_real_neighbors_to_that_kingdom():
    # Phase 982: a King starts physically present in their own Home --
    # the same real "known provinces" floor `turn/move_execution.py
    # reveal_adjacent_provinces()` already grants any Kingdom entering a
    # province during a turn (Phase 623), now also applied once at
    # world-creation time. Every real Turn-0 report the user supplied
    # names the Home province's own 6 real neighbors
    # (`report/turn_report.py describe_home_province_neighbors()`, Phase
    # 981) -- which needs each neighbor already `known_to_kingdom()`
    # (>=1% explored), not just the Home province itself (Phase 428).
    game_state, kings = _setup()
    rng = PascalRandom(seed=1)
    result = generate_new_game(rng, game_state, kings, gamevers=1)
    bounds = MapBounds(result.board_width, result.board_height)

    for king in kings:
        home_coord = result.leaders[king.leader_id].location
        kingdom_id = result.leaders[king.leader_id].kingdom_id
        for neighbor_coord in neighbors(home_coord, bounds):
            neighbor_province = result.provinces.get(neighbor_coord)
            assert neighbor_province is not None
            assert neighbor_province.known_to_kingdom(kingdom_id)


def test_every_province_gets_a_real_name_not_left_unnamed():
    # Phase 983: no call site here ever set ProvinceState.name before
    # this phase, so every province fell back to its own (x, y)
    # coordinate everywhere a report/the webapp displays one.
    # turn/rename_province.py assign_province_name() and models/
    # province_names.py's own real, fixture-verified PRNAMES.PAS pools
    # already existed -- this just wires them in.
    game_state, kings = _setup()
    rng = PascalRandom(seed=1)
    result = generate_new_game(rng, game_state, kings, gamevers=1)

    for province in result.provinces.values():
        assert province.name


def test_every_province_name_comes_from_its_own_terrain_pool():
    game_state, kings = _setup()
    rng = PascalRandom(seed=1)
    result = generate_new_game(rng, game_state, kings, gamevers=1)

    for province in result.provinces.values():
        assert province.name in PROVINCE_NAME_POOLS[province.terrain]


def test_province_names_are_reproducible_for_the_same_seed():
    game_state_a, kings_a = _setup()
    result_a = generate_new_game(PascalRandom(seed=1), game_state_a, kings_a, gamevers=1)

    game_state_b, kings_b = _setup()
    result_b = generate_new_game(PascalRandom(seed=1), game_state_b, kings_b, gamevers=1)

    assert {coord: p.name for coord, p in result_a.provinces.items()} == {
        coord: p.name for coord, p in result_b.provinces.items()
    }


def test_every_kings_home_carries_exactly_two_features():
    # Phase 428: confirmed verbatim (exactly 2 ADVENTURE entries per Home)
    # across the same four independent real Turn-0 reports as above --
    # already correctly implemented by feature_generation.py's own
    # first_2k_home_index() (Phase 364), just previously invisible in a
    # report because explored_percent was never set to reveal it.
    game_state, kings = _setup()
    rng = PascalRandom(seed=1)
    result = generate_new_game(rng, game_state, kings, gamevers=1)

    for king in kings:
        home_coord = result.leaders[king.leader_id].location
        features_here = [f for f in result.features.values() if f.coord == home_coord]
        assert len(features_here) == 2


def test_every_kings_home_features_are_already_detected_by_their_own_kingdom():
    # Phase 429: Phase 428's explored_percent_by_kingdom fix was necessary
    # but not sufficient -- report/turn_report.py describe_adventure_report()
    # actually gates on a *different* field, Feature.discovered_by_kingdom
    # (discovery_level() > 0), confirmed by the same real Turn-0 reports
    # showing a "?" (discovery_level 1: detected, riches unknown) next to
    # each Home feature's own guardian monster.
    game_state, kings = _setup()
    rng = PascalRandom(seed=1)
    result = generate_new_game(rng, game_state, kings, gamevers=1)

    for king in kings:
        home_coord = result.leaders[king.leader_id].location
        kingdom_id = result.leaders[king.leader_id].kingdom_id
        features_here = [f for f in result.features.values() if f.coord == home_coord]
        for feature in features_here:
            assert feature.discovery_level(kingdom_id) == 1
