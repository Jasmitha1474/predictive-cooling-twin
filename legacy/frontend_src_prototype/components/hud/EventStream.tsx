import React from 'react';
import { useTelemetryStore } from '../../store/telemetryStore';

export function EventStream() {
  const { alerts } = useTelemetryStore();

  return (
    <div className="fixed bottom-4 left-4 w-64 h-48 bg-dark/80 border border-cyan/30 rounded flex flex-col font-mono text-[10px] overflow-hidden z-40">
      <div className="bg-cyan/20 p-1 border-b border-cyan/30 text-cyan font-bold">EVENT STREAM</div>
      <div className="flex-1 overflow-y-auto p-2 flex flex-col gap-1">
        {alerts.slice(-15).map((alert, i) => (
          <div key={i} className={`
            ${alert.type === 'INFO' ? 'text-blue-400' : ''}
            ${alert.type === 'PREDICTION' ? 'text-purple-400' : ''}
            ${alert.type === 'CONTROL' ? 'text-green-400' : ''}
            ${alert.type === 'WARNING' ? 'text-orange-400' : ''}
          `}>
            <span className="opacity-50">[{alert.time.split('T')[1]?.substring(0,8)}]</span> {alert.message}
          </div>
        ))}
      </div>
    </div>
  );
}
