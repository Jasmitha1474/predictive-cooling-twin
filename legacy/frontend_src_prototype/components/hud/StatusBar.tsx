import React from 'react';
import { useTelemetryStore } from '../../store/telemetryStore';

export function StatusBar() {
  const { connected, latestFrame, controllerMode } = useTelemetryStore();

  return (
    <div className="fixed top-0 left-0 right-0 p-2 flex justify-between bg-dark/80 text-cyan border-b border-cyan/30 z-50 font-mono text-xs">
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${connected ? 'bg-green-500' : 'bg-red-500'}`} />
          <span>{connected ? 'CONNECTED' : 'DISCONNECTED'}</span>
        </div>
        <div>MODE: {controllerMode.toUpperCase()}</div>
      </div>
      {latestFrame && (
        <div className="flex gap-4">
          <div>TICK: {latestFrame.tick}</div>
          <div>SPEED: {latestFrame.simulation_speed}x</div>
        </div>
      )}
    </div>
  );
}
