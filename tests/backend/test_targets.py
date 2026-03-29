"""Test target curves."""

import numpy as np
import pytest

from backend.eq.targets import TargetPreset, get_target, custom_target


class TestTargetPresets:
    def test_flat(self):
        target = get_target(TargetPreset.FLAT)
        assert target.name == "Flat"
        assert np.all(target.amplitude_db == 0.0)

    def test_harman(self):
        target = get_target(TargetPreset.HARMAN)
        assert target.name == "Harman In-Room"
        # Harman: bass boosted, treble rolled off relative to midrange
        assert target.amplitude_db[0] > 0  # bass boost
        assert target.amplitude_db[-1] < 0  # treble rolloff

    def test_harman_bass_boost(self):
        target = get_target(TargetPreset.HARMAN_BASS_BOOST)
        harman = get_target(TargetPreset.HARMAN)
        # Should have more bass boost than regular Harman
        assert target.amplitude_db[0] > harman.amplitude_db[0]

    def test_interpolation(self):
        target = get_target(TargetPreset.FLAT)
        freqs = np.array([100.0, 1000.0, 10000.0])
        result = target.at_frequencies(freqs)
        assert len(result) == 3
        assert np.allclose(result, 0.0, atol=0.01)


class TestCustomTarget:
    def test_create(self):
        target = custom_target([100, 1000, 10000], [3.0, 0.0, -3.0])
        assert target.name == "custom"
        assert len(target.frequencies) == 3

    def test_interpolation(self):
        target = custom_target([100, 10000], [6.0, -6.0])
        mid = target.at_frequencies(np.array([1000.0]))
        # Should be somewhere between 6 and -6
        assert -6.0 < mid[0] < 6.0
