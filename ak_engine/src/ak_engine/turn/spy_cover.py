"""Spy "cover" -- the chance of escaping notice (rulebook [4.3.3], Spy Table column 1).

"Il personaggio che, in una fase del turno, compie un'azione Spiare (Spy) o Pedinare (Trail),
è meno soggetto ad essere notato per tutto quel turno di gioco" and "Il ladro condivide
l'abilità della spia di passare inosservato quando tenta di rubare".

The original program does exactly that (``DEF2.PAS`` reading each plan: ``Trail, ASpy:
cover[ldr] := Spy``; a Steal tactic in an Encounter Plan: ``cover[ldr] := Thief``; the last one
read wins), and ``RUMORS.PAS ISpy_Cover`` turns the covering Talent's level into the chance of
*being noticed*: level 0 -> 100%, 1 -> 50%, 2 -> 25%, 3 -> 12%, 4 and up -> 5% (the Spy
Table's 0/50/75/88/95% "chance of escaping notice").

The cover covers the whole turn, from the plan alone: it is computed once, when the turn's
plans are collected (``compute_cover_ability()``, stored on ``LeaderState.cover_ability``), and
read by the two things that can "notice" a character: a Patrol (rule [12.e]: "A Patrol may be
unable to detect an enemy character if he is using his Spy or Thief ability that gameturn")
and the other Kings' CHARACTERS report (``turn/leader_visibility.py``).
"""

from __future__ import annotations

from ak_engine.models.enums import Ability, ActionCode, Maneuver
from ak_engine.models.game_state import GameState, LeaderState
from ak_engine.models.plan import ActionPlan, PlanPhase

# Chance of *being noticed* by Spy/Thief level (``ISpy_Cover``): index = level, 4+ -> last.
_NOTICE_CHANCE_BY_LEVEL: tuple[float, ...] = (1.0, 0.5, 0.25, 0.12, 0.05)


def notice_chance(level: int) -> float:
    """``ISpy_Cover``'s own value for a covering Talent at ``level``."""

    return _NOTICE_CHANCE_BY_LEVEL[max(0, min(level, len(_NOTICE_CHANCE_BY_LEVEL) - 1))]


def _phase_has_steal_tactic(phase: PlanPhase) -> bool:
    # Imported here: the decoders import plan models only, but keeping this module cheap to
    # import from models/turn code avoids any import cycle risk.
    from ak_engine.turn.challenge_pursue_decode import decode_challenge_phase, decode_pursue_phase
    from ak_engine.turn.search_decode import decode_search_phase

    try:
        if phase.action is ActionCode.CHALLENGE:
            tactics = decode_challenge_phase(phase).tactics
        elif phase.action is ActionCode.PURSUE:
            tactics = decode_pursue_phase(phase).tactics
        elif phase.action is ActionCode.SEARCH:
            tactics = decode_search_phase(phase).tactics
        else:
            return False
    except Exception:  # noqa: BLE001 -- a malformed phase is some other code's error to report
        return False
    return any(tactic.maneuver is Maneuver.STEAL for tactic in tactics)


def compute_cover_ability(plan: ActionPlan | None, special_plan: tuple = ()) -> Ability | None:
    """The Talent giving ``plan`` its cover this turn: ``Ability.SPY`` for a Spy/Trail order,
    ``Ability.THIEF`` for a Steal tactic, the last of them in plan order; ``None`` for neither.
    """

    cover: Ability | None = None
    if plan is not None:
        for segment in plan.segments:
            for label in sorted(segment.phases):
                phase = segment.phases[label]
                if phase.action in (ActionCode.ASPY, ActionCode.TRAIL):
                    cover = Ability.SPY
                elif _phase_has_steal_tactic(phase):
                    cover = Ability.THIEF
    if any(getattr(tactic, "maneuver", None) is Maneuver.STEAL for tactic in special_plan):
        cover = Ability.THIEF
    return cover


def notice_chance_of(state: GameState, leader: LeaderState) -> float:
    """``ISpy_Cover(ldr)``: the chance the leader is noticed this turn -- 1.0 with no cover."""

    if leader.cover_ability is None:
        return 1.0
    from ak_engine.turn.discovery_effects import effective_skill_level

    return notice_chance(effective_skill_level(state, leader, leader.cover_ability))
