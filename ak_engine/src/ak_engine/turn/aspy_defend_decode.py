"""Decoding ASpy/Defend PlanPhases (rulebook [3.14] Spy Province, [3.15] Defend).

Both are bare `(action, obj, extra)` triples at the wire level -- neither
has a dedicated ``CASE`` branch in ``HostAK/TP/DEF2.PAS``'s
``R_HPlan``/``W_HPlan`` (confirmed by reading the full branch lists:
only Search/Challenge/Pursue, Cast, Use_MI, Trade, Hire, and
Disband/Leave/Pick_Up/Recruit have one). That alone would put them in
the same bucket as Wait/No_Action/Move_Abort, but **unlike those three,
``obj`` is confirmed to be a real, engine-consulted province reference,
not dead data**:

- **ASpy**: ``HostAK/TP/RUMORS.PAS``'s ``Set_Intel`` (the intel-report
  generator) directly reads it -- ``ELSE IF lobjects[_rphase] = _prov
  THEN CASE lactions[_rphase] OF ASpy: Add_Spy(1); ...`` -- comparing
  the phase's ``obj`` against the province currently being processed
  for intelligence purposes.
- **Defend**: ``HostAK/TP/REPORTS.PAS``'s ``Set_Defend`` (the
  missed-turn-deadline auto-fill, previously found while researching
  Wait/No_Action -- rulebook: "the computer ordered Defend actions for
  your generals") explicitly *writes* it: ``lobjects[0]:= lx[l2]*XMULT
  +ly[l2]`` -- the general's own current province, in the host's
  internal ``x*XMULT+y`` coordinate arithmetic. **Phase 134 addendum**:
  ``Set_Defend`` only assigns Defend at all when the leader commands an
  army (``AA_Led(l2) > 0``); see ``turn/missed_deadline.py`` for the
  real implementation, which needs no numeric decode of this field at
  all (``turn/defend_execution.py`` already computes coverage from the
  leader's own live ``HexCoord``, not from a dispatched phase's ``obj``).

Rulebook [3.14] (quoted in full, ``RULES.AK`` ~line 500): "A character
Spying on a province will report on its owner, owners of adjacent
provinces, taxation of the province, army types recruitable there, and
whether the province is the capital province of the Kingdom... A
character may only Spy on a province he is actually in." The official
move-sheet example (``AKMOVES.TXT``) shows ``(SP)_304____`` /
``(_Burgundy__)`` -- a province number, same format as Move/Explore.
``actab[ASpy] = 'SP'``, matching the rulebook's own abbreviation
directly (no Trade/Challenge-style naming mismatch here).

Rulebook [3.15] (quoted in full): "A general ordered to Defend will be
able to react to enemy invasions of adjacent provinces for the rest of
the turn... You can order your general to Defend an area of 7
provinces, centered on any province up to two provinces away." Per
``ADDEND.AK``'s errata: "When giving a 'Defend' order, list only one
province. The general will defend any province that is adjacent to
both the named province and the province the leader is currently
located in." ``actab[Defend] = 'DE'``, again matching directly. A
detail present **only** in the Italian rulebook, not `RULES.AK`: a
Defend order always resolves *last* in its phase (the general must be
able to react to every other action first) -- not modeled by this
decode-only module, noted here for whoever eventually builds phase
ordering/initiative.

**``target_province`` is kept as a raw, unconverted int** -- this
project's ``turn/hex_numbering.py`` decodes LMOVE's target through an
*empirically inferred* row-major scheme (its own docstring: "not a
sourced rule"), and nothing in the available Pascal source shows
whether a player-typed province number for ASpy/Defend uses that same
numbering space or maps directly onto ``Set_Defend``'s internal
``x*XMULT+y`` arithmetic (``XMULT``'s value isn't in the available
source either). Converting here would stack one unconfirmed mapping on
top of another; left raw and flagged, matching this project's
established caution around fields it can't fully source.

``extra``/``tl``: no ``CASE``-specific use for either action anywhere in
``R_HPlan``/``W_HPlan``, and ``Set_Defend`` never writes ``lextra[0]``
at all -- kept as an unconfirmed raw field, same convention as
Search/Recruit's own always-present-but-unused ``extra[0]``.

**Zero real ASpy or Defend phases exist in any of the 10 sample
``AK3__T*.K1`` files** (re-verified fresh via this project's own parser,
walking every phase including nested plans) -- same situation as Fire,
Trade, Challenge, Pursue, and Use_MI. This module's correctness rests
entirely on the Pascal source, the rulebook, its addendum, and the
official ``AKMOVES.TXT`` example sheet, with no real-data cross-check
possible.

**Decode-only, itself** -- this module only turns a raw ``PlanPhase``
into a ``SpyProvinceRequest``/``DefendRequest``; it does not resolve
what a successful Spy report reveals or give a leader reactive Defend
behavior. **Stale as of Phase 134 (Defend) and later phases (ASpy)** --
this paragraph used to say that real-world logic needed game-state
machinery this project didn't have anywhere; both exist now:
``turn/aspy_execution.py execute_aspy()`` is the real Spy Province
report generator (owner/adjacent-owners/taxation/recruitable-types/
capital-status, plus several Advanced-Ability-gated enrichments), and
``turn/defend_execution.py`` is the real reactive-coverage-area/
battle-triggering implementation the Phase 134 addendum above already
points to. Only the *decode* step here stayed this narrow -- both
downstream modules resolve their own province/leader references from
live ``GameState``, not from the raw ``obj``/``extra`` values above.
"""

from __future__ import annotations

from dataclasses import dataclass

from ak_engine.models.plan import PlanPhase
from ak_engine.turn.decode_utils import phase_extra0


@dataclass(slots=True)
class SpyProvinceRequest:
    target_province: int  # phase.obj -- must equal the caster's own province, rulebook [3.14]
    unconfirmed_extra0: int  # phase.extra[0] -- no CASE-specific use, no real data either


@dataclass(slots=True)
class DefendRequest:
    target_province: int  # phase.obj -- center of the "defend area", rulebook [3.15]/ADDEND.AK
    unconfirmed_extra0: int  # phase.extra[0] -- never written by Set_Defend, no real data either


def decode_aspy_phase(phase: PlanPhase) -> SpyProvinceRequest:
    """Decode an ASpy (Spy Province) PlanPhase's target province."""

    return SpyProvinceRequest(target_province=phase.obj, unconfirmed_extra0=phase_extra0(phase))


def decode_defend_phase(phase: PlanPhase) -> DefendRequest:
    """Decode a Defend PlanPhase's target province."""

    return DefendRequest(target_province=phase.obj, unconfirmed_extra0=phase_extra0(phase))
