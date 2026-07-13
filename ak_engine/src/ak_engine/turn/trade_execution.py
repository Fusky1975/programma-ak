"""Executing Trade/Give's one confirmed sub-rule: a King's Gold Give cap -- Phase 132.

**Why this module exists but does *not* consume ``TradeRequest``, and is
*not* wired into ``plan_dispatch.py``'s TRADE dispatch.** ``turn/
trade_decode.py``'s own docstring already documents, in detail, why
Trade is "by a wide margin, the least-confirmed decode module in this
project": ``obj`` is confirmed ambiguous (item id *or* gold amount, no
discriminator anywhere in the available source), there is no confirmed
recipient field at all (the rulebook requires "a co-located character
who will receive it," but neither ``DEF2.PAS``'s ``R_HPlan``/``W_HPlan``
nor this project's own pattern-matched ``extra[1]`` inference names one
with any confidence), zero real Trade phases exist in any of the 10
sample ``AK3__T*.K1`` files to empirically validate against, and the
Pascal source tree has no turn-execution engine for *any* action, Trade
included (only the plan read/write/report-text layers survive).

Given all of that, auto-deriving "who receives this Give and what
exactly are they receiving" from a decoded move-file phase would mean
inventing data this project cannot see -- exactly what the standing
project rule forbids. So this module does **not** attempt "real Trade
execution" in the sense every other ``turn/*_execution.py`` module
means it (decode a real phase, mutate ``GameState`` from it). Instead it
implements the *one* sub-rule of [3.18] that is fully, unambiguously
sourced and requires no recipient inference to state as a general rule:

    "You can give limited amounts of gold to other Kings. Only a King
    may use this 'Give Gold' order. [...] A King may give out in a
    gameturn no more than 10% of the size of his treasury [...]"

``execute_gold_give()`` takes the giver and the gold amount to move
(both real, typed ``GameState`` inputs) plus an explicit
``recipient_kingdom_id`` **supplied by the caller**, not decoded from
``TradeRequest.obj``/``extra`` -- this module makes no claim about
*how* a caller would come to know the recipient from a real move file;
it only implements the treasury-mutation rule once a recipient is known
by whatever means. This mirrors this project's existing "built but not
auto-invoked from decode" precedent (``fight_multi_attacker_battle``,
Phase 28; ``execute_practice_group``, Phase 46) -- except here the
reason isn't test-suite RNG stability, it's a genuine, confirmed
absence of a decodable recipient field.

**A magic-item Give (the other half of [3.18]) isn't attempted at all,
even at this reduced scope**: unlike gold (which only touches the
already-modeled ``KingdomState.treasury``), moving a magic item between
characters needs a per-leader item-ownership model this project has
never built -- ``models/item.py`` is still "a stub for a future phase,
not populated by the move parser" (Phase 1). That's a second,
independent structural gap on top of the missing recipient, not merely
an extension of this same module.
"""

from __future__ import annotations

from dataclasses import dataclass

from ak_engine.models.game_state import GameState

# Rulebook [3.18]: "no more than 10% of the size of his treasury."
GOLD_GIVE_MAX_PERCENT = 10


@dataclass(slots=True)
class TradeExecutionResult:
    applied: bool
    reason: str | None = None
    gold_transferred: int = 0


def execute_gold_give(
    state: GameState,
    giver_leader_id: int,
    recipient_kingdom_id: int,
    gold_amount: int,
) -> TradeExecutionResult:
    """Move gold from a King's own kingdom treasury to another kingdom's, enforcing
    rulebook [3.18]'s 10%-of-treasury cap. See module docstring for why
    ``recipient_kingdom_id`` is a required, caller-supplied parameter
    rather than something decoded from a real move-file phase.
    """

    giver = state.leaders.get(giver_leader_id)
    if giver is None:
        return TradeExecutionResult(applied=False, reason="giver not found")
    if not giver.is_king:
        # "Only a King may use this 'Give Gold' order."
        return TradeExecutionResult(applied=False, reason="only a King may Give Gold")
    if giver.kingdom_id is None:
        return TradeExecutionResult(applied=False, reason="giver has no kingdom")

    giver_kingdom = state.kingdoms.get(giver.kingdom_id)
    recipient_kingdom = state.kingdoms.get(recipient_kingdom_id)
    if giver_kingdom is None or recipient_kingdom is None:
        return TradeExecutionResult(applied=False, reason="kingdom not found")

    if gold_amount <= 0:
        return TradeExecutionResult(applied=False, reason="gold amount must be positive")

    cap = giver_kingdom.treasury * GOLD_GIVE_MAX_PERCENT // 100
    if gold_amount > cap:
        return TradeExecutionResult(applied=False, reason=f"exceeds 10% treasury cap ({cap})")

    giver_kingdom.treasury -= gold_amount
    recipient_kingdom.treasury += gold_amount
    return TradeExecutionResult(applied=True, gold_transferred=gold_amount)
