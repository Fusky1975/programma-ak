from __future__ import annotations

from ak_engine.models.alignment import ALIGNMENT_ABBREVIATION, ALIGNMENT_BY_ORDINAL, ALIGNMENT_ORDINAL, Alignment


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


# -- Phase 162: the real Pascal `outlook` ordinal sequence, distinct from
# this module's own declaration order above. -------------------------------


def test_alignment_ordinal_matches_real_pascal_outlook_sequence():
    # CTBOTH.PAS `outlook = (Heavenly, Good, Druidic, Worldly, Animal,
    # Evil, Hellish, Undead, Mechanical, Special)`.
    assert ALIGNMENT_ORDINAL[Alignment.DIVINE] == 0
    assert ALIGNMENT_ORDINAL[Alignment.GOOD] == 1
    assert ALIGNMENT_ORDINAL[Alignment.DRUID] == 2
    assert ALIGNMENT_ORDINAL[Alignment.NEUTRAL] == 3
    assert ALIGNMENT_ORDINAL[Alignment.PAGAN] == 4
    assert ALIGNMENT_ORDINAL[Alignment.EVIL] == 5
    assert ALIGNMENT_ORDINAL[Alignment.ANTI_HOLY] == 6
    assert ALIGNMENT_ORDINAL[Alignment.UNDEAD] == 7
    assert ALIGNMENT_ORDINAL[Alignment.MECHANICAL] == 8
    assert ALIGNMENT_ORDINAL[Alignment.SPECIAL] == 9


def test_alignment_ordinal_covers_every_member_with_unique_ordinals():
    assert set(ALIGNMENT_ORDINAL) == set(Alignment)
    assert len(set(ALIGNMENT_ORDINAL.values())) == len(Alignment)


def test_alignment_by_ordinal_is_the_inverse_mapping():
    for member, ordinal in ALIGNMENT_ORDINAL.items():
        assert ALIGNMENT_BY_ORDINAL[ordinal] is member


def test_alignment_good_to_pagan_distance_is_three():
    # The user's own hard data point: "a Good King generally cannot hire
    # a Pagan Hero" -- real ordinal distance 3, not the declaration-order
    # distance for the same pair (which would be different).
    distance = abs(ALIGNMENT_ORDINAL[Alignment.GOOD] - ALIGNMENT_ORDINAL[Alignment.PAGAN])
    assert distance == 3


# -- Phase 432: CHARACTERS table column abbreviation --------------------


def test_alignment_abbreviation_verbatim_pascal_outab_values():
    # CTBOTH.PAS `outab: outstrs = ('Divin','Good','Druid','Neutr','Pagan',
    # 'Evil','Hell','Undea','Mech','Spec')`, positionally verbatim with the
    # real Pascal `outlook` ordinal sequence (ALIGNMENT_ORDINAL), not this
    # module's own declaration order.
    assert ALIGNMENT_ABBREVIATION[Alignment.DIVINE] == "Divin"
    assert ALIGNMENT_ABBREVIATION[Alignment.GOOD] == "Good"
    assert ALIGNMENT_ABBREVIATION[Alignment.DRUID] == "Druid"
    assert ALIGNMENT_ABBREVIATION[Alignment.NEUTRAL] == "Neutr"
    assert ALIGNMENT_ABBREVIATION[Alignment.PAGAN] == "Pagan"
    assert ALIGNMENT_ABBREVIATION[Alignment.EVIL] == "Evil"
    assert ALIGNMENT_ABBREVIATION[Alignment.ANTI_HOLY] == "Hell"
    assert ALIGNMENT_ABBREVIATION[Alignment.UNDEAD] == "Undea"
    assert ALIGNMENT_ABBREVIATION[Alignment.MECHANICAL] == "Mech"
    assert ALIGNMENT_ABBREVIATION[Alignment.SPECIAL] == "Spec"


def test_alignment_abbreviation_covers_every_member():
    assert set(ALIGNMENT_ABBREVIATION) == set(Alignment)
