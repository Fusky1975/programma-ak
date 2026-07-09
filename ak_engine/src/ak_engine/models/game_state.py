"""Persistent, mutable game-state containers.

Every module through Phase 8 operates on caller-supplied snapshots (lists
of ``BattleUnit``, raw ``HexCoord``/``MapBounds`` parameters, etc.) -- none
of them remember anything across calls. This module is the first actual
session state: kingdoms, armies, and provinces that persist across turns
and battles, for ``turn/battle_orchestrator.py`` to read and mutate.

Intentionally minimal -- just enough to orchestrate a battle end-to-end
and (as of Phase 14) track which leader commands which army. Not a full
game database: ``LeaderState`` here is a persistent, minimal stand-in
for a character's position and command relationships -- it does NOT
carry Phase 1's parsed ``ActionPlan`` (``models.kingdom.Leader`` is a
parsed *move submission*, a different concept from the persistent
leader here; the two are linked only by sharing a ``leader_id``). No
diplomacy/treaty tracking beyond a flat alliance set, no turn-history
log.

``LeaderState.skills`` (Phase 30) reuses ``models/kingdom.py``'s
already-resolved ``SkillTable``. ``skills`` defaults to ``None`` ("no
ability data recorded for this leader"), and every consumer
(``turn/battle_orchestrator.py``'s Tactical/Naval strength bonus and
Duel commander selection, ``turn/cast_execution.py``'s Cast success
roll) falls back to its pre-Phase-30 placeholder behavior in that case
-- a real skill level only changes anything once it's set.

``turn/kingdom_bridge.py`` (Phase 31) is the one piece of code that sets
it from real data: given a parsed ``Kingdom`` (Phase 1) and a
``GameState`` that **already has** matching ``LeaderState``s (created by
whatever turn-0 setup the caller already did), it attaches the King's
real ``SkillTable`` to his ``LeaderState`` and syncs everyone's
``kingdom_id``. It's deliberately narrow: a move file carries no
location/race/alignment/treasury for anyone, so it can only enrich
``LeaderState``s that already exist, never create a ``KingdomState`` or
a new ``LeaderState`` from nothing -- see that module's docstring for
why. Building the missing piece (populating a brand-new ``GameState``
from turn 0, with no existing entries to enrich) remains a distinct,
unsolved, larger future task.

``ArmyState.kingdom_id`` is nullable (Phase 16): ``None`` means an
unowned mercenary army (rulebook [3.6]: Disband "releases the army(s)
into mercenary status... will wander around as unemployed mercenaries
until hired"). ``is_allied()`` treats ``None`` as allied with nobody,
including another mercenary army -- two masterless bands aren't each
other's allies just because both have no owner.

``LeaderState.kingdom_id`` is nullable too (Phase 17), same convention:
``None`` means an independent Hero, not yet in anyone's service (rulebook
[3.5] Hire, [3.7] Fire: "The Hero will wander around until hired by
another King").

``LeaderState.is_king`` (Phase 40) is the King/Hero distinction earlier
phases repeatedly flagged as missing (Disband [3.6], Fire [3.7], Hire
[3.5] all give a King broader authority than an ordinary Hero -- see
``turn/plan_dispatch.py``). Defaults to ``False``, same "no data yet"
convention as ``skills``: a hand-built ``LeaderState`` in a test is a
Hero unless the caller says otherwise. ``turn/kingdom_bridge.py``
(Phase 31) is the one piece of code that sets it from real data,
reusing the same King-identification (name match against
``kingdom.king_name``) it already uses for ``skills``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.kingdom import SkillTable
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.race import Race
from ak_engine.turn.combat import Quality


@dataclass(slots=True)
class KingdomState:
    kingdom_id: int
    name: str
    race: Race
    alignment: Alignment
    home_province: HexCoord
    treasury: int = 0


@dataclass(slots=True)
class ArmyState:
    army_id: int
    kingdom_id: int | None  # None = unowned mercenary
    army_type: ArmyType
    quality: Quality
    location: HexCoord
    unhireable_this_turn: bool = False
    # Remaining this gameturn. Not auto-reset at turn start and not derived
    # from ARMY_TABLE speed + March/Naval ability -- the caller sets it.
    movement_points: int = 0
    # Which leader currently leads this army, if any (rulebook: an army may
    # also be unled, under the "garrison commander"). Set/cleared by
    # Leave/Pick_Up (turn/plan_dispatch.py); None means unled.
    commanded_by: int | None = None


@dataclass(slots=True)
class LeaderState:
    leader_id: int
    kingdom_id: int | None  # None = independent Hero, not in any kingdom's service
    name: str
    location: HexCoord
    # None = no ability data recorded for this leader -- see module docstring.
    skills: SkillTable | None = None
    # King/Hero distinction (Phase 40) -- see module docstring.
    is_king: bool = False


@dataclass(slots=True)
class ProvinceState:
    coord: HexCoord
    terrain: Terrain
    race: Race
    owner_kingdom_id: int | None = None
    explored_percent: int = 0
    contested_by_kingdom_id: int | None = None
    # How many of each ArmyType have been recruited from this province so
    # far this gameturn (rulebook [3.4]: normally 1 per type per province
    # per turn, 2 in a King's home province). Not auto-reset at turn start
    # -- the caller clears it, same convention as ArmyState.movement_points.
    recruited_this_turn: dict[ArmyType, int] = field(default_factory=dict)


@dataclass(slots=True)
class GameState:
    turn_number: int = 1
    kingdoms: dict[int, KingdomState] = field(default_factory=dict)
    provinces: dict[HexCoord, ProvinceState] = field(default_factory=dict)
    armies: dict[int, ArmyState] = field(default_factory=dict)
    leaders: dict[int, LeaderState] = field(default_factory=dict)
    allied_kingdoms: set[frozenset[int]] = field(default_factory=set)

    def add_kingdom(self, kingdom: KingdomState) -> None:
        self.kingdoms[kingdom.kingdom_id] = kingdom

    def add_province(self, province: ProvinceState) -> None:
        self.provinces[province.coord] = province

    def add_army(self, army: ArmyState) -> None:
        self.armies[army.army_id] = army

    def remove_army(self, army_id: int) -> None:
        self.armies.pop(army_id, None)

    def new_army_id(self) -> int:
        """Next unused army id (1 above the current highest, or 1 if none exist)."""

        return max((*self.armies.keys(), 0)) + 1

    def add_leader(self, leader: LeaderState) -> None:
        self.leaders[leader.leader_id] = leader

    def remove_leader(self, leader_id: int) -> None:
        self.leaders.pop(leader_id, None)

    def armies_at(self, coord: HexCoord) -> list[ArmyState]:
        return [army for army in self.armies.values() if army.location == coord]

    def leaders_at(self, coord: HexCoord) -> list[LeaderState]:
        return [leader for leader in self.leaders.values() if leader.location == coord]

    def armies_commanded_by(self, leader_id: int) -> list[ArmyState]:
        return [army for army in self.armies.values() if army.commanded_by == leader_id]

    def mercenaries_at(self, coord: HexCoord) -> list[ArmyState]:
        return [army for army in self.armies.values() if army.location == coord and army.kingdom_id is None]

    def independent_heroes_at(self, coord: HexCoord) -> list[LeaderState]:
        return [leader for leader in self.leaders.values() if leader.location == coord and leader.kingdom_id is None]

    def is_allied(self, kingdom_a: int | None, kingdom_b: int | None) -> bool:
        if kingdom_a is None or kingdom_b is None:
            return False
        if kingdom_a == kingdom_b:
            return True
        return frozenset({kingdom_a, kingdom_b}) in self.allied_kingdoms

    def friendly_provinces_for(self, kingdom_id: int) -> set[HexCoord]:
        """Provinces owned by ``kingdom_id`` or one of its allies."""

        return {
            province.coord
            for province in self.provinces.values()
            if province.owner_kingdom_id is not None and self.is_allied(province.owner_kingdom_id, kingdom_id)
        }
