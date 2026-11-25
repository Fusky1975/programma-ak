"""Per-species guardian-monster Special Encounter Plans -- Phase 178, project-original.

`Desktop/Piani speciali d'incontro dei mostri.txt` (supplied 2026-07-16,
confirmed by the user to be their own compilation, the same "user
authors replacement content for a confirmed-unsourced gap" pattern
`models/monster.py`'s own Phase 154/176/177 addenda already use) gives
every one of the 60 real monster species its own Special Encounter
Plan: an ordered tactic list, exactly like a player-submitted Search
Encounter Plan (`turn/search_decode.py SearchTactic`/`SearchRequest`),
but chosen by the game itself for the guardian rather than typed by a
player. Several species have 2-6 percentage-weighted plan *variants*
instead of one fixed plan (rolled on a d100), and four species (Gold
Dragon, Titan, Renegade Necromancer, Witch) have one further variant
that's used unconditionally instead of the normal roll whenever the
attacking hero or King is Undead-aligned.

**The general "list runs out -> default to Melee" rule, confirmed
directly by the user (project author) before this file was supplied**,
quoted in full: "Quando finiscono le azioni che vengono messe nel piano
d'incontro il personaggio inizia a usare automaticamente il comando ME
... Il personaggio di default continua a usare il comando ME a mischia
finche' muore lui o il mostro." ("When the actions listed in the
Encounter Plan run out, the character automatically starts using the ME
command ... By default the character keeps using ME in melee until
either he or the monster dies.") Every single line in the source file
ends in the literal words "ME fino alla fine" ("ME until the end") --
directly confirming this same default applies to a monster's own plan,
not just a player's. Since `turn/encounter.py resolve_melee_duel()`
already resolves an entire Melee tactic to the death in one call (its
own docstring: "Melee always ends in a winner"), "ME fino alla fine" is
modeled here as nothing more than one final, ordinary `Maneuver.MELEE`
`SearchTactic` at the end of each variant's own tuple -- no special
"repeat forever" sentinel is needed, because a plain trailing `MELEE`
tactic already *is* that behavior everywhere else in this project.

**The `CA-XX` two-letter Cast notation** is decoded via `models/enums.py
SPELL_BY_ABBREVIATION` (Phase 178, itself sourced from `CTBOTH.PAS`'s
own `spab` abbreviation table) -- e.g. `CA-HA` -> `Spell.HAND_OF_DEATH`,
`CA-CH` -> `Spell.CHARM`. Every one of the 11 distinct spell tokens this
source file uses (`HA, TE, PS, HO, IN, MI, IC, FI, SP, CH, CO`) resolves
to either one of the 10 "Personal-Combat-only" spells `turn/
cast_execution.py`'s own module docstring already names as unmodeled
(`Hand_Of_Death, Telek_Storm, Psychic_Blast, Holy_Symbol, Invisibility,
Mirror_Image, Ice_Suspend, Fireball, Spiritwrack, Control_Undead`) or to
`Charm` -- an exact, internally-consistent confirmation that these
really are the personal-combat spell set the rulebook restricts
Encounter Plans to, not a mistranscription.

**Stale as of Phase 685 -- this used to say a `Maneuver.CAST` entry
rolled from a monster's own plan was "inert data," deliberately not
wired to any combat effect.** That was true as of Phase 178, but
`turn/search_execution.py _resolve_monster_casts()` (Phase 238/293)
has since walked a guardian's own `monster_plan` and dispatched every
real `CAST` tactic through the same personal-combat spell dispatcher a
player's own `CAST` tactic uses (`caster_is_leader=False`) -- nobody
came back to correct this module's own note when that landed.

**What Phase 178 does wire into `turn/search_execution.py`**, since it
needs no new spell-effect engine: a monster's own rolled plan is
checked for a bare `Maneuver.SHOOT` (`FI`) entry, independent of
whatever the *player's* own Encounter Plan says. Per the user's own
confirmation, each side follows its own plan -- so a monster whose plan
opens with `FI` (e.g. Titan, Red Dragon) gets to fire its own missile
attack even if the attacking hero's plan never lists `SHOOT` at all
(previously, Fire Arrow only ever happened if the *hero's* plan asked
for it). This still resolves through the existing, single, symmetric
`resolve_fire_arrow_duel()` call (Phase 170) -- at most one Fire Arrow
phase total per encounter, matching the already-confirmed "only a
single FI order can ever appear" rule (Phase 173), just now triggered
by *either* side wanting it rather than only the hero's own plan.
`search_execution.py`'s own docstring addendum has the wiring detail.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from ak_engine.models.enums import Ability, Maneuver, Spell
from ak_engine.models.monster import (
    MONSTER_MAGIC_ABILITIES,
    MONSTER_RUNTIME_PROFILE,
    SPIRITWRACK_UNDEAD_MONSTERS,
    Monster,
    MonsterIntelligence,
)
from ak_engine.models.temper import Temper
from ak_engine.turn.search_decode import SearchTactic


def _shoot() -> SearchTactic:
    return SearchTactic(maneuver=Maneuver.SHOOT)


def _melee() -> SearchTactic:
    return SearchTactic(maneuver=Maneuver.MELEE)


def _cast(spell: Spell) -> SearchTactic:
    return SearchTactic(maneuver=Maneuver.CAST, sub_object=int(spell))


@dataclass(frozen=True, slots=True)
class MonsterEncounterPlanVariant:
    tactics: tuple[SearchTactic, ...]
    percent: int  # weight among a species' own normal-roll variants; sums to 100. 100 for the Undead-only override (never part of the normal pool).


def _v(percent: int, *tactics: SearchTactic) -> MonsterEncounterPlanVariant:
    return MonsterEncounterPlanVariant(tactics=tactics, percent=percent)


@dataclass(frozen=True, slots=True)
class MonsterEncounterPlan:
    variants: tuple[MonsterEncounterPlanVariant, ...]  # normal weighted roll pool, sums to 100
    undead_variant: MonsterEncounterPlanVariant | None = None  # used at 100% instead, when the attacker is Undead-aligned


# Phase 178 -- project-original, Desktop/Piani speciali d'incontro dei
# mostri.txt (2026-07-16). See module docstring for the CA-XX decode and
# the "ME fino alla fine" -> plain trailing MELEE tactic convention.
MONSTER_ENCOUNTER_PLANS: dict[Monster, MonsterEncounterPlan] = {
    Monster.GRYPHON: MonsterEncounterPlan(variants=(_v(100, _melee()),)),
    Monster.GIANT: MonsterEncounterPlan(variants=(_v(100, _shoot(), _melee()),)),
    Monster.GARGOYLE: MonsterEncounterPlan(variants=(_v(100, _melee()),)),
    Monster.TROLL: MonsterEncounterPlan(variants=(_v(100, _melee()),)),
    Monster.SPECTRE: MonsterEncounterPlan(variants=(_v(100, _cast(Spell.HAND_OF_DEATH), _melee()),)),
    Monster.ELASMOSAURUS: MonsterEncounterPlan(variants=(_v(100, _melee()),)),
    Monster.ROC: MonsterEncounterPlan(variants=(_v(100, _melee()),)),
    Monster.COUATL: MonsterEncounterPlan(
        variants=(_v(100, _cast(Spell.TELEK_STORM), _cast(Spell.PSYCHIC_BLAST), _melee()),)
    ),
    Monster.GI_EAGLE: MonsterEncounterPlan(variants=(_v(100, _melee()),)),
    Monster.SPHINX: MonsterEncounterPlan(variants=(_v(100, _cast(Spell.HAND_OF_DEATH), _melee()),)),
    Monster.R_DRAGON: MonsterEncounterPlan(variants=(_v(100, _shoot(), _melee()),)),
    Monster.B_DRAGON: MonsterEncounterPlan(
        variants=(_v(100, _cast(Spell.PSYCHIC_BLAST), _shoot(), _melee()),)
    ),
    Monster.S_DRAGON: MonsterEncounterPlan(
        variants=(
            _v(10, _cast(Spell.HOLY_SYMBOL), _shoot(), _melee()),
            _v(10, _cast(Spell.PSYCHIC_BLAST), _shoot(), _melee()),
            _v(10, _cast(Spell.FIREBALL), _shoot(), _melee()),
            _v(10, _cast(Spell.PSYCHIC_BLAST), _shoot(), _cast(Spell.INVISIBILITY), _melee()),
            _v(10, _cast(Spell.HOLY_SYMBOL), _shoot(), _cast(Spell.INVISIBILITY), _melee()),
            _v(10, _cast(Spell.ICE_SUSPEND), _shoot(), _cast(Spell.PSYCHIC_BLAST), _melee()),
            _v(10, _cast(Spell.ICE_SUSPEND), _shoot(), _cast(Spell.INVISIBILITY), _melee()),
            _v(10, _cast(Spell.PSYCHIC_BLAST), _shoot(), _cast(Spell.FIREBALL), _melee()),
            _v(10, _cast(Spell.SPIRITWRACK), _shoot(), _cast(Spell.PSYCHIC_BLAST), _melee()),
            _v(10, _cast(Spell.SPIRITWRACK), _shoot(), _cast(Spell.FIREBALL), _melee()),
        )
    ),
    Monster.GO_DRAGON: MonsterEncounterPlan(
        variants=(
            _v(20, _cast(Spell.SPIRITWRACK), _shoot(), _cast(Spell.HOLY_SYMBOL), _melee()),
            _v(15, _cast(Spell.SPIRITWRACK), _shoot(), _cast(Spell.HAND_OF_DEATH), _melee()),
            _v(20, _cast(Spell.HAND_OF_DEATH), _shoot(), _cast(Spell.HOLY_SYMBOL), _melee()),
            _v(15, _cast(Spell.HAND_OF_DEATH), _shoot(), _melee()),
            _v(15, _cast(Spell.HOLY_SYMBOL), _shoot(), _cast(Spell.HAND_OF_DEATH), _melee()),
            _v(15, _cast(Spell.SPIRITWRACK), _shoot(), _melee()),
        ),
        undead_variant=_v(100, _cast(Spell.CONTROL_UNDEAD), _shoot(), _cast(Spell.HOLY_SYMBOL), _melee()),
    ),
    Monster.GR_DRAGON: MonsterEncounterPlan(
        variants=(
            _v(15, _cast(Spell.TELEK_STORM), _shoot(), _cast(Spell.INVISIBILITY), _melee()),
            _v(20, _cast(Spell.TELEK_STORM), _shoot(), _cast(Spell.PSYCHIC_BLAST), _melee()),
            _v(15, _cast(Spell.MIRROR_IMAGE), _shoot(), _cast(Spell.PSYCHIC_BLAST), _melee()),
            _v(15, _cast(Spell.PSYCHIC_BLAST), _shoot(), _cast(Spell.INVISIBILITY), _melee()),
            _v(20, _cast(Spell.TELEK_STORM), _shoot(), _cast(Spell.FIREBALL), _melee()),
            _v(15, _cast(Spell.PSYCHIC_BLAST), _shoot(), _cast(Spell.FIREBALL), _melee()),
        )
    ),
    Monster.GI_WORM: MonsterEncounterPlan(variants=(_v(100, _melee()),)),
    Monster.TITAN: MonsterEncounterPlan(
        variants=(
            _v(10, _cast(Spell.SPIRITWRACK), _shoot(), _cast(Spell.FIREBALL), _melee()),
            _v(10, _cast(Spell.SPIRITWRACK), _shoot(), _cast(Spell.INVISIBILITY), _melee()),
            _v(10, _cast(Spell.ICE_SUSPEND), _shoot(), _cast(Spell.HOLY_SYMBOL), _melee()),
            _v(10, _cast(Spell.ICE_SUSPEND), _shoot(), _cast(Spell.INVISIBILITY), _melee()),
            _v(10, _cast(Spell.HOLY_SYMBOL), _shoot(), _cast(Spell.FIREBALL), _melee()),
            _v(10, _cast(Spell.HOLY_SYMBOL), _shoot(), _cast(Spell.INVISIBILITY), _melee()),
            _v(10, _cast(Spell.FIREBALL), _shoot(), _cast(Spell.INVISIBILITY), _melee()),
            _v(10, _cast(Spell.MIRROR_IMAGE), _shoot(), _cast(Spell.FIREBALL), _melee()),
            _v(10, _cast(Spell.MIRROR_IMAGE), _shoot(), _cast(Spell.HOLY_SYMBOL), _cast(Spell.FIREBALL), _melee()),
            _v(10, _cast(Spell.FIREBALL), _shoot(), _cast(Spell.HOLY_SYMBOL), _melee()),
        ),
        undead_variant=_v(
            100, _cast(Spell.CONTROL_UNDEAD), _shoot(), _cast(Spell.HOLY_SYMBOL), _cast(Spell.FIREBALL), _melee()
        ),
    ),
    Monster.BIGFOOT: MonsterEncounterPlan(variants=(_v(100, _melee()),)),
    Monster.ARCHER: MonsterEncounterPlan(variants=(_v(100, _shoot(), _melee()),)),
    Monster.SWORDSMAN: MonsterEncounterPlan(variants=(_v(100, _melee()),)),
    Monster.WHITE_MAGE: MonsterEncounterPlan(
        variants=(
            _v(25, _cast(Spell.SPIRITWRACK), _cast(Spell.HOLY_SYMBOL), _melee()),
            _v(25, _cast(Spell.SPIRITWRACK), _cast(Spell.HAND_OF_DEATH), _melee()),
            _v(25, _cast(Spell.HOLY_SYMBOL), _cast(Spell.INVISIBILITY), _melee()),
            _v(25, _cast(Spell.HOLY_SYMBOL), _cast(Spell.HAND_OF_DEATH), _melee()),
        )
    ),
    Monster.NEC_MAGE: MonsterEncounterPlan(
        variants=(_v(100, _cast(Spell.HAND_OF_DEATH), _melee()),),
        undead_variant=_v(100, _cast(Spell.CONTROL_UNDEAD), _melee()),
    ),
    Monster.ELE_MAGE: MonsterEncounterPlan(
        variants=(_v(100, _cast(Spell.ICE_SUSPEND), _cast(Spell.FIREBALL), _melee()),)
    ),
    Monster.PSY_MAGE: MonsterEncounterPlan(
        variants=(
            _v(25, _cast(Spell.TELEK_STORM), _cast(Spell.PSYCHIC_BLAST), _melee()),
            _v(15, _cast(Spell.TELEK_STORM), _cast(Spell.HOLY_SYMBOL), _melee()),
            _v(10, _cast(Spell.PSYCHIC_BLAST), _cast(Spell.INVISIBILITY), _melee()),
            _v(10, _cast(Spell.PSYCHIC_BLAST), _cast(Spell.HOLY_SYMBOL), _melee()),
            _v(10, _cast(Spell.TELEK_STORM), _cast(Spell.MIRROR_IMAGE), _melee()),
            _v(10, _cast(Spell.PSYCHIC_BLAST), _cast(Spell.MIRROR_IMAGE), _melee()),
            _v(10, _cast(Spell.TELEK_STORM), _cast(Spell.SPIRITWRACK), _melee()),
            _v(10, _cast(Spell.PSYCHIC_BLAST), _cast(Spell.SPIRITWRACK), _melee()),
        )
    ),
    Monster.ILL_MAGE: MonsterEncounterPlan(
        variants=(
            _v(25, _cast(Spell.MIRROR_IMAGE), _cast(Spell.INVISIBILITY), _melee()),
            _v(25, _cast(Spell.MIRROR_IMAGE), _cast(Spell.PSYCHIC_BLAST), _melee()),
            _v(20, _cast(Spell.TELEK_STORM), _cast(Spell.INVISIBILITY), _melee()),
            _v(15, _cast(Spell.PSYCHIC_BLAST), _cast(Spell.INVISIBILITY), _melee()),
            _v(15, _cast(Spell.TELEK_STORM), _cast(Spell.MIRROR_IMAGE), _melee()),
        )
    ),
    Monster.WITCH: MonsterEncounterPlan(
        variants=(
            _v(50, _cast(Spell.HAND_OF_DEATH), _cast(Spell.PSYCHIC_BLAST), _melee()),
            _v(25, _cast(Spell.TELEK_STORM), _cast(Spell.HAND_OF_DEATH), _melee()),
            _v(25, _cast(Spell.PSYCHIC_BLAST), _cast(Spell.HAND_OF_DEATH), _melee()),
        ),
        undead_variant=_v(100, _cast(Spell.CONTROL_UNDEAD), _cast(Spell.PSYCHIC_BLAST), _melee()),
    ),
    Monster.DRYAD: MonsterEncounterPlan(
        variants=(
            _v(40, _cast(Spell.TELEK_STORM), _cast(Spell.PSYCHIC_BLAST), _melee()),
            _v(
                30,
                _cast(Spell.PSYCHIC_BLAST),
                _melee(),
                _melee(),
                _melee(),
                _melee(),
                _melee(),
                _cast(Spell.CHARM),
                _melee(),
            ),
            _v(
                30,
                _cast(Spell.TELEK_STORM),
                _melee(),
                _melee(),
                _melee(),
                _melee(),
                _melee(),
                _cast(Spell.CHARM),
                _melee(),
            ),
        )
    ),
    Monster.CENTAUR: MonsterEncounterPlan(variants=(_v(100, _shoot(), _melee()),)),
    Monster.GENIE: MonsterEncounterPlan(
        variants=(
            _v(30, _cast(Spell.MIRROR_IMAGE), _cast(Spell.INVISIBILITY), _melee()),
            _v(20, _cast(Spell.TELEK_STORM), _cast(Spell.MIRROR_IMAGE), _melee()),
            _v(30, _cast(Spell.MIRROR_IMAGE), _cast(Spell.PSYCHIC_BLAST), _melee()),
            _v(20, _cast(Spell.TELEK_STORM), _cast(Spell.PSYCHIC_BLAST), _melee()),
        )
    ),
    Monster.GOLEM: MonsterEncounterPlan(variants=(_v(100, _melee()),)),
    Monster.BASILISK: MonsterEncounterPlan(variants=(_v(100, _shoot(), _melee()),)),
    Monster.MEDUSA: MonsterEncounterPlan(variants=(_v(100, _shoot(), _melee()),)),
    Monster.BAL_DEMON: MonsterEncounterPlan(variants=(_v(100, _cast(Spell.HAND_OF_DEATH), _melee()),)),
    Monster.MAR_DEMON: MonsterEncounterPlan(
        variants=(
            _v(40, _cast(Spell.TELEK_STORM), _cast(Spell.PSYCHIC_BLAST), _melee()),
            _v(30, _cast(Spell.PSYCHIC_BLAST), _cast(Spell.INVISIBILITY), _melee()),
            _v(30, _cast(Spell.TELEK_STORM), _cast(Spell.INVISIBILITY), _melee()),
        )
    ),
    Monster.SUCCUBUS: MonsterEncounterPlan(
        variants=(_v(100, _cast(Spell.TELEK_STORM), _cast(Spell.PSYCHIC_BLAST), _melee()),)
    ),
    Monster.RAKSHASHA: MonsterEncounterPlan(
        variants=(
            _v(40, _cast(Spell.MIRROR_IMAGE), _cast(Spell.INVISIBILITY), _melee()),
            _v(30, _cast(Spell.MIRROR_IMAGE), _cast(Spell.HAND_OF_DEATH), _melee()),
            _v(30, _cast(Spell.HAND_OF_DEATH), _cast(Spell.INVISIBILITY), _melee()),
        )
    ),
    Monster.ICE_DEVIL: MonsterEncounterPlan(
        variants=(
            _v(30, _cast(Spell.ICE_SUSPEND), _cast(Spell.PSYCHIC_BLAST), _melee()),
            _v(20, _cast(Spell.TELEK_STORM), _cast(Spell.FIREBALL), _melee()),
            _v(30, _cast(Spell.ICE_SUSPEND), _cast(Spell.FIREBALL), _melee()),
            _v(20, _cast(Spell.TELEK_STORM), _cast(Spell.PSYCHIC_BLAST), _melee()),
        )
    ),
    Monster.BONE_DEVIL: MonsterEncounterPlan(variants=(_v(100, _cast(Spell.HAND_OF_DEATH), _melee()),)),
    Monster.IMP: MonsterEncounterPlan(variants=(_v(100, _cast(Spell.INVISIBILITY), _melee()),)),
    Monster.WEREWOLF: MonsterEncounterPlan(variants=(_v(100, _melee()),)),
    Monster.CHIMERA: MonsterEncounterPlan(variants=(_v(100, _shoot(), _melee()),)),
    Monster.HYDRA: MonsterEncounterPlan(variants=(_v(100, _melee()),)),
    Monster.BEHOLDER: MonsterEncounterPlan(
        variants=(
            _v(40, _cast(Spell.TELEK_STORM), _cast(Spell.HAND_OF_DEATH), _melee()),
            _v(20, _cast(Spell.TELEK_STORM), _cast(Spell.PSYCHIC_BLAST), _cast(Spell.HAND_OF_DEATH), _melee()),
            _v(40, _cast(Spell.PSYCHIC_BLAST), _cast(Spell.HAND_OF_DEATH), _melee()),
        )
    ),
    Monster.MINOTAUR: MonsterEncounterPlan(variants=(_v(100, _melee()),)),
    Monster.GI_WOLVERINE: MonsterEncounterPlan(variants=(_v(100, _melee()),)),
    Monster.TREANT: MonsterEncounterPlan(variants=(_v(100, _shoot(), _melee()),)),
    Monster.GI_AMOEBA: MonsterEncounterPlan(variants=(_v(100, _melee()),)),
    Monster.GI_P_MANTIS: MonsterEncounterPlan(variants=(_v(100, _melee()),)),
    Monster.GI_SCORPION: MonsterEncounterPlan(variants=(_v(100, _melee()),)),
    Monster.GI_WASP: MonsterEncounterPlan(variants=(_v(100, _melee()),)),
    Monster.GI_SPIDER: MonsterEncounterPlan(variants=(_v(100, _melee()),)),
    Monster.GHOST: MonsterEncounterPlan(variants=(_v(100, _melee()),)),
    Monster.VAMPIRE: MonsterEncounterPlan(
        variants=(
            _v(60, _cast(Spell.TELEK_STORM), _cast(Spell.PSYCHIC_BLAST), _melee()),
            _v(40, _cast(Spell.PSYCHIC_BLAST), _melee()),
        )
    ),
    Monster.MUMMY: MonsterEncounterPlan(variants=(_v(100, _melee()),)),
    Monster.BANSHEE: MonsterEncounterPlan(variants=(_v(100, _cast(Spell.PSYCHIC_BLAST), _melee()),)),
    Monster.LICH: MonsterEncounterPlan(variants=(_v(100, _cast(Spell.HAND_OF_DEATH), _melee()),)),
    Monster.GI_OCTOPUS: MonsterEncounterPlan(variants=(_v(100, _melee()),)),
    Monster.GI_CLAM: MonsterEncounterPlan(variants=(_v(100, _melee()),)),
    Monster.GW_WHALE: MonsterEncounterPlan(variants=(_v(100, _melee()),)),
    Monster.MERMAID: MonsterEncounterPlan(
        variants=(
            _v(30, _cast(Spell.PSYCHIC_BLAST), _cast(Spell.HAND_OF_DEATH), _melee()),
            _v(
                35,
                _cast(Spell.HAND_OF_DEATH),
                _melee(),
                _melee(),
                _melee(),
                _melee(),
                _cast(Spell.CHARM),
                _melee(),
            ),
            _v(
                35,
                _cast(Spell.ICE_SUSPEND),
                _cast(Spell.HAND_OF_DEATH),
                _melee(),
                _melee(),
                _melee(),
                _melee(),
                _cast(Spell.CHARM),
                _melee(),
            ),
        )
    ),
}


# --- Generated, varied plans for the intelligent monsters (2026-11-25, user request) -----------------
#
# "Creiamo dei piani d'incontro per loro i più intelligenti e variabili possibile." User choices: only
# more random variants (the plan does not look at the opponent), only the intelligent monsters
# (Medium intelligence or better; Animal and Mechanical ones keep fighting in Melee), and an
# intelligent monster may flee when it is losing but never talks.
#
# An eligible monster gets, in ``GENERATED_PLAN_CHANCE`` of its encounters, a plan built at random
# from what it can really do: only spells of the schools it has a talent in, no more distinct
# spells per school than its level allows (1 at level 1, 2 from level 2), each spell at most once;
# a missile attack only if its own table plan has one; and the order follows the tactical sense of
# each spell (deny magic first, buff, damage, stun/squeeze last before the fight) with some noise.
# Cautious and Cowardly ones sometimes end the plan with a wounded retreat, a hit-and-run
# ("MELEE, MELEE, FLEE": flee only once at half hit points or less, otherwise keep fighting).

GENERATED_PLAN_CHANCE = 0.6
INTELLIGENT_MONSTERS_MIN_INTELLIGENCE = (MonsterIntelligence.MEDIUM, MonsterIntelligence.HIGH, MonsterIntelligence.GODLIKE)
GENERATED_PLAN_MAX_CASTS = 4
GENERATED_PLAN_CAST_COUNT_WEIGHTS = (3, 5, 3, 1)  # for 1, 2, 3, 4 spells
GENERATED_PLAN_SHOOT_CHANCE = 0.85
GENERATED_PLAN_RETREAT_CHANCE = 0.35
GENERATED_PLAN_LURE_CHARM_CHANCE = 0.25  # Psychic 3+: a few rounds of Melee, then Charm (Dryad/Mermaid style)

# Lower = earlier. Deny magic (Spiritwrack), freeze, summon, buff, then damage, then the stun and the squeeze.
_SPELL_ORDER_PRIORITY: dict[Spell, int] = {
    Spell.CONTROL_UNDEAD: 0,
    Spell.SPIRITWRACK: 0,
    Spell.ICE_SUSPEND: 1,
    Spell.MIRROR_IMAGE: 1,
    Spell.HOLY_SYMBOL: 2,
    Spell.INVISIBILITY: 2,
    Spell.FIREBALL: 3,
    Spell.TELEK_STORM: 3,
    Spell.PSYCHIC_BLAST: 4,
    Spell.HAND_OF_DEATH: 5,
}
_SPELL_SCHOOL: dict[Spell, Ability] = {
    Spell.HOLY_SYMBOL: Ability.WHITE,
    Spell.SPIRITWRACK: Ability.WHITE,
    Spell.PSYCHIC_BLAST: Ability.PSYCHIC,
    Spell.TELEK_STORM: Ability.PSYCHIC,
    Spell.INVISIBILITY: Ability.ILLUSION,
    Spell.MIRROR_IMAGE: Ability.ILLUSION,
    Spell.FIREBALL: Ability.ELEMENTAL,
    Spell.ICE_SUSPEND: Ability.ELEMENTAL,
    Spell.HAND_OF_DEATH: Ability.NECROMANCY,
    Spell.CONTROL_UNDEAD: Ability.NECROMANCY,
}


def _flee() -> SearchTactic:
    return SearchTactic(maneuver=Maneuver.FLEE)


def _combat_cast_slots(level: int) -> int:
    return 1 if level <= 1 else 2  # turn/encounter.py combat_cast_slots()


def _table_plans_use_missile(monster: Monster) -> bool:
    plan = MONSTER_ENCOUNTER_PLANS.get(monster)
    return plan is not None and any(t.maneuver is Maneuver.SHOOT for v in plan.variants for t in v.tactics)


def _table_plans_always_shoot(monster: Monster) -> bool:
    plan = MONSTER_ENCOUNTER_PLANS.get(monster)
    return plan is not None and all(any(t.maneuver is Maneuver.SHOOT for t in v.tactics) for v in plan.variants)


def monster_gets_generated_plans(monster: Monster) -> bool:
    """Intelligent (Medium or better) monsters that have something to vary: a spell talent, a missile
    attack, or a Cautious/Cowardly temper (a wounded retreat)."""

    profile = MONSTER_RUNTIME_PROFILE.get(monster)
    if profile is None or profile.intelligence not in INTELLIGENT_MONSTERS_MIN_INTELLIGENCE:
        return False
    return bool(MONSTER_MAGIC_ABILITIES.get(monster)) or _table_plans_use_missile(monster) or profile.temper in (
        Temper.CAUTIOUS,
        Temper.COWARDLY,
    )


def generate_monster_encounter_plan(
    monster: Monster, rng: random.Random, *, attacker_is_undead: bool = False
) -> tuple[SearchTactic, ...]:
    """One randomly built plan for an intelligent monster -- see the block comment above."""

    abilities = MONSTER_MAGIC_ABILITIES.get(monster, {})
    profile = MONSTER_RUNTIME_PROFILE[monster]

    candidates = [
        spell
        for spell, school in _SPELL_SCHOOL.items()
        if abilities.get(school, 0) >= 1
        and (spell is not Spell.CONTROL_UNDEAD or attacker_is_undead)
        and not (spell is Spell.HAND_OF_DEATH and attacker_is_undead)  # undead are immune
    ]
    rng.shuffle(candidates)
    slots_left = {school: _combat_cast_slots(level) for school, level in abilities.items()}
    # A late Charm is a cast of its own school: Psychic, but an Undead caster draws on Necromancy instead
    # (`turn/encounter.py`, Charm's Phase 183 addendum) -- reserve one slot of that school for it, and only
    # lure with a Charm the monster has the talent for (a Vampire has Psychic 3 but no Necromancy at all).
    charm_school = Ability.NECROMANCY if monster in SPIRITWRACK_UNDEAD_MONSTERS else Ability.PSYCHIC
    lure_with_charm = abilities.get(charm_school, 0) >= 3 and rng.random() < GENERATED_PLAN_LURE_CHARM_CHANCE
    if lure_with_charm:
        slots_left[charm_school] -= 1
    max_casts = min(GENERATED_PLAN_MAX_CASTS, sum(min(slots_left.get(s, 0), sum(1 for c in candidates if _SPELL_SCHOOL[c] is s)) for s in set(_SPELL_SCHOOL.values())))
    chosen: list[Spell] = []
    if max_casts > 0:
        weights = GENERATED_PLAN_CAST_COUNT_WEIGHTS[:max_casts]
        wanted = rng.choices(range(1, max_casts + 1), weights=weights)[0]
        if attacker_is_undead and Spell.CONTROL_UNDEAD in candidates:
            chosen.append(Spell.CONTROL_UNDEAD)
            slots_left[Ability.NECROMANCY] -= 1
        for spell in candidates:
            if len(chosen) >= wanted:
                break
            if spell in chosen:
                continue
            school = _SPELL_SCHOOL[spell]
            if slots_left.get(school, 0) <= 0:
                continue
            slots_left[school] -= 1
            chosen.append(spell)
    chosen.sort(key=lambda spell: _SPELL_ORDER_PRIORITY[spell] + rng.uniform(0.0, 2.0))

    tactics: list[SearchTactic] = [_cast(spell) for spell in chosen]
    if _table_plans_always_shoot(monster) or (_table_plans_use_missile(monster) and rng.random() < GENERATED_PLAN_SHOOT_CHANCE):
        tactics.insert(rng.randint(0, len(tactics)), _shoot())

    if lure_with_charm:
        tactics.extend(_melee() for _ in range(rng.randint(3, 5)))
        tactics.append(_cast(Spell.CHARM))
        tactics.append(_melee())
        return tuple(tactics)

    tactics.append(_melee())
    if profile.temper in (Temper.CAUTIOUS, Temper.COWARDLY) and rng.random() < GENERATED_PLAN_RETREAT_CHANCE:
        tactics.extend([_melee(), _flee()])
    return tuple(tactics)


def roll_monster_encounter_plan(
    monster: Monster,
    rng: random.Random,
    *,
    attacker_is_undead: bool = False,
    variety_rng: random.Random | None = None,
) -> tuple[SearchTactic, ...] | None:
    """Rolls a guardian monster's own Special Encounter Plan.

    Returns ``None`` for a species with no recorded plan (only
    ``Monster.NOMONSTER``, the sentinel). If ``attacker_is_undead`` is
    True and this species has an ``undead_variant``, that variant is
    returned unconditionally (no roll consumed) -- matching the source's
    own "si usa questo al 100% se l'eroe o il Re che lo attacca e'
    Undead" wording. Otherwise, for a single-variant species, that one
    variant is returned directly (no roll consumed, the same no-roll
    convention ``models/monster.py roll_monster_alignment()`` already
    established for a single-option species); for a multi-variant
    species, consumes exactly one ``rng.random()`` call and walks the
    variants in the source's own listed order via cumulative percentage
    thresholds.
    """

    plan = MONSTER_ENCOUNTER_PLANS.get(monster)
    if plan is None:
        return None
    if attacker_is_undead and plan.undead_variant is not None:
        return plan.undead_variant.tactics
    # The varied plans of the intelligent monsters draw from their own stream (``variety_rng``), never from
    # ``rng``: the dice of the encounter itself keep the sequence they have always had.
    if (
        variety_rng is not None
        and monster_gets_generated_plans(monster)
        and variety_rng.random() < GENERATED_PLAN_CHANCE
    ):
        return generate_monster_encounter_plan(monster, variety_rng, attacker_is_undead=attacker_is_undead)
    if len(plan.variants) == 1:
        return plan.variants[0].tactics

    roll = rng.random() * 100
    cumulative = 0
    for variant in plan.variants[:-1]:
        cumulative += variant.percent
        if roll < cumulative:
            return variant.tactics
    return plan.variants[-1].tactics
