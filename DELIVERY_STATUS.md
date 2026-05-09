# Delivery Status (as of 2026-05-10)

## Completed
- V1 architecture and modular codebase are implemented.
- Qwen 3 1.7B inference path is integrated in `QwenIntentEngine`.
- Rule fallback path is in place for model load/inference failures.
- Multi-pending queue management is implemented per speaker.
- `merged` / `discarded` runtime behaviors are implemented.
- Stream-like processing API is implemented (`process_utterance` + `finalize`).
- Event JSONL logging is supported (`V1Config.event_log_path`).
- Offline evaluation script is available (`scripts/evaluate_offline.py`).
- Stream JSONL runner is available (`scripts/run_stream_jsonl.py`).
- Unit tests cover core pipeline flows.

## Remaining for formal delivery
- Real upstream ASR integration adapter (direct runtime feed from your ASR service).
- Production threshold tuning with your real labeled set.
- Full acceptance report with agreed KPIs (P50/P95 latency, precision/recall, false trigger rate).

## Suggested acceptance checklist
1. Run offline evaluation on your internal labeled JSONL.
2. Confirm KPI thresholds with product/algorithm owners.
3. Run stream JSONL replay from real ASR exports.
4. Enable event logging and review failure/fallback reasons.
5. Freeze config and publish deployment bundle.
