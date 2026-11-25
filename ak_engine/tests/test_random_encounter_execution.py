from __future__ import annotations

import random
from unittest.mock import ANY, patch

from ak_engine.models.advanced_ability import AdvancedAbility
from ak_engine.models.alignment import Alignment
from ak_engine.models.enums import ActionCode, Ability, Maneuver
from ak_engine.models.game_state import GameState, KingdomState, LeaderState, ProvinceState
from ak_engine.models.leader import Leader
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.monster import MONSTER_COMBAT_STATS, MONSTER_MAGIC_ABILITIES, Monster
from ak_engine.models.monster_encounter_plan import roll_monster_encounter_plan
from ak_engine.models.plan import ActionPlan, PlanPhase, PlanSegment
from ak_engine.models.race import Race
from ak_engine.turn.challenge_execution import ChallengeCombatOutcome
from ak_engine.turn.encounter import FireArrowShot, MeleeSwing
from ak_engine.turn.random_encounter_execution import (
    RandomEncounterResult,
    dispatch_random_encounter_after_phase,
    monster_combatant,
    WANDERING_MAGIC_PLAN_CHANCE,
    _without_magic_most_of_the_time,
    resolve_random_encounter,
    wandering_monster_leader,
    wandering_monster_treasure,
)
from ak_engine.turn.search_decode import SearchTactic

from _helpers import ScriptedRandom

HOME = HexCoord(5, 4)


def _base_state(turn_number: int = 2) -> GameState:
    state = GameState()
    state.turn_number = turn_number
    state.add_kingdom(KingdomState(1, "Homeland", Race.HUMAN, Alignment.GOOD, HOME))
    state.add_kingdom(KingdomState(2, "Otherland", Race.HUMAN, Alignment.GOOD, HexCoord(6, 4)))
    state.add_province(ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    return state


def _plan(*phases: PlanPhase) -> ActionPlan:
    segment = PlanSegment(plan_start=0, plan_end=0, sp=(), phases={f"P{i}": p for i, p in enumerate(phases)})
    return ActionPlan(leader_id=1, segments=[segment])


def _hero(leader_id: int = 1, kingdom_id: int | None = 1, **kwargs) -> LeaderState:
    return LeaderState(leader_id, kingdom_id=kingdom_id, name="Hero", location=HOME, **kwargs)


# -- monster_combatant --


def test_monster_combatant_hp_within_species_range():
    rng = random.Random(1)
    combatant = monster_combatant(Monster.GIANT, rng)
    lo, hi = MONSTER_COMBAT_STATS[Monster.GIANT].hit_points_range
    assert lo <= combatant.hit_points <= hi
    assert combatant.melee_skill == MONSTER_COMBAT_STATS[Monster.GIANT].melee_skill


def test_monster_combatant_carries_the_temper_of_its_species():
    # The disassembled `mtemper` gives a monster the Temper Table's melee effects (Furia, Slancio, Schivare).
    from ak_engine.models.monster import MONSTER_RUNTIME_PROFILE

    for monster in MONSTER_COMBAT_STATS:
        assert monster_combatant(monster, random.Random(1)).temper is MONSTER_RUNTIME_PROFILE[monster].temper
    assert monster_combatant(Monster.GRYPHON, random.Random(1)).temper.name == "BERSERK"


def test_monster_combatant_troll_regenerates():
    combatant = monster_combatant(Monster.TROLL, random.Random(1))
    assert combatant.regenerates_hp == 1


def test_monster_combatant_non_troll_does_not_regenerate():
    combatant = monster_combatant(Monster.GIANT, random.Random(1))
    assert combatant.regenerates_hp == 0


def test_monster_combatant_falls_back_to_fire_arrow_damage_when_no_missile_damage():
    # Swordsman has missile_damage=None in MONSTER_COMBAT_STATS.
    assert MONSTER_COMBAT_STATS[Monster.SWORDSMAN].missile_damage is None
    combatant = monster_combatant(Monster.SWORDSMAN, random.Random(1))
    assert combatant.missile_damage_range == (1, 6)


def test_monster_combatant_undead_flag_for_spiritwrack_species():
    combatant = monster_combatant(Monster.GHOST, random.Random(1))
    assert combatant.is_undead_or_anti_holy is True


# -- resolve_random_encounter --


def test_resolve_random_encounter_gate_closed_returns_none():
    state = _base_state(turn_number=1)
    leader = _hero()
    state.add_leader(leader)
    plan = _plan(PlanPhase("P0", ActionCode.LMOVE, 0))
    result = resolve_random_encounter(state, 1, HOME, plan, check_escort=True, rng=ScriptedRandom([]))
    assert result is None


def test_resolve_random_encounter_missing_leader_returns_none():
    state = _base_state()
    plan = _plan(PlanPhase("P0", ActionCode.LMOVE, 0))
    result = resolve_random_encounter(state, 99, HOME, plan, check_escort=True, rng=ScriptedRandom([]))
    assert result is None


def test_resolve_random_encounter_ineligible_leader_returns_none():
    state = _base_state()
    leader = _hero(is_king=True)
    state.add_leader(leader)
    plan = _plan(PlanPhase("P0", ActionCode.LMOVE, 0))
    result = resolve_random_encounter(state, 1, HOME, plan, check_escort=True, rng=ScriptedRandom([]))
    assert result is None


def test_resolve_random_encounter_failed_terrain_roll():
    state = _base_state()
    leader = _hero()
    state.add_leader(leader)
    plan = _plan(PlanPhase("P0", ActionCode.LMOVE, 0))
    # renc[PLAINS]=10 -- a roll of 0.99 (99%) fails.
    result = resolve_random_encounter(state, 1, HOME, plan, check_escort=True, rng=ScriptedRandom([0.99]))
    assert result == RandomEncounterResult(1, HOME, terrain_roll_succeeded=False)


def test_resolve_random_encounter_patrol_evades_via_diplomacy():
    state = _base_state()
    leader = _hero()
    state.add_leader(leader)
    plan = _plan(PlanPhase("P0", ActionCode.LMOVE, 0))

    with patch("ak_engine.turn.random_encounter_execution.terrain_roll", return_value=True), patch(
        "ak_engine.turn.random_encounter_execution.select_random_monster", return_value=Monster.GIANT
    ), patch("ak_engine.turn.random_encounter_execution.is_patrol_framing", return_value=True), patch(
        "ak_engine.turn.random_encounter_execution.patrol_evades_via_diplomacy", return_value=True
    ) as mock_evade, patch(
        "ak_engine.turn.random_encounter_execution.resolve_challenge_combat"
    ) as mock_combat:
        result = resolve_random_encounter(state, 1, HOME, plan, check_escort=True, rng=ScriptedRandom([]))

    mock_evade.assert_called_once_with(state, 1, 1, ANY)
    mock_combat.assert_not_called()
    assert result.terrain_roll_succeeded is True
    assert result.is_patrol is True
    assert result.evaded_via_diplomacy is True
    assert result.combat_occurred is False


def test_resolve_random_encounter_wandering_monster_never_checks_diplomacy():
    state = _base_state()
    leader = _hero()
    state.add_leader(leader)
    plan = _plan(PlanPhase("P0", ActionCode.LMOVE, 0))

    with patch("ak_engine.turn.random_encounter_execution.terrain_roll", return_value=True), patch(
        "ak_engine.turn.random_encounter_execution.select_random_monster", return_value=Monster.TITAN
    ), patch("ak_engine.turn.random_encounter_execution.is_patrol_framing", return_value=False), patch(
        "ak_engine.turn.random_encounter_execution.patrol_evades_via_diplomacy"
    ) as mock_evade, patch(
        "ak_engine.turn.random_encounter_execution.resolve_challenge_combat",
        return_value=ChallengeCombatOutcome(winner=None),
    ):
        result = resolve_random_encounter(state, 1, HOME, plan, check_escort=True, rng=ScriptedRandom([0.5, 0.5, 0.5, 0.5, 0.5]))

    mock_evade.assert_not_called()
    assert result.is_patrol is False
    assert result.combat_occurred is True


def test_resolve_random_encounter_sense_danger_talent_evades():
    state = _base_state()
    leader = _hero(
        advanced_abilities={AdvancedAbility.SENSE_DANGER_TALENT},
        special_encounter_plan=(SearchTactic(Maneuver.FLEE),),
    )
    state.add_leader(leader)
    plan = _plan(PlanPhase("P0", ActionCode.LMOVE, 0))

    with patch("ak_engine.turn.random_encounter_execution.terrain_roll", return_value=True), patch(
        "ak_engine.turn.random_encounter_execution.select_random_monster", return_value=Monster.TITAN
    ), patch("ak_engine.turn.random_encounter_execution.is_patrol_framing", return_value=False), patch(
        "ak_engine.turn.random_encounter_execution.resolve_challenge_combat"
    ) as mock_combat:
        result = resolve_random_encounter(state, 1, HOME, plan, check_escort=True, rng=ScriptedRandom([]))

    mock_combat.assert_not_called()
    assert result.evaded_via_sense_danger is True
    assert result.combat_occurred is False


def test_resolve_random_encounter_sense_danger_talent_requires_flee_first():
    state = _base_state()
    leader = _hero(
        advanced_abilities={AdvancedAbility.SENSE_DANGER_TALENT},
        special_encounter_plan=(SearchTactic(Maneuver.MELEE),),
    )
    state.add_leader(leader)
    plan = _plan(PlanPhase("P0", ActionCode.LMOVE, 0))

    with patch("ak_engine.turn.random_encounter_execution.terrain_roll", return_value=True), patch(
        "ak_engine.turn.random_encounter_execution.select_random_monster", return_value=Monster.TITAN
    ), patch("ak_engine.turn.random_encounter_execution.is_patrol_framing", return_value=False), patch(
        "ak_engine.turn.random_encounter_execution.resolve_challenge_combat",
        return_value=ChallengeCombatOutcome(winner=None),
    ):
        result = resolve_random_encounter(state, 1, HOME, plan, check_escort=True, rng=ScriptedRandom([0.5, 0.5, 0.5, 0.5, 0.5]))

    assert result.evaded_via_sense_danger is False
    assert result.combat_occurred is True


def test_resolve_random_encounter_leader_wins_no_death_no_loot():
    state = _base_state()
    leader = _hero()
    state.add_leader(leader)
    plan = _plan(PlanPhase("P0", ActionCode.LMOVE, 0))

    with patch("ak_engine.turn.random_encounter_execution.terrain_roll", return_value=True), patch(
        "ak_engine.turn.random_encounter_execution.select_random_monster", return_value=Monster.TITAN
    ), patch("ak_engine.turn.random_encounter_execution.is_patrol_framing", return_value=False), patch(
        "ak_engine.turn.random_encounter_execution.resolve_challenge_combat",
        return_value=ChallengeCombatOutcome(winner="a"),
    ):
        result = resolve_random_encounter(state, 1, HOME, plan, check_escort=True, rng=ScriptedRandom([0.5, 0.5, 0.5, 0.5, 0.5]))

    assert result.winner == "a"
    assert result.leader_died is False
    assert 1 in state.leaders


def test_resolve_random_encounter_monster_wins_removes_leader():
    state = _base_state()
    leader = _hero()
    state.add_leader(leader)
    plan = _plan(PlanPhase("P0", ActionCode.LMOVE, 0))

    with patch("ak_engine.turn.random_encounter_execution.terrain_roll", return_value=True), patch(
        "ak_engine.turn.random_encounter_execution.select_random_monster", return_value=Monster.TITAN
    ), patch("ak_engine.turn.random_encounter_execution.is_patrol_framing", return_value=False), patch(
        "ak_engine.turn.random_encounter_execution.resolve_challenge_combat",
        return_value=ChallengeCombatOutcome(winner="b"),
    ):
        result = resolve_random_encounter(state, 1, HOME, plan, check_escort=True, rng=ScriptedRandom([0.5, 0.5, 0.5, 0.5, 0.5]))

    assert result.winner == "b"
    assert result.leader_died is True
    assert 1 not in state.leaders
    assert 1 in state.dead_leaders


# -- the wandering monster's own plan --


def _run_with_stubbed_combat(monster, outcome, *, rng=None, state=None):
    if state is None:
        state = _base_state()
        state.add_leader(_hero())
    plan = _plan(PlanPhase("P0", ActionCode.LMOVE, 0))
    with patch("ak_engine.turn.random_encounter_execution.terrain_roll", return_value=True), patch(
        "ak_engine.turn.random_encounter_execution.select_random_monster", return_value=monster
    ), patch("ak_engine.turn.random_encounter_execution.is_patrol_framing", return_value=False), patch(
        "ak_engine.turn.random_encounter_execution.resolve_challenge_combat", return_value=outcome
    ) as mock_combat:
        result = resolve_random_encounter(
            state, 1, HOME, plan, check_escort=True, rng=rng or ScriptedRandom([0.5] * 8)
        )
    return result, mock_combat


def test_wandering_monster_leader_carries_the_species_talents_temper_and_alignment():
    nec_mage = wandering_monster_leader(Monster.NEC_MAGE, HOME)
    assert nec_mage.leader_id < 0 and nec_mage.kingdom_id is None
    for ability, level in MONSTER_MAGIC_ABILITIES[Monster.NEC_MAGE].items():
        assert nec_mage.skills.pair_for_ability(ability)[0] == level
    assert nec_mage.temper is not None
    assert wandering_monster_leader(Monster.LICH, HOME).alignment is Alignment.UNDEAD
    # a species with several alignments gets one rolled from the stream it is given
    giant_alignments = {wandering_monster_leader(Monster.GIANT, HOME, random.Random(seed)).alignment for seed in range(40)}
    assert giant_alignments == {Alignment.NEUTRAL, Alignment.PAGAN}


def test_a_wandering_monster_fights_with_its_own_plan_and_retreats_when_wounded():
    _result, mock_combat = _run_with_stubbed_combat(Monster.NEC_MAGE, ChallengeCombatOutcome(winner=None))
    kwargs = mock_combat.call_args.kwargs
    assert kwargs["target_retreats_when_wounded"] is True
    assert kwargs["target_monster"] is Monster.NEC_MAGE  # the hero's spells follow the species rules
    assert kwargs["target_tactics"]
    assert mock_combat.call_args.args[3].leader_id < 0  # the monster's stand-in leader


def test_a_wandering_monster_with_a_missile_plan_opens_with_missiles():
    _result, mock_combat = _run_with_stubbed_combat(Monster.ARCHER, ChallengeCombatOutcome(winner=None))
    assert mock_combat.call_args.kwargs["target_opens_with_missiles"] is True
    _result, mock_combat = _run_with_stubbed_combat(Monster.SWORDSMAN, ChallengeCombatOutcome(winner=None))
    assert mock_combat.call_args.kwargs["target_opens_with_missiles"] is False


def test_a_fleeing_wandering_monster_is_reported_and_the_hero_lives():
    result, _mock = _run_with_stubbed_combat(Monster.TROLL, ChallengeCombatOutcome(winner="a", target_fled=True))
    assert result.monster_fled is True
    assert result.leader_died is False


def test_the_wandering_monster_plan_never_draws_from_the_encounter_dice():
    seen = []
    real = roll_monster_encounter_plan

    def _spy(monster, rng, **kwargs):
        seen.append((rng, kwargs.get("variety_rng")))
        return real(monster, rng, **kwargs)

    encounter_rng = ScriptedRandom([0.5] * 8)
    with patch("ak_engine.turn.random_encounter_execution.roll_monster_encounter_plan", side_effect=_spy):
        _run_with_stubbed_combat(Monster.WHITE_MAGE, ChallengeCombatOutcome(winner=None), rng=encounter_rng)

    assert seen and seen[0][0] is not encounter_rng and seen[0][1] is not encounter_rng


def test_a_wandering_monsters_spells_are_mostly_left_out_of_its_plan():
    plan = (SearchTactic(Maneuver.CAST, 1), SearchTactic(Maneuver.CAST, 2), SearchTactic(Maneuver.MELEE))
    kept = sum(_without_magic_most_of_the_time(plan, random.Random(seed)) == plan for seed in range(1000))
    assert abs(kept / 1000 - WANDERING_MAGIC_PLAN_CHANCE) < 0.05
    stripped = _without_magic_most_of_the_time(plan, ScriptedRandom([0.99]))
    assert stripped == (SearchTactic(Maneuver.MELEE),)


def test_a_plan_without_spells_or_made_only_of_spells_degrades_gracefully():
    melee_only = (SearchTactic(Maneuver.MELEE),)
    assert _without_magic_most_of_the_time(melee_only, ScriptedRandom([])) == melee_only  # no roll consumed
    assert _without_magic_most_of_the_time(None, ScriptedRandom([])) is None
    only_spells = (SearchTactic(Maneuver.CAST, 1),)
    assert _without_magic_most_of_the_time(only_spells, ScriptedRandom([0.99])) is None  # plain fight


def test_wandering_monster_treasure_is_two_to_ten_gold_with_ten_very_rare():
    rolls = [wandering_monster_treasure(random.Random(seed)) for seed in range(5000)]
    assert min(rolls) == 2 and max(rolls) == 10
    assert 0 < rolls.count(10) < 5000 * 0.05
    assert {2, 3, 4, 5, 6, 7, 8, 9} <= set(rolls)


def test_a_defeated_wandering_monster_pays_its_purse_and_counts_for_the_lord_high_defender():
    state = _base_state()
    hero = _hero()
    state.add_leader(hero)
    treasury_before = state.kingdoms[1].treasury
    with patch("ak_engine.turn.random_encounter_execution.monster_combatant") as mock_combatant:
        mock_combatant.return_value = monster_combatant(Monster.TITAN, random.Random(1))
        starting_hp = mock_combatant.return_value.hit_points
        result, _mock = _run_with_stubbed_combat(Monster.TITAN, ChallengeCombatOutcome(winner="a"), state=state)

    assert 2 <= result.gold_found <= 10
    assert state.kingdoms[1].treasury == treasury_before + result.gold_found
    assert hero.merit_tally.monster_hp_defeated == starting_hp


def test_a_monster_that_ran_away_pays_its_purse_but_earns_no_defender_points():
    state = _base_state()
    hero = _hero()
    state.add_leader(hero)
    result, _mock = _run_with_stubbed_combat(
        Monster.TROLL, ChallengeCombatOutcome(winner="a", target_fled=True), state=state
    )
    assert result.gold_found > 0
    assert hero.merit_tally.monster_hp_defeated == 0


def test_a_hero_who_loses_gets_no_purse():
    state = _base_state()
    state.add_leader(_hero())
    lost, _mock = _run_with_stubbed_combat(Monster.TITAN, ChallengeCombatOutcome(winner="b"), state=state)
    assert lost.gold_found == 0 and state.kingdoms[1].treasury == 0


def test_a_patrol_is_not_a_monster_no_plan_no_purse_no_defender_points():
    state = _base_state()
    hero = _hero()
    state.add_leader(hero)
    plan = _plan(PlanPhase("P0", ActionCode.LMOVE, 0))
    with patch("ak_engine.turn.random_encounter_execution.terrain_roll", return_value=True), patch(
        "ak_engine.turn.random_encounter_execution.select_random_monster", return_value=Monster.NEC_MAGE
    ), patch("ak_engine.turn.random_encounter_execution.is_patrol_framing", return_value=True), patch(
        "ak_engine.turn.random_encounter_execution.patrol_evades_via_diplomacy", return_value=False
    ), patch(
        "ak_engine.turn.random_encounter_execution.resolve_challenge_combat",
        return_value=ChallengeCombatOutcome(winner="a"),
    ) as mock_combat:
        result = resolve_random_encounter(state, 1, HOME, plan, check_escort=True, rng=ScriptedRandom([0.5] * 8))

    assert mock_combat.call_args.args[3] is None
    assert mock_combat.call_args.kwargs["target_tactics"] is None
    assert mock_combat.call_args.kwargs["target_retreats_when_wounded"] is False
    assert mock_combat.call_args.kwargs["target_monster"] is None
    assert result.gold_found == 0
    assert hero.merit_tally.monster_hp_defeated == 0


def test_resolve_random_encounter_credits_melee_experience_on_a_landed_hit():
    state = _base_state()
    leader = _hero()
    state.add_leader(leader)
    plan = _plan(PlanPhase("P0", ActionCode.LMOVE, 0))

    with patch("ak_engine.turn.random_encounter_execution.terrain_roll", return_value=True), patch(
        "ak_engine.turn.random_encounter_execution.select_random_monster", return_value=Monster.TITAN
    ), patch("ak_engine.turn.random_encounter_execution.is_patrol_framing", return_value=False), patch(
        "ak_engine.turn.random_encounter_execution.resolve_challenge_combat",
        return_value=ChallengeCombatOutcome(
            winner=None, melee_swings=(MeleeSwing(attacker="a", hit=True, damage=3),)
        ),
    ), patch("ak_engine.turn.random_encounter_execution.add_experience") as mock_add_experience:
        resolve_random_encounter(state, 1, HOME, plan, check_escort=True, rng=ScriptedRandom([0.5, 0.5, 0.5, 0.5, 0.5]))

    mock_add_experience.assert_any_call(leader, Ability.MELEE, 10, ANY)


def test_resolve_random_encounter_credits_archery_experience_on_a_landed_shot():
    state = _base_state()
    leader = _hero()
    state.add_leader(leader)
    plan = _plan(PlanPhase("P0", ActionCode.LMOVE, 0))

    with patch("ak_engine.turn.random_encounter_execution.terrain_roll", return_value=True), patch(
        "ak_engine.turn.random_encounter_execution.select_random_monster", return_value=Monster.TITAN
    ), patch("ak_engine.turn.random_encounter_execution.is_patrol_framing", return_value=False), patch(
        "ak_engine.turn.random_encounter_execution.resolve_challenge_combat",
        return_value=ChallengeCombatOutcome(
            winner=None, fire_arrow_shots=(FireArrowShot(shooter="a", hit=True, damage=3),)
        ),
    ), patch("ak_engine.turn.random_encounter_execution.add_experience") as mock_add_experience:
        resolve_random_encounter(state, 1, HOME, plan, check_escort=True, rng=ScriptedRandom([0.5, 0.5, 0.5, 0.5, 0.5]))

    mock_add_experience.assert_any_call(leader, Ability.ARCHERY, 10, ANY)


def test_resolve_random_encounter_unowned_province_patrol_falls_back_to_neutral():
    state = _base_state()
    state.provinces[HOME].owner_kingdom_id = None
    leader = _hero()
    state.add_leader(leader)
    plan = _plan(PlanPhase("P0", ActionCode.LMOVE, 0))

    with patch("ak_engine.turn.random_encounter_execution.terrain_roll", return_value=True), patch(
        "ak_engine.turn.random_encounter_execution.select_random_monster", return_value=Monster.GIANT
    ), patch("ak_engine.turn.random_encounter_execution.is_patrol_framing", return_value=True), patch(
        "ak_engine.turn.random_encounter_execution.patrol_evades_via_diplomacy"
    ) as mock_evade, patch(
        "ak_engine.turn.random_encounter_execution.resolve_challenge_combat",
        return_value=ChallengeCombatOutcome(winner=None),
    ):
        result = resolve_random_encounter(state, 1, HOME, plan, check_escort=True, rng=ScriptedRandom([0.5, 0.5, 0.5, 0.5, 0.5]))

    # No real owner -- diplomacy is never even checked, combat proceeds.
    mock_evade.assert_not_called()
    assert result.evaded_via_diplomacy is False
    assert result.combat_occurred is True


# -- dispatch_random_encounter_after_phase --


def test_dispatch_random_encounter_after_phase_ignores_non_triggering_actions():
    state = _base_state()
    leader_state = _hero()
    state.add_leader(leader_state)
    leader = Leader(1, "Hero", _plan(PlanPhase("P0", ActionCode.RECRUIT, 0)))
    phase = PlanPhase("P0", ActionCode.RECRUIT, 0)

    with patch("ak_engine.turn.random_encounter_execution.resolve_random_encounter") as mock_resolve:
        result = dispatch_random_encounter_after_phase(state, leader, phase, ScriptedRandom([]))

    mock_resolve.assert_not_called()
    assert result is None


def test_dispatch_random_encounter_after_phase_returns_none_for_a_dead_leader():
    state = _base_state()
    leader = Leader(1, "Hero", _plan(PlanPhase("P0", ActionCode.LMOVE, 0)))
    phase = PlanPhase("P0", ActionCode.LMOVE, 0)

    result = dispatch_random_encounter_after_phase(state, leader, phase, ScriptedRandom([]))

    assert result is None


def test_dispatch_random_encounter_after_phase_checks_escort_for_move_pursue_trail():
    state = _base_state()
    leader_state = _hero()
    state.add_leader(leader_state)
    leader = Leader(1, "Hero", _plan(PlanPhase("P0", ActionCode.LMOVE, 0)))

    for action in (ActionCode.LMOVE, ActionCode.PURSUE, ActionCode.TRAIL):
        phase = PlanPhase("P0", action, 0)
        with patch("ak_engine.turn.random_encounter_execution.resolve_random_encounter") as mock_resolve:
            dispatch_random_encounter_after_phase(state, leader, phase, ScriptedRandom([]))
        mock_resolve.assert_called_once_with(state, 1, HOME, leader.plan, check_escort=True, rng=ANY)


def test_dispatch_random_encounter_after_phase_does_not_check_escort_for_explore_search():
    state = _base_state()
    leader_state = _hero()
    state.add_leader(leader_state)
    leader = Leader(1, "Hero", _plan(PlanPhase("P0", ActionCode.EXPLORE, 0)))

    for action in (ActionCode.EXPLORE, ActionCode.SEARCH):
        phase = PlanPhase("P0", action, 0)
        with patch("ak_engine.turn.random_encounter_execution.resolve_random_encounter") as mock_resolve:
            dispatch_random_encounter_after_phase(state, leader, phase, ScriptedRandom([]))
        mock_resolve.assert_called_once_with(state, 1, HOME, leader.plan, check_escort=False, rng=ANY)
