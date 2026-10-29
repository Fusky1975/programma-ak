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
anywhere in the available Pascal archive as a *formula* -- confirmed
absent, re-audited and closed as of Phase 275 (``report/turn_report.py
compose_letter_report()``'s own Phase 275 addendum has the full
declaration-search citation; ``describe_provinces_report()``'s own
docstring is the other consumer of this same gap). The *data* itself
was recovered a different way (Phase 278, straight from a real world
file) and is now read by ``turn/recruit_execution.py`` when known --
see that module's own Phase 407 addendum. This module's own
``is_army_type_compatible_with_race()`` still gates whether an army
type can be recruited *at all*; the caller decides native-vs-double-
cost from the real per-province list when it has one, falling back to
this function's own broader approximation otherwise.
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


class NonNativeTypeNotYetOwnedError(ValueError):
    """Raised when a non-native (race-compatible, but not province-listed)
    army type is requested and the commander doesn't already have another
    unit of that same type under their command -- sourced directly from
    the user (2026-10-28): "si può comunque effettuare l'arruolamento se
    il comandante, o il personaggio a favore del quale viene dato
    l'ordine, ha già ai suoi ordini un'altra unità del tipo" -- a real
    precondition this project's own earlier reading of [3.4] never
    enforced (``resolve_recruit()`` used to double the price for any
    race-compatible-but-non-native type unconditionally). Without an
    existing unit of that type, the type simply isn't recruitable in
    this province at all, native or not.
    """


@dataclass(slots=True)
class RecruitResolution:
    max_units: int
    gold_per_unit: int
    ally_fee_per_unit: int
    is_double_cost: bool


# Phase 691: `AdvancedAbility.DRUIDIC_DINOSAURS`'s own real description
# -- "trainable only by skilled Elven riders" -- gates Dinosaurs on
# `Race.ELVEN` specifically, not `MONSTROUS_ARMY_RACE` (that dict's own
# real semantic is "native to and exclusive to one non-humanoid race's
# own province"; Dinosaurs are Elven-*trained*, a skill/ability gate
# checked separately in `turn/recruit_execution.py`, not a province-
# nativity gate).
_ELVEN_ONLY_ARMY_TYPES = frozenset({ArmyType.DINOSAURS})


# Phase 929: the symmetric race-compatibility reading below (a monstrous
# type only in its own native province, a humanoid-compatible type only
# in a humanoid province) is confirmed directly by the user -- see
# `models/army_type.py`'s own Phase 929 addendum, next to
# `MONSTROUS_ARMY_RACE`, for the full quote. No longer an interpretation.
def is_army_type_compatible_with_race(army_type: ArmyType, province_race: Race) -> bool:
    if army_type in _ELVEN_ONLY_ARMY_TYPES:
        return province_race is Race.ELVEN
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
    chief_of_staff_discount: bool = False,
    commander_already_has_type: bool = False,
) -> RecruitResolution:
    """Resolve the limit and cost for recruiting one army type in one province.

    Raises ``IncompatibleRaceError`` if the province's race can't field
    that army type at all (native or not).

    Raises ``NonNativeTypeNotYetOwnedError`` if the type is race-
    compatible but not native to this province and
    ``commander_already_has_type`` is ``False`` -- RULES.AK [3.4], sourced
    directly from the user (2026-10-28): "se non è possibile reclutare un
    certo tipo di unità militare perché non previsto per la popolazione
    nativa, si può comunque effettuare l'arruolamento se il comandante,
    o il personaggio a favore del quale viene dato l'ordine, ha già ai
    suoi ordini un'altra unità del tipo." Without that pre-existing unit,
    the type isn't recruitable in this province at all -- the double
    cost below only ever applies once this precondition holds.

    ``chief_of_staff_discount`` (Phase 663): `models/office.py OFFICE_
    TITLE_DESCRIPTION[Office.CHIEF_OF_STAFF]`'s own real "effect_while_
    held" text -- "any unit recruited by <2 will get a discount on
    weapons and armor, so it will cost one less gold to recruit (but not
    to maintain.) Garrison units, for example, < can recruit for free.
    When recruiting a unit type not native to a province, the discount
    is taken before the recruitment cost is doubled." -- ``-1`` applied
    to ``base_pay`` (floored at 0, matching the real "free Garrison"
    example -- Garrison's own real base pay is 1) *before* the native/
    non-native doubling below, exactly per that last sentence.
    Caller-resolved (the same "pure function, Office context supplied
    by the caller" convention `is_native_to_province`/`in_ally_
    territory` already use) -- see `turn/recruit_execution.py
    execute_recruit()`.
    """

    if not is_army_type_compatible_with_race(army_type, province_race):
        raise IncompatibleRaceError(
            f"{army_type.name} can't be recruited in a {province_race.name} province"
        )
    if not is_native_to_province and not commander_already_has_type:
        raise NonNativeTypeNotYetOwnedError(
            f"{army_type.name} isn't native to this province and the commander "
            "doesn't already have another unit of that type"
        )
    if army_type not in ARMY_TABLE:
        # Bug fix (crash): 8 real ArmyType ordinals (Vampires, Marauders,
        # Shamans, Crossbow, Javelins, Artillery, Spiders, D_Turtle --
        # models/army_type.py's own Phase 383 addendum) never appear in
        # the rulebook's own Army Type Table [6.3], so ARMY_TABLE has no
        # entry -- an honest sourcing gap, not something to invent a pay
        # cost for. is_army_type_compatible_with_race() still lets them
        # through in any ordinary humanoid province (none of them has a
        # MONSTROUS_ARMY_RACE entry either), so the bare `.pay` lookup
        # below used to raise an unhandled KeyError the instant a player
        # named one of these ordinals in a Recruit order. Treated the
        # same as an incompatible-race rejection: there's no rulebook
        # data to recruit by, so it can't be recruited, full stop.
        raise IncompatibleRaceError(f"{army_type.name} has no rulebook recruiting cost and can't be recruited")

    base_pay = ARMY_TABLE[army_type].pay
    if chief_of_staff_discount:
        base_pay = max(0, base_pay - 1)
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
