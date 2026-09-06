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
  then returns ``trunc(Random * IRAND_RANGE)`` where ``Random`` is the
  state's own real-valued interpretation (``RandSeed / 2**32``) *after*
  that step -- i.e. every ``IRand`` call both advances and consumes the
  generator, matching every other real ``random.Random``-based RNG
  already used throughout this project (nothing here is peeked without
  being consumed). Every real caller quoted in the source further
  reduces this value with its own ``mod``/``AND`` (e.g. ``IRand mod 60``
  for monster proposal, ``IRand AND 7`` for the recruit-slot gate) --
  ``irand()`` below returns the raw ``0..IRAND_RANGE-1`` value; callers
  apply their own reduction, matching the source's own layering rather
  than baking a single caller's reduction in here.
- **Phase 755 investigation (kept at 32768, not changed)**: ``Desktop/
  AKGEN 0xEB8A.md`` (2026-09-06) disassembles what it presents as this
  same shared ``IRand`` helper at the *identical* address
  (``AKGEN_embedded_catalogs.json.txt``'s own ``hero_talents_and_
  aptitudes.rng`` entry gives ``IRand_file_offset = 0x53E70``; the new
  document gives ``raw 0x53E70-0x53EA6``) and reads the register values
  loading the Real48 divisor as ``(CX,SI,DI) = (008Fh,0000h,7A00h)``,
  which decode (Turbo Pascal Real48: a biased-129 exponent byte plus a
  39-bit mantissa with an implicit leading ``1``) to exactly ``32000.0``,
  not ``32768.0`` -- independently re-derived and verified by hand this
  session (``CX``'s low byte ``0x8F`` = exponent 143 -> base
  ``2**14 = 16384``; ``32000/16384 = 1.953125``, whose fractional part
  encodes to mantissa top byte ``0x7A``, an exact match for ``DI``'s
  high byte; a bare power of two like ``32768`` would need an all-zero
  mantissa instead, as this same document's own ``2.0`` example
  confirms). **This byte-level decoding is internally sound, but
  contradicts real, existing evidence and was NOT applied**:
  ``worldgen/special_ability_level_schedule.py`` already has a
  byte-for-byte cross-check against the real ``GW900`` save file's own
  confirmed ``spabord`` table (``test_build_magic_ability_level_
  schedule_matches_the_real_game_900_example_exactly``), built on this
  exact ``irand()`` default -- switching ``IRAND_RANGE`` to 32000 breaks
  that empirical, ground-truth match, while 32768 reproduces it exactly.
  Between a hand-decoded register value from an unvalidated document and
  a working byte-exact match against a real historical game file, the
  latter wins: ``IRAND_RANGE`` stays ``32768``. This may mean the two
  documents' address citations don't actually refer to the same physical
  routine despite matching hex digits (a plausible mislabeling between a
  raw/linear address and a segment:offset one), or that ``AKGEN.EXE``
  genuinely has more than one ``IRand``-shaped helper. Flagged as a
  real, unresolved discrepancy for a future investigation, not silently
  dropped -- do not change this constant again without either a second,
  independent confirmation of ``32000`` or an explanation for why the
  ``GW900`` schedule still matches under it.

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
# Phase 755 -- `Desktop/AKGEN 0xEB8A.md` proposed correcting this to 32000
# (see the module docstring's own "Phase 755 investigation" paragraph
# above) -- investigated and NOT applied: it breaks the real, byte-exact
# GW900 cross-check in `special_ability_level_schedule.py`. Kept at 32768.
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
        constant -- Phase 755 investigated a 32000 correction and
        rejected it, see that constant's own comment above); pass
        ``irand_range=AK_RUNTIME_IRAND_RANGE`` for an
        `AK.EXE`-side mechanic instead -- see that constant's own
        Phase 679 comment above for why the two are genuinely different,
        not a bug in either.
        """

        return int(self.random() * irand_range)
