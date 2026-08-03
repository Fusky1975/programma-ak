"""Province name pools, by terrain (Phase 366 rewrite of Phase 152).

**Corrects Phase 152's own central premise.** That phase built these
pools from a project-original reference document (the user's own
`Desktop/Nomi province.txt`), explicitly because Phase 150's research
had concluded the real host engine never generates a province name at
runtime at all, and `AKGEN.EXE` -- the offline tool that actually would
have picked them -- had no surviving source in the archive. A later
reverse-engineering pass over `AKGEN.EXE`
(`AKGEN_reverse_engineering_report.md`, `AKGEN_name_catalogs.json.txt`)
found that source after all: `PRNAMES.PAS` (``k:\\tp\\prnames.pas``,
read by `Place_L` at `0006:41FB`), a real Pascal-readable text file
AKGEN opens line-by-line -- 512 short-string lines, at most 20
characters each. **Confirmed exactly**:

- **Pool layout**: the 512 lines are not one shared deck -- they are
  already grouped by terrain, contiguously, in this fixed order:
  Plains 0-49 (50), Desert 50-99 (50), Jungle 100-149 (50), Forest
  150-199 (50), Mountains 200-249 (50), Sea 250-511 (262).
- **Selection**: "uniform random source index inside the terrain
  pool; source indices already used are rejected and redrawn" -- this
  project's own pre-existing `turn/rename_province.py
  assign_province_name()` (Phase 152) already implements exactly this
  "prefer an unused name, reject and redraw on collision" idea (there
  independently, as its own undocumented design choice) -- it needed
  no change, only this module's own data underneath it.
- **Retry fallback**: "after more than 100 failed redraws AKGEN
  broadens the candidate interval" -- not reachable on any ordinary
  18x9 world (confirmed in the source material; a pool of 50-262 names
  against at most 162 provinces never gets that starved), so not
  modeled here.
- **Duplicate semantics**: uniqueness is tracked by source index, not
  display text -- `PRNAMES.PAS` itself contains two duplicate-spelling
  pairs (`the Hammerhead Sea` at ids 287/318, `the Otter Sea` at ids
  475/477), confirmed to both genuinely appear as two same-named
  provinces in the real `GW900` corpus. This project's own
  `ProvinceState.name` is a plain string with no separate index field,
  so `assign_province_name()`'s own "prefer unused *text*" tie-break
  will usually avoid reproducing that duplicate spontaneously (unlike
  the real engine, which can produce it any time both indices happen
  to be drawn) -- a known, minor, deliberately-accepted simplification
  of the real algorithm, not a data change; the pool tuples below still
  keep both spellings verbatim, undeduplicated, matching the source.

**Empirically re-verified against the real, committed `GW3__T1`
fixture**: **all 162 of its own province names match this catalog
exactly** (programmatically checked, zero misses) -- a strictly
stronger result than Phase 152's own pools, which were never
cross-checked against real fixture data at all (Phase 152's own
docstring never claims such a check).

`Terrain.NO_TERRAIN` has no pool: it marks the absence of a real
terrain type (`map.py`'s own catch-all), so there is nothing to name.

**Deliberately not modeled here**: `AKGEN`'s own `Europe_V`/`Earth_V`
fixed-map variants skip `PRNAMES.PAS` entirely and read a name already
baked into the map file per cell instead (confirmed in the same
reverse-engineering material, e.g. `EUROPE.TXT.old`) -- a distinct,
separate data source (and gameplay mode) from the random-map pools
here; out of scope for this phase.
"""

from __future__ import annotations

from ak_engine.models.map import Terrain

# Verbatim from `PRNAMES.PAS` (via `AKGEN_name_catalogs.json.txt`'s own
# `random_province_names.entries`), grouped by terrain in the source's
# own contiguous id-range order. Not deduplicated (see module
# docstring's own note on the two real duplicate-spelling Sea pairs).
PROVINCE_NAME_POOLS: dict[Terrain, tuple[str, ...]] = {
    Terrain.PLAINS: (
        'Candelaria', 'Rosehaven', 'Vinland', 'Orielle', 'Valentine',
        'Cimarron', 'Santiago', 'Blue Springs', 'Istaria', 'Silvania',
        'Florence', 'Piratum', "Milo's Crossroads", 'Quantara Roo', 'Tipperary',
        'Kilkenny', 'Donegal', 'Kildare', 'Limerick', 'Chaco',
        'Jaguardo', 'Cantu', 'Veraval', 'Hollabrand', 'Chandrapur',
        'Marathon', 'Galway', 'Connemara', 'Offaly', 'Kerry',
        'Waterford', 'Fermanagh', 'Tyrone', 'Monaghan', 'Munster',
        'Buckingham', 'Lancashire', 'Khalturin', 'Atkarsk', 'Balanda',
        'Kaluga', 'Vyazma', 'Kajaani', 'Mercia', 'Saxonia',
        'Cantia', 'Northumbria', 'Damnonia', 'Anglia', 'Jutland',
    ),
    Terrain.DESERT: (
        'Jerbilia', 'Erg Iguidi', 'Erg Nafud', 'Erg Jabal', 'Erg Khali',
        'Javir', 'Takla Maklan', 'Chahaerh', 'Al Kufrah', 'Al Jawf',
        'Al Qusayr', 'Al Khandaq', 'Khurum', 'Jabal Marak', 'Mabrouk',
        'Arrak', 'Uman', 'Turku', 'Marzuq', 'Al Jazirah',
        'El Alamein', 'Tabuk', 'El Kharga', 'Bir Atrun', 'Kordofan',
        'Bir Nzaran', 'El Kalaa', 'Ain-Salah', 'Berga', 'Bizerte',
        'Tebessa', 'Gafsa', 'Kasserine', 'Jebel el Gharb', 'Chirfa',
        'Misurata', 'Marada', 'Bir Hakeim', 'Tagrifet', 'Tesawa',
        'Arada', 'Moussoro', 'Bokoro', 'Kutum', 'Dar Masalit',
        'Umm Keddada', 'Abu Matariq', 'Meshra er Req', 'Rejaf', 'Kassala',
    ),
    Terrain.JUNGLE: (
        'Oaxaca', 'Zacatecas', 'Kalamazoo', 'Couatlia', 'Zululand',
        'Mau Mau', 'Ahdogast', 'Unita', 'Bam Yanga', 'Impfondo',
        'Kisangani', 'Kapanga', 'Sikalongo', 'Mumbwa', 'Kafwira',
        'Majunga', 'Keetmanshoop', 'Japura', 'Urubamba', 'Jacunda',
        'Maicuru', 'Uatuma', 'Kumasi', 'Nsukka', 'Wukari',
        'Mungari', 'Unango', 'Mandimba', 'Mbamba', 'Tabora',
        'Kasulu', 'Ngara', 'Kampala', 'Kaabonga', 'Kwilu',
        'Katanga', 'Kambova', 'Malonga', 'Ouango', 'Zongo',
        'Irumu', 'Mambasa', 'Djambala', 'Cazombo', 'Macondo',
        'Mongu', 'Kalabo', 'Kabompo', 'Kawambwa', 'Kulungu',
    ),
    Terrain.FOREST: (
        'Sherwood', 'Black Forest', 'Oakhaven', 'Elmhaven', 'Ravenwood',
        'Sprucehaven', 'Maplehaven', 'Tanglewood', 'Darkwood', 'Ashwood',
        'Wormwood', 'Bearhome', 'Wolfhome', 'Goldleaf', 'Silverleaf',
        'Bronzeleaf', 'Enthome', 'Blue Forest', 'Dirkwood', 'Sequoia',
        'Redwood', 'Birchwood', 'Lynxhome', 'Beaverhome', 'Applewood',
        'Plumwood', 'Elkhome', 'Starhaven', 'Pinehaven', 'Siouxhome',
        'Arapahome', 'Warghaven', 'Gnarlia', 'Knotwood', 'Copperleaf',
        'Acacia', 'Alderwood', 'Balmwood', 'Belladonna', 'Cherrywood',
        'Marigold', 'Peachwood', 'Wintergreen', 'Rosewood', 'Sageleaf',
        'Lakewood', 'Amberleaf', 'Badgerhome', 'Wolverine', 'Tigerhome',
    ),
    Terrain.MTNS: (
        'Denali', 'Wrangell', 'Katmai', 'Kiska', 'Transylvania',
        'Shasta', 'Bighorn', 'Sheridan', 'San Andreas', 'Mammoth',
        'Seleka', 'Carabinia', 'Falkenheim', 'Olympus Mons', 'Novus Mons',
        'Cambria', 'Devonia', 'Jurassus', 'Cretacia', 'Tyrannia',
        'Triceria', 'Allosia', 'St Helens', 'Chimborazo', 'Ancohuma',
        'Eaglehome', 'Condorhome', 'Cascadia', 'Trouthome', 'Matterhorn',
        'Cristobal', 'Apurimac', 'Vilcanota', 'Huascaran', 'Cotopaxi',
        'El Misti', 'Atacama', 'Aconga', 'Big Sky', 'Silvermist',
        'Mazama', 'Stonegard', 'Irongard', 'Talongard', 'Moongard',
        'Horngard', 'Vulgard', 'Jadegate', 'Pearlgate', 'Coralgate',
    ),
    Terrain.SEA: (
        'Mare Imbrium', 'Oceanus Stormium', 'Mare Frigidis', 'Mare Serenitus', 'Mare Tranquillium',
        'Mare Nectaris', 'Mare Fecundis', 'Mare Australe', 'Oceanus Humorum', 'Mare Nubium',
        'Mare Vaporum', 'Mare Crisium', 'Oceanus Orientale', 'Mare Moscoviense', 'Mare Roris',
        'Mare Iridum', 'the Waterford Sea', 'the Marianas Sea', 'the Sargasso Sea', 'the Bermuda Triangle',
        'the Cannibal Sea', 'the Caroline Sea', 'the Marshall Sea', 'the Solomon Sea', 'the Bonin Sea',
        'the Ryukyu Sea', 'the Kurile Sea', 'the Cocos Sea', 'the Barrier Sea', 'the Coral Sea',
        'the Bismarck Sea', 'the Gilbert Sea', 'the Ellice Sea', 'the Arrak Sea', 'the Galapagos Sea',
        'the Christmas Sea', 'the Kodiak Sea', 'the Hammerhead Sea', 'the Bering Sea', 'the Hudson Sea',
        'the Barents Sea', 'the Falkland Sea', 'the Sandwich Sea', 'the Madeira Sea', 'the Balearic Sea',
        'the da Cunha Sea', 'the Seychelles Sea', 'the Maldive Sea', 'the Aries Sea', 'the Tauus Sea',
        'the Gemini Sea', 'the Leo Sea', 'the Virgo Sea', 'the Wukari Sea', 'the Cancer Sea',
        'the Scorpio Sea', 'the Sagittarius Sea', 'the Capricornus Sea', 'the Aquarius Sea', 'the Pisces Sea',
        'the Polaris Sea', 'the Sirius Sea', 'the Centauri Sea', 'the Milky Way Sea', 'the Crab Sea',
        'the Marlin Sea', 'the Irish Lord Sea', 'the Great White Sea', 'the Hammerhead Sea', 'the Albatross Sea',
        'the Tiger Sea', 'the Wolfhome Sea', 'the Jellyfish Sea', 'the Octopus Sea', 'the Nessie Sea',
        'the Squid Sea', 'the Seahorse Sea', 'the Starfish Sea', 'the Nautilus Sea', 'the Orca Sea',
        'the Mercury Sea', 'the Venusian Sea', 'the Terran Sea', 'the Martian Sea', 'the Jupiter Sea',
        'the Saturnian Sea', 'the Neptunian Sea', 'the Uranus Sea', 'the Plutonic Sea', 'the Matterhorn Sea',
        'the Lunar Sea', 'the Deimos Sea', 'the Callisto Sea', 'the Io Sea', 'the Ganymede Sea',
        'the Europa Sea', 'the Memnonian Sea', 'the Amazonian Sea', 'the Arcadian Sea', 'the Tharsis Sea',
        'the Thaumasian Sea', 'the Argyre Sea', 'the Electris Sea', 'the Zephyrian Sea', 'the Xanthe Sea',
        'the Chryse Sea', 'the Elysium Sea', 'the Daedalus Sea', 'the Icaria Sea', 'the Atlantis Sea',
        'the Hellespont Sea', 'the Aethiopis Sea', 'Oceanus Acidium', 'Mare Boreum', 'Mare Chronium',
        'Oceanus Cimmerium', 'Mare Hadriatum', 'Mare Ionium', 'Oceanus Serpentis', 'Mare Sirenum',
        'Mare Tyrrhenium', 'Oceanus Nepenthes', 'Mare Aurorae', 'Mare Craterus', 'Oceanus Cyclopia',
        'Mare Buamota', 'Mare Atlasta', 'Mare Finalis', 'the El Kalaa Sea', 'the Green Sea',
        'the Cyan Sea', 'the Magenta Sea', 'the Yellow Sea', 'the Purple Sea', 'the Burgundy Sea',
        'the Whiskey Sea', 'the Bordeaux Sea', 'the Moonshine Sea', 'the Rotgut Sea', 'the Champagne Sea',
        'the Near-Beer Sea', 'the Powermaster Sea', 'the Vodka Sea', 'the Cider Sea', 'the Cognac Sea',
        'the Armagnac Sea', 'the Kilkenny Sea', 'the Cool Sea', 'the Mermaid Sea', 'the Dolphin Sea',
        'the Norseman Sea', 'the Mariner Sea', 'the Platinum Sea', 'the Gold Sea', 'the Silver Sea',
        'the Royal Sea', 'the Clam Sea', 'the Barnacle Sea', 'the Cetacean Sea', 'the Iceberg Sea',
        'the Tubular Sea', 'the Drowning Sea', 'the Saltine Sea', 'the Sunshine Sea', 'the Majunga Sea',
        'the Reef Sea', 'the Albacore Sea', 'the Plankton Sea', 'the Acidic Sea', 'the Coho Sea',
        'the Salmon Sea', 'the Mollusk Sea', 'the Angel Sea', 'the Piranha Sea', 'the Flying Fish Sea',
        'Mare Tarkium', 'Mare Shulium', 'Mare Granium', 'Mare Rilium', 'Mare Adelium',
        'Mare Scornium', 'Mare Gorbium', 'Mare Yeltium', 'Mare Stalium', 'Mare Ritalis',
        'Mare Tchaikovsky', 'Mare Rachmaninov', 'Mare Mozartis', 'Mare Bachium', 'Mare Ravelis',
        'Mare Pisium', 'Mare Dalium', 'Mare Provencium', 'Mare Alsacium', 'Mare Rhonius',
        'Mare Gaillius', 'Mare Jurancis', 'Mare Anjouie', 'Mare Tourium', 'Mare Toulonis',
        'the Stonegard Sea', 'the Lobster Sea', 'the Giant Crab Sea', 'the Giant Squid Sea', 'the Crabman Sea',
        'the Crocodile Sea', 'the Alligator Sea', 'the Frog Sea', 'the Fog Sea', 'Mare Mantaris',
        'the Buccaneer Sea', 'the Thork Sea', 'the Elasmosaurus Sea', 'the Plesiosaurus Sea', 'the Killer Frog Sea',
        'the Killer Whale Sea', 'the Mad Dolphin Sea', 'the Nixie Sea', 'the Nymph Sea', 'the Turtle Sea',
        'the Water-Weird Sea', 'the Crayfish Sea', 'the Koalinth Sea', 'the Lacedon Sea', 'the Mirkwood Sea',
        'the Otter Sea', 'the Water-Naga Sea', 'the Otter Sea', 'the Giant Pike Sea', 'the Ixitxachitl Sea',
        'the Merman Sea', 'the Sahuagin Sea', 'the Shark Sea', 'the Triton Sea', 'the Giant Turtle Sea',
        'Mare Archelona', 'Mare Dinicthys', 'the Cretacia Sea', 'the Deep Blue Sea', 'the First Sea',
        'the Second Sea', 'the Third Sea', 'the Fourth Sea', 'the Fifth Sea', 'the Sixth Sea',
        'the Seventh Sea', 'the Enterprise Sea', 'the Ark Royal Sea', 'the Tirpitz Sea', 'the Musashi Sea',
        'the Andrea Doria Sea', 'the Yamato Sea', 'the Constitution Sea', 'the Rodney Sea', 'the Monitor Sea',
        'the Merrimack Sea', 'the Akagi Sea', 'the Valiant Sea', 'Mare Nelsonus', 'Mare Alexandrium',
        'Mare Actium', 'the Lepanto Sea',
    ),
}
