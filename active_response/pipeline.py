from __future__ import annotations

from typing import Protocol, Sequence

from .config import V1Config
from .context_buffer import ContextBuffer
from .domain import DecisionEvent, IntentResult, PendingResponse, Utterance


class IntentEngine(Protocol):
    def score(self, context: list[Utterance], current_utt: Utterance) -> IntentResult:
        ...


class RuleBasedIntentEngine:
    def __init__(self, trigger_keywords: Sequence[str] | None = None) -> None:
        self._trigger_keywords = tuple(
            k.lower()
            for k in (trigger_keywords or ("导航", "空调", "打开", "关闭", "播放", "调高", "调低"))
        )

    def score(self, context: list[Utterance], current_utt: Utterance) -> IntentResult:
        del context  # V1 minimal implementation keeps the interface and can use context later.
        text = current_utt.text.lower()
        hit = any(k in text for k in self._trigger_keywords)
        score = 0.9 if hit else 0.2
        return IntentResult(
            utterance_id=current_utt.utterance_id,
            score=score,
            should_respond=hit,
            reason="keyword_hit" if hit else "low_intent",
            draft_reply="收到，马上处理。" if hit else None,
        )


class ActiveResponsePipeline:
    def __init__(
        self,
        config: V1Config | None = None,
        context_buffer: ContextBuffer | None = None,
        intent_engine: IntentEngine | None = None,
    ) -> None:
        self.config = config or V1Config()
        self.context_buffer = context_buffer or ContextBuffer()
        self.intent_engine = intent_engine or RuleBasedIntentEngine()

    def run(self, utterances: list[Utterance]) -> list[DecisionEvent]:
        ordered = sorted(utterances, key=lambda u: u.start_ms)
        events: list[DecisionEvent] = []

        for index, utt in enumerate(ordered):
            context = self.context_buffer.recent_context(
                current_end_ms=utt.end_ms,
                window_ms=self.config.context_window_ms,
            )
            intent = self.intent_engine.score(context=context, current_utt=utt)
            self.context_buffer.add_utterance(utt)

            if intent.score < self.config.urgency_threshold or not intent.should_respond:
                events.append(
                    DecisionEvent(
                        event_type="no_need",
                        event_time_ms=utt.end_ms,
                        speaker_id=utt.speaker_id,
                        source_utt_id=utt.utterance_id,
                        reason=intent.reason or "below_threshold",
                    )
                )
                continue

            pending = PendingResponse(
                speaker_id=utt.speaker_id,
                plan_time_ms=utt.end_ms + self.config.wait_ms,
                response=intent.draft_reply or "收到。",
                score=intent.score,
                source_utt_id=utt.utterance_id,
            )
            next_start_ms = ordered[index + 1].start_ms if index + 1 < len(ordered) else None

            if next_start_ms is not None and next_start_ms < pending.plan_time_ms:
                events.append(
                    DecisionEvent(
                        event_type="interrupted",
                        event_time_ms=next_start_ms,
                        speaker_id=pending.speaker_id,
                        source_utt_id=pending.source_utt_id,
                        reason="next_utterance_started_before_plan_time",
                        response=pending.response,
                    )
                )
                continue

            events.append(
                DecisionEvent(
                    event_type="delivered",
                    event_time_ms=pending.plan_time_ms,
                    speaker_id=pending.speaker_id,
                    source_utt_id=pending.source_utt_id,
                    reason="wait_window_passed",
                    response=pending.response,
                )
            )

        return events
