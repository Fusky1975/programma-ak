"""The "Local Encounter Table" -- the small set of non-combat outcomes a
chance meeting between two characters can resolve to, distinct from the
already-modeled combat-track encounters (``report/turn_report.py``'s own
``render_wandering_encounter``/``render_generic_encounter``/
``render_patrol_encounter``/``render_patrol_release``, Phases 106-107,
all themselves ``FD(...)``-dispatched multi-variant files).

**Sourced from two independent places in `Programma Pascal.zip`, both
read directly, not guessed:**

- ``HostAK/TP/RUMORS.PAS`` (~lines 118-121) declares the real integer
  constants used below as this module's own enum values, sitting right
  next to the already-modeled ``_LSafe``/``_LWEnc``/``_LPEnc`` (Phases
  106-107) in the very same ``CONST`` block:
  ``_LPass = 3310; _LBefr = 3311; _LTricks = 3312; _LDense = 3313;
  _LDona = 3314; _LHear = 3315; _LNice = 3316; _LGreet = 3317;``.
  ``_LHearInv`` (~line 86: ``_LHearInv = 3090``) and ``_LHearPat``
  (~line 140: ``_LHearPat = 3393``) sit in different stretches of the
  same block but share the exact same ``Say(...)`` dispatch shape,
  found immediately adjacent to the other 8 while transcribing
  ``HostAK/TP/SAY.PAS``.
- ``HostAK/TP/SAY.PAS``'s ``Imp_Code`` procedure (the same giant
  ``CASE code OF`` this project's ``FD``/``FD2`` litmus test, Phase 104,
  was originally read out of) dispatches every one of these 10 codes to
  a single, real, hardcoded ``Say('...')`` call (lines 458-459 and
  906-913) -- **not** an ``FD(...)`` file lookup, so unlike the
  MARCH.X/RWENC.X/etc. family there is no per-code *file* of variants
  to pick from; each code has exactly one confirmed template string.

**Evidence tier**: stronger than ``models/intro.py Intro`` (Phase 99,
which had no confirmed integer constants at all for its own codes) --
here both the named constant *and* its dispatched content are directly
confirmed. What's still unconfirmed, and not guessed at: which game
-state fact picks one of these 10 codes over another for a given
encounter (the selection logic lives in the missing main program, the
same recurring gap this project has documented since ``turn/pursuit.py``
-era phases). This module only models the confirmed vocabulary and its
confirmed content, not the selection rule.

**Raw byte inspection** (not just a printed preview, which silently
swallows control bytes -- the same caution ``turn_report.py``'s own
docstring already established) found real Turbo Pascal control-byte
markers in 2 of the 10 templates, transcribed here to ``PROSE.TXT``'s
own source notation:

- ``_LHearInv`` ends in ``\\x13`` = ``^S`` ("Province name #2", the
  invaded province, distinct from ``@`` which is the reporting
  character's own province).
- ``_LDona`` contains ``\\x0b`` = ``^K`` ("King name and title"),
  immediately followed by a Pascal-escaped ``''`` (a literal
  apostrophe) -- i.e. ``^K's``.
- ``_LHear`` contains ``\\x01 & \\x02\\x06 \\x05`` = ``^A & ^B^F ^E`` --
  ``^A`` (article) before ``&`` (feature name), then ``^F`` (feature
  number) wrapped in ``^B``/``^E``, which ``report/prose.py``'s own
  docstring already documents and defers: "anything between these two
  symbols is excluded from the General Intelligence Reports of other
  players" (``PROSE.TXT`` line 51-52) -- an audience-scoping marker,
  not a text substitution, matching the King-exclusion markers
  ``render()`` already leaves untouched unless a caller supplies
  literal values for them.

``LOCAL_ENCOUNTER_TEMPLATE``'s own strings are raw, unrendered prose
templates -- matching how ``models/intro.py INTRO_TEMPLATE``/
``models/power.py POWER_DESCRIPTION`` already store their own raw
template text rather than a pre-resolved sentence; render via
``report/prose.py render()`` directly, supplying whatever markers a
given template needs (see each member's docstring-adjacent comment for
which of ``<``/``<2``/``[``/``[1``/``>``/``@``/``^``/``^K``/``$a``/
``^S``/``^F``/``&``/``+`` it uses).
"""

from __future__ import annotations

from enum import Enum


class LocalEncounterEvent(Enum):
    """``RUMORS.PAS``'s own ``_L*`` story-code constants, verbatim
    values -- see module docstring. Member names are derived from each
    code's confirmed ``Say(...)`` content (the Pascal identifiers
    themselves, e.g. ``_LDona``/``_LDense``, are terse abbreviations
    with no standalone meaning, unlike ``Intro``'s already-readable
    ``CTME.PAS`` names).
    """

    HEAR_OF_INVASION = 3090
    PASS_NO_FIGHT = 3310
    BEFRIEND = 3311
    LEARN_TRICKS = 3312
    TOO_DENSE_TO_LEARN = 3313
    RECEIVE_DONATION = 3314
    HEAR_OF_FEATURE = 3315
    FRIENDLY_CHAT = 3316
    GREET_AVOID_COMBAT = 3317
    HEAR_OF_PATROL_INTRUSION = 3393


# HostAK/TP/SAY.PAS lines 458-459, 906-913, verbatim (control bytes
# transcribed to ^-notation -- see module docstring). Raw, unrendered
# prose templates.
LOCAL_ENCOUNTER_TEMPLATE: dict[LocalEncounterEvent, str] = {
    # <: defending character; @: own province; ^S: the invaded province.
    LocalEncounterEvent.HEAR_OF_INVASION: (
        "<, responsible for the defense of @, learned/Rgot_wind of an "
        "enemy attack/Rmove on ^S."
    ),
    # <: character; [/[1: the other party.
    LocalEncounterEvent.PASS_NO_FIGHT: (
        "< encountered/Rpassed_near [, but [1 seemed_to_have_no/R"
        "had_not_the mettle/Rtime for a fight."
    ),
    # <: character; >: character's; [: the other party.
    LocalEncounterEvent.BEFRIEND: (
        "< raised > hands/Rpalm in greeting/Ra_gesture_of_friendship and "
        "befriended/Rmade_friends_with [."
    ),
    # [1: the teacher; <2: character; ^: ability name.
    LocalEncounterEvent.LEARN_TRICKS: (
        "[1 was kind_enough/Rable to show <2 a few tricks/Rtips in ^."
    ),
    # <: character.
    LocalEncounterEvent.TOO_DENSE_TO_LEARN: (
        "< was very impressed/Rinterested, but couldn't {seem to "
        "}get_the_hang_of/Runderstand it."
    ),
    # <: character; >: character's; ^K: king name and title;
    # $a: alignment of character #1; [1: the donor.
    LocalEncounterEvent.RECEIVE_DONATION: (
        "< explained {> and }^K's {$a }cause/Rbeliefs and [1, "
        "greatly/Rvisibly impressed/Rmoved, gave us 1 gold."
    ),
    # [1: the informant; @: province; &: feature name; ^F: feature
    # number (^B..^E wraps it -- excluded from other players' General
    # Intelligence Reports, see module docstring); +: monster name.
    LocalEncounterEvent.HEAR_OF_FEATURE: (
        "[1 spoke/Rtold of a{n interesting} feature in @: ^A & ^B^F "
        "^Einhabited/Roccupied by +."
    ),
    # <: character; [: the other party.
    LocalEncounterEvent.FRIENDLY_CHAT: (
        "< and [ talked/Rdrank_wine for a while/Rtime, then {parted and "
        "}went their separate ways."
    ),
    # <: character; [: the other party.
    LocalEncounterEvent.GREET_AVOID_COMBAT: (
        "{but }< hailed/Rspoke_to [ with friendly/Rrespectful words, and "
        "combat/Ra_fight was avoided/Raverted."
    ),
    # <: patrolling character; @: province; [: the intruder.
    LocalEncounterEvent.HEAR_OF_PATROL_INTRUSION: (
        "<, patrolling @, learned/Rgot_wind of a nearby intrusion by [."
    ),
}
