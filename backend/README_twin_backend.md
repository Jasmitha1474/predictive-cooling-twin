# Digital-twin backend (research version)

Run from `backend/`:

```bash
python3 -m pip install -r requirements.txt   # or use ../run_local.sh, which finds a Python that already has them
python -m app.replay --clean-dir ../research/work/clean --split-jobs ../research/work/reports/split_jobs.csv \
    --split test --n 40 --out data/replay_pack.parquet          # real test-split traces, kept private
PCOOL_MODEL=lgbm:../research/work/models/A1_lgbm_noclock_label uvicorn app.main:app --port 8000
```

Without `PCOOL_MODEL`, the backend still runs, but predictions come from **persistence**
and every frame says `model_status: "NOT_LOADED"` and `forecast_source: "persistence_baseline_not_ml"`.
A model without `manifest.json` next to it is refused (`REJECTED_NO_MANIFEST`).

The older prototype entry point (`main.py`, `simulation/data_center.py`, `ml/bootstrap_model.py`)
uses synthetic data and is not part of this path. See `docs/existing_prototype_review.md`.

## Modules

| Path | Layer | What it does |
|---|---|---|
| `simulation/twin.py` | SIMULATED | Two-node thermal model + valve, transport delay, flow-dependent two-phase conductance (docs/experiments.md §4) |
| `simulation/calibrate.py` | real data → parameter | Fits thermal time constant τ and resistance R from measured power→temperature; only C_total = τ/R is used |
| `controller/controllers.py` | control | `ReactiveThreshold`, `ReactivePI`, `Predictive` (MPC over 11 valve commands, 60 s rollout) |
| `controller/forecasters.py` | PREDICTED | persistence, oracle, exported LightGBM (`d_power_*.txt`), exported LSTM (`model.pt`) |
| `experiments/compare.py` | E2 | Runs every controller on the same real traces; writes `research/reports/e2_results*.json` |
| `app/replay.py` | MEASURED | Builds and loads the small replay pack (never the training set) |
| `app/engine.py` | all | Per second: measured row → forecast → controller → twin; builds frames |
| `app/main.py` | API | REST + `/ws/telemetry` |

## API

| Endpoint | Purpose |
|---|---|
| `WS /ws/telemetry` | First message `hello` (layout, model status, labels, twin parameters). Then one `frame` per simulated second. Client may send `{"type":"control", ...}` |
| `GET /api/status` | mode, controller, paused, speed, model status, threshold |
| `POST /api/control` | `{mode, controller_mode, paused, speed, reset}`. Changing controller restarts all traces, so both controllers replay the same workload |
| `GET /api/traces` | replay-pack index (series, job, dataset label, duration) |
| `POST /api/replay` | `{gpu_id, series_id}` assign a recorded trace to a virtual GPU |
| `GET /api/results` | research JSON files as written by the experiment code (null when missing) |

## Frame (`type: "frame"`) per GPU

- `measured`: `gpu_utilization`, `gpu_power`, `gpu_temperature`, `memory_utilization`, `memory_used_mib`,
  `memory_temperature`, `sm_clock_mhz`, `mem_clock_mhz` (null when absent in the trace). These come from the recorded row.
- `predicted`: `source`, `model_id`, `horizons_s` [30,45,60], `power`, `temperature_measured_system`
  (null if the model has no temperature head), `twin_temperature_if_valve_held` (twin rollout of the power forecast).
- `simulated`: `twin_temperature`, `cold_plate_temperature`, `coolant_temperature` (= assumed saturation temperature),
  `valve_position`, `valve_command`, `cooling_demand`, `coolant_flow_lpm`, `heat_removed_w`,
  `vapour_generation_g_s`, `dryout_proxy`, `est_pump_power_rel`.
- `events`: `thermal_event_predicted` / `thermal_event_cleared`. These come from the rollout crossing threshold − margin, not from a timer.

Not implemented: the optional "Simulation Workload" stress mode (brief §36). The two modes
`RESEARCH_DATA_REPLAY` and `DIGITAL_TWIN_SIMULATION` run the same engine and differ in what the
frontend emphasises (measured vs simulated temperature). The mode is stamped on every frame.
