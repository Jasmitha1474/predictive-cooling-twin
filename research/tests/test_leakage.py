"""Features at time t must not change when the future is altered; windows stay within one series."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from pcool.config import Config  # noqa: E402
from pcool.features import series_features, target_columns  # noqa: E402

COLS = ["utilization_gpu_pct", "utilization_memory_pct", "memory_used_MiB", "memory_free_MiB",
        "temperature_gpu", "temperature_memory", "power_draw_W",
        "clocks_current_sm_MHz", "clocks_current_memory_MHz", "power_limit_W"]


def _series(n=400, seed=0):
    # Test fixture only: arbitrary numbers to exercise the code path. Never used as data.
    r = np.random.default_rng(seed)
    d = pd.DataFrame(r.uniform(1, 100, (n, len(COLS))), columns=COLS)
    d["t"] = np.arange(n)
    d["series_id"], d["job_id"], d["label"] = "s", "j", "vgg16"
    return d


def test_features_do_not_use_future():
    cfg = Config()
    a = _series()
    b = a.copy()
    cut = 250
    b.loc[cut + 1:, COLS] = b.loc[cut + 1:, COLS] * 3 + 7      # change only the future
    fa, fb = series_features(a, cfg), series_features(b, cfg)
    feats = [c for c in fa.columns if not c.startswith(("y_", "d_")) and fa[c].dtype != object
             and c not in ("family",)]
    pd.testing.assert_frame_equal(fa.loc[:cut, feats], fb.loc[:cut, feats])


def test_targets_are_future_values():
    cfg = Config()
    a = _series()
    f = series_features(a, cfg)
    for h in cfg.horizons_s:
        assert np.allclose(f[f"y_power_{h}"].iloc[:-h], a["power_draw_W"].iloc[h:].to_numpy())
        assert f[f"y_power_{h}"].iloc[-h:].isna().all()       # no target beyond series end
    assert set(target_columns(cfg)) <= set(f.columns)


def test_slope_matches_polyfit():
    from pcool.features import _trailing_slope
    y = np.r_[np.zeros(5), np.arange(30) * 0.5 + 3]
    s = _trailing_slope(y, 10)
    assert np.isclose(s[-1], np.polyfit(np.arange(10), y[-10:], 1)[0])
