"""Creating a new King from a Royal Heir (Phase 260) -- RULES.AK [2.1] "Kings".

Phase 259 wired the automatic side of King succession: when a King
dies, ``GameState.remove_leader()`` installs a Royal Heir under the
same ``leader_id`` (Phase 552: with the automatic Melee/Archery/Sage
training-bonus baseline, not fully zeroed -- see that function's own
docstring), until either a Resurrection restores the exact dead King
or the player assigns the Heir his own new skills. This module is the
second half -- the player-facing act of actually creating that new
King.

**Not a K1-decodable order.** Confirmed directly against the real
Pascal ``action`` enum (``CTBOTH.PAS``, ``models/enums.py
ActionCode``): no ordinal exists for "create a King" anywhere in it.
Unlike every other player order this project models (Move, Search,
Recruit, ...), King creation was never an ordinary per-turn Move-sheet
order in the original game -- RULES.AK's own [2.1] describes it as
happening "at the start of the game," the same one-time setup act a
Royal Heir's own creation now mirrors. There is accordingly no
parser/decode layer here: ``create_king()`` is called directly with
the player's already-decided choices (name, temper, sex, skill
distribution), the same "no real order-file shape, so no decode step"
category as ``turn/practice_execution.py execute_practice_group()``'s
own multi-character call (Phase 46's own docstring makes the same
point for a different reason).

**Phase 1193: the real call site is ``webapp/app.py leader_finalize_
royal_heir()``** -- a GM-facing form on the leader-edit page, shown
whenever ``LeaderState.is_royal_heir`` is set, collecting exactly the
player-facing choices this function needs (name, Temper, Sex, and a
4-point Talent allocation across the 15 ``Ability`` members) and
surfacing ``KingCreationResult.reason`` back to the GM on a rejected
allocation instead of silently failing.

**Rulebook [2.1], quoted in full where relevant**: "At the start of
the game, the player assigns the King's name, race, temper, alignment
and four ability levels. The King can have four abilities start at
level 1, or 2 abilities at level two, and so on, but can't assign more
than 2 points to any ability... Kings also automatically get a +1
modifier to their skill in Melee, Archery and Sage, which reflects
their royal training and education. A Divine King receives a +1
modifier to his White Magic skill, and starts with zero aptitude in
Necromancy skill. An Undead King receives a +1 modifier to his
Necromancy skill, and starts with an zero aptitude in White Magic
skill. The starting aptitude of a King is always 2 higher than his
initial skill, to a maximum of 5. Undead and Divine Kings cannot start
with any ability in a skill in which they have zero aptitude."

**Race and alignment are never re-chosen here, confirmed with the
user (project author)**: a King created via succession keeps the same
lineage as his predecessor -- already true by construction, since
Phase 259's own Royal Heir already carries the dead King's own
``alignment``/``race`` forward (``LeaderState`` has no separate
per-leader race field to begin with for an ordinary King; it's always
implicit in the serving Kingdom's own ``KingdomState.race``, per
``models/game_state.py``'s own module docstring). This module never
touches either field.

**The real validation constraint (Phase 554), sourced from
``AKGEN_reverse_engineering_report (5).md`` SS1/SS8.5 (machine-verified
against ``AKE.EXE:0xC193-0xC2B7``)**: at most 1 of the 15 abilities may
end up above the dead King's own preserved skill level for that
ability, and for that one excepted ability, by at most 1 level --
``final_skill[ability] > F(ability)`` for no more than one ability, and
``final_skill[ability] <= F(ability) + 1`` for that one. This replaces
an earlier, project-original "at least 2 of the 4 points must land on
Talents the dead King started with" heuristic (documented at the time
as "confirmed with the user... a deliberate simplification, not a
silent guess," made before this report existed) -- the real constraint
needed no such workaround, since it compares against the dead King's
own preserved skill at death, which this project already reads from
``GameState.dead_leaders`` for a related purpose (the same snapshot
Phase 259's own Resurrection-on-Heir branch uses). ``F(ability)`` here
is still that death-time snapshot, not the unrecoverable true creation-
time figure -- the real engine's own ``AKE.EXE`` disassembly reads the
identical currently-stored value at the moment of comparison, so this
was never actually an approximation to begin with, just previously
undocumented as exact.

**Phase 557 audit note**: the user's own ``SUCCESSIONE.txt``
(project-original rules notes, Desktop root) describes a different,
inclusion-based constraint instead -- "si devono per forza assegnare
almeno due punti in talenti che possedeva il defunto RE quando è stato
creato" ("you must assign at least two points to Talents the dead King
possessed when he was created"), with a worked example matching the
old, now-removed ``KING_CREATION_MIN_OVERLAP_POINTS`` rule exactly.
Flagged to the user as a direct conflict with SS1/SS8.5 above;
**confirmed by the user (project author): the disassembly-sourced
report governs**, this Phase 554 constraint stays as implemented.
Documented here so a future audit of ``SUCCESSIONE.txt`` doesn't
re-flag the same already-resolved conflict.

**Sex** (``models/sex.py``, new this phase): RULES.AK [2.1] doesn't
list it in its own King-creation sentence, but it's confirmed directly
with the user (project author, drawing on first-hand game knowledge)
as also chosen at creation.

**Phase 862 bug fix**: ``create_king()`` used to apply the Divine/
Undead alignment bonus (+1 White/Necromancy) *after* running the
Phase 554 exceeding-check above, instead of alongside the royal-
training bonus it's otherwise identical to (automatic, not player-
chosen). This let a Divine or Undead succession silently create a
second, never-validated exceeding ability on top of whichever one the
player's own point allocation already produced -- e.g. a Divine heir
whose dead predecessor had ``White=0`` always ends up with a real,
stored ``White=1`` from this bonus alone, which is exactly one
"exceeds the dead King's own preserved skill" case the check should
have counted. Fixed by moving the alignment-bonus assignment to run
before the check, alongside the training bonus.
"""

from __future__ import annotations

from dataclasses import dataclass

from ak_engine.models.alignment import ALIGNMENT_ORDINAL, Alignment
from ak_engine.models.enums import Ability
from ak_engine.models.game_state import GameState, LeaderState
from ak_engine.models.kingdom import SkillTable, trailing_skill_value_for_alignment
from ak_engine.models.sex import Sex
from ak_engine.models.temper import Temper

# RULES.AK [2.1]: "four ability levels... four abilities start at
# level 1, or 2 abilities at level two, and so on, but can't assign
# more than 2 points to any ability."
KING_CREATION_SKILL_POINTS = 4
KING_CREATION_MAX_POINTS_PER_ABILITY = 2

# Phase 554, AKGEN_reverse_engineering_report (5).md SS1/SS8.5
# (AKE.EXE:0xC193-0xC2B7, machine-verified): at most 1 of the 15
# abilities may end up above the dead King's own preserved-at-death
# skill level, and for that one excepted ability, by at most 1 level.
# See module docstring's own "the real constraint" section.
KING_CREATION_MAX_EXCEEDING_ABILITIES = 1
KING_CREATION_MAX_EXCEEDING_LEVELS = 1

# RULES.AK [2.1]: "Kings also automatically get a +1 modifier to their
# skill in Melee, Archery and Sage."
KING_TRAINING_BONUS_ABILITIES: tuple[Ability, ...] = (Ability.MELEE, Ability.ARCHERY, Ability.SAGE)

# RULES.AK [2.1]: "The starting aptitude of a King is always 2 higher
# than his initial skill, to a maximum of 5."
KING_CREATION_APTITUDE_BONUS = 2
KING_CREATION_MAX_APTITUDE = 5

# RULES.AK [2.3] "ALIGNMENT TABLE", "Magic Aptitude"/"Special Aptitude"
# columns -- "listed [are] abilities which characters of the given
# alignment are especially good at. Their starting aptitude is doubled
# for these abilities, up to level 5." Transcribed verbatim; Divine and
# Undead both read "None, None" in the real table (they instead get the
# separate +1-skill/zero-aptitude override below, not this doubling).
ALIGNMENT_SPECIAL_ABILITIES: dict[Alignment, tuple[Ability, Ability]] = {
    Alignment.GOOD: (Ability.WHITE, Ability.SAGE),
    Alignment.DRUID: (Ability.PSYCHIC, Ability.DRUID),
    Alignment.NEUTRAL: (Ability.ILLUSION, Ability.SPY),
    Alignment.PAGAN: (Ability.ELEMENTAL, Ability.EXPLORER),
    Alignment.EVIL: (Ability.NECROMANCY, Ability.THIEF),
}


@dataclass(slots=True)
class KingCreationResult:
    applied: bool
    reason: str | None = None


def _special_aptitude(skill: int) -> int:
    """The Alignment Table's own "doubled... up to level 5" rule for a King's two
    Special/Magic-Aptitude abilities. **Project-original, confirmed with
    the user**: RULES.AK [2.1]'s own "always 2 higher... to a maximum
    of 5" and [2.3]'s "doubled... up to level 5" read as two competing
    formulas for the same two abilities with no stated tie-break --
    resolved as "whichever is higher, still capped at 5," so this rule
    is never worse than the ordinary +2 one it overlaps with.

    **Numerically identical to ``_ordinary_aptitude()`` for every skill
    value this module can ever actually produce (0-3, given the 0-2
    player cap plus at most one +1 bonus).** ``skill + 2 >= skill * 2``
    whenever ``skill <= 2``, and both formulas already hit the ``5``
    cap once ``skill >= 3`` -- so the two never diverge in practice.
    Kept as its own function anyway, not merged with the ordinary one,
    so the distinct [2.1]/[2.3] sourcing for these two abilities stays
    traceable rather than silently folded away -- not a bug, a
    mathematical coincidence of the bounded point scale.
    """

    return min(max(skill + KING_CREATION_APTITUDE_BONUS, skill * 2), KING_CREATION_MAX_APTITUDE)


def _ordinary_aptitude(skill: int) -> int:
    return min(skill + KING_CREATION_APTITUDE_BONUS, KING_CREATION_MAX_APTITUDE)


def create_king(
    state: GameState,
    heir_leader_id: int,
    *,
    name: str,
    temper: Temper,
    sex: Sex,
    skill_points: dict[Ability, int],
) -> KingCreationResult:
    """Turns a still-uncustomized Royal Heir into a real new King -- see module
    docstring for the full, sourced formula. ``skill_points`` need only
    contain the abilities the player actually invested in (any ability
    not present is treated as 0); every one of the 15 ``Ability``
    members is still written into the resulting ``SkillTable``, since
    every ability needs a real (possibly 0) aptitude regardless of
    whether the player chose it.
    """

    heir = state.leaders.get(heir_leader_id)
    if heir is None or not heir.is_royal_heir:
        return KingCreationResult(applied=False, reason="not a Royal Heir")

    total_points = sum(skill_points.values())
    if total_points != KING_CREATION_SKILL_POINTS:
        return KingCreationResult(
            applied=False, reason=f"must assign exactly {KING_CREATION_SKILL_POINTS} Talent points"
        )
    for points in skill_points.values():
        if not (0 <= points <= KING_CREATION_MAX_POINTS_PER_ABILITY):
            return KingCreationResult(
                applied=False, reason=f"no more than {KING_CREATION_MAX_POINTS_PER_ABILITY} points per Talent"
            )

    alignment = heir.alignment
    forbidden_ability: Ability | None = None
    if alignment is Alignment.DIVINE:
        forbidden_ability = Ability.NECROMANCY
    elif alignment is Alignment.UNDEAD:
        forbidden_ability = Ability.WHITE
    if forbidden_ability is not None and skill_points.get(forbidden_ability, 0) > 0:
        return KingCreationResult(
            applied=False, reason=f"a King of this alignment cannot invest in {forbidden_ability.name}"
        )

    final_skill: dict[Ability, int] = {ability: skill_points.get(ability, 0) for ability in Ability}
    for ability in KING_TRAINING_BONUS_ABILITIES:
        final_skill[ability] += 1
    # Phase 862: the alignment-intrinsic bonus below must land in
    # `final_skill` *before* the exceeding-check, not after -- it is
    # just as automatic and unconditional as the training bonus above
    # (the player never chooses it), and the dead King's own preserved
    # skill already reflects his own equivalent bonus from when *he*
    # was created (same alignment, never re-chosen at succession -- see
    # module docstring). Applying it after the check let a Divine/Undead
    # succession silently create a second, unvalidated exceeding ability
    # (White/Necromancy) on top of whichever one the player's own points
    # already produced, defeating the "at most 1 ability may exceed"
    # rule below.
    if alignment is Alignment.DIVINE:
        final_skill[Ability.WHITE] += 1
    elif alignment is Alignment.UNDEAD:
        final_skill[Ability.NECROMANCY] += 1

    dead_king = state.dead_leaders.get(heir_leader_id)
    if dead_king is not None and dead_king.skills is not None:
        exceeding = [
            (ability, final_skill[ability] - dead_king.skills.pair_for_ability(ability)[0])
            for ability in Ability
            if final_skill[ability] > dead_king.skills.pair_for_ability(ability)[0]
        ]
        if len(exceeding) > KING_CREATION_MAX_EXCEEDING_ABILITIES:
            return KingCreationResult(
                applied=False,
                reason=f"no more than {KING_CREATION_MAX_EXCEEDING_ABILITIES} Talent may exceed the dead King's own preserved skill",
            )
        if exceeding and exceeding[0][1] > KING_CREATION_MAX_EXCEEDING_LEVELS:
            return KingCreationResult(
                applied=False,
                reason=f"the one exceeding Talent may rise at most {KING_CREATION_MAX_EXCEEDING_LEVELS} level above the dead King's own preserved skill",
            )

    special_abilities = ALIGNMENT_SPECIAL_ABILITIES.get(alignment) if alignment is not None else None

    raw_values = [0] * 31
    for ability in Ability:
        skill = final_skill[ability]
        if ability is forbidden_ability:
            aptitude = 0
        elif special_abilities is not None and ability in special_abilities:
            aptitude = _special_aptitude(skill)
        else:
            aptitude = _ordinary_aptitude(skill)
        raw_values[ability.value * 2] = skill
        raw_values[ability.value * 2 + 1] = aptitude
    # Phase 1192 bug fix: worldgen/king_talent.py build_king_skill_table()
    # -- the near-identical twin this function duplicates the same real
    # 4-point/2-per-ability talent formula from -- always sets this real
    # trailing SkillTable byte (Phase 910); this function never did,
    # silently leaving every succession-created King with raw_values[30]
    # == 0, a value no real alignment ever produces (see ALIGNMENT_
    # TRAILING_SKILL_VALUE's own docstring). Same permissive "leave it at
    # 0" fallback as elsewhere in this project when alignment is missing.
    if alignment is not None:
        raw_values[30] = trailing_skill_value_for_alignment(alignment)

    heir.name = name
    heir.temper = temper
    heir.sex = sex
    heir.skills = SkillTable(raw_values=raw_values)
    heir.is_royal_heir = False

    return KingCreationResult(applied=True)


# -- A new player takes over a Kingdom that is out of the game ------------------------------------------------------------

NEW_PLAYER_ALIGNMENT_STEPS = 2
_PLAYABLE_KING_ALIGNMENTS = (
    Alignment.DIVINE,
    Alignment.GOOD,
    Alignment.DRUID,
    Alignment.NEUTRAL,
    Alignment.PAGAN,
    Alignment.EVIL,
    Alignment.UNDEAD,
)


def new_player_alignments(state: GameState, kingdom_id: int) -> list[Alignment]:
    """The alignments a new player may give the King of a Kingdom he takes over: no further than two steps (on the real
    scale, ``ALIGNMENT_ORDINAL``) from any of the Kingdom's characters -- the original's standby text: "You may choose an
    alignment that is no further than two steps removed from any of your characters" -- and never Divine or Undead if
    another King already is (rulebook [2.1]: one of each per game). A Kingdom with no character left goes by its own
    alignment."""

    kingdom = state.kingdoms[kingdom_id]
    reference = [
        leader.alignment
        for leader in state.leaders.values()
        if leader.kingdom_id == kingdom_id and not leader.is_king and leader.alignment is not None
    ] or [kingdom.alignment]
    taken = {
        other.alignment
        for other in state.leaders.values()
        if other.is_king and other.kingdom_id != kingdom_id and other.alignment in (Alignment.DIVINE, Alignment.UNDEAD)
    }
    return [
        alignment
        for alignment in _PLAYABLE_KING_ALIGNMENTS
        if alignment not in taken
        and any(abs(ALIGNMENT_ORDINAL[alignment] - ALIGNMENT_ORDINAL[ref]) <= NEW_PLAYER_ALIGNMENT_STEPS for ref in reference)
    ]


def assign_new_player(
    state: GameState,
    kingdom_id: int,
    *,
    name: str,
    temper: Temper,
    sex: Sex,
    alignment: Alignment,
    talent_allocation: dict[Ability, int],
) -> KingCreationResult:
    """A new player takes over a Kingdom that is out of the game (``KingdomState.out_of_game``: its King died with his soul
    sold). The original offered such a realm to a new player, who "may start your King character from scratch, choosing 4
    new abilities for your King, and also his name, gender and temper" and an alignment within two steps of the
    Kingdom's characters. The new King is made like a starting one (rulebook [2.1]: four points, at most two to a Talent,
    the automatic bonuses) -- the dead King's own skills do not limit him -- and stands in the Kingdom's Home province under
    the same leader number, so he finds the dead King's treasures. The realm is back in the game: its lands, armies and
    Heroes were waiting, and reports go to it again."""

    from ak_engine.worldgen.king_talent import MAX_POINTS_PER_ABILITY, MAX_TALENT_POINTS, build_king_skill_table

    kingdom = state.kingdoms.get(kingdom_id)
    if kingdom is None:
        return KingCreationResult(applied=False, reason="Kingdom not found")
    if not kingdom.out_of_game:
        return KingCreationResult(applied=False, reason="this Kingdom is still in the game")
    if kingdom_id in state.leaders:
        return KingCreationResult(applied=False, reason="this Kingdom already has a King")
    if not name.strip():
        return KingCreationResult(applied=False, reason="please enter the new King's name")
    if alignment not in new_player_alignments(state, kingdom_id):
        return KingCreationResult(
            applied=False,
            reason=f"{alignment.name.title()} is not allowed: no further than {NEW_PLAYER_ALIGNMENT_STEPS} steps from "
            "the Kingdom's characters, and only one Divine and one Undead King per game",
        )
    total = sum(talent_allocation.values())
    if total != MAX_TALENT_POINTS:
        return KingCreationResult(applied=False, reason=f"must assign exactly {MAX_TALENT_POINTS} Talent points")
    if any(points < 0 or points > MAX_POINTS_PER_ABILITY for points in talent_allocation.values()):
        return KingCreationResult(applied=False, reason=f"no more than {MAX_POINTS_PER_ABILITY} points per Talent")
    forbidden = Ability.NECROMANCY if alignment is Alignment.DIVINE else Ability.WHITE if alignment is Alignment.UNDEAD else None
    if forbidden is not None and talent_allocation.get(forbidden, 0) > 0:
        return KingCreationResult(applied=False, reason=f"a King of this alignment cannot invest in {forbidden.name}")

    state.leaders[kingdom_id] = LeaderState(
        leader_id=kingdom_id,
        kingdom_id=kingdom_id,
        name=name.strip(),
        location=kingdom.home_province,
        skills=build_king_skill_table(talent_allocation, alignment),
        is_king=True,
        temper=temper,
        sex=sex,
        alignment=alignment,
        race=kingdom.race,
    )
    kingdom.alignment = alignment
    kingdom.out_of_game = False
    kingdom.final_report_sent = False
    return KingCreationResult(applied=True)
