"""Cooling controllers. All share one interface and the same actuator (the twin's valve).

decide(...) is called once per control period (1 s) and returns a valve command 0..1.
Inputs a controller may use:
  sim       : current SIMULATED twin state (Twin.snapshot() + T_j)
  P_now     : current MEASURED power (W) from the real trace
  forecast  : PREDICTED power at +30/+45/+60 s (W), or None
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from simulation.twin import TwinParams, rollout_max_Tj


@dataclass
class ControlSettings:
    T_threshold_C: float = 80.0        # set per experiment (see experiments/compare.py)
    hysteresis_C: float = 3.0
    v_min: float = 0.2                 # minimum valve opening (keeps liquid supplied)
    dv_up: float = 0.10                # reactive step per second above threshold
    dv_down: float = 0.02              # reactive step per second below threshold - hysteresis
    margin_C: float = 2.0              # predictive: keep forecast peak this far below threshold
    kp: float = 0.08                   # PI gains (per degC, per degC*s)
    ki: float = 0.004
    candidates: int = 11               # predictive: valve commands 0, 0.1, ..., 1.0


class ReactiveThreshold:
    """Brief section 21: increase cooling only after the CURRENT temperature crosses the threshold."""
    name = "reactive_threshold"

    def __init__(self, s: ControlSettings):
        self.s, self.v = s, s.v_min

    def decide(self, sim, P_now, forecast):
        T = sim["T_j"]
        if T >= self.s.T_threshold_C:
            self.v = min(1.0, self.v + self.s.dv_up)
        elif T <= self.s.T_threshold_C - self.s.hysteresis_C:
            self.v = max(self.s.v_min, self.v - self.s.dv_down)
        return self.v


class ReactivePI:
    """Stronger reactive baseline: PI on current temperature toward threshold - margin."""
    name = "reactive_pi"

    def __init__(self, s: ControlSettings):
        self.s, self.i = s, 0.0

    def decide(self, sim, P_now, forecast):
        e = sim["T_j"] - (self.s.T_threshold_C - self.s.margin_C)
        u = self.s.v_min + self.s.kp * e + self.s.ki * self.i
        if self.s.v_min < u < 1.0 or (u >= 1.0 and e < 0) or (u <= self.s.v_min and e > 0):
            self.i += e                       # conditional integration = anti-windup
        return float(np.clip(u, self.s.v_min, 1.0))


def power_profile(P_now: float, forecast, horizon_s: int = 60) -> np.ndarray:
    """Piecewise-linear power at t+0..t+horizon from the +30/+45/+60 s forecast."""
    knots_t = np.array([0, 30, 45, 60])
    knots_p = np.r_[P_now, forecast]
    return np.interp(np.arange(horizon_s + 1), knots_t, knots_p)


class Predictive:
    """Brief sections 20 and 22: model-predictive valve choice from a power forecast.

    For each candidate valve command, roll the twin forward 60 s under the forecast
    power profile; choose the smallest command whose predicted peak T_j stays below
    threshold - margin (else fully open). The forecast source is pluggable: persistence,
    oracle (true future), or the exported ML model.
    """

    def __init__(self, s: ControlSettings, p: TwinParams, name: str = "predictive"):
        self.s, self.p, self.name = s, p, name
        self.cands = np.linspace(0, 1, s.candidates)
        self.cands = np.maximum(self.cands, s.v_min)

    def decide(self, sim, P_now, forecast):
        prof = power_profile(P_now, forecast)
        peak = rollout_max_Tj(self.p, sim, prof, self.cands)
        ok = np.where(peak <= self.s.T_threshold_C - self.s.margin_C)[0]
        return float(self.cands[ok[0]]) if len(ok) else 1.0
