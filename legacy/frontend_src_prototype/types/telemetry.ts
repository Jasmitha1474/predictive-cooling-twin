export interface NodeData {
  node_id: string;
  workload: string;
  gpu_utilization: number;
  gpu_power: number;
  gpu_memory: number;
  gpu_clock: number;
  gpu_temperature: number;
  predicted_temperatures: number[];
  predicted_power: number[];
  prediction_horizons: number[];
}
export interface RackData {
  rack_id: string;
  nodes: NodeData[];
  coolant_temperature: number;
  coolant_flow_rate: number;
  valve_position: number;
  cooling_demand: number;
}
export interface Alert {
  time: string;
  type: 'INFO'|'PREDICTION'|'CONTROL'|'WARNING';
  message: string;
}
export interface TelemetryFrame {
  timestamp: string;
  tick: number;
  simulation_speed: number;
  racks: RackData[];
  controller_mode: string;
  alerts: Alert[];
  energy: any;
  model_metrics: any;
}
export type CameraView = 'overview'|'rack'|'gpu'|'cooling'|'thermal'|'control-room';
