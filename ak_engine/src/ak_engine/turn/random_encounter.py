"""Phase 707 -- random-encounter generator primitives.

Sourced from ``Desktop\\CASUALENCOUNTER.md`` (user-supplied, 2026-09-01,
a disassembly-level reverse-engineering of ``AK.EXE``'s random-encounter
routine, mostly CERTO-graded). After a leader performs Move, Explore,
Search, Pursue, or Trail, the real game rolls a per-terrain chance of a
random encounter with either a reskinned "patrol" or a genuine wandering
monster drawn from the full 60-species table, using a real, non-uniform
weighting formula. This closes a real, previously-confirmed-genuinely-
blocked gap: ``AdvancedAbility.SENSE_DANGER_TALENT``'s own "random
encounters" clause (``turn/challenge_execution.py``, Phase 706) was left
explicitly unmodeled because no random-encounter-generation mechanism
existed anywhere in this project.

**This module is primitives only** -- every function here is pure (reads
``GameState``/``LeaderState``/``ActionPlan`` but never mutates them,
consumes only the caller-supplied ``rng``) and **nothing here is wired
into turn dispatch yet**. Matches this project's own established
"primitives now, wiring later" precedent (Feature->Power Phase 616 vs.
622/623; the Special Encounter Plan roadmap's own Phase A/659 vs.
B/669). Two real, still-open follow-ups, not attempted here:

- **Phase 708**: wiring these primitives into ``turn/plan_dispatch.py
  run_leader_plan()``'s own per-phase loop for the 5 real action types,
  a lightweight ephemeral synthetic-monster representation (the real
  game's own ``maxfeatures+256`` sentinel Feature slot has no
  precedent anywhere in this codebase -- every ``Feature`` here is a
  real, ``GameState.features``-indexed, serialized entity), and
  combat-engine integration (a leader driven by their own real Special
  Encounter Plan vs. a bare ``Monster`` driven by its own generated
  tactic plan -- no single existing engine resolves that combination
  today; ``turn/challenge_execution.py resolve_challenge_combat()``
  only knows decoded ``SearchTactic`` lists on both sides, and
  ``turn/search_execution.py``'s own monster-plan generator always
  requires a real, persisted ``Feature``). This is also where Sense
  Danger Talent's own "random encounters" clause finally closes.
- **Phase 709**: the full pre-combat outcome tree (``approach_score``,
  the 8 named branches -- pass-by/befriend/teach-a-skill/donate-gold/
  reveal-a-feature/nice-chat/friendly-greeting) and report-layer
  wiring, including the already-built-but-unwired ``report/turn_
  report.py render_wandering_encounter()``/``render_patrol_release()``/
  ``render_patrol_encounter()`` (Phase 106/107).

**Two genuinely unrecoverable Pascal internals, user-confirmed
directly rather than guessed** (the document's own field/variable
names for these two comparisons don't survive in any available
source):

1. **Patrol diplomatic safety** (``rel + Rand2 >= 2``, real values
   Enemy=0%/Neutral=50%/Allied=100%/Teamed=100%): this project only
   models a binary ``GameState.is_allied()`` -- no separate Enemy/
   Neutral/Teamed states exist anywhere real (``turn/diplomatic_
   merit.py`` already documents this same simplification for an
   unrelated mechanic). Mapped as: allied -> Allied(2), always safe;
   otherwise -> Neutral(1), 50% via a coin flip -- **not** "not allied
   = Enemy = never safe." Matches the rulebook's own "twice as safe"
   framing the document itself quotes (a 2x ratio between friendly and
   neutral territory, not a 0%-vs-100% cliff), and this project has no
   separate "declared enemy" concept anywhere to justify the harsher
   reading.
2. **The "traveling with an army" escort exclusion** (document SS4.3,
   Move/Pursue/Trail only): approximated as "another leader of the
   *same Kingdom* who currently commands at least one army standing at
   the same destination coordinate" -- narrower/safer than a raw "any
   leader, any kingdom" reading.

**RNG source**: the document's own ``Rand100``/``Rand2``/``IRand``/
``RandomReal`` calls are never described as reseeded or deterministic-
per-entity (unlike ``turn/monster_raids.py resolve_monster_raid_
reply()``'s own confirmed exception, Phase 679, which resolves a
guardian-monster's dialogue reply from a fresh ``PascalRandom`` seeded
per ``(monster, feature)`` pair) -- so every function here consumes the
turn's ordinary live ``rng: random.Random``, matching every other dice
roll in this project outside that one documented exception. ``Rand2``/
``Rand100`` port as ``int(rng.random() * 2)``/``int(rng.random() *
100)`` (exact ``Trunc`` semantics, not ``round``); ``IRand mod N``
ports as ``int(rng.random() * N)`` rather than ``rng.randrange(N)`` --
uniform, statistically equivalent to the real routine's own reduction,
not a bit-exact port (the same "ordinary ``random.Random`` reduction
matching the Pascal formula's statistical shape" convention already
used throughout ``turn/`` outside ``monster_raids.py``'s own documented
exception). Using ``.random()`` alone rather than ``.randrange()``
also keeps every draw here controllable via this project's own
established ``ScriptedRandom`` test convention (``tests/_helpers.py``),
which only overrides ``.random()``/``.choice()``.

**Terrain scope**: this project's own ``models/map.py Terrain`` enum
has exactly 7 members (``PLAINS``, ``DESERT``, ``JUNGLE``, ``FOREST``,
``MTNS``, ``SEA``, ``NO_TERRAIN``) -- matching the document's own first
7 ``renc`` entries exactly. Swamp/Lava/extension terrains don't exist
anywhere in this project (``map.py``'s own docstring: "omitted here: no
game data or consumer"). The habitat band that names Swamp (habitat
code >=29, "Sea, No Terrain, or Swamp") is applied only to whichever of
those three real values exist here (Sea, No Terrain) -- Swamp dropped
since it's structurally unreachable in this codebase, not a guess.
"""

from __future__ import annotations

import random

from ak_engine.models.enums import ActionCode
from ak_engine.models.game_state import GameState, LeaderState
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.monster import MONSTER_RUNTIME_PROFILE, Monster
from ak_engine.models.plan import ActionPlan

# CASUALENCOUNTER.md SS5: `renc` -- per-terrain success threshold out of
# 100 (`Rand100 < renc[terrain]`). Only the 7 real `Terrain` members
# this project models are represented (see module docstring).
RENC_BY_TERRAIN: dict[Terrain, int] = {
    Terrain.PLAINS: 10,
    Terrain.DESERT: 15,
    Terrain.JUNGLE: 25,
    Terrain.FOREST: 20,
    Terrain.MTNS: 15,
    Terrain.SEA: 5,
    Terrain.NO_TERRAIN: 0,
}

# CASUALENCOUNTER.md SS9.2/SS15 -- `hab_lo`/`hab_hi`, indexed by
# `Monster.value` (0..59), transcribed verbatim from the document's own
# Python reference tables.
HAB_LO: tuple[int, ...] = (
    15, 15, 21, 15, 15, 0, 0, 0, 10, 10, 0, 10, 15, 15, 15, 0, 0, 0, 0, 0,
    0, 0, 23, 23, 10, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 8, 23, 23, 15, 15, 15, 15, 15, 0, 0, 0, 0, 0, 0, 27, 27, 27, 27, 27,
)

HAB_HI: tuple[int, ...] = (
    26, 26, 22, 26, 20, 9, 9, 9, 22, 22, 26, 14, 26, 26, 26, 26, 26, 26, 26, 26,
    26, 26, 25, 25, 14, 22, 22, 25, 26, 7, 7, 7, 7, 7, 7, 7, 26, 25, 25, 25,
    26, 9, 25, 25, 25, 25, 25, 25, 25, 3, 3, 3, 3, 3, 3, 30, 30, 30, 30, 30,
)

# CASUALENCOUNTER.md SS8: the humanoid generator's own base species
# ("Ord(Archer)").
HUMANOID_GENERATOR_BASE = Monster.ARCHER

# CASUALENCOUNTER.md SS9.1: a defensive cap on the general generator's
# own rejection-sampling loop -- documented as never actually reached,
# since every real terrain admits at least one habitat band (the two
# wildcard bands, habitat <=18 or 27-28, accept any terrain at all).
_GENERAL_GENERATOR_MAX_ATTEMPTS = 10_000

# CASUALENCOUNTER.md SS4.4: the 5 forbidden ActionCode ordinals that
# exempt a leader from random encounters if found anywhere in their
# full annual plan (not just the current phase).
_FORBIDDEN_PLAN_ACTIONS = frozenset(
    {ActionCode.PICK_UP, ActionCode.LEAVE, ActionCode.RECRUIT, ActionCode.DEFEND, ActionCode.DISBAND}
)


def terrain_roll(terrain: Terrain, rng: random.Random) -> bool:
    """CASUALENCOUNTER.md SS5: ``Rand100 < renc[terrain]``. The fail
    boundary is inclusive on the high side -- with a threshold of 10,
    the only successes are 0..9.
    """

    return int(rng.random() * 100) < RENC_BY_TERRAIN.get(terrain, 0)


def habitat_accepts(habitat_code: int, terrain: Terrain) -> bool:
    """CASUALENCOUNTER.md SS9.2's own habitat-band-to-terrain mapping.
    See module docstring for why the Swamp-naming ``>=29`` band is
    narrowed to ``{SEA, NO_TERRAIN}`` in this project.
    """

    if habitat_code >= 29:
        return terrain in (Terrain.SEA, Terrain.NO_TERRAIN)
    if habitat_code <= 18 or 27 <= habitat_code <= 28:
        return True
    if habitat_code <= 20:
        return terrain is Terrain.DESERT
    if habitat_code <= 22:
        return terrain is Terrain.JUNGLE
    if habitat_code <= 24:
        return terrain is Terrain.FOREST
    return terrain is Terrain.MTNS


def select_humanoid_monster(rng: random.Random) -> Monster:
    """CASUALENCOUNTER.md SS8: ``Ord(Archer) + (IRand mod 5) * Rand2 +
    Rand2`` -- the two ``Rand2`` calls are independent (confirmed by
    the document directly). Draw order: ``IRand mod 5``, then the
    multiplier ``Rand2``, then the additive ``Rand2``. ``IRand mod N``
    ports as ``int(rng.random() * N)`` rather than ``rng.randrange(N)``
    -- see module docstring's own RNG-source note (this also keeps every
    draw here controllable via a plain ``.random()`` script, matching
    this project's own established ``ScriptedRandom`` test convention,
    which only overrides ``.random()``/``.choice()``, not ``.randrange()``).
    """

    offset = int(rng.random() * 5) * int(rng.random() * 2) + int(rng.random() * 2)
    return Monster(HUMANOID_GENERATOR_BASE.value + offset)


def select_general_monster(terrain: Terrain, rng: random.Random) -> Monster:
    """CASUALENCOUNTER.md SS9.1-9.2: rejection-sampling loop over the
    full 60-species table. Proposes a uniform species, accepts it with
    probability ``100 / HP^2`` (so low-HP species are far more likely),
    then draws a habitat position and accepts only if it matches
    ``terrain``; otherwise the whole proposal (species, HP roll, and
    habitat roll) redraws from scratch.
    """

    for _ in range(_GENERAL_GENERATOR_MAX_ATTEMPTS):
        candidate = Monster(int(rng.random() * 60))
        hp = MONSTER_RUNTIME_PROFILE[candidate].average_hit_points
        if rng.random() >= 100.0 / (hp**2):
            continue
        lo, hi = HAB_LO[candidate.value], HAB_HI[candidate.value]
        habitat = lo + int(rng.random() * (hi - lo))
        if habitat_accepts(habitat, terrain):
            return candidate
    raise RuntimeError("select_general_monster: no candidate accepted -- should be unreachable")


def select_random_monster(terrain: Terrain, rng: random.Random) -> Monster:
    """CASUALENCOUNTER.md SS7: a single 50/50 coin picks the humanoid
    generator or the general generator; a rejection inside the general
    generator's own loop never re-flips this coin.
    """

    if int(rng.random() * 2) == 1:
        return select_humanoid_monster(rng)
    return select_general_monster(terrain, rng)


def is_humanoid_species(monster: Monster) -> bool:
    """CASUALENCOUNTER.md SS10: ``Humanoid_Opponent`` -- Giant..Witch (12..21)."""

    return Monster.GIANT.value <= monster.value <= Monster.WITCH.value


def is_patrol_framing(visitor_leader_id: int, turn_number: int, monster: Monster) -> bool:
    """CASUALENCOUNTER.md SS10: ``((visitor + gameturn) and 1) = 1`` and the
    monster is humanoid -- decides whether this encounter is narrated as
    a patrol or a wandering-monster episode.
    """

    return (visitor_leader_id + turn_number) % 2 == 1 and is_humanoid_species(monster)


def patrol_evades_via_diplomacy(
    state: GameState, visitor_kingdom_id: int, province_owner_kingdom_id: int, rng: random.Random
) -> bool:
    """CASUALENCOUNTER.md SS10.1: ``rel + Rand2 >= 2``. See module docstring
    for the user-confirmed Allied/Neutral mapping onto this project's own
    binary ``is_allied()``.
    """

    if state.is_allied(visitor_kingdom_id, province_owner_kingdom_id):
        return True
    return int(rng.random() * 2) == 1


def random_encounter_gate_open(state: GameState) -> bool:
    """CASUALENCOUNTER.md SS3: ``gameturn - admin_turn_flag > 1``. This
    project has no ``admin_turn_flag``/catch-up-turn concept anywhere
    (confirmed by grep) -- it is always 0 in every real game this
    project processes, so the real formula reduces to ``gameturn > 1``.
    """

    return state.turn_number > 1


def leader_travels_with_kingdom_army(state: GameState, leader: LeaderState, coord: HexCoord) -> bool:
    """CASUALENCOUNTER.md SS4.3's own "escort" exclusion, user-confirmed
    approximation: a loyal (same-Kingdom) army is physically present at
    ``coord``.
    """

    return any(
        army.kingdom_id == leader.kingdom_id and army.location == coord for army in state.armies.values()
    )


def leader_plan_has_forbidden_action(plan: ActionPlan) -> bool:
    """CASUALENCOUNTER.md SS4.4: scans every phase of every segment of the
    leader's own full annual plan (not just the current phase) for
    Pick Up, Leave, Recruit, Defend, or Disband.
    """

    return any(
        phase.action in _FORBIDDEN_PLAN_ACTIONS
        for segment in plan.segments
        for phase in segment.phases.values()
    )


def is_leader_eligible_for_random_encounter(
    state: GameState, leader: LeaderState, plan: ActionPlan, coord: HexCoord, *, check_escort: bool
) -> bool:
    """CASUALENCOUNTER.md SS4.2-4.4, combined in the document's own real
    order. ``check_escort`` is ``True`` only for Move/Pursue/Trail
    (``random_mode=1``); Explore/Search (``random_mode=2``) never check
    the escort exclusion at all. Every exclusion here is silent -- no
    ``_LNoRand`` narration fires for any of these, only for a failed
    terrain roll (see ``terrain_roll()``).
    """

    if leader.kingdom_id is None:
        return False
    if leader.is_king:
        return False
    if check_escort and leader_travels_with_kingdom_army(state, leader, coord):
        return False
    if leader_plan_has_forbidden_action(plan):
        return False
    if state.armies_commanded_by(leader.leader_id):
        return False
    return True
