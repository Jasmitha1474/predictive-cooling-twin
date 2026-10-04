import { useTelemetryStore } from '../store/telemetryStore';

export function useSimulation() {
  const store = useTelemetryStore();

  const apiCall = async (endpoint: string, payload: any = {}) => {
    // In a real app this would hit the API
    console.log(`API Call to ${endpoint}`, payload);
  };

  return {
    start: () => { apiCall('/start'); store.setSimulationRunning(true); },
    stop: () => { apiCall('/stop'); store.setSimulationRunning(false); },
    reset: () => apiCall('/reset'),
    pause: () => { apiCall('/pause'); store.setSimulationRunning(false); },
    setWorkload: (type: string, rackId?: string, nodeId?: string, intensity?: string) => 
      apiCall('/workload', { type, rackId, nodeId, intensity }),
    setController: (mode: 'reactive' | 'predictive') => { apiCall('/controller', { mode }); store.setControllerMode(mode); },
    setSpeed: (multiplier: number) => { apiCall('/speed', { multiplier }); store.setSimulationSpeed(multiplier); },
    setSettings: (threshold: number, horizon: number, aggressiveness: string) => 
      apiCall('/settings', { threshold, horizon, aggressiveness }),
  };
}
