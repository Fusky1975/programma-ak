from __future__ import annotations

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.enums import ActionCode
from ak_engine.models.game_state import ArmyState, GameState, KingdomState, LeaderState
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.monster import Monster
from ak_engine.models.plan import ActionPlan, PlanPhase, PlanSegment
from ak_engine.models.race import Race
from ak_engine.turn.combat import Quality
from ak_engine.turn.random_encounter import (
    habitat_accepts,
    is_humanoid_species,
    is_leader_eligible_for_random_encounter,
    is_patrol_framing,
    leader_plan_has_forbidden_action,
    leader_travels_with_kingdom_army,
    patrol_evades_via_diplomacy,
    random_encounter_gate_open,
    select_general_monster,
    select_humanoid_monster,
    select_random_monster,
    terrain_roll,
)

from _helpers import ScriptedRandom

HOME = HexCoord(5, 4)


def _base_state() -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Homeland", Race.HUMAN, Alignment.GOOD, HOME))
    state.add_kingdom(KingdomState(2, "Otherland", Race.HUMAN, Alignment.GOOD, HexCoord(6, 4)))
    return state


def _plan(*phases: PlanPhase) -> ActionPlan:
    segment = PlanSegment(plan_start=0, plan_end=0, sp=(), phases={f"P{i}": p for i, p in enumerate(phases)})
    return ActionPlan(leader_id=1, segments=[segment])


def _empty_plan() -> ActionPlan:
    return ActionPlan(leader_id=1, segments=[])


# -- terrain_roll --


def test_terrain_roll_succeeds_below_the_threshold():
    assert terrain_roll(Terrain.PLAINS, ScriptedRandom([0.09])) is True


def test_terrain_roll_fails_at_the_threshold():
    # renc[PLAINS] = 10 -- a roll landing exactly at 10% fails (inclusive on the fail side).
    assert terrain_roll(Terrain.PLAINS, ScriptedRandom([0.10])) is False


def test_terrain_roll_never_succeeds_on_no_terrain():
    assert terrain_roll(Terrain.NO_TERRAIN, ScriptedRandom([0.0])) is False


# -- habitat_accepts --


def test_habitat_accepts_low_wildcard_band():
    assert habitat_accepts(0, Terrain.SEA) is True
    assert habitat_accepts(18, Terrain.MTNS) is True


def test_habitat_accepts_high_wildcard_band():
    assert habitat_accepts(27, Terrain.PLAINS) is True
    assert habitat_accepts(28, Terrain.JUNGLE) is True


def test_habitat_accepts_desert_band():
    assert habitat_accepts(19, Terrain.DESERT) is True
    assert habitat_accepts(20, Terrain.PLAINS) is False


def test_habitat_accepts_jungle_band():
    assert habitat_accepts(21, Terrain.JUNGLE) is True
    assert habitat_accepts(22, Terrain.FOREST) is False


def test_habitat_accepts_forest_band():
    assert habitat_accepts(23, Terrain.FOREST) is True
    assert habitat_accepts(24, Terrain.DESERT) is False


def test_habitat_accepts_mountain_band():
    assert habitat_accepts(25, Terrain.MTNS) is True
    assert habitat_accepts(26, Terrain.PLAINS) is False


def test_habitat_accepts_sea_band_drops_swamp():
    # >=29 real text names Sea, No Terrain, or Swamp -- Swamp doesn't
    # exist anywhere in this project's Terrain enum, so only the other
    # two are ever accepted.
    assert habitat_accepts(29, Terrain.SEA) is True
    assert habitat_accepts(30, Terrain.NO_TERRAIN) is True
    assert habitat_accepts(29, Terrain.PLAINS) is False


# -- select_humanoid_monster --
# Draw order: IRand mod 5 (offset base), multiplier Rand2, additive Rand2.


def test_select_humanoid_monster_archer():
    # offset base 0, mult 0, add 0 -> offset 0 -> Archer (14).
    result = select_humanoid_monster(ScriptedRandom([0.0, 0.0, 0.0]))
    assert result is Monster.ARCHER


def test_select_humanoid_monster_swordsman():
    # base 1 (0.3*5=1.5 -> 1), mult 1 (0.9*2=1.8 -> 1), add 0 -> offset 1 -> Swordsman (15).
    result = select_humanoid_monster(ScriptedRandom([0.3, 0.9, 0.0]))
    assert result is Monster.SWORDSMAN


def test_select_humanoid_monster_witch_at_top_of_range():
    # base 4 (0.9*5=4), mult 1 (0.9*2=1), add 1 (0.9*2=1) -> offset 5 -> Witch (14+5=19)? verify arithmetic below.
    result = select_humanoid_monster(ScriptedRandom([0.9, 0.9, 0.9]))
    assert result.value == Monster.ARCHER.value + 4 * 1 + 1


# -- select_general_monster --


# Monster-index draws use an (n + 0.5) / 60 buffer rather than a bare
# n / 60 fraction -- a bare fraction can truncate to n-1 under floating-
# point rounding (e.g. 14/60*60 can land fractionally under 14.0),
# landing on the wrong species. The buffer keeps `int(rng.random()*60)`
# safely inside bucket n regardless of float rounding direction.
_ARCHER_DRAW = (Monster.ARCHER.value + 0.5) / 60
_TITAN_DRAW = (Monster.TITAN.value + 0.5) / 60
_COUATL_DRAW = (Monster.COUATL.value + 0.5) / 60
_GW_WHALE_DRAW = (Monster.GW_WHALE.value + 0.5) / 60


def test_select_general_monster_accepts_a_low_hp_species_on_the_first_try():
    # Archer: HP=10 -> accept_strength=100/100=1.0, any roll < 1.0
    # accepts; habitat_lo=15, draw 0.0 -> habitat 15, the wildcard
    # "<=18" band -- accepted on any terrain.
    rng = ScriptedRandom([_ARCHER_DRAW, 0.5, 0.0])
    result = select_general_monster(Terrain.PLAINS, rng)
    assert result is Monster.ARCHER


def test_select_general_monster_retries_on_a_rejected_hp_roll():
    # First proposal: Titan, HP=40 -> accept_strength=100/1600=0.0625;
    # roll 0.5 rejects (>= 0.0625), forcing a full redraw (no habitat
    # roll consumed for the rejected attempt). Second proposal: Archer,
    # HP=10 -> accept_strength=1.0, roll 0.05 accepts; habitat draw
    # 0.0 -> 15.
    rng = ScriptedRandom([_TITAN_DRAW, 0.5, _ARCHER_DRAW, 0.05, 0.0])
    result = select_general_monster(Terrain.SEA, rng)
    assert result is Monster.ARCHER


def test_select_general_monster_retries_on_a_rejected_habitat():
    # Couatl: HP=20, hab range (21,22), only accepts Jungle -- a 0.0
    # habitat draw lands on 21 (Jungle-only), rejected against Plains,
    # forcing a redraw. Second proposal: Archer, accepted.
    rng = ScriptedRandom([_COUATL_DRAW, 0.0, 0.0, _ARCHER_DRAW, 0.05, 0.0])
    result = select_general_monster(Terrain.PLAINS, rng)
    assert result is Monster.ARCHER


def test_select_general_monster_sea_wildcard_band_accepts_any_terrain():
    # Great White Whale: HP=30, hab range (27,30) -- habitat draw
    # 0.0 -> 27, the high wildcard band -- accepted on any terrain.
    rng = ScriptedRandom([_GW_WHALE_DRAW, 0.0, 0.0])
    result = select_general_monster(Terrain.MTNS, rng)
    assert result is Monster.GW_WHALE


# -- select_random_monster --


def test_select_random_monster_coin_picks_humanoid_branch():
    # coin=1 (0.9*2=1) -> humanoid branch; base 0, mult 0, add 0 -> Archer.
    rng = ScriptedRandom([0.9, 0.0, 0.0, 0.0])
    result = select_random_monster(Terrain.PLAINS, rng)
    assert result is Monster.ARCHER


def test_select_random_monster_coin_picks_general_branch():
    # coin=0 (0.0*2=0) -> general branch; Archer proposed and accepted.
    rng = ScriptedRandom([0.0, _ARCHER_DRAW, 0.5, 0.0])
    result = select_random_monster(Terrain.PLAINS, rng)
    assert result is Monster.ARCHER


# -- is_humanoid_species / is_patrol_framing --


def test_is_humanoid_species_boundaries():
    assert is_humanoid_species(Monster.GIANT) is True
    assert is_humanoid_species(Monster.WITCH) is True
    assert is_humanoid_species(Monster.TITAN) is False
    assert is_humanoid_species(Monster.DRYAD) is False


def test_is_patrol_framing_requires_odd_parity_and_humanoid():
    assert is_patrol_framing(1, 2, Monster.GIANT) is True  # 1+2=3, odd
    assert is_patrol_framing(1, 1, Monster.GIANT) is False  # 1+1=2, even
    assert is_patrol_framing(1, 2, Monster.TITAN) is False  # odd parity, not humanoid


# -- patrol_evades_via_diplomacy --


def test_patrol_evades_via_diplomacy_always_safe_when_allied():
    state = _base_state()
    state.allied_kingdoms.add(frozenset({1, 2}))
    assert patrol_evades_via_diplomacy(state, 1, 2, ScriptedRandom([0.9])) is True


def test_patrol_evades_via_diplomacy_fifty_fifty_when_not_allied():
    state = _base_state()
    assert patrol_evades_via_diplomacy(state, 1, 2, ScriptedRandom([0.6])) is True
    assert patrol_evades_via_diplomacy(state, 1, 2, ScriptedRandom([0.4])) is False


# -- random_encounter_gate_open --


def test_random_encounter_gate_closed_on_turn_one():
    state = _base_state()
    state.turn_number = 1
    assert random_encounter_gate_open(state) is False


def test_random_encounter_gate_open_from_turn_two():
    state = _base_state()
    state.turn_number = 2
    assert random_encounter_gate_open(state) is True


# -- leader_travels_with_kingdom_army --


def test_leader_travels_with_kingdom_army_true_for_a_loyal_army():
    state = _base_state()
    leader = LeaderState(1, kingdom_id=1, name="Hero", location=HOME)
    state.add_leader(leader)
    state.add_army(ArmyState(1, kingdom_id=1, army_type=ArmyType.PHALANX, quality=Quality.AVERAGE, location=HOME))
    assert leader_travels_with_kingdom_army(state, leader, HOME) is True


def test_leader_travels_with_kingdom_army_false_for_a_foreign_army():
    state = _base_state()
    leader = LeaderState(1, kingdom_id=1, name="Hero", location=HOME)
    state.add_leader(leader)
    state.add_army(ArmyState(1, kingdom_id=2, army_type=ArmyType.PHALANX, quality=Quality.AVERAGE, location=HOME))
    assert leader_travels_with_kingdom_army(state, leader, HOME) is False


def test_leader_travels_with_kingdom_army_false_when_no_army_present():
    state = _base_state()
    leader = LeaderState(1, kingdom_id=1, name="Hero", location=HOME)
    state.add_leader(leader)
    assert leader_travels_with_kingdom_army(state, leader, HOME) is False


# -- leader_plan_has_forbidden_action --


def test_leader_plan_has_forbidden_action_finds_a_later_phase_in_a_later_segment():
    plan = ActionPlan(
        leader_id=1,
        segments=[
            PlanSegment(plan_start=0, plan_end=0, sp=(), phases={"P0": PlanPhase("P0", ActionCode.LMOVE, 0)}),
            PlanSegment(
                plan_start=0,
                plan_end=0,
                sp=(),
                phases={
                    "P0": PlanPhase("P0", ActionCode.LMOVE, 0),
                    "P3": PlanPhase("P3", ActionCode.DEFEND, 0),
                },
            ),
        ],
    )
    assert leader_plan_has_forbidden_action(plan) is True


def test_leader_plan_has_forbidden_action_false_when_none_present():
    plan = _plan(PlanPhase("P0", ActionCode.LMOVE, 0), PlanPhase("P1", ActionCode.SEARCH, 0))
    assert leader_plan_has_forbidden_action(plan) is False


def test_leader_plan_has_forbidden_action_false_for_an_empty_plan():
    assert leader_plan_has_forbidden_action(_empty_plan()) is False


# -- is_leader_eligible_for_random_encounter --


def test_is_leader_eligible_for_random_encounter_excludes_kingdomless_leaders():
    state = _base_state()
    leader = LeaderState(1, kingdom_id=None, name="Wanderer", location=HOME)
    state.add_leader(leader)
    plan = _plan(PlanPhase("P0", ActionCode.LMOVE, 0))
    assert is_leader_eligible_for_random_encounter(state, leader, plan, HOME, check_escort=False) is False


def test_is_leader_eligible_for_random_encounter_excludes_kings():
    state = _base_state()
    leader = LeaderState(1, kingdom_id=1, name="King", location=HOME, is_king=True)
    state.add_leader(leader)
    plan = _plan(PlanPhase("P0", ActionCode.LMOVE, 0))
    assert is_leader_eligible_for_random_encounter(state, leader, plan, HOME, check_escort=False) is False


def test_is_leader_eligible_for_random_encounter_excludes_escorted_leaders_when_checked():
    state = _base_state()
    leader = LeaderState(1, kingdom_id=1, name="Hero", location=HOME)
    state.add_leader(leader)
    state.add_army(ArmyState(1, kingdom_id=1, army_type=ArmyType.PHALANX, quality=Quality.AVERAGE, location=HOME))
    plan = _plan(PlanPhase("P0", ActionCode.LMOVE, 0))

    assert is_leader_eligible_for_random_encounter(state, leader, plan, HOME, check_escort=True) is False
    assert is_leader_eligible_for_random_encounter(state, leader, plan, HOME, check_escort=False) is True


def test_is_leader_eligible_for_random_encounter_excludes_forbidden_plan_actions():
    state = _base_state()
    leader = LeaderState(1, kingdom_id=1, name="Hero", location=HOME)
    state.add_leader(leader)
    plan = _plan(PlanPhase("P0", ActionCode.LMOVE, 0), PlanPhase("P2", ActionCode.RECRUIT, 0))
    assert is_leader_eligible_for_random_encounter(state, leader, plan, HOME, check_escort=False) is False


def test_is_leader_eligible_for_random_encounter_excludes_army_commanders():
    state = _base_state()
    leader = LeaderState(1, kingdom_id=1, name="Commander", location=HOME)
    state.add_leader(leader)
    state.add_army(
        ArmyState(1, kingdom_id=1, army_type=ArmyType.PHALANX, quality=Quality.AVERAGE, location=HOME, commanded_by=1)
    )
    plan = _plan(PlanPhase("P0", ActionCode.LMOVE, 0))
    assert is_leader_eligible_for_random_encounter(state, leader, plan, HOME, check_escort=False) is False


def test_is_leader_eligible_for_random_encounter_true_for_an_ordinary_hero():
    state = _base_state()
    leader = LeaderState(1, kingdom_id=1, name="Hero", location=HOME)
    state.add_leader(leader)
    plan = _plan(PlanPhase("P0", ActionCode.LMOVE, 0))
    assert is_leader_eligible_for_random_encounter(state, leader, plan, HOME, check_escort=True) is True
