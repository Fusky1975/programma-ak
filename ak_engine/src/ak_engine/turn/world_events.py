"""Cross-kingdom event visibility -- GENERAL INTELLIGENCE REPORT's own
real visibility rule (Phase 231; corrected and extended Phase 408).

**Real content confirmed directly from real generated letters, not
guessed**: the Desktop's real `SE3__T*.K*` files show the section as one
`Kingdom of <Name> (#<id>):` block per foreign kingdom whose activity is
visible to the reader, each followed by narrative paragraphs (battles,
movement, plagues, terrain illusions, spell effects...). ``is_visible_to()``
below is built from the rulebook's own [1.4] text plus the real fixture
output, not from a generating procedure -- see the Phase 408 addendum
just below for why, even after finding that procedure, it still isn't
the basis for this function.

**Visibility rule**, rulebook [1.4] (quoted directly): "un giocatore
viene informato quando una provincia adiacente al suo Reame cambia di
mano e può anche ricevere informazioni sulle attività di personaggi
controllati da un altro Re quando agiscono entro i confini del suo
Reame." Read as one combined test, covering both clauses at once:
``kingdom_id`` is informed of something that happened at ``coord`` if
``coord`` is a province it owns (the second clause -- activity *inside*
its own borders) or adjacent to one it owns (the first clause -- a
bordering province changing hands, or any other event there). See
``report/turn_report.py describe_general_intelligence_report()``'s own
docstring for how this feeds the real "Kingdom of X (#N):" grouped feed
and for the deliberately narrow slice of event *sources* this project
records today (battle results, Phase 231; Plague/Illusory Terrain casts,
Phase 232 -- see that module's docstring for the full list of
confirmed-real, still-deferred event types).

**Phase 408 addendum -- the real generating procedure was found, and
most of it turned out to be dead code**: the earlier claim that "no
`Rep_Intel`-equivalent procedure survives" was wrong -- ``RUMORS.PAS``'s
``Get_News(kng): boolean`` ("Does foreign kng get a copy of the string
in his general intelligence report?") is exactly that procedure. Its
real gate (``SAY.PAS`` ~100-103, inside ``{$IFDEF Moderator}``):
```
IF (((event_lev >= S_IDipl) and (kkmet[Min(kng,playking)] and
     (longint(1) Shl Max(kng,playking)) = 1)) or
    (event_lev >= spy_lev[kng]) or
    (event_lev >= intel_lev[kng])) THEN ...
```
is an OR of three clauses. Only the **first** (the diplomatic-contact
one) is implemented here, as ``record_kingdom_contacts()`` /
``GameState.kingdoms_met`` / the ``event_lev`` parameter below. The
other two are deliberately **not** ported, because tracing them all the
way down showed they're either dead or unverifiable:

- ``intel_lev[kng]`` is computed by ``RUMORS.PAS Set_Intel(x,y)``
  (~671-746), which has exactly one call site in the entire available
  archive (``SAY.PAS`` ~363-373) -- inside a branch its own author
  marked `{********** no longer in use!!!!!!!!!!!!!!!}` and gated behind
  a debug halt (`WEK`). Grepping every `Imp_Code(...)` call site and
  every literal/computed value across the archive, nothing ever
  produces a code that reaches that branch: it is unreachable. This is
  also the branch that would have modeled Clairvoyance's own "the
  caster knows everything that happens to the target" grant (via
  `Set_Intel`'s `Counter_Science`/`L_Clairv` block, checked against
  `LeaderState.clairvoyance_watchers`) -- so that grant is confirmed
  dead code, not merely undiscovered. `LeaderState.clairvoyance_watchers`
  therefore stays exactly as Phase 193 left it: recorded, but with
  nothing reading it, and no plan to build a reader.
- ``spy_lev[kng]``'s only assignment anywhere in the archive is inside
  that same dead branch (`SAY.PAS` ~368-369). No declaration for either
  array survives (both presumably live in the missing `DEFINES.PAS`),
  so their real per-turn initialization can't be recovered -- porting
  either as "real" would mean inventing a baseline dressed up as
  sourced, which this project doesn't do.

The diplomatic-contact clause survives this scrutiny because its inputs
are independently confirmed live: `kkmet` is populated every turn by
`Check_KKSugg` (`REPORTS.PAS` ~173-202), itself called from real,
non-dead diplomacy reporting (`REPORTS.PAS` ~244, `Rep_Allies`-adjacent),
via `Adj_King` -- own-province-borders-their-province. ``S_IDipl`` (10)
is the highest of the eleven `spytype` tier constants (`CTBOTH.PAS`
~61-63: `S_Prev=0, S_Red=1, S_Priv=2, S_PCom=3, S_Adv=4, S_Batt=5,
S_AA=6, S_Admin=7, S_Army=8, S_Comm=9, S_IDipl=10`) -- the broadest,
"international news" tier. No renderer in this project tags anything at
that tier yet (the ``event_lev`` parameter below is consequently a
no-op for every event source currently wired), but the mechanism itself
is real, sourced, and ready for whichever future event a Say()-derived
renderer confirms belongs there.
"""

from __future__ import annotations

from ak_engine.models.game_state import GameState
from ak_engine.models.map import HexCoord
from ak_engine.turn.movement import MapBounds, neighbors

# CTBOTH.PAS ~61-63 -- the full `spytype`/`event_lev` tier vocabulary.
# Only S_IDIPL is consumed by this module today (the diplomatic-contact
# clause below); the rest are transcribed for citation completeness and
# for future renderers to tag against, per the module docstring's Phase
# 408 addendum.
S_PREV = 0
S_RED = 1
S_PRIV = 2
S_PCOM = 3
S_ADV = 4
S_BATT = 5
S_AA = 6
S_ADMIN = 7
S_ARMY = 8
S_COMM = 9
S_IDIPL = 10


def is_visible_to(
    state: GameState, kingdom_id: int, coord: HexCoord, bounds: MapBounds, *, event_lev: int | None = None
) -> bool:
    """Whether ``kingdom_id`` would be informed of an event at ``coord`` --
    see module docstring for the rulebook [1.4] rule this implements, and
    its Phase 408 addendum for the ``event_lev`` parameter (the real
    ``Get_News()`` diplomatic-contact clause, additive to the base rule --
    passing ``None`` reproduces the exact pre-408 behavior).
    """

    province = state.provinces.get(coord)
    if province is not None and province.owner_kingdom_id == kingdom_id:
        return True
    for neighbor_coord in neighbors(coord, bounds):
        neighbor = state.provinces.get(neighbor_coord)
        if neighbor is not None and neighbor.owner_kingdom_id == kingdom_id:
            return True
    if (
        event_lev is not None
        and event_lev >= S_IDIPL
        and province is not None
        and state.has_met(kingdom_id, province.owner_kingdom_id)
    ):
        return True
    return False


def record_kingdom_contacts(state: GameState, bounds: MapBounds) -> None:
    """Populates ``GameState.kingdoms_met`` (Phase 408) -- mirrors
    ``Check_KKSugg``'s own real, live computation (``REPORTS.PAS``
    ~173-202): for every province a kingdom owns, any other kingdom
    owning an adjacent province has now "met" it. Bits are only ever
    added, never cleared (matching `kkmet`'s own `or`-in-place update),
    so calling this every turn is safe and idempotent -- a contact once
    made is never un-made.

    **Must be called once per turn, before any ``is_visible_to()`` call
    that passes ``event_lev``** -- same "turn-global, single caller"
    contract as ``report/turn_report.py record_battle_world_events()``.

    **Phase 491 addendum**: also stamps ``GameState.kingdoms_met_since``
    with this turn's own ``state.turn_number`` the first time a pair is
    ever added -- ``setdefault`` so an already-stamped pair keeps its
    real first-contact turn on every later call, never overwritten to a
    later one.

    **Phase 872 -- now actually wired, closing a real dead-subsystem
    gap.** Despite the "must be called once per turn" contract above
    dating to Phase 408, nothing anywhere ever called this function --
    confirmed by grep, zero real call sites outside its own definition
    and `tests/test_world_events.py`'s own unit tests. Every real game
    this engine has ever processed therefore left ``kingdoms_met``/
    ``kingdoms_met_since`` permanently empty, silently starving 3 real
    downstream consumers: `turn/imperial_intelligence.py`'s own World
    Emperor/Imperial Treasurer perks (via ``has_met_for_full_turn()``),
    `report/turn_report.py describe_diplomacy_report()`'s own alignment
    sentence (via ``has_met()``), and this function's own ``is_visible_
    to()`` sibling's ``event_lev`` clause (though that one's real call
    site never actually passes ``event_lev``, so it stays independently
    dead regardless -- a separate, pre-existing gap, not newly closed
    here). Now called from ``orchestrator.py process_turn()``, in the
    same turn-global recorder cluster as ``record_battle_world_events()``
    -- see that module's own Phase 872 addendum.
    """

    for coord, province in state.provinces.items():
        owner = province.owner_kingdom_id
        if owner is None:
            continue
        for neighbor_coord in neighbors(coord, bounds):
            neighbor = state.provinces.get(neighbor_coord)
            if neighbor is None or neighbor.owner_kingdom_id is None or neighbor.owner_kingdom_id == owner:
                continue
            pair = frozenset((owner, neighbor.owner_kingdom_id))
            state.kingdoms_met.add(pair)
            state.kingdoms_met_since.setdefault(pair, state.turn_number)
