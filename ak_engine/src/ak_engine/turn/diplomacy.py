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

**Why the Treat order itself isn't a second, parallel input here**:
this module's own earlier phases justified reading ``GameState.treat_
permissions``/``break_treat_orders`` (GM/caller-populated, not decoded
from a file) instead of a real K1 order field by claiming "no real K1
move file has ever shown a recognizable Treat/Break Treat order shape."
**Stale as of Phase 1192 -- that claim was already false when written.**
``models/kingdom.py KingdomMoveHeader.allreq``/``.brreq`` (Phase 920,
earlier than this module's own Phase 1026/869 claims) are exactly that
shape: a confirmed-decoded, cross-validated Treat (``allreq``)/Break
Treat (``brreq``) per-Kingdom-id request bitmask, matching real
``GWKingExtension`` data turn-for-turn across all 10 real sample turns
and reproducing the real diplomatic-relation downgrade the very next
turn with zero exceptions -- see that property's own docstring for the
full two-part confirmation. They're real, decoded, correct, and simply
never read by this module (or anywhere else -- confirmed by grep). This
module still reads ``treat_permissions``/``break_treat_orders`` as its
Treat/Break-Treat signal for now (GM-populated, same as before) rather
than ``allreq``/``brreq`` directly -- wiring the real decoded fields in
is a separate, not-yet-done follow-up, not something this docstring
should keep claiming is impossible. ``(owner_kingdom_id, recruiter_
kingdom_id)`` in ``treat_permissions`` is read here as "``owner_
kingdom_id`` issued a Treat order toward ``recruiter_kingdom_id`` this
turn."

**Timing.** [8] frames ordinary Treat/Break Treat as resolved "alla fine
di ciascun turno" (at the end of each turn), except two explicit
exceptions that take effect *before* the turn's own combat: [8.3]'s
Evil/Undead Break Treat ("danno l'ordine... all'inizio del turno e non
alla fine... possono incominciare immediatamente un'invasione nello
stesso turno"), and [8.2]'s Druidic mutual-Treat alliance ("diventano
alleati prima dell'inizio del turno").

**2026-11-03 -- the Break Treat half of this is now modeled for real,
not simplified away.** This paragraph used to apply every transition
uniformly, early in the same turn it was ordered, as "a conservative
simplification" for the ordinary (non-exception) case -- true for Treat
(see below), but for Break Treat this silently handed *every* King the
same same-turn-invasion advantage [8.3] reserves for Evil/Undead alone.
``apply_treat_orders()`` now splits on this directly: a pair's own
Break-Treat-driven transition is written to ``diplomatic_relations``
immediately only when at least one of the Kings who issued the break
this turn is Evil or Undead (``_is_evil_or_undead()`` below); otherwise
it's deferred into ``GameState.pending_break_treat_transitions`` and
only promoted into a real transition -- visible to *that* turn's own
combat -- by ``advance_pending_diplomacy()``, called at the very start
of the *next* ``run_turn()``, before that turn's own fresh orders are
read. This reproduces [8.3]'s own "un turno per rischiarare le proprie
forze" grace period exactly: an ordinary Break Treat changes nothing
until the turn after it's issued.

**2026-11-05 -- Treat's own timing is now modeled for real too, the
same way Break Treat's was.** This paragraph used to say "out of scope"
here, reasoning the project had no generic deferred-order mechanism and
Treat (unlike Break Treat) hands nobody an Alignment-gated advantage
worth the trouble -- true as far as it went, but the real distinction
is narrower than "ordinary vs. Druidic": **the only sourced same-turn
exception is [8.2]'s own *mutual* Treat involving a Druidic party**
("diventano alleati prima dell'inizio del turno"); a Druidic Kingdom's
own one-sided Treat toward a Neutral partner (the OTHER [8.2] carve-out,
forming an alliance without reciprocation) has no such timing text at
all, and -- confirmed directly with the user -- follows the same "alla
fine del turno" schedule as an ordinary, non-Druidic mutual Treat (the
user-supplied rulebook quote for both carve-outs is in ``apply_treat_
orders()``'s own docstring below). So:

- **Ordinary mutual Treat, and the Druidic one-sided-toward-Neutral
  case**: deferred into ``GameState.pending_treat_transitions``, the
  same mechanism and promotion point (``advance_pending_diplomacy()``,
  start of the *next* ``run_turn()``) ``pending_break_treat_
  transitions`` already uses -- confirmed with the user: shown only in
  that later turn's own DIPLOMACY report section once it takes effect,
  **no** ``diplomacy_relation_change_notices`` entry (unlike a Break
  Treat promotion, nobody needs advance warning of good news the way
  [8.3]'s own grace period exists to give a victim of war).
- **Mutual Treat with at least one Druidic party**: immediate, same
  turn, regardless of whether the pair started Neutral (ordinary one-
  step upgrade to Allied, just not deferred) or Enemy (the already-
  modeled skip-straight-to-Allied case) -- confirmed with the user, and
  gets a ``diplomacy_relation_change_notices`` entry too (also
  confirmed: "anche qui viene scritto nel report all'inizio" -- the
  same top-of-ACTION-REPORT placement a Break Treat notice already
  gets, not scoped to war declarations specifically after all).

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


def _is_evil_or_undead(state: GameState, kingdom_id: int) -> bool:
    """[8.3]'s own Break Treat timing exception ("I Re Malvagi e
    Non-Morti...") -- mirrors ``_is_druid()`` right above, same
    Kingdom-level (not leader-level) alignment reading.
    """

    kingdom = state.kingdoms.get(kingdom_id)
    return kingdom is not None and kingdom.alignment in (Alignment.EVIL, Alignment.UNDEAD)


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


def set_relation(state: GameState, kingdom_a: int, kingdom_b: int, relation: DiplomaticRelation) -> None:
    """Writes a Kingdom pair's own ``diplomatic_relations`` entry, keeping
    ``allied_kingdoms``/``diplomatic_relations_since`` in sync -- the one
    real primitive both ``apply_treat_orders()`` (below) and the GM web
    interface's own direct-override route (``webapp/app.py
    turns_diplomacy_set_relation()``, for scenario setup -- e.g. starting
    two Kingdoms already at War or Allied without playing out several
    turns of Treat/Break Treat orders first) build on, so the two never
    drift into writing this trio of fields differently. Public (no
    leading underscore) for exactly that second caller.

    **Phase 1192 bug fix**: rejects ``DiplomaticRelation.TEAMED`` with a
    clear ``ValueError`` instead of silently writing it. ``_RELATION_
    RANK`` above only knows the 3 relations [8] itself describes --
    module docstring's own "never produced by this module" note already
    says TEAMED support is deferred pending the user's own confirmation
    (the one real caller outside this module, ``webapp/app.py``'s GM
    override route, already enforces the same restriction at its own
    call site, but this function is the shared primitive both real
    callers build on, so it shouldn't rely on every future caller
    remembering to repeat that check). Writing TEAMED through here
    before this fix would silently succeed, only to crash much later
    and far less clearly -- an uncaught ``KeyError`` inside ``_downgrade``/
    ``_upgrade`` the next time any Treat/Break Treat order touches this
    same pair.
    """

    if relation not in _RELATION_RANK:
        raise ValueError(
            f"{relation} isn't one of the {len(_RELATION_RANK)} relations this project currently models "
            "(TEAMED support is deliberately deferred -- see module docstring)"
        )

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
      this turn (this is also exactly how [8.2]'s own Druidic veto reads
      -- quoted in full right below).
    - **Treat requires mutuality**: "[un ordine Treat] trasforma i
      rapporti di ostilità in neutralità e quelli di neutralità in
      alleanza, ma solo se entrambi i Re danno lo stesso ordine Treat
      nello stesso turno" -- one step up (Enemy -> Neutral -> Allied),
      only when *both* sides issue Treat toward each other this turn.
    - **Druidic exceptions** ([8.2], quoted in full -- user-supplied,
      2026-11-06): "Quando un Reame Druidico stringe un trattato con un
      altro Reame con il quale ha rapporti di neutralità, i diplomatici
      di questo secondo Reame si faranno influenzare dalla persuasività
      e dalla dottrina dell'armonia druidica. Un'alleanza verrà quindi
      sottoscritta anche senza un ordine Treat da parte dell'altro Re, a
      meno che questo non impartisca un ordine Break Treat nello stesso
      turno. I personaggi Druidici inoltre stringono alleanze più
      velocemente. Se un Re Druidico e un altro Re stringono un trattato
      di alleanza reciproco, diventano alleati prima dell'inizio del
      turno, anche se in precedenza erano nemici." -- so: a Druidic
      Kingdom's own one-sided Treat toward a currently-*Neutral* partner
      forms an alliance even without a matching Treat from that partner,
      unless that partner issues a Break Treat of its own this same turn
      (already guaranteed above -- Break Treat is checked, and wins,
      before this one-sided case is ever reached). A *mutual* Treat with
      at least one Druidic party jumps straight from Enemy to Allied in
      one turn instead of the ordinary one-step-at-a-time schedule, and
      resolves "prima dell'inizio del turno" (see Timing below).
    - **Timing** (see module docstring's own 2026-11-05 addendum for the
      full citations): a *mutual* Treat with at least one Druidic party
      is immediate, same turn -- the one-sided Druidic case above is
      not, and neither is an ordinary (non-Druidic) mutual Treat; both
      of those are deferred to the start of next turn exactly like an
      ordinary Break Treat, via ``GameState.pending_treat_transitions``
      and this same function's own ``advance_pending_diplomacy()``
      sibling.

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
        break_driven = a_break or b_break
        mutual_treat = a_treat and b_treat
        druid_party = _is_druid(state, kingdom_a) or _is_druid(state, kingdom_b)

        new_relation = current
        if a_break and b_break and current is DiplomaticRelation.ALLIED:
            new_relation = DiplomaticRelation.ENEMY
        elif a_break or b_break:
            new_relation = _downgrade(current)
        elif mutual_treat:
            if current is DiplomaticRelation.ENEMY and druid_party:
                new_relation = DiplomaticRelation.ALLIED
            else:
                new_relation = _upgrade(current)
        elif current is DiplomaticRelation.NEUTRAL and (
            (a_treat and _is_druid(state, kingdom_a)) or (b_treat and _is_druid(state, kingdom_b))
        ):
            new_relation = DiplomaticRelation.ALLIED

        if new_relation is current:
            continue

        if break_driven:
            # [8.3]'s own timing exception: a Break Treat order from an
            # Evil or Undead King resolves "all'inizio del turno," same
            # turn's combat included -- every other King's own Break
            # Treat still resolves "alla fine del turno," so it's
            # deferred to the start of next turn instead (``advance_
            # pending_diplomacy()`` below), rather than applied here.
            immediate = (a_break and _is_evil_or_undead(state, kingdom_a)) or (
                b_break and _is_evil_or_undead(state, kingdom_b)
            )
            if immediate:
                set_relation(state, kingdom_a, kingdom_b, new_relation)
                state.diplomacy_relation_change_notices.append((kingdom_a, kingdom_b, current, new_relation))
            else:
                state.pending_break_treat_transitions[pair] = (current, new_relation)
            continue

        # [8.2]'s own timing exception: a *mutual* Treat with at least
        # one Druidic party resolves "prima dell'inizio del turno," same
        # turn's combat included (whether starting Neutral -> Allied or
        # the already-modeled Enemy -> Allied skip) -- confirmed with
        # the user. Every other Treat-driven transition -- an ordinary
        # mutual Treat between two non-Druidic Kingdoms, *and* a
        # Druidic Kingdom's own one-sided Treat toward a Neutral partner
        # (no "prima dell'inizio" text covers that narrower carve-out)
        # -- still resolves "alla fine del turno": deferred the same way
        # Break Treat's own ordinary case is, confirmed with the user.
        if mutual_treat and druid_party:
            set_relation(state, kingdom_a, kingdom_b, new_relation)
            state.diplomacy_relation_change_notices.append((kingdom_a, kingdom_b, current, new_relation))
        else:
            state.pending_treat_transitions[pair] = (current, new_relation)


def advance_pending_diplomacy(state: GameState) -> None:
    """Promotes every still-pending Break Treat *and* Treat transition
    into a real ``diplomatic_relations`` change, visible to *this*
    turn's own combat -- called once, at the very start of
    ``run_turn()``, before that same turn's own fresh
    ``apply_treat_orders()`` call. Mirrors ``turn/blackmail.py
    advance_blackmail_claims()``'s own pending -> active promotion,
    called at the exact same point in the turn for the same reason.

    A pair promoted from ``pending_break_treat_transitions`` (an
    ordinary King's own Break Treat, deferred by ``apply_treat_
    orders()`` per [8.3]'s own timing) also gets a fresh ``diplomacy_
    relation_change_notices`` entry -- the whole reason for the one-turn
    delay is so the affected King finds out *before* this turn's own
    combat, not after. A pair promoted from ``pending_treat_
    transitions`` (an ordinary mutual Treat, or a Druidic Kingdom's own
    one-sided Treat toward a Neutral partner -- see module docstring)
    gets **no** notice -- confirmed with the user: it's shown only in
    that later turn's own DIPLOMACY report section, the same as if it
    had never been deferred at all.
    """

    for pair, (old_relation, new_relation) in state.pending_break_treat_transitions.items():
        kingdom_a, kingdom_b = sorted(pair)
        set_relation(state, kingdom_a, kingdom_b, new_relation)
        state.diplomacy_relation_change_notices.append((kingdom_a, kingdom_b, old_relation, new_relation))
    state.pending_break_treat_transitions = {}

    for pair, (_old_relation, new_relation) in state.pending_treat_transitions.items():
        kingdom_a, kingdom_b = sorted(pair)
        set_relation(state, kingdom_a, kingdom_b, new_relation)
    state.pending_treat_transitions = {}
