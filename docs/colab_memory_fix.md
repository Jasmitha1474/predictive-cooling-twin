# Notebook 03 RAM crash: diagnosis and fix

Checked against the code in `research/src/pcool/` (the same code that is in the Drive zip).

## A. Root cause

The crash is a **project memory problem**, not Colab's compute limit. `stage_train_evaluate`
loaded three things whole into RAM. On the full dataset, each of them is larger than 12.7 GB on its own:

| # | What the old code did | Where | Measured bytes per row (13-job test data) | Estimated size on the full dataset* |
|---|---|---|---|---|
| 1 | Read the **entire feature table** (all splits, all ~77 columns, float64, string ids as Python objects), then copied it into train/val/test frames | `pipeline.load_features()`, called first in `stage_train_evaluate` | 888 B/row as loaded | ~25 GB, plus the train/val/test copies |
| 2 | Read **all clean 1 s series** with string `series_id/job_id/label` columns for the LSTM | `pipeline.load_clean_for_lstm()` → `lstm.SeriesStore(clean, …)` | 259 B/row | ~38 GB |
| 3 | Built the **full validation and test window arrays** (anchors × 60 × 6 float32) at once, then copied them again with `X[valid]`. This was repeated for every seed, twice (val and test) | `lstm.SeriesStore.windows()`, `lstm.train_lstm()`, `lstm.predict_lstm()` | 1,440 B per window | ~6 GB per split, ~12 GB with the copy |

\* The full-dataset sizes are **estimates**: the full row counts were scaled from the 13-job test data
(68.8 GB raw → ~1.5×10⁸ clean rows → ~2.8×10⁷ feature rows). They are not measured. Run
`pipeline.size_report(cfg)` in Colab to get the real counts (Step 1 below).

Step 1 already exceeds 12.7 GB, so the old run most likely died before it printed the
`windows: train … val … test …` line. If that line did print, step 2 or 3 is the cause.

Contributing (smaller) issues:
- All 10 LSTM runs (2 models × 5 seeds) were **kept in memory** together with their full val/test
  prediction frames (`runs.append((r, pte, pva))`).
- LSTM val/test prediction ran on the **CPU** even when a GPU was available, which was slow rather than memory-heavy.
- Nothing was saved until the very end, so any crash lost everything.

Ruled out:
- **Multiprocessing / DataLoader workers:** the training stage uses none, and batches are sliced by hand.
  (`stage_features` in notebook 02 uses a process pool, but that is not this notebook.)
- **GPU VRAM:** the LSTM is small (64 hidden units, 2 layers) and the batches are 1,024 × 60 × 6 floats.
  The T4's 15 GB was never the limit.
- **Retained computation graphs:** validation runs under `torch.no_grad()`, and only the loss carries a graph.
- **Parallel seeds:** the seeds already ran one after another. The problem was what each seed kept in memory.
- **`ModuleNotFoundError: No module named 'pccool'`:** the package is called **`pcool`** (one "c").
  The notebook uses `from pcool …`. That old error came from a cell that typed `pccool`.
  It is unrelated to the RAM crash.

## B. Responsible files and functions

- `research/src/pcool/pipeline.py`: `stage_train_evaluate`, `load_features`, `load_clean_for_lstm`, `clock_ablation`
- `research/src/pcool/lstm.py`: `SeriesStore`, `train_lstm`, `predict_lstm`, `_predict`
- `research/src/pcool/models_gbm.py`: `train_gbm`, `_prep` (a pandas copy per model, plus LightGBM's own copy for each of the 6 targets)

## C. The fix (memory behaviour only)

| Change | File / function |
|---|---|
| Read only the columns a model needs, one split at a time, floats as float32, strings as categories (`make_loader`) | `pipeline.py` |
| LightGBM: build the float32 matrix once per model, bin it **once**, reuse the binned Dataset for all 6 targets (only the label changes), free the raw matrix | `models_gbm.train_gbm` |
| LSTM: stream the clean files into **one** float32 array (≈ rows × 6 × 4 bytes), cut windows **batch by batch** with vectorised indexing | `lstm.SeriesStore.from_parquet_dir`, `anchor_ends`, `batch` |
| LSTM validation and prediction in batches of 8,192 windows, on the GPU when available | `lstm.train_lstm`, `_predict_ends`, `predict_lstm` |
| Each LSTM seed: save `model.pt`, test predictions (`.npy`) and val metrics to disk, then `del` + `gc.collect()` + `torch.cuda.empty_cache()` | `pipeline.stage_train_evaluate` |
| Each LightGBM booster is saved as soon as it is fitted, with `info.json` as the checkpoint | `models_gbm.train_gbm` |
| **Resume:** re-running the cell skips finished boosters and seeds | both |
| `[mem]` RSS printouts at each stage, and `pipeline.size_report(cfg)` | `pipeline.py` |

The backend's model loader was updated to read the new LightGBM format: `backend/controller/forecasters.py`.

## D. Scientific validity

**Unchanged:** dataset, chronological split, features, targets, the six models (B0, B1, A0, A1, L0, L1),
5 seeds per LSTM, LSTM architecture, training-window sampling (same 800,000 cap with the same
`random_state=seed`), scaling, loss, optimiser, epochs, patience, the seed-selection rule, all metrics,
the bootstrap, the model-selection rule, and the clock ablation.

Verified locally on the 13-job test data:
- The new LSTM windows are **byte-identical** to the old ones (8,690 anchors, same validity mask).
- A full run followed by a resumed run gives **identical** test metrics.

Small differences, stated so the write-up can mention them:
1. Values are held as **float32 instead of float64**. LightGBM bins features into at most 255 bins, so the
   effect is negligible. Metric values may differ in roughly the 6th–7th significant digit.
2. LightGBM is called through its native API with the **same hyperparameter values**. Early stopping now
   watches **MAE (l1) only**. The old scikit-learn call also tracked the default l2 metric and could stop on
   whichever stalled first. Watching MAE only matches the methodology (selection by MAE), and the best
   iteration may differ slightly. No full results existed before, so nothing already reported changes.
3. LSTM val/test prediction runs on the GPU instead of the CPU. This causes floating-point
   differences at roughly 1e-6.

## E. Colab limit or project problem?

**Project memory problem.** With the fix, the largest arrays are estimated at about 4 GB (LightGBM train
matrix) and about 3.5 GB (LSTM store), not held at the same time. That is estimated to fit in 12.7 GB, but it
is not yet measured. Step 1 prints the real sizes. If `est_gb_largest_gbm_train_matrix_float32` + 2 GB or
`est_gb_lstm_store_float32` + 3 GB comes out above ~11 GB, stop and report back before changing the design.

**Runtime is a separate concern and was not measured.** LightGBM runs on Colab's 2 CPU cores
(18 fits on ~2×10⁷ rows). A free session can disconnect before it finishes. That is why every
booster and seed is now checkpointed.

## Safe Colab procedure

1. **Start clean:** Runtime → *Disconnect and delete runtime*, then reconnect with a **T4 GPU**.
   Replace `MyDrive/pred_cooling/research/` with the new zip contents. **Do not touch `MyDrive/pred_cooling/work/`**:
   it holds your cleaned data and features.
2. **Run the setup cell** (mount Drive, `pip install`, `from pcool.config import Config`). Check the spelling: `pcool`.
3. **Run Step 1 (size check)** and send me the printed dictionary if any value looks large.
4. **Run Step 2 (train)**. Watch the `[mem]` lines and the RAM gauge in the top-right corner.
   `!free -h` and `!nvidia-smi` can run in a second notebook while it trains.
5. **Don't run:** notebooks 01 and 02 again (their outputs are already in `work/`), *Run all*, any old
   cell that says `pccool`, or `pipeline.load_features(cfg)`.
6. **If Colab disconnects:** reconnect, run the setup cell, then run Step 2 again. Finished boosters print
   "loading (resume)" and finished seeds print "already done (resume)". Only the booster or seed that was
   in progress restarts.
7. **Verify (Step 3 cell):** it checks that `work/reports/results.json` and `results_table.csv` exist, prints
   their timestamps and the list of models, and shows the MAE table. Then send me both files plus
   `audit_summary.json` and `split_report.json`.
