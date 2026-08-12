"""Grandfather of Assassins (Office.ASSASSIN) title's own free assassination
attempt -- AKGEN_reverse_engineering_report (2).md SS20.9, quoted in full:

    Con minpts = 2, bastano due uccisioni letali tramite Kill Enemy per
    rendere il personaggio eleggibile al titolo, salvo il normale
    confronto con gli altri candidati e le regole generali di
    mantenimento/assegnazione delle cariche. L'effetto successivo del
    titolo, documentato in TITLE.X2, resta: P_base = 50% - 5%*A - 10%*M,
    dove A e' il numero di armate nella provincia del bersaglio e M la
    sua skill Melee. Il tentativo avviene una volta per turno, alla fine
    della fase 5 dopo le battaglie, puo' colpire ovunque un personaggio
    non-Re ed e' richiesto con FI-re(character). Ogni fallimento
    raddoppia la guardia e dimezza la probabilita' normale del tentativo
    seguente. Questo e' il premio del titolo, non la formula del suo
    merito.

**The title itself is already fully modeled** -- ``models/office.py
OFFICE_MIN_POINTS[Office.ASSASSIN] == 2`` (matches "minpts = 2" exactly,
Phase 379/438) and ``turn/merit_points.py assassin_merit_points()``
already computes the merit that decides who holds it (Phase 379,
corrected against the same disassembly source at SS20.5). This module
closes the other half: what the title actually *does* once held.

**FI-re(character) has no real order-file shape this project has ever
seen** -- the same "no real order-file shape ever seen" category as
Treat/Break Treaty/Call-For-Vote (``turn/emperor_election.py``'s own
docstring, ``GameState.treat_permissions``'s own Phase 261 docstring).
So ``resolve_grandfather_of_assassins_attempt()`` takes the intended
target as a plain parameter the caller supplies directly, rather than
decoding it from anything -- the same "caller's job" convention already
established for a mechanic this project can't parse an order for. This
also means there is deliberately **no ``turn_processor.py`` wiring**
here: "il tentativo avviene una volta per turno, alla fine della fase 5
dopo le battaglie" describes a real sequencing point, but with no way to
discover *who* the target is from anything this project already parses,
there is nothing to hook automatically -- a caller who has a target (an
external actor's decision, per FI-re) invokes this function directly,
the same posture ``turn/scientific_treaty.py``'s own Phase 474 addendum
and ``turn/final_standings.py``'s own Phase 476 addendum already took
for a comparable "no natural once-per-turn hook exists" gap.

**The formula**: ``P_base = 0.50 - 0.05*A - 0.10*M``, floored at ``0.0``
(no source describes what a formally-negative value would mean, so this
follows the same floor-at-zero convention already used throughout this
project's other probability formulas, e.g. Phase 474's alignment-decay
gate) -- see ``grandfather_of_assassins_base_success_chance()``. ``A`` is
every army physically present in the target's own province
(``GameState.armies_at()``, not ``armies_commanded_by()`` -- the source
says "nella provincia del bersaglio", not "sotto il suo comando"), and
``M`` is the target's own natural Melee skill (``LeaderState.skills``,
``0`` if unrecorded -- the same "no data" placeholder convention already
used everywhere else in this project for missing per-leader ability
data, e.g. ``turn/discovery_effects.py``/``turn/cast_execution.py``'s own
success-roll skill reads). No magic-item skill modifier is applied here
either, the same already-flagged gap (this project tracks no per-leader
magic-item skill bonus anywhere).

**Guard escalation** ("ogni fallimento raddoppia la guardia e dimezza la
probabilita' normale del tentativo seguente"): modeled as ``effective_
chance = base_chance * 0.5**failures``, where ``failures`` is the
target's own ``LeaderState.assassination_guild_failed_attempts`` (see
that field's own docstring for why it's per-target, never reset, and
kept separate from ``MeritTally``'s own Assassin counter).

**Non-King restriction** ("puo' colpire ovunque un personaggio non-Re"):
checked the same way Kill Enemy's own King immunity is (``turn/
cast_execution.py _execute_kill_enemy()``), returning ``None`` (not
attempted) rather than a failed attempt for an ineligible target -- a
King was never a valid FI-re target to begin with, so nothing about
this call should look like a real, guard-raising attempt against one.

**On success**: the target is genuinely removed via ``GameState.
remove_leader()`` -- real death, not Kill Enemy's own Phase 310 coma
variant (a *spell's* documented alternate outcome; the Guild's own
non-magical kill has no comparable "coma instead" clause anywhere in
this source, so the ordinary removal path applies, same as any other
personal-combat death this project already models).

**Deliberately never credited to ``MeritTally``**: SS20.7 lists "il
tentativo gratuito riuscito della Assassins Guild prodotto dall'effetto
del titolo" as one of the confirmed-unreachable paths to the real
``Assassin`` merit counter -- "una volta ottenuto il titolo, la Gilda
puo' uccidere per conto del titolare, ma quella morte non alimenta a sua
volta il contatore." A successful call here therefore never touches
``leader.merit_tally`` at all, on either the titleholder or the target's
own side -- the title's own perk and the metric used to earn it are two
genuinely separate mechanics, and conflating them here would be a real,
avoidable correctness bug, not a simplification.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from ak_engine.models.enums import Ability
from ak_engine.models.game_state import GameState
from ak_engine.models.office import Office
from ak_engine.turn.office_holder import resolve_office_holder


def grandfather_of_assassins_base_success_chance(army_count_in_target_province: int, target_melee_skill: int) -> float:
    """SS20.9's own ``P_base = 50% - 5%*A - 10%*M``, floored at ``0.0`` --
    see module docstring for why a floor (not a documented negative
    meaning) is the right reading here, and why guard escalation is
    deliberately a separate multiplier applied by the caller of this
    function, not baked into it.
    """

    return max(0.0, 0.50 - 0.05 * army_count_in_target_province - 0.10 * target_melee_skill)


@dataclass(slots=True, frozen=True)
class GrandfatherOfAssassinsAttemptResult:
    """One resolved Guild attempt -- see module docstring for the full
    derivation of ``success_chance`` (base formula times the target's
    own guard-escalation multiplier) and why a successful attempt
    updates neither side's ``MeritTally``.
    """

    titleholder_leader_id: int
    target_leader_id: int
    success_chance: float
    succeeded: bool


def resolve_grandfather_of_assassins_attempt(
    state: GameState, target_leader_id: int, rng: random.Random | None = None
) -> GrandfatherOfAssassinsAttemptResult | None:
    """Resolves one Grandfather of Assassins free attempt against
    ``target_leader_id``, on behalf of whoever currently holds
    ``Office.ASSASSIN``. Returns ``None`` (nothing attempted, no state
    mutated) if nobody currently holds the title, the target doesn't
    exist, or the target is a King -- see module docstring for why an
    ineligible King is refused outright rather than resolved as a
    guaranteed failure.
    """

    rng = rng if rng is not None else random.Random()

    holder = resolve_office_holder(state, Office.ASSASSIN)
    if holder is None:
        return None

    target = state.leaders.get(target_leader_id)
    if target is None or target.is_king:
        return None

    army_count = len(state.armies_at(target.location))
    melee_skill = target.skills.pair_for_ability(Ability.MELEE)[0] if target.skills is not None else 0
    base_chance = grandfather_of_assassins_base_success_chance(army_count, melee_skill)
    effective_chance = base_chance * (0.5**target.assassination_guild_failed_attempts)

    succeeded = rng.random() < effective_chance
    if succeeded:
        state.remove_leader(target_leader_id)
    else:
        target.assassination_guild_failed_attempts += 1

    return GrandfatherOfAssassinsAttemptResult(
        titleholder_leader_id=holder.leader_id,
        target_leader_id=target_leader_id,
        success_chance=effective_chance,
        succeeded=succeeded,
    )
