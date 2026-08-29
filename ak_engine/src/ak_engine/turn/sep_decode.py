"""Special Encounter Plan (SEP, rulebook [5.10]) decode and classification.

Every leader may submit a standing ``SP:`` tactic list alongside their
ordinary ``AP:`` move plan (`models/plan.py PlanSegment.sp`, captured
verbatim by the K1 parser but never decoded until now). Confirmed the
*exact same* ``-1``-terminated tactic-list wire format Search/Challenge/
Pursue already decode (`AKGEN_reverse_engineering_report (5).md`
section 72: "Search, Challenge, Pursue | lista di manovre/tattiche
terminata da -1" -- `SP:` shares that row), verified by hand against
every distinct real ``SP:`` value found across all 20 available real
K1 move-submission samples (`Desktop/Gioco/Gioco Chatgpt/AK3__T*.K1`,
`Desktop/Gioco/Esempi turni/SE3__T*.K1`):

```
SP: -1                        -> []
SP: 10 -1                     -> [Flee]
SP: 10 0 24 -1                -> [Flee, Cast(spell=24 Mirror-Image Phantasm)]
SP: 10 0 24 9 -1              -> [Flee, Cast(spell=24), Melee]
SP: 0 20 0 3 0 7 9 -1         -> [Cast(20 Spiritwrack), Cast(3 Holy Symbol), Cast(7 Hand of Death), Melee]
SP: 0 28 0 7 8 9 -1           -> [Cast(28 Gate Demon), Cast(7 Hand of Death), Fire Arrow, Melee]
SP: 0 28 0 7 9 -1             -> [Cast(28 Gate Demon), Cast(7 Hand of Death), Melee]
```

Unlike a Search/Challenge/Pursue ``PlanPhase.extra``, ``SP:`` has no
leading ``tl``/``extra0`` slot -- it's a pure tactic list from the first
token, confirmed by the grammar and every real sample above (`decode_
special_encounter_plan()` below skips straight to `turn/search_decode.py
decode_tactic_tokens()`).

**`Plan_Intent` -- the real "is this plan aggressive" classifier,
fully recovered, not guessed** (`AKGEN_reverse_engineering_report (3).md`
section 61, quoting `RUMORS.PAS:835-858` in full):

```pascal
FUNCTION Plan_Intent(td: desigptr): maneuver;
VAR int: maneuver;
BEGIN
  int:= CNone;
  WHILE ((int = CNone) and (td <> Nil)) DO BEGIN
    CASE maneuver(td^.dn) OF
      CFlee: int:= CFlee;
      CFulfill,CTalk,CGive: int:= CTalk;
      CSteal: int:= CSteal;
      CScout: ;
      CSay: IF td^.nextbyte = Nil THEN int:= CTalk;
      CShoot,CMelee: int:= CMelee;
      CUse_MI:
        IF ord(treaslist[td^.dobj]) <> ord(wcp)+ord(Invisibility) THEN
          IF ord(treaslist[td^.dobj]) <> ord(wcp)+ord(Charm) THEN
            int:= CMelee;
      CCast: WITH td^ DO CASE spell(dobj) OF
        Invisibility,Charm,Augur_Combat: ;
        ELSE int:= CMelee;
      END;
    END;
    td:= td^.nextbyte;
  END;
  IF int = CNone THEN int:= CMelee;
  Plan_Intent:= int;
END;
```

A single forward pass that stops at the first tactic carrying real
weight -- `CScout` and a `CSay` that isn't the plan's own last tactic
are transparent no-ops that let the scan continue past them. `Plan_
Intent()`'s own `CUse_MI` exemption (Cologne of Charming / Ring of
Invisibility don't mark the plan aggressive) is *already built* from an
independent source pass -- `turn/use_mi_execution.py USE_MI_NON_
AGGRESSIVE_WANDS = frozenset({Treasure.WAND_CHARM, Treasure.WAND_
INVISIBILITY})` (citing `AKGEN_reverse_engineering_report (4).md SS6.2,
RUMORS.PAS:839-857` -- the exact same source paragraph) -- reused
directly here rather than reinvented. Resolving *which* real item a
``USE_MI`` tactic's own ``sub_object`` (a real, resolvable item-instance
id, confirmed via `turn/use_mi_decode.py`/`turn/search_execution.py
_resolve_use_mi_tactic()`) refers to needs a live `GameState` -- `plan_
intent()` below takes an optional `state` for exactly this; without
one (or an item id that doesn't resolve), it falls back to `Plan_
Intent`'s own real, unconditional-except-two-items aggressive default,
not a guessed third branch.

**The real Duel-trigger rule needs `Plan_Intent()` plus an independent
full-list Flee scan, not `Plan_Intent()` alone** -- confirmed by the
rulebook's own precise wording (`Regolamento AK.txt:1818-1830`, [5.10]):
a commander "che ha un Piano Speciale d'Incontro che contiene
un'azione aggressiva e nessun ordine Fuggire... sfiderà l'altro a
duello", and separately, explicitly: "il personaggio che ha il
comando Fuggire **in un punto qualsiasi** del Piano Speciale
d'Incontro non provocherà mai un duello volontariamente." Since `Plan_
Intent()`'s own single pass stops at the *first* weighted tactic, a
plan like `[Melee, Flee]` reduces to `CMelee` (Flee is never reached)
-- but the rulebook's "anywhere" wording means this plan must NOT
challenge, so `sep_is_aggressive()` checks both independently.
Accepting an *incoming* challenge is a separately-stated rule that
*does* match `Plan_Intent()`'s own single-pass result directly:
"accetterà sempre...prima di darsi alla fuga" unless Flee is literally
the plan's own first tactic -- `sep_accepts_challenge()` below.

**No real call site for `Plan_Intent()` itself survives** in any of
the 5 AKGEN disassembly reports or 18 `.PAS` files (confirmed by grep)
-- same "missing main program" class of gap as everywhere else in this
project; the trigger *formula* is fully sourced, only the exact
orchestrating call site is lost.

**Stale as of Phase 674 (this module's own last touch), fully wired
since Phase 669/675 -- corrected here, Phase 681.** This paragraph used
to say "decode and classification only, not yet wired... no production
caller passes `duel_maneuvers` yet." That's no longer true: `turn/
battle_orchestrator.py`'s own `_commander_challenges()` (Phase 669)
already calls `sep_is_aggressive()`/`sep_accepts_challenge()` below to
gate whether a Duel triggers at all -- matching the bidirectional
formula and neutral-province exception this module doesn't itself
model (that's `battle_orchestrator.py`'s own concern) -- and `_maybe_
fight_duel()` (Phase 675) now defaults `duel_maneuvers` to the
attacker's own real `special_encounter_plan` whenever a caller doesn't
supply one explicitly, threading the defender's SEP into `resolve_
challenge_combat()` too. The one thing that genuinely does stay
dormant in every real game today -- correctly still noted in `battle_
orchestrator.py`'s own docstring, not this one -- is `use_real_duel_
combat` defaulting `False` for every production caller, a separate,
deliberately-deferred decision this project has repeatedly declined to
make unilaterally.
"""

from __future__ import annotations

from ak_engine.models.enums import Maneuver, Spell
from ak_engine.models.game_state import GameState, LeaderState
from ak_engine.models.plan import PlanSegment
from ak_engine.turn.search_decode import SearchTactic, decode_tactic_tokens
from ak_engine.turn.use_mi_execution import USE_MI_NON_AGGRESSIVE_WANDS

# RUMORS.PAS Plan_Intent's own CCast exempt set -- these three spells
# don't mark the plan aggressive on their own (see module docstring).
_PLAN_INTENT_EXEMPT_SPELLS = frozenset({Spell.INVISIBILITY, Spell.CHARM, Spell.AUGUR_COMBAT})

# RUMORS.PAS Plan_Intent's own CTalk-classified maneuvers.
_TALK_MANEUVERS = frozenset({Maneuver.FULFILL, Maneuver.TALK, Maneuver.GIVE})

# RUMORS.PAS Plan_Intent's own CMelee-classified maneuvers (besides Cast/Use_MI's own conditional branches).
_MELEE_MANEUVERS = frozenset({Maneuver.SHOOT, Maneuver.MELEE})


def decode_special_encounter_plan(segment: PlanSegment) -> list[SearchTactic]:
    """Decode a leader's own standing Special Encounter Plan from
    ``PlanSegment.sp`` -- see module docstring for the real wire format
    (identical to Search/Challenge/Pursue's own tactic list, minus their
    leading ``tl`` slot).
    """

    return decode_tactic_tokens(list(segment.sp))


def _cast_is_exempt(tactic: SearchTactic) -> bool:
    if tactic.sub_object is None:
        return False
    try:
        spell = Spell(tactic.sub_object)
    except ValueError:
        return False
    return spell in _PLAN_INTENT_EXEMPT_SPELLS


def _use_mi_is_exempt(tactic: SearchTactic, state: GameState | None) -> bool:
    if state is None or tactic.sub_object is None:
        return False
    item = state.items.get(tactic.sub_object)
    if item is None:
        return False
    return item.treasure in USE_MI_NON_AGGRESSIVE_WANDS


def plan_intent(tactics: list[SearchTactic], state: GameState | None = None) -> Maneuver:
    """``RUMORS.PAS Plan_Intent()`` -- see module docstring for the full,
    verbatim-quoted source this is a literal port of. ``state`` (optional)
    lets a real ``USE_MI`` tactic resolve its own actual item; omitted or
    unresolvable falls back to the function's own real aggressive
    default for that branch, not a guessed third outcome.
    """

    intent = Maneuver.NONE
    for index, tactic in enumerate(tactics):
        maneuver = tactic.maneuver
        if maneuver is Maneuver.FLEE:
            intent = Maneuver.FLEE
        elif maneuver in _TALK_MANEUVERS:
            intent = Maneuver.TALK
        elif maneuver is Maneuver.STEAL:
            intent = Maneuver.STEAL
        elif maneuver is Maneuver.SCOUT:
            pass
        elif maneuver is Maneuver.SAY:
            if index == len(tactics) - 1:
                intent = Maneuver.TALK
        elif maneuver in _MELEE_MANEUVERS:
            intent = Maneuver.MELEE
        elif maneuver is Maneuver.USE_MI:
            if not _use_mi_is_exempt(tactic, state):
                intent = Maneuver.MELEE
        elif maneuver is Maneuver.CAST:
            if not _cast_is_exempt(tactic):
                intent = Maneuver.MELEE

        if intent is not Maneuver.NONE:
            break

    if intent is Maneuver.NONE:
        intent = Maneuver.MELEE
    return intent


def sep_is_aggressive(tactics: list[SearchTactic], state: GameState | None = None) -> bool:
    """Rulebook [5.10]: a Special Encounter Plan challenges the opposing
    commander to a duel when it "contiene un'azione aggressiva e nessun
    ordine Fuggire" -- ``Plan_Intent()`` reduces to Melee AND no Flee
    tactic appears anywhere in the plan (not just before the first
    weighted tactic -- see module docstring).
    """

    return plan_intent(tactics, state) is Maneuver.MELEE and not any(t.maneuver is Maneuver.FLEE for t in tactics)


def sep_accepts_challenge(tactics: list[SearchTactic], state: GameState | None = None) -> bool:
    """Rulebook [5.10]: a commander "accetterà sempre...prima di darsi
    alla fuga" an incoming challenge, unless Flee is literally the
    plan's own first tactic -- i.e. ``Plan_Intent()`` doesn't reduce to
    Flee (see module docstring's "Accepting" paragraph).
    """

    return plan_intent(tactics, state) is not Maneuver.FLEE


def target_uses_special_encounter_plan(state: GameState, target_leader: LeaderState | None) -> bool:
    """Phase 674 -- rulebook [5.10]'s other half: "Se il personaggio non
    comanda eserciti, il Piano d'Incontro sarà usato in tutti gli
    Incontri sollecitati da un altro personaggio o mostro errante." --
    the literal real condition, using the existing ``GameState.armies_
    commanded_by()`` primitive already used elsewhere for exactly this
    "does this leader command any army" check. ``False`` for
    ``target_leader is None`` (a garrison commander -- no real
    ``LeaderState``/``special_encounter_plan`` exists for it).
    """

    return target_leader is not None and not state.armies_commanded_by(target_leader.leader_id)
