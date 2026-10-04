"""Preprocessing: raw nvidia-smi CSV -> clean 1 s series (brief §10 steps 1-9).

One output parquet per source file. An audit record (counts of rows, missing values,
duplicates, impossible values, gaps) is written for every file so the dataset audit
can be completed from measured numbers.
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import threading
import traceback

import numpy as np
import pandas as pd

from .config import Config
from .data_access import fetch_csv, labelled_file_index

CORE = [
    "utilization_gpu_pct", "utilization_memory_pct", "memory_free_MiB", "memory_used_MiB",
    "temperature_gpu", "temperature_memory", "power_draw_W",
]
CLOCKS = ["clocks_current_sm_MHz", "clocks_current_memory_MHz", "power_limit_W"]
SLOW = ["memory_free_MiB", "memory_used_MiB"] + CLOCKS   # may be forward-filled briefly

_audit_lock = threading.Lock()


def _impossible_mask(df: pd.DataFrame, cfg: Config) -> pd.Series:
    bad = pd.Series(False, index=df.index)
    for c in ("utilization_gpu_pct", "utilization_memory_pct"):
        bad |= ~df[c].between(0, 100)
    for c in ("temperature_gpu", "temperature_memory"):
        bad |= ~df[c].between(cfg.min_temp_c, cfg.max_temp_c)
    if "power_limit_W" in df:
        cap = (df["power_limit_W"] * cfg.power_limit_factor).fillna(cfg.fallback_power_cap_w)
    else:
        cap = cfg.fallback_power_cap_w
    bad |= (df["power_draw_W"] < 0) | (df["power_draw_W"] > cap)
    bad |= (df["memory_used_MiB"] < 0) | (df["memory_free_MiB"] < 0)
    return bad


def clean_file(raw: pd.DataFrame, file_id: str, job_id: str, label: str, cfg: Config):
    """Return (clean dataframe on the 1 s grid, audit dict)."""
    audit = dict(file_id=file_id, job_id=job_id, label=label, raw_rows=int(len(raw)),
                 columns=list(raw.columns), has_clocks=bool(set(CLOCKS) <= set(raw.columns)))
    present = [c for c in CORE + CLOCKS if c in raw.columns]
    raw = raw[["timestamp", "gpu_index"] + present].copy()
    for c in present:  # nvidia-smi may print "[N/A]" etc.; coerce, count as missing
        raw[c] = pd.to_numeric(raw[c], errors="coerce")
    audit["missing_cells"] = {c: int(raw[c].isna().sum()) for c in present}
    audit["missing_timestamp"] = int(raw["timestamp"].isna().sum())

    raw = raw.dropna(subset=["timestamp"]).sort_values(["gpu_index", "timestamp"], kind="stable")
    dup = raw.duplicated(subset=["gpu_index", "timestamp"])
    audit["duplicate_rows"] = int(dup.sum())
    raw = raw[~dup]

    # rows with a missing core field are not "impossible"; they are counted as missing
    bad = _impossible_mask(raw, cfg) & raw[CORE].notna().all(axis=1)
    audit["impossible_rows"] = int(bad.sum())
    raw = raw[~bad]

    if len(raw):
        dts = raw.groupby("gpu_index")["timestamp"].diff().dropna()
        audit["dt_median_s"] = float(dts.median()) if len(dts) else None
        audit["dt_p99_s"] = float(dts.quantile(0.99)) if len(dts) else None
        audit["t_start"], audit["t_end"] = float(raw["timestamp"].min()), float(raw["timestamp"].max())

    out, n_gaps, n_dropped_short = [], 0, 0
    g = cfg.grid_seconds
    for gpu, d in raw.groupby("gpu_index"):
        b = np.floor(d["timestamp"].to_numpy() / g).astype(np.int64)
        binned = d.assign(t=b).groupby("t")[present].mean()
        t = binned.index.to_numpy()
        seg = np.concatenate([[0], np.cumsum(np.diff(t) * g > cfg.max_gap_seconds)])
        n_gaps += int(seg[-1]) if len(seg) else 0
        binned["segment"] = seg
        for s, sd in binned.groupby("segment"):
            full = sd.reindex(np.arange(sd.index.min(), sd.index.max() + 1))
            full["segment"] = s
            slow = [c for c in SLOW if c in full]
            full[slow] = full[slow].ffill(limit=int(cfg.ffill_limit_seconds / g))
            if len(full) * g < cfg.min_segment_seconds:
                n_dropped_short += 1
                continue
            full["gpu_index"] = int(gpu)
            out.append(full.rename_axis("t").reset_index())
    audit["gaps_over_threshold"] = n_gaps
    audit["segments_dropped_short"] = n_dropped_short
    if not out:
        audit["clean_rows"] = 0
        return None, audit
    clean = pd.concat(out, ignore_index=True)
    for c in CLOCKS:  # uniform schema; absent clocks stay NaN and are never imputed
        if c not in clean:
            clean[c] = np.nan
    clean.insert(0, "label", label)
    clean.insert(0, "job_id", job_id)
    clean.insert(0, "file_id", file_id)
    clean["series_id"] = clean["file_id"] + ":" + clean["gpu_index"].astype(str) + ":" + clean["segment"].astype(str)
    audit["clean_rows"] = int(len(clean))
    audit["clean_missing_cells"] = {c: int(clean[c].isna().sum()) for c in CORE + CLOCKS}
    return clean, audit


def run(cfg: Config, workers: int = 8) -> pd.DataFrame:
    """Process every labelled file not already processed. Resumable."""
    p = cfg.paths()
    idx = labelled_file_index(cfg)
    if cfg.max_jobs:
        jobs = sorted(idx["job_id"].unique())[: cfg.max_jobs]
        idx = idx[idx["job_id"].isin(jobs)]
    audit_path = p["reports"] / "preprocess_audit.jsonl"
    done = set()
    if audit_path.exists():
        done = {json.loads(l)["file_id"] for l in audit_path.read_text().splitlines() if l.strip()}
    todo = idx[~idx["file_id"].isin(done)]
    print(f"{len(idx)} labelled files, {len(done)} already done, {len(todo)} to process")

    def one(row):
        try:
            raw, sha, nbytes = fetch_csv(cfg, row.key)
            clean, audit = clean_file(raw, row.file_id, row.job_id, row.label, cfg)
            audit.update(sha256=sha, n_bytes=nbytes, key=row.key)
            if clean is not None:
                clean.to_parquet(p["clean"] / f"{row.file_id}.parquet", index=False)
        except Exception:
            audit = dict(file_id=row.file_id, job_id=row.job_id, key=row.key, error=traceback.format_exc())
        with _audit_lock, audit_path.open("a") as f:
            f.write(json.dumps(audit) + "\n")
        return audit

    with cf.ThreadPoolExecutor(workers) as ex:
        for i, a in enumerate(ex.map(one, todo.itertuples(index=False)), 1):
            if i % 100 == 0 or "error" in a:
                print(i, a["file_id"], "ERROR" if "error" in a else a.get("clean_rows"))
    return load_audit(cfg)


def load_audit(cfg: Config) -> pd.DataFrame:
    path = cfg.paths()["reports"] / "preprocess_audit.jsonl"
    return pd.DataFrame([json.loads(l) for l in path.read_text().splitlines() if l.strip()])


def summarize_audit(audit: pd.DataFrame) -> dict:
    """Dataset-level audit numbers, computed (not estimated) from per-file records."""
    ok = audit[audit.get("error").isna()] if "error" in audit else audit
    miss = pd.DataFrame(list(ok["missing_cells"])).sum()
    raw_rows = int(ok["raw_rows"].sum())
    return dict(
        files_processed=int(len(ok)),
        files_failed=int(len(audit) - len(ok)),
        jobs=int(ok["job_id"].nunique()),
        raw_rows=raw_rows,
        clean_rows_1s=int(ok["clean_rows"].sum()),
        missing_pct_by_field={k: round(100 * v / raw_rows, 4) for k, v in miss.items()},
        duplicate_rows=int(ok["duplicate_rows"].sum()),
        impossible_rows=int(ok["impossible_rows"].sum()),
        gaps_over_threshold=int(ok["gaps_over_threshold"].sum()),
        files_with_clocks=int(ok["has_clocks"].sum()),
        jobs_with_clocks=int(ok.loc[ok["has_clocks"], "job_id"].nunique()),
        dt_median_s_median=float(ok["dt_median_s"].median()),
        clean_gpu_hours=round(float(ok["clean_rows"].sum()) / 3600.0, 2),  # 1 s grid
        t_first_utc=str(pd.to_datetime(ok["t_start"].min(), unit="s")),
        t_last_utc=str(pd.to_datetime(ok["t_end"].max(), unit="s")),
        rows_by_label=ok.groupby("label")["raw_rows"].sum().astype(int).to_dict(),
        jobs_by_label=ok.groupby("label")["job_id"].nunique().astype(int).to_dict(),
    )
