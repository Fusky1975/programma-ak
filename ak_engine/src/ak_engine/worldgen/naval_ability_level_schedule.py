"""Naval Ability Level Schedule (Phase 787): ``AKGEN.EXE``'s own build of
``spabord[Naval]`` (``CTBOTH.PAS``, ``array[Ability, 1..6] of
AdvancedAbility``) -- which Advanced Ability a Naval character is granted
at each of skill levels 5-10, per game.

Source: ``AKGEN_reverse_engineering_report (3).md``'s own "Dossier
aggiuntivo: talento NAVAL" (sections 104-105).

**SS105 -- the real per-game ``spabord[Naval]`` template.** ``AKGEN.EXE:
0x60500``'s own compiled template (source order 1-6): ``[17, 13, 16, 13,
15, 13]`` -- i.e. ``NAVAL_LONG_DEFEND, NAVAL_MASTERY_GREAT_15, NAVAL_
COMBINED_ARMS, NAVAL_MASTERY_GREAT_15, NAVAL_HUG_COASTLINE, NAVAL_
MASTERY_GREAT_15`` in this project's own ``AdvancedAbility`` vocabulary.
The editorial ``SA.X2`` catalog's own ids 12/14 (Mastery +10%/+20%) never
actually occur in the real template; id 13 (+15%) occurs three times.

**Algorithm, empirically verified, not taken on the document's own word**:
its own text claims Naval "applica lo stesso algoritmo gia' ricostruito
per Explorer" (the same cumulative-``tries``, 32000-range algorithm
``explorer_ability_level_schedule.py`` already established), distinct
from the reset-per-source/32768 algorithm ``special_ability_level_
schedule.py``'s own magic-college preamble already uses for Naval's own
RNG-consumption-only role there. Since that same "textually uniform
algorithm" claim was already shown wrong once for the magic colleges, this
was re-derived empirically instead of trusted: a scratch script (seed
``50*game_number``, discard 3, one anonymous cumulative/32000 build for
``TACTICAL`` -- content-irrelevant, RNG-consumption only -- then a
cumulative/32000 build for ``NAVAL`` itself) reproduces **both** GW3 and
GW900's own full 6-level results **exactly**:

- **GW3**: L5 Naval Long Defend, L6 Naval Mastery +15%, L7 Naval Combined
  Arms, L8 Naval Mastery +15%, L9 Naval Mastery +15%, L10 Naval Hug
  Coastline.
- **GW900**: L5 Naval Long Defend, L6 Naval Mastery +15%, L7 Naval
  Mastery +15%, L8 Naval Combined Arms, L9 Naval Mastery +15%, L10 Naval
  Hug Coastline.

The alternative (reset-per-source/32768, the style already used elsewhere
in this project) only reproduces GW900, not GW3. A brute-force check of
all 4 combinations of {generic/32768, cumulative/32000} for TACTICAL x
NAVAL found the cumulative/32000-for-both combination uniquely matches
both games; every other combination matches at most one.

**SS104 -- ``SA_Num``/``SA_Mod``: duplicate Advanced Ability grants sum,
not max.** The real engine's ``SA_Num(leader, id)`` counts how many
spabord slots up to the leader's own current skill level hold a matching
id, and ``SA_Mod`` sums ``15 * count`` for Naval Mastery -- so a leader
who unlocks all 3 of the template's own ``NAVAL_MASTERY_GREAT_15`` slots
(as both GW3 and GW900 do) gets a real **+45%** strength bonus, not
+15% (**2026-11-26: now modeled** -- ``AdvancedAbilities`` counts the slots and ``_mastery_bonus_for()`` sums them;
the paragraph below is the older, superseded scoping). This directly contradicts ``turn/battle_orchestrator.py
_mastery_bonus_for()``'s own already-shipped assumption ("the three tiers
of one category never stack") and its use of ``max()`` over held tiers.

**User-confirmed scope**: ship the real per-game Naval template as data
and wire it into runtime granting too (see ``turn/move_execution.py``),
accepting that ``LeaderState.advanced_abilities`` being a plain
``set[AdvancedAbility]`` collapses the 3 duplicate ``NAVAL_MASTERY_
GREAT_15`` slots into one membership flag -- a leader who reaches Naval
skill 9 under this schedule is granted the ability for real (an
improvement over granting nothing at all), but ``_mastery_bonus_for()``
still computes at most +15%, not the real +45%. The full ``SA_Num``/
``SA_Mod`` fix (moving ``advanced_abilities`` to something that can hold
multiplicities, and summing rather than maxing in ``_mastery_bonus_
for()``) is a materially larger, separate data-model change -- not
attempted this phase, flagged for a future one.
"""

from __future__ import annotations

from ak_engine.models.advanced_ability import AdvancedAbility
from ak_engine.models.enums import Ability
from ak_engine.worldgen.pascal_random import PascalRandom
from ak_engine.worldgen.special_ability_level_schedule import (
    INITIAL_DISCARDED_IRAND_CALLS,
    LEVEL_SLOTS,
)

# Naval's own call site, empirically confirmed to match Explorer's own
# cumulative/32000 style (see module docstring), not the magic-college
# reset/32768 style.
IRAND_RANGE_NAVAL = 32000

# `AKGEN_reverse_engineering_report (3).md` SS105's own real
# `spabord[Naval]` template, source order 1-6 (raw `AKGEN.EXE: 0x60500`).
NAVAL_TEMPLATE: tuple[AdvancedAbility, ...] = (
    AdvancedAbility.NAVAL_LONG_DEFEND,
    AdvancedAbility.NAVAL_MASTERY_GREAT_15,
    AdvancedAbility.NAVAL_COMBINED_ARMS,
    AdvancedAbility.NAVAL_MASTERY_GREAT_15,
    AdvancedAbility.NAVAL_HUG_COASTLINE,
    AdvancedAbility.NAVAL_MASTERY_GREAT_15,
)

# The abilities built (and so consuming real IRand calls) before NAVAL in
# `Ability`'s own real CTBOTH.PAS declaration order -- `MARCH` excluded
# (confirmed zero-cost, see special_ability_level_schedule.py). Reduces to
# just `TACTICAL`; its own content is unknown and irrelevant here, only
# how many IRand calls its build consumes matters.
_ABILITIES_BEFORE_NAVAL: tuple[Ability, ...] = tuple(
    ability
    for ability in tuple(Ability)[: tuple(Ability).index(Ability.NAVAL)]
    if ability is not Ability.MARCH
)


def _irand_32000(rng: PascalRandom) -> int:
    """Naval's own call site: ``Trunc(Random * 32000)`` -- distinct from
    the standard 32768-range ``IRand`` (see module docstring)."""

    return int(rng.random() * IRAND_RANGE_NAVAL)


def _run_cumulative_selection(rng: PascalRandom) -> dict[int, int]:
    """Naval's own build algorithm: ``tries`` starts at 3 once per
    *ability* (not reset per source) and grows cumulatively across all 6
    sources' own collisions/retries -- identical shape to Explorer's own
    ``_run_cumulative_selection``, duplicated here per this project's own
    "small, duplicated per-consumer" convention.
    """

    occupied: set[int] = set()
    dest_of_s: dict[int, int] = {}
    tries = 3
    for s in range(1, 7):
        while True:
            n = min(20, tries // 2 + (s + 1) // 2)
            dest = 1 + _irand_32000(rng) % n
            if dest > 6 or dest in occupied:
                tries += 1
                continue
            break
        occupied.add(dest)
        dest_of_s[s] = dest
    return dest_of_s


def build_naval_ability_level_schedule(game_number: int) -> dict[int, AdvancedAbility]:
    """The real, per-``game_number`` ``spabord[Naval]`` level assignment
    -- ``{level (5..10): AdvancedAbility}``. Verified exactly against both
    the GW3 and GW900 worked examples (see module docstring).
    """

    rng = PascalRandom(seed=(50 * game_number) % 2**32)
    for _ in range(INITIAL_DISCARDED_IRAND_CALLS):
        rng.irand()

    for _ in _ABILITIES_BEFORE_NAVAL:
        _run_cumulative_selection(rng)

    dest_of_s = _run_cumulative_selection(rng)
    return {LEVEL_SLOTS[dest - 1]: NAVAL_TEMPLATE[s - 1] for s, dest in dest_of_s.items()}
