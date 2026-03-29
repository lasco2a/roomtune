import { useState, useCallback, useEffect, useRef } from 'react';
import { Mic, Play, Square, CheckCircle2, Circle, RotateCcw, Loader2, ChevronRight, ArrowRight } from 'lucide-react';
import { Card, Button, LevelMeter } from '../ui';
import { useMeasurement } from '../../hooks/useMeasurement';
import { useWebSocket } from '../../hooks/useWebSocket';
import { useWizard } from '../../hooks/useWizard';
import { api } from '../../hooks/useAPI';
import type { Channel, MeasurementStatus } from '../../types';

interface MeasurementStepProps {
  onComplete: () => void;
}

/** Human-friendly labels for measurement status phases. */
const STATUS_LABELS: Record<string, string> = {
  starting: 'Preparing measurement...',
  uploading: 'Uploading sweep to RPi...',
  recording: 'Recording from UMIK-1...',
  playing: 'Playing sweep through speakers...',
  processing: 'Processing recording...',
  complete: 'Measurement complete!',
  error: 'Measurement failed',
};

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
  } = useMeasurement();

  const [rmsDb, setRmsDb] = useState(-60);
  const [peakDb, setPeakDb] = useState(-60);
  const [clipped, setClipped] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [autoStatus, setAutoStatus] = useState<MeasurementStatus | null>(null);
  const [justCompleted, setJustCompleted] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useWebSocket({
    onLevel: (rms, peak, clip) => {
      setRmsDb(rms);
      setPeakDb(peak);
      setClipped(clip);
    },
  });

  // Clean up polling on unmount
  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  /** Poll the backend for measurement progress (auto mode). */
  const startPolling = useCallback(() => {
    if (pollRef.current) clearInterval(pollRef.current);

    pollRef.current = setInterval(async () => {
      try {
        const status = await api.getMeasurementStatus();
        setAutoStatus(status);

        // Update level meter from poll too (backup if WebSocket lags)
        if (status.measuring) {
          setRmsDb(status.level_rms_db);
          setPeakDb(status.level_peak_db);
          setClipped(status.level_clipped);
        }

        // Handle completion
        if (status.status === 'complete' && !status.measuring) {
          if (pollRef.current) clearInterval(pollRef.current);
          pollRef.current = null;
          setMeasuring(false);
          setJustCompleted(true);

          // Mark position complete using the position_id from the backend
          const posId = status.position_id ?? currentPosition;
          markComplete(posId, {
            position_id: posId,
            channel: (status.channel ?? currentChannel) as Channel,
            peak_db: status.level_peak_db,
            clipped: status.level_clipped,
            duration: 6,
          });
          wizard.setMeasurementCount(completedCount + 1);
        }

        // Handle error
        if (status.status === 'error') {
          if (pollRef.current) clearInterval(pollRef.current);
          pollRef.current = null;
          setMeasuring(false);
          setError(status.detail ?? 'Measurement failed');
        }
      } catch {
        // Polling failure is non-critical; keep trying
      }
    }, 500);
  }, [
    currentPosition,
    currentChannel,
    completedCount,
    positions,
    setMeasuring,
    markComplete,
    wizard,
  ]);

  /** Start an automated measurement for the current position/channel. */
  const handleStart = useCallback(async () => {
    setError(null);
    setAutoStatus(null);
    setJustCompleted(false);

    try {
      // Ensure backend has the current RPi config
      await api.setRpiConfig(wizard.rpiConfig);

      const deviceIndex = wizard.umik?.index ?? 0;
      await api.startMeasurement({
        device_index: deviceIndex,
        channel: currentChannel,
        position_id: currentPosition,
        mode: 'auto',
      });
      setMeasuring(true);
      startPolling();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to start measurement');
    }
  }, [wizard, currentChannel, currentPosition, setMeasuring, startPolling]);

  /** Cancel / stop a measurement (stops recording, cleans up). */
  const handleStop = useCallback(async () => {
    setError(null);
    try {
      await api.stopMeasurement();
    } catch {
      // may fail if auto already stopped
    }
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = null;
    setMeasuring(false);
    setAutoStatus(null);
  }, [setMeasuring]);

  /** Advance to the next incomplete position after a measurement. */
  const handleNextPosition = useCallback(() => {
    const nextIncomplete = positions.find(
      (p) => !p.completed && p.id !== currentPosition,
    );
    if (nextIncomplete) {
      setCurrentPosition(nextIncomplete.id);
      setAutoStatus(null);
      setJustCompleted(false);
    }
  }, [positions, currentPosition, setCurrentPosition]);

  const handleReset = useCallback(async () => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = null;
    resetAll();
    wizard.setMeasurementCount(0);
    setAutoStatus(null);
    setJustCompleted(false);
    setError(null);
    try {
      await fetch('/api/measurement/reset', { method: 'POST' });
    } catch {
      // non-critical
    }
  }, [resetAll, wizard]);

  const currentPos = positions.find((p) => p.id === currentPosition);
  const statusPhase = autoStatus?.status ?? 'idle';
  const statusLabel = STATUS_LABELS[statusPhase] ?? autoStatus?.detail ?? '';
  const isRunning = measuring && statusPhase !== 'complete' && statusPhase !== 'error';
  const canContinue = completedCount >= 1; // At least the primary seat
  const hasNextPosition = positions.some((p) => !p.completed && p.id !== currentPosition);

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-gray-100">Measurement</h2>
        <p className="mt-1 text-gray-400">
          Position the microphone and measure each listening position. Point the UMIK-1 straight up
          at the ceiling. The primary seat is required; additional positions improve accuracy.
        </p>
      </div>

      <div className="grid grid-cols-3 gap-6">
        {/* Left: Position list */}
        <div className="space-y-2">
          <h3 className="text-sm font-semibold text-gray-300">
            Positions ({completedCount}/{positions.length})
          </h3>
          {positions.map((pos) => (
            <button
              key={pos.id}
              onClick={() => {
                if (!measuring) {
                  setCurrentPosition(pos.id);
                  setAutoStatus(null);
                  setJustCompleted(false);
                }
              }}
              disabled={measuring}
              className={`flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm transition-colors
                ${pos.id === currentPosition ? 'bg-indigo-600/20 ring-1 ring-indigo-500/40 text-indigo-300' : 'hover:bg-gray-800/60 text-gray-400'}
                ${measuring ? 'cursor-not-allowed opacity-60' : ''}
              `}
            >
              {pos.completed ? (
                <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-400" />
              ) : pos.id === currentPosition && measuring ? (
                <Loader2 className="h-4 w-4 shrink-0 animate-spin text-indigo-400" />
              ) : (
                <Circle className="h-4 w-4 shrink-0 text-gray-600" />
              )}
              <span className={pos.completed ? 'text-gray-300' : ''}>{pos.label}</span>
              {pos.weight === 1.0 && (
                <span className="ml-auto text-xs text-amber-400">Primary</span>
              )}
            </button>
          ))}

          <Button variant="ghost" size="sm" onClick={handleReset} disabled={measuring} className="mt-4 w-full">
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
                    onClick={() => !measuring && setCurrentChannel(ch)}
                    disabled={measuring}
                    className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors
                      ${currentChannel === ch ? 'bg-indigo-600 text-white' : 'bg-gray-800 text-gray-400 hover:text-gray-200'}
                      ${measuring ? 'cursor-not-allowed' : ''}
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

              {/* Progress indicator (auto mode) */}
              {isRunning && (
                <div className="mb-4 rounded-lg border border-indigo-500/30 bg-indigo-500/10 p-4">
                  <div className="flex items-center gap-3">
                    <Loader2 className="h-5 w-5 animate-spin text-indigo-400" />
                    <div className="flex-1">
                      <p className="text-sm font-medium text-indigo-300">{statusLabel}</p>
                      {autoStatus?.detail && autoStatus.detail !== statusLabel && (
                        <p className="mt-0.5 text-xs text-gray-400">{autoStatus.detail}</p>
                      )}
                    </div>
                  </div>
                  {/* Phase progress bar */}
                  <div className="mt-3 flex gap-1">
                    {['uploading', 'recording', 'playing', 'processing'].map((phase) => {
                      const phaseOrder = ['uploading', 'recording', 'playing', 'processing'];
                      const currentIdx = phaseOrder.indexOf(statusPhase);
                      const phaseIdx = phaseOrder.indexOf(phase);
                      const isActive = phase === statusPhase;
                      const isDone = phaseIdx < currentIdx;
                      return (
                        <div
                          key={phase}
                          className={`h-1.5 flex-1 rounded-full transition-colors ${
                            isDone
                              ? 'bg-indigo-500'
                              : isActive
                                ? 'bg-indigo-400 animate-pulse'
                                : 'bg-gray-700'
                          }`}
                        />
                      );
                    })}
                  </div>
                  <div className="mt-2 flex justify-between text-xs text-gray-500">
                    <span>Upload</span>
                    <span>Record</span>
                    <span>Play</span>
                    <span>Process</span>
                  </div>
                </div>
              )}

              {/* Completion state — show success and next action */}
              {!measuring && justCompleted && autoStatus?.status === 'complete' && (
                <div className="mb-4 rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-4">
                  <div className="flex items-center gap-3">
                    <CheckCircle2 className="h-5 w-5 text-emerald-400" />
                    <div className="flex-1">
                      <p className="text-sm font-medium text-emerald-300">
                        {currentPos.label} measured successfully
                      </p>
                      <p className="mt-0.5 text-xs text-gray-400">{autoStatus.detail}</p>
                    </div>
                  </div>
                  <div className="mt-3 flex gap-2">
                    {hasNextPosition && (
                      <Button size="sm" onClick={handleNextPosition} className="flex-1">
                        <ArrowRight className="h-3 w-3" />
                        Measure Next Position
                      </Button>
                    )}
                    <Button
                      size="sm"
                      variant={hasNextPosition ? 'secondary' : 'primary'}
                      onClick={onComplete}
                      className={hasNextPosition ? '' : 'flex-1'}
                    >
                      <ChevronRight className="h-3 w-3" />
                      {hasNextPosition ? 'Skip to Analysis' : 'Continue to Analysis'}
                    </Button>
                  </div>
                </div>
              )}

              {/* Start/Stop buttons — only show when not in completion state */}
              {!(justCompleted && autoStatus?.status === 'complete' && !measuring) && (
                <div className="flex gap-3">
                  {!measuring ? (
                    <Button
                      onClick={handleStart}
                      disabled={currentPos.completed}
                      className="flex-1"
                    >
                      <Play className="h-4 w-4" />
                      {currentPos.completed ? 'Already Measured' : 'Start Measurement'}
                    </Button>
                  ) : (
                    <Button variant="danger" onClick={handleStop} className="flex-1">
                      <Square className="h-4 w-4" />
                      Cancel
                    </Button>
                  )}
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

      {/* Bottom: Continue button — enabled after at least 1 measurement */}
      <div className="flex items-center justify-between">
        <p className="text-xs text-gray-500">
          {completedCount === 0
            ? 'Measure at least the primary seat to continue'
            : completedCount < positions.length
              ? `${completedCount}/${positions.length} positions measured — you can continue or add more`
              : `All ${positions.length} positions measured`}
        </p>
        <Button onClick={onComplete} disabled={!canContinue}>
          Continue to Analysis
        </Button>
      </div>
    </div>
  );
}
