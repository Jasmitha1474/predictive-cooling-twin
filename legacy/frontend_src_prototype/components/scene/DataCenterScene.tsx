import React, { Suspense } from 'react';
import { Canvas } from '@react-three/fiber';
import { CameraController } from './CameraController';
import { DataCenterRoom } from './DataCenterRoom';
import { ServerRack } from './ServerRack';
import { CoolingUnit } from './CoolingUnit';
import { CoolantPipe } from './CoolantPipe';
import { ThermalOverlay } from './ThermalOverlay';
import { useTelemetryStore } from '../../store/telemetryStore';
import { EffectComposer, Bloom } from '@react-three/postprocessing';

export function DataCenterScene() {
  const { latestFrame, currentView } = useTelemetryStore();
  const racks = latestFrame?.racks || [];

  return (
    <Canvas
      style={{ background: '#0a0e17' }}
      camera={{ position: [0, 12, 18], fov: 50 }}
      dpr={[1, 2]}
    >
      <fog attach="fog" args={['#0a0e17', 10, 40]} />
      <ambientLight intensity={0.5} />
      <directionalLight position={[10, 20, 10]} intensity={1.5} />
      
      <Suspense fallback={null}>
        <DataCenterRoom />
        
        {racks.map((rack, i) => (
          <ServerRack key={rack.rack_id} rackData={rack} position={[(i - racks.length / 2) * 2 + 1, 0, 0]} />
        ))}
        
        <CoolingUnit position={[-8, 0, -5]} />
        
        <ThermalOverlay />
        <CameraController />
        
        <EffectComposer>
          <Bloom luminanceThreshold={0.2} luminanceSmoothing={0.9} height={300} />
        </EffectComposer>
      </Suspense>
    </Canvas>
  );
}
