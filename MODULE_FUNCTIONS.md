# Active Response Modules (V1)

## 1. `active_response/domain.py`
- Purpose: shared data contracts across modules.
- Main dataclasses:
  - `Utterance`
  - `IntentResult`
  - `PendingResponse`
  - `DecisionEvent`

## 2. `active_response/config.py`
- Purpose: runtime knobs for model, thresholds, timing, and logging.
- Key fields:
  - `urgency_threshold`
  - `wait_ms`
  - `context_window_ms`
  - `max_pending_per_speaker`
  - `use_qwen_intent_engine`
  - `intent_model_name` (`Qwen/Qwen3-1.7B`)
  - `intent_device_map`
  - `intent_max_new_tokens`
  - `intent_inference_timeout_sec`
  - `event_log_path`

## 3. `active_response/context_buffer.py`
- Purpose: keep utterances in global time order and return recent context windows.
- Main methods:
  - `add_utterance`
  - `recent_context`
  - `recent_by_speaker`

## 4. `active_response/intent_engine.py`
- Purpose: score whether system should proactively respond.
- Components:
  - `IntentEngine` protocol
  - `RuleBasedIntentEngine` (fallback)
  - `QwenIntentEngine` (primary, uses Qwen3-1.7B)
  - `ScoreHeadIntentEngine` (fine-tuned regression/classification head)
- Output contract: always returns `IntentResult`.

## 5. `active_response/response_manager.py`
- Purpose: manage per-speaker pending response queues.
- Main methods:
  - `add_pending`
  - `discard_pending`
  - `merge_latest_pending`
  - `pop_due`
  - `get_latest_pending`
  - `all_pending`

## 6. `active_response/timing_policy.py`
- Purpose: response timing rules.
- Main functions:
  - `plan_time`
  - `is_interrupted`

## 7. `active_response/pipeline.py`
- Purpose: orchestration layer for offline and stream-like processing.
- Main entry points:
  - `run(utterances)`
  - `process_utterance(utterance, next_start_ms=None)`
  - `finalize()`
- Event types:
  - `no_need`
  - `interrupted`
  - `delivered`
  - `merged`
  - `discarded`

## 8. `scripts/run_demo.py`
- Purpose: quick local smoke check for offline and stream behavior.

## 9. `scripts/evaluate_offline.py`
- Purpose: labeled JSONL evaluation with classification and latency metrics.

## 10. `scripts/run_stream_jsonl.py`
- Purpose: feed stream-like JSONL utterances and emit event JSONL.

## 11. `tests/test_pipeline.py`
- Purpose: core behavior coverage for no_need/interrupted/delivered/merged/discarded and stream flushing.

## 12. `scripts/train_score_head.py`
- Purpose: fine-tune a score head model from labeled JSONL, intended for GPU training.

## 13. `scripts/build_semiauto_annotation_pool.py`
- Purpose: build semi-auto annotation candidates with multi-engine scoring, disagreement, and uncertainty ranking.
- Outputs:
  - `scored_all.jsonl`
  - `review_top_{k}.jsonl`
  - `summary.json`

## 14. `scripts/merge_review_labels.py`
- Purpose: merge human-reviewed `human_label` values back into a base JSONL dataset and emit change logs.
