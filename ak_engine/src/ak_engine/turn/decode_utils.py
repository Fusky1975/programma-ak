"""Tiny shared idioms reused across several ``turn/*_decode.py`` modules.

Each of these is architecturally the same field every time -- the
generic ``extra``/``tl`` slot every real ``R_HPlan``/``W_HPlan`` action
reads before its own ``CASE`` dispatch (see ``turn/trade_decode.py``'s
own docstring for the fullest citation of that) -- not a per-action
coincidence, so the one doc note lives here instead of being repeated
piecemeal at every call site.
"""

from __future__ import annotations

from typing import TypeVar

from ak_engine.models.map import Terrain
from ak_engine.models.plan import PlanPhase

_T = TypeVar("_T")


def phase_extra0(phase: PlanPhase, default: int = 0) -> int:
    """``phase.extra[0]``, or ``default`` when ``extra`` is empty --
    the generic "first extra slot" every action's own decode reads
    before checking whether it means anything for that specific action.
    """

    return phase.extra[0] if phase.extra else default


def strip_sentinel(values: list[_T], sentinel: _T = -1) -> list[_T]:
    """Drop a single trailing ``sentinel`` value, if present -- this
    project's own wire-format convention for a ``-1``-terminated list
    (``turn/recruit_decode.py``, ``turn/search_decode.py``, ``turn/
    army_list_decode.py`` each independently reimplemented this exact
    check before being consolidated here).
    """

    if values and values[-1] == sentinel:
        return values[:-1]
    return values


def terrain_from_extra(extra: list[int], index: int) -> Terrain | int | None:
    """``extra[index]`` decoded as a fake ``Terrain`` -- used only by the
    handful of actions (Cast Illus_Terrain, Use_MI of an Illusory-Terrain
    item) whose own second ``extra`` slot encodes a terrain the caller
    doesn't otherwise know how to interpret. ``None`` when ``extra`` has
    no element at ``index`` (the ordinary case for every other action);
    an out-of-range raw int is passed through unresolved rather than
    guessed, matching this project's own "unconfirmed raw field" convention.
    """

    if len(extra) <= index:
        return None
    try:
        return Terrain(extra[index])
    except ValueError:
        return extra[index]
