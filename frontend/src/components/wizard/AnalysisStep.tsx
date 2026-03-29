import { useEffect, useState } from 'react';
import { Clock, Waves, Loader2 } from 'lucide-react';
import { Card, Button, StatusBadge } from '../ui';
import { FrequencyChart } from '../charts';
import { api } from '../../hooks/useAPI';
import { useWizard } from '../../hooks/useWizard';
import type { FrequencyResponse, RT60Result, RoomMode } from '../../types';

interface AnalysisStepProps {
  onComplete: () => void;
}

export function AnalysisStep({ onComplete }: AnalysisStepProps) {
  const wizard = useWizard();
  const [smoothing, setSmoothing] = useState<string>('1/6');
  const smoothingOptions = ['None', '1/3', '1/6', '1/12', '1/24'];

  const [fr, setFr] = useState<FrequencyResponse | null>(null);
  const [rt60, setRt60] = useState<RT60Result | null>(null);
  const [modes, setModes] = useState<RoomMode[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Room dimensions for mode calculation (user could configure these)
  const [roomLength, setRoomLength] = useState(4.0);
  const [roomWidth, setRoomWidth] = useState(3.5);
  const [roomHeight, setRoomHeight] = useState(2.4);

  const smoothingToFraction = (s: string): number => {
    switch (s) {
      case '1/3': return 3;
      case '1/6': return 6;
      case '1/12': return 12;
      case '1/24': return 24;
      default: return 0; // None
    }
  };

  const loadAnalysis = async (smooth: string) => {
    setLoading(true);
    setError(null);
    try {
      const fraction = smoothingToFraction(smooth);
      const params = fraction > 0 ? `?smoothing=${fraction}` : '';
      const data = await fetch(`/api/analysis${params}`).then((r) => {
        if (!r.ok) throw new Error(`API ${r.status}`);
        return r.json();
      });
      setFr(data);
      wizard.setRoomResponse(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load analysis');
    } finally {
      setLoading(false);
    }
  };

  const loadRT60 = async () => {
    try {
      const data = await api.getRT60();
      setRt60(data);
    } catch {
      // non-critical — RT60 may not be available
    }
  };

  const loadModes = async () => {
    try {
      const data = await api.getRoomModes(roomLength, roomWidth, roomHeight);
      setModes(data);
    } catch {
      // non-critical
    }
  };

  useEffect(() => {
    loadAnalysis(smoothing);
    loadRT60();
    loadModes();
  }, []);

  // Reload when smoothing changes
  const handleSmoothingChange = (s: string) => {
    setSmoothing(s);
    loadAnalysis(s);
  };

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-100">Analysis</h2>
        <p className="mt-1 text-gray-400">
          Review the measured room frequency response, reverberation time, and room modes.
        </p>
      </div>

      {error && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {/* Frequency Response Chart */}
      <Card title="Frequency Response" subtitle="Averaged across all measurement positions">
        <div className="mb-3 flex items-center gap-2">
          {smoothingOptions.map((s) => (
            <button
              key={s}
              onClick={() => handleSmoothingChange(s)}
              className={`rounded px-2 py-1 text-xs font-medium transition-colors
                ${smoothing === s ? 'bg-indigo-600 text-white' : 'bg-gray-800 text-gray-400 hover:text-gray-200'}
              `}
            >
              {s}
            </button>
          ))}
          {loading && <Loader2 className="ml-2 h-4 w-4 animate-spin text-gray-400" />}
        </div>
        {fr ? (
          <FrequencyChart
            responses={[{ data: fr, label: 'Room Response' }]}
            height={380}
          />
        ) : (
          <div className="flex h-[380px] items-center justify-center text-gray-500">
            {loading ? 'Loading...' : 'No measurement data available'}
          </div>
        )}
      </Card>

      <div className="grid grid-cols-2 gap-6">
        {/* RT60 */}
        <Card title="Reverberation Time">
          {rt60 ? (
            <div className="space-y-3">
              <div className="flex items-center gap-3">
                <Clock className="h-5 w-5 text-indigo-400" />
                <div>
                  <p className="text-3xl font-bold text-gray-100">{rt60.rt60.toFixed(2)}s</p>
                  <p className="text-xs text-gray-400">RT60 (T30)</p>
                </div>
              </div>
              <div className="grid grid-cols-3 gap-3 rounded-lg bg-gray-800/50 p-3">
                <div>
                  <p className="text-lg font-semibold text-gray-200">{rt60.edt.toFixed(2)}s</p>
                  <p className="text-xs text-gray-400">EDT</p>
                </div>
                <div>
                  <p className="text-lg font-semibold text-gray-200">{rt60.t20.toFixed(2)}s</p>
                  <p className="text-xs text-gray-400">T20</p>
                </div>
                <div>
                  <p className="text-lg font-semibold text-gray-200">{(rt60.confidence * 100).toFixed(0)}%</p>
                  <p className="text-xs text-gray-400">Confidence</p>
                </div>
              </div>
              <p className="text-xs text-gray-500">
                {rt60.rt60 < 0.4
                  ? 'Room is relatively dead — good for near-field listening.'
                  : rt60.rt60 < 0.6
                    ? 'Room has moderate reverb — typical for a treated room.'
                    : 'Room is quite live — consider acoustic treatment.'}
              </p>
            </div>
          ) : (
            <div className="flex h-24 items-center justify-center text-sm text-gray-500">
              RT60 data not available
            </div>
          )}
        </Card>

        {/* Room Modes */}
        <Card title="Room Modes" subtitle="Axial modes from room dimensions">
          <div className="mb-3 grid grid-cols-3 gap-2">
            <div>
              <label className="mb-1 block text-xs text-gray-500">Length (m)</label>
              <input
                type="number"
                step="0.1"
                value={roomLength}
                onChange={(e) => { setRoomLength(Number(e.target.value)); }}
                onBlur={loadModes}
                className="w-full rounded border border-gray-700 bg-gray-800 px-2 py-1 text-xs text-gray-200"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-gray-500">Width (m)</label>
              <input
                type="number"
                step="0.1"
                value={roomWidth}
                onChange={(e) => { setRoomWidth(Number(e.target.value)); }}
                onBlur={loadModes}
                className="w-full rounded border border-gray-700 bg-gray-800 px-2 py-1 text-xs text-gray-200"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-gray-500">Height (m)</label>
              <input
                type="number"
                step="0.1"
                value={roomHeight}
                onChange={(e) => { setRoomHeight(Number(e.target.value)); }}
                onBlur={loadModes}
                className="w-full rounded border border-gray-700 bg-gray-800 px-2 py-1 text-xs text-gray-200"
              />
            </div>
          </div>
          <div className="flex items-start gap-3">
            <Waves className="mt-0.5 h-5 w-5 text-indigo-400" />
            <div className="flex-1">
              {modes.length > 0 ? (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs text-gray-500">
                      <th className="pb-2">Freq</th>
                      <th className="pb-2">Type</th>
                      <th className="pb-2">Mode</th>
                    </tr>
                  </thead>
                  <tbody className="text-gray-300">
                    {modes.map((m, i) => (
                      <tr key={i} className="border-t border-gray-800">
                        <td className="py-1.5 font-medium">{m.frequency.toFixed(1)} Hz</td>
                        <td className="py-1.5">
                          <StatusBadge
                            status={m.mode_type === 'axial' ? 'running' : 'pending'}
                            label={m.mode_type}
                          />
                        </td>
                        <td className="py-1.5 font-mono text-xs text-gray-400">
                          ({m.indices.join(', ')})
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p className="text-sm text-gray-500">Enter room dimensions to compute modes</p>
              )}
            </div>
          </div>
        </Card>
      </div>

      <div className="flex justify-end">
        <Button onClick={onComplete} disabled={!fr}>
          Continue to Target Curve
        </Button>
      </div>
    </div>
  );
}
