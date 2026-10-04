# Research Limitations

Status: PLANNING DRAFT (Phase 1–2). Nothing in this file is an experimental result.

This file lists what the project can and cannot claim. It is written before any
training so that the claims are fixed in advance and cannot drift to fit results.

## 1. Real telemetry versus simulated cooling telemetry

| Quantity | Origin | May be called |
|---|---|---|
| GPU utilization, power, temperature, memory util/used, SM clock, memory clock, power limit | Recorded by `nvidia-smi` on real NVIDIA V100 GPUs (MIT Supercloud; Oxford Reveal) | REAL MEASURED TELEMETRY |
| Forecasts of future power / temperature | Output of our ML models | MODEL PREDICTION |
| Coolant flow, coolant temperature, valve position, cooling demand, cold-plate temperature, twin GPU junction temperature | Our lumped thermal/hydraulic model (`docs/experiments.md` §4) | SIMULATED COOLING VARIABLE |
| Peak temp, overshoot, time-above-threshold, pump energy under reactive vs predictive control | Computed from our simulation | SIMULATED CONTROL RESPONSE |

The two layers are never stored in the same table. Every WebSocket field carries a
`source` tag (`measured` / `predicted` / `simulated`), see `docs/architecture.md` §6.

## 2. Dataset limitations (verified so far)

- **GPU model dependence.** Both shortlisted datasets are NVIDIA **V100** only
  (Supercloud: V100 32 GB, power limit 250 W seen in a sample row; Reveal: V100 32 GB).
  No A100/H100/B200 telemetry with all required fields was found publicly. Results
  will not transfer automatically to newer, higher-TDP GPUs.
- **Source cooling is unknown / not two-phase.** The measured `temperature_gpu`
  reflects whatever cooling the source cluster used. The documentation we read does
  not describe it as two-phase direct-to-chip. Therefore the ML temperature forecast
  is a forecast under the *source* system's cooling, not under our simulated loop.
- **Workload coverage.** Labels are deep-learning model names (Supercloud: 26 labels,
  e.g. `vgg16`, `resnet50`, `bert-base-uncased`, `U3-32`; Reveal: 14 model names × task).
  There are no labels such as "CUDA matmul", "idle", "memory-intensive". We will not
  create them.
- **Labels are per job, not per phase.** A label says which network a job trained; it
  does not mark data-loading, warm-up, checkpointing or idle phases inside the job.
- **Clocks are rare in the primary dataset.** Only ≈5 % of labelled Supercloud jobs
  (6 of 111 sampled) have SM/memory clock and power-limit columns. The main models are
  therefore clock-free; the value of clock features is tested on Reveal.
- **Narrow thermal excursions (Reveal).** In the one partial Reveal sample inspected (≈180 s of a
  BART-large training run) GPU 0 temperature stayed within 52–56 °C while power
  swung 39–246 W. If this is typical, temperature forecasting will be dominated by
  small changes and persistence will be a strong baseline. This must be measured in
  Phase 5 EDA, not assumed.
- **Reveal values appear resampled.** Reveal rows sit on an exact 100 ms grid and contain
  fractional values such as `54.333` °C and linearly stepping power, which suggests
  interpolation onto the grid. The effective native sampling rate is therefore unknown
  and must be estimated in EDA (count of genuine value changes).
- **Supercloud sampling is irregular.** Raw timestamps step ≈0.103–0.105 s (seen in a
  sample), not exactly 0.1 s. We resample explicitly (`docs/methodology.md` §3).
- **Many short Reveal runs.** Per its `meta_gpu.csv` (host htc-g003 only), median
  inference-run length is ≈8 s, so most inference runs are too short for a 60 s
  horizon; 277 of 680 listed runs are ≥120 s.
- **Licence constraint (Supercloud).** CC BY-NC-ND 4.0: non-commercial use, and no
  distribution of modified versions of the data. We keep cleaned data private in the
  training environment and publish only code, aggregate metrics and model weights.
  Whether trained weights count as a "derivative" is a legal grey area; see the
  decision list in `docs/dataset.md`.

## 3. Forecasting-horizon limitations

- 30/45/60 s horizons are long relative to V100 thermal time constants at the
  die level; much of the future power is driven by the job's next phase, which may not
  be predictable from the past window. Expect error to grow with horizon.
- Forecasts are evaluated only within a job (windows never cross job boundaries).
- No forecast is validated against a GPU cooled by a two-phase loop.

## 4. Simplified thermal model

- Lumped-capacitance (RC network) model with a first-order valve, a transport delay and
  a flow-dependent heat-transfer coefficient. It is **not CFD**, does not resolve
  boiling, vapour quality, dry-out, pressure drop across the cold plate, or
  flow distribution between parallel cold plates.
- Parameters are assumptions chosen to give plausible magnitudes and are listed
  explicitly; they are not fitted to a physical two-phase loop.

## 5. Simplified cooling-energy model

- Pump power follows the pump affinity law (P ∝ flow³) with an assumed constant.
  Output is labelled **ESTIMATED COOLING/PUMP ENERGY (relative)**. It is not measured
  pump energy and is meaningful only for comparing controllers on the same model.

## 6. Absent validations

- No physical hardware validation.
- No CFD.
- No direct measurement of two-phase boiling behaviour.
- No closed-loop test on a real GPU: the "closed loop" is real-telemetry-driven
  heat input → simulated cooling. Measured GPU temperature cannot respond to our
  simulated valve, because the recording is fixed.

## 7. Existing prototype in this folder

See `docs/existing_prototype_review.md`. The current backend model was trained on
random numbers and its metrics file contains hard-coded values. It must not be used
as research evidence.
