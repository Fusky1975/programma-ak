"""Supreme Commander selection and duel demoralization (rulebook [7.1]).

"The two supreme commanders at the battles are the characters with the
largest troop contingents, the tiebreaker being the best Tactical
ability... If the defending armies aren't led by a character, they are
led by the 'provincial garrison commander', who has no abilities and is
present for that battle only. Before the battle, the two supreme
commanders may fight a duel. The armies which were led by the loser of
the duel will become demoralized and will be reduced in strength by 25%."

The duel *fight itself* is explicitly out of scope here: the rulebook
points to "the Special Encounter Plan rules [5.10]" for it, a whole
separate character-vs-character combat system (spells, weapon skills,
Encounter Plans) this project hasn't built. This module only provides
what's fully specified without that system: who the two commanders are,
and the fixed 25% strength penalty once a loser is known by some other
means.

Phase 351 addendum: the same AK.EXE/AK.OVR static reverse engineering
as Phase 346-350's own battle-resolution corrections independently
confirms this exact number from the compiled battle engine's own code
-- `battle_engine.column_resolution.confirmed_multipliers.
preliminary_duel_loser_led_units` is `0.75`, matching
`DUEL_DEMORALIZATION_MULTIPLIER` below exactly. Zero correction needed.
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
