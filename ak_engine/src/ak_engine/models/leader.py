from __future__ import annotations

from dataclasses import dataclass

from ak_engine.models.plan import ActionPlan


@dataclass(slots=True)
class Leader:
    leader_id: int
    name: str
    plan: ActionPlan
