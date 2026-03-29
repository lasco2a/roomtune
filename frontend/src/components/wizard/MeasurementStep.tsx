import { useState, useCallback } from 'react';
import { Mic, Play, Square, CheckCircle2, Circle, RotateCcw } from 'lucide-react';
import { Card, Button, LevelMeter } from '../ui';
import { useMeasurement } from '../../hooks/useMeasurement';
import { useWebSocket } from '../../hooks/useWebSocket';
import { useWizard } from '../../hooks/useWizard';
import { api } from '../../hooks/useAPI';
import type { Channel } from '../../types';

interface MeasurementStepProps {
  onComplete: () => void;
}

export function MeasurementStep({ onComplete }: MeasurementStepProps) {
  const wizard = useWizard();
  const {
    positions,
    currentPosition,
    setCurrentPosition,
    measuring,
    setMeasuring,
    currentChannel,
    setCurrentChannel,
    markComplete,
    resetAll,
    completedCount,
    allDone,
  } = useMeasurement();

  const [rmsDb, setRmsDb] = useState(-60);
  const [peakDb, setPeakDb] = useState(-60);
  const [clipped, setClipped] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useWebSocket({
    onLevel: (rms, peak, clip) => {
      setRmsDb(rms);
      setPeakDb(peak);
      setClipped(clip);
    },
  });

  const handleStart = useCallback(async () => {
    setError(null);
    try {
      const deviceIndex = wizard.umik?.index ?? 0;
      await api.startMeasurement({
        device_index: deviceIndex,
        channel: currentChannel,
        position_id: currentPosition,
      });
      setMeasuring(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to start measurement');
    }
  }, [wizard.umik, currentChannel, currentPosition, setMeasuring]);

  const handleStop = useCallback(async () => {
    setError(null);
    try {
      const res = await api.stopMeasurement();
      setMeasuring(false);
      markComplete(currentPosition, {
        position_id: currentPosition,
        channel: currentChannel,
        peak_db: peakDb,
        clipped,
        duration: 6,
      });
      wizard.setMeasurementCount(completedCount + 1);

      // Advance to next position
      const nextIncomplete = positions.find((p) => !p.completed && p.id !== currentPosition);
      if (nextIncomplete) setCurrentPosition(nextIncomplete.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to stop measurement');
      setMeasuring(false);
    }
  }, [setMeasuring, markComplete, currentPosition, currentChannel, peakDb, clipped, positions, setCurrentPosition, completedCount, wizard]);

  const handleReset = useCallback(async () => {
    resetAll();
    wizard.setMeasurementCount(0);
    try {
      await fetch('/api/measurement/reset', { method: 'POST' });
    } catch {
      // non-critical
    }
  }, [resetAll, wizard]);

  const currentPos = positions.find((p) => p.id === currentPosition);

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-100">Measurement</h2>
        <p className="mt-1 text-gray-400">
          Position the microphone and measure each listening position. Point the UMIK-1 straight up
          at the ceiling.
        </p>
      </div>

      <div className="grid grid-cols-3 gap-6">
        {/* Left: Position list */}
        <div className="space-y-2">
          <h3 className="text-sm font-semibold text-gray-300">Positions ({completedCount}/{positions.length})</h3>
          {positions.map((pos) => (
            <button
              key={pos.id}
              onClick={() => setCurrentPosition(pos.id)}
              className={`flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm transition-colors
                ${pos.id === currentPosition ? 'bg-indigo-600/20 text-indigo-300' : 'hover:bg-gray-800/60 text-gray-400'}
              `}
            >
              {pos.completed ? (
                <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-400" />
              ) : (
                <Circle className="h-4 w-4 shrink-0 text-gray-600" />
              )}
              <span className={pos.completed ? 'text-gray-300' : ''}>{pos.label}</span>
              {pos.weight === 1.0 && (
                <span className="ml-auto text-xs text-amber-400">Primary</span>
              )}
            </button>
          ))}

          <Button variant="ghost" size="sm" onClick={handleReset} className="mt-4 w-full">
            <RotateCcw className="h-3 w-3" />
            Reset All
          </Button>
        </div>

        {/* Center: Current measurement */}
        <div className="col-span-2 space-y-4">
          {currentPos && (
            <Card title={currentPos.label} subtitle={currentPos.description}>
              {/* Channel selector */}
              <div className="mb-4 flex gap-2">
                {(['left', 'right', 'both'] as Channel[]).map((ch) => (
                  <button
                    key={ch}
                    onClick={() => setCurrentChannel(ch)}
                    className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors
                      ${currentChannel === ch ? 'bg-indigo-600 text-white' : 'bg-gray-800 text-gray-400 hover:text-gray-200'}
                    `}
                  >
                    {ch === 'left' ? 'L' : ch === 'right' ? 'R' : 'L+R'}
                  </button>
                ))}
              </div>

              {/* Level meter */}
              <div className="mb-4">
                <LevelMeter rmsDb={rmsDb} peakDb={peakDb} clipped={clipped} />
              </div>

              {/* Mic position guide */}
              <div className="mb-4 rounded-lg border border-gray-700 bg-gray-800/40 p-4">
                <div className="flex items-center gap-3">
                  <Mic className="h-8 w-8 text-indigo-400" />
                  <div>
                    <p className="text-sm font-medium text-gray-200">Position Guide</p>
                    <p className="text-xs text-gray-400">
                      Place the microphone at ear height for the {currentPos.label.toLowerCase()}.
                      Point the UMIK-1 capsule straight up (90-degree orientation).
                    </p>
                  </div>
                </div>
              </div>

              {/* Start/Stop buttons */}
              <div className="flex gap-3">
                {!measuring ? (
                  <Button onClick={handleStart} disabled={currentPos.completed} className="flex-1">
                    <Play className="h-4 w-4" />
                    {currentPos.completed ? 'Completed' : 'Start Measurement'}
                  </Button>
                ) : (
                  <Button variant="danger" onClick={handleStop} className="flex-1">
                    <Square className="h-4 w-4" />
                    Stop
                  </Button>
                )}
              </div>

              {measuring && (
                <div className="mt-3 flex items-center gap-2">
                  <div className="h-2 w-2 animate-pulse rounded-full bg-red-500" />
                  <span className="text-sm text-red-400">Recording...</span>
                </div>
              )}
            </Card>
          )}

          {error && (
            <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-400">
              {error}
            </div>
          )}
        </div>
      </div>

      <div className="flex justify-end">
        <Button onClick={onComplete} disabled={!allDone}>
          Continue to Analysis
        </Button>
      </div>
    </div>
  );
}
