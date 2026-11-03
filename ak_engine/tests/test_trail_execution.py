from __future__ import annotations

from unittest.mock import patch

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.enums import Ability
from ak_engine.models.game_state import ArmyState, GameState, KingdomState, LeaderState, ProvinceState
from ak_engine.models.kingdom import SkillTable
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.office import Office
from ak_engine.models.race import Race
from ak_engine.models.temper import Temper
from ak_engine.models.treasure import Treasure
from ak_engine.parser.gw_world import DiplomaticRelation
from ak_engine.turn.combat import Quality
from ak_engine.turn.movement import NORMAL_MAP_BOUNDS, MapBounds, hex_distance
from ak_engine.turn.office_holder import OfficeHolder
from ak_engine.turn.trail_decode import TrailRequest
from ak_engine.turn.trail_execution import KingIntelligence, TrailExecutionResult, advance_trail, execute_trail

from _helpers import ScriptedRandom

FIELD = HexCoord(1, 1)
FAR_AWAY = HexCoord(20, 10)


def _skills_with(ability: Ability, skill: int, aptitude: int) -> SkillTable:
    raw = [0] * 30
    raw[ability.value * 2] = skill
    raw[ability.value * 2 + 1] = aptitude
    return SkillTable(raw)


def _request(target_id: int) -> TrailRequest:
    return TrailRequest(target_character_id=target_id, unconfirmed_extra0=0)


def _base_state() -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Chasia", Race.HUMAN, Alignment.GOOD, FIELD))
    state.add_kingdom(KingdomState(2, "Fleeland", Race.HUMAN, Alignment.GOOD, FIELD))
    return state


def test_execute_trail_reports_not_found_when_trailer_missing():
    state = _base_state()
    state.add_leader(LeaderState(2, kingdom_id=2, name="Target", location=FIELD))

    result = execute_trail(state, 1, _request(2))

    assert result.spied_on is False
    assert result.reason == "trailer or target not found"


def test_execute_trail_reports_not_found_when_target_missing():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Trailer", location=FIELD))

    result = execute_trail(state, 1, _request(2))

    assert result.spied_on is False
    assert result.reason == "trailer or target not found"


def test_execute_trail_rejected_when_trailer_leads_an_army():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Trailer", location=FIELD))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Target", location=FIELD))
    state.add_army(ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, FIELD, commanded_by=1))

    result = execute_trail(state, 1, _request(2), rng=ScriptedRandom([]))

    assert result.spied_on is False
    assert result.reason == "a character leading an army may not be ordered to Trail"


def test_execute_trail_allowed_when_only_target_leads_an_army():
    # Unlike Pursue, Trail has no "both must match" rule -- only the
    # trailer is restricted from leading an army ([3.17]).
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Trailer", location=FIELD))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Target", location=FIELD))
    state.add_army(ArmyState(201, 2, ArmyType.GARRISON, Quality.GREEN, FIELD, commanded_by=2))

    result = execute_trail(state, 1, _request(2), rng=ScriptedRandom([0.0, 0.5, 0.5]))

    assert result.spied_on is True


def test_execute_trail_same_kingdom_target_is_guaranteed_to_be_found():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Trailer", location=FIELD))
    state.add_leader(LeaderState(2, kingdom_id=1, name="Target", location=FAR_AWAY))

    result = execute_trail(state, 1, _request(2), rng=ScriptedRandom([0.99, 0.5, 0.5]))

    assert result.spied_on is True


def test_execute_trail_same_province_target_is_guaranteed_to_be_found():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Trailer", location=FIELD))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Target", location=FIELD))

    result = execute_trail(state, 1, _request(2), rng=ScriptedRandom([0.0, 0.5, 0.5]))

    assert result.spied_on is True


def test_execute_trail_fails_when_roll_is_too_high():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Trailer", location=FIELD))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Target", location=FAR_AWAY))

    result = execute_trail(state, 1, _request(2), rng=ScriptedRandom([0.99]))

    assert result.spied_on is False
    assert result.reason == "did not find the target this phase"


def test_execute_trail_uses_trailers_real_spy_skill():
    state = _base_state()
    state.add_leader(
        LeaderState(1, kingdom_id=1, name="Trailer", location=FIELD, skills=_skills_with(Ability.SPY, 4, 9))
    )
    state.add_leader(LeaderState(2, kingdom_id=2, name="Target", location=HexCoord(3, 1)))  # distance 2

    # Level-4 Spy gives 250% base, /2 distance = 125% -> capped at 100%.
    result = execute_trail(state, 1, _request(2), rng=ScriptedRandom([0.99, 0.5, 0.5]))

    assert result.spied_on is True


# -- Phase 159 (temper/treasures_owned/armies_led) + Phase 164 (alignment)
# + Phase 165 (race) + Phase 166 (king_intelligence) intelligence payload ----


def test_execute_trail_success_reports_targets_temper():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Trailer", location=FIELD))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Target", location=FIELD, temper=Temper.BRAVE))

    result = execute_trail(state, 1, _request(2), rng=ScriptedRandom([0.0, 0.5, 0.5]))

    assert result.temper is Temper.BRAVE


def test_execute_trail_success_reports_none_temper_when_not_recorded():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Trailer", location=FIELD))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Target", location=FIELD))

    result = execute_trail(state, 1, _request(2), rng=ScriptedRandom([0.0, 0.5, 0.5]))

    assert result.temper is None


def test_execute_trail_success_reports_targets_alignment():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Trailer", location=FIELD))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Target", location=FIELD, alignment=Alignment.PAGAN))

    result = execute_trail(state, 1, _request(2), rng=ScriptedRandom([0.0, 0.5, 0.5]))

    assert result.alignment is Alignment.PAGAN


def test_execute_trail_success_reports_none_alignment_when_not_recorded():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Trailer", location=FIELD))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Target", location=FIELD))

    result = execute_trail(state, 1, _request(2), rng=ScriptedRandom([0.0, 0.5, 0.5]))

    assert result.alignment is None


def test_execute_trail_success_reports_targets_race_via_kingdom():
    state = _base_state()
    state.kingdoms[2].race = Race.ELVEN
    state.add_leader(LeaderState(1, kingdom_id=1, name="Trailer", location=FIELD))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Target", location=FIELD))

    result = execute_trail(state, 1, _request(2), rng=ScriptedRandom([0.0, 0.5, 0.5]))

    assert result.race is Race.ELVEN


def test_execute_trail_success_reports_none_race_for_an_independent_hero():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Trailer", location=FIELD))
    state.add_leader(LeaderState(2, kingdom_id=None, name="Wandering Hero", location=FIELD))

    result = execute_trail(state, 1, _request(2), rng=ScriptedRandom([0.0, 0.5, 0.5]))

    assert result.race is None


def test_execute_trail_success_reports_king_intelligence_for_a_king_target():
    state = _base_state()
    state.add_kingdom(KingdomState(3, "Ally", Race.HUMAN, Alignment.GOOD, FIELD, treasury=42))
    state.add_kingdom(KingdomState(4, "Foe", Race.HUMAN, Alignment.EVIL, FIELD, treasury=13))
    state.kingdoms[2].treasury = 77
    state.allied_kingdoms.add(frozenset({2, 3}))
    state.diplomatic_relations[frozenset({2, 4})] = DiplomaticRelation.ENEMY
    state.add_province(ProvinceState(FIELD, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2))
    state.add_province(ProvinceState(FAR_AWAY, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_leader(LeaderState(1, kingdom_id=1, name="Trailer", location=FIELD))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Target King", location=FIELD, is_king=True))

    result = execute_trail(state, 1, _request(2), rng=ScriptedRandom([0.0, 0.5, 0.5]))

    assert result.king_intelligence == KingIntelligence(
        treasury=77,
        allied_kingdom_ids=(3,),
        enemy_kingdom_ids=(4,),
        controlled_provinces=(FIELD,),
    )


def test_execute_trail_success_reports_none_king_intelligence_for_a_hero_target():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Trailer", location=FIELD))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Target Hero", location=FIELD, is_king=False))

    result = execute_trail(state, 1, _request(2), rng=ScriptedRandom([0.0, 0.5, 0.5]))

    assert result.king_intelligence is None


def test_execute_trail_success_reports_targets_treasures_owned():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Trailer", location=FIELD))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Target", location=FIELD))
    state.add_item(Treasure.ABILITY_TACTICAL, owner_leader_id=2)
    state.add_item(Treasure.ABILITY_TACTICAL, owner_leader_id=1)  # trailer's own, not reported

    result = execute_trail(state, 1, _request(2), rng=ScriptedRandom([0.0, 0.5, 0.5]))

    assert len(result.treasures_owned) == 1
    assert result.treasures_owned[0].owner_leader_id == 2


def test_execute_trail_success_reports_targets_armies_led():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Trailer", location=FIELD))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Target", location=FIELD))
    army = ArmyState(201, 2, ArmyType.GARRISON, Quality.GREEN, FIELD, commanded_by=2)
    state.add_army(army)

    result = execute_trail(state, 1, _request(2), rng=ScriptedRandom([0.0, 0.5, 0.5]))

    assert result.armies_led == (army,)


def test_execute_trail_failure_reports_no_payload():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Trailer", location=FIELD))
    state.add_leader(
        LeaderState(2, kingdom_id=2, name="Target", location=FAR_AWAY, temper=Temper.BERSERK, alignment=Alignment.EVIL)
    )

    result = execute_trail(state, 1, _request(2), rng=ScriptedRandom([0.99]))

    assert result.spied_on is False
    assert result.temper is None
    assert result.alignment is None
    assert result.race is None
    assert result.king_intelligence is None
    assert result.treasures_owned == ()
    assert result.armies_led == ()


# -- advance_trail (Phase 68) -------------------------------------------------


_BOUNDS = MapBounds(*NORMAL_MAP_BOUNDS)


def test_advance_trail_moves_the_trailer_one_step_closer_then_rerolls():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Trailer", location=FIELD))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Target", location=FAR_AWAY))  # different Kingdom

    # Rigged to fail the catch-up roll at the new (still nonzero) distance --
    # proves execute_trail ran on the *post-step* location without erroring.
    result = advance_trail(state, 1, _request(2), rng=ScriptedRandom([1.0]))

    assert result.spied_on is False
    assert state.leaders[1].location != FIELD
    assert hex_distance(state.leaders[1].location, FAR_AWAY) == hex_distance(FIELD, FAR_AWAY) - 1


def test_advance_trail_reports_not_found_when_trailer_or_target_missing():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Trailer", location=FIELD))

    result = advance_trail(state, 1, _request(2))

    assert result.spied_on is False
    assert result.reason == "trailer or target not found"


# -- Add_Experience wiring (Phase 461) ----------------------------------------


def test_execute_trail_success_awards_real_add_experience_credit():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Trailer", location=FIELD))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Target", location=FIELD))

    result = execute_trail(state, 1, _request(2), rng=ScriptedRandom([0.0, 0.5, 0.5]))

    assert result.spied_on is True
    assert state.leaders[1].experience_credit == 10  # round(10*(1+0.5-0.5))


def test_execute_trail_failed_catch_up_awards_no_add_experience_credit():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Trailer", location=FIELD))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Target", location=FAR_AWAY))

    result = execute_trail(state, 1, _request(2), rng=ScriptedRandom([0.99]))

    assert result.spied_on is False
    assert state.leaders[1].experience_credit == 0


# -- Phase 695: AdvancedAbility.SPY_SUPER_SLEUTH --------------------------


def test_execute_trail_spy_super_sleuth_bypasses_the_catch_up_roll():
    # Same setup as test_execute_trail_fails_when_roll_is_too_high --
    # succeeds anyway with the ability, since the roll is never made.
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Trailer", location=FIELD))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Target", location=FAR_AWAY))

    result = execute_trail(
        state,
        1,
        _request(2),
        rng=ScriptedRandom([0.5, 0.5], choice_indices=[1]),  # (-1,0,1)[1] == 0 offset
        has_spy_super_sleuth=True,
    )

    assert result.spied_on is True
    assert result.guessed_distance == hex_distance(FIELD, FAR_AWAY)


def test_execute_trail_spy_super_sleuth_guessed_distance_can_be_off_by_one():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Trailer", location=FIELD))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Target", location=HexCoord(3, 1)))  # distance 2

    result = execute_trail(
        state,
        1,
        _request(2),
        rng=ScriptedRandom([0.5, 0.5], choice_indices=[2]),  # (-1,0,1)[2] == +1 offset
        has_spy_super_sleuth=True,
    )

    assert result.guessed_distance == 3


def test_execute_trail_spy_super_sleuth_guessed_distance_floored_at_zero():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Trailer", location=FIELD))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Target", location=FIELD))  # distance 0

    result = execute_trail(
        state,
        1,
        _request(2),
        rng=ScriptedRandom([0.5, 0.5], choice_indices=[0]),  # (-1,0,1)[0] == -1 offset
        has_spy_super_sleuth=True,
    )

    assert result.guessed_distance == 0


def test_execute_trail_guessed_distance_is_none_without_the_ability():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Trailer", location=FIELD))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Target", location=FIELD))

    result = execute_trail(state, 1, _request(2), rng=ScriptedRandom([0.0, 0.5, 0.5]))

    assert result.spied_on is True
    assert result.guessed_distance is None


def test_advance_trail_forwards_has_spy_super_sleuth():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Trailer", location=FIELD))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Target", location=FAR_AWAY))

    result = advance_trail(
        state,
        1,
        _request(2),
        rng=ScriptedRandom([0.5, 0.5], choice_indices=[1]),
        has_spy_super_sleuth=True,
    )

    assert result.spied_on is True
    assert result.guessed_distance is not None


# -- Phase 705: AdvancedAbility.SPY_EXPANDED_SPYING, Trail half --


def test_execute_trail_offices_held_empty_without_the_ability():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Trailer", location=FIELD))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Target", location=FIELD))

    with patch(
        "ak_engine.turn.trail_execution.resolve_all_office_holders",
        return_value={Office.CHANCELLOR: OfficeHolder(leader_id=2, merit_points=10)},
    ):
        result = execute_trail(state, 1, _request(2), rng=ScriptedRandom([0.0, 0.5, 0.5]))

    assert result.spied_on is True
    assert result.offices_held == ()


def test_execute_trail_offices_held_reaches_the_result_with_the_ability():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Trailer", location=FIELD))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Target", location=FIELD))

    with patch(
        "ak_engine.turn.trail_execution.resolve_all_office_holders",
        return_value={Office.CHANCELLOR: OfficeHolder(leader_id=2, merit_points=10), Office.MARSHAL: None},
    ):
        result = execute_trail(
            state, 1, _request(2), rng=ScriptedRandom([0.0, 0.5, 0.5]), caster_has_spy_expanded_spying=True
        )

    assert result.offices_held == (Office.CHANCELLOR,)


def test_execute_trail_offices_held_omits_offices_the_target_does_not_hold():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Trailer", location=FIELD))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Target", location=FIELD))
    state.add_leader(LeaderState(3, kingdom_id=1, name="Someone Else", location=FIELD))

    with patch(
        "ak_engine.turn.trail_execution.resolve_all_office_holders",
        return_value={Office.CHANCELLOR: OfficeHolder(leader_id=3, merit_points=10)},
    ):
        result = execute_trail(
            state, 1, _request(2), rng=ScriptedRandom([0.0, 0.5, 0.5]), caster_has_spy_expanded_spying=True
        )

    assert result.offices_held == ()


def test_advance_trail_forwards_caster_has_spy_expanded_spying():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Trailer", location=FIELD))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Target", location=FIELD))

    with patch(
        "ak_engine.turn.trail_execution.resolve_all_office_holders",
        return_value={Office.CHANCELLOR: OfficeHolder(leader_id=2, merit_points=10)},
    ):
        result = advance_trail(
            state, 1, _request(2), rng=ScriptedRandom([0.0, 0.5, 0.5]), caster_has_spy_expanded_spying=True
        )

    assert result.offices_held == (Office.CHANCELLOR,)


def test_execute_trail_blackmail_claim_none_without_the_ability():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Trailer", location=FIELD))
    state.add_leader(LeaderState(2, kingdom_id=2, name="King", location=FIELD, is_king=True))

    result = execute_trail(state, 1, _request(2), rng=ScriptedRandom([0.0, 0.5, 0.5]))

    assert result.blackmail_claim is None


def test_execute_trail_blackmail_claim_none_when_target_is_not_a_king():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Trailer", location=FIELD))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Hero", location=FIELD, is_king=False))

    result = execute_trail(state, 1, _request(2), rng=ScriptedRandom([0.0, 0.5, 0.5]), caster_has_spy_blackmail=True)

    assert result.blackmail_claim is None


def test_execute_trail_blackmail_claim_none_when_same_kingdom():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Trailer", location=FIELD))
    state.add_leader(LeaderState(2, kingdom_id=1, name="King", location=FIELD, is_king=True))

    result = execute_trail(state, 1, _request(2), rng=ScriptedRandom([0.0, 0.5, 0.5]), caster_has_spy_blackmail=True)

    assert result.blackmail_claim is None


def test_execute_trail_blackmail_detection_success_populates_claim_and_state():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Trailer", location=FIELD))
    state.add_leader(LeaderState(2, kingdom_id=2, name="King", location=FIELD, is_king=True))

    result = execute_trail(
        state, 1, _request(2), rng=ScriptedRandom([0.0, 0.5, 0.5, 0.0]), caster_has_spy_blackmail=True
    )

    assert result.blackmail_claim is not None
    assert result.blackmail_claim.spy_leader_id == 1
    assert result.blackmail_claim.spy_kingdom_id == 1
    assert state.kingdoms[2].pending_blackmail is result.blackmail_claim


def test_execute_trail_blackmail_detection_failed_roll_leaves_no_claim():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Trailer", location=FIELD))
    state.add_leader(LeaderState(2, kingdom_id=2, name="King", location=FIELD, is_king=True))

    result = execute_trail(
        state, 1, _request(2), rng=ScriptedRandom([0.0, 0.5, 0.5, 0.99]), caster_has_spy_blackmail=True
    )

    assert result.blackmail_claim is None
    assert state.kingdoms[2].pending_blackmail is None


def test_advance_trail_forwards_caster_has_spy_blackmail():
    state = _base_state()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Trailer", location=FIELD))
    state.add_leader(LeaderState(2, kingdom_id=2, name="King", location=FIELD, is_king=True))

    result = advance_trail(
        state, 1, _request(2), rng=ScriptedRandom([0.0, 0.5, 0.5, 0.0]), caster_has_spy_blackmail=True
    )

    assert result.blackmail_claim is not None
