"""Thermal / hydraulic digital twin of one GPU on a two-phase direct-to-chip cold plate.

LAYER B (SIMULATED). The only real input is the GPU power trace P(t). Every output of
this module (junction and cold-plate temperature, valve position, flow, heat removed,
vapour generation, pump power) is SIMULATED. Equations: docs/experiments.md section 4.

This is a lumped-capacitance model. It is NOT CFD and does not resolve boiling,
vapour quality, dry-out or pressure drop. Parameters marked ASSUMED are design
choices, not measurements; C_total is identified from real power->temperature data
(see calibrate.py) and only sets the thermal inertia.
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass

import numpy as np


@dataclass
class TwinParams:
    # --- thermal inertia (C_total from calibrate.py; split between die and cold plate is ASSUMED)
    C_total_J_per_K: float = 200.0     # default = tau/R fitted on real V100 data (calibrate.py); overwritten when re-fitted
    die_fraction: float = 0.10         # ASSUMED share of C_total in the die/package
    R_jc_K_per_W: float = 0.05         # ASSUMED junction -> cold-plate resistance

    # --- two-phase cold plate (ASSUMED)
    T_sat_C: float = 35.0              # saturation temperature of dielectric coolant at loop pressure
    h_fg_J_per_kg: float = 190e3       # latent heat of the dielectric fluid
    G0_W_per_K: float = 0.0            # conductance at zero flow
    G1_W_per_K: float = 33.0           # added conductance at full flow
    G_exp: float = 0.7                 # diminishing return with flow (0<n<1)
    rho_kg_per_L: float = 1.2          # liquid density (for vapour-quality proxy)
    x_max: float = 0.8                 # dry-out proxy: max exit vapour quality before G degrades
    k_dry: float = 0.5                 # conductance multiplier when dry-out proxy is active

    # --- hydraulics / actuation (ASSUMED)
    Q_min_Lpm: float = 0.5
    Q_max_Lpm: float = 6.0
    tau_valve_s: float = 5.0           # valve actuator time constant
    valve_rate_max_per_s: float = 0.2  # max |dv/dt|
    transport_delay_s: float = 5.0     # valve -> cold plate flow delay
    k_pump: float = 1.0                # pump power = k_pump * Q^3 (relative units; affinity law)

    dt_s: float = 0.1                  # integration step

    def C_die(self):
        return self.C_total_J_per_K * self.die_fraction

    def C_cp(self):
        return self.C_total_J_per_K * (1 - self.die_fraction)

    def to_dict(self):
        return dataclasses.asdict(self)


def flow_from_valve(v, p: TwinParams):
    return p.Q_min_Lpm + (p.Q_max_Lpm - p.Q_min_Lpm) * v


def conductance(Q, p: TwinParams):
    return p.G0_W_per_K + p.G1_W_per_K * (np.asarray(Q) / p.Q_max_Lpm) ** p.G_exp


class Twin:
    """Stateful simulator. Call step(P_watts, v_cmd) every dt_s seconds."""

    def __init__(self, p: TwinParams, T0_C: float | None = None, v0: float = 0.2):
        self.p = p
        n_delay = max(1, int(round(p.transport_delay_s / p.dt_s)))
        self._vbuf = np.full(n_delay, v0)       # valve history for transport delay
        self._k = 0
        self.v = v0
        self.T_cp = p.T_sat_C if T0_C is None else T0_C
        self.T_j = self.T_cp if T0_C is None else T0_C
        self.Q = flow_from_valve(v0, p)
        self.Q_rem = 0.0

    def check_stability(self):
        p = self.p
        g_max = conductance(p.Q_max_Lpm, p)
        limit = 0.2 * min(p.R_jc_K_per_W * p.C_die(), p.C_cp() / (g_max + 1 / p.R_jc_K_per_W))
        assert p.dt_s < limit, f"dt_s={p.dt_s} too large for explicit Euler (limit {limit:.3f}s)"

    def step(self, P: float, v_cmd: float) -> dict:
        p, dt = self.p, self.p.dt_s
        v_cmd = float(np.clip(v_cmd, 0.0, 1.0))
        dv = np.clip((v_cmd - self.v) / p.tau_valve_s, -p.valve_rate_max_per_s, p.valve_rate_max_per_s)
        self.v = float(np.clip(self.v + dv * dt, 0.0, 1.0))
        v_delayed = self._vbuf[self._k]
        self._vbuf[self._k] = self.v
        self._k = (self._k + 1) % len(self._vbuf)
        self.Q = float(flow_from_valve(v_delayed, p))
        G = float(conductance(self.Q, p))
        q = G * max(self.T_cp - p.T_sat_C, 0.0)
        m_liq = self.Q * p.rho_kg_per_L / 60.0                      # kg/s
        dry = q > p.x_max * m_liq * p.h_fg_J_per_kg
        if dry:
            q = p.k_dry * q
        q_jc = (self.T_j - self.T_cp) / p.R_jc_K_per_W
        self.T_j += dt * (P - q_jc) / p.C_die()
        self.T_cp += dt * (q_jc - q) / p.C_cp()
        self.Q_rem = q
        return dict(T_j=self.T_j, T_cp=self.T_cp, v=self.v, Q=self.Q, Q_rem=q,
                    m_vap=q / p.h_fg_J_per_kg, dry=dry, pump=p.k_pump * self.Q ** 3)

    def snapshot(self) -> dict:
        return dict(T_j=self.T_j, T_cp=self.T_cp, v=self.v, vbuf=self._vbuf.copy(), k=self._k)


def rollout_Tj_path(p: TwinParams, snap: dict, P_future: np.ndarray, v_cmds: np.ndarray,
                    dt_roll: float = 0.5) -> np.ndarray:
    """Vectorised forward simulation for candidate valve commands (one per column).

    P_future: power at 1 s resolution (P_future[k] = power at t+k s, k = 0..H).
    Returns predicted T_j at t+0..t+H seconds, shape [H+1, n_candidates].
    Same equations as Twin.step with a coarser, semi-implicit step (dry-out proxy omitted).
    """
    v_cmds = np.asarray(v_cmds, float)
    n_c = len(v_cmds)
    T_j = np.full(n_c, snap["T_j"])
    T_cp = np.full(n_c, snap["T_cp"])
    v = np.full(n_c, snap["v"])
    pipe = np.roll(snap["vbuf"], -snap["k"])                      # oldest first
    sub = max(1, int(round(dt_roll / p.dt_s)))
    hist = [np.full(n_c, x) for x in pipe[::sub]]                 # valve positions already in transit
    per_s = int(round(1.0 / dt_roll))
    H = len(P_future) - 1
    path = np.empty((H + 1, n_c))
    path[0] = T_j
    a = dt_roll / (p.C_die() * p.R_jc_K_per_W)
    for i in range(H * per_s):
        P = P_future[i // per_s]
        dv = np.clip((v_cmds - v) / p.tau_valve_s, -p.valve_rate_max_per_s, p.valve_rate_max_per_s)
        v = np.clip(v + dv * dt_roll, 0, 1)
        hist.append(v)
        Q = flow_from_valve(hist.pop(0), p)
        q = conductance(Q, p) * np.maximum(T_cp - p.T_sat_C, 0)
        q_jc = (T_j - T_cp) / p.R_jc_K_per_W
        T_j = (T_j + dt_roll * P / p.C_die() + a * T_cp) / (1 + a)
        T_cp = T_cp + dt_roll * (q_jc - q) / p.C_cp()
        if (i + 1) % per_s == 0:
            path[(i + 1) // per_s] = T_j
    return path


def rollout_max_Tj(p: TwinParams, snap: dict, P_future: np.ndarray, v_cmds: np.ndarray,
                   dt_roll: float = 0.5) -> np.ndarray:
    """Maximum predicted T_j over the horizon for each candidate valve command."""
    return rollout_Tj_path(p, snap, P_future, v_cmds, dt_roll).max(axis=0)


def steady_state_Tj(p: TwinParams, P: float, v: float) -> float:
    """Closed form steady state (no dry-out): T_j = T_sat + P (R_jc + 1/G(Q(v)))."""
    return p.T_sat_C + P * (p.R_jc_K_per_W + 1.0 / float(conductance(flow_from_valve(v, p), p)))
