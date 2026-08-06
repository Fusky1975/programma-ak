from __future__ import annotations

import pytest

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_naming import make_army_name
from ak_engine.models.army_type import ArmyType
from ak_engine.models.discovery import Discovery, describe_discovery_line
from ak_engine.models.feature import Feature, FeatureType
from ak_engine.models.game_state import ArmyState, GameState, KingdomState, LeaderState, ProvinceState
from ak_engine.models.item import ItemInstance
from ak_engine.models.kingdom import SkillTable
from ak_engine.models.magic_feature import MagicFeature
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.monster import Monster
from ak_engine.models.office import Office
from ak_engine.models.race import Race
from ak_engine.models.rumor import Rumor, RumorContent
from ak_engine.models.temper import Temper
from ak_engine.models.treasure import TREASURE_NAME, Treasure
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
    INHERIT_TEMPLATE,
    NEMESIS_TEMPLATE,
    PRACTICE_ALREADY_MAXED_TEMPLATE,
    PRACTICE_TUTORED_TEMPLATE,
    QUEST_BUT_THEN_TEMPLATE,
    SEASON_NAME,
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
    describe_general_intelligence_report,
    describe_imperial_office_report,
    describe_armies_report,
    describe_characters_report,
    describe_diplomacy_report,
    describe_feature_discovery,
    describe_finances_report,
    describe_letter_reports,
    describe_provinces_report,
    describe_aspy,
    describe_battle,
    describe_cast,
    describe_fire,
    describe_give,
    describe_hire,
    describe_practice,
    describe_pursue,
    describe_rumor,
    describe_search,
    describe_steal,
    describe_trail,
    describe_trail_intelligence,
    describe_use_mi,
    parse_template_choices,
    pick_variant,
    record_battle_world_events,
    record_move_world_events,
    record_plague_spread_world_events,
    record_spell_world_events,
    record_uncontested_conquest_world_events,
    render_bystander_spell_notice,
    render_flood_world_event,
    render_fly_move_world_event,
    render_illus_terrain_world_event,
    render_plague_world_event,
    render_already_allied,
    render_ally_proposed,
    render_ally_refused,
    render_assassination_attempt,
    render_assassination_failed,
    render_assassination_ordered,
    render_assassination_success,
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
    render_hire_accepted,
    render_hire_counter_offer,
    render_illegal_move_attempted,
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
    render_march,
    render_melee_attack,
    render_monster_offers_raid_truce,
    render_mortally_wounded,
    render_move_to_bow_range,
    render_move_to_melee_range,
    render_patrol_encounter,
    render_patrol_release,
    render_petrifying_gaze_hit,
    render_petrifying_gaze_missed,
    render_homeland_defense_morale,
    render_oratory_speech,
    render_monster_threat_death,
    render_cast_announcement,
    render_practice_already_maxed,
    render_practice_tutored,
    render_sage_discovery,
    render_sage_no_discovery,
    render_skill_book_read,
    render_pursuit_and_destroy,
    render_quest_errand_thanks,
    render_quote_of_the_week,
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
    render_spy_adjacent_owners,
    render_spy_army_type,
    render_spy_capital_province,
    render_spy_character_here,
    render_spy_elements_intro,
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
)
from ak_engine.models.enums import Ability, ActionCode, Spell
from ak_engine.models.weapon import Weapon
from ak_engine.turn.aspy_execution import SpottedCharacter, SpyReport
from ak_engine.turn.battle_line import BattleUnit
from ak_engine.turn.combat import Quality
from ak_engine.turn.battle_orchestrator import BattleReport
from ak_engine.turn.battle_luck import CLUCK2_REVERSAL_PHRASE
from ak_engine.turn.battle_resolution import BattleColumnResult, BattleResult
from ak_engine.turn.cast_decode import CastRequest
from ak_engine.turn.cast_execution import CastExecutionResult
from ak_engine.turn.challenge_execution import ChallengeExecutionResult
from ak_engine.turn.encounter import CombatRange, FireArrowShot
from ak_engine.turn.exploration import ExploreResult
from ak_engine.turn.hex_numbering import encode_hex_number
from ak_engine.turn.hire_fire_decode import FireRequest, HireRequest
from ak_engine.turn.movement import NORMAL_MAP_BOUNDS, MapBounds, neighbors
from ak_engine.turn.plan_dispatch import FireExecutionResult, HireExecutionResult, PhaseDispatchResult
from ak_engine.turn.practice_execution import PracticeExecutionResult
from ak_engine.turn.pursue_execution import PursueExecutionResult
from ak_engine.turn.search_execution import SearchExecutionResult
from ak_engine.turn.trade_execution import TradeExecutionResult
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


# -- render_bluck_narration / render_cluck_narration (Phase 388) -----------


def test_render_bluck_narration_reads_the_battle_results_own_index():
    assert render_bluck_narration(BattleResult(bluck_index=9)) == "no significant fortune"
    assert render_bluck_narration(BattleResult(bluck_index=1)) == "disastrous rear/supply rumor"


def test_render_cluck_narration_reads_the_columns_own_index_when_competitive():
    column = _column(bres=0)  # attacker_strength == defender_strength == 10.0, cluck_index=20
    rng = ScriptedRandom([0.99])  # miss the reversal check
    assert render_cluck_narration(column, rng) == "no decisive local event"


def test_render_cluck_narration_returns_none_when_the_column_is_not_competitive():
    column = BattleColumnResult(
        attacker_strength=10.0,
        defender_strength=1.0,  # ratio 10.0, outside the [0.4, 2.5] gate
        bres=1,
        attacker_won=True,
        cluck_index=20,
    )
    rng = ScriptedRandom([])
    assert render_cluck_narration(column, rng) is None


def test_render_cluck_narration_appends_the_reversal_phrase_when_the_roll_fires():
    column = _column(bres=0)  # cluck_index=20, inside the 13-27 reversal window
    rng = ScriptedRandom([0.0])  # beats the 33% threshold
    result = render_cluck_narration(column, rng)
    assert result == f"no decisive local event, {CLUCK2_REVERSAL_PHRASE}"


def test_render_cluck_narration_does_not_append_when_the_reversal_roll_misses():
    column = _column(bres=0)
    rng = ScriptedRandom([0.99])
    assert render_cluck_narration(column, rng) == "no decisive local event"


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


def test_describe_practice_renders_nothing_for_a_normal_failed_roll():
    result = PracticeExecutionResult(ability=0, skill_rose=False, new_skill=3, new_aptitude=5)
    rng = ScriptedRandom([])

    line = describe_practice(result, character_name="Aldric", ability_name="Tactics", rng=rng)

    assert line is None


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


# -- FINDFEAT.X in-person discovery narrative (Phase 245) -------------------


def test_describe_feature_discovery_first_variant():
    feature = Feature(feature_id=1, coord=HexCoord(0, 0), kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER)
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0])

    line = describe_feature_discovery(feature, "Aldric", "Ancient Valley", rng)

    assert line == "Aldric discovered a feature in Ancient Valley:  Dungeon  inhabited by Renegade Archer."


def test_describe_feature_discovery_picks_the_selected_variant():
    feature = Feature(feature_id=1, coord=HexCoord(0, 0), kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER)
    rng = ScriptedRandom([0.1] * 10, choice_indices=[3])

    line = describe_feature_discovery(feature, "Aldric", "Ancient Valley", rng)

    assert line == "Aldric found  Dungeon  in Ancient Valley, occupied by Renegade Archer."


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
    # RESURRECTION's own SPELL_CAST_ANNOUNCEMENT entry references the caster
    # a second time via <2 and the target via [1 -- same real duplicate-marker
    # shape render_battle_winner() already established for <2 (Phase 61).
    rng = ScriptedRandom([])
    result = render_cast_announcement(Spell.RESURRECTION, "Aldric", rng, target_name="Borin")
    assert result == "Aldric cast a Resurrection spell and Borin was resurrected by the spell cast by Aldric."


def test_render_cast_announcement_oratory_double_cast_clause_is_transcribed_honestly():
    # _LCast1's own CASE doesn't special-case Oratory as "complete" even
    # though SPNOTE.X2's own entry already reads as a full sentence -- the
    # real Pascal output really does redundantly say "cast a spell" twice.
    rng = ScriptedRandom([])
    result = render_cast_announcement(Spell.ORATORY, "Aldric", rng, target_name="Borin")
    assert result == "Aldric cast a Oratory spell and Aldric cast a spell giving magical powers of oratory to Borin."


def test_render_cast_announcement_charm_leading_period_and_r_choices():
    # Charm's own SPNOTE.X2 entry starts with a bare "." (a real, honestly
    # transcribed oddity, the same "transcribe verbatim, don't silently fix"
    # stance already taken for CONTROL_UNDEAD's truncation and the Mermen
    # "air-transport" wording, Phase 127). 3 "/R" choices, all scripted left.
    rng = ScriptedRandom([0.1, 0.1, 0.1])
    result = render_cast_announcement(Spell.CHARM, "Aldric", rng, target_name="Borin")
    assert result == "Aldric cast a Charm spell and .Aldric befriended Borin and used Aldric's respite to escape."


def test_render_cast_announcement_clairvoyance_double_cast_clause_is_transcribed_honestly():
    # Clairvoyance's own SPNOTE.X2 entry begins with "< cast a ~ spell
    # and..." too, so it duplicates the CONTINUED_TEMPLATE's own opening
    # the same way Oratory does (see the docstring's oddity list above) --
    # transcribed honestly, not silently fixed.
    rng = ScriptedRandom([])
    result = render_cast_announcement(Spell.CLAIRVOYANCE, "Aldric", rng, target_name="Borin")
    assert (
        result
        == "Aldric cast a Clairvoyance spell and Aldric cast a Clairvoyance spell "
        "and could see everything that happened to Borin."
    )


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


def test_describe_search_leader_killed_appends_mortally_wounded():
    result = SearchExecutionResult(accepted=True, combat_resolved=True, winner="monster", leader_killed=True)
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0, 0])

    lines = describe_search(result, character_name="Aldric", feature_name="Ancient Ruins", rng=rng)

    assert lines == [
        "Aldric approached the Ancient Ruins, intending to root out its mysteries.",
        "Aldric was mortally wounded.",
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
    rng = ScriptedRandom([0.1] * 10, choice_indices=[0, 0])

    lines = describe_search(result, character_name="Aldric", feature_name="Ancient Ruins", rng=rng)

    assert lines == [
        "Aldric approached the Ancient Ruins, intending to root out its mysteries.",
        "The Red Dragon breathes, and the impact deals 9 damage points.",
        "Aldric was mortally wounded.",
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
    rng = ScriptedRandom([0.1] * 30, choice_indices=[0, 0, 0, 0])

    lines = describe_search(result, character_name="Aldric", feature_name="Ancient Ruins", rng=rng)

    assert lines == [
        "Aldric approached the Ancient Ruins, intending to root out its mysteries.",
        "guardian curled guardian's phantasmal hand around Aldric's heart and squeezed it and inflicted 4 damage points.",
        "Aldric was mortally wounded.",
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


def test_describe_armies_report_led_army_line():
    state = _armies_state()
    state.add_leader(LeaderState(1, 1, "Sir Aldric", HexCoord(0, 0)))
    state.add_army(ArmyState(1, 1, ArmyType.BOWMEN, Quality.AVERAGE, HexCoord(0, 0), commanded_by=1))

    lines = describe_armies_report(state, 1)

    assert lines[2:] == ["Capital City -- Sir Aldric: Bowmen (Human, Average, Modified Veteran)"]


def test_describe_armies_report_unled_army_shows_garrison():
    state = _armies_state()
    state.add_army(ArmyState(1, 1, ArmyType.PHALANX, Quality.VETERAN, HexCoord(0, 0)))

    lines = describe_armies_report(state, 1)

    assert lines[2:] == ["Capital City -- Garrison: Phalanx (Human, Veteran, Modified Crack)"]


def test_describe_armies_report_monstrous_army_uses_its_own_fixed_race():
    state = _armies_state()
    state.add_army(ArmyState(1, 1, ArmyType.DRAGON_WING, Quality.ELITE, HexCoord(0, 0)))

    lines = describe_armies_report(state, 1)

    assert lines[2:] == ["Capital City -- Garrison: Dragons (Dragon, Elite, Modified Elite)"]


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

    assert lines[2:] == ["(3, 4) -- Garrison: Bowmen (Human, Average, Modified Average)"]


def test_describe_armies_report_sorts_multiple_armies_by_location_then_id():
    state = _armies_state()
    state.add_province(ProvinceState(HexCoord(1, 1), None, Race.HUMAN, owner_kingdom_id=1, name="Second Province"))
    state.add_army(ArmyState(2, 1, ArmyType.AXEMEN, Quality.AVERAGE, HexCoord(1, 1)))
    state.add_army(ArmyState(1, 1, ArmyType.BOWMEN, Quality.AVERAGE, HexCoord(0, 0)))

    lines = describe_armies_report(state, 1)

    assert lines[2:] == [
        "Capital City -- Garrison: Bowmen (Human, Average, Modified Veteran)",
        "Second Province -- Garrison: Axemen (Human, Average, Modified Average)",
    ]


def test_describe_armies_report_skeletal_army_uses_skel_designation():
    # Phase 281, REPORTS.PAS:988-992 (Doit, inside Rep_Armies): a
    # Zomboid-state army renders "Skel <atdesig>", not the ordinary
    # <atname> -- Lt Cavalry is the clearest real case, since its own
    # atdesig ("Lt Cav") diverges from its atname ("Light Cavalry").
    state = _armies_state()
    state.add_army(ArmyState(1, 1, ArmyType.LT_CAVALRY, Quality.AVERAGE, HexCoord(0, 0), is_skeletal=True))

    lines = describe_armies_report(state, 1)

    assert lines[2:] == ["Capital City -- Garrison: Skel Lt Cav (Human, Average, Modified Veteran)"]


def test_describe_armies_report_non_skeletal_army_still_uses_atname():
    # Same real branch's else-case: a non-Zomboid army keeps using
    # ARMY_TYPE_NAME ("Light Cavalry"), not ARMY_TYPE_DESIGNATION.
    state = _armies_state()
    state.add_army(ArmyState(1, 1, ArmyType.LT_CAVALRY, Quality.AVERAGE, HexCoord(0, 0)))

    lines = describe_armies_report(state, 1)

    assert lines[2:] == ["Capital City -- Garrison: Light Cavalry (Human, Average, Modified Veteran)"]


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
        "Borin spoke to Elena and convinced Elena to pledge Elena's allegiance to Borin.",
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
    state, results = _rumor_letter_setup()

    lines = describe_letter_reports(results, state, 1, ScriptedRandom([]))

    assert lines == ["LETTER REPORTS", "There are no letters from anyone at this time."]


def test_describe_letter_reports_renders_rumor_when_board_width_given():
    state, results = _rumor_letter_setup()

    lines = describe_letter_reports(results, state, 1, ScriptedRandom([0.1] * 10, choice_indices=[0]), board_width=10)

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
        "Borin spoke to Elena and convinced Elena to pledge Elena's allegiance to Borin.",
        "Thy humble servant,   Borin",
        "From: Cyra",
        "To: Aldric",
        "Honored Sovereign,",
        "Cyra spoke to Finn and convinced Finn to pledge Finn's allegiance to Cyra.",
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
    state.add_kingdom(KingdomState(2, "Otherland", Race.ELVEN, Alignment.NEUTRAL, HexCoord(1, 1)))
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
    state.add_kingdom(KingdomState(2, "Otherland", Race.ELVEN, Alignment.NEUTRAL, HexCoord(1, 1)))
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


def test_describe_diplomacy_report_war_always_renders_none_at_present():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_kingdom(KingdomState(2, "Otherland", Race.ELVEN, Alignment.NEUTRAL, HexCoord(1, 1)))
    state.add_leader(LeaderState(9, 2, "Kwoth", HexCoord(1, 1), is_king=True))

    lines = describe_diplomacy_report(state, 1)

    war_index = lines.index(_DIPLOMACY_WAR_INTRO)
    assert lines[war_index + 1] == "None at present"


def test_describe_diplomacy_report_no_king_recorded_falls_back_to_kingdom_name():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_kingdom(KingdomState(2, "Otherland", Race.ELVEN, Alignment.NEUTRAL, HexCoord(1, 1)))

    lines = describe_diplomacy_report(state, 1)

    assert lines[-1] == "Otherland (#2)"


def test_describe_diplomacy_report_lists_multiple_kingdoms_sorted_by_id():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_kingdom(KingdomState(2, "Bland", Race.ELVEN, Alignment.NEUTRAL, HexCoord(1, 1)))
    state.add_kingdom(KingdomState(3, "Cland", Race.DWARVEN, Alignment.NEUTRAL, HexCoord(2, 2)))
    state.add_leader(LeaderState(20, 2, "Bertha", HexCoord(1, 1), is_king=True))
    state.add_leader(LeaderState(30, 3, "Cyrus", HexCoord(2, 2), is_king=True))

    lines = describe_diplomacy_report(state, 1)

    neutral_index = lines.index(_DIPLOMACY_NEUTRAL_INTRO)
    assert lines[neutral_index + 1 :] == ["Bertha (#2)", "Cyrus (#3)"]


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
        "Gold in treasury: 250",
        "Expected Revenues: 0",
        "Expected Expenses: 0",
        _FINANCES_DISCOVERIES_INTRO,
        "None at present",
    ]


def test_describe_finances_report_zero_treasury():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))

    lines = describe_finances_report(state, 1)

    assert lines[2] == "Gold in treasury: 0"


def test_describe_finances_report_discoveries_none_at_present_when_kingdom_owns_none():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0), treasury=999))

    lines = describe_finances_report(state, 1)

    assert lines[-2:] == [_FINANCES_DISCOVERIES_INTRO, "None at present"]
    assert "+Invention Bonus" not in "\n".join(lines)


# -- Phase 268: real Discoveries of the Sages list + Invention Bonus --


def test_describe_finances_report_lists_owned_discoveries():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.kingdoms[1].discoveries = {Discovery.COMPASS}

    lines = describe_finances_report(state, 1)

    assert lines[-2] == _FINANCES_DISCOVERIES_INTRO
    assert lines[-1] == describe_discovery_line(Discovery.COMPASS)
    assert lines[-1] == "  Compass" + " " * 18 + "(+1 skill in Exploring)"


def test_describe_finances_report_discoveries_sorted_by_real_display_value():
    # PONY_EXPRESS (discval 20) must print before COMPASS (discval 2).
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.kingdoms[1].discoveries = {Discovery.COMPASS, Discovery.PONY_EXPRESS}

    lines = describe_finances_report(state, 1)

    assert lines[-2:] == [
        describe_discovery_line(Discovery.PONY_EXPRESS),
        describe_discovery_line(Discovery.COMPASS),
    ]


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

    assert lines[2] == "Gold in treasury: 10"


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

    assert lines[3] == "Expected Revenues: 10"


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

    assert lines[2] == "Gold in treasury: 50"
    assert lines[3] == "(Including +5 Black Knights)"


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

    assert lines[2] == "Gold in treasury: 50"
    assert lines[3] == "(Including +5 Black Knights)"
    assert lines[4] == "(Including +10 Thieves Guild)"
    assert lines[5] == "Expected Revenues: 30"


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


# -- Phase 221: describe_characters_report() -- the "CHARACTERS" section --


_CHARACTERS_OPENING = (
    "My Lord, Great indeed are the leaders of our proud kingdom.  Though thee "
    "knows them well, I list them here for thy consideration (the first line "
    "shows pay and abilities; line 2 shows move precedence and aptitude.)"
)

_NO_SKILLS_LINE = "Ta0 Ma0 Na0 Ar0 Me0 Wh0 Ne0 El0 Ps0 Il0 Dr0 Th0 Ex0 Sp0 Sa0"


def test_describe_characters_report_renders_own_leader_with_no_recorded_data():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_province(ProvinceState(HexCoord(0, 0), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, name="Capital City"))
    state.add_leader(LeaderState(1, 1, "Aldric", HexCoord(0, 0), is_king=True))

    lines = describe_characters_report(state, 1)

    assert lines == [
        "CHARACTERS",
        _CHARACTERS_OPENING,
        "Aldric -- Capital City, Unknown, Unknown, Human, Pay 0",
        _NO_SKILLS_LINE,
    ]


def test_describe_characters_report_none_at_present_when_no_leaders_owned():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))

    lines = describe_characters_report(state, 1)

    assert lines == ["CHARACTERS", _CHARACTERS_OPENING, "None at present"]


def test_describe_characters_report_ignores_other_kingdoms_leaders():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_kingdom(KingdomState(2, "Otherland", Race.ELVEN, Alignment.NEUTRAL, HexCoord(1, 1)))
    state.add_leader(LeaderState(9, 2, "Kwoth", HexCoord(1, 1)))

    lines = describe_characters_report(state, 1)

    assert lines == ["CHARACTERS", _CHARACTERS_OPENING, "None at present"]


def test_describe_characters_report_falls_back_to_coordinate_when_unnamed_province():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_leader(LeaderState(1, 1, "Aldric", HexCoord(2, 3)))

    lines = describe_characters_report(state, 1)

    assert lines[2] == "Aldric -- (2, 3), Unknown, Unknown, Human, Pay 1"


def test_describe_characters_report_uses_recorded_alignment_temper_and_race():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    leader = LeaderState(1, 1, "Aldric", HexCoord(0, 0))
    leader.alignment = Alignment.GOOD
    leader.temper = Temper.BRAVE
    leader.race = Race.ELVEN
    state.add_leader(leader)

    lines = describe_characters_report(state, 1)

    assert lines[2] == "Aldric -- (0, 0), Good, Brave, Elf, Pay 1"


def test_describe_characters_report_renders_recorded_skill_levels():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    leader = LeaderState(1, 1, "Aldric", HexCoord(0, 0))
    leader.skills = SkillTable(raw_values=list(range(31)))
    state.add_leader(leader)

    lines = describe_characters_report(state, 1)

    assert lines[3] == "Ta0 Ma2 Na4 Ar6 Me8 Wh10 Ne12 El14 Ps16 Il18 Dr20 Th22 Ex24 Sp26 Sa28"


def test_describe_characters_report_sorts_by_leader_id():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_leader(LeaderState(40, 1, "Elena", HexCoord(0, 0)))
    state.add_leader(LeaderState(1, 1, "Aldric", HexCoord(0, 0)))

    lines = describe_characters_report(state, 1)

    assert lines[2].startswith("Aldric")
    assert lines[4].startswith("Elena")


def test_describe_characters_report_pay_matches_real_sample_values():
    # Phase 280, SE3__T1.K2 (real sample): King Bradipo I (Good/Cautious)
    # -- 0; Adele (Good/Brave, alignment distance 0) -- 1; Indra (Good/
    # Cautious, distance 0, same temper) -- 1.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_leader(
        LeaderState(1, 1, "Bradipo I", HexCoord(0, 0), is_king=True, alignment=Alignment.GOOD, temper=Temper.CAUTIOUS)
    )
    state.add_leader(LeaderState(2, 1, "Adele", HexCoord(0, 0), alignment=Alignment.GOOD, temper=Temper.BRAVE))
    state.add_leader(LeaderState(3, 1, "Indra", HexCoord(0, 0), alignment=Alignment.GOOD, temper=Temper.CAUTIOUS))

    lines = describe_characters_report(state, 1)

    assert lines[2].endswith(", Pay 0")
    assert lines[4].endswith(", Pay 1")
    assert lines[6].endswith(", Pay 1")


def test_describe_characters_report_hero_pay_reflects_alignment_distance():
    # ALIGNMENT_ORDINAL: Divine=0, Good=1 -- distance 1, same temper ->
    # required_pay() is 2 (base_pay[1]=2, no penalty since temper matches).
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_leader(
        LeaderState(1, 1, "King", HexCoord(0, 0), is_king=True, alignment=Alignment.DIVINE, temper=Temper.CAUTIOUS)
    )
    state.add_leader(LeaderState(2, 1, "Hero", HexCoord(0, 0), alignment=Alignment.GOOD, temper=Temper.CAUTIOUS))

    lines = describe_characters_report(state, 1)

    assert lines[4].endswith(", Pay 2")


def test_describe_characters_report_lists_held_items():
    # Phase 287: the per-leader treasure list (List_Treas(ldr,false)).
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_leader(LeaderState(1, 1, "Aldric", HexCoord(0, 0)))
    state.add_item(Treasure.LEADERSHIP_HUMAN, owner_leader_id=1)
    state.add_item(Treasure.WAND_FIREBALL, owner_leader_id=1)

    lines = describe_characters_report(state, 1)

    assert lines[4] == f"Items: {TREASURE_NAME[Treasure.LEADERSHIP_HUMAN]}, {TREASURE_NAME[Treasure.WAND_FIREBALL]}"


def test_describe_characters_report_omits_items_line_when_leader_holds_nothing():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testland", Race.HUMAN, Alignment.NEUTRAL, HexCoord(0, 0)))
    state.add_leader(LeaderState(1, 1, "Aldric", HexCoord(0, 0)))

    lines = describe_characters_report(state, 1)

    assert len(lines) == 4  # header, opening, name line, skills line -- no Items line
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

    # Aldric's own two lines (name + skills) are immediately followed by
    # Elena's name line, not an Items line -- his own entry has none.
    aldric_index = next(i for i, line in enumerate(lines) if line.startswith("Aldric"))
    assert not lines[aldric_index + 2].startswith("Items:")
    assert f"Items: {TREASURE_NAME[Treasure.LEADERSHIP_HUMAN]}" in lines


# -- Phase 216: describe_adventure_report() -- the "ADVENTURE" section --


_ADVENTURE_OPENING = (
    "O Luminous One, adventure awaits thee and thy companions at every corner of "
    "the globe!  Fearsome monsters lurk in their cavernous hidden lairs by day and "
    "terrorize the populace by night.  Here are these lairs:"
)
_ADVENTURE_COLUMN_HEADER = "Province             %Exp  Features and F#     Monster         Special"


def test_describe_adventure_report_opening_lines():
    state = GameState()

    lines = describe_adventure_report(state, 1)

    assert lines[0] == "ADVENTURE"
    assert lines[1] == _ADVENTURE_OPENING
    assert lines[2] == _ADVENTURE_COLUMN_HEADER


def test_describe_adventure_report_no_discovered_features_renders_none_at_present():
    state = GameState()
    state.add_feature(Feature(1, HexCoord(0, 0), FeatureType.CAVE, guardian_monster=Monster.SWORDSMAN))

    lines = describe_adventure_report(state, 1)

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

    lines = describe_adventure_report(state, 1)

    assert lines[3:] == [
        "Mongu (100% explored)",
        "  Cave (F#2) -- Swordsman",
    ]


def test_describe_adventure_report_looted_feature_shows_sacked_and_looted():
    state = GameState()
    state.add_feature(
        Feature(3, HexCoord(1, 1), FeatureType.CRYPT, guardian_monster=Monster.GARGOYLE, looted=True, discovered_by_kingdom={1: 3})
    )

    lines = describe_adventure_report(state, 1)

    assert lines[3:] == [
        "(1, 1) (0% explored)",
        "  Crypt (F#3) -- sacked & looted",
    ]


def test_describe_adventure_report_discovery_level_1_renders_question_mark():
    state = GameState()
    state.add_feature(
        Feature(4, HexCoord(2, 2), FeatureType.TOMB, guardian_monster=Monster.MUMMY, discovered_by_kingdom={1: 1})
    )

    lines = describe_adventure_report(state, 1)

    assert lines[3:] == [
        "(2, 2) (0% explored)",
        "  Tomb (F#4) -- Mummy ?",
    ]


def test_describe_adventure_report_undiscovered_feature_is_excluded():
    state = GameState()
    state.add_feature(Feature(5, HexCoord(4, 4), FeatureType.DUNGEON, guardian_monster=Monster.TROLL))

    lines = describe_adventure_report(state, 1)

    assert lines[3:] == ["None at present"]


def test_describe_adventure_report_only_shows_this_kingdoms_own_discovery():
    state = GameState()
    state.add_feature(
        Feature(6, HexCoord(0, 0), FeatureType.CAVE, guardian_monster=Monster.GIANT, discovered_by_kingdom={2: 3})
    )

    lines = describe_adventure_report(state, 1)

    assert lines[3:] == ["None at present"]


def test_describe_adventure_report_monster_name_prefix_is_stripped():
    state = GameState()
    state.add_feature(
        Feature(7, HexCoord(0, 0), FeatureType.PET_FOREST, guardian_monster=Monster.GI_EAGLE, discovered_by_kingdom={1: 3})
    )

    lines = describe_adventure_report(state, 1)

    assert lines[3:] == [
        "(0, 0) (0% explored)",
        "  Petrified Forest (F#7) -- Eagle",
    ]


def test_describe_adventure_report_no_guardian_recorded_omits_monster_segment():
    state = GameState()
    state.add_feature(Feature(8, HexCoord(0, 0), FeatureType.CAVE, discovered_by_kingdom={1: 3}))

    lines = describe_adventure_report(state, 1)

    assert lines[3:] == [
        "(0, 0) (0% explored)",
        "  Cave (F#8)",
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

    lines = describe_adventure_report(state, 1)

    assert lines[3:] == [
        "(0, 0) (0% explored)",
        "  Tomb (F#1) -- Mummy",
        "  Crypt (F#3) -- Ghost",
        "(1, 1) (0% explored)",
        "  Cave (F#2) -- Giant",
    ]


# -- Phase 215: compose_letter_report() -- top-level per-kingdom letter assembler --


def test_compose_letter_report_stitches_all_four_wired_sections_in_the_real_order():
    state = _armies_state()
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
        "Aldric spoke to Borin and convinced Borin to pledge Borin's allegiance to Aldric.",
        "LETTER REPORTS",
        "O King of Kings, thy heroes have travelled around the globe in "
        "search of adventure and conquest.  I have faithfully kept their "
        "correspondence, and now I present it to thee:",
        "From: Borin",
        "To: Aldric",
        "Honored Sovereign,",
        "Borin spoke to Elena and convinced Elena to pledge Elena's allegiance to Borin.",
        "Thy humble servant,   Borin",
        "DIPLOMACY",
        "My lord, the following Kings have wisely allied with thy ever-victorious majesty:",
        "None at present",
        "My lord, the following Kings are foolishly at war with thy ever-victorious majesty:",
        "None at present",
        "My lord, the following Kings are cautiously neutral with thy ever-victorious majesty:",
        "None at present",
        "FINANCES",
        "O Great One, I submit for thy examination the following figures "
        "concerning the finances of our great nation:",
        "Gold in treasury: 0",
        "Expected Revenues: 0",
        "Expected Expenses: 4",
        "Our Kingdom is also benefited by the following Discoveries of the Sages:",
        "None at present",
        "PROVINCES",
        "O superfluous one, I have kept well a list of all provinces which have had "
        "the wisdom to submit to thy yoke.  Here, then, are the lands of thy Empire:",
        "                                                    Recruiting Types:",
        "Province            Tax   Race   Terrain  Expl%     Type 1     Type 2",
        "Capital City              Human    Plain     0%                      ",
        "CHARACTERS",
        "My Lord, Great indeed are the leaders of our proud kingdom.  Though thee "
        "knows them well, I list them here for thy consideration (the first line "
        "shows pay and abilities; line 2 shows move precedence and aptitude.)",
        "Aldric -- Capital City, Unknown, Unknown, Human, Pay 0",
        "Ta0 Ma0 Na0 Ar0 Me0 Wh0 Ne0 El0 Ps0 Il0 Dr0 Th0 Ex0 Sp0 Sa0",
        "Borin -- Capital City, Unknown, Unknown, Human, Pay 1",
        "Ta0 Ma0 Na0 Ar0 Me0 Wh0 Ne0 El0 Ps0 Il0 Dr0 Th0 Ex0 Sp0 Sa0",
        "Elena -- Capital City, Unknown, Unknown, Human, Pay 1",
        "Ta0 Ma0 Na0 Ar0 Me0 Wh0 Ne0 El0 Ps0 Il0 Dr0 Th0 Ex0 Sp0 Sa0",
        "ARMIES",
        "Excellence, thy armies have trained hard and honed their weapons to a fine "
        "edge.  Proudly they serve thy imperial majesty, and they await thy commands.",
        "Capital City -- Garrison: Bowmen (Human, Average, Modified Veteran)",
        "IMPERIAL OFFICE REPORT",
        "World Emperor: None at present",
        "Esteemed High Chancellor: None at present",
        "Imperial Treasurer: None at present",
        "Imperial Grand Marshal: None at present",
        "Imperial Grand Admiral: None at present",
        "Lord High Defender: None at present",
        "High Priest Palatine: None at present",
        "Arch-Mage Palatine: None at present",
        "King of Pain: None at present",
        "Prince of Thieves: None at present",
        "Savior of Humankind: None at present",
        "First Elder of Elvenkind: None at present",
        "King Under the Mountain: None at present",
        "Khan of the Orcish Hordes: None at present",
        "Dragon Lord: None at present",
        "Ace of Eagles: None at present",
        "Whale League Commissioner: None at present",
        "King of Atlantis: None at present",
        "Tsar of the Trees: None at present",
        "High Mucky-Muck of Trolls: None at present",
        "Lord of Lycanthropes: None at present",
        "Divine Archangel: None at present",
        "Most Blessed of Kings: None at present",
        "Great Druid of Life: None at present",
        "Defender of Freedom: None at present",
        "Warlock of the Pagan Gods: None at present",
        "Angel of Death: None at present",
        "Chief of Staff: None at present",
        "Silver Tongue: None at present",
        "Master of Elements: None at present",
        "Amazing Houdini: None at present",
        "Sorceror of Black Magic: None at present",
        "Master Mind: None at present",
        "Ranger of the Plains: None at present",
        "Desert Rat: None at present",
        "Lord of the Jungle: None at present",
        "Warden of the Forests: None at present",
        "Mountain Man: None at present",
        "Ruler of the Waves: None at present",
        "Fool of Battles: None at present",
        "Curator of Artifacts: None at present",
        "Professor Whizdumb: None at present",
        "Grandfather of Assassins: None at present",
        "Captain of the Musketeers: None at present",
        "Air Force Commander: None at present",
        "King of Cowards: None at present",
        "Bravest of the Brave: None at present",
        "ADVENTURE",
        "O Luminous One, adventure awaits thee and thy companions at every corner of "
        "the globe!  Fearsome monsters lurk in their cavernous hidden lairs by day and "
        "terrorize the populace by night.  Here are these lairs:",
        "Province             %Exp  Features and F#     Monster         Special",
        "None at present",
        "GENERAL INTELLIGENCE REPORT",
        "None at present",
    ]


def test_compose_letter_report_omits_action_report_when_this_kingdom_has_no_king():
    state = _armies_state()

    lines = compose_letter_report([], state, 1, ScriptedRandom([]))

    assert "ACTION REPORT" not in lines
    assert lines[0] == "LETTER REPORTS"


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


def test_compose_letter_report_all_four_wired_sections_present_even_when_empty():
    state = _armies_state()

    lines = compose_letter_report([], state, 1, ScriptedRandom([]))

    assert lines == [
        "LETTER REPORTS",
        "There are no letters from anyone at this time.",
        "DIPLOMACY",
        "My lord, the following Kings have wisely allied with thy ever-victorious majesty:",
        "None at present",
        "My lord, the following Kings are foolishly at war with thy ever-victorious majesty:",
        "None at present",
        "My lord, the following Kings are cautiously neutral with thy ever-victorious majesty:",
        "None at present",
        "FINANCES",
        "O Great One, I submit for thy examination the following figures "
        "concerning the finances of our great nation:",
        "Gold in treasury: 0",
        "Expected Revenues: 0",
        "Expected Expenses: 0",
        "Our Kingdom is also benefited by the following Discoveries of the Sages:",
        "None at present",
        "PROVINCES",
        "O superfluous one, I have kept well a list of all provinces which have had "
        "the wisdom to submit to thy yoke.  Here, then, are the lands of thy Empire:",
        "                                                    Recruiting Types:",
        "Province            Tax   Race   Terrain  Expl%     Type 1     Type 2",
        "Capital City              Human    Plain     0%                      ",
        "CHARACTERS",
        "My Lord, Great indeed are the leaders of our proud kingdom.  Though thee "
        "knows them well, I list them here for thy consideration (the first line "
        "shows pay and abilities; line 2 shows move precedence and aptitude.)",
        "None at present",
        "ARMIES",
        "Excellence, thy armies have trained hard and honed their weapons to a fine "
        "edge.  Proudly they serve thy imperial majesty, and they await thy commands.",
        "None at present",
        "IMPERIAL OFFICE REPORT",
        "World Emperor: None at present",
        "Esteemed High Chancellor: None at present",
        "Imperial Treasurer: None at present",
        "Imperial Grand Marshal: None at present",
        "Imperial Grand Admiral: None at present",
        "Lord High Defender: None at present",
        "High Priest Palatine: None at present",
        "Arch-Mage Palatine: None at present",
        "King of Pain: None at present",
        "Prince of Thieves: None at present",
        "Savior of Humankind: None at present",
        "First Elder of Elvenkind: None at present",
        "King Under the Mountain: None at present",
        "Khan of the Orcish Hordes: None at present",
        "Dragon Lord: None at present",
        "Ace of Eagles: None at present",
        "Whale League Commissioner: None at present",
        "King of Atlantis: None at present",
        "Tsar of the Trees: None at present",
        "High Mucky-Muck of Trolls: None at present",
        "Lord of Lycanthropes: None at present",
        "Divine Archangel: None at present",
        "Most Blessed of Kings: None at present",
        "Great Druid of Life: None at present",
        "Defender of Freedom: None at present",
        "Warlock of the Pagan Gods: None at present",
        "Angel of Death: None at present",
        "Chief of Staff: None at present",
        "Silver Tongue: None at present",
        "Master of Elements: None at present",
        "Amazing Houdini: None at present",
        "Sorceror of Black Magic: None at present",
        "Master Mind: None at present",
        "Ranger of the Plains: None at present",
        "Desert Rat: None at present",
        "Lord of the Jungle: None at present",
        "Warden of the Forests: None at present",
        "Mountain Man: None at present",
        "Ruler of the Waves: None at present",
        "Fool of Battles: None at present",
        "Curator of Artifacts: None at present",
        "Professor Whizdumb: None at present",
        "Grandfather of Assassins: None at present",
        "Captain of the Musketeers: None at present",
        "Air Force Commander: None at present",
        "King of Cowards: None at present",
        "Bravest of the Brave: None at present",
        "ADVENTURE",
        "O Luminous One, adventure awaits thee and thy companions at every corner of "
        "the globe!  Fearsome monsters lurk in their cavernous hidden lairs by day and "
        "terrorize the populace by night.  Here are these lairs:",
        "Province             %Exp  Features and F#     Monster         Special",
        "None at present",
        "GENERAL INTELLIGENCE REPORT",
        "None at present",
    ]


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

    lines = compose_letter_report(results, state, 1, ScriptedRandom([0.1] * 20, choice_indices=[0, 0]), board_width=10)

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
    assert "Anti-Holy" not in "".join(lines)
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


# -- Phase 230: describe_imperial_office_report() -- IMPERIAL OFFICE REPORT --


def test_describe_imperial_office_report_none_at_present_for_every_office_with_no_leaders():
    state = _armies_state()

    lines = describe_imperial_office_report(state)

    assert lines[0] == "IMPERIAL OFFICE REPORT"
    assert lines.count("World Emperor: None at present") == 1
    assert lines.count("Arch-Mage Palatine: None at present") == 1
    assert lines.count("King of Pain: None at present") == 1
    assert lines.count("Prince of Thieves: None at present") == 1
    assert lines.count("Savior of Humankind: None at present") == 1
    assert lines.count("Dragon Lord: None at present") == 1
    assert len(lines) == 48  # header + 47 offices


def test_describe_imperial_office_report_shows_a_real_office_holder():
    state = _armies_state()
    state.add_leader(LeaderState(1, 1, "Aldric", HexCoord(0, 0), is_king=True))
    state.leaders[1].merit_tally.resurrection_bless_casts = 3

    lines = describe_imperial_office_report(state)

    assert "High Priest Palatine: Aldric (3 points)" in lines


def test_describe_imperial_office_report_same_content_regardless_of_kingdom_id():
    # Unlike every other section, this one takes no kingdom_id -- it's
    # the same world-wide office standings for every King's own report.
    state = _armies_state()
    state.add_kingdom(KingdomState(2, "Otherland", Race.ELVEN, Alignment.NEUTRAL, HexCoord(1, 1)))
    state.add_leader(LeaderState(1, 1, "Aldric", HexCoord(0, 0), is_king=True))

    assert describe_imperial_office_report(state) == describe_imperial_office_report(state)


def test_compose_letter_report_includes_imperial_office_report_between_armies_and_adventure():
    state = _armies_state()

    lines = compose_letter_report([], state, 1, ScriptedRandom([]))

    armies_index = lines.index("ARMIES")
    office_index = lines.index("IMPERIAL OFFICE REPORT")
    adventure_index = lines.index("ADVENTURE")
    assert armies_index < office_index < adventure_index


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


def test_record_spell_world_events_still_skips_tornado():
    state, battle_coord, _watcher_coord = _gir_state()
    board_width = NORMAL_MAP_BOUNDS[0]
    request = CastRequest(spell=Spell.TORNADO, target=encode_hex_number(battle_coord, board_width))
    result = CastExecutionResult(request, applied=True)
    results = [
        PhaseDispatchResult(leader_id=1, segment_index=0, phase_label="P0", action=ActionCode.CAST, result=result, error=None)
    ]

    record_spell_world_events(state, results, ScriptedRandom([]), board_width=board_width)

    assert state.world_events == []


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


def test_render_fly_move_world_event_renders_the_lfly_template():
    rng = ScriptedRandom([0.1, 0.1])

    line = render_fly_move_world_event("Tlazolteotl", "Waterford", rng)

    assert line == "Tlazolteotl flew into Waterford."


def _fake_move_result(moved: bool, new_location: HexCoord | None):
    class _FakeMoveResult:
        pass

    result = _FakeMoveResult()
    result.moved = moved
    result.new_location = new_location
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
