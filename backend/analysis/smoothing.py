"""Fractional-octave smoothing for frequency responses.

Implements variable-bandwidth smoothing commonly used in acoustic
measurements (1/3, 1/6, 1/12, 1/24 octave, etc.).
"""

from __future__ import annotations

import logging

import numpy as np
from scipy.ndimage import uniform_filter1d

from backend.analysis.frequency import FrequencyResponse

logger = logging.getLogger("roomtune.smoothing")


def octave_smooth(
    fr: FrequencyResponse,
    fraction: float = 3.0,
    f_low: float = 20.0,
    f_high: float = 20000.0,
) -> FrequencyResponse:
    """Apply fractional-octave smoothing to a frequency response.

    Smoothing is performed in the log-frequency domain so that the effective
    bandwidth is proportional to frequency (constant-Q smoothing), which is
    what ``1/N``-octave smoothing means.

    Parameters
    ----------
    fr : FrequencyResponse
        Input frequency response.
    fraction : float
        Octave fraction (e.g., 3 for 1/3 octave, 6 for 1/6, 12 for 1/12).
    f_low : float
        Lower frequency bound for output (default 20 Hz).
    f_high : float
        Upper frequency bound for output (default 20 kHz).

    Returns
    -------
    FrequencyResponse
        Smoothed frequency response.
    """
    freqs = fr.frequencies
    mag_db = fr.magnitude_db.copy()
    phase = fr.phase_deg.copy()

    # Restrict to positive frequencies and requested range
    mask = (freqs > 0) & (freqs >= f_low) & (freqs <= f_high)
    freqs_pos = freqs[mask]
    mag_pos = mag_db[mask]
    phase_pos = phase[mask]

    if len(freqs_pos) < 3:
        logger.warning("Not enough frequency points for smoothing")
        return fr

    # Resample to uniform log-frequency spacing
    log_freqs = np.log2(freqs_pos)
    n_points = len(freqs_pos)
    log_uniform = np.linspace(log_freqs[0], log_freqs[-1], n_points)

    # Interpolate magnitude to uniform log-freq grid
    mag_interp = np.interp(log_uniform, log_freqs, mag_pos)

    # Determine smoothing kernel width
    # 1/N octave means the bandwidth at each frequency is freq * (2^(1/2N) - 2^(-1/2N))
    # In the uniform log-frequency domain, this is a constant width of 1/N octaves.
    log_span = log_uniform[-1] - log_uniform[0]
    points_per_octave = n_points / log_span if log_span > 0 else n_points
    kernel_width = max(1, int(round(points_per_octave / fraction)))

    # Apply uniform filter (moving average in log-freq domain)
    mag_smooth = uniform_filter1d(mag_interp, size=kernel_width, mode="nearest")

    # Interpolate back to original frequency points
    mag_result = np.interp(log_freqs, log_uniform, mag_smooth)

    label = f"1/{int(fraction)}" if fraction == int(fraction) else f"1/{fraction:.1f}"

    result = FrequencyResponse(
        frequencies=freqs_pos,
        magnitude_db=mag_result,
        phase_deg=phase_pos,  # phase is not smoothed
        sample_rate=fr.sample_rate,
        calibrated=fr.calibrated,
        smoothing=f"{label} octave",
    )

    logger.info(
        "Applied %s octave smoothing (%d-point kernel, %d points)",
        label,
        kernel_width,
        len(freqs_pos),
    )
    return result
