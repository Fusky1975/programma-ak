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

**Still not attempted here, the same documented gap `turn/merit_points.py`
already names**: Chancellor's three discovery-attribution Merit Point
terms (`features_discovered_first`/`discoveries_found_first`/
`discoveries_via_espionage`) always read 0 from a fresh `MeritTally`
until some future phase wires real "who found this first" tracking --
this module resolves Chancellor using whatever `MeritTally` state a
caller has already populated (possibly all zeros), the same as every
other office. Likewise Marshal/Admiral/Defender/Priest's own tally
counters resolve from whatever a caller has populated; no battle/
encounter/cast call site increments them automatically yet.

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

- **These titles don't grant Victory Points** (see `turn/
  race_titles.py`'s own module docstring) -- `models/office.py
  OFFICE_VALUE` already reflects this correctly (real, non-zero
  Phase-81-sourced values for all 11, describing a different in-game
  effect than the 8 majors' own Victory Point share), so nothing
  changes here; this module resolves *who holds the title*, not what
  it's worth.
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
Thieves before them, none of these 8 grant Victory Points (`models/
office.py OFFICE_VALUE` already reflects this, Phase 81), and none of
the 6 alignment-King titles has a turn gate stated in the source --
unlike the 11 race titles, no office-level cutoff is applied here.
Each formula function already returns 0/None
for an ineligible leader on its own (King-only, alignment-gated where
stated), so this generic Rank-contest loop needs no additional
special-casing for any of the 8, the same "eligibility lives in the
formula, not the loop" shape Phase 277 established.

**Phase 379: 18 more leader-scoped royal titles join** (4 magic-school,
6 terrain-King, Battle Fool, Curator, Teacher, Assassin, Duellist,
Wingman, Cravenest, Bravest) -- one `if` branch each in `_leader_merit_
points()`, same shape as Phase 368's 8. None of the 18 grant Victory
Points and none is exempted from the death penalty (see `turn/merit_
points.py`'s own Phase 379 addendum, which also explains why the
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
new data needed. **No "current title holder" stickiness modeled** here
either, matching this module's own pre-existing tie-break choice for
every leader-scoped office (see `merit_point_tiebreak_key()`'s own
docstring) -- the general rule's own "prefer the current holder" tier
was never implemented for any of the other 47 offices, so adding it
only for these 3 would be new, undocumented behavior, not consistency.
"""

from __future__ import annotations

from dataclasses import dataclass

from ak_engine.models.army_type import OVERFLIGHT_AIR, ARMY_TABLE, ArmyType
from ak_engine.models.enums import Ability
from ak_engine.models.game_state import ArmyState, GameState, LeaderState
from ak_engine.models.office import OFFICE_MIN_POINTS, Office
from ak_engine.models.race import Race
from ak_engine.turn.combat import Quality
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


def _leader_merit_points(office: Office, state: GameState, leader: LeaderState) -> int | float:
    if office is Office.CHANCELLOR:
        return chancellor_merit_points(state, leader)
    if office is Office.TREASURER:
        return treasurer_merit_points(state, leader.kingdom_id) if leader.kingdom_id is not None else 0
    if office is Office.MARSHAL:
        return marshal_merit_points(leader)
    if office is Office.ADMIRAL:
        return admiral_merit_points(state, leader)
    if office is Office.DEFENDER:
        return defender_merit_points(leader)
    if office is Office.PRIEST:
        return priest_merit_points(state, leader)
    if office is Office.MAGE:
        return mage_merit_points(state, leader)
    if office is Office.EVIL_KING:
        return evilking_merit_points(state, leader)
    if office is Office.THIEF_PRINCE:
        return thiefprince_merit_points(state, leader)
    if office is Office.DIVINE_KING:
        return divinearchangel_merit_points(state, leader)
    if office is Office.GOOD_KING:
        return goodking_merit_points(state, leader)
    if office is Office.DRUID_KING:
        return druidking_merit_points(state, leader)
    if office is Office.NEUTRAL_KING:
        return neutralking_merit_points(state, leader)
    if office is Office.PAGAN_KING:
        return paganking_merit_points(state, leader)
    if office is Office.UNDEAD_KING:
        return undeadking_merit_points(state, leader)
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


def _king_leader_id(state: GameState, kingdom_id: int) -> int | None:
    for leader in state.leaders.values():
        if leader.kingdom_id == kingdom_id and leader.is_king:
            return leader.leader_id
    return None


def resolve_office_holder(state: GameState, office: Office) -> OfficeHolder | None:
    """The leader who currently holds `office`, and their own Merit
    Points -- or `None` if nobody qualifies yet. See module docstring
    for Emperor's own special-cased resolution and the Rank-contest
    rules governing the other 7.
    """

    if office is Office.EMPEROR:
        if state.emperor_kingdom_id is None:
            return None
        leader_id = _king_leader_id(state, state.emperor_kingdom_id)
        if leader_id is None:
            return None
        return OfficeHolder(leader_id, emperor_merit_points(state, state.emperor_kingdom_id))

    if office not in RANKED_OFFICES:
        raise ValueError(f"{office} is not one of the 47 real Imperial Offices this project models")

    if office in _OFFICE_RACE:
        turn_gate = RACE_TITLE_TURN_GATE[_OFFICE_RACE[office]]
        if state.turn_number < turn_gate:
            return None

    min_points = OFFICE_MIN_POINTS[office]
    best: OfficeHolder | None = None
    best_tiebreak: tuple[int, int, int] | None = None

    for leader_id, leader in state.leaders.items():
        points = _leader_merit_points(office, state, leader)
        if points < min_points:
            continue
        tiebreak = merit_point_tiebreak_key(state, leader)
        if best is None or points > best.merit_points or (points == best.merit_points and tiebreak > best_tiebreak):
            best = OfficeHolder(leader_id, points)
            best_tiebreak = tiebreak

    return best


def resolve_all_office_holders(state: GameState) -> dict[Office, OfficeHolder | None]:
    """All 47 real Imperial Offices at once, each resolved via
    `resolve_office_holder()`.
    """

    return {office: resolve_office_holder(state, office) for office in ALL_OFFICES}


# The 3 army-scoped Royal Titles (Phase 394) -- see module docstring's own
# Phase 394 addendum. Kept out of RANKED_OFFICES/ALL_OFFICES: every
# existing consumer of those (resolve_office_holder(), resolve_all_office_
# holders(), describe_imperial_office_report()) assumes a leader_id.
ARMY_RANKED_OFFICES: tuple[Office, ...] = (Office.AIR_FORCE, Office.PRAETOR, Office.FLAGSHIP)

# Flagship's own "type Mermen, Whale League or Fleet" eligibility gate.
_FLAGSHIP_ARMY_TYPES = frozenset({ArmyType.MERMEN, ArmyType.WHALES, ArmyType.FLEET})


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
        return army.army_type not in OVERFLIGHT_AIR
    if office is Office.FLAGSHIP:
        return army.army_type in _FLAGSHIP_ARMY_TYPES
    raise ValueError(f"{office} is not one of the 3 army-scoped Royal Titles")


def _army_office_tiebreak_key(state: GameState, army: ArmyState) -> tuple[int, int, int]:
    """Same shape as `merit_point_tiebreak_key()` (treasury, tax base, lower
    id wins) against the army's own owning Kingdom rather than a leader's.
    """

    kingdom = state.kingdoms[army.kingdom_id]
    return (kingdom.treasury, compute_tax_base(state, army.kingdom_id), -army.army_id)


def resolve_army_office_holder(state: GameState, office: Office) -> ArmyOfficeHolder | None:
    """The army that currently holds one of the 3 army-scoped Royal
    Titles (Airforce/Praetor/Flagship), and its own "Army_Str" score --
    or `None` if no army qualifies yet. See module docstring's own Phase
    394 addendum.

    Local import of `turn/army_quality.py` (not a module-level one):
    that module imports `turn/battle_orchestrator.py` for `druidic_
    shortfall_for()`, which itself imports this module for `resolve_
    office_holder()` (Phase 390's title-fanaticism check) -- a
    module-level import here would close that into a real circular
    import. Deferring to call time breaks the cycle without changing
    what either module actually does.
    """

    from ak_engine.turn.army_quality import army_peacetime_strength, compute_army_modified_quality

    if office not in ARMY_RANKED_OFFICES:
        raise ValueError(f"{office} is not one of the 3 army-scoped Royal Titles this project models")

    ability = Ability.NAVAL if office is Office.FLAGSHIP else Ability.TACTICAL
    min_points = OFFICE_MIN_POINTS[office]
    best: ArmyOfficeHolder | None = None
    best_tiebreak: tuple[int, int, int] | None = None

    for army_id, army in state.armies.items():
        if army.kingdom_id is None:
            continue
        modified_quality = compute_army_modified_quality(state, army)
        if not _army_office_eligible(office, army, modified_quality):
            continue
        score = army_peacetime_strength(state, army, ability)
        if office is Office.PRAETOR:
            score += ARMY_TABLE[army.army_type].speed
        if score < min_points:
            continue
        tiebreak = _army_office_tiebreak_key(state, army)
        if best is None or score > best.merit_points or (score == best.merit_points and tiebreak > best_tiebreak):
            best = ArmyOfficeHolder(army_id, score)
            best_tiebreak = tiebreak

    return best


def resolve_all_army_office_holders(state: GameState) -> dict[Office, ArmyOfficeHolder | None]:
    """All 3 army-scoped Royal Titles at once, each resolved via
    `resolve_army_office_holder()`.
    """

    return {office: resolve_army_office_holder(state, office) for office in ARMY_RANKED_OFFICES}
