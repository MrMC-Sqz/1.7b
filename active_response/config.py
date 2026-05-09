from dataclasses import dataclass


@dataclass(slots=True)
class V1Config:
    urgency_threshold: float = 0.7
    wait_ms: int = 800
    context_window_ms: int = 10000
    max_pending_per_speaker: int = 1
