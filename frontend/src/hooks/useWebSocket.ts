import { useCallback, useEffect, useRef, useState } from 'react';
import type { WSEvent } from '../types';

interface UseWebSocketOptions {
  autoConnect?: boolean;
  onLevel?: (rms_db: number, peak_db: number, clipped: boolean) => void;
  onProgress?: (step: string, percent: number, message: string) => void;
  onStatus?: (status: string, detail?: string) => void;
}

export function useWebSocket(opts: UseWebSocketOptions) {
  const { autoConnect = true } = opts;
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const callbacksRef = useRef(opts);
  callbacksRef.current = opts;

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${protocol}//${window.location.host}/ws`);

    ws.onopen = () => setConnected(true);

    ws.onclose = () => {
      setConnected(false);
      reconnectTimer.current = setTimeout(connect, 2000);
    };

    ws.onerror = () => ws.close();

    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data) as WSEvent;
        const cbs = callbacksRef.current;
        switch (data.event) {
          case 'level':
            cbs.onLevel?.(data.rms_db, data.peak_db, data.clipped);
            break;
          case 'progress':
            cbs.onProgress?.(data.step, data.percent, data.message);
            break;
          case 'status':
            cbs.onStatus?.(data.status, data.detail);
            break;
        }
      } catch {
        // ignore parse errors
      }
    };

    wsRef.current = ws;
  }, []);

  const disconnect = useCallback(() => {
    clearTimeout(reconnectTimer.current);
    wsRef.current?.close();
    wsRef.current = null;
  }, []);

  const send = useCallback((cmd: string, data?: Record<string, unknown>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ cmd, ...data }));
    }
  }, []);

  useEffect(() => {
    if (autoConnect) connect();
    return () => disconnect();
  }, [autoConnect, connect, disconnect]);

  return { connected, connect, disconnect, send };
}
