"""Read-only access to the public MIT Supercloud S3 bucket (anonymous HTTPS).

Nothing here creates or alters data: files are fetched byte-for-byte, hashed, parsed.
"""
from __future__ import annotations

import hashlib
import io
import re
import time
import urllib.parse
import urllib.request

import pandas as pd

from .config import Config


def _get(url: str, retries: int = 5, timeout: int = 120) -> bytes:
    last = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r:
                return r.read()
        except Exception as e:  # network hiccups: back off and retry
            last = e
            time.sleep(2 ** attempt)
    raise RuntimeError(f"failed to fetch {url}: {last}")


def bucket_and_prefix(cfg: Config) -> tuple[str, str]:
    u = urllib.parse.urlparse(cfg.s3_base)
    return f"{u.scheme}://{u.netloc}/", u.path.lstrip("/")


def list_gpu_files(cfg: Config) -> pd.DataFrame:
    """List every object under gpu/ with its size (S3 ListObjectsV2, paginated)."""
    root, prefix = bucket_and_prefix(cfg)
    rows, token = [], None
    while True:
        q = {"list-type": "2", "prefix": prefix + "gpu/"}
        if token:
            q["continuation-token"] = token
        xml = _get(root + "?" + urllib.parse.urlencode(q)).decode()
        for contents in re.findall(r"<Contents>(.*?)</Contents>", xml, re.S):
            k = re.search(r"<Key>([^<]+)</Key>", contents).group(1)
            s = int(re.search(r"<Size>(\d+)</Size>", contents).group(1))
            rows.append((k, s))
        m = re.search(r"<NextContinuationToken>([^<]+)</NextContinuationToken>", xml)
        if not m:
            break
        token = m.group(1)
    df = pd.DataFrame(rows, columns=["key", "size_bytes"])
    stem = df["key"].str.rsplit("/", n=1).str[1].str.replace(".csv", "", regex=False)
    df["job_id"] = stem.str.split("-").str[0]
    df["file_id"] = stem
    return df


def load_labels(cfg: Config) -> pd.DataFrame:
    """labelled_jobids.csv -> columns job_id, label (original names preserved)."""
    raw = _get(cfg.s3_base + "labelled_jobids.csv")
    df = pd.read_csv(io.BytesIO(raw), dtype={"id_job": str})
    return df.rename(columns={"id_job": "job_id", "model": "label"})


def labelled_file_index(cfg: Config) -> pd.DataFrame:
    """One row per GPU CSV belonging to a labelled job. Cached in work/meta."""
    meta = cfg.paths()["raw_meta"] / "labelled_files.parquet"
    if meta.exists():
        return pd.read_parquet(meta)
    files = list_gpu_files(cfg)
    labels = load_labels(cfg)
    idx = files.merge(labels, on="job_id", how="inner")
    idx.to_parquet(meta, index=False)
    return idx


def fetch_csv(cfg: Config, key: str) -> tuple[pd.DataFrame, str, int]:
    """Download one GPU CSV; return (dataframe, sha256, n_bytes)."""
    root, _ = bucket_and_prefix(cfg)
    raw = _get(root + key)
    sha = hashlib.sha256(raw).hexdigest()
    df = pd.read_csv(io.BytesIO(raw))
    return df, sha, len(raw)
