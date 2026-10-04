"""Simulation engine behind /ws/telemetry.

Per virtual GPU, every simulated second:
  1. MEASURED   : next row of a real recorded trace (replay pack)
  2. PREDICTED  : power (+ measured-system temperature, if the model has it) at +30/45/60 s
                  from the loaded model, or from persistence when no model is loaded
  3. CONTROL    : reactive or predictive controller chooses a valve command
  4. SIMULATED  : the twin integrates 1 s with the measured power as heat input
Nothing in the frame is produced by a timer or animation script: every number comes from
steps 1-4. Each value sits under a "measured" / "predicted" / "simulated" key.
"""
from __future__ import annotations

import math
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from controller.controllers import ControlSettings, Predictive, ReactiveThreshold, power_profile  # noqa: E402
from controller.forecasters import HORIZONS  # noqa: E402
from simulation.twin import Twin, TwinParams, rollout_Tj_path, steady_state_Tj  # noqa: E402

MODES = ("RESEARCH_DATA_REPLAY", "DIGITAL_TWIN_SIMULATION")
CONTROLLERS = ("reactive", "predictive")
P_REF_W = 250.0


def _num(x):
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else round(float(x), 3)


@dataclass
class VirtualGPU:
    gpu_id: str
    rack: str
    series_id: str
    trace: object                    # DataFrame (1 s grid)
    F_power: np.ndarray              # [n, 3]
    F_temp: np.ndarray | None        # [n, 3] or None
    offset: int = 0
    idx: int = 0
    twin: Twin | None = None
    ctrl: object = None
    event_active: bool = False
    below_count: int = 0
    restarts: int = 0
    history: list = field(default_factory=list)


class Engine:
    def __init__(self, pack, forecaster, model_status: dict, racks: int = 4, per_rack: int = 5,
                 params: TwinParams | None = None):
        self.pack, self.forecaster, self.model_status = pack, forecaster, model_status
        self.p = params or TwinParams()
        Twin(self.p).check_stability()
        self.s = ControlSettings(T_threshold_C=round(steady_state_Tj(self.p, P_REF_W, 0.5), 1))
        self.mode, self.controller_mode = "DIGITAL_TWIN_SIMULATION", "predictive"
        self.paused, self.speed, self.sim_time = False, 1.0, 0
        self._forecast_cache = {}
        series = sorted(pack.series)
        self.gpus = []
        for r in range(racks):
            for g in range(per_rack):
                i = r * per_rack + g
                sid = series[i % len(series)]
                # if traces are reused, start later in the trace so neighbours differ (reported in the frame)
                offset = (i // len(series)) * 600
                self.gpus.append(self._make_gpu(f"R{r + 1:02d}-G{g + 1:02d}", f"R{r + 1:02d}", sid, offset))
        self.reset()

    # ------------------------------------------------------------------ setup
    def _forecasts(self, sid):
        if sid not in self._forecast_cache:
            tr = self.pack.series[sid]
            self._forecast_cache[sid] = (self.forecaster.forecast(tr), self.forecaster.forecast_temperature(tr))
        return self._forecast_cache[sid]

    def _make_gpu(self, gpu_id, rack, sid, offset=0):
        tr = self.pack.series[sid]
        Fp, Ft = self._forecasts(sid)
        return VirtualGPU(gpu_id, rack, sid, tr, Fp, Ft, offset=min(offset, max(0, len(tr) - 1)))

    def _new_controller(self):
        if self.controller_mode == "reactive":
            return ReactiveThreshold(self.s)
        return Predictive(self.s, self.p)

    def reset(self):
        """Restart every GPU at the start of its trace: lets reactive and predictive replay
        the SAME workload from the SAME initial state (brief section 50, steps 14-16)."""
        self.sim_time = 0
        for g in self.gpus:
            g.idx = g.offset
            P0 = float(g.trace["power_draw_W"].ffill().bfill().iloc[g.idx])
            g.twin = Twin(self.p, T0_C=steady_state_Tj(self.p, P0, self.s.v_min), v0=self.s.v_min)
            g.twin.T_cp = g.twin.T_j - P0 * self.p.R_jc_K_per_W
            g.ctrl = self._new_controller()
            g.event_active, g.below_count, g.history = False, 0, []

    def assign_trace(self, gpu_id: str, series_id: str):
        for i, g in enumerate(self.gpus):
            if g.gpu_id == gpu_id:
                self.gpus[i] = self._make_gpu(g.gpu_id, g.rack, series_id)
        self.reset()

    def configure(self, mode=None, controller_mode=None, paused=None, speed=None, reset=False):
        if mode is not None:
            assert mode in MODES, mode
            self.mode = mode
        if controller_mode is not None and controller_mode != self.controller_mode:
            assert controller_mode in CONTROLLERS, controller_mode
            self.controller_mode = controller_mode
            reset = True                       # same workload, same initial state
        if paused is not None:
            self.paused = bool(paused)
        if speed is not None:
            self.speed = float(min(max(speed, 0.25), 20.0))
        if reset:
            self.reset()

    # ------------------------------------------------------------------ one simulated second
    def step(self) -> dict:
        frames, events = [], []
        n_sub = int(round(1.0 / self.p.dt_s))
        for g in self.gpus:
            if g.idx >= len(g.trace):
                g.idx, g.restarts = 0, g.restarts + 1
            row = g.trace.iloc[g.idx]
            P = float(row["power_draw_W"]) if not math.isnan(row["power_draw_W"]) else float(
                g.trace["power_draw_W"].ffill().iloc[g.idx])
            Fp = g.F_power[g.idx]
            sim = g.twin.snapshot()
            # twin temperature path if the valve were held where it is (what the controller is reacting to)
            path = rollout_Tj_path(self.p, sim, power_profile(P, Fp), np.array([g.twin.v]))[:, 0]
            twin_pred = [float(path[h]) for h in HORIZONS]
            peak = float(path.max())
            v_cmd = g.ctrl.decide(sim, P, Fp if self.controller_mode == "predictive" else None)
            for _ in range(n_sub):
                r = g.twin.step(P, v_cmd)

            ev = self._event(g, peak, twin_pred, v_cmd)
            if ev:
                events.append(ev)
            frames.append(self._frame(g, row, P, Fp, twin_pred, v_cmd, r))
            g.idx += 1
        self.sim_time += 1
        return dict(type="frame", sim_time_s=self.sim_time, mode=self.mode,
                    controller_mode=self.controller_mode, threshold_C=self.s.T_threshold_C,
                    model_status=self.model_status["state"], gpus=frames, events=events,
                    cdu=self._cdu(frames))

    def _event(self, g, peak, twin_pred, v_cmd):
        limit = self.s.T_threshold_C - self.s.margin_C
        if not g.event_active and peak >= limit:
            g.event_active, g.below_count = True, 0
            return dict(type="thermal_event_predicted", gpu_id=g.gpu_id, rack=g.rack,
                        predicted_peak_C=round(peak, 2), threshold_C=self.s.T_threshold_C,
                        predicted_twin_temperature=dict(zip([f"+{h}s" for h in HORIZONS],
                                                            [round(x, 2) for x in twin_pred])),
                        controller_mode=self.controller_mode, valve_command=round(v_cmd, 3),
                        source="predicted (twin rollout of the power forecast)")
        if g.event_active:
            g.below_count = g.below_count + 1 if peak < limit - 1.0 else 0
            if g.below_count >= 30:
                g.event_active = False
                return dict(type="thermal_event_cleared", gpu_id=g.gpu_id, rack=g.rack)
        return None

    def _frame(self, g, row, P, Fp, twin_pred, v_cmd, r):
        Ft = None if g.F_temp is None else g.F_temp[g.idx]
        return dict(
            gpu_id=g.gpu_id, rack=g.rack,
            trace=dict(dataset="mit-supercloud-202201", series_id=g.series_id, job_id=str(row["job_id"]),
                       t_index=int(g.idx), recorded_unix_s=int(row["t"]), restarts=g.restarts),
            workload=dict(label=str(row["label"]), source="dataset_label"),
            measured=dict(gpu_utilization=_num(row["utilization_gpu_pct"]), gpu_power=_num(row["power_draw_W"]),
                          gpu_temperature=_num(row["temperature_gpu"]),
                          memory_utilization=_num(row["utilization_memory_pct"]),
                          memory_used_mib=_num(row["memory_used_MiB"]),
                          memory_temperature=_num(row["temperature_memory"]),
                          sm_clock_mhz=_num(row["clocks_current_sm_MHz"]),
                          mem_clock_mhz=_num(row["clocks_current_memory_MHz"])),
            predicted=dict(source=self.model_status["forecast_source"], model_id=self.model_status.get("model_id"),
                           horizons_s=list(HORIZONS), power=[_num(x) for x in Fp],
                           temperature_measured_system=None if Ft is None else [_num(x) for x in Ft],
                           twin_temperature_if_valve_held=[_num(x) for x in twin_pred]),
            simulated=dict(twin_temperature=_num(r["T_j"]), cold_plate_temperature=_num(r["T_cp"]),
                           coolant_temperature=_num(self.p.T_sat_C),   # two-phase: near saturation (assumed)
                           valve_position=_num(r["v"]), valve_command=_num(v_cmd), cooling_demand=_num(v_cmd),
                           coolant_flow_lpm=_num(r["Q"]), heat_removed_w=_num(r["Q_rem"]),
                           vapour_generation_g_s=_num(r["m_vap"] * 1e3), dryout_proxy=bool(r["dry"]),
                           est_pump_power_rel=_num(r["pump"])),
        )

    @staticmethod
    def _cdu(frames):
        q = [f["simulated"]["coolant_flow_lpm"] for f in frames]
        return dict(source="simulated", total_flow_lpm=_num(sum(q)),
                    mean_valve_position=_num(np.mean([f["simulated"]["valve_position"] for f in frames])),
                    total_heat_removed_w=_num(sum(f["simulated"]["heat_removed_w"] for f in frames)),
                    est_pump_power_rel=_num(sum(f["simulated"]["est_pump_power_rel"] for f in frames)))

    def describe(self) -> dict:
        return dict(type="hello", modes=list(MODES), controllers=list(CONTROLLERS), mode=self.mode,
                    controller_mode=self.controller_mode, threshold_C=self.s.T_threshold_C,
                    horizons_s=list(HORIZONS), model=self.model_status,
                    layout=[dict(gpu_id=g.gpu_id, rack=g.rack, series_id=g.series_id,
                                 label=str(g.trace["label"].iloc[0]), offset_s=g.offset) for g in self.gpus],
                    replay_pack=self.pack.meta, twin_params=asdict(self.p), settings=asdict(self.s),
                    labels=dict(measured="REAL MEASURED TELEMETRY (MIT Supercloud, nvidia-smi)",
                                predicted="MODEL PREDICTION",
                                simulated="SIMULATED COOLING VARIABLE (simplified twin, not CFD)"))
