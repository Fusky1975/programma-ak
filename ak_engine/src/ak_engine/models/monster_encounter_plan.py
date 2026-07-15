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

**Deliberately not wired to any combat effect this phase, by the user's
own explicit direction**: none of those 11 spells has any implemented
personal-combat mechanic anywhere in this project (`cast_execution.py`
only implements leader/army-targeted effects for a disjoint spell set).
A `Maneuver.CAST` entry rolled from a monster's own plan is therefore
inert data here -- present for a future phase that defines what each
spell actually does in personal combat, and skipped by `turn/
search_execution.py`'s tactic walk exactly the same way a player's own
unwired `CAST` tactic already is (Phase 132's own "not wired" list).

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

from ak_engine.models.enums import Maneuver, Spell
from ak_engine.models.monster import Monster
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


def roll_monster_encounter_plan(
    monster: Monster, rng: random.Random, *, attacker_is_undead: bool = False
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
    if len(plan.variants) == 1:
        return plan.variants[0].tactics

    roll = rng.random() * 100
    cumulative = 0
    for variant in plan.variants[:-1]:
        cumulative += variant.percent
        if roll < cumulative:
            return variant.tactics
    return plan.variants[-1].tactics
