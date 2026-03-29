"""Impulse response extraction via deconvolution.

Given a recorded sweep response and the original sweep's inverse filter,
computes the room impulse response (RIR) using FFT-based deconvolution.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
from scipy import signal as sig

from backend.audio.sweep import SweepSignal
from backend.audio.recorder import Recording

logger = logging.getLogger("roomtune.impulse")


@dataclass
class ImpulseResponse:
    """Room impulse response extracted from a sweep measurement."""

    data: np.ndarray = field(repr=False)  # 1-D float64
    sample_rate: int = 48000
    peak_index: int = 0
    peak_amplitude: float = 0.0
    length_seconds: float = 0.0

    @property
    def num_samples(self) -> int:
        return len(self.data)

    @property
    def peak_time(self) -> float:
        """Time of the peak (direct sound arrival) in seconds."""
        return self.peak_index / self.sample_rate

    def windowed(self, pre_ms: float = 5.0, post_ms: float = 500.0) -> np.ndarray:
        """Return a windowed portion of the IR around the peak.

        Parameters
        ----------
        pre_ms : float
            Milliseconds to include before the peak (default 5).
        post_ms : float
            Milliseconds to include after the peak (default 500).

        Returns
        -------
        np.ndarray
            Windowed IR segment.
        """
        pre_samples = int(pre_ms / 1000.0 * self.sample_rate)
        post_samples = int(post_ms / 1000.0 * self.sample_rate)
        start = max(0, self.peak_index - pre_samples)
        end = min(len(self.data), self.peak_index + post_samples)
        return self.data[start:end]


def extract_impulse_response(
    recording: Recording,
    sweep: SweepSignal,
    regularization: float = 1e-6,
) -> ImpulseResponse:
    """Extract the room impulse response from a sweep recording.

    Uses FFT-based deconvolution: ``IR = IFFT(FFT(recording) * FFT(inverse_sweep))``.

    Parameters
    ----------
    recording : Recording
        The recorded sweep response from the microphone.
    sweep : SweepSignal
        The original sweep signal (contains the inverse filter).
    regularization : float
        Small value added to avoid division by zero in spectral division
        (default 1e-6).

    Returns
    -------
    ImpulseResponse
    """
    rec_mono = recording.to_mono()
    inverse = sweep.inverse

    # Determine FFT length (next power of 2 for efficiency)
    n = len(rec_mono) + len(inverse) - 1
    n_fft = int(2 ** np.ceil(np.log2(n)))

    logger.info(
        "Extracting IR: recording=%d, inverse=%d, FFT size=%d",
        len(rec_mono),
        len(inverse),
        n_fft,
    )

    # FFT-based deconvolution
    rec_fft = np.fft.rfft(rec_mono, n=n_fft)
    inv_fft = np.fft.rfft(inverse, n=n_fft)

    # Multiply in frequency domain (convolution)
    ir_fft = rec_fft * inv_fft
    ir = np.fft.irfft(ir_fft, n=n_fft)

    # Trim to reasonable length (2x sweep duration should be more than enough)
    max_len = int(2 * sweep.duration * sweep.sample_rate)
    ir = ir[:max_len]

    # Normalise to unit peak
    peak_idx = int(np.argmax(np.abs(ir)))
    peak_amp = float(np.abs(ir[peak_idx]))
    if peak_amp > 0:
        ir = ir / peak_amp

    result = ImpulseResponse(
        data=ir,
        sample_rate=sweep.sample_rate,
        peak_index=peak_idx,
        peak_amplitude=peak_amp,
        length_seconds=len(ir) / sweep.sample_rate,
    )

    logger.info(
        "IR extracted: %d samples (%.2f s), peak at %.1f ms",
        result.num_samples,
        result.length_seconds,
        result.peak_time * 1000,
    )
    return result
