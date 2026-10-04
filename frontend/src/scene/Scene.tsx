import { Canvas } from '@react-three/fiber';
import { XR, createXRStore } from '@react-three/xr';
import { Suspense, useMemo } from 'react';
import { ControlRoom } from '../control-room/ControlRoom';
import { CoolingLoop } from '../cooling/CoolingLoop';
import { GpuDetail } from '../gpu/GpuDetail';
import { PredictionHologram } from '../prediction/Prediction';
import { Racks } from '../racks/Racks';
import { useTelemetry } from '../telemetry/store';
import { CameraDirector } from './CameraDirector';
import { buildLayout } from './layout';
import { Room } from './Room';

export const xrStore = createXRStore({ emulate: false });

export function Scene() {
  const layout = useTelemetry((s) => s.hello?.layout);
  const racks = useMemo(() => buildLayout(layout ?? []), [layout]);
  const selectGpu = useTelemetry((s) => s.selectGpu);
  return (
    <Canvas
      camera={{ position: [9, 4.4, 14], fov: 45, near: 0.05, far: 200 }}
      dpr={[1, 1.75]}
      gl={{ antialias: true }}
      onPointerMissed={() => selectGpu(null)}
    >
      <XR store={xrStore}>
        <color attach="background" args={['#05080d']} />
        <fog attach="fog" args={['#05080d', 18, 48]} />
        <ambientLight intensity={0.55} color="#9ec9ff" />
        <directionalLight position={[8, 12, 6]} intensity={0.9} color="#dbe9ff" />
        <pointLight position={[0, 5, 0]} intensity={18} distance={22} color="#4fb3ff" />
        <Suspense fallback={null}>
          <Room />
          <Racks racks={racks} />
          <CoolingLoop racks={racks} />
          <GpuDetail racks={racks} />
          <PredictionHologram racks={racks} />
          <ControlRoom />
        </Suspense>
        <CameraDirector racks={racks} />
      </XR>
    </Canvas>
  );
}
