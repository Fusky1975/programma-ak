"""March Ability Level Schedule (Phase 901): ``AKGEN.EXE``'s own build of
``spabord[March]`` -- which Advanced Ability a March character is
granted at each of skill levels 5-10, per game.

**The one category with no per-game variation at all.** Every sibling
schedule module (``naval_``/``explorer_``/``tactical_``/``archery_``/
``melee_``/``druid_``/``thief_``/``sage_``/``spy_ability_level_
schedule.py``, plus the 5 magic colleges in ``special_ability_level_
schedule.py``) replays a real, seeded RNG stream to decide which raw
source item lands on which level. ``Ability.MARCH`` (``Ability`` ordinal
1) is the one confirmed exception to that whole mechanism: ``special_
ability_level_schedule.py``'s own ``_run_cumulative_selection()``-style
builders all special-case it as ``slot := j`` (source position ``j``
*is* destination slot ``j``, no draw, no retry, no ``IRand`` consumed at
all) -- already established and relied on by every sibling module's own
"abilities built before X" skip-count (each one explicitly excludes
``MARCH`` from that count, "confirmed zero-cost"). A zero-cost, fixed
identity mapping means the resulting level assignment is the same in
every real game, independent of ``game_number`` -- there is nothing here
for a seed to vary.

**Real template, source order 1-6** (``models/advanced_ability.py
ADVANCED_ABILITY_POOL[Ability.MARCH]``, Phase 357/768, ``Desktop/
PROGRAMMA AK/MARCH.md``'s own byte-level template, raw
``0x604FA-0x604FF = 08 07 06 07 06 07``): ``MARCH_THROUGH_FLOODS,
MARCH_CAVALRY, MARCH_INFANTRY, MARCH_CAVALRY_MASTERY, MARCH_INFANTRY_
MASTERY, MARCH_CAVALRY_TRUE_MASTERY`` -- Cavalry's own effect id occurs
3 times (not 2, unlike Infantry), the real 6th slot Phase 768 confirmed
directly from the disassembly. Since ``slot := j`` is the identity
mapping, this is *already* the real level-5-through-10 order -- no
redistribution needed, unlike every other category.

**Closes a real gap, not merely a missing module**: ``turn/move_
execution.py``'s own Phase 768 Move-triggered March/Naval experience
credit (the *only* real, reachable trigger for either ability's
``AdvancedAbility`` grant, since Phase 644/787 routed Practice away from
raising either skill personally) already computes a March skill rise
identically to a Naval one, but its own grant branch only ever checked
``move_experience_ability is Ability.NAVAL`` -- March's own identical
rise never granted anything, not because the mechanism doesn't apply
(it's the same code path) but because nobody had built this module yet
to call. See that function's own Phase 901 addendum for the fix.
"""

from __future__ import annotations

from ak_engine.models.advanced_ability import AdvancedAbility
from ak_engine.worldgen.special_ability_level_schedule import LEVEL_SLOTS

# `models/advanced_ability.py ADVANCED_ABILITY_POOL[Ability.MARCH]`'s own
# real source order -- already the real level order too, since March's
# own build is the identity mapping `slot := j` (see module docstring).
MARCH_TEMPLATE: tuple[AdvancedAbility, ...] = (
    AdvancedAbility.MARCH_THROUGH_FLOODS,
    AdvancedAbility.MARCH_CAVALRY,
    AdvancedAbility.MARCH_INFANTRY,
    AdvancedAbility.MARCH_CAVALRY_MASTERY,
    AdvancedAbility.MARCH_INFANTRY_MASTERY,
    AdvancedAbility.MARCH_CAVALRY_TRUE_MASTERY,
)


def build_march_ability_level_schedule(game_number: int) -> dict[int, AdvancedAbility]:
    """The real ``spabord[March]`` level assignment -- ``{level (5..10):
    AdvancedAbility}``. ``game_number`` is accepted, but unused, purely
    for call-site parity with every sibling ``build_*_ability_level_
    schedule()`` -- see module docstring for why March's own real
    assignment never varies from one game to the next.
    """

    return {level: ability for level, ability in zip(LEVEL_SLOTS, MARCH_TEMPLATE)}
