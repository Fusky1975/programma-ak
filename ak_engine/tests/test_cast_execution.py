from __future__ import annotations

import pytest

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.discovery import Discovery
from ak_engine.models.enums import Ability, Spell
from ak_engine.models.feature import Feature, FeatureType
from ak_engine.models.game_state import ArmyState, GameState, GraveyardEntry, KingdomState, LeaderState, ProvinceState
from ak_engine.models.kingdom import SkillTable
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.race import Race
from ak_engine.models.treasure import Treasure
from ak_engine.turn.cast_decode import CastRequest
from ak_engine.turn.cast_execution import (
    ILLUSORY_FOG_DISSIPATES_AT_END_OF_GAMETURN,
    ILLUSORY_FOG_EXTRA_MOVEMENT_COST,
    ILLUSORY_FOG_STRENGTH_MULTIPLIER,
    MYSTIC_WINDS_ENDS_BEFORE_ARMY_BATTLE,
    MYSTIC_WINDS_MOVEMENT_POINTS,
    MYSTIC_WINDS_MOVES_AS_AIR_UNIT,
    MYSTIC_WINDS_USES_MOVEMENT_POINTS_NORMALLY,
    SCAR_TERRAIN_LAND_COLLAPSE_RACES,
    SCAR_TERRAIN_TAX_REDUCTION,
    LocateObjectResult,
    apply_plague_exposure,
    execute_cast,
    illusory_fog_strength,
    is_illusory_fog_affected_air_unit,
    locate_object,
    scar_terrain_collapse,
    scar_terrain_is_exhausted,
)
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


def test_charm_fails_when_target_commands_military_units():
    # Phase 183: "che non comanda unita' militari" -- a co-located Hero
    # commanding an army is not a free-hire target.
    state = build_state()
    state.add_leader(LeaderState(78, None, "Wandering Hero", LOCATION))
    state.add_army(ArmyState(1, None, ArmyType.LEGION, Quality.AVERAGE, LOCATION, commanded_by=78))
    request = CastRequest(spell=Spell.CHARM, target=78)
    rng = ScriptedRandom([])  # precondition fails before any roll

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is False
    assert result.reason == "target commands military units"
    assert state.leaders[78].kingdom_id is None  # untouched


def test_charm_undead_caster_uses_necromancy_instead_of_psychic():
    # Phase 183: "Per i personaggi Non-Morti questo incantesimo
    # appartiene alla magia Negromantica (e non alla magia Psichica)."
    state = build_state()
    state.leaders[CASTER_ID].alignment = Alignment.UNDEAD
    state.leaders[CASTER_ID].skills = _skills_with(Ability.NECROMANCY, 2)
    state.add_leader(LeaderState(78, None, "Wandering Hero", LOCATION))
    request = CastRequest(spell=Spell.CHARM, target=78)
    rng = ScriptedRandom([0.44])  # 15% + 15%*2 = 45% chance

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is True
    assert state.leaders[78].kingdom_id == 1


def test_charm_undead_caster_with_only_psychic_skill_has_insufficient_skill():
    # Confirms the override is real -- an Undead caster's own Psychic
    # skill no longer governs Charm at all.
    state = build_state()
    state.leaders[CASTER_ID].alignment = Alignment.UNDEAD
    state.leaders[CASTER_ID].skills = _skills_with(Ability.PSYCHIC, 3)
    state.add_leader(LeaderState(78, None, "Wandering Hero", LOCATION))
    request = CastRequest(spell=Spell.CHARM, target=78)
    rng = ScriptedRandom([])  # precondition fails first, no roll consumed

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is False
    assert result.reason == "insufficient skill"


def test_charm_non_undead_caster_still_uses_psychic():
    state = build_state()
    assert state.leaders[CASTER_ID].alignment is None
    state.leaders[CASTER_ID].skills = _skills_with(Ability.PSYCHIC, 2)
    state.add_leader(LeaderState(78, None, "Wandering Hero", LOCATION))
    request = CastRequest(spell=Spell.CHARM, target=78)
    rng = ScriptedRandom([0.44])  # 15% + 15%*2 = 45% chance

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is True


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


def test_kill_enemy_neutralized_by_hidden_tattoos():
    # Phase 270: Hidden Tattoos (Discovery.txt) protects every character
    # of the owning Kingdom from Kill Enemy -- the target survives.
    state = build_state()
    state.kingdoms[2].discoveries.add(Discovery.HIDDEN_TATTOOS)
    state.add_leader(LeaderState(78, 2, "Enemy Hero", LOCATION))
    request = CastRequest(spell=Spell.KILL_ENEMY, target=78)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is True
    assert result.discovery_defended is Discovery.HIDDEN_TATTOOS
    assert 78 in state.leaders  # survives


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
    # Holy_Symbol is one of the ten Personal-Combat-only spells -- see the
    # module docstring for why those still have no Action-Cast dispatch
    # branch. Representative of every other real spell this project
    # doesn't execute this way (see the module docstring's full list).
    state = build_state()
    request = CastRequest(spell=Spell.HOLY_SYMBOL, target=0)

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


def test_resurrection_increments_the_casters_merit_tally_on_success():
    state = build_state()
    state.dead_leaders[78] = LeaderState(78, 2, "Fallen Hero", LOCATION)
    request = CastRequest(spell=Spell.RESURRECTION, target=78)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is True
    assert state.leaders[CASTER_ID].merit_tally.resurrection_bless_casts == 1


def test_resurrection_fails_when_dead_leader_died_elsewhere():
    state = build_state()
    state.dead_leaders[78] = LeaderState(78, 2, "Fallen Hero", ELSEWHERE)
    request = CastRequest(spell=Spell.RESURRECTION, target=78)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is False
    assert state.leaders[CASTER_ID].merit_tally.resurrection_bless_casts == 0  # no cast on failure
    assert result.reason == "not co-located"
    assert 78 in state.dead_leaders  # untouched


# ---------------------------------------------------------------------------
# Resurrection on a Royal Heir (Phase 259) -- RULES.AK [4.21.1]
# ---------------------------------------------------------------------------


def test_resurrection_on_a_royal_heir_restores_the_exact_dead_king():
    state = build_state()
    dead_king = LeaderState(78, 2, "Old King", LOCATION, is_king=True, temper=None, alignment=Alignment.EVIL)
    state.dead_leaders[78] = dead_king
    heir = LeaderState(
        78, 2, "Old King", LOCATION, is_king=True, is_royal_heir=True, skills=SkillTable(raw_values=[0] * 31)
    )
    state.add_leader(heir)
    request = CastRequest(spell=Spell.RESURRECTION, target=78)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is True
    assert 78 not in state.dead_leaders
    assert state.leaders[78] is dead_king  # the exact original, not a fresh copy
    assert state.leaders[78].kingdom_id == 2  # resumes his own throne, not the caster's (kingdom 1)


def test_resurrection_on_a_royal_heir_by_another_kingdoms_caster_still_resumes_his_own_throne():
    # RULES.AK: "If another player casts a Resurrection spell on your
    # Royal Heir, you still get your old King back."
    state = build_state()
    dead_king = LeaderState(78, 2, "Old King", ELSEWHERE, is_king=True)
    state.dead_leaders[78] = dead_king
    state.add_leader(LeaderState(78, 2, "Old King", ELSEWHERE, is_king=True, is_royal_heir=True))
    request = CastRequest(spell=Spell.RESURRECTION, target=78)

    # CASTER_ID (kingdom 1) casts on kingdom 2's own Royal Heir.
    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is False  # not co-located (Heir is ELSEWHERE) -- confirms co-location still checked
    assert result.reason == "not co-located"

    state.leaders[78].location = LOCATION
    result2 = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result2.applied is True
    assert state.leaders[78].kingdom_id == 2  # stays kingdom 2's King, despite kingdom 1 casting


def test_resurrection_on_a_royal_heir_fails_without_an_archived_king():
    state = build_state()
    state.add_leader(LeaderState(78, 2, "Heir Only", LOCATION, is_king=True, is_royal_heir=True))
    request = CastRequest(spell=Spell.RESURRECTION, target=78)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is False
    assert result.reason == "target character not found"


def test_resurrection_on_a_royal_heir_increments_the_casters_merit_tally():
    state = build_state()
    state.dead_leaders[78] = LeaderState(78, 2, "Old King", LOCATION, is_king=True)
    state.add_leader(LeaderState(78, 2, "Old King", LOCATION, is_king=True, is_royal_heir=True))
    request = CastRequest(spell=Spell.RESURRECTION, target=78)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is True
    assert state.leaders[CASTER_ID].merit_tally.resurrection_bless_casts == 1


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


def test_tornado_giant_fan_downgrades_quality_instead_of_destroying():
    # Phase 270: Giant Fan (Discovery.txt) -- a 50% chance of losing one
    # quality level instead of being destroyed, checked against the
    # army's own Kingdom.
    state = build_state()
    state.kingdoms[2].discoveries.add(Discovery.GIANT_FAN)
    state.add_province(ProvinceState(LOCATION, Terrain.PLAINS, Race.HUMAN))
    state.leaders[CASTER_ID].skills = _skills_with(Ability.ELEMENTAL, 2)  # 20% destroy chance
    state.add_army(ArmyState(2, 2, ArmyType.BOWMEN, Quality.AVERAGE, LOCATION))
    request = CastRequest(spell=Spell.TORNADO, target=_target(LOCATION))
    # rolls: [0] cast-success roll, [1] army 2's downgrade roll (hits, at flat 50%)
    rng = ScriptedRandom([0.01, 0.49])

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is True
    assert result.discovery_defended is Discovery.GIANT_FAN
    assert 2 in state.armies  # never destroyed
    assert state.armies[2].quality == Quality.GREEN  # one level down from AVERAGE


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


def test_earthquake_reinforced_concrete_applies_flat_reduction_instead():
    # Phase 270: Reinforced Concrete (Discovery.txt) -- replaces the
    # -100% effect with a flat 3-gold reduction, checked against the
    # province owner's own Kingdom.
    state = build_state()
    state.kingdoms[2].discoveries.add(Discovery.REINFORCED_CONCRETE)
    state.add_province(ProvinceState(LOCATION, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2))
    request = CastRequest(spell=Spell.EARTHQUAKE, target=_target(LOCATION))

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is True
    assert result.discovery_defended is Discovery.REINFORCED_CONCRETE
    assert state.provinces[LOCATION].tax_modifier_percent == 0  # untouched
    assert state.provinces[LOCATION].earthquake_flat_reduction == 3


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


def test_bless_increments_the_casters_merit_tally_on_success():
    state = build_state()
    state.add_province(ProvinceState(ELSEWHERE, Terrain.PLAINS, Race.HUMAN))
    request = CastRequest(spell=Spell.BLESS, target=_target(ELSEWHERE))

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is True
    assert state.leaders[CASTER_ID].merit_tally.resurrection_bless_casts == 1


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


def test_plague_marks_the_province_as_plague_active():
    state = build_state()
    state.add_province(ProvinceState(LOCATION, Terrain.PLAINS, Race.HUMAN))
    request = CastRequest(spell=Spell.PLAGUE, target=_target(LOCATION))
    rng = ScriptedRandom([0.01])  # cast success; no armies present, no exposure roll

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is True
    assert state.provinces[LOCATION].plague_active is True


def test_plague_recast_on_an_already_active_province_is_a_no_op():
    state = build_state()
    province = ProvinceState(LOCATION, Terrain.PLAINS, Race.HUMAN, plague_active=True)
    state.add_province(province)
    state.add_army(ArmyState(1, 1, ArmyType.LEGION, Quality.AVERAGE, LOCATION))
    request = CastRequest(spell=Spell.PLAGUE, target=_target(LOCATION))
    rng = ScriptedRandom([0.01])  # only the cast-success roll -- a 2nd (exposure) roll would raise

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is True
    assert 1 in state.armies  # untouched -- no cumulative effect


def test_apply_plague_exposure_immunizes_a_survivor():
    state = build_state()
    state.add_army(ArmyState(1, 1, ArmyType.LEGION, Quality.AVERAGE, LOCATION))
    rng = ScriptedRandom([0.5])  # misses a 0.2 destroy chance -- survives

    apply_plague_exposure(state, LOCATION, 0.2, rng)

    assert 1 in state.armies
    assert state.armies[1].plague_immune is True


def test_apply_plague_exposure_destroys_a_non_immune_army_on_a_hit():
    state = build_state()
    state.add_army(ArmyState(1, 1, ArmyType.LEGION, Quality.AVERAGE, LOCATION))
    rng = ScriptedRandom([0.01])  # hits a 0.2 destroy chance

    apply_plague_exposure(state, LOCATION, 0.2, rng)

    assert 1 not in state.armies


def test_apply_plague_exposure_penicillin_never_destroys_only_downgrades():
    # Phase 270: Penicillin (Discovery.txt) -- a flat 50% chance of
    # losing one quality level, never the destroy roll, regardless of
    # `chance` or prior plague_immune status.
    state = build_state()
    state.kingdoms[1].discoveries.add(Discovery.PENICILLIN)
    state.add_army(ArmyState(1, 1, ArmyType.LEGION, Quality.AVERAGE, LOCATION))
    rng = ScriptedRandom([0.49])  # hits the flat 50% downgrade chance

    apply_plague_exposure(state, LOCATION, 1.0, rng)  # chance=100% would otherwise always destroy

    assert 1 in state.armies  # never destroyed
    assert state.armies[1].quality == Quality.GREEN
    assert state.armies[1].plague_immune is False  # Penicillin's own branch, not the immunity path


def test_apply_plague_exposure_drops_an_immune_armys_quality_instead_of_killing_it():
    state = build_state()
    army = ArmyState(1, 1, ArmyType.LEGION, Quality.VETERAN, LOCATION, plague_immune=True)
    state.add_army(army)
    rng = ScriptedRandom([0.01])  # hits the 0.2 chance -- but immune, so quality drops instead

    apply_plague_exposure(state, LOCATION, 0.2, rng)

    assert 1 in state.armies
    assert state.armies[1].quality is Quality.AVERAGE  # one level below Veteran
    assert state.armies[1].plague_immune is True


def test_apply_plague_exposure_immune_army_at_depleted_stays_depleted():
    state = build_state()
    army = ArmyState(1, 1, ArmyType.LEGION, Quality.DEPLETED, LOCATION, plague_immune=True)
    state.add_army(army)
    rng = ScriptedRandom([0.01])  # hits the chance -- already at the floor

    apply_plague_exposure(state, LOCATION, 0.2, rng)

    assert state.armies[1].quality is Quality.DEPLETED


def test_apply_plague_exposure_skips_mercenaries_and_non_humanoid_races():
    state = build_state()
    state.kingdoms[2] = KingdomState(2, "Rivalia2", Race.DRAGONS, Alignment.EVIL, ELSEWHERE)
    state.add_army(ArmyState(1, 2, ArmyType.DRAGON_WING, Quality.AVERAGE, LOCATION))  # non-humanoid
    state.add_army(ArmyState(2, None, ArmyType.LEGION, Quality.AVERAGE, LOCATION))  # mercenary
    rng = ScriptedRandom([])  # no army is ever eligible for a roll

    apply_plague_exposure(state, LOCATION, 1.0, rng)

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
    assert raised[0].is_skeletal is True


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


# ---------------------------------------------------------------------------
# Clairvoyance (Phase 193) -- Regolamento AK.txt [4.22.3]
# ---------------------------------------------------------------------------


def test_clairvoyance_adds_the_casters_kingdom_to_the_targets_watchers():
    state = build_state()
    state.add_leader(LeaderState(78, 2, "Enemy Hero", ELSEWHERE))  # no co-location requirement
    request = CastRequest(spell=Spell.CLAIRVOYANCE, target=78)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is True
    assert state.leaders[78].clairvoyance_watchers == {1}


def test_clairvoyance_fails_when_target_does_not_exist():
    state = build_state()
    request = CastRequest(spell=Spell.CLAIRVOYANCE, target=78)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is False
    assert result.reason == "target character not found"


def test_clairvoyance_does_not_touch_watchers_on_a_failed_roll():
    state = build_state()
    state.leaders[CASTER_ID].skills = _skills_with(Ability.PSYCHIC, 1)
    state.add_leader(LeaderState(78, 2, "Enemy Hero", ELSEWHERE))
    request = CastRequest(spell=Spell.CLAIRVOYANCE, target=78)
    rng = ScriptedRandom([0.96])  # over the 15%+15% = 30% Action-Cast chance

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is False
    assert state.leaders[78].clairvoyance_watchers == set()


# ---------------------------------------------------------------------------
# Hide_Feature (Phase 193) -- Regolamento AK.txt [4.23.3]
# ---------------------------------------------------------------------------


def test_hide_feature_hides_every_feature_in_the_target_province():
    state = build_state()
    state.add_province(ProvinceState(LOCATION, Terrain.PLAINS, Race.HUMAN))
    state.add_feature(Feature(1, LOCATION, FeatureType.SACRED_ROCK))
    state.add_feature(Feature(2, LOCATION, FeatureType.ALTAR))
    request = CastRequest(spell=Spell.HIDE_FEATURE, target=_target(LOCATION))

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is True
    assert state.features[1].magically_hidden is True
    assert state.features[2].magically_hidden is True


def test_hide_feature_fails_when_the_province_has_no_feature():
    state = build_state()
    state.add_province(ProvinceState(LOCATION, Terrain.PLAINS, Race.HUMAN))
    request = CastRequest(spell=Spell.HIDE_FEATURE, target=_target(LOCATION))

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is False
    assert result.reason == "no feature to hide"


def test_hide_feature_fails_when_the_province_is_unknown():
    state = build_state()
    request = CastRequest(spell=Spell.HIDE_FEATURE, target=_target(LOCATION))

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is False
    assert result.reason == "province not found or not in range"


# ---------------------------------------------------------------------------
# Gate Angel / VALHALLA (Phase 194, corrected Phase 195) -- user-supplied
# rule text, one of the 10 secret spells. GATE_ANGEL_ELIGIBLE_ALIGNMENTS is
# (GOOD, DRUID, NEUTRAL, PAGAN, EVIL) in that order, so choice_indices=[0]
# picks GOOD, [1] picks DRUID, [4] picks EVIL, for the due-alignment draw.
# ---------------------------------------------------------------------------


def test_gate_angel_matching_alignment_succeeds_and_records_the_winner():
    state = build_state()
    assert state.kingdoms[1].alignment is Alignment.GOOD
    request = CastRequest(spell=Spell.GATE_ANGEL, target=0)
    rng = ScriptedRandom([], choice_indices=[0])  # GOOD due -- matches kingdom 1

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is True
    assert state.gate_angel_due_alignment is Alignment.GOOD
    assert state.last_gate_angel_kingdom == 1
    assert state.last_gate_angel_turn == state.turn_number


def test_gate_angel_non_matching_alignment_fails_without_rolling():
    state = build_state()
    assert state.kingdoms[1].alignment is Alignment.GOOD
    request = CastRequest(spell=Spell.GATE_ANGEL, target=0)
    rng = ScriptedRandom([], choice_indices=[1])  # DRUID due -- not kingdom 1's GOOD

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is False
    assert result.reason == "not this alignment's turn for a Valhalla visit"
    assert state.last_gate_angel_kingdom is None


def test_gate_angel_due_alignment_is_cached_for_the_rest_of_the_turn():
    state = build_state()
    state.kingdoms[2].alignment = Alignment.DRUID
    state.add_leader(LeaderState(78, 2, "Druid Caster", ELSEWHERE))
    request = CastRequest(spell=Spell.GATE_ANGEL, target=0)
    # Only one choice_indices entry: the due-alignment draw. If the second
    # cast this turn re-rolled it, ScriptedRandom would raise IndexError.
    rng = ScriptedRandom([], choice_indices=[1])  # DRUID due

    first = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)
    second = execute_cast(state, kingdom_id=2, leader_id=78, request=request, rng=rng)

    assert first.applied is False  # kingdom 1 is GOOD, not this turn's DRUID
    assert second.applied is True  # kingdom 2 is DRUID, matches the cached due alignment


def test_gate_angel_divine_kingdom_never_receives_a_visit():
    state = build_state()
    state.kingdoms[1].alignment = Alignment.DIVINE
    request = CastRequest(spell=Spell.GATE_ANGEL, target=0)
    rng = ScriptedRandom([], choice_indices=[0])  # GOOD due -- Divine is never eligible

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is False
    assert result.reason == "not this alignment's turn for a Valhalla visit"


def test_gate_angel_undead_kingdom_never_receives_a_visit():
    state = build_state()
    state.kingdoms[1].alignment = Alignment.UNDEAD
    request = CastRequest(spell=Spell.GATE_ANGEL, target=0)
    rng = ScriptedRandom([], choice_indices=[4])  # EVIL due -- Undead is never eligible

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is False
    assert result.reason == "not this alignment's turn for a Valhalla visit"


def test_gate_angel_reservoir_sampling_second_candidate_can_win():
    state = build_state()
    state.kingdoms[2].alignment = Alignment.GOOD
    state.add_leader(LeaderState(78, 2, "Second Good King", ELSEWHERE))
    request = CastRequest(spell=Spell.GATE_ANGEL, target=0)
    # [0] = GOOD due-alignment draw; [0] = reservoir swap for the 2nd
    # candidate (rng.choice(range(2)) == 0 -> swap).
    rng = ScriptedRandom([], choice_indices=[0, 0])

    execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)
    assert state.last_gate_angel_kingdom == 1  # first candidate wins outright, no roll needed

    execute_cast(state, kingdom_id=2, leader_id=78, request=request, rng=rng)
    assert state.last_gate_angel_kingdom == 2  # the swap hands the visit to the 2nd candidate


def test_gate_angel_reservoir_sampling_second_candidate_can_lose():
    state = build_state()
    state.kingdoms[2].alignment = Alignment.GOOD
    state.add_leader(LeaderState(78, 2, "Second Good King", ELSEWHERE))
    request = CastRequest(spell=Spell.GATE_ANGEL, target=0)
    # [0] = GOOD due-alignment draw; [1] = no swap (rng.choice(range(2)) == 1).
    rng = ScriptedRandom([], choice_indices=[0, 1])

    execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)
    execute_cast(state, kingdom_id=2, leader_id=78, request=request, rng=rng)

    assert state.last_gate_angel_kingdom == 1  # first candidate keeps the win


def test_gate_angel_cycle_resets_once_all_5_alignments_are_visited():
    state = build_state()
    state.gate_angel_cycle_visited = {
        Alignment.GOOD,
        Alignment.DRUID,
        Alignment.NEUTRAL,
        Alignment.PAGAN,
        Alignment.EVIL,
    }
    request = CastRequest(spell=Spell.GATE_ANGEL, target=0)
    rng = ScriptedRandom([], choice_indices=[0])  # the sole survivor after the reset

    execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    # cleared (all 5 were already visited), then exactly one freshly consumed
    assert len(state.gate_angel_cycle_visited) == 1


def test_gate_angel_failed_roll_does_not_touch_any_state():
    state = build_state()
    state.leaders[CASTER_ID].skills = _skills_with(Ability.WHITE, 1)  # 30% chance
    request = CastRequest(spell=Spell.GATE_ANGEL, target=0)
    rng = ScriptedRandom([0.96], choice_indices=[0])  # GOOD due (matches), roll fails

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is False
    assert state.last_gate_angel_turn is None
    assert state.last_gate_angel_kingdom is None
    assert state.gate_angel_candidates_this_turn == 0


# ---------------------------------------------------------------------------
# Phase 192: spell-cast success formula corrections (a direct re-quote of
# Regolamento AK.txt [3.10] confirmed the 95% cap is real and Pagan
# Kingdoms get a +10% bonus to every spell except White Magic)
# ---------------------------------------------------------------------------


def test_action_spell_chance_caps_at_95_percent_even_at_high_skill_level():
    # Level 10: 15% + 15%*10 = 165% uncapped -- now clamped to 95%.
    state = build_state()
    state.leaders[CASTER_ID].skills = _skills_with(Ability.NECROMANCY, 10)
    state.add_leader(LeaderState(78, 2, "Enemy Hero", LOCATION))
    request = CastRequest(spell=Spell.KILL_ENEMY, target=78)
    rng = ScriptedRandom([0.94])  # under the 95% cap

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is True


def test_action_spell_can_fail_above_the_95_percent_cap_at_high_skill_level():
    # Before Phase 192 this roll would have always succeeded (uncapped
    # chance was 165%, and rng.random() never reaches 1.0).
    state = build_state()
    state.leaders[CASTER_ID].skills = _skills_with(Ability.NECROMANCY, 10)
    state.add_leader(LeaderState(78, 2, "Enemy Hero", LOCATION))
    request = CastRequest(spell=Spell.KILL_ENEMY, target=78)
    rng = ScriptedRandom([0.96])  # over the 95% cap

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is False
    assert result.reason == "spell failed"
    assert 78 in state.leaders  # untouched


def test_pagan_kingdom_caster_gets_a_10_percent_spell_cast_bonus():
    # Level 1 Necromancy: 30% base, +10% Pagan = 40%.
    state = build_state()
    state.kingdoms[1].alignment = Alignment.PAGAN
    state.leaders[CASTER_ID].skills = _skills_with(Ability.NECROMANCY, 1)
    state.add_leader(LeaderState(78, 2, "Enemy Hero", LOCATION))
    request = CastRequest(spell=Spell.KILL_ENEMY, target=78)
    rng = ScriptedRandom([0.35])  # over the un-bonused 30%, under the bonused 40%

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is True


def test_non_pagan_kingdom_caster_gets_no_bonus_at_the_same_roll():
    state = build_state()
    assert state.kingdoms[1].alignment is Alignment.GOOD
    state.leaders[CASTER_ID].skills = _skills_with(Ability.NECROMANCY, 1)
    state.add_leader(LeaderState(78, 2, "Enemy Hero", LOCATION))
    request = CastRequest(spell=Spell.KILL_ENEMY, target=78)
    rng = ScriptedRandom([0.35])  # over the un-bonused 30% base chance

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is False
    assert result.reason == "spell failed"


def test_pagan_kingdom_bonus_does_not_apply_to_white_magic_spells():
    # "un modificatore +10%... fuorche' quelli di Magia Bianca."
    state = build_state()
    state.kingdoms[1].alignment = Alignment.PAGAN
    state.leaders[CASTER_ID].skills = _skills_with(Ability.WHITE, 1)
    state.add_province(ProvinceState(LOCATION, Terrain.PLAINS, Race.HUMAN))
    request = CastRequest(spell=Spell.BLESS, target=_target(LOCATION))
    rng = ScriptedRandom([0.35])  # over the un-bonused 30% White Magic chance

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is False
    assert result.reason == "spell failed"


# ---------------------------------------------------------------------------
# Scar Terrain (Phase 201) -- secret spell, user-supplied
# ---------------------------------------------------------------------------


def test_scar_terrain_reduces_the_provinces_tax_base_by_2():
    state = build_state()
    state.add_province(ProvinceState(LOCATION, Terrain.PLAINS, Race.HUMAN))
    request = CastRequest(spell=Spell.SCAR_TERRAIN, target=_target(LOCATION))

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is True
    assert state.provinces[LOCATION].scar_terrain_gold_reduction == SCAR_TERRAIN_TAX_REDUCTION == 2


def test_scar_terrain_reduction_is_cumulative_across_casts():
    state = build_state()
    state.add_province(ProvinceState(LOCATION, Terrain.PLAINS, Race.HUMAN))
    request = CastRequest(spell=Spell.SCAR_TERRAIN, target=_target(LOCATION))

    execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)
    execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert state.provinces[LOCATION].scar_terrain_gold_reduction == 4


def test_scar_terrain_works_on_a_sea_province_too():
    # No terrain restriction: "Sea provinces will just lose whatever
    # provincial racial and army type they may have" confirms Sea is a
    # valid target, unlike Earthquake's own land-only restriction.
    state = build_state()
    state.add_province(ProvinceState(LOCATION, Terrain.SEA, Race.NO_RACE))
    request = CastRequest(spell=Spell.SCAR_TERRAIN, target=_target(LOCATION))

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is True
    assert state.provinces[LOCATION].scar_terrain_gold_reduction == 2


def test_scar_terrain_fails_when_the_province_is_out_of_range():
    state = build_state()
    request = CastRequest(spell=Spell.SCAR_TERRAIN, target=_target(LOCATION))

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is False
    assert result.reason == "province not found or not in range"


def test_scar_terrain_is_exhausted_at_or_below_zero():
    assert scar_terrain_is_exhausted(0) is True
    assert scar_terrain_is_exhausted(-5) is True
    assert scar_terrain_is_exhausted(1) is False


def test_scar_terrain_collapse_sea_province_becomes_no_race():
    province = ProvinceState(LOCATION, Terrain.SEA, Race.MERMISH)

    scar_terrain_collapse(province)

    assert province.race is Race.NO_RACE


def test_scar_terrain_collapse_land_province_uses_the_callers_chosen_race():
    province = ProvinceState(LOCATION, Terrain.PLAINS, Race.HUMAN)

    scar_terrain_collapse(province, new_land_race=Race.TROLLISH)

    assert province.race is Race.TROLLISH
    assert Race.TROLLISH in SCAR_TERRAIN_LAND_COLLAPSE_RACES


def test_scar_terrain_collapse_land_province_requires_a_valid_race():
    province = ProvinceState(LOCATION, Terrain.PLAINS, Race.HUMAN)

    with pytest.raises(ValueError):
        scar_terrain_collapse(province)

    with pytest.raises(ValueError):
        scar_terrain_collapse(province, new_land_race=Race.HUMAN)


# ---------------------------------------------------------------------------
# Mystic Winds (Phase 204) -- user-supplied, one of the secret spells 25-34
# ---------------------------------------------------------------------------


def test_mystic_winds_constants():
    assert MYSTIC_WINDS_MOVEMENT_POINTS == 5
    assert MYSTIC_WINDS_MOVES_AS_AIR_UNIT is True
    assert MYSTIC_WINDS_USES_MOVEMENT_POINTS_NORMALLY is True
    assert MYSTIC_WINDS_ENDS_BEFORE_ARMY_BATTLE is True


def test_mystic_winds_sets_movement_to_5_for_every_army_the_target_commands():
    state = build_state()
    state.add_leader(LeaderState(78, 1, "Field Commander", LOCATION))
    state.add_army(ArmyState(1, 1, ArmyType.LEGION, Quality.AVERAGE, LOCATION, movement_points=2, commanded_by=78))
    state.add_army(ArmyState(2, 1, ArmyType.BOWMEN, Quality.AVERAGE, LOCATION, movement_points=1, commanded_by=78))
    request = CastRequest(spell=Spell.MYSTIC_WINDS, target=78)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is True
    assert state.leaders[78].mystic_winds_active is True
    assert state.armies[1].movement_points == MYSTIC_WINDS_MOVEMENT_POINTS
    assert state.armies[2].movement_points == MYSTIC_WINDS_MOVEMENT_POINTS


def test_mystic_winds_can_target_the_caster_himself():
    state = build_state()
    state.add_army(ArmyState(1, 1, ArmyType.LEGION, Quality.AVERAGE, LOCATION, movement_points=0, commanded_by=CASTER_ID))
    request = CastRequest(spell=Spell.MYSTIC_WINDS, target=CASTER_ID)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is True
    assert state.leaders[CASTER_ID].mystic_winds_active is True
    assert state.armies[1].movement_points == MYSTIC_WINDS_MOVEMENT_POINTS


def test_mystic_winds_fails_when_target_is_not_colocated():
    state = build_state()
    state.add_leader(LeaderState(78, 1, "Field Commander", ELSEWHERE))
    request = CastRequest(spell=Spell.MYSTIC_WINDS, target=78)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is False
    assert result.reason == "not co-located"


def test_mystic_winds_fails_when_target_character_not_found():
    state = build_state()
    request = CastRequest(spell=Spell.MYSTIC_WINDS, target=999)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is False
    assert result.reason == "target character not found"


def test_mystic_winds_repeated_cast_stays_a_hard_set_not_cumulative():
    state = build_state()
    state.add_army(ArmyState(1, 1, ArmyType.LEGION, Quality.AVERAGE, LOCATION, movement_points=5, commanded_by=CASTER_ID))
    request = CastRequest(spell=Spell.MYSTIC_WINDS, target=CASTER_ID)

    first = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)
    second = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert first.applied is True
    assert second.applied is True
    assert state.armies[1].movement_points == MYSTIC_WINDS_MOVEMENT_POINTS


# ---------------------------------------------------------------------------
# Locate Object (Phase 206) -- user-supplied, one of the secret spells 25-34
# ---------------------------------------------------------------------------


def test_locate_object_cast_succeeds_and_mutates_nothing():
    state = build_state()
    request = CastRequest(spell=Spell.LOCATE_OBJECT, target=1)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is True


def test_locate_object_finds_a_leader_held_item():
    state = build_state()
    state.add_leader(LeaderState(78, 1, "Field Commander", ELSEWHERE))
    item = state.add_item(Treasure.WAND_FIREBALL, owner_leader_id=78)

    found = locate_object(state, item.item_id)

    assert found == LocateObjectResult(location=ELSEWHERE, holder_leader_id=78)


def test_locate_object_returns_none_for_an_unknown_item_id():
    state = build_state()

    assert locate_object(state, 999) is None


def test_locate_object_returns_none_for_a_feature_or_monster_guarded_item():
    # owner_leader_id=None models an item this project has no data for --
    # feature/monster-guarded treasure is a confirmed, sourced gap (see
    # models/item.py's own docstring), not distinguishable from "unknown".
    state = build_state()
    item = state.add_item(Treasure.WAND_FIREBALL, owner_leader_id=None)

    assert locate_object(state, item.item_id) is None


# ---------------------------------------------------------------------------
# Illusory Fog (Phase 207) -- user-supplied, one of the secret spells 25-34
# ---------------------------------------------------------------------------


def test_illusory_fog_constants():
    assert ILLUSORY_FOG_STRENGTH_MULTIPLIER == 0.5
    assert ILLUSORY_FOG_EXTRA_MOVEMENT_COST == 1
    assert ILLUSORY_FOG_DISSIPATES_AT_END_OF_GAMETURN is True


def test_illusory_fog_cast_sets_the_province_flag():
    state = build_state()
    state.add_province(ProvinceState(LOCATION, Terrain.PLAINS, Race.HUMAN))
    request = CastRequest(spell=Spell.ILLUS_FOG, target=_target(LOCATION))

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is True
    assert state.provinces[LOCATION].illusory_fog_active is True


def test_illusory_fog_fails_when_the_province_is_out_of_range():
    state = build_state()
    request = CastRequest(spell=Spell.ILLUS_FOG, target=_target(LOCATION))

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is False
    assert result.reason == "province not found or not in range"


def test_is_illusory_fog_affected_air_unit_true_for_overflight_air_types():
    assert is_illusory_fog_affected_air_unit(ArmyType.DRAGON_WING, mystic_winds_active=False) is True
    assert is_illusory_fog_affected_air_unit(ArmyType.EAGLE_WING, mystic_winds_active=False) is True


def test_is_illusory_fog_affected_air_unit_true_when_mystic_winds_active():
    assert is_illusory_fog_affected_air_unit(ArmyType.LEGION, mystic_winds_active=True) is True


def test_is_illusory_fog_affected_air_unit_false_for_ordinary_ground_units():
    assert is_illusory_fog_affected_air_unit(ArmyType.LEGION, mystic_winds_active=False) is False


def test_illusory_fog_strength_halves_when_affected():
    assert illusory_fog_strength(20.0, affected=True) == 10.0


def test_illusory_fog_strength_unchanged_when_not_affected():
    assert illusory_fog_strength(20.0, affected=False) == 20.0
