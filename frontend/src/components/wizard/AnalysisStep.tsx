import { useState } from 'react';
import { Clock, Waves } from 'lucide-react';
import { Card, Button, StatusBadge } from '../ui';
import { FrequencyChart } from '../charts';
import type { FrequencyResponse, RT60Result, RoomMode } from '../../types';

interface AnalysisStepProps {
  onComplete: () => void;
}

// Demo data for UI development — replaced by real measurements in production
function demoFrequencyResponse(): FrequencyResponse {
  const n = 500;
  const freqs = Array.from({ length: n }, (_, i) => 20 * Math.pow(1000, i / (n - 1)));
  const mag = freqs.map((f) => {
    let db = -10;
    // Simulate room response with some peaks and dips
    db += 8 * Math.exp(-Math.pow(Math.log2(f / 50), 2) * 2);
    db -= 6 * Math.exp(-Math.pow(Math.log2(f / 120), 2) * 8);
    db += 4 * Math.exp(-Math.pow(Math.log2(f / 3000), 2) * 3);
    db -= 3 * Math.exp(-Math.pow(Math.log2(f / 8000), 2) * 4);
    db += (Math.random() - 0.5) * 2;
    return db;
  });
  return {
    frequencies: freqs,
    magnitude_db: mag,
    phase_deg: freqs.map(() => 0),
    num_points: n,
    calibrated: true,
    smoothing: '1/6 octave',
  };
}

export function AnalysisStep({ onComplete }: AnalysisStepProps) {
  const [smoothing, setSmoothing] = useState<string>('1/6');
  const smoothingOptions = ['None', '1/3', '1/6', '1/12', '1/24'];

  // In production, these come from the API
  const fr = demoFrequencyResponse();
  const rt60: RT60Result = { rt60: 0.42, edt: 0.38, t20: 0.40, t30: 0.42, confidence: 0.95 };
  const modes: RoomMode[] = [
    { frequency: 42.8, mode_type: 'axial', indices: [1, 0, 0] },
    { frequency: 57.2, mode_type: 'axial', indices: [0, 1, 0] },
    { frequency: 71.5, mode_type: 'axial', indices: [0, 0, 1] },
    { frequency: 85.6, mode_type: 'axial', indices: [2, 0, 0] },
  ];

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-100">Analysis</h2>
        <p className="mt-1 text-gray-400">
          Review the measured room frequency response, reverberation time, and room modes.
        </p>
      </div>

      {/* Frequency Response Chart */}
      <Card title="Frequency Response" subtitle="Averaged across all measurement positions">
        <div className="mb-3 flex gap-2">
          {smoothingOptions.map((s) => (
            <button
              key={s}
              onClick={() => setSmoothing(s)}
              className={`rounded px-2 py-1 text-xs font-medium transition-colors
                ${smoothing === s ? 'bg-indigo-600 text-white' : 'bg-gray-800 text-gray-400 hover:text-gray-200'}
              `}
            >
              {s}
            </button>
          ))}
        </div>
        <FrequencyChart
          responses={[{ data: fr, label: 'Room Response' }]}
          height={380}
        />
      </Card>

      <div className="grid grid-cols-2 gap-6">
        {/* RT60 */}
        <Card title="Reverberation Time">
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
        </Card>

        {/* Room Modes */}
        <Card title="Room Modes" subtitle="Axial modes from room dimensions">
          <div className="flex items-start gap-3">
            <Waves className="mt-0.5 h-5 w-5 text-indigo-400" />
            <div className="flex-1">
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
            </div>
          </div>
        </Card>
      </div>

      <div className="flex justify-end">
        <Button onClick={onComplete}>Continue to Target Curve</Button>
      </div>
    </div>
  );
}
