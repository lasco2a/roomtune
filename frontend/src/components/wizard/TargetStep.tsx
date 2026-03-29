import { useEffect, useState } from 'react';
import { Target, Sliders, Loader2 } from 'lucide-react';
import { Card, Button } from '../ui';
import { FrequencyChart } from '../charts';
import { useWizard } from '../../hooks/useWizard';
import { api } from '../../hooks/useAPI';
import type { TargetPreset, TargetCurve } from '../../types';

interface TargetStepProps {
  onComplete: () => void;
}

const PRESETS: { key: TargetPreset; label: string; description: string }[] = [
  { key: 'flat', label: 'Flat', description: '0 dB at all frequencies' },
  { key: 'harman', label: 'Harman In-Room', description: 'Gentle bass shelf, treble roll-off (~-1 dB/octave above 200 Hz)' },
  { key: 'harman_bass_boost', label: 'Harman + Bass', description: 'Harman target with additional +3 dB bass boost' },
  { key: 'bbc_dip', label: 'BBC Dip', description: 'Flat with ~3 dB dip around 2-4 kHz presence region' },
];

export function TargetStep({ onComplete }: TargetStepProps) {
  const wizard = useWizard();
  const [targets, setTargets] = useState<TargetCurve[]>([]);
  const [loading, setLoading] = useState(false);

  // Load target curves from API on mount
  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const data = await api.getTargets();
        setTargets(data);
      } catch {
        // Fall back to empty — presets still shown for selection
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  // Find the currently selected target from API data, or use local fallback
  const selectedTargetData = targets.find((t) => t.name === wizard.selectedTarget);

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
        {wizard.roomResponse ? (
          <FrequencyChart
            responses={[{ data: wizard.roomResponse, label: 'Room Response', color: '#818cf8' }]}
            target={
              selectedTargetData
                ? { frequencies: selectedTargetData.frequencies, amplitude_db: selectedTargetData.amplitude_db, label: selectedTargetData.name }
                : undefined
            }
            height={380}
          />
        ) : (
          <div className="flex h-[380px] items-center justify-center text-gray-500">
            No room measurement data — go back and run a measurement first
          </div>
        )}
      </Card>

      {/* Preset selector */}
      <Card title="Target Presets" subtitle="Select a reference target curve">
        {loading && (
          <div className="mb-3 flex items-center gap-2 text-sm text-gray-400">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading target curves...
          </div>
        )}
        <div className="grid grid-cols-2 gap-3">
          {PRESETS.map((p) => (
            <button
              key={p.key}
              onClick={() => wizard.setSelectedTarget(p.key)}
              className={`rounded-lg border p-4 text-left transition-colors
                ${wizard.selectedTarget === p.key
                  ? 'border-indigo-500 bg-indigo-600/10'
                  : 'border-gray-700 bg-gray-800/40 hover:border-gray-600'}
              `}
            >
              <div className="flex items-center gap-2">
                <Target className={`h-4 w-4 ${wizard.selectedTarget === p.key ? 'text-indigo-400' : 'text-gray-500'}`} />
                <span className={`text-sm font-semibold ${wizard.selectedTarget === p.key ? 'text-indigo-300' : 'text-gray-300'}`}>
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
              <span className="font-mono text-indigo-400">{wizard.maxFilters}</span>
            </label>
            <input
              type="range"
              min={3}
              max={20}
              value={wizard.maxFilters}
              onChange={(e) => wizard.setMaxFilters(Number(e.target.value))}
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
              <span className="font-mono text-indigo-400">-{wizard.maxGain}</span>
            </label>
            <input
              type="range"
              min={3}
              max={20}
              value={wizard.maxGain}
              onChange={(e) => wizard.setMaxGain(Number(e.target.value))}
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
        <Button onClick={onComplete} disabled={!wizard.roomResponse}>
          Compute EQ Filters
        </Button>
      </div>
    </div>
  );
}
