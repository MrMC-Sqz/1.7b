import argparse
import json
from dataclasses import asdict
from pathlib import Path

from active_response.config import V1Config
from active_response.domain import Utterance
from active_response.pipeline import ActiveResponsePipeline


POSITIVE_EVENT_TYPES = {"delivered", "interrupted", "merged", "discarded"}


def _load_jsonl(path: Path) -> list[dict]:
    items: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            items.append(json.loads(line))
    return items


def _build_utterances(rows: list[dict]) -> list[Utterance]:
    return [
        Utterance(
            utterance_id=str(row["utterance_id"]),
            speaker_id=str(row["speaker_id"]),
            text=str(row["text"]),
            start_ms=int(row["start_ms"]),
            end_ms=int(row["end_ms"]),
        )
        for row in rows
    ]


def _event_map(events: list) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for event in events:
        mapping.setdefault(event.source_utt_id, event.event_type)
    return mapping


def _calc_metrics(rows: list[dict], pred_event_by_utt: dict[str, str]) -> dict[str, float]:
    tp = fp = tn = fn = 0
    for row in rows:
        utt_id = str(row["utterance_id"])
        label = bool(row["label_should_respond"])
        event_type = pred_event_by_utt.get(utt_id, "no_need")
        pred = event_type in POSITIVE_EVENT_TYPES
        if label and pred:
            tp += 1
        elif (not label) and pred:
            fp += 1
        elif (not label) and (not pred):
            tn += 1
        else:
            fn += 1

    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    accuracy = (tp + tn) / (tp + tn + fp + fn) if tp + tn + fp + fn else 0.0
    return {
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "accuracy": round(accuracy, 4),
    }


def _latency_stats(rows: list[dict], events: list) -> dict[str, float]:
    by_id = {str(row["utterance_id"]): int(row["end_ms"]) for row in rows}
    latencies = []
    for event in events:
        if event.event_type != "delivered":
            continue
        end_ms = by_id.get(event.source_utt_id)
        if end_ms is None:
            continue
        latencies.append(event.event_time_ms - end_ms)
    if not latencies:
        return {"count": 0, "p50_ms": 0.0, "p95_ms": 0.0, "max_ms": 0.0}
    latencies.sort()
    p50 = latencies[int(0.5 * (len(latencies) - 1))]
    p95 = latencies[int(0.95 * (len(latencies) - 1))]
    return {
        "count": len(latencies),
        "p50_ms": float(p50),
        "p95_ms": float(p95),
        "max_ms": float(latencies[-1]),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate active response pipeline on labeled JSONL.")
    parser.add_argument("--input", required=True, help="Path to labeled JSONL.")
    parser.add_argument("--output", default="", help="Optional path to save event JSONL.")
    parser.add_argument("--use-qwen", action="store_true", help="Use QwenIntentEngine.")
    parser.add_argument("--use-score-head", action="store_true", help="Use ScoreHeadIntentEngine.")
    parser.add_argument(
        "--score-head-model-path",
        default="",
        help="ScoreHead model path, required when --use-score-head.",
    )
    parser.add_argument("--threshold", type=float, default=0.7, help="Urgency threshold.")
    parser.add_argument("--wait-ms", type=int, default=800, help="Response wait window in ms.")
    parser.add_argument("--max-new-tokens", type=int, default=64, help="Max new tokens for intent model.")
    parser.add_argument("--infer-timeout-sec", type=float, default=20.0, help="Intent inference timeout.")
    args = parser.parse_args()

    rows = _load_jsonl(Path(args.input))
    utterances = _build_utterances(rows)
    cfg = V1Config(
        use_qwen_intent_engine=args.use_qwen,
        use_score_head_intent_engine=args.use_score_head,
        score_head_model_path=args.score_head_model_path,
        urgency_threshold=args.threshold,
        wait_ms=args.wait_ms,
        intent_max_new_tokens=args.max_new_tokens,
        intent_inference_timeout_sec=args.infer_timeout_sec,
    )
    pipeline = ActiveResponsePipeline(config=cfg)
    events = pipeline.run(utterances)
    pred_map = _event_map(events)
    cls_metrics = _calc_metrics(rows, pred_map)
    lat_metrics = _latency_stats(rows, events)

    result = {
        "num_samples": len(rows),
        "config": {
            "use_qwen": args.use_qwen,
            "use_score_head": args.use_score_head,
            "score_head_model_path": args.score_head_model_path,
            "threshold": args.threshold,
            "wait_ms": args.wait_ms,
            "max_new_tokens": args.max_new_tokens,
            "infer_timeout_sec": args.infer_timeout_sec,
        },
        "classification": cls_metrics,
        "latency": lat_metrics,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", encoding="utf-8") as handle:
            for event in events:
                handle.write(json.dumps(asdict(event), ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
