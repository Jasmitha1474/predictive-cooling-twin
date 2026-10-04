"""LSTM forecaster (Model B): 60 s of raw telemetry -> 6 changes (2 targets x 3 horizons).

Sequences are cut from the clean 1 s series at exactly the same anchor points
(series_id, t) used by the tree models, so all models are scored on identical rows.
"""
from __future__ import annotations

import time

import numpy as np
import pandas as pd
import torch
from torch import nn

from .config import Config
from .features import target_columns

LSTM_INPUTS = ["utilization_gpu_pct", "utilization_memory_pct", "memory_used_MiB",
               "temperature_gpu", "temperature_memory", "power_draw_W"]


class SeriesStore:
    """All clean series in ONE contiguous float32 array [total_seconds, 6] plus per-series offsets.

    Windows are cut lazily, a batch at a time, with vectorised indexing, so the full set of
    (n_anchors x 60 x 6) windows is never held in memory. NaN gaps <= 2 s are forward-filled
    within a series (unchanged rule); a window is valid only if it lies inside one series and
    contains no NaN (unchanged rule).
    """

    def __init__(self, clean: pd.DataFrame | None = None, labels: list[str] | None = None):
        self.labels = labels or []
        self._parts, self.index = [], {}
        self._n = 0
        if clean is not None:
            for sid, s in clean.groupby("series_id", sort=False, observed=True):
                self._add(str(sid), s)
            self._finish()

    # ---- construction
    def _add(self, sid: str, s: pd.DataFrame):
        s = s.sort_values("t")
        x = s[LSTM_INPUTS].ffill(limit=2).to_numpy(np.float32)
        lab = str(s["label"].iloc[0])
        self.index[sid] = (self._n, int(s["t"].iloc[0]), len(x), self.labels.index(lab) if lab in self.labels else -1)
        self._parts.append(x)
        self._n += len(x)

    def _finish(self):
        self.data = np.empty((self._n, len(LSTM_INPUTS)), np.float32)
        for (off, _, n, _), x in zip(self.index.values(), self._parts):
            self.data[off:off + n] = x
        self._parts = []
        bad = np.isnan(self.data).any(axis=1)
        self.nan_cum = np.concatenate([[0], np.cumsum(bad, dtype=np.int64)])

    @classmethod
    def from_parquet_dir(cls, clean_dir, labels: list[str], keep_series: set | None = None):
        """Stream the clean Parquet files one by one (never the whole dataset as a DataFrame)."""
        import pyarrow.parquet as pq
        from pathlib import Path
        st = cls(None, labels)
        files = sorted(Path(clean_dir).glob("*.parquet"))
        total = sum(pq.ParquetFile(f).metadata.num_rows for f in files)
        st.data = np.empty((total, len(LSTM_INPUTS)), np.float32)   # upper bound, trimmed below
        for f in files:
            d = pd.read_parquet(f, columns=["series_id", "t", "label"] + LSTM_INPUTS)
            for sid, s in d.groupby("series_id", sort=False):
                if keep_series is not None and sid not in keep_series:
                    continue
                s = s.sort_values("t")
                x = s[LSTM_INPUTS].ffill(limit=2).to_numpy(np.float32)
                lab = str(s["label"].iloc[0])
                st.index[str(sid)] = (st._n, int(s["t"].iloc[0]), len(x), labels.index(lab) if lab in labels else -1)
                st.data[st._n:st._n + len(x)] = x
                st._n += len(x)
            del d
        st.data = st.data[:st._n].copy() if st._n < total else st.data
        bad = np.isnan(st.data).any(axis=1)
        st.nan_cum = np.concatenate([[0], np.cumsum(bad, dtype=np.int64)])
        return st

    # ---- lookup
    def anchor_ends(self, anchors: pd.DataFrame, seq: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """For anchor rows (series_id, t): global end index (exclusive), label index, validity."""
        sids = anchors["series_id"].astype(str).to_numpy()
        t = anchors["t"].to_numpy(np.int64)
        uniq, inv = np.unique(sids, return_inverse=True)
        meta = np.array([self.index.get(u, (-1, 0, 0, -1)) for u in uniq], dtype=np.int64).reshape(-1, 4)
        off, t0, n, lab = (meta[inv, k] for k in range(4))
        local_end = t - t0 + 1
        valid = (off >= 0) & (local_end - seq >= 0) & (local_end <= n)
        end = np.where(valid, off + local_end, seq)          # dummy index for invalid rows
        valid &= (self.nan_cum[end] - self.nan_cum[end - seq]) == 0
        return end, lab, valid

    def batch(self, ends: np.ndarray, seq: int) -> np.ndarray:
        """Windows [len(ends), seq, 6] for valid ends (vectorised gather; a copy of this batch only)."""
        return self.data[ends[:, None] - seq + np.arange(seq)[None, :]]

    def windows(self, anchors: pd.DataFrame, seq: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Back-compatible: full window array for a SMALL anchor set (used by the backend)."""
        end, lab, valid = self.anchor_ends(anchors, seq)
        X = np.zeros((len(anchors), seq, len(LSTM_INPUTS)), np.float32)
        if valid.any():
            X[valid] = self.batch(end[valid], seq)
        return X, np.where(valid, lab, 0), valid


class LSTMForecaster(nn.Module):
    def __init__(self, n_in: int, n_out: int, n_labels: int, use_label: bool, cfg: Config):
        super().__init__()
        self.use_label = use_label
        self.emb = nn.Embedding(n_labels + 1, 8) if use_label else None
        self.lstm = nn.LSTM(n_in, cfg.lstm_hidden, cfg.lstm_layers, batch_first=True,
                            dropout=cfg.lstm_dropout if cfg.lstm_layers > 1 else 0.0)
        self.head = nn.Sequential(nn.Linear(cfg.lstm_hidden + (8 if use_label else 0), 64), nn.ReLU(),
                                  nn.Linear(64, n_out))

    def forward(self, x, lab=None):
        h, _ = self.lstm(x)
        z = h[:, -1]
        if self.use_label:
            z = torch.cat([z, self.emb(lab + 1)], dim=1)   # index 0 = unknown label
        return self.head(z)


def train_lstm(store: SeriesStore, train: pd.DataFrame, val: pd.DataFrame, cfg: Config,
               use_label: bool, seed: int, device: str) -> dict:
    """Same model, sampling, scaling, loss, optimiser and early-stopping rule as before;
    only memory behaviour differs (no full-size window copies, batched validation)."""
    torch.manual_seed(seed)
    np.random.seed(seed)
    tcols = target_columns(cfg)
    seq = cfg.seq_len_s
    if len(train) > cfg.lstm_max_train_windows:
        train = train.sample(cfg.lstm_max_train_windows, random_state=seed)
    e_tr, l_tr, v_tr = store.anchor_ends(train, seq)
    e_va, l_va, v_va = store.anchor_ends(val, seq)
    Ytr = train[tcols].to_numpy(np.float32)[v_tr]
    Yva = val[tcols].to_numpy(np.float32)[v_va]
    e_tr, l_tr, e_va, l_va = e_tr[v_tr], l_tr[v_tr], e_va[v_va], l_va[v_va]
    Xtr = store.batch(e_tr, seq)                       # <= lstm_max_train_windows windows (one copy)

    # scalers fitted on TRAIN only
    x_mu, x_sd = Xtr.reshape(-1, Xtr.shape[-1]).mean(0), Xtr.reshape(-1, Xtr.shape[-1]).std(0) + 1e-6
    y_mu, y_sd = Ytr.mean(0), Ytr.std(0) + 1e-6
    Xtr -= x_mu
    Xtr /= x_sd

    model = LSTMForecaster(len(LSTM_INPUTS), len(tcols), len(store.labels), use_label, cfg).to(device)
    opt = torch.optim.Adam(model.parameters(), lr=cfg.lstm_lr)
    loss_fn = nn.MSELoss()
    tX, tY, tL = torch.from_numpy(Xtr), torch.from_numpy((Ytr - y_mu) / y_sd), torch.from_numpy(l_tr)

    best, best_state, bad, hist = np.inf, None, 0, []
    t_start = time.time()
    for ep in range(cfg.lstm_epochs):
        model.train()
        perm = torch.randperm(len(tX))   # shuffling of TRAINING windows only; split is chronological
        for i in range(0, len(perm), cfg.lstm_batch):
            b = perm[i:i + cfg.lstm_batch]
            opt.zero_grad(set_to_none=True)
            loss = loss_fn(model(tX[b].to(device), tL[b].to(device)), tY[b].to(device))
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
        pred = _predict_ends(model, store, e_va, l_va, x_mu, x_sd, seq, device) * y_sd + y_mu
        val_mae = float(np.mean(np.abs(pred - Yva) / y_sd))   # scale-free average over 6 outputs
        del pred
        hist.append(dict(epoch=ep, val_mae_scaled=val_mae))
        print(f"    epoch {ep}: val_mae_scaled {val_mae:.4f}")
        if val_mae < best - 1e-5:
            best, bad = val_mae, 0
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
        else:
            bad += 1
            if bad >= cfg.lstm_patience:
                break
    model.load_state_dict(best_state)
    n_tr, n_va = int(len(tX)), int(len(e_va))
    del tX, tY, tL, Xtr, opt
    return dict(model=model, x_mu=x_mu, x_sd=x_sd, y_mu=y_mu, y_sd=y_sd, history=hist,
                seed=seed, use_label=use_label, train_seconds=round(time.time() - t_start, 1),
                n_train_windows=n_tr, n_val_windows=n_va, device=device)


@torch.no_grad()
def _predict_ends(model, store: SeriesStore, ends, labs, x_mu, x_sd, seq, device, batch=8192) -> np.ndarray:
    """Predict in batches; each batch of windows is built, normalised, used and discarded."""
    model.eval()
    out = np.empty((len(ends), len(target_columns(Config()))), np.float32)
    for i in range(0, len(ends), batch):
        X = store.batch(ends[i:i + batch], seq)
        X -= x_mu
        X /= x_sd
        out[i:i + batch] = model(torch.from_numpy(X).to(device),
                                 torch.from_numpy(np.ascontiguousarray(labs[i:i + batch])).to(device)).cpu().numpy()
    return out


def predict_lstm(res: dict, store: SeriesStore, df: pd.DataFrame, cfg: Config) -> tuple[pd.DataFrame, np.ndarray]:
    seq = cfg.seq_len_s
    end, lab, valid = store.anchor_ends(df, seq)
    pred = np.full((len(df), len(target_columns(cfg))), np.nan, np.float32)
    if valid.any():
        dev = res.get("device", "cpu")
        m = res["model"].to(dev)
        pred[valid] = _predict_ends(m, store, end[valid], lab[valid], res["x_mu"], res["x_sd"], seq, dev) \
            * res["y_sd"] + res["y_mu"]
    return pd.DataFrame(pred, index=df.index, columns=target_columns(cfg)), valid


def lstm_latency_ms(res: dict, cfg: Config, calls: int) -> dict:
    """CPU latency, batch = 1 (the backend serves on CPU)."""
    m = res["model"].cpu().eval()
    x = torch.zeros(1, cfg.seq_len_s, len(LSTM_INPUTS))
    lab = torch.zeros(1, dtype=torch.long)
    with torch.no_grad():
        for _ in range(10):
            m(x, lab)
        ts = []
        for _ in range(calls):
            t0 = time.perf_counter()
            m(x, lab)
            ts.append((time.perf_counter() - t0) * 1e3)
    return dict(median_ms=float(np.median(ts)), p95_ms=float(np.percentile(ts, 95)))


def export_onnx(res: dict, cfg: Config, path) -> str | None:
    """ONNX export for the cloud backend (onnxruntime). Inputs: x[1,seq,6] (already scaled), lab[1]."""
    try:
        import onnx  # noqa: F401
    except ImportError:
        return None
    m = res["model"].cpu().eval()
    x = torch.zeros(1, cfg.seq_len_s, len(LSTM_INPUTS))
    lab = torch.zeros(1, dtype=torch.long)
    torch.onnx.export(m, (x, lab), str(path), input_names=["x", "label_idx"], output_names=["delta_scaled"],
                      dynamic_axes={"x": {0: "batch"}, "label_idx": {0: "batch"}, "delta_scaled": {0: "batch"}})
    return str(path)
