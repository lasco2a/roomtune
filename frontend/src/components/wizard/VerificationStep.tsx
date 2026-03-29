import { useState } from 'react';
import { CheckCircle2, Play, Loader2 } from 'lucide-react';
import { Card, Button, StatusBadge } from '../ui';
import { EQChart } from '../charts';

export function VerificationStep() {
  const [measuring, setMeasuring] = useState(false);
  const [verified, setVerified] = useState(false);

  const handleVerify = async () => {
    setMeasuring(true);
    // In production: run a quick measurement and compare
    await new Promise((r) => setTimeout(r, 3000));
    setMeasuring(false);
    setVerified(true);
  };

  // Demo data
  const n = 500;
  const freqs = Array.from({ length: n }, (_, i) => 20 * Math.pow(1000, i / (n - 1)));
  const before = freqs.map((f) => {
    let db = -10;
    db += 8 * Math.exp(-Math.pow(Math.log2(f / 50), 2) * 2);
    db -= 6 * Math.exp(-Math.pow(Math.log2(f / 120), 2) * 8);
    db += 4 * Math.exp(-Math.pow(Math.log2(f / 3000), 2) * 3);
    return db;
  });
  const after = before.map((db) => db * 0.3 - 5 + (Math.random() - 0.5) * 0.5);

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-100">Verification</h2>
        <p className="mt-1 text-gray-400">
          Run a quick re-measurement to verify the EQ correction is working as expected.
        </p>
      </div>

      {/* Before / After */}
      {verified && (
        <Card title="Before / After Comparison" subtitle="Original measurement vs. corrected measurement">
          <EQChart
            measuredFreqs={freqs}
            measuredDb={before}
            correctedDb={after}
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
        </div>
      )}
    </div>
  );
}
