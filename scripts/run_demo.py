from active_response.config import V1Config
from active_response.domain import Utterance
from active_response.pipeline import ActiveResponsePipeline


def main() -> None:
    utterances = [
        Utterance(
            utterance_id="u1",
            speaker_id="A",
            text="今天的天气真不错",
            start_ms=0,
            end_ms=900,
        ),
        Utterance(
            utterance_id="u2",
            speaker_id="B",
            text="帮我打开空调",
            start_ms=1000,
            end_ms=1800,
        ),
        Utterance(
            utterance_id="u3",
            speaker_id="C",
            text="我先接个电话",
            start_ms=2200,
            end_ms=3000,
        ),
        Utterance(
            utterance_id="u4",
            speaker_id="A",
            text="帮我导航去公司",
            start_ms=5000,
            end_ms=5800,
        ),
    ]
    pipeline = ActiveResponsePipeline(config=V1Config(urgency_threshold=0.7, wait_ms=800))
    events = pipeline.run(utterances)

    print("=== Decision Events ===")
    for event in events:
        print(
            f"{event.event_type:11s} t={event.event_time_ms:5d}ms "
            f"speaker={event.speaker_id} src={event.source_utt_id} "
            f"reason={event.reason} response={event.response}"
        )


if __name__ == "__main__":
    main()
