"""GM web interface (Phase 1): a local Flask app guiding the Game Master
through a game's full lifecycle -- player setup, optional titles, world
creation and editing, and the per-turn move/report cycle -- on top of
the existing ``ak_engine`` engine (``worldgen``, ``turn``, ``report``,
``persistence``), with no game logic duplicated here.

Run with ``python -m ak_engine.webapp`` (see ``__main__.py``), or
programmatically via ``create_app()``.
"""

from __future__ import annotations
