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

**Grand Marshal/Grand Admiral's own recruitment bonuses (Phase 488,
"CARICHE E ABILITA.txt")**: "[Grand Marshal] will allow you to
recruit one extra unit of any army type which can move overland
(except for flying units)... [Grand Admiral] will allow you to recruit
one extra unit of any army type which can move from sea to sea (except
for flying units)" -- the same "acting leader currently holds this
Office, raise that one type's own per-turn cap by one, gated on
``is_native``" shape as Wingman's own bonus directly above, extended to
the other two Offices whose real perk is also phrased as "recruit one
extra unit." The three Offices partition ``ArmyType`` cleanly along the
domain split this project already uses everywhere else (``models/
army_type.py OVERFLIGHT_AIR``/``OVERFLIGHT_SEA``): Wingman's own bonus
already claims the 2 flying types; Grand Admiral's own "sea to sea"
types are the 3 already-classified naval movers (``OVERFLIGHT_SEA`` --
Whales, Mermen -- plus ``ArmyType.FLEET``, the one naval type that set
doesn't itself cover); Grand Marshal's own "overland" types are simply
whatever's left -- every other, non-flying, non-naval type. A leader
holding more than one of these three Offices at once (rare, but the
rulebook never forbids it -- "uno stesso personaggio puo aggiudicarsene
piu di una," rulebook [10.1]) gets each qualifying type's own bonus
independently; the three domains are mutually exclusive, so no army
type can ever double-count towards more than one Office's own bonus.

**Dinosaur armies (Phase 691, `AdvancedAbility.DRUIDIC_DINOSAURS`)**:
a real Advanced Ability precondition beyond the Race.ELVEN race gate
(``turn/recruit.py is_army_type_compatible_with_race()``) -- checked
right after the existing ``IncompatibleRaceError`` catch, since the
ability is a separate, independent requirement, not encoded in the
race check itself. A fresh levy's quality is ``Quality.AVERAGE`` (the
usual baseline) only when the acting leader's own Druid skill is
``>= DINOSAUR_FULL_QUALITY_DRUID_SKILL`` (5, "For full quality, Druid
level 5 is required"); below that, a documented interpretation steps
it down to ``Quality.GREEN`` instead -- see that constant's own
docstring. A successful Dinosaur recruit also sets ``ProvinceState.
recruit_locked_this_turn = True`` ("no further units may be recruited
in the province that turn"), reported via ``RecruitExecutionResult.
province_locked``. **Bug fix**: this was originally checked only once,
before the per-``army_type`` loop -- correctly blocking a later,
*separate* ``execute_recruit()`` call the same turn, but not a *later
army type in the same request* (a single real Recruit order can list
several types at once, ``turn/recruit_decode.py``'s own ordinal list),
letting e.g. ``[DINOSAURS, BOWMEN]`` in one order still recruit the
Bowmen after the Dinosaur locked the province. Now re-checked at the
top of every loop iteration, so the lock takes effect immediately once
set, within the same call too.

**Phase 980 addendum, user-confirmed: "only in place of elven EL, LC or
HC" is a real province-level precondition, not just descriptive
context.** The earlier reading above was right to reject a literal
cross-type slot-*consumption* formula (recruiting a Dinosaur still never
decrements a different type's own ``recruited_this_turn`` counter -- no
source gives that mechanism, and none is invented here either), but it
stopped short of implementing the plainer, confirmed half of the same
sentence: the province must currently offer Elephants, Light Cavalry or
Heavy Cavalry as one of its own two recruit slots (``ProvinceState.
recruit_type_1``/``recruit_type_2``) for Dinosaurs to be recruitable
there at all -- a real *precondition* check, independent of the
``AdvancedAbility.DRUIDIC_DINOSAURS`` leader gate right above it.
``_DINOSAUR_REQUIRED_PROVINCE_SLOT_TYPES`` below names the three
qualifying types; blocked via the new ``RecruitExecutionResult.
elven_slot_required``. Only enforced when this project actually has
real per-province slot data (``recruit_type_1 is not None``, the same
condition ``is_native_to_province`` above already gates on) -- a hand-
built test fixture or any other caller that never populated real slots
has no data to check this against, so the gate is silently satisfied
rather than blocking everything, the same "approximate, don't invent,
when real data is missing" precedent `is_native`'s own fallback already
set.

**Also Phase 980: the real "Race: Saurian" fact (already quoted
verbatim in `models/advanced_ability.py ADVANCED_ABILITY_DESCRIPTION
[DRUIDIC_DINOSAURS]`` since Phase 691, but never wired anywhere) now
actually applies.** `models/army_type.py MONSTROUS_ARMY_RACE` gains
``ArmyType.DINOSAURS: Race.SAURIAN`` -- every Dinosaur army now reports
and fights as Saurian, not the owning (necessarily Elven, per the race
gate above) Kingdom's own race. A real, user-supplied reverse-
engineering report of ``REPORTS.PAS`` independently describes this as a
report-generation-time correction (an Elven-race Dinosaur army gets
mutated to Saurian the first time a report runs, with a one-time "The
race of Dinosaurs has changed from Elven to Saurian" announcement) --
not reproduced here verbatim: this project's armies are created with
their final display race up front (`ArmyState` has no mutable race
field of its own, and every other ``MONSTROUS_ARMY_RACE`` entry already
works this way, fixed at creation, never corrected later), so there is
no "was Elven, became Saurian" moment for an announcement to narrate in
the first place -- a Dinosaur army is simply Saurian from the moment
it's recruited.

**Non-native double-cost recruiting now needs an existing unit of that
type (2026-10-28), RULES.AK [3.4], sourced directly from the user**: "se
non è possibile reclutare un certo tipo di unità militare perché non
previsto per la popolazione nativa, si può comunque effettuare
l'arruolamento se il comandante, o il personaggio a favore del quale
viene dato l'ordine, ha già ai suoi ordini un'altra unità del tipo."
Through this phase, Phase 407's own double-cost path (above) applied
unconditionally to any race-compatible-but-non-native type -- a real gap,
since the rulebook ties that option to a precondition, not an
unconditional price bump. ``turn/recruit.py resolve_recruit()`` now takes
``commander_already_has_type`` and raises a new, distinct
``NonNativeTypeNotYetOwnedError`` (not ``IncompatibleRaceError`` -- the
race *is* compatible here, only the ownership precondition fails) when
it's ``False``; this module computes it fresh on every loop iteration
(so a unit of that type recruited earlier in the very same request also
counts) by scanning ``state.armies`` for one already ``commanded_by``
the resolved ``commanded_by`` of this order. A Garrison-targeted order
(``commanded_by is None``) has no commander roster to check against, so
this precondition can never be satisfied for it -- the rulebook's own
wording names "the commander, or the [...] favored character," never the
garrison, so a Garrison-targeted recruit of a non-native type is always
blocked, reported via the new ``RecruitExecutionResult.non_native_type_
not_owned``, same "no sourced narrative template yet" convention as
every other blocked-request list (see ``report/turn_report.py describe_
recruit()``'s own docstring).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ak_engine.models.advanced_ability import AdvancedAbility
from ak_engine.models.army_type import OVERFLIGHT_AIR, OVERFLIGHT_SEA, ArmyType
from ak_engine.models.enums import Ability
from ak_engine.models.game_state import ArmyState, GameState
from ak_engine.models.office import Office
from ak_engine.turn.combat import Quality
from ak_engine.turn.discovery_effects import effective_skill_level
from ak_engine.turn.office_holder import resolve_office_holder
from ak_engine.turn.recruit import (
    IncompatibleRaceError,
    NonNativeTypeNotYetOwnedError,
    is_army_type_compatible_with_race,
    resolve_recruit,
)
from ak_engine.turn.recruit_decode import RecruitRequest

# Phase 691: Druid skill required for full Dinosaur quality
# (`AdvancedAbility.DRUIDIC_DINOSAURS`'s own real description --
# "For full quality, Druid level 5 is required"). Below this, a
# documented interpretation steps the fresh levy's quality down one
# tier (`Quality.GREEN` instead of the universal `Quality.AVERAGE`
# baseline), mirroring this project's own "shortfall steps quality
# down by tiers" convention without reusing `compute_druidic_
# shortfall()`'s own differently-scoped kingdom-race check.
DINOSAUR_FULL_QUALITY_DRUID_SKILL = 5

# Phase 980: `AdvancedAbility.DRUIDIC_DINOSAURS`'s own real description --
# "only in place of elven EL, LC or HC" -- the three army types whose
# own presence in a province's recruit slots unlocks Dinosaur recruiting
# there (user-confirmed as a precondition check, not a slot-consumption
# formula -- see this module's own Phase 980 docstring addendum).
_DINOSAUR_REQUIRED_PROVINCE_SLOT_TYPES = frozenset({ArmyType.ELEPHANTS, ArmyType.LT_CAVALRY, ArmyType.HVY_CAVALRY})


@dataclass(slots=True)
class RecruitedUnit:
    army_id: int
    army_type: ArmyType
    gold_paid: int
    hired: bool = False  # True = an existing mercenary was hired, not freshly levied
    # Phase 645: the ally-territory recruiting fee (rulebook [3.4], "you
    # will need to pay him 1 gold for each unit recruited") already
    # folded into `gold_paid` above -- kept separate here too so
    # `report/turn_report.py describe_recruit()` can render the real
    # `_AAPay` sentence without re-deriving it from `province`/`state`.
    ally_fee_paid: int = 0


@dataclass(slots=True)
class RecruitExecutionResult:
    request: RecruitRequest
    recruited: list[RecruitedUnit] = field(default_factory=list)
    limit_blocked: list[ArmyType] = field(default_factory=list)
    gold_blocked: list[ArmyType] = field(default_factory=list)
    incompatible: list[ArmyType] = field(default_factory=list)
    treat_blocked: list[ArmyType] = field(default_factory=list)
    territory_blocked: list[ArmyType] = field(default_factory=list)
    # Phase 691: `AdvancedAbility.DRUIDIC_DINOSAURS`'s own "no further
    # units may be recruited in the province that turn" -- a whole-order
    # block distinct from `limit_blocked` (a per-type cap), triggered by
    # `ProvinceState.recruit_locked_this_turn` from an earlier successful
    # Dinosaur recruit this same turn.
    province_locked: list[ArmyType] = field(default_factory=list)
    # Phase 980: `AdvancedAbility.DRUIDIC_DINOSAURS`'s own "only in place
    # of elven EL, LC or HC" -- a separate, province-level precondition
    # from `province_locked` above (which fires only *after* a Dinosaur
    # has already been recruited this turn); this one blocks the very
    # first attempt when the province's own recruit slots don't qualify.
    elven_slot_required: list[ArmyType] = field(default_factory=list)
    # Sourced directly from the user (2026-10-28), RULES.AK [3.4]: a
    # non-native type is recruitable at double cost only if the
    # commander already has another unit of that same type under their
    # command; without that, the type isn't recruitable here at all --
    # a separate reason from `incompatible` (race-incompatible), so it
    # gets its own bucket, matching this dataclass's own established
    # one-field-per-distinct-block-reason convention.
    non_native_type_not_owned: list[ArmyType] = field(default_factory=list)
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

    **Phase 825 bug fix**: the *acting* leader (the one issuing this
    Recruit order) was resolved via a bare ``state.leaders[leader_id]``
    lookup, unconditionally -- a leader who died earlier in the same
    turn can still have a later-phase Recruit order dispatched for
    them, since ``turn/plan_dispatch.py``'s own per-phase loop has no
    leader-liveness gate of its own (the same "dead leader with a
    stale later-phase order" gap already fixed for Leave/Pick_Up
    (Phase 821), Practice (Phase 822), Hire (Phase 823), and ASpy
    (Phase 824)). Previously this raised an unhandled ``KeyError``,
    caught upstream by ``run_leader_plan()``'s own top-level
    ``try``/``except`` (so it never crashed the whole turn), but an
    opaque exception instead of a clean, empty result. Resolved via
    ``.get()``, returning a fully-default ``RecruitExecutionResult(
    request=request)`` (nothing recruited, nothing blocked-for-a-
    specific-reason) when the acting leader no longer exists -- none of
    this dataclass's own existing fields (``recruited``/``limit_
    blocked``/``gold_blocked``/``incompatible``/``treat_blocked``/
    ``territory_blocked``/``province_locked``) semantically represents
    "the acting leader is dead, the whole order never started", so this
    mirrors ``execute_practice()``'s own Phase 822 precedent of reusing
    an already-established "no-op" result shape rather than inventing a
    new category. The two adjacent bare indices right below this guard
    (``state.provinces[location]``, ``state.kingdoms[kingdom_id]``) are
    out of scope for this same bug class -- ``location`` is the now-
    guaranteed-live ``leader``'s own current position (always a real
    province by construction), and ``kingdom_id`` is the dispatcher's
    own parameter, not a value carried stale from an earlier phase.
    """

    leader = state.leaders.get(leader_id)
    if leader is None:
        return RecruitExecutionResult(request=request)
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
    marshal_holder = resolve_office_holder(state, Office.MARSHAL)
    leader_is_marshal = marshal_holder is not None and marshal_holder.leader_id == leader_id
    admiral_holder = resolve_office_holder(state, Office.ADMIRAL)
    leader_is_admiral = admiral_holder is not None and admiral_holder.leader_id == leader_id
    # Phase 663: Chief of Staff's own -1 gold discount (below), and
    # Neutral King's own separate "recruit mercenaries for 1 gold" flat
    # override (see the mercenary/fresh-levy branch below -- the real
    # text names mercenaries specifically, not fresh levies).
    chief_of_staff_holder = resolve_office_holder(state, Office.CHIEF_OF_STAFF)
    leader_is_chief_of_staff = chief_of_staff_holder is not None and chief_of_staff_holder.leader_id == leader_id
    neutral_king_holder = resolve_office_holder(state, Office.NEUTRAL_KING)
    leader_is_neutral_king = neutral_king_holder is not None and neutral_king_holder.leader_id == leader_id

    for army_type in request.army_types:
        # Phase (bug fix): re-checked on every iteration, not just once
        # before the loop -- "no further units may be recruited in the
        # province that turn" must also block a *later* army type in this
        # SAME request once an earlier Dinosaur recruit in this same call
        # has already set the lock, matching a real single Recruit order
        # that lists several types together (`turn/recruit_decode.py`
        # already decodes an ordinal list, not just one type per order).
        # Checking only once up front let a request like [DINOSAURS,
        # BOWMEN] recruit the Bowmen anyway, contradicting the rule.
        if province.recruit_locked_this_turn:
            result.province_locked.append(army_type)
            continue
        if province.recruit_type_1 is not None:
            is_native = army_type in (province.recruit_type_1, province.recruit_type_2)
        else:
            is_native = is_army_type_compatible_with_race(army_type, province.race)
        # Sourced directly from the user (2026-10-28), RULES.AK [3.4]:
        # "il comandante, o il personaggio a favore del quale viene dato
        # l'ordine, ha già ai suoi ordini un'altra unità del tipo" --
        # checked against `commanded_by` (the actual resolved commander
        # for this order, already co-location-checked above), re-scanned
        # fresh on every loop iteration so a unit of this same type
        # recruited earlier in this SAME request also counts. A
        # Garrison-targeted order (`commanded_by is None`) has no
        # commander roster to check, so this precondition can never be
        # met for it -- the literal text ties the exception to a named
        # commander/favored character, not to the garrison.
        #
        # Dinosaurs are exempt: their own non-native-race eligibility is
        # already fully governed by a separate, previously user-confirmed
        # precondition chain (`AdvancedAbility.DRUIDIC_DINOSAURS` plus the
        # province's own Elephants/Lt Cavalry/Hvy Cavalry slot requirement,
        # Phase 691/980 above) -- that chain *is* this army type's own real
        # "why a non-native type is recruitable here" story, not the
        # generic one this new check targets. Layering the new check on
        # top as well would make a first Dinosaur unit permanently
        # unrecruitable anywhere (nobody can ever already own one), which
        # would silently break that already-shipped, already-confirmed
        # mechanic.
        commander_already_has_type = army_type is ArmyType.DINOSAURS or (
            commanded_by is not None
            and any(army.commanded_by == commanded_by and army.army_type is army_type for army in state.armies.values())
        )
        try:
            resolution = resolve_recruit(
                army_type,
                province.race,
                is_home_province=is_home_province,
                is_native_to_province=is_native,
                in_ally_territory=in_ally_territory,
                is_former_home_province_now_allied=is_former_home_province_now_allied,
                chief_of_staff_discount=leader_is_chief_of_staff,
                commander_already_has_type=commander_already_has_type,
            )
        except IncompatibleRaceError:
            result.incompatible.append(army_type)
            continue
        except NonNativeTypeNotYetOwnedError:
            result.non_native_type_not_owned.append(army_type)
            continue

        # Phase 691: the race gate (Race.ELVEN, checked above via
        # is_army_type_compatible_with_race()) is necessary but not
        # sufficient -- `AdvancedAbility.DRUIDIC_DINOSAURS` is a real,
        # separate precondition ("The Druid can now recruit Dinosaur
        # armies").
        if army_type is ArmyType.DINOSAURS and AdvancedAbility.DRUIDIC_DINOSAURS not in leader.advanced_abilities:
            result.incompatible.append(army_type)
            continue

        # Phase 980: "only in place of elven EL, LC or HC" -- a real
        # province-level precondition, independent of the leader-level
        # ability gate just above. Only enforced when real per-province
        # slot data exists (recruit_type_1 is not None), matching
        # is_native's own fallback a few lines up.
        if (
            army_type is ArmyType.DINOSAURS
            and province.recruit_type_1 is not None
            and province.recruit_type_1 not in _DINOSAUR_REQUIRED_PROVINCE_SLOT_TYPES
            and province.recruit_type_2 not in _DINOSAUR_REQUIRED_PROVINCE_SLOT_TYPES
        ):
            result.elven_slot_required.append(army_type)
            continue

        wingman_bonus = 1 if leader_is_wingman and army_type in OVERFLIGHT_AIR and is_native else 0
        is_naval_type = army_type in OVERFLIGHT_SEA or army_type is ArmyType.FLEET
        marshal_bonus = 1 if leader_is_marshal and army_type not in OVERFLIGHT_AIR and not is_naval_type and is_native else 0
        admiral_bonus = 1 if leader_is_admiral and is_naval_type and is_native else 0
        already_this_turn = province.recruited_this_turn.get(army_type, 0)
        if already_this_turn >= resolution.max_units + wingman_bonus + marshal_bonus + admiral_bonus:
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

        # Phase 663: Neutral King's own real "recruit mercenaries for
        # just one gold" flat override -- names mercenaries specifically
        # ("although maintenance costs remain normal"), so it only
        # applies to this branch (mercenary is not None), never a fresh
        # levy from the populace. Overrides gold_per_unit outright (a
        # flat "one gold", not a further discount stacked on Chief of
        # Staff's own -1) -- the ally fee (a separate real surcharge for
        # recruiting in someone else's territory) still applies on top.
        gold_per_unit = 1 if mercenary is not None and leader_is_neutral_king else resolution.gold_per_unit
        unit_cost = gold_per_unit + resolution.ally_fee_per_unit
        if kingdom.treasury < unit_cost:
            result.gold_blocked.append(army_type)
            continue

        kingdom.treasury -= unit_cost
        if in_ally_territory and resolution.ally_fee_per_unit:
            state.kingdoms[province.owner_kingdom_id].treasury += resolution.ally_fee_per_unit

        if mercenary is not None:
            mercenary.kingdom_id = kingdom_id
            mercenary.commanded_by = commanded_by
            # Bug fix (2026-10-25): a hired mercenary transitions out of
            # the real `astate=Mercenary` state -- it's no longer
            # "available to Recruit" (see `ArmyState.is_mercenary`'s own
            # docstring) -- matching `Known_Merc`'s own real formula,
            # which already requires `astate[an] = Mercenary`.
            mercenary.is_mercenary = False
            army_id = mercenary.army_id
            hired = True
        else:
            army_id = state.new_army_id()
            if army_type is ArmyType.DINOSAURS and effective_skill_level(state, leader, Ability.DRUID) < DINOSAUR_FULL_QUALITY_DRUID_SKILL:
                fresh_levy_quality = Quality.GREEN
            else:
                fresh_levy_quality = Quality.AVERAGE
            state.add_army(
                ArmyState(
                    army_id=army_id,
                    kingdom_id=kingdom_id,
                    army_type=army_type,
                    quality=fresh_levy_quality,
                    location=location,
                    commanded_by=commanded_by,
                    movement_points=0,
                    recruited_this_turn=True,
                )
            )
            hired = False
        province.recruited_this_turn[army_type] = already_this_turn + 1
        if army_type is ArmyType.DINOSAURS:
            province.recruit_locked_this_turn = True

        result.recruited.append(
            RecruitedUnit(
                army_id=army_id,
                army_type=army_type,
                gold_paid=unit_cost,
                hired=hired,
                ally_fee_paid=resolution.ally_fee_per_unit,
            )
        )
        result.total_gold_spent += unit_cost

    return result
