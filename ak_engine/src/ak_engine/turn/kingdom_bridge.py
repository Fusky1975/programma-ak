"""Bridging a parsed move-submission file (``models.kingdom.Kingdom``) into a
persistent ``GameState`` (``models/game_state.py``).

**Why this is much narrower than "load a Kingdom into the game"**: a
``.K1`` move file is an *order submission*, not a state snapshot. It
carries a King's name/title, his own real ``SkillTable`` (skill/aptitude
pairs), a list of leaders currently submitting orders as part of his
kingdom, and each leader's plan for the turn -- and nothing else. It has
**no location, race, alignment, home province, or treasury for anyone** --
those live in the game's persistent state, which this project has no
access to (the original engine's own save-game format was never part of
the available Pascal source; see ``ak_engine/README.md``). So this module
cannot create a ``KingdomState`` or a new ``LeaderState`` out of thin air
-- there's nothing to give a freshly-created one for ``location``,
``race``, etc. that wouldn't be a fabricated guess.

What it *can* honestly do, given only what the move file actually
contains: for every ``Leader`` in ``kingdom.leaders`` that **already has**
a matching ``LeaderState`` in ``state.leaders`` (created by whatever
turn-0 setup or prior-turn processing the caller already did), sync the
two pieces of real data the file provides:

- **``kingdom_id``**: a leader appearing in Kingdom N's move-file submission
  this turn is, by construction, currently in Kingdom N's service this
  turn (only a King's own leaders' orders are submitted together in his
  file) -- so every matched leader's ``LeaderState.kingdom_id`` is set to
  ``kingdom.header.kingdom_number``.
- **``skills``**: only the King's own real ``SkillTable`` is present in the
  file (``Kingdom.skills`` -- see that class's docstring); no other
  leader's ability data is ever in a move file. The King's own entry
  within ``kingdom.leaders`` is identified by name match against
  ``kingdom.king_name`` (empirically always the first leader block in
  every sample file, e.g. ``AK3__T1.K1``'s "1 -Uga-Buga Makumb" following
  the king-name line "Uga-Buga Makumb" -- but matched by name here rather
  than by position/id, since that's the actual invariant the file
  encodes, not an assumption that the King is always id 1).
- **``is_king``** (Phase 40): the same name-matched identification also
  sets ``LeaderState.is_king`` for every synced leader in the file --
  ``True`` for the identified King, ``False`` for every other leader
  (an authoritative sync, not just "set True and leave everyone else
  alone" -- a leader who was, say, hand-marked as a King in a prior test
  setup but isn't the King in *this* file's data gets corrected).

Leaders present in ``kingdom.leaders`` with no existing ``LeaderState``
are left uncreated and reported as skipped -- not a bug, a direct
consequence of having no location data for them. Populating ``GameState``
from nothing (turn 0) is a separate, still-unsolved problem this module
doesn't attempt to solve.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ak_engine.models.game_state import GameState
from ak_engine.models.kingdom import Kingdom


@dataclass(slots=True)
class KingdomBridgeReport:
    synced_leader_ids: list[int] = field(default_factory=list)
    skills_attached_to_leader_id: int | None = None
    not_found_leader_ids: list[int] = field(default_factory=list)
    king_not_identified: bool = False  # no leader in the file's name matched kingdom.king_name


def sync_leaders_from_kingdom(kingdom: Kingdom, state: GameState) -> KingdomBridgeReport:
    """Apply the real, move-file-derived data described in the module docstring to ``state``.

    Mutates matching ``LeaderState``s in place; never creates new ones.
    """

    report = KingdomBridgeReport()
    kingdom_id = kingdom.header.kingdom_number
    king_matches = [leader for leader in kingdom.leaders if leader.name == kingdom.king_name]
    king_leader_id = king_matches[0].leader_id if king_matches else None
    report.king_not_identified = king_leader_id is None

    for leader in kingdom.leaders:
        leader_state = state.leaders.get(leader.leader_id)
        if leader_state is None:
            report.not_found_leader_ids.append(leader.leader_id)
            continue

        leader_state.kingdom_id = kingdom_id
        leader_state.is_king = leader.leader_id == king_leader_id
        report.synced_leader_ids.append(leader.leader_id)

        if leader.leader_id == king_leader_id:
            leader_state.skills = kingdom.skills
            report.skills_attached_to_leader_id = leader.leader_id

    return report
