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

**Phase 524 -- `AdvancedAbility.NAVAL_LONG_DEFEND` widens the same
radius, still without needing the undecodable named-province.**
`AKGEN_reverse_engineering_report (3).md` SS108 (disassembly of
`AK.EXE:0x12538-0x12942`) gives the real compiled gate and formula:

```pascal
long_naval := (CountArmyTypes(leader, WhaleLeague..Mermen) > 0)
              and Has_SA(leader, Nav_Defend);
radius := 1 + Ord(long_naval);
candidate is eligible iff
  Dist(candidate, leader_position) <= radius and
  Dist(candidate, stated_defend_hex) <= radius;
```

The second half of that "iff" (the named-hex distance) is exactly the
same undecodable input the conservative superset above already drops --
nothing new is unlocked there. What *is* new and fully computable from
this project's own data: the **radius itself doubles from 1 to 2** when
the Defending leader both holds `NAVAL_LONG_DEFEND` and currently
commands at least one Whale League/Fleet/Mermen unit
(`models/army_type.py SEA_ARMY_TYPES` -- the dossier's own `WhaleLeague..
Mermen` ordinal range, confirmed to exclude the empty ID 15 slot in
between). `defend_coverage_area()` gains an optional `radius` parameter
(default 1, the pre-existing behavior, still exactly `neighbors()`) and
`defend_radius_for_leader()` computes which radius a given Defending
leader actually qualifies for -- `turn/turn_processor.py`'s own
registration site (Phase 422) passes it straight into the existing call,
one line, no other change to the reinforcement-matching logic itself.
"""

from __future__ import annotations

from dataclasses import dataclass

from ak_engine.models.advanced_ability import AdvancedAbility
from ak_engine.models.army_type import SEA_ARMY_TYPES
from ak_engine.models.game_state import GameState
from ak_engine.models.map import HexCoord
from ak_engine.turn.movement import MapBounds, hex_distance, neighbors

DEFAULT_DEFEND_RADIUS = 1
LONG_NAVAL_DEFEND_RADIUS = 2


def defend_radius_for_leader(state: GameState, leader_id: int) -> int:
    """`LONG_NAVAL_DEFEND_RADIUS` if ``leader_id`` both holds
    ``AdvancedAbility.NAVAL_LONG_DEFEND`` and currently commands at least
    one Whale League/Fleet/Mermen unit, else `DEFAULT_DEFEND_RADIUS` --
    see module docstring's own Phase 524 addendum for the sourced gate.
    """

    leader = state.leaders.get(leader_id)
    if leader is None or AdvancedAbility.NAVAL_LONG_DEFEND not in leader.advanced_abilities:
        return DEFAULT_DEFEND_RADIUS
    commands_sea_army = any(army.army_type in SEA_ARMY_TYPES for army in state.armies_commanded_by(leader_id))
    return LONG_NAVAL_DEFEND_RADIUS if commands_sea_army else DEFAULT_DEFEND_RADIUS


def _hexes_within_radius(center: HexCoord, radius: int, bounds: MapBounds) -> set[HexCoord]:
    result: set[HexCoord] = set()
    for x in range(center.x - radius, center.x + radius + 1):
        for y in range(center.y - radius, center.y + radius + 1):
            candidate = HexCoord(x, y)
            if candidate == center or not bounds.contains(candidate):
                continue
            if hex_distance(center, candidate) <= radius:
                result.add(candidate)
    return result


def defend_coverage_area(leader_location: HexCoord, bounds: MapBounds, *, radius: int = DEFAULT_DEFEND_RADIUS) -> set[HexCoord]:
    """Every province within ``radius`` hexes of the Defending leader's
    own current location (``radius=1``, the default, is exactly
    ``neighbors()``).

    See module docstring for why this is a documented superset of the
    rulebook's own (uncomputable, from this project's data) "adjacent to
    both X and Y" formula, and its own Phase 524 addendum for why
    widening ``radius`` to `LONG_NAVAL_DEFEND_RADIUS` is sourced and
    computable even though the named-hex half of the real formula still
    isn't.
    """

    if radius == 1:
        return set(neighbors(leader_location, bounds))
    return _hexes_within_radius(leader_location, radius, bounds)


@dataclass(slots=True)
class DefendCoverage:
    """Phase 422: ``turn/turn_processor.py``'s own ``active_defends`` registry
    used to store a bare ``defend_coverage_area()`` result (the coverage
    *set*), discarding the defender's own original province -- fine
    while nothing needed to narrate the reinforcement event, but
    ``origin`` is exactly ``@`` in ``SAY.PAS _LHearInv``'s own real
    template ("<, responsible for the defense of @, ... on ^S."), so
    it has to survive alongside ``area`` now.
    """

    origin: HexCoord
    area: set[HexCoord]


@dataclass(slots=True)
class DefendReinforcement:
    """Phase 422: ``turn/turn_processor.py _apply_defend_reinforcements()``'s
    own per-defender outcome -- ``origin`` (``@``) and ``target`` (``^S``)
    are exactly ``_LHearInv``'s own two province markers.
    """

    origin: HexCoord
    target: HexCoord
