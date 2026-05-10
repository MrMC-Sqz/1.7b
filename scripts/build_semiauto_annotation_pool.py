import argparse
import json
from pathlib import Path
from statistics import mean
from typing import Any

from active_response.domain import Utterance
from active_response.intent_engine import QwenIntentEngine, RuleBasedIntentEngine, ScoreHeadIntentEngine


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def to_utterances(rows: list[dict[str, Any]]) -> list[Utterance]:
    items: list[Utterance] = []
    for row in rows:
        items.append(
            Utterance(
                utterance_id=str(row["utterance_id"]),
                speaker_id=str(row["speaker_id"]),
                text=str(row["text"]),
                start_ms=int(row["start_ms"]),
                end_ms=int(row["end_ms"]),
            )
        )
    return items


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def compute_priority(
    preds: list[bool],
    scores: list[float],
    threshold: float,
    weak_label: bool | None,
) -> tuple[float, float, int, bool]:
    avg_score = float(mean(scores)) if scores else 0.0
    # uncertainty in [0, 1], where 1 means very close to threshold.
    uncertainty = 1.0 - min(1.0, abs(avg_score - threshold) / 0.5)
    disagreement = int(len(set(preds)) > 1)
    proposed = sum(1 for p in preds if p) >= ((len(preds) // 2) + 1)
    weak_conflict = weak_label is not None and proposed != weak_label
    priority = 0.5 * disagreement + 0.3 * uncertainty + 0.2 * (1 if weak_conflict else 0)
    return round(priority, 6), round(uncertainty, 6), disagreement, weak_conflict


def main() -> None:
    parser = argparse.ArgumentParser(description="Build semi-auto annotation pool with multi-engine disagreement.")
    parser.add_argument("--input", required=True, help="Input JSONL path.")
    parser.add_argument("--output-dir", default="data/annotate_pool", help="Output folder.")
    parser.add_argument("--top-k", type=int, default=2000, help="Top-k candidates for manual review.")
    parser.add_argument("--start-index", type=int, default=0, help="Start row index (for chunked runs).")
    parser.add_argument("--max-rows", type=int, default=0, help="Process first N rows (0 means all).")
    parser.add_argument("--context-size", type=int, default=12, help="Context window size for scoring.")
    parser.add_argument("--threshold", type=float, default=0.7, help="Decision threshold.")
    parser.add_argument("--use-qwen", action="store_true", help="Enable Qwen engine scoring.")
    parser.add_argument("--qwen-model-name", default="Qwen/Qwen3-1.7B", help="Qwen model name.")
    parser.add_argument("--qwen-device-map", default="auto", help="Qwen device_map, e.g. auto/cpu.")
    parser.add_argument("--qwen-max-new-tokens", type=int, default=64, help="Qwen max new tokens.")
    parser.add_argument("--qwen-timeout-sec", type=float, default=20.0, help="Qwen max generation time.")
    parser.add_argument(
        "--use-score-head",
        action="store_true",
        help="Enable ScoreHead engine scoring.",
    )
    parser.add_argument(
        "--score-head-model-path",
        default="out/score_head_smoke_small",
        help="ScoreHead model path.",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    rows = load_jsonl(input_path)
    if args.start_index > 0:
        rows = rows[args.start_index :]
    if args.max_rows > 0:
        rows = rows[: args.max_rows]

    utterances = to_utterances(rows)
    rule_engine = RuleBasedIntentEngine(urgency_threshold=args.threshold)
    qwen_engine = None
    score_head_engine = None

    if args.use_qwen:
        qwen_engine = QwenIntentEngine(
            model_name=args.qwen_model_name,
            urgency_threshold=args.threshold,
            device_map=args.qwen_device_map,
            max_new_tokens=args.qwen_max_new_tokens,
            inference_timeout_sec=args.qwen_timeout_sec,
            disable_thinking=True,
            fallback_engine=None,
        )
    if args.use_score_head:
        score_head_engine = ScoreHeadIntentEngine(
            model_path=args.score_head_model_path,
            urgency_threshold=args.threshold,
        )

    scored_rows: list[dict[str, Any]] = []
    for idx, utt in enumerate(utterances):
        context = utterances[max(0, idx - args.context_size) : idx]
        row = dict(rows[idx])

        rule = rule_engine.score(context=context, current_utt=utt)
        preds = [rule.should_respond]
        scores = [rule.score]

        result: dict[str, Any] = {
            **row,
            "rule_score": rule.score,
            "rule_pred": rule.should_respond,
            "rule_reason": rule.reason,
        }

        if qwen_engine is not None:
            qwen = qwen_engine.score(context=context, current_utt=utt)
            preds.append(qwen.should_respond)
            scores.append(qwen.score)
            result.update(
                {
                    "qwen_score": qwen.score,
                    "qwen_pred": qwen.should_respond,
                    "qwen_reason": qwen.reason,
                }
            )

        if score_head_engine is not None:
            score_head = score_head_engine.score(context=context, current_utt=utt)
            preds.append(score_head.should_respond)
            scores.append(score_head.score)
            result.update(
                {
                    "score_head_score": score_head.score,
                    "score_head_pred": score_head.should_respond,
                    "score_head_reason": score_head.reason,
                }
            )

        weak_label = row.get("label_should_respond")
        weak_bool = bool(weak_label) if weak_label is not None else None
        priority, uncertainty, disagreement, weak_conflict = compute_priority(
            preds=preds,
            scores=scores,
            threshold=args.threshold,
            weak_label=weak_bool,
        )
        proposed_label = sum(1 for p in preds if p) >= ((len(preds) // 2) + 1)
        avg_score = float(mean(scores)) if scores else 0.0

        result.update(
            {
                "ensemble_avg_score": round(avg_score, 6),
                "ensemble_proposed_label": proposed_label,
                "uncertainty": uncertainty,
                "disagreement": disagreement,
                "weak_conflict": weak_conflict,
                "priority": priority,
                # Fields for manual review.
                "review_status": "todo",
                "human_label": None,
                "review_note": "",
            }
        )
        scored_rows.append(result)

    scored_sorted = sorted(scored_rows, key=lambda x: x["priority"], reverse=True)
    top_k = scored_sorted[: args.top_k]

    output_dir = Path(args.output_dir)
    scored_path = output_dir / "scored_all.jsonl"
    review_path = output_dir / f"review_top_{args.top_k}.jsonl"
    summary_path = output_dir / "summary.json"

    write_jsonl(scored_path, scored_rows)
    write_jsonl(review_path, top_k)

    summary = {
        "input": str(input_path),
        "num_rows": len(scored_rows),
        "top_k": args.top_k,
        "start_index": args.start_index,
        "engines": {
            "rule": True,
            "qwen": bool(args.use_qwen),
            "score_head": bool(args.use_score_head),
        },
        "priority_mean": round(float(mean([r["priority"] for r in scored_rows])) if scored_rows else 0.0, 6),
        "priority_max": round(float(max([r["priority"] for r in scored_rows])) if scored_rows else 0.0, 6),
        "disagreement_rows": int(sum(int(r["disagreement"]) for r in scored_rows)),
        "weak_conflict_rows": int(sum(1 for r in scored_rows if r["weak_conflict"])),
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"scored_all: {scored_path}")
    print(f"review_topk: {review_path}")
    print(f"summary: {summary_path}")


if __name__ == "__main__":
    main()
