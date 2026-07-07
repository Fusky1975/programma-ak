from __future__ import annotations

import random

from ak_engine.models.map import HexCoord
from ak_engine.turn.multiple_contingents import (
    Attacker,
    eligible_to_unite,
    group_attackers_into_battles,
    roll_unite_for_battle,
)

ORIGIN_A = HexCoord(1, 1)
ORIGIN_B = HexCoord(9, 9)


def test_eligible_to_unite_same_king():
    a = Attacker(leader_id=1, kingdom_id=5, origin_province=ORIGIN_A)
    b = Attacker(leader_id=2, kingdom_id=5, origin_province=ORIGIN_B)
    assert eligible_to_unite(a, b, allied_kingdoms=set())


def test_eligible_to_unite_allied_kings():
    a = Attacker(leader_id=1, kingdom_id=5, origin_province=ORIGIN_A)
    b = Attacker(leader_id=2, kingdom_id=6, origin_province=ORIGIN_B)
    assert eligible_to_unite(a, b, allied_kingdoms={frozenset({5, 6})})


def test_not_eligible_when_unrelated_kingdoms():
    a = Attacker(leader_id=1, kingdom_id=5, origin_province=ORIGIN_A)
    b = Attacker(leader_id=2, kingdom_id=7, origin_province=ORIGIN_B)
    assert not eligible_to_unite(a, b, allied_kingdoms={frozenset({5, 6})})


def test_roll_unite_uses_higher_chance_for_same_origin():
    a = Attacker(leader_id=1, kingdom_id=5, origin_province=ORIGIN_A)
    b_same = Attacker(leader_id=2, kingdom_id=5, origin_province=ORIGIN_A)
    b_diff = Attacker(leader_id=3, kingdom_id=5, origin_province=ORIGIN_B)

    rng = random.Random()
    rng.random = lambda: 0.5  # between the two documented chances (0.30 < 0.5 < 0.85)

    assert roll_unite_for_battle(a, b_same, rng) is True
    assert roll_unite_for_battle(a, b_diff, rng) is False


def test_group_attackers_same_king_same_origin_unite():
    attackers = [
        Attacker(leader_id=1, kingdom_id=5, origin_province=ORIGIN_A),
        Attacker(leader_id=2, kingdom_id=5, origin_province=ORIGIN_A),
    ]
    rng = random.Random()
    rng.random = lambda: 0.0  # always succeeds

    groups = group_attackers_into_battles(attackers, allied_kingdoms=set(), rng=rng)

    assert len(groups) == 1
    assert len(groups[0]) == 2


def test_group_attackers_unrelated_kingdoms_always_separate():
    attackers = [
        Attacker(leader_id=1, kingdom_id=5, origin_province=ORIGIN_A),
        Attacker(leader_id=2, kingdom_id=99, origin_province=ORIGIN_A),
    ]
    rng = random.Random()
    rng.random = lambda: 0.0  # would always succeed if eligible, but they aren't

    groups = group_attackers_into_battles(attackers, allied_kingdoms=set(), rng=rng)

    assert len(groups) == 2
