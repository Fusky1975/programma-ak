from __future__ import annotations

import random
from unittest.mock import patch

import pytest

from ak_engine.models.alignment import Alignment
from ak_engine.models.enums import Ability, Maneuver, Spell
from ak_engine.models.feature import Feature, FeatureType
from ak_engine.models.game_state import GameState, LeaderState
from ak_engine.models.kingdom import SkillTable
from ak_engine.models.map import HexCoord
from ak_engine.models.monster import MONSTER_COMBAT_STATS, Monster, MonsterSpeed
from ak_engine.models.valhalla import VALHALLA_VISITOR_LEADER_ID
from ak_engine.turn.encounter import FIRE_ARROW_DAMAGE_RANGE, EncounterCombatResult, FireArrowShot
from ak_engine.turn.search_decode import SearchRequest, SearchTactic
from ak_engine.turn.search_execution import (
    FLEE_CHANCE,
    TROLL_REGENERATION_PER_COMBAT_ROUND,
    SearchExecutionResult,
    execute_search,
)

from _helpers import ScriptedRandom

LOCATION = HexCoord(3, 9)
LEADER_ID = 1


def _state_with_leader(*, skills: SkillTable | None = None) -> GameState:
    state = GameState()
    state.add_leader(LeaderState(LEADER_ID, 1, "Searcher", LOCATION, skills=skills))
    return state


def _melee_request(feature_id: int) -> SearchRequest:
    return SearchRequest(feature_id=feature_id, unconfirmed_extra0=0, tactics=[SearchTactic(maneuver=Maneuver.MELEE)])


def test_execute_search_leader_not_found():
    state = GameState()
    result = execute_search(state, LEADER_ID, _melee_request(1))
    assert result == SearchExecutionResult(accepted=False, reason="leader not found")


def test_execute_search_feature_not_found():
    state = _state_with_leader()
    result = execute_search(state, LEADER_ID, _melee_request(99))
    assert result.accepted is False
    assert result.reason == "feature not found"


def test_execute_search_already_looted_feature_rejected():
    state = _state_with_leader()
    state.add_feature(
        Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE, looted=True)
    )
    result = execute_search(state, LEADER_ID, _melee_request(1))
    assert result.accepted is False
    assert result.reason == "feature already looted"


def test_execute_search_no_guardian_recorded_rejected():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=None))
    result = execute_search(state, LEADER_ID, _melee_request(1))
    assert result.accepted is False
    assert result.reason == "feature has no guardian recorded"


def test_execute_search_not_co_located_rejected():
    state = _state_with_leader()
    elsewhere = HexCoord(9, 9)
    state.add_feature(Feature(feature_id=1, coord=elsewhere, kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE))
    result = execute_search(state, LEADER_ID, _melee_request(1))
    assert result.accepted is False
    assert result.reason == "not co-located with feature"


def test_execute_search_unsourced_guardian_stats_reports_unresolved():
    # Monster.NOMONSTER is the "no monster" sentinel, not a real species --
    # it has no MONSTER_COMBAT_STATS entry by design (Phase 154 gave all
    # 60 real species combat stats, so NOMONSTER is the one remaining
    # guaranteed-unsourced case).
    state = _state_with_leader()
    state.add_feature(
        Feature(feature_id=1, coord=LOCATION, kind=FeatureType.PET_FOREST, guardian_monster=Monster.NOMONSTER)
    )
    result = execute_search(state, LEADER_ID, _melee_request(1))
    assert result.accepted is True
    assert result.combat_resolved is False
    assert "no combat stats" in result.reason


def test_execute_search_previously_unsourced_species_now_resolves():
    # Monster.ROC had no MONSTER_STATS entry before Phase 154; it now has
    # a MONSTER_COMBAT_STATS entry (project-original data) and resolves
    # real combat like any other species.
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.PET_FOREST, guardian_monster=Monster.ROC))

    result = execute_search(state, LEADER_ID, _melee_request(1), random.Random(1))

    assert result.accepted is True
    assert result.combat_resolved is True
    assert result.reason is None


def test_execute_search_no_melee_tactic_reports_unresolved():
    state = _state_with_leader()
    state.add_feature(
        Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE)
    )
    scout_only = SearchRequest(feature_id=1, unconfirmed_extra0=0, tactics=[SearchTactic(maneuver=Maneuver.SCOUT)])

    result = execute_search(state, LEADER_ID, scout_only)

    assert result.accepted is True
    assert result.combat_resolved is False
    assert "no Melee or Fire Arrow tactic" in result.reason


def test_execute_search_leader_wins_marks_feature_looted():
    # A leader with high Melee skill (level 9) always acts first against
    # a Gargoyle (melee_skill=1); scripted so the leader always hits and
    # the Gargoyle (15 hp) always misses.
    raw = [0] * 30
    raw[Ability.MELEE.value * 2] = 9
    raw[Ability.MELEE.value * 2 + 1] = 9
    state = _state_with_leader(skills=SkillTable(raw_values=raw))
    feature = Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE)
    state.add_feature(feature)
    block = [0.1, 0.5, 0.9]  # leader hits (chance+damage), Gargoyle misses
    rng = ScriptedRandom(block * 20)

    result = execute_search(state, LEADER_ID, _melee_request(1), rng)

    assert result.accepted is True
    assert result.combat_resolved is True
    assert result.winner == "leader"
    assert result.feature_looted is True
    assert feature.looted is True
    assert LEADER_ID in state.leaders


def test_execute_search_leader_loses_is_removed_from_state():
    # A leaderless-skill searcher (melee_skill=0) faces a Troll
    # (melee_skill=1): the Troll always acts first and always hits;
    # the leader (10 hp) always misses.
    state = _state_with_leader()
    feature = Feature(feature_id=1, coord=LOCATION, kind=FeatureType.CAVE, guardian_monster=Monster.TROLL)
    state.add_feature(feature)
    block = [0.1, 0.5, 0.9]  # Troll hits (chance+damage), leader misses
    rng = ScriptedRandom(block * 20)

    result = execute_search(state, LEADER_ID, _melee_request(1), rng)

    assert result.accepted is True
    assert result.combat_resolved is True
    assert result.winner == "monster"
    assert result.leader_killed is True
    assert LEADER_ID not in state.leaders
    assert LEADER_ID in state.dead_leaders
    assert feature.looted is False


# -- Phase 155: Troll regeneration wiring --


def test_execute_search_sets_troll_regeneration_on_the_monster_combatant():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.CAVE, guardian_monster=Monster.TROLL))

    with patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_resolve:
        mock_resolve.return_value = EncounterCombatResult(winner=None, rounds=1)
        execute_search(state, LEADER_ID, _melee_request(1), random.Random(0))

    monster_combatant = mock_resolve.call_args[0][1]
    assert monster_combatant.regenerates_hp == TROLL_REGENERATION_PER_COMBAT_ROUND


def test_execute_search_non_troll_guardian_has_no_regeneration():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.CAVE, guardian_monster=Monster.GARGOYLE))

    with patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_resolve:
        mock_resolve.return_value = EncounterCombatResult(winner=None, rounds=1)
        execute_search(state, LEADER_ID, _melee_request(1), random.Random(0))

    monster_combatant = mock_resolve.call_args[0][1]
    assert monster_combatant.regenerates_hp == 0


# -- Phase 169: Flee (rulebook [5.6]) --


def test_flee_chance_matches_the_rulebooks_three_speed_tiers():
    assert FLEE_CHANCE == {
        MonsterSpeed.FAST: 0.20,
        MonsterSpeed.MEDIUM: 0.50,
        MonsterSpeed.SLOW: 0.80,
    }
    # Confirms the tiers line up with real species, not just the enum.
    assert MONSTER_COMBAT_STATS[Monster.GRYPHON].speed is MonsterSpeed.FAST
    assert MONSTER_COMBAT_STATS[Monster.GARGOYLE].speed is MonsterSpeed.MEDIUM
    assert MONSTER_COMBAT_STATS[Monster.GOLEM].speed is MonsterSpeed.SLOW


def test_execute_search_flee_tactic_success_ends_search_without_combat():
    # Gryphon is Fast (20% flee chance) -- 0.1 < 0.20 succeeds.
    state = _state_with_leader()
    feature = Feature(feature_id=1, coord=LOCATION, kind=FeatureType.CAVE, guardian_monster=Monster.GRYPHON)
    state.add_feature(feature)
    request = SearchRequest(
        feature_id=1, unconfirmed_extra0=0, tactics=[SearchTactic(maneuver=Maneuver.FLEE), SearchTactic(maneuver=Maneuver.MELEE)]
    )

    # Padding: the monster's own hit_points draw (rng.randint()) now runs
    # before the tactic walk even starts, consuming an unknown number of
    # randoms from the front of the queue -- every value here is 0.1 (< the
    # 20% flee chance), so whichever one lands on the flee roll still succeeds.
    result = execute_search(state, LEADER_ID, request, ScriptedRandom([0.1] * 20))

    assert result.accepted is True
    assert result.combat_resolved is False
    assert result.fled is True
    assert result.winner is None
    assert feature.looted is False
    assert LEADER_ID in state.leaders


def test_execute_search_flee_tactic_failure_falls_through_to_melee():
    # Gryphon is Fast (20% flee chance) -- 0.99 >= 0.20 fails, so the plan's
    # Melee tactic still runs afterward exactly as if Flee weren't there.
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.CAVE, guardian_monster=Monster.GRYPHON))
    request = SearchRequest(
        feature_id=1, unconfirmed_extra0=0, tactics=[SearchTactic(maneuver=Maneuver.FLEE), SearchTactic(maneuver=Maneuver.MELEE)]
    )

    with patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_resolve:
        mock_resolve.return_value = EncounterCombatResult(winner=None, rounds=1)
        # Padding beyond the flee roll: rng.randint() for the monster's hit
        # points draws further from the same scripted queue.
        result = execute_search(state, LEADER_ID, request, ScriptedRandom([0.99] + [0.5] * 10))

    assert mock_resolve.called
    assert result.accepted is True
    assert result.combat_resolved is True
    assert result.fled is False


def test_execute_search_no_flee_tactic_never_rolls_for_it():
    # A Melee-only plan against a Fast monster must not flee even though
    # the very first scripted roll (0.1) would satisfy the 20% chance --
    # confirms the roll is only consumed when Flee is actually in the plan.
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.CAVE, guardian_monster=Monster.GRYPHON))

    with patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_resolve:
        mock_resolve.return_value = EncounterCombatResult(winner=None, rounds=1)
        result = execute_search(state, LEADER_ID, _melee_request(1), ScriptedRandom([0.1] + [0.5] * 10))

    assert mock_resolve.called
    assert result.fled is False


# -- Phase 170: Fire Arrow (rulebook [5.2]) --


def _shoot_request(feature_id: int, *maneuvers: Maneuver) -> SearchRequest:
    tactics = [SearchTactic(maneuver=m) for m in maneuvers] or [SearchTactic(maneuver=Maneuver.SHOOT)]
    return SearchRequest(feature_id=feature_id, unconfirmed_extra0=0, tactics=tactics)


def test_execute_search_shoot_tactic_leader_wins_marks_feature_looted():
    state = _state_with_leader()
    feature = Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE)
    state.add_feature(feature)

    with patch("ak_engine.turn.search_execution.resolve_fire_arrow_duel") as mock_resolve:
        mock_resolve.return_value = EncounterCombatResult(winner="a", rounds=1)
        result = execute_search(state, LEADER_ID, _shoot_request(1, Maneuver.SHOOT), random.Random(0))

    assert mock_resolve.called
    assert result.accepted is True
    assert result.combat_resolved is True
    assert result.winner == "leader"
    assert result.feature_looted is True
    assert feature.looted is True
    assert LEADER_ID in state.leaders


def test_execute_search_shoot_tactic_monster_wins_removes_leader():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))

    with patch("ak_engine.turn.search_execution.resolve_fire_arrow_duel") as mock_resolve:
        mock_resolve.return_value = EncounterCombatResult(winner="b", rounds=1)
        result = execute_search(state, LEADER_ID, _shoot_request(1, Maneuver.SHOOT), random.Random(0))

    assert mock_resolve.called
    assert result.accepted is True
    assert result.combat_resolved is True
    assert result.winner == "monster"
    assert result.leader_killed is True
    assert LEADER_ID not in state.leaders
    assert LEADER_ID in state.dead_leaders


def test_execute_search_shoot_tactic_exhausted_falls_through_to_melee():
    # Mirrors Regolamento AK.txt [11.3]'s own worked example ("FI, FL.
    # Significato: Tirare con l'Arco, poi fuggire") -- Fire Arrow runs
    # first; when it exhausts its free attacks with nobody dead, the
    # plan's next tactic (here Melee, not Flee) still runs.
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE))
    request = _shoot_request(1, Maneuver.SHOOT, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.resolve_fire_arrow_duel") as mock_shoot, patch(
        "ak_engine.turn.search_execution.resolve_melee_duel"
    ) as mock_melee:
        mock_shoot.return_value = EncounterCombatResult(winner=None, rounds=1)
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert mock_shoot.called
    assert mock_melee.called
    assert result.combat_resolved is True
    assert result.winner == "leader"


def test_execute_search_shoot_then_flee_tries_shoot_first():
    # Same real example as above, but this time Flee genuinely is the
    # plan's second tactic -- confirms Fire Arrow is attempted before
    # Flee, not the other way around (Phase 169's original bug).
    state = _state_with_leader()
    feature = Feature(feature_id=1, coord=LOCATION, kind=FeatureType.CAVE, guardian_monster=Monster.GRYPHON)
    state.add_feature(feature)
    request = _shoot_request(1, Maneuver.SHOOT, Maneuver.FLEE)

    with patch("ak_engine.turn.search_execution.resolve_fire_arrow_duel") as mock_shoot:
        mock_shoot.return_value = EncounterCombatResult(winner=None, rounds=1)
        # Gryphon is Fast (20% flee chance); every padding value is 0.1 so
        # whichever one lands on the flee roll still succeeds.
        result = execute_search(state, LEADER_ID, request, ScriptedRandom([0.1] * 20))

    assert mock_shoot.called
    assert result.combat_resolved is False
    assert result.fled is True


def test_execute_search_unwired_tactic_is_skipped_not_aborting():
    # "ST, CA-FI, ME, SC" ([11.3]) mixes Steal and Cast (both unwired)
    # with Melee -- an unwired tactic must be silently skipped, not treat
    # the whole plan as unresolvable.
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE))
    request = _shoot_request(1, Maneuver.STEAL, Maneuver.CAST, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert mock_melee.called
    assert result.combat_resolved is True
    assert result.winner == "leader"


def test_execute_search_monster_combatant_carries_missile_skill_and_damage():
    # Archer: missile_skill=3, missile_damage=(3, 9) -- both must reach
    # the monster's own Combatant, not the character-default (1-6).
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))

    with patch("ak_engine.turn.search_execution.resolve_fire_arrow_duel") as mock_resolve:
        mock_resolve.return_value = EncounterCombatResult(winner=None, rounds=1)
        execute_search(state, LEADER_ID, _shoot_request(1, Maneuver.SHOOT), random.Random(0))

    monster_combatant = mock_resolve.call_args[0][1]
    stats = MONSTER_COMBAT_STATS[Monster.ARCHER]
    assert monster_combatant.archery_skill == stats.missile_skill == 3
    assert monster_combatant.missile_damage_range == stats.missile_damage == (3, 9)


def test_execute_search_monster_missile_damage_range_defaults_when_unarmed():
    # Gargoyle has missile_skill=0 and missile_damage=None (no ranged
    # attack at all) -- the Combatant must fall back to the character
    # rule rather than crash on an unpacking of None.
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE))

    with patch("ak_engine.turn.search_execution.resolve_fire_arrow_duel") as mock_resolve:
        mock_resolve.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_search(state, LEADER_ID, _shoot_request(1, Maneuver.SHOOT), random.Random(0))

    monster_combatant = mock_resolve.call_args[0][1]
    assert monster_combatant.archery_skill == 0
    assert monster_combatant.missile_damage_range == FIRE_ARROW_DAMAGE_RANGE


# -- Phase 175: carrying the Fire Arrow shot log + guardian species out to the report layer --


def test_execute_search_shoot_tactic_carries_shots_and_guardian_monster_on_win():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE))
    shots = (FireArrowShot(shooter="a", hit=True, damage=4),)

    with patch("ak_engine.turn.search_execution.resolve_fire_arrow_duel") as mock_resolve:
        mock_resolve.return_value = EncounterCombatResult(winner="a", rounds=1, shots=shots)
        result = execute_search(state, LEADER_ID, _shoot_request(1, Maneuver.SHOOT), random.Random(0))

    assert result.fire_arrow_shots == shots
    assert result.guardian_monster is Monster.GARGOYLE


def test_execute_search_shoot_exhausted_then_melee_still_carries_the_earlier_shots():
    # The Fire Arrow phase's own shots must survive onto whichever later
    # tactic actually ends the fight, since a shot fired earlier in the
    # plan is still worth narrating even though it didn't decide the
    # outcome (turn/search_execution.py's own Phase 175 addendum).
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE))
    request = _shoot_request(1, Maneuver.SHOOT, Maneuver.MELEE)
    shots = (FireArrowShot(shooter="a", hit=False, damage=0), FireArrowShot(shooter="b", hit=False, damage=0))

    with patch("ak_engine.turn.search_execution.resolve_fire_arrow_duel") as mock_shoot, patch(
        "ak_engine.turn.search_execution.resolve_melee_duel"
    ) as mock_melee:
        mock_shoot.return_value = EncounterCombatResult(winner=None, rounds=1, shots=shots)
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert result.winner == "leader"
    assert result.fire_arrow_shots == shots
    assert result.guardian_monster is Monster.GARGOYLE


def test_execute_search_melee_only_has_empty_fire_arrow_shots_but_still_sets_guardian():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE))

    with patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        result = execute_search(state, LEADER_ID, _melee_request(1), random.Random(0))

    assert result.fire_arrow_shots == ()
    assert result.guardian_monster is Monster.GARGOYLE


def test_execute_search_shoot_exhausted_with_no_further_tactic_defaults_to_melee():
    # Phase 178: a plan whose tactic list runs out without a winner no
    # longer reports "inconclusive" -- it now defaults to Melee until
    # someone dies, per the user's own confirmed default behavior.
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE))
    shots = (FireArrowShot(shooter="a", hit=False, damage=0),)

    with patch("ak_engine.turn.search_execution.resolve_fire_arrow_duel") as mock_shoot, patch(
        "ak_engine.turn.search_execution.resolve_melee_duel"
    ) as mock_melee:
        mock_shoot.return_value = EncounterCombatResult(winner=None, rounds=1, shots=shots)
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        result = execute_search(state, LEADER_ID, _shoot_request(1, Maneuver.SHOOT), random.Random(0))

    assert mock_melee.called
    assert result.combat_resolved is True
    assert result.winner == "leader"
    assert result.fire_arrow_shots == shots
    assert result.guardian_monster is Monster.GARGOYLE


# -- Phase 178: the guardian's own Special Encounter Plan --


def test_execute_search_monster_wanting_shoot_fires_even_when_the_leaders_plan_never_does():
    # Titan's own rolled plan always opens with Cast+Shoot -- the leader's
    # own plan here is Melee-only, but Fire Arrow must still resolve
    # first because the guardian's own plan wants it. Titan's own CAST
    # tactics are real as of Phase 209 (real MONSTER_MAGIC_ABILITIES skill
    # levels), so the generic cast-success roll is forced to fail here to
    # isolate this test's own Fire-Arrow-ordering concern from the CAST
    # dispatch behavior covered separately in the Phase 209 CAST tests.
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.TITAN))

    with patch("ak_engine.turn.search_execution.resolve_fire_arrow_duel") as mock_shoot, patch(
        "ak_engine.turn.search_execution.resolve_melee_duel"
    ) as mock_melee, patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=False):
        mock_shoot.return_value = EncounterCombatResult(winner=None, rounds=1)
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        result = execute_search(state, LEADER_ID, _melee_request(1), random.Random(0))

    assert mock_shoot.called
    assert mock_melee.called
    assert result.winner == "leader"


def test_execute_search_monster_not_wanting_shoot_never_triggers_fire_arrow():
    # Gargoyle's own plan is "ME fino alla fine" only -- no Fire Arrow
    # phase should happen even though the guardian's own plan is rolled.
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE))

    with patch("ak_engine.turn.search_execution.resolve_fire_arrow_duel") as mock_shoot, patch(
        "ak_engine.turn.search_execution.resolve_melee_duel"
    ) as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_search(state, LEADER_ID, _melee_request(1), random.Random(0))

    assert not mock_shoot.called
    assert mock_melee.called


def test_execute_search_monster_wanting_shoot_does_not_double_resolve_when_leader_plan_also_shoots():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.TITAN))
    request = _shoot_request(1, Maneuver.SHOOT, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.resolve_fire_arrow_duel") as mock_shoot, patch(
        "ak_engine.turn.search_execution.resolve_melee_duel"
    ) as mock_melee, patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=False):
        mock_shoot.return_value = EncounterCombatResult(winner=None, rounds=1)
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_search(state, LEADER_ID, request, random.Random(0))

    assert mock_shoot.call_count == 1
    assert mock_melee.call_count == 1


def test_execute_search_rolls_the_guardians_plan_with_the_leaders_own_undead_alignment():
    state = GameState()
    state.add_leader(LeaderState(LEADER_ID, 1, "Searcher", LOCATION, alignment=Alignment.UNDEAD))
    state.add_feature(
        Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.NEC_MAGE)
    )

    with patch("ak_engine.turn.search_execution.roll_monster_encounter_plan") as mock_roll, patch(
        "ak_engine.turn.search_execution.resolve_melee_duel"
    ) as mock_melee:
        mock_roll.return_value = (SearchTactic(maneuver=Maneuver.MELEE),)
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_search(state, LEADER_ID, _melee_request(1), random.Random(0))

    mock_roll.assert_called_once()
    assert mock_roll.call_args.kwargs["attacker_is_undead"] is True


def test_execute_search_non_undead_leader_rolls_the_guardians_plan_without_the_undead_override():
    state = _state_with_leader()  # LeaderState default alignment is None
    state.add_feature(
        Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.NEC_MAGE)
    )

    with patch("ak_engine.turn.search_execution.roll_monster_encounter_plan") as mock_roll, patch(
        "ak_engine.turn.search_execution.resolve_melee_duel"
    ) as mock_melee:
        mock_roll.return_value = (SearchTactic(maneuver=Maneuver.MELEE),)
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_search(state, LEADER_ID, _melee_request(1), random.Random(0))

    assert mock_roll.call_args.kwargs["attacker_is_undead"] is False


# -- Phase 209: CAST orchestration engine (8 non-channeled Personal-Combat spells + Charm) --


def _cast_request(feature_id: int, spell: Spell, *following: Maneuver) -> SearchRequest:
    tactics = [SearchTactic(maneuver=Maneuver.CAST, sub_object=spell.value)]
    tactics += [SearchTactic(maneuver=m) for m in following]
    return SearchRequest(feature_id=feature_id, unconfirmed_extra0=0, tactics=tactics)


def _skilled_leader(ability: Ability, level: int, **kwargs) -> LeaderState:
    raw = [0] * 30
    raw[ability.value * 2] = level
    raw[ability.value * 2 + 1] = level
    return LeaderState(LEADER_ID, 1, "Searcher", LOCATION, skills=SkillTable(raw_values=raw), **kwargs)


def test_execute_search_cast_charm_success_makes_the_caster_flee():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE))
    request = _cast_request(1, Spell.CHARM, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.resolve_melee_duel"
    ) as mock_melee:
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert result.fled is True
    assert result.combat_resolved is False
    assert not mock_melee.called


def test_execute_search_cast_charm_failure_falls_through_to_melee():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE))
    request = _cast_request(1, Spell.CHARM, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=False), patch(
        "ak_engine.turn.search_execution.resolve_melee_duel"
    ) as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert mock_melee.called
    assert result.winner == "leader"


def test_execute_search_cast_charm_undead_caster_uses_necromancy_skill_level():
    # Charm's own Phase 183 addendum: an Undead caster's Charm draws on
    # Necromancy instead of Psychic -- replicated for monster casters via
    # species classification, for leader casters via `LeaderState.alignment`.
    leader = _skilled_leader(Ability.NECROMANCY, 5, alignment=Alignment.UNDEAD)
    state = GameState()
    state.add_leader(leader)
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE))
    request = _cast_request(1, Spell.CHARM, Maneuver.MELEE)

    with patch(
        "ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=False
    ) as mock_cast_roll, patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_search(state, LEADER_ID, request, random.Random(0))

    mock_cast_roll.assert_called_once()
    assert mock_cast_roll.call_args[0][0] == 5  # the Necromancy level, not the (0) Psychic level


def test_execute_search_cast_holy_symbol_reduces_casters_own_hit_chance_taken():
    leader = _skilled_leader(Ability.WHITE, 2)
    state = GameState()
    state.add_leader(leader)
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _cast_request(1, Spell.HOLY_SYMBOL, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.resolve_melee_duel"
    ) as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_search(state, LEADER_ID, request, random.Random(0))

    leader_combatant = mock_melee.call_args[0][0]
    assert leader_combatant.defensive_hit_multiplier < 1.0


def test_execute_search_cast_holy_symbol_bonus_damage_kills_undead_target_instantly():
    leader = _skilled_leader(Ability.WHITE, 2)
    state = GameState()
    state.add_leader(leader)
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.VAMPIRE))
    request = _cast_request(1, Spell.HOLY_SYMBOL, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.roll_holy_symbol_undead_damage", return_value=999
    ), patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_melee:
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert result.combat_resolved is True
    assert result.winner == "leader"
    assert result.feature_looted is True
    assert not mock_melee.called


def test_execute_search_cast_spiritwrack_debuffs_the_target():
    leader = _skilled_leader(Ability.WHITE, 2)  # exact reduction of 1, no rng consumed
    state = GameState()
    state.add_leader(leader)
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _cast_request(1, Spell.SPIRITWRACK, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.resolve_melee_duel"
    ) as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_search(state, LEADER_ID, request, random.Random(0))

    monster_combatant = mock_melee.call_args[0][1]
    assert monster_combatant.melee_damage_dealt_reduction == 1
    assert monster_combatant.blocked_from_cast_and_archery is True


def test_execute_search_cast_psychic_blast_bonus_swing_can_end_the_encounter():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _cast_request(1, Spell.PSYCHIC_BLAST)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.roll_psychic_blast_stun_rounds", return_value=2
    ), patch("ak_engine.turn.search_execution.roll_melee_attack", return_value=999), patch(
        "ak_engine.turn.search_execution.resolve_melee_duel"
    ) as mock_melee, patch("ak_engine.turn.search_execution.resolve_fire_arrow_duel") as mock_shoot:
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert result.combat_resolved is True
    assert result.winner == "leader"
    assert result.feature_looted is True
    assert not mock_melee.called
    assert not mock_shoot.called


def test_execute_search_cast_telekinetic_storm_kills_the_target():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _cast_request(1, Spell.TELEK_STORM)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.roll_telekinetic_storm_victim_damage", return_value=999
    ), patch("ak_engine.turn.search_execution.roll_telekinetic_storm_caster_damage", return_value=0):
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert result.winner == "leader"
    assert result.feature_looted is True


def test_execute_search_cast_telekinetic_storm_can_kill_the_caster():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _cast_request(1, Spell.TELEK_STORM)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.roll_telekinetic_storm_victim_damage", return_value=0
    ), patch("ak_engine.turn.search_execution.roll_telekinetic_storm_caster_damage", return_value=999):
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert result.winner == "monster"
    assert result.leader_killed is True


def test_execute_search_cast_invisibility_halves_casters_own_hit_chance_taken():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _cast_request(1, Spell.INVISIBILITY, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.resolve_melee_duel"
    ) as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_search(state, LEADER_ID, request, random.Random(0))

    leader_combatant = mock_melee.call_args[0][0]
    assert leader_combatant.defensive_hit_multiplier == 0.5


def test_execute_search_cast_fireball_kills_the_target():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _cast_request(1, Spell.FIREBALL)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.roll_fireball_damage", return_value=999
    ):
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert result.winner == "leader"


def test_execute_search_cast_fireball_marks_submarine_targets_immune():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.MERMAID))
    request = _cast_request(1, Spell.FIREBALL, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.roll_fireball_damage", return_value=0
    ) as mock_fireball, patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_search(state, LEADER_ID, request, random.Random(0))

    assert mock_fireball.call_args.kwargs["target_is_immune"] is True


def test_execute_search_cast_ice_suspend_immune_species_has_no_effect():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.SPECTRE))
    request = _cast_request(1, Spell.ICE_SUSPEND, Maneuver.MELEE)

    # SPECTRE's own real rolled plan may include real CAST tactics of its
    # own (Phase 210 wired Hand of Death/Mirror-Image); mocked empty here
    # to isolate this test's own "Ice Suspend has no effect" concern from
    # the guardian's own CAST dispatch, covered separately.
    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.roll_monster_encounter_plan", return_value=()
    ), patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_search(state, LEADER_ID, request, random.Random(0))

    assert mock_melee.called
    leader_combatant = mock_melee.call_args[0][0]
    assert leader_combatant.bonus_unanswered_attacks == 0


def test_execute_search_cast_ice_suspend_frozen_branch_wins_instantly():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _cast_request(1, Spell.ICE_SUSPEND)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.ice_suspension_is_frozen", return_value=True
    ):
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert result.winner == "leader"


def test_execute_search_cast_ice_suspend_flying_branch_crash_damage_can_kill():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.VAMPIRE))
    request = _cast_request(1, Spell.ICE_SUSPEND)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.ice_suspension_is_frozen", return_value=False
    ), patch("ak_engine.turn.search_execution.roll_ice_suspension_flying_crash_damage", return_value=999), patch(
        "ak_engine.turn.search_execution.roll_ice_suspension_flying_bonus_rounds", return_value=0
    ):
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert result.winner == "leader"


def test_execute_search_cast_ice_suspend_slowed_branch_grants_bonus_attacks():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _cast_request(1, Spell.ICE_SUSPEND)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.ice_suspension_is_frozen", return_value=False
    ), patch("ak_engine.turn.search_execution.ice_suspension_slowed_bonus_rounds", return_value=2), patch(
        "ak_engine.turn.search_execution.roll_melee_attack", return_value=999
    ):
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert result.winner == "leader"


def test_execute_search_cast_control_undead_ineligible_target_consumes_no_roll():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _cast_request(1, Spell.CONTROL_UNDEAD, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast") as mock_roll, patch(
        "ak_engine.turn.search_execution.resolve_melee_duel"
    ) as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_search(state, LEADER_ID, request, random.Random(0))

    assert not mock_roll.called
    assert mock_melee.called


def test_execute_search_cast_control_undead_success_wins_instantly():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.VAMPIRE))
    request = _cast_request(1, Spell.CONTROL_UNDEAD)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True):
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert result.winner == "leader"
    assert result.feature_looted is True


def test_execute_search_cast_control_undead_failure_applies_rage_buff():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.VAMPIRE))
    request = _cast_request(1, Spell.CONTROL_UNDEAD, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=False), patch(
        "ak_engine.turn.search_execution.control_undead_failure_new_hit_points", return_value=999
    ), patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_search(state, LEADER_ID, request, random.Random(0))

    monster_combatant = mock_melee.call_args[0][1]
    assert monster_combatant.hit_points == 999


def test_execute_search_guardians_own_cast_resolves_before_the_first_real_combat_phase():
    # The guardian's own CAST tactics are injected right before the first
    # real combat phase (same point already established for
    # monster_wants_shoot, Phase 178), independent of the leader's own
    # plan -- here the leader's plan never casts anything at all.
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ELE_MAGE))
    request = _melee_request(1)

    with patch("ak_engine.turn.search_execution.roll_monster_encounter_plan") as mock_roll, patch(
        "ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True
    ), patch("ak_engine.turn.search_execution.roll_fireball_damage", return_value=999), patch(
        "ak_engine.turn.search_execution.resolve_melee_duel"
    ) as mock_melee:
        mock_roll.return_value = (SearchTactic(maneuver=Maneuver.CAST, sub_object=Spell.FIREBALL.value),)
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert result.winner == "monster"
    assert result.leader_killed is True
    assert not mock_melee.called


def test_execute_search_blocked_from_cast_and_archery_skips_the_guardians_own_later_cast():
    # The leader's own Spiritwrack lands on the guardian first (leader-CAST
    # resolves when the walk reaches it, before any guardian-CAST
    # injection); once the guardian is blocked, its own later Fireball
    # tactic (from its own rolled plan) is skipped outright, never
    # reaching the generic cast-success roll.
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _cast_request(1, Spell.SPIRITWRACK, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.roll_monster_encounter_plan") as mock_roll, patch(
        "ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True
    ) as mock_cast_roll, patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_melee:
        mock_roll.return_value = (SearchTactic(maneuver=Maneuver.CAST, sub_object=Spell.FIREBALL.value),)
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_search(state, LEADER_ID, request, random.Random(0))

    assert mock_cast_roll.call_count == 1
    assert mock_melee.called


# -- Phase 210: Hand of Death + Mirror-Image Phantasm CAST dispatch --


def test_execute_search_cast_hand_of_death_threads_the_immune_flag():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.VAMPIRE))
    request = _cast_request(1, Spell.HAND_OF_DEATH, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.resolve_hand_of_death_channel"
    ) as mock_channel, patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_melee:
        mock_channel.return_value = EncounterCombatResult(winner=None, rounds=0)
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_search(state, LEADER_ID, request, random.Random(0))

    # Vampire is Undead (SPIRITWRACK_UNDEAD_MONSTERS), part of
    # HAND_OF_DEATH_IMMUNE_MONSTERS.
    assert mock_channel.call_args.kwargs["target_is_immune"] is True


def test_execute_search_cast_hand_of_death_caster_wins_instantly():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _cast_request(1, Spell.HAND_OF_DEATH)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.resolve_hand_of_death_channel"
    ) as mock_channel:
        mock_channel.return_value = EncounterCombatResult(winner="a", rounds=3)
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert mock_channel.call_args.kwargs["target_is_immune"] is False
    assert result.winner == "leader"
    assert result.feature_looted is True


def test_execute_search_cast_hand_of_death_broken_channel_falls_through_to_melee():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _cast_request(1, Spell.HAND_OF_DEATH, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.resolve_hand_of_death_channel"
    ) as mock_channel, patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_melee:
        mock_channel.return_value = EncounterCombatResult(winner=None, rounds=2)
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert mock_melee.called
    assert result.winner == "leader"


def test_execute_search_cast_hand_of_death_rolls_the_necromancy_skill_level():
    leader = _skilled_leader(Ability.NECROMANCY, 4)
    state = GameState()
    state.add_leader(leader)
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _cast_request(1, Spell.HAND_OF_DEATH)

    with patch(
        "ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True
    ) as mock_cast_roll, patch("ak_engine.turn.search_execution.resolve_hand_of_death_channel") as mock_channel:
        mock_channel.return_value = EncounterCombatResult(winner=None, rounds=1)
        execute_search(state, LEADER_ID, request, random.Random(0))

    assert mock_cast_roll.call_args[0][0] == 4


def test_execute_search_cast_mirror_image_monster_target_uses_the_sourced_tier():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.SPHINX))
    request = _cast_request(1, Spell.MIRROR_IMAGE, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.resolve_mirror_image_duel"
    ) as mock_duel, patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_melee:
        mock_duel.return_value = EncounterCombatResult(winner=None, rounds=1)
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_search(state, LEADER_ID, request, random.Random(0))

    from ak_engine.turn.encounter import MirrorImageIntelligenceTier

    assert mock_duel.call_args[0][2] is MirrorImageIntelligenceTier.HIGH_HUMAN


def test_execute_search_cast_mirror_image_leader_target_uses_high_human_plus_the_sage_illusion_bonus():
    # The guardian's own rolled plan casts Mirror-Image at the leader --
    # opponent_tier is always High Human for a King/Hero (confirmed by the
    # user), plus a further bonus from the leader's own Sage/Illusion
    # skill levels.
    leader = _skilled_leader(Ability.SAGE, 3)  # 3*2% = 6% bonus, 0% Illusion
    state = GameState()
    state.add_leader(leader)
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _melee_request(1)

    with patch("ak_engine.turn.search_execution.roll_monster_encounter_plan") as mock_roll, patch(
        "ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True
    ), patch("ak_engine.turn.search_execution.resolve_mirror_image_duel") as mock_duel, patch(
        "ak_engine.turn.search_execution.resolve_melee_duel"
    ) as mock_melee:
        mock_roll.return_value = (SearchTactic(maneuver=Maneuver.CAST, sub_object=Spell.MIRROR_IMAGE.value),)
        mock_duel.return_value = EncounterCombatResult(winner=None, rounds=1)
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_search(state, LEADER_ID, request, random.Random(0))

    from ak_engine.turn.encounter import MirrorImageIntelligenceTier

    assert mock_duel.call_args[0][2] is MirrorImageIntelligenceTier.HIGH_HUMAN
    assert mock_duel.call_args.kwargs["opponent_disbelief_bonus"] == pytest.approx(0.06)


def test_execute_search_cast_mirror_image_caster_wins_instantly():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _cast_request(1, Spell.MIRROR_IMAGE)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.resolve_mirror_image_duel"
    ) as mock_duel:
        mock_duel.return_value = EncounterCombatResult(winner="a", rounds=2)
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert result.winner == "leader"
    assert result.feature_looted is True


def test_execute_search_cast_mirror_image_caster_is_slain_by_own_illusion():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _cast_request(1, Spell.MIRROR_IMAGE)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.resolve_mirror_image_duel"
    ) as mock_duel:
        mock_duel.return_value = EncounterCombatResult(winner="b", rounds=2)
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert result.winner == "monster"
    assert result.leader_killed is True


def test_execute_search_cast_illusory_hero_no_valhalla_visitor_has_no_effect():
    leader = _skilled_leader(Ability.ILLUSION, 5)
    state = GameState()
    state.add_leader(leader)
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _cast_request(1, Spell.ILLUS_HERO, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.resolve_illusory_hero_duel"
    ) as mock_duel, patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_search(state, LEADER_ID, request, random.Random(0))

    assert not mock_duel.called
    assert mock_melee.called


def test_execute_search_cast_illusory_hero_level_gate_blocks_low_illusion_skill():
    leader = _skilled_leader(Ability.ILLUSION, 4)
    state = GameState()
    state.add_leader(leader)
    state.add_leader(LeaderState(VALHALLA_VISITOR_LEADER_ID, None, "Hero", LOCATION))
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _cast_request(1, Spell.ILLUS_HERO, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast") as mock_cast_roll, patch(
        "ak_engine.turn.search_execution.resolve_melee_duel"
    ) as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_search(state, LEADER_ID, request, random.Random(0))

    assert not mock_cast_roll.called
    assert mock_melee.called


def test_execute_search_cast_illusory_hero_monster_target_uses_the_sourced_tier():
    leader = _skilled_leader(Ability.ILLUSION, 5)
    state = GameState()
    state.add_leader(leader)
    state.add_leader(LeaderState(VALHALLA_VISITOR_LEADER_ID, None, "Hero", LOCATION))
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.SPHINX))
    request = _cast_request(1, Spell.ILLUS_HERO, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.resolve_illusory_hero_duel"
    ) as mock_duel, patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_melee:
        mock_duel.return_value = EncounterCombatResult(winner=None, rounds=1)
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_search(state, LEADER_ID, request, random.Random(0))

    from ak_engine.turn.encounter import MirrorImageIntelligenceTier

    assert mock_duel.call_args[0][2].melee_skill == 0  # the hero-illusion Combatant
    assert mock_duel.call_args[0][3] is MirrorImageIntelligenceTier.HIGH_HUMAN
    assert mock_duel.call_args.kwargs["opponent_disbelief_bonus"] == 0.0


def test_execute_search_cast_illusory_hero_leader_target_uses_high_human_plus_bonus():
    leader = _skilled_leader(Ability.SAGE, 3)  # 3*2% = 6% bonus, 0% Illusion
    state = GameState()
    state.add_leader(leader)
    state.add_leader(LeaderState(VALHALLA_VISITOR_LEADER_ID, None, "Hero", LOCATION))
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _melee_request(1)

    with patch("ak_engine.turn.search_execution.roll_monster_encounter_plan") as mock_roll, patch.dict(
        "ak_engine.turn.search_execution.MONSTER_MAGIC_ABILITIES", {Monster.ARCHER: {Ability.ILLUSION: 5}}
    ), patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.resolve_illusory_hero_duel"
    ) as mock_duel, patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_melee:
        mock_roll.return_value = (SearchTactic(maneuver=Maneuver.CAST, sub_object=Spell.ILLUS_HERO.value),)
        mock_duel.return_value = EncounterCombatResult(winner=None, rounds=1)
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_search(state, LEADER_ID, request, random.Random(0))

    from ak_engine.turn.encounter import MirrorImageIntelligenceTier

    assert mock_duel.call_args[0][3] is MirrorImageIntelligenceTier.HIGH_HUMAN
    assert mock_duel.call_args.kwargs["opponent_disbelief_bonus"] == pytest.approx(0.06)


def test_execute_search_cast_illusory_hero_caster_wins_instantly():
    leader = _skilled_leader(Ability.ILLUSION, 5)
    state = GameState()
    state.add_leader(leader)
    state.add_leader(LeaderState(VALHALLA_VISITOR_LEADER_ID, None, "Hero", LOCATION))
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _cast_request(1, Spell.ILLUS_HERO)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.resolve_illusory_hero_duel"
    ) as mock_duel:
        mock_duel.return_value = EncounterCombatResult(winner="a", rounds=2)
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert result.winner == "leader"
    assert result.feature_looted is True


def test_execute_search_cast_illusory_hero_caster_is_slain_by_own_illusion():
    leader = _skilled_leader(Ability.ILLUSION, 5)
    state = GameState()
    state.add_leader(leader)
    state.add_leader(LeaderState(VALHALLA_VISITOR_LEADER_ID, None, "Hero", LOCATION))
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _cast_request(1, Spell.ILLUS_HERO)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.resolve_illusory_hero_duel"
    ) as mock_duel:
        mock_duel.return_value = EncounterCombatResult(winner="b", rounds=2)
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert result.winner == "monster"
    assert result.leader_killed is True


def test_execute_search_cast_illusory_hero_turns_on_master_when_alignments_are_hostile():
    leader = _skilled_leader(Ability.ILLUSION, 5, alignment=Alignment.GOOD)
    state = GameState()
    state.add_leader(leader)
    state.add_leader(LeaderState(VALHALLA_VISITOR_LEADER_ID, None, "Hero", LOCATION, alignment=Alignment.EVIL))
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _cast_request(1, Spell.ILLUS_HERO)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.resolve_illusory_hero_duel"
    ) as mock_duel:
        mock_duel.return_value = EncounterCombatResult(winner=None, rounds=1)
        execute_search(state, LEADER_ID, request, random.Random(0))

    assert mock_duel.call_args.kwargs["turns_on_master"] is True


def test_execute_search_cast_illusory_hero_turns_on_master_false_when_alignments_unset():
    leader = _skilled_leader(Ability.ILLUSION, 5)
    state = GameState()
    state.add_leader(leader)
    state.add_leader(LeaderState(VALHALLA_VISITOR_LEADER_ID, None, "Hero", LOCATION))
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _cast_request(1, Spell.ILLUS_HERO)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.resolve_illusory_hero_duel"
    ) as mock_duel:
        mock_duel.return_value = EncounterCombatResult(winner=None, rounds=1)
        execute_search(state, LEADER_ID, request, random.Random(0))

    assert mock_duel.call_args.kwargs["turns_on_master"] is False
