from __future__ import annotations


def plan_time(end_ms: int, wait_ms: int) -> int:
    if end_ms < 0:
        raise ValueError("end_ms must be >= 0")
    if wait_ms < 0:
        raise ValueError("wait_ms must be >= 0")
    return end_ms + wait_ms


def is_interrupted(next_start_ms: int, planned_time_ms: int) -> bool:
    if next_start_ms < 0 or planned_time_ms < 0:
        raise ValueError("timestamps must be >= 0")
    return next_start_ms < planned_time_ms
