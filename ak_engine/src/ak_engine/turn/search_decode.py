"""Decoding a Search PlanPhase (rulebook [3.3] Search Feature).

Search is structurally unlike Explore ([3.2], ``turn/exploration.py``):
Explore is an untargeted, deterministic percentage roll over the
mover's *own* province, revealing that a feature exists. Search targets
one *already-known* feature by number (possibly in a province the
searcher doesn't own, or hasn't even Explored, if a rumor gave up its
number -- rulebook: "A character may Search a feature... if they know
the location and feature number") and immediately triggers a personal
**Encounter** against that feature's guardian monster (rulebook [5.0]),
resolved via a player-supplied **Encounter Plan**: an ordered list of
combat tactics (Cast, Use Item, Talk, Say, Give, Fulfill, Steal, Shoot,
Melee, Flee, Beg, Scout -- [5.1]-[5.8]).

Sourced from ``HostAK/TP/DEF2.PAS``'s ``R_HPlan``/``W_HPlan``:

- ``obj`` (``lobjects[m]``) is the target feature's number.
- ``tl`` (this project's ``PlanPhase.extra[0]``) is read but has **no**
  ``CASE``-specific use anywhere in ``R_HPlan``/``W_HPlan`` for Search
  (unlike Hire's gold offer) -- and every one of the 12 real Search
  phases across the 10 sample ``AK3__T*.K1`` files has it as ``0``. Kept
  as a raw, unconfirmed field, same convention as Recruit's own
  always-``0`` ``extra[0]`` (see ``turn/recruit_decode.py``).
- The remainder of ``extra`` is a ``-1``-terminated **tactic list**
  (``R_List(..., Tac_Bytes, ...)``): each entry is a ``Maneuver``
  ordinal, and ``CAST``, ``USE_MI``, and ``GIVE`` (``models.enums
  TACTICS_WITH_SUB_OBJECT``) are followed by a sub-object (a spell id,
  magic-item id, or gift-item id respectively -- ``CTBOTH.PAS``'s
  ``maneuver`` enum / ``W_List``'s ``Tac_Bytes`` mode).

- **Phase 618**: ``SAY`` (the real Pascal ``'SA'`` tactic) is followed
  by something else entirely -- free text on its own line(s),
  terminated by a blank line (``DEF2.PAS W_List``'s own ``CSay`` branch:
  ``WrCr; WrS(tacptr^.sayeth^); WrCr; WrCr`` -- a forced newline, the
  text, then a real blank-line terminator; ``R_List``'s own ``CSay``
  branch reads it back the same way, ``REPEAT READLN(tmp) ... UNTIL
  tmp=''``). Confirmed directly by the user: the text sits on its own
  line, unquoted -- rulebook examples like ``"SA-y the character
  number... e.g., 'SA Tell me about character 1.'"`` (``Special
  Features.md`` section 5.4) and the user's own example plan (``CA-FI,
  SA "Take that!", FI, ME, ME``, used to answer a riddle or reply to a
  guardian, not only to feed the 5 Oracles/Recharge/Grant Wish/Gamble
  their own numeric argument) describe the *mechanic*, not the literal
  on-disk quoting. Since this doesn't fit a plain integer, ``parser/
  k1_moves.py`` recovers it directly from the move file's own raw lines
  (not from the generic flat-integer tokenizer every other action type
  uses) and stores it as the one ``str`` element ``PlanPhase.extra`` is
  ever allowed to contain, positioned exactly where ``SAY``'s own
  ordinal appears -- see that module's own Phase 618 addendum for the
  full recovery algorithm. No real sample ``AK3__T*.K1`` file contains
  an actual ``SAY`` tactic (confirmed below), so this is built from the
  Pascal source's own logic plus the user's direct confirmation, not a
  real byte-level example.

Validated against real data: all 12 real Search phases across the 10
sample files decode to a clean, fully-consumed tactic list (no leftover
or misaligned tokens), using only ``Maneuver`` ordinals ``CAST``(0),
``STEAL``(7), ``SHOOT``(8), ``MELEE``(9), ``FLEE``(10), and ``SCOUT``(13)
-- every real Search order ends in ``Melee`` and/or ``Scout``.

**This module only decodes the request -- it does not resolve a Search's
outcome.** **Stale as of the many phases that built ``turn/search_
execution.py``** -- this paragraph used to say resolving a Search's own
outcome needed a personal, non-army Encounter/combat resolver this
project didn't have yet; ``turn/search_execution.py`` (a large module,
``_apply_scout()`` and its many siblings) is exactly that resolver and
has existed for a long time, handling combat, Feature->Power, treasure/
monster content, and rumor generation alike. Only the *decode* step
here stayed this narrow. A Cast/Use_MI tactic's own ``sub_object`` is
still kept as a raw int at this layer -- that half of the claim remains
accurate as a description of the decode/execute split this project uses
throughout (e.g. ``turn/cast_decode.py`` resolves the same kind of value
via ``spell_from_int()`` at ITS own decode layer, but this shared tactic
walk deliberately doesn't, leaving that to whichever execution module
consumes a given ``SearchTactic``) -- but "this project has no decoded
spell-id or magic-item-id table yet" is false: ``models/enums.py Spell``/
``spell_from_int()`` and ``models/item.py``/``GameState.items`` have
both existed for a long time.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ak_engine.models.enums import TACTICS_WITH_SUB_OBJECT, Maneuver, maneuver_from_int
from ak_engine.models.plan import PlanPhase


@dataclass(slots=True)
class SearchTactic:
    maneuver: Maneuver | int
    sub_object: int | None = None  # spell/item id -- only set for CAST/USE_MI/GIVE
    # Phase 618: SAY's own free-text argument (recovered from the raw
    # move file's own lines by parser/k1_moves.py, not a plain int) --
    # only set for SAY. A separate field rather than overloading
    # sub_object with a different type/meaning, per this module's own
    # docstring addendum above.
    say_text: str | None = None


@dataclass(slots=True)
class SearchRequest:
    feature_id: int  # phase.obj
    unconfirmed_extra0: int  # phase.extra[0] ("tl") -- always 0 in every real sample
    tactics: list[SearchTactic] = field(default_factory=list)


def decode_tactic_tokens(tokens: list[int | str]) -> list[SearchTactic]:
    """Decode a raw, ``-1``-terminated tactic-token list (already stripped
    of any leading ``tl``/``extra0`` slot) into ``SearchTactic``s -- the
    shared walk Search/Challenge/Pursue's own ``PlanPhase.extra`` and the
    Special Encounter Plan's own ``PlanSegment.sp`` (``turn/sep_decode.py``,
    Phase 659) all need identically, extracted here (Phase 659) rather
    than kept as three separate copies.
    """

    if tokens and tokens[-1] == -1:
        tokens = tokens[:-1]

    tactics: list[SearchTactic] = []
    i = 0
    while i < len(tokens):
        maneuver = maneuver_from_int(tokens[i])
        i += 1
        sub_object = None
        say_text = None
        if maneuver is Maneuver.SAY and i < len(tokens):
            say_text = str(tokens[i])
            i += 1
        elif maneuver in TACTICS_WITH_SUB_OBJECT and i < len(tokens):
            sub_object = tokens[i]
            i += 1
        tactics.append(SearchTactic(maneuver=maneuver, sub_object=sub_object, say_text=say_text))

    return tactics


def decode_search_phase(phase: PlanPhase) -> SearchRequest:
    """Decode a Search PlanPhase's target feature and Encounter Plan tactics."""

    values = list(phase.extra)
    extra0 = values[0] if values else 0
    tactics = decode_tactic_tokens(values[1:])

    return SearchRequest(feature_id=phase.obj, unconfirmed_extra0=extra0, tactics=tactics)
