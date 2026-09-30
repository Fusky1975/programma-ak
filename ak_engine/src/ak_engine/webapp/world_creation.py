""""Create World" (Phase 4 of the GM interface): turns a Phase 2 King
roster (``webapp/players.py``, name/race/alignment only, no real
``KingdomState``/``LeaderState`` yet) into a fully generated, populated
``GameState`` -- the same one-shot ``KingdomState``+``LeaderState``+
``KingSetup`` construction ``cli.py _cmd_new_game`` already does from a
JSON roster, run here from the webapp's own roster instead.

Every King's Home province is auto-placed (``KingSetup.home_coord=None``,
``worldgen/king_home_placement.py``'s own project-original rules) --
there is no map yet at roster-entry time (Phase 2) for the GM to have
pinned an explicit Home coordinate to, so this phase doesn't offer one.
"""

from __future__ import annotations

from pathlib import Path

from ak_engine.models.game_state import GameState, KingdomState, LeaderState
from ak_engine.models.map import HexCoord
from ak_engine.webapp.games import GameMeta, game_dir, open_game, save_game
from ak_engine.webapp.players import MAX_PLAYERS, MIN_PLAYERS, list_players
from ak_engine.worldgen.generate_new_game import KingSetup, generate_new_game
from ak_engine.worldgen.pascal_random import PascalRandom
from ak_engine.worldgen.place_map import DEFAULT_HEIGHT, DEFAULT_WIDTH


class WorldAlreadyCreatedError(Exception):
    """Raised when a game's world has already been generated (``state.kingdoms``
    is non-empty) -- creating it again would silently discard the real,
    already-in-progress game."""


class RosterOutOfBoundsError(Exception):
    """Raised when the roster's own player count isn't within [MIN_PLAYERS,
    MAX_PLAYERS] at the moment "Create World" is invoked."""

    def __init__(self, player_count: int) -> None:
        super().__init__(f"roster has {player_count} players, need {MIN_PLAYERS}-{MAX_PLAYERS}")
        self.player_count = player_count


def create_world(
    root: Path, slug: str, *, width: int = DEFAULT_WIDTH, height: int = DEFAULT_HEIGHT, seed: int
) -> tuple[GameMeta, GameState]:
    """Builds the real ``KingdomState``/``LeaderState`` for every roster
    entry, then runs the full ``generate_new_game()`` pipeline against
    them, saving the result. Raises ``WorldAlreadyCreatedError``/
    ``RosterOutOfBoundsError`` rather than silently regenerating an
    existing world or a roster outside the rulebook's own 2-12 bound.
    """

    _, state = open_game(root, slug)
    if state.kingdoms:
        raise WorldAlreadyCreatedError(slug)

    players = list_players(game_dir(root, slug))
    if not (MIN_PLAYERS <= len(players) <= MAX_PLAYERS):
        raise RosterOutOfBoundsError(len(players))

    king_setups: list[KingSetup] = []
    for kingdom_id, player in enumerate(players, start=1):
        placeholder_home = HexCoord(0, 0)  # generate_new_game() overwrites this with the real, auto-placed Home
        state.add_kingdom(KingdomState(kingdom_id, player.name, player.race_enum, player.alignment_enum, placeholder_home))
        state.add_leader(
            LeaderState(
                kingdom_id,
                kingdom_id=kingdom_id,
                name=player.name,
                location=placeholder_home,
                is_king=True,
                race=player.race_enum,
            )
        )
        king_setups.append(KingSetup(leader_id=kingdom_id, race=player.race_enum, home_coord=None))

    rng = PascalRandom(seed)
    generate_new_game(rng, state, king_setups, width=width, height=height)

    meta = save_game(root, slug, state)
    return meta, state
