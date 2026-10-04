import { create } from 'zustand';
import { TelemetryFrame, Alert, CameraView } from '../types/telemetry';

interface TelemetryState {
  connected: boolean;
  latestFrame: TelemetryFrame | null;
  history: TelemetryFrame[];
  selectedRack: string | null;
  selectedNode: string | null;
  currentView: CameraView;
  thermalViewEnabled: boolean;
  simulationRunning: boolean;
  controllerMode: 'reactive' | 'predictive';
  simulationSpeed: number;
  predictionHorizon: number;
  temperatureThreshold: number;
  coolingAggressiveness: 'low' | 'medium' | 'high';
  alerts: Alert[];
  comparisonData: { reactive: any, predictive: any } | null;
  setConnected: (connected: boolean) => void;
  addFrame: (frame: TelemetryFrame) => void;
  setSelectedRack: (id: string | null) => void;
  setSelectedNode: (id: string | null) => void;
  setCurrentView: (view: CameraView) => void;
  setThermalViewEnabled: (enabled: boolean) => void;
  setSimulationRunning: (running: boolean) => void;
  setControllerMode: (mode: 'reactive' | 'predictive') => void;
  setSimulationSpeed: (speed: number) => void;
  setPredictionHorizon: (horizon: number) => void;
  setTemperatureThreshold: (threshold: number) => void;
  setCoolingAggressiveness: (aggressiveness: 'low' | 'medium' | 'high') => void;
}

export const useTelemetryStore = create<TelemetryState>((set) => ({
  connected: false,
  latestFrame: null,
  history: [],
  selectedRack: null,
  selectedNode: null,
  currentView: 'overview',
  thermalViewEnabled: false,
  simulationRunning: false,
  controllerMode: 'reactive',
  simulationSpeed: 1,
  predictionHorizon: 30,
  temperatureThreshold: 80,
  coolingAggressiveness: 'medium',
  alerts: [],
  comparisonData: null,
  setConnected: (connected) => set({ connected }),
  addFrame: (frame) => set((state) => {
    const newHistory = [...state.history, frame].slice(-120);
    const newAlerts = [...state.alerts, ...frame.alerts].slice(-100);
    return { latestFrame: frame, history: newHistory, alerts: newAlerts };
  }),
  setSelectedRack: (id) => set({ selectedRack: id }),
  setSelectedNode: (id) => set({ selectedNode: id }),
  setCurrentView: (view) => set({ currentView: view }),
  setThermalViewEnabled: (enabled) => set({ thermalViewEnabled: enabled }),
  setSimulationRunning: (running) => set({ simulationRunning: running }),
  setControllerMode: (mode) => set({ controllerMode: mode }),
  setSimulationSpeed: (speed) => set({ simulationSpeed: speed }),
  setPredictionHorizon: (horizon) => set({ predictionHorizon: horizon }),
  setTemperatureThreshold: (threshold) => set({ temperatureThreshold: threshold }),
  setCoolingAggressiveness: (agg) => set({ coolingAggressiveness: agg }),
}));
