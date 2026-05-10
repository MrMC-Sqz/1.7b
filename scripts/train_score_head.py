import argparse
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class TrainItem:
    text: str
    label: float


def load_items(path: Path) -> list[TrainItem]:
    items: list[TrainItem] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            label = 1.0 if bool(row["label_should_respond"]) else 0.0
            text = (
                f"[{row['start_ms']}-{row['end_ms']}] speaker={row['speaker_id']} "
                f"text={row['text']}"
            )
            items.append(TrainItem(text=text, label=label))
    return items


def split_train_eval(items: list[TrainItem], eval_ratio: float) -> tuple[list[TrainItem], list[TrainItem]]:
    n_eval = max(1, int(len(items) * eval_ratio))
    return items[n_eval:], items[:n_eval]


def compute_binary_metrics(preds: list[float], labels: list[float], threshold: float = 0.5) -> dict[str, float]:
    tp = fp = tn = fn = 0
    for pred, label in zip(preds, labels):
        binary = pred >= threshold
        truth = label >= 0.5
        if binary and truth:
            tp += 1
        elif binary and not truth:
            fp += 1
        elif (not binary) and (not truth):
            tn += 1
        else:
            fn += 1
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    acc = (tp + tn) / (tp + tn + fp + fn) if tp + tn + fp + fn else 0.0
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "accuracy": acc,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Fine-tune a score head for proactive response scoring.")
    parser.add_argument("--train-jsonl", required=True, help="Labeled JSONL path.")
    parser.add_argument(
        "--base-model",
        default="distilbert-base-uncased",
        help="Base HF model with safetensors support.",
    )
    parser.add_argument("--output-dir", default="out/score_head_model", help="Output directory.")
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--lr", type=float, default=2e-5)
    parser.add_argument("--eval-ratio", type=float, default=0.1)
    parser.add_argument("--max-length", type=int, default=256)
    args = parser.parse_args()

    import torch
    from safetensors.torch import save_file
    from torch.utils.data import DataLoader
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    items = load_items(Path(args.train_jsonl))
    if len(items) < 10:
        raise ValueError("Need at least 10 samples for a minimal fine-tuning run.")
    train_items, eval_items = split_train_eval(items, args.eval_ratio)

    tokenizer = AutoTokenizer.from_pretrained(args.base_model, trust_remote_code=True)
    model = AutoModelForSequenceClassification.from_pretrained(
        args.base_model,
        trust_remote_code=True,
        num_labels=1,
        problem_type="regression",
    )
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device)
    model.train()

    def collate(rows: list[TrainItem]) -> dict[str, torch.Tensor]:
        texts = [r.text for r in rows]
        labels = torch.tensor([r.label for r in rows], dtype=torch.float32)
        enc = tokenizer(
            texts,
            truncation=True,
            max_length=args.max_length,
            padding=True,
            return_tensors="pt",
        )
        enc["labels"] = labels
        return enc

    train_loader = DataLoader(train_items, batch_size=args.batch_size, shuffle=True, collate_fn=collate)
    eval_loader = DataLoader(eval_items, batch_size=args.batch_size, shuffle=False, collate_fn=collate)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr)

    for epoch in range(args.epochs):
        running = 0.0
        steps = 0
        for batch in train_loader:
            batch = {k: v.to(device) for k, v in batch.items()}
            out = model(**batch)
            loss = out.loss
            loss.backward()
            optimizer.step()
            optimizer.zero_grad()
            running += float(loss.item())
            steps += 1
        avg_loss = running / max(1, steps)

        # Eval
        model.eval()
        preds: list[float] = []
        labels: list[float] = []
        with torch.no_grad():
            for batch in eval_loader:
                labels.extend([float(x) for x in batch["labels"].tolist()])
                batch = {k: v.to(device) for k, v in batch.items()}
                out = model(**batch)
                # Regression output; clamp to [0,1].
                scores = out.logits.squeeze(-1).detach().cpu().tolist()
                if isinstance(scores, float):
                    scores = [scores]
                preds.extend([max(0.0, min(1.0, float(s))) for s in scores])
        metrics = compute_binary_metrics(preds, labels)
        print(
            f"epoch={epoch + 1} train_loss={avg_loss:.4f} "
            f"eval_f1={metrics['f1']:.4f} eval_acc={metrics['accuracy']:.4f}"
        )
        model.train()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    tokenizer.save_pretrained(output_dir)
    model.config.save_pretrained(output_dir)
    state = {k: v.detach().cpu().contiguous() for k, v in model.state_dict().items()}
    save_file(state, str(output_dir / "model.safetensors"))
    print(f"Saved score-head model to: {output_dir}")


if __name__ == "__main__":
    main()
