"""Logarithmic sine sweep generation for room impulse response measurement.

Generates an exponential (log) swept sine signal from ``f_start`` to ``f_end``
with configurable duration and sample rate.  Includes a pre/post silence
padding and fade-in/out to avoid clicks.

The inverse sweep filter is also generated so that the impulse response can
be extracted via deconvolution (see ``backend.analysis.impulse``).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np

logger = logging.getLogger("roomtune.sweep")


@dataclass
class SweepSignal:
    """Container for a generated sweep and its inverse filter."""

    signal: np.ndarray = field(repr=False)  # The sweep waveform (float64, -1..1)
    inverse: np.ndarray = field(repr=False)  # Inverse filter for deconvolution
    sample_rate: int = 48000
    f_start: float = 20.0
    f_end: float = 20000.0
    duration: float = 5.0  # Sweep duration in seconds (excl. padding)
    padding: float = 0.5  # Silence before/after in seconds
    total_samples: int = 0

    @property
    def total_duration(self) -> float:
        return self.total_samples / self.sample_rate


def generate_sweep(
    f_start: float = 20.0,
    f_end: float = 20000.0,
    duration: float = 5.0,
    sample_rate: int = 48000,
    amplitude: float = 0.8,
    padding: float = 0.5,
    fade_ms: float = 10.0,
) -> SweepSignal:
    """Generate a logarithmic (exponential) sine sweep.

    Parameters
    ----------
    f_start : float
        Start frequency in Hz (default 20).
    f_end : float
        End frequency in Hz (default 20 000).
    duration : float
        Sweep duration in seconds (default 5).
    sample_rate : int
        Sample rate in Hz (default 48 000).
    amplitude : float
        Peak amplitude, 0..1 (default 0.8).
    padding : float
        Silence added before and after the sweep in seconds (default 0.5).
    fade_ms : float
        Fade-in and fade-out duration in milliseconds (default 10).

    Returns
    -------
    SweepSignal
        Dataclass containing the sweep waveform and its inverse filter.
    """
    n_sweep = int(duration * sample_rate)
    n_pad = int(padding * sample_rate)
    n_fade = int(fade_ms / 1000.0 * sample_rate)

    # Time vector for the sweep portion
    t = np.arange(n_sweep, dtype=np.float64) / sample_rate

    # Exponential sweep: x(t) = sin(2π f1 T / ln(f2/f1) * (exp(t/T * ln(f2/f1)) - 1))
    # where T = duration, f1 = f_start, f2 = f_end
    w1 = 2.0 * np.pi * f_start
    log_ratio = np.log(f_end / f_start)
    sweep_rate = duration / log_ratio  # T / ln(f2/f1)

    phase = w1 * sweep_rate * (np.exp(t / duration * log_ratio) - 1.0)
    sweep = amplitude * np.sin(phase)

    # Fade in/out to avoid clicks
    if n_fade > 0 and n_fade < n_sweep // 2:
        fade_in = np.linspace(0.0, 1.0, n_fade)
        fade_out = np.linspace(1.0, 0.0, n_fade)
        sweep[:n_fade] *= fade_in
        sweep[-n_fade:] *= fade_out

    # Pad with silence
    full_signal = np.concatenate(
        [
            np.zeros(n_pad, dtype=np.float64),
            sweep,
            np.zeros(n_pad, dtype=np.float64),
        ]
    )

    # --- Inverse filter ---
    # For an exponential sweep, the inverse filter is the time-reversed sweep
    # with an amplitude envelope that compensates for the sweep rate:
    #   k(t) ∝ exp(-t / T * ln(f2/f1))
    # This ensures the deconvolution yields a flat frequency response.
    envelope = np.exp(-t / duration * log_ratio)
    inverse_sweep = envelope * sweep[::-1]

    # Normalise so that convolving sweep * inverse gives unity peak
    # (we normalise after convolution in impulse.py, so just basic scaling here)
    energy = np.sum(sweep**2)
    if energy > 0:
        inverse_sweep *= n_sweep / energy

    # Pad inverse the same way (for alignment)
    inverse_full = np.concatenate(
        [
            np.zeros(n_pad, dtype=np.float64),
            inverse_sweep,
            np.zeros(n_pad, dtype=np.float64),
        ]
    )

    result = SweepSignal(
        signal=full_signal,
        inverse=inverse_full,
        sample_rate=sample_rate,
        f_start=f_start,
        f_end=f_end,
        duration=duration,
        padding=padding,
        total_samples=len(full_signal),
    )

    logger.info(
        "Generated sweep: %.0f–%.0f Hz, %.1f s (%.1f s total), %d samples @ %d Hz",
        f_start,
        f_end,
        duration,
        result.total_duration,
        result.total_samples,
        sample_rate,
    )
    return result


def sweep_to_wav_bytes(sweep: SweepSignal, channel: str = "both") -> bytes:
    """Convert a sweep signal to WAV file bytes for playback via MPD/Moode.

    Parameters
    ----------
    sweep : SweepSignal
        The sweep to convert.
    channel : str
        ``"left"``, ``"right"``, or ``"both"`` (default).

    Returns
    -------
    bytes
        WAV file content (16-bit PCM, stereo).
    """
    import io
    import wave

    signal = sweep.signal.copy()

    # Create stereo signal
    if channel == "left":
        stereo = np.column_stack([signal, np.zeros_like(signal)])
    elif channel == "right":
        stereo = np.column_stack([np.zeros_like(signal), signal])
    else:
        stereo = np.column_stack([signal, signal])

    # Convert to 16-bit PCM
    pcm = (stereo * 32767).clip(-32768, 32767).astype(np.int16)

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sweep.sample_rate)
        wf.writeframes(pcm.tobytes())

    return buf.getvalue()
