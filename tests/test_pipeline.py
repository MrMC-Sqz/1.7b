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
        utterances = [Utterance("u1", "A", "casual chat", 0, 1000)]
        pipeline = ActiveResponsePipeline(
            config=V1Config(use_qwen_intent_engine=False, urgency_threshold=0.7, wait_ms=800),
            intent_engine=StubIntentEngine({"u1": 0.2}),
        )
        events = pipeline.run(utterances)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, "no_need")
        self.assertEqual(events[0].source_utt_id, "u1")

    def test_interrupted_when_next_utterance_starts_before_plan_time(self) -> None:
        utterances = [
            Utterance("u1", "A", "open ac", 0, 1000),
            Utterance("u2", "B", "wait a second", 1500, 1900),
        ]
        pipeline = ActiveResponsePipeline(
            config=V1Config(use_qwen_intent_engine=False, urgency_threshold=0.7, wait_ms=800),
            intent_engine=StubIntentEngine({"u1": 0.9, "u2": 0.2}),
        )
        events = pipeline.run(utterances)
        self.assertEqual(events[0].event_type, "interrupted")
        self.assertEqual(events[0].source_utt_id, "u1")
        self.assertEqual(events[0].event_time_ms, 1500)

    def test_delivered_when_no_interrupt(self) -> None:
        utterances = [Utterance("u1", "A", "navigate home", 0, 1000)]
        pipeline = ActiveResponsePipeline(
            config=V1Config(use_qwen_intent_engine=False, urgency_threshold=0.7, wait_ms=800),
            intent_engine=StubIntentEngine({"u1": 0.95}),
        )
        events = pipeline.run(utterances)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, "delivered")
        self.assertEqual(events[0].source_utt_id, "u1")
        self.assertEqual(events[0].event_time_ms, 1800)

    def test_merge_and_discard_flow(self) -> None:
        pipeline = ActiveResponsePipeline(
            config=V1Config(use_qwen_intent_engine=False, urgency_threshold=0.7, wait_ms=800),
            intent_engine=StubIntentEngine({"u1": 0.95, "u2": 0.2, "u3": 0.2}),
        )
        events = []
        events.extend(pipeline.process_utterance(Utterance("u1", "A", "open ac", 0, 1000)))
        events.extend(pipeline.process_utterance(Utterance("u2", "A", "另外风量小一点", 1200, 1500)))
        events.extend(pipeline.process_utterance(Utterance("u3", "A", "算了不用了", 1600, 1900)))
        events.extend(pipeline.finalize())
        event_types = [item.event_type for item in events]
        self.assertIn("merged", event_types)
        self.assertIn("discarded", event_types)
        self.assertNotIn("delivered", event_types)

    def test_stream_mode_delivers_due_pending(self) -> None:
        pipeline = ActiveResponsePipeline(
            config=V1Config(use_qwen_intent_engine=False, urgency_threshold=0.7, wait_ms=500),
            intent_engine=StubIntentEngine({"u1": 0.92, "u2": 0.2}),
        )
        events = []
        events.extend(pipeline.process_utterance(Utterance("u1", "A", "open ac", 0, 1000)))
        # This utterance starts after u1 delivery time (1500), so delivery should flush before scoring u2.
        events.extend(pipeline.process_utterance(Utterance("u2", "B", "chat", 1700, 2100)))
        events.extend(pipeline.finalize())
        self.assertEqual(events[0].event_type, "delivered")
        self.assertEqual(events[0].event_time_ms, 1500)


if __name__ == "__main__":
    unittest.main()
