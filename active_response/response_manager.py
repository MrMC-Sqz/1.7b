from __future__ import annotations

from dataclasses import dataclass, field

from .domain import PendingResponse


@dataclass
class ResponseManager:
    _pending_by_speaker: dict[str, list[PendingResponse]] = field(default_factory=dict)

    def add_pending(
        self,
        pending: PendingResponse,
        max_pending_per_speaker: int,
    ) -> list[PendingResponse]:
        queue = self._pending_by_speaker.setdefault(pending.speaker_id, [])
        queue.append(pending)
        queue.sort(key=lambda item: item.plan_time_ms)
        dropped: list[PendingResponse] = []
        while len(queue) > max_pending_per_speaker:
            dropped.append(queue.pop(0))
        return dropped

    def discard_pending(self, speaker_id: str) -> PendingResponse | None:
        queue = self._pending_by_speaker.get(speaker_id)
        if not queue:
            return None
        removed = queue.pop()
        if not queue:
            self._pending_by_speaker.pop(speaker_id, None)
        return removed

    def merge_latest_pending(
        self,
        speaker_id: str,
        supplement: str,
        new_plan_time_ms: int | None = None,
    ) -> PendingResponse | None:
        queue = self._pending_by_speaker.get(speaker_id)
        if not queue:
            return None
        existing = queue[-1]
        merged_text = supplement.strip()
        if merged_text:
            response = f"{existing.response}；另外，{merged_text}"
        else:
            response = existing.response
        merged = PendingResponse(
            speaker_id=existing.speaker_id,
            plan_time_ms=new_plan_time_ms if new_plan_time_ms is not None else existing.plan_time_ms,
            response=response,
            score=existing.score,
            source_utt_id=existing.source_utt_id,
        )
        queue[-1] = merged
        queue.sort(key=lambda item: item.plan_time_ms)
        return merged

    def get_latest_pending(self, speaker_id: str) -> PendingResponse | None:
        queue = self._pending_by_speaker.get(speaker_id)
        if not queue:
            return None
        return queue[-1]

    def pop_due(self, current_time_ms: int) -> list[PendingResponse]:
        due: list[PendingResponse] = []
        empty_speakers: list[str] = []
        for speaker_id, queue in self._pending_by_speaker.items():
            while queue and queue[0].plan_time_ms <= current_time_ms:
                due.append(queue.pop(0))
            if not queue:
                empty_speakers.append(speaker_id)
        for speaker_id in empty_speakers:
            self._pending_by_speaker.pop(speaker_id, None)
        due.sort(key=lambda item: item.plan_time_ms)
        return due

    def all_pending(self) -> list[PendingResponse]:
        items: list[PendingResponse] = []
        for queue in self._pending_by_speaker.values():
            items.extend(queue)
        return sorted(items, key=lambda item: item.plan_time_ms)
