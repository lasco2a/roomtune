"""Measurement orchestrator.

Coordinates the full measurement cycle:
1. Generate a log sweep WAV
2. Upload it to the RPi via SCP
3. Start UMIK-1 recording on the Mac
4. Play the sweep on the RPi via MPD
5. Wait for playback + recording to finish
6. Extract impulse response via deconvolution
7. Compute frequency response with calibration correction

Stores results per (position, channel) for later analysis.
"""

from __future__ import annotations

import asyncio
import logging
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from backend.audio.calibration import CalibrationData
from backend.audio.recorder import Recorder, Recording
from backend.audio.sweep import SweepSignal, generate_sweep, sweep_to_wav_bytes
from backend.analysis.impulse import ImpulseResponse, extract_impulse_response
from backend.analysis.frequency import FrequencyResponse, compute_frequency_response
from backend.analysis.smoothing import octave_smooth

logger = logging.getLogger("roomtune.orchestrator")


@dataclass
class PositionResult:
    """Result of a single measurement at one position + channel."""

    position_id: int
    channel: str  # "left" | "right" | "both"
    recording: Recording
    impulse_response: ImpulseResponse
    frequency_response: FrequencyResponse
    frequency_response_smoothed: FrequencyResponse


@dataclass
class MeasurementSession:
    """Holds all measurement results for a session."""

    sweep: SweepSignal | None = None
    calibration: CalibrationData | None = None
    results: list[PositionResult] = field(default_factory=list)
    measuring: bool = False
    current_position: int = -1
    current_channel: str = ""
    # Level meter state (updated by recording callback)
    level_rms_db: float = -120.0
    level_peak_db: float = -120.0
    level_clipped: bool = False

    @property
    def averaged_frequency_response(self) -> FrequencyResponse | None:
        """Compute weighted average of all smoothed frequency responses."""
        if not self.results:
            return None

        # Collect all smoothed FRs and their weights
        # Primary seat (position_id=1) gets weight 1.0, others get less
        weights_map = {1: 1.0, 2: 0.7, 3: 0.7, 4: 0.5, 5: 0.5}

        # Use the first result's frequency grid as reference
        ref = self.results[0].frequency_response_smoothed
        freqs = ref.frequencies.copy()

        weighted_sum = np.zeros_like(freqs, dtype=np.float64)
        total_weight = 0.0

        for r in self.results:
            w = weights_map.get(r.position_id, 0.5)
            fr = r.frequency_response_smoothed
            # Interpolate to the reference grid
            interp_mag = np.interp(np.log10(freqs), np.log10(fr.frequencies), fr.magnitude_db)
            weighted_sum += w * interp_mag
            total_weight += w

        if total_weight > 0:
            avg_mag = weighted_sum / total_weight
        else:
            avg_mag = weighted_sum

        return FrequencyResponse(
            frequencies=freqs,
            magnitude_db=avg_mag,
            phase_deg=np.zeros_like(freqs),
            sample_rate=ref.sample_rate,
            calibrated=ref.calibrated,
            smoothing=ref.smoothing,
        )

    def get_result(self, position_id: int, channel: str) -> PositionResult | None:
        for r in self.results:
            if r.position_id == position_id and r.channel == channel:
                return r
        return None


class MeasurementOrchestrator:
    """Orchestrates sweep playback and recording."""

    def __init__(self) -> None:
        self.session = MeasurementSession()
        self._recorder: Recorder | None = None
        self._level_callback: callable | None = None

    def configure(
        self,
        device_index: int | None,
        calibration: CalibrationData | None,
        sample_rate: int = 48000,
        sweep_duration: float = 5.0,
        level_callback: callable | None = None,
    ) -> None:
        """Set up the measurement session parameters."""
        self.session.sweep = generate_sweep(duration=sweep_duration, sample_rate=sample_rate)
        self.session.calibration = calibration
        self._recorder = Recorder(
            device_index=device_index,
            sample_rate=sample_rate,
            channels=1,
        )
        self._level_callback = level_callback
        logger.info("Orchestrator configured: device=%s, sr=%d", device_index, sample_rate)

    def start_measurement(self, position_id: int, channel: str) -> None:
        """Start a measurement for a given position and channel.

        This starts the UMIK-1 recording in streaming mode. The sweep
        playback on the RPi should be triggered separately (or is handled
        by the caller). Recording continues until stop_measurement() is
        called.
        """
        if self._recorder is None:
            raise RuntimeError("Orchestrator not configured — call configure() first")
        if self.session.measuring:
            raise RuntimeError("Measurement already in progress")

        self.session.measuring = True
        self.session.current_position = position_id
        self.session.current_channel = channel

        def on_level(rms_db: float, peak_db: float, clipped: bool) -> None:
            self.session.level_rms_db = rms_db
            self.session.level_peak_db = peak_db
            self.session.level_clipped = clipped
            if self._level_callback:
                self._level_callback(rms_db, peak_db, clipped)

        self._recorder.start_stream(level_callback=on_level)
        logger.info("Measurement started: position=%d, channel=%s", position_id, channel)

    def stop_measurement(self) -> PositionResult:
        """Stop the current measurement and process the recording."""
        if self._recorder is None or not self.session.measuring:
            raise RuntimeError("No measurement in progress")

        recording = self._recorder.stop_stream()
        self.session.measuring = False

        pos_id = self.session.current_position
        channel = self.session.current_channel

        logger.info(
            "Recording stopped: %d samples (%.2f s), peak=%.1f dB",
            recording.num_samples,
            recording.duration,
            recording.peak_db,
        )

        # Extract impulse response
        ir = extract_impulse_response(recording, self.session.sweep)

        # Compute frequency response
        fr = compute_frequency_response(ir, calibration=self.session.calibration)

        # Smooth
        fr_smoothed = octave_smooth(fr, fraction=6.0)

        result = PositionResult(
            position_id=pos_id,
            channel=channel,
            recording=recording,
            impulse_response=ir,
            frequency_response=fr,
            frequency_response_smoothed=fr_smoothed,
        )

        # Remove any previous result for same position+channel, then add
        self.session.results = [
            r
            for r in self.session.results
            if not (r.position_id == pos_id and r.channel == channel)
        ]
        self.session.results.append(result)

        logger.info(
            "Measurement complete for position %d/%s (%d total results)",
            pos_id,
            channel,
            len(self.session.results),
        )
        return result

    def get_sweep_wav(self, channel: str = "both") -> bytes:
        """Get the sweep signal as WAV bytes for upload to RPi."""
        if self.session.sweep is None:
            raise RuntimeError("No sweep generated — call configure() first")
        return sweep_to_wav_bytes(self.session.sweep, channel=channel)

    def reset(self) -> None:
        """Reset the session, discarding all results."""
        if self.session.measuring and self._recorder:
            try:
                self._recorder.stop_stream()
            except Exception:
                pass
        self.session = MeasurementSession()
        logger.info("Measurement session reset")
