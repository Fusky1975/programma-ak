"""Race-fanaticism Imperial title Merit Point formulas (Phase 367,
reformulated Phase 369) -- the 11 race-fanaticism titles' own real
scoring rule.

**Phase 369 correction.** Phase 367 built this module's own formula
from ``CARICHE E ABILITÀ.txt``: front-line battle win/loss points, live
Crack-or-better units commanded, heroes-in-service, provinces-owned,
rival-race kills, monster-in-province kills, named-monster kills, and a
legendary-item bonus -- seven terms altogether. `AKGEN_embedded_
catalogs.json gw_format.royal_title_system` (a real static disassembly
of ``AK.EXE``/``AK.OVR``, verified against the 12 ``GW3__T1..T12``
historical saves) proved this doesn't match the real compiled formula.
Every one of the 11 entries (ids 9-20) reads, verbatim:

    "score_formula": "Tit_Pts; doubled when holder race is <Race>"
    "how_points_are_obtained": "battle merit for <Race> units: compiled
    scorer gives the unit owner's leader +1 on a victory and -2 on a
    loss, with an additional positive battle award in a proportional/
    random branch; own-race candidates have the stored total doubled
    for ranking"

So the real formula is: a single cumulative counter (+1 per won battle,
**-2** per lost battle -- not the -1 this project had guessed), doubled
outright if the candidate leader's own `Race` matches the title's race.
None of the other six Phase 367 terms exist in the real formula, so
they're removed rather than kept as unused flavor -- `models/game_
state.py RaceTitleTally`'s own Phase 369 note has the same correction.

**One real term is still an honest, documented gap**: "an additional
positive battle award in a proportional/random branch" is named by the
source but never fully specified (the surviving symbol-free code proves
it exists without pinning down its exact magnitude) -- not folded into
`front_line_battles_won_points` by guesswork.

**Kept as-is, not (dis)confirmed by this disassembly pass**: the 7
special races' own "0 points without an owned province" prerequisite
and the per-race turn gate both still come from `CARICHE E ABILITÀ.txt`
only -- this correction pass targeted the *score formula*, and found no
contradicting or confirming evidence either way for these two
eligibility rules, so they're left in place rather than removed on
suspicion alone.
"""

from __future__ import annotations

from ak_engine.models.game_state import GameState, LeaderState, RaceTitleTally
from ak_engine.models.office import Office
from ak_engine.models.race import Race

# Race <-> its own title office (`models/office.py Office`, already
# sourced, Phase 81).
RACE_TITLE_OFFICE: dict[Race, Office] = {
    Race.HUMAN: Office.HUMAN_KING,
    Race.ELVEN: Office.ELVEN_KING,
    Race.DWARVEN: Office.DWARVEN_KING,
    Race.ORCISH: Office.ORC_LORD,
    Race.DRAGONS: Office.DRAGON_LORD,
    Race.EAGLES: Office.EAGLE_KING,
    Race.WHALES: Office.WHALE_KING,
    Race.MERMISH: Office.MERMAN_KING,
    Race.ENTISH: Office.ENT_KING,
    Race.TROLLISH: Office.TROLL_KING,
    Race.WEREFOLK: Office.WERE_KING,
}

# The 7 special races whose own title requires the leader's Kingdom to
# own at least one province of that race -- the 4 core humanoid races
# have no such clause in the source. See module docstring: unconfirmed
# by the disassembly pass, kept as-is.
RACE_TITLE_REQUIRES_OWNED_PROVINCE: frozenset[Race] = frozenset(
    {Race.DRAGONS, Race.EAGLES, Race.WHALES, Race.MERMISH, Race.ENTISH, Race.TROLLISH, Race.WEREFOLK}
)

# "Questa carica entra in gioco alla fine del turno N." See module
# docstring: unconfirmed by the disassembly pass, kept as-is.
RACE_TITLE_TURN_GATE: dict[Race, int] = {
    Race.HUMAN: 4,
    Race.ELVEN: 4,
    Race.DWARVEN: 4,
    Race.ORCISH: 4,
    Race.DRAGONS: 6,
    Race.EAGLES: 6,
    Race.WHALES: 6,
    Race.MERMISH: 4,
    Race.ENTISH: 8,
    Race.TROLLISH: 6,
    Race.WEREFOLK: 6,
}


def _provinces_of_race_owned(state: GameState, kingdom_id: int, race: Race) -> int:
    return sum(
        1
        for province in state.provinces.values()
        if province.owner_kingdom_id == kingdom_id and province.race is race
    )


def race_title_merit_points(state: GameState, leader: LeaderState, race: Race) -> float:
    """One race title's full Merit Point score for ``leader`` -- see
    module docstring for the real, disassembly-confirmed formula. Applies
    the special races' own "0 without an owned province" prerequisite
    directly (Kingdom-scoped, so an independent Hero always reads 0 for
    those 7 races); the turn gate is enforced separately, by
    ``turn/office_holder.py resolve_office_holder()``.
    """

    if race in RACE_TITLE_REQUIRES_OWNED_PROVINCE:
        if leader.kingdom_id is None or _provinces_of_race_owned(state, leader.kingdom_id, race) == 0:
            return 0

    tally = leader.race_title_tally.get(race, RaceTitleTally())
    points: float = tally.front_line_battles_won_points - 2 * tally.front_line_battles_lost_points

    if leader.race is race:
        points *= 2

    return points
