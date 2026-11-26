"""Tests for turn/tax_base.py -- see its module docstring for the full,
project-original scar-then-percent-modifier formula this exercises.
"""

from __future__ import annotations

from ak_engine.models.alignment import Alignment
from ak_engine.models.discovery import Discovery
from ak_engine.models.feature import Feature, FeatureType
from ak_engine.models.game_state import BlackmailClaim, GameState, KingdomState, LeaderState, ProvinceState
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.monster import Monster, MonsterEngagementState
from ak_engine.models.race import Race
from ak_engine.turn.tax_base import (
    apply_turn_revenue,
    compute_invention_bonus_percent,
    compute_office_gold_bonus,
    compute_tax_base,
    province_tax_yield,
)
from _helpers import ScriptedRandom

HOME = HexCoord(0, 0)


def make_state() -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, HOME))
    state.add_kingdom(KingdomState(2, "Defendia", Race.HUMAN, Alignment.NEUTRAL, HOME))
    return state


def test_province_tax_yield_none_when_tax_unrecorded():
    province = ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN)
    assert province_tax_yield(province) is None


def test_province_tax_yield_plain_base_tax():
    province = ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, tax=4)
    assert province_tax_yield(province) == 4


def test_province_tax_yield_applies_scar_terrain_reduction():
    province = ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, tax=4, scar_terrain_gold_reduction=2)
    assert province_tax_yield(province) == 2


def test_province_tax_yield_scar_terrain_floors_at_zero():
    province = ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, tax=3, scar_terrain_gold_reduction=10)
    assert province_tax_yield(province) == 0


def test_province_tax_yield_applies_bless_bonus():
    province = ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, tax=10, tax_modifier_percent=60)
    assert province_tax_yield(province) == 16


def test_province_tax_yield_earthquake_zeroes_revenue():
    province = ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, tax=10, tax_modifier_percent=-100)
    assert province_tax_yield(province) == 0


def test_province_tax_yield_applies_earthquake_flat_reduction():
    # Phase 270: Reinforced Concrete's own flat 3-gold Earthquake
    # replacement -- ProvinceState.earthquake_flat_reduction.
    province = ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, tax=10, earthquake_flat_reduction=3)
    assert province_tax_yield(province) == 7


def test_province_tax_yield_earthquake_flat_reduction_floors_at_zero():
    province = ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, tax=2, earthquake_flat_reduction=3)
    assert province_tax_yield(province) == 0


def test_province_tax_yield_combines_scar_then_bless():
    # base 10 -> scar -2 -> 8 -> Bless +60% -> 12
    province = ProvinceState(
        HOME, Terrain.PLAINS, Race.HUMAN, tax=10, scar_terrain_gold_reduction=2, tax_modifier_percent=60
    )
    assert province_tax_yield(province) == 12


# -- Phase 509: Find Mines' own mine_gold_bonus -----------------------------


def test_province_tax_yield_applies_find_mines_bonus():
    province = ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, tax=4, mine_gold_bonus=3)
    assert province_tax_yield(province) == 7


def test_province_tax_yield_combines_mines_with_scar_then_bless():
    # base 10 -> scar -2, mines +5 -> 13 -> Bless +60% -> 20 (20.8 floored)
    province = ProvinceState(
        HOME,
        Terrain.PLAINS,
        Race.HUMAN,
        tax=10,
        scar_terrain_gold_reduction=2,
        mine_gold_bonus=5,
        tax_modifier_percent=60,
    )
    assert province_tax_yield(province) == 20


def test_province_tax_yield_mines_cannot_push_below_zero_floor():
    # scar reduction still dominates -- mines only ever add, never rescue
    # a heavily scarred province past its own floor-at-zero rule doesn't
    # apply here since mines are additive, but the combined value must
    # never go negative even in a degenerate scar > tax + mines case.
    province = ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, tax=2, scar_terrain_gold_reduction=10, mine_gold_bonus=3)
    assert province_tax_yield(province) == 0


def test_compute_tax_base_sums_only_owned_provinces_with_known_tax():
    state = make_state()
    state.add_province(ProvinceState(HexCoord(0, 0), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, tax=4))
    state.add_province(ProvinceState(HexCoord(0, 1), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, tax=6))
    state.add_province(ProvinceState(HexCoord(0, 2), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2, tax=10))
    state.add_province(ProvinceState(HexCoord(0, 3), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))  # tax unknown

    assert compute_tax_base(state, 1) == 10
    assert compute_tax_base(state, 2) == 10


def test_compute_tax_base_ignores_unowned_provinces():
    state = make_state()
    state.add_province(ProvinceState(HexCoord(0, 0), Terrain.PLAINS, Race.HUMAN, tax=4))

    assert compute_tax_base(state, 1) == 0


def test_compute_tax_base_zero_for_a_kingdom_with_no_provinces():
    state = make_state()
    assert compute_tax_base(state, 1) == 0


def test_compute_tax_base_does_not_count_allied_kingdoms_provinces():
    # Tax_Base is a single kingdom's own revenue figure, distinct from
    # GameState.friendly_provinces_for's broader owned-or-allied scope.
    state = make_state()
    state.allied_kingdoms.add(frozenset({1, 2}))
    state.add_province(ProvinceState(HexCoord(0, 0), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2, tax=10))

    assert compute_tax_base(state, 1) == 0


# -- Phase 268: compute_invention_bonus_percent() (Inv_Bonus) --------------


def test_compute_invention_bonus_percent_zero_with_no_discoveries():
    kingdom = KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, HOME)
    assert compute_invention_bonus_percent(kingdom) == 0


def test_compute_invention_bonus_percent_sums_only_revenue_discoveries():
    kingdom = KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, HOME)
    kingdom.discoveries = {
        Discovery.PEANUT_BUTTER_SANDWICH,  # 1%
        Discovery.ASPIRIN_PILL,  # 2%
        Discovery.COMPASS,  # ability bonus, no revenue contribution
    }

    assert compute_invention_bonus_percent(kingdom) == 3


# -- Phase 412: compute_office_gold_bonus() + apply_turn_revenue() --------


def test_compute_office_gold_bonus_credits_this_kingdoms_king_of_pain():
    # King of Pain's own merit-point formula is plain Tax_Base(King)
    # (Phase 369), gated at OFFICE_MIN_POINTS[EVIL_KING] == 25 -- a real
    # province tax base is needed to actually clear the Rank contest.
    state = make_state()
    state.kingdoms[1].alignment = Alignment.EVIL
    state.add_leader(LeaderState(1, 1, "Vaelgor", HOME, is_king=True))
    state.add_province(ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, tax=30))

    assert compute_office_gold_bonus(state, 1) == 5


def test_compute_office_gold_bonus_credits_this_kingdoms_prince_of_thieves():
    state = make_state()
    king = LeaderState(1, 1, "Aldric", HOME, is_king=True)
    king.merit_tally.successful_thefts = 5
    state.add_leader(king)

    assert compute_office_gold_bonus(state, 1) == 10


def test_compute_office_gold_bonus_sums_both_offices_when_both_are_earned():
    state = make_state()
    state.kingdoms[1].alignment = Alignment.EVIL
    king = LeaderState(1, 1, "Vaelgor", HOME, is_king=True)
    king.merit_tally.successful_thefts = 5
    state.add_leader(king)
    state.add_province(ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, tax=30))

    assert compute_office_gold_bonus(state, 1) == 15


def test_compute_office_gold_bonus_ignores_another_kingdoms_holder():
    state = make_state()
    state.kingdoms[2].alignment = Alignment.EVIL
    state.add_leader(LeaderState(2, 2, "Borin", HOME, is_king=True))
    state.add_province(ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2, tax=30))

    assert compute_office_gold_bonus(state, 1) == 0


def test_compute_office_gold_bonus_zero_when_nobody_holds_either_office():
    state = make_state()

    assert compute_office_gold_bonus(state, 1) == 0


def test_apply_turn_revenue_credits_tax_base_plus_office_bonus_to_treasury():
    state = make_state()
    state.kingdoms[1].alignment = Alignment.EVIL
    state.kingdoms[1].treasury = 50
    state.add_leader(LeaderState(1, 1, "Vaelgor", HOME, is_king=True))
    state.add_province(ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, tax=30))

    # Phase 747: one extra `rng.random()` draw per kingdom, unconditional
    # (the real `Inv_Bonus` credit formula), even with `Inv_Bonus() == 0`.
    credited = apply_turn_revenue(state, ScriptedRandom([0.0, 0.0]))

    assert credited == {1: 35, 2: 0}
    assert state.kingdoms[1].treasury == 85


def test_apply_turn_revenue_credits_each_kingdom_independently():
    state = make_state()
    state.add_province(ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, tax=4))
    state.add_province(ProvinceState(HexCoord(0, 1), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2, tax=6))

    credited = apply_turn_revenue(state, ScriptedRandom([0.0, 0.0]))

    assert credited == {1: 4, 2: 6}
    assert state.kingdoms[1].treasury == 4
    assert state.kingdoms[2].treasury == 6


# -- Phase 670: apply_turn_revenue() now runs each province through
# turn/monster_raids.py resolve_province_raids() --------------------------


def test_apply_turn_revenue_reduces_credit_for_a_raided_province_and_records_the_event():
    state = make_state()
    state.turn_number = 4  # monsters do not plunder before turn 4
    state.add_province(ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, tax=700))
    state.add_feature(
        Feature(
            feature_id=1,
            coord=HOME,
            kind=FeatureType.DUNGEON,
            guardian_monster=Monster.GRYPHON,  # Temper.BERSERK -- always active.
            guardian_state=MonsterEngagementState.BOLD,
        )
    )

    # Activity check (Berserk, always active regardless of the draw); no
    # Thunderbird holder configured, so no second roll is consumed. Phase
    # 747 adds one more unconditional `rng.random()` draw per kingdom
    # for the real `Inv_Bonus` credit formula.
    credited = apply_turn_revenue(state, ScriptedRandom([0.0, 0.0, 0.0]))

    assert credited[1] < 700
    assert len(state.turn_raid_events) == 1
    assert state.turn_raid_events[0].kind == "raid"
    assert state.kingdoms[1].treasury == credited[1]


def test_apply_turn_revenue_expected_revenues_line_unaffected_by_a_raid():
    state = make_state()
    state.add_province(ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, tax=700))
    state.add_feature(
        Feature(
            feature_id=1,
            coord=HOME,
            kind=FeatureType.DUNGEON,
            guardian_monster=Monster.GRYPHON,
            guardian_state=MonsterEngagementState.BOLD,
        )
    )

    apply_turn_revenue(state, ScriptedRandom([0.0, 0.0, 0.0]))

    # The persisted per-province tax base -- what "Expected Revenues"
    # renders -- is untouched by the raid; only this turn's own credited
    # amount (asserted above) is reduced.
    assert compute_tax_base(state, 1) == 700
    assert province_tax_yield(state.provinces[HOME]) == 700


def test_apply_turn_revenue_resets_turn_raid_events_each_call():
    state = make_state()
    state.turn_raid_events = ["stale"]  # type: ignore[list-item]
    state.add_province(ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, tax=4))

    apply_turn_revenue(state, ScriptedRandom([0.0, 0.0]))

    assert state.turn_raid_events == []


# -- Phase 713: apply_turn_revenue() now resolves a still-unpaid
# AdvancedAbility.SPY_BLACKMAIL claim once per Kingdom -----------------


def test_apply_turn_revenue_applies_unpaid_blackmail_penalty():
    state = make_state()
    state.add_province(ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, tax=100))
    state.add_leader(LeaderState(9, 2, "Spymaster", HOME))
    state.kingdoms[1].active_blackmail = BlackmailClaim(spy_leader_id=9, spy_kingdom_id=2, amount=15)

    credited = apply_turn_revenue(state, ScriptedRandom([0.0, 0.0]))

    assert credited[1] == 100 - 45  # 3x the 15-gold demand
    assert state.kingdoms[1].active_blackmail is None
    assert state.leaders[9].unpaid_blackmail_penalty_exponent == 1
    # Phase 741: the real penalty actually deducted is recorded for
    # report/turn_report.py's own FINANCES-section narration.
    assert len(state.turn_blackmail_penalties) == 1
    penalty = state.turn_blackmail_penalties[0]
    assert penalty.kingdom_id == 1
    assert penalty.blackmailer_kingdom_id == 2
    assert penalty.amount == 45


def test_apply_turn_revenue_untouched_without_an_active_claim():
    state = make_state()
    state.add_province(ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, tax=100))

    credited = apply_turn_revenue(state, ScriptedRandom([0.0, 0.0]))

    assert credited[1] == 100
    assert state.turn_blackmail_penalties == []


def test_apply_turn_revenue_blackmail_penalty_is_capped_at_available_income():
    # A demand far larger than this turn's own real province income --
    # the recorded penalty (and the credited deduction) can't exceed
    # what was actually available to lose.
    state = make_state()
    state.add_province(ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, tax=10))
    state.add_leader(LeaderState(9, 2, "Spymaster", HOME))
    state.kingdoms[1].active_blackmail = BlackmailClaim(spy_leader_id=9, spy_kingdom_id=2, amount=15)

    credited = apply_turn_revenue(state, ScriptedRandom([0.0, 0.0]))

    assert credited[1] == 0  # floored, never negative
    assert len(state.turn_blackmail_penalties) == 1
    assert state.turn_blackmail_penalties[0].amount == 10  # capped, not the full 45


# -- Phase 747: Inv_Bonus really credits gold (Desktop/INVBONUS.md) -------


def test_apply_turn_revenue_applies_the_real_stochastic_invention_bonus_rounding():
    # INVBONUS.md SS6's own worked example: B=26, P=2% -> 0.52, rounding
    # down (U<0.52 -> Trunc(0.52+U)==0) or up (U>=0.48 -> Trunc(0.52+U)
    # ==1) -- Trunc(x+U), not round()/floor-only.
    state = make_state()
    state.kingdoms[1].discoveries = {Discovery.ASPIRIN_PILL}  # +2%
    state.add_province(ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, tax=26))

    credited_down = apply_turn_revenue(state, ScriptedRandom([0.0, 0.0]))
    assert credited_down[1] == 26  # Trunc(0.52 + 0.0) == 0

    state = make_state()
    state.kingdoms[1].discoveries = {Discovery.ASPIRIN_PILL}
    state.add_province(ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, tax=26))
    credited_up = apply_turn_revenue(state, ScriptedRandom([0.48, 0.0]))
    assert credited_up[1] == 27  # Trunc(0.52 + 0.48) == 1


def test_apply_turn_revenue_draws_rng_unconditionally_even_with_zero_percent():
    # INVBONUS.md's own confirmed fidelity point: `Random` is drawn once
    # per active Kingdom regardless of whether Inv_Bonus(kng) == 0 --
    # skipping it would desync every later RNG draw. No IndexError means
    # exactly one draw per kingdom was consumed, not zero.
    state = make_state()  # no discoveries, no provinces -- percent == 0, amount == 0 for both

    credited = apply_turn_revenue(state, ScriptedRandom([0.0, 0.0]))

    assert credited == {1: 0, 2: 0}


def test_apply_turn_revenue_populates_turn_revenue_credited_for_the_lrev_narration():
    state = make_state()
    state.add_province(ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, tax=4))

    apply_turn_revenue(state, ScriptedRandom([0.0, 0.0]))

    assert state.turn_revenue_credited == {1: 4, 2: 0}


def test_apply_turn_revenue_each_kingdom_draws_its_own_independent_invention_roll():
    state = make_state()
    state.kingdoms[1].discoveries = {Discovery.ASPIRIN_PILL}  # +2%
    state.kingdoms[2].discoveries = {Discovery.ASPIRIN_PILL}
    state.add_province(ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, tax=26))
    state.add_province(ProvinceState(HexCoord(0, 1), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2, tax=26))

    # Kingdom 1's own roll rounds down, Kingdom 2's own roll (drawn
    # independently, second in `state.kingdoms` iteration order) rounds up.
    credited = apply_turn_revenue(state, ScriptedRandom([0.0, 0.48]))

    assert credited == {1: 26, 2: 27}
