from __future__ import annotations

from ak_engine.models.advanced_ability import AdvancedAbility
from ak_engine.models.alignment import Alignment
from ak_engine.models.army_naming import make_army_name
from ak_engine.models.army_type import ArmyType
from ak_engine.models.discovery import Discovery
from ak_engine.models.enums import Ability
from ak_engine.models.feature import Feature, FeatureType
from ak_engine.models.game_state import ArmyState, GameState, KingdomState, LeaderState, ProvinceState
from ak_engine.models.kingdom import SkillTable
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.race import Race
from ak_engine.models.temper import Temper
from ak_engine.turn.aspy_defend_decode import SpyProvinceRequest
from ak_engine.turn.aspy_execution import (
    ESPIONAGE_DISCOVERY_CHANCE_MULTIPLIER,
    SpottedCharacter,
    SpyReport,
    _roll_espionage_discoveries,
    execute_aspy,
)
from ak_engine.turn.combat import Quality

from _helpers import ScriptedRandom

LEADER_ID = 1
HOME = HexCoord(3, 9)


def _state(*, owner_kingdom_id: int | None = 1, home_province: HexCoord = HOME, leader_location: HexCoord = HOME) -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.GOOD, home_province))
    state.add_province(ProvinceState(leader_location, Terrain.PLAINS, Race.HUMAN, owner_kingdom_id=owner_kingdom_id))
    state.add_leader(LeaderState(LEADER_ID, 1, "Test Leader", leader_location))
    return state


def _request() -> SpyProvinceRequest:
    # obj is deliberately never trusted by execute_aspy -- see module
    # docstring -- so any value here should have no effect on the result.
    return SpyProvinceRequest(target_province=9999, unconfirmed_extra0=0)


def test_execute_aspy_reports_the_casters_own_province_and_owner():
    state = _state()
    report = execute_aspy(state, LEADER_ID, _request())

    assert isinstance(report, SpyReport)
    assert report.province == HOME
    assert report.owner_kingdom_id == 1


def test_execute_aspy_ignores_the_raw_target_province_field():
    state = _state(leader_location=HexCoord(5, 5), home_province=HexCoord(5, 5))
    report = execute_aspy(state, LEADER_ID, SpyProvinceRequest(target_province=1, unconfirmed_extra0=0))

    assert report.province == HexCoord(5, 5)


def test_execute_aspy_reports_none_owner_for_an_unowned_province():
    state = _state(owner_kingdom_id=None)
    report = execute_aspy(state, LEADER_ID, _request())

    assert report.owner_kingdom_id is None
    assert report.is_capital is False


def test_execute_aspy_reports_adjacent_province_owners():
    state = _state()
    neighbor = HexCoord(4, 9)  # adjacent to (3, 9) on the odd-r grid
    state.add_province(ProvinceState(neighbor, Terrain.FOREST, Race.ELVEN, owner_kingdom_id=2))

    report = execute_aspy(state, LEADER_ID, _request())

    assert report.adjacent_owners == {neighbor: 2}


def test_execute_aspy_omits_unknown_neighboring_hexes():
    # Only (3, 9)'s own province is registered -- every neighboring hex is
    # unknown to this GameState, so adjacent_owners stays empty rather than
    # guessing.
    state = _state()
    report = execute_aspy(state, LEADER_ID, _request())

    assert report.adjacent_owners == {}


def test_execute_aspy_reports_recruitable_army_types_for_the_provinces_race():
    state = _state()
    report = execute_aspy(state, LEADER_ID, _request())

    assert ArmyType.BOWMEN in report.recruitable_army_types
    assert ArmyType.TROLLS not in report.recruitable_army_types  # Race.HUMAN isn't a monstrous race


def test_execute_aspy_reports_the_provinces_tax_estimate_unperturbed_at_zero_offset():
    # Phase 265: tax_estimate is now perturbed by the caster's own
    # Spy-skill margin of error -- scripted rng.random()=0.5 lands the
    # uniform(-margin, margin) offset at exactly 0, keeping this the
    # simplest possible assertion (no margin-of-error math needed).
    state = _state()
    state.provinces[HOME].tax = 5
    report = execute_aspy(state, LEADER_ID, _request(), rng=ScriptedRandom([0.5, 0.5, 0.5]))

    assert report.tax_estimate == 5


def test_execute_aspy_tax_estimate_is_perturbed_at_zero_spy_skill():
    # No leader.skills recorded -> spy skill 0 -> the widest margin
    # (70%). rng.random()=1.0 pushes the offset to its maximum (+70%).
    state = _state()
    state.provinces[HOME].tax = 10
    report = execute_aspy(state, LEADER_ID, _request(), rng=ScriptedRandom([1.0, 0.5, 0.5]))

    assert report.tax_estimate == 17  # round(10 * 1.70)


def test_execute_aspy_tax_estimate_margin_shrinks_with_spy_skill():
    # Spy skill 4 -> the narrowest margin (15%), same rng.random()=1.0
    # (maximum offset) as the skill-0 case above, for a direct contrast.
    state = _state()
    state.provinces[HOME].tax = 10
    state.leaders[LEADER_ID].skills = SkillTable(
        [0] * (Ability.SPY.value * 2) + [4, 6] + [0] * (30 - Ability.SPY.value * 2 - 2)
    )

    report = execute_aspy(state, LEADER_ID, _request(), rng=ScriptedRandom([1.0, 0.5, 0.5]))

    assert report.tax_estimate == 12  # round(10 * 1.15)


def test_execute_aspy_tax_estimate_floors_at_zero():
    state = _state()
    state.provinces[HOME].tax = 1
    report = execute_aspy(
        state, LEADER_ID, _request(), rng=ScriptedRandom([0.0, 0.5, 0.5])
    )  # maximum negative offset

    assert report.tax_estimate == 0


def test_execute_aspy_reports_none_tax_estimate_when_never_recorded():
    state = _state()  # ProvinceState.tax defaults to None
    report = execute_aspy(state, LEADER_ID, _request(), rng=ScriptedRandom([0.5, 0.5]))

    assert report.tax_estimate is None


def test_execute_aspy_reports_is_capital_true_at_the_kingdoms_home_province():
    state = _state(home_province=HOME, leader_location=HOME)
    report = execute_aspy(state, LEADER_ID, _request())

    assert report.is_capital is True


def test_execute_aspy_reports_is_capital_false_away_from_home():
    state = _state(home_province=HexCoord(0, 0), leader_location=HOME)
    report = execute_aspy(state, LEADER_ID, _request())

    assert report.is_capital is False


def test_execute_aspy_returns_none_when_the_casters_province_is_unknown():
    state = GameState()
    state.add_kingdom(KingdomState(1, "Testia", Race.HUMAN, Alignment.GOOD, HOME))
    state.add_leader(LeaderState(LEADER_ID, 1, "Test Leader", HOME))
    # No ProvinceState registered at HOME.

    assert execute_aspy(state, LEADER_ID, _request()) is None


# --- Phase 139: spotted_characters (Align_Est/Temper_Est consumer) ---


def test_execute_aspy_omits_the_caster_itself_from_spotted_characters():
    state = _state()
    report = execute_aspy(state, LEADER_ID, _request())

    assert report.spotted_characters == []


def test_execute_aspy_spots_a_co_located_leader():
    state = _state()
    state.add_leader(LeaderState(2, 1, "Rival", HOME, temper=Temper.BRAVE))

    report = execute_aspy(state, LEADER_ID, _request())

    assert len(report.spotted_characters) == 1
    spotted = report.spotted_characters[0]
    assert isinstance(spotted, SpottedCharacter)
    assert spotted.leader_id == 2
    assert spotted.name == "Rival"


def test_execute_aspy_does_not_spot_leaders_in_other_provinces():
    state = _state()
    state.add_leader(LeaderState(2, 1, "Elsewhere", HexCoord(0, 0), temper=Temper.BRAVE))

    report = execute_aspy(state, LEADER_ID, _request())

    assert report.spotted_characters == []


def test_execute_aspy_reports_true_alignment_and_temper_for_a_psychic_mage_caster():
    state = _state()
    state.add_leader(LeaderState(2, 1, "Rival", HOME, temper=Temper.BRAVE))

    report = execute_aspy(state, LEADER_ID, _request(), caster_holds_psychic_mage_office=True)

    spotted = report.spotted_characters[0]
    assert spotted.estimated_alignment == Alignment.GOOD  # Testia's own KingdomState.alignment
    assert spotted.estimated_temper == Temper.BRAVE


def test_execute_aspy_detect_align_talent_perfects_alignment_only():
    state = _state()
    # Caster's own birth_x=3 (odd parity) vs spotted leader_id=2 (even
    # parity) forces a real nudge in estimate_temper() -- proving
    # caster_has_detect_align alone grants the perfect *alignment* path
    # without also perfecting temper (the real Pascal source gives temper
    # detection no advanced-ability bypass at all; see
    # turn/intelligence_estimate.py's _nudge()).
    state.leaders[LEADER_ID].birth_x = 3
    state.add_leader(LeaderState(2, 1, "Rival", HOME, temper=Temper.BRAVE))

    report = execute_aspy(state, LEADER_ID, _request(), caster_has_detect_align=True)

    spotted = report.spotted_characters[0]
    assert spotted.estimated_alignment == Alignment.GOOD
    assert spotted.estimated_temper == Temper.CAUTIOUS  # BRAVE nudged down one step


def test_execute_aspy_estimates_alignment_imperfectly_by_default():
    state = _state()
    # Testia's alignment is GOOD (ordinal 1). spotted.leader_id=2 (even
    # parity) vs caster LEADER_ID=1 (odd parity) nudges the ordinal down
    # by one to DIVINE (ordinal 0) per turn/intelligence_estimate.py's
    # _nudge() formula.
    state.add_leader(LeaderState(2, 1, "Rival", HOME))

    report = execute_aspy(state, LEADER_ID, _request())

    assert report.spotted_characters[0].estimated_alignment == Alignment.DIVINE


def test_execute_aspy_reports_none_alignment_for_an_independent_hero():
    state = _state()
    state.add_leader(LeaderState(2, None, "Wandering Hero", HOME, temper=Temper.BRAVE))

    report = execute_aspy(state, LEADER_ID, _request(), caster_holds_psychic_mage_office=True)

    spotted = report.spotted_characters[0]
    assert spotted.estimated_alignment is None
    assert spotted.estimated_temper == Temper.BRAVE


def test_execute_aspy_reports_none_temper_when_not_recorded():
    state = _state()
    state.add_leader(LeaderState(2, 1, "Rival", HOME))  # temper defaults to None

    report = execute_aspy(state, LEADER_ID, _request(), caster_holds_psychic_mage_office=True)

    assert report.spotted_characters[0].estimated_temper is None


# --- Phase 212: real army display names for "leads"/garrison lines ---


def test_execute_aspy_spotted_character_army_names_lists_armies_they_lead():
    state = _state()
    state.add_leader(LeaderState(2, 1, "Commander", HOME))
    state.add_army(ArmyState(1, 1, ArmyType.BOWMEN, Quality.AVERAGE, HOME, commanded_by=2))

    report = execute_aspy(state, LEADER_ID, _request())

    expected = make_army_name(1, ArmyType.BOWMEN, Race.HUMAN)
    assert report.spotted_characters[0].army_names == (expected,)


def test_execute_aspy_spotted_character_no_army_names_when_unled_leader():
    state = _state()
    state.add_leader(LeaderState(2, 1, "Wanderer", HOME))

    report = execute_aspy(state, LEADER_ID, _request())

    assert report.spotted_characters[0].army_names == ()


def test_execute_aspy_garrison_army_names_lists_unled_armies_only():
    state = _state()
    state.add_army(ArmyState(1, 1, ArmyType.BOWMEN, Quality.AVERAGE, HOME))  # unled
    state.add_leader(LeaderState(2, 1, "Commander", HOME))
    state.add_army(ArmyState(2, 1, ArmyType.AXEMEN, Quality.AVERAGE, HOME, commanded_by=2))  # led

    report = execute_aspy(state, LEADER_ID, _request())

    expected = make_army_name(1, ArmyType.BOWMEN, Race.HUMAN)
    assert report.garrison_army_names == (expected,)


def test_execute_aspy_garrison_army_names_empty_when_no_unled_armies():
    state = _state()
    state.add_leader(LeaderState(2, 1, "Commander", HOME))
    state.add_army(ArmyState(1, 1, ArmyType.AXEMEN, Quality.AVERAGE, HOME, commanded_by=2))

    report = execute_aspy(state, LEADER_ID, _request())

    assert report.garrison_army_names == ()


def test_execute_aspy_mercenary_army_falls_back_to_human_race():
    state = _state()
    state.add_army(ArmyState(5, None, ArmyType.BOWMEN, Quality.AVERAGE, HOME))  # mercenary, unled

    report = execute_aspy(state, LEADER_ID, _request())

    expected = make_army_name(5, ArmyType.BOWMEN, Race.HUMAN)
    assert report.garrison_army_names == (expected,)


# -- Phase 267: espionage-obtained Discoveries (RULES.AK [3.14]) -----------


def _kingdom(kingdom_id: int, *, discoveries: set[Discovery] | None = None) -> KingdomState:
    kingdom = KingdomState(kingdom_id, f"Kingdom{kingdom_id}", Race.HUMAN, Alignment.GOOD, HOME)
    if discoveries is not None:
        kingdom.discoveries = discoveries
    return kingdom


def test_roll_espionage_discoveries_never_rolls_against_own_kingdom():
    state = GameState()
    state.add_kingdom(_kingdom(1, discoveries={Discovery.COMPASS}))

    obtained = _roll_espionage_discoveries(state, 1, 1, spy_skill=9, rng=ScriptedRandom([]))

    assert obtained == ()


def test_roll_espionage_discoveries_never_rolls_with_no_kingdom_ids():
    state = GameState()
    state.add_kingdom(_kingdom(1, discoveries={Discovery.COMPASS}))

    assert _roll_espionage_discoveries(state, None, 1, spy_skill=9, rng=ScriptedRandom([])) == ()
    assert _roll_espionage_discoveries(state, 1, None, spy_skill=9, rng=ScriptedRandom([])) == ()


def test_roll_espionage_discoveries_never_rolls_for_a_kingdom_missing_from_state():
    state = GameState()
    state.add_kingdom(_kingdom(1))

    obtained = _roll_espionage_discoveries(state, 1, 2, spy_skill=9, rng=ScriptedRandom([]))

    assert obtained == ()


def test_roll_espionage_discoveries_only_considers_what_the_spy_kingdom_lacks():
    state = GameState()
    state.add_kingdom(_kingdom(1, discoveries={Discovery.COMPASS}))
    state.add_kingdom(_kingdom(2, discoveries={Discovery.COMPASS, Discovery.SEXTANT}))

    # Only SEXTANT is a real candidate (COMPASS is already owned) -- a
    # single scripted value proves exactly one roll was consumed.
    obtained = _roll_espionage_discoveries(state, 1, 2, spy_skill=9, rng=ScriptedRandom([0.0]))

    assert obtained == (Discovery.SEXTANT,)
    assert state.kingdoms[1].discoveries == {Discovery.COMPASS, Discovery.SEXTANT}


def test_roll_espionage_discoveries_uses_twice_the_sage_chance():
    # Skill 1 -> chance = 2 * 1 * 5% = 10%. 0.09 succeeds, 0.11 fails.
    state = GameState()
    state.add_kingdom(_kingdom(1))
    state.add_kingdom(_kingdom(2, discoveries={Discovery.SEXTANT}))

    assert _roll_espionage_discoveries(state, 1, 2, spy_skill=1, rng=ScriptedRandom([0.09])) == (Discovery.SEXTANT,)

    state2 = GameState()
    state2.add_kingdom(_kingdom(1))
    state2.add_kingdom(_kingdom(2, discoveries={Discovery.SEXTANT}))
    assert _roll_espionage_discoveries(state2, 1, 2, spy_skill=1, rng=ScriptedRandom([0.11])) == ()


def test_roll_espionage_discoveries_chance_is_capped_at_100_percent():
    assert ESPIONAGE_DISCOVERY_CHANCE_MULTIPLIER == 2.0
    state = GameState()
    state.add_kingdom(_kingdom(1))
    state.add_kingdom(_kingdom(2, discoveries={Discovery.SEXTANT}))

    # skill 20 -> raw formula is 200%, must still just barely succeed at 0.999.
    obtained = _roll_espionage_discoveries(state, 1, 2, spy_skill=20, rng=ScriptedRandom([0.999]))

    assert obtained == (Discovery.SEXTANT,)


def test_execute_aspy_obtains_discoveries_via_espionage_and_credits_merit():
    state = _state(owner_kingdom_id=2)
    state.add_kingdom(_kingdom(2, discoveries={Discovery.SEXTANT}))
    state.leaders[LEADER_ID].skills = SkillTable(raw_values=[0] * 30)
    state.leaders[LEADER_ID].skills.set_pair_for_ability(Ability.SPY, 4, 0)  # chance = 2*4*5% = 40%

    report = execute_aspy(state, LEADER_ID, _request(), rng=ScriptedRandom([0.1, 0.5, 0.5]))

    assert report.discoveries_obtained == (Discovery.SEXTANT,)
    assert state.kingdoms[1].discoveries == {Discovery.SEXTANT}
    assert state.leaders[LEADER_ID].merit_tally.discoveries_via_espionage == 1


def test_execute_aspy_reports_no_discoveries_when_the_roll_fails():
    state = _state(owner_kingdom_id=2)
    state.add_kingdom(_kingdom(2, discoveries={Discovery.SEXTANT}))
    state.leaders[LEADER_ID].skills = SkillTable(raw_values=[0] * 30)
    state.leaders[LEADER_ID].skills.set_pair_for_ability(Ability.SPY, 4, 0)  # chance = 40%

    report = execute_aspy(state, LEADER_ID, _request(), rng=ScriptedRandom([0.9, 0.5, 0.5]))

    assert report.discoveries_obtained == ()
    assert state.kingdoms[1].discoveries == set()
    assert state.leaders[LEADER_ID].merit_tally.discoveries_via_espionage == 0


def test_execute_aspy_awards_real_add_experience_credit():
    # Phase 458: AKGEN_reverse_engineering_report (2).md SS3.3's own Spy
    # row (base 10) -- every real ASpy report (no success/failure roll
    # gates this action at all) credits the caster's own shared
    # experience_credit counter (Phase 456).
    state = _state()
    state.provinces[HOME].tax = 5

    execute_aspy(state, LEADER_ID, _request(), rng=ScriptedRandom([0.5, 0.5, 0.5]))

    assert state.leaders[LEADER_ID].experience_credit == 10  # round(10 * (1 + 0.5 - 0.5))


def test_execute_aspy_reports_no_discoveries_for_an_unowned_province():
    state = _state(owner_kingdom_id=None)

    report = execute_aspy(state, LEADER_ID, _request())

    assert report.discoveries_obtained == ()


def test_execute_aspy_reports_no_discoveries_when_target_kingdom_has_none():
    state = _state(owner_kingdom_id=2)
    state.add_kingdom(_kingdom(2))

    # No discovery candidates -- but Phase 458's own Add_Experience call
    # still needs its two triangular-gain draws.
    report = execute_aspy(state, LEADER_ID, _request(), rng=ScriptedRandom([0.5, 0.5]))

    assert report.discoveries_obtained == ()


# -- Phase 694: Druidic Animal Spies -----------------------------------


def test_execute_aspy_adjacent_military_forces_empty_without_the_ability():
    state = _state()
    neighbor = HexCoord(4, 9)  # adjacent to (3, 9) on the odd-r grid
    state.add_province(ProvinceState(neighbor, Terrain.FOREST, Race.ELVEN, owner_kingdom_id=2))
    state.add_army(ArmyState(1, 2, ArmyType.AXEMEN, Quality.AVERAGE, neighbor))

    report = execute_aspy(state, LEADER_ID, _request())

    assert report.adjacent_military_forces == {}


def test_execute_aspy_reports_adjacent_military_forces_with_the_ability():
    state = _state()
    state.leaders[LEADER_ID].advanced_abilities.add(AdvancedAbility.DRUIDIC_ANIMAL_SPIES)
    neighbor = HexCoord(4, 9)
    state.add_province(ProvinceState(neighbor, Terrain.FOREST, Race.ELVEN, owner_kingdom_id=2))
    state.add_army(ArmyState(1, 2, ArmyType.AXEMEN, Quality.AVERAGE, neighbor))

    report = execute_aspy(state, LEADER_ID, _request(), caster_has_druidic_animal_spies=True)

    expected = make_army_name(1, ArmyType.AXEMEN, Race.HUMAN)  # kingdom 2 is never registered -- Race.HUMAN fallback
    assert report.adjacent_military_forces == {neighbor: (expected,)}


def test_execute_aspy_adjacent_military_forces_include_commanded_armies_too():
    # Unlike garrison_army_names (unled only, at the caster's own
    # province), the sourced text draws no such distinction for adjacent
    # provinces -- a commanded army is reported too.
    state = _state()
    neighbor = HexCoord(4, 9)
    state.add_province(ProvinceState(neighbor, Terrain.FOREST, Race.ELVEN, owner_kingdom_id=2))
    state.add_leader(LeaderState(2, 2, "Foreign Commander", neighbor))
    state.add_army(ArmyState(1, 2, ArmyType.AXEMEN, Quality.AVERAGE, neighbor, commanded_by=2))

    report = execute_aspy(state, LEADER_ID, _request(), caster_has_druidic_animal_spies=True)

    expected = make_army_name(1, ArmyType.AXEMEN, Race.HUMAN)
    assert report.adjacent_military_forces == {neighbor: (expected,)}


def test_execute_aspy_adjacent_military_forces_empty_tuple_for_a_forceless_neighbor():
    state = _state()
    neighbor = HexCoord(4, 9)
    state.add_province(ProvinceState(neighbor, Terrain.FOREST, Race.ELVEN, owner_kingdom_id=2))

    report = execute_aspy(state, LEADER_ID, _request(), caster_has_druidic_animal_spies=True)

    assert report.adjacent_military_forces == {neighbor: ()}


def test_execute_aspy_adjacent_military_forces_omits_unknown_neighboring_hexes():
    state = _state()

    report = execute_aspy(state, LEADER_ID, _request(), caster_has_druidic_animal_spies=True)

    assert report.adjacent_military_forces == {}


# -- Phase 705: AdvancedAbility.SPY_EXPANDED_SPYING, Spy Province half --


def test_execute_aspy_features_known_to_owner_empty_without_the_ability():
    state = _state()
    state.add_feature(Feature(1, HOME, FeatureType.TOWER, discovered_by_kingdom={1: 3}))

    report = execute_aspy(state, LEADER_ID, _request())

    assert report.features_known_to_owner == {}


def test_execute_aspy_reports_features_known_to_the_provinces_own_owner():
    state = _state(owner_kingdom_id=2)
    state.add_feature(Feature(1, HOME, FeatureType.TOWER, discovered_by_kingdom={2: 3}))

    report = execute_aspy(state, LEADER_ID, _request(), caster_has_spy_expanded_spying=True)

    assert report.features_known_to_owner == {1: 3}


def test_execute_aspy_features_known_to_owner_uses_the_owners_own_level_not_the_casters():
    # The caster's own kingdom (1) knows this feature fully, but the
    # province's own owner (2) has only detected it -- the report must
    # reflect what the *owner* knows, not what the caster's kingdom does.
    state = _state(owner_kingdom_id=2)
    state.add_feature(Feature(1, HOME, FeatureType.TOWER, discovered_by_kingdom={1: 3, 2: 1}))

    report = execute_aspy(state, LEADER_ID, _request(), caster_has_spy_expanded_spying=True)

    assert report.features_known_to_owner == {1: 1}


def test_execute_aspy_features_known_to_owner_omits_undiscovered_features():
    state = _state(owner_kingdom_id=2)
    state.add_feature(Feature(1, HOME, FeatureType.TOWER))  # discovered_by_kingdom defaults to {}

    report = execute_aspy(state, LEADER_ID, _request(), caster_has_spy_expanded_spying=True)

    assert report.features_known_to_owner == {}


def test_execute_aspy_features_known_to_owner_empty_for_an_unowned_province():
    state = _state(owner_kingdom_id=None)
    state.add_feature(Feature(1, HOME, FeatureType.TOWER, discovered_by_kingdom={1: 3}))

    report = execute_aspy(state, LEADER_ID, _request(), caster_has_spy_expanded_spying=True)

    assert report.features_known_to_owner == {}
