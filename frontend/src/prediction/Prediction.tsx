import { Html, Line } from '@react-three/drei';
import { useMemo } from 'react';
import * as THREE from 'three';
import { RACK, nodePosition, type RackLayout } from '../scene/layout';
import { thermalColor } from '../scene/thermal';
import { useTelemetry } from '../telemetry/store';
import type { GpuFrame, Num } from '../telemetry/types';

const fmt = (x: Num | undefined, d = 1) => (x === null || x === undefined ? null : x.toFixed(d));

/** Holographic panel + 3D forecast path next to the selected GPU. Only non-null fields are shown. */
export function PredictionHologram({ racks }: { racks: RackLayout[] }) {
  const gpuId = useTelemetry((s) => s.selectedGpu);
  const g = useTelemetry((s) => (gpuId ? s.byGpu[gpuId] : undefined));
  const thr = useTelemetry((s) => s.frame?.threshold_C ?? 60);
  const active = useTelemetry((s) => (gpuId ? !!s.activeEvents[gpuId] : false));
  const model = useTelemetry((s) => s.hello?.model);
  const rack = racks.find((r) => gpuId && r.gpus.includes(gpuId));
  if (!gpuId || !g || !rack) return null;
  const base = nodePosition(rack, gpuId);
  const anchor = new THREE.Vector3(base.x + rack.side * 1.6, base.y + 0.9, base.z + RACK.d / 2 + 0.2);
  return (
    <group>
      <PredictionPath g={g} thr={thr} origin={new THREE.Vector3(anchor.x - 0.9, anchor.y - 0.9, anchor.z + 0.05)} />
      <Html position={anchor} center distanceFactor={3.2} zIndexRange={[20, 0]}>
        <Panel g={g} thr={thr} active={active} modelState={model?.state ?? 'UNKNOWN'} />
      </Html>
    </group>
  );
}

function Row({ k, v, unit, tag }: { k: string; v: string | null; unit: string; tag: 'M' | 'P' | 'S' }) {
  if (v === null) return null;
  const color = tag === 'M' ? 'text-sky-300' : tag === 'P' ? 'text-amber-300' : 'text-violet-300';
  return (
    <div className="flex justify-between gap-6 font-mono text-[12px] leading-5">
      <span className="text-slate-400">{k}</span>
      <span>
        <span className="text-white">{v}</span> <span className="text-slate-400">{unit}</span>{' '}
        <span className={`${color} text-[10px]`}>{tag === 'M' ? 'MEASURED' : tag === 'P' ? 'PREDICTED' : 'SIMULATED'}</span>
      </span>
    </div>
  );
}

function Panel({ g, thr, active, modelState }: { g: GpuFrame; thr: number; active: boolean; modelState: string }) {
  const m = g.measured;
  const p = g.predicted;
  const s = g.simulated;
  const ml = p.source === 'ml_model';
  return (
    <div className={`w-[330px] rounded-md border bg-slate-950/80 p-3 backdrop-blur ${active ? 'border-amber-400' : 'border-cyan-400/60'} pointer-events-none`}>
      <div className="mb-1 flex items-baseline justify-between font-mono">
        <span className="text-sm font-semibold text-cyan-200">GPU NODE {g.gpu_id}</span>
        <span className="text-[10px] text-slate-400">workload: {g.workload.label} (dataset label)</span>
      </div>
      {active && <div className="mb-1 font-mono text-[12px] font-semibold text-amber-300">THERMAL EVENT PREDICTED</div>}
      <Row k="UTIL" v={fmt(m.gpu_utilization, 0)} unit="%" tag="M" />
      <Row k="POWER" v={fmt(m.gpu_power, 1)} unit="W" tag="M" />
      <Row k="TEMP (source system)" v={fmt(m.gpu_temperature, 0)} unit="°C" tag="M" />
      <Row k="MEM UTIL" v={fmt(m.memory_utilization, 0)} unit="%" tag="M" />
      <Row k="SM CLOCK" v={fmt(m.sm_clock_mhz, 0)} unit="MHz" tag="M" />
      <Row k="MEM CLOCK" v={fmt(m.mem_clock_mhz, 0)} unit="MHz" tag="M" />
      <div className="my-1 border-t border-slate-700" />
      <Row k="TWIN TEMP" v={fmt(s.twin_temperature, 1)} unit="°C" tag="S" />
      <Row k="VALVE" v={fmt(s.valve_position * 100, 0)} unit="%" tag="S" />
      <Row k="FLOW" v={fmt(s.coolant_flow_lpm, 2)} unit="L/min" tag="S" />
      <div className="my-1 border-t border-slate-700" />
      <div className="font-mono text-[11px] text-amber-200">
        FORECAST · {ml ? `ML model ${p.model_id}` : 'persistence baseline (no ML model loaded)'}
      </div>
      {p.horizons_s.map((h, i) => (
        <Row key={h} k={`+${h} s power`} v={fmt(p.power[i], 0)} unit="W" tag="P" />
      ))}
      {p.horizons_s.map((h, i) => (
        <Row key={`t${h}`} k={`+${h} s twin temp`} v={fmt(p.twin_temperature_if_valve_held[i], 1)} unit="°C" tag="P" />
      ))}
      {p.temperature_measured_system &&
        p.horizons_s.map((h, i) => (
          <Row key={`m${h}`} k={`+${h} s source-system temp`} v={fmt(p.temperature_measured_system![i], 1)} unit="°C" tag="P" />
        ))}
      <div className="mt-1 font-mono text-[10px] text-slate-500">
        threshold {thr.toFixed(1)} °C · model {modelState} · trace {g.trace.series_id.slice(0, 14)}… t={g.trace.t_index}s
      </div>
    </div>
  );
}

/** NOW -> +30 -> +45 -> +60 s twin-temperature forecast as a 3D line with a threshold reference. */
function PredictionPath({ g, thr, origin }: { g: GpuFrame; thr: number; origin: THREE.Vector3 }) {
  const pts = useMemo(() => {
    const temps = [g.simulated.twin_temperature, ...g.predicted.twin_temperature_if_valve_held.map((x) => x ?? g.simulated.twin_temperature)];
    const hs = [0, ...g.predicted.horizons_s];
    const y = (t: number) => (t - (thr - 20)) / 20; // 0 at thr-20, 1 at threshold
    return hs.map((h, i) => new THREE.Vector3(origin.x + (h / 60) * 1.8, origin.y + y(temps[i]) * 0.9, origin.z));
  }, [g, thr, origin]);
  const temps = [g.simulated.twin_temperature, ...g.predicted.twin_temperature_if_valve_held.map((x) => x ?? 0)];
  const thrY = origin.y + 0.9;
  return (
    <group>
      <Line points={[new THREE.Vector3(origin.x, thrY, origin.z), new THREE.Vector3(origin.x + 1.8, thrY, origin.z)]} color="#ff5a3c" dashed dashSize={0.05} gapSize={0.04} lineWidth={1} />
      <Line points={pts} color="#ffd36b" lineWidth={2} />
      {pts.map((p, i) => (
        <mesh key={i} position={p}>
          <sphereGeometry args={[0.035, 12, 12]} />
          <meshBasicMaterial color={thermalColor(temps[i], thr)} toneMapped={false} />
        </mesh>
      ))}
    </group>
  );
}
