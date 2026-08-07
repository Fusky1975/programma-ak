from __future__ import annotations

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.enums import Ability
from ak_engine.models.game_state import GameState, KingdomState, LeaderState
from ak_engine.models.hero_roster import STANDARD_HERO_ROSTER
from ak_engine.models.kingdom import SkillTable
from ak_engine.models.magic_feature import MagicFeature
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.power import Power
from ak_engine.models.race import Race
from ak_engine.turn.movement import MapBounds, hex_distance, neighbors
from ak_engine.worldgen.feature_generation import feature_count
from ak_engine.worldgen.generate_new_game import STARTING_TREASURY, KingSetup, generate_new_game
from ak_engine.worldgen.initial_armies import BEST_ATYPE, COMMANDER_NONE
from ak_engine.worldgen.king_home_placement import MIN_HOME_DISTANCE
from ak_engine.worldgen.leader_placement import COMPANIONS_PER_KING, owner_leader_count
from ak_engine.worldgen.magic_item_placement import item_slot_count
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


def test_king_home_gets_a_real_initial_army_using_best_atype():
    game_state, kings = _setup()
    rng = PascalRandom(seed=3)
    result = generate_new_game(rng, game_state, kings, gamevers=1)

    for king in kings:
        armies = [a for a in result.armies.values() if a.location == king.home_coord]
        assert armies
        assert armies[0].army_type == BEST_ATYPE[king.race]
        for army in armies:
            assert army.commanded_by is None  # COMMANDER_NONE (255) translates to None
            assert army.kingdom_id == king.leader_id


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


def test_trollish_provinces_never_get_an_army_no_sourced_budget():
    game_state, kings = _setup()
    # A handful of seeds to reliably land at least one Trollish placement.
    for seed in range(1, 15):
        rng = PascalRandom(seed=seed)
        gs, k = _setup()
        result = generate_new_game(rng, gs, k, gamevers=1)
        trollish = [p for p in result.provinces.values() if p.race is Race.TROLLISH]
        for province in trollish:
            armies_here = [a for a in result.armies.values() if a.location == province.coord]
            assert armies_here == []


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

    with_treasure = sum(1 for f in result.features.values() if f.treasure is not None)
    assert with_treasure == item_slot_count(feature_count(1))


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


def test_independent_lords_govern_free_humanoid_provinces_as_independent_heroes():
    # Phase 426: "le altre province umanoidi libere ricevono un leader
    # non ancora usato. Il leader diventa Hired... la propria razza
    # viene resa uguale alla razza nativa della provincia" -- lords are
    # independent (kingdom_id=None, the Phase 104 "independent Hero"
    # convention), not owned by any King's kingdom.
    game_state, kings = _setup()
    rng = PascalRandom(seed=1)
    result = generate_new_game(rng, game_state, kings, gamevers=1)

    king_ids = {king.leader_id for king in kings}
    king_homes = {king.home_coord for king in kings}
    lords = [
        leader for leader in result.leaders.values() if leader.leader_id not in king_ids and leader.kingdom_id is None
    ]
    assert lords
    for lord in lords:
        assert lord.location not in king_homes
        province = result.provinces[lord.location]
        assert province.race in _HUMANOID_RACES
        assert lord.race == province.race
        assert lord.skills is not None
        assert lord.alignment is not None
        assert lord.name == STANDARD_HERO_ROSTER[lord.leader_id]


def test_lord_count_matches_the_confirmed_owner_leader_count_formula():
    game_state, kings = _setup()
    rng = PascalRandom(seed=1)
    result = generate_new_game(rng, game_state, kings, gamevers=1)

    king_ids = {king.leader_id for king in kings}
    lord_count = sum(
        1 for leader in result.leaders.values() if leader.leader_id not in king_ids and leader.kingdom_id is None
    )
    humanoid_count = sum(1 for province in result.provinces.values() if province.race in _HUMANOID_RACES)
    expected_lord_count = owner_leader_count(humanoid_count, 100, len(kings)) - len(kings)
    assert lord_count == expected_lord_count


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
