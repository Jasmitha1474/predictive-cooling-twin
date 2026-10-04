import React from 'react';
import { useTelemetryStore } from '../../store/telemetryStore';

export function ThermalOverlay() {
  const { thermalViewEnabled } = useTelemetryStore();
  
  if (!thermalViewEnabled) return null;

  return (
    <mesh position={[0, 5, 0]} rotation={[-Math.PI / 2, 0, 0]}>
      <planeGeometry args={[20, 15]} />
      <meshBasicMaterial color="#ff0000" transparent opacity={0.1} />
    </mesh>
  );
}
