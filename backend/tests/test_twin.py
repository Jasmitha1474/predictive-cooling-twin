"""Physics sanity checks for the simplified twin (not validation against hardware)."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from controller.controllers import ControlSettings, Predictive, ReactiveThreshold  # noqa: E402
from simulation.twin import Twin, TwinParams, rollout_max_Tj, steady_state_Tj  # noqa: E402


def _run(tw, P, v, seconds):
    for _ in range(int(seconds / tw.p.dt_s)):
        r = tw.step(P, v)
    return r


def test_converges_to_closed_form_steady_state():
    p = TwinParams()
    tw = Twin(p)
    tw.check_stability()
    r = _run(tw, 200.0, 0.5, 2000)
    assert abs(r["T_j"] - steady_state_Tj(p, 200.0, 0.5)) < 0.05
    assert abs(r["Q_rem"] - 200.0) < 0.5          # energy balance at steady state


def test_more_flow_means_cooler():
    p = TwinParams()
    assert steady_state_Tj(p, 250, 1.0) < steady_state_Tj(p, 250, 0.5) < steady_state_Tj(p, 250, 0.2)


def test_valve_rate_limit_and_delay():
    p = TwinParams()
    tw = Twin(p, v0=0.0)
    r = tw.step(100.0, 1.0)
    assert r["v"] <= p.valve_rate_max_per_s * p.dt_s + 1e-12
    # flow must not change before the transport delay has elapsed
    flows = [tw.step(100.0, 1.0)["Q"] for _ in range(int(p.transport_delay_s / p.dt_s) - 2)]
    assert max(flows) == p.Q_min_Lpm


def test_rollout_matches_simulator_roughly():
    p = TwinParams()
    tw = Twin(p, T0_C=50.0)
    snap = tw.snapshot()
    P = np.full(61, 220.0)
    pred = rollout_max_Tj(p, snap, P, np.array([0.3]))[0]
    Tmax = max(_run(tw, 220.0, 0.3, 1)["T_j"] for _ in range(60))
    assert abs(pred - Tmax) < 1.0


def test_predictive_opens_before_reactive_on_step():
    p, s = TwinParams(), ControlSettings(T_threshold_C=60.0)
    pred, react = Predictive(s, p), ReactiveThreshold(s)
    tw = Twin(p, T0_C=45.0)
    sim = dict(tw.snapshot(), T_j=45.0)
    f = np.array([240.0, 240.0, 240.0])              # forecast: big rise coming
    assert pred.decide(sim, 80.0, f) > react.decide(sim, 80.0, f)
