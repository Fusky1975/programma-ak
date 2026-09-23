"""Kingdom-level "Discoveries of the Sages" (permanent per-kingdom bonuses).

``HostAK/TP/CTBOTH.PAS``'s ``discovery`` enum (~line 743, 64 members) plus
``HostAK/TP/CTME.PAS``'s own ``dname`` table (~line 4, a *different* file
from ``CTBOTH.PAS`` -- found continuing to mine the wider Pascal source the
way Phases 79-90 found their own real data; a prior phase's search for a
"dname"/"_discov" pair came up empty because it only searched
``CTBOTH.PAS`` itself).

**Confirmed real and used** via ``REPORTS.PAS``'s own "Discoveries of the
Sages" kingdom report section (~line 325-348):

```pascal
FOR dval:= 20 DOWNTO 0 DO FOR d:= fix0 TO crunch27 DO
  IF discval[d] = dval THEN IF dk[d] THEN BEGIN
    ...
    WRITE(playfile,'  ',dname[d],' ':25-Length(dname[d]),'(');
    CASE d OF
      fix0..fix9: WRITE(playfile,'+1 skill in ',anoun[ability(ord(d) Shr 1)]);
      wreck0..wreck9: WRITE(playfile,'+1 skill in ',anoun[ability((ord(d)+10) Shr 1)]);
      bild10..bild43: WRITE(playfile,'Anti-spell: ',spname[spell(ord(Skeletal_Army)+ord(d)-ord(bild10))]);
      crunch0..crunch27:WRITE(playfile,'+',1+((ord(d)-ord(crunch0)) and 3),'% revenue');
    END;
```

This confirms four distinct effect categories, positional with the enum's
own four member groups (``fix0``-``fix9``, ``wreck0``-``wreck9``,
``bild10``-``bild43``, ``crunch0``-``crunch27``):

- **Ability skill bonus** (``fix0``-``fix9``, ``wreck0``-``wreck9``, 20
  discoveries, two per ``Ability``): "+1 skill in <ability>", covering
  ``Ability`` ordinals 0-4 (``fix``) and 10-14 (``wreck``) -- ordinals 5-9
  (White/Necromancy/Elemental/Psychic/Illusion) have no matching
  discoveries in either group.
- **Anti-spell ward** (``bild10``-``bild43``, 16 discoveries): "Anti-spell:
  <spell name>", covering ``Spell`` ordinals 4-19 (``SKELETAL_ARMY``
  through ``INVISIBILITY`` -- the "first four spells" block of each of the
  five Magical ``Ability``s, per ``models/enums.py Spell``'s own
  docstring, minus the White ability's own first two).
- **Revenue bonus** (``crunch0``-``crunch27``, 28 discoveries): "+X%
  revenue", ``X`` cycling ``1,2,3,4`` by ``(ordinal-in-group) mod 4``.

``discval`` (``CTBOTH.PAS`` ~line 766, also confirmed real via the same
report loop) is a pure *display-order* key -- the loop above prints
discoveries in descending ``discval`` order, grouped by identical value --
not a difficulty/point score with any other confirmed meaning. Not
modeled here since it has no use outside that one print loop.

**Phase 93 addition**: the user supplied ``Discovery.txt``, a design
document giving the full flavor/mechanics paragraph for all 64
discoveries, in the same order as the Pascal ``discovery`` enum. Every
single entry cross-checks exactly against the ``CASE`` statement quoted
above -- all 20 ability-bonus paragraphs name the same ``Ability`` the
Pascal formula computes, and all 16 anti-spell paragraphs describe an
effect on the same ``Spell`` the Pascal formula computes -- so
``DISCOVERY_ABILITY_BONUS``/``DISCOVERY_ANTISPELL_TARGET`` below are
doubly confirmed, not a guess from either source alone.

One real discrepancy surfaced comparing the 28 revenue paragraphs against
the Pascal formula's own 1-2-3-4 cycle: ``SPECTACLES`` is the 21st
``crunch`` discovery (``crunch20``), for which
``1+((ord(d)-ord(crunch0)) and 3)`` computes ``1%``, but ``Discovery.txt``
states "raise your revenue by an average of 2% each gameturn." Every
other of the 28 revenue entries matches the formula exactly. This is kept
as an explicitly documented discrepancy, not silently resolved either
way: ``DISCOVERY_REVENUE_BONUS_PERCENT`` below follows the Pascal
formula (the actual executable behavior of the original engine), and this
one exception is called out at its own dict entry.

Applying any of these bonuses to actual gameplay (how the ability bonus
stacks with ``LeaderState.skills``, how the anti-spell wards actually
modify ``turn/cast_execution.py``) was originally left to a real
follow-up phase -- this phase only models the confirmed *data*, matching
how ``models/office.py``/``models/weapon.py`` (Phases 81/83) started with
vocabulary before any mechanical wiring. **Phase 268 closes the
acquisition mechanic (`KingdomState.discoveries`, Phase 266) and, since
Phase 268, the revenue-bonus half of this list**: `Inv_Bonus` and the
real per-discovery FINANCES report line, both below.

**Anti-spell-ward wiring status (re-audited during a later cover-to-cover
pass, since this note was never revisited as each ward landed): 9 of the
16 `DISCOVERY_ANTISPELL_TARGET` entries are now real, wired mechanics --
each via its own ad-hoc `Discovery.X in kingdom.discoveries` check at its
own real trigger site, not through `DISCOVERY_ANTISPELL_TARGET` itself
(which has no consumer anywhere -- it exists purely to pair a Discovery
with the `Spell` its own flavor text names, for
`discovery_effect_description()`'s report line).** Wired: `OSTEOPATHIC_
GERM_WARFARE` (`turn/battle_orchestrator.py`, weakens the opponent's own
Skeletal Army), `HIDDEN_TATTOOS` (`turn/cast_execution.py`, Kill Enemy),
`PENICILLIN` (`turn/cast_execution.py`, Plague), `GIANT_FAN` (`turn/
cast_execution.py`, Tornado), `REINFORCED_CONCRETE` (`turn/cast_
execution.py`, Earthquake's flat-3-gold reduction), `ANALYTICAL_
PSYCHOLOGY` (Charm -- wired across `turn/cast_execution.py`/`challenge_
execution.py`/`practice_execution.py`/`turn_processor.py`/`search_
execution.py`, the most heavily-wired of the 16), `PROPAGANDA_
MEGAPHONES` (`turn/cast_execution.py`, Oratory), `OBSERVATION_BALLOONS`
(`turn/battle_orchestrator.py`, Phantasmal Armies), `HAND_HELD_RADAR`
(`turn/exploration.py`, Hide Feature). **Phase 881**: `INFRARED_GOGGLES`
(Invisibility) is now wired too -- `turn/encounter.py INFRARED_GOGGLES_
HIT_CHANCE_MULTIPLIER`, checked at the same two real Invisibility-cast
sites (`turn/challenge_execution.py`/`turn/search_execution.py`) as the
`AdvancedAbility.WITCHSIGHT_TALENT`/Crystal-of-True-Seeing carve-outs --
a weaker, partial override (20% hit-chance reduction instead of the
ordinary 50%), not a full bypass like those two. Deliberately NOT
threaded into `weapon_defensive_hit_multiplier()`'s own Invisible-Sword
branch (that function runs at `Combatant`-construction time, with no
opponent known yet to check a Discovery against) -- a real, separate,
smaller residual. **Phase 882**: `ASBESTOS_CLOTHING` (Fireball) is now
wired too -- `turn/encounter.py ASBESTOS_CLOTHING_DAMAGE_MULTIPLIER`,
reducing `roll_fireball_damage()`'s own rolled damage by 67% for a
target whose own Kingdom holds it, checked at the same two real
Fireball-cast sites (`turn/challenge_execution.py`/`turn/search_
execution.py`) as the submarine-monster immunity. **Phase 883**:
`LEAD_LINED_HELMET` (Psychic Blast) is now wired too --
`turn/encounter.py LEAD_LINED_HELMET_STUN_ROUNDS_RANGE` (1-2 instead
of the ordinary 2-5), checked at the same two real Psychic-Blast-cast
sites for a target whose own Kingdom holds it. **Phase 884**:
`ARTIFICIAL_ORGANS` (Hand of Death) is now wired too -- `turn/
encounter.py roll_hand_of_death_damage()`'s own `target_has_
artificial_organs` flag zeroes the caster's own squeeze damage for a
target whose own Kingdom holds it, checked at the same two real
Hand-of-Death-cast sites. Unlike full immunity, the channel itself
still runs (the victim's own halved-hit-chance Melee counter-attack
can still end it) -- only the damage is zeroed. The Discovery's own
second clause ("archery can be used, but not spells") is deliberately
NOT wired: Hand of Death's own baseline "victim cannot cast spells nor
shoot with a bow" restriction is itself never threaded into `Combatant.
blocked_from_cast_and_archery` for this spell in either real call site
(confirmed by direct grep, unlike Spiritwrack's own sites) -- a real,
separate, pre-existing gap this ward's own wiring doesn't invent a
baseline for. Still genuinely unwired, confirmed absent everywhere in
`src/` (not just under a different name): `FLOOD_DAMS` (Flood),
`DRY_ICE_FOG` (Clairvoyance), `ULTRAVIOLET_LENSES` (Illusory Terrain)
-- a real, separate follow-up, not attempted here.

``REPORTS.PAS`` (~line 325-360, continuing the loop quoted above)
confirms the full "Discoveries of the Sages" report line format and the
separate `Inv_Bonus` line right above it:

```pascal
WRITELN(playfile,  '  Expected Revenues: ',Tax_Base(kng):3);
IF Inv_Bonus(kng) > 0 THEN
  WRITELN(playfile,'   +Invention Bonus: ',Inv_Bonus(kng):3,'%');
...
FOR dval:= 20 DOWNTO 0 DO FOR d:= fix0 TO crunch27 DO
  IF discval[d] = dval THEN IF dk[d] THEN BEGIN
    WRITE(playfile,'  ',dname[d],' ':25-Length(dname[d]),'(');
    CASE d OF ... END;
    WRITELN(playfile,')');
    ...
```

`Inv_Bonus(kng)` prints as a bare percentage (`'%'` suffix, no gold sign),
confirming it's the *sum* of every owned `crunch` discovery's own revenue
percentage (`DISCOVERY_REVENUE_BONUS_PERCENT`), not a gold figure --
`turn/tax_base.py compute_invention_bonus_percent()` (Phase 268) is
therefore additive to, not folded into, `compute_tax_base()`'s own
return value, matching how the two print as separate report lines.
**Phase 747** (`Desktop/INVBONUS.md`, user-supplied disassembly) closes
the other half of this: although `Inv_Bonus` itself only ever returns a
bare percentage, `AK.EXE`'s own real economic resolver does use that
percentage to credit real gold (`Trunc(Inv_Bonus(kng)*0.01*eligible_
revenue + Random)`, `Random` drawn unconditionally) -- `turn/tax_base.py
apply_turn_revenue()` now applies this formula for real; the percentage
computed here and displayed by `+Invention Bonus: N%` is unchanged.
Each Discoveries-list line orders by descending `discval` (a real,
previously-unmodeled field, extracted verbatim from `CTBOTH.PAS` line
766's own `discval: discbyte = (...)` const array as
`DISCOVERY_DISPLAY_VALUE` below -- Phase 93's own docstring called this
field's only use "that one print loop"; this phase is exactly that use),
ties broken by declaration order (the inner `FOR d` loop's own order).
**Phase 643 -- exchange attribution now modeled**: an earlier version
of this note called the `'(Received from player(s) #k1...'` line
blocked on tracking "from whom" a Discovery came, tying it (wrongly)
to espionage. Re-reading `REPORTS.PAS` lines 348-392 directly found
the real text is unconditionally "...by scientific treaty" -- this
parenthetical (and its own sibling, "(Sent to player(s) #k1... by
scientific treaty)", a second, independent line this note didn't even
name) is *only* about `turn/scientific_treaty.py execute_scientific_
treaties()` ([8.4]), never espionage; `MeritTally.discoveries_via_
espionage` (Phase 267) remains the correct, separate, already-modeled
counter for that. See `GameState.discovery_exchanged_from`'s own
docstring for the real `kexch[giver,receiver]` shape now tracked, and
`report/turn_report.py describe_finances_report()` for the rendering.
"""

from __future__ import annotations

from enum import Enum

from ak_engine.models.enums import ABILITY_NAME, SPELL_NAME, Ability, Spell


class Discovery(Enum):
    """Positional with ``CTBOTH.PAS``'s own ``discovery`` enum declaration:
    ``fix0``-``fix9`` (ability bonus set 1), ``wreck0``-``wreck9`` (ability
    bonus set 2), ``bild10``,``bild11``,``bild12``,``bild13``,``bild20``..
    ``bild23``,``bild30``..``bild33``,``bild40``..``bild43`` (anti-spell,
    16 members), ``crunch0``-``crunch27`` (revenue bonus, 28 members).
    Member names below are derived from ``DISCOVERY_NAME``'s own display
    strings (matching this project's ``Weapon``/``Treasure`` precedent),
    not the Pascal source's internal ``fix``/``wreck``/``bild``/``crunch``
    identifiers, which carry no rulebook-facing meaning of their own.
    """

    LAND_SHIP = 0
    SCYTHED_CHARIOTS = 1
    PONY_EXPRESS = 2
    MACADAM_ROADS = 3
    GREEK_FIRE = 4
    SEXTANT = 5
    COMPOSITE_BOW = 6
    TUNGSTEN_TIPPED_ARROW = 7
    STRENGTH_ELIXIR = 8
    MITHRIL_CHAINMAIL = 9
    MEDITATION_INCENSE = 10
    CLASSIFICATION_OF_LIFE = 11
    MAGNETIZED_LOCK_PICKS = 12
    TRAP_FINDING_DUST = 13
    COMPASS = 14
    TELESCOPE = 15
    INVISIBLE_INK = 16
    TWO_WAY_MIRRORS = 17
    HIEROGLYPHIC_TRANSLATION = 18
    SCIENTIFIC_METHOD = 19
    OSTEOPATHIC_GERM_WARFARE = 20
    HIDDEN_TATTOOS = 21
    PENICILLIN = 22
    ARTIFICIAL_ORGANS = 23
    FLOOD_DAMS = 24
    GIANT_FAN = 25
    REINFORCED_CONCRETE = 26
    ASBESTOS_CLOTHING = 27
    ANALYTICAL_PSYCHOLOGY = 28
    PROPAGANDA_MEGAPHONES = 29
    DRY_ICE_FOG = 30
    LEAD_LINED_HELMET = 31
    ULTRAVIOLET_LENSES = 32
    OBSERVATION_BALLOONS = 33
    HAND_HELD_RADAR = 34
    INFRARED_GOGGLES = 35
    PEANUT_BUTTER_SANDWICH = 36
    ASPIRIN_PILL = 37
    PEPPER_SPICE = 38
    COTTON_GIN = 39
    ICE_CREAM_CONE = 40
    BLACK_LACE_TEDDY = 41
    SCREW = 42
    REFORGING_OF_STEEL = 43
    MAGNET = 44
    MALPRACTICE_SUIT = 45
    GAMBLING_CASINO = 46
    PULLEY = 47
    INK_STAMP = 48
    POSTAGE_STAMP = 49
    GAME_OF_CHESS = 50
    WATER_WHEEL = 51
    SOAP_BAR = 52
    PIPE_ORGAN = 53
    REAPER = 54
    COAL_MINE = 55
    SPECTACLES = 56
    WINDMILL = 57
    GUITAR = 58
    PAPER_MILL = 59
    UMBRELLA = 60
    TIMEPIECE = 61
    FIREWORKS_DISPLAY = 62
    VULCANIZED_RUBBER = 63


# CTME.PAS `dname`, verbatim, positional with `Discovery`'s own ordinals above.
DISCOVERY_NAME: dict[Discovery, str] = {
    Discovery.LAND_SHIP: "Land Ship",
    Discovery.SCYTHED_CHARIOTS: "Scythed Chariots",
    Discovery.PONY_EXPRESS: "Pony Express",
    Discovery.MACADAM_ROADS: "Macadam Roads",
    Discovery.GREEK_FIRE: "Greek Fire",
    Discovery.SEXTANT: "Sextant",
    Discovery.COMPOSITE_BOW: "Composite Bow",
    Discovery.TUNGSTEN_TIPPED_ARROW: "Tungsten-Tipped Arrow",
    Discovery.STRENGTH_ELIXIR: "Strength Elixir",
    Discovery.MITHRIL_CHAINMAIL: "Mithril Chainmail",
    Discovery.MEDITATION_INCENSE: "Meditation Incense",
    Discovery.CLASSIFICATION_OF_LIFE: "Classification of Life",
    Discovery.MAGNETIZED_LOCK_PICKS: "Magnetized Lock Picks",
    Discovery.TRAP_FINDING_DUST: "Trap Finding Dust",
    Discovery.COMPASS: "Compass",
    Discovery.TELESCOPE: "Telescope",
    Discovery.INVISIBLE_INK: "Invisible Ink",
    Discovery.TWO_WAY_MIRRORS: "2-Way Mirrors",
    Discovery.HIEROGLYPHIC_TRANSLATION: "Hieroglyphic Translation",
    Discovery.SCIENTIFIC_METHOD: "Scientific Method",
    Discovery.OSTEOPATHIC_GERM_WARFARE: "Osteopathic Germ Warfare",
    Discovery.HIDDEN_TATTOOS: "Hidden Tattoos",
    Discovery.PENICILLIN: "Penicillin",
    Discovery.ARTIFICIAL_ORGANS: "Artificial Organs",
    Discovery.FLOOD_DAMS: "Flood Dams",
    Discovery.GIANT_FAN: "Giant Fan",
    Discovery.REINFORCED_CONCRETE: "Reinforced Concrete",
    Discovery.ASBESTOS_CLOTHING: "Asbestos Clothing",
    Discovery.ANALYTICAL_PSYCHOLOGY: "Analytical Psychology",
    Discovery.PROPAGANDA_MEGAPHONES: "Propaganda Megaphones",
    Discovery.DRY_ICE_FOG: "Dry Ice Fog",
    Discovery.LEAD_LINED_HELMET: "Lead-Lined Helmet",
    Discovery.ULTRAVIOLET_LENSES: "Ultraviolet Lenses",
    Discovery.OBSERVATION_BALLOONS: "Observation Balloons",
    Discovery.HAND_HELD_RADAR: "Hand-Held Radar",
    Discovery.INFRARED_GOGGLES: "Infrared Goggles",
    Discovery.PEANUT_BUTTER_SANDWICH: "Peanut Butter Sandwich",
    Discovery.ASPIRIN_PILL: "Aspirin Pill",
    Discovery.PEPPER_SPICE: "Pepper Spice",
    Discovery.COTTON_GIN: "Cotton Gin",
    Discovery.ICE_CREAM_CONE: "Ice Cream Cone",
    Discovery.BLACK_LACE_TEDDY: "Black Lace Teddy",
    Discovery.SCREW: "Screw",
    Discovery.REFORGING_OF_STEEL: "Reforging of Steel",
    Discovery.MAGNET: "Magnet",
    Discovery.MALPRACTICE_SUIT: "Malpractice Suit",
    Discovery.GAMBLING_CASINO: "Gambling Casino",
    Discovery.PULLEY: "Pulley",
    Discovery.INK_STAMP: "Ink Stamp",
    Discovery.POSTAGE_STAMP: "Postage Stamp",
    Discovery.GAME_OF_CHESS: "Game of Chess",
    Discovery.WATER_WHEEL: "Water Wheel",
    Discovery.SOAP_BAR: "Soap Bar",
    Discovery.PIPE_ORGAN: "Pipe Organ",
    Discovery.REAPER: "Reaper",
    Discovery.COAL_MINE: "Coal Mine",
    Discovery.SPECTACLES: "Spectacles",
    Discovery.WINDMILL: "Windmill",
    Discovery.GUITAR: "Guitar",
    Discovery.PAPER_MILL: "Paper Mill",
    Discovery.UMBRELLA: "Umbrella",
    Discovery.TIMEPIECE: "Timepiece",
    Discovery.FIREWORKS_DISPLAY: "Fireworks Display",
    Discovery.VULCANIZED_RUBBER: "Vulcanized Rubber",
}


# `Discovery.txt` (user-supplied design document), verbatim, positional
# with `Discovery`'s own ordinals above.
DISCOVERY_DESCRIPTION: dict[Discovery, str] = {
    Discovery.LAND_SHIP: "The Land Ship is a galley on wheels which can be used to charge enemy lines along a road or clearing in a battle.  They need not be recruited because is assumed to be a small Land Ship contingent at each battle. Its effect is to raise the Tactical ability of all of the characters of the Kingdom by 1 level.",
    Discovery.SCYTHED_CHARIOTS: "Scythed Chariots can be used to charge enemy lines along a road, plains area or clearing in a battle.  They need not be recruited because there is assumed to be a small Scythed Chariot contingent at each battle. Their effect is to raise the Tactical ability of all of the characters of the Kingdom by 1 level.",
    Discovery.PONY_EXPRESS: "The Pony Express enables the Kingdom to establish fast, consistent lines of communication between troops and characters, enabling faster movement of armies. Its effect is to raise the March ability of all of the characters of the Kingdom by 1 level.",
    Discovery.MACADAM_ROADS: "Macadam Roads are an improvement over the old dirt roads because they drain well and troops never get bogged down in mud, so they can move faster. Their effect is to raise the March ability of all of the characters of the Kingdom by 1 level.",
    Discovery.GREEK_FIRE: "Greek Fire is a special mixture of flammables which sets the wood of enemy ships on fire and is very difficult to put out. Its effect is to raise the Naval ability of all of the characters of the Kingdom by 1 level.",
    Discovery.SEXTANT: "The Sextant allows the determination of a ship's position at sea. Its effect is to raise the Naval ability of all of the generals of the Kingdom by 1 level.",
    Discovery.COMPOSITE_BOW: "The Composite bow is a bow that is specially strung to deliver more force to an arrow without having to pull very hard on the bowstring. Its effect is to raise the Archery ability of all of the characters of the Kingdom by 1 level.",
    Discovery.TUNGSTEN_TIPPED_ARROW: "Tungsten-Tipped Arrows are arrows with their tips strengthed with steel-tungsten alloy. Their effect is to raise the Archery ability of all of the characters of the Kingdom by 1 level.",
    Discovery.STRENGTH_ELIXIR: "The Strength Elixir is a nutritious blend which enables the imbiber to maximize the strength gained through exercise. Its effect is to raise the Melee ability of all of the characters of the Kingdom by 1 level.",
    Discovery.MITHRIL_CHAINMAIL: "Mithril Chainmail is a specially strengthed armor which enables the wearer to swing and maneuver with greater agility in combat. Its effect is to raise the Melee ability of all of the characters of the Kingdom by 1 level.",
    Discovery.MEDITATION_INCENSE: "Meditation Incense is a fragrant, calming incense which allows the user to attain a state of mind that is closer to Nature. Its effect is to raise the Druid ability of all of the characters of the Kingdom by 1 level.",
    Discovery.CLASSIFICATION_OF_LIFE: "The Classification of Life is an index to all the races and species of the world. Its effect is to raise the Druid ability of all of the characters of the Kingdom by 1 level.",
    Discovery.MAGNETIZED_LOCK_PICKS: "Magnetized Lock Picks help a thief in picking locks to steal the treasure that lies within. Their effect is to raise the Thief ability of all of the characters of the Kingdom by 1 level.",
    Discovery.TRAP_FINDING_DUST: "Trap Finding Dust is a specially ground and colored dust which, when thrown onto a stone surface, helps to identify joints in the stone which may be traps or secret compartments. Its effect is to raise the Thief ability of all of the characters of the Kingdom by 1 level.",
    Discovery.COMPASS: "The compass helps an explorer find his way in a wilderness or at sea on a cloudy night. Its effect is to raise the Explorer ability of all of the characters of the Kingdom by 1 level.",
    Discovery.TELESCOPE: "The telescope helps an explorer see more territory from a given vantage point.  Its effect is to raise the Explorer ability of all of the characters of the Kingdom by 1 level.",
    Discovery.INVISIBLE_INK: "Invisible Ink helps a spy to keep notes without the risk of being exposed as a spy. Its effect is to raise the Spy ability of all of the characters of the Kingdom by 1 level.",
    Discovery.TWO_WAY_MIRRORS: "2-Way mirrors helps a spy to gather information from foreign officials who are caught in compromising situations. Their effect is to raise the Spy ability of all of the characters of the Kingdom by 1 level.",
    Discovery.HIEROGLYPHIC_TRANSLATION: "Hieroglyphic Translation helps a Sage in his researches of old manuscripts.  Its effect is to raise the Sage ability of all of the characters of the Kingdom by 1 level.",
    Discovery.SCIENTIFIC_METHOD: "The Scientific Method helps a Sage to conduct his researches systematically and efficiently. Its effect is to raise the Sage ability of all of the characters of the Kingdom by 1 level.",
    Discovery.OSTEOPATHIC_GERM_WARFARE: "Osteopathic Germ Warfare can be used to infect Skeletal Armies raised by Necromancers with a disease that rots their bones. Its effect is to reduce the strength of Skeletal Armies in the opposing force by one quality level in any battle fought by the Kingdom. From now on, Osteopathic Germ Warfare will reduce the strength of Skeletal Armies in the opposing force by one quality level.",
    Discovery.HIDDEN_TATTOOS: "Hidden Tattoos neutralize the Kill Enemy spell of Necromancers because they can't make a sufficiently accurate figurine of the character they want dead. All characters of the Kingdom are protected.  Instead of being killed, the target character will be sick for the remainder of the gameturn and will spend his time practicing abilities somewhat randomly. From now on, Hidden Tattoos will reduce the effect of the Kill Enemy spell: the target character will be sick for the remainder of the gameturn and will spend his time practicing abilities somewhat randomly.",
    Discovery.PENICILLIN: "Penicillin protects the Kingdom from all effects of the Plague spell used by Necromancers. Your armies are protected wherever they go, and all armies (yours and your ally's) are protected in your provinces. Armies affected by Plague will have a 50% chance of losing one level of quality. From now on, Penicillin will reduce the effects of the Plague spell: affected armies will have a 50% chance of losing one level of quality.",
    Discovery.ARTIFICIAL_ORGANS: 'Artificial Organs are installed in characters employed by the Kingdom, and they reduce the effect of the Hand of Death spell used by Necromancers to squeeze and crush the internal organs of their enemies. No damage is caused to the target, and archery can be used (but not spells.) From now on, Artificial Organs will reduce the effects of "Hand of Death": no damage is caused, and archery can be used (but not spells.)',
    Discovery.FLOOD_DAMS: 'Flood Dams reduce the effects of the Flood spell used by Elemental Magicians. When it\'s cast on a province owned by your kingdom, affected armies currently in the target province will immediately lose one movement point. From now on, Flood Dams will reduce the effects of the "Flood" spell: when it\'s cast on a province owned by your kingdom, affected armies currently in the target province will immediately lose one movement point.',
    Discovery.GIANT_FAN: 'A Giant Fan is transported by all armies of the Kingdom.  Whenever an Elemental Mage casts a Tornado spell, the soldiers just turn the fan on and it helps disperse the tornadoes. Armies hit by Tornadoes will have a 50% chance of losing one level of quality. From now on, the Giant Fan will reduce the effects of the "Tornado" spell: affected armies will have a 50% chance of losing one level of quality.',
    Discovery.REINFORCED_CONCRETE: 'Reinforced Concrete is used to build and strengthen the structures of the Kingdom, reducing the effect of Earthquake spells cast by Elemental Mages. Income from the affected province will only decrease by 3 gold. From now on, Reinforced Concrete will reduce the effects of the "Earthquake" spell: income from the affected province will decrease by 3 gold.',
    Discovery.ASBESTOS_CLOTHING: 'Asbestos Clothing is a fireproof clothing worn by all characters of the Kingdom which reduces the effects of fireball spells cast by Elemental Mages. From now on, Asbestos Clothing will reduce the effects of the "Fireball" spell: the damage caused will be reduced by 67%.',
    Discovery.ANALYTICAL_PSYCHOLOGY: 'Analytical Psychology is taught to all characters employed by the Kingdom. Any Charm spell cast by a Psychic Mage on your character will work, but it wears off at the end of the turn, and the charmed character will never Search features or risk combat. From now on, Analytical Psychology will reduce the effects of the "Charm" spell: the "Charm" spell will work, but it wears off at the end of the turn, and the charmed character will never Search features or risk combat. Any armies traveling with the character will go with him when he returns to his master.',
    Discovery.PROPAGANDA_MEGAPHONES: 'Propaganda Megaphones are used at a battle to reduce the effects of any Oratory spell cast by enemy Psychics on their forces.  The megaphones allow the Kingdom\'s generals to broadcast the lies and logical flaws in the enemy leader\'s speeches. Each opposing army will have only a 33% chance of being affected by their leader\'s Oratory ("you can fool some of the people all of the time..."). From now on, Propaganda Megaphones will reduce the effects of the "Oratory" spell: each opposing army will have only a 33% chance of being affected by their leader\'s Oratory ("you can fool some of the people all of the time...")',
    Discovery.DRY_ICE_FOG: 'Dry Ice Fog reduces the effects of Clairvoyance spells cast on any character employed by the Kingdom. Information obtained will be limited to very large-scale activities, while more personal activities will be clouded (no more keyhole-peeping!) From now on, Dry Ice Fog will will reduce the effects of the "Clairvoyance" spell: information obtained will be limited to very large-scale activities, while more personal activities will be clouded (no more keyhole-peeping!)',
    Discovery.LEAD_LINED_HELMET: 'The Lead-Lined Helmet reduces the effect of a Pyschic Blast spell cast by an enemy Psychic from having any effect on any character employed by the Kingdom. The spell will allow only 1-2 free attack rounds. From now on, the Lead-Lined Helmet will reduce the effect of the "Pyschic Blast" spell: the spell will allow only 1-2 free attack rounds.',
    Discovery.ULTRAVIOLET_LENSES: "Ultraviolet Lenses are given to all characters employed by the Kingdom to enable them to see through an Illusory Terrain spell cast by an Illusionist. Ultraviolet Lenses will still have the same effect: characters will see through the Illusory terrain, but armies will still be affected.",
    Discovery.OBSERVATION_BALLOONS: 'Observation Balloons are raised at a field of battle.  They enable the observers to perceive Phantasmal Armies formed by Illusionists for the two-dimensional images they are, thus reducing the effects of the spell at any battle which the Kingdom conducts: their army strength is increased by only 5% per skill level by the phantasms. From now on, Observation Balloons will reduce the effect of "Phantasmal Armies": army strength is increased by only 5% per skill level.',
    Discovery.HAND_HELD_RADAR: "Hand-Held Radar sets are distributed to all characters employed by the Kingdom.  They enable characters to find features regardless of whether a Hide Feature spell has been cast on the feature by an Illusionist. Hand-Held Radar sets will still have the same effect.",
    Discovery.INFRARED_GOGGLES: 'Infrared Goggles are distributed to all characters employed by the Kingdom.  They enable characters to help detect enemy Illusionists who have cast an Invisibility spell on themselves. The defensive protection will be only 20%, not 50%. From now on, Infrared Goggles will reduce the effect of the "Invisibility" spell: defensive protection will be only 20%, not 50%.',
    Discovery.PEANUT_BUTTER_SANDWICH: "The invention of Peanut Butter Sandwiches vastly increases the morale of the younger population, and also makes the little rug rats cheaper to feed.  It has the effect of raising the revenue of the Kingdom by an average of 1% each gameturn.",
    Discovery.ASPIRIN_PILL: "Aspirin helps increase revenue by keeping the populace feeling well and working hard for His Majesty's glory.  It also provides fast relief when your Royal Concubines are giving you a headache. Aspirin has the effect of raising the revenue of the Kingdom by an average of 2% each gameturn.",
    Discovery.PEPPER_SPICE: "Congratulations, you have discovered the Pepper Corn!  All you have to do is grind up those little suckers, sell the spice at jacked-up Royal Monopoly prices and you will increase your Kingdom's revenue by an average of 3% each gameturn.",
    Discovery.COTTON_GIN: "The Cotton Gin automates the separation of cotton from the seeds contained within the cotton bolls, thus freeing all your contented little slaves for other productive work.  It has the effect of raising the revenue of the Kingdom by an average of 4% each gameturn.",
    Discovery.ICE_CREAM_CONE: "The Ice Cream Cone is a nice little Royal Monopoly which will also boost revenue from your Toothpaste Monopoly.  You can increase your Kingdom's revenue by an average of 1% each gameturn.",
    Discovery.BLACK_LACE_TEDDY: "Black Lace raises the revenue of the Kingdom by an average of 2% each gameturn.  How?  Simple.  Women can now drive men even crazier than before.  Men will have to work harder to please them, which means they will have to produce more goods, which means more taxes flowing into your coffers.",
    Discovery.SCREW: "The Screw helps your woodworking industry.  Its effect is to raise the revenue of the Kingdom by an average of 3% each gameturn.",
    Discovery.REFORGING_OF_STEEL: "Steel Reforging helps your Royal Steelers make the finest possible steel products, and also insures that the King possesses the most finely-worked sword that money can buy. The sole effect is to raise the revenue of the Kingdom by an average of 4% each gameturn.",
    Discovery.MAGNET: "The Magnet has many minor uses.  It has the effect of raising the revenue of the Kingdom by an average of 1% each gameturn.",
    Discovery.MALPRACTICE_SUIT: "The Malpractice Suit helps increase revenue from your Insurance Monopoly.  The effect is to raise the revenue of the Kingdom by an average of 2% each gameturn.",
    Discovery.GAMBLING_CASINO: "The Gambling Casino (complete with such wonderful innovations as marked cards, rigged roulette wheels, etc.  ) raises the revenue of the Kingdom by an average of 3% each gameturn.",
    Discovery.PULLEY: "The Pulley helps raise bridges, buildings and other indispensable structures such as 100-foot high statues of Your Majesty.  Its effect is to raise the revenue of the Kingdom by an average of 4% each gameturn.",
    Discovery.INK_STAMP: "The Ink Stamp helps increase the efficiency of all the pesky little bureaucrats you have running around your Palace.  Its effect is to raise the revenue of the Kingdom by an average of 1% each gameturn.",
    Discovery.POSTAGE_STAMP: "The Postage Stamp helps establish and regulate communications in your Kingdom.  There's also a P.  R.  bonanza:  You get to put your portrait on every stamp. The effect is to raise the revenue of the Kingdom by 2% each turn.",
    Discovery.GAME_OF_CHESS: "The Game of Chess helps everyone who plays it to sharpen their minds, enabling them to think and act with alacrity.  Its effect is to raise the revenue of the Kingdom by an average of 3% each gameturn.",
    Discovery.WATER_WHEEL: "The Water Wheel enables greedy entrepreneurs to build factories to grind wheat, corn, axes, et cetera.  It raises the revenue of the Kingdom by an average of 4% each gameturn.",
    Discovery.SOAP_BAR: "Soap helps people to work alongside each other without having to use one of their hands to hold their nose (before soap, people generally smelled something like a dead cow).  Its effect is to the revenue of the Kingdom by an average of 1% each gameturn.",
    Discovery.PIPE_ORGAN: "The deep, sonorous tones of the Pipe Organ attract multitudes of people to your Churches, where they happily donate their hard-earned money.  And since you control the Church, guess who's raking in the bucks?  That's right, your revenues are increased by an average of 2% each gameturn.",
    Discovery.REAPER: "Your peasants are grateful for the horse-drawn Reaper, which automatically harvests the wheat as it rolls along.  Its effect is to raise the revenue of the Kingdom by an average of 3% each gameturn.",
    Discovery.COAL_MINE: "Coal Mines have many uses.  They produce fuel.  You can put coal in Christmas stockings.  You can exile your political enemies to work in the Mines.  Need I say more? Their effect is to raises the revenue of the Kingdom by an average of 4% each gameturn.",
    Discovery.SPECTACLES: "Your Royal Monopoly on Spectacles enables you to miraculously help nearsighted people see clearly for the first tiime!  And if they don't want to pay your jacked-up prices, they can damn well stumble over pebbles and step in horse puckey for the rest of their lives!  The effect is to raise your revenue by an average of 2% each gameturn.",
    Discovery.WINDMILL: "Windmills help drive machines, pump water for irrigation, et cetera.  They also are the favorite jousting partners for your intrepid knights.  The effect is to raise the revenue of the Kingdom by an average of 2% each gameturn.",
    Discovery.GUITAR: "The Guitar helps spread folk music and rock 'n' roll to the farthest reaches of the Kingdom, greatly increasing the morale of your people.  Fortunately, punk rock hasn't been invented yet, or your civilization would be doomed. The effect is to raise the revenue of the Kingdom by an average of 3% each gameturn.",
    Discovery.PAPER_MILL: "Paper has many, many uses. The most important usage is the printing of paper currency, so you can spend money that you don't really have.  The effect is to raise the revenue of the Kingdom by an average of 4% each gameturn.",
    Discovery.UMBRELLA: "The Umbrella protects people from getting soaked in the rain, thus curbing pneumonia and other diseases.  Healthy people are working, tax-paying people.  Your revenues are raised by an average of 1% each gameturn.",
    Discovery.TIMEPIECE: "Your peasants can't imagine how they ever got along without the Timepiece.  And your Royal Engineers have installed a built-in calendar which reminds the peasants of all the important tax deadlines. Now wasn't that nice of them? The effect of the Timepiece is to raise the revenue of the Kingdom by an average of 2% each gameturn.",
    Discovery.FIREWORKS_DISPLAY: "Now you can put on a Fireworks display on every important patriotic holiday.  The peasants are greatly impressed, and their voluntary contributions raise your revenue by an average of 3% each gameturn.",
    Discovery.VULCANIZED_RUBBER: "Rubber has a thousand uses.  Your 25-year-old heir is especially thankful for the rubber ducky made for him by the Royal Toymaker. The effect of this invention is to raise the revenue of the Kingdom by an average of 4% each gameturn.",
}


# Ability skill bonus group (fix0-fix9, wreck0-wreck9) -- CTBOTH.PAS's own
# `ability(ord(d) Shr 1)` / `ability((ord(d)+10) Shr 1)` formula, confirmed
# a second time by `DISCOVERY_DESCRIPTION`'s own "raise the <ability>
# ability" text for every one of these 20 entries.
DISCOVERY_ABILITY_BONUS: dict[Discovery, Ability] = {
    Discovery.LAND_SHIP: Ability.TACTICAL,
    Discovery.SCYTHED_CHARIOTS: Ability.TACTICAL,
    Discovery.PONY_EXPRESS: Ability.MARCH,
    Discovery.MACADAM_ROADS: Ability.MARCH,
    Discovery.GREEK_FIRE: Ability.NAVAL,
    Discovery.SEXTANT: Ability.NAVAL,
    Discovery.COMPOSITE_BOW: Ability.ARCHERY,
    Discovery.TUNGSTEN_TIPPED_ARROW: Ability.ARCHERY,
    Discovery.STRENGTH_ELIXIR: Ability.MELEE,
    Discovery.MITHRIL_CHAINMAIL: Ability.MELEE,
    Discovery.MEDITATION_INCENSE: Ability.DRUID,
    Discovery.CLASSIFICATION_OF_LIFE: Ability.DRUID,
    Discovery.MAGNETIZED_LOCK_PICKS: Ability.THIEF,
    Discovery.TRAP_FINDING_DUST: Ability.THIEF,
    Discovery.COMPASS: Ability.EXPLORER,
    Discovery.TELESCOPE: Ability.EXPLORER,
    Discovery.INVISIBLE_INK: Ability.SPY,
    Discovery.TWO_WAY_MIRRORS: Ability.SPY,
    Discovery.HIEROGLYPHIC_TRANSLATION: Ability.SAGE,
    Discovery.SCIENTIFIC_METHOD: Ability.SAGE,
}

# Anti-spell ward group (bild10-bild43) -- CTBOTH.PAS's own
# `spell(ord(Skeletal_Army)+ord(d)-ord(bild10))` formula (Spell ordinals
# 4-19), confirmed a second time by `DISCOVERY_DESCRIPTION`'s own named
# spell for every one of these 16 entries.
DISCOVERY_ANTISPELL_TARGET: dict[Discovery, Spell] = {
    Discovery.OSTEOPATHIC_GERM_WARFARE: Spell.SKELETAL_ARMY,
    Discovery.HIDDEN_TATTOOS: Spell.KILL_ENEMY,
    Discovery.PENICILLIN: Spell.PLAGUE,
    Discovery.ARTIFICIAL_ORGANS: Spell.HAND_OF_DEATH,
    Discovery.FLOOD_DAMS: Spell.FLOOD,
    Discovery.GIANT_FAN: Spell.TORNADO,
    Discovery.REINFORCED_CONCRETE: Spell.EARTHQUAKE,
    Discovery.ASBESTOS_CLOTHING: Spell.FIREBALL,
    Discovery.ANALYTICAL_PSYCHOLOGY: Spell.CHARM,
    Discovery.PROPAGANDA_MEGAPHONES: Spell.ORATORY,
    Discovery.DRY_ICE_FOG: Spell.CLAIRVOYANCE,
    Discovery.LEAD_LINED_HELMET: Spell.PSYCHIC_BLAST,
    Discovery.ULTRAVIOLET_LENSES: Spell.ILLUS_TERRAIN,
    Discovery.OBSERVATION_BALLOONS: Spell.ILLUS_ARMIES,
    Discovery.HAND_HELD_RADAR: Spell.HIDE_FEATURE,
    Discovery.INFRARED_GOGGLES: Spell.INVISIBILITY,
}

# Revenue bonus group (crunch0-crunch27) -- CTBOTH.PAS's own
# `1+((ord(d)-ord(crunch0)) and 3)` formula (cycling 1,2,3,4). Matches
# `DISCOVERY_DESCRIPTION`'s own stated percentage for 27 of these 28
# entries; `SPECTACLES` is the one confirmed exception (formula: 1%,
# `Discovery.txt`: "2%") -- see the module docstring. This dict follows
# the Pascal formula, the actual executable behavior of the original
# engine, not the design-doc text, for that one entry.
DISCOVERY_REVENUE_BONUS_PERCENT: dict[Discovery, int] = {
    Discovery.PEANUT_BUTTER_SANDWICH: 1,
    Discovery.ASPIRIN_PILL: 2,
    Discovery.PEPPER_SPICE: 3,
    Discovery.COTTON_GIN: 4,
    Discovery.ICE_CREAM_CONE: 1,
    Discovery.BLACK_LACE_TEDDY: 2,
    Discovery.SCREW: 3,
    Discovery.REFORGING_OF_STEEL: 4,
    Discovery.MAGNET: 1,
    Discovery.MALPRACTICE_SUIT: 2,
    Discovery.GAMBLING_CASINO: 3,
    Discovery.PULLEY: 4,
    Discovery.INK_STAMP: 1,
    Discovery.POSTAGE_STAMP: 2,
    Discovery.GAME_OF_CHESS: 3,
    Discovery.WATER_WHEEL: 4,
    Discovery.SOAP_BAR: 1,
    Discovery.PIPE_ORGAN: 2,
    Discovery.REAPER: 3,
    Discovery.COAL_MINE: 4,
    Discovery.SPECTACLES: 1,  # Discovery.txt says 2% -- see module docstring
    Discovery.WINDMILL: 2,
    Discovery.GUITAR: 3,
    Discovery.PAPER_MILL: 4,
    Discovery.UMBRELLA: 1,
    Discovery.TIMEPIECE: 2,
    Discovery.FIREWORKS_DISPLAY: 3,
    Discovery.VULCANIZED_RUBBER: 4,
}


# CTBOTH.PAS `discval: discbyte = (...)` (~line 766), verbatim, positional
# with `Discovery`'s own enum declaration order -- see module docstring's
# Phase 268 note. A pure display-order key (higher prints first): the
# real report loop is `FOR dval:= 20 DOWNTO 0 DO FOR d:= fix0 TO crunch27
# DO IF discval[d] = dval ...`, so sorting a kingdom's own discoveries by
# `(-DISCOVERY_DISPLAY_VALUE[d], d.value)` reproduces that exact order
# (descending value, ties broken by the inner loop's own declaration
# order).
DISCOVERY_DISPLAY_VALUE: dict[Discovery, int] = {
    Discovery.LAND_SHIP: 19,
    Discovery.SCYTHED_CHARIOTS: 19,
    Discovery.PONY_EXPRESS: 20,
    Discovery.MACADAM_ROADS: 20,
    Discovery.GREEK_FIRE: 18,
    Discovery.SEXTANT: 18,
    Discovery.COMPOSITE_BOW: 3,
    Discovery.TUNGSTEN_TIPPED_ARROW: 3,
    Discovery.STRENGTH_ELIXIR: 3,
    Discovery.MITHRIL_CHAINMAIL: 3,
    Discovery.MEDITATION_INCENSE: 17,
    Discovery.CLASSIFICATION_OF_LIFE: 17,
    Discovery.MAGNETIZED_LOCK_PICKS: 2,
    Discovery.TRAP_FINDING_DUST: 2,
    Discovery.COMPASS: 2,
    Discovery.TELESCOPE: 2,
    Discovery.INVISIBLE_INK: 16,
    Discovery.TWO_WAY_MIRRORS: 16,
    Discovery.HIEROGLYPHIC_TRANSLATION: 1,
    Discovery.SCIENTIFIC_METHOD: 1,
    Discovery.OSTEOPATHIC_GERM_WARFARE: 17,
    Discovery.HIDDEN_TATTOOS: 17,
    Discovery.PENICILLIN: 18,
    Discovery.ARTIFICIAL_ORGANS: 2,
    Discovery.FLOOD_DAMS: 17,
    Discovery.GIANT_FAN: 18,
    Discovery.REINFORCED_CONCRETE: 15,
    Discovery.ASBESTOS_CLOTHING: 2,
    Discovery.ANALYTICAL_PSYCHOLOGY: 14,
    Discovery.PROPAGANDA_MEGAPHONES: 17,
    Discovery.DRY_ICE_FOG: 16,
    Discovery.LEAD_LINED_HELMET: 2,
    Discovery.ULTRAVIOLET_LENSES: 17,
    Discovery.OBSERVATION_BALLOONS: 18,
    Discovery.HAND_HELD_RADAR: 1,
    Discovery.INFRARED_GOGGLES: 1,
    Discovery.PEANUT_BUTTER_SANDWICH: 10,
    Discovery.ASPIRIN_PILL: 11,
    Discovery.PEPPER_SPICE: 12,
    Discovery.COTTON_GIN: 13,
    Discovery.ICE_CREAM_CONE: 10,
    Discovery.BLACK_LACE_TEDDY: 11,
    Discovery.SCREW: 12,
    Discovery.REFORGING_OF_STEEL: 13,
    Discovery.MAGNET: 10,
    Discovery.MALPRACTICE_SUIT: 11,
    Discovery.GAMBLING_CASINO: 12,
    Discovery.PULLEY: 13,
    Discovery.INK_STAMP: 10,
    Discovery.POSTAGE_STAMP: 11,
    Discovery.GAME_OF_CHESS: 12,
    Discovery.WATER_WHEEL: 13,
    Discovery.SOAP_BAR: 10,
    Discovery.PIPE_ORGAN: 11,
    Discovery.REAPER: 12,
    Discovery.COAL_MINE: 13,
    Discovery.SPECTACLES: 10,
    Discovery.WINDMILL: 11,
    Discovery.GUITAR: 12,
    Discovery.PAPER_MILL: 13,
    Discovery.UMBRELLA: 10,
    Discovery.TIMEPIECE: 11,
    Discovery.FIREWORKS_DISPLAY: 12,
    Discovery.VULCANIZED_RUBBER: 13,
}


# CTME.PAS `dspread` (~line 390-420), verbatim, positional with
# `Discovery`'s own enum declaration order -- cross-checked byte-for-
# byte against `AK.EXE` raw 0x5107F-0x510BE by `Desktop/DISCVAL.md`
# (2026-09-13), zero mismatches across all 64 entries. **This is a
# different table from `DISCOVERY_DISPLAY_VALUE`/`discval` above** --
# `discval` is a pure display-order key read by the printing report and
# the Scientific Treaty exchange-priority selector; `dspread` instead
# categorizes how hard a Discovery is to obtain via "diffusion" (learning
# a Discovery already known to another Kingdom, via Spy/Battle/
# Conversation contexts) -- four categories, `Batt=1` (battle-related),
# `Comm=2` (common), `Prof=3` (professional), `Form=4` (formula-based),
# each with its own real per-category probability formula (`turn/
# aspy_execution.py _discovery_spread_success()`, the confirmed real
# per-category formula for the Spy channel specifically). See DISCVAL.md
# sections 16-18 for the full derivation, including the confirmed
# byte-level verification and the deliberately-deferred cumulative-
# budget/scanning-order refinement this project does not reproduce.
DISCOVERY_SPREAD_CATEGORY: dict[Discovery, int] = {
    Discovery.LAND_SHIP: 1,
    Discovery.SCYTHED_CHARIOTS: 1,
    Discovery.PONY_EXPRESS: 2,
    Discovery.MACADAM_ROADS: 2,
    Discovery.GREEK_FIRE: 4,
    Discovery.SEXTANT: 3,
    Discovery.COMPOSITE_BOW: 3,
    Discovery.TUNGSTEN_TIPPED_ARROW: 4,
    Discovery.STRENGTH_ELIXIR: 4,
    Discovery.MITHRIL_CHAINMAIL: 4,
    Discovery.MEDITATION_INCENSE: 4,
    Discovery.CLASSIFICATION_OF_LIFE: 3,
    Discovery.MAGNETIZED_LOCK_PICKS: 3,
    Discovery.TRAP_FINDING_DUST: 4,
    Discovery.COMPASS: 3,
    Discovery.TELESCOPE: 3,
    Discovery.INVISIBLE_INK: 4,
    Discovery.TWO_WAY_MIRRORS: 3,
    Discovery.HIEROGLYPHIC_TRANSLATION: 3,
    Discovery.SCIENTIFIC_METHOD: 3,
    Discovery.OSTEOPATHIC_GERM_WARFARE: 4,
    Discovery.HIDDEN_TATTOOS: 3,
    Discovery.PENICILLIN: 4,
    Discovery.ARTIFICIAL_ORGANS: 4,
    Discovery.FLOOD_DAMS: 2,
    Discovery.GIANT_FAN: 1,
    Discovery.REINFORCED_CONCRETE: 2,
    Discovery.ASBESTOS_CLOTHING: 4,
    Discovery.ANALYTICAL_PSYCHOLOGY: 3,
    Discovery.PROPAGANDA_MEGAPHONES: 1,
    Discovery.DRY_ICE_FOG: 4,
    Discovery.LEAD_LINED_HELMET: 4,
    Discovery.ULTRAVIOLET_LENSES: 4,
    Discovery.OBSERVATION_BALLOONS: 1,
    Discovery.HAND_HELD_RADAR: 4,
    Discovery.INFRARED_GOGGLES: 4,
    Discovery.PEANUT_BUTTER_SANDWICH: 2,
    Discovery.ASPIRIN_PILL: 3,
    Discovery.PEPPER_SPICE: 3,
    Discovery.COTTON_GIN: 2,
    Discovery.ICE_CREAM_CONE: 2,
    Discovery.BLACK_LACE_TEDDY: 3,
    Discovery.SCREW: 2,
    Discovery.REFORGING_OF_STEEL: 3,
    Discovery.MAGNET: 3,
    Discovery.MALPRACTICE_SUIT: 2,
    Discovery.GAMBLING_CASINO: 2,
    Discovery.PULLEY: 2,
    Discovery.INK_STAMP: 2,
    Discovery.POSTAGE_STAMP: 2,
    Discovery.GAME_OF_CHESS: 2,
    Discovery.WATER_WHEEL: 2,
    Discovery.SOAP_BAR: 2,
    Discovery.PIPE_ORGAN: 2,
    Discovery.REAPER: 2,
    Discovery.COAL_MINE: 2,
    Discovery.SPECTACLES: 2,
    Discovery.WINDMILL: 2,
    Discovery.GUITAR: 2,
    Discovery.PAPER_MILL: 2,
    Discovery.UMBRELLA: 2,
    Discovery.TIMEPIECE: 2,
    Discovery.FIREWORKS_DISPLAY: 3,
    Discovery.VULCANIZED_RUBBER: 3,
}


def discovery_effect_description(discovery: Discovery) -> str:
    """The parenthesized effect text REPORTS.PAS prints after each
    Discovery's own name -- see module docstring's Phase 268 quote:
    "+1 skill in <ability>" / "Anti-spell: <spell>" / "+X% revenue".
    """

    ability = DISCOVERY_ABILITY_BONUS.get(discovery)
    if ability is not None:
        return f"+1 skill in {ABILITY_NAME[ability]}"
    spell = DISCOVERY_ANTISPELL_TARGET.get(discovery)
    if spell is not None:
        return f"Anti-spell: {SPELL_NAME[spell]}"
    return f"+{DISCOVERY_REVENUE_BONUS_PERCENT[discovery]}% revenue"


def sorted_kingdom_discoveries(discoveries: set[Discovery]) -> list[Discovery]:
    """Orders a kingdom's own held Discoveries the way the real report
    does: descending `DISCOVERY_DISPLAY_VALUE`, ties broken by the
    Pascal enum's own declaration order -- see `DISCOVERY_DISPLAY_VALUE`'s
    own docstring.
    """

    return sorted(discoveries, key=lambda d: (-DISCOVERY_DISPLAY_VALUE[d], d.value))


def describe_discovery_line(discovery: Discovery) -> str:
    """One real report line: two spaces, the name padded to a 25-character
    field, then the parenthesized effect -- ``REPORTS.PAS``'s own
    ``WRITE(playfile,'  ',dname[d],' ':25-Length(dname[d]),'(');`` ...
    ``WRITELN(playfile,')');``. See module docstring's Phase 268 quote.
    """

    name = DISCOVERY_NAME[discovery]
    padding = " " * max(0, 25 - len(name))
    return f"  {name}{padding}({discovery_effect_description(discovery)})"
