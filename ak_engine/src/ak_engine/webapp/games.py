"""Local game registry (Phase 1): one folder per game under a configurable
root, each holding a pickled ``GameState`` (``persistence.py``, reused
as-is) plus a small JSON sidecar with the display metadata a game-list
screen needs without unpickling every game just to show its name and
turn number.

Not a database -- this is a single-GM, local-filesystem tool (see the
GM interface plan's own "Scelte tecniche" section), so a folder-per-game
layout with no locking/concurrency handling is the right level of
complexity.
"""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from ak_engine.models.game_state import GameState
from ak_engine.persistence import load_game_state, save_game_state

_META_FILENAME = "meta.json"
_STATE_FILENAME = "state.pkl"
_SLUG_RE = re.compile(r"[^a-z0-9]+")
# Bug fix: a real slug is always this shape (see _slugify() below) --
# anything else (a literal "..", an absolute path, a path with "/" in
# it, ...) must never reach a filesystem join. Flask's own <slug> URL
# converter does not reject ".." as a path segment (confirmed directly:
# POST /games/../delete reaches this module with slug="..", and before
# this fix, game_dir(root, "..") silently resolved to root's own parent
# directory, which delete_game() then shutil.rmtree()'d in full).
_VALID_SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


class GameNotFoundError(Exception):
    """Raised when a slug doesn't correspond to an existing game directory."""


class DuplicateGameNameError(Exception):
    """Raised when a new game's name slugifies to an already-existing slug."""


@dataclass(slots=True)
class GameMeta:
    """The small, fast-to-read subset of a game's state a list screen needs.

    Kept as its own JSON sidecar (``meta.json``) rather than unpickling
    ``state.pkl`` just to read ``turn_number``/kingdom count -- cheap to
    keep in sync since only ``save_game()`` below ever writes either file.
    """

    slug: str
    name: str
    created_at: str
    turn_number: int
    kingdom_count: int


def _slugify(name: str) -> str:
    slug = _SLUG_RE.sub("-", name.strip().lower()).strip("-")
    return slug or "game"


def game_dir(root: Path, slug: str) -> Path:
    """The on-disk directory for ``slug`` -- public so sibling modules
    (``players.py``) can locate a game's own sidecar files without
    duplicating the root/slug join.

    Raises ``GameNotFoundError`` for any ``slug`` that isn't shaped like
    a real ``_slugify()`` output (see ``_VALID_SLUG_RE``'s own docstring
    note) -- every real game directory's own name is created that way,
    so this never rejects a genuine game, only a slug that could escape
    ``root`` via a filesystem join (e.g. ``".."``, an absolute path, or
    anything containing ``/``). Every caller already treats a bad/
    missing slug as ``GameNotFoundError`` one way or another (either
    directly, or via this same exception already propagating from here
    before an existence check even runs), so this is a stricter version
    of an error every real caller already handles, not a new failure
    mode to plumb through.
    """

    if not _VALID_SLUG_RE.fullmatch(slug):
        raise GameNotFoundError(slug)
    return root / slug


def _read_meta(game_dir: Path) -> GameMeta:
    data = json.loads((game_dir / _META_FILENAME).read_text(encoding="utf-8"))
    return GameMeta(**data)


def _write_meta(game_dir: Path, meta: GameMeta) -> None:
    payload = {
        "slug": meta.slug,
        "name": meta.name,
        "created_at": meta.created_at,
        "turn_number": meta.turn_number,
        "kingdom_count": meta.kingdom_count,
    }
    (game_dir / _META_FILENAME).write_text(json.dumps(payload, indent=2), encoding="utf-8")


def list_games(root: Path) -> list[GameMeta]:
    """Every game under ``root``, newest first. Skips any subdirectory
    missing a real ``meta.json`` rather than raising -- a partially
    written/corrupt entry shouldn't take down the whole list screen.
    """

    if not root.exists():
        return []
    metas = []
    for entry in root.iterdir():
        if not entry.is_dir():
            continue
        try:
            metas.append(_read_meta(entry))
        except (OSError, json.JSONDecodeError, TypeError):
            continue
    metas.sort(key=lambda m: m.created_at, reverse=True)
    return metas


def create_game(root: Path, name: str) -> GameMeta:
    """Creates a new, empty game (a bare ``GameState``, no kingdoms yet --
    Phase 2's player-setup screen populates those). Raises
    ``DuplicateGameNameError`` rather than silently overwriting an
    existing game whose name slugifies the same way.
    """

    slug = _slugify(name)
    directory = game_dir(root, slug)
    if directory.exists():
        raise DuplicateGameNameError(f"a game named {name!r} already exists (slug {slug!r})")

    directory.mkdir(parents=True)
    created_at = datetime.now(timezone.utc).isoformat()
    return save_game(root, slug, GameState(), meta_overrides={"name": name, "created_at": created_at})


def open_game(root: Path, slug: str) -> tuple[GameMeta, GameState]:
    directory = game_dir(root, slug)
    if not directory.is_dir():
        raise GameNotFoundError(slug)
    return _read_meta(directory), load_game_state(directory / _STATE_FILENAME)


def save_game(root: Path, slug: str, state: GameState, *, meta_overrides: dict | None = None) -> GameMeta:
    """Persists ``state`` and refreshes ``meta.json`` from it (turn number,
    kingdom count) -- the one place both files are ever written, so they
    can't drift apart. ``meta_overrides`` only matters for fields
    ``GameState`` itself doesn't carry (``name``/``created_at``).
    """

    directory = game_dir(root, slug)
    directory.mkdir(parents=True, exist_ok=True)

    if (directory / _META_FILENAME).exists():
        existing = _read_meta(directory)
        name, created_at = existing.name, existing.created_at
    else:
        name, created_at = slug, datetime.now(timezone.utc).isoformat()
    if meta_overrides:
        name = meta_overrides.get("name", name)
        created_at = meta_overrides.get("created_at", created_at)

    meta = GameMeta(
        slug=slug,
        name=name,
        created_at=created_at,
        turn_number=getattr(state, "turn_number", 0),
        kingdom_count=len(state.kingdoms),
    )
    save_game_state(state, directory / _STATE_FILENAME)
    _write_meta(directory, meta)
    return meta


def delete_game(root: Path, slug: str) -> None:
    directory = game_dir(root, slug)
    if not directory.is_dir():
        raise GameNotFoundError(slug)
    shutil.rmtree(directory)
