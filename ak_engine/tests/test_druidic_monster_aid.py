"""Tests for turn/druidic_monster_aid.py -- see its module docstring for
the full AKGEN_reverse_engineering_report (2).md SS5 derivation.
"""

from __future__ import annotations

import random

from ak_engine.models.alignment import Alignment
from ak_engine.models.feature import Feature, FeatureType
from ak_engine.models.game_state import GameState
from ak_engine.models.map import HexCoord
from ak_engine.models.monster import Monster
from ak_engine.turn.druidic_monster_aid import (
    DruidicMonsterAssistance,
    find_druidic_monster_assistance,
    monster_effective_alignment,
    monster_join_probability,
    monster_strength_bonus,
)

from _helpers import ScriptedRandom

HOME = HexCoord(0, 0)


# -- monster_effective_alignment (Agent_Align) ------------------------------


def test_monster_effective_alignment_no_walk_when_view_variation_zero():
    assert monster_effective_alignment(0, 0, Alignment.NEUTRAL, 0) is Alignment.NEUTRAL


def test_monster_effective_alignment_skips_the_step_on_an_even_bit_but_keeps_shifting():
    # feature_id=0, monster_id=0 -> q=256=0b100000000 -- its own low 3
    # bits are all 0, so every one of 3 iterations skips the ordinal
    # step (no early exit, still shifts each time) -- stays NEUTRAL.
    assert monster_effective_alignment(0, 0, Alignment.NEUTRAL, 3) is Alignment.NEUTRAL


def test_monster_effective_alignment_phase_726_fix_an_even_bit_no_longer_ends_the_whole_walk():
    # Phase 726 regression case: feature_id=0, monster_id=2 -> q=258=
    # 0b100000010 -- direction -1 (bit 3 unset). Iteration 1: low bit 0
    # (even) -> skip the step, but still shift (q -> 129). Iteration 2:
    # low bit 1 (odd) -> apply one step. Real result: NEUTRAL(3) -> 2 =
    # Alignment.DRUID. The pre-Phase-726 bug would have permanently
    # broken out of the loop on iteration 1's even bit, applying zero
    # steps and wrongly staying at NEUTRAL.
    assert monster_effective_alignment(0, 2, Alignment.NEUTRAL, 2) is Alignment.DRUID


def test_monster_effective_alignment_walks_multiple_steps_direction_positive():
    # feature_id=0, monster_id=11 -> q=267 (0b100001011): q&8 set ->
    # direction +1; two full odd-q steps before q goes even: NEUTRAL(3)
    # -> PAGAN(4) -> EVIL(5).
    assert monster_effective_alignment(0, 11, Alignment.NEUTRAL, 2) is Alignment.EVIL


def test_monster_effective_alignment_clamps_at_the_mechanical_upper_bound():
    # Same feature/monster id pair as the positive-direction test above
    # (direction +1), started already at the walk's own upper clamp
    # (Alignment.MECHANICAL, ordinal 8) -- stays there, never reaching
    # Alignment.SPECIAL (ordinal 9).
    assert monster_effective_alignment(0, 11, Alignment.MECHANICAL, 1) is Alignment.MECHANICAL


def test_monster_effective_alignment_clamps_at_the_divine_lower_bound():
    # feature_id=1, monster_id=0 -> q=257 (odd, q&8 unset) -> direction
    # -1, starting already at Alignment.DIVINE (ordinal 0) -- stays put.
    assert monster_effective_alignment(1, 0, Alignment.DIVINE, 1) is Alignment.DIVINE


# -- monster_join_probability -----------------------------------------------


def test_monster_join_probability_purely_druidic_against_a_distant_enemy_is_certain():
    # d_D == 0 (effective alignment IS Druidic) -- always eligible.
    assert monster_join_probability(Alignment.DRUID, Alignment.EVIL) == 1.0


def test_monster_join_probability_worked_example():
    # effective=Neutral (ordinal 3), enemy=Undead (ordinal 7): d_D=1,
    # d_E=4 -> 1 - 1/4 == 0.75.
    assert monster_join_probability(Alignment.NEUTRAL, Alignment.UNDEAD) == 0.75


def test_monster_join_probability_zero_when_no_more_druidic_than_enemy_leaning():
    # effective's own distance from Druidic (1) is not smaller than its
    # distance from an enemy who shares that same effective alignment
    # (0) -- not eligible.
    assert monster_join_probability(Alignment.NEUTRAL, Alignment.NEUTRAL) == 0.0


def test_monster_join_probability_druidic_vs_druidic_is_never_eligible():
    # Two Druidic Kingdoms fighting each other -- d_D == d_E == 0, the
    # source's own degenerate case, handled without a division by zero.
    assert monster_join_probability(Alignment.DRUID, Alignment.DRUID) == 0.0


# -- monster_strength_bonus ---------------------------------------------------


def test_monster_strength_bonus_gold_dragon_worked_example():
    # MONSTER_RUNTIME_PROFILE[Monster.GO_DRAGON]: hp=40, melee=12, missile=15.
    assert monster_strength_bonus(40, 12, 15) == 21


def test_monster_strength_bonus_floors_the_division():
    assert monster_strength_bonus(10, 1, 1) == 0  # (10*2)//50 == 0


# -- find_druidic_monster_assistance -----------------------------------------


def _guarded_feature(feature_id: int, monster: Monster, *, looted: bool = False, magically_hidden: bool = False) -> Feature:
    return Feature(feature_id, HOME, FeatureType.CAVE, guardian_monster=monster, looted=looted, magically_hidden=magically_hidden)


def test_find_druidic_monster_assistance_grants_a_bonus_on_a_successful_roll():
    state = GameState()
    state.add_feature(_guarded_feature(1, Monster.GO_DRAGON))

    # GO_DRAGON: base_view=GOOD (ordinal 1), view_variation=1.
    # feature_id=1, monster_id=Monster.GO_DRAGON.value(9) -> q=266
    # (0b100001010), even -> effective alignment stays GOOD (no walk).
    # Enemy Evil (ordinal 5): d_D=|1-2|=1, d_E=|1-5|=4 -> prob 0.75.
    rng = ScriptedRandom([0.5], choice_indices=[])
    rng.randrange = lambda n: 2  # deterministic column pick, verified separately below

    result = find_druidic_monster_assistance(state, HOME, Alignment.EVIL, line_length=5, rng=rng)

    # Gold Dragon's own worked-example bonus, plus (Phase 657) its identity.
    assert result == {2: DruidicMonsterAssistance(strength_bonus=21, monster=Monster.GO_DRAGON, feature_id=1)}


def test_find_druidic_monster_assistance_skips_ineligible_monsters():
    state = GameState()
    # Same feature as above, but pitted against Good (its own effective
    # alignment) -- d_D(1) >= d_E(0), never eligible, no roll consumed.
    state.add_feature(_guarded_feature(1, Monster.GO_DRAGON))

    result = find_druidic_monster_assistance(state, HOME, Alignment.GOOD, line_length=5, rng=ScriptedRandom([]))

    assert result == {}


def test_find_druidic_monster_assistance_skips_a_failed_roll():
    state = GameState()
    state.add_feature(_guarded_feature(1, Monster.GO_DRAGON))

    # Same 0.75 chance as the success test above; 0.9 fails it.
    result = find_druidic_monster_assistance(state, HOME, Alignment.EVIL, line_length=5, rng=ScriptedRandom([0.9]))

    assert result == {}


def test_find_druidic_monster_assistance_skips_looted_features():
    state = GameState()
    state.add_feature(_guarded_feature(1, Monster.GO_DRAGON, looted=True))

    result = find_druidic_monster_assistance(state, HOME, Alignment.EVIL, line_length=5, rng=ScriptedRandom([]))

    assert result == {}


def test_find_druidic_monster_assistance_skips_a_magically_hidden_feature():
    # Phase 1194 bug fix: this used to omit magically_hidden entirely,
    # unlike the equivalent guardian-eligibility filters elsewhere
    # (monster_raids.py resolve_province_raids(), rumor.py find_rumor_
    # candidates()) -- a Hide-Feature'd, supposedly-undetectable
    # guardian could still roll to join a battle.
    state = GameState()
    state.add_feature(_guarded_feature(1, Monster.GO_DRAGON, magically_hidden=True))

    result = find_druidic_monster_assistance(state, HOME, Alignment.EVIL, line_length=5, rng=ScriptedRandom([]))

    assert result == {}


def test_find_druidic_monster_assistance_skips_a_feature_with_no_guardian():
    state = GameState()
    state.add_feature(Feature(1, HOME, FeatureType.CAVE, guardian_monster=None))

    result = find_druidic_monster_assistance(state, HOME, Alignment.EVIL, line_length=5, rng=ScriptedRandom([]))

    assert result == {}


def test_find_druidic_monster_assistance_ignores_features_at_a_different_province():
    state = GameState()
    state.add_feature(_guarded_feature(1, Monster.GO_DRAGON))

    result = find_druidic_monster_assistance(
        state, HexCoord(9, 9), Alignment.EVIL, line_length=5, rng=ScriptedRandom([])
    )

    assert result == {}


def test_find_druidic_monster_assistance_second_monster_on_the_same_column_is_discarded():
    # Two features, both guarded by Gold Dragons (same eligibility/roll
    # shape), scanned in ascending feature_id order. Both succeed their
    # own roll and both land on column 0 -- the second (feature_id=2) is
    # discarded outright, no retry onto another column.
    state = GameState()
    state.add_feature(_guarded_feature(1, Monster.GO_DRAGON))
    state.add_feature(_guarded_feature(2, Monster.GO_DRAGON))

    rng = ScriptedRandom([0.1, 0.1])
    rng.randrange = lambda n: 0

    result = find_druidic_monster_assistance(state, HOME, Alignment.EVIL, line_length=5, rng=rng)

    # feature_id=1's own monster claimed column 0 first -- feature_id
    # confirms it's the *first* feature's monster, not the second's.
    assert result == {0: DruidicMonsterAssistance(strength_bonus=21, monster=Monster.GO_DRAGON, feature_id=1)}


def test_find_druidic_monster_assistance_scans_in_ascending_feature_id_order():
    # Registered out of id order in GameState.features (dict insertion
    # order) -- the scan must still process feature_id=1 before
    # feature_id=5, proven by which one wins the column-0 collision.
    state = GameState()
    state.add_feature(_guarded_feature(5, Monster.GO_DRAGON))
    state.add_feature(_guarded_feature(1, Monster.GO_DRAGON))

    rng = ScriptedRandom([0.1, 0.1])
    rng.randrange = lambda n: 0

    result = find_druidic_monster_assistance(state, HOME, Alignment.EVIL, line_length=5, rng=rng)

    # feature_id=1's own monster claimed column 0 first, confirmed by its
    # own feature_id surviving in the result (Phase 657), not feature_id=5's.
    assert result == {0: DruidicMonsterAssistance(strength_bonus=21, monster=Monster.GO_DRAGON, feature_id=1)}
