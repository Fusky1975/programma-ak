from __future__ import annotations

import pytest

from ak_engine.models.army_type import ArmyType
from ak_engine.models.magic_feature import MagicFeature
from ak_engine.report.turn_report import (
    ALREADY_ALLIED_TEMPLATE,
    ATTACK_DEVASTATING_HIT_TEMPLATE,
    EXPLORE_ALREADY_MAXED_TEMPLATE,
    EXPLORE_NOT_PRESENT_PREFIX,
    HIRE_COUNTER_OFFER_TEMPLATE,
    INHERIT_TEMPLATE,
    NEMESIS_TEMPLATE,
    SNEAKUP_RANGE_BOW,
    SNEAKUP_RANGE_MELEE,
    SNEAKUP_RANGE_SPELL,
    SPY_GARRISON_APPROXIMATELY_TEMPLATE,
    SPY_LEADS_APPROXIMATELY_TEMPLATE,
    WILL_TEMPLATE,
    describe_battle,
    margin_bucket,
    parse_template_choices,
    pick_variant,
    render_already_allied,
    render_ally_proposed,
    render_ally_refused,
    render_attack_devastating_hit,
    render_attack_hit,
    render_attack_missed,
    render_battle_winner,
    render_column_clash,
    render_destroyed_army,
    render_explore_already_maxed,
    render_explore_continued,
    render_explore_progress,
    render_fire_arrow_attack,
    render_fire_hireling,
    render_flee_failure,
    render_generic_encounter,
    render_hire_accepted,
    render_hire_counter_offer,
    render_hire_refused,
    render_inherit,
    render_magic_feature_discovery,
    render_march,
    render_melee_attack,
    render_mortally_wounded,
    render_move_to_bow_range,
    render_move_to_melee_range,
    render_patrol_encounter,
    render_patrol_release,
    render_pursuit_and_destroy,
    render_retreat,
    render_sneak_detected,
    render_spy_army_type,
    render_spy_capital_province,
    render_spy_character_here,
    render_spy_elements_intro,
    render_spy_no_characters,
    render_spy_no_characters_or_forces,
    render_spy_report_closing,
    render_spy_report_opening,
    render_spy_tax_estimate,
    render_tactical_comparison,
    render_take_gold,
    render_uncontested_conquest,
    render_wandering_encounter,
    render_will,
    tactical_margin_bucket,
)
from ak_engine.turn.battle_line import BattleUnit
from ak_engine.turn.battle_orchestrator import BattleReport
from ak_engine.turn.battle_resolution import BattleColumnResult, BattleResult

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
