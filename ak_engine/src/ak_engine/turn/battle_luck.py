"""Random battle-luck events -- the real, confirmed `AK.EXE`/`AK.OVR`
luck-draw formula (rulebook [6.3] "Summary of factors" closing
paragraph, corroborated by `HostAK/TP/SAY.PAS`'s `_BLuck`/`_CLuck`/
`_CLuck2` narrative hooks and `BLUCK.X2`/`CLUCK.X2`/`CLUCK2.X2`).

**Phase 346 origin, Phase 370 wired in.** Phase 346's own static reverse
engineering of `AK.EXE`/`AK.OVR` (`gw_format`'s own sibling
`battle_engine` key, sourced from `AK.EXE`, `AK.OVR`, `RULES.AK`,
`ADDEND.AK`, `RUMORS.PAS`, `SAY.PAS`, `BLUCK.X2`, `CLUCK.X2`,
`CLUCK2.X2`, `TACTICS.X2`) replaced this module's own earlier,
explicitly-flagged-as-unsourced guess (a 75%-chance column event, a
55%-chance battle-wide event) with the real formula below, but left it
unwired pending a larger rewire of `resolve_battle`'s own win-decision
path. **Phase 370 is that rewire** -- see `turn/battle_resolution.py`'s
own Phase 370 addendum.

The real mechanic draws **one global luck value per side, drawn once
per battle** (`G1` for side 1, `G2` for side 2, each `U[0,1)`), and
**one local luck value per side, drawn fresh for every column** (`L1`,
`L2`, each `U[0,1)`). Side `s`'s own real strength multiplier for a
given column is `R_s = 1 + k*(G_s + L_s)`, where `k` is `0.75` on the
game's own first turn and `1.5` on every turn after -- "because both
random components are halved" on turn 1, per the source's own note.
`R_s` ranges `[1, 2.5)` on turn 1 and `[1, 4)` on turn 2+, i.e. this
real mechanic can **more than double** a column's strength (up to 4x on
turn 2+) -- unlike the old, superseded model, this multiplier is
**always applied**, every column, every battle; there is no "does the
event trigger" gate at all. It's consistent with the rulebook's own
"can as much as double... but most only... 1.5 or less" language once
the *typical* draw (not the extreme tail) is considered.

The source also gives exact discretized narration-index formulas for
the two events this module's own docstring already named:
`BLUCK` (`clamp(1,17, 9+round(9*(G1-G2)))`, drawn once per battle from
the two *global* values only) and `CLUCK` (`clamp(1,39,
20+round(20*(L_selected-L_other)))`, drawn per column from that
column's own *local* values). Both formulas were verified empirically
against the source's own declared probability tables before being
written here: a 2,000,000-draw Monte Carlo simulation of each formula
matches the source's own per-index percentages to within 0.03
percentage points (pure sampling noise at that N), for both the turn-1
and turn-2+ tables. These indices are narrative-only (which prose
template a report would pick) -- they don't gate or scale `R_s` itself.

`draw_global_luck`, `draw_local_luck`, `luck_strength_multiplier`,
`bluck_event_index`, `cluck_event_index`, and `apply_bres_tie_correction`
below are these confirmed primitives, now the sole luck mechanism
`turn/battle_resolution.py resolve_battle` uses.

**Phase 388 addendum -- the actual narration text.** Phase 370 only
wired the *numeric* `bluck_index`/`cluck_index` (see
`turn/battle_resolution.py BattleResult.bluck_index`/
`BattleColumnResult.cluck_index`'s own docstrings) -- neither was ever
rendered into a sentence. AKGEN's own `battle_engine.global_event.
entries`/`local_column_event.entries` supplied a real 17-entry `BLUCK.X2`
and 39-entry `CLUCK.X2` correspondence, plus two confirmed mechanics
this module didn't have yet:

- **The CLUCK narration gate**: a column's local CLUCK text is only
  emitted when the column is "competitive" -- the deterministic
  pre-luck strength ratio (attacker/defender, either direction, since
  `1/0.4 == 2.5`) falls in `[0.4, 2.5]`. Outside that gate local luck
  still affects the column's own combat outcome (`R_s` above is applied
  unconditionally, every column, per Phase 370), it just goes unnarrated.

**Phase 388 correction (Phase 584).** The `BLUCK_ENTRIES`/`CLUCK_ENTRIES`
tuples this addendum originally added were mislabeled: despite being
called "verbatim AKGEN `BLUCK.X2`/`CLUCK.X2` catalog", they were
actually AKGEN's own short internal *event labels* ("mutiny",
"commander or standard falls") -- not the real, renderable prose
sentences, which AKGEN's own structured JSON export never carried. A
byte-faithful third-party reconstruction of the full 162-file prose
corpus (`AKPROSE_reverse_engineering_report.md`, supplied directly by
the user) now supplies the real text for these catalogs --
`BLUCK_TEMPLATE`/`CLUCK_TEMPLATE`/`CLUCK2_TEMPLATE` below replace the
mislabeled tuples, and `render_bluck_event()`/`render_cluck_event()`
now call `report/prose.py render()` properly (`/R`/`{...}`/`/S`
alternation, plus real King/army-name substitution) instead of
returning the bare label string.

**Phase 605 correction -- the real BLUCK2/CLUCK2 trigger.** Phase 584's
own "CLUCK2 fortune reverses" account above (a 33% reversal check on
indices `[13, 27]`, appending a CLUCK2 sentence after CLUCK's own) was
built from AKGEN's own aggregate JSON statistics, not a direct
`SAY.PAS` citation -- and turned out to describe the wrong mechanism.
Direct reading of `SAY.PAS`'s real dispatch code (`_BLuck`/`_CLuck`,
~line 1052-1071) shows both events share one identical selector:

    _BLuck: BEGIN
      batluck:= Rint;
      IF Odd(_px+_py+_attl+_defl+_rphase) THEN
          FD('bluck.x2',S_Batt,1000+batluck)
        ELSE FD('bluck2.x2',S_Batt,1000+batluck);
     END;
    _CLuck: BEGIN
      FD('luckint',S_Batt,7);
      IF Odd(_px+_py+_attl+_defl+_rphase) THEN
          FD('cluck.x2',S_Batt,1000+Rint)
        ELSE FD('cluck2.x2',S_Batt,1000+Rint);
     END;

`BLUCK2.X2`/`CLUCK2.X2` are not a "fortune reverses" follow-up drawn
*in addition to* `BLUCK.X2`/`CLUCK.X2` -- they are the **mutually
exclusive alternate catalog**, selected by the identical parity check
on `_px+_py+_attl+_defl+_rphase` (province x, province y, attacker
leader id, defender leader id, current game phase), for the same
narration index. The `_CLuck2` Pascal case label a few lines below is
an unrelated inline `Say()` two-way branch on `trint > 20` -- it only
*shares a name* with the `cluck2.x2` file `_CLuck` itself already
dispatches to; it never appends anything to `_CLuck`'s own output.

`bluck_cluck_uses_secondary_catalog()` below implements the real
`Odd(...)` parity check (inverted: it returns `True` -- "use the
secondary catalog" -- exactly when the sum is *even*, matching
Pascal's `ELSE` branch). `render_bluck_event()`/`render_cluck_event()`
both gained a `secondary` keyword driven by it; `render_bluck_
narration()`/`render_cluck_narration()` (`report/turn_report.py`) now
require the five real inputs the formula needs and compute it there.
`render_cluck2_event()` is removed (folded into `render_cluck_
event(..., secondary=True)`), and so is `roll_cluck_reversal()` along
with `CLUCK_REVERSAL_INDEX_LOW`/`_HIGH`/`CLUCK_REVERSAL_CHECK_PERCENT`/
`CLUCK2_REVERSAL_PHRASE` -- all four existed only to support the now-
disproven reversal mechanism, so nothing is left as "historical record"
this time (unlike Phase 388's own approximation, this wasn't a
placeholder for missing text -- it was a wrong model of a real,
now-directly-confirmed mechanism, not worth preserving as dead code).

`BLUCK2_TEMPLATE` (Phase 605, from the same byte-faithful reconstruction
as `BLUCK_TEMPLATE`/`CLUCK_TEMPLATE`/`CLUCK2_TEMPLATE`) supplies the
real 17-entry secondary catalog, matching `BLUCK_TEMPLATE`'s own index
range exactly (both keyed 1..17 from the identical `bluck_event_index`).

The one control-byte code these catalogs use, `⟦CTRL-A⟧` ("a/an"),
maps directly onto `report/prose.py render()`'s own already-implemented
`^A` token (`PROSE.TXT`'s own documented marker) -- converted during
transcription, not left as an unrendered placeholder.
"""

from __future__ import annotations

import random

from ak_engine.report.prose import render
from ak_engine.turn.pursuit import draw_pursuit_r01

FIRST_TURN_LUCK_COEFFICIENT = 0.75
LATER_TURN_LUCK_COEFFICIENT = 1.5

# -- Phase 583/584: BLUCK.X2 (whole-battle) narration -- real prose
# (Phase 584), keyed by bluck_event_index's own 1..17 index.
BLUCK_TEMPLATE: dict[int, str] = {
    1: "<'s luck was awful/Rterrible, for ^A nasty/Runfounded rumor that enemy forces were_approaching_from_the_rear/Rhad_destroyed_all_supplies began to sweep through > troops!This gave ['s forces/Rmen ^A huge/Rgreat advantage.",
    2: "The fortunes/Rtides of war turned against <2 when > advance_guard/Rbest_scout_troops fell/Rwalked into ^A {well-laid/Rclever }ambush/Rtrap and were disastrously_routed/Rannihilated.['s horde/Rhost thus gained ^A huge/Rtremendous advantage.",
    3: "A bad omen caused <'s luck to take ^A serious turn for the worse.A dark_cloud/Sdead_elasmosaurus suddenly passed_overhead/Sbobbed_up, frightening the superstitious soldiers.This gave ['s host/Rhorde ^A momentous/Rimportant advantage.",
    4: "<'s fortunes took ^A serious/Rterrible turn for the worse when some of > troops/Sships mutinied/Rrebelled against > strict_discipline/Rdangerous_orders and refused to enter_battle/Rmove_forward.",
    5: "<'s luck seemed/Rappeared to be running_low/Ron_furlough, as the engagement's unexpected/Runforeseen timing/Rfield_of_battle caught > men/Rsoldiers somewhat unprepared.['s men/Rforces thus gained/Robtained ^A significant/Rconsiderable edge.",
    6: '< was unlucky this day/Rtime, for many/Ra_number of > skirmishers/Sscout_ships got_lost/Rbecame_scattered in ^A swamp/Sstorm.[1 thus lucked_into/Rgained ^A significant/Rsmall edge.',
    7: "< was not very/Rat_all lucky/Rfortunate this time/Rday, because a_strong_wind_blew/Rthe_sun_shone {directly }against/Rinto > men's faces/Reyes, giving ['s host/Rmen ^A slight/Rsmall edge.",
    8: "<'s luck wasn't_very_good/Rdidn't_hold_up this time.> superstitious men became unsettled when > priests were unable to properly sacrifice ^A goat/Rbull to the gods/RGreat_Father because they had all been slain/Rstolen by gryphons/Rracketeers.",
    9: '{The battle/Rcontest was ^A fair fight, as }no luck {or mischance }of {any }great/Rnoteworthy significance/Rimportance seemed/Rappeared to affect/Rinfluence the overall {course/Rresult of the }battle/Rengagement before it commenced/Rstarted.',
    10: "as luck would have it, <'s formations/Sships were partially/Rwell concealed/Rhidden by some_rocks/Ra_sudden_mist, giving them ^A slight/Rsmall edge.",
    11: "As_per/RIn_keeping_with <'s usual good luck/Rfortune, [1 was {still }recovering/Rrecuperating from wounds/Rinjuries suffered/Rsustained in an_earlier/Ra_minor duel/Rengagement, and < thus gained/Robtained ^A {considerable }edge.",
    12: "the luck of <'s men/Rforces was running_high/Rgood on/Rfor this {momentous }occasion, for > men were in high/Rgood spirits from ^A recent holiday_feast/Rsuccessful_plundering_expedition, and < thus enjoyed/Rhad ^A significant/Rconsiderable edge.",
    13: "<'s luck/Rfortunes took ^A turn for the better when > scouts/Radvance_guard found/Rlocated {and occupied }a prominent/Rhigh rock/Rgranite outcropping, which proved_useful/Rwas_well_suited as ^A observation_post/Rartillery_site.",
    14: 'Fortunately/RLuckily, < managed/Rwas_able to bribe/Rconvince ^A savage/Rwarlike {native }tribe to harass/Rsurprise [ with their fleet_footed_skirmishers/Sspeedy_war_canoes.With this help/Ralliance, < gained/Robtained ^A clear/Rimportant advantage.',
    15: "{just }before the battle, ^A good/Rfavorable omen appeared/Rmanifested_itself, giving <'s men/Rhost ^A momentous/Rimportant advantage.A giant_eagle/Rgold_dragon flew over > lines, {its grandeur }inspiring/Rinfusing them with {new/Rrenewed }hope.",
    16: "the luck of <'s men/Rforce was good/Rholding, for ^A favorable {(if untrue) }rumor gave <2 ^A huge/Rgreat advantage.The rumor had it that the_gods_themselves/Ra_great_army_of_allied_troops were coming/Rabout to join/Renter_the battle_on their side!",
    17: "To <'s great happiness/Rjoy, ^A {disgruntled/Rgreedy }traitor/Rturncoat from ['s army/Snavy stole/Rmemorized ] battle_plans/Rmarching_orders and sold/Rpeddled them to <2 for ^A small fortune.Naturally, < gained ^A tremendous/Rextraordinary advantage.",
}

# -- Phase 583/584: CLUCK.X2 (per-column) narration -- real prose
# (Phase 584), keyed by cluck_event_index's own 1..39 index.
CLUCK_TEMPLATE: dict[int, str] = {
    1: 'the commander/Rstandard_bearer of = fell, a man who was {be}loved by all{ > men}.Their spirits/Rmorale sank/Rsuffered, and they fought/Rperformed as if they were {only }half-trained/Rthree_feet_tall.',
    2: "the spirits/Rmorale of = suffered greatly/Rterribly when a bad/Rterrible omen occurred/Rreared_its_ugly_head.the troop's/Rmen's favorite/Rbest-loved mascot/Rwhore fell {off_a_chariot/Soverboard }and drowned/Rsank in a_stream/Sthe_ocean.",
    3: '= feigned retreat/Rflight, hoping/Rintending to lure the enemy into more favorable/Rsuitable ground/Swaters.but the ruse/Rtrick backfired when some of the soldiers/Ssquadrons panicked, and = milled/Sfloundered about in confusion/Rdisorder.',
    4: 'the men/Rsoldiers of = were hungry/Rfamished because they had been forced_to_enter/Rbaited_into the fight/Rbattle before they had consumed/Reaten their lunch/Rbreakfast, thus/Rso they joined battle/Rcombat in a weakened/Rsorry state/Rcondition.',
    5: 'a battalion/Ssquadron of = lost_its_way/Rbecame_disoriented in the dust/Smist, {severely/Rsignifcantly }weakening/Rlessening its fighting_strength/Rstriking_power.',
    6: 'some men/Ssquadrons of = had been drawn/Rsiphoned off/Raway by false/Rspurious reports/Rrumors of a raid/Rbattle elsewhere, and entered/Rjoined {the }battle at/Rwith a significant/Rhefty disadvantage.',
    7: '= were held_off/Rthwarted by the{ hastily-constructed/Rstout} earthen_ramparts/Sfloating_boom built_up/Rconstructed by their opponents.= expended a_great_many_soldiers/Rall_their_energy in battering/Rfighting through/Rover it.',
    8: '= were held_up/Rsomewhat_dispersed by rocks_falling_from_a_cliff/Sentangling_seaweed which disrupted_their_formation/Sfouled_their_rudders, putting_them_at/Rsaddling_them_with a considerable/Rsignificant disadvantage.',
    9: 'the men/Ssquadrons of = encountered/Rran_into {some }treacherous/Runpredictable footing/Scurrents and experienced/Rwere_afflicted_with great_disruption/Rconfusion.',
    10: 'a whirlwind/Rstray_gryphon suddenly/Runexpectedly appeared/Rpassed_through, disrupting/Rdisordering {the formation/Rlines of }= and causing/Rcreating {some }confusion/Rapprehension.',
    11: '= bravely/Raudaciously charged their enemy, but became strung_out/Rdisordered and were thrown_back/Rchecked by a well-timed/Rdisciplined, sustained/Reffective countercharge.',
    12: 'many men/Rsoldiers of = were suffering/Rrecovering from hangovers/Rthe_flu, weakening/Rhampering their {fighting }strength/Rspirit significantly.',
    13: "='s commander performed/Rled_his_troops badly/Rpoorly because he had drunk/Ropium-smoked all_through/Rhimself_to_sleep the_previous/Rthat night, not having expected/Rforeseen a battle/Rfight {with the enemy }on_the_morrow/Rso_soon.",
    14: '= {first }had to pass/Rgo through a_ford/Sthe_narrows_between_some_rocks.but their enemy charged/Rattacked before the crossing/Spassage {operation }was completed/Rhalf_made.',
    15: '{some/Ra_few of }the men/Ssquadrons of = fell_to/Rindulged_in looting/Rplundering before the battle/Rcontest was_over/Rhad_been_decided, which_weakened/Rreducing their forces/Rnumbers slightly/Ra_little.',
    16: 'some {soldiers }of = had been drawn_off/Rheld_up by the need to take/Rreduce a {small but }strategically/Rcentrally located/Rsituated fort/Rcastle, so they were considerably/Rfar below {their usual }strength/Rmuster.',
    17: 'the battle standard/Rpennon of = was captured/Rtaken{ in a bold/Rsurprise attack/Rthrust}.Some {men }were_discouraged/Rlost_heart, yet a few {others }redoubled_their_efforts/Rstrove_mightily to regain/Rrecover their {cherished/Rprized }trophy.',
    18: 'the men/Rsoldiers of = had queasy_stomachs/Rlost_sleep because of the{ bad/Rsickening} local_food/Srolling_and_pitching_of_the_decks and became/Rfell slightly ill/Sseasick.They entered/Rwent_into battle at a slight/Rminor disadvantage.',
    19: '= were slightly disrupted/Rdisordered by a_slippery_patch_of_ground/Shigh_swells_which_the_local_rocks_seemed_to_channel_into_them and they entered/Rjoined battle/Rthe_fight at a tiny disadvantage.',
    20: 'the contest/Rfight was ^A{ uneventful/Rstraightforward} slugfest/Rbashing_match {which was }decided/Rdetermined by the courage/Rbravery{ and ability/Rexperience} of the men/Rsoldiers {themselves }in hand-to-hand/Rmelee combat/Rfighting.',
    21: 'the musicians/Rmarching_band of = {bravely/Rcourageously }volunteered/Rasked_permission to lead_the_way/Rmarch_in_the_van, and all {the soldiers/Ssailors }were stirred/Rheartened by their spirited/Rmartial singing/Rmusic.',
    22: 'the spirits/Rmorale of the men/Rsoldiers of = were uplifted/Rraised when one sergeant shouted/Ryelled "Long_live/R"Let\'s_win_one_for the_King/Rour_glorious_Commander!", and the rallying/Rbattle cry was taken_up/Rechoed by all {the men }of =.',
    23: 'a_rumor/Rsome_gossip passed_through/Rwas_circulated_among = that they would receive/Rbe_given an_extra_share_of_loot/Rmedals if they performed_well/Rwon_the_battle, which gave/Rbestowed_upon = the {psychological }advantage/Redge.',
    24: '= were rallied/Rinspired by the exhortations/Rspeech of ^A {brave }officer who shouted/Rbellowed "Do you think_you_can_live_forever/Rwant_to_be_remembered_as_Heroes_or_despised_as_cowards?Charge/SLet\'s_ram_\'em{, brave/Rmy soldiers/Rcomrades}!!!"',
    25: "='s opponents held/Rwere_lined_up_in ^A upslope_position/Rline_along_a_crest.But = charged them, and because there was no counter-charge, = knocked/Rshoved them off the crest/Rhilltop and gained/Rwrested the upper_hand/Radvantage.",
    26: 'the {stone-throwing }{torsion }catapults of = were well/Radmirably situated/Rserved and found/Rhit their mark/Rtargets early{ and often}, {thus }giving = a significant/Rconsiderable advantage/Rartillery_superiority.',
    27: '= were {at first }slow/Rreluctant to join battle, but when a brave little squire/Rcooking_wench picked up a dagger and said "{You cowards, }I\'ll show you how to fight!", they were so ashamed/Rinspired that they determinedly charged into battle.',
    28: '= were held up/Roff by earthen_ramparts/Sa_floating_boom built_up/Rconstructed by their opponents.but = had a_giant_worm/Shammerhead_sharks on retainer to undermine_it/Scrack_it_open, and = broke through quickly, demoralizing them.',
    29: '^A captain/Rofficer of = heroically rushed in{to the battle/Rmelee} and smote/Rstruck down his foes/Ropponents{ left and right}.He{ gave his life/Rall for a glorious/Rgreat cause/Rsovereign, and} inspired all of ={ to a superior performance}.',
    30: '= launched/Rfired_off an_attack/Rtheir_catapult_missiles before the enemy had fully deployed/Rarrived.These attacks dealt_them/Rstaggered_them_with telling/Rsevere blows/Rdamage.',
    31: 'the leader/Rcommander of = paid_off/Rbribed a traitorous prisoner to start a rumor that a hidden detachment was going to attack their baggage_train/Ssupply_ships, and the opposing commander detached valuable troops/Sships to guard it.',
    32: 'scouts/Sfrogmen of = had been captured/Rtrapped before/Rprior_to the battle/Rfight.They were {cruelly }{tortured and }killed and their bodies/Rheads flung_at/Rcatapulted_over =.This drove/Rgoaded = into a berserk/Rmaniacal attacking rage.',
    33: '= immediately turned in/Rto flight when they contacted/Rmet their enemy.But it soon became apparent/Rclear that the panic/Rretreat was {a feigned_one/Rdeception, }a trick to lure their enemy into_overextending_himself/Ronto_more_favorable_ground.',
    34: 'fighting/Rarrayed alongside/Rwith =, and of great assistance/Rhelp, were soldiers/Rmen from a rebellious/Rdisgruntled international_Order/Rlocal_Guild of Knights/RRangers, who happened_to_have/Rused @ as/Rfor their headquarters/Rhome_base.',
    35: '= had bolstered/Rfortified their spirits/Rmorale with ^A drug/Rhallucinogen extracted_from_a_rare_mushroom/Rbought_from_a_narcotics_trafficker, and this gave/Rbestowed_upon = a definite_advantage/Rbig_edge.',
    36: 'after some fighting, the commander of = waved a white flag and offered his sword to the enemy commander.but just as he reached out to accept it, he was treacherously decapitated!at this signal, = charged forward in a surprise attack.',
    37: "= managed/Rwas_able to sneak/Rinfiltrate a detachment/Rspecial_force behind/Raround their enemy's {front }lines, catching_them_in_a_vise/Rpanicking_them and {thus }gaining/Rwresting a tremendous/Rgreat advantage.",
    38: '= concealed strong forces in a_dry_stream_bed/Sthe_false_bottom_of_some_ships and, at a critical/Rcrucial moment in the battle/Rengagement, ruthlessly/Rdaringly ambushed their opponents.this gained {for }= a tremendous/Rgreat {surprise }advantage.',
    39: '^A wonderful/Rawe-inspiring omen appeared/Rmanifested_itself to = in the form of a rainbow/Rfalcon, alighting/Rdescending upon their battle-standard/Rcaptain.Each/REvery man {took heart, and }seemed/Rwas_inspired to fight as_two/Rlike_a_giant!',
}

# -- Phase 584: CLUCK2.X2 -- real text, keyed by the same cluck_index.
# **Not** a "fortune reversed itself" follow-up to CLUCK.X2 -- see
# module docstring's own Phase 605 correction: this is the real,
# mutually exclusive secondary catalog for the same event.
CLUCK2_TEMPLATE: dict[int, str] = {
    1: 'a mutiny/Rrevolt broke_out_among/Rconvulsed = when a false_report/Rrumor spread/Rwas_circulated that they would_not_be_paid_this_year/Rwere_to_be_used_as_cannon_fodder, thus/Rso they were of_little/Rnot_of_much use.',
    2: "='s luck turned ugly/Rhorrible!a stray_tornado/Rmeteor crashed_into/Rfell_upon = and crushed/Rkilled many of_them/Rsoldiers.",
    3: 'some soldiers/Ssquadrons of = suddenly encountered/Rran_into a stone_wall/Sreef and had/Rwere_forced to march/Smaneuver around it, placing/Rsetting them at a daunting/Rsevere disadvantage.',
    4: '= carelessly stumbled/Rblundered into a nest/Sherd of booby_traps/Sstray_sea_monsters and lost some irreplaceable/Rof_their_best front-line/Rbattle-hardened troops/Ssquadrons.',
    5: '= became disorganized/Rdispersed when they ran_into/Rwere_surprised_by a stray/Rwandering herd_of_buffaloes/Sleague_of_whales, putting_them_at/Rsaddling_them_with a severe/Rsignificant disadvantage.',
    6: 'the commander/Rregimental_band of = was flattened/Rsquashed by a boulder/Rcask_of_acid thrown/Rhurled from a catapult/Rmangonel, which greatly/Rterribly disheartened/Rdeflated_the_spirits_of the troops/Rsoldiers.',
    7: 'the cowardice/Rcraven_fear of a {single }soldier/Ssailor worked/Rwent against =.They were thrown into disarray/Rdisorder when he {panicked and }ran/Sjumped_overboard, shouting "{The_battle/RIt is lost/Rhopeless!}We\'re all {of us }doomed/Rcooked!"',
    8: '= had to cross_a_ditch/Snegotiate_some_treacherous_currents, which disrupted/Rdisordered {the formation/Rlines of }= and caused/Rcreated {some }confusion/Rpanic.',
    9: '= bravely/Raudaciously charged their enemy, but became strung_out/Rdisordered and were thrown_back/Rchecked by a well-timed/Rdisciplined, sustained/Reffective countercharge.',
    10: '{some soldiers of }= were_slowed_down_by/Rreceived_slight_wounds_from some_thorny_underbrush/Sa_school_of_flying_fish_which_zipped_haphazardly_amongst_them, and found themselves feeling drained/Rtired by the time they entered/Rjoined battle.',
    11: '= advanced/Rmoved_forward confidently/Rwith_alacrity, but were thrown_into_disarray/Rsurprised_and_disrupted when a {previously }concealed/Rhidden battery_of_catapults/Rdetachment_of_slingers suddenly/Runexpectedly opened fire/Rup.',
    12: 'orders/Rsignals from the higher-ups/Rgeneral_staff to = were misunderstood/Rincorrectly_deciphered and some formations/Runits collided/Rbecame_entangled with others/Reach_other, causing/Rresulting_in some disorder/Rdisruption.',
    13: '= were suprised to find that their brand-new weapons had ^A {alarming }tendency to break {in half }when they struck their opponents, {no doubt }because of the shoddy work of the {fly-by-night }arms/Rdefense contractor who supplied/Rmade them.',
    14: 'some/Rthe soldiers/Ssquadrons of = were held_up_by/Rdelayed_by a_muddy_field/Shaving_to_navigate_some_treacherous_waters.',
    15: '{some/Ra_few of }the soldiers/Ssquadrons of = got_lost/Rstrayed_away in a patch_of_fog/Rsudden_mist, which weakened/Rwhittled_down their forces/Rnumbers slightly/Ra_little.',
    16: '= charged/Smoved forward energetically/Rwith_great_zeal, but neglected/Rfailed to take_into_account/Rconsider the distance_to_their_enemy_lines/Runusually_hot_weather.Their charge had little effect/Rimpact, except to tire them considerably.',
    17: 'some/Ra_few mischievous/Rmischief-making leprechauns/Rhalflings angered/Rdisrupted = with their prankster_spells/Rstone-throwing and had to be chased_off/Rscooted_away{ by a detachment/Rsquadron of soldiers/Spatrol_boats}.',
    18: 'a few soldiers in/Rof = panicked/Rturned_yellow{ and ran/Shid}; however, they were {quickly/Rsummarily }cut_down/Rexecuted by {roving }security guards/Rpolice, and the battle continued/Rproceeded with minimal/Rlittle disruption/Rloss_of_time.',
    19: "='s commander {cleverly }unleashed/Rreleased a herd of pink-painted elephants/Swhales to make his opponents believe/Rimagine they were going insane/Rcrazy, but the ruse/Rtactic had little/Rno effect except to amuse_them/Rlighten_their_spirits.",
    20: '= expected/Rseemed to have the upper_hand/Radvantage because they had constructed_prepared_defenses/Rpoisoned_their_weapons, but were suprised/Rchagrined to discover/Rfind_out that their opponents/Renemy had done the same{ thing}.',
    21: 'the clever/Rruthless commander of = hit_upon/Rthought_of ^A idea/Rnew_tactic.He dragged/Rrecruited some/Ra_few monks/Rpeasants out of a nearby/Rlittle village/Rmonastery and lined_them_up/Rused_them as cannon_fodder/Rhuman_shields.',
    22: '= obtained/Rgot a_small_advantage/Rthe_upper_hand when they used/Rordered their {own }trumpeters/Rdrummers to disrupt/Rdrown_out the signal{ call}s of their enemy.',
    23: "the/Rsome soldiers of = noticed {the presence of }^A encampment_of_trollops/Streasury_ship behind their opponents{' lines}, so they valiantly/Rlustily redoubled/Rconcentrated their efforts to break/Rsmash through{ to victory}.",
    24: "= were fearful_of_defeat/Rbeing_steadily_driven_back.but then ='s commander/Rregimental_high_priest picked_up/Rwielded a/R> pike/Rsword and {personally }held_off_all_assailants/Rjoined_the_battle, and = rallied admirably/Rfiercely.",
    25: '= found_a_walled_chateau/Sformed_a_crescent_of_ships to rally/Rcenter_their_position around and gained/Robtained the upper_hand/Redge.',
    26: 'the commander of = knew that his opponents were from a race who were especially vain about their appearance/Rsex_appeal, so he ordered/Rtold his soldiers to strike at their faces/RPeerless_Parts.this strategem/Rtactic caused much panic/Rterror!',
    27: '= carried/Rheld_aloft a statue/Rgreat_battle-standard they had made to represent/Rhonor all the ideals/Raccomplishments of their King{dom}, and whenever the battle/Rfight went wrong/Rbadly they rallied around it admirably/Rwith_great_determination.',
    28: 'when a_captain/Rthe_commander of = spotted/Rnoticed a weak point/Rlink in the enemy line, he quickly assembled a{n elite} force of picked soldiers/Rveterans to break/Rcut_their_way through it, and met_with/Rachieved_some {initial }success.',
    29: 'the commander of = decided/Rresolved on a charge.He moved to the fore/Rfront and shouted/Ryelled "Crush/R"Smash them/Rthe_cowards!{Ride/SSend them down/Sunder!}" and {with_a_great_roar/Rin_a_berserk_rage, }{all of }= charged valiantly/Rbravely.',
    30: '^A captain/Rofficer of = noticed/Rperceived ^A gap/Ropening in the enemy lines which had opened/Rappeared when they moved_around/Rskirted a large/Rwide rock outcropping/Rformation.{By }charging into the gap, = gained a considerable advantage.',
    31: 'the leader/Rcommander of = engaged his opposite number in single/Rpersonal combat.{After a prolonged/Rhard-fought duel, }he unhorsed/Sdisarmed him{ and buried his spear/Rsword in his heart/Rbrain}, and = exultantly/Rjubilantly charged ahead.',
    32: "= sprayed_oil/Rsquirted_tallow on their enemy's weapons/Sdecks to make them slip_off/Ralmost_impossible_to_handle.",
    33: 'the supreme_commander/Rarmy_general appeared/Rcondescended to personally/Ractually lead/Rride_with {the troops/Ssquadrons of }= at/Rin the front{ lines}, inspiring/Rrallying them to a {truly }surpassing/Rexcellent effort/Rperformance.',
    34: '= had coated/Rtreated their weapons/Rswords with a poison extracted_from_a_rare_local_plant/Rbought_from_a_shadowy_master-assassin.this gave/Rbestowed_upon = a definite_advantage/Rbig_edge.',
    35: "= used wide-headed/Rscythed arrows/Rcatapult_missiles to cut_down/Rslash_apart the enemy's catapult_engines/Srigging.",
    36: 'the commander of = had_infiltrated/Rsneaked a {hemp-smoking, }fanatical{ly religous} assassin behind enemy lines.he killed/Rmurdered the opposing {regimental }commander in a {frenzied }{headlong }rush, then was_himself_killed/Rcommitted_suicide.',
    37: 'a wonderful/Rfantastic omen {greatly }inspired/Rheartened =.a flight_of_silver_dragons/Rcloud-giant_castle flew/Rfloated over, and their magic/Rmystic mists/Rwinds settled_upon/Rbreathed_new_life_into =.',
    38: "='s opponents were overjoyed when a {beautiful }golden_eagle/Swhite_albatross flew_overhead/Salighted_on_their_fleet, a wonderful omen.but their joy turned to despair when ^A boorish/Ridiotic soldier shot/Rkilled the bird (a SURE sign of doom!)",
    39: '= was struck/Rdusted by a {cosmic }storm/Rshower of magic{al} {star}dust{ from a disintegrating/Rfalling meteor/Rcomet made of/Rfrom luckstone/Rmithril,} and = fought/Rshone with enchanted_fury/Rmagical_elan{ for the entire/Rrest_of_the battle}!',
}

# -- Phase 605: BLUCK2.X2 -- the real mutually-exclusive secondary
# whole-battle catalog (see module docstring's own Phase 605 correction
# for why this replaces BLUCK.X2 only sometimes, not "on top of" it),
# keyed by the same bluck_event_index's own 1..17 index.
BLUCK2_TEMPLATE: dict[int, str] = {
    1: "the fortunes/Rtides of war took ^A terrible/Rawful turn {for the "
    "worse }against <2 when > forces were trapped/Rcaught in ^A "
    "{narrow }canyon/Schannel and had to fight/Sram their_way_past/"
    "Rthrough prepared/Rhastily-constructed defenses/Robstacles.",
    2: "<'s luck was awful/Rterrible!a thundercloud_formed/Rstorm_"
    "passed overhead and > vanguard/Sflag_squadron was struck_by_a_"
    "lightning_bolt/Rdrenched_by_a_dark_thundershower.This bad/"
    "Rterrible omen completely disheartened/Rdemoralized > forces/Rmen.",
    3: "< was out_of_luck/Runfortunate{ this time}, for/Rbecause ^A "
    "giant_worm/Sgiant_sea_monster {suddenly/Rabruptly "
    "}{rose/Rbroke_the_surface and viciously }attacked from below/"
    "Sthe_deep, and < {thus }had to fight on_two_fronts/Rtwo_"
    "battles{, not one}.",
    4: "< seemed lucky, for < was able to convince ^A native_tribe/"
    "Rancient_sphinx to aid/Rfight_for > cause.But > luck turned "
    "sour/Rbad when [ bribed <'s {new }recruit/Rally to switch_"
    "sides/Rturn_traitor{, giving/Rwhich_gave [ a clear/Rgreat "
    "advantage}.",
    5: "^A bad/Runfavorable omen appeared/Rmanifested_itself, which{ "
    "of course} dealt a severe/Rtelling blow to <'s fortunes/"
    "Rhopes.{it seems that }<'s mount was shot down/Rand_killed "
    "from_under_<2/Rwhile_<_was_giving_a_speech.",
    6: "< was unlucky/Rrunning_low_on_luck, for < had_been_unable_to/"
    "Rcouldn't find/Rlocate ^A suitable/Rprotected encampment/"
    "Sharbor to weather_a_storm/Rrest_>_troops{ the previous day}, "
    "thus > men/Sships were in poor/Rdismal shape/Rcondition.",
    7: "< was unlucky this day/Rtime, for/Rbecause {> }{food "
    "}supplies/Rrations were running_low/Rdwindling and {some of }> "
    "men/Rtroops had/Rwere_forced to fight_on_empty_stomachs/Rgo_"
    "hungry.",
    8: "< had used/Rconducted ^A night/Rlong_flanking march/"
    "Smaneuver to try to suprise_[/Rcatch_[_off_guard.but the "
    "gambit/Rruse was_detected/Rfailed, and its only effect was to "
    "tire/Rdemoralize <'s troops/Rsolders{ considerably/"
    "Ralarmingly}.",
    9: "{the battle/Rcontest was ^A fair/Reven fight, as }no luck "
    "{or misfortune }of {any }great/Rnoteworthy significance/"
    "Rimportance altered/Raffected the {general course of the "
    "}battle/Rengagement.",
    10: "the two/Ropposing armies/Sforces raced/Rstrived_mightily "
    "for_the_high_ground/Sto_be_upwind, and < obtained an_advantage/"
    "Rthe_edge by getting/Rarriving there first/Rbefore_the_enemy.",
    11: "as_luck_would_have_it/Rluckily_for_<2, some/Ra_force_of "
    "{mischievous/Ropportunistic }bandits/Spirates ambushed/Rraided "
    "['s rearguard/Rsupply_elements, giving_<2/Rso_<_had the_edge/"
    "Ra_clear_advantage{ over > opponent}.",
    12: "[ and < had both persuaded/Rbribed some {primitive/"
    "Rfeuding }native{ tribe}s to fight_for/Raid them, but "
    "fortunately/Rluckily for <2, > allies/Rrecruits were better/"
    "Rmore_adequately trained/Rarmed{ for their skirmishing/"
    "Rguerilla duties/Rrole}.",
    13: "< allowed a prisoner to overhear/Rbelieve that "
    "reinforcements/Rallies would soon come to double/Raugment > "
    "forces, then gave him a chance to escape.The prisoner reported "
    "the grim news to [, and [1 deployed ] forces with excessive/"
    "Rtoo_much caution.",
    14: "in this battle, < had stolen_a_march/Rconducted_a_swift_"
    "night_attack on [ and was {quite }lucky/Rfortunate to catch_"
    "the_defenders_napping/Rgain_a_positional_advantage.",
    15: "< approached the doddering/Rgullible local commander under "
    "a flag of truce and glibly told him that the war was over, and "
    "under the treaty's terms, a large bridge/Sharbor was to be "
    "turned_over/Rleft_unguarded, thus capturing this crucial "
    "bridge/Sharbor.",
    16: "< gambled/Rtook_a_chance on infiltrating/Rsending {some "
    "}scouts/Sfrogmen behind enemy/Rthe lines to set_fire_to/"
    "Rsabotage their supply/Rarmament wagons/Sships, and the "
    "{brash/Rdaring }scheme/Rplan succeeded brilliantly/Rcompletely.",
    17: "< was upslope/Supwind of/Rfrom [.Finding/RHappening_to_"
    "have some/Ra_few rusty_wagons/Sold_ships, < ladened/Rloaded "
    "them with flaming pitch/Roil and sent them rolling/Sdrifting "
    "towards [, whose forces were totally_disrupted/Rlargely_"
    "scattered.",
}

CLUCK_NARRATION_GATE_LOW = 0.4
CLUCK_NARRATION_GATE_HIGH = 2.5

# -- Phase 587: LUCKINT.X/LUCKINT2.X -- bridge phrases used alongside
# BLUCK/CLUCK/CLUCK2, real prose from the same byte-faithful 162-file
# reverse-engineering pass as Phases 578-586. Both are dispatched from
# the exact same `_CLuck` handler CLUCK.X2/CLUCK2.X2 already are
# (`SAY.PAS:1068 _CLuck FD('luckint',S_Batt,7)`, immediately before the
# `SAY.PAS:1070-1071` CLUCK.X2/CLUCK2.X2 dispatch; `SAY.PAS:1081-1082
# trint FD('luckint2',S_Batt,7)` alongside a separate `trint`-driven
# CLUCK2.X2 call) -- both real, sourced connector phrases for that
# narration, but the *exact* join order/spacing between them and
# BLUCK_TEMPLATE/CLUCK_TEMPLATE/CLUCK2_TEMPLATE isn't confirmed from
# the available source citations alone, so no `render_*()` wrapper
# threads them into `render_bluck_narration()`/`render_cluck_narration()`
# here -- kept as sourced, unwired data, the same posture `models/
# office.py`/`turn/encounter.py`'s own Phase 578/581 additions took.
# Each `dex=7` call (below 100) is dispatched via `FD`'s own normal
# random-cycling branch, not a computed index -- these are genuinely
# random flavor picks among their own small catalog, unlike `Rint`.
# LUCKINT.X's own trailing `_` (space) leaves each entry ready for
# direct concatenation with whatever sentence follows, the same bare-
# precursor-clause shape `QUEST_BUT_THEN_TEMPLATE`/`DUEL_NO_EXCUSE_
# TEMPLATE` (`report/turn_report.py`) already established.
LUCKINT_TEMPLATE: dict[int, str] = {
    1: "In this engagement/Rmatch,_",
    2: "Here,_",
    3: "On this field/Rbattleground,_",
    4: "In this sector/Rarea,_",
}

LUCKINT2_TEMPLATE: dict[int, str] = {
    1: "{But }then the tide {of battle }turned/Rreversed.",
    2: "But the battle/Raffair was not yet over/Rdone.",
    3: (
        "But might/Rwould victory_yet_be_snatched_from_the_jaws_of_defeat/"
        "Rdefeat_now_be_snatched_from_the_jaws_of_victory?"
    ),
    4: "The {ongoing }battle/Rstruggle went_on/Rblazed with a {terrible/Rmurderous }fury/Rfrenzy.",
}


def draw_global_luck(rng: random.Random) -> tuple[float, float]:
    """G1, G2: each side's own global luck draw, made once per battle."""

    return rng.random(), rng.random()


def draw_local_luck(rng: random.Random) -> tuple[float, float]:
    """L1, L2: each side's own local luck draw, made fresh for every column."""

    return rng.random(), rng.random()


def luck_strength_multiplier(g_side: float, l_side: float, *, is_first_turn: bool) -> float:
    """R_s = 1 + k*(g_side + l_side) -- side `s`'s own real strength
    multiplier for one column, `k` = 0.75 on the game's own first turn
    (`[1, 2.5)`), 1.5 on every turn after (`[1, 4)`)."""

    coefficient = FIRST_TURN_LUCK_COEFFICIENT if is_first_turn else LATER_TURN_LUCK_COEFFICIENT
    return 1 + coefficient * (g_side + l_side)


def bluck_event_index(g1: float, g2: float) -> int:
    """The whole-battle BLUCK narration index, drawn once per battle from
    the two global luck values alone: `clamp(1,17, 9+round(9*(g1-g2)))`
    -- 1-8 favor side 2, 9 neutral, 10-17 favor side 1."""

    return max(1, min(17, 9 + round(9 * (g1 - g2))))


def cluck_event_index(l_selected: float, l_other: float) -> int:
    """One column's own local CLUCK narration index:
    `clamp(1,39, 20+round(20*(l_selected-l_other)))` -- 1-19 negative for
    the selected unit, 20 neutral, 21-39 positive."""

    return max(1, min(39, 20 + round(20 * (l_selected - l_other))))


def apply_bres_tie_correction(bres: int, running_total_before: int, rng: random.Random) -> int:
    """Phase 933: the real exact-zero summed-`BRES` tie-break -- **not**
    an abstract "flip a coin for each side" decision (Phase 347's own
    `break_bres_tie`, superseded outright by this function, see its own
    replaced docstring in git history), but a direct *correction of the
    last column's own `BRES` value*, confirmed by a user-supplied
    byte-level disassembly of `AK.OVR` (`BRES.md`/`BRESOK.md`, raw
    `[0x500A,0x5307)`, address `0x511E`-`0x5124`).

    The real Pascal (`BRES.md`'s own reconstruction, addresses as
    above): only ever runs for the battle's *last* column (`colonna =
    larghezza`), and only when this column's own already-clamped `BRES`
    would make the running battle-wide total exactly zero:

    ```pascal
    while (colonna = larghezza) and (totale + bres = 0) do begin
      prima := R01;
      seconda := R01;
      bres := bres + seconda - prima;
    end;
    ```

    `R01` (`turn/pursuit.py draw_pursuit_r01`, the same routine
    `BRES.md` itself identifies as shared with the already-confirmed
    Pursuit catch test, `2E5A:246D`) is a single fair `0`/`1` coin, so
    `seconda - prima` is `-1`/`0`/`+1` at `25%`/`50%`/`25%` each -- the
    loop repeats only on the `50%` no-op case, terminating with
    probability 1. **No second clamp is applied after this correction**
    (`BRES.md`'s own explicit note) -- the corrected value can land
    outside `-5..+5` (e.g. a `+5` column corrected to `+6`), read as-is
    by every downstream consumer of this column's own `BRES` (the
    quality-loss test in `turn/combat.py direct_destruction_
    probability`, the narration index, `attacker_won`), not just the
    battle-wide winner decision.

    Since `resolve_battle`'s own `line_length` is always `>= 1` (an
    empty side is rejected outright, see this module's own caller), the
    battle's last column always exists, so this correction -- not any
    separate coin-flip abstraction -- is what actually prevents
    `resolve_battle` from ever reporting an exact-zero `total_bres`:
    the `while` loop above can only exit once `running_total_before +
    bres != 0` holds, by construction. `running_total_before` is the
    sum of every *earlier* column's own (already-settled) `BRES` --
    `bres` is this last column's own value, corrected in place and
    returned; the caller still has to add it to its own running total
    itself, exactly as the Pascal's own `totale := totale + bres` does
    right after this loop.
    """

    while running_total_before + bres == 0:
        prima = draw_pursuit_r01(rng)
        seconda = draw_pursuit_r01(rng)
        bres += seconda - prima
    return bres


def bluck_cluck_uses_secondary_catalog(
    province_x: int, province_y: int, attacker_leader_id: int, defender_leader_id: int, phase: int
) -> bool:
    """The real, shared BLUCK/CLUCK catalog-pair selector (Phase 605
    correction -- see module docstring). `SAY.PAS`'s `_BLuck`/`_CLuck`
    both gate on the identical `Odd(_px+_py+_attl+_defl+_rphase)`
    expression: the odd-sum case draws from the primary catalog
    (`BLUCK.X2`/`CLUCK.X2`), the even-sum case from the secondary one
    (`BLUCK2.X2`/`CLUCK2.X2`). Returns ``True`` for the secondary
    (even-sum) case, i.e. the logical inverse of Pascal's own `Odd(...)`.
    """

    return (province_x + province_y + attacker_leader_id + defender_leader_id + phase) % 2 == 0


def render_bluck_event(
    index: int, attacker_name: str, defender_name: str, rng: random.Random, *, secondary: bool = False
) -> str:
    """The whole-battle BLUCK narration sentence for `bluck_event_index`'s
    own 1..17 index (real `BLUCK.X2` prose, Phase 584). `<`/`<2` are the
    attacker (side 1, the one whose own luck is being narrated), `[`/`[1`
    the defender (side 2) -- the same convention `report/turn_report.py
    render_battle_winner()` already uses for `_WINNER_TEMPLATES`.
    `secondary` (Phase 605) picks `BLUCK2_TEMPLATE` instead -- see
    `bluck_cluck_uses_secondary_catalog()`.
    """

    values = {
        "<": attacker_name,
        "<2": attacker_name,
        ">": f"{attacker_name}'s",
        "[": defender_name,
        "[1": defender_name,
        "]": f"{defender_name}'s",
    }
    template = BLUCK2_TEMPLATE if secondary else BLUCK_TEMPLATE
    return render(template[index], values, rng=rng)


def render_cluck_event(index: int, army_name: str, rng: random.Random, *, secondary: bool = False) -> str:
    """One column's own local CLUCK narration sentence for
    `cluck_event_index`'s own 1..39 index (real `CLUCK.X2` prose, Phase
    584). `=` is the affected army, the same marker `report/
    turn_report.py render_column_clash()` already uses for the margin
    templates. `secondary` (Phase 605) picks `CLUCK2_TEMPLATE` instead
    -- see `bluck_cluck_uses_secondary_catalog()`; this replaces the
    former separate `render_cluck2_event()`.
    """

    template = CLUCK2_TEMPLATE if secondary else CLUCK_TEMPLATE
    return render(template[index], {"=": army_name}, rng=rng)


def column_narration_eligible(attacker_strength: float, defender_strength: float) -> bool:
    """A column's local CLUCK text is only narrated when the deterministic
    pre-luck strength ratio is "competitive" -- AKGEN's own confirmed
    gate, `[0.4, 2.5]` (Phase 388) -- otherwise local luck still affects
    that column's own combat outcome (Phase 370's `R_s` is applied
    unconditionally) but goes unnarrated. Symmetric: `a/d` and `d/a` land
    on the same pass/fail outcome since `1/0.4 == 2.5`."""

    if attacker_strength <= 0 or defender_strength <= 0:
        return False
    ratio = attacker_strength / defender_strength
    return CLUCK_NARRATION_GATE_LOW <= ratio <= CLUCK_NARRATION_GATE_HIGH
