from .base import SchedulerPolicy, SchedulerState
from .timeframe import TimeframeFirstPolicy
from .critical_path import CriticalPathPolicy
from .best_fit import BestFitBackfillPolicy


def get_policy(name: str) -> SchedulerPolicy:
    name = name.lower().strip()
    if name in ("timeframe", "tf", "legacy"):
        return TimeframeFirstPolicy()
    if name in ("critical-path", "cp"):
        return CriticalPathPolicy()
    if name in ("best-fit", "bf"):
        return BestFitBackfillPolicy()
    raise ValueError(f"unknown scheduler policy: {name}")


__all__ = [
    "SchedulerPolicy", "SchedulerState",
    "TimeframeFirstPolicy", "CriticalPathPolicy", "BestFitBackfillPolicy",
    "get_policy",
]
