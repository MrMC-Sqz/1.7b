import argparse
import json
import time
from dataclasses import asdict
from pathlib import Path

from active_response.config import V1Config
from active_response.domain import Utterance
from active_response.pipeline import ActiveResponsePipeline


def _load_utterances(path: Path) -> list[Utterance]:
    items: list[Utterance] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            items.append(
                Utterance(
                    utterance_id=str(row["utterance_id"]),
                    speaker_id=str(row["speaker_id"]),
                    text=str(row["text"]),
                    start_ms=int(row["start_ms"]),
                    end_ms=int(row["end_ms"]),
                )
            )
    return sorted(items, key=lambda x: x.start_ms)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run stream-like pipeline from JSONL utterances.")
    parser.add_argument("--input", required=True, help="Input utterance JSONL path.")
    parser.add_argument("--output", default="", help="Optional output event JSONL path.")
    parser.add_argument("--use-qwen", action="store_true", help="Use Qwen intent engine.")
    parser.add_argument("--realtime", action="store_true", help="Replay by timestamp intervals.")
    parser.add_argument("--speed", type=float, default=1.0, help="Replay speed multiplier.")
    args = parser.parse_args()

    utterances = _load_utterances(Path(args.input))
    cfg = V1Config(use_qwen_intent_engine=args.use_qwen)
    pipeline = ActiveResponsePipeline(config=cfg)
    events = []

    prev_start = None
    for idx, utt in enumerate(utterances):
        if args.realtime and prev_start is not None:
            wait = max(0, (utt.start_ms - prev_start) / 1000.0 / max(args.speed, 1e-6))
            if wait > 0:
                time.sleep(wait)
        next_start = utterances[idx + 1].start_ms if idx + 1 < len(utterances) else None
        chunk = pipeline.process_utterance(utt, next_start_ms=next_start)
        events.extend(chunk)
        prev_start = utt.start_ms

    events.extend(pipeline.finalize())

    for event in events:
        print(json.dumps(asdict(event), ensure_ascii=False))

    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w", encoding="utf-8") as handle:
            for event in events:
                handle.write(json.dumps(asdict(event), ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
