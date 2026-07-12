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
    # /P is still deferred (see module docstring); /F itself is now
    # supported as of Phase 76 -- see the /F-specific tests below.
    with pytest.raises(NotImplementedError):
        render("a{ferry/Pboat}", rng=ScriptedRandom([0.1]))


def test_sea_marker_picks_left_choice_on_land():
    assert render("army/Sfleet", is_sea=False) == "army"


def test_sea_marker_picks_right_choice_at_sea():
    assert render("army/Sfleet", is_sea=True) == "fleet"


def test_sea_marker_never_consumes_a_random_value():
    # Unlike /R, /S is never a coin flip -- an empty ScriptedRandom must
    # not be asked for a value at all.
    assert render("army/Sfleet", rng=ScriptedRandom([]), is_sea=True) == "fleet"


def test_sea_marker_and_random_choice_combine_in_one_template():
    # "/S" resolves first (left-to-right scan hits it first), consuming
    # no rng; the remaining "/R" still consumes exactly one value.
    rng = ScriptedRandom([0.9])
    assert render("army/Sfleet retreated/Rfled", rng=rng, is_sea=True) == "fleet fled"


def test_feature_marker_picks_left_choice_on_odd_feature_id():
    assert render("crystal/Fcursed", feature_id=1) == "crystal"


def test_feature_marker_picks_right_choice_on_even_feature_id():
    assert render("crystal/Fcursed", feature_id=2) == "cursed"


def test_feature_marker_never_consumes_a_random_value():
    # Unlike /R, /F is never a coin flip -- an empty ScriptedRandom must
    # not be asked for a value at all.
    assert render("crystal/Fcursed", rng=ScriptedRandom([]), feature_id=1) == "crystal"


def test_feature_marker_without_feature_id_raises_value_error():
    with pytest.raises(ValueError):
        render("crystal/Fcursed")


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


# -- ^L list insertion (Phase 118) -------------------------------------------


def test_list_insertion_single_item_renders_bare():
    result = render("^L=", lists={"=": ["241st Axemen"]})
    assert result == "241st Axemen"


def test_list_insertion_two_items_join_with_and_no_comma():
    result = render("^L=", lists={"=": ["241st Axemen", "34th Legion"]})
    assert result == "241st Axemen and 34th Legion"


def test_list_insertion_three_items_matches_prose_txt_quoted_example():
    # PROSE.TXT's own quoted example for ^L=.
    result = render("^L=", lists={"=": ["241st Axemen", "34th Legion", "145th Fleet"]})
    assert result == "241st Axemen, 34th Legion and 145th Fleet"


def test_list_insertion_four_items():
    result = render("^L=", lists={"=": ["A", "B", "C", "D"]})
    assert result == "A, B, C and D"


def test_list_insertion_works_inside_a_larger_template():
    template = "< led ^L= into battle."
    result = render(template, {"<": "Aldric"}, lists={"=": ["241st Axemen", "34th Legion"]})
    assert result == "Aldric led 241st Axemen and 34th Legion into battle."


def test_list_insertion_supports_two_character_markers():
    # e.g. ^L^V ("^V" = Army name), the exact shape SAY.PAS's own
    # _LSLeads/_LSGarr carry (report/turn_report.py Phase 115/118).
    result = render("[ leads approximately ^L^V.", {"[": "Borin"}, lists={"^V": ["241st Axemen", "34th Legion"]})
    assert result == "Borin leads approximately 241st Axemen and 34th Legion."


def test_list_insertion_supports_backslash_marker():
    # e.g. ^L\\ ("\\" = Magic Item), SAY.PAS's own _LInher THEN branch
    # and _MGain (report/turn_report.py Phase 117/118).
    result = render("The heir of < inherited the ^L\\.", {"<": "Aldric"}, lists={"\\": ["Crystal Ball", "Ring of Power"]})
    assert result == "The heir of Aldric inherited the Crystal Ball and Ring of Power."


def test_list_insertion_raises_on_empty_list():
    with pytest.raises(ValueError, match="at least one item"):
        render("^L=", lists={"=": []})


def test_list_insertion_raises_when_no_matching_list_supplied():
    with pytest.raises(ValueError, match="no matching list"):
        render("^L=")


def test_list_insertion_raises_when_lists_has_only_unrelated_markers():
    with pytest.raises(ValueError, match="no matching list"):
        render("^L=", lists={"^V": ["241st Axemen"]})


def test_list_insertion_only_consumes_the_marker_pair_leaving_other_text_alone():
    # A literal standalone "=" elsewhere in the template still resolves
    # via the ordinary `values` substitution, unaffected by ^L=.
    result = render("^L= vs =", lists={"=": ["241st Axemen", "34th Legion"]}, values={"=": "145th Fleet"})
    assert result == "241st Axemen and 34th Legion vs 145th Fleet"
