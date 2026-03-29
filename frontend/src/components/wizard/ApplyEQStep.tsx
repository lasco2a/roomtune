import { useEffect, useState } from 'react';
import { Zap, Upload, Loader2 } from 'lucide-react';
import { Card, Button, StatusBadge } from '../ui';
import { EQChart } from '../charts';
import { useWizard } from '../../hooks/useWizard';
import { api } from '../../hooks/useAPI';
import type { AutoEQResult } from '../../types';

interface ApplyEQStepProps {
  onComplete: () => void;
}

export function ApplyEQStep({ onComplete }: ApplyEQStepProps) {
  const wizard = useWizard();
  const [computing, setComputing] = useState(false);
  const [applying, setApplying] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Compute EQ on mount if not already computed
  useEffect(() => {
    if (!wizard.eqResult && wizard.roomResponse) {
      computeEQ();
    }
  }, []);

  const computeEQ = async () => {
    setComputing(true);
    setError(null);
    try {
      const result = await api.runAutoEQ({
        target: wizard.selectedTarget,
        max_filters: wizard.maxFilters,
        max_gain_db: -wizard.maxGain,
      });
      wizard.setEqResult(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to compute EQ');
    } finally {
      setComputing(false);
    }
  };

  const handleApply = async () => {
    setApplying(true);
    setError(null);
    try {
      await api.applyCamillaDSP();
      wizard.setEqApplied(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to apply EQ to CamillaDSP');
    } finally {
      setApplying(false);
    }
  };

  const result = wizard.eqResult;

  // Build chart data from room response + EQ result
  const chartData = wizard.roomResponse && result
    ? {
        freqs: wizard.roomResponse.frequencies,
        before: wizard.roomResponse.magnitude_db,
        // Simulated corrected: apply the EQ filter correction curve
        // The backend auto-EQ result includes error metrics; for the chart
        // we approximate the corrected response
        after: wizard.roomResponse.magnitude_db.map((db, i) => {
          // Simplified: reduce deviation from 0 dB by the improvement ratio
          const ratio = result.error_before_db > 0
            ? result.error_after_db / result.error_before_db
            : 1;
          return db * ratio;
        }),
      }
    : null;

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-100">Apply EQ</h2>
        <p className="mt-1 text-gray-400">
          Review the computed EQ filters and apply them to CamillaDSP.
        </p>
      </div>

      {computing && (
        <div className="flex items-center justify-center gap-3 rounded-lg border border-indigo-500/30 bg-indigo-500/10 p-6">
          <Loader2 className="h-6 w-6 animate-spin text-indigo-400" />
          <span className="text-indigo-300">Computing optimal EQ filters...</span>
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">
          {error}
          <Button variant="ghost" size="sm" onClick={computeEQ} className="ml-3">
            Retry
          </Button>
        </div>
      )}

      {/* Before / After Chart */}
      {chartData && (
        <Card title="Before / After Comparison">
          <EQChart
            measuredFreqs={chartData.freqs}
            measuredDb={chartData.before}
            correctedDb={chartData.after}
            height={350}
          />
          {result && (
            <div className="mt-3 flex items-center gap-6 text-sm">
              <div>
                <span className="text-gray-400">Error before: </span>
                <span className="font-mono text-red-400">{result.error_before_db.toFixed(1)} dB</span>
              </div>
              <div>
                <span className="text-gray-400">Error after: </span>
                <span className="font-mono text-emerald-400">{result.error_after_db.toFixed(1)} dB</span>
              </div>
              <div>
                <span className="text-gray-400">Improvement: </span>
                <span className="font-mono text-indigo-400">{result.improvement_db.toFixed(1)} dB</span>
              </div>
            </div>
          )}
        </Card>
      )}

      {/* Filter Table */}
      {result && (
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
      )}

      {/* Apply button */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {wizard.eqApplied && <StatusBadge status="ok" label="Applied to CamillaDSP" />}
        </div>
        <div className="flex gap-3">
          {result && (
            <Button variant="ghost" onClick={computeEQ} disabled={computing}>
              Recompute
            </Button>
          )}
          <Button variant="secondary" onClick={onComplete}>
            Skip to Verification
          </Button>
          <Button onClick={handleApply} disabled={applying || wizard.eqApplied || !result}>
            {applying ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Applying...
              </>
            ) : wizard.eqApplied ? (
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
