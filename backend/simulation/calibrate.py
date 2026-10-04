"""Identify thermal inertia from REAL power -> temperature traces (brief section 6, option B).

Model fitted (per 1 s step, pooled over series):
    T(t) = T(0) a^t + T_amb (1 - a^t) + R * F_tau[P](t),   a = exp(-1/tau)
where F_tau is a first-order low-pass filter. For each tau on a grid, (T_amb, R) are
solved by least squares; the tau with lowest RMSE wins. C_total = tau / R.

Only C_total is passed to the twin. R and T_amb describe the SOURCE system's cooling
(not two-phase) and are reported, not reused.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

TAU_GRID_S = (5, 10, 15, 20, 25, 30, 40, 50, 60, 90, 120, 180, 240)


def _lowpass(x: np.ndarray, tau: float) -> np.ndarray:
    a = np.exp(-1.0 / tau)
    y = np.empty_like(x, dtype=float)
    acc = 0.0
    for i, v in enumerate(x):
        acc = a * acc + (1 - a) * v
        y[i] = acc
    return y


def fit_first_order(series: list[tuple[np.ndarray, np.ndarray]]) -> dict:
    """series: list of (power_W, temperature_C) arrays on a 1 s grid (NaNs allowed in T)."""
    best = None
    table = []
    for tau in TAU_GRID_S:
        A, Y = [], []
        a = np.exp(-1.0 / tau)
        for P, T in series:
            P = pd.Series(P).ffill().bfill().to_numpy(float)
            T = np.asarray(T, float)
            if np.isnan(T[0]):
                continue
            decay = a ** np.arange(1, len(P) + 1)
            m = ~np.isnan(T)
            A.append(np.c_[1 - decay, _lowpass(P, tau)][m])
            Y.append((T - T[0] * decay)[m])
        A, Y = np.vstack(A), np.concatenate(Y)
        coef, *_ = np.linalg.lstsq(A, Y, rcond=None)
        rmse = float(np.sqrt(np.mean((A @ coef - Y) ** 2)))
        row = dict(tau_s=tau, rmse_C=rmse, T_amb_C=float(coef[0]), R_K_per_W=float(coef[1]))
        table.append(row)
        if best is None or rmse < best["rmse_C"]:
            best = row
    best = dict(best, C_total_J_per_K=best["tau_s"] / best["R_K_per_W"], n_series=len(series),
                n_seconds=int(sum(len(P) for P, _ in series)), grid=table)
    return best


def series_from_clean(clean: pd.DataFrame) -> list[tuple[np.ndarray, np.ndarray]]:
    out = []
    for _, s in clean.groupby("series_id", sort=False):
        s = s.sort_values("t")
        out.append((s["power_draw_W"].to_numpy(float), s["temperature_gpu"].to_numpy(float)))
    return out
