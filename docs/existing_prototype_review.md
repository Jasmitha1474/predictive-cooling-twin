# Review of the Existing Prototype in `pred_cooling/`

Status: PLANNING DRAFT. Read-only review; no existing file was changed.

The folder already contains a working prototype (FastAPI backend, React Three Fiber
frontend, three Colab notebooks). It conflicts with the research-integrity rules in
the project brief in the following verifiable ways.

| # | Finding | Evidence | Conflicts with brief § |
|---|---|---|---|
| 1 | The shipped model is trained on random numbers | `backend/ml/bootstrap_model.py`: `X = np.random.rand(num_samples, 12) * 100`; targets built from `X` plus `np.random.normal` | 2, 51.1, 51.2 |
| 2 | Model metrics are hard-coded, not measured | `backend/ml/bootstrap_model.py` writes `{'mae': 1.2, 'rmse': 1.8, 'r2': 0.92}` literally; `backend/models/model_metadata.json` contains these values | 17, 51.5 |
| 3 | README says metrics are "computed from actual training/evaluation, not fabricated" | `README.md` (ML Methodology → Metrics) | 17 |
| 4 | Default dataset mode is synthetic | `README.md` "Mode A: Synthetic Simulation Data (Default)"; `training/01_dataset_generation.ipynb` | 2, 51.1 |
| 5 | Workload categories are invented | `backend/simulation/workload_profiles.py` (not tied to any dataset label) | 11, 36, 51.4 |
| 6 | Model features include simulated coolant variables mixed with telemetry | README feature table: `coolant_temperature`, `coolant_flow_rate`, `valve_position` alongside GPU telemetry | 7, 6 ("never mix") |

## Recommendation

- Keep the frontend scene components as a starting point for Phase 15 after review;
  they are presentation code and do not create research evidence.
- Retire `bootstrap_model.py`, `thermal_model.joblib`, `model_metadata.json`
  and `training/01_dataset_generation.ipynb` from the research path (move to
  `legacy/` and label "SYNTHETIC – NOT RESEARCH EVIDENCE"), rather than delete.
- Rewrite `README.md` once real results exist.

These are proposals; nothing is moved until you confirm (decision D6 in `docs/dataset.md`).
