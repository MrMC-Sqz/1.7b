# Active Response V1 (Worker C)

## Run demo

```bash
python -m scripts.run_demo
```

## Run tests

```bash
python -m unittest discover -s tests -p "test_*.py" -q
```

## What this includes

- `active_response/pipeline.py`: V1 orchestrator for `no_need / interrupted / delivered`.
- `scripts/run_demo.py`: sample utterances and event stream output.
- `tests/test_pipeline.py`: minimal path coverage for core decision flow.
