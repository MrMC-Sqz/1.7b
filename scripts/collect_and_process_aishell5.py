import argparse
import json
import re
import tarfile
from pathlib import Path
from urllib.request import urlretrieve


AISHELL5_URLS = {
    "Dev": "https://www.openslr.org/resources/159/Dev.tar.gz",
    "Eval1": "https://www.openslr.org/resources/159/Eval1.tar.gz",
}

POSITIVE_HINTS = (
    "导航",
    "空调",
    "温度",
    "车窗",
    "天窗",
    "除雾",
    "雨刷",
    "音量",
    "播放",
    "暂停",
    "下一首",
    "打电话",
    "帮我",
    "麻烦",
    "可以吗",
    "怎么",
    "如何",
    "查一下",
)


def download_if_needed(url: str, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists() and dst.stat().st_size > 0:
        return
    print(f"[download] {url} -> {dst}")
    urlretrieve(url, str(dst))


def extract_if_needed(tar_path: Path, extract_dir: Path) -> None:
    marker = extract_dir / "Dev"
    if marker.exists():
        return
    extract_dir.mkdir(parents=True, exist_ok=True)
    print(f"[extract] {tar_path} -> {extract_dir}")
    with tarfile.open(tar_path, "r:gz") as tf:
        tf.extractall(path=extract_dir)


def parse_textgrid(textgrid_path: Path) -> list[dict]:
    lines = textgrid_path.read_text(encoding="utf-8").splitlines()
    out: list[dict] = []
    speaker = "UNKNOWN"
    i = 0
    seg_idx = 0
    while i < len(lines):
        line = lines[i].strip()
        name_match = re.match(r'name = "(.*)"', line)
        if name_match:
            speaker = name_match.group(1)
            i += 1
            continue

        if re.match(r"intervals \[\d+\]:", line):
            if i + 3 >= len(lines):
                break
            xmin_line = lines[i + 1].strip()
            xmax_line = lines[i + 2].strip()
            text_line = lines[i + 3].strip()
            xmin_match = re.match(r"xmin = ([0-9eE\.\-]+)", xmin_line)
            xmax_match = re.match(r"xmax = ([0-9eE\.\-]+)", xmax_line)
            text_match = re.match(r'text = "(.*)"', text_line)
            if xmin_match and xmax_match and text_match:
                text = text_match.group(1).strip()
                if text:
                    seg_idx += 1
                    start_ms = int(float(xmin_match.group(1)) * 1000)
                    end_ms = int(float(xmax_match.group(1)) * 1000)
                    out.append(
                        {
                            "speaker_id": speaker,
                            "text": text,
                            "start_ms": start_ms,
                            "end_ms": end_ms,
                            "seg_index": seg_idx,
                        }
                    )
            i += 4
            continue
        i += 1
    return out


def should_respond_weak(text: str) -> bool:
    return any(token in text for token in POSITIVE_HINTS)


def build_jsonl(extract_dir: Path, split: str, out_raw: Path, out_weak: Path) -> dict:
    textgrids = sorted((extract_dir / split).rglob("*.TextGrid"))
    out_raw.parent.mkdir(parents=True, exist_ok=True)
    num_sessions = set()
    rows = 0
    weak_pos = 0

    with out_raw.open("w", encoding="utf-8") as f_raw, out_weak.open("w", encoding="utf-8") as f_weak:
        for tg in textgrids:
            session_id = tg.parent.name
            file_id = tg.stem
            num_sessions.add(session_id)
            segments = parse_textgrid(tg)
            for seg in segments:
                rows += 1
                split_tag = split.lower()
                utt_id = f"aishell5_{split_tag}_{session_id}_{file_id}_{seg['speaker_id']}_{seg['seg_index']:04d}"
                item = {
                    "utterance_id": utt_id,
                    "speaker_id": seg["speaker_id"],
                    "text": seg["text"],
                    "start_ms": seg["start_ms"],
                    "end_ms": seg["end_ms"],
                    "dataset": f"AISHELL-5-{split}",
                    "session_id": session_id,
                    "source_file": str(tg).replace("\\", "/"),
                }
                f_raw.write(json.dumps(item, ensure_ascii=False) + "\n")

                label = should_respond_weak(seg["text"])
                if label:
                    weak_pos += 1
                labeled = dict(item)
                labeled["label_should_respond"] = label
                f_weak.write(json.dumps(labeled, ensure_ascii=False) + "\n")

    return {
        "num_textgrid_files": len(textgrids),
        "num_sessions": len(num_sessions),
        "num_utterances": rows,
        "weak_positive": weak_pos,
        "weak_positive_ratio": round(weak_pos / rows, 4) if rows else 0.0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect and process AISHELL-5 Dev into project JSONL schema.")
    parser.add_argument(
        "--split",
        default="Dev",
        choices=["Dev", "Eval1"],
        help="AISHELL-5 split to collect and process.",
    )
    parser.add_argument(
        "--cache-root",
        default=r"C:\Users\46638\dataset_cache\aishell5",
        help="Where to store raw downloads and extraction.",
    )
    parser.add_argument(
        "--out-raw",
        default="",
        help="Output raw JSONL path.",
    )
    parser.add_argument(
        "--out-weak",
        default="",
        help="Output weak-labeled JSONL path.",
    )
    args = parser.parse_args()

    split = args.split
    cache_root = Path(args.cache_root)
    tar_path = cache_root / f"{split}.tar.gz"
    extract_dir = cache_root / f"{split}_extracted"
    out_raw = Path(args.out_raw) if args.out_raw else Path(
        rf"G:\1.7b\data\collected\aishell5_{split.lower()}_segments.jsonl"
    )
    out_weak = Path(args.out_weak) if args.out_weak else Path(
        rf"G:\1.7b\data\collected\aishell5_{split.lower()}_segments_weak.jsonl"
    )

    download_if_needed(AISHELL5_URLS[split], tar_path)
    extract_if_needed(tar_path, extract_dir)
    stats = build_jsonl(extract_dir, split, out_raw, out_weak)
    stats["split"] = split
    stats["out_raw"] = str(out_raw)
    stats["out_weak"] = str(out_weak)
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
