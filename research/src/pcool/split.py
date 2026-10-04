"""Chronological, job-level train/validation/test split (no shuffling)."""
from __future__ import annotations

import pandas as pd

from .config import Config


def chronological_job_split(audit: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    """Order jobs by first timestamp; earliest 70 % train, next 15 % val, last 15 % test.

    A job is never split across sets, so no window of a test job is seen in training.
    """
    ok = audit[audit["clean_rows"].fillna(0) > 0] if "clean_rows" in audit else audit
    jobs = (ok.groupby("job_id").agg(t_start=("t_start", "min"), t_end=("t_end", "max"), label=("label", "first"))
              .sort_values(["t_start", "job_id"]).reset_index())
    n = len(jobs)
    a, b, _ = cfg.split_fractions
    n_tr, n_va = int(round(a * n)), int(round(b * n))
    jobs["split"] = ["train"] * n_tr + ["val"] * n_va + ["test"] * (n - n_tr - n_va)
    return jobs


def split_report(jobs: pd.DataFrame) -> dict:
    """Coverage numbers reported in the audit; a label missing from test is reported, not fixed."""
    rep = {}
    for sp, d in jobs.groupby("split"):
        rep[sp] = dict(
            jobs=int(len(d)),
            t_first_utc=str(pd.to_datetime(d["t_start"].min(), unit="s")),
            t_last_utc=str(pd.to_datetime(d["t_end"].max(), unit="s")),
            jobs_by_label=d["label"].value_counts().astype(int).to_dict(),
        )
    labels = set(jobs["label"])
    rep["labels_missing_from_test"] = sorted(labels - set(jobs.loc[jobs["split"] == "test", "label"]))
    tr_end = jobs.loc[jobs["split"] == "train", "t_end"].max()
    te_start = jobs.loc[jobs["split"] == "test", "t_start"].min()
    rep["train_jobs_overlapping_test_period"] = int(((jobs["split"] == "train") & (jobs["t_end"] > te_start)).sum())
    rep["note"] = ("Split is by job start time. Long training jobs can still be running when the first "
                   "test job starts; the count above reports how many. Windows never cross jobs.")
    rep["train_last_end_utc"] = str(pd.to_datetime(tr_end, unit="s"))
    return rep
