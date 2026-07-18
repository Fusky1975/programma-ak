"""Imperfect-information alignment/temper estimation -- Phase 136.

``HostAK/TP/REPORTS.PAS``'s ``Align_Est``/``Temper_Est`` (~lines 43-58),
quoted in full (the Pascal ``ln < 256`` character-vs-monster branch and
the outer ``2880+``/``2896+`` prose-dispatch-code offsets are covered
in this module's own docstring notes below, not reproduced in the
quoted formula itself):

    FUNCTION Align_Est(ln,agent: integer): integer;
    BEGIN
      IF ((titchar[Psychic_Mage] = agent) or (Has_SA(agent,Detect_Align)))
        THEN Align_Est:= ord(Agent_Align(ln,bali))
        ELSE Align_Est:= Max(0,Min(ord(Special),
          ord(Agent_Align(ln,bali))+(ln and 1) - (agent and 1)));
     END;

    FUNCTION Temper_Est(ln,agent: integer): integer;
    BEGIN
      IF titchar[Psychic_Mage] = agent THEN Temper_Est:= ord(btemp)
        ELSE Temper_Est:= Max(0,Min(ord(Berserk),
          ord(btemp)+(ln and 1) - (bornx[agent] and 1)));
     END;

A character trying to size up another character's alignment or
temperament doesn't automatically see the true value -- unless the
observer has *perfect* detection (holds the Psychic Mage office, or --
for alignment only -- has the ``Detect_Align`` advanced ability, almost
certainly this project's own ``AdvancedAbility.KNOW_ALIGNMENT_TALENT``,
the "Know Alignment" Talent, given the semantic match; no literal
Pascal-identifier confirmation exists since ``Detect_Align`` is a
constant name, not free text) -- the estimate is nudged by exactly ±1
enum-ordinal step, clamped to the enum's own real range
(``Alignment.SPECIAL`` / ``Temper.BERSERK`` are each enum's own highest
ordinal, confirming the clamp bounds directly).

**Phase 162 fixes a genuine ordinal-order bug here**: the alignment
"ordinal" this function nudges must be the real Pascal ``outlook``
sequence (``Heavenly=0, Good=1, Druidic=2, Worldly=3, ...`` --
``models/alignment.py``'s own ``ALIGNMENT_ORDINAL``/
``ALIGNMENT_BY_ORDINAL``, added the same phase), not
``models/alignment.py Alignment``'s own Python declaration order
(chosen, Phase 4/80, to match display strings, not Pascal ordinals).
This module used ``tuple(Alignment)`` -- the wrong, declaration-order
sequence -- from Phase 136 until this fix; found while designing
Hire's required-pay formula, which needed the *real* ordinal distance
for an unrelated reason and exposed the mismatch by cross-checking a
real rulebook data point (a Good King generally cannot hire a Pagan
Hero -- true only at real ordinal distance 3, not at the
declaration-order distance for the same pair).

**The noise source is each id's own parity (odd/even), not a random
roll** -- ``(ln and 1) - (agent and 1)``: the nudge is ``+1`` if the
target's id is odd and the agent's is even, ``-1`` if reversed, ``0``
if both share parity. Deterministic given both ids, not RNG-driven --
unusual among this project's other "roll a die" mechanics, but that's
exactly what the Pascal source computes, not a design choice made
here.

**Temper's second parity term is the agent's own birth
x-coordinate, not the agent's id** -- ``bornx[agent] and 1``, a
different, more specific value ``Align_Est`` doesn't use at all.
``estimate_temper()`` below still takes it as an explicit,
caller-supplied parameter rather than reading it internally, so this
module stays free of a ``GameState`` dependency -- but the value
itself is no longer unsourced: ``LeaderState.birth_x`` (Phase 139)
models exactly this field, and ``turn/aspy_execution.py``'s own real
caller already passes ``leader.birth_x or 0`` (see that module's own
Phase 139 wiring). **Phase 160 corrects this docstring's own earlier,
now-stale claim** that this project had no field for a leader's birth
coordinate at all -- left uncorrected, a future reader would trust the
doc comment over the actual code, the same self-correction policy
Phase 55/153/159 already established elsewhere in this project.

**``ln < 256`` (character) vs. ``ln >= 256`` (a feature's guardian
monster, ``ord(fmonst[ln-256])``) branch, and the ``2880+``/``2896+``
prose-dispatch-code offsets, are deliberately not modeled here**: this
module only covers the character-vs-character case (the realistic
ASpy-adjacent intelligence use), and exposes the real estimated
``Alignment``/``Temper`` enum member directly rather than a
`FD`-style numeric dispatch code -- the target ``.X2`` prose file
those codes point into isn't part of the available Pascal archive (the
same "external `.X2` content, not `.PAS` source" gap already declared
for ``ioname.x2``/``saname.x2`` elsewhere), so this project has no
exact display string to reconstruct for a monster's own estimated
alignment/temper announcement, and no separate real formula (beyond
citing ``Agent_Align``'s unresolvable existence, see below) for
translating a monster's own species into an implied alignment.

**``Agent_Align(ln,bali)`` itself has no available Pascal source**
(declared, presumably, in the same missing ``mboth``/``defines``
compiled-only units already responsible for ``spabord``'s own lost
data, Phase 131) -- but for the character case, ``bali:= ln`` is
assigned immediately before the call, strongly suggesting
``Agent_Align(ln,ln)`` for a character simply returns that leader's own
real alignment (there is no plausible alternative reading of passing a
value identical to the first argument as a second lookup key for a
same-source value). This module's own callers therefore supply
``true_alignment``/``true_temper`` directly, keeping this module
``GameState``-free -- **updated as of Phase 160**: this docstring
previously claimed neither ``LeaderState.alignment`` nor
``LeaderState.temper`` existed to source them from, which was only
half true even then. ``LeaderState.temper`` is real (Phase 139), and
``turn/aspy_execution.py``'s own real caller sources ``true_temper``
straight from ``spotted.temper``. **Phase 212 corrects a second stale
claim this docstring carried past its own sell-by date**:
``LeaderState.alignment`` (Phase 162, two phases after this note was
first written) is now a real, stored per-leader field -- not only
``KingdomState.alignment``, kingdom-level, as claimed here through
Phase 211. ``turn/aspy_execution.py``'s own ``execute_aspy()`` still
passes the spotted leader's own *kingdom* alignment into
``estimate_alignment()``, not ``LeaderState.alignment`` directly --
now a real, sourced-but-unswitched simplification worth revisiting in
a future ASpy-focused phase, not the "no field exists at all" gap this
docstring claimed before Phase 160, nor an oversight introduced here.
"""

from __future__ import annotations

from ak_engine.models.alignment import ALIGNMENT_BY_ORDINAL, ALIGNMENT_ORDINAL, Alignment
from ak_engine.models.temper import Temper

_TEMPER_ORDER: tuple[Temper, ...] = tuple(Temper)


def _nudge(true_ordinal: int, target_parity: int, agent_parity: int, max_ordinal: int) -> int:
    nudged = true_ordinal + (target_parity & 1) - (agent_parity & 1)
    return max(0, min(max_ordinal, nudged))


def estimate_alignment(
    true_alignment: Alignment,
    target_id: int,
    agent_id: int,
    *,
    perfect: bool,
) -> Alignment:
    """Rulebook-unstated, ``REPORTS.PAS Align_Est``-sourced imperfect-information estimate.

    ``perfect`` is caller-supplied: true when the observing agent holds
    the Psychic Mage office or the ``Detect_Align``/"Know Alignment"
    Talent advanced ability -- neither office-holding nor per-leader
    advanced-ability possession is tracked anywhere in this project's
    ``GameState`` yet, so the caller must determine it. See module
    docstring for the ±1-ordinal noise formula and its real clamp
    bound (``Alignment.SPECIAL``, the enum's own highest ordinal).
    """

    if perfect:
        return true_alignment
    max_ordinal = len(ALIGNMENT_BY_ORDINAL) - 1
    true_ordinal = ALIGNMENT_ORDINAL[true_alignment]
    nudged = _nudge(true_ordinal, target_id, agent_id, max_ordinal)
    return ALIGNMENT_BY_ORDINAL[nudged]


def estimate_temper(
    true_temper: Temper,
    target_id: int,
    agent_birth_x: int,
    *,
    perfect: bool,
) -> Temper:
    """Rulebook-unstated, ``REPORTS.PAS Temper_Est``-sourced imperfect-information estimate.

    ``agent_birth_x`` is the observing agent's own birth x-coordinate
    (``bornx[agent]`` in the Pascal source) -- a real, distinct
    parity source from ``estimate_alignment()``'s own agent-id parity,
    not a mistake; see module docstring for why this project has no
    field to source it from automatically. ``perfect`` is caller-supplied,
    true only for a Psychic Mage office-holding agent (unlike alignment,
    the Pascal source gives temper detection no advanced-ability
    bypass at all).
    """

    if perfect:
        return true_temper
    max_ordinal = len(_TEMPER_ORDER) - 1
    nudged = _nudge(true_temper.value, target_id, agent_birth_x, max_ordinal)
    return _TEMPER_ORDER[nudged]
