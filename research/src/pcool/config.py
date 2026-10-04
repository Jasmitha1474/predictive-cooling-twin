"""Single source of truth for every pipeline setting.

Every value here is written into the experiment manifest, so a result can always be
traced back to the configuration that produced it.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Config:
    # ---- data source (MIT Supercloud, labelled subset) ----
    dataset_name: str = "MIT Supercloud Dataset (labelled subset)"
    dataset_version: str = "datacenter-challenge/202201"
    s3_base: str = "https://mit-supercloud-dataset.s3.amazonaws.com/datacenter-challenge/202201/"
    citation: str = (
        "S. Samsi et al., 'The MIT Supercloud Dataset,' IEEE HPEC 2021, "
        "doi:10.1109/HPEC49654.2021.9622850"
    )
    license: str = "CC BY-NC-ND 4.0"

    # ---- working directories (Colab: point these at Google Drive) ----
    work_dir: str = "./work"

    # ---- preprocessing ----
    grid_seconds: float = 1.0          # resample grid
    max_gap_seconds: float = 2.0       # larger gaps split a series into segments
    ffill_limit_seconds: int = 2       # forward-fill only slow fields, only this far
    max_temp_c: float = 110.0          # impossible-value bounds
    min_temp_c: float = 0.0
    power_limit_factor: float = 1.10   # power > factor * power_limit_W is impossible
    fallback_power_cap_w: float = 400.0  # used when power_limit_W column is absent
    min_segment_seconds: int = 180     # shorter segments are dropped

    # ---- forecasting ----
    horizons_s: tuple = (30, 45, 60)
    targets: tuple = ("power_draw_W", "temperature_gpu")
    roll_windows_s: tuple = (10, 30, 60)
    lags_s: tuple = (1, 5, 10, 30)
    seq_len_s: int = 60                # LSTM input length

    # ---- splitting (chronological, job level) ----
    split_fractions: tuple = (0.70, 0.15, 0.15)

    # ---- sampling of windows (memory control; documented in methodology) ----
    train_stride_s: int = 5
    eval_stride_s: int = 5

    # ---- models ----
    seed: int = 42
    lgbm_params: dict = field(default_factory=lambda: dict(
        n_estimators=2000, learning_rate=0.05, num_leaves=63, min_child_samples=200,
        subsample=0.8, subsample_freq=1, colsample_bytree=0.8, reg_lambda=1.0,
        n_jobs=-1, verbose=-1,
    ))
    lgbm_early_stopping_rounds: int = 100
    lstm_hidden: int = 64
    lstm_layers: int = 2
    lstm_dropout: float = 0.1
    lstm_epochs: int = 20
    lstm_batch: int = 1024
    lstm_lr: float = 1e-3
    lstm_patience: int = 3
    lstm_seeds: tuple = (0, 1, 2, 3, 4)
    lstm_max_train_windows: int = 800_000   # RAM cap on Colab; random subset of TRAIN windows only

    # ---- evaluation ----
    min_series_per_label: int = 20
    bootstrap_resamples: int = 10_000
    latency_calls: int = 1000

    # ---- optional limits (smoke tests only; None = all jobs) ----
    max_jobs: int | None = None

    def paths(self) -> dict:
        w = Path(self.work_dir)
        p = dict(
            work=w,
            raw_meta=w / "meta",
            clean=w / "clean",          # one parquet per job, 1 s grid
            features=w / "features",
            reports=w / "reports",
            models=w / "models",
        )
        for v in p.values():
            v.mkdir(parents=True, exist_ok=True)
        return p

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    def hash(self) -> str:
        return hashlib.sha256(json.dumps(self.to_dict(), sort_keys=True, default=str).encode()).hexdigest()[:16]
