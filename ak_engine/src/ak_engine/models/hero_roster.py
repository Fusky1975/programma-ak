"""The fixed, game-independent Hero name roster (Phase 366 rewrite of Phase 339).

**Corrects Phase 339's own central premise.** That phase built this
roster from a project-original reference document (`"Nomi (eroi) fino
a #99.txt"`), explicitly because no Pascal source for Hero name
selection was known to exist. A later reverse-engineering pass over
`AKGEN.EXE` (`AKGEN_reverse_engineering_report.md`,
`AKGEN_name_catalogs.json.txt`) found that source: `LNAMES.PAS`
(``k:\\tp\\lnames.pas``, read by `Init_Tr` at `0006:1176`), a real
Pascal-readable text file AKGEN opens line-by-line -- 255 short-string
lines, at most 12 characters each. **Confirmed exactly**:

- **Selection**: "read sequentially from index 0 through
  `leader_count-1`; not shuffled" -- leader slot 0 gets line 1 (id 0),
  slot 1 gets line 2 (id 1), and so on. No randomness at all.
- **`leader_count` by game version**: 100 for game version 3 and
  earlier, 175 for version 4+ `Arcanes_V`, 250 for version 4+ every
  other standard type -- `LEADER_COUNT_BY_GAME_VERSION` below.
- **King override**: "player-entered King names replace the
  corresponding initial entries; the final reserved leader slot can be
  replaced by an externally loaded Valhalla visitor; other loaded
  leaders retain their sequential defaults unless renamed later" --
  matches this project's own already-confirmed "Kings occupy the low
  ids, id 99 is the Valhalla-reserved slot" findings (Phase 330,
  Phase 339) exactly, now with a real mechanism behind them.
- **Duplicates**: `Gabriel` (ids 46, 212) and `Ishtar` (ids 57, 231) --
  both real, both kept verbatim (not deduplicated); only the 250-leader
  variant can ever expose both members of either pair in the same game
  (100 and 175-leader games never reach past id 174).

**Empirically re-verified against the real, committed `GW3__T1`
fixture (10-kingdom game, so Kings occupy ids 0-9)**: **89 of its 90
real Hero names now match this table exactly**, at unique ids forming
one unbroken run from 10 through 98 -- zero collisions, zero gaps, a
strictly better result than Phase 339's own 88/90 with two gap-filling
guesses. The one remaining unmatched name, `Kitralus`, is confirmed
**absent from `LNAMES.PAS`** (checked programmatically against every
one of the 255 entries) -- consistent with Phase 339's own conclusion
that it is a real `VALHALLA NEUTRAL.txt` visitor occupying the
reserved id-99 slot, not a data error.

**Two concrete corrections to Phase 339's own table, found directly by
this re-verification**:

- Ids 0-3 were previously `Adam`, `Eve`, `Abel`, and a name for id 3 --
  unverifiable guesses, since every fixture this project has ever
  cross-checked against is a 4-or-more-kingdom game (ids 0-3 are always
  King-occupied). The real `LNAMES.PAS` values are `Alanus`, `Bubka`,
  `Cecil`, `Daedona`. Every id from 4 through 98 in Phase 339's own
  table was already correct.
- Id 75 was previously `Atlas`, and its real fixture mismatch was
  wrongly attributed to a Valhalla arrival (the same excuse that
  correctly explains `Kitralus`). The real value is `Bagmore` -- itself
  a real `GW3__T1` Hero name, now matched -- meaning `Bagmore` was
  never a Valhalla case at all, just a single wrong table entry.

**Sex is not part of `LNAMES.PAS` at all** (confirmed: the JSON
catalog's own entries carry no sex field), so Phase 339's per-name Sex
values were guesses from name appearance alone -- and several are now
known wrong (e.g. `Isis` and `Kishijoten`, both mythological goddess
names, were marked `MALE`). The real mechanism is a separate,
AK.EXE/AK.OVR-side runtime rule (`AKGEN_reverse_engineering_report.md`,
byte 20 of the leader status row): "the sex-determination function
starts from the default female band of leaders 80-95, and if the
[per-leader override] flag is 1, inverts the result." `default_hero_sex()`
below realizes the unconditional default half of that rule (every id
80-95 inclusive defaults Female, every other id defaults Male) -- the
per-leader override flag itself is a separate, rare, persistent
runtime bit (confirmed only for two specific leaders, `Hume` from turn
4 and `Clarambald` from turn 8, in the real corpus) with no known
general rule for which leader acquires it or when, so it is
**deliberately not modeled here**, the same "don't invent past what's
sourced" treatment as every other genuinely open gap in this project.

`#99` remains deliberately absent from `STANDARD_HERO_ROSTER` -- the
reserved Valhalla-visitor slot, never a `LNAMES.PAS` entry itself (see
`models/valhalla.py`).
"""

from __future__ import annotations

from ak_engine.models.sex import Sex

# `world_generation.hero_names.standard_leader_counts` -- how many of
# `STANDARD_HERO_ROSTER`'s own sequential entries (ids `0..count-1`)
# a game actually draws from, by game version.
LEADER_COUNT_BY_GAME_VERSION: dict[str, int] = {
    "game_version_3_or_earlier": 100,
    "game_version_4_or_later_Arcanes_V": 175,
    "game_version_4_or_later_other_standard_types": 250,
}

# Verbatim from `LNAMES.PAS` (via `AKGEN_name_catalogs.json.txt`'s own
# `hero_names.entries`), 0-based id = source line - 1. `id` here is the
# same numbering this project's own `LeaderState.leader_id` already
# uses for every non-King leader (Phase 330/339's own finding).
STANDARD_HERO_ROSTER: dict[int, str] = {
    0: 'Alanus',
    1: 'Bubka',
    2: 'Cecil',
    3: 'Daedona',
    4: 'Elegorn',
    5: 'Fafax',
    6: 'Gogolak',
    7: 'Hahar',
    8: 'Ilikuth',
    9: 'Enlil',
    10: 'Kokocala',
    11: 'Lallipugh',
    12: 'Alexius',
    13: 'Ningarl',
    14: 'Saladin',
    15: 'Girard',
    16: 'Everard',
    17: 'Stonebrick',
    18: 'Guerin',
    19: 'Arnulf',
    20: 'Clarambald',
    21: 'Behemond',
    22: 'Alaric',
    23: 'Snorri',
    24: 'Tancred',
    25: 'Rainulf',
    26: 'Oakley',
    27: 'Fingol',
    28: 'Adhemar',
    29: 'Amalric',
    30: 'Melantheus',
    31: 'Reynald',
    32: 'Tao-Li',
    33: 'Alain',
    34: 'Dreux',
    35: 'Helatia',
    36: 'Geoffrey',
    37: 'Jolin',
    38: 'Dracona',
    39: 'Drago',
    40: 'Korchnoi',
    41: 'Bairn',
    42: 'Garin',
    43: 'Tarsus',
    44: 'Drake',
    45: 'Thorus',
    46: 'Gabriel',
    47: 'Tilden',
    48: 'Lexington',
    49: 'Constantine',
    50: 'Duqaq',
    51: 'Robin',
    52: 'Riose',
    53: 'Charious',
    54: 'Attla',
    55: 'Rolando',
    56: 'Hawkins',
    57: 'Ishtar',
    58: 'Elmer',
    59: 'Thrym',
    60: 'Eric',
    61: 'Magnus',
    62: 'Kurtinaitis',
    63: 'Marlboro',
    64: 'Lakes',
    65: 'Migfox',
    66: 'Aegir',
    67: 'York',
    68: 'Marlon',
    69: 'Adonis',
    70: 'Philo',
    71: 'Gladstone',
    72: 'Teleko',
    73: 'Presto',
    74: 'Ashley',
    75: 'Bagmore',
    76: 'Cortez',
    77: 'Hume',
    78: 'Pascal',
    79: 'Hakim',
    80: 'Jamielle',
    81: 'Kari',
    82: 'Astelle',
    83: 'Adele',
    84: 'Hecate',
    85: 'Inanna',
    86: 'Brunhilda',
    87: 'Tiffany',
    88: 'Tlazolteotl',
    89: 'Isis',
    90: 'Bouticca',
    91: 'Indra',
    92: 'Loviatar',
    93: 'Kishijoten',
    94: 'Hope',
    95: 'Samantha',
    96: 'Raiden',
    97: 'Odysseus',
    98: 'Negumba',
    99: 'Bellerophon',
    100: 'Achilles',
    101: 'Ilmarinen',
    102: 'Osiris',
    103: 'Silvanus',
    104: 'Mannanan',
    105: 'Managgen',
    106: 'Marhaus',
    107: 'Melias',
    108: 'Meliot',
    109: 'Miles',
    110: 'Naram',
    111: 'Ontzlake',
    112: 'Pelleas',
    113: 'Percard',
    114: 'Percivale',
    115: 'Alisander',
    116: 'Allardin',
    117: 'Bagdemagus',
    118: 'Balin',
    119: 'Barant',
    120: 'Abellius',
    121: 'Ablamor',
    122: 'Accolon',
    123: 'Aglovale',
    124: 'Agravaine',
    125: 'Lucan',
    126: 'Brandiles',
    127: 'Breunor',
    128: 'Cador',
    129: 'Caradoc',
    130: 'Palomides',
    131: 'Lamorak',
    132: 'Loren',
    133: 'Hiawatha',
    134: 'Raven',
    135: 'Fairfax',
    136: 'Yunix',
    137: 'Hytec',
    138: 'Irata',
    139: 'Agima',
    140: 'Hsotnicam',
    141: 'Safere',
    142: 'Sagramour',
    143: 'Sorlons',
    144: 'Trantrist',
    145: 'Ulfius',
    146: 'Dinadan',
    147: 'Ector',
    148: 'Elias',
    149: 'Ewaine',
    150: 'Feldenak',
    151: 'Floridas',
    152: 'Gahalatine',
    153: 'Gaheris',
    154: 'Gainus',
    155: 'Carados',
    156: 'Chestelaine',
    157: 'Greystoke',
    158: 'Neville',
    159: 'Beaufort',
    160: 'Caro',
    161: 'Aubrey',
    162: 'Arnult',
    163: 'Alberard',
    164: 'Eustace',
    165: 'Dudo',
    166: 'Conon',
    167: 'Gaston',
    168: 'Isoard',
    169: 'Balian',
    170: 'Leopold',
    171: 'Lorens',
    172: 'Ansel',
    173: 'Comain',
    174: 'Nicholas',
    175: 'Angeram',
    176: 'Rohart',
    177: 'Isaac',
    178: 'Gilmere',
    179: 'Gouvernail',
    180: 'Hector',
    181: 'Helior',
    182: 'Herlen',
    183: 'Antipater',
    184: 'Bessus',
    185: 'Kehydius',
    186: 'Lanceor',
    187: 'Lionel',
    188: 'Uwaine',
    189: 'Andred',
    190: 'Breunis',
    191: 'Gringamore',
    192: 'Helius',
    193: 'Meleagrance',
    194: 'Pinell',
    195: 'Turquine',
    196: 'Percy',
    197: 'Audley',
    198: 'Cromwell',
    199: 'Chamberlain',
    200: 'Espinal',
    201: 'Molembec',
    202: 'Raoul',
    203: 'Joscelyn',
    204: 'Hervis',
    205: 'Hontzlake',
    206: 'Tiberias',
    207: 'Claudius',
    208: 'Augustus',
    209: 'Rutger',
    210: 'Blondal',
    211: 'Barthold',
    212: 'Gabriel',
    213: 'Howorth',
    214: 'Clairemonde',
    215: 'Clegis',
    216: 'Dagonet',
    217: 'Darras',
    218: 'Permimones',
    219: 'Persante',
    220: 'Pertelope',
    221: 'Priamus',
    222: 'Sadok',
    223: 'Leondegrance',
    224: 'Belleus',
    225: 'Berel',
    226: 'Blamor',
    227: 'Bleaberis',
    228: 'Urians',
    229: 'Chulainn',
    230: 'Ramman',
    231: 'Ishtar',
    232: 'Tristram',
    233: 'Galagers',
    234: 'Gaunter',
    235: 'Komroff',
    236: 'Marzials',
    237: 'Munroe',
    238: 'Nicol',
    239: 'Agenor',
    240: 'Belus',
    241: 'Gordius',
    242: 'Mithras',
    243: 'Pollux',
    244: 'Typho',
    245: 'Tithonus',
    246: 'Blanchegarde',
    247: 'Quastrin',
    248: 'Demetrius',
    249: 'Meleager',
    250: 'Craterus',
    251: 'Tauron',
    252: 'Olympias',
    253: 'Perdiccas',
    254: 'Danilo',
}

# `AKGEN_reverse_engineering_report.md`'s own confirmed default-sex band
# -- see module docstring for the full rule, including the deliberately
# unmodeled per-leader override flag.
DEFAULT_FEMALE_ID_RANGE = range(80, 96)


def default_hero_sex(hero_id: int) -> Sex:
    """The confirmed default half of the sex-determination rule: ids 80-95
    inclusive default Female, every other id defaults Male. Does not model
    the separate, rare, persistent per-leader override flag -- see module
    docstring."""

    return Sex.FEMALE if hero_id in DEFAULT_FEMALE_ID_RANGE else Sex.MALE


# Reverse lookups for `parser/gw_world_bridge.py`'s own name-matching use
# (Phase 339/366): built in id order, keeping the *first* occurrence of a
# duplicated name (`Gabriel`, `Ishtar`) -- the lower, always-in-range id,
# matching every game version rather than only the 250-leader one.
STANDARD_HERO_ID_BY_NAME: dict[str, int] = {}
for _id, _name in STANDARD_HERO_ROSTER.items():
    STANDARD_HERO_ID_BY_NAME.setdefault(_name, _id)
del _id, _name

STANDARD_HERO_SEX_BY_NAME: dict[str, Sex] = {
    name: default_hero_sex(hero_id) for name, hero_id in STANDARD_HERO_ID_BY_NAME.items()
}
