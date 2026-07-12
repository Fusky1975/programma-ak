from __future__ import annotations

import pytest

from ak_engine.models.army_type import ArmyType
from ak_engine.models.magic_feature import MagicFeature
from ak_engine.report.turn_report import (
    SNEAKUP_RANGE_BOW,
    SNEAKUP_RANGE_MELEE,
    SNEAKUP_RANGE_SPELL,
    describe_battle,
    margin_bucket,
    parse_template_choices,
    pick_variant,
    render_battle_winner,
    render_column_clash,
    render_destroyed_army,
    render_flee_failure,
    render_magic_feature_discovery,
    render_march,
    render_pursuit_and_destroy,
    render_retreat,
    render_sneak_detected,
    render_spy_report_opening,
    render_uncontested_conquest,
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
