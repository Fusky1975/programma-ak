"""Debug export of a whole game: one zip with every file in the game's own
directory (state, players, submitted moves, generated reports, processing
logs -- everything the GM interface ever wrote for it) plus a generated
``DIAGNOSTICS.txt`` summary, so a game can be handed over for bug analysis
without picking files out of the games folder by hand.
"""

from __future__ import annotations

import io
import zipfile
from collections import Counter
from pathlib import Path

from ak_engine.models.game_state import GameState
from ak_engine.models.map import Terrain
from ak_engine.webapp.games import GameMeta, game_dir, open_game

DIAGNOSTICS_NAME = "DIAGNOSTICS.txt"


def _neutral_province_lines(state: GameState) -> list[str]:
    """The exact situation behind "I marched in and nobody fought": every
    unowned land province with no non-mercenary army present."""

    unowned_land = [
        (coord, province)
        for coord, province in state.provinces.items()
        if province.owner_kingdom_id is None and province.effective_terrain() is not Terrain.SEA
    ]
    undefended = [
        (coord, province)
        for coord, province in unowned_land
        if not any(not army.is_mercenary for army in state.armies_at(coord))
    ]
    lines = [
        f"unowned land provinces: {len(unowned_land)}",
        f"  of which with no defending army (non-mercenary): {len(undefended)}",
    ]
    for coord, province in undefended[:50]:
        name = province.name or "?"
        lines.append(f"    ({coord.x},{coord.y}) {name} race={province.race.name} terrain={province.effective_terrain().name}")
    if len(undefended) > 50:
        lines.append(f"    ... and {len(undefended) - 50} more")
    return lines


def build_diagnostics(meta: GameMeta, state: GameState, files: list[tuple[str, int]]) -> str:
    armies_by_owner = Counter(
        ("independent/mercenary" if army.kingdom_id is None else f"kingdom {army.kingdom_id}") for army in state.armies.values()
    )
    lines = [
        f"Game: {meta.name} (slug {meta.slug})",
        f"Turn: {meta.turn_number}",
        f"Kingdoms: {len(state.kingdoms)}",
        f"Board: {state.board_width}x{state.board_height}",
        f"Provinces: {len(state.provinces)}  Leaders: {len(state.leaders)}  Armies: {len(state.armies)}  Features: {len(state.features)}",
        "Armies by owner: " + ", ".join(f"{owner}={count}" for owner, count in sorted(armies_by_owner.items())),
        "",
        *_neutral_province_lines(state),
        "",
        "Files in the bundle:",
        *(f"  {name}  ({size} bytes)" for name, size in files),
    ]
    return "\n".join(lines) + "\n"


def build_game_bundle(root: Path, slug: str) -> bytes:
    """Raises ``GameNotFoundError`` (via ``game_dir``/``open_game``) for an
    unknown or malformed slug. Symlinks are skipped, so a stray link inside
    a game directory can never pull in a file from outside it."""

    directory = game_dir(root, slug)
    meta, state = open_game(root, slug)

    entries: list[tuple[str, Path]] = []
    for path in sorted(directory.rglob("*")):
        if path.is_symlink() or not path.is_file():
            continue
        entries.append((path.relative_to(directory).as_posix(), path))

    sizes = [(name, path.stat().st_size) for name, path in entries]
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(DIAGNOSTICS_NAME, build_diagnostics(meta, state, sizes))
        for name, path in entries:
            archive.write(path, arcname=f"{slug}/{name}")
    return buffer.getvalue()
