from __future__ import annotations

from pathlib import Path

from ak_engine.models.alignment import Alignment
from ak_engine.models.game_state import GameState, KingdomState, LeaderState
from ak_engine.models.map import HexCoord
from ak_engine.models.race import Race
from ak_engine.models.temper import Temper
from ak_engine.parser.gw_world import parse_gw_leaders
from ak_engine.parser.k1_moves import parse_k1_moves_file
from ak_engine.turn.kingdom_bridge import sync_leaders_from_gw_world, sync_leaders_from_kingdom

GAME_DATA_DIR = Path(__file__).resolve().parents[2]
LOCATION = HexCoord(3, 9)
GW_FIXTURE = Path(__file__).parent / "fixtures" / "world" / "G3" / "GW3__T1"


def test_syncs_kingdom_id_and_attaches_kings_skills_when_leaders_already_exist():
    kingdom = parse_k1_moves_file(GAME_DATA_DIR / "AK3__T1.K1")  # King id 1, Heroes 18 and 72
    state = GameState()
    state.add_kingdom(KingdomState(27, "Uga-Buga Makumb", Race.HUMAN, Alignment.NEUTRAL, LOCATION))
    state.add_leader(LeaderState(1, kingdom_id=None, name="Uga-Buga Makumb", location=LOCATION))
    state.add_leader(LeaderState(18, kingdom_id=None, name="Guerin", location=LOCATION))
    state.add_leader(LeaderState(72, kingdom_id=None, name="Teleko", location=LOCATION))

    report = sync_leaders_from_kingdom(kingdom, state)

    assert sorted(report.synced_leader_ids) == [1, 18, 72]
    assert report.not_found_leader_ids == []
    assert report.king_not_identified is False
    assert report.skills_attached_to_leader_id == 1

    assert state.leaders[1].kingdom_id == 27
    assert state.leaders[18].kingdom_id == 27
    assert state.leaders[72].kingdom_id == 27
    assert state.leaders[1].skills is kingdom.skills
    # Only the King's real skill line exists in the file -- Heroes' own
    # ability data is never present, so they stay untouched.
    assert state.leaders[18].skills is None
    assert state.leaders[72].skills is None
    # Phase 40: the same name-matched identification also syncs is_king.
    assert state.leaders[1].is_king is True
    assert state.leaders[18].is_king is False
    assert state.leaders[72].is_king is False


def test_reports_leaders_with_no_existing_leaderstate_without_creating_them():
    kingdom = parse_k1_moves_file(GAME_DATA_DIR / "AK3__T1.K1")
    state = GameState()  # no leaders tracked at all yet

    report = sync_leaders_from_kingdom(kingdom, state)

    assert report.synced_leader_ids == []
    assert sorted(report.not_found_leader_ids) == [1, 18, 72]
    assert report.skills_attached_to_leader_id is None
    assert state.leaders == {}


def test_only_matched_leaders_are_synced_others_still_reported_missing():
    kingdom = parse_k1_moves_file(GAME_DATA_DIR / "AK3__T1.K1")
    state = GameState()
    state.add_leader(LeaderState(18, kingdom_id=5, name="Guerin", location=LOCATION))  # was Hired away

    report = sync_leaders_from_kingdom(kingdom, state)

    assert report.synced_leader_ids == [18]
    assert sorted(report.not_found_leader_ids) == [1, 72]
    # Guerin is back in this kingdom's own move-file submission this turn
    # -> re-synced to kingdom_id 27, regardless of last turn's employer.
    assert state.leaders[18].kingdom_id == 27
    # He's not the King, so no skills attached even though he was found.
    assert report.skills_attached_to_leader_id is None
    assert state.leaders[18].skills is None


def test_king_not_identified_when_no_leader_name_matches_king_name():
    kingdom = parse_k1_moves_file(GAME_DATA_DIR / "AK3__T1.K1")
    # Simulate a hypothetical file whose King's own leader-block name
    # doesn't match the king-name line (never observed in real samples,
    # but the module must not silently guess a King in that case).
    kingdom.leaders[0].name = "Someone Else"
    state = GameState()
    state.add_leader(LeaderState(1, kingdom_id=None, name="Uga-Buga Makumb", location=LOCATION))

    report = sync_leaders_from_kingdom(kingdom, state)

    assert report.king_not_identified is True
    assert report.skills_attached_to_leader_id is None
    assert state.leaders[1].skills is None
    # kingdom_id syncing is unaffected -- it doesn't depend on King identification.
    assert state.leaders[1].kingdom_id == 27
    # Nobody in the file was matched as King, so nobody gets is_king=True.
    assert state.leaders[1].is_king is False


def test_is_king_sync_corrects_a_stale_flag_from_a_prior_state():
    kingdom = parse_k1_moves_file(GAME_DATA_DIR / "AK3__T1.K1")  # King id 1, Hero 18
    state = GameState()
    # Hand-built state has this backwards -- leader 18 was (incorrectly)
    # marked King, and the real King (1) wasn't.
    state.add_leader(LeaderState(1, kingdom_id=None, name="Uga-Buga Makumb", location=LOCATION, is_king=False))
    state.add_leader(LeaderState(18, kingdom_id=None, name="Guerin", location=LOCATION, is_king=True))

    sync_leaders_from_kingdom(kingdom, state)

    assert state.leaders[1].is_king is True
    assert state.leaders[18].is_king is False


def test_gw_world_sync_sets_a_heros_own_kingdom_id_race_alignment_temper_skills():
    # Ningarl (#13) serves King Hokuto (#4) -- Phase 327's own confirmed
    # Liege cross-check against SE3__T1.K4's real CHARACTERS roster.
    records = parse_gw_leaders(GW_FIXTURE)
    state = GameState()
    state.add_leader(LeaderState(13, kingdom_id=None, name="Ningarl", location=LOCATION))

    report = sync_leaders_from_gw_world(records, state)

    assert "Ningarl" in report.synced_names
    assert "Ningarl" in report.kingdom_id_set_for_names
    ningarl = state.leaders[13]
    assert ningarl.kingdom_id == 4
    assert ningarl.race is Race.HUMAN
    assert ningarl.alignment is Alignment.GOOD
    assert ningarl.temper is Temper.CAUTIOUS
    assert ningarl.skills is not None
    assert len(ningarl.skills.raw_values) == 30
    assert ningarl.is_king is False


def test_gw_world_sync_sets_an_independent_heros_kingdom_id_to_none():
    # Kokocala -- narrated as an independent local ruler in SE3__T2.K1's
    # own letter, matching his own real Liege 255/255 header value.
    records = parse_gw_leaders(GW_FIXTURE)
    state = GameState()
    # Was previously (incorrectly) recorded as serving kingdom 3.
    state.add_leader(LeaderState(50, kingdom_id=3, name="Kokocala", location=LOCATION))

    report = sync_leaders_from_gw_world(records, state)

    assert "Kokocala" in report.kingdom_id_set_for_names
    assert state.leaders[50].kingdom_id is None


def test_gw_world_sync_sets_a_kings_own_race_alignment_but_leaves_his_kingdom_id_untouched():
    # Bradipo I's own GW3 record can't supply his own kingdom id (his own
    # Liege reads 255, like every King's) -- that's the K1-based sync's
    # own job (already covered by the King-name-match tests above).
    records = parse_gw_leaders(GW_FIXTURE)
    state = GameState()
    state.add_leader(LeaderState(2, kingdom_id=2, name="Bradipo I", location=LOCATION, is_king=False))

    report = sync_leaders_from_gw_world(records, state)

    assert "Bradipo I" in report.synced_names
    assert "Bradipo I" not in report.kingdom_id_set_for_names
    bradipo = state.leaders[2]
    assert bradipo.kingdom_id == 2  # unchanged
    assert bradipo.race is Race.HUMAN
    assert bradipo.alignment is Alignment.GOOD
    assert bradipo.is_king is True  # is_king IS derivable from the record shape alone


def test_gw_world_sync_reports_unmatched_names_without_creating_new_leaderstates():
    records = parse_gw_leaders(GW_FIXTURE)
    state = GameState()  # no leaders tracked at all yet

    report = sync_leaders_from_gw_world(records, state)

    assert report.synced_names == []
    assert len(report.not_found_names) == 100
    assert state.leaders == {}
