// ─── Audio Devices ──────────────────────────────────────────────────

export interface AudioDevice {
  index: number;
  name: string;
  channels: number;
  default_samplerate: number;
  hostapi: string;
  is_umik: boolean;
}

export interface DevicesResponse {
  devices: AudioDevice[];
  umik: AudioDevice | null;
}

// ─── Calibration ────────────────────────────────────────────────────

export interface CalibrationData {
  path: string;
  sensitivity_db: number;
  serial: string;
  is_90deg: boolean;
  num_points: number;
  freq_min: number;
  freq_max: number;
  frequencies: number[];
  amplitudes_db: number[];
}

// ─── Measurement ────────────────────────────────────────────────────

export type Channel = 'left' | 'right' | 'both';

export interface MeasurementPosition {
  id: number;
  label: string;
  description: string;
  weight: number; // Higher = more important (primary seat)
  completed: boolean;
  channel: Channel;
}

export interface MeasurementResult {
  position_id: number;
  channel: Channel;
  peak_db: number;
  clipped: boolean;
  duration: number;
}

export type MeasurementMode = 'auto' | 'manual';

export interface MeasurementStatus {
  measuring: boolean;
  status: 'idle' | 'starting' | 'uploading' | 'recording' | 'playing' | 'processing' | 'complete' | 'error';
  detail: string | null;
  position_id: number | null;
  channel: string | null;
  level_rms_db: number;
  level_peak_db: number;
  level_clipped: boolean;
  completed_count: number;
}

// ─── Frequency Response ─────────────────────────────────────────────

export interface FrequencyResponse {
  frequencies: number[];
  magnitude_db: number[];
  phase_deg: number[];
  num_points: number;
  calibrated: boolean;
  smoothing: string;
}

// ─── Room Analysis ──────────────────────────────────────────────────

export interface RT60Result {
  rt60: number;
  edt: number;
  t20: number;
  t30: number;
  confidence: number;
}

export interface RoomMode {
  frequency: number;
  mode_type: 'axial' | 'tangential' | 'oblique';
  indices: [number, number, number];
}

// ─── Target Curves ──────────────────────────────────────────────────

export type TargetPreset = 'flat' | 'harman' | 'harman_bass_boost' | 'bbc_dip';

export interface TargetCurve {
  name: string;
  frequencies: number[];
  amplitude_db: number[];
}

// ─── EQ Filters ─────────────────────────────────────────────────────

export type FilterType = 'peaking' | 'low_shelf' | 'high_shelf';

export interface EQFilter {
  type: FilterType;
  frequency: number;
  gain_db: number;
  q: number;
  coefficients?: {
    b0: number;
    b1: number;
    b2: number;
    a1: number;
    a2: number;
  };
}

export interface AutoEQResult {
  filters: EQFilter[];
  target_name: string;
  error_before_db: number;
  error_after_db: number;
  improvement_db: number;
  num_filters: number;
}

// ─── RPi / CamillaDSP ──────────────────────────────────────────────

export interface RPiConfig {
  host: string;
  port: number;
  username: string;
  password: string;
  key_path?: string;
}

export interface ConnectionTestResult {
  rpi: { connected: boolean; hostname?: string; error?: string };
  camilladsp: { connected: boolean; state?: string; error?: string };
  mpd: { connected: boolean; version?: string; error?: string };
}

// ─── WebSocket Events ───────────────────────────────────────────────

export interface WSLevelEvent {
  event: 'level';
  rms_db: number;
  peak_db: number;
  clipped: boolean;
}

export interface WSProgressEvent {
  event: 'progress';
  step: string;
  percent: number;
  message: string;
}

export interface WSStatusEvent {
  event: 'status';
  status: string;
  detail?: string;
}

export type WSEvent = WSLevelEvent | WSProgressEvent | WSStatusEvent;

// ─── Wizard ─────────────────────────────────────────────────────────

export type WizardStep =
  | 'setup'
  | 'connection'
  | 'measurement'
  | 'analysis'
  | 'target'
  | 'apply'
  | 'verification';

export const WIZARD_STEPS: { key: WizardStep; label: string; number: number }[] = [
  { key: 'setup', label: 'Setup', number: 1 },
  { key: 'connection', label: 'Connection', number: 2 },
  { key: 'measurement', label: 'Measure', number: 3 },
  { key: 'analysis', label: 'Analysis', number: 4 },
  { key: 'target', label: 'Target', number: 5 },
  { key: 'apply', label: 'Apply EQ', number: 6 },
  { key: 'verification', label: 'Verify', number: 7 },
];
