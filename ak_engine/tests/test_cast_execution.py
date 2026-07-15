from __future__ import annotations

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.enums import Ability, Spell
from ak_engine.models.game_state import ArmyState, GameState, GraveyardEntry, KingdomState, LeaderState, ProvinceState
from ak_engine.models.kingdom import SkillTable
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.race import Race
from ak_engine.turn.cast_decode import CastRequest
from ak_engine.turn.cast_execution import execute_cast
from ak_engine.turn.combat import Quality
from ak_engine.turn.hex_numbering import encode_hex_number
from ak_engine.turn.movement import NORMAL_MAP_BOUNDS, MapBounds, neighbors

from _helpers import ScriptedRandom

LOCATION = HexCoord(3, 9)
ELSEWHERE = HexCoord(9, 9)
CASTER_ID = 1
BOARD_WIDTH = NORMAL_MAP_BOUNDS[0]


def _skills_with(ability: Ability, level: int) -> SkillTable:
    raw_values = [0] * 30
    raw_values[ability.value * 2] = level
    return SkillTable(raw_values=raw_values)


def _target(coord: HexCoord) -> int:
    return encode_hex_number(coord, BOARD_WIDTH)


def build_state() -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.GOOD, LOCATION))
    state.add_kingdom(KingdomState(2, "Rivalia", Race.HUMAN, Alignment.EVIL, ELSEWHERE))
    state.add_leader(LeaderState(CASTER_ID, 1, "Caster", LOCATION))
    return state


def test_charm_assigns_a_colocated_independent_hero_to_the_casters_kingdom():
    state = build_state()
    state.add_leader(LeaderState(78, None, "Wandering Hero", LOCATION))
    request = CastRequest(spell=Spell.CHARM, target=78)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is True
    assert result.reason is None
    assert state.leaders[78].kingdom_id == 1


def test_charm_steals_a_colocated_enemy_characters_allegiance():
    # Charm doesn't require the target to already be independent -- see
    # cast_execution.py's docstring for why this differs from Hire.
    state = build_state()
    state.add_leader(LeaderState(78, 2, "Enemy Hero", LOCATION))
    request = CastRequest(spell=Spell.CHARM, target=78)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is True
    assert state.leaders[78].kingdom_id == 1


def test_charm_fails_when_target_not_colocated():
    state = build_state()
    state.add_leader(LeaderState(78, None, "Wandering Hero", ELSEWHERE))
    request = CastRequest(spell=Spell.CHARM, target=78)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is False
    assert result.reason == "not co-located"
    assert state.leaders[78].kingdom_id is None  # untouched


def test_charm_fails_when_target_does_not_exist():
    state = build_state()
    request = CastRequest(spell=Spell.CHARM, target=999)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is False
    assert result.reason == "target character not found"


def test_kill_enemy_removes_a_colocated_target():
    state = build_state()
    state.add_leader(LeaderState(78, 2, "Enemy Hero", LOCATION))
    request = CastRequest(spell=Spell.KILL_ENEMY, target=78)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is True
    assert 78 not in state.leaders


def test_kill_enemy_fails_when_target_not_colocated():
    state = build_state()
    state.add_leader(LeaderState(78, 2, "Enemy Hero", ELSEWHERE))
    request = CastRequest(spell=Spell.KILL_ENEMY, target=78)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is False
    assert result.reason == "not co-located"
    assert 78 in state.leaders  # untouched


def test_kill_enemy_fails_when_target_does_not_exist():
    state = build_state()
    request = CastRequest(spell=Spell.KILL_ENEMY, target=999)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is False
    assert result.reason == "target character not found"


def test_charm_succeeds_on_a_real_roll_under_the_casters_chance():
    # Rulebook [3.10]: 15% + 15%/level. Psychic level 2 -> 45% chance.
    state = build_state()
    state.leaders[CASTER_ID].skills = _skills_with(Ability.PSYCHIC, 2)
    state.add_leader(LeaderState(78, None, "Wandering Hero", LOCATION))
    request = CastRequest(spell=Spell.CHARM, target=78)
    rng = ScriptedRandom([0.44])

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is True
    assert state.leaders[78].kingdom_id == 1


def test_charm_fails_on_a_real_roll_over_the_casters_chance():
    state = build_state()
    state.leaders[CASTER_ID].skills = _skills_with(Ability.PSYCHIC, 2)
    state.add_leader(LeaderState(78, None, "Wandering Hero", LOCATION))
    request = CastRequest(spell=Spell.CHARM, target=78)
    rng = ScriptedRandom([0.99])

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is False
    assert result.reason == "spell failed"
    assert state.leaders[78].kingdom_id is None  # untouched


def test_charm_fails_outright_when_caster_has_no_skill_in_the_ability():
    state = build_state()
    state.leaders[CASTER_ID].skills = _skills_with(Ability.PSYCHIC, 0)
    state.add_leader(LeaderState(78, None, "Wandering Hero", LOCATION))
    request = CastRequest(spell=Spell.CHARM, target=78)
    rng = ScriptedRandom([])  # no roll consumed -- precondition fails first

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is False
    assert result.reason == "insufficient skill"


def test_kill_enemy_success_roll_uses_necromancy_skill():
    state = build_state()
    state.leaders[CASTER_ID].skills = _skills_with(Ability.NECROMANCY, 1)
    state.add_leader(LeaderState(78, 2, "Enemy Hero", LOCATION))
    request = CastRequest(spell=Spell.KILL_ENEMY, target=78)
    rng = ScriptedRandom([0.29])  # 15% + 15%*1 = 30% chance

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is True
    assert 78 not in state.leaders


def test_cast_always_succeeds_when_caster_has_no_skills_recorded():
    # LeaderState.skills is None by default -- see cast_execution.py's
    # module docstring for why this preserves pre-Phase-30 behavior.
    state = build_state()
    assert state.leaders[CASTER_ID].skills is None
    state.add_leader(LeaderState(78, None, "Wandering Hero", LOCATION))
    request = CastRequest(spell=Spell.CHARM, target=78)
    rng = ScriptedRandom([])  # no roll consumed

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is True


def test_unmodeled_spells_report_a_reason_without_touching_state():
    # Hide_Feature can't be executed -- see the module docstring (the
    # Feature model is an unpopulated stub). Representative of every
    # other real spell this project doesn't execute (see the module
    # docstring's full list).
    state = build_state()
    request = CastRequest(spell=Spell.HIDE_FEATURE, target=0)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is False
    assert result.reason == "spell effect not modeled"


# ---------------------------------------------------------------------------
# Resurrection (Phase 59) -- Regolamento AK.txt [4.21.1]
# ---------------------------------------------------------------------------


def test_resurrection_revives_a_dead_leader_co_located_with_caster():
    state = build_state()
    dead = LeaderState(78, 2, "Fallen Hero", LOCATION)
    state.dead_leaders[78] = dead
    request = CastRequest(spell=Spell.RESURRECTION, target=78)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is True
    assert 78 not in state.dead_leaders
    assert state.leaders[78] is dead
    assert state.leaders[78].kingdom_id == 1


def test_resurrection_fails_when_target_is_not_a_dead_leader():
    state = build_state()
    state.add_leader(LeaderState(78, 2, "Very Much Alive", LOCATION))  # alive, not in dead_leaders
    request = CastRequest(spell=Spell.RESURRECTION, target=78)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is False
    assert result.reason == "target character not found"


def test_resurrection_fails_when_dead_leader_died_elsewhere():
    state = build_state()
    state.dead_leaders[78] = LeaderState(78, 2, "Fallen Hero", ELSEWHERE)
    request = CastRequest(spell=Spell.RESURRECTION, target=78)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is False
    assert result.reason == "not co-located"
    assert 78 in state.dead_leaders  # untouched


# ---------------------------------------------------------------------------
# Part Sea (Phase 59) -- Regolamento AK.txt [4.21.2]
# ---------------------------------------------------------------------------


def test_part_sea_turns_a_sea_province_into_plains():
    state = build_state()
    state.add_province(ProvinceState(LOCATION, Terrain.SEA, Race.HUMAN))
    request = CastRequest(spell=Spell.PART_SEA, target=_target(LOCATION))

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is True
    assert state.provinces[LOCATION].terrain_override is Terrain.PLAINS


def test_part_sea_fails_on_a_non_sea_province():
    state = build_state()
    state.add_province(ProvinceState(LOCATION, Terrain.PLAINS, Race.HUMAN))
    request = CastRequest(spell=Spell.PART_SEA, target=_target(LOCATION))

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is False
    assert result.reason == "target province is not Sea"
    assert state.provinces[LOCATION].terrain_override is None


def test_part_sea_fails_on_a_province_out_of_range():
    state = build_state()
    state.add_province(ProvinceState(LOCATION, Terrain.SEA, Race.HUMAN))
    state.add_province(ProvinceState(ELSEWHERE, Terrain.SEA, Race.HUMAN))
    request = CastRequest(spell=Spell.PART_SEA, target=_target(ELSEWHERE))

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is False
    assert result.reason == "province not found or not in range"


def test_part_sea_succeeds_on_an_adjacent_province():
    state = build_state()
    bounds = MapBounds(*NORMAL_MAP_BOUNDS)
    adjacent = neighbors(LOCATION, bounds)[0]
    state.add_province(ProvinceState(LOCATION, Terrain.PLAINS, Race.HUMAN))
    state.add_province(ProvinceState(adjacent, Terrain.SEA, Race.HUMAN))
    request = CastRequest(spell=Spell.PART_SEA, target=_target(adjacent))

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is True
    assert state.provinces[adjacent].terrain_override is Terrain.PLAINS


def test_part_sea_succeeds_on_a_province_flooded_to_sea_via_override():
    # Phase 168: eligibility must read effective_terrain() -- a province
    # whose base terrain is Plains but has been Flooded to Sea
    # (terrain_override) is really Sea right now, so Part Sea can target it.
    state = build_state()
    state.add_province(ProvinceState(LOCATION, Terrain.PLAINS, Race.HUMAN, terrain_override=Terrain.SEA))
    request = CastRequest(spell=Spell.PART_SEA, target=_target(LOCATION))

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is True
    assert state.provinces[LOCATION].terrain_override is Terrain.PLAINS


def test_part_sea_fails_when_target_province_is_unknown():
    state = build_state()
    request = CastRequest(spell=Spell.PART_SEA, target=_target(LOCATION))

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is False
    assert result.reason == "province not found or not in range"


# ---------------------------------------------------------------------------
# Flood Province (Phase 59) -- Regolamento AK.txt [4.24.1]
# ---------------------------------------------------------------------------


def test_flood_turns_a_land_province_into_sea():
    state = build_state()
    state.add_province(ProvinceState(LOCATION, Terrain.PLAINS, Race.HUMAN))
    request = CastRequest(spell=Spell.FLOOD, target=_target(LOCATION))

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is True
    assert state.provinces[LOCATION].terrain_override is Terrain.SEA


def test_flood_fails_on_a_mountain_province():
    state = build_state()
    state.add_province(ProvinceState(LOCATION, Terrain.MTNS, Race.HUMAN))
    request = CastRequest(spell=Spell.FLOOD, target=_target(LOCATION))

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is False
    assert result.reason == "target province is not a non-mountain land province"


def test_flood_fails_on_an_already_sea_province():
    state = build_state()
    state.add_province(ProvinceState(LOCATION, Terrain.SEA, Race.HUMAN))
    request = CastRequest(spell=Spell.FLOOD, target=_target(LOCATION))

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is False
    assert result.reason == "target province is not a non-mountain land province"


def test_flood_fails_on_a_province_already_flooded_to_sea_via_override():
    # Phase 168: a province whose base terrain is still Plains but has
    # already been Flooded to Sea (terrain_override) must be rejected the
    # same as a genuinely Sea province -- effective_terrain() is what
    # eligibility now reads.
    state = build_state()
    state.add_province(ProvinceState(LOCATION, Terrain.PLAINS, Race.HUMAN, terrain_override=Terrain.SEA))
    request = CastRequest(spell=Spell.FLOOD, target=_target(LOCATION))

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is False
    assert result.reason == "target province is not a non-mountain land province"


# ---------------------------------------------------------------------------
# Tornado (Phase 59) -- Regolamento AK.txt [4.24.2]
# ---------------------------------------------------------------------------


def test_tornado_destroys_units_that_roll_under_the_per_level_chance():
    state = build_state()
    state.add_province(ProvinceState(LOCATION, Terrain.PLAINS, Race.HUMAN))
    state.leaders[CASTER_ID].skills = _skills_with(Ability.ELEMENTAL, 2)  # 20% destroy chance
    state.add_army(ArmyState(1, 1, ArmyType.LEGION, Quality.AVERAGE, LOCATION))  # caster's own army
    state.add_army(ArmyState(2, 2, ArmyType.BOWMEN, Quality.AVERAGE, LOCATION))  # enemy army
    request = CastRequest(spell=Spell.TORNADO, target=_target(LOCATION))
    # rolls: [0] cast-success roll, [1] army 1 destroy roll (hits), [2] army 2 destroy roll (misses)
    rng = ScriptedRandom([0.01, 0.19, 0.99])

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is True
    assert 1 not in state.armies  # own army destroyed too -- no ownership exemption
    assert 2 in state.armies


def test_tornado_destroys_nothing_when_caster_has_no_recorded_level():
    state = build_state()
    state.add_province(ProvinceState(LOCATION, Terrain.PLAINS, Race.HUMAN))
    state.add_army(ArmyState(1, 2, ArmyType.BOWMEN, Quality.AVERAGE, LOCATION))
    request = CastRequest(spell=Spell.TORNADO, target=_target(LOCATION))
    rng = ScriptedRandom([0.0])  # would destroy at any nonzero chance -- see module docstring

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is True
    assert 1 in state.armies  # unknown level -> 0% chance, nothing destroyed


# ---------------------------------------------------------------------------
# Earthquake (Phase 59) -- Regolamento AK.txt [4.24.3]
# ---------------------------------------------------------------------------


def test_earthquake_zeroes_the_tax_modifier_on_a_land_province():
    state = build_state()
    state.add_province(ProvinceState(LOCATION, Terrain.PLAINS, Race.HUMAN))
    request = CastRequest(spell=Spell.EARTHQUAKE, target=_target(LOCATION))

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is True
    assert state.provinces[LOCATION].tax_modifier_percent == -100


def test_earthquake_fails_on_a_sea_province():
    state = build_state()
    state.add_province(ProvinceState(LOCATION, Terrain.SEA, Race.HUMAN))
    request = CastRequest(spell=Spell.EARTHQUAKE, target=_target(LOCATION))

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is False
    assert result.reason == "target province is not land"


def test_earthquake_fails_on_a_province_flooded_to_sea_via_override():
    # Phase 168: Earthquake must refuse a province Flooded to Sea even
    # though its base terrain is still land -- effective_terrain() is the
    # real current terrain, not the frozen base field.
    state = build_state()
    state.add_province(ProvinceState(LOCATION, Terrain.PLAINS, Race.HUMAN, terrain_override=Terrain.SEA))
    request = CastRequest(spell=Spell.EARTHQUAKE, target=_target(LOCATION))

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is False
    assert result.reason == "target province is not land"


# ---------------------------------------------------------------------------
# Bless (Phase 59) -- Regolamento AK.txt [4.21.3]
# ---------------------------------------------------------------------------


def test_bless_sets_the_tax_bonus_on_any_province_regardless_of_distance():
    state = build_state()
    state.add_province(ProvinceState(ELSEWHERE, Terrain.PLAINS, Race.HUMAN))
    request = CastRequest(spell=Spell.BLESS, target=_target(ELSEWHERE))

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is True
    assert state.provinces[ELSEWHERE].tax_modifier_percent == 60


def test_bless_fails_when_target_province_is_unknown():
    state = build_state()
    request = CastRequest(spell=Spell.BLESS, target=_target(ELSEWHERE))

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is False
    assert result.reason == "province not found"


# ---------------------------------------------------------------------------
# Illusory Terrain (Phase 59) -- Regolamento AK.txt [4.23.1]
# ---------------------------------------------------------------------------


def test_illus_terrain_records_the_fake_terrain_on_the_province():
    state = build_state()
    state.add_province(ProvinceState(LOCATION, Terrain.PLAINS, Race.HUMAN))
    request = CastRequest(spell=Spell.ILLUS_TERRAIN, target=_target(LOCATION), terrain=Terrain.FOREST)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is True
    assert state.provinces[LOCATION].illusory_terrain is Terrain.FOREST


def test_illus_terrain_fails_without_a_fake_terrain_specified():
    state = build_state()
    state.add_province(ProvinceState(LOCATION, Terrain.PLAINS, Race.HUMAN))
    request = CastRequest(spell=Spell.ILLUS_TERRAIN, target=_target(LOCATION))  # terrain left as None

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is False
    assert result.reason == "fake terrain not specified"


# ---------------------------------------------------------------------------
# Phantasmal Armies / Illus_Armies (Phase 59) -- Regolamento AK.txt [4.23.2]
# ---------------------------------------------------------------------------


def test_illus_armies_sets_the_casters_illusion_level_on_a_colocated_target():
    state = build_state()
    state.leaders[CASTER_ID].skills = _skills_with(Ability.ILLUSION, 3)
    state.add_leader(LeaderState(78, 1, "Field Commander", LOCATION))
    request = CastRequest(spell=Spell.ILLUS_ARMIES, target=78)
    rng = ScriptedRandom([0.01])  # 15% + 15%*3 = 60% chance

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is True
    assert state.leaders[78].phantasmal_armies_level == 3


def test_illus_armies_can_target_the_caster_himself():
    state = build_state()
    state.leaders[CASTER_ID].skills = _skills_with(Ability.ILLUSION, 2)
    request = CastRequest(spell=Spell.ILLUS_ARMIES, target=CASTER_ID)
    rng = ScriptedRandom([0.01])  # 15% + 15%*2 = 45% chance

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is True
    assert state.leaders[CASTER_ID].phantasmal_armies_level == 2


# ---------------------------------------------------------------------------
# Oratory (Phase 59) -- Regolamento AK.txt [4.22.2]
# ---------------------------------------------------------------------------


def test_oratory_bumps_quality_one_rank_for_every_army_the_target_commands():
    state = build_state()
    state.add_leader(LeaderState(78, 1, "Field Commander", LOCATION))
    state.add_army(ArmyState(1, 1, ArmyType.LEGION, Quality.GREEN, LOCATION, commanded_by=78))
    state.add_army(ArmyState(2, 1, ArmyType.BOWMEN, Quality.AVERAGE, LOCATION, commanded_by=78))
    request = CastRequest(spell=Spell.ORATORY, target=78)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is True
    assert state.armies[1].quality is Quality.AVERAGE
    assert state.armies[2].quality is Quality.VETERAN


def test_oratory_caps_at_elite():
    state = build_state()
    state.add_leader(LeaderState(78, 1, "Field Commander", LOCATION))
    state.add_army(ArmyState(1, 1, ArmyType.LEGION, Quality.ELITE, LOCATION, commanded_by=78))
    request = CastRequest(spell=Spell.ORATORY, target=78)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is True
    assert state.armies[1].quality is Quality.ELITE


def test_oratory_is_not_cumulative_on_a_second_cast_the_same_turn():
    state = build_state()
    state.add_leader(LeaderState(78, 1, "Field Commander", LOCATION))
    state.add_army(ArmyState(1, 1, ArmyType.LEGION, Quality.GREEN, LOCATION, commanded_by=78))
    request = CastRequest(spell=Spell.ORATORY, target=78)

    first = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)
    second = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert first.applied is True
    assert second.applied is True  # the cast itself still succeeds
    assert state.armies[1].quality is Quality.AVERAGE  # but only bumped once


# ---------------------------------------------------------------------------
# Plague (Phase 59) -- Regolamento AK.txt [4.25.3]
# ---------------------------------------------------------------------------


def test_plague_destroys_humanoid_units_that_roll_under_the_chance():
    state = build_state()
    state.add_province(ProvinceState(LOCATION, Terrain.PLAINS, Race.HUMAN))
    state.leaders[CASTER_ID].skills = _skills_with(Ability.NECROMANCY, 1)  # 10% + 10% = 20%
    state.add_army(ArmyState(1, 1, ArmyType.LEGION, Quality.AVERAGE, LOCATION))
    request = CastRequest(spell=Spell.PLAGUE, target=_target(LOCATION))
    rng = ScriptedRandom([0.01, 0.19])  # [0] cast success, [1] per-unit destroy roll (hits)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is True
    assert 1 not in state.armies


def test_plague_skips_non_humanoid_and_mercenary_armies():
    state = build_state()
    state.add_province(ProvinceState(LOCATION, Terrain.PLAINS, Race.HUMAN))
    state.leaders[CASTER_ID].skills = _skills_with(Ability.NECROMANCY, 9)  # near-certain chance
    state.kingdoms[2] = KingdomState(2, "Rivalia", Race.DRAGONS, Alignment.EVIL, ELSEWHERE)
    state.add_army(ArmyState(1, 2, ArmyType.DRAGON_WING, Quality.AVERAGE, LOCATION))  # non-humanoid race
    state.add_army(ArmyState(2, None, ArmyType.LEGION, Quality.AVERAGE, LOCATION))  # mercenary, race unknown
    request = CastRequest(spell=Spell.PLAGUE, target=_target(LOCATION))
    rng = ScriptedRandom([0.01])  # only the cast-success roll is ever consumed

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is True
    assert 1 in state.armies
    assert 2 in state.armies


# ---------------------------------------------------------------------------
# Bless's corpse-cleanup addendum (Phase 60) -- "NUOVE REGOLE E MODIFICHE"
# ---------------------------------------------------------------------------


def test_bless_clears_the_graveyard_on_a_successful_cleanup_roll():
    state = build_state()
    state.add_province(ProvinceState(LOCATION, Terrain.PLAINS, Race.HUMAN))
    state.battle_graveyard[LOCATION] = [GraveyardEntry(ArmyType.LEGION, Quality.AVERAGE, kingdom_id=2)]
    request = CastRequest(spell=Spell.BLESS, target=_target(LOCATION))
    rng = ScriptedRandom([0.05])  # no skills recorded -> cast succeeds free; cleanup chance 10% -> hits

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is True
    assert state.provinces[LOCATION].tax_modifier_percent == 60
    assert LOCATION not in state.battle_graveyard


def test_bless_does_not_clear_the_graveyard_on_a_failed_cleanup_roll():
    state = build_state()
    state.add_province(ProvinceState(LOCATION, Terrain.PLAINS, Race.HUMAN))
    state.battle_graveyard[LOCATION] = [GraveyardEntry(ArmyType.LEGION, Quality.AVERAGE, kingdom_id=2)]
    request = CastRequest(spell=Spell.BLESS, target=_target(LOCATION))
    rng = ScriptedRandom([0.99])  # cleanup chance 10% -> misses

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is True
    assert state.provinces[LOCATION].tax_modifier_percent == 60  # tax bonus still applies
    assert len(state.battle_graveyard[LOCATION]) == 1  # graveyard untouched


def test_bless_cleanup_chance_scales_with_white_magic_level():
    state = build_state()
    state.add_province(ProvinceState(LOCATION, Terrain.PLAINS, Race.HUMAN))
    state.leaders[CASTER_ID].skills = _skills_with(Ability.WHITE, 2)  # cast 45%, cleanup 30%
    state.battle_graveyard[LOCATION] = [GraveyardEntry(ArmyType.LEGION, Quality.AVERAGE, kingdom_id=2)]
    request = CastRequest(spell=Spell.BLESS, target=_target(LOCATION))
    rng = ScriptedRandom([0.01, 0.25])  # [0] cast success, [1] cleanup roll (0.25 < 30%)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is True
    assert LOCATION not in state.battle_graveyard


# ---------------------------------------------------------------------------
# Skeletal Army (Phase 60) -- Regolamento AK.txt [4.25.1]
# ---------------------------------------------------------------------------


def test_skeletal_army_raises_a_unit_from_the_casters_own_province_graveyard():
    state = build_state()
    state.battle_graveyard[LOCATION] = [GraveyardEntry(ArmyType.LEGION, Quality.VETERAN, kingdom_id=2)]
    state.leaders[CASTER_ID].skills = _skills_with(Ability.NECROMANCY, 1)  # level 1 -> raise up to 1
    request = CastRequest(spell=Spell.SKELETAL_ARMY, target=0)
    rng = ScriptedRandom([0.01])  # cast-success roll only -- raising itself is deterministic

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is True
    assert LOCATION not in state.battle_graveyard  # the one entry was consumed
    raised = [a for a in state.armies.values() if a.army_type is ArmyType.LEGION]
    assert len(raised) == 1
    assert raised[0].quality is Quality.VETERAN
    assert raised[0].kingdom_id == 1  # joins the caster's kingdom
    assert raised[0].commanded_by == CASTER_ID
    assert raised[0].location == LOCATION


def test_skeletal_army_fails_when_the_provinces_graveyard_is_empty():
    state = build_state()
    request = CastRequest(spell=Spell.SKELETAL_ARMY, target=0)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is False
    assert result.reason == "no dead units in this province to raise"


def test_skeletal_army_caps_the_raised_count_at_the_casters_necromancy_level():
    state = build_state()
    state.battle_graveyard[LOCATION] = [
        GraveyardEntry(ArmyType.LEGION, Quality.AVERAGE, kingdom_id=2),
        GraveyardEntry(ArmyType.BOWMEN, Quality.VETERAN, kingdom_id=2),
        GraveyardEntry(ArmyType.AXEMEN, Quality.GREEN, kingdom_id=2),
    ]
    state.leaders[CASTER_ID].skills = _skills_with(Ability.NECROMANCY, 2)  # level 2 -> raise at most 2 of the 3
    request = CastRequest(spell=Spell.SKELETAL_ARMY, target=0)
    rng = ScriptedRandom([0.01])

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is True
    assert len(state.battle_graveyard[LOCATION]) == 1  # one entry left unraised
    assert len([a for a in state.armies.values()]) == 2


def test_skeletal_army_raises_nothing_when_caster_has_no_recorded_level():
    state = build_state()
    state.battle_graveyard[LOCATION] = [GraveyardEntry(ArmyType.LEGION, Quality.AVERAGE, kingdom_id=2)]
    request = CastRequest(spell=Spell.SKELETAL_ARMY, target=0)
    rng = ScriptedRandom([])  # no skills recorded -> cast succeeds free, no roll consumed

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is True  # the cast itself still "succeeds"...
    assert len(state.armies) == 0  # ...but unknown level -> 0 raised, see module docstring
    assert len(state.battle_graveyard[LOCATION]) == 1  # graveyard untouched
