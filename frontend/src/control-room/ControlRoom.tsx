import { Html } from '@react-three/drei';
import { useEffect, useState } from 'react';
import { CONTROL_ROOM_POS } from '../scene/layout';
import { thermalBand } from '../scene/thermal';
import { getJSON } from '../telemetry/connection';
import { useTelemetry } from '../telemetry/store';

const BAND_CLS = { normal: 'text-sky-300', elevated: 'text-yellow-300', warning: 'text-orange-400', critical: 'text-red-400' };

/** Virtual control room: wall displays rendered as HTML planes inside the 3D scene. */
export function ControlRoom() {
  const p = CONTROL_ROOM_POS;
  // HTML screens are DOM overlays and are not hidden by walls, so mount them only in this view
  const inRoom = useTelemetry((s) => s.view === 'control-room');
  return (
    <group position={p}>
      <mesh position={[0, 0.4, 1.5]}>
        <boxGeometry args={[5, 0.8, 1]} />
        <meshStandardMaterial color="#1a2330" metalness={0.7} roughness={0.4} />
      </mesh>
      {[-3.6, 0, 3.6].map((x, i) => (
        <group key={x} position={[x, 2.2, -1.5]} rotation-y={(-x / 3.6) * 0.35}>
          <mesh position={[0, 0, -0.03]}>
            <boxGeometry args={[3.3, 2.1, 0.05]} />
            <meshStandardMaterial color="#05090f" metalness={0.5} roughness={0.6} />
          </mesh>
          {inRoom && (
            <Html transform distanceFactor={1.55} position={[0, 0, 0.01]} occlude={false}>
              {i === 0 ? <FleetScreen /> : i === 1 ? <CoolingScreen /> : <ComparisonScreen />}
            </Html>
          )}
        </group>
      ))}
    </group>
  );
}

function Screen({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="h-[520px] w-[820px] overflow-hidden rounded border border-cyan-500/40 bg-slate-950/90 p-4 font-mono text-[15px] text-slate-200">
      <div className="mb-3 text-lg font-semibold tracking-widest text-cyan-300">{title}</div>
      {children}
    </div>
  );
}

function FleetScreen() {
  const frame = useTelemetry((s) => s.frame);
  if (!frame) return <Screen title="GPU FLEET">waiting for backend…</Screen>;
  const racks = [...new Set(frame.gpus.map((g) => g.rack))];
  return (
    <Screen title="GPU FLEET · twin temperature (SIMULATED) · power (MEASURED)">
      <div className="grid grid-cols-2 gap-3">
        {racks.map((r) => {
          const gs = frame.gpus.filter((g) => g.rack === r);
          return (
            <div key={r} className="rounded border border-slate-700 p-2">
              <div className="mb-1 text-cyan-200">{r}</div>
              {gs.map((g) => {
                const b = thermalBand(g.simulated.twin_temperature, frame.threshold_C);
                return (
                  <div key={g.gpu_id} className="flex justify-between text-[13px]">
                    <span className="text-slate-400">{g.gpu_id.split('-')[1]}</span>
                    <span className={BAND_CLS[b]}>{g.simulated.twin_temperature.toFixed(1)} °C</span>
                    <span>{g.measured.gpu_power?.toFixed(0) ?? '—'} W</span>
                    <span className="text-slate-500">{g.workload.label}</span>
                  </div>
                );
              })}
            </div>
          );
        })}
      </div>
    </Screen>
  );
}

function CoolingScreen() {
  const frame = useTelemetry((s) => s.frame);
  const events = useTelemetry((s) => s.events);
  const model = useTelemetry((s) => s.hello?.model);
  if (!frame) return <Screen title="COOLING">waiting for backend…</Screen>;
  const meanDemand = frame.gpus.reduce((a, g) => a + g.simulated.cooling_demand, 0) / frame.gpus.length;
  const power = frame.gpus.reduce((a, g) => a + (g.measured.gpu_power ?? 0), 0);
  return (
    <Screen title="COOLING · CONTROL · EVENTS">
      <div className="grid grid-cols-2 gap-x-8 gap-y-1">
        <span className="text-slate-400">controller</span><span className="text-amber-300">{frame.controller_mode.toUpperCase()}</span>
        <span className="text-slate-400">model</span><span>{model?.state}{model?.state !== 'ACTIVE' ? ' (persistence forecast)' : ` · ${model?.model_id}`}</span>
        <span className="text-slate-400">fleet power (measured)</span><span>{(power / 1000).toFixed(2)} kW</span>
        <span className="text-slate-400">mean cooling demand (sim)</span><span>{(meanDemand * 100).toFixed(0)} %</span>
        <span className="text-slate-400">total coolant flow (sim)</span><span>{frame.cdu.total_flow_lpm.toFixed(1)} L/min</span>
        <span className="text-slate-400">heat removed (sim)</span><span>{(frame.cdu.total_heat_removed_w / 1000).toFixed(2)} kW</span>
        <span className="text-slate-400">est. pump power (rel.)</span><span>{frame.cdu.est_pump_power_rel.toFixed(0)}</span>
        <span className="text-slate-400">threshold</span><span>{frame.threshold_C.toFixed(1)} °C</span>
      </div>
      <div className="mt-4 text-cyan-300">PREDICTED THERMAL EVENTS</div>
      <div className="mt-1 space-y-0.5 text-[13px]">
        {events.slice(-9).reverse().map((e, i) => (
          <div key={i} className={e.type === 'thermal_event_predicted' ? 'text-amber-300' : 'text-slate-500'}>
            t={e.sim_time_s}s {e.gpu_id} {e.type === 'thermal_event_predicted' ? `peak ${e.predicted_peak_C?.toFixed(1)} °C predicted` : 'cleared'}
          </div>
        ))}
        {!events.length && <div className="text-slate-500">none so far</div>}
      </div>
    </Screen>
  );
}

interface E2 { label?: string; traces: { n_series: number; n_jobs: number }; summary: Record<string, Record<string, { total?: number | null; median?: number | null }> & { est_pump_energy_vs_baseline_ratio?: number }> }

function ComparisonScreen() {
  const [e2, setE2] = useState<{ final: E2 | null; pre: E2 | null } | null>(null);
  useEffect(() => {
    getJSON<Record<string, unknown>>('/api/results')
      .then((r) => setE2({ final: r['e2_results.json'] as E2 | null, pre: r['e2_results_preliminary.json'] as E2 | null }))
      .catch(() => setE2({ final: null, pre: null }));
  }, []);
  const data = e2?.final ?? e2?.pre;
  return (
    <Screen title="REACTIVE vs PREDICTIVE · from experiment file">
      {!data && <div className="text-slate-400">No comparison results file found on the backend.</div>}
      {data && (
        <>
          <div className="mb-2 text-[13px] text-amber-300">
            {e2?.final ? 'final experiment' : `PRELIMINARY: ${data.label ?? ''}`} · {data.traces.n_series} real traces / {data.traces.n_jobs} jobs · simulated response
          </div>
          <table className="w-full text-[14px]">
            <thead className="text-slate-400">
              <tr><td>controller</td><td>time above thr (s)</td><td>median peak (°C)</td><td>pump energy vs reactive</td></tr>
            </thead>
            <tbody>
              {Object.entries(data.summary).map(([c, m]) => (
                <tr key={c}>
                  <td className="text-cyan-200">{c}</td>
                  <td>{m.time_above_threshold_s?.total?.toFixed(0)}</td>
                  <td>{m.peak_Tj_C?.median?.toFixed(2)}</td>
                  <td>{(m.est_pump_energy_vs_baseline_ratio as number | undefined)?.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </Screen>
  );
}
