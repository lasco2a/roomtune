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

# Remote path where we upload the sweep WAV on the RPi
REMOTE_SWEEP_DIR = "/var/lib/mpd/music"
REMOTE_SWEEP_FILENAME = "roomtune_sweep.wav"
REMOTE_SWEEP_PATH = f"{REMOTE_SWEEP_DIR}/{REMOTE_SWEEP_FILENAME}"
# MPD URI (relative to its music directory)
MPD_SWEEP_URI = REMOTE_SWEEP_FILENAME


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
    sweep_uploaded: bool = False
    # Level meter state (updated by recording callback)
    level_rms_db: float = -120.0
    level_peak_db: float = -120.0
    level_clipped: bool = False
    # Progress tracking
    status: str = "idle"  # idle | uploading | recording | playing | processing | complete | error
    status_detail: str = ""

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
        # RPi config — set via configure_rpi()
        self._rpi_host: str = "moode.local"
        self._rpi_port: int = 22
        self._rpi_username: str = "pi"
        self._rpi_password: str | None = None
        self._rpi_key_path: str | None = None
        # Background thread for automated measurement
        self._measure_thread: threading.Thread | None = None

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
        self.session.sweep_uploaded = False
        self._recorder = Recorder(
            device_index=device_index,
            sample_rate=sample_rate,
            channels=1,
        )
        self._level_callback = level_callback
        logger.info("Orchestrator configured: device=%s, sr=%d", device_index, sample_rate)

    def configure_rpi(
        self,
        host: str = "moode.local",
        port: int = 22,
        username: str = "pi",
        password: str | None = None,
        key_path: str | None = None,
    ) -> None:
        """Set RPi connection parameters for automated sweep playback."""
        self._rpi_host = host
        self._rpi_port = port
        self._rpi_username = username
        self._rpi_password = password
        self._rpi_key_path = key_path
        # Reset upload flag since host may have changed
        self.session.sweep_uploaded = False
        logger.info("RPi configured: %s@%s:%d", username, host, port)

    # ------------------------------------------------------------------
    # Automated measurement (upload + record + play + process)
    # ------------------------------------------------------------------

    def run_measurement(self, position_id: int, channel: str) -> None:
        """Run a fully automated measurement in a background thread.

        Steps:
        1. Upload sweep WAV to RPi (if not already uploaded)
        2. Start UMIK-1 recording
        3. Short pre-roll delay (let recording stabilise)
        4. Trigger MPD playback of the sweep on RPi
        5. Wait for sweep to finish + post-roll tail capture
        6. Stop recording
        7. Process: IR extraction → FR computation

        The result is stored in ``self.session.results``.
        Progress is tracked via ``self.session.status``.
        """
        if self._recorder is None:
            raise RuntimeError("Orchestrator not configured — call configure() first")
        if self.session.measuring:
            raise RuntimeError("Measurement already in progress")

        self.session.measuring = True
        self.session.current_position = position_id
        self.session.current_channel = channel
        self.session.status = "starting"
        self.session.status_detail = ""

        self._measure_thread = threading.Thread(
            target=self._run_measurement_sync,
            args=(position_id, channel),
            daemon=True,
        )
        self._measure_thread.start()

    def _run_measurement_sync(self, position_id: int, channel: str) -> None:
        """Synchronous measurement flow (runs in background thread)."""
        from backend.integration.rpi import RPiConfig, RPiConnection
        from backend.integration.moode import MPDClient

        try:
            sweep = self.session.sweep
            if sweep is None:
                raise RuntimeError("No sweep generated")

            # --- Step 1: Upload sweep WAV to RPi ---
            if not self.session.sweep_uploaded:
                self.session.status = "uploading"
                self.session.status_detail = "Uploading sweep WAV to RPi..."
                logger.info("Uploading sweep WAV to RPi %s", self._rpi_host)

                wav_bytes = sweep_to_wav_bytes(sweep, channel=channel)
                rpi = RPiConnection(
                    RPiConfig(
                        host=self._rpi_host,
                        port=self._rpi_port,
                        username=self._rpi_username,
                        password=self._rpi_password,
                        key_path=self._rpi_key_path,
                    )
                )
                rpi.connect()
                try:
                    rpi.upload_bytes(wav_bytes, REMOTE_SWEEP_PATH)
                finally:
                    rpi.disconnect()

                # Update MPD database so it sees the new file
                mpd = MPDClient(host=self._rpi_host)
                mpd.connect()
                try:
                    mpd.update(REMOTE_SWEEP_FILENAME)
                    # Give MPD a moment to index the new file
                    time.sleep(1.0)
                finally:
                    mpd.disconnect()

                self.session.sweep_uploaded = True
                logger.info("Sweep WAV uploaded to %s", REMOTE_SWEEP_PATH)

            # --- Step 2: Start UMIK-1 recording ---
            self.session.status = "recording"
            self.session.status_detail = "Recording from UMIK-1..."

            def on_level(rms_db: float, peak_db: float, clipped: bool) -> None:
                self.session.level_rms_db = rms_db
                self.session.level_peak_db = peak_db
                self.session.level_clipped = clipped
                if self._level_callback:
                    self._level_callback(rms_db, peak_db, clipped)

            self._recorder.start_stream(level_callback=on_level)
            logger.info("UMIK-1 recording started")

            # --- Step 3: Pre-roll delay ---
            # Let the recording stream stabilise before triggering playback
            time.sleep(0.5)

            # --- Step 4: Trigger MPD playback ---
            self.session.status = "playing"
            self.session.status_detail = "Playing sweep through speakers..."
            logger.info("Triggering sweep playback on RPi")

            mpd = MPDClient(host=self._rpi_host)
            mpd.connect()
            try:
                mpd.play_file(MPD_SWEEP_URI, volume=80)
            finally:
                mpd.disconnect()

            # --- Step 5: Wait for sweep to finish + tail capture ---
            # Total wait = sweep duration + padding + extra tail for reverb
            total_wait = sweep.total_duration + 1.5  # 1.5s extra for room tail
            self.session.status_detail = f"Playing... ({sweep.total_duration:.1f}s sweep + tail)"
            logger.info("Waiting %.1f s for sweep + tail", total_wait)
            time.sleep(total_wait)

            # --- Step 6: Stop recording ---
            self.session.status = "processing"
            self.session.status_detail = "Processing recording..."

            recording = self._recorder.stop_stream()
            logger.info(
                "Recording stopped: %d samples (%.2f s), peak=%.1f dB",
                recording.num_samples,
                recording.duration,
                recording.peak_db,
            )

            # --- Step 7: Process — IR extraction + FR computation ---
            ir = extract_impulse_response(recording, sweep)
            fr = compute_frequency_response(ir, calibration=self.session.calibration)
            fr_smoothed = octave_smooth(fr, fraction=6.0)

            result = PositionResult(
                position_id=position_id,
                channel=channel,
                recording=recording,
                impulse_response=ir,
                frequency_response=fr,
                frequency_response_smoothed=fr_smoothed,
            )

            # Store result (replace any previous for same position+channel)
            self.session.results = [
                r
                for r in self.session.results
                if not (r.position_id == position_id and r.channel == channel)
            ]
            self.session.results.append(result)

            self.session.status = "complete"
            self.session.status_detail = (
                f"Position {position_id}/{channel}: peak={recording.peak_db:.1f} dB, "
                f"duration={recording.duration:.1f}s"
            )
            logger.info(
                "Measurement complete for position %d/%s (%d total results)",
                position_id,
                channel,
                len(self.session.results),
            )

        except Exception as e:
            logger.error("Measurement failed: %s", e, exc_info=True)
            self.session.status = "error"
            self.session.status_detail = str(e)
            # Make sure recording is stopped
            if self._recorder and self._recorder.is_recording:
                try:
                    self._recorder.stop_stream()
                except Exception:
                    pass
        finally:
            self.session.measuring = False

    # ------------------------------------------------------------------
    # Manual start/stop (kept for backward compat / manual mode)
    # ------------------------------------------------------------------

    def start_measurement(self, position_id: int, channel: str) -> None:
        """Start a manual measurement (recording only, no sweep playback).

        Use run_measurement() for the full automated flow instead.
        """
        if self._recorder is None:
            raise RuntimeError("Orchestrator not configured — call configure() first")
        if self.session.measuring:
            raise RuntimeError("Measurement already in progress")

        self.session.measuring = True
        self.session.current_position = position_id
        self.session.current_channel = channel
        self.session.status = "recording"

        def on_level(rms_db: float, peak_db: float, clipped: bool) -> None:
            self.session.level_rms_db = rms_db
            self.session.level_peak_db = peak_db
            self.session.level_clipped = clipped
            if self._level_callback:
                self._level_callback(rms_db, peak_db, clipped)

        self._recorder.start_stream(level_callback=on_level)
        logger.info("Manual measurement started: position=%d, channel=%s", position_id, channel)

    def stop_measurement(self) -> PositionResult:
        """Stop a manual measurement and process the recording."""
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

        self.session.status = "complete"
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
