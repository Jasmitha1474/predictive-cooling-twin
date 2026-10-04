import { Label as Text } from '../scene/Label';
import { useFrame } from '@react-three/fiber';
import { useMemo, useRef } from 'react';
import * as THREE from 'three';
import { CDU_POS, pipeCurves, valvePosition, type RackLayout } from '../scene/layout';
import { damp } from '../scene/thermal';
import { rackAggregate, useTelemetry } from '../telemetry/store';

const PARTICLES_PER_PIPE = 70;
// Visual scale: particle speed (scene units per second) per L/min of simulated flow per GPU branch.
export const UNITS_PER_S_PER_LPM = 0.55;

/**
 * Coolant loop: CDU -> supply pipe -> valve -> rack riser -> cold plates -> return -> CDU.
 * Particle speed = UNITS_PER_S_PER_LPM x (rack simulated flow / GPUs in rack).
 * Return-side particles whiten with simulated vapour generation (two-phase return).
 * Nothing moves unless the backend reports flow.
 */
export function CoolingLoop({ racks }: { racks: RackLayout[] }) {
  return (
    <group>
      {racks.map((r) => (
        <RackBranch key={r.id} rack={r} />
      ))}
      <CDU racks={racks} />
    </group>
  );
}

function RackBranch({ rack }: { rack: RackLayout }) {
  const { sup, ret } = useMemo(() => pipeCurves(rack), [rack]);
  return (
    <group>
      <Pipe curve={sup} color="#2a6ea8" />
      <Pipe curve={ret} color="#6b5aa8" />
      <Particles curve={sup} rack={rack} kind="supply" />
      <Particles curve={ret} rack={rack} kind="return" />
      <Valve rack={rack} />
    </group>
  );
}

function Pipe({ curve, color }: { curve: THREE.Curve<THREE.Vector3>; color: string }) {
  const geo = useMemo(() => new THREE.TubeGeometry(curve, 160, 0.07, 10, false), [curve]);
  return (
    <mesh geometry={geo}>
      <meshPhysicalMaterial color={color} transparent opacity={0.28} roughness={0.1} metalness={0.2} depthWrite={false} />
    </mesh>
  );
}

function Particles({ curve, rack, kind }: { curve: THREE.Curve<THREE.Vector3>; rack: RackLayout; kind: 'supply' | 'return' }) {
  const mesh = useRef<THREE.InstancedMesh>(null!);
  const length = useMemo(() => curve.getLength(), [curve]);
  const u = useMemo(() => Float32Array.from({ length: PARTICLES_PER_PIPE }, (_, i) => i / PARTICLES_PER_PIPE), []);
  const speed = useRef(0);
  const vapour = useRef(0);
  const tmp = useMemo(() => new THREE.Object3D(), []);
  const p = useMemo(() => new THREE.Vector3(), []);
  const col = useMemo(() => new THREE.Color(), []);

  useFrame((_, dt) => {
    const s = useTelemetry.getState();
    const agg = rackAggregate(s.frame, rack.id);
    const perGpuFlow = rack.gpus.length ? agg.flow / rack.gpus.length : 0;
    speed.current = damp(speed.current, perGpuFlow * UNITS_PER_S_PER_LPM, 2, dt);
    const vap = s.frame ? s.frame.gpus.filter((g) => g.rack === rack.id).reduce((a, g) => a + g.simulated.vapour_generation_g_s, 0) : 0;
    vapour.current = damp(vapour.current, vap, 2, dt);
    const du = (speed.current * Math.min(dt, 0.1)) / length;
    const white = Math.min(1, vapour.current / 6); // ~6 g/s per rack -> fully white (visual scale)
    col.set(kind === 'supply' ? '#3fc4ff' : '#8f7cff');
    if (kind === 'return') col.lerp(new THREE.Color('#f4f8ff'), white);
    for (let i = 0; i < u.length; i++) {
      u[i] = (u[i] + du) % 1;
      curve.getPointAt(u[i], p);
      tmp.position.copy(p);
      const sc = kind === 'return' ? 0.035 + 0.025 * white * ((i % 3) / 2) : 0.035;
      tmp.scale.setScalar(sc);
      tmp.updateMatrix();
      mesh.current.setMatrixAt(i, tmp.matrix);
      mesh.current.setColorAt(i, col);
    }
    mesh.current.instanceMatrix.needsUpdate = true;
    if (mesh.current.instanceColor) mesh.current.instanceColor.needsUpdate = true;
  });

  return (
    <instancedMesh ref={mesh} args={[undefined, undefined, PARTICLES_PER_PIPE]} frustumCulled={false}>
      <sphereGeometry args={[1, 8, 8]} />
      <meshBasicMaterial toneMapped={false} />
    </instancedMesh>
  );
}

/** Rack valve: handle angle = mean simulated valve_position of the rack's GPU branches x 90 deg. */
function Valve({ rack }: { rack: RackLayout }) {
  const handle = useRef<THREE.Group>(null!);
  const v = useRef(0);
  const pct = useTelemetry((s) => Math.round(rackAggregate(s.frame, rack.id).valve * 100));
  const pos = useMemo(() => valvePosition(rack), [rack]);
  const select = useTelemetry((s) => s.setView);
  useFrame((_, dt) => {
    const s = useTelemetry.getState();
    const agg = rackAggregate(s.frame, rack.id);
    v.current = damp(v.current, agg.valve, 4, dt);
    handle.current.rotation.y = v.current * (Math.PI / 2);
  });
  return (
    <group position={pos} onClick={(e) => { e.stopPropagation(); select('cooling'); }}>
      <mesh rotation-z={Math.PI / 2}>
        <cylinderGeometry args={[0.16, 0.16, 0.38, 20]} />
        <meshStandardMaterial color="#8aa4b8" metalness={0.9} roughness={0.25} />
      </mesh>
      <mesh position={[0, 0.22, 0]}>
        <cylinderGeometry args={[0.03, 0.03, 0.18, 8]} />
        <meshStandardMaterial color="#cfd8df" metalness={0.9} roughness={0.2} />
      </mesh>
      <group ref={handle} position={[0, 0.33, 0]}>
        <mesh position={[0.18, 0, 0]}>
          <boxGeometry args={[0.38, 0.04, 0.07]} />
          <meshStandardMaterial color="#e2b23a" metalness={0.5} roughness={0.4} />
        </mesh>
      </group>
      <Text position={[0, 0.62, 0]} fontSize={0.13} color="#ffd36b" anchorX="center">
        {`VALVE ${pct}%`}
      </Text>
    </group>
  );
}

/** Coolant distribution unit: pump impeller speed follows the simulated total flow. */
function CDU({ racks }: { racks: RackLayout[] }) {
  const impeller = useRef<THREE.Group>(null!);
  const w = useRef(0);
  const label = useTelemetry((s) =>
    s.frame
      ? `CDU  (SIMULATED)\nflow ${s.frame.cdu.total_flow_lpm.toFixed(1)} L/min\nheat ${(s.frame.cdu.total_heat_removed_w / 1000).toFixed(2)} kW\npump ${s.frame.cdu.est_pump_power_rel.toFixed(0)} (relative)`
      : 'CDU  (no data)',
  );
  const setView = useTelemetry((s) => s.setView);
  const maxFlow = useMemo(() => racks.reduce((a, r) => a + r.gpus.length, 0) * 6, [racks]); // Q_max 6 L/min per branch
  useFrame((_, dt) => {
    const s = useTelemetry.getState();
    const flow = s.frame?.cdu.total_flow_lpm ?? 0;
    w.current = damp(w.current, (flow / Math.max(1, maxFlow)) * 14, 2, dt); // rad/s, visual scale
    impeller.current.rotation.z += w.current * dt;
  });
  return (
    <group position={CDU_POS} onClick={(e) => { e.stopPropagation(); setView('cooling'); }}>
      <mesh position={[0, 1.1, 0]}>
        <boxGeometry args={[2.4, 2.2, 1.2]} />
        <meshStandardMaterial color="#18222f" metalness={0.8} roughness={0.35} />
      </mesh>
      {/* heat-exchanger plate stack */}
      {Array.from({ length: 9 }, (_, i) => (
        <mesh key={i} position={[-0.55 + i * 0.07, 1.25, -0.62]}>
          <boxGeometry args={[0.03, 1.1, 0.05]} />
          <meshStandardMaterial color="#5b7c95" metalness={0.9} roughness={0.3} />
        </mesh>
      ))}
      {/* pump housing + impeller */}
      <mesh position={[0.6, 0.6, -0.65]} rotation-x={Math.PI / 2}>
        <cylinderGeometry args={[0.32, 0.32, 0.12, 28]} />
        <meshStandardMaterial color="#2c3e50" metalness={0.8} roughness={0.3} transparent opacity={0.6} />
      </mesh>
      <group ref={impeller} position={[0.6, 0.6, -0.72]}>
        {Array.from({ length: 6 }, (_, i) => (
          <mesh key={i} rotation-z={(i * Math.PI) / 3} position={[0, 0, 0]}>
            <boxGeometry args={[0.5, 0.06, 0.02]} />
            <meshStandardMaterial color="#7fe3ff" emissive="#1a6a88" emissiveIntensity={0.6} />
          </mesh>
        ))}
      </group>
      <Text position={[0, 2.9, 0]} fontSize={0.17} color="#a9dcff" anchorX="center" lineHeight={1.3}>
        {label}
      </Text>
    </group>
  );
}
