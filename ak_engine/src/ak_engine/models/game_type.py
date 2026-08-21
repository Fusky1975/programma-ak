"""``GameType`` -- the world header's own `gametyp` enum (header field 22).

Moved here from `parser/gw_world.py` (Phase 538) so `models/game_state.py`
can read `GameState.game_type` without `models/` importing from `parser/`
-- this project's own established import direction is parser depends on
models, never the reverse. `parser/gw_world.py` re-imports it from here,
so every existing `from ak_engine.parser.gw_world import GameType` call
site keeps working unchanged.
"""

from __future__ import annotations

from enum import Enum


class GameType(Enum):
    """Confirmed directly from a static reverse engineering of AKGEN.EXE
    (see `parser/gw_world.py`'s own module docstring, Phase 342 addendum),
    not inferred from real letters. Every one of the real `GW3__T1`-
    `GW3__T12` files reads `NORMAL`.
    """

    TRIAL = 0
    NORMAL = 1
    EUROPE = 2
    EARTH = 3
    VALHALLA = 4
    ARCANES = 10


# HostAK/TP/PROSE/EARTH.X2 (header "31 2", SAY.PAS:1283 `_LEarth: FD(
# 'earth.x2', S_Red, 1001+_ldr1)`) -- the real flavor text and starting-
# bonus description for each of the GameType.EARTH scenario's own
# historical starting empires, keyed by `_ldr1+1` (this project's own
# established "raw file position" convention, matching NEMESIS_TEMPLATE/
# TACTICS.X2/ILLMOVE_TEMPLATE -- no dedicated enum is built for the 28
# empires since nothing in this project resolves a real Kingdom to its
# own `_ldr1` yet). Sourced from a byte-faithful third-party reverse-
# engineering pass over the full 162-file prose corpus
# (`AKPROSE_reverse_engineering_report.md`, supplied directly by the
# user). Genuine, public-domain historical/mythological content (Rome,
# Carthage, Persia, the Aztecs, Atlantis, ...), not personal or
# real-individual data -- unlike the Valhalla catalogs (Phase 585), this
# family needed no redaction. `AKMAN.TXT`'s own confirmed 22-28 King
# range for a real Earth Variant setup means only ordinals 0-27
# (choices 1-28) are ever reachable in a real game; choices 29-31
# (ordinals 28-30) are a real but unreachable reserve, each a literal
# duplicate of choice 22's own "Lost Empire of Atlantis" text -- kept
# verbatim rather than deduplicated, since a caller indexing by ordinal
# still needs every key present. Choice 23 (ordinal 22, "New Atlantis")
# is the one real position in that block with its own distinct text.
EARTH_EMPIRE_DESCRIPTION: dict[int, str] = {
    1: 'Your empire in the Earth Variant game is the Roman Empire, which arose in about the fourth century BC, and was dismembered around 400-475 by invading barbarians, although the eastern half lasted until 1454 AD, and some remnants lasted until 1805 AD, when the Holy Roman Empire was officially dissolved.The Romans had a fine tactical system, held gladiatorial events with well-trained fighters, and had a fine system of roads throughout the empire.',
    2: 'Your empire in the Earth Variant game is the Empire of Carthage.Founded by Phoenician traders in about the 8th century BC, it was overthrown by Rome in the Punic wars, ending 202 BC.The Carthaginians had a great general in the famous Hannibal, and from the Phoenician legacy they inherited a fine navy and merchant fleet, as well as a great tradition of exploring (some Phoenicians even claimed to have circumnavigated Africa, 2000 years before Portugal did so).',
    3: 'Your empire in the Earth Variant game is the Persian Empire.Founded by Cyrus the Great around 550 BC, it lasted until Alexander the Great conquered it around 320 BC.The Persians invented a fast postal system using a sort of pony-express of horse relays, and developed Scythed Chariots for use against Alexander, though it ultimately did not turn the tide for them.The Persians also were good archers, relying heavily on bowmen in their battles.',
    4: 'Your empire in the Earth Variant game is Imperial India.Perhaps the oldest empire in the world, the Indians invented the game of chess, and possesed a great wealth of gold and spices.They were fine archers, relying greatly on those troops in battle, and their religion was one of great variety that sought harmony and included a great variety of philosophies.Consequently, Indian heroes start with good Archery and Druidism, and the Empire starts with 5 extra gold.',
    5: 'Your empire in the Earth Variant game is the Chinese Empire.China was a great center of learning, so their heroes start with good Sage and Spy ability and several sage discoveries.A wealthy empire, China also starts with 5 extra gold.',
    6: 'Your empire in the Earth Variant game is the Aztec Empire, founded around 1325 AD and overthrown by the Spanish Conquistador Hernano Cortez around 1519 AD.The Aztecs were fierce warriors who worshipped a strange serpent-God and practiced human sacrifice, so they start with good Melee, Tactical and Necromancy ability.Their famous city of Tenochticlan, built on a lake, was well-protected by ingenious flood dams.',
    7: 'Your empire in the Earth Variant game is the Incan Empire, which emerged around 1450 AD and lasted until its conquest by the Spanish Conquistador Pizarro around 1535 AD.The Incans were surrounded by mountains, but still managed to maintain their hold over subject peoples by the use of fierce, fast-moving troops moving over an impressively well-engineered road system.Consequently Incan leaders start with good March and Melee ability.',
    8: 'Your empire in the Earth Variant game is the Rus Empire.The Rus were a tribe of Viking warriors who moved into slavic Russia along the vast river systems, raiding and conquering from their river-going longboats.They start with good skill in Melee and Explorer abilities.The Vikings are also thought to have used a kind of magnetic lodestone for navigation.',
    9: 'Your empire in the Earth Variant game is the Zulu Empire, which arose in the 19th century, only to be crushed by the forces of the British Empire by the turn of the century.They start with good skill in Melee, March and Necromancy (to simulate their skill in the arts of the Witch Doctor).',
    10: 'Your empire in the Earth Variant game is the Egyptian Empire, which arose around 3000 BC.The Egyptian Empire has died and been resurrected in various forms under the Greeks, Arabs and Turks, as well as native rulers.They start with good skill in White Magic because of their respected and peace-loving priestly class, and also some Thief ability (historically, the Pharoah Alaric actually began his career as a thief).',
    11: 'Your empire in the Earth Variant game is the Empire of Attila the Hun.Attila welded together a great variety of Hunnish tribes from the Central Asian steppes, and menaced the Roman Empire from about 440 TO 460 AD.The Huns start with good skill in March, Melee and Archery ability.',
    12: 'Your empire in the Earth Variant game is the Mongolian Empire of Genghis Khan.The Mongols were excellent, fast-moving horse-archers with extraordinary cunning and a good tactical system.Their heroes start with good March, Archery and Tactical ability.',
    13: 'The Siberians conquered China in 1636 AD and established the Manchu Dynasty.Your characters start with good Archery and Explorer skills, and a special Winter Attack ability.During the entire Early Winter phase, the Tactical and March abilities of all your characters are increased by one point, while they are in the top 4 rows of the world-map, or any mountain province in the top 6 rows.At levels 4 and higher, you are given the special Tactical and March abilities for the next level, for winters only.',
    14: 'Your empire in the Earth Variant game is the Polynesian Tribes.You start controlling southwestern Australia.The Polynesians were great explorers and settlers of the Pacific Ocean, and had great navigational ability (they could often navigate between islands just by listening to how the waves struck their boat, which told them where they were).Consequently, their heroes start with good Explorer skill and excellent Naval skill.',
    15: 'Your empire in the Earth Variant game is the Amazonian Empire.This is a somewhat fanciful position, assumed to be led by fleet-footed female warriors.They start with good skill in March and Archery, and their intuitional ability of social manipulation also gives them good Druidic skill.',
    16: 'Your empire in the Earth Variant game is the Viking Explorers, such as Leif "the Lucky" Ericson.They tried to colonize Vinland (America) in the 11th century, but failed because they were too few in number and unable to stay at peace with the natives.Their heroes start with good Naval and Melee abilities.The Vikings are also thought to have used a kind of magnetic lodestone for navigation.',
    17: 'Your empire in the Earth Variant game is the American Indians.Your heroes start with good Archery and Explorer abilities, and their nature-worship gives them good Druidic skill as well.',
    18: 'Your empire in the Earth Variant game is the Hudson Bay Company, which established a network of trading posts throughout Canada in the eighteenth century.Your heroes start with good skill in Naval and Explorer abilities, and you also start with some nice trinkets (sage discoveries) to trade with the natives, and 5 extra gold.',
    19: 'Your empire in the Earth Variant game is the Eskimo Tribes of North America.Your heroes start with good Archery and Explorer skills, and a special Winter Attack ability.During the entire Early Winter phase, the Tactical and March abilities of all your leaders are increased by one point, while they are in the top 4 rows of the world-map, or any mountain province in the top 6 or bottom 4 rows.At levels 4 and up, you are given the special Tactical and March abilities for the next level, for winters only.',
    20: 'Your empire in the Earth Variant game is the Japanese Shogunate, of around 1500 AD.Your Samarai heroes start with good Melee and Archery ability.You also have good Spy ability, always a necessity in Japan, because of the many intrigues among the clans and secret societies such as the Ninja.',
    21: 'Your empire in the Earth Variant game is the Dutch East India Company, which established a network of trading posts throughout the East Indies in the seventeenth century.Your heroes start with good skill in Naval and Explorer abilities, and you also start with some nice trinkets (sage discoveries) to trade with the natives, and 2 extra gold.',
    22: 'Your empire in the Earth Variant game is the Lost Empire of Atlantis.The great philospher Plato mentioned this lost empire in his writings.According to ancient legend, it was a naval power led by sages of great wisdom, which kept its existence shrouded in secrecy by the use of powerful illusions.Consequently, your heroes start with good skill in Sage and Illusionist abilities, and the Sextant, a Sage Disocvery which increases your Naval skills.',
    23: 'Your empire is the utopia of New Atlantis, created by the English philosopher Francis Bacon.His work "The New Atlantis", published in 1624, depicted a society where only men of great wisdom could become leaders.In Bacon\'s inspirational vision, they roam the world in search of wisdom, and their Science leads humanity to a perfect society and "the achievement of all things possible".Consequently, your leaders are given good Sage and Naval ability, and you also start with some good sage discoveries.',
    24: 'Your empire in the Earth Variant game is the Lost Empire of Atlantis.The great philospher Plato mentioned this lost empire in his writings.According to ancient legend, it was a naval power led by sages of great wisdom, which kept its existence shrouded in secrecy by the use of powerful illusions.Consequently, your heroes start with good skill in Sage and Illusionist abilities, and the Sextant, a Sage Disocvery which increases your Naval skills.',
    25: 'Your empire in the Earth Variant game is the Lost Empire of Atlantis.The great philospher Plato mentioned this lost empire in his writings.According to ancient legend, it was a naval power led by sages of great wisdom, which kept its existence shrouded in secrecy by the use of powerful illusions.Consequently, your heroes start with good skill in Sage and Illusionist abilities, and the Sextant, a Sage Disocvery which increases your Naval skills.',
    26: 'Your empire in the Earth Variant game is the Lost Empire of Atlantis.The great philospher Plato mentioned this lost empire in his writings.According to ancient legend, it was a naval power led by sages of great wisdom, which kept its existence shrouded in secrecy by the use of powerful illusions.Consequently, your heroes start with good skill in Sage and Illusionist abilities, and the Sextant, a Sage Disocvery which increases your Naval skills.',
    27: 'Your empire in the Earth Variant game is the Lost Empire of Atlantis.The great philospher Plato mentioned this lost empire in his writings.According to ancient legend, it was a naval power led by sages of great wisdom, which kept its existence shrouded in secrecy by the use of powerful illusions.Consequently, your heroes start with good skill in Sage and Illusionist abilities, and the Sextant, a Sage Disocvery which increases your Naval skills.',
    28: 'Your empire in the Earth Variant game is the Lost Empire of Atlantis.The great philospher Plato mentioned this lost empire in his writings.According to ancient legend, it was a naval power led by sages of great wisdom, which kept its existence shrouded in secrecy by the use of powerful illusions.Consequently, your heroes start with good skill in Sage and Illusionist abilities, and the Sextant, a Sage Disocvery which increases your Naval skills.',
    29: 'Your empire in the Earth Variant game is the Lost Empire of Atlantis.The great philospher Plato mentioned this lost empire in his writings.According to ancient legend, it was a naval power led by sages of great wisdom, which kept its existence shrouded in secrecy by the use of powerful illusions.Consequently, your heroes start with good skill in Sage and Illusionist abilities, and the Sextant, a Sage Disocvery which increases your Naval skills.',
    30: 'Your empire in the Earth Variant game is the Lost Empire of Atlantis.The great philospher Plato mentioned this lost empire in his writings.According to ancient legend, it was a naval power led by sages of great wisdom, which kept its existence shrouded in secrecy by the use of powerful illusions.Consequently, your heroes start with good skill in Sage and Illusionist abilities, and the Sextant, a Sage Disocvery which increases your Naval skills.',
    31: 'Your empire in the Earth Variant game is the Lost Empire of Atlantis.The great philospher Plato mentioned this lost empire in his writings.According to ancient legend, it was a naval power led by sages of great wisdom, which kept its existence shrouded in secrecy by the use of powerful illusions.Consequently, your heroes start with good skill in Sage and Illusionist abilities, and the Sextant, a Sage Disocvery which increases your Naval skills.',
}
# HostAK/TP/PROSE/EUROPE.X2 (header "12 2", SAY.PAS:1282 `_LEuro: FD(
# 'europe.x2', S_Red, 1001+_ldr1)`) -- the same real flavor-text/starting-
# bonus convention as EARTH_EMPIRE_DESCRIPTION above, for the GameType.
# EUROPE scenario's own 12 real historical 11th-century kingdoms.
EUROPE_KINGDOM_DESCRIPTION: dict[int, str] = {
    1: 'Your kingdom in the European game is the Caliphate of Cordoba, in southern Spain.In the 11th century, it was a great center of learning with the largest city in the world (Cordoba).This gives you a bonus of plus 2 Sage to all your characters.',
    2: 'Your kingdom in the European game is the Dukedom of Normandy in northwest France.In the 11th century, it was a stronghold of the Norsemen, who were great mariners.This gives you a bonus of plus 1 Naval to all your characters.',
    3: 'Your kingdom in the European game is the Kingdom of England.This gives you a bonus of plus 1 Naval to all your characters.',
    4: 'Your kingdom in the European game is the Kingdom of Germany, part of the Holy Roman Empire.In the 11th century, it still had some Druidic influences, and so you will receive a bonus of plus 1 Druid to all your characters.',
    5: 'Your kingdom in the European game is the Papal States in central Italy, including Rome.In the 11th century, it was the great center of Christianity.This gives you a bonus of plus 1 White Magic to all your characters.',
    6: 'Your kingdom in the European game is the Kingdom of the Magyars (Hungary) in eastern europe.In the 11th century, the Magyars were becoming a stable kingdom after their raids deep into Germany and France in the 10th century.Hungary was the ancient home of vampires such as Count Dracula, which gives you a bonus of plus 1 Necromancy to all your characters.',
    7: "Your kingdom in the European game is the Byzantine Empire.Actually, you're a duke from a rival noble family who is out to overthrow the weak, corrupt Byzantine Emperor.Byzantium was a center of learning.There, deceitful politics and diplomacy had already been developed into a fine art.This gives you a bonus of plus 1 Sage and plus 1 Spy to all your characters.",
    8: 'Your kingdom in the European game is the Caliphate of Baghdad in Babylon.In the 11th century, Baghdad was a very large city, a center of learning as well as the sin capital of the world.This gives you a bonus of plus 1 Sage and plus 1 Thief to all your characters',
    9: 'Your kingdom in the European game is the Mongolian Khanate of the Golden Horde, in central Asia.In the 11th century, the Mongols were not yet politically unified, but under you they will explode across the world 2 centuries earlier than they did historically.The Mongols had very swift, hard-marching cavalry and therefore you get a bonus of plus 1 March to all your characters.',
    10: 'Your kingdom in the European game is the northern Seljuq Turks, who inhabited the area of southern Russia.The Turks are famous for their fanaticism in personal combat, and therefore you get a bonus of plus 1 Melee to all your characters.',
    11: 'Your kingdom in the European game is the Principality of Novgorod in northern Russia.Russia at that time was ruled by norsemen who penetrated and explored the vastness of Russia.This gives a bonus of plus 1 Explorer to all your characters.Also, a plus 1 in Naval is given to them, reflecting their Norseman heritage.',
    12: 'Your kingdom in the European game is the Principality of Kiev in southern Russia.Russia at that time was ruled by norsemen who penetrated and explored the vastness of Russia.This gives a bonus of plus 1 Explorer to all your characters.Your characters also combine the best skills of the archers of the northern woodsmen and the plains horse-archers, therefore they get a plus 1 bonus in archery.',
}
