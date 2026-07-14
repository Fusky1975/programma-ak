"""Province name pools, by terrain -- Phase 152.

**Project-original, not a Pascal transcription.** Phase 150's own research
confirmed the real host engine never generates a province name at runtime
at all: names are baked into the world-generated map by `AKGEN.EXE`, an
offline tool whose own source isn't present in `Programma Pascal.zip` --
so there is no `pname^[x,y]`-filling algorithm anywhere in the archive to
transcribe. That gap was previously left as a permanent, unfillable
`ProvinceState.name = None`.

The user supplied this exact name list directly (`Desktop/Nomi
province.txt`, 2026-07-14), organized by terrain, and asked for it to
close that gap -- the same "user authors replacement content for a
confirmed-unsourced gap, explicitly labeled as project-original" pattern
already established for Use_MI's skill-book-read narrative (Phase 148).
Every name below is transcribed verbatim from that file, in the same
order, including its two incidental repeats in the Sea pool ("Frog Sea",
"Pocket Sea" each appear twice in the source list) -- not deduplicated,
since this is the user's own supplied data, not something to silently
"fix".

`Terrain.NO_TERRAIN` has no pool: it marks the absence of a real
terrain type (`map.py`'s own catch-all), so there is nothing to name.
"""

from __future__ import annotations

from ak_engine.models.map import Terrain

PROVINCE_NAME_POOLS: dict[Terrain, tuple[str, ...]] = {
    Terrain.DESERT: (
        "Al Jair", "Jurbjal", "Klashib", "El Hadwi", "Abu Gornk",
        "Mojave", "Yuma", "Ub Sonora", "Borrego", "Sand Rock",
        "Escalante", "Magdalena", "Smoke Creek", "Vizcaino", "Yuha",
        "Kalahari", "Okavango", "Makajuhl", "Kavir Lut", "Atacama",
        "El Gobi", "Kyzyl Kum", "Tanami", "Rangipo", "Negev",
        "Thar Cholistum", "Al Mharisha", "Roger Playa", "Taklamakan", "Quaib",
    ),
    Terrain.FOREST: (
        "Amazonia", "Conecuch", "Talladega", "Tuskgeewood", "Coronado",
        "Ozarkwood", "Klamath", "Lassen", "Modocwood", "Holy Spring",
        "Sequoia", "Six Rivers", "Panwee", "Uncompahgre", "Osceola",
        "Clearwater", "Payette", "Sawtooth", "Shawnee", "Hoosierwood",
        "Bitterwood", "Kootenai", "Gallatin", "Fingerwood", "Wallowa",
        "Ritablanca", "Collwille", "Thunderwood", "Marstone", "Bracknell",
        "Sherwood", "Newford", "Ashdown", "Wyrewood", "Mercia",
        "Clocaenog", "Kielder", "Merseywood", "Argylwood", "Dundeugh",
        "Penninghame", "Laurieston", "Tairlaw", "Cleanwood", "Strathyre",
        "Ballypatrick", "Purewood", "Glenariff", "Tollymore", "Castewellan",
    ),
    Terrain.JUNGLE: (
        "Mitumba", "Virunga", "Suggeema", "Apukwa", "Hiawatha",
        "Jacala", "Karela", "Nushka", "Onaway", "Kolkata",
        "Pukeena", "Rikki-Tikki", "Shadda", "Tabaqui", "Wabeeno",
        "Kwasin", "Manyara", "Arusha", "Meerkat", "Empakaai",
        "Bagongho", "Sabah", "Borneo", "Walla-walla", "Rafflesia",
        "Kinabalu", "Padasgorge", "Melalap", "Putatan", "Mandinka",
        "Chiquibil", "Kinkajous", "Macal", "Stacalamba", "Umatilla",
        "Wanapum", "Mokele", "Hottentot", "Dawuewe", "Rotswana",
    ),
    Terrain.SEA: (
        "Yellow Sea", "Red Sea", "Brown Sea", "Blood Sea", "Rose Sea",
        "Frog Sea", "Black Sea", "Last Sea", "Jog Sea", "Large Sea",
        "Narrow Sea", "Gust Sea", "Fast Sea", "Marble Sea", "Deep Sea",
        "Sand Sea", "Brick Sea", "Girl's Sea", "Dead Sea", "Kurst Sea",
        "Pollux Sea", "Medium Sea", "Frog Sea", "Scilla Sea", "Numbers Sea",
        "Men's Sea", "Victory Sea", "Beautiful Sea", "Ghost Sea", "Peace Sea",
        "Smile Sea", "Blue Sea", "Heaven Sea", "Night Sea", "Close Sea",
        "Eyes Sea", "Pocket Sea", "Stone Sea", "Cyclops Sea", "Far Sea",
        "Pocket Sea", "Winter Sea", "Ice Sea", "Wanted Sea", "Line Sea",
        "Lantern Sea", "East Sea", "South Sea", "West Sea", "North Sea",
        "Bath Sea", "Marlon Sea", "Jet Sea", "Lux Sea", "Oster Sea",
        "Khile Sea", "Pox Sea", "Dark Sea", "Ialta Sea", "Locust Sea",
        "Minor Sea", "Palliet Sea", "Lagoon Sea", "Rust Sea", "Quantum Sea",
        "Eghule Sea", "Summer Sea", "Dent Sea", "Iron Sea", "Zamter Sea",
        "Inner Sea", "Sun Sea", "Rish Sea", "Yule Sea", "Dragon Sea",
        "Moon Sea", "Wide Sea", "Belt Sea", "Triangle Sea", "Square Sea",
    ),
    Terrain.MTNS: (
        "Blue Ridge", "Cherangany", "Great Smoke", "Drakensberg", "Appalachia",
        "Livingstone", "Black Mount", "Aberdare", "Ruwenzory", "Queen Maud",
        "Barisan", "Crockem", "Fliderhome", "Star Mount", "Thurnwald",
        "Pegunungan", "Alps", "Sudirman Mount", "Hamersley", "Alborz",
        "Altay", "Corldillera", "East Ghats", "Chin Hill", "Gydan Mount",
        "Pamir", "Hinda Mount", "Dinaric", "Khingan", "Sierra",
        "Kunlun", "Stanovoi", "Sulaiman", "Taurus Mount", "Titiwangsa",
        "Endless Mount", "Verkhoyansk", "Dolomites", "Beskidy", "Dentelles",
        "Karelides", "Pennine Mount", "Vogelsberg", "Wicklow Mount", "Aleutia",
        "Zagros", "White Mount", "Oquirrh", "Panamint", "Schwatka",
    ),
    Terrain.PLAINS: (
        "Smeraldine", "Pontinas", "Cobaya", "Donbass", "Monferrate",
        "Rodan", "Ladogus", "Achensee", "Rimmingas", "Bask",
        "Padania", "Magnon", "Agirocastrus", "Villanovian", "Wessex",
        "Marshall", "Mugania", "Apollonia", "Haapsalum", "Gullfoss",
        "Daugavpills", "Gamprin", "Klaipeda", "Steinamanger", "Cabriels",
        "Elchein", "Chischima", "Muromed", "Iranovo", "Dimri",
        "Buxton", "Gellingaer", "Hendon", "Gallonway", "Listburn",
        "Northallerton", "Mardston Moorn", "Pevensey", "Poole", "Rhondda",
        "Stimling", "Roshdale", "Worthing", "Trowbridge", "Zetaland",
        "Swindon", "Ramgate", "Cascamus", "Ostwoch", "Hoorn",
    ),
}
