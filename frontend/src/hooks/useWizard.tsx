import { createContext, useContext, useState, useCallback, type ReactNode } from 'react';
import type {
  RPiConfig,
  AudioDevice,
  CalibrationData,
  FrequencyResponse,
  AutoEQResult,
  TargetPreset,
} from '../types';

// ---------------------------------------------------------------------------
// Shared wizard state
// ---------------------------------------------------------------------------

export interface WizardState {
  // Setup (Step 1)
  umik: AudioDevice | null;
  calibration: CalibrationData | null;
  rpiConfig: RPiConfig;

  // Connection (Step 2)
  connectionOk: boolean;

  // Measurement (Step 3) — results live on the backend; we just track counts
  measurementCount: number;

  // Analysis (Step 4)
  roomResponse: FrequencyResponse | null;

  // Target / EQ (Steps 5-6)
  selectedTarget: TargetPreset;
  maxFilters: number;
  maxGain: number; // positive number, applied as negative dB
  eqResult: AutoEQResult | null;

  // Apply (Step 6)
  eqApplied: boolean;
}

interface WizardActions {
  setUmik: (d: AudioDevice | null) => void;
  setCalibration: (c: CalibrationData | null) => void;
  setRpiConfig: (c: RPiConfig) => void;
  setConnectionOk: (ok: boolean) => void;
  setMeasurementCount: (n: number) => void;
  setRoomResponse: (fr: FrequencyResponse | null) => void;
  setSelectedTarget: (t: TargetPreset) => void;
  setMaxFilters: (n: number) => void;
  setMaxGain: (n: number) => void;
  setEqResult: (r: AutoEQResult | null) => void;
  setEqApplied: (applied: boolean) => void;
}

type WizardContextType = WizardState & WizardActions;

const WizardContext = createContext<WizardContextType | null>(null);

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

const DEFAULT_RPI_CONFIG: RPiConfig = {
  host: 'moode.local',
  port: 22,
  username: 'pi',
  password: '',
};

export function WizardProvider({ children }: { children: ReactNode }) {
  const [umik, setUmik] = useState<AudioDevice | null>(null);
  const [calibration, setCalibration] = useState<CalibrationData | null>(null);
  const [rpiConfig, setRpiConfig] = useState<RPiConfig>(DEFAULT_RPI_CONFIG);
  const [connectionOk, setConnectionOk] = useState(false);
  const [measurementCount, setMeasurementCount] = useState(0);
  const [roomResponse, setRoomResponse] = useState<FrequencyResponse | null>(null);
  const [selectedTarget, setSelectedTarget] = useState<TargetPreset>('harman');
  const [maxFilters, setMaxFilters] = useState(10);
  const [maxGain, setMaxGain] = useState(12);
  const [eqResult, setEqResult] = useState<AutoEQResult | null>(null);
  const [eqApplied, setEqApplied] = useState(false);

  const value: WizardContextType = {
    umik,
    setUmik,
    calibration,
    setCalibration,
    rpiConfig,
    setRpiConfig,
    connectionOk,
    setConnectionOk,
    measurementCount,
    setMeasurementCount,
    roomResponse,
    setRoomResponse,
    selectedTarget,
    setSelectedTarget,
    maxFilters,
    setMaxFilters,
    maxGain,
    setMaxGain,
    eqResult,
    setEqResult,
    eqApplied,
    setEqApplied,
  };

  return <WizardContext.Provider value={value}>{children}</WizardContext.Provider>;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useWizard(): WizardContextType {
  const ctx = useContext(WizardContext);
  if (!ctx) {
    throw new Error('useWizard must be used within a WizardProvider');
  }
  return ctx;
}
