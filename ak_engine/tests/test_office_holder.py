"""Tests for turn/office_holder.py -- see its module docstring for the
full derivation (Emperor's special-cased resolution vs. the other 9
offices' genuine Merit Point Rank contest).
"""

from __future__ import annotations

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.game_state import ArmyState, GameState, KingdomState, LeaderState, ProvinceState, RaceTitleTally
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.office import Office
from ak_engine.models.race import Race
from ak_engine.models.temper import Temper
from ak_engine.models.treasure import Treasure
from ak_engine.turn.combat import Quality
from ak_engine.turn.office_holder import (
    ALL_OFFICES,
    ARMY_RANKED_OFFICES,
    RANKED_OFFICES,
    apply_cravenest_temperament_escalation,
    kingdom_best_candidate,
    kingdom_runner_up,
    leader_office_rank,
    office_rival_best_points,
    resolve_all_army_office_holders,
    resolve_all_office_holders,
    resolve_army_office_holder,
    resolve_office_holder,
)

HOME = HexCoord(0, 0)


def make_state() -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Attackia", Race.HUMAN, Alignment.GOOD, HOME, treasury=10))
    state.add_kingdom(KingdomState(2, "Defendia", Race.HUMAN, Alignment.NEUTRAL, HexCoord(1, 1), treasury=5))
    return state


def test_resolve_office_holder_emperor_reads_the_real_election_result():
    state = make_state()
    state.add_leader(LeaderState(1, 1, "Aldric", HOME, is_king=True))
    state.emperor_kingdom_id = 1
    state.add_province(ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, tax=8))

    holder = resolve_office_holder(state, Office.EMPEROR)

    assert holder is not None
    assert holder.leader_id == 1
    assert holder.merit_points == 8  # emperor_merit_points == Tax_Base


def test_resolve_office_holder_emperor_none_before_any_election():
    state = make_state()
    state.add_leader(LeaderState(1, 1, "Aldric", HOME, is_king=True))

    assert resolve_office_holder(state, Office.EMPEROR) is None


def test_resolve_office_holder_treasurer_picks_the_wealthier_king():
    state = make_state()
    state.add_leader(LeaderState(1, 1, "Aldric", HOME, is_king=True))
    state.add_leader(LeaderState(2, 2, "Borin", HexCoord(1, 1), is_king=True))

    holder = resolve_office_holder(state, Office.TREASURER)

    assert holder is not None
    assert holder.leader_id == 1  # Attackia's own treasury (10) beats Defendia's (5)
    assert holder.merit_points == 10


def test_resolve_office_holder_treasurer_ineligible_for_independent_hero():
    state = make_state()
    state.add_leader(LeaderState(9, None, "Wanderer", HOME))  # no kingdom, no treasury

    assert resolve_office_holder(state, Office.TREASURER) is None


def test_resolve_office_holder_hero_can_win_an_office():
    # Rulebook [10.1]: "Anche un Eroe può aggiudicarsi una carica."
    state = make_state()
    state.add_leader(LeaderState(1, 1, "Aldric", HOME, is_king=True))
    hero = LeaderState(50, 1, "Wandering Sage", HOME)
    hero.merit_tally.resurrection_bless_casts = 5
    state.add_leader(hero)

    holder = resolve_office_holder(state, Office.PRIEST)

    assert holder is not None
    assert holder.leader_id == 50
    assert holder.merit_points == 5


def test_resolve_office_holder_none_when_nobody_meets_the_minimum():
    state = make_state()
    state.add_leader(LeaderState(1, 1, "Aldric", HOME, is_king=True))  # 0 Merit Points everywhere

    assert resolve_office_holder(state, Office.MARSHAL) is None


def test_resolve_office_holder_tiebreak_uses_treasury_then_tax_base():
    state = make_state()
    a = LeaderState(1, 1, "Aldric", HOME, is_king=True)
    a.merit_tally.monster_hp_defeated = 10
    b = LeaderState(2, 2, "Borin", HexCoord(1, 1), is_king=True)
    b.merit_tally.monster_hp_defeated = 10
    state.add_leader(a)
    state.add_leader(b)

    holder = resolve_office_holder(state, Office.DEFENDER)

    # Tied at 10 points each -- kingdom 1's own treasury (10) beats kingdom 2's (5).
    assert holder is not None
    assert holder.leader_id == 1


def test_resolve_office_holder_tiebreak_falls_through_to_lower_leader_id():
    # Phase 377: a real third tie-break tier past treasury and tax base
    # -- both Kings share the same Kingdom (so treasury and tax base are
    # necessarily identical too), so only leader_id can break this tie.
    state = make_state()
    higher_id = LeaderState(7, 1, "Later Claimant", HOME, is_king=True)
    higher_id.merit_tally.monster_hp_defeated = 10
    lower_id = LeaderState(3, 1, "Earlier Claimant", HOME, is_king=True)
    lower_id.merit_tally.monster_hp_defeated = 10
    state.add_leader(higher_id)
    state.add_leader(lower_id)

    holder = resolve_office_holder(state, Office.DEFENDER)

    assert holder is not None
    assert holder.leader_id == 3


def test_resolve_office_holder_raises_for_a_non_office():
    state = make_state()
    import pytest

    with pytest.raises(ValueError):
        resolve_office_holder(state, "not-an-office")  # type: ignore[arg-type]


def test_resolve_all_office_holders_covers_every_real_office():
    state = make_state()
    state.add_leader(LeaderState(1, 1, "Aldric", HOME, is_king=True))

    holders = resolve_all_office_holders(state)

    assert set(holders.keys()) == set(ALL_OFFICES)
    assert len(ALL_OFFICES) == 47
    assert len(RANKED_OFFICES) == 46


def test_resolve_office_holder_evilking_none_for_good_kingdom():
    # Attackia is Alignment.GOOD (see make_state()) -- King of Pain
    # requires an Evil-aligned Kingdom, so its own King never qualifies.
    state = make_state()
    state.add_leader(LeaderState(1, 1, "Aldric", HOME, is_king=True))

    assert resolve_office_holder(state, Office.EVIL_KING) is None


def test_resolve_office_holder_evilking_resolves_for_an_evil_king():
    # Phase 369: King of Pain's real formula is plain Tax_Base(King).
    state = GameState()
    state.add_kingdom(KingdomState(1, "Mordoth", Race.HUMAN, Alignment.EVIL, HOME, treasury=10))
    king = LeaderState(1, 1, "Vaelgor", HOME, is_king=True)
    state.add_leader(king)
    state.add_province(ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, tax=30))

    holder = resolve_office_holder(state, Office.EVIL_KING)

    assert holder is not None
    assert holder.leader_id == 1


def test_resolve_office_holder_thiefprince_open_to_a_hero():
    # No King-only gate, unlike King of Pain -- a Hero can win it too.
    state = make_state()
    state.add_leader(LeaderState(1, 1, "Aldric", HOME, is_king=True))
    hero = LeaderState(50, 1, "Sneak", HOME)
    hero.merit_tally.successful_thefts = 20
    state.add_leader(hero)

    holder = resolve_office_holder(state, Office.THIEF_PRINCE)

    assert holder is not None
    assert holder.leader_id == 50


def test_resolve_office_holder_race_title_blocked_before_the_turn_gate():
    # Human's own title (Office.HUMAN_KING) doesn't award a winner
    # before turn 4, even with points that clear OFFICE_MIN_POINTS.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Humania", Race.HUMAN, Alignment.NEUTRAL, HOME, treasury=10))
    king = LeaderState(1, 1, "Aldric", HOME, is_king=True, race=Race.HUMAN)
    state.add_leader(king)
    king.race_title_tally[Race.HUMAN] = RaceTitleTally(front_line_battles_won_points=50)
    state.turn_number = 1

    assert resolve_office_holder(state, Office.HUMAN_KING) is None

    state.turn_number = 4
    holder = resolve_office_holder(state, Office.HUMAN_KING)
    assert holder is not None
    assert holder.leader_id == 1


def test_resolve_office_holder_race_title_special_race_needs_an_owned_province():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Wyrmreach", Race.HUMAN, Alignment.NEUTRAL, HOME, treasury=10))
    king = LeaderState(1, 1, "Aldric", HOME, is_king=True, race=Race.HUMAN)
    state.add_leader(king)
    king.race_title_tally[Race.DRAGONS] = RaceTitleTally(front_line_battles_won_points=50)
    state.turn_number = 10  # past Dragon Lord's own turn-6 gate

    assert resolve_office_holder(state, Office.DRAGON_LORD) is None

    state.add_province(ProvinceState(HexCoord(3, 3), Terrain.MTNS, Race.DRAGONS, owner_kingdom_id=1))
    holder = resolve_office_holder(state, Office.DRAGON_LORD)
    assert holder is not None
    assert holder.leader_id == 1


# -- Phase 379: 18 more leader-scoped royal titles ---------------------------


def test_resolve_office_holder_ele_mage_reads_the_tally():
    state = make_state()
    leader = LeaderState(1, 1, "Aldric", HOME, is_king=True)
    leader.merit_tally.elemental_spell_casts = 25
    state.add_leader(leader)

    holder = resolve_office_holder(state, Office.ELE_MAGE)

    assert holder is not None
    assert holder.leader_id == 1
    assert holder.merit_points == 25


def test_resolve_office_holder_plains_king_open_to_a_hero():
    state = make_state()
    state.add_leader(LeaderState(1, 1, "Aldric", HOME, is_king=True))
    hero = LeaderState(50, 1, "Ranger", HOME)
    hero.merit_tally.plains_explorations = 10
    state.add_leader(hero)

    holder = resolve_office_holder(state, Office.PLAINS_KING)

    assert holder is not None
    assert holder.leader_id == 50


def test_resolve_office_holder_battle_fool_ranks_the_worst_combined_record():
    state = make_state()
    fool = LeaderState(1, 1, "Bumbler", HOME, is_king=True)
    fool.merit_tally.land_battles_won_points = 0
    fool.merit_tally.land_battles_lost_points = 5  # -5 combined
    hero = LeaderState(2, 2, "Champion", HexCoord(1, 1), is_king=True)
    hero.merit_tally.land_battles_won_points = 0
    hero.merit_tally.land_battles_lost_points = 2  # -2 combined
    state.add_leader(fool)
    state.add_leader(hero)

    holder = resolve_office_holder(state, Office.BATTLE_FOOL)

    assert holder is not None
    assert holder.leader_id == 1  # -(-5) = 5 beats -(-2) = 2
    assert holder.merit_points == 5


def test_resolve_office_holder_curator_counts_held_items():
    state = make_state()
    leader = LeaderState(1, 1, "Aldric", HOME, is_king=True)
    state.add_leader(leader)
    state.add_item(Treasure.WAND_FIREBALL, owner_leader_id=1)
    state.add_item(Treasure.WAND_CHARM, owner_leader_id=1)
    state.add_item(Treasure.WAND_BLESS, owner_leader_id=1)

    holder = resolve_office_holder(state, Office.CURATOR)

    assert holder is not None
    assert holder.leader_id == 1
    assert holder.merit_points == 3


def test_resolve_office_holder_bravest_none_below_the_minimum():
    # Office.BRAVEST has OFFICE_MIN_POINTS == 15 (models/office.py).
    state = make_state()
    leader = LeaderState(1, 1, "Aldric", HOME, is_king=True)
    leader.merit_tally.bravery_merit = 14
    state.add_leader(leader)

    assert resolve_office_holder(state, Office.BRAVEST) is None

    leader.merit_tally.bravery_merit = 15
    holder = resolve_office_holder(state, Office.BRAVEST)
    assert holder is not None
    assert holder.leader_id == 1


def test_resolve_office_holder_air_force_praetor_flagship_are_not_leader_scoped():
    # Army-scoped (Phase 394: resolve_army_office_holder()), not
    # leader-scoped -- they don't fit RANKED_OFFICES/OfficeHolder's
    # leader_id-only shape, so they stay out of it permanently, not just
    # until some future phase (see turn/office_holder.py's own Phase 394
    # addendum).
    assert Office.AIR_FORCE not in RANKED_OFFICES
    assert Office.PRAETOR not in RANKED_OFFICES
    assert Office.FLAGSHIP not in RANKED_OFFICES


# -- Army-scoped Royal Titles: Airforce/Praetor/Flagship (Phase 394) ------


def test_resolve_army_office_holder_airforce_picks_the_stronger_flying_army():
    state = make_state()
    state.add_province(ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_province(ProvinceState(HexCoord(1, 1), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2))
    state.add_army(ArmyState(101, 1, ArmyType.DRAGON_WING, Quality.ELITE, HOME))
    state.add_army(ArmyState(201, 2, ArmyType.EAGLE_WING, Quality.CRACK, HexCoord(1, 1)))

    holder = resolve_army_office_holder(state, Office.AIR_FORCE)

    assert holder is not None
    assert holder.army_id == 101  # Elite Dragon Wing beats Crack Eagle Wing


def test_resolve_army_office_holder_airforce_excludes_non_flying_types():
    state = make_state()
    state.add_province(ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_army(ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, HOME))

    assert resolve_army_office_holder(state, Office.AIR_FORCE) is None


def test_resolve_army_office_holder_requires_crack_or_elite_quality():
    # AVERAGE, not VETERAN: HOME is kingdom 1's own home province too, so
    # the peacetime home-province +1 bonus (turn/army_quality.py) would
    # otherwise lift VETERAN straight to CRACK and defeat the point of
    # this test.
    state = make_state()
    state.add_province(ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_army(ArmyState(101, 1, ArmyType.DRAGON_WING, Quality.AVERAGE, HOME))

    assert resolve_army_office_holder(state, Office.AIR_FORCE) is None


def test_resolve_army_office_holder_requires_a_valid_player_owner():
    state = make_state()
    state.add_province(ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_army(ArmyState(101, None, ArmyType.DRAGON_WING, Quality.ELITE, HOME))  # mercenary

    assert resolve_army_office_holder(state, Office.AIR_FORCE) is None


def test_resolve_army_office_holder_praetor_excludes_flying_types():
    state = make_state()
    state.add_province(ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_army(ArmyState(101, 1, ArmyType.DRAGON_WING, Quality.ELITE, HOME))

    assert resolve_army_office_holder(state, Office.PRAETOR) is None


def test_resolve_army_office_holder_praetor_picks_the_stronger_non_flying_army():
    state = make_state()
    state.add_province(ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_province(ProvinceState(HexCoord(1, 1), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2))
    state.add_army(ArmyState(101, 1, ArmyType.HVY_CAVALRY, Quality.ELITE, HOME))
    state.add_army(ArmyState(201, 2, ArmyType.LEGION, Quality.CRACK, HexCoord(1, 1)))

    holder = resolve_army_office_holder(state, Office.PRAETOR)

    assert holder is not None
    assert holder.army_id == 101


def test_resolve_army_office_holder_flagship_requires_a_naval_army_type():
    state = make_state()
    state.add_province(ProvinceState(HOME, Terrain.SEA, Race.HUMAN, owner_kingdom_id=1))
    state.add_army(ArmyState(101, 1, ArmyType.LEGION, Quality.ELITE, HOME))  # land, not naval

    assert resolve_army_office_holder(state, Office.FLAGSHIP) is None


def test_resolve_army_office_holder_flagship_picks_among_mermen_whale_fleet():
    state = make_state()
    state.add_province(ProvinceState(HOME, Terrain.SEA, Race.HUMAN, owner_kingdom_id=1))
    state.add_province(ProvinceState(HexCoord(1, 1), Terrain.SEA, Race.HUMAN, owner_kingdom_id=2))
    state.add_army(ArmyState(101, 1, ArmyType.WHALES, Quality.ELITE, HOME))
    state.add_army(ArmyState(201, 2, ArmyType.FLEET, Quality.CRACK, HexCoord(1, 1)))

    holder = resolve_army_office_holder(state, Office.FLAGSHIP)

    assert holder is not None
    assert holder.army_id == 101


def test_resolve_all_army_office_holders_covers_all_three_titles():
    state = make_state()
    state.add_province(ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1))
    state.add_army(ArmyState(101, 1, ArmyType.DRAGON_WING, Quality.ELITE, HOME))

    holders = resolve_all_army_office_holders(state)

    assert set(holders) == set(ARMY_RANKED_OFFICES)
    assert holders[Office.AIR_FORCE] is not None
    assert holders[Office.PRAETOR] is None
    assert holders[Office.FLAGSHIP] is None


# -- Phase 438: office ranking primitives (Rank/ftoppts/per-Kingdom Best Hope/runner-up) --


def _ranking_state() -> GameState:
    # Aldric and Cedric (both Attackia, kingdom 1) tie at 10 Defender
    # points; Borin (Defendia, kingdom 2) trails at 5.
    state = make_state()
    aldric = LeaderState(1, 1, "Aldric", HOME, is_king=True)
    aldric.merit_tally.monster_hp_defeated = 10
    cedric = LeaderState(3, 1, "Cedric", HOME)
    cedric.merit_tally.monster_hp_defeated = 10
    borin = LeaderState(2, 2, "Borin", HexCoord(1, 1), is_king=True)
    borin.merit_tally.monster_hp_defeated = 5
    state.add_leader(aldric)
    state.add_leader(cedric)
    state.add_leader(borin)
    return state


def test_leader_office_rank_ties_share_the_same_rank():
    state = _ranking_state()

    assert leader_office_rank(state, Office.DEFENDER, 1) == 1  # Aldric: nobody strictly beats 10
    assert leader_office_rank(state, Office.DEFENDER, 3) == 1  # Cedric: tied with Aldric, not beaten
    assert leader_office_rank(state, Office.DEFENDER, 2) == 3  # Borin: beaten by both Aldric and Cedric


def test_office_rival_best_points_excludes_the_querying_kingdom():
    state = _ranking_state()

    assert office_rival_best_points(state, Office.DEFENDER, 1) == 5  # Attackia's own rival is Borin (5)
    assert office_rival_best_points(state, Office.DEFENDER, 2) == 10  # Defendia's own rival is Aldric/Cedric (10)


def test_office_rival_best_points_zero_when_nobody_else_is_a_candidate():
    state = make_state()
    state.add_leader(LeaderState(1, 1, "Aldric", HOME, is_king=True))

    assert office_rival_best_points(state, Office.DEFENDER, 1) == 0


def test_kingdom_best_candidate_picks_the_kingdoms_own_top_scorer():
    state = _ranking_state()

    best = kingdom_best_candidate(state, Office.DEFENDER, 1)

    assert best is not None
    assert best.leader_id == 1  # Aldric, tied with Cedric but encountered first
    assert best.merit_points == 10


def test_kingdom_best_candidate_ignores_the_minimum_points_gate():
    # Unlike resolve_office_holder(), the real pre-election "Best Hope"
    # scan never gates on OFFICE_MIN_POINTS -- a 0-point candidate is
    # still this kingdom's own best (and only) candidate.
    state = make_state()
    state.add_leader(LeaderState(1, 1, "Aldric", HOME, is_king=True))  # 0 Merit Points

    assert resolve_office_holder(state, Office.MARSHAL) is None
    best = kingdom_best_candidate(state, Office.MARSHAL, 1)
    assert best is not None
    assert best.leader_id == 1
    assert best.merit_points == 0


def test_kingdom_runner_up_is_the_kingdoms_own_second_best_excluding_the_top():
    state = _ranking_state()

    runner_up = kingdom_runner_up(state, Office.DEFENDER, 1, exclude_leader_id=1)

    assert runner_up is not None
    assert runner_up.leader_id == 3  # Cedric, Attackia's own remaining candidate
    assert runner_up.merit_points == 10


def test_kingdom_runner_up_none_when_the_kingdom_has_only_one_candidate():
    state = _ranking_state()

    assert kingdom_runner_up(state, Office.DEFENDER, 2, exclude_leader_id=2) is None


def test_leader_office_rank_and_kingdom_best_candidate_handle_emperor():
    state = make_state()
    state.add_leader(LeaderState(1, 1, "Aldric", HOME, is_king=True))
    state.add_leader(LeaderState(2, 2, "Borin", HexCoord(1, 1), is_king=True))
    state.add_province(ProvinceState(HOME, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=1, tax=8))
    state.add_province(ProvinceState(HexCoord(1, 1), Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=2, tax=3))

    assert leader_office_rank(state, Office.EMPEROR, 1) == 1  # Aldric's Tax_Base (8) beats Borin's (3)
    assert leader_office_rank(state, Office.EMPEROR, 2) == 2

    best = kingdom_best_candidate(state, Office.EMPEROR, 2)
    assert best is not None
    assert best.leader_id == 2
    assert best.merit_points == 3


# -- Phase 468: apply_cravenest_temperament_escalation() ------------------


def test_apply_cravenest_temperament_escalation_raises_a_valid_titleholders_temper():
    state = make_state()
    leader = LeaderState(1, 1, "Aldric", HOME, is_king=True, temper=Temper.COWARDLY)
    # King of Cowards is confirmed structurally unreachable via the real
    # merit-accrual path (courage_encounter_merit can only ever be <= 0)
    # -- inflated directly here, matching the report's own counterfactual
    # framing ("se fosse presente un titolare valido"), to prove the
    # *effect* itself works once a holder somehow exists.
    leader.merit_tally.courage_encounter_merit = 10
    state.add_leader(leader)

    apply_cravenest_temperament_escalation(state)

    assert state.leaders[1].temper == Temper.CAUTIOUS


def test_apply_cravenest_temperament_escalation_caps_at_berserk():
    state = make_state()
    leader = LeaderState(1, 1, "Aldric", HOME, is_king=True, temper=Temper.BERSERK)
    leader.merit_tally.courage_encounter_merit = 10
    state.add_leader(leader)

    apply_cravenest_temperament_escalation(state)

    assert state.leaders[1].temper == Temper.BERSERK


def test_apply_cravenest_temperament_escalation_is_a_noop_under_real_generated_data():
    # No leader's own courage_encounter_merit was artificially inflated
    # here -- resolve_office_holder(state, Office.CRAVENEST) finds nobody
    # meeting OFFICE_MIN_POINTS, exactly as the confirmed compiled bug
    # predicts, so the escalation has nothing to apply to.
    state = make_state()
    leader = LeaderState(1, 1, "Aldric", HOME, is_king=True, temper=Temper.COWARDLY)
    state.add_leader(leader)

    apply_cravenest_temperament_escalation(state)

    assert state.leaders[1].temper == Temper.COWARDLY


def test_apply_cravenest_temperament_escalation_skips_a_titleholder_with_no_recorded_temper():
    state = make_state()
    leader = LeaderState(1, 1, "Aldric", HOME, is_king=True, temper=None)
    leader.merit_tally.courage_encounter_merit = 10
    state.add_leader(leader)

    apply_cravenest_temperament_escalation(state)  # must not raise

    assert state.leaders[1].temper is None
