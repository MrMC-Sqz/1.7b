from dataclasses import dataclass
from typing import Optional


@dataclass(slots=True)
class Utterance:
    utterance_id: str
    speaker_id: str
    text: str
    start_ms: int
    end_ms: int

    def __post_init__(self) -> None:
        if self.start_ms > self.end_ms:
            raise ValueError("start_ms must be <= end_ms")


@dataclass(slots=True)
class IntentResult:
    utterance_id: str
    score: float
    should_respond: bool
    reason: str = ""
    draft_reply: Optional[str] = None


@dataclass(slots=True)
class PendingResponse:
    speaker_id: str
    plan_time_ms: int
    response: str
    score: float
    source_utt_id: str


@dataclass(slots=True)
class DecisionEvent:
    event_type: str  # no_need/interrupted/delivered/merged/discarded
    event_time_ms: int
    speaker_id: str
    source_utt_id: str
    reason: str = ""
    response: Optional[str] = None
