from __future__ import annotations

from unittest.mock import patch

from ak_engine.models.alignment import Alignment
from ak_engine.models.enums import ActionCode
from ak_engine.models.game_state import GameState, KingdomState, LeaderState
from ak_engine.models.leader import Leader
from ak_engine.models.map import HexCoord
from ak_engine.models.plan import ActionPlan, PlanPhase, PlanSegment
from ak_engine.models.race import Race
from ak_engine.models.treasure import Treasure
from ak_engine.turn.challenge_execution import ChallengeCombatOutcome
from ak_engine.turn.legendary_item_rescue import deliver_squire_items, rescue_legendary_items
from ak_engine.turn.random_encounter_execution import resolve_random_encounter
from ak_engine.turn.turn_processor import TurnLeader, run_turn
from ak_engine.report.turn_report import describe_random_encounter

from _helpers import ScriptedRandom

SPOT = HexCoord(5, 4)
ELSEWHERE = HexCoord(7, 7)


def _state() -> GameState:
    state = GameState()
    state.turn_number = 2
    state.add_kingdom(KingdomState(1, "Homeland", Race.HUMAN, Alignment.GOOD, SPOT))
    state.add_kingdom(KingdomState(2, "Otherland", Race.HUMAN, Alignment.GOOD, HexCoord(6, 4)))
    state.add_leader(LeaderState(100, 1, "King", HexCoord(1, 1), is_king=True))
    state.add_leader(LeaderState(1, 1, "Fallen", SPOT))
    return state


def _fall(state: GameState, leader_id: int = 1):
    leader = state.leaders[leader_id]
    state.remove_leader(leader_id)
    return rescue_legendary_items(state, leader_id, leader.kingdom_id, leader.location)


def test_a_comrade_on_the_spot_takes_the_legendary_item_at_once_a_hero_before_the_king():
    state = _state()
    state.add_leader(LeaderState(2, 1, "Friend", SPOT))
    state.leaders[100].location = SPOT
    excalibur = state.add_item(Treasure.LEADERSHIP_HUMAN, 1)

    rescued = _fall(state)

    assert [r.taken_by_leader_id for r in rescued] == [2]  # lowest-id Hero, not the King
    assert state.items[excalibur.item_id].owner_leader_id == 2
    assert state.pending_squire_deliveries == []


def test_the_king_himself_takes_it_when_he_is_the_only_comrade_there():
    state = _state()
    state.leaders[100].location = SPOT
    item = state.add_item(Treasure.WEAPON_1, 1)

    _fall(state)

    assert state.items[item.item_id].owner_leader_id == 100


def test_a_comrade_elsewhere_or_of_another_kingdom_does_not_count_so_the_squire_carries_it():
    state = _state()
    state.add_leader(LeaderState(2, 1, "Far friend", ELSEWHERE))
    state.add_leader(LeaderState(3, 2, "Foreigner", SPOT))
    item = state.add_item(Treasure.MONSTER_AID_WHALE, 1)

    rescued = _fall(state)

    assert [r.taken_by_leader_id for r in rescued] == [None]
    assert state.items[item.item_id].owner_leader_id == 1  # still with the dead hero until the turn ends
    assert state.pending_squire_deliveries == [(item.item_id, 1)]

    deliver_squire_items(state)

    assert state.items[item.item_id].owner_leader_id == 100  # the King
    assert state.pending_squire_deliveries == []


def test_a_minor_item_is_left_to_its_fate():
    state = _state()
    state.add_leader(LeaderState(2, 1, "Friend", SPOT))
    minor = state.add_item(Treasure.ABILITY_MARCH, 1)

    assert _fall(state) == []

    assert state.items[minor.item_id].owner_leader_id == 1
    assert state.pending_squire_deliveries == []


def test_an_independent_hero_has_no_kingdom_to_return_the_item_to():
    state = GameState()
    state.add_leader(LeaderState(1, None, "Loner", SPOT))
    item = state.add_item(Treasure.LEADERSHIP_HUMAN, 1)

    assert rescue_legendary_items(state, 1, None, SPOT) == []
    assert state.pending_squire_deliveries == []
    assert state.items[item.item_id].owner_leader_id == 1


def test_when_the_king_falls_his_squire_brings_the_item_to_the_royal_heir():
    state = _state()
    item = state.add_item(Treasure.LEADERSHIP_ELVEN, 100)

    rescued = _fall(state, 100)
    assert [r.taken_by_leader_id for r in rescued] == [None]
    assert 100 not in state.leaders  # no King until the turn boundary

    state.install_pending_royal_heirs()
    deliver_squire_items(state)

    assert 100 in state.leaders and state.leaders[100].is_royal_heir
    assert state.items[item.item_id].owner_leader_id == 100


def test_if_the_king_falls_with_a_hero_on_the_spot_the_hero_takes_it():
    state = _state()
    state.leaders[1].location = ELSEWHERE  # not on the spot: the item is the King's, who falls at SPOT
    state.leaders[100].location = SPOT
    state.add_leader(LeaderState(2, 1, "Friend", SPOT))
    item = state.add_item(Treasure.LEADERSHIP_DWARVEN, 100)

    _fall(state, 100)

    assert state.items[item.item_id].owner_leader_id == 2


def test_run_turn_delivers_the_squires_items_after_the_royal_heirs_are_installed():
    state = _state()
    item = state.add_item(Treasure.LEADERSHIP_ORCISH, 100)
    _fall(state, 100)
    wait = PlanPhase(label="P0", action=ActionCode.WAIT, obj=0, extra=[0])
    other = Leader(1000, "Idle", ActionPlan(1000, [PlanSegment(0, 1, (), {"P0": wait})]))
    state.add_leader(LeaderState(1000, 1, "Idle", ELSEWHERE))

    run_turn([TurnLeader(other, 1)], state, board_width=20)

    assert state.items[item.item_id].owner_leader_id == 100
    assert state.pending_squire_deliveries == []


def _lose_to_a_wandering_monster(state: GameState):
    plan = ActionPlan(1, [PlanSegment(0, 0, (), {"P0": PlanPhase("P0", ActionCode.LMOVE, 0)})])
    with patch("ak_engine.turn.random_encounter_execution.terrain_roll", return_value=True), patch(
        "ak_engine.turn.random_encounter_execution.select_random_monster"
    ) as mock_monster, patch("ak_engine.turn.random_encounter_execution.is_patrol_framing", return_value=False), patch(
        "ak_engine.turn.random_encounter_execution.resolve_challenge_combat",
        return_value=ChallengeCombatOutcome(winner="b"),
    ):
        from ak_engine.models.monster import Monster

        mock_monster.return_value = Monster.TROLL
        return resolve_random_encounter(state, 1, SPOT, plan, check_escort=True, rng=ScriptedRandom([0.5] * 8))


def test_a_hero_killed_by_a_wandering_monster_keeps_his_legendary_item_in_the_game():
    state = _state()
    state.add_leader(LeaderState(2, 1, "Friend", SPOT))
    item = state.add_item(Treasure.LEADERSHIP_HUMAN, 1)

    result = _lose_to_a_wandering_monster(state)

    assert result.leader_died is True
    assert [r.treasure for r in result.rescued_items] == [Treasure.LEADERSHIP_HUMAN]
    assert state.items[item.item_id].owner_leader_id == 2
    lines = describe_random_encounter(result, state, "Fallen", __import__("random").Random(1))
    assert any("Excalibur" in line and "Friend" in line for line in lines)


def test_the_report_names_the_squire_when_nobody_is_on_the_spot():
    state = _state()
    state.add_item(Treasure.LEADERSHIP_HUMAN, 1)

    result = _lose_to_a_wandering_monster(state)

    lines = describe_random_encounter(result, state, "Fallen", __import__("random").Random(1))
    assert any("squire" in line and "Excalibur" in line for line in lines)
