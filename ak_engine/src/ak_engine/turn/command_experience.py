"""Experience for commanding in battle and for taking or leaving units
(``Regolamento AK.txt`` [3.13], the table of the chance to improve an ability):

    Prendere o Lasciare unità di terra     5%  Marcia
    Prendere o Lasciare unità navali       5%  Navale
    Comandante Supremo in battaglia       15%  Tattica o Navale
    Comandare unità in battaglia          10%  Tattica o Navale

Tactical applies to a battle on land, Naval to a battle in a sea province
(rulebook [6.3]: "Tactical ability (or Naval ability in Sea provinces)").

The percentages are the ``base_points`` of ``turn/experience.py
add_experience()``, the same call convention the Melee/Archery, Spy and Move
(March/Naval) awards already use. A rise grants the real ``spabord`` Advanced
Ability of the new level exactly as a Move-triggered rise does.

These awards draw from their own deterministic stream (seeded by game, turn,
leader and place) rather than the turn's shared one, so adding them never
shifts the random draws of the actions around them.
"""

from __future__ import annotations

import random

from ak_engine.models.army_type import SEA_ARMY_TYPES, is_land_army
from ak_engine.models.enums import Ability
from ak_engine.models.game_state import GameState, LeaderState
from ak_engine.models.map import Terrain
from ak_engine.turn.experience import ExperienceOutcome, add_experience
from ak_engine.turn.practice_execution import _maybe_grant_advanced_ability
from ak_engine.worldgen.march_ability_level_schedule import build_march_ability_level_schedule
from ak_engine.worldgen.naval_ability_level_schedule import build_naval_ability_level_schedule

SUPREME_COMMANDER_BASE_POINTS = 15
COMMANDER_BASE_POINTS = 10
PICK_UP_LEAVE_BASE_POINTS = 5


def _stream(state: GameState, *key: object) -> random.Random:
    return random.Random(":".join(["command-xp", str(state.game_number), str(state.turn_number), *map(str, key)]))


def _award(state: GameState, leader: LeaderState, ability: Ability, base_points: int, rng: random.Random) -> ExperienceOutcome:
    outcome = add_experience(leader, ability, base_points, rng)
    if outcome.skill_rose:
        if ability is Ability.NAVAL:
            granted = build_naval_ability_level_schedule(state.game_number).get(outcome.new_skill)
            if granted is not None:
                leader.advanced_abilities.add(granted)
        elif ability is Ability.MARCH:
            granted = build_march_ability_level_schedule(state.game_number).get(outcome.new_skill)
            if granted is not None:
                leader.advanced_abilities.add(granted)
        else:
            _maybe_grant_advanced_ability(state, leader, ability, True, outcome.new_skill)
    return outcome


def award_battle_command_experience(
    state: GameState,
    terrain: Terrain,
    *,
    province_key: object,
    supreme_commander_ids: tuple[int | None, ...],
    commanding_leader_ids: tuple[list[int], ...],
) -> None:
    """Credits every leader who commanded units in a battle: the supreme
    commander of each side at the higher rate, the others at the lower one.
    ``commanding_leader_ids`` has one list per side."""

    ability = Ability.NAVAL if terrain is Terrain.SEA else Ability.TACTICAL
    supreme = {leader_id for leader_id in supreme_commander_ids if leader_id is not None}
    credited: set[int] = set()
    for leader_ids in commanding_leader_ids:
        for leader_id in sorted(set(leader_ids)):
            if leader_id in credited:
                continue
            credited.add(leader_id)
            leader = state.leaders.get(leader_id)
            if leader is None:
                continue
            base = SUPREME_COMMANDER_BASE_POINTS if leader_id in supreme else COMMANDER_BASE_POINTS
            _award(state, leader, ability, base, _stream(state, "battle", province_key, leader_id))


def award_pick_up_leave_experience(state: GameState, leader_id: int, army_ids: list[int]) -> None:
    """Credits the acting leader for armies actually picked up or left: March
    for land units, Naval for naval ones, once each however many were moved."""

    leader = state.leaders.get(leader_id)
    if leader is None:
        return
    armies = [state.armies[army_id] for army_id in army_ids if army_id in state.armies]
    if any(army.army_type in SEA_ARMY_TYPES for army in armies):
        _award(state, leader, Ability.NAVAL, PICK_UP_LEAVE_BASE_POINTS, _stream(state, "units-naval", leader_id, sorted(army_ids)))
    if any(is_land_army(army.army_type) for army in armies):
        _award(state, leader, Ability.MARCH, PICK_UP_LEAVE_BASE_POINTS, _stream(state, "units-land", leader_id, sorted(army_ids)))
