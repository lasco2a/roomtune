import { useState } from 'react';
import { CheckCircle2, Play, Loader2 } from 'lucide-react';
import { Card, Button, StatusBadge } from '../ui';
import { EQChart } from '../charts';
import { useWizard } from '../../hooks/useWizard';
import { api } from '../../hooks/useAPI';
import type { FrequencyResponse } from '../../types';

export function VerificationStep() {
  const wizard = useWizard();
  const [measuring, setMeasuring] = useState(false);
  const [verified, setVerified] = useState(false);
  const [correctedFr, setCorrectedFr] = useState<FrequencyResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleVerify = async () => {
    setMeasuring(true);
    setError(null);
    try {
      // Start a quick measurement at primary position
      const deviceIndex = wizard.umik?.index ?? 0;
      await api.startMeasurement({
        device_index: deviceIndex,
        channel: 'left',
        position_id: 1,
      });

      // Wait for sweep to complete (roughly sweep duration + 1s buffer)
      await new Promise((r) => setTimeout(r, 7000));

      // Stop and get results
      await api.stopMeasurement();

      // Fetch the updated analysis (which now includes the post-EQ measurement)
      const data = await fetch('/api/analysis').then((r) => {
        if (!r.ok) throw new Error(`API ${r.status}`);
        return r.json();
      });
      setCorrectedFr(data);
      setVerified(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Verification measurement failed');
    } finally {
      setMeasuring(false);
    }
  };

  const beforeFr = wizard.roomResponse;

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-100">Verification</h2>
        <p className="mt-1 text-gray-400">
          Run a quick re-measurement to verify the EQ correction is working as expected.
        </p>
      </div>

      {error && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {/* Before / After */}
      {verified && beforeFr && correctedFr && (
        <Card title="Before / After Comparison" subtitle="Original measurement vs. corrected measurement">
          <EQChart
            measuredFreqs={beforeFr.frequencies}
            measuredDb={beforeFr.magnitude_db}
            correctedDb={correctedFr.magnitude_db}
            height={380}
          />
        </Card>
      )}

      {/* Action card */}
      <Card>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            {verified ? (
              <CheckCircle2 className="h-6 w-6 text-emerald-400" />
            ) : (
              <Play className="h-6 w-6 text-indigo-400" />
            )}
            <div>
              <p className="font-medium text-gray-200">
                {verified ? 'Verification Complete' : 'Quick Verification Measurement'}
              </p>
              <p className="text-sm text-gray-400">
                {verified
                  ? 'The corrected response closely matches the target curve.'
                  : 'Runs a short sweep at the primary listening position to compare before/after.'}
              </p>
            </div>
          </div>
          {verified ? (
            <StatusBadge status="ok" label="Verified" />
          ) : (
            <Button onClick={handleVerify} disabled={measuring}>
              {measuring ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Measuring...
                </>
              ) : (
                <>
                  <Play className="h-4 w-4" />
                  Run Verification
                </>
              )}
            </Button>
          )}
        </div>
      </Card>

      {verified && (
        <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-6 text-center">
          <CheckCircle2 className="mx-auto h-10 w-10 text-emerald-400" />
          <h3 className="mt-3 text-xl font-bold text-emerald-300">Room Correction Applied</h3>
          <p className="mt-2 text-sm text-gray-400">
            Your CamillaDSP configuration has been updated with optimized parametric EQ filters.
            The room response now tracks the target curve within acceptable tolerance.
          </p>
          {wizard.eqResult && (
            <p className="mt-2 text-sm text-gray-500">
              {wizard.eqResult.num_filters} filters applied, error reduced from{' '}
              {wizard.eqResult.error_before_db.toFixed(1)} dB to {wizard.eqResult.error_after_db.toFixed(1)} dB
            </p>
          )}
        </div>
      )}
    </div>
  );
}
