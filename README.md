# Active Response V1

## Intent engine
- Primary: `Qwen/Qwen3-1.7B` (`QwenIntentEngine`)
- Fallback: `RuleBasedIntentEngine`

## Quick start
```bash
python -m scripts.run_demo
python -m unittest discover -s tests -p "test_*.py" -q
```

Check GPU visibility:
```bash
python -m scripts.check_gpu
```

## Stream JSONL run
```bash
python -m scripts.run_stream_jsonl --input data/sample_stream.jsonl
```

Optional realtime replay:
```bash
python -m scripts.run_stream_jsonl --input data/sample_stream.jsonl --realtime --speed 2.0
```

## Offline evaluation
Input schema (`jsonl`, one line per utterance):
- `utterance_id` (str)
- `speaker_id` (str)
- `text` (str)
- `start_ms` (int)
- `end_ms` (int)
- `label_should_respond` (bool)

Run:
```bash
python -m scripts.evaluate_offline --input data/sample_eval.jsonl
```

Use Qwen for evaluation:
```bash
python -m scripts.evaluate_offline --input data/sample_eval.jsonl --use-qwen
```

Tune Qwen decoding budget:
```bash
python -m scripts.evaluate_offline --input data/sample_eval.jsonl --use-qwen --max-new-tokens 256 --infer-timeout-sec 40
```

Save event output:
```bash
python -m scripts.evaluate_offline --input data/sample_eval.jsonl --output out/events.jsonl
```

## Event logging
Set `V1Config.event_log_path` to enable pipeline JSONL logs for all emitted events.

## Score-head fine-tuning (GPU)
Train a regression head from labeled JSONL:
```bash
python -m scripts.train_score_head --train-jsonl data/asr_export_round1.jsonl --output-dir out/score_head_model
```

For 4GB VRAM devices, keep a small base model (default `distilbert-base-uncased`) for score-head training.
Large bases like `Qwen/Qwen3-1.7B` usually OOM during full fine-tuning on 4GB.

Then switch pipeline config:
- `use_score_head_intent_engine=True`
- `score_head_model_path=out/score_head_model`

## Semi-auto annotation workflow
Stage 1 (rule-only full scan):
```bash
python -m scripts.build_semiauto_annotation_pool \
  --input data/pack/aishell5_active_response_weak/train.jsonl \
  --output-dir data/annotate_pool/stage1_rule_train \
  --top-k 4000
```

Stage 2 (rule + score-head rerank):
```bash
python -m scripts.build_semiauto_annotation_pool \
  --input data/annotate_pool/stage1_rule_train/review_top_4000.jsonl \
  --output-dir data/annotate_pool/stage2_scorehead_train_top4k \
  --top-k 1200 \
  --use-score-head \
  --score-head-model-path out/score_head_smoke_small
```

Optional Stage 3 (Qwen deep check on a smaller subset):
```bash
python -m scripts.build_semiauto_annotation_pool \
  --input data/annotate_pool/stage2_scorehead_train_top4k/review_top_1200.jsonl \
  --output-dir data/annotate_pool/stage3_qwen_only_top1200_sample120 \
  --start-index 0 \
  --max-rows 120 \
  --top-k 80 \
  --use-qwen \
  --qwen-device-map auto \
  --qwen-max-new-tokens 48 \
  --qwen-timeout-sec 10
```

Merge reviewed `human_label` back to training set:
```bash
python -m scripts.merge_review_labels \
  --base data/pack/aishell5_active_response_weak/train.jsonl \
  --review data/annotate_pool/stage2_scorehead_train_top4k/review_top_1200.jsonl \
  --output data/annotate_review/train_merged.jsonl \
  --changes-output data/annotate_review/train_merged_changes.jsonl
```

Auto-fill review labels (semi-auto round):
```bash
python -m scripts.auto_fill_review_labels \
  --input data/annotate_pool/stage2_scorehead_train_top4k/review_top_1200.jsonl \
  --output data/annotate_review/review_top_1200_autolabeled_guarded.jsonl \
  --strategy no_downgrade_rule
```
