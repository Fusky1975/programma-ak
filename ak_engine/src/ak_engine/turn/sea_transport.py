"""Fleet/Whale cargo-capacity subsystem -- Phase 714.

**`Regolamento AK.txt` (lines 1917-1937), quoted in full**:

    Le unità di terra possono muovere solo via terra a meno che non
    siano trasportate da flotte. Possono però essere lasciate in mare,
    in quanto si presume che tutti i mari abbiano isole e difenderanno
    la provincia di mare anche contro le flotte di invasione.

    Balene e Flotte possono entrare e uscire da province di terra, ma
    non possono muovere direttamente da una provincia di terra
    all'altra. Una flotta può trasportare due unità di fanteria
    (inclusi Troll e Bestie Mannare) o un'unità montata (inclusi
    Elefanti e Cammelli).

    I Tritoni muovono come le Flotte, con l'eccezione che possono
    entrare ed uscire da una provincia colpita da un incantesimo
    Separare le Acque. Non possono trasportare altre unità, ma possono
    essere trasportate da unità aeree.

    Gli Ent non possono mai essere trasportati e possono entrare in una
    provincia di mare solo se questa è sotto l'effetto di un
    incantesimo Separare le Acque.

    Le unità aeree (Draghi e Aquile) possono muovere per terra e per
    mare e possono terminare un turno sul mare. Possono trasportare
    un'unità di fanteria ciascuna.

    Le unità militari non possono usare un punto di movimento via terra
    ed essere trasportate (per mare o per aria) in uno stesso turno.

This is a real, previously entirely unmodeled BASE mechanic -- an
ordinary Fleet already carries 2 infantry or 1 mounted unit, no
Advanced Ability needed. `AdvancedAbility.DRUIDIC_WHALE_TRANSPORT`/
`DRUIDIC_TRANSPORT` (`models/advanced_ability.py`) are narrow
*extensions* on top of it: Whales, normally unable to carry anything at
all, gain "one infantry unit" of capacity per Whale with the first
ability; Fleets gain the ability to carry one otherwise-ineligible unit
("such as Ents and Dinosaurs") with the second -- an explicit,
sourced override of the rulebook's own "Ents can never be transported"
line, not an invented exception. Mermen are confirmed to never be able
to carry anything (they can only ever be cargo, for an air unit).

**Phase 738**: that last sentence describes the rulebook's own real
promise, but `can_board()`'s own air-carrier branch didn't honor it
until now -- Mermen were absent from `FLEET_INFANTRY_ARMY_TYPES` (the
Fleet/Whale rule's own eligible-cargo set) since Phase 714, and the
air-carrier branch (Phase 717) reused that same set directly, so a
real `board_army()` call could never actually seat a Mermen unit onto
a Dragon/Eagle Wing -- a gap flagged explicitly in Phase 737's own
closing note (`turn/move_execution.py`'s own `find_transport_
illegality()` already had a real, tested "carried by an air unit"
legality exemption for Mermen with nothing to make it reachable).
Closed by adding `ArmyType.MERMEN` as a second, explicit eligible type
in that one branch, sharing the same one-unit `AIR_INFANTRY_CAPACITY`
slot (the rulebook's own Mermen clause names no capacity of its own).

**Army-type classification** (`models/army_type.py FLEET_INFANTRY_
ARMY_TYPES`/`FLEET_MOUNTED_ARMY_TYPES`): the rulebook's own "(inclusi
Troll e Bestie Mannare)"/"(inclusi Elefanti e Cammelli)" parentheticals
are examples, not an exhaustive list, over the 23 land-eligible
`ArmyType` members. Classified there only for the types whose own name
is unambiguous (plain infantry/cavalry names, plus the rulebook's own
explicit examples) -- every other land-eligible type (Garrison, Ents,
Dinosaurs, Marauders, Shamans, Vampires, Spiders, D Turtle, Artillery)
needs `DRUIDIC_TRANSPORT` to board a Fleet at all, via its own separate
1-unit capacity below.

**Fleet-destroyed-while-carrying, user-confirmed directly (no source
describes this)**: the cargo sinks with the carrier. `apply_carrier_
destruction()` implements this, deliberately **not** auto-hooked into
`GameState.remove_army()` itself (shared by every removal reason --
disband, Skeletal Army's own grave-digging, ...; cascading cargo
destruction there unconditionally would be a real behavior change to
every existing caller). **Phase 716** wires the real battle case
specifically -- see `apply_battle_carrier_destruction()` below, called
at all 4 real `fight_battle()` call sites.

**Report-layer narration -- DONE (Phase 736)**: no real `SAY.PAS`-style
text survives anywhere for a boarding event or for cargo sinking with
its carrier (confirmed by a direct search of every available reverse-
engineering report) -- the user directly authored the sinking event's
own theme ("the transported unit sinks together with the annihilated
fleet and disappears into the depths of the sea") and authorized
project-original prose for both events. `MoveExecutionResult.boarded_
army_ids` (Phase 715) is narrated directly at render time (`report/
turn_report.py`'s own `ActionCode.LMOVE` branch, `render_cargo_
boarded()`); cargo sinking needed a new structured per-turn event list
(`GameState.sunk_cargo_events`, `SunkCargoEvent`) since the carrier's
own type is already gone from `state.armies` by the time `apply_
carrier_destruction()` runs -- see that function's own Phase 736
addendum, and `report/turn_report.py record_sunk_cargo_world_events()`
for the render side.

**Phase 717 -- Dragon Wing/Eagle Wing air transport, `Regolamento
AK.txt` lines 1932-1934** (quoted in full above): "Le unità aeree
(Draghi e Aquile)... Possono trasportare un'unità di fanteria
ciascuna." A third, real base mechanic, unrelated to either Druidic
ability and unconditional (no Advanced Ability gate) -- reuses
`models/army_type.py OVERFLIGHT_AIR` directly as the carrier-type set
and `FLEET_INFANTRY_ARMY_TYPES` for eligible cargo, 1 unit each
(`AIR_INFANTRY_CAPACITY`). See `can_board()` above.

**Deliberately out of scope, real and separate follow-ups, none
started**: the base Fleet-for-everyone rule as a *live, enforced*
mechanic (Phase 715 wired automatic boarding into `execute_move()`,
but land units still move onto/across Sea completely unassisted --
nothing *requires* boarding); `turn/move_execution.py
_naval_hug_coastline_move_is_legal()`'s own capacity-based allocation
priority (a different, more specific rule -- deterministic priority by
speed/army-id, `AKGEN_reverse_engineering_report (3).md` §106 -- not
just "is there room," so it isn't a trivial reuse of `can_board()`
even though it's wired elsewhere now). Matches this project's own
established "primitives now, wiring later, staged" precedent
(Feature->Power Phase 616 vs. 622/623; SEP decode Phase 659 vs. 669;
Random Encounters 707 vs. 708/709).
"""

from __future__ import annotations

from collections.abc import Sequence

from ak_engine.models.army_type import (
    AIR_INFANTRY_CAPACITY,
    DRUIDIC_TRANSPORT_CAPACITY,
    FLEET_INFANTRY_ARMY_TYPES,
    FLEET_INFANTRY_CAPACITY,
    FLEET_MOUNTED_ARMY_TYPES,
    FLEET_MOUNTED_CAPACITY,
    OVERFLIGHT_AIR,
    WHALE_INFANTRY_CAPACITY,
    ArmyType,
)
from ak_engine.models.game_state import ArmyState, GameState, SunkCargoEvent
from ak_engine.models.map import HexCoord


def cargo_aboard(state: GameState, carrier_army_id: int) -> list[ArmyState]:
    return [army for army in state.armies.values() if army.transported_by == carrier_army_id]


def can_board(
    state: GameState,
    carrier: ArmyState,
    cargo_type: ArmyType,
    *,
    caster_has_druidic_whale_transport: bool = False,
    caster_has_druidic_transport: bool = False,
) -> bool:
    """Whether one more unit of `cargo_type` could legally board `carrier`
    right now, given whatever's already aboard. See module docstring
    for the full sourcing.
    """

    current_cargo_types = [army.army_type for army in cargo_aboard(state, carrier.army_id)]

    if carrier.army_type is ArmyType.FLEET:
        if any(t in FLEET_MOUNTED_ARMY_TYPES for t in current_cargo_types):
            # "due unità di fanteria... o un'unità montata" -- exclusive-or:
            # a mounted unit already aboard fills the Fleet outright.
            return False
        if cargo_type in FLEET_MOUNTED_ARMY_TYPES:
            return len(current_cargo_types) < FLEET_MOUNTED_CAPACITY
        if cargo_type in FLEET_INFANTRY_ARMY_TYPES:
            infantry_aboard = sum(1 for t in current_cargo_types if t in FLEET_INFANTRY_ARMY_TYPES)
            return infantry_aboard < FLEET_INFANTRY_CAPACITY
        # Otherwise-ineligible type (Ents, Dinosaurs, ...) -- needs
        # DRUIDIC_TRANSPORT's own separate, smaller capacity.
        if not caster_has_druidic_transport:
            return False
        special_aboard = sum(1 for t in current_cargo_types if t not in FLEET_MOUNTED_ARMY_TYPES and t not in FLEET_INFANTRY_ARMY_TYPES)
        return special_aboard < DRUIDIC_TRANSPORT_CAPACITY

    if carrier.army_type is ArmyType.WHALES:
        if not caster_has_druidic_whale_transport or cargo_type not in FLEET_INFANTRY_ARMY_TYPES:
            return False
        return len(current_cargo_types) < WHALE_INFANTRY_CAPACITY

    if carrier.army_type in OVERFLIGHT_AIR:
        # Phase 717: "Possono trasportare un'unità di fanteria ciascuna"
        # -- a real base rule, unconditional (no Advanced Ability gate,
        # unlike the two Druidic Fleet/Whale extensions above).
        # Phase 738: Mermen are a second, real exception to this same
        # rule -- the rulebook's own separate clause for them, quoted in
        # full in this module's own docstring above ("possono essere
        # trasportate da unità aeree"), names no capacity of its own, so
        # they share the identical one-unit slot every other eligible
        # infantry type already does, rather than a separate pool.
        if cargo_type not in FLEET_INFANTRY_ARMY_TYPES and cargo_type is not ArmyType.MERMEN:
            return False
        return len(current_cargo_types) < AIR_INFANTRY_CAPACITY

    # Every other army type (Mermen included -- confirmed by the
    # rulebook as never able to carry anything) can never carry cargo.
    return False


def board_army(
    state: GameState,
    cargo_army_id: int,
    carrier_army_id: int,
    *,
    caster_has_druidic_whale_transport: bool = False,
    caster_has_druidic_transport: bool = False,
) -> bool:
    cargo = state.armies.get(cargo_army_id)
    carrier = state.armies.get(carrier_army_id)
    if cargo is None or carrier is None:
        return False
    if cargo.transported_by is not None:
        return False
    if cargo.location != carrier.location:
        return False
    if not can_board(
        state,
        carrier,
        cargo.army_type,
        caster_has_druidic_whale_transport=caster_has_druidic_whale_transport,
        caster_has_druidic_transport=caster_has_druidic_transport,
    ):
        return False

    cargo.transported_by = carrier_army_id
    return True


def disembark_army(state: GameState, cargo_army_id: int) -> bool:
    cargo = state.armies.get(cargo_army_id)
    if cargo is None or cargo.transported_by is None:
        return False
    cargo.transported_by = None
    return True


def apply_carrier_destruction(
    state: GameState,
    carrier_army_id: int,
    *,
    carrier_army_type: ArmyType | None = None,
    coord: HexCoord | None = None,
) -> list[int]:
    """The cargo sinks with the carrier (user-confirmed, no source
    describes this) -- destroys every army currently boarded on
    `carrier_army_id` and returns their own ids. Wired into every real
    battle call site by `apply_battle_carrier_destruction()` below
    (Phase 716) -- this primitive itself stays reusable on its own.

    Phase 736: when `carrier_army_type`/`coord` are both given (every
    real caller now supplies them -- the carrier is typically already
    gone from `state.armies` by the time this runs, so its own type
    can't be looked up here), records one `SunkCargoEvent` per real
    cargo unit *before* it's removed -- `report/turn_report.py record_
    sunk_cargo_world_events()` renders these once per turn. `None`
    (the default) skips recording entirely, preserving every pre-
    Phase-736 caller/test unchanged.
    """

    cargo = cargo_aboard(state, carrier_army_id)
    if carrier_army_type is not None and coord is not None:
        for army in cargo:
            state.sunk_cargo_events.append(SunkCargoEvent(coord, carrier_army_type, army.army_type))
    destroyed_ids = [army.army_id for army in cargo]
    for army_id in destroyed_ids:
        state.remove_army(army_id)
    return destroyed_ids


def apply_battle_carrier_destruction(
    state: GameState,
    destroyed_army_ids: Sequence[int] = (),
    disbanded_army_ids: Sequence[int] = (),
    pursuit_destroyed_army_ids: Sequence[int] = (),
    *,
    coord: HexCoord | None = None,
    army_types_before_battle: dict[int, ArmyType] | None = None,
) -> list[int]:
    """Phase 716 -- cascades `apply_carrier_destruction()` for every real
    army destroyed this battle, whether or not it was actually a Fleet/
    Whale carrier (a non-carrier id simply has no cargo aboard it, so
    this is harmless to call unconditionally -- no per-army type check
    needed). Takes the three real `turn/battle_orchestrator.py
    BattleReport` lists that each correspond to a genuine `GameState.
    remove_army()` call during battle resolution (`destroyed_army_ids`,
    `disbanded_army_ids`, `pursuit_destroyed_army_ids`) as plain
    sequences of ids, not the `BattleReport` object itself -- avoids a
    circular import (`battle_orchestrator.py` is this function's own
    caller). `retreated_army_ids`/`mercenary_army_ids` are deliberately
    NOT included -- those armies stay in `state`, never removed.

    Call this once, right after `fight_battle()` returns, at each of
    this project's own 4 real call sites (`turn/move_execution.py
    execute_move()`, `turn/pursue_execution.py execute_pursue()`,
    `turn/turn_processor.py`'s forced-rebattle continuation, `turn/
    battle_orchestrator.py fight_multi_attacker_battle()`'s own per-
    group call). Returns every cargo army id sunk this way.

    Phase 736: `coord`/`army_types_before_battle` (a `{army_id:
    army_type}` snapshot the caller builds from `state.armies` *before*
    calling `fight_battle()`, since `fight_battle()` itself already
    removed the carrier by the time this function runs) let real event
    recording reach `apply_carrier_destruction()` above -- both `None`
    (every pre-Phase-736 caller/test) reproduces the exact prior
    behavior, no recording at all.
    """

    sunk_cargo_ids: list[int] = []
    for army_id in (*destroyed_army_ids, *disbanded_army_ids, *pursuit_destroyed_army_ids):
        carrier_army_type = army_types_before_battle.get(army_id) if army_types_before_battle is not None else None
        sunk_cargo_ids.extend(
            apply_carrier_destruction(state, army_id, carrier_army_type=carrier_army_type, coord=coord)
        )
    return sunk_cargo_ids
