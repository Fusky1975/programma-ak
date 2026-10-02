"""Phase 398: proves the full item-instance creation chain end-to-end.

``README.md``'s own "Not yet implemented" section carried, since Phase
24, a claim that Use_MI's remaining gap was "deeper than Cast's --
there's no Pascal source for how item instances are even created" and
that ``item_instance_id`` "can never be resolved to a concrete
item/spell from this project's available data." That was accurate at
the time, but three later phases closed it without ever correcting
this bullet:

- Phase 242 wired a Search win to actually grant a feature's own
  ``treasure`` via ``GameState.add_item()`` (``turn/search_execution.py``).
- Phase 360 recovered the real ``AKGEN.EXE`` magic-item-placement
  algorithm from the disassembly-derived reverse-engineering material
  (``worldgen/magic_item_placement.py``) -- not a project-original
  guess.
- Phase 365 wired that cursor into ``generate_new_game()``'s own
  feature-creation loop, in real feature-index order.

No single existing test exercised all three pieces chained together --
each phase's own tests stop at its own module boundary (``test_
generate_new_game.py`` checks the treasure *count* matches
``item_slot_count()``; ``test_use_mi_execution.py`` seeds ``state.items``
by hand). This module closes that integration gap: generate a real
game, find a real world-generated feature carrying a real magic item,
have a leader Search-and-defeat its guardian, and confirm the granted
item is both present in ``GameState.items`` and directly usable via a
real ``execute_use_mi()`` call -- proving the chain
``generate_new_game()`` -> ``Feature.treasure`` -> ``execute_search()``
-> ``GameState.add_item()`` -> ``execute_use_mi()`` is genuinely closed,
not just closed in separate pieces.

The search-RNG seeds below were found by scanning outcomes for each
exact scenario until the leader won -- Melee combat's own win/loss
roll has no simpler deterministic lever available (see ``turn/
encounter.py``); recorded here as fixed, reproducible facts about
each scenario, not tuned probabilities. (Originally ``seed=30``
against a different feature; re-scanned after Phase 427 added
King-Home second-recruit-slot RNG consumption before
``place_all_features()``, which -- like Phase 426 before it -- shifted
which treasure lands on which feature id for this same
``generate_new_game(seed=1)`` scenario. Re-scanned after Phase 797
added the ordinary-humanoid-province first-recruit-slot pass
(``worldgen/initial_armies.py humanoid_first_slot()``), which -- for
the identical reason -- consumes real RNG before ``place_all_
features()`` too, shifting the feature roster once more. Re-scanned
again after Phase 799 added the ordinary-humanoid-province second-
recruit-slot pass (``humanoid_second_slot()``), the identical class of
shift once more: the first treasure+guardian feature is now feature_id
1, a weak ``ELE_MAGE`` guard (hp 10, melee skill 1), win seed ``11``;
``_BOOK_FEATURE_ID`` moved to feature_id 88, guarded by an equally weak
``MERMAID`` (hp 10, melee skill 1), win seed ``1``.) Re-scanned again
after Phase 892 wired ``worldgen/mercenary_band.py`` into
``generate_new_game()`` (RNG consumption for each King's own extra
mercenary-band search, before ``place_all_features()``, the identical
class of shift once more): feature_id 1 is now guarded by a Banshee
(hp 15, melee skill 1), win seed ``6``; feature_id 88 happens to keep
the same real facts (a ``MERMAID`` guard, win seed ``1`` still wins),
so ``_BOOK_FEATURE_ID``/``_BOOK_SEARCH_WIN_SEED`` are unchanged.
Re-scanned again after Phase 902 fixed ``worldgen/initial_armies.py
ordinary_humanoid_budget()``'s own formula (``TROLL.md``) and wired
Trollish provinces through it -- both changes consume real RNG (or, for
Trollish, newly consume it at all) before ``place_all_features()``, the
identical class of shift once more: feature_id 1 is now guarded by a
``RAKSHASHA`` (hp 18-27, melee skill 1), win seed ``2``; the
``SKILL_BOOK``-category feature moved to feature_id 86, guarded by a
``GI_CLAM`` (hp 14-27, melee skill 0), win seed ``5``.

Re-scanned again after Phase 979 wired ``worldgen/leader_placement.py
draw_mercenary_relocation_coordinate()`` into ``generate_new_game()``
for "remaining mercenary heroes" (one ``PascalRandom`` draw per leftover
roster id, consumed before ``place_all_features()``, the identical
class of shift once more): feature_id 1 is now guarded by a
``MINOTAUR`` (hp 15-25, melee skill 2), win seed ``0``; the
``SKILL_BOOK``-category feature moved to feature_id 95, still guarded
by a ``GI_CLAM`` (hp 14-27, melee skill 0, the same real fact as
before -- only its feature id shifted), win seed ``5`` unchanged.

Re-scanned a final time after Phase 979's own addendum materialized the
reserved last roster id too (one more ``PascalRandom`` coordinate draw,
same class of shift once more): feature_id 1 is now guarded by a
``GR_DRAGON`` (hp 21-31, melee skill 2) -- a genuinely tough guardian
for an unskilled Searcher, so its own win seed is larger than every
prior rescan's, ``827``, rather than the usual small one; the
``SKILL_BOOK``-category feature keeps feature_id 95/``GI_CLAM``/win
seed ``5`` unchanged (that specific treasure+guardian pairing wasn't
affected by this particular shift).

Re-scanned again after Phase 982 added ``roll_temper()`` (one
``PascalRandom`` draw per ordinary generated hero, consumed in the same
``hero_pool``-building loop ``roll_alignment()``'s own draw already
sits in, well before ``place_all_features()``), the identical class of
shift once more: feature_id 1 keeps its own real facts unchanged (still
a ``MINOTAUR``, win seed ``827`` still wins -- this particular shift
happened not to move that specific pairing); the ``SKILL_BOOK``-category
feature moved to feature_id 13, still guarded by a ``GI_CLAM`` (the
same real monster as every prior rescan, just a new feature id and a
different book, ``BOOK_SAGE``), win seed ``5`` unchanged.

Re-scanned again after Phase 986 recalibrated ``worldgen/place_map.py``'s
own land-growth target to match a real played game's land/Sea ratio (far
more land cells now exist for the same ``generate_new_game(seed=1)``
scenario, so the whole province grid -- and every RNG draw that depends
on its size or contents, all of them before ``place_all_features()`` --
shifts, the identical class of change as every rescan above, just from a
different cause this time): feature_id 1 is now guarded by a ``GENIE``
(good-aligned), win seed ``2``; the ``SKILL_BOOK``-category feature moved
to feature_id 21, guarded by a ``MEDUSA`` and carrying a different book,
``BOOK_TACTICAL``, win seed ``30``.
"""

from __future__ import annotations

import random

from ak_engine.models.alignment import Alignment
from ak_engine.models.enums import Maneuver
from ak_engine.models.game_state import GameState, KingdomState, LeaderState
from ak_engine.models.map import HexCoord
from ak_engine.models.race import Race
from ak_engine.models.treasure import TREASURE_BOOK_ABILITY, TREASURE_CATEGORY, TreasureCategory
from ak_engine.turn.search_decode import SearchRequest, SearchTactic
from ak_engine.turn.search_execution import execute_search
from ak_engine.turn.use_mi_decode import UseMIRequest
from ak_engine.turn.use_mi_execution import execute_use_mi
from ak_engine.worldgen.generate_new_game import KingSetup, generate_new_game
from ak_engine.worldgen.pascal_random import PascalRandom

_KING_RACES = [Race.HUMAN, Race.ELVEN, Race.DWARVEN, Race.ORCISH] * 3
_SEARCHER_LEADER_ID = 999
# Phase 986 note: generate_new_game(seed=1)'s own feature roster shifted
# again after the land-ratio recalibration (see this module's own Phase
# 986 rescan paragraph above) -- a fixed, reproducible fact of this
# scenario, not a tuning choice. The first treasure+guardian feature
# (feature_id 1) is now guarded by a good-aligned GENIE.
_SEARCH_WIN_SEED = 2
# feature_id 21 (a MEDUSA guarding a Tactical skill book) is the
# SKILL_BOOK-category feature this test now targets.
_BOOK_FEATURE_ID = 21
_BOOK_SEARCH_WIN_SEED = 30


def _generate_game(king_count: int = 10) -> GameState:
    game_state = GameState()
    kings: list[KingSetup] = []
    for i in range(king_count):
        race = _KING_RACES[i % 4]
        home = HexCoord(i, 0)
        game_state.kingdoms[i] = KingdomState(
            kingdom_id=i, name=f"K{i}", race=race, alignment=Alignment.NEUTRAL, home_province=home
        )
        game_state.leaders[i] = LeaderState(
            leader_id=i, kingdom_id=i, name=f"King{i}", location=HexCoord(0, 0), is_king=True, race=race
        )
        kings.append(KingSetup(leader_id=i, race=race, home_coord=home))
    return generate_new_game(PascalRandom(seed=1), game_state, kings, gamevers=1)


def test_world_generated_treasure_reaches_state_items_via_a_search_win():
    state = _generate_game()
    feature = next(f for f in state.features.values() if f.treasure is not None and f.guardian_monster is not None)
    state.leaders[_SEARCHER_LEADER_ID] = LeaderState(
        leader_id=_SEARCHER_LEADER_ID, kingdom_id=0, name="Searcher", location=feature.coord, skills=None
    )
    request = SearchRequest(feature_id=feature.feature_id, unconfirmed_extra0=0, tactics=[SearchTactic(maneuver=Maneuver.MELEE)])

    result = execute_search(state, _SEARCHER_LEADER_ID, request, rng=random.Random(_SEARCH_WIN_SEED))

    assert result.winner == "leader"
    assert feature.looted is True
    assert len(state.items) == 1
    item = next(iter(state.items.values()))
    assert item.treasure == feature.treasure
    assert item.owner_leader_id == _SEARCHER_LEADER_ID


def test_a_world_generated_and_search_won_book_is_directly_usable_via_use_mi():
    # This project's real generate_new_game(seed=1) scenario places a
    # BOOK_TACTICAL on feature_id 21 (guarded by a MEDUSA) -- not tuned
    # for that, just what this fixed, reproducible generation run
    # produces (see _BOOK_FEATURE_ID's own Phase 986 note above). Any
    # SKILL_BOOK category member would exercise the same chain.
    state = _generate_game()
    feature = next(f for f in state.features.values() if f.feature_id == _BOOK_FEATURE_ID)
    assert TREASURE_CATEGORY[feature.treasure] is TreasureCategory.SKILL_BOOK
    state.leaders[_SEARCHER_LEADER_ID] = LeaderState(
        leader_id=_SEARCHER_LEADER_ID, kingdom_id=0, name="Searcher", location=feature.coord, skills=None
    )
    request = SearchRequest(feature_id=feature.feature_id, unconfirmed_extra0=0, tactics=[SearchTactic(maneuver=Maneuver.MELEE)])
    execute_search(state, _SEARCHER_LEADER_ID, request, rng=random.Random(_BOOK_SEARCH_WIN_SEED))
    item_id, item = next(iter(state.items.items()))
    expected_ability = TREASURE_BOOK_ABILITY[item.treasure]

    use_result = execute_use_mi(
        state, kingdom_id=0, leader_id=_SEARCHER_LEADER_ID, request=UseMIRequest(item_instance_id=item_id, target=0)
    )

    assert use_result.applied is True
    assert use_result.ability_boosted is expected_ability
    skill, _aptitude = state.leaders[_SEARCHER_LEADER_ID].skills.pair_for_ability(expected_ability)
    assert skill == 1
    assert item_id not in state.items  # self-consuming, per turn/use_mi_execution.py's own docstring
