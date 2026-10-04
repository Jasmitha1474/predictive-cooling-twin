import { useEffect } from 'react';
import { useTelemetry } from './store';
import type { Frame, Hello } from './types';

const env = import.meta.env as Record<string, string | undefined>;
export const BACKEND_HTTP = env.VITE_BACKEND_HTTP ?? `http://${location.hostname}:8000`;
export const BACKEND_WS = env.VITE_BACKEND_WS ?? BACKEND_HTTP.replace(/^http/, 'ws') + '/ws/telemetry';

/** Single WebSocket to the backend. All scene state arrives through here. */
export function useTelemetrySocket() {
  useEffect(() => {
    let ws: WebSocket | null = null;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let delay = 1000;
    let closed = false;
    const { setConnected, onHello, onFrame } = useTelemetry.getState();

    const connect = () => {
      ws = new WebSocket(BACKEND_WS);
      ws.onopen = () => {
        setConnected(true);
        delay = 1000;
      };
      ws.onmessage = (ev) => {
        const msg = JSON.parse(ev.data as string) as Hello | Frame | { type: string };
        if (msg.type === 'hello') onHello(msg as Hello);
        else if (msg.type === 'frame') onFrame(msg as Frame);
      };
      ws.onclose = () => {
        setConnected(false);
        if (!closed) timer = setTimeout(connect, delay);
        delay = Math.min(delay * 2, 15000);
      };
      ws.onerror = () => ws?.close();
    };
    connect();
    return () => {
      closed = true;
      clearTimeout(timer);
      ws?.close();
    };
  }, []);
}

export async function postControl(body: Partial<{ mode: string; controller_mode: string; paused: boolean; speed: number; reset: boolean }>) {
  const r = await fetch(`${BACKEND_HTTP}/api/control`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  return r.json();
}

export async function getJSON<T>(path: string): Promise<T> {
  const r = await fetch(`${BACKEND_HTTP}${path}`);
  if (!r.ok) throw new Error(`${path}: ${r.status}`);
  return r.json() as Promise<T>;
}

export async function assignTrace(gpu_id: string, series_id: string) {
  const r = await fetch(`${BACKEND_HTTP}/api/replay`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ gpu_id, series_id }) });
  return r.json();
}
