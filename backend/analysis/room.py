"""Room acoustic analysis: RT60, room modes, and related metrics.

Computes reverberation time (RT60) using the Schroeder backward integration
method, and identifies room modes from room dimensions.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
from scipy import signal as sig
from scipy.stats import linregress

from backend.analysis.impulse import ImpulseResponse

logger = logging.getLogger("roomtune.room")


@dataclass
class RT60Result:
    """Reverberation time analysis results."""

    rt60: float  # Estimated RT60 in seconds
    edt: float  # Early Decay Time in seconds
    t20: float  # T20 (extrapolated from -5 to -25 dB)
    t30: float  # T30 (extrapolated from -5 to -35 dB)
    confidence: float  # R² of the linear fit (0..1)
    decay_curve_db: np.ndarray  # Schroeder decay curve in dB
    decay_time: np.ndarray  # Time axis for decay curve


@dataclass
class RoomMode:
    """A room resonance mode."""

    frequency: float  # Hz
    mode_type: str  # "axial", "tangential", or "oblique"
    indices: tuple[int, int, int]  # (nx, ny, nz)


def compute_rt60(ir: ImpulseResponse, freq_band: tuple[float, float] | None = None) -> RT60Result:
    """Compute RT60 using Schroeder backward integration.

    Parameters
    ----------
    ir : ImpulseResponse
        Room impulse response.
    freq_band : tuple[float, float], optional
        If given, bandpass-filter the IR to this frequency range before analysis.

    Returns
    -------
    RT60Result
    """
    data = ir.data.copy()
    sr = ir.sample_rate

    # Optional bandpass filtering
    if freq_band is not None:
        f_low, f_high = freq_band
        nyq = sr / 2.0
        low = max(f_low / nyq, 0.001)
        high = min(f_high / nyq, 0.999)
        sos = sig.butter(4, [low, high], btype="band", output="sos")
        data = sig.sosfilt(sos, data)

    # Start from the peak (direct sound)
    peak_idx = int(np.argmax(np.abs(data)))
    data = data[peak_idx:]

    # Schroeder backward integration
    # Energy decay curve: EDC(t) = integral from t to inf of h²(τ) dτ
    energy = data**2
    edc = np.cumsum(energy[::-1])[::-1]
    edc = np.maximum(edc, 1e-20)  # avoid log(0)
    edc_db = 10.0 * np.log10(edc / edc[0])

    time_axis = np.arange(len(edc_db)) / sr

    # --- Fit linear decay for different ranges ---
    def _fit_range(db_start: float, db_end: float) -> tuple[float, float]:
        """Fit a line to the decay curve between db_start and db_end dB.
        Returns (decay_time_60dB, r_squared)."""
        mask = (edc_db >= db_end) & (edc_db <= db_start)
        if np.sum(mask) < 10:
            return 0.0, 0.0
        t_fit = time_axis[mask]
        db_fit = edc_db[mask]
        slope, intercept, r_value, _, _ = linregress(t_fit, db_fit)
        if slope >= 0:
            return 0.0, 0.0
        # Extrapolate to -60 dB
        rt = -60.0 / slope
        return float(rt), float(r_value**2)

    # EDT: 0 to -10 dB, extrapolated to -60 dB
    edt, _ = _fit_range(0.0, -10.0)

    # T20: -5 to -25 dB, extrapolated to -60 dB
    t20, r2_20 = _fit_range(-5.0, -25.0)

    # T30: -5 to -35 dB, extrapolated to -60 dB
    t30, r2_30 = _fit_range(-5.0, -35.0)

    # Use T30 as the primary RT60 estimate; fall back to T20
    if t30 > 0 and r2_30 > 0.8:
        rt60 = t30
        confidence = r2_30
    elif t20 > 0:
        rt60 = t20
        confidence = r2_20
    else:
        rt60 = edt
        confidence = 0.0

    logger.info(
        "RT60=%.2f s (EDT=%.2f, T20=%.2f, T30=%.2f, R²=%.3f)",
        rt60,
        edt,
        t20,
        t30,
        confidence,
    )

    return RT60Result(
        rt60=rt60,
        edt=edt,
        t20=t20,
        t30=t30,
        confidence=confidence,
        decay_curve_db=edc_db,
        decay_time=time_axis,
    )


def compute_room_modes(
    length: float,
    width: float,
    height: float,
    max_freq: float = 300.0,
    speed_of_sound: float = 343.0,
    max_order: int = 4,
) -> list[RoomMode]:
    """Compute room resonance modes from dimensions.

    Uses the formula: f = (c/2) * sqrt((nx/L)² + (ny/W)² + (nz/H)²)

    Parameters
    ----------
    length, width, height : float
        Room dimensions in metres.
    max_freq : float
        Only return modes below this frequency (default 300 Hz).
    speed_of_sound : float
        Speed of sound in m/s (default 343).
    max_order : int
        Maximum mode order to compute in each dimension (default 4).

    Returns
    -------
    list[RoomMode]
        Sorted by frequency.
    """
    modes: list[RoomMode] = []

    for nx in range(0, max_order + 1):
        for ny in range(0, max_order + 1):
            for nz in range(0, max_order + 1):
                if nx == 0 and ny == 0 and nz == 0:
                    continue

                f = (speed_of_sound / 2.0) * np.sqrt(
                    (nx / length) ** 2 + (ny / width) ** 2 + (nz / height) ** 2
                )

                if f > max_freq:
                    continue

                # Classify mode type
                nonzero = sum(1 for n in (nx, ny, nz) if n > 0)
                if nonzero == 1:
                    mode_type = "axial"
                elif nonzero == 2:
                    mode_type = "tangential"
                else:
                    mode_type = "oblique"

                modes.append(
                    RoomMode(
                        frequency=float(f),
                        mode_type=mode_type,
                        indices=(nx, ny, nz),
                    )
                )

    modes.sort(key=lambda m: m.frequency)
    logger.info("Computed %d room modes below %.0f Hz", len(modes), max_freq)
    return modes
