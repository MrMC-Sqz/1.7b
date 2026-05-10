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


def parse_label(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y"}:
        return True
    if text in {"0", "false", "no", "n"}:
        return False
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge manual review labels into base JSONL dataset.")
    parser.add_argument("--base", required=True, help="Base dataset JSONL.")
    parser.add_argument("--review", required=True, help="Review JSONL with human_label field.")
    parser.add_argument("--output", required=True, help="Merged JSONL output path.")
    parser.add_argument("--changes-output", default="", help="Optional changes JSONL output path.")
    parser.add_argument(
        "--label-field",
        default="label_should_respond",
        help="Target label field to write in base dataset.",
    )
    args = parser.parse_args()

    base_path = Path(args.base)
    review_path = Path(args.review)

    base_rows = load_jsonl(base_path)
    review_rows = load_jsonl(review_path)

    review_map: dict[str, dict[str, Any]] = {}
    for row in review_rows:
        utt_id = str(row.get("utterance_id", "")).strip()
        if not utt_id:
            continue
        label = parse_label(row.get("human_label"))
        if label is None:
            continue
        review_map[utt_id] = row

    merged: list[dict[str, Any]] = []
    changes: list[dict[str, Any]] = []
    for row in base_rows:
        new_row = dict(row)
        utt_id = str(row.get("utterance_id", ""))
        if utt_id in review_map:
            reviewed = review_map[utt_id]
            new_label = parse_label(reviewed.get("human_label"))
            old_label = parse_label(row.get(args.label_field))
            if new_label is not None:
                new_row[args.label_field] = new_label
                if old_label != new_label:
                    changes.append(
                        {
                            "utterance_id": utt_id,
                            "old_label": old_label,
                            "new_label": new_label,
                            "review_note": reviewed.get("review_note", ""),
                        }
                    )
        merged.append(new_row)

    output_path = Path(args.output)
    write_jsonl(output_path, merged)

    if args.changes_output:
        write_jsonl(Path(args.changes_output), changes)

    summary = {
        "base_rows": len(base_rows),
        "review_rows": len(review_rows),
        "valid_review_labels": len(review_map),
        "changed_rows": len(changes),
        "output": str(output_path),
        "changes_output": args.changes_output,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
