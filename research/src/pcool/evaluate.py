"""Metrics on the chronological test split (brief §16). Every number comes from here."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import Config
from .features import SHORT

TARGET_LEVEL_NOW = {"power": "power_draw_W", "temp": "temperature_gpu"}


def _metrics(y: np.ndarray, p: np.ndarray, with_mape: bool) -> dict:
    e = p - y
    ss_res, ss_tot = float(np.sum(e ** 2)), float(np.sum((y - y.mean()) ** 2))
    out = dict(n=int(len(y)), mae=float(np.mean(np.abs(e))), rmse=float(np.sqrt(np.mean(e ** 2))),
               r2=float(1 - ss_res / ss_tot) if ss_tot > 0 else None)
    if with_mape:
        m = np.abs(y) >= 1.0   # avoid division by ~0 W
        out["mape_pct"] = float(100 * np.mean(np.abs(e[m]) / np.abs(y[m]))) if m.any() else None
    return out


def level_predictions(df: pd.DataFrame, pred_delta: pd.DataFrame, cfg: Config) -> dict:
    """{(target_short, h): (y_true_level, y_pred_level)} reconstructed from predicted changes."""
    res = {}
    for tgt in cfg.targets:
        s = SHORT[tgt]
        for h in cfg.horizons_s:
            y = df[f"y_{s}_{h}"].to_numpy(float)
            p = df[tgt].to_numpy(float) + pred_delta[f"d_{s}_{h}"].to_numpy(float)
            res[(s, h)] = (y, p)
    return res


def score(df: pd.DataFrame, pred_delta: pd.DataFrame, cfg: Config) -> list[dict]:
    rows = []
    for (s, h), (y, p) in level_predictions(df, pred_delta, cfg).items():
        rows.append(dict(target=s, horizon_s=h, group="ALL", **_metrics(y, p, with_mape=(s == "power"))))
        for lab, idx in df.groupby("label").indices.items():
            if df.iloc[idx]["series_id"].nunique() < cfg.min_series_per_label:
                continue
            rows.append(dict(target=s, horizon_s=h, group=f"label={lab}",
                             **_metrics(y[idx], p[idx], with_mape=(s == "power"))))
    return rows


def paired_bootstrap_mae_diff(df: pd.DataFrame, pred_a: pd.DataFrame, pred_b: pd.DataFrame,
                              cfg: Config, seed: int = 0) -> list[dict]:
    """95 % CI of MAE(a) - MAE(b), resampling whole test JOBS (respects within-job correlation)."""
    rng = np.random.default_rng(seed)
    jobs = df["job_id"].to_numpy()
    uniq, inv = np.unique(jobs, return_inverse=True)
    la, lb = level_predictions(df, pred_a, cfg), level_predictions(df, pred_b, cfg)
    out = []
    for key in la:
        y, pa = la[key]
        _, pb = lb[key]
        ea, eb = np.abs(pa - y), np.abs(pb - y)
        sa = np.bincount(inv, ea, len(uniq))
        sb = np.bincount(inv, eb, len(uniq))
        cnt = np.bincount(inv, None, len(uniq)).astype(float)
        diffs = np.empty(cfg.bootstrap_resamples)
        for i in range(cfg.bootstrap_resamples):
            w = np.bincount(rng.integers(0, len(uniq), len(uniq)), minlength=len(uniq))
            diffs[i] = (w @ sa) / (w @ cnt) - (w @ sb) / (w @ cnt)
        out.append(dict(target=key[0], horizon_s=key[1], mae_diff=float(ea.mean() - eb.mean()),
                        ci95_low=float(np.percentile(diffs, 2.5)), ci95_high=float(np.percentile(diffs, 97.5)),
                        n_test_jobs=int(len(uniq))))
    return out
