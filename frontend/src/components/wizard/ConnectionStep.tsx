import { useState } from 'react';
import { Wifi, Server, Music, Loader2 } from 'lucide-react';
import { Card, Button, StatusBadge } from '../ui';
import { api } from '../../hooks/useAPI';
import type { ConnectionTestResult } from '../../types';

interface ConnectionStepProps {
  onComplete: () => void;
}

export function ConnectionStep({ onComplete }: ConnectionStepProps) {
  const [testing, setTesting] = useState(false);
  const [result, setResult] = useState<ConnectionTestResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const runTest = async () => {
    setTesting(true);
    setError(null);
    try {
      const res = await api.connectionTest({
        host: 'moode.local',
        port: 22,
        username: 'pi',
        password: '',
      });
      setResult(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Connection test failed');
    } finally {
      setTesting(false);
    }
  };

  const allConnected = result?.rpi.connected && result?.camilladsp.connected && result?.mpd.connected;

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-100">Connection Test</h2>
        <p className="mt-1 text-gray-400">
          Verify connectivity to the Raspberry Pi, CamillaDSP, and MPD.
        </p>
      </div>

      <div className="grid gap-4">
        {/* RPi SSH */}
        <Card>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Wifi className="h-5 w-5 text-indigo-400" />
              <div>
                <p className="font-medium text-gray-200">Raspberry Pi (SSH)</p>
                <p className="text-sm text-gray-400">
                  {result?.rpi.connected
                    ? `Connected: ${result.rpi.hostname}`
                    : result?.rpi.error || 'Not tested'}
                </p>
              </div>
            </div>
            <StatusBadge
              status={result === null ? 'pending' : result.rpi.connected ? 'ok' : 'error'}
              label={result === null ? 'Pending' : result.rpi.connected ? 'OK' : 'Failed'}
            />
          </div>
        </Card>

        {/* CamillaDSP */}
        <Card>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Server className="h-5 w-5 text-indigo-400" />
              <div>
                <p className="font-medium text-gray-200">CamillaDSP</p>
                <p className="text-sm text-gray-400">
                  {result?.camilladsp.connected
                    ? `Running (${result.camilladsp.state})`
                    : result?.camilladsp.error || 'Not tested'}
                </p>
              </div>
            </div>
            <StatusBadge
              status={
                result === null ? 'pending' : result.camilladsp.connected ? 'ok' : 'error'
              }
              label={
                result === null ? 'Pending' : result.camilladsp.connected ? 'OK' : 'Failed'
              }
            />
          </div>
        </Card>

        {/* MPD */}
        <Card>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Music className="h-5 w-5 text-indigo-400" />
              <div>
                <p className="font-medium text-gray-200">MPD (Moode Audio)</p>
                <p className="text-sm text-gray-400">
                  {result?.mpd.connected
                    ? `Connected (${result.mpd.version})`
                    : result?.mpd.error || 'Not tested'}
                </p>
              </div>
            </div>
            <StatusBadge
              status={result === null ? 'pending' : result.mpd.connected ? 'ok' : 'error'}
              label={result === null ? 'Pending' : result.mpd.connected ? 'OK' : 'Failed'}
            />
          </div>
        </Card>
      </div>

      {error && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      )}

      <div className="flex items-center justify-between">
        <Button variant="secondary" onClick={runTest} disabled={testing}>
          {testing ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Testing...
            </>
          ) : (
            'Run Connection Test'
          )}
        </Button>
        <Button onClick={onComplete} disabled={!allConnected}>
          Continue to Measurement
        </Button>
      </div>
    </div>
  );
}
