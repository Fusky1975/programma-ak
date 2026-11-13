"""Phase 1049: a drift guard for the 6 near-identical, deliberately NOT
shared Combatant-builder functions this project's own code repeatedly
documents as an accepted "small lookup, not worth a cross-module
dependency" duplication (``challenge_execution.py``'s own docstring:
"a Duel commander and an Encounter participant are different concepts
that happen to need the same small lookup, not worth a cross-module
dependency for"; ``battle_orchestrator.py``'s own ``_commander_
combatant`` makes the identical call). ``cast_execution.py``'s own
Phase 684 addendum names two real historical instances of exactly this
duplication silently drifting apart before a dedicated audit caught
them: the Arcane's Valor hit-point bonus, and ``archery_skill``
defaulting to 0 in one copy (``patrol_execution.py``'s own Phase 684
addendum).

Rather than consolidate the 6 functions into one shared helper --
overriding that twice-documented architectural choice, and papering
over each one's own slightly different parameter order/temper-override
shape -- this module gives the drift itself an automated catch: every
test below calls all 6 builders against the SAME leader/state fixture
and asserts they agree on the one bonus field that fixture triggers. A
future bonus added to one copy and forgotten in the others fails here
instead of silently shipping.

``search_execution.py``'s own ``_leader_combatant()`` is the one
documented, deliberate exception: its own docstring says Search has no
"Neutral Kingdom" Order-of-Duelists bonus concern (that bonus is about
character-vs-character Encounters, not leader-vs-monster), so it never
sets ``neutral_duelist_bonus`` at all -- excluded from that one
comparison only, included in every other one below.
"""

from __future__ import annotations

from ak_engine.models.advanced_ability import AdvancedAbility
from ak_engine.models.alignment import Alignment
from ak_engine.models.enums import Ability
from ak_engine.models.game_state import GameState, KingdomState, LeaderState
from ak_engine.models.game_type import GameType
from ak_engine.models.kingdom import SkillTable
from ak_engine.models.map import HexCoord
from ak_engine.models.race import Race
from ak_engine.models.treasure import Treasure
from ak_engine.turn.cast_execution import _kill_enemy_combatant
from ak_engine.turn.challenge_execution import _leader_combatant as _challenge_combatant
from ak_engine.turn.patrol_execution import _leader_combatant as _patrol_combatant
from ak_engine.turn.pursue_execution import _leader_combatant as _pursue_combatant
from ak_engine.turn.random_encounter_execution import _leader_combatant as _random_encounter_combatant
from ak_engine.turn.search_execution import _leader_combatant as _search_combatant

LOCATION = HexCoord(3, 9)
LEADER_ID = 1


def _skills_with(ability: Ability, level: int) -> SkillTable:
    raw_values = [0] * 30
    raw_values[ability.value * 2] = level
    return SkillTable(raw_values=raw_values)


def _state_and_leader() -> tuple[GameState, LeaderState]:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.GOOD, LOCATION))
    leader = LeaderState(LEADER_ID, 1, "Combatant", LOCATION)
    state.add_leader(leader)
    return state, leader


def _all_combatants(state: GameState, leader: LeaderState) -> dict[str, object]:
    return {
        "cast_execution": _kill_enemy_combatant(state, leader, temper=leader.temper),
        "challenge_execution": _challenge_combatant(leader, state),
        "patrol_execution": _patrol_combatant(leader, state),
        "pursue_execution": _pursue_combatant(leader, state),
        "random_encounter_execution": _random_encounter_combatant(leader, state),
        "search_execution": _search_combatant(state, leader),
    }


def _assert_field_agrees(combatants: dict[str, object], field: str, *, exclude: tuple[str, ...] = ()) -> None:
    values = {name: getattr(c, field) for name, c in combatants.items() if name not in exclude}
    assert len(set(values.values())) == 1, f"{field} disagreement across builders: {values}"


def test_combatant_builders_agree_on_arcane_valor_hit_points_bonus():
    # The real, historically-confirmed drift (cast_execution.py's own
    # Phase 684 addendum): this bonus was added to some of these 6
    # builders and silently missed in others for multiple phases.
    state, leader = _state_and_leader()
    state.game_type = GameType.ARCANES
    state.add_item(Treasure.NAMED_UNIQUE_SCEPTER_LIFE, owner_leader_id=LEADER_ID)

    _assert_field_agrees(_all_combatants(state, leader), "hit_points")


def test_combatant_builders_agree_on_archery_skill():
    # The second real, historically-confirmed drift (patrol_execution.py's
    # own Phase 684 addendum): one copy never computed/passed archery_
    # skill at all, silently leaving it at the dataclass default.
    state, leader = _state_and_leader()
    leader.skills = _skills_with(Ability.ARCHERY, 4)

    _assert_field_agrees(_all_combatants(state, leader), "archery_skill")


def test_combatant_builders_agree_on_melee_skill():
    state, leader = _state_and_leader()
    leader.skills = _skills_with(Ability.MELEE, 3)

    _assert_field_agrees(_all_combatants(state, leader), "melee_skill")


def test_combatant_builders_agree_on_neutral_duelist_bonus():
    # Excludes search_execution.py -- its own docstring documents that
    # it deliberately never sets this field (no "Neutral Kingdom" bonus
    # concern for a leader-vs-monster Search encounter).
    state, leader = _state_and_leader()
    state.kingdoms[1].alignment = Alignment.NEUTRAL

    _assert_field_agrees(_all_combatants(state, leader), "neutral_duelist_bonus", exclude=("search_execution",))


def test_combatant_builders_agree_on_weapon_and_bow_bonuses():
    state, leader = _state_and_leader()
    state.add_item(Treasure.WEAPON_3, owner_leader_id=LEADER_ID)  # Flaming Scimitar: +20%/+3
    state.add_item(Treasure.LEADERSHIP_ELVEN, owner_leader_id=LEADER_ID)  # Bow of the Elven Kings

    combatants = _all_combatants(state, leader)
    for field in (
        "offensive_hit_multiplier",
        "melee_damage_dealt_bonus",
        "defensive_hit_multiplier",
        "is_invisible",
        "equipped_weapon",
        "archery_hit_multiplier",
        "missile_damage_dealt_bonus",
    ):
        _assert_field_agrees(combatants, field)


def test_combatant_builders_agree_on_advanced_abilities_and_race_alignment():
    state, leader = _state_and_leader()
    leader.race = Race.ELVEN
    leader.alignment = Alignment.UNDEAD
    leader.advanced_abilities.update(
        {
            AdvancedAbility.MELEE_HIT_POINTS,
            AdvancedAbility.MELEE_MASTERY,
            AdvancedAbility.MELEE_DUELLISTS_MEDAL,
            AdvancedAbility.MELEE_CONTROL_TEMPER,
            AdvancedAbility.ARCHERY_FREE_ATTACK,
        }
    )

    combatants = _all_combatants(state, leader)
    for field in (
        "has_melee_hit_points_ability",
        "offensive_hit_multiplier",
        "melee_damage_dealt_bonus",
        "has_duellists_medal_ability",
        "has_control_temper_ability",
        "archery_free_attack_bonus",
        "is_humanoid",
        "is_undead_or_anti_holy",
    ):
        _assert_field_agrees(combatants, field)


def test_combatant_builders_agree_on_defender_office_damage_reduction():
    state, leader = _state_and_leader()
    leader.merit_tally.monster_hp_defeated = 1  # meets OFFICE_MIN_POINTS[Office.DEFENDER]

    _assert_field_agrees(_all_combatants(state, leader), "damage_reduction")


def test_combatant_builders_agree_on_illus_mage_and_necro_mage_offices():
    illus_state, illus_leader = _state_and_leader()
    illus_leader.merit_tally.illusionist_spell_casts = 1  # Office.ILLUS_MAGE -- always_acts_first
    _assert_field_agrees(_all_combatants(illus_state, illus_leader), "always_acts_first")

    necro_state, necro_leader = _state_and_leader()
    necro_leader.merit_tally.necromancy_spell_casts = 1  # Office.NECRO_MAGE -- regenerates_hp(_interval)
    necro_combatants = _all_combatants(necro_state, necro_leader)
    _assert_field_agrees(necro_combatants, "regenerates_hp")
    _assert_field_agrees(necro_combatants, "regenerates_hp_interval")
