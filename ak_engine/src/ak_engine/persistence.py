"""Save/load a persistent ``GameState`` between turns (Phase 424).

**Why this didn't exist until now, and why it can't be a reproduction of
the original save format**: the real ``AK.EXE``'s own save-game format
was never part of the available Pascal source (see ``turn/
kingdom_bridge.py``'s own docstring, which already documents this same
gap for a different reason -- a ``.K1`` move file carries no location/
race/treasury data because that state lives entirely in the original
engine's own save file, which this project has never had access to).
So there is no real format to port here; this module invents a new one
for this project's own internal use only, not a recovered one.

**Why pickle, not JSON**: every model in ``models/game_state.py`` is a
plain ``@dataclass`` (many with ``set``/``dict`` fields keyed by
``HexCoord`` or enum members, e.g. ``GameState.provinces``,
``KingdomState.discoveries``) -- exactly what ``pickle`` round-trips for
free and what JSON cannot represent without a large, bespoke encode/
decode layer (non-string dict keys, enums, sets) that would itself be
new, unsourced code with its own bugs to find. Since this format has no
external counterpart to stay compatible with, there is nothing lost by
picking the option that needs zero new serialization code.

**Real limits, not hidden ones**:
- Pickled state is coupled to this project's own class definitions --
  a save file made before a model's fields change may fail to load
  after. This is an internal working format, not a durable archive
  format; it makes no forward/backward-compatibility promise.
- ``pickle.load`` executes arbitrary code for a maliciously-crafted
  file. Only load save files this project (or a trusted caller) wrote
  itself -- never a file received from an untrusted source.
"""

from __future__ import annotations

import dataclasses
import pickle
from pathlib import Path

from ak_engine.models.game_state import GameState


def save_game_state(state: GameState, path: Path) -> None:
    """Writes ``state`` to ``path`` as a pickle. Overwrites any existing file."""

    path.write_bytes(pickle.dumps(state))


def load_game_state(path: Path) -> GameState:
    """Reads a ``GameState`` previously written by ``save_game_state()``.

    See the module docstring's security note: only call this on a file
    this project's own tooling wrote.
    """

    state = pickle.loads(path.read_bytes())
    _backfill_missing_fields(state)
    return state


def _backfill_missing_fields(root: object) -> None:
    """Gives every dataclass in a loaded state the fields it did not have when it was saved.

    A game saved by an earlier version of the program is a pickle of dataclasses with ``slots=True``: a field added
    since is simply *unset* on the loaded object (reading it raises ``AttributeError``), so a game that was running
    would stop working after an update. Every missing field takes its declared default; nothing present is touched."""

    seen: set[int] = set()
    stack: list[object] = [root]
    while stack:
        obj = stack.pop()
        if id(obj) in seen:
            continue
        seen.add(id(obj))
        if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
            for field in dataclasses.fields(obj):
                try:
                    value = getattr(obj, field.name)
                except AttributeError:
                    if field.default is not dataclasses.MISSING:
                        value = field.default
                    elif field.default_factory is not dataclasses.MISSING:
                        value = field.default_factory()
                    else:
                        continue
                    object.__setattr__(obj, field.name, value)
                stack.append(value)
        elif isinstance(obj, dict):
            stack.extend(obj.keys())
            stack.extend(obj.values())
        elif isinstance(obj, (list, tuple, set, frozenset)):
            stack.extend(obj)
