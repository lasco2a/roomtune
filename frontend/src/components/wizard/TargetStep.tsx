import { useState } from 'react';
import { Target, Sliders } from 'lucide-react';
import { Card, Button } from '../ui';
import { FrequencyChart } from '../charts';
import type { TargetPreset, TargetCurve, FrequencyResponse } from '../../types';

interface TargetStepProps {
  onComplete: () => void;
}

const PRESETS: { key: TargetPreset; label: string; description: string }[] = [
  { key: 'flat', label: 'Flat', description: '0 dB at all frequencies' },
  { key: 'harman', label: 'Harman In-Room', description: 'Gentle bass shelf, treble roll-off (~-1 dB/octave above 200 Hz)' },
  { key: 'harman_bass_boost', label: 'Harman + Bass', description: 'Harman target with additional +3 dB bass boost' },
  { key: 'bbc_dip', label: 'BBC Dip', description: 'Flat with ~3 dB dip around 2-4 kHz presence region' },
];

// Generate target curve data for display
function generateTargetData(preset: TargetPreset): TargetCurve {
  const freqs = [20, 25, 31.5, 40, 50, 63, 80, 100, 125, 160, 200, 250, 315, 400, 500, 630, 800, 1000, 1250, 1600, 2000, 2500, 3150, 4000, 5000, 6300, 8000, 10000, 12500, 16000, 20000];
  let db: number[];
  switch (preset) {
    case 'flat':
      db = freqs.map(() => 0);
      break;
    case 'harman':
      db = [6, 5.8, 5.5, 5, 4.5, 4, 3.5, 3, 2.5, 2, 1.5, 1, 0.7, 0.4, 0.2, 0, 0, 0, -0.2, -0.5, -0.8, -1, -1.3, -1.5, -1.8, -2.2, -2.8, -3.5, -4.5, -6, -8];
      break;
    case 'harman_bass_boost':
      db = [9, 8.8, 8.5, 8, 7.5, 7, 6.5, 6, 4.5, 3, 1.5, 1, 0.7, 0.4, 0.2, 0, 0, 0, -0.2, -0.5, -0.8, -1, -1.3, -1.5, -1.8, -2.2, -2.8, -3.5, -4.5, -6, -8];
      break;
    case 'bbc_dip':
      db = freqs.map((f) => {
        if (f > 1500 && f < 6000) {
          const logDist = Math.log2(f / 3000);
          return -3 * Math.exp(-2 * logDist * logDist);
        }
        return 0;
      });
      break;
  }
  return { name: preset, frequencies: freqs, amplitude_db: db! };
}

// Dummy room response for overlay
function dummyRoomResponse(): FrequencyResponse {
  const n = 500;
  const freqs = Array.from({ length: n }, (_, i) => 20 * Math.pow(1000, i / (n - 1)));
  const mag = freqs.map((f) => {
    let db = -10;
    db += 8 * Math.exp(-Math.pow(Math.log2(f / 50), 2) * 2);
    db -= 6 * Math.exp(-Math.pow(Math.log2(f / 120), 2) * 8);
    db += 4 * Math.exp(-Math.pow(Math.log2(f / 3000), 2) * 3);
    db -= 3 * Math.exp(-Math.pow(Math.log2(f / 8000), 2) * 4);
    return db;
  });
  return {
    frequencies: freqs, magnitude_db: mag, phase_deg: freqs.map(() => 0),
    num_points: n, calibrated: true, smoothing: '1/6 octave',
  };
}

export function TargetStep({ onComplete }: TargetStepProps) {
  const [selectedPreset, setSelectedPreset] = useState<TargetPreset>('harman');
  const [maxFilters, setMaxFilters] = useState(10);
  const [maxGain, setMaxGain] = useState(12);

  const target = generateTargetData(selectedPreset);
  const room = dummyRoomResponse();

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-100">Target Curve</h2>
        <p className="mt-1 text-gray-400">
          Select a target curve that defines what the corrected response should look like.
        </p>
      </div>

      {/* Chart with room response + target overlay */}
      <Card>
        <FrequencyChart
          responses={[{ data: room, label: 'Room Response', color: '#818cf8' }]}
          target={{ frequencies: target.frequencies, amplitude_db: target.amplitude_db, label: target.name }}
          height={380}
        />
      </Card>

      {/* Preset selector */}
      <Card title="Target Presets" subtitle="Select a reference target curve">
        <div className="grid grid-cols-2 gap-3">
          {PRESETS.map((p) => (
            <button
              key={p.key}
              onClick={() => setSelectedPreset(p.key)}
              className={`rounded-lg border p-4 text-left transition-colors
                ${selectedPreset === p.key
                  ? 'border-indigo-500 bg-indigo-600/10'
                  : 'border-gray-700 bg-gray-800/40 hover:border-gray-600'}
              `}
            >
              <div className="flex items-center gap-2">
                <Target className={`h-4 w-4 ${selectedPreset === p.key ? 'text-indigo-400' : 'text-gray-500'}`} />
                <span className={`text-sm font-semibold ${selectedPreset === p.key ? 'text-indigo-300' : 'text-gray-300'}`}>
                  {p.label}
                </span>
              </div>
              <p className="mt-1 text-xs text-gray-400">{p.description}</p>
            </button>
          ))}
        </div>
      </Card>

      {/* EQ Parameters */}
      <Card title="EQ Parameters" subtitle="Configure auto-EQ constraints">
        <div className="grid grid-cols-2 gap-6">
          <div>
            <label className="mb-2 flex items-center justify-between text-sm text-gray-300">
              <span>Max Filters per Channel</span>
              <span className="font-mono text-indigo-400">{maxFilters}</span>
            </label>
            <input
              type="range"
              min={3}
              max={20}
              value={maxFilters}
              onChange={(e) => setMaxFilters(Number(e.target.value))}
              className="w-full accent-indigo-500"
            />
            <div className="mt-1 flex justify-between text-xs text-gray-500">
              <span>3</span>
              <span>20</span>
            </div>
          </div>
          <div>
            <label className="mb-2 flex items-center justify-between text-sm text-gray-300">
              <span>Max Cut (dB)</span>
              <span className="font-mono text-indigo-400">-{maxGain}</span>
            </label>
            <input
              type="range"
              min={3}
              max={20}
              value={maxGain}
              onChange={(e) => setMaxGain(Number(e.target.value))}
              className="w-full accent-indigo-500"
            />
            <div className="mt-1 flex justify-between text-xs text-gray-500">
              <span>-3 dB</span>
              <span>-20 dB</span>
            </div>
          </div>
        </div>
        <p className="mt-4 text-xs text-gray-500">
          <Sliders className="mr-1 inline h-3 w-3" />
          Subtractive EQ only (cuts peaks, does not boost nulls). More filters = finer correction but
          higher DSP load.
        </p>
      </Card>

      <div className="flex justify-end">
        <Button onClick={onComplete}>Compute EQ Filters</Button>
      </div>
    </div>
  );
}
