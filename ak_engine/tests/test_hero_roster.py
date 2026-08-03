"""Tests for the fixed, game-independent Hero name roster (Phase 366 rewrite of Phase 339).

See `models/hero_roster.py`'s own module docstring for the `LNAMES.PAS`
source and the empirical re-verification against the real, committed
`GW3__T1` fixture.
"""

from __future__ import annotations

from pathlib import Path

from ak_engine.models.hero_roster import (
    DEFAULT_FEMALE_ID_RANGE,
    LEADER_COUNT_BY_GAME_VERSION,
    STANDARD_HERO_ID_BY_NAME,
    STANDARD_HERO_ROSTER,
    STANDARD_HERO_SEX_BY_NAME,
    default_hero_sex,
)
from ak_engine.models.sex import Sex
from ak_engine.parser.gw_world import parse_gw_leaders

FIXTURE = Path(__file__).parent / "fixtures" / "world" / "G3" / "GW3__T1"


def test_roster_has_all_255_entries_with_unique_ids_0_through_254():
    assert len(STANDARD_HERO_ROSTER) == 255
    assert sorted(STANDARD_HERO_ROSTER) == list(range(255))


def test_leader_counts_by_game_version_match_the_confirmed_values():
    assert LEADER_COUNT_BY_GAME_VERSION == {
        "game_version_3_or_earlier": 100,
        "game_version_4_or_later_Arcanes_V": 175,
        "game_version_4_or_later_other_standard_types": 250,
    }


def test_known_real_ids_from_earlier_phases_still_match_the_roster():
    # Philo=70, Guerin=18, Teleko=72, Ningarl=13, Kokocala=10 -- confirmed
    # in Phases 316-327/338/339, all still correct in the real LNAMES.PAS
    # data.
    assert STANDARD_HERO_ID_BY_NAME["Philo"] == 70
    assert STANDARD_HERO_ID_BY_NAME["Guerin"] == 18
    assert STANDARD_HERO_ID_BY_NAME["Teleko"] == 72
    assert STANDARD_HERO_ID_BY_NAME["Ningarl"] == 13
    assert STANDARD_HERO_ID_BY_NAME["Kokocala"] == 10


def test_phase_339_table_errors_are_corrected():
    # Ids 0-3 were unverifiable guesses (Adam/Eve/Abel/...) in Phase 339's
    # own table -- the real LNAMES.PAS values are Alanus/Bubka/Cecil/
    # Daedona. Id 75 was wrongly "Atlas"; the real value "Bagmore" is
    # itself a genuine GW3__T1 Hero name, not a Valhalla arrival.
    assert STANDARD_HERO_ROSTER[0] == "Alanus"
    assert STANDARD_HERO_ROSTER[1] == "Bubka"
    assert STANDARD_HERO_ROSTER[2] == "Cecil"
    assert STANDARD_HERO_ROSTER[3] == "Daedona"
    assert STANDARD_HERO_ROSTER[75] == "Bagmore"


def test_duplicate_names_keep_their_first_lower_id_in_the_reverse_lookup():
    # Gabriel (46, 212) and Ishtar (57, 231) are LNAMES.PAS's own two real
    # duplicate-spelling pairs; only ids 46/57 are in range for every game
    # version, so the reverse lookup prefers them.
    assert STANDARD_HERO_ID_BY_NAME["Gabriel"] == 46
    assert STANDARD_HERO_ID_BY_NAME["Ishtar"] == 57
    assert STANDARD_HERO_ROSTER[212] == "Gabriel"
    assert STANDARD_HERO_ROSTER[231] == "Ishtar"


def test_default_hero_sex_matches_the_confirmed_80_95_female_band():
    assert list(DEFAULT_FEMALE_ID_RANGE) == list(range(80, 96))
    assert default_hero_sex(79) is Sex.MALE
    assert default_hero_sex(80) is Sex.FEMALE
    assert default_hero_sex(95) is Sex.FEMALE
    assert default_hero_sex(96) is Sex.MALE
    assert default_hero_sex(0) is Sex.MALE


def test_sex_lookup_corrects_two_of_phase_339s_own_wrong_guesses():
    # Isis (89) and Kishijoten (93) are both in the 80-95 default-Female
    # band, but Phase 339's own hand-typed table marked both MALE.
    assert STANDARD_HERO_SEX_BY_NAME["Isis"] is Sex.FEMALE
    assert STANDARD_HERO_SEX_BY_NAME["Kishijoten"] is Sex.FEMALE
    assert STANDARD_HERO_SEX_BY_NAME["Guerin"] is Sex.MALE
    assert STANDARD_HERO_SEX_BY_NAME["Tao-Li"] is Sex.MALE  # id 32, outside the female band


def test_89_of_90_real_t1_heroes_match_the_roster_at_ids_10_through_98():
    # The real GW3__T1 fixture is a 10-kingdom game, so Kings already
    # occupy ids 0-9 (Phase 330). The one remaining unmatched name,
    # Kitralus, is confirmed absent from every one of LNAMES.PAS's 255
    # entries -- a real VALHALLA NEUTRAL.txt visitor in the reserved
    # id-99 slot, not a data error. This strictly improves on Phase 339's
    # own 88/90 (two gap-filling guesses, one of which -- Bagmore -- is
    # now known to have been a real roster entry all along).
    leaders = parse_gw_leaders(FIXTURE)
    heroes = [r for r in leaders if not r.is_king]
    assert len(heroes) == 90

    matched = [h for h in heroes if h.name in STANDARD_HERO_ID_BY_NAME]
    unmatched = [h.name for h in heroes if h.name not in STANDARD_HERO_ID_BY_NAME]

    assert len(matched) == 89
    assert unmatched == ["Kitralus"]
    assert "Kitralus" not in STANDARD_HERO_ROSTER.values()

    matched_ids = sorted(STANDARD_HERO_ID_BY_NAME[h.name] for h in matched)
    assert len(matched_ids) == len(set(matched_ids))  # no id collisions
    assert matched_ids == list(range(10, 99))  # one unbroken run, zero gaps
