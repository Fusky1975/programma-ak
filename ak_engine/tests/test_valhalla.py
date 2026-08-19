from __future__ import annotations

from ak_engine.models.alignment import Alignment
from ak_engine.models.race import Race
from ak_engine.models.temper import Temper
from ak_engine.models.treasure import Treasure
from ak_engine.models.valhalla import (
    VALHALLA_ROSTER,
    VALHALLA_ROSTER_UNCONFIRMED,
    VALHALLA_VISITOR_LEADER_ID,
    _valhalla_stay_phase_count,
)


def test_visitor_leader_id_is_the_fixed_reserved_slot():
    assert VALHALLA_VISITOR_LEADER_ID == 199


def test_roster_covers_all_5_eligible_alignments_with_150_heroes_total():
    # Phase 560: 137 (Phase 195-198) + 13 real duplicate-name slots
    # (AKGEN_complete_name_lists.md's own raw NEUTRAL2.X2/etc. catalogs
    # give each alignment's true slot count, not a deduplicated-by-name
    # one) -- see this module's own Phase 560 docstring note.
    assert set(VALHALLA_ROSTER.keys()) == {
        Alignment.GOOD,
        Alignment.DRUID,
        Alignment.NEUTRAL,
        Alignment.PAGAN,
        Alignment.EVIL,
    }
    assert sum(len(heroes) for heroes in VALHALLA_ROSTER.values()) == 150


def test_per_alignment_hero_counts():
    assert len(VALHALLA_ROSTER[Alignment.GOOD]) == 36
    assert len(VALHALLA_ROSTER[Alignment.DRUID]) == 24
    assert len(VALHALLA_ROSTER[Alignment.NEUTRAL]) == 38
    assert len(VALHALLA_ROSTER[Alignment.PAGAN]) == 23
    assert len(VALHALLA_ROSTER[Alignment.EVIL]) == 29


def test_every_hero_has_a_30_value_skill_table():
    for heroes in VALHALLA_ROSTER.values():
        for hero in heroes:
            assert len(hero.skills.raw_values) == 30


def test_monster_aid_eagle_gap_was_filled_from_this_roster():
    # Phase 560: switched from a fixed index to a name lookup -- this
    # bucket's own indices shifted once real duplicate-name slots (e.g.
    # a second/third "La-La") were inserted earlier in the list.
    otto = next(h for h in VALHALLA_ROSTER[Alignment.NEUTRAL] if h.name == "Otto")
    assert otto.fixed_item is Treasure.MONSTER_AID_EAGLE
    assert otto.fixed_item_name == "Feather of the Great Eagle"


def test_monster_aid_whale_gap_was_filled_from_this_roster():
    gelenor = next(h for h in VALHALLA_ROSTER[Alignment.PAGAN] if h.name == "Gelenor")
    assert gelenor.fixed_item is Treasure.MONSTER_AID_WHALE
    assert gelenor.fixed_item_name == "Horn of Neptune"


def test_book_tactical_gap_was_filled_from_this_roster():
    xerxes = next(h for h in VALHALLA_ROSTER[Alignment.PAGAN] if h.name == "Xerxes")
    assert xerxes.fixed_item is Treasure.BOOK_TACTICAL
    assert xerxes.fixed_item_name == "Hannibal's Grimoire"


def test_every_hero_has_a_resolved_treasure_item():
    # Phase 198 closed the last of the 63 distinct VALHALLA item names
    # (Hannibal's Grimoire -> BOOK_TACTICAL); no hero's fixed_item is
    # None anymore.
    unresolved = [
        (align, hero.name, hero.fixed_item_name)
        for align, heroes in VALHALLA_ROSTER.items()
        for hero in heroes
        if hero.fixed_item is None
    ]
    assert unresolved == []


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


# -- Phase 546: visitor lifecycle -- stay-phase-count table --


def test_valhalla_stay_phase_count_matches_the_rulebooks_own_table():
    # "Nei turni 1 e 2... una sola azione... due azioni [...] turni
    # 3-4. Tre azioni nei turni 5-6, quattro azioni nei turni 7-8,
    # cinque nei turni dal 9 in poi."
    assert _valhalla_stay_phase_count(1) == 1
    assert _valhalla_stay_phase_count(2) == 1
    assert _valhalla_stay_phase_count(3) == 2
    assert _valhalla_stay_phase_count(4) == 2
    assert _valhalla_stay_phase_count(5) == 3
    assert _valhalla_stay_phase_count(6) == 3
    assert _valhalla_stay_phase_count(7) == 4
    assert _valhalla_stay_phase_count(8) == 4
    assert _valhalla_stay_phase_count(9) == 5
    assert _valhalla_stay_phase_count(20) == 5


# -- Phase 551: 27 further real heroes, deliberately excluded from selection --


def test_unconfirmed_roster_covers_all_5_alignments_with_28_heroes_total():
    # Phase 560: +1 (a second real "Artur" slot, Neutral) -- see this
    # module's own Phase 560 docstring note.
    assert set(VALHALLA_ROSTER_UNCONFIRMED.keys()) == {
        Alignment.GOOD,
        Alignment.DRUID,
        Alignment.NEUTRAL,
        Alignment.PAGAN,
        Alignment.EVIL,
    }
    assert sum(len(heroes) for heroes in VALHALLA_ROSTER_UNCONFIRMED.values()) == 28


def test_unconfirmed_roster_per_alignment_hero_counts():
    assert len(VALHALLA_ROSTER_UNCONFIRMED[Alignment.GOOD]) == 7
    assert len(VALHALLA_ROSTER_UNCONFIRMED[Alignment.DRUID]) == 1
    assert len(VALHALLA_ROSTER_UNCONFIRMED[Alignment.NEUTRAL]) == 8
    assert len(VALHALLA_ROSTER_UNCONFIRMED[Alignment.PAGAN]) == 7
    assert len(VALHALLA_ROSTER_UNCONFIRMED[Alignment.EVIL]) == 5


def test_unconfirmed_roster_every_hero_has_a_30_value_skill_table():
    for heroes in VALHALLA_ROSTER_UNCONFIRMED.values():
        for hero in heroes:
            assert len(hero.skills.raw_values) == 30


def test_unconfirmed_roster_every_hero_has_no_resolved_fixed_item():
    # Unlike VALHALLA_ROSTER (Phase 198 closed every real gap), none of
    # these 27 has a sourced fixed_item -- see module docstring for why.
    for heroes in VALHALLA_ROSTER_UNCONFIRMED.values():
        for hero in heroes:
            assert hero.fixed_item is None


def test_unconfirmed_roster_spot_check_race_and_temper():
    # AKGEN_name_catalogs.json.txt stats_raw[2]/[10], cross-checked
    # against all 137 already-confirmed heroes before trusting the
    # decode on these new ones.
    evelyn = next(h for h in VALHALLA_ROSTER_UNCONFIRMED[Alignment.GOOD] if h.name == "Evelyn")
    assert evelyn.race is Race.ELVEN
    assert evelyn.temper is Temper.CAUTIOUS

    kratos = VALHALLA_ROSTER_UNCONFIRMED[Alignment.DRUID][0]
    assert kratos.name == "Kratos"
    assert kratos.race is Race.HUMAN
    assert kratos.temper is Temper.BRAVE


def test_unconfirmed_roster_names_never_duplicate_the_real_roster_within_an_alignment():
    # Per-alignment, not global: the same name can legitimately appear
    # in two different alignment buckets as two distinct roster slots
    # (e.g. "SWK" is already real in Good and newly found in Pagan) --
    # what must never happen is the same alignment's own two rosters
    # silently colliding.
    for alignment in VALHALLA_ROSTER_UNCONFIRMED:
        real_names = {hero.name for hero in VALHALLA_ROSTER[alignment]}
        unconfirmed_names = {hero.name for hero in VALHALLA_ROSTER_UNCONFIRMED[alignment]}
        assert real_names.isdisjoint(unconfirmed_names), alignment


def test_unconfirmed_roster_is_not_merged_into_the_real_roster_counts():
    # VALHALLA_ROSTER itself must stay at its own Phase 560 baseline
    # (150) -- this phase (551) is purely additive, in a separate dict.
    assert sum(len(heroes) for heroes in VALHALLA_ROSTER.values()) == 150


# -- Phase 560: 178 real raw slots, not 164 unique heroes --


def _name_count(heroes, name: str) -> int:
    return sum(1 for h in heroes if h.name == name)


def test_confirmed_roster_duplicate_slot_counts_match_the_real_raw_catalog():
    # AKGEN_complete_name_lists.md's own raw GOOD2.X2/DRUIDIC2.X2/
    # NEUTRAL2.X2/PAGAN2.X2/EVIL2.X2 source-index counts, cross-checked
    # against AKGEN_name_catalogs.json.txt -- see this module's own
    # Phase 560 docstring note.
    good = VALHALLA_ROSTER[Alignment.GOOD]
    assert _name_count(good, "Winner") == 3
    assert _name_count(good, "Kalko") == 2
    assert _name_count(good, "Endriel") == 2  # already correct before this phase
    assert _name_count(good, "Swk") == 2

    assert _name_count(VALHALLA_ROSTER[Alignment.DRUID], "Fire") == 2

    neutral = VALHALLA_ROSTER[Alignment.NEUTRAL]
    assert _name_count(neutral, "La-La") == 3
    assert _name_count(neutral, "Rogvold") == 2
    assert _name_count(neutral, "Skilza") == 2

    pagan = VALHALLA_ROSTER[Alignment.PAGAN]
    assert _name_count(pagan, "Mary") == 2
    assert _name_count(pagan, "Lancelot") == 2

    assert _name_count(VALHALLA_ROSTER[Alignment.EVIL], "Skilza") == 3


def test_confirmed_roster_final_entry_per_alignment_is_unchanged_by_the_duplicate_fix():
    # turn/valhalla_execution.py _select_visitor_template()'s own
    # turns-1-5 default always reads roster[-1] -- the new duplicate
    # entries must never have been appended after it.
    assert VALHALLA_ROSTER[Alignment.GOOD][-1].name == "Quintilian"
    assert VALHALLA_ROSTER[Alignment.DRUID][-1].name == "Bo"
    assert VALHALLA_ROSTER[Alignment.NEUTRAL][-1].name == "Kitralus"
    assert VALHALLA_ROSTER[Alignment.PAGAN][-1].name == "Kelderek"
    assert VALHALLA_ROSTER[Alignment.EVIL][-1].name == "Dietrich"


def test_unconfirmed_roster_artur_duplicate_slot_count():
    assert _name_count(VALHALLA_ROSTER_UNCONFIRMED[Alignment.NEUTRAL], "Artur") == 2
