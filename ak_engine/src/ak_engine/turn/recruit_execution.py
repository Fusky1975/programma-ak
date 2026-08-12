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

**The ally "Treat" order precondition (Phase 261)**: rulebook [3.4], "In
order for you to Recruit in your ally's territory, he MUST issue a
'Treat' order with you (even though you may already be allied.)" --
being merely allied is not enough; the whole request is blocked
(``RecruitExecutionResult.treat_blocked``, no partial recruiting) unless
``GameState.has_treat_permission()`` confirms the territory's owner
granted this specific recruiter permission this turn -- see that
field's own docstring for why this is caller-populated rather than
decoded from a move file. Recruiting in one's own territory (allied or
not relevant) is never gated by this check.

**The "former home province, now an ally's" 4-unit bonus (Phase 262)**:
same [3.4] paragraph, next sentence -- "Also, if you are recruiting in
your former home province which is now your ally's province, you can
recruit 4 units." ``at_own_former_home`` (location still matches
``KingdomState.home_province``, which this project never reassigns) is
split into two mutually exclusive cases: still self-owned ->
``is_home_province`` (ordinary 2-unit bonus, unchanged), or now owned
by an ally -> ``is_former_home_province_now_allied`` (the new 4-unit
bonus, still subject to the same Treat-permission gate above, since
it's still ally territory).

**Blocking a levy in hostile/unclaimed territory (Phase 303)**: RULES.AK
[3.4], quoted in full: "You can Recruit armies from the populace only if
you own the province, but mercenaries can be Recruited in any province
by any character, even a King who owns no provinces." This project
never enforced the first half -- a levy (no matching mercenary present)
used to succeed in any province at all, regardless of ownership.
``can_levy`` (``province.owner_kingdom_id == kingdom_id or
in_ally_territory`` -- ally territory is already gated by the Treat
check above) now blocks *only* the populace-levy path
(``RecruitExecutionResult.territory_blocked``); a genuine mercenary hire
still proceeds in any province, exactly as the quoted sentence's own
second half requires. "Belonging to another kingdom" (the same
paragraph's later "You can never Recruit armies belonging to another
kingdom") needed no separate fix -- ``GameState.mercenaries_at()``
already only returns ``kingdom_id is None`` armies, so a kingdom-owned
army was never mistakenly hireable as a mercenary in the first place.

**Wingman's own recruitment bonus (Phase 472, AKGEN_reverse_engineering_
report (2).md SS19.7)**: "la sua fama attira reclute e gli permette di
reclutare una unità aggiuntiva di un tipo d'armata volante in una
provincia visitata che abbia una razza compatibile" -- if the *acting*
leader (this function's own ``leader_id`` parameter -- the character
physically present and recruiting, not ``request.leader_id``, who only
commands the resulting army and may be a different character or None)
currently holds ``Office.WINGMAN`` (``resolve_office_holder``,
resolved once per call, not per army type), a flying army type
(``models/army_type.py OVERFLIGHT_AIR`` -- Dragons/Eagles, the exact
same narrower set SS19.5 already confirmed for the title's own merit
formula, not the broader ``is_overflight_unit()`` that also includes
Whales/Mermen) gets its own real per-turn limit raised by one, provided
it's also race-compatible here (``is_native``, the same "razza
compatibile" check this function already computes for ordinary
recruiting legality -- no separate formula needed). "Belongs to the
titleholder *character*, not the army that might separately hold Royal
Air Force" -- confirmed by construction here, since the check is keyed
off the acting leader, never off any ``ArmyState``. Doesn't change unit
cost, starting quality, or the merit formula itself -- only the
recruitment cap for that one type this call.

**Real per-province native types, when known (Phase 407)**: through
Phase 406, ``is_native_to_province`` was always computed from
``is_army_type_compatible_with_race()`` -- the exact same test
``turn/recruit.py resolve_recruit()`` already uses to decide whether an
army type can be recruited *at all*, so by construction it could never
observe a compatible-but-non-native type here; the double-cost path
this project had already built for that case (``RecruitResolution.
is_double_cost``) was consequently unreachable dead code. Real
per-province data has existed since Phase 278
(``ProvinceState.recruit_type_1``/``recruit_type_2``, decoded from a
real world file's own ``Mod_PAT``) but was never read here. Now, when
a province was bridged from a real world file (``recruit_type_1 is not
None``), an army type is "native" only if it's exactly
``recruit_type_1`` or ``recruit_type_2`` -- a race-compatible but
un-listed type still recruits (nothing in the rulebook text this
project has blocks it outright), just at double cost, the same
mechanic Phase 4 already built for this exact case. For a province
``GameState`` never bridged from a real world file
(``recruit_type_1 is None``, e.g. every hand-built test fixture), this
falls back to the pre-existing race-compatibility approximation
unchanged -- no real per-province list to check yet, so nothing to
enforce more precisely.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ak_engine.models.army_type import OVERFLIGHT_AIR, ArmyType
from ak_engine.models.game_state import ArmyState, GameState
from ak_engine.models.office import Office
from ak_engine.turn.combat import Quality
from ak_engine.turn.office_holder import resolve_office_holder
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
    treat_blocked: list[ArmyType] = field(default_factory=list)
    territory_blocked: list[ArmyType] = field(default_factory=list)
    total_gold_spent: int = 0


def execute_recruit(state: GameState, kingdom_id: int, leader_id: int, request: RecruitRequest) -> RecruitExecutionResult:
    """Price, limit-check, and actually recruit every type in ``request``.

    Recruits at the acting leader's current location. Newly recruited
    armies are commanded by ``request.leader_id`` (the phase's decoded
    target leader, possibly None = unled/garrison) -- **provided that
    leader is co-located with the acting leader** (rulebook [3.4]: "Any
    character in the province may lead the armies, or they can be
    placed under the garrison commander"). A ``request.leader_id`` that
    doesn't exist as a ``LeaderState`` at all, or exists but is in a
    different province, falls back to unled/garrison command
    (``commanded_by=None``) instead -- the same silent "skip, don't
    raise" convention already used for Disband/Fire/Pick_Up's own
    co-location checks (Phase 40), rather than assigning command to a
    character who couldn't plausibly have issued this order.
    """

    leader = state.leaders[leader_id]
    location = leader.location
    province = state.provinces[location]
    kingdom = state.kingdoms[kingdom_id]

    target_leader = state.leaders.get(request.leader_id) if request.leader_id is not None else None
    commanded_by = request.leader_id if target_leader is not None and target_leader.location == location else None

    at_own_former_home = location == kingdom.home_province
    in_ally_territory = (
        province.owner_kingdom_id is not None
        and province.owner_kingdom_id != kingdom_id
        and state.is_allied(province.owner_kingdom_id, kingdom_id)
    )
    # Own home province: still self-owned. A former home province now
    # owned by an ally is a distinct, better-treated case (Phase 262,
    # RULES.AK [3.4]) -- not merely "not the home-province bonus".
    is_home_province = at_own_former_home and province.owner_kingdom_id == kingdom_id
    is_former_home_province_now_allied = at_own_former_home and in_ally_territory

    result = RecruitExecutionResult(request=request)

    if in_ally_territory and not state.has_treat_permission(province.owner_kingdom_id, kingdom_id):
        result.treat_blocked.extend(request.army_types)
        return result

    wingman_holder = resolve_office_holder(state, Office.WINGMAN)
    leader_is_wingman = wingman_holder is not None and wingman_holder.leader_id == leader_id

    for army_type in request.army_types:
        if province.recruit_type_1 is not None:
            is_native = army_type in (province.recruit_type_1, province.recruit_type_2)
        else:
            is_native = is_army_type_compatible_with_race(army_type, province.race)
        try:
            resolution = resolve_recruit(
                army_type,
                province.race,
                is_home_province=is_home_province,
                is_native_to_province=is_native,
                in_ally_territory=in_ally_territory,
                is_former_home_province_now_allied=is_former_home_province_now_allied,
            )
        except IncompatibleRaceError:
            result.incompatible.append(army_type)
            continue

        wingman_bonus = 1 if leader_is_wingman and army_type in OVERFLIGHT_AIR and is_native else 0
        already_this_turn = province.recruited_this_turn.get(army_type, 0)
        if already_this_turn >= resolution.max_units + wingman_bonus:
            result.limit_blocked.append(army_type)
            continue

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
        can_levy = province.owner_kingdom_id == kingdom_id or in_ally_territory
        if mercenary is None and not can_levy:
            result.territory_blocked.append(army_type)
            continue

        unit_cost = resolution.gold_per_unit + resolution.ally_fee_per_unit
        if kingdom.treasury < unit_cost:
            result.gold_blocked.append(army_type)
            continue

        kingdom.treasury -= unit_cost
        if in_ally_territory and resolution.ally_fee_per_unit:
            state.kingdoms[province.owner_kingdom_id].treasury += resolution.ally_fee_per_unit

        if mercenary is not None:
            mercenary.kingdom_id = kingdom_id
            mercenary.commanded_by = commanded_by
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
                    commanded_by=commanded_by,
                    movement_points=0,
                )
            )
            hired = False
        province.recruited_this_turn[army_type] = already_this_turn + 1

        result.recruited.append(RecruitedUnit(army_id=army_id, army_type=army_type, gold_paid=unit_cost, hired=hired))
        result.total_gold_spent += unit_cost

    return result
