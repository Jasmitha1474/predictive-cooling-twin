"""Power forecasters for the predictive controller.

A forecaster turns one REAL telemetry trace (1 s grid, columns as produced by
research/src/pcool/preprocess.py) into PREDICTED power at +30/+45/+60 s for every
second. Forecasts use only measured telemetry up to t, never the simulated twin state,
so they can be computed once per trace (the trace does not react to our valve).

  PersistenceForecaster : P(t+h) = P(t)                     (no ML; lower reference)
  OracleForecaster      : true future measured power         (upper bound; not deployable)
  LightGBMForecaster    : exported A0/A1 models (research/work/models/<id>/d_power_<h>.txt)
  LSTMForecaster        : exported L0/L1 model.pt
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HORIZONS = (30, 45, 60)
_RESEARCH_SRC = Path(__file__).resolve().parents[2] / "research" / "src"


def _pcool():
    if str(_RESEARCH_SRC) not in sys.path:
        sys.path.insert(0, str(_RESEARCH_SRC))
    import pcool  # noqa: F401
    return pcool


class PersistenceForecaster:
    name = "persistence"

    def forecast(self, s: pd.DataFrame) -> np.ndarray:
        P = s["power_draw_W"].ffill().to_numpy(float)
        return np.repeat(P[:, None], len(HORIZONS), axis=1)

    def forecast_temperature(self, s: pd.DataFrame):
        return None


class OracleForecaster:
    name = "oracle"

    def forecast(self, s: pd.DataFrame) -> np.ndarray:
        P = s["power_draw_W"].ffill().to_numpy(float)
        idx = np.arange(len(P))
        return np.stack([P[np.minimum(idx + h, len(P) - 1)] for h in HORIZONS], axis=1)

    def forecast_temperature(self, s: pd.DataFrame):
        return None


class LightGBMForecaster:
    """Loads d_power_{30,45,60}.txt written by pcool.models_gbm.train_gbm."""

    def __init__(self, model_dir: str | Path, name: str | None = None):
        import lightgbm as lgb
        self.dir = Path(model_dir)
        self.name = name or f"ml_{self.dir.name}"
        self.boosters = {h: lgb.Booster(model_file=str(self.dir / f"d_power_{h}.txt")) for h in HORIZONS}
        self.features = self.boosters[HORIZONS[0]].feature_name()
        # models trained by the memory-safe pipeline store categorical codes + their category lists
        info = self.dir / "info.json"
        self.categories = __import__("json").loads(info.read_text()).get("categories") if info.exists() else None

    def _features(self, s: pd.DataFrame) -> pd.DataFrame:
        _pcool()
        from pcool.config import Config
        from pcool.features import series_features
        f = series_features(s, Config())
        for c in ("label", "family"):
            if c in self.features:
                f[c] = f[c].astype("category")
        return f

    def _predict(self, s: pd.DataFrame, boosters: dict, col: str) -> np.ndarray:
        f = self._features(s)
        now = s[col].ffill().to_numpy(float)
        if self.categories is not None:
            from pcool.models_gbm import to_matrix
            X = to_matrix(f, self.features, self.categories)
        else:
            X = f[self.features]
        out = np.empty((len(s), len(HORIZONS)))
        for j, h in enumerate(HORIZONS):
            out[:, j] = now + boosters[h].predict(X)
        # before the 60 s warm-up the model has no complete feature window: fall back to persistence
        warm = (f["t_since_start_s"] < 60).to_numpy() | np.isnan(out).any(axis=1)
        out[warm] = now[warm, None]
        return out

    def forecast(self, s: pd.DataFrame) -> np.ndarray:
        return self._predict(s, self.boosters, "power_draw_W")

    def forecast_temperature(self, s: pd.DataFrame):
        """Forecast of the MEASURED (source-system) GPU temperature, if d_temp models were exported."""
        import lightgbm as lgb
        files = {h: self.dir / f"d_temp_{h}.txt" for h in HORIZONS}
        if not all(f.exists() for f in files.values()):
            return None
        boosters = {h: lgb.Booster(model_file=str(f)) for h, f in files.items()}
        return self._predict(s, boosters, "temperature_gpu")


class LSTMForecaster:
    """Loads model.pt written by pcool.pipeline (L0/L1)."""

    def __init__(self, model_pt: str | Path, name: str | None = None):
        import torch
        _pcool()
        from pcool import lstm
        from pcool.config import Config
        ck = torch.load(model_pt, map_location="cpu", weights_only=False)
        cfg = Config(**{k: v for k, v in ck["cfg"].items() if k in Config.__dataclass_fields__})
        self.cfg, self.ck, self.lstm = cfg, ck, lstm
        self.model = lstm.LSTMForecaster(len(ck["inputs"]), 6, len(ck["labels"]), ck["use_label"], cfg)
        self.model.load_state_dict(ck["state_dict"])
        self.name = name or f"ml_{Path(model_pt).parent.name}"

    def forecast(self, s: pd.DataFrame) -> np.ndarray:
        store = self.lstm.SeriesStore(s, self.ck["labels"])
        anchors = s[["series_id", "t"]].reset_index(drop=True)
        res = dict(model=self.model, x_mu=self.ck["x_mu"], x_sd=self.ck["x_sd"],
                   y_mu=self.ck["y_mu"], y_sd=self.ck["y_sd"])
        pred, valid = self.lstm.predict_lstm(res, store, anchors, self.cfg)
        P = s["power_draw_W"].ffill().to_numpy(float)
        out = np.repeat(P[:, None], len(HORIZONS), 1)
        cols = [f"d_power_{h}" for h in HORIZONS]
        out[valid] = P[valid, None] + pred.loc[valid, cols].to_numpy()
        return out

    def forecast_temperature(self, s: pd.DataFrame):
        store = self.lstm.SeriesStore(s, self.ck["labels"])
        anchors = s[["series_id", "t"]].reset_index(drop=True)
        res = dict(model=self.model, x_mu=self.ck["x_mu"], x_sd=self.ck["x_sd"],
                   y_mu=self.ck["y_mu"], y_sd=self.ck["y_sd"])
        pred, valid = self.lstm.predict_lstm(res, store, anchors, self.cfg)
        T = s["temperature_gpu"].ffill().to_numpy(float)
        out = np.repeat(T[:, None], len(HORIZONS), 1)
        cols = [f"d_temp_{h}" for h in HORIZONS]
        out[valid] = T[valid, None] + pred.loc[valid, cols].to_numpy()
        return out


def load_forecaster(spec: str):
    """'persistence' | 'oracle' | 'lgbm:<model_dir>' | 'lstm:<model.pt>'."""
    if spec == "persistence":
        return PersistenceForecaster()
    if spec == "oracle":
        return OracleForecaster()
    kind, _, path = spec.partition(":")
    if kind == "lgbm":
        return LightGBMForecaster(path)
    if kind == "lstm":
        return LSTMForecaster(path)
    raise ValueError(spec)
