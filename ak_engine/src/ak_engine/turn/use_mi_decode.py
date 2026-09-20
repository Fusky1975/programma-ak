"""Decoding a Use Magic Item PlanPhase (rulebook [3.11] Use Magic Item).

Rulebook [3.11] (quoted in full): "The character Uses a Magic Item to
cast a spell, specifying the ID number of the magic item. A spell cast
from a magic item is automatically successful." [3.10] warns the two
are easy to confuse: "Be careful that you don't use the Cast Spell
command to use a magic item." Not to be confused with
``Maneuver.USE_MI``, the *encounter-plan* tactic (rulebook [5.1], "US-#"
inside a Search/Challenge tactic list, already decoded by
``turn/search_decode.py``) -- a different Pascal reading path with no
top-level ``ActionCode`` of its own.

Sourced from ``HostAK/TP/CTBOTH.PAS`` (``action`` enum: ``Use_MI`` =
ordinal 10) and ``HostAK/TP/DEF2.PAS``'s ``R_HPlan``/``W_HPlan``:

```pascal
Use_MI: BEGIN
      trt:= treaslist[lobjects[m]];
      IF ((trt >= wcp) and (trt <= pic)) THEN
        Read_More(spell(ord(trt)-ord(wcp)));
 END;
```

**The critical structural difference from Cast**: for Cast, ``obj`` *is
directly* a ``Spell`` ordinal. For Use_MI, ``obj`` (``lobjects[m]``) is
instead a **global item-instance id** -- an index (``trav`` in the
Pascal source) into three parallel global arrays (``treaslist``: which
``treasure`` *type* this specific item is; ``trowner``: which character
holds it; ``trcharges``: charges remaining) that record every physical
magic item currently in play across the whole game, populated by
``RUMORS.PAS``'s ``Add_Tr`` as items are created. This is the same
number a character's own turn report prints next to an item's name
(``REPORTS.PAS``: ``"<ItemName> (#<tn>): ... (N charges)"``) and the
same number a Give order's item field refers to (rulebook [3.18]).

**This means a ``PlanPhase.obj`` for Use_MI cannot be resolved to "what
item is this" by decoding alone** -- unlike Cast's ``obj``, which is
self-describing. Knowing what instance #31 *is* requires knowing that
specific game's item-creation history (``Add_Tr`` calls over the
game's lifetime), and the only call site for ``Add_Tr`` present in the
available Pascal source is a narrow Valhalla-visitor special case
(``RUMORS.PAS``); the general loot/world-gen pipeline that would assign
a ``treasure`` type to a feature or grant it as combat loot isn't in
this project's available source at all (no ``AK.PAS``/``DEF1.PAS``).

**Phase 140 update**: the registry *structure* itself -- the exact
``treaslist``/``trowner``/``trcharges`` triple this paragraph names --
is now built (``models/item.py ItemInstance``, ``GameState.items``),
along with a faithful ``Add_Tr`` equivalent (``GameState.add_item()``).
So an ``item_instance_id`` *can* now be resolved via
``state.items.get(item_instance_id)`` once something has actually
called ``add_item()`` for it. What's still missing is exactly what this
paragraph originally said: an automatic world-gen/loot trigger that
calls it -- ``ak_engine`` has no way to *auto-populate* the registry the
way it auto-populates the mercenary-army pool (Phase 16) or
independent-hero pool (Phase 17), since there's no Pascal source
describing how instances come into existence in the first place.
**Stale as of a later phase** -- this paragraph used to also say a
real ``execute_use_mi()`` resolver consuming the now-resolvable id was
still a separate, not-yet-built follow-up; ``turn/use_mi_execution.py
execute_use_mi()`` is that resolver and has existed for a while
(wands, skill books, the Illus_Terrain/Charm/Resurrection sub-reads
this same docstring names below, all wired against a real, populated
``GameState.items``) -- only the registry's own *auto-population* gap
described just above remains genuinely open.

**The ``treasure`` type enum itself, though, is fully present and has
been reconstructed** (``CTBOTH.PAS`` lines 605-645, cross-referenced
against ``HostAK/TP/PROSE/TREASURE.X2``/``TREASAB.X2``'s flavor text,
whose entries are obfuscated in the Pascal source itself -- identifiers
like ``hla``, ``wcp``, ``xle`` carry no meaning by design, so the
readable names live only in the prose files): 113 ordinals across seven
functional groups -- 15 passive ability-boosting items (one per
``Ability``, "operate automatically", never a ``Use_MI`` target), **20
spell-casting "wands"** (ordinals 15-34, one per each of the first 20
``Spell`` ordinals, 1:1 positional -- these are exactly the
``wcp..pic`` range the ``CASE`` above checks, and are what actually
triggers the ``Read_More`` sub-read shown above), 5 named combat
weapons and 4 race-leadership weapons (wielded via combat tactics, not
``Use_MI``), 5 anti-magic-school amulets and 3 monster-command items
(automatic, not ``Use_MI`` targets), **15 one-shot skill-boosting
"books"** (ordinals 52-66, one per ``Ability``, explicitly documented
as ``Use_MI``-invoked and self-consuming, but -- unlike the wands --
outside the ``wcp..pic`` check, so a book's ``Use_MI`` phase triggers
*no* extra sub-read at all), plus non-magic-item bookkeeping ordinals
(gold-hoard tiers, quest-tracking entries, a sentinel, unused reserved
slots). Only the 20 wands and 15 books -- 35 of 113 ordinals -- are
legitimate ``Use_MI`` targets at all; the rest "operate automatically"
per rulebook [5.9] and are never invoked by this action. ~~This
project's ``models/item.py MagicItem`` stub is a reasonable shape for a
future type catalog, but populating all 113 entries accurately needs a
careful direct transcription of the prose files, not attempted here.~~
**The full 113-ordinal type catalog now exists as of Phase 77**
(``models/treasure.py Treasure``/``TreasureCategory``, with
``USE_MI_TARGET_CATEGORIES`` marking exactly the wand/book split named
above) -- see that phase's own README note for the transcription
details. ``models/item.py ItemInstance`` (Phase 140) is the physical
item *instance* shape (owner, charges) built on top of that catalog --
see the paragraph above for exactly what it does and doesn't close.

**When the resolved item type is a wand, the exact same conditional
sub-reads as Cast fire** (Illusory Terrain's extra fake-``Terrain``
field at ``extra[1]``; Charm/Resurrection's nested plan, per
``PlanPhase.nested_plan``). ``parser/k1_moves.py``'s nested-plan
detection is already action-agnostic (structural: "does an ``AP:``
token immediately follow", not gated on which action triggered it), so
it handles a Use_MI-triggered nesting correctly with no changes needed
-- only the nested plan's inferred ``leader_id`` (Phase 23's Cast/Charm/
Resurrection extension) doesn't currently extend to a Use_MI-cast
Charm/Resurrection, since that extension keys off ``ActionCode.CAST``
specifically; left as a known gap, not fixed here, since there's no
real data to validate it against either way.

**Zero real Use_MI phases exist in any of the 10 sample
``AK3__T*.K1`` files** (independently confirmed via this project's own
parser, not just a text search) -- same situation as Fire and Trade,
decoded here from Pascal-source reconstruction alone with no real-data
cross-check.
"""

from __future__ import annotations

from dataclasses import dataclass

from ak_engine.models.map import Terrain
from ak_engine.models.plan import PlanPhase


@dataclass(slots=True)
class UseMIRequest:
    item_instance_id: int  # phase.obj -- a global item-instance id, NOT a treasure-type ordinal (see module docstring)
    target: int  # phase.extra[0] -- generic target field, semantics unresolved (no live code consumes it directly)
    terrain: Terrain | int | None = None  # phase.extra[1], only if the item casts Illus_Terrain


def decode_use_mi_phase(phase: PlanPhase) -> UseMIRequest:
    """Decode a Use_MI PlanPhase's item-instance id and generic target/terrain fields.

    Cannot resolve ``item_instance_id`` to a specific item type or spell
    -- see the module docstring for why that's structurally impossible
    from decode alone. ``terrain`` is only ever populated if the
    caller already knows (from external game state this project doesn't
    have) that the referenced item casts Illusory Terrain; absent that,
    a second ``extra`` element is passed through as an unresolved
    ``Terrain | int``, matching ``cast_decode.py``'s own convention.
    """

    target = phase.extra[0] if phase.extra else 0

    terrain: Terrain | int | None = None
    if len(phase.extra) > 1:
        try:
            terrain = Terrain(phase.extra[1])
        except ValueError:
            terrain = phase.extra[1]

    return UseMIRequest(item_instance_id=phase.obj, target=target, terrain=terrain)
