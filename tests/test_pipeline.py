import unittest

from active_response.config import V1Config
from active_response.domain import IntentResult, Utterance
from active_response.pipeline import ActiveResponsePipeline


class StubIntentEngine:
    def __init__(self, score_map: dict[str, float]) -> None:
        self._score_map = score_map

    def score(self, context: list[Utterance], current_utt: Utterance) -> IntentResult:
        del context
        score = self._score_map[current_utt.utterance_id]
        return IntentResult(
            utterance_id=current_utt.utterance_id,
            score=score,
            should_respond=score >= 0.7,
            reason="stub",
            draft_reply="stub-reply",
        )


class PipelineTest(unittest.TestCase):
    def test_no_need_when_score_below_threshold(self) -> None:
        utterances = [
            Utterance("u1", "A", "随便聊聊", 0, 1000),
        ]
        pipeline = ActiveResponsePipeline(
            config=V1Config(urgency_threshold=0.7, wait_ms=800),
            intent_engine=StubIntentEngine({"u1": 0.2}),
        )

        events = pipeline.run(utterances)

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, "no_need")
        self.assertEqual(events[0].source_utt_id, "u1")

    def test_interrupted_when_next_utterance_starts_before_plan_time(self) -> None:
        utterances = [
            Utterance("u1", "A", "打开空调", 0, 1000),
            Utterance("u2", "B", "等等我先说", 1500, 1900),
        ]
        pipeline = ActiveResponsePipeline(
            config=V1Config(urgency_threshold=0.7, wait_ms=800),
            intent_engine=StubIntentEngine({"u1": 0.9, "u2": 0.2}),
        )

        events = pipeline.run(utterances)
        first = events[0]

        self.assertEqual(first.event_type, "interrupted")
        self.assertEqual(first.source_utt_id, "u1")
        self.assertEqual(first.event_time_ms, 1500)

    def test_delivered_when_no_next_utterance_interrupts_plan_time(self) -> None:
        utterances = [
            Utterance("u1", "A", "导航去公司", 0, 1000),
        ]
        pipeline = ActiveResponsePipeline(
            config=V1Config(urgency_threshold=0.7, wait_ms=800),
            intent_engine=StubIntentEngine({"u1": 0.95}),
        )

        events = pipeline.run(utterances)

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, "delivered")
        self.assertEqual(events[0].source_utt_id, "u1")
        self.assertEqual(events[0].event_time_ms, 1800)
