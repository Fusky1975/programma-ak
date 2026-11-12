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
  ``kingdom.kingdom_id`` (Phase 574 -- the file-name-derived real
  identifier; see that property's own docstring for why the header's own
  ``kingdom_number`` field was confirmed broken and replaced).
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

**Phase 330 addendum -- ``sync_leaders_from_gw_world``, closing the
leader-to-kingdom-ownership gap flagged since Phase 224.** The K1-based
sync above has two real limits: it only ever sees leaders who are
*submitting orders this turn* (a Hero sitting idle, or an independent
Hero doing nothing, never appears in any King's own move file at all),
and it cannot supply anything beyond ``kingdom_id``/``skills``/``is_king``
(a move file carries no race/alignment/temper for anyone). The world
file (``parser/gw_world.py``'s ``GWLeaderRecord``, Phase 330) has neither
limit: it's a full snapshot of every King and Hero in the game, whether
or not they moved this turn, and it independently carries the Liege
field (Phase 325/327, confirmed 27-for-27 against real letter rosters)
that decodes every Hero's own real ``kingdom_id`` directly, plus
race/alignment/temper/skills that this bridge previously had no source
for at all.

Matched by **name**, the same limitation the K1-based sync above already
has (a ``GWLeaderRecord`` carries no ``leader_id`` either -- see that
dataclass's own docstring for why) -- so, like the function above, this
only enriches ``LeaderState``s that already exist in ``state.leaders``,
never creates new ones. For every matched leader it authoritatively sets
``race``/``alignment``/``temper``/``skills``/``is_king`` (real data this
project had no other source for), and, for a Hero record specifically,
``kingdom_id`` too (a King's own record can't supply his own kingdom id
this way -- see ``GWLeaderRecord.kingdom_id``'s own docstring for the
separate, file-order-based derivation this project uses for a King's own
id instead, not reused here since a King's own ``kingdom_id`` already has
a confirmed source via the K1-based sync's own King-name match). A
matched Hero's ``kingdom_id`` is set even when it's currently ``None``
in ``state.leaders`` -- e.g. an independent Hero later Hired, or a Hero
who simply never appeared in a submitted move file before -- something
the K1-based sync alone could never populate.

**Phase 1193: the real call site is ``webapp/app.py turns_sync_world_
leaders()``** -- a GM-facing world-file upload on the Turn Cycle page,
reachable independently of turn processing itself (a GM applies a
fresher world-file snapshot whenever one becomes available, not only
once per turn), parsing the upload with ``parser/gw_world.py parse_gw_
leaders()`` and showing the GM a plain-English summary of how many
leaders were synced/unmatched. Previously this function, and the GW-
world-file parsing subsystem generally, had zero production callers.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ak_engine.models.game_state import GameState, LeaderState
from ak_engine.models.kingdom import Kingdom
from ak_engine.parser.gw_world import GWLeaderRecord


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
    kingdom_id = kingdom.kingdom_id
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


@dataclass(slots=True)
class GWKingdomBridgeReport:
    synced_names: list[str] = field(default_factory=list)
    kingdom_id_set_for_names: list[str] = field(default_factory=list)
    not_found_names: list[str] = field(default_factory=list)


def sync_leaders_from_gw_world(records: list[GWLeaderRecord], state: GameState) -> GWKingdomBridgeReport:
    """Apply the real, world-file-derived data described in the module docstring's own
    Phase 330 addendum to ``state``.

    Matches each ``GWLeaderRecord`` to an existing ``LeaderState`` by name;
    mutates matches in place, never creates new ones (see the module
    docstring for why). For a matched Hero record, also sets
    ``kingdom_id`` from ``record.kingdom_id`` -- for a matched King
    record, ``kingdom_id`` is left untouched (see ``GWLeaderRecord``'s
    own docstring for why a King's own record can't supply it here).

    **Phase 1192 bug fix**: matching used to build one *global*,
    cross-Kingdom ``name -> LeaderState`` index, so two different
    ``LeaderState``s anywhere in the game sharing the same ``.name``
    (plausible with generic Hero names reused across Kingdoms, and a
    ``GWLeaderRecord`` carries no ``leader_id`` of its own to disambiguate
    with -- see that dataclass's own docstring) silently collapsed onto
    whichever one a plain dict comprehension happened to keep last --
    misattributing a record's own race/alignment/temper/skills/kingdom_id
    to the wrong leader with no error reported at all (``report.not_
    found_names`` stayed empty, since the name genuinely *was* found,
    just ambiguously). A name matching more than one current ``LeaderState``
    is now treated the same as matching none -- reported in ``not_found_
    names`` rather than guessed -- the same "never a silent guess"
    discipline this project applies everywhere else.
    """

    report = GWKingdomBridgeReport()
    name_counts: dict[str, int] = {}
    by_name: dict[str, LeaderState] = {}
    for leader in state.leaders.values():
        name_counts[leader.name] = name_counts.get(leader.name, 0) + 1
        by_name[leader.name] = leader

    for record in records:
        leader_state = by_name.get(record.name) if name_counts.get(record.name, 0) == 1 else None
        if leader_state is None:
            report.not_found_names.append(record.name)
            continue

        leader_state.race = record.race
        leader_state.alignment = record.alignment
        leader_state.temper = record.temper
        leader_state.skills = record.skills
        leader_state.is_king = record.is_king
        report.synced_names.append(record.name)

        if not record.is_king:
            leader_state.kingdom_id = record.kingdom_id
            report.kingdom_id_set_for_names.append(record.name)

    return report
