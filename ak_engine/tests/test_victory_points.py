"""Tests for turn/victory_points.py -- see its module docstring for the
full derivation (real `outred`/`ofcval` Victory Point decay formula,
Phase 439).
"""

from __future__ import annotations

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.game_state import ArmyState, GameState, KingdomState, LeaderState, ProvinceState
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.office import OFFICE_VALUE, Office
from ak_engine.models.race import Race
from ak_engine.turn.combat import Quality
from ak_engine.turn.victory_points import OUTLOOK_REDUCTION, army_office_victory_points, office_victory_points

HOME = HexCoord(0, 0)
AWAY = HexCoord(1, 1)


def make_state(*, kalign: Alignment, empalign: Alignment) -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, kalign, HOME))
    state.add_kingdom(KingdomState(2, "Emperia", Race.HUMAN, empalign, AWAY))
    state.add_leader(LeaderState(1, 1, "Aldric", HOME, is_king=True))
    state.add_leader(LeaderState(2, 2, "Cassian", AWAY, is_king=True))
    aldric = state.leaders[1]
    aldric.merit_tally.monster_hp_defeated = 10  # Attackia's own King wins Defender
    return state


def test_office_victory_points_zero_before_any_emperor_is_elected():
    state = make_state(kalign=Alignment.GOOD, empalign=Alignment.GOOD)

    assert office_victory_points(state, Office.DEFENDER, 1) == 0.0


def test_office_victory_points_zero_for_a_kingdom_that_doesnt_hold_the_office():
    state = make_state(kalign=Alignment.GOOD, empalign=Alignment.GOOD)
    state.emperor_kingdom_id = 2

    assert office_victory_points(state, Office.DEFENDER, 2) == 0.0  # Attackia's Aldric holds it, not Emperia


def test_office_victory_points_full_value_when_alignment_matches_the_emperor():
    state = make_state(kalign=Alignment.GOOD, empalign=Alignment.GOOD)
    state.emperor_kingdom_id = 2  # Emperia's own King is Emperor

    points = office_victory_points(state, Office.DEFENDER, 1)

    assert points == OFFICE_VALUE[Office.DEFENDER]  # distance 0 -> reduct 0


def test_office_victory_points_reduced_by_alignment_distance():
    # Good (ordinal 1) vs Evil (ordinal 5): distance 4, outred[Good] = 0.12.
    state = make_state(kalign=Alignment.GOOD, empalign=Alignment.EVIL)
    state.emperor_kingdom_id = 2

    points = office_victory_points(state, Office.DEFENDER, 1)

    expected_reduct = min(1.0, OUTLOOK_REDUCTION[Alignment.GOOD] * 4)
    assert points == OFFICE_VALUE[Office.DEFENDER] * (1.0 - expected_reduct)
    assert points < OFFICE_VALUE[Office.DEFENDER]


def test_office_victory_points_capped_at_full_reduction():
    # Divine (ordinal 0) vs Anti-Holy/Hellish (ordinal 6): distance 6,
    # outred[Divine] = 0.20 -> raw reduct 1.2, capped to 1.0 -> zero points.
    state = make_state(kalign=Alignment.DIVINE, empalign=Alignment.ANTI_HOLY)
    state.emperor_kingdom_id = 2

    assert office_victory_points(state, Office.DEFENDER, 1) == 0.0


def test_office_victory_points_emperor_office_itself_awards_full_value_to_its_own_kingdom():
    state = make_state(kalign=Alignment.GOOD, empalign=Alignment.GOOD)
    state.emperor_kingdom_id = 2

    points = office_victory_points(state, Office.EMPEROR, 2)

    assert points == OFFICE_VALUE[Office.EMPEROR]  # same Kingdom as itself -> distance 0


def test_outlook_reduction_covers_every_alignment_and_matches_the_real_outred_table():
    assert set(OUTLOOK_REDUCTION) == set(Alignment)
    # CTBOTH.PAS outred, positionally verbatim against the real outlook
    # ordinal sequence (Heavenly=0..Special=9).
    assert OUTLOOK_REDUCTION[Alignment.DIVINE] == 0.20
    assert OUTLOOK_REDUCTION[Alignment.GOOD] == 0.12
    assert OUTLOOK_REDUCTION[Alignment.DRUID] == 0.15
    assert OUTLOOK_REDUCTION[Alignment.NEUTRAL] == 0.20
    assert OUTLOOK_REDUCTION[Alignment.PAGAN] == 0.15
    assert OUTLOOK_REDUCTION[Alignment.EVIL] == 0.12
    assert OUTLOOK_REDUCTION[Alignment.ANTI_HOLY] == 0.20
    assert OUTLOOK_REDUCTION[Alignment.UNDEAD] == 0.20
    assert OUTLOOK_REDUCTION[Alignment.MECHANICAL] == 0.20
    assert OUTLOOK_REDUCTION[Alignment.SPECIAL] == 0.20


# -- Army-scoped Royal Titles: Airforce/Praetor/Flagship (Phase 633) --------


def _army_state(*, kalign: Alignment, empalign: Alignment) -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, kalign, HOME))
    state.add_kingdom(KingdomState(2, "Emperia", Race.HUMAN, empalign, AWAY))
    state.add_province(ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_army(ArmyState(101, 1, ArmyType.DRAGON_WING, Quality.ELITE, HOME))  # Attackia's own Airforce
    return state


def test_army_office_victory_points_zero_before_any_emperor_is_elected():
    state = _army_state(kalign=Alignment.GOOD, empalign=Alignment.GOOD)

    assert army_office_victory_points(state, Office.AIR_FORCE, 1) == 0.0


def test_army_office_victory_points_zero_for_a_kingdom_that_doesnt_hold_the_office():
    state = _army_state(kalign=Alignment.GOOD, empalign=Alignment.GOOD)
    state.emperor_kingdom_id = 2

    assert army_office_victory_points(state, Office.AIR_FORCE, 2) == 0.0  # Attackia's army holds it, not Emperia


def test_army_office_victory_points_full_value_when_alignment_matches_the_emperor():
    state = _army_state(kalign=Alignment.GOOD, empalign=Alignment.GOOD)
    state.emperor_kingdom_id = 2

    points = army_office_victory_points(state, Office.AIR_FORCE, 1)

    assert points == OFFICE_VALUE[Office.AIR_FORCE]  # distance 0 -> reduct 0


def test_army_office_victory_points_reduced_by_alignment_distance():
    # Same real formula office_victory_points() already uses -- see that
    # function's own analogous test for the worked distance/reduct math.
    state = _army_state(kalign=Alignment.GOOD, empalign=Alignment.EVIL)
    state.emperor_kingdom_id = 2

    points = army_office_victory_points(state, Office.AIR_FORCE, 1)

    expected_reduct = min(1.0, OUTLOOK_REDUCTION[Alignment.GOOD] * 4)
    assert points == OFFICE_VALUE[Office.AIR_FORCE] * (1.0 - expected_reduct)
    assert points < OFFICE_VALUE[Office.AIR_FORCE]


def test_army_office_victory_points_raises_for_a_non_army_scoped_office():
    import pytest

    state = _army_state(kalign=Alignment.GOOD, empalign=Alignment.GOOD)

    with pytest.raises(ValueError):
        army_office_victory_points(state, Office.DEFENDER, 1)
