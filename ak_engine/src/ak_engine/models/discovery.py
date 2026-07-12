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

Only the *name* table is transcribed here -- matching how
``models/office.py``/``models/weapon.py`` (Phases 81/83) started with
vocabulary before any mechanical wiring. Computing/applying these bonuses
(how a kingdom actually earns a ``Discovery``, and how each category's
effect combines with the rest of the engine -- e.g. does the ability bonus
stack additively with ``LeaderState.skills``, does the revenue bonus
combine with ``Inv_Bonus`` the same report section prints right above it)
is deliberately left to a real follow-up phase, not attempted here.

``discval`` (``CTBOTH.PAS`` ~line 766, also confirmed real via the same
report loop) is a pure *display-order* key -- the loop above prints
discoveries in descending ``discval`` order, grouped by identical value --
not a difficulty/point score with any other confirmed meaning. Not
modeled here since it has no use outside that one print loop.
"""

from __future__ import annotations

from enum import Enum


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
