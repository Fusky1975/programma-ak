"""Executing a Recruit order end-to-end (rulebook [3.4]).

Wires together: ``turn/recruit_decode.py``'s already-decoded
``RecruitRequest`` -> ``turn/recruit.py resolve_recruit()`` (per-turn
limit + gold cost per requested type) -> ``KingdomState.treasury`` debit
(plus a real gold transfer to an ally, "the recruiter pays 1 gold to his
ally for each recruited army", rulebook [3.4]) -> a new ``ArmyState`` per
successfully recruited unit.

**Cost data double-checked before writing this module**: every one of
``models.army_type.ARMY_TABLE``'s 19 ``pay`` values was re-verified
against the rulebook's Army Type Table [6.3] Pay column, line by line --
all correct. Also investigated a red herring in ``CTBOTH.PAS``: an
``at_cost``/``atdesig`` array that looks army-related at a glance is
actually indexed by an unrelated ``retainer`` enum (personal
companions/followers for character encounters -- Heralds, Armorers,
Entertainers, etc. -- a different subsystem entirely, not recruitable
provincial armies). Confirmed via the ``retainer`` type declaration
(``CTBOTH.PAS`` ~line 1388) and its own ``atdesig``/``atstren`` tables,
which don't overlap with the ``army`` enum's members at all. So
``ARMY_TABLE.pay`` remains the correct and only cost source.

**Quantity requested vs. quantity recruited**: if a phase requests more
of a type than the per-turn limit allows, or more than the treasury can
afford, this recruits as many as it can (in the order requested) and
reports the rest as blocked, rather than either silently dropping the
excess or failing the whole order -- a documented choice, since the
rulebook doesn't say which happens when a request exceeds what's
affordable/allowed.

**New army defaults**: quality ``Average`` (rulebook: "an army is levied
from among the populace") and 0 movement points (conservative: the
rulebook doesn't say whether a freshly recruited army can act the same
phase, so it starts unable to move rather than guessing it can).

**Hiring an existing mercenary (Phase 16)**: rulebook [3.4], "if there is
an Average or higher quality mercenary army of that type in the
province, then the mercenaries are hired" -- before levying a fresh
``Average`` army, checks ``GameState.mercenaries_at()`` for a co-located,
matching-``army_type``, ``quality >= Average``, currently-hireable
(``not unhireable_this_turn``) army and re-assigns it in place instead of
creating a new one, preserving its (possibly higher) quality. Still
costs the same ``unit_cost`` and still counts against
``recruited_this_turn`` -- the rulebook doesn't distinguish hiring from
levying on price or the per-province limit, only on where the army comes
from. Reported via ``RecruitedUnit.hired``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ak_engine.models.army_type import ArmyType
from ak_engine.models.game_state import ArmyState, GameState
from ak_engine.turn.combat import Quality
from ak_engine.turn.recruit import IncompatibleRaceError, is_army_type_compatible_with_race, resolve_recruit
from ak_engine.turn.recruit_decode import RecruitRequest


@dataclass(slots=True)
class RecruitedUnit:
    army_id: int
    army_type: ArmyType
    gold_paid: int
    hired: bool = False  # True = an existing mercenary was hired, not freshly levied


@dataclass(slots=True)
class RecruitExecutionResult:
    request: RecruitRequest
    recruited: list[RecruitedUnit] = field(default_factory=list)
    limit_blocked: list[ArmyType] = field(default_factory=list)
    gold_blocked: list[ArmyType] = field(default_factory=list)
    incompatible: list[ArmyType] = field(default_factory=list)
    total_gold_spent: int = 0


def execute_recruit(state: GameState, kingdom_id: int, leader_id: int, request: RecruitRequest) -> RecruitExecutionResult:
    """Price, limit-check, and actually recruit every type in ``request``.

    Recruits at the acting leader's current location. Newly recruited
    armies are commanded by ``request.leader_id`` (the phase's decoded
    target leader, possibly None = unled/garrison).
    """

    leader = state.leaders[leader_id]
    location = leader.location
    province = state.provinces[location]
    kingdom = state.kingdoms[kingdom_id]

    is_home_province = location == kingdom.home_province
    in_ally_territory = (
        province.owner_kingdom_id is not None
        and province.owner_kingdom_id != kingdom_id
        and state.is_allied(province.owner_kingdom_id, kingdom_id)
    )

    result = RecruitExecutionResult(request=request)

    for army_type in request.army_types:
        is_native = is_army_type_compatible_with_race(army_type, province.race)
        try:
            resolution = resolve_recruit(
                army_type,
                province.race,
                is_home_province=is_home_province,
                is_native_to_province=is_native,
                in_ally_territory=in_ally_territory,
            )
        except IncompatibleRaceError:
            result.incompatible.append(army_type)
            continue

        already_this_turn = province.recruited_this_turn.get(army_type, 0)
        if already_this_turn >= resolution.max_units:
            result.limit_blocked.append(army_type)
            continue

        unit_cost = resolution.gold_per_unit + resolution.ally_fee_per_unit
        if kingdom.treasury < unit_cost:
            result.gold_blocked.append(army_type)
            continue

        kingdom.treasury -= unit_cost
        if in_ally_territory and resolution.ally_fee_per_unit:
            state.kingdoms[province.owner_kingdom_id].treasury += resolution.ally_fee_per_unit

        mercenary = next(
            (
                army
                for army in state.mercenaries_at(location)
                if army.army_type is army_type
                and army.quality >= Quality.AVERAGE
                and not army.unhireable_this_turn
            ),
            None,
        )
        if mercenary is not None:
            mercenary.kingdom_id = kingdom_id
            mercenary.commanded_by = request.leader_id
            army_id = mercenary.army_id
            hired = True
        else:
            army_id = state.new_army_id()
            state.add_army(
                ArmyState(
                    army_id=army_id,
                    kingdom_id=kingdom_id,
                    army_type=army_type,
                    quality=Quality.AVERAGE,
                    location=location,
                    commanded_by=request.leader_id,
                    movement_points=0,
                )
            )
            hired = False
        province.recruited_this_turn[army_type] = already_this_turn + 1

        result.recruited.append(RecruitedUnit(army_id=army_id, army_type=army_type, gold_paid=unit_cost, hired=hired))
        result.total_gold_spent += unit_cost

    return result
