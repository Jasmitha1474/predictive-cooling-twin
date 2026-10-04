# Predictive Thermal Control for Two-Phase Direct-to-Chip GPU Cooling

Short-horizon (30–60 s) forecasting of GPU power and temperature from **real NVIDIA V100 telemetry**,
used to drive a predictive cooling controller in a **simulated** two-phase direct-to-chip cooling loop,
shown in an immersive 3D data-center digital twin.

**Live demo:** https://predictive-cooling-twin.vercel.app
**Paper (subset run):** [`docs/paper/Predictive_Cooling_IEEE_Paper_subset.pdf`](docs/paper/Predictive_Cooling_IEEE_Paper_subset.pdf)

## What is real, predicted and simulated

| Layer | Source |
|---|---|
| **Measured** | GPU utilization, power, temperature, memory, clocks: `nvidia-smi` telemetry from the MIT Supercloud dataset [1] |
| **Predicted** | Forecasts from the trained models (persistence, LightGBM, LSTM) |
| **Simulated** | Coolant flow, valve, cold-plate and twin GPU temperature, pump energy: a simplified lumped thermal model (not CFD) |

## Current results (subset run)

The results in `research/reports/` come from a **real but reduced run**: 104 randomly sampled labelled jobs
(4 per workload label) out of 3,430, a chronological job split of 73/16/15, and 2 LSTM seeds instead of 5. Every
results file carries `run_type: SUBSET_104_JOBS`. The full-dataset run will replace these files.

- **Power forecasting:** the LSTM had the lowest test MAE (11.37 W at +30 s vs 12.79 W for persistence). The
  improvement is not statistically significant on 15 test jobs.
- **Temperature forecasting:** no model was significantly better than persistence.
- **Workload labels:** adding them did not help.
- **Cooling (simulated, same real power traces):** threshold control spent 993 s above the limit, PI control 15 s
  and predictive control 0 s. A persistence-forecast predictive controller also reached 0 s, so the gain here comes
  from model-based control rather than from the learned forecast.

## Repository layout

| Path | Contents |
|---|---|
| `research/src/pcool/` | Data pipeline: download → clean → chronological split → features → models → evaluation |
| `research/notebooks/` | Google Colab notebooks for the full run |
| `research/reports/`, `research/figures/` | Results and figures (subset run) |
| `backend/` | FastAPI + WebSocket server: replay, forecasting, controllers, thermal twin, experiments |
| `frontend/` | React + Three.js / React Three Fiber 3D data hall |
| `docs/` | Methodology, dataset audit, limitations, architecture, user guide, paper |
| `legacy/`, `training/` | Earlier synthetic-data prototype, kept for reference only; not used for any result |

## Data

The dataset is **not included** in this repository. The pipeline downloads the public files directly from the
MIT Supercloud bucket (`datacenter-challenge/202201`); see `research/README.md`. The dataset is licensed under
CC BY-NC-ND 4.0, so derived data (cleaned series, features, per-second traces) is kept out of the repository.
`research/reports/subset_run/subset_job_list.parquet` lists the job IDs used in the subset run.

## Run locally

```bash
./run_local.sh          # starts the backend (port 8000) and the frontend (port 5173)
```

See `backend/README_twin_backend.md`, `frontend/README_frontend.md` and `docs/user_guide/`.

## Limitations

V100 GPUs only, source cluster cooling (not two-phase), simplified cooling model, no hardware validation, subset
results. See `docs/limitations.md`.

## References

[1] S. Samsi et al., "The MIT Supercloud Dataset," IEEE HPEC 2021, doi:10.1109/HPEC49654.2021.9622850.
