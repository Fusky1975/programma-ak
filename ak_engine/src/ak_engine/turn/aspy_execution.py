"""ASpy (Spy Province) execution -- rulebook [3.14] (quoted in full,
``RULES.AK`` ~line 500): "A character Spying on a province will report on
its owner, owners of adjacent provinces, taxation of the province, army
types recruitable there, and whether the province is the capital province
of the Kingdom... A character may only Spy on a province he is actually
in."

Closes the report-generation half of Phase 26's ASpy gap (the decode-only
half, and the reasons it stayed decode-only, live in
``turn/aspy_defend_decode.py``): "intelligence-report content ... needs a
report-generation system this project doesn't have at all" was true when
that was written, but Phases 58/61 now give this project exactly that --
``report/prose.py``'s rendering engine and ``report/turn_report.py``'s
first real consumer. This module only builds the *data* a spy report
needs (mirroring the "data first, prose later" split those two phases
already established for battle outcomes and spells); rendering it into
English sentences was that natural follow-up -- closed since ``report/
turn_report.py describe_aspy()`` (Phase 115/213/400), wired into
``describe_turn_results()``'s own real ``ActionCode.ASPY`` branch.

**"A character may only Spy on a province he is actually in"** is read
literally: this module always reports on the caster's own current
``LeaderState.location``, never on ``SpyProvinceRequest.target_province``.
That raw field is deliberately *not* decoded or cross-checked here --
``turn/aspy_defend_decode.py``'s own docstring already flags that no
Pascal source confirms whether it shares ``turn/hex_numbering.py``'s
empirically-inferred numbering space or the host's separate internal
``x*XMULT+y`` arithmetic. Trusting the rule's own "he is actually in" text
over an unconfirmed number space is the same kind of documented,
conservative choice this project has made before (e.g. Recruit and
Practice already resolve against the acting leader's own location rather
than a player-typed target).

**Taxation of the province is reported as of Phase 253, and finally
subject to a real margin of error as of Phase 265.** ``turn/
tax_base.py province_tax_yield()`` (Phase 222-224) computes the
province's own real, exact figure -- but [3.14] itself is explicit
that "taxation values ... are subject to a margin of error which
decreases with increasing skill in Spy ability," and Phase 253 shipped
this field passing that exact value straight through unperturbed, the
same gap the field's own name ("estimate") already implied but never
delivered on. **Phase 265 closes it**: ``turn/spy_table.py
estimate_reported_value()`` (the [4.33] Spy Table's own "Margin of
Error of Spy Reports" column, previously modeled as raw data but never
exposed) perturbs the exact yield by the caster's own Spy-skill-scaled
margin before it reaches ``SpyReport.tax_estimate`` -- see that
module's own docstring for why the exact perturbation shape (a
uniform, symmetric, floor-at-0 offset) is this project's own documented
design choice, the percentages themselves being the only sourced part.
``None`` (not a guessed zero, and never perturbed) whenever
``ProvinceState.tax`` was never recorded, the same "no data isn't a
true zero" convention this module already uses everywhere else.
``execute_aspy()`` reads the caster's own Spy skill the same
``leader.skills is None -> 0`` placeholder convention ``turn/
trail_execution.py``'s own ``_spy_skill_of()`` already established
for the identical lookup.

Reuses ``turn/movement.py neighbors()`` (already the sourced hex-adjacency
primitive every other module needing "provinces around here" already
uses) for "owners of adjacent provinces", and
``turn/recruit.py is_army_type_compatible_with_race`` (the same
race-compatibility table Recruit itself already resolves against) for
"army types recruitable there" -- rulebook [3.4]'s race-native-unit rule,
not re-derived.

**Spotted characters (Phase 139)** -- ``turn/intelligence_estimate.py``
(Phase 136) implements ``REPORTS.PAS``'s real ``Align_Est``/``Temper_Est``
imperfect-information formulas, but an exhaustive grep across all 14
``.PAS`` files this project has turned up *zero call sites* for either
function anywhere in the available Pascal archive -- there is no sourced
integration point telling this project when a real report actually
invokes them. Wiring them into ASpy's report (rather than, say, Cast or
Challenge) is this project's own design choice: ASpy is the one action
whose entire rulebook purpose ([3.14]) is "report on what's here," so a
list of co-located leaders with the observer's best guess at their
alignment/temper is a natural fit for the estimation formulas' actual
shape, even without a Pascal citation pinning them to this specific spot.
This is flagged here, not presented as sourced, per the user's own
explicit go-ahead to build a consumer despite the missing call sites.

The real formula asymmetry from ``intelligence_estimate.py`` carries
through as two separate caller-supplied booleans, not one combined flag:
``caster_holds_psychic_mage_office`` grants perfect detection for BOTH
alignment and temper (``titchar[Psychic_Mage] = agent`` in both real
conditions), while ``caster_has_detect_align`` only ever helps alignment
(``Has_SA(agent,Detect_Align)`` -- temper detection has no such
advanced-ability bypass in the Pascal source at all).

**Phase 267 -- espionage-obtained Discoveries.** RULES.AK [3.14], quoted
in full: "There is also a chance of finding out what Sage Discoveries
the spied-on Kingdom has, and obtaining them for the use of your
Kingdom. Sage ability also has something to do with spying out
inventions. If a spy sees an invention, some Sage ability will help him
figure out how to get it for your kingdom. Sage level 1 will be more
than enough to understand all common inventions, but higher ability may
be needed for inventions of obscure design. The chance for discovering
an invention by spying is limited to twice the chance of discovery by
Sages." **Phase 795 (``Desktop/DISCVAL.md``, 2026-09-13) supersedes the
original flat-chance reading above** with the real compiled formula:
``models/discovery.py DISCOVERY_SPREAD_CATEGORY`` (``dspread``, a real,
byte-verified 64-entry table distinct from ``discval`` -- see that
constant's own docstring) categorizes every Discovery into one of four
"diffusion" classes (Batt/Comm/Prof/Form), each with its own real two-
stage roll depending on *both* the caster's Spy *and* Sage skill levels
(``_discovery_spread_success()``) -- this **is** the real, sourced
answer to the rulebook's own "common vs. obscure design" distinction,
not an invented weighting. Every Discovery the province's owning
kingdom has that the caster's own kingdom doesn't is still rolled
independently (an explicit, documented reading of "a chance of finding
out what Discoveries... and obtaining them" as a per-invention roll, not
one single roll unlocking the whole list; no sourced text distinguishes
the two readings, and per-item independent rolls already match this
project's own established shape for "roll each eligible X separately",
``turn/exploration.py discover_features()``, Phase 242) -- the real
diffusion container's own increasing-index-order scan with a cumulative
per-category budget threshold (DISCVAL sections 17-18) is deliberately
NOT reproduced, since it needs an unmodeled ``gdyear``/``gdmonth``
calendar concept this project has never had a reason to build. Espionage never targets the caster's
own kingdom (``province.owner_kingdom_id == leader.kingdom_id`` skips
entirely) and grants nothing when the caster has no kingdom of their
own (an independent Hero) -- the same "nowhere to grant a kingdom-level
Discovery to" edge case ``turn/practice_execution.py``'s own Phase 266
note already established. Each discovery actually obtained credits the
caster's own ``MeritTally.discoveries_via_espionage`` (rulebook page
51's own Chancellor formula, "+1 per Invention obtained via
espionage") -- previously never incremented by anything, per that
field's own Phase 227 note.

A spotted leader's "true" alignment is read from their own kingdom's
``KingdomState.alignment`` (the same per-kingdom field
``turn/challenge_execution.py``'s Neutral-duelist-bonus check already
treats as characterizing a leader in its service) -- ``None`` for an
independent Hero with no kingdom. True temper is read from the new
``LeaderState.temper`` field (Phase 139); ``None`` if not recorded, the
same "no data" convention ``LeaderState.skills`` already established.
Either being ``None`` means the corresponding estimate is also reported
as ``None`` -- there's nothing to estimate away from.

**Phase 212 -- real army names for the "leads"/garrison line items.**
``SAY.PAS``'s own ``_LSLeads``/``_LSGarr`` (Phase 115, unblocked Phase
118) need a list of army display names, which this module's own data
never carried before. ``SpottedCharacter.army_names`` (every army that
spotted leader commands, via ``GameState.armies_commanded_by()``, the
same lookup ``turn/trail_execution.py``'s own ``armies_led`` already
uses) and ``SpyReport.garrison_army_names`` (every *unled* army at the
spy's own province, ``GameState.armies_at()`` filtered on
``commanded_by is None``) are both named via ``models/army_naming.py
make_army_name()`` -- built Phase 149, never given a real caller until
now. See ``_army_display_name()``'s own docstring for how an army's
race (needed only to decide whether a short non-Human tag is appended)
is resolved, including the explicit ``Race.HUMAN`` fallback for a
mercenary army with no owning Kingdom.

**Phase 458 -- Add_Experience's own Spy call site.** ``AKGEN_reverse_
engineering_report (2).md`` SS3.3's own Spy row gives a fixed base
value (10) for "evento informativo qualificante" (a qualifying
informational event); SS3.4 names the real trigger set explicitly:
"Spy, Trail, Pursue e attivita' informative pertinenti" (Spy, Trail,
Pursue, and relevant informational activities). ``execute_aspy()``
has no success/failure roll of its own -- every call that reaches a
real ``SpyReport`` (the caster's location resolves to a known
province) is a genuine informational event, so ``turn/experience.py
add_experience(leader, Ability.SPY, 10, rng)`` fires unconditionally
right before that report is built. **Also wired** (Phase 461): Trail
(``turn/trail_execution.py``, on its own real "qualifying" moment) and
Pursue (``turn/pursue_execution.py``, gated on its own ``spied_on=True``)
-- SS3.4's own text names all three under one row; each fires the same
``add_experience(leader, Ability.SPY, 10, rng)`` call at its own
action-specific qualifying moment rather than reusing ASpy's own
always-fires shape verbatim.

**Phase 694 -- Druidic Animal Spies.** ``models/advanced_ability.py
ADVANCED_ABILITY_DESCRIPTION[DRUIDIC_ANIMAL_SPIES]``: "When the Druid
issues a Spy order (SP), animals will scout adjacent provinces, then
come back and squeak their little reports... However, only military
forces are reported." ``SpyReport.adjacent_military_forces`` reuses
the same ``neighbors()``/``_army_display_name()`` primitives already
built for ``adjacent_owners``/``garrison_army_names`` above, applied
one hex further out -- every army at each real adjacent province
(commanded or not; the sourced text draws no such distinction the way
``garrison_army_names`` does for the caster's own province), gated on
the new ``caster_has_druidic_animal_spies`` flag (empty dict without
it, the same "caller-computed boolean" convention already used for
``caster_holds_psychic_mage_office``/``caster_has_detect_align``).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_naming import make_army_name
from ak_engine.models.army_type import MONSTROUS_ARMY_RACE, ArmyType
from ak_engine.models.discovery import DISCOVERY_SPREAD_CATEGORY, Discovery
from ak_engine.models.enums import Ability
from ak_engine.models.game_state import ArmyState, GameState, LeaderState
from ak_engine.models.map import HexCoord
from ak_engine.models.race import Race
from ak_engine.models.temper import Temper
from ak_engine.turn.aspy_defend_decode import SpyProvinceRequest
from ak_engine.turn.discovery_effects import effective_skill_level
from ak_engine.turn.experience import add_experience
from ak_engine.turn.intelligence_estimate import estimate_alignment, estimate_temper
from ak_engine.turn.movement import MapBounds, neighbors
from ak_engine.turn.recruit import is_army_type_compatible_with_race
from ak_engine.turn.spy_table import estimate_reported_value
from ak_engine.turn.tax_base import province_tax_yield

def _spy_skill_of(state: GameState, leader: LeaderState) -> int:
    return effective_skill_level(state, leader, Ability.SPY)


def _discovery_spread_success(category: int, sp: int, sa: int, rng: random.Random) -> bool:
    """The real "diffusion" success roll for one ``Discovery`` already
    known to the spied-on kingdom, keyed by its own ``DISCOVERY_SPREAD_
    CATEGORY`` -- ``Desktop/DISCVAL.md`` (2026-09-13) section 16.3,
    the two-stage roll behind the real ``AK.EXE`` ``_DCSpy`` diffusion
    contexts (raw ``0x122F4``/``AK.OVR 0x00707``). ``sp``/``sa`` are the
    caster's own Spy/Sage skill levels plus one (``M_Skill(actor,X)+1``
    in the source). Each branch short-circuits on the first failed roll
    -- confirmed essential for RNG-consumption fidelity by the source
    itself ("è essenziale mantenere il cortocircuito: se il primo
    confronto fallisce, il secondo numero casuale non viene consumato").
    """

    if category == 1:  # Batt: raw 205AD/201AA
        return rng.random() < 0.15 + 0.10 * sp and rng.random() < 0.30 * sp and rng.random() < 0.25 * sa
    if category == 2:  # Comm: raw 205F2/20146
        return rng.random() < 0.10 * sp and rng.random() < 0.60 * sa
    if category == 3:  # Prof: raw 2062A/20217
        return rng.random() < 0.05 * sp and rng.random() < 0.30 * sp and rng.random() < 0.15 * sa
    return rng.random() < 0.02 * sp and rng.random() < 0.20 * sp and rng.random() < 0.05 * sa  # Form: raw 2063B/20283


def _roll_espionage_discoveries(
    state: GameState,
    spy_kingdom_id: int | None,
    target_kingdom_id: int | None,
    spy_skill: int,
    sage_skill: int,
    rng: random.Random,
) -> tuple[Discovery, ...]:
    """Rolls, independently, every ``Discovery`` the spied-on kingdom owns
    that the caster's own kingdom doesn't, via the real per-category
    "diffusion" formula (``_discovery_spread_success()``, ``Desktop/
    DISCVAL.md`` sections 16-18) -- supersedes this function's own Phase
    267 flat-chance approximation (rulebook [3.14]'s plain-English
    "twice the chance of discovery by Sages" undersold the real, category-
    dependent, Spy-*and*-Sage-skill-dependent compiled formula). Grants
    each success directly to ``spy_kingdom_id``'s own ``KingdomState.
    discoveries``. Returns an empty tuple (no roll at all) when either
    kingdom is missing or they're the same kingdom.

    **Deliberately not reproduced** (see this module's own docstring):
    the real diffusion container's own increasing-index-order scan with
    a cumulative per-category budget threshold (DISCVAL sections 17-18,
    gated on an unmodeled ``gdyear``/``gdmonth`` calendar check) -- every
    eligible ``Discovery`` here is still rolled independently, matching
    this project's own established "roll each eligible X separately"
    convention (``turn/exploration.py discover_features()``).
    """

    if spy_kingdom_id is None or target_kingdom_id is None or spy_kingdom_id == target_kingdom_id:
        return ()
    spy_kingdom = state.kingdoms.get(spy_kingdom_id)
    target_kingdom = state.kingdoms.get(target_kingdom_id)
    if spy_kingdom is None or target_kingdom is None:
        return ()

    sp = spy_skill + 1
    sa = sage_skill + 1
    candidates = sorted(target_kingdom.discoveries - spy_kingdom.discoveries, key=lambda d: d.value)
    obtained = [d for d in candidates if _discovery_spread_success(DISCOVERY_SPREAD_CATEGORY[d], sp, sa, rng)]
    spy_kingdom.discoveries.update(obtained)
    return tuple(obtained)


def _army_display_name(state: GameState, army: ArmyState) -> str:
    """``models/army_naming.py make_army_name()``'s first real caller
    (Phase 212) -- built Phase 149, never wired to a consumer before.
    Race is resolved the same way ``describe_armies_report()``'s own
    Phase 158 note already established: ``MONSTROUS_ARMY_RACE`` for a
    fixed-race army type, else the owning kingdom's own race. A
    mercenary army (``kingdom_id is None``) has no kingdom to fall back
    to -- there is no per-army race field anywhere in this project, so
    ``Race.HUMAN`` is used as an explicit, flagged default rather than
    leaving the name unbuildable; ``make_army_name()`` only ever uses
    the race to decide whether to append a short non-Human tag, so this
    default is cosmetic (it can only ever suppress a tag that might
    otherwise be real), never a fabricated fact reported elsewhere.
    """

    kingdom = state.kingdoms.get(army.kingdom_id) if army.kingdom_id is not None else None
    race = MONSTROUS_ARMY_RACE.get(army.army_type, kingdom.race if kingdom is not None else Race.HUMAN)
    return make_army_name(army.army_id, army.army_type, race)


@dataclass(slots=True)
class SpottedCharacter:
    leader_id: int
    name: str
    estimated_alignment: Alignment | None
    estimated_temper: Temper | None
    # Phase 212: real army display names (``models/army_naming.py``) for
    # every army this spotted character leads -- SAY.PAS's own
    # ``_LSLeads`` line item needs this list, see module docstring.
    army_names: tuple[str, ...] = ()


@dataclass(slots=True)
class SpyReport:
    province: HexCoord
    owner_kingdom_id: int | None
    adjacent_owners: dict[HexCoord, int | None] = field(default_factory=dict)
    recruitable_army_types: list[ArmyType] = field(default_factory=list)
    is_capital: bool = False
    spotted_characters: list[SpottedCharacter] = field(default_factory=list)
    # Phase 212: real army display names for every *unled* army sitting in
    # this province -- SAY.PAS's own ``_LSGarr`` line item needs this
    # list, see module docstring.
    garrison_army_names: tuple[str, ...] = ()
    # Phase 253: this province's own expected tax revenue this turn
    # (``turn/tax_base.py province_tax_yield()``), perturbed by the [4.33]
    # Spy Table's own margin of error as of Phase 265 (``turn/spy_table.py
    # estimate_reported_value()``) -- ``None`` if its base
    # ``ProvinceState.tax`` was never recorded. See module docstring.
    tax_estimate: int | None = None
    # Phase 267: every Discovery obtained via espionage this call --
    # already granted to the caster's own kingdom by the time this report
    # is returned. Empty whenever nothing was obtained (including every
    # pre-Phase-267 caller). See module docstring.
    discoveries_obtained: tuple[Discovery, ...] = ()
    # Phase 694: `AdvancedAbility.DRUIDIC_ANIMAL_SPIES`'s own real
    # description -- "animals will scout adjacent provinces... only
    # military forces are reported." Real army display names for every
    # army sitting in each adjacent province with real data (whether
    # commanded or not -- the sourced text draws no such distinction,
    # unlike `garrison_army_names` above). Empty dict for any caster who
    # doesn't hold the Advanced Ability.
    adjacent_military_forces: dict[HexCoord, tuple[str, ...]] = field(default_factory=dict)
    # Phase 705: `AdvancedAbility.SPY_EXPANDED_SPYING`'s own "gains
    # information on what features are known to the owning kingdom" --
    # maps `Feature.feature_id` to whatever discovery level (1-3) *this
    # province's own owner* has recorded, for every Feature here the
    # owner knows about at all (level > 0). Empty for a caster who
    # doesn't hold the ability, an unowned province, or a province with
    # no Features the owner has discovered.
    features_known_to_owner: dict[int, int] = field(default_factory=dict)


def execute_aspy(
    state: GameState,
    leader_id: int,
    request: SpyProvinceRequest,  # noqa: ARG001 -- see module docstring: target_province isn't trusted
    *,
    board_width: int | None = None,
    board_height: int | None = None,
    caster_holds_psychic_mage_office: bool = False,
    caster_has_detect_align: bool = False,
    caster_has_druidic_animal_spies: bool = False,
    caster_has_spy_expanded_spying: bool = False,
    rng: random.Random | None = None,
) -> SpyReport | None:
    """Builds the intelligence report for the caster's own current province.

    Returns ``None`` if the caster's location isn't a known province (no
    ``GameState`` in this project's tests populates every hex -- the same
    "insufficient data, not a guessed result" convention used throughout).
    Also returns ``None`` if ``leader_id`` doesn't resolve to a real
    ``LeaderState`` at all (Phase 824 bug fix) -- a leader who died
    earlier in the same turn can still have an ASPY order queued for a
    later phase, since ``turn/plan_dispatch.py _dispatch_aspy()`` (the
    one real per-phase caller) computes this function's own Advanced-
    Ability flags defensively via ``.get()`` but never actually gates
    the call on the result, unlike `turn_processor.py`'s own separate
    Double-Agent end-of-turn call site (always a real, currently-live
    leader by construction, since it iterates `state.leaders.values()`
    directly). Previously resolved via a bare ``state.leaders[leader_
    id]`` lookup, raising an unhandled ``KeyError`` -- caught upstream
    by ``run_leader_plan()``'s own top-level ``try``/``except`` so it
    never crashed the whole turn, but an opaque exception instead of
    the same "insufficient data" ``None`` this function already returns
    for a comparable case one line below.

    ``caster_holds_psychic_mage_office``/``caster_has_detect_align`` feed
    ``turn/intelligence_estimate.py``'s ``estimate_alignment()``/
    ``estimate_temper()`` for the ``spotted_characters`` list -- see the
    module docstring's "Spotted characters (Phase 139)" section for why
    these are two separate flags, not one.

    ``caster_has_druidic_animal_spies`` (Phase 694) populates ``SpyReport.
    adjacent_military_forces`` -- see that field's own docstring.

    ``caster_has_spy_expanded_spying`` (Phase 705, ``AdvancedAbility.
    SPY_EXPANDED_SPYING``) populates ``SpyReport.features_known_to_
    owner`` -- see that field's own docstring. The ability's own second
    clause ("with the Trail action, estimates are gained for skills,
    and for offices held") is unrelated to this function -- see
    ``turn/trail_execution.py execute_trail()``'s own Phase 705
    addendum.

    ``board_width``/``board_height`` (Phase 780, default ``None``) fall
    back to ``state.board_width``/``.board_height``.
    """

    del request  # see module docstring
    rng = rng if rng is not None else random.Random()
    leader = state.leaders.get(leader_id)
    if leader is None:
        return None
    province = state.provinces.get(leader.location)
    if province is None:
        return None

    board_width = board_width if board_width is not None else state.board_width
    board_height = board_height if board_height is not None else state.board_height
    bounds = MapBounds(board_width, board_height)
    adjacent_owners: dict[HexCoord, int | None] = {}
    adjacent_military_forces: dict[HexCoord, tuple[str, ...]] = {}
    for neighbor_coord in neighbors(leader.location, bounds):
        neighbor_province = state.provinces.get(neighbor_coord)
        if neighbor_province is not None:
            adjacent_owners[neighbor_coord] = neighbor_province.owner_kingdom_id
            if caster_has_druidic_animal_spies:
                adjacent_military_forces[neighbor_coord] = tuple(
                    _army_display_name(state, army) for army in state.armies_at(neighbor_coord)
                )

    # Rulebook [3.4]: "Ciascuna provincia offre 1 o 2 tipi di unità militari possibili"
    # -- the province's own real slot types (``recruit_type_1``/``recruit_type_2``,
    # the same data ``turn/recruit_execution.py`` already uses for its native/non-native
    # test), which is what SAY.PAS's ``_LSAT`` ("Province Army Type #: |") reports.
    # Only a province with no recorded slot data (hand-built fixtures) falls back to the
    # race-compatibility approximation -- every type a race *could* field, not what the
    # province actually offers.
    if province.recruit_type_1 is not None:
        recruitable = [province.recruit_type_1]
        if province.recruit_type_2 is not None and province.recruit_type_2 != province.recruit_type_1:
            recruitable.append(province.recruit_type_2)
    else:
        recruitable = [
            army_type for army_type in ArmyType if is_army_type_compatible_with_race(army_type, province.race)
        ]

    is_capital = False
    if province.owner_kingdom_id is not None:
        kingdom = state.kingdoms.get(province.owner_kingdom_id)
        is_capital = kingdom is not None and kingdom.home_province == leader.location

    perfect_alignment = caster_holds_psychic_mage_office or caster_has_detect_align
    spotted_characters: list[SpottedCharacter] = []
    for spotted in state.leaders_at(leader.location):
        if spotted.leader_id == leader_id:
            continue

        estimated_alignment: Alignment | None = None
        if spotted.kingdom_id is not None:
            spotted_kingdom = state.kingdoms.get(spotted.kingdom_id)
            if spotted_kingdom is not None:
                estimated_alignment = estimate_alignment(
                    spotted_kingdom.alignment,
                    spotted.leader_id,
                    leader_id,
                    perfect=perfect_alignment,
                )

        estimated_temper: Temper | None = None
        if spotted.temper is not None:
            estimated_temper = estimate_temper(
                spotted.temper,
                spotted.leader_id,
                leader.birth_x or 0,
                perfect=caster_holds_psychic_mage_office,
            )

        army_names = tuple(_army_display_name(state, army) for army in state.armies_commanded_by(spotted.leader_id))

        spotted_characters.append(
            SpottedCharacter(
                leader_id=spotted.leader_id,
                name=spotted.name,
                estimated_alignment=estimated_alignment,
                estimated_temper=estimated_temper,
                army_names=army_names,
            )
        )

    garrison_army_names = tuple(
        _army_display_name(state, army) for army in state.armies_at(leader.location) if army.commanded_by is None
    )

    spy_skill = _spy_skill_of(state, leader)
    sage_skill = effective_skill_level(state, leader, Ability.SAGE)

    exact_tax_yield = province_tax_yield(province)
    tax_estimate = (
        estimate_reported_value(exact_tax_yield, spy_skill, rng) if exact_tax_yield is not None else None
    )

    discoveries_obtained = _roll_espionage_discoveries(
        state, leader.kingdom_id, province.owner_kingdom_id, spy_skill, sage_skill, rng
    )
    if discoveries_obtained:
        leader.merit_tally.discoveries_via_espionage += len(discoveries_obtained)

    # Phase 458: AKGEN_reverse_engineering_report (2).md SS3.3's own Spy
    # row (base 10) -- see module docstring's own Phase 458 addendum for
    # why every real report this function produces (there's no success/
    # failure roll gating ASpy itself) counts as the "evento informativo
    # qualificante" (qualifying informational event) that row names.
    add_experience(leader, Ability.SPY, 10, rng)

    features_known_to_owner: dict[int, int] = {}
    if caster_has_spy_expanded_spying and province.owner_kingdom_id is not None:
        for feature in state.features_at(leader.location):
            level = feature.discovered_by_kingdom.get(province.owner_kingdom_id, 0)
            if level > 0:
                features_known_to_owner[feature.feature_id] = level

    return SpyReport(
        province=leader.location,
        owner_kingdom_id=province.owner_kingdom_id,
        adjacent_owners=adjacent_owners,
        recruitable_army_types=recruitable,
        is_capital=is_capital,
        spotted_characters=spotted_characters,
        garrison_army_names=garrison_army_names,
        tax_estimate=tax_estimate,
        discoveries_obtained=discoveries_obtained,
        adjacent_military_forces=adjacent_military_forces,
        features_known_to_owner=features_known_to_owner,
    )
