# Game 3 real turn reports (SE files)

58 real narrative turn reports from a real, long-running Adventurer-Kings game
(Game 3), provided by the user for validating the report generation engine
(`ak_engine/report/`) against real original-engine output -- the same
precedent `tests/fixtures/reports/G6/` already established, but far larger:
six consecutive gameturns (6-11) across up to 9 Kingdoms each, plus 4 Turn 0
("Birthright") reports.

- `SE3__T0.K1`, `.K2`, `.K3`, `.K5`: Turn 0 Birthright reports (world
  creation), for Kingdoms 1/2/3/5 only -- the other Kingdom slots either
  weren't created yet or weren't supplied for turn 0.
- `SE3__T6.K1`-`.K9` through `SE3__T11.K1`-`.K9`: ordinary per-kingdom turn
  reports for six consecutive turns, 9 Kingdoms each turn (54 files).

All are real dot-matrix-era mail-order output (`Sargona Games`), legacy
8-bit encoded (not UTF-8) -- read them with a shell command or a
byte-preserving tool, not the `Write`/`Edit` tools, which refuse non-UTF-8
content.

## Battle diagrams (`ATTACKING ARMY`/`DEFENDING ARMY`)

Unlike `tests/fixtures/reports/G6/` (only 2 of 46 files contain any, 5
diagrams total), this corpus is rich in them: **97 real battle-line
diagrams across 38 of the 58 files**, confirmed via `grep -c "ATTACKING
ARMY"`. This is the primary reason the user supplied this corpus -- to
reverse-engineer the real battle-line diagram format
(`report/turn_report.py` has no renderer for it yet; see that module's
own analysis notes/commit history for what has been decoded so far:
fixed 10-character-wide cells, a per-unit 4-line block repeated once per
unit in the line, a `----------` separator between attacker and
defender blocks, and an open question on the exact meaning of the
quality-looking suffix (`/A`, `/C`, `/V`, ...) and the marker box
(`GC` vs a 2-character leader code) after the separator -- this larger
corpus should be enough to resolve both with real statistical
confidence, unlike the original 5-sample G6 corpus).

These are read-only reference/validation fixtures, not inputs to the K1
moves parser -- see `parser/k1_moves.py`'s own tests for the distinct
`AK3__T*.K1` move-file fixtures at the repo root, a different format
entirely.
