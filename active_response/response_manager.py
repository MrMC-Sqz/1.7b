from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .domain import PendingResponse


@dataclass
class ResponseManager:
    _pending_by_speaker: dict[str, PendingResponse] = field(default_factory=dict)

    def add_or_replace_pending(self, pending: PendingResponse) -> PendingResponse:
        # V1: one pending item per speaker, keep only the latest.
        self._pending_by_speaker[pending.speaker_id] = pending
        return pending

    def discard_pending(self, speaker_id: str) -> Optional[PendingResponse]:
        return self._pending_by_speaker.pop(speaker_id, None)

    def merge_pending(self, speaker_id: str, supplement: str) -> Optional[PendingResponse]:
        existing = self._pending_by_speaker.get(speaker_id)
        if existing is None:
            return None

        merged_text = supplement.strip()
        if merged_text:
            merged_response = f"{existing.response}；另外，{merged_text}"
        else:
            merged_response = existing.response

        merged = PendingResponse(
            speaker_id=existing.speaker_id,
            plan_time_ms=existing.plan_time_ms,
            response=merged_response,
            score=existing.score,
            source_utt_id=existing.source_utt_id,
        )
        self._pending_by_speaker[speaker_id] = merged
        return merged

    def get_pending(self, speaker_id: str) -> Optional[PendingResponse]:
        return self._pending_by_speaker.get(speaker_id)

    def all_pending(self) -> list[PendingResponse]:
        return list(self._pending_by_speaker.values())
