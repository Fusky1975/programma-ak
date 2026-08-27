from __future__ import annotations

import random

import pytest

from ak_engine.models.advanced_ability import AdvancedAbility
from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.discovery import Discovery
from ak_engine.models.enums import Ability, Spell
from ak_engine.models.feature import Feature, FeatureType
from ak_engine.models.game_state import ArmyState, GameState, GraveyardEntry, KingdomState, LeaderState, ProvinceState
from ak_engine.models.kingdom import SkillTable
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.office import Office
from ak_engine.models.race import Race
from ak_engine.models.temper import Temper
from ak_engine.models.treasure import Treasure
from ak_engine.turn.cast_decode import CastRequest
from ak_engine.turn.cast_execution import (
    ILLUSORY_FOG_DISSIPATES_AT_END_OF_GAMETURN,
    ILLUSORY_FOG_EXTRA_MOVEMENT_COST,
    ILLUSORY_FOG_STRENGTH_MULTIPLIER,
    MYSTIC_WINDS_ENDS_BEFORE_ARMY_BATTLE,
    MYSTIC_WINDS_MOVEMENT_POINTS,
    MYSTIC_WINDS_MOVES_AS_AIR_UNIT,
    MYSTIC_WINDS_USES_MOVEMENT_POINTS_NORMALLY,
    SCAR_TERRAIN_LAND_COLLAPSE_RACES,
    SCAR_TERRAIN_TAX_REDUCTION,
    UNDEAD_CONVERSION_STEP_BUDGET_NUMERATOR,
    LocateObjectResult,
    _apply_undead_king_alignment_conversion,
    _kill_enemy_combatant,
    _total_usable_skill,
    action_cast_slots,
    apply_plague_exposure,
    execute_cast,
    illusory_fog_strength,
    is_illusory_fog_affected_air_unit,
    is_unfinalized_royal_heir,
    locate_object,
    scar_terrain_collapse,
    scar_terrain_is_exhausted,
)
from ak_engine.turn.combat import Quality
from ak_engine.turn.hex_numbering import encode_hex_number
from ak_engine.turn.movement import NORMAL_MAP_BOUNDS, MapBounds, neighbors

from _helpers import ScriptedRandom

LOCATION = HexCoord(3, 9)
ELSEWHERE = HexCoord(9, 9)
CASTER_ID = 1
BOARD_WIDTH = NORMAL_MAP_BOUNDS[0]


def _skills_with(ability: Ability, level: int) -> SkillTable:
    raw_values = [0] * 30
    raw_values[ability.value * 2] = level
    return SkillTable(raw_values=raw_values)


def _skills_totaling(total: int) -> SkillTable:
    # Spread across two abilities since a single (skill, aptitude) pair is
    # capped at 9 (CTBOTH.PAS skillrange 0..9) -- irrelevant to which
    # ability holds it, since Total_USkill only cares about the sum.
    raw_values = [0] * 30
    first = min(9, total)
    raw_values[Ability.TACTICAL.value * 2] = first
    raw_values[Ability.MARCH.value * 2] = total - first
    return SkillTable(raw_values=raw_values)


def _target(coord: HexCoord) -> int:
    return encode_hex_number(coord, BOARD_WIDTH)


def build_state() -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.GOOD, LOCATION))
    state.add_kingdom(KingdomState(2, "Rivalia", Race.HUMAN, Alignment.EVIL, ELSEWHERE))
    state.add_leader(LeaderState(CASTER_ID, 1, "Caster", LOCATION))
    return state


# -- Phase 547: Valhalla visitor spell immunity except Resurrection --


def test_charm_is_blocked_against_the_active_valhalla_visitor():
    state = build_state()
    state.add_leader(LeaderState(199, 2, "Visitor", LOCATION, valhalla_active_turn=state.turn_number))
    request = CastRequest(spell=Spell.CHARM, target=199)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is False
    assert result.reason == "the Valhalla visitor is immune to this spell"
    assert state.leaders[199].kingdom_id == 2  # untouched


def test_kill_enemy_is_blocked_against_the_active_valhalla_visitor():
    state = build_state()
    state.add_leader(LeaderState(199, 2, "Visitor", LOCATION, valhalla_active_turn=state.turn_number))
    request = CastRequest(spell=Spell.KILL_ENEMY, target=199)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is False
    assert result.reason == "the Valhalla visitor is immune to this spell"
    assert 199 in state.leaders  # untouched -- not killed


def test_resurrection_is_not_blocked_against_the_valhalla_visitor():
    # "except Resurrection" -- the one spell VALHALLA.txt explicitly
    # carves out. The visitor isn't even dead here, so this only proves
    # the immunity gate itself doesn't trigger (Resurrection then fails
    # for the ordinary "target isn't dead" reason, not the Valhalla one).
    state = build_state()
    state.add_leader(LeaderState(199, 2, "Visitor", LOCATION, valhalla_active_turn=state.turn_number))
    request = CastRequest(spell=Spell.RESURRECTION, target=199)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.reason != "the Valhalla visitor is immune to this spell"


def test_charm_is_not_blocked_against_leader_199_when_not_the_active_valhalla_visitor():
    # leader_id 199 with no valhalla_active_turn recorded (e.g. a stray
    # id collision, or a departed visitor whose fields were cleared) is
    # just an ordinary leader -- the immunity is scoped to a genuine
    # current visit, not the bare id.
    state = build_state()
    state.add_leader(LeaderState(199, 2, "Not A Visitor", LOCATION))
    request = CastRequest(spell=Spell.CHARM, target=199)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is True
    assert state.leaders[199].kingdom_id == 1


def test_charm_assigns_a_colocated_independent_hero_to_the_casters_kingdom():
    state = build_state()
    state.add_leader(LeaderState(78, None, "Wandering Hero", LOCATION))
    request = CastRequest(spell=Spell.CHARM, target=78)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is True
    assert result.reason is None
    assert state.leaders[78].kingdom_id == 1


def test_charm_steals_a_colocated_enemy_characters_allegiance():
    # Charm doesn't require the target to already be independent -- see
    # cast_execution.py's docstring for why this differs from Hire.
    state = build_state()
    state.add_leader(LeaderState(78, 2, "Enemy Hero", LOCATION))
    request = CastRequest(spell=Spell.CHARM, target=78)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is True
    assert state.leaders[78].kingdom_id == 1


def test_charm_against_an_analytical_psychology_protected_target_still_succeeds():
    # Phase 302 fix: Discovery.ANALYTICAL_PSYCHOLOGY does NOT block Charm
    # outright -- the source text says the spell still works, but wears
    # off at end of turn. The reassignment happens exactly as normal;
    # only the new revert bookkeeping differs from an unprotected target.
    state = build_state()
    state.kingdoms[2].discoveries.add(Discovery.ANALYTICAL_PSYCHOLOGY)
    state.add_leader(LeaderState(78, 2, "Protected Hero", LOCATION))
    request = CastRequest(spell=Spell.CHARM, target=78)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is True
    assert state.leaders[78].kingdom_id == 1  # charmed, same as an unprotected target
    assert state.leaders[78].analytical_psychology_revert_kingdom_id == 2  # queued to revert to kingdom 2


def test_charm_against_an_unprotected_target_never_sets_the_revert_field():
    state = build_state()
    state.add_leader(LeaderState(78, 2, "Ordinary Enemy Hero", LOCATION))
    request = CastRequest(spell=Spell.CHARM, target=78)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is True
    assert state.leaders[78].kingdom_id == 1
    assert state.leaders[78].analytical_psychology_revert_kingdom_id is None


# ---------------------------------------------------------------------------
# Charm: AdvancedAbility.ENHANCED_CHARM (Phase 499)
# ---------------------------------------------------------------------------


def test_charm_with_enhanced_ability_transfers_the_targets_highest_id_eligible_item():
    # Phase 539: AKGEN_reverse_engineering_report (4).md SS12.1 -- NT_Owned
    # overwrites its own `index` result on every match while scanning
    # ascending, so Enhanced Charm steals the LAST (highest-item_id)
    # eligible instance, not the first-created one.
    state = build_state()
    state.leaders[CASTER_ID].advanced_abilities.add(AdvancedAbility.ENHANCED_CHARM)
    state.add_leader(LeaderState(78, 2, "Laden Hero", LOCATION))
    first_item = state.add_item(Treasure.ABILITY_MELEE, owner_leader_id=78)
    second_item = state.add_item(Treasure.WAND_FIREBALL, owner_leader_id=78)
    request = CastRequest(spell=Spell.CHARM, target=78)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is True
    assert state.items[second_item.item_id].owner_leader_id == CASTER_ID
    assert state.items_held_by(78) == [state.items[first_item.item_id]]


def test_charm_with_enhanced_ability_ignores_ineligible_categories():
    # Gold Hoards, Quest items, and Named Uniques (93-98) are explicitly
    # excluded from Enhanced Charm's eligible range (dossier SS12.1: "non
    # sono eleggibili hoard, quest, contratto o artefatti 93..98") --
    # even though the Named Unique here has a higher item_id than the
    # eligible item, it must stay with the victim.
    state = build_state()
    state.leaders[CASTER_ID].advanced_abilities.add(AdvancedAbility.ENHANCED_CHARM)
    state.add_leader(LeaderState(78, 2, "Hoarding Hero", LOCATION))
    eligible_item = state.add_item(Treasure.ABILITY_MELEE, owner_leader_id=78)
    state.add_item(Treasure.GOLD_HOARD_LARGE, owner_leader_id=78)
    state.add_item(Treasure.NAMED_UNIQUE_CROWN_ROHAN, owner_leader_id=78)
    request = CastRequest(spell=Spell.CHARM, target=78)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is True
    assert state.items[eligible_item.item_id].owner_leader_id == CASTER_ID
    assert {item.treasure for item in state.items_held_by(78)} == {
        Treasure.GOLD_HOARD_LARGE,
        Treasure.NAMED_UNIQUE_CROWN_ROHAN,
    }


def test_charm_with_enhanced_ability_and_only_ineligible_items_is_a_no_op():
    state = build_state()
    state.leaders[CASTER_ID].advanced_abilities.add(AdvancedAbility.ENHANCED_CHARM)
    state.add_leader(LeaderState(78, 2, "Hoard-Only Hero", LOCATION))
    state.add_item(Treasure.GOLD_HOARD_LARGE, owner_leader_id=78)
    request = CastRequest(spell=Spell.CHARM, target=78)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is True
    assert len(state.items_held_by(78)) == 1
    assert state.items_held_by(CASTER_ID) == []


def test_charm_with_enhanced_ability_and_no_items_is_a_no_op():
    state = build_state()
    state.leaders[CASTER_ID].advanced_abilities.add(AdvancedAbility.ENHANCED_CHARM)
    state.add_leader(LeaderState(78, 2, "Empty-Handed Hero", LOCATION))
    request = CastRequest(spell=Spell.CHARM, target=78)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is True
    assert state.leaders[78].kingdom_id == 1


def test_charm_without_enhanced_ability_leaves_the_targets_items_untouched():
    state = build_state()
    state.add_leader(LeaderState(78, 2, "Laden Hero", LOCATION))
    item = state.add_item(Treasure.ABILITY_MELEE, owner_leader_id=78)
    request = CastRequest(spell=Spell.CHARM, target=78)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is True
    assert state.items[item.item_id].owner_leader_id == 78


def test_charm_fails_when_target_not_colocated():
    state = build_state()
    state.add_leader(LeaderState(78, None, "Wandering Hero", ELSEWHERE))
    request = CastRequest(spell=Spell.CHARM, target=78)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is False
    assert result.reason == "not co-located"
    assert state.leaders[78].kingdom_id is None  # untouched


def test_charm_fails_when_target_does_not_exist():
    state = build_state()
    request = CastRequest(spell=Spell.CHARM, target=999)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is False
    assert result.reason == "target character not found"


def test_charm_fails_when_target_commands_military_units():
    # Phase 183: "che non comanda unita' militari" -- a co-located Hero
    # commanding an army is not a free-hire target.
    state = build_state()
    state.add_leader(LeaderState(78, None, "Wandering Hero", LOCATION))
    state.add_army(ArmyState(1, None, ArmyType.LEGION, Quality.AVERAGE, LOCATION, commanded_by=78))
    request = CastRequest(spell=Spell.CHARM, target=78)
    rng = ScriptedRandom([])  # precondition fails before any roll

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is False
    assert result.reason == "target commands military units"
    assert state.leaders[78].kingdom_id is None  # untouched


def test_charm_fails_when_target_is_a_king():
    # Phase 529: AKGEN_reverse_engineering_report (3).md SS6.1/SS15.1 --
    # a King target is excluded from Action Charm's free-hire effect
    # outright, unlike an ordinary Hero.
    state = build_state()
    state.add_leader(LeaderState(78, 2, "Rival King", LOCATION, is_king=True))
    request = CastRequest(spell=Spell.CHARM, target=78)
    rng = ScriptedRandom([])  # precondition fails before any roll

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is False
    assert result.reason == "a King cannot be acquired by Action Charm"
    assert state.leaders[78].kingdom_id == 2  # untouched


def test_charm_fails_when_target_holds_the_matching_anti_magic_amulet():
    # Phase 531: AKGEN_reverse_engineering_report (4).md SS8 -- the Helm
    # of Psychic Dampening (Anti-Psychic Amulet) personally blocks Charm.
    state = build_state()
    state.add_leader(LeaderState(78, 2, "Protected Hero", LOCATION))
    state.add_item(Treasure.AMULET_ANTI_PSYCHIC, owner_leader_id=78)
    request = CastRequest(spell=Spell.CHARM, target=78)
    rng = ScriptedRandom([0.1, 0.5, 0.5])  # roll succeeds

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is False
    assert result.reason == "target is immune (anti-magic amulet)"
    assert state.leaders[78].kingdom_id == 2  # untouched


def test_charm_succeeds_when_target_holds_a_non_matching_anti_magic_amulet():
    state = build_state()
    state.add_leader(LeaderState(78, 2, "Ordinary Hero", LOCATION))
    state.add_item(Treasure.AMULET_ANTI_WHITE, owner_leader_id=78)
    request = CastRequest(spell=Spell.CHARM, target=78)
    rng = ScriptedRandom([0.1, 0.5, 0.5])

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is True
    assert state.leaders[78].kingdom_id == 1


def test_charm_undead_caster_still_blocked_by_anti_psychic_amulet():
    # Phase 531: immunity is keyed to the spell (Charm), not to whichever
    # school the caster happened to draw on -- the Helm of Psychic
    # Dampening blocks Charm even when an Undead caster cast it via
    # Necromancy.
    state = build_state()
    state.leaders[CASTER_ID].alignment = Alignment.UNDEAD
    state.leaders[CASTER_ID].skills = _skills_with(Ability.NECROMANCY, 2)
    state.add_leader(LeaderState(78, None, "Wandering Hero", LOCATION))
    state.add_item(Treasure.AMULET_ANTI_PSYCHIC, owner_leader_id=78)
    request = CastRequest(spell=Spell.CHARM, target=78)
    rng = ScriptedRandom([0.44, 0.5, 0.5])  # 15% + 15%*2 = 45% chance

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is False
    assert result.reason == "target is immune (anti-magic amulet)"


def test_charm_undead_caster_not_blocked_by_anti_necromancy_amulet():
    # The True Cross (Anti-Necromancy) blocks Kill_Enemy/Hand_of_Death
    # only -- Charm isn't in its blocked set, even for an Undead caster
    # whose Charm draws on Necromancy skill.
    state = build_state()
    state.leaders[CASTER_ID].alignment = Alignment.UNDEAD
    state.leaders[CASTER_ID].skills = _skills_with(Ability.NECROMANCY, 2)
    state.add_leader(LeaderState(78, None, "Wandering Hero", LOCATION))
    state.add_item(Treasure.AMULET_ANTI_NECROMANCY, owner_leader_id=78)
    request = CastRequest(spell=Spell.CHARM, target=78)
    rng = ScriptedRandom([0.44, 0.5, 0.5])

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is True


def test_charm_undead_caster_uses_necromancy_instead_of_psychic():
    # Phase 183: "Per i personaggi Non-Morti questo incantesimo
    # appartiene alla magia Negromantica (e non alla magia Psichica)."
    state = build_state()
    state.leaders[CASTER_ID].alignment = Alignment.UNDEAD
    state.leaders[CASTER_ID].skills = _skills_with(Ability.NECROMANCY, 2)
    state.add_leader(LeaderState(78, None, "Wandering Hero", LOCATION))
    request = CastRequest(spell=Spell.CHARM, target=78)
    rng = ScriptedRandom([0.44, 0.5, 0.5])  # 15% + 15%*2 = 45% chance

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is True
    assert state.leaders[78].kingdom_id == 1


def test_charm_undead_caster_with_only_psychic_skill_has_insufficient_skill():
    # Confirms the override is real -- an Undead caster's own Psychic
    # skill no longer governs Charm at all.
    state = build_state()
    state.leaders[CASTER_ID].alignment = Alignment.UNDEAD
    state.leaders[CASTER_ID].skills = _skills_with(Ability.PSYCHIC, 3)
    state.add_leader(LeaderState(78, None, "Wandering Hero", LOCATION))
    request = CastRequest(spell=Spell.CHARM, target=78)
    rng = ScriptedRandom([])  # precondition fails first, no roll consumed

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is False
    assert result.reason == "insufficient skill"


def test_charm_non_undead_caster_still_uses_psychic():
    state = build_state()
    assert state.leaders[CASTER_ID].alignment is None
    state.leaders[CASTER_ID].skills = _skills_with(Ability.PSYCHIC, 2)
    state.add_leader(LeaderState(78, None, "Wandering Hero", LOCATION))
    request = CastRequest(spell=Spell.CHARM, target=78)
    rng = ScriptedRandom([0.44, 0.5, 0.5])  # 15% + 15%*2 = 45% chance

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is True


# ---------------------------------------------------------------------------
# Charm: Undead King alignment conversion (Phase 522)
# ---------------------------------------------------------------------------


def _undead_king() -> LeaderState:
    return LeaderState(1, 1, "Undead King", LOCATION, is_king=True, alignment=Alignment.UNDEAD)


def test_total_usable_skill_sums_all_fifteen_abilities_raw_skill_not_aptitude():
    leader = LeaderState(2, None, "Target", LOCATION, skills=SkillTable(raw_values=list(range(30))))
    # Skill sits at even indices (0, 2, .. 28): 0+2+4+...+28 == 210.
    assert _total_usable_skill(leader) == 210


def test_total_usable_skill_returns_zero_when_skills_unrecorded():
    leader = LeaderState(2, None, "Target", LOCATION)
    assert _total_usable_skill(leader) == 0


def test_undead_king_conversion_step_budget_numerator_is_twelve():
    assert UNDEAD_CONVERSION_STEP_BUDGET_NUMERATOR == 12


def test_is_unfinalized_royal_heir_true_below_the_threshold():
    leader = LeaderState(2, None, "Heir", LOCATION, is_royal_heir=True, skills=_skills_totaling(6))
    assert is_unfinalized_royal_heir(leader) is True


def test_is_unfinalized_royal_heir_false_at_the_threshold():
    leader = LeaderState(2, None, "Heir", LOCATION, is_royal_heir=True, skills=_skills_totaling(7))
    assert is_unfinalized_royal_heir(leader) is False


def test_is_unfinalized_royal_heir_false_when_flag_is_not_set():
    leader = LeaderState(2, None, "Not a Heir", LOCATION, is_royal_heir=False, skills=_skills_totaling(0))
    assert is_unfinalized_royal_heir(leader) is False


def test_undead_king_conversion_table_matches_the_dossiers_own_worked_examples():
    # AKGEN_reverse_engineering_report (3).md SS94/SS94.1's own worked
    # table, every row starting from Alignment.DIVINE ("Heavenly").
    cases = [
        (1, Alignment.UNDEAD),  # T=0-1: budget 12, immediate conversion
        (2, Alignment.UNDEAD),  # T=2: budget 6, forced 6->7 jump still lands on Undead
        (3, Alignment.PAGAN),  # T=3: budget 4 -> Heavenly to "Animal" (Pagan)
        (4, Alignment.NEUTRAL),  # T=4: budget 3 -> Heavenly to "Worldly" (Neutral)
        (5, Alignment.DRUID),  # T=5-6: budget 2 -> Heavenly to Druidic
        (6, Alignment.DRUID),
        (7, Alignment.GOOD),  # T>=7: budget 1 -> Heavenly to Good
        (13, Alignment.GOOD),  # quotient hits 0, but the repeat still forces >= 1 step
    ]
    for total_skill, expected in cases:
        caster = _undead_king()
        target = LeaderState(2, 2, "Target", LOCATION, alignment=Alignment.DIVINE, skills=_skills_totaling(total_skill))

        _apply_undead_king_alignment_conversion(caster, target)

        assert target.alignment is expected, f"Total_USkill={total_skill}"


def test_undead_king_conversion_evil_target_jumps_through_anti_holy_to_undead():
    # SS94.1's own highlighted case: budget 1 lands on Anti-Holy (6), which
    # is never a valid resting alignment -- the loop is forced to take one
    # more step to Undead (7), two ordinal positions for one nominal step.
    caster = _undead_king()
    target = LeaderState(2, 2, "Target", LOCATION, alignment=Alignment.EVIL, skills=_skills_totaling(7))

    _apply_undead_king_alignment_conversion(caster, target)

    assert target.alignment is Alignment.UNDEAD


def test_undead_king_conversion_gated_on_caster_being_a_king_not_a_hero():
    # RQ.TXT:3248-3249: Undead Heroes never convert alignment via Charm.
    caster = LeaderState(1, 1, "Undead Hero", LOCATION, is_king=False, alignment=Alignment.UNDEAD)
    target = LeaderState(2, 2, "Target", LOCATION, alignment=Alignment.GOOD, skills=_skills_totaling(1))

    _apply_undead_king_alignment_conversion(caster, target)

    assert target.alignment is Alignment.GOOD


def test_undead_king_conversion_is_a_no_op_on_an_already_undead_target():
    caster = _undead_king()
    target = LeaderState(2, 2, "Target", LOCATION, alignment=Alignment.UNDEAD, skills=_skills_totaling(1))

    _apply_undead_king_alignment_conversion(caster, target)

    assert target.alignment is Alignment.UNDEAD


def test_undead_king_conversion_gated_on_no_pending_analytical_psychology_return():
    caster = _undead_king()
    target = LeaderState(2, 2, "Target", LOCATION, alignment=Alignment.GOOD, skills=_skills_totaling(1))
    target.analytical_psychology_revert_kingdom_id = 2

    _apply_undead_king_alignment_conversion(caster, target)

    assert target.alignment is Alignment.GOOD


def test_undead_king_conversion_skips_a_target_with_unrecorded_alignment():
    caster = _undead_king()
    target = LeaderState(2, 2, "Target", LOCATION, skills=_skills_totaling(1))
    assert target.alignment is None

    _apply_undead_king_alignment_conversion(caster, target)

    assert target.alignment is None


def test_charm_by_an_undead_king_converts_a_colocated_heros_alignment():
    state = build_state()
    state.leaders[CASTER_ID].alignment = Alignment.UNDEAD
    state.leaders[CASTER_ID].is_king = True
    state.leaders[CASTER_ID].skills = _skills_with(Ability.NECROMANCY, 2)
    state.add_leader(LeaderState(78, None, "Wandering Hero", LOCATION, alignment=Alignment.GOOD))
    request = CastRequest(spell=Spell.CHARM, target=78)
    rng = ScriptedRandom([0.44, 0.5, 0.5])  # 15% + 15%*2 = 45% chance

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is True
    assert state.leaders[78].kingdom_id == 1
    # target.skills is unrecorded -- Total_USkill reads 0, so max(1, 0) = 1
    # and the step budget (12) converts straight to Undead.
    assert state.leaders[78].alignment is Alignment.UNDEAD


def test_charm_by_an_undead_hero_does_not_convert_alignment():
    state = build_state()
    state.leaders[CASTER_ID].alignment = Alignment.UNDEAD
    state.leaders[CASTER_ID].is_king = False
    state.leaders[CASTER_ID].skills = _skills_with(Ability.NECROMANCY, 2)
    state.add_leader(LeaderState(78, None, "Wandering Hero", LOCATION, alignment=Alignment.GOOD))
    request = CastRequest(spell=Spell.CHARM, target=78)
    rng = ScriptedRandom([0.44, 0.5, 0.5])

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is True
    assert state.leaders[78].kingdom_id == 1
    assert state.leaders[78].alignment is Alignment.GOOD  # untouched -- Heroes never convert


def test_charm_own_hero_by_undead_king_with_analytical_psychology_still_converts():
    # Phase 522 fix: the AP-revert marker must NOT be set on a same-Kingdom
    # Charm (LKing doesn't change), so it can no longer spuriously block
    # the Undead King's own alignment-conversion gate on their own Hero --
    # the dossier's own confirmed case 6.
    state = build_state()
    state.kingdoms[1].discoveries.add(Discovery.ANALYTICAL_PSYCHOLOGY)
    state.leaders[CASTER_ID].alignment = Alignment.UNDEAD
    state.leaders[CASTER_ID].is_king = True
    state.leaders[CASTER_ID].skills = _skills_with(Ability.NECROMANCY, 2)
    state.add_leader(LeaderState(78, 1, "Loyal Hero", LOCATION, alignment=Alignment.GOOD))
    request = CastRequest(spell=Spell.CHARM, target=78)
    rng = ScriptedRandom([0.44, 0.5, 0.5])

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is True
    assert state.leaders[78].analytical_psychology_revert_kingdom_id is None
    assert state.leaders[78].alignment is Alignment.UNDEAD


def test_charm_on_own_already_loyal_hero_never_sets_the_revert_field_even_with_analytical_psychology():
    # General AP-marker fix, independent of Undead conversion: a Charm that
    # doesn't actually change kingdom_id must never record a revert target.
    state = build_state()
    state.kingdoms[1].discoveries.add(Discovery.ANALYTICAL_PSYCHOLOGY)
    state.add_leader(LeaderState(78, 1, "Already Loyal Hero", LOCATION))
    request = CastRequest(spell=Spell.CHARM, target=78)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is True
    assert state.leaders[78].kingdom_id == 1
    assert state.leaders[78].analytical_psychology_revert_kingdom_id is None


def test_kill_enemy_combatant_gives_the_imperial_defender_a_damage_reduction_of_one():
    # Phase 489: CARICHE E ABLITA.txt's own Office.DEFENDER perk ("reduce
    # any strike against you in personal combat ... by one damage point").
    state = build_state()
    state.leaders[CASTER_ID].merit_tally.monster_hp_defeated = 1  # meets OFFICE_MIN_POINTS[Office.DEFENDER]

    combatant = _kill_enemy_combatant(state, state.leaders[CASTER_ID], temper=Temper.BERSERK)

    assert combatant.damage_reduction == 1


def test_kill_enemy_combatant_reads_the_melee_hit_points_advanced_ability():
    # Phase 516: AdvancedAbility.MELEE_HIT_POINTS.
    state = build_state()
    state.leaders[CASTER_ID].advanced_abilities.add(AdvancedAbility.MELEE_HIT_POINTS)

    combatant = _kill_enemy_combatant(state, state.leaders[CASTER_ID], temper=Temper.BERSERK)

    assert combatant.has_melee_hit_points_ability is True


def test_kill_enemy_combatant_reads_melee_mastery():
    # Phase 517: AdvancedAbility.MELEE_MASTERY/MELEE_TRUE_MASTERY.
    state = build_state()
    state.leaders[CASTER_ID].advanced_abilities.add(AdvancedAbility.MELEE_MASTERY)

    combatant = _kill_enemy_combatant(state, state.leaders[CASTER_ID], temper=Temper.BERSERK)

    assert combatant.offensive_hit_multiplier == pytest.approx(1.10)
    assert combatant.melee_damage_dealt_bonus == 1


def test_kill_enemy_combatant_reads_melee_true_mastery():
    state = build_state()
    state.leaders[CASTER_ID].advanced_abilities.add(AdvancedAbility.MELEE_TRUE_MASTERY)

    combatant = _kill_enemy_combatant(state, state.leaders[CASTER_ID], temper=Temper.BERSERK)

    assert combatant.offensive_hit_multiplier == 1.0
    assert combatant.melee_damage_dealt_bonus == 2


def test_kill_enemy_combatant_reads_duellists_medal_and_kingdom_race_humanoid():
    # Phase 518: AdvancedAbility.MELEE_DUELLISTS_MEDAL + is_humanoid.
    state = build_state()
    state.leaders[CASTER_ID].advanced_abilities.add(AdvancedAbility.MELEE_DUELLISTS_MEDAL)

    combatant = _kill_enemy_combatant(state, state.leaders[CASTER_ID], temper=Temper.BERSERK)

    assert combatant.has_duellists_medal_ability is True
    assert combatant.is_humanoid is True


def test_kill_enemy_combatant_reads_control_temper_ability():
    # Phase 519: AdvancedAbility.MELEE_CONTROL_TEMPER.
    state = build_state()
    state.leaders[CASTER_ID].advanced_abilities.add(AdvancedAbility.MELEE_CONTROL_TEMPER)

    combatant = _kill_enemy_combatant(state, state.leaders[CASTER_ID], temper=Temper.BERSERK)

    assert combatant.has_control_temper_ability is True


def test_kill_enemy_combatant_reads_archery_free_attack_bonus():
    # Phase 520: AdvancedAbility.ARCHERY_FREE_ATTACK/_MASTERY/_TRUE_MASTERY.
    state = build_state()
    state.leaders[CASTER_ID].advanced_abilities.add(AdvancedAbility.ARCHERY_FREE_ATTACK)

    combatant = _kill_enemy_combatant(state, state.leaders[CASTER_ID], temper=Temper.BERSERK)

    assert combatant.archery_free_attack_bonus == 1


def test_kill_enemy_puts_a_colocated_target_into_a_coma():
    # Phase 310: this project's Kill_Enemy is only ever cast as an Action
    # spell -- see _execute_kill_enemy()'s own docstring for why a success
    # here always produces the Action-cast coma outcome, not death.
    state = build_state()
    state.add_leader(LeaderState(78, 2, "Enemy Hero", LOCATION))
    request = CastRequest(spell=Spell.KILL_ENEMY, target=78)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is True
    assert 78 in state.leaders  # comatose, not removed
    assert state.leaders[78].is_comatose is True
    # Phase 447: Grandfather of Assassins merit -- credited only at this
    # real lethal branch.
    assert state.leaders[CASTER_ID].merit_tally.successful_assassinations == 1


def test_kill_enemy_fails_when_target_holds_the_anti_necromancy_amulet():
    # Phase 531: The True Cross (Anti-Necromancy Amulet) personally
    # blocks Kill_Enemy -- checked before (and independent of) the
    # Hidden Tattoos Discovery ward.
    state = build_state()
    state.add_leader(LeaderState(78, 2, "Protected Enemy", LOCATION))
    state.add_item(Treasure.AMULET_ANTI_NECROMANCY, owner_leader_id=78)
    request = CastRequest(spell=Spell.KILL_ENEMY, target=78)
    rng = ScriptedRandom([0.1])

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is False
    assert result.reason == "target is immune (anti-magic amulet)"
    assert 78 in state.leaders
    assert state.leaders[78].is_comatose is False


def test_kill_enemy_fails_when_target_not_colocated():
    state = build_state()
    state.add_leader(LeaderState(78, 2, "Enemy Hero", ELSEWHERE))
    request = CastRequest(spell=Spell.KILL_ENEMY, target=78)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is False
    assert result.reason == "not co-located"
    assert 78 in state.leaders  # untouched


def test_kill_enemy_fails_when_target_does_not_exist():
    state = build_state()
    request = CastRequest(spell=Spell.KILL_ENEMY, target=999)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is False
    assert result.reason == "target character not found"


def test_kill_enemy_neutralized_by_hidden_tattoos():
    # Phase 270: Hidden Tattoos (Discovery.txt) protects every character
    # of the owning Kingdom from Kill Enemy -- the target survives.
    state = build_state()
    state.kingdoms[2].discoveries.add(Discovery.HIDDEN_TATTOOS)
    state.add_leader(LeaderState(78, 2, "Enemy Hero", LOCATION))
    request = CastRequest(spell=Spell.KILL_ENEMY, target=78)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is True
    assert result.discovery_defended is Discovery.HIDDEN_TATTOOS
    assert 78 in state.leaders  # survives
    assert state.leaders[78].is_comatose is False  # the ward blocks the coma too
    # Phase 447: disease, not death -- no Assassin merit credited.
    assert state.leaders[CASTER_ID].merit_tally.successful_assassinations == 0


# ---------------------------------------------------------------------------
# Kill_Enemy [4.25.2] Phase 310 addendum: King immunity, the Special-Place/
# army-leading-Hero halving, and the Berserk counterattack on failure
# ---------------------------------------------------------------------------


def test_kill_enemy_fails_outright_against_a_king_no_roll_consumed():
    state = build_state()
    state.add_leader(LeaderState(78, 2, "Enemy King", LOCATION, is_king=True))
    request = CastRequest(spell=Spell.KILL_ENEMY, target=78)
    rng = ScriptedRandom([])  # no roll, no melee -- King immunity short-circuits first

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is False
    assert result.reason == "target is a King, immune to Kill Enemy"
    assert 78 in state.leaders
    assert state.leaders[78].is_comatose is False
    assert state.leaders[CASTER_ID].merit_tally.successful_assassinations == 0


def test_kill_enemy_halves_the_chance_against_an_army_leading_hero():
    # Real, seeded RNG, not ScriptedRandom -- a failed cast here falls
    # through into the real Berserk-counterattack melee (see the two
    # dedicated Berserk tests below for why that needs a real RNG, not a
    # short scripted list). Seed 3's own first roll (~0.238) is under the
    # un-halved 30% chance but over the halved 15% -- proving the
    # halving, not just "some roll failed."
    state = build_state()
    state.leaders[CASTER_ID].skills = _skills_with(Ability.NECROMANCY, 1)  # 30% base, 15% halved
    state.add_leader(LeaderState(78, 2, "Enemy Hero", LOCATION))
    state.add_army(ArmyState(201, 2, ArmyType.LEGION, Quality.AVERAGE, LOCATION, commanded_by=78))
    request = CastRequest(spell=Spell.KILL_ENEMY, target=78)
    rng = random.Random(3)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is False
    assert result.reason == "spell failed"


def test_kill_enemy_halves_the_chance_in_a_special_place_province():
    # Same seed-3 reasoning as the army-leading-Hero test above.
    state = build_state()
    state.leaders[CASTER_ID].skills = _skills_with(Ability.NECROMANCY, 1)  # 30% base, 15% halved
    state.add_leader(LeaderState(78, 2, "Enemy Hero", LOCATION))  # leads no army -- the province alone triggers it
    state.add_feature(Feature(1, LOCATION, FeatureType.TOWER))
    request = CastRequest(spell=Spell.KILL_ENEMY, target=78)
    rng = random.Random(3)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is False
    assert result.reason == "spell failed"


def test_kill_enemy_full_chance_against_an_unled_hero_in_an_ordinary_province():
    # Neither halving condition applies -- the same 30% roll that fails
    # above (halved to 15%) succeeds here at full strength.
    state = build_state()
    state.leaders[CASTER_ID].skills = _skills_with(Ability.NECROMANCY, 1)
    state.add_leader(LeaderState(78, 2, "Enemy Hero", LOCATION))
    request = CastRequest(spell=Spell.KILL_ENEMY, target=78)
    rng = ScriptedRandom([0.20, 0.5, 0.5])

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is True
    assert state.leaders[78].is_comatose is True


def test_kill_enemy_berserk_counterattack_kills_the_caster_on_a_failed_cast():
    # Real, seeded RNG rather than ScriptedRandom -- the Berserk temper's
    # own Furia bonus-hit-points roll (turn/encounter.py
    # berserk_fury_bonus_hit_points()) goes through rng.randint(), which
    # ScriptedRandom doesn't intercept (same reason test_encounter.py's
    # own apply_temper_melee_setup tests use random.Random(0), not
    # ScriptedRandom). Seed 0 empirically produces a real cast failure
    # followed by the retaliating target winning the melee.
    state = build_state()
    state.add_leader(LeaderState(78, 2, "Enemy Hero", LOCATION))
    state.leaders[CASTER_ID].skills = _skills_with(Ability.NECROMANCY, 1)  # 30% chance
    item = state.add_item(Treasure.ABILITY_MELEE, owner_leader_id=CASTER_ID)
    request = CastRequest(spell=Spell.KILL_ENEMY, target=78)
    rng = random.Random(0)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is False
    assert result.reason == "spell failed"
    assert result.kill_enemy_berserk_winner == "b"
    assert CASTER_ID not in state.leaders  # the caster died to the retaliation
    assert 78 in state.leaders  # the Berserk retaliator survived
    # Phase 313, rulebook [5.9]: the retaliator loots the dead caster's items.
    assert result.looted_item_ids == [item.item_id]
    assert state.items[item.item_id].owner_leader_id == 78
    # Phase 447: a failed cast (Berserk counterattack) never credits Assassin merit.
    assert state.dead_leaders[CASTER_ID].merit_tally.successful_assassinations == 0
    # Phase 612: the duel's own per-round detail survives for narration.
    assert len(result.melee_swings) > 0


def test_kill_enemy_berserk_counterattack_caster_survives_and_kills_the_retaliator():
    # Same reasoning as above -- seed 10 empirically produces a real cast
    # failure followed by the caster winning the melee instead.
    state = build_state()
    state.add_leader(LeaderState(78, 2, "Enemy Hero", LOCATION))
    state.leaders[CASTER_ID].skills = _skills_with(Ability.NECROMANCY, 1)  # 30% chance
    # Phase 534: a non-ability item -- ABILITY_MELEE would now also bump
    # the retaliator's own effective Melee skill (ability_bonus_from_
    # items()), perturbing this seed's own melee outcome; any inert item
    # still exercises the same looting mechanic.
    item = state.add_item(Treasure.AMULET_ANTI_WHITE, owner_leader_id=78)
    request = CastRequest(spell=Spell.KILL_ENEMY, target=78)
    rng = random.Random(10)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is False
    assert result.reason == "spell failed"
    assert result.kill_enemy_berserk_winner == "a"
    assert CASTER_ID in state.leaders  # the caster survived
    assert 78 not in state.leaders  # the Berserk retaliator died
    # Phase 313, rulebook [5.9]: the surviving caster loots the retaliator.
    assert result.looted_item_ids == [item.item_id]
    assert state.items[item.item_id].owner_leader_id == CASTER_ID
    # Phase 447: a failed cast (Berserk counterattack) never credits Assassin merit.
    assert state.leaders[CASTER_ID].merit_tally.successful_assassinations == 0
    # Phase 612: the duel's own per-round detail survives for narration.
    assert len(result.melee_swings) > 0


def test_charm_succeeds_on_a_real_roll_under_the_casters_chance():
    # Rulebook [3.10]: 15% + 15%/level. Psychic level 2 -> 45% chance.
    state = build_state()
    state.leaders[CASTER_ID].skills = _skills_with(Ability.PSYCHIC, 2)
    state.add_leader(LeaderState(78, None, "Wandering Hero", LOCATION))
    request = CastRequest(spell=Spell.CHARM, target=78)
    rng = ScriptedRandom([0.44, 0.5, 0.5])

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is True
    assert state.leaders[78].kingdom_id == 1


def test_charm_fails_on_a_real_roll_over_the_casters_chance():
    state = build_state()
    state.leaders[CASTER_ID].skills = _skills_with(Ability.PSYCHIC, 2)
    state.add_leader(LeaderState(78, None, "Wandering Hero", LOCATION))
    request = CastRequest(spell=Spell.CHARM, target=78)
    rng = ScriptedRandom([0.99])

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is False
    assert result.reason == "spell failed"
    assert state.leaders[78].kingdom_id is None  # untouched


def test_charm_fails_outright_when_caster_has_no_skill_in_the_ability():
    state = build_state()
    state.leaders[CASTER_ID].skills = _skills_with(Ability.PSYCHIC, 0)
    state.add_leader(LeaderState(78, None, "Wandering Hero", LOCATION))
    request = CastRequest(spell=Spell.CHARM, target=78)
    rng = ScriptedRandom([])  # no roll consumed -- precondition fails first

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is False
    assert result.reason == "insufficient skill"


def test_kill_enemy_success_roll_uses_necromancy_skill():
    state = build_state()
    state.leaders[CASTER_ID].skills = _skills_with(Ability.NECROMANCY, 1)
    state.add_leader(LeaderState(78, 2, "Enemy Hero", LOCATION))
    request = CastRequest(spell=Spell.KILL_ENEMY, target=78)
    rng = ScriptedRandom([0.29, 0.5, 0.5])  # 15% + 15%*1 = 30% chance

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is True
    assert state.leaders[78].is_comatose is True


def test_cast_always_succeeds_when_caster_has_no_skills_recorded():
    # LeaderState.skills is None by default -- see cast_execution.py's
    # module docstring for why this preserves pre-Phase-30 behavior.
    state = build_state()
    assert state.leaders[CASTER_ID].skills is None
    state.add_leader(LeaderState(78, None, "Wandering Hero", LOCATION))
    request = CastRequest(spell=Spell.CHARM, target=78)
    rng = ScriptedRandom([])  # no roll consumed

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is True


def test_unmodeled_spells_report_a_reason_without_touching_state():
    # Holy_Symbol is one of the ten Personal-Combat-only spells -- see the
    # module docstring for why those still have no Action-Cast dispatch
    # branch. Representative of every other real spell this project
    # doesn't execute this way (see the module docstring's full list).
    state = build_state()
    request = CastRequest(spell=Spell.HOLY_SYMBOL, target=0)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is False
    assert result.reason == "spell effect not modeled"


# ---------------------------------------------------------------------------
# Resurrection (Phase 59) -- Regolamento AK.txt [4.21.1]
# ---------------------------------------------------------------------------


def test_resurrection_revives_a_dead_leader_co_located_with_caster():
    state = build_state()
    dead = LeaderState(78, 2, "Fallen Hero", LOCATION)
    state.dead_leaders[78] = dead
    request = CastRequest(spell=Spell.RESURRECTION, target=78)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is True
    assert 78 not in state.dead_leaders
    assert state.leaders[78] is dead
    assert state.leaders[78].kingdom_id == 1


def test_resurrection_fails_when_target_is_not_a_dead_leader():
    state = build_state()
    state.add_leader(LeaderState(78, 2, "Very Much Alive", LOCATION))  # alive, not in dead_leaders
    request = CastRequest(spell=Spell.RESURRECTION, target=78)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is False
    assert result.reason == "target character not found"


def test_resurrection_increments_the_casters_merit_tally_on_success():
    state = build_state()
    state.dead_leaders[78] = LeaderState(78, 2, "Fallen Hero", LOCATION)
    request = CastRequest(spell=Spell.RESURRECTION, target=78)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is True
    assert state.leaders[CASTER_ID].merit_tally.resurrection_bless_casts == 1


def test_resurrection_fails_when_dead_leader_died_elsewhere():
    state = build_state()
    state.dead_leaders[78] = LeaderState(78, 2, "Fallen Hero", ELSEWHERE)
    request = CastRequest(spell=Spell.RESURRECTION, target=78)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is False
    assert state.leaders[CASTER_ID].merit_tally.resurrection_bless_casts == 0  # no cast on failure
    assert result.reason == "not co-located"
    assert 78 in state.dead_leaders  # untouched


# ---------------------------------------------------------------------------
# Resurrection: AdvancedAbility.ENHANCED_RESURRECTION (Phase 498)
# ---------------------------------------------------------------------------


def test_resurrection_with_enhanced_ability_matches_the_casters_kings_alignment():
    # kingdom_id=1 ("Testia") is Alignment.GOOD in build_state(); the dead
    # Hero starts Alignment.EVIL to make the change unmistakable.
    state = build_state()
    state.leaders[CASTER_ID].advanced_abilities.add(AdvancedAbility.ENHANCED_RESURRECTION)
    state.dead_leaders[78] = LeaderState(78, 2, "Fallen Hero", LOCATION, alignment=Alignment.EVIL)
    request = CastRequest(spell=Spell.RESURRECTION, target=78)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is True
    assert state.leaders[78].alignment is Alignment.GOOD


def test_resurrection_without_enhanced_ability_leaves_alignment_untouched():
    state = build_state()
    state.dead_leaders[78] = LeaderState(78, 2, "Fallen Hero", LOCATION, alignment=Alignment.EVIL)
    request = CastRequest(spell=Spell.RESURRECTION, target=78)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is True
    assert state.leaders[78].alignment is Alignment.EVIL


# ---------------------------------------------------------------------------
# Resurrection curing a Kill_Enemy coma (Phase 310) -- [4.25.2]
# ---------------------------------------------------------------------------


def test_resurrection_cures_a_coma_and_keeps_the_original_kingdom():
    # User-clarified 2026-07-31: unlike an ordinary dead-Hero revival,
    # curing a coma never changes kingdom_id, even cast by a foreign
    # hero/King -- the comatose leader stays a co-located, living
    # LeaderState the whole time, never entering dead_leaders.
    state = build_state()
    comatose = LeaderState(78, 2, "Comatose Hero", LOCATION, is_comatose=True)
    state.add_leader(comatose)
    request = CastRequest(spell=Spell.RESURRECTION, target=78)

    # CASTER_ID belongs to kingdom 1, the comatose Hero to kingdom 2.
    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is True
    assert state.leaders[78] is comatose  # same object, never removed/replaced
    assert state.leaders[78].is_comatose is False
    assert state.leaders[78].kingdom_id == 2  # unchanged, despite a kingdom-1 caster
    assert state.leaders[CASTER_ID].merit_tally.resurrection_bless_casts == 1


def test_resurrection_does_not_cure_a_coma_when_not_co_located():
    state = build_state()
    state.add_leader(LeaderState(78, 2, "Comatose Hero", ELSEWHERE, is_comatose=True))
    request = CastRequest(spell=Spell.RESURRECTION, target=78)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is False
    assert result.reason == "not co-located"
    assert state.leaders[78].is_comatose is True  # untouched
    assert state.leaders[CASTER_ID].merit_tally.resurrection_bless_casts == 0


def test_resurrection_does_not_cure_a_coma_on_a_failed_roll():
    state = build_state()
    state.leaders[CASTER_ID].skills = _skills_with(Ability.WHITE, 1)  # 30% chance
    state.add_leader(LeaderState(78, 2, "Comatose Hero", LOCATION, is_comatose=True))
    request = CastRequest(spell=Spell.RESURRECTION, target=78)
    rng = ScriptedRandom([0.99])  # over 30%

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is False
    assert result.reason == "spell failed"
    assert state.leaders[78].is_comatose is True


def test_resurrection_coma_cure_does_not_restore_the_real_stored_skills_it_never_touched():
    # No "restoration" logic exists because the real values were never
    # mutated -- clearing is_comatose alone un-hides them everywhere
    # effective_skill_level() reads them (see that field's own docstring).
    state = build_state()
    comatose = LeaderState(78, 2, "Comatose Hero", LOCATION, is_comatose=True, skills=_skills_with(Ability.MELEE, 4))
    state.add_leader(comatose)
    request = CastRequest(spell=Spell.RESURRECTION, target=78)

    execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert state.leaders[78].skills.pair_for_ability(Ability.MELEE) == (4, 0)


# ---------------------------------------------------------------------------
# Resurrection on a Royal Heir (Phase 259) -- RULES.AK [4.21.1]
# ---------------------------------------------------------------------------


def test_resurrection_on_a_royal_heir_restores_the_exact_dead_king():
    state = build_state()
    dead_king = LeaderState(78, 2, "Old King", LOCATION, is_king=True, temper=None, alignment=Alignment.EVIL)
    state.dead_leaders[78] = dead_king
    heir = LeaderState(
        78, 2, "Old King", LOCATION, is_king=True, is_royal_heir=True, skills=SkillTable(raw_values=[0] * 31)
    )
    state.add_leader(heir)
    request = CastRequest(spell=Spell.RESURRECTION, target=78)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is True
    assert 78 not in state.dead_leaders
    assert state.leaders[78] is dead_king  # the exact original, not a fresh copy
    assert state.leaders[78].kingdom_id == 2  # resumes his own throne, not the caster's (kingdom 1)


def test_resurrection_on_a_royal_heir_by_another_kingdoms_caster_still_resumes_his_own_throne():
    # RULES.AK: "If another player casts a Resurrection spell on your
    # Royal Heir, you still get your old King back."
    state = build_state()
    dead_king = LeaderState(78, 2, "Old King", ELSEWHERE, is_king=True)
    state.dead_leaders[78] = dead_king
    state.add_leader(LeaderState(78, 2, "Old King", ELSEWHERE, is_king=True, is_royal_heir=True))
    request = CastRequest(spell=Spell.RESURRECTION, target=78)

    # CASTER_ID (kingdom 1) casts on kingdom 2's own Royal Heir.
    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is False  # not co-located (Heir is ELSEWHERE) -- confirms co-location still checked
    assert result.reason == "not co-located"

    state.leaders[78].location = LOCATION
    result2 = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result2.applied is True
    assert state.leaders[78].kingdom_id == 2  # stays kingdom 2's King, despite kingdom 1 casting


def test_resurrection_on_a_royal_heir_fails_without_an_archived_king():
    state = build_state()
    state.add_leader(LeaderState(78, 2, "Heir Only", LOCATION, is_king=True, is_royal_heir=True))
    request = CastRequest(spell=Spell.RESURRECTION, target=78)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is False
    assert result.reason == "target character not found"


def test_resurrection_on_a_royal_heir_past_the_threshold_is_refused():
    # Phase 553: heir.is_royal_heir alone is no longer enough -- once
    # Total_USkill(heir) reaches 7, the option is gone even though the
    # flag itself is untouched (see is_unfinalized_royal_heir()'s own
    # docstring; the flag is cleared only by create_king() or a
    # successful Resurrection).
    state = build_state()
    state.dead_leaders[78] = LeaderState(78, 2, "Old King", LOCATION, is_king=True)
    trained_skills = SkillTable(raw_values=[0] * 31)
    trained_skills.set_pair_for_ability(Ability.MELEE, skill=7, aptitude=9)
    state.add_leader(
        LeaderState(78, 2, "Old King", LOCATION, is_king=True, is_royal_heir=True, skills=trained_skills)
    )
    request = CastRequest(spell=Spell.RESURRECTION, target=78)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is False
    assert result.reason == "Royal Heir has trained past the Resurrection threshold"
    assert 78 in state.dead_leaders  # archived King left untouched, not consumed
    assert state.leaders[78].is_royal_heir is True  # flag itself still not cleared by this refusal


def test_resurrection_on_a_royal_heir_increments_the_casters_merit_tally():
    state = build_state()
    state.dead_leaders[78] = LeaderState(78, 2, "Old King", LOCATION, is_king=True)
    state.add_leader(LeaderState(78, 2, "Old King", LOCATION, is_king=True, is_royal_heir=True))
    request = CastRequest(spell=Spell.RESURRECTION, target=78)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is True
    assert state.leaders[CASTER_ID].merit_tally.resurrection_bless_casts == 1


# ---------------------------------------------------------------------------
# Part Sea (Phase 59) -- Regolamento AK.txt [4.21.2]
# ---------------------------------------------------------------------------


def test_part_sea_turns_a_sea_province_into_plains():
    state = build_state()
    state.add_province(ProvinceState(LOCATION, Terrain.SEA, Race.HUMAN))
    request = CastRequest(spell=Spell.PART_SEA, target=_target(LOCATION))

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is True
    assert state.provinces[LOCATION].terrain_override is Terrain.PLAINS


def test_part_sea_fails_on_a_non_sea_province():
    state = build_state()
    state.add_province(ProvinceState(LOCATION, Terrain.PLAINS, Race.HUMAN))
    request = CastRequest(spell=Spell.PART_SEA, target=_target(LOCATION))

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is False
    assert result.reason == "target province is not Sea"
    assert state.provinces[LOCATION].terrain_override is None


def test_part_sea_fails_on_a_province_out_of_range():
    state = build_state()
    state.add_province(ProvinceState(LOCATION, Terrain.SEA, Race.HUMAN))
    state.add_province(ProvinceState(ELSEWHERE, Terrain.SEA, Race.HUMAN))
    request = CastRequest(spell=Spell.PART_SEA, target=_target(ELSEWHERE))

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is False
    assert result.reason == "province not found or not in range"


def test_part_sea_succeeds_on_an_adjacent_province():
    state = build_state()
    bounds = MapBounds(*NORMAL_MAP_BOUNDS)
    adjacent = neighbors(LOCATION, bounds)[0]
    state.add_province(ProvinceState(LOCATION, Terrain.PLAINS, Race.HUMAN))
    state.add_province(ProvinceState(adjacent, Terrain.SEA, Race.HUMAN))
    request = CastRequest(spell=Spell.PART_SEA, target=_target(adjacent))

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is True
    assert state.provinces[adjacent].terrain_override is Terrain.PLAINS


def test_part_sea_succeeds_on_a_province_flooded_to_sea_via_override():
    # Phase 168: eligibility must read effective_terrain() -- a province
    # whose base terrain is Plains but has been Flooded to Sea
    # (terrain_override) is really Sea right now, so Part Sea can target it.
    state = build_state()
    state.add_province(ProvinceState(LOCATION, Terrain.PLAINS, Race.HUMAN, terrain_override=Terrain.SEA))
    request = CastRequest(spell=Spell.PART_SEA, target=_target(LOCATION))

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is True
    assert state.provinces[LOCATION].terrain_override is Terrain.PLAINS


def test_part_sea_fails_when_target_province_is_unknown():
    state = build_state()
    request = CastRequest(spell=Spell.PART_SEA, target=_target(LOCATION))

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is False
    assert result.reason == "province not found or not in range"


# ---------------------------------------------------------------------------
# Flood Province (Phase 59) -- Regolamento AK.txt [4.24.1]
# ---------------------------------------------------------------------------


def test_flood_turns_a_land_province_into_sea():
    state = build_state()
    state.add_province(ProvinceState(LOCATION, Terrain.PLAINS, Race.HUMAN))
    request = CastRequest(spell=Spell.FLOOD, target=_target(LOCATION))

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is True
    assert state.provinces[LOCATION].terrain_override is Terrain.SEA


def test_flood_fails_on_a_mountain_province():
    state = build_state()
    state.add_province(ProvinceState(LOCATION, Terrain.MTNS, Race.HUMAN))
    request = CastRequest(spell=Spell.FLOOD, target=_target(LOCATION))

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is False
    assert result.reason == "target province is not a non-mountain land province"


def test_flood_fails_on_an_already_sea_province():
    state = build_state()
    state.add_province(ProvinceState(LOCATION, Terrain.SEA, Race.HUMAN))
    request = CastRequest(spell=Spell.FLOOD, target=_target(LOCATION))

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is False
    assert result.reason == "target province is not a non-mountain land province"


def test_flood_fails_on_a_province_already_flooded_to_sea_via_override():
    # Phase 168: a province whose base terrain is still Plains but has
    # already been Flooded to Sea (terrain_override) must be rejected the
    # same as a genuinely Sea province -- effective_terrain() is what
    # eligibility now reads.
    state = build_state()
    state.add_province(ProvinceState(LOCATION, Terrain.PLAINS, Race.HUMAN, terrain_override=Terrain.SEA))
    request = CastRequest(spell=Spell.FLOOD, target=_target(LOCATION))

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is False
    assert result.reason == "target province is not a non-mountain land province"


# ---------------------------------------------------------------------------
# Tornado (Phase 59) -- Regolamento AK.txt [4.24.2]
# ---------------------------------------------------------------------------


def test_tornado_destroys_units_that_roll_under_the_per_level_chance():
    state = build_state()
    state.add_province(ProvinceState(LOCATION, Terrain.PLAINS, Race.HUMAN))
    state.leaders[CASTER_ID].skills = _skills_with(Ability.ELEMENTAL, 2)  # 20% destroy chance
    state.add_army(ArmyState(1, 1, ArmyType.LEGION, Quality.AVERAGE, LOCATION))  # caster's own army
    state.add_army(ArmyState(2, 2, ArmyType.BOWMEN, Quality.AVERAGE, LOCATION))  # enemy army
    request = CastRequest(spell=Spell.TORNADO, target=_target(LOCATION))
    # rolls: [0] cast-success roll, [1] army 1 destroy roll (hits), [2] army 2 destroy roll (misses)
    rng = ScriptedRandom([0.01, 0.19, 0.99, 0.5, 0.5])

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is True
    assert 1 not in state.armies  # own army destroyed too -- no ownership exemption
    assert 2 in state.armies


def test_tornado_destroys_nothing_when_caster_has_no_recorded_level():
    state = build_state()
    state.add_province(ProvinceState(LOCATION, Terrain.PLAINS, Race.HUMAN))
    state.add_army(ArmyState(1, 2, ArmyType.BOWMEN, Quality.AVERAGE, LOCATION))
    request = CastRequest(spell=Spell.TORNADO, target=_target(LOCATION))
    rng = ScriptedRandom([0.0])  # would destroy at any nonzero chance -- see module docstring

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is True
    assert 1 in state.armies  # unknown level -> 0% chance, nothing destroyed


def test_tornado_giant_fan_downgrades_quality_instead_of_destroying():
    # Phase 270: Giant Fan (Discovery.txt) -- a 50% chance of losing one
    # quality level instead of being destroyed, checked against the
    # army's own Kingdom.
    state = build_state()
    state.kingdoms[2].discoveries.add(Discovery.GIANT_FAN)
    state.add_province(ProvinceState(LOCATION, Terrain.PLAINS, Race.HUMAN))
    state.leaders[CASTER_ID].skills = _skills_with(Ability.ELEMENTAL, 2)  # 20% destroy chance
    state.add_army(ArmyState(2, 2, ArmyType.BOWMEN, Quality.AVERAGE, LOCATION))
    request = CastRequest(spell=Spell.TORNADO, target=_target(LOCATION))
    # rolls: [0] cast-success roll, [1] army 2's downgrade roll (hits, at flat 50%)
    rng = ScriptedRandom([0.01, 0.49, 0.5, 0.5])

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is True
    assert result.discovery_defended is Discovery.GIANT_FAN
    assert 2 in state.armies  # never destroyed
    assert state.armies[2].quality == Quality.GREEN  # one level down from AVERAGE


# ---------------------------------------------------------------------------
# Earthquake (Phase 59) -- Regolamento AK.txt [4.24.3]
# ---------------------------------------------------------------------------


def test_earthquake_zeroes_the_tax_modifier_on_a_land_province():
    state = build_state()
    state.add_province(ProvinceState(LOCATION, Terrain.PLAINS, Race.HUMAN))
    request = CastRequest(spell=Spell.EARTHQUAKE, target=_target(LOCATION))

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is True
    assert state.provinces[LOCATION].tax_modifier_percent == -100


def test_earthquake_reinforced_concrete_applies_flat_reduction_instead():
    # Phase 270: Reinforced Concrete (Discovery.txt) -- replaces the
    # -100% effect with a flat 3-gold reduction, checked against the
    # province owner's own Kingdom.
    state = build_state()
    state.kingdoms[2].discoveries.add(Discovery.REINFORCED_CONCRETE)
    state.add_province(ProvinceState(LOCATION, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2))
    request = CastRequest(spell=Spell.EARTHQUAKE, target=_target(LOCATION))

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is True
    assert result.discovery_defended is Discovery.REINFORCED_CONCRETE
    assert state.provinces[LOCATION].tax_modifier_percent == 0  # untouched
    assert state.provinces[LOCATION].earthquake_flat_reduction == 3


def test_earthquake_fails_on_a_sea_province():
    state = build_state()
    state.add_province(ProvinceState(LOCATION, Terrain.SEA, Race.HUMAN))
    request = CastRequest(spell=Spell.EARTHQUAKE, target=_target(LOCATION))

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is False
    assert result.reason == "target province is not land"


def test_earthquake_fails_on_a_province_flooded_to_sea_via_override():
    # Phase 168: Earthquake must refuse a province Flooded to Sea even
    # though its base terrain is still land -- effective_terrain() is the
    # real current terrain, not the frozen base field.
    state = build_state()
    state.add_province(ProvinceState(LOCATION, Terrain.PLAINS, Race.HUMAN, terrain_override=Terrain.SEA))
    request = CastRequest(spell=Spell.EARTHQUAKE, target=_target(LOCATION))

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is False
    assert result.reason == "target province is not land"


# ---------------------------------------------------------------------------
# Bless (Phase 59) -- Regolamento AK.txt [4.21.3]
# ---------------------------------------------------------------------------


def test_bless_sets_the_tax_bonus_on_any_province_regardless_of_distance():
    state = build_state()
    state.add_province(ProvinceState(ELSEWHERE, Terrain.PLAINS, Race.HUMAN))
    request = CastRequest(spell=Spell.BLESS, target=_target(ELSEWHERE))

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is True
    assert state.provinces[ELSEWHERE].tax_modifier_percent == 60


def test_bless_increments_the_casters_merit_tally_on_success():
    state = build_state()
    state.add_province(ProvinceState(ELSEWHERE, Terrain.PLAINS, Race.HUMAN))
    request = CastRequest(spell=Spell.BLESS, target=_target(ELSEWHERE))

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is True
    assert state.leaders[CASTER_ID].merit_tally.resurrection_bless_casts == 1


def test_bless_fails_when_target_province_is_unknown():
    state = build_state()
    request = CastRequest(spell=Spell.BLESS, target=_target(ELSEWHERE))

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is False
    assert result.reason == "province not found"


# ---------------------------------------------------------------------------
# Illusory Terrain (Phase 59) -- Regolamento AK.txt [4.23.1]
# ---------------------------------------------------------------------------


def test_illus_terrain_records_the_fake_terrain_on_the_province():
    state = build_state()
    state.add_province(ProvinceState(LOCATION, Terrain.PLAINS, Race.HUMAN))
    request = CastRequest(spell=Spell.ILLUS_TERRAIN, target=_target(LOCATION), terrain=Terrain.FOREST)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is True
    assert state.provinces[LOCATION].illusory_terrain is Terrain.FOREST


def test_illus_terrain_fails_without_a_fake_terrain_specified():
    state = build_state()
    state.add_province(ProvinceState(LOCATION, Terrain.PLAINS, Race.HUMAN))
    request = CastRequest(spell=Spell.ILLUS_TERRAIN, target=_target(LOCATION))  # terrain left as None

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is False
    assert result.reason == "fake terrain not specified"


# ---------------------------------------------------------------------------
# Phantasmal Armies / Illus_Armies (Phase 59) -- Regolamento AK.txt [4.23.2]
# ---------------------------------------------------------------------------


def test_illus_armies_sets_the_casters_illusion_level_on_a_colocated_target():
    state = build_state()
    state.leaders[CASTER_ID].skills = _skills_with(Ability.ILLUSION, 3)
    state.add_leader(LeaderState(78, 1, "Field Commander", LOCATION))
    request = CastRequest(spell=Spell.ILLUS_ARMIES, target=78)
    rng = ScriptedRandom([0.01, 0.5, 0.5])  # 15% + 15%*3 = 60% chance

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is True
    assert state.leaders[78].phantasmal_armies_level == 3


def test_illus_armies_can_target_the_caster_himself():
    state = build_state()
    state.leaders[CASTER_ID].skills = _skills_with(Ability.ILLUSION, 2)
    request = CastRequest(spell=Spell.ILLUS_ARMIES, target=CASTER_ID)
    rng = ScriptedRandom([0.01, 0.5, 0.5])  # 15% + 15%*2 = 45% chance

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is True
    assert state.leaders[CASTER_ID].phantasmal_armies_level == 2


# ---------------------------------------------------------------------------
# Oratory (Phase 59) -- Regolamento AK.txt [4.22.2]
# ---------------------------------------------------------------------------


def test_oratory_bumps_quality_one_rank_for_every_army_the_target_commands():
    state = build_state()
    state.add_leader(LeaderState(78, 1, "Field Commander", LOCATION))
    state.add_army(ArmyState(1, 1, ArmyType.LEGION, Quality.GREEN, LOCATION, commanded_by=78))
    state.add_army(ArmyState(2, 1, ArmyType.BOWMEN, Quality.AVERAGE, LOCATION, commanded_by=78))
    request = CastRequest(spell=Spell.ORATORY, target=78)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is True
    assert state.armies[1].quality is Quality.AVERAGE
    assert state.armies[2].quality is Quality.VETERAN


def test_oratory_caps_at_elite():
    state = build_state()
    state.add_leader(LeaderState(78, 1, "Field Commander", LOCATION))
    state.add_army(ArmyState(1, 1, ArmyType.LEGION, Quality.ELITE, LOCATION, commanded_by=78))
    request = CastRequest(spell=Spell.ORATORY, target=78)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is True
    assert state.armies[1].quality is Quality.ELITE


def test_oratory_is_not_cumulative_on_a_second_cast_the_same_turn():
    state = build_state()
    state.add_leader(LeaderState(78, 1, "Field Commander", LOCATION))
    state.add_army(ArmyState(1, 1, ArmyType.LEGION, Quality.GREEN, LOCATION, commanded_by=78))
    request = CastRequest(spell=Spell.ORATORY, target=78)

    first = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)
    second = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert first.applied is True
    assert second.applied is True  # the cast itself still succeeds
    assert state.armies[1].quality is Quality.AVERAGE  # but only bumped once


# -- Phase 391: Propaganda Megaphones (vs Oratory) --


def test_oratory_propaganda_megaphones_blocks_the_boost_when_the_roll_misses():
    state = build_state()
    state.kingdoms[1].discoveries.add(Discovery.PROPAGANDA_MEGAPHONES)
    state.add_leader(LeaderState(78, 1, "Field Commander", LOCATION))
    state.add_army(ArmyState(1, 1, ArmyType.LEGION, Quality.GREEN, LOCATION, commanded_by=78))
    request = CastRequest(spell=Spell.ORATORY, target=78)

    result = execute_cast(
        state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=ScriptedRandom([0.99])
    )

    assert result.applied is True
    assert result.discovery_defended is Discovery.PROPAGANDA_MEGAPHONES
    assert state.armies[1].quality is Quality.GREEN  # the 33% roll missed -- no boost


def test_oratory_propaganda_megaphones_still_boosts_when_the_roll_hits():
    state = build_state()
    state.kingdoms[1].discoveries.add(Discovery.PROPAGANDA_MEGAPHONES)
    state.add_leader(LeaderState(78, 1, "Field Commander", LOCATION))
    state.add_army(ArmyState(1, 1, ArmyType.LEGION, Quality.GREEN, LOCATION, commanded_by=78))
    request = CastRequest(spell=Spell.ORATORY, target=78)

    result = execute_cast(
        state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=ScriptedRandom([0.01])
    )

    assert result.applied is True
    assert result.discovery_defended is Discovery.PROPAGANDA_MEGAPHONES
    assert state.armies[1].quality is Quality.AVERAGE  # the 33% roll hit -- boosted anyway


def test_oratory_without_propaganda_megaphones_never_rolls_and_always_boosts():
    state = build_state()
    state.add_leader(LeaderState(78, 1, "Field Commander", LOCATION))
    state.add_army(ArmyState(1, 1, ArmyType.LEGION, Quality.GREEN, LOCATION, commanded_by=78))
    request = CastRequest(spell=Spell.ORATORY, target=78)
    rng = ScriptedRandom([])  # no Discovery -- no per-army roll, IndexError if one is attempted

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is True
    assert result.discovery_defended is None
    assert state.armies[1].quality is Quality.AVERAGE


# -- Phase 387: action_slots_per_school --


def test_action_cast_slots_matches_the_documented_level_tiers():
    assert action_cast_slots(1) == 1
    assert action_cast_slots(2) == 1
    assert action_cast_slots(3) == 2
    assert action_cast_slots(4) == 3
    assert action_cast_slots(9) == 3


def test_execute_cast_exhausts_the_single_slot_at_low_level():
    state = build_state()
    state.leaders[CASTER_ID].skills = _skills_with(Ability.PSYCHIC, 1)  # 1 action-cast slot
    state.add_leader(LeaderState(78, 1, "Field Commander", LOCATION))
    state.add_army(ArmyState(1, 1, ArmyType.LEGION, Quality.GREEN, LOCATION, commanded_by=78))
    request = CastRequest(spell=Spell.ORATORY, target=78)
    # both cast rolls would succeed if a slot were available; the second
    # call fails at the slot check, before any roll, so only the first
    # (successful) call's own Add_Experience draws need padding.
    rng = ScriptedRandom([0.01, 0.5, 0.5, 0.01])

    first = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)
    second = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert first.applied is True
    assert second.applied is False
    assert second.reason == "no action-cast slots remaining this turn for this ability"


def test_execute_cast_slots_scoped_to_ability_allow_two_casts_at_level_3():
    state = build_state()
    state.leaders[CASTER_ID].skills = _skills_with(Ability.PSYCHIC, 3)  # 2 action-cast slots
    state.add_leader(LeaderState(78, 1, "Field Commander", LOCATION))
    state.add_army(ArmyState(1, 1, ArmyType.LEGION, Quality.GREEN, LOCATION, commanded_by=78))
    request = CastRequest(spell=Spell.ORATORY, target=78)
    # third call fails at the slot check, before any roll -- only the
    # first two (successful) calls' own Add_Experience draws need padding.
    rng = ScriptedRandom([0.01, 0.5, 0.5, 0.01, 0.5, 0.5])

    first = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)
    second = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)
    third = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert first.applied is True
    assert second.applied is True
    assert third.applied is False
    assert third.reason == "no action-cast slots remaining this turn for this ability"


def test_execute_cast_a_failed_roll_still_consumes_a_slot():
    # AKGEN's own confirmed failed_attempt_consumes_slot: true.
    state = build_state()
    state.leaders[CASTER_ID].skills = _skills_with(Ability.PSYCHIC, 1)  # 1 action-cast slot
    state.add_leader(LeaderState(78, 1, "Field Commander", LOCATION))
    state.add_army(ArmyState(1, 1, ArmyType.LEGION, Quality.GREEN, LOCATION, commanded_by=78))
    request = CastRequest(spell=Spell.ORATORY, target=78)
    rng = ScriptedRandom([0.99])  # fails the roll (base action-cast chance 30% at level 1)

    first = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)
    second = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert first.applied is False
    assert first.reason == "spell failed"
    assert second.applied is False
    assert second.reason == "no action-cast slots remaining this turn for this ability"


def test_execute_cast_wand_casts_never_consume_action_slots():
    state = build_state()
    state.leaders[CASTER_ID].skills = _skills_with(Ability.PSYCHIC, 1)
    state.add_leader(LeaderState(78, 1, "Field Commander", LOCATION))
    state.add_army(ArmyState(1, 1, ArmyType.LEGION, Quality.GREEN, LOCATION, commanded_by=78))
    request = CastRequest(spell=Spell.ORATORY, target=78)

    for _ in range(5):
        result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, wand_skill_level=2)
        assert result.applied is True
    assert state.action_casts_used == {}


# ---------------------------------------------------------------------------
# Plague (Phase 59) -- Regolamento AK.txt [4.25.3]
# ---------------------------------------------------------------------------


def test_plague_destroys_humanoid_units_that_roll_under_the_chance():
    state = build_state()
    state.add_province(ProvinceState(LOCATION, Terrain.PLAINS, Race.HUMAN))
    state.leaders[CASTER_ID].skills = _skills_with(Ability.NECROMANCY, 1)  # 10% + 10% = 20%
    state.add_army(ArmyState(1, 1, ArmyType.LEGION, Quality.AVERAGE, LOCATION))
    request = CastRequest(spell=Spell.PLAGUE, target=_target(LOCATION))
    rng = ScriptedRandom([0.01, 0.19, 0.5, 0.5])  # [0] cast success, [1] per-unit destroy roll (hits)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is True
    assert 1 not in state.armies


def test_plague_skips_non_humanoid_and_mercenary_armies():
    state = build_state()
    state.add_province(ProvinceState(LOCATION, Terrain.PLAINS, Race.HUMAN))
    state.leaders[CASTER_ID].skills = _skills_with(Ability.NECROMANCY, 9)  # near-certain chance
    state.kingdoms[2] = KingdomState(2, "Rivalia", Race.DRAGONS, Alignment.EVIL, ELSEWHERE)
    state.add_army(ArmyState(1, 2, ArmyType.DRAGON_WING, Quality.AVERAGE, LOCATION))  # non-humanoid race
    state.add_army(ArmyState(2, None, ArmyType.LEGION, Quality.AVERAGE, LOCATION))  # mercenary, race unknown
    request = CastRequest(spell=Spell.PLAGUE, target=_target(LOCATION))
    rng = ScriptedRandom([0.01, 0.5, 0.5])  # [0] cast success, [1:] Add_Experience gain draws

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is True
    assert 1 in state.armies
    assert 2 in state.armies


def test_plague_marks_the_province_as_plague_active():
    state = build_state()
    state.add_province(ProvinceState(LOCATION, Terrain.PLAINS, Race.HUMAN))
    request = CastRequest(spell=Spell.PLAGUE, target=_target(LOCATION))
    rng = ScriptedRandom([0.01])  # cast success; no armies present, no exposure roll

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is True
    assert state.provinces[LOCATION].plague_active is True


def test_plague_recast_on_an_already_active_province_is_a_no_op():
    state = build_state()
    province = ProvinceState(LOCATION, Terrain.PLAINS, Race.HUMAN, plague_active=True)
    state.add_province(province)
    state.add_army(ArmyState(1, 1, ArmyType.LEGION, Quality.AVERAGE, LOCATION))
    request = CastRequest(spell=Spell.PLAGUE, target=_target(LOCATION))
    rng = ScriptedRandom([0.01])  # only the cast-success roll -- a 2nd (exposure) roll would raise

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is True
    assert 1 in state.armies  # untouched -- no cumulative effect


def test_apply_plague_exposure_immunizes_a_survivor():
    state = build_state()
    state.add_army(ArmyState(1, 1, ArmyType.LEGION, Quality.AVERAGE, LOCATION))
    rng = ScriptedRandom([0.5])  # misses a 0.2 destroy chance -- survives

    apply_plague_exposure(state, LOCATION, 0.2, rng)

    assert 1 in state.armies
    assert state.armies[1].plague_immune is True


def test_apply_plague_exposure_destroys_a_non_immune_army_on_a_hit():
    state = build_state()
    state.add_army(ArmyState(1, 1, ArmyType.LEGION, Quality.AVERAGE, LOCATION))
    rng = ScriptedRandom([0.01])  # hits a 0.2 destroy chance

    apply_plague_exposure(state, LOCATION, 0.2, rng)

    assert 1 not in state.armies


def test_apply_plague_exposure_penicillin_never_destroys_only_downgrades():
    # Phase 270: Penicillin (Discovery.txt) -- a flat 50% chance of
    # losing one quality level, never the destroy roll, regardless of
    # `chance` or prior plague_immune status.
    state = build_state()
    state.kingdoms[1].discoveries.add(Discovery.PENICILLIN)
    state.add_army(ArmyState(1, 1, ArmyType.LEGION, Quality.AVERAGE, LOCATION))
    rng = ScriptedRandom([0.49])  # hits the flat 50% downgrade chance

    apply_plague_exposure(state, LOCATION, 1.0, rng)  # chance=100% would otherwise always destroy

    assert 1 in state.armies  # never destroyed
    assert state.armies[1].quality == Quality.GREEN
    assert state.armies[1].plague_immune is False  # Penicillin's own branch, not the immunity path


def test_apply_plague_exposure_penicillin_protects_an_ally_in_the_owners_own_province():
    # Phase 300 fix: Discovery.txt's own second clause -- "all armies
    # (yours and your ally's) are protected in your provinces" -- an
    # allied army with no Penicillin of its own, standing in a
    # Penicillin-owning kingdom's own territory, gets the same flat
    # downgrade-only protection instead of risking outright destruction.
    state = build_state()
    state.add_kingdom(KingdomState(3, "Allia", Race.HUMAN, Alignment.GOOD, ELSEWHERE))
    state.allied_kingdoms.add(frozenset({1, 3}))
    state.kingdoms[1].discoveries.add(Discovery.PENICILLIN)
    state.add_province(ProvinceState(LOCATION, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_army(ArmyState(1, 3, ArmyType.LEGION, Quality.AVERAGE, LOCATION))  # kingdom 3's own army, no Penicillin
    rng = ScriptedRandom([0.49])  # hits the flat 50% downgrade chance

    apply_plague_exposure(state, LOCATION, 1.0, rng)  # chance=100% would otherwise always destroy

    assert 1 in state.armies  # never destroyed
    assert state.armies[1].quality == Quality.GREEN
    assert state.armies[1].plague_immune is False


def test_apply_plague_exposure_penicillin_does_not_protect_a_non_ally_in_the_owners_own_province():
    state = build_state()
    state.add_kingdom(KingdomState(3, "Foelandia", Race.HUMAN, Alignment.EVIL, ELSEWHERE))  # not allied
    state.kingdoms[1].discoveries.add(Discovery.PENICILLIN)
    state.add_province(ProvinceState(LOCATION, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_army(ArmyState(1, 3, ArmyType.LEGION, Quality.AVERAGE, LOCATION))
    rng = ScriptedRandom([0.01])  # hits the ordinary 100% destroy chance -- no protection applies

    apply_plague_exposure(state, LOCATION, 1.0, rng)

    assert 1 not in state.armies  # destroyed -- an unallied trespasser gets no Penicillin protection


def test_apply_plague_exposure_drops_an_immune_armys_quality_instead_of_killing_it():
    state = build_state()
    army = ArmyState(1, 1, ArmyType.LEGION, Quality.VETERAN, LOCATION, plague_immune=True)
    state.add_army(army)
    rng = ScriptedRandom([0.01])  # hits the 0.2 chance -- but immune, so quality drops instead

    apply_plague_exposure(state, LOCATION, 0.2, rng)

    assert 1 in state.armies
    assert state.armies[1].quality is Quality.AVERAGE  # one level below Veteran
    assert state.armies[1].plague_immune is True


def test_apply_plague_exposure_immune_army_at_depleted_stays_depleted():
    state = build_state()
    army = ArmyState(1, 1, ArmyType.LEGION, Quality.DEPLETED, LOCATION, plague_immune=True)
    state.add_army(army)
    rng = ScriptedRandom([0.01])  # hits the chance -- already at the floor

    apply_plague_exposure(state, LOCATION, 0.2, rng)

    assert state.armies[1].quality is Quality.DEPLETED


def test_apply_plague_exposure_skips_mercenaries_and_non_humanoid_races():
    state = build_state()
    state.kingdoms[2] = KingdomState(2, "Rivalia2", Race.DRAGONS, Alignment.EVIL, ELSEWHERE)
    state.add_army(ArmyState(1, 2, ArmyType.DRAGON_WING, Quality.AVERAGE, LOCATION))  # non-humanoid
    state.add_army(ArmyState(2, None, ArmyType.LEGION, Quality.AVERAGE, LOCATION))  # mercenary
    rng = ScriptedRandom([])  # no army is ever eligible for a roll

    apply_plague_exposure(state, LOCATION, 1.0, rng)

    assert 1 in state.armies
    assert 2 in state.armies


# -- Phase 664: Office.GOOD_KING's own "-15% Plague chance" perk --


def _grant_good_king_title(state: GameState) -> None:
    # OFFICE_MIN_POINTS[Office.GOOD_KING] == 25; kingdom 1 is Alignment.GOOD
    # by build_state()'s own default. Tax base supplied by a separate
    # province (ELSEWHERE) so it doesn't interfere with whichever
    # province the test's own Plague roll targets.
    state.leaders[CASTER_ID].is_king = True
    state.add_province(ProvinceState(ELSEWHERE, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, tax=30))


def test_apply_plague_exposure_protects_an_army_owned_by_the_good_kings_own_kingdom():
    state = build_state()
    _grant_good_king_title(state)
    state.add_province(ProvinceState(LOCATION, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2))
    state.add_army(ArmyState(1, 1, ArmyType.LEGION, Quality.AVERAGE, LOCATION))  # kingdom 1's own army, foreign soil
    rng = ScriptedRandom([0.10])  # over the reduced 0.05 chance, under the ordinary 0.20 one

    apply_plague_exposure(state, LOCATION, 0.20, rng)

    assert 1 in state.armies  # protected -- survives instead of being destroyed
    assert state.armies[1].plague_immune is True


def test_apply_plague_exposure_protects_a_foreign_army_standing_in_the_good_kings_own_territory():
    state = build_state()
    _grant_good_king_title(state)
    state.add_province(ProvinceState(LOCATION, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))  # Good King's own territory
    state.add_army(ArmyState(1, 2, ArmyType.LEGION, Quality.AVERAGE, LOCATION))  # a foreign, unallied army
    rng = ScriptedRandom([0.10])  # over the reduced 0.05 chance, under the ordinary 0.20 one

    apply_plague_exposure(state, LOCATION, 0.20, rng)

    assert 1 in state.armies  # protected by territory, regardless of the army's own owner
    assert state.armies[1].plague_immune is True


def test_apply_plague_exposure_no_good_king_title_gets_no_protection_at_the_same_roll():
    state = build_state()
    state.add_province(ProvinceState(LOCATION, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2))
    state.add_army(ArmyState(1, 1, ArmyType.LEGION, Quality.AVERAGE, LOCATION))
    rng = ScriptedRandom([0.10])  # under the ordinary 0.20 chance -- no title held, no reduction

    apply_plague_exposure(state, LOCATION, 0.20, rng)

    assert 1 not in state.armies  # destroyed -- proves the reduction above is real, not a no-op


# ---------------------------------------------------------------------------
# Bless's corpse-cleanup addendum (Phase 60) -- "NUOVE REGOLE E MODIFICHE"
# ---------------------------------------------------------------------------


def test_bless_clears_the_graveyard_on_a_successful_cleanup_roll():
    state = build_state()
    state.add_province(ProvinceState(LOCATION, Terrain.PLAINS, Race.HUMAN))
    state.battle_graveyard[LOCATION] = [GraveyardEntry(ArmyType.LEGION, Quality.AVERAGE, kingdom_id=2)]
    request = CastRequest(spell=Spell.BLESS, target=_target(LOCATION))
    rng = ScriptedRandom([0.05])  # no skills recorded -> cast succeeds free; cleanup chance 10% -> hits

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is True
    assert state.provinces[LOCATION].tax_modifier_percent == 60
    assert LOCATION not in state.battle_graveyard


def test_bless_does_not_clear_the_graveyard_on_a_failed_cleanup_roll():
    state = build_state()
    state.add_province(ProvinceState(LOCATION, Terrain.PLAINS, Race.HUMAN))
    state.battle_graveyard[LOCATION] = [GraveyardEntry(ArmyType.LEGION, Quality.AVERAGE, kingdom_id=2)]
    request = CastRequest(spell=Spell.BLESS, target=_target(LOCATION))
    rng = ScriptedRandom([0.99])  # cleanup chance 10% -> misses

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is True
    assert state.provinces[LOCATION].tax_modifier_percent == 60  # tax bonus still applies
    assert len(state.battle_graveyard[LOCATION]) == 1  # graveyard untouched


def test_bless_cleanup_chance_scales_with_white_magic_level():
    state = build_state()
    state.add_province(ProvinceState(LOCATION, Terrain.PLAINS, Race.HUMAN))
    state.leaders[CASTER_ID].skills = _skills_with(Ability.WHITE, 2)  # cast 45%, cleanup 30%
    state.battle_graveyard[LOCATION] = [GraveyardEntry(ArmyType.LEGION, Quality.AVERAGE, kingdom_id=2)]
    request = CastRequest(spell=Spell.BLESS, target=_target(LOCATION))
    rng = ScriptedRandom([0.01, 0.25, 0.5, 0.5])  # [0] cast success, [1] cleanup roll (0.25 < 30%)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is True
    assert LOCATION not in state.battle_graveyard


# ---------------------------------------------------------------------------
# Skeletal Army (Phase 60) -- Regolamento AK.txt [4.25.1]
# ---------------------------------------------------------------------------


def test_skeletal_army_raises_a_unit_from_the_casters_own_province_graveyard():
    state = build_state()
    state.battle_graveyard[LOCATION] = [GraveyardEntry(ArmyType.LEGION, Quality.VETERAN, kingdom_id=2)]
    state.leaders[CASTER_ID].skills = _skills_with(Ability.NECROMANCY, 1)  # level 1 -> raise up to 1
    request = CastRequest(spell=Spell.SKELETAL_ARMY, target=0)
    rng = ScriptedRandom([0.01, 0.5, 0.5])  # [0] cast success -- raising itself is deterministic, [1:] Add_Experience gain draws

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is True
    assert LOCATION not in state.battle_graveyard  # the one entry was consumed
    raised = [a for a in state.armies.values() if a.army_type is ArmyType.LEGION]
    assert len(raised) == 1
    assert raised[0].quality is Quality.VETERAN
    assert raised[0].kingdom_id == 1  # joins the caster's kingdom
    assert raised[0].commanded_by == CASTER_ID
    assert raised[0].location == LOCATION
    assert raised[0].is_skeletal is True


def test_skeletal_army_fails_when_the_provinces_graveyard_is_empty():
    state = build_state()
    request = CastRequest(spell=Spell.SKELETAL_ARMY, target=0)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is False
    assert result.reason == "no dead units in this province to raise"


def test_skeletal_army_caps_the_raised_count_at_the_casters_necromancy_level():
    state = build_state()
    state.battle_graveyard[LOCATION] = [
        GraveyardEntry(ArmyType.LEGION, Quality.AVERAGE, kingdom_id=2),
        GraveyardEntry(ArmyType.BOWMEN, Quality.VETERAN, kingdom_id=2),
        GraveyardEntry(ArmyType.AXEMEN, Quality.GREEN, kingdom_id=2),
    ]
    state.leaders[CASTER_ID].skills = _skills_with(Ability.NECROMANCY, 2)  # level 2 -> raise at most 2 of the 3
    request = CastRequest(spell=Spell.SKELETAL_ARMY, target=0)
    rng = ScriptedRandom([0.01, 0.5, 0.5])  # [0] cast success, [1:] Add_Experience gain draws

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is True
    assert len(state.battle_graveyard[LOCATION]) == 1  # one entry left unraised
    assert len([a for a in state.armies.values()]) == 2


def test_skeletal_army_raises_nothing_when_caster_has_no_recorded_level():
    state = build_state()
    state.battle_graveyard[LOCATION] = [GraveyardEntry(ArmyType.LEGION, Quality.AVERAGE, kingdom_id=2)]
    request = CastRequest(spell=Spell.SKELETAL_ARMY, target=0)
    rng = ScriptedRandom([])  # no skills recorded -> cast succeeds free, no roll consumed

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is True  # the cast itself still "succeeds"...
    assert len(state.armies) == 0  # ...but unknown level -> 0 raised, see module docstring
    assert len(state.battle_graveyard[LOCATION]) == 1  # graveyard untouched


# -- Phase 664: Office.UNDEAD_KING's own "+1 max raised" perk --


def _grant_undead_king_title(state: GameState) -> None:
    # OFFICE_MIN_POINTS[Office.UNDEAD_KING] == 25: Undead-alignment King
    # plus a real Tax_Base of at least that much (Alignment alone isn't
    # enough -- same "known" gate Phase 663 used for Neutral King).
    state.kingdoms[1].alignment = Alignment.UNDEAD
    state.leaders[CASTER_ID].is_king = True
    state.add_province(ProvinceState(LOCATION, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, tax=30))


def test_undead_king_titleholder_raises_one_extra_skeletal_army():
    state = build_state()
    _grant_undead_king_title(state)
    state.battle_graveyard[LOCATION] = [
        GraveyardEntry(ArmyType.LEGION, Quality.AVERAGE, kingdom_id=2),
        GraveyardEntry(ArmyType.BOWMEN, Quality.VETERAN, kingdom_id=2),
        GraveyardEntry(ArmyType.AXEMEN, Quality.GREEN, kingdom_id=2),
    ]
    state.leaders[CASTER_ID].skills = _skills_with(Ability.NECROMANCY, 2)  # unboosted cap 2, titled cap 3
    request = CastRequest(spell=Spell.SKELETAL_ARMY, target=0)
    rng = ScriptedRandom([0.01, 0.5, 0.5])  # [0] cast success, [1:] Add_Experience gain draws

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is True
    assert LOCATION not in state.battle_graveyard  # all 3 entries consumed
    assert len(state.armies) == 3


def test_non_titleholder_stays_at_the_ordinary_skeletal_army_cap():
    state = build_state()
    _grant_undead_king_title(state)
    state.add_leader(LeaderState(501, 1, "Someone Else", LOCATION, is_king=True))  # the real King of kingdom 1
    state.leaders[CASTER_ID].is_king = False  # CASTER_ID is only a Hero here -- doesn't hold the title
    state.battle_graveyard[LOCATION] = [
        GraveyardEntry(ArmyType.LEGION, Quality.AVERAGE, kingdom_id=2),
        GraveyardEntry(ArmyType.BOWMEN, Quality.VETERAN, kingdom_id=2),
        GraveyardEntry(ArmyType.AXEMEN, Quality.GREEN, kingdom_id=2),
    ]
    state.leaders[CASTER_ID].skills = _skills_with(Ability.NECROMANCY, 2)
    request = CastRequest(spell=Spell.SKELETAL_ARMY, target=0)
    rng = ScriptedRandom([0.01, 0.5, 0.5])

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is True
    assert len(state.battle_graveyard[LOCATION]) == 1  # only the ordinary cap of 2 raised
    assert len(state.armies) == 2


# ---------------------------------------------------------------------------
# Clairvoyance (Phase 193) -- Regolamento AK.txt [4.22.3]
# ---------------------------------------------------------------------------


def test_clairvoyance_adds_the_casters_kingdom_to_the_targets_watchers():
    state = build_state()
    state.add_leader(LeaderState(78, 2, "Enemy Hero", ELSEWHERE))  # no co-location requirement
    request = CastRequest(spell=Spell.CLAIRVOYANCE, target=78)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is True
    assert state.leaders[78].clairvoyance_watchers == {1}


def test_clairvoyance_records_the_casters_own_target_leader_id():
    # Phase 637: LeaderState.clairvoyance_cast_target -- the caster's own
    # side of the same successful cast, feeding Was_Clairved.
    state = build_state()
    state.add_leader(LeaderState(78, 2, "Enemy Hero", ELSEWHERE))
    request = CastRequest(spell=Spell.CLAIRVOYANCE, target=78)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is True
    assert state.leaders[CASTER_ID].clairvoyance_cast_target == 78


def test_clairvoyance_a_second_cast_overwrites_the_casters_own_prior_target():
    state = build_state()
    state.add_leader(LeaderState(78, 2, "Enemy Hero", ELSEWHERE))
    state.add_leader(LeaderState(79, 2, "Another Enemy Hero", ELSEWHERE))

    execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=CastRequest(spell=Spell.CLAIRVOYANCE, target=78))
    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=CastRequest(spell=Spell.CLAIRVOYANCE, target=79))

    assert result.applied is True
    assert state.leaders[CASTER_ID].clairvoyance_cast_target == 79


def test_clairvoyance_fails_when_target_does_not_exist():
    state = build_state()
    request = CastRequest(spell=Spell.CLAIRVOYANCE, target=78)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is False
    assert result.reason == "target character not found"


def test_clairvoyance_does_not_touch_watchers_on_a_failed_roll():
    state = build_state()
    state.leaders[CASTER_ID].skills = _skills_with(Ability.PSYCHIC, 1)
    state.add_leader(LeaderState(78, 2, "Enemy Hero", ELSEWHERE))
    request = CastRequest(spell=Spell.CLAIRVOYANCE, target=78)
    rng = ScriptedRandom([0.96])  # over the 15%+15% = 30% Action-Cast chance

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is False
    assert state.leaders[78].clairvoyance_watchers == set()


# -- Phase 492: High Chancellor's own Crystal Ball addendum -------------


def test_clairvoyance_chancellor_bypasses_a_roll_that_would_otherwise_fail():
    # Phase 492: "will automatically be successful even if you have no
    # skill in psychic magic" -- CASTER_ID has no skills recorded here
    # (already an auto-success case per Phase 193's own fallback), so
    # give them a real, insufficient skill and an over-the-cap roll to
    # prove the Chancellor bypass is what's actually firing, not the
    # pre-existing "no skills" shortcut.
    state = build_state()
    state.leaders[CASTER_ID].skills = _skills_with(Ability.PSYCHIC, 1)
    state.leaders[CASTER_ID].merit_tally.discoveries_found_first = 1  # meets OFFICE_MIN_POINTS[Office.CHANCELLOR]
    state.add_leader(LeaderState(78, 2, "Enemy Hero", ELSEWHERE))
    request = CastRequest(spell=Spell.CLAIRVOYANCE, target=78)
    # A real (non-bypassed) roll at skill 1 (30% chance) would almost
    # certainly fail against these two high draws -- only consumed here
    # by _award_cast_experience() (Phase 460's own +10 XP roll), not by
    # any cast-success check, if the Chancellor bypass is working.
    rng = ScriptedRandom([0.9, 0.9])

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is True
    assert state.leaders[78].clairvoyance_watchers == {1}


def test_clairvoyance_chancellor_does_not_consume_an_action_cast_slot():
    state = build_state()
    state.leaders[CASTER_ID].skills = _skills_with(Ability.PSYCHIC, 1)
    state.leaders[CASTER_ID].merit_tally.discoveries_found_first = 1
    state.add_leader(LeaderState(78, 2, "Enemy Hero", ELSEWHERE))
    request = CastRequest(spell=Spell.CLAIRVOYANCE, target=78)

    execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=ScriptedRandom([0.9, 0.9]))

    assert state.action_casts_used == {}


def test_clairvoyance_chancellor_lists_the_spied_kingdoms_offices():
    state = build_state()
    state.leaders[CASTER_ID].merit_tally.discoveries_found_first = 1
    target = LeaderState(78, 2, "Enemy Hero", ELSEWHERE)
    target.merit_tally.land_battles_won_points = 1  # meets OFFICE_MIN_POINTS[Office.MARSHAL]
    state.add_leader(target)
    request = CastRequest(spell=Spell.CLAIRVOYANCE, target=78)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=ScriptedRandom([0.9, 0.9]))

    assert result.applied is True
    assert Office.MARSHAL in result.clairvoyance_target_offices


def test_clairvoyance_non_chancellor_cast_leaves_target_offices_none():
    state = build_state()
    target = LeaderState(78, 2, "Enemy Hero", ELSEWHERE)
    target.merit_tally.land_battles_won_points = 1
    state.add_leader(target)
    request = CastRequest(spell=Spell.CLAIRVOYANCE, target=78)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is True
    assert result.clairvoyance_target_offices is None


# ---------------------------------------------------------------------------
# Hide_Feature (Phase 193) -- Regolamento AK.txt [4.23.3]
# ---------------------------------------------------------------------------


def test_hide_feature_hides_every_feature_in_the_target_province():
    state = build_state()
    state.add_province(ProvinceState(LOCATION, Terrain.PLAINS, Race.HUMAN))
    state.add_feature(Feature(1, LOCATION, FeatureType.SACRED_ROCK))
    state.add_feature(Feature(2, LOCATION, FeatureType.ALTAR))
    request = CastRequest(spell=Spell.HIDE_FEATURE, target=_target(LOCATION))

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is True
    assert state.features[1].magically_hidden is True
    assert state.features[2].magically_hidden is True


def test_hide_feature_fails_when_the_province_has_no_feature():
    state = build_state()
    state.add_province(ProvinceState(LOCATION, Terrain.PLAINS, Race.HUMAN))
    request = CastRequest(spell=Spell.HIDE_FEATURE, target=_target(LOCATION))

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is False
    assert result.reason == "no feature to hide"


def test_hide_feature_fails_when_the_province_is_unknown():
    state = build_state()
    request = CastRequest(spell=Spell.HIDE_FEATURE, target=_target(LOCATION))

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is False
    assert result.reason == "province not found or not in range"


# ---------------------------------------------------------------------------
# Gate Angel / VALHALLA (Phase 194, corrected Phase 195) -- user-supplied
# rule text, one of the 10 secret spells. GATE_ANGEL_ELIGIBLE_ALIGNMENTS is
# (GOOD, DRUID, NEUTRAL, PAGAN, EVIL) in that order, so choice_indices=[0]
# picks GOOD, [1] picks DRUID, [4] picks EVIL, for the due-alignment draw.
# ---------------------------------------------------------------------------


def test_gate_angel_matching_alignment_succeeds_and_records_the_winner():
    state = build_state()
    assert state.kingdoms[1].alignment is Alignment.GOOD
    request = CastRequest(spell=Spell.GATE_ANGEL, target=0)
    rng = ScriptedRandom([], choice_indices=[0])  # GOOD due -- matches kingdom 1

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is True
    assert state.gate_angel_due_alignment is Alignment.GOOD
    assert state.last_gate_angel_kingdom == 1
    assert state.last_gate_angel_turn == state.turn_number


def test_gate_angel_non_matching_alignment_fails_without_rolling():
    state = build_state()
    assert state.kingdoms[1].alignment is Alignment.GOOD
    request = CastRequest(spell=Spell.GATE_ANGEL, target=0)
    rng = ScriptedRandom([], choice_indices=[1])  # DRUID due -- not kingdom 1's GOOD

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is False
    assert result.reason == "not this alignment's turn for a Valhalla visit"
    assert state.last_gate_angel_kingdom is None


def test_gate_angel_due_alignment_is_cached_for_the_rest_of_the_turn():
    state = build_state()
    state.kingdoms[2].alignment = Alignment.DRUID
    state.add_leader(LeaderState(78, 2, "Druid Caster", ELSEWHERE))
    request = CastRequest(spell=Spell.GATE_ANGEL, target=0)
    # Only one choice_indices entry: the due-alignment draw. If the second
    # cast this turn re-rolled it, ScriptedRandom would raise IndexError.
    rng = ScriptedRandom([], choice_indices=[1])  # DRUID due

    first = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)
    second = execute_cast(state, kingdom_id=2, leader_id=78, request=request, rng=rng)

    assert first.applied is False  # kingdom 1 is GOOD, not this turn's DRUID
    assert second.applied is True  # kingdom 2 is DRUID, matches the cached due alignment


def test_gate_angel_divine_kingdom_receives_a_visit_when_good_is_due():
    # Phase 386 correction: AKGEN's own confirmed validation_alignment_
    # mapping clamps Divine to Good rather than excluding it outright.
    state = build_state()
    state.kingdoms[1].alignment = Alignment.DIVINE
    request = CastRequest(spell=Spell.GATE_ANGEL, target=0)
    rng = ScriptedRandom([], choice_indices=[0])  # GOOD due -- Divine clamps to Good

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is True
    assert state.last_gate_angel_kingdom == 1


def test_gate_angel_undead_kingdom_receives_a_visit_when_evil_is_due():
    # Phase 386 correction: Undead clamps to Evil rather than being excluded.
    state = build_state()
    state.kingdoms[1].alignment = Alignment.UNDEAD
    request = CastRequest(spell=Spell.GATE_ANGEL, target=0)
    rng = ScriptedRandom([], choice_indices=[4])  # EVIL due -- Undead clamps to Evil

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is True
    assert state.last_gate_angel_kingdom == 1


def test_gate_angel_contention_second_candidate_can_win():
    # Phase 386 correction: the real rule is "later cast has 50% to
    # replace the current incumbent" (rng.random() < 0.5), not reservoir
    # sampling's rng.choice(range(n)).
    state = build_state()
    state.kingdoms[2].alignment = Alignment.GOOD
    state.add_leader(LeaderState(78, 2, "Second Good King", ELSEWHERE))
    request = CastRequest(spell=Spell.GATE_ANGEL, target=0)
    rng = ScriptedRandom([0.3], choice_indices=[0])  # GOOD due; 2nd candidate's roll < 0.5 -> replaces

    execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)
    assert state.last_gate_angel_kingdom == 1  # first candidate wins outright, no roll needed

    execute_cast(state, kingdom_id=2, leader_id=78, request=request, rng=rng)
    assert state.last_gate_angel_kingdom == 2  # the 50% replace roll hands the visit to the 2nd candidate


def test_gate_angel_contention_second_candidate_can_lose():
    state = build_state()
    state.kingdoms[2].alignment = Alignment.GOOD
    state.add_leader(LeaderState(78, 2, "Second Good King", ELSEWHERE))
    request = CastRequest(spell=Spell.GATE_ANGEL, target=0)
    rng = ScriptedRandom([0.7], choice_indices=[0])  # GOOD due; 2nd candidate's roll >= 0.5 -> nullified

    execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)
    execute_cast(state, kingdom_id=2, leader_id=78, request=request, rng=rng)

    assert state.last_gate_angel_kingdom == 1  # first candidate keeps the win


def test_gate_angel_cycle_resets_once_all_5_alignments_are_visited():
    state = build_state()
    state.gate_angel_cycle_visited = {
        Alignment.GOOD,
        Alignment.DRUID,
        Alignment.NEUTRAL,
        Alignment.PAGAN,
        Alignment.EVIL,
    }
    request = CastRequest(spell=Spell.GATE_ANGEL, target=0)
    rng = ScriptedRandom([], choice_indices=[0])  # the sole survivor after the reset

    execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    # cleared (all 5 were already visited), then exactly one freshly consumed
    assert len(state.gate_angel_cycle_visited) == 1


def test_gate_angel_due_alignment_also_resets_on_the_turn_mod_5_equals_4_boundary():
    # Phase 386: a second, independent reset condition -- the cycle now
    # force-clears on this turn-count boundary even when fewer than 5
    # alignments have actually been visited (e.g. no Gate Angel cast at
    # all on some intervening turn).
    state = build_state()
    state.turn_number = 4  # 4 % 5 == 4
    state.gate_angel_cycle_visited = {Alignment.GOOD, Alignment.DRUID}  # only 2 of 5, not a full cycle
    request = CastRequest(spell=Spell.GATE_ANGEL, target=0)
    rng = ScriptedRandom([], choice_indices=[0])  # GOOD is remaining[0] after the forced reset

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is True
    assert state.gate_angel_due_alignment is Alignment.GOOD


def test_gate_angel_failed_roll_does_not_touch_any_state():
    state = build_state()
    state.leaders[CASTER_ID].skills = _skills_with(Ability.WHITE, 1)  # 30% chance
    request = CastRequest(spell=Spell.GATE_ANGEL, target=0)
    rng = ScriptedRandom([0.96], choice_indices=[0])  # GOOD due (matches), roll fails

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is False
    assert state.last_gate_angel_turn is None
    assert state.last_gate_angel_kingdom is None
    assert state.gate_angel_candidates_this_turn == 0


# ---------------------------------------------------------------------------
# Phase 192: spell-cast success formula corrections (a direct re-quote of
# Regolamento AK.txt [3.10] confirmed the 95% cap is real and Pagan
# Kingdoms get a +10% bonus to every spell except White Magic)
# ---------------------------------------------------------------------------


def test_action_spell_chance_caps_at_95_percent_even_at_high_skill_level():
    # Level 10: 15% + 15%*10 = 165% uncapped -- now clamped to 95%.
    state = build_state()
    state.leaders[CASTER_ID].skills = _skills_with(Ability.NECROMANCY, 10)
    state.add_leader(LeaderState(78, 2, "Enemy Hero", LOCATION))
    request = CastRequest(spell=Spell.KILL_ENEMY, target=78)
    rng = ScriptedRandom([0.94, 0.5, 0.5])  # [0] under the 95% cap, [1:] Add_Experience gain draws

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is True


def test_action_spell_can_fail_above_the_95_percent_cap_at_high_skill_level():
    # Before Phase 192 this roll would have always succeeded (uncapped
    # chance was 165%, and rng.random() never reaches 1.0).
    # Charm, not Kill_Enemy, so a failed roll here stays a plain failure
    # -- Kill_Enemy's own Phase 310 Berserk-counterattack-on-failure
    # would consume extra RNG this test isn't scripting.
    state = build_state()
    state.leaders[CASTER_ID].skills = _skills_with(Ability.PSYCHIC, 10)
    state.add_leader(LeaderState(78, 2, "Enemy Hero", LOCATION))
    request = CastRequest(spell=Spell.CHARM, target=78)
    rng = ScriptedRandom([0.96])  # over the 95% cap

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is False
    assert result.reason == "spell failed"
    assert state.leaders[78].kingdom_id == 2  # untouched


def test_pagan_kingdom_caster_gets_a_10_percent_spell_cast_bonus():
    # Level 1 Necromancy: 30% base, +10% Pagan = 40%.
    state = build_state()
    state.kingdoms[1].alignment = Alignment.PAGAN
    state.leaders[CASTER_ID].skills = _skills_with(Ability.NECROMANCY, 1)
    state.add_leader(LeaderState(78, 2, "Enemy Hero", LOCATION))
    request = CastRequest(spell=Spell.KILL_ENEMY, target=78)
    rng = ScriptedRandom([0.35, 0.5, 0.5])  # [0] over the un-bonused 30%, under the bonused 40%, [1:] Add_Experience gain draws

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is True


def test_non_pagan_kingdom_caster_gets_no_bonus_at_the_same_roll():
    # Charm, not Kill_Enemy -- see the 95%-cap test above's own note on
    # why a spell whose failure has no side effect is used here.
    state = build_state()
    assert state.kingdoms[1].alignment is Alignment.GOOD
    state.leaders[CASTER_ID].skills = _skills_with(Ability.PSYCHIC, 1)
    state.add_leader(LeaderState(78, 2, "Enemy Hero", LOCATION))
    request = CastRequest(spell=Spell.CHARM, target=78)
    rng = ScriptedRandom([0.35])  # over the un-bonused 30% base chance

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is False
    assert result.reason == "spell failed"


def test_pagan_kingdom_bonus_does_not_apply_to_white_magic_spells():
    # "un modificatore +10%... fuorche' quelli di Magia Bianca."
    state = build_state()
    state.kingdoms[1].alignment = Alignment.PAGAN
    state.leaders[CASTER_ID].skills = _skills_with(Ability.WHITE, 1)
    state.add_province(ProvinceState(LOCATION, Terrain.PLAINS, Race.HUMAN))
    request = CastRequest(spell=Spell.BLESS, target=_target(LOCATION))
    rng = ScriptedRandom([0.35])  # over the un-bonused 30% White Magic chance

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is False
    assert result.reason == "spell failed"


# -- Phase 664: Office.PAGAN_KING's own "+10% White Magic" perk --


def _grant_pagan_king_title(state: GameState) -> None:
    # OFFICE_MIN_POINTS[Office.PAGAN_KING] == 25. The titleholder is a
    # separate King (leader 501), not CASTER_ID -- "all your Pagan
    # characters" get the bonus, not just the titleholder himself,
    # the opposite scoping from Undead King's Skeletal Army perk above.
    state.kingdoms[1].alignment = Alignment.PAGAN
    state.add_leader(LeaderState(501, 1, "Pagan King", LOCATION, is_king=True))
    state.add_province(ProvinceState(ELSEWHERE, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, tax=30))


def test_pagan_king_title_grants_a_10_percent_white_magic_bonus_to_any_kingdom_character():
    # Level 1 White Magic: 30% base, +10% Pagan King title = 40%. Uses the
    # same roll (0.35) the "no bonus" test above fails at, proving this
    # title-gated bonus reaches a leader (CASTER_ID) who isn't himself
    # the King/titleholder.
    state = build_state()
    _grant_pagan_king_title(state)
    state.leaders[CASTER_ID].skills = _skills_with(Ability.WHITE, 1)
    state.add_province(ProvinceState(LOCATION, Terrain.PLAINS, Race.HUMAN))
    request = CastRequest(spell=Spell.BLESS, target=_target(LOCATION))
    rng = ScriptedRandom([0.35, 0.99, 0.5, 0.5])  # [0] over the un-bonused 30%, under the titled 40%; [1] graveyard-cleanup roll (misses); [2:] Add_Experience gain draws

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is True


def test_pagan_king_title_bonus_does_not_reach_a_different_kingdoms_caster():
    state = build_state()
    _grant_pagan_king_title(state)
    state.kingdoms[2].alignment = Alignment.PAGAN  # also Pagan-aligned, but not the titleholder's own Kingdom
    state.add_leader(LeaderState(78, 2, "Foreign Pagan Hero", LOCATION))
    state.leaders[78].skills = _skills_with(Ability.WHITE, 1)
    state.add_province(ProvinceState(LOCATION, Terrain.PLAINS, Race.HUMAN))
    request = CastRequest(spell=Spell.BLESS, target=_target(LOCATION))
    rng = ScriptedRandom([0.35])  # over the un-bonused 30% -- no reachable bonus for kingdom 2

    result = execute_cast(state, kingdom_id=2, leader_id=78, request=request, rng=rng)

    assert result.applied is False
    assert result.reason == "spell failed"


# ---------------------------------------------------------------------------
# Scar Terrain (Phase 201) -- secret spell, user-supplied
# ---------------------------------------------------------------------------


def test_scar_terrain_reduces_the_provinces_tax_base_by_2():
    state = build_state()
    state.add_province(ProvinceState(LOCATION, Terrain.PLAINS, Race.HUMAN))
    request = CastRequest(spell=Spell.SCAR_TERRAIN, target=_target(LOCATION))

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is True
    assert state.provinces[LOCATION].scar_terrain_gold_reduction == SCAR_TERRAIN_TAX_REDUCTION == 2


def test_scar_terrain_reduction_is_cumulative_across_casts():
    state = build_state()
    state.add_province(ProvinceState(LOCATION, Terrain.PLAINS, Race.HUMAN))
    request = CastRequest(spell=Spell.SCAR_TERRAIN, target=_target(LOCATION))

    execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)
    execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert state.provinces[LOCATION].scar_terrain_gold_reduction == 4


def test_scar_terrain_works_on_a_sea_province_too():
    # No terrain restriction: "Sea provinces will just lose whatever
    # provincial racial and army type they may have" confirms Sea is a
    # valid target, unlike Earthquake's own land-only restriction.
    state = build_state()
    state.add_province(ProvinceState(LOCATION, Terrain.SEA, Race.NO_RACE))
    request = CastRequest(spell=Spell.SCAR_TERRAIN, target=_target(LOCATION))

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is True
    assert state.provinces[LOCATION].scar_terrain_gold_reduction == 2


def test_scar_terrain_fails_when_the_province_is_out_of_range():
    state = build_state()
    request = CastRequest(spell=Spell.SCAR_TERRAIN, target=_target(LOCATION))

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is False
    assert result.reason == "province not found or not in range"


def test_scar_terrain_is_exhausted_at_or_below_zero():
    assert scar_terrain_is_exhausted(0) is True
    assert scar_terrain_is_exhausted(-5) is True
    assert scar_terrain_is_exhausted(1) is False


def test_scar_terrain_collapse_sea_province_becomes_no_race():
    province = ProvinceState(LOCATION, Terrain.SEA, Race.MERMISH)

    scar_terrain_collapse(province)

    assert province.race is Race.NO_RACE


def test_scar_terrain_collapse_land_province_uses_the_callers_chosen_race():
    province = ProvinceState(LOCATION, Terrain.PLAINS, Race.HUMAN)

    scar_terrain_collapse(province, new_land_race=Race.TROLLISH)

    assert province.race is Race.TROLLISH
    assert Race.TROLLISH in SCAR_TERRAIN_LAND_COLLAPSE_RACES


def test_scar_terrain_collapse_land_province_requires_a_valid_race():
    province = ProvinceState(LOCATION, Terrain.PLAINS, Race.HUMAN)

    with pytest.raises(ValueError):
        scar_terrain_collapse(province)

    with pytest.raises(ValueError):
        scar_terrain_collapse(province, new_land_race=Race.HUMAN)


# ---------------------------------------------------------------------------
# Mystic Winds (Phase 204) -- user-supplied, one of the secret spells 25-34
# ---------------------------------------------------------------------------


def test_mystic_winds_constants():
    assert MYSTIC_WINDS_MOVEMENT_POINTS == 5
    assert MYSTIC_WINDS_MOVES_AS_AIR_UNIT is True
    assert MYSTIC_WINDS_USES_MOVEMENT_POINTS_NORMALLY is True
    assert MYSTIC_WINDS_ENDS_BEFORE_ARMY_BATTLE is True


def test_mystic_winds_sets_movement_to_5_for_every_army_the_target_commands():
    state = build_state()
    state.add_leader(LeaderState(78, 1, "Field Commander", LOCATION))
    state.add_army(ArmyState(1, 1, ArmyType.LEGION, Quality.AVERAGE, LOCATION, movement_points=2, commanded_by=78))
    state.add_army(ArmyState(2, 1, ArmyType.BOWMEN, Quality.AVERAGE, LOCATION, movement_points=1, commanded_by=78))
    request = CastRequest(spell=Spell.MYSTIC_WINDS, target=78)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is True
    assert state.leaders[78].mystic_winds_active is True
    assert state.armies[1].movement_points == MYSTIC_WINDS_MOVEMENT_POINTS
    assert state.armies[2].movement_points == MYSTIC_WINDS_MOVEMENT_POINTS


def test_mystic_winds_can_target_the_caster_himself():
    state = build_state()
    state.add_army(ArmyState(1, 1, ArmyType.LEGION, Quality.AVERAGE, LOCATION, movement_points=0, commanded_by=CASTER_ID))
    request = CastRequest(spell=Spell.MYSTIC_WINDS, target=CASTER_ID)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is True
    assert state.leaders[CASTER_ID].mystic_winds_active is True
    assert state.armies[1].movement_points == MYSTIC_WINDS_MOVEMENT_POINTS


def test_mystic_winds_fails_when_target_is_not_colocated():
    state = build_state()
    state.add_leader(LeaderState(78, 1, "Field Commander", ELSEWHERE))
    request = CastRequest(spell=Spell.MYSTIC_WINDS, target=78)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is False
    assert result.reason == "not co-located"


def test_mystic_winds_fails_when_target_character_not_found():
    state = build_state()
    request = CastRequest(spell=Spell.MYSTIC_WINDS, target=999)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is False
    assert result.reason == "target character not found"


def test_mystic_winds_repeated_cast_stays_a_hard_set_not_cumulative():
    state = build_state()
    state.add_army(ArmyState(1, 1, ArmyType.LEGION, Quality.AVERAGE, LOCATION, movement_points=5, commanded_by=CASTER_ID))
    request = CastRequest(spell=Spell.MYSTIC_WINDS, target=CASTER_ID)

    first = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)
    second = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert first.applied is True
    assert second.applied is True
    assert state.armies[1].movement_points == MYSTIC_WINDS_MOVEMENT_POINTS


# ---------------------------------------------------------------------------
# Locate Object (Phase 206) -- user-supplied, one of the secret spells 25-34
# ---------------------------------------------------------------------------


def test_locate_object_cast_succeeds_and_mutates_nothing():
    state = build_state()
    request = CastRequest(spell=Spell.LOCATE_OBJECT, target=1)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is True


def test_locate_object_finds_a_leader_held_item():
    state = build_state()
    state.add_leader(LeaderState(78, 1, "Field Commander", ELSEWHERE))
    item = state.add_item(Treasure.WAND_FIREBALL, owner_leader_id=78)

    found = locate_object(state, item.item_id)

    assert found == LocateObjectResult(location=ELSEWHERE, holder_leader_id=78)


def test_locate_object_returns_none_for_an_unknown_item_id():
    state = build_state()

    assert locate_object(state, 999) is None


def test_locate_object_returns_none_for_a_feature_or_monster_guarded_item():
    # owner_leader_id=None models an item this project has no data for --
    # feature/monster-guarded treasure is a confirmed, sourced gap (see
    # models/item.py's own docstring), not distinguishable from "unknown".
    state = build_state()
    item = state.add_item(Treasure.WAND_FIREBALL, owner_leader_id=None)

    assert locate_object(state, item.item_id) is None


# ---------------------------------------------------------------------------
# Illusory Fog (Phase 207) -- user-supplied, one of the secret spells 25-34
# ---------------------------------------------------------------------------


def test_illusory_fog_constants():
    assert ILLUSORY_FOG_STRENGTH_MULTIPLIER == 0.5
    assert ILLUSORY_FOG_EXTRA_MOVEMENT_COST == 1
    assert ILLUSORY_FOG_DISSIPATES_AT_END_OF_GAMETURN is True


def test_illusory_fog_cast_sets_the_province_flag():
    state = build_state()
    state.add_province(ProvinceState(LOCATION, Terrain.PLAINS, Race.HUMAN))
    request = CastRequest(spell=Spell.ILLUS_FOG, target=_target(LOCATION))

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is True
    assert state.provinces[LOCATION].illusory_fog_active is True


def test_illusory_fog_fails_when_the_province_is_out_of_range():
    state = build_state()
    request = CastRequest(spell=Spell.ILLUS_FOG, target=_target(LOCATION))

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is False
    assert result.reason == "province not found or not in range"


def test_is_illusory_fog_affected_air_unit_true_for_overflight_air_types():
    assert is_illusory_fog_affected_air_unit(ArmyType.DRAGON_WING, mystic_winds_active=False) is True
    assert is_illusory_fog_affected_air_unit(ArmyType.EAGLE_WING, mystic_winds_active=False) is True


def test_is_illusory_fog_affected_air_unit_true_when_mystic_winds_active():
    assert is_illusory_fog_affected_air_unit(ArmyType.LEGION, mystic_winds_active=True) is True


def test_is_illusory_fog_affected_air_unit_false_for_ordinary_ground_units():
    assert is_illusory_fog_affected_air_unit(ArmyType.LEGION, mystic_winds_active=False) is False


def test_illusory_fog_strength_halves_when_affected():
    assert illusory_fog_strength(20.0, affected=True) == 10.0


def test_illusory_fog_strength_unchanged_when_not_affected():
    assert illusory_fog_strength(20.0, affected=False) == 20.0


# ---------------------------------------------------------------------------
# Add_Experience wiring for spell-school casts (Phase 460) --
# AKGEN_reverse_engineering_report (2).md SS3.3's spell-school row
# ---------------------------------------------------------------------------


def test_execute_cast_awards_real_add_experience_credit_on_a_successful_relevant_cast():
    state = build_state()
    state.leaders[CASTER_ID].skills = _skills_with(Ability.NECROMANCY, 2)
    state.add_leader(LeaderState(78, 2, "Enemy Hero", LOCATION))
    request = CastRequest(spell=Spell.KILL_ENEMY, target=78)
    rng = ScriptedRandom([0.29, 0.5, 0.5])  # [0] under the 45% chance, [1:] Add_Experience gain draws

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is True
    assert state.leaders[CASTER_ID].experience_credit == 10  # round(10*(1+0.5-0.5))


def test_execute_cast_with_no_recorded_skill_grants_no_add_experience_credit():
    # caster.skills is None -- _roll_cast_success's own automatic-success
    # bypass lets the cast succeed, but SS3.3's own "skill 0 resta esclusa"
    # clause still applies since the caster's real skill is unrecorded.
    state = build_state()
    state.add_leader(LeaderState(78, None, "Wandering Hero", LOCATION))
    request = CastRequest(spell=Spell.CHARM, target=78)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is True
    assert state.leaders[CASTER_ID].experience_credit == 0


def test_execute_cast_wand_triggered_cast_at_natural_skill_0_grants_no_add_experience_credit():
    # wand_skill_level bypasses _roll_cast_success's own skill check, but
    # the caster's real (natural) Psychic skill is still 0 here -- the
    # bypass must not leak into Add_Experience eligibility.
    state = build_state()
    state.leaders[CASTER_ID].skills = _skills_with(Ability.NECROMANCY, 1)  # unrelated ability
    state.add_leader(LeaderState(78, 1, "Field Commander", LOCATION))
    state.add_army(ArmyState(1, 1, ArmyType.LEGION, Quality.GREEN, LOCATION, commanded_by=78))
    request = CastRequest(spell=Spell.ORATORY, target=78)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, wand_skill_level=2)

    assert result.applied is True
    assert state.leaders[CASTER_ID].experience_credit == 0


# ---------------------------------------------------------------------------
# Magic-school royal-title merit crediting (Phase 630) --
# AKGEN_embedded_catalogs.json.txt gw_format.royal_title_system entries
# 16/21/28/46 -- unlike Add_Experience above, this counter has no
# "skill 0 excluded" gate of its own.
# ---------------------------------------------------------------------------


def test_execute_cast_credits_elemental_school_title_merit():
    state = build_state()
    state.add_army(ArmyState(1, 1, ArmyType.LEGION, Quality.AVERAGE, LOCATION, movement_points=0, commanded_by=CASTER_ID))
    request = CastRequest(spell=Spell.MYSTIC_WINDS, target=CASTER_ID)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is True
    assert state.leaders[CASTER_ID].merit_tally.elemental_spell_casts == 1
    assert state.leaders[CASTER_ID].merit_tally.illusionist_spell_casts == 0
    assert state.leaders[CASTER_ID].merit_tally.necromancy_spell_casts == 0
    assert state.leaders[CASTER_ID].merit_tally.psychic_spell_casts == 0


def test_execute_cast_credits_illusionist_school_title_merit():
    state = build_state()
    state.leaders[CASTER_ID].skills = _skills_with(Ability.ILLUSION, 2)
    request = CastRequest(spell=Spell.ILLUS_ARMIES, target=CASTER_ID)
    rng = ScriptedRandom([0.01, 0.5, 0.5])  # 15% + 15%*2 = 45% chance

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is True
    assert state.leaders[CASTER_ID].merit_tally.illusionist_spell_casts == 1


def test_execute_cast_credits_necromancy_school_title_merit():
    state = build_state()
    state.battle_graveyard[LOCATION] = [GraveyardEntry(ArmyType.LEGION, Quality.VETERAN, kingdom_id=2)]
    state.leaders[CASTER_ID].skills = _skills_with(Ability.NECROMANCY, 1)
    request = CastRequest(spell=Spell.SKELETAL_ARMY, target=0)
    rng = ScriptedRandom([0.01, 0.5, 0.5])

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is True
    assert state.leaders[CASTER_ID].merit_tally.necromancy_spell_casts == 1


def test_execute_cast_credits_psychic_school_title_merit():
    state = build_state()
    request = CastRequest(spell=Spell.LOCATE_OBJECT, target=1)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is True
    assert state.leaders[CASTER_ID].merit_tally.psychic_spell_casts == 1


def test_execute_cast_charm_by_undead_caster_credits_necromancy_not_psychic():
    # _award_royal_title_spell_merit() reuses _spell_ability(), so it
    # inherits Charm's own Phase 183 Undead-caster override for free.
    state = build_state()
    state.leaders[CASTER_ID].alignment = Alignment.UNDEAD
    state.leaders[CASTER_ID].skills = _skills_with(Ability.NECROMANCY, 2)
    state.add_leader(LeaderState(78, None, "Wandering Hero", LOCATION))
    request = CastRequest(spell=Spell.CHARM, target=78)
    rng = ScriptedRandom([0.44, 0.5, 0.5])  # 15% + 15%*2 = 45% chance

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is True
    assert state.leaders[CASTER_ID].merit_tally.necromancy_spell_casts == 1
    assert state.leaders[CASTER_ID].merit_tally.psychic_spell_casts == 0


def test_execute_cast_white_magic_credits_no_school_title_merit():
    # Bless is Ability.WHITE -- the Priest office's own formula reads a
    # live ability-skill sum, not one of these 4 Tit_Pts counters.
    state = build_state()
    state.add_province(ProvinceState(ELSEWHERE, Terrain.PLAINS, Race.HUMAN))
    request = CastRequest(spell=Spell.BLESS, target=_target(ELSEWHERE))

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request)

    assert result.applied is True
    tally = state.leaders[CASTER_ID].merit_tally
    assert (tally.elemental_spell_casts, tally.illusionist_spell_casts, tally.necromancy_spell_casts, tally.psychic_spell_casts) == (
        0,
        0,
        0,
        0,
    )


def test_execute_cast_failed_cast_credits_no_school_title_merit():
    # Ability.ILLUSION, skill 1 -> 15%+15%*1 = 30% success chance
    # (matches test_illus_armies_can_target_the_caster_himself's own
    # formula); a 0.99 roll fails cleanly.
    state = build_state()
    state.leaders[CASTER_ID].skills = _skills_with(Ability.ILLUSION, 1)
    request = CastRequest(spell=Spell.ILLUS_ARMIES, target=CASTER_ID)
    rng = ScriptedRandom([0.99])

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=rng)

    assert result.applied is False
    assert state.leaders[CASTER_ID].merit_tally.illusionist_spell_casts == 0


# ---------------------------------------------------------------------------
# Province spell-chance halving (Phase 533) -- AKGEN_reverse_engineering_
# report (4).md SS8: each of the 5 protection amulets also halves the
# cast-success chance of any matching-college spell targeted at a province
# the amulet holder's own Kingdom owns. All 10 province-targeted, ability-
# mapped spells get one test each: caster skill level 4 (75% base chance),
# a rival Kingdom owning the target province and holding the matching
# amulet halves it to 37.5%; a single scripted 0.5 roll is > 37.5% (so the
# halved chance always fails here) and < 75% (so an unhalved cast at the
# same roll would have succeeded, per each spell's own pre-existing test
# above) -- the failure alone proves the multiplier reached the roll.
# ---------------------------------------------------------------------------


def _state_with_amulet_owned_province(amulet: Treasure, terrain: Terrain) -> GameState:
    state = build_state()
    state.add_province(ProvinceState(LOCATION, terrain, Race.HUMAN, owner_kingdom_id=2))
    state.add_leader(LeaderState(99, 2, "Amulet Holder", ELSEWHERE))
    state.add_item(amulet, owner_leader_id=99)
    return state


def test_part_sea_success_chance_halved_by_provinces_owning_kingdoms_anti_white_amulet():
    state = _state_with_amulet_owned_province(Treasure.AMULET_ANTI_WHITE, Terrain.SEA)
    state.leaders[CASTER_ID].skills = _skills_with(Ability.WHITE, 4)
    request = CastRequest(spell=Spell.PART_SEA, target=_target(LOCATION))

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=ScriptedRandom([0.5]))

    assert result.applied is False
    assert result.reason == "spell failed"


def test_flood_success_chance_halved_by_provinces_owning_kingdoms_anti_elemental_amulet():
    state = _state_with_amulet_owned_province(Treasure.AMULET_ANTI_ELEMENTAL, Terrain.PLAINS)
    state.leaders[CASTER_ID].skills = _skills_with(Ability.ELEMENTAL, 4)
    request = CastRequest(spell=Spell.FLOOD, target=_target(LOCATION))

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=ScriptedRandom([0.5]))

    assert result.applied is False
    assert result.reason == "spell failed"


def test_tornado_success_chance_halved_by_provinces_owning_kingdoms_anti_elemental_amulet():
    state = _state_with_amulet_owned_province(Treasure.AMULET_ANTI_ELEMENTAL, Terrain.PLAINS)
    state.leaders[CASTER_ID].skills = _skills_with(Ability.ELEMENTAL, 4)
    request = CastRequest(spell=Spell.TORNADO, target=_target(LOCATION))

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=ScriptedRandom([0.5]))

    assert result.applied is False
    assert result.reason == "spell failed"


def test_earthquake_success_chance_halved_by_provinces_owning_kingdoms_anti_elemental_amulet():
    state = _state_with_amulet_owned_province(Treasure.AMULET_ANTI_ELEMENTAL, Terrain.PLAINS)
    state.leaders[CASTER_ID].skills = _skills_with(Ability.ELEMENTAL, 4)
    request = CastRequest(spell=Spell.EARTHQUAKE, target=_target(LOCATION))

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=ScriptedRandom([0.5]))

    assert result.applied is False
    assert result.reason == "spell failed"


def test_bless_success_chance_halved_by_provinces_owning_kingdoms_anti_white_amulet():
    state = _state_with_amulet_owned_province(Treasure.AMULET_ANTI_WHITE, Terrain.PLAINS)
    state.leaders[CASTER_ID].skills = _skills_with(Ability.WHITE, 4)
    request = CastRequest(spell=Spell.BLESS, target=_target(LOCATION))

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=ScriptedRandom([0.5]))

    assert result.applied is False
    assert result.reason == "spell failed"


def test_illus_terrain_success_chance_halved_by_provinces_owning_kingdoms_anti_illusion_amulet():
    state = _state_with_amulet_owned_province(Treasure.AMULET_ANTI_ILLUSION, Terrain.PLAINS)
    state.leaders[CASTER_ID].skills = _skills_with(Ability.ILLUSION, 4)
    request = CastRequest(spell=Spell.ILLUS_TERRAIN, target=_target(LOCATION), terrain=Terrain.MTNS)

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=ScriptedRandom([0.5]))

    assert result.applied is False
    assert result.reason == "spell failed"


def test_illus_fog_success_chance_halved_by_provinces_owning_kingdoms_anti_illusion_amulet():
    state = _state_with_amulet_owned_province(Treasure.AMULET_ANTI_ILLUSION, Terrain.PLAINS)
    state.leaders[CASTER_ID].skills = _skills_with(Ability.ILLUSION, 4)
    request = CastRequest(spell=Spell.ILLUS_FOG, target=_target(LOCATION))

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=ScriptedRandom([0.5]))

    assert result.applied is False
    assert result.reason == "spell failed"


def test_plague_success_chance_halved_by_provinces_owning_kingdoms_anti_necromancy_amulet():
    state = _state_with_amulet_owned_province(Treasure.AMULET_ANTI_NECROMANCY, Terrain.PLAINS)
    state.leaders[CASTER_ID].skills = _skills_with(Ability.NECROMANCY, 4)
    request = CastRequest(spell=Spell.PLAGUE, target=_target(LOCATION))

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=ScriptedRandom([0.5]))

    assert result.applied is False
    assert result.reason == "spell failed"


def test_scar_terrain_success_chance_halved_by_provinces_owning_kingdoms_anti_necromancy_amulet():
    state = _state_with_amulet_owned_province(Treasure.AMULET_ANTI_NECROMANCY, Terrain.PLAINS)
    state.leaders[CASTER_ID].skills = _skills_with(Ability.NECROMANCY, 4)
    request = CastRequest(spell=Spell.SCAR_TERRAIN, target=_target(LOCATION))

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=ScriptedRandom([0.5]))

    assert result.applied is False
    assert result.reason == "spell failed"


def test_hide_feature_success_chance_halved_by_provinces_owning_kingdoms_anti_illusion_amulet():
    state = _state_with_amulet_owned_province(Treasure.AMULET_ANTI_ILLUSION, Terrain.PLAINS)
    state.leaders[CASTER_ID].skills = _skills_with(Ability.ILLUSION, 4)
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON))
    request = CastRequest(spell=Spell.HIDE_FEATURE, target=_target(LOCATION))

    result = execute_cast(state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=ScriptedRandom([0.5]))

    assert result.applied is False
    assert result.reason == "spell failed"


def test_earthquake_not_halved_when_target_province_has_no_owner():
    # Contrast case: same skill/roll setup as the halved test above, but
    # the province has no owner at all -- province_halves_spell_chance()
    # returns False, so the un-halved 75% chance beats the 0.5 roll.
    state = build_state()
    state.add_province(ProvinceState(LOCATION, Terrain.PLAINS, Race.HUMAN))  # owner_kingdom_id=None
    state.add_leader(LeaderState(99, 2, "Amulet Holder", ELSEWHERE))
    state.add_item(Treasure.AMULET_ANTI_ELEMENTAL, owner_leader_id=99)
    state.leaders[CASTER_ID].skills = _skills_with(Ability.ELEMENTAL, 4)
    request = CastRequest(spell=Spell.EARTHQUAKE, target=_target(LOCATION))

    # A successful cast also rolls Add_Experience's own two-roll gain
    # formula (turn/experience.py) -- two extra scripted values beyond
    # the cast-success roll itself.
    result = execute_cast(
        state, kingdom_id=1, leader_id=CASTER_ID, request=request, rng=ScriptedRandom([0.5, 0.5, 0.5])
    )

    assert result.applied is True
