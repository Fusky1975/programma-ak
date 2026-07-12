from __future__ import annotations

from ak_engine.models.enums import FAME_DESCRIPTOR


def test_fame_descriptor_covers_skill_levels_0_through_9():
    assert set(FAME_DESCRIPTOR.keys()) == set(range(10))


def test_fame_descriptor_verbatim_samples():
    assert FAME_DESCRIPTOR[0] == "noted for"
    assert FAME_DESCRIPTOR[2] == "famous for"
    assert FAME_DESCRIPTOR[5] == "revered for"


def test_fame_descriptor_levels_6_through_9_all_collapse_to_worshipped():
    # RUMORS.PAS Get_AbDesc: "6..9: s:= 'worshipped for '" -- a real Pascal
    # CASE range, not a transcription shortcut taken here.
    for level in (6, 7, 8, 9):
        assert FAME_DESCRIPTOR[level] == "worshipped for"
