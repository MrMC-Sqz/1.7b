import argparse
import json
import random
from pathlib import Path


def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def dump_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build train/val/test pack from AISHELL-5 weak labels.")
    parser.add_argument(
        "--dev",
        default=r"G:\1.7b\data\collected\aishell5_dev_segments_weak.jsonl",
    )
    parser.add_argument(
        "--eval1",
        default=r"G:\1.7b\data\collected\aishell5_eval1_segments_weak.jsonl",
    )
    parser.add_argument(
        "--out-dir",
        default=r"G:\1.7b\data\pack\aishell5_active_response_weak",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--train-ratio", type=float, default=0.8)
    parser.add_argument("--val-ratio", type=float, default=0.1)
    args = parser.parse_args()

    random.seed(args.seed)
    dev_rows = load_jsonl(Path(args.dev))
    eval_rows = load_jsonl(Path(args.eval1))
    all_rows = dev_rows + eval_rows
    random.shuffle(all_rows)

    n = len(all_rows)
    n_train = int(n * args.train_ratio)
    n_val = int(n * args.val_ratio)
    train_rows = all_rows[:n_train]
    val_rows = all_rows[n_train : n_train + n_val]
    test_rows = all_rows[n_train + n_val :]

    out_dir = Path(args.out_dir)
    dump_jsonl(out_dir / "train.jsonl", train_rows)
    dump_jsonl(out_dir / "val.jsonl", val_rows)
    dump_jsonl(out_dir / "test.jsonl", test_rows)

    pos = sum(1 for r in all_rows if r.get("label_should_respond"))
    summary = {
        "total": n,
        "positive": pos,
        "positive_ratio": round(pos / n, 6) if n else 0.0,
        "train": len(train_rows),
        "val": len(val_rows),
        "test": len(test_rows),
        "out_dir": str(out_dir),
    }
    with (out_dir / "summary.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
