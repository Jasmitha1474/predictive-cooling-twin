# ML Methodology

Status: PLANNING DRAFT (awaiting your confirmation). No model has been trained; no
number below is a result. Numbers that appear are either facts read from the dataset
documentation/samples (cited) or design choices (marked *choice*).

## 1. Research question

Does richer telemetry (power, memory, clocks) and workload information improve
30/45/60-second forecasts of GPU power and GPU temperature compared with
(a) persistence and (b) a utilization-only model?

Hypotheses (to be accepted or rejected by measurement):

- H1: A full-telemetry model beats persistence on MAE at each horizon.
- H2: A full-telemetry model beats a utilization-only model.
- H3: Adding the workload label improves error over the same model without it.
- H4: An LSTM beats gradient boosting by a margin that justifies its cost
  (latency, size). If not, the simpler model is selected.

## 2. Data unit

One series = one `(job_id, gpu_index)` pair from the primary dataset (MIT Supercloud
labelled subset; see `docs/dataset.md`). Windows never cross series boundaries, so a
forecast never "sees" another job or another GPU.

## 3. Preprocessing pipeline (runs in Colab; deterministic; config-driven)

| Step (brief §10) | Concrete operation |
|---|---|
| 1 Load | Stream each labelled job's CSV(s) from the public S3 bucket (anonymous HTTPS); never on the laptop |
| 2 Inspect schema | Record header per file. Files have **two schemas** (10-column without clocks; 14-column with `clocks_current_sm_MHz`, `clocks_current_memory_MHz`, `clocks_current_video_MHz`, `power_limit_W`). Tag each series with its schema |
| 3 Parse timestamps | `timestamp` is Unix seconds (float). Convert to UTC datetime |
| 4 Sort | Sort by `(job_id, gpu_index, timestamp)` |
| 5 Duplicates | Drop exact duplicate rows; for duplicate timestamps keep the first and count them in the audit |
| 6 Missing values | No imputation across gaps > 2 s (*choice*); short gaps (≤ 2 s) are forward-filled only for slowly varying fields (memory used, clocks, power limit), never for targets |
| 7 Impossible values | Flag `utilization_* ∉ [0,100]`, `power_draw_W < 0` or `> 1.1 × power_limit_W` (when present), `temperature_* ∉ [0, 110]` °C, negative memory. Flagged rows are removed and counted |
| 8 Gaps | Split a series into segments at any gap > 2 s; segments shorter than (window + 60 s) are dropped from training |
| 9 Workload segments | The label is per job (from `labelled_jobids.csv`). Within a job we additionally derive *activity phases* from measured utilization (idle if `utilization_gpu_pct == 0` for ≥ 10 s). These derived phases are labelled "derived", never presented as dataset labels |
| 10 Scaling | Tree models: no scaling. LSTM: z-score fitted on the **training split only** |
| 11 Rolling features | See §5 |
| 12 Targets | See §4 |
| 13 Split | Chronological, by job start time; see §6 |

### Resampling and horizon-to-sample conversion

Raw sampling is irregular: consecutive timestamps on the same GPU differ by about
0.105–0.108 s in the 12 labelled files sampled (median per file). We resample every
series to a regular grid by averaging within bins.

| Grid | 30 s | 45 s | 60 s | Notes |
|---|---|---|---|---|
| 1 s (*primary choice*) | 30 steps | 45 steps | 60 steps | 10× fewer rows; matches controller rate |
| 100 ms (secondary) | 300 steps | 450 steps | 600 steps | Used only to test whether 1 s averaging loses predictive information |

Rule: steps = horizon_seconds / grid_seconds. With the 1 s grid all three horizons are
exact integers, so no rounding is needed.

## 4. Targets

For each horizon h ∈ {30, 45, 60} s:

- `power_t+h` = mean `power_draw_W` in the 1 s bin at t+h
- `temp_t+h` = mean `temperature_gpu` in the 1 s bin at t+h

Models predict the **change** (`temp_t+h − temp_t`, `power_t+h − power_t`) and the
level is reconstructed; this makes persistence the natural zero point. Metrics are
reported on the level.

## 5. Features (only information available at time t)

Raw, at t: `utilization_gpu_pct`, `utilization_memory_pct`, `memory_used_MiB`,
`power_draw_W`, `temperature_gpu`, `temperature_memory`; and, only for 14-column
series (≈5 % of labelled jobs, so used only in a clock ablation and on Reveal): `clocks_current_sm_MHz`, `clocks_current_memory_MHz`, `power_limit_W`.

Temporal (windows W ∈ {10, 30, 60} s, all trailing):
rolling mean/max/std of power; rolling mean of utilization; slope (least-squares) of
temperature, power, utilization, memory used, SM clock; lags at 1, 5, 10, 30 s; time
since job start; `power_draw_W / power_limit_W` where available.

Workload: one-hot of the dataset label (26 labels), and a coarse family feature
(vision CNN / U-Net / transformer NLP / GNN) derived by a fixed mapping from those
labels; the mapping will be published in the repo.

Leakage guard: a unit test asserts that every feature at row t depends only on rows
≤ t (shift-and-compare test), and that no window spans two series.

## 6. Splits (no shuffling)

1. Order all labelled jobs by their first timestamp.
2. Train = earliest 70 % of jobs, validation = next 15 %, test = last 15 %
   (*choice*). A job is entirely in one split.
3. Check label coverage per split; if a label is missing from test, report it rather
   than re-splitting randomly.
4. Additional generalisation tests (reported separately, never used for tuning):
   - Leave-one-family-out (train without e.g. all GNN jobs, test on them).
   - Cross-dataset: test the Supercloud-trained model on Oxford Reveal V100 runs that
     are ≥ 120 s long, using only the fields both datasets share.

## 7. Models

| ID | Model | Inputs | Purpose |
|---|---|---|---|
| B0 | Persistence (`ŷ_t+h = y_t`) | — | Baseline 1 |
| B1 | Gradient boosting on utilization features only | util raw + rolling + slope | Baseline 2 (brief §13) |
| A0 | LightGBM, full telemetry, **no** workload label | §5 minus workload | Model A |
| A1 | LightGBM, full telemetry **+** workload label | §5 | Tests H3 |
| L0/L1 | LSTM (1–2 layers), 60 s input sequence at 1 Hz, multi-horizon head, without/with label | raw + label embedding | Model B |
| opt | GRU or TCN | same as L1 | Only if L1 beats A1 on validation |

Hyper-parameters are tuned on validation only (small grid or Optuna with a fixed
trial budget). LSTMs are trained with 5 seeds; mean ± std is reported. Model selection
rule: lowest validation MAE at 30 s; ties within one standard deviation go to the
smaller/faster model.

## 8. Evaluation (test split, run once)

Per horizon (30/45/60 s) and per target (power, temperature):
MAE, RMSE, R², MAPE (power only; temperature MAPE is reported only on °C level, and
we note it is scale-dependent), inference latency (CPU, batch = 1, median and p95 over
1 000 calls, hardware recorded), model file size.

Per workload label when the test split holds ≥ 20 series for that label (*choice*).

Significance: paired bootstrap over test jobs (10 000 resamples) for the MAE difference
between each model and B0/B1; we report the 95 % interval.

## 9. Export

- LightGBM: native model text file (no pickle) plus ONNX via `onnxmltools` if the
  conversion reproduces predictions to 1e-5.
- LSTM: ONNX (`torch.onnx.export`), served with `onnxruntime` on CPU.
- A JSON manifest is exported with each model (see §10). The backend refuses to load
  a model without a manifest.

## 10. Reproducibility manifest (`models/exported/<model>/manifest.json`)

dataset name, URL, version (`datacenter-challenge/202201`), SHA-256 of every raw file
used, preprocessing config hash, feature list, split job-id lists, random seeds,
hyper-parameters, Python and library versions (`pip freeze`), Colab GPU/CPU type,
training start/end time, git commit of the training code, metric values copied from
the evaluation run (never typed by hand).

## 11. Compute plan

- Raw labelled GPU CSVs total 68.8 GB (sum of S3 object sizes listed for the 3 430
  labelled jobs). Too large for the laptop by design (brief §8).
- Colab streams each file over HTTPS, resamples to 1 s, writes Parquet to Google
  Drive, then discards the raw file. Expected Parquet size is not yet measured.
- If Colab disk/time limits are hit, process per label in batches and checkpoint.
