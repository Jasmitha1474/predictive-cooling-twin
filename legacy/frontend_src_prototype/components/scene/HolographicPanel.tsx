import React from 'react';
import { Html } from '@react-three/drei';
import { NodeData } from '../../types/telemetry';

interface Props {
  nodeData: NodeData;
}

export function HolographicPanel({ nodeData }: Props) {
  return (
    <Html position={[0.6, 0.2, 0]} center transform sprite>
      <div className="holographic-panel w-48 text-xs">
        <div className="font-bold border-b border-cyan-500 pb-1 mb-1">{nodeData.node_id}</div>
        <div>Temp: {nodeData.gpu_temperature.toFixed(1)}°C</div>
        <div>Power: {nodeData.gpu_power.toFixed(0)}W</div>
        <div>Util: {nodeData.gpu_utilization.toFixed(0)}%</div>
        <div>Mem: {nodeData.gpu_memory.toFixed(0)}MB</div>
      </div>
    </Html>
  );
}
