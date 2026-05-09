from __future__ import annotations

import json
import os
from dataclasses import asdict
from typing import Sequence

from .config import V1Config
from .context_buffer import ContextBuffer
from .domain import DecisionEvent, PendingResponse, Utterance
from .intent_engine import IntentEngine, QwenIntentEngine, RuleBasedIntentEngine
from .response_manager import ResponseManager
from .timing_policy import is_interrupted, plan_time


class ActiveResponsePipeline:
    def __init__(
        self,
        config: V1Config | None = None,
        context_buffer: ContextBuffer | None = None,
        intent_engine: IntentEngine | None = None,
        response_manager: ResponseManager | None = None,
    ) -> None:
        self.config = config or V1Config()
        self.context_buffer = context_buffer or ContextBuffer()
        self.intent_engine = intent_engine or self._build_default_intent_engine()
        self.response_manager = response_manager or ResponseManager()

    def run(self, utterances: list[Utterance]) -> list[DecisionEvent]:
        ordered = sorted(utterances, key=lambda u: u.start_ms)
        events: list[DecisionEvent] = []
        for idx, utt in enumerate(ordered):
            next_start = ordered[idx + 1].start_ms if idx + 1 < len(ordered) else None
            events.extend(self.process_utterance(utt, next_start_ms=next_start))
        events.extend(self.finalize())
        self._log_events(events)
        return events

    def process_utterance(
        self,
        utterance: Utterance,
        next_start_ms: int | None = None,
    ) -> list[DecisionEvent]:
        events = self._flush_due(until_ms=utterance.start_ms)
        pending_same_speaker = self.response_manager.get_latest_pending(utterance.speaker_id)

        if pending_same_speaker and self._is_discard_update(utterance.text):
            removed = self.response_manager.discard_pending(utterance.speaker_id)
            if removed is not None:
                events.append(
                    DecisionEvent(
                        event_type="discarded",
                        event_time_ms=utterance.end_ms,
                        speaker_id=utterance.speaker_id,
                        source_utt_id=removed.source_utt_id,
                        reason="speaker_cancelled_or_self_resolved",
                    )
                )
            self.context_buffer.add_utterance(utterance)
            self._log_events(events)
            return events

        if pending_same_speaker and self._is_merge_update(utterance.text):
            merged = self.response_manager.merge_latest_pending(
                speaker_id=utterance.speaker_id,
                supplement=utterance.text,
                new_plan_time_ms=plan_time(utterance.end_ms, self.config.wait_ms),
            )
            if merged is not None:
                events.append(
                    DecisionEvent(
                        event_type="merged",
                        event_time_ms=utterance.end_ms,
                        speaker_id=utterance.speaker_id,
                        source_utt_id=merged.source_utt_id,
                        reason="speaker_followup_constraints",
                        response=merged.response,
                    )
                )
            self.context_buffer.add_utterance(utterance)
            self._log_events(events)
            return events

        context = self.context_buffer.recent_context(
            current_end_ms=utterance.end_ms,
            window_ms=self.config.context_window_ms,
        )
        intent = self.intent_engine.score(context=context, current_utt=utterance)
        self.context_buffer.add_utterance(utterance)

        if intent.score < self.config.urgency_threshold or not intent.should_respond:
            events.append(
                DecisionEvent(
                    event_type="no_need",
                    event_time_ms=utterance.end_ms,
                    speaker_id=utterance.speaker_id,
                    source_utt_id=utterance.utterance_id,
                    reason=intent.reason or "below_threshold",
                )
            )
            self._log_events(events)
            return events

        pending = PendingResponse(
            speaker_id=utterance.speaker_id,
            plan_time_ms=plan_time(utterance.end_ms, self.config.wait_ms),
            response=intent.draft_reply or "收到，我马上处理。",
            score=intent.score,
            source_utt_id=utterance.utterance_id,
        )
        dropped = self.response_manager.add_pending(
            pending=pending,
            max_pending_per_speaker=self.config.max_pending_per_speaker,
        )
        for dropped_item in dropped:
            events.append(
                DecisionEvent(
                    event_type="discarded",
                    event_time_ms=utterance.end_ms,
                    speaker_id=dropped_item.speaker_id,
                    source_utt_id=dropped_item.source_utt_id,
                    reason="pending_queue_overflow",
                    response=dropped_item.response,
                )
            )

        if next_start_ms is not None and is_interrupted(next_start_ms, pending.plan_time_ms):
            removed = self.response_manager.discard_pending(utterance.speaker_id)
            if removed is not None:
                events.append(
                    DecisionEvent(
                        event_type="interrupted",
                        event_time_ms=next_start_ms,
                        speaker_id=removed.speaker_id,
                        source_utt_id=removed.source_utt_id,
                        reason="next_utterance_started_before_plan_time",
                        response=removed.response,
                    )
                )
        self._log_events(events)
        return events

    def finalize(self) -> list[DecisionEvent]:
        events = self._flush_due(until_ms=10**18)
        self._log_events(events)
        return events

    def _flush_due(self, until_ms: int) -> list[DecisionEvent]:
        due = self.response_manager.pop_due(current_time_ms=until_ms)
        return [
            DecisionEvent(
                event_type="delivered",
                event_time_ms=item.plan_time_ms,
                speaker_id=item.speaker_id,
                source_utt_id=item.source_utt_id,
                reason="wait_window_passed",
                response=item.response,
            )
            for item in due
        ]

    def _build_default_intent_engine(self) -> IntentEngine:
        fallback = RuleBasedIntentEngine(urgency_threshold=self.config.urgency_threshold)
        if self.config.use_qwen_intent_engine:
            return QwenIntentEngine(
                model_name=self.config.intent_model_name,
                urgency_threshold=self.config.urgency_threshold,
                device_map=self.config.intent_device_map,
                max_new_tokens=self.config.intent_max_new_tokens,
                inference_timeout_sec=self.config.intent_inference_timeout_sec,
                fallback_engine=fallback,
            )
        return fallback

    def _log_events(self, events: list[DecisionEvent]) -> None:
        if not events or not self.config.event_log_path:
            return
        log_path = self.config.event_log_path
        parent = os.path.dirname(log_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as handle:
            for event in events:
                handle.write(json.dumps(asdict(event), ensure_ascii=False) + "\n")

    @staticmethod
    def _contains_any(text: str, tokens: Sequence[str]) -> bool:
        return any(token in text for token in tokens)

    def _is_discard_update(self, text: str) -> bool:
        tokens = ("算了", "不用了", "取消", "我自己来", "已经", "搞定了", "不用")
        return self._contains_any(text, tokens)

    def _is_merge_update(self, text: str) -> bool:
        tokens = ("再", "另外", "顺便", "还有", "并且", "同时", "然后")
        return self._contains_any(text, tokens)
