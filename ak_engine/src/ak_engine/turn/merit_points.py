"""Imperial Office Merit Point formulas -- rulebook page 51's "TABELLA
DELLE CARICHE IMPERIALI" (user-supplied PDF, studied directly; quoted
below in the relevant sections), Phase 227.

**This closes the formula half of a gap Phase 137 called a "confirmed,
permanent dead end."** That phase found `REPORTS.PAS`'s real `Ofc_Pts`/
`Rank` scoring formulas but couldn't build them: nearly every office's
own points formula reads a global (`lgenp`/`ladmp`/`lmhpp`/`lwmsp`/`oops`/
`tipts`/`seatax`/`alltax`/`lfdisc`/`ldiscp`) declared nowhere in the
surviving 14 `.PAS` files -- their true declarations live in a missing
compiled-only unit. **That conclusion still stands for the Pascal source
itself** -- those globals are still unrecoverable, and this module makes
no claim to reproduce them bit-for-bit. What changed is the source: the
user supplied the rulebook's own printed "TABELLA DELLE CARICHE
IMPERIALI" (page 51), a different, independently authoritative
description of the same 8 formulas in the game's own official terms
("Attribuzione dei Punti Merito" per office) -- not a Pascal
transcription, but a real, sourced, directly-quoted rule, the same
standing this project already gives every other rulebook excerpt the
user has supplied (the Alignment-reduction table, the Emperor election
thresholds).

**The 8 offices and their real 20%/10%x7 Victory Point quotas already
matched `models/office.py OFFICE_VALUE` exactly before this phase** --
independent cross-confirmation the two sources describe the same system.

## Emperor (20%)
"Ammontare della rendita di tasse alla fine del gioco" -- the kingdom's
tax revenue at game end. This is exactly `turn/tax_base.py
compute_tax_base()` (Phase 225), reused directly rather than
reimplemented.

## Gran Cancelliere / Chancellor (10%)
- +1 per level in Explorer, Spy, and Sage
- +2 per Special Place (Feature) discovered first
- +2 per Invention (Discovery) found first
- +1 per Invention obtained via espionage

**The skill-level term and the Feature half are live; the Invention half
still isn't.** `features_discovered_first` is live as of **Phase 256**:
`models/feature.py Feature.discovered_by_kingdom` (a per-kingdom dict,
Phase 75) already exists and is written by `turn/exploration.py
discover_features()` every time a kingdom first discovers a Special
Place; `turn/plan_dispatch.py`'s own `ActionCode.EXPLORE` branch now
checks, for each newly-discovered feature, whether that kingdom's own
entry is still the *only* one in the dict (nobody else got there
first) and credits the acting leader's own `MeritTally.
features_discovered_first` when so. `discoveries_found_first`/
`discoveries_via_espionage` (Inventions) remain unwired -- unlike
Features, this project has **no acquisition mechanic for a `Discovery`
at all**: nothing anywhere ever grants a `KingdomState` a `Discovery`
in the first place (confirmed by an exhaustive search, not merely
unwired), so there is no event to attribute "found first" or "via
espionage" to yet. That's a materially larger, still-unscoped gap
(inventing the acquisition mechanic itself, not just attributing an
existing one) than Phase 256's own Feature-side fix.

## Tesoriere Imperiale / Treasurer (10%)
"Il tesoro più sostanzioso alla fine del gioco" -- the kingdom's own
`KingdomState.treasury`. Fully live; Phase 137's own speculation
("`Treasurer`'s `lgold[ldran]` is plausibly just that King's own
treasury") is now confirmed by the rulebook's own text, not a guess.

## Gran Maresciallo / Marshal (10%)
"Per ogni battaglia terrestre comandata: se vinta, per ciascuna unità
dell'esercito nemico +1; se persa, per ciascuna unità nel proprio
esercito -1." `MeritTally.land_battles_won_enemy_units`/
`land_battles_lost_own_units` are **live as of Phase 254**:
`turn/battle_orchestrator.py _record_battle_merit()` credits/debits
each side's own Supreme Commander (`None` for an unled side -- not a
"battaglia comandata" for anyone) right after `fight_battle()` resolves
`battle_result.winner`, counting the *entire* opposing army fielded
(one `ArmyState` = one "unità", the project's own existing 1:1
army<->`BattleUnit` correspondence), not just casualties. A `"tie"`
records nothing for either side -- the rulebook's own "vinta"/"persa"
wording doesn't address one.

## Grande Ammiraglio / Admiral (10%)
Same won/lost-unit formula as Marshal but for naval battles (also live
as of Phase 254, same `_record_battle_merit()` call, keyed off
`terrain is Terrain.SEA`), **plus**: "Per ogni livello di abilità
Navale +1" (live -- `LeaderState.skills`) and "Per ogni provincia di
mare con rendita di 2+ gold +1" -- footnote 1 confirms this last term
is a flat per-kingdom count applied to *every* character of that
kingdom, not per-leader-owned territory, so `admiral_merit_points()`
counts qualifying sea provinces once per `leader.kingdom_id` and adds
the same figure for every leader who shares that kingdom.

## Gran Difensore / Defender (10%)
"Per ciascun mostro ucciso: totale Punti Ferita del mostro (metà dei
punti se neutralizzato con trattative)." Footnote 2: no points for a
Fulfilled quest agreement; a monster persuaded to stop raiding (rather
than killed) via negotiation/damage scores half. `MeritTally.
monster_hp_defeated`/`monster_hp_neutralized` store the raw, unhalved HP
sums the caller observed; `defender_merit_points()` applies the halving
(floor division) so the tally itself stays a faithful raw record.
`monster_hp_defeated` is **live as of Phase 255**: `turn/
search_execution.py execute_search()`'s own `_outcome_from()` credits
the guardian's starting hit points whenever the leader wins the
encounter (Melee, Fire Arrow, or a Cast-tactic instant kill). The
negotiated half, `monster_hp_neutralized`, still has no writer -- it
needs the Fulfill/Talk-Say mechanic `turn/search_execution.py`'s own
docstring already flags as unwired.

## Gran Sacerdote / Priest (10%)
"Per ogni incantesimo Resurrection o Bless riuscito +1" (either spell,
same +1 -- the table doesn't distinguish) plus "+2 per ciascun livello
nei Talenti Druidico e Magia Bianca." Both terms are live as of Phase
251: `turn/cast_execution.py`'s own `_execute_resurrection`/
`_execute_bless` each increment `MeritTally.resurrection_bless_casts`
by 1 on success -- the project's first real `MeritTally` writer,
closing the gap this dataclass's own Phase 227 docstring flagged
("no action in this project is wired to increment yet").

## Arcimago di Palazzo / Mage (10%)
"Per ogni livello in tutti i Talenti Magici +1" (the 5 spell-casting
Abilities: White, Necromancy, Elemental, Psychic, Illusion -- Druidic is
its own separate Talent, already claimed by Priest above, not counted
here) plus "+1 per ciascun oggetto magico in grado di lanciare
incantesimi posseduto" -- `models/treasure.py TreasureCategory.
SPELL_WAND` is exactly "a Use_MI-castable wand" (the project's own
existing, sourced category for "operates by casting a spell"), not
`SKILL_BOOK` (a one-shot item consumed on read, not an ongoing
possession the rulebook's "posseduto" implies). Both terms are fully
live: skills via `LeaderState.skills`, wands via `GameState.
items_held_by()`.

## The "10 restanti Punti Merito" legendary-item bonus (not an office)
The table's own closing paragraph: 10 named artifacts (Excalibur, Arco
del Re degli Elfi, Ascia dei Signori dei Nani, Scimitarra del Dominio
degli Orchi, Corona del Comando dei Draghi, Penna della Grande Aquila,
Corno di Nettuno, Spada Santa, Spada Invisibile, Spada dell'Ombra) each
grant a flat share of a separate 10%-of-total Victory Point pool simply
for being possessed -- "questi punteggi non sono modificati
dall'eventuale differenza di Allineamento con l'Imperatore" (unlike
every one of the 8 offices' own points, per 10.2's own paragraph). This
is structurally different from a Merit Point/Rank contest (no
"highest wins" comparison at all), so it's modeled as its own function,
not folded into any of the 8 office formulas above. **A perfect 1:1
cross-check against this project's own pre-existing `models/treasure.py
TREASURE_NAME`**: all 10 named items already exist there under those
exact English names (`LEADERSHIP_HUMAN` = "Excalibur", `WEAPON_1` =
"Holy Sword", `MONSTER_AID_WHALE` = "Horn of Neptune", ...) --
independent confirmation the rulebook table and the already-transcribed
Pascal `treasure` enum describe the same 10 artifacts.

## Tie-break (rulebook footnote 3)
"Se due personaggi hanno pari punteggio per una Carica Imperiale, il
primo posto viene assegnato in base prima all'ammontare del tesoro e poi
alla rendita in tasse." Both tie-break figures are Kingdom-scoped (a
leader has no personal treasury or tax base of their own), so
`merit_point_tiebreak_key()` reads `leader.kingdom_id`'s own
`KingdomState.treasury` and `compute_tax_base()`. An independent Hero
(`kingdom_id is None`) has neither -- the rulebook's own "anche un Eroe
può aggiudicarsi una carica" confirms a Hero can win an office outright,
but says nothing about how *that* Hero would be ranked against a tied
rival, so this falls back to `(0, 0)`, a documented gap rather than a
guess.
"""

from __future__ import annotations

from ak_engine.models.enums import Ability
from ak_engine.models.game_state import GameState, LeaderState
from ak_engine.models.map import Terrain
from ak_engine.models.treasure import Treasure, TreasureCategory, TREASURE_CATEGORY
from ak_engine.turn.tax_base import compute_tax_base

_CHANCELLOR_SKILL_ABILITIES: tuple[Ability, ...] = (Ability.EXPLORER, Ability.SPY, Ability.SAGE)
_PRIEST_SKILL_ABILITIES: tuple[Ability, ...] = (Ability.DRUID, Ability.WHITE)
_MAGE_SKILL_ABILITIES: tuple[Ability, ...] = (
    Ability.WHITE,
    Ability.NECROMANCY,
    Ability.ELEMENTAL,
    Ability.PSYCHIC,
    Ability.ILLUSION,
)

# Rulebook page 51's own closing paragraph -- see module docstring for the
# 1:1 cross-check against models/treasure.py TREASURE_NAME.
LEGENDARY_ITEM_BONUS_TREASURES: frozenset[Treasure] = frozenset(
    {
        Treasure.LEADERSHIP_HUMAN,  # Excalibur
        Treasure.LEADERSHIP_ELVEN,  # Bow of the Elven Kings
        Treasure.LEADERSHIP_DWARVEN,  # Axe of the Dwarven Lords
        Treasure.LEADERSHIP_ORCISH,  # Scimitar of Orc Mastery
        Treasure.MONSTER_AID_DRAGON,  # Crown of Dragon Command
        Treasure.MONSTER_AID_EAGLE,  # Feather of the Great Eagle
        Treasure.MONSTER_AID_WHALE,  # Horn of Neptune
        Treasure.WEAPON_1,  # Holy Sword
        Treasure.WEAPON_2,  # Shadow Sword
        Treasure.WEAPON_5,  # Invisible Sword
    }
)


def _skill_level_sum(leader: LeaderState, abilities: tuple[Ability, ...]) -> int:
    if leader.skills is None:
        return 0
    return sum(leader.skills.pair_for_ability(ability)[0] for ability in abilities)


def emperor_merit_points(state: GameState, kingdom_id: int) -> int:
    """"Ammontare della rendita di tasse alla fine del gioco" -- reuses
    Phase 225's `compute_tax_base()` directly.
    """

    return compute_tax_base(state, kingdom_id)


def chancellor_merit_points(leader: LeaderState) -> int:
    """See module docstring: only the Explorer/Spy/Sage skill term is
    live; the three discovery-attribution terms read `MeritTally`
    counters no action in this project increments yet.
    """

    tally = leader.merit_tally
    return (
        _skill_level_sum(leader, _CHANCELLOR_SKILL_ABILITIES)
        + 2 * tally.features_discovered_first
        + 2 * tally.discoveries_found_first
        + tally.discoveries_via_espionage
    )


def treasurer_merit_points(state: GameState, kingdom_id: int) -> int:
    """"Il tesoro più sostanzioso alla fine del gioco" -- `KingdomState.treasury`."""

    return state.kingdoms[kingdom_id].treasury


def marshal_merit_points(leader: LeaderState) -> int:
    """+1 per enemy unit in a won land battle, -1 per own unit in a lost
    one -- reads `MeritTally`'s raw won/lost counters (see module
    docstring for why no consumer populates them yet).
    """

    tally = leader.merit_tally
    return tally.land_battles_won_enemy_units - tally.land_battles_lost_own_units


def _rich_sea_province_count(state: GameState, kingdom_id: int | None) -> int:
    if kingdom_id is None:
        return 0
    return sum(
        1
        for province in state.provinces.values()
        if province.owner_kingdom_id == kingdom_id
        and province.effective_terrain() is Terrain.SEA
        and province.tax is not None
        and province.tax >= 2
    )


def admiral_merit_points(state: GameState, leader: LeaderState) -> int:
    """Same won/lost-unit formula as Marshal (naval battles), plus a live
    Naval-skill term and a live "rich sea province" per-kingdom bonus --
    see module docstring for footnote 1's "applies to every character of
    the Kingdom" reading.
    """

    tally = leader.merit_tally
    naval_skill = _skill_level_sum(leader, (Ability.NAVAL,))
    rich_sea_provinces = _rich_sea_province_count(state, leader.kingdom_id)
    return tally.naval_battles_won_enemy_units - tally.naval_battles_lost_own_units + naval_skill + rich_sea_provinces


def defender_merit_points(leader: LeaderState) -> int:
    """Full monster HP for a kill, half (floored) for a negotiated
    neutralization -- see module docstring for why `MeritTally` stores
    the raw, unhalved HP sums.
    """

    tally = leader.merit_tally
    return tally.monster_hp_defeated + tally.monster_hp_neutralized // 2


def priest_merit_points(leader: LeaderState) -> int:
    """+1 per successful Resurrection/Bless cast, +2 per level in Druidic
    and White Magic (live).
    """

    tally = leader.merit_tally
    return tally.resurrection_bless_casts + 2 * _skill_level_sum(leader, _PRIEST_SKILL_ABILITIES)


def mage_merit_points(state: GameState, leader: LeaderState) -> int:
    """+1 per level across the 5 spell-casting Abilities, +1 per owned
    Spell-Wand-category item -- both terms are fully live.
    """

    skill_sum = _skill_level_sum(leader, _MAGE_SKILL_ABILITIES)
    wand_count = sum(
        1
        for item in state.items_held_by(leader.leader_id)
        if TREASURE_CATEGORY.get(item.treasure) is TreasureCategory.SPELL_WAND
    )
    return skill_sum + wand_count


def legendary_item_victory_point_bonus_count(state: GameState, leader_id: int) -> int:
    """How many of the 10 rulebook-named legendary items (see module
    docstring) this leader currently holds -- **not** an Office Merit
    Point tally; the rulebook explicitly separates this flat, un-ranked
    Victory Point share from the 8-office Rank contest above.
    """

    return sum(1 for item in state.items_held_by(leader_id) if item.treasure in LEGENDARY_ITEM_BONUS_TREASURES)


def merit_point_tiebreak_key(state: GameState, leader: LeaderState) -> tuple[int, int]:
    """Rulebook footnote 3's own tie-break, as a sort key (higher wins):
    treasury first, then tax base -- both read from `leader.kingdom_id`'s
    own `KingdomState`. `(0, 0)` for a kingdom-less independent Hero, a
    documented gap (see module docstring), not a guess.
    """

    if leader.kingdom_id is None:
        return (0, 0)
    kingdom = state.kingdoms[leader.kingdom_id]
    return (kingdom.treasury, compute_tax_base(state, leader.kingdom_id))
