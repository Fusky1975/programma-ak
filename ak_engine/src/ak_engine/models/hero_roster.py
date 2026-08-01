"""The fixed, game-independent Hero name/id/sex roster (Phase 339).

Every `AK` game draws its Heroes from the same 98-entry named roster,
independent of which particular world/game it is -- confirmed directly
by the user (project author) via a project-original reference document
(`"Nomi (eroi) fino a #99.txt"`), not derived from any Pascal source.
`#0` is documented there as never used (a game always has at least one
King occupying the low ids instead -- see `parser/gw_world.py`'s own
Phase 330 "King's `leader_id` == `kingdom_id`" finding); `#99` is
reserved for a Hero arriving via `models/valhalla.py`'s own VALHALLA
mechanic, not a specific named entry in this table.

**Empirically verified against the real, committed `GW3__T1` fixture**
before being relied on anywhere: 88 of that fixture's own 90 real Hero
names match this table exactly, at unique ids all in the `10-98` range
(zero ids `1-9`, consistent with this being a 10-kingdom game -- Kings
already occupy `0-9`, per `parser/gw_world.py`'s own Phase 330 finding
-- so the roster's own low-id Heroes, `#1` Adam through `#9` Enlil,
never get to appear as Heroes in this particular game). The 2
unmatched names (`Bagmore`, `Kitralus`) are both real entries in the
user's own separate `VALHALLA NEUTRAL.txt` reference file -- exactly
the `#99` "arrived via VALHALLA" case this roster's own note predicts,
not a data error.

This closes `parser/gw_world_bridge.py bridge_new_game_state()`'s own
Phase 338 "no general Hero id recovery" gap for every Hero whose name
is in this table -- `apply_confirmed_hero_ids()` (Phase 338) remains
the fallback path for the genuinely un-rostered case (a VALHALLA
arrival), not the primary one anymore.
"""

from __future__ import annotations

from dataclasses import dataclass

from ak_engine.models.sex import Sex


@dataclass(slots=True, frozen=True)
class StandardHeroEntry:
    hero_id: int
    name: str
    sex: Sex


# Verbatim from the user's own "Nomi (eroi) fino a #99.txt" -- ids 1-98.
# `#0` and `#99` are deliberately absent (see module docstring).
STANDARD_HERO_ROSTER: tuple[StandardHeroEntry, ...] = (
    StandardHeroEntry(1, "Adam", Sex.MALE),
    StandardHeroEntry(2, "Eve", Sex.FEMALE),
    StandardHeroEntry(3, "Abel", Sex.MALE),
    StandardHeroEntry(4, "Elegorn", Sex.MALE),
    StandardHeroEntry(5, "Fafax", Sex.MALE),
    StandardHeroEntry(6, "Gogolak", Sex.MALE),
    StandardHeroEntry(7, "Hahar", Sex.MALE),
    StandardHeroEntry(8, "Ilikuth", Sex.MALE),
    StandardHeroEntry(9, "Enlil", Sex.MALE),
    StandardHeroEntry(10, "Kokocala", Sex.MALE),
    StandardHeroEntry(11, "Lallipugh", Sex.MALE),
    StandardHeroEntry(12, "Alexius", Sex.MALE),
    StandardHeroEntry(13, "Ningarl", Sex.MALE),
    StandardHeroEntry(14, "Saladin", Sex.MALE),
    StandardHeroEntry(15, "Girard", Sex.MALE),
    StandardHeroEntry(16, "Everard", Sex.MALE),
    StandardHeroEntry(17, "Stonebrick", Sex.MALE),
    StandardHeroEntry(18, "Guerin", Sex.MALE),
    StandardHeroEntry(19, "Arnulf", Sex.MALE),
    StandardHeroEntry(20, "Clarambald", Sex.MALE),
    StandardHeroEntry(21, "Behemond", Sex.MALE),
    StandardHeroEntry(22, "Alaric", Sex.MALE),
    StandardHeroEntry(23, "Snorri", Sex.MALE),
    StandardHeroEntry(24, "Tancred", Sex.MALE),
    StandardHeroEntry(25, "Rainulf", Sex.MALE),
    StandardHeroEntry(26, "Oakley", Sex.MALE),
    StandardHeroEntry(27, "Fingol", Sex.MALE),
    StandardHeroEntry(28, "Adhemar", Sex.MALE),
    StandardHeroEntry(29, "Amalric", Sex.MALE),
    StandardHeroEntry(30, "Melantheus", Sex.MALE),
    StandardHeroEntry(31, "Reynald", Sex.MALE),
    StandardHeroEntry(32, "Tao-Li", Sex.FEMALE),
    StandardHeroEntry(33, "Alain", Sex.MALE),
    StandardHeroEntry(34, "Dreux", Sex.MALE),
    StandardHeroEntry(35, "Helatia", Sex.FEMALE),
    StandardHeroEntry(36, "Geoffrey", Sex.MALE),
    StandardHeroEntry(37, "Jolin", Sex.MALE),
    StandardHeroEntry(38, "Dracona", Sex.FEMALE),
    StandardHeroEntry(39, "Drago", Sex.MALE),
    StandardHeroEntry(40, "Korchnoi", Sex.MALE),
    StandardHeroEntry(41, "Bairn", Sex.MALE),
    StandardHeroEntry(42, "Garin", Sex.MALE),
    StandardHeroEntry(43, "Tarsus", Sex.MALE),
    StandardHeroEntry(44, "Drake", Sex.MALE),
    StandardHeroEntry(45, "Thorus", Sex.MALE),
    StandardHeroEntry(46, "Gabriel", Sex.MALE),
    StandardHeroEntry(47, "Tilden", Sex.FEMALE),
    StandardHeroEntry(48, "Lexington", Sex.MALE),
    StandardHeroEntry(49, "Constantine", Sex.MALE),
    StandardHeroEntry(50, "Duqaq", Sex.MALE),
    StandardHeroEntry(51, "Robin", Sex.MALE),
    StandardHeroEntry(52, "Riose", Sex.FEMALE),
    StandardHeroEntry(53, "Charious", Sex.MALE),
    StandardHeroEntry(54, "Attla", Sex.MALE),
    StandardHeroEntry(55, "Rolando", Sex.MALE),
    StandardHeroEntry(56, "Hawkins", Sex.MALE),
    StandardHeroEntry(57, "Ishtar", Sex.FEMALE),
    StandardHeroEntry(58, "Elmer", Sex.MALE),
    StandardHeroEntry(59, "Thrym", Sex.MALE),
    StandardHeroEntry(60, "Eric", Sex.MALE),
    StandardHeroEntry(61, "Magnus", Sex.MALE),
    StandardHeroEntry(62, "Kurtinaitis", Sex.MALE),
    StandardHeroEntry(63, "Marlboro", Sex.MALE),
    StandardHeroEntry(64, "Lakes", Sex.FEMALE),
    StandardHeroEntry(65, "Migfox", Sex.MALE),
    StandardHeroEntry(66, "Aegir", Sex.MALE),
    StandardHeroEntry(67, "York", Sex.MALE),
    StandardHeroEntry(68, "Marlon", Sex.MALE),
    StandardHeroEntry(69, "Adonis", Sex.MALE),
    StandardHeroEntry(70, "Philo", Sex.MALE),
    StandardHeroEntry(71, "Gladstone", Sex.MALE),
    StandardHeroEntry(72, "Teleko", Sex.MALE),
    StandardHeroEntry(73, "Presto", Sex.MALE),
    StandardHeroEntry(74, "Ashley", Sex.FEMALE),
    StandardHeroEntry(75, "Atlas", Sex.MALE),
    StandardHeroEntry(76, "Cortez", Sex.MALE),
    StandardHeroEntry(77, "Hume", Sex.MALE),
    StandardHeroEntry(78, "Pascal", Sex.MALE),
    StandardHeroEntry(79, "Hakim", Sex.MALE),
    StandardHeroEntry(80, "Jamielle", Sex.FEMALE),
    StandardHeroEntry(81, "Kari", Sex.FEMALE),
    StandardHeroEntry(82, "Astelle", Sex.FEMALE),
    StandardHeroEntry(83, "Adele", Sex.FEMALE),
    StandardHeroEntry(84, "Hecate", Sex.FEMALE),
    StandardHeroEntry(85, "Inanna", Sex.FEMALE),
    StandardHeroEntry(86, "Brunhilda", Sex.FEMALE),
    StandardHeroEntry(87, "Tiffany", Sex.FEMALE),
    StandardHeroEntry(88, "Tlazolteotl", Sex.MALE),
    StandardHeroEntry(89, "Isis", Sex.MALE),
    StandardHeroEntry(90, "Bouticca", Sex.FEMALE),
    StandardHeroEntry(91, "Indra", Sex.FEMALE),
    StandardHeroEntry(92, "Loviatar", Sex.FEMALE),
    StandardHeroEntry(93, "Kishijoten", Sex.MALE),
    StandardHeroEntry(94, "Hope", Sex.FEMALE),
    StandardHeroEntry(95, "Samantha", Sex.FEMALE),
    StandardHeroEntry(96, "Raiden", Sex.MALE),
    StandardHeroEntry(97, "Odysseus", Sex.MALE),
    StandardHeroEntry(98, "Negumba", Sex.MALE),
)

STANDARD_HERO_ID_BY_NAME: dict[str, int] = {entry.name: entry.hero_id for entry in STANDARD_HERO_ROSTER}
STANDARD_HERO_SEX_BY_NAME: dict[str, Sex] = {entry.name: entry.sex for entry in STANDARD_HERO_ROSTER}
