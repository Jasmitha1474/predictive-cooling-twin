import { useEffect, useRef } from 'react';
import { useTelemetryStore } from '../store/telemetryStore';
import { TelemetryFrame } from '../types/telemetry';

export function useWebSocket() {
  const ws = useRef<WebSocket | null>(null);
  const { setConnected, addFrame } = useTelemetryStore();

  useEffect(() => {
    let reconnectTimeout: any;
    let delay = 1000;

    const connect = () => {
      ws.current = new WebSocket('ws://localhost:8000/ws/telemetry');
      ws.current.onopen = () => {
        setConnected(true);
        delay = 1000;
      };
      ws.current.onmessage = (event) => {
        try {
          const data: TelemetryFrame = JSON.parse(event.data);
          addFrame(data);
        } catch (e) {
          console.error('Failed to parse frame', e);
        }
      };
      ws.current.onclose = () => {
        setConnected(false);
        reconnectTimeout = setTimeout(connect, delay);
        delay = Math.min(delay * 2, 30000);
      };
      ws.current.onerror = () => {
        ws.current?.close();
      };
    };

    connect();

    return () => {
      clearTimeout(reconnectTimeout);
      ws.current?.close();
    };
  }, [setConnected, addFrame]);
}
