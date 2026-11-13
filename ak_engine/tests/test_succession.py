from __future__ import annotations

from ak_engine.models.alignment import Alignment
from ak_engine.models.enums import Ability
from ak_engine.models.game_state import GameState, KingdomState, LeaderState
from ak_engine.models.kingdom import ALIGNMENT_TRAILING_SKILL_VALUE, SkillTable
from ak_engine.models.map import HexCoord
from ak_engine.models.race import Race
from ak_engine.models.sex import Sex
from ak_engine.models.temper import Temper
from ak_engine.turn.succession import (
    ALIGNMENT_SPECIAL_ABILITIES,
    KING_CREATION_MAX_APTITUDE,
    KING_CREATION_MAX_EXCEEDING_ABILITIES,
    KING_CREATION_MAX_EXCEEDING_LEVELS,
    KING_CREATION_SKILL_POINTS,
    KING_TRAINING_BONUS_ABILITIES,
    _ordinary_aptitude,
    _special_aptitude,
    create_king,
)

LOCATION = HexCoord(3, 9)
HEIR_ID = 1


def _dead_king_skills(overrides: dict[Ability, int]) -> SkillTable:
    """A realistic dead-King skill snapshot: every King this project can
    ever install (via ``create_king()`` itself or Phase 552's own
    ``remove_leader()`` reset) always carries the automatic Melee/
    Archery/Sage training bonus baseline -- ``overrides`` layers
    whatever else this particular King had invested by the time he
    died.
    """

    table = SkillTable(raw_values=[0] * 31)
    for bonus_ability in KING_TRAINING_BONUS_ABILITIES:
        table.set_pair_for_ability(bonus_ability, skill=1, aptitude=3)
    for ability, skill in overrides.items():
        table.set_pair_for_ability(ability, skill=skill, aptitude=_ordinary_aptitude(skill))
    return table


def _state_with_heir(*, alignment: Alignment | None = Alignment.NEUTRAL, dead_king_skills: SkillTable | None = None) -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, alignment or Alignment.NEUTRAL, LOCATION))
    heir = LeaderState(
        HEIR_ID,
        1,
        "Old King",
        LOCATION,
        skills=SkillTable(raw_values=[0] * 31),
        is_king=True,
        is_royal_heir=True,
        alignment=alignment,
    )
    state.add_leader(heir)
    if dead_king_skills is not None:
        state.dead_leaders[HEIR_ID] = LeaderState(
            HEIR_ID, 1, "Old King", LOCATION, skills=dead_king_skills, is_king=True, alignment=alignment
        )
    return state


def test_create_king_fails_when_leader_not_found():
    state = GameState()

    result = create_king(state, 999, name="New King", temper=Temper.BRAVE, sex=Sex.MALE, skill_points={})

    assert result.applied is False
    assert result.reason == "not a Royal Heir"


def test_create_king_fails_when_leader_is_not_a_royal_heir():
    state = _state_with_heir()
    state.leaders[HEIR_ID].is_royal_heir = False

    result = create_king(
        state, HEIR_ID, name="New King", temper=Temper.BRAVE, sex=Sex.MALE,
        skill_points={Ability.TACTICAL: 4},
    )

    assert result.applied is False
    assert result.reason == "not a Royal Heir"


def test_create_king_requires_exactly_the_full_point_total():
    state = _state_with_heir(dead_king_skills=_dead_king_skills({Ability.TACTICAL: 3}))

    result = create_king(
        state, HEIR_ID, name="New King", temper=Temper.BRAVE, sex=Sex.MALE,
        skill_points={Ability.TACTICAL: 2},  # only 2, not 4
    )

    assert result.applied is False
    assert result.reason == f"must assign exactly {KING_CREATION_SKILL_POINTS} Talent points"


def test_create_king_rejects_more_than_two_points_on_a_single_ability():
    state = _state_with_heir(dead_king_skills=_dead_king_skills({Ability.TACTICAL: 3}))

    result = create_king(
        state, HEIR_ID, name="New King", temper=Temper.BRAVE, sex=Sex.MALE,
        skill_points={Ability.TACTICAL: 3, Ability.MARCH: 1},
    )

    assert result.applied is False
    assert "no more than" in result.reason


def test_create_king_rejects_when_two_abilities_exceed_the_dead_kings_own_skill():
    # Phase 554: the real constraint (AKGEN_reverse_engineering_report
    # (5).md SS1/SS8.5) -- at most 1 ability may end up above the dead
    # King's own preserved-at-death skill level.
    state = _state_with_heir(dead_king_skills=_dead_king_skills({Ability.TACTICAL: 3}))

    result = create_king(
        state, HEIR_ID, name="New King", temper=Temper.BRAVE, sex=Sex.MALE,
        skill_points={Ability.MARCH: 2, Ability.NAVAL: 2},  # dead King had 0 in both
    )

    assert result.applied is False
    assert result.reason == (
        f"no more than {KING_CREATION_MAX_EXCEEDING_ABILITIES} Talent may exceed the dead King's own preserved skill"
    )


def test_create_king_rejects_a_single_ability_exceeding_by_more_than_one_level():
    state = _state_with_heir(dead_king_skills=_dead_king_skills({Ability.TACTICAL: 3, Ability.NAVAL: 1}))

    result = create_king(
        state, HEIR_ID, name="New King", temper=Temper.BRAVE, sex=Sex.MALE,
        # TACTICAL:2 stays within the dead King's own 3; MARCH:2 alone
        # exceeds his 0 by 2 -- one ability, but by too much.
        skill_points={Ability.TACTICAL: 2, Ability.MARCH: 2},
    )

    assert result.applied is False
    assert result.reason == (
        f"the one exceeding Talent may rise at most {KING_CREATION_MAX_EXCEEDING_LEVELS} level "
        "above the dead King's own preserved skill"
    )


def test_create_king_accepts_a_single_ability_exceeding_by_exactly_one_level():
    state = _state_with_heir(dead_king_skills=_dead_king_skills({Ability.TACTICAL: 3, Ability.NAVAL: 1}))

    result = create_king(
        state, HEIR_ID, name="New King", temper=Temper.BRAVE, sex=Sex.MALE,
        # TACTICAL:2 (<=3) and NAVAL:1 (<=1) stay within the dead King's
        # own levels; MARCH:1 alone exceeds his 0, by exactly 1.
        skill_points={Ability.TACTICAL: 2, Ability.NAVAL: 1, Ability.MARCH: 1},
    )

    assert result.applied is True


def test_create_king_accepts_a_redistribution_entirely_at_or_below_the_dead_kings_own_levels():
    # Uses the dead King's own snapshot as the comparison baseline
    # (GameState.dead_leaders, the same snapshot Phase 259's own
    # Resurrection-on-Heir branch already reads) -- zero abilities
    # exceed it here, regardless of which two the player chose.
    state = _state_with_heir(dead_king_skills=_dead_king_skills({Ability.TACTICAL: 3, Ability.NAVAL: 2}))

    result = create_king(
        state, HEIR_ID, name="New King", temper=Temper.BRAVE, sex=Sex.MALE,
        skill_points={Ability.TACTICAL: 2, Ability.NAVAL: 2},
    )

    assert result.applied is True


def test_create_king_skips_the_exceeding_check_when_no_dead_king_snapshot_exists():
    state = _state_with_heir(dead_king_skills=None)  # no dead_leaders entry at all

    result = create_king(
        state, HEIR_ID, name="New King", temper=Temper.BRAVE, sex=Sex.MALE,
        skill_points={Ability.MARCH: 2, Ability.NAVAL: 2},
    )

    assert result.applied is True


def test_create_king_applies_royal_training_bonus_and_sets_identity_fields():
    state = _state_with_heir(
        alignment=Alignment.NEUTRAL,
        dead_king_skills=_dead_king_skills({Ability.TACTICAL: 3, Ability.MARCH: 2}),
    )

    result = create_king(
        state, HEIR_ID, name="Aldric II", temper=Temper.BERSERK, sex=Sex.FEMALE,
        skill_points={Ability.TACTICAL: 2, Ability.MARCH: 2},
    )

    assert result.applied is True
    heir = state.leaders[HEIR_ID]
    assert heir.name == "Aldric II"
    assert heir.temper is Temper.BERSERK
    assert heir.sex is Sex.FEMALE
    assert heir.is_royal_heir is False
    # Player-chosen abilities: no royal-training bonus applies to either.
    assert heir.skills.pair_for_ability(Ability.TACTICAL) == (2, _ordinary_aptitude(2))
    assert heir.skills.pair_for_ability(Ability.MARCH) == (2, _ordinary_aptitude(2))
    # Untouched abilities still get the +1 royal-training bonus.
    for ability in KING_TRAINING_BONUS_ABILITIES:
        assert heir.skills.pair_for_ability(ability) == (1, _ordinary_aptitude(1))
    # Every other untouched, non-bonus ability stays at (0, ordinary_aptitude(0)).
    untouched = set(Ability) - {Ability.TACTICAL, Ability.MARCH} - set(KING_TRAINING_BONUS_ABILITIES)
    for ability in untouched:
        assert heir.skills.pair_for_ability(ability)[0] == 0


def test_create_king_sets_the_real_trailing_skill_table_byte():
    # Phase 1192 bug fix: raw_values[30] (Phase 910's real alignment
    # trailing value) used to stay at its 0 initializer -- a value no
    # real alignment ever produces -- for every succession-created King,
    # unlike worldgen/king_talent.py build_king_skill_table()'s own
    # near-identical twin, which always sets it.
    state = _state_with_heir(alignment=Alignment.NEUTRAL)

    result = create_king(
        state, HEIR_ID, name="Aldric II", temper=Temper.BERSERK, sex=Sex.FEMALE,
        skill_points={Ability.MELEE: 2, Ability.ARCHERY: 2},
    )

    assert result.applied is True
    assert state.leaders[HEIR_ID].skills.raw_values[30] == ALIGNMENT_TRAILING_SKILL_VALUE[Alignment.NEUTRAL]


def test_create_king_race_and_alignment_are_never_touched():
    state = _state_with_heir(
        alignment=Alignment.EVIL,
        dead_king_skills=_dead_king_skills({Ability.NECROMANCY: 3, Ability.THIEF: 2}),
    )

    create_king(
        state, HEIR_ID, name="New King", temper=Temper.CAUTIOUS, sex=Sex.MALE,
        skill_points={Ability.NECROMANCY: 2, Ability.THIEF: 2},
    )

    assert state.leaders[HEIR_ID].alignment is Alignment.EVIL  # unchanged
    assert state.leaders[HEIR_ID].race is None  # unchanged (never set, same as before)


def test_create_king_divine_alignment_bonus_counts_toward_the_exceeding_check():
    # Phase 862: the dead King never invested in White (his own record
    # stays at 0), and the player's own points already spend the single
    # allowed "exceeds by 1" exception on MARCH -- so the automatic
    # Divine +1 White bonus (which the player never chose) must count
    # as a *second* exceeding ability and refuse the creation, exactly
    # like a second player-chosen exceeding ability would.
    state = _state_with_heir(
        alignment=Alignment.DIVINE,
        dead_king_skills=_dead_king_skills({Ability.TACTICAL: 3, Ability.MARCH: 1}),
    )

    result = create_king(
        state, HEIR_ID, name="Divine King", temper=Temper.BRAVE, sex=Sex.MALE,
        skill_points={Ability.TACTICAL: 2, Ability.MARCH: 2},
    )

    assert result.applied is False
    assert result.reason == (
        f"no more than {KING_CREATION_MAX_EXCEEDING_ABILITIES} Talent may exceed the dead King's own preserved skill"
    )


def test_create_king_undead_alignment_bonus_counts_toward_the_exceeding_check():
    state = _state_with_heir(
        alignment=Alignment.UNDEAD,
        dead_king_skills=_dead_king_skills({Ability.TACTICAL: 3, Ability.MARCH: 1}),
    )

    result = create_king(
        state, HEIR_ID, name="Undead King", temper=Temper.BRAVE, sex=Sex.MALE,
        skill_points={Ability.TACTICAL: 2, Ability.MARCH: 2},
    )

    assert result.applied is False
    assert result.reason == (
        f"no more than {KING_CREATION_MAX_EXCEEDING_ABILITIES} Talent may exceed the dead King's own preserved skill"
    )


def test_create_king_divine_gets_white_magic_bonus_and_zero_necromancy_aptitude():
    state = _state_with_heir(
        alignment=Alignment.DIVINE,
        dead_king_skills=_dead_king_skills({Ability.TACTICAL: 3, Ability.MARCH: 2}),
    )

    result = create_king(
        state, HEIR_ID, name="Divine King", temper=Temper.BRAVE, sex=Sex.MALE,
        skill_points={Ability.TACTICAL: 2, Ability.MARCH: 2},
    )

    assert result.applied is True
    heir = state.leaders[HEIR_ID]
    # +1 White Magic even though the player invested nothing there.
    assert heir.skills.pair_for_ability(Ability.WHITE) == (1, _ordinary_aptitude(1))
    # Necromancy stays locked at zero skill and zero aptitude.
    assert heir.skills.pair_for_ability(Ability.NECROMANCY) == (0, 0)


def test_create_king_undead_gets_necromancy_bonus_and_zero_white_aptitude():
    state = _state_with_heir(
        alignment=Alignment.UNDEAD,
        dead_king_skills=_dead_king_skills({Ability.TACTICAL: 3, Ability.MARCH: 2}),
    )

    result = create_king(
        state, HEIR_ID, name="Undead King", temper=Temper.BRAVE, sex=Sex.MALE,
        skill_points={Ability.TACTICAL: 2, Ability.MARCH: 2},
    )

    assert result.applied is True
    heir = state.leaders[HEIR_ID]
    assert heir.skills.pair_for_ability(Ability.NECROMANCY) == (1, _ordinary_aptitude(1))
    assert heir.skills.pair_for_ability(Ability.WHITE) == (0, 0)


def test_create_king_divine_cannot_invest_in_necromancy():
    state = _state_with_heir(alignment=Alignment.DIVINE, dead_king_skills=_dead_king_skills({Ability.NECROMANCY: 3}))

    result = create_king(
        state, HEIR_ID, name="Divine King", temper=Temper.BRAVE, sex=Sex.MALE,
        skill_points={Ability.NECROMANCY: 2, Ability.MARCH: 2},
    )

    assert result.applied is False
    assert "cannot invest in NECROMANCY" in result.reason


def test_create_king_undead_cannot_invest_in_white():
    state = _state_with_heir(alignment=Alignment.UNDEAD, dead_king_skills=_dead_king_skills({Ability.WHITE: 3}))

    result = create_king(
        state, HEIR_ID, name="Undead King", temper=Temper.BRAVE, sex=Sex.MALE,
        skill_points={Ability.WHITE: 2, Ability.MARCH: 2},
    )

    assert result.applied is False
    assert "cannot invest in WHITE" in result.reason


def test_alignment_special_abilities_covers_the_five_doubling_alignments():
    assert ALIGNMENT_SPECIAL_ABILITIES.keys() == {
        Alignment.GOOD, Alignment.DRUID, Alignment.NEUTRAL, Alignment.PAGAN, Alignment.EVIL,
    }
    assert ALIGNMENT_SPECIAL_ABILITIES[Alignment.GOOD] == (Ability.WHITE, Ability.SAGE)
    assert ALIGNMENT_SPECIAL_ABILITIES[Alignment.EVIL] == (Ability.NECROMANCY, Ability.THIEF)


def test_create_king_special_ability_aptitude_matches_the_doubling_formula():
    state = _state_with_heir(
        alignment=Alignment.EVIL,
        dead_king_skills=_dead_king_skills({Ability.NECROMANCY: 3, Ability.THIEF: 2}),
    )

    result = create_king(
        state, HEIR_ID, name="Evil King", temper=Temper.BRAVE, sex=Sex.MALE,
        skill_points={Ability.NECROMANCY: 2, Ability.THIEF: 2},
    )

    assert result.applied is True
    heir = state.leaders[HEIR_ID]
    assert heir.skills.pair_for_ability(Ability.NECROMANCY) == (2, _special_aptitude(2))
    assert heir.skills.pair_for_ability(Ability.THIEF) == (2, _special_aptitude(2))


def test_special_and_ordinary_aptitude_coincide_across_every_reachable_skill_value():
    # Documented mathematical coincidence (see _special_aptitude's own
    # docstring) -- given the 0-2 player cap plus at most one +1 bonus,
    # skill never exceeds 3, and the two formulas never diverge there.
    for skill in range(0, 4):
        assert _special_aptitude(skill) == _ordinary_aptitude(skill)


def test_ordinary_aptitude_caps_at_the_maximum():
    assert _ordinary_aptitude(0) == 2
    assert _ordinary_aptitude(2) == 4
    assert _ordinary_aptitude(10) == KING_CREATION_MAX_APTITUDE
