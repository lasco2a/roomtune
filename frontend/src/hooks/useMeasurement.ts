import { useState, useCallback } from 'react';
import type { MeasurementPosition, MeasurementResult, Channel } from '../types';

const DEFAULT_POSITIONS: MeasurementPosition[] = [
  { id: 1, label: 'Primary Seat', description: 'Main listening position', weight: 1.0, completed: false, channel: 'both' },
  { id: 2, label: 'Left of Center', description: '0.5m left of primary', weight: 0.7, completed: false, channel: 'both' },
  { id: 3, label: 'Right of Center', description: '0.5m right of primary', weight: 0.7, completed: false, channel: 'both' },
  { id: 4, label: 'Front', description: '0.5m forward of primary', weight: 0.5, completed: false, channel: 'both' },
  { id: 5, label: 'Back', description: '0.5m behind primary', weight: 0.5, completed: false, channel: 'both' },
];

export function useMeasurement() {
  const [positions, setPositions] = useState<MeasurementPosition[]>(DEFAULT_POSITIONS);
  const [currentPosition, setCurrentPosition] = useState<number>(1);
  const [measuring, setMeasuring] = useState(false);
  const [results, setResults] = useState<MeasurementResult[]>([]);
  const [currentChannel, setCurrentChannel] = useState<Channel>('left');

  const markComplete = useCallback((posId: number, result: MeasurementResult) => {
    setPositions((prev) =>
      prev.map((p) => (p.id === posId ? { ...p, completed: true } : p)),
    );
    setResults((prev) => [...prev, result]);
  }, []);

  const resetAll = useCallback(() => {
    setPositions(DEFAULT_POSITIONS);
    setResults([]);
    setCurrentPosition(1);
    setMeasuring(false);
    setCurrentChannel('left');
  }, []);

  const completedCount = positions.filter((p) => p.completed).length;
  const allDone = completedCount === positions.length;

  return {
    positions,
    currentPosition,
    setCurrentPosition,
    measuring,
    setMeasuring,
    results,
    markComplete,
    resetAll,
    currentChannel,
    setCurrentChannel,
    completedCount,
    allDone,
  };
}
