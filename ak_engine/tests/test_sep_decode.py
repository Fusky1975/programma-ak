"""Tests for turn/sep_decode.py -- see its module docstring for the full
Special Encounter Plan (rulebook [5.10]) decode/Plan_Intent derivation.
"""

from __future__ import annotations

from ak_engine.models.enums import Maneuver, Spell
from ak_engine.models.game_state import GameState
from ak_engine.models.plan import PlanSegment
from ak_engine.models.treasure import Treasure
from ak_engine.turn.search_decode import SearchTactic
from ak_engine.turn.sep_decode import (
    decode_special_encounter_plan,
    plan_intent,
    sep_accepts_challenge,
    sep_is_aggressive,
)

# -- decode_special_encounter_plan() -- against every real SP: value found
# across all 20 real K1 move-submission samples (Desktop/Gioco/Gioco
# Chatgpt/AK3__T*.K1, Desktop/Gioco/Esempi turni/SE3__T*.K1), hand-decoded
# in the module docstring.


def _segment(*sp: int) -> PlanSegment:
    return PlanSegment(plan_start=0, plan_end=4, sp=sp)


def test_decode_special_encounter_plan_empty():
    assert decode_special_encounter_plan(_segment(-1)) == []


def test_decode_special_encounter_plan_flee_only():
    assert decode_special_encounter_plan(_segment(10, -1)) == [SearchTactic(Maneuver.FLEE)]


def test_decode_special_encounter_plan_flee_then_cast():
    assert decode_special_encounter_plan(_segment(10, 0, 24, -1)) == [
        SearchTactic(Maneuver.FLEE),
        SearchTactic(Maneuver.CAST, sub_object=24),
    ]


def test_decode_special_encounter_plan_flee_cast_melee():
    assert decode_special_encounter_plan(_segment(10, 0, 24, 9, -1)) == [
        SearchTactic(Maneuver.FLEE),
        SearchTactic(Maneuver.CAST, sub_object=24),
        SearchTactic(Maneuver.MELEE),
    ]


def test_decode_special_encounter_plan_three_casts_then_melee():
    assert decode_special_encounter_plan(_segment(0, 20, 0, 3, 0, 7, 9, -1)) == [
        SearchTactic(Maneuver.CAST, sub_object=20),
        SearchTactic(Maneuver.CAST, sub_object=3),
        SearchTactic(Maneuver.CAST, sub_object=7),
        SearchTactic(Maneuver.MELEE),
    ]


def test_decode_special_encounter_plan_two_casts_fire_arrow_melee():
    assert decode_special_encounter_plan(_segment(0, 28, 0, 7, 8, 9, -1)) == [
        SearchTactic(Maneuver.CAST, sub_object=28),
        SearchTactic(Maneuver.CAST, sub_object=7),
        SearchTactic(Maneuver.SHOOT),
        SearchTactic(Maneuver.MELEE),
    ]


def test_decode_special_encounter_plan_two_casts_then_melee():
    assert decode_special_encounter_plan(_segment(0, 28, 0, 7, 9, -1)) == [
        SearchTactic(Maneuver.CAST, sub_object=28),
        SearchTactic(Maneuver.CAST, sub_object=7),
        SearchTactic(Maneuver.MELEE),
    ]


# -- plan_intent() -- RUMORS.PAS Plan_Intent(), cross-checked by hand
# against every one of the 7 real decoded sequences above.


def test_plan_intent_empty_plan_defaults_to_melee():
    # IF int = CNone THEN int:= CMelee -- the real function's own empty-
    # input fallback, not a guessed "default SEP" formula.
    assert plan_intent([]) is Maneuver.MELEE


def test_plan_intent_flee_first_is_flee_regardless_of_what_follows():
    tactics = [SearchTactic(Maneuver.FLEE), SearchTactic(Maneuver.CAST, sub_object=24), SearchTactic(Maneuver.MELEE)]
    assert plan_intent(tactics) is Maneuver.FLEE


def test_plan_intent_cast_of_a_non_exempt_spell_is_melee():
    tactics = [
        SearchTactic(Maneuver.CAST, sub_object=int(Spell.SPIRITWRACK)),
        SearchTactic(Maneuver.CAST, sub_object=int(Spell.HOLY_SYMBOL)),
        SearchTactic(Maneuver.CAST, sub_object=int(Spell.HAND_OF_DEATH)),
        SearchTactic(Maneuver.MELEE),
    ]
    assert plan_intent(tactics) is Maneuver.MELEE


def test_plan_intent_cast_gate_demon_then_hand_of_death_fire_arrow_melee_is_melee():
    tactics = [
        SearchTactic(Maneuver.CAST, sub_object=int(Spell.GATE_DEMON)),
        SearchTactic(Maneuver.CAST, sub_object=int(Spell.HAND_OF_DEATH)),
        SearchTactic(Maneuver.SHOOT),
        SearchTactic(Maneuver.MELEE),
    ]
    assert plan_intent(tactics) is Maneuver.MELEE


def test_plan_intent_scout_is_a_no_op_and_scan_continues():
    tactics = [SearchTactic(Maneuver.SCOUT), SearchTactic(Maneuver.MELEE)]
    assert plan_intent(tactics) is Maneuver.MELEE


def test_plan_intent_talk_fulfill_give_all_classify_as_talk():
    assert plan_intent([SearchTactic(Maneuver.TALK)]) is Maneuver.TALK
    assert plan_intent([SearchTactic(Maneuver.FULFILL)]) is Maneuver.TALK
    assert plan_intent([SearchTactic(Maneuver.GIVE)]) is Maneuver.TALK


def test_plan_intent_steal_classifies_as_steal():
    assert plan_intent([SearchTactic(Maneuver.STEAL)]) is Maneuver.STEAL


def test_plan_intent_say_as_last_tactic_is_talk():
    tactics = [SearchTactic(Maneuver.SCOUT), SearchTactic(Maneuver.SAY, say_text="Greetings")]
    assert plan_intent(tactics) is Maneuver.TALK


def test_plan_intent_say_followed_by_more_tactics_is_a_no_op():
    tactics = [SearchTactic(Maneuver.SAY, say_text="Greetings"), SearchTactic(Maneuver.MELEE)]
    assert plan_intent(tactics) is Maneuver.MELEE


def test_plan_intent_cast_invisibility_charm_augur_combat_are_exempt():
    for spell in (Spell.INVISIBILITY, Spell.CHARM, Spell.AUGUR_COMBAT):
        tactics = [SearchTactic(Maneuver.CAST, sub_object=int(spell)), SearchTactic(Maneuver.SCOUT)]
        assert plan_intent(tactics) is Maneuver.MELEE  # falls through to the empty-scan default


def test_plan_intent_use_mi_charm_wand_is_exempt_with_real_state():
    state = GameState()
    item = state.add_item(Treasure.WAND_CHARM, owner_leader_id=1)
    tactics = [SearchTactic(Maneuver.USE_MI, sub_object=item.item_id), SearchTactic(Maneuver.SCOUT)]

    assert plan_intent(tactics, state) is Maneuver.MELEE  # exempt item is a no-op; falls through to default


def test_plan_intent_use_mi_other_wand_is_aggressive_with_real_state():
    state = GameState()
    item = state.add_item(Treasure.WAND_FIREBALL, owner_leader_id=1)
    tactics = [SearchTactic(Maneuver.USE_MI, sub_object=item.item_id)]

    assert plan_intent(tactics, state) is Maneuver.MELEE


def test_plan_intent_use_mi_without_state_falls_back_to_aggressive():
    tactics = [SearchTactic(Maneuver.USE_MI, sub_object=1)]
    assert plan_intent(tactics, state=None) is Maneuver.MELEE


# -- sep_is_aggressive() / sep_accepts_challenge() --


def test_sep_is_aggressive_true_for_a_real_offensive_plan():
    tactics = [SearchTactic(Maneuver.CAST, sub_object=int(Spell.GATE_DEMON)), SearchTactic(Maneuver.MELEE)]
    assert sep_is_aggressive(tactics) is True
    assert sep_accepts_challenge(tactics) is True


def test_sep_is_aggressive_false_when_flee_appears_anywhere_even_after_an_aggressive_tactic():
    # Plan_Intent() alone would reduce [Melee, Flee] to CMelee (it stops
    # at the first weighted tactic) -- but rulebook [5.10] says Flee
    # "in un punto qualsiasi" means never voluntarily challenging.
    tactics = [SearchTactic(Maneuver.MELEE), SearchTactic(Maneuver.FLEE)]
    assert plan_intent(tactics) is Maneuver.MELEE  # the raw reduction, for contrast
    assert sep_is_aggressive(tactics) is False


def test_sep_accepts_challenge_false_only_when_flee_is_the_first_tactic():
    # [Flee, Melee]: Plan_Intent() reduces to CFlee from the very first
    # tactic (the WHILE loop stops immediately) -- accepts() is False.
    tactics = [SearchTactic(Maneuver.FLEE), SearchTactic(Maneuver.MELEE)]
    assert plan_intent(tactics) is Maneuver.FLEE
    assert sep_accepts_challenge(tactics) is False


def test_sep_accepts_challenge_true_for_an_empty_plan():
    assert sep_accepts_challenge([]) is True
