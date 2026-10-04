// Mirrors backend/app/engine.py. Every value lives under the key that says where it came from.

export type Num = number | null;

export interface Measured {
  gpu_utilization: Num;
  gpu_power: Num;
  gpu_temperature: Num;
  memory_utilization: Num;
  memory_used_mib: Num;
  memory_temperature: Num;
  sm_clock_mhz: Num;
  mem_clock_mhz: Num;
}

export interface Predicted {
  source: 'ml_model' | 'persistence_baseline_not_ml' | string;
  model_id: string | null;
  horizons_s: number[];
  power: Num[];
  temperature_measured_system: Num[] | null;
  twin_temperature_if_valve_held: Num[];
}

export interface Simulated {
  twin_temperature: number;
  cold_plate_temperature: number;
  coolant_temperature: number;
  valve_position: number;
  valve_command: number;
  cooling_demand: number;
  coolant_flow_lpm: number;
  heat_removed_w: number;
  vapour_generation_g_s: number;
  dryout_proxy: boolean;
  est_pump_power_rel: number;
}

export interface GpuFrame {
  gpu_id: string;
  rack: string;
  trace: { dataset: string; series_id: string; job_id: string; t_index: number; recorded_unix_s: number; restarts: number };
  workload: { label: string; source: 'dataset_label' };
  measured: Measured;
  predicted: Predicted;
  simulated: Simulated;
}

export interface ThermalEvent {
  type: 'thermal_event_predicted' | 'thermal_event_cleared';
  gpu_id: string;
  rack: string;
  predicted_peak_C?: number;
  threshold_C?: number;
  predicted_twin_temperature?: Record<string, number>;
  controller_mode?: string;
  valve_command?: number;
  source?: string;
}

export interface Frame {
  type: 'frame';
  sim_time_s: number;
  mode: 'RESEARCH_DATA_REPLAY' | 'DIGITAL_TWIN_SIMULATION';
  controller_mode: 'reactive' | 'predictive';
  threshold_C: number;
  model_status: string;
  gpus: GpuFrame[];
  events: ThermalEvent[];
  cdu: { source: 'simulated'; total_flow_lpm: number; mean_valve_position: number; total_heat_removed_w: number; est_pump_power_rel: number };
}

export interface ModelStatus {
  state: 'ACTIVE' | 'NOT_LOADED' | 'REJECTED_NO_MANIFEST' | 'LOAD_FAILED' | string;
  forecast_source: string;
  model_id?: string;
  detail?: string;
  manifest?: Record<string, unknown>;
}

export interface Hello {
  type: 'hello';
  modes: string[];
  controllers: string[];
  mode: Frame['mode'];
  controller_mode: Frame['controller_mode'];
  threshold_C: number;
  horizons_s: number[];
  model: ModelStatus;
  layout: { gpu_id: string; rack: string; series_id: string; label: string; offset_s: number }[];
  replay_pack: Record<string, unknown>;
  twin_params: Record<string, number>;
  settings: Record<string, number>;
  labels: { measured: string; predicted: string; simulated: string };
}

export type CameraView = 'overview' | 'rack' | 'gpu' | 'cooling' | 'thermal' | 'control-room';
