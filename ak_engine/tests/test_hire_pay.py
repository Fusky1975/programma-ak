from __future__ import annotations

from ak_engine.models.alignment import Alignment
from ak_engine.models.game_state import GameState, KingdomState, LeaderState, ProvinceState
from ak_engine.models.kingdom import SkillTable
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.race import Race
from ak_engine.models.temper import Temper
from ak_engine.turn.hire_pay import (
    RARE_ALIGNMENT_EXCEPTION_CHANCE,
    RARE_ALIGNMENT_EXCEPTION_PAY,
    required_pay,
    roll_rare_alignment_exception,
)

from _helpers import ScriptedRandom

HOME = HexCoord(3, 9)
# Total_USkill way over the "king with < 7 total skill" exception's own
# threshold -- every one of the 15 skill pairs at max.
HIGH_SKILL = SkillTable(raw_values=[9] * 30 + [0])


def make_state() -> GameState:
    state = GameState()
    state.add_kingdom(KingdomState(1, "Kingdom", Race.HUMAN, Alignment.GOOD, HOME))
    return state


def _leader(
    leader_id: int,
    *,
    kingdom_id: int | None = None,
    alignment: Alignment | None = None,
    temper: Temper | None = None,
    race: Race | None = None,
    birth_x: int | None = None,
    birth_y: int | None = None,
    is_king: bool = False,
    skills: SkillTable | None = None,
    is_starting_companion: bool = False,
) -> LeaderState:
    return LeaderState(
        leader_id,
        kingdom_id,
        "Someone",
        HOME,
        is_king=is_king,
        alignment=alignment,
        temper=temper,
        race=race,
        birth_x=birth_x,
        birth_y=birth_y,
        skills=skills,
        is_starting_companion=is_starting_companion,
    )


# King leader_id=2 (even) with no birth coordinate recorded on the hero
# pins the real formula's own `bias` term to 0 for *any* hero leader_id
# -- isolating the alignment-distance ladder cleanly from the personal-
# bit terms exercised further down. See module docstring's own note on
# why a *specific* historical game's real leader indices can no longer
# be reproduced from this project's own, unrelated id-assignment order.
_KING_ID = 2
_HERO_ID = 5


def _ladder_king(alignment: Alignment) -> LeaderState:
    return _leader(_KING_ID, kingdom_id=1, alignment=alignment, temper=Temper.BRAVE, is_king=True)


def test_required_pay_same_alignment_is_cheapest():
    hero = _leader(_HERO_ID, alignment=Alignment.GOOD, temper=Temper.BRAVE)
    assert required_pay(make_state(), hero, _ladder_king(Alignment.GOOD)) == 1


def test_required_pay_distance_one_costs_two():
    # GOOD(1) vs DRUID(2) -- real ordinal distance 1.
    hero = _leader(_HERO_ID, alignment=Alignment.DRUID, temper=Temper.BRAVE)
    assert required_pay(make_state(), hero, _ladder_king(Alignment.GOOD)) == 2


def test_required_pay_distance_two_costs_three():
    # GOOD(1) vs NEUTRAL(3) -- real ordinal distance 2.
    hero = _leader(_HERO_ID, alignment=Alignment.NEUTRAL, temper=Temper.BRAVE)
    assert required_pay(make_state(), hero, _ladder_king(Alignment.GOOD)) == 3


def test_required_pay_distance_three_is_unhireable():
    # The rulebook's own hard anchor: "a Good King generally cannot hire
    # a Pagan Hero" -- real ordinal distance 3.
    hero = _leader(_HERO_ID, alignment=Alignment.PAGAN, temper=Temper.BRAVE)
    assert required_pay(make_state(), hero, _ladder_king(Alignment.GOOD)) == 5


def test_required_pay_distance_beyond_three_still_caps_at_five():
    hero = _leader(_HERO_ID, alignment=Alignment.EVIL, temper=Temper.BRAVE)
    assert required_pay(make_state(), hero, _ladder_king(Alignment.GOOD)) == 5


def test_required_pay_defaults_to_cheapest_when_hero_alignment_missing():
    hero = _leader(_HERO_ID, alignment=None, temper=Temper.BRAVE)
    assert required_pay(make_state(), hero, _ladder_king(Alignment.PAGAN)) == 1


def test_required_pay_defaults_to_cheapest_when_king_is_none():
    hero = _leader(_HERO_ID, alignment=Alignment.PAGAN, temper=Temper.BERSERK)
    assert required_pay(make_state(), hero, None) == 1


# -- bias/race/temper personal-bit mechanics (Phase 505's own real
# formula). All four cases below hold the same DRUID-vs-GOOD real
# distance 1 (align_penalty=1, bias=0 -- king id 2, no other friction
# would price at 2), varying only the bit each penalty term itself
# gates on. -------------------------------------------------------------


def test_required_pay_temper_mismatch_only_bites_when_the_personal_bit_is_set():
    king = _leader(_KING_ID, kingdom_id=1, alignment=Alignment.GOOD, temper=Temper.BRAVE, is_king=True, skills=HIGH_SKILL)

    matching_temper = _leader(
        _HERO_ID, alignment=Alignment.DRUID, temper=Temper.BRAVE, race=Race.HUMAN, birth_x=1, birth_y=1
    )
    assert required_pay(make_state(), matching_temper, king) == 2

    mismatched_bit_on = _leader(
        _HERO_ID, alignment=Alignment.DRUID, temper=Temper.COWARDLY, race=Race.HUMAN, birth_x=1, birth_y=1
    )
    assert required_pay(make_state(), mismatched_bit_on, king) == 3

    mismatched_bit_off = _leader(
        _HERO_ID, alignment=Alignment.DRUID, temper=Temper.COWARDLY, race=Race.HUMAN, birth_x=0, birth_y=1
    )
    assert required_pay(make_state(), mismatched_bit_off, king) == 2


def test_required_pay_race_mismatch_only_bites_when_the_personal_bit_is_set():
    king = _leader(_KING_ID, kingdom_id=1, alignment=Alignment.GOOD, temper=Temper.BRAVE, is_king=True, skills=HIGH_SKILL)

    mismatched_bit_on = _leader(
        _HERO_ID, alignment=Alignment.DRUID, temper=Temper.BRAVE, race=Race.DWARVEN, birth_x=1, birth_y=1
    )
    assert required_pay(make_state(), mismatched_bit_on, king) == 3

    mismatched_bit_off = _leader(
        _HERO_ID, alignment=Alignment.DRUID, temper=Temper.BRAVE, race=Race.DWARVEN, birth_x=1, birth_y=0
    )
    assert required_pay(make_state(), mismatched_bit_off, king) == 2


def test_required_pay_free_hero_under_a_weak_king_amplifies_temper_even_when_it_matches():
    # "While the Hero is still Mercenary (kingdom_id is None), a King
    # whose own Total_USkill < 7 gets the temper-mismatch penalty
    # regardless" -- the dossier's own real exception, distinct from an
    # actual temper mismatch.
    weak_king = _leader(_KING_ID, kingdom_id=1, alignment=Alignment.GOOD, temper=Temper.BRAVE, is_king=True)  # Total_USkill=0
    free_hero = _leader(
        _HERO_ID, kingdom_id=None, alignment=Alignment.DRUID, temper=Temper.BRAVE, race=Race.HUMAN, birth_x=1, birth_y=1
    )
    assert required_pay(make_state(), free_hero, weak_king) == 3

    # Once actually hired (kingdom_id set), the same Hero/King pair no
    # longer qualifies as "still Mercenary" -- the exception stops firing.
    hired_hero = _leader(
        _HERO_ID, kingdom_id=9, alignment=Alignment.DRUID, temper=Temper.BRAVE, race=Race.HUMAN, birth_x=1, birth_y=1
    )
    assert required_pay(make_state(), hired_hero, weak_king) == 2


# -- home-province conquest surcharge -----------------------------------


def test_required_pay_conquest_surcharge_applies_when_king_owns_the_heros_birthplace():
    state = make_state()
    state.provinces[HexCoord(7, 7)] = ProvinceState(HexCoord(7, 7), terrain=Terrain.PLAINS, race=Race.HUMAN, owner_kingdom_id=1)
    king = _leader(_KING_ID, kingdom_id=1, alignment=Alignment.GOOD, temper=Temper.BRAVE, is_king=True, skills=HIGH_SKILL)
    hero = _leader(_HERO_ID, alignment=Alignment.DRUID, temper=Temper.BRAVE, race=Race.HUMAN, birth_x=7, birth_y=7)

    with_surcharge = required_pay(state, hero, king)
    without_surcharge = required_pay(make_state(), hero, king)  # same coords, no province recorded

    assert without_surcharge == 3
    assert with_surcharge == without_surcharge + 1 == 4


def test_required_pay_conquest_surcharge_never_applies_to_a_divine_king():
    state = make_state()
    state.provinces[HexCoord(7, 7)] = ProvinceState(HexCoord(7, 7), terrain=Terrain.PLAINS, race=Race.HUMAN, owner_kingdom_id=1)
    divine_king = _leader(_KING_ID, kingdom_id=1, alignment=Alignment.DIVINE, temper=Temper.BRAVE, is_king=True, skills=HIGH_SKILL)
    hero = _leader(_HERO_ID, alignment=Alignment.GOOD, temper=Temper.BRAVE, race=Race.HUMAN, birth_x=7, birth_y=7)

    assert required_pay(state, hero, divine_king) == 2


def test_required_pay_conquest_surcharge_skipped_without_a_recorded_birth_coordinate():
    state = make_state()
    state.provinces[HexCoord(7, 7)] = ProvinceState(HexCoord(7, 7), terrain=Terrain.PLAINS, race=Race.HUMAN, owner_kingdom_id=1)
    king = _leader(_KING_ID, kingdom_id=1, alignment=Alignment.GOOD, temper=Temper.BRAVE, is_king=True, skills=HIGH_SKILL)
    hero = _leader(_HERO_ID, alignment=Alignment.DRUID, temper=Temper.BRAVE, race=Race.HUMAN)  # no birth_x/birth_y

    assert required_pay(state, hero, king) == 2


def test_required_pay_conquest_surcharge_skipped_for_a_starting_companion():
    # Phase 984: a King's own starting companion is born at his own Home
    # by construction, not by conquest -- 2 of the 4 real Turn-0 samples
    # this project has (K1's Teleko/Evil under Uga-Buga/Undead, K3's
    # Garin/Pagan under Kwoth/Neutral) show a misaligned starting
    # companion paying the *same* gold as their own aligned companion
    # counterpart, confirming the surcharge never actually applies here.
    state = make_state()
    state.provinces[HexCoord(7, 7)] = ProvinceState(HexCoord(7, 7), terrain=Terrain.PLAINS, race=Race.HUMAN, owner_kingdom_id=1)
    king = _leader(_KING_ID, kingdom_id=1, alignment=Alignment.GOOD, temper=Temper.BRAVE, is_king=True, skills=HIGH_SKILL)
    companion = _leader(
        _HERO_ID, alignment=Alignment.DRUID, temper=Temper.BRAVE, race=Race.HUMAN, birth_x=7, birth_y=7, is_starting_companion=True
    )
    ordinary_hero = _leader(_HERO_ID, alignment=Alignment.DRUID, temper=Temper.BRAVE, race=Race.HUMAN, birth_x=7, birth_y=7)

    assert required_pay(state, companion, king) == 3
    assert required_pay(state, ordinary_hero, king) == 4  # same inputs, surcharge still applies


# -- Phase 264: "In rare occasioni..." bypass --------------------------------


def test_rare_alignment_exception_chance_is_the_user_specified_fifteen_percent():
    assert RARE_ALIGNMENT_EXCEPTION_CHANCE == 0.15


def test_rare_alignment_exception_pay_is_the_hire_offer_ceiling():
    assert RARE_ALIGNMENT_EXCEPTION_PAY == 4


def test_roll_rare_alignment_exception_succeeds_under_the_threshold():
    rng = ScriptedRandom([0.14])
    assert roll_rare_alignment_exception(rng) is True


def test_roll_rare_alignment_exception_fails_at_or_above_the_threshold():
    rng = ScriptedRandom([0.15])
    assert roll_rare_alignment_exception(rng) is False
