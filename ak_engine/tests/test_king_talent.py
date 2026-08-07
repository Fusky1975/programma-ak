from __future__ import annotations

import pytest

from ak_engine.models.alignment import Alignment
from ak_engine.models.enums import Ability
from ak_engine.worldgen.king_talent import (
    AUTOMATIC_BONUS_ABILITIES,
    MAX_POINTS_PER_ABILITY,
    MAX_TALENT_POINTS,
    build_king_skill_table,
)


def test_automatic_bonus_abilities_are_melee_archery_and_sage():
    assert set(AUTOMATIC_BONUS_ABILITIES) == {Ability.MELEE, Ability.ARCHERY, Ability.SAGE}


def test_no_allocation_still_carries_the_automatic_bonuses():
    table = build_king_skill_table({}, Alignment.NEUTRAL)

    for ability in Ability:
        skill, aptitude = table.pair_for_ability(ability)
        if ability in AUTOMATIC_BONUS_ABILITIES:
            assert skill == 1
            assert aptitude == 3
        else:
            assert skill == 0
            assert aptitude == 2


def test_allocated_points_add_on_top_of_the_automatic_bonus():
    table = build_king_skill_table({Ability.MELEE: 2, Ability.NECROMANCY: 1}, Alignment.NEUTRAL)

    melee_skill, melee_apt = table.pair_for_ability(Ability.MELEE)
    assert melee_skill == 3  # 2 allocated + 1 automatic
    assert melee_apt == 5

    necro_skill, necro_apt = table.pair_for_ability(Ability.NECROMANCY)
    assert necro_skill == 1  # no automatic bonus for Necromancy
    assert necro_apt == 3


def test_aptitude_is_always_exactly_skill_plus_two():
    table = build_king_skill_table({Ability.TACTICAL: 2, Ability.WHITE: 1}, Alignment.NEUTRAL)

    for ability in Ability:
        skill, aptitude = table.pair_for_ability(ability)
        assert aptitude == skill + 2


def test_divine_king_gets_a_white_magic_bonus_and_zero_necromancy_aptitude():
    table = build_king_skill_table({}, Alignment.DIVINE)

    white_skill, white_apt = table.pair_for_ability(Ability.WHITE)
    assert white_skill == 1
    assert white_apt == 3

    necro_skill, necro_apt = table.pair_for_ability(Ability.NECROMANCY)
    assert necro_skill == 0
    assert necro_apt == 0  # forced to 0, not skill+2


def test_undead_king_gets_a_necromancy_bonus_and_zero_white_magic_aptitude():
    table = build_king_skill_table({}, Alignment.UNDEAD)

    necro_skill, necro_apt = table.pair_for_ability(Ability.NECROMANCY)
    assert necro_skill == 1
    assert necro_apt == 3

    white_skill, white_apt = table.pair_for_ability(Ability.WHITE)
    assert white_skill == 0
    assert white_apt == 0


def test_matches_the_confirmed_real_ak3_t1_k1_undead_king_sample():
    # models/kingdom.py SkillTable's own Phase 21 docstring: an Undead
    # King's real skill line included Necromancy=(3, 5) and White=(0, 0)
    # -- reproduced here via 2 allocated Necromancy points (skill 2) plus
    # the automatic Undead +1 (skill 3), aptitude min(5, 3+2) == 5.
    table = build_king_skill_table({Ability.NECROMANCY: 2}, Alignment.UNDEAD)

    assert table.pair_for_ability(Ability.NECROMANCY) == (3, 5)
    assert table.pair_for_ability(Ability.WHITE) == (0, 0)


def test_aptitude_caps_at_five_even_with_the_automatic_bonus_stacked_on_two_allocated_points():
    table = build_king_skill_table({Ability.SAGE: 2}, Alignment.NEUTRAL)

    skill, aptitude = table.pair_for_ability(Ability.SAGE)
    assert skill == 3  # 2 allocated + 1 automatic
    assert aptitude == 5  # min(5, 3+2) == 5, not 5 by luck


def test_rejects_more_than_four_total_points():
    with pytest.raises(ValueError):
        build_king_skill_table({Ability.TACTICAL: 2, Ability.MARCH: 2, Ability.NAVAL: 1}, Alignment.NEUTRAL)


def test_rejects_more_than_two_points_on_a_single_ability():
    with pytest.raises(ValueError):
        build_king_skill_table({Ability.TACTICAL: 3}, Alignment.NEUTRAL)


def test_rejects_a_negative_point_count():
    with pytest.raises(ValueError):
        build_king_skill_table({Ability.TACTICAL: -1}, Alignment.NEUTRAL)


def test_max_talent_points_and_max_per_ability_match_the_rulebook():
    assert MAX_TALENT_POINTS == 4
    assert MAX_POINTS_PER_ABILITY == 2
