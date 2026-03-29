"""Test sweep generation."""

import numpy as np
import pytest

from backend.audio.sweep import SweepSignal, generate_sweep, sweep_to_wav_bytes


class TestSweepGeneration:
    def test_basic_sweep(self):
        sweep = generate_sweep(duration=1.0, sample_rate=48000)
        assert isinstance(sweep, SweepSignal)
        assert sweep.sample_rate == 48000
        assert sweep.duration == 1.0
        assert sweep.total_samples > 48000  # At least 1 second + padding

    def test_sweep_amplitude(self):
        sweep = generate_sweep(amplitude=0.5, duration=1.0)
        # Peak should be close to the amplitude (may be slightly less due to fade)
        assert np.max(np.abs(sweep.signal)) <= 0.51
        assert np.max(np.abs(sweep.signal)) > 0.3  # Not all zeros

    def test_sweep_has_inverse(self):
        sweep = generate_sweep(duration=1.0)
        assert len(sweep.inverse) == len(sweep.signal)
        assert np.any(sweep.inverse != 0)

    def test_sweep_padding(self):
        sweep = generate_sweep(duration=1.0, padding=0.5, sample_rate=48000)
        # First 0.5s should be silence (padding)
        pad_samples = int(0.5 * 48000)
        assert np.max(np.abs(sweep.signal[:pad_samples])) < 1e-10
        # Last 0.5s should be silence
        assert np.max(np.abs(sweep.signal[-pad_samples:])) < 1e-10

    def test_wav_bytes(self):
        sweep = generate_sweep(duration=0.5, sample_rate=48000)
        wav = sweep_to_wav_bytes(sweep, channel="both")
        assert isinstance(wav, bytes)
        assert len(wav) > 0
        # WAV header starts with RIFF
        assert wav[:4] == b"RIFF"

    def test_wav_channels(self):
        sweep = generate_sweep(duration=0.5)
        wav_left = sweep_to_wav_bytes(sweep, channel="left")
        wav_right = sweep_to_wav_bytes(sweep, channel="right")
        wav_both = sweep_to_wav_bytes(sweep, channel="both")
        # All should produce valid WAV files of same size
        assert len(wav_left) == len(wav_right) == len(wav_both)
