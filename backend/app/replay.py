"""Replay pack: a SMALL set of real test-split traces the backend streams (brief section 37).

The backend never loads the training dataset. The pack holds only the columns needed
for replay and forecasting, for a few dozen series.

Build (in Colab or wherever research/work exists):
  python -m app.replay --clean-dir ../research/work/clean \
      --split-jobs ../research/work/reports/split_jobs.csv --split test --n 40 \
      --out data/replay_pack.parquet

Licence: MIT Supercloud data is CC BY-NC-ND 4.0. A replay pack is resampled (modified)
data, so keep it private (it is git-ignored); do not publish it.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

COLUMNS = ["series_id", "job_id", "file_id", "gpu_index", "label", "t",
           "utilization_gpu_pct", "utilization_memory_pct", "memory_used_MiB", "memory_free_MiB",
           "temperature_gpu", "temperature_memory", "power_draw_W",
           "clocks_current_sm_MHz", "clocks_current_memory_MHz", "power_limit_W"]


def build(clean_dir: Path, split_jobs: Path | None, split: str | None, n: int, min_seconds: int) -> pd.DataFrame:
    clean = pd.read_parquet(clean_dir, columns=COLUMNS)
    if split_jobs is not None and split:
        jobs = pd.read_csv(split_jobs, dtype={"job_id": str})
        clean = clean[clean["job_id"].isin(set(jobs.loc[jobs["split"] == split, "job_id"]))]
    lens = clean.groupby("series_id").size()
    ok = clean[clean["series_id"].isin(lens[lens >= min_seconds].index)]
    # round-robin over labels so the pack covers as many dataset labels as possible
    per = ok.groupby("series_id")["label"].first().reset_index().sort_values(["label", "series_id"])
    per["rank"] = per.groupby("label").cumcount()
    chosen = per.sort_values(["rank", "label"]).head(n)["series_id"]
    return ok[ok["series_id"].isin(set(chosen))].sort_values(["series_id", "t"]).reset_index(drop=True)


def build_from_s3(jobs_file: Path, out: Path, min_seconds: int = 600) -> Path:
    """Download the listed PUBLIC MIT Supercloud files (unmodified, anonymous HTTPS), clean them in
    memory with the research preprocessing code, and cache the result locally. Used by deployments
    so that no dataset files have to be shipped with the app."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "research" / "src"))
    from pcool.config import Config
    from pcool.data_access import fetch_csv
    from pcool.preprocess import clean_file

    spec = json.loads(Path(jobs_file).read_text())
    cfg = Config(work_dir=str(out.parent / "_pcool_tmp"))
    parts = []
    for f in spec["files"]:
        raw, _, _ = fetch_csv(cfg, f["key"])
        clean, _ = clean_file(raw, f["file_id"], f["job_id"], f["label"], cfg)
        if clean is not None:
            parts.append(clean)
    df = pd.concat(parts, ignore_index=True)
    lens = df.groupby("series_id").size()
    df = df[df["series_id"].isin(lens[lens >= min_seconds].index)][COLUMNS]
    out.parent.mkdir(parents=True, exist_ok=True)
    df.sort_values(["series_id", "t"]).to_parquet(out, index=False)
    out.with_suffix(".json").write_text(json.dumps(dict(
        source=spec["source"], citation="S. Samsi et al., IEEE HPEC 2021, doi:10.1109/HPEC49654.2021.9622850",
        note="Built at startup from public S3 files listed in backend/replay_jobs.json (13 small labelled jobs; development demo set).",
        n_series=int(df["series_id"].nunique()), n_seconds=int(len(df)), labels=sorted(df["label"].unique().tolist())), indent=2))
    return out


class ReplayPack:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.df = pd.read_parquet(self.path)
        meta = self.path.with_suffix(".json")
        self.meta = json.loads(meta.read_text()) if meta.exists() else {}
        self.series = {sid: d.reset_index(drop=True) for sid, d in self.df.groupby("series_id", sort=True)}

    def index(self) -> list[dict]:
        return [dict(series_id=sid, job_id=str(d["job_id"].iloc[0]), label=str(d["label"].iloc[0]),
                     gpu_index=int(d["gpu_index"].iloc[0]), duration_s=int(len(d)),
                     has_clocks=bool(d["clocks_current_sm_MHz"].notna().any()))
                for sid, d in self.series.items()]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--clean-dir", type=Path, required=True)
    ap.add_argument("--split-jobs", type=Path)
    ap.add_argument("--split", default="test")
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--min-seconds", type=int, default=600)
    ap.add_argument("--out", type=Path, default=Path("data/replay_pack.parquet"))
    ap.add_argument("--note", default="")
    a = ap.parse_args(argv)
    pack = build(a.clean_dir, a.split_jobs, a.split if a.split_jobs else None, a.n, a.min_seconds)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    pack.to_parquet(a.out, index=False)
    meta = dict(source="MIT Supercloud Dataset, datacenter-challenge/202201 (CC BY-NC-ND 4.0)",
                citation="S. Samsi et al., IEEE HPEC 2021, doi:10.1109/HPEC49654.2021.9622850",
                split=a.split if a.split_jobs else "all (no split file given)", note=a.note,
                n_series=int(pack["series_id"].nunique()), n_seconds=int(len(pack)),
                labels=sorted(pack["label"].unique().tolist()))
    a.out.with_suffix(".json").write_text(json.dumps(meta, indent=2))
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
