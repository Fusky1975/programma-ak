"""Defend's reactive coverage area (rulebook [3.15] Defend, corrected by
ADDEND.AK) -- Phase 57.

Rulebook [3.15] (quoted in full): "A general ordered to Defend will be
able to react to enemy invasions of adjacent provinces for the rest of
the turn... You can order your general to Defend an area of 7 provinces,
centered on any province up to two provinces away." Per ADDEND.AK's
errata (already treated as authoritative over the original text in this
project -- see ``turn/aspy_defend_decode.py``'s own docstring, which
quotes it in full): "When giving a 'Defend' order, list only one
province. The general will defend any province that is adjacent to
both the named province and the province the leader is currently
located in."

**The addendum's own coverage formula can't be computed exactly, a
confirmed blocker, not an oversight**: ``DefendRequest.target_province``
(the "named province") is kept as a raw, unconverted int by ``turn/
aspy_defend_decode.py``, because no confirmed numbering scheme exists
for ASpy/Defend's province references at all (LMOVE's own
``hex_numbering.py`` scheme is itself only an empirically-inferred
guess, and nothing confirms it applies to ASpy/Defend's ``obj`` field
too -- converting here would stack one unconfirmed mapping on top of
another). Without a real ``HexCoord`` for the named province, the
addendum's "adjacent to both X and Y" intersection literally cannot be
computed from this project's available data.

**Documented, conservative simplification, confirmed with the user
before implementation**: coverage is approximated as every province
adjacent to the general's own current location alone
(``defend_coverage_area``) -- a strict *superset* of the true
addendum-corrected area (which would further narrow it down by
intersecting with the named province's own neighbors, information this
project can't decode). This means a Defend order modeled here may react
to an invasion the real rule's narrower area wouldn't have covered; it
will never fail to react to one the real rule *would* have covered,
since intersecting two sets can only shrink or preserve a set, never
expand it.
"""

from __future__ import annotations

from ak_engine.models.map import HexCoord
from ak_engine.turn.movement import MapBounds, neighbors


def defend_coverage_area(leader_location: HexCoord, bounds: MapBounds) -> set[HexCoord]:
    """Every province adjacent to the Defending leader's own current location.

    See module docstring for why this is a documented superset of the
    rulebook's own (uncomputable, from this project's data) "adjacent to
    both X and Y" formula.
    """

    return set(neighbors(leader_location, bounds))
