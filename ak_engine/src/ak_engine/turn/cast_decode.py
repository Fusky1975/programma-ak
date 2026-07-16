"""Decoding a Cast PlanPhase -- top-level Action Spell casting (rulebook [3.10]).

Not to be confused with ``Maneuver.CAST``, the *encounter-plan* tactic
used inside a Search/Challenge's tactic list (rulebook [5.1], already
decoded by ``turn/search_decode.py``) -- that's a different Pascal
reading path (``R_List``'s ``Tac_Bytes`` mode) with no top-level
``ActionCode``. This module is specifically for ``ActionCode.CAST``
(ordinal 9), a leader's own phase.

Rulebook [3.10] (quoted in full): "The character can attempt to Cast a
spell in a Magical ability that he has some skill in. The spell must be
an Action Spell, not a personal-combat spell. The chance of success is
15% plus 15% per level." [4.2] adds the per-turn cast-count limits (1
Action spell/turn per Magical ability at skill 1-2, 2 at skill 3, 3 at
skill 4) and "If the spell fails, nothing happens."

Sourced from ``HostAK/TP/CTBOTH.PAS`` (``action`` enum: ``Cast`` =
ordinal 9) and ``HostAK/TP/DEF2.PAS``'s ``R_HPlan``/``W_HPlan``:

- ``obj`` (``lobjects[m]``) is the ``Spell`` ordinal (``Cast:
  Read_More(spell(lobjects[m]))``).
- ``extra[0]`` (``tl``/``lextra[m]``) is the spell's **target**, whose
  concrete meaning (character id / province id / unused) depends on
  which spell it is -- confirmed against the rulebook's per-spell
  target descriptions ([4.21]-[4.25]) and cross-checked against real
  data (e.g. Skeletal Army, which needs no target per the rulebook, has
  ``extra[0] == 0`` in all 29 real examples; Bless/Plague/Flood/Tornado,
  all province-targeted, have ``extra[0]`` values matching real province
  numbers seen elsewhere in the same files; Resurrection/Kill_Enemy/
  Charm/Oratory/Illus_Armies, all character-targeted, have small-integer
  ``extra[0]`` values in the same range as real character ids).
- **Illusory Terrain (``Spell.ILLUS_TERRAIN``) is the one spell with an
  extra field beyond the standard triple**: ``Read_More``'s ``CASE``
  reads one more integer (``pexrec[m].n1``) for it specifically -- the
  illusion's selected fake ``Terrain`` (``ADDEND.AK`` [4.23.1]: "you can
  select the terrain the illusion will mimic"). Lands as
  ``PlanPhase.extra[1]``. Confirmed against real data: both real
  Illus_Terrain casts in the sample files (``AK3__T10.K1``) have
  ``extra == [target, 3]``, and terrain ordinal 3 is ``Terrain.FOREST``.
- **Charm and Resurrection are the two spells that embed a nested plan**
  (``Read_More``'s ``CASE``: ``Charm, Resurrection: Read_HPlan`` -- the
  same recursive-nested-plan mechanism Hire uses, fixed generically in
  Phase 18's parser rewrite; see ``PlanPhase.nested_plan`` and
  ``parser/k1_moves.py``'s ``_maybe_parse_nested_plan``, which now also
  infers the nested character's id from a Cast(Charm/Resurrection)
  phase's own ``extra[0]`` target).

Validated against all 108 real Cast phases across the 10 sample
``AK3__T*.K1`` files: 12 distinct spell ids appear, and **every single
one is a documented Action spell** (never one of the 10 Personal-Combat-
only spells) -- an independent confirmation of both the decode and the
rulebook's own "must be an Action Spell" restriction [3.10], not just a
plausible reading.

**Deliberately not handled here: the Trade-\\>Cast rewrite for secret
spells 25-34.** ``DEF2.PAS``'s ``Trade`` branch can reclassify a
self-targeted Give phase into a Cast of a secret spell if the caster has
the matching special ability (see ``turn/trade_decode.py``'s docstring).
That rewrite happens to a *Trade*-ordinal phase before this module ever
sees it -- ``cast_decode.py`` only decodes phases already tagged
``ActionCode.CAST`` in the parsed token stream, and no real Trade phase
(let alone this specific rewrite) exists in any sample file to validate
against regardless.

**Decode-only**: resolving what a successful Cast actually does (a
province's tax/exploration effects, a character's death/resurrection,
army effects, etc.) needs game-state mutation logic not present anywhere
in the available Pascal source -- only the rulebook's percentages and
the id/target/nesting *shape* reconstructed above.
"""

from __future__ import annotations

from dataclasses import dataclass

from ak_engine.models.enums import Spell, spell_from_int
from ak_engine.models.map import Terrain
from ak_engine.models.plan import PlanPhase

# Rulebook [4.21]-[4.25]: each spell's target is a character, a province,
# or nothing at all -- never more than one of these, and never both a
# character/province target and something else (Illus_Terrain is the
# only spell with a *second* field, but its own extra[0] target is still
# a province like every other Illusionist province-affecting spell).
CHARACTER_TARGET_SPELLS = frozenset(
    {
        Spell.RESURRECTION,
        Spell.KILL_ENEMY,
        Spell.CHARM,
        Spell.ORATORY,
        Spell.CLAIRVOYANCE,
        Spell.ILLUS_ARMIES,
    }
)
PROVINCE_TARGET_SPELLS = frozenset(
    {
        Spell.PART_SEA,
        Spell.BLESS,
        Spell.PLAGUE,
        Spell.FLOOD,
        Spell.TORNADO,
        Spell.EARTHQUAKE,
        Spell.ILLUS_TERRAIN,
        Spell.HIDE_FEATURE,
    }
)
# Spell.GATE_ANGEL (Phase 194, one of the secret spells 25-34): the
# user-supplied rule text names no target field at all ("the spellcaster
# has no control over which hero arrives") -- no real sample data exists
# to validate this against (see this module's own "Deliberately not
# handled here" note on the secret-spell Trade->Cast rewrite).
NO_TARGET_SPELLS = frozenset({Spell.SKELETAL_ARMY, Spell.GATE_ANGEL})

# The only two spells whose Cast phase embeds a nested plan for the
# character it creates (DEF2.PAS Read_More: "Charm, Resurrection:
# Read_HPlan") -- also used by parser/k1_moves.py's nested-plan handling.
NESTED_PLAN_SPELLS = frozenset({Spell.CHARM, Spell.RESURRECTION})


@dataclass(slots=True)
class CastRequest:
    spell: Spell | int  # phase.obj
    target: int  # phase.extra[0] -- character id, province id, or unused (0), depending on spell
    terrain: Terrain | int | None = None  # phase.extra[1], only for Spell.ILLUS_TERRAIN


def decode_cast_phase(phase: PlanPhase) -> CastRequest:
    """Decode a Cast PlanPhase's target spell, target, and (for Illus_Terrain) fake terrain."""

    spell = spell_from_int(phase.obj)
    target = phase.extra[0] if phase.extra else 0

    terrain: Terrain | int | None = None
    if spell is Spell.ILLUS_TERRAIN and len(phase.extra) > 1:
        try:
            terrain = Terrain(phase.extra[1])
        except ValueError:
            terrain = phase.extra[1]

    return CastRequest(spell=spell, target=target, terrain=terrain)
