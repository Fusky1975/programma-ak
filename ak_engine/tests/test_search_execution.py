from __future__ import annotations

import random
from unittest.mock import ANY, patch

import pytest

from ak_engine.models.advanced_ability import AdvancedAbility
from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.enums import Ability, Maneuver, Spell
from ak_engine.models.feature import Feature, FeatureType
from ak_engine.models.game_state import ArmyState, GameState, KingdomState, LeaderState, ProvinceState
from ak_engine.models.game_type import GameType
from ak_engine.models.kingdom import SkillTable
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.monster import MONSTER_COMBAT_STATS, Monster, MonsterEngagementState, MonsterSpeed
from ak_engine.models.office import Office
from ak_engine.models.power import Power
from ak_engine.models.race import Race
from ak_engine.models.sex import Sex
from ak_engine.models.temper import Temper
from ak_engine.models.treasure import Treasure
from ak_engine.models.valhalla import VALHALLA_VISITOR_LEADER_ID
from ak_engine.turn.combat import Quality
from ak_engine.turn.encounter import (
    CHARACTER_HIT_POINTS,
    FIRE_ARROW_DAMAGE_RANGE,
    Combatant,
    EncounterCombatResult,
    FireArrowShot,
    MeleeRoundOutcome,
    MeleeSwing,
    MonsterTalkReply,
    ReactiveMeleeSwingResult,
)
from ak_engine.turn.search_decode import SearchRequest, SearchTactic
from ak_engine.turn.search_execution import (
    FLEE_CHANCE,
    INVISIBILITY_FLEE_CHANCE_BONUS,
    MELEE_EVASION_FLEE_CHANCE_BONUS,
    TROLL_REGENERATION_PER_COMBAT_ROUND,
    WEAK_TEMPER_FLEE_CHANCE_BONUS,
    SearchExecutionResult,
    _leader_combatant,
    effective_flee_chance,
    execute_search,
)

from _helpers import ScriptedRandom

LOCATION = HexCoord(3, 9)
LEADER_ID = 1


def _state_with_leader(*, skills: SkillTable | None = None, temper: Temper | None = None) -> GameState:
    state = GameState()
    state.add_leader(LeaderState(LEADER_ID, 1, "Searcher", LOCATION, skills=skills, temper=temper))
    return state


def _melee_request(feature_id: int) -> SearchRequest:
    return SearchRequest(feature_id=feature_id, unconfirmed_extra0=0, tactics=[SearchTactic(maneuver=Maneuver.MELEE)])


def _steal_request(feature_id: int, *following: Maneuver) -> SearchRequest:
    tactics = [SearchTactic(maneuver=Maneuver.STEAL)]
    tactics += [SearchTactic(maneuver=m) for m in following]
    return SearchRequest(feature_id=feature_id, unconfirmed_extra0=0, tactics=tactics)


def _talk_request(feature_id: int, *following: Maneuver) -> SearchRequest:
    tactics = [SearchTactic(maneuver=Maneuver.TALK)]
    tactics += [SearchTactic(maneuver=m) for m in following]
    return SearchRequest(feature_id=feature_id, unconfirmed_extra0=0, tactics=tactics)


def _beg_request(feature_id: int, *following: Maneuver) -> SearchRequest:
    # Beg only ever makes sense after taking a hit, so every wiring test
    # opens with a Shoot tactic (mocked to damage the leader without
    # ending the encounter) ahead of the Beg tactic under test.
    tactics = [SearchTactic(maneuver=Maneuver.SHOOT), SearchTactic(maneuver=Maneuver.BEG)]
    tactics += [SearchTactic(maneuver=m) for m in following]
    return SearchRequest(feature_id=feature_id, unconfirmed_extra0=0, tactics=tactics)


def _damage_leader_fire_arrow_duel(leader_combatant, monster_combatant, rng):
    leader_combatant.hit_points -= 3
    return EncounterCombatResult(winner=None, rounds=1)


def test_execute_search_rejected_for_a_leader_protected_by_analytical_psychology():
    # Phase 302 fix: Discovery.ANALYTICAL_PSYCHOLOGY's own "the charmed
    # character will never Search features" clause -- turn/
    # cast_execution.py's _execute_charm() sets this field on a
    # protected target; execute_search() must refuse before any real
    # encounter resolution runs at all.
    state = _state_with_leader()
    state.leaders[LEADER_ID].analytical_psychology_revert_kingdom_id = 2
    request = _melee_request(1)  # no matching Feature registered -- a real resolution would raise/no-op differently

    result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert result.accepted is False
    assert result.reason == "protected by Analytical Psychology -- a charmed character never Searches"
    assert result.combat_resolved is False


def test_leader_combatant_reads_real_temper():
    state = GameState()
    leader = LeaderState(LEADER_ID, 1, "Searcher", LOCATION, temper=Temper.BRAVE)
    state.add_leader(leader)

    combatant = _leader_combatant(state, leader)

    assert combatant.temper is Temper.BRAVE


def test_leader_combatant_gives_the_imperial_defender_a_damage_reduction_of_one():
    # Phase 489: CARICHE E ABLITA.txt's own Office.DEFENDER perk ("reduce
    # any strike against you in personal combat ... by one damage point").
    state = GameState()
    state.add_kingdom(KingdomState(1, "Searchia", Race.HUMAN, Alignment.GOOD, LOCATION))
    leader = LeaderState(LEADER_ID, 1, "Searcher", LOCATION)
    leader.merit_tally.monster_hp_defeated = 1  # meets OFFICE_MIN_POINTS[Office.DEFENDER]
    state.add_leader(leader)

    combatant = _leader_combatant(state, leader)

    assert combatant.damage_reduction == 1


def test_leader_combatant_reads_the_melee_hit_points_advanced_ability():
    # Phase 516: AdvancedAbility.MELEE_HIT_POINTS.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Searchia", Race.HUMAN, Alignment.GOOD, LOCATION))
    leader = LeaderState(LEADER_ID, 1, "Searcher", LOCATION, advanced_abilities={AdvancedAbility.MELEE_HIT_POINTS})
    state.add_leader(leader)

    combatant = _leader_combatant(state, leader)

    assert combatant.has_melee_hit_points_ability is True


def test_leader_combatant_reads_melee_mastery():
    # Phase 517: AdvancedAbility.MELEE_MASTERY/MELEE_TRUE_MASTERY.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Searchia", Race.HUMAN, Alignment.GOOD, LOCATION))
    leader = LeaderState(LEADER_ID, 1, "Searcher", LOCATION, advanced_abilities={AdvancedAbility.MELEE_MASTERY})
    state.add_leader(leader)

    combatant = _leader_combatant(state, leader)

    assert combatant.offensive_hit_multiplier == pytest.approx(1.10)
    assert combatant.melee_damage_dealt_bonus == 1


def test_leader_combatant_reads_melee_true_mastery():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Searchia", Race.HUMAN, Alignment.GOOD, LOCATION))
    leader = LeaderState(LEADER_ID, 1, "Searcher", LOCATION, advanced_abilities={AdvancedAbility.MELEE_TRUE_MASTERY})
    state.add_leader(leader)

    combatant = _leader_combatant(state, leader)

    assert combatant.offensive_hit_multiplier == 1.0
    assert combatant.melee_damage_dealt_bonus == 2


def test_leader_combatant_reads_equipped_weapon_hit_and_damage_bonus():
    # Phase 535: AKGEN_reverse_engineering_report (4).md SS7.2.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Searchia", Race.HUMAN, Alignment.GOOD, LOCATION))
    leader = LeaderState(LEADER_ID, 1, "Searcher", LOCATION)
    state.add_leader(leader)
    state.add_item(Treasure.WEAPON_3, owner_leader_id=LEADER_ID)  # Flaming Scimitar: +20%/+3

    combatant = _leader_combatant(state, leader)

    assert combatant.offensive_hit_multiplier == pytest.approx(1.20)
    assert combatant.melee_damage_dealt_bonus == 3


def test_leader_combatant_reads_bow_of_the_elven_kings_archery_bonus():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Searchia", Race.HUMAN, Alignment.GOOD, LOCATION))
    leader = LeaderState(LEADER_ID, 1, "Searcher", LOCATION)
    state.add_leader(leader)
    state.add_item(Treasure.LEADERSHIP_ELVEN, owner_leader_id=LEADER_ID)
    state.add_item(Treasure.LEADERSHIP_ELVEN, owner_leader_id=LEADER_ID)  # doesn't stack

    combatant = _leader_combatant(state, leader)

    assert combatant.archery_hit_multiplier == pytest.approx(1.25)
    assert combatant.missile_damage_dealt_bonus == 2
    assert combatant.offensive_hit_multiplier == 1.0
    assert combatant.melee_damage_dealt_bonus == 0


def test_leader_combatant_reads_undead_alignment_as_undead_or_anti_holy():
    # Phase 682: SS7.1's Holy Sword vs-Undead bonus needs the combatant's
    # own nature, set independently of any weapon.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Searchia", Race.HUMAN, Alignment.GOOD, LOCATION))
    leader = LeaderState(LEADER_ID, 1, "Searcher", LOCATION, alignment=Alignment.UNDEAD)
    state.add_leader(leader)

    combatant = _leader_combatant(state, leader)

    assert combatant.is_undead_or_anti_holy is True


def test_leader_combatant_reads_non_undead_alignment_as_not_undead_or_anti_holy():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Searchia", Race.HUMAN, Alignment.GOOD, LOCATION))
    leader = LeaderState(LEADER_ID, 1, "Searcher", LOCATION, alignment=Alignment.GOOD)
    state.add_leader(leader)

    combatant = _leader_combatant(state, leader)

    assert combatant.is_undead_or_anti_holy is False


def test_leader_combatant_reads_holy_sword_auto_protection():
    # Phase 536: AKGEN_reverse_engineering_report (4).md SS7.3.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Searchia", Race.HUMAN, Alignment.GOOD, LOCATION))
    leader = LeaderState(LEADER_ID, 1, "Searcher", LOCATION)
    state.add_leader(leader)
    state.add_item(Treasure.WEAPON_1, owner_leader_id=LEADER_ID)

    combatant = _leader_combatant(state, leader)

    assert combatant.defensive_hit_multiplier == pytest.approx(0.6)
    assert combatant.is_invisible is False
    assert combatant.equipped_weapon is Treasure.WEAPON_1


def test_leader_combatant_reads_invisible_sword_auto_invisibility():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Searchia", Race.HUMAN, Alignment.GOOD, LOCATION))
    leader = LeaderState(LEADER_ID, 1, "Searcher", LOCATION)
    state.add_leader(leader)
    state.add_item(Treasure.WEAPON_5, owner_leader_id=LEADER_ID)

    combatant = _leader_combatant(state, leader)

    assert combatant.is_invisible is True
    assert combatant.defensive_hit_multiplier == pytest.approx(0.5)
    assert combatant.equipped_weapon is Treasure.WEAPON_5


def test_leader_combatant_reads_arcane_valor_scepter_hit_points_bonus():
    # Phase 538: AKGEN_reverse_engineering_report (4).md SS11.2.
    state = GameState(game_type=GameType.ARCANES)
    state.add_kingdom(KingdomState(1, "Searchia", Race.HUMAN, Alignment.GOOD, LOCATION))
    leader = LeaderState(LEADER_ID, 1, "Searcher", LOCATION)
    state.add_leader(leader)
    state.add_item(Treasure.NAMED_UNIQUE_SCEPTER_LIFE, owner_leader_id=LEADER_ID)

    combatant = _leader_combatant(state, leader)

    assert combatant.hit_points == CHARACTER_HIT_POINTS + 5


def test_leader_combatant_reads_duellists_medal_and_kingdom_race_humanoid():
    # Phase 518: AdvancedAbility.MELEE_DUELLISTS_MEDAL + is_humanoid.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Searchia", Race.HUMAN, Alignment.GOOD, LOCATION))
    leader = LeaderState(LEADER_ID, 1, "Searcher", LOCATION, advanced_abilities={AdvancedAbility.MELEE_DUELLISTS_MEDAL})
    state.add_leader(leader)

    combatant = _leader_combatant(state, leader)

    assert combatant.has_duellists_medal_ability is True
    assert combatant.is_humanoid is True


def test_leader_combatant_reads_control_temper_ability():
    # Phase 519: AdvancedAbility.MELEE_CONTROL_TEMPER.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Searchia", Race.HUMAN, Alignment.GOOD, LOCATION))
    leader = LeaderState(LEADER_ID, 1, "Searcher", LOCATION, advanced_abilities={AdvancedAbility.MELEE_CONTROL_TEMPER})
    state.add_leader(leader)

    combatant = _leader_combatant(state, leader)

    assert combatant.has_control_temper_ability is True


def test_leader_combatant_reads_archery_free_attack_bonus():
    # Phase 520: AdvancedAbility.ARCHERY_FREE_ATTACK/_MASTERY/_TRUE_MASTERY.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Searchia", Race.HUMAN, Alignment.GOOD, LOCATION))
    leader = LeaderState(LEADER_ID, 1, "Searcher", LOCATION, advanced_abilities={AdvancedAbility.ARCHERY_FREE_ATTACK})
    state.add_leader(leader)

    combatant = _leader_combatant(state, leader)

    assert combatant.archery_free_attack_bonus == 1


def test_execute_search_leader_not_found():
    state = GameState()
    result = execute_search(state, LEADER_ID, _melee_request(1))
    assert result == SearchExecutionResult(accepted=False, reason="leader not found")


def test_execute_search_feature_not_found():
    state = _state_with_leader()
    result = execute_search(state, LEADER_ID, _melee_request(99))
    assert result.accepted is False
    assert result.reason == "feature not found"


def test_execute_search_already_looted_feature_rejected():
    state = _state_with_leader()
    state.add_feature(
        Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE, looted=True)
    )
    result = execute_search(state, LEADER_ID, _melee_request(1))
    assert result.accepted is False
    assert result.reason == "feature already looted"


def test_execute_search_no_guardian_recorded_rejected():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=None))
    result = execute_search(state, LEADER_ID, _melee_request(1))
    assert result.accepted is False
    assert result.reason == "feature has no guardian recorded"


def test_execute_search_not_co_located_rejected():
    state = _state_with_leader()
    elsewhere = HexCoord(9, 9)
    state.add_feature(Feature(feature_id=1, coord=elsewhere, kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE))
    result = execute_search(state, LEADER_ID, _melee_request(1))
    assert result.accepted is False
    assert result.reason == "not co-located with feature"


def test_execute_search_unsourced_guardian_stats_reports_unresolved():
    # Monster.NOMONSTER is the "no monster" sentinel, not a real species --
    # it has no MONSTER_COMBAT_STATS entry by design (Phase 154 gave all
    # 60 real species combat stats, so NOMONSTER is the one remaining
    # guaranteed-unsourced case).
    state = _state_with_leader()
    state.add_feature(
        Feature(feature_id=1, coord=LOCATION, kind=FeatureType.PET_FOREST, guardian_monster=Monster.NOMONSTER)
    )
    result = execute_search(state, LEADER_ID, _melee_request(1))
    assert result.accepted is True
    assert result.combat_resolved is False
    assert "no combat stats" in result.reason


def test_execute_search_previously_unsourced_species_now_resolves():
    # Monster.ROC had no MONSTER_STATS entry before Phase 154; it now has
    # a MONSTER_COMBAT_STATS entry (project-original data) and resolves
    # real combat like any other species.
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.PET_FOREST, guardian_monster=Monster.ROC))

    result = execute_search(state, LEADER_ID, _melee_request(1), random.Random(1))

    assert result.accepted is True
    assert result.combat_resolved is True
    assert result.reason is None


def test_execute_search_no_melee_tactic_reports_unresolved():
    state = _state_with_leader()
    state.add_feature(
        Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE)
    )
    scout_only = SearchRequest(feature_id=1, unconfirmed_extra0=0, tactics=[SearchTactic(maneuver=Maneuver.SCOUT)])

    result = execute_search(state, LEADER_ID, scout_only)

    assert result.accepted is True
    assert result.combat_resolved is False
    assert "no Melee or Fire Arrow tactic" in result.reason


def test_execute_search_leader_wins_marks_feature_looted():
    # A leader with high Melee skill (level 9) always acts first against
    # a Gargoyle (melee_skill=1); scripted so the leader always hits and
    # the Gargoyle (15 hp) always misses.
    raw = [0] * 30
    raw[Ability.MELEE.value * 2] = 9
    raw[Ability.MELEE.value * 2 + 1] = 9
    state = _state_with_leader(skills=SkillTable(raw_values=raw))
    feature = Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE)
    state.add_feature(feature)
    block = [0.1, 0.5, 0.9]  # leader hits (chance+damage), Gargoyle misses
    rng = ScriptedRandom(block * 20)

    result = execute_search(state, LEADER_ID, _melee_request(1), rng)

    assert result.accepted is True
    assert result.combat_resolved is True
    assert result.winner == "leader"
    assert result.feature_looted is True
    assert feature.looted is True
    assert LEADER_ID in state.leaders


def test_execute_search_leader_wins_grants_the_features_own_treasure():
    # Phase 242: a winning Search now actually grants the feature's own
    # treasure (if world generation set one) via the item registry.
    raw = [0] * 30
    raw[Ability.MELEE.value * 2] = 9
    raw[Ability.MELEE.value * 2 + 1] = 9
    state = _state_with_leader(skills=SkillTable(raw_values=raw))
    feature = Feature(
        feature_id=1,
        coord=LOCATION,
        kind=FeatureType.DUNGEON,
        guardian_monster=Monster.GARGOYLE,
        treasure=Treasure.ABILITY_TACTICAL,
    )
    state.add_feature(feature)
    block = [0.1, 0.5, 0.9]
    rng = ScriptedRandom(block * 20)

    result = execute_search(state, LEADER_ID, _melee_request(1), rng)

    assert result.winner == "leader"
    granted = [item for item in state.items.values() if item.owner_leader_id == LEADER_ID]
    assert len(granted) == 1
    assert granted[0].treasure is Treasure.ABILITY_TACTICAL


# -- Phase 548: Valhalla visitor Gold Hoard routing --


def test_execute_search_routes_a_gold_hoard_to_the_king_when_the_visitor_wins():
    # VALHALLA.txt rule 1: "any monetary treasure Vahlalla visitor
    # captures will be given to you" -- immediate hand-off to the King,
    # not held by the visitor like magic treasure (rule 2).
    raw = [0] * 30
    raw[Ability.MELEE.value * 2] = 9
    raw[Ability.MELEE.value * 2 + 1] = 9
    state = GameState()
    state.add_leader(LeaderState(1, 1, "King Foo", LOCATION, is_king=True))
    state.add_leader(
        LeaderState(199, 1, "Visitor", LOCATION, skills=SkillTable(raw_values=raw), valhalla_active_turn=1)
    )
    feature = Feature(
        feature_id=1,
        coord=LOCATION,
        kind=FeatureType.DUNGEON,
        guardian_monster=Monster.GARGOYLE,
        treasure=Treasure.GOLD_HOARD_LARGE,
    )
    state.add_feature(feature)
    rng = ScriptedRandom([0.1, 0.5, 0.9] * 20)

    result = execute_search(state, 199, _melee_request(1), rng)

    assert result.winner == "leader"
    assert state.items_held_by(199) == []
    king_items = state.items_held_by(1)
    assert len(king_items) == 1
    assert king_items[0].treasure is Treasure.GOLD_HOARD_LARGE


def test_execute_search_grants_a_non_gold_treasure_to_the_visitor_directly():
    # Magic treasure (rule 2) stays with the visitor until departure --
    # only Gold Hoard (rule 1) routes immediately.
    raw = [0] * 30
    raw[Ability.MELEE.value * 2] = 9
    raw[Ability.MELEE.value * 2 + 1] = 9
    state = GameState()
    state.add_leader(LeaderState(1, 1, "King Foo", LOCATION, is_king=True))
    state.add_leader(
        LeaderState(199, 1, "Visitor", LOCATION, skills=SkillTable(raw_values=raw), valhalla_active_turn=1)
    )
    feature = Feature(
        feature_id=1,
        coord=LOCATION,
        kind=FeatureType.DUNGEON,
        guardian_monster=Monster.GARGOYLE,
        treasure=Treasure.ABILITY_TACTICAL,
    )
    state.add_feature(feature)
    rng = ScriptedRandom([0.1, 0.5, 0.9] * 20)

    result = execute_search(state, 199, _melee_request(1), rng)

    assert result.winner == "leader"
    assert state.items_held_by(1) == []
    visitor_items = state.items_held_by(199)
    assert len(visitor_items) == 1
    assert visitor_items[0].treasure is Treasure.ABILITY_TACTICAL


def test_execute_search_leader_wins_without_treasure_grants_nothing():
    # A feature created without going through world generation (treasure=None,
    # the default) grants no item -- confirmed no silent fabrication.
    raw = [0] * 30
    raw[Ability.MELEE.value * 2] = 9
    raw[Ability.MELEE.value * 2 + 1] = 9
    state = _state_with_leader(skills=SkillTable(raw_values=raw))
    feature = Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE)
    state.add_feature(feature)
    block = [0.1, 0.5, 0.9]
    rng = ScriptedRandom(block * 20)

    result = execute_search(state, LEADER_ID, _melee_request(1), rng)

    assert result.winner == "leader"
    assert state.items == {}


def test_execute_search_leader_loses_is_removed_from_state():
    # A leaderless-skill searcher (melee_skill=0) faces a Troll
    # (melee_skill=1): the Troll always acts first and always hits;
    # the leader (10 hp) always misses.
    state = _state_with_leader()
    feature = Feature(feature_id=1, coord=LOCATION, kind=FeatureType.CAVE, guardian_monster=Monster.TROLL)
    state.add_feature(feature)
    block = [0.1, 0.5, 0.9]  # Troll hits (chance+damage), leader misses
    rng = ScriptedRandom(block * 20)

    result = execute_search(state, LEADER_ID, _melee_request(1), rng)

    assert result.accepted is True
    assert result.combat_resolved is True
    assert result.winner == "monster"
    assert result.leader_killed is True
    assert LEADER_ID not in state.leaders
    assert LEADER_ID in state.dead_leaders
    assert feature.looted is False


# -- Phase 255: Defender Merit Points (rulebook page 51) --


def test_execute_search_leader_win_credits_the_monsters_starting_hit_points():
    # resolve_melee_duel is mocked so the win is instant -- the monster's
    # own hit_points draw (the very first rng call execute_search makes,
    # before the tactic walk even starts) is independently reproduced
    # here from a freshly-seeded Random(0) for comparison.
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.CAVE, guardian_monster=Monster.GARGOYLE))
    expected_hp = random.Random(0).randint(*MONSTER_COMBAT_STATS[Monster.GARGOYLE].hit_points_range)

    with patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_resolve:
        mock_resolve.return_value = EncounterCombatResult(winner="a", rounds=1)
        result = execute_search(state, LEADER_ID, _melee_request(1), random.Random(0))

    assert result.winner == "leader"
    assert state.leaders[LEADER_ID].merit_tally.monster_hp_defeated == expected_hp
    # A real combat win credits the "killed" half only -- the negotiated
    # half is a separate, Fulfill-only path (Phase 258, see below).
    assert state.leaders[LEADER_ID].merit_tally.monster_hp_neutralized == 0


def test_execute_search_leader_loss_credits_nothing():
    state = _state_with_leader()
    feature = Feature(feature_id=1, coord=LOCATION, kind=FeatureType.CAVE, guardian_monster=Monster.TROLL)
    state.add_feature(feature)
    block = [0.1, 0.5, 0.9]  # Troll hits (chance+damage), leader misses
    rng = ScriptedRandom(block * 20)

    result = execute_search(state, LEADER_ID, _melee_request(1), rng)

    assert result.winner == "monster"
    # The leader is dead -- nothing left in state.leaders to credit, and
    # the monster (the winner here) has no MeritTally of its own either.
    assert LEADER_ID not in state.leaders


# -- Phase 462: Duellist/Cravenest/Bravest monster-opponent merit --


def test_execute_search_leader_win_against_eligible_monster_awards_duel_and_bravery_merit():
    # Monster.BIGFOOT is ordinal 13, inside the compiled Giant..Witch
    # (12..21) group -- AKGEN_reverse_engineering_report (2).md SS17.3.
    # Missile-skill 0 (no Fire Arrow phase) keeps the mocked Melee win
    # the only thing that touches the leader's own hit points.
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.BIGFOOT))
    wounded_combatant = Combatant(name="Searcher", hit_points=CHARACTER_HIT_POINTS - 4, melee_skill=0, archery_skill=0)

    with patch("ak_engine.turn.search_execution._leader_combatant", return_value=wounded_combatant), patch(
        "ak_engine.turn.search_execution.resolve_melee_duel"
    ) as mock_resolve:
        mock_resolve.return_value = EncounterCombatResult(winner="a", rounds=1)
        result = execute_search(state, LEADER_ID, _melee_request(1), random.Random(0))

    assert result.winner == "leader"
    tally = state.leaders[LEADER_ID].merit_tally
    assert tally.duel_merit_net == 2
    assert tally.bravery_merit == 4  # CHARACTER_HIT_POINTS - 4 hit points left
    assert tally.courage_encounter_merit == 0


def test_execute_search_leader_win_against_ineligible_monster_awards_no_duel_merit():
    # Monster.GARGOYLE is outside the compiled group entirely.
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.CAVE, guardian_monster=Monster.GARGOYLE))

    with patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_resolve:
        mock_resolve.return_value = EncounterCombatResult(winner="a", rounds=1)
        result = execute_search(state, LEADER_ID, _melee_request(1), random.Random(0))

    assert result.winner == "leader"
    tally = state.leaders[LEADER_ID].merit_tally
    assert tally.duel_merit_net == 0
    assert tally.bravery_merit == 0


def test_execute_search_leader_loss_against_eligible_monster_docks_duel_and_courage_merit():
    # Monster.WITCH is ordinal 21, the other end of the compiled group.
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.WITCH))

    with patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_resolve:
        mock_resolve.return_value = EncounterCombatResult(winner="b", rounds=1)
        result = execute_search(state, LEADER_ID, _melee_request(1), random.Random(0))

    assert result.winner == "monster"
    tally = state.dead_leaders[LEADER_ID].merit_tally
    assert tally.duel_merit_net == -2
    assert tally.courage_encounter_merit == -1
    assert tally.bravery_merit == 0


def test_execute_search_leader_loss_against_ineligible_monster_docks_nothing():
    # Titan (ordinal 11) sits one slot short of the compiled 12..21
    # range -- the source's own deliberate off-by-one exclusion.
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.CAVE, guardian_monster=Monster.TITAN))

    with patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_resolve:
        mock_resolve.return_value = EncounterCombatResult(winner="b", rounds=1)
        result = execute_search(state, LEADER_ID, _melee_request(1), random.Random(0))

    assert result.winner == "monster"
    tally = state.dead_leaders[LEADER_ID].merit_tally
    assert tally.duel_merit_net == 0
    assert tally.courage_encounter_merit == 0


# -- Phase 155: Troll regeneration wiring --


def test_execute_search_sets_troll_regeneration_on_the_monster_combatant():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.CAVE, guardian_monster=Monster.TROLL))

    with patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_resolve:
        mock_resolve.return_value = EncounterCombatResult(winner=None, rounds=1)
        execute_search(state, LEADER_ID, _melee_request(1), random.Random(0))

    monster_combatant = mock_resolve.call_args[0][1]
    assert monster_combatant.regenerates_hp == TROLL_REGENERATION_PER_COMBAT_ROUND


def test_execute_search_non_troll_guardian_has_no_regeneration():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.CAVE, guardian_monster=Monster.GARGOYLE))

    with patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_resolve:
        mock_resolve.return_value = EncounterCombatResult(winner=None, rounds=1)
        execute_search(state, LEADER_ID, _melee_request(1), random.Random(0))

    monster_combatant = mock_resolve.call_args[0][1]
    assert monster_combatant.regenerates_hp == 0


# -- Phase 686: Melee/Archery combat-experience wiring --


def test_execute_search_landed_melee_hit_credits_the_leaders_melee_experience():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.CAVE, guardian_monster=Monster.GARGOYLE))

    with patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_resolve, patch(
        "ak_engine.turn.search_execution.add_experience"
    ) as mock_add_experience:
        mock_resolve.return_value = EncounterCombatResult(
            winner="a", rounds=1, melee_swings=(MeleeSwing(attacker="a", hit=True, damage=3),)
        )
        execute_search(state, LEADER_ID, _melee_request(1), random.Random(0))

    mock_add_experience.assert_any_call(state.leaders[LEADER_ID], Ability.MELEE, 10, ANY)


def test_execute_search_all_miss_melee_credits_nothing():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.CAVE, guardian_monster=Monster.GARGOYLE))

    with patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_resolve, patch(
        "ak_engine.turn.search_execution.add_experience"
    ) as mock_add_experience:
        mock_resolve.return_value = EncounterCombatResult(
            winner="b", rounds=1, melee_swings=(MeleeSwing(attacker="a", hit=False, damage=0),)
        )
        execute_search(state, LEADER_ID, _melee_request(1), random.Random(0))

    mock_add_experience.assert_not_called()


def test_execute_search_landed_fire_arrow_shot_credits_the_leaders_archery_experience():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.CAVE, guardian_monster=Monster.GARGOYLE))
    request = _shoot_request(1, Maneuver.SHOOT)

    with patch("ak_engine.turn.search_execution.resolve_fire_arrow_duel") as mock_resolve, patch(
        "ak_engine.turn.search_execution.add_experience"
    ) as mock_add_experience:
        mock_resolve.return_value = EncounterCombatResult(
            winner="a", rounds=1, shots=(FireArrowShot(shooter="a", hit=True, damage=4),)
        )
        execute_search(state, LEADER_ID, request, random.Random(0))

    mock_add_experience.assert_any_call(state.leaders[LEADER_ID], Ability.ARCHERY, 10, ANY)


# -- Phase 682: is_undead_or_anti_holy on the monster combatant (Holy Sword vs-Undead) --


def test_execute_search_sets_undead_flag_on_an_undead_species_guardian():
    state = _state_with_leader()
    # Vampire is in SPIRITWRACK_UNDEAD_MONSTERS (already relied on elsewhere in this file).
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.CAVE, guardian_monster=Monster.VAMPIRE))

    with patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_resolve:
        mock_resolve.return_value = EncounterCombatResult(winner=None, rounds=1)
        execute_search(state, LEADER_ID, _melee_request(1), random.Random(0))

    monster_combatant = mock_resolve.call_args[0][1]
    assert monster_combatant.is_undead_or_anti_holy is True


def test_execute_search_non_undead_guardian_has_no_undead_flag():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.CAVE, guardian_monster=Monster.GARGOYLE))

    with patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_resolve:
        mock_resolve.return_value = EncounterCombatResult(winner=None, rounds=1)
        execute_search(state, LEADER_ID, _melee_request(1), random.Random(0))

    monster_combatant = mock_resolve.call_args[0][1]
    assert monster_combatant.is_undead_or_anti_holy is False


# -- Phase 169: Flee (rulebook [5.6]) --


def test_flee_chance_matches_the_rulebooks_three_speed_tiers():
    assert FLEE_CHANCE == {
        MonsterSpeed.FAST: 0.20,
        MonsterSpeed.MEDIUM: 0.50,
        MonsterSpeed.SLOW: 0.80,
    }
    # Confirms the tiers line up with real species, not just the enum.
    assert MONSTER_COMBAT_STATS[Monster.GRYPHON].speed is MonsterSpeed.FAST
    assert MONSTER_COMBAT_STATS[Monster.GARGOYLE].speed is MonsterSpeed.MEDIUM
    assert MONSTER_COMBAT_STATS[Monster.GOLEM].speed is MonsterSpeed.SLOW


def test_weak_temper_flee_chance_bonus_stays_at_the_body_texts_30_percent():
    # Phase 312: `Regolamento AK.txt` contradicts itself here -- [5.6]'s own
    # body text says "+30% in piu' di possibilita' di fuggire" for Cauti,
    # but the closing "NUOVE REGOLE E MODIFICHE" appendix restates the same
    # rule as "+20%". The user (project author), asked directly, confirmed
    # +30% is correct -- this guards against the value silently drifting to
    # the appendix's own +20% figure.
    assert WEAK_TEMPER_FLEE_CHANCE_BONUS == pytest.approx(0.30)


# -- effective_flee_chance (Phase 286): Weak-Temperament + Invisibility --


def test_effective_flee_chance_no_temper_no_invisibility_returns_the_base_chance_unchanged():
    assert effective_flee_chance(0.20, temper=None, is_invisible=False) == 0.20


def test_effective_flee_chance_cautious_adds_the_weak_temper_bonus():
    assert effective_flee_chance(0.20, temper=Temper.CAUTIOUS, is_invisible=False) == pytest.approx(
        0.20 + WEAK_TEMPER_FLEE_CHANCE_BONUS
    )


def test_effective_flee_chance_cowardly_gets_the_same_bonus_as_cautious():
    # Phase 286: a confirmed project-original extension beyond the
    # rulebook's own literal "I personaggi Cauti" (Cautious-only) wording
    # -- see module docstring's own Phase 286 addendum for the reasoning.
    assert effective_flee_chance(0.20, temper=Temper.COWARDLY, is_invisible=False) == pytest.approx(
        0.20 + WEAK_TEMPER_FLEE_CHANCE_BONUS
    )


def test_effective_flee_chance_brave_and_berserk_get_no_bonus():
    assert effective_flee_chance(0.50, temper=Temper.BRAVE, is_invisible=False) == 0.50
    assert effective_flee_chance(0.50, temper=Temper.BERSERK, is_invisible=False) == 0.50


def test_effective_flee_chance_invisibility_adds_its_own_bonus_independently_of_temper():
    assert effective_flee_chance(0.20, temper=None, is_invisible=True) == pytest.approx(
        0.20 + INVISIBILITY_FLEE_CHANCE_BONUS
    )


def test_effective_flee_chance_bonuses_stack_and_clamp_at_certainty():
    # Cautious (+30%) and invisible (+30%) on top of an 80% base would be
    # 140% -- clamped to 100%, since a probability can't exceed certainty.
    assert effective_flee_chance(0.80, temper=Temper.CAUTIOUS, is_invisible=True) == 1.0


def test_effective_flee_chance_melee_evasion_adds_its_own_bonus_independently():
    # Phase 515: Melee Evasion Advanced Ability -- a third additive
    # bonus, same shape as Invisibility.
    assert effective_flee_chance(0.20, temper=None, is_invisible=False, has_melee_evasion=True) == pytest.approx(
        0.20 + MELEE_EVASION_FLEE_CHANCE_BONUS
    )


def test_effective_flee_chance_melee_evasion_stacks_with_temper_and_invisibility():
    assert effective_flee_chance(
        0.05, temper=Temper.CAUTIOUS, is_invisible=True, has_melee_evasion=True
    ) == pytest.approx(
        0.05 + WEAK_TEMPER_FLEE_CHANCE_BONUS + INVISIBILITY_FLEE_CHANCE_BONUS + MELEE_EVASION_FLEE_CHANCE_BONUS
    )


def test_effective_flee_chance_melee_evasion_defaults_to_false():
    assert effective_flee_chance(0.20, temper=None, is_invisible=False) == effective_flee_chance(
        0.20, temper=None, is_invisible=False, has_melee_evasion=False
    )


def test_effective_flee_chance_air_elemental_familiar_guarantees_success():
    # Phase 665: Office.ELE_MAGE -- "all flee attempts are automatically
    # successful," an unconditional override, not another additive bonus.
    assert effective_flee_chance(
        0.20, temper=Temper.BRAVE, is_invisible=False, has_air_elemental_familiar=True
    ) == 1.0


def test_effective_flee_chance_air_elemental_familiar_defaults_to_false():
    assert effective_flee_chance(0.20, temper=None, is_invisible=False) == effective_flee_chance(
        0.20, temper=None, is_invisible=False, has_air_elemental_familiar=False
    )


def test_execute_search_flee_tactic_success_ends_search_without_combat():
    # Gryphon is Fast (20% flee chance) -- 0.1 < 0.20 succeeds.
    state = _state_with_leader()
    feature = Feature(feature_id=1, coord=LOCATION, kind=FeatureType.CAVE, guardian_monster=Monster.GRYPHON)
    state.add_feature(feature)
    request = SearchRequest(
        feature_id=1, unconfirmed_extra0=0, tactics=[SearchTactic(maneuver=Maneuver.FLEE), SearchTactic(maneuver=Maneuver.MELEE)]
    )

    # Padding: the monster's own hit_points draw (rng.randint()) now runs
    # before the tactic walk even starts, consuming an unknown number of
    # randoms from the front of the queue -- every value here is 0.1 (< the
    # 20% flee chance), so whichever one lands on the flee roll still succeeds.
    result = execute_search(state, LEADER_ID, request, ScriptedRandom([0.1] * 20))

    assert result.accepted is True
    assert result.combat_resolved is False
    assert result.fled is True
    assert result.winner is None
    assert feature.looted is False
    assert LEADER_ID in state.leaders


def test_execute_search_flee_tactic_failure_falls_through_to_melee():
    # Gryphon is Fast (20% flee chance) -- 0.99 >= 0.20 fails, so the plan's
    # Melee tactic still runs afterward exactly as if Flee weren't there.
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.CAVE, guardian_monster=Monster.GRYPHON))
    request = SearchRequest(
        feature_id=1, unconfirmed_extra0=0, tactics=[SearchTactic(maneuver=Maneuver.FLEE), SearchTactic(maneuver=Maneuver.MELEE)]
    )

    with patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_resolve:
        mock_resolve.return_value = EncounterCombatResult(winner=None, rounds=1)
        # Padding beyond the flee roll: rng.randint() for the monster's hit
        # points draws further from the same scripted queue.
        result = execute_search(state, LEADER_ID, request, ScriptedRandom([0.99] + [0.5] * 10))

    assert mock_resolve.called
    assert result.accepted is True
    assert result.combat_resolved is True
    assert result.fled is False


def test_execute_search_ele_mage_titleholder_flee_always_succeeds():
    # Phase 665: Office.ELE_MAGE's own Air Elemental familiar -- the same
    # 0.99 roll that fails the ordinary 20% Gryphon flee chance in the
    # test above still succeeds outright once the leader holds the title.
    state = _state_with_leader()
    state.add_kingdom(KingdomState(1, "Searchia", Race.HUMAN, Alignment.GOOD, LOCATION))
    state.leaders[LEADER_ID].merit_tally.elemental_spell_casts = 20  # meets OFFICE_MIN_POINTS[Office.ELE_MAGE]
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.CAVE, guardian_monster=Monster.GRYPHON))
    request = SearchRequest(
        feature_id=1, unconfirmed_extra0=0, tactics=[SearchTactic(maneuver=Maneuver.FLEE), SearchTactic(maneuver=Maneuver.MELEE)]
    )

    result = execute_search(state, LEADER_ID, request, ScriptedRandom([0.99] * 20))

    assert result.accepted is True
    assert result.combat_resolved is False
    assert result.fled is True


def test_execute_search_flee_tactic_melee_evasion_widens_the_success_window():
    # Phase 515: Gryphon is Fast (20% base flee chance); a roll of 0.25
    # fails the unmodified chance but clears Melee Evasion's own +30%
    # (0.20 + 0.30 = 0.50).
    state = _state_with_leader()
    state.leaders[LEADER_ID].advanced_abilities.add(AdvancedAbility.MELEE_EVASION)
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.CAVE, guardian_monster=Monster.GRYPHON))
    request = SearchRequest(
        feature_id=1, unconfirmed_extra0=0, tactics=[SearchTactic(maneuver=Maneuver.FLEE), SearchTactic(maneuver=Maneuver.MELEE)]
    )

    result = execute_search(state, LEADER_ID, request, ScriptedRandom([0.25] * 20))

    assert result.fled is True
    assert result.combat_resolved is False


def test_execute_search_no_flee_tactic_never_rolls_for_it():
    # A Melee-only plan against a Fast monster must not flee even though
    # the very first scripted roll (0.1) would satisfy the 20% chance --
    # confirms the roll is only consumed when Flee is actually in the plan.
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.CAVE, guardian_monster=Monster.GRYPHON))

    with patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_resolve:
        mock_resolve.return_value = EncounterCombatResult(winner=None, rounds=1)
        result = execute_search(state, LEADER_ID, _melee_request(1), ScriptedRandom([0.1] + [0.5] * 10))

    assert mock_resolve.called
    assert result.fled is False


def test_execute_search_flee_tactic_cautious_temper_bonus_lets_a_fast_monster_flee_succeed():
    # Gryphon is Fast (20% base) -- 0.35 fails the base chance but
    # succeeds once Cautious' own +30% flee bonus lifts it to 50%.
    state = _state_with_leader(temper=Temper.CAUTIOUS)
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.CAVE, guardian_monster=Monster.GRYPHON))
    request = SearchRequest(
        feature_id=1, unconfirmed_extra0=0, tactics=[SearchTactic(maneuver=Maneuver.FLEE), SearchTactic(maneuver=Maneuver.MELEE)]
    )

    result = execute_search(state, LEADER_ID, request, ScriptedRandom([0.35] * 20))

    assert result.fled is True
    assert result.combat_resolved is False


def test_execute_search_flee_tactic_cowardly_temper_gets_the_same_bonus_as_cautious():
    state = _state_with_leader(temper=Temper.COWARDLY)
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.CAVE, guardian_monster=Monster.GRYPHON))
    request = SearchRequest(
        feature_id=1, unconfirmed_extra0=0, tactics=[SearchTactic(maneuver=Maneuver.FLEE), SearchTactic(maneuver=Maneuver.MELEE)]
    )

    result = execute_search(state, LEADER_ID, request, ScriptedRandom([0.35] * 20))

    assert result.fled is True
    assert result.combat_resolved is False


def test_execute_search_flee_tactic_brave_temper_gets_no_bonus_and_falls_through_to_melee():
    # Same 0.35 roll as the Cautious/Cowardly tests above, but Brave gets
    # no flee-chance bonus at all -- the base 20% still fails, so the
    # plan's own Melee tactic runs afterward instead.
    state = _state_with_leader(temper=Temper.BRAVE)
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.CAVE, guardian_monster=Monster.GRYPHON))
    request = SearchRequest(
        feature_id=1, unconfirmed_extra0=0, tactics=[SearchTactic(maneuver=Maneuver.FLEE), SearchTactic(maneuver=Maneuver.MELEE)]
    )

    with patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_resolve:
        mock_resolve.return_value = EncounterCombatResult(winner=None, rounds=1)
        result = execute_search(state, LEADER_ID, request, ScriptedRandom([0.35] * 20))

    assert result.fled is False
    assert mock_resolve.called


def test_execute_search_cast_invisibility_sets_the_is_invisible_flag():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _cast_request(1, Spell.INVISIBILITY, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.resolve_melee_duel"
    ) as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_search(state, LEADER_ID, request, random.Random(0))

    leader_combatant = mock_melee.call_args[0][0]
    assert leader_combatant.is_invisible is True


def test_execute_search_cast_invisibility_then_flee_gets_the_invisibility_flee_bonus():
    # Gryphon is Fast (20% base) -- 0.35 fails the base chance but
    # succeeds once Invisibility's own +30% flee bonus lifts it to 50%.
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.CAVE, guardian_monster=Monster.GRYPHON))
    request = _cast_request(1, Spell.INVISIBILITY, Maneuver.FLEE)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True):
        result = execute_search(state, LEADER_ID, request, ScriptedRandom([0.35] * 20))

    assert result.fled is True
    assert result.combat_resolved is False


def test_execute_search_cast_augur_combat_not_first_tactic_gets_the_cowardly_flee_bonus():
    # Archer is MEDIUM speed (50% base) -- 0.65 fails the base chance but
    # succeeds once Cowardly's own +30% flee bonus lifts it to 80%.
    leader = _skilled_leader(Ability.PSYCHIC, 5, temper=Temper.COWARDLY)
    state = GameState()
    state.add_leader(leader)
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = SearchRequest(
        feature_id=1,
        unconfirmed_extra0=0,
        tactics=[
            SearchTactic(maneuver=Maneuver.GIVE),
            SearchTactic(maneuver=Maneuver.CAST, sub_object=Spell.AUGUR_COMBAT.value),
            SearchTactic(maneuver=Maneuver.MELEE),
        ],
    )

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.roll_monster_encounter_plan", return_value=()
    ), patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_melee:
        result = execute_search(state, LEADER_ID, request, ScriptedRandom([0.65] * 20))

    assert result.fled is True
    assert result.combat_resolved is False
    assert not mock_melee.called


# -- Phase 170: Fire Arrow (rulebook [5.2]) --


def _shoot_request(feature_id: int, *maneuvers: Maneuver) -> SearchRequest:
    tactics = [SearchTactic(maneuver=m) for m in maneuvers] or [SearchTactic(maneuver=Maneuver.SHOOT)]
    return SearchRequest(feature_id=feature_id, unconfirmed_extra0=0, tactics=tactics)


def test_execute_search_shoot_tactic_leader_wins_marks_feature_looted():
    state = _state_with_leader()
    feature = Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE)
    state.add_feature(feature)

    with patch("ak_engine.turn.search_execution.resolve_fire_arrow_duel") as mock_resolve:
        mock_resolve.return_value = EncounterCombatResult(winner="a", rounds=1)
        result = execute_search(state, LEADER_ID, _shoot_request(1, Maneuver.SHOOT), random.Random(0))

    assert mock_resolve.called
    assert result.accepted is True
    assert result.combat_resolved is True
    assert result.winner == "leader"
    assert result.feature_looted is True
    assert feature.looted is True
    assert LEADER_ID in state.leaders


def test_execute_search_shoot_tactic_monster_wins_removes_leader():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))

    with patch("ak_engine.turn.search_execution.resolve_fire_arrow_duel") as mock_resolve:
        mock_resolve.return_value = EncounterCombatResult(winner="b", rounds=1)
        result = execute_search(state, LEADER_ID, _shoot_request(1, Maneuver.SHOOT), random.Random(0))

    assert mock_resolve.called
    assert result.accepted is True
    assert result.combat_resolved is True
    assert result.winner == "monster"
    assert result.leader_killed is True
    assert LEADER_ID not in state.leaders
    assert LEADER_ID in state.dead_leaders


def test_execute_search_shoot_tactic_exhausted_falls_through_to_melee():
    # Mirrors Regolamento AK.txt [11.3]'s own worked example ("FI, FL.
    # Significato: Tirare con l'Arco, poi fuggire") -- Fire Arrow runs
    # first; when it exhausts its free attacks with nobody dead, the
    # plan's next tactic (here Melee, not Flee) still runs.
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE))
    request = _shoot_request(1, Maneuver.SHOOT, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.resolve_fire_arrow_duel") as mock_shoot, patch(
        "ak_engine.turn.search_execution.resolve_melee_duel"
    ) as mock_melee:
        mock_shoot.return_value = EncounterCombatResult(winner=None, rounds=1)
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert mock_shoot.called
    assert mock_melee.called
    assert result.combat_resolved is True
    assert result.winner == "leader"


def test_execute_search_shoot_then_flee_tries_shoot_first():
    # Same real example as above, but this time Flee genuinely is the
    # plan's second tactic -- confirms Fire Arrow is attempted before
    # Flee, not the other way around (Phase 169's original bug).
    state = _state_with_leader()
    feature = Feature(feature_id=1, coord=LOCATION, kind=FeatureType.CAVE, guardian_monster=Monster.GRYPHON)
    state.add_feature(feature)
    request = _shoot_request(1, Maneuver.SHOOT, Maneuver.FLEE)

    with patch("ak_engine.turn.search_execution.resolve_fire_arrow_duel") as mock_shoot:
        mock_shoot.return_value = EncounterCombatResult(winner=None, rounds=1)
        # Gryphon is Fast (20% flee chance); every padding value is 0.1 so
        # whichever one lands on the flee roll still succeeds.
        result = execute_search(state, LEADER_ID, request, ScriptedRandom([0.1] * 20))

    assert mock_shoot.called
    assert result.combat_resolved is False
    assert result.fled is True


def test_execute_search_unwired_tactic_is_skipped_not_aborting():
    # "ST, CA-FI, ME, SC" ([11.3]) mixes Steal and Cast (both unwired)
    # with Melee -- an unwired tactic must be silently skipped, not treat
    # the whole plan as unresolvable.
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE))
    request = _shoot_request(1, Maneuver.STEAL, Maneuver.CAST, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert mock_melee.called
    assert result.combat_resolved is True
    assert result.winner == "leader"


def test_execute_search_monster_combatant_carries_missile_skill_and_damage():
    # Archer: missile_skill=3, missile_damage=(3, 9) -- both must reach
    # the monster's own Combatant, not the character-default (1-6).
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))

    with patch("ak_engine.turn.search_execution.resolve_fire_arrow_duel") as mock_resolve:
        mock_resolve.return_value = EncounterCombatResult(winner=None, rounds=1)
        execute_search(state, LEADER_ID, _shoot_request(1, Maneuver.SHOOT), random.Random(0))

    monster_combatant = mock_resolve.call_args[0][1]
    stats = MONSTER_COMBAT_STATS[Monster.ARCHER]
    assert monster_combatant.archery_skill == stats.missile_skill == 3
    assert monster_combatant.missile_damage_range == stats.missile_damage == (3, 9)


def test_execute_search_monster_missile_damage_range_defaults_when_unarmed():
    # Gargoyle has missile_skill=0 and missile_damage=None (no ranged
    # attack at all) -- the Combatant must fall back to the character
    # rule rather than crash on an unpacking of None.
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE))

    with patch("ak_engine.turn.search_execution.resolve_fire_arrow_duel") as mock_resolve:
        mock_resolve.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_search(state, LEADER_ID, _shoot_request(1, Maneuver.SHOOT), random.Random(0))

    monster_combatant = mock_resolve.call_args[0][1]
    assert monster_combatant.archery_skill == 0
    assert monster_combatant.missile_damage_range == FIRE_ARROW_DAMAGE_RANGE


# -- Phase 175: carrying the Fire Arrow shot log + guardian species out to the report layer --


def test_execute_search_shoot_tactic_carries_shots_and_guardian_monster_on_win():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE))
    shots = (FireArrowShot(shooter="a", hit=True, damage=4),)

    with patch("ak_engine.turn.search_execution.resolve_fire_arrow_duel") as mock_resolve:
        mock_resolve.return_value = EncounterCombatResult(winner="a", rounds=1, shots=shots)
        result = execute_search(state, LEADER_ID, _shoot_request(1, Maneuver.SHOOT), random.Random(0))

    assert result.fire_arrow_shots == shots
    assert result.guardian_monster is Monster.GARGOYLE


def test_execute_search_shoot_exhausted_then_melee_still_carries_the_earlier_shots():
    # The Fire Arrow phase's own shots must survive onto whichever later
    # tactic actually ends the fight, since a shot fired earlier in the
    # plan is still worth narrating even though it didn't decide the
    # outcome (turn/search_execution.py's own Phase 175 addendum).
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE))
    request = _shoot_request(1, Maneuver.SHOOT, Maneuver.MELEE)
    shots = (FireArrowShot(shooter="a", hit=False, damage=0), FireArrowShot(shooter="b", hit=False, damage=0))

    with patch("ak_engine.turn.search_execution.resolve_fire_arrow_duel") as mock_shoot, patch(
        "ak_engine.turn.search_execution.resolve_melee_duel"
    ) as mock_melee:
        mock_shoot.return_value = EncounterCombatResult(winner=None, rounds=1, shots=shots)
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert result.winner == "leader"
    assert result.fire_arrow_shots == shots
    assert result.guardian_monster is Monster.GARGOYLE


def test_execute_search_melee_only_has_empty_fire_arrow_shots_but_still_sets_guardian():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE))

    with patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        result = execute_search(state, LEADER_ID, _melee_request(1), random.Random(0))

    assert result.fire_arrow_shots == ()
    assert result.guardian_monster is Monster.GARGOYLE


# -- Phase 415: per-swing Melee detail (turn/encounter.py MeleeSwing) --


def test_execute_search_melee_fast_path_surfaces_the_duels_own_melee_swings():
    # The "whole plan is Melee, nothing else pending" fast path calls
    # resolve_melee_duel() once for the entire duel -- its own returned
    # EncounterCombatResult.melee_swings (already aggregated across every
    # round internally, Phase 415) must reach SearchExecutionResult
    # unchanged.
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE))
    swings = (MeleeSwing(attacker="a", hit=True, damage=4), MeleeSwing(attacker="b", hit=False, damage=0))

    with patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1, melee_swings=swings)
        result = execute_search(state, LEADER_ID, _melee_request(1), random.Random(0))

    assert result.melee_swings == swings


def test_execute_search_melee_round_stepping_accumulates_swings_across_rounds():
    # A bare [MELEE] leader plan still round-steps (instead of taking the
    # atomic resolve_melee_duel() fast path) whenever the guardian's own
    # plan has a CAST pending somewhere later (_monster_has_more_casts_
    # pending()). Two guardian MELEE entries before that CAST keep
    # _peek_monster_action() returning None (its own "guardian's next
    # tactic is Melee" convention) for both of the first two rounds, so
    # the ordinary mutual Melee-vs-Melee branch (resolve_one_melee_round())
    # actually fires twice -- each round's own MeleeRoundOutcome.swings
    # must accumulate across both, not just the decisive one.
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE))
    monster_plan = (
        SearchTactic(maneuver=Maneuver.MELEE),
        SearchTactic(maneuver=Maneuver.MELEE),
        SearchTactic(maneuver=Maneuver.CAST, sub_object=Spell.FIREBALL.value),
    )

    with patch("ak_engine.turn.search_execution.roll_monster_encounter_plan", return_value=monster_plan), patch(
        "ak_engine.turn.search_execution.resolve_one_melee_round"
    ) as mock_round:
        mock_round.side_effect = [
            MeleeRoundOutcome(result=None, swings=(MeleeSwing(attacker="a", hit=False, damage=0),)),
            MeleeRoundOutcome(
                result=EncounterCombatResult(winner="a", rounds=2),
                swings=(MeleeSwing(attacker="a", hit=True, damage=3),),
            ),
        ]
        # Phase 686: 2 extra scripted values beyond the original single
        # 0.5 -- the leader's own landed swing now also fires
        # add_experience()'s own triangular draw.
        result = execute_search(state, LEADER_ID, _melee_request(1), ScriptedRandom([0.5, 0.5, 0.5]))

    assert result.melee_swings == (
        MeleeSwing(attacker="a", hit=False, damage=0),
        MeleeSwing(attacker="a", hit=True, damage=3),
    )


def test_execute_search_steal_caught_melee_range_surfaces_melee_swings():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _steal_request(1)
    swings = (MeleeSwing(attacker="b", hit=True, damage=5),)

    with patch("ak_engine.turn.search_execution.roll_monster_encounter_plan", return_value=()), patch(
        "ak_engine.turn.search_execution.resolve_steal_attempt", return_value=False
    ), patch(
        "ak_engine.turn.search_execution.resolve_steal_evasion", return_value=False
    ), patch(
        "ak_engine.turn.search_execution.resolve_melee_duel",
        return_value=EncounterCombatResult(winner="b", rounds=1, melee_swings=swings),
    ) as mock_melee:
        rng = ScriptedRandom([0.5] * 20, choice_indices=[2])  # MELEE_RANGE
        result = execute_search(state, LEADER_ID, request, rng)

    assert mock_melee.called
    assert result.melee_swings == swings


def test_execute_search_shoot_exhausted_with_no_further_tactic_defaults_to_melee():
    # Phase 178: a plan whose tactic list runs out without a winner no
    # longer reports "inconclusive" -- it now defaults to Melee until
    # someone dies, per the user's own confirmed default behavior.
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE))
    shots = (FireArrowShot(shooter="a", hit=False, damage=0),)

    with patch("ak_engine.turn.search_execution.resolve_fire_arrow_duel") as mock_shoot, patch(
        "ak_engine.turn.search_execution.resolve_melee_duel"
    ) as mock_melee:
        mock_shoot.return_value = EncounterCombatResult(winner=None, rounds=1, shots=shots)
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        result = execute_search(state, LEADER_ID, _shoot_request(1, Maneuver.SHOOT), random.Random(0))

    assert mock_melee.called
    assert result.combat_resolved is True
    assert result.winner == "leader"
    assert result.fire_arrow_shots == shots
    assert result.guardian_monster is Monster.GARGOYLE


# -- Phase 178: the guardian's own Special Encounter Plan --


def test_execute_search_monster_wanting_shoot_fires_even_when_the_leaders_plan_never_does():
    # Titan's own rolled plan always opens with Cast+Shoot -- the leader's
    # own plan here is Melee-only, but Fire Arrow must still resolve
    # first because the guardian's own plan wants it. Titan's own CAST
    # tactics are real as of Phase 209 (real MONSTER_MAGIC_ABILITIES skill
    # levels), so the generic cast-success roll is forced to fail here to
    # isolate this test's own Fire-Arrow-ordering concern from the CAST
    # dispatch behavior covered separately in the Phase 209 CAST tests.
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.TITAN))

    with patch("ak_engine.turn.search_execution.resolve_fire_arrow_duel") as mock_shoot, patch(
        "ak_engine.turn.search_execution.resolve_melee_duel"
    ) as mock_melee, patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=False):
        mock_shoot.return_value = EncounterCombatResult(winner=None, rounds=1)
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        result = execute_search(state, LEADER_ID, _melee_request(1), random.Random(0))

    assert mock_shoot.called
    assert mock_melee.called
    assert result.winner == "leader"


def test_execute_search_monster_not_wanting_shoot_never_triggers_fire_arrow():
    # Gargoyle's own plan is "ME fino alla fine" only -- no Fire Arrow
    # phase should happen even though the guardian's own plan is rolled.
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE))

    with patch("ak_engine.turn.search_execution.resolve_fire_arrow_duel") as mock_shoot, patch(
        "ak_engine.turn.search_execution.resolve_melee_duel"
    ) as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_search(state, LEADER_ID, _melee_request(1), random.Random(0))

    assert not mock_shoot.called
    assert mock_melee.called


def test_execute_search_monster_wanting_shoot_does_not_double_resolve_when_leader_plan_also_shoots():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.TITAN))
    request = _shoot_request(1, Maneuver.SHOOT, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.resolve_fire_arrow_duel") as mock_shoot, patch(
        "ak_engine.turn.search_execution.resolve_melee_duel"
    ) as mock_melee, patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=False):
        mock_shoot.return_value = EncounterCombatResult(winner=None, rounds=1)
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_search(state, LEADER_ID, request, random.Random(0))

    assert mock_shoot.call_count == 1
    assert mock_melee.call_count == 1


def test_execute_search_rolls_the_guardians_plan_with_the_leaders_own_undead_alignment():
    state = GameState()
    state.add_leader(LeaderState(LEADER_ID, 1, "Searcher", LOCATION, alignment=Alignment.UNDEAD))
    state.add_feature(
        Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.NEC_MAGE)
    )

    with patch("ak_engine.turn.search_execution.roll_monster_encounter_plan") as mock_roll, patch(
        "ak_engine.turn.search_execution.resolve_melee_duel"
    ) as mock_melee:
        mock_roll.return_value = (SearchTactic(maneuver=Maneuver.MELEE),)
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_search(state, LEADER_ID, _melee_request(1), random.Random(0))

    mock_roll.assert_called_once()
    assert mock_roll.call_args.kwargs["attacker_is_undead"] is True


def test_execute_search_non_undead_leader_rolls_the_guardians_plan_without_the_undead_override():
    state = _state_with_leader()  # LeaderState default alignment is None
    state.add_feature(
        Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.NEC_MAGE)
    )

    with patch("ak_engine.turn.search_execution.roll_monster_encounter_plan") as mock_roll, patch(
        "ak_engine.turn.search_execution.resolve_melee_duel"
    ) as mock_melee:
        mock_roll.return_value = (SearchTactic(maneuver=Maneuver.MELEE),)
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_search(state, LEADER_ID, _melee_request(1), random.Random(0))

    assert mock_roll.call_args.kwargs["attacker_is_undead"] is False


# -- Phase 209: CAST orchestration engine (8 non-channeled Personal-Combat spells + Charm) --


def _cast_request(feature_id: int, spell: Spell, *following: Maneuver) -> SearchRequest:
    tactics = [SearchTactic(maneuver=Maneuver.CAST, sub_object=spell.value)]
    tactics += [SearchTactic(maneuver=m) for m in following]
    return SearchRequest(feature_id=feature_id, unconfirmed_extra0=0, tactics=tactics)


def _skilled_leader(ability: Ability, level: int, **kwargs) -> LeaderState:
    raw = [0] * 30
    raw[ability.value * 2] = level
    raw[ability.value * 2 + 1] = level
    return LeaderState(LEADER_ID, 1, "Searcher", LOCATION, skills=SkillTable(raw_values=raw), **kwargs)


def test_execute_search_cast_charm_success_makes_the_caster_flee():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE))
    request = _cast_request(1, Spell.CHARM, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.resolve_melee_duel"
    ) as mock_melee:
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert result.fled is True
    assert result.combat_resolved is False
    assert not mock_melee.called


def test_execute_search_cast_charm_failure_falls_through_to_melee():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE))
    request = _cast_request(1, Spell.CHARM, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=False), patch(
        "ak_engine.turn.search_execution.resolve_melee_duel"
    ) as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert mock_melee.called
    assert result.winner == "leader"


def test_execute_search_cast_charm_undead_caster_uses_necromancy_skill_level():
    # Charm's own Phase 183 addendum: an Undead caster's Charm draws on
    # Necromancy instead of Psychic -- replicated for monster casters via
    # species classification, for leader casters via `LeaderState.alignment`.
    leader = _skilled_leader(Ability.NECROMANCY, 5, alignment=Alignment.UNDEAD)
    state = GameState()
    state.add_leader(leader)
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE))
    request = _cast_request(1, Spell.CHARM, Maneuver.MELEE)

    with patch(
        "ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=False
    ) as mock_cast_roll, patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_search(state, LEADER_ID, request, random.Random(0))

    mock_cast_roll.assert_called_once()
    assert mock_cast_roll.call_args[0][0] == 5  # the Necromancy level, not the (0) Psychic level


def test_execute_search_cast_holy_symbol_reduces_casters_own_hit_chance_taken():
    leader = _skilled_leader(Ability.WHITE, 2)
    state = GameState()
    state.add_leader(leader)
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _cast_request(1, Spell.HOLY_SYMBOL, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.resolve_melee_duel"
    ) as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_search(state, LEADER_ID, request, random.Random(0))

    leader_combatant = mock_melee.call_args[0][0]
    assert leader_combatant.defensive_hit_multiplier < 1.0


def test_execute_search_cast_holy_symbol_bonus_damage_kills_undead_target_instantly():
    leader = _skilled_leader(Ability.WHITE, 2)
    state = GameState()
    state.add_leader(leader)
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.VAMPIRE))
    request = _cast_request(1, Spell.HOLY_SYMBOL, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.roll_holy_symbol_undead_damage", return_value=999
    ), patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_melee:
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert result.combat_resolved is True
    assert result.winner == "leader"
    assert result.feature_looted is True
    assert not mock_melee.called


def test_execute_search_cast_holy_symbol_enhanced_grants_bonus_damage_against_evil_monster():
    # Phase 497: AdvancedAbility.ENHANCED_HOLY_SYMBOL -- "the Holy Symbol
    # spell now has the same effect against opponents who have an Evil
    # alignment as it does against Undead creatures." Monster.ARCHER
    # rolls 100% Alignment.EVIL (single-option distribution, so
    # roll_monster_alignment() itself consumes no RNG here).
    leader = _skilled_leader(Ability.WHITE, 2)
    leader.advanced_abilities.add(AdvancedAbility.ENHANCED_HOLY_SYMBOL)
    state = GameState()
    state.add_leader(leader)
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _cast_request(1, Spell.HOLY_SYMBOL, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.roll_holy_symbol_undead_damage", return_value=999
    ), patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_melee:
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert result.combat_resolved is True
    assert result.winner == "leader"
    assert result.feature_looted is True
    assert not mock_melee.called


def test_execute_search_cast_holy_symbol_without_enhancement_no_bonus_against_evil_monster():
    leader = _skilled_leader(Ability.WHITE, 2)
    state = GameState()
    state.add_leader(leader)
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _cast_request(1, Spell.HOLY_SYMBOL, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.roll_holy_symbol_undead_damage", return_value=999
    ) as mock_damage, patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_search(state, LEADER_ID, request, random.Random(0))

    assert not mock_damage.called
    assert mock_melee.called


def test_execute_search_cast_spiritwrack_debuffs_the_target():
    leader = _skilled_leader(Ability.WHITE, 2)  # exact reduction of 1, no rng consumed
    state = GameState()
    state.add_leader(leader)
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _cast_request(1, Spell.SPIRITWRACK, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.resolve_melee_duel"
    ) as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_search(state, LEADER_ID, request, random.Random(0))

    monster_combatant = mock_melee.call_args[0][1]
    assert monster_combatant.melee_damage_dealt_reduction == 1
    assert monster_combatant.blocked_from_cast_and_archery is True


def test_execute_search_cast_psychic_blast_bonus_swing_can_end_the_encounter():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _cast_request(1, Spell.PSYCHIC_BLAST)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.roll_psychic_blast_stun_rounds", return_value=2
    ), patch("ak_engine.turn.search_execution.roll_melee_attack", return_value=999), patch(
        "ak_engine.turn.search_execution.resolve_melee_duel"
    ) as mock_melee, patch("ak_engine.turn.search_execution.resolve_fire_arrow_duel") as mock_shoot:
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert result.combat_resolved is True
    assert result.winner == "leader"
    assert result.feature_looted is True
    assert not mock_melee.called
    assert not mock_shoot.called


def test_execute_search_cast_telekinetic_storm_kills_the_target():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _cast_request(1, Spell.TELEK_STORM)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.roll_telekinetic_storm_victim_damage", return_value=999
    ), patch("ak_engine.turn.search_execution.roll_telekinetic_storm_caster_damage", return_value=0):
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert result.winner == "leader"
    assert result.feature_looted is True


def test_execute_search_cast_telekinetic_storm_can_kill_the_caster():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _cast_request(1, Spell.TELEK_STORM)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.roll_telekinetic_storm_victim_damage", return_value=0
    ), patch("ak_engine.turn.search_execution.roll_telekinetic_storm_caster_damage", return_value=999):
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert result.winner == "monster"
    assert result.leader_killed is True


def test_execute_search_cast_invisibility_halves_casters_own_hit_chance_taken():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _cast_request(1, Spell.INVISIBILITY, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.resolve_melee_duel"
    ) as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_search(state, LEADER_ID, request, random.Random(0))

    leader_combatant = mock_melee.call_args[0][0]
    assert leader_combatant.defensive_hit_multiplier == 0.5


def test_execute_search_cast_invisibility_leader_opponent_with_witchsight_is_unaffected():
    # Phase 496: AdvancedAbility.WITCHSIGHT_TALENT -- "the Necromancer can
    # still see his opponent and is unaffected by the spell" -- here the
    # monster casts Invisibility on itself and the leader is the one who
    # needs to keep fighting it; Witchsight should suppress the halving.
    leader = _skilled_leader(Ability.NECROMANCY, 0)
    leader.advanced_abilities.add(AdvancedAbility.WITCHSIGHT_TALENT)
    state = GameState()
    state.add_leader(leader)
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _melee_request(1)

    with patch("ak_engine.turn.search_execution.roll_monster_encounter_plan") as mock_roll, patch.dict(
        "ak_engine.turn.search_execution.MONSTER_MAGIC_ABILITIES", {Monster.ARCHER: {Ability.ILLUSION: 5}}
    ), patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.resolve_melee_duel"
    ) as mock_melee:
        mock_roll.return_value = (SearchTactic(maneuver=Maneuver.CAST, sub_object=Spell.INVISIBILITY.value),)
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_search(state, LEADER_ID, request, random.Random(0))

    # resolve_melee_duel() is always called (leader_combatant,
    # monster_combatant, ...) regardless of who cast/who's the target.
    monster_combatant = mock_melee.call_args[0][1]
    assert monster_combatant.defensive_hit_multiplier == 1.0


def test_execute_search_cast_invisibility_leader_opponent_without_witchsight_is_halved():
    leader = _skilled_leader(Ability.NECROMANCY, 0)
    state = GameState()
    state.add_leader(leader)
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _melee_request(1)

    with patch("ak_engine.turn.search_execution.roll_monster_encounter_plan") as mock_roll, patch.dict(
        "ak_engine.turn.search_execution.MONSTER_MAGIC_ABILITIES", {Monster.ARCHER: {Ability.ILLUSION: 5}}
    ), patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.resolve_melee_duel"
    ) as mock_melee:
        mock_roll.return_value = (SearchTactic(maneuver=Maneuver.CAST, sub_object=Spell.INVISIBILITY.value),)
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_search(state, LEADER_ID, request, random.Random(0))

    monster_combatant = mock_melee.call_args[0][1]
    assert monster_combatant.defensive_hit_multiplier == 0.5


def test_execute_search_cast_invisibility_leader_caster_still_halved_regardless_of_witchsight():
    # The leader casting Invisibility on themselves is the one who
    # becomes invisible -- their own Witchsight (if any) is irrelevant to
    # their own defensive_hit_multiplier, matching the base (pre-Phase
    # 496) test above; a monster opponent can never hold an Advanced
    # Ability, so the halving always applies here regardless.
    leader = _skilled_leader(Ability.ILLUSION, 5)
    leader.advanced_abilities.add(AdvancedAbility.WITCHSIGHT_TALENT)
    state = GameState()
    state.add_leader(leader)
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _cast_request(1, Spell.INVISIBILITY, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.resolve_melee_duel"
    ) as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_search(state, LEADER_ID, request, random.Random(0))

    leader_combatant = mock_melee.call_args[0][0]
    assert leader_combatant.defensive_hit_multiplier == 0.5


def test_execute_search_cast_invisibility_leader_opponent_holding_crystal_of_true_seeing_is_unaffected():
    # Phase 532: AKGEN_reverse_engineering_report (4).md SS8 point 3 --
    # same shape as the Witchsight carve-out above, but via item
    # possession (AMULET_ANTI_ILLUSION) rather than an Advanced Ability.
    # A monster casts Invisibility on itself; the leader is the opponent
    # who needs to keep fighting it.
    leader = _skilled_leader(Ability.NECROMANCY, 0)
    state = GameState()
    state.add_leader(leader)
    state.add_item(Treasure.AMULET_ANTI_ILLUSION, owner_leader_id=LEADER_ID)
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _melee_request(1)

    with patch("ak_engine.turn.search_execution.roll_monster_encounter_plan") as mock_roll, patch.dict(
        "ak_engine.turn.search_execution.MONSTER_MAGIC_ABILITIES", {Monster.ARCHER: {Ability.ILLUSION: 5}}
    ), patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.resolve_melee_duel"
    ) as mock_melee:
        mock_roll.return_value = (SearchTactic(maneuver=Maneuver.CAST, sub_object=Spell.INVISIBILITY.value),)
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_search(state, LEADER_ID, request, random.Random(0))

    monster_combatant = mock_melee.call_args[0][1]
    assert monster_combatant.defensive_hit_multiplier == 1.0


def test_execute_search_cast_fireball_kills_the_target():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _cast_request(1, Spell.FIREBALL)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.roll_fireball_damage", return_value=999
    ):
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert result.winner == "leader"


def test_execute_search_cast_fireball_marks_submarine_targets_immune():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.MERMAID))
    request = _cast_request(1, Spell.FIREBALL, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.roll_fireball_damage", return_value=0
    ) as mock_fireball, patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_search(state, LEADER_ID, request, random.Random(0))

    assert mock_fireball.call_args.kwargs["target_is_immune"] is True


def test_execute_search_cast_fireball_enhanced_ability_overrides_submarine_immunity():
    # Phase 501: AdvancedAbility.ENHANCED_COMBAT_EL_SPELLS -- "Fireball
    # can be cast against underwater monsters."
    state = _state_with_leader()
    state.leaders[LEADER_ID].advanced_abilities.add(AdvancedAbility.ENHANCED_COMBAT_EL_SPELLS)
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.MERMAID))
    request = _cast_request(1, Spell.FIREBALL)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.roll_fireball_damage", return_value=999
    ) as mock_fireball:
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert mock_fireball.call_args.kwargs["target_is_immune"] is False
    assert result.winner == "leader"


def test_execute_search_monster_cast_fireball_blocked_by_leaders_anti_elemental_amulet():
    # Phase 531: AKGEN_reverse_engineering_report (4).md SS8 -- when the
    # *monster* is the caster, the searching leader is the target; this
    # proves the immunity check also applies on that side of the
    # dispatcher, not just leader-casts-at-monster.
    state = _state_with_leader()
    state.add_item(Treasure.AMULET_ANTI_ELEMENTAL, owner_leader_id=LEADER_ID)
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))

    with patch("ak_engine.turn.search_execution.roll_monster_encounter_plan") as mock_roll, patch(
        "ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True
    ), patch("ak_engine.turn.search_execution.roll_fireball_damage") as mock_damage, patch(
        "ak_engine.turn.search_execution.resolve_melee_duel"
    ) as mock_melee:
        mock_roll.return_value = (
            SearchTactic(maneuver=Maneuver.CAST, sub_object=Spell.FIREBALL.value),
            SearchTactic(maneuver=Maneuver.MELEE),
        )
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_search(state, LEADER_ID, _melee_request(1), random.Random(0))

    assert not mock_damage.called  # negated -- damage roll never even attempted
    assert mock_melee.called  # falls through to Melee since the cast had no effect


def test_execute_search_monster_cast_fireball_resisted_by_leaders_necro_mage_title():
    # Phase 666: Office.NECRO_MAGE's own Imp familiar -- "25% magic
    # resistance." Same dispatcher side as the amulet test above (the
    # monster is the caster, the leader is the target), no amulet
    # involved this time.
    state = _state_with_leader()
    state.add_kingdom(KingdomState(1, "Searchia", Race.HUMAN, Alignment.GOOD, LOCATION))
    state.leaders[LEADER_ID].merit_tally.necromancy_spell_casts = 20  # meets OFFICE_MIN_POINTS[Office.NECRO_MAGE]
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))

    with patch("ak_engine.turn.search_execution.roll_monster_encounter_plan") as mock_roll, patch(
        "ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True
    ), patch("ak_engine.turn.search_execution.roll_fireball_damage") as mock_damage, patch(
        "ak_engine.turn.search_execution.resolve_melee_duel"
    ) as mock_melee:
        mock_roll.return_value = (
            SearchTactic(maneuver=Maneuver.CAST, sub_object=Spell.FIREBALL.value),
            SearchTactic(maneuver=Maneuver.MELEE),
        )
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        # Padding: the monster's own hit-points draw runs before the tactic
        # walk starts, consuming an unknown number of randoms from the
        # front of the queue -- every value here is 0.1 (well under the
        # 25% resistance chance), so whichever one lands on that roll
        # still resists.
        execute_search(state, LEADER_ID, _melee_request(1), ScriptedRandom([0.1] * 20))

    assert not mock_damage.called  # resisted -- damage roll never even attempted
    assert mock_melee.called  # falls through to Melee since the cast had no effect


def test_execute_search_cast_ice_suspend_immune_species_has_no_effect():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.SPECTRE))
    request = _cast_request(1, Spell.ICE_SUSPEND, Maneuver.MELEE)

    # SPECTRE's own real rolled plan may include real CAST tactics of its
    # own (Phase 210 wired Hand of Death/Mirror-Image); mocked empty here
    # to isolate this test's own "Ice Suspend has no effect" concern from
    # the guardian's own CAST dispatch, covered separately.
    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.roll_monster_encounter_plan", return_value=()
    ), patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_search(state, LEADER_ID, request, random.Random(0))

    assert mock_melee.called
    leader_combatant = mock_melee.call_args[0][0]
    assert leader_combatant.bonus_unanswered_attacks == 0


def test_execute_search_cast_ice_suspend_enhanced_ability_overrides_species_immunity():
    # Phase 501: AdvancedAbility.ENHANCED_COMBAT_EL_SPELLS -- "Ice
    # Suspension will work against any monster." SPECTRE would
    # otherwise be immune (see the test above, where the guardian never
    # takes any bonus-attack damage); with the ability, the spell's
    # ordinary slowed-branch bonus rounds apply instead and can kill it.
    state = _state_with_leader()
    state.leaders[LEADER_ID].advanced_abilities.add(AdvancedAbility.ENHANCED_COMBAT_EL_SPELLS)
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.SPECTRE))
    request = _cast_request(1, Spell.ICE_SUSPEND)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.roll_monster_encounter_plan", return_value=()
    ), patch("ak_engine.turn.search_execution.ice_suspension_is_frozen", return_value=False), patch(
        "ak_engine.turn.search_execution.ice_suspension_slowed_bonus_rounds", return_value=1
    ), patch("ak_engine.turn.search_execution.roll_melee_attack", return_value=999):
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert result.winner == "leader"


def test_execute_search_cast_ice_suspend_frozen_branch_wins_instantly():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _cast_request(1, Spell.ICE_SUSPEND)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.ice_suspension_is_frozen", return_value=True
    ):
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert result.winner == "leader"


def test_execute_search_cast_ice_suspend_flying_branch_crash_damage_can_kill():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.VAMPIRE))
    request = _cast_request(1, Spell.ICE_SUSPEND)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.ice_suspension_is_frozen", return_value=False
    ), patch("ak_engine.turn.search_execution.roll_ice_suspension_flying_crash_damage", return_value=999), patch(
        "ak_engine.turn.search_execution.roll_ice_suspension_flying_bonus_rounds", return_value=0
    ):
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert result.winner == "leader"


def test_execute_search_cast_ice_suspend_slowed_branch_grants_bonus_attacks():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _cast_request(1, Spell.ICE_SUSPEND)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.ice_suspension_is_frozen", return_value=False
    ), patch("ak_engine.turn.search_execution.ice_suspension_slowed_bonus_rounds", return_value=2), patch(
        "ak_engine.turn.search_execution.roll_melee_attack", return_value=999
    ):
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert result.winner == "leader"


def test_execute_search_cast_control_undead_ineligible_target_consumes_no_roll():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _cast_request(1, Spell.CONTROL_UNDEAD, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast") as mock_roll, patch(
        "ak_engine.turn.search_execution.resolve_melee_duel"
    ) as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_search(state, LEADER_ID, request, random.Random(0))

    assert not mock_roll.called
    assert mock_melee.called


def test_execute_search_cast_control_undead_success_wins_instantly():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.VAMPIRE))
    request = _cast_request(1, Spell.CONTROL_UNDEAD)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True):
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert result.winner == "leader"
    assert result.feature_looted is True


def test_execute_search_cast_control_undead_failure_applies_rage_buff():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.VAMPIRE))
    request = _cast_request(1, Spell.CONTROL_UNDEAD, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=False), patch(
        "ak_engine.turn.search_execution.control_undead_failure_new_hit_points", return_value=999
    ), patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_search(state, LEADER_ID, request, random.Random(0))

    monster_combatant = mock_melee.call_args[0][1]
    assert monster_combatant.hit_points == 999


def test_execute_search_cast_control_undead_without_ability_anti_holy_target_stays_ineligible():
    # Phase 502: AdvancedAbility.ENHANCED_COMBAT_NE_SPELLS -- IMP is
    # anti-holy (HAND_OF_DEATH_ANTI_HOLY_MONSTERS) but not Undead, so
    # without the ability it's still an ineligible Control Undead target.
    # IMP's own real rolled plan may include a real CAST tactic of its
    # own (it knows Illusion 2); mocked empty here to isolate this
    # test's own eligibility concern, same as the SPECTRE test above.
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.IMP))
    request = _cast_request(1, Spell.CONTROL_UNDEAD, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast") as mock_roll, patch(
        "ak_engine.turn.search_execution.roll_monster_encounter_plan", return_value=()
    ), patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_search(state, LEADER_ID, request, random.Random(0))

    assert not mock_roll.called
    assert mock_melee.called


def test_execute_search_cast_control_undead_enhanced_ability_makes_anti_holy_target_eligible():
    # Phase 502: with the ability, IMP becomes an eligible target and a
    # successful cast (with the resist roll forced to never trigger)
    # neutralizes it just like an ordinary Undead target.
    state = _state_with_leader()
    state.leaders[LEADER_ID].advanced_abilities.add(AdvancedAbility.ENHANCED_COMBAT_NE_SPELLS)
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.IMP))
    request = _cast_request(1, Spell.CONTROL_UNDEAD)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.control_undead_anti_holy_resist_chance", return_value=0.0
    ):
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert result.winner == "leader"
    assert result.feature_looted is True


def test_execute_search_cast_control_undead_anti_holy_resist_roll_blocks_neutralization():
    # Phase 502: "there is a percentage chance that they will resist the
    # spell" -- forcing the resist chance to certainty makes an otherwise
    # successful cast fall through to ordinary Melee instead of winning.
    state = _state_with_leader()
    state.leaders[LEADER_ID].advanced_abilities.add(AdvancedAbility.ENHANCED_COMBAT_NE_SPELLS)
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.IMP))
    request = _cast_request(1, Spell.CONTROL_UNDEAD, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.control_undead_anti_holy_resist_chance", return_value=1.0
    ), patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_search(state, LEADER_ID, request, random.Random(0))

    assert mock_melee.called


def test_execute_search_guardians_own_cast_resolves_before_the_first_real_combat_phase():
    # The guardian's own CAST tactics are injected right before the first
    # real combat phase (same point already established for
    # monster_wants_shoot, Phase 178), independent of the leader's own
    # plan -- here the leader's plan never casts anything at all.
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ELE_MAGE))
    request = _melee_request(1)

    with patch("ak_engine.turn.search_execution.roll_monster_encounter_plan") as mock_roll, patch(
        "ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True
    ), patch("ak_engine.turn.search_execution.roll_fireball_damage", return_value=999), patch(
        "ak_engine.turn.search_execution.resolve_melee_duel"
    ) as mock_melee:
        mock_roll.return_value = (SearchTactic(maneuver=Maneuver.CAST, sub_object=Spell.FIREBALL.value),)
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert result.winner == "monster"
    assert result.leader_killed is True
    assert not mock_melee.called


def test_execute_search_blocked_from_cast_and_archery_skips_the_guardians_own_later_cast():
    # The leader's own Spiritwrack lands on the guardian first (leader-CAST
    # resolves when the walk reaches it, before any guardian-CAST
    # injection); once the guardian is blocked, its own later Fireball
    # tactic (from its own rolled plan) is skipped outright, never
    # reaching the generic cast-success roll.
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _cast_request(1, Spell.SPIRITWRACK, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.roll_monster_encounter_plan") as mock_roll, patch(
        "ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True
    ) as mock_cast_roll, patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_melee:
        mock_roll.return_value = (SearchTactic(maneuver=Maneuver.CAST, sub_object=Spell.FIREBALL.value),)
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_search(state, LEADER_ID, request, random.Random(0))

    assert mock_cast_roll.call_count == 1
    assert mock_melee.called


# -- Phase 210: Hand of Death + Mirror-Image Phantasm CAST dispatch --


def test_execute_search_cast_hand_of_death_threads_the_immune_flag():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.VAMPIRE))
    request = _cast_request(1, Spell.HAND_OF_DEATH, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.resolve_hand_of_death_channel"
    ) as mock_channel, patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_melee:
        mock_channel.return_value = EncounterCombatResult(winner=None, rounds=0)
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_search(state, LEADER_ID, request, random.Random(0))

    # Vampire is Undead (SPIRITWRACK_UNDEAD_MONSTERS), part of
    # HAND_OF_DEATH_IMMUNE_MONSTERS.
    assert mock_channel.call_args.kwargs["target_is_immune"] is True


def test_execute_search_cast_hand_of_death_enhanced_ability_overrides_the_immune_flag():
    # Phase 500: AdvancedAbility.ENHANCED_COMBAT_NE_SPELLS -- "'Hand of
    # Death' now works against all creatures." Vampire would otherwise
    # be immune (see the test above); the ability overrides that.
    state = _state_with_leader()
    state.leaders[LEADER_ID].advanced_abilities.add(AdvancedAbility.ENHANCED_COMBAT_NE_SPELLS)
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.VAMPIRE))
    request = _cast_request(1, Spell.HAND_OF_DEATH, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.resolve_hand_of_death_channel"
    ) as mock_channel, patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_melee:
        mock_channel.return_value = EncounterCombatResult(winner=None, rounds=0)
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_search(state, LEADER_ID, request, random.Random(0))

    assert mock_channel.call_args.kwargs["target_is_immune"] is False


def test_execute_search_cast_hand_of_death_caster_wins_instantly():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _cast_request(1, Spell.HAND_OF_DEATH)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.resolve_hand_of_death_channel"
    ) as mock_channel:
        mock_channel.return_value = EncounterCombatResult(winner="a", rounds=3, squeeze_hits=(2, 2, 3))
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert mock_channel.call_args.kwargs["target_is_immune"] is False
    assert result.winner == "leader"
    assert result.feature_looted is True
    # Phase 413: the winning channel's own per-round damage log, threaded
    # through for report/turn_report.py render_squeeze_attack().
    assert result.squeeze_hits == (2, 2, 3)


def test_execute_search_cast_hand_of_death_broken_channel_falls_through_to_melee():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _cast_request(1, Spell.HAND_OF_DEATH, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.resolve_hand_of_death_channel"
    ) as mock_channel, patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_melee:
        mock_channel.return_value = EncounterCombatResult(winner=None, rounds=2)
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert mock_melee.called
    assert result.winner == "leader"


def test_execute_search_cast_hand_of_death_rolls_the_necromancy_skill_level():
    leader = _skilled_leader(Ability.NECROMANCY, 4)
    state = GameState()
    state.add_leader(leader)
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _cast_request(1, Spell.HAND_OF_DEATH)

    with patch(
        "ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True
    ) as mock_cast_roll, patch("ak_engine.turn.search_execution.resolve_hand_of_death_channel") as mock_channel:
        mock_channel.return_value = EncounterCombatResult(winner=None, rounds=1)
        execute_search(state, LEADER_ID, request, random.Random(0))

    assert mock_cast_roll.call_args[0][0] == 4


def test_execute_search_cast_mirror_image_monster_target_uses_the_sourced_tier():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.SPHINX))
    request = _cast_request(1, Spell.MIRROR_IMAGE, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.resolve_mirror_image_duel"
    ) as mock_duel, patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_melee:
        mock_duel.return_value = EncounterCombatResult(winner=None, rounds=1)
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_search(state, LEADER_ID, request, random.Random(0))

    from ak_engine.turn.encounter import MirrorImageIntelligenceTier

    assert mock_duel.call_args[0][2] is MirrorImageIntelligenceTier.HIGH_HUMAN


def test_execute_search_cast_mirror_image_leader_target_uses_medium_human_plus_the_sage_illusion_bonus():
    # The guardian's own rolled plan casts Mirror-Image at the leader --
    # opponent_tier is always Medium Human for a King/Hero (Phase 470,
    # AKGEN_reverse_engineering_report (2).md SS21.4), plus a further
    # bonus from the leader's own Sage/Illusion skill levels.
    leader = _skilled_leader(Ability.SAGE, 3)  # 3*2% = 6% bonus, 0% Illusion
    state = GameState()
    state.add_leader(leader)
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _melee_request(1)

    with patch("ak_engine.turn.search_execution.roll_monster_encounter_plan") as mock_roll, patch(
        "ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True
    ), patch("ak_engine.turn.search_execution.resolve_mirror_image_duel") as mock_duel, patch(
        "ak_engine.turn.search_execution.resolve_melee_duel"
    ) as mock_melee:
        mock_roll.return_value = (SearchTactic(maneuver=Maneuver.CAST, sub_object=Spell.MIRROR_IMAGE.value),)
        mock_duel.return_value = EncounterCombatResult(winner=None, rounds=1)
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_search(state, LEADER_ID, request, random.Random(0))

    from ak_engine.turn.encounter import MirrorImageIntelligenceTier

    assert mock_duel.call_args[0][2] is MirrorImageIntelligenceTier.MEDIUM_HUMAN
    assert mock_duel.call_args.kwargs["opponent_disbelief_bonus"] == pytest.approx(0.06)


def test_execute_search_cast_mirror_image_leader_caster_passes_own_detect_illusions_as_caster_bonus():
    # Phase 494: leader is the caster (Stage 2 disbeliever) -- Detect
    # Illusions belongs to caster_has_detect_illusions here, never
    # opponent_has_detect_illusions (the monster can't hold an Advanced Ability).
    state = _state_with_leader()
    state.leaders[LEADER_ID].advanced_abilities.add(AdvancedAbility.DETECT_ILLUSIONS_TALENT)
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _cast_request(1, Spell.MIRROR_IMAGE)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.resolve_mirror_image_duel"
    ) as mock_duel:
        mock_duel.return_value = EncounterCombatResult(winner=None, rounds=1)
        execute_search(state, LEADER_ID, request, random.Random(0))

    assert mock_duel.call_args.kwargs["caster_has_detect_illusions"] is True
    assert mock_duel.call_args.kwargs["opponent_has_detect_illusions"] is False


def test_execute_search_cast_mirror_image_leader_caster_without_the_talent_passes_false():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _cast_request(1, Spell.MIRROR_IMAGE)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.resolve_mirror_image_duel"
    ) as mock_duel:
        mock_duel.return_value = EncounterCombatResult(winner=None, rounds=1)
        execute_search(state, LEADER_ID, request, random.Random(0))

    assert mock_duel.call_args.kwargs["caster_has_detect_illusions"] is False
    assert mock_duel.call_args.kwargs["opponent_has_detect_illusions"] is False


def test_execute_search_cast_mirror_image_leader_target_passes_own_detect_illusions_as_opponent_bonus():
    # Phase 494: leader is the opponent/target here (a monster's own plan
    # casts Mirror-Image at the leader) -- Detect Illusions belongs to
    # opponent_has_detect_illusions, never caster_has_detect_illusions
    # (the monster caster can't hold an Advanced Ability).
    leader = _skilled_leader(Ability.SAGE, 0)
    leader.advanced_abilities.add(AdvancedAbility.DETECT_ILLUSIONS_TALENT)
    state = GameState()
    state.add_leader(leader)
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _melee_request(1)

    with patch("ak_engine.turn.search_execution.roll_monster_encounter_plan") as mock_roll, patch(
        "ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True
    ), patch("ak_engine.turn.search_execution.resolve_mirror_image_duel") as mock_duel, patch(
        "ak_engine.turn.search_execution.resolve_melee_duel"
    ) as mock_melee:
        mock_roll.return_value = (SearchTactic(maneuver=Maneuver.CAST, sub_object=Spell.MIRROR_IMAGE.value),)
        mock_duel.return_value = EncounterCombatResult(winner=None, rounds=1)
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_search(state, LEADER_ID, request, random.Random(0))

    assert mock_duel.call_args.kwargs["opponent_has_detect_illusions"] is True
    assert mock_duel.call_args.kwargs["caster_has_detect_illusions"] is False


def test_execute_search_cast_mirror_image_caster_wins_instantly():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _cast_request(1, Spell.MIRROR_IMAGE)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.resolve_mirror_image_duel"
    ) as mock_duel:
        mock_duel.return_value = EncounterCombatResult(winner="a", rounds=2)
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert result.winner == "leader"
    assert result.feature_looted is True


def test_execute_search_cast_mirror_image_caster_is_slain_by_own_illusion():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _cast_request(1, Spell.MIRROR_IMAGE)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.resolve_mirror_image_duel"
    ) as mock_duel:
        mock_duel.return_value = EncounterCombatResult(winner="b", rounds=2)
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert result.winner == "monster"
    assert result.leader_killed is True


def test_execute_search_cast_illusory_hero_no_valhalla_visitor_has_no_effect():
    leader = _skilled_leader(Ability.ILLUSION, 5)
    state = GameState()
    state.add_leader(leader)
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _cast_request(1, Spell.ILLUS_HERO, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.resolve_illusory_hero_duel"
    ) as mock_duel, patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_search(state, LEADER_ID, request, random.Random(0))

    assert not mock_duel.called
    assert mock_melee.called


def test_execute_search_cast_illusory_hero_level_gate_blocks_low_illusion_skill():
    leader = _skilled_leader(Ability.ILLUSION, 4)
    state = GameState()
    state.add_leader(leader)
    state.add_leader(LeaderState(VALHALLA_VISITOR_LEADER_ID, None, "Hero", LOCATION))
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _cast_request(1, Spell.ILLUS_HERO, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast") as mock_cast_roll, patch(
        "ak_engine.turn.search_execution.resolve_melee_duel"
    ) as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_search(state, LEADER_ID, request, random.Random(0))

    assert not mock_cast_roll.called
    assert mock_melee.called


def test_execute_search_cast_illusory_hero_monster_target_uses_the_sourced_tier():
    leader = _skilled_leader(Ability.ILLUSION, 5)
    state = GameState()
    state.add_leader(leader)
    state.add_leader(LeaderState(VALHALLA_VISITOR_LEADER_ID, None, "Hero", LOCATION))
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.SPHINX))
    request = _cast_request(1, Spell.ILLUS_HERO, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.resolve_illusory_hero_duel"
    ) as mock_duel, patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_melee:
        mock_duel.return_value = EncounterCombatResult(winner=None, rounds=1)
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_search(state, LEADER_ID, request, random.Random(0))

    from ak_engine.turn.encounter import MirrorImageIntelligenceTier

    assert mock_duel.call_args[0][2].melee_skill == 0  # the hero-illusion Combatant
    assert mock_duel.call_args[0][3] is MirrorImageIntelligenceTier.HIGH_HUMAN
    assert mock_duel.call_args.kwargs["opponent_disbelief_bonus"] == 0.0


def test_execute_search_cast_illusory_hero_leader_target_uses_medium_human_plus_bonus():
    leader = _skilled_leader(Ability.SAGE, 3)  # 3*2% = 6% bonus, 0% Illusion
    state = GameState()
    state.add_leader(leader)
    state.add_leader(LeaderState(VALHALLA_VISITOR_LEADER_ID, None, "Hero", LOCATION))
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _melee_request(1)

    with patch("ak_engine.turn.search_execution.roll_monster_encounter_plan") as mock_roll, patch.dict(
        "ak_engine.turn.search_execution.MONSTER_MAGIC_ABILITIES", {Monster.ARCHER: {Ability.ILLUSION: 5}}
    ), patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.resolve_illusory_hero_duel"
    ) as mock_duel, patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_melee:
        mock_roll.return_value = (SearchTactic(maneuver=Maneuver.CAST, sub_object=Spell.ILLUS_HERO.value),)
        mock_duel.return_value = EncounterCombatResult(winner=None, rounds=1)
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_search(state, LEADER_ID, request, random.Random(0))

    from ak_engine.turn.encounter import MirrorImageIntelligenceTier

    assert mock_duel.call_args[0][3] is MirrorImageIntelligenceTier.MEDIUM_HUMAN
    assert mock_duel.call_args.kwargs["opponent_disbelief_bonus"] == pytest.approx(0.06)


def test_execute_search_cast_illusory_hero_leader_caster_passes_own_detect_illusions_as_caster_bonus():
    # Phase 494: same wiring as Mirror-Image's own equivalent test --
    # Illusory Hero is exclusively leader-cast in practice, so the leader
    # is always the caster/Stage-2 disbeliever here.
    leader = _skilled_leader(Ability.ILLUSION, 5)
    leader.advanced_abilities.add(AdvancedAbility.DETECT_ILLUSIONS_TALENT)
    state = GameState()
    state.add_leader(leader)
    state.add_leader(LeaderState(VALHALLA_VISITOR_LEADER_ID, None, "Hero", LOCATION))
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _cast_request(1, Spell.ILLUS_HERO)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.resolve_illusory_hero_duel"
    ) as mock_duel:
        mock_duel.return_value = EncounterCombatResult(winner=None, rounds=1)
        execute_search(state, LEADER_ID, request, random.Random(0))

    assert mock_duel.call_args.kwargs["caster_has_detect_illusions"] is True
    assert mock_duel.call_args.kwargs["opponent_has_detect_illusions"] is False


def test_execute_search_cast_illusory_hero_caster_wins_instantly():
    leader = _skilled_leader(Ability.ILLUSION, 5)
    state = GameState()
    state.add_leader(leader)
    state.add_leader(LeaderState(VALHALLA_VISITOR_LEADER_ID, None, "Hero", LOCATION))
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _cast_request(1, Spell.ILLUS_HERO)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.resolve_illusory_hero_duel"
    ) as mock_duel:
        mock_duel.return_value = EncounterCombatResult(winner="a", rounds=2)
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert result.winner == "leader"
    assert result.feature_looted is True


def test_execute_search_cast_illusory_hero_caster_is_slain_by_own_illusion():
    leader = _skilled_leader(Ability.ILLUSION, 5)
    state = GameState()
    state.add_leader(leader)
    state.add_leader(LeaderState(VALHALLA_VISITOR_LEADER_ID, None, "Hero", LOCATION))
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _cast_request(1, Spell.ILLUS_HERO)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.resolve_illusory_hero_duel"
    ) as mock_duel:
        mock_duel.return_value = EncounterCombatResult(winner="b", rounds=2)
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert result.winner == "monster"
    assert result.leader_killed is True


def test_execute_search_cast_illusory_hero_turns_on_master_when_alignments_are_hostile():
    leader = _skilled_leader(Ability.ILLUSION, 5, alignment=Alignment.GOOD)
    state = GameState()
    state.add_leader(leader)
    state.add_leader(LeaderState(VALHALLA_VISITOR_LEADER_ID, None, "Hero", LOCATION, alignment=Alignment.EVIL))
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _cast_request(1, Spell.ILLUS_HERO)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.resolve_illusory_hero_duel"
    ) as mock_duel:
        mock_duel.return_value = EncounterCombatResult(winner=None, rounds=1)
        execute_search(state, LEADER_ID, request, random.Random(0))

    assert mock_duel.call_args.kwargs["turns_on_master"] is True


def test_execute_search_cast_illusory_hero_turns_on_master_false_when_alignments_unset():
    leader = _skilled_leader(Ability.ILLUSION, 5)
    state = GameState()
    state.add_leader(leader)
    state.add_leader(LeaderState(VALHALLA_VISITOR_LEADER_ID, None, "Hero", LOCATION))
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _cast_request(1, Spell.ILLUS_HERO)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.resolve_illusory_hero_duel"
    ) as mock_duel:
        mock_duel.return_value = EncounterCombatResult(winner=None, rounds=1)
        execute_search(state, LEADER_ID, request, random.Random(0))

    assert mock_duel.call_args.kwargs["turns_on_master"] is False


# -- Phase 214: Gate Demon / Lava Pool ----------------------------------------


def test_execute_search_cast_gate_demon_refusal_only_rolled_for_eligible_alignment():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _cast_request(1, Spell.GATE_DEMON)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.roll_monster_alignment", return_value=Alignment.GOOD
    ), patch("ak_engine.turn.search_execution.resolve_gate_demon_refusal") as mock_refusal, patch(
        "ak_engine.turn.search_execution.roll_gate_demon_type", return_value=Monster.ARCHER
    ), patch("ak_engine.turn.search_execution.resolve_melee_duel", return_value=EncounterCombatResult(winner="a", rounds=1)):
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    # Alignment.GOOD is below the Evil-to-Undead eligibility floor -- the
    # demon never even considers refusing.
    assert not mock_refusal.called
    assert result.winner == "leader"


def test_execute_search_cast_gate_demon_refusal_prevents_the_demon_duel():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _cast_request(1, Spell.GATE_DEMON, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.roll_monster_alignment", return_value=Alignment.EVIL
    ), patch("ak_engine.turn.search_execution.resolve_gate_demon_refusal", return_value=True), patch(
        "ak_engine.turn.search_execution.roll_gate_demon_type"
    ) as mock_demon_type, patch(
        "ak_engine.turn.search_execution.resolve_melee_duel", return_value=EncounterCombatResult(winner="a", rounds=1)
    ) as mock_melee:
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert not mock_demon_type.called  # refused -- no demon is ever summoned
    assert mock_melee.called  # falls through to the plan's own following Melee tactic
    assert result.winner == "leader"


def test_execute_search_cast_gate_demon_win_credits_the_caster():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _cast_request(1, Spell.GATE_DEMON)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.roll_monster_alignment", return_value=Alignment.GOOD
    ), patch("ak_engine.turn.search_execution.roll_gate_demon_type", return_value=Monster.ARCHER), patch(
        "ak_engine.turn.search_execution.resolve_melee_duel", return_value=EncounterCombatResult(winner="a", rounds=3)
    ):
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert result.winner == "leader"
    assert result.feature_looted is True


def test_execute_search_cast_gate_demon_loss_lets_the_plan_continue():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _cast_request(1, Spell.GATE_DEMON, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.roll_monster_alignment", return_value=Alignment.GOOD
    ), patch("ak_engine.turn.search_execution.roll_gate_demon_type", return_value=Monster.ARCHER), patch(
        "ak_engine.turn.search_execution.roll_monster_encounter_plan", return_value=()
    ), patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_melee:
        mock_melee.side_effect = [
            EncounterCombatResult(winner="b", rounds=2),  # the demon loses to the guardian
            EncounterCombatResult(winner="a", rounds=1),  # the plan's own following Melee
        ]
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert mock_melee.call_count == 2
    assert result.winner == "leader"  # decided by the second (real) duel, not the demon's loss


def test_execute_search_cast_gate_demon_missing_stats_has_no_effect():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _cast_request(1, Spell.GATE_DEMON, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.roll_monster_alignment", return_value=Alignment.GOOD
    ), patch(
        "ak_engine.turn.search_execution.roll_gate_demon_type", return_value=Monster.NOMONSTER
    ), patch(
        "ak_engine.turn.search_execution.resolve_melee_duel", return_value=EncounterCombatResult(winner="a", rounds=1)
    ) as mock_melee:
        execute_search(state, LEADER_ID, request, random.Random(0))

    assert mock_melee.call_count == 1  # only the plan's own Melee tactic -- no demon duel attempted


def test_execute_search_cast_lava_pool_immune_species_has_no_effect():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.SPECTRE))
    request = _cast_request(1, Spell.LAVA_POOL, Maneuver.MELEE)

    # SPECTRE's own real rolled plan may include real CAST tactics of its
    # own; mocked empty here for the same reason the Ice Suspend immune-
    # species test above does.
    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.roll_monster_encounter_plan", return_value=()
    ), patch("ak_engine.turn.search_execution.resolve_lava_pool_escape") as mock_escape, patch(
        "ak_engine.turn.search_execution.resolve_melee_duel", return_value=EncounterCombatResult(winner="a", rounds=1)
    ):
        execute_search(state, LEADER_ID, request, random.Random(0))

    assert not mock_escape.called


def test_execute_search_cast_lava_pool_uses_the_monster_targets_own_speed():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _cast_request(1, Spell.LAVA_POOL)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.resolve_lava_pool_escape", return_value=True
    ) as mock_escape:
        execute_search(state, LEADER_ID, request, random.Random(0))

    # MONSTER_COMBAT_STATS[Monster.ARCHER].speed is MonsterSpeed.MEDIUM.
    assert mock_escape.call_args[0][0] is MonsterSpeed.MEDIUM


def test_execute_search_cast_lava_pool_escape_has_no_effect():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _cast_request(1, Spell.LAVA_POOL, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.resolve_lava_pool_escape", return_value=True
    ), patch(
        "ak_engine.turn.search_execution.resolve_melee_duel", return_value=EncounterCombatResult(winner="a", rounds=1)
    ) as mock_melee:
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert mock_melee.called  # no instant kill -- falls through to the plan's own Melee
    assert result.winner == "leader"


def test_execute_search_cast_lava_pool_failed_escape_kills_instantly():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _cast_request(1, Spell.LAVA_POOL)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.resolve_lava_pool_escape", return_value=False
    ):
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert result.winner == "leader"
    assert result.feature_looted is True


def test_execute_search_cast_lava_pool_on_a_leader_target_defaults_to_medium_speed():
    # A leader target has no sourced speed of its own -- defaults to
    # MonsterSpeed.MEDIUM, the same tier the rulebook's own [5.6] Flee
    # text already groups "other characters" into. The MONSTER is the
    # caster here (its own rolled plan carries the CAST tactic), the
    # leader is the target -- the reverse of every other test above.
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _melee_request(1)
    monster_plan = (SearchTactic(maneuver=Maneuver.CAST, sub_object=Spell.LAVA_POOL.value),)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.resolve_lava_pool_escape", return_value=True
    ) as mock_escape, patch(
        "ak_engine.turn.search_execution.roll_monster_encounter_plan", return_value=monster_plan
    ), patch(
        "ak_engine.turn.search_execution.resolve_melee_duel", return_value=EncounterCombatResult(winner="a", rounds=1)
    ):
        execute_search(state, LEADER_ID, request, random.Random(0))

    assert mock_escape.call_args[0][0] is MonsterSpeed.MEDIUM


# -- Phase 238: Augur Combat ---------------------------------------------------


def test_execute_search_cast_augur_combat_monster_caster_has_no_effect():
    # Confirmed by the user: never appears in any real
    # monster_encounter_plan.py species plan and a monster has no Temper
    # to shirk with, so a monster-cast Augur Combat is a documented
    # no-effect.
    state = _state_with_leader(skills=SkillTable(raw_values=[0] * 30))
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _melee_request(1)
    monster_plan = (SearchTactic(maneuver=Maneuver.CAST, sub_object=Spell.AUGUR_COMBAT.value),)

    with patch(
        "ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True
    ) as mock_roll, patch(
        "ak_engine.turn.search_execution.roll_monster_encounter_plan", return_value=monster_plan
    ), patch("ak_engine.turn.search_execution.resolve_melee_duel", return_value=EncounterCombatResult(winner="a", rounds=1)):
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert mock_roll.called  # the generic cast-success roll still happens...
    assert result.winner == "leader"  # ...but the spell's own effect is a documented no-op


def test_execute_search_cast_augur_combat_not_first_tactic_flee_succeeds():
    # AUGUR_COMBAT_ACTS_AS_FLEE_WHEN_CAST_LATER -- Maneuver.GIVE (still
    # unwired, no-op, no RNG consumed as of Phase 240) stands in as a
    # harmless "something else came first" tactic. Talk itself is no
    # longer inert (Phase 240), so it can't be reused here.
    leader = _skilled_leader(Ability.PSYCHIC, 5, temper=Temper.COWARDLY)
    state = GameState()
    state.add_leader(leader)
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = SearchRequest(
        feature_id=1,
        unconfirmed_extra0=0,
        tactics=[
            SearchTactic(maneuver=Maneuver.GIVE),
            SearchTactic(maneuver=Maneuver.CAST, sub_object=Spell.AUGUR_COMBAT.value),
            SearchTactic(maneuver=Maneuver.MELEE),
        ],
    )

    # Archer is MEDIUM speed (50% flee chance). Padding: the monster's own
    # hit_points draw (rng.randint()) runs first, consuming an unknown
    # number of randoms from the front of the queue (same established
    # pattern as test_execute_search_flee_tactic_success_ends_search_
    # without_combat above) -- every value here is 0.01 (< 50%), so
    # whichever one lands on the Flee-check roll still succeeds.
    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.roll_monster_encounter_plan", return_value=()
    ), patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_melee:
        result = execute_search(state, LEADER_ID, request, ScriptedRandom([0.01] * 20))

    assert result.fled is True
    assert result.combat_resolved is False
    assert not mock_melee.called


def test_execute_search_cast_augur_combat_not_first_tactic_flee_fails_falls_through():
    leader = _skilled_leader(Ability.PSYCHIC, 5, temper=Temper.COWARDLY)
    state = GameState()
    state.add_leader(leader)
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = SearchRequest(
        feature_id=1,
        unconfirmed_extra0=0,
        tactics=[
            SearchTactic(maneuver=Maneuver.GIVE),
            SearchTactic(maneuver=Maneuver.CAST, sub_object=Spell.AUGUR_COMBAT.value),
            SearchTactic(maneuver=Maneuver.MELEE),
        ],
    )

    # Archer is MEDIUM speed (50% flee chance). Padding: every value here is
    # 0.99 (>= 50%), so whichever one lands on the Flee-check roll still
    # fails, regardless of how many the monster's own hit_points draw
    # consumes first (same rationale as the test above).
    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.roll_monster_encounter_plan", return_value=()
    ), patch(
        "ak_engine.turn.search_execution.resolve_melee_duel", return_value=EncounterCombatResult(winner="a", rounds=1)
    ) as mock_melee:
        result = execute_search(state, LEADER_ID, request, ScriptedRandom([0.99] * 20))

    assert result.fled is False
    assert mock_melee.called
    assert result.winner == "leader"


def test_execute_search_cast_augur_combat_first_tactic_no_temper_has_no_effect():
    state = _state_with_leader()  # no skills, no temper
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _cast_request(1, Spell.AUGUR_COMBAT, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.resolve_melee_duel", return_value=EncounterCombatResult(winner="a", rounds=1)
    ) as mock_melee:
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert mock_melee.call_count == 1  # only the plan's own Melee -- no simulated duel attempted
    assert result.winner == "leader"


def test_execute_search_cast_augur_combat_simulated_win_never_shirks():
    leader = _skilled_leader(Ability.PSYCHIC, 5, temper=Temper.COWARDLY)  # highest shirk chance (80%)
    state = GameState()
    state.add_leader(leader)
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _cast_request(1, Spell.AUGUR_COMBAT, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.resolve_melee_duel"
    ) as mock_melee:
        mock_melee.side_effect = [
            EncounterCombatResult(winner="a", rounds=2),  # the silent simulation: caster wins
            EncounterCombatResult(winner="a", rounds=1),  # the plan's own real, following Melee
        ]
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert mock_melee.call_count == 2  # simulation always runs, real duel follows (never shirks)
    assert result.fled is False
    assert result.winner == "leader"


def test_execute_search_cast_augur_combat_simulated_loss_shirks_and_flees():
    leader = _skilled_leader(Ability.PSYCHIC, 5, temper=Temper.COWARDLY)
    state = GameState()
    state.add_leader(leader)
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _cast_request(1, Spell.AUGUR_COMBAT, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.resolve_melee_duel", return_value=EncounterCombatResult(winner="b", rounds=2)
    ) as mock_melee, patch("ak_engine.turn.search_execution.resolve_augur_combat", return_value=True) as mock_shirk:
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert mock_shirk.call_args[0][0] is True  # would_lose_simulated_combat
    assert mock_shirk.call_args[0][1] is Temper.COWARDLY
    assert mock_melee.call_count == 1  # only the simulation ran -- shirked before any real duel
    assert result.fled is True
    assert result.combat_resolved is False


def test_execute_search_cast_augur_combat_simulated_loss_no_shirk_falls_through():
    leader = _skilled_leader(Ability.PSYCHIC, 5, temper=Temper.BERSERK)
    state = GameState()
    state.add_leader(leader)
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _cast_request(1, Spell.AUGUR_COMBAT, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.resolve_melee_duel"
    ) as mock_melee, patch("ak_engine.turn.search_execution.resolve_augur_combat", return_value=False):
        mock_melee.side_effect = [
            EncounterCombatResult(winner="b", rounds=2),  # simulation: caster loses
            EncounterCombatResult(winner="a", rounds=1),  # real Melee, unaffected by the loss
        ]
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert mock_melee.call_count == 2
    assert result.fled is False
    assert result.winner == "leader"


def test_execute_search_cast_augur_combat_simulation_does_not_mutate_real_combatants():
    # `dataclasses.replace()` clones -- a real (unmocked) simulated duel
    # must not leave the real leader/monster combatants damaged before
    # the real duel actually runs.
    leader = _skilled_leader(Ability.PSYCHIC, 5, temper=Temper.BRAVE)
    state = GameState()
    state.add_leader(leader)
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _cast_request(1, Spell.AUGUR_COMBAT, Maneuver.MELEE)

    # Real resolve_melee_duel/resolve_augur_combat, real RNG -- if the
    # simulation mutated the real combatants, this would either crash
    # (fighting with 0 or negative hit points) or resolve the second,
    # real duel deterministically wrong.
    result = execute_search(state, LEADER_ID, request, random.Random(42))

    assert result.combat_resolved is True or result.fled is True
    assert result.winner in ("leader", "monster", None)


# -- Phase 289: Words of Healing --


def test_execute_search_cast_words_of_healing_heals_leader_to_full_after_taking_damage():
    leader = _skilled_leader(Ability.WHITE, 5)
    state = GameState()
    state.add_leader(leader)
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    tactics = [
        SearchTactic(maneuver=Maneuver.SHOOT),
        SearchTactic(maneuver=Maneuver.CAST, sub_object=Spell.HEAL.value),
        SearchTactic(maneuver=Maneuver.MELEE),
    ]
    request = SearchRequest(feature_id=1, unconfirmed_extra0=0, tactics=tactics)

    with patch(
        "ak_engine.turn.search_execution.resolve_fire_arrow_duel", side_effect=_damage_leader_fire_arrow_duel
    ), patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.resolve_melee_duel"
    ) as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_search(state, LEADER_ID, request, random.Random(0))

    leader_combatant = mock_melee.call_args[0][0]
    assert leader_combatant.hit_points == CHARACTER_HIT_POINTS


def test_execute_search_cast_words_of_healing_level_gate_blocks_low_white_skill():
    leader = _skilled_leader(Ability.WHITE, 4)
    state = GameState()
    state.add_leader(leader)
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _cast_request(1, Spell.HEAL, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast") as mock_cast_roll, patch(
        "ak_engine.turn.search_execution.words_of_healing_heal"
    ) as mock_heal, patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_search(state, LEADER_ID, request, random.Random(0))

    assert not mock_cast_roll.called
    assert not mock_heal.called
    assert mock_melee.called


def test_execute_search_cast_words_of_healing_monster_caster_heals_to_its_own_starting_hit_points():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    expected_hp = random.Random(0).randint(*MONSTER_COMBAT_STATS[Monster.ARCHER].hit_points_range)
    monster_plan = (SearchTactic(maneuver=Maneuver.CAST, sub_object=Spell.HEAL.value),)

    with patch("ak_engine.turn.search_execution.roll_monster_encounter_plan", return_value=monster_plan), patch.dict(
        "ak_engine.turn.search_execution.MONSTER_MAGIC_ABILITIES", {Monster.ARCHER: {Ability.WHITE: 5}}
    ), patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True), patch(
        "ak_engine.turn.search_execution.words_of_healing_heal"
    ) as mock_heal, patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_search(state, LEADER_ID, _melee_request(1), random.Random(0))

    assert mock_heal.called
    monster_combatant_arg, max_hp_arg = mock_heal.call_args[0]
    assert max_hp_arg == expected_hp


# -- Phase 506: Steal, real disassembly-sourced formula --


def test_execute_search_steal_success_but_monster_hides_the_hoard_falls_through():
    # The real formula's own two-roll order: the success roll (monster-
    # intelligence-blind) passes here, but the second, intelligence-based
    # item-transfer roll fails -- the thief got past the guardian but
    # found nothing, a documented no-effect, not a caught-thief outcome.
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _steal_request(1, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.roll_monster_encounter_plan", return_value=()), patch(
        "ak_engine.turn.search_execution.resolve_steal_attempt", return_value=True
    ), patch(
        "ak_engine.turn.search_execution.resolve_steal_monster_item_transfer", return_value=False
    ) as mock_transfer, patch(
        "ak_engine.turn.search_execution.resolve_melee_duel", return_value=EncounterCombatResult(winner="a", rounds=1)
    ) as mock_melee:
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert mock_transfer.called
    assert mock_melee.called  # nothing found -- the plan's own Melee still runs
    assert result.winner == "leader"


def test_execute_search_steal_success_loots_the_feature():
    state = _state_with_leader()
    feature = Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER)
    state.add_feature(feature)
    request = _steal_request(1)

    with patch("ak_engine.turn.search_execution.roll_monster_encounter_plan", return_value=()), patch(
        "ak_engine.turn.search_execution.resolve_steal_attempt", return_value=True
    ), patch("ak_engine.turn.search_execution.resolve_steal_monster_item_transfer", return_value=True):
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert result.winner == "leader"
    assert result.feature_looted is True
    assert feature.looted is True


def test_execute_search_steal_success_credits_the_thief_prince_merit_tally():
    # Phase 442: MeritTally.successful_thefts -- the other of the real
    # compiled formula's own "two separate success paths" (thiefprince_
    # merit_points()'s own Phase 369 addendum), sibling to challenge_
    # execution.py's own character-vs-character Steal credit.
    state = _state_with_leader()
    feature = Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER)
    state.add_feature(feature)
    request = _steal_request(1)

    with patch("ak_engine.turn.search_execution.roll_monster_encounter_plan", return_value=()), patch(
        "ak_engine.turn.search_execution.resolve_steal_attempt", return_value=True
    ), patch("ak_engine.turn.search_execution.resolve_steal_monster_item_transfer", return_value=True):
        execute_search(state, LEADER_ID, request, random.Random(0))

    assert state.leaders[LEADER_ID].merit_tally.successful_thefts == 1


def test_execute_search_steal_success_awards_real_add_experience_credit():
    # Phase 457: AKGEN_reverse_engineering_report (2).md SS3.3's own
    # Thief row (base 15) -- the same real credit challenge_execution.py
    # _apply_successful_theft() awards for the character-vs-character
    # Steal path, sibling-wired here for the guarded-feature Steal path.
    state = _state_with_leader()
    feature = Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER)
    state.add_feature(feature)
    request = _steal_request(1)

    with patch("ak_engine.turn.search_execution.roll_monster_encounter_plan", return_value=()), patch(
        "ak_engine.turn.search_execution.resolve_steal_attempt", return_value=True
    ), patch("ak_engine.turn.search_execution.resolve_steal_monster_item_transfer", return_value=True):
        execute_search(state, LEADER_ID, request, random.Random(0))

    assert state.leaders[LEADER_ID].experience_credit > 0


def test_execute_search_steal_failure_evades_falls_through():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _steal_request(1, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.roll_monster_encounter_plan", return_value=()), patch(
        "ak_engine.turn.search_execution.resolve_steal_attempt", return_value=False
    ), patch(
        "ak_engine.turn.search_execution.resolve_steal_evasion", return_value=True
    ) as mock_evasion, patch(
        "ak_engine.turn.search_execution.resolve_melee_duel", return_value=EncounterCombatResult(winner="a", rounds=1)
    ) as mock_melee:
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert mock_evasion.called
    assert mock_melee.called  # evaded capture -- the plan's own Melee still runs
    assert result.winner == "leader"


def test_execute_search_steal_caught_spell_range_no_effect_falls_through():
    # Archer is a multi-variant guardian: roll_monster_encounter_plan is
    # mocked to () so it doesn't consume the scripted rng.choice queue
    # meant for the caught-thief combat-range roll.
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _steal_request(1, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.roll_monster_encounter_plan", return_value=()), patch(
        "ak_engine.turn.search_execution.resolve_steal_attempt", return_value=False
    ), patch(
        "ak_engine.turn.search_execution.resolve_steal_evasion", return_value=False
    ), patch(
        "ak_engine.turn.search_execution.resolve_melee_duel", return_value=EncounterCombatResult(winner="a", rounds=1)
    ) as mock_melee:
        rng = ScriptedRandom([0.5] * 20, choice_indices=[0])  # SPELL_RANGE
        result = execute_search(state, LEADER_ID, request, rng)

    assert mock_melee.called  # spell-range combat has no model -- the plan's own Melee still runs
    assert result.winner == "leader"


def test_execute_search_steal_caught_melee_range_resolves_melee_duel():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _steal_request(1)

    with patch("ak_engine.turn.search_execution.roll_monster_encounter_plan", return_value=()), patch(
        "ak_engine.turn.search_execution.resolve_steal_attempt", return_value=False
    ), patch(
        "ak_engine.turn.search_execution.resolve_steal_evasion", return_value=False
    ), patch(
        "ak_engine.turn.search_execution.resolve_melee_duel", return_value=EncounterCombatResult(winner="b", rounds=1)
    ) as mock_melee:
        rng = ScriptedRandom([0.5] * 20, choice_indices=[2])  # MELEE_RANGE
        result = execute_search(state, LEADER_ID, request, rng)

    assert mock_melee.called
    assert result.winner == "monster"
    assert LEADER_ID not in state.leaders


def test_execute_search_steal_caught_bow_range_resolves_fire_arrow_duel():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _steal_request(1)

    with patch("ak_engine.turn.search_execution.roll_monster_encounter_plan", return_value=()), patch(
        "ak_engine.turn.search_execution.resolve_steal_attempt", return_value=False
    ), patch(
        "ak_engine.turn.search_execution.resolve_steal_evasion", return_value=False
    ), patch(
        "ak_engine.turn.search_execution.resolve_fire_arrow_duel", return_value=EncounterCombatResult(winner="a", rounds=1)
    ) as mock_fire:
        rng = ScriptedRandom([0.5] * 20, choice_indices=[1])  # BOW_RANGE
        result = execute_search(state, LEADER_ID, request, rng)

    assert mock_fire.called
    assert result.winner == "leader"
    assert result.feature_looted is True


# -- Phase 537: racial-command item skips the normal Talk roll ----------
# AKGEN_reverse_engineering_report (4).md SS9.


def test_execute_search_talk_command_item_skips_the_roll_and_loots_the_feature():
    state = _state_with_leader()
    state.add_item(Treasure.MONSTER_AID_DRAGON, owner_leader_id=LEADER_ID)
    state.add_feature(
        Feature(
            feature_id=1,
            coord=LOCATION,
            kind=FeatureType.CAVE,
            guardian_monster=Monster.R_DRAGON,
            treasure=Treasure.GOLD_HOARD_LARGE,
        )
    )
    request = _talk_request(1)

    with patch("ak_engine.turn.search_execution.select_monster_talk_reply") as mock_reply:
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert not mock_reply.called  # no social roll at all
    assert result.accepted is True
    assert result.combat_resolved is False
    assert result.winner == "leader"
    assert result.feature_looted is True
    assert state.features[1].looted is True
    assert any(item.treasure is Treasure.GOLD_HOARD_LARGE for item in state.items_held_by(LEADER_ID))


def test_execute_search_talk_command_item_does_not_apply_to_a_non_matching_species():
    # Holding the Dragon-command item against a non-Dragon/Eagle/Whale
    # guardian doesn't skip anything -- the normal 24-reply table still
    # runs (Archer needs Druid level 0, so any leader can talk to it).
    state = _state_with_leader()
    state.add_item(Treasure.MONSTER_AID_DRAGON, owner_leader_id=LEADER_ID)
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _talk_request(1, Maneuver.MELEE)

    with patch(
        "ak_engine.turn.search_execution.select_monster_talk_reply", return_value=MonsterTalkReply.R_PUZZLED
    ) as mock_reply, patch(
        "ak_engine.turn.search_execution.resolve_melee_duel", return_value=EncounterCombatResult(winner="a", rounds=1)
    ):
        execute_search(state, LEADER_ID, request, ScriptedRandom([0.1] * 20))

    assert mock_reply.called


def test_execute_search_talk_without_the_item_still_uses_the_normal_roll_against_a_dragon():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.CAVE, guardian_monster=Monster.R_DRAGON))
    request = _talk_request(1, Maneuver.MELEE)

    with patch(
        "ak_engine.turn.search_execution.select_monster_talk_reply", return_value=MonsterTalkReply.R_PUZZLED
    ) as mock_reply, patch(
        "ak_engine.turn.search_execution.resolve_melee_duel", return_value=EncounterCombatResult(winner="a", rounds=1)
    ):
        execute_search(state, LEADER_ID, request, ScriptedRandom([0.1] * 20))

    assert mock_reply.called


# -- Phase 240: Talk / Say --


def test_execute_search_talk_dr_gate_not_met_falls_through():
    # Gargoyle needs Druid level 2 -- a leader with no Druid skill can't
    # even communicate, so the plan falls through to its own Melee.
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.CAVE, guardian_monster=Monster.GARGOYLE))
    request = _talk_request(1, Maneuver.MELEE)

    with patch(
        "ak_engine.turn.search_execution.resolve_melee_duel", return_value=EncounterCombatResult(winner="a", rounds=1)
    ) as mock_melee:
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert mock_melee.called
    assert result.winner == "leader"


def test_execute_search_talk_dr_gate_not_met_awards_no_add_experience_credit():
    # Phase 459: the DR gate failing means no real druidic interaction
    # happened at all -- no Add_Experience credit either.
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.CAVE, guardian_monster=Monster.GARGOYLE))
    request = _talk_request(1, Maneuver.MELEE)

    with patch(
        "ak_engine.turn.search_execution.resolve_melee_duel", return_value=EncounterCombatResult(winner="a", rounds=1)
    ):
        execute_search(state, LEADER_ID, request, random.Random(0))

    assert state.leaders[LEADER_ID].experience_credit == 0


def test_execute_search_talk_dr_gate_met_awards_real_add_experience_credit():
    # Phase 459: AKGEN_reverse_engineering_report (2).md SS3.3's own
    # Druid row (base 10) -- the DR gate passing (regardless of which
    # reply follows) is the real "interazione druidica" this credits.
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _talk_request(1, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.roll_monster_encounter_plan", return_value=()), patch(
        "ak_engine.turn.search_execution.select_monster_talk_reply", return_value=MonsterTalkReply.R_PUZZLED
    ), patch(
        "ak_engine.turn.search_execution.resolve_melee_duel", return_value=EncounterCombatResult(winner="a", rounds=1)
    ):
        execute_search(state, LEADER_ID, request, ScriptedRandom([0.1] * 20))

    assert state.leaders[LEADER_ID].experience_credit > 0


# -- Phase 544: Talk language-failure narrative branch --


def test_execute_search_talk_language_failure_puzzled_for_low_intelligence_monster():
    # AKGEN_reverse_engineering_report (3).md SS60-62.1: the DR-gate-
    # failure branch's own mintel < Medium half ("RPuzzled"). Gargoyle
    # needs Druid level 2 (unreachable for a level-0 leader) and is
    # MonsterIntelligence.LOW (< Medium) in MONSTER_RUNTIME_PROFILE.
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.CAVE, guardian_monster=Monster.GARGOYLE))
    request = _talk_request(1, Maneuver.MELEE)

    with patch(
        "ak_engine.turn.search_execution.resolve_melee_duel", return_value=EncounterCombatResult(winner="a", rounds=1)
    ):
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert result.talk_language_failure is True


def test_execute_search_talk_language_failure_silent_for_medium_intelligence_monster():
    # Same DR-gate failure shape, but Giant Eagle is MonsterIntelligence.
    # MEDIUM (>= Medium) -- the dossier's own "_LIgnore" half, no
    # observable trace, matching this project's own pre-existing
    # TalkReplyOutcome.IGNORE convention.
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.CAVE, guardian_monster=Monster.GI_EAGLE))
    request = _talk_request(1, Maneuver.MELEE)

    with patch(
        "ak_engine.turn.search_execution.resolve_melee_duel", return_value=EncounterCombatResult(winner="a", rounds=1)
    ):
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert result.talk_language_failure is False


def test_execute_search_talk_language_failure_not_set_when_dr_gate_passes():
    # Archer needs Druid level 0 -- the DR gate always passes, so the
    # language-failure branch never applies at all, regardless of the
    # guardian's own intelligence tier.
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _talk_request(1, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.roll_monster_encounter_plan", return_value=()), patch(
        "ak_engine.turn.search_execution.select_monster_talk_reply", return_value=MonsterTalkReply.R_PUZZLED
    ), patch(
        "ak_engine.turn.search_execution.resolve_melee_duel", return_value=EncounterCombatResult(winner="a", rounds=1)
    ):
        result = execute_search(state, LEADER_ID, request, ScriptedRandom([0.1] * 20))

    assert result.talk_language_failure is False


def test_execute_search_talk_language_failure_not_set_without_a_talk_tactic():
    # No Talk tactic in the plan at all -- the language-failure branch
    # can never apply, even against a low-intelligence guardian the
    # leader couldn't have talked to anyway.
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.CAVE, guardian_monster=Monster.GARGOYLE))
    request = _melee_request(1)

    with patch(
        "ak_engine.turn.search_execution.resolve_melee_duel", return_value=EncounterCombatResult(winner="a", rounds=1)
    ):
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert result.talk_language_failure is False


def test_execute_search_talk_attack_reply_falls_through():
    # Phase 528: RCharge is an Attack-category reply -- no special effect
    # of its own, the plan's own Melee still runs (Archer needs Druid
    # level 0, so any leader can talk to it at all).
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _talk_request(1, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.roll_monster_encounter_plan", return_value=()), patch(
        "ak_engine.turn.search_execution.select_monster_talk_reply", return_value=MonsterTalkReply.R_CHARGE
    ), patch(
        "ak_engine.turn.search_execution.resolve_melee_duel", return_value=EncounterCombatResult(winner="a", rounds=1)
    ) as mock_melee:
        result = execute_search(state, LEADER_ID, request, ScriptedRandom([0.1] * 20))

    assert mock_melee.called
    assert result.winner == "leader"


def test_execute_search_talk_ignore_reply_falls_through():
    # RWarn is an Ignore-category reply -- also no special effect.
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _talk_request(1, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.roll_monster_encounter_plan", return_value=()), patch(
        "ak_engine.turn.search_execution.select_monster_talk_reply", return_value=MonsterTalkReply.R_WARN
    ), patch(
        "ak_engine.turn.search_execution.resolve_melee_duel", return_value=EncounterCombatResult(winner="a", rounds=1)
    ) as mock_melee:
        result = execute_search(state, LEADER_ID, request, ScriptedRandom([0.5] * 20))

    assert mock_melee.called
    assert result.winner == "leader"


def test_execute_search_talk_quest_reply_ends_search_unresolved():
    # RRegain is a Quest/Agreement-category reply -- the guardian
    # proposes a deal, ending the Search honestly unresolved (each
    # Quest's own distinct completion condition isn't modeled, Phase
    # 258's own scope note) rather than as a combat win/loss.
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _talk_request(1, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.roll_monster_encounter_plan", return_value=()), patch(
        "ak_engine.turn.search_execution.select_monster_talk_reply", return_value=MonsterTalkReply.R_REGAIN
    ), patch(
        "ak_engine.turn.search_execution.resolve_melee_duel"
    ) as mock_melee:
        result = execute_search(state, LEADER_ID, request, ScriptedRandom([0.9] * 20))

    assert not mock_melee.called
    assert result.accepted is True
    assert result.combat_resolved is False
    assert result.winner is None


def test_execute_search_talk_reply_is_resolved_once_and_reused():
    # Phase 528: AKGEN_reverse_engineering_report (3).md SS62's own "per
    # la stessa feature e lo stesso guardiano la risposta e normalmente
    # ripetibile" -- select_monster_talk_reply() is consulted at most
    # once per guardian; a later Search's own Talk against the same
    # feature reuses Feature.guardian_talk_reply_id instead of rolling
    # again (simulated here as two separate execute_search() calls
    # sharing the same Feature, standing in for two different turns).
    state = _state_with_leader()
    feature = Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER)
    state.add_feature(feature)
    request = _talk_request(1, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.roll_monster_encounter_plan", return_value=()), patch(
        "ak_engine.turn.search_execution.select_monster_talk_reply", return_value=MonsterTalkReply.R_WARN
    ) as mock_select, patch(
        "ak_engine.turn.search_execution.resolve_melee_duel", return_value=EncounterCombatResult(winner="a", rounds=1)
    ):
        execute_search(state, LEADER_ID, request, ScriptedRandom([0.5] * 20))
        assert mock_select.call_count == 1
        assert feature.guardian_talk_reply_id == MonsterTalkReply.R_WARN.value

        execute_search(state, LEADER_ID, request, ScriptedRandom([0.5] * 20))
        assert mock_select.call_count == 1  # not called again -- the persisted reply was reused


def test_execute_search_say_is_a_documented_noop_falls_through():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.CAVE, guardian_monster=Monster.GARGOYLE))
    request = SearchRequest(
        feature_id=1,
        unconfirmed_extra0=0,
        tactics=[SearchTactic(maneuver=Maneuver.SAY), SearchTactic(maneuver=Maneuver.MELEE)],
    )

    with patch(
        "ak_engine.turn.search_execution.resolve_melee_duel", return_value=EncounterCombatResult(winner="a", rounds=1)
    ) as mock_melee:
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert mock_melee.called
    assert result.winner == "leader"


# -- Phase 241: Beg --


def test_execute_search_beg_undamaged_leader_falls_through():
    # Full health -- nothing to beg about yet, no roll is even consulted.
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = SearchRequest(
        feature_id=1,
        unconfirmed_extra0=0,
        tactics=[SearchTactic(maneuver=Maneuver.BEG), SearchTactic(maneuver=Maneuver.MELEE)],
    )

    with patch("ak_engine.turn.search_execution.roll_monster_encounter_plan", return_value=()), patch(
        "ak_engine.turn.search_execution.resolve_beg_for_mercy"
    ) as mock_beg, patch(
        "ak_engine.turn.search_execution.resolve_melee_duel", return_value=EncounterCombatResult(winner="a", rounds=1)
    ) as mock_melee:
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert not mock_beg.called
    assert mock_melee.called
    assert result.winner == "leader"


def test_execute_search_beg_animal_tier_monster_never_succeeds():
    # Gryphon is Animal-tier -- BEG_MERCY_CHANCE is 0.0, so even a roll of
    # 0.0 (the most favorable possible) grants no mercy.
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.GRYPHON))
    request = _beg_request(1, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.roll_monster_encounter_plan", return_value=()), patch(
        "ak_engine.turn.search_execution.resolve_fire_arrow_duel", side_effect=_damage_leader_fire_arrow_duel
    ), patch(
        "ak_engine.turn.search_execution.resolve_melee_duel", return_value=EncounterCombatResult(winner="a", rounds=1)
    ) as mock_melee:
        result = execute_search(state, LEADER_ID, request, ScriptedRandom([0.0] * 20))

    assert mock_melee.called
    assert result.winner == "leader"


def test_execute_search_beg_success_flees_unharmed():
    # Archer is Medium-Human tier -- BEG_MERCY_CHANCE is 0.30. A damaged
    # leader rolling under that succeeds, ending the Search exactly like
    # a successful Flee.
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _beg_request(1, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.roll_monster_encounter_plan", return_value=()), patch(
        "ak_engine.turn.search_execution.resolve_fire_arrow_duel", side_effect=_damage_leader_fire_arrow_duel
    ), patch(
        "ak_engine.turn.search_execution.resolve_melee_duel"
    ) as mock_melee:
        result = execute_search(state, LEADER_ID, request, ScriptedRandom([0.1] * 20))

    assert not mock_melee.called
    assert result.accepted is True
    assert result.combat_resolved is False
    assert result.fled is True


def test_execute_search_beg_failure_falls_through():
    # Same setup as the success case, but a roll above the 30% threshold
    # fails -- no mercy, the plan's own next tactic (Melee) still runs.
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _beg_request(1, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.roll_monster_encounter_plan", return_value=()), patch(
        "ak_engine.turn.search_execution.resolve_fire_arrow_duel", side_effect=_damage_leader_fire_arrow_duel
    ), patch(
        "ak_engine.turn.search_execution.resolve_melee_duel", return_value=EncounterCombatResult(winner="a", rounds=1)
    ) as mock_melee:
        result = execute_search(state, LEADER_ID, request, ScriptedRandom([0.9] * 20))

    assert mock_melee.called
    assert result.winner == "leader"


# -- Phase 258: Fulfill --


def _fulfill_request(feature_id: int, *following: Maneuver) -> SearchRequest:
    tactics = [SearchTactic(maneuver=Maneuver.FULFILL)]
    tactics += [SearchTactic(maneuver=m) for m in following]
    return SearchRequest(feature_id=feature_id, unconfirmed_extra0=0, tactics=tactics)


def test_execute_search_talk_deal_reaction_records_the_pending_deal():
    state = _state_with_leader()
    feature = Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER)
    state.add_feature(feature)
    request = _talk_request(1, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.roll_monster_encounter_plan", return_value=()), patch(
        "ak_engine.turn.search_execution.select_monster_talk_reply", return_value=MonsterTalkReply.R_REGAIN
    ), patch(
        "ak_engine.turn.search_execution.resolve_melee_duel"
    ):
        execute_search(state, LEADER_ID, request, ScriptedRandom([0.9] * 20))

    assert feature.pending_deal_leader_id == LEADER_ID


# -- Phase 468: Silver Tongue wiring ---------------------------------------


def test_execute_search_talk_silver_tongue_titleholder_suppresses_combat():
    # Phase 528: Silver Tongue suppresses even an Attack-category reply
    # (RCharge) -- proven with a Talk-only plan (no following combat
    # tactic), so whether real combat happens at all depends entirely on
    # whether Silver Tongue set combat_attempted. LEADER_ID is the
    # world's only Diplomat candidate here, and meets OFFICE_MIN_POINTS
    # [Office.DIPLOMAT] (50) -- resolve_office_holder() picks them.
    state = _state_with_leader()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, LOCATION))
    state.leaders[LEADER_ID].merit_tally.diplomatic_merit_points = 50
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _talk_request(1)

    with patch(
        "ak_engine.turn.search_execution.select_monster_talk_reply", return_value=MonsterTalkReply.R_CHARGE
    ), patch(
        "ak_engine.turn.search_execution.resolve_melee_duel", return_value=EncounterCombatResult(winner="a", rounds=1)
    ) as mock_melee:
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert not mock_melee.called
    assert result.combat_resolved is False


def test_execute_search_talk_non_titleholder_still_forces_combat_on_attack_reply():
    state = _state_with_leader()  # diplomatic_merit_points defaults to 0.0 -- below min_points
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER))
    request = _talk_request(1)

    with patch(
        "ak_engine.turn.search_execution.select_monster_talk_reply", return_value=MonsterTalkReply.R_CHARGE
    ), patch(
        "ak_engine.turn.search_execution.resolve_melee_duel", return_value=EncounterCombatResult(winner="a", rounds=1)
    ) as mock_melee:
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert mock_melee.called
    assert result.winner == "leader"


def test_execute_search_fulfill_wires_the_silver_tongue_titleholder_into_the_honor_roll():
    state = _state_with_leader()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, LOCATION))
    state.leaders[LEADER_ID].merit_tally.diplomatic_merit_points = 50
    feature = Feature(
        feature_id=1,
        coord=LOCATION,
        kind=FeatureType.CAVE,
        guardian_monster=Monster.GARGOYLE,
        pending_deal_leader_id=LEADER_ID,
    )
    state.add_feature(feature)
    request = _fulfill_request(1)

    with patch("ak_engine.turn.search_execution.resolve_fulfill_honored", return_value=True) as mock_honor:
        execute_search(state, LEADER_ID, request, ScriptedRandom([0.1] * 20))

    assert mock_honor.call_args.kwargs["caster_is_silver_tongue"] is True


def test_execute_search_fulfill_no_pending_deal_falls_through():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.CAVE, guardian_monster=Monster.GARGOYLE))
    request = _fulfill_request(1, Maneuver.MELEE)

    with patch(
        "ak_engine.turn.search_execution.resolve_melee_duel", return_value=EncounterCombatResult(winner="a", rounds=1)
    ) as mock_melee:
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert mock_melee.called
    assert result.winner == "leader"


def test_execute_search_fulfill_pending_deal_for_a_different_leader_falls_through():
    state = _state_with_leader()
    feature = Feature(
        feature_id=1,
        coord=LOCATION,
        kind=FeatureType.CAVE,
        guardian_monster=Monster.GARGOYLE,
        pending_deal_leader_id=99,
    )
    state.add_feature(feature)
    request = _fulfill_request(1, Maneuver.MELEE)

    with patch(
        "ak_engine.turn.search_execution.resolve_melee_duel", return_value=EncounterCombatResult(winner="a", rounds=1)
    ) as mock_melee:
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert mock_melee.called
    assert result.winner == "leader"
    assert feature.pending_deal_leader_id == 99  # untouched -- not this leader's own deal


def test_execute_search_fulfill_honored_ends_search_peacefully_and_credits_raw_hp():
    state = _state_with_leader()
    feature = Feature(
        feature_id=1,
        coord=LOCATION,
        kind=FeatureType.CAVE,
        guardian_monster=Monster.GARGOYLE,
        pending_deal_leader_id=LEADER_ID,
    )
    state.add_feature(feature)
    expected_hp = random.Random(0).randint(*MONSTER_COMBAT_STATS[Monster.GARGOYLE].hit_points_range)
    request = _fulfill_request(1, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.resolve_fulfill_honored", return_value=True), patch(
        "ak_engine.turn.search_execution.resolve_melee_duel"
    ) as mock_melee:
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert not mock_melee.called  # honored -- the Search ends peacefully, no duel ever fought
    assert result.accepted is True
    assert result.combat_resolved is False
    assert result.winner == "leader"
    assert result.feature_looted is False
    assert feature.looted is False  # nothing ties Fulfill's own success to looting -- see module docstring
    assert feature.pending_deal_leader_id is None
    # Phase 301 fix: the raw, unhalved HP is stored here -- the negotiated
    # half-credit is applied once, by merit_points.py's own
    # defender_merit_points(), not pre-halved at the write site.
    assert state.leaders[LEADER_ID].merit_tally.monster_hp_neutralized == expected_hp
    assert state.leaders[LEADER_ID].merit_tally.monster_hp_defeated == 0


def test_execute_search_fulfill_honored_end_to_end_defender_merit_points_gets_exactly_half():
    # Phase 301 regression: a bug-hunt audit found this pipeline's own
    # writer (execute_search's _resolve_fulfill) and reader
    # (merit_points.defender_merit_points) each independently tested,
    # but never exercised together -- which is exactly how the writer
    # pre-halving the value, on top of the reader's own halving, hid for
    # a long time (a quartered credit instead of the documented half).
    # This test closes that gap by driving both ends of the real
    # pipeline in one place.
    from ak_engine.turn.merit_points import defender_merit_points

    state = _state_with_leader()
    feature = Feature(
        feature_id=1,
        coord=LOCATION,
        kind=FeatureType.CAVE,
        guardian_monster=Monster.GARGOYLE,
        pending_deal_leader_id=LEADER_ID,
    )
    state.add_feature(feature)
    expected_hp = random.Random(0).randint(*MONSTER_COMBAT_STATS[Monster.GARGOYLE].hit_points_range)
    request = _fulfill_request(1, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.resolve_fulfill_honored", return_value=True), patch(
        "ak_engine.turn.search_execution.resolve_melee_duel"
    ):
        execute_search(state, LEADER_ID, request, random.Random(0))

    assert defender_merit_points(state.leaders[LEADER_ID]) == expected_hp // 2


def test_execute_search_fulfill_not_honored_falls_through_and_clears_the_deal():
    state = _state_with_leader()
    feature = Feature(
        feature_id=1,
        coord=LOCATION,
        kind=FeatureType.CAVE,
        guardian_monster=Monster.GARGOYLE,
        pending_deal_leader_id=LEADER_ID,
    )
    state.add_feature(feature)
    request = _fulfill_request(1, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.resolve_fulfill_honored", return_value=False), patch(
        "ak_engine.turn.search_execution.resolve_melee_duel", return_value=EncounterCombatResult(winner="a", rounds=1)
    ) as mock_melee:
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert mock_melee.called  # not honored -- no forced combat, just the plan's own next tactic
    assert result.winner == "leader"
    assert feature.pending_deal_leader_id is None  # the attempt still consumes the pending flag


# -- Phase 671: quest/Fulfill pacification + intimidating-attack --------


def test_execute_search_fulfill_honored_pacifies_a_bold_guardian_to_mercenary():
    state = _state_with_leader()
    feature = Feature(
        feature_id=1,
        coord=LOCATION,
        kind=FeatureType.CAVE,
        guardian_monster=Monster.GARGOYLE,
        pending_deal_leader_id=LEADER_ID,
        guardian_state=MonsterEngagementState.BOLD,
    )
    state.add_feature(feature)
    request = _fulfill_request(1, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.resolve_fulfill_honored", return_value=True), patch(
        "ak_engine.turn.search_execution.resolve_melee_duel"
    ):
        execute_search(state, LEADER_ID, request, random.Random(0))

    assert feature.guardian_state is MonsterEngagementState.MERCENARY


def test_execute_search_fulfill_honored_pacifies_a_mercenary_guardian_to_calm():
    state = _state_with_leader()
    feature = Feature(
        feature_id=1,
        coord=LOCATION,
        kind=FeatureType.CAVE,
        guardian_monster=Monster.GARGOYLE,
        pending_deal_leader_id=LEADER_ID,
        guardian_state=MonsterEngagementState.MERCENARY,
    )
    state.add_feature(feature)
    request = _fulfill_request(1, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.resolve_fulfill_honored", return_value=True), patch(
        "ak_engine.turn.search_execution.resolve_melee_duel"
    ):
        execute_search(state, LEADER_ID, request, random.Random(0))

    assert feature.guardian_state is MonsterEngagementState.CALM


def test_execute_search_fulfill_not_honored_leaves_guardian_state_untouched():
    state = _state_with_leader()
    feature = Feature(
        feature_id=1,
        coord=LOCATION,
        kind=FeatureType.CAVE,
        guardian_monster=Monster.GARGOYLE,
        pending_deal_leader_id=LEADER_ID,
        guardian_state=MonsterEngagementState.BOLD,
    )
    state.add_feature(feature)
    request = _fulfill_request(1, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.resolve_fulfill_honored", return_value=False), patch(
        "ak_engine.turn.search_execution.resolve_melee_duel", return_value=EncounterCombatResult(winner="a", rounds=1)
    ):
        execute_search(state, LEADER_ID, request, random.Random(0))

    assert feature.guardian_state is MonsterEngagementState.BOLD  # not honored -- no pacification applied


def _monster_wins_after_melee_damage(damage: int):
    # Gargoyle: Temper.BERSERK (factor 4-3=1), average_hit_points=15 --
    # damage=15 makes intimidation certain (p=1.0); damage=1 makes it a
    # 1/15 (~6.7%) chance, missed by the standard [0.1]*20 script below.
    def _side_effect(leader_combatant, monster_combatant, rng, **_kwargs):
        monster_combatant.hit_points -= damage
        return EncounterCombatResult(winner="b", rounds=1, melee_swings=(MeleeSwing(attacker="a", hit=True, damage=damage),))

    return _side_effect


def test_execute_search_intimidation_guardian_survives_loss_after_crossing_threshold():
    state = _state_with_leader()
    feature = Feature(
        feature_id=1, coord=LOCATION, kind=FeatureType.CAVE, guardian_monster=Monster.GARGOYLE,
        guardian_state=MonsterEngagementState.BOLD,
    )
    state.add_feature(feature)
    request = _melee_request(1)

    with patch("ak_engine.turn.search_execution.roll_monster_encounter_plan", return_value=()), patch(
        "ak_engine.turn.search_execution.resolve_melee_duel", side_effect=_monster_wins_after_melee_damage(15)
    ):
        result = execute_search(state, LEADER_ID, request, ScriptedRandom([0.1] * 20))

    assert result.winner == "monster"
    assert feature.guardian_state is MonsterEngagementState.MERCENARY
    assert result.guardian_intimidated is True
    assert result.guardian_undeterred is False


def test_execute_search_intimidation_not_triggered_below_threshold_renders_undeterred():
    state = _state_with_leader()
    feature = Feature(
        feature_id=1, coord=LOCATION, kind=FeatureType.CAVE, guardian_monster=Monster.GARGOYLE,
        guardian_state=MonsterEngagementState.BOLD,
    )
    state.add_feature(feature)
    request = _melee_request(1)

    with patch("ak_engine.turn.search_execution.roll_monster_encounter_plan", return_value=()), patch(
        "ak_engine.turn.search_execution.resolve_melee_duel", side_effect=_monster_wins_after_melee_damage(1)
    ):
        result = execute_search(state, LEADER_ID, request, ScriptedRandom([0.1] * 20))

    assert result.winner == "monster"
    assert feature.guardian_state is MonsterEngagementState.BOLD
    assert result.guardian_intimidated is False
    # Phase 673: the real _MUnDt outcome -- wounded, but the roll missed.
    assert result.guardian_undeterred is True


def _damage_leader_and_monster_via_fire_arrow(damage: int):
    def _side_effect(leader_combatant, monster_combatant, rng, **_kwargs):
        leader_combatant.hit_points -= 3
        monster_combatant.hit_points -= damage
        return EncounterCombatResult(winner=None, rounds=1, shots=(FireArrowShot(shooter="a", hit=True, damage=damage),))

    return _side_effect


def test_execute_search_intimidation_beg_success_after_crossing_threshold():
    # Archer: Temper.BRAVE (factor 4-2=2), average_hit_points=10 --
    # damage=5 makes intimidation certain (p=1.0).
    state = _state_with_leader()
    feature = Feature(
        feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER,
        guardian_state=MonsterEngagementState.BOLD,
    )
    state.add_feature(feature)
    request = _beg_request(1)

    with patch("ak_engine.turn.search_execution.roll_monster_encounter_plan", return_value=()), patch(
        "ak_engine.turn.search_execution.resolve_fire_arrow_duel", side_effect=_damage_leader_and_monster_via_fire_arrow(5)
    ), patch(
        "ak_engine.turn.search_execution.resolve_beg_for_mercy", return_value=True
    ):
        result = execute_search(state, LEADER_ID, request, ScriptedRandom([0.1] * 20))

    assert result.fled is True
    assert feature.guardian_state is MonsterEngagementState.MERCENARY
    assert result.guardian_intimidated is True


def test_execute_search_intimidation_beg_success_below_threshold_leaves_guardian_bold():
    state = _state_with_leader()
    feature = Feature(
        feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER,
        guardian_state=MonsterEngagementState.BOLD,
    )
    state.add_feature(feature)
    request = _beg_request(1)

    with patch("ak_engine.turn.search_execution.roll_monster_encounter_plan", return_value=()), patch(
        "ak_engine.turn.search_execution.resolve_fire_arrow_duel", side_effect=_damage_leader_fire_arrow_duel
    ), patch(
        "ak_engine.turn.search_execution.resolve_beg_for_mercy", return_value=True
    ):
        result = execute_search(state, LEADER_ID, request, ScriptedRandom([0.1] * 20))

    assert result.fled is True
    # Only the leader took damage in this fixture (no recorded Fire Arrow
    # shot against the monster at all) -- proves the check doesn't fire
    # unconditionally on any Beg success, and isn't a _MUnDt case either
    # since the guardian genuinely took no damage.
    assert feature.guardian_state is MonsterEngagementState.BOLD
    assert result.guardian_intimidated is False
    assert result.guardian_undeterred is False


def test_execute_search_intimidation_flee_success_after_crossing_threshold():
    # SHOOT (damages the monster past the threshold, nobody dies) then
    # FLEE -- MELEE alone can't be followed by another tactic here since
    # a lone/last MELEE resolves atomically via resolve_melee_duel()
    # (Phase 293's own "is_last_leader_tactic" fast path), never falling
    # through to a later tactic.
    state = _state_with_leader()
    feature = Feature(
        feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.ARCHER,
        guardian_state=MonsterEngagementState.BOLD,
    )
    state.add_feature(feature)
    request = SearchRequest(
        feature_id=1, unconfirmed_extra0=0,
        tactics=[SearchTactic(maneuver=Maneuver.SHOOT), SearchTactic(maneuver=Maneuver.FLEE)],
    )

    with patch("ak_engine.turn.search_execution.roll_monster_encounter_plan", return_value=()), patch(
        "ak_engine.turn.search_execution.resolve_fire_arrow_duel", side_effect=_damage_leader_and_monster_via_fire_arrow(5)
    ), patch(
        "ak_engine.turn.search_execution.effective_flee_chance", return_value=1.0
    ):
        result = execute_search(state, LEADER_ID, request, ScriptedRandom([0.0] * 20))

    assert result.fled is True
    assert feature.guardian_state is MonsterEngagementState.MERCENARY
    assert result.guardian_intimidated is True


# -- Phase 274: Use_MI wired as a real Search Encounter Plan tactic ----


def _use_mi_request(feature_id: int, item_id: int, *following: Maneuver) -> SearchRequest:
    tactics = [SearchTactic(maneuver=Maneuver.USE_MI, sub_object=item_id)]
    tactics += [SearchTactic(maneuver=m) for m in following]
    return SearchRequest(feature_id=feature_id, unconfirmed_extra0=0, tactics=tactics)


def test_execute_search_use_mi_missing_item_falls_through_to_melee():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE))
    request = _use_mi_request(1, 999, Maneuver.MELEE)  # no such item in state.items

    with patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert mock_melee.called
    assert result.winner == "leader"


def test_execute_search_use_mi_item_not_owned_by_leader_falls_through_to_melee():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE))
    item = state.add_item(Treasure.WAND_CHARM, owner_leader_id=99, charges=3)  # somebody else's wand
    request = _use_mi_request(1, item.item_id, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert mock_melee.called
    assert item.charges == 3  # untouched -- never resolved as this leader's own item


def test_execute_search_use_mi_non_wand_category_falls_through_to_melee():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE))
    item = state.add_item(Treasure.ABILITY_MELEE, owner_leader_id=LEADER_ID)  # not a SPELL_WAND
    request = _use_mi_request(1, item.item_id, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert mock_melee.called
    assert result.winner == "leader"


def test_execute_search_use_mi_no_charges_left_falls_through_to_melee():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE))
    item = state.add_item(Treasure.WAND_CHARM, owner_leader_id=LEADER_ID, charges=0)
    request = _use_mi_request(1, item.item_id, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert mock_melee.called
    assert item.charges == 0


def test_execute_search_use_mi_wand_of_charm_is_automatically_successful_and_spends_a_charge():
    # [3.11]/[5.1]: a spell cast from a magic item is automatically
    # successful -- no resolve_personal_combat_spell_cast roll at all,
    # unlike a hand-cast Charm (see test_execute_search_cast_charm_*).
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE))
    item = state.add_item(Treasure.WAND_CHARM, owner_leader_id=LEADER_ID, charges=3)
    request = _use_mi_request(1, item.item_id, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast") as mock_roll, patch(
        "ak_engine.turn.search_execution.resolve_melee_duel"
    ) as mock_melee:
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert not mock_roll.called  # automatic success -- the real roll is never even consulted
    assert not mock_melee.called  # Charm's own success ends the Search in a guaranteed Flee
    assert result.fled is True
    assert item.charges == 2


def test_execute_search_use_mi_wand_of_charm_ignores_the_casters_own_real_skill_level():
    # TREASAB.X2: every wand casts "at skill-2" regardless of the
    # caster's real Psychic level -- an unskilled leader (level 0) still
    # gets a fully-successful, automatic cast.
    state = _state_with_leader()  # skills=None -- level 0 in every ability
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE))
    item = state.add_item(Treasure.WAND_CHARM, owner_leader_id=LEADER_ID, charges=1)
    request = _use_mi_request(1, item.item_id, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_melee:
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert not mock_melee.called
    assert result.fled is True
    assert item.charges == 0


def test_execute_search_use_mi_wand_holding_an_unmodeled_spell_is_a_no_effect_and_no_charge_spent():
    # Wand of Oratory: a real Treasure/Spell mapping, but Oratory isn't
    # one of the 13 Personal-Combat spells `_resolve_cast_tactic()`
    # models -- `cast_attempt_applied` stays False, so no charge is
    # spent (nothing was actually cast), same as Phase 141's own rule.
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE))
    item = state.add_item(Treasure.WAND_ORATORY, owner_leader_id=LEADER_ID, charges=3)
    request = _use_mi_request(1, item.item_id, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert mock_melee.called
    assert result.winner == "leader"
    assert item.charges == 3  # untouched


def test_execute_search_use_mi_wand_of_hand_of_death_kills_the_guardian_instantly():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE))
    item = state.add_item(Treasure.WAND_HAND_OF_DEATH, owner_leader_id=LEADER_ID, charges=1)
    request = _use_mi_request(1, item.item_id, Maneuver.MELEE)

    with patch(
        "ak_engine.turn.search_execution.resolve_hand_of_death_channel", return_value=EncounterCombatResult(winner="a", rounds=1)
    ), patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_melee:
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert not mock_melee.called
    assert result.combat_resolved is True
    assert result.winner == "leader"
    assert result.feature_looted is True
    assert item.charges == 0


# -- Phase 274: Scout wired as a real, always-last Search Encounter Plan tactic --


def _scout_request(feature_id: int, *tactics: Maneuver) -> SearchRequest:
    return SearchRequest(
        feature_id=feature_id, unconfirmed_extra0=0, tactics=[SearchTactic(maneuver=m) for m in tactics]
    )


def test_execute_search_no_scout_tactic_leaves_the_feature_undiscovered():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE))
    request = _scout_request(1, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert result.scout_orders_given == 0
    assert state.features[1].discovered_by_kingdom == {}


def test_execute_search_scout_counts_every_scout_tactic_in_the_plan():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE))
    request = _scout_request(1, Maneuver.MELEE, Maneuver.SCOUT, Maneuver.SCOUT)

    with patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    # PCOND.X2's own confirmed reading: >=2 Scout orders is this game's
    # explicit consent signal for a Power condition, recorded honestly
    # even though nothing yet consumes it.
    assert result.scout_orders_given == 2


def test_execute_search_scout_with_only_unnamed_tactics_is_genuinely_unresolved():
    # A bare Scout (or Cast/Beg/Say + Scout) matches neither [5.8]'s
    # guaranteed branch nor either of its two named exceptions (Steal,
    # Flee) -- no source gives a percentage for this case, so it must
    # have no effect at all, not a guessed-at reveal.
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE))
    request = _scout_request(1, Maneuver.SCOUT)

    result = execute_search(state, LEADER_ID, request, ScriptedRandom([0.5]))  # the monster's own hit_points roll

    assert result.scout_orders_given == 1
    assert state.features[1].discovered_by_kingdom == {}


def test_execute_search_scout_with_melee_in_plan_is_a_guaranteed_full_discovery():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE))
    request = _scout_request(1, Maneuver.MELEE, Maneuver.SCOUT)

    with patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        # The lone scripted value is consumed by the monster's own
        # hit_points roll at Combatant construction, not by Scout (the
        # Talk/Fulfill/Attacking branch is a guaranteed reveal, no roll).
        result = execute_search(state, LEADER_ID, request, ScriptedRandom([0.5]))

    assert result.scout_orders_given == 1
    assert state.features[1].discovery_level(1) == 3


def test_execute_search_scout_skipped_when_the_leader_dies_but_still_counted():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE))
    request = _scout_request(1, Maneuver.MELEE, Maneuver.SCOUT)

    with patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="b", rounds=1)  # the guardian wins
        result = execute_search(state, LEADER_ID, request, ScriptedRandom([0.5]))

    assert result.leader_killed is True
    assert result.scout_orders_given == 1  # still recorded -- see _apply_scout()'s own docstring
    assert state.features[1].discovered_by_kingdom == {}  # but no discovery -- a dead leader can't scout


def test_execute_search_scout_steal_only_partial_discovery_on_the_documented_33_percent_miss():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE))
    request = _scout_request(1, Maneuver.STEAL, Maneuver.SCOUT)

    with patch("ak_engine.turn.search_execution.resolve_steal_attempt", return_value=True), patch(
        "ak_engine.turn.search_execution.resolve_steal_monster_item_transfer", return_value=False
    ):
        # First value: the monster's own hit_points roll at Combatant
        # construction. Second: Scout's own roll, >= 0.67 -- the 33% miss.
        result = execute_search(state, LEADER_ID, request, ScriptedRandom([0.5, 0.9]))

    assert result.scout_orders_given == 1
    assert state.features[1].discovery_level(1) == 2  # told it's there, not what it does


def test_execute_search_scout_steal_only_full_discovery_on_the_documented_67_percent_hit():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE))
    request = _scout_request(1, Maneuver.STEAL, Maneuver.SCOUT)

    with patch("ak_engine.turn.search_execution.resolve_steal_attempt", return_value=True), patch(
        "ak_engine.turn.search_execution.resolve_steal_monster_item_transfer", return_value=False
    ):
        result = execute_search(state, LEADER_ID, request, ScriptedRandom([0.5, 0.1]))  # < 0.67 -- the 67% hit

    assert state.features[1].discovery_level(1) == 3


def test_execute_search_scout_flee_only_partial_discovery_on_the_documented_67_percent_miss():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE))
    request = _scout_request(1, Maneuver.FLEE, Maneuver.SCOUT)

    # First value: the monster's own hit_points roll. Second fails the
    # Flee roll (Gargoyle is MEDIUM speed, 50% chance -- 0.9 always
    # fails); third is Scout's own roll, >= 0.33 -- the rulebook's
    # documented 67% miss for Flee+Scout.
    result = execute_search(state, LEADER_ID, request, ScriptedRandom([0.5, 0.9, 0.9]))

    assert state.features[1].discovery_level(1) == 2


def test_execute_search_scout_flee_only_full_discovery_on_the_documented_33_percent_hit():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE))
    request = _scout_request(1, Maneuver.FLEE, Maneuver.SCOUT)

    result = execute_search(state, LEADER_ID, request, ScriptedRandom([0.5, 0.9, 0.1]))  # < 0.33 -- the 33% hit

    assert state.features[1].discovery_level(1) == 3


def test_execute_search_scout_never_downgrades_an_already_fully_known_feature():
    state = _state_with_leader()
    feature = Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE)
    feature.discovered_by_kingdom[1] = 3  # already fully known from an earlier Search
    state.add_feature(feature)
    request = _scout_request(1, Maneuver.STEAL, Maneuver.SCOUT)

    with patch("ak_engine.turn.search_execution.resolve_steal_attempt", return_value=True), patch(
        "ak_engine.turn.search_execution.resolve_steal_monster_item_transfer", return_value=False
    ):
        execute_search(state, LEADER_ID, request, ScriptedRandom([0.5, 0.9]))  # the 33% miss

    assert feature.discovery_level(1) == 3  # a failed re-scout never downgrades a known feature


def test_execute_search_scout_kingdomless_leader_is_a_no_effect():
    state = GameState()
    state.add_leader(LeaderState(LEADER_ID, kingdom_id=None, name="Independent", location=LOCATION))
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE))
    request = _scout_request(1, Maneuver.MELEE, Maneuver.SCOUT)

    with patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        result = execute_search(state, LEADER_ID, request, ScriptedRandom([0.5]))

    assert result.scout_orders_given == 1


# -- Phase 616: Feature -> Power [5.8] wired into a full Scout discovery --


def test_execute_search_scout_full_discovery_applies_a_tractable_feature_power():
    # F#5 (`Special Features.md` section 8, user-supplied 2026-08-22):
    # province 301 (x=3,...), Temple -> Up Skill/ME, Drain Courage. Only
    # `coord.x` feeds the derivation (see `derive_feature_event()`), so
    # `y` is set to `LOCATION`'s own 9 to satisfy this project's
    # co-location requirement without changing which power derives.
    state = _state_with_leader(skills=SkillTable(raw_values=[0] * 30), temper=Temper.BRAVE)
    state.add_feature(
        Feature(feature_id=5, coord=LOCATION, kind=FeatureType.TEMPLE, guardian_monster=Monster.GARGOYLE)
    )
    # Phase 688: 2 Scout orders are the real PCOND.X2 consent signal for
    # this power's own DRAIN_COURAGE condition -- without them, the real
    # gate now refuses the attempt outright (a coverage gap this test
    # used to have: it never checked `.applied`, so it kept passing green
    # even when the underlying effect silently stopped firing).
    request = _scout_request(5, Maneuver.MELEE, Maneuver.SCOUT, Maneuver.SCOUT)

    with patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert state.features[5].discovery_level(1) == 3
    assert result.feature_power_outcome is not None
    assert result.feature_power_outcome.power is Power.UP_SKILL
    # UP_SKILL's own roll is genuinely probabilistic (skill=0, aptitude=0
    # here -> 50/50) -- this only proves the real Scout-consent gate was
    # satisfied (2 Scout orders given), not a specific roll outcome.
    assert result.feature_power_outcome.reason != "needs two Scout orders to accept these terms"
    assert state.leaders[LEADER_ID].temper is Temper.CAUTIOUS  # DRAIN_COURAGE's own real cost, BRAVE -1 step


def test_execute_search_scout_full_discovery_leaves_a_powerless_feature_unapplied():
    # F#0: Pyramid at x=3 -> Power.PNONE (no power at all, the ~55% of
    # real Features with none, see resolve_visible_location()'s own
    # docstring) -- so no outcome is recorded here. As of Phase 623
    # every real (non-PNONE) `Power` is wired -- F#171/Pyramid (`MAP_
    # PROV`) and F#29/Pyramid (`Chance`) were this test's own "still
    # unwired" examples through Phase 622, but neither one still
    # qualifies now that both are tractable.
    state = _state_with_leader()
    state.add_feature(
        Feature(feature_id=0, coord=LOCATION, kind=FeatureType.PYRAMID, guardian_monster=Monster.GARGOYLE)
    )
    request = _scout_request(0, Maneuver.MELEE, Maneuver.SCOUT)

    with patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        result = execute_search(state, LEADER_ID, request, ScriptedRandom([0.5]))

    assert state.features[0].discovery_level(1) == 3
    assert result.feature_power_outcome is None


def test_execute_search_scout_cast_spell_unresolved_terrain_is_a_real_not_none_outcome():
    # F#17: Crypt at x=3 -> Cast Spell (Phase 620), but its own province
    # is unknown to `state.provinces` here, so `spell_parameter` can't
    # be resolved -- a real "power not yet wired" outcome, not silently
    # dropped like a fully-untouched power (see the CHANCE test above).
    state = _state_with_leader()
    state.add_feature(
        Feature(feature_id=17, coord=LOCATION, kind=FeatureType.CRYPT, guardian_monster=Monster.GARGOYLE)
    )
    request = _scout_request(17, Maneuver.MELEE, Maneuver.SCOUT)

    with patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        result = execute_search(state, LEADER_ID, request, ScriptedRandom([0.5]))

    assert result.feature_power_outcome is not None
    assert result.feature_power_outcome.power is Power.CAST_SPELL
    assert result.feature_power_outcome.applied is False


def test_execute_search_scout_cast_spell_success_casts_flood_on_the_provinces_own_terrain():
    # F#7: Tomb at x=3 -> Cast Spell / Flood (Phase 620). Plains is a
    # real Flood-eligible terrain, so the automatic-success cast really
    # turns it into Sea.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, LOCATION, treasury=100))
    state.add_leader(LeaderState(LEADER_ID, 1, "Searcher", LOCATION))
    state.provinces[LOCATION] = ProvinceState(coord=LOCATION, terrain=Terrain.PLAINS, race=Race.HUMAN)
    state.add_feature(
        Feature(feature_id=7, coord=LOCATION, kind=FeatureType.TOMB, guardian_monster=Monster.GARGOYLE)
    )
    # Phase 688: 2 Scout orders are the real PCOND.X2 consent signal for
    # this power's own PAY_UP condition.
    request = _scout_request(7, Maneuver.MELEE, Maneuver.SCOUT, Maneuver.SCOUT)

    with patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert result.feature_power_outcome is not None
    assert result.feature_power_outcome.applied is True
    assert result.feature_power_outcome.cast_spell is Spell.FLOOD
    assert state.provinces[LOCATION].effective_terrain() is Terrain.SEA


def test_execute_search_scout_cast_spell_success_casts_oratory_on_the_scouting_leader():
    # F#13: Pyramid at x=3 -> Cast Spell / Oratory (Phase 621 -- only
    # resolvable now that `Set_Spell`'s full 13-candidate table is
    # wired, gated on `GameState.miscwrit`'s own real default). Oratory
    # is character-targeted, not province-targeted -- this proves the
    # Phase 621 target-resolution fix reaches the scouting leader
    # himself (rulebook [4.22.2]'s own "cast on yourself"), not the
    # Feature's province.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, LOCATION, treasury=100))
    state.add_leader(LeaderState(LEADER_ID, 1, "Searcher", LOCATION))
    state.provinces[LOCATION] = ProvinceState(coord=LOCATION, terrain=Terrain.PLAINS, race=Race.HUMAN)
    state.add_army(
        ArmyState(army_id=1, kingdom_id=1, army_type=ArmyType.BOWMEN, quality=Quality.AVERAGE, location=LOCATION, commanded_by=LEADER_ID)
    )
    state.add_feature(
        Feature(feature_id=13, coord=LOCATION, kind=FeatureType.PYRAMID, guardian_monster=Monster.GARGOYLE)
    )
    # Phase 688: 2 Scout orders are the real PCOND.X2 consent signal for
    # this power's own PAY_UP condition.
    request = _scout_request(13, Maneuver.MELEE, Maneuver.SCOUT, Maneuver.SCOUT)

    with patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert result.feature_power_outcome is not None
    assert result.feature_power_outcome.applied is True
    assert result.feature_power_outcome.cast_spell is Spell.ORATORY
    assert state.armies[1].quality is Quality.VETERAN


def test_execute_search_scout_chance_resolves_and_applies_a_real_sub_power():
    # F#29: Pyramid at x=3 -> Chance (Phase 622 -- previously this
    # project's own "still entirely unhandled" example, see the
    # repointed non-tractable-power test above). gameturn=1, gdday=7 ->
    # (1+7) AND 7 = 0 -> NewSex, a deterministic sub-power (no success
    # roll) that proves the outcome is stamped with the *sub*-power
    # (Power.NEW_SEX), not Power.CHANCE.
    state = GameState(turn_number=1, gdday=7)
    state.add_leader(LeaderState(LEADER_ID, 1, "Searcher", LOCATION, sex=Sex.MALE))
    state.add_feature(
        Feature(feature_id=29, coord=LOCATION, kind=FeatureType.PYRAMID, guardian_monster=Monster.GARGOYLE)
    )
    request = _scout_request(29, Maneuver.MELEE, Maneuver.SCOUT)

    with patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert result.feature_power_outcome is not None
    assert result.feature_power_outcome.applied is True
    assert result.feature_power_outcome.power is Power.NEW_SEX
    assert state.leaders[LEADER_ID].sex is Sex.FEMALE


def test_execute_search_scout_map_prov_reveals_unknown_provinces():
    # F#171: Pyramid at x=3 -> Map Province (Phase 623 -- "known
    # provinces" now exists, so this previously-dropped power is
    # tractable). A handful of real, still-unknown provinces are
    # available to reveal (3-5 of them, per Special Features.md's own
    # sourced `3 + IRand MOD 3`).
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, LOCATION, treasury=100))
    state.add_leader(LeaderState(LEADER_ID, 1, "Searcher", LOCATION))
    for x in range(10):
        coord = HexCoord(x, 0)
        state.provinces[coord] = ProvinceState(coord=coord, terrain=Terrain.PLAINS, race=Race.HUMAN)
    state.add_feature(
        Feature(feature_id=171, coord=LOCATION, kind=FeatureType.PYRAMID, guardian_monster=Monster.GARGOYLE)
    )
    # Phase 688: 2 Scout orders are the real PCOND.X2 consent signal for
    # this power's own PAY_UP condition.
    request = _scout_request(171, Maneuver.MELEE, Maneuver.SCOUT, Maneuver.SCOUT)

    with patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        result = execute_search(state, LEADER_ID, request, random.Random(0))

    assert result.feature_power_outcome is not None
    assert result.feature_power_outcome.applied is True
    assert result.feature_power_outcome.power is Power.MAP_PROV
    assert 3 <= len(result.feature_power_outcome.revealed_province_coords) <= 5
    for coord in result.feature_power_outcome.revealed_province_coords:
        assert state.provinces[coord].known_to_kingdom(1) is True


# -- Phase 617: DAMP_COLLEGE/DAMP_MAGIC/WARP_SPACE, the 3 passive battle-
# field powers -- always live for whoever fights at that Feature,
# independent of Scout (unlike Phase 616's own TRACTABLE_POWERS).


def test_execute_search_warp_space_halves_the_melee_hit_chance_for_both_sides():
    # F#57 (real formula output, `derive_feature_event()`): Dungeon at
    # x=3 (matching LOCATION) -> Warp Space.
    state = _state_with_leader()
    state.add_feature(
        Feature(feature_id=57, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE)
    )
    request = _melee_request(57)

    with patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_search(state, LEADER_ID, request, ScriptedRandom([0.5]))

    leader_combatant, monster_combatant = mock_melee.call_args[0][0], mock_melee.call_args[0][1]
    assert leader_combatant.offensive_hit_multiplier == 0.5
    assert monster_combatant.offensive_hit_multiplier == 0.5
    assert leader_combatant.archery_hit_multiplier == 0.25
    assert monster_combatant.archery_hit_multiplier == 0.25


def test_execute_search_no_warp_space_leaves_hit_multipliers_untouched():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE))
    request = _melee_request(1)

    with patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_search(state, LEADER_ID, request, ScriptedRandom([0.5]))

    leader_combatant = mock_melee.call_args[0][0]
    assert leader_combatant.offensive_hit_multiplier == 1.0
    assert leader_combatant.archery_hit_multiplier == 1.0


def test_execute_search_damp_college_blocks_casting_the_matching_school():
    # F#137: Dungeon at x=3 -> Damp College / Illusion. Invisibility is
    # an Illusion spell (PERSONAL_COMBAT_SPELL_ABILITY) -- should be
    # blocked outright, never reaching the cast-success roll.
    leader = _skilled_leader(Ability.ILLUSION, 5)
    state = GameState()
    state.add_leader(leader)
    state.add_feature(
        Feature(feature_id=137, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE)
    )
    request = _cast_request(137, Spell.INVISIBILITY, Maneuver.MELEE)

    with patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast") as mock_cast_roll, patch(
        "ak_engine.turn.search_execution.resolve_melee_duel"
    ) as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_search(state, LEADER_ID, request, random.Random(0))

    assert not mock_cast_roll.called
    assert mock_melee.called  # the blocked Cast falls through, Melee still resolves


def test_execute_search_damp_college_does_not_block_a_different_school():
    # Same Feature as above (Illusion blocked), but casting a White
    # Magic spell (Holy Symbol) should reach the roll normally.
    leader = _skilled_leader(Ability.WHITE, 5)
    state = GameState()
    state.add_leader(leader)
    state.add_feature(
        Feature(feature_id=137, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE)
    )
    request = _cast_request(137, Spell.HOLY_SYMBOL, Maneuver.MELEE)

    with patch(
        "ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=False
    ) as mock_cast_roll, patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_search(state, LEADER_ID, request, random.Random(0))

    mock_cast_roll.assert_called_once()
    assert mock_cast_roll.call_args.kwargs["damp_magic"] is False


def test_execute_search_damp_magic_halves_the_cast_success_chance():
    # F#51: Tomb at x=3 -> Damp Magic (halves every spell's own chance).
    leader = _skilled_leader(Ability.WHITE, 5)
    state = GameState()
    state.add_leader(leader)
    state.add_feature(Feature(feature_id=51, coord=LOCATION, kind=FeatureType.TOMB, guardian_monster=Monster.GARGOYLE))
    request = _cast_request(51, Spell.HOLY_SYMBOL, Maneuver.MELEE)

    with patch(
        "ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=False
    ) as mock_cast_roll, patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        execute_search(state, LEADER_ID, request, random.Random(0))

    mock_cast_roll.assert_called_once()
    assert mock_cast_roll.call_args.kwargs["damp_magic"] is True


# -- Phase 619: the 8 SA-argument powers -- _apply_scout() finds and
# parses a real SAY tactic's own argument end to end.


def test_execute_search_scout_finds_and_parses_the_say_tactics_own_argument():
    # F#7: Dungeon at x=3 -> Gamble, PC_NONE condition (no extra gating
    # to work around). SearchTactic(say_text=...) stands in directly for
    # what turn/search_decode.py's own Phase 618 SAY recovery already
    # produces from a real move file.
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, LOCATION, treasury=100))
    state.add_leader(LeaderState(LEADER_ID, 1, "King Testerman", LOCATION, is_king=True))
    state.add_feature(Feature(feature_id=7, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE))
    request = SearchRequest(
        feature_id=7,
        unconfirmed_extra0=0,
        tactics=[
            SearchTactic(maneuver=Maneuver.MELEE),
            SearchTactic(maneuver=Maneuver.SAY, say_text="10"),
            SearchTactic(maneuver=Maneuver.SCOUT),
        ],
    )

    with patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        result = execute_search(state, LEADER_ID, request, random.Random(1))

    assert result.feature_power_outcome is not None
    assert result.feature_power_outcome.power is Power.GAMBLE
    assert result.feature_power_outcome.applied is True
    assert result.feature_power_outcome.gamble_amount == 10


def test_execute_search_scout_with_no_say_tactic_refuses_the_sa_argument_power():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.NEUTRAL, LOCATION, treasury=100))
    state.add_leader(LeaderState(LEADER_ID, 1, "King Testerman", LOCATION, is_king=True))
    state.add_feature(Feature(feature_id=7, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE))
    request = _scout_request(7, Maneuver.MELEE, Maneuver.SCOUT)

    with patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_melee:
        mock_melee.return_value = EncounterCombatResult(winner="a", rounds=1)
        result = execute_search(state, LEADER_ID, request, random.Random(1))

    assert result.feature_power_outcome is not None
    assert result.feature_power_outcome.applied is False
    assert result.feature_power_outcome.reason == "no SA argument given"


# -- Phase 293: bidirectional round-per-round engine ---------------------


def test_execute_search_melee_uses_atomic_fast_path_when_guardian_has_nothing_left_to_interleave():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE))
    request = _melee_request(1)

    with patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_duel, patch(
        "ak_engine.turn.search_execution.resolve_one_melee_round"
    ) as mock_round:
        mock_duel.return_value = EncounterCombatResult(winner="a", rounds=1)
        result = execute_search(state, LEADER_ID, request, ScriptedRandom([0.5]))

    assert mock_duel.called
    assert not mock_round.called
    assert result.winner == "leader"


def test_execute_search_melee_round_steps_when_guardian_has_a_cast_pending_beyond_its_first_melee():
    # Mirrors Dryad's/Mermaid's own real "MELEE, MELEE, ..., CAST, MELEE"
    # shape (models/monster_encounter_plan.py) -- the guardian's own
    # immediate next action is Melee, but a real Cast is scheduled a
    # round later; the fast path must not fire just because the
    # guardian's own *very first* action happens to be Melee.
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE))
    request = _melee_request(1)
    monster_plan = (
        SearchTactic(maneuver=Maneuver.MELEE),
        SearchTactic(maneuver=Maneuver.CAST, sub_object=Spell.FIREBALL.value),
    )

    with patch("ak_engine.turn.search_execution.roll_monster_encounter_plan", return_value=monster_plan), patch(
        "ak_engine.turn.search_execution.resolve_melee_duel"
    ) as mock_duel, patch("ak_engine.turn.search_execution.resolve_one_melee_round") as mock_round, patch(
        "ak_engine.turn.search_execution.resolve_reactive_melee_swing",
        return_value=ReactiveMeleeSwingResult(hit=False, damage=0),
    ), patch(
        "ak_engine.turn.search_execution.resolve_spell_disruption_from_missed_attack", return_value=False
    ), patch(
        "ak_engine.turn.search_execution.resolve_personal_combat_spell_cast", return_value=True
    ) as mock_cast, patch("ak_engine.turn.search_execution.roll_fireball_damage", return_value=999):
        mock_round.return_value = MeleeRoundOutcome(result=None)
        execute_search(state, LEADER_ID, request, ScriptedRandom([0.5]))

    assert not mock_duel.called
    assert mock_round.called
    assert mock_cast.called  # the guardian's own later Cast was genuinely attempted


def test_execute_search_guardians_own_cast_disrupted_by_a_landed_swing_never_attempts_the_cast():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE))
    request = _melee_request(1)
    monster_plan = (
        SearchTactic(maneuver=Maneuver.MELEE),
        SearchTactic(maneuver=Maneuver.CAST, sub_object=Spell.FIREBALL.value),
    )

    with patch("ak_engine.turn.search_execution.roll_monster_encounter_plan", return_value=monster_plan), patch(
        "ak_engine.turn.search_execution.resolve_one_melee_round"
    ) as mock_round, patch(
        "ak_engine.turn.search_execution.resolve_reactive_melee_swing",
        return_value=ReactiveMeleeSwingResult(hit=True, damage=5),
    ) as mock_swing, patch(
        "ak_engine.turn.search_execution.resolve_spell_disruption", return_value=True
    ) as mock_disrupt, patch(
        "ak_engine.turn.search_execution.resolve_spell_disruption_from_missed_attack"
    ) as mock_miss_disrupt, patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast") as mock_cast:
        # First call: the guardian's own opening Melee round (undecided,
        # advancing it to its own Cast tactic). Second call, if ever
        # reached again after its plan is fully exhausted, is decisive --
        # guards against an infinite loop, since this mock never actually
        # reduces either side's real hit points on its own.
        mock_round.side_effect = [
            MeleeRoundOutcome(result=None),
            MeleeRoundOutcome(result=EncounterCombatResult(winner="a", rounds=2)),
        ]
        # Phase 686: 2 extra scripted values beyond the original single
        # 0.5 -- the leader's own landed reactive swing (mocked hit=True
        # above) now also fires add_experience()'s own triangular draw.
        result = execute_search(state, LEADER_ID, request, ScriptedRandom([0.5, 0.5, 0.5]))

    assert mock_swing.called
    assert mock_disrupt.called
    assert not mock_miss_disrupt.called  # a landed hit uses the damage-scaled formula, not the flat-miss one
    assert not mock_cast.called  # disrupted -- "the caster loses a turn," no cast-chance roll at all
    # Phase 416: the leader's own reactive swing (attacker="a") is narrated
    # even though the cast it disrupted never reached _resolve_cast().
    assert result.melee_swings == (MeleeSwing(attacker="a", hit=True, damage=5),)


def test_execute_search_guardians_own_cast_disrupted_by_a_missed_swing_uses_the_flat_30_percent():
    state = _state_with_leader()
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE))
    request = _melee_request(1)
    monster_plan = (
        SearchTactic(maneuver=Maneuver.MELEE),
        SearchTactic(maneuver=Maneuver.CAST, sub_object=Spell.FIREBALL.value),
    )

    with patch("ak_engine.turn.search_execution.roll_monster_encounter_plan", return_value=monster_plan), patch(
        "ak_engine.turn.search_execution.resolve_one_melee_round"
    ) as mock_round, patch(
        "ak_engine.turn.search_execution.resolve_reactive_melee_swing",
        return_value=ReactiveMeleeSwingResult(hit=False, damage=0),
    ), patch("ak_engine.turn.search_execution.resolve_spell_disruption") as mock_damage_disrupt, patch(
        "ak_engine.turn.search_execution.resolve_spell_disruption_from_missed_attack", return_value=True
    ) as mock_miss_disrupt, patch("ak_engine.turn.search_execution.resolve_personal_combat_spell_cast") as mock_cast:
        mock_round.side_effect = [
            MeleeRoundOutcome(result=None),
            MeleeRoundOutcome(result=EncounterCombatResult(winner="a", rounds=2)),
        ]
        execute_search(state, LEADER_ID, request, ScriptedRandom([0.5]))

    assert mock_miss_disrupt.called
    assert not mock_damage_disrupt.called  # a miss uses the flat 30%, not the damage-scaled formula
    assert not mock_cast.called


def test_execute_search_leaders_own_cast_after_a_non_last_melee_tactic_can_be_disrupted():
    # The leader's own MELEE followed by a real CAST -- a genuinely new
    # plan shape (no pre-Phase-293 caller ever ordered these this way)
    # that must trigger round-stepping regardless of the guardian's own
    # (here, trivial single-Melee) plan.
    raw = [0] * 30
    raw[Ability.ELEMENTAL.value * 2] = 4
    raw[Ability.ELEMENTAL.value * 2 + 1] = 9
    state = _state_with_leader(skills=SkillTable(raw_values=raw))
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE))
    request = SearchRequest(
        feature_id=1,
        unconfirmed_extra0=0,
        tactics=[
            SearchTactic(maneuver=Maneuver.MELEE),
            SearchTactic(maneuver=Maneuver.CAST, sub_object=Spell.FIREBALL.value),
        ],
    )

    with patch("ak_engine.turn.search_execution.resolve_one_melee_round") as mock_round, patch(
        "ak_engine.turn.search_execution.resolve_reactive_melee_swing",
        return_value=ReactiveMeleeSwingResult(hit=True, damage=5),
    ) as mock_swing, patch(
        "ak_engine.turn.search_execution.resolve_spell_disruption", return_value=True
    ) as mock_disrupt, patch(
        "ak_engine.turn.search_execution.resolve_personal_combat_spell_cast"
    ) as mock_cast, patch("ak_engine.turn.search_execution.resolve_melee_duel") as mock_duel:
        mock_round.return_value = MeleeRoundOutcome(result=None)
        mock_duel.return_value = EncounterCombatResult(winner=None, rounds=1)
        result = execute_search(state, LEADER_ID, request, ScriptedRandom([0.5]))

    assert mock_swing.called
    assert mock_disrupt.called
    assert not mock_cast.called
    assert state.features[1].discovered_by_kingdom == {}  # nowhere to record it
    # Phase 416: the guardian's own reactive swing (attacker="b", since
    # this branch is "monster swings while the leader casts") is narrated.
    assert MeleeSwing(attacker="b", hit=True, damage=5) in result.melee_swings


# -- Phase 297: exhausted-fallback's own resolve_melee_duel() must not
# double-apply Temper setup after an earlier non-last MELEE already ran it --


def test_execute_search_non_last_melee_trailing_fallback_skips_temper_setup_already_applied():
    # Same real bug as turn/challenge_execution.py's own identical Phase
    # 297 fix, found in a dedicated bug-hunt audit: a MELEE tactic that
    # isn't last (round-stepping applies real Temper setup once) followed
    # by an unwired/no-op tactic (SAY) falls through to the exhausted-
    # tactic-list fallback, whose own resolve_melee_duel() call must
    # skip re-applying setup a second time.
    state = _state_with_leader(temper=Temper.CAUTIOUS)
    state.add_feature(Feature(feature_id=1, coord=LOCATION, kind=FeatureType.DUNGEON, guardian_monster=Monster.GARGOYLE))
    request = SearchRequest(
        feature_id=1,
        unconfirmed_extra0=0,
        tactics=[SearchTactic(maneuver=Maneuver.MELEE), SearchTactic(maneuver=Maneuver.SAY)],
    )

    with patch(
        "ak_engine.turn.search_execution.roll_monster_encounter_plan", return_value=(SearchTactic(Maneuver.MELEE),)
    ), patch("ak_engine.turn.search_execution.resolve_one_melee_round") as mock_round, patch(
        "ak_engine.turn.search_execution.resolve_melee_duel"
    ) as mock_duel:
        mock_round.return_value = MeleeRoundOutcome(result=None)
        mock_duel.return_value = EncounterCombatResult(winner=None, rounds=1)
        execute_search(state, LEADER_ID, request, ScriptedRandom([0.5]))

    assert mock_duel.call_args.kwargs["skip_temper_setup"] is True
