# Semi-auto Annotation Progress (2026-05-10)

## 1) Data migration status
- Raw extracted AISHELL-5 has been migrated to:
  - `G:\1.7b\data\raw\aishell5\Dev_extracted\Dev\...`
  - `G:\1.7b\data\raw\aishell5\Eval1_extracted\Eval1\...`
- Current counts on `G:`:
  - `Dev_extracted`: 228 files
  - `Eval1_extracted`: 230 files
- Archive backups are kept at:
  - `C:\Users\46638\dataset_cache\aishell5_archives\Dev.tar.gz`
  - `C:\Users\46638\dataset_cache\aishell5_archives\Eval1.tar.gz`

## 2) Semi-auto annotation pipeline
### Stage 1: Rule-only full scan
- Input: `data/pack/aishell5_active_response_weak/train.jsonl`
- Output:
  - `data/annotate_pool/stage1_rule_train/scored_all.jsonl`
  - `data/annotate_pool/stage1_rule_train/review_top_4000.jsonl`
- Summary:
  - rows: 32,927
  - weak-conflict rows: 534

### Stage 2: Rule + score-head rerank
- Input: `data/annotate_pool/stage1_rule_train/review_top_4000.jsonl`
- Output:
  - `data/annotate_pool/stage2_scorehead_train_top4k/scored_all.jsonl`
  - `data/annotate_pool/stage2_scorehead_train_top4k/review_top_1200.jsonl`
- Summary:
  - rows: 4,000
  - disagreement rows: 29
  - weak-conflict rows: 563

### Stage 3: Qwen deep check (sample run)
- Input: `data/annotate_pool/stage2_scorehead_train_top4k/review_top_1200.jsonl`
- Output:
  - `data/annotate_pool/stage3_qwen_only_top1200_sample120/scored_all.jsonl`
  - `data/annotate_pool/stage3_qwen_only_top1200_sample120/review_top_80.jsonl`
- Summary:
  - rows: 120
  - disagreement rows: 29

## 3) Manual review and merge
- Review file format includes:
  - `review_status` (`todo` / custom)
  - `human_label` (`true` / `false`)
  - `review_note`
- Merge command:
  - `python -m scripts.merge_review_labels --base data/pack/aishell5_active_response_weak/train.jsonl --review <review_jsonl> --output data/annotate_review/train_merged.jsonl --changes-output data/annotate_review/train_merged_changes.jsonl`

## 4) Notes
- On 4GB VRAM, running Qwen + score-head in the same process can trigger OOM; use chunked Qwen-only runs (`--start-index` + `--max-rows`) for Stage 3.
