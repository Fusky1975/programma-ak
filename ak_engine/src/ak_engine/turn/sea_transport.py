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
destruction()` implements this, but is deliberately **not** auto-hooked
into `GameState.remove_army()` itself -- that function is shared by
every removal reason (disband, battle death, Skeletal Army's own
grave-digging, ...), and cascading cargo destruction there
unconditionally would be a real behavior change to every existing
caller. A future battle-integration phase calls this explicitly at the
one real "carrier destroyed in battle" call site instead.

**Deliberately out of scope this phase, a real and separate follow-up**:
the base Fleet-for-everyone rule as a *live, enforced* mechanic (no
order dispatch calls anything here yet -- no new `ActionCode`, no
`turn/move_execution.py execute_move()` changes); Dragon/Eagle Wing's
own separate "one infantry unit each" air-transport rule (a third, real
base mechanic the rulebook names in the same passage, unrelated to
either Druidic ability); keeping a boarded army's own `location` in
sync as its carrier moves (real move-integration work); and `turn/
move_execution.py _naval_hug_coastline_move_is_legal()`'s own
capacity-based allocation priority (a different, more specific rule --
deterministic priority by speed/army-id, `AKGEN_reverse_engineering_
report (3).md` §106 -- not just "is there room," so it isn't a trivial
reuse of `can_board()` even once wiring starts). This phase produces
correct, tested primitives a later phase can wire into a real dispatch
path, not a live game mechanic yet -- matching this project's own
established "primitives now, wiring later" precedent (Feature->Power
Phase 616 vs. 622/623; SEP decode Phase 659 vs. 669; Random Encounters
707 vs. 708/709).
"""

from __future__ import annotations

from ak_engine.models.army_type import (
    DRUIDIC_TRANSPORT_CAPACITY,
    FLEET_INFANTRY_ARMY_TYPES,
    FLEET_INFANTRY_CAPACITY,
    FLEET_MOUNTED_ARMY_TYPES,
    FLEET_MOUNTED_CAPACITY,
    WHALE_INFANTRY_CAPACITY,
    ArmyType,
)
from ak_engine.models.game_state import ArmyState, GameState


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
            return not current_cargo_types
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


def apply_carrier_destruction(state: GameState, carrier_army_id: int) -> list[int]:
    """The cargo sinks with the carrier (user-confirmed, no source
    describes this) -- destroys every army currently boarded on
    `carrier_army_id` and returns their own ids. Not auto-hooked into
    any real removal call site yet -- see module docstring.
    """

    destroyed_ids = [army.army_id for army in cargo_aboard(state, carrier_army_id)]
    for army_id in destroyed_ids:
        state.remove_army(army_id)
    return destroyed_ids
