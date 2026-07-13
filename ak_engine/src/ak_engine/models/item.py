"""Magic-item instance / ownership registry -- Phase 140.

Sourced from ``HostAK/TP/RUMORS.PAS``'s ``Add_Tr`` procedure (~line 646),
found while closing Trade/Give's own "no item-ownership registry exists"
gap (``turn/trade_execution.py``, Phase 133) and cross-checked against
every other real reference to the same three arrays across the archive:

```pascal
PROCEDURE Add_Tr(tr: treasure; tow,tch: integer);
VAR trd,trl: integer;
BEGIN
  trav:= Max(maxfeatures+1,ntreasures);
  IF ntreasures = maxfeatures+1 THEN trl:= maxfeatures ELSE trl:= ntreasures;
  FOR trd:= 0 TO trl-1 DO IF trowner[trd] = noleader THEN IF trd <> maxfeatures THEN
    trav:= trd;
  trowner[trav]:= tow;
  trcharges[trav]:= tch and 255;
  treaslist[trav]:= tr;
  ...
  IF trav >= ntreasures THEN ntreasures:= trav+1;
 END;
```

Every physical magic item in play is one slot across three parallel
global arrays: ``treaslist`` (which ``Treasure`` type this instance is),
``trowner`` (which leader currently holds it, or ``noleader``), and
``trcharges`` (charges/uses remaining -- meaningful for wands, per
``models/treasure.py``'s own ``USE_MI_TARGET_CATEGORIES``). This is not
a guess: ``DEF2.PAS``'s ``R_HPlan``/``W_HPlan`` index straight into
``treaslist[lobjects[m]]`` to resolve a Use_MI phase's item (see
``turn/use_mi_decode.py``'s own docstring, which already named this
exact triple without being able to build it -- this module is that
follow-up), and ``REPORTS.PAS``'s per-leader inventory listing
(``FOR tn:= 0 TO ntreasures-1 DO IF trowner[tn] = tro THEN ...``, ~line
540) prints exactly ``"<ItemName> (#<tn>): ..."`` next to a character's
own turn report -- the same instance id a Give order's item field refers
to (rulebook [3.18]).

This is a physical item *instance*, distinct from ``models/treasure.py
Treasure`` (the type catalog, Phase 77) the same way
``models/game_state.py ArmyState`` is distinct from
``models/army_type.py ArmyType``.

**Scope boundary, deliberately not modeled**: the Pascal arrays are
sized ``0..maxfeatures`` for monster/feature-guarded treasure (encoded
via a ``feature_id + 256`` owner convention, e.g. ``REPORTS.PAS``
~line 2040's ``trowner[fn] <> fn+256``) plus ``maxfeatures+1..`` for
freely-held items allocated by ``Add_Tr``. ``maxfeatures`` is one of
this project's already-confirmed missing compiled-only constants (same
category as ``spabord``, Phase 131), and -- independently -- this
project has no monster/feature loot-generation pipeline at all (see
``turn/use_mi_decode.py``'s own docstring: ``Add_Tr``'s only call site
in the available archive is a narrow Valhalla-visitor special case, not
a general world-gen loop). So ``ItemInstance`` below models only the
leader-held half of the real structure -- ``owner_leader_id`` is a
leader id or ``None`` (Pascal ``noleader``), never a feature-guarded
encoding. ``GameState.add_item()`` also allocates ids monotonically
(``new_item_id()``, mirroring ``new_army_id()``) rather than
replicating ``Add_Tr``'s own free-slot-reuse scan against the missing
``maxfeatures`` boundary -- the same simplification this project already
made for army/leader ids instead of reusing Pascal's own slot recycling.

**Structure and creation primitive are genuinely sourced even though
automatic population is not** -- the same split this project already
accepted for the mercenary-army pool (Phase 16) and independent-hero
pool (Phase 17): a caller with real item-creation knowledge (a future
loot table, a Valhalla-visit outcome, a scenario-scripted grant) has a
faithful primitive (``GameState.add_item()``) to call, even though
nothing in this project yet calls it automatically during world
generation.
"""

from __future__ import annotations

from dataclasses import dataclass

from ak_engine.models.treasure import Treasure


@dataclass(slots=True)
class ItemInstance:
    item_id: int  # Pascal: trav -- the index into treaslist/trowner/trcharges
    treasure: Treasure  # Pascal: treaslist[item_id]
    owner_leader_id: int | None  # Pascal: trowner[item_id]; None = noleader (unowned)
    charges: int = 0  # Pascal: trcharges[item_id] (tch and 255 -- charges/uses remaining)
