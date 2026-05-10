# Data Collection and Processing Log

## Scope
This project collected and processed external data for proactive in-car response research.

## Source datasets
1. AISHELL-5 Dev  
   - URL: `https://www.openslr.org/resources/159/Dev.tar.gz`  
   - Source page: `https://www.openslr.org/159/`
2. AISHELL-5 Eval1  
   - URL: `https://www.openslr.org/resources/159/Eval1.tar.gz`  
   - Source page: `https://www.openslr.org/159/`

## Collection date
- Download and processing executed on **2026-05-10**.

## Storage layout
- Current raw extracted location (migrated on **2026-05-10**):  
  - `G:\1.7b\data\raw\aishell5\Dev_extracted\Dev\...`  
  - `G:\1.7b\data\raw\aishell5\Eval1_extracted\Eval1\...`
- Archive backup location:  
  - `C:\Users\46638\dataset_cache\aishell5_archives\Dev.tar.gz`  
  - `C:\Users\46638\dataset_cache\aishell5_archives\Eval1.tar.gz`

## Processing pipeline
Script:
- `scripts/collect_and_process_aishell5.py`

What it does:
1. Downloads `Dev` or `Eval1` split (if missing).
2. Extracts archive.
3. Parses `.TextGrid` interval tiers.
4. Emits project JSONL schema:
   - `utterance_id`
   - `speaker_id`
   - `text`
   - `start_ms`
   - `end_ms`
   - `dataset`
   - `session_id`
   - `source_file`
5. Builds weak labels `label_should_respond` using keyword heuristics.

## Processed outputs
Collected JSONL:
- `data/collected/aishell5_dev_segments.jsonl`
- `data/collected/aishell5_dev_segments_weak.jsonl`
- `data/collected/aishell5_eval1_segments.jsonl`
- `data/collected/aishell5_eval1_segments_weak.jsonl`

Pack builder:
- `scripts/build_aishell5_active_response_pack.py`

Packed dataset:
- `data/pack/aishell5_active_response_weak/train.jsonl`
- `data/pack/aishell5_active_response_weak/val.jsonl`
- `data/pack/aishell5_active_response_weak/test.jsonl`
- `data/pack/aishell5_active_response_weak/summary.json`

## Statistics
- Dev weak set:
  - textgrid files: 108
  - sessions: 18
  - utterances: 20,822
  - weak positive ratio: 0.0234
- Eval1 weak set:
  - textgrid files: 108
  - sessions: 18
  - utterances: 20,337
  - weak positive ratio: 0.0106
- Combined pack:
  - total: 41,159
  - positives: 702
  - positive ratio: 0.017056
  - split: train 32,927 / val 4,115 / test 4,117

## Baseline scoring on packed test split
Command:
- `python -m scripts.evaluate_offline --input data/pack/aishell5_active_response_weak/test.jsonl`

Result (Rule engine):
- precision: 1.0000
- recall: 0.0588
- f1: 0.1111
- accuracy: 0.9845

## Notes
- Weak labels are heuristic only and should be replaced by manual or model-assisted annotation for final research conclusions.
- Because the JSONL files were generated before migration, `source_file` fields still point to historical `C:` paths; this does not affect model training fields (`text`, `start_ms`, `end_ms`, labels).
