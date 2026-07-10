# Game 6 real turn reports (SE/SB files)

46 real narrative turn reports from a completed Adventurer-Kings game (Game 6,
turns 2-3, most kingdoms), provided by the user for validating the report
generation engine (`ak_engine/report/`, see Phase 58+ in the top-level
README) against real original-engine output.

- `SE6__T2.K*`, `SE6__T3.K*`: standard per-kingdom turn reports. Most are
  "missed the turn deadline, Defend ordered" reports (narratively thin, but
  useful for validating the DIPLOMACY/FINANCES/PROVINCES/CHARACTERS/ARMIES/
  ADVENTURE sections). `SE6__T3.K3` (Josh the gentle) has several complete
  narrated battles with the "ATTACKING ARMY / DEFENDING ARMY" diagram and
  full prose -- the primary fixture for validating battle narration once
  that phase is attempted.
- `SB6__T3.K0`: a "standby kingdom" report (Catilina) -- same content, a
  visibly different layout (narrower margins, stray `M`/`P`/`PM` markers
  likely left over from a column-wrap or OCR/transcription artifact in the
  source file). Kept as a fixture for layout-variance awareness, not
  necessarily to be reproduced exactly.

These are read-only reference/validation fixtures, not inputs to the K1
moves parser (`parser/k1_moves.py`) -- see that module's own tests for the
distinct AK3__T*.K1 move-file fixtures at the repo root, which are a
different format entirely.
