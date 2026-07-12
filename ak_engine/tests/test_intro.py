from __future__ import annotations

from ak_engine.models.intro import INTRO_TEMPLATE, Intro


def test_intro_has_15_declared_members():
    assert len(Intro) == 15


def test_intro_template_covers_every_member():
    assert set(INTRO_TEMPLATE.keys()) == set(Intro)


def test_intro_template_verbatim_samples():
    assert INTRO_TEMPLATE[Intro.NONE] == "None."
    assert INTRO_TEMPLATE[Intro.SAIL] == "< sailed/Rnavigated > little_ship/Rsloop into the &."


def test_intro_template_down_stairs_and_up_stairs_are_distinct():
    # Two separate stair-related scenarios (descending into vs. climbing
    # up to a Feature) -- confirm they're not accidentally aliased.
    assert INTRO_TEMPLATE[Intro.DOWN_STAIRS] != INTRO_TEMPLATE[Intro.UP_STAIRS]
    assert "descended" not in INTRO_TEMPLATE[Intro.UP_STAIRS]
    assert "climb" in INTRO_TEMPLATE[Intro.UP_STAIRS]


def test_intro_template_swim_and_wade_are_distinct_water_scenarios():
    assert "swam" in INTRO_TEMPLATE[Intro.SWIM]
    assert "waded" in INTRO_TEMPLATE[Intro.WADE]
