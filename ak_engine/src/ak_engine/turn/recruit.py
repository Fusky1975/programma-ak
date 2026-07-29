"""Recruit-action resolution (rulebook [3.4]).

Scope: the deterministic race-compatibility, per-turn recruit limit, and
gold-cost rules only. Actually executing a Recruit order -- choosing a
leader, updating a kingdom's treasury and army roster, checking whether an
Average-or-better mercenary army is present to hire instead of levying from
the populace -- needs kingdom/treasury/mercenary-pool state this module
doesn't carry, and lives in ``turn/recruit_execution.py`` instead (Phase
15/16). The ally "Treat" order precondition also lives there (Phase 261,
``GameState.has_treat_permission()``) -- this module's own
``in_ally_territory`` parameter only ever affects pricing/crediting, never
whether recruiting is allowed to proceed at all.

**Phase 262 -- the "former home province, now an ally's" 4-unit bonus**:
RULES.AK [3.4], same paragraph as the ally-fee/Treat text: "Also, if you
are recruiting in your former home province which is now your ally's
province, you can recruit 4 units, and they will start as Average
units." ``is_former_home_province_now_allied`` is a separate flag from
``is_home_province`` (not merely its negation-of-ownership) because the
two are mutually exclusive by construction in the caller
(``turn/recruit_execution.py``): ``is_home_province`` there now also
requires *current* self-ownership, whereas this flag requires the
location to still be the kingdom's own (never-reassigned, see
``KingdomState.home_province``'s own field) home province while
currently owned by an ally instead.

**What this module can't answer**: ``is_army_type_compatible_with_race()``
below only answers "can this army type be recruited in a province of
this race at all" -- never "which exactly two `ArmyType`s does the real
Recruiting Types table cell for *this specific province* name"
(``Mod_PAT(px,py,0)``/``Mod_PAT(px,py,1)``). `Mod_PAT` is never defined
anywhere in the available Pascal archive -- confirmed absent, re-audited
and closed as of Phase 275 (``report/turn_report.py
compose_letter_report()``'s own Phase 275 addendum has the full
declaration-search citation; ``describe_provinces_report()``'s own
docstring is the other consumer of this same gap).
"""

from __future__ import annotations

from dataclasses import dataclass

from ak_engine.models.army_type import ARMY_TABLE, MONSTROUS_ARMY_RACE, ArmyType
from ak_engine.models.race import HUMANOID_RACES, Race

DEFAULT_RECRUIT_LIMIT = 1
HOME_PROVINCE_RECRUIT_LIMIT = 2
GARRISON_HUMANOID_PROVINCE_LIMIT = 2
# RULES.AK [3.4]: "if you are recruiting in your former home province
# which is now your ally's province, you can recruit 4 units."
FORMER_HOME_PROVINCE_ALLY_RECRUIT_LIMIT = 4


class IncompatibleRaceError(ValueError):
    """Raised when an army type can't be recruited in a province of that race."""


@dataclass(slots=True)
class RecruitResolution:
    max_units: int
    gold_per_unit: int
    ally_fee_per_unit: int
    is_double_cost: bool


def is_army_type_compatible_with_race(army_type: ArmyType, province_race: Race) -> bool:
    monstrous_race = MONSTROUS_ARMY_RACE.get(army_type)
    if monstrous_race is not None:
        return province_race == monstrous_race
    return province_race in HUMANOID_RACES


def recruit_limit(
    army_type: ArmyType,
    *,
    is_home_province: bool,
    province_race: Race,
    is_former_home_province_now_allied: bool = False,
) -> int:
    """Max number of this army type recruitable from the populace this turn.

    Normally 1; a King's home province allows 2 of each type; Garrison
    units get the same "2 per gameturn" allowance in *any* humanoid
    province, home or not; a *former* home province now owned by an
    ally allows 4 (Phase 262, RULES.AK [3.4]).
    """

    if is_former_home_province_now_allied:
        return FORMER_HOME_PROVINCE_ALLY_RECRUIT_LIMIT
    if is_home_province:
        return HOME_PROVINCE_RECRUIT_LIMIT
    if army_type is ArmyType.GARRISON and province_race in HUMANOID_RACES:
        return GARRISON_HUMANOID_PROVINCE_LIMIT
    return DEFAULT_RECRUIT_LIMIT


def resolve_recruit(
    army_type: ArmyType,
    province_race: Race,
    *,
    is_home_province: bool,
    is_native_to_province: bool,
    in_ally_territory: bool = False,
    is_former_home_province_now_allied: bool = False,
) -> RecruitResolution:
    """Resolve the limit and cost for recruiting one army type in one province.

    Raises ``IncompatibleRaceError`` if the province's race can't field
    that army type at all (native or not).
    """

    if not is_army_type_compatible_with_race(army_type, province_race):
        raise IncompatibleRaceError(
            f"{army_type.name} can't be recruited in a {province_race.name} province"
        )

    base_pay = ARMY_TABLE[army_type].pay
    return RecruitResolution(
        max_units=recruit_limit(
            army_type,
            is_home_province=is_home_province,
            province_race=province_race,
            is_former_home_province_now_allied=is_former_home_province_now_allied,
        ),
        gold_per_unit=base_pay if is_native_to_province else base_pay * 2,
        ally_fee_per_unit=1 if in_ally_territory else 0,
        is_double_cost=not is_native_to_province,
    )
