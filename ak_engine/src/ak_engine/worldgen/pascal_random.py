"""Turbo Pascal 6.0-compatible pseudo-random number generator (Phase 352).

The first phase of a new sub-plan porting ``AKGEN.EXE``'s own world
generator (a static reverse engineering, distinct from Phase 346-351's
own ``AK.EXE``/``AK.OVR`` runtime battle resolver) -- see
``ak_engine/README.md`` for the full 10-phase plan this opens.

Several later phases (feature generation, initial-army budgets, hero
talent/aptitude rolls) all draw from the *same* underlying linear
congruential generator the real DOS executable used, so this phase
builds that primitive first, standalone, rather than re-deriving it in
each later consumer.

**Confirmed exactly** from the disassembly (``world_generation.
hero_talents_and_aptitudes.rng`` in the source JSON):

- State transition: ``RandSeed = (RandSeed * 134775813 + 1) mod 2**32``
  -- ``134775813`` is ``0x8088405``, the real, historically documented
  multiplier Borland's own Turbo Pascal runtime used for ``Random``
  (not a value this project invented or guessed).
- ``IRand`` (the game's own custom "give me an integer" wrapper, not
  Pascal's built-in parameterized ``Random(n)``): steps the state once,
  then returns ``trunc(Random * 32768)`` where ``Random`` is the
  state's own real-valued interpretation (``RandSeed / 2**32``) *after*
  that step -- i.e. every ``IRand`` call both advances and consumes the
  generator, matching every other real ``random.Random``-based RNG
  already used throughout this project (nothing here is peeked without
  being consumed). Every real caller quoted in the source further
  reduces this 0..32767 value with its own ``mod``/``AND`` (e.g.
  ``IRand mod 60`` for monster proposal, ``IRand AND 7`` for the
  recruit-slot gate) -- ``irand()`` below returns the raw 0..32767
  value; callers apply their own reduction, matching the source's own
  layering rather than baking a single caller's reduction in here.

**What's deliberately NOT implemented here**: the real startup seed
(DOS ``INT 21h``/``AH=2Ch`` clock words -- hour/minute/second/
hundredth) that seeds hero-talent generation specifically. The source
confirms *that* it's clock-derived (and therefore not reproducible from
``game_number``, an explicitly stated real consequence -- "hero skills/
aptitudes are clock-seeded and are not determined by game_number"), but
does not give the exact bit-packing formula combining the four clock
words into one 32-bit seed, so guessing one would be exactly the kind
of unsourced invention this project avoids. Callers needing a
reproducible seed (e.g. testing, or the source's own *separately*
confirmed ``RandSeed = (50 * game_number) mod 2**32`` reseed used for
special-ability selection elsewhere in the source, a later phase's own
concern) pass one explicitly to ``PascalRandom.__init__``.

**Verification**: no known-seed/known-output trace from the real
binary is available in the source material to check byte-exact
reproduction against, so this isn't tested that way. What *is* tested:
the state transition is deterministic and repeatable for a given seed
(two generators seeded identically produce identical sequences), and a
large-sample Monte Carlo of ``irand()`` lands close to the expected
uniform mean and range -- the same empirical bar this project already
applies to its own ``random.Random``-based dice-roll formulas
elsewhere, not a claim of matching the original DOS executable's own
literal output stream.
"""

from __future__ import annotations

MODULUS = 2**32
MULTIPLIER = 134775813
INCREMENT = 1
IRAND_RANGE = 32768
# Phase 679 -- `Desktop/NOARMY.md`'s own targeted disassembly of `AK.EXE`'s
# resident `IRand` (`35EB:11D4`, a separate executable/address from the
# `AKGEN.EXE` disassembly `IRAND_RANGE` above is sourced from) confirms a
# real, genuinely different compiled Real48 constant: 32000, not 32768.
# Both are correct for their own executable -- not a contradiction to
# resolve either way, confirmed by checking every `turn/` module's own
# "IRand" comment first: none of them implement a byte-exact LCG at all
# (every `turn/` dice roll uses an ordinary `random.Random` reduction
# matching the Pascal formula's statistical shape, not a literal port) --
# `turn/monster_raids.py resolve_monster_raid_reply()` is the first `AK.EXE`
# -side mechanic confirmed to need byte-exact, deterministic-per-entity
# reproduction, so this is a new, additive constant, not a correction to
# the existing `AKGEN.EXE`-scoped `IRAND_RANGE` above.
AK_RUNTIME_IRAND_RANGE = 32000


class PascalRandom:
    """One Turbo Pascal-compatible ``RandSeed`` stream."""

    __slots__ = ("state",)

    def __init__(self, seed: int) -> None:
        self.state = seed % MODULUS

    def _step(self) -> int:
        self.state = (self.state * MULTIPLIER + INCREMENT) % MODULUS
        return self.state

    def random(self) -> float:
        """The real-valued ``Random`` -- ``RandSeed / 2**32`` after one step, in ``[0, 1)``."""

        return self._step() / MODULUS

    def irand(self, *, irand_range: int = IRAND_RANGE) -> int:
        """``IRand``: ``trunc(Random * irand_range)``, in ``[0, irand_range)``.

        Callers reduce this further with their own ``mod``/``AND`` mask
        (e.g. ``irand() % 60`` for a 1-in-60 monster draw) -- this
        function does not apply any caller-specific reduction itself.
        Defaults to ``IRAND_RANGE`` (32768, `AKGEN.EXE`'s own confirmed
        constant); pass ``irand_range=AK_RUNTIME_IRAND_RANGE`` for an
        `AK.EXE`-side mechanic instead -- see that constant's own
        Phase 679 comment above for why the two are genuinely different,
        not a bug in either.
        """

        return int(self.random() * irand_range)
