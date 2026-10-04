import React from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { useTelemetryStore } from '../../store/telemetryStore';

export function AnalyticsCharts() {
  const { history } = useTelemetryStore();

  const data = history.map(frame => {
    let maxTemp = 0;
    let totalPower = 0;
    frame.racks.forEach(r => {
      r.nodes.forEach(n => {
        maxTemp = Math.max(maxTemp, n.gpu_temperature);
        totalPower += n.gpu_power;
      });
    });
    return {
      time: frame.tick,
      maxTemp,
      totalPower
    };
  });

  return (
    <div className="grid grid-cols-2 gap-4">
      <div className="bg-dark border border-cyan/30 p-4 h-64">
        <h3 className="text-cyan mb-2">Max Temperature</h3>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#333" />
            <XAxis dataKey="time" stroke="#00e5ff" />
            <YAxis stroke="#00e5ff" domain={['auto', 'auto']} />
            <Tooltip contentStyle={{backgroundColor: '#0a0e17', borderColor: '#00e5ff'}} />
            <Line type="monotone" dataKey="maxTemp" stroke="#ff0000" dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div className="bg-dark border border-cyan/30 p-4 h-64">
        <h3 className="text-cyan mb-2">Total Power</h3>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#333" />
            <XAxis dataKey="time" stroke="#00e5ff" />
            <YAxis stroke="#00e5ff" domain={['auto', 'auto']} />
            <Tooltip contentStyle={{backgroundColor: '#0a0e17', borderColor: '#00e5ff'}} />
            <Line type="monotone" dataKey="totalPower" stroke="#00e5ff" dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
