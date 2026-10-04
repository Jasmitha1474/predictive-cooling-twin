"""Summarise a finished run (results.json, audit, split, E2) into report tables + figures.

Usage: python make_subset_report.py <work_dir> <e2_json or ''> <out_dir>
Every number is copied from the experiment files; nothing is typed by hand.
"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

work, e2_path, out = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
out.mkdir(parents=True, exist_ok=True)
R = json.loads((work / "reports" / "results.json").read_text())
A = json.loads((work / "reports" / "audit_summary.json").read_text())
S = json.loads((work / "reports" / "split_report.json").read_text())
E2 = json.loads(Path(e2_path).read_text()) if e2_path else None

ORDER = ["B0_persistence", "B1_util_only", "A0_lgbm_noclock", "A1_lgbm_noclock_label", "L0_lstm", "L1_lstm_label"]
NAMES = {"B0_persistence": "B0 Persistence", "B1_util_only": "B1 Utilization-only LightGBM",
         "A0_lgbm_noclock": "A0 LightGBM (telemetry)", "A1_lgbm_noclock_label": "A1 LightGBM (telemetry + workload label)",
         "L0_lstm": "L0 LSTM", "L1_lstm_label": "L1 LSTM + workload label"}
rows = []
for m in ORDER:
    if m not in R["models"]:
        continue
    for r in R["models"][m]["test"]:
        if r["group"] == "ALL":
            rows.append(dict(model=m, name=NAMES[m], target=r["target"], horizon_s=r["horizon_s"], n=r["n"],
                             mae=r["mae"], rmse=r["rmse"], r2=r["r2"], mape_pct=r.get("mape_pct")))
T = pd.DataFrame(rows)
T.to_csv(out / "forecast_metrics_test.csv", index=False)

# per-label (only labels with enough test series, as the pipeline decided)
lab = []
for m in ORDER:
    for r in R["models"].get(m, {}).get("test", []):
        if r["group"] != "ALL" and r["horizon_s"] == 30:
            lab.append(dict(model=m, label=r["group"].split("=", 1)[1], target=r["target"], mae=r["mae"], n=r["n"]))
pd.DataFrame(lab).to_csv(out / "forecast_mae30_by_label.csv", index=False)

# figures
for tgt, unit in (("power", "W"), ("temp", "°C")):
    fig, ax = plt.subplots(figsize=(8, 3.6))
    d = T[T.target == tgt].pivot(index="horizon_s", columns="model", values="mae")[[m for m in ORDER if m in T.model.unique()]]
    d.plot(kind="bar", ax=ax, width=0.8, color=["#9aa3ad", "#6c7a89", "#3fa7d6", "#1f6fb2", "#f2a541", "#d1495b"])
    ax.set_ylabel(f"MAE ({unit})")
    ax.set_xlabel("forecast horizon (s)")
    ax.set_title(f"Test-split MAE, GPU {'power' if tgt == 'power' else 'temperature'} (lower is better)")
    ax.legend([NAMES[c] for c in d.columns], fontsize=7, ncol=2)
    ax.tick_params(axis="x", rotation=0)
    fig.tight_layout()
    fig.savefig(out / f"fig_mae_{tgt}.png", dpi=150)
    plt.close(fig)

summary = dict(
    audit={k: A[k] for k in ("files_processed", "files_failed", "jobs", "raw_rows", "clean_rows_1s", "duplicate_rows",
                             "impossible_rows", "gaps_over_threshold", "jobs_with_clocks", "t_first_utc", "t_last_utc",
                             "clean_gpu_hours", "dt_median_s_median")},
    missing_pct=A["missing_pct_by_field"],
    jobs_by_label=A["jobs_by_label"],
    split={k: S[k]["jobs"] for k in ("train", "val", "test")},
    split_dates={k: [S[k]["t_first_utc"], S[k]["t_last_utc"]] for k in ("train", "val", "test")},
    labels_in_test=sorted(S["test"]["jobs_by_label"]),
    labels_missing_from_test=S["labels_missing_from_test"],
    test_set=R["test_set"],
    selection=R["selection"],
    lstm_seed_spread={m: R["models"][m].get("test_mae_seed_mean_std") for m in ("L0_lstm", "L1_lstm_label") if m in R["models"]},
    lstm_selected_seed={m: R["models"][m].get("selected_seed") for m in ("L0_lstm", "L1_lstm_label") if m in R["models"]},
    latency_ms={m: R["models"][m].get("latency", {}).get("median_ms") for m in ORDER if m in R["models"]},
    size_bytes={m: R["models"][m].get("size_bytes") for m in ORDER if m in R["models"]},
    bootstrap_vs_B0={m: [dict(target=x["target"], h=x["horizon_s"], diff=x["mae_diff"], lo=x["ci95_low"], hi=x["ci95_high"])
                         for x in v] for m, v in R["bootstrap_vs_B0"].items()},
    clock_ablation=R["clock_ablation"].get("status"),
    runtime_seconds=R["runtime_seconds"],
    table=rows,
)
if E2:
    summary["e2"] = dict(threshold=E2["settings"]["T_threshold_C"], traces=E2["traces"], calibration={
        k: E2["calibration"][k] for k in ("tau_s", "R_K_per_W", "C_total_J_per_K", "rmse_C")},
        rows=[dict(controller=c, time_above_s=m["time_above_threshold_s"]["total"], peak_median=m["peak_Tj_C"]["median"],
                   overshoot_median=m["overshoot_C"]["median"], energy_ratio=m.get("est_pump_energy_vs_baseline_ratio"),
                   reversals_median=m["valve_reversals"]["median"], response_median=m["response_time_median_s"]["median"],
                   reversals_mean=sum(t[c]["valve_reversals"] for t in E2["per_trace"].values()) / len(E2["per_trace"]),
                   traces_above=sum(1 for t in E2["per_trace"].values() if t[c]["time_above_threshold_s"] > 0))
              for c, m in E2["summary"].items()])
(out / "summary.json").write_text(json.dumps(summary, indent=1, default=float))
print(T[["name", "target", "horizon_s", "mae", "rmse", "r2"]].round(3).to_string())
