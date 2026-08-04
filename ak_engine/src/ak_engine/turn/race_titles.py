"""Race-fanaticism Imperial title Merit Point formulas (Phase 367) --
``CARICHE E ABILITÀ.txt``'s own "cariche minori" section (the same
user-supplied reference already used for `Office.EVIL_KING`/`Office.
THIEF_PRINCE`, Phase 277), covering the 11 remaining titles.

**These titles don't grant Victory Points** ("Queste non danno punti
vittoria ma solo abilità utili durante il gioco") -- unlike the 8
majors (Phase 227) and King of Pain/Prince of Thieves (Phase 277),
which the source's own opening paragraph explicitly separates from
this section. They're still resolved the same way, though: `models/
office.py OFFICE_MIN_POINTS`/`OFFICE_VALUE` already carry real,
Phase-81-sourced entries for all 11 (`CTBOTH.PAS minpts`/`ofcvalue`),
confirming this project's own pre-existing Office model already knew
these were real, threshold-gated titles -- only the scoring *formula*
that fills `Ofc_Pts` was missing, exactly the gap this phase closes,
the same shape as Phase 227's own "confirmed dead end, formula now
found elsewhere" story.

**Each race's own formula shares one common shape**, quoted once here
rather than per-race (see `RACE_TITLE_*` tables below for the
per-race parameters each term plugs into):

- +1 per own-race unit in the front line, per battle won; -1 per
  own-race unit in the front line, per battle lost.
- +1 per own-race unit of Crack-or-better quality currently commanded
  (lost if the unit changes hands or is destroyed) -- **live only for
  the 7 special races**, via `models.army_type.NATIVE_ARMY_TYPE`'s own
  exact `ArmyType`<->`Race` correspondence (already relied on
  throughout the world-generation arc, Phase 358+). For the 4 core
  humanoid races (Human/Elven/Dwarven/Orcish), this project's own
  `models/army_type.py` docstring already establishes that ordinary
  `ArmyType`s carry no race marker at all ("you CAN recruit any
  humanoid army type in any humanoid province") -- there is no way to
  tell a Human-recruited Legion from an Orc-recruited one, so this
  term is a documented, honest 0 for those four, not a guess.
- +1 per Hero of this race currently in this leader's own Kingdom's
  service, **King only** -- live via `GameState.leaders`.
- +1 per province of this race owned by this leader's own Kingdom,
  **King only** -- live via `GameState.provinces`.
- +0.5 per unit of this race's own confirmed "rival" race(s) destroyed
  -- by battle, spell, Plague, or Tornado alike (`RACE_TITLE_RIVAL_
  RACES`); cumulative, no writer yet (`RaceTitleTally.rival_race_
  units_destroyed`).
- +1 per monster killed in a province of this race (`RaceTitleTally.
  monsters_killed_in_race_province`); cumulative, no writer yet.
- +1 per kill of one of this race's own specific named monster species
  (`RACE_TITLE_NAMED_MONSTERS`; `RaceTitleTally.named_monster_kills`);
  cumulative, no writer yet. The source's own wording ("se si uccide
  uno di questi mostri si ottiene un punto") doesn't distinguish a
  one-time bonus from a per-kill-event one -- read here as per-event,
  matching every other repeatable term in this same formula family,
  not a one-shot flag.
- +2 if this leader currently owns this race's own named legendary
  item (`RACE_TITLE_LEGENDARY_ITEM`, `None` for the 3 races the source
  names no item for) -- live via `GameState.items_held_by()`.
- **Prerequisite** ("Se non si possiede almeno una provincia di
  [razza] si hanno sempre 0 punti"): for the 7 special races only (not
  the 4 core humanoid ones, whose own provinces are never optional in
  a normal game), a leader whose own Kingdom owns no province of this
  race always scores 0, regardless of any tally already accrued. Read
  as Kingdom-scoped like every other King-only term above -- an
  independent Hero (no Kingdom) can never satisfy this, so every
  special-race title is effectively King-only in practice for these 7
  races, even though the source states no such restriction explicitly
  (`RACE_TITLE_REQUIRES_OWNED_PROVINCE`).
- **Turn gate** ("questa carica entra in gioco alla fine del turno
  N"): the *office itself* awards no winner before turn N, even though
  points visibly accumulate before then ("prima si accumulano solo
  punti") -- `RACE_TITLE_TURN_GATE`, enforced in `turn/office_holder.py
  resolve_office_holder()`, not in the score formula itself (so a
  caller inspecting raw points still sees the true accumulated total).

**Werefolk's own named-monster term** ("Se si uccide uno di questi
mostri si ottiene un punto: Renegade priest") matches `Monster.
WHITE_MAGE` exactly -- `MONSTER_NAMES[Monster.WHITE_MAGE] ==
"Renegade Priest"` (this project's own already-transcribed
`models/monster.py` display-name table, not a new lookup). Several of
this project's caster-type `Monster` members have a display name that
doesn't match their own Python identifier at all (`WHITE_MAGE`/
`NEC_MAGE`/`PSY_MAGE`/`ILL_MAGE` are each "Renegade ..." in
`MONSTER_NAMES`), so this only turns up by checking the name table,
not by grepping enum *member* names for "RENEGADE".
"""

from __future__ import annotations

from ak_engine.models.army_type import MONSTROUS_ARMY_RACE, ArmyType
from ak_engine.models.game_state import GameState, LeaderState, RaceTitleTally
from ak_engine.models.monster import Monster
from ak_engine.models.office import Office
from ak_engine.models.race import Race
from ak_engine.models.treasure import Treasure
from ak_engine.turn.combat import Quality

# Race <-> its own title office (`models/office.py Office`, already
# sourced, Phase 81).
RACE_TITLE_OFFICE: dict[Race, Office] = {
    Race.HUMAN: Office.HUMAN_KING,
    Race.ELVEN: Office.ELVEN_KING,
    Race.DWARVEN: Office.DWARVEN_KING,
    Race.ORCISH: Office.ORC_LORD,
    Race.DRAGONS: Office.DRAGON_LORD,
    Race.EAGLES: Office.EAGLE_KING,
    Race.WHALES: Office.WHALE_KING,
    Race.MERMISH: Office.MERMAN_KING,
    Race.ENTISH: Office.ENT_KING,
    Race.TROLLISH: Office.TROLL_KING,
    Race.WEREFOLK: Office.WERE_KING,
}

# The 7 special races whose own title requires the leader's Kingdom to
# own at least one province of that race -- the 4 core humanoid races
# have no such clause in the source.
RACE_TITLE_REQUIRES_OWNED_PROVINCE: frozenset[Race] = frozenset(
    {Race.DRAGONS, Race.EAGLES, Race.WHALES, Race.MERMISH, Race.ENTISH, Race.TROLLISH, Race.WEREFOLK}
)

# "Questa carica entra in gioco alla fine del turno N."
RACE_TITLE_TURN_GATE: dict[Race, int] = {
    Race.HUMAN: 4,
    Race.ELVEN: 4,
    Race.DWARVEN: 4,
    Race.ORCISH: 4,
    Race.DRAGONS: 6,
    Race.EAGLES: 6,
    Race.WHALES: 6,
    Race.MERMISH: 4,
    Race.ENTISH: 8,
    Race.TROLLISH: 6,
    Race.WEREFOLK: 6,
}

# "Per ogni unità di [rivali] distrutta ... si ottiene 0,5 punti."
RACE_TITLE_RIVAL_RACES: dict[Race, tuple[Race, ...]] = {
    Race.HUMAN: (Race.ORCISH,),
    Race.ELVEN: (Race.DWARVEN, Race.ORCISH),
    Race.DWARVEN: (Race.ELVEN, Race.ORCISH),
    Race.ORCISH: (Race.ELVEN, Race.DWARVEN, Race.HUMAN),
    Race.DRAGONS: (Race.EAGLES, Race.ELVEN, Race.DWARVEN),
    Race.EAGLES: (Race.ORCISH, Race.DRAGONS),
    Race.WHALES: (Race.MERMISH,),
    Race.MERMISH: (Race.WHALES,),
    Race.ENTISH: (Race.ORCISH, Race.DRAGONS),
    Race.TROLLISH: (Race.ELVEN, Race.DWARVEN),
    Race.WEREFOLK: (Race.HUMAN, Race.ELVEN),
}

# "Se si uccide uno di questi mostri si ottiene un punto: ..." -- see
# module docstring for why Race.WEREFOLK's own set is empty.
RACE_TITLE_NAMED_MONSTERS: dict[Race, frozenset[Monster]] = {
    Race.HUMAN: frozenset(),
    Race.ELVEN: frozenset(),
    Race.DWARVEN: frozenset(),
    Race.ORCISH: frozenset(),
    Race.DRAGONS: frozenset({Monster.S_DRAGON, Monster.R_DRAGON, Monster.GR_DRAGON, Monster.GO_DRAGON, Monster.B_DRAGON}),
    Race.EAGLES: frozenset({Monster.S_DRAGON, Monster.R_DRAGON, Monster.GR_DRAGON, Monster.GO_DRAGON, Monster.B_DRAGON}),
    Race.WHALES: frozenset({Monster.ELASMOSAURUS, Monster.GI_CLAM, Monster.GI_OCTOPUS, Monster.MERMAID}),
    Race.MERMISH: frozenset({Monster.ELASMOSAURUS, Monster.GI_CLAM, Monster.GI_OCTOPUS, Monster.MERMAID}),
    Race.ENTISH: frozenset({Monster.R_DRAGON, Monster.GR_DRAGON, Monster.B_DRAGON}),
    Race.TROLLISH: frozenset({Monster.S_DRAGON, Monster.GO_DRAGON}),
    # "Renegade priest" is Monster.WHITE_MAGE's own confirmed display
    # name (MONSTER_NAMES[Monster.WHITE_MAGE] == "Renegade Priest") --
    # not a naming gap after all, just not findable by grepping enum
    # *member* names for "RENEGADE" (several of this project's monster
    # enum members use a display name that doesn't match their own
    # Python identifier at all, e.g. WHITE_MAGE/NEC_MAGE/PSY_MAGE/
    # ILL_MAGE are all "Renegade ..." in MONSTER_NAMES).
    Race.WEREFOLK: frozenset({Monster.WHITE_MAGE}),
}

# "Se si possiede l'oggetto [nome] si ottengono due punti" -- None for
# the 3 races the source names no item for (Ent/Troll/Werefolk). Whale
# and Merman/Atlantis share the same real item (Horn of Neptune).
RACE_TITLE_LEGENDARY_ITEM: dict[Race, Treasure | None] = {
    Race.HUMAN: Treasure.LEADERSHIP_HUMAN,  # Excalibur
    Race.ELVEN: Treasure.LEADERSHIP_ELVEN,  # Bow of the Elven Kings
    Race.DWARVEN: Treasure.LEADERSHIP_DWARVEN,  # Axe of the Dwarven Lords
    Race.ORCISH: Treasure.LEADERSHIP_ORCISH,  # Scimitar of Orc Mastery
    Race.DRAGONS: Treasure.MONSTER_AID_DRAGON,  # Crown of Dragon Command
    Race.EAGLES: Treasure.MONSTER_AID_EAGLE,  # Feather of the Great Eagle
    Race.WHALES: Treasure.MONSTER_AID_WHALE,  # Horn of Neptune
    Race.MERMISH: Treasure.MONSTER_AID_WHALE,  # Horn of Neptune (shared with Whales)
    Race.ENTISH: None,
    Race.TROLLISH: None,
    Race.WEREFOLK: None,
}

_CRACK_OR_BETTER: tuple[Quality, ...] = (Quality.CRACK, Quality.ELITE)

# Local inverse of models.army_type.MONSTROUS_ARMY_RACE -- the same
# exact ArmyType<->Race correspondence worldgen.initial_armies.
# NATIVE_ARMY_TYPE already relies on (Phase 358), rebuilt here rather
# than importing from `worldgen` to keep this module's own dependency
# on the turn-execution layer, not the separate world-generation one.
_NATIVE_ARMY_TYPE: dict[Race, ArmyType] = {race: army_type for army_type, race in MONSTROUS_ARMY_RACE.items()}


def _crack_plus_units_commanded(state: GameState, leader_id: int, race: Race) -> int:
    """Live count of this race's own Crack-or-better units currently
    commanded by ``leader_id`` -- only resolvable for the 7 special
    races (see module docstring for the humanoid ArmyType/Race
    ambiguity that makes this a documented 0 for the other 4).
    """

    army_type = _NATIVE_ARMY_TYPE.get(race)
    if army_type is None:
        return 0
    return sum(
        1
        for army in state.armies.values()
        if army.commanded_by == leader_id and army.army_type is army_type and army.quality in _CRACK_OR_BETTER
    )


def _heroes_of_race_in_service(state: GameState, kingdom_id: int, race: Race) -> int:
    # "Per ogni eroe di [razza] che sotto il proprio servizio" -- a Hero,
    # not the King himself (this project's own is_king distinction
    # already separates the two leader categories throughout).
    return sum(
        1
        for leader in state.leaders.values()
        if leader.kingdom_id == kingdom_id and not leader.is_king and leader.race is race
    )


def _provinces_of_race_owned(state: GameState, kingdom_id: int, race: Race) -> int:
    return sum(
        1
        for province in state.provinces.values()
        if province.owner_kingdom_id == kingdom_id and province.race is race
    )


def _owns_legendary_item(state: GameState, leader_id: int, race: Race) -> bool:
    item = RACE_TITLE_LEGENDARY_ITEM.get(race)
    if item is None:
        return False
    return any(held.treasure is item for held in state.items_held_by(leader_id))


def race_title_merit_points(state: GameState, leader: LeaderState, race: Race) -> float:
    """One race title's full Merit Point score for ``leader`` -- see
    module docstring for every term. Applies the special races' own
    "0 without an owned province" prerequisite directly (Kingdom-scoped,
    so an independent Hero always reads 0 for those 7 races); the turn
    gate is enforced separately, by ``turn/office_holder.py
    resolve_office_holder()``.
    """

    if race in RACE_TITLE_REQUIRES_OWNED_PROVINCE:
        if leader.kingdom_id is None or _provinces_of_race_owned(state, leader.kingdom_id, race) == 0:
            return 0

    tally = leader.race_title_tally.get(race, RaceTitleTally())
    points: float = tally.front_line_battles_won_points - tally.front_line_battles_lost_points
    points += _crack_plus_units_commanded(state, leader.leader_id, race)

    if leader.is_king and leader.kingdom_id is not None:
        points += _heroes_of_race_in_service(state, leader.kingdom_id, race)
        points += _provinces_of_race_owned(state, leader.kingdom_id, race)

    points += 0.5 * tally.rival_race_units_destroyed
    points += tally.monsters_killed_in_race_province
    points += tally.named_monster_kills

    if _owns_legendary_item(state, leader.leader_id, race):
        points += 2

    return points
