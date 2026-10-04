"""Baselines (B0 persistence, B1 utilization-only) and LightGBM models (A0, A1).

One LightGBM model per (target, horizon). Each predicts the CHANGE of the target;
levels are reconstructed as current value + predicted change.

Memory design (Colab, 12.7 GB RAM): feature matrices are read from Parquet only for the
columns a model needs, as float32, one split at a time; LightGBM bins the training matrix
ONCE per model and the same binned Dataset is reused for all six targets (only the label
changes). Every fitted booster is saved immediately, so a disconnected run resumes.
"""
from __future__ import annotations

import gc
import json
import time
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

from .config import Config
from .features import feature_columns, target_columns

# model id -> feature set (docs/methodology.md §7)
GBM_MODELS = {
    "B1_util_only": "util_only",
    "A0_lgbm_noclock": "full_noclock",
    "A1_lgbm_noclock_label": "full_noclock_label",
    "A2_lgbm_clock_label": "full_clock_label",   # clock ablation only (jobs with clock columns)
}
MAIN_GBM = ["B1_util_only", "A0_lgbm_noclock", "A1_lgbm_noclock_label"]
CATEGORICAL = ("label", "family")


def lgb_params(cfg: Config) -> dict:
    """cfg.lgbm_params (sklearn names) translated to native LightGBM names; same values."""
    p = dict(cfg.lgbm_params)
    return dict(
        objective="regression", metric="l1", seed=cfg.seed,
        learning_rate=p["learning_rate"], num_leaves=p["num_leaves"],
        min_data_in_leaf=p["min_child_samples"], bagging_fraction=p["subsample"],
        bagging_freq=p["subsample_freq"], feature_fraction=p["colsample_bytree"],
        lambda_l2=p["reg_lambda"], num_threads=0 if p.get("n_jobs", -1) == -1 else p["n_jobs"],
        verbosity=-1,
    )


def to_matrix(df: pd.DataFrame, cols: list[str], categories: dict) -> np.ndarray:
    """float32 matrix in column order `cols`; categorical columns become codes of the TRAIN categories
    (unseen category -> NaN, which LightGBM treats as missing)."""
    X = np.empty((len(df), len(cols)), np.float32)
    for j, c in enumerate(cols):
        if c in CATEGORICAL:
            codes = pd.Categorical(df[c].astype(str), categories=categories[c]).codes.astype(np.float32)
            codes[codes < 0] = np.nan
            X[:, j] = codes
        else:
            X[:, j] = df[c].to_numpy(np.float32, na_value=np.nan)
    return X


def persistence(df: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    """B0: future value = current value, i.e. predicted change = 0."""
    return pd.DataFrame(0.0, index=df.index, columns=target_columns(cfg), dtype=np.float32)


def train_gbm(model_id: str, load_split, cfg: Config, out_dir: Path, all_columns: list[str],
              row_filter=None) -> dict:
    """Train the six (target, horizon) boosters of one model.

    load_split(split, columns, row_filter) -> DataFrame   (reads Parquet, float32)
    """
    kind = GBM_MODELS[model_id]
    cols = feature_columns(pd.DataFrame(columns=all_columns), kind)
    mdir = out_dir / model_id
    mdir.mkdir(parents=True, exist_ok=True)
    info_path = mdir / "info.json"
    tcols = target_columns(cfg)
    info = json.loads(info_path.read_text()) if info_path.exists() else None
    if info and all((mdir / f"{t}.txt").exists() for t in tcols) and info.get("complete"):
        print(f"  {model_id}: all boosters already on disk, loading (resume)")
        info["_models"] = {t: lgb.Booster(model_file=str(mdir / f"{t}.txt")) for t in tcols}
        return info

    need_cat = [c for c in CATEGORICAL if c in cols]
    tr = load_split("train", cols + tcols, row_filter)
    categories = {c: sorted(tr[c].astype(str).unique()) for c in need_cat}
    Ytr = {t: tr[t].to_numpy(np.float32) for t in tcols}
    Xtr = to_matrix(tr, cols, categories)
    del tr
    gc.collect()
    va = load_split("val", cols + tcols, row_filter)
    Yva = {t: va[t].to_numpy(np.float32) for t in tcols}
    Xva = to_matrix(va, cols, categories)
    del va
    gc.collect()

    params = lgb_params(cfg)
    cat_idx = [cols.index(c) for c in need_cat]
    dtr = lgb.Dataset(Xtr, label=Ytr[tcols[0]], feature_name=cols, categorical_feature=cat_idx,
                      free_raw_data=True, params=params)
    dva = lgb.Dataset(Xva, label=Yva[tcols[0]], reference=dtr, feature_name=cols, categorical_feature=cat_idx,
                      free_raw_data=True, params=params)
    dtr.construct()
    dva.construct()
    del Xtr, Xva
    gc.collect()

    info = info or {"model_id": model_id, "features": cols, "categories": categories, "per_target": {},
                    "n_train_rows": int(dtr.num_data()), "n_val_rows": int(dva.num_data())}
    boosters = {}
    for tgt in tcols:
        path = mdir / f"{tgt}.txt"
        if path.exists() and tgt in info["per_target"]:
            print(f"  {model_id} {tgt}: on disk, loading (resume)")
            boosters[tgt] = lgb.Booster(model_file=str(path))
            continue
        t0 = time.time()
        dtr.set_label(Ytr[tgt])
        dva.set_label(Yva[tgt])
        b = lgb.train(params, dtr, num_boost_round=cfg.lgbm_params["n_estimators"], valid_sets=[dva],
                      valid_names=["val"],
                      callbacks=[lgb.early_stopping(cfg.lgbm_early_stopping_rounds, verbose=False)])
        b.save_model(str(path), num_iteration=b.best_iteration)
        boosters[tgt] = lgb.Booster(model_file=str(path))
        info["per_target"][tgt] = dict(best_iteration=int(b.best_iteration or 0),
                                       train_seconds=round(time.time() - t0, 1),
                                       file=str(path), file_bytes=path.stat().st_size)
        info_path.write_text(json.dumps(info, indent=1))      # checkpoint after every booster
        print(f"  {model_id} {tgt}: best_iteration {b.best_iteration}, {time.time() - t0:.0f}s")
        del b
        gc.collect()
    info["complete"] = True
    info_path.write_text(json.dumps(info, indent=1))
    del dtr, dva
    gc.collect()
    info["_models"] = boosters
    return info


def predict_gbm(info: dict, df: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    X = to_matrix(df, info["features"], info["categories"])
    out = pd.DataFrame({t: info["_models"][t].predict(X).astype(np.float32) for t in target_columns(cfg)},
                       index=df.index)
    del X
    return out


def gbm_latency_ms(info: dict, df: pd.DataFrame, cfg: Config, calls: int) -> dict:
    """Latency of producing ALL 6 forecasts for one row (batch = 1), on this CPU."""
    X = to_matrix(df.iloc[:1], info["features"], info["categories"])
    for _ in range(10):
        [m.predict(X) for m in info["_models"].values()]
    ts = []
    for _ in range(calls):
        t0 = time.perf_counter()
        [m.predict(X) for m in info["_models"].values()]
        ts.append((time.perf_counter() - t0) * 1e3)
    return dict(median_ms=float(np.median(ts)), p95_ms=float(np.percentile(ts, 95)))
