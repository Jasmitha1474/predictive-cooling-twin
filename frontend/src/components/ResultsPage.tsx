import { useEffect, useState } from 'react';
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { getJSON } from '../telemetry/connection';
import { useTelemetry } from '../telemetry/store';

type Row = { target: string; horizon_s: number; group: string; n: number; mae: number; rmse: number; r2: number | null; mape_pct?: number | null };
type Results = Record<string, any> | null;

const SERIES_COLORS = ['#6b7a90', '#9aa6b8', '#3fc4ff', '#2a8cff', '#f2c94c', '#ff9f43'];

/** Research results: every number is read from files written by the experiment code. */
export function ResultsPage() {
  const [res, setRes] = useState<Record<string, Results> | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const close = () => useTelemetry.getState().setShowResults(false);
  useEffect(() => {
    getJSON<Record<string, Results>>('/api/results').then(setRes).catch((e) => setErr(String(e)));
  }, []);
  const hello = useTelemetry((s) => s.hello);
  const full = res?.['results.json'];
  const r = full ?? res?.['results_subset.json'];
  const subset = !!r && (!full || String(r?.run_type ?? '').startsWith('SUBSET'));
  const audit = res?.['audit_summary.json'] ?? res?.['audit_summary_subset.json'];
  const e2 = res?.['e2_results.json'] ?? res?.['e2_results_subset.json'] ?? res?.['e2_results_preliminary.json'];
  const e2Final = !!res?.['e2_results.json'] && !String(res?.['e2_results.json']?.run_type ?? '').startsWith('SUBSET');

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-950/95 p-8 font-mono text-[13px] text-slate-200">
      <div className="mx-auto max-w-6xl space-y-8">
        <div className="flex items-baseline justify-between">
          <h1 className="text-xl tracking-[0.2em] text-cyan-200">RESEARCH RESULTS</h1>
          <button className="rounded border border-slate-600 px-3 py-1 hover:border-cyan-400" onClick={close}>BACK TO DATA HALL</button>
        </div>
        {err && <div className="text-red-400">Backend not reachable: {err}</div>}

        <Section title="Dataset">
          <div>MIT Supercloud Dataset, labelled subset (datacenter-challenge/202201) · NVIDIA V100 · nvidia-smi ~0.1 s, resampled to 1 s · CC BY-NC-ND 4.0</div>
          <div className="text-slate-400">Samsi et al., IEEE HPEC 2021, doi:10.1109/HPEC49654.2021.9622850</div>
          {audit ? (
            <pre className="mt-2 overflow-x-auto text-[12px] text-slate-300">{JSON.stringify(audit, null, 1).slice(0, 1800)}</pre>
          ) : (
            <Missing what="audit_summary.json (produced by Colab notebook 01)" />
          )}
          {hello?.replay_pack && <div className="mt-2 text-slate-400">Replay pack in use: {JSON.stringify(hello.replay_pack)}</div>}
        </Section>

        <Section title={`Forecasting (E1) · chronological test split${subset ? ' · SUBSET RUN' : ''}`}>
          {subset && (
            <div className="mb-3 rounded border border-amber-400/60 p-2 text-amber-200">
              SUBSET RUN: {r?.subset_note ?? 'real data, random subset of labelled jobs'}. Measured values, not the full-dataset experiment.
            </div>
          )}
          {r ? <ForecastTables r={r} /> : <Missing what="results.json (produced by Colab notebook 03). No forecasting metrics exist yet, so none are shown." />}
        </Section>

        <Section title={`Reactive vs predictive control (E2) ${e2Final ? '' : String(e2?.run_type ?? '').startsWith('SUBSET') ? '· SUBSET RUN' : '· PRELIMINARY'}`}>
          {e2 ? <E2Table e2={e2} final={e2Final} /> : <Missing what="e2_results.json" />}
        </Section>

        <Section title="Model in the live twin">
          <pre className="text-[12px]">{JSON.stringify(hello?.model ?? null, null, 1)}</pre>
        </Section>
      </div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded border border-slate-700 p-4">
      <h2 className="mb-3 tracking-widest text-cyan-300">{title}</h2>
      {children}
    </section>
  );
}

function Missing({ what }: { what: string }) {
  return <div className="text-amber-300">Not available yet: {what}.</div>;
}

function ForecastTables({ r }: { r: Record<string, any> }) {
  const models = Object.keys(r.models);
  const all: (Row & { model: string })[] = models.flatMap((m) => (r.models[m].test as Row[]).filter((x) => x.group === 'ALL').map((x) => ({ ...x, model: m })));
  const chart = (target: string) =>
    [30, 45, 60].map((h) => Object.fromEntries([['horizon', `${h}s`], ...models.map((m) => [m, all.find((x) => x.model === m && x.target === target && x.horizon_s === h)?.mae])]));
  return (
    <div className="space-y-6">
      <div className="text-slate-400">
        Test rows: {r.test_set?.rows_common} · jobs {r.test_set?.jobs} · series {r.test_set?.series}. Selected (validation MAE @30 s): power → {r.selection?.power?.selected}, temperature → {r.selection?.temp?.selected}
      </div>
      {(['power', 'temp'] as const).map((t) => (
        <div key={t}>
          <div className="mb-1 text-cyan-100">{t === 'power' ? 'GPU power (W)' : 'GPU temperature (°C, source system)'} · MAE by horizon</div>
          <div className="h-56">
            <ResponsiveContainer>
              <BarChart data={chart(t)}>
                <CartesianGrid stroke="#1e293b" />
                <XAxis dataKey="horizon" stroke="#94a3b8" />
                <YAxis stroke="#94a3b8" />
                <Tooltip contentStyle={{ background: '#0f172a', border: '1px solid #334155' }} />
                <Legend />
                {models.map((m, i) => (
                  <Bar key={m} dataKey={m} fill={SERIES_COLORS[i % SERIES_COLORS.length]} />
                ))}
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      ))}
      <table className="w-full text-[12px]">
        <thead className="text-slate-400">
          <tr><td>model</td><td>target</td><td>h</td><td>n</td><td>MAE</td><td>RMSE</td><td>R²</td><td>MAPE %</td><td>latency ms (p50)</td><td>size KB</td></tr>
        </thead>
        <tbody>
          {all.map((x, i) => (
            <tr key={i} className="border-t border-slate-800">
              <td className="text-cyan-100">{x.model}</td><td>{x.target}</td><td>{x.horizon_s}</td><td>{x.n}</td>
              <td>{x.mae.toFixed(3)}</td><td>{x.rmse.toFixed(3)}</td><td>{x.r2?.toFixed(3) ?? '—'}</td><td>{x.mape_pct?.toFixed(2) ?? '—'}</td>
              <td>{r.models[x.model].latency?.median_ms?.toFixed(3) ?? '—'}</td><td>{r.models[x.model].size_bytes ? (r.models[x.model].size_bytes / 1024).toFixed(0) : '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function E2Table({ e2, final }: { e2: Record<string, any>; final: boolean }) {
  return (
    <div className="space-y-2">
      {!final && <div className="text-amber-300">{e2.label}{String(e2.run_type ?? '').startsWith('SUBSET') ? '' : '. Predictive uses persistence/oracle forecasts, not ML.'}</div>}
      <div className="text-slate-400">
        {e2.traces.n_series} real power traces ({e2.traces.n_jobs} jobs, {e2.traces.total_seconds} s) · threshold {e2.settings.T_threshold_C} °C ({e2.threshold_rule}) · simulated responses; cooling parameters assumed
      </div>
      <table className="w-full text-[12px]">
        <thead className="text-slate-400">
          <tr><td>controller</td><td>time above threshold (s, total)</td><td>peak T median</td><td>overshoot median</td><td>est. pump energy vs reactive</td><td>valve reversals median</td><td>response time median (s)</td></tr>
        </thead>
        <tbody>
          {Object.entries(e2.summary as Record<string, any>).map(([c, m]) => (
            <tr key={c} className="border-t border-slate-800">
              <td className="text-cyan-100">{c}</td>
              <td>{m.time_above_threshold_s.total?.toFixed(0)}</td>
              <td>{m.peak_Tj_C.median?.toFixed(2)}</td>
              <td>{m.overshoot_C.median?.toFixed(2)}</td>
              <td>{m.est_pump_energy_vs_baseline_ratio?.toFixed(2)}</td>
              <td>{m.valve_reversals.median?.toFixed(0)}</td>
              <td>{m.response_time_median_s.median?.toFixed(1) ?? '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
