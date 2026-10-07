"""Diplomatic relations and Treat/Break Treat orders -- RULES.AK [8],
quoted below (the user's own rulebook text, section 8, translated
paraphrase in field/function docstrings throughout this module; see
``apply_treat_orders()``'s own docstring for the exact Italian quotes
this phase's logic is sourced from).

**Three relations, one shared value per Kingdom pair** (Phase 1026):
Enemy/Neutral/Allied, reusing ``parser/gw_world.py``'s own confirmed
``DiplomaticRelation`` enum (imported, not redefined) -- its own fourth
value, ``TEAMED``, is never produced by this module: [8] itself only
ever describes three relations, so a Kingdom pair reading ``TEAMED`` can
only come from something outside this module (e.g. a future GM editor),
never from ``apply_treat_orders()``. All Kings start Neutral to each
other (turn 1, [8]'s own opening line) -- ``GameState.diplomatic_
relation()``'s own missing-pair default already matches this with no
extra setup needed.

**Why the Treat order itself isn't a second, parallel input here**: this
project has already confirmed, twice independently (``GameState.treat_
permissions``'s own docstring, and ``turn/scientific_treaty.py``'s own
Phase 869 addendum), that no real K1 move file has ever shown a
recognizable Treat/Break Treat order shape -- "no real order-file shape
ever seen," the same category as Break Treaty/Call-For-Vote
(``turn/emperor_election.py``'s own docstring). Inventing a byte format
for an order never observed would violate this project's own "never a
silent guess" discipline. [8.2]/[3.4] both describe a Treat order as
*one* order with two effects (the recruit-in-ally-territory permission,
and the relation upgrade below) -- so this module reads the exact same
``GameState.treat_permissions`` field [3.4]'s own Phase 261 already
populates (directly by the caller, not decoded from a file) as its own
Treat-order signal, rather than adding a second, redundant channel for
the same real order. ``(owner_kingdom_id, recruiter_kingdom_id)`` in
``treat_permissions`` is read here as "``owner_kingdom_id`` issued a
Treat order toward ``recruiter_kingdom_id`` this turn." Break Treat has
no existing field to reuse -- ``GameState.break_treat_orders`` (Phase
1026, same shape and same turn-scoped-reset convention) is new.

**Timing -- a documented simplification.** [8] frames ordinary Treat/
Break Treat as resolved "alla fine di ciascun turno" (at the end of each
turn), except two explicit exceptions that take effect *before* the
turn's own combat: [8.3]'s Evil/Undead Break Treat ("danno l'ordine...
all'inizio del turno e non alla fine... possono incominciare
immediatamente un'invasione nello stesso turno"), and [8.2]'s Druidic
mutual-Treat alliance ("diventano alleati prima dell'inizio del turno").
This project's own turn engine has no existing "orders submitted this
turn take effect starting next turn" mechanism for *any* other order
type (every Move/Explore/etc. order is read and applied within the same
``run_turn()`` call it's submitted for) -- inventing one here, just for
this one rule, to support a maximally literal reading of "alla fine"
would be new machinery nothing else in this project needs or exercises.
``apply_treat_orders()`` is therefore called once, early in ``run_turn()``
(mirroring ``advance_blackmail_claims()``'s own "before any phase
dispatches" placement) -- every transition it computes, not only the two
timed exceptions, becomes visible to that same turn's own combat. This
exactly reproduces the two exceptions' own real effect (same-turn
visibility) and is a conservative, explicitly documented simplification
for the ordinary case (one phase earlier than a maximally literal "end
of turn" reading), never a silent guess.

**[8.1]'s own "triangle" case -- a Kingdom X allied to both Y and Z, who
are themselves enemies of each other.** Closed via ``is_attackable_at()``
below, consumed by every one of this project's own three defender-
gathering call sites (``turn/move_execution.py execute_move()``,
``turn/battle_orchestrator.py fight_battle()``/``fight_multi_attacker_
battle()``). The rulebook's own text ("Y e Z possono marciare attraverso
il territorio di X per attaccarsi a vicenda, ma nessuna battaglia può
avvenire tra loro sul territorio di quest'ultimo") turns out to need no
triangle-specific code at all: it falls out of one general principle --
territory owned by a Kingdom Allied with the attacker shields *every*
army physically present there from that attacker, not just the
territory owner's own forces (already covered by the ordinary ``is_
allied()`` check on the defending army itself). The other half of the
rule ("se X comanda forze presenti... nella provincia di Y invasa da Z,
le sue forze combattono con Y contro Z") needs no new code either: X's
forces, merely co-located (not attacking), are already swept into the
ordinary non-allied-with-the-attacker defender pool today. The rule's own
closing sentence ("in nessuno di questi casi il Re X può dare assistenza
in attacco") is likewise already structurally guaranteed, not something
to additionally enforce: X moving against its own ally Z's territory is
never framed as an attack in the first place (RULES.AK [8.1]'s own
"alleati... hanno libero passaggio," wired as the Allied-passage case
right alongside the Neutral-move block), so X can never appear as an
*attacking* party against Z to begin with -- there is no uniting
contingent for it to join.
"""

from __future__ import annotations

from ak_engine.models.alignment import Alignment
from ak_engine.models.game_state import GameState, ProvinceState
from ak_engine.parser.gw_world import DiplomaticRelation

_RELATION_RANK: dict[DiplomaticRelation, int] = {
    DiplomaticRelation.ENEMY: 0,
    DiplomaticRelation.NEUTRAL: 1,
    DiplomaticRelation.ALLIED: 2,
}
_RELATION_BY_RANK: dict[int, DiplomaticRelation] = {rank: relation for relation, rank in _RELATION_RANK.items()}


def _downgrade(relation: DiplomaticRelation) -> DiplomaticRelation:
    return _RELATION_BY_RANK[max(_RELATION_RANK[relation] - 1, 0)]


def _upgrade(relation: DiplomaticRelation) -> DiplomaticRelation:
    return _RELATION_BY_RANK[min(_RELATION_RANK[relation] + 1, 2)]


def _is_druid(state: GameState, kingdom_id: int) -> bool:
    kingdom = state.kingdoms.get(kingdom_id)
    return kingdom is not None and kingdom.alignment is Alignment.DRUID


def is_attackable_at(
    state: GameState, defender_kingdom_id: int, attacker_kingdom_id: int, province: ProvinceState
) -> bool:
    """[8.1]'s own "triangle" rule, generalized (see module docstring):
    an army of ``defender_kingdom_id`` physically present at ``province``
    is a legitimate target for ``attacker_kingdom_id``'s own move/battle
    there only if (a) the two Kingdoms aren't themselves Allied (the
    ordinary rule), AND (b) ``province`` isn't owned by a *third*
    Kingdom who is Allied with the attacker -- an Allied territory owner
    shields every army present, not just their own. Reusable at every
    defender-gathering call site (``turn/move_execution.py``,
    ``turn/battle_orchestrator.py``) so the two project-wide "who's a
    legitimate target here" checks never drift apart.
    """

    if state.is_allied(defender_kingdom_id, attacker_kingdom_id):
        return False
    if province.owner_kingdom_id is not None and state.is_allied(province.owner_kingdom_id, attacker_kingdom_id):
        return False
    return True


def _set_relation(state: GameState, kingdom_a: int, kingdom_b: int, relation: DiplomaticRelation) -> None:
    pair = frozenset({kingdom_a, kingdom_b})
    state.diplomatic_relations[pair] = relation
    if relation is DiplomaticRelation.ALLIED:
        state.allied_kingdoms.add(pair)
        state.diplomatic_relations_since[pair] = state.turn_number
    else:
        state.allied_kingdoms.discard(pair)


def apply_treat_orders(state: GameState) -> None:
    """Resolves this turn's own Treat (``state.treat_permissions``) and
    Break Treat (``state.break_treat_orders``) orders into real
    ``diplomatic_relations`` transitions -- see module docstring for
    where each input comes from and for the call-timing simplification.

    Per Kingdom pair with at least one order this turn, quoting [8.2]/
    [8.3] directly:

    - **Break Treat is unilateral**: "[un ordine Break Treat] 'declassa'
      di una sola posizione per volta" -- either side issuing it alone
      downgrades the relation one step (Allied -> Neutral -> Enemy,
      floored at Enemy). "Se due alleati danno l'ordine Break Treat
      l'uno verso l'altro nello stesso turno, diventano nemici" -- *both*
      sides issuing it the same turn on a currently-Allied pair jumps
      straight to Enemy instead (skipping Neutral). A Break Treat order
      always takes precedence over any Treat order between the same pair
      this turn (this is also exactly how [8.2]'s own Druidic veto reads:
      "[l'alleanza forma] a meno che [l'altro Re] non impartisca un
      ordine Break Treat nello stesso turno").
    - **Treat requires mutuality**: "[un ordine Treat] trasforma i
      rapporti di ostilità in neutralità e quelli di neutralità in
      alleanza, ma solo se entrambi i Re danno lo stesso ordine Treat
      nello stesso turno" -- one step up (Enemy -> Neutral -> Allied),
      only when *both* sides issue Treat toward each other this turn.
    - **Druidic exceptions** ([8.2]): a Druidic Kingdom's own one-sided
      Treat toward a currently-*Neutral* partner forms an alliance even
      without a matching Treat from that partner ("i diplomatici di
      questo secondo Reame si faranno influenzare... un'alleanza verrà
      quindi sottoscritta anche senza un ordine Treat da parte
      dell'altro Re") -- scoped to Neutral starting points only, per the
      quoted text's own "con il quale ha rapporti di neutralità." A
      *mutual* Treat with at least one Druidic party jumps straight from
      Enemy to Allied in one turn instead of the ordinary one-step-at-a-
      time schedule ("se un Re Druidico e un altro Re stringono un
      trattato di alleanza reciproco, diventano alleati... anche se in
      precedenza erano nemici").

    A pair with no net change (e.g. a lone Treat toward a non-Druidic
    partner who doesn't reciprocate) is left untouched -- no entry is
    written, no ``diplomatic_relations_since`` timestamp updated.
    """

    pairs = {frozenset({a, b}) for a, b in state.treat_permissions if a != b}
    pairs |= {frozenset({a, b}) for a, b in state.break_treat_orders if a != b}

    for pair in pairs:
        kingdom_a, kingdom_b = sorted(pair)
        current = state.diplomatic_relation(kingdom_a, kingdom_b)

        a_break = (kingdom_a, kingdom_b) in state.break_treat_orders
        b_break = (kingdom_b, kingdom_a) in state.break_treat_orders
        a_treat = (kingdom_a, kingdom_b) in state.treat_permissions
        b_treat = (kingdom_b, kingdom_a) in state.treat_permissions

        new_relation = current
        if a_break and b_break and current is DiplomaticRelation.ALLIED:
            new_relation = DiplomaticRelation.ENEMY
        elif a_break or b_break:
            new_relation = _downgrade(current)
        elif a_treat and b_treat:
            if current is DiplomaticRelation.ENEMY and (_is_druid(state, kingdom_a) or _is_druid(state, kingdom_b)):
                new_relation = DiplomaticRelation.ALLIED
            else:
                new_relation = _upgrade(current)
        elif current is DiplomaticRelation.NEUTRAL and (
            (a_treat and _is_druid(state, kingdom_a)) or (b_treat and _is_druid(state, kingdom_b))
        ):
            new_relation = DiplomaticRelation.ALLIED

        if new_relation is not current:
            _set_relation(state, kingdom_a, kingdom_b, new_relation)
