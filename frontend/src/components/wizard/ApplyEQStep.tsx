import { useState } from 'react';
import { Zap, Upload, Loader2 } from 'lucide-react';
import { Card, Button, StatusBadge } from '../ui';
import { EQChart } from '../charts';
import type { EQFilter, AutoEQResult } from '../../types';

interface ApplyEQStepProps {
  onComplete: () => void;
}

// Demo data
const DEMO_FILTERS: EQFilter[] = [
  { type: 'peaking', frequency: 52, gain_db: -8.2, q: 2.5 },
  { type: 'peaking', frequency: 118, gain_db: -5.1, q: 3.2 },
  { type: 'peaking', frequency: 245, gain_db: -3.8, q: 4.1 },
  { type: 'peaking', frequency: 680, gain_db: -2.1, q: 2.8 },
  { type: 'peaking', frequency: 2800, gain_db: -4.5, q: 3.0 },
  { type: 'peaking', frequency: 5200, gain_db: -2.8, q: 2.2 },
  { type: 'high_shelf', frequency: 12000, gain_db: -1.5, q: 0.7 },
];

function demoChartData() {
  const n = 500;
  const freqs = Array.from({ length: n }, (_, i) => 20 * Math.pow(1000, i / (n - 1)));
  const before = freqs.map((f) => {
    let db = -10;
    db += 8 * Math.exp(-Math.pow(Math.log2(f / 50), 2) * 2);
    db -= 6 * Math.exp(-Math.pow(Math.log2(f / 120), 2) * 8);
    db += 4 * Math.exp(-Math.pow(Math.log2(f / 3000), 2) * 3);
    db -= 3 * Math.exp(-Math.pow(Math.log2(f / 8000), 2) * 4);
    return db;
  });
  // Simulated corrected response (flatter)
  const after = before.map((db) => db * 0.3 - 5);
  const targetFreqs = [20, 100, 1000, 10000, 20000];
  const targetDb = [6, 3, 0, -3.5, -8];
  return { freqs, before, after, targetFreqs, targetDb };
}

export function ApplyEQStep({ onComplete }: ApplyEQStepProps) {
  const [applying, setApplying] = useState(false);
  const [applied, setApplied] = useState(false);

  const chart = demoChartData();
  const result: AutoEQResult = {
    filters: DEMO_FILTERS,
    target_name: 'Harman In-Room',
    error_before_db: 6.8,
    error_after_db: 2.1,
    improvement_db: 4.7,
    num_filters: DEMO_FILTERS.length,
  };

  const handleApply = async () => {
    setApplying(true);
    // In production: await api.applyCamillaDSP()
    await new Promise((r) => setTimeout(r, 1500));
    setApplying(false);
    setApplied(true);
  };

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-100">Apply EQ</h2>
        <p className="mt-1 text-gray-400">
          Review the computed EQ filters and apply them to CamillaDSP.
        </p>
      </div>

      {/* Before / After Chart */}
      <Card title="Before / After Comparison">
        <EQChart
          measuredFreqs={chart.freqs}
          measuredDb={chart.before}
          correctedDb={chart.after}
          targetFreqs={chart.targetFreqs}
          targetDb={chart.targetDb}
          height={350}
        />
        <div className="mt-3 flex items-center gap-6 text-sm">
          <div>
            <span className="text-gray-400">Error before: </span>
            <span className="font-mono text-red-400">{result.error_before_db} dB</span>
          </div>
          <div>
            <span className="text-gray-400">Error after: </span>
            <span className="font-mono text-emerald-400">{result.error_after_db} dB</span>
          </div>
          <div>
            <span className="text-gray-400">Improvement: </span>
            <span className="font-mono text-indigo-400">{result.improvement_db} dB</span>
          </div>
        </div>
      </Card>

      {/* Filter Table */}
      <Card title="Parametric EQ Filters" subtitle={`${result.num_filters} filters (subtractive only)`}>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-700 text-left text-xs font-medium text-gray-400">
                <th className="pb-2 pr-4">#</th>
                <th className="pb-2 pr-4">Type</th>
                <th className="pb-2 pr-4">Frequency</th>
                <th className="pb-2 pr-4">Gain</th>
                <th className="pb-2 pr-4">Q</th>
              </tr>
            </thead>
            <tbody>
              {result.filters.map((f, i) => (
                <tr key={i} className="border-t border-gray-800 text-gray-300">
                  <td className="py-2 pr-4 text-gray-500">{i + 1}</td>
                  <td className="py-2 pr-4">
                    <StatusBadge
                      status={f.type === 'peaking' ? 'running' : 'pending'}
                      label={f.type.replace('_', ' ')}
                    />
                  </td>
                  <td className="py-2 pr-4 font-mono">
                    {f.frequency >= 1000
                      ? `${(f.frequency / 1000).toFixed(1)}k`
                      : f.frequency.toFixed(0)}{' '}
                    Hz
                  </td>
                  <td className="py-2 pr-4 font-mono text-red-400">{f.gain_db.toFixed(1)} dB</td>
                  <td className="py-2 pr-4 font-mono">{f.q.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Apply button */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {applied && <StatusBadge status="ok" label="Applied to CamillaDSP" />}
        </div>
        <div className="flex gap-3">
          <Button variant="secondary" onClick={onComplete}>
            Skip to Verification
          </Button>
          <Button onClick={handleApply} disabled={applying || applied}>
            {applying ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Applying...
              </>
            ) : applied ? (
              <>
                <Zap className="h-4 w-4" />
                Applied
              </>
            ) : (
              <>
                <Upload className="h-4 w-4" />
                Apply to CamillaDSP
              </>
            )}
          </Button>
        </div>
      </div>
    </div>
  );
}
