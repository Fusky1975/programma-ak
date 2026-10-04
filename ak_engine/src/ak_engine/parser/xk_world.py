"""Phase 992: the real ``XK`` per-Kingdom "known world" file -- the
binary export a player's own separate Windows support program reads to
show that Kingdom's own map and prepare their next turn's moves.

**Supersedes Phases 988-991.** Those phases built this module from pure
known-plaintext cryptanalysis (searching for real GW/letter facts inside
the raw bytes, with no Pascal source or disassembly for this format in
the project) and got the header, the per-leader name table, and most of
the province/Feature/treasure records right -- but, lacking a ground
truth for byte *order*, mis-grouped a few adjacent fields (e.g. treating
a Feature record's real 2-byte ``DS:962A`` field as "two always-zero
unknown bytes"), and got the Army record's own field order wrong
entirely (swapping what are really separate ``race``/``type`` bytes for
a guessed, partly-duplicated ``quality``/``state`` layout that happened
to fit the 3 non-Mercenary samples available at the time but broke on
the 4th, Mercenary-state one).

**The user then supplied a real disassembly of ``AK.EXE``'s own XK
*writer* routine** (raw range ``0x1DCBF-0x1FE8A``, calling the real
``BlockWrite``/``3EE5:1C4B``), cross-checked against partial real Pascal
source (``CTBOTH.PAS`` excerpts: the ``ability``/``race``/``outlook``
enum orders, the ``TR_*`` extension-tag constants) and a 12-sample
corpus (this project's own 4 fixtures plus 8 more: the same campaign's
Kingdom 2, and Turns 3-4) -- a far stronger evidentiary basis than
cryptanalysis alone, since it reads the real field order and sizes
directly from the code that writes them rather than inferring them from
outcomes. This phase ports that work: every field and record shape
below is sourced to a specific disassembly address or Pascal excerpt,
not re-derived. Genuinely unconfirmed semantics (most global words, both
~256-byte flag areas, both 192-byte pointer blocks, the Feature record's
own ``DS:962A`` word, Army ``quality_or_mask``, every state/status bit)
are kept as raw ints under their own ``DS_xxxx`` address rather than
guessed at -- the same discipline ``parser/gw_world.py`` already applies
to its own undeciphered fields.

**What XK contains.** A snapshot of the world as known to one specific
Kingdom (the file's own ``kingdom_id``, 0-indexed -- the filename's own
``Kx`` suffix matches it in every sample, but isn't itself authoritative;
this module reads the real header field): names, full or partial
character cards, known provinces, Features, treasures, armies,
discoveries, player administrative data, a province-by-province
recruitable-type map, and race/alignment/ability lookups the real client
needs to render them -- not the GW world save, not an AK orders file.

**Confirmed exact file grammar**, in order:

1. **Header** (5 bytes): ``format_revision`` (``u16``, always ``30`` in
   every sample -- this strict decoder, matching the real disassembly's
   own validated branch, only supports this revision), 1 reserved byte
   (always ``0``), ``kingdom_id`` (``u16``, though every real value seen
   fits a single byte).
2. **Globals** (774 bytes): a verbatim copy of ``DS:C2F6..C5FB`` --
   131 words (262 bytes, ``DS:C2F6..C3FA``), then two 256-byte areas
   (``DS:C3FC``, ``DS:C4FC``). 16 of the 131 words are confirmed-named
   (``XK_GLOBAL_FIELD_NAMES`` below, e.g. ``gameturn``, ``king_count``);
   the rest are raw, keyed ``DS_xxxx`` by address. Both 256-byte areas
   are kept as raw bytes -- real per-bit flag meanings are undeciphered.
3. **Leader names** (always starting at the confirmed offset ``0x30B``,
   779 -- unchanged from Phase 988): ``leader_capacity`` (a named global,
   ``100`` in every real sample) Pascal ShortStrings, one per leader id.
4. **Full character cards**: 74 bytes each (``XKLeaderCard`` below),
   0xFE-terminated -- confirmed (Phase 1004) to hold *exactly* this
   Kingdom's own leaders, a full biconditional with real GW ground
   truth (57 of 57 of this Kingdom's own leaders get a full card here,
   zero get a partial card or neither).
5. **Partial character cards**: ``id, x, y`` (3 bytes each), 0xFE-terminated
   -- confirmed (Phase 1004) to never hold one of this Kingdom's own
   leaders (0 of 68 real partial cards belong to the viewing Kingdom).
6. **Leader races**, 7. **leader states**: ``leader_capacity + 1`` raw
   bytes each -- the ``+1`` (not just ``leader_capacity``) is real and
   confirmed in the disassembly; missing it misaligns everything after.
8. ``DS:89C7`` (12 bytes): each King's own real sex, decoded (Phase
   1007) as ``king_sex``, king-id ordered. 9. a word at
   ``DS:8AE7 + 2*kingdom_id``, decoded (Phase 1008) as this King's own
   real ``treasury``. 10-11. two 192-byte **per-King title tables** from
   far pointers ``DS:8B29``/``DS:8B2D`` -- see the Phase 993 addendum
   below.
12. **Known provinces** (``XKProvinceRecord`` below), 0xFE-terminated.
13. **Features** (``XKFeatureRecord``, 8 bytes each), 0xFE-terminated.
14. **Treasures** (``XKTreasureRecord``, variable length), 0xFE-terminated.
15. **Armies** (``XKArmyRecord``, 4 or 8 bytes): index-implicit, looping
    the real ``army_count`` global but **skipping index 255** -- a real
    disassembly-confirmed quirk (``army_count=260`` yields 259 records).
16. **Discoveries**: ``id`` + a real ``0xFE01`` legacy word (not a plain
    ``0x0001``/``0x0000`` boolean -- the writer copies 2 bytes from a
    local variable whose own neighbor byte happens to be ``0xFE``),
    0xFE-terminated.
17. **Player tail** (28 bytes): mostly raw (``XK_PLAYER_TAIL_FIELDS_
    BEFORE_RELATIONS``/``_AFTER_RELATIONS``/``_TRAILING`` below), except
    the 12-byte ``relations_D1D4`` span, fully decoded (Phase 1005) as
    ``diplomatic_relations``, and 2 of the remaining words, decoded
    (Phase 1006) as ``account_number``/``met_kings_bitmask_low``.
18. ``TR_End`` (``16001`` as a ``u16``) -- **not EOF yet**.
19. **Recruitment map**: one ``(slot_1, slot_2)`` raw-byte pair per
    board cell, ``(right-left+1) * (bottom-top+1)`` cells, outer loop
    over ``x`` then inner over ``y``. ``0x0F`` (``NoArmy``/placeholder
    in ``MOD_PAT_ORDINAL_TO_ARMY_TYPE``) marks a cell this Kingdom
    doesn't actually know the recruit types for -- not proof the host
    province has none.
20. **Typed extensions**, each its own ``u16`` tag: ``TR_LLs`` (16004,
    id/lliege pairs, ``0xFF``-id-terminated -- a different sentinel than
    everywhere else in this format), ``TR_SA`` (16005, 90 raw bytes, 15
    abilities x 6 levels), ``TR_T2`` (16006, 450 raw bytes, a fixed
    30x15 secondary-terrain capacity -- **not** the played board's own
    size), ``TR_HK`` (16007, syntactically supported, no real sample
    exercises it).
21. **Final** ``TR_End`` (``16001``) -- true EOF; any trailing byte is
    rejected.

**Confirmed real enum/ordinal reuse** (no new lookup tables needed):
``Terrain``/``Race`` ordinals match a province record's raw
``terrain``/``race`` bytes directly (already established, Phase 988).
``parser/gw_world.py``'s own ``MOD_PAT_ORDINAL_TO_ARMY_TYPE`` is the real
ordinal table for a province's ``recruit_type_1``/``recruit_type_2`` AND
for an Army record's own ``army_type`` AND for a recruitment-map cell's
own slot -- one real table, three real call sites (the ``CTBOTH.PAS``
army-type ordinal list this new material supplies matches it exactly
through every ordinal checked, 0-19). ``models/monster.py Monster``/
``MonsterEngagementState`` and ``models/feature.py FeatureType`` match a
Feature record's own raw bytes directly (Phase 991, unchanged).
``models/treasure.py Treasure`` matches a Treasure record's own raw
``type`` byte directly (Phase 991, unchanged). ``models/temper.py
Temper``'s own ``.value`` and ``models/alignment.py
ALIGNMENT_BY_ORDINAL`` (the real ``CTBOTH.PAS outlook`` order, already
in this project) match a full leader card's own raw ``temper``/
``alignment`` bytes directly -- newly confirmed this phase (e.g. King
Babba Sissoko, real ``Alignment.UNDEAD``/``Temper.BERSERK``, reads
``alignment=7``/``temper=3``, exactly ``ALIGNMENT_BY_ORDINAL[7]``/
``Temper.BERSERK.value``).

**Phase 993 -- the two 192-byte ``DS:8B29``/``DS:8B2D`` blocks, fully
decoded.** Each is a fixed array of 12 slots, 16 bytes each (a 1-byte
length then a 15-byte char buffer -- the same truncate-at-15 ShortString
shape Phase 990 first noticed on 2 stray strings before their own
container was known), indexed by king id (``king_count`` real entries,
0-9 in this corpus, plus 2 always-blank reserve slots never observed
populated). ``DS:8B29`` is each King's own ``title_prefix``; ``DS:8B2D``
is each King's own ``title_suffix`` -- **exactly** this project's own
already-existing, already-named ``parser/gw_world.py GWKingExtension.
title_prefix``/``title_suffix`` fields, confirmed by direct cross-check
against both real ``GW3__T1`` and ``GW3__T4`` for both of this
campaign's 2 Kings who ever have non-blank titles: King 0 (Babba
Sissoko) reads ``prefix="Lord"``, ``suffix="Master of the s"`` at Turn 1
and ``suffix="Master orango"`` at Turn 4 (short enough this time to show
untruncated) in both XK *and* GW; King 1 (Uga-Buga Makumb) reads
``prefix="Shaman"``, ``suffix="Lord of the stu"`` (Turn 1) /
``"Stuffy doll"`` (Turn 4) in both, identically. Confirmed identical
across different Kingdoms' own XK files too (every King's title is
public, not per-recipient-filtered) -- this closes Phase 990's own
"two still-unattributed title strings" gap completely, and the
"per-leader status data" that pointer wasn't actually about: these 2
blocks are per-*King*, not per-leader at all.

**Phase 994 -- the Army record's own ``status``/``detail_status``/
``quality_or_mask``, cross-checked at scale.** Confirmed (Phase 992)
that a given XK file's own ``army_index`` (the ``0..army_count-1`` loop
position, ``255`` skipped) lines up *exactly* with ``parser/gw_world.py
parse_gw_armies()``'s own same-order list for the same real world file
(re-inserting the skipped index: ``gw_index = army_index if army_index
< 255 else army_index - 1``) -- this lets every Army record in the
entire 12-file corpus be paired with its own real ``GWArmyRecord``
directly, not just the handful at one Home. Across all 3015 armies this
produced real pairs for: ``race``/``army_type`` matched their own real
``GWArmyRecord`` fields with **zero exceptions**. ``status`` and
``detail_status`` (when present) matched ``GWArmyRecord.state``'s own
real ``MonsterEngagementState`` ordinal **exactly, zero exceptions**
each of the 3 non-``DEAD`` values actually observed (``HIRED``,
``MERCENARY``, ``ZOMBOID``) -- the real enum this project's
``parser/gw_world.py`` already defines, no new table needed; both
fields are now decoded as ``MonsterEngagementState``, not raw ints.
``quality_or_mask`` is **not** a clean 1:1 ordinal: every nonzero value
(``1``-``4``) matched ``GWArmyRecord.quality.value`` exactly in every
one of 190 such cases, but raw ``0`` mapped to **5 different** real
``Quality`` values (``0`` through ``4``, 2825 cases) -- a real masking
sentinel, not "this army's quality is ``Quality.DEPLETED``" (``0``):
most real ``Quality.AVERAGE`` armies happen to be masked to ``0`` too.
Kept as a raw int for exactly this reason -- converting ``0`` to either
``None`` or ``Quality.DEPLETED`` would silently discard real
information the format itself doesn't let a reader recover unambiguously.
A Mercenary-state army is masked less often than an ordinary one (102 of
111 real Mercenary armies reveal their real quality) but not
reliably enough to treat "Mercenary" as the real reveal rule --
genuinely still open.

**Phase 995 -- Feature records at scale: a defeated guardian's real
transformation, and the leader-held ``trowner`` convention confirmed.**
Using the same ``feature_id``-as-GW-list-index correspondence Phase 994
established for armies (confirmed here too: a Feature's own ``feature_id``
is the exact 0-based position ``parser/gw_world.py parse_gw_features()``
already returns for the same real world file), all 36 real Feature
records across the 12-file corpus were paired with their own real
``GWFeatureRecord``. ``feature_type`` matched with **zero exceptions**.
``unknown_962a`` is ``0`` in all 36 real samples -- no observed variance
to test a hypothesis against; still genuinely open. ``monster`` and
``engagement_state`` matched in all but 3 cases, and those 3 are not a
parser bug: they are 3 independent XK snapshots (``XK3__T2.K0``,
``XK3__T3.K0``, ``XK3__T4.K0``) of the *same* single real event, the only
dead Feature anywhere in this campaign's Turns 1-4 -- Feature 15
(Piratum's Catacombs, Kingdom 0's Home), whose Spectre guardian was
defeated between Turn 1 and Turn 2. Real GW shows this as
``engagement_state=DEAD`` with the monster's identity preserved
(``monster=SPECTRE``); XK instead shows ``monster=Monster.NOMONSTER``
(this project's own pre-existing "no monster" sentinel) and
``engagement_state=MonsterEngagementState.MERCENARY`` (not ``DEAD``) in
all 3 snapshots, with ``feature_type`` staying correctly ``CATACOMBS``
throughout -- a real, reproducible XK-side convention for "guardian
cleared", not a mirror of GW's own literal ``DEAD`` state.

The same Feature's own Treasure record (the Shadow Sword) corroborates
this: ``trowner`` reads ``271`` (``256 + 15``, the already-documented
feature-held convention) at Turn 1, then ``0`` at Turns 2-4 after the
guardian falls. Because King Babba Sissoko also happens to hold
``leader_id=0``, this single example cannot by itself distinguish "now
held by leader 0" from a generic "cleared" sentinel. A full scan of every
Treasure record in the 12-file corpus for any ``trowner`` deviating from
``256 + feature_id`` found exactly one more, independent case that does
disambiguate it: ``XK3__T3.K2``, a Treasure record carrying
``feature_id=130`` (past this world's real 128-Feature range, i.e. not
bound to any currently-extant Feature at all -- the treasure table also
holds free-floating items with their own slot numbering once their
origin Feature is gone) with ``trowner=99``. Leader id 99 is a real,
ordinary (non-King) hero in that same file -- ``Quintilian``, Kingdom 2,
``Race.HUMAN`` -- holding a ``Treasure.LEADERSHIP_HUMAN`` item ("Sword
Excalibur"). ``99`` cannot be a "cleared" sentinel coinciding with a
King's id here (Quintilian isn't a King; this corpus's King ids are
0-9), so this independently confirms the disassembly documentation's own
asserted rule: **a leader-held item's ``trowner`` is that leader's own
raw ``leader_id``**, not a derived value. Combined with the Turn 1-4
Shadow Sword sequence, the most likely reading of ``trowner=0`` there is
"now held by leader 0" (King Babba Sissoko) rather than a distinct
sentinel, but with only one such King-id-0 example this remains a
one-sample inference, not independently proven the way leader 99's case
is.

**Phase 996 -- character-card fields at scale, one real naming
correction, one field fully decoded.** Using the same leader_id-as-
GW-list-index correspondence (``parser/gw_world.py parse_gw_leaders()``
for the same real world file), 58 real full ``XKLeaderCard`` records
across the 12-file corpus were paired with their own real
``GWLeaderRecord``. Three already-named-but-never-cross-checked fields
are now confirmed exactly, 58/58, no exceptions: ``lfdisc`` ==
``feature_discoveries``, ``ldiscp`` == ``discovery_points``, ``lwmsp`` ==
``white_magic_service_points``. One field is a real naming correction:
the slot the delivered disassembly material calls ``admiral_merit``
(its own stated confidence is only the far pointer address, ``82E2`` --
"i nomi semantici dei contatori derivano dalle corrispondenze del
corpus", i.e. a corpus-correspondence guess, not a certain name) in
fact equals GW's own ``general_merit`` field in all 58 cases, while
matching GW's own, separate ``admiral_merit`` field in only 35/58 --
renamed here to ``general_merit`` accordingly.

``skills``/``aptitudes`` are confirmed to be the real per-ability
``(skill, aptitude)`` pairs: ``XKLeaderCard.skills[i]``/``aptitudes[i]``
equals ``GWLeaderRecord.skills.raw_values[2*i]``/``[2*i+1]`` for
``LEADER_ABILITY_ORDER``'s first 15 real abilities, in 819 of 870
(94%) pairs checked exactly, with slot 15 (``noabil``) confirmed
always ``(0, 0)`` padding in both, 58/58. The 51 residual mismatches
(affecting 26 of 58 leaders, almost all a single ability each) are not
a decode error: in 48 of 51, GW's own same-turn value is
``>=`` XK's in both skill and aptitude (never lower) -- consistent with
GW reflecting a later point in that turn's own processing pipeline
(e.g. after weekly Practice resolution) than the XK snapshot of the
same nominal turn number, not a pairing-order bug. (The remaining 3,
all the same one leader -- Riose -- are a single aptitude point the
other way, genuinely unexplained but too small and too narrowly
concentrated to indicate a structural issue.)

``sex_flags``, read full-width as a signed word, is ``0`` in all 58
real samples -- consistent with GW's own ``sex_override_flag`` boolean,
also ``False`` throughout this corpus (no real female leader exists in
this campaign to exercise the nonzero case) -- the bitfield's own
further semantics remain genuinely untested. ``leader_races``' real
observed value range across the full corpus is exactly ``{DWARVEN,
ELVEN, HUMAN, ORCISH}`` -- no new race, consistent with the
already-confirmed ``Race`` ordinals. ``leader_states`` remains
genuinely open, but is now substantially characterized rather than a
total blank: its real value range is ``{0, 1, 2, 7}``; every full
card's own slot reads exactly ``1`` (58/58, zero exceptions); the
overwhelming majority of slots backing neither a full nor a partial
card read ``7`` (1074 of 1080); partial-card slots split across all
four values with no single clean predicate found despite testing
several real candidates -- GW's own ``kingdom_id``, ``is_king``, and
``condition`` fields were each checked directly and each falsified as
the sole explanation (e.g. Riose's own real Turn 2->3 transition from
unemployed, ``kingdom_id=None``, to hired into Kingdom 0,
``kingdom_id=0``, matches his own XK partial-to-full card transition
exactly, but most other ``state=1`` partial-card leaders keep
``kingdom_id=None`` in GW throughout, so a null/non-null
``kingdom_id`` split alone cannot be the rule).

**Phase 997 -- province records fully decoded and cross-checked at
scale.** Matching ``parser/gw_world.py parse_gw_world()``'s own
province list by its real, unique ``name`` field (both formats carry
one) rather than by index, all 177 real province records across the
12-file corpus were paired with their own real ``GWProvinceRecord``.
``terrain`` and ``race`` matched with **zero exceptions** (177/177).
For the 59 records with this Kingdom's own full economic view,
``tax``/``recruit_type_1``/``recruit_type_2`` matched **zero
exceptions** against GW's own fields, and ``owner_kingdom_id`` matched
the real Kingdom of GW's own ``governor_leader_id`` (cross-referenced
through ``parse_gw_leaders()``) with **zero exceptions**. For the 75
records with only a visible owner, ``visible_owner_leader_id`` matched
GW's own ``governor_leader_id`` directly, **zero exceptions**. The
field previously kept raw as ``unknown_9197_word`` is now fully
decoded: it is **exactly** GW's own ``effects_bitmask`` (``termod``)
field, confirmed byte-for-byte across all 177 real records including
both non-zero real samples on hand (``XK3__T2.K1``'s "the Mermaid Sea"
and "the Icaria Sea", both ``0x40`` -- ``TERMOD_PLAGUE_EFF_MASK``'s own
range, i.e. ``plague_effect_level == 4`` via that already-existing
module's own decode property) -- renamed to ``effects_bitmask``, no new
lookup table needed since ``parser/gw_world.py``'s own ``TERMOD_*``
constants and properties already decode every bit.

**Phase 998 -- the Army record's own ``quality_or_mask`` reveal rule,
solved for 96% of real armies.** Cross-referencing each army's real
owner against ``quality_or_mask``'s own reveal/mask split (nonzero vs.
``0``) at scale, across all 3015 real army/``GWArmyRecord`` pairs,
finds a single rule with **zero exceptions** across 2904 of them
(96.3%): **``quality_or_mask`` is revealed exactly when this Kingdom
effectively owns the army.** Concretely, two cases, both checked with
zero exceptions in both directions:

- A leader-commanded army (``GWArmyRecord.commanded_by_leader_id`` set):
  revealed iff that leader's own real Kingdom (via
  ``parse_gw_leaders()``) is this file's own ``kingdom_id`` -- ``77`` of
  ``77`` own-Kingdom armies revealed, ``0`` of ``1480`` other-Kingdom
  armies revealed.
- A leaderless army whose real ``state`` is ``HIRED`` (an ordinary
  province garrison) or ``ZOMBOID`` (an undead garrison): revealed iff
  it sits at a coordinate this file's own ``provinces`` list shows as
  owned by this Kingdom (``owner_kingdom_id`` matches) -- ``11`` of
  ``11`` own-province garrisons revealed, ``0`` of ``754`` other/unknown-
  province garrisons revealed. A leaderless army whose real ``state`` is
  ``DEAD`` is masked unconditionally (``582`` of ``582``), consistent
  with a destroyed army having no current owner to reveal it to.

This rule is reconstructible from already-decoded XK fields alone, not
only from external GW ground truth: "this file's own ``kingdom_id``"
is the header field, "a leader's own Kingdom" is knowable because only
this Kingdom's own leaders get a full ``XKLeaderCard`` in this same
file, and "a province this Kingdom owns" is ``XKProvinceRecord.
owner_kingdom_id`` in this same file's own ``provinces`` list -- GW was
needed only to confirm the rule, not to state it.

The one real exception: a leaderless army whose real ``state`` is
``MERCENARY`` (``is_mercenary`` real armies, roaming free companies)
does **not** follow the ownership rule -- checked directly, both
directions contradicted (some own-province Mercenary armies are
masked, some other-Kingdom-province ones are revealed) -- and is
instead revealed far more often than not regardless of location
(``102`` of ``111``, consistent with the already-known Phase 994
figure). This 3.7% of real armies remains a genuine, real, unresolved
exception -- not reducible to the ownership rule above, and not yet
reducible to any other single-field rule tried.

**Phase 999 -- the globals block and both flag areas, structurally
characterized at scale.** For every turn with all 3 of this campaign's
real Kingdom files on hand (all 4 turns), every unnamed global word
that varies at all (``DS_C2F6``/``C2F8``/``C2FC``/``C2FE``/``C308``/
``C316``/``C330``/``C332``/``C334``/``C336``, and the whole run from
``DS_C388`` through ``DS_C3FA``) is **identical across all 3 Kingdoms'
own files for that turn**, zero exceptions -- these are genuinely
turn-level (or shared/world-level) values, not per-Kingdom secrets one
Kingdom's own file reveals and another's withholds. The ``DS_C388``-
``DS_C3FA`` run in particular has the shape of leftover host-process
memory rather than meaningful encoded data (arbitrary-looking,
round-in-hex values like ``0x3C00``/``0x0D00``/``0xFF00``, shared
identically by the 3 files the host writes back-to-back in the same
turn-processing run) -- a real, data-backed inference, not disassembly-
certain, so kept exactly as raw as before.

``flags_c4fc`` is **not a flat 256-bit flag field**: it is indexed by
``leader_id`` (only bytes ``0..leader_capacity-1`` ever carry data,
confirmed: the highest nonzero index seen in the whole 12-file corpus
is exactly ``100``, i.e. ``leader_capacity`` itself, the N+1 slot this
format's leader vectors already reserve elsewhere). Every byte at an
index with neither a full nor a partial character card is confirmed
``0``, zero exceptions (1142 of 1142 checked); every one of this
corpus's own 3 real Kings also reads exactly ``0`` at their own
``leader_id``. A real Hero's own full-card ``leader_id`` usually (24 of
25 real Heroes checked) carries a small, nonzero integer (``1``-``5``
observed, stable across every turn the same Hero has a full card in)
-- but the role of that integer resists every real hypothesis tried
(``hire_turn``, race, alignment, temper, and each of the already-
decoded ``general_merit``/``defender_merit``/``lfdisc``/``ldiscp``/
``lwmsp`` fields), and one real Hero (Quintilian) reads ``0`` too, so
"nonzero" isn't even a clean full-card/no-full-card split -- genuinely
open. ``flags_c3fc`` is structurally different: it is **mostly**
shared identically across this campaign's 3 Kingdoms at the same turn
(confirmed at Turns 2-4), with only a handful of real per-Kingdom bit
differences at specific indices (e.g. index 22 reads ``10`` for
Kingdom 2 but ``8`` for Kingdoms 0 and 1 at every one of Turns 2-4) --
and Turn 1's own nonzero-index pattern is entirely different in shape
from Turns 2-4's shared one, consistent with this project's own
already-established finding (``parser/gw_world.py``) that ``GW3__T1``
is itself a pre-turn-1 snapshot, not an ordinary turn. No bit-level
meaning is decoded for either flag area beyond this structural
picture.

**Phase 1000 -- Feature/Treasure fields pushed one step further
against GW's own raw fields.** ``feature_count`` (the named global) is
confirmed, in every one of the 12 real files, to be the real *world*
total (``128``, exactly ``len(parse_gw_features(...))`` for that turn)
-- not this Kingdom's own known-feature count, which is far smaller
(``2``-``8`` in this corpus's own ``world.features``). A feature-held
Treasure's own ``trowner`` is now cross-checked directly against GW's
own raw ``GWFeatureRecord.trowner_raw`` field (not just re-derived from
the ``256 + feature_id`` arithmetic and a name match, as before): all
``13`` real matched cases agree exactly, zero exceptions -- confirming
``trowner`` is a literal copy of that same underlying value, not an
independently recomputed one. ``trcharges`` has, as before, zero real
examples in this corpus whose ordinal falls in the ``[70, 92)`` range
that would carry one, so its predicate remains structurally confirmed
(Phase 992) but its actual value is still untested against GW's own
``trcharges`` field.

``unknown_962a`` has a real, named candidate worth recording even
though it can't be confirmed from data alone: ``parser/gw_world.py``'s
own ``GWFeatureRecord.fdis_raw`` -- the Pascal source's own name for
that field is "discovery **or flags**" (ambiguous even at the source),
and it is confirmed constant ``0`` across *that* module's own full,
pre-existing 12-turn, 128-feature-per-turn real corpus, exactly
mirroring ``unknown_962a``'s own "always ``0`` in all 36 real XK
samples" finding (Phase 995). The naming pattern also fits: this
project has already confirmed (Phase 996) that a leader's own
``lfdisc``/``ldiscp`` fields are real, "feature discovery" / "discovery
points" counters -- the same ``fdis``-rooted Pascal naming family, at
the Feature level instead of the leader level, is a plausible same-
concept counterpart. This is a **named hypothesis, not a confirmed
decode**: both fields are always ``0`` in every real sample on hand in
either corpus, so there is no actual data to tell whether they are the
same quantity or merely two different, equally-silent always-``0``
fields -- a real sample where some feature has actually been
discovered (nonzero in either field) would settle it outright. Kept as
``unknown_962a``, not renamed, until such a sample exists.

**Phase 1001 -- a Treasure's own ``name`` field checked against this
project's own pre-existing, ``TREASURE.X2``-sourced name tables.** The
full real corpus holds exactly 5 distinct real Treasure instances (16
raw records once repeats across turns are collapsed). For the one
"generic" type repeated across 3 different real features
(``Treasure.GOLD_HOARD_LARGE``, features 1/17/99), ``name`` reads
exactly ``"Large Hoard of Gold"`` every time -- a byte-for-byte match
to this project's own pre-existing ``models/treasure.py
GOLD_HOARD_DISPLAY_NAME[Treasure.GOLD_HOARD_LARGE]``, confirming a
generic treasure's ``name`` is the type's own fixed display name, not
a per-instance string. For the 4 distinct "unique artifact" types (one
real instance each), ``name`` matches this project's own pre-existing,
directly ``TREASURE.X2``-transcribed ``TREASURE_NAME`` table exactly
for 3 of 4: ``Treasure.WEAPON_2`` -> ``"Shadow Sword"``,
``Treasure.WAND_FLOOD`` -> ``"Feathers of Rain-Dancing"``,
``Treasure.BOOK_PSYCHIC`` -> ``"Codex of Mental Prowess"``. The 4th is
a real, confirmed discrepancy, not a decode bug (verified directly
against the raw bytes: a genuine ``0x0F`` length prefix precedes a
literal 15-character string): ``Treasure.LEADERSHIP_HUMAN``'s real XK
instance (``XK3__T3.K2``, feature 130, Quintilian's own Excalibur)
reads ``name == "Sword Excalibur"``, where ``TREASURE_NAME``'s own
verbatim-from-``TREASURE.X2`` value is ``"Excalibur"`` (no "Sword ").
Left unresolved rather than assumed to be an error in either source --
only one real sample exists to check this specific ordinal against.
This also confirms a Treasure's own ``name`` is an ordinary,
unbounded Pascal ShortString, **not** subject to the King-title
table's own fixed 15-character cutoff (``"Feathers of Rain-Dancing"``,
24 real characters, is the longest on hand and reads back whole).

**Phase 1002 -- a full character card's own ``actions``/``objects``
decoded against the real K1 move files, and a ``planstart``/``planend``
correction.** This project already has a full parser for the real
``AK3__Tn.K1`` move files Kingdom 1's own player actually submitted
(``parser/k1_moves.py``, independent of this module) -- Kingdom 1's own
leaders' full cards in ``XK3__T(n+1).K1`` can therefore be checked
directly against that same Kingdom's own real submitted plan for turn
``n``, not just against GW's own post-processing snapshot. Across all 3
available turn-pairs (``T1``->``XK T2``, ``T2``->``XK T3``, ``T3``->
``XK T4``) and every one of that Kingdom's own leaders with a full card
in both: ``actions[i]`` matches that leader's own real ``P<i>`` action
code from the preceding turn's K1 file **exactly, 55 of 55 phases,
zero exceptions**. ``objects[i]`` matches that same phase's own real
``obj`` value **exactly for every action type except ``ActionCode.
LMOVE`` (37 of 37 non-``LMOVE`` phases, zero exceptions)** -- every
single mismatch found (18 of 18) is on an ``LMOVE`` phase, and this
project's own production turn code (``turn/plan_dispatch.py``'s real
``ActionCode.LMOVE`` dispatch) already explains why: an ``LMOVE``
phase's own ``obj`` is itself a packed hex-coordinate
(``decode_hex_number(phase.obj, board_width)``), a structurally
different kind of value from the simple small-integer target id every
other action's own ``obj`` holds -- so XK's own ``objects[i]`` for an
``LMOVE`` phase specifically is *not* expected to equal the raw K1
``obj`` integer directly, and indeed doesn't. What XK's own value
represents for that one action type is not pinned down (several
real coordinate-decode readings were tried directly against the real
``coord``/``birth_coord`` fields and none matched), but the *reason*
it diverges is now understood, not just observed.

This also **corrects** this dataclass's own prior "``-1`` is a real,
confirmed 'no plan' value" claim: every single full card in the entire
12-file corpus reads ``planstart=-1``/``planend=-1``, with zero
exceptions -- including, now directly confirmed via the same K1
cross-check, leaders who very much *did* have a full, 5-phase plan
submitted and already executed by snapshot time. ``-1`` cannot mean
"no plan was ever submitted" for those leaders. The better-supported
reading is "no plan is currently pending at snapshot time" -- i.e. the
previous turn's plan has already been consumed by the time XK is
exported, which this corpus's own snapshot timing happens to make true
for every single real card on hand, leaving the genuinely-nonzero case
still unobserved. ``extra_low_bytes`` is not a simple copy or low byte
of the real K1 ``extra`` value for the *same* phase -- checked directly
(including as a literal low byte, modulo 256), no correspondence found
-- but Phase 1003 below finds a real, non-coincidental partial
correspondence to the LMOVE ``obj`` value instead.

**Phase 1003 -- ``extra_low_bytes``'s own LMOVE-specific, partial
correspondence.** Checking ``extra_low_bytes[i]`` against *that same
phase's own* real K1 ``obj`` value (not ``extra``) at the same scale as
Phase 1002's own cross-check finds a real, action-specific pattern:
for an ``ActionCode.LMOVE`` phase, ``extra_low_bytes[i] == obj``
in 10 of 18 real cases -- for every other action type, zero matches in
37 cases (ruling out coincidence; the correspondence is real and
LMOVE-specific, the same action type Phase 1002's own ``objects``
exception already singled out). The 8 real exceptions mostly (7 of 8)
read ``0`` instead of the real target value. No single clean predicate
was found to separate the matching and non-matching cases -- tried and
ruled out: plan position (both match and mismatch occur at every
position ``P0``-``P4`` except ``P0``, which only ever matches),
the preceding or following phase's own action type, and grouping by
leader or by turn-transition (both groups mix matches and non-matches
for the same leader within the same turn-transition). Settling this
further would most likely need a disassembly of the turn-*processing*
engine's own write-back to a leader's in-memory plan record (only the
XK *writer* has been disassembled so far) -- the pattern's own shape
(a real value half the time, ``0`` otherwise, specific to the one
action type whose own ``obj`` is a coordinate rather than a plain id)
is consistent with that record being live-mutated by move execution
itself before XK captures it, but this is not confirmed.

**Phase 1004 -- the full/partial character-card split is a complete
biconditional with real ownership.** Checked directly against GW's own
``kingdom_id`` for every leader in the 12-file corpus: a leader gets a
full card in this file **if and only if** they belong to the viewing
Kingdom. Both directions confirmed with zero exceptions: every one of
this Kingdom's own real leaders (57 of 57) gets a full card, never a
partial one or neither; every real partial card (68 of 68) belongs to
some *other* Kingdom (or no Kingdom at all), never this one. A reader
of this format can therefore tell "is this my own leader" directly
from which list (if either) a ``leader_id`` appears in, with no need
to cross-reference GW or any other ground truth.

**Phase 1005 -- the player tail's own 12-byte ``relations_D1D4`` span
fully decoded.** This project already has a confirmed, independently-
sourced real field for exactly this concept: ``parser/gw_world.py
GWKingExtension.diplomatic_relations`` -- a King's own king-id-ordered
view of every King's relation to them (``DiplomaticRelation.ENEMY``/
``NEUTRAL``/``ALLIED``/``TEAMED``), already cross-validated elsewhere
in this project against ``GW3__T10``'s own real relation downgrade.
Checked directly against this file's own ``relations_D1D4`` bytes for
this file's own King, across the full 12-file corpus: **exact match,
120 of 120 real king-slots, zero exceptions**. Promoted out of the raw
``player_tail`` dict into a real, typed ``XKWorld.diplomatic_relations``
field. The 2 slots past ``king_count`` (every real sample has 10 real
Kings, 12 raw slots) are always ``0``/``ENEMY`` -- unused padding, the
same pattern the King title table (Phase 993) already shows, not a
genuine "11th and 12th King" relation.

**Phase 1006 -- two more player-tail words decoded against
``GWKingExtension``.** Checking every still-raw player-tail word
against every numeric field on this project's own pre-existing
``GWKingExtension`` for this file's own King, across the full 12-file
corpus, finds two more exact, real (non-coincidental) matches:
``DS_8D83`` is exactly ``account_number`` (``100``/``101``/``102`` for
Kingdoms 0/1/2 respectively, every real sample) -- renamed to
``account_number``. ``DS_8E49_low`` is exactly ``met_kings_bitmask``
(real variance confirmed, not just a shared constant: ``0`` at Turns
1-2, then ``2``/``1``/``256`` for Kingdoms 0/1/2 respectively at Turns
3-4, matching exactly every time) -- renamed to
``met_kings_bitmask_low``, keeping the "_low" suffix the real
disassembly already gives it, since XK only ever captures the low word
of that field and this corpus's own small King count never exercises a
high-word bit. Two further candidates were found but are **not**
renamed, for lack of real discriminating evidence: ``DS_8CBD`` always
reads ``15``, matching ``election_request_or_previous_choice`` exactly
in every sample, but with zero observed variance a specific-looking
constant still isn't distinguishable from coincidence the way a
varying field is; ``DS_8DC5`` always reads ``1``, matching
``player_mode``, but ``1`` is too common a value to carry real
evidentiary weight on its own. The remaining player-tail words
(``DS_8B31``, ``DS_8B73``, ``DS_8D41``, ``DS_8ECD_low``, ``DS_8F51_low``)
are likewise always-constant in this corpus and were checked against
every other ``GWKingExtension`` field with no distinguishing match
found; kept raw.

**Phase 1007 -- ``DS:89C7`` decoded as each King's own real sex.** The
12 raw bytes read, in every one of the 12 real files (identical in
every sample, since no King's own sex ever changes), as the literal
ASCII characters ``M``/``M``/``M``/``M``/``M``/``M``/``M``/``F``/``F``/
``M`` for the first 10 slots -- exactly this project's own pre-existing
``GWKingExtension.is_male`` for this campaign's real 10 Kings, king-id
ordered (Kings 7 and 8, Giovanna d'Arco and Circe, are the only two
real female Kings in this campaign, and are exactly where the two real
``F`` bytes land). Decoded as ``king_sex: tuple[models.sex.Sex | None,
...]`` -- this project's own pre-existing ``Sex`` enum, not a new type.
The 2 slots past ``king_count`` are unused padding (one happens to
still decode as a valid ``Sex.MALE`` byte, the other as ``0``, mapped
to ``None`` here) -- the same pattern every other 12-slot, ≤10-real-King
array in this format already shows.

**Phase 1008 -- the per-recipient word at ``DS:8AE7 + 2*kingdom_id``
decoded as this King's own real treasury.** Checked directly against
``GWKingExtension.treasury`` for this file's own King: exact match, 12
of 12 real samples, zero exceptions, with real variance confirmed
(``10`` at every Kingdom's own Turn 1, then diverging per-Kingdom:
``22``/``11``/``0`` at Turn 2, ``24``/``22``/``4`` at Turn 3,
``30``/``14``/``16`` at Turn 4). Renamed from the previously-raw
``recipient_word`` to ``treasury``.

**Phase 1009 -- the recruitment map cross-checked at scale, and found
to carry more than the province list.** Checked directly against real
GW ground truth (not just this file's own ``provinces`` list) across
the full 12-file corpus: for every one of the 177 real provinces this
Kingdom knows, the recruitment-map cell at that coordinate matches the
real ``recruit_type_1``/``recruit_type_2`` **exactly, zero exceptions**
-- including the 118 of those 177 that this Kingdom doesn't *own* and
whose own ``XKProvinceRecord.recruit_type_1``/``recruit_type_2`` are
therefore ``None`` (that field is only populated for an owned
province's full economics, per the module docstring's own ownership-
shape rule). The recruitment map is a **strictly richer** channel for
this one piece of information: it reveals a known province's real
recruit types regardless of ownership, where the province record
itself only does so for an owned one. For every one of the other 1767
real cells (a province this Kingdom does *not* know at all), both
slots are the ``0x0F``/``None`` sentinel, zero exceptions -- the
recruitment map's own real "known" footprint is exactly this
Kingdom's own known-province set, no broader and no narrower.

**Phase 1010 -- the ``TR_LLs`` liege extension: richer than the full
card, and one real leader-id-reuse artifact.** ``liege_by_leader_id``
covers more than just this Kingdom's own full-card leaders: it also
carries an entry for 62 of the 68 real partial-card leaders across the
corpus -- and the 6 real exceptions are fully explained, not a gap:
each one is independently confirmed, via GW's own ``kingdom_id``, to be
an unemployed/independent character (``kingdom_id=None``), for whom a
liege is meaningless. For every leader_id covered by both a full card
and this extension, the two agree exactly in 57 of 58 real cases. The
one exception (``XK3__T4.K2``, leader 99) is not a decode error: it is
a real leader-id-reuse artifact confirmed independently against GW --
``GW3__T3``'s own leader 99 is Quintilian (Kingdom 2, this Phase's own
earlier Excalibur example); ``GW3__T4``'s own leader 99 is a different
real character, Bo (Kingdom 9). The identity behind this one
``leader_id`` genuinely changed between the two files' own capture
moments, so comparing "the same nominal turn" compares two different
real people for this one slot -- not a flaw in either decoder.

**Genuinely still open** (kept raw rather than guessed, per the
delivered material's own stated limits): the ~115 unnamed globals
(Phase 999: now confirmed turn-level/shared rather than per-Kingdom,
but not otherwise named) and both 256-byte flag areas (Phase 999:
``flags_c4fc``'s own leader-indexed shape confirmed, its per-Hero
integer's real meaning isn't; ``flags_c3fc``'s mostly-shared-with-a-
few-per-Kingdom-bits shape confirmed, no bit meaning decoded); a full
card's own ``sex_flags`` bitfield beyond "0 in this corpus",
``extra_low_bytes`` (Phase 1003: a real, LMOVE-specific partial
correspondence to K1's own ``obj`` found -- 10 of 18 exact matches,
0 of 37 for any other action type -- but no predicate separating the
8 real exceptions from the 10 matches), and ``objects[i]``'s own real
meaning specifically for an ``LMOVE`` phase (Phase 1002: every other
action type and the whole of ``actions`` is now fully decoded against
real K1 data); the
``leader_states`` vector's own exact per-value meaning (Phase 996:
substantially characterized with real data and several real hypotheses
tested and falsified, see above, but no clean rule found yet); a
Feature record's own ``unknown_962a`` (Phase 995: confirmed always
``0`` in all 36 real samples, role still unconfirmed); a Mercenary-
state leaderless Army record's own ``quality_or_mask`` reveal rule
(Phase 998: solved for every other real army shape, but this one real
exception -- 111 of 3015 armies -- resists the same ownership rule and
every other single-field rule tried so far); exactly how a
defeated Feature guardian's ``NOMONSTER``/``MERCENARY`` XK-side
convention is chosen (confirmed real and reproducible, Phase 995, but
only one real dead-Feature event exists in this corpus to observe it);
why each King title table reserves 12 slots for at most 10 real Kings
(no real sample with ``king_count`` above 10 exists to test whether it's
a true fixed cap or simply never-observed to matter); the real SAGA
client reader (only the host *writer* was disassembled); and any
``gamevers`` other than ``3`` (the compiled client has other branches;
this strict decoder deliberately refuses them rather than extrapolate).
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

from ak_engine.models.alignment import ALIGNMENT_BY_ORDINAL, Alignment
from ak_engine.models.army_type import ArmyType
from ak_engine.models.feature import FeatureType
from ak_engine.models.map import HexCoord, Terrain
from ak_engine.models.monster import Monster, MonsterEngagementState
from ak_engine.models.race import Race
from ak_engine.models.sex import Sex
from ak_engine.models.temper import Temper
from ak_engine.models.treasure import Treasure
from ak_engine.parser.gw_world import MOD_PAT_ORDINAL_TO_ARMY_TYPE, DiplomaticRelation

SUPPORTED_FORMAT_REVISION = 30
SUPPORTED_GAME_VERSION = 3
XK_NAME_TABLE_OFFSET = 0x30B

# DS:C2F6 word index -> confirmed real field name (the other 115 of 131
# words in this range are exposed raw, keyed "DS_xxxx" by address -- see
# module docstring).
XK_GLOBAL_FIELD_NAMES: dict[int, str] = {
    0xC302: "gameturn",
    0xC306: "leader_capacity",
    0xC30C: "left",
    0xC30E: "right",
    0xC310: "bottom",
    0xC312: "top",
    0xC314: "gamevers",
    0xC318: "orig_turn",
    0xC320: "gameno",
    0xC322: "due_day",
    0xC324: "due_month",
    0xC326: "due_year",
    0xC328: "turn_days",
    0xC32A: "diplomacy_mode",
    0xC32C: "feature_count",
    0xC338: "army_count",
    0xC33A: "king_count",
    0xC33C: "last_leader",
}

_GLOBALS_START = 0xC2F6
_GLOBALS_WORD_COUNT = 131  # DS:C2F6..C3FA
_FLAGS_AREA_SIZE = 256

# CTBOTH.PAS `ability` order (Tactical..noabil) -- the real index order
# of a full leader card's own 16-entry skills/aptitudes arrays. The 16th
# ("noabil") is a real array slot, not a playable ability.
LEADER_ABILITY_ORDER: tuple[str, ...] = (
    "Tactical",
    "ForcedMarch",
    "Naval",
    "Archery",
    "Melee",
    "White",
    "Necromancy",
    "Elemental",
    "Psychic",
    "Illusionist",
    "Druid",
    "Thief",
    "Explorer",
    "Spy",
    "Sage",
    "noabil",
)

_LEADER_CARD_SIZE = 74
_SENTINEL_END = 0xFE
_SENTINEL_NO_OWNER = 0xFF
_SENTINEL_NO_VISIBLE_OWNER = 0xFE
_TR_LLS_END = 0xFF

_TAG_TR_LLS = 16004
_TAG_TR_SA = 16005
_TAG_TR_T2 = 16006
_TAG_TR_HK = 16007
_TAG_TR_END = 16001

XK_PLAYER_TAIL_FIELDS_BEFORE_RELATIONS: tuple[tuple[str, int], ...] = (
    ("DS_8B31", 1),
    ("DS_8B73", 1),
)
XK_PLAYER_TAIL_FIELDS_AFTER_RELATIONS: tuple[tuple[str, int], ...] = (
    ("DS_8CBD", 2),
    ("DS_8D41", 2),
)
XK_PLAYER_TAIL_FIELDS_TRAILING: tuple[tuple[str, int], ...] = (
    ("DS_8DC5", 2),
    ("DS_8ECD_low", 2),
    ("DS_8F51_low", 2),
)


class XKParseError(ValueError):
    """Raised when an ``XK`` file doesn't match the confirmed shape above."""

    def __init__(self, message: str, *, byte_offset: int | None = None):
        self.byte_offset = byte_offset
        super().__init__(message if byte_offset is None else f"{message} (byte offset {byte_offset})")


class _Reader:
    """A sequential byte-string reader mirroring the real writer's own
    field order -- ports the delivered, roundtrip-verified decoder's
    internals, adapted to raise ``XKParseError`` and to not retain a
    flat leaf log (this module exposes typed dataclasses instead).
    """

    __slots__ = ("data", "offset")

    def __init__(self, data: bytes):
        self.data = data
        self.offset = 0

    def bytes_(self, name: str, length: int) -> bytes:
        start = self.offset
        end = start + length
        if length < 0 or end > len(self.data):
            raise XKParseError(f"{name}: truncated", byte_offset=start)
        self.offset = end
        return self.data[start:end]

    def u8(self, name: str) -> int:
        return self.bytes_(name, 1)[0]

    def u16(self, name: str) -> int:
        return struct.unpack_from("<H", self.bytes_(name, 2))[0]

    def s8(self, name: str) -> int:
        return struct.unpack_from("<b", self.bytes_(name, 1))[0]

    def s16(self, name: str) -> int:
        return struct.unpack_from("<h", self.bytes_(name, 2))[0]

    def peek(self, name: str) -> int:
        if self.offset >= len(self.data):
            raise XKParseError(f"{name}: unexpected EOF", byte_offset=self.offset)
        return self.data[self.offset]

    def pstring(self, name: str) -> str:
        length = self.u8(name + ".length")
        raw = self.bytes_(name, length)
        return raw.decode("cp850")

    def sentinel(self, name: str, expected: int) -> None:
        start = self.offset
        got = self.u8(name)
        if got != expected:
            raise XKParseError(f"{name}: expected {expected:#x}, got {got:#x}", byte_offset=start)


@dataclass(slots=True)
class XKHeader:
    format_revision: int
    kingdom_id: int


@dataclass(slots=True)
class XKGlobals:
    """The 774-byte global block (``DS:C2F6..C5FB``). ``values`` holds
    all 131 words, named where confirmed (``XK_GLOBAL_FIELD_NAMES``) and
    ``DS_xxxx``-keyed otherwise; the named-field properties below are
    thin lookups into it. Every unnamed word that varies at all is
    confirmed (Phase 999) to be identical across this campaign's 3
    Kingdoms' own files for the same turn -- turn-level/shared state,
    not a per-Kingdom secret. ``flags_c3fc``/``flags_c4fc`` are the two
    256-byte areas that follow, kept raw -- see module docstring's own
    Phase 999 addendum for their real structural shape (``flags_c4fc``
    is leader_id-indexed; ``flags_c3fc`` is mostly shared across
    Kingdoms with a few real per-Kingdom bits).
    """

    values: dict[str, int]
    flags_c3fc: bytes
    flags_c4fc: bytes

    @property
    def game_turn(self) -> int:
        return self.values["gameturn"]

    @property
    def leader_capacity(self) -> int:
        return self.values["leader_capacity"]

    @property
    def board_left(self) -> int:
        return self.values["left"]

    @property
    def board_right(self) -> int:
        return self.values["right"]

    @property
    def board_top(self) -> int:
        return self.values["top"]

    @property
    def board_bottom(self) -> int:
        return self.values["bottom"]

    @property
    def game_version(self) -> int:
        return self.values["gamevers"]

    @property
    def king_count(self) -> int:
        return self.values["king_count"]

    @property
    def army_count(self) -> int:
        return self.values["army_count"]

    @property
    def feature_count(self) -> int:
        return self.values["feature_count"]

    @property
    def last_leader_id(self) -> int:
        return self.values["last_leader"]


@dataclass(slots=True)
class XKLeaderCard:
    """One full, 74-byte character card -- see module docstring.
    ``skills``/``aptitudes`` are 16-entry raw lists, indexed by
    ``LEADER_ABILITY_ORDER`` (the real ``CTBOTH.PAS ability`` order) --
    confirmed (Phase 996) to be the exact same ``(skill, aptitude)``
    pairs ``parser/gw_world.py``'s own ``GWLeaderRecord.skills.
    raw_values`` already carries for the same real leader, for the 15
    real abilities (slot 15, ``noabil``, is always ``(0, 0)`` padding,
    not a 16th real ability). ``general_merit`` is named for what it's
    confirmed (Phase 996) to equal -- GW's own ``general_merit`` field,
    not GW's own ``admiral_merit`` field it was first guessed to be,
    from the delivered disassembly material's own corpus-correspondence
    guess (its own stated confidence was the far pointer address alone,
    not this specific name).

    ``actions``/``objects`` (Phase 1002) are confirmed against Kingdom
    1's own real submitted ``AK3__Tn.K1`` move files (not just GW's own
    post-processing snapshot): ``actions[i]`` is that leader's own real
    ``P<i>`` action code from the preceding turn, exact, zero
    exceptions. ``objects[i]`` is that phase's own real ``obj`` value,
    exact, for every action type except ``ActionCode.LMOVE`` -- an
    ``LMOVE`` phase's own real ``obj`` is itself a packed hex-coordinate
    (``turn/plan_dispatch.py``'s own ``decode_hex_number(phase.obj,
    board_width)``), not a simple target id, which is why XK's own
    value there doesn't match the raw K1 integer; what it holds instead
    isn't pinned down. ``extra_low_bytes`` doesn't correspond to the
    real K1 ``extra`` value at all, but (Phase 1003) does to that same
    phase's own ``obj`` for an ``LMOVE`` phase specifically, in 10 of
    18 real cases (0 of 37 for any other action type -- a real,
    non-coincidental pattern, not fully decoded: no predicate was found
    to separate the matches from the 8 real exceptions, which mostly
    read ``0`` instead). ``planstart``/``planend`` are signed bytes; ``-1`` is
    confirmed real (every full card in the whole 12-file corpus reads
    ``-1``/``-1``), but -- corrected from this field's own prior
    docstring claim -- it does **not** mean "no plan was ever
    submitted": the same Phase 1002 cross-check directly confirms
    leaders reading ``-1``/``-1`` here who very much had a full 5-phase
    plan submitted and already executed by snapshot time. The better-
    supported reading is "no plan is currently pending at snapshot
    time"; the genuinely-nonzero case remains unobserved.
    """

    leader_id: int
    client_owner: int
    lliege: int
    skills: list[int]
    aptitudes: list[int]
    coord: HexCoord
    birth_coord: HexCoord
    hire_turn: int
    general_merit: int
    defender_merit: int
    lfdisc: int
    ldiscp: int
    lwmsp: int
    temper: Temper
    alignment: Alignment
    sex_flags: int
    actions: list[int]
    objects: list[int]
    extra_low_bytes: list[int]
    planstart: int
    planend: int


@dataclass(slots=True)
class XKPartialLeaderCard:
    """A leader known only by location -- confirmed (Phase 1004) to
    never be one of this Kingdom's own: every real partial card belongs
    to another Kingdom or no Kingdom at all (see module docstring).
    """

    leader_id: int
    coord: HexCoord


@dataclass(slots=True)
class XKProvinceRecord:
    """One known-province record -- see module docstring. Exactly one of
    the 3 real ownership shapes applies:

    - ``owner_kingdom_id`` set (and ``tax``/``recruit_type_1``/
      ``recruit_type_2`` with it): this Kingdom's own full economic view
      of a province it owns (``ownership_marker`` is itself the owning
      Kingdom's id).
    - ``visible_owner_leader_id`` set or ``None`` (``ownership_marker ==
      0xFF``): another province's owner is visible by leader id, with no
      economic data -- ``None`` means "visibly ungoverned", not
      "unknown".
    - All three ``None`` (``ownership_marker == 0xFE``): no ownership
      information at all.

    ``effects_bitmask`` is confirmed (Phase 997) to be exactly
    ``parser/gw_world.py GWProvinceRecord.effects_bitmask`` (``termod``)
    for the same real province -- that module's own ``TERMOD_*``
    constants and decode properties (``plague_effect_level``,
    ``bless_effect_active``, etc.) apply here unchanged; no separate
    table is needed.
    """

    coord: HexCoord
    name: str
    terrain: Terrain
    race: Race
    exploration_percent: int
    owner_kingdom_id: int | None
    visible_owner_leader_id: int | None
    tax: int | None
    recruit_type_1: ArmyType | None
    recruit_type_2: ArmyType | None
    effects_bitmask: int


@dataclass(slots=True)
class XKFeatureRecord:
    """One Feature-summary record (8 bytes) -- see module docstring.
    ``unknown_962a`` is a real ``DS:962A`` word, always ``0`` in every
    sample so far (36 real records checked, Phase 995), role
    unconfirmed. ``parser/gw_world.py GWFeatureRecord.fdis_raw`` is a
    plausible, named candidate for the same quantity (Phase 1000 --
    same "always 0 in every real sample" behavior in that module's own
    much larger pre-existing corpus, and the same ``fdis``-rooted
    Pascal naming family this project already confirmed at the leader
    level), but neither field has a single nonzero real example to
    confirm or refute it against -- not renamed on that basis alone.

    ``monster``/``engagement_state`` mirror real GW ground truth for a
    live guardian, but Phase 995 found a real, reproducible exception
    for a *defeated* one: once a Feature's guardian has been cleared, XK
    reports ``monster=Monster.NOMONSTER`` and
    ``engagement_state=MonsterEngagementState.MERCENARY`` instead of
    mirroring GW's own literal ``DEAD`` state and the monster's original
    identity -- confirmed across 3 independent XK snapshots of the same
    real event (see module docstring's Phase 995 addendum).
    """

    feature_id: int
    coord: HexCoord
    unknown_962a: int
    monster: Monster
    engagement_state: MonsterEngagementState
    feature_type: FeatureType


@dataclass(slots=True)
class XKTreasureRecord:
    """One Treasure record -- see module docstring. ``trcharges`` is
    only present (real disassembly-proven predicate, ``0x40558``) when
    ``treasure`` has a raw ordinal in ``[70, 92)``; ``None`` otherwise,
    never defaulted to ``0``. ``trowner`` is kept raw rather than split
    into a typed union: the feature-held convention is ``256 +
    feature_id`` (confirmed by example); the leader-held convention is a
    plain raw ``leader_id`` (Phase 995 -- independently confirmed via
    ``XK3__T3.K2``'s Quintilian, a real non-King hero, holding a
    ``Treasure.LEADERSHIP_HUMAN`` item with ``trowner`` exactly his own
    ``leader_id``, 99). The two conventions aren't distinguishable from
    ``trowner`` alone without also knowing this file's own
    ``feature_id`` range -- also note ``feature_id`` here isn't always a
    currently-extant Feature: a treasure whose origin Feature is gone
    can still appear with a ``feature_id`` past the world's real Feature
    count, a free-floating slot number rather than a live Feature's id.

    ``name`` is confirmed (Phase 1001) to match this project's own
    pre-existing, ``TREASURE.X2``-sourced ``models/treasure.py
    GOLD_HOARD_DISPLAY_NAME``/``TREASURE_NAME`` tables exactly for 4 of
    5 real distinct instances on hand -- a generic type's own fixed
    display name for an ordinary treasure, or a unique artifact's own
    transcribed proper name. The one exception
    (``Treasure.LEADERSHIP_HUMAN``'s real instance reading ``"Sword
    Excalibur"`` where the table's own value is ``"Excalibur"``) is a
    confirmed real discrepancy, not a decode bug, and is left
    unresolved -- see module docstring's own Phase 1001 addendum.
    """

    feature_id: int
    treasure: Treasure
    trcharges: int | None
    trowner: int
    name: str


@dataclass(slots=True)
class XKArmyRecord:
    """One Army record (4 or 8 bytes) -- see module docstring's own
    Phase 994 addendum for ``status``/``detail_status``/
    ``quality_or_mask``. ``army_index`` is this army's own position in
    the real ``0..army_count-1`` loop (with ``255`` always skipped), not
    a stored id -- confirmed (Phase 994) to be the *exact* same 0-based
    position this project's own ``parser/gw_world.py parse_gw_armies()``
    already returns for the same real world file, so the two can be
    zipped directly (after re-inserting the skipped index) for a real
    army's full detail. ``coord``/``commanded_by_leader_id``/
    ``detail_status`` are ``None`` when this record has no location
    details (a literal ``0xFE`` in that position, confirmed real, not
    merely "not yet observed").

    ``quality_or_mask`` is confirmed (Phase 998) to be revealed (nonzero)
    exactly when this Kingdom effectively owns the army -- a leader of
    its own commands it, or (for a leaderless garrison) it sits in one
    of its own provinces -- for 96% of real armies, zero exceptions. A
    leaderless, real-``MERCENARY``-state army is the one confirmed
    exception: mostly revealed regardless of ownership, but not reliably
    enough to extend the same rule to it. See the module docstring's own
    Phase 998 addendum for the full real counts both ways.
    """

    army_index: int
    race: Race
    army_type: ArmyType | None
    quality_or_mask: int
    status: MonsterEngagementState
    coord: HexCoord | None
    commanded_by_leader_id: int | None
    detail_status: MonsterEngagementState | None


@dataclass(slots=True)
class XKDiscoveryRecord:
    feature_id: int
    legacy_word: int


@dataclass(slots=True)
class XKRecruitmentMapCell:
    """One board cell's own known recruit types -- see module docstring's
    own Phase 1009 addendum. Confirmed, zero exceptions across the full
    corpus, to carry the real recruit types for every province this
    Kingdom knows (matching real GW ground truth exactly), regardless
    of ownership -- richer than ``XKProvinceRecord.recruit_type_1``/
    ``recruit_type_2``, which are ``None`` for a known-but-not-owned
    province. Both ``None`` for a province this Kingdom doesn't know at
    all, with zero real exceptions either direction.
    """

    coord: HexCoord
    recruit_type_1: ArmyType | None
    recruit_type_2: ArmyType | None


@dataclass(slots=True)
class XKSecondaryAbilityTable:
    """``TR_SA`` (tag 16005): 90 raw bytes, 15 real abilities x 6 levels
    (``LEADER_ABILITY_ORDER``'s own first 15 entries, excluding
    ``noabil``) -- associates special-ability codes with the real
    prose/name tables those abilities use, not a second skill array.
    """

    levels_by_ability: list[list[int]]


@dataclass(slots=True)
class XKLiegeExtension:
    """``TR_LLs`` (tag 16004): id/lliege pairs. A real ``0xFF`` in the
    ``lliege`` position does not end the list -- only ``0xFF`` in the
    ``id`` position does (a different sentinel than every other list in
    this format).

    Confirmed (Phase 1010) richer than ``XKLeaderCard.lliege``: it also
    covers a real partial-card leader, when (and only when) that leader
    is actually employed by some Kingdom (``kingdom_id`` set in GW) --
    an unemployed/independent character is correctly absent, not a gap.
    See module docstring's own Phase 1010 addendum for the one real
    leader-id-reuse exception found cross-checking it against GW.
    """

    liege_by_leader_id: dict[int, int]


@dataclass(slots=True)
class XKSecondaryTerrainTable:
    """``TR_T2`` (tag 16006): a fixed 30x15 (450-byte) capacity table,
    indexed ``15*x + y`` -- **not** sized to the played board, and not
    proof every cell is a real, active province.
    """

    raw: bytes


@dataclass(slots=True)
class XKHomeKingdomExtension:
    """``TR_HK`` (tag 16007): syntactically supported, sourced from the
    writer's own branch and the real Pascal shield-record size -- no
    real sample in this project's own corpus exercises it yet.
    """

    king_leader_id: int
    shield_record: bytes


_KING_TITLE_TABLE_CAPACITY = 12
_KING_TITLE_SLOT_SIZE = 16


@dataclass(slots=True)
class XKKingTitles:
    """Both per-King title tables (``DS:8B29``/``DS:8B2D``) -- see the
    module docstring's own Phase 993 addendum. Each list has exactly
    ``_KING_TITLE_TABLE_CAPACITY`` (12) entries, indexed by king id; a
    king with no title (or a reserve slot beyond the real ``king_count``)
    reads ``""``, never absent. Confirmed public (identical across every
    Kingdom's own XK file), not filtered per recipient.
    """

    prefix_by_king_id: list[str]
    suffix_by_king_id: list[str]


@dataclass(slots=True)
class XKWorld:
    """The fully decoded contents of one ``XK`` file.

    ``diplomatic_relations`` (Phase 1005) is confirmed, 120 of 120 real
    king-slots checked with zero exceptions, to be exactly ``parser/
    gw_world.py GWKingExtension.diplomatic_relations`` for this file's
    own King -- the real ``DiplomaticRelation`` enum (``ENEMY``/
    ``NEUTRAL``/``ALLIED``/``TEAMED``), king-id-ordered, this King's own
    view of every King including itself (always ``ALLIED`` at its own
    index, a self-relation sentinel). ``king_count``-long; any slot past
    that (up to the raw 12-byte span) is always ``0``/``ENEMY``, unused
    padding -- the same "12 slots reserved for at most 10 real Kings"
    pattern the King title table (Phase 993) already shows.

    ``account_number``/``met_kings_bitmask_low`` (Phase 1006) are
    confirmed exactly, 12 of 12 real samples each, against
    ``GWKingExtension.account_number``/``.met_kings_bitmask`` for this
    file's own King. ``met_kings_bitmask_low`` keeps its own disassembly-
    sourced "_low" suffix because XK only ever captures the low word of
    that real field (per the writer's own source), not confirmed
    equivalent beyond the bit range this corpus's own small King count
    ever sets.

    ``treasury`` (Phase 1008, renamed from the previously-raw
    ``recipient_word``) is confirmed exactly, 12 of 12 real samples,
    against ``GWKingExtension.treasury`` for this file's own King, with
    real per-Kingdom variance across turns, not a shared constant.
    """

    header: XKHeader
    globals: XKGlobals
    leader_names: list[str | None]
    leader_cards: list[XKLeaderCard]
    partial_leader_cards: list[XKPartialLeaderCard]
    leader_races: list[Race]
    leader_states: list[int]
    king_sex: tuple[Sex | None, ...]
    treasury: int
    king_titles: XKKingTitles
    provinces: list[XKProvinceRecord]
    features: list[XKFeatureRecord]
    treasures: list[XKTreasureRecord]
    armies: list[XKArmyRecord]
    discoveries: list[XKDiscoveryRecord]
    diplomatic_relations: tuple[DiplomaticRelation, ...]
    account_number: int
    met_kings_bitmask_low: int
    player_tail: dict[str, bytes]
    recruitment_map: list[XKRecruitmentMapCell]
    liege_extension: XKLiegeExtension | None
    secondary_abilities: XKSecondaryAbilityTable | None
    secondary_terrain: XKSecondaryTerrainTable | None
    home_kingdom: XKHomeKingdomExtension | None


def _read_globals(r: _Reader) -> XKGlobals:
    values: dict[str, int] = {}
    for word_index in range(_GLOBALS_WORD_COUNT):
        address = _GLOBALS_START + 2 * word_index
        key = XK_GLOBAL_FIELD_NAMES.get(address, f"DS_{address:04X}")
        values[key] = r.s16(f"globals.{key}")
    flags_c3fc = r.bytes_("flags_C3FC", _FLAGS_AREA_SIZE)
    flags_c4fc = r.bytes_("flags_C4FC", _FLAGS_AREA_SIZE)
    return XKGlobals(values=values, flags_c3fc=flags_c3fc, flags_c4fc=flags_c4fc)


def _read_king_title_table(r: _Reader, name: str) -> list[str]:
    """Reads one 192-byte per-King title table -- see module docstring's
    own Phase 993 addendum. Each of the 12 fixed-width 16-byte slots
    holds a length-prefixed string in its own first ``1 + length`` bytes;
    the rest of the slot is unused padding, discarded here.
    """

    titles: list[str] = []
    for king_id in range(_KING_TITLE_TABLE_CAPACITY):
        slot = r.bytes_(f"{name}[{king_id}]", _KING_TITLE_SLOT_SIZE)
        length = slot[0]
        titles.append(slot[1 : 1 + length].decode("cp850"))
    return titles


def _read_leader_names(r: _Reader, leader_capacity: int) -> list[str | None]:
    names: list[str | None] = []
    for leader_id in range(leader_capacity):
        name = r.pstring(f"leader_names[{leader_id}]")
        names.append(None if name == f"Ldr-{leader_id}" else name)
    return names


def _read_leader_card(r: _Reader) -> XKLeaderCard:
    leader_id = r.u8("leader.id")
    client_owner = r.u8(f"leader[{leader_id}].client_owner")
    lliege = r.u8(f"leader[{leader_id}].lliege")
    skills = list(r.bytes_(f"leader[{leader_id}].skills", 16))
    aptitudes = list(r.bytes_(f"leader[{leader_id}].aptitudes", 16))
    x = r.u8(f"leader[{leader_id}].x")
    y = r.u8(f"leader[{leader_id}].y")
    born_x = r.u8(f"leader[{leader_id}].born_x")
    born_y = r.u8(f"leader[{leader_id}].born_y")
    hire_turn = r.s16(f"leader[{leader_id}].hire_turn")
    general_merit = r.s16(f"leader[{leader_id}].general_merit")
    defender_merit = r.s16(f"leader[{leader_id}].defender_merit")
    lfdisc = r.u8(f"leader[{leader_id}].lfdisc")
    ldiscp = r.u8(f"leader[{leader_id}].ldiscp")
    lwmsp = r.u8(f"leader[{leader_id}].lwmsp")
    temper = r.u8(f"leader[{leader_id}].temper")
    alignment = r.u8(f"leader[{leader_id}].alignment")
    sex_flags = r.s16(f"leader[{leader_id}].sex_flags")
    actions = list(r.bytes_(f"leader[{leader_id}].actions", 5))
    objects = [struct.unpack("<h", r.bytes_(f"leader[{leader_id}].objects[{i}]", 2))[0] for i in range(5)]
    extra_low_bytes = list(r.bytes_(f"leader[{leader_id}].extra_low_bytes", 5))
    planstart = r.s8(f"leader[{leader_id}].planstart")
    planend = r.s8(f"leader[{leader_id}].planend")
    return XKLeaderCard(
        leader_id=leader_id,
        client_owner=client_owner,
        lliege=lliege,
        skills=skills,
        aptitudes=aptitudes,
        coord=HexCoord(x, y),
        birth_coord=HexCoord(born_x, born_y),
        hire_turn=hire_turn,
        general_merit=general_merit,
        defender_merit=defender_merit,
        lfdisc=lfdisc,
        ldiscp=ldiscp,
        lwmsp=lwmsp,
        temper=Temper(temper),
        alignment=ALIGNMENT_BY_ORDINAL[alignment],
        sex_flags=sex_flags,
        actions=actions,
        objects=objects,
        extra_low_bytes=extra_low_bytes,
        planstart=planstart,
        planend=planend,
    )


def _read_province(r: _Reader) -> XKProvinceRecord:
    x = r.u8("province.x")
    y = r.u8("province.y")
    key = f"province[{x},{y}]"
    name = r.pstring(key + ".name")
    terrain = Terrain(r.u8(key + ".terrain"))
    race = Race(r.u8(key + ".race"))
    effects_bitmask = r.s16(key + ".effects_bitmask")
    exploration_percent = r.u8(key + ".exploration")
    marker = r.u8(key + ".ownership_marker")
    owner_kingdom_id: int | None = None
    visible_owner_leader_id: int | None = None
    tax: int | None = None
    recruit_type_1: ArmyType | None = None
    recruit_type_2: ArmyType | None = None
    if marker == _SENTINEL_NO_OWNER:
        visible_owner = r.u8(key + ".visible_owner")
        visible_owner_leader_id = None if visible_owner == _SENTINEL_NO_OWNER else visible_owner
    elif marker == _SENTINEL_NO_VISIBLE_OWNER:
        pass
    else:
        owner_kingdom_id = marker
        tax = r.u8(key + ".ptax")
        recruit_type_1 = MOD_PAT_ORDINAL_TO_ARMY_TYPE.get(r.u8(key + ".recruit_1"))
        recruit_type_2 = MOD_PAT_ORDINAL_TO_ARMY_TYPE.get(r.u8(key + ".recruit_2"))
    return XKProvinceRecord(
        coord=HexCoord(x, y),
        name=name,
        terrain=terrain,
        race=race,
        exploration_percent=exploration_percent,
        owner_kingdom_id=owner_kingdom_id,
        visible_owner_leader_id=visible_owner_leader_id,
        tax=tax,
        recruit_type_1=recruit_type_1,
        recruit_type_2=recruit_type_2,
        effects_bitmask=effects_bitmask,
    )


def _read_feature(r: _Reader) -> XKFeatureRecord:
    feature_id = r.u8("feature.id")
    x = r.u8(f"feature[{feature_id}].x")
    y = r.u8(f"feature[{feature_id}].y")
    unknown_962a = r.s16(f"feature[{feature_id}].unknown_962a")
    monster = r.u8(f"feature[{feature_id}].monster")
    engagement_state = r.u8(f"feature[{feature_id}].engagement_state")
    feature_type = r.u8(f"feature[{feature_id}].feature_type")
    return XKFeatureRecord(
        feature_id=feature_id,
        coord=HexCoord(x, y),
        unknown_962a=unknown_962a,
        monster=Monster(monster),
        engagement_state=MonsterEngagementState(engagement_state),
        feature_type=FeatureType(feature_type),
    )


def _read_treasure(r: _Reader) -> XKTreasureRecord:
    feature_id = r.u8("treasure.id")
    treasure_ordinal = r.u8(f"treasure[{feature_id}].type")
    trcharges: int | None = None
    if 70 <= treasure_ordinal < 92:
        trcharges = r.u8(f"treasure[{feature_id}].trcharges")
    trowner = r.u16(f"treasure[{feature_id}].trowner")
    name = r.pstring(f"treasure[{feature_id}].name")
    return XKTreasureRecord(
        feature_id=feature_id,
        treasure=Treasure(treasure_ordinal),
        trcharges=trcharges,
        trowner=trowner,
        name=name,
    )


def _read_army(r: _Reader, army_index: int) -> XKArmyRecord:
    race = Race(r.u8(f"army[{army_index}].race"))
    army_type = MOD_PAT_ORDINAL_TO_ARMY_TYPE.get(r.u8(f"army[{army_index}].type"))
    quality_or_mask = r.u8(f"army[{army_index}].quality_or_mask")
    status = MonsterEngagementState(r.u8(f"army[{army_index}].status"))
    marker = r.u8(f"army[{army_index}].x_or_hidden")
    coord: HexCoord | None = None
    commanded_by_leader_id: int | None = None
    detail_status: MonsterEngagementState | None = None
    if marker != _SENTINEL_END:
        x = marker
        y = r.u8(f"army[{army_index}].y")
        leader = r.u8(f"army[{army_index}].leader")
        detail_status = MonsterEngagementState(r.u8(f"army[{army_index}].detail_status"))
        coord = HexCoord(x, y)
        commanded_by_leader_id = None if leader == _SENTINEL_NO_OWNER else leader
    return XKArmyRecord(
        army_index=army_index,
        race=race,
        army_type=army_type,
        quality_or_mask=quality_or_mask,
        status=status,
        coord=coord,
        commanded_by_leader_id=commanded_by_leader_id,
        detail_status=detail_status,
    )


def parse_xk_world(path: Path) -> XKWorld:
    """Fully decodes one ``XK`` file -- see module docstring for the
    complete grammar and sourcing. Raises ``XKParseError`` on anything
    that doesn't match the confirmed shape (an unsupported
    ``format_revision``/``gamevers``, a truncated file, or trailing
    bytes after the final ``TR_End``).
    """

    data = path.read_bytes()
    r = _Reader(data)

    format_revision = r.u16("format_revision")
    if format_revision != SUPPORTED_FORMAT_REVISION:
        raise XKParseError(f"unsupported format_revision {format_revision} (only {SUPPORTED_FORMAT_REVISION} is validated)")
    r.u8("prefix_reserved")
    kingdom_id = r.u16("kingdom_id")
    header = XKHeader(format_revision=format_revision, kingdom_id=kingdom_id)

    globals_ = _read_globals(r)
    if globals_.game_version != SUPPORTED_GAME_VERSION:
        raise XKParseError(f"unsupported gamevers {globals_.game_version} (only {SUPPORTED_GAME_VERSION} is validated)")

    leader_names = _read_leader_names(r, globals_.leader_capacity)

    leader_cards: list[XKLeaderCard] = []
    while r.peek("leaders") != _SENTINEL_END:
        leader_cards.append(_read_leader_card(r))
    r.sentinel("leaders.end", _SENTINEL_END)

    partial_leader_cards: list[XKPartialLeaderCard] = []
    while r.peek("partial_leaders") != _SENTINEL_END:
        leader_id = r.u8("partial_leader.id")
        x = r.u8(f"partial[{leader_id}].x")
        y = r.u8(f"partial[{leader_id}].y")
        partial_leader_cards.append(XKPartialLeaderCard(leader_id=leader_id, coord=HexCoord(x, y)))
    r.sentinel("partial_leaders.end", _SENTINEL_END)

    leader_races = [Race(r.u8(f"leader_races[{i}]")) for i in range(globals_.leader_capacity + 1)]
    leader_states = [r.u8(f"leader_states[{i}]") for i in range(globals_.leader_capacity + 1)]

    king_sex = tuple(
        Sex(chr(value)) if value in (ord("M"), ord("F")) else None
        for value in r.bytes_("DS_89C7", 12)
    )
    treasury = r.s16("DS_8AE7_treasury")
    king_titles = XKKingTitles(
        prefix_by_king_id=_read_king_title_table(r, "king_title_prefixes"),
        suffix_by_king_id=_read_king_title_table(r, "king_title_suffixes"),
    )

    provinces: list[XKProvinceRecord] = []
    while r.peek("provinces") != _SENTINEL_END:
        provinces.append(_read_province(r))
    r.sentinel("provinces.end", _SENTINEL_END)

    features: list[XKFeatureRecord] = []
    while r.peek("features") != _SENTINEL_END:
        features.append(_read_feature(r))
    r.sentinel("features.end", _SENTINEL_END)

    treasures: list[XKTreasureRecord] = []
    while r.peek("treasures") != _SENTINEL_END:
        treasures.append(_read_treasure(r))
    r.sentinel("treasures.end", _SENTINEL_END)

    armies: list[XKArmyRecord] = []
    for army_index in range(globals_.army_count):
        if army_index == 255:
            continue
        armies.append(_read_army(r, army_index))

    discoveries: list[XKDiscoveryRecord] = []
    while r.peek("discoveries") != _SENTINEL_END:
        feature_id = r.u8("discovery.id")
        legacy_word = r.s16(f"discovery[{feature_id}].legacy_word")
        discoveries.append(XKDiscoveryRecord(feature_id=feature_id, legacy_word=legacy_word))
    r.sentinel("discoveries.end", _SENTINEL_END)

    player_tail: dict[str, bytes] = {}
    for field_name, size in XK_PLAYER_TAIL_FIELDS_BEFORE_RELATIONS:
        player_tail[field_name] = r.bytes_(field_name, size)
    diplomatic_relations = tuple(
        DiplomaticRelation(value) for value in r.bytes_("relations_D1D4", 12)
    )
    for field_name, size in XK_PLAYER_TAIL_FIELDS_AFTER_RELATIONS:
        player_tail[field_name] = r.bytes_(field_name, size)
    account_number = r.s16("account_number")
    met_kings_bitmask_low = r.s16("met_kings_bitmask_low")
    for field_name, size in XK_PLAYER_TAIL_FIELDS_TRAILING:
        player_tail[field_name] = r.bytes_(field_name, size)

    r.sentinel("base.end", _TAG_TR_END & 0xFF)
    r.sentinel("base.end.hi", _TAG_TR_END >> 8)

    recruitment_map: list[XKRecruitmentMapCell] = []
    for x in range(globals_.board_left, globals_.board_right + 1):
        for y in range(globals_.board_top, globals_.board_bottom + 1):
            slot1 = r.u8(f"recruit_map[{x},{y}].slot1")
            slot2 = r.u8(f"recruit_map[{x},{y}].slot2")
            recruitment_map.append(
                XKRecruitmentMapCell(
                    coord=HexCoord(x, y),
                    recruit_type_1=MOD_PAT_ORDINAL_TO_ARMY_TYPE.get(slot1),
                    recruit_type_2=MOD_PAT_ORDINAL_TO_ARMY_TYPE.get(slot2),
                )
            )

    liege_extension: XKLiegeExtension | None = None
    secondary_abilities: XKSecondaryAbilityTable | None = None
    secondary_terrain: XKSecondaryTerrainTable | None = None
    home_kingdom: XKHomeKingdomExtension | None = None
    saw_final_end = False
    while not saw_final_end:
        tag = r.u16("extension.tag")
        if tag == _TAG_TR_END:
            saw_final_end = True
        elif tag == _TAG_TR_LLS:
            liege_by_leader_id: dict[int, int] = {}
            while r.peek("TR_LLs") != _TR_LLS_END:
                leader_id = r.u8("TR_LLs.id")
                liege_by_leader_id[leader_id] = r.u8(f"TR_LLs[{leader_id}].lliege")
            r.sentinel("TR_LLs.end", _TR_LLS_END)
            liege_extension = XKLiegeExtension(liege_by_leader_id=liege_by_leader_id)
        elif tag == _TAG_TR_SA:
            flat = list(r.bytes_("TR_SA.spabord", 90))
            secondary_abilities = XKSecondaryAbilityTable(levels_by_ability=[flat[i : i + 6] for i in range(0, 90, 6)])
        elif tag == _TAG_TR_T2:
            secondary_terrain = XKSecondaryTerrainTable(raw=r.bytes_("TR_T2.pt2", 450))
        elif tag == _TAG_TR_HK:
            king_leader_id = r.u8("TR_HK.king")
            shield_record = r.bytes_("TR_HK.shield_record", 190)
            home_kingdom = XKHomeKingdomExtension(king_leader_id=king_leader_id, shield_record=shield_record)
        else:
            raise XKParseError(f"unsupported extension tag {tag}", byte_offset=r.offset - 2)

    if r.offset != len(data):
        raise XKParseError(f"{len(data) - r.offset} trailing bytes after the final TR_End", byte_offset=r.offset)

    return XKWorld(
        header=header,
        globals=globals_,
        leader_names=leader_names,
        leader_cards=leader_cards,
        partial_leader_cards=partial_leader_cards,
        leader_races=leader_races,
        leader_states=leader_states,
        king_sex=king_sex,
        treasury=treasury,
        king_titles=king_titles,
        provinces=provinces,
        features=features,
        treasures=treasures,
        armies=armies,
        discoveries=discoveries,
        diplomatic_relations=diplomatic_relations,
        account_number=account_number,
        met_kings_bitmask_low=met_kings_bitmask_low,
        player_tail=player_tail,
        recruitment_map=recruitment_map,
        liege_extension=liege_extension,
        secondary_abilities=secondary_abilities,
        secondary_terrain=secondary_terrain,
        home_kingdom=home_kingdom,
    )
