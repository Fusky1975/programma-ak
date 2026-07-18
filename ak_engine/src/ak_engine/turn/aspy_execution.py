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
English sentences is a natural, still-open follow-up, not attempted here.

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

**Taxation of the province is not reported** -- there's still no
per-province tax-base model anywhere in this project.
``models/game_state.py ProvinceState.tax_modifier_percent`` is a
*modifier* (Bless/Earthquake's spell effect, Phase 59), not a base tax
figure; nothing computes an actual per-province gold amount the way
``turn/recruit_execution.py`` computes kingdom-level treasury deltas.
Reporting "no data" here would be indistinguishable from reporting a
true zero, so ``SpyReport`` simply omits the field rather than guessing
one.

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
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_naming import make_army_name
from ak_engine.models.army_type import MONSTROUS_ARMY_RACE, ArmyType
from ak_engine.models.game_state import ArmyState, GameState
from ak_engine.models.map import HexCoord
from ak_engine.models.race import Race
from ak_engine.models.temper import Temper
from ak_engine.turn.aspy_defend_decode import SpyProvinceRequest
from ak_engine.turn.intelligence_estimate import estimate_alignment, estimate_temper
from ak_engine.turn.movement import NORMAL_MAP_BOUNDS, MapBounds, neighbors
from ak_engine.turn.recruit import is_army_type_compatible_with_race


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


def execute_aspy(
    state: GameState,
    leader_id: int,
    request: SpyProvinceRequest,  # noqa: ARG001 -- see module docstring: target_province isn't trusted
    *,
    board_width: int = NORMAL_MAP_BOUNDS[0],
    board_height: int = NORMAL_MAP_BOUNDS[1],
    caster_holds_psychic_mage_office: bool = False,
    caster_has_detect_align: bool = False,
) -> SpyReport | None:
    """Builds the intelligence report for the caster's own current province.

    Returns ``None`` if the caster's location isn't a known province (no
    ``GameState`` in this project's tests populates every hex -- the same
    "insufficient data, not a guessed result" convention used throughout).

    ``caster_holds_psychic_mage_office``/``caster_has_detect_align`` feed
    ``turn/intelligence_estimate.py``'s ``estimate_alignment()``/
    ``estimate_temper()`` for the ``spotted_characters`` list -- see the
    module docstring's "Spotted characters (Phase 139)" section for why
    these are two separate flags, not one.
    """

    del request  # see module docstring
    leader = state.leaders[leader_id]
    province = state.provinces.get(leader.location)
    if province is None:
        return None

    bounds = MapBounds(board_width, board_height)
    adjacent_owners: dict[HexCoord, int | None] = {}
    for neighbor_coord in neighbors(leader.location, bounds):
        neighbor_province = state.provinces.get(neighbor_coord)
        if neighbor_province is not None:
            adjacent_owners[neighbor_coord] = neighbor_province.owner_kingdom_id

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

    return SpyReport(
        province=leader.location,
        owner_kingdom_id=province.owner_kingdom_id,
        adjacent_owners=adjacent_owners,
        recruitable_army_types=recruitable,
        is_capital=is_capital,
        spotted_characters=spotted_characters,
        garrison_army_names=garrison_army_names,
    )
