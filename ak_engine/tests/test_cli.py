from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from ak_engine.cli import main
from ak_engine.models.alignment import Alignment
from ak_engine.models.enums import ActionCode
from ak_engine.models.game_state import GameState, KingdomState, LeaderState
from ak_engine.models.kingdom import Kingdom, KingdomMoveHeader, SkillTable
from ak_engine.models.leader import Leader
from ak_engine.models.map import HexCoord
from ak_engine.models.plan import ActionPlan, PlanPhase, PlanSegment
from ak_engine.models.race import Race
from ak_engine.persistence import load_game_state, save_game_state

BOARD_WIDTH = 10


def test_new_game_creates_a_loadable_populated_save(tmp_path: Path):
    config = {
        "kings": [
            {"kingdom_id": 1, "leader_id": 1, "name": "Arthur", "race": "HUMAN", "alignment": "GOOD", "home": [0, 0]},
            {"kingdom_id": 2, "leader_id": 2, "name": "Baldric", "race": "ELVEN", "alignment": "NEUTRAL", "home": [5, 5]},
        ]
    }
    config_path = tmp_path / "kings.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    out_path = tmp_path / "save.pkl"

    exit_code = main(["new-game", "--config", str(config_path), "--out", str(out_path), "--seed", "1"])

    assert exit_code == 0
    assert out_path.exists()
    state = load_game_state(out_path)
    assert len(state.kingdoms) == 2
    assert state.kingdoms[1].name == "Arthur"
    assert state.kingdoms[1].race is Race.HUMAN
    assert state.kingdoms[2].alignment is Alignment.NEUTRAL
    assert len(state.provinces) > 0
    assert state.leaders[1].is_king is True


def _wait_leader(leader_id: int, name: str) -> Leader:
    phase = PlanPhase(label="P0", action=ActionCode.WAIT, obj=0, extra=[0])
    return Leader(leader_id, name, ActionPlan(leader_id, [PlanSegment(0, 0, (), {"P0": phase})]))


def _fake_kingdom() -> Kingdom:
    return Kingdom(
        source_filename="fake.K1",
        king_name="Arthur",
        king_title=None,
        header=KingdomMoveHeader(raw_fields=[1, 1, 0]),
        skills=SkillTable(raw_values=[0] * 31),
        leaders=[_wait_leader(1, "Arthur")],
    )


def _saved_state_with_a_king(tmp_path: Path) -> Path:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Arthur", Race.HUMAN, Alignment.GOOD, HexCoord(0, 0)))
    state.add_leader(LeaderState(1, kingdom_id=1, name="Arthur", location=HexCoord(0, 0), is_king=True))
    path = tmp_path / "state.pkl"
    save_game_state(state, path)
    return path


def test_run_turn_writes_a_report_and_saves_the_updated_state(tmp_path: Path):
    state_path = _saved_state_with_a_king(tmp_path)
    report_path = tmp_path / "report.txt"

    with patch("ak_engine.orchestrator.parse_k1_moves_file", return_value=_fake_kingdom()):
        exit_code = main(
            [
                "run-turn",
                "--state", str(state_path),
                "--orders", "fake.K1",
                "--board-width", str(BOARD_WIDTH),
                "--report", str(report_path),
            ]
        )

    assert exit_code == 0
    assert report_path.exists()  # empty is fine for a WAIT-only turn; existing is what matters here
    updated = load_game_state(state_path)
    assert updated.leaders[1].kingdom_id == 1


def test_run_turn_save_as_writes_to_a_different_path_leaving_the_original_untouched(tmp_path: Path):
    state_path = _saved_state_with_a_king(tmp_path)
    original_bytes = state_path.read_bytes()
    save_as_path = tmp_path / "next_turn.pkl"
    report_path = tmp_path / "report.txt"

    with patch("ak_engine.orchestrator.parse_k1_moves_file", return_value=_fake_kingdom()):
        exit_code = main(
            [
                "run-turn",
                "--state", str(state_path),
                "--orders", "fake.K1",
                "--board-width", str(BOARD_WIDTH),
                "--report", str(report_path),
                "--save-as", str(save_as_path),
            ]
        )

    assert exit_code == 0
    assert save_as_path.exists()
    assert state_path.read_bytes() == original_bytes
