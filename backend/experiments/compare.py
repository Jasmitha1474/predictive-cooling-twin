"""E2: reactive vs predictive cooling on the SAME real workload traces (docs/experiments.md).

Input  : REAL measured power traces (clean 1 s parquet from research/src/pcool).
Output : SIMULATED control-response metrics, written to research/reports/e2_results.json.
Every controller sees identical traces, initial state, twin parameters and settings.

Usage (from backend/):
  python -m experiments.compare --clean-dir ../research/work/clean \
      --split-jobs ../research/work/reports/split_jobs.csv --use-split test \
      --forecasters persistence oracle lgbm:../research/work/models/A1_lgbm_noclock_label
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import dataclasses
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from controller.controllers import ControlSettings, Predictive, ReactivePI, ReactiveThreshold  # noqa: E402
from controller.forecasters import load_forecaster  # noqa: E402
from simulation.calibrate import fit_first_order, series_from_clean  # noqa: E402
from simulation.twin import Twin, TwinParams, steady_state_Tj  # noqa: E402

P_REF_W = 250.0   # threshold reference power: the power_limit_W value observed in Supercloud V100 rows
EVENT_RISE_W = 0.30 * P_REF_W
EVENT_WINDOW_S = 10
RESPONSE_WINDOW_S = 60


# ------------------------------------------------------------------ simulation of one trace
def simulate(P: np.ndarray, forecast: np.ndarray | None, ctrl, p: TwinParams, s: ControlSettings) -> dict:
    n_sub = int(round(1.0 / p.dt_s))
    twin = Twin(p, T0_C=steady_state_Tj(p, P[0], s.v_min), v0=s.v_min)
    twin.T_cp = twin.T_j - P[0] * p.R_jc_K_per_W
    out = {k: np.empty(len(P)) for k in ("T_j", "T_cp", "v_cmd", "v", "Q", "Q_rem")}
    pump_energy = 0.0
    for k in range(len(P)):
        sim = twin.snapshot()
        v_cmd = ctrl.decide(sim, P[k], None if forecast is None else forecast[k])
        for _ in range(n_sub):
            r = twin.step(P[k], v_cmd)
            pump_energy += r["pump"] * p.dt_s
        out["T_j"][k], out["T_cp"][k], out["v_cmd"][k] = r["T_j"], r["T_cp"], v_cmd
        out["v"][k], out["Q"][k], out["Q_rem"][k] = r["v"], r["Q"], r["Q_rem"]
    out["pump_energy_rel"] = pump_energy
    return out


def events(P: np.ndarray) -> list[int]:
    """Power-rise events: rise >= 30 % of P_REF within 10 s; at least 60 s apart."""
    ev, k = [], 0
    while k < len(P) - EVENT_WINDOW_S:
        if P[k + EVENT_WINDOW_S] - P[k] >= EVENT_RISE_W:
            ev.append(k)
            k += RESPONSE_WINDOW_S
        else:
            k += 1
    return ev


def metrics(out: dict, P: np.ndarray, s: ControlSettings) -> dict:
    T, v = out["T_j"], out["v"]
    dv = np.diff(out["v_cmd"])
    dv = dv[np.abs(dv) > 1e-6]
    resp = []
    for e in events(P):
        w = v[e:e + RESPONSE_WINDOW_S]
        rise = w.max() - w[0]
        if rise < 0.05:
            resp.append(np.nan)               # no cooling response within 60 s
            continue
        resp.append(float(np.argmax(w >= w[0] + 0.9 * rise)))
    resp = np.array(resp)
    return dict(
        peak_Tj_C=float(T.max()),
        overshoot_C=float(max(0.0, T.max() - s.T_threshold_C)),
        time_above_threshold_s=float((T > s.T_threshold_C).sum()),
        mean_cooling_demand=float(out["v_cmd"].mean()),
        est_pump_energy_rel=float(out["pump_energy_rel"]),
        Tj_std_C=float(T.std()),
        valve_reversals=int((np.diff(np.sign(dv)) != 0).sum()) if len(dv) > 1 else 0,
        n_power_events=int(len(resp)),
        n_events_with_response=int(np.isfinite(resp).sum()),
        response_time_median_s=float(np.nanmedian(resp)) if np.isfinite(resp).any() else None,
        duration_s=int(len(P)),
    )


def _run_trace(args):
    sid, P, fc, p_dict, s_dict = args[:5]
    dump = len(args) > 5 and args[5]
    p, s = TwinParams(**p_dict), ControlSettings(**s_dict)
    res = {}
    ctrls = [ReactiveThreshold(s), ReactivePI(s)]
    for name in fc:
        ctrls.append(Predictive(s, p, name=f"predictive_{name}"))
    for c in ctrls:
        f = fc.get(c.name.replace("predictive_", "")) if c.name.startswith("predictive_") else None
        out = simulate(P, f, c, p, s)
        res[c.name] = metrics(out, P, s)
        if dump:
            res[c.name]["timeseries"] = {k: np.round(v, 4).tolist() for k, v in out.items() if isinstance(v, np.ndarray)}
    if dump:
        res["_inputs"] = dict(measured_power_W=np.round(P, 3).tolist(),
                              forecasts={k: np.round(v, 3).tolist() for k, v in fc.items()})
    return sid, res


# ------------------------------------------------------------------ experiment driver
def load_traces(clean_dir: Path, split_jobs: Path | None, use_split: str | None, max_series: int | None,
                max_seconds: int | None = None):
    clean = pd.read_parquet(clean_dir)
    if split_jobs is not None and use_split:
        jobs = pd.read_csv(split_jobs, dtype={"job_id": str})
        keep = set(jobs.loc[jobs["split"].isin(use_split.split(",")), "job_id"])
        clean = clean[clean["job_id"].isin(keep)]
    sids = sorted(clean["series_id"].unique())[: max_series or None]
    out = clean[clean["series_id"].isin(sids)].sort_values(["series_id", "t"])
    if max_seconds:   # first N seconds of every series (same window for every controller)
        out = out[out.groupby("series_id").cumcount() < max_seconds]
    return out


def run(clean: pd.DataFrame, forecasters: list, p: TwinParams, s: ControlSettings, workers: int,
        dump_series: tuple = ()) -> dict:
    tasks = []
    for sid, d in clean.groupby("series_id", sort=True):
        P = d["power_draw_W"].ffill().bfill().to_numpy(float)
        tasks.append((sid, P, {f.name: f.forecast(d.reset_index(drop=True)) for f in forecasters},
                      p.to_dict(), dataclasses.asdict(s), sid in dump_series))
    with cf.ProcessPoolExecutor(workers) as ex:
        return dict(ex.map(_run_trace, tasks))


def summarize(per_trace: dict, baseline: str = "reactive_threshold") -> dict:
    from scipy.stats import wilcoxon
    ctrls = [c for c in next(iter(per_trace.values())).keys() if not c.startswith("_")]
    keys = ["peak_Tj_C", "overshoot_C", "time_above_threshold_s", "mean_cooling_demand",
            "est_pump_energy_rel", "Tj_std_C", "valve_reversals", "response_time_median_s"]
    summ = {}
    for c in ctrls:
        summ[c] = {}
        for k in keys:
            vals = np.array([per_trace[t][c][k] if per_trace[t][c][k] is not None else np.nan for t in per_trace], float)
            base = np.array([per_trace[t][baseline][k] if per_trace[t][baseline][k] is not None else np.nan
                             for t in per_trace], float)
            d = vals - base
            m = np.isfinite(d)
            entry = dict(median=float(np.nanmedian(vals)) if np.isfinite(vals).any() else None,
                         total=float(np.nansum(vals)) if k in ("time_above_threshold_s", "est_pump_energy_rel") else None)
            if c != baseline and m.sum() >= 1:
                entry.update(diff_vs_baseline_median=float(np.median(d[m])),
                             diff_iqr=[float(np.percentile(d[m], 25)), float(np.percentile(d[m], 75))],
                             n_paired=int(m.sum()))
                nz = d[m][d[m] != 0]
                if len(nz) >= 6:
                    entry["wilcoxon_p"] = float(wilcoxon(nz).pvalue)
                else:
                    entry["wilcoxon_p"] = None   # too few non-zero paired differences
            summ[c][k] = entry
        if "est_pump_energy_rel" in summ[c] and summ[baseline]["est_pump_energy_rel"]["total"]:
            summ[c]["est_pump_energy_vs_baseline_ratio"] = (
                summ[c]["est_pump_energy_rel"]["total"] / summ[baseline]["est_pump_energy_rel"]["total"])
    return summ


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--clean-dir", required=True, type=Path)
    ap.add_argument("--split-jobs", type=Path)
    ap.add_argument("--use-split", default=None, help="train/val/test; omit to use all traces")
    ap.add_argument("--calibrate-split", default="train", help="split used to fit thermal inertia")
    ap.add_argument("--forecasters", nargs="+", default=["persistence", "oracle"])
    ap.add_argument("--max-series", type=int)
    ap.add_argument("--max-seconds", type=int, help="use only the first N seconds of each trace")
    ap.add_argument("--sensitivity", action="store_true")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parents[2] / "research/reports/e2_results.json")
    ap.add_argument("--label", default="", help="free text stored in the results (e.g. 'preliminary')")
    ap.add_argument("--dump-series", nargs="*", default=[], help="series ids whose per-second timeseries are saved")
    ap.add_argument("--dump-out", type=Path, help="where to write the timeseries JSON")
    a = ap.parse_args(argv)
    t0 = time.time()

    # ---- calibration of thermal inertia on REAL data (temperature used here only)
    cal_clean = load_traces(a.clean_dir, a.split_jobs, a.calibrate_split if a.split_jobs else None, None)
    cal = fit_first_order(series_from_clean(cal_clean))
    p = TwinParams(C_total_J_per_K=cal["C_total_J_per_K"])
    Twin(p).check_stability()
    s = ControlSettings(T_threshold_C=round(steady_state_Tj(p, P_REF_W, 0.5), 1))

    clean = load_traces(a.clean_dir, a.split_jobs, a.use_split, a.max_series, a.max_seconds)
    forecasters = [load_forecaster(x) for x in a.forecasters]
    per_trace = run(clean, forecasters, p, s, a.workers, tuple(a.dump_series))
    if a.dump_series:
        ts = {sid: per_trace[sid] for sid in a.dump_series if sid in per_trace}
        for sid in ts:
            per_trace[sid] = {k: {m: v for m, v in d.items() if m != "timeseries"} for k, d in per_trace[sid].items()
                              if not k.startswith("_")}
        (a.dump_out or a.out.with_name(a.out.stem + "_timeseries.json")).write_text(json.dumps(ts))
    result = dict(
        label=a.label,
        note=("Controller metrics are SIMULATED (twin driven by REAL measured power). Cooling-side twin "
              "parameters are ASSUMED; thermal inertia is fitted on real data. Not physical measurements."),
        traces=dict(n_series=len(per_trace), n_jobs=int(clean["job_id"].nunique()),
                    total_seconds=int(len(clean)), series_ids=sorted(per_trace),
                    labels=clean.groupby("label")["series_id"].nunique().astype(int).to_dict(),
                    split_used=a.use_split or "all", max_seconds_per_trace=a.max_seconds),
        calibration={k: v for k, v in cal.items()},
        calibration_split=a.calibrate_split if a.split_jobs else "all",
        twin_params=p.to_dict(), settings=dataclasses.asdict(s),
        threshold_rule=f"steady-state T_j at {P_REF_W:.0f} W with valve 0.5",
        forecasters=[f.name for f in forecasters],
        summary=summarize(per_trace), per_trace=per_trace,
    )
    if a.sensitivity:
        result["sensitivity"] = sensitivity(clean, forecasters, p, s, a.workers)
    result["runtime_s"] = round(time.time() - t0, 1)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2, default=float))
    print("wrote", a.out)
    return result


def sensitivity(clean, forecasters, p: TwinParams, s: ControlSettings, workers: int) -> list[dict]:
    """One-at-a-time sweeps of the ASSUMED parameters that most affect the comparison."""
    rows = []
    sweeps = [("transport_delay_s", [2.0, 10.0, 20.0]), ("tau_valve_s", [2.0, 10.0]),
              ("T_threshold_offset_C", [-5.0, 5.0])]
    for name, values in sweeps:
        for val in values:
            p2, s2 = dataclasses.replace(p), dataclasses.replace(s)
            if name == "T_threshold_offset_C":
                s2.T_threshold_C = s.T_threshold_C + val
            else:
                setattr(p2, name, val)
            summ = summarize(run(clean, forecasters, p2, s2, workers))
            rows.append(dict(parameter=name, value=val, summary={
                c: {k: summ[c][k] for k in ("time_above_threshold_s", "peak_Tj_C", "est_pump_energy_rel")}
                for c in summ}))
    return rows


if __name__ == "__main__":
    main()
