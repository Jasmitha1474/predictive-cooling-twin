"""End-to-end research pipeline. Run in Colab (see research/notebooks), not on a laptop.

Stages are resumable and write everything they produce under cfg.work_dir:
  preprocess -> split -> features -> train_evaluate (+ export + manifest)
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import os
import platform
import subprocess
import sys
import time
from importlib import metadata
from pathlib import Path

import numpy as np
import pandas as pd

from . import evaluate, models_gbm, preprocess, split
from .config import Config
from .features import build_file_features, target_columns


def _dump(obj, path: Path):
    path.write_text(json.dumps(obj, indent=2, default=lambda o: o.item() if hasattr(o, "item") else str(o)))


# ---------------------------------------------------------------- stages
def stage_preprocess(cfg: Config, workers: int = 8) -> dict:
    audit = preprocess.run(cfg, workers=workers)
    summary = preprocess.summarize_audit(audit)
    _dump(summary, cfg.paths()["reports"] / "audit_summary.json")
    return summary


def stage_split(cfg: Config) -> dict:
    p = cfg.paths()
    jobs = split.chronological_job_split(preprocess.load_audit(cfg), cfg)
    jobs.to_csv(p["reports"] / "split_jobs.csv", index=False)
    rep = split.split_report(jobs)
    _dump(rep, p["reports"] / "split_report.json")
    return rep


def _features_one(args):
    path, split_of_job, cfg_dict, out_dir = args
    cfg = Config(**cfg_dict)
    out = Path(out_dir) / path.name
    if out.exists():
        return 0
    f = build_file_features(pd.read_parquet(path), split_of_job, cfg)
    if len(f):
        f.to_parquet(out, index=False)
    return len(f)


def stage_features(cfg: Config, workers: int = os.cpu_count() or 2) -> int:
    p = cfg.paths()
    jobs = pd.read_csv(p["reports"] / "split_jobs.csv", dtype={"job_id": str})
    split_of_job = dict(zip(jobs["job_id"], jobs["split"]))
    files = sorted(p["clean"].glob("*.parquet"))
    args = [(f, split_of_job, cfg.to_dict(), str(p["features"])) for f in files]
    n = 0
    with cf.ProcessPoolExecutor(workers) as ex:
        for i, k in enumerate(ex.map(_features_one, args, chunksize=8), 1):
            n += k
            if i % 500 == 0:
                print(f"features: {i}/{len(files)} files")
    return n


def load_features(cfg: Config) -> pd.DataFrame:
    """Whole feature table in RAM (all splits, float64). Too large for Colab on the full dataset;
    kept only for small local checks. The training stage uses make_loader() instead."""
    df = pd.read_parquet(cfg.paths()["features"])
    for c in ("series_id", "job_id", "label", "family", "split"):
        df[c] = df[c].astype("category")
    return df


def load_clean_for_lstm(cfg: Config) -> pd.DataFrame:
    from . import lstm  # torch imported lazily: on macOS torch + LightGBM OpenMP runtimes can clash
    cols = ["series_id", "job_id", "label", "t"] + lstm.LSTM_INPUTS
    return pd.read_parquet(cfg.paths()["clean"], columns=cols)


# ---------------------------------------------------------------- memory-safe data access
META_COLS = ["series_id", "job_id", "label", "family", "t", "power_draw_W", "temperature_gpu"]
STR_COLS = ("series_id", "job_id", "label", "family", "split")


def rss_gb() -> float:
    try:
        import psutil
        return psutil.Process().memory_info().rss / 1e9
    except Exception:
        return float("nan")


def mem(tag: str):
    print(f"[mem] {tag}: process RSS {rss_gb():.2f} GB", flush=True)


def make_loader(cfg: Config):
    """Return (load_split, all_columns). load_split(split, columns, row_filter=None) reads ONLY the
    requested columns of ONLY one split from the feature Parquet files, strings as categories,
    floats as float32. Row order is deterministic (file order, then row order)."""
    import pyarrow.dataset as pads
    dset = pads.dataset(str(cfg.paths()["features"]), format="parquet")
    all_columns = dset.schema.names

    def load_split(split: str, columns: list[str], row_filter=None) -> pd.DataFrame:
        cols = list(dict.fromkeys(["series_id", "t"] + list(columns)))
        flt = pads.field("split") == split
        if row_filter is not None:
            flt = flt & row_filter
        tab = dset.to_table(columns=cols, filter=flt, use_threads=False)
        for i, name in enumerate(tab.column_names):
            if name in STR_COLS:
                tab = tab.set_column(i, name, tab.column(name).dictionary_encode())
        df = tab.to_pandas()
        del tab
        for c in df.columns:
            if df[c].dtype == np.float64:
                df[c] = df[c].astype(np.float32)
        return df

    return load_split, all_columns


def _same_rows(a: pd.DataFrame, b: pd.DataFrame):
    assert len(a) == len(b) and np.array_equal(a["t"].to_numpy(), b["t"].to_numpy()) and \
        (a["series_id"].astype(str).to_numpy() == b["series_id"].astype(str).to_numpy()).all(), \
        "row order differs between reads of the same split"


def size_report(cfg: Config) -> dict:
    """Row counts per split and clean-series size, read from Parquet metadata / one small column.
    Run this BEFORE training to see what has to fit in RAM."""
    import pyarrow.dataset as pads
    import pyarrow.parquet as pq
    p = cfg.paths()
    dset = pads.dataset(str(p["features"]), format="parquet")
    sp = dset.to_table(columns=["split"]).column("split").to_pandas().value_counts().to_dict()
    clean_rows = sum(pq.ParquetFile(f).metadata.num_rows for f in p["clean"].glob("*.parquet"))
    ncol = len(dset.schema.names)
    rep = dict(feature_rows_by_split={k: int(v) for k, v in sp.items()}, feature_columns=ncol,
               clean_rows=int(clean_rows),
               est_gb_old_load_features_float64=round(sum(sp.values()) * ncol * 8 / 1e9, 2),
               est_gb_lstm_store_float32=round(clean_rows * 6 * 4 / 1e9, 2),
               est_gb_largest_gbm_train_matrix_float32=round(sp.get("train", 0) * 56 * 4 / 1e9, 2))
    return rep


# ---------------------------------------------------------------- training + evaluation
def stage_train_evaluate(cfg: Config, device: str = "cpu", run_lstm: bool = True) -> dict:
    """Same models, seeds, data and metrics as designed; memory-safe and resumable:
    - feature columns are read per model and per split (float32), never the whole table;
    - LightGBM bins each training matrix once and reuses it for the 6 targets;
    - LSTM windows are built batch by batch from one float32 store of the clean series;
    - every booster / LSTM seed is written to disk as soon as it is trained (resume)."""
    import gc
    p = cfg.paths()
    t_all = time.time()
    load_split, all_cols = make_loader(cfg)
    tcols = target_columns(cfg)
    ycols = [c.replace("d_", "y_", 1) for c in tcols]
    mem("start")
    tr = load_split("train", ["label"] + tcols)                     # small: ids + targets only
    va = load_split("val", META_COLS + tcols + ycols)
    te = load_split("test", META_COLS + tcols + ycols)
    print(f"windows: train {len(tr):,}  val {len(va):,}  test {len(te):,}", flush=True)
    mem("meta loaded")
    results = dict(models={}, val={}, note="All values computed by pcool.pipeline on the test split. "
                                          "Do not edit by hand.")

    preds_te, preds_va, infos = {}, {}, {}
    preds_te["B0_persistence"] = models_gbm.persistence(te, cfg)
    preds_va["B0_persistence"] = models_gbm.persistence(va, cfg)

    for mid in models_gbm.MAIN_GBM:
        print("training", mid, flush=True)
        info = models_gbm.train_gbm(mid, load_split, cfg, p["models"], all_cols)
        infos[mid] = info
        mem(f"{mid} trained")
        for split, meta, store_preds in (("val", va, preds_va), ("test", te, preds_te)):
            X = load_split(split, info["features"])
            _same_rows(meta, X)
            store_preds[mid] = models_gbm.predict_gbm(info, X, cfg)
            if split == "test":
                info["_latency"] = models_gbm.gbm_latency_ms(info, X, cfg, cfg.latency_calls)
            del X
            gc.collect()
        mem(f"{mid} predicted")

    # ---- LSTM (L0 without label, L1 with label), several seeds, one at a time, checkpointed
    lstm_summ = {}
    valid_te = np.ones(len(te), bool)
    if run_lstm:
        import torch
        from . import lstm
        labels = sorted(tr["label"].astype(str).unique())
        store = lstm.SeriesStore.from_parquet_dir(p["clean"], labels)
        mem(f"LSTM store built ({store.data.shape[0]:,} s x 6, {store.data.nbytes / 1e9:.2f} GB)")
        _, _, valid_te = store.anchor_ends(te, cfg.seq_len_s)
        for mid, use_label in (("L0_lstm", False), ("L1_lstm_label", True)):
            seeds = []
            for seed in cfg.lstm_seeds:
                sdir = p["models"] / mid / f"seed{seed}"
                sdir.mkdir(parents=True, exist_ok=True)
                done = sdir / "done.json"
                if done.exists():
                    print("  ", mid, "seed", seed, "already done (resume)", flush=True)
                    seeds.append(json.loads(done.read_text()))
                    continue
                print("training", mid, "seed", seed, flush=True)
                r = lstm.train_lstm(store, tr, va, cfg, use_label, seed, device)
                pva, _ = lstm.predict_lstm(r, store, va, cfg)
                ok = ~pva.isna().any(axis=1).to_numpy()
                val_score = evaluate.score(va[ok], pva[ok], cfg)
                del pva
                pte, _ = lstm.predict_lstm(r, store, te, cfg)
                np.save(sdir / "test_pred.npy", pte.to_numpy(np.float32))
                del pte
                r["model"].cpu()
                torch.save(dict(state_dict=r["model"].state_dict(), x_mu=r["x_mu"], x_sd=r["x_sd"],
                                y_mu=r["y_mu"], y_sd=r["y_sd"], use_label=use_label, labels=store.labels,
                                inputs=lstm.LSTM_INPUTS, cfg=cfg.to_dict()), sdir / "model.pt")
                rec = dict(seed=seed, val=val_score, history=r["history"], train_seconds=r["train_seconds"],
                           n_train_windows=r["n_train_windows"], n_val_windows=r["n_val_windows"])
                done.write_text(json.dumps(rec, default=float))
                seeds.append(rec)
                del r
                gc.collect()
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                mem(f"{mid} seed {seed} saved")
            lstm_summ[mid] = seeds

    # ---- common test set: rows every model can score
    common = valid_te
    results["test_set"] = dict(rows_total=int(len(te)), rows_common=int(common.sum()),
                               jobs=int(te.loc[common, "job_id"].nunique()),
                               series=int(te.loc[common, "series_id"].nunique()))
    te_c = te[common]

    for mid, pr in preds_te.items():
        results["models"][mid] = dict(test=evaluate.score(te_c, pr[common], cfg))
        results["val"][mid] = evaluate.score(va, preds_va[mid], cfg)
    for mid, info in infos.items():
        results["models"][mid].update(
            latency=info["_latency"],
            size_bytes=int(sum(v["file_bytes"] for v in info["per_target"].values())),
            train_info={k: v for k, v in info.items() if not k.startswith("_")},
            test_full_set=evaluate.score(te, preds_te[mid], cfg))

    for mid, seeds in lstm_summ.items():
        import torch
        from . import lstm
        per_seed = []
        for rec in seeds:
            pte = pd.DataFrame(np.load(p["models"] / mid / f"seed{rec['seed']}" / "test_pred.npy"),
                               index=te.index, columns=tcols)
            per_seed.append(evaluate.score(te_c, pte[common], cfg))
            del pte
        val_seed = [rec["val"] for rec in seeds]
        best = int(np.argmin([[r["mae"] for r in v if r["group"] == "ALL" and r["horizon_s"] == 30][0]
                              for v in val_seed]))
        bseed = seeds[best]["seed"]
        ck = torch.load(p["models"] / mid / f"seed{bseed}" / "model.pt", map_location="cpu", weights_only=False)
        model = lstm.LSTMForecaster(len(lstm.LSTM_INPUTS), len(tcols), len(ck["labels"]), ck["use_label"], cfg)
        model.load_state_dict(ck["state_dict"])
        r_best = dict(model=model, x_mu=ck["x_mu"], x_sd=ck["x_sd"], y_mu=ck["y_mu"], y_sd=ck["y_sd"])
        path = p["models"] / mid / "model.pt"
        torch.save(ck, path)                                     # exported = best-validation seed
        onnx_path = lstm.export_onnx(r_best, cfg, path.with_suffix(".onnx"))
        pte_best = pd.DataFrame(np.load(p["models"] / mid / f"seed{bseed}" / "test_pred.npy"),
                                index=te.index, columns=tcols)
        results["models"][mid] = dict(
            test=evaluate.score(te_c, pte_best[common], cfg),
            test_by_seed=per_seed,
            seeds=list(cfg.lstm_seeds), selected_seed=int(bseed),
            latency=lstm.lstm_latency_ms(r_best, cfg, cfg.latency_calls),
            size_bytes=int(path.stat().st_size),
            onnx=str(onnx_path) if onnx_path else "not exported (onnx not installed)",
            train_info=[dict(seed=s["seed"], history=s["history"], train_seconds=s["train_seconds"],
                             n_train_windows=s["n_train_windows"]) for s in seeds])
        results["val"][mid] = val_seed[best]
        preds_te[mid] = pte_best

    # ---- seed spread for LSTMs (mean ± std of test MAE)
    for mid in lstm_summ:
        spread = {}
        for rows in results["models"][mid]["test_by_seed"]:
            for r in rows:
                if r["group"] == "ALL":
                    spread.setdefault(f"{r['target']}_{r['horizon_s']}", []).append(r["mae"])
        results["models"][mid]["test_mae_seed_mean_std"] = {k: [float(np.mean(v)), float(np.std(v))]
                                                            for k, v in spread.items()}

    # ---- significance vs baselines (paired bootstrap over test jobs)
    results["bootstrap_vs_B0"], results["bootstrap_vs_B1"] = {}, {}
    for mid, pr in preds_te.items():
        if mid == "B0_persistence":
            continue
        results["bootstrap_vs_B0"][mid] = evaluate.paired_bootstrap_mae_diff(
            te_c, pr[common], preds_te["B0_persistence"][common], cfg)
        if mid != "B1_util_only":
            results["bootstrap_vs_B1"][mid] = evaluate.paired_bootstrap_mae_diff(
                te_c, pr[common], preds_te["B1_util_only"][common], cfg)

    # ---- selection rule (docs/methodology.md §7): lowest VALIDATION MAE at 30 s, per target
    sel = {}
    for tgt in ("power", "temp"):
        scores = {m: [r["mae"] for r in v if r["group"] == "ALL" and r["target"] == tgt and r["horizon_s"] == 30][0]
                  for m, v in results["val"].items()}
        sel[tgt] = dict(selected=min(scores, key=scores.get), val_mae_30s=scores)
    results["selection"] = sel

    del tr
    gc.collect()
    results["clock_ablation"] = clock_ablation(load_split, all_cols, cfg)
    results["runtime_seconds"] = round(time.time() - t_all, 1)
    results["peak_note"] = f"process RSS at end {rss_gb():.2f} GB"
    _dump(results, p["reports"] / "results.json")
    flat_results(results).to_csv(p["reports"] / "results_table.csv", index=False)
    write_manifest(cfg)
    mem("done")
    return results


def clock_ablation(load_split, all_cols, cfg: Config) -> dict:
    """A1 with vs without clock features, trained and tested only on jobs that HAVE clocks."""
    import pyarrow.dataset as pads
    has = pads.field("clocks_current_sm_MHz").is_valid()
    tcols = target_columns(cfg)
    ycols = [c.replace("d_", "y_", 1) for c in tcols]
    n = {s: len(load_split(s, [], has)) for s in ("train", "val")}
    tec = load_split("test", META_COLS + tcols + ycols, has)
    rep = dict(train_rows=n["train"], val_rows=n["val"], test_rows=len(tec),
               test_jobs=int(tec["job_id"].nunique()) if len(tec) else 0)
    if n["train"] < 10_000 or n["val"] < 1_000 or rep["test_jobs"] < 5:
        rep["status"] = "not run: too few jobs with clock columns in one of the splits"
        return rep
    out = {}
    out_dir = cfg.paths()["models"] / "clock_ablation"
    for mid in ("A1_lgbm_noclock_label", "A2_lgbm_clock_label"):
        info = models_gbm.train_gbm(mid, load_split, cfg, out_dir, all_cols, row_filter=has)
        X = load_split("test", info["features"], has)
        _same_rows(tec, X)
        out[mid] = evaluate.score(tec, models_gbm.predict_gbm(info, X, cfg), cfg)
    rep.update(status="run", results=out)
    return rep


def flat_results(results: dict) -> pd.DataFrame:
    rows = []
    for mid, m in results["models"].items():
        for r in m["test"]:
            rows.append(dict(model=mid, **r))
    return pd.DataFrame(rows)


def write_manifest(cfg: Config):
    p = cfg.paths()
    audit = preprocess.load_audit(cfg)
    pkgs = {}
    for name in ("pandas", "numpy", "pyarrow", "lightgbm", "scikit-learn", "torch", "onnx", "onnxruntime"):
        try:
            pkgs[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            pkgs[name] = None
    try:
        top = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True,
                             cwd=Path(__file__).parent).stdout.strip()
        # only record a commit if the repository is this project (not an enclosing home-directory repo)
        project = Path(__file__).resolve().parents[3]
        commit = (subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                                 cwd=Path(__file__).parent).stdout.strip() or None) if top and Path(top).resolve() == project else None
    except Exception:
        commit = None
    gpu = None
    try:
        import torch
        gpu = torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
    except Exception:
        pass
    manifest = dict(
        dataset=dict(name=cfg.dataset_name, version=cfg.dataset_version, source=cfg.s3_base,
                     citation=cfg.citation, license=cfg.license),
        raw_file_sha256=dict(zip(audit["key"], audit.get("sha256", pd.Series([None] * len(audit))))),
        config=cfg.to_dict(), config_hash=cfg.hash(),
        split_jobs_file="reports/split_jobs.csv",
        environment=dict(python=sys.version, platform=platform.platform(), packages=pkgs, gpu=gpu),
        code_commit=commit, created_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        target_columns=target_columns(cfg),
    )
    _dump(manifest, p["models"] / "manifest.json")
    return manifest


def run_all(cfg: Config, device: str = "cpu", run_lstm: bool = True):
    print(stage_preprocess(cfg))
    print(stage_split(cfg))
    print("feature rows:", stage_features(cfg))
    return stage_train_evaluate(cfg, device=device, run_lstm=run_lstm)
