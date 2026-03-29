"""Target curves for room EQ.

Provides preset target curves (Harman In-Room, flat, etc.) and support for
custom user-defined targets.  All targets are defined as dB offset vs
frequency and can be interpolated to arbitrary frequency grids.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum

import numpy as np

logger = logging.getLogger("roomtune.targets")


class TargetPreset(str, Enum):
    """Built-in target curve presets."""

    FLAT = "flat"
    HARMAN = "harman"
    HARMAN_BASS_BOOST = "harman_bass_boost"
    BBC_DIP = "bbc_dip"


@dataclass
class TargetCurve:
    """A target frequency response curve for EQ optimisation."""

    name: str
    frequencies: np.ndarray = field(repr=False)  # Hz
    amplitude_db: np.ndarray = field(repr=False)  # dB offset from flat

    def at_frequencies(self, freqs: np.ndarray) -> np.ndarray:
        """Interpolate target to arbitrary frequencies (log-freq domain)."""
        log_f = np.log10(np.maximum(self.frequencies, 1.0))
        log_q = np.log10(np.maximum(freqs, 1.0))
        return np.interp(log_q, log_f, self.amplitude_db)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "frequencies": self.frequencies.tolist(),
            "amplitude_db": self.amplitude_db.tolist(),
        }


def get_target(preset: TargetPreset | str) -> TargetCurve:
    """Return a built-in target curve.

    Parameters
    ----------
    preset : TargetPreset or str
        The preset name.

    Returns
    -------
    TargetCurve
    """
    if isinstance(preset, str):
        preset = TargetPreset(preset)

    if preset == TargetPreset.FLAT:
        return _flat_target()
    elif preset == TargetPreset.HARMAN:
        return _harman_target()
    elif preset == TargetPreset.HARMAN_BASS_BOOST:
        return _harman_bass_boost_target()
    elif preset == TargetPreset.BBC_DIP:
        return _bbc_dip_target()
    else:
        raise ValueError(f"Unknown preset: {preset}")


def custom_target(
    frequencies: list[float], amplitudes_db: list[float], name: str = "custom"
) -> TargetCurve:
    """Create a custom target curve from user-defined control points.

    Points are interpolated in the log-frequency domain.
    """
    return TargetCurve(
        name=name,
        frequencies=np.array(frequencies, dtype=np.float64),
        amplitude_db=np.array(amplitudes_db, dtype=np.float64),
    )


# ---------------------------------------------------------------------------
# Preset definitions
# ---------------------------------------------------------------------------

# Standard frequency grid for presets
_PRESET_FREQS = np.array(
    [
        20,
        25,
        31.5,
        40,
        50,
        63,
        80,
        100,
        125,
        160,
        200,
        250,
        315,
        400,
        500,
        630,
        800,
        1000,
        1250,
        1600,
        2000,
        2500,
        3150,
        4000,
        5000,
        6300,
        8000,
        10000,
        12500,
        16000,
        20000,
    ],
    dtype=np.float64,
)


def _flat_target() -> TargetCurve:
    """Perfectly flat target (0 dB at all frequencies)."""
    return TargetCurve(
        name="Flat",
        frequencies=_PRESET_FREQS.copy(),
        amplitude_db=np.zeros(len(_PRESET_FREQS), dtype=np.float64),
    )


def _harman_target() -> TargetCurve:
    """Harman In-Room target curve (2019 revision approximation).

    Gentle downward tilt from bass to treble, about -1 dB/octave above 200 Hz,
    with a bass shelf and slight treble roll-off.
    """
    # Approximate Harman in-room target (dB relative to 1 kHz)
    db = np.array(
        [
            6.0,
            5.8,
            5.5,
            5.0,
            4.5,
            4.0,
            3.5,
            3.0,
            2.5,
            2.0,
            1.5,
            1.0,
            0.7,
            0.4,
            0.2,
            0.0,
            0.0,
            0.0,
            -0.2,
            -0.5,
            -0.8,
            -1.0,
            -1.3,
            -1.5,
            -1.8,
            -2.2,
            -2.8,
            -3.5,
            -4.5,
            -6.0,
            -8.0,
        ],
        dtype=np.float64,
    )
    return TargetCurve(name="Harman In-Room", frequencies=_PRESET_FREQS.copy(), amplitude_db=db)


def _harman_bass_boost_target() -> TargetCurve:
    """Harman target with +3 dB additional bass boost below 100 Hz."""
    harman = _harman_target()
    boost = np.where(harman.frequencies <= 100, 3.0, 0.0)
    # Smooth transition between 100–200 Hz
    transition = (harman.frequencies > 100) & (harman.frequencies <= 200)
    boost[transition] = 3.0 * (1.0 - np.log10(harman.frequencies[transition] / 100) / np.log10(2))
    return TargetCurve(
        name="Harman + Bass Boost",
        frequencies=harman.frequencies,
        amplitude_db=harman.amplitude_db + boost,
    )


def _bbc_dip_target() -> TargetCurve:
    """Flat with a ~3 dB dip around 2-4 kHz (BBC-style listener preference)."""
    db = np.zeros(len(_PRESET_FREQS), dtype=np.float64)
    # Apply a gentle dip centered around 3 kHz
    for i, f in enumerate(_PRESET_FREQS):
        if 1500 < f < 6000:
            # Gaussian-ish dip centered at 3 kHz in log domain
            log_dist = np.log2(f / 3000)
            db[i] = -3.0 * np.exp(-2 * log_dist**2)
    return TargetCurve(name="BBC Dip", frequencies=_PRESET_FREQS.copy(), amplitude_db=db)
