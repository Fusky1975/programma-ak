from __future__ import annotations

import random

import pytest

from ak_engine.models.army_type import ArmyType
from ak_engine.models.map import Terrain
from ak_engine.turn.battle_line import BattleUnit
from ak_engine.turn.pursuit import (
    PURSUIT_SPEED,
    draw_pursuit_r01,
    draw_pursuit_random_multiplier,
    max_pursuit_attempts,
    pursuit_catch_succeeds,
    pursuit_effective_speed,
    pursuit_target_eligible,
    resolve_pursuit,
)

TRIALS = 3000


def unit(army_type: ArmyType, strength: float = 10) -> BattleUnit:
    return BattleUnit(army_type=army_type, effective_strength=strength)


# -- Phase 906: the real atspeed table (PURSUIT.md Appendix H) -----------


def test_pursuit_speed_table_matches_the_byte_dump_exactly():
    # Every value straight from PURSUIT.md's own Appendix H hex dump.
    expected = {
        ArmyType.GARRISON: 1,
        ArmyType.BOWMEN: 2,
        ArmyType.AXEMEN: 2,
        ArmyType.PHALANX: 2,
        ArmyType.LEGION: 2,
        ArmyType.LT_CAVALRY: 4,
        ArmyType.HVY_CAVALRY: 3,
        ArmyType.CHARIOTS: 3,
        ArmyType.ELEPHANTS: 2,
        ArmyType.CAMEL_CORPS: 3,
        ArmyType.WARG_RIDERS: 3,
        ArmyType.DRAGON_WING: 5,
        ArmyType.EAGLE_WING: 5,
        ArmyType.WHALES: 4,
        ArmyType.FLEET: 2,
        ArmyType.MERMEN: 3,
        ArmyType.ENTS: 1,
        ArmyType.TROLLS: 2,
        ArmyType.WEREBEASTS: 3,
        ArmyType.DINOSAURS: 3,
        ArmyType.VAMPIRES: 4,
        ArmyType.MARAUDERS: 3,
    }
    for army_type, speed in expected.items():
        assert pursuit_effective_speed(army_type) == speed


def test_pursuit_speed_table_covers_every_army_type_without_crashing():
    for army_type in ArmyType:
        assert PURSUIT_SPEED[army_type] >= 0


# -- max_pursuit_attempts: max(1, speed - front_line_penalty - 1) --------


@pytest.mark.parametrize(
    ("army_type", "front_attempts", "rear_attempts"),
    [
        (ArmyType.GARRISON, 1, 1),
        (ArmyType.BOWMEN, 1, 1),
        (ArmyType.HVY_CAVALRY, 1, 2),
        (ArmyType.CHARIOTS, 1, 2),
        (ArmyType.CAMEL_CORPS, 1, 2),
        (ArmyType.WARG_RIDERS, 1, 2),
        (ArmyType.LT_CAVALRY, 2, 3),
        (ArmyType.WHALES, 2, 3),
        (ArmyType.VAMPIRES, 2, 3),
        (ArmyType.DRAGON_WING, 3, 4),
        (ArmyType.EAGLE_WING, 3, 4),
    ],
)
def test_max_pursuit_attempts_matches_every_documented_table_row(army_type, front_attempts, rear_attempts):
    assert max_pursuit_attempts(army_type, is_front_line=True) == front_attempts
    assert max_pursuit_attempts(army_type, is_front_line=False) == rear_attempts


def test_elephants_is_not_cavalry_speed_but_camels_and_wargs_match_heavy_cavalry():
    # Directly answers the user's original question: there is no clean
    # 5-item "cavalry" set -- Elephants (speed 2) is ordinary infantry
    # speed, while Camel Corps/Warg Riders share Heavy Cavalry/Chariots'
    # own speed (3) exactly.
    assert pursuit_effective_speed(ArmyType.ELEPHANTS) == pursuit_effective_speed(ArmyType.BOWMEN)
    assert (
        pursuit_effective_speed(ArmyType.CAMEL_CORPS)
        == pursuit_effective_speed(ArmyType.WARG_RIDERS)
        == pursuit_effective_speed(ArmyType.HVY_CAVALRY)
        == pursuit_effective_speed(ArmyType.CHARIOTS)
    )


# -- draw_pursuit_r01 / pursuit_catch_succeeds ----------------------------


def test_draw_pursuit_r01_is_a_fair_coin():
    rng = random.Random(906)
    draws = [draw_pursuit_r01(rng) for _ in range(TRIALS)]
    assert set(draws) == {0, 1}
    assert abs(sum(draws) / TRIALS - 0.5) < 0.03


def test_pursuit_catch_succeeds_deterministic_when_speed_gap_guarantees_it():
    # speed(pursuer)=4, front_line_penalty=0, attempt_index=0 -> s=4;
    # speed(target)=1 -- even r01()=0 gives 4>1.
    rng = random.Random(0)
    assert (
        pursuit_catch_succeeds(ArmyType.LT_CAVALRY, 0, ArmyType.ENTS, rng, is_front_line=False) is True
    )


def test_pursuit_catch_succeeds_deterministic_when_speed_gap_forbids_it():
    # speed(pursuer)=1, front_line_penalty=1, attempt_index=0 -> s=0;
    # speed(target)=5 -- even r01()=1 gives 1, never > 5.
    rng = random.Random(0)
    assert pursuit_catch_succeeds(ArmyType.ENTS, 0, ArmyType.DRAGON_WING, rng, is_front_line=True) is False


def test_pursuit_catch_succeeds_the_tie_case_depends_on_r01():
    # speed(pursuer)=2, front_line_penalty=0, attempt_index=0 -> s=2;
    # speed(target)=2 -- catch succeeds only when r01()=1 (2+1>2).
    assert pursuit_catch_succeeds(ArmyType.BOWMEN, 0, ArmyType.AXEMEN, _Rng(0.0), is_front_line=False) is False
    assert pursuit_catch_succeeds(ArmyType.BOWMEN, 0, ArmyType.AXEMEN, _Rng(0.9), is_front_line=False) is True


class _Rng(random.Random):
    def __init__(self, value: float) -> None:
        super().__init__()
        self._value = value

    def random(self) -> float:
        return self._value


# -- pursuit_target_eligible: Whale League only pursuable at Sea ---------


def test_whale_league_target_ineligible_outside_sea():
    assert pursuit_target_eligible(ArmyType.WHALES, Terrain.PLAINS) is False
    assert pursuit_target_eligible(ArmyType.WHALES, Terrain.SEA) is True


def test_ordinary_target_always_eligible():
    assert pursuit_target_eligible(ArmyType.BOWMEN, Terrain.PLAINS) is True
    assert pursuit_target_eligible(ArmyType.BOWMEN, Terrain.SEA) is True


# -- draw_pursuit_random_multiplier: U[1,2) -------------------------------


def test_draw_pursuit_random_multiplier_stays_within_u1_2():
    rng = random.Random(349)
    for _ in range(TRIALS):
        multiplier = draw_pursuit_random_multiplier(rng)
        assert 1.0 <= multiplier < 2.0


# -- resolve_pursuit: the full per-position attempt loop ------------------


def test_resolve_pursuit_front_line_unit_gets_the_front_line_penalty():
    # A speed-2 front-line pursuer (Legion) gets exactly 1 attempt
    # (max(1, 2-1-1)=1); against a same-speed target the tie-break r01()
    # decides. Force r01()=0 (rng.random()<0.5) -> s=2-1-0=1, 0+1=1, not >
    # target speed 2 -- no catch, no outcome recorded.
    winner_columns = [[unit(ArmyType.LEGION)]]
    targets = [unit(ArmyType.AXEMEN)]
    rng = _Rng(0.0)

    outcomes = resolve_pursuit(winner_columns, targets, Terrain.PLAINS, rng)

    assert outcomes == []


class _CountingNeverCatchRng(random.Random):
    """``random()`` always 0.0 (the weakest possible ``r01``); counts
    ``.choice()`` calls (one per target draw/attempt) without otherwise
    affecting which target is picked.
    """

    def __init__(self) -> None:
        super().__init__()
        self.choice_calls = 0

    def random(self) -> float:
        return 0.0

    def choice(self, seq):
        self.choice_calls += 1
        return seq[0]


def test_resolve_pursuit_rear_unit_gets_more_attempts_than_front_line():
    # A target too fast to ever be caught (speed 5 -- even r01()=1 can't
    # beat it for any pursuer used here) isolates the attempt *count*:
    # Light Cavalry (speed 4) gets max(1,4-0-1)=3 attempts from the rear,
    # vs max(1,4-1-1)=2 from the front line -- confirmed by counting
    # target draws (one .choice() call per attempt) directly.
    target = [unit(ArmyType.DRAGON_WING, strength=1)]  # speed 5, never caught here

    front_rng = _CountingNeverCatchRng()
    resolve_pursuit([[unit(ArmyType.LT_CAVALRY)]], target, Terrain.PLAINS, front_rng)
    assert front_rng.choice_calls == 2

    rear_rng = _CountingNeverCatchRng()
    resolve_pursuit([[unit(ArmyType.BOWMEN), unit(ArmyType.LT_CAVALRY)]], target, Terrain.PLAINS, rear_rng)
    assert rear_rng.choice_calls == 1 + 3  # Bowmen's own 1 front-line attempt + LCav's 3 rear attempts


def test_resolve_pursuit_position_order_is_front_line_of_every_column_first():
    # Two columns, each with a front+rear unit: the front-line units of
    # both columns must be visited before either column's own rear unit
    # (PURSUIT.md's own row-major-by-depth position order). Verified by
    # forcing every possible catch, then checking the outcome order.
    winner_columns = [
        [unit(ArmyType.HVY_CAVALRY), unit(ArmyType.HVY_CAVALRY)],
        [unit(ArmyType.LT_CAVALRY), unit(ArmyType.LT_CAVALRY)],
    ]
    targets = [unit(ArmyType.ENTS, strength=1) for _ in range(10)]
    rng = _AlwaysCatchRng()

    outcomes = resolve_pursuit(winner_columns, targets, Terrain.PLAINS, rng)

    visited_columns = [outcome.pursuer.army_type for outcome in outcomes[:2]]
    assert visited_columns == [ArmyType.HVY_CAVALRY, ArmyType.LT_CAVALRY]


class _AlwaysCatchRng(random.Random):
    """random()->0.99 (guarantees any catch test with a nonnegative s),
    choice()->first element (deterministic target pick)."""

    def random(self) -> float:
        return 0.99

    def choice(self, seq):
        return seq[0]

    def uniform(self, a: float, b: float) -> float:
        return a


def test_resolve_pursuit_whale_league_target_never_caught_outside_sea():
    winner_columns = [[unit(ArmyType.DRAGON_WING)]]
    targets = [unit(ArmyType.WHALES, strength=1)]
    rng = _AlwaysCatchRng()

    outcomes = resolve_pursuit(winner_columns, targets, Terrain.PLAINS, rng)

    assert outcomes == []


def test_resolve_pursuit_whale_league_target_can_be_caught_at_sea():
    winner_columns = [[unit(ArmyType.DRAGON_WING)]]
    targets = [unit(ArmyType.WHALES, strength=1)]
    rng = _AlwaysCatchRng()

    outcomes = resolve_pursuit(winner_columns, targets, Terrain.SEA, rng)

    assert len(outcomes) == 1


def test_resolve_pursuit_destroys_when_pursuer_overwhelms():
    winner_columns = [[unit(ArmyType.HVY_CAVALRY, strength=1000)]]
    targets = [unit(ArmyType.ENTS, strength=1)]
    rng = _AlwaysCatchRng()

    outcomes = resolve_pursuit(winner_columns, targets, Terrain.PLAINS, rng)

    assert outcomes[0].target_destroyed is True


def test_resolve_pursuit_target_resists_when_pursuer_is_weak():
    winner_columns = [[unit(ArmyType.HVY_CAVALRY, strength=1)]]
    targets = [unit(ArmyType.ENTS, strength=1000)]
    rng = _AlwaysCatchRng()

    outcomes = resolve_pursuit(winner_columns, targets, Terrain.PLAINS, rng)

    assert outcomes[0].target_destroyed is False


def test_resolve_pursuit_a_caught_target_stops_this_pursuers_own_search():
    # A single-attempt pursuer (front-line, speed-2 Bowmen) that catches
    # its only target on attempt 0 never gets a second outcome recorded
    # for the same pursuer.
    winner_columns = [[unit(ArmyType.BOWMEN)]]
    targets = [unit(ArmyType.ENTS, strength=1)]
    rng = _AlwaysCatchRng()

    outcomes = resolve_pursuit(winner_columns, targets, Terrain.PLAINS, rng)

    assert len(outcomes) == 1


def test_resolve_pursuit_stops_early_once_retreaters_run_out():
    # Two Light Cavalry pursuers (budget 2 attempts each) but only one
    # target, destroyed by the first pursuer -- the second pursuer must
    # not raise or fabricate an outcome against a nonexistent target.
    winner_columns = [[unit(ArmyType.LT_CAVALRY), unit(ArmyType.LT_CAVALRY)]]
    targets = [unit(ArmyType.ENTS, strength=1)]
    rng = _AlwaysCatchRng()

    outcomes = resolve_pursuit(winner_columns, targets, Terrain.PLAINS, rng)

    assert len(outcomes) == 1


def test_resolve_pursuit_no_targets_at_all_returns_no_outcomes():
    winner_columns = [[unit(ArmyType.LT_CAVALRY)]]
    outcomes = resolve_pursuit(winner_columns, [], Terrain.PLAINS, random.Random(0))
    assert outcomes == []


def test_resolve_pursuit_empty_winner_side_returns_no_outcomes():
    outcomes = resolve_pursuit([], [unit(ArmyType.ENTS)], Terrain.PLAINS, random.Random(0))
    assert outcomes == []
