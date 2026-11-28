"""Imperial Office holder resolution -- rulebook [10.1]'s own Rank
contest, Phase 230. Given a `GameState` with every leader's real
skills/treasury/Tax_Base/owned-items data (fully live per `turn/
merit_points.py`, Phase 227) plus whatever `MeritTally` counters a
caller has populated, this resolves *who currently holds* each of the 29
Imperial Offices this project models (the rulebook's own 8 major offices
plus, as of Phase 277, `Office.EVIL_KING`/`Office.THIEF_PRINCE`, plus,
as of Phase 367, the 11 race-fanaticism titles, plus, as of Phase 368,
the 6 alignment-King titles and Chief of Staff/Silver Tongue) -- closing
the "needs the full Merit Point Rank contest across every leader in the
game" gap Phase 227/228's own docstrings both flagged as a separate,
considerably larger follow-up.

**Emperor is resolved differently from the other 28 offices.** The
rulebook's own table lists Emperor's Merit Points as the Kingdom's own
Tax_Base ("Ammontare della rendita di tasse alla fine del gioco"), but
the actual *winner* of the Emperor office isn't a Merit-Point-Rank
comparison at all -- it's decided by the real Call-for-Vote election
mechanic (rulebook [10.2], `turn/emperor_election.py`, Phase 228),
already resolved into `GameState.emperor_kingdom_id`. `resolve_office_
holder(state, Office.EMPEROR)` reads that field directly (resolving to
the elected Kingdom's own King, via `LeaderState.is_king`) rather than
re-deriving anything from `emperor_merit_points()`.

**The other 28 offices are a genuine Rank contest across every leader in
the game** -- "Anche un Eroe può aggiudicarsi una carica e uno stesso
personaggio può aggiudicarsene più di una" (rulebook [10.1]): a Hero can
win an office too, and the same character can hold more than one. Each
office iterates `state.leaders` (Kings and Heroes alike), computes that
leader's own Merit Points via the matching `turn/merit_points.py`
formula, and picks the strictly highest scorer who meets `models/
office.py OFFICE_MIN_POINTS[office]` (real, sourced Pascal `minpts`
threshold, Phase 81) -- a leader below threshold is not a genuine
office-holder yet, even if they're the highest scorer among a field of
zeros. Ties are broken via `turn/merit_points.py
merit_point_tiebreak_key()` (rulebook footnote 3: treasury, then
Tax_Base, both of the tied leader's own serving Kingdom; plus a real
third tier, Phase 377: lower `leader_id`).

**Treasurer needs a per-leader wrapper.** `treasurer_merit_points()`
takes a `kingdom_id` (a King's own treasury is his Kingdom's), so a
leader with no Kingdom (`kingdom_id is None`, an independent Hero) is
never eligible for Treasurer -- there's no treasury to measure, not a
guessed 0.

**This module resolves every office from whatever `MeritTally` state a
caller has already populated** -- for Chancellor, Marshal, Admiral,
Defender, and Priest specifically, that state is fully live in real
turn execution, not a future TODO: Chancellor's three discovery-
attribution terms are credited by `plan_dispatch.py`'s own EXPLORE
branch (Phase 256), `practice_execution.py`'s SAGE branch (Phase 271),
and `aspy_execution.py execute_aspy()` (Phase 267); Marshal/Admiral's
battle counters by `battle_orchestrator.py _record_battle_merit()`
(Phase 254, quality-weighted since Phase 308); Defender's two monster-HP
counters by `search_execution.py` (Phase 255 and Phase 258); Priest's
cast counter by `cast_execution.py` (Phase 251) -- see `turn/merit_
points.py`'s own per-office sections for the exact write sites. (Phase
441: this paragraph itself had drifted stale, still describing the
pre-Phase-254 state of the world well after every one of these writers
had landed -- corrected here, no behavior change.) Any *other*
`MeritTally` field an office formula might read in the future should be
checked against `merit_points.py`'s own "field-only, no writer"
comments before assuming it's live.

**Phase 277: `Office.EVIL_KING`/`Office.THIEF_PRINCE` join the Rank
contest**, using the same generic loop as the other 7 non-Emperor
offices -- `evilking_merit_points()` already returns 0 for any leader
who isn't the acting King of an Evil-aligned Kingdom (see that
function's own docstring), so King of Pain's own "King-only, Evil-only"
eligibility rule needs no special-casing here, unlike Emperor's genuinely
different resolution mechanism. Since `describe_imperial_office_report()`
already iterates `ALL_OFFICES` generically (`models/office.py OFFICE_
NAME` already had real display strings for both), extending this
module's own registry automatically -- correctly -- adds "King of Pain"/
"Prince of Thieves" rows to that table too, confirmed as real rows in
that same table by the real `SE3__T10.K1` sample (alongside several
other real titles -- e.g. race-specific fanaticism ones -- this project
still doesn't model at all, an unrelated, larger, already-documented gap
in that composer, not reopened here).

**Phase 367: the 11 race-fanaticism titles join too**, via `turn/
race_titles.py race_title_merit_points()` -- dispatched generically
through `_OFFICE_RACE` (the inverse of that module's own `RACE_TITLE_
OFFICE`) rather than one `if` branch per race, since all 11 share the
exact same formula shape. Two things this generic loop does *not*
handle on its own, both applied explicitly:

- **Phase 1191 correction: these titles DO grant Victory Points**, same
  as every other real Imperial Office -- `turn/victory_points.py
  office_victory_points()` applies `OFFICE_VALUE[office] * (1-reduct)`
  uniformly with no exclusion list, and `turn/final_standings.py
  kingdom_points()` sums it over every office in `ALL_OFFICES`, which
  includes all 11 race titles. (This module's own Phase 633 addendum,
  below, already establishes this reading: it treats `ALL_OFFICES`'
  sum as correct and complete for the 44 offices it does cover, fixing
  only the 3 army-scoped titles' *absence* from that set -- not a
  second, narrower exclusion for these 11.) The claim this replaced --
  that `OFFICE_VALUE`'s own real, non-zero Phase-81-sourced values for
  these 11 "describe a different in-game effect than the 8 majors' own
  Victory Point share" -- predates Phase 439's real `Pray_Report`
  formula being pinned down and was never revisited once that formula
  confirmed every real Office (this project's own `OFFICE_VALUE`
  included) banks real Victory Points uniformly; this module still
  resolves *who holds the title*, not what it's worth -- that part was
  always correct, only the VP-exclusion claim was wrong.
- **The turn gate** ("questa carica entra in gioco alla fine del turno
  N") is an office-level cutoff, not a per-leader one -- `resolve_
  office_holder()` returns `None` outright for any of these 11 offices
  before `state.turn_number` reaches `RACE_TITLE_TURN_GATE[race]`,
  even if some leader's own tally already clears `OFFICE_MIN_POINTS`.

**Phase 368: the 6 alignment-King titles plus Chief of Staff/Silver
Tongue join too**, via 8 new `turn/merit_points.py` formula functions
(`divinearchangel_merit_points()`, `goodking_merit_points()`,
`druidking_merit_points()`, `neutralking_merit_points()`,
`paganking_merit_points()`, `undeadking_merit_points()`,
`chiefofstaff_merit_points()`, `silvertongue_merit_points()`) --
one `if` branch each in `_leader_merit_points()`, not a generic table
dispatch like the race titles, since these 8 don't share one common
formula shape the way the 11 race titles do (different `Ability`
pairs, different eligibility rules per title). **Phase 369 corrected
every one of these 8 formulas** (plus King of Pain/Prince of Thieves
and the 11 race titles) against a real disassembly of `AKGEN.EXE`/
`AK.EXE`/`AK.OVR` -- the `CARICHE E ABILITÀ.txt` source these phases
built from turned out not to match the real compiled formulas. See
`turn/merit_points.py`/`turn/race_titles.py`'s own Phase 369 addenda
for exactly what changed; this module's own dispatch shape (which
branch calls which function) didn't need to change, only what each
function computes. Like the 11 race titles and King of Pain/Prince of
Thieves before them, these 8 DO grant Victory Points, same Phase 1191
correction as above -- `models/office.py OFFICE_VALUE` (Phase 81) is
their real per-office VP quota, not a different, VP-exempt figure --
and none of the 6 alignment-King titles has a turn gate stated in the
source --
unlike the 11 race titles, no office-level cutoff is applied here.
Each formula function already returns 0/None
for an ineligible leader on its own (King-only, alignment-gated where
stated), so this generic Rank-contest loop needs no additional
special-casing for any of the 8, the same "eligibility lives in the
formula, not the loop" shape Phase 277 established.

**Phase 379: 18 more leader-scoped royal titles join** (4 magic-school,
6 terrain-King, Battle Fool, Curator, Teacher, Assassin, Duellist,
Wingman, Cravenest, Bravest) -- one `if` branch each in `_leader_merit_
points()`, same shape as Phase 368's 8. These 18 DO grant Victory
Points too (Phase 1191 correction, same as the 11 race titles and the
previous 8 above), and none is exempted from the death penalty (see
`turn/merit_points.py`'s own Phase 379 addendum, which also explains why the
remaining 3 titles the source names -- `AIR_FORCE`/`PRAETOR`/
`FLAGSHIP` -- were deliberately **not** modeled there: they're
army-scoped, not leader-scoped, and don't fit `OfficeHolder.leader_id`
-only shape at all.

**Phase 394 closes that gap** with a parallel, army-scoped resolution
path: `ArmyOfficeHolder` (an `army_id`, not a `leader_id`),
`ARMY_RANKED_OFFICES` (just the 3), `resolve_army_office_holder()`/
`resolve_all_army_office_holders()`. Deliberately a *separate* set of
functions rather than folded into `RANKED_OFFICES`/`resolve_office_
holder()` -- every existing caller of those (`describe_imperial_office_
report()` included) already assumes every holder has a `leader_id` and
looks it up in `state.leaders`; forcing an army-scoped holder through
that same path would either crash or need a leaked "is this an army or
a leader" branch deep inside otherwise-uniform leader code. Each of the
3 real scoring formulas needed one new piece this project didn't have
before: `turn/army_quality.py army_peacetime_strength()`, an "Army_Str
outside of battle" reading built on that module's own pre-existing
`compute_army_modified_quality()` (Phase 279) -- see that function's
own Phase 394 addendum for exactly which of `turn/strength.py compute_
effective_strength()`'s many battle-only parameters do and don't have
a coherent "at rest" value, the concern `turn/merit_points.py`'s own
Phase 379 addendum raised and left for "a future phase that can
address both honestly." Eligibility (`army: quality Crack or Elite,
flying, with a valid player owner`, etc.) is gated on this same
peacetime-modified quality, not raw `ArmyState.quality`, for the same
reason the score itself is: both already run through `compute_army_
modified_quality()`, so a bonus that lifts an army up to Crack (or a
penalty that drops it below) is honored consistently by both.
Praetorian Guard's own extra `+base movement speed of army type` term
reads `models/army_type.py ARMY_TABLE[army_type].speed` directly, no
new data needed.

**Phase 633 closes the two loose ends Phase 394 itself flagged**:
Victory Points were never actually awarded for these 3 titles (`turn/
final_standings.py kingdom_points()` only ever summed `ALL_OFFICES`,
which deliberately excludes `ARMY_RANKED_OFFICES` -- up to 6 real
Victory Points per game were unreachable by any Kingdom; `turn/
victory_points.py army_office_victory_points()` closes this, mirroring
`office_victory_points()`'s own real formula exactly, sourced from
`resolve_army_office_holder()` and the winning army's own `kingdom_id`
instead of a leader's), and the same Phase 475 tier-1 stickiness tie-
break now applies here too, via a new, deliberately separate `GameState.
army_office_holders` dict (`leader_id`s and `army_id`s are different
integer namespaces that can collide numerically, so this doesn't share
`office_holders` -- see that new field's own docstring) and a new
`commit_army_office_holders()` mirroring `commit_office_holders()`
exactly. Each title's own `"effect_while_held"` bonus (`models/
office.py`'s own real "Improved Training" text -- doubled quality-
improvement chance for matching unit types, 1.5x for non-matching) is
now wired (Phase 641, `turn/practice_execution.py _improved_training_
multiplier()`, hooked into `execute_practice_tactical()`/`_group()`'s
own [6.1] army-quality-training roll -- resolved fresh via `resolve_
army_office_holder()` here, not the sticky commit-cache). **Phase 735
correction**: report-layer visibility for these 3 titles is wired too,
since Phase 668 -- `report/turn_report.py describe_imperial_office_
report()` has a second, real loop over `ARMY_RANKED_OFFICES` (`resolve_
army_office_holder()`/`kingdom_best_army_candidate()`/`_army_office_
candidate_line()`), the same suppression-gate shape the 39 minor
leader titles already use.

**Phase 475 -- the real tier-1 tie-break, ``AKGEN_reverse_engineering_
report (2).md`` SS14.4, real disassembly source**: "per i titoli
avanzati, il titolare precedente conserva precedenza se è fra i pari"
(for advanced titles, the previous titleholder retains precedence if
tied) -- a tier this module's own tie-break had never implemented for
any of the 47 leader-scoped offices, confirmed missing by this exact
docstring's own prior wording ("the general rule's own 'prefer the
current holder' tier was never implemented for any of the other 47
offices"). `resolve_office_holder()` now reads `state.office_holders.
get(office)` and prepends a `1`/`0` stickiness flag ahead of `turn/
merit_points.py merit_point_tiebreak_key()`'s own 3-tuple (treasury,
Tax_Base, `-leader_id`) -- deliberately done at the call site, not by
changing `merit_point_tiebreak_key()`'s own signature, since that
function's tuple shape is independently tested and has nothing to do
with *which* office is being resolved. `GameState.office_holders`
itself is never written by `resolve_office_holder()` -- reading and
writing "the current winner" in the same resolution pass would let the
tie-break see this turn's own still-in-progress result instead of last
turn's settled one. `commit_office_holders()` (below) is the caller's
own explicit "persist this turn's results for next turn's tie-break"
step, the same "caller's job, no `turn_processor.py` wiring" convention
`turn/scientific_treaty.py`'s own Phase 474 addendum already
established for a comparable "no natural once-per-turn hook exists"
gap. Emperor is unaffected (resolved via `state.emperor_kingdom_id`
directly, never through this tie-break loop at all).

**Phase 438 adds the real per-Kingdom ranking primitives** (`leader_
office_rank()`, `office_rival_best_points()`, `kingdom_best_candidate()`,
`kingdom_runner_up()`) that `report/turn_report.py describe_imperial_
office_report()` (Phase 440) needs to reproduce `REPORTS.PAS Pray_
Report`'s own rank-number/percentage-of-rival/per-Kingdom-runner-up
columns -- the gap that same composer's own docstring had flagged since
Phase 435 as "a substantially larger feature." These are pure additions;
`resolve_office_holder()`/`resolve_all_office_holders()` keep their
existing signature and behavior unchanged for their other callers
(`turn/battle_orchestrator.py`, `turn/tax_base.py`).

**Phase 550 -- the Valhalla visitor is excluded from every Rank
contest.** A fresh audit of `CARICHE E ABILITÀ.txt`/`ABILITÀ SOPRA IL
LIVELLO 4 OK.txt` (finding both otherwise fully and correctly consumed
already, Phase 367-379) cross-checked `AKGEN_reverse_engineering_
report.md` too, which gives a real, save-file-verified example (line
1440): "Il visitatore di Valhalla 'Two-Headed Eagle' ha 127 punti da
Maresciallo ma viene esplicitamente escluso dal selettore delle
cariche; per questo il titolare corretto resta Giovanna con 72. Questa
esclusione è indispensabile per riprodurre il salvataggio." Nothing
previously excluded `VALHALLA_VISITOR_LEADER_ID` from this loop --
`resolve_office_holder()` now skips them outright, regardless of how
high their own Merit Points happen to be during their one active turn
(`turn/valhalla_execution.py`, Phase 546-548). Emperor is unaffected
(never resolved through this loop at all); the 3 army-scoped offices
are unaffected too (the visitor is a leader, never an army).
"""

from __future__ import annotations

from dataclasses import dataclass

from ak_engine.models.army_type import OVERFLIGHT_AIR, ARMY_TABLE, SEA_ARMY_TYPES, ArmyType, is_land_army
from ak_engine.models.enums import Ability
from ak_engine.models.game_state import ArmyState, GameState, LeaderState
from ak_engine.models.office import OFFICE_MIN_POINTS, Office
from ak_engine.models.temper import raise_temper_one_level
from ak_engine.models.race import Race
from ak_engine.models.valhalla import VALHALLA_VISITOR_LEADER_ID
from ak_engine.turn.combat import Quality
from ak_engine.turn.leader_queries import find_king_of_kingdom
from ak_engine.turn.tax_base import compute_tax_base
from ak_engine.turn.merit_points import (
    admiral_merit_points,
    assassin_merit_points,
    battlefool_merit_points,
    bravest_merit_points,
    chancellor_merit_points,
    chiefofstaff_merit_points,
    cravenest_merit_points,
    curator_merit_points,
    defender_merit_points,
    desertking_merit_points,
    divinearchangel_merit_points,
    druidking_merit_points,
    duellist_merit_points,
    elementalmage_merit_points,
    emperor_merit_points,
    evilking_merit_points,
    forestking_merit_points,
    goodking_merit_points,
    illusionistmage_merit_points,
    jungleking_merit_points,
    mage_merit_points,
    marshal_merit_points,
    merit_point_tiebreak_key,
    mountainking_merit_points,
    necromancermage_merit_points,
    neutralking_merit_points,
    paganking_merit_points,
    plainsking_merit_points,
    priest_merit_points,
    psychicmage_merit_points,
    seaking_merit_points,
    silvertongue_merit_points,
    teacher_merit_points,
    thiefprince_merit_points,
    treasurer_merit_points,
    undeadking_merit_points,
    wingman_merit_points,
)
from ak_engine.turn.race_titles import RACE_TITLE_OFFICE, RACE_TITLE_TURN_GATE, race_title_merit_points

# Race title offices, keyed by their own Office (the inverse of
# RACE_TITLE_OFFICE) -- Phase 367.
_OFFICE_RACE: dict[Office, Race] = {office: race for race, office in RACE_TITLE_OFFICE.items()}

# Every office except Emperor (resolved separately, see module docstring)
# is a genuine Merit Point Rank contest across every leader in the game.
RANKED_OFFICES: tuple[Office, ...] = (
    Office.CHANCELLOR,
    Office.TREASURER,
    Office.MARSHAL,
    Office.ADMIRAL,
    Office.DEFENDER,
    Office.PRIEST,
    Office.MAGE,
    Office.EVIL_KING,
    Office.THIEF_PRINCE,
    *RACE_TITLE_OFFICE.values(),
    Office.DIVINE_KING,
    Office.GOOD_KING,
    Office.DRUID_KING,
    Office.NEUTRAL_KING,
    Office.PAGAN_KING,
    Office.UNDEAD_KING,
    Office.CHIEF_OF_STAFF,
    Office.DIPLOMAT,
    Office.ELE_MAGE,
    Office.ILLUS_MAGE,
    Office.NECRO_MAGE,
    Office.PSYCHIC_MAGE,
    Office.PLAINS_KING,
    Office.DESERT_KING,
    Office.JUNGLE_KING,
    Office.FOREST_KING,
    Office.MOUNTAIN_KING,
    Office.SEA_KING,
    Office.BATTLE_FOOL,
    Office.CURATOR,
    Office.TEACHER,
    Office.ASSASSIN,
    Office.DUELLIST,
    Office.WINGMAN,
    Office.CRAVENEST,
    Office.BRAVEST,
)

# All 47 real Imperial Offices this project models, in the rulebook's own
# table order (EVIL_KING/THIEF_PRINCE appended Phase 277, the 11 race
# titles appended Phase 367, the 6 alignment-King titles plus Chief of
# Staff/Silver Tongue appended Phase 368, 18 more leader-scoped royal
# titles appended Phase 379 -- see each phase's own module docstring
# note). AIR_FORCE/PRAETOR/FLAGSHIP (army-scoped, not leader-scoped) are
# deliberately not modeled here -- see `turn/merit_points.py`'s own
# Phase 379 addendum.
ALL_OFFICES: tuple[Office, ...] = (Office.EMPEROR, *RANKED_OFFICES)


@dataclass(slots=True)
class OfficeHolder:
    leader_id: int
    merit_points: int | float


def _leader_merit_points(
    office: Office,
    state: GameState,
    leader: LeaderState,
    *,
    tax_base_cache: dict[int, int] | None = None,
    rich_sea_cache: dict[int, int] | None = None,
) -> int | float:
    if office is Office.CHANCELLOR:
        return chancellor_merit_points(state, leader)
    if office is Office.TREASURER:
        return treasurer_merit_points(state, leader.kingdom_id) if leader.kingdom_id is not None else 0
    if office is Office.MARSHAL:
        return marshal_merit_points(leader)
    if office is Office.ADMIRAL:
        return admiral_merit_points(state, leader, rich_sea_cache=rich_sea_cache)
    if office is Office.DEFENDER:
        return defender_merit_points(leader)
    if office is Office.PRIEST:
        return priest_merit_points(state, leader)
    if office is Office.MAGE:
        return mage_merit_points(state, leader)
    if office is Office.EVIL_KING:
        return evilking_merit_points(state, leader, tax_base_cache=tax_base_cache)
    if office is Office.THIEF_PRINCE:
        return thiefprince_merit_points(state, leader)
    if office is Office.DIVINE_KING:
        return divinearchangel_merit_points(state, leader, tax_base_cache=tax_base_cache)
    if office is Office.GOOD_KING:
        return goodking_merit_points(state, leader, tax_base_cache=tax_base_cache)
    if office is Office.DRUID_KING:
        return druidking_merit_points(state, leader, tax_base_cache=tax_base_cache)
    if office is Office.NEUTRAL_KING:
        return neutralking_merit_points(state, leader, tax_base_cache=tax_base_cache)
    if office is Office.PAGAN_KING:
        return paganking_merit_points(state, leader, tax_base_cache=tax_base_cache)
    if office is Office.UNDEAD_KING:
        return undeadking_merit_points(state, leader, tax_base_cache=tax_base_cache)
    if office is Office.CHIEF_OF_STAFF:
        return chiefofstaff_merit_points(state, leader)
    if office is Office.DIPLOMAT:
        return silvertongue_merit_points(state, leader)
    if office is Office.ELE_MAGE:
        return elementalmage_merit_points(leader)
    if office is Office.ILLUS_MAGE:
        return illusionistmage_merit_points(leader)
    if office is Office.NECRO_MAGE:
        return necromancermage_merit_points(leader)
    if office is Office.PSYCHIC_MAGE:
        return psychicmage_merit_points(leader)
    if office is Office.PLAINS_KING:
        return plainsking_merit_points(leader)
    if office is Office.DESERT_KING:
        return desertking_merit_points(leader)
    if office is Office.JUNGLE_KING:
        return jungleking_merit_points(leader)
    if office is Office.FOREST_KING:
        return forestking_merit_points(leader)
    if office is Office.MOUNTAIN_KING:
        return mountainking_merit_points(leader)
    if office is Office.SEA_KING:
        return seaking_merit_points(leader)
    if office is Office.BATTLE_FOOL:
        return battlefool_merit_points(leader)
    if office is Office.CURATOR:
        return curator_merit_points(state, leader)
    if office is Office.TEACHER:
        return teacher_merit_points(leader)
    if office is Office.ASSASSIN:
        return assassin_merit_points(leader)
    if office is Office.DUELLIST:
        return duellist_merit_points(leader)
    if office is Office.WINGMAN:
        return wingman_merit_points(leader)
    if office is Office.CRAVENEST:
        return cravenest_merit_points(leader)
    if office is Office.BRAVEST:
        return bravest_merit_points(leader)
    if office in _OFFICE_RACE:
        return race_title_merit_points(state, leader, _OFFICE_RACE[office])
    raise ValueError(f"{office} is not a ranked office -- Emperor is resolved via resolve_office_holder() directly")


def leader_office_merit_points(office: Office, state: GameState, leader: LeaderState) -> int | float:
    """Public wrapper around ``_leader_merit_points()`` for a caller (the
    GM web interface's own ``MeritTally`` display) that wants one
    specific leader's own current score for one specific office,
    regardless of who's actually winning it right now --
    ``resolve_office_holder()`` only ever returns the current top
    scorer, discarding every other candidate's own number.
    """

    return _leader_merit_points(office, state, leader)


def resolve_office_holder(
    state: GameState,
    office: Office,
    *,
    _tax_base_cache: dict[int, int] | None = None,
    _rich_sea_cache: dict[int, int] | None = None,
) -> OfficeHolder | None:
    """The leader who currently holds `office`, and their own Merit
    Points -- or `None` if nobody qualifies yet. See module docstring
    for Emperor's own special-cased resolution, the Rank-contest rules
    governing the other 47, and the Phase 475 addendum for the
    ``state.office_holders``-backed tier-1 tie-break below.

    ``_tax_base_cache``/``_rich_sea_cache`` (Phase 1193 efficiency,
    leading underscore since they're an internal performance detail, not
    part of this function's own public contract): optional ``{kingdom_id:
    value}`` dicts ``resolve_all_office_holders()`` builds once and
    shares across all 47 offices it resolves in one call -- see ``turn/
    merit_points.py _alignment_king_merit_points()``/``_rich_sea_
    province_count()``'s own docstrings for why reusing them across
    offices (not just across leaders within *this* one office's own
    loop below) is still safe: resolving every office is one atomic,
    read-only pass over `state`, with no mutation between offices either.
    A caller that resolves just one office in isolation (every pre-
    existing caller) gets a fresh, call-scoped dict instead -- still
    removes the redundant per-leader rescan within this one call's own
    loop, just not the cross-office rescan `resolve_all_office_holders()`
    additionally avoids.
    """

    if office is Office.EMPEROR:
        if state.emperor_kingdom_id is None:
            return None
        king = find_king_of_kingdom(state, state.emperor_kingdom_id)
        if king is None:
            return None
        return OfficeHolder(king.leader_id, emperor_merit_points(state, state.emperor_kingdom_id))

    if office not in RANKED_OFFICES:
        raise ValueError(f"{office} is not one of the 47 real Imperial Offices this project models")

    if office.value > Office.MAGE.value and state.enabled_optional_offices is not None and office not in state.enabled_optional_offices:
        return None  # a title the GM left out of this game: nobody holds it, and its perk does nothing

    if office in _OFFICE_RACE:
        turn_gate = RACE_TITLE_TURN_GATE[_OFFICE_RACE[office]]
        if state.turn_number < turn_gate:
            return None

    min_points = OFFICE_MIN_POINTS[office]
    previous_holder_id = state.office_holders.get(office)
    best: OfficeHolder | None = None
    best_tiebreak: tuple[int, int, int, int] | None = None
    tax_base_cache = _tax_base_cache if _tax_base_cache is not None else {}
    rich_sea_cache = _rich_sea_cache if _rich_sea_cache is not None else {}

    for leader_id, leader in state.leaders.items():
        if leader_id == VALHALLA_VISITOR_LEADER_ID:
            # Phase 550 -- AKGEN_reverse_engineering_report.md line 1440's
            # own real save-file example: "Il visitatore di Valhalla
            # 'Two-Headed Eagle' ha 127 punti da Maresciallo ma viene
            # esplicitamente escluso dal selettore delle cariche; per
            # questo il titolare corretto resta Giovanna con 72." The
            # visitor is never a genuine office candidate, however high
            # their own Merit Points happen to be during their one active
            # turn -- confirmed indispensable to reproduce that save.
            continue
        if leader.kingdom_id is None:
            # User ruling 2026-11-28: the points of an Imperial Office do not count for an independent Hero (one in no
            # Kingdom's service) -- a free Hero never holds an office.
            continue
        points = _leader_merit_points(office, state, leader, tax_base_cache=tax_base_cache, rich_sea_cache=rich_sea_cache)
        if points < min_points:
            continue
        stickiness = 1 if leader_id == previous_holder_id else 0
        tiebreak = (stickiness, *merit_point_tiebreak_key(state, leader))
        if best is None or points > best.merit_points or (points == best.merit_points and tiebreak > best_tiebreak):
            best = OfficeHolder(leader_id, points)
            best_tiebreak = tiebreak

    return best


def emperor_best_hope(state: GameState) -> OfficeHolder | None:
    """Who "holds" the World Emperor title in the reports: the elected Emperor once there is one, before that the King of
    the Kingdom with the largest tax base -- the "best hope to become the next World Emperor" that wears the Emerald
    Crown ("for as long as you are the best hope", real reports) and has its "Know Tax Bases" perk. A tie for the lead,
    or no Kingdom with any tax base yet, leaves it with nobody."""

    elected = resolve_office_holder(state, Office.EMPEROR)
    if elected is not None:
        return elected
    ranked = sorted(
        ((emperor_merit_points(state, kingdom_id), kingdom_id) for kingdom_id in state.kingdoms), reverse=True
    )
    if not ranked or ranked[0][0] <= 0 or (len(ranked) > 1 and ranked[1][0] == ranked[0][0]):
        return None
    king = find_king_of_kingdom(state, ranked[0][1])
    return OfficeHolder(king.leader_id, ranked[0][0]) if king is not None else None


def cached_office_holder_leader_id(
    state: GameState, office: Office, cache: dict[Office, int | None] | None = None
) -> int | None:
    """``resolve_office_holder(state, office)``'s own ``leader_id``,
    optionally memoized in a caller-supplied ``{Office: leader_id}``
    dict -- the same "safe only within one atomic read-only pass"
    reasoning as this module's own ``resolve_all_office_holders()``
    cache parameters (Phase 1193 efficiency). Used by several files'
    own duplicate ``_leader_combatant()``-style Combatant builders
    (``turn/patrol_execution.py``, ``turn/pursue_execution.py``, ``turn/
    challenge_execution.py``, ``turn/battle_orchestrator.py
    _commander_combatant``; see each one's own docstring for why the
    builders themselves stay duplicated, not merged) to avoid re-
    resolving the same turn-global office 3 times when building 2
    sibling Combatants (e.g. challenger+target) in one call.
    """

    if cache is not None and office in cache:
        return cache[office]
    holder = resolve_office_holder(state, office)
    leader_id = holder.leader_id if holder is not None else None
    if cache is not None:
        cache[office] = leader_id
    return leader_id


def resolve_all_office_holders(state: GameState) -> dict[Office, OfficeHolder | None]:
    """All 47 real Imperial Offices at once, each resolved via
    `resolve_office_holder()`. Shares one ``tax_base``/``rich_sea``
    cache pair across every office resolved this call -- see that
    function's own docstring for why that's safe here specifically.
    """

    tax_base_cache: dict[int, int] = {}
    rich_sea_cache: dict[int, int] = {}
    return {
        office: resolve_office_holder(state, office, _tax_base_cache=tax_base_cache, _rich_sea_cache=rich_sea_cache)
        for office in ALL_OFFICES
    }


def commit_office_holders(state: GameState) -> dict[Office, OfficeHolder | None]:
    """Phase 475: resolves every one of the 47 leader-scoped offices via
    `resolve_all_office_holders()`, then persists each non-`None` result's
    own `leader_id` into `state.office_holders` -- the caller's own
    explicit "settle this turn's results for next turn's tie-break" step
    (see `GameState.office_holders`'s own docstring for why this can't be
    done implicitly inside `resolve_office_holder()` itself). An office
    with no current qualifying candidate is left untouched in `state.
    office_holders` (its last known holder stays sticky rather than being
    cleared -- see that field's own docstring), not overwritten with
    `None`. Emperor is included in the returned dict (via `resolve_all_
    office_holders()`) but never written to `state.office_holders`,
    since `resolve_office_holder(state, Office.EMPEROR)` never reads it
    either -- Emperor's own resolution is a direct `state.emperor_
    kingdom_id` lookup, not a Rank-contest tie-break.

    **Phase 676**: the real call site is `orchestrator.py process_turn()`,
    right after the election/final-standings step -- see that function's
    own Phase 676 docstring addendum.

    **2026-11-20 bug fix**: also computes `state.office_title_change_
    notices` -- the real `titchar[ofc] <> prevchar[ofc]` comparison
    (SS93.1) that gates SAY.PAS's own `_ODesc` title-acquisition
    narrative (`models/office.py OFFICE_TITLE_DESCRIPTION`, confirmed
    real but never wired anywhere else -- see that field's own
    docstring). Must compare against the *previous* `state.office_
    holders[office]` before this same call overwrites it below, so the
    comparison is done first, per office, right alongside the write.
    Freshly overwritten every call (not merged/appended) since this
    runs exactly once per real turn -- a leader who held an office
    before this method ever ran (a loaded mid-game save, say) reads as
    a "new" acquisition the first time `commit_office_holders()` is
    ever called for that game, same as the real engine's own `prevchar`
    starting at a sentinel no real leader_id can match.
    """

    results = resolve_all_office_holders(state)
    title_changes: dict[Office, int] = {}
    # The World Emperor row of the report: its "holder" is the best hope (see ``emperor_best_hope()``), who is told of
    # the Crown the turn he becomes it. The Emperor is not a Rank contest (``state.office_holders`` never holds it), so
    # who it was last turn is remembered apart, in ``state.emperor_best_hope_leader_id``.
    best_hope = emperor_best_hope(state)
    if best_hope is not None:
        if state.emperor_best_hope_leader_id != best_hope.leader_id:
            title_changes[Office.EMPEROR] = best_hope.leader_id
        state.emperor_best_hope_leader_id = best_hope.leader_id
    for office, holder in results.items():
        if office is Office.EMPEROR or holder is None:
            continue
        if state.office_holders.get(office) != holder.leader_id:
            title_changes[office] = holder.leader_id
        state.office_holders[office] = holder.leader_id
    state.office_title_change_notices = title_changes
    return results


def _ranking_candidates(state: GameState, office: Office) -> list[tuple[int, int | float]]:
    """(leader_id, points) for every real candidate for `office`, with
    **no** `OFFICE_MIN_POINTS` gate -- Phase 438, backing the ranking
    primitives below (`leader_office_rank`/`office_rival_best_points`/
    `kingdom_best_candidate`/`kingdom_runner_up`). The real `Rank()`
    (`REPORTS.PAS` ~line 1198-1250) never gates on `minpts` either; that
    gate only decides whether a row gets *printed*, a separate question
    `describe_imperial_office_report()` handles on its own (Phase 440).

    Same leader population `resolve_office_holder()`'s own scan already
    uses (every `state.leaders` entry, independent Heroes included, per
    that function's own docstring: "Anche un Eroe può aggiudicarsi una
    carica") -- deliberately not the real Pascal's own stricter `tlak <
    nkings` owning-King requirement, so ranking and "who holds it" stay
    consistent with each other within this project.

    **Emperor is a genuine special case**, same as `resolve_office_holder()`
    already treats it: only a Kingdom's own King is a candidate, scored via
    `emperor_merit_points()` (Tax_Base-based), not `_leader_merit_points()`
    (which explicitly refuses Emperor).

    **Phase 1191 bug fix**: this used to skip both real exclusions
    `resolve_office_holder()` applies -- the Valhalla visitor (Phase 550:
    never a genuine office candidate, however high their own Merit Points)
    and the race-title turn gate (`RACE_TITLE_TURN_GATE`: the office
    doesn't exist yet before it) -- so every ranking primitive built on
    this function (`leader_office_rank`/`office_rival_best_points`/
    `kingdom_best_candidate`/`kingdom_runner_up`) could surface the
    visitor as a rival/best-candidate, or a race title before its own
    gate turn, contradicting this function's own "ranking and 'who holds
    it' stay consistent with each other" claim above.
    """

    if office in _OFFICE_RACE:
        turn_gate = RACE_TITLE_TURN_GATE[_OFFICE_RACE[office]]
        if state.turn_number < turn_gate:
            return []

    candidates: list[tuple[int, int | float]] = []
    for leader_id, leader in state.leaders.items():
        if leader_id == VALHALLA_VISITOR_LEADER_ID:
            continue
        if office is Office.EMPEROR:
            if not leader.is_king or leader.kingdom_id is None:
                continue
            points = emperor_merit_points(state, leader.kingdom_id)
        else:
            points = _leader_merit_points(office, state, leader)
        candidates.append((leader_id, points))
    return candidates


def leader_office_rank(state: GameState, office: Office, leader_id: int) -> int:
    """The real `Rank()`: 1 + how many other real candidates for `office`
    strictly outscore this leader. Ties share a rank -- only strictly
    greater scores count towards `betters`, matching `Rank:= betters+1`
    exactly. Phase 438.
    """

    leader = state.leaders[leader_id]
    own_points = (
        emperor_merit_points(state, leader.kingdom_id)
        if office is Office.EMPEROR and leader.kingdom_id is not None
        else _leader_merit_points(office, state, leader)
    )
    betters = sum(
        1 for other_id, points in _ranking_candidates(state, office) if other_id != leader_id and points > own_points
    )
    return betters + 1


def office_rival_best_points(state: GameState, office: Office, kingdom_id: int) -> int | float:
    """The real `ftoppts`: the best score among candidates whose own
    Kingdom isn't `kingdom_id` -- `0` if nobody outside this Kingdom is
    even a candidate, matching the real `ftoppts:= 0` initializer never
    being overwritten in that case. Phase 438.
    """

    rival_scores = [
        points for other_id, points in _ranking_candidates(state, office) if state.leaders[other_id].kingdom_id != kingdom_id
    ]
    return max(rival_scores, default=0)


def kingdom_best_candidate(state: GameState, office: Office, kingdom_id: int) -> OfficeHolder | None:
    """This Kingdom's own top-scoring candidate for `office`, **not**
    gated by `OFFICE_MIN_POINTS` -- the real pre-election "Best Hope" scan
    (`REPORTS.PAS Pray_Report` ~line 1605-1626) never applies that gate
    either; `describe_imperial_office_report()` (Phase 440) applies it
    separately, only when deciding whether to print a row at all. Ties go
    to the lower `leader_id` (stable scan order) -- simpler than the real
    nested `Rank()`-based tiebreak Pascal only invokes for an exact points
    tie, the same "readable, not exhaustively pixel-perfect" simplification
    this composer's prose sections already use elsewhere. Phase 438.
    """

    best: OfficeHolder | None = None
    for leader_id, points in _ranking_candidates(state, office):
        if state.leaders[leader_id].kingdom_id != kingdom_id:
            continue
        if best is None or points > best.merit_points:
            best = OfficeHolder(leader_id, points)
    return best


def kingdom_runner_up(state: GameState, office: Office, kingdom_id: int, exclude_leader_id: int) -> OfficeHolder | None:
    """This Kingdom's own second-best candidate for `office`, excluding
    the leader already chosen as its top candidate -- the real `nextldr`
    (always scoped `lak = kng`, regardless of Emperor-election state).
    Phase 438.
    """

    best: OfficeHolder | None = None
    for leader_id, points in _ranking_candidates(state, office):
        if leader_id == exclude_leader_id:
            continue
        if state.leaders[leader_id].kingdom_id != kingdom_id:
            continue
        if best is None or points > best.merit_points:
            best = OfficeHolder(leader_id, points)
    return best


# The 3 army-scoped Royal Titles (Phase 394) -- see module docstring's own
# Phase 394 addendum. Kept out of RANKED_OFFICES/ALL_OFFICES: every
# existing consumer of those (resolve_office_holder(), resolve_all_office_
# holders(), describe_imperial_office_report()) assumes a leader_id.
ARMY_RANKED_OFFICES: tuple[Office, ...] = (Office.AIR_FORCE, Office.PRAETOR, Office.FLAGSHIP)

# Flagship's own "type Mermen, Whale League or Fleet" eligibility gate --
# this is exactly `models/army_type.py SEA_ARMY_TYPES`, reused directly
# rather than a second, locally-duplicated frozenset of the same 3 types.


@dataclass(slots=True)
class ArmyOfficeHolder:
    army_id: int
    merit_points: float


def _army_office_eligible(office: Office, army: ArmyState, modified_quality: Quality) -> bool:
    if army.kingdom_id is None:
        return False
    if modified_quality not in (Quality.CRACK, Quality.ELITE):
        return False
    if office is Office.AIR_FORCE:
        return army.army_type in OVERFLIGHT_AIR
    if office is Office.PRAETOR:
        # Real text (models/office.py OFFICE_TITLE_DESCRIPTION): "the
        # military land unit best suited..." -- `is_land_army()` (not
        # in OVERFLIGHT_AIR) excludes both air *and* sea types, matching
        # this project's own established land/sea/air three-way split
        # (models/army_type.py). A bare `not in OVERFLIGHT_AIR` check
        # here would wrongly also admit Fleet/Mermen/Whales, letting a
        # naval army qualify for Praetor and Flagship simultaneously.
        return is_land_army(army.army_type)
    if office is Office.FLAGSHIP:
        return army.army_type in SEA_ARMY_TYPES
    raise ValueError(f"{office} is not one of the 3 army-scoped Royal Titles")


def _army_office_tiebreak_key(state: GameState, army: ArmyState) -> tuple[int, int, int]:
    """Same shape as `merit_point_tiebreak_key()` (treasury, tax base, lower
    id wins) against the army's own owning Kingdom rather than a leader's.
    """

    kingdom = state.kingdoms[army.kingdom_id]
    return (kingdom.treasury, compute_tax_base(state, army.kingdom_id), -army.army_id)


def _army_ranking_candidates(state: GameState, office: Office) -> list[tuple[int, int | float]]:
    """(army_id, score) for every real candidate for `office`, mirroring
    `_ranking_candidates()`'s own role for the 47 leader-scoped offices
    -- no `OFFICE_MIN_POINTS` gate here either, backing `army_office_
    rank()`/`army_office_rival_best_points()`/`kingdom_best_army_
    candidate()`/`kingdom_runner_up_army()` (Phase 668) the same way.
    `resolve_army_office_holder()` applies the min-points gate and
    stickiness tiebreak itself, on top of this shared candidate list --
    extracted from that function's own original inline loop, pure
    refactor, no behavior change.

    Local import of `turn/army_quality.py`, see `resolve_army_office_
    holder()`'s own docstring for why it can't be module-level.
    """

    from ak_engine.turn.army_quality import army_peacetime_strength, compute_army_modified_quality

    ability = Ability.NAVAL if office is Office.FLAGSHIP else Ability.TACTICAL
    candidates: list[tuple[int, int | float]] = []
    for army_id, army in state.armies.items():
        if army.kingdom_id is None:
            continue
        modified_quality = compute_army_modified_quality(state, army)
        if not _army_office_eligible(office, army, modified_quality):
            continue
        # Bug fix (crash): Elephants/Dinosaurs have no fixed base strength
        # outside an actual battle (it's rolled per-battle, see turn/
        # strength.py's own _base_strength() -- army_peacetime_strength()
        # never has a battle roll to supply as its override, so it always
        # raises here for these two). 8 further real ArmyType ordinals
        # (Vampires/Marauders/Shamans/Crossbow/Javelins/Artillery/Spiders/
        # D_Turtle -- models/army_type.py's own Phase 383 addendum) have
        # no rulebook-sourced Speed/Strength data at all -- an honest
        # sourcing gap, not something to invent a number for -- and raise
        # a bare KeyError from ARMY_TABLE/BASE_STRENGTH instead. Any one
        # of these army types reaching Quality Crack/Elite (an entirely
        # ordinary outcome of ordinary battle/Oratory for Elephants) used
        # to crash this whole function -- and therefore every Royal Title
        # resolution, called unconditionally every turn with no caller
        # anywhere up to the Flask route catching it. No sourced rule
        # says how an army whose own strength can't be computed at rest
        # should rank for a Royal Title, so it's excluded from candidacy
        # here instead -- the safe, non-inventive choice.
        try:
            score = army_peacetime_strength(state, army, ability)
            if office is Office.PRAETOR:
                score += ARMY_TABLE[army.army_type].speed
        except (ValueError, KeyError):
            continue
        candidates.append((army_id, score))
    return candidates


def resolve_army_office_holder(state: GameState, office: Office) -> ArmyOfficeHolder | None:
    """The army that currently holds one of the 3 army-scoped Royal
    Titles (Airforce/Praetor/Flagship), and its own "Army_Str" score --
    or `None` if no army qualifies yet. See module docstring's own Phase
    394 addendum.
    """

    if office not in ARMY_RANKED_OFFICES:
        raise ValueError(f"{office} is not one of the 3 army-scoped Royal Titles this project models")

    if state.enabled_optional_offices is not None and office not in state.enabled_optional_offices:
        return None  # a title the GM left out of this game

    min_points = OFFICE_MIN_POINTS[office]
    previous_holder_id = state.army_office_holders.get(office)
    best: ArmyOfficeHolder | None = None
    best_tiebreak: tuple[int, int, int, int] | None = None

    for army_id, score in _army_ranking_candidates(state, office):
        if score < min_points:
            continue
        army = state.armies[army_id]
        stickiness = 1 if army_id == previous_holder_id else 0
        tiebreak = (stickiness, *_army_office_tiebreak_key(state, army))
        if best is None or score > best.merit_points or (score == best.merit_points and tiebreak > best_tiebreak):
            best = ArmyOfficeHolder(army_id, score)
            best_tiebreak = tiebreak

    return best


def army_office_rank(state: GameState, office: Office, army_id: int) -> int:
    """The army-scoped equivalent of `leader_office_rank()`'s real
    `Rank()`: 1 + how many other real army candidates for `office`
    strictly outscore this one. Phase 668 -- see `describe_imperial_
    office_report()`'s own addendum for why this reuses the leader
    formula's exact shape against the army candidate pool instead.

    **Phase 1191 bug fix**: raises a clear `ValueError`, not an opaque
    `StopIteration`, when `army_id` doesn't itself qualify as a
    candidate for `office` (wrong Quality/ArmyType, or no base-strength
    data for its type) -- `_army_ranking_candidates()` silently drops
    such armies, so the old bare `next()` with no default crashed
    uninformatively instead of telling the caller why no rank exists.
    Every real call site (`report/turn_report.py`) only ever passes the
    office's own already-resolved holder, which is always a genuine
    candidate by construction, so this never actually fires today --
    it's a defensive fix for any future caller that doesn't guarantee
    that.
    """

    candidates = _army_ranking_candidates(state, office)
    own_points = next((points for aid, points in candidates if aid == army_id), None)
    if own_points is None:
        raise ValueError(f"army {army_id} is not itself a real candidate for {office}")
    betters = sum(1 for other_id, points in candidates if other_id != army_id and points > own_points)
    return betters + 1


def army_office_rival_best_points(state: GameState, office: Office, kingdom_id: int) -> int | float:
    """The army-scoped equivalent of `office_rival_best_points()`'s real
    `ftoppts`: the best score among army candidates whose own Kingdom
    isn't `kingdom_id`. Phase 668.
    """

    rival_scores = [
        points
        for other_id, points in _army_ranking_candidates(state, office)
        if state.armies[other_id].kingdom_id != kingdom_id
    ]
    return max(rival_scores, default=0)


def kingdom_best_army_candidate(state: GameState, office: Office, kingdom_id: int) -> ArmyOfficeHolder | None:
    """This Kingdom's own top-scoring army candidate for `office`, **not**
    gated by `OFFICE_MIN_POINTS` -- the army-scoped equivalent of
    `kingdom_best_candidate()`'s own pre-election "Best Hope" scan.
    Phase 668.
    """

    best: ArmyOfficeHolder | None = None
    for army_id, points in _army_ranking_candidates(state, office):
        if state.armies[army_id].kingdom_id != kingdom_id:
            continue
        if best is None or points > best.merit_points:
            best = ArmyOfficeHolder(army_id, points)
    return best


def kingdom_runner_up_army(
    state: GameState, office: Office, kingdom_id: int, exclude_army_id: int
) -> ArmyOfficeHolder | None:
    """This Kingdom's own second-best army candidate for `office`,
    excluding the army already chosen as its top candidate -- the
    army-scoped equivalent of `kingdom_runner_up()`. Phase 668.
    """

    best: ArmyOfficeHolder | None = None
    for army_id, points in _army_ranking_candidates(state, office):
        if army_id == exclude_army_id:
            continue
        if state.armies[army_id].kingdom_id != kingdom_id:
            continue
        if best is None or points > best.merit_points:
            best = ArmyOfficeHolder(army_id, points)
    return best


def resolve_all_army_office_holders(state: GameState) -> dict[Office, ArmyOfficeHolder | None]:
    """All 3 army-scoped Royal Titles at once, each resolved via
    `resolve_army_office_holder()`.
    """

    return {office: resolve_army_office_holder(state, office) for office in ARMY_RANKED_OFFICES}


def commit_army_office_holders(state: GameState) -> dict[Office, ArmyOfficeHolder | None]:
    """Phase 633: the same "settle this turn's results for next turn's
    tie-break" commit step `commit_office_holders()` already provides
    for the 47 leader-scoped offices, mirrored for the 3 army-scoped
    ones. Resolves every one of `ARMY_RANKED_OFFICES` via `resolve_all_
    army_office_holders()`, then persists each non-`None` result's own
    `army_id` into `state.army_office_holders`. An office with no
    current qualifying candidate is left untouched (its last known
    holder stays sticky, same "stale until overwritten" convention).
    Not wired into `turn_processor.py` -- neither is `commit_office_
    holders()` (that module runs once per *phase*, not once per real
    turn). **Phase 676**: the real call site is `orchestrator.py
    process_turn()`, right alongside `commit_office_holders()` -- see
    that function's own Phase 676 docstring addendum.

    **2026-11-20 bug fix**: also computes `state.army_office_title_
    change_notices`, the army-scoped mirror of `commit_office_holders()`'s
    own same-phase `office_title_change_notices` fix -- see that field's
    own docstring for the real `titchar[ofc] <> prevchar[ofc]` condition
    this reproduces.
    """

    results = resolve_all_army_office_holders(state)
    title_changes: dict[Office, int] = {}
    for office, holder in results.items():
        if holder is None:
            continue
        if state.army_office_holders.get(office) != holder.army_id:
            title_changes[office] = holder.army_id
        state.army_office_holders[office] = holder.army_id
    state.army_office_title_change_notices = title_changes
    return results


def apply_cravenest_temperament_escalation(state: GameState) -> None:
    """Report SS18.6: "Se fosse presente un titolare valido, REPORTS.PAS
    ne migliorerebbe il temperamento di un livello a ogni turno, fino a
    Berserk. L'effetto è implementato; è la via normale di
    qualificazione a essere guasta." -- the real compiled effect,
    applied every turn to whoever currently holds King of Cowards
    (`Office.CRAVENEST`), if anyone.

    `turn/merit_points.py cravenest_merit_points()`'s own docstring
    already documents the confirmed compiled bug that makes normal
    qualification unreachable (`courage_encounter_merit` can only ever
    be `<= 0`, but `OFFICE_MIN_POINTS[Office.CRAVENEST] = 5`, and
    `resolve_office_holder()` above never returns a candidate below
    `min_points`) -- so under real generated data this function is
    expected to be a no-op every turn, exactly matching the report's own
    framing ("è la via normale di qualificazione a essere guasta", not
    "l'effetto non esiste"). Modeled anyway, not skipped, since the
    effect itself is real and independently testable -- the same
    "confirmed mechanic before its consuming pipeline" pattern this
    project already uses elsewhere (e.g. Phase 463's Detect Illusions).
    """

    holder = resolve_office_holder(state, Office.CRAVENEST)
    if holder is None:
        return
    leader = state.leaders.get(holder.leader_id)
    if leader is None or leader.temper is None:
        return
    leader.temper = raise_temper_one_level(leader.temper)


def apply_battle_fool_aptitude_escalation(state: GameState) -> None:
    """`models/office.py OFFICE_TITLE_DESCRIPTION[Office.BATTLE_FOOL]`
    (Phase 660): "> aptitude in Tactics will increase by 1 every turn
    (to a maximum of 5.)" -- applied every turn to whoever currently
    holds the Fool of Battles title, if anyone. Same shape as `apply_
    cravenest_temperament_escalation()` immediately above.
    """

    holder = resolve_office_holder(state, Office.BATTLE_FOOL)
    if holder is None:
        return
    leader = state.leaders.get(holder.leader_id)
    if leader is None or leader.skills is None:
        return
    skill, aptitude = leader.skills.pair_for_ability(Ability.TACTICAL)
    leader.skills.set_pair_for_ability(Ability.TACTICAL, skill, min(5, aptitude + 1))
