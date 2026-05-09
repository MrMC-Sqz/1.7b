# Active Response V1

## Intent engine
- Primary: `Qwen/Qwen3-1.7B` (`QwenIntentEngine`)
- Fallback: `RuleBasedIntentEngine`

## Quick start
```bash
python -m scripts.run_demo
python -m unittest discover -s tests -p "test_*.py" -q
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

Save event output:
```bash
python -m scripts.evaluate_offline --input data/sample_eval.jsonl --output out/events.jsonl
```

## Event logging
Set `V1Config.event_log_path` to enable pipeline JSONL logs for all emitted events.
