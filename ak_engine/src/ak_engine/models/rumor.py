"""Rumor model (rulebook [3.2]) -- Phase 243.

"Sometimes you get rumours of previously unheard-of features in your
turn reports. About half of these rumours are true, but the rest are
false in some respect: the treasure may not actually be there, and/or
the feature may be in a different province." (quoted in full already in
``models/feature.py``'s own docstring, and prose templates for it exist
-- ``HostAK/TP/PROSE/FRUMOR.X`` -- but the actual selection/
falsification logic doesn't survive anywhere in the archive.)

This is the *record* of one heard rumor -- see ``turn/rumor.py`` for the
trigger/selection/falsification logic that creates one, all
project-original and confirmed directly with the user (project author).

**``leader_id`` (Phase 247)**: the specific character who heard the
rumor, not just the kingdom -- needed once ``report/turn_report.py
describe_turn_results()`` started narrating rumors, since ``describe_
rumor()``'s own ``character_name`` argument (Phase 244) has to name
someone, and ``kingdom_id`` alone can't (a kingdom can have several
leaders). ``turn/plan_dispatch.py``'s own rumor-roll block already had
the ordering leader in scope the whole time; this only threads it
through to the stored record.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ak_engine.models.enums import ActionCode
from ak_engine.models.map import HexCoord
from ak_engine.models.monster import Monster
from ak_engine.models.treasure import Treasure


class RumorContent(Enum):
    FEATURE_AND_MONSTER = "feature_and_monster"
    ITEM = "item"


@dataclass(slots=True)
class Rumor:
    rumor_id: int
    kingdom_id: int  # who heard it
    leader_id: int  # which specific character heard it (Phase 247)
    source_action: ActionCode  # the order type that triggered it
    content: RumorContent
    feature_id: int  # the real feature this rumor is actually about
    is_true: bool
    described_coord: HexCoord  # possibly false -- see turn/rumor.py
    described_monster: Monster | None = None  # set when content is FEATURE_AND_MONSTER
    described_treasure: Treasure | None = None  # set when content is ITEM
