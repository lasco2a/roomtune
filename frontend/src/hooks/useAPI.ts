const API_BASE = '/api';

async function fetchJSON<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json();
}

export const api = {
  health: () => fetchJSON<{ status: string; version: string }>('/health'),
  devices: () =>
    fetchJSON<{ devices: import('../types').AudioDevice[]; umik: import('../types').AudioDevice | null }>('/devices'),
  calibration: (path?: string) => {
    const qs = path ? `?path=${encodeURIComponent(path)}` : '';
    return fetchJSON<import('../types').CalibrationData>(`/calibration${qs}`);
  },
  connectionTest: (config: import('../types').RPiConfig) =>
    fetchJSON<import('../types').ConnectionTestResult>('/connection/test', {
      method: 'POST',
      body: JSON.stringify(config),
    }),
  startMeasurement: (params: {
    device_index: number;
    channel: string;
    position_id: number;
    duration?: number;
  }) =>
    fetchJSON<{ status: string }>('/measurement/start', {
      method: 'POST',
      body: JSON.stringify(params),
    }),
  stopMeasurement: () => fetchJSON<{ status: string }>('/measurement/stop', { method: 'POST' }),
  getAnalysis: () => fetchJSON<import('../types').FrequencyResponse>('/analysis'),
  getRT60: () => fetchJSON<import('../types').RT60Result>('/analysis/rt60'),
  getRoomModes: (length: number, width: number, height: number) =>
    fetchJSON<import('../types').RoomMode[]>(
      `/analysis/modes?length=${length}&width=${width}&height=${height}`,
    ),
  getTargets: () => fetchJSON<import('../types').TargetCurve[]>('/eq/targets'),
  runAutoEQ: (params: {
    target: string;
    max_filters?: number;
    max_gain_db?: number;
  }) =>
    fetchJSON<import('../types').AutoEQResult>('/eq/auto', {
      method: 'POST',
      body: JSON.stringify(params),
    }),
  applyCamillaDSP: () =>
    fetchJSON<{ status: string }>('/eq/apply', { method: 'POST' }),
};
