from __future__ import annotations

from ak_engine.models.alignment import Alignment
from ak_engine.models.treasure import Treasure
from ak_engine.models.valhalla import VALHALLA_ROSTER, VALHALLA_VISITOR_LEADER_ID


def test_visitor_leader_id_is_the_fixed_reserved_slot():
    assert VALHALLA_VISITOR_LEADER_ID == 199


def test_roster_covers_all_5_eligible_alignments_with_137_heroes_total():
    assert set(VALHALLA_ROSTER.keys()) == {
        Alignment.GOOD,
        Alignment.DRUID,
        Alignment.NEUTRAL,
        Alignment.PAGAN,
        Alignment.EVIL,
    }
    assert sum(len(heroes) for heroes in VALHALLA_ROSTER.values()) == 137


def test_per_alignment_hero_counts():
    assert len(VALHALLA_ROSTER[Alignment.GOOD]) == 32
    assert len(VALHALLA_ROSTER[Alignment.DRUID]) == 23
    assert len(VALHALLA_ROSTER[Alignment.NEUTRAL]) == 34
    assert len(VALHALLA_ROSTER[Alignment.PAGAN]) == 21
    assert len(VALHALLA_ROSTER[Alignment.EVIL]) == 27


def test_every_hero_has_a_30_value_skill_table():
    for heroes in VALHALLA_ROSTER.values():
        for hero in heroes:
            assert len(hero.skills.raw_values) == 30


def test_monster_aid_eagle_gap_was_filled_from_this_roster():
    otto = VALHALLA_ROSTER[Alignment.NEUTRAL][3]
    assert otto.name == "Otto"
    assert otto.fixed_item is Treasure.MONSTER_AID_EAGLE
    assert otto.fixed_item_name == "Feather of the Great Eagle"


def test_two_heroes_have_no_resolved_treasure_item():
    unresolved = [
        (align, hero.name, hero.fixed_item_name)
        for align, heroes in VALHALLA_ROSTER.items()
        for hero in heroes
        if hero.fixed_item is None
    ]
    assert unresolved == [
        (Alignment.PAGAN, "Gelenor", "Horn of Neptune"),
        (Alignment.PAGAN, "Xerxes", "Hannibal's Grimoire"),
    ]


def test_undead_and_divine_heroes_appear_inside_good_and_evil_buckets():
    # Confirms the VALHALLA rule: Divine/Undead kings' own legendary
    # characters join the Good/Evil roster despite never receiving a
    # visit themselves -- see turn/cast_execution.py's own "Phase 195
    # addendum".
    good_true_alignments = {h.true_alignment for h in VALHALLA_ROSTER[Alignment.GOOD]}
    evil_true_alignments = {h.true_alignment for h in VALHALLA_ROSTER[Alignment.EVIL]}
    assert Alignment.DIVINE in good_true_alignments
    assert Alignment.UNDEAD in evil_true_alignments


def test_arthur_carries_excalibur_matching_the_rulebooks_own_example():
    # "Re Artu' avra' sempre Excalibur"
    arthur = next(h for h in VALHALLA_ROSTER[Alignment.GOOD] if h.name == "Arthur")
    assert arthur.fixed_item is Treasure.LEADERSHIP_HUMAN
    assert arthur.fixed_item_name == "Sword Excalibur"
