# Game 3 real world file (GW3__T1)

The turn-1 snapshot of the world file for a completed Adventurer-Kings game
(Game 3), copied from the user's own archived host data
(`HostAK-old/TP/G3/GW3__T1`), for validating `parser/gw_world.py` (Phase 222)
against real original-engine output -- the same "provided by the user,
read-only reference fixture" precedent as `tests/fixtures/reports/G6/`.

Plain ASCII text, CRLF line-terminated, one 4-line record per province (162
provinces total): name, `<tax> <terrain> 0 <race> 0 6`, an undecoded
2-integer line, and an owning-kingdom id (`255` = unowned). See
`parser/gw_world.py`'s own module docstring for the full, evidence-based
schema recovery (there is no surviving Pascal source for this file format --
it was reverse-engineered by cross-referencing known real Tax/Race/Terrain
values from `SE3__T*.K2` PROVINCES sections against this file's raw
integers).
