import { Label as Text } from '../scene/Label';
import { useFrame } from '@react-three/fiber';
import { useMemo, useRef } from 'react';
import * as THREE from 'three';
import { NODE, RACK, nodePosition, type RackLayout } from '../scene/layout';
import { damp, thermalColor } from '../scene/thermal';
import { useTelemetry } from '../telemetry/store';

/**
 * Racks and GPU nodes. Every visual state is read from the latest backend frame:
 *  - node colour/emissive  <- simulated.twin_temperature (relative to backend threshold)
 *  - status LED blink rate <- measured.gpu_utilization
 *  - amber outline         <- active thermal_event_predicted for that GPU
 */
export function Racks({ racks }: { racks: RackLayout[] }) {
  return (
    <group>
      {racks.map((r) => (
        <Rack key={r.id} rack={r} />
      ))}
    </group>
  );
}

function Rack({ rack }: { rack: RackLayout }) {
  const selectRack = useTelemetry((s) => s.selectRack);
  const selected = useTelemetry((s) => s.selectedRack === rack.id);
  return (
    <group>
      <group position={rack.pos}>
        {/* frame */}
        {/* frame is not raycast so clicks reach the GPU nodes inside; the rack is selected via its top cap */}
        <mesh position={[0, RACK.h / 2, 0]} raycast={() => null}>
          <boxGeometry args={[RACK.w, RACK.h, RACK.d]} />
          <meshStandardMaterial color="#141b26" metalness={0.85} roughness={0.35} transparent opacity={0.55} />
        </mesh>
        <mesh
          position={[0, RACK.h + 0.02, 0]}
          onClick={(e) => {
            e.stopPropagation();
            selectRack(rack.id);
          }}
        >
          <boxGeometry args={[RACK.w, 0.05, RACK.d]} />
          <meshStandardMaterial color={selected ? '#2f6f8f' : '#1b2a38'} metalness={0.8} roughness={0.3} />
        </mesh>
        <lineSegments position={[0, RACK.h / 2, 0]}>
          <edgesGeometry args={[new THREE.BoxGeometry(RACK.w, RACK.h, RACK.d)]} />
          <lineBasicMaterial color={selected ? '#7fe3ff' : '#2b4f6b'} />
        </lineSegments>
        <Text position={[0, RACK.h + 0.25, RACK.d / 2]} fontSize={0.22} color="#a9dcff" anchorX="center">
          {rack.id.replace('R', 'RACK ')}
        </Text>
        <HeatColumn rack={rack} />
      </group>
      {rack.gpus.map((g) => (
        <GpuNode key={g} gpuId={g} pos={nodePosition(rack, g)} />
      ))}
    </group>
  );
}

function GpuNode({ gpuId, pos }: { gpuId: string; pos: THREE.Vector3 }) {
  const body = useRef<THREE.MeshStandardMaterial>(null!);
  const led = useRef<THREE.MeshBasicMaterial>(null!);
  const outline = useRef<THREE.LineSegments>(null!);
  const temp = useRef<number | null>(null);
  const phase = useRef(0);
  const color = useMemo(() => new THREE.Color(), []);
  const selectGpu = useTelemetry((s) => s.selectGpu);
  const isSelected = useTelemetry((s) => s.selectedGpu === gpuId);
  const edges = useMemo(() => new THREE.EdgesGeometry(new THREE.BoxGeometry(NODE.w + 0.04, NODE.h + 0.04, NODE.d + 0.04)), []);

  useFrame((_, dt) => {
    const s = useTelemetry.getState();
    const g = s.byGpu[gpuId];
    const thr = s.frame?.threshold_C ?? 60;
    if (!g) return;
    const target = g.simulated.twin_temperature;
    temp.current = temp.current === null ? target : damp(temp.current, target, 3, dt);
    thermalColor(temp.current, thr, color);
    // restrained: colour always, glow only in thermal view or when near/above threshold
    const glow = s.thermalView ? 0.9 : Math.max(0, Math.min(0.6, (temp.current - (thr - 5)) / 10));
    body.current.color.copy(color).multiplyScalar(s.thermalView ? 1 : 0.35).addScalar(0.04);
    body.current.emissive.copy(color);
    body.current.emissiveIntensity = glow;
    // status LED: blink frequency follows measured utilisation (0-100 % -> 0.3-4 Hz)
    const util = g.measured.gpu_utilization ?? 0;
    phase.current += dt * (0.3 + 3.7 * (util / 100)) * Math.PI * 2;
    led.current.color.setRGB(0.1, 0.4 + 0.6 * (0.5 + 0.5 * Math.sin(phase.current)) * (util > 1 ? 1 : 0.2), 0.6);
    const active = !!s.activeEvents[gpuId];
    outline.current.visible = active || isSelected;
    (outline.current.material as THREE.LineBasicMaterial).color.set(active ? '#ffb020' : '#7fe3ff');
  });

  return (
    <group position={pos}>
      <mesh
        onClick={(e) => {
          e.stopPropagation();
          selectGpu(gpuId);
        }}
      >
        <boxGeometry args={[NODE.w, NODE.h, NODE.d]} />
        <meshStandardMaterial ref={body} metalness={0.6} roughness={0.4} />
      </mesh>
      {/* front bezel vents */}
      <mesh position={[0, 0, NODE.d / 2 + 0.005]}>
        <planeGeometry args={[NODE.w * 0.92, NODE.h * 0.7]} />
        <meshStandardMaterial color="#0c1118" metalness={0.9} roughness={0.5} />
      </mesh>
      <mesh position={[NODE.w / 2 - 0.08, 0, NODE.d / 2 + 0.012]}>
        <circleGeometry args={[0.025, 12]} />
        <meshBasicMaterial ref={led} />
      </mesh>
      <lineSegments ref={outline} geometry={edges}>
        <lineBasicMaterial color="#ffb020" />
      </lineSegments>
      <Text position={[-NODE.w / 2 + 0.05, 0, NODE.d / 2 + 0.012]} fontSize={0.075} color="#7aa7c7" anchorX="left">
        {gpuId}
      </Text>
    </group>
  );
}

/** Thermal view only: translucent column whose colour/height follow the rack's hottest twin temperature. */
function HeatColumn({ rack }: { rack: RackLayout }) {
  const m = useRef<THREE.Mesh>(null!);
  const mat = useRef<THREE.MeshBasicMaterial>(null!);
  const h = useRef(0.01);
  useFrame((_, dt) => {
    const s = useTelemetry.getState();
    m.current.visible = s.thermalView;
    if (!s.thermalView || !s.frame) return;
    const temps = rack.gpus.map((g) => s.byGpu[g]?.simulated.twin_temperature ?? 0);
    const mx = Math.max(...temps);
    const thr = s.frame.threshold_C;
    h.current = damp(h.current, Math.max(0.05, (mx - (thr - 25)) / 10), 3, dt);
    m.current.scale.y = h.current;
    m.current.position.y = RACK.h + 0.4 + h.current / 2;
    thermalColor(mx, thr, mat.current.color);
  });
  return (
    <mesh ref={m}>
      <cylinderGeometry args={[0.35, 0.35, 1, 24, 1, true]} />
      <meshBasicMaterial ref={mat} transparent opacity={0.35} side={THREE.DoubleSide} depthWrite={false} />
    </mesh>
  );
}
