# Game 3 real world files (GW3__T1, GW3__T5)

Turn snapshots of the world file for a completed Adventurer-Kings game (Game
3), copied from the user's own archived host data (`HostAK-old/TP/G3/`), for
validating `parser/gw_world.py` (Phase 222) against real original-engine
output -- the same "provided by the user, read-only reference fixture"
precedent as `tests/fixtures/reports/G6/`. `GW3__T5` was added in Phase 340
to end-to-end-validate `parser/gw_world_bridge.py bridge_new_game_state()`
against a real, non-T1 file, cross-checked against the real `SE3__T4.K1`
letter for that same turn (the turn-alignment convention: `GW3__T5` reflects
the state at the end of real turn 4).

Plain ASCII text, CRLF line-terminated, one 4-line record per province (162
provinces total): name, `<tax> <terrain> <mystery> <race> 0 6`, an undecoded
2-integer line, and an owning-kingdom id (`255` = unowned). The `<mystery>`
field was originally believed to always be `0` (true for every province in
`GW3__T1`), until Phase 340's own cross-file check against `GW3__T5` proved
it takes on other values there (a per-province bitmask of some kind, still
undeciphered) -- see `parser/gw_world.py parse_gw_world()`'s own Phase 340
docstring addendum. See `parser/gw_world.py`'s own module docstring for the
full, evidence-based schema recovery (there is no surviving Pascal source for
this file format -- it was reverse-engineered by cross-referencing known real
Tax/Race/Terrain values from `SE3__T*.K2` PROVINCES sections against this
file's raw integers).
