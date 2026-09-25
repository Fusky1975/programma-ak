"""Post-battle quality changes (rulebook [7.5]).

"Armies of the winning force that did well in the battle may have their
quality increased by 1 level, although most troops will never become
Crack and very few will ever become Elite. Some armies in the losing
force will probably have their quality level decreased by 1 level,
although a defeated force that does not retreat can either improve or
decrease in quality. The chance of rising or falling in quality decreases
as armies gain in quality. A unit has less than the normal chance to
improve in quality if it is inadequately led. If it fought as a Green or
Depleted unit because of insufficient Druidic ability, it has 60% and 20%
(respectively) of the normal chance to improve."

**No numbers at all are given here** -- unlike ``win_probability``
(which at least has two anchor points), this rule is entirely
qualitative. Every constant in this module is therefore a deliberate,
unsourced design choice made to have *some* deterministic, testable
behavior, not a recovered or even approximated rule. Revisit freely;
there's nothing here to contradict.

**Phase 350 addendum**: real data has now arrived, from the same
`AK.EXE`/`AK.OVR` source as Phase 346-349's own battle-resolution
corrections. Its own confirmed formula: `base_percent = 60 >>
max(0, quality + formation_divisor - 2)` (an integer right-shift, not a
division), where `formation_divisor` is `1`/`2`/`4`/`8` for front/
second/third/fourth-and-later formation depth (`FORMATION_DIVISOR`
below) and `quality` is `Quality`'s own `0`-`5` ordinal -- verified
exactly against the source's own 4x6 worked table (e.g. front-line
Average, `60 >> max(0,2+1-2) = 60 >> 1 = 30`; third-line Elite,
`60 >> max(0,5+4-2) = 60 >> 7 = 0`). A losing, selected front-line unit
falls one level at exactly this `base_percent` (Depleted excluded --
"Depleted cannot fall"). A winning, selected unit rises one level at
`base_percent * merit_multiplier` (`MERIT_MULTIPLIER` below, keyed by
the unit's own battle-performance "score"; Elite excluded -- "Elite
cannot gain").

**Phase 372: wired into `roll_quality_change`/`turn/battle_orchestrator.py`'s
call sites.** Formation depth turned out to already be available, not
missing: `turn/battle_resolution.py BattleColumnResult.attacker_units`/
`defender_units` are ordered front-to-back lists (Phase 6's own
`assign_battle_lines`), so an army's own index in its column's list
*is* its formation depth -- `battle_orchestrator._formation_divisors()`
reads exactly that, no new state needed. `improve_chance`/
`decline_chance` below now take that `formation_divisor` and use
`base_quality_change_percent` instead of the old flat, unsourced
`BASE_QUALITY_CHANGE_CHANCE` formula -- that constant is removed
outright, not kept dead, since nothing else in the project ever needs a
from-scratch flat rate again.

**Phase 423 addendum -- `score` wired, as a documented, unconfirmed
interpretation, not a recovered formula.** The other real input, a
unit's own per-unit "merit" battle-performance `score` (used only by
the *gain* side's `quality_gain_merit_multiplier`), stayed genuinely
missing through Phase 372 -- `column_bres` was tempting (it *is* a
real, per-column performance number) but nothing in this project's
source material said the engine's own "score" reuses `BRES`.
`AKGEN_reverse_engineering_report.md`'s own battle-engine section
(re-read directly for this phase) turned out to already describe the
gain multiplier's own input, calling it `P` ("100% se il confronto
effettivo restituisce P>=0, 60% con P=-1, 20% con P=-2, 0% con
P<=-3") -- the exact same `-5..+5`-anchored thresholds
`MERIT_MULTIPLIER` already used, described immediately after that same
report's own `BRES` writeup. The report still never writes "P = BRES"
as an equation, and no raw `AK.EXE`/`AK.OVR` binary is available in
this project to disassemble further and settle it either way -- so
`turn/battle_orchestrator.py _column_bres_by_army_id()` now feeds
`column_bres` in as `score` anyway, explicitly labeled (in its own
docstring and this one) as the project's best-motivated guess at what
`P` is, not a confirmed identity. A future phase that finds a real,
sourced answer should replace it outright, not treat this as settled.
`roll_quality_change`'s `score` parameter still defaults to `0` for any
caller that doesn't pass one -- the gain formula's own documented
"score >= 0 --> multiplier 1.0" neutral case, the same "missing data
defaults to a neutral, not a guessed, value" convention this project
already uses elsewhere (see `turn/battle_orchestrator.py
_build_battle_units`'s own exploration-advantage default).

**Phase 922 addendum -- due diligence attempted on the "P = BRES"
identity; confirmed structurally unresolvable with any data this
project could ever recover, not just presently missing.** Unlike the
deterministic cross-references that closed several other README
"Known-unresolved semantics" bullets this session (Phases 915/920,
comparing two static file formats that always encode the same fixed
value), `P`/`score` is fed by the battle engine's own internal random
luck draws (`r1`/`r2`, `turn/battle_luck.py`) for one specific,
already-played historical battle. No surviving artifact -- a real
turn-report letter's prose, a `GW`-format world-save's post-battle
`Quality` field, or anything else this project parses -- records those
draws or the resulting `BRES`/`P` value itself; both are purely
internal to a single already-completed `AK.EXE` run and were never
written to any file this project's source material includes. A real
`Quality`-change narration (`DECQ.X`/`INCQ.X`) does appear in real
letters (e.g. `SE3__T2.K1`'s "the 240th Bowmen proved its mettle...
we now rate it a Veteran unit", `SE3__T11.K1`'s Trolls "severely
mangled... fallen in stature", and several more across `SE3__T3`/`T6`-
`T10`), confirming the mechanic itself fires in real games, but the
sentence only reports the
*outcome* ("we now rate it a Crack unit"), never the internal score
that decided its probability -- so even a real example changes nothing
here. The `AKGEN_reverse_engineering_report.md` this bullet's own
Phase 423 addendum already quoted for `P`'s threshold behavior is
itself not available in this project's current file set to re-read for
a possible missed "P = BRES" statement elsewhere in it; re-deriving
`P` from first principles would need the original `AK.EXE`/`AK.OVR`
binary that same addendum already says isn't available either. This
isn't a "not yet searched" gap like the Beasts/Duel bullets were before
their own due-diligence phases -- it's a "cannot be searched with any
real-game text or save file, ever" one. `column_bres` remains the
project's best-motivated stand-in for `score`, unchanged.
"""

from __future__ import annotations

import random

from ak_engine.turn.combat import Quality

# -- Phase 350: the confirmed AK.EXE/AK.OVR quality-change formula --------

FORMATION_DIVISOR = {
    "front": 1,
    "second": 2,
    "third": 4,
    "fourth_and_later": 8,
}

MERIT_MULTIPLIER = {
    0: 1.0,
    -1: 0.6,
    -2: 0.2,
}


def base_quality_change_percent(quality: Quality, formation_divisor: int) -> float:
    """`60 >> max(0, quality + formation_divisor - 2)`, as a `0.0`-`0.6`
    fraction -- see this module's own "Phase 350 addendum" for the full
    derivation and its source. `formation_divisor` is one of
    `FORMATION_DIVISOR`'s own four values, not an arbitrary int."""

    shift = max(0, int(quality) + formation_divisor - 2)
    return (60 >> shift) / 100


def quality_gain_merit_multiplier(score: int) -> float:
    """The source's own `gain_merit_multiplier`: `1.0` for a
    non-negative battle-performance score, `0.6`/`0.2` for `-1`/`-2`,
    and `0.0` (no gain at all) for `-3` or worse."""

    return MERIT_MULTIPLIER.get(min(score, 0), 0.0)

DRUID_LED_IMPROVE_MULTIPLIER: dict[Quality, float] = {
    Quality.GREEN: 0.60,
    Quality.DEPLETED: 0.20,
}


def improve_chance(quality: Quality, formation_divisor: int = FORMATION_DIVISOR["front"], *, score: int = 0) -> float:
    """Chance to rise one quality level: `base_quality_change_percent`
    scaled by `quality_gain_merit_multiplier(score)` -- zero at Elite
    ("Elite cannot gain"), regardless of `score`."""

    if quality == Quality.ELITE:
        return 0.0
    return base_quality_change_percent(quality, formation_divisor) * quality_gain_merit_multiplier(score)


def decline_chance(quality: Quality, formation_divisor: int = FORMATION_DIVISOR["front"]) -> float:
    """Chance to fall one quality level: `base_quality_change_percent`
    directly -- zero at Depleted ("Depleted cannot fall")."""

    if quality == Quality.DEPLETED:
        return 0.0
    return base_quality_change_percent(quality, formation_divisor)


def _step(quality: Quality, delta: int) -> Quality:
    level = max(int(Quality.DEPLETED), min(int(Quality.ELITE), int(quality) + delta))
    return Quality(level)


def roll_quality_change(
    quality: Quality,
    rng: random.Random,
    *,
    is_winner: bool,
    retreated: bool = False,
    led_by_insufficient_druid: bool = False,
    formation_divisor: int = FORMATION_DIVISOR["front"],
    score: int = 0,
) -> Quality:
    """Roll this unit's post-battle quality change.

    - Winners: may improve (chance reduced if ``led_by_insufficient_druid``
      and the unit fought as Green/Depleted).
    - Losers that retreated: may decline.
    - Losers that didn't retreat ("can either improve or decrease"): rolls
      both directions, decline checked first.

    ``formation_divisor`` (Phase 372) is one of ``FORMATION_DIVISOR``'s
    own four values -- which formation depth this unit fought at,
    defaulting to front-line for a caller that doesn't track it.
    ``score`` (Phase 372) only affects the *improve* side (see
    ``improve_chance``'s own docstring) -- defaulting to `0`, the
    formula's own "no reduction" case, since no real source gives this
    project a per-unit merit score to compute (see this module's own
    docstring).

    **Phase 770 -- `wargames_mastery` removed, corrected elsewhere.**
    Phase 513 added a `wargames_mastery` parameter here, doubling this
    function's own improve chance for `AdvancedAbility.TACTICAL_
    WARGAMES_MASTERY`, reasoning this was "the rulebook's own only
    'chance for a unit to increase in quality' mechanic this project
    models" -- already false when written. The ability's own real text
    says "when **Practicing** Tactics (or Naval)," not "after a
    battle," and its own worked example ("an Average unit now has a
    10% chance") only matches doubling `turn/practice_execution.py
    TACTICAL_TRAINING_CHANCE[Quality.AVERAGE] = 0.05` (-> 0.10) --
    doubling *this* function's own post-battle Average chance (30%)
    gives 60%, no match at all. The bonus now lives correctly in
    `turn/practice_execution.py _wargames_mastery_multiplier()`,
    consumed by `execute_practice_tactical()`/`_group()`. No source
    supports doubling this post-battle mechanic at all -- removed
    outright, not kept as a redundant/unsourced extra.
    """

    if is_winner:
        chance = improve_chance(quality, formation_divisor, score=score)
        if led_by_insufficient_druid:
            chance *= DRUID_LED_IMPROVE_MULTIPLIER.get(quality, 1.0)
        return _step(quality, 1) if rng.random() < chance else quality

    if retreated:
        return _step(quality, -1) if rng.random() < decline_chance(quality, formation_divisor) else quality

    decline = decline_chance(quality, formation_divisor)
    improve = improve_chance(quality, formation_divisor, score=score)
    roll = rng.random()
    if roll < decline / 2:
        return _step(quality, -1)
    if roll < decline / 2 + improve / 2:
        return _step(quality, 1)
    return quality
