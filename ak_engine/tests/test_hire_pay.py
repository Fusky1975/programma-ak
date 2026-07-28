from __future__ import annotations

from ak_engine.models.alignment import Alignment
from ak_engine.models.game_state import LeaderState
from ak_engine.models.map import HexCoord
from ak_engine.models.temper import Temper
from ak_engine.turn.hire_pay import (
    RARE_ALIGNMENT_EXCEPTION_CHANCE,
    RARE_ALIGNMENT_EXCEPTION_PAY,
    required_pay,
    roll_rare_alignment_exception,
)

from _helpers import ScriptedRandom

HOME = HexCoord(3, 9)


def _leader(*, alignment: Alignment | None = None, temper: Temper | None = None, is_king: bool = False) -> LeaderState:
    return LeaderState(1, 1, "Someone", HOME, is_king=is_king, alignment=alignment, temper=temper)


def test_required_pay_same_alignment_same_temper_is_cheapest():
    hero = _leader(alignment=Alignment.GOOD, temper=Temper.BRAVE)
    king = _leader(alignment=Alignment.GOOD, temper=Temper.BRAVE, is_king=True)

    assert required_pay(hero, king) == 1


def test_required_pay_same_alignment_different_temper_has_no_effect():
    # Phase 163: temper only amplifies an *existing* alignment gap --
    # exact alignment match means a temper mismatch alone doesn't move
    # the price (this is how temper's weight ends up "about half" of
    # alignment's own, per the user's own feedback).
    hero = _leader(alignment=Alignment.GOOD, temper=Temper.BRAVE)
    king = _leader(alignment=Alignment.GOOD, temper=Temper.COWARDLY, is_king=True)

    assert required_pay(hero, king) == 1


def test_required_pay_distance_one_same_temper():
    # GOOD(1) vs DRUID(2) -- real ordinal distance 1.
    hero = _leader(alignment=Alignment.GOOD, temper=Temper.BRAVE)
    king = _leader(alignment=Alignment.DRUID, temper=Temper.BRAVE, is_king=True)

    assert required_pay(hero, king) == 2


def test_required_pay_distance_one_different_temper_adds_one():
    # Once some alignment friction exists (distance >= 1), a temper
    # mismatch does amplify it, same +1 as Phase 162's original design.
    hero = _leader(alignment=Alignment.GOOD, temper=Temper.BRAVE)
    king = _leader(alignment=Alignment.DRUID, temper=Temper.COWARDLY, is_king=True)

    assert required_pay(hero, king) == 3


def test_required_pay_distance_two_different_temper_caps_at_four():
    # GOOD(1) vs NEUTRAL(3) -- real ordinal distance 2 -> base 3, +1 temper.
    hero = _leader(alignment=Alignment.GOOD, temper=Temper.BRAVE)
    king = _leader(alignment=Alignment.NEUTRAL, temper=Temper.COWARDLY, is_king=True)

    assert required_pay(hero, king) == 4


def test_required_pay_good_king_pagan_hero_is_unhireable():
    # The user's own hard data point: real ordinal distance 3 -> 5 gold,
    # above the 4-gold Hire offer ceiling ("generally cannot hire").
    hero = _leader(alignment=Alignment.PAGAN, temper=Temper.BRAVE)
    king = _leader(alignment=Alignment.GOOD, temper=Temper.BRAVE, is_king=True)

    assert required_pay(hero, king) == 5


def test_required_pay_distance_beyond_three_still_caps_at_five():
    # DIVINE(0) vs SPECIAL(9) -- the widest possible real gap.
    hero = _leader(alignment=Alignment.SPECIAL, temper=Temper.BERSERK)
    king = _leader(alignment=Alignment.DIVINE, temper=Temper.COWARDLY, is_king=True)

    assert required_pay(hero, king) == 5


def test_required_pay_defaults_to_cheapest_when_hero_alignment_missing():
    hero = _leader(alignment=None, temper=Temper.BRAVE)
    king = _leader(alignment=Alignment.PAGAN, temper=Temper.BRAVE, is_king=True)

    assert required_pay(hero, king) == 1


def test_required_pay_defaults_to_cheapest_when_king_is_none():
    hero = _leader(alignment=Alignment.PAGAN, temper=Temper.BERSERK)

    assert required_pay(hero, None) == 1


def test_required_pay_defaults_to_same_temper_when_temper_missing():
    hero = _leader(alignment=Alignment.GOOD, temper=None)
    king = _leader(alignment=Alignment.GOOD, temper=Temper.BRAVE, is_king=True)

    assert required_pay(hero, king) == 1


# -- Phase 264: "In rare occasioni..." bypass --------------------------------


def test_rare_alignment_exception_chance_is_the_user_specified_fifteen_percent():
    assert RARE_ALIGNMENT_EXCEPTION_CHANCE == 0.15


def test_rare_alignment_exception_pay_is_the_hire_offer_ceiling():
    assert RARE_ALIGNMENT_EXCEPTION_PAY == 4


def test_roll_rare_alignment_exception_succeeds_under_the_threshold():
    rng = ScriptedRandom([0.14])
    assert roll_rare_alignment_exception(rng) is True


def test_roll_rare_alignment_exception_fails_at_or_above_the_threshold():
    rng = ScriptedRandom([0.15])
    assert roll_rare_alignment_exception(rng) is False
