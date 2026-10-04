import React from 'react';
import { AnalyticsCharts } from './AnalyticsCharts';
import { useTelemetryStore } from '../../store/telemetryStore';

export function ControlRoom() {
  const { currentView } = useTelemetryStore();
  
  if (currentView !== 'control-room') return null;

  return (
    <div className="fixed inset-0 pt-10 pb-20 px-8 bg-dark/95 z-40 overflow-y-auto font-sans">
      <h1 className="text-2xl text-cyan mb-6 font-mono">DASHBOARD</h1>
      <AnalyticsCharts />
    </div>
  );
}
