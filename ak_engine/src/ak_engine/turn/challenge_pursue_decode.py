"""Decoding Challenge/Pursue PlanPhases (rulebook [3.12] Encounter Character, [3.16] Pursue).

**Naming mismatch, confirmed in the Pascal source**: ``ActionCode.CHALLENGE``
(``CTBOTH.PAS`` ordinal 11) is the internal name for the rulebook's
**Encounter Character (EN)** order -- its ``actab`` abbreviation is
``'EN'``, not ``'CH'``, matching [3.12] exactly, and the official
move-sheet example (``AKMOVES.TXT``) labels it ``(EN)_88_____``. Same
naming-mismatch situation as ``ActionCode.TRADE`` being the internal
name for the rulebook's Give order (``turn/trade_decode.py``). Pursue
has no such mismatch: ``ActionCode.PURSUE`` (ordinal 16, ``actab``
``'PU'``) is the rulebook's own [3.16] Pursue, directly.

Both share **exactly the same wire format as Search** (rulebook [3.3],
already decoded in ``turn/search_decode.py``): ``HostAK/TP/DEF2.PAS``
handles all three together --

```pascal
{ write }  Search,Challenge,Pursue: W_List(pexrec[m].firstbyte,Tac_Bytes);
{ read }   Challenge,Pursue: BEGIN
             R_List(pexrec[m].firstbyte,Tac_Bytes,abbrev,sldr,-(lobjects[m]+1));
             pexrec[m].ertype:= Tac_Bytes;
            END;
```

Same ``-1``-terminated **tactic list** (``Maneuver`` ordinals, only
``CAST``/``USE_MI``/``GIVE`` take a sub-object) -- reuses
``turn/search_decode.py``'s ``SearchTactic`` for that shape rather than
redefining an identical dataclass.

**The one real difference from Search: what ``obj`` means.** Search's
``obj`` is a target *feature* id. Challenge/Pursue's ``obj`` is a target
**character** id -- confirmed by the rulebook ([3.12]: "Encounter
*another character* in the same province"; [3.16]: "chase after
*another character*"), the move-sheet example (``(EN)_88_____`` /
``(_Lancelot__)`` -- 88 is annotated with a character name), and
structurally in the Pascal itself: ``R_List`` is called with
``sfeat = -(lobjects[m]+1)`` for Challenge/Pursue -- always negative,
regardless of ``obj``'s own sign -- deliberately routing around
``R_List``'s Search-specific "``sfeat >= 0``" feature-id special case
(a Give-tactic-with-item-0 -> Scout quirk that only makes sense for a
*feature* target). This project models that distinction as a field
name (``target_character_id``, not ``feature_id``), not a literal
negative-number encoding -- the sign trick is purely an internal Pascal
disambiguation between two ``R_List`` call sites, not something this
project's own ``PlanPhase.obj`` (already a plain non-negative int by
the time the parser hands it over) needs to reproduce.

Rulebook [3.12] (quoted in full, ``RULES.AK`` ~line 479): "The character
attempts to Encounter another character in the same province, to talk
to him, steal from him or engage in personal combat... Heroes who don't
lead armies can always be Encountered by other Heroes, but evade
encounters from Kings 50% of the time. Kings only accept a non-peaceful
encounter if both King and challenger attempt to Encounter each other
in the same province in the same phase. Heroes who lead armies also do
not accept encounters." None of this acceptance logic is modeled here
-- decode-only, same as every other action-with-no-resolver in this
project.

Rulebook [3.16] (quoted in full, ``RULES.AK`` ~line 580): "A character
can be ordered to chase after another character for the rest of the
turn... If both characters lead armies, the pursuing character will
attempt to run him down and defeat him in battle. If the Pursuing
character does not lead any armies, then an encounter plan must be
specified... If the Pursuing character leads an army and the pursued
character doesn't, or visa versa, the Pursue order is ignored." Success
is governed by the Spy Table [4.33] (base chance by Spy skill level,
``*2`` if the target leads an army, ``/`` distance in provinces, `100%`
if pursuer and target share a Kingdom) -- none of this is modeled here
either. A documented but unmodeled nuance: targeting **one's own**
character id turns a Pursue order into a standing "Patrol" (auto-
intercept nearby armyless enemy characters, rulebook [3.16] "Characters
on Patrol") -- this module doesn't special-case that; it decodes
whatever character id ``obj`` contains, self or not.

**Not to be confused with ``turn/pursuit.py``**, a completely separate,
already-implemented mechanic: the automatic chase-down of a clean-swept
loser's retreating units immediately after a battle (rulebook [7.3]),
driven by unit speed, with no player order and no character-id target.
Confirmed no Pascal-source overlap between the two: the only Pascal
hits for "Pursue" are in the plan encode/decode layer
(``CTBOTH.PAS``/``DEF2.PAS``) and narrative templates (``SAY.PAS``) --
no battle-resolution engine source exists in the available Pascal
archive for either mechanic, which is exactly why ``turn/pursuit.py``
was already built from rulebook text alone. The two modules should stay
separate; this one doesn't touch ``turn/pursuit.py``.

**Zero real Challenge or Pursue phases exist in any of the 10 sample
``AK3__T*.K1`` files** (confirmed twice: once via a raw-text scan, once
via this project's own parser walking every phase including nested
plans) -- so unlike Search's tactic-list decode (validated against 12
real examples), this module's correctness rests on the Pascal source
and rulebook alone, with no real-data cross-check possible. Same
situation as Fire, Trade, and Use_MI.

**Decode-only**: resolving whether an Encounter/Pursue is even accepted
(the King/Hero acceptance rules above), let alone what happens in the
resulting personal combat, needs the same non-army Encounter/combat
resolver ``turn/search_decode.py`` already flags as missing.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ak_engine.models.plan import PlanPhase
from ak_engine.turn.search_decode import SearchTactic, decode_tactic_tokens


@dataclass(slots=True)
class ChallengeRequest:
    target_character_id: int  # phase.obj
    unconfirmed_extra0: int  # phase.extra[0] ("tl") -- no CASE-specific use in R_HPlan/W_HPlan, no real data either
    tactics: list[SearchTactic] = field(default_factory=list)


@dataclass(slots=True)
class PursueRequest:
    target_character_id: int  # phase.obj
    unconfirmed_extra0: int  # phase.extra[0] ("tl") -- no CASE-specific use in R_HPlan/W_HPlan, no real data either
    tactics: list[SearchTactic] = field(default_factory=list)


def _decode_tactic_list(phase: PlanPhase) -> tuple[int, list[SearchTactic]]:
    """Shared Search/Challenge/Pursue tactic-list decode (see module
    docstring) -- delegates to ``turn/search_decode.py decode_tactic_
    tokens()`` (Phase 659) rather than keeping its own separate copy, a
    copy that had drifted: it never special-cased ``SAY`` the way Search's
    own walk (Phase 618) does, which would have misread a real ``SAY``
    tactic's free-text argument as a plain sub-object int. No real
    Challenge/Pursue sample has ever exercised this (see module
    docstring's own "zero real phases" note), so this was a latent,
    never-triggered bug, not a behavior change for any real data.
    """

    values = list(phase.extra)
    extra0 = values[0] if values else 0
    tactics = decode_tactic_tokens(values[1:])

    return extra0, tactics


def decode_challenge_phase(phase: PlanPhase) -> ChallengeRequest:
    """Decode a Challenge (Encounter Character) PlanPhase's target and Encounter Plan tactics."""

    extra0, tactics = _decode_tactic_list(phase)
    return ChallengeRequest(target_character_id=phase.obj, unconfirmed_extra0=extra0, tactics=tactics)


def decode_pursue_phase(phase: PlanPhase) -> PursueRequest:
    """Decode a Pursue PlanPhase's target and Encounter Plan tactics."""

    extra0, tactics = _decode_tactic_list(phase)
    return PursueRequest(target_character_id=phase.obj, unconfirmed_extra0=extra0, tactics=tactics)
