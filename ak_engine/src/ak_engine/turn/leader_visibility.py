"""``Ldr_Near``/``Known_Loc`` primitives (``RUMORS.PAS``), Phase 636.

Sourced from ``LDRNEAR.md`` (Desktop/PROGRAMMA AK/LDRNEAR.md,
2026-08-25), a disassembly-level reverse-engineering report the user
supplied to close a "no source" blocker found while investigating the
CHARACTERS report's own "impulse 2" (wandering Heroes/other Kings'
leaders this kingdom happens to know the location of) and "impulse 3"
(Priest-office clairvoyance) passes.

**Phase 636 correction, kept for the record**: this docstring originally
said these primitives weren't wired into any report composer yet, and
that ``orig_turn``'s real mapping was unconfirmed. Both are now closed:
``report/turn_report.py describe_characters_report()`` wires impulse
2/3 in full as of Phase 639 (``_impulse2_candidates()``/``_impulse3_
candidates()``, calling ``leader_location_known_to_kingdom()`` below
directly), and ``orig_turn = GameState.turn_number`` is confirmed (not
assumed) by the user's own ``ORIGTURN.md`` disassembly report
(Desktop/ORIGTURN.md, 2026-08-26) -- see [[project_characters_
impulse23_phase636]] for the full closure history.

``leader_location_known_to_kingdom()`` still takes ``orig_turn`` as an
explicit caller-supplied parameter rather than resolving it internally
(the real Pascal ``Known_Loc`` reads it from a global the function
itself never derives), but every real caller now simply passes `state.
turn_number`.

``known_mercenary()`` (Phase 642) closes the module's own last
originally-deferred item: ``Known_Merc`` (``RUMORS.PAS``), the ARMIES
report's own mercenary-army-visibility check, reusing ``leader_near()``
at ``radius=1`` exactly as this docstring originally flagged.
"""

from __future__ import annotations

import itertools

from ak_engine.models.game_state import ArmyState, GameState
from ak_engine.models.map import HexCoord
from ak_engine.turn.movement import hex_distance_wrapped
from ak_engine.turn.spy_cover import notice_chance_of
from ak_engine.worldgen.place_map import DEFAULT_WIDTH


def leader_near(
    state: GameState,
    kingdom_id: int,
    coord: HexCoord,
    radius: int,
    *,
    board_width: int = DEFAULT_WIDTH,
) -> bool:
    """``Ldr_Near(kng,x,y,radius)`` -- LDRNEAR.md section 2.

    Existential test: at least one leader with ``LeaderState.kingdom_id
    == kingdom_id`` (the already-established ``LKing(ldr) = kng``
    mapping) within ``radius`` hexes of ``coord`` (inclusive, wraparound-
    aware via ``hex_distance_wrapped()``).

    Scans both ``state.leaders`` (living) and ``state.dead_leaders``
    (archived by ``GameState.remove_leader()``, Phase 59) -- the source
    confirms ``Ldr_Near`` has no ``Dead`` filter at all (LDRNEAR.md
    section 2.3, point 5: "Non controlla direttamente lstate[ldr] e non
    contiene un filtro esplicito contro Dead").
    """

    for leader in itertools.chain(state.leaders.values(), state.dead_leaders.values()):
        if leader.kingdom_id != kingdom_id:
            continue
        if hex_distance_wrapped(leader.location, coord, board_width) <= radius:
            return True
    return False


def leader_location_known_to_kingdom(
    state: GameState,
    target_leader_id: int,
    viewer_kingdom_id: int,
    *,
    orig_turn: int,
    board_width: int = DEFAULT_WIDTH,
) -> bool:
    """``Known_Loc(ln,kng,gtmod=0,advrep=true)`` -- LDRNEAR.md section
    6.2, the exact reduction ``REPORTS.PAS Rep_Leaders`` uses for the
    CHARACTERS report's impulse-2/3 passes.

    ``target_leader_id`` is looked up in ``state.leaders`` then
    ``state.dead_leaders`` -- an unknown id, or a target who belongs to
    the viewer's own kingdom, is never a "stranger" and returns
    ``False`` immediately, matching the real formula's own ``LKing(ln)
    != kng`` guard.
    """

    target = state.leaders.get(target_leader_id) or state.dead_leaders.get(target_leader_id)
    if target is None:
        return False
    if target.kingdom_id == viewer_kingdom_id:
        return False

    province = state.provinces.get(target.location)
    owner_kingdom_id = province.owner_kingdom_id if province is not None else None

    # ``powner[lx[ln],ly[ln]] <> ln`` (advrep=true, so the ``or (not
    # advrep)`` half of the real clause never applies): once LKing's own
    # "King index == Kingdom id" fact is applied, this is only ever
    # false when the target is a King sitting on his own kingdom's
    # throne province -- unconditionally true for any Hero target,
    # whose leader_id never lands in the Kingdom-id range.
    if target.is_king and target.kingdom_id is not None and owner_kingdom_id == target.kingdom_id:
        return False

    # cover_gate: ``Dead(ln) or Trunc(16*ISpy_Cover(ln)) > ((kng+ln+orig_turn+gtmod+
    # begvalkng) AND 15)``. ``ISpy_Cover`` is 1.0 (so the gate always holds) unless the
    # character used Spy/Trail or a Steal tactic this turn -- then the Spy Table's chance of
    # being noticed (``turn/spy_cover.py``) lets only that share of (kingdom, character, turn)
    # combinations see them. ``gtmod`` is 0 here; ``begvalkng`` (a per-game constant in the
    # original, not recoverable from the archive) is taken as 0.
    cover_gate = (
        state.leaders.get(target_leader_id) is None
        or int(16 * notice_chance_of(state, target)) > ((viewer_kingdom_id + target_leader_id + orig_turn) & 15)
    )

    location_gate = owner_kingdom_id == viewer_kingdom_id or (
        (target_leader_id + orig_turn) % 5 <= 1
        and leader_near(state, viewer_kingdom_id, target.location, 0, board_width=board_width)
    )

    return cover_gate and location_gate


def known_mercenary(
    state: GameState,
    army: ArmyState,
    kingdom_id: int,
    *,
    board_width: int = DEFAULT_WIDTH,
) -> bool:
    """``Known_Merc(an,kng)`` -- ``RUMORS.PAS`` lines 231-235 (Phase 642),
    the ARMIES report's own "which independent mercenaries can this
    kingdom see and Recruit" check:

    ``Known_Merc := (astate[an] = Mercenary) and ((powner[ax,ay] = kng)
    or (Ldr_Near(kng,ax,ay,1)))``

    ``astate[an] = Mercenary`` is ``army.is_mercenary`` -- the exact
    predicate `GameState.mercenaries_at()` already uses (bug fix,
    2026-10-25: previously read as `army.kingdom_id is None`, which
    also matched every ordinary unowned province's own native garrison
    -- see `ArmyState.is_mercenary`'s own docstring for the real-sample
    evidence). `radius=1` here (adjacent province counts), unlike
    `Known_Loc`'s own `radius=0` for the CHARACTERS report.
    """

    if not army.is_mercenary:
        return False
    province = state.provinces.get(army.location)
    owner_kingdom_id = province.owner_kingdom_id if province is not None else None
    return owner_kingdom_id == kingdom_id or leader_near(state, kingdom_id, army.location, 1, board_width=board_width)
