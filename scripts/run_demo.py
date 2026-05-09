from active_response.config import V1Config
from active_response.domain import Utterance
from active_response.pipeline import ActiveResponsePipeline


def run_offline_demo() -> None:
    utterances = [
        Utterance("u1", "A", "今天天气真不错", 0, 900),
        Utterance("u2", "B", "帮我打开空调", 1000, 1800),
        Utterance("u3", "B", "另外风量再小一点", 2200, 3000),
        Utterance("u4", "B", "算了不用了", 3200, 3600),
        Utterance("u5", "A", "帮我导航去公司", 5000, 5800),
    ]
    config = V1Config(use_qwen_intent_engine=False, urgency_threshold=0.7, wait_ms=800)
    pipeline = ActiveResponsePipeline(config=config)
    events = pipeline.run(utterances)
    print("=== Offline Decision Events ===")
    for event in events:
        print(
            f"{event.event_type:11s} t={event.event_time_ms:5d}ms "
            f"speaker={event.speaker_id} src={event.source_utt_id} "
            f"reason={event.reason} response={event.response}"
        )


def run_stream_demo() -> None:
    config = V1Config(use_qwen_intent_engine=False, urgency_threshold=0.7, wait_ms=800)
    pipeline = ActiveResponsePipeline(config=config)
    events: list = []
    sequence = [
        Utterance("s1", "C", "帮我打开空调", 0, 800),
        Utterance("s2", "C", "另外温度调低一点", 1200, 1900),
        Utterance("s3", "C", "算了不用了", 2300, 2600),
    ]
    for item in sequence:
        events.extend(pipeline.process_utterance(item))
    events.extend(pipeline.finalize())

    print("\n=== Stream Decision Events ===")
    for event in events:
        print(
            f"{event.event_type:11s} t={event.event_time_ms:5d}ms "
            f"speaker={event.speaker_id} src={event.source_utt_id} "
            f"reason={event.reason} response={event.response}"
        )


if __name__ == "__main__":
    run_offline_demo()
    run_stream_demo()
