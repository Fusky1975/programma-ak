from __future__ import annotations

from pathlib import Path

from ak_engine.models.enums import ActionCode, Maneuver
from ak_engine.models.plan import PlanPhase
from ak_engine.parser.k1_moves import parse_k1_moves_file
from ak_engine.turn.search_decode import SearchTactic, decode_search_phase, decode_tactic_tokens

GAME_DATA_DIR = Path(__file__).resolve().parents[2]


def test_decode_tactic_tokens_shared_by_search_challenge_pursue_sep():
    # Phase 659: the extracted walk itself, exercised directly -- no
    # leading tl slot here, matching turn/sep_decode.py's own SP: use
    # (Search/Challenge/Pursue strip their own extra[0] before calling
    # this, see decode_search_phase()/challenge_pursue_decode.py).
    assert decode_tactic_tokens([0, 7, 9, -1]) == [
        SearchTactic(Maneuver.CAST, sub_object=7),
        SearchTactic(Maneuver.MELEE),
    ]
    assert decode_tactic_tokens([]) == []


def test_decode_search_phase_reads_feature_id_and_tactics():
    # AK3__T10.K1, leader 42 "Garin", P2: "2 20 0 0 11 0 22 0 7 9 13 -1"
    # -> Search feature 20, tactics: Cast(11), Cast(22), Cast(7), Melee, Scout.
    phase = PlanPhase(label="P2", action=ActionCode.SEARCH, obj=20, extra=[0, 0, 11, 0, 22, 0, 7, 9, 13, -1])

    request = decode_search_phase(phase)

    assert request.feature_id == 20
    assert request.unconfirmed_extra0 == 0
    assert request.tactics == [
        SearchTactic(Maneuver.CAST, sub_object=11),
        SearchTactic(Maneuver.CAST, sub_object=22),
        SearchTactic(Maneuver.CAST, sub_object=7),
        SearchTactic(Maneuver.MELEE),
        SearchTactic(Maneuver.SCOUT),
    ]


def test_decode_search_phase_only_cast_use_mi_give_take_a_sub_object():
    phase = PlanPhase(label="P0", action=ActionCode.SEARCH, obj=1, extra=[0, 7, 9, 13, -1])

    request = decode_search_phase(phase)

    assert request.tactics == [SearchTactic(Maneuver.STEAL), SearchTactic(Maneuver.MELEE), SearchTactic(Maneuver.SCOUT)]


def test_decode_search_phase_say_tactic_reads_free_text():
    # Phase 618: SAY's own argument is a str (already recovered from the
    # raw move file's own lines by parser/k1_moves.py), not an int.
    phase = PlanPhase(label="P0", action=ActionCode.SEARCH, obj=1, extra=[0, 4, "Take that!", -1])

    request = decode_search_phase(phase)

    assert request.tactics == [SearchTactic(Maneuver.SAY, say_text="Take that!")]
    assert request.tactics[0].sub_object is None


def test_decode_search_phase_say_between_other_tactics():
    # Cast(12), then Say("Take that!"), then Melee -- proves SAY's own
    # str element doesn't throw off decoding what comes before or after.
    phase = PlanPhase(label="P0", action=ActionCode.SEARCH, obj=1, extra=[0, 0, 12, 4, "Take that!", 9, -1])

    request = decode_search_phase(phase)

    assert request.tactics == [
        SearchTactic(Maneuver.CAST, sub_object=12),
        SearchTactic(Maneuver.SAY, say_text="Take that!"),
        SearchTactic(Maneuver.MELEE),
    ]


def test_decode_search_phase_say_with_no_following_element_leaves_say_text_none():
    phase = PlanPhase(label="P0", action=ActionCode.SEARCH, obj=1, extra=[0, 4])

    request = decode_search_phase(phase)

    assert request.tactics == [SearchTactic(Maneuver.SAY)]
    assert request.tactics[0].say_text is None


def test_decode_search_phase_handles_empty_extra():
    phase = PlanPhase(label="P0", action=ActionCode.SEARCH, obj=1, extra=[])

    request = decode_search_phase(phase)

    assert request.feature_id == 1
    assert request.unconfirmed_extra0 == 0
    assert request.tactics == []


def test_decode_search_phase_against_every_real_move_file():
    # Ground truth extracted directly via the parser against all 10 real
    # files: 12 real SEARCH phases exist (in T5, T6, T7, T9, T10).
    expected = {
        ("T5", 73, "P4"): (1, [(Maneuver.CAST, 19), (Maneuver.STEAL, None), (Maneuver.SCOUT, None),
                                (Maneuver.FLEE, None), (Maneuver.CAST, 24)]),
        ("T6", 73, "P2"): (16, [(Maneuver.CAST, 19), (Maneuver.STEAL, None), (Maneuver.SCOUT, None),
                                 (Maneuver.FLEE, None), (Maneuver.CAST, 24), (Maneuver.MELEE, None)]),
        ("T6", 73, "P4"): (104, [(Maneuver.CAST, 19), (Maneuver.STEAL, None), (Maneuver.SCOUT, None),
                                  (Maneuver.FLEE, None), (Maneuver.CAST, 24), (Maneuver.MELEE, None)]),
        ("T6", 99, "P0"): (3, [(Maneuver.CAST, 3), (Maneuver.CAST, 11), (Maneuver.SHOOT, None),
                                (Maneuver.MELEE, None), (Maneuver.SCOUT, None)]),
        ("T6", 99, "P2"): (69, [(Maneuver.CAST, 20), (Maneuver.CAST, 3), (Maneuver.CAST, 11), (Maneuver.SHOOT, None),
                                 (Maneuver.MELEE, None), (Maneuver.SCOUT, None)]),
        ("T7", 20, "P2"): (69, [(Maneuver.CAST, 11), (Maneuver.CAST, 22), (Maneuver.SHOOT, None),
                                 (Maneuver.MELEE, None), (Maneuver.SCOUT, None)]),
        ("T7", 73, "P0"): (104, [(Maneuver.CAST, 19), (Maneuver.STEAL, None), (Maneuver.SCOUT, None),
                                  (Maneuver.FLEE, None), (Maneuver.CAST, 24), (Maneuver.MELEE, None)]),
        ("T7", 73, "P2"): (16, [(Maneuver.CAST, 19), (Maneuver.STEAL, None), (Maneuver.SCOUT, None),
                                 (Maneuver.FLEE, None), (Maneuver.CAST, 24), (Maneuver.MELEE, None)]),
        ("T7", 73, "P3"): (1, [(Maneuver.CAST, 19), (Maneuver.STEAL, None), (Maneuver.SCOUT, None),
                                (Maneuver.FLEE, None), (Maneuver.CAST, 24), (Maneuver.MELEE, None)]),
        ("T9", 42, "P0"): (66, [(Maneuver.CAST, 11), (Maneuver.CAST, 22), (Maneuver.CAST, 7),
                                 (Maneuver.MELEE, None), (Maneuver.SCOUT, None)]),
        ("T10", 42, "P2"): (20, [(Maneuver.CAST, 11), (Maneuver.CAST, 22), (Maneuver.CAST, 7),
                                  (Maneuver.MELEE, None), (Maneuver.SCOUT, None)]),
        ("T10", 72, "P0"): (75, [(Maneuver.CAST, 20), (Maneuver.CAST, 15), (Maneuver.CAST, 3), (Maneuver.CAST, 28),
                                  (Maneuver.CAST, 7), (Maneuver.MELEE, None), (Maneuver.SCOUT, None)]),
    }

    found: dict[tuple[str, int, str], object] = {}
    for turn, leader_id, label in expected:
        kingdom = parse_k1_moves_file(GAME_DATA_DIR / f"AK3__T{turn[1:]}.K1")
        leader = next(l for l in kingdom.leaders if l.leader_id == leader_id)
        phase = leader.plan.segments[0].phases[label]
        assert phase.action == ActionCode.SEARCH
        found[(turn, leader_id, label)] = decode_search_phase(phase)

    for key, (feature_id, tactics) in expected.items():
        request = found[key]
        assert request.feature_id == feature_id, key
        assert request.unconfirmed_extra0 == 0, key
        assert [(t.maneuver, t.sub_object) for t in request.tactics] == tactics, key
