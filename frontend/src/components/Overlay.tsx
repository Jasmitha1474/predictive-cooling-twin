import { useEffect, useState } from 'react';
import { xrStore } from '../scene/Scene';
import { assignTrace, getJSON, postControl } from '../telemetry/connection';
import { useTelemetry } from '../telemetry/store';
import type { CameraView } from '../telemetry/types';

const btn = 'rounded border px-3 py-1.5 font-mono text-[12px] tracking-wider transition-colors';
const on = 'border-cyan-300 bg-cyan-400/20 text-cyan-100';
const off = 'border-slate-600 bg-slate-900/70 text-slate-300 hover:border-cyan-500';

/** Minimal DOM overlay. Status values come from the backend; buttons call the backend API. */
export function Overlay() {
  const connected = useTelemetry((s) => s.connected);
  const hello = useTelemetry((s) => s.hello);
  const frame = useTelemetry((s) => s.frame);
  const view = useTelemetry((s) => s.view);
  const thermal = useTelemetry((s) => s.thermalView);
  const follow = useTelemetry((s) => s.followEvents);
  const { setView, toggleThermal, toggleFollow, setShowResults } = useTelemetry.getState();
  const [paused, setPaused] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [vr, setVr] = useState(false);
  const [showWorkload, setShowWorkload] = useState(false);

  useEffect(() => {
    (navigator as any).xr?.isSessionSupported?.('immersive-vr').then((ok: boolean) => setVr(ok)).catch(() => setVr(false));
  }, []);

  const model = hello?.model;
  const mode = frame?.mode ?? hello?.mode;
  const ctrl = frame?.controller_mode ?? hello?.controller_mode;
  const go = (v: CameraView) => setView(v);

  return (
    <>
      {/* top status */}
      <div className="pointer-events-none fixed left-0 right-0 top-0 flex items-start justify-between p-4 font-mono text-[12px]">
        <div className="space-y-1">
          <div className="text-[15px] font-semibold tracking-[0.25em] text-cyan-200">AI DATA HALL · PREDICTIVE COOLING TWIN</div>
          <div className="flex gap-4">
            <span>SYSTEM: <b className={connected ? 'text-emerald-300' : 'text-red-400'}>{connected ? 'ONLINE' : 'OFFLINE'}</b></span>
            <span>
              MODEL:{' '}
              <b className={model?.state === 'ACTIVE' ? 'text-emerald-300' : 'text-amber-300'}>
                {model?.state === 'ACTIVE' ? `ACTIVE (${model.model_id})` : `${model?.state ?? '—'} · persistence forecast, not ML`}
              </b>
            </span>
            <span>CONTROLLER: <b className="text-amber-200">{ctrl?.toUpperCase() ?? '—'}</b></span>
            {frame && <span className="text-slate-400">t = {frame.sim_time_s}s · threshold {frame.threshold_C.toFixed(1)} °C</span>}
          </div>
        </div>
        <div className={`rounded border px-3 py-1 text-[12px] font-semibold tracking-widest ${mode === 'RESEARCH_DATA_REPLAY' ? 'border-sky-400 text-sky-300' : 'border-violet-400 text-violet-300'}`}>
          {mode === 'RESEARCH_DATA_REPLAY' ? 'RESEARCH DATA REPLAY' : 'DIGITAL TWIN SIMULATION'}
        </div>
      </div>

      {/* provenance legend */}
      <div className="pointer-events-none fixed left-4 top-20 space-y-0.5 font-mono text-[10px]">
        <div className="text-sky-300">■ MEASURED: recorded V100 telemetry (MIT Supercloud)</div>
        <div className="text-amber-300">■ PREDICTED: model forecast</div>
        <div className="text-violet-300">■ SIMULATED: cooling twin (simplified, not CFD)</div>
      </div>

      <EventToasts />
      {showWorkload && <WorkloadPicker onClose={() => setShowWorkload(false)} />}

      {/* bottom controls */}
      <div className="fixed bottom-4 left-0 right-0 flex flex-wrap justify-center gap-2 px-4">
        <button className={`${btn} ${showWorkload ? on : off}`} onClick={() => setShowWorkload((x) => !x)}>WORKLOAD</button>
        <div className="flex">
          {(['reactive', 'predictive'] as const).map((c) => (
            <button key={c} className={`${btn} ${ctrl === c ? on : off}`} onClick={() => postControl({ controller_mode: c })}>
              {c.toUpperCase()}
            </button>
          ))}
        </div>
        <div className="flex">
          {(['RESEARCH_DATA_REPLAY', 'DIGITAL_TWIN_SIMULATION'] as const).map((m) => (
            <button key={m} className={`${btn} ${mode === m ? on : off}`} onClick={() => postControl({ mode: m })}>
              {m === 'RESEARCH_DATA_REPLAY' ? 'REPLAY' : 'TWIN SIM'}
            </button>
          ))}
        </div>
        <button className={`${btn} ${thermal ? on : off}`} onClick={() => { toggleThermal(); go(thermal ? 'overview' : 'thermal'); }}>THERMAL VIEW</button>
        <button className={`${btn} ${view === 'overview' ? on : off}`} onClick={() => useTelemetry.setState({ view: 'overview', selectedGpu: null, selectedRack: null })}>OVERVIEW</button>
        <button className={`${btn} ${view === 'cooling' ? on : off}`} onClick={() => go('cooling')}>COOLING LOOP</button>
        <button className={`${btn} ${view === 'control-room' ? on : off}`} onClick={() => go('control-room')}>CONTROL ROOM</button>
        <button className={`${btn} ${follow ? on : off}`} onClick={toggleFollow}>FOLLOW EVENTS</button>
        <button className={`${btn} ${paused ? on : off}`} onClick={() => postControl({ paused: !paused }).then((r) => setPaused(!!r.paused))}>{paused ? 'RESUME' : 'PAUSE'}</button>
        <div className="flex">
          {[1, 5, 20].map((x) => (
            <button key={x} className={`${btn} ${speed === x ? on : off}`} title="simulated seconds per real second"
              onClick={() => postControl({ speed: x }).then((r) => setSpeed(r.speed))}>
              {x}×
            </button>
          ))}
        </div>
        <button className={`${btn} ${off}`} onClick={() => postControl({ reset: true })}>RESTART TRACES</button>
        <button className={`${btn} ${off}`} onClick={() => setShowResults(true)}>RESULTS</button>
        {vr && <button className={`${btn} ${off}`} onClick={() => xrStore.enterVR()}>ENTER VR</button>}
      </div>
    </>
  );
}

function EventToasts() {
  const events = useTelemetry((s) => s.events);
  const recent = events.filter((e) => e.type === 'thermal_event_predicted').slice(-3).reverse();
  return (
    <div className="pointer-events-none fixed right-4 top-16 w-[300px] space-y-2 font-mono text-[12px]">
      {recent.map((e, i) => (
        <div key={`${e.gpu_id}${e.sim_time_s}${i}`} className="rounded border border-amber-400/70 bg-slate-950/80 p-2">
          <div className="font-semibold text-amber-300">THERMAL EVENT PREDICTED</div>
          <div>{e.gpu_id} · peak {e.predicted_peak_C?.toFixed(1)} °C vs threshold {e.threshold_C?.toFixed(1)} °C</div>
          <div className="text-slate-400">
            {Object.entries(e.predicted_twin_temperature ?? {}).map(([h, t]) => `${h}: ${t.toFixed(1)}`).join(' · ')}
          </div>
          <div className="text-[10px] text-slate-500">t={e.sim_time_s}s · {e.controller_mode} · {e.source}</div>
        </div>
      ))}
    </div>
  );
}

interface TraceInfo { series_id: string; job_id: string; label: string; duration_s: number; has_clocks: boolean }

/** Replays a recorded trace (dataset label shown verbatim) on the selected GPU. No invented workloads. */
function WorkloadPicker({ onClose }: { onClose: () => void }) {
  const [traces, setTraces] = useState<TraceInfo[]>([]);
  const gpu = useTelemetry((s) => s.selectedGpu);
  useEffect(() => {
    getJSON<{ traces: TraceInfo[] }>('/api/traces').then((r) => setTraces(r.traces)).catch(() => setTraces([]));
  }, []);
  return (
    <div className="fixed bottom-20 left-1/2 w-[520px] -translate-x-1/2 rounded border border-cyan-500/60 bg-slate-950/90 p-3 font-mono text-[12px]">
      <div className="mb-2 flex justify-between">
        <span className="font-semibold tracking-widest text-cyan-200">REPLAY RECORDED WORKLOAD</span>
        <button className="text-slate-400" onClick={onClose}>close</button>
      </div>
      <div className="mb-2 text-slate-400">
        {gpu ? `Target: ${gpu}` : 'Select a GPU in the hall first.'} Labels are the dataset's own (MIT Supercloud). All traces restart so controllers stay comparable.
      </div>
      <div className="max-h-[260px] overflow-y-auto">
        {traces.map((t) => (
          <button
            key={t.series_id}
            disabled={!gpu}
            className="flex w-full justify-between rounded px-2 py-1 text-left hover:bg-cyan-500/10 disabled:opacity-40"
            onClick={() => gpu && assignTrace(gpu, t.series_id).then(onClose)}
          >
            <span className="text-cyan-100">{t.label}</span>
            <span className="text-slate-400">job {t.job_id.slice(0, 8)} · {Math.round(t.duration_s / 60)} min</span>
          </button>
        ))}
      </div>
    </div>
  );
}
