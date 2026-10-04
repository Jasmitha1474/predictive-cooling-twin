# Experimental Methodology

Status: PLANNING DRAFT. Defines experiments before they are run. No results here.

Two experiment families, kept separate:

- **E1 Forecasting (Layer A, real data)** — defined in `docs/methodology.md`.
- **E2 Control comparison (Layer B, simulation driven by real power traces)** — below.

## 1. What is real and what is simulated in E2

| Signal | Source |
|---|---|
| Heat input `P(t)` to the twin | **Measured** `power_draw_W` from a test-split job (replayed) |
| Forecast `P̂(t+h)` | **ML prediction** from the selected model, using only data ≤ t |
| Twin junction temperature `T_j`, cold-plate temperature `T_cp`, valve `v`, flow `Q`, vapour rate, pump power | **Simulated** by the model in §4 |
| Measured `temperature_gpu` | Shown for reference only; it cannot respond to our valve |

## 2. Why the controller uses the power forecast

The measured GPU temperature in the dataset was produced by the source cluster's own
cooling, not by our two-phase loop. Feeding that temperature forecast into our
controller would mix two different thermal systems. The forecast that transfers is
**power** (heat input). The predictive controller therefore takes `P̂(t+30/45/60)`
and rolls the twin model forward to predict *twin* temperature. The ML temperature
forecast is still produced and evaluated in E1 and displayed in the UI as a
"measured-system forecast". (Decision D4 in `docs/dataset.md`.)

## 3. Horizons

Controller period Δt_c = 1 s (*choice*), matching the 1 s data grid. Forecast steps:
30 s → 30, 45 s → 45, 60 s → 60. The simulation integrates at Δt_s = 0.1 s (*choice*).

## 4. Thermal / hydraulic twin model (simplified, not CFD)

States: `T_j` (GPU junction, °C), `T_cp` (cold plate, °C), `v` (valve opening, 0–1).

Two-phase representation: the dielectric coolant enters the cold plate as saturated
liquid at `T_sat`, set by loop pressure. Heat removed at the cold plate goes into
evaporation, so coolant temperature stays near `T_sat` (isothermal assumption).

Equations:

```
Valve actuator (first order, rate-limited):
    dv/dt = clip( (v_cmd − v) / τ_v , −r_max , +r_max )

Flow with transport delay τ_d:
    Q(t) = Q_min + (Q_max − Q_min) · v(t − τ_d)            [L/min]

Flow-dependent effective conductance (diminishing returns):
    G(Q) = G_0 + G_1 · (Q / Q_max)^n ,  0 < n < 1          [W/K]

Junction:
    C_j  · dT_j/dt  = P(t) − (T_j − T_cp) / R_jc

Cold plate:
    C_cp · dT_cp/dt = (T_j − T_cp) / R_jc − G(Q) · (T_cp − T_sat)

Heat removed and derived vapour generation (reported, simulated):
    Q_rem(t) = G(Q) · (T_cp − T_sat)                       [W]
    ṁ_vap(t) = Q_rem(t) / h_fg                             [kg/s]

Dry-out proxy (optional, flagged): if ṁ_vap exceeds x_max · ṁ_liq(Q), G is reduced
by factor k_dry to mimic loss of two-phase heat transfer.

Integration: explicit Euler at Δt_s = 0.1 s; a check asserts
Δt_s < 0.2 · min(R_jc·C_j, C_cp / G_max) for stability.
```

Parameters (all **ASSUMED**, listed in `backend/simulation/params.yaml` and in the
results page): `C_j, C_cp, R_jc, G_0, G_1, n, T_sat, h_fg, Q_min, Q_max, τ_v, τ_d,
r_max, x_max, k_dry`.

Calibration (uses real data legitimately, option B of brief §6): `C_j` and an
effective resistance are fitted so that, with cooling held constant, the twin's
response of `T_j` to the measured power trace matches the *shape* (time constant) of
the measured `temperature_gpu` response on training jobs. Cooling-side parameters
(`G_*`, `T_sat`, `h_fg`, `τ_v`, `τ_d`, flow range) cannot be derived from the data and
remain assumptions; a sensitivity sweep (§8) shows how conclusions depend on them.

## 5. Controllers

**Reactive (baseline, brief §21)**

```
if T_j ≥ T_th:            v_cmd ← min(1, v_cmd + Δv_up)
elif T_j ≤ T_th − δ:      v_cmd ← max(v_min, v_cmd − Δv_down)
else:                     v_cmd unchanged
```

**Reactive-PI (stronger baseline, optional, decision D5)** — PI control on current
`T_j` with the same actuator limits. Included so a predictive advantage is not just
an artefact of a weak baseline.

**Predictive (brief §20, §22)** — every Δt_c:

1. Get `P̂(t+k)` for k = 1…60 s by interpolating the 30/45/60 s forecasts with the
   current power at k = 0.
2. For each candidate `v_cmd ∈ {0, 0.1, …, 1}`, roll the twin model forward 60 s.
3. Choose the smallest `v_cmd` for which predicted `max T_j ≤ T_th − margin`; if none,
   choose 1.
4. Apply the same actuator limits as the reactive controller.

**Oracle (upper bound)** — identical to Predictive but with the true future power.
The gap between Predictive and Oracle isolates the cost of forecast error.

Cooling demand reported to the UI = `v_cmd` × 100 %.

## 6. Comparison protocol

- Traces: all test-split series whose length ≥ 300 s (*choice*). The same trace list is
  used for every controller.
- Same initial state, same parameters, same random seed (the simulation is
  deterministic).
- Thresholds: `T_th` chosen relative to the twin's steady state at the power limit
  (e.g. the temperature reached at `P = power_limit_W` with `v = 0.5`), fixed before
  running and reported.

## 7. Metrics (computed from simulation output)

| Metric | Definition |
|---|---|
| Peak temperature | `max T_j` |
| Overshoot | `max(0, max T_j − T_th)` |
| Time above threshold | seconds with `T_j > T_th` |
| Cooling response time | time from a power-rise event (power increase ≥ 30 % of power limit within 10 s, *choice*) to `v` reaching 90 % of its post-event maximum |
| Average cooling demand | mean `v_cmd` |
| Estimated pump energy | `E = Σ k_p · Q(t)^3 · Δt_s` (affinity law, `k_p` ASSUMED), reported relative to the reactive controller |
| Temperature stability | std of `T_j`; number of valve-direction reversals |

Statistics: per-trace paired differences (Predictive − Reactive); Wilcoxon signed-rank
test; report median and IQR. No improvement is claimed if the interval includes zero.

## 8. Sensitivity analysis

Sweep `τ_d ∈ {2, 5, 10, 20} s`, `τ_v ∈ {2, 5, 10} s`, `T_th` ± 5 °C, and forecast
horizon used by the controller (30/45/60 s). Expectation to test, not assume:
prediction should matter more when cooling delays are long.

## 9. Outputs

All metrics are written by the experiment script to `research/reports/e2_results.json`
with a manifest (trace ids, parameters, model id, git commit). The results page reads
only this file.
