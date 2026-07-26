from ak_engine.models.army_type import ArmyType
from ak_engine.turn.army_naming import make_army_display_name, make_army_ordinal


def test_make_army_ordinal_first_second_third():
    assert make_army_ordinal(1) == "1st"
    assert make_army_ordinal(2) == "2nd"
    assert make_army_ordinal(3) == "3rd"


def test_make_army_ordinal_th_default():
    assert make_army_ordinal(4) == "4th"
    assert make_army_ordinal(0) == "0th"
    assert make_army_ordinal(110) == "110th"


def test_make_army_ordinal_eleven_twelve_thirteen_exception():
    # REPORTS.PAS's own Make_Des (Moderator branch): n MOD 100 in
    # (11,12,13) always gets 'th', even though n MOD 10 alone would say
    # 1st/2nd/3rd.
    assert make_army_ordinal(11) == "11th"
    assert make_army_ordinal(12) == "12th"
    assert make_army_ordinal(13) == "13th"
    assert make_army_ordinal(111) == "111th"
    assert make_army_ordinal(112) == "112th"
    assert make_army_ordinal(113) == "113th"


def test_make_army_ordinal_twenty_one_uses_st_again():
    assert make_army_ordinal(21) == "21st"


def test_make_army_display_name_normal_uses_full_type_name():
    # Verified against real letter data: SE3__T0.K1:137, "110th Bowmen".
    assert make_army_display_name(110, ArmyType.BOWMEN) == "110th Bowmen"


def test_make_army_display_name_skeletal_uses_short_designation():
    # Verified against real letter data: SE3__T0.K1:135, "108th Skel Bowmen".
    assert make_army_display_name(108, ArmyType.BOWMEN, is_skeletal=True) == "108th Skel Bowmen"


def test_make_army_display_name_defaults_to_not_skeletal():
    assert make_army_display_name(5, ArmyType.LEGION) == "5th Legion"


def test_make_army_display_name_skeletal_uses_designation_not_full_name_for_whales():
    # WHALES diverges between ARMY_TYPE_NAME ("Whales") and
    # ARMY_TYPE_DESIGNATION ("League") -- confirms the skeletal branch
    # really uses atdesig, not atname, matching REPORTS.PAS:990-992.
    assert make_army_display_name(1, ArmyType.WHALES) == "1st Whales"
    assert make_army_display_name(1, ArmyType.WHALES, is_skeletal=True) == "1st Skel League"
