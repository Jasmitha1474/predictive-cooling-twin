import { Label as Text } from '../scene/Label';
import { useFrame } from '@react-three/fiber';
import { useMemo, useRef } from 'react';
import * as THREE from 'three';
import { UNITS_PER_S_PER_LPM } from '../cooling/CoolingLoop';
import { RACK, nodePosition, type RackLayout } from '../scene/layout';
import { damp, thermalColor } from '../scene/thermal';
import { useTelemetry } from '../telemetry/store';

/**
 * Close-up of the selected GPU (GPU view): die, HBM stacks, cold plate with internal
 * channels and coolant particles, temperature sensors. Placed in the aisle in front of
 * its rack slot.
 *  die colour        <- simulated.twin_temperature
 *  cold-plate colour <- simulated.cold_plate_temperature
 *  channel particles <- simulated.coolant_flow_lpm of this GPU branch
 */
export function GpuDetail({ racks }: { racks: RackLayout[] }) {
  const gpuId = useTelemetry((s) => s.selectedGpu);
  const view = useTelemetry((s) => s.view);
  const rack = racks.find((r) => gpuId && r.gpus.includes(gpuId));
  if (!gpuId || !rack || view !== 'gpu') return null;
  const p = nodePosition(rack, gpuId);
  const pos = new THREE.Vector3(p.x, Math.max(1.2, p.y + 0.2), p.z + RACK.d / 2 + 1.0);
  return <DetailModel gpuId={gpuId} pos={pos} />;
}

const CHANNEL = new THREE.CatmullRomCurve3(
  Array.from({ length: 9 }, (_, i) => new THREE.Vector3(-0.32 + (i % 2) * 0.64, 0.1, -0.3 + i * 0.075)),
  false,
  'catmullrom',
  0.0,
);

function DetailModel({ gpuId, pos }: { gpuId: string; pos: THREE.Vector3 }) {
  const die = useRef<THREE.MeshStandardMaterial>(null!);
  const plate = useRef<THREE.MeshPhysicalMaterial>(null!);
  const parts = useRef<THREE.InstancedMesh>(null!);
  const tj = useRef<number | null>(null);
  const tcp = useRef<number | null>(null);
  const speed = useRef(0);
  const N = 40;
  const u = useMemo(() => Float32Array.from({ length: N }, (_, i) => i / N), []);
  const len = useMemo(() => CHANNEL.getLength(), []);
  const o = useMemo(() => new THREE.Object3D(), []);
  const v = useMemo(() => new THREE.Vector3(), []);
  const sensors = useTelemetry((s) => {
    const g = s.byGpu[gpuId];
    return g ? `T_j ${g.simulated.twin_temperature.toFixed(1)} °C  ·  T_cp ${g.simulated.cold_plate_temperature.toFixed(1)} °C  (SIMULATED)` : '';
  });

  useFrame((_, dt) => {
    const s = useTelemetry.getState();
    const g = s.byGpu[gpuId];
    if (!g || !s.frame) return;
    const thr = s.frame.threshold_C;
    tj.current = tj.current === null ? g.simulated.twin_temperature : damp(tj.current, g.simulated.twin_temperature, 3, dt);
    tcp.current = tcp.current === null ? g.simulated.cold_plate_temperature : damp(tcp.current, g.simulated.cold_plate_temperature, 3, dt);
    thermalColor(tj.current, thr, die.current.color);
    die.current.emissive.copy(die.current.color);
    die.current.emissiveIntensity = 0.5;
    thermalColor(tcp.current, thr, plate.current.color);
    speed.current = damp(speed.current, g.simulated.coolant_flow_lpm * UNITS_PER_S_PER_LPM * 0.35, 2, dt);
    for (let i = 0; i < N; i++) {
      u[i] = (u[i] + (speed.current * Math.min(dt, 0.1)) / len) % 1;
      CHANNEL.getPointAt(u[i], v);
      o.position.copy(v);
      o.scale.setScalar(0.018);
      o.updateMatrix();
      parts.current.setMatrixAt(i, o.matrix);
    }
    parts.current.instanceMatrix.needsUpdate = true;
  });

  return (
    <group position={pos}>
      {/* substrate */}
      <mesh position={[0, -0.05, 0]}>
        <boxGeometry args={[1.0, 0.04, 0.8]} />
        <meshStandardMaterial color="#1d3b2a" roughness={0.7} />
      </mesh>
      {/* GPU die */}
      <mesh position={[0, 0, 0]}>
        <boxGeometry args={[0.42, 0.05, 0.42]} />
        <meshStandardMaterial ref={die} roughness={0.3} metalness={0.2} />
      </mesh>
      {/* HBM stacks (neutral: the twin does not model memory temperature) */}
      {[-0.33, 0.33].flatMap((x) =>
        [-0.13, 0.13].map((z) => (
          <mesh key={`${x}${z}`} position={[x, 0, z]}>
            <boxGeometry args={[0.14, 0.06, 0.2]} />
            <meshStandardMaterial color="#3d4a57" metalness={0.6} roughness={0.4} />
          </mesh>
        )),
      )}
      {/* cold plate (translucent) with serpentine channel */}
      <mesh position={[0, 0.1, 0]}>
        <boxGeometry args={[0.86, 0.08, 0.72]} />
        <meshPhysicalMaterial ref={plate} transparent opacity={0.35} roughness={0.15} metalness={0.4} depthWrite={false} />
      </mesh>
      <instancedMesh ref={parts} args={[undefined, undefined, N]} frustumCulled={false}>
        <sphereGeometry args={[1, 6, 6]} />
        <meshBasicMaterial color="#5fd3ff" toneMapped={false} />
      </instancedMesh>
      {/* sensors */}
      {[
        [0.0, 0.03, 0.24],
        [0.4, 0.15, 0.3],
      ].map((p, i) => (
        <mesh key={i} position={p as [number, number, number]}>
          <sphereGeometry args={[0.022, 10, 10]} />
          <meshBasicMaterial color="#ffffff" />
        </mesh>
      ))}
      <Text position={[0, 0.35, 0]} fontSize={0.06} color="#cfe9ff" anchorX="center">
        {`${gpuId} · die · HBM · two-phase cold plate`}
      </Text>
      <Text position={[0, 0.27, 0]} fontSize={0.05} color="#ffd36b" anchorX="center">
        {sensors}
      </Text>
    </group>
  );
}
