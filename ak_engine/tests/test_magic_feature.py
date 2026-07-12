from __future__ import annotations

from ak_engine.models.magic_feature import MAGIC_FEATURE_NAME, MagicFeature


def test_magic_feature_has_21_declared_members():
    assert len(MagicFeature) == 21


def test_magic_feature_name_covers_every_member():
    assert set(MAGIC_FEATURE_NAME.keys()) == set(MagicFeature)


def test_magic_feature_name_matches_prose_txt_marker_verbatim():
    # PROSE.TXT: '$\\: Magic feature name ("crystal ball", "magic bell", etc.)'
    assert MAGIC_FEATURE_NAME[MagicFeature.CRYSTAL_BALL] == "Crystal_Ball/FMagic_Mirror"
    assert MAGIC_FEATURE_NAME[MagicFeature.BELL] == "Bell/FGong"


def test_magic_feature_name_verbatim_samples():
    assert MAGIC_FEATURE_NAME[MagicFeature.POOL] == "Pool/FStream"
    assert MAGIC_FEATURE_NAME[MagicFeature.THRONE] == "Throne/FDirector's_Chair"
    assert MAGIC_FEATURE_NAME[MagicFeature.GAS_TRAP] == "Gas_Trap/SElectric_Trap"


def test_magic_feature_itself_is_the_ampersand_sentinel():
    # CTME.PAS's own mfname table gives a literal '&' for magfeat's final
    # member (Itself), not a normal name -- kept verbatim rather than guessed.
    assert MAGIC_FEATURE_NAME[MagicFeature.ITSELF] == "&"
