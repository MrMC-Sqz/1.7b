# Active Response V1

## Current intent model choice

- Primary: `Qwen/Qwen3-1.7B` (through `QwenIntentEngine`)
- Fallback: `RuleBasedIntentEngine` when model runtime is unavailable

## Run demo

```bash
python -m scripts.run_demo
```

## Run tests

```bash
python -m unittest discover -s tests -p "test_*.py" -q
```

## What this includes

- `active_response/intent_engine.py`: `QwenIntentEngine` + rule fallback, same `score(context, current_utt)` interface.
- `active_response/response_manager.py`: multi-pending queue per speaker.
- `active_response/pipeline.py`: supports `no_need / interrupted / delivered / merged / discarded` and both offline + streaming usage.
- `scripts/run_demo.py`: offline and streaming event-loop demos.
- `tests/test_pipeline.py`: coverage for interrupted, delivered, merged/discarded, and stream flushing behavior.
