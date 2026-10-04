# E2 preliminary: reactive vs predictive control (no ML model yet)

Source: `e2_results_preliminary.json`, written by `backend/experiments/compare.py`. The numbers below are copied from that file.

**Scope.** These are SIMULATED control responses. The twin is driven by REAL measured power from 17 V100 series
(13 small labelled MIT Supercloud jobs, 45,451 s in total). These are the same jobs as the code smoke test, all
splits, so this is not the final test-split experiment. Thermal inertia was fitted on the same traces
(τ = 25 s, R = 0.150 K/W, fit RMSE 3.9 °C → C_total = 166 J/K). Cooling-side parameters are ASSUMED.
The threshold is 59.1 °C, the twin's steady state at 250 W with the valve 50 % open.
"Predictive" here uses a **persistence** or **oracle** power forecast. The ML forecast is pending the Colab run.

| Controller | Time above threshold (total, s) | Peak T_j median (°C) | Est. pump energy vs reactive | Valve reversals (median per trace) |
|---|---|---|---|---|
| Reactive threshold | 1,281 | 57.75 | 1.00 | 0 |
| Reactive PI | 1 | 57.45 | 0.39 | 455 |
| Predictive (persistence forecast) | 0 | 56.51 | 0.54 | 617 |
| Predictive (oracle forecast, upper bound) | 0 | 56.81 | 0.61 | 381 |

Sensitivity (time above threshold, total s), one assumed parameter changed at a time:

| Change | Reactive | PI | Pred. persistence | Pred. oracle |
|---|---|---|---|---|
| transport delay 2 s | 878 | 0 | 0 | 0 |
| transport delay 10 s | 1,894 | 26 | 0 | 1 |
| transport delay 20 s | 2,781 | 704 | 0 | 0 |
| threshold −5 °C | 1,807 | 214 | 1 | 6 |

**What this does and does not show.**
- Most traces never reach the threshold (median overshoot 0 for every controller). The differences come from a few
  high-power traces.
- With these assumed parameters, a PI controller already removes almost all threshold time. Model-based (predictive)
  control only clearly beats PI when the cooling delay is long (20 s).
- The oracle forecast does not beat persistence here, so this setup cannot yet show any value from forecasting.
  That question waits on the ML forecaster and the test-split traces.
- The PI and predictive controllers move the valve back and forth hundreds of times per trace (chatter). This is a
  weakness to fix with a deadband or rate penalty before claiming them as practical.
- The energy ratios depend strongly on how the reactive baseline is tuned (it closes slowly: 0.02 per second).
