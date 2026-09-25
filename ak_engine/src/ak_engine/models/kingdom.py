"""Top-level parsed representation of a player move-submission (.K1) file."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import PurePath

from ak_engine.models.enums import Ability
from ak_engine.models.leader import Leader


VOTE_TURN_SENTINEL = 31000
"""Pascal ``Vote_Turn`` constant (``AKGEN_reverse_engineering_report
(2).md`` SS12.1, ``AKE.EXE`` offset ``0x16823-0x169A1``) -- the special
`KingdomMoveHeader.kprevgold` value meaning "a vote is being held this
turn" for this Kingdom, as opposed to holding an election-request toggle.
See `KingdomMoveHeader.is_vote_turn`.
"""


@dataclass(slots=True)
class KingdomMoveHeader:
    """The Kingdom-header line (``sex interp_vers allreq brreq kacct kpmode
    kprevgold ksendmeth``), decoded against the real Pascal source
    (Phase 464).

    **The leading token is not a literal ``"M"`` format marker** -- earlier
    phases assumed this (the parser required it literally) because every
    available sample happens to be a male King. It is ``sex[kng]``, a
    per-King ``Char`` field (``HostAK/TP/DEF2.PAS`` ``Write_Moves`` line
    ~274: ``WRITELN(miscfile,sex[kng],' ',interp_vers,' ',allreq[kng],'
    ',brreq[kng],' ',kacct[kng],' ',kpmode[kng],' ',kprevgold[kng],'
    ',ksendmeth[kng])``). ``Read_Moves`` (line ~849) reads the same line
    back in the identical order (``READLN(miscfile,sex[kng],intvers,
    allreq[kng],brreq[kng],tka,tpm,kprevgold[kng],tks)``), confirming both
    the field order and the field count (8, not 7) two ways. ``raw_fields``
    holds the 7 *integer* fields after ``sex`` -- see the named properties
    below for what each one is.
    """

    raw_fields: list[int]
    sex: str = "M"

    @property
    def kingdom_number(self) -> int:
        """**Corrected (Phase 464): this is not a per-Kingdom identifier.**

        It is literally ``raw_fields[0]`` -- the exact same slot as
        `interp_vers` below. Proven by `Read_Moves`'s own read line: of
        the 8 variables read (``sex[kng],intvers,allreq[kng],brreq[kng],
        tka,tpm,kprevgold[kng],tks``), `intvers` is the *only* one without
        a ``[kng]`` index -- every other field is a per-Kingdom array
        access, `intvers` is a single global. It read as a stable ``27``
        across all 10 sample turns of this project's one available
        Kingdom, which is exactly what made it look like a Kingdom id
        before this correction (a global interpreter-version constant is
        just as "stable turn-to-turn" as a real per-Kingdom id would be,
        for a *single* Kingdom's own files -- the two are indistinguishable
        without a second Kingdom's sample to compare against, which this
        project doesn't have).

        **Fixed (Phase 574): `orchestrator.py`/`turn/kingdom_bridge.py` no
        longer key off this property.** In a real multi-Kingdom game every
        Kingdom's own move file would report the *same* `interp_vers`
        value (it's a build-wide constant, not per-Kingdom data), so every
        Kingdom would collide onto the same `kingdom_id` if this were
        still used that way. See `Kingdom.kingdom_id` for the real
        per-Kingdom identifier, and its own docstring for the sourced
        replacement and the direct cross-file confirmation found this
        phase. This property itself is kept, unchanged, purely as the
        decoded `interp_vers`/`raw_fields[0]` accessor -- not repurposed.
        """
        return self.raw_fields[0]

    @property
    def interp_vers(self) -> int:
        """Global interpreter-version constant -- ``raw_fields[0]``. See
        `kingdom_number`'s docstring (Phase 464) for the sourced proof
        this is *not* per-Kingdom data.
        """
        return self.raw_fields[0]

    @property
    def allreq(self) -> int:
        """``allreq[kng]`` -- ``raw_fields[1]``. Not further decoded this
        phase (Phase 464 scope: field *positions* only); presumably an
        alliance-request value given the "alleanza di Re" concept this
        project's `turn/emperor_election.py _alliance_component` already
        models, but that reading is unconfirmed and not asserted as fact.
        """
        return self.raw_fields[1]

    @property
    def brreq(self) -> int:
        """``brreq[kng]`` -- ``raw_fields[2]``, presumably a break-treaty
        counterpart to `allreq`. Not further decoded this phase.
        """
        return self.raw_fields[2]

    @property
    def kacct(self) -> int:
        """``kacct[kng]`` -- ``raw_fields[3]``, an account-related field.
        Not further decoded this phase.
        """
        return self.raw_fields[3]

    @property
    def kpmode(self) -> int:
        """``kpmode[kng]`` -- ``raw_fields[4]``, a play-mode field.
        `Read_Moves`'s own ``{$IFDEF Moderator}`` branch checks
        ``ksendmeth[kng] = S_Disk`` and then switches on `kpmode[kng]` to
        pick a disk drive letter, suggesting a submission-channel mode;
        not further decoded this phase.
        """
        return self.raw_fields[4]

    @property
    def kprevgold(self) -> int:
        """The Emperor-election Vote-command field
        (``AKGEN_reverse_engineering_report (2).md`` SS12.2) --
        ``raw_fields[5]``. Despite the misleading Pascal name (a reused
        field -- "in questa fase non rappresenta oro, ma
        richiesta/candidato elettorale"), it holds either an
        election-request toggle or, when a vote is actively being held
        this turn (compare against `VOTE_TURN_SENTINEL`), the chosen
        candidate King's index (``0..nkings-1``). The counterpart
        "No_King" reset sentinel's own numeric value isn't confirmed
        anywhere in the available Pascal source (referenced but never
        assigned a literal value in any extracted file) -- this project's
        one sample Kingdom never issues a real Vote command, so its own
        `kprevgold` reads a constant ``15`` across all 10 sample turns,
        plausibly (not confirmed) that sentinel's own value.
        """
        return self.raw_fields[5]

    @property
    def ksendmeth(self) -> int:
        """``ksendmeth[kng]`` -- ``raw_fields[6]``, the move-submission
        method (`Read_Moves`'s own ``{$IFDEF Moderator}`` branch checks it
        against ``S_Disk``, so at least "disk vs. some other channel" is
        confirmed). Not further decoded this phase.
        """
        return self.raw_fields[6]

    def is_vote_turn(self) -> bool:
        """Whether `kprevgold` currently holds `VOTE_TURN_SENTINEL` --
        i.e. a vote is being held this turn and `kprevgold` is (or should
        be) a King-index candidate choice, rather than an
        election-request toggle. See `kprevgold`'s docstring and report
        SS12.1.
        """
        return self.kprevgold == VOTE_TURN_SENTINEL


@dataclass(slots=True)
class SkillTable:
    """Raw integers from the skill-values line.

    Every sampled ``AK3__T*.K1`` file has exactly 31 integers on this line:
    15 ``Ability`` pairs (30 values) plus one trailing value.

    **The pair's meaning is now resolved (Phase 21): ``(current_skill_level,
    current_aptitude_level)``, each 0-9** (``CTBOTH.PAS``: ``skillrange =
    0..9``). Confirmed three ways: (1) ``HostAK/TP/CTME.PAS``'s ``power``
    enum has independently-adjustable ``UpSkill``/``UpApt``/``DnSkill``/
    ``DnApt`` members, proving the engine tracks skill and aptitude as two
    separate per-ability quantities; (2) the King-creation formula
    (``RULES.AK`` ~[2.x]: a King's starting aptitude is "always 2 higher
    than his initial skill, to a maximum of 5", with race/alignment
    overrides -- e.g. an Undead King gets a Necromancy skill +1 bonus but
    *zero* starting White Magic aptitude); (3) independently verified
    against ``AK3__T1.K1``'s real skill line -- every one of the 15 pairs
    matches the formula exactly, including both override cases
    (``WHITE = (0, 0)``, ``NECROMANCY = (3, 5)``). Skill *can* exceed
    aptitude after enough practice/experience rises (rulebook [3.13]: the
    rise chance is merely halved per level beyond aptitude, not blocked) --
    confirmed in the same sample Kingdom's Necromancy pair climbing to
    ``(7, 6)`` by turn 8.

    The 31st (trailing) value's meaning is still unconfirmed -- constant
    per Kingdom across turns (never changes turn-to-turn despite several
    skill/aptitude pairs shifting), consistent with something fixed at
    character creation rather than a 16th ability slot.

    **The earlier "race ordinal, probably Orcish" guess is now disproven
    (2026-09-12), not just unverified.** A second real game's move files
    (`Desktop/PROGRAMMA AK/AK6__T1.K3`/`AK6__T2.K{3,7,12,16,17,22}`, cross-
    checked against that game's own `GW6` world save via `parse_gw_
    leaders()`) gave 6 more real Kingdoms to check against, and a re-check
    of the original AK3 sample's own real race (`GW3__T1`, previously
    never actually looked up -- only guessed from character-name flavor)
    found it is **Elven**, not Orcish. The 7 real (Kingdom, race,
    alignment, trailing-value) tuples now on hand:

    - Uga-Buga Makumb (AK3): Elven, Undead -> 3
    - Josh the gentle (AK6 K3): Dwarven, Evil -> 3
    - Piotr (AK6 K7): Elven, Neutral -> 2
    - Haggis Wen Yen (AK6 K12): Dwarven, Pagan -> 3
    - Dances (AK6 K16): Human, Neutral -> 2
    - Medard (AK6 K17): Dwarven, Good -> 3
    - Mercino (AK6 K22): Human, Druid -> 1

    No single-field hypothesis tried survives all 7: race alone fails
    (two Elven Kings give 3 and 2); alignment alone fails (three Dwarven
    Kings with three different alignments -- Evil/Pagan/Good -- all give
    3, and two Neutral Kings of different races both give 2, but a
    race-ordinal-plus-one reading of "race" would need Elven to map to 2,
    contradicting Uga-Buga Makumb's own 3); nor does raw skill-value sum,
    max skill, or count of non-zero skills (checked directly, no clean
    match). Genuinely still unconfirmed -- documented with real data
    instead of a guess so a future attempt doesn't have to re-derive this
    table from scratch, and doesn't retry the now-falsified race-ordinal
    reading.

    **Phase 806 addendum -- two more real avenues tried, both confirmed
    dead ends (2026-09-16), so a future attempt doesn't retry them.**
    (1) The `GW*`-format world save's own per-leader skill line (`parser/
    gw_world.py GWLeaderRecord.skills`) does NOT carry this 31st value at
    all -- it is exactly 30 tokens for a Hero, 60 (the same 30-value
    table written twice back-to-back) for a King, both fully accounted
    for as the real 15 `(skill, aptitude)` pairs (Phase 325, an original
    game-host document's own field legend). There is no hidden 31st slot
    to extract from `GW6`/`GW3__T1`'s own 22+10 real Kings via this
    route -- the K1 move-file's own 31-value line is a genuinely
    different, move-file-only shape with no GW-format equivalent. (2)
    `Desktop/PROGRAMMA AK/G6/Pre turno 1.rar`/`Pre turno 2.rar` were
    listed (not extracted, since nothing new was found) -- both contain
    only the same 7 real `AK6__T*.K*` move files already on hand at the
    Desktop root (`T1.K3`, `T2.K{3,7,12,16,17,22}`), no additional
    Kingdoms' own move files hiding inside. The 44 real `SE6__T{2,3}.K*`
    turn-report letters were also checked directly (not just assumed) --
    their own CHARACTERS section prints exactly the 15 visible skill/
    aptitude pairs and nothing else; the 31st value is never surfaced in
    real report prose at all, confirming it really is an invisible,
    K1-move-file-only field. Still genuinely blocked: would need either
    a K1 move file for one of G6's other 16 Kingdoms (never supplied) or
    a disassembly of the move-file writer covering this specific field.

    **Phase 907 addendum -- the first hypothesis that survives every
    real sample on hand (2026-09-25), from a third and fourth real
    game.** `Desktop/PROGRAMMA AK/AK7__T1.K2`/`AK7__T2.K2` (Solrac's
    Kingdom, `interp_vers=24` -- a genuinely different build than every
    other sample's `27`) and `AK900T1.K0`/its own real `GW900T1`/`GW900`
    world-save pair (Legolas's Kingdom) were supplied. The `AK7` pair
    has no matching world-save, so its own trailing value (``3`` on both
    turns -- confirming, again, "constant per Kingdom across turns") is
    real but still unusable: no independently-confirmed race/alignment
    to attach it to. `GW900T1`/`GW900` (via `parse_gw_leaders()`) *does*
    give Legolas's real identity -- **Elven, Druidic** -- and his own
    K1's trailing value is ``1``, exactly matching Mercino's own
    (Human, Druidic -> ``1``) from the original 7-tuple set. Two
    *different* races sharing the same alignment producing the *same*
    trailing value, for the first time, is the concrete new evidence
    here.

    The 8 real tuples now on hand, testing "the trailing value is a
    function of `Alignment` alone" (ignoring race and everything else):

    - Undead -> 3 (Uga-Buga Makumb)
    - Evil -> 3 (Josh the gentle)
    - Neutral -> 2 (Piotr)
    - Pagan -> 3 (Haggis Wen Yen)
    - Neutral -> 2 (Dances)
    - Good -> 3 (Medard)
    - Druidic -> 1 (Mercino)
    - Druidic -> 1 (Legolas)

    **Zero contradictions across all 8** -- the first single-field
    hypothesis to survive the full real dataset (every prior hypothesis
    tried, including a literal alignment-ordinal reading, was falsified
    by at least one sample). The apparent grouping is ``{Druidic} -> 1``,
    ``{Neutral} -> 2``, ``{Good, Pagan, Evil, Undead} -> 3`` -- not a
    literal ordinal computation (`ALIGNMENT_ORDINAL` gives Good=1,
    Druidic=2, Neutral=3, Pagan=4, Evil=5, Undead=7, which groups
    nothing this way), so this is an observed correlation, not yet a
    derived formula with a known mechanism.

    **User-confirmed (2026-09-25): no real Hero or King has ever had
    `Alignment.ANTI_HOLY`/`MECHANICAL`/`SPECIAL`** -- consistent with
    this project's own existing code, where all three are only ever
    assigned to monsters (`models/monster.py`) or used as ordinal
    reference points, never produced by `worldgen/hero_talent_
    generation.py roll_alignment()` (the ordinary 5-alignment roll:
    Good/Druidic/Neutral/Pagan/Evil) or by `turn/succession.py
    create_king()`'s own Divine/Undead special-casing. That narrows the
    real, reachable alignment space for this field to exactly 7 members
    (Divine, Good, Druidic, Neutral, Pagan, Evil, Undead) -- of which
    **6 are now tested and consistent; only `Alignment.DIVINE` has never
    appeared in any real sample.**

    **Still not promoted to a real decode function.** Three real risks
    remain, all addressable only with more data or a disassembly, not
    by reasoning further from what's on hand: (1) only 8 data points
    back a 3-way grouping -- a 9th sample from `Good`/`Pagan`/`Evil`/
    `Undead` breaking the shared `3` would falsify the grouping, not
    just narrow it; (2) `Alignment.DIVINE`, the one untested reachable
    member, could land on `1`, `2`, `3`, or a genuinely new 4th value;
    (3) no sourced mechanism explains *why* four distinct alignments
    would collapse to one value. A King of confirmed Divine alignment's
    own K1 (plus its world-save, to confirm the alignment independently)
    would settle point (2) outright; a disassembly of the move-file
    writer (see the still-blocked note above) would settle all three at
    once. Recorded here, with the real data, so neither the falsified
    ordinal reading nor a half-considered grouping has to be
    re-discovered from scratch.
    """

    raw_values: list[int]

    def pair_for_ability(self, ability: Ability) -> tuple[int, int]:
        """Return ``(skill_level, aptitude_level)`` for ``ability``, each 0-9."""

        i = ability.value * 2
        return (self.raw_values[i], self.raw_values[i + 1])

    def set_pair_for_ability(self, ability: Ability, skill: int, aptitude: int) -> None:
        """Write back a new ``(skill_level, aptitude_level)`` pair (Phase 44, Practice execution).

        Mutates ``raw_values`` in place -- the symmetric write counterpart
        to ``pair_for_ability``, added so ``turn/practice_execution.py``
        doesn't need to know this table's raw layout.
        """

        i = ability.value * 2
        self.raw_values[i] = skill
        self.raw_values[i + 1] = aptitude


@dataclass(slots=True)
class Kingdom:
    """Everything parsed out of one player move-submission file."""

    source_filename: str
    king_name: str
    king_title: str | None
    header: KingdomMoveHeader
    skills: SkillTable
    leaders: list[Leader] = field(default_factory=list)
    trailer_comments: str = ""

    @property
    def kingdom_id(self) -> int:
        """The real per-Kingdom identifier (Phase 574), replacing the
        confirmed-broken `KingdomMoveHeader.kingdom_number`.

        Parsed from this file's own name's trailing ``.K<N>`` suffix
        (``source_filename``, e.g. ``AK3__T1.K1`` -> ``1``) rather than
        its header content. `HostAK/TP/DEF2.PAS` `Write_Moves`/`Read_
        Moves` both build this exact filename via ``Get_FN('AK',
        gameturn, kng, fs)``, threading the real per-Kingdom `kng` loop
        variable through -- so the name *must* vary with `kng`, or two
        Kingdoms writing their own move files to the same host disk
        would overwrite each other, which the engine plainly never does.

        **Directly confirmed this phase**, not just inferred by analogy:
        this project's one real move-file sample, ``AK3__T1.K1``, and its
        own turn's report, ``SE3__T1.K1`` -- the *same* trailing ``.K1``
        suffix -- name the identical King ("Uga-Buga Makumb(u)") on their
        very first line, tying the suffix to one real, cross-checked
        Kingdom across both file series. This matches the already
        extensively-confirmed `SE3__T*.K<N>` report convention this
        project's ASCII-map/report work relies on throughout. `Get_FN`'s
        own body still isn't present anywhere in the extracted Pascal
        source (checked again this phase, in both `HostAK` and
        `HostAK-old`), so the exact byte-level construction algorithm
        remains unconfirmed -- but which *value* it embeds is no longer
        a guess.
        """
        suffix = PurePath(self.source_filename).suffix  # e.g. ".K1"
        return int(suffix[2:])
