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

**Phase 614 -- wired into production.** A user-supplied direct
disassembly reverse-engineering report (`AK.EXE`/`AK.OVR`, byte offsets
cited throughout, 2026-08-22) resolved the one real blocker Phase 612's
own research found: **FI-re(character)'s real order-file shape is now
confirmed**, not invented. `AK.EXE:0xCD0D-0xCD39` intercepts an ordinary
`ActionCode.FIRE` order *before* its normal Hero-release logic runs,
exactly when `target >= nkings` (this project: `not target.is_king`),
`order_giver = titchar[Assassin]` (`resolve_office_holder(state,
Office.ASSASSIN)`), and `LKing(target) <> LKing(order_giver)` (`target.
kingdom_id != order_giver.kingdom_id`, both real) all hold -- see
`turn/plan_dispatch.py _dispatch_fire()`'s own Phase 614 addendum for
the interception itself. `resolve_grandfather_of_assassins_attempt()`
below still takes its target as a plain parameter (now supplied by
`resolve_pending_guild_assassination()`, not a caller's own invented
value) -- the "which target" decoding gap this docstring used to flag
is closed, not the function's own calling convention.

**The once-per-turn queue and phase-5 timing**: `AK.EXE:0xCCC2-0xCCE0`
keeps a single global slot (`GameState.pending_guild_target`, Phase
614), overwritten by a later same-turn interception rather than queuing
a list (`"l'ultimo bersaglio sovrascrive i precedenti"`, a confirmed
real anomaly). `AK.EXE:0x18D13-0x18D18` resolves it once battles for the
turn are done -- `resolve_pending_guild_assassination()` below is called
exactly once per turn from `orchestrator.py process_turn()`, right after
`run_turn()` returns (see that function's own Phase 608 addendum for why
a single post-`run_turn()` call is this project's own equivalent of "a
real sequencing point with nothing to hook automatically" no longer
applying).

**The formula**: ``P_base = 0.50 - 0.05*A - 0.10*M``, floored at ``0.0``
(no source describes what a formally-negative value would mean, so this
follows the same floor-at-zero convention already used throughout this
project's other probability formulas, e.g. Phase 474's alignment-decay
gate) -- see ``grandfather_of_assassins_base_success_chance()``. ``A`` is
every army physically present in the target's own province
(``GameState.armies_at()``, not ``armies_commanded_by()`` -- the source
says "nella provincia del bersaglio", not "sotto il suo comando").

**``M`` correction (Phase 614)**: previously read as the target's own
*raw* stored Melee skill. The new disassembly is explicit (CERTO,
`AK.EXE:0x18DC0-0x18DC8`) that the real formula calls `M_Skill`, the
*effective/modified* skill the engine recognizes at resolution time --
this project already has that exact function, ``turn/discovery_effects.py
effective_skill_level()`` (Phase 534: folds in Discovery bonuses, item
bonuses, comatose zeroing), it just wasn't used here. The old "no
magic-item skill modifier tracked anywhere" docstring claim was stale
even before this phase (Phase 534 predates this module).

**Guard escalation** ("ogni fallimento raddoppia la guardia e dimezza la
probabilita' normale del tentativo seguente"): modeled as ``effective_
chance = base_chance * 0.5**attempts``, where ``attempts`` is the
target's own ``LeaderState.assassination_guild_attempts`` (see that
field's own docstring for why it's per-target, never reset, and kept
separate from ``MeritTally``'s own Assassin counter). **Phase 614
correction**: this counter increments after *every* resolved attempt,
not only a failed one (CERTO, `AK.EXE:0x18F0F-0x18F1D` -- both branches
converge on the same increment) -- renamed from `assassination_guild_
failed_attempts` accordingly; see that field's own docstring.

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

**`resolve_pending_guild_assassination()` (Phase 614)**: the real
phase-5 entry point. Consumes and always clears `state.pending_guild_
target`; if the target is already dead by resolution time (`AK.EXE`'s
own "dead and buried" branch, `ILLEG.X2` record 91), returns an
`already_dead` outcome with **no** guard-counter increment (that branch
skips it in the disassembly too) rather than calling `resolve_
grandfather_of_assassins_attempt()` at all -- a `None`/missing target
there would otherwise be indistinguishable from "nothing was queued."

**`commit_office_holders()` has no caller anywhere in production**
(confirmed by search, Phase 614) -- `state.office_holders`'s own
"current titleholder retains ties" stickiness tier is therefore dead
code today, for every Office, not just Assassin. `resolve_office_
holder()` is still called live (correct on its own terms, matches the
disassembly's own live `titchar[Assassin]` read at both interception
and resolution time), but a turn's tie-break can't actually favor last
turn's settled titleholder until that separate, pre-existing gap is
closed -- explicitly out of scope here, not silently worked around.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from ak_engine.models.enums import Ability
from ak_engine.models.game_state import GameState
from ak_engine.models.office import Office
from ak_engine.turn.discovery_effects import effective_skill_level
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
    melee_skill = effective_skill_level(state, target, Ability.MELEE)
    base_chance = grandfather_of_assassins_base_success_chance(army_count, melee_skill)
    effective_chance = base_chance * (0.5**target.assassination_guild_attempts)

    succeeded = rng.random() < effective_chance
    target.assassination_guild_attempts += 1
    if succeeded:
        state.remove_leader(target_leader_id)

    return GrandfatherOfAssassinsAttemptResult(
        titleholder_leader_id=holder.leader_id,
        target_leader_id=target_leader_id,
        success_chance=effective_chance,
        succeeded=succeeded,
    )


@dataclass(slots=True, frozen=True)
class GuildAssassinationOutcome:
    """One turn's own resolution of ``GameState.pending_guild_target``
    (Phase 614) -- the real phase-5 entry point
    ``resolve_pending_guild_assassination()`` returns, for
    ``orchestrator.py``/``report/turn_report.py`` to narrate.

    ``already_dead=True`` (``attempt=None``) is `AK.EXE`'s own "dead and
    buried" branch (``ILLEG.X2`` record 91) -- the queued target was
    removed from play by something else entirely (any other death this
    same turn) before phase-5 resolution ever ran; no guard-counter
    increment happens in this case, matching the disassembly exactly.
    """

    target_leader_id: int
    already_dead: bool
    attempt: GrandfatherOfAssassinsAttemptResult | None


def resolve_pending_guild_assassination(
    state: GameState, rng: random.Random | None = None
) -> GuildAssassinationOutcome | None:
    """The real phase-5-after-battles resolution of one turn's own
    Grandfather of Assassins attempt (Phase 614) -- see module docstring
    for the full derivation. Returns ``None`` and mutates nothing if
    ``state.pending_guild_target is None`` (no ``FI`` interception
    queued one this turn). Otherwise **always** clears ``state.
    pending_guild_target`` back to ``None`` before returning, whichever
    branch below fires -- ``AK.EXE:0x17851``'s own reset-at-turn-start
    is functionally equivalent to clearing it here at the end of the
    turn it was set in, since nothing reads it in between.
    """

    target_leader_id = state.pending_guild_target
    if target_leader_id is None:
        return None
    state.pending_guild_target = None

    if target_leader_id not in state.leaders:
        return GuildAssassinationOutcome(target_leader_id=target_leader_id, already_dead=True, attempt=None)

    attempt = resolve_grandfather_of_assassins_attempt(state, target_leader_id, rng)
    return GuildAssassinationOutcome(target_leader_id=target_leader_id, already_dead=False, attempt=attempt)
