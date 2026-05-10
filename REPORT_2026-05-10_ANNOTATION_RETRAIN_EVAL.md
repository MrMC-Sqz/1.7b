# Round-1 Backflow + Retrain + Evaluation Report (2026-05-10)

## 1. Scope completed
- Data migration to `G:` verified.
- Semi-auto annotation candidate generation completed (Stage1/2/3).
- Label backflow pipeline executed.
- Score-head retraining executed.
- Offline evaluation completed on:
  - weak-label packed test set (`data/pack/aishell5_active_response_weak/test.jsonl`)
  - real ASR export labeled set (`data/asr_export_round1.jsonl`)

## 2. Data migration status
- Raw dataset root:
  - `G:\1.7b\data\raw\aishell5\Dev_extracted`
  - `G:\1.7b\data\raw\aishell5\Eval1_extracted`
- Integrity check:
  - `Dev_extracted`: 228 files
  - `Eval1_extracted`: 230 files
- Archive backup:
  - `C:\Users\46638\dataset_cache\aishell5_archives\Dev.tar.gz`
  - `C:\Users\46638\dataset_cache\aishell5_archives\Eval1.tar.gz`

## 3. Semi-auto annotation and backflow
### 3.1 Candidate generation
- Stage1 summary: `data/annotate_pool/stage1_rule_train/summary.json`
- Stage2 summary: `data/annotate_pool/stage2_scorehead_train_top4k/summary.json`
- Stage3 summary: `data/annotate_pool/stage3_qwen_only_top1200_sample120/summary.json`

### 3.2 Backflow result
- Reviewed file (guarded auto-label):
  - `data/annotate_review/review_top_1200_autolabeled_guarded.jsonl`
- Merged file:
  - `data/annotate_review/train_merged_round1_guarded.jsonl`
- Merge stats:
  - reviewed rows: 1200
  - changed rows: 0

Note:
- An aggressive auto-label strategy (`ensemble`) changed 563 positive weak labels to negative and caused class collapse in training.
- This strategy was rejected for production backflow.

## 4. Training
### 4.1 Runtime fix applied
- `ScoreHeadIntentEngine` inference changed from `clamp(logit)` to `sigmoid(logit)`.
- `train_score_head.py` changed to:
  - BCEWithLogits training (`pos_weight` support)
  - deterministic shuffle before split (fixes zero-positive train split issue)

### 4.2 Final retrain run
- Command:
  - `python -m scripts.train_score_head --train-jsonl data/annotate_review/train_merged_round1_guarded.jsonl --output-dir out/score_head_round3_guarded_bce_shuffle --epochs 1 --batch-size 4 --eval-ratio 0.1 --seed 42`
- Log: `out/train_score_head_round3.log`
- Key log metrics:
  - train_size=29635, eval_size=3292
  - train_pos=500, train_neg=29135, pos_weight=58.27
  - eval_f1=0.1045, eval_acc=0.7345

## 5. Evaluation metrics
## 5.1 Weak-label packed test set (N=4117)
- Rule engine (threshold=0.7):
  - precision=1.0000 recall=0.0588 f1=0.1111 accuracy=0.9845
  - source: `out/metrics_test_rule_before.json`
- Score-head (before retrain, threshold=0.5):
  - precision=0.0143 recall=0.7059 f1=0.0280 accuracy=0.1892
  - source: `out/metrics_test_scorehead_before_t05_v2.json`
- Score-head (after retrain round3):
  - threshold=0.5: precision=0.0147 recall=0.6912 f1=0.0289 accuracy=0.2320
  - threshold=0.7: precision=0.0149 recall=0.6912 f1=0.0292 accuracy=0.2410
  - sources:
    - `out/metrics_test_scorehead_after_round3_t05.json`
    - `out/metrics_test_scorehead_after_round3_t07.json`

## 5.2 Real ASR export labeled set (N=24)
- Rule engine (threshold=0.7):
  - precision=0.9091 recall=0.7143 f1=0.8000 accuracy=0.7917
  - source: `out/metrics_asr_rule_before.json`
- Score-head (before retrain, threshold=0.5):
  - precision=0.6087 recall=1.0000 f1=0.7568 accuracy=0.6250
  - source: `out/metrics_asr_scorehead_before_t05_v2.json`
- Score-head (after retrain round3):
  - threshold=0.5: precision=0.6190 recall=0.9286 f1=0.7429 accuracy=0.6250
  - threshold=0.7: precision=0.5789 recall=0.7857 f1=0.6667 accuracy=0.5417
  - sources:
    - `out/metrics_asr_scorehead_after_round3_t05.json`
    - `out/metrics_asr_scorehead_after_round3_t07.json`

## 6. Conclusion
- Backflow/retrain/evaluation pipeline has been executed end-to-end.
- On weak-label packed test set, rule engine still outperforms score-head in F1 due severe class imbalance and weak-label noise.
- On real ASR export small set, score-head is usable at threshold 0.5 but not better than rule baseline in this round.
- Current recommendation for delivery default:
  - keep rule engine as production baseline
  - keep score-head as experimental branch with continued annotation improvement

## 7. Generated artifacts
- Model:
  - `out/score_head_round3_guarded_bce_shuffle/`
- Training logs:
  - `out/train_score_head_round2.log`
  - `out/train_score_head_round3.log`
- Evaluation outputs:
  - `out/metrics_*.json`
  - `out/events_*.jsonl`
