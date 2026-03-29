import { useEffect, useState } from 'react';
import { Mic, RefreshCw, FileText } from 'lucide-react';
import { Card, Button, StatusBadge } from '../ui';
import { api } from '../../hooks/useAPI';
import type { AudioDevice, CalibrationData } from '../../types';

interface SetupStepProps {
  onComplete: () => void;
}

export function SetupStep({ onComplete }: SetupStepProps) {
  const [devices, setDevices] = useState<AudioDevice[]>([]);
  const [umik, setUmik] = useState<AudioDevice | null>(null);
  const [calibration, setCalibration] = useState<CalibrationData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // RPi connection config
  const [rpiHost, setRpiHost] = useState('moode.local');
  const [rpiUser, setRpiUser] = useState('pi');
  const [rpiPassword, setRpiPassword] = useState('');

  const scanDevices = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await api.devices();
      setDevices(result.devices);
      setUmik(result.umik);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to scan devices');
    } finally {
      setLoading(false);
    }
  };

  const loadCalibration = async () => {
    try {
      const cal = await api.calibration();
      setCalibration(cal);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load calibration');
    }
  };

  useEffect(() => {
    scanDevices();
    loadCalibration();
  }, []);

  const ready = umik !== null && calibration !== null;

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
              {umik ? (
                <div>
                  <p className="font-medium text-gray-200">{umik.name}</p>
                  <p className="text-sm text-gray-400">
                    {umik.channels}ch, {umik.default_samplerate / 1000}kHz, {umik.hostapi}
                  </p>
                </div>
              ) : (
                <p className="text-gray-400">No UMIK-1 detected</p>
              )}
            </div>
            <div className="flex items-center gap-2">
              <StatusBadge status={umik ? 'ok' : 'error'} label={umik ? 'Detected' : 'Not found'} />
              <Button variant="ghost" size="sm" onClick={scanDevices} disabled={loading}>
                <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
              </Button>
            </div>
          </div>

          {devices.length > 0 && !umik && (
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
            {calibration ? (
              <div>
                <p className="font-medium text-gray-200">
                  Serial {calibration.serial} {calibration.is_90deg ? '(90-degree)' : '(0-degree)'}
                </p>
                <p className="text-sm text-gray-400">
                  {calibration.num_points} points, {calibration.freq_min.toFixed(0)}
                  &ndash;{calibration.freq_max.toFixed(0)} Hz, sensitivity{' '}
                  {calibration.sensitivity_db.toFixed(3)} dB
                </p>
              </div>
            ) : (
              <p className="text-gray-400">No calibration file loaded</p>
            )}
          </div>
          <StatusBadge
            status={calibration ? 'ok' : 'error'}
            label={calibration ? 'Loaded' : 'Missing'}
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
              value={rpiHost}
              onChange={(e) => setRpiHost(e.target.value)}
              className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-200 focus:border-indigo-500 focus:outline-none"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-400">Username</label>
            <input
              type="text"
              value={rpiUser}
              onChange={(e) => setRpiUser(e.target.value)}
              className="w-full rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-200 focus:border-indigo-500 focus:outline-none"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-gray-400">Password</label>
            <input
              type="password"
              value={rpiPassword}
              onChange={(e) => setRpiPassword(e.target.value)}
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
        <Button onClick={onComplete} disabled={!ready}>
          Continue to Connection Test
        </Button>
      </div>
    </div>
  );
}
