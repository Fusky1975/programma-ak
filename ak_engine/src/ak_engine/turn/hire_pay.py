"""Hire Hero's required-pay formula (`LCost`) -- Phase 162/163/264,
**superseded by Phase 505** with the real formula, recovered by a
disassembly-based reverse-engineering pass the user supplied directly
(``AKGEN_reverse_engineering_report (3).md``, Part II, "reclutamento e
mantenimento degli Eroi liberi"), not this project's own invention.

**Why the old formula existed at all**: Phase 162's own note explained
`LCost` was "confirmed absent from the surviving Pascal source" (only 13
``.PAS`` files, the moderator-side tooling, were available at the time) --
the identifier was called but never *defined*. The dossier above resolves
that gap directly, from a real disassembly of ``AKGEN.EXE``
(``0x54798-0x54BDA``) and ``AK.OVR`` (the ``HI`` resolver,
``0x0166A-0x0197D``), cross-checked against ``REPORTS.PAS``/``RULES.AK``/
``ADDEND.AK``. It also explains, precisely, the one real-sample mismatch
``turn/expenses.py``'s own docstring already flagged (Garin, Pagan/Brave/
Dwarf under a Neutral/Brave/presumably-Human King: the old formula
predicted 2, the real sample showed 1) -- race *does* matter, but only for
Heroes whose own hidden per-character bit (``borny[hero] and 1``) enables
it, exactly the kind of "sometimes race matters, sometimes it doesn't"
behavior a simple always-on/always-off race term could never reproduce.

**The real formula, in full**:

    NormAlign(c)     = clamp(1, 6, ALIGNMENT_ORDINAL[align(c)])
    AlignDistance    = |NormAlign(hero) - NormAlign(king)|
    align_penalty    = 8 >> max(0, 4 - AlignDistance)   # 0,1,2,4,8 by distance 0..4+

    bias = (k & 1) - ((bornx[h] & 2) >> 1)
    if ((k + h) & 2) == 0: bias = -bias

    race_penalty   = (borny[h] & 1) * (race[h] != race[k])
    temper_conflict = temper[h] != temper[k]
    if not temper_conflict and hero is still Mercenary (unhired) and Total_USkill(king) < 7:
        temper_conflict = True
    temper_penalty = (bornx[h] & 1) * temper_conflict

    like      = clamp(-2, 2, 2 - align_penalty - race_penalty - temper_penalty + bias)
    base_cost = 3 - like   # 1..5

    if king.alignment != Divine and hero.alignment != king.alignment
       and hero's own birth province is owned by the king's own kingdom:
        LCost = min(5, base_cost + 1)
    else:
        LCost = base_cost

``h``/``k`` are the real engine's own internal leader indices (``LKing``
resolves a King to *his own* leader index, not a separate "kingdom id"
concept the Pascal source doesn't have) -- this project's own
``LeaderState.leader_id`` is the direct, structurally equivalent
substitute (see ``bias``'s own worked derivation below for why an
arbitrary historical game's real indices can no longer be reproduced from
this project's own, unrelated leader-id assignment order).

**``bias`` is real, not noise, but it can no longer be checked against a
specific historical game's own numbers.** It's a fully deterministic
function of two real leader indices and one birth-coordinate bit -- not a
per-turn dice roll -- but *which* two indices a real historical game
assigned to (say) Adele and Bradipo I is lost information: this project's
own leader ids are assigned by its own worldgen/parsing order, with no
guaranteed relationship to a real Pascal game's internal numbering.
``turn/expenses.py``'s own former "matches SE3__T1.K2 exactly" assertions
for Adele/Indra (both real Heroes at real alignment distance 0) relied on
the *old*, bias-free approximation always giving the cheapest price at
distance 0 -- the real formula does not make that guarantee (a King/Hero
index pair can push ``bias`` negative even at perfect alignment/race/
temper match), so those specific real-sample numbers no longer transfer;
what *does* transfer, and is re-verified here, is the formula's own shape
match to the dossier's disassembly-sourced pseudocode.

**Missing data defaults permissively**, same convention as the pre-Phase-
505 formula: no ``king`` at all, or no recorded alignment/temper/race/
birth coordinate on either side, drops the corresponding term to zero
friction (``align_penalty=0``, ``race_penalty=0``, no conquest surcharge)
rather than penalizing a leader for data this project hasn't populated.
A missing ``birth_x``/``birth_y`` also zeroes ``bias``'s own personal-bit
inputs (the same "even bit -> gate off" effect a real, unset coordinate
would have).

**``Total_USkill``** reuses this project's own already-established
``effective_skill_level()`` sum across all 15 ``Ability`` members --
named ``Total_Skill`` at its other real call site
(``report/turn_report.py _total_skill()``), the identical real quantity.

**The "rare exception" bypass (Phase 264) is unaffected** -- still a
user-specified 15% chance to drop an otherwise-refused (``pay >= 5``)
Hire down to the 4-gold offer ceiling; see ``roll_rare_alignment_
exception()``'s own docstring.
"""

from __future__ import annotations

import random

from ak_engine.models.alignment import ALIGNMENT_ORDINAL, Alignment
from ak_engine.models.enums import Ability
from ak_engine.models.game_state import GameState, LeaderState
from ak_engine.models.map import HexCoord
from ak_engine.models.race import Race
from ak_engine.turn.discovery_effects import effective_skill_level

_UNHIREABLE_PAY = 5
_ALIGN_FLOOR = 1  # NormAlign's "current rules" floor -- see module docstring.

# Phase 264: user-specified (2026-07-28), not sourced -- see module
# docstring's own "rare exception" note.
RARE_ALIGNMENT_EXCEPTION_CHANCE = 0.15
RARE_ALIGNMENT_EXCEPTION_PAY = 4


def _norm_align(alignment: Alignment) -> int:
    return max(_ALIGN_FLOOR, min(6, ALIGNMENT_ORDINAL[alignment]))


def _align_penalty(hero_alignment: Alignment | None, king_alignment: Alignment | None) -> int:
    if hero_alignment is None or king_alignment is None:
        return 0
    distance = abs(_norm_align(hero_alignment) - _norm_align(king_alignment))
    return 8 >> max(0, 4 - distance)


def _total_uskill(state: GameState, leader: LeaderState) -> int:
    """``Total_USkill(leader)`` -- see module docstring."""

    return sum(effective_skill_level(state, leader, ability) for ability in Ability)


def _leader_race(state: GameState, leader: LeaderState) -> Race | None:
    if leader.race is not None:
        return leader.race
    if leader.kingdom_id is not None:
        return state.kingdoms[leader.kingdom_id].race
    return None


def _like(state: GameState, hero: LeaderState, king: LeaderState) -> int:
    align_penalty = _align_penalty(hero.alignment, king.alignment)

    h, k = hero.leader_id, king.leader_id
    bornx_h = hero.birth_x if hero.birth_x is not None else 0
    borny_h = hero.birth_y if hero.birth_y is not None else 0

    bias = (k & 1) - ((bornx_h & 2) >> 1)
    if ((k + h) & 2) == 0:
        bias = -bias

    hero_race = _leader_race(state, hero)
    king_race = _leader_race(state, king)
    race_mismatch = hero_race is not None and king_race is not None and hero_race is not king_race
    race_penalty = (borny_h & 1) * (1 if race_mismatch else 0)

    hero_temper = hero.temper
    king_temper = king.temper
    temper_conflict = hero_temper is not None and king_temper is not None and hero_temper is not king_temper
    if not temper_conflict and hero.kingdom_id is None and _total_uskill(state, king) < 7:
        temper_conflict = True
    temper_penalty = (bornx_h & 1) * (1 if temper_conflict else 0)

    raw_like = 2 - align_penalty - race_penalty - temper_penalty + bias
    return max(-2, min(2, raw_like))


def required_pay(state: GameState, hero: LeaderState, king: LeaderState | None) -> int:
    """The gold-per-annum a Hero requires to enter a King's service
    (``LCost``) -- see module docstring for the full, real formula.

    ``king`` is the kingdom's own ``LeaderState`` with ``is_king=True``
    (``None`` if no King is currently recorded for the kingdom -- treated
    as "no data," the same permissive default as a missing alignment or
    temper).
    """

    if king is None:
        return 1

    like = _like(state, hero, king)
    base_cost = 3 - like

    king_alignment = king.alignment
    hero_alignment = hero.alignment
    if (
        king_alignment is not None
        and king_alignment is not Alignment.DIVINE
        and hero_alignment is not None
        and hero_alignment != king_alignment
        and hero.birth_x is not None
        and hero.birth_y is not None
    ):
        home_province = state.provinces.get(HexCoord(hero.birth_x, hero.birth_y))
        if home_province is not None and home_province.owner_kingdom_id == king.kingdom_id:
            return min(_UNHIREABLE_PAY, base_cost + 1)

    return base_cost


def roll_rare_alignment_exception(rng: random.Random) -> bool:
    """Phase 264: the "In rare occasioni..." bypass for an otherwise-unhireable
    (``required_pay() >= 5``) alignment gap -- see module docstring for
    the user-specified 15% chance and why 4, not 5, becomes the price
    on success.
    """

    return rng.random() < RARE_ALIGNMENT_EXCEPTION_CHANCE
