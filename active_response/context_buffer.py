from bisect import bisect_right
from dataclasses import dataclass, field

from .domain import Utterance


@dataclass
class ContextBuffer:
    # Always kept sorted by end_ms.
    _utterances: list[Utterance] = field(default_factory=list)

    def add_utterance(self, utt: Utterance) -> None:
        insert_at = bisect_right([u.end_ms for u in self._utterances], utt.end_ms)
        self._utterances.insert(insert_at, utt)

    def recent_context(self, current_end_ms: int, window_ms: int) -> list[Utterance]:
        start_bound = current_end_ms - window_ms
        return [
            u
            for u in self._utterances
            if start_bound <= u.end_ms <= current_end_ms
        ]

    def recent_by_speaker(
        self,
        speaker_id: str,
        current_end_ms: int,
        window_ms: int,
    ) -> list[Utterance]:
        start_bound = current_end_ms - window_ms
        return [
            u
            for u in self._utterances
            if u.speaker_id == speaker_id and start_bound <= u.end_ms <= current_end_ms
        ]
