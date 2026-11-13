"""Player/King roster for a not-yet-created world (Phase 2): a small JSON
sidecar per game (``players.json``, alongside ``state.pkl``/``meta.json``)
holding each King's name/race/alignment before ``generate_new_game()`` ever
runs.

Kept off ``GameState`` itself rather than as real ``KingdomState``/
``LeaderState`` entries: a real ``KingdomState`` requires a
``home_province`` (``models/game_state.py``, no default), which is
meaningless before a map exists -- Phase 4's own "Create World" step is
what builds the real map, resolves each King's Home coordinate
(``worldgen/king_home_placement.py``, explicit or automatic), and only
then constructs the real ``KingdomState``/``LeaderState``/``KingSetup``
objects and calls ``generate_new_game()``, exactly as ``cli.py
_cmd_new_game`` already does in one shot. This module is the webapp-level
bookkeeping that collects the roster up to that point.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from ak_engine.models.alignment import Alignment
from ak_engine.models.enums import Ability
from ak_engine.models.race import Race
from ak_engine.models.temper import Temper

_PLAYERS_FILENAME = "players.json"

# Player-created Kings are mechanically restricted to these four races:
# worldgen/initial_armies.py's own BEST_ATYPE dict (the real "home_first_
# slot: forced best_atype[king race]" table) only has entries for them,
# so generate_new_game() KeyErrors on any other race for a King's Home
# province. Confirmed from that dict directly, not from the "four
# humanoid races" comment alone.
PLAYABLE_RACES: tuple[Race, ...] = (Race.HUMAN, Race.ELVEN, Race.DWARVEN, Race.ORCISH)

# RULES.AK [1.0]: "Characters also have a race (Human, Elven, Dwarven,
# Orcish), an Alignment (Divine, Good, Druidic, Neutral, Pagan, Evil,
# Undead) and a Temper..." -- these seven are the only Alignments a
# player-controlled character (King or Hero) can ever hold. The other
# three real Alignment members (ANTI_HOLY/"Hellish", MECHANICAL, SPECIAL)
# are monster/construct-only (models/alignment.py's own CTBOTH.PAS
# sourcing), never offered to a player. [2.1] separately caps Divine and
# Undead at one King each per game -- not enforced here, since this
# constant only scopes which seven values are selectable at all.
PLAYABLE_ALIGNMENTS: tuple[Alignment, ...] = (
    Alignment.DIVINE,
    Alignment.GOOD,
    Alignment.DRUID,
    Alignment.NEUTRAL,
    Alignment.PAGAN,
    Alignment.EVIL,
    Alignment.UNDEAD,
)

# Rulebook-sourced player-count bounds (the GM plan's own opening
# request) -- not enforced anywhere in the engine itself, so this is the
# one place that does it.
MIN_PLAYERS = 2
MAX_PLAYERS = 12


class RosterFullError(Exception):
    """Raised when adding a player would exceed MAX_PLAYERS."""


class PlayerNotFoundError(Exception):
    """Raised when removing a player_id that doesn't exist in the roster."""


@dataclass(slots=True)
class PlayerEntry:
    player_id: int
    name: str
    race: str  # Race.name -- plain str for direct JSON round-tripping
    alignment: str  # Alignment.name
    # RULES.AK [2.1]: the player also assigns a Temper and four ability
    # points at signup (worldgen/king_talent.py build_king_skill_table()
    # implements the point-buy formula from that same quote). Both
    # optional (None/empty), matching LeaderState.temper/.skills' own
    # "None = not recorded" convention -- an older players.json predating
    # this field, or a GM who skips them, leaves the King's Temper/skills
    # unset exactly as generate_new_game() already left every King before
    # this phase.
    temper: str | None = None  # Temper.name
    talent_allocation: dict[str, int] = field(default_factory=dict)  # Ability.name -> points (0..2)

    @property
    def race_enum(self) -> Race:
        return Race[self.race]

    @property
    def alignment_enum(self) -> Alignment:
        return Alignment[self.alignment]

    @property
    def temper_enum(self) -> Temper | None:
        return Temper[self.temper] if self.temper is not None else None

    @property
    def talent_allocation_by_ability(self) -> dict[Ability, int]:
        return {Ability[name]: points for name, points in self.talent_allocation.items()}


def _players_file(game_dir: Path) -> Path:
    return game_dir / _PLAYERS_FILENAME


def list_players(game_dir: Path) -> list[PlayerEntry]:
    """Every King added so far, in the order they were added."""

    path = _players_file(game_dir)
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return [PlayerEntry(**entry) for entry in data]


def _save(game_dir: Path, players: list[PlayerEntry]) -> None:
    _players_file(game_dir).write_text(json.dumps([asdict(p) for p in players], indent=2), encoding="utf-8")


def add_player(
    game_dir: Path,
    name: str,
    race: Race,
    alignment: Alignment,
    temper: Temper | None = None,
    talent_allocation: dict[Ability, int] | None = None,
) -> PlayerEntry:
    players = list_players(game_dir)
    if len(players) >= MAX_PLAYERS:
        raise RosterFullError(f"a game can have at most {MAX_PLAYERS} players")

    next_id = max((p.player_id for p in players), default=-1) + 1
    entry = PlayerEntry(
        player_id=next_id,
        name=name,
        race=race.name,
        alignment=alignment.name,
        temper=temper.name if temper is not None else None,
        talent_allocation={ability.name: points for ability, points in (talent_allocation or {}).items()},
    )
    players.append(entry)
    _save(game_dir, players)
    return entry


def remove_player(game_dir: Path, player_id: int) -> None:
    players = list_players(game_dir)
    remaining = [p for p in players if p.player_id != player_id]
    if len(remaining) == len(players):
        raise PlayerNotFoundError(player_id)
    _save(game_dir, remaining)
