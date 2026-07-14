from __future__ import annotations

import pytest

from ak_engine.models.army_type import ArmyType
from ak_engine.models.magic_feature import MagicFeature
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
    SEARCH_FEATURE_ALREADY_SACKED_TEMPLATE,
    SNEAKUP_RANGE_BOW,
    SNEAKUP_RANGE_MELEE,
    SNEAKUP_RANGE_SPELL,
    SPY_GARRISON_APPROXIMATELY_TEMPLATE,
    SPY_LEADS_APPROXIMATELY_TEMPLATE,
    WILL_TEMPLATE,
    describe_battle,
    describe_cast,
    describe_fire,
    describe_give,
    describe_hire,
    describe_practice,
    describe_pursue,
    describe_search,
    describe_trail,
    describe_use_mi,
    margin_bucket,
    parse_template_choices,
    pick_variant,
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
    render_boulder_throw_hit,
    render_boulder_throw_missed,
    render_breath_weapon_hit,
    render_breath_weapon_missed,
    render_caught_up,
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
    render_skill_book_read,
    render_pursuit_and_destroy,
    render_quest_errand_thanks,
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
    render_spy_army_type,
    render_spy_capital_province,
    render_spy_character_here,
    render_spy_elements_intro,
    render_spy_garrison,
    render_spy_leads,
    render_spy_no_characters,
    render_spy_no_characters_or_forces,
    render_spy_report_closing,
    render_spy_report_opening,
    render_spy_tax_estimate,
    render_steal_caught_and_ransomed,
    render_tactical_comparison,
    render_take_gold,
    render_take_items,
    render_trade_deal_failed,
    render_troll_regeneration,
    render_uncontested_conquest,
    render_vampiric_bite,
    render_wandering_encounter,
    render_weapon_rally,
    render_will,
    missile_attack_flavor,
    tactical_margin_bucket,
)
from ak_engine.models.enums import Ability, Spell
from ak_engine.models.weapon import Weapon
from ak_engine.turn.battle_line import BattleUnit
from ak_engine.turn.battle_orchestrator import BattleReport
from ak_engine.turn.battle_resolution import BattleColumnResult, BattleResult
from ak_engine.turn.cast_decode import CastRequest
from ak_engine.turn.cast_execution import CastExecutionResult
from ak_engine.turn.hire_fire_decode import FireRequest, HireRequest
from ak_engine.turn.plan_dispatch import FireExecutionResult, HireExecutionResult
from ak_engine.turn.practice_execution import PracticeExecutionResult
from ak_engine.turn.pursue_execution import PursueExecutionResult
from ak_engine.turn.search_execution import SearchExecutionResult
from ak_engine.turn.trade_execution import TradeExecutionResult
from ak_engine.turn.trail_execution import TrailExecutionResult
from ak_engine.turn.use_mi_execution import UseMIExecutionResult

from _helpers import ScriptedRandom


def _column(attacker_win_probability: float, attacker_source_id: int = 1, defender_source_id: int = 2) -> BattleColumnResult:
    return BattleColumnResult(
        attacker_strength=10.0,
        defender_strength=10.0,
        attacker_win_probability=attacker_win_probability,
        attacker_won=attacker_win_probability >= 0.5,
        attacker_column_luck=None,
        defender_column_luck=None,
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


# -- margin_bucket ---------------------------------------------------------


def test_margin_bucket_is_zero_at_an_even_fight():
    assert margin_bucket(0.5) == 0


def test_margin_bucket_is_positive_when_attacker_favored():
    assert margin_bucket(0.8) == 3


def test_margin_bucket_is_negative_when_attacker_disfavored():
    assert margin_bucket(0.2) == -3


def test_margin_bucket_clamps_at_plus_five():
    assert margin_bucket(1.0) == 5


def test_margin_bucket_clamps_at_minus_five():
    assert margin_bucket(0.0) == -5


# -- render_column_clash ----------------------------------------------------


def test_render_column_clash_names_both_armies_and_picks_a_margin_sentence():
    # attacker_win_probability=0.5 -> bucket 0 ("zero" templates). All /R and
    # {} draws scripted to their "right/include" branch (0.9).
    column = _column(attacker_win_probability=0.5)
    rng = ScriptedRandom([0.9, 0.9, 0.9, 0.9], choice_indices=[0])
    result = render_column_clash(column, "the 260th Garrison", "the 45th Orcs", rng)
    assert result == "the 260th Garrison battled with the 45th Orcs and battled them to a standstill."


def test_render_column_clash_appends_a_plus_bucket_sentence():
    # attacker_win_probability=0.8 -> bucket 3. All draws scripted "left/exclude" (0.1).
    column = _column(attacker_win_probability=0.8)
    rng = ScriptedRandom([0.1, 0.1, 0.1, 0.1], choice_indices=[0])
    result = render_column_clash(column, "Attackia's host", "Defendia's line", rng)
    assert result == "Attackia's host fought Defendia's line and advanced at will."


def test_render_column_clash_resolves_sea_marker():
    # Phase 74: attacker_win_probability=0.4 -> bucket -1, variant 0
    # (" gradually gave_ground/Swas_pushed_back.") carries only a "/S"
    # marker, no "/R" -- the opening clause's own "/R" (fought/battled)
    # and "{with }" inclusion each still consume one draw (0.1 -> left
    # choice / excluded).
    column = _column(attacker_win_probability=0.4)
    rng = ScriptedRandom([0.1, 0.1], choice_indices=[0])
    result = render_column_clash(column, "A", "B", rng, is_sea=True)
    assert result == "A fought B and gradually was pushed back."


def test_render_column_clash_land_default_resolves_sea_marker_left():
    column = _column(attacker_win_probability=0.4)
    rng = ScriptedRandom([0.1, 0.1], choice_indices=[0])
    result = render_column_clash(column, "A", "B", rng)
    assert result == "A fought B and gradually gave ground."


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
    column = _column(attacker_win_probability=0.8, attacker_source_id=10, defender_source_id=20)
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
        army_names={10: "the 260th Garrison", 20: "the 45th Orcs"},
        destination_names={},
        rng=rng,
    )
    assert lines == [
        "the 260th Garrison fought the 45th Orcs and advanced at will.",
        "the forces of Attackia broke through and were victorious.",
        "Attackia annihilated the 45th Orcs.",
    ]


def test_describe_battle_threads_is_sea_to_every_sub_renderer():
    # Phase 74: is_sea propagates to both the per-column clash sentence
    # (bucket -1 variant 0, "/S" only) and the winner sentence (DEFWIN
    # variant 1, "/S" x2 + "/R").
    column = _column(attacker_win_probability=0.4, attacker_source_id=10, defender_source_id=20)
    battle_result = BattleResult(winner="defender", columns=[column])
    report = BattleReport(battle_result=battle_result, conquered=False)

    rng = ScriptedRandom([0.1, 0.1, 0.1], choice_indices=[0, 1])
    lines = describe_battle(
        report,
        attacker_name="Attackia",
        defender_name="Defendia",
        province_name="the Dolphin Sea",
        army_names={10: "the 260th Garrison", 20: "the 45th Orcs"},
        destination_names={},
        rng=rng,
        is_sea=True,
    )
    assert lines == [
        "the 260th Garrison fought the 45th Orcs and gradually was pushed back.",
        "Attackia's fleets were beaten and chased out of the Dolphin Sea.",
    ]


def test_describe_battle_skips_unnamed_armies_and_ties_without_erroring():
    column = _column(attacker_win_probability=0.5, attacker_source_id=1, defender_source_id=2)
    battle_result = BattleResult(winner="tie", columns=[column])
    report = BattleReport(battle_result=battle_result, conquered=False)

    rng = ScriptedRandom([])
    lines = describe_battle(
        report,
        attacker_name="Attackia",
        defender_name="Defendia",
        province_name="the Dolphin Sea",
        army_names={},  # no display names supplied -- clash sentence skipped
        destination_names={},
        rng=rng,
    )
    assert lines == []


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


def test_describe_hire_renders_nothing_on_any_failure_reason():
    # Every real HireExecutionResult failure reason is an administrative
    # one with no sourced narrative -- see describe_hire()'s own
    # docstring for why render_hire_refused/render_hire_counter_offer
    # are never reachable at all.
    for reason in ("hero not found", "cannot hire a King", "hero already in service", "not co-located", "insufficient treasury"):
        result = HireExecutionResult(HireRequest(hero_id=32, gold_offer=2), hired=False, reason=reason)
        rng = ScriptedRandom([])

        line = describe_hire(result, character_name="Aldric", hireling_name="Borin", king_name="King Harold the Bold", rng=rng)

        assert line is None


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
