import { create } from 'zustand';
import type { CameraView, Frame, GpuFrame, Hello, ThermalEvent } from './types';

const HISTORY_S = 120;

export interface HistoryPoint {
  t: number;
  measuredTemp: number | null;
  measuredPower: number | null;
  twinTemp: number;
  valve: number;
  flow: number;
}

export interface EventLogEntry extends ThermalEvent {
  sim_time_s: number;
}

interface State {
  connected: boolean;
  hello: Hello | null;
  frame: Frame | null;
  byGpu: Record<string, GpuFrame>;
  history: Record<string, HistoryPoint[]>; // per GPU, last 120 s (small: never the dataset)
  events: EventLogEntry[];
  activeEvents: Record<string, EventLogEntry>;
  pendingFocus: EventLogEntry | null;

  view: CameraView;
  selectedRack: string | null;
  selectedGpu: string | null;
  thermalView: boolean;
  followEvents: boolean;
  showResults: boolean;

  setConnected: (c: boolean) => void;
  onHello: (h: Hello) => void;
  onFrame: (f: Frame) => void;
  consumeFocus: () => void;
  setView: (v: CameraView) => void;
  selectRack: (r: string | null) => void;
  selectGpu: (g: string | null) => void;
  toggleThermal: () => void;
  toggleFollow: () => void;
  setShowResults: (s: boolean) => void;
}

export const useTelemetry = create<State>((set) => ({
  connected: false,
  hello: null,
  frame: null,
  byGpu: {},
  history: {},
  events: [],
  activeEvents: {},
  pendingFocus: null,
  view: 'overview',
  selectedRack: null,
  selectedGpu: null,
  thermalView: false,
  followEvents: true,
  showResults: false,

  setConnected: (connected) => set({ connected }),
  onHello: (hello) => set({ hello, history: {}, events: [], activeEvents: {} }),
  onFrame: (frame) =>
    set((s) => {
      const byGpu: Record<string, GpuFrame> = {};
      const history = { ...s.history };
      const restarted = s.frame && frame.sim_time_s < s.frame.sim_time_s; // controller switch / reset
      for (const g of frame.gpus) {
        byGpu[g.gpu_id] = g;
        const prev = restarted ? [] : history[g.gpu_id] ?? [];
        const point: HistoryPoint = {
          t: frame.sim_time_s,
          measuredTemp: g.measured.gpu_temperature,
          measuredPower: g.measured.gpu_power,
          twinTemp: g.simulated.twin_temperature,
          valve: g.simulated.valve_position,
          flow: g.simulated.coolant_flow_lpm,
        };
        history[g.gpu_id] = [...prev, point].slice(-HISTORY_S);
      }
      const activeEvents = restarted ? {} : { ...s.activeEvents };
      let pendingFocus = s.pendingFocus;
      const logged: EventLogEntry[] = [];
      for (const e of frame.events) {
        const entry = { ...e, sim_time_s: frame.sim_time_s };
        logged.push(entry);
        if (e.type === 'thermal_event_predicted') {
          activeEvents[e.gpu_id] = entry;
          if (!pendingFocus) pendingFocus = entry;
        } else delete activeEvents[e.gpu_id];
      }
      return {
        frame,
        byGpu,
        history,
        activeEvents,
        pendingFocus,
        events: [...(restarted ? [] : s.events), ...logged].slice(-50),
      };
    }),
  consumeFocus: () => set({ pendingFocus: null }),
  setView: (view) => set({ view }),
  selectRack: (selectedRack) => set({ selectedRack, view: selectedRack ? 'rack' : 'overview' }),
  selectGpu: (selectedGpu) =>
    set((s) => ({ selectedGpu, selectedRack: selectedGpu ? s.byGpu[selectedGpu]?.rack ?? s.selectedRack : s.selectedRack, view: selectedGpu ? 'gpu' : s.view })),
  toggleThermal: () => set((s) => ({ thermalView: !s.thermalView })),
  toggleFollow: () => set((s) => ({ followEvents: !s.followEvents })),
  setShowResults: (showResults) => set({ showResults }),
}));

/** Rack-level aggregates of SIMULATED values (mean valve, summed flow) for rack valves/pipes. */
export function rackAggregate(frame: Frame | null, rack: string) {
  const gs = frame?.gpus.filter((g) => g.rack === rack) ?? [];
  if (!gs.length) return { flow: 0, valve: 0, heat: 0, maxTwinTemp: 0 };
  return {
    flow: gs.reduce((a, g) => a + g.simulated.coolant_flow_lpm, 0),
    valve: gs.reduce((a, g) => a + g.simulated.valve_position, 0) / gs.length,
    heat: gs.reduce((a, g) => a + g.simulated.heat_removed_w, 0),
    maxTwinTemp: Math.max(...gs.map((g) => g.simulated.twin_temperature)),
  };
}
