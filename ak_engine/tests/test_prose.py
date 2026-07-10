from __future__ import annotations

import pytest

from ak_engine.report.prose import render

from _helpers import ScriptedRandom


def test_underscore_becomes_a_literal_space():
    assert render("bored_with_you") == "bored with you"


def test_random_choice_picks_left_below_half():
    assert render("ran/Rswam", rng=ScriptedRandom([0.1])) == "ran"


def test_random_choice_picks_right_at_or_above_half():
    assert render("ran/Rswam", rng=ScriptedRandom([0.5])) == "swam"


def test_random_choice_treats_an_underscore_joined_phrase_as_one_word():
    # "_" must still be literal when /R's word-boundary scan runs (see
    # module docstring on staged ordering) -- "bored_with" counts as a
    # single word choice, not just "bored".
    assert render("tired/Rbored_with", rng=ScriptedRandom([0.9])) == "bored with"


def test_random_choice_resolves_multiple_occurrences_left_to_right():
    rng = ScriptedRandom([0.1, 0.9])  # first: left; second: right
    assert render("ran/Rswam and jumped/Rflew", rng=rng) == "ran and flew"


def test_unsupported_choice_marker_raises_not_implemented():
    with pytest.raises(NotImplementedError):
        render("a{ferry/Sboat}", rng=ScriptedRandom([0.1]))


def test_optional_inclusion_excludes_below_half():
    assert render("a {very }big dog", rng=ScriptedRandom([0.1])) == "a big dog"


def test_optional_inclusion_includes_at_or_above_half():
    assert render("a {very }big dog", rng=ScriptedRandom([0.5])) == "a very big dog"


def test_optional_inclusion_resolves_multiple_blocks_in_order():
    rng = ScriptedRandom([0.1, 0.9])  # first block excluded, second included
    assert render("a {big }dog {barked}here", rng=rng) == "a dog barkedhere"


def test_optional_inclusion_unmatched_brace_raises():
    with pytest.raises(ValueError):
        render("a {very big dog", rng=ScriptedRandom([0.1]))


def test_placeholder_substitution_with_no_special_symbols():
    assert render("< patrolled @ and the surrounding provinces for enemy characters.", {"@": "the Dolphin Sea"}) == (
        "< patrolled the Dolphin Sea and the surrounding provinces for enemy characters."
    )


def test_placeholder_substitution_leaves_unmapped_symbols_untouched():
    assert render("< wielded > \\.", {}) == "< wielded > \\."


def test_placeholder_substitution_prefers_longer_keys_at_the_same_position():
    # At the position where "@2" begins, the longer key must win -- an
    # incorrect shortest-first scan would match "@" instead and leave a
    # stray "2" in the output.
    assert render("@2", {"@": "Attackia", "@2": "Defendia"}) == "Defendia"


def test_indefinite_article_chooses_an_before_a_vowel():
    assert render("^A elephant") == "an elephant"


def test_indefinite_article_chooses_a_before_a_consonant():
    assert render("^A dungeon") == "a dungeon"


def test_indefinite_article_peeks_past_a_substituted_value():
    assert render("^A @", {"@": "Elven ruin"}) == "an Elven ruin"


def test_full_pipeline_renders_a_real_say_pas_template():
    # RUMORS.PAS _LPOwns (line 446): "The {scenic/Rrich }province of @
    # belongs/Rowes_allegiance to thee/Ryour_Majesty."
    template = "The {scenic/Rrich }province of @ belongs/Rowes_allegiance to thee/Ryour_Majesty."
    # /R picks: scenic/rich -> right (rich); belongs/owes -> right (owes);
    # thee/your_Majesty -> right (your_Majesty). Then {...}: included.
    rng = ScriptedRandom([0.9, 0.9, 0.9, 0.9])
    result = render(template, {"@": "the Dolphin Sea"}, rng=rng)
    assert result == "The rich province of the Dolphin Sea owes allegiance to your Majesty."


def test_full_pipeline_renders_a_real_say_pas_template_minimal_branch():
    # Same template, opposite choices: scenic/rich -> left; belongs/owes ->
    # left; thee/your_Majesty -> left; {...} excluded entirely.
    template = "The {scenic/Rrich }province of @ belongs/Rowes_allegiance to thee/Ryour_Majesty."
    rng = ScriptedRandom([0.1, 0.1, 0.1, 0.1])
    result = render(template, {"@": "the Dolphin Sea"}, rng=rng)
    assert result == "The province of the Dolphin Sea belongs to thee."


def test_full_pipeline_renders_a_real_say_pas_template_no_choices_needed():
    # RUMORS.PAS _LPatrol (line 463): "< patrolled @ and the surrounding
    # provinces for enemy characters." -- no /R or {} at all.
    template = "< patrolled @ and the surrounding provinces for enemy characters."
    result = render(template, {"@": "the Moonshine Sea"})
    assert result == "< patrolled the Moonshine Sea and the surrounding provinces for enemy characters."
