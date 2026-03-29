"""Biquad filter design for parametric EQ.

Implements the Audio EQ Cookbook (Robert Bristow-Johnson) biquad filter
formulas: Peaking EQ, Low Shelf, and High Shelf.  Each filter is defined
by centre/corner frequency, gain in dB, and Q factor.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from math import cos, log, pi, sin, sqrt

import numpy as np

logger = logging.getLogger("roomtune.filters")


class FilterType(str, Enum):
    PEAKING = "peaking"
    LOW_SHELF = "low_shelf"
    HIGH_SHELF = "high_shelf"


@dataclass
class BiquadFilter:
    """A single biquad (second-order IIR) filter."""

    filter_type: FilterType
    frequency: float  # Centre or corner frequency (Hz)
    gain_db: float  # Gain in dB (negative = cut)
    q: float  # Q factor (bandwidth)

    # Biquad coefficients (normalised so a0 = 1)
    b0: float = 0.0
    b1: float = 0.0
    b2: float = 0.0
    a1: float = 0.0
    a2: float = 0.0

    def magnitude_response(self, freqs: np.ndarray, sample_rate: int = 48000) -> np.ndarray:
        """Compute magnitude response (dB) at given frequencies."""
        w = 2.0 * np.pi * freqs / sample_rate
        z = np.exp(1j * w)
        z2 = z**2

        H = (self.b0 + self.b1 / z + self.b2 / z2) / (1.0 + self.a1 / z + self.a2 / z2)
        return 20.0 * np.log10(np.maximum(np.abs(H), 1e-10))

    def to_dict(self) -> dict:
        return {
            "type": self.filter_type.value,
            "frequency": round(self.frequency, 1),
            "gain_db": round(self.gain_db, 2),
            "q": round(self.q, 3),
            "coefficients": {
                "b0": self.b0,
                "b1": self.b1,
                "b2": self.b2,
                "a1": self.a1,
                "a2": self.a2,
            },
        }

    def to_camilladsp(self) -> dict:
        """Convert to CamillaDSP filter config format."""
        type_map = {
            FilterType.PEAKING: "Peaking",
            FilterType.LOW_SHELF: "Lowshelf",
            FilterType.HIGH_SHELF: "Highshelf",
        }
        return {
            "type": "Biquad",
            "parameters": {
                "type": type_map[self.filter_type],
                "freq": self.frequency,
                "gain": self.gain_db,
                "q": self.q,
            },
        }


def design_peaking(
    frequency: float,
    gain_db: float,
    q: float,
    sample_rate: int = 48000,
) -> BiquadFilter:
    """Design a peaking EQ filter (Audio EQ Cookbook).

    Parameters
    ----------
    frequency : float
        Centre frequency in Hz.
    gain_db : float
        Gain in dB (negative for cut).
    q : float
        Q factor (higher = narrower).
    sample_rate : int
        Sample rate in Hz.

    Returns
    -------
    BiquadFilter
    """
    A = 10.0 ** (gain_db / 40.0)
    w0 = 2.0 * pi * frequency / sample_rate
    alpha = sin(w0) / (2.0 * q)

    b0 = 1.0 + alpha * A
    b1 = -2.0 * cos(w0)
    b2 = 1.0 - alpha * A
    a0 = 1.0 + alpha / A
    a1 = -2.0 * cos(w0)
    a2 = 1.0 - alpha / A

    return BiquadFilter(
        filter_type=FilterType.PEAKING,
        frequency=frequency,
        gain_db=gain_db,
        q=q,
        b0=b0 / a0,
        b1=b1 / a0,
        b2=b2 / a0,
        a1=a1 / a0,
        a2=a2 / a0,
    )


def design_low_shelf(
    frequency: float,
    gain_db: float,
    q: float = 0.707,
    sample_rate: int = 48000,
) -> BiquadFilter:
    """Design a low shelf filter (Audio EQ Cookbook)."""
    A = 10.0 ** (gain_db / 40.0)
    w0 = 2.0 * pi * frequency / sample_rate
    alpha = sin(w0) / (2.0 * q)
    two_sqrt_A_alpha = 2.0 * sqrt(A) * alpha

    b0 = A * ((A + 1) - (A - 1) * cos(w0) + two_sqrt_A_alpha)
    b1 = 2 * A * ((A - 1) - (A + 1) * cos(w0))
    b2 = A * ((A + 1) - (A - 1) * cos(w0) - two_sqrt_A_alpha)
    a0 = (A + 1) + (A - 1) * cos(w0) + two_sqrt_A_alpha
    a1 = -2 * ((A - 1) + (A + 1) * cos(w0))
    a2 = (A + 1) + (A - 1) * cos(w0) - two_sqrt_A_alpha

    return BiquadFilter(
        filter_type=FilterType.LOW_SHELF,
        frequency=frequency,
        gain_db=gain_db,
        q=q,
        b0=b0 / a0,
        b1=b1 / a0,
        b2=b2 / a0,
        a1=a1 / a0,
        a2=a2 / a0,
    )


def design_high_shelf(
    frequency: float,
    gain_db: float,
    q: float = 0.707,
    sample_rate: int = 48000,
) -> BiquadFilter:
    """Design a high shelf filter (Audio EQ Cookbook)."""
    A = 10.0 ** (gain_db / 40.0)
    w0 = 2.0 * pi * frequency / sample_rate
    alpha = sin(w0) / (2.0 * q)
    two_sqrt_A_alpha = 2.0 * sqrt(A) * alpha

    b0 = A * ((A + 1) + (A - 1) * cos(w0) + two_sqrt_A_alpha)
    b1 = -2 * A * ((A - 1) + (A + 1) * cos(w0))
    b2 = A * ((A + 1) + (A - 1) * cos(w0) - two_sqrt_A_alpha)
    a0 = (A + 1) - (A - 1) * cos(w0) + two_sqrt_A_alpha
    a1 = 2 * ((A - 1) - (A + 1) * cos(w0))
    a2 = (A + 1) - (A - 1) * cos(w0) - two_sqrt_A_alpha

    return BiquadFilter(
        filter_type=FilterType.HIGH_SHELF,
        frequency=frequency,
        gain_db=gain_db,
        q=q,
        b0=b0 / a0,
        b1=b1 / a0,
        b2=b2 / a0,
        a1=a1 / a0,
        a2=a2 / a0,
    )


def combined_response(
    filters: list[BiquadFilter],
    freqs: np.ndarray,
    sample_rate: int = 48000,
) -> np.ndarray:
    """Compute the combined magnitude response of multiple filters (dB)."""
    total = np.zeros(len(freqs), dtype=np.float64)
    for f in filters:
        total += f.magnitude_response(freqs, sample_rate)
    return total
