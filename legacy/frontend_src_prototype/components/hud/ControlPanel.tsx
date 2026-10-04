import React from 'react';
import { useTelemetryStore } from '../../store/telemetryStore';

export function ControlPanel() {
  const { currentView, setCurrentView, thermalViewEnabled, setThermalViewEnabled } = useTelemetryStore();

  return (
    <div className="fixed bottom-4 left-1/2 -translate-x-1/2 flex gap-2 p-2 bg-dark/80 border border-cyan/50 rounded-full z-50">
      <button onClick={() => setCurrentView('overview')} className={`px-4 py-2 rounded-full text-xs font-mono ${currentView === 'overview' ? 'bg-cyan text-dark' : 'text-cyan hover:bg-cyan/20'}`}>OVERVIEW</button>
      <button onClick={() => setCurrentView('cooling')} className={`px-4 py-2 rounded-full text-xs font-mono ${currentView === 'cooling' ? 'bg-cyan text-dark' : 'text-cyan hover:bg-cyan/20'}`}>COOLING</button>
      <button onClick={() => setThermalViewEnabled(!thermalViewEnabled)} className={`px-4 py-2 rounded-full text-xs font-mono ${thermalViewEnabled ? 'bg-red-500 text-white' : 'text-cyan hover:bg-cyan/20'}`}>THERMAL</button>
      <button onClick={() => setCurrentView('control-room')} className={`px-4 py-2 rounded-full text-xs font-mono ${currentView === 'control-room' ? 'bg-cyan text-dark' : 'text-cyan hover:bg-cyan/20'}`}>DASHBOARD</button>
    </div>
  );
}
