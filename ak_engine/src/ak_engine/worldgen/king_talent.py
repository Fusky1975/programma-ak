"""The King's own initial skill/aptitude table (Phase 430) -- rulebook
[2.1] "IL RE", supplied verbatim by the user (their own copy of the
rulebook, not a Pascal source):

    "All'inizio della partita, il giocatore assegna al proprio Re, nome,
    razza, temperamento, allineamento e quattro livelli di abilita' da
    distribuire sui vari Talenti. Il Re puo' cioe' iniziare con quattro
    Talenti al livello 1 o due talenti al livello 2 e cosi' via, ma non
    puo' assegnare piu' di 2 livelli a ciascun Talento. [...] I Re
    ricevono anche automaticamente un modificatore +1 alla loro abilita'
    di Mischia, Tiro con l'Arco e Conoscenza, come conseguenza
    dell'educazione e dell'addestramento regali. I Re Divini ricevono un
    modificatore +1 alla loro abilita' di Magia Bianca e partono con
    potenzialita' 0 in Negromanzia. I Re Non-Morti, invece ricevono un
    modificatore +1 alla loro abilita' in Negromanzia e partono con
    potenzialita' 0 in Magia Bianca. Le potenzialita' di un Re e' sempre
    di 2 punti piu' alta del suo livello di abilita' iniziale, con
    massimo di 5 per i Talenti Speciali."

Distinct from `worldgen/hero_talent_generation.py` on purpose -- that
module's own docstring already scopes itself to "every non-King leader
slot" and rolls a *random* primary ability (`roll_primary_ability()`).
A King's own primary abilities are a genuine player choice, not a
Pascal-RNG draw, so this module takes that choice as an input
(`talent_allocation`) instead of rolling one -- and every other part of
the formula here is fully deterministic (no `PascalRandom` parameter at
all), unlike the Hero formula's own random `roll_aptitude()`.

**Independently corroborated, not a fresh guess**: `models/kingdom.py
SkillTable`'s own docstring (Phase 21, written long before this rule
text was supplied) already stated this exact formula from a different
angle -- "a King's starting aptitude is always 2 higher than his
initial skill, to a maximum of 5" plus the same Divine/Undead
overrides -- and had already verified it against a real ``AK3__T1.K1``
skill line (`WHITE = (0, 0)`, `NECROMANCY = (3, 5)` for an Undead King).
This module is the first time that already-confirmed formula is
actually implemented as callable code.

**The "max 5 for Special Talents" cap needs no separate branch**: a
King's own maximum possible skill in any single Ability is 2 (allocated)
+ 1 (an automatic-bonus Ability) = 3, so `skill + 2` never exceeds 5 for
*any* Ability, "Special Talent" or not -- `min(5, skill + 2)` alone
already satisfies the rulebook's own note in every case.

**Not implemented here**: which Abilities count as the rulebook's own
"Talenti Speciali" is never actually needed by this formula (see above)
-- `worldgen/hero_talent_generation.py FAVORED_ALIGNMENT`'s own 10
alignment-favored Abilities are the likely referent (2 per alignment,
Good..Evil, matching the rulebook's own "sono due per ogni allineamento
da Buono a Malvagio"), but nothing here depends on identifying them.
"""

from __future__ import annotations

from ak_engine.models.alignment import Alignment
from ak_engine.models.enums import Ability
from ak_engine.models.kingdom import SkillTable

MAX_TALENT_POINTS = 4
MAX_POINTS_PER_ABILITY = 2

# "un modificatore +1 alla loro abilita' di Mischia, Tiro con l'Arco e
# Conoscenza" -- every King, unconditionally.
AUTOMATIC_BONUS_ABILITIES: tuple[Ability, ...] = (Ability.MELEE, Ability.ARCHERY, Ability.SAGE)


def build_king_skill_table(talent_allocation: dict[Ability, int], alignment: Alignment) -> SkillTable:
    """The player's own ``talent_allocation`` (skill points per Ability,
    each 0..``MAX_POINTS_PER_ABILITY``, summing to at most
    ``MAX_TALENT_POINTS``), plus the automatic bonuses and Divine/Undead
    overrides from this module's own docstring, yielding a full
    ``SkillTable`` with both skill and aptitude populated for all 15
    Abilities.
    """

    total = sum(talent_allocation.values())
    if total > MAX_TALENT_POINTS:
        raise ValueError(f"talent_allocation totals {total} points, max is {MAX_TALENT_POINTS}")
    for ability, points in talent_allocation.items():
        if points < 0:
            raise ValueError(f"{ability} has a negative point count")
        if points > MAX_POINTS_PER_ABILITY:
            raise ValueError(f"{ability} has {points} points, max is {MAX_POINTS_PER_ABILITY} per Ability")

    skill = {ability: talent_allocation.get(ability, 0) for ability in Ability}
    for ability in AUTOMATIC_BONUS_ABILITIES:
        skill[ability] += 1
    if alignment is Alignment.DIVINE:
        skill[Ability.WHITE] += 1
    elif alignment is Alignment.UNDEAD:
        skill[Ability.NECROMANCY] += 1

    raw_values = [0] * 31
    for ability in Ability:
        level = skill[ability]
        aptitude = min(5, level + 2)
        if alignment is Alignment.DIVINE and ability is Ability.NECROMANCY:
            aptitude = 0
        elif alignment is Alignment.UNDEAD and ability is Ability.WHITE:
            aptitude = 0
        raw_values[ability.value * 2] = level
        raw_values[ability.value * 2 + 1] = aptitude

    return SkillTable(raw_values=raw_values)
