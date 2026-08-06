"""Command-line entry point tying world generation, turn processing, and
persistence into a runnable game (Phase 424): ``python -m ak_engine.cli``.

Two subcommands:

- ``new-game``: builds a fresh, populated ``GameState`` (``worldgen.
  generate_new_game.generate_new_game()``) from a caller-supplied roster
  of Kings (name/race/alignment/home province -- data this project has
  no source to invent, see that module's own ``KingSetup`` docstring)
  and saves it.
- ``run-turn``: loads a saved ``GameState``, processes one turn's worth
  of real ``.K1`` move-submission files (``orchestrator.process_turn()``),
  writes the resulting narrative to a report file, and saves the
  updated state -- the repeatable step for every subsequent turn.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

from ak_engine.models.alignment import Alignment
from ak_engine.models.game_state import GameState, KingdomState, LeaderState
from ak_engine.models.map import HexCoord
from ak_engine.models.race import Race
from ak_engine.orchestrator import process_turn
from ak_engine.persistence import load_game_state, save_game_state
from ak_engine.worldgen.generate_new_game import KingSetup, generate_new_game
from ak_engine.worldgen.pascal_random import PascalRandom
from ak_engine.worldgen.place_map import DEFAULT_HEIGHT, DEFAULT_WIDTH


def _cmd_new_game(args: argparse.Namespace) -> int:
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))

    state = GameState()
    king_setups: list[KingSetup] = []
    for entry in config["kings"]:
        kingdom_id = entry["kingdom_id"]
        leader_id = entry["leader_id"]
        home = HexCoord(*entry["home"])
        race = Race[entry["race"]]
        alignment = Alignment[entry["alignment"]]
        name = entry["name"]

        state.add_kingdom(KingdomState(kingdom_id, name, race, alignment, home))
        state.add_leader(
            LeaderState(leader_id, kingdom_id=kingdom_id, name=name, location=home, is_king=True, race=race)
        )
        king_setups.append(KingSetup(leader_id=leader_id, race=race, home_coord=home))

    rng = PascalRandom(args.seed)
    generate_new_game(rng, state, king_setups, width=args.width, height=args.height)

    save_game_state(state, Path(args.out))
    print(f"New game saved to {args.out}: {len(state.kingdoms)} kingdoms, {len(state.provinces)} provinces.")
    return 0


def _cmd_run_turn(args: argparse.Namespace) -> int:
    state_path = Path(args.state)
    state = load_game_state(state_path)

    rng = random.Random(args.seed) if args.seed is not None else None
    order_paths = [Path(p) for p in args.orders]

    outcome = process_turn(state, order_paths, board_width=args.board_width, rng=rng)

    Path(args.report).write_text("\n".join(outcome.report_lines), encoding="utf-8")

    save_path = Path(args.save_as) if args.save_as else state_path
    save_game_state(state, save_path)

    for kingdom_id, bridge_report in outcome.bridge_reports.items():
        if bridge_report.not_found_leader_ids:
            print(
                f"warning: kingdom {kingdom_id} order file names leader id(s) "
                f"{bridge_report.not_found_leader_ids} with no matching LeaderState -- skipped",
                file=sys.stderr,
            )
        if bridge_report.king_not_identified:
            print(f"warning: kingdom {kingdom_id}'s King name didn't match any leader in its own file", file=sys.stderr)

    print(f"Turn processed: {len(outcome.results)} phase results, {len(outcome.report_lines)} report lines.")
    print(f"Report written to {args.report}. State saved to {save_path}.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ak_engine", description="Adventurer-Kings engine CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    new_game = subparsers.add_parser("new-game", help="Generate a fresh game and save it")
    new_game.add_argument("--config", required=True, help="JSON file listing Kings (see cli.py module docstring)")
    new_game.add_argument("--out", required=True, help="Path to write the saved GameState")
    new_game.add_argument("--width", type=int, default=DEFAULT_WIDTH)
    new_game.add_argument("--height", type=int, default=DEFAULT_HEIGHT)
    new_game.add_argument("--seed", type=int, default=0, help="PascalRandom seed")
    new_game.set_defaults(func=_cmd_new_game)

    run_turn = subparsers.add_parser("run-turn", help="Process one turn's move files against a saved GameState")
    run_turn.add_argument("--state", required=True, help="Path to a GameState previously saved by this CLI")
    run_turn.add_argument("--orders", required=True, nargs="+", help="One or more .K1 move-submission files")
    run_turn.add_argument("--board-width", type=int, required=True)
    run_turn.add_argument("--report", required=True, help="Path to write the turn's narrative report")
    run_turn.add_argument("--save-as", default=None, help="Where to save the updated state (default: overwrite --state)")
    run_turn.add_argument("--seed", type=int, default=None, help="random.Random seed (default: unseeded)")
    run_turn.set_defaults(func=_cmd_run_turn)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
