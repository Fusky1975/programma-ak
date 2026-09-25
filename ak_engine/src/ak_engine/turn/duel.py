"""Supreme Commander selection and duel demoralization (rulebook [7.1]).

"The two supreme commanders at the battles are the characters with the
largest troop contingents, the tiebreaker being the best Tactical
ability... If the defending armies aren't led by a character, they are
led by the 'provincial garrison commander', who has no abilities and is
present for that battle only. Before the battle, the two supreme
commanders may fight a duel. The armies which were led by the loser of
the duel will become demoralized and will be reduced in strength by 25%."

~~The duel *fight itself* is explicitly out of scope here: the rulebook
points to "the Special Encounter Plan rules [5.10]" for it, a whole
separate character-vs-character combat system (spells, weapon skills,
Encounter Plans) this project hasn't built.~~ -- **stale as of Phase
930, see that addendum below: the system this paragraph called
unbuilt has been built (`turn/encounter.py`/`turn/challenge_
execution.py`, originally for Search/Challenge/Pursue) and is now the
real production duel resolver.** This module itself still only
provides what doesn't depend on that system: who the two commanders
are, and the fixed 25% strength penalty once a loser is known by some
other means (now: the real combat resolver in `turn/battle_
orchestrator.py _maybe_fight_duel()`, not a formula).

Phase 351 addendum: the same AK.EXE/AK.OVR static reverse engineering
as Phase 346-350's own battle-resolution corrections independently
confirms this exact number from the compiled battle engine's own code
-- `battle_engine.column_resolution.confirmed_multipliers.
preliminary_duel_loser_led_units` is `0.75`, matching
`DUEL_DEMORALIZATION_MULTIPLIER` below exactly. Zero correction needed.

**Phase 921 addendum -- rulebook [5.10] now fully read (previously only
a paraphrased [7.1] excerpt was quoted above); still no resolution
formula.** "Regolamento AK.txt" section 5.10 "PIANO SPECIALE D'INCONTRO"
(lines 1811-1853) gives real detail this module didn't have before:

- A duel is triggered by the two supreme commanders' own Special
  Encounter Plans: whichever of the two has an aggressive tactic with
  no Flee order ahead of it in the Plan challenges the other. Putting
  Flee first is the only way to avoid being challenged; a commander
  who has Flee anywhere in the Plan never challenges voluntarily.
- Flee always succeeds in a duel (unless the commander is incapacitated
  or stunned) -- but using it still costs the fleeing side's troops a
  25% strength reduction, same penalty as using the Seduction spell to
  flee. This is a *second, independent* path to the exact same
  `DUEL_DEMORALIZATION_MULTIPLIER` outcome already modeled below, not a
  new number.
- Otherwise ("altrimenti"), the duel ends with the DEATH of one of the
  two commanders, and the loser's troops suffer the same 25% strength
  reduction (morale collapse). This is the actual fight -- and per
  [5.10]'s own text this is *all* it says about it: no die roll, no
  ability comparison, no formula of any kind for which commander dies.
- Heroes commanding neutral provinces never challenge to duel and
  always accept one, unless their Temperament is Cowardly -- a
  neutral-province-specific exception with no equivalent in this
  module (out of scope: this project has no neutral-Hero AI yet).

~~None of this closes the actual gap `combat.py win_probability()`
already documents (see its own Phase 911/921 addenda): who wins the
"otherwise" fight is still unspecified anywhere in the rulebook.~~ --
**resolved in Phase 930: the premise was wrong, not just the search.**
User-confirmed directly, citing rulebook [5.10] and a real move-file
example (`Uga-Buga Ma[kumb]`'s own real "Special Plan: FL" line, this
project's own already-recurring real leader from the `GW3`/`AK3`
fixture corpus): "Non c'è una formula del duello specifica. E'
un combattimento come quello tra mostri... Il combattimento segue
quel piano speciale d'incontro" ("There's no specific duel formula.
It's a fight like the one against monsters... combat follows that
Special Encounter Plan"). [5.10]'s own silence on "who wins" was never
a missing formula to search for -- a duel is resolved exactly like a
Search encounter against a monster: each side's own real Special
Encounter Plan tactics (Melee, Fire Arrow, spells, Flee, ...), fought
out with the same character-vs-character combat this project already
built for Search/Challenge/Pursue (`turn/encounter.py`, `turn/
challenge_execution.py`). Nothing was actually missing except
recognizing that connection -- `turn/battle_orchestrator.py
_maybe_fight_duel()`'s own `use_real_duel_combat` flag already wired
exactly this resolver in since Phase 49/669/675, just never flipped on
by a real production caller until Phase 930 did. The Phase 913-style
turn-report search this addendum used to cite is retracted as evidence
of a dead end -- it was answering the wrong question (a duel-outcome
*narration* to reverse-engineer a formula from) when no formula was
ever the real mechanism to look for.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from ak_engine.turn.battle_line import BattleUnit

DUEL_DEMORALIZATION_MULTIPLIER = 0.75  # "reduced in strength by 25%"


@dataclass(slots=True)
class Commander:
    leader_id: int | None
    contingent_size: int
    tactical_ability: int


def provincial_garrison_commander(contingent_size: int) -> Commander:
    """Fallback commander for defending armies with no leading character.

    "Has no abilities and is present for that battle only" -- modeled as
    ``leader_id=None`` and ``tactical_ability=0``.
    """

    return Commander(leader_id=None, contingent_size=contingent_size, tactical_ability=0)


def select_supreme_commander(candidates: list[Commander]) -> Commander | None:
    """Largest contingent wins; ties broken by best Tactical ability."""

    if not candidates:
        return None
    return max(candidates, key=lambda c: (c.contingent_size, c.tactical_ability))


def apply_duel_demoralization(units: list[BattleUnit]) -> list[BattleUnit]:
    """Return a new list with the duel loser's armies reduced 25% in strength.

    Phase 471: carries ``duellist_bonus_if_selected`` through too (scaled
    by the same multiplier, consistent with ``effective_strength`` itself
    being scaled) -- without this, a Duellist-side unit's own eligibility
    for the "1 Fanatical Unit" front-line bonus would silently vanish
    whenever its side lost the preliminary duel, since this function
    already rebuilds fresh ``BattleUnit`` instances rather than mutating
    the originals in place. Phase 661: ``alignment_king_bonus_if_
    selected`` gets the exact same treatment, for the exact same reason
    -- the 7 alignment-King titles' own shared version of this bonus.
    Phase 696: ``has_druidic_horse_control`` (a plain boolean, no scaling
    needed) gets the same treatment -- without it, a demoralized cavalry
    unit would silently lose its own Beasts-nemesis exemption for the
    rest of the battle whenever its side lost the preliminary duel.

    **Bug fix (Phase 812's own sibling finding)**: this function's own
    hand-rolled reconstruction was patched three separate times (471,
    661, 696) for three separate fields, but never noticed it was
    *still* missing two OTHER fields that existed even earlier --
    ``led_by_insufficient_druid`` (Phase 298) and ``is_humanoid_race``
    (Phase 392) -- the exact same "reconstruction drops newer fields"
    bug class just fixed in ``turn/battle_line.py apply_nemesis_
    penalties()`` (see that module's own Phase 812 addendum). Real
    consequence: `turn/battle_orchestrator.py`'s own `attacker_units`/
    `defender_units` lists are overwritten in place with whatever this
    function returns, and those same lists later feed both `led_by_
    insufficient_druid_by_army_id` (read straight from them) and
    `resolve_battle()` (whose own `BattleResult.columns` are built from
    them) -- so a demoralized unit that also had `led_by_insufficient_
    druid=True` or `is_humanoid_race=True` before losing the duel
    silently lost both flags for the rest of the battle. Fixed by
    switching to `dataclasses.replace()`, which carries every field --
    current and future -- forward automatically, then overrides only
    the three that need scaling/recomputation.
    """

    demoralized = []
    for u in units:
        demoralized.append(
            replace(
                u,
                effective_strength=u.effective_strength * DUEL_DEMORALIZATION_MULTIPLIER,
                duellist_bonus_if_selected=(
                    u.duellist_bonus_if_selected * DUEL_DEMORALIZATION_MULTIPLIER
                    if u.duellist_bonus_if_selected is not None
                    else None
                ),
                alignment_king_bonus_if_selected=(
                    u.alignment_king_bonus_if_selected * DUEL_DEMORALIZATION_MULTIPLIER
                    if u.alignment_king_bonus_if_selected is not None
                    else None
                ),
            )
        )
    return demoralized
