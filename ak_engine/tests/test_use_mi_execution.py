from __future__ import annotations

from ak_engine.models.alignment import Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.enums import Ability, Spell
from ak_engine.models.game_state import ArmyState, GameState, KingdomState, LeaderState, ProvinceState
from ak_engine.models.kingdom import SkillTable
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.race import Race
from ak_engine.models.treasure import Treasure
from ak_engine.turn.combat import Quality
from ak_engine.turn.hex_numbering import encode_hex_number
from ak_engine.turn.movement import NORMAL_MAP_BOUNDS
from ak_engine.turn.use_mi_decode import UseMIRequest
from ak_engine.turn.use_mi_execution import execute_use_mi

from _helpers import ScriptedRandom

LOCATION = HexCoord(3, 9)
CASTER_ID = 1
KINGDOM_ID = 1
BOARD_WIDTH = NORMAL_MAP_BOUNDS[0]


def _target(coord: HexCoord) -> int:
    return encode_hex_number(coord, BOARD_WIDTH)


def build_state() -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(KINGDOM_ID, "Testia", Race.HUMAN, Alignment.GOOD, LOCATION))
    state.add_kingdom(KingdomState(2, "Rivalia", Race.HUMAN, Alignment.EVIL, LOCATION))
    state.add_leader(LeaderState(CASTER_ID, KINGDOM_ID, "Caster", LOCATION))
    return state


def test_execute_use_mi_item_not_found():
    state = build_state()
    request = UseMIRequest(item_instance_id=999, target=0)

    result = execute_use_mi(state, KINGDOM_ID, CASTER_ID, request)

    assert result.applied is False
    assert result.reason == "item not found"


def test_execute_use_mi_rejects_an_item_the_leader_doesnt_own():
    state = build_state()
    item = state.add_item(Treasure.WAND_KILL_ENEMY, owner_leader_id=999)
    request = UseMIRequest(item_instance_id=item.item_id, target=0)

    result = execute_use_mi(state, KINGDOM_ID, CASTER_ID, request)

    assert result.applied is False
    assert result.reason == "leader does not possess this item"


def test_execute_use_mi_rejects_a_category_that_operates_automatically():
    # Ability items (e.g. Standard of Command) are never a Use_MI target
    # -- rulebook [5.9] -- unlike wands/books.
    state = build_state()
    item = state.add_item(Treasure.ABILITY_TACTICAL, owner_leader_id=CASTER_ID)
    request = UseMIRequest(item_instance_id=item.item_id, target=0)

    result = execute_use_mi(state, KINGDOM_ID, CASTER_ID, request)

    assert result.applied is False
    assert result.reason == "not a Use_MI target -- operates automatically"


# --- Spell wands (rulebook [3.11]: automatically successful, TREASAB.X2: "at skill-2") ---


def test_execute_use_mi_wand_casts_the_mapped_spell():
    state = build_state()
    state.add_leader(LeaderState(78, 2, "Enemy Hero", LOCATION))
    item = state.add_item(Treasure.WAND_KILL_ENEMY, owner_leader_id=CASTER_ID)
    request = UseMIRequest(item_instance_id=item.item_id, target=78)

    result = execute_use_mi(state, KINGDOM_ID, CASTER_ID, request)

    assert result.applied is True
    assert result.cast_result is not None
    assert result.cast_result.request.spell is Spell.KILL_ENEMY
    assert 78 not in state.leaders


def test_execute_use_mi_wand_bypasses_the_success_roll_even_with_no_recorded_skill():
    # A real Cast of Kill_Enemy with skills=None still auto-succeeds
    # (Phase 30's own "no data" placeholder) -- so use an explicit
    # *insufficient* skill (0) instead, which would fail a real Cast
    # outright ("insufficient skill"), to prove the wand path really
    # bypasses the roll rather than coincidentally succeeding anyway.
    state = build_state()
    raw_values = [0] * 30
    raw_values[Ability.NECROMANCY.value * 2] = 0
    state.leaders[CASTER_ID].skills = SkillTable(raw_values=raw_values)
    state.add_leader(LeaderState(78, 2, "Enemy Hero", LOCATION))
    item = state.add_item(Treasure.WAND_KILL_ENEMY, owner_leader_id=CASTER_ID)
    request = UseMIRequest(item_instance_id=item.item_id, target=78)
    rng = ScriptedRandom([])  # no .random() call should happen at all

    result = execute_use_mi(state, KINGDOM_ID, CASTER_ID, request, rng=rng)

    assert result.applied is True
    assert 78 not in state.leaders


def test_execute_use_mi_wand_uses_skill_level_2_regardless_of_casters_real_level():
    # Caster's real Elemental skill is 0 (0% Tornado destroy chance in a
    # real Cast); the wand always casts "at skill-2" (TREASAB.X2), i.e.
    # a 20% chance, regardless.
    state = build_state()
    state.add_province(ProvinceState(LOCATION, Terrain.PLAINS, Race.HUMAN))
    raw_values = [0] * 30
    state.leaders[CASTER_ID].skills = SkillTable(raw_values=raw_values)  # Elemental level 0
    state.add_army(ArmyState(1, 2, ArmyType.BOWMEN, Quality.AVERAGE, LOCATION))
    item = state.add_item(Treasure.WAND_TORNADO, owner_leader_id=CASTER_ID)
    request = UseMIRequest(item_instance_id=item.item_id, target=_target(LOCATION))
    # No cast-success roll consumed (automatic) -- this is only the
    # per-army destroy roll. 0.15 destroys at skill-2's 20% chance but
    # would NOT destroy at the caster's real 0% chance.
    rng = ScriptedRandom([0.15])

    result = execute_use_mi(state, KINGDOM_ID, CASTER_ID, request, rng=rng)

    assert result.applied is True
    assert 1 not in state.armies


# --- Skill books (rulebook [5.9]: one-shot, self-consuming +1 Ability) ---


def test_execute_use_mi_book_boosts_the_ability_and_consumes_the_item():
    state = build_state()
    item = state.add_item(Treasure.BOOK_MELEE, owner_leader_id=CASTER_ID)
    request = UseMIRequest(item_instance_id=item.item_id, target=0)

    result = execute_use_mi(state, KINGDOM_ID, CASTER_ID, request)

    assert result.applied is True
    assert result.ability_boosted is Ability.MELEE
    assert state.leaders[CASTER_ID].skills.pair_for_ability(Ability.MELEE) == (1, 0)
    assert item.item_id not in state.items


def test_execute_use_mi_book_creates_a_fresh_skill_table_if_none_recorded():
    state = build_state()
    assert state.leaders[CASTER_ID].skills is None
    item = state.add_item(Treasure.BOOK_SAGE, owner_leader_id=CASTER_ID)
    request = UseMIRequest(item_instance_id=item.item_id, target=0)

    result = execute_use_mi(state, KINGDOM_ID, CASTER_ID, request)

    assert result.applied is True
    assert state.leaders[CASTER_ID].skills is not None
    assert state.leaders[CASTER_ID].skills.pair_for_ability(Ability.SAGE) == (1, 0)


def test_execute_use_mi_book_clamps_skill_at_the_real_ceiling_of_9():
    # CTBOTH.PAS: skillrange = 0..9.
    state = build_state()
    raw_values = [0] * 30
    raw_values[Ability.MELEE.value * 2] = 9
    state.leaders[CASTER_ID].skills = SkillTable(raw_values=raw_values)
    item = state.add_item(Treasure.BOOK_MELEE, owner_leader_id=CASTER_ID)
    request = UseMIRequest(item_instance_id=item.item_id, target=0)

    result = execute_use_mi(state, KINGDOM_ID, CASTER_ID, request)

    assert result.applied is True
    assert state.leaders[CASTER_ID].skills.pair_for_ability(Ability.MELEE) == (9, 0)
