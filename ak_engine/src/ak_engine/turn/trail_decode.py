"""Decoding a Trail PlanPhase (rulebook [3.17] Trail).

Trail is Pursue's simpler sibling -- same "follow a character id" target,
but confirmed to carry **no** Encounter Plan tactic list, unlike Pursue/
Challenge/Search (see ``turn/challenge_pursue_decode.py``). The Italian
rulebook states this relationship explicitly, more plainly than the
English `RULES.AK`: "In pratica il Trail è simile al Pursue, solo che il
primo non genera un Piano d'Incontro, il secondo invece sì." ("In
practice Trail is similar to Pursue, except the former doesn't generate
an Encounter Plan, while the latter does.")

Rulebook [3.17] (quoted in full): "The character follows and spies on a
character, gaining information on the character's Actions, race,
temper, alignment, treasures owned and armies led. If the character is
a King, some information may be gained concerning the finances,
alliances, enemies and controlled provinces of the Kingdom... Like the
Pursue order, the Trail order ends when the character finds and has
spied on the character for one phase... A character leading an army may
not be ordered to Trail." Success uses the same Spy Table as Pursue
([4.33]: base chance by Spy level, doubled if the target leads an army,
divided by distance, 100% if same Kingdom) -- none of this resolution
logic is modeled here.

Sourced from ``HostAK/TP/DEF2.PAS``'s ``R_HPlan``/``W_HPlan``: neither
has a ``CASE`` arm for ``Trail`` that reads/writes anything beyond the
generic ``(action, obj, extra)`` triple (the *only* place ``Trail``
appears in ``R_HPlan`` at all is a moderator-only, no-extra-data side
effect -- ``{$IFDEF Moderator} Trail,ASpy: cover[sldr]:= Spy; {$ENDIF}``
-- the same stealth-bonus bookkeeping [4.33]'s "reduced chance of being
noticed" describes, not order-payload parsing). ``obj`` is the target
character id -- confirmed via ``RUMORS.PAS``'s ``Set_Intel`` comparing
``lobjects[_rphase]`` against attacker/defender-leader character ids in
a `Succ_Trail`-triggered spy bonus, and ``SAY.PAS``'s ``_LANoTr``
rejection message ("could not Trail [ because > armies could not follow
along...") referencing the target via the same character placeholder
Pursue's own messages use.

**Zero real Trail phases exist in any of the 10 sample ``AK3__T*.K1``
files** (re-verified fresh) -- same situation as Fire, Trade, Challenge,
Pursue, Use_MI, ASpy, and Defend. This module's correctness rests on
the rulebook (English and Italian) and the Pascal source alone.

**Decode-only, itself** -- this module only turns a raw ``PlanPhase``
into a ``TrailRequest``. **Stale as of Phase 70** -- this paragraph
used to say resolving whether a Trail catches its target and what
intelligence it reveals needed a turn-simulation engine this project
didn't have; ``turn/trail_execution.py`` is that engine (the shared
Spy Table catch-up roll also used by Pursue, all six named
intelligence fields [3.17] lists, Spy Super Sleuth/Expanded Spying/
Blackmail's own wiring) and has existed for a long time.

Not to be confused with **Succ_Trail** (``ActionCode.SUCC_TRAIL``),
which this project deliberately does *not* decode at all -- see
``turn/plan_dispatch.py``'s module docstring for why.
"""

from __future__ import annotations

from dataclasses import dataclass

from ak_engine.models.plan import PlanPhase


@dataclass(slots=True)
class TrailRequest:
    target_character_id: int  # phase.obj
    unconfirmed_extra0: int  # phase.extra[0] -- no CASE-specific use in R_HPlan/W_HPlan, no real data either


def decode_trail_phase(phase: PlanPhase) -> TrailRequest:
    """Decode a Trail PlanPhase's target character."""

    extra0 = phase.extra[0] if phase.extra else 0
    return TrailRequest(target_character_id=phase.obj, unconfirmed_extra0=extra0)
