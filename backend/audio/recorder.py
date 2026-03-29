"""Audio recording engine for UMIK-1.

Records audio from the UMIK-1 (or any selected input device) using
``sounddevice``.  Supports blocking capture for a fixed duration and
streaming capture with a callback for real-time level monitoring.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field

import numpy as np
import sounddevice as sd

logger = logging.getLogger("roomtune.recorder")


@dataclass
class Recording:
    """Result of a recording session."""

    data: np.ndarray = field(repr=False)  # shape (samples, channels), float32
    sample_rate: int = 48000
    channels: int = 1
    duration: float = 0.0
    device_index: int = -1
    device_name: str = ""
    peak_db: float = -120.0
    clipped: bool = False

    @property
    def num_samples(self) -> int:
        return self.data.shape[0] if self.data.ndim > 0 else 0

    def to_mono(self) -> np.ndarray:
        """Return a 1-D mono signal (average of all channels)."""
        if self.data.ndim == 1:
            return self.data
        return self.data.mean(axis=1)


class Recorder:
    """Record audio from an input device (typically UMIK-1)."""

    def __init__(
        self,
        device_index: int | None = None,
        sample_rate: int = 48000,
        channels: int = 1,
        dtype: str = "float32",
    ) -> None:
        self.device_index = device_index
        self.sample_rate = sample_rate
        self.channels = channels
        self.dtype = dtype

        # Streaming state
        self._stream: sd.InputStream | None = None
        self._buffer: list[np.ndarray] = []
        self._lock = threading.Lock()
        self._level_callback: callable | None = None
        self._recording = False

    # ------------------------------------------------------------------
    # Blocking capture
    # ------------------------------------------------------------------

    def record(self, duration: float) -> Recording:
        """Record for a fixed duration (blocking).

        Parameters
        ----------
        duration : float
            Recording length in seconds.

        Returns
        -------
        Recording
        """
        n_frames = int(duration * self.sample_rate)
        logger.info(
            "Recording %.2f s (%d frames) from device %s …",
            duration,
            n_frames,
            self.device_index,
        )

        data = sd.rec(
            frames=n_frames,
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype=self.dtype,
            device=self.device_index,
        )
        sd.wait()

        peak = float(np.max(np.abs(data)))
        peak_db = 20.0 * np.log10(peak) if peak > 0 else -120.0
        clipped = peak >= 0.99

        rec = Recording(
            data=data,
            sample_rate=self.sample_rate,
            channels=self.channels,
            duration=duration,
            device_index=self.device_index if self.device_index is not None else -1,
            device_name=self._device_name(),
            peak_db=peak_db,
            clipped=clipped,
        )

        logger.info(
            "Recording complete: %d samples, peak=%.1f dB, clipped=%s",
            rec.num_samples,
            rec.peak_db,
            rec.clipped,
        )
        return rec

    # ------------------------------------------------------------------
    # Streaming capture (for real-time level meter)
    # ------------------------------------------------------------------

    def start_stream(self, level_callback: callable | None = None) -> None:
        """Start continuous recording with optional real-time level callback.

        Parameters
        ----------
        level_callback : callable, optional
            Called with ``(rms_db: float, peak_db: float, clipped: bool)``
            on every audio block.
        """
        if self._recording:
            logger.warning("Stream already running")
            return

        self._buffer.clear()
        self._level_callback = level_callback
        self._recording = True

        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype=self.dtype,
            device=self.device_index,
            callback=self._stream_callback,
            blocksize=1024,
        )
        self._stream.start()
        logger.info("Streaming capture started on device %s", self.device_index)

    def stop_stream(self) -> Recording:
        """Stop streaming and return the accumulated recording."""
        if not self._recording or self._stream is None:
            raise RuntimeError("No stream running")

        self._recording = False
        self._stream.stop()
        self._stream.close()
        self._stream = None

        with self._lock:
            if self._buffer:
                data = np.concatenate(self._buffer, axis=0)
            else:
                data = np.zeros((0, self.channels), dtype=np.float32)
            self._buffer.clear()

        duration = len(data) / self.sample_rate
        peak = float(np.max(np.abs(data))) if len(data) > 0 else 0.0
        peak_db = 20.0 * np.log10(peak) if peak > 0 else -120.0

        rec = Recording(
            data=data,
            sample_rate=self.sample_rate,
            channels=self.channels,
            duration=duration,
            device_index=self.device_index if self.device_index is not None else -1,
            device_name=self._device_name(),
            peak_db=peak_db,
            clipped=peak >= 0.99,
        )

        logger.info("Streaming capture stopped: %.2f s, peak=%.1f dB", duration, peak_db)
        return rec

    @property
    def is_recording(self) -> bool:
        return self._recording

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _stream_callback(self, indata: np.ndarray, frames: int, time_info, status) -> None:
        if status:
            logger.warning("Stream status: %s", status)

        with self._lock:
            self._buffer.append(indata.copy())

        if self._level_callback is not None:
            rms = float(np.sqrt(np.mean(indata**2)))
            peak = float(np.max(np.abs(indata)))
            rms_db = 20.0 * np.log10(rms) if rms > 0 else -120.0
            peak_db = 20.0 * np.log10(peak) if peak > 0 else -120.0
            clipped = peak >= 0.99
            try:
                self._level_callback(rms_db, peak_db, clipped)
            except Exception:
                pass  # Don't let callback errors kill the stream

    def _device_name(self) -> str:
        if self.device_index is None:
            return "default"
        try:
            info = sd.query_devices(self.device_index)
            return info["name"]
        except Exception:
            return f"device-{self.device_index}"
