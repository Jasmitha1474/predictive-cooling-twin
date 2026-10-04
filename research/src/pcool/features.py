"""Leakage-free features and multi-horizon targets (brief §10 steps 11-12, §15).

Every feature at grid time t uses only rows <= t of the same series. Targets use the
row at t + h of the same series only; rows whose target falls outside the series are
dropped. A unit test (tests/test_leakage.py) checks both properties.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import Config

# Fixed mapping from the dataset's original labels to coarse families. Published so
# readers can check it; it is derived from the label names, not invented labels.
FAMILY = {
    **{k: "vision_cnn" for k in ["vgg11", "vgg16", "vgg19", "inception3", "inception4", "resnet50",
                                  "resnet50_v1.5", "resnet101", "resnet101_v2", "resnet152", "resnet152_v2"]},
    **{f"U{d}-{w}": "unet" for d in (3, 4, 5) for w in (32, 64, 128)},
    "bert-base-uncased": "nlp_transformer", "distilbert-base-uncased": "nlp_transformer",
    "dimenet": "gnn", "schnet": "gnn", "pna": "gnn", "conv": "gnn",
}

RAW_FEATURES = ["utilization_gpu_pct", "utilization_memory_pct", "memory_used_MiB",
                "temperature_gpu", "temperature_memory", "power_draw_W"]
CLOCK_FEATURES = ["clocks_current_sm_MHz", "clocks_current_memory_MHz", "power_limit_W", "power_frac_of_limit"]
UTIL_ONLY_PREFIX = "utilization_gpu_pct"
SHORT = {"utilization_gpu_pct": "util", "utilization_memory_pct": "memutil", "memory_used_MiB": "memused",
         "temperature_gpu": "temp", "temperature_memory": "memtemp", "power_draw_W": "power",
         "clocks_current_sm_MHz": "smclk"}


def _trailing_slope(y: np.ndarray, w: int) -> np.ndarray:
    """Least-squares slope (units per second on a 1 s grid) over the last w points."""
    out = np.full(len(y), np.nan)
    if len(y) < w:
        return out
    j = np.arange(w) - (w - 1) / 2.0
    k = j / np.sum(j * j)
    out[w - 1:] = np.convolve(y, k[::-1], mode="valid")
    return out


def series_features(s: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    """Features + targets for ONE contiguous series on the 1 s grid (sorted by t)."""
    s = s.sort_values("t").reset_index(drop=True)
    f = pd.DataFrame({"series_id": s["series_id"], "job_id": s["job_id"], "label": s["label"], "t": s["t"]})
    f["family"] = s["label"].map(FAMILY).fillna("unknown")
    for c in RAW_FEATURES + ["clocks_current_sm_MHz", "clocks_current_memory_MHz", "power_limit_W"]:
        f[c] = s[c].to_numpy()
    f["power_frac_of_limit"] = s["power_draw_W"] / s["power_limit_W"]
    f["t_since_start_s"] = s["t"] - s["t"].iloc[0]

    for w in cfg.roll_windows_s:
        r = s["power_draw_W"].rolling(w, min_periods=w)
        f[f"power_mean_{w}"], f[f"power_max_{w}"], f[f"power_std_{w}"] = r.mean(), r.max(), r.std()
        f[f"util_mean_{w}"] = s["utilization_gpu_pct"].rolling(w, min_periods=w).mean()
        f[f"util_max_{w}"] = s["utilization_gpu_pct"].rolling(w, min_periods=w).max()
        f[f"temp_mean_{w}"] = s["temperature_gpu"].rolling(w, min_periods=w).mean()
        f[f"memutil_mean_{w}"] = s["utilization_memory_pct"].rolling(w, min_periods=w).mean()
        for c in ["temperature_gpu", "power_draw_W", "utilization_gpu_pct", "memory_used_MiB", "clocks_current_sm_MHz"]:
            f[f"{SHORT[c]}_slope_{w}"] = _trailing_slope(s[c].to_numpy(dtype=float), w)
    for lag in cfg.lags_s:
        for c in ["power_draw_W", "temperature_gpu", "utilization_gpu_pct"]:
            f[f"{SHORT[c]}_lag_{lag}"] = s[c].shift(lag)

    for tgt in cfg.targets:
        y = s[tgt]
        for h in cfg.horizons_s:
            f[f"y_{SHORT[tgt]}_{h}"] = y.shift(-h)              # level at t+h
            f[f"d_{SHORT[tgt]}_{h}"] = y.shift(-h) - y           # change, the model target
    return f


def feature_columns(df: pd.DataFrame, kind: str) -> list[str]:
    """Feature sets for the model ladder in docs/methodology.md §7."""
    excluded = {"series_id", "job_id", "label", "family", "t", "split"}
    allf = [c for c in df.columns if c not in excluded and not c.startswith(("y_", "d_"))]
    if kind == "util_only":                                   # B1
        return [c for c in allf if c.startswith(("utilization_gpu_pct", "util_"))]
    no_clock = [c for c in allf if not any(k in c for k in ("clocks_", "power_limit", "power_frac", "smclk"))]
    if kind == "full_noclock":                                # A0
        return no_clock
    if kind == "full_noclock_label":                          # A1
        return no_clock + ["label", "family"]
    if kind == "full_clock_label":                            # clock ablation (clock subset only)
        return allf + ["label", "family"]
    raise ValueError(kind)


def target_columns(cfg: Config) -> list[str]:
    return [f"d_{SHORT[t]}_{h}" for t in cfg.targets for h in cfg.horizons_s]


def build_file_features(clean: pd.DataFrame, split_of_job: dict, cfg: Config) -> pd.DataFrame:
    """Features for every series in one clean file, sampled with the configured stride."""
    parts = []
    warm = max(max(cfg.roll_windows_s), max(cfg.lags_s), cfg.seq_len_s)
    for _, s in clean.groupby("series_id", sort=False):
        f = series_features(s, cfg)
        split = split_of_job[s["job_id"].iloc[0]]
        stride = cfg.train_stride_s if split == "train" else cfg.eval_stride_s
        keep = (f["t_since_start_s"] >= warm) & (f["t_since_start_s"] % stride == 0)
        keep &= f[target_columns(cfg)].notna().all(axis=1)
        keep &= f[["power_draw_W", "temperature_gpu", "utilization_gpu_pct"]].notna().all(axis=1)
        f = f[keep]
        f.insert(0, "split", split)
        parts.append(f)
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
