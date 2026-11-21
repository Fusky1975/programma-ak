"""Tests for report/layout.py -- every expected line below is copied from a
real ``SE3__T*.K1`` report written by the original Pascal program."""

from __future__ import annotations

from ak_engine.report.layout import (
    REPORT_WIDTH,
    flow_paragraph,
    flow_sentences,
    normalize_sentences,
    protect_units,
    unprotect,
)


def test_flow_paragraph_matches_a_real_quote_paragraph():
    text = (
        "Sir Christopher Hatton, Lord Chancellor of England, 1589 (in asking for more naval funds, "
        "after England had defeated the Spanish Armada):"
    )

    assert flow_paragraph(text) == [
        "  Sir Christopher Hatton, Lord Chancellor of England, 1589 (in asking for ",
        "more naval funds, after England had defeated the Spanish Armada):",
    ]


def test_flow_paragraph_keeps_the_double_space_after_a_question_mark_at_a_wrap():
    text = (
        '"England hath been accounted hitherto the most renowned kingdom for valour and manhood in all '
        "Christendom, and shall we now lose our old reputation?  If we should, it would have been better "
        'for England to have never been born."'
    )

    assert flow_paragraph(text) == [
        '  "England hath been accounted hitherto the most renowned kingdom for valour ',
        "and manhood in all Christendom, and shall we now lose our old reputation?  ",
        "If we should, it would have been better for England to have never been ",
        'born."',
    ]


def test_flow_paragraph_matches_a_real_phase_paragraph():
    text = (
        "In spring, Uga-Buga Makumb tried hard to improve his Necromancy, but he practiced in vain."
    )

    assert flow_paragraph(text) == [
        "  In spring, Uga-Buga Makumb tried hard to improve his Necromancy, but he ",
        "practiced in vain.",
    ]


def test_flow_sentences_matches_the_real_valhalla_paragraph():
    sentences = [
        "If Roderoch searches a feature, any monetary treasure Roderoch captures will be given to you.",
        "If Roderoch captures a magic treasure, Roderoch will give it to your King when he departs for Valhalla, "
        "or you can order Roderoch to Give it to one of your characters.",
        "You can do anything you want with the magic item Roderoch came with, but the item will leave at the end "
        "of his stay with you.",
    ]

    assert flow_sentences(sentences) == [
        "  If Roderoch searches a feature, any monetary treasure Roderoch captures ",
        "will be given to you.  If Roderoch captures a magic treasure, Roderoch will ",
        "give it to your King when he departs for Valhalla, or you can order Roderoch ",
        "to Give it to one of your characters.  You can do anything you want with the ",
        "magic item Roderoch came with, but the item will leave at the end of his ",
        "stay with you.",
    ]


def test_a_name_is_never_split_across_two_lines():
    sentences = [
        "Standing at the ready with his warriors was Shaman Uga-Buga Makumb Lord of the stu.",
        "Melantheus marched with his loyal troops, eyes set in terrible resolution.",
    ]

    lines = flow_sentences(sentences, units=["Shaman Uga-Buga Makumb Lord of the stu"])

    assert lines == [
        "  Standing at the ready with his warriors was ",
        "Shaman Uga-Buga Makumb Lord of the stu.  Melantheus marched with his loyal ",
        "troops, eyes set in terrible resolution.",
    ]


def test_an_army_type_name_stays_on_one_line():
    lines = flow_sentences(
        ["During fall, Guerin dropped off the 108th Skeletal Bowmen, the 109th Heavy Cavalry and the 110th Bowmen in the Dolphin Sea for Uga-Buga Makumb."],
        units=["Heavy Cavalry", "Skeletal Bowmen"],
    )

    assert lines == [
        "  During fall, Guerin dropped off the 108th Skeletal Bowmen, the 109th ",
        "Heavy Cavalry and the 110th Bowmen in the Dolphin Sea for Uga-Buga Makumb.",
    ]


def test_normalize_sentences_separates_glued_and_single_spaced_sentences():
    assert normalize_sentences("one.Two three. Four five!Six") == "one.  Two three.  Four five!  Six"
    assert normalize_sentences('He said "stop."Then left.') == 'He said "stop."  Then left.'
    assert normalize_sentences("version 1.5 is out and e.g. lowercase stays") == "version 1.5 is out and e.g. lowercase stays"


def test_protect_units_also_joins_an_id_suffix_and_unprotect_restores_spaces():
    protected = protect_units("marched on the Virgo Sea (#1005) with forces", ["Virgo Sea"])

    assert "Virgo Sea" not in protected
    assert unprotect(protected) == "marched on the Virgo Sea (#1005) with forces"


def test_flow_paragraph_never_exceeds_the_report_width_for_ordinary_text():
    text = " ".join(["word"] * 80)

    assert all(len(line.rstrip()) <= REPORT_WIDTH for line in flow_paragraph(text))


def test_flow_sentences_capitalizes_a_unit_that_starts_a_new_sentence():
    lines = flow_sentences(["Fusky rode into Mercia.", "conversing with farmers, Fusky heard a rumor."])

    assert lines == ["  Fusky rode into Mercia.  Conversing with farmers, Fusky heard a rumor."]


def test_normalize_sentences_collapses_stray_double_spaces_inside_a_sentence():
    assert normalize_sentences("a feature in  Galway:  Ancient Megaliths") == "a feature in Galway: Ancient Megaliths"
