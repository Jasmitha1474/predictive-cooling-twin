# Research pipeline (Layer A: real telemetry only)

Code: `src/pcool/`. Tests: `tests/`. Notebooks for Google Colab: `notebooks/`.
Data: MIT Supercloud labelled subset, streamed from its public S3 bucket inside Colab.
No synthetic data is created anywhere in this pipeline.

## Run it (Google Colab, not a laptop)

1. Copy this `research/` folder to Google Drive as `MyDrive/pred_cooling/research`.
2. Open `notebooks/01_dataset_acquisition_and_audit.ipynb` in Colab and run all cells. It downloads
   the 3,430 labelled jobs (68.8 GB raw CSV) one file at a time, cleans each to a 1 s grid,
   and writes Parquet plus an audit record to `MyDrive/pred_cooling/work/`. If Colab disconnects,
   re-run it: finished files are skipped.
3. Run `02_split_and_features.ipynb` (chronological job split, features).
4. Switch the runtime to GPU and run `03_models_and_evaluation.ipynb`.
5. Results appear in `work/reports/results.json` and `results_table.csv`. Models are saved in `work/models/`
   with `manifest.json`. Send those files back so the results page and backend can use them.

## What each stage does

| Stage | Module | Output |
|---|---|---|
| Acquisition + cleaning + audit | `preprocess.py`, `data_access.py` | `work/clean/*.parquet`, `reports/preprocess_audit.jsonl`, `reports/audit_summary.json` |
| Chronological split | `split.py` | `reports/split_jobs.csv`, `reports/split_report.json` |
| Features + targets | `features.py` | `work/features/*.parquet` |
| B0, B1, A0, A1 | `models_gbm.py` | LightGBM text models |
| L0, L1 (5 seeds each) | `lstm.py` | `model.pt` and `model.onnx` |
| Metrics, bootstrap CIs, selection | `evaluate.py`, `pipeline.py` | `reports/results.json` |

## Implementation choices not spelled out in docs/methodology.md

- `t_since_start_s` is measured from the start of the series segment (a GPU's contiguous data
  within a job), because that is what is known at prediction time.
- Rows are sampled every 5 s (`train_stride_s`, `eval_stride_s`) to fit Colab memory. Windows
  still use every 1 s sample.
- The LSTM uses at most 800,000 randomly chosen training windows (`lstm_max_train_windows`).
  Validation and test are not subsampled.
- All models are scored on the same test rows: the anchors where a full 60 s LSTM window
  exists. Tree models are also scored on their full test set (`test_full_set`).
- Because clock columns exist in only about 5 % of labelled jobs, the main models do not use clocks.
  The clock ablation (A1 vs A2) trains and tests only on jobs that have clock columns. It is skipped,
  and says so, if any split has too few such jobs.
- Notebooks are grouped into three files (01 acquisition/audit, 02 split/features, 03 models/evaluation)
  instead of the six names in the brief, because one training call produces all model results
  on identical rows.

## Memory (Colab free tier, 12.7 GB RAM)

`stage_train_evaluate` never loads the whole feature table. It reads only the columns a model needs,
one split at a time, as float32. LightGBM bins the training matrix once per model and reuses it for the six
targets. LSTM windows are cut batch by batch from one float32 store of the clean series. Each booster and
each LSTM seed is saved as soon as it finishes (`work/models/<model>/…`), so re-running the cell resumes.
Run `pipeline.size_report(cfg)` first to see the row counts and the estimated size of the largest arrays.

## Smoke test (code check only, NOT results)

The pipeline was run end to end on a laptop on 13 small labelled jobs (21.5 MB) to check that the
code works. Its outputs are not research results and are not reported anywhere: two test jobs cannot
support any conclusion. `python3 -m pytest research/tests` checks that features never use future data.

On macOS, LightGBM and PyTorch load different OpenMP runtimes, which can crash or hang the process. Set
`OMP_NUM_THREADS=1` for local runs. Colab (Linux) is not affected.
