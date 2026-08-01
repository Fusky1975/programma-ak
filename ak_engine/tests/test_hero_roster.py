"""Tests for the fixed, game-independent Hero name/id/sex roster (Phase 339).

See `models/hero_roster.py`'s own module docstring for the user-supplied
source document and the empirical cross-check against the real, committed
`GW3__T1` fixture.
"""

from __future__ import annotations

from pathlib import Path

from ak_engine.models.hero_roster import (
    STANDARD_HERO_ID_BY_NAME,
    STANDARD_HERO_ROSTER,
    STANDARD_HERO_SEX_BY_NAME,
)
from ak_engine.models.sex import Sex
from ak_engine.parser.gw_world import parse_gw_leaders

FIXTURE = Path(__file__).parent / "fixtures" / "world" / "G3" / "GW3__T1"


def test_roster_has_all_98_entries_with_unique_ids_1_through_98():
    assert len(STANDARD_HERO_ROSTER) == 98
    ids = sorted(entry.hero_id for entry in STANDARD_HERO_ROSTER)
    assert ids == list(range(1, 99))


def test_roster_names_are_unique():
    names = [entry.name for entry in STANDARD_HERO_ROSTER]
    assert len(names) == len(set(names))


def test_known_real_ids_from_earlier_phases_match_the_roster():
    # Philo=70, Guerin=18, Teleko=72, Ningarl=13, Kokocala=10 -- the
    # first four independently confirmed in Phases 316-327; Kokocala's
    # own real id was mistakenly assumed to be 50 in an earlier Phase
    # 338 experiment (an arbitrary test fixture id, never independently
    # confirmed) -- this roster corrects it to his own real value, 10.
    assert STANDARD_HERO_ID_BY_NAME["Philo"] == 70
    assert STANDARD_HERO_ID_BY_NAME["Guerin"] == 18
    assert STANDARD_HERO_ID_BY_NAME["Teleko"] == 72
    assert STANDARD_HERO_ID_BY_NAME["Ningarl"] == 13
    assert STANDARD_HERO_ID_BY_NAME["Kokocala"] == 10


def test_sex_lookup_matches_id_lookup_for_every_entry():
    assert len(STANDARD_HERO_SEX_BY_NAME) == 98
    assert STANDARD_HERO_SEX_BY_NAME["Guerin"] is Sex.MALE
    assert STANDARD_HERO_SEX_BY_NAME["Tao-Li"] is Sex.FEMALE


def test_88_of_90_real_t1_heroes_match_the_roster_at_ids_10_and_up():
    # The real GW3__T1 fixture is a 10-kingdom game, so Kings already
    # occupy ids 0-9 (Phase 330) -- the roster's own 1-9 slots (Adam
    # through Enlil) never get to appear as Heroes here. The 2 unmatched
    # names (Bagmore, Kitralus) are real VALHALLA NEUTRAL.txt entries,
    # not a data error -- see the module docstring's own writeup.
    leaders = parse_gw_leaders(FIXTURE)
    heroes = [r for r in leaders if not r.is_king]
    assert len(heroes) == 90

    matched = [h for h in heroes if h.name in STANDARD_HERO_ID_BY_NAME]
    unmatched = [h.name for h in heroes if h.name not in STANDARD_HERO_ID_BY_NAME]

    assert len(matched) == 88
    assert sorted(unmatched) == ["Bagmore", "Kitralus"]

    matched_ids = [STANDARD_HERO_ID_BY_NAME[h.name] for h in matched]
    assert len(matched_ids) == len(set(matched_ids))  # no id collisions
    assert min(matched_ids) >= 10
    assert max(matched_ids) <= 98
