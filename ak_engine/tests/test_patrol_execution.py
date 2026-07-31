from __future__ import annotations

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.enums import Ability, Maneuver
from ak_engine.models.game_state import ArmyState, GameState, KingdomState, LeaderState, ProvinceState
from ak_engine.models.kingdom import SkillTable
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.race import Race
from ak_engine.models.temper import Temper
from ak_engine.models.treasure import Treasure
from ak_engine.turn.challenge_pursue_decode import PursueRequest
from ak_engine.turn.combat import Quality
from ak_engine.turn.movement import NORMAL_MAP_BOUNDS, MapBounds
from ak_engine.turn.movement import neighbors as _neighbors
from ak_engine.turn.patrol_execution import _leader_combatant, execute_patrol, find_patrol_target
from ak_engine.turn.search_decode import SearchTactic

from _helpers import ScriptedRandom

_BOUNDS = MapBounds(*NORMAL_MAP_BOUNDS)
HOME = HexCoord(5, 4)
ADJACENT = _neighbors(HOME, _BOUNDS)[0]
FAR_AWAY = HexCoord(20, 10)


def _skills_with(ability: Ability, skill: int, aptitude: int) -> SkillTable:
    raw = [0] * 30
    raw[ability.value * 2] = skill
    raw[ability.value * 2 + 1] = aptitude
    return SkillTable(raw)


def _peaceful_request(target_id: int) -> PursueRequest:
    return PursueRequest(target_character_id=target_id, unconfirmed_extra0=0, tactics=[SearchTactic(Maneuver.TALK)])


def _melee_request(target_id: int) -> PursueRequest:
    return PursueRequest(target_character_id=target_id, unconfirmed_extra0=0, tactics=[SearchTactic(Maneuver.MELEE)])


def _base_state() -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Patrolia", Race.HUMAN, Alignment.GOOD, HOME))
    state.add_kingdom(KingdomState(2, "Intrudia", Race.HUMAN, Alignment.GOOD, ADJACENT))
    state.add_province(ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_province(ProvinceState(ADJACENT, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2))
    return state


def test_leader_combatant_reads_real_temper():
    state = _base_state()
    leader = LeaderState(1, kingdom_id=1, name="Patroller", location=HOME, temper=Temper.BERSERK)
    state.add_leader(leader)

    combatant = _leader_combatant(leader, state)

    assert combatant.temper is Temper.BERSERK


# -- find_patrol_target: rules (a), (f) ---------------------------------


def test_find_patrol_target_ignored_when_patroller_leads_an_army():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Patroller", location=HOME))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Intruder", location=HOME))
    state.add_army(ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, HOME, commanded_by=1))

    assert find_patrol_target(state, 1, _BOUNDS) is None


def test_find_patrol_target_none_when_home_province_unowned():
    state = _base_state()
    state.provinces[HOME].owner_kingdom_id = None
    state.add_leader(LeaderState(1, kingdom_id=1, name="Patroller", location=HOME))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Intruder", location=HOME))

    assert find_patrol_target(state, 1, _BOUNDS) is None


def test_find_patrol_target_none_when_home_province_owned_by_a_non_allied_kingdom():
    state = _base_state()
    state.provinces[HOME].owner_kingdom_id = 2  # not the patroller's own, not an ally
    state.add_leader(LeaderState(1, kingdom_id=1, name="Patroller", location=HOME))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Intruder", location=HOME))

    assert find_patrol_target(state, 1, _BOUNDS) is None


def test_find_patrol_target_allowed_from_an_allied_owned_province():
    state = _base_state()
    state.provinces[HOME].owner_kingdom_id = 2
    state.allied_kingdoms.add(frozenset({1, 2}))
    state.add_leader(LeaderState(1, kingdom_id=1, name="Patroller", location=HOME))
    # An allied intruder is never "enemy" though -- add a genuinely hostile
    # third Kingdom's leader instead.
    state.add_kingdom(KingdomState(3, "Hostilia", Race.HUMAN, Alignment.EVIL, HOME))
    state.add_leader(LeaderState(3, kingdom_id=3, name="Intruder", location=HOME))

    target = find_patrol_target(state, 1, _BOUNDS)

    assert target is not None
    assert target.leader_id == 3


# -- find_patrol_target: rules (a) candidate, (b), (c) -------------------


def test_find_patrol_target_excludes_an_armied_intruder():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Patroller", location=HOME))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Intruder", location=HOME))
    state.add_army(ArmyState(201, 2, ArmyType.GARRISON, Quality.GREEN, HOME, commanded_by=2))

    assert find_patrol_target(state, 1, _BOUNDS) is None


def test_find_patrol_target_excludes_a_same_kingdom_character():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Patroller", location=HOME))
    state.add_leader(LeaderState(2, kingdom_id=1, name="Friend", location=HOME))

    assert find_patrol_target(state, 1, _BOUNDS) is None


def test_find_patrol_target_excludes_an_allied_kingdoms_character():
    state = _base_state()
    state.allied_kingdoms.add(frozenset({1, 2}))
    state.add_leader(LeaderState(1, kingdom_id=1, name="Patroller", location=HOME))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Ally", location=HOME))

    assert find_patrol_target(state, 1, _BOUNDS) is None


def test_find_patrol_target_excludes_a_kingdomless_independent_hero():
    # Same "kingdomless is never automatically hostile" reading this
    # module's own docstring cites from _sees_nonallied_defender.
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Patroller", location=HOME))
    state.add_leader(LeaderState(2, kingdom_id=None, name="Wanderer", location=HOME))

    assert find_patrol_target(state, 1, _BOUNDS) is None


def test_find_patrol_target_excludes_a_character_outside_current_and_adjacent_hexes():
    state = _base_state()
    state.add_province(ProvinceState(FAR_AWAY, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2))
    state.add_leader(LeaderState(1, kingdom_id=1, name="Patroller", location=HOME))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Intruder", location=FAR_AWAY))

    assert find_patrol_target(state, 1, _BOUNDS) is None


def test_find_patrol_target_finds_a_same_hex_enemy():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Patroller", location=HOME))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Intruder", location=HOME))

    target = find_patrol_target(state, 1, _BOUNDS)

    assert target is not None and target.leader_id == 2


def test_find_patrol_target_finds_an_adjacent_hex_enemy():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Patroller", location=HOME))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Intruder", location=ADJACENT))

    target = find_patrol_target(state, 1, _BOUNDS)

    assert target is not None and target.leader_id == 2


# -- find_patrol_target: rules (g), (h) -----------------------------------


def test_find_patrol_target_excludes_an_intruder_with_a_higher_combat_skill():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Patroller", location=HOME, skills=_skills_with(Ability.MELEE, 1, 9)))
    state.add_leader(
        LeaderState(2, kingdom_id=2, name="Intruder", location=HOME, skills=_skills_with(Ability.MELEE, 2, 9))
    )

    assert find_patrol_target(state, 1, _BOUNDS) is None


def test_find_patrol_target_allows_an_intruder_with_an_equal_combat_skill():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Patroller", location=HOME, skills=_skills_with(Ability.MELEE, 1, 9)))
    state.add_leader(
        LeaderState(2, kingdom_id=2, name="Intruder", location=HOME, skills=_skills_with(Ability.MELEE, 1, 9))
    )

    target = find_patrol_target(state, 1, _BOUNDS)

    assert target is not None and target.leader_id == 2


def test_find_patrol_target_uses_the_max_magic_school_as_magic_skill():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Patroller", location=HOME, skills=_skills_with(Ability.WHITE, 3, 9)))
    state.add_leader(
        LeaderState(2, kingdom_id=2, name="Intruder", location=HOME, skills=_skills_with(Ability.ILLUSION, 3, 9))
    )

    target = find_patrol_target(state, 1, _BOUNDS)

    assert target is not None and target.leader_id == 2


def test_find_patrol_target_picks_the_highest_skill_intruder_when_several_qualify():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Patroller", location=HOME, skills=_skills_with(Ability.MELEE, 3, 9)))
    state.add_leader(
        LeaderState(2, kingdom_id=2, name="Weaker", location=HOME, skills=_skills_with(Ability.MELEE, 0, 9))
    )
    state.add_leader(
        LeaderState(3, kingdom_id=2, name="Stronger", location=HOME, skills=_skills_with(Ability.MELEE, 2, 9))
    )

    target = find_patrol_target(state, 1, _BOUNDS)

    assert target is not None and target.leader_id == 3


def test_find_patrol_target_breaks_a_skill_tie_with_the_lower_leader_id():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Patroller", location=HOME))
    state.add_leader(LeaderState(30, kingdom_id=2, name="A", location=HOME))
    state.add_leader(LeaderState(20, kingdom_id=2, name="B", location=HOME))

    target = find_patrol_target(state, 1, _BOUNDS)

    assert target is not None and target.leader_id == 20


# -- execute_patrol: no target / same-hex / adjacent Spy Table roll -------


def test_execute_patrol_reports_no_intruder_detected():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Patroller", location=HOME))

    result = execute_patrol(
        state, 1, _peaceful_request(1), ScriptedRandom([]), board_width=NORMAL_MAP_BOUNDS[0], board_height=NORMAL_MAP_BOUNDS[1]
    )

    assert result.intercepted is False
    assert result.target_leader_id is None
    assert result.reason == "no intruder detected"


def test_execute_patrol_same_hex_intruder_never_rolls_the_spy_table():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Patroller", location=HOME))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Intruder", location=HOME))

    # No Spy skill (level 0) would normally risk the 50% wander roll --
    # but that only applies to an *adjacent*-hex interception (rule i).
    result = execute_patrol(
        state, 1, _peaceful_request(1), ScriptedRandom([]), board_width=NORMAL_MAP_BOUNDS[0], board_height=NORMAL_MAP_BOUNDS[1]
    )

    assert result.intercepted is True
    assert result.target_leader_id == 2


def test_execute_patrol_adjacent_intruder_wanders_off_at_spy_skill_zero():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Patroller", location=HOME))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Intruder", location=ADJACENT))

    result = execute_patrol(
        state, 1, _peaceful_request(1), ScriptedRandom([0.1]), board_width=NORMAL_MAP_BOUNDS[0], board_height=NORMAL_MAP_BOUNDS[1]
    )

    assert result.intercepted is False
    assert result.target_leader_id == 2
    assert result.reason == "wandered into a random hex"


def test_execute_patrol_adjacent_intruder_intercepted_when_roll_beats_50_percent():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Patroller", location=HOME))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Intruder", location=ADJACENT))

    result = execute_patrol(
        state, 1, _peaceful_request(1), ScriptedRandom([0.9]), board_width=NORMAL_MAP_BOUNDS[0], board_height=NORMAL_MAP_BOUNDS[1]
    )

    assert result.intercepted is True
    assert result.target_leader_id == 2


def test_execute_patrol_adjacent_intruder_guaranteed_with_spy_skill():
    state = _base_state()
    state.add_leader(
        LeaderState(1, kingdom_id=1, name="Patroller", location=HOME, skills=_skills_with(Ability.SPY, 1, 9))
    )
    state.add_leader(LeaderState(2, kingdom_id=2, name="Intruder", location=ADJACENT))

    # No roll consumed at all for the wander check once Spy skill is 1+.
    result = execute_patrol(
        state, 1, _peaceful_request(1), ScriptedRandom([]), board_width=NORMAL_MAP_BOUNDS[0], board_height=NORMAL_MAP_BOUNDS[1]
    )

    assert result.intercepted is True
    assert result.target_leader_id == 2


# -- execute_patrol: combat resolution -------------------------------------


def test_execute_patrol_peaceful_request_never_fights():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Patroller", location=HOME))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Intruder", location=HOME))

    result = execute_patrol(
        state, 1, _peaceful_request(1), ScriptedRandom([]), board_width=NORMAL_MAP_BOUNDS[0], board_height=NORMAL_MAP_BOUNDS[1]
    )

    assert result.combat_occurred is False
    assert 2 in state.leaders


def test_execute_patrol_melee_request_fights_and_removes_the_loser():
    state = _base_state()
    state.add_leader(
        LeaderState(1, kingdom_id=1, name="Patroller", location=HOME, skills=_skills_with(Ability.MELEE, 3, 9))
    )
    state.add_leader(
        LeaderState(2, kingdom_id=2, name="Intruder", location=HOME, skills=_skills_with(Ability.MELEE, 0, 9))
    )

    # Same hex -> no Spy Table roll; neither is a King/army-leader -> no
    # acceptance roll either. Patroller always acts first (higher Melee
    # skill) and always hits while the intruder always misses -- same
    # decisive-win script shape as test_pursue_execution.py's own
    # test_execute_pursue_combat_removes_the_decisive_loser.
    result = execute_patrol(
        state,
        1,
        _melee_request(1),
        ScriptedRandom([0.1, 0.5, 0.9] * 15),
        board_width=NORMAL_MAP_BOUNDS[0],
        board_height=NORMAL_MAP_BOUNDS[1],
    )

    assert result.combat_occurred is True
    assert result.winner_leader_id == 1
    assert result.loser_leader_id == 2
    assert result.loser_killed is True
    assert 2 not in state.leaders


def test_execute_patrol_melee_request_loots_the_decisive_losers_items():
    # Phase 313, rulebook [5.9] -- same setup as the removal test above.
    state = _base_state()
    state.add_leader(
        LeaderState(1, kingdom_id=1, name="Patroller", location=HOME, skills=_skills_with(Ability.MELEE, 3, 9))
    )
    state.add_leader(
        LeaderState(2, kingdom_id=2, name="Intruder", location=HOME, skills=_skills_with(Ability.MELEE, 0, 9))
    )
    item = state.add_item(Treasure.ABILITY_MELEE, owner_leader_id=2)

    result = execute_patrol(
        state,
        1,
        _melee_request(1),
        ScriptedRandom([0.1, 0.5, 0.9] * 15),
        board_width=NORMAL_MAP_BOUNDS[0],
        board_height=NORMAL_MAP_BOUNDS[1],
    )

    assert result.loser_killed is True
    assert result.looted_item_ids == [item.item_id]
    assert state.items[item.item_id].owner_leader_id == 1
