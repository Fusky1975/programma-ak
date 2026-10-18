from __future__ import annotations

import random

import pytest

from ak_engine.models.advanced_ability import AdvancedAbility
from ak_engine.models.alignment import Alignment
from ak_engine.models.army_naming import make_army_name
from ak_engine.models.army_type import ArmyType
from ak_engine.models.discovery import DISCOVERY_NAME, Discovery, describe_discovery_line, discovery_effect_description
from ak_engine.models.feature import Feature, FeatureType, RaidEvent
from ak_engine.models.game_state import (
    ArmyState,
    BlackmailClaim,
    GameState,
    KingdomState,
    LeaderState,
    ProvinceState,
    SunkCargoEvent,
    UnpaidBlackmailPenalty,
)
from ak_engine.models.valhalla import VALHALLA_VISITOR_LEADER_ID
from ak_engine.models.game_type import GameType
from ak_engine.models.item import ItemInstance
from ak_engine.models.kingdom import SkillTable
from ak_engine.models.magic_feature import MagicFeature
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.monster import Monster, MonsterEngagementState
from ak_engine.models.office import OFFICE_NAME, Office
from ak_engine.models.power import Power, PowerCondition
from ak_engine.models.race import Race
from ak_engine.models.rumor import Rumor, RumorContent
from ak_engine.models.sex import Sex
from ak_engine.models.temper import Temper
from ak_engine.models.treasure import TREASURE_NAME, Treasure
from ak_engine.parser.gw_world import DiplomaticRelation
from ak_engine.turn.feature_power_execution import FeaturePowerAttemptResult
from ak_engine.turn.movement import Direction, neighbor_in_direction_wrapped
from ak_engine.turn.contested_province import IllegalMoveFromContestedError
from ak_engine.turn.random_encounter_execution import RandomEncounterResult
from ak_engine.report.turn_report import (
    ALREADY_ALLIED_TEMPLATE,
    ATTACK_DEVASTATING_HIT_TEMPLATE,
    CAUGHT_UP_TEMPLATE,
    DEFENSIVE_MARCH_TEMPLATE,
    DUEL_NO_EXCUSE_TEMPLATE,
    EXPLORE_ALREADY_MAXED_TEMPLATE,
    EXPLORE_NOT_PRESENT_PREFIX,
    FUNERAL_PYRE_TEMPLATE,
    HIRE_COUNTER_OFFER_TEMPLATE,
    ILLMOVE_TEMPLATE,
    INHERIT_TEMPLATE,
    NEMESIS_TEMPLATE,
    PRACTICE_ALREADY_MAXED_TEMPLATE,
    PRACTICE_TUTORED_TEMPLATE,
    DEFEND_TEMPLATE,
    DEFEND_REINFORCEMENT_TEMPLATE,
    DISBAND_TEMPLATE,
    LEAVE_TEMPLATES,
    PICKUP_TEMPLATES,
    QUEST_BUT_THEN_TEMPLATE,
    QUEST_RIDDLE_ANSWER_TEXT,
    QUEST_RIDDLE_TEXT,
    QUEST_VISIT_FULFILLED_TEXT,
    QUEST_VISIT_TEXT,
    RECRUIT_TEMPLATES,
    SEASON_ADVENT_TEMPLATE,
    SEASON_NAME,
    SEASON_PREFIX_TEMPLATE,
    SEASON_TRANSITION_TEMPLATE,
    SEARCH_FEATURE_ALREADY_SACKED_TEMPLATE,
    SNEAKUP_RANGE_BOW,
    SNEAKUP_RANGE_MELEE,
    SNEAKUP_RANGE_SPELL,
    SPY_GARRISON_APPROXIMATELY_TEMPLATE,
    SPY_LEADS_APPROXIMATELY_TEMPLATE,
    WILL_TEMPLATE,
    build_battle_army_names,
    compose_letter_report,
    describe_adventure_report,
    describe_alignment_victory_point_reduction,
    describe_election_report,
    describe_election_status_report,
    describe_final_standings_report,
    describe_map_report,
    describe_state_of_the_nation_report,
    describe_general_intelligence_report,
    describe_imperial_office_report,
    describe_armies_report,
    describe_characters_report,
    describe_diplomacy_report,
    describe_feature_discovery,
    describe_finances_report,
    describe_home_province_neighbors,
    describe_letter_reports,
    describe_provinces_report,
    describe_aspy,
    _bluck_cluck_leader_id,
    describe_battle,
    describe_quality_changes,
    render_battle_line_diagram,
    render_battle_reserve_sentences,
    describe_cast,
    describe_locate_object,
    render_locate_object,
    describe_kill_enemy_berserk_retaliation,
    describe_challenge,
    describe_curator_research,
    describe_encounter_combat,
    describe_patrol_combat,
    describe_random_encounter,
    describe_random_encounter_combat,
    describe_turn_results,
    describe_fire,
    describe_give,
    describe_hire,
    describe_defend,
    describe_defend_reinforcement,
    describe_cargo_boarded,
    describe_disband,
    describe_leave,
    describe_move,
    describe_naval_hug_coastline_stragglers,
    describe_transport_illegal_move,
    describe_pick_up,
    describe_practice,
    describe_sage_discovery,
    describe_pursue,
    describe_pursue_guessed_distance,
    describe_recruit,
    describe_rumor,
    describe_feature_power_attempt,
    describe_feature_power_condition_satisfied,
    describe_feature_power_condition_terms,
    describe_feature_power_needs_more_info,
    describe_feature_power_oracle_power_armies,
    describe_search,
    _search_province_name,
    describe_steal,
    describe_trail,
    describe_trail_intelligence,
    describe_use_mi,
    parse_template_choices,
    pick_variant,
    record_battle_narratives,
    record_battle_world_events,
    record_blackmail_narratives,
    record_illusory_fog_foreign_entry_world_events,
    record_move_world_events,
    record_plague_spread_world_events,
    record_spell_world_events,
    record_sunk_cargo_world_events,
    record_uncontested_conquest_world_events,
    record_wandering_world_events,
    render_blackmail_demand,
    render_blackmail_penalty,
    render_bystander_spell_notice,
    render_flood_world_event,
    render_fly_move_world_event,
    render_illus_terrain_world_event,
    render_illusory_fog_foreign_entry_note,
    render_plague_world_event,
    render_scar_terrain_cast_notice,
    render_scar_terrain_fite,
    render_scar_terrain_zero,
    render_wind_walk_move_world_event,
    render_already_allied,
    render_ally_proposed,
    render_ally_refused,
    render_assassinate_encounter_note,
    render_assassination_attempt,
    render_assassination_failed,
    render_assassination_ordered,
    render_assassination_success,
    render_could_not_be_assassinated,
    render_attack_devastating_hit,
    render_attack_hit,
    render_attack_missed,
    render_battle_winner,
    render_bluck_narration,
    render_boulder_throw_hit,
    render_boulder_throw_missed,
    render_breath_weapon_hit,
    render_breath_weapon_missed,
    render_caught_up,
    render_guessed_distance,
    render_cluck_narration,
    render_column_clash,
    render_commander_died_demoralized,
    render_commander_fled_demoralized,
    render_defensive_march,
    render_destroyed_army,
    render_explore_already_maxed,
    render_explore_continued,
    render_explore_progress,
    render_finance_army_costs,
    render_finance_leader_costs,
    render_finance_report_opening,
    render_finance_revenue,
    render_finance_treasury,
    render_finance_unpaid_armies,
    render_fire_arrow_attack,
    render_squeeze_attack,
    render_fire_hireling,
    render_flee_failure,
    render_funeral_pyre,
    render_generic_encounter,
    render_guardian_intimidated,
    render_guardian_pacified_by_fulfill,
    render_guardian_undeterred,
    render_hire_accepted,
    render_hire_counter_offer,
    render_illegal_move_attempted,
    render_illegal_move_choice,
    render_illegal_move_flooding_transport,
    render_illegal_move_insufficient_water_transport,
    render_illegal_move_mermen_air_transport,
    render_illegal_move_non_adjacent,
    render_illegal_move_occupied_retreat,
    render_hire_refused,
    render_ice_break_out_attempt,
    render_ice_break_out_success,
    render_ice_fall_damage,
    render_ice_ghost_immune,
    render_ice_immobilized,
    render_ice_steal_blocked,
    render_gold_give,
    render_ice_suspend_failed_to_hold,
    render_ice_wait_for_melt,
    render_inherit,
    render_inherit_as_heir,
    render_insufficient_gold,
    render_item_give,
    render_magic_feature_discovery,
    render_cast_no_treasure,
    render_spell_fizzled_in_combat,
    render_spell_cast_failed,
    render_cargo_boarded,
    render_defend,
    render_defend_reinforcement,
    render_disband_unit,
    render_flaming_scimitar_proc,
    render_leave_unit,
    render_skeletal_army_dug_grave,
    render_sunk_cargo,
    render_march,
    render_travel,
    render_naval_hug_coastline_stragglers_arrived,
    render_pickup_unit,
    render_recruit_unit,
    render_recruit_hired_mercenary,
    render_recruit_ally_fee,
    render_melee_attack,
    render_monster_offers_raid_truce,
    render_mortally_wounded,
    render_character_death,
    render_move_to_bow_range,
    render_move_to_melee_range,
    render_patrol_encounter,
    render_patrol_release,
    render_random_encounter_failure,
    render_random_encounter_intro,
    render_petrifying_gaze_hit,
    render_shadow_sword_drain,
    render_weapon_proc_line,
    render_stun_recovery,
    render_stunned,
    render_group_theft_from_survivor,
    render_group_theft_tense,
    render_group_spoils_from_survivor,
    render_group_spoils_from_corpse,
    render_treasure_theft_from_survivor,
    render_treasure_theft_tense,
    render_treasure_spoils_from_survivor,
    render_treasure_spoils_from_corpse,
    render_gold_spoils,
    render_challenge_search,
    render_army_quality_decreased,
    render_army_quality_increased,
    render_hero_deserted,
    render_hail_greeting,
    render_talk_rebuffed,
    render_talk_learned_hire_price,
    render_valhalla_visitor_rules,
    render_valhalla_visit_announcement,
    describe_valhalla_visit_announcement,
    render_practice_vain,
    describe_desertions,
    render_mercenary_army_wanders_away,
    render_mercenary_army_wanders_in,
    render_character_wanders_away,
    render_character_wanders_in,
    render_thief_searches_treasure,
    render_thief_search_failed,
    render_steal_treasure_inaccessible,
    render_battle_leader_intro,
    render_battle_leader_no_command,
    render_battle_leader_no_generals,
    render_monster_reinforcement_arrives,
    render_monster_reinforcement_helped,
    render_binoculars_preview,
    render_petrifying_gaze_missed,
    render_homeland_defense_morale,
    render_race_fanaticism,
    render_oratory_speech,
    render_monster_threat_death,
    render_bless_graveyard_outcome,
    render_skeletal_army_outcome,
    render_tornado_outcome,
    render_charm_outcome,
    render_illus_terrain_cast_outcome,
    render_plague_outcome,
    render_flood_cast_outcome,
    render_cast_announcement,
    render_kill_enemy_berserk_onset,
    render_monster_description,
    render_practice_already_maxed,
    render_practice_tutored,
    render_sage_discovery,
    render_sage_no_discovery,
    render_skill_book_read,
    render_pursuit_and_destroy,
    render_quest_errand_thanks,
    render_quote_of_the_week,
    render_guardian_poses_riddle,
    render_guardian_proposes_quest_location,
    render_quest_fled_in_fear,
    render_quest_hero_not_tasty,
    render_quest_insufficient_price,
    render_quest_insufficient_skill,
    render_quest_item_taken_anyway,
    render_quest_mockery,
    render_quest_no_agreement,
    render_quest_progress_acknowledged,
    render_quest_reward_already_given,
    render_quest_service_not_performed,
    render_quest_wrong_answer,
    render_retreat,
    render_search_attempt,
    render_search_feature_already_sacked,
    render_skeletal_army_fervor,
    render_sneak_detected,
    render_espionage_discovery,
    render_spy_adjacent_forces,
    render_spy_adjacent_owners,
    render_spy_army_type,
    render_spy_capital_province,
    render_spy_character_here,
    render_spy_elements_intro,
    render_spy_feature_knowledge,
    render_spy_garrison,
    render_spy_leads,
    render_spy_no_characters,
    render_spy_no_characters_or_forces,
    render_spy_owner,
    render_spy_report_closing,
    render_spy_report_opening,
    render_spy_tax_estimate,
    render_steal_caught_and_ransomed,
    render_tactical_comparison,
    render_take_gold,
    render_take_items,
    render_trade_deal_failed,
    render_trail_alignment,
    render_trail_armies_led,
    render_trail_king_allies,
    render_trail_king_finances,
    render_trail_king_no_allies,
    render_trail_king_no_provinces,
    render_trail_king_provinces,
    render_trail_no_armies_led,
    render_trail_no_treasures,
    render_trail_offices_held,
    render_trail_race,
    render_trail_temper,
    render_trail_treasures,
    render_troll_regeneration,
    render_uncontested_conquest,
    render_vampiric_bite,
    render_wandering_encounter,
    render_weapon_rally,
    render_will,
    missile_attack_flavor,
    tactical_margin_bucket,
    _best_ability,
    _leader_ability_description,
    _stranger_descriptor,
    _tell_align,
    _impulse2_candidates,
    _impulse3_candidates,
    _resolve_viewer_priest,
    _render_stranger_row,
)
from ak_engine.models.enums import SPELL_NAME, Ability, ActionCode, Spell
from ak_engine.models.weapon import Weapon
from ak_engine.turn.aspy_execution import SpottedCharacter, SpyReport
from ak_engine.turn.battle_line import BattleUnit
from ak_engine.turn.combat import Quality
from ak_engine.turn.battle_orchestrator import BattleReport, QualityChange
from ak_engine.turn.battle_resolution import BattleColumnResult, BattleResult
from ak_engine.turn.cast_decode import CastRequest
from ak_engine.turn.cast_execution import CastExecutionResult, LocateObjectResult
from ak_engine.turn.challenge_execution import ChallengeExecutionResult
from ak_engine.turn.challenge_pursue_decode import ChallengeRequest, PursueRequest
from ak_engine.turn.encounter import CombatRange, FireArrowShot, MeleeSwing
from ak_engine.turn.druidic_monster_aid import DruidicMonsterAssistance
from ak_engine.turn.emperor_election import ElectionCallOutcome, ElectionResult
from ak_engine.turn.expenses import MaintenanceResult
from ak_engine.turn.exploration import ExploreResult
from ak_engine.turn.hex_numbering import encode_hex_number
from ak_engine.turn.hire_fire_decode import FireRequest, HireRequest
from ak_engine.turn.movement import NORMAL_MAP_BOUNDS, MapBounds, neighbors
from ak_engine.turn.tax_base import compute_tax_base
from ak_engine.turn.wandering_units import WanderRelocation
from ak_engine.turn.aspy_defend_decode import DefendRequest
from ak_engine.turn.defend_execution import DefendReinforcement
from ak_engine.turn.move_execution import MoveExecutionResult, TransportIllegalMoveError
from ak_engine.turn.army_list_decode import ArmyListRequest
from ak_engine.turn.plan_dispatch import ArmyListExecutionResult, FireExecutionResult, HireExecutionResult, PhaseDispatchResult
from ak_engine.turn.practice_execution import PracticeExecutionResult
from ak_engine.turn.patrol_execution import PatrolExecutionResult
from ak_engine.turn.pursue_execution import PursueExecutionResult
from ak_engine.turn.recruit_decode import RecruitRequest
from ak_engine.turn.recruit_execution import RecruitedUnit, RecruitExecutionResult
from ak_engine.turn.search_decode import SearchRequest
from ak_engine.turn.search_execution import SearchExecutionResult
from ak_engine.turn.trade_execution import CuratorResearchResult, TradeExecutionResult
from ak_engine.turn.trail_execution import KingIntelligence, TrailExecutionResult
from ak_engine.turn.use_mi_execution import UseMIExecutionResult

from _helpers import ScriptedRandom


def _column(bres: int, attacker_source_id: int = 1, defender_source_id: int = 2) -> BattleColumnResult:
    return BattleColumnResult(
        attacker_strength=10.0,
        defender_strength=10.0,
        bres=bres,
        attacker_won=bres > 0,
        cluck_index=20,
        attacker_units=[BattleUnit(ArmyType.GARRISON, 10.0, source_id=attacker_source_id)],
        defender_units=[BattleUnit(ArmyType.LEGION, 10.0, source_id=defender_source_id)],
    )


# -- parse_template_choices ---------------------------------------------------


def test_parse_template_choices_reads_header_and_slices_variant_lines():
    raw = "2 1\n< retreated to ^S.\n< withdrew to ^S.\n"
    assert parse_template_choices(raw) == ["< retreated to ^S.", "< withdrew to ^S."]


def test_parse_template_choices_ignores_lines_past_the_declared_count():
    raw = "3 1\nfirst\nsecond\nthird\nfourth (unused)\n"
    assert parse_template_choices(raw) == ["first", "second", "third"]


def test_parse_template_choices_rejects_multiline_blockdepth():
    raw = "2 2\nfirst line one\nfirst line two\nsecond line one\nsecond line two\n"
    with pytest.raises(NotImplementedError):
        parse_template_choices(raw)


def test_parse_template_choices_rejects_a_short_file():
    raw = "3 1\nonly one line\n"
    with pytest.raises(ValueError):
        parse_template_choices(raw)


# -- pick_variant --------------------------------------------------------------


def test_pick_variant_uses_the_rng_choice_hook():
    rng = ScriptedRandom([], choice_indices=[1])
    assert pick_variant(["a", "b", "c"], rng) == "b"


# -- render_column_clash ----------------------------------------------------


def test_render_column_clash_names_both_armies_and_picks_a_margin_sentence():
    # bres=0 (a genuine per-column tie). All /R and {} draws scripted to
    # their "right/include" branch (0.9).
    column = _column(bres=0)
    rng = ScriptedRandom([0.9, 0.9, 0.9, 0.9], choice_indices=[0])
    result = render_column_clash(column, "the 260th Garrison", "the 45th Orcs", rng)
    assert result == "the 260th Garrison battled with the 45th Orcs and battled them to a standstill."


def test_render_column_clash_appends_a_plus_bucket_sentence():
    # bres=3. All draws scripted "left/exclude" (0.1).
    column = _column(bres=3)
    rng = ScriptedRandom([0.1, 0.1, 0.1, 0.1], choice_indices=[0])
    result = render_column_clash(column, "Attackia's host", "Defendia's line", rng)
    assert result == "Attackia's host fought Defendia's line and advanced at will."


def test_render_column_clash_resolves_sea_marker():
    # Phase 74: bres=-1, variant 0 (" gradually gave_ground/Swas_pushed_back.")
    # carries only a "/S" marker, no "/R" -- the opening clause's own "/R"
    # (fought/battled) and "{with }" inclusion each still consume one draw
    # (0.1 -> left choice / excluded).
    column = _column(bres=-1)
    rng = ScriptedRandom([0.1, 0.1], choice_indices=[0])
    result = render_column_clash(column, "A", "B", rng, is_sea=True)
    assert result == "A fought B and gradually was pushed back."


def test_render_column_clash_land_default_resolves_sea_marker_left():
    column = _column(bres=-1)
    rng = ScriptedRandom([0.1, 0.1], choice_indices=[0])
    result = render_column_clash(column, "A", "B", rng)
    assert result == "A fought B and gradually gave ground."


# -- render_bluck_narration / render_cluck_narration (Phase 388, real prose
# -- Phase 584, real BLUCK2/CLUCK2 catalog-pair selector Phase 605) --

# Phase 605: province(0,0) + attacker_leader_id=1 + defender_leader_id=2
# + phase -- sum is odd (phase=2, sum=5) for the primary catalog, even
# (phase=1, sum=4) for the secondary one, matching SAY.PAS's own
# Odd(_px+_py+_attl+_defl+_rphase) check exactly.
_PRIMARY_CATALOG_KWARGS = dict(province_coord=HexCoord(0, 0), attacker_leader_id=1, defender_leader_id=2, phase=2)
_SECONDARY_CATALOG_KWARGS = dict(province_coord=HexCoord(0, 0), attacker_leader_id=1, defender_leader_id=2, phase=1)


def test_render_bluck_narration_reads_the_battle_results_own_index():
    rng = ScriptedRandom([0.1] * 20)
    assert render_bluck_narration(
        BattleResult(bluck_index=9), "Aldric", "Borin", rng, **_PRIMARY_CATALOG_KWARGS
    ) == ("no luck of great significance seemed to affect the overall battle before it commenced.")
    rng = ScriptedRandom([0.1] * 20)
    assert render_bluck_narration(
        BattleResult(bluck_index=1), "Aldric", "Borin", rng, **_PRIMARY_CATALOG_KWARGS
    ) == (
        "Aldric's luck was awful, for a nasty rumor that enemy forces "
        "were approaching from the rear began to sweep through Aldric's "
        "troops!This gave Borin's forces a huge advantage."
    )


def test_render_bluck_narration_uses_the_secondary_catalog_on_an_even_parity_sum():
    rng = ScriptedRandom([0.1] * 20)
    result = render_bluck_narration(BattleResult(bluck_index=1), "Aldric", "Borin", rng, **_SECONDARY_CATALOG_KWARGS)
    assert result == (
        "the fortunes of war took a terrible turn against Aldric when "
        "Aldric's forces were trapped in a canyon and had to fight "
        "their way past prepared defenses."
    )


def test_render_cluck_narration_reads_the_columns_own_index_when_competitive():
    column = _column(bres=0)  # attacker_strength == defender_strength == 10.0, cluck_index=20
    rng = ScriptedRandom([0.1] * 20)
    assert render_cluck_narration(column, "144th Legion", rng, **_PRIMARY_CATALOG_KWARGS) == (
        "the contest was a slugfest decided by the courage of the men in hand-to-hand combat."
    )


def test_render_cluck_narration_returns_none_when_the_column_is_not_competitive():
    column = BattleColumnResult(
        attacker_strength=10.0,
        defender_strength=1.0,  # ratio 10.0, outside the [0.4, 2.5] gate
        bres=1,
        attacker_won=True,
        cluck_index=20,
    )
    rng = ScriptedRandom([])
    assert render_cluck_narration(column, "144th Legion", rng, **_PRIMARY_CATALOG_KWARGS) is None


def test_render_cluck_narration_uses_the_secondary_catalog_on_an_even_parity_sum():
    # Phase 605: CLUCK2.X2 is a mutually exclusive alternate catalog for
    # the same event, not a "fortune reversed itself" follow-up appended
    # after a separate reversal roll.
    column = _column(bres=0)  # cluck_index=20
    rng = ScriptedRandom([0.1] * 20)
    result = render_cluck_narration(column, "144th Legion", rng, **_SECONDARY_CATALOG_KWARGS)
    assert result == (
        "144th Legion expected to have the upper hand because they had "
        "constructed prepared defenses, but were suprised to discover "
        "that their opponents had done the same."
    )


# -- render_battle_winner ----------------------------------------------------


def test_render_battle_winner_returns_none_for_a_tie():
    battle_result = BattleResult(winner="tie")
    rng = ScriptedRandom([])
    assert render_battle_winner(battle_result, "Attackia", "Defendia", "the Dolphin Sea", rng) is None


def test_render_battle_winner_uses_winner_template_for_the_attacker():
    battle_result = BattleResult(winner="attacker")
    rng = ScriptedRandom([0.1, 0.1], choice_indices=[0])
    result = render_battle_winner(battle_result, "Attackia", "Defendia", "the Dolphin Sea", rng)
    assert result == "the forces of Attackia broke through and were victorious."


def test_render_battle_winner_uses_defwin_template_for_the_defender():
    battle_result = BattleResult(winner="defender")
    rng = ScriptedRandom([0.1, 0.1, 0.1], choice_indices=[2])
    result = render_battle_winner(battle_result, "Attackia", "Defendia", "the Dolphin Sea", rng)
    assert result == "the attacking Kingdom was defeated in its attempt to conquer the Dolphin Sea."


def test_render_battle_winner_resolves_sea_markers_land():
    # DEFWIN variant 1 carries two "/S" markers ("armies/Sfleets",
    # "pushed/Schased") plus one "/R" ("beaten/Rdefeated").
    battle_result = BattleResult(winner="defender")
    rng = ScriptedRandom([0.1], choice_indices=[1])
    result = render_battle_winner(battle_result, "Attackia", "Defendia", "the Dolphin Sea", rng)
    assert result == "Attackia's armies were beaten and pushed out of the Dolphin Sea."


def test_render_battle_winner_resolves_sea_markers_sea():
    battle_result = BattleResult(winner="defender")
    rng = ScriptedRandom([0.1], choice_indices=[1])
    result = render_battle_winner(battle_result, "Attackia", "Defendia", "the Dolphin Sea", rng, is_sea=True)
    assert result == "Attackia's fleets were beaten and chased out of the Dolphin Sea."


# -- render_destroyed_army ----------------------------------------------------


def test_render_destroyed_army_prefixes_the_winner_and_names_the_victim():
    rng = ScriptedRandom([], choice_indices=[2])
    assert render_destroyed_army("Attackia", "the 45th Orcs", rng) == "Attackia destroyed the 45th Orcs."


# -- render_pursuit_and_destroy ------------------------------------------------


def test_render_pursuit_and_destroy_concatenates_both_clauses():
    rng = ScriptedRandom([], choice_indices=[1, 2])  # pursuit variant 1, killarmy variant 2
    result = render_pursuit_and_destroy("Attackia", "the 45th Orcs", rng)
    assert result == "Attackia gave chase and destroyed the 45th Orcs."


# -- render_retreat ----------------------------------------------------------


def test_render_retreat_substitutes_name_destination_and_possessive():
    rng = ScriptedRandom([0.1, 0.1, 0.1], choice_indices=[5])
    result = render_retreat("Guerin", "Falkenheim", rng)
    assert result == "Guerin retired to Falkenheim, beaten but not broken."


def test_render_retreat_resolves_sea_marker_land():
    # Variant 2 ("< made/Rset_out for {the safety of }^S with > motley
    # army/SFleet.") carries a "/S" marker -- land keeps "army".
    rng = ScriptedRandom([0.1, 0.1], choice_indices=[2])
    result = render_retreat("Guerin", "Falkenheim", rng)
    assert result == "Guerin made for Falkenheim with Guerin's motley army."


def test_render_retreat_resolves_sea_marker_sea():
    rng = ScriptedRandom([0.1, 0.1], choice_indices=[2])
    result = render_retreat("Guerin", "Falkenheim", rng, is_sea=True)
    assert result == "Guerin made for Falkenheim with Guerin's motley Fleet."


def test_render_retreat_resolves_optional_blocks_for_other_variants():
    # Variant 0 has two /R choices (outer "retreated/Rfell_back" and the
    # nested one inside the optional block) followed by the block's own
    # inclusion draw.
    rng = ScriptedRandom([0.9, 0.9, 0.9], choice_indices=[0])
    result = render_retreat("Guerin", "Falkenheim", rng)
    assert result == "Guerin fell back to Falkenheim with what remained of Guerin's forces."


# -- describe_battle (integration) --------------------------------------------


def test_describe_battle_assembles_clash_winner_and_destroyed_sentences_in_order():
    column = _column(bres=3, attacker_source_id=10, defender_source_id=20)
    battle_result = BattleResult(winner="attacker", columns=[column])
    report = BattleReport(battle_result=battle_result, conquered=True, destroyed_army_ids=[20])

    # clash opening (2 draws) + bucket-3 variant 0's own "{almost }" (1 draw)
    # + winner-attacker variant 0 (2 draws) = 5 draws; killarmy variant 0 has
    # none.
    rng = ScriptedRandom([0.1, 0.1, 0.1, 0.1, 0.1], choice_indices=[0, 0, 0])
    lines = describe_battle(
        report,
        attacker_name="Attackia",
        defender_name="Defendia",
        province_name="the Dolphin Sea",
        state=GameState(),
        destination_names={},
        rng=rng,
    )
    # Phase 236: army_names is now synthesized via build_battle_army_names()
    # -- make_army_name(10, ArmyType.GARRISON, Race.HUMAN) / (20, LEGION,
    # Race.HUMAN), the same names _column()'s own unit types/ids produce.
    assert lines == [
        "10th Garrison fought 20th Legion and advanced at will.",
        "the forces of Attackia broke through and were victorious.",
        "Attackia annihilated 20th Legion.",
    ]


def test_describe_battle_renders_batldr_lines_before_everything_else():
    # Phase 649: attacker commanders first (in the report's own stored
    # order), then defender commanders -- before BLUCK/clash/winner. An
    # empty BattleResult (default "tie" winner, no columns) isolates this
    # from every other describe_battle() sub-renderer.
    state = GameState()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Aldric", location=HexCoord(0, 0)))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Borin", location=HexCoord(0, 0)))
    report = BattleReport(
        battle_result=BattleResult(),
        conquered=False,
        attacker_commanding_leader_ids=[1],
        defender_commanding_leader_ids=[2],
    )

    rng = ScriptedRandom([0.1] * 20, choice_indices=[0, 0])
    lines = describe_battle(
        report,
        attacker_name="Attackia",
        defender_name="Defendia",
        province_name="the Dolphin Sea",
        state=state,
        destination_names={},
        rng=rng,
    )

    assert lines == [
        "Aldric led Aldric's armies into the battle.",
        "Borin led Borin's armies into the battle.",
    ]


def test_describe_battle_skips_a_commanding_leader_no_longer_in_state():
    # No source, don't guess -- a leader id with no matching LeaderState
    # (e.g. died earlier the same turn) is silently omitted.
    state = GameState()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Aldric", location=HexCoord(0, 0)))
    report = BattleReport(
        battle_result=BattleResult(),
        conquered=False,
        attacker_commanding_leader_ids=[1, 999],
    )

    rng = ScriptedRandom([0.1] * 20, choice_indices=[0])
    lines = describe_battle(
        report,
        attacker_name="Attackia",
        defender_name="Defendia",
        province_name="the Dolphin Sea",
        state=state,
        destination_names={},
        rng=rng,
    )

    assert lines == ["Aldric led Aldric's armies into the battle."]


# -- Phase 739: _ADishK/_ADishF (duel-loser demoralization narrative) --


def test_describe_battle_renders_the_died_narration_for_an_ordinary_duel_loss():
    state = GameState()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Aldric", location=HexCoord(0, 0)))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Borin", location=HexCoord(0, 0)))
    report = BattleReport(
        battle_result=BattleResult(),
        conquered=False,
        attacker_commander_leader_id=1,
        defender_commander_leader_id=2,
        duel_loser_side="defender",
        duel_loser_fled=False,
    )

    rng = ScriptedRandom([0.1] * 20)
    lines = describe_battle(
        report,
        attacker_name="Attackia",
        defender_name="Defendia",
        province_name="the Dolphin Sea",
        state=state,
        destination_names={},
        rng=rng,
    )

    assert lines == [
        "The forces commanded by Borin were disheartened by Borin's death, "
        "but still they pressed forward with some hope of victory."
    ]


def test_describe_battle_renders_the_fled_narration_when_the_loser_fled():
    state = GameState()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Aldric", location=HexCoord(0, 0)))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Borin", location=HexCoord(0, 0)))
    report = BattleReport(
        battle_result=BattleResult(),
        conquered=False,
        attacker_commander_leader_id=1,
        defender_commander_leader_id=2,
        duel_loser_side="attacker",
        duel_loser_fled=True,
    )

    rng = ScriptedRandom([0.1] * 20)
    lines = describe_battle(
        report,
        attacker_name="Attackia",
        defender_name="Defendia",
        province_name="the Dolphin Sea",
        state=state,
        destination_names={},
        rng=rng,
    )

    assert lines == [
        "The forces commanded by Aldric were disappointed by Aldric's "
        "cowardice.They marched on, though with lessened confidence."
    ]


def test_describe_battle_renders_no_duel_demoralization_line_when_no_duel_occurred():
    state = GameState()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Aldric", location=HexCoord(0, 0)))
    report = BattleReport(battle_result=BattleResult(), conquered=False, attacker_commander_leader_id=1)

    rng = ScriptedRandom([0.1] * 20)
    lines = describe_battle(
        report,
        attacker_name="Attackia",
        defender_name="Defendia",
        province_name="the Dolphin Sea",
        state=state,
        destination_names={},
        rng=rng,
    )

    assert lines == []


def test_describe_battle_skips_the_duel_demoralization_line_when_the_loser_no_longer_resolves():
    state = GameState()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Aldric", location=HexCoord(0, 0)))
    report = BattleReport(
        battle_result=BattleResult(),
        conquered=False,
        attacker_commander_leader_id=1,
        defender_commander_leader_id=999,  # died earlier the same turn
        duel_loser_side="defender",
    )

    rng = ScriptedRandom([0.1] * 20)
    lines = describe_battle(
        report,
        attacker_name="Attackia",
        defender_name="Defendia",
        province_name="the Dolphin Sea",
        state=state,
        destination_names={},
        rng=rng,
    )

    assert lines == []


def test_describe_battle_renders_present_but_not_commanding_leaders():
    # Phase 658: a present-but-not-commanding leader gets the "was there,
    # leading no armies" sentence, right after that same side's own
    # commanders -- attacker side fully (commander then present), then
    # the defender side fully, matching the real per-side loop order.
    state = GameState()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Aldric", location=HexCoord(0, 0)))
    state.add_leader(LeaderState(2, kingdom_id=1, name="Borin", location=HexCoord(0, 0)))
    state.add_leader(LeaderState(3, kingdom_id=2, name="Vraxis", location=HexCoord(0, 0)))
    report = BattleReport(
        battle_result=BattleResult(),
        conquered=False,
        attacker_commanding_leader_ids=[1],
        attacker_present_leader_ids=[2],
        defender_present_leader_ids=[3],
    )

    rng = ScriptedRandom([0.1] * 20, choice_indices=[0, 0])
    lines = describe_battle(
        report,
        attacker_name="Attackia",
        defender_name="Defendia",
        province_name="the Dolphin Sea",
        state=state,
        destination_names={},
        rng=rng,
    )

    assert lines == [
        "Aldric led Aldric's armies into the battle.",
        "Borin was there, leading no armies.",
        "Vraxis was there, leading no armies.",
    ]


def test_describe_battle_skips_a_present_leader_no_longer_in_state():
    state = GameState()
    report = BattleReport(battle_result=BattleResult(), conquered=False, attacker_present_leader_ids=[999])

    lines = describe_battle(
        report,
        attacker_name="Attackia",
        defender_name="Defendia",
        province_name="the Dolphin Sea",
        state=state,
        destination_names={},
        rng=ScriptedRandom([]),
    )

    assert lines == []


def test_describe_battle_renders_no_generals_line_for_a_side_with_nobody_present():
    # Phase 927: `_BLList`'s own third real case (`IF lp = 1 THEN`) -- a
    # side with NO leaders present at all, commanding or not, is narrated
    # with the *province owner's* (defender's) Kingdom name even when
    # it's the attacking side's own empty roster that triggered it -- a
    # real, sourced asymmetry (`SAY.PAS`'s own unconditional `_attl:=
    # powner[_px,_py]` for both `fn` values), not a bug to "fix" to use
    # each side's own Kingdom. Here only the attacker side is empty; the
    # defender has a real commander and gets the ordinary BATLDR sentence.
    state = GameState()
    state.add_leader(LeaderState(1, kingdom_id=2, name="Vraxis", location=HexCoord(0, 0)))
    report = BattleReport(
        battle_result=BattleResult(),
        conquered=False,
        province_coord=HexCoord(0, 0),
        defender_kingdom_id=2,
        defender_commanding_leader_ids=[1],
    )

    lines = describe_battle(
        report,
        attacker_name="Attackia",
        defender_name="Defendia",
        province_name="the Dolphin Sea",
        state=state,
        destination_names={},
        rng=ScriptedRandom([0.1] * 10, choice_indices=[0]),
    )

    assert lines == [
        "no generals were present to lead the forces of Defendia.",
        "Vraxis led Vraxis's armies into the battle.",
    ]


def test_describe_battle_omits_no_generals_line_for_the_instant_conquest_shortcut():
    # Phase 927: `province_coord=None` (the default) is this project's own
    # established "no real battle fought" signal (the same gate BLUCK/
    # CLUCK already use) -- both rosters being empty here must NOT invent
    # a "no generals" sentence for a battle that never actually happened.
    report = BattleReport(battle_result=BattleResult(), conquered=True)

    lines = describe_battle(
        report,
        attacker_name="Attackia",
        defender_name="Defendia",
        province_name="the Dolphin Sea",
        state=GameState(),
        destination_names={},
        rng=ScriptedRandom([]),
    )

    assert lines == []


def test_describe_battle_renders_homeland_defense_morale_right_after_the_leader_roster():
    # Phase 852: attacker home-province leaders, then defender home-province
    # leaders, right after the BATLDR roster (both sides) and before the
    # duel-demoralization line.
    state = GameState()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Aldric", location=HexCoord(0, 0)))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Borin", location=HexCoord(0, 0)))
    report = BattleReport(
        battle_result=BattleResult(),
        conquered=False,
        attacker_commanding_leader_ids=[1],
        defender_commanding_leader_ids=[2],
        attacker_home_province_leader_ids=[1],
        defender_home_province_leader_ids=[2],
    )

    rng = ScriptedRandom([0.1] * 20, choice_indices=[0, 0])
    lines = describe_battle(
        report,
        attacker_name="Attackia",
        defender_name="Defendia",
        province_name="the Dolphin Sea",
        state=state,
        destination_names={},
        rng=rng,
    )

    assert lines == [
        "Aldric led Aldric's armies into the battle.",
        "Borin led Borin's armies into the battle.",
        "Aldric's troops were prepared to fight desperately for their homeland.",
        "Borin's troops were prepared to fight desperately for their homeland.",
    ]


def test_describe_battle_skips_a_home_province_leader_no_longer_in_state():
    # No source, don't guess -- same "died earlier the same turn" convention
    # every other BATLDR-adjacent field in this composer already uses.
    state = GameState()
    report = BattleReport(battle_result=BattleResult(), conquered=False, attacker_home_province_leader_ids=[999])

    lines = describe_battle(
        report,
        attacker_name="Attackia",
        defender_name="Defendia",
        province_name="the Dolphin Sea",
        state=state,
        destination_names={},
        rng=ScriptedRandom([]),
    )

    assert lines == []


def test_describe_battle_omits_homeland_defense_morale_when_nobody_is_home():
    # Non-regression: the new field defaults to an empty list, so a battle
    # away from home renders exactly as it did before Phase 852.
    state = GameState()
    state.add_leader(LeaderState(1, kingdom_id=1, name="Aldric", location=HexCoord(0, 0)))
    report = BattleReport(
        battle_result=BattleResult(),
        conquered=False,
        attacker_commanding_leader_ids=[1],
    )

    rng = ScriptedRandom([0.1] * 20, choice_indices=[0])
    lines = describe_battle(
        report,
        attacker_name="Attackia",
        defender_name="Defendia",
        province_name="the Dolphin Sea",
        state=state,
        destination_names={},
        rng=rng,
    )

    assert lines == ["Aldric led Aldric's armies into the battle."]


def test_describe_battle_renders_race_fanaticism_right_after_home_province_morale():
    # Phase 895: attacker race-fanatic units, then defender ones, right
    # after the _BHome block and before the duel-demoralization line.
    state = GameState()
    state.add_leader(LeaderState(501, kingdom_id=1, name="Sir Roland", location=HexCoord(0, 0)))
    column = _column(bres=3, attacker_source_id=101, defender_source_id=201)
    battle_result = BattleResult(winner="attacker", columns=[column])
    report = BattleReport(
        battle_result=battle_result,
        conquered=False,
        attacker_race_fanatic_units=((101, Race.HUMAN, 501),),
    )

    rng = ScriptedRandom([0.1] * 40, choice_indices=[0, 0, 0, 0, 0])
    lines = describe_battle(
        report,
        attacker_name="Attackia",
        defender_name="Defendia",
        province_name="the Dolphin Sea",
        state=state,
        destination_names={},
        rng=rng,
    )

    assert "101st Garrison were inspired to fanaticism by Sir Roland, their glorious Savior of Humankind." in lines


def test_describe_battle_skips_race_fanaticism_when_the_title_holder_is_no_longer_in_state():
    # Same "died earlier the same turn, no data, don't guess" convention
    # _BHome's own equivalent test already established.
    state = GameState()
    column = _column(bres=3, attacker_source_id=101, defender_source_id=201)
    battle_result = BattleResult(winner="attacker", columns=[column])
    report = BattleReport(
        battle_result=battle_result,
        conquered=False,
        attacker_race_fanatic_units=((101, Race.HUMAN, 999),),
    )

    rng = ScriptedRandom([0.1] * 40, choice_indices=[0, 0, 0, 0, 0])
    lines = describe_battle(
        report,
        attacker_name="Attackia",
        defender_name="Defendia",
        province_name="the Dolphin Sea",
        state=state,
        destination_names={},
        rng=rng,
    )

    assert not any("fanaticism" in line for line in lines)


def test_describe_battle_skips_race_fanaticism_for_an_army_with_no_name():
    # Same "no source_id, don't guess" convention the monster-assistance
    # wiring right below this test already uses.
    state = GameState()
    state.add_leader(LeaderState(501, kingdom_id=1, name="Sir Roland", location=HexCoord(0, 0)))
    report = BattleReport(
        battle_result=BattleResult(),
        conquered=False,
        attacker_race_fanatic_units=((101, Race.HUMAN, 501),),
    )

    lines = describe_battle(
        report,
        attacker_name="Attackia",
        defender_name="Defendia",
        province_name="the Dolphin Sea",
        state=state,
        destination_names={},
        rng=ScriptedRandom([]),
    )

    assert lines == []


def test_describe_battle_renders_monster_assistance_before_everything_else():
    # Phase 657: MCOME/MFIGHT render right after the BATLDR roster, before
    # BLUCK and the per-column clash sentences.
    column = _column(bres=3, attacker_source_id=10, defender_source_id=20)
    battle_result = BattleResult(winner="attacker", columns=[column])
    report = BattleReport(
        battle_result=battle_result,
        conquered=True,
        destroyed_army_ids=[20],
        attacker_monster_assistance={
            0: DruidicMonsterAssistance(strength_bonus=21, monster=Monster.GO_DRAGON, feature_id=1)
        },
    )

    rng = ScriptedRandom([0.1] * 40, choice_indices=[0, 0, 0, 0, 0])
    lines = describe_battle(
        report,
        attacker_name="Attackia",
        defender_name="Defendia",
        province_name="the Dolphin Sea",
        state=GameState(),
        destination_names={},
        rng=rng,
    )

    assert lines == [
        "Gold Dragon, hearing of the peril of the Druidic king, arrived at the battle to fight with 10th Garrison.",
        "Gold Dragon was of some slight help in the battle.",
        "10th Garrison fought 20th Legion and advanced at will.",
        "the forces of Attackia broke through and were victorious.",
        "Attackia annihilated 20th Legion.",
    ]


def test_describe_battle_renders_defender_side_monster_assistance_too():
    column = _column(bres=-3, attacker_source_id=10, defender_source_id=20)
    battle_result = BattleResult(winner="defender", columns=[column])
    report = BattleReport(
        battle_result=battle_result,
        conquered=False,
        defender_monster_assistance={
            0: DruidicMonsterAssistance(strength_bonus=21, monster=Monster.GO_DRAGON, feature_id=1)
        },
    )

    rng = ScriptedRandom([0.1] * 40, choice_indices=[0, 0, 0, 0, 0])
    lines = describe_battle(
        report,
        attacker_name="Attackia",
        defender_name="Defendia",
        province_name="the Dolphin Sea",
        state=GameState(),
        destination_names={},
        rng=rng,
    )

    assert lines[0] == "Gold Dragon, hearing of the peril of the Druidic king, arrived at the battle to fight with 20th Legion."
    assert lines[1] == "Gold Dragon was of some slight help in the battle."


def test_describe_battle_skips_monster_assistance_for_a_column_with_no_named_army():
    # Same "no source_id, don't guess" convention every other sub-renderer
    # in this function already uses.
    column = BattleColumnResult(
        attacker_strength=10.0,
        defender_strength=10.0,
        bres=0,
        attacker_won=False,
        cluck_index=20,
        attacker_units=[BattleUnit(ArmyType.GARRISON, 10.0, source_id=None)],
        defender_units=[BattleUnit(ArmyType.LEGION, 10.0, source_id=2)],
    )
    battle_result = BattleResult(winner="tie", columns=[column])
    report = BattleReport(
        battle_result=battle_result,
        conquered=False,
        attacker_monster_assistance={
            0: DruidicMonsterAssistance(strength_bonus=21, monster=Monster.GO_DRAGON, feature_id=1)
        },
    )

    lines = describe_battle(
        report,
        attacker_name="Attackia",
        defender_name="Defendia",
        province_name="the Dolphin Sea",
        state=GameState(),
        destination_names={},
        rng=ScriptedRandom([]),
    )

    assert lines == []


def test_describe_battle_threads_is_sea_to_every_sub_renderer():
    # Phase 74: is_sea propagates to both the per-column clash sentence
    # (bucket -1 variant 0, "/S" only) and the winner sentence (DEFWIN
    # variant 1, "/S" x2 + "/R").
    column = _column(bres=-1, attacker_source_id=10, defender_source_id=20)
    battle_result = BattleResult(winner="defender", columns=[column])
    report = BattleReport(battle_result=battle_result, conquered=False)

    rng = ScriptedRandom([0.1, 0.1, 0.1], choice_indices=[0, 1])
    lines = describe_battle(
        report,
        attacker_name="Attackia",
        defender_name="Defendia",
        province_name="the Dolphin Sea",
        state=GameState(),
        destination_names={},
        rng=rng,
        is_sea=True,
    )
    assert lines == [
        "10th Garrison fought 20th Legion and gradually was pushed back.",
        "Attackia's fleets were beaten and chased out of the Dolphin Sea.",
    ]


def test_describe_battle_skips_unnamed_armies_and_ties_without_erroring():
    # A front unit with no source_id at all (no backing ArmyState, e.g. a
    # pure combat calculation) is the one remaining "can't be named" case
    # as of Phase 236 -- build_battle_army_names() can synthesize a name
    # for any real id, but not for None.
    column = BattleColumnResult(
        attacker_strength=10.0,
        defender_strength=10.0,
        bres=0,
        attacker_won=False,
        cluck_index=20,
        attacker_units=[BattleUnit(ArmyType.GARRISON, 10.0, source_id=None)],
        defender_units=[BattleUnit(ArmyType.LEGION, 10.0, source_id=2)],
    )
    battle_result = BattleResult(winner="tie", columns=[column])
    report = BattleReport(battle_result=battle_result, conquered=False)

    rng = ScriptedRandom([])
    lines = describe_battle(
        report,
        attacker_name="Attackia",
        defender_name="Defendia",
        province_name="the Dolphin Sea",
        state=GameState(),
        destination_names={},
        rng=rng,
    )
    assert lines == []


def test_describe_battle_appends_quality_change_sentences_after_retreats():
    # Phase 610: quality_changes narration is the final section describe_
    # battle() appends, after clashes/winner/destroyed/pursuit/retreats.
    column = _column(bres=3, attacker_source_id=10, defender_source_id=20)
    battle_result = BattleResult(winner="attacker", columns=[column])
    report = BattleReport(
        battle_result=battle_result,
        conquered=True,
        quality_changes={10: QualityChange(old=Quality.VETERAN, new=Quality.CRACK)},
    )

    # clash opening (2 draws) + bucket-3 variant 0's own "{almost }" (1 draw)
    # + winner-attacker variant 0 (2 draws) + INCQ variant 0's own "/R"
    # alternations -- generously padded rather than counted exactly.
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0, 0, 0])
    lines = describe_battle(
        report,
        attacker_name="Attackia",
        defender_name="Defendia",
        province_name="the Dolphin Sea",
        state=GameState(),
        destination_names={},
        rng=rng,
    )
    assert lines == [
        "10th Garrison fought 20th Legion and advanced at will.",
        "the forces of Attackia broke through and were victorious.",
        "10th Garrison proved its mettle in the battle and we now rate it a Crack unit.",
    ]


# -- render_battle_line_diagram (Phase 1035) ---------------------------------


def test_render_battle_line_diagram_matches_a_real_one_column_sample():
    # tests/fixtures/reports/G3/SE3__T6.K6 -- Kahn (kingdom 6) attacks
    # Gnarlia (#1301), defended by the independent Hero Fingol (#27), no
    # Kingdom owner. Real diagram (border bytes aside, and this
    # renderer's own documented "always show the quality letter"
    # simplification): 3 attacker Legions (144th, 219th, 142nd/Crack)
    # printed rear-to-front, defender's single 141st/Average Bowmen
    # marked with Fingol's own leader_id (27), not a Kingdom id.
    column = BattleColumnResult(
        attacker_strength=0.0, defender_strength=0.0, bres=0, attacker_won=True, cluck_index=9,
        attacker_units=[
            BattleUnit(ArmyType.LEGION, 10.0, source_id=144, quality=Quality.AVERAGE, kingdom_id=6),
            BattleUnit(ArmyType.LEGION, 10.0, source_id=219, quality=Quality.AVERAGE, kingdom_id=6),
            BattleUnit(ArmyType.LEGION, 10.0, source_id=142, quality=Quality.CRACK, kingdom_id=6),
        ],
        defender_units=[
            BattleUnit(ArmyType.BOWMEN, 5.0, source_id=141, quality=Quality.AVERAGE, kingdom_id=None, commanded_by=27),
        ],
    )
    result = BattleResult(columns=[column])

    assert render_battle_line_diagram(result, "Gnarlia", HexCoord(13, 1)) == [
        "  ATTACKING ARMY, Battle of Gnarlia (1301):",
        "",
        " 142nd/C  ",
        "  Legion  ",
        "    06    ",
        "          ",
        " 219th/A  ",
        "  Legion  ",
        "    06    ",
        "          ",
        " 144th/A  ",
        "  Legion  ",
        "    06    ",
        "----------",
        "    27    ",
        " 141st/A  ",
        "  Bowmen  ",
        "          ",
        "  DEFENDING ARMY",
    ]


def test_render_battle_line_diagram_a_ragged_line_sits_in_the_columns_assign_battle_lines_gave_it():
    # tests/fixtures/reports/G3/SE3__T6.K1 -- 11 attacker units dealt
    # round-robin into 5 columns: column 0 alone reaches a 3rd (rearmost)
    # line (the real `assign_battle_lines()` round-robin gives the extra
    # depth to the lowest-indexed columns, not a centered sub-block) --
    # confirmed directly against the real sample's own raw bytes.
    columns = [
        BattleColumnResult(
            attacker_strength=0.0, defender_strength=0.0, bres=0, attacker_won=True, cluck_index=9,
            attacker_units=units, defender_units=[],
        )
        for units in (
            [
                BattleUnit(ArmyType.BOWMEN, 1.0, source_id=316, quality=Quality.VETERAN, kingdom_id=1),
                BattleUnit(ArmyType.LEGION, 1.0, source_id=282, quality=Quality.VETERAN, kingdom_id=1),
                BattleUnit(ArmyType.LEGION, 1.0, source_id=267, quality=Quality.AVERAGE, kingdom_id=1),
            ],
            [
                BattleUnit(ArmyType.DRAGON_WING, 1.0, source_id=293, quality=Quality.AVERAGE, kingdom_id=1),
                BattleUnit(ArmyType.CHARIOTS, 1.0, source_id=70, quality=Quality.CRACK, kingdom_id=1),
            ],
            [
                BattleUnit(ArmyType.TROLLS, 1.0, source_id=317, quality=Quality.AVERAGE, kingdom_id=1),
                BattleUnit(ArmyType.LEGION, 1.0, source_id=71, quality=Quality.VETERAN, kingdom_id=1),
            ],
            [
                BattleUnit(ArmyType.DRAGON_WING, 1.0, source_id=314, quality=Quality.VETERAN, kingdom_id=1),
                BattleUnit(ArmyType.LEGION, 1.0, source_id=283, quality=Quality.VETERAN, kingdom_id=1),
            ],
            [
                BattleUnit(ArmyType.TROLLS, 1.0, source_id=318, quality=Quality.AVERAGE, kingdom_id=1),
                BattleUnit(ArmyType.CHARIOTS, 1.0, source_id=233, quality=Quality.AVERAGE, kingdom_id=1),
            ],
        )
    ]
    result = BattleResult(columns=columns)

    lines = render_battle_line_diagram(result, "Chaco", HexCoord(5, 4))
    assert lines[0] == "  ATTACKING ARMY, Battle of Chaco (0504):"
    # The rearmost (3rd) line has only column 0 populated -- the other 4
    # columns render as blank cells, not centered elsewhere in the row.
    assert lines[2] == " 267th/A  " + " " * 40
    assert lines[3] == "  Legion  " + " " * 40
    assert lines[4] == "    01    " + " " * 40
    assert lines[13] == "-" * 50


def test_render_battle_line_diagram_defender_shows_kingdom_id_when_kingdom_owned():
    column = BattleColumnResult(
        attacker_strength=0.0, defender_strength=0.0, bres=0, attacker_won=False, cluck_index=9,
        attacker_units=[BattleUnit(ArmyType.LEGION, 1.0, source_id=1, kingdom_id=1)],
        defender_units=[BattleUnit(ArmyType.LEGION, 1.0, source_id=2, kingdom_id=4)],
    )
    result = BattleResult(columns=[column])

    lines = render_battle_line_diagram(result, "Keep", HexCoord(1, 1))
    # separator, then defender number row first.
    assert lines[5] == "----------"
    assert lines[6] == "    04    "


def test_render_battle_line_diagram_defender_shows_gc_when_no_commander_present():
    column = BattleColumnResult(
        attacker_strength=0.0, defender_strength=0.0, bres=0, attacker_won=False, cluck_index=9,
        attacker_units=[BattleUnit(ArmyType.LEGION, 1.0, source_id=1, kingdom_id=1)],
        defender_units=[BattleUnit(ArmyType.LEGION, 1.0, source_id=2, kingdom_id=None, commanded_by=None)],
    )
    result = BattleResult(columns=[column])

    lines = render_battle_line_diagram(result, "Keep", HexCoord(1, 1))
    assert lines[6] == "    GC    "


def test_render_battle_line_diagram_skeletal_flag_appends_s_after_the_quality_letter():
    column = BattleColumnResult(
        attacker_strength=0.0, defender_strength=0.0, bres=0, attacker_won=True, cluck_index=9,
        attacker_units=[BattleUnit(ArmyType.LEGION, 1.0, source_id=71, quality=Quality.CRACK, kingdom_id=1, is_skeletal=True)],
        defender_units=[BattleUnit(ArmyType.LEGION, 1.0, source_id=2, kingdom_id=4)],
    )
    result = BattleResult(columns=[column])

    lines = render_battle_line_diagram(result, "Keep", HexCoord(1, 1))
    assert lines[2] == " 71st/CS  "


def test_render_battle_line_diagram_skips_a_unit_with_no_source_id():
    # No backing ArmyState (a pure combat calculation) -- rendered as a
    # blank cell, the same "no source, don't guess" convention
    # build_battle_army_names() already uses for this exact case.
    column = BattleColumnResult(
        attacker_strength=0.0, defender_strength=0.0, bres=0, attacker_won=True, cluck_index=9,
        attacker_units=[BattleUnit(ArmyType.LEGION, 1.0, source_id=None, kingdom_id=1)],
        defender_units=[BattleUnit(ArmyType.LEGION, 1.0, source_id=2, kingdom_id=4)],
    )
    result = BattleResult(columns=[column])

    lines = render_battle_line_diagram(result, "Keep", HexCoord(1, 1))
    assert lines[2] == " " * 10
    assert lines[3] == " " * 10
    assert lines[4] == " " * 10


def test_render_battle_line_diagram_returns_empty_list_for_no_columns():
    result = BattleResult(columns=[])
    assert render_battle_line_diagram(result, "Keep", HexCoord(1, 1)) == []


def test_describe_battle_skips_diagram_when_province_coord_is_unset():
    # The instant-conquest/no-real-battle shortcut (Phase 927's own
    # "was this a real battle" gate) -- no province_coord means no
    # diagram either, matching BLUCK/CLUCK/the leader roster's own gate.
    column = _column(bres=3, attacker_source_id=10, defender_source_id=20)
    battle_result = BattleResult(winner="attacker", columns=[column])
    report = BattleReport(battle_result=battle_result, conquered=True)

    rng = ScriptedRandom([0.1] * 10, choice_indices=[0, 0, 0])
    lines = describe_battle(
        report,
        attacker_name="Attackia",
        defender_name="Defendia",
        province_name="the Dolphin Sea",
        state=GameState(),
        destination_names={},
        rng=rng,
    )
    assert lines[0] != "The armies were drawn up into lines of battle as shown here:"


# -- render_battle_reserve_sentences (Phase 1036) ----------------------------


def test_render_battle_reserve_sentences_matches_a_real_one_column_sample():
    # tests/fixtures/reports/G3/SE3__T6.K1:274-296 (Bir Nzaran): 8 real
    # attacker units in a single column -- only the first 3 (strongest)
    # make it into the diagram, the other 5 go to reserve verbatim.
    attacker_units = [
        BattleUnit(ArmyType.BOWMEN, 1.0, source_id=240, quality=Quality.AVERAGE, kingdom_id=1),
        BattleUnit(ArmyType.DRAGON_WING, 1.0, source_id=124, quality=Quality.AVERAGE, kingdom_id=1, is_skeletal=True),
        BattleUnit(ArmyType.BOWMEN, 1.0, source_id=108, quality=Quality.CRACK, kingdom_id=1, is_skeletal=True),
        BattleUnit(ArmyType.BOWMEN, 1.0, source_id=241, quality=Quality.AVERAGE, kingdom_id=1),
        BattleUnit(ArmyType.BOWMEN, 1.0, source_id=110, quality=Quality.AVERAGE, kingdom_id=1),
        BattleUnit(ArmyType.HVY_CAVALRY, 1.0, source_id=109, quality=Quality.AVERAGE, kingdom_id=1),
        BattleUnit(ArmyType.EAGLE_WING, 1.0, source_id=277, quality=Quality.AVERAGE, kingdom_id=1),
        BattleUnit(ArmyType.WARG_RIDERS, 1.0, source_id=209, quality=Quality.AVERAGE, kingdom_id=1),
    ]
    column = BattleColumnResult(
        attacker_strength=0.0, defender_strength=0.0, bres=0, attacker_won=True, cluck_index=9,
        attacker_units=attacker_units,
        defender_units=[BattleUnit(ArmyType.AXEMEN, 1.0, source_id=130, quality=Quality.AVERAGE, kingdom_id=22)],
    )
    result = BattleResult(columns=[column])

    assert render_battle_reserve_sentences(result, random.Random(0)) == [
        "The attackers had the 241st Bowmen, the 110th Bowmen, the 109th Heavy Cavalry, "
        "the 277th Eagles and the 209th Warg Riders in reserve.",
    ]


def test_render_battle_reserve_sentences_matches_a_real_three_column_sample():
    # tests/fixtures/reports/G3/SE3__T11.K1:388-417 (Maplehaven): 15 real
    # defender units across 3 columns -- only the first 3 lines (9 units)
    # make it into the diagram, the other 6 (depths 3 and 4) go to
    # reserve in depth-then-column order, matching the real sentence.
    def col(*ids_and_types):
        return [BattleUnit(t, 1.0, source_id=i, kingdom_id=7) for i, t in ids_and_types]

    AT = ArmyType
    columns = [
        BattleColumnResult(
            attacker_strength=0.0, defender_strength=0.0, bres=0, attacker_won=True, cluck_index=9,
            attacker_units=[], defender_units=units,
        )
        for units in (
            col((186, AT.LEGION), (275, AT.LEGION), (242, AT.LT_CAVALRY), (243, AT.LT_CAVALRY), (248, AT.LT_CAVALRY)),
            col((274, AT.LEGION), (299, AT.LEGION), (311, AT.LEGION), (331, AT.BOWMEN), (215, AT.CAMEL_CORPS)),
            col((259, AT.LEGION), (177, AT.LEGION), (185, AT.LT_CAVALRY), (21, AT.LEGION), (332, AT.BOWMEN)),
        )
    ]
    result = BattleResult(columns=columns)

    assert render_battle_reserve_sentences(result, random.Random(0)) == [
        "The defenders had the 243rd Light Cavalry, the 331st Bowmen, the 21st Legion, "
        "the 248th Light Cavalry, the 215th Camel Corps and the 332nd Bowmen in reserve.",
    ]


def test_render_battle_reserve_sentences_both_sides_get_their_own_sentence():
    # tests/fixtures/reports/G3/SE3__T8.K1:427-428: both sides can have a
    # real reserve sentence in the very same battle, as two independent
    # list entries, not one combined sentence.
    column = BattleColumnResult(
        attacker_strength=0.0, defender_strength=0.0, bres=0, attacker_won=True, cluck_index=9,
        attacker_units=[
            BattleUnit(ArmyType.LEGION, 1.0, source_id=i, kingdom_id=1) for i in (1, 2, 3, 4)
        ],
        defender_units=[
            BattleUnit(ArmyType.BOWMEN, 1.0, source_id=i, kingdom_id=2) for i in (10, 20, 30, 40)
        ],
    )
    result = BattleResult(columns=[column])

    lines = render_battle_reserve_sentences(result, random.Random(0))
    assert lines == [
        "The attackers had the 4th Legion in reserve.",
        "The defenders had the 40th Bowmen in reserve.",
    ]


def test_render_battle_reserve_sentences_returns_empty_list_when_nothing_is_held_back():
    column = _column(bres=3, attacker_source_id=10, defender_source_id=20)
    result = BattleResult(columns=[column])
    assert render_battle_reserve_sentences(result, random.Random(0)) == []


def test_render_battle_reserve_sentences_skips_a_unit_with_no_source_id():
    column = BattleColumnResult(
        attacker_strength=0.0, defender_strength=0.0, bres=0, attacker_won=True, cluck_index=9,
        attacker_units=[
            BattleUnit(ArmyType.LEGION, 1.0, source_id=1, kingdom_id=1),
            BattleUnit(ArmyType.LEGION, 1.0, source_id=2, kingdom_id=1),
            BattleUnit(ArmyType.LEGION, 1.0, source_id=3, kingdom_id=1),
            BattleUnit(ArmyType.LEGION, 1.0, source_id=None, kingdom_id=1),
        ],
        defender_units=[BattleUnit(ArmyType.BOWMEN, 1.0, source_id=20, kingdom_id=2)],
    )
    result = BattleResult(columns=[column])
    assert render_battle_reserve_sentences(result, random.Random(0)) == []


def test_describe_battle_includes_reserve_sentence_right_after_the_diagram():
    attacker_units = [BattleUnit(ArmyType.GARRISON, 10.0, source_id=i) for i in (10, 11, 12, 13)]
    column = BattleColumnResult(
        attacker_strength=10.0, defender_strength=10.0, bres=3, attacker_won=True, cluck_index=20,
        attacker_units=attacker_units,
        defender_units=[BattleUnit(ArmyType.LEGION, 10.0, source_id=20)],
    )
    battle_result = BattleResult(winner="attacker", columns=[column])
    report = BattleReport(battle_result=battle_result, conquered=True, province_coord=HexCoord(3, 5))

    rng = ScriptedRandom([0.1] * 10, choice_indices=[0, 0, 0])
    lines = describe_battle(
        report,
        attacker_name="Attackia",
        defender_name="Defendia",
        province_name="the Dolphin Sea",
        state=GameState(),
        destination_names={},
        rng=rng,
    )
    diagram_end = lines.index("  DEFENDING ARMY")
    assert lines[diagram_end + 1] == "The attackers had the 13th Garrison in reserve."


# -- BLUCK/CLUCK luck narration wiring (Phase 615) ---------------------------


def test_describe_battle_prepends_bluck_and_interleaves_cluck_when_phase_is_supplied():
    column = _column(bres=3, attacker_source_id=10, defender_source_id=20)
    battle_result = BattleResult(winner="attacker", columns=[column], bluck_index=9)
    report = BattleReport(
        battle_result=battle_result,
        conquered=True,
        province_coord=HexCoord(3, 5),
        attacker_kingdom_id=1,
        defender_kingdom_id=2,
        attacker_commander_leader_id=100,
        defender_commander_leader_id=200,
    )
    rng = ScriptedRandom([0.1] * 60, choice_indices=[0, 0, 0, 0, 0])

    lines = describe_battle(
        report,
        attacker_name="Attackia",
        defender_name="Defendia",
        province_name="the Dolphin Sea",
        state=GameState(),
        destination_names={},
        rng=rng,
        phase=0,
    )

    assert lines == [
        # Phase 1035: the real battle-line ASCII diagram is this
        # composer's own first output, before any narrative line -- see
        # `render_battle_line_diagram()`'s own module comment.
        "The armies were drawn up into lines of battle as shown here:",
        "  ATTACKING ARMY, Battle of the Dolphin Sea (0305):",
        "",
        "  10th/A  ",
        " Garrison ",
        "    GC    ",
        "----------",
        "    GC    ",
        "  20th/A  ",
        "  Legion  ",
        "          ",
        "  DEFENDING ARMY",
        # Phase 927: neither side's own `*_commanding_leader_ids`/
        # `*_present_leader_ids` roster is populated on this fixture (only
        # the separate, singular `attacker_commander_leader_id`/`defender_
        # commander_leader_id` BLUCK/CLUCK fields are) -- per real
        # `_BLList` semantics this is a genuine "no leaders present at
        # all" case for both sides, always narrated with the province
        # owner's (defender's) name even for the attacker.
        "no generals were present to lead the forces of Defendia.",
        "no generals were present to lead the forces of Defendia.",
        "no luck of great significance altered the battle.",
        # Phase 712: TACTICS.X2, right after BLUCK -- both tactical
        # abilities default to 0 here, bucket 5 (even).
        "as the battle developed, the tactical wit of Defendia and Attackia seemed evenly matched.",
        "10th Garrison fought 20th Legion and advanced at will.",
        "10th Garrison expected to have the upper hand because they had constructed prepared "
        "defenses, but were suprised to discover that their opponents had done the same.",
        "the forces of Attackia broke through and were victorious.",
    ]


def test_describe_battle_skips_bluck_and_cluck_when_phase_is_not_supplied():
    # The pre-Phase-615 default -- every caller/test that doesn't know
    # its own phase keeps producing exactly the same output as before.
    column = _column(bres=3, attacker_source_id=10, defender_source_id=20)
    battle_result = BattleResult(winner="attacker", columns=[column], bluck_index=9)
    report = BattleReport(
        battle_result=battle_result,
        conquered=True,
        province_coord=HexCoord(3, 5),
        attacker_kingdom_id=1,
        defender_kingdom_id=2,
        attacker_commander_leader_id=100,
        defender_commander_leader_id=200,
    )
    rng = ScriptedRandom([0.1, 0.1, 0.1, 0.1, 0.1], choice_indices=[0, 0, 0])

    lines = describe_battle(
        report,
        attacker_name="Attackia",
        defender_name="Defendia",
        province_name="the Dolphin Sea",
        state=GameState(),
        destination_names={},
        rng=rng,
    )

    assert lines == [
        # Phase 1035: see the previous test's own comment -- the diagram
        # always prints first, regardless of whether `phase` is supplied.
        "The armies were drawn up into lines of battle as shown here:",
        "  ATTACKING ARMY, Battle of the Dolphin Sea (0305):",
        "",
        "  10th/A  ",
        " Garrison ",
        "    GC    ",
        "----------",
        "    GC    ",
        "  20th/A  ",
        "  Legion  ",
        "          ",
        "  DEFENDING ARMY",
        # Phase 927: same "no BATLDR roster populated on this fixture"
        # case as the previous test -- see its own comment.
        "no generals were present to lead the forces of Defendia.",
        "no generals were present to lead the forces of Defendia.",
        "10th Garrison fought 20th Legion and advanced at will.",
        "the forces of Attackia broke through and were victorious.",
    ]


def test_describe_battle_tactics_reflects_a_real_asymmetric_ability_gap():
    # Phase 712: attacker_tactical_ability=7 vs. defender_tactical_
    # ability=2 -> bucket 9 (max(1, min(9, 5 + (7-2)))), the "total
    # attacker advantage" end of the scale -- proving the real field
    # values reach the render, not just the 0-vs-0 default bucket 5
    # every other describe_battle() test here happens to exercise.
    column = _column(bres=3, attacker_source_id=10, defender_source_id=20)
    battle_result = BattleResult(winner="attacker", columns=[column], bluck_index=9)
    report = BattleReport(
        battle_result=battle_result,
        conquered=True,
        province_coord=HexCoord(3, 5),
        attacker_kingdom_id=1,
        defender_kingdom_id=2,
        attacker_commander_leader_id=100,
        defender_commander_leader_id=200,
        attacker_tactical_ability=7,
        defender_tactical_ability=2,
    )
    rng = ScriptedRandom([0.1] * 60, choice_indices=[0, 0, 0, 0, 0])

    lines = describe_battle(
        report,
        attacker_name="Attackia",
        defender_name="Defendia",
        province_name="the Dolphin Sea",
        state=GameState(),
        destination_names={},
        rng=rng,
        phase=0,
    )

    assert "tactical supremacy was guaranteed by Attackia's unmatched tactical mind." in lines


def test_describe_battle_falls_back_to_each_sides_own_king_when_unled():
    # SAY.PAS:1043's own "_attl:= powner[_px,_py]" fallback -- no
    # commander_leader_id on either side, but a real King exists for
    # each Kingdom.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, HexCoord(0, 0)))
    state.add_kingdom(KingdomState(2, "Defendia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(1, 1)))
    state.add_leader(LeaderState(1, 1, "King Aldric", HexCoord(0, 0), is_king=True))
    state.add_leader(LeaderState(2, 2, "King Borin", HexCoord(1, 1), is_king=True))
    column = _column(bres=3, attacker_source_id=10, defender_source_id=20)
    battle_result = BattleResult(winner="attacker", columns=[column], bluck_index=9)
    report = BattleReport(
        battle_result=battle_result, conquered=True, province_coord=HexCoord(3, 5), attacker_kingdom_id=1, defender_kingdom_id=2
    )
    rng = ScriptedRandom([0.1] * 60, choice_indices=[0, 0, 0, 0, 0])

    lines = describe_battle(
        report,
        attacker_name="Attackia",
        defender_name="Defendia",
        province_name="the Dolphin Sea",
        state=state,
        destination_names={},
        rng=rng,
        phase=0,
    )

    assert lines == [
        # Phase 1035: the diagram prints first -- see the earlier tests'
        # own comment.
        "The armies were drawn up into lines of battle as shown here:",
        "  ATTACKING ARMY, Battle of the Dolphin Sea (0305):",
        "",
        "  10th/A  ",
        " Garrison ",
        "    GC    ",
        "----------",
        "    GC    ",
        "  20th/A  ",
        "  Legion  ",
        "          ",
        "  DEFENDING ARMY",
        # Phase 927: the Kings added above are real leaders, but neither
        # is *present at the battle province* (their own `LeaderState.
        # location` is each Kingdom's home, not `HexCoord(3, 5)`) -- so
        # per real `_BLList` "present" semantics (`LeaderState.location`),
        # this is still a genuine "no leaders present" case for both
        # sides, distinct from BLUCK/CLUCK's own separate King-fallback
        # (which doesn't require physical presence).
        "no generals were present to lead the forces of Defendia.",
        "no generals were present to lead the forces of Defendia.",
        "no luck of great significance seemed to affect the overall battle before it commenced.",
        # Phase 712: TACTICS.X2, right after BLUCK.
        "as the battle developed, the tactical wit of Defendia and Attackia seemed evenly matched.",
        "10th Garrison fought 20th Legion and advanced at will.",
        "the contest was a slugfest decided by the courage of the men in hand-to-hand combat.",
        "the forces of Attackia broke through and were victorious.",
    ]


def test_describe_battle_skips_bluck_and_cluck_when_no_leader_id_resolves_for_either_side():
    # No commander_leader_id, and an empty state (no King to fall back
    # to either) -- BLUCK/CLUCK skipped, not guessed.
    column = _column(bres=3, attacker_source_id=10, defender_source_id=20)
    battle_result = BattleResult(winner="attacker", columns=[column], bluck_index=9)
    report = BattleReport(
        battle_result=battle_result, conquered=True, province_coord=HexCoord(3, 5), attacker_kingdom_id=1, defender_kingdom_id=2
    )
    rng = ScriptedRandom([0.1] * 30, choice_indices=[0, 0])

    lines = describe_battle(
        report,
        attacker_name="Attackia",
        defender_name="Defendia",
        province_name="the Dolphin Sea",
        state=GameState(),
        destination_names={},
        rng=rng,
        phase=0,
    )

    assert lines == [
        # Phase 1035: the diagram prints first -- see the earlier tests'
        # own comment.
        "The armies were drawn up into lines of battle as shown here:",
        "  ATTACKING ARMY, Battle of the Dolphin Sea (0305):",
        "",
        "  10th/A  ",
        " Garrison ",
        "    GC    ",
        "----------",
        "    GC    ",
        "  20th/A  ",
        "  Legion  ",
        "          ",
        "  DEFENDING ARMY",
        # Phase 927: no BATLDR roster on this fixture -- see the earlier
        # "phase is not supplied" test's own comment.
        "no generals were present to lead the forces of Defendia.",
        "no generals were present to lead the forces of Defendia.",
        "10th Garrison fought 20th Legion and advanced at will.",
        "the forces of Attackia broke through and were victorious.",
    ]


def test_describe_battle_bluck_appears_without_cluck_for_an_ineligible_column():
    # column_narration_eligible()'s own [0.4, 2.5] strength-ratio gate --
    # BLUCK (whole-battle) still appears, CLUCK (this one column) doesn't.
    column = _column(bres=3, attacker_source_id=10, defender_source_id=20)
    column.attacker_strength = 100.0
    column.defender_strength = 1.0
    battle_result = BattleResult(winner="attacker", columns=[column], bluck_index=9)
    report = BattleReport(
        battle_result=battle_result,
        conquered=True,
        province_coord=HexCoord(3, 5),
        attacker_kingdom_id=1,
        defender_kingdom_id=2,
        attacker_commander_leader_id=100,
        defender_commander_leader_id=200,
    )
    rng = ScriptedRandom([0.1] * 60, choice_indices=[0, 0, 0, 0])

    lines = describe_battle(
        report,
        attacker_name="Attackia",
        defender_name="Defendia",
        province_name="the Dolphin Sea",
        state=GameState(),
        destination_names={},
        rng=rng,
        phase=0,
    )

    assert lines == [
        # Phase 1035: the diagram prints first -- see the earlier tests'
        # own comment.
        "The armies were drawn up into lines of battle as shown here:",
        "  ATTACKING ARMY, Battle of the Dolphin Sea (0305):",
        "",
        "  10th/A  ",
        " Garrison ",
        "    GC    ",
        "----------",
        "    GC    ",
        "  20th/A  ",
        "  Legion  ",
        "          ",
        "  DEFENDING ARMY",
        # Phase 927: no BATLDR roster on this fixture -- see the "phase
        # is not supplied" test's own comment above.
        "no generals were present to lead the forces of Defendia.",
        "no generals were present to lead the forces of Defendia.",
        "no luck of great significance altered the battle.",
        # Phase 712: TACTICS.X2, right after BLUCK.
        "as the battle developed, the tactical wit of Defendia and Attackia seemed evenly matched.",
        "10th Garrison fought 20th Legion and advanced at will.",
        "the forces of Attackia broke through and were victorious.",
    ]


def test_bluck_cluck_leader_id_prefers_the_commander_over_the_king():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, HexCoord(0, 0)))
    state.add_leader(LeaderState(1, 1, "King Aldric", HexCoord(0, 0), is_king=True))

    assert _bluck_cluck_leader_id(42, 1, state) == 42


def test_bluck_cluck_leader_id_falls_back_to_the_king_when_unled():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, HexCoord(0, 0)))
    state.add_leader(LeaderState(1, 1, "King Aldric", HexCoord(0, 0), is_king=True))

    assert _bluck_cluck_leader_id(None, 1, state) == 1


def test_bluck_cluck_leader_id_returns_none_when_nothing_resolves():
    assert _bluck_cluck_leader_id(None, None, GameState()) is None
    assert _bluck_cluck_leader_id(None, 1, GameState()) is None


# -- build_battle_army_names (Phase 236) --------------------------------------


def test_build_battle_army_names_uses_the_armys_own_kingdom_when_still_present():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Elvenholt", Race.ELVEN, Alignment.GOOD, HexCoord(0, 0)))
    # _column()'s own attacker unit is always ArmyType.GARRISON -- that's
    # the type this function names by (the column's own BattleUnit), not
    # whatever type the backing ArmyState happens to carry.
    state.add_army(ArmyState(10, 1, ArmyType.GARRISON, Quality.AVERAGE, HexCoord(0, 0)))
    column = _column(bres=3, attacker_source_id=10, defender_source_id=20)
    report = BattleReport(battle_result=BattleResult(winner="attacker", columns=[column]), conquered=False)

    names = build_battle_army_names(state, report)

    assert names[10] == make_army_name(10, ArmyType.GARRISON, Race.ELVEN)
    assert names[10] == "10th Elf Garrison"


def test_build_battle_army_names_falls_back_to_battle_report_kingdom_when_army_already_destroyed():
    state = GameState()
    state.add_kingdom(KingdomState(2, "Orclund", Race.ORCISH, Alignment.EVIL, HexCoord(0, 0)))
    # id 20 was destroyed and removed from state.armies before this runs --
    # same "GameState.remove_army() already ran" ordering describe_battle()
    # itself operates under.
    column = _column(bres=3, attacker_source_id=10, defender_source_id=20)
    report = BattleReport(
        battle_result=BattleResult(winner="attacker", columns=[column]),
        conquered=False,
        destroyed_army_ids=[20],
        defender_kingdom_id=2,
    )

    names = build_battle_army_names(state, report)

    assert names[20] == make_army_name(20, ArmyType.LEGION, Race.ORCISH)
    assert names[20] == "20th Orc Legion"


def test_build_battle_army_names_uses_monstrous_army_race_over_kingdom_race():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Humania", Race.HUMAN, Alignment.GOOD, HexCoord(0, 0)))
    state.add_army(ArmyState(10, 1, ArmyType.DRAGON_WING, Quality.AVERAGE, HexCoord(0, 0)))
    column = BattleColumnResult(
        attacker_strength=10.0,
        defender_strength=10.0,
        bres=3,
        attacker_won=True,
        cluck_index=20,
        attacker_units=[BattleUnit(ArmyType.DRAGON_WING, 10.0, source_id=10)],
        defender_units=[BattleUnit(ArmyType.LEGION, 10.0, source_id=20)],
    )
    report = BattleReport(battle_result=BattleResult(winner="attacker", columns=[column]), conquered=False)

    names = build_battle_army_names(state, report)

    # MONSTROUS_ARMY_RACE[DRAGON_WING] = Race.DRAGONS overrides Humania's
    # own Race.HUMAN -- Dragon armies stay Dragon-race regardless of the
    # Human kingdom that owns them.
    assert names[10] == make_army_name(10, ArmyType.DRAGON_WING, Race.DRAGONS)


def test_build_battle_army_names_defaults_to_human_with_no_kingdom_data_at_all():
    state = GameState()
    column = _column(bres=3, attacker_source_id=10, defender_source_id=20)
    report = BattleReport(battle_result=BattleResult(winner="attacker", columns=[column]), conquered=False)

    names = build_battle_army_names(state, report)

    assert names[10] == "10th Garrison"
    assert names[20] == "20th Legion"


# -- render_uncontested_conquest (Phase 63) -----------------------------------


def test_render_uncontested_conquest_first_variant():
    rng = ScriptedRandom([0.1, 0.1], choice_indices=[0])
    result = render_uncontested_conquest("Attackia", "the Dolphin Sea", rng)
    assert result == "Attackia's forces conquered the Dolphin Sea without any major battles."


def test_render_uncontested_conquest_last_variant():
    rng = ScriptedRandom([0.9, 0.9, 0.9], choice_indices=[3])
    result = render_uncontested_conquest("Attackia", "the Dolphin Sea", rng)
    assert result == (
        "Attackia's forces experienced little opposition in the Dolphin Sea "
        "and Attackia there established our reign."
    )


def test_render_uncontested_conquest_second_variant_land():
    # Phase 74: variant 1 carries both a "/S" marker ("armies/Snaval_forces",
    # deterministic, no rng consumed) and a "/R" marker ("control/Rpossession",
    # random) -- land (is_sea defaults to False) picks "armies"; 0.1 -> /R
    # picks "control".
    rng = ScriptedRandom([0.1], choice_indices=[1])
    result = render_uncontested_conquest("Attackia", "the Dolphin Sea", rng)
    assert result == "Attackia's armies took control of the Dolphin Sea practically uncontested."


def test_render_uncontested_conquest_second_variant_sea():
    rng = ScriptedRandom([0.1], choice_indices=[1])
    result = render_uncontested_conquest("Attackia", "the Dolphin Sea", rng, is_sea=True)
    assert result == "Attackia's naval forces took control of the Dolphin Sea practically uncontested."


def test_render_uncontested_conquest_third_variant_land():
    # Variant 2 carries two markers: "/R" (conquered/overrun, always
    # resolved randomly) and "/S" ("host/Sfleet", deterministic by
    # is_sea). 0.1 -> /R picks the left choice ("conquered"); the
    # optional "{ and occupied}" block excluded (also < 0.5).
    rng = ScriptedRandom([0.1, 0.1], choice_indices=[2])
    result = render_uncontested_conquest("Attackia", "the Dolphin Sea", rng)
    assert result == "the Dolphin Sea was conquered by Attackia's host."


def test_render_uncontested_conquest_third_variant_sea():
    rng = ScriptedRandom([0.1, 0.1], choice_indices=[2])
    result = render_uncontested_conquest("Attackia", "the Dolphin Sea", rng, is_sea=True)
    assert result == "the Dolphin Sea was conquered by Attackia's fleet."


# -- render_spy_report_opening (Phase 63) -------------------------------------


def test_render_spy_report_opening_first_variant_elides_king_exclusion_markers():
    # Variant 0 has one optional block ("{secretly }") and no /R choice;
    # the real template's "^B"..."^E" span (a King-exclusion marker this
    # project doesn't implement) is elided to empty string.
    rng = ScriptedRandom([0.1], choice_indices=[0])
    result = render_spy_report_opening("Guerin", "Falkenheim", rng)
    assert result == "Guerin spied on Falkenheim.Here is Guerin's report:  "


def test_render_spy_report_opening_second_variant():
    rng = ScriptedRandom([0.1], choice_indices=[1])
    result = render_spy_report_opening("Guerin", "Falkenheim", rng)
    assert result == "Guerin conducted espionage in Falkenheim and compiled this report."


def test_render_spy_report_opening_last_variant_resolves_possessive_and_optional_blocks():
    rng = ScriptedRandom([0.9, 0.9, 0.9, 0.9, 0.9, 0.9], choice_indices=[4])
    result = render_spy_report_opening("Guerin", "Falkenheim", rng)
    assert result == (
        "Guerin utilized Guerin's fine spying skills to secretly keep track "
        "of happenings in Falkenheim and reported the following information."
    )


# -- Phase 96: render_magic_feature_discovery (MAGFEAT.X2) --


def test_render_magic_feature_discovery_none():
    result = render_magic_feature_discovery(MagicFeature.NONE, "Everhold", "Arthur")
    assert result == "Arthur saw nothing special while scouting out the Everhold."


def test_render_magic_feature_discovery_found_something():
    result = render_magic_feature_discovery(MagicFeature.POOL, "Everhold", "Arthur")
    assert result == (
        "While scouting the Everhold, Arthur saw a Pool/FStream which "
        "seemed to be of a magical nature."
    )


def test_render_magic_feature_discovery_any_non_none_non_itself_ordinal_renders_the_same_sentence_shape():
    # 19 of MAGFEAT.X2's 20-line choice pool are textually identical --
    # the specific MagicFeature only changes the substituted $\ value.
    result = render_magic_feature_discovery(MagicFeature.CRYSTAL_BALL, "Everhold", "Arthur")
    assert result == (
        "While scouting the Everhold, Arthur saw a Crystal_Ball/FMagic_Mirror "
        "which seemed to be of a magical nature."
    )


def test_render_magic_feature_discovery_itself():
    result = render_magic_feature_discovery(MagicFeature.ITSELF, "Everhold", "Arthur")
    assert result == (
        "While scouting the Everhold, Arthur noticed that the Everhold "
        "itself seems to be imbued with magical qualities."
    )


# -- Phase 104: render_march (MARCH.X) --


def test_render_march_first_variant_land():
    rng = ScriptedRandom([0.1, 0.1], choice_indices=[0])
    result = render_march("Arthur", "Numenor", "0304", rng)
    assert result == "Arthur marched on Numenor 0304 with Arthur's command."


def test_render_march_second_variant():
    rng = ScriptedRandom([0.1, 0.1], choice_indices=[1])
    result = render_march("Arthur", "Numenor", "0304", rng)
    assert result == "Arthur marched Arthur's forces into Numenor 0304."


def test_render_march_third_variant_land():
    rng = ScriptedRandom([0.1, 0.1], choice_indices=[2])
    result = render_march("Arthur", "Numenor", "0304", rng)
    assert result == "Arthur moved into Numenor 0304 with Arthur's army."


def test_render_march_resolves_sea_marker():
    rng = ScriptedRandom([0.1, 0.1], choice_indices=[0])
    result = render_march("Arthur", "Numenor", "0304", rng, is_sea=True)
    assert result == "Arthur sailed into Numenor 0304 with Arthur's command."


def test_render_march_resolves_optional_block_and_choice_marker():
    rng = ScriptedRandom([0.9, 0.9], choice_indices=[2])
    result = render_march("Arthur", "Numenor", "0304", rng)
    assert result == "Arthur moved into Numenor 0304 with Arthur's high-spirited army."


# -- Phase 769: render_travel (TRAV.X, an armyless personal Move) --


def test_render_travel_first_variant():
    rng = ScriptedRandom([], choice_indices=[0])
    result = render_travel("Arthur", "Numenor", rng)
    assert result == "Arthur travelled to Numenor."


def test_render_travel_second_variant_resolves_sea_marker():
    rng = ScriptedRandom([], choice_indices=[1])
    result = render_travel("Arthur", "Numenor", rng, is_sea=True)
    assert result == "Arthur sailed into Numenor."


def test_render_travel_second_variant_land():
    rng = ScriptedRandom([], choice_indices=[1])
    result = render_travel("Arthur", "Numenor", rng)
    assert result == "Arthur rode into Numenor."


def test_render_travel_third_variant():
    rng = ScriptedRandom([], choice_indices=[2])
    result = render_travel("Arthur", "Numenor", rng)
    assert result == "Arthur moved into Numenor."


def test_render_travel_fourth_variant_resolves_sea_marker():
    rng = ScriptedRandom([], choice_indices=[3])
    result = render_travel("Arthur", "Numenor", rng, is_sea=True)
    assert result == "Arthur cruised over to Numenor."


# -- Phase 419: render_recruit_unit (RECRUIT.X) + describe_recruit --


def test_render_recruit_unit_first_variant_left_choices():
    rng = ScriptedRandom([0.1, 0.1], choice_indices=[0])
    result = render_recruit_unit("Arthur", "Numenor", "Bowmen", "Cedric", rng)
    assert result == "Arthur recruited Bowmen from among the people of Numenor, to serve under Cedric."


def test_render_recruit_unit_first_variant_right_choices():
    rng = ScriptedRandom([0.6, 0.6], choice_indices=[0])
    result = render_recruit_unit("Arthur", "Numenor", "Bowmen", "Cedric", rng)
    assert result == "Arthur levied Bowmen from among the population of Numenor, to serve under Cedric."


def test_render_recruit_unit_second_variant():
    rng = ScriptedRandom([0.1], choice_indices=[1])
    result = render_recruit_unit("Arthur", "Numenor", "Bowmen", "Cedric", rng)
    assert result == "Arthur levied Bowmen in Numenor to serve Cedric."


def test_render_recruit_unit_third_variant():
    rng = ScriptedRandom([0.1, 0.1, 0.1], choice_indices=[2])
    result = render_recruit_unit("Arthur", "Numenor", "Bowmen", "Cedric", rng)
    assert result == (
        "Arthur announced  plea for volunteers in Numenor and was able to form Bowmen to fight for Cedric."
    )


def test_render_recruit_unit_fourth_variant():
    rng = ScriptedRandom([0.1, 0.1], choice_indices=[3])
    result = render_recruit_unit("Arthur", "Numenor", "Bowmen", "Cedric", rng)
    assert result == "Arthur enlisted enough men in Numenor to create Bowmen for the army of Cedric."


def _recruit_state(*, province_race: Race = Race.HUMAN) -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.GOOD, HexCoord(0, 0)))
    state.add_province(
        ProvinceState(HexCoord(3, 9), Terrain.PLAINS, province_race, owner_kingdom_id=1, name="Numenor")
    )
    state.add_leader(LeaderState(1, 1, "Arthur", HexCoord(3, 9)))
    return state


# -- HIREMERC.X (Phase 595) --


def test_render_recruit_hired_mercenary_first_variant():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])
    result = render_recruit_hired_mercenary("Aldric", "Mongu", "144th Legion", rng)
    assert result == "Aldric hired 144th Legion, a mercenary army which had made its way to Mongu."


def test_render_recruit_hired_mercenary_first_variant_resolves_sea_marker():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])
    result = render_recruit_hired_mercenary("Aldric", "Mongu", "144th Legion", rng, is_sea=True)
    assert result == "Aldric hired 144th Legion, a mercenary squadron which had made its way to Mongu."


def test_render_recruit_hired_mercenary_second_variant_includes_optional_clause():
    rng = ScriptedRandom([0.99] * 10, choice_indices=[1])
    result = render_recruit_hired_mercenary("Aldric", "Mongu", "144th Legion", rng)
    assert result == "Aldric recruited a hard fighting force of mercenary soldiers in Mongu who are known as 144th Legion."


def test_render_recruit_hired_mercenary_third_variant():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[2])
    result = render_recruit_hired_mercenary("Aldric", "Mongu", "144th Legion", rng)
    assert result == "Aldric negotiated with 144th Legion for their allegiance, and succeeded in contracting for their services."


def test_describe_recruit_commanded_unit():
    state = _recruit_state()
    state.add_leader(LeaderState(2, 1, "Cedric", HexCoord(3, 9)))
    state.add_army(ArmyState(100, 1, ArmyType.BOWMEN, Quality.AVERAGE, HexCoord(3, 9), commanded_by=2))
    result = RecruitExecutionResult(
        request=None, recruited=[RecruitedUnit(army_id=100, army_type=ArmyType.BOWMEN, gold_paid=2)]
    )

    rng = ScriptedRandom([0.1, 0.1], choice_indices=[0])
    lines = describe_recruit(result, state, recruiter_name="Arthur", province=state.provinces[HexCoord(3, 9)], rng=rng)

    assert lines == ["Arthur recruited Bowmen from among the people of Numenor, to serve under Cedric."]


def test_describe_recruit_unled_humanoid_province_uses_garrison_commander():
    state = _recruit_state(province_race=Race.HUMAN)
    state.add_army(ArmyState(100, 1, ArmyType.BOWMEN, Quality.AVERAGE, HexCoord(3, 9), commanded_by=None))
    result = RecruitExecutionResult(
        request=None, recruited=[RecruitedUnit(army_id=100, army_type=ArmyType.BOWMEN, gold_paid=2)]
    )

    rng = ScriptedRandom([0.1, 0.1], choice_indices=[0])
    lines = describe_recruit(result, state, recruiter_name="Arthur", province=state.provinces[HexCoord(3, 9)], rng=rng)

    assert lines == [
        "Arthur recruited Bowmen from among the people of Numenor, to serve under "
        "the provincial garrison commander."
    ]


def test_describe_recruit_unled_monstrous_province_uses_race_chieftain():
    state = _recruit_state(province_race=Race.DRAGONS)
    state.add_army(ArmyState(100, 1, ArmyType.DRAGON_WING, Quality.AVERAGE, HexCoord(3, 9), commanded_by=None))
    result = RecruitExecutionResult(
        request=None, recruited=[RecruitedUnit(army_id=100, army_type=ArmyType.DRAGON_WING, gold_paid=2)]
    )

    rng = ScriptedRandom([0.1, 0.1], choice_indices=[0])
    lines = describe_recruit(result, state, recruiter_name="Arthur", province=state.provinces[HexCoord(3, 9)], rng=rng)

    assert lines == [
        "Arthur recruited Dragons from among the people of Numenor, to serve under "
        "the provincial Dragon chieftain."
    ]


def test_describe_recruit_hired_unit_uses_hiremerc_not_recruit():
    state = _recruit_state()
    state.add_army(ArmyState(100, 1, ArmyType.BOWMEN, Quality.AVERAGE, HexCoord(3, 9), commanded_by=None))
    result = RecruitExecutionResult(
        request=None, recruited=[RecruitedUnit(army_id=100, army_type=ArmyType.BOWMEN, gold_paid=5, hired=True)]
    )

    rng = ScriptedRandom([0.1] * 5, choice_indices=[0])
    lines = describe_recruit(result, state, recruiter_name="Arthur", province=state.provinces[HexCoord(3, 9)], rng=rng)

    assert lines == ["Arthur hired Bowmen, a mercenary army which had made its way to Numenor."]


# -- Phase 645: RUMORS.PAS _AAPay (ally-territory recruiting fee) --


def test_render_recruit_ally_fee():
    rng = ScriptedRandom([0.1], choice_indices=[0])
    result = render_recruit_ally_fee("Arthur", 1, "Bors", rng)
    assert result == "Arthur paid 1 gold to Bors for the privilege of recruiting these troops."


def _ally_territory_recruit_state() -> GameState:
    # Kingdom 1 (recruiter) has no King of its own here -- irrelevant to
    # the ``_AAPay`` line, which names the *province owner*'s King.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.GOOD, HexCoord(0, 0)))
    state.add_kingdom(KingdomState(2, "Allia", Race.HUMAN, Alignment.GOOD, HexCoord(5, 5)))
    state.add_leader(LeaderState(2, 2, "Bors", HexCoord(5, 5), is_king=True))
    state.add_province(
        ProvinceState(HexCoord(3, 9), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2, name="Numenor")
    )
    state.add_leader(LeaderState(1, 1, "Arthur", HexCoord(3, 9)))
    return state


def test_describe_recruit_appends_aapay_line_after_a_freshly_levied_unit():
    state = _ally_territory_recruit_state()
    state.add_army(ArmyState(100, 1, ArmyType.BOWMEN, Quality.AVERAGE, HexCoord(3, 9), commanded_by=None))
    result = RecruitExecutionResult(
        request=None,
        recruited=[RecruitedUnit(army_id=100, army_type=ArmyType.BOWMEN, gold_paid=3, ally_fee_paid=1)],
    )

    rng = ScriptedRandom([0.1, 0.1, 0.1], choice_indices=[0])
    lines = describe_recruit(result, state, recruiter_name="Arthur", province=state.provinces[HexCoord(3, 9)], rng=rng)

    assert len(lines) == 2
    assert lines[0] == (
        "Arthur recruited Bowmen from among the people of Numenor, to serve under "
        "the provincial garrison commander."
    )
    assert lines[1] == "Arthur paid 1 gold to Bors for the privilege of recruiting these troops."


def test_describe_recruit_appends_aapay_line_after_a_hired_unit():
    state = _ally_territory_recruit_state()
    state.add_army(ArmyState(100, 1, ArmyType.BOWMEN, Quality.AVERAGE, HexCoord(3, 9), commanded_by=None))
    result = RecruitExecutionResult(
        request=None,
        recruited=[RecruitedUnit(army_id=100, army_type=ArmyType.BOWMEN, gold_paid=6, hired=True, ally_fee_paid=1)],
    )

    rng = ScriptedRandom([0.1] * 6, choice_indices=[0])
    lines = describe_recruit(result, state, recruiter_name="Arthur", province=state.provinces[HexCoord(3, 9)], rng=rng)

    assert len(lines) == 2
    assert lines[0] == "Arthur hired Bowmen, a mercenary army which had made its way to Numenor."
    assert lines[1] == "Arthur paid 1 gold to Bors for the privilege of recruiting these troops."


def test_describe_recruit_own_territory_has_no_aapay_line():
    # Non-regression: `ally_fee_paid` defaults to 0 for a unit recruited
    # in the kingdom's own territory, so no extra line appears.
    state = _recruit_state()
    state.add_army(ArmyState(100, 1, ArmyType.BOWMEN, Quality.AVERAGE, HexCoord(3, 9), commanded_by=None))
    result = RecruitExecutionResult(
        request=None, recruited=[RecruitedUnit(army_id=100, army_type=ArmyType.BOWMEN, gold_paid=2)]
    )

    rng = ScriptedRandom([0.1, 0.1], choice_indices=[0])
    lines = describe_recruit(result, state, recruiter_name="Arthur", province=state.provinces[HexCoord(3, 9)], rng=rng)

    assert len(lines) == 1


def test_describe_recruit_multiple_units_render_one_line_each():
    state = _recruit_state()
    state.add_army(ArmyState(100, 1, ArmyType.BOWMEN, Quality.AVERAGE, HexCoord(3, 9), commanded_by=None))
    state.add_army(ArmyState(101, 1, ArmyType.AXEMEN, Quality.AVERAGE, HexCoord(3, 9), commanded_by=None))
    result = RecruitExecutionResult(
        request=None,
        recruited=[
            RecruitedUnit(army_id=100, army_type=ArmyType.BOWMEN, gold_paid=2),
            RecruitedUnit(army_id=101, army_type=ArmyType.AXEMEN, gold_paid=2),
        ],
    )

    rng = ScriptedRandom([0.1] * 4, choice_indices=[0, 0])
    lines = describe_recruit(result, state, recruiter_name="Arthur", province=state.provinces[HexCoord(3, 9)], rng=rng)

    assert len(lines) == 2
    assert "Bowmen" in lines[0]
    assert "Axemen" in lines[1]


# -- Phase 420: render_leave_unit (LEAVE.X) + describe_leave --


def test_render_leave_unit_first_variant():
    rng = ScriptedRandom([], choice_indices=[0])
    result = render_leave_unit("Arthur", "Numenor", "Bowmen", "Cedric", rng)
    assert result == "Arthur left Bowmen with Cedric in Numenor."


def test_render_leave_unit_second_variant():
    rng = ScriptedRandom([], choice_indices=[1])
    result = render_leave_unit("Arthur", "Numenor", "Bowmen", "Cedric", rng)
    assert result == "Arthur dropped off Bowmen in Numenor for Cedric."


def test_render_leave_unit_third_variant_excludes_optional_block():
    rng = ScriptedRandom([0.1, 0.1], choice_indices=[2])
    result = render_leave_unit("Arthur", "Numenor", "Bowmen", "Cedric", rng)
    assert result == "Arthur ordered Bowmen to remain in Numenor with Cedric."


def test_render_leave_unit_third_variant_includes_optional_block_land():
    rng = ScriptedRandom([0.6, 0.6], choice_indices=[2])
    result = render_leave_unit("Arthur", "Numenor", "Bowmen", "Cedric", rng, is_sea=False)
    assert result == "Arthur directed Bowmen to remain encamped in Numenor with Cedric."


def test_render_leave_unit_third_variant_includes_optional_block_sea():
    rng = ScriptedRandom([0.6, 0.6], choice_indices=[2])
    result = render_leave_unit("Arthur", "Numenor", "Bowmen", "Cedric", rng, is_sea=True)
    assert result == "Arthur directed Bowmen to remain anchored in Numenor with Cedric."


def test_render_leave_unit_fourth_variant():
    rng = ScriptedRandom([0.1, 0.1], choice_indices=[3])
    result = render_leave_unit("Arthur", "Numenor", "Bowmen", "Cedric", rng)
    assert result == "Arthur instructed Bowmen to stay behind in Numenor with Cedric."


def test_render_leave_unit_fifth_variant():
    rng = ScriptedRandom([0.1], choice_indices=[4])
    result = render_leave_unit("Arthur", "Numenor", "Bowmen", "Cedric", rng)
    assert result == "Arthur transferred Bowmen to Cedric in Numenor."


def _leave_state(*, province_race: Race = Race.HUMAN, terrain: Terrain = Terrain.PLAINS) -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.GOOD, HexCoord(0, 0)))
    state.add_province(ProvinceState(HexCoord(3, 9), terrain, province_race, owner_kingdom_id=1, name="Numenor"))
    state.add_leader(LeaderState(1, 1, "Arthur", HexCoord(3, 9)))
    return state


def test_describe_leave_commanded_unit():
    state = _leave_state()
    state.add_leader(LeaderState(2, 1, "Cedric", HexCoord(3, 9)))
    state.add_army(ArmyState(100, 1, ArmyType.BOWMEN, Quality.AVERAGE, HexCoord(3, 9), commanded_by=2))
    result = ArmyListExecutionResult(request=None, succeeded=[100])

    rng = ScriptedRandom([], choice_indices=[0])
    lines = describe_leave(result, state, leader_name="Arthur", province=state.provinces[HexCoord(3, 9)], rng=rng)

    assert lines == ["Arthur left Bowmen with Cedric in Numenor."]


def test_describe_leave_unled_humanoid_uses_garrison_commander():
    state = _leave_state(province_race=Race.HUMAN)
    state.add_army(ArmyState(100, None, ArmyType.BOWMEN, Quality.AVERAGE, HexCoord(3, 9), commanded_by=None))
    result = ArmyListExecutionResult(request=None, succeeded=[100])

    rng = ScriptedRandom([], choice_indices=[0])
    lines = describe_leave(result, state, leader_name="Arthur", province=state.provinces[HexCoord(3, 9)], rng=rng)

    assert lines == ["Arthur left Bowmen with the provincial garrison commander in Numenor."]


# -- Phase 647: SAY.PAS _ADig -- Skeletal Army "digs its own grave" --


def test_render_skeletal_army_dug_grave():
    rng = ScriptedRandom([], choice_indices=[0])
    result = render_skeletal_army_dug_grave("Bowmen", rng)
    assert result == (
        "Bowmen dug graves for themselves, unwilling to serve anyone but their "
        "master, unless given to an Undead leader like themselves."
    )


def test_describe_leave_appends_adig_line_for_a_lost_skeletal_army():
    state = _leave_state()
    result = ArmyListExecutionResult(request=None, succeeded=[], skeletal_army_lost=[(100, ArmyType.BOWMEN)])

    rng = ScriptedRandom([], choice_indices=[0])
    lines = describe_leave(result, state, leader_name="Arthur", province=state.provinces[HexCoord(3, 9)], rng=rng)

    assert lines == [
        "Bowmen dug graves for themselves, unwilling to serve anyone but their "
        "master, unless given to an Undead leader like themselves."
    ]


def test_describe_leave_adig_line_follows_ordinary_leave_sentences():
    state = _leave_state()
    state.add_leader(LeaderState(2, 1, "Cedric", HexCoord(3, 9)))
    state.add_army(ArmyState(100, 1, ArmyType.BOWMEN, Quality.AVERAGE, HexCoord(3, 9), commanded_by=2))
    result = ArmyListExecutionResult(request=None, succeeded=[100], skeletal_army_lost=[(200, ArmyType.AXEMEN)])

    rng = ScriptedRandom([], choice_indices=[0, 0])
    lines = describe_leave(result, state, leader_name="Arthur", province=state.provinces[HexCoord(3, 9)], rng=rng)

    assert lines == [
        "Arthur left Bowmen with Cedric in Numenor.",
        "Axemen dug graves for themselves, unwilling to serve anyone but their "
        "master, unless given to an Undead leader like themselves.",
    ]


def test_describe_leave_skips_army_not_found():
    state = _leave_state()
    result = ArmyListExecutionResult(request=None, succeeded=[999])

    lines = describe_leave(result, state, leader_name="Arthur", province=state.provinces[HexCoord(3, 9)], rng=ScriptedRandom([]))

    assert lines == []


# -- Phase 420: render_pickup_unit (PICKUP.X) + describe_pick_up --


def test_render_pickup_unit_first_variant():
    rng = ScriptedRandom([], choice_indices=[0])
    result = render_pickup_unit("Arthur", "Numenor", "Bowmen", rng)
    assert result == "Arthur picked up Bowmen in Numenor."


def test_render_pickup_unit_second_variant_land():
    rng = ScriptedRandom([0.1], choice_indices=[1])
    result = render_pickup_unit("Arthur", "Numenor", "Bowmen", rng, is_sea=False)
    assert result == "in Numenor, Arthur ordered Bowmen to join forces with Arthur's army."


def test_render_pickup_unit_second_variant_sea():
    rng = ScriptedRandom([0.1], choice_indices=[1])
    result = render_pickup_unit("Arthur", "Numenor", "Fleet", rng, is_sea=True)
    assert result == "in Numenor, Arthur ordered Fleet to join forces with Arthur's navy."


def test_render_pickup_unit_third_variant():
    rng = ScriptedRandom([0.1], choice_indices=[2])
    result = render_pickup_unit("Arthur", "Numenor", "Bowmen", rng)
    assert result == "Arthur strengthened Arthur's forces in Numenor with Bowmen."


def test_render_pickup_unit_fourth_variant_land():
    rng = ScriptedRandom([], choice_indices=[3])
    result = render_pickup_unit("Arthur", "Numenor", "Bowmen", rng, is_sea=False)
    assert result == "Arthur added Bowmen to Arthur's host in Numenor."


def test_render_pickup_unit_fourth_variant_sea():
    rng = ScriptedRandom([], choice_indices=[3])
    result = render_pickup_unit("Arthur", "Numenor", "Fleet", rng, is_sea=True)
    assert result == "Arthur added Fleet to Arthur's fleet in Numenor."


def test_describe_pick_up_resolves_sea_marker_from_army_type():
    state = _leave_state()
    state.add_army(ArmyState(100, None, ArmyType.FLEET, Quality.AVERAGE, HexCoord(3, 9), commanded_by=1))
    result = ArmyListExecutionResult(request=None, succeeded=[100])

    rng = ScriptedRandom([], choice_indices=[3])
    lines = describe_pick_up(result, state, leader_name="Arthur", province=state.provinces[HexCoord(3, 9)], rng=rng)

    assert lines == ["Arthur added Fleet to Arthur's fleet in Numenor."]


def test_describe_pick_up_skips_army_not_found():
    state = _leave_state()
    result = ArmyListExecutionResult(request=None, succeeded=[999])

    lines = describe_pick_up(
        result, state, leader_name="Arthur", province=state.provinces[HexCoord(3, 9)], rng=ScriptedRandom([])
    )

    assert lines == []


# -- Phase 420: render_disband_unit (_ADisb) + describe_disband --


def test_render_disband_unit():
    result = render_disband_unit("Arthur", "Bowmen", ScriptedRandom([]))
    assert result == "Arthur disbanded Bowmen."


def test_describe_disband_renders_one_line_per_succeeded_army():
    state = _leave_state()
    state.add_army(ArmyState(100, None, ArmyType.BOWMEN, Quality.AVERAGE, HexCoord(3, 9), commanded_by=None))
    result = ArmyListExecutionResult(request=None, succeeded=[100])

    lines = describe_disband(result, state, leader_name="Arthur", rng=ScriptedRandom([]))

    assert lines == ["Arthur disbanded Bowmen."]


def test_describe_disband_skips_army_not_found():
    state = _leave_state()
    result = ArmyListExecutionResult(request=None, succeeded=[999])

    lines = describe_disband(result, state, leader_name="Arthur", rng=ScriptedRandom([]))

    assert lines == []


# -- Phase 421: render_defend (_LDefend) + describe_defend --


def test_render_defend_land():
    result = render_defend("Arthur", "Numenor", ScriptedRandom([]), is_sea=False)
    assert result == "Arthur prepared Arthur's armies to defend Numenor and the surrounding provinces."


def test_render_defend_sea():
    result = render_defend("Arthur", "Numenor", ScriptedRandom([]), is_sea=True)
    assert result == "Arthur prepared Arthur's forces to defend Numenor and the surrounding provinces."


def test_describe_defend_uses_leader_own_province():
    state = _leave_state(terrain=Terrain.PLAINS)
    result = describe_defend(state, leader_name="Arthur", province=state.provinces[HexCoord(3, 9)], rng=ScriptedRandom([]))
    assert result == "Arthur prepared Arthur's armies to defend Numenor and the surrounding provinces."


def test_describe_defend_resolves_sea_from_province_terrain():
    state = _leave_state(terrain=Terrain.SEA)
    result = describe_defend(state, leader_name="Arthur", province=state.provinces[HexCoord(3, 9)], rng=ScriptedRandom([]))
    assert result == "Arthur prepared Arthur's forces to defend Numenor and the surrounding provinces."


# -- Phase 422: render_defend_reinforcement (_LHearInv) + describe_defend_reinforcement --


def test_render_defend_reinforcement_left_variants():
    result = render_defend_reinforcement("Arthur", "Numenor", "Gondor", ScriptedRandom([0.0, 0.0]))
    assert result == "Arthur, responsible for the defense of Numenor, learned of an enemy attack on Gondor."


def test_render_defend_reinforcement_right_variants():
    result = render_defend_reinforcement("Arthur", "Numenor", "Gondor", ScriptedRandom([0.9, 0.9]))
    assert result == "Arthur, responsible for the defense of Numenor, got wind of an enemy move on Gondor."


def test_describe_defend_reinforcement_resolves_origin_and_target_names():
    state = _leave_state()
    state.add_province(ProvinceState(HexCoord(4, 9), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, name="Gondor"))
    result = DefendReinforcement(origin=HexCoord(3, 9), target=HexCoord(4, 9))

    lines = describe_defend_reinforcement(result, state, defender_name="Arthur", rng=ScriptedRandom([0.0, 0.0]))

    # Phase 769: _LHearInv + _LCMarch, both real sentences for this one
    # atomic reinforcement event -- see describe_defend_reinforcement()'s
    # own Phase 769 addendum for the marker-mapping reasoning.
    assert lines == [
        "Arthur, responsible for the defense of Numenor, learned of an enemy attack on Gondor.",
        "Arthur marched into Gondor from Numenor to defend Gondor against its would-be conquerors.",
    ]


# -- Phase 421: describe_move (MARCH.X, wiring render_march() for the first time) --


def _move_result(
    *, moved: bool = True, new_location: HexCoord | None = HexCoord(3, 9), moved_without_armies: bool = False
) -> MoveExecutionResult:
    return MoveExecutionResult(
        moved=moved,
        battle_report=None,
        exploration=None,
        movement_points_spent=1,
        new_location=new_location,
        moved_without_armies=moved_without_armies,
    )


def test_describe_move_renders_march_land():
    state = _leave_state(terrain=Terrain.PLAINS)
    rng = ScriptedRandom([0.1, 0.1], choice_indices=[0])
    line = describe_move(_move_result(), state, character_name="Arthur", board_width=20, rng=rng)
    assert line == "Arthur marched on Numenor 183 with Arthur's command."


def test_describe_move_resolves_sea_marker_from_terrain():
    state = _leave_state(terrain=Terrain.SEA)
    rng = ScriptedRandom([0.1, 0.1], choice_indices=[0])
    line = describe_move(_move_result(), state, character_name="Arthur", board_width=20, rng=rng)
    assert line == "Arthur sailed into Numenor 183 with Arthur's command."


def test_describe_move_renders_travel_when_moved_without_armies():
    # Phase 769: an armyless personal Move renders TRAV.X, not MARCH.X's
    # own army-flavored text.
    state = _leave_state(terrain=Terrain.PLAINS)
    rng = ScriptedRandom([], choice_indices=[0])
    line = describe_move(
        _move_result(moved_without_armies=True), state, character_name="Arthur", board_width=20, rng=rng
    )
    assert line == "Arthur travelled to Numenor."


def test_describe_move_travel_resolves_sea_marker_from_terrain():
    state = _leave_state(terrain=Terrain.SEA)
    rng = ScriptedRandom([], choice_indices=[1])
    line = describe_move(
        _move_result(moved_without_armies=True), state, character_name="Arthur", board_width=20, rng=rng
    )
    assert line == "Arthur sailed into Numenor."


def test_describe_move_returns_none_when_not_moved():
    state = _leave_state()
    line = describe_move(_move_result(moved=False), state, character_name="Arthur", board_width=20, rng=ScriptedRandom([]))
    assert line is None


def test_describe_move_returns_none_without_new_location():
    state = _leave_state()
    line = describe_move(
        _move_result(new_location=None), state, character_name="Arthur", board_width=20, rng=ScriptedRandom([])
    )
    assert line is None


# -- Phase 766: Naval Hug Coastline stragglers' own arrival narration --


def test_render_naval_hug_coastline_stragglers_arrived():
    line = render_naval_hug_coastline_stragglers_arrived("Arthur", "Numenor", ScriptedRandom([]))
    assert line == "Arthur's troops, left behind for lack of transport, arrived separately at Numenor."


def test_describe_naval_hug_coastline_stragglers_renders_when_moved():
    state = _leave_state()
    line = describe_naval_hug_coastline_stragglers(_move_result(), state, character_name="Arthur", rng=ScriptedRandom([]))
    assert line == "Arthur's troops, left behind for lack of transport, arrived separately at Numenor."


def test_describe_naval_hug_coastline_stragglers_returns_none_when_not_moved():
    state = _leave_state()
    line = describe_naval_hug_coastline_stragglers(
        _move_result(moved=False), state, character_name="Arthur", rng=ScriptedRandom([])
    )
    assert line is None


def test_describe_naval_hug_coastline_stragglers_returns_none_without_new_location():
    state = _leave_state()
    line = describe_naval_hug_coastline_stragglers(
        _move_result(new_location=None), state, character_name="Arthur", rng=ScriptedRandom([])
    )
    assert line is None


def test_describe_turn_results_renders_the_stragglers_sentinel():
    # The sentinel is matched purely by isinstance(entry.result,
    # MoveExecutionResult) with action=None -- proves describe_turn_
    # results() reaches the new branch, not just the composer directly.
    state = _leave_state()
    entry = PhaseDispatchResult(1, -1, "P0", None, _move_result(), None)
    lines = describe_turn_results([entry], state, ScriptedRandom([]), board_width=20)
    assert lines == ["Arthur's troops, left behind for lack of transport, arrived separately at Numenor."]


# -- Phase 736: render_cargo_boarded/describe_cargo_boarded, render_sunk_cargo/record_sunk_cargo_world_events --


def test_render_cargo_boarded():
    result = render_cargo_boarded("Arthur", "Bowmen", "Fleet", ScriptedRandom([]))
    assert result == "Arthur boarded Bowmen aboard the Fleet."


def test_describe_cargo_boarded_renders_one_line_per_boarded_army():
    state = _leave_state()
    state.add_army(ArmyState(1, 1, ArmyType.FLEET, Quality.AVERAGE, HexCoord(3, 9)))
    state.add_army(ArmyState(2, 1, ArmyType.BOWMEN, Quality.AVERAGE, HexCoord(3, 9), transported_by=1))
    result = MoveExecutionResult(
        moved=True, battle_report=None, exploration=None, movement_points_spent=1,
        new_location=HexCoord(3, 9), boarded_army_ids=[2],
    )

    lines = describe_cargo_boarded(result, state, character_name="Arthur", rng=ScriptedRandom([]))

    assert lines == ["Arthur boarded Bowmen aboard the Fleet."]


def test_describe_cargo_boarded_skips_a_boarded_army_id_not_found():
    state = _leave_state()
    result = MoveExecutionResult(
        moved=True, battle_report=None, exploration=None, movement_points_spent=1,
        new_location=HexCoord(3, 9), boarded_army_ids=[999],
    )

    lines = describe_cargo_boarded(result, state, character_name="Arthur", rng=ScriptedRandom([]))

    assert lines == []


def test_describe_cargo_boarded_skips_an_army_with_no_carrier_recorded():
    state = _leave_state()
    state.add_army(ArmyState(2, 1, ArmyType.BOWMEN, Quality.AVERAGE, HexCoord(3, 9)))
    result = MoveExecutionResult(
        moved=True, battle_report=None, exploration=None, movement_points_spent=1,
        new_location=HexCoord(3, 9), boarded_army_ids=[2],
    )

    lines = describe_cargo_boarded(result, state, character_name="Arthur", rng=ScriptedRandom([]))

    assert lines == []


def test_describe_cargo_boarded_returns_empty_with_no_boarded_armies():
    state = _leave_state()
    result = MoveExecutionResult(
        moved=True, battle_report=None, exploration=None, movement_points_spent=1, new_location=HexCoord(3, 9)
    )

    lines = describe_cargo_boarded(result, state, character_name="Arthur", rng=ScriptedRandom([]))

    assert lines == []


def test_render_sunk_cargo():
    result = render_sunk_cargo("Bowmen", "Fleet", ScriptedRandom([]))
    assert result == (
        "The Bowmen being transported sank together with the annihilated Fleet "
        "and disappeared into the depths of the sea."
    )


def test_record_sunk_cargo_world_events_populates_state_world_events():
    state = GameState()
    state.sunk_cargo_events.append(SunkCargoEvent(HexCoord(3, 9), ArmyType.FLEET, ArmyType.BOWMEN))

    record_sunk_cargo_world_events(state, ScriptedRandom([]))

    assert len(state.world_events) == 1
    assert state.world_events[0].coord == HexCoord(3, 9)
    assert state.world_events[0].lines == [
        "The Bowmen being transported sank together with the annihilated Fleet "
        "and disappeared into the depths of the sea."
    ]


def test_record_sunk_cargo_world_events_appends_one_event_per_sunk_cargo_event():
    state = GameState()
    state.sunk_cargo_events.append(SunkCargoEvent(HexCoord(3, 9), ArmyType.FLEET, ArmyType.BOWMEN))
    state.sunk_cargo_events.append(SunkCargoEvent(HexCoord(4, 9), ArmyType.WHALES, ArmyType.AXEMEN))

    record_sunk_cargo_world_events(state, ScriptedRandom([]))

    assert len(state.world_events) == 2


def test_record_sunk_cargo_world_events_is_a_no_op_with_no_events():
    state = GameState()

    record_sunk_cargo_world_events(state, ScriptedRandom([]))

    assert state.world_events == []


# -- Phase 105: render_flee_failure (FLEEFAIL.X) + render_sneak_detected (SNEAKUP.X) --


def test_render_flee_failure_first_variant():
    rng = ScriptedRandom([0.1] * 4, choice_indices=[0])
    result = render_flee_failure("Arthur", "Grendel", rng)
    assert result == "Arthur attempted to flee from the fight, but Grendel cornered Arthur."


def test_render_flee_failure_second_variant_resolves_control_byte():
    rng = ScriptedRandom([0.1] * 8, choice_indices=[1])
    result = render_flee_failure("Arthur", "Grendel", rng)
    assert result == (
        "Arthur turned to flee from Grendel, but found that Arthur's path "
        "of retreat had been magically blocked by a wall of fire."
    )


def test_render_flee_failure_third_variant_land():
    rng = ScriptedRandom([0.1] * 4, choice_indices=[2])
    result = render_flee_failure("Arthur", "Grendel", rng)
    assert result == (
        "Arthur ran from the melee, but slipped and fell.Arthur injured "
        "Arthur's leg and could not escape!"
    )


def test_render_flee_failure_third_variant_sea():
    rng = ScriptedRandom([0.1] * 4, choice_indices=[2])
    result = render_flee_failure("Arthur", "Grendel", rng, is_sea=True)
    assert result == (
        "Arthur swam away from the melee, but scraped against a submerged "
        "rock.Arthur injured Arthur's leg and could not escape!"
    )


def test_render_flee_failure_fourth_variant():
    rng = ScriptedRandom([0.1] * 8, choice_indices=[3])
    result = render_flee_failure("Arthur", "Grendel", rng)
    assert result == (
        "desiring only to escape from Arthur's vicious opponent, Arthur "
        "ran like the wind.But Arthur was too tired and could not gain "
        "ground on Grendel."
    )


def test_render_sneak_detected_first_variant_melee_range():
    rng = ScriptedRandom([0.1] * 4, choice_indices=[0])
    result = render_sneak_detected("Arthur", "Grendel", SNEAKUP_RANGE_MELEE, rng)
    assert result == "Arthur tried to sneak by Grendel, but was seen at melee range."


def test_render_sneak_detected_second_variant_bow_range():
    rng = ScriptedRandom([0.1] * 8, choice_indices=[1])
    result = render_sneak_detected("Arthur", "Grendel", SNEAKUP_RANGE_BOW, rng)
    assert result == (
        "despite Arthur's caution, Arthur was detected by Grendel and "
        "engaged at bow range."
    )


def test_render_sneak_detected_third_variant_spell_range():
    rng = ScriptedRandom([0.1] * 4, choice_indices=[2])
    result = render_sneak_detected("Arthur", "Grendel", SNEAKUP_RANGE_SPELL, rng)
    assert result == (
        "Arthur stole quietly up to the treasure of Grendel, but "
        "unfortunately Arthur was noticed.Arthur had to encounter Grendel "
        "at spell range."
    )


def test_render_sneak_detected_fourth_variant():
    rng = ScriptedRandom([0.1] * 8, choice_indices=[3])
    result = render_sneak_detected("Arthur", "Grendel", SNEAKUP_RANGE_BOW, rng)
    assert result == "Arthur hoped to steal the treasures of Grendel but Grendel spotted Arthur at bow range."


# -- Phase 106: render_wandering_encounter (RWENC.X) --


def test_render_wandering_encounter_first_variant_land():
    rng = ScriptedRandom([0.1] * 6, choice_indices=[0])
    result = render_wandering_encounter("Arthur", "Grendel", rng)
    assert result == "Arthur was crossing an open field when Grendel spotted Arthur from a distance."


def test_render_wandering_encounter_first_variant_sea():
    rng = ScriptedRandom([0.1] * 6, choice_indices=[0])
    result = render_wandering_encounter("Arthur", "Grendel", rng, is_sea=True)
    assert result == "Arthur was swimming in a lagoon when Grendel spotted Arthur from a distance."


def test_render_wandering_encounter_second_variant():
    rng = ScriptedRandom([0.1] * 6, choice_indices=[1])
    result = render_wandering_encounter("Arthur", "Grendel", rng)
    assert result == "Arthur was approached by Grendel."


def test_render_wandering_encounter_third_variant():
    rng = ScriptedRandom([0.1] * 6, choice_indices=[2])
    result = render_wandering_encounter("Arthur", "Grendel", rng)
    assert result == "Grendel came at Arthur from out of nowhere."


def test_render_wandering_encounter_fourth_variant():
    rng = ScriptedRandom([0.1] * 6, choice_indices=[3])
    result = render_wandering_encounter("Arthur", "Grendel", rng)
    assert result == "Arthur encountered Grendel."


# -- Phase 107: render_generic_encounter (ENCO.X) + render_patrol_release
# (SAFPAT.X) + render_patrol_encounter (PATENC.X) --


def test_render_generic_encounter():
    rng = ScriptedRandom([0.1] * 4, choice_indices=[0])
    result = render_generic_encounter("Arthur", "Grendel", rng)
    assert result == "Arthur encountered Grendel."


def test_render_patrol_release_first_variant():
    rng = ScriptedRandom([0.1] * 8, choice_indices=[0])
    result = render_patrol_release("Arthur", "King Harold the Bold", rng)
    assert result == (
        "but when Arthur was taken to the judge, Arthur showed him the "
        "official seal of King Harold the Bold, and was let go."
    )


def test_render_patrol_release_second_variant():
    rng = ScriptedRandom([0.1] * 12, choice_indices=[1])
    result = render_patrol_release("Arthur", "King Harold the Bold", rng)
    assert result == (
        "but he was easily dazzled by Arthur's tales of Arthur's "
        "heroism.he bowed before Arthur and marched away."
    )


def test_render_patrol_release_third_variant_resolves_indefinite_article():
    rng = ScriptedRandom([0.1] * 8, choice_indices=[2])
    result = render_patrol_release("Arthur", "King Harold the Bold", rng)
    assert result == "but Arthur wasn't listed as an outlaw, and that got Arthur off the hook."


def test_render_patrol_encounter_first_variant():
    rng = ScriptedRandom([0.1] * 12, choice_indices=[0])
    result = render_patrol_encounter("Arthur", "King Harold the Bold", rng)
    assert result == (
        "Arthur was ambushed, tied up and severely beaten by wild-eyed "
        "soldiers.Arthur escaped.a King's Ranger tracked Arthur down."
    )


def test_render_patrol_encounter_second_variant():
    rng = ScriptedRandom([0.1] * 8, choice_indices=[1])
    result = render_patrol_encounter("Arthur", "King Harold the Bold", rng)
    assert result == "Arthur was stopped by a patrol.Their commanding officer suspiciously challenged Arthur."


def test_render_patrol_encounter_third_variant():
    rng = ScriptedRandom([0.1] * 8, choice_indices=[2])
    result = render_patrol_encounter("Arthur", "King Harold the Bold", rng)
    assert result == "Arthur was challenged by a Royal bounty hunter who apparently thought Arthur was a spy."


def test_render_patrol_encounter_fourth_variant():
    rng = ScriptedRandom([0.1] * 12, choice_indices=[3])
    result = render_patrol_encounter("Arthur", "King Harold the Bold", rng)
    assert result == (
        "Arthur was badgered by an officer who insulted the respected "
        "name of Arthur.Arthur killed him in a duel, but the rogue's "
        "older brother was a marshal, and he came after Arthur!"
    )


# -- tactical_margin_bucket / render_tactical_comparison (Phase 109) --------


def test_tactical_margin_bucket_is_five_when_even():
    assert tactical_margin_bucket(5, 5) == 5
    assert tactical_margin_bucket(0, 0) == 5


def test_tactical_margin_bucket_favors_attacker_when_higher():
    assert tactical_margin_bucket(6, 5) == 6
    assert tactical_margin_bucket(3, 0) == 8


def test_tactical_margin_bucket_favors_defender_when_lower():
    assert tactical_margin_bucket(4, 5) == 4
    assert tactical_margin_bucket(0, 3) == 2


def test_tactical_margin_bucket_clamps_at_nine():
    assert tactical_margin_bucket(20, 0) == 9


def test_tactical_margin_bucket_clamps_at_one():
    assert tactical_margin_bucket(0, 20) == 1


def test_render_tactical_comparison_bucket_one_defender_total_advantage():
    rng = ScriptedRandom([0.1] * 10)
    result = render_tactical_comparison("Aldric", "Borin", 0, 20, rng)
    assert result == "it was obvious to all that Borin's tactical strokes of genius doubled Borin's strength."


def test_render_tactical_comparison_bucket_one_resolves_sea_marker():
    rng = ScriptedRandom([0.1] * 10)
    result = render_tactical_comparison("Aldric", "Borin", 0, 20, rng, is_sea=True)
    assert result == "it was obvious to all that Borin's naval strokes of genius doubled Borin's strength."


def test_render_tactical_comparison_bucket_five_is_even():
    rng = ScriptedRandom([0.1] * 15)
    result = render_tactical_comparison("Aldric", "Borin", 5, 5, rng)
    assert result == "as the battle developed, the tactical wit of Borin and Aldric seemed evenly matched."


def test_render_tactical_comparison_bucket_nine_attacker_total_advantage():
    rng = ScriptedRandom([0.1] * 15)
    result = render_tactical_comparison("Aldric", "Borin", 20, 0, rng)
    assert result == "tactical supremacy was guaranteed by Aldric's unmatched tactical mind."


def test_render_tactical_comparison_bucket_three_favors_defender():
    rng = ScriptedRandom([0.1] * 15)
    result = render_tactical_comparison("Aldric", "Borin", 3, 5, rng)
    assert result == "despite Aldric's careful leadership, Aldric was tactically outmaneuvered and realized that it would be an uphill struggle."


# -- NEMESIS_TEMPLATE (Phase 109) --------------------------------------------


def test_nemesis_template_has_15_real_entries():
    assert len(NEMESIS_TEMPLATE) == 15
    assert set(NEMESIS_TEMPLATE.keys()) == set(range(1, 16))


def test_nemesis_template_verbatim_sample():
    assert NEMESIS_TEMPLATE[1] == (
        "= were frightened/Rdismayed by the{ sudden/Runexpected}"
        "appearance_of/Rconfrontation_with their hated/Rdreaded nemesis."
    )


def test_nemesis_template_phalanx_vs_legion_matches_rulebook_nemesis():
    # models/army_type.py's own rulebook-sourced NEMESIS dict confirms
    # Legion is Phalanx's real nemesis -- cross-checked, not guessed.
    assert "Legionnaires" in NEMESIS_TEMPLATE[3]


def test_nemesis_template_whales_vs_mermen_matches_rulebook_nemesis():
    assert "Mermen" in NEMESIS_TEMPLATE[10]


def test_nemesis_template_renders_via_prose_render():
    from ak_engine.report.prose import render

    rng = ScriptedRandom([0.1] * 10)
    result = render(NEMESIS_TEMPLATE[3], {"=": "144th Legion"}, rng=rng)
    assert result == "the unwieldy formation of 144th Legion was tested by the flexible Legionnaires."


# -- render_explore_progress / render_explore_continued (Phase 110) ---------


def test_render_explore_progress_first_variant():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])
    result = render_explore_progress("Aldric", "Greenfield", 42, rng)
    assert result == "Aldric explored Greenfield and now 42% of it has been explored."


def test_render_explore_progress_first_variant_right_branch():
    rng = ScriptedRandom([0.9] * 10, choice_indices=[0])
    result = render_explore_progress("Aldric", "Greenfield", 42, rng)
    assert result == "Aldric explored Greenfield well and now 42% of it has been explored."


def test_render_explore_progress_resolves_possessive_marker():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[1])
    result = render_explore_progress("Aldric", "Greenfield", 100, rng)
    assert result == (
        "Aldric travelled throughout Greenfield, exploring its features."
        "After Aldric's efforts, 100% of it has been explored to date."
    )


def test_render_explore_progress_resolves_sea_marker():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[3])
    result = render_explore_progress("Aldric", "Greenfield", 100, rng, is_sea=True)
    assert result == (
        "Aldric explored Greenfield, taking careful notes of the islands "
        "and features, and now 100% of it has been explored."
    )


def test_render_explore_continued_first_variant():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])
    result = render_explore_continued("Aldric", "Greenfield", 55, rng)
    assert result == "Aldric observed the area while we were on the march and now 55% of Greenfield has been explored."


def test_render_explore_continued_resolves_sea_marker():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[3])
    result = render_explore_continued("Aldric", "Greenfield", 60, rng, is_sea=True)
    assert result == (
        "while on the move, Aldric took an interest in the islands of "
        "Greenfield, exploring some unknown areas.We have now explored "
        "60% of Greenfield."
    )


def test_render_explore_already_maxed():
    rng = ScriptedRandom([0.1] * 4)
    result = render_explore_already_maxed("Aldric", "Greenfield", rng)
    assert result == "Aldric tried to explore Greenfield but it seemed that it had already been completely explored."


def test_explore_already_maxed_template_is_the_confirmed_hardcoded_say():
    assert EXPLORE_ALREADY_MAXED_TEMPLATE == (
        "< tried to explore @ but it seemed that it had already been "
        "completely explored."
    )


def test_explore_not_present_prefix_is_the_confirmed_hardcoded_precursor():
    # No trailing period -- SAY.PAS concatenates one of the three Explore
    # templates above directly after this clause.
    assert EXPLORE_NOT_PRESENT_PREFIX == "< wasn't in @ so "


# -- Fire Arrow attack sequence (Phase 111) ----------------------------------


def test_render_move_to_bow_range_first_variant():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])
    result = render_move_to_bow_range("Aldric", rng)
    assert result == "Aldric moved to bow range."


def test_render_move_to_bow_range_resolves_sea_marker():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[1])
    result = render_move_to_bow_range("Aldric", rng, is_sea=True)
    assert result == "Aldric swam along smoothly and closed to bow range."


def test_render_move_to_melee_range_first_variant():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])
    result = render_move_to_melee_range("Aldric", rng)
    assert result == "Aldric charged into the melee."


def test_render_move_to_melee_range_resolves_sea_marker():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])
    result = render_move_to_melee_range("Aldric", rng, is_sea=True)
    assert result == "Aldric darted into the melee."


def test_render_fire_arrow_attack_first_variant_has_no_trailing_punctuation():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])
    result = render_fire_arrow_attack("Aldric", "Borin", rng)
    assert result == "Aldric Fired an arrow at Borin"


def test_render_fire_arrow_attack_second_variant():
    rng = ScriptedRandom([0.9] * 10, choice_indices=[1])
    result = render_fire_arrow_attack("Aldric", "Borin", rng)
    assert result == "Aldric Fired an angry arrow at Borin"


def test_render_attack_missed_first_variant():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])
    result = render_attack_missed("Aldric", "Borin", "arrow", rng)
    assert result == " and missed."


def test_render_attack_missed_second_variant_names_the_weapon():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[1])
    result = render_attack_missed("Aldric", "Borin", "arrow", rng)
    assert result == " but Borin dodged the blow."


def test_render_attack_missed_resolves_sea_marker():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[2])
    result = render_attack_missed("Aldric", "Borin", "arrow", rng, is_sea=True)
    assert result == " but Aldric's arrow darted through the murky water."


def test_fire_arrow_attack_and_missed_concatenate_into_one_sentence():
    rng = ScriptedRandom([0.1] * 20, choice_indices=[0, 0])
    attack = render_fire_arrow_attack("Aldric", "Borin", rng)
    miss = render_attack_missed("Aldric", "Borin", "arrow", rng)
    assert attack + miss == "Aldric Fired an arrow at Borin and missed."


# -- Phase 413: Hand of Death's own per-round squeeze narration ------------


def test_render_squeeze_attack_heart_variant_left_choices_omit_the_adverb():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])
    result = render_squeeze_attack("Aldric", "Borin", rng)
    assert result == "Aldric curled Aldric's phantasmal hand around Borin's heart and squeezed it"


def test_render_squeeze_attack_heart_variant_right_choices_include_the_adverb():
    rng = ScriptedRandom([0.9] * 10, choice_indices=[0])
    result = render_squeeze_attack("Aldric", "Borin", rng)
    assert result == "Aldric wrapped Aldric's phantasmal hand around Borin's heart and squeezed it mercilessly"


def test_render_squeeze_attack_innards_variant_omits_tightly():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[2])
    result = render_squeeze_attack("Aldric", "Borin", rng)
    assert result == "Aldric clenched Aldric's fist, squeezing the innards of Borin"


def test_render_squeeze_attack_innards_variant_includes_tightly():
    rng = ScriptedRandom([0.9] * 10, choice_indices=[2])
    result = render_squeeze_attack("Aldric", "Borin", rng)
    assert result == "Aldric clenched Aldric's fist tightly, squeezing the innards of Borin"


def test_render_squeeze_attack_tearing_variant_left_choices():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[4])
    result = render_squeeze_attack("Aldric", "Borin", rng)
    assert result == "Aldric brought Aldric's hands together and yanked them apart in a ripping gesture, provoking a squeal from Borin"


def test_render_squeeze_attack_tearing_variant_right_choices():
    rng = ScriptedRandom([0.9] * 10, choice_indices=[4])
    result = render_squeeze_attack("Aldric", "Borin", rng)
    assert result == (
        "Aldric brought Aldric's hands together and pulled them apart in a tearing motion, "
        "provoking a blood-curdling squeal of pain from Borin"
    )


def test_squeeze_attack_and_hit_concatenate_into_one_sentence():
    rng = ScriptedRandom([0.1] * 20, choice_indices=[0, 0])
    attack = render_squeeze_attack("Aldric", "Borin", rng)
    hit = render_attack_hit("Borin", 3, rng)
    assert attack + hit == (
        "Aldric curled Aldric's phantasmal hand around Borin's heart and squeezed it and inflicted 3 damage points."
    )


# -- hit / devastate / mortal-wound continuations (Phase 112) ---------------


def test_render_attack_hit_first_variant():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])
    result = render_attack_hit("Borin", 4, rng)
    assert result == " and inflicted 4 damage points."


def test_render_attack_hit_second_variant_names_the_defender():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[1])
    result = render_attack_hit("Borin", 4, rng)
    assert result == " and scorched Borin with 4 damage points."


def test_render_attack_devastating_hit_left_branch():
    rng = ScriptedRandom([0.1] * 4)
    result = render_attack_devastating_hit("Borin", rng)
    assert result == " and devastated Borin."


def test_render_attack_devastating_hit_right_branch():
    rng = ScriptedRandom([0.9] * 4)
    result = render_attack_devastating_hit("Borin", rng)
    assert result == " and annihilated Borin."


def test_attack_devastating_hit_template_is_the_confirmed_hardcoded_say():
    assert ATTACK_DEVASTATING_HIT_TEMPLATE == " and devastated/Rannihilated [."


def test_render_mortally_wounded_first_variant():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])
    result = render_mortally_wounded("Borin", rng)
    assert result == "Borin was mortally wounded."


def test_render_mortally_wounded_resolves_sea_marker():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[1])
    result = render_mortally_wounded("Borin", rng, is_sea=True)
    assert result == "Borin sank down, fatally injured."


def test_render_mortally_wounded_fourth_variant_describes_a_stun_not_death():
    # MORTWOUN.X's own 4th line, despite the file's name -- transcribed
    # verbatim rather than assumed to mean death (see module docstring).
    rng = ScriptedRandom([0.1] * 10, choice_indices=[3])
    result = render_mortally_wounded("Borin", rng)
    assert result == "Borin staggered, stunned by the deadly blow."


# -- HORDEATH.X (Phase 607) --


def test_render_character_death_first_variant():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])
    result = render_character_death("Aldric", rng)
    assert result == "and so it was that Aldric met Aldric's unseemly end."


def test_render_character_death_second_variant_excludes_optional_clause():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[1])
    result = render_character_death("Aldric", rng)
    assert result == "thus did Aldric die, a brave end by any standard."


def test_render_character_death_second_variant_includes_optional_clause():
    rng = ScriptedRandom([0.99] * 10, choice_indices=[1])
    result = render_character_death("Aldric", rng)
    assert result == "thus did Aldric finally die, a defiant death by any standard."


def test_fire_arrow_attack_and_hit_concatenate_into_one_sentence():
    rng = ScriptedRandom([0.1] * 20, choice_indices=[0, 0])
    attack = render_fire_arrow_attack("Aldric", "Borin", rng)
    hit = render_attack_hit("Borin", 5, rng)
    assert attack + hit == "Aldric Fired an arrow at Borin and inflicted 5 damage points."


# -- render_melee_attack (Phase 113) -----------------------------------------


def test_render_melee_attack_first_variant_left_branch():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])
    result = render_melee_attack("Aldric", "Borin", "Slashed", rng)
    assert result == "Aldric assailed Borin"


def test_render_melee_attack_first_variant_right_branch():
    rng = ScriptedRandom([0.9] * 10, choice_indices=[0])
    result = render_melee_attack("Aldric", "Borin", "Slashed", rng)
    assert result == "Aldric circled left and violently attacked Borin"


def test_render_melee_attack_resolves_attack_method_marker():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[1])
    result = render_melee_attack("Aldric", "Borin", "Thrust", rng)
    assert result == "Aldric Thrust Borin"


def test_render_melee_attack_ninth_variant_has_no_trailing_punctuation():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[8])
    result = render_melee_attack("Aldric", "Borin", "Slashed", rng)
    assert result == "Aldric Slashed Borin"


# -- CCAST.X/FLAMEREL.X/SHADTR.X/RECSTUN.X/STUN.X (Phase 588) --


def test_render_cast_no_treasure_first_variant():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])
    result = render_cast_no_treasure("Aldric", "Fireball", rng)
    assert result == (
        "weaving Aldric's silver words of magic into a mighty Fireball "
        "spell, Aldric waved Aldric's hands"
    )


def test_render_cast_no_treasure_resolves_sea_marker():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[3])
    result = render_cast_no_treasure("Aldric", "Fireball", rng, is_sea=True)
    assert result == "raising Aldric's hands high in the waves, Aldric cast a Fireball spell"


def test_render_flaming_scimitar_proc_first_variant():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])
    result = render_flaming_scimitar_proc("Borin", rng)
    assert result == "the Flaming Scimitar released a fireball which imploded inside Borin."


def test_render_shadow_sword_drain_first_variant():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])
    result = render_shadow_sword_drain("Aldric", "Borin", 42, rng)
    assert result == "the Shadow Sword transferred the life energy to Aldric and Aldric's hit points rose to 42."


# -- Phase 740: render_weapon_proc_line() ------------------------------


def test_render_weapon_proc_line_shadow_sword_drain():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])
    result = render_weapon_proc_line("shadow_sword_drain", "Aldric", "Borin", 7, rng)
    assert result == "the Shadow Sword transferred the life energy to Aldric and Aldric's hit points rose to 7."


def test_render_weapon_proc_line_flaming_scimitar_instakill():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])
    result = render_weapon_proc_line("flaming_scimitar_instakill", "Aldric", "Borin", None, rng)
    assert result == "the Flaming Scimitar released a fireball which imploded inside Borin."


def test_render_weapon_proc_line_psychic_flail_stun():
    # Phase 767: attributed to the *defender* (Borin), not the Flail's
    # own wielder (Aldric) -- the one actually stunned.
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])
    result = render_weapon_proc_line("psychic_flail_stun", "Aldric", "Borin", None, rng)
    assert result == "Borin stood stunned, unable to regain Borin's senses."


def test_render_weapon_proc_line_returns_none_for_no_proc():
    rng = ScriptedRandom([])
    assert render_weapon_proc_line(None, "Aldric", "Borin", None, rng) is None


def test_render_stun_recovery_first_variant():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])
    result = render_stun_recovery("Aldric", rng)
    assert result == "Aldric shook Aldric's head and recovered from Aldric's stunned state."


def test_render_stunned_first_variant():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])
    result = render_stunned("Aldric", rng)
    assert result == "Aldric stood stunned, unable to regain Aldric's senses."


def test_render_stunned_resolves_sea_marker():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])
    result = render_stunned("Aldric", rng, is_sea=True)
    assert result == "Aldric stayed stunned, unable to regain Aldric's senses."


# -- GLSTEAL.X/GMSTEAL.X/GLSPOILS.X/GMSPOILS.X/TLSTEAL.X/TMSTEAL.X/
# -- TLSPOILS.X/TMSPOILS.X (Phase 590) -- sourced, render-tested, but
# -- not wired into any composer (see module docstring's own Phase 590
# -- addendum for why).


def test_render_group_theft_from_survivor_first_variant():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])
    result = render_group_theft_from_survivor("Aldric", "Borin", ["a sword", "a shield"], rng)
    assert result == "Aldric pickpocketed Borin's a sword and a shield."


def test_render_group_theft_from_survivor_single_item_has_no_conjunction():
    rng = ScriptedRandom([0.99] * 10, choice_indices=[1])
    result = render_group_theft_from_survivor("Aldric", "Borin", ["a ring"], rng)
    assert result == "Aldric skillfully stole the a ring owned by Borin."


def test_render_group_theft_tense_joins_three_items():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[3])
    result = render_group_theft_tense("Aldric", ["a ring", "a wand", "a helm"], rng)
    assert result == "Aldric grabbed the a ring, a wand and a helm, Aldric's eyes glittering with avarice."


def test_render_group_spoils_from_survivor_first_variant():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])
    result = render_group_spoils_from_survivor("Aldric", "Borin", ["a wand"], rng)
    assert result == "Aldric grabbed the a wand."


def test_render_group_spoils_from_survivor_includes_optional_hoard_clause():
    rng = ScriptedRandom([0.99] * 10, choice_indices=[0])
    result = render_group_spoils_from_survivor("Aldric", "Borin", ["a wand"], rng)
    assert result == "Aldric took the a wand from Borin's treasure."


def test_render_group_spoils_from_corpse_first_variant():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])
    result = render_group_spoils_from_corpse("Aldric", "Borin", ["a helm"], rng)
    assert result == "Aldric bagged the a helm."


def test_render_group_spoils_from_corpse_resolves_sea_marker():
    # The /S marker sits inside an optional `{...}` clause -- only
    # visible at rng >= 0.5 (clause included); a low rng excludes the
    # whole clause and the /S choice never gets a chance to differ.
    rng = ScriptedRandom([0.99] * 10, choice_indices=[0])
    result = render_group_spoils_from_corpse("Aldric", "Borin", ["a helm"], rng, is_sea=True)
    assert result == "Aldric swam over to a mound of treasure and secured the a helm."


def test_render_group_spoils_from_corpse_third_variant_is_the_real_unreachable_overflow():
    # GMSPOILS.X's own header declares only 1 choice -- choices 2/3 were
    # never reachable in the original engine (see module docstring's own
    # Phase 590 addendum), but the real bytes are preserved here anyway.
    rng = ScriptedRandom([0.1] * 10, choice_indices=[2])
    result = render_group_spoils_from_corpse("Aldric", "Borin", ["a helm"], rng)
    assert result == "the a helm lay nearby, and Aldric picked up the treasure."


def test_render_treasure_theft_from_survivor_first_variant():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])
    result = render_treasure_theft_from_survivor("Aldric", rng)
    assert result == "Aldric cautiously laid hands on for the treasure."


def test_render_treasure_theft_from_survivor_resolves_greedy_clause():
    rng = ScriptedRandom([0.99] * 10, choice_indices=[2])
    result = render_treasure_theft_from_survivor("Aldric", rng)
    assert result == "Aldric succeeded in laying Aldric's greedy fingers on the treasure."


def test_render_treasure_theft_tense_first_variant():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])
    result = render_treasure_theft_tense("Aldric", rng)
    assert result == "Aldric caressed the treasure fondly."


def test_render_treasure_theft_tense_fourth_variant():
    rng = ScriptedRandom([0.99] * 10, choice_indices=[3])
    result = render_treasure_theft_tense("Aldric", rng)
    assert result == (
        "Aldric could see the gleaming, glowing treasure which seemed to "
        "seductively call out to Aldric's trembling fingers."
    )


def test_render_treasure_spoils_from_survivor_first_variant():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])
    result = render_treasure_spoils_from_survivor("Aldric", "Borin", rng)
    assert result == "Aldric stooped to recover the belongings of Borin."


def test_render_treasure_spoils_from_survivor_fourth_variant():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[3])
    result = render_treasure_spoils_from_survivor("Aldric", "Borin", rng)
    assert result == "Aldric stripped Borin of Borin's treasure."


def test_render_treasure_spoils_from_corpse_first_variant():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])
    result = render_treasure_spoils_from_corpse("Aldric", "Borin", rng)
    assert result == "Aldric looked with satisfaction at the remains of Borin."


def test_render_treasure_spoils_from_corpse_second_variant():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[1])
    result = render_treasure_spoils_from_corpse("Aldric", "Borin", rng)
    assert result == "Aldric shifted Aldric's attention to the treasure of Borin."


# -- LSPOILG.X (Phase 596) --


def test_render_gold_spoils_first_variant():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])
    result = render_gold_spoils("Aldric", "Borin", 42, rng)
    assert result == "Aldric took 42 gold from the treasure of Borin."


def test_render_gold_spoils_second_variant_has_no_victim_reference():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[1])
    result = render_gold_spoils("Aldric", "Borin", 42, rng)
    assert result == "Aldric found a treasure of 42 gold."


def test_render_gold_spoils_second_variant_includes_optional_clause():
    rng = ScriptedRandom([0.99] * 10, choice_indices=[1])
    result = render_gold_spoils("Aldric", "Borin", 42, rng)
    assert result == "Aldric located a treasure of 42 gold and snarfed it up."


def test_render_gold_spoils_third_variant():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[2])
    result = render_gold_spoils("Aldric", "Borin", 42, rng)
    assert result == "Aldric found 42 gold in the treasure of Borin."


# -- AWANDFR.X/AWANDTO.X/LWANDFR.X/LWANDTO.X (Phase 591) --


def test_render_mercenary_army_wanders_away_first_variant():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])
    result = render_mercenary_army_wanders_away("144th Legion", "Ferrara", "Mongu", rng)
    assert result == (
        "144th Legion grew tired of the whores of Ferrara and moved on "
        "off to Mongu where they hoped the pickings would be more to "
        "their liking."
    )


def test_render_mercenary_army_wanders_away_resolves_sea_marker():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])
    result = render_mercenary_army_wanders_away("144th Legion", "Ferrara", "Mongu", rng, is_sea=True)
    assert result == (
        "144th Legion grew tired of the whores of Ferrara and sailed "
        "off to Mongu where they hoped the pickings would be more to "
        "their liking."
    )


def test_render_mercenary_army_wanders_away_third_variant_resolves_article():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[2])
    result = render_mercenary_army_wanders_away("144th Legion", "Ferrara", "Mongu", rng)
    assert result == (
        "the captain of 144th Legion felt a wanderlust stirring in his "
        "breast, and speaking highly of Mongu, persuaded his men to "
        "march with him to Mongu."
    )


def test_render_mercenary_army_wanders_in_first_variant():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])
    result = render_mercenary_army_wanders_in("144th Legion", "Ferrara", "Mongu", rng)
    assert result == "144th Legion has arrived in Mongu, having travelled from Ferrara."


def test_render_mercenary_army_wanders_in_includes_optional_clauses():
    rng = ScriptedRandom([0.99] * 10, choice_indices=[0])
    result = render_mercenary_army_wanders_in("144th Legion", "Ferrara", "Mongu", rng)
    assert result == (
        "144th Legion has just recently arrived in Mongu, having come "
        "from Ferrara in search of employment."
    )


def test_render_character_wanders_away_first_variant():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])
    result = render_character_wanders_away("Aldric", "Ferrara", "Mongu", rng)
    assert result == "Aldric grew bored with Ferrara and departed for Mongu."


def test_render_character_wanders_away_sixth_variant():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[5])
    result = render_character_wanders_away("Aldric", "Ferrara", "Mongu", rng)
    assert result == "Aldric left Ferrara to attend a reunion of Aldric's old regiment in Mongu."


def test_render_character_wanders_away_resolves_sea_marker():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[3])
    result = render_character_wanders_away("Aldric", "Ferrara", "Mongu", rng, is_sea=True)
    assert result == "Aldric got into trouble with the law in Ferrara and escaped by sailing away to Mongu."


def test_render_character_wanders_in_first_variant():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])
    result = render_character_wanders_in("Aldric", "Ferrara", "Mongu", rng)
    assert result == "Aldric just recently wandered into Mongu from Ferrara."


def test_render_character_wanders_in_third_variant_is_two_sentences():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[2])
    result = render_character_wanders_in("Aldric", "Ferrara", "Mongu", rng)
    assert result == (
        "Aldric hiked into Mongu.Aldric had grown bored with Ferrara "
        "and was attracted there by tales of its fine scotch."
    )


def test_render_character_wanders_in_fourth_variant_includes_optional_clause():
    rng = ScriptedRandom([0.99] * 10, choice_indices=[3])
    result = render_character_wanders_in("Aldric", "Ferrara", "Mongu", rng)
    assert result == "Aldric rode into Mongu in search of worthy employment, having found nothing much in Ferrara."


# -- THATT.X/THFAIL.X (Phase 592) --


def test_render_thief_searches_treasure_first_variant():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])
    result = render_thief_searches_treasure("Aldric", "Borin", rng)
    assert result == "Aldric crept up on Borin's treasure, hoping to steal a great treasure."


def test_render_thief_searches_treasure_third_variant_is_two_sentences():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[2])
    result = render_thief_searches_treasure("Aldric", "Borin", rng)
    assert result == (
        "Aldric searched for Borin's treasure.Aldric's greedy fingers "
        "twitched in anticipation when Aldric saw the chest."
    )


def test_render_thief_searches_treasure_fifth_variant_includes_optional_clauses():
    rng = ScriptedRandom([0.99] * 10, choice_indices=[4])
    result = render_thief_searches_treasure("Aldric", "Borin", rng)
    assert result == (
        "Aldric quietly searched for the treasure of Borin.Finally "
        "Aldric found a concealed chest, and a black tide of avarice "
        "gushed up out of Aldric's heart and filled Aldric's dry throat."
    )


def test_render_thief_search_failed_first_variant():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])
    result = render_thief_search_failed("Aldric", rng)
    assert result == "but after searching for an hour, Aldric failed to find any treasure."


def test_render_thief_search_failed_second_variant_excludes_redundant_repeat():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[1])
    result = render_thief_search_failed("Aldric", rng)
    assert result == "Aldric searched the area, but could not find any treasure and departed in frustration."


def test_render_thief_search_failed_third_variant_is_two_sentences():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[2])
    result = render_thief_search_failed("Aldric", rng)
    assert result == "Aldric had hopes of hauling away a hoard.But searching could not reveal treasure of any value."


# -- TGETAWAY.X (Phase 602) --


def test_render_steal_treasure_inaccessible_first_variant():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])
    result = render_steal_treasure_inaccessible("Aldric", "Borin", rng)
    assert result == "but the treasure of Borin was encased in thick steel, and Aldric could not find a way into the treasure."


def test_render_steal_treasure_inaccessible_second_variant_includes_optional_clause():
    rng = ScriptedRandom([0.99] * 10, choice_indices=[1])
    result = render_steal_treasure_inaccessible("Aldric", "Borin", rng)
    assert result == "Aldric stole up to the treasure chest of Borin, but could not open the lock and had to leave without any treasure."


def test_render_steal_treasure_inaccessible_third_variant_includes_optional_clauses():
    rng = ScriptedRandom([0.99] * 10, choice_indices=[2])
    result = render_steal_treasure_inaccessible("Aldric", "Borin", rng)
    assert result == (
        "Aldric found what seemed to be the treasure of Borin, but "
        "after Aldric had taken it Aldric looked at it more carefully "
        "and discovered to Aldric's dismay that it was just a cheap fake."
    )


# -- BATLDR.X (Phase 593) --


def test_render_battle_leader_intro_first_variant_land():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])
    result = render_battle_leader_intro("Aldric", rng)
    assert result == "Aldric led Aldric's armies into the battle."


def test_render_battle_leader_intro_first_variant_resolves_sea_marker():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])
    result = render_battle_leader_intro("Aldric", rng, is_sea=True)
    assert result == "Aldric led Aldric's navies into the battle."


def test_render_battle_leader_intro_third_variant_includes_optional_clause():
    rng = ScriptedRandom([0.99] * 10, choice_indices=[2])
    result = render_battle_leader_intro("Aldric", rng)
    assert result == "Aldric led a host of loyal soldiers into the battle."


def test_render_battle_leader_intro_fourth_variant_puts_commander_name_last():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[3])
    result = render_battle_leader_intro("Aldric", rng, is_sea=True)
    assert result == "standing at the ready with Aldric's ships was Aldric."


# -- BATLDR.X's own "present, not commanding" branch (Phase 658) --


def test_render_battle_leader_no_command():
    rng = ScriptedRandom([])
    result = render_battle_leader_no_command("Aldric", rng)
    assert result == "Aldric was there, leading no armies."


# -- BATLDR.X's own "no generals present at all" branch (Phase 927) --


def test_render_battle_leader_no_generals():
    rng = ScriptedRandom([])
    result = render_battle_leader_no_generals("Defendia", rng)
    assert result == "no generals were present to lead the forces of Defendia."


# -- MCOME.X/MFIGHT.X (Phase 604) --


def test_render_monster_reinforcement_arrives_first_variant_ignores_province():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])
    result = render_monster_reinforcement_arrives("the Forest Guardian", "144th Legion", "Mongu", rng)
    assert result == "the Forest Guardian, hearing of the peril of the Druidic king, arrived at the battle to fight with 144th Legion."


def test_render_monster_reinforcement_arrives_second_variant_uses_province():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[1])
    result = render_monster_reinforcement_arrives("the Forest Guardian", "144th Legion", "Mongu", rng)
    assert result == (
        "word of the impending battle had spread throughout Mongu, so "
        "that even the Forest Guardian heard of it and made an "
        "appearance, where the Forest Guardian fought alongside 144th Legion."
    )


def test_render_monster_reinforcement_helped_first_variant():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])
    result = render_monster_reinforcement_helped("the Forest Guardian", "144th Legion", rng)
    assert result == "the Forest Guardian was of some slight help in the battle."


def test_render_monster_reinforcement_helped_fifth_variant():
    rng = ScriptedRandom([0.99] * 10, choice_indices=[4])
    result = render_monster_reinforcement_helped("the Forest Guardian", "144th Legion", rng)
    assert result == "the Forest Guardian almost tripled the strength of 144th Legion!"


# -- BINOCPR.X (Phase 594) --

_BINOCPR_KWARGS = dict(
    direction="east",
    wealth_descriptor="poor",
    terrain_name="Plains",
    province_name="Mongu",
    province_number="305",
    race_name="Elves",
    ruler_name="Aldric",
)


def test_render_binoculars_preview_first_variant():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])
    result = render_binoculars_preview(**_BINOCPR_KWARGS, rng=rng)
    assert result == "to the east lies a poor Plains province called Mongu 305, populated by Elves.It is ruled by Aldric."


def test_render_binoculars_preview_fourth_variant_resolves_sea_marker():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[3])
    result = render_binoculars_preview(**_BINOCPR_KWARGS, rng=rng, is_sea=True)
    assert result == "to the east there lies a Plains province known as Mongu 305, a poor area of Elves where Aldric rules."


def test_render_binoculars_preview_fifth_variant_appends_ern_suffix_to_direction():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[4])
    kwargs = dict(_BINOCPR_KWARGS, direction="northeast")
    result = render_binoculars_preview(**kwargs, rng=rng)
    assert result == (
        "viewing the northeastern horizon, a man can see a poor Plains "
        "province called Mongu 305.It is said that Aldric reigns "
        "there.It is known to be occupied by Elves."
    )


def test_render_binoculars_preview_sixth_variant():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[5])
    result = render_binoculars_preview(**_BINOCPR_KWARGS, rng=rng)
    assert result == "east of here lies the poor province of Mongu 305, ruled by Aldric.It is said to be a Plains province inhabited by Elves."


# -- Phase 155: monster missile-attack flavor text + Troll regeneration --


def test_render_breath_weapon_hit():
    rng = ScriptedRandom([])
    result = render_breath_weapon_hit("Red Dragon", "Aldric", 7, rng)
    assert result == "The Red Dragon breathes, and the impact deals 7 damage points."


def test_render_breath_weapon_missed():
    rng = ScriptedRandom([])
    result = render_breath_weapon_missed("Red Dragon", "Aldric", rng)
    assert result == "The Red Dragon breathes, but Aldric miraculously manages to evade it!"


def test_render_boulder_throw_hit():
    rng = ScriptedRandom([])
    result = render_boulder_throw_hit("Giant", "Aldric", 5, rng)
    assert result == "The Giant hurls a huge boulder, and the impact deals 5 damage points."


def test_render_boulder_throw_missed():
    rng = ScriptedRandom([])
    result = render_boulder_throw_missed("Giant", "Aldric", rng)
    assert result == "The Giant hurls a huge boulder, but Aldric dodges it."


def test_render_petrifying_gaze_hit():
    rng = ScriptedRandom([])
    result = render_petrifying_gaze_hit("Basilisk", "Aldric", 4, rng)
    assert result == "The Basilisk casts a petrifying gaze, and Aldric takes 4 damage points."


def test_render_petrifying_gaze_missed():
    rng = ScriptedRandom([])
    result = render_petrifying_gaze_missed("Basilisk", "Aldric", rng)
    assert result == "The Basilisk casts a gaze, but Aldric evades it."


def test_render_troll_regeneration():
    rng = ScriptedRandom([])
    result = render_troll_regeneration("Troll", rng)
    assert result == "Horror! The Troll is regenerating its wounds."


def test_missile_attack_flavor_breath_weapons():
    assert missile_attack_flavor(Weapon.FLAME_BREATH) == "breath_weapon"
    assert missile_attack_flavor(Weapon.SPIT_ACID) == "breath_weapon"
    assert missile_attack_flavor(Weapon.POIS_BREATH) == "breath_weapon"


def test_missile_attack_flavor_boulder():
    assert missile_attack_flavor(Weapon.BOULDER) == "boulder_throw"


def test_missile_attack_flavor_gaze():
    assert missile_attack_flavor(Weapon.GAZE) == "petrifying_gaze"


def test_missile_attack_flavor_none_for_unrelated_weapon():
    assert missile_attack_flavor(Weapon.BOW) is None
    assert missile_attack_flavor(Weapon.NO_WEAP) is None


def test_melee_attack_and_missed_concatenate_into_one_sentence():
    rng = ScriptedRandom([0.1] * 20, choice_indices=[1, 0])
    attack = render_melee_attack("Aldric", "Borin", "Thrust", rng)
    miss = render_attack_missed("Aldric", "Borin", "sword", rng)
    assert attack + miss == "Aldric Thrust Borin and missed."


# -- Hire/Fire narrative (Phase 114) -----------------------------------------


def test_render_hire_accepted_left_branch():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])
    result = render_hire_accepted("Aldric", "Borin", "King Harold the Bold", rng)
    assert result == "Aldric spoke to Borin and convinced Borin to pledge Borin's allegiance to King Harold the Bold."


def test_render_hire_accepted_right_branch():
    rng = ScriptedRandom([0.9] * 10, choice_indices=[0])
    result = render_hire_accepted("Aldric", "Borin", "King Harold the Bold", rng)
    assert result == (
        "Aldric spoke eloquently to Borin of the grandness of King "
        "Harold the Bold's empire and convinced Borin to pledge Borin's "
        "services to King Harold the Bold."
    )


def test_render_hire_refused_first_variant():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])
    result = render_hire_refused("Aldric", "Borin", "King Harold the Bold", rng)
    assert result == "Borin refused to join with King Harold the Bold, citing a clan enmity with King Harold the Bold's alignment."


def test_render_hire_refused_third_variant_has_nested_quote():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[2])
    result = render_hire_refused("Aldric", "Borin", "King Harold the Bold", rng)
    assert result == (
        "Borin turned down employment, expressing Borin's disgust for "
        "King Harold the Bold's alignment and criticizing King Harold "
        'the Bold for "Holding a palace court staffed with buffoons!"'
    )


def test_render_fire_hireling_first_variant_uses_king_marker():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])
    result = render_fire_hireling("Aldric", "Borin", "King Harold the Bold", rng)
    assert result == (
        "Aldric told Borin that Borin was no longer an useful employee "
        "to King Harold the Bold, and relieved Borin of Borin's position."
    )


def test_render_fire_hireling_fourth_variant():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[3])
    result = render_fire_hireling("Aldric", "Borin", "King Harold the Bold", rng)
    assert result == "Aldric fired Borin and told Borin to find employment elsewhere."


def test_render_hire_counter_offer():
    rng = ScriptedRandom([0.1] * 4)
    result = render_hire_counter_offer("Aldric", "Borin", 50, rng)
    assert result == "Borin informed Aldric that Borin would not sell Borin's services for less than 50 gold."


def test_hire_counter_offer_template_is_the_confirmed_hardcoded_say():
    assert HIRE_COUNTER_OFFER_TEMPLATE == "[1 informed <2 that [1 would not sell ] services for less than # gold."


# -- describe_hire / describe_fire (integration, Phase 143) --


def test_describe_hire_renders_acceptance():
    result = HireExecutionResult(HireRequest(hero_id=32, gold_offer=2), hired=True)
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])

    line = describe_hire(result, character_name="Aldric", hireling_name="Borin", king_name="King Harold the Bold", rng=rng)

    assert line == "Aldric spoke to Borin and convinced Borin to pledge Borin's allegiance to King Harold the Bold."


def test_describe_hire_renders_nothing_on_administrative_failure_reasons():
    # These five real HireExecutionResult failure reasons stay
    # administrative, with no sourced narrative template.
    for reason in ("hero not found", "cannot hire a King", "hero already in service", "not co-located", "insufficient treasury"):
        result = HireExecutionResult(HireRequest(hero_id=32, gold_offer=2), hired=False, reason=reason)
        rng = ScriptedRandom([])

        line = describe_hire(result, character_name="Aldric", hireling_name="Borin", king_name="King Harold the Bold", rng=rng)

        assert line is None


def test_describe_hire_renders_refusal_on_too_wide_an_alignment_gap():
    # Phase 162 unblocks render_hire_refused (REFHIRE.X) via the real
    # required-pay formula's "alignment gap too wide" reason.
    result = HireExecutionResult(HireRequest(hero_id=32, gold_offer=4), hired=False, reason="alignment gap too wide", minimum_gold=5)
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])

    line = describe_hire(result, character_name="Aldric", hireling_name="Borin", king_name="King Harold the Bold", rng=rng)

    assert line is not None
    assert "Borin" in line
    assert "King Harold the Bold" in line


def test_describe_hire_renders_counter_offer_on_price_refusal():
    # Phase 162 unblocks render_hire_counter_offer (_LCounter) via the
    # real required-pay formula's "offer below required pay" reason.
    result = HireExecutionResult(HireRequest(hero_id=32, gold_offer=1), hired=False, reason="offer below required pay", minimum_gold=3)
    rng = ScriptedRandom([0.1] * 10)

    line = describe_hire(result, character_name="Aldric", hireling_name="Borin", king_name="King Harold the Bold", rng=rng)

    assert line == "Borin informed Aldric that Borin would not sell Borin's services for less than 3 gold."


def test_describe_fire_renders_a_successful_release():
    result = FireExecutionResult(FireRequest(hero_id=32), fired=True)
    rng = ScriptedRandom([0.1] * 10, choice_indices=[3])

    line = describe_fire(result, character_name="Aldric", hireling_name="Borin", king_name="King Harold the Bold", rng=rng)

    assert line == "Aldric fired Borin and told Borin to find employment elsewhere."


def test_describe_fire_renders_nothing_on_failure():
    for reason in ("hero not found", "not co-located"):
        result = FireExecutionResult(FireRequest(hero_id=32), fired=False, reason=reason)
        rng = ScriptedRandom([])

        line = describe_fire(result, character_name="Aldric", hireling_name="Borin", king_name="King Harold the Bold", rng=rng)

        assert line is None


# -- describe_steal (integration, Phase 306) ---------------------------------


def test_describe_steal_renders_the_ransom_narrative():
    result = ChallengeExecutionResult(accepted=True, combat_occurred=True, steal_outcome="ransom")
    rng = ScriptedRandom([0.1] * 10)

    line = describe_steal(result, thief_name="Aldric", victim_name="Borin", rng=rng)

    assert line == (
        "Borin caught Aldric red-handed while Aldric was rummaging "
        "through Borin's things in a bungled attempt at thievery.Borin "
        "forced Aldric to pay Borin half Aldric's treasury in ransom "
        "before letting him go."
    )


def test_describe_steal_renders_the_combat_narrative_at_the_captured_range():
    result = ChallengeExecutionResult(
        accepted=True, combat_occurred=True, steal_outcome="combat", steal_capture_range=CombatRange.MELEE_RANGE
    )
    rng = ScriptedRandom([0.1] * 4, choice_indices=[0])

    line = describe_steal(result, thief_name="Arthur", victim_name="Grendel", rng=rng)

    assert line == "Arthur tried to sneak by Grendel, but was seen at melee range."


def test_describe_steal_renders_nothing_for_outcomes_with_no_sourced_template():
    for outcome in (None, "success", "evaded", "executed", "unresolved"):
        result = ChallengeExecutionResult(accepted=True, combat_occurred=True, steal_outcome=outcome)
        rng = ScriptedRandom([])  # any .random()/.choice() call here would raise

        line = describe_steal(result, thief_name="Aldric", victim_name="Borin", rng=rng)

        assert line is None


def test_describe_steal_renders_nothing_when_combat_outcome_has_no_capture_range():
    # Defensive: `steal_capture_range` is only ever unset alongside
    # `steal_outcome == "combat"` if a caller builds the result by hand
    # (never happens via `resolve_challenge_combat()` itself) -- no crash,
    # no guessed range.
    result = ChallengeExecutionResult(accepted=True, combat_occurred=True, steal_outcome="combat")
    rng = ScriptedRandom([])

    line = describe_steal(result, thief_name="Aldric", victim_name="Borin", rng=rng)

    assert line is None


def test_describe_steal_also_accepts_a_pursue_execution_result():
    # `PursueExecutionResult` shares the same field names (Phase 306) --
    # this composer reads them structurally, no isinstance check.
    result = PursueExecutionResult(caught_up=True, combat_occurred=True, steal_outcome="ransom")
    rng = ScriptedRandom([0.1] * 10)

    line = describe_steal(result, thief_name="Aldric", victim_name="Borin", rng=rng)

    assert line is not None
    assert "Aldric" in line and "Borin" in line


# -- describe_steal STEAL-family narration (Phase 777, backlog #19) --------


def _state_with_items(*treasures: Treasure) -> tuple[GameState, list[int]]:
    state = GameState()
    item_ids = []
    for i, treasure in enumerate(treasures):
        item = state.add_item(treasure, owner_leader_id=None)
        item_ids.append(item.item_id)
    return state, item_ids


def test_describe_steal_success_with_one_item_renders_the_treasure_theft_line():
    state, item_ids = _state_with_items(Treasure.ABILITY_TACTICAL)
    result = ChallengeExecutionResult(accepted=True, combat_occurred=True, steal_outcome="success", stolen_item_ids=item_ids)
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])

    line = describe_steal(result, thief_name="Aldric", victim_name="Borin", rng=rng, state=state)

    assert line == "Aldric caressed the treasure fondly."


def test_describe_steal_success_with_two_items_renders_the_group_theft_line():
    state, item_ids = _state_with_items(Treasure.ABILITY_TACTICAL, Treasure.ABILITY_MELEE)
    result = ChallengeExecutionResult(accepted=True, combat_occurred=True, steal_outcome="success", stolen_item_ids=item_ids)
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])

    line = describe_steal(result, thief_name="Aldric", victim_name="Borin", rng=rng, state=state)

    assert line is not None
    assert line.startswith("with hands as soft as a zephyr, Aldric carefully pilfered the ")
    assert TREASURE_NAME[Treasure.ABILITY_TACTICAL] in line
    assert TREASURE_NAME[Treasure.ABILITY_MELEE] in line


def test_describe_steal_success_with_no_stolen_items_renders_nothing():
    result = ChallengeExecutionResult(accepted=True, combat_occurred=True, steal_outcome="success", stolen_item_ids=[])
    rng = ScriptedRandom([])

    assert describe_steal(result, thief_name="Aldric", victim_name="Borin", rng=rng) is None


def test_describe_steal_success_with_no_state_renders_nothing():
    # A real caller always threads `state`, but the defensive fallback
    # (no data, no guess) should never crash or guess names either.
    result = ChallengeExecutionResult(accepted=True, combat_occurred=True, steal_outcome="success", stolen_item_ids=[7])
    rng = ScriptedRandom([])

    assert describe_steal(result, thief_name="Aldric", victim_name="Borin", rng=rng, state=None) is None


# -- describe_encounter_combat / describe_challenge (Phase 417) -------------


def test_describe_encounter_combat_narrates_a_fizzled_cast_before_fire_arrow_and_melee():
    # Phase 858: SBUNGLE.X's own real "personal-combat Cast that just
    # fizzles" text -- see ChallengeCombatOutcome.fizzled_spells's own
    # docstring for the real, sourced trigger and the placement choice.
    result = ChallengeExecutionResult(
        accepted=True,
        combat_occurred=True,
        fizzled_spells=(("Aldric", Spell.FIREBALL),),
        fire_arrow_shots=(FireArrowShot(shooter="a", hit=True, damage=5),),
    )
    rng = ScriptedRandom([0.1] * 30, choice_indices=[0, 0, 0])

    lines = describe_encounter_combat(result, a_leader_id=1, a_name="Aldric", b_name="Borin", rng=rng)

    assert lines[0] == "Aldric attempted to bolster Aldric's fortunes with a Fireball spell, but it fizzled at the last moment."
    assert lines[1] == "Aldric Fired an arrow at Borin and inflicted 5 damage points."


def test_describe_encounter_combat_omits_fizzled_spells_line_when_none_fizzled():
    result = ChallengeExecutionResult(
        accepted=True,
        combat_occurred=True,
        fire_arrow_shots=(FireArrowShot(shooter="a", hit=True, damage=5),),
    )
    rng = ScriptedRandom([0.1] * 30, choice_indices=[0, 0])

    lines = describe_encounter_combat(result, a_leader_id=1, a_name="Aldric", b_name="Borin", rng=rng)

    assert lines == ["Aldric Fired an arrow at Borin and inflicted 5 damage points."]


def test_describe_encounter_combat_narrates_fire_arrow_shots_and_melee_swings_in_order():
    result = ChallengeExecutionResult(
        accepted=True,
        combat_occurred=True,
        fire_arrow_shots=(FireArrowShot(shooter="a", hit=True, damage=5),),
        melee_swings=(MeleeSwing(attacker="b", hit=False, damage=0),),
    )
    rng = ScriptedRandom([0.1] * 30, choice_indices=[0, 0, 8, 0])

    lines = describe_encounter_combat(result, a_leader_id=1, a_name="Aldric", b_name="Borin", rng=rng)

    assert lines == [
        "Aldric Fired an arrow at Borin and inflicted 5 damage points.",
        "Borin Attacked Aldric and missed.",
    ]


def test_describe_encounter_combat_narrates_a_shadow_sword_proc_after_its_own_swing():
    # Phase 740: the proc line follows the swing's own attack line
    # immediately, for whichever side actually wields the weapon.
    result = ChallengeExecutionResult(
        accepted=True,
        combat_occurred=True,
        melee_swings=(MeleeSwing(attacker="a", hit=True, damage=5, weapon_proc="shadow_sword_drain", weapon_proc_hit_points=8),),
    )
    rng = ScriptedRandom([0.1] * 30, choice_indices=[0, 0, 0])

    lines = describe_encounter_combat(result, a_leader_id=1, a_name="Aldric", b_name="Borin", rng=rng)

    assert lines == [
        "Aldric assailed Borin and inflicted 5 damage points.",
        "the Shadow Sword transferred the life energy to Aldric and Aldric's hit points rose to 8.",
    ]


def test_describe_encounter_combat_narrates_the_mortal_wound_line_for_the_loser():
    result = ChallengeExecutionResult(
        accepted=True,
        combat_occurred=True,
        winner_leader_id=1,
        loser_leader_id=2,
        loser_killed=True,
    )
    # Phase 611: HORDEATH.X's own generic closing beat now follows the
    # MORTWOUN.X sentence -- variant 0 of each (mortally-wounded has no
    # further /R alternation of its own; HORDEATH's own "/R" is padded).
    # Phase 859: THATT.X/THFAIL.X (variant 0 each) now follow, since no
    # items were looted.
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0, 0, 0, 0])

    lines = describe_encounter_combat(result, a_leader_id=1, a_name="Aldric", b_name="Borin", rng=rng)

    assert lines == [
        "Borin was mortally wounded.",
        "and so it was that Borin met Borin's unseemly end.",
        "Aldric crept up on Borin's treasure, hoping to steal a great treasure.",
        "but after searching for an hour, Aldric failed to find any treasure.",
    ]


def test_describe_encounter_combat_narrates_the_spoils_line_with_one_looted_item():
    state, item_ids = _state_with_items(Treasure.ABILITY_TACTICAL)
    result = ChallengeExecutionResult(
        accepted=True,
        combat_occurred=True,
        winner_leader_id=1,
        loser_leader_id=2,
        loser_killed=True,
        looted_item_ids=item_ids,
    )
    # Phase 859: one more choice_indices entry for THATT.X, now rendered
    # unconditionally right before the SPOILS line.
    rng = ScriptedRandom([0.1] * 20, choice_indices=[0, 0, 0, 0])

    lines = describe_encounter_combat(result, a_leader_id=1, a_name="Aldric", b_name="Borin", rng=rng, state=state)

    assert lines == [
        "Borin was mortally wounded.",
        "and so it was that Borin met Borin's unseemly end.",
        "Aldric crept up on Borin's treasure, hoping to steal a great treasure.",
        "Aldric looked with satisfaction at the remains of Borin.",
    ]


def test_describe_encounter_combat_narrates_the_spoils_line_with_two_looted_items_and_threads_is_sea():
    for is_sea, verb in ((False, "walked"), (True, "swam")):
        state, item_ids = _state_with_items(Treasure.ABILITY_TACTICAL, Treasure.ABILITY_MELEE)
        result = ChallengeExecutionResult(
            accepted=True,
            combat_occurred=True,
            winner_leader_id=1,
            loser_leader_id=2,
            loser_killed=True,
            looted_item_ids=item_ids,
        )
        # Phase 859: one more choice_indices entry for THATT.X, now
        # rendered unconditionally right before the SPOILS line (shifting
        # it from index 2 to index 3).
        rng = ScriptedRandom([0.9] * 20, choice_indices=[0, 0, 0, 0])

        lines = describe_encounter_combat(
            result, a_leader_id=1, a_name="Aldric", b_name="Borin", rng=rng, state=state, is_sea=is_sea
        )

        assert lines[3] == f"Aldric {verb} over to a mound of treasure and secured the Standard of Command and Bracelets of Swordsmanship."


def test_describe_encounter_combat_narrates_thatt_then_thfail_when_nothing_was_looted():
    # Phase 859: renamed from "omits the spoils line" -- the SPOILS line
    # itself is still correctly absent, but THATT.X/THFAIL.X (the real
    # "searched the body, found nothing" pair) now render in its place,
    # rather than nothing at all.
    result = ChallengeExecutionResult(
        accepted=True,
        combat_occurred=True,
        winner_leader_id=1,
        loser_leader_id=2,
        loser_killed=True,
        looted_item_ids=[],
    )
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0, 0, 0, 0])

    lines = describe_encounter_combat(result, a_leader_id=1, a_name="Aldric", b_name="Borin", rng=rng)

    assert lines == [
        "Borin was mortally wounded.",
        "and so it was that Borin met Borin's unseemly end.",
        "Aldric crept up on Borin's treasure, hoping to steal a great treasure.",
        "but after searching for an hour, Aldric failed to find any treasure.",
    ]


def test_describe_encounter_combat_omits_the_spoils_line_when_the_loser_wasnt_killed():
    # Should never happen in real dispatch (looted_item_ids is only ever
    # populated alongside loser_killed=True), but proves the gate is
    # real, not accidental.
    state, item_ids = _state_with_items(Treasure.ABILITY_TACTICAL)
    result = ChallengeExecutionResult(
        accepted=True,
        combat_occurred=True,
        loser_killed=False,
        looted_item_ids=item_ids,
    )
    rng = ScriptedRandom([])

    assert describe_encounter_combat(result, a_leader_id=1, a_name="Aldric", b_name="Borin", rng=rng, state=state) == []


def test_describe_encounter_combat_renders_thatt_but_not_thfail_when_items_are_unresolvable():
    # Phase 859: looted_item_ids is genuinely non-empty here, but no
    # state is supplied to resolve their names -- THATT.X still renders
    # (it needs no state), but THFAIL.X must NOT render, since "found
    # nothing" would be a real, wrong guess about what actually happened.
    result = ChallengeExecutionResult(
        accepted=True,
        combat_occurred=True,
        winner_leader_id=1,
        loser_leader_id=2,
        loser_killed=True,
        looted_item_ids=[999],
    )
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0, 0, 0])

    lines = describe_encounter_combat(result, a_leader_id=1, a_name="Aldric", b_name="Borin", rng=rng)

    assert lines == [
        "Borin was mortally wounded.",
        "and so it was that Borin met Borin's unseemly end.",
        "Aldric crept up on Borin's treasure, hoping to steal a great treasure.",
    ]


def test_describe_encounter_combat_narrates_the_steal_line_first():
    result = ChallengeExecutionResult(accepted=True, combat_occurred=True, steal_outcome="ransom")
    rng = ScriptedRandom([0.1] * 10)

    lines = describe_encounter_combat(result, a_leader_id=1, a_name="Aldric", b_name="Borin", rng=rng)

    assert len(lines) == 1
    assert "Aldric" in lines[0] and "Borin" in lines[0] and "ransom" in lines[0]


def test_describe_encounter_combat_returns_empty_when_no_combat_occurred():
    result = ChallengeExecutionResult(accepted=False, reason="encounter refused")
    rng = ScriptedRandom([])

    assert describe_encounter_combat(result, a_leader_id=1, a_name="Aldric", b_name="Borin", rng=rng) == []


def test_describe_encounter_combat_returns_empty_for_a_peaceful_accepted_plan():
    result = ChallengeExecutionResult(accepted=True, combat_occurred=False)
    rng = ScriptedRandom([])

    assert describe_encounter_combat(result, a_leader_id=1, a_name="Aldric", b_name="Borin", rng=rng) == []


# -- Phase 733: describe_patrol_combat() --


def test_describe_patrol_combat_returns_empty_when_no_combat_occurred():
    result = PatrolExecutionResult(intercepted=False, reason="wandered into a random hex")
    rng = ScriptedRandom([])

    assert describe_patrol_combat(result, a_leader_id=1, a_name="Aldric", b_name="Borin", rng=rng) == []


def test_describe_patrol_combat_returns_empty_for_a_peaceful_accepted_encounter():
    result = PatrolExecutionResult(intercepted=True, target_leader_id=2, combat_occurred=False)
    rng = ScriptedRandom([])

    assert describe_patrol_combat(result, a_leader_id=1, a_name="Aldric", b_name="Borin", rng=rng) == []


def test_describe_patrol_combat_narrates_melee_swings_in_order():
    result = PatrolExecutionResult(
        intercepted=True,
        target_leader_id=2,
        combat_occurred=True,
        melee_swings=(MeleeSwing(attacker="a", hit=True, damage=5), MeleeSwing(attacker="b", hit=False, damage=0)),
    )
    rng = ScriptedRandom([0.1] * 40, choice_indices=[0] * 10)

    lines = describe_patrol_combat(result, a_leader_id=1, a_name="Aldric", b_name="Borin", rng=rng)

    assert lines == [
        "Aldric assailed Borin and inflicted 5 damage points.",
        "Borin assailed Aldric and missed.",
    ]


def test_describe_patrol_combat_narrates_the_mortal_wound_line_for_the_loser():
    result = PatrolExecutionResult(
        intercepted=True,
        target_leader_id=2,
        combat_occurred=True,
        winner_leader_id=1,
        loser_leader_id=2,
        loser_killed=True,
    )
    # Phase 859: THATT.X/THFAIL.X (variant 0 each) now follow, since no
    # items were looted.
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0, 0, 0, 0])

    lines = describe_patrol_combat(result, a_leader_id=1, a_name="Aldric", b_name="Borin", rng=rng)

    assert lines == [
        "Borin was mortally wounded.",
        "and so it was that Borin met Borin's unseemly end.",
        "Aldric crept up on Borin's treasure, hoping to steal a great treasure.",
        "but after searching for an hour, Aldric failed to find any treasure.",
    ]


def test_describe_patrol_combat_narrates_the_spoils_line_with_one_looted_item():
    # Phase 836: PatrolExecutionResult.looted_item_ids (Phase 313) was
    # populated by execute_patrol() from day one but never read here --
    # the SPOILS line describe_encounter_combat() already renders for
    # the identical Challenge/Pursue situation was silently missing.
    state, item_ids = _state_with_items(Treasure.ABILITY_TACTICAL)
    result = PatrolExecutionResult(
        intercepted=True,
        target_leader_id=2,
        combat_occurred=True,
        winner_leader_id=1,
        loser_leader_id=2,
        loser_killed=True,
        looted_item_ids=item_ids,
    )
    # Phase 859: one more choice_indices entry for THATT.X.
    rng = ScriptedRandom([0.1] * 20, choice_indices=[0, 0, 0, 0])

    lines = describe_patrol_combat(result, a_leader_id=1, a_name="Aldric", b_name="Borin", rng=rng, state=state)

    assert lines == [
        "Borin was mortally wounded.",
        "and so it was that Borin met Borin's unseemly end.",
        "Aldric crept up on Borin's treasure, hoping to steal a great treasure.",
        "Aldric looked with satisfaction at the remains of Borin.",
    ]


def test_describe_patrol_combat_narrates_the_spoils_line_when_the_patroller_is_the_loser():
    # The winner isn't always "a" -- an intruder can win the duel and
    # loot the patroller. Proves winner_name resolution, not just the
    # a_leader_id-is-always-the-winner shortcut.
    state, item_ids = _state_with_items(Treasure.ABILITY_TACTICAL)
    result = PatrolExecutionResult(
        intercepted=True,
        target_leader_id=2,
        combat_occurred=True,
        winner_leader_id=2,
        loser_leader_id=1,
        loser_killed=True,
        looted_item_ids=item_ids,
    )
    # Phase 859: one more choice_indices entry for THATT.X.
    rng = ScriptedRandom([0.1] * 20, choice_indices=[0, 0, 0, 0])

    lines = describe_patrol_combat(result, a_leader_id=1, a_name="Aldric", b_name="Borin", rng=rng, state=state)

    assert lines == [
        "Aldric was mortally wounded.",
        "and so it was that Aldric met Aldric's unseemly end.",
        "Borin crept up on Aldric's treasure, hoping to steal a great treasure.",
        "Borin looked with satisfaction at the remains of Aldric.",
    ]


def test_describe_patrol_combat_omits_the_spoils_line_without_state():
    # Same "no data, no guess" fallback _item_display_names() itself
    # already documents -- non-regression for every existing caller
    # that never threads state through. THATT.X (Phase 859) still
    # renders unconditionally (it needs no state), but neither the
    # SPOILS line nor THFAIL.X follows -- looted_item_ids is genuinely
    # non-empty here, so "found nothing" would be a real, wrong guess.
    result = PatrolExecutionResult(
        intercepted=True,
        target_leader_id=2,
        combat_occurred=True,
        winner_leader_id=1,
        loser_leader_id=2,
        loser_killed=True,
        looted_item_ids=[999],
    )
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0, 0, 0])

    lines = describe_patrol_combat(result, a_leader_id=1, a_name="Aldric", b_name="Borin", rng=rng)

    assert lines == [
        "Borin was mortally wounded.",
        "and so it was that Borin met Borin's unseemly end.",
        "Aldric crept up on Borin's treasure, hoping to steal a great treasure.",
    ]


def test_describe_turn_results_narrates_a_patrol_interception_sentinel():
    state = GameState()
    location = HexCoord(0, 0)
    state.add_kingdom(KingdomState(1, "Kingdom A", Race.HUMAN, Alignment.NEUTRAL, location))
    state.add_kingdom(KingdomState(2, "Kingdom B", Race.HUMAN, Alignment.NEUTRAL, location))
    state.add_leader(LeaderState(1, kingdom_id=1, name="Patroller", location=location))
    state.add_leader(LeaderState(2, kingdom_id=2, name="Intruder", location=location))
    result = PatrolExecutionResult(
        intercepted=True,
        target_leader_id=2,
        combat_occurred=True,
        winner_leader_id=1,
        loser_leader_id=2,
        loser_killed=True,
        melee_swings=(MeleeSwing(attacker="a", hit=True, damage=6),),
    )
    entries = [
        PhaseDispatchResult(leader_id=1, segment_index=-1, phase_label="P0", action=ActionCode.PURSUE, result=result, error=None)
    ]

    # Phase 859: two more choice_indices entries for THATT.X/THFAIL.X.
    lines = describe_turn_results(entries, state, ScriptedRandom([0.1] * 20, choice_indices=[0, 0, 0, 0, 0, 0]))

    assert "Patroller assailed Intruder and inflicted 6 damage points." in lines
    assert "and so it was that Intruder met Intruder's unseemly end." in lines


# -- Phase 709: random-encounter report narration --

_RANDOM_ENCOUNTER_HOME = HexCoord(5, 4)


def _random_encounter_state(*, owner_kingdom_id: int | None = 1) -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Homeland", Race.HUMAN, Alignment.GOOD, _RANDOM_ENCOUNTER_HOME))
    state.add_province(ProvinceState(_RANDOM_ENCOUNTER_HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=owner_kingdom_id))
    state.add_leader(LeaderState(2, kingdom_id=1, name="King Harold", location=_RANDOM_ENCOUNTER_HOME, is_king=True))
    return state


def test_render_random_encounter_failure():
    rng = ScriptedRandom([0.1] * 10)
    assert render_random_encounter_failure("Arthur", rng) == "Arthur saw no wandering monster."


def test_render_random_encounter_failure_other_branch():
    rng = ScriptedRandom([0.9] * 10)
    assert render_random_encounter_failure("Arthur", rng) == "while adventuring, Arthur encountered no marauding monsters."


def test_render_random_encounter_intro_land():
    rng = ScriptedRandom([0.1] * 10)
    assert render_random_encounter_intro("Arthur", rng) == "during Arthur's travels, "


def test_render_random_encounter_intro_sea():
    rng = ScriptedRandom([0.1] * 10)
    assert render_random_encounter_intro("Arthur", rng, is_sea=True) == "during Arthur's coastal explorations, "


def test_describe_random_encounter_combat_returns_empty_when_no_combat_occurred():
    result = RandomEncounterResult(1, _RANDOM_ENCOUNTER_HOME, terrain_roll_succeeded=True)
    rng = ScriptedRandom([])

    assert describe_random_encounter_combat(result, character_name="Arthur", opponent_name="Grendel", rng=rng) == []


def test_describe_random_encounter_combat_narrates_fire_arrow_shots_and_melee_swings_in_order():
    result = RandomEncounterResult(
        1,
        _RANDOM_ENCOUNTER_HOME,
        terrain_roll_succeeded=True,
        combat_occurred=True,
        fire_arrow_shots=(FireArrowShot(shooter="a", hit=True, damage=5),),
        melee_swings=(MeleeSwing(attacker="b", hit=False, damage=0),),
    )
    rng = ScriptedRandom([0.1] * 30, choice_indices=[0, 0, 8, 0])

    lines = describe_random_encounter_combat(result, character_name="Arthur", opponent_name="Grendel", rng=rng)

    assert lines == [
        "Arthur Fired an arrow at Grendel and inflicted 5 damage points.",
        "Grendel Attacked Arthur and missed.",
    ]


def test_describe_random_encounter_combat_narrates_the_characters_own_death():
    result = RandomEncounterResult(1, _RANDOM_ENCOUNTER_HOME, terrain_roll_succeeded=True, combat_occurred=True, leader_died=True)
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0, 0])

    lines = describe_random_encounter_combat(result, character_name="Arthur", opponent_name="Grendel", rng=rng)

    assert lines == [
        "Arthur was mortally wounded.",
        "and so it was that Arthur met Arthur's unseemly end.",
    ]


def test_describe_random_encounter_failed_terrain_roll():
    state = _random_encounter_state()
    result = RandomEncounterResult(1, _RANDOM_ENCOUNTER_HOME, terrain_roll_succeeded=False)
    rng = ScriptedRandom([0.1] * 10)

    assert describe_random_encounter(result, state, "Arthur", rng) == ["Arthur saw no wandering monster."]


def test_describe_random_encounter_wandering_sense_danger_evasion_has_no_resolution_sentence():
    state = _random_encounter_state()
    result = RandomEncounterResult(
        1, _RANDOM_ENCOUNTER_HOME, terrain_roll_succeeded=True, monster=Monster.GIANT, is_patrol=False, evaded_via_sense_danger=True
    )
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])

    lines = describe_random_encounter(result, state, "Arthur", rng)

    assert lines == ["during Arthur's travels, Arthur was crossing an open field when Giant spotted Arthur from a distance."]


def test_describe_random_encounter_wandering_combat_uses_the_real_species_name():
    state = _random_encounter_state()
    result = RandomEncounterResult(
        1,
        _RANDOM_ENCOUNTER_HOME,
        terrain_roll_succeeded=True,
        monster=Monster.GIANT,
        is_patrol=False,
        combat_occurred=True,
        melee_swings=(MeleeSwing(attacker="b", hit=True, damage=4),),
    )
    rng = ScriptedRandom([0.1] * 30, choice_indices=[0, 0, 0])

    lines = describe_random_encounter(result, state, "Arthur", rng)

    assert lines[0] == "during Arthur's travels, Arthur was crossing an open field when Giant spotted Arthur from a distance."
    assert "Giant" in lines[1]
    assert "Officer" not in lines[1]


def test_describe_random_encounter_patrol_diplomatic_evasion_appends_the_release_line():
    state = _random_encounter_state()
    result = RandomEncounterResult(
        1, _RANDOM_ENCOUNTER_HOME, terrain_roll_succeeded=True, monster=Monster.GIANT, is_patrol=True, evaded_via_diplomacy=True
    )
    rng = ScriptedRandom([0.1] * 20, choice_indices=[0, 0])

    lines = describe_random_encounter(result, state, "Arthur", rng)

    assert lines == [
        "during Arthur's travels, Arthur was ambushed, tied up and severely beaten by wild-eyed "
        "soldiers.Arthur escaped.a King's Ranger tracked Arthur down.",
        "but when Arthur was taken to the judge, Arthur showed him the official seal of King Harold, and was let go.",
    ]


def test_describe_random_encounter_patrol_evasion_never_appends_combat_lines():
    state = _random_encounter_state()
    result = RandomEncounterResult(
        1,
        _RANDOM_ENCOUNTER_HOME,
        terrain_roll_succeeded=True,
        monster=Monster.GIANT,
        is_patrol=True,
        evaded_via_diplomacy=True,
        combat_occurred=True,
        melee_swings=(MeleeSwing(attacker="b", hit=True, damage=4),),
    )
    rng = ScriptedRandom([0.1] * 20, choice_indices=[0, 0])

    lines = describe_random_encounter(result, state, "Arthur", rng)

    assert len(lines) == 2


def test_describe_random_encounter_patrol_combat_masks_the_species_as_the_officer():
    state = _random_encounter_state()
    result = RandomEncounterResult(
        1,
        _RANDOM_ENCOUNTER_HOME,
        terrain_roll_succeeded=True,
        monster=Monster.GIANT,
        is_patrol=True,
        combat_occurred=True,
        melee_swings=(MeleeSwing(attacker="b", hit=True, damage=4),),
    )
    rng = ScriptedRandom([0.1] * 30, choice_indices=[0, 0, 0, 0])

    lines = describe_random_encounter(result, state, "Arthur", rng)

    assert "the Officer" in lines[1]
    assert "Giant" not in lines[1]


def test_describe_random_encounter_patrol_falls_back_to_a_generic_king_name_for_an_unowned_province():
    state = _random_encounter_state(owner_kingdom_id=None)
    result = RandomEncounterResult(
        1, _RANDOM_ENCOUNTER_HOME, terrain_roll_succeeded=True, monster=Monster.GIANT, is_patrol=True, evaded_via_diplomacy=True
    )
    rng = ScriptedRandom([0.1] * 20, choice_indices=[0, 0])

    lines = describe_random_encounter(result, state, "Arthur", rng)

    assert "the local authorities" in lines[1]


def test_describe_turn_results_narrates_a_random_encounter_sentinel():
    state = _random_encounter_state()
    result = RandomEncounterResult(1, _RANDOM_ENCOUNTER_HOME, terrain_roll_succeeded=False)
    state.add_leader(LeaderState(1, kingdom_id=1, name="Arthur", location=_RANDOM_ENCOUNTER_HOME))
    entries = [PhaseDispatchResult(leader_id=1, segment_index=-1, phase_label="P0", action=None, result=result, error=None)]
    rng = ScriptedRandom([0.1] * 10)

    lines = describe_turn_results(entries, state, rng)

    assert lines == ["Arthur saw no wandering monster."]


def test_describe_turn_results_narrates_an_illegal_move_from_contested():
    # Phase 718: describe_turn_results() narrates the one real exception
    # type it recognizes -- SAY.PAS code 32501's own generic prefix.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, HexCoord(0, 0)))
    state.add_leader(LeaderState(1, kingdom_id=1, name="Arthur", location=HexCoord(0, 0)))
    entries = [
        PhaseDispatchResult(
            leader_id=1,
            segment_index=0,
            phase_label="P0",
            action=ActionCode.LMOVE,
            result=None,
            error=IllegalMoveFromContestedError("illegal to move from a contested province to an adjacent enemy province"),
        )
    ]
    rng = ScriptedRandom([0.1] * 10)

    lines = describe_turn_results(entries, state, rng)

    assert lines == ["Arthur attempted an illegal move."]


def test_describe_turn_results_narrates_cargo_boarding_after_a_real_move():
    # Phase 736: describe_turn_results()'s own ActionCode.LMOVE branch
    # narrates both the MARCH.X move line and, when the move auto-
    # boarded any cargo, one boarding-notice line per boarded army.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_province(ProvinceState(HexCoord(3, 9), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, name="Numenor"))
    state.add_leader(LeaderState(1, kingdom_id=1, name="Arthur", location=HexCoord(3, 9)))
    state.add_army(ArmyState(10, 1, ArmyType.FLEET, Quality.AVERAGE, HexCoord(3, 9)))
    state.add_army(ArmyState(11, 1, ArmyType.BOWMEN, Quality.AVERAGE, HexCoord(3, 9), transported_by=10))
    result = MoveExecutionResult(
        moved=True, battle_report=None, exploration=None, movement_points_spent=1,
        new_location=HexCoord(3, 9), boarded_army_ids=[11],
    )
    entries = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.LMOVE, result=result, error=None)
    ]
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])

    lines = describe_turn_results(entries, state, rng, board_width=20)

    assert "Arthur boarded Bowmen aboard the Fleet." in lines


def test_describe_turn_results_narrates_a_recruit_by_a_leader_who_later_dies_this_same_turn():
    # Phase 827: a leader can successfully Recruit in an early phase (P0)
    # and then die in a LATER phase of the same turn (e.g. losing a
    # Challenge) -- the real, already-applied Recruit (a real new army
    # already exists in state.armies) must still be narrated. Previously
    # the RECRUIT branch resolved the province via a bare, alive-only
    # state.leaders.get(entry.leader_id), silently dropping the whole
    # narration once the acting leader was dead by report-generation time.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_province(ProvinceState(HexCoord(3, 9), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_leader(LeaderState(1, kingdom_id=1, name="Arthur", location=HexCoord(3, 9)))
    state.add_army(ArmyState(10, 1, ArmyType.BOWMEN, Quality.AVERAGE, HexCoord(3, 9)))
    unit = RecruitedUnit(army_id=10, army_type=ArmyType.BOWMEN, gold_paid=2)
    result = RecruitExecutionResult(
        request=RecruitRequest(leader_id=None, army_types=[ArmyType.BOWMEN]), recruited=[unit], total_gold_spent=2
    )
    entries = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.RECRUIT, result=result, error=None)
    ]
    state.remove_leader(1)  # died in a later phase this same turn

    lines = describe_turn_results(entries, state, ScriptedRandom([0.1] * 10, choice_indices=[0]))

    assert lines != []


def test_describe_turn_results_narrates_a_leave_by_a_leader_who_later_dies_this_same_turn():
    # Phase 827: same fix as Recruit above, for Leave.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_province(ProvinceState(HexCoord(3, 9), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_leader(LeaderState(1, kingdom_id=1, name="Arthur", location=HexCoord(3, 9)))
    state.add_army(ArmyState(10, 1, ArmyType.BOWMEN, Quality.AVERAGE, HexCoord(3, 9)))
    result = ArmyListExecutionResult(
        request=ArmyListRequest(target_leader_id=None, army_ids=[10]), succeeded=[10]
    )
    entries = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.LEAVE, result=result, error=None)
    ]
    state.remove_leader(1)  # died in a later phase this same turn

    lines = describe_turn_results(entries, state, ScriptedRandom([0.1] * 10, choice_indices=[0]))

    assert lines != []


def test_describe_turn_results_narrates_a_pick_up_by_a_leader_who_later_dies_this_same_turn():
    # Phase 827: same fix as Recruit above, for Pick_Up.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_province(ProvinceState(HexCoord(3, 9), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_leader(LeaderState(1, kingdom_id=1, name="Arthur", location=HexCoord(3, 9)))
    state.add_army(ArmyState(10, 1, ArmyType.BOWMEN, Quality.AVERAGE, HexCoord(3, 9)))
    result = ArmyListExecutionResult(
        request=ArmyListRequest(target_leader_id=1, army_ids=[10]), succeeded=[10]
    )
    entries = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.PICK_UP, result=result, error=None)
    ]
    state.remove_leader(1)  # died in a later phase this same turn

    lines = describe_turn_results(entries, state, ScriptedRandom([0.1] * 10, choice_indices=[0]))

    assert lines != []


def test_describe_turn_results_narrates_a_defend_by_a_leader_who_later_dies_this_same_turn():
    # Phase 827: same fix as Recruit above, for Defend. The real Defend
    # coverage area registers in turn/turn_processor.py's own active_
    # defends while the leader is still alive at THAT phase's dispatch
    # time, independent of whether they later die this same turn.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_province(ProvinceState(HexCoord(3, 9), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_leader(LeaderState(1, kingdom_id=1, name="Arthur", location=HexCoord(3, 9)))
    result = DefendRequest(target_province=0, unconfirmed_extra0=0)
    entries = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.DEFEND, result=result, error=None)
    ]
    state.remove_leader(1)  # died in a later phase this same turn

    lines = describe_turn_results(entries, state, ScriptedRandom([0.1] * 10, choice_indices=[0]))

    assert lines != []


def test_describe_turn_results_narrates_a_rumor_heard_by_a_leader_who_later_dies_this_same_turn():
    # Phase 835: a leader can hear a rumor in an early phase (e.g. a real
    # 20-30% roll on Explore/Move/Trail/etc., turn/rumor.py) and then die
    # in a LATER phase of the same turn (e.g. losing a Challenge) --
    # the already-generated rumor must still be narrated. The end-of-
    # function rumor block resolved the hearer via a bare, alive-only
    # state.leaders.get(leader_id), silently dropping the rumor once the
    # leader was dead by report-generation time.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_leader(LeaderState(1, kingdom_id=1, name="Aldric", location=HexCoord(9, 9)))
    state.add_feature(Feature(feature_id=5, coord=HexCoord(2, 2), kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    state.rumors[1] = Rumor(
        rumor_id=1,
        kingdom_id=1,
        leader_id=1,
        source_action=ActionCode.EXPLORE,
        content=RumorContent.FEATURE_AND_MONSTER,
        feature_id=5,
        is_true=True,
        described_coord=HexCoord(2, 2),
        described_monster=Monster.ARCHER,
    )
    entries = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.EXPLORE, result=None, error=None)
    ]
    state.remove_leader(1)  # died in a later phase this same turn

    lines = describe_turn_results(entries, state, ScriptedRandom([0.1] * 10, choice_indices=[0]), board_width=10)

    assert any("Archer" in line for line in lines)


def test_describe_turn_results_narrates_a_double_agent_report_sentinel():
    # Phase 729: AdvancedAbility.SPY_DOUBLE_AGENT's own end-of-turn
    # intel grant -- action=None, matched by phase_label alone, renders
    # identically to a real ActionCode.ASPY dispatch via the same
    # describe_aspy() composer.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_leader(LeaderState(20, kingdom_id=1, name="Aldric", location=HexCoord(0, 0)))
    report = SpyReport(province=HexCoord(0, 0), owner_kingdom_id=None)
    entries = [
        PhaseDispatchResult(
            leader_id=20, segment_index=-1, phase_label="double-agent-report", action=None, result=report, error=None
        )
    ]

    lines = describe_turn_results(entries, state, ScriptedRandom([0.1] * 20, choice_indices=[0]))

    expected = describe_aspy(
        report, spy_name="Aldric", province_name="(0, 0)", owner_name=None,
        adjacent_owner_names=[], rng=ScriptedRandom([0.1] * 20, choice_indices=[0]),
    )
    assert lines == expected


def test_describe_turn_results_narrates_a_successful_clairvoyance_cast():
    # Phase 831 bug fix: Spell.CLAIRVOYANCE was added to
    # render_cast_announcement()'s own _CAST_ANNOUNCEMENT_TARGET_SPELLS
    # (Phase 193), but _AUTO_RESOLVABLE_CAST_TARGET_SPELLS -- the sibling
    # set describe_turn_results()'s own CAST branch uses to decide which
    # spells' target it may safely auto-resolve -- was never updated to
    # match, so a successful Clairvoyance cast silently produced zero
    # turn-report lines.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_leader(LeaderState(1, kingdom_id=1, name="Sir Aldric", location=HexCoord(0, 0)))
    state.add_leader(LeaderState(2, kingdom_id=1, name="Borin", location=HexCoord(0, 0)))
    request = CastRequest(spell=Spell.CLAIRVOYANCE, target=2)
    result = CastExecutionResult(request=request, applied=True)
    entries = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.CAST, result=result, error=None)
    ]

    lines = describe_turn_results(entries, state, ScriptedRandom([0.1] * 10, choice_indices=[0]))

    assert lines != []
    assert "Sir Aldric" in lines[0]
    assert "Borin" in lines[0]


def test_describe_turn_results_narrates_a_successful_locate_object_cast():
    # Phase 878: Locate Object's own target is an item id, not a leader
    # id -- confirms describe_turn_results()'s own new, dedicated branch
    # reaches describe_locate_object() instead of trying (and failing) to
    # resolve the item id as a leader name via _AUTO_RESOLVABLE_CAST_
    # TARGET_SPELLS' own shared resolution path.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_leader(LeaderState(1, kingdom_id=1, name="Sir Aldric", location=HexCoord(0, 0)))
    state.add_leader(LeaderState(2, kingdom_id=1, name="Borin", location=HexCoord(0, 0)))
    state.add_province(ProvinceState(HexCoord(0, 0), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, name="Capital City"))
    item = state.add_item(Treasure.WAND_FIREBALL, owner_leader_id=2)
    request = CastRequest(spell=Spell.LOCATE_OBJECT, target=item.item_id)
    result = CastExecutionResult(
        request=request, applied=True, located_object=LocateObjectResult(location=HexCoord(0, 0), holder_leader_id=2)
    )
    entries = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.CAST, result=result, error=None)
    ]

    lines = describe_turn_results(entries, state, ScriptedRandom([0.1]))

    assert lines == ["Sir Aldric divined that the Wand of Fire was located in Capital City, held by Borin."]


def test_describe_turn_results_narrates_a_successful_bless_cast():
    # Phase 935: Spell.BLESS is province-targeted, not leader-targeted --
    # this dedicated branch resolves province_name via decode_hex_number()/
    # _province_label() instead of _leader_name(), the one province-
    # targeted Cast spell wired into this dispatch loop so far. The
    # graveyard-cleanup companion sentence (also Phase 935) appends after
    # the base announcement.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_leader(LeaderState(1, kingdom_id=1, name="Sir Aldric", location=HexCoord(0, 0)))
    state.add_province(ProvinceState(HexCoord(0, 0), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, name="Sageleaf"))
    request = CastRequest(spell=Spell.BLESS, target=encode_hex_number(HexCoord(0, 0), board_width=10))
    result = CastExecutionResult(request=request, applied=True, bless_graveyard_cleared=[ArmyType.LEGION])
    entries = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.CAST, result=result, error=None)
    ]

    lines = describe_turn_results(entries, state, ScriptedRandom([]), board_width=10)

    assert lines == [
        "Sir Aldric cast a Bless spell.Sageleaf was magically blessed and prospered."
        "The skeletal remains of the Legion were Blessed and permanently destroyed."
    ]


def test_describe_turn_results_skips_a_bless_cast_without_board_width():
    # board_width is opt-in (same convention rumor narration already
    # established) -- a caller that doesn't supply one gets no Bless
    # narration at all, rather than a crash trying to decode its target.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_leader(LeaderState(1, kingdom_id=1, name="Sir Aldric", location=HexCoord(0, 0)))
    request = CastRequest(spell=Spell.BLESS, target=encode_hex_number(HexCoord(0, 0), board_width=10))
    result = CastExecutionResult(request=request, applied=True)
    entries = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.CAST, result=result, error=None)
    ]

    lines = describe_turn_results(entries, state, ScriptedRandom([]))

    assert lines == []


def test_describe_turn_results_narrates_a_successful_part_sea_cast():
    # Phase 941: Spell.PART_SEA is a third province-targeted Cast spell
    # wired into this dispatch loop, the simplest of the three -- no
    # companion sentence (Bless) or dedicated renderer (Tornado) needed,
    # just render_cast_announcement()'s own generic fallback. Real
    # fixture text (SE3__T5.K1: "In spring, I cast a Part Sea spell and
    # the waters of Mercia were magically parted.") confirms this exact
    # wording, opening clause included.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_leader(LeaderState(1, kingdom_id=1, name="Sir Aldric", location=HexCoord(0, 0)))
    state.add_province(ProvinceState(HexCoord(0, 0), Terrain.SEA, Race.NO_RACE, owner_kingdom_id=1, name="Mercia"))
    request = CastRequest(spell=Spell.PART_SEA, target=encode_hex_number(HexCoord(0, 0), board_width=10))
    result = CastExecutionResult(request=request, applied=True)
    entries = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.CAST, result=result, error=None)
    ]

    lines = describe_turn_results(entries, state, ScriptedRandom([]), board_width=10)

    assert lines == ["Sir Aldric cast a Part Sea spell and the waters of Mercia were magically parted."]


def test_describe_turn_results_skips_a_part_sea_cast_without_board_width():
    # Same opt-in board_width convention as Bless/Tornado above.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_leader(LeaderState(1, kingdom_id=1, name="Sir Aldric", location=HexCoord(0, 0)))
    request = CastRequest(spell=Spell.PART_SEA, target=encode_hex_number(HexCoord(0, 0), board_width=10))
    result = CastExecutionResult(request=request, applied=True)
    entries = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.CAST, result=result, error=None)
    ]

    lines = describe_turn_results(entries, state, ScriptedRandom([]))

    assert lines == []


def test_describe_turn_results_narrates_a_successful_earthquake_cast():
    # Phase 942: Spell.EARTHQUAKE is a fourth province-targeted Cast spell
    # wired into this dispatch loop, structurally identical to Part_Sea
    # above -- same generic render_cast_announcement() fallback, same
    # board_width gating. Inferred (not independently fixture-confirmed:
    # no successful real Earthquake cast survives) from Part_Sea's own
    # already-confirmed identical SAY.PAS dispatch shape (`_SQuake:
    # Sps(Earthquake,S_Comm)`, the same "_S*" group, same single-call
    # shape, as `_SPart: Sps(Part_Sea,S_Comm)`) -- see this dispatch
    # branch's own Phase 942 comment for the full derivation.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_leader(LeaderState(1, kingdom_id=1, name="Sir Aldric", location=HexCoord(0, 0)))
    state.add_province(ProvinceState(HexCoord(0, 0), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2, name="Limerick"))
    request = CastRequest(spell=Spell.EARTHQUAKE, target=encode_hex_number(HexCoord(0, 0), board_width=10))
    result = CastExecutionResult(request=request, applied=True)
    entries = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.CAST, result=result, error=None)
    ]

    lines = describe_turn_results(entries, state, ScriptedRandom([]), board_width=10)

    assert lines == ["Sir Aldric cast a Earthquake spell and Limerick was devastated by an earthquake!"]


def test_describe_turn_results_skips_an_earthquake_cast_without_board_width():
    # Same opt-in board_width convention as Bless/Tornado/Part_Sea above.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_leader(LeaderState(1, kingdom_id=1, name="Sir Aldric", location=HexCoord(0, 0)))
    request = CastRequest(spell=Spell.EARTHQUAKE, target=encode_hex_number(HexCoord(0, 0), board_width=10))
    result = CastExecutionResult(request=request, applied=True)
    entries = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.CAST, result=result, error=None)
    ]

    lines = describe_turn_results(entries, state, ScriptedRandom([]))

    assert lines == []


def test_describe_turn_results_narrates_a_successful_illus_terrain_cast():
    # Phase 943: Spell.ILLUS_TERRAIN is a fifth province-targeted Cast
    # spell wired into this dispatch loop -- needs two terrain names
    # (real, from province.terrain; fake, from request.terrain), unlike
    # Bless/Tornado/Earthquake/Part_Sea's province_name-only shape.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_leader(LeaderState(1, kingdom_id=1, name="Teleko", location=HexCoord(0, 0)))
    state.add_province(ProvinceState(HexCoord(0, 0), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, name="Kajaani"))
    request = CastRequest(
        spell=Spell.ILLUS_TERRAIN, target=encode_hex_number(HexCoord(0, 0), board_width=10), terrain=Terrain.MTNS
    )
    result = CastExecutionResult(request=request, applied=True)
    entries = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.CAST, result=result, error=None)
    ]

    lines = describe_turn_results(entries, state, ScriptedRandom([]), board_width=10)

    assert lines == [
        "Teleko cast a Illusory Terrain spell and the Plain terrain of Kajaani was magically made to appear as Mountain."
    ]


def test_describe_turn_results_skips_an_illus_terrain_cast_without_board_width():
    # Same opt-in board_width convention as Bless/Tornado/Part_Sea/
    # Earthquake above.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_leader(LeaderState(1, kingdom_id=1, name="Teleko", location=HexCoord(0, 0)))
    request = CastRequest(
        spell=Spell.ILLUS_TERRAIN, target=encode_hex_number(HexCoord(0, 0), board_width=10), terrain=Terrain.MTNS
    )
    result = CastExecutionResult(request=request, applied=True)
    entries = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.CAST, result=result, error=None)
    ]

    lines = describe_turn_results(entries, state, ScriptedRandom([]))

    assert lines == []


def test_describe_turn_results_skips_an_illus_terrain_cast_with_unknown_province():
    # Same "province not found" guard the other province-targeted
    # branches don't need a dedicated test for (their own describe_cast()
    # calls tolerate a missing province_name gracefully via _province_
    # label()'s own fallback) -- this branch needs its own real
    # ProvinceState to read the real terrain from, so an unknown coord
    # is skipped explicitly before ever calling describe_cast().
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_leader(LeaderState(1, kingdom_id=1, name="Teleko", location=HexCoord(0, 0)))
    request = CastRequest(
        spell=Spell.ILLUS_TERRAIN, target=encode_hex_number(HexCoord(0, 0), board_width=10), terrain=Terrain.MTNS
    )
    result = CastExecutionResult(request=request, applied=True)
    entries = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.CAST, result=result, error=None)
    ]

    lines = describe_turn_results(entries, state, ScriptedRandom([]), board_width=10)

    assert lines == []


def test_describe_turn_results_narrates_a_successful_plague_cast():
    # Phase 944: Spell.PLAGUE is a sixth province-targeted Cast spell
    # wired into this dispatch loop, the same board_width-gated shape as
    # Bless/Tornado/Earthquake/Part_Sea -- describe_cast()'s own
    # dedicated branch reads result.plague_destroyed directly.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_leader(LeaderState(1, kingdom_id=1, name="Alaric", location=HexCoord(0, 0)))
    state.add_province(ProvinceState(HexCoord(0, 0), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, name="Cascadia"))
    request = CastRequest(spell=Spell.PLAGUE, target=encode_hex_number(HexCoord(0, 0), board_width=10))
    destroyed = [ArmyState(55, 2, ArmyType.GARRISON, Quality.AVERAGE, HexCoord(0, 0))]
    result = CastExecutionResult(request=request, applied=True, plague_destroyed=destroyed)
    entries = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.CAST, result=result, error=None)
    ]

    lines = describe_turn_results(entries, state, ScriptedRandom([]), board_width=10)

    assert lines == [
        "Alaric cast a Plague spell.Cascadia was hit by a plague."
        "The plague struck the 55th Garrison in Cascadia and destroyed them."
    ]


def test_describe_turn_results_skips_a_plague_cast_without_board_width():
    # Same opt-in board_width convention as the other province-targeted
    # Cast branches above.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_leader(LeaderState(1, kingdom_id=1, name="Alaric", location=HexCoord(0, 0)))
    request = CastRequest(spell=Spell.PLAGUE, target=encode_hex_number(HexCoord(0, 0), board_width=10))
    result = CastExecutionResult(request=request, applied=True)
    entries = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.CAST, result=result, error=None)
    ]

    lines = describe_turn_results(entries, state, ScriptedRandom([]))

    assert lines == []


def test_describe_turn_results_narrates_a_successful_flood_cast():
    # Phase 945: Spell.FLOOD is a seventh province-targeted Cast spell
    # wired into this dispatch loop, the simplest of all of them --
    # describe_cast()'s own dedicated branch needs only province_name.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_leader(LeaderState(1, kingdom_id=1, name="Clarambald", location=HexCoord(0, 0)))
    state.add_province(ProvinceState(HexCoord(0, 0), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, name="Ngara"))
    request = CastRequest(spell=Spell.FLOOD, target=encode_hex_number(HexCoord(0, 0), board_width=10))
    result = CastExecutionResult(request=request, applied=True)
    entries = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.CAST, result=result, error=None)
    ]

    lines = describe_turn_results(entries, state, ScriptedRandom([]), board_width=10)

    assert lines == ["Clarambald cast a Flood spell and Ngara was magically flooded."]


def test_describe_turn_results_skips_a_flood_cast_without_board_width():
    # Same opt-in board_width convention as the other province-targeted
    # Cast branches above.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_leader(LeaderState(1, kingdom_id=1, name="Clarambald", location=HexCoord(0, 0)))
    request = CastRequest(spell=Spell.FLOOD, target=encode_hex_number(HexCoord(0, 0), board_width=10))
    result = CastExecutionResult(request=request, applied=True)
    entries = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.CAST, result=result, error=None)
    ]

    lines = describe_turn_results(entries, state, ScriptedRandom([]))

    assert lines == []


def test_describe_turn_results_narrates_a_successful_hide_feature_cast():
    # Phase 946: Spell.HIDE_FEATURE is the eighth and last province-
    # targeted Cast spell wired here -- reads state.features_at(coord)
    # directly rather than a new CastExecutionResult field, since
    # _execute_hide_feature() itself never records which feature(s) it
    # hid. Only the single-feature case is wired (see this branch's own
    # Phase 946 comment for why the multi-feature case is a deliberate,
    # documented exception).
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_leader(LeaderState(1, kingdom_id=1, name="Aldric", location=HexCoord(0, 0)))
    state.add_province(ProvinceState(HexCoord(0, 0), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, name="Sageleaf"))
    state.add_feature(Feature(feature_id=1, coord=HexCoord(0, 0), kind=FeatureType.DUNGEON))
    request = CastRequest(spell=Spell.HIDE_FEATURE, target=encode_hex_number(HexCoord(0, 0), board_width=10))
    result = CastExecutionResult(request=request, applied=True)
    entries = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.CAST, result=result, error=None)
    ]

    lines = describe_turn_results(entries, state, ScriptedRandom([]), board_width=10)

    assert lines == ["Aldric cast a Hide Feature spell and the Dungeon in Sageleaf was magically hidden."]


def test_describe_turn_results_skips_a_hide_feature_cast_without_board_width():
    # Same opt-in board_width convention as the other province-targeted
    # Cast branches above.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_leader(LeaderState(1, kingdom_id=1, name="Aldric", location=HexCoord(0, 0)))
    state.add_feature(Feature(feature_id=1, coord=HexCoord(0, 0), kind=FeatureType.DUNGEON))
    request = CastRequest(spell=Spell.HIDE_FEATURE, target=encode_hex_number(HexCoord(0, 0), board_width=10))
    result = CastExecutionResult(request=request, applied=True)
    entries = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.CAST, result=result, error=None)
    ]

    lines = describe_turn_results(entries, state, ScriptedRandom([]))

    assert lines == []


def test_describe_turn_results_skips_a_hide_feature_cast_with_more_than_one_feature():
    # Phase 946: the deliberate, documented multi-feature exception --
    # no real fixture example of a successful Hide_Feature cast survives
    # to confirm the real grouping rule for more than one feature, so
    # this stays silently unwired rather than guessed at (the same
    # "no data to weigh a default against" reasoning this branch's own
    # comment gives, unlike Tornado/Plague's own resolved multi-army
    # ambiguity).
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_leader(LeaderState(1, kingdom_id=1, name="Aldric", location=HexCoord(0, 0)))
    state.add_province(ProvinceState(HexCoord(0, 0), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, name="Sageleaf"))
    state.add_feature(Feature(feature_id=1, coord=HexCoord(0, 0), kind=FeatureType.DUNGEON))
    state.add_feature(Feature(feature_id=2, coord=HexCoord(0, 0), kind=FeatureType.CAVE))
    request = CastRequest(spell=Spell.HIDE_FEATURE, target=encode_hex_number(HexCoord(0, 0), board_width=10))
    result = CastExecutionResult(request=request, applied=True)
    entries = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.CAST, result=result, error=None)
    ]

    lines = describe_turn_results(entries, state, ScriptedRandom([]), board_width=10)

    assert lines == []


def test_describe_turn_results_narrates_a_successful_skeletal_army_cast():
    # Phase 936: Spell.SKELETAL_ARMY is a NO_TARGET_SPELLS entry -- no
    # leader/province target to resolve, so no board_width needed either,
    # unlike Bless above.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_leader(LeaderState(1, kingdom_id=1, name="Sir Aldric", location=HexCoord(0, 0)))
    request = CastRequest(spell=Spell.SKELETAL_ARMY, target=0)
    raised = [ArmyState(1, 1, ArmyType.BOWMEN, Quality.AVERAGE, HexCoord(0, 0), is_skeletal=True)]
    result = CastExecutionResult(request=request, applied=True, skeletal_army_raised=raised)
    entries = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.CAST, result=result, error=None)
    ]

    lines = describe_turn_results(entries, state, ScriptedRandom([]))

    assert lines == ["Sir Aldric cast a Skeletal Army spell and the 1st Skeletal Bowmen arose from the graves of the dead!"]


def test_describe_turn_results_narrates_a_successful_tornado_cast():
    # Phase 937: Spell.TORNADO is province-targeted, resolved the same
    # board_width-gated way Bless already is.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_leader(LeaderState(1, kingdom_id=1, name="Sir Aldric", location=HexCoord(0, 0)))
    state.add_province(ProvinceState(HexCoord(0, 0), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2, name="Limerick"))
    request = CastRequest(spell=Spell.TORNADO, target=encode_hex_number(HexCoord(0, 0), board_width=10))
    destroyed = [ArmyState(20, 2, ArmyType.LEGION, Quality.AVERAGE, HexCoord(0, 0))]
    result = CastExecutionResult(request=request, applied=True, tornado_destroyed=destroyed)
    entries = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.CAST, result=result, error=None)
    ]

    lines = describe_turn_results(entries, state, ScriptedRandom([]), board_width=10)

    assert lines == [
        "Sir Aldric cast a Tornado spell.Magical tornadoes hit the defenders of Limerick."
        "Tornadoes sucked up the 20th Legion in Limerick and destroyed them."
    ]


def test_describe_turn_results_narrates_a_successful_charm_cast():
    # Phase 938: Spell.CHARM already flows through
    # _AUTO_RESOLVABLE_CAST_TARGET_SPELLS (leader-targeted) -- only
    # describe_cast()'s own dedicated branch changed, using the real
    # top-level-cast text instead of the Encounter-context one.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_leader(LeaderState(1, kingdom_id=1, name="Uga-Buga Makumb", location=HexCoord(0, 0)))
    state.add_leader(LeaderState(2, kingdom_id=1, name="Melantheus", location=HexCoord(0, 0)))
    request = CastRequest(spell=Spell.CHARM, target=2)
    result = CastExecutionResult(request=request, applied=True)
    entries = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.CAST, result=result, error=None)
    ]

    lines = describe_turn_results(entries, state, ScriptedRandom([]))

    assert lines == ["Melantheus was magically charmed by Uga-Buga Makumb."]


def test_describe_turn_results_still_ignores_an_unrelated_error():
    # Non-regression: every other exception (including this same
    # function's own "no province data" ValueError) still narrates
    # nothing, matching the pre-existing "silently skip" behavior.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, HexCoord(0, 0)))
    state.add_leader(LeaderState(1, kingdom_id=1, name="Arthur", location=HexCoord(0, 0)))
    entries = [
        PhaseDispatchResult(
            leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.LMOVE, result=None, error=ValueError("no province data for (9, 9)")
        )
    ]
    rng = ScriptedRandom([0.1] * 10)

    lines = describe_turn_results(entries, state, rng)

    assert lines == []


# -- ENCATT.X (Phase 597) --


def test_render_challenge_search_first_variant():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])
    result = render_challenge_search("Aldric", "Borin", "Mongu", rng)
    assert result == "Aldric searched throughout Mongu for Borin."


def test_render_challenge_search_first_variant_includes_optional_clauses():
    rng = ScriptedRandom([0.99] * 10, choice_indices=[0])
    result = render_challenge_search("Aldric", "Borin", "Mongu", rng)
    assert result == "Aldric searched all throughout Mongu for some sign of Borin."


def test_render_challenge_search_third_variant():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[2])
    result = render_challenge_search("Aldric", "Borin", "Mongu", rng)
    assert result == "Aldric searched for Borin in the bars and whorehouses of Mongu."


# -- SANOTE.X2 record 79, AdvancedAbility.SPY_ASSASSINATE (Phase 793) --


def test_render_assassinate_encounter_note_first_wording():
    rng = ScriptedRandom([0.1] * 10)
    result = render_assassinate_encounter_note("Aldric", "Borin", rng)
    assert result == "Using Aldric's special Spy ability of Assassination, Aldric got close to Borin, without being seen."


def test_render_assassinate_encounter_note_alternate_wording_includes_the_optional_clause():
    rng = ScriptedRandom([0.99] * 10)
    result = render_assassinate_encounter_note("Aldric", "Borin", rng)
    assert result == (
        "employing Aldric's advanced Spy technique of Assassination, Aldric stole up to Borin, "
        "not detected by any guards."
    )


# -- describe_challenge() -- Phase 793: ENCATT.X always opens, SANOTE.X2 --
# record 79 follows only when the encounter was accepted via Assassinate


def test_describe_challenge_encatt_line_opens_every_outcome():
    # A refused encounter still gets the ENCATT.X search line -- Desktop/
    # LCHALL.md confirms `_LChall` is written before every restriction
    # check that could refuse the encounter.
    refused = ChallengeExecutionResult(accepted=False, reason="encounter refused")
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])

    lines = describe_challenge(
        refused, challenger_leader_id=1, challenger_name="Aldric", target_name="Borin", province_name="Mongu", rng=rng
    )

    assert lines == ["Aldric searched throughout Mongu for Borin."]


def test_describe_challenge_encatt_line_opens_a_peaceful_encounter():
    peaceful = ChallengeExecutionResult(accepted=True, combat_occurred=False)
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])

    lines = describe_challenge(
        peaceful, challenger_leader_id=1, challenger_name="Aldric", target_name="Borin", province_name="Mongu", rng=rng
    )

    assert lines == ["Aldric searched throughout Mongu for Borin."]


def test_describe_challenge_assassinate_note_follows_the_search_line_when_used():
    result = ChallengeExecutionResult(accepted=True, combat_occurred=False, used_spy_assassinate=True)
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])

    lines = describe_challenge(
        result, challenger_leader_id=1, challenger_name="Aldric", target_name="Borin", province_name="Mongu", rng=rng
    )

    assert lines == [
        "Aldric searched throughout Mongu for Borin.",
        "Using Aldric's special Spy ability of Assassination, Aldric got close to Borin, without being seen.",
    ]


def test_describe_challenge_never_renders_the_assassinate_note_when_unused():
    result = ChallengeExecutionResult(accepted=True, combat_occurred=False, used_spy_assassinate=False)
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])

    lines = describe_challenge(
        result, challenger_leader_id=1, challenger_name="Aldric", target_name="Borin", province_name="Mongu", rng=rng
    )

    assert lines == ["Aldric searched throughout Mongu for Borin."]


# -- DECQ.X/INCQ.X (Phase 598) --


def test_render_army_quality_decreased_first_variant():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])
    result = render_army_quality_decreased("144th Legion", "Green", rng)
    assert result == "144th Legion was severely shaken during the battle and we must now rate it as a Green unit."


def test_render_army_quality_decreased_sixth_variant_has_no_article():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[5])
    result = render_army_quality_decreased("144th Legion", "Green", rng)
    assert result == "144th Legion was mauled in the battle and has fallen in stature to Green condition."


def test_render_army_quality_increased_first_variant():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])
    result = render_army_quality_increased("144th Legion", "Elite", rng)
    assert result == "144th Legion proved its mettle in the battle and we now rate it an Elite unit."


def test_render_army_quality_increased_second_variant_includes_optional_clause():
    rng = ScriptedRandom([0.99] * 10, choice_indices=[1])
    result = render_army_quality_increased("144th Legion", "Elite", rng)
    assert result == "144th Legion was greatly inspired by the exciting battle.We now designate it a proud Elite unit."


def test_render_army_quality_increased_fifth_variant_resolves_sea_marker():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[4])
    result = render_army_quality_increased("144th Legion", "Elite", rng, is_sea=True)
    assert result == (
        "the fun head-bashing by 144th Legion in the battle has raised "
        "the spirits of its sailors, and it has achieved Elite status."
    )


def test_describe_quality_changes_dispatches_decq_and_incq_by_comparing_old_and_new():
    # Phase 610: describe_quality_changes() is the composer that finally
    # wires QualityChange.old/.new into render_army_quality_decreased()/
    # _increased() -- army 10 dropped (ELITE -> VETERAN, DECQ.X), army 20
    # rose (GREEN -> AVERAGE, INCQ.X).
    report = BattleReport(
        battle_result=BattleResult(winner="attacker", columns=[]),
        conquered=False,
        quality_changes={
            10: QualityChange(old=Quality.ELITE, new=Quality.VETERAN),
            20: QualityChange(old=Quality.GREEN, new=Quality.AVERAGE),
        },
    )
    army_names = {10: "144th Legion", 20: "Guerin's Guard"}
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0, 0])

    lines = describe_quality_changes(report, army_names, rng)

    assert lines == [
        "144th Legion was severely shaken during the battle and we must now rate it as a Veteran unit.",
        "Guerin's Guard proved its mettle in the battle and we now rate it an Average unit.",
    ]


def test_describe_quality_changes_skips_unchanged_rolls_and_unnamed_armies():
    report = BattleReport(
        battle_result=BattleResult(winner="attacker", columns=[]),
        conquered=False,
        quality_changes={
            10: QualityChange(old=Quality.VETERAN, new=Quality.VETERAN),  # rolled back to the same Quality
            99: QualityChange(old=Quality.GREEN, new=Quality.AVERAGE),  # no entry in army_names
        },
    )
    lines = describe_quality_changes(report, {10: "144th Legion"}, ScriptedRandom([]))
    assert lines == []


# -- LDESERT.X (Phase 599) --


def test_render_hero_deserted_first_variant():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])
    result = render_hero_deserted("Aldric", "Borin", rng)
    assert result == "Aldric quit the service of Borin, grumbling about the lack of pay."


def test_render_hero_deserted_second_variant_includes_optional_clause():
    rng = ScriptedRandom([0.99] * 10, choice_indices=[1])
    result = render_hero_deserted("Aldric", "Borin", rng)
    assert result == "Aldric grew tired of fighting for Borin for no pay and submitted Aldric's resignation."


def test_render_hero_deserted_third_variant_resolves_article():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[2])
    result = render_hero_deserted("Aldric", "Borin", rng)
    assert result == "Aldric left Borin to find employment elsewhere, hoping to find a more consistent source of income."


def test_describe_desertions_one_line_per_deserted_leader():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.GOOD, HexCoord(0, 0)))
    state.add_leader(LeaderState(1, 1, "Borin", HexCoord(0, 0), is_king=True))
    state.add_leader(LeaderState(2, 1, "Aldric", HexCoord(0, 0)))
    state.add_leader(LeaderState(3, 1, "Cedric", HexCoord(0, 0)))
    result = MaintenanceResult(debited=0, deserted_leader_ids=[2, 3])

    rng = ScriptedRandom([0.1] * 10, choice_indices=[0, 0])
    lines = describe_desertions(result, state, king_name="Borin", rng=rng)

    assert lines == [
        "Aldric quit the service of Borin, grumbling about the lack of pay.",
        "Cedric quit the service of Borin, grumbling about the lack of pay.",
    ]


def test_describe_desertions_empty_when_no_desertions():
    state = GameState()
    result = MaintenanceResult(debited=0)
    rng = ScriptedRandom([])

    lines = describe_desertions(result, state, king_name="Borin", rng=rng)

    assert lines == []


# -- LHAIL.X/LREBUFF.X/LTALKOK.X (Phase 600) --


def test_render_hail_greeting_low_rng_excludes_optional_clause():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])
    result = render_hail_greeting("Aldric", "Borin", rng)
    assert result == "Aldric hailed Borin with words of greeting."


def test_render_hail_greeting_high_rng_includes_optional_clause():
    rng = ScriptedRandom([0.99] * 10, choice_indices=[0])
    result = render_hail_greeting("Aldric", "Borin", rng)
    assert result == "Aldric held forth a white handkerchief and shouted out to Borin with friendly words of greeting."


def test_render_talk_rebuffed_first_variant():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])
    result = render_talk_rebuffed("Aldric", "Borin", "Cedric", rng)
    assert result == "Aldric tried talking to Borin, but Borin's family holds a grudge against Cedric and does not want to associate with him."


def test_render_talk_rebuffed_third_variant():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[2])
    result = render_talk_rebuffed("Aldric", "Borin", "Cedric", rng)
    assert result == 'Aldric spoke kindly to Borin, but was rebuffed because, said Borin, "you and your ilk are a gang of SNAKES!"'


def test_render_talk_learned_hire_price_first_variant():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])
    result = render_talk_learned_hire_price("Aldric", "Borin", 42, rng)
    assert result == "Aldric talked to Borin and learned that Borin could be hired for 42 gold."


def test_render_talk_learned_hire_price_fourth_variant_keeps_the_real_double_space():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[3])
    result = render_talk_learned_hire_price("Aldric", "Borin", 42, rng)
    assert result == (
        "Aldric  found Borin in a tavern and had a few beers with Borin."
        "Borin told Aldric that it would be Borin's honor to serve "
        "Aldric at the price of 42 gold."
    )


# -- VALINT.X2 (Phase 606) --


def test_render_valhalla_visitor_rules_returns_the_nine_real_reachable_lines():
    rng = ScriptedRandom([])
    lines = render_valhalla_visitor_rules("Aldric", rng)
    assert len(lines) == 9
    assert lines[0] == "If Aldric searches a feature, any monetary treasure Aldric captures will be given to you."
    assert lines[-1] == "If no leader is available, the armies will be disbanded."


def test_render_valhalla_visitor_rules_resolves_possessive_marker():
    rng = ScriptedRandom([])
    lines = render_valhalla_visitor_rules("Aldric", rng)
    assert lines[2] == (
        "You can do anything you want with the magic item Aldric came "
        "with, but the item will leave at the end of Aldric's stay with you."
    )


# -- Phase 678: Valhalla visit announcement --


def test_render_valhalla_visit_announcement_substitutes_king_and_hero():
    rng = ScriptedRandom([])
    line = render_valhalla_visit_announcement("Aldric", "Quintilian", rng)
    assert line == (
        'Aldric was visited by a hero from Valhalla, named Quintilian!The characteristics '
        'for this great King from Game # are given in your "CHARACTERS" report.'
    )


def test_render_valhalla_visit_announcement_leaves_the_game_number_marker_literal():
    rng = ScriptedRandom([])
    line = render_valhalla_visit_announcement("Aldric", "Quintilian", rng)
    assert "Game #" in line


def _gate_angel_visit_sentinel(visitor: LeaderState) -> PhaseDispatchResult:
    return PhaseDispatchResult(
        leader_id=visitor.leader_id, segment_index=-1, phase_label="gate-angel-visit", action=None,
        result=visitor, error=None,
    )


def test_describe_valhalla_visit_announcement_renders_announcement_and_rules():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, HexCoord(0, 0)))
    state.add_leader(LeaderState(1, 1, "Aldric", HexCoord(0, 0), is_king=True))
    visitor = LeaderState(VALHALLA_VISITOR_LEADER_ID, 1, "Quintilian", HexCoord(0, 0))
    state.add_leader(visitor)
    results = [_gate_angel_visit_sentinel(visitor)]

    lines = describe_valhalla_visit_announcement(results, state, 1, ScriptedRandom([]))

    assert lines[0] == render_valhalla_visit_announcement("Aldric", "Quintilian", ScriptedRandom([]))
    assert lines[1:] == render_valhalla_visitor_rules("Quintilian", ScriptedRandom([]))


def test_describe_valhalla_visit_announcement_recognizes_the_ordinary_valhalla_visit_sentinel():
    # Phase 756: the automatic per-turn visit (independent of Gate Angel)
    # appends a "valhalla-visit" sentinel instead of "gate-angel-visit" --
    # this composer narrates it identically, no new template needed.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, HexCoord(0, 0)))
    state.add_leader(LeaderState(1, 1, "Aldric", HexCoord(0, 0), is_king=True))
    visitor = LeaderState(VALHALLA_VISITOR_LEADER_ID, 1, "Quintilian", HexCoord(0, 0))
    state.add_leader(visitor)
    results = [
        PhaseDispatchResult(
            leader_id=visitor.leader_id, segment_index=-1, phase_label="valhalla-visit", action=None,
            result=visitor, error=None,
        )
    ]

    lines = describe_valhalla_visit_announcement(results, state, 1, ScriptedRandom([]))

    assert lines[0] == render_valhalla_visit_announcement("Aldric", "Quintilian", ScriptedRandom([]))
    assert lines[1:] == render_valhalla_visitor_rules("Quintilian", ScriptedRandom([]))


def test_describe_valhalla_visit_announcement_ignores_a_different_kingdoms_visitor():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, HexCoord(0, 0)))
    state.add_kingdom(KingdomState(2, "Otherland", Race.HUMAN, Alignment.GOOD, HexCoord(1, 1)))
    state.add_leader(LeaderState(1, 1, "Aldric", HexCoord(0, 0), is_king=True))
    visitor = LeaderState(VALHALLA_VISITOR_LEADER_ID, 2, "Quintilian", HexCoord(1, 1))
    state.add_leader(visitor)
    results = [_gate_angel_visit_sentinel(visitor)]

    assert describe_valhalla_visit_announcement(results, state, 1, ScriptedRandom([])) == []


def test_describe_valhalla_visit_announcement_returns_empty_with_no_sentinel():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, HexCoord(0, 0)))
    state.add_leader(LeaderState(1, 1, "Aldric", HexCoord(0, 0), is_king=True))

    assert describe_valhalla_visit_announcement([], state, 1, ScriptedRandom([])) == []


def test_describe_valhalla_visit_announcement_returns_empty_with_no_living_king():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, HexCoord(0, 0)))
    visitor = LeaderState(VALHALLA_VISITOR_LEADER_ID, 1, "Quintilian", HexCoord(0, 0))
    state.add_leader(visitor)
    results = [_gate_angel_visit_sentinel(visitor)]

    assert describe_valhalla_visit_announcement(results, state, 1, ScriptedRandom([])) == []


def test_compose_letter_report_includes_valhalla_visit_announcement_in_action_report():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, HexCoord(0, 0)))
    state.add_kingdom(KingdomState(2, "Otherland", Race.HUMAN, Alignment.GOOD, HexCoord(1, 1)))
    state.add_leader(LeaderState(1, 1, "Aldric", HexCoord(0, 0), is_king=True))
    state.add_leader(LeaderState(2, 2, "Borin", HexCoord(1, 1), is_king=True))
    visitor = LeaderState(VALHALLA_VISITOR_LEADER_ID, 1, "Quintilian", HexCoord(0, 0))
    state.add_leader(visitor)
    results = [_gate_angel_visit_sentinel(visitor)]

    lines_for_kingdom_1 = compose_letter_report(results, state, 1, ScriptedRandom([]))
    lines_for_kingdom_2 = compose_letter_report(results, state, 2, ScriptedRandom([]))

    assert "ACTION REPORT" in lines_for_kingdom_1
    assert render_valhalla_visit_announcement("Aldric", "Quintilian", ScriptedRandom([])) in lines_for_kingdom_1
    assert not any("Valhalla" in line for line in lines_for_kingdom_2)


def test_compose_letter_report_includes_battle_narrative_for_both_involved_kingdoms():
    # Phase 711: state.battle_narratives_by_kingdom is set up directly
    # here (bypassing record_battle_narratives()'s own rendering, tested
    # separately) to isolate compose_letter_report()'s own reading/
    # folding behavior from describe_battle()'s own RNG consumption.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, HexCoord(0, 0)))
    state.add_kingdom(KingdomState(2, "Defendia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(1, 1)))
    state.add_leader(LeaderState(1, 1, "Aldric", HexCoord(0, 0), is_king=True))
    state.add_leader(LeaderState(2, 2, "Borin", HexCoord(1, 1), is_king=True))
    state.battle_narratives_by_kingdom[1] = ["Attackia's men overran Defendia's own garrison."]
    state.battle_narratives_by_kingdom[2] = ["Attackia's men overran Defendia's own garrison."]

    lines_for_kingdom_1 = compose_letter_report([], state, 1, ScriptedRandom([]))
    lines_for_kingdom_2 = compose_letter_report([], state, 2, ScriptedRandom([]))

    assert "ACTION REPORT" in lines_for_kingdom_1
    assert "Attackia's men overran Defendia's own garrison." in lines_for_kingdom_1
    assert "ACTION REPORT" in lines_for_kingdom_2
    assert "Attackia's men overran Defendia's own garrison." in lines_for_kingdom_2


def test_compose_letter_report_omits_battle_narrative_for_an_uninvolved_kingdom():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, HexCoord(0, 0)))
    state.add_kingdom(KingdomState(3, "Watchia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(2, 2)))
    state.add_leader(LeaderState(1, 1, "Aldric", HexCoord(0, 0), is_king=True))
    state.add_leader(LeaderState(3, 3, "Cedric", HexCoord(2, 2), is_king=True))
    state.battle_narratives_by_kingdom[1] = ["Attackia's men overran Defendia's own garrison."]

    lines_for_kingdom_3 = compose_letter_report([], state, 3, ScriptedRandom([]))

    assert not any("overran" in line for line in lines_for_kingdom_3)


def test_compose_letter_report_includes_illusory_terrain_reveal_for_a_privileged_kingdom():
    # Phase 886: state.illusory_terrain_reveals_by_kingdom is set up
    # directly here, isolating compose_letter_report()'s own reading/
    # folding behavior from record_spell_world_events()'s own rendering,
    # tested separately.
    state = GameState()
    state.add_kingdom(KingdomState(3, "Watchia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(2, 2)))
    state.add_leader(LeaderState(3, 3, "Cedric", HexCoord(2, 2), is_king=True))
    state.illusory_terrain_reveals_by_kingdom[3] = [
        "In spring, the Plain terrain of Border Fort was magically made to appear as Mountain."
    ]

    lines_for_kingdom_3 = compose_letter_report([], state, 3, ScriptedRandom([]))

    assert "ACTION REPORT" in lines_for_kingdom_3
    assert "In spring, the Plain terrain of Border Fort was magically made to appear as Mountain." in lines_for_kingdom_3


def test_compose_letter_report_includes_tornado_victim_notice_for_the_affected_kingdom():
    # Phase 939: state.tornado_victim_notices_by_kingdom is set up
    # directly here, isolating compose_letter_report()'s own reading/
    # folding behavior from record_spell_world_events()'s own rendering,
    # tested separately.
    state = GameState()
    state.add_kingdom(KingdomState(3, "Watchia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(2, 2)))
    state.add_leader(LeaderState(3, 3, "Cedric", HexCoord(2, 2), is_king=True))
    state.tornado_victim_notices_by_kingdom[3] = [
        "In spring, Tornadoes sucked up the 20th Legion in Border Fort and destroyed them."
    ]

    lines_for_kingdom_3 = compose_letter_report([], state, 3, ScriptedRandom([]))

    assert "ACTION REPORT" in lines_for_kingdom_3
    assert "In spring, Tornadoes sucked up the 20th Legion in Border Fort and destroyed them." in lines_for_kingdom_3


def test_describe_challenge_delegates_to_describe_encounter_combat():
    result = ChallengeExecutionResult(
        accepted=True,
        combat_occurred=True,
        melee_swings=(MeleeSwing(attacker="a", hit=True, damage=3),),
    )
    # Phase 793: choice_indices[0] now picks the new, unconditional
    # ENCATT.X opening line -- every other index shifts one to the right.
    rng = ScriptedRandom([0.1] * 30, choice_indices=[0, 8, 0])

    lines = describe_challenge(
        result, challenger_leader_id=1, challenger_name="Aldric", target_name="Borin", province_name="Capital City", rng=rng
    )

    assert lines == [
        "Aldric searched throughout Capital City for Borin.",
        "Aldric Attacked Borin and inflicted 3 damage points.",
    ]


def test_describe_challenge_threads_state_through_to_the_steal_and_spoils_narration():
    # Phase 777: `describe_challenge()`'s own new `state` parameter must
    # reach both `describe_steal()` (STEAL family) and the SPOILS branch
    # inside `describe_encounter_combat()` -- proven end to end here,
    # not just at the shared function's own unit-test level.
    state, stolen_ids = _state_with_items(Treasure.ABILITY_TACTICAL)
    steal_result = ChallengeExecutionResult(
        accepted=True, combat_occurred=True, steal_outcome="success", stolen_item_ids=stolen_ids
    )
    # Phase 793: one more choice_indices entry for the new, unconditional
    # ENCATT.X opening line.
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0, 0])
    steal_lines = describe_challenge(
        steal_result,
        challenger_leader_id=1,
        challenger_name="Aldric",
        target_name="Borin",
        province_name="Capital City",
        rng=rng,
        state=state,
    )
    assert steal_lines == [
        "Aldric searched throughout Capital City for Borin.",
        "Aldric caressed the treasure fondly.",
    ]

    spoils_state, looted_ids = _state_with_items(Treasure.ABILITY_MELEE)
    spoils_result = ChallengeExecutionResult(
        accepted=True,
        combat_occurred=True,
        winner_leader_id=1,
        loser_leader_id=2,
        loser_killed=True,
        looted_item_ids=looted_ids,
    )
    # Phase 859: one more choice_indices entry for THATT.X.
    rng2 = ScriptedRandom([0.1] * 20, choice_indices=[0, 0, 0, 0, 0])
    spoils_lines = describe_challenge(
        spoils_result,
        challenger_leader_id=1,
        challenger_name="Aldric",
        target_name="Borin",
        province_name="Capital City",
        rng=rng2,
        state=spoils_state,
    )
    assert spoils_lines[0] == "Aldric searched throughout Capital City for Borin."
    assert spoils_lines[-1] == "Aldric looked with satisfaction at the remains of Borin."


# -- ASpy report body (Phase 115) --------------------------------------------


def test_render_spy_tax_estimate():
    rng = ScriptedRandom([0.1] * 4)
    result = render_spy_tax_estimate(250, rng)
    assert result == "Approximate Taxation: 250"


def test_render_spy_army_type():
    rng = ScriptedRandom([0.1] * 4)
    result = render_spy_army_type(1, "Bowmen", rng)
    assert result == "Province Army Type 1: Bowmen"


def test_render_spy_elements_intro_keeps_trailing_double_space():
    rng = ScriptedRandom([0.1] * 4)
    result = render_spy_elements_intro("Greenfield", rng)
    assert result == "the following elements are present in Greenfield:  "


def test_render_spy_character_here_defaults_title_to_empty():
    rng = ScriptedRandom([0.1] * 4)
    result = render_spy_character_here("Borin", rng)
    assert result == "Borin  is here."


def test_render_spy_character_here_with_explicit_title():
    rng = ScriptedRandom([0.1] * 4)
    result = render_spy_character_here("Borin", rng, title="General")
    assert result == "Borin General is here."


def test_render_spy_no_characters_or_forces():
    rng = ScriptedRandom([0.1] * 4)
    result = render_spy_no_characters_or_forces("Greenfield", rng)
    assert result == "there were no conspicuous characters or forces in Greenfield."


def test_render_spy_no_characters():
    rng = ScriptedRandom([0.1] * 4)
    result = render_spy_no_characters("Greenfield", rng)
    assert result == "there were no conspicuous characters in Greenfield."


def test_render_spy_capital_province():
    rng = ScriptedRandom([0.1] * 4)
    result = render_spy_capital_province("Greenfield", rng)
    assert result == "Greenfield is the kingdom's capital province."


def test_render_spy_report_closing():
    rng = ScriptedRandom([0.1] * 4)
    result = render_spy_report_closing("Aldric", "Greenfield", rng)
    assert result == (
        "Aldric also kept tabs on the characters in Greenfield and any "
        "further news is in the General Intelligence Report."
    )


def test_spy_leads_and_garrison_templates_are_blocked_on_list_insertion():
    # Real, confirmed content -- no render_* wrapper since ^L (list
    # insertion) isn't implemented by report/prose.py yet.
    assert SPY_LEADS_APPROXIMATELY_TEMPLATE == "[ leads approximately ^L^V."
    assert SPY_GARRISON_APPROXIMATELY_TEMPLATE == "there is a garrison of approximately ^L^V."


# -- Ally/Treat narrative (Phase 116) ----------------------------------------


def test_render_ally_proposed_first_variant_left_branch():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])
    result = render_ally_proposed("Aldric", "King Harold the Bold", rng)
    assert result == (
        "Aldric urged King Harold the Bold to improve relations with "
        "Aldric's Kingdom, speaking at length of the great advantages "
        "of such an agreement.the offer was wisely accepted by King "
        "Harold the Bold."
    )


def test_render_ally_proposed_first_variant_right_branch():
    rng = ScriptedRandom([0.9] * 10, choice_indices=[0])
    result = render_ally_proposed("Aldric", "King Harold the Bold", rng)
    assert result == (
        "Aldric asked King Harold the Bold to improve diplomatic "
        "relations with Aldric's great Kingdom, speaking eloquently of "
        "the great benefits of such an agreement.After some "
        "deliberation, the proposal was graciously accepted by King "
        "Harold the Bold."
    )


def test_render_ally_proposed_second_variant_uses_king_name_for_both_markers():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[1])
    result = render_ally_proposed("Aldric", "King Harold the Bold", rng)
    assert result == "Aldric proposed a treaty with King Harold the Bold, and the offer was accepted."


def test_render_already_allied():
    rng = ScriptedRandom([0.1] * 4)
    result = render_already_allied("Aldric", "King Harold the Bold", rng)
    assert result == "Aldric treated with Aldric's ally King Harold the Bold."


def test_already_allied_template_is_the_confirmed_hardcoded_say():
    assert ALREADY_ALLIED_TEMPLATE == "< treated with > ally [3."


def test_render_ally_refused_concatenates_both_sentences_with_no_separator():
    rng = ScriptedRandom([0.1] * 10)
    result = render_ally_refused("Aldric", "King Harold the Bold", rng)
    assert result == (
        "Aldric Treated with King Harold the Bold, but King Harold the "
        "Bold did not respond to Aldric's friendly noises.it is hoped "
        "that next year, both Kings will see the wisdom of Treating."
    )


# -- Treasure/Steal narrative (Phase 117) ------------------------------------


def test_render_take_gold_first_variant():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])
    result = render_take_gold("Aldric", "Borin", 50, rng)
    assert result == "Aldric stole 50 gold from Borin."


def test_render_take_gold_second_variant_uses_victim_possessive():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[1])
    result = render_take_gold("Aldric", "Borin", 50, rng)
    assert result == "Aldric stole 50 gold from Borin's treasure chest."


def test_render_take_gold_third_variant():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[2])
    result = render_take_gold("Aldric", "Borin", 50, rng)
    assert result == "Aldric robbed Borin of 50 gold."


def test_render_inherit():
    rng = ScriptedRandom([0.1] * 4)
    result = render_inherit("Borin", "Crystal Ball", rng)
    assert result == "Borin inherited the Crystal Ball."


def test_inherit_template_is_the_confirmed_hardcoded_say_else_branch():
    assert INHERIT_TEMPLATE == "< inherited/Rgained the \\."


def test_render_will_left_branch():
    rng = ScriptedRandom([0.1] * 10)
    result = render_will("Borin", rng)
    assert result == "Borin's will left Borin's possessions to Borin's compatriots."


def test_render_will_right_branch():
    rng = ScriptedRandom([0.9] * 10)
    result = render_will("Borin", rng)
    assert result == "Borin's will left all Borin's worldly possessions to Borin's fellow adventurers."


def test_will_template_is_the_confirmed_hardcoded_say():
    assert WILL_TEMPLATE == "['s will left {all }] {worldly }possessions to ] compatriots/Rfellow_adventurers."


# -- ^L list insertion unblocks 3 templates (Phase 118) ----------------------


def test_render_spy_leads():
    rng = ScriptedRandom([0.1] * 4)
    result = render_spy_leads("Borin", ["241st Axemen", "34th Legion"], rng)
    assert result == "Borin leads approximately 241st Axemen and 34th Legion."


def test_render_spy_garrison():
    rng = ScriptedRandom([0.1] * 4)
    result = render_spy_garrison(["241st Axemen"], rng)
    assert result == "there is a garrison of approximately 241st Axemen."


def test_render_inherit_as_heir():
    rng = ScriptedRandom([0.1] * 4)
    result = render_inherit_as_heir("Aldric", ["Crystal Ball", "Ring of Power"], rng)
    assert result == "The heir of Aldric inherited the Crystal Ball and Ring of Power."


def test_render_take_items():
    rng = ScriptedRandom([0.1] * 4)
    result = render_take_items("Aldric", ["Crystal Ball"], rng)
    assert result == "Aldric took the Crystal Ball."


def test_render_take_items_single_item_has_no_and():
    # A single-item ^L list renders bare -- no "and" is inserted.
    rng = ScriptedRandom([0.1] * 4)
    result = render_take_items("Aldric", ["Crystal Ball"], rng)
    assert "and" not in result


# -- funeral pyre and failed-Steal ransom (Phase 119) ------------------------


def test_render_funeral_pyre():
    rng = ScriptedRandom([0.1] * 4)
    result = render_funeral_pyre("Borin", "Aldric", rng)
    assert result == "Borin's possessions were burned with Aldric on the funeral pyre."


def test_funeral_pyre_template_is_the_confirmed_hardcoded_say():
    assert FUNERAL_PYRE_TEMPLATE == "] possessions were burned with [3 on the funeral pyre."


def test_render_steal_caught_and_ransomed_concatenates_both_sentences():
    rng = ScriptedRandom([0.1] * 10)
    result = render_steal_caught_and_ransomed("Borin", "Aldric", rng)
    assert result == (
        "Borin caught Aldric red-handed while Aldric was rummaging "
        "through Borin's things in a bungled attempt at thievery.Borin "
        "forced Aldric to pay Borin half Aldric's treasury in ransom "
        "before letting him go."
    )


# -- Move/Pursue/Practice narrative (Phase 120) ------------------------------


def test_render_defensive_march():
    rng = ScriptedRandom([0.1] * 4)
    result = render_defensive_march("Aldric", "Greenfield", "Redhaven", rng)
    assert result == "Aldric marched into Greenfield from Redhaven to defend Greenfield against its would-be conquerors."


def test_defensive_march_template_is_the_confirmed_hardcoded_say():
    assert DEFENSIVE_MARCH_TEMPLATE == "< marched into @ from ^S to defend @ against its would-be conquerors."


def test_render_caught_up():
    rng = ScriptedRandom([0.1] * 4)
    result = render_caught_up("Aldric", "Borin", "Greenfield", rng)
    assert result == "Aldric caught up with Borin in Greenfield."


def test_caught_up_template_is_the_confirmed_hardcoded_say():
    assert CAUGHT_UP_TEMPLATE == "< caught up with [ in @."


def test_render_practice_tutored_left_branch():
    rng = ScriptedRandom([0.1] * 4)
    result = render_practice_tutored("Aldric", "Tactics", "Borin", rng)
    assert result == "Aldric was tutored in Tactics by Borin."


def test_render_practice_tutored_right_branch():
    rng = ScriptedRandom([0.9] * 4)
    result = render_practice_tutored("Aldric", "Tactics", "Borin", rng)
    assert result == "Aldric was instructed in the art of Tactics by Borin."


def test_practice_tutored_template_is_the_confirmed_hardcoded_say():
    assert PRACTICE_TUTORED_TEMPLATE == "< was tutored/Rinstructed in{ the art of} ^ by [."


def test_render_practice_already_maxed():
    rng = ScriptedRandom([0.1] * 4)
    result = render_practice_already_maxed("Aldric", "Tactics", rng)
    assert result == "Aldric practiced Tactics even though Aldric had already reached the maximum skill level."


def test_practice_already_maxed_template_is_the_confirmed_hardcoded_say():
    assert PRACTICE_ALREADY_MAXED_TEMPLATE == (
        "< practiced ^ even though < had already reached the maximum skill level."
    )


# -- Sage device-discovery narrative (DISCOV.X / _LNoDisc, Phase 266) -------


def test_render_sage_discovery_names_the_granted_discovery():
    rng = ScriptedRandom([0.1] * 4)
    result = render_sage_discovery("Aldric", Discovery.COMPASS, rng)
    assert result == "in Aldric's sagely researches, Aldric discovered a fabulous invention called the Compass"


def test_render_sage_discovery_picks_an_before_a_vowel_initial_discovery():
    # ^A peeks past "fabulous" (hardcoded, consonant-initial) either way --
    # this only confirms ^A resolution runs at all, via a vowel-initial name.
    rng = ScriptedRandom([0.1] * 4)
    result = render_sage_discovery("Aldric", Discovery.ASBESTOS_CLOTHING, rng)
    assert result == "in Aldric's sagely researches, Aldric discovered a fabulous invention called the Asbestos Clothing"


def test_render_sage_no_discovery_left_branch():
    # Three /R choices resolve left-to-right before the {optional} block's
    # own inclusion roll: "discovered", "valuable", "researches", then a
    # >=0.5 fourth roll includes the optional block.
    rng = ScriptedRandom([0.1, 0.1, 0.1, 0.9])
    result = render_sage_no_discovery("Aldric", rng)
    assert result == "Aldric discovered nothing valuable in Aldric's sagely researches."


def test_render_sage_no_discovery_right_branch():
    rng = ScriptedRandom([0.9] * 4)
    result = render_sage_no_discovery("Aldric", rng)
    assert result == "Aldric invented nothing worthy of note in Aldric's sagely experiments."


# -- describe_sage_discovery (Phase 772) ---------------------------------


def test_describe_sage_discovery_empty_for_a_non_sage_ability():
    result = PracticeExecutionResult(ability=Ability.MELEE, device_discovered=True, discovery_granted=Discovery.COMPASS)
    lines = describe_sage_discovery(result, character_name="Aldric", rng=ScriptedRandom([0.1] * 4))
    assert lines == []


def test_describe_sage_discovery_renders_the_success_line_when_a_discovery_was_granted():
    result = PracticeExecutionResult(ability=Ability.SAGE, device_discovered=True, discovery_granted=Discovery.COMPASS)
    lines = describe_sage_discovery(result, character_name="Aldric", rng=ScriptedRandom([0.1] * 4))
    assert lines == [render_sage_discovery("Aldric", Discovery.COMPASS, ScriptedRandom([0.1] * 4))]


def test_describe_sage_discovery_renders_the_failure_line_when_no_roll_succeeded():
    result = PracticeExecutionResult(ability=Ability.SAGE, device_discovered=False, discovery_granted=None)
    lines = describe_sage_discovery(result, character_name="Aldric", rng=ScriptedRandom([0.1, 0.1, 0.1, 0.9]))
    assert lines == [render_sage_no_discovery("Aldric", ScriptedRandom([0.1, 0.1, 0.1, 0.9]))]


def test_describe_sage_discovery_renders_the_failure_line_even_when_the_roll_succeeded_but_nothing_was_granted():
    # PracticeExecutionResult's own documented edge case: device_discovered
    # can be True (the roll succeeded) with discovery_granted still None
    # (a kingdomless leader, or a kingdom that already owns all 64) --
    # there's no real Discovery to plug into the success template, so this
    # must render the failure line, not the success one, proving the
    # gate is discovery_granted, not the raw device_discovered flag.
    result = PracticeExecutionResult(ability=Ability.SAGE, device_discovered=True, discovery_granted=None)
    lines = describe_sage_discovery(result, character_name="Aldric", rng=ScriptedRandom([0.1, 0.1, 0.1, 0.9]))
    assert lines == [render_sage_no_discovery("Aldric", ScriptedRandom([0.1, 0.1, 0.1, 0.9]))]


def _sage_practice_state() -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_leader(LeaderState(1, kingdom_id=1, name="Aldric", location=HexCoord(0, 0)))
    return state


def test_describe_turn_results_practice_renders_only_the_discovery_line_when_describe_practice_has_none():
    # An aptitude-only rise has no sourced narrative of its own
    # (describe_practice()'s own docstring), so this proves the Sage
    # discovery line still appears alone, not silently swallowed by the
    # main line being None.
    state = _sage_practice_state()
    result = PracticeExecutionResult(
        ability=Ability.SAGE, skill_rose=False, aptitude_rose=True, new_skill=3, new_aptitude=6,
        discovery_granted=Discovery.COMPASS,
    )
    entries = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.PRACTICE, result=result, error=None)
    ]
    rng = ScriptedRandom([0.1] * 10)

    lines = describe_turn_results(entries, state, rng, ability_names={Ability.SAGE: "Sageness"})

    assert lines == [render_sage_discovery("Aldric", Discovery.COMPASS, ScriptedRandom([0.1] * 10))]


def test_describe_turn_results_practice_renders_both_lines_in_order_when_both_are_real():
    state = _sage_practice_state()
    result = PracticeExecutionResult(
        ability=Ability.SAGE, skill_rose=False, new_skill=9, new_aptitude=5,
        discovery_granted=Discovery.COMPASS,
    )
    entries = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.PRACTICE, result=result, error=None)
    ]
    rng = ScriptedRandom([0.1] * 10)

    lines = describe_turn_results(entries, state, rng, ability_names={Ability.SAGE: "Sageness"})

    assert lines == [
        "Aldric practiced Sageness even though Aldric had already reached the maximum skill level.",
        render_sage_discovery("Aldric", Discovery.COMPASS, ScriptedRandom([0.1] * 10)),
    ]


# -- describe_practice (integration, Phase 144) --


def test_describe_practice_renders_already_maxed():
    # new_skill == MAX_SKILL_LEVEL (9) with skill_rose False is only
    # reachable by starting the attempt already at the ceiling -- see
    # describe_practice()'s own docstring.
    result = PracticeExecutionResult(ability=0, skill_rose=False, new_skill=9, new_aptitude=5)
    rng = ScriptedRandom([0.1] * 4)

    line = describe_practice(result, character_name="Aldric", ability_name="Tactics", rng=rng)

    assert line == "Aldric practiced Tactics even though Aldric had already reached the maximum skill level."


def test_describe_practice_renders_tutored_when_a_teacher_is_supplied():
    result = PracticeExecutionResult(ability=0, skill_rose=True, new_skill=3, new_aptitude=5)
    rng = ScriptedRandom([0.1] * 4)

    line = describe_practice(result, character_name="Aldric", ability_name="Tactics", teacher_name="Borin", rng=rng)

    assert line == "Aldric was tutored in Tactics by Borin."


def test_describe_practice_renders_nothing_for_a_solo_rise_with_no_teacher():
    # No sourced narrative template exists for solo Practice success at
    # all -- see describe_practice()'s own docstring.
    result = PracticeExecutionResult(ability=0, skill_rose=True, new_skill=3, new_aptitude=5)
    rng = ScriptedRandom([])

    line = describe_practice(result, character_name="Aldric", ability_name="Tactics", rng=rng)

    assert line is None


# -- PRACVAIN.X (Phase 601) --


def test_render_practice_vain_first_variant():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])
    result = render_practice_vain("Aldric", "Tactics", rng)
    assert result == "Aldric tried hard to improve Aldric's Tactics, but Aldric practiced in vain."


def test_render_practice_vain_third_variant_includes_optional_clause():
    rng = ScriptedRandom([0.99] * 10, choice_indices=[2])
    result = render_practice_vain("Aldric", "Tactics", rng)
    assert result == "Aldric practiced Aldric's Tactics well, and even consulted an astrologer, but could not improve Aldric's skill in Tactics."


def test_render_practice_vain_fourth_variant():
    rng = ScriptedRandom([0.99] * 10, choice_indices=[3])
    result = render_practice_vain("Aldric", "Tactics", rng)
    assert result == "Aldric worked hard on Aldric's Tactics but was frustrated in Aldric's self-improvement efforts."


def test_describe_practice_renders_pracvain_for_a_normal_failed_roll():
    # Phase 601: PRACVAIN.X closes what used to be an unsourced gap.
    result = PracticeExecutionResult(ability=0, skill_rose=False, new_skill=3, new_aptitude=5)
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])

    line = describe_practice(result, character_name="Aldric", ability_name="Tactics", rng=rng)

    assert line == "Aldric tried hard to improve Aldric's Tactics, but Aldric practiced in vain."


def test_describe_practice_renders_nothing_for_an_aptitude_only_rise():
    result = PracticeExecutionResult(ability=0, skill_rose=False, aptitude_rose=True, new_skill=3, new_aptitude=6)
    rng = ScriptedRandom([])

    line = describe_practice(result, character_name="Aldric", ability_name="Tactics", rng=rng)

    assert line is None


def test_describe_practice_renders_nothing_when_not_implemented_for_ability():
    result = PracticeExecutionResult(ability=0, not_implemented_for_ability=True)
    rng = ScriptedRandom([])

    line = describe_practice(result, character_name="Aldric", ability_name="Tactical", rng=rng)

    assert line is None


# -- FRUMOR.X rumor narrative (Phase 244) -------------------------------


def _rumor_state_with_feature(coord: HexCoord, **feature_kwargs) -> tuple[GameState, Feature]:
    state = GameState()
    feature = Feature(feature_id=1, coord=coord, kind=FeatureType.DUNGEON, **feature_kwargs)
    state.add_feature(feature)
    return state, feature


def test_describe_rumor_renders_feature_and_monster_content():
    coord = HexCoord(9, 9)
    state, feature = _rumor_state_with_feature(coord, guardian_monster=Monster.ARCHER)
    rumor = Rumor(
        rumor_id=1,
        kingdom_id=1,
        leader_id=1,
        source_action=ActionCode.EXPLORE,
        content=RumorContent.FEATURE_AND_MONSTER,
        feature_id=feature.feature_id,
        is_true=True,
        described_coord=coord,
        described_monster=Monster.ARCHER,
    )
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])

    line = describe_rumor(rumor, state, "Aldric", board_width=10, rng=rng)

    assert line == "Aldric heard of a feature in  $99:  Dungeon inhabited by Renegade Archer."


def test_describe_rumor_renders_item_content():
    coord = HexCoord(9, 9)
    state, feature = _rumor_state_with_feature(coord, treasure=Treasure.ABILITY_TACTICAL)
    rumor = Rumor(
        rumor_id=1,
        kingdom_id=1,
        leader_id=1,
        source_action=ActionCode.EXPLORE,
        content=RumorContent.ITEM,
        feature_id=feature.feature_id,
        is_true=True,
        described_coord=coord,
        described_treasure=Treasure.ABILITY_TACTICAL,
    )
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])

    line = describe_rumor(rumor, state, "Aldric", board_width=10, rng=rng)

    assert line == "Aldric heard of a feature in  $99:  Dungeon is said to hold the Standard of Command."


def test_describe_rumor_uses_the_described_coord_not_the_features_real_coord():
    # A false rumor corrupts the province -- the rendered location must come
    # from rumor.described_coord, not feature.coord (turn/rumor.py's own
    # false-rumor-corrupts-the-province branch, Phase 243).
    real_coord = HexCoord(1, 1)
    corrupted_coord = HexCoord(4, 0)
    state, feature = _rumor_state_with_feature(real_coord, guardian_monster=Monster.ARCHER)
    rumor = Rumor(
        rumor_id=1,
        kingdom_id=1,
        leader_id=1,
        source_action=ActionCode.LMOVE,
        content=RumorContent.FEATURE_AND_MONSTER,
        feature_id=feature.feature_id,
        is_true=False,
        described_coord=corrupted_coord,
        described_monster=Monster.ARCHER,
    )
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])

    line = describe_rumor(rumor, state, "Aldric", board_width=10, rng=rng)

    # encode_hex_number(HexCoord(4, 0), board_width=10) == 0 * 10 + 4 == 4
    assert "$4:" in line


def test_describe_rumor_picks_the_selected_variant():
    coord = HexCoord(0, 0)
    state, feature = _rumor_state_with_feature(coord, guardian_monster=Monster.ARCHER)
    rumor = Rumor(
        rumor_id=1,
        kingdom_id=1,
        leader_id=1,
        source_action=ActionCode.EXPLORE,
        content=RumorContent.FEATURE_AND_MONSTER,
        feature_id=feature.feature_id,
        is_true=True,
        described_coord=coord,
        described_monster=Monster.ARCHER,
    )
    rng = ScriptedRandom([0.1] * 10, choice_indices=[2])

    line = describe_rumor(rumor, state, "Aldric", board_width=10, rng=rng)

    assert line == "Aldric heard a rumor telling of  feature in  $0,  Dungeon inhabited by Renegade Archer."


# -- MONSTERS.X2 flavor text (Phase 613) -------------------------------------


def test_render_monster_description_returns_the_real_flavor_text_verbatim():
    assert render_monster_description(Monster.ROC) == (
        "The Roc is reputed to be a huge, powerful bird, many times the size of an elephant, "
        "which the Roc often feeds upon."
    )


def test_render_monster_description_second_species():
    # Confirms this is a plain per-species lookup, not a first-variant-only
    # bug -- Gargoyle's own real entry, distinct from Roc's.
    assert render_monster_description(Monster.GARGOYLE) == (
        "The Gargoyle is an ugly and evil winged humanoid monster.It is extremely vicious and cruel."
    )


# -- FINDFEAT.X in-person discovery narrative (Phase 245) -------------------


def test_describe_feature_discovery_first_variant():
    feature = Feature(feature_id=1, coord=HexCoord(0, 0), kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER)
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])

    lines = describe_feature_discovery(feature, "Aldric", "Ancient Valley", rng)

    # Phase 613: MONSTERS.X2's own flavor text now follows FINDFEAT.X's
    # own discovery sentence, as its own separate line.
    assert lines == [
        "Aldric discovered a feature in Ancient Valley:  Dungeon  inhabited by Renegade Archer.",
        "Rangers describe the Renegade Archer as an accomplished archer who has taken to the "
        "wilderness in protest against the injustices of the world.",
    ]


def test_describe_feature_discovery_picks_the_selected_variant():
    feature = Feature(feature_id=1, coord=HexCoord(0, 0), kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER)
    rng = ScriptedRandom([0.1] * 10, choice_indices=[3])

    lines = describe_feature_discovery(feature, "Aldric", "Ancient Valley", rng)

    assert lines == [
        "Aldric found  Dungeon  in Ancient Valley, occupied by Renegade Archer.",
        "Rangers describe the Renegade Archer as an accomplished archer who has taken to the "
        "wilderness in protest against the injustices of the world.",
    ]


# -- duel demoralization narrative (Phase 121) -------------------------------


def test_render_commander_died_demoralized_left_branch():
    rng = ScriptedRandom([0.1] * 10)
    result = render_commander_died_demoralized("Borin", rng)
    assert result == "The forces commanded by Borin were disheartened by Borin's death, but still they pressed forward with some hope of victory."


def test_render_commander_died_demoralized_right_branch():
    rng = ScriptedRandom([0.9] * 10)
    result = render_commander_died_demoralized("Borin", rng)
    assert result == "The forces commanded by Borin were disheartened by Borin's demise, yet still they moved ahead with some hope of victory."


def test_render_commander_fled_demoralized_left_branch():
    rng = ScriptedRandom([0.1] * 10)
    result = render_commander_fled_demoralized("Borin", rng)
    assert result == "The forces commanded by Borin were disappointed by Borin's cowardice.They marched on, though with lessened confidence."


def test_render_commander_fled_demoralized_right_branch():
    rng = ScriptedRandom([0.9] * 10)
    result = render_commander_fled_demoralized("Borin", rng)
    assert result == "The forces commanded by Borin were dismayed by Borin's faint-heartedness.They steadfastly marched on, though with shaken confidence."


def test_commander_died_and_fled_are_distinct_narrations():
    rng1 = ScriptedRandom([0.1] * 10)
    rng2 = ScriptedRandom([0.1] * 10)
    assert render_commander_died_demoralized("Borin", rng1) != render_commander_fled_demoralized("Borin", rng2)


# -- Ice-Suspend narrative cluster (Phase 123) --


def test_render_ice_suspend_failed_to_hold():
    rng = ScriptedRandom([0.1] * 10)
    result = render_ice_suspend_failed_to_hold("Bob", rng)
    assert result == (
        "but the shell was not strong enough to hold Bob, and Bob began to break out."
    )


def test_render_ice_break_out_attempt_left_branch():
    rng = ScriptedRandom([0.1] * 10)
    result = render_ice_break_out_attempt("Bob", rng)
    assert result == "Bob struggled to break out of Bob's shell of ice."


def test_render_ice_break_out_attempt_right_branch():
    rng = ScriptedRandom([0.9] * 10)
    result = render_ice_break_out_attempt("Bob", rng)
    assert result == "Bob attempted to break out of Bob's frosty prison of frigid ice."


def test_render_ice_break_out_success_left_branch():
    rng = ScriptedRandom([0.1] * 10)
    result = render_ice_break_out_success("Bob", rng)
    assert result == "with a mighty heave, Bob broke out of Bob's shell of ice."


def test_render_ice_break_out_success_right_branch():
    rng = ScriptedRandom([0.9] * 10)
    result = render_ice_break_out_success("Bob", rng)
    assert result == "with a mighty effort, Bob broke out of Bob's frosty prison of frigid ice."


def test_render_ice_fall_damage():
    rng = ScriptedRandom([0.1] * 10)
    result = render_ice_fall_damage("Bob", 12, rng)
    assert result == "Bob dropped, suffering 12 damage points."


def test_render_ice_ghost_immune():
    rng = ScriptedRandom([0.1] * 10)
    result = render_ice_ghost_immune("Bob", rng)
    assert result == "but Bob's translucent form easily glided through the ice."


def test_render_ice_immobilized_left_branch():
    rng = ScriptedRandom([0.1] * 10)
    result = render_ice_immobilized("Bob", rng)
    assert result == "Bob was immobilized by the shell of ice."


def test_render_ice_immobilized_right_branch():
    rng = ScriptedRandom([0.9] * 10)
    result = render_ice_immobilized("Bob", rng)
    assert result == "Bob was locked in the frosty prison of frigid ice."


def test_render_ice_wait_for_melt():
    rng = ScriptedRandom([0.1] * 10)
    result = render_ice_wait_for_melt("Alice", "Bob", rng)
    assert result == "Alice stood away from Bob and waited for the ice to melt."


def test_render_ice_steal_blocked_single_item():
    rng = ScriptedRandom([0.1] * 10)
    result = render_ice_steal_blocked("Alice", "Bob", ["a Ring of Fire"], rng)
    assert result == (
        "Alice could not take the a Ring of Fire because what Bob carried was frozen in with Bob."
    )


def test_render_ice_steal_blocked_multiple_items():
    rng = ScriptedRandom([0.1] * 10)
    result = render_ice_steal_blocked("Alice", "Bob", ["a Ring of Fire", "a Sword of Ice"], rng)
    assert result == (
        "Alice could not take the a Ring of Fire and a Sword of Ice "
        "because what Bob carried was frozen in with Bob."
    )


# -- end-of-turn Financial Report (Phase 124) --


def test_render_finance_report_opening():
    rng = ScriptedRandom([0.1] * 10)
    result = render_finance_report_opening("Uga-Buga Makumb", rng)
    assert result == "here is the financial report for Uga-Buga Makumb's kingdom: "


def test_render_finance_revenue():
    rng = ScriptedRandom([0.1] * 10)
    result = render_finance_revenue(500, rng)
    assert result == "this turn, the Kingdom collected 500 gold in revenue."


def test_render_finance_leader_costs():
    rng = ScriptedRandom([0.1] * 10)
    result = render_finance_leader_costs(120, rng)
    assert result == "120 gold was expended to finance our leaders."


def test_render_finance_unpaid_armies():
    rng = ScriptedRandom([0.1] * 10)
    result = render_finance_unpaid_armies(15, rng)
    assert result == "unfortunately, 15% of your Majesty's armies had to go without pay."


def test_render_finance_army_costs():
    rng = ScriptedRandom([0.1] * 10)
    result = render_finance_army_costs(300, rng)
    assert result == "300 gold was expended to maintain our armies."


def test_render_finance_treasury():
    rng = ScriptedRandom([0.1] * 10)
    result = render_finance_treasury("Uga-Buga Makumb", 80, rng)
    assert result == "Uga-Buga Makumb was left with 80 gold in the treasury."


# -- Assassination narrative (Phase 125) --


def test_render_assassination_ordered():
    rng = ScriptedRandom([0.1] * 10)
    result = render_assassination_ordered("Malachar", "Bob", rng)
    assert result == "Malachar ordered the assassination of Bob."


def test_render_assassination_attempt_left_branch():
    rng = ScriptedRandom([0.1] * 10)
    result = render_assassination_attempt("Bob", rng)
    assert result == "While Bob was out for a stroll, suddenly an assassin launched himself at Bob!"


def test_render_assassination_attempt_right_branch():
    rng = ScriptedRandom([0.9] * 10)
    result = render_assassination_attempt("Bob", rng)
    assert result == (
        "While Bob was in meditation, suddenly an unknown assassin "
        "launched himself from out of the dark at Bob!"
    )


def test_render_assassination_success_left_branch():
    rng = ScriptedRandom([0.1] * 10)
    result = render_assassination_success("Bob", rng)
    assert result == (
        "Bob was wounded by a poisoned dagger!"
        "Cursed be the Assassin's Guild and whoever heads it!"
    )


def test_render_assassination_success_right_branch():
    rng = ScriptedRandom([0.9] * 10)
    result = render_assassination_success("Bob", rng)
    assert result == (
        "Bob was stabbed by his poisonous dagger!"
        "Cursed be the Assassin's Guild and whoever heads it!"
    )


def test_render_assassination_failed_left_branch():
    rng = ScriptedRandom([0.1] * 10)
    result = render_assassination_failed("Bob", rng)
    assert result == (
        "Fortunately, Bob survived the attempt and the assassin "
        "(apparently, a member of the Assassin's Guild) was killed."
        "Of course, the guard in Bob's kingdom was doubled."
    )


def test_render_assassination_failed_right_branch():
    rng = ScriptedRandom([0.9] * 10)
    result = render_assassination_failed("Bob", rng)
    assert result == (
        "Fortunately, Bob survived the attempt and the assassin "
        "(apparently, a member of the Assassin's Guild) was killed."
        "Without delay, the guard throughout Bob's kingdom was immediately doubled."
    )


def test_render_could_not_be_assassinated():
    # Phase 614: ILLEG.X2 record 91 -- no rng draws, no /R or {} markers.
    result = render_could_not_be_assassinated("Bob")
    assert result == "Bob could not be assassinated because Bob was dead and buried."


# -- battle morale narrative + vampiric bite (Phase 126) --


def test_render_skeletal_army_fervor():
    rng = ScriptedRandom([0.1] * 10)
    result = render_skeletal_army_fervor("Aldric", rng)
    assert result == "The Skeletal Armies led by Aldric marched into battle with a fanatical fervor."


def test_render_oratory_speech_left_branch():
    rng = ScriptedRandom([0.1] * 10)
    result = render_oratory_speech("Aldric", rng)
    assert result == (
        "using Aldric's magical powers of Oratory, Aldric gave a "
        "rousing speech to Aldric's troops, raising their courage."
    )


def test_render_oratory_speech_right_branch():
    rng = ScriptedRandom([0.9] * 10)
    result = render_oratory_speech("Aldric", rng)
    assert result == (
        "calling upon Aldric's arcane Spell of Oratory, Aldric started "
        "with an inspiring harangue to Aldric's army, which bolstered "
        "their morale."
    )


def test_render_homeland_defense_morale_left_branch():
    rng = ScriptedRandom([0.1] * 10)
    result = render_homeland_defense_morale("Aldric", rng)
    assert result == "Aldric's troops were prepared to fight desperately for their homeland."


def test_render_homeland_defense_morale_right_branch():
    rng = ScriptedRandom([0.9] * 10)
    result = render_homeland_defense_morale("Aldric", rng)
    assert result == "Aldric's soldiers swore to struggle like tigers for their fatherland."


def test_render_race_fanaticism_left_branch():
    rng = ScriptedRandom([0.1] * 10)
    result = render_race_fanaticism("The 231st Bowmen", Race.HUMAN, "Sir Roland", rng)
    assert result == "The 231st Bowmen were inspired to fanaticism by Sir Roland, their glorious Savior of Humankind."


def test_render_race_fanaticism_right_branch():
    rng = ScriptedRandom([0.9] * 10)
    result = render_race_fanaticism("The 231st Bowmen", Race.HUMAN, "Sir Roland", rng)
    assert (
        result
        == "The 231st Bowmen were exhorted to a fanatical elan by Sir Roland, their exalted Savior of Humankind."
    )


def test_render_race_fanaticism_dwarven_title():
    rng = ScriptedRandom([0.1] * 10)
    result = render_race_fanaticism("The 12th Legion", Race.DWARVEN, "King Thorin", rng)
    assert result == "The 12th Legion were impelled to fanaticism by King Thorin, their esteemed King Under the Mountain."


def test_render_weapon_rally_left_branch():
    rng = ScriptedRandom([0.1] * 10)
    result = render_weapon_rally("Aldric", "Sword of Flame", "Orcs", rng)
    assert result == "Aldric waved Aldric's Sword of Flame and the Orcs cheered wildly!"


def test_render_weapon_rally_right_branch():
    rng = ScriptedRandom([0.9] * 10)
    result = render_weapon_rally("Aldric", "Sword of Flame", "Orcs", rng)
    assert result == (
        "Aldric held aloft Aldric's Sword of Flame and Aldric's Orcs "
        "were virtually hypnotized in it's enchanted glow!"
    )


def test_duel_no_excuse_template_is_the_confirmed_hardcoded_say():
    assert DUEL_NO_EXCUSE_TEMPLATE == (
        "< couldn't/Rfailed_to think_of/Rcome_up_with a good/Rbelievable "
        "excuse/Rploy for_avoiding/Rto_get_out_of the duel, so "
    )


def test_render_vampiric_bite_left_branch():
    rng = ScriptedRandom([0.1] * 10)
    result = render_vampiric_bite("Countess", "Bob", "Evil", rng)
    assert result == (
        "Countess sank Countess's fangs into Bob and drained "
        "Bob's blood.Bob changed to Evil alignment!"
    )


def test_render_vampiric_bite_right_branch():
    rng = ScriptedRandom([0.9] * 10)
    result = render_vampiric_bite("Countess", "Bob", "Evil", rng)
    assert result == (
        "Countess bit Countess's fangs into Bob and sucked up all "
        "Bob's blood.Bob changed to Evil alignment!"
    )


# -- illegal-move error narrative (Phase 127) --


def test_render_illegal_move_non_adjacent():
    rng = ScriptedRandom([0.1] * 10)
    result = render_illegal_move_non_adjacent("Aldric", "Greenfield", "Redhaven", rng)
    assert result == "Aldric tried to move from Greenfield to Redhaven, a non-adjacent province.This is illegal!"


def test_render_illegal_move_attempted():
    rng = ScriptedRandom([0.1] * 10)
    result = render_illegal_move_attempted("Aldric", rng)
    assert result == "Aldric attempted an illegal move."


def test_render_illegal_move_occupied_retreat():
    rng = ScriptedRandom([0.1] * 10)
    result = render_illegal_move_occupied_retreat("Aldric", rng)
    assert result == "Aldric could not retreat into an occupied province."


def test_render_illegal_move_insufficient_water_transport():
    rng = ScriptedRandom([0.1] * 10)
    result = render_illegal_move_insufficient_water_transport("Aldric", "Greenfield", "Redhaven", rng)
    assert result == (
        "Aldric tried to use water-borne movement to move from "
        "Greenfield to Redhaven, but Aldric's transport was "
        "insufficent for the task."
    )


def test_render_illegal_move_flooding_transport():
    rng = ScriptedRandom([0.1] * 10)
    result = render_illegal_move_flooding_transport("Aldric", "Greenfield", "Redhaven", rng)
    assert result == (
        "Aldric tried to move from Greenfield to Redhaven, but "
        "provincial flooding and insufficient transport thwarted the move."
    )


def test_render_illegal_move_mermen_air_transport():
    rng = ScriptedRandom([0.1] * 10)
    result = render_illegal_move_mermen_air_transport("Aldric", "Greenfield", "Redhaven", rng)
    assert result == (
        "Aldric was ordered to move with Mermen from Greenfield to "
        "Redhaven, but had insufficient air-transport."
    )


# -- Phase 737: render_illegal_move_choice() / describe_transport_illegal_move() --


def test_render_illegal_move_choice_1_naval_land_hop():
    rng = ScriptedRandom([0.1] * 10)
    result = render_illegal_move_choice(1, "Aldric", "Greenfield", "Redhaven", rng)
    assert result == (
        "Aldric was ordered to move from Greenfield to Redhaven, but it is "
        "illegal to move naval forces from one non-sea province to another."
    )


def test_render_illegal_move_choice_16_ent_shoreline():
    rng = ScriptedRandom([0.1] * 10)
    result = render_illegal_move_choice(16, "Aldric", "Greenfield", "Redhaven", rng)
    assert result == (
        "Aldric could not move from Greenfield to Redhaven because "
        "Aldric's ents refused to cross the shoreline."
    )


def test_render_illegal_move_choice_19_dinosaur_shoreline():
    rng = ScriptedRandom([0.1] * 10)
    result = render_illegal_move_choice(19, "Aldric", "Greenfield", "Redhaven", rng)
    assert result == (
        "Aldric could not move from Greenfield to Redhaven because "
        "Aldric's dinosaurs refused to cross the shoreline."
    )


def test_describe_transport_illegal_move_insufficient_water_transport():
    error = TransportIllegalMoveError("insufficient_water_transport", origin_coord=HexCoord(0, 0), destination_coord=HexCoord(1, 0))
    rng = ScriptedRandom([0.1] * 10)
    lines = describe_transport_illegal_move(error, "Aldric", "Greenfield", "Redhaven", rng)
    assert lines == [
        "Aldric attempted an illegal move.",
        "Aldric tried to use water-borne movement to move from Greenfield to "
        "Redhaven, but Aldric's transport was insufficent for the task.",
    ]


def test_describe_transport_illegal_move_mermen_air_transport():
    error = TransportIllegalMoveError("mermen_air_transport", origin_coord=HexCoord(0, 0), destination_coord=HexCoord(1, 0))
    rng = ScriptedRandom([0.1] * 10)
    lines = describe_transport_illegal_move(error, "Aldric", "Greenfield", "Redhaven", rng)
    assert lines == [
        "Aldric attempted an illegal move.",
        "Aldric was ordered to move with Mermen from Greenfield to Redhaven, "
        "but had insufficient air-transport.",
    ]


def test_describe_transport_illegal_move_naval_land_hop():
    error = TransportIllegalMoveError("naval_land_hop", origin_coord=HexCoord(0, 0), destination_coord=HexCoord(1, 0))
    rng = ScriptedRandom([0.1] * 10)
    lines = describe_transport_illegal_move(error, "Aldric", "Greenfield", "Redhaven", rng)
    assert lines == [
        "Aldric attempted an illegal move.",
        "Aldric was ordered to move from Greenfield to Redhaven, but it is "
        "illegal to move naval forces from one non-sea province to another.",
    ]


def test_describe_transport_illegal_move_ent_shoreline():
    error = TransportIllegalMoveError("ent_shoreline", origin_coord=HexCoord(0, 0), destination_coord=HexCoord(1, 0))
    rng = ScriptedRandom([0.1] * 10)
    lines = describe_transport_illegal_move(error, "Aldric", "Greenfield", "Redhaven", rng)
    assert lines == [
        "Aldric attempted an illegal move.",
        "Aldric could not move from Greenfield to Redhaven because Aldric's "
        "ents refused to cross the shoreline.",
    ]


def test_describe_transport_illegal_move_dinosaur_shoreline():
    error = TransportIllegalMoveError("dinosaur_shoreline", origin_coord=HexCoord(0, 0), destination_coord=HexCoord(1, 0))
    rng = ScriptedRandom([0.1] * 10)
    lines = describe_transport_illegal_move(error, "Aldric", "Greenfield", "Redhaven", rng)
    assert lines == [
        "Aldric attempted an illegal move.",
        "Aldric could not move from Greenfield to Redhaven because Aldric's "
        "dinosaurs refused to cross the shoreline.",
    ]


def test_describe_turn_results_narrates_a_transport_illegal_move():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, HexCoord(0, 0)))
    state.add_leader(LeaderState(1, kingdom_id=1, name="Arthur", location=HexCoord(0, 0)))
    state.add_province(ProvinceState(HexCoord(0, 0), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, name="Numenor"))
    state.add_province(ProvinceState(HexCoord(1, 0), Terrain.SEA, Race.HUMAN, name="Deepwater"))
    entries = [
        PhaseDispatchResult(
            leader_id=1,
            segment_index=0,
            phase_label="P0",
            action=ActionCode.LMOVE,
            result=None,
            error=TransportIllegalMoveError(
                "insufficient_water_transport", origin_coord=HexCoord(0, 0), destination_coord=HexCoord(1, 0)
            ),
        )
    ]
    rng = ScriptedRandom([0.1] * 10)

    lines = describe_turn_results(entries, state, rng)

    assert lines == [
        "Arthur attempted an illegal move.",
        "Arthur tried to use water-borne movement to move from Numenor to "
        "Deepwater, but Arthur's transport was insufficent for the task.",
    ]


def test_describe_turn_results_transport_illegal_move_skips_an_unresolvable_leader():
    state = GameState()
    entries = [
        PhaseDispatchResult(
            leader_id=999,
            segment_index=0,
            phase_label="P0",
            action=ActionCode.LMOVE,
            result=None,
            error=TransportIllegalMoveError(
                "insufficient_water_transport", origin_coord=HexCoord(0, 0), destination_coord=HexCoord(1, 0)
            ),
        )
    ]
    rng = ScriptedRandom([0.1] * 10)

    lines = describe_turn_results(entries, state, rng)

    assert lines == []


# -- ILLMOVE_TEMPLATE (Phase 583) --------------------------------------------


def test_illmove_template_has_21_real_entries():
    assert len(ILLMOVE_TEMPLATE) == 21
    assert set(ILLMOVE_TEMPLATE.keys()) == set(range(1, 22))


def test_illmove_template_verbatim_sample():
    assert ILLMOVE_TEMPLATE[1] == (
        "< was ordered to move from ⟦CTRL-S:province-2⟧ to @, but it is "
        "illegal to move naval forces from one non-sea province to another."
    )


def test_illmove_template_choice_7_is_the_sources_own_placeholder():
    # "xxxxxxxx" is the real, unfilled content at this position in the
    # source file itself -- not a transcription gap.
    assert ILLMOVE_TEMPLATE[7] == "xxxxxxxx"


def test_illmove_template_excludes_the_authors_own_leftover_note():
    # Choice 22 ("Note: don't forget to increase #lines!! (this is line
    # 22)") is a development reminder, not real game text -- excluded.
    assert 22 not in ILLMOVE_TEMPLATE


def test_illmove_template_renders_via_prose_render():
    from ak_engine.report.prose import render

    rng = ScriptedRandom([0.1] * 10)
    result = render(ILLMOVE_TEMPLATE[2], {"<": "Aldric", "@": "Redhaven"}, rng=rng)
    assert result == "Aldric was ordered to move with whales into Redhaven, a land province.This is illegal."


# -- Monster Quest Fulfillment dialogue (Phase 129) --


def test_render_quest_mockery():
    rng = ScriptedRandom([0.1] * 10)
    result = render_quest_mockery("the Ogre", rng)
    assert result == 'snarleth the Ogre, "Ha!You fool, I\'ve tricked you!'


def test_quest_but_then_template_is_the_confirmed_hardcoded_say():
    assert QUEST_BUT_THEN_TEMPLATE == "But then "


def test_render_monster_threat_death_concatenates_both_sentences():
    rng = ScriptedRandom([0.1] * 10)
    result = render_monster_threat_death("the Ogre", rng)
    assert result == (
        'the Ogre snarled, "You impudent fool!I\'ll teach YOU to show '
        'some respect!now, prepare to die!"'
    )


def test_render_quest_item_taken_anyway_left_branch():
    rng = ScriptedRandom([0.1] * 10)
    result = render_quest_item_taken_anyway("the Ogre", rng)
    assert result == 'Sayeth the Ogre, "thank you.But I always TAKE what I want!'


def test_render_quest_item_taken_anyway_right_branch():
    rng = ScriptedRandom([0.9] * 10)
    result = render_quest_item_taken_anyway("the Ogre", rng)
    assert result == (
        'Sayeth the Ogre, "Ah, thank you very much.But I will wrest '
        "for myself what I desire!"
    )


def test_render_quest_errand_thanks_left_branch():
    rng = ScriptedRandom([0.1] * 10)
    result = render_quest_errand_thanks("the Ogre", rng)
    assert result == 'Sayeth the Ogre, "You have done well.'


def test_render_quest_errand_thanks_right_branch():
    rng = ScriptedRandom([0.9] * 10)
    result = render_quest_errand_thanks("the Ogre", rng)
    assert result == 'Sayeth the Ogre, "You have served me admirably, and you have my gratitude.'


def test_render_quest_wrong_answer_left_branch():
    rng = ScriptedRandom([0.1] * 10)
    result = render_quest_wrong_answer("the Ogre", rng)
    assert result == 'Sayeth the Ogre, "No!That is not the answer I had in mind.Why don\'t you give up?"'


def test_render_quest_wrong_answer_right_branch():
    rng = ScriptedRandom([0.9] * 10)
    result = render_quest_wrong_answer("the Ogre", rng)
    assert result == (
        'Sayeth the Ogre, "No!That is not the answer I was thinking of.'
        'Why don\'t you give up, you idiot?"'
    )


def test_render_quest_progress_acknowledged_left_branch():
    rng = ScriptedRandom([0.1] * 10)
    result = render_quest_progress_acknowledged("the Ogre", rng)
    assert result == 'Sayeth the Ogre, "You have served me well.I shall remember you."'


def test_render_quest_progress_acknowledged_right_branch():
    rng = ScriptedRandom([0.9] * 10)
    result = render_quest_progress_acknowledged("the Ogre", rng)
    assert result == 'Sayeth the Ogre, "You have done well.I shall not forget your deed."'


def test_render_quest_insufficient_skill():
    rng = ScriptedRandom([0.1] * 10)
    result = render_quest_insufficient_skill("the Ogre", rng)
    assert result == 'Sayeth the Ogre, "You haven\'t the skill required to do as I\'ve asked!Go away!"'


def test_render_quest_insufficient_price():
    rng = ScriptedRandom([0.1] * 10)
    result = render_quest_insufficient_price("the Ogre", rng)
    assert result == 'Sayeth the Ogre, "You have not met my asking price!Go away!"'


def test_render_quest_service_not_performed_left_branch():
    rng = ScriptedRandom([0.1] * 10)
    result = render_quest_service_not_performed("the Ogre", rng)
    assert result == 'Sayeth the Ogre, "You have not done as I asked!Go away!"'


def test_render_quest_service_not_performed_right_branch():
    rng = ScriptedRandom([0.9] * 10)
    result = render_quest_service_not_performed("the Ogre", rng)
    assert result == 'Sayeth the Ogre, "You have not performed the service I wished at all!Go away!"'


def test_render_quest_fled_in_fear():
    rng = ScriptedRandom([0.1] * 10)
    result = render_quest_fled_in_fear("Aldric", "the Ogre", rng)
    assert result == "But as Aldric approached the Ogre, Aldric lost Aldric's courage and ran away from the Ogre."


def test_render_quest_hero_not_tasty():
    rng = ScriptedRandom([0.1] * 10)
    result = render_quest_hero_not_tasty("the Ogre", rng)
    assert result == (
        'Sayeth the Ogre, "That one did not taste like a Hero!Next time '
        'bring me something tastier.Now, go away!"'
    )


def test_render_quest_no_agreement():
    rng = ScriptedRandom([0.1] * 10)
    result = render_quest_no_agreement("the Ogre", rng)
    assert result == 'Sayeth the Ogre, "Fulfill what?We have not talked over any agreement!Go away!"'


def test_render_quest_reward_already_given():
    rng = ScriptedRandom([0.1] * 10)
    result = render_quest_reward_already_given("the Ogre", "Ring of Power", rng)
    assert result == (
        'Sayeth the Ogre, "I have already given away the Ring of Power '
        'to a worthier adventurer.Go away!"'
    )


# -- RIDDLE.X2/RANS.X/VISIT.X2/FUVIS.X2 (Phase 582) --


def test_quest_riddle_text_and_answer_text_cover_all_seven_ra_ordinals():
    ra_members = {t for t in Treasure if t.name.startswith("QUEST_RA_")}
    assert len(ra_members) == 7
    assert set(QUEST_RIDDLE_TEXT.keys()) == ra_members
    assert set(QUEST_RIDDLE_ANSWER_TEXT.keys()) == ra_members


def test_quest_riddle_text_man_is_the_riddle_of_the_sphinx():
    assert QUEST_RIDDLE_TEXT[Treasure.QUEST_RA_MAN] == (
        '"\'What goes on four legs in the morning, two at midday and '
        'three legs in the evening?\''
    )


def test_quest_riddle_answer_text_congratulates_on_every_ordinal():
    # RANS.X does NOT close QUEST_MOCKERY_TEMPLATE's own unclosed quote
    # (a previous, now-withdrawn hypothesis) -- every one of its 7
    # entries is instead the monster confirming the answer was right.
    for text in QUEST_RIDDLE_ANSWER_TEXT.values():
        assert text.startswith("Sayeth [, ")


def test_render_guardian_poses_riddle_resolves_the_ctrl_a_marker():
    # Phase 1027. "monster" is consonant-initial -> "a", "end" is
    # vowel-initial -> "an" -- the one real, deterministic grammar rule
    # this project resolves for this catalog; every other sourced word
    # is untouched.
    result = render_guardian_poses_riddle("the Sphinx", Treasure.QUEST_RA_RIDDLE)
    assert result == (
        'the Sphinx poses a riddle: "\'I am a monster, strange and alien.A band '
        "of hunters follows behind me looking for the tracks made by my feet."
        "They desire greatly to put me to an end, yet they seek no meat, only "
        "knowledge.i inhabit the darkest places, and if I pass from the shadows "
        "into the bright light my soul quickly slips away.What am I?'"
    )


def test_render_guardian_poses_riddle_collapses_coffins_stanza_markers():
    result = render_guardian_poses_riddle("the Mummy", Treasure.QUEST_RA_COFFIN)
    assert "$+" not in result
    assert result.startswith('the Mummy poses a riddle: "Solve this riddle: There was a man bespake a thing,')


def test_render_guardian_poses_riddle_leaves_plain_entries_untouched():
    # QUEST_RA_BRIDGE/MAN carry no CTRL-byte markers at all -- the
    # sourced text passes straight through, verbatim.
    assert render_guardian_poses_riddle("the Troll", Treasure.QUEST_RA_BRIDGE) == (
        f"the Troll poses a riddle: {QUEST_RIDDLE_TEXT[Treasure.QUEST_RA_BRIDGE]}"
    )


def test_quest_visit_text_and_fulfilled_text_cover_the_five_location_quests():
    location_quests = {
        Treasure.QUEST_SNOW_QUEST,
        Treasure.QUEST_SAPPH_RING,
        Treasure.QUEST_LUCKY_PENNY,
        Treasure.QUEST_GODS_QUEST,
        Treasure.QUEST_MERMAID_AMULET,
    }
    assert set(QUEST_VISIT_TEXT.keys()) == location_quests
    assert set(QUEST_VISIT_FULFILLED_TEXT.keys()) == location_quests


def test_quest_visit_fulfilled_text_verbatim_sample():
    assert QUEST_VISIT_FULFILLED_TEXT[Treasure.QUEST_LUCKY_PENNY] == (
        "While < was in @, < found ⟦CTRL-A:a/an⟧ wishing-well which matched the "
        "description < had been given.< took the Lucky Penny, wished for luck "
        "and tossed it into the well."
    )


def test_quest_visit_text_control_byte_codes_preserved_literally():
    # Not resolved -- render() has no defined behavior for these, see
    # module docstring's own Phase 582 addendum.
    assert "⟦CTRL-X:province-3⟧" in QUEST_VISIT_TEXT[Treasure.QUEST_SNOW_QUEST]


def test_render_guardian_proposes_quest_location_resolves_the_ctrl_a_marker():
    # Phase 1028. GODS_QUEST carries no CTRL-A marker at all -- GODS_QUEST
    # is covered separately below; this one (LUCKY_PENNY) has exactly one
    # CTRL-A marker ("wishing-well" is consonant-initial -> "a").
    result = render_guardian_proposes_quest_location("the Hermit", Treasure.QUEST_LUCKY_PENNY)
    assert result == (
        "the Hermit proposes a quest: the province of my birth, there is a "
        "wishing-well which I remember from my younger days.For me, it is the "
        "luckiest well in the world.You see, for years I have been having bad "
        "luck.take my lucky penny and journey to the well.When you get there, "
        "wish me luck and toss it into the well.Then, maybe my luck will "
        "change!"
    )


def test_render_guardian_proposes_quest_location_resolves_the_ctrl_x_marker_to_a_generic_placeholder():
    # SNOW_QUEST and MERMAID_AMULET are the only two entries carrying the
    # real province-reference marker -- resolved to a generic phrase per
    # explicit user instruction, never an invented specific province.
    snow = render_guardian_proposes_quest_location("the Oracle", Treasure.QUEST_SNOW_QUEST)
    assert "⟦CTRL-X:province-3⟧" not in snow
    assert "a distant province" in snow

    mermaid = render_guardian_proposes_quest_location("the Oracle", Treasure.QUEST_MERMAID_AMULET)
    assert "⟦CTRL-X:province-3⟧" not in mermaid
    assert "a distant province" in mermaid
    assert "charm a mermaid for me" in mermaid


def test_render_guardian_proposes_quest_location_leaves_plain_entries_untouched():
    # GODS_QUEST carries no CTRL-byte markers at all -- the sourced text
    # passes straight through, verbatim.
    assert render_guardian_proposes_quest_location("the Shaman", Treasure.QUEST_GODS_QUEST) == (
        f"the Shaman proposes a quest: {QUEST_VISIT_TEXT[Treasure.QUEST_GODS_QUEST]}"
    )


# -- monster raid-truce offer (Phase 130) --


def test_render_monster_offers_raid_truce_left_branch():
    rng = ScriptedRandom([0.1] * 10)
    result = render_monster_offers_raid_truce("the Ogre", "Greenfield", rng)
    assert result == "the Ogre also offered to stop raiding Greenfield if this quest be accomplished."


def test_render_monster_offers_raid_truce_right_branch():
    rng = ScriptedRandom([0.9] * 10)
    result = render_monster_offers_raid_truce("the Ogre", "Greenfield", rng)
    assert result == "the Ogre also offered to stop plundering Greenfield if this quest were completed."


# -- Trade/Give narrative cluster (Phase 133) --


def test_render_item_give():
    rng = ScriptedRandom([])
    result = render_item_give("Aldric", "Borin", "Ring of Power", rng)
    assert result == "Aldric gave the Ring of Power to Borin."


def test_render_gold_give_left_branch():
    rng = ScriptedRandom([0.1, 0.1])
    result = render_gold_give("Aldric", "Borin", 100, rng)
    assert result == "Aldric gave to Borin 100 gold from Aldric's treasury."


def test_render_gold_give_right_branch():
    rng = ScriptedRandom([0.9, 0.9])
    result = render_gold_give("Aldric", "Borin", 100, rng)
    assert result == "Aldric donated to Borin 100 gold from Aldric's own funds."


def test_render_insufficient_gold():
    rng = ScriptedRandom([])
    result = render_insufficient_gold("Aldric", 100, rng)
    assert result == "Aldric didn't have on hand the full 100 gold requested, so "


def test_render_trade_deal_failed():
    rng = ScriptedRandom([])
    result = render_trade_deal_failed("Aldric", "Borin", "Ring of Power", rng)
    assert result == "Aldric could not strike a deal with Borin for the Ring of Power."


# -- describe_give (integration, Phase 142) --


def test_describe_give_renders_a_successful_item_transfer():
    result = TradeExecutionResult(applied=True, item_transferred=True)
    rng = ScriptedRandom([])

    line = describe_give(result, giver_name="Aldric", recipient_name="Borin", item_name="Ring of Power", rng=rng)

    assert line == "Aldric gave the Ring of Power to Borin."


def test_describe_give_item_transfer_without_a_name_renders_nothing():
    # No item-instance display-name synthesis exists -- see describe_give()'s
    # own docstring, same caller-supplies-names convention as describe_battle.
    result = TradeExecutionResult(applied=True, item_transferred=True)
    rng = ScriptedRandom([])

    line = describe_give(result, giver_name="Aldric", recipient_name="Borin", rng=rng)

    assert line is None


def test_describe_give_renders_a_successful_gold_transfer():
    result = TradeExecutionResult(applied=True, gold_transferred=100)
    rng = ScriptedRandom([0.1, 0.1])

    line = describe_give(result, giver_name="Aldric", recipient_name="Borin", rng=rng)

    assert line == "Aldric gave to Borin 100 gold from Aldric's treasury."


def test_describe_give_renders_insufficient_gold_on_the_10_percent_cap_failure():
    result = TradeExecutionResult(applied=False, reason="exceeds 10% treasury cap (25)")
    rng = ScriptedRandom([])

    line = describe_give(result, giver_name="Aldric", recipient_name="Borin", gold_requested=100, rng=rng)

    assert line == "Aldric didn't have on hand the full 100 gold requested, so "


def test_describe_give_insufficient_gold_without_amount_renders_nothing():
    result = TradeExecutionResult(applied=False, reason="exceeds 10% treasury cap (25)")
    rng = ScriptedRandom([])

    line = describe_give(result, giver_name="Aldric", recipient_name="Borin", rng=rng)

    assert line is None


def test_describe_give_renders_nothing_for_an_unsourced_failure_reason():
    # e.g. "recipient not found", "not co-located", "gold Give recipient
    # must be a King" -- no SAY.PAS template exists for these.
    result = TradeExecutionResult(applied=False, reason="recipient not found")
    rng = ScriptedRandom([])

    line = describe_give(result, giver_name="Aldric", recipient_name="Borin", gold_requested=100, rng=rng)

    assert line is None


# -- describe_curator_research (Phase 667) --


def test_describe_curator_research_renders_a_successful_lookup():
    result = CuratorResearchResult(applied=True, item_id=42, treasure=Treasure.WAND_FIREBALL)
    rng = ScriptedRandom([])

    line = describe_curator_research(result, researcher_name="Aldric", rng=rng)

    assert line == f"The Guild of Sages researched item number 42 for Aldric: it is a {TREASURE_NAME[Treasure.WAND_FIREBALL]}."


def test_describe_curator_research_failed_lookup_renders_nothing():
    result = CuratorResearchResult(applied=False, item_id=999, reason="no such item number exists in the world")
    rng = ScriptedRandom([])

    line = describe_curator_research(result, researcher_name="Aldric", rng=rng)

    assert line is None


# -- render_cast_announcement / describe_cast (Phase 145) --


def test_render_cast_announcement_target_spell_continued():
    rng = ScriptedRandom([])
    result = render_cast_announcement(Spell.KILL_ENEMY, "Aldric", rng, target_name="Borin")
    assert result == "Aldric cast a Kill Enemy spell and Borin was magically killed by a dark Necromantic spell!"


def test_render_cast_announcement_province_spell_continued():
    rng = ScriptedRandom([])
    result = render_cast_announcement(Spell.EARTHQUAKE, "Aldric", rng, province_name="Province")
    assert result == "Aldric cast a Earthquake spell and Province was devastated by an earthquake!"


def test_render_cast_announcement_complete_sentence_spell():
    # Bless is one of the 3 CAST_SPELL_OPENING_COMPLETE_SPELLS (_LCast1's own
    # CASE Tornado,Bless,Plague) -- no "and" joiner, and no space is inserted
    # either, matching _LCast1's literal source text.
    rng = ScriptedRandom([])
    result = render_cast_announcement(Spell.BLESS, "Aldric", rng, province_name="Province")
    assert result == "Aldric cast a Bless spell.Province was magically blessed and prospered."


def test_render_cast_announcement_army_list_and_province():
    rng = ScriptedRandom([])
    result = render_cast_announcement(
        Spell.TORNADO, "Aldric", rng, province_name="Province", army_names=["1st Legion"]
    )
    assert result == "Aldric cast a Tornado spell.tornadoes sucked up 1st Legion in Province and destroyed them."


def test_render_cast_announcement_illus_terrain_needs_terrain_name():
    rng = ScriptedRandom([])
    result = render_cast_announcement(
        Spell.ILLUS_TERRAIN, "Aldric", rng, province_name="Province", terrain_name="Desert"
    )
    assert result == "Aldric cast a Illusory Terrain spell and Province had an illusion cast upon it.It was actually a Desert province."


def test_render_cast_announcement_skeletal_army_list_only():
    rng = ScriptedRandom([])
    result = render_cast_announcement(Spell.SKELETAL_ARMY, "Aldric", rng, army_names=["1st Legion"])
    assert result == "Aldric cast a Skeletal Army spell and 1st Legion arose from the graves of the dead!"


def test_render_cast_announcement_resurrection_reuses_caster_and_target_markers():
    # Phase 938 correction: Resurrection gets no "< cast a ~ spell and "
    # opening at all on a successful cast -- real fixture text never
    # shows one (see render_cast_announcement()'s own Phase 938 note).
    # RESURRECTION's own SPELL_CAST_ANNOUNCEMENT entry references the caster
    # a second time via <2 and the target via [1 -- same real duplicate-marker
    # shape render_battle_winner() already established for <2 (Phase 61).
    rng = ScriptedRandom([])
    result = render_cast_announcement(Spell.RESURRECTION, "Aldric", rng, target_name="Borin")
    assert result == "Borin was resurrected by the spell cast by Aldric."


def test_render_cast_announcement_oratory_has_no_double_cast_clause():
    # Phase 938 correction: this test used to assert the "cast a spell...
    # cast a spell" double statement as an honestly-transcribed real
    # oddity -- real fixture text (SE3__T5/T7.K1: "I cast a spell giving
    # magical powers of oratory to me.") proves there's no opening clause
    # at all on a successful cast, so no doubling ever happens for real.
    rng = ScriptedRandom([])
    result = render_cast_announcement(Spell.ORATORY, "Aldric", rng, target_name="Borin")
    assert result == "Aldric cast a spell giving magical powers of oratory to Borin."


def test_render_cast_announcement_charm_leading_period_and_r_choices():
    # Charm's own SPNOTE.X2 entry starts with a bare "." (a real, honestly
    # transcribed oddity, the same "transcribe verbatim, don't silently fix"
    # stance already taken for CONTROL_UNDEAD's truncation and the Mermen
    # "air-transport" wording, Phase 127). 3 "/R" choices, all scripted left.
    # Phase 938: this is the real Encounter-context text -- the top-level
    # Cast action's own real narration uses render_charm_outcome() instead
    # (a wholly different, confirmed-by-fixture sentence) -- see that
    # function's own docstring. render_cast_announcement() itself still
    # works for this entry directly, unchanged.
    rng = ScriptedRandom([0.1, 0.1, 0.1])
    result = render_cast_announcement(Spell.CHARM, "Aldric", rng, target_name="Borin")
    assert result == "Aldric cast a Charm spell and .Aldric befriended Borin and used Aldric's respite to escape."


def test_render_cast_announcement_clairvoyance_has_no_double_cast_clause():
    # Phase 938 correction: this test used to assert a "cast a spell...
    # cast a spell" double statement as an honestly-transcribed real
    # oddity -- inferred (not directly fixture-confirmed, see
    # render_cast_announcement()'s own Phase 938 note) to have no opening
    # clause at all, the same as Oratory's own confirmed case. Its own
    # SPNOTE.X2 entry already begins with "< cast a ~ spell and..." as a
    # complete, self-contained sentence.
    rng = ScriptedRandom([])
    result = render_cast_announcement(Spell.CLAIRVOYANCE, "Aldric", rng, target_name="Borin")
    assert result == "Aldric cast a Clairvoyance spell and could see everything that happened to Borin."


def test_render_cast_announcement_hide_feature_needs_feature_and_province_name():
    rng = ScriptedRandom([])
    result = render_cast_announcement(
        Spell.HIDE_FEATURE, "Aldric", rng, province_name="Province", feature_name="Sacred Rock"
    )
    assert result == "Aldric cast a Hide Feature spell and the Sacred Rock in Province was magically hidden."


def test_render_cast_announcement_missing_target_name_raises():
    rng = ScriptedRandom([])
    with pytest.raises(ValueError, match="target_name"):
        render_cast_announcement(Spell.KILL_ENEMY, "Aldric", rng)


def test_render_cast_announcement_missing_province_name_raises():
    rng = ScriptedRandom([])
    with pytest.raises(ValueError, match="province_name"):
        render_cast_announcement(Spell.EARTHQUAKE, "Aldric", rng)


def test_render_cast_announcement_missing_army_names_raises():
    rng = ScriptedRandom([])
    with pytest.raises(ValueError, match="army_names"):
        render_cast_announcement(Spell.SKELETAL_ARMY, "Aldric", rng)


def test_render_cast_announcement_missing_terrain_name_raises():
    rng = ScriptedRandom([])
    with pytest.raises(ValueError, match="terrain_name"):
        render_cast_announcement(Spell.ILLUS_TERRAIN, "Aldric", rng, province_name="Province")


def test_render_cast_announcement_missing_feature_name_raises():
    rng = ScriptedRandom([])
    with pytest.raises(ValueError, match="feature_name"):
        render_cast_announcement(Spell.HIDE_FEATURE, "Aldric", rng, province_name="Province")


def test_render_cast_announcement_unmapped_spell_raises():
    # Spell.GATE_ANGEL is one of the 10 "secret" spells SPNOTE.X2 never
    # documented -- see SPELL_CAST_ANNOUNCEMENT's own docstring.
    rng = ScriptedRandom([])
    with pytest.raises(ValueError, match="no SPELL_CAST_ANNOUNCEMENT entry"):
        render_cast_announcement(Spell.GATE_ANGEL, "Aldric", rng)


# -- Bless's own graveyard-cleanup companion sentence (Phase 935) -----------


def test_render_bless_graveyard_outcome_with_nothing_cleared():
    rng = ScriptedRandom([])
    result = render_bless_graveyard_outcome("Sageleaf", [], rng)
    assert result == "The Bless affected no armies in Sageleaf."


def test_render_bless_graveyard_outcome_with_one_army_cleared():
    rng = ScriptedRandom([])
    result = render_bless_graveyard_outcome("Kajaani", [ArmyType.LT_CAVALRY], rng)
    assert result == "The skeletal remains of the Light Cavalry were Blessed and permanently destroyed."


def test_render_bless_graveyard_outcome_with_multiple_armies_cleared():
    # Real fixture text (SE3__T10.K1): "The skeletal remains of the 48th
    # Chariots, the 216th Axemen and the 227th Light Cavalry were Blessed
    # and permanently destroyed." -- no per-army ordinal survives in
    # GraveyardEntry (see this function's own docstring), so this project
    # renders the bare ArmyType name instead of inventing one.
    rng = ScriptedRandom([])
    result = render_bless_graveyard_outcome(
        "Ngara", [ArmyType.CHARIOTS, ArmyType.AXEMEN, ArmyType.LT_CAVALRY], rng
    )
    assert result == (
        "The skeletal remains of the Chariots, the Axemen and the Light Cavalry "
        "were Blessed and permanently destroyed."
    )


def test_describe_cast_appends_the_bless_graveyard_outcome():
    result = CastExecutionResult(
        request=CastRequest(spell=Spell.BLESS, target=0), applied=True,
        bless_graveyard_cleared=[ArmyType.LEGION],
    )
    rng = ScriptedRandom([])

    line = describe_cast(result, caster_name="Aldric", rng=rng, province_name="Sageleaf")

    assert line == (
        "Aldric cast a Bless spell.Sageleaf was magically blessed and prospered."
        "The skeletal remains of the Legion were Blessed and permanently destroyed."
    )


def test_describe_cast_appends_the_bless_unaffected_outcome_by_default():
    result = CastExecutionResult(request=CastRequest(spell=Spell.BLESS, target=0), applied=True)
    rng = ScriptedRandom([])

    line = describe_cast(result, caster_name="Aldric", rng=rng, province_name="Sageleaf")

    assert line == (
        "Aldric cast a Bless spell.Sageleaf was magically blessed and prospered."
        "The Bless affected no armies in Sageleaf."
    )


# -- Skeletal Army's own real cast outcome (Phase 936) -----------------------


def test_render_skeletal_army_outcome_with_nothing_raised():
    rng = ScriptedRandom([])
    result = render_skeletal_army_outcome("Aldric", [], rng)
    assert result == "Aldric cast a Skeletal Army spell and no skeletons answered the spell's call."


def test_render_skeletal_army_outcome_with_armies_raised():
    # Real fixture text (SE3__T10.K1): "...the 250th Skeletal Bowmen,
    # the 172nd Skeletal Legion..." -- full "Skeletal" wording and full
    # ARMY_TYPE_NAME designation, not the Army List table's own
    # abbreviated "Skel"/"Lt Cav" convention (see this function's own
    # docstring for the full sourcing).
    rng = ScriptedRandom([])
    raised = [
        ArmyState(250, 1, ArmyType.BOWMEN, Quality.AVERAGE, HexCoord(0, 0), is_skeletal=True),
        ArmyState(172, 1, ArmyType.LT_CAVALRY, Quality.AVERAGE, HexCoord(0, 0), is_skeletal=True),
    ]

    result = render_skeletal_army_outcome("Aldric", raised, rng)

    assert result == (
        "Aldric cast a Skeletal Army spell and the 250th Skeletal Bowmen "
        "and the 172nd Skeletal Light Cavalry arose from the graves of the dead!"
    )


def test_describe_cast_uses_the_skeletal_army_outcome_when_nothing_raised():
    result = CastExecutionResult(request=CastRequest(spell=Spell.SKELETAL_ARMY, target=0), applied=True)
    rng = ScriptedRandom([])

    line = describe_cast(result, caster_name="Aldric", rng=rng)

    assert line == "Aldric cast a Skeletal Army spell and no skeletons answered the spell's call."


def test_describe_cast_uses_the_skeletal_army_outcome_when_armies_raised():
    raised = [ArmyState(250, 1, ArmyType.BOWMEN, Quality.AVERAGE, HexCoord(0, 0), is_skeletal=True)]
    result = CastExecutionResult(
        request=CastRequest(spell=Spell.SKELETAL_ARMY, target=0), applied=True, skeletal_army_raised=raised,
    )
    rng = ScriptedRandom([])

    line = describe_cast(result, caster_name="Aldric", rng=rng)

    assert line == "Aldric cast a Skeletal Army spell and the 250th Skeletal Bowmen arose from the graves of the dead!"


# -- Tornado's own real cast outcome (Phase 937) -----------------------------


def test_render_tornado_outcome_with_nothing_destroyed():
    rng = ScriptedRandom([])
    result = render_tornado_outcome("Aldric", "Kajaani", [], [], rng)
    assert result == (
        "Aldric cast a Tornado spell.Magical tornadoes hit the defenders of Kajaani."
        "The Tornado affected no armies in Kajaani."
    )


def test_render_tornado_outcome_with_armies_destroyed():
    # Real fixture text (SE3__T6.K1): each destroyed army gets its own
    # repeated sentence, not a combined "X, Y and Z" list (see this
    # function's own docstring for the full sourcing).
    rng = ScriptedRandom([])
    destroyed = [
        ArmyState(20, 2, ArmyType.LEGION, Quality.AVERAGE, HexCoord(0, 0)),
        ArmyState(21, 2, ArmyType.LT_CAVALRY, Quality.AVERAGE, HexCoord(0, 0)),
    ]

    result = render_tornado_outcome("Aldric", "Limerick", destroyed, [], rng)

    assert result == (
        "Aldric cast a Tornado spell.Magical tornadoes hit the defenders of Limerick."
        "Tornadoes sucked up the 20th Legion in Limerick and destroyed them."
        "Tornadoes sucked up the 21st Light Cavalry in Limerick and destroyed them."
    )


def test_describe_cast_uses_the_tornado_outcome_when_nothing_destroyed():
    result = CastExecutionResult(request=CastRequest(spell=Spell.TORNADO, target=0), applied=True)
    rng = ScriptedRandom([])

    line = describe_cast(result, caster_name="Aldric", rng=rng, province_name="Kajaani")

    assert line == (
        "Aldric cast a Tornado spell.Magical tornadoes hit the defenders of Kajaani."
        "The Tornado affected no armies in Kajaani."
    )


def test_describe_cast_uses_the_tornado_outcome_when_armies_destroyed():
    destroyed = [ArmyState(20, 2, ArmyType.LEGION, Quality.AVERAGE, HexCoord(0, 0))]
    result = CastExecutionResult(
        request=CastRequest(spell=Spell.TORNADO, target=0), applied=True, tornado_destroyed=destroyed,
    )
    rng = ScriptedRandom([])

    line = describe_cast(result, caster_name="Aldric", rng=rng, province_name="Limerick")

    assert line == (
        "Aldric cast a Tornado spell.Magical tornadoes hit the defenders of Limerick."
        "Tornadoes sucked up the 20th Legion in Limerick and destroyed them."
    )


def test_describe_cast_uses_the_tornado_outcome_when_a_giant_fan_army_is_downgraded():
    # Phase 948: result.tornado_quality_downgraded reaches describe_cast()
    # too, not just the destroy list.
    quality_downgraded = [ArmyState(21, 2, ArmyType.LT_CAVALRY, Quality.AVERAGE, HexCoord(0, 0))]
    result = CastExecutionResult(
        request=CastRequest(spell=Spell.TORNADO, target=0), applied=True, tornado_quality_downgraded=quality_downgraded,
    )
    rng = ScriptedRandom([])

    line = describe_cast(result, caster_name="Aldric", rng=rng, province_name="Limerick")

    assert line == (
        "Aldric cast a Tornado spell.Magical tornadoes hit the defenders of Limerick."
        "The Tornado spell struck the 21st Light Cavalry in Limerick and reduced them by one quality level."
    )


def test_render_charm_outcome():
    rng = ScriptedRandom([])
    result = render_charm_outcome("Melantheus", "Uga-Buga Makumb", rng)
    assert result == "Melantheus was magically charmed by Uga-Buga Makumb."


def test_describe_cast_uses_the_charm_outcome():
    result = CastExecutionResult(request=CastRequest(spell=Spell.CHARM, target=0), applied=True)
    rng = ScriptedRandom([])

    line = describe_cast(result, caster_name="Uga-Buga Makumb", rng=rng, target_name="Melantheus")

    assert line == "Melantheus was magically charmed by Uga-Buga Makumb."


def test_render_illus_terrain_cast_outcome():
    # Phase 943: Illusory Terrain's own real top-level-cast text is
    # _STerIl's (the same one render_illus_terrain_world_event() already
    # renders for the bystander/GIR view), not SPELL_CAST_ANNOUNCEMENT[
    # Spell.ILLUS_TERRAIN]'s own catalog entry (that one is real too, just
    # for a different dispatch -- _LSeeI, a still-unwired movement-
    # discovery reveal). Real fixture text (SE3__T11.K1): "I cast a
    # Illusory Terrain spell and the Plain terrain of Kajaani was
    # magically made to appear as Mountain."
    rng = ScriptedRandom([])
    result = render_illus_terrain_cast_outcome("Teleko", "Plain", "Kajaani", "Mountain", rng)
    assert result == "Teleko cast a Illusory Terrain spell and the Plain terrain of Kajaani was magically made to appear as Mountain."


def test_describe_cast_uses_the_illus_terrain_cast_outcome():
    result = CastExecutionResult(request=CastRequest(spell=Spell.ILLUS_TERRAIN, target=0), applied=True)
    rng = ScriptedRandom([])

    line = describe_cast(
        result, caster_name="Teleko", rng=rng, province_name="Kajaani", terrain_name="Mountain", real_terrain_name="Plain"
    )

    assert line == "Teleko cast a Illusory Terrain spell and the Plain terrain of Kajaani was magically made to appear as Mountain."


def test_render_plague_outcome_with_nothing_destroyed():
    rng = ScriptedRandom([])
    result = render_plague_outcome("Aldric", "Sageleaf", [], [], rng)
    assert result == "Aldric cast a Plague spell.Sageleaf was hit by a plague.The Plague affected no armies in Sageleaf."


def test_render_plague_outcome_with_armies_destroyed():
    # Phase 944: real fixture text (SE3__T7.K1/T10.K1) shows the same
    # repeated-sentence pattern Tornado already established as this
    # project's own majority-supported default for a multi-army destroy
    # list, not SPELL_CAST_ANNOUNCEMENT[Spell.PLAGUE]'s own joined `^L=`
    # catalog entry.
    destroyed = [
        ArmyState(244, 2, ArmyType.HVY_CAVALRY, Quality.AVERAGE, HexCoord(0, 0)),
        ArmyState(276, 2, ArmyType.HVY_CAVALRY, Quality.AVERAGE, HexCoord(0, 0)),
    ]
    rng = ScriptedRandom([])
    result = render_plague_outcome("Aldric", "Kajaani", destroyed, [], rng)
    assert result == (
        "Aldric cast a Plague spell.Kajaani was hit by a plague."
        "The plague struck the 244th Heavy Cavalry in Kajaani and destroyed them."
        "The plague struck the 276th Heavy Cavalry in Kajaani and destroyed them."
    )


def test_render_plague_outcome_with_quality_downgraded_armies():
    # Phase 948: real fixture text (SE3__T11.K1's own Rejaf paragraph)
    # shows a destroy sentence and a quality-downgrade sentence together
    # in one cast's own outcome, destroy first.
    destroyed = [ArmyState(109, 2, ArmyType.HVY_CAVALRY, Quality.AVERAGE, HexCoord(0, 0))]
    quality_downgraded = [ArmyState(209, 2, ArmyType.WARG_RIDERS, Quality.AVERAGE, HexCoord(0, 0))]
    rng = ScriptedRandom([])
    result = render_plague_outcome("Aldric", "Rejaf", destroyed, quality_downgraded, rng)
    assert result == (
        "Aldric cast a Plague spell.Rejaf was hit by a plague."
        "The plague struck the 109th Heavy Cavalry in Rejaf and destroyed them."
        "The Plague spell struck the 209th Warg Riders in Rejaf and reduced them by one quality level."
    )


def test_render_tornado_outcome_with_quality_downgraded_armies():
    # Phase 948: Tornado's own inferred quality-downgrade text (Giant
    # Fan), same shape as Plague's own fixture-confirmed version.
    destroyed = [ArmyState(20, 2, ArmyType.LEGION, Quality.AVERAGE, HexCoord(0, 0))]
    quality_downgraded = [ArmyState(21, 2, ArmyType.LT_CAVALRY, Quality.AVERAGE, HexCoord(0, 0))]
    rng = ScriptedRandom([])
    result = render_tornado_outcome("Aldric", "Limerick", destroyed, quality_downgraded, rng)
    assert result == (
        "Aldric cast a Tornado spell.Magical tornadoes hit the defenders of Limerick."
        "Tornadoes sucked up the 20th Legion in Limerick and destroyed them."
        "The Tornado spell struck the 21st Light Cavalry in Limerick and reduced them by one quality level."
    )


def test_describe_cast_uses_the_plague_outcome():
    destroyed = [ArmyState(55, 2, ArmyType.GARRISON, Quality.AVERAGE, HexCoord(0, 0))]
    result = CastExecutionResult(request=CastRequest(spell=Spell.PLAGUE, target=0), applied=True, plague_destroyed=destroyed)
    rng = ScriptedRandom([])

    line = describe_cast(result, caster_name="Alaric", rng=rng, province_name="Cascadia")

    assert line == (
        "Alaric cast a Plague spell.Cascadia was hit by a plague."
        "The plague struck the 55th Garrison in Cascadia and destroyed them."
    )


def test_describe_cast_uses_the_plague_outcome_with_a_quality_downgraded_army():
    # Phase 948: result.plague_quality_downgraded reaches describe_cast()
    # too, not just the destroy list.
    quality_downgraded = [ArmyState(209, 2, ArmyType.WARG_RIDERS, Quality.AVERAGE, HexCoord(0, 0))]
    result = CastExecutionResult(
        request=CastRequest(spell=Spell.PLAGUE, target=0), applied=True, plague_quality_downgraded=quality_downgraded
    )
    rng = ScriptedRandom([])

    line = describe_cast(result, caster_name="Alaric", rng=rng, province_name="Rejaf")

    assert line == (
        "Alaric cast a Plague spell.Rejaf was hit by a plague."
        "The Plague spell struck the 209th Warg Riders in Rejaf and reduced them by one quality level."
    )


def test_render_flood_cast_outcome():
    # Phase 945: Flood's own real top-level-cast text is _SFlood's (the
    # same one render_flood_world_event() already renders for the
    # bystander/GIR view), not SPELL_CAST_ANNOUNCEMENT[Spell.FLOOD]'s own
    # catalog entry (that one is real too, just for a different, still-
    # unwired dispatch -- _ASlow, whose own trigger condition has zero
    # confirmed real fixture occurrences). Real fixture text (SE3__T6.K1):
    # "I cast a Flood spell and Limerick was magically flooded."
    rng = ScriptedRandom([])
    result = render_flood_cast_outcome("Aldric", "Limerick", rng)
    assert result == "Aldric cast a Flood spell and Limerick was magically flooded."


def test_describe_cast_uses_the_flood_cast_outcome():
    result = CastExecutionResult(request=CastRequest(spell=Spell.FLOOD, target=0), applied=True)
    rng = ScriptedRandom([])

    line = describe_cast(result, caster_name="Clarambald", rng=rng, province_name="Ngara")

    assert line == "Clarambald cast a Flood spell and Ngara was magically flooded."


def test_describe_cast_renders_the_announcement_when_applied():
    result = CastExecutionResult(request=CastRequest(spell=Spell.KILL_ENEMY, target=0), applied=True)
    rng = ScriptedRandom([])

    line = describe_cast(result, caster_name="Aldric", rng=rng, target_name="Borin")

    assert line == "Aldric cast a Kill Enemy spell and Borin was magically killed by a dark Necromantic spell!"


def test_describe_cast_renders_nothing_when_not_applied():
    result = CastExecutionResult(
        request=CastRequest(spell=Spell.KILL_ENEMY, target=0), applied=False, reason="cast roll failed"
    )
    rng = ScriptedRandom([])

    line = describe_cast(result, caster_name="Aldric", rng=rng, target_name="Borin")

    assert line is None


# -- Locate Object (Phase 878, project-original text) ------------------------


def test_render_locate_object():
    rng = ScriptedRandom([0.1])  # picks "divined", not the /R alternate "sensed"

    line = render_locate_object("Aldric", "Wand of Fire", "Capital City", "Borin", rng)

    assert line == "Aldric divined that the Wand of Fire was located in Capital City, held by Borin."


def test_describe_locate_object_narrates_a_successful_find():
    state = GameState()
    state.add_leader(LeaderState(50, 1, "Borin", HexCoord(0, 0)))
    state.add_province(ProvinceState(HexCoord(0, 0), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, name="Capital City"))
    item = state.add_item(Treasure.WAND_FIREBALL, owner_leader_id=50)
    result = CastExecutionResult(
        request=CastRequest(spell=Spell.LOCATE_OBJECT, target=item.item_id),
        applied=True,
        located_object=LocateObjectResult(location=HexCoord(0, 0), holder_leader_id=50),
    )
    rng = ScriptedRandom([0.1])  # picks "divined", not the /R alternate "sensed"

    lines = describe_locate_object(result, caster_name="Aldric", state=state, rng=rng)

    assert lines == ["Aldric divined that the Wand of Fire was located in Capital City, held by Borin."]


def test_describe_locate_object_returns_nothing_when_not_applied():
    result = CastExecutionResult(request=CastRequest(spell=Spell.LOCATE_OBJECT, target=1), applied=False, reason="cast roll failed")

    lines = describe_locate_object(result, caster_name="Aldric", state=GameState(), rng=ScriptedRandom([]))

    assert lines == []


def test_describe_locate_object_returns_nothing_when_located_object_is_none():
    # A real, successful cast against an item this project's data model
    # can't answer (unknown, or feature/monster-guarded) -- "no data,
    # don't guess", not an error.
    result = CastExecutionResult(request=CastRequest(spell=Spell.LOCATE_OBJECT, target=999), applied=True, located_object=None)

    lines = describe_locate_object(result, caster_name="Aldric", state=GameState(), rng=ScriptedRandom([]))

    assert lines == []


def test_describe_locate_object_returns_nothing_when_the_holder_cannot_be_named():
    # located_object names a real coord/holder_leader_id pair, but the
    # holder is no longer resolvable (defensive -- shouldn't happen in
    # practice, since locate_object() only ever returns a currently-real
    # leader, but describe_locate_object() shouldn't crash if it did).
    state = GameState()
    item = state.add_item(Treasure.WAND_FIREBALL, owner_leader_id=999)
    result = CastExecutionResult(
        request=CastRequest(spell=Spell.LOCATE_OBJECT, target=item.item_id),
        applied=True,
        located_object=LocateObjectResult(location=HexCoord(0, 0), holder_leader_id=999),
    )

    lines = describe_locate_object(result, caster_name="Aldric", state=state, rng=ScriptedRandom([]))

    assert lines == []


# -- SAY.PAS _LTrack / Kill Enemy Berserk retaliation (Phase 612) ------------


def test_render_kill_enemy_berserk_onset():
    # No rng draws -- the real text has no /R or {} choice markers.
    result = render_kill_enemy_berserk_onset("Borin")

    assert result == (
        "Borin went berserk over the Kill-Enemy attempt."
        "Guided by eerily accurate psychotic visions, "
    )


def test_describe_kill_enemy_berserk_retaliation_returns_nothing_for_an_ordinary_cast():
    result = CastExecutionResult(request=CastRequest(spell=Spell.KILL_ENEMY, target=2), applied=True)

    lines = describe_kill_enemy_berserk_retaliation(result, caster_name="Aldric", target_name="Borin", rng=ScriptedRandom([]))

    assert lines == []


def test_describe_kill_enemy_berserk_retaliation_narrates_the_caster_winning():
    # The onset fragment (ending ", ") concatenates directly onto the
    # first swing's own sentence, no separator -- the same "Say() calls
    # concatenate with no space" precedent render_cast_announcement()
    # already established.
    result = CastExecutionResult(
        request=CastRequest(spell=Spell.KILL_ENEMY, target=2),
        applied=False,
        reason="spell failed",
        kill_enemy_berserk_winner="a",
        melee_swings=(MeleeSwing(attacker="a", hit=True, damage=5),),
    )
    # Phase 859: two more choice_indices entries for THATT.X/THFAIL.X.
    rng = ScriptedRandom([0.1] * 30, choice_indices=[0, 0, 0, 0, 0, 0])

    lines = describe_kill_enemy_berserk_retaliation(result, caster_name="Aldric", target_name="Borin", rng=rng)

    assert lines == [
        "Borin went berserk over the Kill-Enemy attempt.Guided by eerily accurate psychotic visions, "
        "Aldric assailed Borin and inflicted 5 damage points.",
        "Borin was mortally wounded.",
        "and so it was that Borin met Borin's unseemly end.",
        "Aldric crept up on Borin's treasure, hoping to steal a great treasure.",
        "but after searching for an hour, Aldric failed to find any treasure.",
    ]


def test_describe_kill_enemy_berserk_retaliation_forwards_is_sea_to_the_mortally_wounded_line():
    # Phase 849: `is_sea` was already threaded into this composer (used
    # by the sibling SPOILS line) but never forwarded to its own
    # render_mortally_wounded() call -- MORTWOUN.X's own "sank down"
    # variant could never render for a Kill-Enemy duel resolved at sea.
    result = CastExecutionResult(
        request=CastRequest(spell=Spell.KILL_ENEMY, target=2),
        applied=False,
        reason="spell failed",
        kill_enemy_berserk_winner="a",
        melee_swings=(MeleeSwing(attacker="a", hit=True, damage=5),),
    )
    # Phase 859: two more choice_indices entries for THATT.X/THFAIL.X.
    rng = ScriptedRandom([0.1] * 30, choice_indices=[0, 0, 1, 0, 0, 0])

    lines = describe_kill_enemy_berserk_retaliation(result, caster_name="Aldric", target_name="Borin", rng=rng, is_sea=True)

    assert lines[1] == "Borin sank down, fatally injured."


def test_describe_kill_enemy_berserk_retaliation_narrates_the_target_winning():
    result = CastExecutionResult(
        request=CastRequest(spell=Spell.KILL_ENEMY, target=2),
        applied=False,
        reason="spell failed",
        kill_enemy_berserk_winner="b",
        melee_swings=(MeleeSwing(attacker="b", hit=False, damage=0),),
    )
    # Phase 859: two more choice_indices entries for THATT.X/THFAIL.X.
    rng = ScriptedRandom([0.1] * 30, choice_indices=[0, 0, 0, 0, 0, 0])

    lines = describe_kill_enemy_berserk_retaliation(result, caster_name="Aldric", target_name="Borin", rng=rng)

    assert lines == [
        "Borin went berserk over the Kill-Enemy attempt.Guided by eerily accurate psychotic visions, "
        "Borin assailed Aldric and missed.",
        "Aldric was mortally wounded.",
        "and so it was that Aldric met Aldric's unseemly end.",
        "Borin crept up on Aldric's treasure, hoping to steal a great treasure.",
        "but after searching for an hour, Borin failed to find any treasure.",
    ]


def test_describe_kill_enemy_berserk_retaliation_narrates_the_spoils_line_with_one_looted_item():
    state, item_ids = _state_with_items(Treasure.ABILITY_TACTICAL)
    result = CastExecutionResult(
        request=CastRequest(spell=Spell.KILL_ENEMY, target=2),
        applied=False,
        reason="spell failed",
        kill_enemy_berserk_winner="a",
        melee_swings=(MeleeSwing(attacker="a", hit=True, damage=5),),
        looted_item_ids=item_ids,
    )
    # Phase 859: one more choice_indices entry for THATT.X.
    rng = ScriptedRandom([0.1] * 30, choice_indices=[0, 0, 0, 0, 0, 0])

    lines = describe_kill_enemy_berserk_retaliation(
        result, caster_name="Aldric", target_name="Borin", rng=rng, state=state
    )

    assert lines[-1] == "Aldric looked with satisfaction at the remains of Borin."


def test_describe_kill_enemy_berserk_retaliation_omits_the_spoils_line_when_nothing_was_looted():
    # Phase 859: THFAIL.X ("searched, found nothing") now renders in the
    # SPOILS line's own place, not silence -- see this test's own
    # updated final-line assertion.
    result = CastExecutionResult(
        request=CastRequest(spell=Spell.KILL_ENEMY, target=2),
        applied=False,
        reason="spell failed",
        kill_enemy_berserk_winner="a",
        melee_swings=(MeleeSwing(attacker="a", hit=True, damage=5),),
    )
    rng = ScriptedRandom([0.1] * 30, choice_indices=[0, 0, 0, 0, 0, 0])

    lines = describe_kill_enemy_berserk_retaliation(
        result, caster_name="Aldric", target_name="Borin", rng=rng, state=GameState()
    )

    assert lines[-1] == "but after searching for an hour, Aldric failed to find any treasure."


# -- SBUNGLE.X/SFAIL.X (Phase 603) --


def test_render_spell_fizzled_in_combat_first_variant():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])
    result = render_spell_fizzled_in_combat("Aldric", "Fireball", rng)
    assert result == "Aldric attempted to bolster Aldric's fortunes with a Fireball spell, but it fizzled at the last moment."


def test_render_spell_fizzled_in_combat_third_variant_includes_optional_clause():
    rng = ScriptedRandom([0.99] * 10, choice_indices=[2])
    result = render_spell_fizzled_in_combat("Aldric", "Fireball", rng)
    assert result == (
        "Aldric raised Aldric's hands and gestured rhythmically, "
        "meaning to cast a Fireball spell, but it went awry and a "
        "dove tumbled out of Aldric's hat instead."
    )


def test_render_spell_cast_failed_first_variant():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])
    result = render_spell_cast_failed("Aldric", "Fireball", rng)
    assert result == "Aldric attempted a Fireball spell, but bungled it."


def test_render_spell_cast_failed_fourth_variant():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[3])
    result = render_spell_cast_failed("Aldric", "Fireball", rng)
    assert result == "Aldric's Fireball spell backfired and Aldric wound up covered with psycho-kinetic slime."


# -- describe_use_mi (Phase 146) --


def test_describe_use_mi_delegates_to_describe_cast_for_a_wand():
    cast_result = CastExecutionResult(request=CastRequest(spell=Spell.KILL_ENEMY, target=0), applied=True)
    result = UseMIExecutionResult(applied=True, cast_result=cast_result)
    rng = ScriptedRandom([])

    line = describe_use_mi(result, caster_name="Aldric", rng=rng, target_name="Borin")

    assert line == "Aldric cast a Kill Enemy spell and Borin was magically killed by a dark Necromantic spell!"


def test_describe_use_mi_renders_nothing_when_the_wand_cast_fizzled():
    cast_result = CastExecutionResult(
        request=CastRequest(spell=Spell.KILL_ENEMY, target=0), applied=False, reason="cast roll failed"
    )
    result = UseMIExecutionResult(applied=True, cast_result=cast_result)
    rng = ScriptedRandom([])

    line = describe_use_mi(result, caster_name="Aldric", rng=rng, target_name="Borin")

    assert line is None


def test_describe_use_mi_renders_nothing_for_a_skill_book_without_names():
    # No sourced SAY.PAS narrative exists for reading a skill book, and
    # without book_name/ability_name there's nothing to fill the
    # project-original template with either -- see describe_use_mi()'s
    # own docstring.
    result = UseMIExecutionResult(applied=True, ability_boosted=Ability.MELEE)
    rng = ScriptedRandom([])

    line = describe_use_mi(result, caster_name="Aldric", rng=rng)

    assert line is None


def test_describe_use_mi_renders_the_project_original_skill_book_sentence():
    result = UseMIExecutionResult(applied=True, ability_boosted=Ability.MELEE)
    rng = ScriptedRandom([])

    line = describe_use_mi(
        result, caster_name="Aldric", rng=rng, book_name="Hannibal's Grimoire", ability_name="Melee"
    )

    assert line == "Aldric read the Hannibal's Grimoire and Aldric's Melee increased by one level!"


def test_render_skill_book_read():
    rng = ScriptedRandom([])
    result = render_skill_book_read("Aldric", "Hannibal's Grimoire", "Melee", rng)
    assert result == "Aldric read the Hannibal's Grimoire and Aldric's Melee increased by one level!"


def test_describe_use_mi_renders_nothing_on_failure():
    result = UseMIExecutionResult(applied=False, reason="item not found")
    rng = ScriptedRandom([])

    line = describe_use_mi(result, caster_name="Aldric", rng=rng)

    assert line is None


def test_describe_turn_results_narrates_a_skill_book_use_mi():
    # Phase 833 bug fix: describe_turn_results()'s own ActionCode.USE_MI
    # branch used to `continue` outright whenever `cast_result` was None
    # (a wand-triggered spell fizzled or, as here, never happened at all
    # because a skill book was read instead) -- never checking whether
    # `ability_boosted`/`book_treasure` were set, so a real, successful
    # skill-book read produced zero turn-report narration despite
    # render_skill_book_read() (Phase 148) existing specifically for it.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_leader(LeaderState(1, kingdom_id=1, name="Aldric", location=HexCoord(0, 0)))
    result = UseMIExecutionResult(applied=True, ability_boosted=Ability.MELEE, book_treasure=Treasure.BOOK_MELEE)
    entries = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.USE_MI, result=result, error=None)
    ]

    lines = describe_turn_results(entries, state, ScriptedRandom([0.1] * 10, choice_indices=[0]))

    assert lines == [f"Aldric read the {TREASURE_NAME[Treasure.BOOK_MELEE]} and Aldric's Meleeing increased by one level!"]


def test_describe_turn_results_still_ignores_a_use_mi_with_no_cast_and_no_book():
    # Non-regression: a genuinely no-op UseMIExecutionResult (neither a
    # wand cast nor a skill-book read -- e.g. `applied=False`, or the
    # existing "not a Use_MI target" refusal) still narrates nothing.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_leader(LeaderState(1, kingdom_id=1, name="Aldric", location=HexCoord(0, 0)))
    result = UseMIExecutionResult(applied=False, reason="not a Use_MI target -- operates automatically")
    entries = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.USE_MI, result=result, error=None)
    ]

    lines = describe_turn_results(entries, state, ScriptedRandom([0.1] * 10, choice_indices=[0]))

    assert lines == []


# -- describe_pursue / describe_trail (Phase 147) --


def test_describe_pursue_renders_the_catch_up_sentence_on_an_army_battle():
    result = PursueExecutionResult(caught_up=True, combat_occurred=True, battle_report=object())
    rng = ScriptedRandom([])

    line = describe_pursue(result, pursuer_name="Aldric", target_name="Borin", province_name="Eldoria", rng=rng)

    assert line == "Aldric caught up with Borin in Eldoria."


def test_describe_pursue_renders_the_catch_up_sentence_on_an_armyless_duel():
    result = PursueExecutionResult(
        caught_up=True, combat_occurred=True, winner_leader_id=1, loser_leader_id=2, loser_killed=True
    )
    rng = ScriptedRandom([])

    line = describe_pursue(result, pursuer_name="Aldric", target_name="Borin", province_name="Eldoria", rng=rng)

    assert line == "Aldric caught up with Borin in Eldoria."


def test_describe_pursue_renders_the_catch_up_sentence_with_no_combat_intent():
    result = PursueExecutionResult(caught_up=True, combat_occurred=False)
    rng = ScriptedRandom([])

    line = describe_pursue(result, pursuer_name="Aldric", target_name="Borin", province_name="Eldoria", rng=rng)

    assert line == "Aldric caught up with Borin in Eldoria."


def test_describe_pursue_renders_nothing_when_not_caught_up():
    result = PursueExecutionResult(caught_up=False, reason="did not catch up this phase")
    rng = ScriptedRandom([])

    line = describe_pursue(result, pursuer_name="Aldric", target_name="Borin", province_name="Eldoria", rng=rng)

    assert line is None


def test_describe_trail_renders_the_catch_up_sentence():
    result = TrailExecutionResult(spied_on=True)
    rng = ScriptedRandom([])

    line = describe_trail(result, trailer_name="Aldric", target_name="Borin", province_name="Eldoria", rng=rng)

    assert line == "Aldric caught up with Borin in Eldoria."


def test_describe_trail_renders_nothing_when_not_spied_on():
    result = TrailExecutionResult(spied_on=False, reason="did not catch up this phase")
    rng = ScriptedRandom([])

    line = describe_trail(result, trailer_name="Aldric", target_name="Borin", province_name="Eldoria", rng=rng)

    assert line is None


# -- Phase 212: Trail's own intelligence payload (project-original prose) --


def test_render_trail_temper():
    rng = ScriptedRandom([0.1] * 4)
    result = render_trail_temper("Aldric", "Borin", "Brave", rng)
    assert result == "Aldric learned that Borin has temper Brave."


def test_render_trail_alignment():
    rng = ScriptedRandom([0.1] * 4)
    result = render_trail_alignment("Aldric", "Borin", "Good", rng)
    assert result == "Aldric learned that Borin is Good in alignment."


def test_render_trail_race():
    rng = ScriptedRandom([0.1] * 4)
    result = render_trail_race("Aldric", "Borin", "Human", rng)
    assert result == "Aldric learned that Borin is Human."


def test_render_trail_treasures():
    rng = ScriptedRandom([0.1] * 4)
    result = render_trail_treasures("Aldric", "Borin", ["Sword of Truth", "Shield of Faith"], rng)
    assert result == "Aldric learned that Borin owns Sword of Truth and Shield of Faith."


def test_render_trail_no_treasures():
    rng = ScriptedRandom([0.1] * 4)
    result = render_trail_no_treasures("Aldric", "Borin", rng)
    assert result == "Aldric learned that Borin owns no treasures."


def test_render_trail_armies_led():
    rng = ScriptedRandom([0.1] * 4)
    result = render_trail_armies_led("Aldric", "Borin", ["241st Axemen"], rng)
    assert result == "Aldric learned that Borin leads 241st Axemen."


def test_render_trail_no_armies_led():
    rng = ScriptedRandom([0.1] * 4)
    result = render_trail_no_armies_led("Aldric", "Borin", rng)
    assert result == "Aldric learned that Borin leads no armies."


def test_render_trail_king_finances():
    rng = ScriptedRandom([0.1] * 4)
    result = render_trail_king_finances("Aldric", "King Borin", 500, rng)
    assert result == "Aldric learned that King Borin commands a treasury of 500 gold."


def test_render_trail_king_allies():
    rng = ScriptedRandom([0.1] * 4)
    result = render_trail_king_allies("Aldric", "King Borin", ["Alliedland"], rng)
    assert result == "Aldric learned that King Borin is allied with Alliedland."


def test_render_trail_king_no_allies():
    rng = ScriptedRandom([0.1] * 4)
    result = render_trail_king_no_allies("Aldric", "King Borin", rng)
    assert result == "Aldric learned that King Borin has no allies."


def test_render_trail_king_provinces():
    rng = ScriptedRandom([0.1] * 4)
    result = render_trail_king_provinces("Aldric", "King Borin", ["Greenfield"], rng)
    assert result == "Aldric learned that King Borin controls Greenfield."


def test_render_trail_king_no_provinces():
    rng = ScriptedRandom([0.1] * 4)
    result = render_trail_king_no_provinces("Aldric", "King Borin", rng)
    assert result == "Aldric learned that King Borin controls no provinces."


def _trail_intel_state() -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.GOOD, HexCoord(0, 0)))
    state.add_kingdom(KingdomState(2, "Alliedland", Race.HUMAN, Alignment.GOOD, HexCoord(5, 5)))
    return state


def test_describe_trail_intelligence_empty_when_not_spied_on():
    result = TrailExecutionResult(spied_on=False, reason="did not catch up this phase")
    rng = ScriptedRandom([0.1] * 4)

    lines = describe_trail_intelligence(result, state=_trail_intel_state(), trailer_name="Aldric", target_name="Borin", rng=rng)

    assert lines == []


def test_describe_trail_intelligence_omits_none_fields():
    result = TrailExecutionResult(spied_on=True, temper=None, alignment=None, race=None)
    rng = ScriptedRandom([0.1] * 20)

    lines = describe_trail_intelligence(result, state=_trail_intel_state(), trailer_name="Aldric", target_name="Borin", rng=rng)

    assert lines == [
        "Aldric learned that Borin owns no treasures.",
        "Aldric learned that Borin leads no armies.",
    ]


def test_describe_trail_intelligence_renders_temper_alignment_race():
    result = TrailExecutionResult(spied_on=True, temper=Temper.BRAVE, alignment=Alignment.GOOD, race=Race.ELVEN)
    rng = ScriptedRandom([0.1] * 20)

    lines = describe_trail_intelligence(result, state=_trail_intel_state(), trailer_name="Aldric", target_name="Borin", rng=rng)

    assert lines[:3] == [
        "Aldric learned that Borin has temper Brave.",
        "Aldric learned that Borin is Good in alignment.",
        "Aldric learned that Borin is Elf.",
    ]


def test_describe_trail_intelligence_renders_treasures_and_armies_led():
    item = ItemInstance(1, Treasure.ABILITY_TACTICAL, 2)
    army = ArmyState(1, 1, ArmyType.BOWMEN, Quality.AVERAGE, HexCoord(0, 0))
    result = TrailExecutionResult(spied_on=True, treasures_owned=(item,), armies_led=(army,))
    rng = ScriptedRandom([0.1] * 20)

    lines = describe_trail_intelligence(result, state=_trail_intel_state(), trailer_name="Aldric", target_name="Borin", rng=rng)

    assert lines[0] == f"Aldric learned that Borin owns {TREASURE_NAME[Treasure.ABILITY_TACTICAL]}."
    assert lines[1] == f"Aldric learned that Borin leads {make_army_name(1, ArmyType.BOWMEN, Race.HUMAN)}."


def test_describe_trail_intelligence_no_king_lines_when_no_king_intelligence():
    result = TrailExecutionResult(spied_on=True, king_intelligence=None)
    rng = ScriptedRandom([0.1] * 20)

    lines = describe_trail_intelligence(result, state=_trail_intel_state(), trailer_name="Aldric", target_name="Borin", rng=rng)

    assert not any("treasury" in line or "allied" in line or "controls" in line for line in lines)


def test_describe_trail_intelligence_king_lines_with_allies_and_provinces():
    state = _trail_intel_state()
    state.add_province(ProvinceState(HexCoord(0, 0), None, Race.HUMAN, owner_kingdom_id=1, name="Capital City"))
    king = KingIntelligence(treasury=500, allied_kingdom_ids=(2,), controlled_provinces=(HexCoord(0, 0),))
    result = TrailExecutionResult(spied_on=True, king_intelligence=king)
    rng = ScriptedRandom([0.1] * 20)

    lines = describe_trail_intelligence(result, state=state, trailer_name="Aldric", target_name="Borin", rng=rng)

    assert "Aldric learned that Borin commands a treasury of 500 gold." in lines
    assert "Aldric learned that Borin is allied with Alliedland." in lines
    assert "Aldric learned that Borin controls Capital City." in lines


def test_describe_trail_intelligence_king_lines_with_no_allies_or_provinces():
    king = KingIntelligence(treasury=0, allied_kingdom_ids=(), controlled_provinces=())
    result = TrailExecutionResult(spied_on=True, king_intelligence=king)
    rng = ScriptedRandom([0.1] * 20)

    lines = describe_trail_intelligence(
        result, state=_trail_intel_state(), trailer_name="Aldric", target_name="Borin", rng=rng
    )

    assert "Aldric learned that Borin commands a treasury of 0 gold." in lines
    assert "Aldric learned that Borin has no allies." in lines
    assert "Aldric learned that Borin controls no provinces." in lines


# -- Phase 832: SPY_SUPER_SLEUTH's own "guessed distance" (Pursue/Trail)
# and SPY_EXPANDED_SPYING's own "offices held" (Trail) -- both computed
# since Phase 695/705 but never rendered until now.


def test_render_guessed_distance_singular():
    rng = ScriptedRandom([0.1] * 4)
    result = render_guessed_distance("Aldric", "Borin", 1, rng)
    assert result == "Aldric estimates Borin to be about 1 province away."


def test_render_guessed_distance_plural():
    rng = ScriptedRandom([0.1] * 4)
    result = render_guessed_distance("Aldric", "Borin", 3, rng)
    assert result == "Aldric estimates Borin to be about 3 provinces away."


def test_render_guessed_distance_zero_is_plural():
    rng = ScriptedRandom([0.1] * 4)
    result = render_guessed_distance("Aldric", "Borin", 0, rng)
    assert result == "Aldric estimates Borin to be about 0 provinces away."


def test_render_trail_offices_held_one_office():
    rng = ScriptedRandom([0.1] * 4)
    result = render_trail_offices_held("Aldric", "Borin", ["Esteemed High Chancellor"], rng)
    assert result == "Aldric learned that Borin holds the office of Esteemed High Chancellor."


def test_render_trail_offices_held_multiple_offices():
    rng = ScriptedRandom([0.1] * 4)
    result = render_trail_offices_held("Aldric", "Borin", ["Esteemed High Chancellor", "Imperial Treasurer"], rng)
    assert result == "Aldric learned that Borin holds the office of Esteemed High Chancellor and Imperial Treasurer."


def test_describe_trail_intelligence_renders_guessed_distance_first():
    result = TrailExecutionResult(spied_on=True, guessed_distance=2)
    rng = ScriptedRandom([0.1] * 20)

    lines = describe_trail_intelligence(result, state=_trail_intel_state(), trailer_name="Aldric", target_name="Borin", rng=rng)

    assert lines[0] == "Aldric estimates Borin to be about 2 provinces away."


def test_describe_trail_intelligence_omits_guessed_distance_when_none():
    result = TrailExecutionResult(spied_on=True, guessed_distance=None)
    rng = ScriptedRandom([0.1] * 20)

    lines = describe_trail_intelligence(result, state=_trail_intel_state(), trailer_name="Aldric", target_name="Borin", rng=rng)

    assert not any("estimates" in line for line in lines)


def test_describe_trail_intelligence_renders_offices_held():
    result = TrailExecutionResult(spied_on=True, offices_held=(Office.CHANCELLOR,))
    rng = ScriptedRandom([0.1] * 20)

    lines = describe_trail_intelligence(result, state=_trail_intel_state(), trailer_name="Aldric", target_name="Borin", rng=rng)

    assert f"Aldric learned that Borin holds the office of {OFFICE_NAME[Office.CHANCELLOR]}." in lines


def test_describe_trail_intelligence_omits_offices_held_when_empty():
    # Phase 832: an empty `offices_held` is genuinely ambiguous between
    # "caster doesn't hold SPY_EXPANDED_SPYING" and "ability held, target
    # holds no offices" -- this result type exposes no way to tell them
    # apart, so (unlike treasures/armies_led) the line is skipped rather
    # than claiming a "holds no offices" fact it can't actually confirm.
    result = TrailExecutionResult(spied_on=True, offices_held=())
    rng = ScriptedRandom([0.1] * 20)

    lines = describe_trail_intelligence(result, state=_trail_intel_state(), trailer_name="Aldric", target_name="Borin", rng=rng)

    assert not any("office" in line for line in lines)


def test_describe_pursue_guessed_distance_renders_when_set():
    result = PursueExecutionResult(caught_up=True, guessed_distance=4)
    rng = ScriptedRandom([0.1] * 4)

    lines = describe_pursue_guessed_distance(result, pursuer_name="Aldric", target_name="Borin", rng=rng)

    assert lines == ["Aldric estimates Borin to be about 4 provinces away."]


def test_describe_pursue_guessed_distance_empty_when_none():
    result = PursueExecutionResult(caught_up=True, guessed_distance=None)
    rng = ScriptedRandom([0.1] * 4)

    lines = describe_pursue_guessed_distance(result, pursuer_name="Aldric", target_name="Borin", rng=rng)

    assert lines == []


def test_describe_turn_results_renders_pursue_guessed_distance():
    # End-to-end: SPY_SUPER_SLEUTH's own real fact reaches the turn
    # report through describe_turn_results()'s ActionCode.PURSUE branch,
    # independent of whatever catch-up/combat outcome also renders.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_province(ProvinceState(HexCoord(0, 0), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_leader(LeaderState(1, kingdom_id=1, name="Aldric", location=HexCoord(0, 0)))
    state.add_leader(LeaderState(2, kingdom_id=1, name="Borin", location=HexCoord(0, 0)))
    request = PursueRequest(target_character_id=2, unconfirmed_extra0=0, tactics=[])
    result = PursueExecutionResult(caught_up=True, combat_occurred=False, guessed_distance=2, request=request)
    entries = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.PURSUE, result=result, error=None)
    ]

    lines = describe_turn_results(entries, state, ScriptedRandom([0.1] * 20, choice_indices=[0]))

    assert "Aldric estimates Borin to be about 2 provinces away." in lines


# -- Phase 156: Search's own report composer --


def test_render_search_attempt_first_variant():
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])
    result = render_search_attempt("Aldric", "Ancient Ruins", rng)
    assert result == "Aldric approached the Ancient Ruins, intending to root out its mysteries."


def test_render_search_attempt_resolves_sea_marker():
    rng = ScriptedRandom([0.9] * 10, choice_indices=[0])
    result = render_search_attempt("Aldric", "Ancient Ruins", rng, is_sea=True)
    assert result == "Aldric investigated the Ancient Ruins, meaning to uncover its dark secrets."


def test_render_search_feature_already_sacked():
    rng = ScriptedRandom([0.1] * 10)
    result = render_search_feature_already_sacked("Aldric", "Ancient Ruins", rng)
    assert result == "Aldric searched the Ancient Ruins but it had been looted."


def test_describe_search_rejected_already_looted_renders_sacked_line():
    result = SearchExecutionResult(accepted=False, reason="feature already looted")
    rng = ScriptedRandom([0.1] * 10)

    lines = describe_search(result, character_name="Aldric", feature_name="Ancient Ruins", rng=rng)

    assert lines == ["Aldric searched the Ancient Ruins but it had been looted."]


def test_describe_search_rejected_for_other_reasons_renders_nothing():
    result = SearchExecutionResult(accepted=False, reason="not co-located with feature")
    rng = ScriptedRandom([])

    lines = describe_search(result, character_name="Aldric", feature_name="Ancient Ruins", rng=rng)

    assert lines == []


def test_describe_search_accepted_no_combat_renders_only_the_opening_line():
    result = SearchExecutionResult(accepted=True, combat_resolved=False, reason="no Melee tactic in encounter plan")
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])

    lines = describe_search(result, character_name="Aldric", feature_name="Ancient Ruins", rng=rng)

    assert lines == ["Aldric approached the Ancient Ruins, intending to root out its mysteries."]


def test_describe_search_guardian_riddle_appends_the_riddle_line():
    result = SearchExecutionResult(
        accepted=True,
        combat_resolved=False,
        reason="the guardian proposes a deal -- honor it with Fulfill on a later Search",
        guardian_monster=Monster.SPHINX,
        guardian_riddle=Treasure.QUEST_RA_BRIDGE,
    )
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])

    lines = describe_search(result, character_name="Aldric", feature_name="Ancient Ruins", rng=rng)

    assert lines == [
        "Aldric approached the Ancient Ruins, intending to root out its mysteries.",
        render_guardian_poses_riddle("Sphinx", Treasure.QUEST_RA_BRIDGE),
    ]


def test_describe_search_non_riddle_quest_reply_appends_no_extra_line():
    # The other 18 QUEST_OR_AGREEMENT replies still render nothing
    # beyond the opening line -- guardian_riddle stays None for them.
    result = SearchExecutionResult(
        accepted=True,
        combat_resolved=False,
        reason="the guardian proposes a deal -- honor it with Fulfill on a later Search",
        guardian_monster=Monster.ARCHER,
        guardian_riddle=None,
    )
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])

    lines = describe_search(result, character_name="Aldric", feature_name="Ancient Ruins", rng=rng)

    assert lines == ["Aldric approached the Ancient Ruins, intending to root out its mysteries."]


def test_describe_search_guardian_quest_location_appends_the_quest_line():
    result = SearchExecutionResult(
        accepted=True,
        combat_resolved=False,
        reason="the guardian proposes a deal -- honor it with Fulfill on a later Search",
        guardian_monster=Monster.SPHINX,
        guardian_quest_location=Treasure.QUEST_GODS_QUEST,
    )
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])

    lines = describe_search(result, character_name="Aldric", feature_name="Ancient Ruins", rng=rng)

    assert lines == [
        "Aldric approached the Ancient Ruins, intending to root out its mysteries.",
        render_guardian_proposes_quest_location("Sphinx", Treasure.QUEST_GODS_QUEST),
    ]


def test_describe_search_non_visit_quest_reply_appends_no_extra_line():
    # The other 18 QUEST_OR_AGREEMENT replies still render nothing
    # beyond the opening line -- guardian_quest_location stays None for
    # them.
    result = SearchExecutionResult(
        accepted=True,
        combat_resolved=False,
        reason="the guardian proposes a deal -- honor it with Fulfill on a later Search",
        guardian_monster=Monster.ARCHER,
        guardian_quest_location=None,
    )
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])

    lines = describe_search(result, character_name="Aldric", feature_name="Ancient Ruins", rng=rng)

    assert lines == ["Aldric approached the Ancient Ruins, intending to root out its mysteries."]


def test_describe_search_leader_killed_appends_mortally_wounded():
    result = SearchExecutionResult(accepted=True, combat_resolved=True, winner="monster", leader_killed=True)
    # Phase 611: HORDEATH.X's own generic closing beat now follows.
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0, 0, 0])

    lines = describe_search(result, character_name="Aldric", feature_name="Ancient Ruins", rng=rng)

    assert lines == [
        "Aldric approached the Ancient Ruins, intending to root out its mysteries.",
        "Aldric was mortally wounded.",
        "and so it was that Aldric met Aldric's unseemly end.",
    ]


def test_describe_search_leader_won_renders_only_the_opening_line():
    # No sourced "you defeated the guardian" sentence exists -- see
    # describe_search()'s own docstring.
    result = SearchExecutionResult(accepted=True, combat_resolved=True, winner="leader", feature_looted=True)
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])

    lines = describe_search(result, character_name="Aldric", feature_name="Ancient Ruins", rng=rng)

    assert lines == ["Aldric approached the Ancient Ruins, intending to root out its mysteries."]


def test_describe_search_inconclusive_combat_renders_only_the_opening_line():
    result = SearchExecutionResult(accepted=True, combat_resolved=True, winner=None)
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])

    lines = describe_search(result, character_name="Aldric", feature_name="Ancient Ruins", rng=rng)

    assert lines == ["Aldric approached the Ancient Ruins, intending to root out its mysteries."]


def test_describe_search_renders_a_fizzled_leader_cast_right_after_the_opening_line():
    # Phase 858: SBUNGLE.X's own real "personal-combat Cast that just
    # fizzles" text -- see SearchExecutionResult.fizzled_spells's own
    # docstring for the real, sourced trigger.
    result = SearchExecutionResult(accepted=True, combat_resolved=True, winner=None, fizzled_spells=(("leader", Spell.FIREBALL),))
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0, 0])

    lines = describe_search(result, character_name="Aldric", feature_name="Ancient Ruins", rng=rng)

    assert lines == [
        "Aldric approached the Ancient Ruins, intending to root out its mysteries.",
        "Aldric attempted to bolster Aldric's fortunes with a Fireball spell, but it fizzled at the last moment.",
    ]


def test_describe_search_renders_a_fizzled_monster_cast_using_the_guardians_own_name():
    result = SearchExecutionResult(
        accepted=True,
        combat_resolved=True,
        winner=None,
        guardian_monster=Monster.GARGOYLE,
        fizzled_spells=(("monster", Spell.FIREBALL),),
    )
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0, 0])

    lines = describe_search(result, character_name="Aldric", feature_name="Ancient Ruins", rng=rng)

    assert lines == [
        "Aldric approached the Ancient Ruins, intending to root out its mysteries.",
        "Gargoyle attempted to bolster Gargoyle's fortunes with a Fireball spell, but it fizzled at the last moment.",
    ]


# -- Phase 855 (SAY.PAS _LShIce): Ice Suspend's own "fully frozen" branch --
# -- always ends the encounter as an immediate win (turn/encounter.py's --
# -- own Phase 189 addendum) -- see SearchExecutionResult.ice_suspend_ --
# -- immobilized's own docstring for why only this one branch is captured.


def test_describe_search_ice_suspend_immobilized_guardian_renders_before_win():
    result = SearchExecutionResult(
        accepted=True, combat_resolved=True, winner="leader", feature_looted=True, ice_suspend_immobilized=True
    )
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])

    lines = describe_search(result, character_name="Aldric", feature_name="Ancient Ruins", rng=rng)

    assert lines == [
        "Aldric approached the Ancient Ruins, intending to root out its mysteries.",
        "guardian was immobilized by the shell of ice.",
    ]


def test_describe_search_ice_suspend_immobilized_leader_renders_before_mortal_wound():
    result = SearchExecutionResult(
        accepted=True, combat_resolved=True, winner="monster", leader_killed=True, ice_suspend_immobilized=True
    )
    rng = ScriptedRandom([0.1] * 20, choice_indices=[0, 0, 0, 0, 0])

    lines = describe_search(result, character_name="Aldric", feature_name="Ancient Ruins", rng=rng)

    assert lines == [
        "Aldric approached the Ancient Ruins, intending to root out its mysteries.",
        "Aldric was immobilized by the shell of ice.",
        "Aldric was mortally wounded.",
        "and so it was that Aldric met Aldric's unseemly end.",
    ]


def test_describe_search_ice_suspend_immobilized_false_renders_no_extra_line():
    # Non-regression: the default (every pre-Phase-855 fixture) renders
    # nothing extra -- same shape as test_describe_search_leader_won_
    # renders_only_the_opening_line above, just spelled out explicitly
    # for this new field.
    result = SearchExecutionResult(accepted=True, combat_resolved=True, winner="leader", feature_looted=True)
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])

    lines = describe_search(result, character_name="Aldric", feature_name="Ancient Ruins", rng=rng)

    assert lines == ["Aldric approached the Ancient Ruins, intending to root out its mysteries."]


# -- Phase 672/673: report-layer narration for the 3 raid-pacification --
# -- outcomes -- real, sourced SAY.PAS text as of Phase 673 (Desktop/ --
# -- BOLD OK.txt), see render_guardian_pacified_by_fulfill()/render_ --
# -- guardian_intimidated()/render_guardian_undeterred()'s own docstrings.


def test_render_guardian_pacified_by_fulfill():
    result = render_guardian_pacified_by_fulfill("Gargoyle", "Tebessa", ScriptedRandom([0.1, 0.1]))
    assert result == "in Gargoyle's gratitude, Gargoyle swore off any raids in Tebessa."


def test_render_guardian_intimidated():
    result = render_guardian_intimidated("Gargoyle", "Tebessa", ScriptedRandom([]))
    assert result == "Gargoyle was intimidated by the encounter, and surely will not be raiding Tebessa again for some time!"


def test_render_guardian_undeterred():
    result = render_guardian_undeterred("Gargoyle", "Tebessa", ScriptedRandom([0.1]))
    assert result == "In Gargoyle's judgement, Gargoyle was undaunted by the encounter and surely intends to continue plundering Tebessa."


def test_describe_search_renders_fulfill_pacification_line():
    result = SearchExecutionResult(
        accepted=True, combat_resolved=False, winner="leader", guardian_pacified_by_fulfill=True,
        guardian_monster=Monster.GARGOYLE,
    )
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])

    lines = describe_search(result, character_name="Aldric", feature_name="Ancient Ruins", rng=rng)

    assert lines == [
        "Aldric approached the Ancient Ruins, intending to root out its mysteries.",
        "in Gargoyle's gratitude, Gargoyle swore off any raids in these lands.",
    ]


def test_describe_search_renders_intimidation_line():
    result = SearchExecutionResult(
        accepted=True, combat_resolved=True, winner="monster", leader_killed=True, guardian_intimidated=True,
        guardian_monster=Monster.GARGOYLE,
    )
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0, 0, 0])

    lines = describe_search(result, character_name="Aldric", feature_name="Ancient Ruins", rng=rng)

    assert lines == [
        "Aldric approached the Ancient Ruins, intending to root out its mysteries.",
        "Aldric was mortally wounded.",
        "and so it was that Aldric met Aldric's unseemly end.",
        "Gargoyle was intimidated by the encounter, and surely will not be raiding these lands again for some time!",
    ]


def test_describe_search_renders_undeterred_line():
    result = SearchExecutionResult(
        accepted=True, combat_resolved=True, winner="monster", leader_killed=True, guardian_undeterred=True,
        guardian_monster=Monster.GARGOYLE,
    )
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0, 0, 0])

    lines = describe_search(result, character_name="Aldric", feature_name="Ancient Ruins", rng=rng)

    assert lines == [
        "Aldric approached the Ancient Ruins, intending to root out its mysteries.",
        "Aldric was mortally wounded.",
        "and so it was that Aldric met Aldric's unseemly end.",
        "In Gargoyle's judgement, Gargoyle was undaunted by the encounter and surely intends to continue plundering these lands.",
    ]


def test_describe_search_neither_pacification_flag_renders_no_extra_line():
    result = SearchExecutionResult(accepted=True, combat_resolved=False, winner="leader")
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])

    lines = describe_search(result, character_name="Aldric", feature_name="Ancient Ruins", rng=rng)

    assert lines == ["Aldric approached the Ancient Ruins, intending to root out its mysteries."]


def test_describe_search_pacification_line_falls_back_to_generic_guardian_name():
    # No guardian_monster set (e.g. the Talk/Fulfill/Beg/Flee call sites
    # that don't populate it) -- the existing generic fallback applies.
    result = SearchExecutionResult(accepted=True, combat_resolved=False, winner="leader", guardian_pacified_by_fulfill=True)
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])

    lines = describe_search(result, character_name="Aldric", feature_name="Ancient Ruins", rng=rng)

    assert lines[-1] == "in guardian's gratitude, guardian swore off any raids in these lands."


def test_search_province_name_resolves_the_real_province():
    state = GameState()
    coord = HexCoord(1, 1)
    state.add_province(ProvinceState(coord, Terrain.PLAINS, Race.HUMAN, name="Tebessa"))
    state.add_feature(Feature(feature_id=1, coord=coord, kind=FeatureType.CAVE, guardian_monster=Monster.GARGOYLE))
    request = SearchRequest(feature_id=1, unconfirmed_extra0=0, tactics=[])
    result = SearchExecutionResult(accepted=True, request=request)

    assert _search_province_name(state, result) == "Tebessa"


def test_search_province_name_falls_back_when_unresolvable():
    assert _search_province_name(None, SearchExecutionResult(accepted=True)) == "these lands"
    assert _search_province_name(GameState(), SearchExecutionResult(accepted=True)) == "these lands"


# -- Phase 616: describe_feature_power_attempt() (POWMSG.X2) --


def test_describe_feature_power_attempt_new_temp_already_matched():
    outcome = FeaturePowerAttemptResult(
        power=Power.NEW_TEMP, applied=True, already_matched=True, new_temper=Temper.BRAVE, magic_feature=MagicFeature.POOL
    )
    line = describe_feature_power_attempt(outcome, ScriptedRandom([0.1] * 4))
    assert line == "The Pool/FStream turns your temper to Brave.But your temper is already Brave, so you're fine already."


def test_describe_feature_power_attempt_new_temp_changed():
    outcome = FeaturePowerAttemptResult(
        power=Power.NEW_TEMP, applied=True, new_temper=Temper.BERSERK, magic_feature=MagicFeature.POOL
    )
    line = describe_feature_power_attempt(outcome, ScriptedRandom([0.1] * 4))
    assert "Berserk temper" in line


def test_describe_feature_power_attempt_new_race_changed():
    outcome = FeaturePowerAttemptResult(power=Power.NEW_RACE, applied=True, new_race=Race.ELVEN, magic_feature=MagicFeature.ALTAR)
    line = describe_feature_power_attempt(outcome, ScriptedRandom([0.1] * 4))
    assert "supreme Elf race" in line


def test_describe_feature_power_attempt_up_skill_success():
    outcome = FeaturePowerAttemptResult(
        power=Power.UP_SKILL, applied=True, ability=Ability.MELEE, new_skill_level=2, magic_feature=MagicFeature.PENTAGRAM
    )
    line = describe_feature_power_attempt(outcome, ScriptedRandom([0.1] * 4))
    assert line == "by the power of the Pentagram/FMagic_Circle, I increase your skill in Meleeing by 1 skill level!"


def test_describe_feature_power_attempt_up_skill_at_limit():
    outcome = FeaturePowerAttemptResult(
        power=Power.UP_SKILL, applied=True, at_limit=True, ability=Ability.MELEE, magic_feature=MagicFeature.PENTAGRAM
    )
    line = describe_feature_power_attempt(outcome, ScriptedRandom([0.1] * 4))
    assert "already reached that limit" in line


def test_describe_feature_power_attempt_up_skill_roll_failed():
    outcome = FeaturePowerAttemptResult(
        power=Power.UP_SKILL, applied=False, reason="the roll failed", ability=Ability.MELEE, magic_feature=MagicFeature.PENTAGRAM
    )
    line = describe_feature_power_attempt(outcome, ScriptedRandom([0.1] * 4))
    assert "aptitude is simply inadequate" in line


def test_describe_feature_power_attempt_up_apt_success():
    outcome = FeaturePowerAttemptResult(
        power=Power.UP_APT, applied=True, ability=Ability.SAGE, new_aptitude_level=3, magic_feature=MagicFeature.LAMP
    )
    line = describe_feature_power_attempt(outcome, ScriptedRandom([0.1] * 4))
    assert "aptitude in Sageness" in line


def test_describe_feature_power_attempt_up_apt_at_limit_has_no_recovered_message():
    outcome = FeaturePowerAttemptResult(
        power=Power.UP_APT, applied=True, at_limit=True, ability=Ability.SAGE, magic_feature=MagicFeature.LAMP
    )
    assert describe_feature_power_attempt(outcome, ScriptedRandom([0.1] * 4)) is None


def test_describe_feature_power_attempt_dn_skill_success():
    outcome = FeaturePowerAttemptResult(
        power=Power.DN_SKILL, applied=True, ability=Ability.THIEF, new_skill_level=1, magic_feature=MagicFeature.BOOK
    )
    line = describe_feature_power_attempt(outcome, ScriptedRandom([0.1] * 4))
    assert "1 less skill level in Thievery" in line


def test_describe_feature_power_attempt_dn_apt_at_limit():
    outcome = FeaturePowerAttemptResult(
        power=Power.DN_APT, applied=True, at_limit=True, ability=Ability.THIEF, magic_feature=MagicFeature.BOOK
    )
    line = describe_feature_power_attempt(outcome, ScriptedRandom([0.1] * 4))
    assert "no aptitude for Thievery" in line


def test_describe_feature_power_attempt_map_feat_exhausted():
    outcome = FeaturePowerAttemptResult(power=Power.MAP_FEAT, applied=False, reason="no more features to reveal")
    line = describe_feature_power_attempt(outcome, ScriptedRandom([0.1] * 4))
    assert line == "There are no more features to be told of in the provinces you have mapped."


def test_describe_feature_power_attempt_map_feat_success_has_no_recovered_message():
    outcome = FeaturePowerAttemptResult(power=Power.MAP_FEAT, applied=True, revealed_feature_id=42)
    assert describe_feature_power_attempt(outcome, ScriptedRandom([0.1] * 4)) is None


def test_describe_feature_power_attempt_map_prov_exhausted():
    outcome = FeaturePowerAttemptResult(power=Power.MAP_PROV, applied=False, reason="no more provinces to reveal")
    line = describe_feature_power_attempt(outcome, ScriptedRandom([0.1] * 4))
    assert line == "No more provinces exist to be told of in this world."


def test_describe_feature_power_attempt_map_prov_success_has_no_recovered_message():
    outcome = FeaturePowerAttemptResult(power=Power.MAP_PROV, applied=True, revealed_province_coords=(HexCoord(1, 1),))
    assert describe_feature_power_attempt(outcome, ScriptedRandom([0.1] * 4)) is None


def test_describe_feature_power_attempt_sage_disc_exhausted():
    outcome = FeaturePowerAttemptResult(power=Power.SAGE_DISC, applied=False, reason="no more discoveries to reveal")
    line = describe_feature_power_attempt(outcome, ScriptedRandom([0.1] * 4))
    assert line == "Science has come to an end!There are no more discoveries to be made in this universe."


# -- Phase 796: SAGE_DISC's own real success narration (direct
# disassembly + RUMORS.PAS/SAY.PAS) -- see `_POWMSG_SAGE_DISC_SUCCESS_
# TEMPLATE`'s own docstring for the 3-fragment sourcing.


def test_describe_feature_power_attempt_sage_disc_success_ability_bonus():
    outcome = FeaturePowerAttemptResult(power=Power.SAGE_DISC, applied=True, revealed_discoveries=(Discovery.COMPASS,))
    line = describe_feature_power_attempt(outcome, ScriptedRandom([0.1] * 8), character_name="Erasmus")
    assert "Erasmus then learned that the following benefits are conferred by the" in line
    assert DISCOVERY_NAME[Discovery.COMPASS] in line
    assert line.endswith(discovery_effect_description(Discovery.COMPASS))


def test_describe_feature_power_attempt_sage_disc_success_antispell():
    discovery = Discovery.OSTEOPATHIC_GERM_WARFARE
    outcome = FeaturePowerAttemptResult(power=Power.SAGE_DISC, applied=True, revealed_discoveries=(discovery,))
    line = describe_feature_power_attempt(outcome, ScriptedRandom([0.1] * 8), character_name="Erasmus")
    assert DISCOVERY_NAME[discovery] in line
    assert line.endswith(discovery_effect_description(discovery))
    assert discovery_effect_description(discovery) == "Anti-spell: Skeletal Army"


def test_describe_feature_power_attempt_sage_disc_success_revenue_bonus():
    discovery = Discovery.PEANUT_BUTTER_SANDWICH
    outcome = FeaturePowerAttemptResult(power=Power.SAGE_DISC, applied=True, revealed_discoveries=(discovery,))
    line = describe_feature_power_attempt(outcome, ScriptedRandom([0.1] * 8), character_name="Erasmus")
    assert DISCOVERY_NAME[discovery] in line
    assert line.endswith(discovery_effect_description(discovery))
    assert discovery_effect_description(discovery) == "+1% revenue"


def test_describe_feature_power_attempt_sage_disc_success_needs_a_character_name():
    outcome = FeaturePowerAttemptResult(power=Power.SAGE_DISC, applied=True, revealed_discoveries=(Discovery.COMPASS,))
    assert describe_feature_power_attempt(outcome, ScriptedRandom([0.1] * 8), character_name=None) is None


def test_describe_feature_power_attempt_new_sex_to_female():
    outcome = FeaturePowerAttemptResult(power=Power.NEW_SEX, applied=True, new_sex=Sex.FEMALE, magic_feature=MagicFeature.ALTAR)
    line = describe_feature_power_attempt(outcome, ScriptedRandom([0.1] * 4))
    assert "I change you to a woman" in line


def test_describe_feature_power_attempt_new_sex_to_male():
    outcome = FeaturePowerAttemptResult(power=Power.NEW_SEX, applied=True, new_sex=Sex.MALE, magic_feature=MagicFeature.ALTAR)
    line = describe_feature_power_attempt(outcome, ScriptedRandom([0.1] * 4))
    assert "I zap you from female to male" in line


def test_describe_feature_power_attempt_condition_refusal_without_condition_refused_falls_through():
    # A refusal whose own `condition_refused` was never set (e.g. built
    # directly rather than via `_apply_condition_gate()`) skips the new
    # Phase 782 generic dispatch entirely and falls through to the
    # per-power branch's own ordinary "applied=False" early return.
    outcome = FeaturePowerAttemptResult(power=Power.NEW_TEMP, applied=False, reason="wrong alignment", magic_feature=MagicFeature.POOL)
    assert describe_feature_power_attempt(outcome, ScriptedRandom([0.1] * 4)) is None


# -- Phase 782: the 4 generic PowerCondition refusals, DRAIN_COURAGE,
# and the DRAIN_SKILL mis-scoping fix (POWMSG.X2/PCOND.X2, backlog #7) --


def test_describe_feature_power_attempt_need_king_refused_is_power_agnostic():
    # Phase 803 (Desktop/PCCOND.md): NeedKing/SameAlign/GTurn now render
    # the real, byte-verified `_NoMeet` generic intro line directly --
    # POWER_CONDITION_REJECTION_INTRO -- not the old POWMSG-based guess.
    # MAGIC_FEATURE_NAME's own strings are raw, unresolved "<name>/F
    # <alternate>" compound templates (models/magic_feature.py's own
    # docstring) -- every existing test in this file avoids asserting
    # exact text across the `$\\` substitution point for exactly this
    # reason; this phase's new tests follow the same convention.
    for power in (Power.NEW_TEMP, Power.MAP_FEAT):
        outcome = FeaturePowerAttemptResult(
            power=power, applied=False, reason="only a King may use this power", condition_refused=PowerCondition.NEED_KING,
            magic_feature=MagicFeature.POOL,
        )
        line = describe_feature_power_attempt(outcome, ScriptedRandom([0.1] * 4))
        assert line.startswith("You don't meet the conditions for using the ")


def test_describe_feature_power_attempt_pay_up_refused_is_power_agnostic():
    for power in (Power.NEW_RACE, Power.SAGE_DISC):
        outcome = FeaturePowerAttemptResult(
            power=power, applied=False, reason="insufficient gold", condition_refused=PowerCondition.PAY_UP,
            magic_feature=MagicFeature.POOL,
        )
        line = describe_feature_power_attempt(outcome, ScriptedRandom([0.1] * 4))
        assert line.startswith("Your Kingdom doesn't have enough gold to use the power of the ")


def test_describe_feature_power_attempt_same_align_refused():
    # Phase 803: same generic intro line as NEED_KING -- the condition-
    # specific rejection text moved to describe_feature_power_condition_
    # terms(), see the new tests for that composer below.
    outcome = FeaturePowerAttemptResult(
        power=Power.NEW_TEMP, applied=False, reason="wrong alignment", condition_refused=PowerCondition.SAME_ALIGN,
        magic_feature=MagicFeature.POOL,
    )
    line = describe_feature_power_attempt(outcome, ScriptedRandom([0.1] * 4))
    assert line.startswith("You don't meet the conditions for using the ")


def test_describe_feature_power_attempt_g_turn_refused():
    outcome = FeaturePowerAttemptResult(
        power=Power.UP_SKILL, applied=False, reason="already used this gameturn", condition_refused=PowerCondition.G_TURN,
        magic_feature=MagicFeature.POOL,
    )
    line = describe_feature_power_attempt(outcome, ScriptedRandom([0.1] * 4))
    assert line.startswith("You don't meet the conditions for using the ")


def test_describe_feature_power_attempt_drain_skill_refused_reaches_a_power_other_than_grant_wish():
    # Regression test for the real mis-scoping bug found this phase:
    # _POWMSG_DRAIN_SKILL_REFUSED was only ever checked inside the
    # Power.GRANT_WISH branch, even though DRAIN_SKILL can gate any
    # power POWER_CONDITION_PAIRS names it for.
    outcome = FeaturePowerAttemptResult(
        power=Power.NEW_RACE, applied=False, reason="insufficient skill levels", condition_refused=PowerCondition.DRAIN_SKILL,
        magic_feature=MagicFeature.POOL,
    )
    line = describe_feature_power_attempt(outcome, ScriptedRandom([0.1] * 4))
    assert "thirst for wisdom" in line


def test_describe_feature_power_attempt_drain_courage_refused():
    outcome = FeaturePowerAttemptResult(
        power=Power.DN_APT, applied=False, reason="a Coward may not use this feature", condition_refused=PowerCondition.DRAIN_COURAGE,
        magic_feature=MagicFeature.POOL,
    )
    line = describe_feature_power_attempt(outcome, ScriptedRandom([0.1] * 4))
    assert line == "A Coward may not use this feature!"


def test_describe_feature_power_attempt_scout_consent_refusal_still_has_no_recovered_message():
    # condition_refused IS set (a real condition-gate refusal), but the
    # specific reason ("needs two Scout orders...") has no POWMSG.X2 id.
    outcome = FeaturePowerAttemptResult(
        power=Power.UP_SKILL,
        applied=False,
        reason="needs two Scout orders to accept these terms",
        condition_refused=PowerCondition.PAY_UP,
        magic_feature=MagicFeature.POOL,
    )
    assert describe_feature_power_attempt(outcome, ScriptedRandom([0.1] * 4)) is None


# Note: `test_describe_feature_power_attempt_gamble_refused()` below
# already proves Power.GAMBLE's own "insufficient gold" reason (set by
# its own internal wager-shortfall check, condition_refused left at its
# default None) is unaffected by the new generic PAY_UP dispatch above --
# confirmed unchanged by the standing non-breaking run for this phase.


def test_describe_feature_power_attempt_dn_skill_at_limit_matches_verbatim_source():
    # POWMSG.X2 line 14 reads "aptitude," not "skill" -- a confirmed,
    # byte-verified real-source wording quirk, corrected this phase.
    outcome = FeaturePowerAttemptResult(power=Power.DN_SKILL, applied=True, at_limit=True, ability=Ability.MELEE, magic_feature=MagicFeature.POOL)
    line = describe_feature_power_attempt(outcome, ScriptedRandom([0.1] * 4))
    assert "drains your aptitude in Meleeing" in line


def test_describe_feature_power_attempt_chance_has_no_recovered_message():
    # CHANCE isn't one of this phase's own 9 TRACTABLE_POWERS at all.
    outcome = FeaturePowerAttemptResult(power=Power.CHANCE, applied=False, reason="power not yet wired")
    assert describe_feature_power_attempt(outcome, ScriptedRandom([0.1] * 4)) is None


# -- Phase 619: the 8 SA-argument powers --


def _sa_state():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.GOOD, HexCoord(0, 0), treasury=100))
    state.add_leader(LeaderState(1, 1, "King Testerman", HexCoord(0, 0), is_king=True))
    state.add_leader(LeaderState(2, 1, "Sir Roland", HexCoord(1, 1), alignment=Alignment.GOOD))
    return state


def test_describe_feature_power_attempt_orac_align():
    outcome = FeaturePowerAttemptResult(
        power=Power.ORAC_ALIGN, applied=True, oracle_target_leader_id=2, oracle_alignment=Alignment.GOOD
    )
    line = describe_feature_power_attempt(outcome, ScriptedRandom([0.1] * 4), state=_sa_state(), character_name="King Testerman")
    assert line == "Sir Roland is a Good character."


def test_describe_feature_power_attempt_orac_align_uses_the_full_outname_not_the_abbreviation():
    # Phase 805 (Desktop/PCCOND.md, Phase 803's own flagged finding): the
    # real `$o` marker resolves via `outname` (Alignment.value), never
    # `ALIGNMENT_ABBREVIATION`/`outab` -- Good/Evil/Pagan happen to render
    # identically under both tables, so this needs an alignment where they
    # genuinely differ (e.g. "Divine" vs the abbreviated "Divin") to prove
    # the fix, not just leave the old bug coincidentally passing.
    outcome = FeaturePowerAttemptResult(
        power=Power.ORAC_ALIGN, applied=True, oracle_target_leader_id=2, oracle_alignment=Alignment.DIVINE
    )
    line = describe_feature_power_attempt(outcome, ScriptedRandom([0.1] * 4), state=_sa_state(), character_name="King Testerman")
    assert line == "Sir Roland is a Divine character."


def test_describe_feature_power_attempt_orac_power_with_armies():
    # Phase 804: the real per-army `_ArmSay` enumeration supersedes
    # Phase 782's own single "As an example..." sentence -- this
    # composer's own single-string contract can't express that list, so
    # it now returns None; describe_feature_power_oracle_power_armies()
    # is the only source of narration for this outcome.
    state = _sa_state()
    state.add_army(
        ArmyState(army_id=1, kingdom_id=1, army_type=ArmyType.BOWMEN, quality=Quality.AVERAGE, location=HexCoord(1, 1), commanded_by=2)
    )
    outcome = FeaturePowerAttemptResult(power=Power.ORAC_POWER, applied=True, oracle_target_leader_id=2, oracle_armies=tuple(state.armies.values()))
    line = describe_feature_power_attempt(outcome, ScriptedRandom([0.1] * 4), state=state, character_name="King Testerman")
    assert line is None


def test_describe_feature_power_attempt_orac_power_no_armies():
    outcome = FeaturePowerAttemptResult(power=Power.ORAC_POWER, applied=True, oracle_target_leader_id=2, oracle_armies=())
    line = describe_feature_power_attempt(outcome, ScriptedRandom([0.1] * 10), state=_sa_state(), character_name="King Testerman")
    assert "no armies" in line or "no soldiers" in line


def _army(army_id, army_type=ArmyType.BOWMEN, commanded_by=2):
    return ArmyState(
        army_id=army_id, kingdom_id=1, army_type=army_type, quality=Quality.AVERAGE, location=HexCoord(1, 1), commanded_by=commanded_by
    )


def test_describe_feature_power_oracle_power_armies_single_army_one_line():
    state = _sa_state()
    state.add_army(_army(1))
    outcome = FeaturePowerAttemptResult(
        power=Power.ORAC_POWER, applied=True, oracle_target_leader_id=2, oracle_armies=(state.armies[1],)
    )
    lines = describe_feature_power_oracle_power_armies(outcome, state, ScriptedRandom([0.1]))
    assert lines == ["Sir Roland leads 1st Bowmen."]


def test_describe_feature_power_oracle_power_armies_two_armies_two_separate_lines():
    state = _sa_state()
    state.add_army(_army(1, ArmyType.BOWMEN))
    state.add_army(_army(2, ArmyType.LT_CAVALRY))
    outcome = FeaturePowerAttemptResult(
        power=Power.ORAC_POWER, applied=True, oracle_target_leader_id=2, oracle_armies=(state.armies[1], state.armies[2])
    )
    lines = describe_feature_power_oracle_power_armies(outcome, state, ScriptedRandom([0.1, 0.9]))
    assert lines == ["Sir Roland leads 1st Bowmen.", "Sir Roland commands 2nd Lt Cav."]


@pytest.mark.parametrize(
    "outcome_kwargs",
    [
        {"power": Power.ORAC_POWER, "applied": False, "oracle_target_leader_id": 2, "oracle_armies": (_army(1),)},
        {"power": Power.ORAC_POWER, "applied": True, "oracle_target_leader_id": None, "oracle_armies": (_army(1),)},
        {"power": Power.ORAC_POWER, "applied": True, "oracle_target_leader_id": 2, "oracle_armies": None},
        {"power": Power.ORAC_POWER, "applied": True, "oracle_target_leader_id": 2, "oracle_armies": ()},
        {"power": Power.ORAC_ALIGN, "applied": True, "oracle_target_leader_id": 2, "oracle_armies": (_army(1),)},
    ],
)
def test_describe_feature_power_oracle_power_armies_returns_empty_for_every_ineligible_case(outcome_kwargs):
    outcome = FeaturePowerAttemptResult(**outcome_kwargs)
    assert describe_feature_power_oracle_power_armies(outcome, _sa_state(), ScriptedRandom([0.1] * 5)) == []


def test_describe_feature_power_oracle_power_armies_state_none_returns_empty():
    outcome = FeaturePowerAttemptResult(
        power=Power.ORAC_POWER, applied=True, oracle_target_leader_id=2, oracle_armies=(_army(1),)
    )
    assert describe_feature_power_oracle_power_armies(outcome, None, ScriptedRandom([0.1])) == []


def test_describe_feature_power_attempt_orac_office_vacant():
    outcome = FeaturePowerAttemptResult(power=Power.ORAC_OFFICE, applied=True, oracle_office=Office.EMPEROR, oracle_office_holder_leader_id=None)
    line = describe_feature_power_attempt(outcome, ScriptedRandom([0.1] * 4), state=_sa_state(), character_name="King Testerman")
    assert line == "No one has accomplished anything in the race for this office."


def test_describe_feature_power_attempt_orac_office_holder():
    outcome = FeaturePowerAttemptResult(
        power=Power.ORAC_OFFICE,
        applied=True,
        oracle_office=Office.EMPEROR,
        oracle_office_holder_leader_id=1,
        oracle_office_holder_merit_points=5,
    )
    line = describe_feature_power_attempt(outcome, ScriptedRandom([0.1] * 4), state=_sa_state(), character_name="King Testerman")
    assert "King Testerman" in line
    assert "Testia" in line


def test_describe_feature_power_attempt_orac_gold_success():
    outcome = FeaturePowerAttemptResult(power=Power.ORAC_GOLD, applied=True, oracle_target_leader_id=1, oracle_treasury=100)
    line = describe_feature_power_attempt(outcome, ScriptedRandom([0.1] * 4), state=_sa_state(), character_name="King Testerman")
    assert line == "King Testerman has a treasury of 100 gold."


def test_describe_feature_power_attempt_orac_gold_not_a_king():
    outcome = FeaturePowerAttemptResult(power=Power.ORAC_GOLD, applied=False, reason="not a King", oracle_target_leader_id=2)
    line = describe_feature_power_attempt(outcome, ScriptedRandom([0.1] * 4), state=_sa_state(), character_name="King Testerman")
    assert line == "Sir Roland is not a King but a Hero, and has little gold to speak of."


def test_describe_feature_power_attempt_orac_treas():
    state = _sa_state()
    state.features[42] = Feature(feature_id=42, coord=HexCoord(5, 5), kind=FeatureType.PYRAMID, treasure=Treasure.GOLD_HOARD_LARGE)
    outcome = FeaturePowerAttemptResult(power=Power.ORAC_TREAS, applied=True, oracle_feature_id=42, oracle_treasure=Treasure.GOLD_HOARD_LARGE)
    line = describe_feature_power_attempt(outcome, ScriptedRandom([0.1] * 4), state=state, character_name="King Testerman")
    assert TREASURE_NAME[Treasure.GOLD_HOARD_LARGE] in line


def test_describe_feature_power_attempt_recharge_success():
    state = _sa_state()
    item = state.add_item(Treasure.WAND_RESURRECTION, owner_leader_id=1, charges=3)
    outcome = FeaturePowerAttemptResult(power=Power.RECHARGE, applied=True, recharged_item_id=item.item_id, magic_feature=MagicFeature.LAMP)
    line = describe_feature_power_attempt(outcome, ScriptedRandom([0.1] * 4), state=state, character_name="King Testerman")
    assert TREASURE_NAME[Treasure.WAND_RESURRECTION] in line


def test_describe_feature_power_attempt_recharge_not_owned():
    outcome = FeaturePowerAttemptResult(power=Power.RECHARGE, applied=False, reason="item not owned", recharged_item_id=999)
    line = describe_feature_power_attempt(outcome, ScriptedRandom([0.1] * 4), state=_sa_state(), character_name="King Testerman")
    assert line == "Treasure 999 could not be recharged because King Testerman didn't own it."


def test_describe_feature_power_attempt_recharge_not_spell_casting():
    state = _sa_state()
    item = state.add_item(Treasure.GOLD_HOARD_LARGE, owner_leader_id=1, charges=0)
    outcome = FeaturePowerAttemptResult(power=Power.RECHARGE, applied=False, reason="not a spell-casting item", recharged_item_id=item.item_id)
    line = describe_feature_power_attempt(outcome, ScriptedRandom([0.1] * 4), state=state, character_name="King Testerman")
    assert TREASURE_NAME[Treasure.GOLD_HOARD_LARGE] in line
    assert "isn't a spell-casting item" in line


def test_describe_feature_power_attempt_grant_wish_success():
    outcome = FeaturePowerAttemptResult(power=Power.GRANT_WISH, applied=True, ability=Ability.MELEE, new_skill_level=2)
    line = describe_feature_power_attempt(outcome, ScriptedRandom([0.1] * 4), state=_sa_state(), character_name="King Testerman")
    assert "one point higher" in line


def test_describe_feature_power_attempt_grant_wish_at_limit():
    outcome = FeaturePowerAttemptResult(power=Power.GRANT_WISH, applied=True, at_limit=True, ability=Ability.MELEE)
    line = describe_feature_power_attempt(outcome, ScriptedRandom([0.1] * 4), state=_sa_state(), character_name="King Testerman")
    assert "cannot grant the wish" in line


def test_describe_feature_power_attempt_grant_wish_drain_skill_refused():
    outcome = FeaturePowerAttemptResult(
        power=Power.GRANT_WISH,
        applied=False,
        reason="insufficient skill levels",
        condition_refused=PowerCondition.DRAIN_SKILL,
        magic_feature=MagicFeature.LAMP,
    )
    line = describe_feature_power_attempt(outcome, ScriptedRandom([0.1] * 4), state=_sa_state(), character_name="King Testerman")
    assert "thirst for wisdom" in line


def test_describe_feature_power_attempt_gamble_won():
    outcome = FeaturePowerAttemptResult(
        power=Power.GAMBLE,
        applied=True,
        gamble_amount=10,
        gamble_character_roll=8,
        gamble_house_roll=5,
        gamble_won=True,
        oracle_target_leader_id=1,
        magic_feature=MagicFeature.LAMP,
    )
    line = describe_feature_power_attempt(outcome, ScriptedRandom([0.1] * 4), state=_sa_state(), character_name="King Testerman")
    assert "won 10 gold for Testia" in line
    assert "a 8" in line and "a 5" in line


def test_describe_feature_power_attempt_gamble_lost():
    outcome = FeaturePowerAttemptResult(
        power=Power.GAMBLE,
        applied=True,
        gamble_amount=10,
        gamble_character_roll=4,
        gamble_house_roll=9,
        gamble_won=False,
        oracle_target_leader_id=1,
        magic_feature=MagicFeature.LAMP,
    )
    line = describe_feature_power_attempt(outcome, ScriptedRandom([0.1] * 4), state=_sa_state(), character_name="King Testerman")
    assert "Testia lost 10 gold" in line


def test_describe_feature_power_attempt_gamble_refused():
    outcome = FeaturePowerAttemptResult(power=Power.GAMBLE, applied=False, reason="insufficient gold", gamble_amount=1000, oracle_target_leader_id=1)
    line = describe_feature_power_attempt(outcome, ScriptedRandom([0.1] * 4), state=_sa_state(), character_name="King Testerman")
    assert line == "Hah!The realm of Testia isn't that rich.Begone!"


def test_describe_feature_power_attempt_sa_power_without_state_renders_nothing():
    outcome = FeaturePowerAttemptResult(power=Power.ORAC_ALIGN, applied=True, oracle_target_leader_id=2, oracle_alignment=Alignment.GOOD)
    assert describe_feature_power_attempt(outcome, ScriptedRandom([0.1] * 4)) is None


# -- Phase 620: CAST_SPELL/ANS_PRAYER's Part_Sea/Flood/Earthquake subset --


def test_describe_feature_power_attempt_cast_spell_success():
    outcome = FeaturePowerAttemptResult(power=Power.CAST_SPELL, applied=True, cast_spell=Spell.FLOOD)
    line = describe_feature_power_attempt(outcome, ScriptedRandom([0.1] * 4))
    assert line == f"I give you the power to cast a {SPELL_NAME[Spell.FLOOD]} spell!"


def test_describe_feature_power_attempt_ans_prayer_success_reuses_the_same_message():
    outcome = FeaturePowerAttemptResult(power=Power.ANS_PRAYER, applied=True, cast_spell=Spell.EARTHQUAKE)
    line = describe_feature_power_attempt(outcome, ScriptedRandom([0.1] * 4))
    assert line == f"I give you the power to cast a {SPELL_NAME[Spell.EARTHQUAKE]} spell!"


def test_describe_feature_power_attempt_cast_spell_failure_has_no_recovered_message():
    outcome = FeaturePowerAttemptResult(power=Power.CAST_SPELL, applied=False, reason="target province is not Sea", cast_spell=Spell.PART_SEA)
    assert describe_feature_power_attempt(outcome, ScriptedRandom([0.1] * 4)) is None


# -- Phase 801 (Desktop/POWMSG.md choice 18): CAST_SPELL/ANS_PRAYER
# granting Spell.ILLUS_TERRAIN overrides the generic choice-43 text --


def test_describe_feature_power_attempt_cast_spell_illus_terrain_uses_the_real_demonstration_text():
    outcome = FeaturePowerAttemptResult(
        power=Power.CAST_SPELL, applied=True, cast_spell=Spell.ILLUS_TERRAIN, cast_illusory_terrain=Terrain.SEA
    )
    line = describe_feature_power_attempt(outcome, ScriptedRandom([0.1] * 4))
    assert line == "As a demonstration, I will change the appearance of this province to Sea!"


def test_describe_feature_power_attempt_ans_prayer_illus_terrain_uses_the_same_override():
    outcome = FeaturePowerAttemptResult(
        power=Power.ANS_PRAYER, applied=True, cast_spell=Spell.ILLUS_TERRAIN, cast_illusory_terrain=Terrain.JUNGLE
    )
    line = describe_feature_power_attempt(outcome, ScriptedRandom([0.1] * 4))
    assert line == "As a demonstration, I will change the appearance of this province to Jungle!"


def test_describe_feature_power_attempt_illus_terrain_without_a_chosen_terrain_falls_back_to_the_generic_text():
    # Defensive -- shouldn't happen in practice (resolve_feature_power_
    # attempt() always stamps cast_illusory_terrain alongside cast_spell
    # for a real ILLUS_TERRAIN attempt), but a missing value must not
    # crash, and must not silently render an unresolved "`" marker.
    outcome = FeaturePowerAttemptResult(power=Power.CAST_SPELL, applied=True, cast_spell=Spell.ILLUS_TERRAIN, cast_illusory_terrain=None)
    line = describe_feature_power_attempt(outcome, ScriptedRandom([0.1] * 4))
    assert line == f"I give you the power to cast a {SPELL_NAME[Spell.ILLUS_TERRAIN]} spell!"


def test_describe_search_appends_the_feature_power_line_when_present():
    outcome = FeaturePowerAttemptResult(power=Power.MAP_FEAT, applied=False, reason="no more features to reveal")
    result = SearchExecutionResult(accepted=True, combat_resolved=False, feature_power_outcome=outcome)
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])

    lines = describe_search(result, character_name="Aldric", feature_name="Ancient Ruins", rng=rng)

    assert lines == [
        "Aldric approached the Ancient Ruins, intending to root out its mysteries.",
        "There are no more features to be told of in the provinces you have mapped.",
    ]


def test_describe_search_omits_the_feature_power_line_when_none_recovered():
    outcome = FeaturePowerAttemptResult(power=Power.CHANCE, applied=False, reason="power not yet wired")
    result = SearchExecutionResult(accepted=True, combat_resolved=False, feature_power_outcome=outcome)
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])

    lines = describe_search(result, character_name="Aldric", feature_name="Ancient Ruins", rng=rng)

    assert lines == ["Aldric approached the Ancient Ruins, intending to root out its mysteries."]


def test_describe_search_orac_power_has_armies_renders_per_army_lines_with_no_summary_sentence():
    # Phase 804: describe_feature_power_attempt() itself contributes no
    # power_line for this outcome (returns None) -- the real narration
    # comes entirely from describe_feature_power_oracle_power_armies().
    state = _sa_state()
    state.add_army(_army(1, ArmyType.BOWMEN))
    outcome = FeaturePowerAttemptResult(
        power=Power.ORAC_POWER, applied=True, oracle_target_leader_id=2, oracle_armies=(state.armies[1],)
    )
    result = SearchExecutionResult(accepted=True, combat_resolved=False, feature_power_outcome=outcome)
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])

    lines = describe_search(result, state=state, character_name="Aldric", feature_name="Ancient Ruins", rng=rng)

    assert lines == [
        "Aldric approached the Ancient Ruins, intending to root out its mysteries.",
        "Sir Roland leads 1st Bowmen.",
    ]


# -- Phase 790: describe_feature_power_needs_more_info() (SAY.PAS `_EDesc` "needy") --


@pytest.mark.parametrize(
    "power",
    [
        Power.ORAC_ALIGN,
        Power.ORAC_POWER,
        Power.ORAC_OFFICE,
        Power.ORAC_GOLD,
        Power.ORAC_TREAS,
        Power.RECHARGE,
        # Power.GRANT_WISH deliberately excluded -- Phase 801, it now
        # renders its own real POWMSG-30-then-31 text instead (see
        # test_describe_feature_power_needs_more_info_excludes_grant_wish
        # below).
        Power.GAMBLE,
    ],
)
def test_describe_feature_power_needs_more_info_renders_both_lines_for_every_sa_argument_power(power):
    outcome = FeaturePowerAttemptResult(power=power, applied=False, reason="no SA argument given", magic_feature=MagicFeature.POOL)
    lines = describe_feature_power_needs_more_info(outcome, ScriptedRandom([0.1] * 4))
    assert lines[0] == "The Pool/FStream needs more information to perform its power."
    assert len(lines) == 2
    assert "Pool/FStream" in lines[1]


def test_describe_feature_power_needs_more_info_excludes_grant_wish():
    # Phase 801: Desktop/POWMSG.md's own disassembly-verified account of
    # GRANT_WISH's own real dispatcher shows only POWMSG choices 30-
    # then-31 firing for this refusal, not this generic `_EDesc` pair --
    # see describe_feature_power_attempt()'s own GRANT_WISH branch.
    outcome = FeaturePowerAttemptResult(
        power=Power.GRANT_WISH, applied=False, reason="no SA argument given", magic_feature=MagicFeature.POOL
    )
    assert describe_feature_power_needs_more_info(outcome, ScriptedRandom([0.1] * 4)) == []


def test_describe_feature_power_needs_more_info_non_matching_reason_returns_nothing():
    outcome = FeaturePowerAttemptResult(power=Power.ORAC_ALIGN, applied=True, reason=None, magic_feature=MagicFeature.POOL)
    assert describe_feature_power_needs_more_info(outcome, ScriptedRandom([0.1] * 4)) == []


def test_describe_feature_power_needs_more_info_wrong_power_reason_returns_nothing():
    # A refusal with some other real reason string on a power outside
    # SA_ARGUMENT_POWERS -- the exact reason text is what gates this,
    # not the power itself, but this confirms an unrelated refusal
    # never accidentally matches.
    outcome = FeaturePowerAttemptResult(power=Power.UP_SKILL, applied=False, reason="insufficient gold")
    assert describe_feature_power_needs_more_info(outcome, ScriptedRandom([0.1] * 4)) == []


def test_describe_feature_power_needs_more_info_no_magic_feature_still_renders_gracefully():
    outcome = FeaturePowerAttemptResult(power=Power.ORAC_ALIGN, applied=False, reason="no SA argument given", magic_feature=None)
    lines = describe_feature_power_needs_more_info(outcome, ScriptedRandom([0.1] * 4))
    assert lines[0] == "The $\\ needs more information to perform its power."
    assert len(lines) == 2


def test_describe_search_renders_magic_feature_discovery_before_the_feature_power_line():
    power_outcome = FeaturePowerAttemptResult(power=Power.MAP_FEAT, applied=False, reason="no more features to reveal")
    result = SearchExecutionResult(
        accepted=True, combat_resolved=False, magic_feature_discovered=MagicFeature.POOL, feature_power_outcome=power_outcome
    )
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])

    lines = describe_search(result, character_name="Aldric", feature_name="Ancient Ruins", rng=rng)

    assert lines == [
        "Aldric approached the Ancient Ruins, intending to root out its mysteries.",
        "While scouting the Ancient Ruins, Aldric saw a Pool/FStream which seemed to be of a magical nature.",
        "There are no more features to be told of in the provinces you have mapped.",
    ]


def test_describe_search_needs_more_info_refusal_renders_after_the_empty_power_line():
    power_outcome = FeaturePowerAttemptResult(
        power=Power.ORAC_ALIGN, applied=False, reason="no SA argument given", magic_feature=MagicFeature.POOL
    )
    result = SearchExecutionResult(accepted=True, combat_resolved=False, feature_power_outcome=power_outcome)
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])

    lines = describe_search(result, character_name="Aldric", feature_name="Ancient Ruins", rng=rng)

    # describe_feature_power_attempt() itself renders nothing for this
    # refusal (no recovered POWMSG id) -- both new lines still follow.
    assert lines == [
        "Aldric approached the Ancient Ruins, intending to root out its mysteries.",
        "The Pool/FStream needs more information to perform its power.",
        "The Pool/FStream is an Oracle of Alignment.When you scout it, just SA-y the character number "
        '(not the name; e.g., "SA Tell me about character 1.") and the character\'s alignment will become '
        "known to you.",
    ]


def test_describe_search_grant_wish_invalid_argument_renders_the_tutorial_then_at_limit_text():
    # Phase 801: supersedes the generic `_EDesc` pair for GRANT_WISH
    # specifically -- see describe_feature_power_attempt()'s own
    # GRANT_WISH branch and describe_feature_power_needs_more_info()'s
    # own exclusion of this power.
    power_outcome = FeaturePowerAttemptResult(
        power=Power.GRANT_WISH, applied=False, reason="no SA argument given", magic_feature=MagicFeature.POOL
    )
    result = SearchExecutionResult(accepted=True, combat_resolved=False, feature_power_outcome=power_outcome)
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])

    lines = describe_search(result, character_name="Aldric", feature_name="Ancient Ruins", rng=rng)

    assert lines == [
        "Aldric approached the Ancient Ruins, intending to root out its mysteries.",
        "The Pool/FStream will grant a wish to a character.SA-y an ability number (not the skill name itself), "
        "and your skill shall be raised by one: 0-Tac, 1-Mar, 2-Nav, 3-Arc, 4-Mel, 5-Whi, 6-Nec, 7-Ele, 8-Psy, "
        "9-Ill, 10-Dru, 11-Thi, 12-Exp, 13-Spy, 14-Sage. "
        "The Pool/FStream cannot grant the wish if the character's skill has already reached his aptitude level.",
    ]


# -- Phase 801: describe_feature_power_condition_terms()/_satisfied()
# (PCOND.X2/MCOND.X2, `Desktop/POWMSG.md` Approfondimento 4) --


@pytest.mark.parametrize(
    "condition,cost,expected",
    [
        (
            PowerCondition.PAY_UP,
            5,
            "You must pay 5 gold each time the Pool/FStream is used (to show that you accept these terms, "
            "a character must give two Scout orders when he Searches this feature.)",
        ),
        (
            PowerCondition.DRAIN_SKILL,
            2,
            "2 skill level(s), chosen at random, will be drained from the character if the Pool/FStream is "
            "scouted.You MUST have enough skill levels to meet the Pool/FStream's demand (to accept these "
            "terms, a character must give two Scout orders when Searching this feature.",
        ),
        (
            PowerCondition.DRAIN_COURAGE,
            None,
            "When you use the Pool/FStream, it will drain away one level of courage (Brave men become "
            "Cautious, etc.)A Coward may not use this feature!To accept these terms, a character must give "
            "two Scout orders when Searching this feature.",
        ),
    ],
)
def test_describe_feature_power_condition_terms_renders_pcond_text(condition, cost, expected):
    outcome = FeaturePowerAttemptResult(
        power=Power.NEW_TEMP,
        applied=False,
        reason="needs two Scout orders to accept these terms",
        condition_refused=condition,
        condition_cost=cost,
        magic_feature=MagicFeature.POOL,
    )
    lines = describe_feature_power_condition_terms(outcome, ScriptedRandom([0.1] * 4))
    assert lines == [expected]


def test_describe_feature_power_condition_terms_non_matching_reason_returns_nothing():
    outcome = FeaturePowerAttemptResult(power=Power.NEW_TEMP, applied=True, reason=None, condition_refused=None)
    assert describe_feature_power_condition_terms(outcome, ScriptedRandom([0.1] * 4)) == []

    # A refusal for an unrelated reason on one of the 3 real Scout-
    # consent conditions is still not the Scout-consent case itself.
    other_refusal = FeaturePowerAttemptResult(
        power=Power.NEW_TEMP, applied=False, reason="insufficient gold", condition_refused=PowerCondition.PAY_UP
    )
    assert describe_feature_power_condition_terms(other_refusal, ScriptedRandom([0.1] * 4)) == []


# -- Phase 803 (Desktop/PCCOND.md): describe_feature_power_condition_
# terms() widened past the Scout-consent trigger alone -- a real
# NeedKing/SameAlign/GTurn refusal now renders PCOND's own "terms" line
# followed by the condition-specific rejection, in the confirmed real
# order (_NoMeet). --


def test_describe_feature_power_condition_terms_need_king_renders_both_lines_in_order():
    outcome = FeaturePowerAttemptResult(
        power=Power.NEW_TEMP,
        applied=False,
        reason="only a King may use this power",
        condition_refused=PowerCondition.NEED_KING,
        magic_feature=MagicFeature.POOL,
    )
    # 2 draws for the rejection message's own leading /R markers (left/
    # left), 1 for its final "here/Rthis_&" marker (right, so `&`
    # actually resolves in the output -- proven via `feature_name`).
    lines = describe_feature_power_condition_terms(outcome, ScriptedRandom([0.1, 0.1, 0.9]), feature_name="Ancient Ruins")
    assert lines == [
        "Only a King may use the power of the Pool/FStream.",
        "You're just a lowly hero, so get out of this Ancient Ruins!",
    ]


def test_describe_feature_power_condition_terms_same_align_resolves_the_real_alignment_via_o_marker():
    outcome = FeaturePowerAttemptResult(
        power=Power.NEW_TEMP,
        applied=False,
        reason="wrong alignment",
        condition_refused=PowerCondition.SAME_ALIGN,
        required_alignment=Alignment.EVIL,
        magic_feature=MagicFeature.POOL,
    )
    lines = describe_feature_power_condition_terms(outcome, ScriptedRandom([0.9]))
    assert lines == [
        "A character must be Evil to use the Pool/FStream (the Kingdom alignment does not matter.)",
        "You are not Evil, so go away!",
    ]


def test_describe_feature_power_condition_terms_g_turn_renders_both_lines_with_no_markers_to_resolve():
    outcome = FeaturePowerAttemptResult(
        power=Power.UP_SKILL,
        applied=False,
        reason="already used this gameturn",
        condition_refused=PowerCondition.G_TURN,
        magic_feature=MagicFeature.POOL,
    )
    lines = describe_feature_power_condition_terms(outcome, ScriptedRandom([]))
    assert lines == [
        "After the power of the Pool/FStream is used in a gameturn, it may not be used again until the next gameturn.",
        "The power has already been used this turn, so go away!",
    ]


def test_describe_feature_power_condition_terms_pay_up_drain_skill_drain_courage_unaffected_by_the_widening():
    # PayUp/DrainSkill/DrainCourage stay gated on the pre-existing Scout-
    # consent trigger only -- a refusal for any OTHER reason on one of
    # these 3 conditions still renders nothing, non-regression of the
    # behavior `test_describe_feature_power_condition_terms_non_matching_
    # reason_returns_nothing` already covers for PayUp.
    for condition, reason in (
        (PowerCondition.DRAIN_SKILL, "insufficient skill levels"),
        (PowerCondition.DRAIN_COURAGE, "a Coward may not use this feature"),
    ):
        outcome = FeaturePowerAttemptResult(
            power=Power.NEW_TEMP, applied=False, reason=reason, condition_refused=condition
        )
        assert describe_feature_power_condition_terms(outcome, ScriptedRandom([0.1] * 4)) == []


@pytest.mark.parametrize(
    "condition,cost,expected",
    [
        (
            PowerCondition.PAY_UP,
            5,
            'Aldric plunked down the gold.Spake Aldric, "I have brought you 5 gold, as you have asked", '
            "and the gold immediately disappeared.",
        ),
        (
            PowerCondition.DRAIN_SKILL,
            2,
            'Spake Aldric, "I am willing to give up the 2 skill levels".',
        ),
        (
            PowerCondition.DRAIN_COURAGE,
            None,
            'Spake Aldric, "I agree to lose some of my courage in exchange for your favor".'
            "immediately, Aldric felt less hot-tempered.",
        ),
    ],
)
def test_describe_feature_power_condition_satisfied_renders_mcond_text(condition, cost, expected):
    outcome = FeaturePowerAttemptResult(
        power=Power.NEW_TEMP, applied=True, condition_satisfied=condition, condition_cost=cost, magic_feature=MagicFeature.POOL
    )
    lines = describe_feature_power_condition_satisfied(outcome, ScriptedRandom([0.1] * 10), character_name="Aldric")
    assert lines == [expected]


def test_describe_feature_power_condition_satisfied_none_returns_nothing():
    outcome = FeaturePowerAttemptResult(power=Power.NEW_TEMP, applied=True, condition_satisfied=None)
    assert describe_feature_power_condition_satisfied(outcome, ScriptedRandom([0.1] * 4), character_name="Aldric") == []


def test_describe_search_scout_consent_refusal_renders_the_real_pcond_terms():
    power_outcome = FeaturePowerAttemptResult(
        power=Power.NEW_SEX,
        applied=False,
        reason="needs two Scout orders to accept these terms",
        condition_refused=PowerCondition.DRAIN_SKILL,
        condition_cost=2,
        magic_feature=MagicFeature.POOL,
    )
    result = SearchExecutionResult(accepted=True, combat_resolved=False, feature_power_outcome=power_outcome)
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])

    lines = describe_search(result, character_name="Aldric", feature_name="Ancient Ruins", rng=rng)

    # describe_feature_power_attempt() itself renders nothing for this
    # refusal -- the PCOND terms line is the entire added content.
    assert lines == [
        "Aldric approached the Ancient Ruins, intending to root out its mysteries.",
        "2 skill level(s), chosen at random, will be drained from the character if the Pool/FStream is "
        "scouted.You MUST have enough skill levels to meet the Pool/FStream's demand (to accept these "
        "terms, a character must give two Scout orders when Searching this feature.",
    ]


def test_describe_search_need_king_refusal_renders_the_full_real_three_line_sequence():
    # Phase 803: NeedKing's own real sequence, end to end -- the generic
    # intro (describe_feature_power_attempt()), then PCOND's own terms
    # description, then the specific rejection (describe_feature_power_
    # condition_terms()), matching the byte-verified real `_NoMeet` order.
    power_outcome = FeaturePowerAttemptResult(
        power=Power.NEW_TEMP,
        applied=False,
        reason="only a King may use this power",
        condition_refused=PowerCondition.NEED_KING,
        magic_feature=MagicFeature.POOL,
    )
    result = SearchExecutionResult(accepted=True, combat_resolved=False, feature_power_outcome=power_outcome)
    rng = ScriptedRandom([0.1, 0.1, 0.1, 0.1, 0.1, 0.9], choice_indices=[0])

    lines = describe_search(result, character_name="Aldric", feature_name="Ancient Ruins", rng=rng)

    assert lines == [
        "Aldric approached the Ancient Ruins, intending to root out its mysteries.",
        "You don't meet the conditions for using the Pool/FStream.",
        "Only a King may use the power of the Pool/FStream.",
        "You're just a lowly hero, so get out of this Ancient Ruins!",
    ]


def test_describe_search_scout_consent_success_renders_the_power_line_then_mcond():
    power_outcome = FeaturePowerAttemptResult(
        power=Power.NEW_SEX,
        applied=True,
        new_sex=Sex.FEMALE,
        condition_satisfied=PowerCondition.DRAIN_COURAGE,
        magic_feature=MagicFeature.POOL,
    )
    result = SearchExecutionResult(accepted=True, combat_resolved=False, feature_power_outcome=power_outcome)
    rng = ScriptedRandom([0.1] * 30, choice_indices=[0])

    lines = describe_search(result, character_name="Aldric", feature_name="Ancient Ruins", rng=rng)

    assert lines == [
        "Aldric approached the Ancient Ruins, intending to root out its mysteries.",
        "By the power of the Pool/FStream, I change you to a woman!Hee hee, how do you like THEM apples!",
        'Spake Aldric, "I agree to lose some of my courage in exchange for your favor".'
        "immediately, Aldric felt less hot-tempered.",
    ]


def test_describe_search_no_feature_power_outcome_skips_needs_more_info_entirely():
    result = SearchExecutionResult(accepted=True, combat_resolved=False)
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])

    lines = describe_search(result, character_name="Aldric", feature_name="Ancient Ruins", rng=rng)

    assert lines == ["Aldric approached the Ancient Ruins, intending to root out its mysteries."]


# -- Phase 175: per-shot Fire Arrow narration, including the dragon-breath/
# boulder-throw/petrifying-gaze species flavor --


def test_describe_search_monster_breath_weapon_hit_uses_flavored_renderer():
    result = SearchExecutionResult(
        accepted=True,
        combat_resolved=True,
        winner=None,
        fire_arrow_shots=(FireArrowShot(shooter="b", hit=True, damage=7),),
        guardian_monster=Monster.R_DRAGON,
    )
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])

    lines = describe_search(result, character_name="Aldric", feature_name="Ancient Ruins", rng=rng)

    assert lines == [
        "Aldric approached the Ancient Ruins, intending to root out its mysteries.",
        "The Red Dragon breathes, and the impact deals 7 damage points.",
    ]


def test_describe_search_monster_breath_weapon_miss_uses_flavored_renderer():
    result = SearchExecutionResult(
        accepted=True,
        combat_resolved=True,
        winner=None,
        fire_arrow_shots=(FireArrowShot(shooter="b", hit=False, damage=0),),
        guardian_monster=Monster.GR_DRAGON,
    )
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])

    lines = describe_search(result, character_name="Aldric", feature_name="Ancient Ruins", rng=rng)

    assert lines == [
        "Aldric approached the Ancient Ruins, intending to root out its mysteries.",
        "The Green Dragon breathes, but Aldric miraculously manages to evade it!",
    ]


def test_describe_search_giant_boulder_throw_hit_uses_flavored_renderer():
    result = SearchExecutionResult(
        accepted=True,
        combat_resolved=True,
        winner=None,
        fire_arrow_shots=(FireArrowShot(shooter="b", hit=True, damage=6),),
        guardian_monster=Monster.GIANT,
    )
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])

    lines = describe_search(result, character_name="Aldric", feature_name="Ancient Ruins", rng=rng)

    assert lines == [
        "Aldric approached the Ancient Ruins, intending to root out its mysteries.",
        "The Giant hurls a huge boulder, and the impact deals 6 damage points.",
    ]


def test_describe_search_basilisk_petrifying_gaze_miss_uses_flavored_renderer():
    result = SearchExecutionResult(
        accepted=True,
        combat_resolved=True,
        winner=None,
        fire_arrow_shots=(FireArrowShot(shooter="b", hit=False, damage=0),),
        guardian_monster=Monster.BASILISK,
    )
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])

    lines = describe_search(result, character_name="Aldric", feature_name="Ancient Ruins", rng=rng)

    assert lines == [
        "Aldric approached the Ancient Ruins, intending to root out its mysteries.",
        "The Basilisk casts a gaze, but Aldric evades it.",
    ]


def test_describe_search_leader_shot_always_uses_the_generic_renderer_even_vs_a_flavored_monster():
    # Only the guardian's own shots get species flavor -- the leader's
    # never do, per the user's own footnote wording (module docstring's
    # Phase 175 addendum).
    result = SearchExecutionResult(
        accepted=True,
        combat_resolved=True,
        winner=None,
        fire_arrow_shots=(FireArrowShot(shooter="a", hit=True, damage=4),),
        guardian_monster=Monster.R_DRAGON,
    )
    rng = ScriptedRandom([0.1] * 40, choice_indices=[0, 0, 0])

    lines = describe_search(result, character_name="Aldric", feature_name="Ancient Ruins", rng=rng)

    assert len(lines) == 2
    assert "breathes" not in lines[1]
    assert lines[1] == "Aldric Fired an arrow at Red Dragon and inflicted 4 damage points."


def test_describe_search_titan_has_no_flavor_mapping_falls_back_to_generic():
    # models/weapon.py's own deliberately-preserved discrepancy: Titan
    # maps to Weapon.NO_WEAP, not Weapon.BOULDER, despite the user's own
    # footnote naming Titan alongside Giant/Treant for the boulder throw.
    result = SearchExecutionResult(
        accepted=True,
        combat_resolved=True,
        winner=None,
        fire_arrow_shots=(FireArrowShot(shooter="b", hit=False, damage=0),),
        guardian_monster=Monster.TITAN,
    )
    rng = ScriptedRandom([0.1] * 40, choice_indices=[0, 0, 0])

    lines = describe_search(result, character_name="Aldric", feature_name="Ancient Ruins", rng=rng)

    assert len(lines) == 2
    assert "hurls a huge boulder" not in lines[1]
    assert lines[1] == "Titan Fired an arrow at Aldric and missed."


def test_describe_search_shot_narration_appears_before_the_mortal_wound_line():
    result = SearchExecutionResult(
        accepted=True,
        combat_resolved=True,
        winner="monster",
        leader_killed=True,
        fire_arrow_shots=(FireArrowShot(shooter="b", hit=True, damage=9),),
        guardian_monster=Monster.R_DRAGON,
    )
    # Phase 611: HORDEATH.X's own generic closing beat now follows.
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0, 0, 0])

    lines = describe_search(result, character_name="Aldric", feature_name="Ancient Ruins", rng=rng)

    assert lines == [
        "Aldric approached the Ancient Ruins, intending to root out its mysteries.",
        "The Red Dragon breathes, and the impact deals 9 damage points.",
        "Aldric was mortally wounded.",
        "and so it was that Aldric met Aldric's unseemly end.",
    ]


# -- Phase 413: Hand of Death's own per-round squeeze narration ------------


def test_describe_search_squeeze_hits_narrated_for_a_leader_win():
    result = SearchExecutionResult(
        accepted=True,
        combat_resolved=True,
        winner="leader",
        feature_looted=True,
        squeeze_hits=(3, 2),
    )
    rng = ScriptedRandom([0.1] * 30, choice_indices=[0, 0, 0, 0, 0])

    lines = describe_search(result, character_name="Aldric", feature_name="Ancient Ruins", rng=rng)

    assert lines == [
        "Aldric approached the Ancient Ruins, intending to root out its mysteries.",
        "Aldric curled Aldric's phantasmal hand around guardian's heart and squeezed it and inflicted 3 damage points.",
        "Aldric curled Aldric's phantasmal hand around guardian's heart and squeezed it and inflicted 2 damage points.",
    ]


def test_describe_search_squeeze_hits_narrated_before_the_mortal_wound_line_for_a_monster_win():
    result = SearchExecutionResult(
        accepted=True,
        combat_resolved=True,
        winner="monster",
        leader_killed=True,
        squeeze_hits=(4,),
    )
    # Phase 611: HORDEATH.X's own generic closing beat now follows.
    rng = ScriptedRandom([0.1] * 30, choice_indices=[0, 0, 0, 0, 0])

    lines = describe_search(result, character_name="Aldric", feature_name="Ancient Ruins", rng=rng)

    assert lines == [
        "Aldric approached the Ancient Ruins, intending to root out its mysteries.",
        "guardian curled guardian's phantasmal hand around Aldric's heart and squeezed it and inflicted 4 damage points.",
        "Aldric was mortally wounded.",
        "and so it was that Aldric met Aldric's unseemly end.",
    ]


# -- Phase 415: ordinary Melee's own per-swing narration --------------------


def test_describe_search_melee_swings_narrated_in_chronological_order_both_directions():
    result = SearchExecutionResult(
        accepted=True,
        combat_resolved=True,
        winner="leader",
        feature_looted=True,
        melee_swings=(
            MeleeSwing(attacker="a", hit=True, damage=5),
            MeleeSwing(attacker="b", hit=False, damage=0),
        ),
    )
    rng = ScriptedRandom([0.1] * 30, choice_indices=[0, 8, 0, 8, 0])

    lines = describe_search(result, character_name="Aldric", feature_name="Ancient Ruins", rng=rng)

    assert lines == [
        "Aldric approached the Ancient Ruins, intending to root out its mysteries.",
        "Aldric Attacked guardian and inflicted 5 damage points.",
        "guardian Attacked Aldric and missed.",
    ]


def test_describe_search_melee_swings_narrated_before_the_mortal_wound_line_for_a_monster_win():
    result = SearchExecutionResult(
        accepted=True,
        combat_resolved=True,
        winner="monster",
        leader_killed=True,
        melee_swings=(MeleeSwing(attacker="b", hit=True, damage=6),),
    )
    # Phase 611: HORDEATH.X's own generic closing beat now follows.
    rng = ScriptedRandom([0.1] * 30, choice_indices=[0, 8, 0, 0, 0])

    lines = describe_search(result, character_name="Aldric", feature_name="Ancient Ruins", rng=rng)

    assert lines == [
        "Aldric approached the Ancient Ruins, intending to root out its mysteries.",
        "guardian Attacked Aldric and inflicted 6 damage points.",
        "Aldric was mortally wounded.",
        "and so it was that Aldric met Aldric's unseemly end.",
    ]


def test_describe_search_melee_swings_narrated_after_squeeze_hits():
    result = SearchExecutionResult(
        accepted=True,
        combat_resolved=True,
        winner="leader",
        feature_looted=True,
        squeeze_hits=(3,),
        melee_swings=(MeleeSwing(attacker="a", hit=True, damage=2),),
    )
    rng = ScriptedRandom([0.1] * 30, choice_indices=[0, 0, 0, 8, 0])

    lines = describe_search(result, character_name="Aldric", feature_name="Ancient Ruins", rng=rng)

    assert lines == [
        "Aldric approached the Ancient Ruins, intending to root out its mysteries.",
        "Aldric curled Aldric's phantasmal hand around guardian's heart and squeezed it and inflicted 3 damage points.",
        "Aldric Attacked guardian and inflicted 2 damage points.",
    ]


# -- Phase 157: Quote of the Week --


def test_render_quote_of_the_week_first_block():
    lines = render_quote_of_the_week(0)

    assert lines == [
        "Quote of the Week:",
        '"The King of England has men, horses, silk, jewels, fruit, game and everything '
        'else.  And we in France have nothing but bread and wine and gaiety!"',
        "-Louis VII, King of France, 1179 A.D.",
    ]


def test_render_quote_of_the_week_returns_three_paragraphs():
    # Header + the block's own two source lines, each a separate
    # paragraph -- matching _SQuote's own per-line PR1 behavior.
    lines = render_quote_of_the_week(1)

    assert len(lines) == 3
    assert lines[0] == "Quote of the Week:"


def test_render_quote_of_the_week_out_of_range_raises_index_error():
    with pytest.raises(IndexError):
        render_quote_of_the_week(94)


# -- Phase 158: ARMIES report (describe_armies_report) --


def _armies_state() -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_province(ProvinceState(HexCoord(0, 0), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, name="Capital City"))
    return state


def test_describe_armies_report_opening_lines():
    state = _armies_state()
    lines = describe_armies_report(state, 1)

    assert lines[0] == "ARMIES"
    assert lines[1] == (
        "Excellence, thy armies have trained hard and honed their weapons to a fine "
        "edge.  Proudly they serve thy imperial majesty, and they await thy commands."
    )


def test_describe_armies_report_no_armies_renders_none_at_present():
    state = _armies_state()
    lines = describe_armies_report(state, 1)

    assert lines[2:] == ["None at present"]


# REPORTS.PAS Rep_Armies Doit (~lines 945-950), Hired-pass variant,
# verbatim (Phase 433) -- see turn_report.py's own module-level constants
# of the same names/values.
_ARMIES_CAPTION_LINE_1 = "                                                              Normal  Modified"
_ARMIES_COLUMN_HEADER = "Province          Leader         Designation           Race   Quality  Quality"


def test_describe_armies_report_led_army_line():
    state = _armies_state()
    state.add_leader(LeaderState(1, 1, "Sir Aldric", HexCoord(0, 0)))
    state.add_army(ArmyState(1, 1, ArmyType.BOWMEN, Quality.AVERAGE, HexCoord(0, 0), commanded_by=1))

    lines = describe_armies_report(state, 1)

    assert lines[2:] == [
        _ARMIES_CAPTION_LINE_1,
        _ARMIES_COLUMN_HEADER,
        "Capital City      Sir Aldric     Bowmen                Human  Average  Veteran",
    ]


def test_describe_armies_report_unled_army_shows_garrison():
    state = _armies_state()
    state.add_army(ArmyState(1, 1, ArmyType.PHALANX, Quality.VETERAN, HexCoord(0, 0)))

    lines = describe_armies_report(state, 1)

    assert lines[2:] == [
        _ARMIES_CAPTION_LINE_1,
        _ARMIES_COLUMN_HEADER,
        "Capital City      Garrison       Phalanx               Human  Veteran    Crack",
    ]


def test_describe_armies_report_names_a_commander_who_died_earlier_this_same_turn():
    state = _armies_state()
    state.add_leader(LeaderState(1, 1, "Sir Aldric", HexCoord(0, 0)))
    state.add_army(ArmyState(1, 1, ArmyType.BOWMEN, Quality.AVERAGE, HexCoord(0, 0), commanded_by=1))
    state.remove_leader(1)  # died in an earlier phase this same turn

    lines = describe_armies_report(state, 1)

    assert lines[2:] == [
        _ARMIES_CAPTION_LINE_1,
        _ARMIES_COLUMN_HEADER,
        "Capital City      Sir Aldric     Bowmen                Human  Average  Veteran",
    ]


def test_describe_armies_report_monstrous_army_uses_its_own_fixed_race():
    state = _armies_state()
    state.add_army(ArmyState(1, 1, ArmyType.DRAGON_WING, Quality.ELITE, HexCoord(0, 0)))

    lines = describe_armies_report(state, 1)

    assert lines[2:] == [
        _ARMIES_CAPTION_LINE_1,
        _ARMIES_COLUMN_HEADER,
        "Capital City      Garrison       Dragons              Dragon    Elite    Elite",
    ]


def test_describe_armies_report_dinosaurs_show_as_saurian_not_the_owning_kingdoms_race():
    # Phase 980: AdvancedAbility.DRUIDIC_DINOSAURS's own "Race: Saurian"
    # -- a Dinosaur army's race resolves to Race.SAURIAN regardless of
    # the owning Kingdom's own race (Human here, to prove it's not
    # merely falling back to kingdom.race -- in real play the owner is
    # always Elven, per the separate recruiting race gate). The real
    # column text is RACE_NAME[SAURIAN]'s own already-sourced "Dinosaur"
    # (CTBOTH.PAS rname), the same short singular form every other
    # MONSTROUS_ARMY_RACE entry already renders (e.g. Dragon_Wing's own
    # "Dragons" designation shows race "Dragon", not "Dragons").
    state = _armies_state()
    state.add_army(ArmyState(1, 1, ArmyType.DINOSAURS, Quality.AVERAGE, HexCoord(0, 0)))

    lines = describe_armies_report(state, 1)

    assert lines[2:] == [
        _ARMIES_CAPTION_LINE_1,
        _ARMIES_COLUMN_HEADER,
        "Capital City      Garrison       Dinosaurs           Dinosaur  Average  Veteran",
    ]


def test_describe_armies_report_excludes_other_kingdoms_armies():
    state = _armies_state()
    state.add_kingdom(KingdomState(2, "Otherland", Race.ELVEN, Alignment.NEUTRAL, HexCoord(1, 1)))
    state.add_army(ArmyState(1, 2, ArmyType.BOWMEN, Quality.AVERAGE, HexCoord(0, 0)))

    lines = describe_armies_report(state, 1)

    assert lines[2:] == ["None at present"]


def test_describe_armies_report_unnamed_province_falls_back_to_coordinates():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_province(ProvinceState(HexCoord(3, 4), None, Race.HUMAN, owner_kingdom_id=1))
    state.add_army(ArmyState(1, 1, ArmyType.BOWMEN, Quality.AVERAGE, HexCoord(3, 4)))

    lines = describe_armies_report(state, 1)

    assert lines[2:] == [
        _ARMIES_CAPTION_LINE_1,
        _ARMIES_COLUMN_HEADER,
        "(3, 4)            Garrison       Bowmen                Human  Average  Average",
    ]


def test_describe_armies_report_sorts_multiple_armies_by_location_then_id():
    state = _armies_state()
    state.add_province(ProvinceState(HexCoord(1, 1), None, Race.HUMAN, owner_kingdom_id=1, name="Second Province"))
    state.add_army(ArmyState(2, 1, ArmyType.AXEMEN, Quality.AVERAGE, HexCoord(1, 1)))
    state.add_army(ArmyState(1, 1, ArmyType.BOWMEN, Quality.AVERAGE, HexCoord(0, 0)))

    lines = describe_armies_report(state, 1)

    assert lines[2:] == [
        _ARMIES_CAPTION_LINE_1,
        _ARMIES_COLUMN_HEADER,
        "Capital City      Garrison       Bowmen                Human  Average  Veteran",
        "Second Province   Garrison       Axemen                Human  Average  Average",
    ]


def test_describe_armies_report_same_province_groups_by_leader_index_not_army_id():
    # Phase 926: REPORTS.PAS Rep_Armies's own middle loop visits leaders
    # by ascending array index (Garrison/noleader always last), armies
    # within a leader's own group in army-index order -- NOT flat
    # army_id order across the whole province. Leader 1 (Sir Aldric)
    # has the higher army_id but the lower leader index, so his army
    # must render first despite army_id=3; the Garrison army (army_id=1,
    # the lowest id of all) must render last.
    state = _armies_state()
    state.add_leader(LeaderState(1, 1, "Sir Aldric", HexCoord(0, 0)))
    state.add_leader(LeaderState(2, 1, "Lady Brenna", HexCoord(0, 0)))
    state.add_army(ArmyState(1, 1, ArmyType.PHALANX, Quality.AVERAGE, HexCoord(0, 0)))
    state.add_army(ArmyState(2, 1, ArmyType.AXEMEN, Quality.AVERAGE, HexCoord(0, 0), commanded_by=2))
    state.add_army(ArmyState(3, 1, ArmyType.BOWMEN, Quality.AVERAGE, HexCoord(0, 0), commanded_by=1))

    lines = describe_armies_report(state, 1)

    assert lines[4:] == [
        "Capital City      Sir Aldric     Bowmen                Human  Average  Veteran",
        "(#0)              Lady Brenna    Axemen                Human  Average  Veteran",
        "                  Garrison       Phalanx               Human  Average  Veteran",
    ]


def test_describe_armies_report_suppresses_province_column_after_the_second_army():
    # Phase 436: REPORTS.PAS Check_None's own pac/none state -- the
    # first army at a province gets the full name, the second gets
    # "(#code)", every later one gets a fully blank 18-char field.
    state = _armies_state()
    state.add_army(ArmyState(1, 1, ArmyType.BOWMEN, Quality.AVERAGE, HexCoord(0, 0)))
    state.add_army(ArmyState(2, 1, ArmyType.AXEMEN, Quality.AVERAGE, HexCoord(0, 0)))
    state.add_army(ArmyState(3, 1, ArmyType.PHALANX, Quality.AVERAGE, HexCoord(0, 0)))

    lines = describe_armies_report(state, 1)

    assert lines[4:] == [
        "Capital City      Garrison       Bowmen                Human  Average  Veteran",
        "(#0)              Garrison       Axemen                Human  Average  Veteran",
        "                  Garrison       Phalanx               Human  Average  Veteran",
    ]


def test_describe_armies_report_skeletal_army_uses_skel_designation():
    # Phase 281, REPORTS.PAS:988-992 (Doit, inside Rep_Armies): a
    # Zomboid-state army renders "Skel <atdesig>", not the ordinary
    # <atname> -- Lt Cavalry is the clearest real case, since its own
    # atdesig ("Lt Cav") diverges from its atname ("Light Cavalry").
    state = _armies_state()
    state.add_army(ArmyState(1, 1, ArmyType.LT_CAVALRY, Quality.AVERAGE, HexCoord(0, 0), is_skeletal=True))

    lines = describe_armies_report(state, 1)

    assert lines[2:] == [
        _ARMIES_CAPTION_LINE_1,
        _ARMIES_COLUMN_HEADER,
        "Capital City      Garrison       Skel Lt Cav           Human  Average  Veteran",
    ]


def test_describe_armies_report_non_skeletal_army_still_uses_atname():
    # Same real branch's else-case: a non-Zomboid army keeps using
    # ARMY_TYPE_NAME ("Light Cavalry"), not ARMY_TYPE_DESIGNATION.
    state = _armies_state()
    state.add_army(ArmyState(1, 1, ArmyType.LT_CAVALRY, Quality.AVERAGE, HexCoord(0, 0)))

    lines = describe_armies_report(state, 1)

    assert lines[2:] == [
        _ARMIES_CAPTION_LINE_1,
        _ARMIES_COLUMN_HEADER,
        "Capital City      Garrison       Light Cavalry         Human  Average  Veteran",
    ]


# -- Phase 642: ARMIES report's real "Mercenary" pass (Known_Merc) --

_ARMIES_MERCENARY_INTRO = "The following unit(s) are independent mercenaries which you may Recruit:"
_ARMIES_MERCENARY_CAPTION_LINE_1 = "                                                              Normal"
_ARMIES_MERCENARY_COLUMN_HEADER = "Province          Leader         Designation           Race   Quality"


def test_describe_armies_report_known_mercenary_in_owned_province():
    state = _armies_state()
    state.add_army(ArmyState(9, None, ArmyType.BOWMEN, Quality.AVERAGE, HexCoord(0, 0)))

    lines = describe_armies_report(state, 1)

    assert lines[2:] == [
        "None at present",
        _ARMIES_MERCENARY_INTRO,
        _ARMIES_MERCENARY_CAPTION_LINE_1,
        _ARMIES_MERCENARY_COLUMN_HEADER,
        "Capital City                     Bowmen                Human  Average",
    ]


def test_describe_armies_report_known_mercenary_via_adjacent_leader():
    state = _armies_state()
    state.add_province(ProvinceState(HexCoord(1, 0), Terrain.PLAINS, Race.HUMAN))  # unowned, adjacent to (0,0)
    state.add_leader(LeaderState(1, 1, "Sir Aldric", HexCoord(0, 0)))  # this kingdom's own leader, radius 1 away
    state.add_army(ArmyState(9, None, ArmyType.BOWMEN, Quality.AVERAGE, HexCoord(1, 0)))

    lines = describe_armies_report(state, 1)

    assert any(line.startswith("(1, 0)") or "Bowmen" in line for line in lines[2:])
    assert _ARMIES_MERCENARY_INTRO in lines


def test_describe_armies_report_known_mercenary_uses_the_real_board_width():
    # Phase 871: same wraparound-distance bug as the map/impulse-3
    # cases -- a mercenary ~1 hex away under the pre-fix hardcoded-18
    # default is genuinely 13 hexes away on GameState's own real
    # default board (30-wide, Super-AK) -- past known_mercenary()'s
    # own radius=1 "adjacent" gate.
    state = _armies_state()
    assert state.board_width == 30
    state.add_leader(LeaderState(1, 1, "Sir Aldric", HexCoord(1, 2)))
    state.add_province(ProvinceState(HexCoord(18, 2), Terrain.PLAINS, Race.HUMAN))
    state.add_army(ArmyState(9, None, ArmyType.BOWMEN, Quality.AVERAGE, HexCoord(18, 2)))

    lines = describe_armies_report(state, 1)

    assert _ARMIES_MERCENARY_INTRO not in lines


def test_describe_armies_report_unknown_mercenary_is_absent():
    state = _armies_state()
    state.add_province(ProvinceState(HexCoord(5, 5), Terrain.PLAINS, Race.HUMAN))  # unowned, far away
    state.add_army(ArmyState(9, None, ArmyType.BOWMEN, Quality.AVERAGE, HexCoord(5, 5)))

    lines = describe_armies_report(state, 1)

    assert lines[2:] == ["None at present"]
    assert _ARMIES_MERCENARY_INTRO not in lines


def test_describe_armies_report_no_mercenary_section_when_none_known():
    state = _armies_state()
    state.add_army(ArmyState(1, 1, ArmyType.BOWMEN, Quality.AVERAGE, HexCoord(0, 0)))

    lines = describe_armies_report(state, 1)

    assert _ARMIES_MERCENARY_INTRO not in lines


def test_describe_armies_report_mercenary_section_appears_even_with_no_owned_armies():
    # The real `none`/`strip` state is per-passtype (Phase 642 mirrors
    # Phase 639's own CHARACTERS-report fix for the identical bug class):
    # an empty Hired pass must not suppress a real Mercenary pass.
    state = _armies_state()
    state.add_army(ArmyState(9, None, ArmyType.BOWMEN, Quality.AVERAGE, HexCoord(0, 0)))

    lines = describe_armies_report(state, 1)

    assert lines[2] == "None at present"  # Hired pass, empty
    assert _ARMIES_MERCENARY_INTRO in lines  # Mercenary pass, real content


def test_describe_armies_report_mercenary_suppresses_province_column_after_the_second():
    state = _armies_state()
    state.add_army(ArmyState(9, None, ArmyType.BOWMEN, Quality.AVERAGE, HexCoord(0, 0)))
    state.add_army(ArmyState(10, None, ArmyType.AXEMEN, Quality.AVERAGE, HexCoord(0, 0)))

    lines = describe_armies_report(state, 1)

    rows = lines[lines.index(_ARMIES_MERCENARY_COLUMN_HEADER) + 1 :]
    assert rows == [
        "Capital City                     Bowmen                Human  Average",
        "(#0)                             Axemen                Human  Average",
    ]


def test_describe_armies_report_mercenary_race_falls_back_to_the_provinces_own_race():
    state = _armies_state()  # viewing kingdom (Testland) is Human
    state.add_province(ProvinceState(HexCoord(2, 2), Terrain.PLAINS, Race.ELVEN, owner_kingdom_id=1))
    state.add_army(ArmyState(9, None, ArmyType.BOWMEN, Quality.AVERAGE, HexCoord(2, 2)))

    lines = describe_armies_report(state, 1)

    mercenary_row = lines[-1]
    assert "Elf" in mercenary_row  # the province's own race, not the viewer's Human
    assert "Human" not in mercenary_row


def test_describe_armies_report_mercenary_leader_column_is_blank_not_garrison():
    state = _armies_state()
    state.add_army(ArmyState(9, None, ArmyType.BOWMEN, Quality.AVERAGE, HexCoord(0, 0)))

    lines = describe_armies_report(state, 1)

    mercenary_row = lines[-1]
    assert "Garrison" not in mercenary_row


# -- Phase 217: describe_letter_reports() -- the "LETTER REPORTS" section --


def _letter_state() -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    return state


def test_describe_letter_reports_no_other_leaders_renders_none():
    state = _letter_state()
    state.add_leader(LeaderState(1, 1, "Aldric", HexCoord(0, 0), is_king=True))

    lines = describe_letter_reports([], state, 1, ScriptedRandom([]))

    assert lines == ["LETTER REPORTS", "There are no letters from anyone at this time."]


def test_describe_letter_reports_other_leader_with_no_results_renders_none():
    state = _letter_state()
    state.add_leader(LeaderState(1, 1, "Aldric", HexCoord(0, 0), is_king=True))
    state.add_leader(LeaderState(32, 1, "Borin", HexCoord(0, 0)))

    lines = describe_letter_reports([], state, 1, ScriptedRandom([]))

    assert lines == ["LETTER REPORTS", "There are no letters from anyone at this time."]


def test_describe_letter_reports_renders_a_letter_from_a_hero_to_the_king():
    state = _letter_state()
    state.add_leader(LeaderState(1, 1, "Aldric", HexCoord(0, 0), is_king=True))
    state.add_leader(LeaderState(32, 1, "Borin", HexCoord(0, 0)))
    state.add_leader(LeaderState(40, 1, "Elena", HexCoord(0, 0)))
    result = HireExecutionResult(HireRequest(hero_id=40, gold_offer=1), hired=True)
    results = [
        PhaseDispatchResult(leader_id=32, segment_index=0, phase_label="P0", action=ActionCode.HIRE, result=result, error=None)
    ]

    lines = describe_letter_reports(results, state, 1, ScriptedRandom([0.1] * 10, choice_indices=[0]))

    assert lines == [
        "LETTER REPORTS",
        "O King of Kings, thy heroes have travelled around the globe in "
        "search of adventure and conquest.  I have faithfully kept their "
        "correspondence, and now I present it to thee:",
        "From: Borin",
        "To: Aldric",
        "Honored Sovereign,",
        # Phase 851: Hire's own ^K marker names Borin's real King (Aldric),
        # not Borin himself -- the hireling's employment goes to Aldric's
        # Kingdom, per _dispatch_hire()'s own `hero.kingdom_id = kingdom_id`.
        "Borin spoke to Elena and convinced Elena to pledge Elena's allegiance to Aldric.",
        "Thy humble servant,   Borin",
    ]


def test_describe_letter_reports_excludes_the_kings_own_results():
    state = _letter_state()
    state.add_leader(LeaderState(1, 1, "Aldric", HexCoord(0, 0), is_king=True))
    state.add_leader(LeaderState(32, 1, "Borin", HexCoord(0, 0)))
    king_result = HireExecutionResult(HireRequest(hero_id=32, gold_offer=2), hired=True)
    results = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.HIRE, result=king_result, error=None)
    ]

    lines = describe_letter_reports(results, state, 1, ScriptedRandom([]))

    assert lines == ["LETTER REPORTS", "There are no letters from anyone at this time."]


# -- Phase 248: board_width threading (rumor narration in a real letter) --


def _rumor_letter_setup() -> tuple[GameState, list[PhaseDispatchResult]]:
    state = _letter_state()
    state.add_leader(LeaderState(1, 1, "Aldric", HexCoord(0, 0), is_king=True))
    state.add_leader(LeaderState(32, 1, "Borin", HexCoord(0, 0)))
    feature = Feature(feature_id=5, coord=HexCoord(3, 4), kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE)
    state.add_feature(feature)
    rumor = Rumor(
        rumor_id=state.new_rumor_id(),
        kingdom_id=1,
        leader_id=32,
        source_action=ActionCode.EXPLORE,
        content=RumorContent.FEATURE_AND_MONSTER,
        feature_id=5,
        is_true=True,
        described_coord=HexCoord(3, 4),
        described_monster=Monster.GARGOYLE,
    )
    state.add_rumor(rumor)
    explore_result = ExploreResult(new_percent=50, delta_applied=50, fully_explored=False)
    results = [
        PhaseDispatchResult(
            leader_id=32, segment_index=0, phase_label="P0", action=ActionCode.EXPLORE, result=explore_result, error=None
        )
    ]
    return state, results


def test_describe_letter_reports_omits_rumor_without_board_width():
    # Phase 848: Borin's own turn is no longer silently empty -- the
    # newly-wired EXPLORE progress sentence renders regardless of
    # board_width, so a real letter now appears; only the rumor text
    # itself stays omitted without a real board_width.
    state, results = _rumor_letter_setup()

    lines = describe_letter_reports(results, state, 1, ScriptedRandom([0.1] * 10, choice_indices=[0]))

    assert any(line == "From: Borin" for line in lines)
    assert not any("heard" in line for line in lines)


def test_describe_letter_reports_renders_rumor_when_board_width_given():
    state, results = _rumor_letter_setup()

    lines = describe_letter_reports(
        results, state, 1, ScriptedRandom([0.1] * 10, choice_indices=[0, 0]), board_width=10
    )

    assert lines[0] == "LETTER REPORTS"
    assert any(line == "From: Borin" for line in lines)
    assert any("heard" in line for line in lines)


def test_describe_letter_reports_multiple_heroes_each_get_their_own_letter():
    state = _letter_state()
    state.add_leader(LeaderState(1, 1, "Aldric", HexCoord(0, 0), is_king=True))
    state.add_leader(LeaderState(32, 1, "Borin", HexCoord(0, 0)))
    state.add_leader(LeaderState(50, 1, "Cyra", HexCoord(0, 0)))
    state.add_leader(LeaderState(40, 1, "Elena", HexCoord(0, 0)))
    state.add_leader(LeaderState(60, 1, "Finn", HexCoord(0, 0)))
    borin_result = HireExecutionResult(HireRequest(hero_id=40, gold_offer=1), hired=True)
    cyra_result = HireExecutionResult(HireRequest(hero_id=60, gold_offer=1), hired=True)
    results = [
        PhaseDispatchResult(
            leader_id=32, segment_index=0, phase_label="P0", action=ActionCode.HIRE, result=borin_result, error=None
        ),
        PhaseDispatchResult(
            leader_id=50, segment_index=0, phase_label="P0", action=ActionCode.HIRE, result=cyra_result, error=None
        ),
    ]

    lines = describe_letter_reports(results, state, 1, ScriptedRandom([0.1] * 20, choice_indices=[0, 0]))

    assert lines == [
        "LETTER REPORTS",
        "O King of Kings, thy heroes have travelled around the globe in "
        "search of adventure and conquest.  I have faithfully kept their "
        "correspondence, and now I present it to thee:",
        "From: Borin",
        "To: Aldric",
        "Honored Sovereign,",
        # Phase 851: both heroes' own Hire orders name their shared real
        # King (Aldric), not themselves -- see the sibling test above.
        "Borin spoke to Elena and convinced Elena to pledge Elena's allegiance to Aldric.",
        "Thy humble servant,   Borin",
        "From: Cyra",
        "To: Aldric",
        "Honored Sovereign,",
        "Cyra spoke to Finn and convinced Finn to pledge Finn's allegiance to Aldric.",
        "Thy humble servant,   Cyra",
    ]


def test_describe_letter_reports_excludes_other_kingdoms_leaders():
    state = _letter_state()
    state.add_leader(LeaderState(1, 1, "Aldric", HexCoord(0, 0), is_king=True))
    state.add_kingdom(KingdomState(2, "Otherland", Race.ELVEN, Alignment.NEUTRAL, HexCoord(1, 1)))
    state.add_leader(LeaderState(9, 2, "Kwoth", HexCoord(1, 1)))
    other_kingdom_result = FireExecutionResult(FireRequest(hero_id=9), fired=True)
    results = [
        PhaseDispatchResult(
            leader_id=9, segment_index=0, phase_label="P0", action=ActionCode.FIRE, result=other_kingdom_result, error=None
        )
    ]

    lines = describe_letter_reports(results, state, 1, ScriptedRandom([]))

    assert lines == ["LETTER REPORTS", "There are no letters from anyone at this time."]


def test_describe_letter_reports_no_king_recorded_still_lists_other_leaders_letters():
    state = _letter_state()
    state.add_leader(LeaderState(32, 1, "Borin", HexCoord(0, 0)))
    state.add_leader(LeaderState(40, 1, "Elena", HexCoord(0, 0)))
    result = HireExecutionResult(HireRequest(hero_id=40, gold_offer=1), hired=True)
    results = [
        PhaseDispatchResult(leader_id=32, segment_index=0, phase_label="P0", action=ActionCode.HIRE, result=result, error=None)
    ]

    lines = describe_letter_reports(results, state, 1, ScriptedRandom([0.1] * 10, choice_indices=[0]))

    assert lines == [
        "LETTER REPORTS",
        "O King of Kings, thy heroes have travelled around the globe in "
        "search of adventure and conquest.  I have faithfully kept their "
        "correspondence, and now I present it to thee:",
        "From: Borin",
        "To:",
        "Honored Sovereign,",
        "Borin spoke to Elena and convinced Elena to pledge Elena's allegiance to Borin.",
        "Thy humble servant,   Borin",
    ]


# -- Phase 218: describe_diplomacy_report() -- the "DIPLOMACY" section --


_DIPLOMACY_ALLIED_INTRO = "My lord, the following Kings have wisely allied with thy ever-victorious majesty:"
_DIPLOMACY_WAR_INTRO = "My lord, the following Kings are foolishly at war with thy ever-victorious majesty:"
_DIPLOMACY_NEUTRAL_INTRO = "My lord, the following Kings are cautiously neutral with thy ever-victorious majesty:"


def test_describe_diplomacy_report_no_other_kingdoms_renders_all_none():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))

    lines = describe_diplomacy_report(state, 1)

    assert lines == [
        "DIPLOMACY",
        _DIPLOMACY_ALLIED_INTRO,
        "None at present",
        _DIPLOMACY_WAR_INTRO,
        "None at present",
        _DIPLOMACY_NEUTRAL_INTRO,
        "None at present",
    ]


def test_describe_diplomacy_report_unallied_kingdom_is_neutral():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    # Phase 640: a shared alignment triggers its own real enrichment
    # sentence (tested separately below) -- GOOD here keeps this test
    # about the allied/neutral classification alone.
    state.add_kingdom(KingdomState(2, "Otherland", Race.ELVEN, Alignment.GOOD, HexCoord(1, 1)))
    state.add_leader(LeaderState(9, 2, "Kwoth", HexCoord(1, 1), is_king=True))

    lines = describe_diplomacy_report(state, 1)

    assert lines == [
        "DIPLOMACY",
        _DIPLOMACY_ALLIED_INTRO,
        "None at present",
        _DIPLOMACY_WAR_INTRO,
        "None at present",
        _DIPLOMACY_NEUTRAL_INTRO,
        "Kwoth (#2)",
    ]


def test_describe_diplomacy_report_allied_kingdom_is_listed_as_allied():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_kingdom(KingdomState(2, "Otherland", Race.ELVEN, Alignment.GOOD, HexCoord(1, 1)))
    state.add_leader(LeaderState(9, 2, "Kwoth", HexCoord(1, 1), is_king=True))
    state.allied_kingdoms.add(frozenset({1, 2}))

    lines = describe_diplomacy_report(state, 1)

    assert lines == [
        "DIPLOMACY",
        _DIPLOMACY_ALLIED_INTRO,
        "Kwoth (#2)",
        _DIPLOMACY_WAR_INTRO,
        "None at present",
        _DIPLOMACY_NEUTRAL_INTRO,
        "None at present",
    ]


def test_describe_diplomacy_report_war_renders_none_at_present_with_no_enemy_relation():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_kingdom(KingdomState(2, "Otherland", Race.ELVEN, Alignment.NEUTRAL, HexCoord(1, 1)))
    state.add_leader(LeaderState(9, 2, "Kwoth", HexCoord(1, 1), is_king=True))

    lines = describe_diplomacy_report(state, 1)

    war_index = lines.index(_DIPLOMACY_WAR_INTRO)
    assert lines[war_index + 1] == "None at present"


def test_describe_diplomacy_report_enemy_relation_is_listed_as_at_war():
    # Phase 1026: turn/diplomacy.py's own real Enemy relation (via a
    # Break Treat order) now renders here -- previously always empty,
    # since no war-declaration mechanism existed in this project at all.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_kingdom(KingdomState(2, "Otherland", Race.ELVEN, Alignment.GOOD, HexCoord(1, 1)))
    state.add_leader(LeaderState(9, 2, "Kwoth", HexCoord(1, 1), is_king=True))
    state.diplomatic_relations[frozenset({1, 2})] = DiplomaticRelation.ENEMY

    lines = describe_diplomacy_report(state, 1)

    assert lines == [
        "DIPLOMACY",
        _DIPLOMACY_ALLIED_INTRO,
        "None at present",
        _DIPLOMACY_WAR_INTRO,
        "Kwoth (#2)",
        _DIPLOMACY_NEUTRAL_INTRO,
        "None at present",
    ]


def test_describe_diplomacy_report_no_king_recorded_falls_back_to_kingdom_name():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_kingdom(KingdomState(2, "Otherland", Race.ELVEN, Alignment.GOOD, HexCoord(1, 1)))

    lines = describe_diplomacy_report(state, 1)

    assert lines[-1] == "Otherland (#2)"


def test_describe_diplomacy_report_lists_multiple_kingdoms_sorted_by_id():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_kingdom(KingdomState(2, "Bland", Race.ELVEN, Alignment.GOOD, HexCoord(1, 1)))
    state.add_kingdom(KingdomState(3, "Cland", Race.DWARVEN, Alignment.GOOD, HexCoord(2, 2)))
    state.add_leader(LeaderState(20, 2, "Bertha", HexCoord(1, 1), is_king=True))
    state.add_leader(LeaderState(30, 3, "Cyrus", HexCoord(2, 2), is_king=True))

    lines = describe_diplomacy_report(state, 1)

    neutral_index = lines.index(_DIPLOMACY_NEUTRAL_INTRO)
    assert lines[neutral_index + 1 :] == ["Bertha (#2)", "Cyrus (#3)"]


# -- Phase 640: DIPLOMACY's real Write_List/Desc_Align enrichment --
# tax-base/treasury figures (Emperor/Treasurer, known-for-a-full-turn,
# bordering) and the alignment sentence (met Heavenly/Undead, or a
# shared alignment with no "met" prerequisite at all).


def _bordering_diplomacy_state() -> GameState:
    # Kingdom 1 (viewer) at (0,0), Kingdom 2 at (1,0) -- real, adjacent
    # provinces, since bordering_kingdoms() scans actual province
    # ownership, not just home_province.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.GOOD, HexCoord(0, 0)))
    state.add_kingdom(KingdomState(2, "Otherland", Race.ELVEN, Alignment.EVIL, HexCoord(1, 0)))
    p1 = ProvinceState(HexCoord(0, 0), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1)
    p2 = ProvinceState(HexCoord(1, 0), Terrain.PLAINS, Race.ELVEN, owner_kingdom_id=2)
    p2.tax = 45
    state.add_province(p1)
    state.add_province(p2)
    state.add_leader(LeaderState(1, 1, "Aldric", HexCoord(0, 0), is_king=True))
    state.add_leader(LeaderState(9, 2, "Bertha", HexCoord(1, 0), is_king=True))
    state.kingdoms_met.add(frozenset({1, 2}))
    state.kingdoms_met_since[frozenset({1, 2})] = 0  # turn_number defaults to 1 -> "known for a full turn"
    return state


def test_describe_diplomacy_report_shows_tax_base_for_a_bordering_known_kingdom_when_emperor():
    state = _bordering_diplomacy_state()
    state.emperor_kingdom_id = 1
    expected_tax = compute_tax_base(state, 2)
    assert expected_tax > 0

    lines = describe_diplomacy_report(state, 1)

    entry = next(line for line in lines if line.startswith("Bertha"))
    assert f"{expected_tax}g taxbase" in entry
    assert "in treasury" not in entry  # not Treasurer, no treasury figure


def test_describe_diplomacy_report_no_tax_base_without_emperor():
    state = _bordering_diplomacy_state()
    # state.emperor_kingdom_id left None -- nobody elected Emperor yet

    lines = describe_diplomacy_report(state, 1)

    entry = next(line for line in lines if line.startswith("Bertha"))
    assert "taxbase" not in entry


def test_describe_diplomacy_report_no_tax_base_when_not_known_for_a_full_turn():
    state = _bordering_diplomacy_state()
    state.emperor_kingdom_id = 1
    state.kingdoms_met_since[frozenset({1, 2})] = 1  # first met THIS turn (turn_number=1) -- not yet a full turn

    lines = describe_diplomacy_report(state, 1)

    entry = next(line for line in lines if line.startswith("Bertha"))
    assert "taxbase" not in entry


def test_describe_diplomacy_report_shows_treasury_when_treasurer_and_both_figures_can_appear_together():
    state = _bordering_diplomacy_state()
    state.emperor_kingdom_id = 1
    state.kingdoms[1].treasury = 999  # Aldric wins Treasurer by having the higher treasury
    state.kingdoms[2].treasury = 5
    other_treasury = state.kingdoms[2].treasury

    lines = describe_diplomacy_report(state, 1)

    entry = next(line for line in lines if line.startswith("Bertha"))
    assert f"{other_treasury}g in treasury" in entry
    assert "taxbase" in entry  # both figures together


def test_describe_diplomacy_report_treasurer_held_by_a_hero_not_the_king_shows_no_treasury():
    # REPORTS.PAS's own `prevchar[Treasurer] = kng` only matches when the
    # King HIMSELF holds the office -- a Hero of the SAME kingdom holding
    # it (a real, rulebook-sanctioned possibility) must not grant the
    # King this intelligence. `treasurer_merit_points()` is purely
    # kingdom-based (same value for the King and any Hero of that
    # kingdom), so Aldric and this Hero tie on points -- the Phase 475
    # stickiness tie-break, forced here via `state.office_holders`,
    # deterministically picks the Hero over the King.
    state = _bordering_diplomacy_state()
    state.kingdoms[1].treasury = 999  # Testland's own treasury wins the Treasurer contest outright
    hero = LeaderState(2, 1, "Wandering Hero", HexCoord(0, 0))
    state.add_leader(hero)
    state.office_holders[Office.TREASURER] = hero.leader_id

    lines = describe_diplomacy_report(state, 1)

    entry = next(line for line in lines if line.startswith("Bertha"))
    assert "in treasury" not in entry


def test_describe_diplomacy_report_alignment_sentence_for_a_met_heavenly_kingdom():
    state = _bordering_diplomacy_state()
    state.kingdoms[2].alignment = Alignment.DIVINE

    lines = describe_diplomacy_report(state, 1)

    entry = next(line for line in lines if line.startswith("Bertha"))
    assert entry.endswith("is of Divine alignment.")


def test_describe_diplomacy_report_alignment_sentence_for_a_met_undead_kingdom():
    state = _bordering_diplomacy_state()
    state.kingdoms[2].alignment = Alignment.UNDEAD

    lines = describe_diplomacy_report(state, 1)

    entry = next(line for line in lines if line.startswith("Bertha"))
    assert entry.endswith("is of Undead alignment.")


def test_describe_diplomacy_report_no_alignment_sentence_for_an_unmet_heavenly_kingdom():
    state = _bordering_diplomacy_state()
    state.kingdoms[2].alignment = Alignment.DIVINE
    state.kingdoms_met.discard(frozenset({1, 2}))
    del state.kingdoms_met_since[frozenset({1, 2})]

    lines = describe_diplomacy_report(state, 1)

    entry = next(line for line in lines if line.startswith("Bertha"))
    assert "alignment" not in entry


def test_describe_diplomacy_report_shared_alignment_shows_sentence_with_no_met_prerequisite():
    state = _bordering_diplomacy_state()
    state.kingdoms[2].alignment = Alignment.GOOD  # same as Testland's own -- not Heavenly/Undead
    state.kingdoms_met.discard(frozenset({1, 2}))
    del state.kingdoms_met_since[frozenset({1, 2})]  # never met -- shouldn't matter for this branch

    lines = describe_diplomacy_report(state, 1)

    entry = next(line for line in lines if line.startswith("Bertha"))
    assert entry.endswith("is of Good alignment.")


def test_describe_diplomacy_report_figures_without_alignment_sentence_when_conditions_dont_overlap():
    state = _bordering_diplomacy_state()
    state.emperor_kingdom_id = 1
    # Testland=GOOD, Otherland=EVIL (from _bordering_diplomacy_state) --
    # neither Heavenly/Undead nor shared, so no alignment sentence,
    # even though the tax-base figure still shows.

    lines = describe_diplomacy_report(state, 1)

    entry = next(line for line in lines if line.startswith("Bertha"))
    assert "taxbase" in entry
    assert "alignment" not in entry


# -- Phase 219: describe_finances_report() -- the "FINANCES" section --


_FINANCES_OPENING = (
    "O Great One, I submit for thy examination the following figures "
    "concerning the finances of our great nation:"
)
_FINANCES_DISCOVERIES_INTRO = "Our Kingdom is also benefited by the following Discoveries of the Sages:"


def test_describe_finances_report_shows_treasury():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0), treasury=250))

    lines = describe_finances_report(state, 1)

    assert lines == [
        "FINANCES",
        _FINANCES_OPENING,
        "here is the financial report for Testland's kingdom: ",
        "Gold in treasury: 250",
        "Expected Revenues:   0",
        "Expected Expenses:   0",
        _FINANCES_DISCOVERIES_INTRO,
        "None at present",
        "Testland was left with 250 gold in the treasury.",
    ]


def test_describe_finances_report_zero_treasury():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))

    lines = describe_finances_report(state, 1)

    assert lines[3] == "Gold in treasury:   0"


def test_describe_finances_report_discoveries_none_at_present_when_kingdom_owns_none():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0), treasury=999))

    lines = describe_finances_report(state, 1)

    assert lines[-3:-1] == [_FINANCES_DISCOVERIES_INTRO, "None at present"]
    assert "+Invention Bonus" not in "\n".join(lines)


# -- Phase 268: real Discoveries of the Sages list + Invention Bonus --


def test_describe_finances_report_lists_owned_discoveries():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.kingdoms[1].discoveries = {Discovery.COMPASS}

    lines = describe_finances_report(state, 1)

    assert lines[-3] == _FINANCES_DISCOVERIES_INTRO
    assert lines[-2] == describe_discovery_line(Discovery.COMPASS)
    assert lines[-2] == "  Compass" + " " * 18 + "(+1 skill in Exploring)"


def test_describe_finances_report_discoveries_sorted_by_real_display_value():
    # PONY_EXPRESS (discval 20) must print before COMPASS (discval 2).
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.kingdoms[1].discoveries = {Discovery.COMPASS, Discovery.PONY_EXPRESS}

    lines = describe_finances_report(state, 1)

    assert lines[-3:-1] == [
        describe_discovery_line(Discovery.PONY_EXPRESS),
        describe_discovery_line(Discovery.COMPASS),
    ]


# -- Phase 643: Scientific Treaty exchange attribution (kexch) --


def test_describe_finances_report_shows_received_from_line():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.kingdoms[1].discoveries = {Discovery.COMPASS}
    state.discovery_exchanged_from[(3, 1)] = Discovery.COMPASS

    lines = describe_finances_report(state, 1)

    assert lines[-3:-1] == [
        describe_discovery_line(Discovery.COMPASS),
        "(Received from player(s) #3 by scientific treaty)",
    ]


def test_describe_finances_report_received_from_joins_multiple_givers():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.kingdoms[1].discoveries = {Discovery.COMPASS}
    state.discovery_exchanged_from[(3, 1)] = Discovery.COMPASS
    state.discovery_exchanged_from[(7, 1)] = Discovery.COMPASS

    lines = describe_finances_report(state, 1)

    assert lines[-2] == "(Received from player(s) #3, 7 by scientific treaty)"


def test_describe_finances_report_shows_sent_to_line():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.kingdoms[1].discoveries = {Discovery.COMPASS}
    state.discovery_exchanged_from[(1, 5)] = Discovery.COMPASS

    lines = describe_finances_report(state, 1)

    assert lines[-3:-1] == [
        describe_discovery_line(Discovery.COMPASS),
        "(Sent to player(s) #5 by scientific treaty)",
    ]


def test_describe_finances_report_received_from_and_sent_to_both_appear_in_order():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.kingdoms[1].discoveries = {Discovery.COMPASS}
    state.discovery_exchanged_from[(3, 1)] = Discovery.COMPASS
    state.discovery_exchanged_from[(1, 5)] = Discovery.COMPASS

    lines = describe_finances_report(state, 1)

    assert lines[-4:-1] == [
        describe_discovery_line(Discovery.COMPASS),
        "(Received from player(s) #3 by scientific treaty)",
        "(Sent to player(s) #5 by scientific treaty)",
    ]


def test_describe_finances_report_no_exchange_lines_without_a_recorded_exchange():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.kingdoms[1].discoveries = {Discovery.COMPASS}

    lines = describe_finances_report(state, 1)

    assert lines[-2] == describe_discovery_line(Discovery.COMPASS)
    assert "scientific treaty" not in "\n".join(lines)


def test_describe_finances_report_shows_invention_bonus_when_positive():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.kingdoms[1].discoveries = {Discovery.PEANUT_BUTTER_SANDWICH, Discovery.ASPIRIN_PILL}  # 1% + 2%

    lines = describe_finances_report(state, 1)

    assert "+Invention Bonus: 3%" in lines


def test_describe_finances_report_omits_invention_bonus_line_when_zero():
    # Ability-bonus/anti-spell Discoveries contribute nothing to Inv_Bonus.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.kingdoms[1].discoveries = {Discovery.COMPASS}

    lines = describe_finances_report(state, 1)

    assert not any("+Invention Bonus" in line for line in lines)


def test_describe_finances_report_reads_only_the_given_kingdoms_own_treasury():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0), treasury=10))
    state.add_kingdom(KingdomState(2, "Otherland", Race.ELVEN, Alignment.NEUTRAL, HexCoord(1, 1), treasury=999))

    lines = describe_finances_report(state, 1)

    assert lines[3] == "Gold in treasury:  10"


def test_describe_finances_report_expected_revenues_uses_compute_tax_base():
    # Phase 225: Expected Revenues sums this kingdom's own owned provinces'
    # real tax, not the other kingdom's -- same scope test_describe_finances_
    # report_reads_only_the_given_kingdoms_own_treasury already established
    # for the treasury line.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_kingdom(KingdomState(2, "Otherland", Race.ELVEN, Alignment.NEUTRAL, HexCoord(1, 1)))
    state.add_province(ProvinceState(HexCoord(0, 0), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, tax=4))
    state.add_province(ProvinceState(HexCoord(0, 1), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, tax=6))
    state.add_province(ProvinceState(HexCoord(1, 1), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2, tax=99))

    lines = describe_finances_report(state, 1)

    assert lines[4] == "Expected Revenues:  10"


# -- Phase 277: King of Pain / Prince of Thieves FINANCES bonus notes --


def _skills_with(**levels: int) -> SkillTable:
    raw_values = [0] * (len(Ability) * 2 + 1)
    for name, level in levels.items():
        i = Ability[name].value * 2
        raw_values[i] = level
        raw_values[i + 1] = level
    return SkillTable(raw_values)


def test_describe_finances_report_shows_black_knights_note_for_this_kingdoms_king_of_pain():
    # Phase 369: King of Pain's real formula is plain Tax_Base(King).
    state = GameState()
    state.add_kingdom(KingdomState(1, "Mordoth", Race.HUMAN, Alignment.EVIL, HexCoord(0, 0), treasury=50))
    king = LeaderState(1, 1, "Vaelgor", HexCoord(0, 0), is_king=True)
    state.add_leader(king)
    state.add_province(ProvinceState(HexCoord(0, 0), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, tax=30))

    lines = describe_finances_report(state, 1)

    assert lines[3] == "Gold in treasury:  50"
    assert lines[4] == "(Including +5 Black Knights)"


def test_describe_finances_report_omits_black_knights_note_for_another_kingdoms_king_of_pain():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_kingdom(KingdomState(2, "Mordoth", Race.HUMAN, Alignment.EVIL, HexCoord(1, 1)))
    other_king = LeaderState(2, 2, "Vaelgor", HexCoord(1, 1), is_king=True)
    state.add_province(ProvinceState(HexCoord(1, 1), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2, tax=30))
    state.add_leader(other_king)

    lines = describe_finances_report(state, 1)

    assert not any("Black Knights" in line for line in lines)


def test_describe_finances_report_omits_black_knights_note_when_nobody_holds_king_of_pain():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))

    lines = describe_finances_report(state, 1)

    assert not any("Black Knights" in line for line in lines)


def test_describe_finances_report_shows_thieves_guild_note_for_this_kingdoms_king_holder():
    # Phase 369: Prince of Thieves' real formula is +1 per successful
    # theft result, no TH-skill term.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0), treasury=50))
    king = LeaderState(1, 1, "Aldric", HexCoord(0, 0), is_king=True)
    king.merit_tally.successful_thefts = 5
    state.add_leader(king)

    lines = describe_finances_report(state, 1)

    assert "(Including +10 Thieves Guild)" in lines


def test_describe_finances_report_shows_thieves_guild_note_credited_to_holders_own_king_when_holder_is_a_hero():
    # Rulebook [10.1]: a Hero can win an office too -- Prince of Thieves has
    # no Kingdom of its own, so the bonus is credited to the Hero's own King's
    # Kingdom (the same Kingdom this report is being composed for).
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0), treasury=50))
    state.add_leader(LeaderState(1, 1, "Aldric", HexCoord(0, 0), is_king=True))
    hero = LeaderState(50, 1, "Sneak", HexCoord(0, 0))
    hero.merit_tally.successful_thefts = 20
    state.add_leader(hero)

    lines = describe_finances_report(state, 1)

    assert "(Including +10 Thieves Guild)" in lines


def test_describe_finances_report_omits_thieves_guild_note_for_another_kingdoms_holder():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_kingdom(KingdomState(2, "Otherland", Race.ELVEN, Alignment.NEUTRAL, HexCoord(1, 1)))
    other_king = LeaderState(2, 2, "Borin", HexCoord(1, 1), is_king=True)
    other_king.merit_tally.successful_thefts = 5
    state.add_leader(other_king)

    lines = describe_finances_report(state, 1)

    assert not any("Thieves Guild" in line for line in lines)


def test_describe_finances_report_omits_thieves_guild_note_when_nobody_holds_prince_of_thieves():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))

    lines = describe_finances_report(state, 1)

    assert not any("Thieves Guild" in line for line in lines)


def test_describe_finances_report_shows_both_notes_in_order_when_both_are_earned():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Mordoth", Race.HUMAN, Alignment.EVIL, HexCoord(0, 0), treasury=50))
    king = LeaderState(1, 1, "Vaelgor", HexCoord(0, 0), is_king=True)
    king.merit_tally.successful_thefts = 5
    state.add_leader(king)
    state.add_province(ProvinceState(HexCoord(0, 0), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, tax=30))

    lines = describe_finances_report(state, 1)

    assert lines[3] == "Gold in treasury:  50"
    assert lines[4] == "(Including +5 Black Knights)"
    assert lines[5] == "(Including +10 Thieves Guild)"
    assert lines[6] == "Expected Revenues:  30"


# -- Phase 670: monster-raid/Thunderbird-intervention narration ----------


def _finances_state_with_owned_province() -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_kingdom(KingdomState(2, "Otherland", Race.ELVEN, Alignment.NEUTRAL, HexCoord(5, 5)))
    state.add_province(ProvinceState(HexCoord(0, 0), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, name="Home"))
    state.add_province(ProvinceState(HexCoord(5, 5), Terrain.PLAINS, Race.ELVEN, owner_kingdom_id=2, name="Otherhome"))
    return state


def test_describe_finances_report_renders_a_raid_line_for_this_kingdoms_own_province():
    state = _finances_state_with_owned_province()
    state.turn_raid_events.append(RaidEvent("raid", HexCoord(0, 0), 1, Monster.GARGOYLE, 4))

    lines = describe_finances_report(state, 1, random.Random(0))

    revenues_index = lines.index("Expected Revenues:   0")
    expenses_index = lines.index("Expected Expenses:   0")
    assert revenues_index < expenses_index - 1
    raid_line = lines[revenues_index + 1]
    assert "Home" in raid_line
    assert "Gargoyle" in raid_line
    assert "4" in raid_line


def test_describe_finances_report_renders_a_thunderbird_line_with_no_damage_figure():
    state = _finances_state_with_owned_province()
    state.turn_raid_events.append(RaidEvent("thunderbird", HexCoord(0, 0), 1, Monster.GARGOYLE, 0))

    lines = describe_finances_report(state, 1, random.Random(0))

    revenues_index = lines.index("Expected Revenues:   0")
    thunderbird_line = lines[revenues_index + 1]
    assert "Home" in thunderbird_line
    assert "Gargoyle" in thunderbird_line
    assert "Thunderbird" in thunderbird_line


def test_describe_finances_report_omits_another_kingdoms_raid_event():
    state = _finances_state_with_owned_province()
    state.turn_raid_events.append(RaidEvent("raid", HexCoord(5, 5), 1, Monster.GARGOYLE, 4))

    lines = describe_finances_report(state, 1, random.Random(0))

    assert not any("Gargoyle" in line for line in lines)


def test_describe_finances_report_no_raid_events_leaves_lines_unchanged():
    state = _finances_state_with_owned_province()

    lines = describe_finances_report(state, 1, random.Random(0))

    assert lines[4] == "Expected Revenues:   0"
    assert lines[5] == "Expected Expenses:   0"


# -- Phase 741: render_blackmail_penalty() / its own FINANCES-report wiring --


def test_render_blackmail_penalty():
    rng = ScriptedRandom([0.1] * 10)
    result = render_blackmail_penalty(45, 2, rng)
    assert result == (
        "45 gold was lost from the treasury's tax revenues this turn as a "
        "result of lost prestige, after a blackmail demand from King 2 "
        "went unpaid and the dirt was leaked to the public."
    )


def test_describe_finances_report_renders_a_blackmail_penalty_line_for_this_kingdom():
    state = _finances_state_with_owned_province()
    state.turn_blackmail_penalties.append(UnpaidBlackmailPenalty(kingdom_id=1, blackmailer_kingdom_id=2, amount=45))

    lines = describe_finances_report(state, 1, random.Random(0))

    revenues_index = lines.index("Expected Revenues:   0")
    penalty_line = lines[revenues_index + 1]
    assert "45 gold" in penalty_line
    assert "King 2" in penalty_line


def test_describe_finances_report_omits_another_kingdoms_blackmail_penalty():
    state = _finances_state_with_owned_province()
    state.turn_blackmail_penalties.append(UnpaidBlackmailPenalty(kingdom_id=2, blackmailer_kingdom_id=1, amount=45))

    lines = describe_finances_report(state, 1, random.Random(0))

    assert not any("lost prestige" in line for line in lines)


def test_describe_finances_report_no_blackmail_penalties_leaves_lines_unchanged():
    state = _finances_state_with_owned_province()

    lines = describe_finances_report(state, 1, random.Random(0))

    assert lines[4] == "Expected Revenues:   0"
    assert lines[5] == "Expected Expenses:   0"


# -- Phase 747: Inv_Bonus really credits gold -- FINANCES-section wiring --


def test_describe_finances_report_invention_bonus_line_sits_right_after_expected_revenues():
    # REPORTS.PAS's own exact quoted order (models/discovery.py's own
    # docstring): Expected Revenues -> Inv_Bonus, nothing else in between
    # -- previously rendered after Expected Expenses instead.
    state = _finances_state_with_owned_province()
    state.kingdoms[1].discoveries = {Discovery.PEANUT_BUTTER_SANDWICH}  # +1%

    lines = describe_finances_report(state, 1, random.Random(0))

    revenues_index = lines.index("Expected Revenues:   0")
    assert lines[revenues_index + 1] == "+Invention Bonus: 1%"


def test_describe_finances_report_renders_lrev_line_using_turn_revenue_credited():
    state = _finances_state_with_owned_province()
    state.turn_revenue_credited = {1: 42, 2: 999}

    lines = describe_finances_report(state, 1, random.Random(0))

    assert "this turn, the Kingdom collected 42 gold in revenue." in lines
    # Sits before Expected Expenses, after any raid/blackmail explanatory
    # lines -- here there are none, so it's the line right before it.
    expenses_index = lines.index("Expected Expenses:   0")
    assert lines[expenses_index - 1] == "this turn, the Kingdom collected 42 gold in revenue."


def test_describe_finances_report_lrev_line_reads_only_this_kingdoms_own_credit():
    state = _finances_state_with_owned_province()
    state.turn_revenue_credited = {2: 999}  # no entry for kingdom 1

    lines = describe_finances_report(state, 1, random.Random(0))

    assert not any("collected" in line and "gold in revenue" in line for line in lines)


def test_describe_finances_report_omits_lrev_line_when_apply_turn_revenue_never_ran():
    # No `state.turn_revenue_credited` entry at all (the default empty
    # dict) -- no data isn't a guess, the line simply doesn't render.
    state = _finances_state_with_owned_province()

    lines = describe_finances_report(state, 1, random.Random(0))

    assert not any("gold in revenue" in line for line in lines)


def test_describe_finances_report_lrev_line_sits_after_raid_and_blackmail_lines():
    state = _finances_state_with_owned_province()
    state.turn_raid_events.append(RaidEvent("raid", HexCoord(0, 0), 1, Monster.GARGOYLE, 4))
    state.turn_blackmail_penalties.append(UnpaidBlackmailPenalty(kingdom_id=1, blackmailer_kingdom_id=2, amount=45))
    state.turn_revenue_credited = {1: 42}

    lines = describe_finances_report(state, 1, random.Random(0))

    lrev_index = lines.index("this turn, the Kingdom collected 42 gold in revenue.")
    expenses_index = lines.index("Expected Expenses:   0")
    revenues_index = lines.index("Expected Revenues:   0")
    assert revenues_index < lrev_index < expenses_index


# -- Phase 771: _LFinance/_LLCosts/_LACosts/_LTreas wiring ---------------


def test_describe_finances_report_lfinance_and_ltreas_always_render():
    state = _finances_state_with_owned_province()
    state.kingdoms[1].treasury = 42

    lines = describe_finances_report(state, 1, random.Random(0))

    assert lines[2] == "here is the financial report for Testland's kingdom: "
    assert lines[-1] == "Testland was left with 42 gold in the treasury."


def test_describe_finances_report_lfinance_and_ltreas_use_the_kings_own_name_when_one_is_registered():
    state = _finances_state_with_owned_province()
    state.add_leader(LeaderState(1, 1, "Aldric", HexCoord(0, 0), is_king=True))

    lines = describe_finances_report(state, 1, random.Random(0))

    assert lines[2] == "here is the financial report for Aldric's kingdom: "
    assert lines[-1] == "Aldric was left with 0 gold in the treasury."


def test_describe_finances_report_llcosts_and_lacosts_render_when_maintenance_ran():
    state = _finances_state_with_owned_province()
    state.turn_maintenance_by_kingdom[1] = MaintenanceResult(debited=9)
    state.add_army(ArmyState(1, 1, ArmyType.LEGION, Quality.AVERAGE, HexCoord(0, 0)))  # ACost 2

    lines = describe_finances_report(state, 1, random.Random(0))

    assert "7 gold was expended to finance our leaders." in lines
    assert "2 gold was expended to maintain our armies." in lines


def test_describe_finances_report_llcosts_and_lacosts_sit_after_lrev_and_before_expected_expenses():
    state = _finances_state_with_owned_province()
    state.turn_revenue_credited = {1: 42}
    state.turn_maintenance_by_kingdom[1] = MaintenanceResult(debited=0)

    lines = describe_finances_report(state, 1, random.Random(0))

    lrev_index = lines.index("this turn, the Kingdom collected 42 gold in revenue.")
    llcosts_index = lines.index("0 gold was expended to finance our leaders.")
    lacosts_index = lines.index("0 gold was expended to maintain our armies.")
    expenses_index = lines.index("Expected Expenses:   0")
    assert lrev_index < llcosts_index < lacosts_index < expenses_index


def test_describe_finances_report_llcosts_and_lacosts_absent_when_maintenance_never_ran():
    state = _finances_state_with_owned_province()

    lines = describe_finances_report(state, 1, random.Random(0))

    assert not any("expended to finance our leaders" in line for line in lines)
    assert not any("expended to maintain our armies" in line for line in lines)


def test_describe_finances_report_llcosts_reads_only_this_kingdoms_own_maintenance():
    state = _finances_state_with_owned_province()
    state.turn_maintenance_by_kingdom[2] = MaintenanceResult(debited=999)  # no entry for kingdom 1

    lines = describe_finances_report(state, 1, random.Random(0))

    assert not any("expended to finance our leaders" in line for line in lines)


def test_describe_finances_report_renders_a_desertion_line_when_maintenance_reports_one():
    # Phase 791: describe_desertions() (Phase 599, dormant since built)
    # is wired here for the first time -- a Hero's desertion is a real
    # narrative consequence of this same kingdom's own MaintenanceResult.
    state = _finances_state_with_owned_province()
    state.add_leader(LeaderState(1, 1, "Borin", HexCoord(0, 0), is_king=True))
    state.add_leader(LeaderState(2, 1, "Aldric", HexCoord(0, 0)))
    state.turn_maintenance_by_kingdom[1] = MaintenanceResult(debited=0, deserted_leader_ids=[2])

    lines = describe_finances_report(state, 1, random.Random(0))

    assert any("Aldric" in line and "Borin" in line for line in lines[5:])


def test_describe_finances_report_omits_desertion_lines_when_none_occurred():
    state = _finances_state_with_owned_province()
    state.add_leader(LeaderState(1, 1, "Borin", HexCoord(0, 0), is_king=True))
    state.turn_maintenance_by_kingdom[1] = MaintenanceResult(debited=0)

    lines = describe_finances_report(state, 1, random.Random(0))

    assert not any("quit the service" in line for line in lines)


def test_describe_finances_report_desertion_line_sits_after_army_costs_and_before_expected_expenses():
    state = _finances_state_with_owned_province()
    state.add_leader(LeaderState(1, 1, "Borin", HexCoord(0, 0), is_king=True))
    state.add_leader(LeaderState(2, 1, "Aldric", HexCoord(0, 0)))
    state.turn_maintenance_by_kingdom[1] = MaintenanceResult(debited=0, deserted_leader_ids=[2])

    lines = describe_finances_report(state, 1, random.Random(0))

    lacosts_index = lines.index("0 gold was expended to maintain our armies.")
    desertion_index = next(i for i, line in enumerate(lines) if "Aldric" in line)
    expenses_index = next(i for i, line in enumerate(lines) if line.startswith("Expected Expenses:"))
    assert lacosts_index < desertion_index < expenses_index


def test_describe_finances_report_desertion_reads_only_this_kingdoms_own_maintenance():
    state = _finances_state_with_owned_province()
    state.add_leader(LeaderState(1, 1, "Borin", HexCoord(0, 0), is_king=True))
    state.add_leader(LeaderState(2, 2, "Sneak", HexCoord(5, 5)))
    state.turn_maintenance_by_kingdom[2] = MaintenanceResult(debited=0, deserted_leader_ids=[2])

    lines = describe_finances_report(state, 1, random.Random(0))

    assert not any("quit the service" in line for line in lines)


# -- Phase 220: describe_provinces_report() -- the "PROVINCES" section --


_PROVINCES_OPENING = (
    "O superfluous one, I have kept well a list of all provinces which have had "
    "the wisdom to submit to thy yoke.  Here, then, are the lands of thy Empire:"
)

# Phase 288: the real REPORTS.PAS column caption/header, printed once
# (not per tier) before the fixed-width rows.
_PROVINCES_COLUMN_CAPTION = "                                                    Recruiting Types:"
_PROVINCES_COLUMN_HEADER = "Province            Tax   Race   Terrain  Expl%     Type 1     Type 2"


def _province_row(name: str, race: str, terrain: str, explored: int, *, tax: int | None = None, type1: str = "", type2: str = "") -> str:
    """Builds the exact real fixed-width row -- see describe_provinces_report()'s own Phase 288 addendum."""

    tax_field = f"{tax:>3}" if tax is not None else "   "
    return f"{name:<20}{tax_field}{race:>8}{terrain:>9}{explored:>6}%{type1:>11}{type2:>11}"


def test_describe_provinces_report_lists_owned_province():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_province(
        ProvinceState(HexCoord(0, 0), Terrain.FOREST, Race.HUMAN, owner_kingdom_id=1, name="Capital City", explored_percent=75)
    )

    lines = describe_provinces_report(state, 1)

    assert lines == [
        "PROVINCES",
        _PROVINCES_OPENING,
        _PROVINCES_COLUMN_CAPTION,
        _PROVINCES_COLUMN_HEADER,
        _province_row("Capital City", "Human", "Forest", 75),
    ]


def test_describe_provinces_report_none_at_present_when_no_provinces_owned():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))

    lines = describe_provinces_report(state, 1)

    assert lines == ["PROVINCES", _PROVINCES_OPENING, "None at present"]


def test_describe_provinces_report_ignores_other_kingdoms_provinces():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_kingdom(KingdomState(2, "Otherland", Race.ELVEN, Alignment.NEUTRAL, HexCoord(5, 5)))
    state.add_province(ProvinceState(HexCoord(5, 5), Terrain.PLAINS, Race.ELVEN, owner_kingdom_id=2, name="Elftown"))

    lines = describe_provinces_report(state, 1)

    assert lines == ["PROVINCES", _PROVINCES_OPENING, "None at present"]


def test_describe_provinces_report_falls_back_to_coordinate_when_unnamed():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_province(ProvinceState(HexCoord(2, 3), Terrain.DESERT, Race.HUMAN, owner_kingdom_id=1))

    lines = describe_provinces_report(state, 1)

    assert lines[-1] == _province_row("(2, 3)", "Human", "Desert", 0)


def test_describe_provinces_report_sorts_by_coordinate_within_the_same_tax_tier():
    # Both at tax=None (tier 0) and neither is the kingdom's own home
    # province -- ties break by ascending coordinate, same as before
    # Phase 288 demoted coordinate from the primary sort key to the
    # tie-breaker.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(9, 9)))
    state.add_province(ProvinceState(HexCoord(3, 1), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, name="South"))
    state.add_province(ProvinceState(HexCoord(1, 1), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, name="North"))

    lines = describe_provinces_report(state, 1)

    assert lines[4:] == [
        _province_row("North", "Human", "Plain", 0),
        _province_row("South", "Human", "Plain", 0),
    ]


def test_describe_provinces_report_uses_effective_terrain_not_illusory():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    province = ProvinceState(HexCoord(0, 0), Terrain.SEA, Race.HUMAN, owner_kingdom_id=1, name="Drowned Fen")
    province.terrain_override = Terrain.PLAINS
    province.illusory_terrain = Terrain.MTNS
    state.add_province(province)

    lines = describe_provinces_report(state, 1)

    assert lines[-1] == _province_row("Drowned Fen", "Human", "Plain", 0)


# -- Phase 981: describe_home_province_neighbors() --


def _neighbor_coord(home: HexCoord, direction: Direction, state: GameState) -> HexCoord:
    coord = neighbor_in_direction_wrapped(home, direction, state.board_width, state.board_height)
    assert coord is not None
    return coord


def test_describe_home_province_neighbors_intro_names_the_home_province():
    state = GameState()
    home = HexCoord(5, 5)
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, home))
    state.add_province(ProvinceState(home, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, name="Capital City"))

    lines = describe_home_province_neighbors(state, 1)

    assert any("The province of Capital City belongs to your Majesty." in line for line in lines)


def test_describe_home_province_neighbors_names_a_claimed_humanoid_neighbor_with_full_army_names():
    state = GameState()
    home = HexCoord(5, 5)
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, home))
    state.add_province(ProvinceState(home, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, name="Capital City"))
    state.add_kingdom(KingdomState(2, "Elfland", Race.ELVEN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_leader(LeaderState(1, kingdom_id=2, name="Thranduil", location=HexCoord(0, 0), is_king=True, race=Race.ELVEN))
    neighbor = _neighbor_coord(home, Direction.E, state)
    state.add_province(
        ProvinceState(
            neighbor,
            Terrain.FOREST,
            Race.ELVEN,
            owner_kingdom_id=2,
            name="Elftown",
            recruit_type_1=ArmyType.BOWMEN,
            recruit_type_2=ArmyType.HVY_CAVALRY,
        )
    )

    paragraph = " ".join(describe_home_province_neighbors(state, 1))

    assert "Elftown" in paragraph
    assert "It is ruled by Thranduil." in paragraph
    assert "Their Elven warriors fight as Bowmen and Heavy Cavalry." in paragraph


def test_describe_home_province_neighbors_unclaimed_humanoid_neighbor_still_gets_a_warriors_sentence():
    state = GameState()
    home = HexCoord(5, 5)
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, home))
    state.add_province(ProvinceState(home, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, name="Capital City"))
    neighbor = _neighbor_coord(home, Direction.W, state)
    state.add_province(
        ProvinceState(neighbor, Terrain.JUNGLE, Race.ORCISH, owner_kingdom_id=None, name="Macondo", recruit_type_1=ArmyType.PHALANX)
    )

    paragraph = " ".join(describe_home_province_neighbors(state, 1))

    assert "where no one rules" in paragraph
    assert "Their Orcish warriors fight as Phalanx." in paragraph


def test_describe_home_province_neighbors_unclaimed_monster_neighbor_gets_a_muster_sentence():
    state = GameState()
    home = HexCoord(5, 5)
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, home))
    state.add_province(ProvinceState(home, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, name="Capital City"))
    neighbor = _neighbor_coord(home, Direction.NE, state)
    state.add_province(ProvinceState(neighbor, Terrain.MTNS, Race.EAGLES, owner_kingdom_id=None, name="Shasta"))

    paragraph = " ".join(describe_home_province_neighbors(state, 1))

    assert "no one rules there" in paragraph
    assert "If need be, they can muster an army of Eagles to defend their province." in paragraph


def test_describe_home_province_neighbors_omits_a_no_race_neighbor():
    state = GameState()
    home = HexCoord(5, 5)
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, home))
    state.add_province(ProvinceState(home, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, name="Capital City"))
    neighbor = _neighbor_coord(home, Direction.NE, state)
    state.add_province(ProvinceState(neighbor, Terrain.SEA, Race.NO_RACE, owner_kingdom_id=None))

    paragraph = " ".join(describe_home_province_neighbors(state, 1))

    assert "no races" not in paragraph


def test_describe_home_province_neighbors_top_edge_uses_the_icy_expanse_line_and_drops_the_northeast_sentence():
    state = GameState()
    home = HexCoord(5, 0)
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, home))
    state.add_province(ProvinceState(home, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, name="Birchwood"))

    lines = describe_home_province_neighbors(state, 1)
    paragraph = " ".join(lines)

    assert "To the north lay an icy expanse which extends as far as the eye can see." in paragraph
    assert "northeast" not in paragraph


def test_describe_home_province_neighbors_empty_when_home_province_missing():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(5, 5)))
    # No ProvinceState ever added at (5, 5).

    assert describe_home_province_neighbors(state, 1) == []


# -- Phase 981: compose_letter_report()'s own include_home_province_narrative flag --


def test_compose_letter_report_omits_home_province_narrative_by_default():
    state = GameState()
    home = HexCoord(5, 5)
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, home))
    state.add_province(ProvinceState(home, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, name="Capital City"))

    lines = compose_letter_report([], state, 1, random.Random(1))

    assert not any("belongs to your Majesty" in line for line in lines)


def test_compose_letter_report_includes_home_province_narrative_when_requested():
    state = GameState()
    home = HexCoord(5, 5)
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, home))
    state.add_province(ProvinceState(home, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, name="Capital City"))

    lines = compose_letter_report([], state, 1, random.Random(1), include_home_province_narrative=True)

    assert any("The province of Capital City belongs to your Majesty." in line for line in lines)


# -- Phase 278: Tax + Recruiting Types columns --


def test_describe_provinces_report_shows_tax_when_known():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(9, 9)))
    state.add_province(
        ProvinceState(HexCoord(0, 0), Terrain.JUNGLE, Race.ORCISH, owner_kingdom_id=1, name="Macondo", explored_percent=16, tax=4)
    )

    lines = describe_provinces_report(state, 1)

    assert lines[-1] == _province_row("Macondo", "Orc", "Jungle", 16, tax=4)


def test_describe_provinces_report_omits_tax_when_unknown():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_province(ProvinceState(HexCoord(0, 0), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, name="Unbridged"))

    lines = describe_provinces_report(state, 1)

    assert lines[-1] == _province_row("Unbridged", "Human", "Plain", 0)


def test_describe_provinces_report_tax_reflects_scar_terrain_reduction():
    # Tax renders via province_tax_yield(), not the raw `tax` field --
    # confirms the FINANCES-side scar/Bless/Earthquake modifiers apply
    # here too, not just in compute_tax_base().
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(9, 9)))
    province = ProvinceState(HexCoord(0, 0), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, name="Scarred", tax=10)
    province.scar_terrain_gold_reduction = 4
    state.add_province(province)

    lines = describe_provinces_report(state, 1)

    assert lines[-1] == _province_row("Scarred", "Human", "Plain", 0, tax=6)


def test_describe_provinces_report_shows_both_recruit_types():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    province = ProvinceState(HexCoord(0, 0), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, name="Orielle")
    province.recruit_type_1 = ArmyType.LEGION
    province.recruit_type_2 = ArmyType.CHARIOTS
    state.add_province(province)

    lines = describe_provinces_report(state, 1)

    assert lines[-1] == _province_row("Orielle", "Human", "Plain", 0, type1="Legion", type2="Chariots")


def test_describe_provinces_report_shows_single_recruit_type_when_second_is_none():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(9, 9)))
    province = ProvinceState(HexCoord(0, 0), Terrain.JUNGLE, Race.ORCISH, owner_kingdom_id=1, name="Macondo")
    province.recruit_type_1 = ArmyType.PHALANX
    state.add_province(province)

    lines = describe_provinces_report(state, 1)

    assert lines[-1] == _province_row("Macondo", "Orc", "Jungle", 0, type1="Phalanx")


def test_describe_provinces_report_omits_recruits_when_unknown():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_province(ProvinceState(HexCoord(0, 0), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, name="Unbridged"))

    lines = describe_provinces_report(state, 1)

    assert lines[-1] == _province_row("Unbridged", "Human", "Plain", 0)


def test_describe_provinces_report_shows_tax_and_recruits_together_in_order():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(9, 9)))
    province = ProvinceState(HexCoord(0, 0), Terrain.JUNGLE, Race.ORCISH, owner_kingdom_id=1, name="Macondo", explored_percent=16, tax=4)
    province.recruit_type_1 = ArmyType.PHALANX
    state.add_province(province)

    lines = describe_provinces_report(state, 1)

    assert lines[-1] == _province_row("Macondo", "Orc", "Jungle", 16, tax=4, type1="Phalanx")


def test_describe_provinces_report_shows_island_parenthetical():
    # Phase 282/283, pt2 -- project-original, see describe_provinces_
    # report()'s own docstring. Rendered as "(Sea)", not "(Island)" --
    # corrected in Phase 283 against the user's own real-report example
    # ("Jungle (Sea)"): Type 1 is the land terrain, Type 2 is literally
    # "Sea".
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    province = ProvinceState(HexCoord(0, 0), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, name="Reef Isle")
    province.is_island = True
    state.add_province(province)

    lines = describe_provinces_report(state, 1)

    assert lines[-1] == _province_row("Reef Isle", "Human", "Plain (Sea)", 0)


def test_describe_provinces_report_omits_island_parenthetical_when_not_an_island():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_province(ProvinceState(HexCoord(0, 0), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, name="Mainland"))

    lines = describe_provinces_report(state, 1)

    assert lines[-1] == _province_row("Mainland", "Human", "Plain", 0)


# -- Phase 288: fixed-width columns + tax-tier grouping --


def test_describe_provinces_report_column_header_and_caption():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_province(ProvinceState(HexCoord(0, 0), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, name="Onlytown"))

    lines = describe_provinces_report(state, 1)

    assert lines[2] == _PROVINCES_COLUMN_CAPTION
    assert lines[3] == _PROVINCES_COLUMN_HEADER


def test_describe_provinces_report_sorts_by_descending_tax_tier_before_coordinate():
    # Min(11, tax + 8*is_home_province) -- REPORTS.PAS Rep_Provs. Alpha
    # (tax=5, not home) -> tier 5. Beta (tax=1, IS the kingdom's own home
    # province) -> tier min(11, 1+8)=9. Gamma (tax=None -> 0, not home)
    # -> tier 0. Expected order: Beta (9), Alpha (5), Gamma (0) --
    # despite Gamma's coordinate sorting first and Beta's own name
    # sorting after Alpha's alphabetically.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(5, 5)))
    state.add_province(ProvinceState(HexCoord(9, 9), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, name="Alpha", tax=5))
    state.add_province(ProvinceState(HexCoord(5, 5), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, name="Beta", tax=1))
    state.add_province(ProvinceState(HexCoord(0, 0), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, name="Gamma"))

    lines = describe_provinces_report(state, 1)

    names_in_order = [line.split()[0] for line in lines[4:]]
    assert names_in_order == ["Beta", "Alpha", "Gamma"]


def test_describe_provinces_report_home_province_tier_bonus_caps_at_eleven():
    # tax=10 + home bonus 8 = 18, capped at Min(11, ...) = 11 -- still
    # sorts ahead of a non-home province with a higher raw tax (9 < 11).
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_province(ProvinceState(HexCoord(0, 0), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, name="Capital", tax=10))
    state.add_province(ProvinceState(HexCoord(1, 1), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, name="Frontier", tax=9))

    lines = describe_provinces_report(state, 1)

    names_in_order = [line.split()[0] for line in lines[4:]]
    assert names_in_order == ["Capital", "Frontier"]


# -- Phase 562: describe_map_report() -- the real ASCII map --


def test_describe_map_report_empty_when_no_provinces_known():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))

    assert describe_map_report(state, 1) == []


def test_describe_map_report_starts_with_the_real_scribe_intro():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_province(
        ProvinceState(
            HexCoord(1, 1), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, name="Capital", explored_percent_by_kingdom={1: 100}
        )
    )

    lines = describe_map_report(state, 1)

    assert lines[2] == "  Sire, our royal scribe has drawn up a map of all neighboring lands: "
    assert lines[-3] == "Key:   _ Plains   + Forest   & Jungle   ^ Mountain   . Desert     Sea"


def test_describe_map_report_inserts_ice_cap_label_when_topmost_row_is_y_1():
    # Phase 577: real sourced trigger -- the map's own topmost row is
    # y == 1, the world's own northern edge.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_province(
        ProvinceState(
            HexCoord(1, 1), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, name="Capital", explored_percent_by_kingdom={1: 100}
        )
    )

    lines = describe_map_report(state, 1)

    assert lines[4] == "Ice cap"
    assert lines[5] == "-" * 78


def test_describe_map_report_omits_ice_cap_label_when_topmost_row_is_below_y_1():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_province(
        ProvinceState(
            HexCoord(1, 4), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, name="Capital", explored_percent_by_kingdom={1: 100}
        )
    )

    lines = describe_map_report(state, 1)

    assert "Ice cap" not in lines


def test_describe_map_report_only_renders_provinces_this_kingdom_knows():
    # Phase 628: ProvinceState.known_to_kingdom() (Phase 623) now gates
    # what the map shows -- a province that merely exists in
    # state.provinces, with no recorded exploration by this Kingdom,
    # must not appear.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(1, 1)))
    state.add_province(
        ProvinceState(
            HexCoord(1, 1), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, name="Capital", explored_percent_by_kingdom={1: 100}
        )
    )
    state.add_province(ProvinceState(HexCoord(2, 1), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=None, name="Unseen"))

    text = "\n".join(describe_map_report(state, 1))

    assert "Capital" in text
    assert "Unseen" not in text


def test_describe_map_report_ownership_alone_does_not_imply_knowledge():
    # Phase 69/623: a Kingdom that owns a province without a recorded
    # Explore/Move order into it reads as 0% known, same as anyone
    # else -- ownership must not silently substitute for knowledge here.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(1, 1)))
    state.add_province(ProvinceState(HexCoord(1, 1), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, name="Unexplored Capital"))

    assert describe_map_report(state, 1) == []


def test_describe_map_report_splits_into_a_far_side_page_when_too_wide():
    # Phase 627: with tier auto-selection, even the densest real tier
    # (stride8) only fits 9 columns/page -- 10 known columns spanning
    # the wrap (13-18,1-4), home at x=18, guarantees a far-side page
    # regardless of which tier gets picked. `select_layout_tier()`
    # picks stride8 here (cluster of 10 exceeds every tier's own cap,
    # floor tier used); `paginate_known_columns()` then keeps the 9
    # columns closest to home on page 1, pushing the 1 farthest (13)
    # to page 2. Page 1's own provinces sit at y=1 (Ice cap trigger);
    # page 2's own sits at y=5 (no trigger) -- proving the Ice-cap
    # check runs independently per page, not once globally.
    state = GameState()
    # Phase 871: this test's own narrative assumes an 18-wide board
    # (column 18 borders column 1) -- GameState.board_width now
    # genuinely drives the map's own wraparound math, so that must be
    # set explicitly instead of relying on the field's own real default
    # of 30 (Super-AK) to accidentally not matter.
    state.board_width = 18
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(18, 1)))
    for x in (14, 15, 16, 17, 18, 1, 2, 3, 4):
        state.add_province(
            ProvinceState(
                HexCoord(x, 1), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, name=f"P{x}", explored_percent_by_kingdom={1: 100}
            )
        )
    state.add_province(
        ProvinceState(
            HexCoord(13, 5), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, name="Farland", explored_percent_by_kingdom={1: 100}
        )
    )

    lines = describe_map_report(state, 1)
    text = "\n".join(lines)

    assert "Sire, our royal scribe has drawn up a map of all neighboring lands:" in text
    assert "We also drew up this map of lands on the far side of the world:" in text
    assert lines.count("Ice cap") == 1
    assert lines.count("Key:   _ Plains   + Forest   & Jungle   ^ Mountain   . Desert     Sea") == 1
    for name in ("P14", "P15", "P16", "P17", "P18", "P1", "P2", "P3", "P4", "Farland"):
        assert name in text
    # The far-side page's own intro directly follows the previous
    # page's last grid row -- no blank line in between.
    far_index = lines.index("  We also drew up this map of lands on the far side of the world: ")
    assert lines[far_index - 1].strip() != ""


def test_describe_map_report_uses_the_real_board_width_for_wraparound_not_the_18_wide_default():
    # Phase 871: columns 1 and 18 are only wraparound-adjacent under the
    # pre-fix hardcoded-18-wide assumption. On GameState's own real
    # default board (30-wide, Super-AK), they're 17 apart -- not
    # adjacent -- so this must produce a genuine far-side split.
    state = GameState()
    assert state.board_width == 30
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(1, 1)))
    state.add_province(
        ProvinceState(
            HexCoord(1, 1), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, name="Homeland", explored_percent_by_kingdom={1: 100}
        )
    )
    state.add_province(
        ProvinceState(
            HexCoord(18, 1), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, name="Farland", explored_percent_by_kingdom={1: 100}
        )
    )

    lines = describe_map_report(state, 1)
    text = "\n".join(lines)

    assert "We also drew up this map of lands on the far side of the world:" in text
    assert "Homeland" in text
    assert "Farland" in text


def test_describe_map_report_wraps_at_the_real_30_wide_seam():
    # Companion case: columns 1 and 30 genuinely ARE adjacent on a real
    # 30-wide board (the true cylindrical seam) -- confirms wraparound
    # still works correctly once it's keyed to the real board width,
    # not just that it stops firing at the wrong (18-wide) one.
    state = GameState()
    assert state.board_width == 30
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(1, 1)))
    state.add_province(
        ProvinceState(
            HexCoord(1, 1), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, name="Homeland", explored_percent_by_kingdom={1: 100}
        )
    )
    state.add_province(
        ProvinceState(
            HexCoord(30, 1), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, name="Nearland", explored_percent_by_kingdom={1: 100}
        )
    )

    lines = describe_map_report(state, 1)
    text = "\n".join(lines)

    assert "We also drew up this map of lands on the far side of the world:" not in text
    assert "Homeland" in text
    assert "Nearland" in text


def test_compose_letter_report_places_the_map_between_provinces_and_characters():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_province(
        ProvinceState(
            HexCoord(1, 1), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, name="Capital", explored_percent_by_kingdom={1: 100}
        )
    )

    lines = compose_letter_report([], state, 1, ScriptedRandom([]))

    provinces_index = lines.index("PROVINCES")
    characters_index = lines.index("CHARACTERS")
    scribe_index = lines.index("  Sire, our royal scribe has drawn up a map of all neighboring lands: ")
    assert provinces_index < scribe_index < characters_index


# -- Phase 221: describe_characters_report() -- the "CHARACTERS" section --


_CHARACTERS_OPENING = (
    "My Lord, Great indeed are the leaders of our proud kingdom.  Though thee "
    "knows them well, I list them here for thy consideration (the first line "
    "shows pay and abilities; line 2 shows move precedence and aptitude.)"
)

# REPORTS.PAS Rep_Leaders (~lines 818-824), verbatim -- see turn_report.py's
# own module-level constants of the same names.
_CHARACTERS_CAPTION_LINE_1 = "                                         Pay Modified Skills/Aptitudes:"
_CHARACTERS_CAPTION_LINE_2 = "             Province                     /  Combat     Magical    Other"
_CHARACTERS_COLUMN_HEADER = "Character      Loc Align  Temp M/F  Race Ini TaMaNaArMe WhNeElPsIl DrThExSpSa"
# Phase 625: `_discovery_skill_modifier_row()`'s own all-blank case (no
# Kingdom Discoveries known) -- 45-char prefix + 2 chars/ability * 15 +
# 2 extra group-separator spaces (after Melee, after Illusion) = 77
# spaces total.
_CHARACTERS_NO_DISCOVERY_MODIFIERS_LINE = " " * 77
_CHARACTERS_HEADER_LINES = [
    "CHARACTERS",
    _CHARACTERS_OPENING,
    "",
    _CHARACTERS_CAPTION_LINE_1,
    _CHARACTERS_CAPTION_LINE_2,
    _CHARACTERS_COLUMN_HEADER,
    _CHARACTERS_NO_DISCOVERY_MODIFIERS_LINE,
]

# The real skill row (`_ability_value_row(..., tactical_widens=True)`) and
# aptitude row (`_ability_value_row(..., tactical_widens=False)` prefixed by
# the Total_Skill+March*2 leading value) for 15 all-zero `Ability` values.
_NO_SKILLS_LINE = "  0 0 0 0 0  0 0 0 0 0  0 0 0 0 0"
_NO_APTITUDE_LINE = " 0   0 0 0 0 0  0 0 0 0 0  0 0 0 0 0"


# -- Phase 625: _discovery_skill_modifier_row() -- the sk_mod `^`/`^^`
# markers above the ability columns.


def test_discovery_skill_modifier_row_matches_a_real_sample_byte_for_byte():
    # Desktop/PROGRAMMA AK/SE3__T5.K1 line 811, verbatim -- this Kingdom
    # knows exactly one of Melee's own two linked Discoveries (fix8,
    # STRENGTH_ELIXIR), producing a single '^' at column 53.
    state = GameState()
    kingdom = KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0))
    kingdom.discoveries = {Discovery.STRENGTH_ELIXIR}
    state.add_kingdom(kingdom)
    state.add_leader(LeaderState(1, 1, "Aldric", HexCoord(0, 0), is_king=True))

    lines = describe_characters_report(state, 1)

    marker_row = lines[6]
    assert marker_row == "                                                     ^                       "
    assert marker_row.index("^") == 53


def test_discovery_skill_modifier_row_double_marker_when_both_discoveries_known():
    state = GameState()
    kingdom = KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0))
    kingdom.discoveries = {Discovery.STRENGTH_ELIXIR, Discovery.MITHRIL_CHAINMAIL}
    state.add_kingdom(kingdom)
    state.add_leader(LeaderState(1, 1, "Aldric", HexCoord(0, 0), is_king=True))

    lines = describe_characters_report(state, 1)

    assert lines[6][53:55] == "^^"


def test_discovery_skill_modifier_row_marks_the_other_group_too():
    # Druid (the "Other" group, sk >= Druid) -- MEDITATION_INCENSE is
    # its own first linked Discovery, confirming the second branch of
    # the formula (not just the Combat-group branch the real sample
    # above exercises).
    state = GameState()
    kingdom = KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0))
    kingdom.discoveries = {Discovery.MEDITATION_INCENSE}
    state.add_kingdom(kingdom)
    state.add_leader(LeaderState(1, 1, "Aldric", HexCoord(0, 0), is_king=True))

    lines = describe_characters_report(state, 1)

    assert lines[6][67] == "^"


def test_discovery_skill_modifier_row_never_marks_magical_abilities():
    # White..Illusion (sk_mod always 0 in the source, unconditionally)
    # -- a Discovery that happens to share an ordinal with that range
    # (there are none linked to it at all, by construction) can't move
    # this row; simplest direct check is that a Kingdom knowing every
    # single Discovery still leaves the magical-ability band blank.
    state = GameState()
    kingdom = KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0))
    kingdom.discoveries = set(Discovery)
    state.add_kingdom(kingdom)
    state.add_leader(LeaderState(1, 1, "Aldric", HexCoord(0, 0), is_king=True))

    lines = describe_characters_report(state, 1)

    # Magical group is abilities 5-9 (White..Illusion): relative offsets
    # 22-32 within the marker row (after Tactical..Melee's 5*2=10 chars
    # + 1 group-separator space = offset 11, then 5*2=10 more chars).
    magical_band = lines[6][45 + 11 : 45 + 11 + 10]
    assert magical_band == " " * 10


def test_describe_characters_report_renders_own_leader_with_no_recorded_data():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_province(ProvinceState(HexCoord(0, 0), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, name="Capital City"))
    state.add_leader(LeaderState(1, 1, "Aldric", HexCoord(0, 0), is_king=True))

    lines = describe_characters_report(state, 1)

    assert lines == [
        *_CHARACTERS_HEADER_LINES,
        f"Aldric           0  Unkn  Unkn     Human  0 {_NO_SKILLS_LINE}",
        _NO_APTITUDE_LINE,
    ]


def test_describe_characters_report_none_at_present_when_no_leaders_owned():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))

    lines = describe_characters_report(state, 1)

    assert lines == [*_CHARACTERS_HEADER_LINES, "None at present"]


def test_describe_characters_report_ignores_other_kingdoms_leaders():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_kingdom(KingdomState(2, "Otherland", Race.ELVEN, Alignment.NEUTRAL, HexCoord(1, 1)))
    state.add_leader(LeaderState(9, 2, "Kwoth", HexCoord(1, 1)))

    lines = describe_characters_report(state, 1)

    assert lines == [*_CHARACTERS_HEADER_LINES, "None at present"]


# -- Phase 638: Desc_Stranger rendering primitives (Best_Ab/Get_AbDesc/
# stranger descriptor/Tell_Align) -- primitives only, not wired into
# describe_characters_report() yet, so tested directly.


def test_best_ability_picks_the_clearly_highest_skilled_ability():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    leader = LeaderState(1, 1, "Aldric", HexCoord(0, 0), skills=_skills_with(ARCHERY=3, MELEE=1))

    assert _best_ability(state, leader) == (Ability.ARCHERY, 3)


def test_best_ability_ties_pick_the_earlier_declared_ability():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    leader = LeaderState(1, 1, "Aldric", HexCoord(0, 0), skills=_skills_with(MELEE=2, TACTICAL=2))

    # Tactical is declared before Melee -- the documented, unsourced tie-break.
    assert _best_ability(state, leader) == (Ability.TACTICAL, 2)


def test_best_ability_with_no_skills_recorded_defaults_to_tactical_zero():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    leader = LeaderState(1, 1, "Aldric", HexCoord(0, 0))

    assert _best_ability(state, leader) == (Ability.TACTICAL, 0)


def test_leader_ability_description_matches_the_real_phrase_bands():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    cases = [(0, "noted for "), (1, "well known for "), (2, "famous for "), (3, "renowned for "), (4, "world-famous for "), (5, "revered for "), (6, "worshipped for "), (9, "worshipped for ")]
    for level, phrase in cases:
        # TACTICAL explicitly, not ARCHERY: level 0 ties with every other
        # ability's own 0 default, and Tactical (declared first) wins that
        # tie -- explicitly targeting it avoids the ambiguity entirely.
        leader = LeaderState(1, 1, "Aldric", HexCoord(0, 0), skills=_skills_with(TACTICAL=level))
        assert _leader_ability_description(state, leader) == f"(a Human {phrase}Tactics)"


def test_leader_ability_description_race_falls_back_to_the_leaders_own_kingdom():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_kingdom(KingdomState(2, "Otherland", Race.ELVEN, Alignment.NEUTRAL, HexCoord(1, 1)))
    leader = LeaderState(9, 2, "Kwoth", HexCoord(1, 1), skills=_skills_with(ARCHERY=2))

    assert _leader_ability_description(state, leader) == "(a Elf famous for Archery)"


def test_stranger_descriptor_dead_leader_shows_named_province():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_province(ProvinceState(HexCoord(2, 2), Terrain.PLAINS, Race.HUMAN, name="Ashford"))
    leader = LeaderState(9, 1, "Kwoth", HexCoord(2, 2))
    state.add_leader(leader)
    state.remove_leader(9)

    assert _stranger_descriptor(state, state.dead_leaders[9], viewer_kingdom_id=99) == ": buried in Ashford"


def test_stranger_descriptor_dead_leader_falls_back_to_province_code_when_unnamed():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    leader = LeaderState(9, 1, "Kwoth", HexCoord(2, 3))
    state.add_leader(leader)
    state.remove_leader(9)

    assert _stranger_descriptor(state, state.dead_leaders[9], viewer_kingdom_id=99) == ": buried in 203"


def test_stranger_descriptor_wandering_hero():
    state = GameState()
    leader = LeaderState(9, None, "Kwoth", HexCoord(1, 1))

    assert _stranger_descriptor(state, leader, viewer_kingdom_id=99) == ": a wandering Hero"


def test_stranger_descriptor_a_king():
    state = GameState()
    leader = LeaderState(9, 2, "Foreign King", HexCoord(1, 1), is_king=True)

    assert _stranger_descriptor(state, leader, viewer_kingdom_id=99) == ": a King character"


def test_stranger_descriptor_an_ordinary_hero_of_a_real_king():
    state = GameState()
    state.add_kingdom(KingdomState(2, "Otherland", Race.ELVEN, Alignment.NEUTRAL, HexCoord(1, 1)))
    state.add_leader(LeaderState(1, 2, "Roderick", HexCoord(1, 1), is_king=True))
    hero = LeaderState(9, 2, "Kwoth", HexCoord(1, 1))

    assert _stranger_descriptor(state, hero, viewer_kingdom_id=99) == ": Roderick's Hero"


def test_stranger_descriptor_truncates_at_26_characters():
    state = GameState()
    state.add_kingdom(KingdomState(2, "Otherland", Race.ELVEN, Alignment.NEUTRAL, HexCoord(1, 1)))
    state.add_leader(LeaderState(1, 2, "A Very Long Royal Name Indeed", HexCoord(1, 1), is_king=True))
    hero = LeaderState(9, 2, "Kwoth", HexCoord(1, 1))

    descriptor = _stranger_descriptor(state, hero, viewer_kingdom_id=99)
    assert len(descriptor) == 26
    assert descriptor == ": A Very Long Royal Name I"


# -- Phase 729: AdvancedAbility.SPY_DOUBLE_AGENT's own report masquerade --


def test_stranger_descriptor_double_agent_masquerades_as_a_wandering_hero_to_a_foreign_viewer():
    state = GameState()
    state.add_kingdom(KingdomState(2, "Otherland", Race.ELVEN, Alignment.NEUTRAL, HexCoord(1, 1)))
    state.add_leader(LeaderState(1, 2, "Roderick", HexCoord(1, 1), is_king=True))
    spy = LeaderState(9, 2, "Kwoth", HexCoord(1, 1))
    spy.advanced_abilities.add(AdvancedAbility.SPY_DOUBLE_AGENT)

    assert _stranger_descriptor(state, spy, viewer_kingdom_id=99) == ": a wandering Hero"


def test_stranger_descriptor_double_agent_shows_truthfully_to_their_own_real_kingdom():
    state = GameState()
    state.add_kingdom(KingdomState(2, "Otherland", Race.ELVEN, Alignment.NEUTRAL, HexCoord(1, 1)))
    state.add_leader(LeaderState(1, 2, "Roderick", HexCoord(1, 1), is_king=True))
    spy = LeaderState(9, 2, "Kwoth", HexCoord(1, 1))
    spy.advanced_abilities.add(AdvancedAbility.SPY_DOUBLE_AGENT)

    assert _stranger_descriptor(state, spy, viewer_kingdom_id=2) == ": Roderick's Hero"


def test_render_stranger_row_shows_hire_hint_for_a_masquerading_double_agent():
    state = GameState()
    spy = LeaderState(9, 2, "Kwoth", HexCoord(5, 5), race=Race.HUMAN)
    spy.advanced_abilities.add(AdvancedAbility.SPY_DOUBLE_AGENT)

    lines = _render_stranger_row(
        state, spy, show_location=True, priest=None, tell_align_distance=2, viewer_kingdom_id=99, king=None
    )

    # king=None -> required_pay() permissively returns 1.
    assert lines[1] == "  (who, we hear, desires to enter thy Majesty's service for 1 gold per annum)"


def test_render_stranger_row_omits_hire_hint_for_a_double_agent_viewed_by_their_own_kingdom():
    state = GameState()
    spy = LeaderState(9, 2, "Kwoth", HexCoord(5, 5), race=Race.HUMAN)
    spy.advanced_abilities.add(AdvancedAbility.SPY_DOUBLE_AGENT)

    lines = _render_stranger_row(
        state, spy, show_location=True, priest=None, tell_align_distance=2, viewer_kingdom_id=2, king=None
    )

    assert len(lines) == 1


def test_tell_align_basic_arithmetic_and_the_king_vs_hero_shift():
    priest = LeaderState(1, 1, "Priest", HexCoord(0, 0))
    hero_target = LeaderState(9, 2, "Kwoth", HexCoord(3, 5))
    hero_target.alignment = Alignment.GOOD

    assert _tell_align(hero_target, priest) is Alignment.DIVINE

    king_target = LeaderState(9, 2, "Foreign King", HexCoord(3, 5), is_king=True)
    king_target.alignment = Alignment.GOOD
    # Same coordinates/alignment, only is_king differs -> different tdmod shift,
    # so this is NOT a copy-paste of the assertion above.
    assert _tell_align(king_target, priest) is Alignment.DRUID


def test_tell_align_clamps_at_the_divine_floor():
    priest = LeaderState(1, 1, "Priest", HexCoord(0, 0))
    target = LeaderState(9, 2, "Kwoth", HexCoord(0, 3))
    target.alignment = Alignment.GOOD  # raw ta computes to -2 here, unclamped

    assert _tell_align(target, priest) is Alignment.DIVINE


def test_tell_align_clamps_at_the_undead_ceiling():
    priest = LeaderState(1, 1, "Priest", HexCoord(0, 0))
    target = LeaderState(9, 2, "Kwoth", HexCoord(4, 0))
    target.alignment = Alignment.ANTI_HOLY  # raw ta computes to 8 here, unclamped

    assert _tell_align(target, priest) is Alignment.UNDEAD


def test_tell_align_requires_a_recorded_alignment():
    priest = LeaderState(1, 1, "Priest", HexCoord(0, 0))
    target = LeaderState(9, 2, "Kwoth", HexCoord(3, 5))
    assert target.alignment is None

    with pytest.raises(AssertionError):
        _tell_align(target, priest)


# -- Phase 639: wires impulse 2 (Known_Loc)/impulse 3 (Tell_Align near
# this kingdom's own Priest) into describe_characters_report(), using
# the Phase 636/637/638 primitives built earlier.


def _priest_leader(leader_id: int, kingdom_id: int, coord: HexCoord) -> LeaderState:
    priest = LeaderState(leader_id, kingdom_id, "Priestly", coord)
    priest.merit_tally.resurrection_bless_casts = 5  # wins Office.PRIEST (min 1 point)
    return priest


def test_resolve_viewer_priest_none_when_nobody_holds_the_office():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))

    assert _resolve_viewer_priest(state, 1) is None


def test_resolve_viewer_priest_none_when_a_different_kingdom_holds_it():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_kingdom(KingdomState(2, "Otherland", Race.ELVEN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_leader(_priest_leader(50, 2, HexCoord(0, 0)))

    assert _resolve_viewer_priest(state, 1) is None


def test_resolve_viewer_priest_found_when_this_kingdom_holds_it():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    priest = _priest_leader(50, 1, HexCoord(0, 0))
    state.add_leader(priest)

    assert _resolve_viewer_priest(state, 1) is priest


def test_impulse2_candidates_includes_a_known_stranger_and_excludes_valhalla_visitor():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_province(ProvinceState(HexCoord(5, 5), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    stranger = LeaderState(9, 2, "Kwoth", HexCoord(5, 5))
    state.add_leader(stranger)
    visitor = LeaderState(199, 2, "Valhalla Visitor", HexCoord(5, 5))
    state.add_leader(visitor)

    result = _impulse2_candidates(state, 1, orig_turn=0)

    assert result == [stranger]


def test_impulse2_candidates_includes_a_dead_strangers_last_known_position():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_province(ProvinceState(HexCoord(5, 5), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_leader(LeaderState(9, 2, "Kwoth", HexCoord(5, 5)))
    state.remove_leader(9)

    result = _impulse2_candidates(state, 1, orig_turn=0)

    assert result == [state.dead_leaders[9]]


def test_impulse3_candidates_empty_without_a_priest():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_leader(LeaderState(9, 2, "Foreign King", HexCoord(2, 1), is_king=True))

    assert _impulse3_candidates(state, 1, priest=None, orig_turn=0) == []


def test_impulse3_candidates_excludes_a_hero_and_a_too_distant_king():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    priest = _priest_leader(50, 1, HexCoord(0, 0))
    state.add_leader(priest)
    hero = LeaderState(9, 2, "Kwoth", HexCoord(2, 1))  # distance 3, but not a King
    state.add_leader(hero)
    far_king = LeaderState(10, 2, "Far King", HexCoord(4, 1), is_king=True)  # distance 5 > 4
    state.add_leader(far_king)

    assert _impulse3_candidates(state, 1, priest=priest, orig_turn=0) == []


def test_impulse3_candidates_uses_the_real_board_width_not_the_18_wide_default():
    # Phase 871: columns 1 and 18 are ~1 hex apart under the pre-fix
    # hardcoded-18-wide assumption (well within the real "within 4
    # hexes" gate) but genuinely 13 hexes apart on GameState's own real
    # default board (30-wide, Super-AK) -- past the gate.
    state = GameState()
    assert state.board_width == 30
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    priest = _priest_leader(50, 1, HexCoord(1, 2))
    state.add_leader(priest)
    far_king = LeaderState(10, 2, "Far King", HexCoord(18, 2), is_king=True)
    state.add_leader(far_king)

    assert _impulse3_candidates(state, 1, priest=priest, orig_turn=0) == []


def test_impulse3_candidates_excludes_a_king_already_known_via_impulse_2():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    priest = _priest_leader(50, 1, HexCoord(0, 0))
    state.add_leader(priest)
    state.add_province(ProvinceState(HexCoord(3, 1), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))  # distance 4
    known_king = LeaderState(10, 2, "Known King", HexCoord(3, 1), is_king=True)
    state.add_leader(known_king)

    assert _impulse3_candidates(state, 1, priest=priest, orig_turn=0) == []


def test_impulse3_candidates_includes_a_real_unknown_king_within_range():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    priest = _priest_leader(50, 1, HexCoord(0, 0))
    state.add_leader(priest)
    king = LeaderState(10, 2, "Unknown King", HexCoord(3, 1), is_king=True)  # distance 4, unowned province
    state.add_leader(king)

    assert _impulse3_candidates(state, 1, priest=priest, orig_turn=0) == [king]


def test_describe_characters_report_impulse2_known_stranger_appears_with_ability_text():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_kingdom(KingdomState(2, "Otherland", Race.ELVEN, Alignment.NEUTRAL, HexCoord(5, 5)))
    state.add_province(ProvinceState(HexCoord(5, 5), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_leader(LeaderState(1, 2, "Roderick", HexCoord(5, 5), is_king=True))
    stranger = LeaderState(9, 2, "Kwoth", HexCoord(5, 5), skills=_skills_with(ARCHERY=2))
    state.add_leader(stranger)

    lines = describe_characters_report(state, 1)

    stranger_row = next(line for line in lines if line.startswith("Kwoth"))
    assert ": Roderick's Hero" in stranger_row
    assert "a Elf famous for Archery" in stranger_row
    assert not any('Rod senses' in line for line in lines)  # no Priest resolved


def test_describe_characters_report_impulse2_masquerading_double_agent_shows_as_a_wandering_hero():
    # Phase 729: end-to-end proof that describe_characters_report()
    # threads viewer_kingdom_id=kingdom_id through to the masquerade --
    # same fixture shape as the "known stranger" test above, but the
    # stranger holds SPY_DOUBLE_AGENT and should NOT reveal Roderick.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_kingdom(KingdomState(2, "Otherland", Race.ELVEN, Alignment.NEUTRAL, HexCoord(5, 5)))
    state.add_province(ProvinceState(HexCoord(5, 5), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_leader(LeaderState(1, 2, "Roderick", HexCoord(5, 5), is_king=True))
    spy = LeaderState(9, 2, "Kwoth", HexCoord(5, 5), skills=_skills_with(ARCHERY=2))
    spy.advanced_abilities.add(AdvancedAbility.SPY_DOUBLE_AGENT)
    state.add_leader(spy)

    lines = describe_characters_report(state, 1)

    stranger_row = next(line for line in lines if line.startswith("Kwoth"))
    assert ": a wandering Hero" in stranger_row
    assert "Roderick" not in stranger_row


def test_describe_characters_report_impulse2_secondary_reveal_fires_within_two_hexes():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_kingdom(KingdomState(2, "Otherland", Race.ELVEN, Alignment.NEUTRAL, HexCoord(2, 0)))
    priest = _priest_leader(50, 1, HexCoord(0, 0))
    state.add_leader(priest)
    state.add_province(ProvinceState(HexCoord(2, 0), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))  # distance 2
    stranger = LeaderState(9, 2, "Kwoth", HexCoord(2, 0))
    stranger.alignment = Alignment.GOOD
    state.add_leader(stranger)

    lines = describe_characters_report(state, 1)

    idx = next(i for i, line in enumerate(lines) if line.startswith("Kwoth"))
    assert "Rod senses" in lines[idx + 1]


def test_describe_characters_report_impulse2_secondary_reveal_does_not_fire_beyond_two_hexes():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_kingdom(KingdomState(2, "Otherland", Race.ELVEN, Alignment.NEUTRAL, HexCoord(2, 1)))
    priest = _priest_leader(50, 1, HexCoord(0, 0))
    state.add_leader(priest)
    state.add_province(ProvinceState(HexCoord(2, 1), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))  # distance 3
    stranger = LeaderState(9, 2, "Kwoth", HexCoord(2, 1))
    stranger.alignment = Alignment.GOOD
    state.add_leader(stranger)

    lines = describe_characters_report(state, 1)

    assert not any("Rod senses" in line for line in lines)


def test_describe_characters_report_impulse2_no_reveal_when_target_alignment_unrecorded():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_kingdom(KingdomState(2, "Otherland", Race.ELVEN, Alignment.NEUTRAL, HexCoord(2, 0)))
    priest = _priest_leader(50, 1, HexCoord(0, 0))
    state.add_leader(priest)
    state.add_province(ProvinceState(HexCoord(2, 0), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))  # distance 2
    stranger = LeaderState(9, 2, "Kwoth", HexCoord(2, 0))
    assert stranger.alignment is None
    state.add_leader(stranger)

    lines = describe_characters_report(state, 1)

    assert any(line.startswith("Kwoth") for line in lines)
    assert not any("Rod senses" in line for line in lines)


def test_describe_characters_report_impulse3_king_shows_blank_location_and_unconditional_reveal():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_kingdom(KingdomState(2, "Otherland", Race.ELVEN, Alignment.NEUTRAL, HexCoord(3, 1)))
    priest = _priest_leader(50, 1, HexCoord(0, 0))
    state.add_leader(priest)
    king = LeaderState(10, 2, "Unknown King", HexCoord(3, 1), is_king=True)  # distance 4, unowned province
    king.alignment = Alignment.EVIL
    state.add_leader(king)

    lines = describe_characters_report(state, 1)

    idx = next(i for i, line in enumerate(lines) if line.startswith("Unknown King"))
    assert lines[idx][14:18] == "    "  # blank Loc column
    assert "Rod senses" in lines[idx + 1]


def test_describe_characters_report_impulse3_king_already_known_appears_only_once_via_impulse2():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_kingdom(KingdomState(2, "Otherland", Race.ELVEN, Alignment.NEUTRAL, HexCoord(3, 1)))
    priest = _priest_leader(50, 1, HexCoord(0, 0))
    state.add_leader(priest)
    state.add_province(ProvinceState(HexCoord(3, 1), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))  # distance 4, owned
    king = LeaderState(10, 2, "Dupe King", HexCoord(3, 1), is_king=True)
    state.add_leader(king)

    lines = describe_characters_report(state, 1)

    matching_rows = [line for line in lines if line.startswith("Dupe King")]
    assert len(matching_rows) == 1
    assert matching_rows[0][14:18] != "    "  # the impulse-2 row shows a real location, not blank


# -- Phase 646: Desc_Stranger's mercenary hire-cost hint (impulse 2 only) --


def test_render_stranger_row_shows_hire_hint_for_cheap_kingdomless_hero():
    state = GameState()
    hero = LeaderState(9, None, "Kwoth", HexCoord(5, 5), race=Race.HUMAN)

    lines = _render_stranger_row(
        state, hero, show_location=True, priest=None, tell_align_distance=2, viewer_kingdom_id=99, king=None
    )

    # king=None -> required_pay() permissively returns 1.
    assert lines[1] == "  (who, we hear, desires to enter thy Majesty's service for 1 gold per annum)"


def test_render_stranger_row_omits_hire_hint_when_cost_exceeds_three():
    state = GameState()
    hero = LeaderState(9, None, "Kwoth", HexCoord(5, 5), race=Race.HUMAN)
    hero.alignment = Alignment.DIVINE
    king = LeaderState(1, 1, "Roderick", HexCoord(0, 0), is_king=True, race=Race.HUMAN)
    king.alignment = Alignment.UNDEAD  # max alignment distance -> pay == 5

    lines = _render_stranger_row(
        state, hero, show_location=True, priest=None, tell_align_distance=2, viewer_kingdom_id=99, king=king
    )

    assert len(lines) == 1


def test_render_stranger_row_omits_hire_hint_for_a_dead_kingdomless_hero():
    state = GameState()
    state.add_leader(LeaderState(9, None, "Kwoth", HexCoord(5, 5), race=Race.HUMAN))
    state.remove_leader(9)
    dead_hero = state.dead_leaders[9]

    lines = _render_stranger_row(
        state, dead_hero, show_location=True, priest=None, tell_align_distance=2, viewer_kingdom_id=99, king=None
    )

    assert len(lines) == 1
    assert "Majesty's service" not in lines[0]


def test_render_stranger_row_omits_hire_hint_for_a_leader_with_a_kingdom():
    state = GameState()
    hero = LeaderState(9, 2, "Kwoth", HexCoord(5, 5), race=Race.HUMAN)

    lines = _render_stranger_row(
        state, hero, show_location=True, priest=None, tell_align_distance=2, viewer_kingdom_id=99, king=None
    )

    assert len(lines) == 1


def test_render_stranger_row_never_shows_hire_hint_for_impulse_3():
    state = GameState()
    # A kingdomless "King" can't really occur in this game model, but this
    # confirms the hint is gated on show_location (impulse 2) structurally,
    # not merely absent because no real impulse-3 candidate is ever kingdomless.
    hero = LeaderState(9, None, "Kwoth", HexCoord(5, 5))

    lines = _render_stranger_row(
        state, hero, show_location=False, priest=None, tell_align_distance=None, viewer_kingdom_id=99, king=None
    )

    assert len(lines) == 1


def test_describe_characters_report_impulse2_shows_hire_hint_after_ability_text():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_province(ProvinceState(HexCoord(5, 5), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    stranger = LeaderState(9, None, "Kwoth", HexCoord(5, 5), race=Race.HUMAN)
    state.add_leader(stranger)

    lines = describe_characters_report(state, 1)

    idx = next(i for i, line in enumerate(lines) if line.startswith("Kwoth"))
    assert lines[idx + 1] == "  (who, we hear, desires to enter thy Majesty's service for 1 gold per annum)"


def test_describe_characters_report_impulse2_no_hire_hint_for_an_owned_stranger():
    # Non-regression: a stranger who belongs to another kingdom (not a
    # wandering Hero) never gets the hint, matching the real lstate<>
    # Mercenary case.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_kingdom(KingdomState(2, "Otherland", Race.ELVEN, Alignment.NEUTRAL, HexCoord(5, 5)))
    state.add_province(ProvinceState(HexCoord(5, 5), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_leader(LeaderState(1, 2, "Roderick", HexCoord(5, 5), is_king=True))
    stranger = LeaderState(9, 2, "Kwoth", HexCoord(5, 5))
    state.add_leader(stranger)

    lines = describe_characters_report(state, 1)

    assert not any("Majesty's service" in line for line in lines)


# -- Phase 637: Was_Clairved -- a foreign leader targeted by an Enhanced-
# Clairvoyance cast from this kingdom gets the full impulse-1 row too.


def test_describe_characters_report_ignores_a_clairvoyance_cast_without_enhanced_ability():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_kingdom(KingdomState(2, "Otherland", Race.ELVEN, Alignment.NEUTRAL, HexCoord(1, 1)))
    watcher = LeaderState(1, 1, "Aldric", HexCoord(0, 0), is_king=True)
    watcher.clairvoyance_cast_target = 9  # no AdvancedAbility.ENHANCED_CLAIRVOYANCE
    state.add_leader(watcher)
    state.add_leader(LeaderState(9, 2, "Kwoth", HexCoord(1, 1)))

    lines = describe_characters_report(state, 1)

    assert lines == [
        *_CHARACTERS_HEADER_LINES,
        f"Aldric           0  Unkn  Unkn     Human  0 {_NO_SKILLS_LINE}",
        _NO_APTITUDE_LINE,
    ]


def test_describe_characters_report_was_clairved_leader_gets_a_full_row():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_kingdom(KingdomState(2, "Otherland", Race.ELVEN, Alignment.NEUTRAL, HexCoord(1, 1)))
    watcher = LeaderState(1, 1, "Aldric", HexCoord(0, 0), is_king=True)
    watcher.clairvoyance_cast_target = 9
    watcher.advanced_abilities = {AdvancedAbility.ENHANCED_CLAIRVOYANCE}
    state.add_leader(watcher)
    state.add_leader(LeaderState(9, 2, "Kwoth", HexCoord(1, 1)))

    lines = describe_characters_report(state, 1)

    assert lines == [
        *_CHARACTERS_HEADER_LINES,
        f"Aldric           0  Unkn  Unkn     Human  0 {_NO_SKILLS_LINE}",
        _NO_APTITUDE_LINE,
        f"Kwoth          101  Unkn  Unkn       Elf  1 {_NO_SKILLS_LINE}",
        _NO_APTITUDE_LINE,
    ]


def test_describe_characters_report_was_clairved_foreign_king_is_not_mistaken_for_this_kingdoms_king():
    # Testland has no King of its own recorded (`king=None`). If the
    # displayed-leader merge were computed before resolving `king` (the
    # bug this phase's design deliberately avoids), a Was_Clairved
    # foreign King showing up in the merged list would get mistaken for
    # this kingdom's own King, changing Bram's own Pay column. Compares
    # the *rendered* row with vs. without the Was_Clairved link (rather
    # than a hand-typed expected string, avoiding a spacing miscount --
    # see Phase 635's own precedent for this) -- `king` must resolve to
    # `None` identically either way, so Bram's row must be identical too.
    def _build():
        state = GameState()
        state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
        state.add_kingdom(KingdomState(2, "Otherland", Race.ELVEN, Alignment.NEUTRAL, HexCoord(1, 1)))
        watcher = LeaderState(1, 1, "Aldric", HexCoord(0, 0))
        watcher.advanced_abilities = {AdvancedAbility.ENHANCED_CLAIRVOYANCE}
        state.add_leader(watcher)
        state.add_leader(LeaderState(9, 2, "Foreign King", HexCoord(1, 1), is_king=True))
        state.add_leader(LeaderState(2, 1, "Bram", HexCoord(0, 0)))
        return state, watcher

    state_with_link, watcher = _build()
    watcher.clairvoyance_cast_target = 9
    lines_with_link = describe_characters_report(state_with_link, 1)
    bram_with_link = next(line for line in lines_with_link if line.startswith("Bram"))

    state_without_link, _ = _build()  # no Was_Clairved link -- foreign King never displayed
    lines_without_link = describe_characters_report(state_without_link, 1)
    bram_without_link = next(line for line in lines_without_link if line.startswith("Bram"))

    assert bram_with_link == bram_without_link


def test_describe_characters_report_was_clairved_leader_falls_back_to_own_kingdoms_race():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_kingdom(KingdomState(2, "Otherland", Race.ELVEN, Alignment.NEUTRAL, HexCoord(1, 1)))
    watcher = LeaderState(1, 1, "Aldric", HexCoord(0, 0), is_king=True)
    watcher.clairvoyance_cast_target = 9
    watcher.advanced_abilities = {AdvancedAbility.ENHANCED_CLAIRVOYANCE}
    state.add_leader(watcher)
    kwoth = LeaderState(9, 2, "Kwoth", HexCoord(1, 1))
    assert kwoth.race is None
    state.add_leader(kwoth)

    lines = describe_characters_report(state, 1)

    kwoth_row = next(line for line in lines if line.startswith("Kwoth"))
    assert "Elf" in kwoth_row  # Otherland's own race, not Testland's Human
    assert "Human" not in kwoth_row


def test_describe_characters_report_falls_back_to_province_code_when_unnamed_province():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_leader(LeaderState(1, 1, "Aldric", HexCoord(2, 3)))

    lines = describe_characters_report(state, 1)

    assert lines[7] == f"Aldric         203  Unkn  Unkn     Human  1 {_NO_SKILLS_LINE}"


def test_describe_characters_report_uses_recorded_alignment_temper_and_race():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    leader = LeaderState(1, 1, "Aldric", HexCoord(0, 0))
    leader.alignment = Alignment.GOOD
    leader.temper = Temper.BRAVE
    leader.race = Race.ELVEN
    state.add_leader(leader)

    lines = describe_characters_report(state, 1)

    assert lines[7] == f"Aldric           0  Good Brave       Elf  1 {_NO_SKILLS_LINE}"


def test_describe_characters_report_uses_recorded_sex():
    # Phase 635: the real "M/F" column, correcting this composer's own
    # Phase 432 "no Gender() concept or field exists" claim -- stale
    # even when written, since LeaderState.sex has existed since Phase
    # 260. Blank (not "Unkn") when unset, the field's own established
    # "no data, don't guess" convention.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    leader = LeaderState(1, 1, "Aldric", HexCoord(0, 0))
    leader.alignment = Alignment.GOOD
    leader.temper = Temper.BRAVE
    leader.race = Race.ELVEN
    leader.sex = Sex.MALE
    state.add_leader(leader)

    lines = describe_characters_report(state, 1)

    assert lines[7] == f"Aldric           0  Good Brave  M    Elf  1 {_NO_SKILLS_LINE}"


def test_describe_characters_report_female_sex():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    leader = LeaderState(1, 1, "Aldric", HexCoord(0, 0))
    leader.alignment = Alignment.GOOD
    leader.temper = Temper.BRAVE
    leader.race = Race.ELVEN
    leader.sex = Sex.FEMALE
    state.add_leader(leader)

    lines = describe_characters_report(state, 1)

    assert lines[7] == f"Aldric           0  Good Brave  F    Elf  1 {_NO_SKILLS_LINE}"


def test_describe_characters_report_renders_recorded_skill_levels():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    leader = LeaderState(1, 1, "Aldric", HexCoord(0, 0))
    leader.skills = SkillTable(raw_values=list(range(31)))
    state.add_leader(leader)

    lines = describe_characters_report(state, 1)

    # Skill row uses effective_skill_level() (discovery-bonus-inclusive,
    # capped at MAX_SKILL_LEVEL=9); aptitude row uses the raw stored
    # aptitude (uncapped) prefixed by Total_Skill(leader) +
    # effective_skill_level(leader, MARCH)*2 == 110 + 2*2 == 114.
    assert lines[7] == "Aldric           0  Unkn  Unkn     Human  1   0 2 4 6 8  9 9 9 9 9  9 9 9 9 9"
    assert lines[8] == "114   1 3 5 7 9 1113151719 2123252729"


def test_describe_characters_report_sorts_by_leader_id():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_leader(LeaderState(40, 1, "Elena", HexCoord(0, 0)))
    state.add_leader(LeaderState(1, 1, "Aldric", HexCoord(0, 0)))

    lines = describe_characters_report(state, 1)

    assert lines[7].startswith("Aldric")
    assert lines[9].startswith("Elena")


def test_describe_characters_report_pay_matches_the_real_lcost_formula():
    # King Bradipo I (Good/Cautious) -- 0; Adele (Good/Brave, real
    # alignment distance 0) -- 1; Indra (Good/Cautious, distance 0, same
    # temper) -- 2, both at distance 0 but differing via the real
    # formula's own per-leader-id bias term (turn/hire_pay.py's own
    # module docstring).
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_leader(
        LeaderState(1, 1, "Bradipo I", HexCoord(0, 0), is_king=True, alignment=Alignment.GOOD, temper=Temper.CAUTIOUS)
    )
    state.add_leader(LeaderState(2, 1, "Adele", HexCoord(0, 0), alignment=Alignment.GOOD, temper=Temper.BRAVE))
    state.add_leader(LeaderState(3, 1, "Indra", HexCoord(0, 0), alignment=Alignment.GOOD, temper=Temper.CAUTIOUS))

    lines = describe_characters_report(state, 1)

    assert lines[7] == f"Bradipo I        0  Good  Caut     Human  0 {_NO_SKILLS_LINE}"
    assert lines[9] == f"Adele            0  Good Brave     Human  1 {_NO_SKILLS_LINE}"
    assert lines[11] == f"Indra            0  Good  Caut     Human  2 {_NO_SKILLS_LINE}"


def test_describe_characters_report_hero_pay_reflects_alignment_distance():
    # NormAlign floors Divine to the same ordinal as Good (both clamp to
    # 1) -- real alignment distance 0, same temper, no other friction --
    # required_pay() is 1 for this King/Hero leader-id pair.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_leader(
        LeaderState(1, 1, "King", HexCoord(0, 0), is_king=True, alignment=Alignment.DIVINE, temper=Temper.CAUTIOUS)
    )
    state.add_leader(LeaderState(2, 1, "Hero", HexCoord(0, 0), alignment=Alignment.GOOD, temper=Temper.CAUTIOUS))

    lines = describe_characters_report(state, 1)

    assert lines[9] == f"Hero             0  Good  Caut     Human  1 {_NO_SKILLS_LINE}"


def test_describe_characters_report_lists_held_items():
    # Phase 287: the per-leader treasure list (List_Treas(ldr,false)).
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_leader(LeaderState(1, 1, "Aldric", HexCoord(0, 0)))
    state.add_item(Treasure.LEADERSHIP_HUMAN, owner_leader_id=1)
    state.add_item(Treasure.WAND_FIREBALL, owner_leader_id=1)

    lines = describe_characters_report(state, 1)

    assert lines[9] == f"Items: {TREASURE_NAME[Treasure.LEADERSHIP_HUMAN]}, {TREASURE_NAME[Treasure.WAND_FIREBALL]}"


def test_describe_characters_report_skill_row_shows_magic_item_ownership_tick_marks():
    # Phase 437: REPORTS.PAS ~lines 862-870 -- ' for exactly one owned
    # ability-boosting item, " for two or more, eating one character off
    # the *next* ability's own number-field width (`space_sub`, clamped to
    # at most 1). Aldric owns 1x Naval item (index 2) and 2x Melee item
    # (index 4), so the tick marks land after Naval's and Melee's values,
    # and Archery's (index 3) and White magic's (index 5) fields each
    # shrink by one character.
    #
    # Phase 534: the displayed numbers themselves now include each item's
    # own effective_skill_level() bonus (Naval 1, Melee 2, both stacking
    # on top of a stored skill of 0) -- this row already reads through
    # effective_skill_level(), so folding item bonuses into that function
    # correctly updates the number alongside the pre-existing tick marks,
    # not just the count itself.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_leader(LeaderState(1, 1, "Aldric", HexCoord(0, 0)))
    state.add_item(Treasure.ABILITY_NAVAL, owner_leader_id=1)
    state.add_item(Treasure.ABILITY_MELEE, owner_leader_id=1)
    state.add_item(Treasure.ABILITY_MELEE, owner_leader_id=1)

    lines = describe_characters_report(state, 1)

    assert lines[7] == "Aldric           0  Unkn  Unkn     Human  1   0 0 1'0 2\" 0 0 0 0 0  0 0 0 0 0"


def test_describe_characters_report_omits_items_line_when_leader_holds_nothing():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_leader(LeaderState(1, 1, "Aldric", HexCoord(0, 0)))

    lines = describe_characters_report(state, 1)

    assert len(lines) == 9  # 7 header lines, name line, aptitude line -- no Items line
    assert not any(line.startswith("Items:") for line in lines)


def test_describe_characters_report_only_lists_items_owned_by_that_leader():
    # Aldric owns nothing; Elena owns the item -- confirms each leader's
    # own Items line (or its absence) is keyed by leader_id, not shared.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_leader(LeaderState(1, 1, "Aldric", HexCoord(0, 0)))
    state.add_leader(LeaderState(2, 1, "Elena", HexCoord(0, 0)))
    state.add_item(Treasure.LEADERSHIP_HUMAN, owner_leader_id=2)

    lines = describe_characters_report(state, 1)

    # Aldric's own two lines (name + aptitude) are immediately followed by
    # Elena's name line, not an Items line -- his own entry has none.
    aldric_index = next(i for i, line in enumerate(lines) if line.startswith("Aldric"))
    assert not lines[aldric_index + 2].startswith("Items:")
    assert f"Items: {TREASURE_NAME[Treasure.LEADERSHIP_HUMAN]}" in lines


# -- Phase 555: "Royal Heir" name substitution (REPORTS.PAS Get_HName) --


def test_describe_characters_report_shows_royal_heir_for_an_unfinalized_heir():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    heir_skills = SkillTable(raw_values=[0] * 31)  # Total_USkill 0, well under 7
    state.add_leader(LeaderState(1, 1, "Aldric", HexCoord(0, 0), is_king=True, is_royal_heir=True, skills=heir_skills))

    lines = describe_characters_report(state, 1)

    assert lines[7].startswith("Royal Heir    ")
    assert "Aldric" not in lines[7]


def test_describe_characters_report_shows_the_real_name_once_finalized():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_leader(LeaderState(1, 1, "Aldric II", HexCoord(0, 0), is_king=True, is_royal_heir=False))

    lines = describe_characters_report(state, 1)

    assert lines[7].startswith("Aldric II     ")


def test_describe_characters_report_shows_the_real_name_once_past_the_skill_threshold():
    # Phase 553's own numeric gate, read here through is_unfinalized_
    # royal_heir(): is_royal_heir can still be True (not yet finalized
    # by create_king()) while Total_USkill has already reached 7.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    trained_skills = SkillTable(raw_values=[0] * 31)
    trained_skills.set_pair_for_ability(Ability.MELEE, skill=7, aptitude=9)
    state.add_leader(
        LeaderState(1, 1, "Aldric", HexCoord(0, 0), is_king=True, is_royal_heir=True, skills=trained_skills)
    )

    lines = describe_characters_report(state, 1)

    assert lines[7].startswith("Aldric        ")


def test_describe_characters_report_non_king_leader_never_shows_royal_heir():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    # is_royal_heir=True on a non-King leader isn't a reachable game
    # state, but the substitution should still key off the flag/
    # threshold alone, not silently assume is_king -- confirms the
    # substitution doesn't accidentally fire for the wrong reason.
    state.add_leader(LeaderState(1, 1, "Kwoth", HexCoord(0, 0), is_king=False, is_royal_heir=False))

    lines = describe_characters_report(state, 1)

    assert lines[7].startswith("Kwoth         ")


# -- Phase 216: describe_adventure_report() -- the "ADVENTURE" section --


_ADVENTURE_OPENING = (
    "O Luminous One, adventure awaits thee and thy companions at every corner of "
    "the globe!  Fearsome monsters lurk in their cavernous hidden lairs by day and "
    "terrorize the populace by night.  Here are these lairs:"
)
_ADVENTURE_COLUMN_HEADER = "Province             %Exp  Features and F#     Monster         Special"
# Phase 434: the real 27-space column-blank width (`REPORTS.PAS`
# `Check_None`'s own `'':27`), replacing Phase 430's unsourced 2-space
# indent -- see turn_report.py's own `_ADVENTURE_BLANK_PROVINCE_COLUMNS`.
_ADVENTURE_UNKNOWN_RICHES = " " * 27 + "/Guarding unknown riches"


class _AlwaysTrueRandom(random.Random):
    """Forces the Phase 430 treasure-reveal roll to always succeed."""

    def random(self) -> float:
        return 0.0


class _AlwaysFalseRandom(random.Random):
    """Forces the Phase 430 treasure-reveal roll to always fail."""

    def random(self) -> float:
        return 0.999


def test_describe_adventure_report_opening_lines():
    state = GameState()

    lines = describe_adventure_report(state, 1, random.Random(0))

    assert lines[0] == "ADVENTURE"
    assert lines[1] == _ADVENTURE_OPENING
    assert lines[2] == _ADVENTURE_COLUMN_HEADER


def test_describe_adventure_report_no_discovered_features_renders_none_at_present():
    state = GameState()
    state.add_feature(Feature(1, HexCoord(0, 0), FeatureType.CAVE, guardian_monster=Monster.SWORDSMAN))

    lines = describe_adventure_report(state, 1, random.Random(0))

    assert lines[3:] == ["None at present"]


def test_describe_adventure_report_lists_a_discovered_feature():
    state = GameState()
    state.add_province(ProvinceState(HexCoord(3, 5), None, Race.HUMAN, name="Mongu"))
    state.provinces[HexCoord(3, 5)].explored_percent_by_kingdom[1] = 100
    state.add_feature(
        Feature(
            2,
            HexCoord(3, 5),
            FeatureType.CAVE,
            guardian_monster=Monster.SWORDSMAN,
            discovered_by_kingdom={1: 3},
        )
    )

    lines = describe_adventure_report(state, 1, random.Random(0))

    assert lines[3:] == [
        "Mongu           305  100  Cave             2  Swordsman       ",
        _ADVENTURE_UNKNOWN_RICHES,
    ]


def test_describe_adventure_report_looted_feature_shows_sacked_and_looted():
    state = GameState()
    state.add_feature(
        Feature(3, HexCoord(1, 1), FeatureType.CRYPT, guardian_monster=Monster.GARGOYLE, looted=True, discovered_by_kingdom={1: 3})
    )

    lines = describe_adventure_report(state, 1, random.Random(0))

    assert lines[3:] == [
        "(1, 1)          101    0  Crypt            3  sacked &looted  ",
    ]


def test_describe_adventure_report_discovery_level_1_renders_question_mark():
    state = GameState()
    state.add_feature(
        Feature(4, HexCoord(2, 2), FeatureType.TOMB, guardian_monster=Monster.MUMMY, discovered_by_kingdom={1: 1})
    )

    lines = describe_adventure_report(state, 1, random.Random(0))

    assert lines[3:] == [
        "(2, 2)          202    0  Tomb             4  Mummy               ?",
        _ADVENTURE_UNKNOWN_RICHES,
    ]


def test_describe_adventure_report_undiscovered_feature_is_excluded():
    state = GameState()
    state.add_feature(Feature(5, HexCoord(4, 4), FeatureType.DUNGEON, guardian_monster=Monster.TROLL))

    lines = describe_adventure_report(state, 1, random.Random(0))

    assert lines[3:] == ["None at present"]


def test_describe_adventure_report_only_shows_this_kingdoms_own_discovery():
    state = GameState()
    state.add_feature(
        Feature(6, HexCoord(0, 0), FeatureType.CAVE, guardian_monster=Monster.GIANT, discovered_by_kingdom={2: 3})
    )

    lines = describe_adventure_report(state, 1, random.Random(0))

    assert lines[3:] == ["None at present"]


def test_describe_adventure_report_monster_name_prefix_is_stripped():
    state = GameState()
    state.add_feature(
        Feature(7, HexCoord(0, 0), FeatureType.PET_FOREST, guardian_monster=Monster.GI_EAGLE, discovered_by_kingdom={1: 3})
    )

    lines = describe_adventure_report(state, 1, random.Random(0))

    assert lines[3:] == [
        "(0, 0)          0    0  Petrified Fores  7  Eagle           ",
        _ADVENTURE_UNKNOWN_RICHES,
    ]


def test_describe_adventure_report_no_guardian_recorded_omits_monster_segment():
    state = GameState()
    state.add_feature(Feature(8, HexCoord(0, 0), FeatureType.CAVE, discovered_by_kingdom={1: 3}))

    lines = describe_adventure_report(state, 1, random.Random(0))

    assert lines[3:] == [
        "(0, 0)          0    0  Cave             8                  ",
        _ADVENTURE_UNKNOWN_RICHES,
    ]


def test_describe_adventure_report_sorts_provinces_then_features_by_id():
    state = GameState()
    state.add_feature(
        Feature(2, HexCoord(1, 1), FeatureType.CAVE, guardian_monster=Monster.GIANT, discovered_by_kingdom={1: 3})
    )
    state.add_feature(
        Feature(1, HexCoord(0, 0), FeatureType.TOMB, guardian_monster=Monster.MUMMY, discovered_by_kingdom={1: 3})
    )
    state.add_feature(
        Feature(3, HexCoord(0, 0), FeatureType.CRYPT, guardian_monster=Monster.GHOST, discovered_by_kingdom={1: 3})
    )

    lines = describe_adventure_report(state, 1, random.Random(0))

    assert lines[3:] == [
        "(0, 0)          0    0  Tomb             1  Mummy           ",
        _ADVENTURE_UNKNOWN_RICHES,
        "                           Crypt            3  Ghost           ",
        _ADVENTURE_UNKNOWN_RICHES,
        "(1, 1)          101    0  Cave             2  Giant           ",
        _ADVENTURE_UNKNOWN_RICHES,
    ]


def test_describe_adventure_report_reveals_treasure_when_the_roll_succeeds():
    # Phase 430: a feature with a real Treasure gets the revealed line
    # instead of "Guarding unknown riches" when the reveal roll succeeds.
    state = GameState()
    state.add_feature(
        Feature(
            9,
            HexCoord(0, 0),
            FeatureType.CRYPT,
            guardian_monster=Monster.GARGOYLE,
            discovered_by_kingdom={1: 3},
            treasure=Treasure.GOLD_HOARD_LARGE,
        )
    )

    lines = describe_adventure_report(state, 1, _AlwaysTrueRandom())

    assert lines[3:] == [
        "(0, 0)          0    0  Crypt            9  Gargoyle        ",
        "                           /Large Hoard of Gold (#9): 10-25 gold",
    ]


def test_describe_adventure_report_hides_treasure_when_the_roll_fails():
    state = GameState()
    state.add_feature(
        Feature(
            10,
            HexCoord(0, 0),
            FeatureType.CRYPT,
            guardian_monster=Monster.GARGOYLE,
            discovered_by_kingdom={1: 3},
            treasure=Treasure.GOLD_HOARD_LARGE,
        )
    )

    lines = describe_adventure_report(state, 1, _AlwaysFalseRandom())

    assert lines[3:] == [
        "(0, 0)          0    0  Crypt           10  Gargoyle        ",
        _ADVENTURE_UNKNOWN_RICHES,
    ]


def test_describe_adventure_report_reveals_a_magic_item_treasure():
    state = GameState()
    state.add_feature(
        Feature(
            11,
            HexCoord(0, 0),
            FeatureType.PYRAMID,
            guardian_monster=Monster.LICH,
            discovered_by_kingdom={1: 3},
            treasure=Treasure.WAND_ILLUS_ARMIES,
        )
    )

    lines = describe_adventure_report(state, 1, _AlwaysTrueRandom())

    assert lines[3:] == [
        "(0, 0)          0    0  Pyramid         11  Lich            ",
        '                           /Reflector of Armies (#11): Cast "Phantasmal Armies" at skill-2',
    ]


def test_describe_adventure_report_looted_feature_never_shows_a_treasure_line():
    state = GameState()
    state.add_feature(
        Feature(
            12,
            HexCoord(0, 0),
            FeatureType.CRYPT,
            guardian_monster=Monster.GARGOYLE,
            looted=True,
            discovered_by_kingdom={1: 3},
            treasure=Treasure.GOLD_HOARD_LARGE,
        )
    )

    lines = describe_adventure_report(state, 1, _AlwaysTrueRandom())

    assert lines[3:] == [
        "(0, 0)          0    0  Crypt           12  sacked &looted  ",
    ]


# -- Phase 215: compose_letter_report() -- top-level per-kingdom letter assembler --


def test_compose_letter_report_stitches_all_four_wired_sections_in_the_real_order():
    state = _armies_state()
    state.provinces[HexCoord(0, 0)].explored_percent_by_kingdom[1] = 100
    state.add_leader(LeaderState(1, 1, "Aldric", HexCoord(0, 0), is_king=True))
    state.add_leader(LeaderState(32, 1, "Borin", HexCoord(0, 0)))
    state.add_leader(LeaderState(40, 1, "Elena", HexCoord(0, 0)))
    state.add_army(ArmyState(1, 1, ArmyType.BOWMEN, Quality.AVERAGE, HexCoord(0, 0)))
    king_result = HireExecutionResult(HireRequest(hero_id=32, gold_offer=2), hired=True)
    hero_result = HireExecutionResult(HireRequest(hero_id=40, gold_offer=1), hired=True)
    results = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.HIRE, result=king_result, error=None),
        PhaseDispatchResult(leader_id=32, segment_index=0, phase_label="P0", action=ActionCode.HIRE, result=hero_result, error=None),
    ]

    lines = compose_letter_report(results, state, 1, ScriptedRandom([0.1] * 20, choice_indices=[0, 0]))

    assert lines == [
        "ACTION REPORT",
        "",
        "Aldric spoke to Borin and convinced Borin to pledge Borin's allegiance to Aldric.",
        "",
        "",
        "LETTER REPORTS",
        "",
        "O King of Kings, thy heroes have travelled around the globe in "
        "search of adventure and conquest.  I have faithfully kept their "
        "correspondence, and now I present it to thee:",
        "From: Borin",
        "To: Aldric",
        "Honored Sovereign,",
        # Phase 851: Borin's own Hire order names his real King (Aldric).
        "Borin spoke to Elena and convinced Elena to pledge Elena's allegiance to Aldric.",
        "Thy humble servant,   Borin",
        "",
        "",
        "STATE OF THE NATION:",
        "",
        "My lord and sovereign, greatest of Kings, I humbly beg thy leave to make "
        "report of matters of this Kingdom that may concern thy divine majesty.",
        "",
        "",
        "DIPLOMACY",
        "",
        "My lord, the following Kings have wisely allied with thy ever-victorious majesty:",
        "None at present",
        "My lord, the following Kings are foolishly at war with thy ever-victorious majesty:",
        "None at present",
        "My lord, the following Kings are cautiously neutral with thy ever-victorious majesty:",
        "None at present",
        "",
        "",
        "FINANCES",
        "",
        "O Great One, I submit for thy examination the following figures "
        "concerning the finances of our great nation:",
        "here is the financial report for Aldric's kingdom: ",
        "Gold in treasury:   0",
        "Expected Revenues:   0",
        "Expected Expenses:   6",
        "Our Kingdom is also benefited by the following Discoveries of the Sages:",
        "None at present",
        "Aldric was left with 0 gold in the treasury.",
        "",
        "",
        "PROVINCES",
        "",
        "O superfluous one, I have kept well a list of all provinces which have had "
        "the wisdom to submit to thy yoke.  Here, then, are the lands of thy Empire:",
        "                                                    Recruiting Types:",
        "Province            Tax   Race   Terrain  Expl%     Type 1     Type 2",
        "Capital City              Human    Plain     0%                      ",
        "",
        "",
        "  Sire, our royal scribe has drawn up a map of all neighboring lands: ",
        "",
        "        _Capital_(0000)_",
        "        _ _ Aldric(1) __",
        "        _   _Humans _  _",
        "        _ _   _   _   __",
        "        _   _Tax: 0 _  _",
        "        ____0%_Expl.____",
        "",
        "Key:   _ Plains   + Forest   & Jungle   ^ Mountain   . Desert     Sea",
        "    In each province, the name and I.D. number of the province",
        "  are listed above the ruler I.D and name.",
        "",
        "",
        "CHARACTERS",
        "",
        "My Lord, Great indeed are the leaders of our proud kingdom.  Though thee "
        "knows them well, I list them here for thy consideration (the first line "
        "shows pay and abilities; line 2 shows move precedence and aptitude.)",
        "",
        "                                         Pay Modified Skills/Aptitudes:",
        "             Province                     /  Combat     Magical    Other",
        "Character      Loc Align  Temp M/F  Race Ini TaMaNaArMe WhNeElPsIl DrThExSpSa",
        " " * 77,
        "Aldric           0  Unkn  Unkn     Human  0   0 0 0 0 0  0 0 0 0 0  0 0 0 0 0",
        " 0   0 0 0 0 0  0 0 0 0 0  0 0 0 0 0",
        "Borin            0  Unkn  Unkn     Human  2   0 0 0 0 0  0 0 0 0 0  0 0 0 0 0",
        " 0   0 0 0 0 0  0 0 0 0 0  0 0 0 0 0",
        "Elena            0  Unkn  Unkn     Human  2   0 0 0 0 0  0 0 0 0 0  0 0 0 0 0",
        " 0   0 0 0 0 0  0 0 0 0 0  0 0 0 0 0",
        "",
        "",
        "ARMIES",
        "",
        "Excellence, thy armies have trained hard and honed their weapons to a fine "
        "edge.  Proudly they serve thy imperial majesty, and they await thy commands.",
        "                                                              Normal  Modified",
        "Province          Leader         Designation           Race   Quality  Quality",
        "Capital City      Garrison       Bowmen                Human  Average  Veteran",
        "",
        "",
        "IMPERIAL OFFICE REPORT",
        "",
        "Into thy heroic dreams cometh an apparition heaven-sent, to speak to thee of thy progress in thy ambitions "
        "for Imperial Office.  It is not for mortal Kings to know who rivals them for high offices, but the Divine "
        "One will allow you to know thy place in the standings, and how thee compares to thy fiercest foreign rival "
        'for each office (shown under "Riv%" as a percentage: your points divided by your rival\'s points, times 100.)',
        "World Emperor             Aldric (0 points, rank 1, None)",
        "Esteemed High Chancellor  Aldric (0 points, rank 1, None)",
        "                          Borin (0 points, rank 1, None)",
        "Imperial Treasurer        Aldric (0 points, rank 1, None)",
        "                          Borin (0 points, rank 1, None)",
        "Imperial Grand Marshal    Aldric (0 points, rank 1, None)",
        "                          Borin (0 points, rank 1, None)",
        "Imperial Grand Admiral    Aldric (0 points, rank 1, None)",
        "                          Borin (0 points, rank 1, None)",
        "Lord High Defender        Aldric (0 points, rank 1, None)",
        "                          Borin (0 points, rank 1, None)",
        "High Priest Palatine      Aldric (0 points, rank 1, None)",
        "                          Borin (0 points, rank 1, None)",
        "Arch-Mage Palatine        Aldric (0 points, rank 1, None)",
        "                          Borin (0 points, rank 1, None)",
        "King of Pain              None at present",
        "Prince of Thieves         None at present",
        "Savior of Humankind       None at present",
        "First Elder of Elvenkind  None at present",
        "King Under the Mountain   None at present",
        "Khan of the Orcish Hordes None at present",
        "Dragon Lord               None at present",
        "Ace of Eagles             None at present",
        "Whale League Commissioner None at present",
        "King of Atlantis          None at present",
        "Tsar of the Trees         None at present",
        "High Mucky-Muck of Trolls None at present",
        "Lord of Lycanthropes      None at present",
        "Divine Archangel          None at present",
        "Most Blessed of Kings     None at present",
        "Great Druid of Life       None at present",
        "Defender of Freedom       None at present",
        "Warlock of the Pagan Gods None at present",
        "Angel of Death            None at present",
        "Chief of Staff            None at present",
        "Silver Tongue             None at present",
        "Master of Elements        None at present",
        "Amazing Houdini           None at present",
        "Sorceror of Black Magic   None at present",
        "Master Mind               None at present",
        "Ranger of the Plains      None at present",
        "Desert Rat                None at present",
        "Lord of the Jungle        None at present",
        "Warden of the Forests     None at present",
        "Mountain Man              None at present",
        "Ruler of the Waves        None at present",
        "Fool of Battles           None at present",
        "Curator of Artifacts      None at present",
        "Professor Whizdumb        None at present",
        "Grandfather of Assassins  None at present",
        "Captain of the Musketeers None at present",
        "Air Force Commander       None at present",
        "King of Cowards           None at present",
        "Bravest of the Brave      None at present",
        "Royal Air Force           None at present",
        "Praetorian Guard          None at present",
        "Imperial Flag Squadron    None at present",
        "",
        "",
        "ADVENTURE",
        "",
        "O Luminous One, adventure awaits thee and thy companions at every corner of "
        "the globe!  Fearsome monsters lurk in their cavernous hidden lairs by day and "
        "terrorize the populace by night.  Here are these lairs:",
        "Province             %Exp  Features and F#     Monster         Special",
        "None at present",
        "",
        "",
        "GENERAL INTELLIGENCE REPORT",
        "",
        "None at present",
        "",
        "",
        "END MOVES REPORT",
    ]


def test_compose_letter_report_omits_action_report_when_this_kingdom_has_no_king():
    state = _armies_state()

    lines = compose_letter_report([], state, 1, ScriptedRandom([]))

    assert "ACTION REPORT" not in lines
    assert lines[0] == "LETTER REPORTS"


def test_compose_letter_report_blank_line_spacing_matches_the_real_pr1_pr2_idiom():
    # Phase 431: no leading blank lines before the very first section (the
    # real PR2 is "two blank lines before a header", not "before the
    # report"), exactly one blank line right after every header (PR1,
    # REPORTS.PAS's own Expand_Write never emits its own trailing blank),
    # and exactly two blank lines between every pair of sections (PR2).
    state = _armies_state()

    lines = compose_letter_report([], state, 1, ScriptedRandom([]))

    assert lines[0] == "LETTER REPORTS"
    assert lines[1] == ""  # PR1 right after the first header
    diplomacy_index = lines.index("DIPLOMACY")
    assert lines[diplomacy_index - 1] == ""
    assert lines[diplomacy_index - 2] == ""
    assert lines[diplomacy_index - 3] != ""  # exactly two, not more
    assert lines[diplomacy_index + 1] == ""  # PR1 right after DIPLOMACY too


def test_compose_letter_report_filters_results_to_only_this_kingdoms_own_leaders():
    state = _armies_state()
    state.add_leader(LeaderState(1, 1, "Aldric", HexCoord(0, 0), is_king=True))
    state.add_kingdom(KingdomState(2, "Otherland", Race.ELVEN, Alignment.NEUTRAL, HexCoord(1, 1)))
    state.add_leader(LeaderState(9, 2, "Kwoth", HexCoord(1, 1)))
    other_kingdom_result = FireExecutionResult(FireRequest(hero_id=9), fired=True)
    results = [
        PhaseDispatchResult(
            leader_id=9, segment_index=0, phase_label="P0", action=ActionCode.FIRE, result=other_kingdom_result, error=None
        )
    ]

    lines = compose_letter_report(results, state, 1, ScriptedRandom([]))

    assert "ACTION REPORT" not in lines
    assert lines[0] == "LETTER REPORTS"


def test_compose_letter_report_narrates_a_non_king_leader_who_dies_this_turn():
    # Phase 614: before this fix, both compose_letter_report()'s own
    # kingdom_leader_ids and describe_letter_reports()'s own separately-
    # computed other_leader_ids only scanned state.leaders (live), so a
    # Hero who died from their own action this turn (state.remove_leader()
    # already ran, same timing as a real end-to-end run) was silently
    # dropped from their own kingdom's letter entirely -- not just the
    # death sentence, the whole letter.
    state = GameState()
    location = HexCoord(0, 0)
    state.add_kingdom(KingdomState(1, "Kingdom A", Race.HUMAN, Alignment.NEUTRAL, location))
    state.add_kingdom(KingdomState(2, "Kingdom B", Race.HUMAN, Alignment.NEUTRAL, location))
    state.add_leader(LeaderState(1, 1, "TheKing", location, is_king=True))
    state.add_leader(LeaderState(5, 1, "Guerin", location, is_king=False))
    state.add_leader(LeaderState(2, 2, "Borin", location, is_king=True))
    state.remove_leader(5)
    result = ChallengeExecutionResult(
        accepted=True,
        combat_occurred=True,
        winner_leader_id=2,
        loser_leader_id=5,
        loser_killed=True,
        melee_swings=(MeleeSwing(attacker="b", hit=True, damage=6),),
        request=ChallengeRequest(target_character_id=2, unconfirmed_extra0=0),
    )
    results = [
        PhaseDispatchResult(leader_id=5, segment_index=0, phase_label="P0", action=ActionCode.CHALLENGE, result=result, error=None)
    ]

    # Phase 793: one more choice_indices entry for the new, unconditional
    # ENCATT.X opening line. Phase 859: two more for THATT.X/THFAIL.X.
    lines = compose_letter_report(results, state, 1, ScriptedRandom([0.1] * 40, choice_indices=[0, 0, 0, 0, 0, 0, 0]))

    assert "From: Guerin" in lines
    assert "Borin assailed Guerin and inflicted 6 damage points." in lines
    assert "and so it was that Guerin met Guerin's unseemly end." in lines


def test_compose_letter_report_all_four_wired_sections_present_even_when_empty():
    state = _armies_state()
    state.provinces[HexCoord(0, 0)].explored_percent_by_kingdom[1] = 100

    lines = compose_letter_report([], state, 1, ScriptedRandom([]))

    assert lines == [
        "LETTER REPORTS",
        "",
        "There are no letters from anyone at this time.",
        "",
        "",
        "STATE OF THE NATION:",
        "",
        "My lord and sovereign, greatest of Kings, I humbly beg thy leave to make "
        "report of matters of this Kingdom that may concern thy divine majesty.",
        "",
        "",
        "DIPLOMACY",
        "",
        "My lord, the following Kings have wisely allied with thy ever-victorious majesty:",
        "None at present",
        "My lord, the following Kings are foolishly at war with thy ever-victorious majesty:",
        "None at present",
        "My lord, the following Kings are cautiously neutral with thy ever-victorious majesty:",
        "None at present",
        "",
        "",
        "FINANCES",
        "",
        "O Great One, I submit for thy examination the following figures "
        "concerning the finances of our great nation:",
        "here is the financial report for Testland's kingdom: ",
        "Gold in treasury:   0",
        "Expected Revenues:   0",
        "Expected Expenses:   0",
        "Our Kingdom is also benefited by the following Discoveries of the Sages:",
        "None at present",
        "Testland was left with 0 gold in the treasury.",
        "",
        "",
        "PROVINCES",
        "",
        "O superfluous one, I have kept well a list of all provinces which have had "
        "the wisdom to submit to thy yoke.  Here, then, are the lands of thy Empire:",
        "                                                    Recruiting Types:",
        "Province            Tax   Race   Terrain  Expl%     Type 1     Type 2",
        "Capital City              Human    Plain     0%                      ",
        "",
        "",
        "  Sire, our royal scribe has drawn up a map of all neighboring lands: ",
        "",
        "        _Capital_(0000)_",
        "        _ _  Unowned  __",
        "        _   _Humans _  _",
        "        _ _   _   _   __",
        "        _   _Tax: 0 _  _",
        "        ____0%_Expl.____",
        "",
        "Key:   _ Plains   + Forest   & Jungle   ^ Mountain   . Desert     Sea",
        "    In each province, the name and I.D. number of the province",
        "  are listed above the ruler I.D and name.",
        "",
        "",
        "CHARACTERS",
        "",
        "My Lord, Great indeed are the leaders of our proud kingdom.  Though thee "
        "knows them well, I list them here for thy consideration (the first line "
        "shows pay and abilities; line 2 shows move precedence and aptitude.)",
        "",
        "                                         Pay Modified Skills/Aptitudes:",
        "             Province                     /  Combat     Magical    Other",
        "Character      Loc Align  Temp M/F  Race Ini TaMaNaArMe WhNeElPsIl DrThExSpSa",
        " " * 77,
        "None at present",
        "",
        "",
        "ARMIES",
        "",
        "Excellence, thy armies have trained hard and honed their weapons to a fine "
        "edge.  Proudly they serve thy imperial majesty, and they await thy commands.",
        "None at present",
        "",
        "",
        "IMPERIAL OFFICE REPORT",
        "",
        "Into thy heroic dreams cometh an apparition heaven-sent, to speak to thee of thy progress in thy ambitions "
        "for Imperial Office.  It is not for mortal Kings to know who rivals them for high offices, but the Divine "
        "One will allow you to know thy place in the standings, and how thee compares to thy fiercest foreign rival "
        'for each office (shown under "Riv%" as a percentage: your points divided by your rival\'s points, times 100.)',
        "World Emperor             None at present",
        "Esteemed High Chancellor  None at present",
        "Imperial Treasurer        None at present",
        "Imperial Grand Marshal    None at present",
        "Imperial Grand Admiral    None at present",
        "Lord High Defender        None at present",
        "High Priest Palatine      None at present",
        "Arch-Mage Palatine        None at present",
        "King of Pain              None at present",
        "Prince of Thieves         None at present",
        "Savior of Humankind       None at present",
        "First Elder of Elvenkind  None at present",
        "King Under the Mountain   None at present",
        "Khan of the Orcish Hordes None at present",
        "Dragon Lord               None at present",
        "Ace of Eagles             None at present",
        "Whale League Commissioner None at present",
        "King of Atlantis          None at present",
        "Tsar of the Trees         None at present",
        "High Mucky-Muck of Trolls None at present",
        "Lord of Lycanthropes      None at present",
        "Divine Archangel          None at present",
        "Most Blessed of Kings     None at present",
        "Great Druid of Life       None at present",
        "Defender of Freedom       None at present",
        "Warlock of the Pagan Gods None at present",
        "Angel of Death            None at present",
        "Chief of Staff            None at present",
        "Silver Tongue             None at present",
        "Master of Elements        None at present",
        "Amazing Houdini           None at present",
        "Sorceror of Black Magic   None at present",
        "Master Mind               None at present",
        "Ranger of the Plains      None at present",
        "Desert Rat                None at present",
        "Lord of the Jungle        None at present",
        "Warden of the Forests     None at present",
        "Mountain Man              None at present",
        "Ruler of the Waves        None at present",
        "Fool of Battles           None at present",
        "Curator of Artifacts      None at present",
        "Professor Whizdumb        None at present",
        "Grandfather of Assassins  None at present",
        "Captain of the Musketeers None at present",
        "Air Force Commander       None at present",
        "King of Cowards           None at present",
        "Bravest of the Brave      None at present",
        "Royal Air Force           None at present",
        "Praetorian Guard          None at present",
        "Imperial Flag Squadron    None at present",
        "",
        "",
        "ADVENTURE",
        "",
        "O Luminous One, adventure awaits thee and thy companions at every corner of "
        "the globe!  Fearsome monsters lurk in their cavernous hidden lairs by day and "
        "terrorize the populace by night.  Here are these lairs:",
        "Province             %Exp  Features and F#     Monster         Special",
        "None at present",
        "",
        "",
        "GENERAL INTELLIGENCE REPORT",
        "",
        "None at present",
        "",
        "",
        "END MOVES REPORT",
    ]


def test_compose_letter_report_always_ends_with_end_moves_report():
    # Phase 1034: confirmed present, as the letter's own final line, in
    # all 46 of tests/fixtures/reports/G6/'s real SE6__T*.K* samples --
    # even the thinnest "missed the turn deadline" report still ends
    # with it (SE6__T2.K0 line 289).
    state = _armies_state()

    lines = compose_letter_report([], state, 1, ScriptedRandom([]))

    assert lines[-1] == "END MOVES REPORT"
    assert lines[-2] == ""
    assert lines[-3] == ""
    assert lines[-4] != ""  # exactly two blank lines, not more


def test_compose_letter_report_forwards_board_width_to_action_report_and_letters():
    state = _armies_state()
    state.add_leader(LeaderState(1, 1, "Aldric", HexCoord(0, 0), is_king=True))
    state.add_leader(LeaderState(32, 1, "Borin", HexCoord(0, 0)))
    feature = Feature(feature_id=5, coord=HexCoord(3, 4), kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE)
    state.add_feature(feature)
    king_rumor = Rumor(
        rumor_id=state.new_rumor_id(),
        kingdom_id=1,
        leader_id=1,
        source_action=ActionCode.EXPLORE,
        content=RumorContent.FEATURE_AND_MONSTER,
        feature_id=5,
        is_true=True,
        described_coord=HexCoord(3, 4),
        described_monster=Monster.GARGOYLE,
    )
    state.add_rumor(king_rumor)
    hero_rumor = Rumor(
        rumor_id=state.new_rumor_id(),
        kingdom_id=1,
        leader_id=32,
        source_action=ActionCode.EXPLORE,
        content=RumorContent.FEATURE_AND_MONSTER,
        feature_id=5,
        is_true=True,
        described_coord=HexCoord(3, 4),
        described_monster=Monster.GARGOYLE,
    )
    state.add_rumor(hero_rumor)
    explore_result = ExploreResult(new_percent=50, delta_applied=50, fully_explored=False)
    results = [
        PhaseDispatchResult(
            leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.EXPLORE, result=explore_result, error=None
        ),
        PhaseDispatchResult(
            leader_id=32, segment_index=0, phase_label="P0", action=ActionCode.EXPLORE, result=explore_result, error=None
        ),
    ]

    lines = compose_letter_report(results, state, 1, ScriptedRandom([0.1] * 40, choice_indices=[0, 0, 0, 0]), board_width=10)

    action_start = lines.index("ACTION REPORT")
    letters_start = lines.index("LETTER REPORTS")
    assert any("heard" in line for line in lines[action_start:letters_start])
    letters_end = lines.index("DIPLOMACY")
    assert any("heard" in line for line in lines[letters_start:letters_end])


# -- Phase 229: describe_alignment_victory_point_reduction() -- ALIGNMENT REDUCTION --


def test_describe_alignment_reduction_empty_before_any_emperor_elected():
    state = _armies_state()

    assert describe_alignment_victory_point_reduction(state) == []


def test_describe_alignment_reduction_lists_every_covered_alignment():
    state = _armies_state()
    state.kingdoms[1].alignment = Alignment.GOOD
    state.emperor_kingdom_id = 1

    lines = describe_alignment_victory_point_reduction(state)

    assert lines[0] == "ALIGNMENT REDUCTION"
    assert "Divine: -20%" in lines  # Divine=0, Good=1, distance 1 x 20%
    assert "Good: -0%" in lines  # the Emperor's own alignment -- distance 0
    assert "Druidic: -15%" in lines  # Druid=2, distance 1 x 15%
    assert "Pagan: -45%" in lines  # Pagan=4, distance 3 x 15%
    # Phase 558: Anti-Holy is now covered too (a real, previously-missing
    # OUTLOOK_REDUCTION entry) -- capped-at-Hellish distance from Good(1)
    # is 5, Anti-Holy's own 20%-per-step row -> 20 x 5 = 100%.
    assert "Anti-Holy: -100%" in lines
    # Mechanical/Special stay excluded -- confirmed never a selectable
    # Kingdom Alignment (_ORDINARY_ALIGNMENTS), not a formula gap.
    assert "Mechanical" not in "".join(lines)
    assert "Special" not in "".join(lines)


def test_describe_alignment_reduction_matches_the_rulebooks_own_worked_example():
    state = _armies_state()
    state.kingdoms[1].alignment = Alignment.GOOD
    state.emperor_kingdom_id = 1

    lines = describe_alignment_victory_point_reduction(state)

    assert "Pagan: -45%" in lines  # 15% x 3 ordinal positions from Good


def test_compose_letter_report_includes_alignment_reduction_once_emperor_elected():
    state = _armies_state()
    state.emperor_kingdom_id = 1

    lines = compose_letter_report([], state, 1, ScriptedRandom([]))

    assert "ALIGNMENT REDUCTION" in lines


def test_compose_letter_report_omits_alignment_reduction_before_any_emperor_elected():
    state = _armies_state()

    lines = compose_letter_report([], state, 1, ScriptedRandom([]))

    assert "ALIGNMENT REDUCTION" not in lines


# -- Phase 559: describe_final_standings_report() -- FINAL STANDINGS --


def test_describe_final_standings_report_empty_before_any_emperor_elected():
    state = _armies_state()

    assert describe_final_standings_report(state) == []


def test_describe_final_standings_report_lists_rank_king_kingdom_and_points():
    # Same fixture shape as test_final_standings.py's own
    # test_compose_final_standings_report_matches_the_individual_functions:
    # Kingdom 1's King holds Emperor (20, self, no discount) and
    # Treasurer (10, treasury 7 > 0) -- 30.0 total. Kingdom 2 has
    # nothing, no King at all -- 0.0.
    state = _armies_state()
    state.provinces[HexCoord(0, 0)].tax = 10
    state.add_leader(LeaderState(1, 1, "Aldric", HexCoord(0, 0), is_king=True))
    state.kingdoms[1].treasury = 7
    state.emperor_kingdom_id = 1
    state.add_kingdom(KingdomState(2, "Farland", Race.HUMAN, Alignment.EVIL, HexCoord(1, 1)))

    lines = describe_final_standings_report(state)

    assert lines[0] == "FINAL STANDINGS"
    assert "1. Aldric of Testland: 30 Victory Points" in lines
    assert "2. no King of Farland: 0 Victory Points" in lines


def test_describe_final_standings_report_formats_fractional_points():
    # Kingdom 1 (Evil), King Vraxis, wins Treasurer (highest treasury,
    # 7 > Kingdom 2's 0) while Kingdom 2 (Good) is the actual elected
    # Emperor -- Office.EMPEROR is special-cased to always resolve to
    # the elected Emperor's own King (turn/office_holder.py
    # resolve_office_holder()), so Kingdom 1 never holds it here and its
    # own Alignment distance from the Emperor genuinely discounts its
    # Treasurer points: Evil's own 12%-per-step row x capped distance 4
    # from Good = 48% discount, 10 * (1 - 0.48) = 5.2 -- a real
    # non-integer case _format_victory_points() must render as "5.2",
    # not "5.2000000000000006" or "5.0".
    state = _armies_state()
    state.kingdoms[1].alignment = Alignment.EVIL
    state.add_leader(LeaderState(1, 1, "Vraxis", HexCoord(0, 0), is_king=True))
    state.kingdoms[1].treasury = 7
    state.add_kingdom(KingdomState(2, "Farland", Race.HUMAN, Alignment.GOOD, HexCoord(1, 1)))
    state.add_leader(LeaderState(2, 2, "Aldric", HexCoord(1, 1), is_king=True))
    state.emperor_kingdom_id = 2

    lines = describe_final_standings_report(state)

    assert any(line.startswith("2. Vraxis of Testland: 5.2 Victory Points") for line in lines)


def test_describe_final_standings_report_announces_valhalla_qualifiers():
    state = _armies_state()
    state.provinces[HexCoord(0, 0)].tax = 10
    state.add_leader(LeaderState(1, 1, "Aldric", HexCoord(0, 0), is_king=True))
    state.kingdoms[1].treasury = 7
    state.emperor_kingdom_id = 1  # kingdom_points/individual_king_points both 30.0, clears >= 20

    lines = describe_final_standings_report(state)

    assert any(
        line == (
            "Aldric of Testland has earned enough Victory Points to enter Valhalla -- "
            "write to the GM if you wish to induct them, specifying which item Aldric held on the last turn."
        )
        for line in lines
    )


def test_describe_final_standings_report_announces_all_star_qualifiers():
    # Phase 652: kingdom_points() == 30.0 here clears the real >= 7.5
    # all-star threshold (same fixture the Valhalla test above already
    # uses, which separately clears its own >= 20 threshold).
    state = _armies_state()
    state.provinces[HexCoord(0, 0)].tax = 10
    state.add_leader(LeaderState(1, 1, "Aldric", HexCoord(0, 0), is_king=True))
    state.kingdoms[1].treasury = 7
    state.emperor_kingdom_id = 1

    lines = describe_final_standings_report(state)

    assert "Aldric of Testland has qualified for an all-star game of Adventurer-Kings." in lines


def test_describe_final_standings_report_no_all_star_line_below_threshold():
    state = _armies_state()
    state.add_leader(LeaderState(1, 1, "Aldric", HexCoord(0, 0), is_king=True))
    state.emperor_kingdom_id = 1
    state.add_kingdom(KingdomState(2, "Farland", Race.HUMAN, Alignment.EVIL, HexCoord(1, 1)))
    state.add_leader(LeaderState(2, 2, "Vraxis", HexCoord(1, 1), is_king=True))

    lines = describe_final_standings_report(state)

    assert not any("Vraxis" in line and "all-star" in line for line in lines)


def test_describe_final_standings_report_no_valhalla_line_below_threshold():
    # Kingdom 1 is the elected Emperor (an automatic, undiscounted 20
    # office points -- enough to qualify on its own) so the Valhalla
    # gate itself is exercised; Kingdom 2's own King holds no office at
    # all (0 points, not first place either) and must not get a line.
    state = _armies_state()
    state.add_leader(LeaderState(1, 1, "Aldric", HexCoord(0, 0), is_king=True))
    state.emperor_kingdom_id = 1
    state.add_kingdom(KingdomState(2, "Farland", Race.HUMAN, Alignment.EVIL, HexCoord(1, 1)))
    state.add_leader(LeaderState(2, 2, "Vraxis", HexCoord(1, 1), is_king=True))

    lines = describe_final_standings_report(state)

    assert not any("Vraxis" in line and "Valhalla" in line for line in lines)


# -- Phase 652: describe_election_status_report() -- ELECTION STATUS --


def test_describe_election_status_report_empty_when_nothing_applies():
    # Turn 1 (threshold hasn't decayed) and no tax base at all (world_
    # total == 0, so the alignment vote-share line can't compute either).
    state = _armies_state()

    lines = describe_election_status_report(state, 1)

    assert lines == []


def test_describe_election_status_report_threshold_hint_after_turn_24():
    state = _armies_state()
    state.turn_number = 25  # 55 - 5*(25-24) = 50

    lines = describe_election_status_report(state, 1)

    assert "Note: it requires only 50% of world taxbase to become Emperor next turn." in lines


def test_describe_election_status_report_no_threshold_hint_before_turn_25():
    state = _armies_state()
    state.turn_number = 24

    lines = describe_election_status_report(state, 1)

    assert not any("requires only" in line for line in lines)


def test_describe_election_status_report_no_threshold_hint_once_emperor_elected():
    state = _armies_state()
    state.turn_number = 30
    state.emperor_kingdom_id = 1

    lines = describe_election_status_report(state, 1)

    assert not any("requires only" in line for line in lines)


def test_describe_election_status_report_shows_this_kingdoms_alignment_vote_share():
    # A single Kingdom with a real tax base -- its own alignment holds
    # 100% of world vote weight by construction (nobody else exists).
    state = _armies_state()
    state.provinces[HexCoord(0, 0)].tax = 10
    state.kingdoms[1].alignment = Alignment.GOOD

    lines = describe_election_status_report(state, 1)

    assert lines == [
        "ELECTION STATUS",
        "The Good alignment now controls 100% of the world's votes (taxbase + (5 x office/treasure points)).",
    ]


def test_describe_election_status_report_omits_alignment_line_when_world_total_is_zero():
    state = _armies_state()  # no tax base anywhere -- world_total == 0

    lines = describe_election_status_report(state, 1)

    assert not any("controls" in line for line in lines)


# -- Phase 778: describe_election_status_report()'s alignment-bloc-trigger notice --


def test_describe_election_status_report_alignment_bloc_trigger_renders_both_lines():
    state = _armies_state()
    state.provinces[HexCoord(0, 0)].tax = 10
    state.kingdoms[1].alignment = Alignment.GOOD  # sole Kingdom -> 100% GOOD bloc share
    outcome = ElectionResult(
        elected_emperor_kingdom_id=None, votes_by_candidate={}, total_votes_cast=0, ballots={}, alignment_trigger=Alignment.GOOD
    )

    lines = describe_election_status_report(state, 1, outcome)

    assert "The Good alignment controls 100% of the world's votes." in lines
    assert "Consquently, a vote for World Emperor will be held this turn." in lines


def test_describe_election_status_report_alignment_bloc_trigger_omits_the_controls_line_once_the_share_has_shrunk():
    # The alignment was the real trigger at scheduling time, but its own
    # *current* bloc share has since dropped below 55% by tally time --
    # the real IF alperc[alvote] >= 55 gate silently drops just this one
    # sentence, not the "vote will be held" line.
    state = _armies_state()
    state.provinces[HexCoord(0, 0)].tax = 40
    state.kingdoms[1].alignment = Alignment.GOOD
    state.add_kingdom(KingdomState(2, "Farland", Race.HUMAN, Alignment.EVIL, HexCoord(1, 1)))
    state.add_province(ProvinceState(HexCoord(1, 1), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2, tax=60))
    outcome = ElectionResult(
        elected_emperor_kingdom_id=None, votes_by_candidate={}, total_votes_cast=0, ballots={}, alignment_trigger=Alignment.GOOD
    )

    lines = describe_election_status_report(state, 1, outcome)

    # The sibling "This Kingdom's own alignment vote share" notice (a
    # different template, "now controls") still renders unconditionally
    # -- only the trigger-specific "alignment controls X%." sentence
    # (no "now") is gated on the 55% threshold.
    assert not any(line.startswith("The Good alignment controls") for line in lines)
    assert "Consquently, a vote for World Emperor will be held this turn." in lines


def test_describe_election_status_report_alignment_bloc_trigger_none_still_renders_the_vote_held_line():
    # A vote scheduled by King-request weight alone, no alignment bloc.
    state = _armies_state()
    outcome = ElectionResult(
        elected_emperor_kingdom_id=None, votes_by_candidate={}, total_votes_cast=0, ballots={}, alignment_trigger=None
    )

    lines = describe_election_status_report(state, 1, outcome)

    assert lines == ["ELECTION STATUS", "Consquently, a vote for World Emperor will be held this turn."]


def test_describe_election_status_report_no_vote_held_line_without_a_real_tally():
    state = _armies_state()

    assert describe_election_status_report(state, 1, None) == []

    call_outcome = ElectionCallOutcome(
        world_total=10, immediate_coronation_kingdom_id=None, callers_qualify=False, alignment_trigger=Alignment.GOOD
    )
    lines = describe_election_status_report(state, 1, call_outcome)

    assert not any("will be held" in line for line in lines)


# -- Phase 800: describe_election_status_report()'s caller-percentage notice --


def test_describe_election_status_report_caller_percentage_from_a_call_outcome():
    state = _armies_state()
    call_outcome = ElectionCallOutcome(
        world_total=10,
        immediate_coronation_kingdom_id=None,
        callers_qualify=False,
        alignment_trigger=None,
        caller_percent=60,
    )

    lines = describe_election_status_report(state, 1, call_outcome)

    assert "Note: Kings owning 60% of the world's tax base called for an election." in lines


def test_describe_election_status_report_caller_percentage_from_a_tally_result():
    state = _armies_state()
    outcome = ElectionResult(
        elected_emperor_kingdom_id=None,
        votes_by_candidate={},
        total_votes_cast=0,
        ballots={},
        alignment_trigger=None,
        caller_percent=40,
    )

    lines = describe_election_status_report(state, 1, outcome)

    assert "Note: Kings owning 40% of the world's tax base called for an election." in lines


def test_describe_election_status_report_omits_caller_percentage_line_when_zero():
    state = _armies_state()
    call_outcome = ElectionCallOutcome(
        world_total=10, immediate_coronation_kingdom_id=None, callers_qualify=False, alignment_trigger=None
    )

    lines = describe_election_status_report(state, 1, call_outcome)

    assert not any("called for an election" in line for line in lines)


def test_describe_election_status_report_caller_percentage_line_precedes_the_alignment_lines():
    state = _armies_state()
    state.provinces[HexCoord(0, 0)].tax = 10
    state.kingdoms[1].alignment = Alignment.GOOD
    outcome = ElectionResult(
        elected_emperor_kingdom_id=None,
        votes_by_candidate={},
        total_votes_cast=0,
        ballots={},
        alignment_trigger=Alignment.GOOD,
        caller_percent=60,
    )

    lines = describe_election_status_report(state, 1, outcome)

    assert lines == [
        "ELECTION STATUS",
        "Note: Kings owning 60% of the world's tax base called for an election.",
        "The Good alignment now controls 100% of the world's votes (taxbase + (5 x office/treasure points)).",
        "The Good alignment controls 100% of the world's votes.",
        "Consquently, a vote for World Emperor will be held this turn.",
    ]


# -- Phase 656: describe_election_report() -- ELECTION REPORT --


def test_describe_election_report_empty_when_no_outcome():
    state = _armies_state()

    assert describe_election_report(state, None) == []


def test_describe_election_report_empty_for_a_call_outcome_not_a_real_tally():
    # ElectionCallOutcome means the engine only *evaluated* whether to
    # hold a vote this turn -- no real tally to show, matching the real
    # `tktax > 0` gate (no vote was actually tallied).
    state = _armies_state()
    outcome = ElectionCallOutcome(
        world_total=10, immediate_coronation_kingdom_id=None, callers_qualify=False, alignment_trigger=None
    )

    assert describe_election_report(state, outcome) == []


def test_describe_election_report_renders_a_real_vote_with_a_clear_winner():
    state = _armies_state()
    state.provinces[HexCoord(0, 0)].tax = 75
    state.add_leader(LeaderState(1, 1, "Aldric", HexCoord(0, 0), is_king=True))
    state.add_kingdom(KingdomState(2, "Farland", Race.HUMAN, Alignment.EVIL, HexCoord(1, 1)))
    state.add_province(
        ProvinceState(HexCoord(1, 1), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2, name="Farhold", tax=25)
    )
    state.add_leader(LeaderState(2, 2, "Vraxis", HexCoord(1, 1), is_king=True))
    outcome = ElectionResult(
        elected_emperor_kingdom_id=1,
        votes_by_candidate={1: 75, 2: 25},
        total_votes_cast=100,
        ballots={1: 1, 2: 2},  # each King voted for himself
    )

    lines = describe_election_report(state, outcome)

    assert lines[0] == "ELECTION REPORT"
    assert lines[1] == "A vote was held this turn in game 1.  Here are the results:"
    assert lines[2] == "                   Votes"
    assert lines[3] == "King                Cast  Voted for King   Votes Received"
    aldric_row = next(line for line in lines if line.startswith("Aldric"))
    vraxis_row = next(line for line in lines if line.startswith("Vraxis"))
    assert "75" in aldric_row and "Aldric" in aldric_row and "75 votes (75%)" in aldric_row
    assert "25" in vraxis_row and "Vraxis" in vraxis_row and "25 votes (25%)" in vraxis_row
    assert not any("Neutral Characters" in line for line in lines)


def test_describe_election_report_abstaining_king_shows_no_one():
    state = _armies_state()
    state.add_leader(LeaderState(1, 1, "Aldric", HexCoord(0, 0), is_king=True))
    outcome = ElectionResult(
        elected_emperor_kingdom_id=None,
        votes_by_candidate={},
        total_votes_cast=50,
        ballots={},  # Aldric abstained -- no entry for kingdom 1
    )

    lines = describe_election_report(state, outcome)

    aldric_row = next(line for line in lines if line.startswith("Aldric"))
    assert "0" in aldric_row and "No one" in aldric_row
    assert "0 votes (0%)" in aldric_row


def test_describe_election_report_percentage_is_truncated_not_rounded():
    # 2/3 * 100 == 66.67 -- Trunc() (the real, confirmed REPORTS.PAS
    # formula) gives 66%, round() would give 67%. Proves this composer
    # follows the real source's own truncation, not a rounding guess.
    state = _armies_state()
    state.add_leader(LeaderState(1, 1, "Aldric", HexCoord(0, 0), is_king=True))
    outcome = ElectionResult(
        elected_emperor_kingdom_id=None,
        votes_by_candidate={1: 2},
        total_votes_cast=3,
        ballots={1: 1},
    )

    lines = describe_election_report(state, outcome)

    aldric_row = next(line for line in lines if line.startswith("Aldric"))
    assert "2 votes (66%)" in aldric_row


def test_compose_letter_report_includes_election_report_before_imperial_office():
    state = _armies_state()
    state.add_leader(LeaderState(1, 1, "Aldric", HexCoord(0, 0), is_king=True))
    outcome = ElectionResult(
        elected_emperor_kingdom_id=None,
        votes_by_candidate={1: 10},
        total_votes_cast=10,
        ballots={1: 1},
    )

    lines = compose_letter_report([], state, 1, ScriptedRandom([]), election_outcome=outcome)

    assert "ELECTION REPORT" in lines
    assert lines.index("ELECTION REPORT") < lines.index("IMPERIAL OFFICE REPORT")


def test_compose_letter_report_omits_election_report_by_default():
    state = _armies_state()

    lines = compose_letter_report([], state, 1, ScriptedRandom([]))

    assert "ELECTION REPORT" not in lines


def test_compose_letter_report_includes_election_status_section():
    state = _armies_state()
    state.provinces[HexCoord(0, 0)].tax = 10

    lines = compose_letter_report([], state, 1, ScriptedRandom([]))

    assert "ELECTION STATUS" in lines


def test_compose_letter_report_threads_election_outcome_to_the_status_section_too():
    # Phase 778: election_outcome reaches describe_election_status_
    # report(), not just describe_election_report() -- proven end to
    # end via compose_letter_report()'s own real call site.
    state = _armies_state()
    state.provinces[HexCoord(0, 0)].tax = 10
    outcome = ElectionResult(
        elected_emperor_kingdom_id=None,
        votes_by_candidate={},
        total_votes_cast=0,
        ballots={},
        alignment_trigger=None,
    )

    lines = compose_letter_report([], state, 1, ScriptedRandom([]), election_outcome=outcome)

    assert "Consquently, a vote for World Emperor will be held this turn." in lines


def test_compose_letter_report_includes_final_standings_once_emperor_elected():
    state = _armies_state()
    state.emperor_kingdom_id = 1

    lines = compose_letter_report([], state, 1, ScriptedRandom([]))

    assert "FINAL STANDINGS" in lines


def test_compose_letter_report_omits_final_standings_before_any_emperor_elected():
    state = _armies_state()

    lines = compose_letter_report([], state, 1, ScriptedRandom([]))

    assert "FINAL STANDINGS" not in lines


# -- Phase 230: describe_imperial_office_report() -- IMPERIAL OFFICE REPORT --


def test_describe_imperial_office_report_none_at_present_for_every_office_with_no_leaders():
    state = _armies_state()

    lines = describe_imperial_office_report(state, 1)

    assert lines[0] == "IMPERIAL OFFICE REPORT"
    assert lines[1].startswith("Into thy heroic dreams")  # Phase 652: pre-election framing
    assert lines.count("World Emperor             None at present") == 1
    assert lines.count("Arch-Mage Palatine        None at present") == 1
    assert lines.count("King of Pain              None at present") == 1
    assert lines.count("Prince of Thieves         None at present") == 1
    assert lines.count("Savior of Humankind       None at present") == 1
    assert lines.count("Dragon Lord               None at present") == 1
    # Phase 668: the 3 army-scoped titles, rendered in their own separate loop.
    assert lines.count("Royal Air Force           None at present") == 1
    assert lines.count("Praetorian Guard          None at present") == 1
    assert lines.count("Imperial Flag Squadron    None at present") == 1
    assert len(lines) == 52  # header + pre-election framing + 47 leader offices + 3 army offices


def test_describe_imperial_office_report_omits_disabled_optional_titles():
    # GM interface Phase 3: an optional title the GM excluded from this
    # game gets no row at all -- not even "None at present" -- while the
    # 8 mandatory Imperial Offices are unaffected by the same setting.
    state = _armies_state()
    state.enabled_optional_offices = {Office.EVIL_KING}  # excludes every other optional title

    lines = describe_imperial_office_report(state, 1)

    assert not any(line.startswith("Prince of Thieves") for line in lines)
    assert not any(line.startswith("Savior of Humankind") for line in lines)
    assert not any(line.startswith("Royal Air Force") for line in lines)
    assert not any(line.startswith("Praetorian Guard") for line in lines)
    assert not any(line.startswith("Imperial Flag Squadron") for line in lines)
    # Kept: an explicitly-enabled optional title, and the 8 mandatory ones.
    assert lines.count("King of Pain              None at present") == 1
    assert lines.count("World Emperor             None at present") == 1
    assert lines.count("Arch-Mage Palatine        None at present") == 1


def test_describe_imperial_office_report_unset_enabled_optional_offices_shows_everything():
    # None (never configured -- every pre-existing game/test) must keep
    # this composer's original, unfiltered behavior.
    state = _armies_state()
    assert state.enabled_optional_offices is None

    lines = describe_imperial_office_report(state, 1)

    assert lines.count("Dragon Lord               None at present") == 1
    assert lines.count("Royal Air Force           None at present") == 1


def test_describe_imperial_office_report_shows_a_real_office_holder():
    # Phase 440: name/points now come with real rank/Riv% too -- "None"
    # for Riv% since nobody outside Testland is even a candidate.
    state = _armies_state()
    state.add_leader(LeaderState(1, 1, "Aldric", HexCoord(0, 0), is_king=True))
    state.leaders[1].merit_tally.resurrection_bless_casts = 3

    lines = describe_imperial_office_report(state, 1)

    assert "High Priest Palatine      Aldric (3 points, rank 1, None)" in lines


def test_describe_imperial_office_report_shows_a_real_army_office_holder():
    # Phase 668: the 3 army-scoped titles "evaluate the military unit
    # directly rather than a leader" -- rendered with a type+province
    # identity (no real per-army ordinal survives), not a leader name.
    state = _armies_state()
    state.add_army(ArmyState(101, 1, ArmyType.DRAGON_WING, Quality.ELITE, HexCoord(0, 0)))

    lines = describe_imperial_office_report(state, 1)

    matching = [line for line in lines if line.startswith("Royal Air Force")]
    assert len(matching) == 1
    assert "Dragons army in Capital City" in matching[0]
    assert "rank 1" in matching[0]


def test_describe_imperial_office_report_army_office_riv_percent_and_runner_up():
    # A second, weaker qualifying army in the same Kingdom becomes the
    # runner-up line; a rival Kingdom's own army feeds Riv%.
    state = _armies_state()
    state.add_kingdom(KingdomState(2, "Otherland", Race.ELVEN, Alignment.NEUTRAL, HexCoord(5, 5)))
    state.add_province(ProvinceState(HexCoord(1, 1), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_province(ProvinceState(HexCoord(5, 5), Terrain.PLAINS, Race.ELVEN, owner_kingdom_id=2, name="Elvenhold"))
    state.add_army(ArmyState(101, 1, ArmyType.DRAGON_WING, Quality.ELITE, HexCoord(0, 0)))  # kingdom 1, home bonus
    state.add_army(ArmyState(102, 1, ArmyType.DRAGON_WING, Quality.CRACK, HexCoord(1, 1)))  # kingdom 1, no home bonus
    state.add_army(ArmyState(201, 2, ArmyType.DRAGON_WING, Quality.CRACK, HexCoord(5, 5)))  # rival kingdom, home bonus

    lines = describe_imperial_office_report(state, 1)

    top_index = next(i for i, line in enumerate(lines) if line.startswith("Royal Air Force"))
    assert "Dragons army in Capital City" in lines[top_index]
    assert "None" not in lines[top_index]  # a real rival exists (army 201)
    runner_up_line = lines[top_index + 1]
    assert "Dragons army" in runner_up_line
    assert runner_up_line.startswith(" " * 26)  # blank-indented runner-up prefix


def test_describe_imperial_office_report_differs_per_kingdom_before_the_emperor_election():
    # Phase 440: the report is genuinely per-Kingdom pre-election -- each
    # King's own report shows only his own Kingdom's "Best Hope", not the
    # true global leader. Testland's own Aldric is a real (if 0-point)
    # King candidate for World Emperor; Otherland has no leaders at all.
    state = _armies_state()
    state.add_kingdom(KingdomState(2, "Otherland", Race.ELVEN, Alignment.NEUTRAL, HexCoord(1, 1)))
    state.add_leader(LeaderState(1, 1, "Aldric", HexCoord(0, 0), is_king=True))

    testland_lines = describe_imperial_office_report(state, 1)
    otherland_lines = describe_imperial_office_report(state, 2)

    assert "World Emperor             Aldric (0 points, rank 1, None)" in testland_lines
    assert "World Emperor             None at present" in otherland_lines


def test_describe_imperial_office_report_converges_after_the_emperor_election():
    # Phase 440: once an Emperor is elected, every Kingdom's own report
    # shows the same true global winner for Emperor, even a Kingdom
    # (Otherland) that never had a candidate of its own.
    state = _armies_state()
    state.add_kingdom(KingdomState(2, "Otherland", Race.ELVEN, Alignment.NEUTRAL, HexCoord(1, 1)))
    state.add_leader(LeaderState(1, 1, "Aldric", HexCoord(0, 0), is_king=True))
    state.emperor_kingdom_id = 1

    testland_lines = describe_imperial_office_report(state, 1)
    otherland_lines = describe_imperial_office_report(state, 2)

    expected = "World Emperor             Aldric (0 points, rank 1, None)"
    assert expected in testland_lines
    assert expected in otherland_lines


def test_describe_imperial_office_report_riv_percent_and_runner_up_are_kingdom_scoped():
    # Phase 440: Rank()/Riv% are always relative to the ROW's own holder
    # (real REPORTS.PAS Rank(bestldr,...)/Rank(nextldr,...), each deriving
    # their own rival kingdom from their own leader) -- not the report's
    # own viewing Kingdom. Aldric (Testland) globally wins Defender at 10
    # points; Cassian (Rivalland) is Testland's only rival at 4 points.
    state = _armies_state()
    state.add_kingdom(KingdomState(2, "Rivalland", Race.DWARVEN, Alignment.NEUTRAL, HexCoord(1, 1)))
    aldric = LeaderState(1, 1, "Aldric", HexCoord(0, 0), is_king=True)
    aldric.merit_tally.monster_hp_defeated = 10
    cassian = LeaderState(2, 2, "Cassian", HexCoord(1, 1), is_king=True)
    cassian.merit_tally.monster_hp_defeated = 4
    state.add_leader(aldric)
    state.add_leader(cassian)
    state.emperor_kingdom_id = 1  # settles the election so the true global winner is shown

    testland_lines = describe_imperial_office_report(state, 1)
    rivalland_lines = describe_imperial_office_report(state, 2)

    # Both Kingdoms' own reports show the same true winner (Aldric),
    # scored against his own real rival (Cassian, 4 points -> 250%).
    assert "Lord High Defender        Aldric (10 points, rank 1, 250%)" in testland_lines
    assert "Lord High Defender        Aldric (10 points, rank 1, 250%)" in rivalland_lines
    # Testland has no runner-up of its own (Aldric is its only candidate).
    assert not any(l.startswith(" " * 26 + "Cassian") for l in testland_lines)
    # Rivalland's own runner-up is Cassian himself -- rank 2 (beaten only
    # by Aldric), scored against Rivalland's own real rival (Aldric, 10
    # points -> 40%).
    assert "                          Cassian (4 points, rank 2, 40%)" in rivalland_lines


# -- Phase 652: IMPERIAL OFFICE REPORT's own real framing paragraphs --


def test_describe_imperial_office_report_post_election_shows_coronation_banner():
    state = _armies_state()
    state.add_leader(LeaderState(1, 1, "Aldric", HexCoord(0, 0), is_king=True))
    state.emperor_kingdom_id = 1

    lines = describe_imperial_office_report(state, 1)

    assert lines[1] == (
        "The world has finally been united under the rule of one Emperor.  All Kings now owe their allegiance to Aldric!"
    )
    assert lines[2].startswith("In his Divine wisdom")


def test_describe_imperial_office_report_coronation_banner_falls_back_to_kingdom_name():
    # No registered King for the Emperor's own kingdom -- falls back to
    # the Kingdom's own name rather than guessing/blanking.
    state = _armies_state()
    state.emperor_kingdom_id = 1

    lines = describe_imperial_office_report(state, 1)

    assert "Testland" in lines[1]


# -- Phase 543: Arcane's Valor "unification" report line -- SS11.3 --

_UNIFICATION_LINE_1 = "The Crown of Rohan, Scepter of Life and Amulet of Power have been united!"
_UNIFICATION_LINE_2 = (
    'All races are unified under the awesome power of "Arcane\'s Valor" and its glorious wielder, Aldric!'
)


def test_describe_imperial_office_report_shows_unification_line_in_the_emperors_own_kingdom():
    state = _armies_state()
    state.game_type = GameType.ARCANES
    state.add_leader(LeaderState(1, 1, "Aldric", HexCoord(0, 0), is_king=True))
    state.emperor_kingdom_id = 1
    state.add_item(Treasure.NAMED_UNIQUE_CROWN_ROHAN, owner_leader_id=1)
    state.add_item(Treasure.NAMED_UNIQUE_AMULET_POWER, owner_leader_id=1)
    state.add_item(Treasure.NAMED_UNIQUE_SCEPTER_LIFE, owner_leader_id=1)

    lines = describe_imperial_office_report(state, 1)

    assert _UNIFICATION_LINE_1 in lines
    assert _UNIFICATION_LINE_2 in lines


def test_describe_imperial_office_report_omits_unification_line_for_a_non_emperor_kingdom():
    state = _armies_state()
    state.game_type = GameType.ARCANES
    state.add_kingdom(KingdomState(2, "Otherland", Race.ELVEN, Alignment.NEUTRAL, HexCoord(1, 1)))
    state.add_leader(LeaderState(1, 1, "Aldric", HexCoord(0, 0), is_king=True))
    state.emperor_kingdom_id = 1
    state.add_item(Treasure.NAMED_UNIQUE_CROWN_ROHAN, owner_leader_id=1)
    state.add_item(Treasure.NAMED_UNIQUE_AMULET_POWER, owner_leader_id=1)
    state.add_item(Treasure.NAMED_UNIQUE_SCEPTER_LIFE, owner_leader_id=1)

    otherland_lines = describe_imperial_office_report(state, 2)

    assert _UNIFICATION_LINE_1 not in otherland_lines


def test_describe_imperial_office_report_omits_unification_line_outside_arcanes():
    state = _armies_state()
    state.add_leader(LeaderState(1, 1, "Aldric", HexCoord(0, 0), is_king=True))
    state.emperor_kingdom_id = 1
    state.add_item(Treasure.NAMED_UNIQUE_CROWN_ROHAN, owner_leader_id=1)
    state.add_item(Treasure.NAMED_UNIQUE_AMULET_POWER, owner_leader_id=1)
    state.add_item(Treasure.NAMED_UNIQUE_SCEPTER_LIFE, owner_leader_id=1)

    lines = describe_imperial_office_report(state, 1)

    assert _UNIFICATION_LINE_1 not in lines


def test_describe_imperial_office_report_extended_title_suppressed_below_minimum_points():
    # Phase 440: an extended title (Office.DUELLIST, min 2 points) whose
    # own pre-election "Best Hope" clears the real ftoppts/2 gate (1 >=
    # half of the rival's 2) but not OFFICE_MIN_POINTS (1 < 2) must still
    # render "None at present" -- the real second `IF bestpts <
    # minpts[ofc]` check, distinct from the ftoppts/2 one.
    state = _armies_state()
    state.add_kingdom(KingdomState(2, "Rivalland", Race.DWARVEN, Alignment.NEUTRAL, HexCoord(1, 1)))
    aldric = LeaderState(1, 1, "Aldric", HexCoord(0, 0), is_king=True)
    aldric.merit_tally.duel_merit_net = 1
    cassian = LeaderState(2, 2, "Cassian", HexCoord(1, 1), is_king=True)
    cassian.merit_tally.duel_merit_net = 2
    state.add_leader(aldric)
    state.add_leader(cassian)

    lines = describe_imperial_office_report(state, 1)

    assert "Captain of the Musketeers None at present" in lines


def test_describe_imperial_office_report_extended_title_shown_above_both_thresholds():
    state = _armies_state()
    state.add_kingdom(KingdomState(2, "Rivalland", Race.DWARVEN, Alignment.NEUTRAL, HexCoord(1, 1)))
    aldric = LeaderState(1, 1, "Aldric", HexCoord(0, 0), is_king=True)
    aldric.merit_tally.duel_merit_net = 5
    cassian = LeaderState(2, 2, "Cassian", HexCoord(1, 1), is_king=True)
    cassian.merit_tally.duel_merit_net = 2
    state.add_leader(aldric)
    state.add_leader(cassian)

    lines = describe_imperial_office_report(state, 1)

    assert "Captain of the Musketeers Aldric (5 points, rank 1, 250%)" in lines


def test_compose_letter_report_includes_imperial_office_report_between_armies_and_adventure():
    state = _armies_state()

    lines = compose_letter_report([], state, 1, ScriptedRandom([]))

    armies_index = lines.index("ARMIES")
    office_index = lines.index("IMPERIAL OFFICE REPORT")
    adventure_index = lines.index("ADVENTURE")
    assert armies_index < office_index < adventure_index


# -- Phase 561: describe_state_of_the_nation_report() -- STATE OF THE NATION --
# and the Emperor-conditional IMPERIAL OFFICE REPORT reordering it brought


def test_describe_state_of_the_nation_report_matches_the_real_sample_text():
    assert describe_state_of_the_nation_report() == [
        "STATE OF THE NATION:",
        "My lord and sovereign, greatest of Kings, I humbly beg thy leave to make "
        "report of matters of this Kingdom that may concern thy divine majesty.",
    ]


def test_compose_letter_report_state_of_the_nation_always_appears_once_before_diplomacy():
    state = _armies_state()

    lines = compose_letter_report([], state, 1, ScriptedRandom([]))

    assert lines.count("STATE OF THE NATION:") == 1
    assert lines.index("STATE OF THE NATION:") < lines.index("DIPLOMACY")


def test_compose_letter_report_imperial_office_report_stays_after_armies_without_an_emperor():
    state = _armies_state()

    lines = compose_letter_report([], state, 1, ScriptedRandom([]))

    state_of_the_nation_index = lines.index("STATE OF THE NATION:")
    armies_index = lines.index("ARMIES")
    office_index = lines.index("IMPERIAL OFFICE REPORT")
    assert state_of_the_nation_index < armies_index < office_index
    assert lines.count("IMPERIAL OFFICE REPORT") == 1


def test_compose_letter_report_imperial_office_report_moves_before_state_of_the_nation_once_an_emperor_exists():
    state = _armies_state()
    state.emperor_kingdom_id = 1

    lines = compose_letter_report([], state, 1, ScriptedRandom([]))

    office_index = lines.index("IMPERIAL OFFICE REPORT")
    state_of_the_nation_index = lines.index("STATE OF THE NATION:")
    armies_index = lines.index("ARMIES")
    assert office_index < state_of_the_nation_index < armies_index
    # No duplication -- it must not also still appear after ARMIES.
    assert lines.count("IMPERIAL OFFICE REPORT") == 1


# -- Phase 212: describe_aspy() -- real assembly of Phase 115/118's own SAY.PAS templates --


def test_describe_aspy_no_characters_or_forces():
    report = SpyReport(province=HexCoord(0, 0), owner_kingdom_id=1)
    rng = ScriptedRandom([0.1] * 20, choice_indices=[0])

    lines = describe_aspy(
        report, spy_name="Aldric", province_name="Greenfield", owner_name=None, adjacent_owner_names=[], rng=rng
    )

    assert lines[0] == render_spy_report_opening("Aldric", "Greenfield", ScriptedRandom([0.1] * 4, choice_indices=[0]))
    assert "there were no conspicuous characters or forces in Greenfield." in lines
    assert lines[-1] == (
        "Aldric also kept tabs on the characters in Greenfield and any "
        "further news is in the General Intelligence Report."
    )


def test_describe_aspy_forces_but_no_characters():
    report = SpyReport(province=HexCoord(0, 0), owner_kingdom_id=1, garrison_army_names=("241st Axemen",))
    rng = ScriptedRandom([0.1] * 20, choice_indices=[0])

    lines = describe_aspy(
        report, spy_name="Aldric", province_name="Greenfield", owner_name=None, adjacent_owner_names=[], rng=rng
    )

    assert "the following elements are present in Greenfield:  " in lines
    assert "there were no conspicuous characters in Greenfield." in lines
    assert "there is a garrison of approximately 241st Axemen." in lines
    assert "there were no conspicuous characters or forces in Greenfield." not in lines


def test_describe_aspy_characters_with_and_without_armies():
    report = SpyReport(
        province=HexCoord(0, 0),
        owner_kingdom_id=1,
        spotted_characters=[
            SpottedCharacter(1, "Borin", estimated_alignment=None, estimated_temper=None),
            SpottedCharacter(
                2, "Commander Vale", estimated_alignment=None, estimated_temper=None, army_names=("34th Legion",)
            ),
        ],
    )
    rng = ScriptedRandom([0.1] * 30, choice_indices=[0])

    lines = describe_aspy(
        report, spy_name="Aldric", province_name="Greenfield", owner_name=None, adjacent_owner_names=[], rng=rng
    )

    assert "Borin  is here." in lines
    assert "Commander Vale  is here." in lines
    assert "Commander Vale leads approximately 34th Legion." in lines
    assert not any("no conspicuous characters" in line for line in lines)


def test_describe_aspy_includes_capital_notice_when_capital():
    report = SpyReport(province=HexCoord(0, 0), owner_kingdom_id=1, is_capital=True)
    rng = ScriptedRandom([0.1] * 20, choice_indices=[0])

    lines = describe_aspy(
        report, spy_name="Aldric", province_name="Greenfield", owner_name=None, adjacent_owner_names=[], rng=rng
    )

    assert "Greenfield is the kingdom's capital province." in lines


def test_describe_aspy_omits_capital_notice_when_not_capital():
    report = SpyReport(province=HexCoord(0, 0), owner_kingdom_id=1, is_capital=False)
    rng = ScriptedRandom([0.1] * 20, choice_indices=[0])

    lines = describe_aspy(
        report, spy_name="Aldric", province_name="Greenfield", owner_name=None, adjacent_owner_names=[], rng=rng
    )

    assert "Greenfield is the kingdom's capital province." not in lines


def test_describe_aspy_lists_recruitable_army_types_in_order():
    report = SpyReport(
        province=HexCoord(0, 0), owner_kingdom_id=1, recruitable_army_types=[ArmyType.BOWMEN, ArmyType.AXEMEN]
    )
    rng = ScriptedRandom([0.1] * 20, choice_indices=[0])

    lines = describe_aspy(
        report, spy_name="Aldric", province_name="Greenfield", owner_name=None, adjacent_owner_names=[], rng=rng
    )

    assert "Province Army Type 1: Bowmen" in lines
    assert "Province Army Type 2: Axemen" in lines
    assert lines.index("Province Army Type 1: Bowmen") < lines.index("Province Army Type 2: Axemen")


def test_describe_aspy_renders_taxation_between_army_types_and_characters():
    report = SpyReport(
        province=HexCoord(0, 0), owner_kingdom_id=1, recruitable_army_types=[ArmyType.BOWMEN], tax_estimate=250
    )
    rng = ScriptedRandom([0.1] * 20, choice_indices=[0])

    lines = describe_aspy(
        report, spy_name="Aldric", province_name="Greenfield", owner_name=None, adjacent_owner_names=[], rng=rng
    )

    assert "Approximate Taxation: 250" in lines
    tax_index = lines.index("Approximate Taxation: 250")
    assert lines.index("Province Army Type 1: Bowmen") < tax_index
    assert tax_index < lines.index("there were no conspicuous characters or forces in Greenfield.")


def test_describe_aspy_omits_taxation_when_never_recorded():
    report = SpyReport(province=HexCoord(0, 0), owner_kingdom_id=1)  # tax_estimate defaults to None
    rng = ScriptedRandom([0.1] * 20, choice_indices=[0])

    lines = describe_aspy(
        report, spy_name="Aldric", province_name="Greenfield", owner_name=None, adjacent_owner_names=[], rng=rng
    )

    assert not any("Taxation" in line for line in lines)


# -- Phase 400: render_spy_owner / render_spy_adjacent_owners (project-original) --


def test_render_spy_owner_present():
    rng = ScriptedRandom([0.1] * 4, choice_indices=[0])
    assert render_spy_owner("Greenfield", "Aldric (#3)", rng) == "Greenfield is owned by Aldric (#3)."


def test_render_spy_owner_absent():
    rng = ScriptedRandom([0.1] * 4, choice_indices=[0])
    assert render_spy_owner("Greenfield", None, rng) == "Greenfield is not owned by any Kingdom."


def test_render_spy_adjacent_owners_present():
    rng = ScriptedRandom([0.1] * 4, choice_indices=[0])
    result = render_spy_adjacent_owners("Greenfield", ["Aldric (#3)", "Boru (#5)"], rng)
    # report/prose.py's own ^L "X, Y and Z" conjunction join, Phase 118.
    assert result == "The provinces adjacent to Greenfield are owned by Aldric (#3) and Boru (#5)."


def test_render_spy_adjacent_owners_absent():
    rng = ScriptedRandom([0.1] * 4, choice_indices=[0])
    result = render_spy_adjacent_owners("Greenfield", [], rng)
    assert result == "None of the provinces adjacent to Greenfield are owned by any Kingdom."


def test_describe_aspy_renders_owner_and_adjacent_owners_right_after_opening():
    report = SpyReport(province=HexCoord(0, 0), owner_kingdom_id=1)
    rng = ScriptedRandom([0.1] * 20, choice_indices=[0])

    lines = describe_aspy(
        report,
        spy_name="Aldric",
        province_name="Greenfield",
        owner_name="Boru (#1)",
        adjacent_owner_names=["Cedric (#2)"],
        rng=rng,
    )

    assert lines[1] == "Greenfield is owned by Boru (#1)."
    assert lines[2] == "The provinces adjacent to Greenfield are owned by Cedric (#2)."


def test_describe_aspy_renders_no_owner_and_no_adjacent_owners_as_real_facts():
    report = SpyReport(province=HexCoord(0, 0), owner_kingdom_id=None)
    rng = ScriptedRandom([0.1] * 20, choice_indices=[0])

    lines = describe_aspy(
        report, spy_name="Aldric", province_name="Greenfield", owner_name=None, adjacent_owner_names=[], rng=rng
    )

    assert lines[1] == "Greenfield is not owned by any Kingdom."
    assert lines[2] == "None of the provinces adjacent to Greenfield are owned by any Kingdom."


# -- Phase 850: render_espionage_discovery / render_spy_adjacent_forces / render_spy_feature_knowledge (project-original) --


def test_render_espionage_discovery():
    rng = ScriptedRandom([0.1] * 4, choice_indices=[0])
    result = render_espionage_discovery("Aldric", "Greenfield", Discovery.SEXTANT, rng)
    assert result == "Through espionage in Greenfield, Aldric learned the secrets of the Sextant."


def test_render_spy_adjacent_forces():
    rng = ScriptedRandom([0.1] * 4, choice_indices=[0])
    result = render_spy_adjacent_forces("Northfield", ["1st Bowmen", "2nd Axemen"], rng)
    assert result == "Animal scouts report 1st Bowmen and 2nd Axemen near Northfield."


def test_render_spy_feature_knowledge_all_three_levels():
    rng = ScriptedRandom([0.1] * 4, choice_indices=[0])
    assert (
        render_spy_feature_knowledge("Greenfield", 7, 1, rng)
        == "Regarding Feature 7 in Greenfield, the owner knows something is hidden there, but no more."
    )
    assert (
        render_spy_feature_knowledge("Greenfield", 7, 2, rng)
        == "Regarding Feature 7 in Greenfield, the owner has identified what it is."
    )
    assert (
        render_spy_feature_knowledge("Greenfield", 7, 3, rng)
        == "Regarding Feature 7 in Greenfield, the owner fully understands its secrets."
    )


def test_describe_aspy_renders_espionage_discoveries_right_before_closing():
    report = SpyReport(
        province=HexCoord(0, 0), owner_kingdom_id=1, discoveries_obtained=(Discovery.SEXTANT, Discovery.LAND_SHIP)
    )
    rng = ScriptedRandom([0.1] * 30, choice_indices=[0])

    lines = describe_aspy(
        report, spy_name="Aldric", province_name="Greenfield", owner_name=None, adjacent_owner_names=[], rng=rng
    )

    assert "Through espionage in Greenfield, Aldric learned the secrets of the Sextant." in lines
    assert "Through espionage in Greenfield, Aldric learned the secrets of the Land Ship." in lines
    sextant_index = lines.index("Through espionage in Greenfield, Aldric learned the secrets of the Sextant.")
    assert lines[-1] == (
        "Aldric also kept tabs on the characters in Greenfield and any "
        "further news is in the General Intelligence Report."
    )
    assert sextant_index == len(lines) - 3


def test_describe_aspy_omits_espionage_discoveries_when_none_obtained():
    report = SpyReport(province=HexCoord(0, 0), owner_kingdom_id=1)  # discoveries_obtained defaults to ()
    rng = ScriptedRandom([0.1] * 20, choice_indices=[0])

    lines = describe_aspy(
        report, spy_name="Aldric", province_name="Greenfield", owner_name=None, adjacent_owner_names=[], rng=rng
    )

    assert not any("espionage" in line for line in lines)


def test_describe_aspy_renders_adjacent_forces_right_after_adjacent_owners_and_skips_empty_ones():
    report = SpyReport(province=HexCoord(0, 0), owner_kingdom_id=1)
    rng = ScriptedRandom([0.1] * 20, choice_indices=[0])

    lines = describe_aspy(
        report,
        spy_name="Aldric",
        province_name="Greenfield",
        owner_name=None,
        adjacent_owner_names=[],
        adjacent_force_names={"Northfield": ("1st Bowmen",), "Emptyville": ()},
        rng=rng,
    )

    assert lines[3] == "Animal scouts report 1st Bowmen near Northfield."
    assert not any("Emptyville" in line for line in lines)


def test_describe_aspy_omits_adjacent_forces_line_when_not_supplied():
    report = SpyReport(province=HexCoord(0, 0), owner_kingdom_id=1)
    rng = ScriptedRandom([0.1] * 20, choice_indices=[0])

    lines = describe_aspy(
        report, spy_name="Aldric", province_name="Greenfield", owner_name=None, adjacent_owner_names=[], rng=rng
    )

    assert not any("Animal scouts" in line for line in lines)


def test_describe_aspy_renders_feature_knowledge_between_taxation_and_characters_sorted_by_id():
    report = SpyReport(
        province=HexCoord(0, 0),
        owner_kingdom_id=1,
        recruitable_army_types=[ArmyType.BOWMEN],
        tax_estimate=250,
        features_known_to_owner={9: 3, 4: 1},
    )
    rng = ScriptedRandom([0.1] * 20, choice_indices=[0])

    lines = describe_aspy(
        report, spy_name="Aldric", province_name="Greenfield", owner_name=None, adjacent_owner_names=[], rng=rng
    )

    low_id_index = lines.index(
        "Regarding Feature 4 in Greenfield, the owner knows something is hidden there, but no more."
    )
    high_id_index = lines.index("Regarding Feature 9 in Greenfield, the owner fully understands its secrets.")
    tax_index = lines.index("Approximate Taxation: 250")
    assert tax_index < low_id_index < high_id_index
    assert high_id_index < lines.index("there were no conspicuous characters or forces in Greenfield.")


def test_describe_aspy_omits_feature_knowledge_when_empty():
    report = SpyReport(province=HexCoord(0, 0), owner_kingdom_id=1)  # features_known_to_owner defaults to {}
    rng = ScriptedRandom([0.1] * 20, choice_indices=[0])

    lines = describe_aspy(
        report, spy_name="Aldric", province_name="Greenfield", owner_name=None, adjacent_owner_names=[], rng=rng
    )

    assert not any("Regarding Feature" in line for line in lines)


# -- Phase 231: record_battle_world_events() / describe_general_intelligence_report() --

_GIR_BOUNDS = MapBounds(*NORMAL_MAP_BOUNDS)


def _gir_state() -> GameState:
    home = HexCoord(5, 5)
    battle_coord = neighbors(home, _GIR_BOUNDS)[0]
    watcher_coord = neighbors(battle_coord, _GIR_BOUNDS)[1]

    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, home))
    state.add_kingdom(KingdomState(2, "Defendia", Race.HUMAN, Alignment.NEUTRAL, battle_coord))
    state.add_kingdom(KingdomState(3, "Watchia", Race.HUMAN, Alignment.NEUTRAL, watcher_coord))
    state.add_province(ProvinceState(home, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_province(ProvinceState(battle_coord, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, name="Border Fort"))
    state.add_province(ProvinceState(watcher_coord, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=3))
    return state, battle_coord, watcher_coord


def test_record_battle_world_events_records_the_winner_sentence():
    state, battle_coord, _watcher_coord = _gir_state()
    battle_result = BattleResult(winner="attacker")
    report = BattleReport(
        battle_result=battle_result, conquered=True,
        province_coord=battle_coord, attacker_kingdom_id=1, defender_kingdom_id=2,
    )
    results = [PhaseDispatchResult(leader_id=0, segment_index=-1, phase_label="forced-rebattle", action=None, result=report, error=None)]
    rng = ScriptedRandom([0.1, 0.1], choice_indices=[0])

    record_battle_world_events(state, results, rng)

    assert len(state.world_events) == 1
    event = state.world_events[0]
    assert event.coord == battle_coord
    assert event.lines == ["the forces of Attackia (#1) broke through and were victorious."]


def test_record_battle_world_events_skips_a_tie():
    state, battle_coord, _watcher_coord = _gir_state()
    report = BattleReport(
        battle_result=BattleResult(winner="tie"), conquered=False,
        province_coord=battle_coord, attacker_kingdom_id=1, defender_kingdom_id=2,
    )
    results = [PhaseDispatchResult(leader_id=0, segment_index=-1, phase_label="forced-rebattle", action=None, result=report, error=None)]

    record_battle_world_events(state, results, ScriptedRandom([]))

    assert state.world_events == []


def test_record_battle_world_events_skips_a_report_with_no_defender_kingdom():
    state, battle_coord, _watcher_coord = _gir_state()
    report = BattleReport(
        battle_result=BattleResult(winner="attacker"), conquered=True,
        province_coord=battle_coord, attacker_kingdom_id=1, defender_kingdom_id=None,
    )
    results = [PhaseDispatchResult(leader_id=0, segment_index=-1, phase_label="forced-rebattle", action=None, result=report, error=None)]

    record_battle_world_events(state, results, ScriptedRandom([0.1, 0.1], choice_indices=[0]))

    assert state.world_events == []


def test_record_battle_world_events_finds_a_battle_report_nested_under_battle_report_attribute():
    state, battle_coord, _watcher_coord = _gir_state()
    report = BattleReport(
        battle_result=BattleResult(winner="attacker"), conquered=True,
        province_coord=battle_coord, attacker_kingdom_id=1, defender_kingdom_id=2,
    )

    class _FakeMoveExecutionResult:
        def __init__(self, battle_report):
            self.battle_report = battle_report

    results = [
        PhaseDispatchResult(
            leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.LMOVE,
            result=_FakeMoveExecutionResult(report), error=None,
        )
    ]

    record_battle_world_events(state, results, ScriptedRandom([0.1, 0.1], choice_indices=[0]))

    assert len(state.world_events) == 1


def test_record_battle_world_events_finds_a_battle_report_nested_under_battle_dot_report():
    state, battle_coord, _watcher_coord = _gir_state()
    report = BattleReport(
        battle_result=BattleResult(winner="attacker"), conquered=True,
        province_coord=battle_coord, attacker_kingdom_id=1, defender_kingdom_id=2,
    )

    class _FakeBattle:
        def __init__(self, report):
            self.report = report

    class _FakeMultiAttackerMoveResult:
        def __init__(self, report):
            self.battle = _FakeBattle(report)

    results = [
        PhaseDispatchResult(
            leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.LMOVE,
            result=_FakeMultiAttackerMoveResult(report), error=None,
        )
    ]

    record_battle_world_events(state, results, ScriptedRandom([0.1, 0.1], choice_indices=[0]))

    assert len(state.world_events) == 1


def test_record_battle_world_events_deduplicates_a_multi_attacker_shared_battle_report():
    # Phase 844: rulebook [7.8] Multiple Contingents genuinely unites 2+
    # leaders into ONE shared BattleReport -- turn_processor.py's own
    # fan-out then appends one PhaseDispatchResult per united leader,
    # each pointing at the identical BattleReport object. Before this
    # fix, each duplicate entry independently re-rolled and recorded
    # its own copy of the same battle's winner sentence.
    state, battle_coord, _watcher_coord = _gir_state()
    report = BattleReport(
        battle_result=BattleResult(winner="attacker"), conquered=True,
        province_coord=battle_coord, attacker_kingdom_id=1, defender_kingdom_id=2,
    )

    class _FakeBattle:
        def __init__(self, report):
            self.report = report

    class _FakeMultiAttackerMoveResult:
        def __init__(self, report):
            self.battle = _FakeBattle(report)

    results = [
        PhaseDispatchResult(
            leader_id=101, segment_index=0, phase_label="P0", action=ActionCode.LMOVE,
            result=_FakeMultiAttackerMoveResult(report), error=None,
        ),
        PhaseDispatchResult(
            leader_id=102, segment_index=0, phase_label="P0", action=ActionCode.LMOVE,
            result=_FakeMultiAttackerMoveResult(report), error=None,
        ),
    ]

    record_battle_world_events(state, results, ScriptedRandom([0.1, 0.1], choice_indices=[0]))

    assert len(state.world_events) == 1


def test_describe_general_intelligence_report_none_at_present_with_no_events():
    state, _battle_coord, _watcher_coord = _gir_state()

    lines = describe_general_intelligence_report(state, 1)

    assert lines == ["GENERAL INTELLIGENCE REPORT", "None at present"]


def test_describe_general_intelligence_report_groups_visible_battle_under_the_provinces_owner():
    state, battle_coord, _watcher_coord = _gir_state()
    state.record_world_event(battle_coord, ["Border Fort was overrun."])

    lines = describe_general_intelligence_report(state, 3)

    assert lines == ["GENERAL INTELLIGENCE REPORT", "Kingdom of Attackia (#1):", "Border Fort was overrun."]


def test_describe_general_intelligence_report_excludes_this_kingdoms_own_activity():
    state, battle_coord, _watcher_coord = _gir_state()
    state.record_world_event(battle_coord, ["Border Fort was overrun."])

    lines = describe_general_intelligence_report(state, 1)

    assert lines == ["GENERAL INTELLIGENCE REPORT", "None at present"]


def test_describe_general_intelligence_report_hides_events_outside_visibility():
    state, battle_coord, watcher_coord = _gir_state()
    state.record_world_event(battle_coord, ["Border Fort was overrun."])
    state.kingdoms[4] = KingdomState(4, "Faraway", Race.HUMAN, Alignment.NEUTRAL, HexCoord(29, 14))

    lines = describe_general_intelligence_report(state, 4)

    assert lines == ["GENERAL INTELLIGENCE REPORT", "None at present"]


def test_describe_general_intelligence_report_skips_an_event_in_an_unowned_province():
    state, battle_coord, watcher_coord = _gir_state()
    state.provinces[battle_coord].owner_kingdom_id = None
    state.record_world_event(battle_coord, ["Border Fort was overrun."])

    lines = describe_general_intelligence_report(state, 3)

    assert lines == ["GENERAL INTELLIGENCE REPORT", "None at present"]


# -- Phase 232: render_plague_world_event() / render_illus_terrain_world_event() /
# record_spell_world_events() --


def test_render_plague_world_event():
    rng = ScriptedRandom([])

    assert render_plague_world_event("Transylvania", rng) == "Transylvania was hit by a plague."


def test_render_illus_terrain_world_event():
    rng = ScriptedRandom([])

    result = render_illus_terrain_world_event("Plain", "Border Fort", "Mountain", rng)

    assert result == "the Plain terrain of Border Fort was magically made to appear as Mountain."


def test_record_spell_world_events_records_a_successful_plague():
    state, battle_coord, _watcher_coord = _gir_state()
    board_width = NORMAL_MAP_BOUNDS[0]
    request = CastRequest(spell=Spell.PLAGUE, target=encode_hex_number(battle_coord, board_width))
    result = CastExecutionResult(request, applied=True)
    results = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.CAST, result=result, error=None)
    ]

    record_spell_world_events(state, results, ScriptedRandom([]), board_width=board_width)

    assert len(state.world_events) == 1
    event = state.world_events[0]
    assert event.coord == battle_coord
    assert event.lines == ["In spring, Border Fort was hit by a plague."]


def test_record_spell_world_events_records_a_successful_illus_terrain():
    state, battle_coord, _watcher_coord = _gir_state()
    board_width = NORMAL_MAP_BOUNDS[0]
    state.provinces[battle_coord].illusory_terrain = Terrain.MTNS
    request = CastRequest(spell=Spell.ILLUS_TERRAIN, target=encode_hex_number(battle_coord, board_width), terrain=Terrain.MTNS)
    result = CastExecutionResult(request, applied=True)
    results = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.CAST, result=result, error=None)
    ]

    record_spell_world_events(state, results, ScriptedRandom([]), board_width=board_width)

    assert len(state.world_events) == 1
    event = state.world_events[0]
    assert event.coord == battle_coord
    assert event.lines == ["In spring, the Plain terrain of Border Fort was magically made to appear as Mountain."]


def test_record_spell_world_events_illus_terrain_reveals_the_truth_to_a_privileged_kingdom():
    # Phase 886: Discovery.ULTRAVIOLET_LENSES -- a privileged Kingdom
    # (here, kingdom 3 "Watchia") learns the real terrain unconditionally,
    # regardless of distance, via its own separate, targeted accumulator.
    state, battle_coord, _watcher_coord = _gir_state()
    board_width = NORMAL_MAP_BOUNDS[0]
    state.add_leader(LeaderState(1, 1, "Caster", battle_coord))
    state.kingdoms[3].discoveries.add(Discovery.ULTRAVIOLET_LENSES)
    state.provinces[battle_coord].illusory_terrain = Terrain.MTNS
    request = CastRequest(spell=Spell.ILLUS_TERRAIN, target=encode_hex_number(battle_coord, board_width), terrain=Terrain.MTNS)
    result = CastExecutionResult(request, applied=True)
    results = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.CAST, result=result, error=None)
    ]

    record_spell_world_events(state, results, ScriptedRandom([]), board_width=board_width)

    assert state.illusory_terrain_reveals_by_kingdom[3] == [
        "In spring, the Plain terrain of Border Fort was magically made to appear as Mountain."
    ]
    assert state.illusory_terrain_reveals_by_kingdom.get(2, []) == []  # not privileged


def test_record_spell_world_events_illus_terrain_reveal_excludes_the_casters_own_kingdom():
    # The caster's own Kingdom already gets a private CAST-success line
    # elsewhere -- it must not also receive this targeted reveal, even
    # when it happens to hold Ultraviolet Lenses itself.
    state, battle_coord, _watcher_coord = _gir_state()
    board_width = NORMAL_MAP_BOUNDS[0]
    state.add_leader(LeaderState(1, 1, "Caster", battle_coord))
    state.kingdoms[1].discoveries.add(Discovery.ULTRAVIOLET_LENSES)
    state.provinces[battle_coord].illusory_terrain = Terrain.MTNS
    request = CastRequest(spell=Spell.ILLUS_TERRAIN, target=encode_hex_number(battle_coord, board_width), terrain=Terrain.MTNS)
    result = CastExecutionResult(request, applied=True)
    results = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.CAST, result=result, error=None)
    ]

    record_spell_world_events(state, results, ScriptedRandom([]), board_width=board_width)

    assert state.illusory_terrain_reveals_by_kingdom.get(1, []) == []


def test_record_spell_world_events_illus_terrain_no_reveal_without_true_sight():
    state, battle_coord, _watcher_coord = _gir_state()
    board_width = NORMAL_MAP_BOUNDS[0]
    state.add_leader(LeaderState(1, 1, "Caster", battle_coord))
    state.provinces[battle_coord].illusory_terrain = Terrain.MTNS
    request = CastRequest(spell=Spell.ILLUS_TERRAIN, target=encode_hex_number(battle_coord, board_width), terrain=Terrain.MTNS)
    result = CastExecutionResult(request, applied=True)
    results = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.CAST, result=result, error=None)
    ]

    record_spell_world_events(state, results, ScriptedRandom([]), board_width=board_width)

    assert state.illusory_terrain_reveals_by_kingdom == {}


def test_record_spell_world_events_skips_a_failed_cast():
    state, battle_coord, _watcher_coord = _gir_state()
    board_width = NORMAL_MAP_BOUNDS[0]
    request = CastRequest(spell=Spell.PLAGUE, target=encode_hex_number(battle_coord, board_width))
    result = CastExecutionResult(request, applied=False, reason="fizzled")
    results = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.CAST, result=result, error=None)
    ]

    record_spell_world_events(state, results, ScriptedRandom([]), board_width=board_width)

    assert state.world_events == []


def test_record_spell_world_events_skips_a_spell_with_no_world_event_source():
    state, battle_coord, _watcher_coord = _gir_state()
    board_width = NORMAL_MAP_BOUNDS[0]
    request = CastRequest(spell=Spell.KILL_ENEMY, target=1)
    result = CastExecutionResult(request, applied=True)
    results = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.CAST, result=result, error=None)
    ]

    record_spell_world_events(state, results, ScriptedRandom([]), board_width=board_width)

    assert state.world_events == []


def test_record_spell_world_events_skips_non_cast_results():
    state, _battle_coord, _watcher_coord = _gir_state()
    results = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.WAIT, result=None, error=None)
    ]

    record_spell_world_events(state, results, ScriptedRandom([]))

    assert state.world_events == []


# -- Phase 235: render_flood_world_event() / render_bystander_spell_notice() /
# record_spell_world_events() (Flood/Part Sea/Earthquake) --


def test_render_flood_world_event():
    rng = ScriptedRandom([])

    assert render_flood_world_event("Border Fort", rng) == "Border Fort was magically flooded."


def test_render_bystander_spell_notice_part_sea():
    rng = ScriptedRandom([])

    result = render_bystander_spell_notice(Spell.PART_SEA, "Border Fort", rng)

    assert result == "the waters of Border Fort were magically parted."


def test_render_bystander_spell_notice_earthquake():
    rng = ScriptedRandom([])

    result = render_bystander_spell_notice(Spell.EARTHQUAKE, "Border Fort", rng)

    assert result == "Border Fort was devastated by an earthquake!"


def test_render_bystander_spell_notice_raises_for_an_unsupported_spell():
    rng = ScriptedRandom([])

    with pytest.raises(ValueError):
        render_bystander_spell_notice(Spell.TORNADO, "Border Fort", rng)


def test_record_spell_world_events_records_a_successful_flood():
    state, battle_coord, _watcher_coord = _gir_state()
    board_width = NORMAL_MAP_BOUNDS[0]
    request = CastRequest(spell=Spell.FLOOD, target=encode_hex_number(battle_coord, board_width))
    result = CastExecutionResult(request, applied=True)
    results = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.CAST, result=result, error=None)
    ]

    record_spell_world_events(state, results, ScriptedRandom([]), board_width=board_width)

    assert len(state.world_events) == 1
    assert state.world_events[0].lines == ["In spring, Border Fort was magically flooded."]


def test_record_spell_world_events_records_a_successful_part_sea():
    state, battle_coord, _watcher_coord = _gir_state()
    board_width = NORMAL_MAP_BOUNDS[0]
    request = CastRequest(spell=Spell.PART_SEA, target=encode_hex_number(battle_coord, board_width))
    result = CastExecutionResult(request, applied=True)
    results = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.CAST, result=result, error=None)
    ]

    record_spell_world_events(state, results, ScriptedRandom([]), board_width=board_width)

    assert len(state.world_events) == 1
    assert state.world_events[0].lines == ["In spring, the waters of Border Fort were magically parted."]


def test_record_spell_world_events_records_a_successful_earthquake():
    state, battle_coord, _watcher_coord = _gir_state()
    board_width = NORMAL_MAP_BOUNDS[0]
    request = CastRequest(spell=Spell.EARTHQUAKE, target=encode_hex_number(battle_coord, board_width))
    result = CastExecutionResult(request, applied=True)
    results = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.CAST, result=result, error=None)
    ]

    record_spell_world_events(state, results, ScriptedRandom([]), board_width=board_width)

    assert len(state.world_events) == 1
    assert state.world_events[0].lines == ["In spring, Border Fort was devastated by an earthquake!"]


def test_record_spell_world_events_still_skips_tornado_world_events_with_nothing_destroyed():
    # Tornado never populates state.world_events (no S_Comm dispatch
    # exists for it) -- unchanged by Phase 939's own new S_AA victim-
    # notice branch below, which only fires when tornado_destroyed is
    # non-empty (see the dedicated tests for that).
    state, battle_coord, _watcher_coord = _gir_state()
    board_width = NORMAL_MAP_BOUNDS[0]
    request = CastRequest(spell=Spell.TORNADO, target=encode_hex_number(battle_coord, board_width))
    result = CastExecutionResult(request, applied=True)
    results = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.CAST, result=result, error=None)
    ]

    record_spell_world_events(state, results, ScriptedRandom([]), board_width=board_width)

    assert state.world_events == []
    assert state.tornado_victim_notices_by_kingdom == {}


def test_record_spell_world_events_tornado_notifies_a_victim_kingdom():
    # Phase 939: SAY.PAS's own real _ATDestr (Sps(Tornado,S_AA)) --
    # confirmed by real fixture text showing this exact sentence appear
    # bare inside the VICTIM's own letter, not the caster's.
    state, battle_coord, _watcher_coord = _gir_state()
    board_width = NORMAL_MAP_BOUNDS[0]
    state.add_leader(LeaderState(1, 1, "Caster", battle_coord))
    state.add_kingdom(KingdomState(9, "Victimia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(9, 9)))
    request = CastRequest(spell=Spell.TORNADO, target=encode_hex_number(battle_coord, board_width))
    destroyed = [ArmyState(20, 9, ArmyType.LEGION, Quality.AVERAGE, battle_coord)]
    result = CastExecutionResult(request, applied=True, tornado_destroyed=destroyed)
    results = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.CAST, result=result, error=None)
    ]

    record_spell_world_events(state, results, ScriptedRandom([]), board_width=board_width)

    assert state.world_events == []  # still no S_Comm/GIR visibility
    notices = state.tornado_victim_notices_by_kingdom[9]
    assert len(notices) == 1
    assert notices[0].endswith("Tornadoes sucked up the 20th Legion in Border Fort and destroyed them.")


def test_record_spell_world_events_tornado_excludes_the_casters_own_kingdom():
    # The caster's own kingdom (leader_id=1 -> kingdom_id=1, see
    # _gir_state()) already sees every destroyed army via their own
    # private describe_cast() view -- no duplicate notice here.
    state, battle_coord, _watcher_coord = _gir_state()
    board_width = NORMAL_MAP_BOUNDS[0]
    state.add_leader(LeaderState(1, 1, "Caster", battle_coord))
    request = CastRequest(spell=Spell.TORNADO, target=encode_hex_number(battle_coord, board_width))
    destroyed = [ArmyState(20, 1, ArmyType.LEGION, Quality.AVERAGE, battle_coord)]
    result = CastExecutionResult(request, applied=True, tornado_destroyed=destroyed)
    results = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.CAST, result=result, error=None)
    ]

    record_spell_world_events(state, results, ScriptedRandom([]), board_width=board_width)

    assert state.tornado_victim_notices_by_kingdom == {}


def test_record_spell_world_events_tornado_skips_an_unowned_destroyed_army():
    state, battle_coord, _watcher_coord = _gir_state()
    board_width = NORMAL_MAP_BOUNDS[0]
    state.add_leader(LeaderState(1, 1, "Caster", battle_coord))
    request = CastRequest(spell=Spell.TORNADO, target=encode_hex_number(battle_coord, board_width))
    destroyed = [ArmyState(20, None, ArmyType.LEGION, Quality.AVERAGE, battle_coord)]
    result = CastExecutionResult(request, applied=True, tornado_destroyed=destroyed)
    results = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.CAST, result=result, error=None)
    ]

    record_spell_world_events(state, results, ScriptedRandom([]), board_width=board_width)

    assert state.tornado_victim_notices_by_kingdom == {}


def test_record_spell_world_events_tornado_notifies_a_victim_kingdom_of_a_quality_downgrade():
    # Phase 948: _ATTorn's own real S_AA victim-kingdom notice for a
    # Giant-Fan-protected foreign army, the same treatment _ATDestr
    # already gets (Phase 939).
    state, battle_coord, _watcher_coord = _gir_state()
    board_width = NORMAL_MAP_BOUNDS[0]
    state.add_leader(LeaderState(1, 1, "Caster", battle_coord))
    state.add_kingdom(KingdomState(9, "Victimia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(9, 9)))
    request = CastRequest(spell=Spell.TORNADO, target=encode_hex_number(battle_coord, board_width))
    quality_downgraded = [ArmyState(21, 9, ArmyType.LT_CAVALRY, Quality.AVERAGE, battle_coord)]
    result = CastExecutionResult(request, applied=True, tornado_quality_downgraded=quality_downgraded)
    results = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.CAST, result=result, error=None)
    ]

    record_spell_world_events(state, results, ScriptedRandom([]), board_width=board_width)

    notices = state.tornado_victim_notices_by_kingdom[9]
    assert notices == [
        "In spring, The Tornado spell struck the 21st Light Cavalry in Border Fort and reduced them by one quality level."
    ]


def test_record_spell_world_events_plague_notifies_a_victim_kingdom():
    # Phase 947: SAY.PAS's own real _APDestr (Sps(Plague,S_AA)) --
    # confirmed by real fixture text (SE3__T6.K1) showing the "was hit by
    # a plague"/destroy-sentence pair appear together inside the
    # VICTIM's own letter, not the caster's, with that same letter's own
    # PROVINCES table confirming ownership of the affected province.
    state, battle_coord, _watcher_coord = _gir_state()
    board_width = NORMAL_MAP_BOUNDS[0]
    state.add_leader(LeaderState(1, 1, "Caster", battle_coord))
    state.add_kingdom(KingdomState(9, "Victimia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(9, 9)))
    request = CastRequest(spell=Spell.PLAGUE, target=encode_hex_number(battle_coord, board_width))
    destroyed = [ArmyState(96, 9, ArmyType.BOWMEN, Quality.AVERAGE, battle_coord)]
    result = CastExecutionResult(request, applied=True, plague_destroyed=destroyed)
    results = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.CAST, result=result, error=None)
    ]

    record_spell_world_events(state, results, ScriptedRandom([]), board_width=board_width)

    notices = state.plague_victim_notices_by_kingdom[9]
    assert notices == [
        "In spring, Border Fort was hit by a plague.The plague struck the 96th Bowmen in Border Fort and destroyed them."
    ]


def test_record_spell_world_events_plague_groups_multiple_destroyed_armies_for_one_victim():
    state, battle_coord, _watcher_coord = _gir_state()
    board_width = NORMAL_MAP_BOUNDS[0]
    state.add_leader(LeaderState(1, 1, "Caster", battle_coord))
    state.add_kingdom(KingdomState(9, "Victimia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(9, 9)))
    request = CastRequest(spell=Spell.PLAGUE, target=encode_hex_number(battle_coord, board_width))
    destroyed = [
        ArmyState(96, 9, ArmyType.BOWMEN, Quality.AVERAGE, battle_coord),
        ArmyState(269, 9, ArmyType.BOWMEN, Quality.AVERAGE, battle_coord),
    ]
    result = CastExecutionResult(request, applied=True, plague_destroyed=destroyed)
    results = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.CAST, result=result, error=None)
    ]

    record_spell_world_events(state, results, ScriptedRandom([]), board_width=board_width)

    notices = state.plague_victim_notices_by_kingdom[9]
    assert notices == [
        "In spring, Border Fort was hit by a plague."
        "The plague struck the 96th Bowmen in Border Fort and destroyed them."
        "The plague struck the 269th Bowmen in Border Fort and destroyed them."
    ]


def test_record_spell_world_events_plague_notifies_a_victim_kingdom_of_a_quality_downgrade():
    # Phase 948: _APSick's own real S_AA victim-kingdom notice, destroy
    # lines ordered first when a single cast affects both a destroyed and
    # a quality-downgraded army of the same victim Kingdom -- the one
    # confirmed real ordering (SE3__T11.K1's own Rejaf paragraph).
    state, battle_coord, _watcher_coord = _gir_state()
    board_width = NORMAL_MAP_BOUNDS[0]
    state.add_leader(LeaderState(1, 1, "Caster", battle_coord))
    state.add_kingdom(KingdomState(9, "Victimia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(9, 9)))
    request = CastRequest(spell=Spell.PLAGUE, target=encode_hex_number(battle_coord, board_width))
    destroyed = [ArmyState(109, 9, ArmyType.HVY_CAVALRY, Quality.AVERAGE, battle_coord)]
    quality_downgraded = [ArmyState(209, 9, ArmyType.WARG_RIDERS, Quality.AVERAGE, battle_coord)]
    result = CastExecutionResult(
        request, applied=True, plague_destroyed=destroyed, plague_quality_downgraded=quality_downgraded
    )
    results = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.CAST, result=result, error=None)
    ]

    record_spell_world_events(state, results, ScriptedRandom([]), board_width=board_width)

    notices = state.plague_victim_notices_by_kingdom[9]
    assert notices == [
        "In spring, Border Fort was hit by a plague."
        "The plague struck the 109th Heavy Cavalry in Border Fort and destroyed them."
        "The Plague spell struck the 209th Warg Riders in Border Fort and reduced them by one quality level."
    ]


def test_record_spell_world_events_plague_excludes_the_casters_own_kingdom():
    # The caster's own kingdom (leader_id=1 -> kingdom_id=1, see
    # _gir_state()) already sees every destroyed army via their own
    # private describe_cast()/render_plague_outcome() view -- no
    # duplicate notice here.
    state, battle_coord, _watcher_coord = _gir_state()
    board_width = NORMAL_MAP_BOUNDS[0]
    state.add_leader(LeaderState(1, 1, "Caster", battle_coord))
    request = CastRequest(spell=Spell.PLAGUE, target=encode_hex_number(battle_coord, board_width))
    destroyed = [ArmyState(96, 1, ArmyType.BOWMEN, Quality.AVERAGE, battle_coord)]
    result = CastExecutionResult(request, applied=True, plague_destroyed=destroyed)
    results = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.CAST, result=result, error=None)
    ]

    record_spell_world_events(state, results, ScriptedRandom([]), board_width=board_width)

    assert state.plague_victim_notices_by_kingdom == {}


def test_record_spell_world_events_plague_skips_an_unowned_destroyed_army():
    state, battle_coord, _watcher_coord = _gir_state()
    board_width = NORMAL_MAP_BOUNDS[0]
    state.add_leader(LeaderState(1, 1, "Caster", battle_coord))
    request = CastRequest(spell=Spell.PLAGUE, target=encode_hex_number(battle_coord, board_width))
    destroyed = [ArmyState(96, None, ArmyType.BOWMEN, Quality.AVERAGE, battle_coord)]
    result = CastExecutionResult(request, applied=True, plague_destroyed=destroyed)
    results = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.CAST, result=result, error=None)
    ]

    record_spell_world_events(state, results, ScriptedRandom([]), board_width=board_width)

    assert state.plague_victim_notices_by_kingdom == {}


def test_compose_letter_report_includes_plague_victim_notice_for_the_affected_kingdom():
    # Phase 947: state.plague_victim_notices_by_kingdom is set up
    # directly here, isolating compose_letter_report()'s own reading/
    # folding behavior from record_spell_world_events()'s own rendering,
    # tested separately.
    state = GameState()
    state.add_kingdom(KingdomState(3, "Watchia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(2, 2)))
    state.add_leader(LeaderState(3, 3, "Cedric", HexCoord(2, 2), is_king=True))
    state.plague_victim_notices_by_kingdom[3] = [
        "In spring, Tebessa was hit by a plague."
        "The plague struck the 96th Bowmen in Tebessa and destroyed them."
    ]

    lines_for_kingdom_3 = compose_letter_report([], state, 3, ScriptedRandom([]))

    assert "ACTION REPORT" in lines_for_kingdom_3
    assert (
        "In spring, Tebessa was hit by a plague."
        "The plague struck the 96th Bowmen in Tebessa and destroyed them."
    ) in lines_for_kingdom_3


# -- Phase 722: render_scar_terrain_cast_notice() / render_scar_terrain_zero() /
# render_scar_terrain_fite() / record_spell_world_events() (Scar Terrain) --


def test_render_scar_terrain_cast_notice_left_branch():
    rng = ScriptedRandom([0.1] * 10)
    assert render_scar_terrain_cast_notice("Border Fort", rng) == (
        "Border Fort was scarred by pestilence and polluting toxins, "
        "drastically driving down its taxable income."
    )


def test_render_scar_terrain_cast_notice_right_branch():
    rng = ScriptedRandom([0.9] * 10)
    assert render_scar_terrain_cast_notice("Border Fort", rng) == (
        "Border Fort was scarred and blighted by locust swarms and evil magic toxins, "
        "inevitably reducing its property values and tax base."
    )


def test_render_scar_terrain_zero_land():
    rng = ScriptedRandom([])
    assert render_scar_terrain_zero("Border Fort", is_sea=False, rng=rng) == (
        "Border Fort was magically changed into a wasteland, and its inhabitants all died or wandered away."
    )


def test_render_scar_terrain_zero_sea():
    rng = ScriptedRandom([])
    assert render_scar_terrain_zero("Border Fort", is_sea=True, rng=rng) == (
        "Border Fort was magically changed into a polluted sea, and its inhabitants all died or wandered away."
    )


def test_render_scar_terrain_fite():
    rng = ScriptedRandom([])
    assert render_scar_terrain_fite("Orcish", "Phalanx", rng) == (
        "A wandering tribe of Orcish, who fight as Phalanx, settled there, adapting themselves to the scarred terrain."
    )


def test_record_spell_world_events_scar_terrain_no_collapse_records_only_the_cast_notice():
    state, battle_coord, _watcher_coord = _gir_state()
    board_width = NORMAL_MAP_BOUNDS[0]
    request = CastRequest(spell=Spell.SCAR_TERRAIN, target=encode_hex_number(battle_coord, board_width))
    result = CastExecutionResult(request, applied=True, scar_terrain_collapsed=False)
    results = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.CAST, result=result, error=None)
    ]

    record_spell_world_events(state, results, ScriptedRandom([0.1] * 10), board_width=board_width)

    assert len(state.world_events) == 1
    assert state.world_events[0].lines == [
        "In spring, Border Fort was scarred by pestilence and polluting toxins, "
        "drastically driving down its taxable income."
    ]


def test_record_spell_world_events_scar_terrain_sea_collapse_has_no_fite_lines():
    state, battle_coord, _watcher_coord = _gir_state()
    board_width = NORMAL_MAP_BOUNDS[0]
    province = state.provinces[battle_coord]
    province.terrain = Terrain.SEA
    province.race = Race.NO_RACE
    request = CastRequest(spell=Spell.SCAR_TERRAIN, target=encode_hex_number(battle_coord, board_width))
    result = CastExecutionResult(request, applied=True, scar_terrain_collapsed=True)
    results = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.CAST, result=result, error=None)
    ]

    record_spell_world_events(state, results, ScriptedRandom([0.1] * 10), board_width=board_width)

    assert len(state.world_events) == 1
    assert state.world_events[0].lines == [
        "In spring, Border Fort was scarred by pestilence and polluting toxins, "
        "drastically driving down its taxable income.",
        "In spring, Border Fort was magically changed into a polluted sea, and its inhabitants all died or wandered away.",
    ]


def test_record_spell_world_events_scar_terrain_land_collapse_both_slots_records_two_fite_lines():
    state, battle_coord, _watcher_coord = _gir_state()
    board_width = NORMAL_MAP_BOUNDS[0]
    province = state.provinces[battle_coord]
    province.race = Race.ORCISH
    province.recruit_type_1 = ArmyType.PHALANX
    province.recruit_type_2 = ArmyType.WARG_RIDERS
    request = CastRequest(spell=Spell.SCAR_TERRAIN, target=encode_hex_number(battle_coord, board_width))
    result = CastExecutionResult(request, applied=True, scar_terrain_collapsed=True)
    results = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.CAST, result=result, error=None)
    ]

    record_spell_world_events(state, results, ScriptedRandom([0.1] * 10), board_width=board_width)

    assert len(state.world_events) == 1
    lines = state.world_events[0].lines
    assert len(lines) == 4
    assert lines[1] == "In spring, Border Fort was magically changed into a wasteland, and its inhabitants all died or wandered away."
    assert lines[2] == (
        "In spring, A wandering tribe of Orc, who fight as Phalanx, "
        "settled there, adapting themselves to the scarred terrain."
    )
    assert lines[3] == (
        "In spring, A wandering tribe of Orc, who fight as Wargs, "
        "settled there, adapting themselves to the scarred terrain."
    )


def test_record_spell_world_events_scar_terrain_land_collapse_one_slot_records_one_fite_line():
    state, battle_coord, _watcher_coord = _gir_state()
    board_width = NORMAL_MAP_BOUNDS[0]
    province = state.provinces[battle_coord]
    province.race = Race.TROLLISH
    province.recruit_type_1 = ArmyType.TROLLS
    province.recruit_type_2 = None
    request = CastRequest(spell=Spell.SCAR_TERRAIN, target=encode_hex_number(battle_coord, board_width))
    result = CastExecutionResult(request, applied=True, scar_terrain_collapsed=True)
    results = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.CAST, result=result, error=None)
    ]

    record_spell_world_events(state, results, ScriptedRandom([0.1] * 10), board_width=board_width)

    lines = state.world_events[0].lines
    assert len(lines) == 3
    assert lines[2] == (
        "In spring, A wandering tribe of Troll, who fight as Trolls, "
        "settled there, adapting themselves to the scarred terrain."
    )


def test_record_spell_world_events_scar_terrain_duplicate_recruit_types_no_dedup():
    state, battle_coord, _watcher_coord = _gir_state()
    board_width = NORMAL_MAP_BOUNDS[0]
    province = state.provinces[battle_coord]
    province.race = Race.ORCISH
    province.recruit_type_1 = ArmyType.PHALANX
    province.recruit_type_2 = ArmyType.PHALANX
    request = CastRequest(spell=Spell.SCAR_TERRAIN, target=encode_hex_number(battle_coord, board_width))
    result = CastExecutionResult(request, applied=True, scar_terrain_collapsed=True)
    results = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.CAST, result=result, error=None)
    ]

    record_spell_world_events(state, results, ScriptedRandom([0.1] * 10), board_width=board_width)

    lines = state.world_events[0].lines
    assert len(lines) == 4
    assert lines[2] == lines[3] == (
        "In spring, A wandering tribe of Orc, who fight as Phalanx, "
        "settled there, adapting themselves to the scarred terrain."
    )


# -- Phase 234: record_plague_spread_world_events() --


def test_record_plague_spread_world_events_records_a_newly_infected_province():
    state, battle_coord, _watcher_coord = _gir_state()
    results = [
        PhaseDispatchResult(
            leader_id=0, segment_index=-1, phase_label="plague-spread", action=None, result=battle_coord, error=None
        )
    ]

    record_plague_spread_world_events(state, results, ScriptedRandom([]))

    assert len(state.world_events) == 1
    event = state.world_events[0]
    assert event.coord == battle_coord
    assert event.lines == ["Border Fort was hit by a plague."]


def test_record_plague_spread_world_events_ignores_other_phase_labels():
    state, battle_coord, _watcher_coord = _gir_state()
    results = [
        PhaseDispatchResult(
            leader_id=0, segment_index=-1, phase_label="forced-rebattle", action=None, result=battle_coord, error=None
        )
    ]

    record_plague_spread_world_events(state, results, ScriptedRandom([]))

    assert state.world_events == []


def test_describe_general_intelligence_report_shows_a_plague_spread_event():
    state, battle_coord, _watcher_coord = _gir_state()
    results = [
        PhaseDispatchResult(
            leader_id=0, segment_index=-1, phase_label="plague-spread", action=None, result=battle_coord, error=None
        )
    ]
    record_plague_spread_world_events(state, results, ScriptedRandom([]))

    lines = describe_general_intelligence_report(state, 3)

    assert lines == [
        "GENERAL INTELLIGENCE REPORT",
        "Kingdom of Attackia (#1):",
        "Border Fort was hit by a plague.",
    ]


def test_describe_general_intelligence_report_shows_a_recorded_plague():
    state, battle_coord, _watcher_coord = _gir_state()
    board_width = NORMAL_MAP_BOUNDS[0]
    request = CastRequest(spell=Spell.PLAGUE, target=encode_hex_number(battle_coord, board_width))
    result = CastExecutionResult(request, applied=True)
    results = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.CAST, result=result, error=None)
    ]
    record_spell_world_events(state, results, ScriptedRandom([]), board_width=board_width)

    lines = describe_general_intelligence_report(state, 3)

    assert lines == [
        "GENERAL INTELLIGENCE REPORT",
        "Kingdom of Attackia (#1):",
        "In spring, Border Fort was hit by a plague.",
    ]


# -- Phase 257: SEASON_NAME + _season_phrase_for_phase_label (via the season
# prefix threaded into record_battle_world_events/record_spell_world_events)
# + render_fly_move_world_event + record_move_world_events --


def test_season_name_covers_all_five_real_phase_indices():
    assert SEASON_NAME == {
        0: "spring",
        1: "early summer",
        2: "late summer",
        3: "fall",
        4: "early winter",
    }


# -- Phase 589: SPRING.X/ESUMMER.X/LSUMMER.X/FALL.X/EWINTER.X --


def test_season_transition_prefix_advent_templates_cover_all_five_seasons():
    assert set(SEASON_TRANSITION_TEMPLATE.keys()) == set(SEASON_NAME.keys())
    assert set(SEASON_PREFIX_TEMPLATE.keys()) == set(SEASON_NAME.keys())
    assert set(SEASON_ADVENT_TEMPLATE.keys()) == set(SEASON_NAME.keys())


def test_season_prefix_template_matches_yak_pas_own_confirmed_call_site():
    # SEASON_NAME's own docstring already cites YAK.PAS's real
    # `Concat('In ', seasname[...], ', ')` call site -- this is the
    # real source template behind that simplified approximation.
    from ak_engine.report.prose import render

    rng = ScriptedRandom([0.1] * 10)
    assert render(SEASON_PREFIX_TEMPLATE[0], {}, rng=rng) == "in spring, "


def test_season_transition_template_only_spring_has_the_optional_character_clause():
    from ak_engine.report.prose import render

    rng = ScriptedRandom([0.99] * 10)
    for season in (1, 2, 3, 4):
        assert "<" not in SEASON_TRANSITION_TEMPLATE[season]
        assert ">" not in SEASON_TRANSITION_TEMPLATE[season]
    result = render(
        SEASON_TRANSITION_TEMPLATE[0], {"<": "Aldric", ">": "Aldric's"}, rng=rng
    )
    assert result == (
        "frigid winter melted into fragrant spring, and Aldric made "
        "ready to carry out Aldric's imperial assignments."
    )


def test_season_advent_template_only_spring_is_a_full_sentence():
    from ak_engine.report.prose import render

    for season in (1, 2, 3, 4):
        assert SEASON_ADVENT_TEMPLATE[season].endswith("_")
        assert "<" not in SEASON_ADVENT_TEMPLATE[season]
    rng = ScriptedRandom([0.1] * 10)
    result = render(SEASON_ADVENT_TEMPLATE[0], {"<": "Aldric", ">": "Aldric's"}, rng=rng)
    assert result == "with the advent of the spring season Aldric prepared to quench Aldric's thirst for adventure."


def test_record_battle_world_events_prefixes_the_season_for_a_real_phase_label():
    state, battle_coord, _watcher_coord = _gir_state()
    report = BattleReport(
        battle_result=BattleResult(winner="attacker"), conquered=True,
        province_coord=battle_coord, attacker_kingdom_id=1, defender_kingdom_id=2,
    )
    results = [
        PhaseDispatchResult(
            leader_id=1, segment_index=0, phase_label="P2", action=ActionCode.LMOVE, result=report, error=None
        )
    ]

    record_battle_world_events(state, results, ScriptedRandom([0.1, 0.1], choice_indices=[0]))

    assert state.world_events[0].lines == ["In late summer, the forces of Attackia (#1) broke through and were victorious."]


# -- Phase 711: record_battle_narratives --------------------------------------


def test_record_battle_narratives_populates_both_kingdoms_with_identical_content():
    state, battle_coord, _watcher_coord = _gir_state()
    column = _column(bres=3, attacker_source_id=10, defender_source_id=20)
    battle_result = BattleResult(winner="attacker", columns=[column])
    report = BattleReport(
        battle_result=battle_result,
        conquered=True,
        destroyed_army_ids=[20],
        province_coord=battle_coord,
        attacker_kingdom_id=1,
        defender_kingdom_id=2,
    )
    results = [
        PhaseDispatchResult(leader_id=0, segment_index=-1, phase_label="forced-rebattle", action=None, result=report, error=None)
    ]
    rng = ScriptedRandom([0.1, 0.1, 0.1, 0.1, 0.1], choice_indices=[0, 0, 0])

    record_battle_narratives(state, results, rng)

    assert state.battle_narratives_by_kingdom[1] == state.battle_narratives_by_kingdom[2]
    assert state.battle_narratives_by_kingdom[1] != []
    assert any("Attackia" in line for line in state.battle_narratives_by_kingdom[1])


def test_record_battle_narratives_skips_a_report_missing_a_kingdom_id():
    state, battle_coord, _watcher_coord = _gir_state()
    report = BattleReport(
        battle_result=BattleResult(winner="attacker"),
        conquered=True,
        province_coord=battle_coord,
        attacker_kingdom_id=1,
        defender_kingdom_id=None,
    )
    results = [
        PhaseDispatchResult(leader_id=0, segment_index=-1, phase_label="forced-rebattle", action=None, result=report, error=None)
    ]

    record_battle_narratives(state, results, ScriptedRandom([0.1, 0.1], choice_indices=[0]))

    assert state.battle_narratives_by_kingdom == {}


def test_record_battle_narratives_resolves_real_retreat_destination_names():
    state, battle_coord, watcher_coord = _gir_state()
    state.add_army(ArmyState(201, kingdom_id=2, army_type=ArmyType.LEGION, quality=Quality.AVERAGE, location=watcher_coord))
    column = BattleColumnResult(
        attacker_strength=10.0,
        defender_strength=10.0,
        bres=1,
        attacker_won=True,
        cluck_index=20,
        attacker_units=[BattleUnit(ArmyType.GARRISON, 10.0, source_id=101)],
        defender_units=[BattleUnit(ArmyType.LEGION, 10.0, source_id=201)],
    )
    report = BattleReport(
        battle_result=BattleResult(winner="attacker", columns=[column]),
        conquered=False,
        retreated_army_ids=[201],
        retreat_destination_coord={201: watcher_coord},
        province_coord=battle_coord,
        attacker_kingdom_id=1,
        defender_kingdom_id=2,
    )
    results = [
        PhaseDispatchResult(leader_id=0, segment_index=-1, phase_label="forced-rebattle", action=None, result=report, error=None)
    ]
    rng = ScriptedRandom([0.1] * 20, choice_indices=[0] * 10)

    record_battle_narratives(state, results, rng)

    assert any("retreated" in line for line in state.battle_narratives_by_kingdom[1])


def test_record_battle_narratives_deduplicates_a_multi_attacker_shared_battle_report():
    # Phase 844: same shared-BattleReport fan-out as record_battle_
    # world_events()'s own sibling regression test above -- before this
    # fix, both involved Kingdoms' own ACTION REPORT showed the full
    # narrative once per united leader instead of once per real battle.
    def _build_report():
        column = _column(bres=3, attacker_source_id=10, defender_source_id=20)
        battle_result = BattleResult(winner="attacker", columns=[column])
        return BattleReport(
            battle_result=battle_result,
            conquered=True,
            destroyed_army_ids=[20],
            province_coord=battle_coord,
            attacker_kingdom_id=1,
            defender_kingdom_id=2,
        )

    class _FakeBattle:
        def __init__(self, report):
            self.report = report

    class _FakeMultiAttackerMoveResult:
        def __init__(self, report):
            self.battle = _FakeBattle(report)

    state, battle_coord, _watcher_coord = _gir_state()
    single_report = _build_report()
    single_results = [
        PhaseDispatchResult(
            leader_id=101, segment_index=0, phase_label="P0", action=ActionCode.LMOVE,
            result=_FakeMultiAttackerMoveResult(single_report), error=None,
        )
    ]
    record_battle_narratives(state, single_results, ScriptedRandom([0.1, 0.1, 0.1, 0.1, 0.1], choice_indices=[0, 0, 0]))
    single_run_lines = list(state.battle_narratives_by_kingdom[1])

    state2, battle_coord, _watcher_coord = _gir_state()
    shared_report = _build_report()
    shared_results = [
        PhaseDispatchResult(
            leader_id=101, segment_index=0, phase_label="P0", action=ActionCode.LMOVE,
            result=_FakeMultiAttackerMoveResult(shared_report), error=None,
        ),
        PhaseDispatchResult(
            leader_id=102, segment_index=0, phase_label="P0", action=ActionCode.LMOVE,
            result=_FakeMultiAttackerMoveResult(shared_report), error=None,
        ),
    ]
    record_battle_narratives(state2, shared_results, ScriptedRandom([0.1, 0.1, 0.1, 0.1, 0.1], choice_indices=[0, 0, 0]))

    assert state2.battle_narratives_by_kingdom[1] == single_run_lines
    assert state2.battle_narratives_by_kingdom[2] == single_run_lines


# -- Phase 713: render_blackmail_demand / record_blackmail_narratives ---------


def test_render_blackmail_demand_substitutes_amount_and_disambiguated_kingdom_number():
    rng = ScriptedRandom([0.1] * 15)

    line = render_blackmail_demand("Spymaster", "King Bob", 17, 3, rng)

    assert "17 gold" in line
    assert 'King 3 in this amount' in line
    assert "Spymaster" in line
    assert "King Bob" in line


def _blackmail_state():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Spydom", Race.HUMAN, Alignment.GOOD, HexCoord(0, 0)))
    state.add_kingdom(KingdomState(2, "Targetia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_leader(LeaderState(1, kingdom_id=1, name="Spymaster", location=HexCoord(0, 0)))
    state.add_leader(LeaderState(2, kingdom_id=2, name="King Bob", location=HexCoord(0, 0), is_king=True))
    return state


def test_record_blackmail_narratives_populates_both_kingdoms_with_identical_content():
    state = _blackmail_state()
    claim = BlackmailClaim(spy_leader_id=1, spy_kingdom_id=1, amount=15)
    state.kingdoms[2].pending_blackmail = claim
    result = TrailExecutionResult(spied_on=True, blackmail_claim=claim)
    results = [PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.TRAIL, result=result, error=None)]

    record_blackmail_narratives(state, results, ScriptedRandom([0.1] * 15))

    assert state.blackmail_narratives_by_kingdom[1] == state.blackmail_narratives_by_kingdom[2]
    assert state.blackmail_narratives_by_kingdom[1] != []
    assert any("Spymaster" in line and "King Bob" in line for line in state.blackmail_narratives_by_kingdom[1])


def test_record_blackmail_narratives_survives_the_spy_dying_later_the_same_turn():
    # Phase 845: a Spy can deliver a real Blackmail demand in an early
    # phase and then die in a LATER phase of the same turn (e.g. losing
    # a Challenge) -- the already-delivered demand must still be
    # narrated to both the spy's own Kingdom and the victim. A bare,
    # alive-only state.leaders.get(claim.spy_leader_id) silently dropped
    # the whole line for both sides once the spy was dead by report-
    # generation time.
    state = _blackmail_state()
    claim = BlackmailClaim(spy_leader_id=1, spy_kingdom_id=1, amount=15)
    state.kingdoms[2].pending_blackmail = claim
    result = TrailExecutionResult(spied_on=True, blackmail_claim=claim)
    results = [PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.TRAIL, result=result, error=None)]
    state.remove_leader(1)  # the spy died in a later phase this same turn

    record_blackmail_narratives(state, results, ScriptedRandom([0.1] * 15))

    assert state.blackmail_narratives_by_kingdom[1] == state.blackmail_narratives_by_kingdom[2]
    assert any("Spymaster" in line and "King Bob" in line for line in state.blackmail_narratives_by_kingdom[1])


def test_record_blackmail_narratives_skips_a_non_trail_result():
    state = _blackmail_state()
    results = [PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.LMOVE, result=object(), error=None)]

    record_blackmail_narratives(state, results, ScriptedRandom([]))

    assert state.blackmail_narratives_by_kingdom == {}


def test_record_blackmail_narratives_skips_a_trail_result_with_no_claim():
    state = _blackmail_state()
    result = TrailExecutionResult(spied_on=True, blackmail_claim=None)
    results = [PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.TRAIL, result=result, error=None)]

    record_blackmail_narratives(state, results, ScriptedRandom([]))

    assert state.blackmail_narratives_by_kingdom == {}


def test_record_blackmail_narratives_skips_when_the_claim_is_not_found_on_any_kingdom():
    state = _blackmail_state()
    claim = BlackmailClaim(spy_leader_id=1, spy_kingdom_id=1, amount=15)  # never stored as pending anywhere
    result = TrailExecutionResult(spied_on=True, blackmail_claim=claim)
    results = [PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.TRAIL, result=result, error=None)]

    record_blackmail_narratives(state, results, ScriptedRandom([]))

    assert state.blackmail_narratives_by_kingdom == {}


def test_compose_letter_report_includes_blackmail_narrative_for_both_involved_kingdoms():
    state = _blackmail_state()
    claim = BlackmailClaim(spy_leader_id=1, spy_kingdom_id=1, amount=15)
    state.kingdoms[2].pending_blackmail = claim
    result = TrailExecutionResult(spied_on=True, blackmail_claim=claim)
    results = [PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.TRAIL, result=result, error=None)]
    record_blackmail_narratives(state, results, ScriptedRandom([0.1] * 15))

    spy_letter = compose_letter_report(results, state, 1, ScriptedRandom([]))
    target_letter = compose_letter_report(results, state, 2, ScriptedRandom([]))

    assert any("Spymaster" in line for line in spy_letter)
    assert any("Spymaster" in line for line in target_letter)


def test_render_fly_move_world_event_renders_the_lfly_template():
    rng = ScriptedRandom([0.1, 0.1])

    line = render_fly_move_world_event("Tlazolteotl", "Waterford", rng)

    assert line == "Tlazolteotl flew into Waterford."


def _fake_move_result(
    moved: bool, new_location: HexCoord | None, *, wind_walking: bool = False, entered_foreign_illusory_fog: bool = False
):
    class _FakeMoveResult:
        pass

    result = _FakeMoveResult()
    result.moved = moved
    result.new_location = new_location
    result.wind_walking = wind_walking
    result.entered_foreign_illusory_fog = entered_foreign_illusory_fog
    return result


def test_record_move_world_events_records_a_fly_event_for_an_all_overflight_army():
    state, battle_coord, _watcher_coord = _gir_state()
    state.add_leader(LeaderState(1, 1, "Tlazolteotl", battle_coord))
    state.add_army(ArmyState(10, 1, ArmyType.DRAGON_WING, Quality.AVERAGE, battle_coord, commanded_by=1))
    results = [
        PhaseDispatchResult(
            leader_id=1, segment_index=0, phase_label="P2", action=ActionCode.LMOVE,
            result=_fake_move_result(True, battle_coord), error=None,
        )
    ]

    record_move_world_events(state, results, ScriptedRandom([0.1, 0.1]))

    assert len(state.world_events) == 1
    event = state.world_events[0]
    assert event.coord == battle_coord
    assert event.lines == ["In late summer, Tlazolteotl flew into Border Fort."]


def test_record_move_world_events_skips_a_mixed_overflight_and_ground_army():
    state, battle_coord, _watcher_coord = _gir_state()
    state.add_leader(LeaderState(1, 1, "Tlazolteotl", battle_coord))
    state.add_army(ArmyState(10, 1, ArmyType.DRAGON_WING, Quality.AVERAGE, battle_coord, commanded_by=1))
    state.add_army(ArmyState(11, 1, ArmyType.BOWMEN, Quality.AVERAGE, battle_coord, commanded_by=1))
    results = [
        PhaseDispatchResult(
            leader_id=1, segment_index=0, phase_label="P2", action=ActionCode.LMOVE,
            result=_fake_move_result(True, battle_coord), error=None,
        )
    ]

    record_move_world_events(state, results, ScriptedRandom([]))

    assert state.world_events == []


def test_record_move_world_events_skips_a_mover_with_no_army_at_the_destination():
    state, battle_coord, _watcher_coord = _gir_state()
    state.add_leader(LeaderState(1, 1, "Tlazolteotl", battle_coord))
    results = [
        PhaseDispatchResult(
            leader_id=1, segment_index=0, phase_label="P2", action=ActionCode.LMOVE,
            result=_fake_move_result(True, battle_coord), error=None,
        )
    ]

    record_move_world_events(state, results, ScriptedRandom([]))

    assert state.world_events == []


def test_record_move_world_events_records_a_wind_walk_event_for_a_leader_travelling_alone():
    # Phase 846: the real _LWWalk trigger names only the mover, never an
    # accompanying army ("the great Wind Spirits... carry the mage or a
    # co-located character into the sky") -- a wind-walking leader who
    # moves with no army at all (`MoveExecutionResult.moved_without_
    # armies`, Phase 769) must still get this notice, unlike an ordinary
    # (non-wind-walking) armless mover, which stays private.
    state, battle_coord, _watcher_coord = _gir_state()
    state.add_leader(LeaderState(1, 1, "Tlazolteotl", battle_coord))
    results = [
        PhaseDispatchResult(
            leader_id=1, segment_index=0, phase_label="P2", action=ActionCode.LMOVE,
            result=_fake_move_result(True, battle_coord, wind_walking=True), error=None,
        )
    ]

    record_move_world_events(state, results, ScriptedRandom([0.1, 0.1]))

    assert len(state.world_events) == 1
    assert state.world_events[0].lines == ["In late summer, Tlazolteotl rode the Mystic Winds into Border Fort."]


def test_record_move_world_events_skips_a_result_that_did_not_move():
    state, battle_coord, _watcher_coord = _gir_state()
    state.add_leader(LeaderState(1, 1, "Tlazolteotl", battle_coord))
    state.add_army(ArmyState(10, 1, ArmyType.DRAGON_WING, Quality.AVERAGE, battle_coord, commanded_by=1))
    results = [
        PhaseDispatchResult(
            leader_id=1, segment_index=0, phase_label="P2", action=ActionCode.LMOVE,
            result=_fake_move_result(False, battle_coord), error=None,
        )
    ]

    record_move_world_events(state, results, ScriptedRandom([]))

    assert state.world_events == []


def test_render_wind_walk_move_world_event_renders_the_lwwalk_template():
    rng = ScriptedRandom([0.1, 0.1])

    line = render_wind_walk_move_world_event("Tlazolteotl", "Waterford", rng)

    assert line == "Tlazolteotl rode the Mystic Winds into Waterford."


def test_record_move_world_events_records_a_wind_walk_event_for_an_ordinary_ground_army():
    # Phase 634: wind_walking=True renders _LWWalk even for an ordinary,
    # non-overflight army -- the whole point of the spell is moving
    # ground units as if they were air units.
    state, battle_coord, _watcher_coord = _gir_state()
    state.add_leader(LeaderState(1, 1, "Tlazolteotl", battle_coord))
    state.add_army(ArmyState(10, 1, ArmyType.BOWMEN, Quality.AVERAGE, battle_coord, commanded_by=1))
    results = [
        PhaseDispatchResult(
            leader_id=1, segment_index=0, phase_label="P2", action=ActionCode.LMOVE,
            result=_fake_move_result(True, battle_coord, wind_walking=True), error=None,
        )
    ]

    record_move_world_events(state, results, ScriptedRandom([0.1, 0.1]))

    assert len(state.world_events) == 1
    assert state.world_events[0].lines == ["In late summer, Tlazolteotl rode the Mystic Winds into Border Fort."]


def test_record_move_world_events_wind_walking_takes_priority_over_the_overflight_check():
    # A wind-walking mover whose own armies also happen to be natively
    # overflight-type still gets the more specific magical-effect
    # notice, not the passive army-composition one -- a documented,
    # unsourced tie-break (see module-level comment), not an accident.
    state, battle_coord, _watcher_coord = _gir_state()
    state.add_leader(LeaderState(1, 1, "Tlazolteotl", battle_coord))
    state.add_army(ArmyState(10, 1, ArmyType.DRAGON_WING, Quality.AVERAGE, battle_coord, commanded_by=1))
    results = [
        PhaseDispatchResult(
            leader_id=1, segment_index=0, phase_label="P2", action=ActionCode.LMOVE,
            result=_fake_move_result(True, battle_coord, wind_walking=True), error=None,
        )
    ]

    record_move_world_events(state, results, ScriptedRandom([0.1, 0.1]))

    assert len(state.world_events) == 1
    assert "rode the Mystic Winds" in state.world_events[0].lines[0]
    assert "flew" not in state.world_events[0].lines[0]


# -- Phase 754: `Desktop/MOVE.md` section 21.3 -- foreign Illusory Fog entry --


def test_render_illusory_fog_foreign_entry_note_renders_the_template():
    rng = ScriptedRandom([0.1] * 15)

    line = render_illusory_fog_foreign_entry_note("Waterford", rng)

    assert line.startswith("Waterford was ")
    assert line.endswith(".")
    assert "fog" in line or "mist" in line


def test_record_illusory_fog_foreign_entry_world_events_records_when_flagged():
    state, battle_coord, _watcher_coord = _gir_state()
    state.add_leader(LeaderState(1, 1, "Tlazolteotl", battle_coord))
    results = [
        PhaseDispatchResult(
            leader_id=1, segment_index=0, phase_label="P2", action=ActionCode.LMOVE,
            result=_fake_move_result(True, battle_coord, entered_foreign_illusory_fog=True), error=None,
        )
    ]

    record_illusory_fog_foreign_entry_world_events(state, results, ScriptedRandom([0.1] * 15))

    assert len(state.world_events) == 1
    assert state.world_events[0].lines[0].startswith("In late summer, Border Fort was ")


def test_record_illusory_fog_foreign_entry_world_events_skips_when_not_flagged():
    state, battle_coord, _watcher_coord = _gir_state()
    state.add_leader(LeaderState(1, 1, "Tlazolteotl", battle_coord))
    results = [
        PhaseDispatchResult(
            leader_id=1, segment_index=0, phase_label="P2", action=ActionCode.LMOVE,
            result=_fake_move_result(True, battle_coord, entered_foreign_illusory_fog=False), error=None,
        )
    ]

    record_illusory_fog_foreign_entry_world_events(state, results, ScriptedRandom([]))

    assert state.world_events == []


def test_record_illusory_fog_foreign_entry_world_events_skips_a_result_that_did_not_move():
    state, battle_coord, _watcher_coord = _gir_state()
    results = [
        PhaseDispatchResult(
            leader_id=1, segment_index=0, phase_label="P2", action=ActionCode.LMOVE,
            result=_fake_move_result(False, None, entered_foreign_illusory_fog=True), error=None,
        )
    ]

    record_illusory_fog_foreign_entry_world_events(state, results, ScriptedRandom([]))

    assert state.world_events == []


# -- Phase 410: record_uncontested_conquest_world_events() --------------


def _fake_conquest_result(conquered: bool, new_location: HexCoord | None, battle_report=None):
    class _FakeConquestResult:
        pass

    result = _FakeConquestResult()
    result.conquered = conquered
    result.new_location = new_location
    result.battle_report = battle_report
    return result


def test_record_uncontested_conquest_world_events_records_a_conquest_event():
    state, battle_coord, _watcher_coord = _gir_state()
    state.add_leader(LeaderState(1, 1, "Attackia", battle_coord))
    results = [
        PhaseDispatchResult(
            leader_id=1, segment_index=0, phase_label="P2", action=ActionCode.LMOVE,
            result=_fake_conquest_result(True, battle_coord), error=None,
        )
    ]

    record_uncontested_conquest_world_events(state, results, ScriptedRandom([0.1, 0.1], choice_indices=[0]))

    assert len(state.world_events) == 1
    event = state.world_events[0]
    assert event.coord == battle_coord
    assert event.lines == ["In late summer, Attackia's forces conquered Border Fort without any major battles."]


def test_record_uncontested_conquest_world_events_survives_the_conqueror_dying_later_the_same_turn():
    # Phase 847: a Hero can uncontestedly conquer a province in an early
    # phase and then die in a LATER phase of the same turn (e.g. losing
    # a Challenge) -- the already-happened conquest must still be
    # narrated. A bare, alive-only state.leaders.get(entry.leader_id)
    # silently dropped the whole notice once the conqueror was dead by
    # report-generation time.
    state, battle_coord, _watcher_coord = _gir_state()
    state.add_leader(LeaderState(1, 1, "Attackia", battle_coord))
    results = [
        PhaseDispatchResult(
            leader_id=1, segment_index=0, phase_label="P2", action=ActionCode.LMOVE,
            result=_fake_conquest_result(True, battle_coord), error=None,
        )
    ]
    state.remove_leader(1)  # the conqueror died in a later phase this same turn

    record_uncontested_conquest_world_events(state, results, ScriptedRandom([0.1, 0.1], choice_indices=[0]))

    assert len(state.world_events) == 1
    event = state.world_events[0]
    assert event.coord == battle_coord
    assert event.lines == ["In late summer, Attackia's forces conquered Border Fort without any major battles."]


def test_record_uncontested_conquest_world_events_skips_a_battle_won_conquest():
    # A real BattleReport means record_battle_world_events() already
    # recorded this one via its own winner sentence -- must not double-record.
    state, battle_coord, _watcher_coord = _gir_state()
    state.add_leader(LeaderState(1, 1, "Attackia", battle_coord))
    report = BattleReport(
        battle_result=BattleResult(winner="attacker"), conquered=True,
        province_coord=battle_coord, attacker_kingdom_id=1, defender_kingdom_id=2,
    )
    results = [
        PhaseDispatchResult(
            leader_id=1, segment_index=0, phase_label="P2", action=ActionCode.LMOVE,
            result=_fake_conquest_result(True, battle_coord, battle_report=report), error=None,
        )
    ]

    record_uncontested_conquest_world_events(state, results, ScriptedRandom([]))

    assert state.world_events == []


def test_record_uncontested_conquest_world_events_skips_an_unconquered_move():
    state, battle_coord, _watcher_coord = _gir_state()
    state.add_leader(LeaderState(1, 1, "Attackia", battle_coord))
    results = [
        PhaseDispatchResult(
            leader_id=1, segment_index=0, phase_label="P2", action=ActionCode.LMOVE,
            result=_fake_conquest_result(False, battle_coord), error=None,
        )
    ]

    record_uncontested_conquest_world_events(state, results, ScriptedRandom([]))

    assert state.world_events == []


def test_record_uncontested_conquest_world_events_skips_when_leader_missing():
    state, battle_coord, _watcher_coord = _gir_state()
    results = [
        PhaseDispatchResult(
            leader_id=1, segment_index=0, phase_label="P2", action=ActionCode.LMOVE,
            result=_fake_conquest_result(True, battle_coord), error=None,
        )
    ]

    record_uncontested_conquest_world_events(state, results, ScriptedRandom([]))

    assert state.world_events == []


# -- Phase 781: record_wandering_world_events() --------------------------


def _wandering_state():
    origin = HexCoord(5, 5)
    destination = HexCoord(6, 5)
    state = GameState()
    state.add_kingdom(KingdomState(1, "Origania", Race.HUMAN, Alignment.GOOD, origin))
    state.add_kingdom(KingdomState(2, "Destinia", Race.HUMAN, Alignment.NEUTRAL, destination))
    state.add_province(ProvinceState(origin, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, name="Origin Fort"))
    state.add_province(ProvinceState(destination, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2, name="Destinia Keep"))
    state.add_leader(LeaderState(90, 1, "King Origanus", origin, is_king=True))
    state.add_leader(LeaderState(91, 2, "King Destinus", destination, is_king=True))
    return state, origin, destination


def _wander_result(kind: str, entity_id: int, origin: HexCoord, destination: HexCoord) -> PhaseDispatchResult:
    return PhaseDispatchResult(
        leader_id=entity_id,
        segment_index=-1,
        phase_label="hero-wander" if kind == "hero" else "army-wander",
        action=None,
        result=WanderRelocation(kind, entity_id, origin, destination),
        error=None,
    )


def test_record_wandering_world_events_hero_records_departure_and_arrival():
    state, origin, destination = _wandering_state()
    state.add_leader(LeaderState(1, None, "Wanderer", destination))
    results = [_wander_result("hero", 1, origin, destination)]

    record_wandering_world_events(state, results, random.Random(1))

    assert len(state.world_events) == 2
    assert state.world_events[0].coord == origin
    assert "Wanderer" in state.world_events[0].lines[0]
    assert state.world_events[1].coord == destination
    assert "Wanderer" in state.world_events[1].lines[0]


def test_record_wandering_world_events_mercenary_army_records_departure_and_arrival():
    state, origin, destination = _wandering_state()
    state.add_army(ArmyState(300, None, ArmyType.BOWMEN, Quality.AVERAGE, destination))
    results = [_wander_result("army", 300, origin, destination)]

    record_wandering_world_events(state, results, random.Random(1))

    assert len(state.world_events) == 2
    assert state.world_events[0].coord == origin
    assert state.world_events[1].coord == destination


def test_record_wandering_world_events_no_departure_notice_when_origin_has_no_king():
    state, origin, destination = _wandering_state()
    state.leaders.pop(90)  # Origania now has no King on record
    state.add_leader(LeaderState(1, None, "Wanderer", destination))
    results = [_wander_result("hero", 1, origin, destination)]

    record_wandering_world_events(state, results, random.Random(1))

    assert len(state.world_events) == 1
    assert state.world_events[0].coord == destination


def test_record_wandering_world_events_no_arrival_notice_when_destination_owner_unchanged():
    state, origin, destination = _wandering_state()
    # Both provinces now belong to the same Kingdom -- no real "arrival
    # in a different Kingdom's own territory" to announce.
    state.provinces[destination].owner_kingdom_id = 1
    state.add_leader(LeaderState(1, None, "Wanderer", destination))
    results = [_wander_result("hero", 1, origin, destination)]

    record_wandering_world_events(state, results, random.Random(1))

    assert len(state.world_events) == 1
    assert state.world_events[0].coord == origin


def test_record_wandering_world_events_no_arrival_notice_when_destination_has_no_king():
    state, origin, destination = _wandering_state()
    state.leaders.pop(91)  # Destinia now has no King on record
    state.add_leader(LeaderState(1, None, "Wanderer", destination))
    results = [_wander_result("hero", 1, origin, destination)]

    record_wandering_world_events(state, results, random.Random(1))

    assert len(state.world_events) == 1
    assert state.world_events[0].coord == origin


def test_record_wandering_world_events_ignores_unrelated_entries():
    state, origin, destination = _wandering_state()
    results = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.WAIT, result=None, error=None)
    ]

    record_wandering_world_events(state, results, ScriptedRandom([]))

    assert state.world_events == []


def test_record_wandering_world_events_skips_when_entity_no_longer_exists():
    state, origin, destination = _wandering_state()
    results = [_wander_result("hero", 999, origin, destination)]

    record_wandering_world_events(state, results, ScriptedRandom([]))

    assert state.world_events == []
