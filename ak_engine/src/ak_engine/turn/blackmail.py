"""``AdvancedAbility.SPY_BLACKMAIL`` -- Phase 713.

Real text (``models/advanced_ability.py``, ordinal 48): "When the Spy
Trails (TR command) a foreign king and ends any phase in the same
province, there is about a 20% chance of getting some dirt on him. If
that happens, a message is delivered, with instructions to pay off
your kingdom (the amount will average about 15 gold). If no payola is
coughed up, he will lose 3 times that much in tax revenues when the
dirt is given to the tabloids, causing great social turmoil. If the
blackmail money isn't paid, the next attempt will be worth about half
as much gold. Note: it's easier to find dirt on a king tending towards
evil, harder for good kings; but evil kings pay less gold because
their bad habits are already somewhat known; and, rich kings pay more
gold. Blackmail is usable once per turn on a kingdom."

**The payment mechanism is fully resolved by a second, independent
source**: ``AKPROSE_reverse_engineering_report.md`` (choice 080/090)
preserves the real ``SAY.PAS`` demand-delivery message verbatim (see
``report/turn_report.py render_blackmail_demand()``), and it names the
real payment path directly: "[the victim king] must personally execute
a 'Give' order to King [the blackmailer's own Kingdom number] in this
amount, sometime in the upcoming gameturn, or else lose 3 times that
much gold in taxes for one turn... The money will be automatically
transferred without any need for the kings to be in the same
province." This is this project's own already-real ``ActionCode.
TRADE``/``turn/trade_execution.py execute_give()`` gold-Give order,
with one real, sourced exception (no co-location requirement) wired
directly into that function -- see its own Phase 713 addendum.

**The two-turn "pending, then due" shape is a real, sourced mechanic,
not invented**: it mirrors the real parsed ``parser/gw_world.py
GWKingExtension.pending_blackmailer_king_id``/``active_blackmailer_
king_id`` field PAIR exactly. A demand delivered this turn sits as
``KingdomState.pending_blackmail`` (not yet due -- the victim hasn't
even seen the report yet); ``advance_blackmail_claims()`` promotes it
to ``KingdomState.active_blackmail`` (due this turn) at the very start
of the *next* real turn, before any phase dispatches -- mirroring
``turn/turn_processor.py run_turn()``'s own Phase 669 SEP pre-loop
placement exactly. Whichever of the two is set also implements the
real "usable once per turn on a kingdom" cap: no new demand can be
created against a Kingdom that already has one outstanding, of either
kind.

**Detection chance and demand-amount formulas are documented,
unsourced-but-reasonable interpretations** of the ability's own
qualitative description (no exact formula survives) -- the same class
of choice as e.g. ``AdvancedAbility.THIEF_TREASURY_RAIDS``'s own "up to
half the treasury" magnitude (Phase 702). Detection is modulated by the
target's own ``models/alignment.py ALIGNMENT_ORDINAL`` (0=Divine ..
7=Undead, clamped to that real "outlook" range): +/-3 percentage points
per ordinal step away from Worldly/Neutral (ordinal 3, the spectrum's
own midpoint) toward the Undead end, floored/ceilinged. The demand
amount starts at 15 gold, +1 gold per 100 gold of the target's own
treasury ("rich kings pay more"), -1 gold per ordinal step past Neutral
toward Undead ("evil kings pay less" -- never a bonus for the good
side, matching the text's own one-directional framing), floored at 5,
then halved once per the spy's own ``LeaderState.unpaid_blackmail_
penalty_exponent`` (the real parsed field's own "halves the next
demand each time it's incremented" behavior).

**Phase 741 closes the report-line gap this addendum used to flag.**
No new report text survives anywhere for "the tax penalty applied" --
only the one demand-delivery message (`render_blackmail_demand()`)
exists in the whole corpus -- but that message's own sourced clause
("or else lose 3 times that much gold in taxes for one turn, as a
result of lost prestige") gave enough real material to build a close-
paraphrase, user-approved, project-original FINANCES-report line from.
See `models/game_state.py UnpaidBlackmailPenalty`/`turn/tax_base.py
apply_turn_revenue()`'s own Phase 741 addendum for the real recording
mechanism, and `report/turn_report.py render_blackmail_penalty()` for
the render side.
"""

from __future__ import annotations

import random

from ak_engine.models.alignment import ALIGNMENT_ORDINAL, Alignment
from ak_engine.models.game_state import BlackmailClaim, GameState, LeaderState

# Base ~20% chance of "getting some dirt" per phase-end co-located with
# a foreign King. See module docstring -- unsourced magnitude.
BLACKMAIL_BASE_DETECTION_CHANCE = 0.20
# +/-3 percentage points per ALIGNMENT_ORDINAL step away from Worldly/
# Neutral (ordinal 3) toward Undead ("easier ... evil, harder ... good").
BLACKMAIL_DETECTION_ALIGNMENT_STEP = 0.03
BLACKMAIL_DETECTION_CHANCE_FLOOR = 0.05
BLACKMAIL_DETECTION_CHANCE_CEIL = 0.40

# "the amount will average about 15 gold".
BLACKMAIL_BASE_DEMAND_GOLD = 15
# "rich kings pay more gold" -- +1 gold per 100 gold of treasury.
BLACKMAIL_DEMAND_TREASURY_DIVISOR = 100
# "evil kings pay less gold" -- -1 gold per ordinal step past Neutral(3)
# toward Undead(7); never a bonus for the good side (the text only ever
# describes a reduction for evil-tending kings).
BLACKMAIL_DEMAND_ALIGNMENT_STEP = 1
BLACKMAIL_DEMAND_FLOOR = 5

# "he will lose 3 times that much in tax revenues".
BLACKMAIL_UNPAID_TAX_MULTIPLIER = 3

# The real "outlook" spectrum this ability's alignment text describes
# (Heavenly/Divine .. Undead) -- Mechanical/Special sit outside it and
# are clamped in, same as several other alignment-gradient formulas
# elsewhere in this project (e.g. `turn/hire_pay.py _norm_align()`).
_ALIGNMENT_ORDINAL_FLOOR = 0
_ALIGNMENT_ORDINAL_CEIL = 7
_ALIGNMENT_ORDINAL_NEUTRAL = 3


def _clamped_ordinal(alignment: Alignment) -> int:
    return max(_ALIGNMENT_ORDINAL_FLOOR, min(_ALIGNMENT_ORDINAL_CEIL, ALIGNMENT_ORDINAL[alignment]))


def blackmail_detection_chance(target_alignment: Alignment) -> float:
    ordinal = _clamped_ordinal(target_alignment)
    chance = BLACKMAIL_BASE_DETECTION_CHANCE + BLACKMAIL_DETECTION_ALIGNMENT_STEP * (ordinal - _ALIGNMENT_ORDINAL_NEUTRAL)
    return max(BLACKMAIL_DETECTION_CHANCE_FLOOR, min(BLACKMAIL_DETECTION_CHANCE_CEIL, chance))


def blackmail_demand_amount(target_alignment: Alignment, target_treasury: int, spy_exponent: int) -> int:
    ordinal = _clamped_ordinal(target_alignment)
    base = BLACKMAIL_BASE_DEMAND_GOLD + target_treasury // BLACKMAIL_DEMAND_TREASURY_DIVISOR
    base -= max(0, ordinal - _ALIGNMENT_ORDINAL_NEUTRAL) * BLACKMAIL_DEMAND_ALIGNMENT_STEP
    base = max(BLACKMAIL_DEMAND_FLOOR, base)
    return max(1, round(base * (0.5**spy_exponent)))


def advance_blackmail_claims(state: GameState) -> None:
    """Promotes every Kingdom's own still-``pending_blackmail`` demand
    (delivered last turn) into ``active_blackmail`` (due this turn).
    Called once, at the very start of ``run_turn()``, before any phase
    dispatches -- see module docstring.
    """

    for kingdom in state.kingdoms.values():
        if kingdom.pending_blackmail is not None:
            kingdom.active_blackmail = kingdom.pending_blackmail
            kingdom.pending_blackmail = None


def maybe_detect_blackmail(
    state: GameState, trailer: LeaderState, target: LeaderState, rng: random.Random
) -> BlackmailClaim | None:
    """One phase-end's worth of "ends the phase in the same province with
    a foreign king" detection roll -- called from ``turn/trail_
    execution.py`` whenever a Trail catch-up succeeds (``spied_on``) and
    the trailer holds the ability. Returns ``None`` (no roll, or a
    failed roll) unless every real precondition holds: the target is a
    King, both sides have a real, *different* Kingdom, and that
    Kingdom has no already-outstanding claim of either kind (the real
    "usable once per turn on a kingdom" cap).
    """

    if not target.is_king or target.kingdom_id is None:
        return None
    if trailer.kingdom_id is None or trailer.kingdom_id == target.kingdom_id:
        return None

    target_kingdom = state.kingdoms.get(target.kingdom_id)
    if target_kingdom is None or target_kingdom.pending_blackmail is not None or target_kingdom.active_blackmail is not None:
        return None

    # A King's own personal Alignment may not be recorded ("no data" --
    # same convention `execute_trail()`'s own `race` fallback already
    # uses a few lines above its Phase 705 addendum) -- fall back to
    # the Kingdom's own Alignment, always real.
    target_alignment = target.alignment if target.alignment is not None else target_kingdom.alignment

    if rng.random() >= blackmail_detection_chance(target_alignment):
        return None

    amount = blackmail_demand_amount(target_alignment, target_kingdom.treasury, trailer.unpaid_blackmail_penalty_exponent)
    claim = BlackmailClaim(spy_leader_id=trailer.leader_id, spy_kingdom_id=trailer.kingdom_id, amount=amount)
    target_kingdom.pending_blackmail = claim
    return claim


def resolve_unpaid_blackmail(state: GameState, kingdom_id: int) -> int:
    """Called once per Kingdom from ``turn/tax_base.py apply_turn_
    revenue()`` -- if that Kingdom's own ``active_blackmail`` claim
    survived the turn unpaid (``turn/trade_execution.py execute_give()``
    clears it the moment a matching Give order pays it off), applies
    the real "3 times that much" tax-revenue penalty, increments the
    spy's own halving exponent for their next demand, and clears the
    claim. Returns ``0`` when there's nothing outstanding.

    **Phase 1192 bug fix**: the spy's own exponent increment is applied
    whether the spy is still in ``state.leaders`` or has since died and
    been archived into ``state.dead_leaders`` (``GameState.remove_
    leader()`` moves, never destroys, the ``LeaderState``) -- the spy
    placing the demand earlier the same turn and then dying in combat
    before this later end-of-turn step runs is a real, reachable
    ordering, and the increment matters for a future Resurrection of
    that same leader.
    """

    kingdom = state.kingdoms.get(kingdom_id)
    if kingdom is None or kingdom.active_blackmail is None:
        return 0

    claim = kingdom.active_blackmail
    kingdom.active_blackmail = None
    # Phase 1192 bug fix: a spy who died earlier the same turn (e.g. in
    # combat) is moved to GameState.dead_leaders by remove_leader(), not
    # destroyed -- a bare state.leaders.get() missed that archive and
    # silently dropped the escalation, even though the LeaderState (and
    # a future Resurrection's use of it) still exists.
    spy = state.leaders.get(claim.spy_leader_id) or state.dead_leaders.get(claim.spy_leader_id)
    if spy is not None:
        spy.unpaid_blackmail_penalty_exponent += 1
    return claim.amount * BLACKMAIL_UNPAID_TAX_MULTIPLIER
