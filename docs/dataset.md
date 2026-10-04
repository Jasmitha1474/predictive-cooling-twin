# Dataset Selection Report

Status: PLANNING DRAFT (Phase 1 discovery and Phase 2 desk audit). Checked on
2026-10-03. Only documentation, file listings, headers and a few kilobytes of sample
rows were read; nothing was downloaded in bulk and nothing was trained.

Full per-field audit: `research/dataset_audit/dataset_audit.md`.

## 1. Recommendation

**Primary research dataset: MIT Supercloud Dataset, labelled deep-learning subset
(`datacenter-challenge/202201`).**
**Secondary (external validation only): Oxford "Reveal" V100 telemetry.**

Reasons, against the brief's §5 criteria:

| Criterion | MIT Supercloud (labelled) | Why it matters here |
|---|---|---|
| Telemetry completeness | All 8 required fields exist as real `nvidia-smi` columns, but SM/memory clocks and power limit appear only in the 14-column files, which are ≈5 % of labelled jobs (6 of 111 sampled) | Required by §2 and §4 |
| Sampling frequency | Raw ≈ 0.105–0.108 s per GPU (medians from 12 sampled labelled files) | 30/45/60 s horizons map to exact 1 s-grid steps |
| Workload information | 3 430 jobs with a per-job model label, 26 distinct labels | Needed for §11 workload-aware study |
| Size | 3 430 labelled jobs, 10 201 GPU CSV objects, 68.8 GB raw | Enough series for a chronological job-level split |
| Job length | 17–288 min in 12 randomly sampled labelled jobs | Long enough for 60 s horizons, unlike most Reveal inference runs |
| Provenance | Real NVIDIA V100 (TX-GAIA), peer-reviewed (IEEE HPEC 2021), MIT Lincoln Lab | §3 items 1, 9 |
| Reproducibility | Public S3 bucket, anonymous HTTPS, fixed version folder `202201` | §3 item 11, §44 |
| Licence | CC BY-NC-ND 4.0 (from the bucket's LICENSE file) | Permits non-commercial research use; restricts sharing modified data |

Reveal is the only other candidate with every required field at 100 ms and richer,
more recent workloads (LLaMA, Mistral, DeepSeek, ViT). It ranks second because its
runs are short (median inference run ≈ 8 s), its values appear interpolated onto the
grid, and it covers one 2-node system over a few days. It has the more permissive
licence (CC BY 4.0), which makes it the fallback if you decide the Supercloud licence
is unacceptable (decision D2).

## 2. Candidates examined

| Dataset | GPU | Interval | Util | Power | Temp | Mem util | SM clk | Mem clk | Labels | Licence | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **MIT Supercloud** (Samsi et al., HPEC 2021) | V100 32 GB | ~0.1 s raw | ✓ | ✓ | ✓ (+mem temp) | ✓ | partial | partial | ✓ 26 model labels | CC BY-NC-ND 4.0 | **Primary** |
| **Reveal** (Chen et al., Oxford, arXiv 2510.26008) | V100 32 GB, 2 nodes × 2 | 100 ms grid (resampled?) | ✓ | ✓ | ✓ (+mem temp) | ✓ | ✓ | ✓ | ✓ 34 workload IDs | CC BY 4.0 | Secondary |
| **M100 ExaData** (Borghesi et al., Sci Data 2023) | V100 (Marconi100) | ~20 s (ganglia, "high variability") | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ (job table has no application label) | CC BY 4.0 | Too coarse: 60 s = 3 samples |
| **Summit power & thermal** (Shin et al., SC21; OLCF DOI 10.13139/OLCF/1861393) | V100 | 10 s / 1 min means (1 Hz raw not released) | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ | CC BY 4.0 | Missing util, clocks, labels |
| Alibaba PAI, Microsoft Philly, Helios, Azure LLM traces | various | job / minute level | partial | ✗ | ✗ | — | ✗ | ✗ | partial | various | No power/temperature time series |

Searched but no usable public release found: A100/H100/B200 DCGM time series with
power, temperature, clocks and workload labels together. Several 2024–2026 papers
measure such traces (e.g. Microsoft's ASPLOS'24 GPU power study) but we did not find
the underlying telemetry published with all required fields.

## 3. Required-field mapping (primary dataset)

| Requirement | Available? | Dataset field |
|---|---|---|
| GPU utilization | YES | `utilization_gpu_pct` |
| GPU power | YES | `power_draw_W` |
| GPU temperature | YES | `temperature_gpu` |
| Memory temperature | YES | `temperature_memory` |
| Memory utilization | YES | `utilization_memory_pct` |
| Memory usage | YES | `memory_used_MiB` (and `memory_free_MiB`) |
| GPU / SM clock | PARTIAL (≈5 % of labelled jobs) | `clocks_current_sm_MHz` |
| Memory clock | PARTIAL (≈5 % of labelled jobs) | `clocks_current_memory_MHz` |
| Power limit | PARTIAL (≈5 % of labelled jobs) | `power_limit_W` |
| Energy counter (`DCGM_FI_DEV_TOTAL_ENERGY_CONSUMPTION`) | NO | derivable as ∫ `power_draw_W` dt (option B), labelled "derived" |
| Workload label | YES (per job) | `labelled_jobids.csv` → `model` |
| Timestamp | YES | `timestamp` (Unix seconds, float) |
| GPU model | YES (documented) | V100 32 GB per README/paper; `gpu_index` per node |

DCGM field names (`DCGM_FI_DEV_*`) do **not** appear in this dataset; the telemetry
is from `nvidia-smi`. We use the dataset's own names everywhere.

## 4. Handling missing variables (brief §6)

| Variable | A: other name? | B: derivable? | C: other real dataset? | D: redesign? | Outcome |
|---|---|---|---|---|---|
| SM / memory clock (missing in ≈95 % of labelled jobs) | No | No | Reveal has them in every run | Yes: main models are clock-free; clock value tested on Reveal and on the small Supercloud clock subset | Clock features never imputed |
| Energy | No | Yes, integrate power | — | — | Derived, labelled |
| Coolant flow, valve, coolant temp | No | No | M100 has RDHx (rear-door, not direct-to-chip) pump/valve/flow logs at 20 s | Yes: these belong to Layer B | Simulated, labelled SIMULATED |
| Two-phase boiling quantities | No | No | None found | Yes | Simulated (vapour rate = Q/h_fg), labelled |
| Fine workload phases (idle, data-loading) | No | Partly: idle from `utilization_gpu_pct == 0` | — | — | "Derived activity phase", never shown as a dataset label |

## 5. Access and split

- Access: `https://mit-supercloud-dataset.s3.amazonaws.com/datacenter-challenge/202201/`
  (anonymous). Files: `labelled_jobids.csv` (job id → model), `gpu/NNNN/<jobid>-r…-n….csv`.
- Downloaded only inside Colab; SHA-256 of each file recorded in the manifest.
- Split: chronological by job start, 70/15/15 at job level (`docs/methodology.md` §6).

## 6. Citations

- S. Samsi et al., "The MIT Supercloud Dataset," IEEE HPEC 2021,
  doi:10.1109/HPEC49654.2021.9622850. Repo: https://github.com/MIT-AI-Accelerator/MIT-Supercloud-Dataset
- Z. Chen, S. W. D. Chien, P. Qian, N. Zilberman, "Detecting Anomalies in Machine
  Learning Infrastructure via Hardware Telemetry," arXiv:2510.26008, 2025. Data:
  https://huggingface.co/datasets/subsetchen/RevealTelemetryDatasetforMLInfraProfilingAnomalyDetection,
  doi:10.5281/zenodo.17470313
- A. Borghesi et al., "M100 ExaData," Scientific Data 2023. Data: https://zenodo.org/records/7588815,
  code: https://gitlab.com/ecs-lab/exadata
- W. Shin et al., "Revealing power, energy and thermal dynamics of a 200PF pre-exascale
  supercomputer," SC21. Data: doi:10.13139/OLCF/1861393, https://github.com/at-aaims/summit_power_and_thermal_data

## 7. Decisions needing your confirmation

- **D1** Primary dataset = MIT Supercloud labelled subset; Reveal = external validation only.
- **D2** Accept CC BY-NC-ND 4.0: processed data stays private; we publish code,
  aggregate metrics and model weights (weights-as-derivative is a grey area; the safe
  alternative is to switch primary to Reveal, CC BY 4.0).
- **D3** Resample to a 1 s grid (30/45/60 s = 30/45/60 steps); 100 ms kept as an ablation.
- **D4** Predictive controller acts on the ML **power** forecast run through the twin
  model; the ML temperature forecast is evaluated on real data and displayed, but not
  used to drive the simulated loop (`docs/experiments.md` §2).
- **D5** Add a PI reactive baseline and an oracle controller alongside the simple
  threshold controller.
- **D6** Move the existing synthetic model, metadata and dataset-generation notebook to
  `legacy/` (see `docs/existing_prototype_review.md`).
