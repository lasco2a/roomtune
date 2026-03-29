"""Frequency response computation from impulse responses.

Computes the magnitude frequency response from a room impulse response,
optionally applying the UMIK-1 calibration correction.  Supports windowing
and optional octave smoothing.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
from scipy import signal as sig

from backend.analysis.impulse import ImpulseResponse
from backend.audio.calibration import CalibrationData

logger = logging.getLogger("roomtune.frequency")


@dataclass
class FrequencyResponse:
    """Magnitude frequency response."""

    frequencies: np.ndarray = field(repr=False)  # Hz
    magnitude_db: np.ndarray = field(repr=False)  # dB (relative)
    phase_deg: np.ndarray = field(repr=False)  # degrees
    sample_rate: int = 48000
    calibrated: bool = False
    smoothing: str = "none"

    @property
    def num_points(self) -> int:
        return len(self.frequencies)

    def in_range(self, f_low: float = 20.0, f_high: float = 20000.0) -> "FrequencyResponse":
        """Return a new FrequencyResponse limited to [f_low, f_high]."""
        mask = (self.frequencies >= f_low) & (self.frequencies <= f_high)
        return FrequencyResponse(
            frequencies=self.frequencies[mask],
            magnitude_db=self.magnitude_db[mask],
            phase_deg=self.phase_deg[mask],
            sample_rate=self.sample_rate,
            calibrated=self.calibrated,
            smoothing=self.smoothing,
        )

    def to_dict(self) -> dict:
        return {
            "frequencies": self.frequencies.tolist(),
            "magnitude_db": self.magnitude_db.tolist(),
            "phase_deg": self.phase_deg.tolist(),
            "num_points": self.num_points,
            "calibrated": self.calibrated,
            "smoothing": self.smoothing,
        }


def compute_frequency_response(
    ir: ImpulseResponse,
    window: str = "hann",
    n_fft: int | None = None,
    calibration: CalibrationData | None = None,
) -> FrequencyResponse:
    """Compute the frequency response from an impulse response.

    Parameters
    ----------
    ir : ImpulseResponse
        Room impulse response.
    window : str
        Window function applied to the IR before FFT (default ``"hann"``).
        Use ``"none"`` or ``"rectangular"`` for no windowing.
    n_fft : int, optional
        FFT length. Defaults to the IR length (zero-padded to next power of 2).
    calibration : CalibrationData, optional
        If provided, the mic calibration correction is applied.

    Returns
    -------
    FrequencyResponse
    """
    data = ir.data.copy()

    # Apply window
    if window not in ("none", "rectangular"):
        w = sig.get_window(window, len(data))
        data = data * w

    # FFT
    if n_fft is None:
        n_fft = int(2 ** np.ceil(np.log2(len(data))))

    spectrum = np.fft.rfft(data, n=n_fft)
    freqs = np.fft.rfftfreq(n_fft, d=1.0 / ir.sample_rate)

    magnitude = np.abs(spectrum)
    phase = np.angle(spectrum, deg=True)

    # Convert to dB (with floor to avoid -inf)
    mag_db = 20.0 * np.log10(np.maximum(magnitude, 1e-10))

    # Apply calibration correction
    calibrated = False
    if calibration is not None:
        correction = calibration.correction_at(freqs[1:])  # skip DC
        mag_db[1:] -= correction  # subtract because cal file gives mic's deviation
        calibrated = True
        logger.info("Applied calibration correction from %s", calibration.path)

    result = FrequencyResponse(
        frequencies=freqs,
        magnitude_db=mag_db,
        phase_deg=phase,
        sample_rate=ir.sample_rate,
        calibrated=calibrated,
        smoothing="none",
    )

    logger.info(
        "Frequency response: %d points, %.1f–%.1f Hz, calibrated=%s",
        result.num_points,
        freqs[1] if len(freqs) > 1 else 0,
        freqs[-1] if len(freqs) > 0 else 0,
        calibrated,
    )
    return result
