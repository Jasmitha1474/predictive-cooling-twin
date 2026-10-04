# Dataset Audit (desk audit, pre-download)

Status: PHASE 2 DESK AUDIT. Checked 2026-10-03 from documentation, S3/Hugging Face
file listings, CSV headers and small byte-range samples only. Items marked
**[Colab]** need the full files and will be filled by `01_dataset_analysis.ipynb`;
they are deliberately left blank rather than estimated.

## A. MIT Supercloud Dataset — labelled subset (PRIMARY)

| Item | Value | How verified |
|---|---|---|
| Dataset name | MIT Supercloud Dataset, `datacenter-challenge/202201` | S3 prefix listing |
| URL | https://mit-supercloud-dataset.s3.amazonaws.com/datacenter-challenge/202201/ | anonymous listing worked |
| Authors / organisation | S. Samsi et al., MIT Lincoln Laboratory Supercomputing Center / USAF-MIT AI Accelerator | repo README citation |
| Publication | IEEE HPEC 2021, doi:10.1109/HPEC49654.2021.9622850 | repo README |
| Licence | CC BY-NC-ND 4.0 | `LICENSE` file in the bucket (285 bytes) |
| GPU model | NVIDIA V100 32 GB (TX-GAIA nodes, 2 GPUs per node) | paper/README; `memory_free_MiB = 32510` in sample rows is consistent |
| Number of GPUs | 2 per job file in all 12 sampled jobs (`gpu_index` 0,1); total distinct physical GPUs **[Colab]** (node id is in file name `-n<id>`) | sample rows |
| Sampling interval | median 0.105–0.108 s between consecutive rows of the same GPU (12 sampled labelled files) | timestamps in samples |
| Number of records | **[Colab]** (exact). Not estimated here | — |
| Number of jobs / files | 3 430 labelled jobs; 10 201 GPU CSV objects; 2 395 jobs have 1 file, 926 have 2, 49 have 4, 12 have 32, 10 have 128 | S3 listing joined with `labelled_jobids.csv` |
| Raw size | 68.8 GB for labelled jobs (whole `gpu/` folder: 109 946 files, 2 437 GB) | sum of S3 object sizes |
| Time duration | 17–288 min per job in 12 randomly sampled labelled jobs (last minus first timestamp); full distribution **[Colab]** | byte-range head/tail reads |
| Calendar span | sample timestamps fall in Sept 2021; full span **[Colab]** | sample rows |
| Workload types | 26 labels: `U3-32/64/128`, `U4-32/64/128`, `U5-32/64/128`, `bert-base-uncased`, `distilbert-base-uncased`, `vgg11/16/19`, `inception3/4`, `resnet50`, `resnet50_v1.5`, `resnet101(_v2)`, `resnet152(_v2)`, `conv`, `dimenet`, `schnet`, `pna` | `labelled_jobids.csv` (3 430 rows) |
| Label counts | inception4 243, inception3 241, vgg19 199, bert-base-uncased 189, vgg11 185, vgg16 176, distilbert 172, U3-32 165, U3-128 165, U4-32 163, U3-64 159, U4-64 158, U5-32 158, U5-64 158, U4-128 157, U5-128 148, resnet50 111, resnet50_v1.5 91, resnet101 77, resnet152 76, resnet101_v2 54, resnet152_v2 54, schnet 39, dimenet 33, conv 32, pna 27 | counted from `labelled_jobids.csv` |
| Telemetry columns | 10-column schema: `timestamp, gpu_index, utilization_gpu_pct, utilization_memory_pct, memory_free_MiB, memory_used_MiB, temperature_gpu, temperature_memory, power_draw_W, pcie_link_width_current`. 14-column schema adds `clocks_current_sm_MHz, clocks_current_memory_MHz, clocks_current_video_MHz, power_limit_W` | headers read from S3 |
| Schema coverage | Clock/power-limit columns are rare in the labelled subset: 6 of 111 randomly sampled labelled jobs (≈5 %) and 20 of 517 labelled file headers read in listing order had the 14-column schema. Exact count **[Colab]** (header-only scan was stopped by a time limit on this machine) | header of every labelled file read (first 400 bytes) |
| Missing-value % | 0 % empty/`N/A` cells in 49 110 rows read (first 200 KB of 12 randomly chosen labelled files). Full-dataset value **[Colab]** | byte-range sample |
| Duplicate records | 0 duplicate `(timestamp, gpu_index)` pairs in the same 49 110 sample rows. Full-dataset value **[Colab]** | byte-range sample |
| Timestamp quality | Irregular spacing (not an exact 100 ms grid); GPUs 0 and 1 interleaved in one file; gaps **[Colab]** | samples |
| Value ranges in sample | `temperature_gpu` 25–74 °C, `power_draw_W` up to 279.67 W, utilization within 0–100 (same 49 110 rows) | byte-range sample |
| Workload-label availability | Per job, not per phase | file format |
| Limitations | V100 only; source cooling not documented as two-phase; clocks only in some files; NC-ND licence; label = network architecture, not workload phase | see `docs/limitations.md` |

### Requirement table

| Requirement | Available? | Dataset field |
|---|---|---|
| GPU utilization | YES | `utilization_gpu_pct` |
| GPU power | YES | `power_draw_W` |
| GPU temperature | YES | `temperature_gpu` |
| Memory utilization | YES | `utilization_memory_pct` |
| GPU clock | PARTIAL (≈5 % of labelled jobs) | `clocks_current_sm_MHz` |
| Memory clock | PARTIAL (≈5 % of labelled jobs) | `clocks_current_memory_MHz` |
| Workload label | YES | `labelled_jobids.csv: model` |
| Timestamp | YES | `timestamp` |

### Copied sample rows (unmodified data from the dataset)

```text
# gpu/0000/10047800340911-r4858666-n830961.csv (not a labelled job; shows 14-column schema)
timestamp,gpu_index,utilization_gpu_pct,utilization_memory_pct,memory_free_MiB,memory_used_MiB,temperature_gpu,temperature_memory,power_draw_W,pcie_link_width_current,clocks_current_sm_MHz,clocks_current_memory_MHz,clocks_current_video_MHz,power_limit_W
1632719875.772,0,6,0,32510,0,38,39,44.54,16,1380,877,1237,250.0
1632719875.875,0,0,0,32510,0,38,38,44.54,16,1380,877,1237,250.0
1632719875.978,0,0,0,32510,0,38,38,44.54,16,1380,877,1237,250.0
```

```text
# a labelled job file (10-column schema)
timestamp,gpu_index,utilization_gpu_pct,utilization_memory_pct,memory_free_MiB,memory_used_MiB,temperature_gpu,temperature_memory,power_draw_W,pcie_link_width_current
1631786120.45,0,0,0,32510,0,32,30,26.7,16
1631786120.454,1,0,0,32510,0,33,29,26.32,16
```

## B. Oxford "Reveal" — V100 part (SECONDARY)

| Item | Value | How verified |
|---|---|---|
| URL | https://huggingface.co/datasets/subsetchen/RevealTelemetryDatasetforMLInfraProfilingAnomalyDetection (DOI 10.5281/zenodo.17470313) | dataset card |
| Authors | Z. Chen, S. W. D. Chien, P. Qian, N. Zilberman (Univ. of Oxford) | dataset card |
| Publication | arXiv:2510.26008 (2025) | dataset card |
| Licence | CC BY 4.0 | dataset card |
| GPU model / count | 2 nodes (`htc-g003`, `htc-g004`) × 2 V100 32 GB | dataset card; column names `…0.htc-g004`, `…1.htc-g004` |
| Sampling interval | rows on an exact 100 ms grid (`06:29:03.000, .100, …`) | sample |
| Files / size | `Reveal_GPU.zip` 4.50 GB compressed; 1 480 run files (740 per host; 740 train, 740 infer), 25.0 GB uncompressed | zip central directory read by byte range |
| Records | 2 329 184 rows across the 680 runs listed in `meta_gpu.csv` (host htc-g003 only); host htc-g004 **[Colab]** | `meta_gpu.csv` |
| Duration | htc-g003: train median 399 s, inference median 8 s, fine-tuning median 1 848 s; 277 of 680 runs ≥ 120 s | `meta_gpu.csv` (`n_rows` × 0.1 s) |
| Workloads | 14 models (`Resnet18/50`, `VGG16/19`, `ViTB16/L16`, `BARTBASE/LARGE`, `BERTBASE/LARGE`, `DISTILBERT`, `DEEPSEEK`, `LLAMA`, `MISTRAL`) × tasks/datasets → 34 `workload` ids; phases `train`, `infer`, `fine-tuning` | `meta_gpu.csv` |
| GPU columns (per GPU n) | `GPU: utilization.gpu.<n>`, `utilization.memory.<n>`, `memory.used.<n>`, `memory.free.<n>`, `temperature.gpu.<n>`, `temperature.memory.<n>`, `power.draw.<n>`, `power.draw.instant.<n>`, `clocks.current.sm.<n>`, `clocks.current.memory.<n>`, `clocks.current.graphics.<n>` (+ ECC, PCIe, encoder); `power.draw.average` and `fan.speed` empty in sample | header of two run files |
| Timestamp | first column, header `Unnamed: 0`, e.g. `2025-04-26 06:29:03.000` | sample |
| Observations from one partial 180 s sample (BART-large training, GPU 0) | power 39.3–245.6 W, temperature 52–56 °C, SM clock 1230–1380 MHz, memory clock constant 877 MHz, no missing values in these 8 fields; fractional temperatures (e.g. 54.33) suggest interpolation | partial decompression of one file |
| Note | The card says workloads were "synthetic workloads" run by the authors in a controlled environment: the ML jobs are real runs on real GPUs, but they are benchmark runs, not production traffic | dataset card |

## C. Rejected candidates (reason recorded)

| Dataset | Reason |
|---|---|
| M100 ExaData (CINECA) | GPU metrics via ganglia at ~20 s with "high variability"; no application label. Useful only as context for real cooling-plant signals (RDHx pumps/valves/flow at 20 s, `schneider` plugin) |
| Summit power & thermal (OLCF) | Released only as 10 s / 1 min means; no utilization, clocks or job labels |
| Alibaba PAI / Philly / Helios / Azure LLM traces | Scheduler or request traces; no per-GPU power and temperature time series |
