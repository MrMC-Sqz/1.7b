import argparse
import json
from pathlib import Path
from typing import Any


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Auto-fill review labels for semi-auto annotation round.")
    parser.add_argument("--input", required=True, help="Review JSONL input path.")
    parser.add_argument("--output", required=True, help="Output JSONL path.")
    parser.add_argument(
        "--strategy",
        default="ensemble",
        choices=["ensemble", "rule", "keep_weak", "no_downgrade_rule"],
        help="Label fill strategy.",
    )
    args = parser.parse_args()

    rows = load_jsonl(Path(args.input))
    updated = 0
    for row in rows:
        if row.get("human_label") is not None:
            continue
        weak_label = bool(row.get("label_should_respond", False))
        if args.strategy == "ensemble":
            label = bool(row.get("ensemble_proposed_label", False))
            row["review_note"] = str(row.get("review_note") or "auto-filled by ensemble_proposed_label")
        elif args.strategy == "rule":
            label = bool(row.get("rule_pred", False))
            row["review_note"] = str(row.get("review_note") or "auto-filled by rule_pred")
        elif args.strategy == "keep_weak":
            label = weak_label
            row["review_note"] = str(row.get("review_note") or "auto-filled by original weak label")
        else:
            label = weak_label or bool(row.get("rule_pred", False))
            row["review_note"] = str(
                row.get("review_note") or "auto-filled with no_downgrade_rule (weak OR rule)"
            )
        row["human_label"] = label
        row["review_status"] = "auto_labeled"
        updated += 1

    write_jsonl(Path(args.output), rows)
    print(
        json.dumps(
            {
                "input_rows": len(rows),
                "updated_rows": updated,
                "output": args.output,
                "strategy": args.strategy,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
