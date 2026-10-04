# End-to-end integration demo

All numbers are copied from files written by `backend/experiments/compare.py`. The ML step uses a **DEV model**: LightGBM trained on 13 small jobs as a code check (`backend/data/models_dev/`). It is not the research model, which is pending the Colab run.

Pipeline exercised: recorded V100 power trace (MEASURED) → ML power forecast at +30/45/60 s (PREDICTED) → twin rollout → predictive controller → valve command → valve/flow/two-phase cold plate (SIMULATED) → twin temperature → next step. The same loop drives the live 3D twin over `/ws/telemetry`.

## A. Jobs the DEV model did not train on (7 series, 4 jobs: val + test of the check split)

Threshold 59.1 °C. Total 14355 s of real power.

| controller | time above threshold (s, total) | peak T_j median (°C) | est. pump energy vs reactive | valve reversals (median) |
|---|---|---|---|---|
| reactive_threshold | 0 | 49.53 | 1.00 | 0 |
| reactive_pi | 0 | 49.53 | 1.00 | 0 |
| predictive_persistence | 0 | 49.53 | 1.05 | 0 |
| predictive_oracle | 0 | 49.53 | 1.08 | 0 |
| predictive_ml_DEV_smoke13jobs_A1_lgbm | 0 | 49.53 | 1.04 | 0 |

**Reading:** none of these 7 workloads pushes the twin past the threshold under any controller. Peak measured power in these traces is 195.9 W, against the 250 W reference used to set the threshold, so there is nothing for prediction to prevent. Predictive control raises estimated pump energy by 4–8 % here without a thermal benefit. This is a real, if unexciting, result of this small sample.

## B. One high-load workload, all five controllers (illustration)

Trace `1059916241808-r9352821-n851693:0:0` (label U3-128). **Caveat: the DEV ML model was trained on this job**, so the ML row is not a fair evaluation. Figure: `research/figures/e2e_demo_highload_U3-128.png`.

| controller | time above threshold (s) | peak T_j (°C) | overshoot (°C) | est. pump energy (rel. units) | valve reversals | power-rise events / with response | response time median (s) |
|---|---|---|---|---|---|---|---|
| reactive_threshold | 429 | 60.21 | 1.11 | 220304 | 109 | 10 / 10 | 41.5 |
| reactive_pi | 0 | 58.89 | 0.00 | 48434 | 2913 | 10 / 9 | 32.0 |
| predictive_persistence | 0 | 56.98 | 0.00 | 71542 | 2681 | 10 / 10 | 28.5 |
| predictive_oracle | 0 | 58.03 | 0.00 | 83006 | 619 | 10 / 0 | — |
| predictive_ml_DEV_smoke13jobs_A1_lgbm | 0 | 57.10 | 0.00 | 71263 | 2335 | 10 / 4 | 24.0 |

**Reading:** the threshold controller cycles above and below the threshold (429 s above, 1.11 °C overshoot). Every other controller keeps the twin below it. The oracle opens the valve before the power step arrives, which shows what a perfect forecast buys. PI and the predictive controllers chatter, with thousands of small valve reversals. This needs a deadband or rate penalty before it could be called practical.

## C. Live 3D twin

Screenshots `docs/screenshots/04_live_predictive_ml_dev_event.jpg` and `05_live_reactive_same_workload.jpg`: the same replay restarted under each controller. The overlay shows `MODEL: ACTIVE (ml_DEV_smoke13jobs_A1_lgbm)`, and every value is tagged MEASURED / PREDICTED / SIMULATED.

## What waits on the Colab run

- The research model (trained on 3,430 jobs) and its forecasting metrics.
- The final E2 on real test-split traces with that model: `e2_results.json` replaces these demo files on the results page.