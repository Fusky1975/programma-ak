from __future__ import annotations

from ak_engine.models.alignment import Alignment


def test_alignment_has_10_declared_values():
    assert len(Alignment) == 10


def test_alignment_verbatim_pascal_outname_values():
    # HostAK/TP/CTBOTH.PAS `outname`, verbatim, positional with `outlook`.
    assert Alignment.DIVINE.value == "Divine"
    assert Alignment.GOOD.value == "Good"
    assert Alignment.DRUID.value == "Druidic"
    assert Alignment.NEUTRAL.value == "Neutral"
    assert Alignment.PAGAN.value == "Pagan"
    assert Alignment.EVIL.value == "Evil"
    assert Alignment.ANTI_HOLY.value == "Anti-Holy"
    assert Alignment.UNDEAD.value == "Undead"
    assert Alignment.MECHANICAL.value == "Mechanical"
    assert Alignment.SPECIAL.value == "Special"


def test_alignment_values_are_all_unique():
    assert len({a.value for a in Alignment}) == len(Alignment)
