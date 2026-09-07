"""Character Initiative -- the general rulebook concept (quoted in full):
"Il coefficiente di iniziativa di ciascun personaggio equivale alla somma
dei punteggi nei suoi vari Talenti, con Marcia contato 3 volte, più tutti
gli aumenti derivanti dal possesso di oggetti magici e conoscenza
speciali... Il coefficiente d'iniziativa di ogni personaggio è indicato
nel Resoconto del turno insieme alle abilità e alla potenzialità nei vari
Talenti."

Not to be confused with `turn/encounter.py`'s own narrower [5.0]
per-combat-tactic "initiative" ("the character whose skill level in the
ability relevant to the employed tactic is higher acts first this
round") -- that's a different, already-implemented mechanic
(`_acts_first()`), scoped to one personal-combat round. This module is
the general, character-wide score the rulebook itself describes as
fundamental to *turn-wide* action sequencing and now shown "nel
Resoconto del turno" (the turn report) -- Phase 311 is this project's
first real consumer (contested-province simultaneous-invasion priority,
`turn/battle_orchestrator.py fight_multi_attacker_battle()`).

**"Con Marcia contato 3 volte"**: March's own score is included at 3x
weight rather than 1x -- implemented as the ordinary sum over every
`Ability` plus two *extra* copies of March's own level, equivalent to
counting it three times in the sum.

**"Più tutti gli aumenti derivanti dal possesso di oggetti magici e
conoscenza speciali"**: "conoscenza speciali" (special knowledge) is
this project's own already-established term for Discoveries --
`turn/discovery_effects.py effective_skill_level()` already folds
Discovery-derived ability bonuses into every per-ability read, so
summing that function over every `Ability` picks those up for free.
**Stale as of Phase 759 -- the same is true of the magic-item half**:
this paragraph used to claim "no item field, no formula" existed for a
magic-item-derived ability bonus, predating Phase 534's `ability_bonus_
from_items()` (`M_Skill`'s own "+1 per copy held" formula, already
folded into `effective_skill_level()` alongside the Discovery bonus,
both capped together at `MAX_SKILL_LEVEL`). Both halves of "oggetti
magici e conoscenza speciali" therefore already reach this module's own
sum for free, through the one shared function -- nothing further to
wire.
"""

from __future__ import annotations

from ak_engine.models.enums import Ability
from ak_engine.models.game_state import GameState, LeaderState
from ak_engine.turn.discovery_effects import effective_skill_level


def character_initiative(state: GameState, leader: LeaderState) -> int:
    """The character-wide Initiative score -- see module docstring for the
    full sourced formula. Every real skill read goes through
    ``effective_skill_level()``, so a leader with ``skills is None``
    (Phase 30's own "no data" placeholder) reads a flat 0 across every
    Ability, the same fallback every other consumer of that function
    already uses.
    """

    total = sum(effective_skill_level(state, leader, ability) for ability in Ability)
    return total + 2 * effective_skill_level(state, leader, Ability.MARCH)
