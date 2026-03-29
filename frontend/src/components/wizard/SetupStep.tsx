import { useEffect, useState } from 'react';
import { Mic, RefreshCw, FileText } from 'lucide-react';
import { Card, Button, StatusBadge } from '../ui';
import { api } from '../../hooks/useAPI';
import { useWizard } from '../../hooks/useWizard';
import type { AudioDevice, CalibrationData } from '../../types';

interface SetupStepProps {
  onComplete: () => void;
}

export function SetupStep({ onComplete }: SetupStepProps) {
  const wizard = useWizard();
  const [devices, setDevices] = useState<AudioDevice[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const scanDevices = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await api.devices();
      setDevices(result.devices);
      wizard.setUmik(result.umik);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to scan devices');
    } finally {
      setLoading(false);
    }
  };

  const loadCalibration = async () => {
    try {
      const cal = await api.calibration();
      wizard.setCalibration(cal);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load calibration');
    }
  };

  useEffect(() => {
    scanDevices();
    loadCalibration();
  }, []);

  // Sync RPi config changes to context and notify backend
  const updateRpiHost = (host: string) => {
    wizard.setRpiConfig({ ...wizard.rpiConfig, host });
  };
  const updateRpiUser = (username: string) => {
    wizard.setRpiConfig({ ...wizard.rpiConfig, username });
  };
  const updateRpiPassword = (password: string) => {
    wizard.setRpiConfig({ ...wizard.rpiConfig, password });
  };

  const handleContinue = async () => {
    // Tell the backend the RPi host so EQ apply knows where to connect
    try {
      await fetch('/api/config/rpi-host', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ host: wizard.rpiConfig.host }),
      });
    } catch {
      // non-critical
    }
    onComplete();
  };

  const ready = wizard.umik !== null && wizard.calibration !== null;

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-100">Setup</h2>
        <p className="mt-1 text-gray-400">
          Detect your UMIK-1 microphone and configure the Raspberry Pi connection.
        </p>
      </div>

      {/* Microphone Detection */}
      <Card title="Microphone" subtitle="Detect UMIK-1 USB microphone">
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Mic className="h-5 w-5 text-indigo-400" />
              {wizard.umik ? (
                <div>
                  <p className="font-medium text-gray-200">{wizard.umik.name}</p>
                  <p className="text-sm text-gray-400">
                    {wizard.umik.channels}ch, {wizard.umik.default_samplerate / 1000}kHz, {wizard.umik.hostapi}
                  </p>
                </div>
              ) : (
                <p className="text-gray-400">No UMIK-1 detected</p>
              )}
            </div>
            <div className="flex items-center gap-2">
              <StatusBadge status={wizard.umik ? 'ok' : 'error'} label={wizard.umik ? 'Detected' : 'Not found'} />
              <Button variant="ghost" size="sm" onClick={scanDevices} disabled={loading}>
                <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
              </Button>
            </div>
          </div>

          {devices.length > 0 && !wizard.umik && (
            <div className="rounded-lg bg-gray-800/50 p-3">
              <p className="mb-2 text-xs font-medium text-gray-400">Available input devices:</p>
              {devices.map((d) => (
                <p key={d.index} className="text-sm text-gray-300">
                  [{d.index}] {d.name} ({d.channels}ch)
                </p>
              ))}
            </div>
          )}
        </div>
      </Card>

      {/* Calibration File */}
      <Card title="Calibration" subtitle="UMIK-1 calibration file (90-degree for room measurement)">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <FileText className="h-5 w-5 text-indigo-400" />
            {wizard.calibration ? (
              <div>
                <p className="font-medium text-gray-200">
                  Serial {wizard.calibration.serial} {wizard.calibration.is_90deg ? '(90-degree)' : '(0-degree)'}
                </p>
                <p className="text-sm text-gray-400">
                  {wizard.calibration.num_points} points, {wizard.calibration.freq_min.toFixed(0)}
                  &ndash;{wizard.calibration.freq_max.toFixed(0)} Hz, sensitivity{' '}
                  {wizard.calibration.sensitivity_db.toFixed(3)} dB
                </p>
              </div>
            ) : (
              <p className="text-gray-400">No calibration file loaded</p>
            )}
          </div>
          <StatusBadge
            status={wizard.calibration ? 'ok' : 'error'}
            label={wizard.calibration ? 'Loaded' : 'Missing'}
          />
        </div>
      </Card>

      {/* RPi Configuration */}
      <Card title="Raspberry Pi" subtitle="SSH connection to Moode Audio / CamillaDSP">
        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-400">Host</label>
            <input
              type="text"
              value={wizard.rpiConfig.host}
              onChange={(e) => updateRpiHost(e.target.value)}
              className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-200 focus:border-indigo-500 focus:outline-none"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-400">Username</label>
            <input
              type="text"
              value={wizard.rpiConfig.username}
              onChange={(e) => updateRpiUser(e.target.value)}
              className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-200 focus:border-indigo-500 focus:outline-none"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-400">Password</label>
            <input
              type="password"
              value={wizard.rpiConfig.password}
              onChange={(e) => updateRpiPassword(e.target.value)}
              placeholder="or use SSH key"
              className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:border-indigo-500 focus:outline-none"
            />
          </div>
        </div>
      </Card>

      {error && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      )}

      <div className="flex justify-end">
        <Button onClick={handleContinue} disabled={!ready}>
          Continue to Connection Test
        </Button>
      </div>
    </div>
  );
}
