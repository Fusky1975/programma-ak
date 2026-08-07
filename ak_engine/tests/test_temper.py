from __future__ import annotations

from ak_engine.models.temper import TEMPER_ABBREVIATION, TEMPER_NAME, Temper


def test_temper_enum_has_4_declared_values():
    assert len(Temper) == 4
    assert Temper.COWARDLY.value == 0
    assert Temper.BERSERK.value == 3


def test_temper_name_covers_every_enum_value():
    assert set(TEMPER_NAME.keys()) == set(Temper)


def test_temper_name_matches_prose_txt_examples_verbatim():
    # PROSE.TXT: "$T: Temper name ('Berserk', 'Cautious', etc.)"
    assert TEMPER_NAME[Temper.BERSERK] == "Berserk"
    assert TEMPER_NAME[Temper.CAUTIOUS] == "Cautious"


def test_temper_name_remaining_verbatim_values():
    assert TEMPER_NAME[Temper.COWARDLY] == "Cowardly"
    assert TEMPER_NAME[Temper.BRAVE] == "Brave"


# -- Phase 432: CHARACTERS table column abbreviation --------------------


def test_temper_abbreviation_verbatim_pascal_tempab_values():
    # CTBOTH.PAS `tempab: tempstrs = ('Cowrd','Caut','Brave','Bersk')`,
    # positionally verbatim with `Temper`'s own declared order.
    assert TEMPER_ABBREVIATION[Temper.COWARDLY] == "Cowrd"
    assert TEMPER_ABBREVIATION[Temper.CAUTIOUS] == "Caut"
    assert TEMPER_ABBREVIATION[Temper.BRAVE] == "Brave"
    assert TEMPER_ABBREVIATION[Temper.BERSERK] == "Bersk"


def test_temper_abbreviation_covers_every_enum_value():
    assert set(TEMPER_ABBREVIATION) == set(Temper)
