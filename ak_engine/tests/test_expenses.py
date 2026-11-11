"""Tests for turn/expenses.py -- see its module docstring for the full
real-sample cross-check this exercises.
"""

from __future__ import annotations

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ARMY_TABLE, ArmyType
from ak_engine.models.game_state import ArmyState, GameState, KingdomState, LeaderState
from ak_engine.models.map import HexCoord
from ak_engine.models.race import Race
from ak_engine.models.temper import Temper
from ak_engine.models.valhalla import VALHALLA_VISITOR_LEADER_ID
from ak_engine.turn.combat import Quality
from ak_engine.turn.expenses import (
    apply_turn_maintenance,
    compute_army_maintenance,
    compute_expected_expenses,
    compute_leader_maintenance,
    leader_pay,
)
from ak_engine.turn.hire_pay import hero_liking, required_pay

from _helpers import ScriptedRandom

HOME = HexCoord(3, 5)


def make_state() -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, HOME))
    state.add_kingdom(KingdomState(2, "Defendia", Race.HUMAN, Alignment.NEUTRAL, HOME))
    return state


# -- compute_army_maintenance --------------------------------------------


def test_compute_army_maintenance_sums_pay_across_owned_armies():
    state = make_state()
    state.add_army(ArmyState(1, 1, ArmyType.LEGION, Quality.AVERAGE, HOME))
    state.add_army(ArmyState(2, 1, ArmyType.LEGION, Quality.AVERAGE, HOME))
    state.add_army(ArmyState(3, 1, ArmyType.LT_CAVALRY, Quality.AVERAGE, HOME))

    # SE3__T0.K2 (real sample, 2026-07-29): 2x Legion + 1x Lt Cavalry = 6.
    assert compute_army_maintenance(state, 1) == 6


def test_compute_army_maintenance_ignores_mercenary_armies():
    state = make_state()
    state.add_army(ArmyState(1, 1, ArmyType.LEGION, Quality.AVERAGE, HOME))
    state.add_army(ArmyState(2, None, ArmyType.CAMEL_CORPS, Quality.AVERAGE, HOME))  # unowned mercenary

    assert compute_army_maintenance(state, 1) == 2


def test_compute_army_maintenance_ignores_other_kingdoms_armies():
    state = make_state()
    state.add_army(ArmyState(1, 1, ArmyType.LEGION, Quality.AVERAGE, HOME))
    state.add_army(ArmyState(2, 2, ArmyType.HVY_CAVALRY, Quality.AVERAGE, HOME))

    assert compute_army_maintenance(state, 1) == 2


def test_compute_army_maintenance_zero_with_no_armies():
    state = make_state()
    assert compute_army_maintenance(state, 1) == 0


def test_compute_army_maintenance_skips_army_types_with_no_army_table_entry():
    # Phase 1054 bug fix: 8 real ArmyType ordinals (Vampires, Marauders,
    # Shamans, Crossbow, Javelins, Artillery, Spiders, D_Turtle) have no
    # ARMY_TABLE entry -- turn/recruit.py's own resolve_recruit() was
    # already hardened against this exact same bare lookup with a
    # documented bug-fix comment, but compute_army_maintenance() used to
    # have no equivalent guard, crashing with an unhandled KeyError for
    # any kingdom owning one (e.g. created via the GM army editor, which
    # applies no ARMY_TABLE filtering).
    state = make_state()
    state.add_army(ArmyState(1, 1, ArmyType.LEGION, Quality.AVERAGE, HOME))
    state.add_army(ArmyState(2, 1, ArmyType.VAMPIRES, Quality.AVERAGE, HOME))

    assert compute_army_maintenance(state, 1) == ARMY_TABLE[ArmyType.LEGION].pay


# -- compute_leader_maintenance ------------------------------------------


def test_compute_leader_maintenance_king_contributes_zero():
    state = make_state()
    state.add_leader(LeaderState(1, 1, "King", HOME, is_king=True, alignment=Alignment.GOOD, temper=Temper.BRAVE))

    assert compute_leader_maintenance(state, 1) == 0


def test_compute_leader_maintenance_ordinary_hero_uses_required_pay():
    state = make_state()
    state.add_leader(LeaderState(1, 1, "King", HOME, is_king=True, alignment=Alignment.GOOD, temper=Temper.CAUTIOUS))
    state.add_leader(LeaderState(2, 1, "Adele", HOME, alignment=Alignment.GOOD, temper=Temper.BRAVE))

    # Alignment distance 0 -- required_pay() is 1 regardless of the temper
    # mismatch (no friction to amplify at distance 0), at this leader-id
    # pair's own bias (see turn/hire_pay.py's own module docstring for why
    # the real formula's bias term means this isn't distance-0-implies-1
    # universally, just for these specific ids).
    assert compute_leader_maintenance(state, 1) == 1


def test_compute_leader_maintenance_sums_multiple_heroes():
    state = make_state()
    state.add_leader(LeaderState(1, 1, "King", HOME, is_king=True, alignment=Alignment.GOOD, temper=Temper.CAUTIOUS))
    state.add_leader(LeaderState(2, 1, "Adele", HOME, alignment=Alignment.GOOD, temper=Temper.BRAVE))
    state.add_leader(LeaderState(3, 1, "Indra", HOME, alignment=Alignment.GOOD, temper=Temper.CAUTIOUS))

    # Adele (id 2) prices at 1, Indra (id 3) at 2 -- both at real alignment
    # distance 0, differing only in the real formula's own per-leader-id
    # bias term (turn/hire_pay.py's own module docstring).
    assert compute_leader_maintenance(state, 1) == 3


def test_compute_leader_maintenance_valhalla_visitor_contributes_zero():
    state = make_state()
    state.add_leader(LeaderState(1, 1, "King", HOME, is_king=True, alignment=Alignment.NEUTRAL, temper=Temper.BRAVE))
    state.add_leader(
        LeaderState(
            VALHALLA_VISITOR_LEADER_ID, 1, "Kitralus", HOME, alignment=Alignment.NEUTRAL, temper=Temper.BRAVE
        )
    )

    # SE3__T0.K3 (real sample): Kitralus (the Valhalla visitor) prints 0
    # despite an alignment/temper match that would otherwise price non-zero.
    assert compute_leader_maintenance(state, 1) == 0


def test_compute_leader_maintenance_ignores_other_kingdoms_leaders():
    state = make_state()
    state.add_leader(LeaderState(1, 1, "King", HOME, is_king=True, alignment=Alignment.GOOD, temper=Temper.BRAVE))
    state.add_leader(LeaderState(2, 2, "Rival Hero", HOME, alignment=Alignment.GOOD, temper=Temper.BRAVE))

    assert compute_leader_maintenance(state, 1) == 0


# -- leader_pay (Phase 280) ----------------------------------------------


def test_leader_pay_king_is_zero_even_against_himself():
    state = make_state()
    king = LeaderState(1, 1, "Bradipo I", HOME, is_king=True, alignment=Alignment.GOOD, temper=Temper.CAUTIOUS)
    state.add_leader(king)

    assert leader_pay(state, king, king) == 0


def test_leader_pay_valhalla_visitor_is_zero():
    state = make_state()
    visitor = LeaderState(
        VALHALLA_VISITOR_LEADER_ID, 1, "Kitralus", HOME, alignment=Alignment.NEUTRAL, temper=Temper.BRAVE
    )
    king = LeaderState(1, 1, "King", HOME, is_king=True, alignment=Alignment.NEUTRAL, temper=Temper.BRAVE)

    assert leader_pay(state, visitor, king) == 0


def test_leader_pay_ordinary_hero_uses_the_real_formula():
    # King Bradipo I (Good/Cautious); Adele (Good/Brave, distance 0) -> 1;
    # Indra (Good/Cautious, distance 0, same temper) -> 2 -- both at real
    # alignment distance 0, differing only in the real formula's own
    # per-leader-id bias term (turn/hire_pay.py's own module docstring).
    state = make_state()
    king = LeaderState(1, 1, "Bradipo I", HOME, is_king=True, alignment=Alignment.GOOD, temper=Temper.CAUTIOUS)
    adele = LeaderState(2, 1, "Adele", HOME, alignment=Alignment.GOOD, temper=Temper.BRAVE)
    indra = LeaderState(3, 1, "Indra", HOME, alignment=Alignment.GOOD, temper=Temper.CAUTIOUS)

    assert leader_pay(state, adele, king) == 1
    assert leader_pay(state, indra, king) == 2


def test_leader_pay_no_king_falls_back_to_permissive_default():
    state = make_state()
    hero = LeaderState(2, 1, "Adele", HOME, alignment=Alignment.GOOD, temper=Temper.BRAVE)

    assert leader_pay(state, hero, None) == 1


# -- compute_expected_expenses -------------------------------------------


def test_compute_expected_expenses_sums_army_and_leader_maintenance():
    # King Bradipo I (Good/Cautious), two Heroes (Adele Good/Brave -> 1
    # gold, Indra Good/Caut -> 2 gold, both real alignment distance 0,
    # differing only via the real formula's own bias -- turn/hire_pay.py's
    # own module docstring), and six Hired armies -- three Legion (2
    # each), two Lt Cavalry (2 each), one Camel Corps (3) -- summing to
    # 13. Expected total: 13 (armies) + 3 (leaders) = 16.
    state = make_state()
    state.add_leader(LeaderState(1, 1, "Bradipo I", HOME, is_king=True, alignment=Alignment.GOOD, temper=Temper.CAUTIOUS))
    state.add_leader(LeaderState(2, 1, "Adele", HOME, alignment=Alignment.GOOD, temper=Temper.BRAVE))
    state.add_leader(LeaderState(3, 1, "Indra", HOME, alignment=Alignment.GOOD, temper=Temper.CAUTIOUS))
    for army_id, army_type in enumerate(
        [
            ArmyType.LEGION,
            ArmyType.LEGION,
            ArmyType.LEGION,
            ArmyType.LT_CAVALRY,
            ArmyType.LT_CAVALRY,
            ArmyType.CAMEL_CORPS,
        ],
        start=1,
    ):
        state.add_army(ArmyState(army_id, 1, army_type, Quality.AVERAGE, HOME))

    assert compute_expected_expenses(state, 1) == 16


# -- apply_turn_maintenance (Phase 404) -----------------------------------


def test_apply_turn_maintenance_debits_treasury_by_expected_expenses():
    state = make_state()
    state.kingdoms[1].treasury = 100
    state.add_leader(LeaderState(1, 1, "Bradipo I", HOME, is_king=True, alignment=Alignment.GOOD, temper=Temper.CAUTIOUS))
    state.add_leader(LeaderState(2, 1, "Adele", HOME, alignment=Alignment.GOOD, temper=Temper.BRAVE))
    state.add_army(ArmyState(1, 1, ArmyType.LEGION, Quality.AVERAGE, HOME))

    result = apply_turn_maintenance(state)

    # 2 (army) + 1 (Adele, distance 0) = 3.
    assert result[1].debited == 3
    assert result[1].deserted_leader_ids == []
    assert result[1].standby_leader_ids == []
    assert result[2].debited == 0
    assert state.kingdoms[1].treasury == 97
    # Phase 771: the returned dict is also persisted onto `state`, the
    # same convention `apply_turn_revenue()` already established for
    # `state.turn_revenue_credited`.
    assert state.turn_maintenance_by_kingdom == result


def test_apply_turn_maintenance_covers_every_kingdom_independently():
    state = make_state()
    state.kingdoms[1].treasury = 10
    state.kingdoms[2].treasury = 10
    state.add_army(ArmyState(1, 1, ArmyType.LEGION, Quality.AVERAGE, HOME))
    state.add_army(ArmyState(2, 2, ArmyType.HVY_CAVALRY, Quality.AVERAGE, HOME))

    result = apply_turn_maintenance(state)

    assert result[1].debited == 2
    assert result[2].debited == 3
    assert state.kingdoms[1].treasury == 8
    assert state.kingdoms[2].treasury == 7


def test_apply_turn_maintenance_is_a_noop_with_nothing_to_pay():
    state = make_state()
    state.kingdoms[1].treasury = 5

    result = apply_turn_maintenance(state)

    assert result[1].debited == 0
    assert result[2].debited == 0
    assert state.kingdoms[1].treasury == 5


def test_apply_turn_maintenance_unclamped_allows_negative_treasury():
    # Army maintenance alone (no Heroes) stays unclamped -- Phase 527's own
    # per-Hero desertion mechanic never applies to ACost.
    state = make_state()
    state.kingdoms[1].treasury = 1
    state.add_army(ArmyState(1, 1, ArmyType.LEGION, Quality.AVERAGE, HOME))

    result = apply_turn_maintenance(state)

    assert result[1].debited == 2
    assert state.kingdoms[1].treasury == -1


# -- apply_turn_maintenance: Hero desertion/standby (Phase 527) -----------


def test_apply_turn_maintenance_pays_a_hero_normally_when_treasury_covers_it():
    state = make_state()
    state.kingdoms[1].treasury = 10
    king = LeaderState(1, 1, "Bradipo I", HOME, is_king=True, alignment=Alignment.GOOD, temper=Temper.CAUTIOUS)
    hero = LeaderState(2, 1, "Adele", HOME, alignment=Alignment.GOOD, temper=Temper.BRAVE)
    state.add_leader(king)
    state.add_leader(hero)

    # Adele (id 2) prices at 1 against this King -- see test_leader_pay_
    # ordinary_hero_uses_the_real_formula's own worked example.
    result = apply_turn_maintenance(state, ScriptedRandom([], choice_indices=[]))

    assert result[1].debited == 1
    assert result[1].deserted_leader_ids == []
    assert result[1].standby_leader_ids == []
    assert hero.kingdom_id == 1
    assert state.kingdoms[1].treasury == 9


def test_apply_turn_maintenance_unpaid_hero_deserts_when_the_roll_beats_liking():
    state = make_state()
    state.kingdoms[1].treasury = 0
    king = LeaderState(1, 1, "Bradipo I", HOME, is_king=True, alignment=Alignment.GOOD, temper=Temper.CAUTIOUS)
    # Indra (id 3) against this King: like=1 (base_cost=2) -- see test_
    # leader_pay_ordinary_hero_uses_the_real_formula's own worked example
    # (same pair). Confirmed below rather than assumed.
    hero = LeaderState(3, 1, "Indra", HOME, alignment=Alignment.GOOD, temper=Temper.CAUTIOUS)
    state.add_leader(king)
    state.add_leader(hero)
    like = hero_liking(state, hero, king)
    assert like == 1

    # _DESERTION_ROLL_VALUES = (-2, -1, 0, 1) -- index 3 rolls the maximum,
    # +1, which is >= like (1) for this specific pair.
    result = apply_turn_maintenance(state, ScriptedRandom([], choice_indices=[3]))

    assert result[1].deserted_leader_ids == [3]
    assert result[1].standby_leader_ids == []
    assert hero.kingdom_id is None
    assert state.kingdoms[1].treasury == 0  # unpaid -- no debit for a deserter


def test_apply_turn_maintenance_unpaid_hero_stays_in_standby_when_the_roll_loses_to_liking():
    state = make_state()
    state.kingdoms[1].treasury = 0
    king = LeaderState(1, 1, "Bradipo I", HOME, is_king=True, alignment=Alignment.GOOD, temper=Temper.CAUTIOUS)
    hero = LeaderState(3, 1, "Indra", HOME, alignment=Alignment.GOOD, temper=Temper.CAUTIOUS)
    state.add_leader(king)
    state.add_leader(hero)
    assert hero_liking(state, hero, king) == 1

    # Index 0 rolls the minimum, -2, which is < like (1) for this pair.
    result = apply_turn_maintenance(state, ScriptedRandom([], choice_indices=[0]))

    assert result[1].deserted_leader_ids == []
    assert result[1].standby_leader_ids == [3]
    assert hero.kingdom_id == 1
    assert state.kingdoms[1].treasury == 0


def test_apply_turn_maintenance_pays_heroes_in_ascending_leader_id_order_until_treasury_runs_out():
    # Enough treasury for the lower-id Hero's own pay only -- the higher
    # leader_id is left to roll for desertion/standby against whatever
    # treasury remains (0), regardless of its own required pay.
    state = make_state()
    king = LeaderState(1, 1, "Bradipo I", HOME, is_king=True, alignment=Alignment.GOOD, temper=Temper.CAUTIOUS)
    first_hero = LeaderState(2, 1, "Adele", HOME, alignment=Alignment.GOOD, temper=Temper.BRAVE)
    second_hero = LeaderState(4, 1, "Elyse", HOME, alignment=Alignment.GOOD, temper=Temper.BRAVE)
    state.add_leader(king)
    state.add_leader(first_hero)
    state.add_leader(second_hero)
    first_cost = required_pay(state, first_hero, king)
    second_cost = required_pay(state, second_hero, king)
    assert second_cost > 0  # sanity: there's something for the second Hero to fail to pay
    state.kingdoms[1].treasury = first_cost

    result = apply_turn_maintenance(state, ScriptedRandom([], choice_indices=[0]))

    assert first_hero.kingdom_id == 1
    assert result[1].debited == first_cost
    assert 4 in (result[1].deserted_leader_ids + result[1].standby_leader_ids)
    assert state.kingdoms[1].treasury == 0


def test_apply_turn_maintenance_missing_king_pays_unconditionally_no_roll_consumed():
    # No King recorded for this kingdom -- required_pay() falls back to 1
    # (permissive default) and no desertion roll can happen (no `like()`
    # to compute); ScriptedRandom([], choice_indices=[]) proves no roll is
    # attempted even though the treasury can't cover it.
    state = make_state()
    state.kingdoms[1].treasury = 0
    hero = LeaderState(2, 1, "Adele", HOME, alignment=Alignment.GOOD, temper=Temper.BRAVE)
    state.add_leader(hero)

    result = apply_turn_maintenance(state, ScriptedRandom([], choice_indices=[]))

    assert result[1].debited == 1
    assert result[1].deserted_leader_ids == []
    assert result[1].standby_leader_ids == []
    assert hero.kingdom_id == 1
    assert state.kingdoms[1].treasury == -1
