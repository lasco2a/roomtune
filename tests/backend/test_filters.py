"""Test biquad filter design."""

import numpy as np
import pytest

from backend.eq.filters import (
    FilterType,
    combined_response,
    design_high_shelf,
    design_low_shelf,
    design_peaking,
)


class TestPeakingFilter:
    def test_unity_at_zero_gain(self):
        filt = design_peaking(1000, 0.0, 1.0)
        freqs = np.logspace(1, 4.3, 500)
        response = filt.magnitude_response(freqs)
        # Should be flat (0 dB) everywhere
        assert np.allclose(response, 0.0, atol=0.01)

    def test_peak_at_center(self):
        filt = design_peaking(1000, -6.0, 2.0)
        freqs = np.logspace(1, 4.3, 1000)
        response = filt.magnitude_response(freqs)
        # Find the minimum (since gain is negative)
        min_idx = np.argmin(response)
        min_freq = freqs[min_idx]
        # Should be near 1000 Hz
        assert 900 < min_freq < 1100
        # Gain at center should be close to -6 dB
        assert abs(response[min_idx] - (-6.0)) < 0.5

    def test_to_camilladsp(self):
        filt = design_peaking(1000, -3.0, 2.0)
        config = filt.to_camilladsp()
        assert config["type"] == "Biquad"
        assert config["parameters"]["type"] == "Peaking"
        assert config["parameters"]["freq"] == 1000
        assert config["parameters"]["gain"] == -3.0
        assert config["parameters"]["q"] == 2.0


class TestShelfFilters:
    def test_low_shelf_boost(self):
        filt = design_low_shelf(200, 6.0)
        freqs = np.logspace(1, 4.3, 500)
        response = filt.magnitude_response(freqs)
        # Below corner: boosted; above corner: flat
        assert response[0] > 4.0  # significant boost at 10 Hz
        assert abs(response[-1]) < 1.0  # nearly flat at 20 kHz

    def test_high_shelf_cut(self):
        filt = design_high_shelf(5000, -6.0)
        freqs = np.logspace(1, 4.3, 500)
        response = filt.magnitude_response(freqs)
        # Above corner: cut; below corner: flat
        assert response[-1] < -4.0  # cut at 20 kHz
        assert abs(response[0]) < 1.0  # nearly flat at 10 Hz


class TestCombinedResponse:
    def test_additive(self):
        f1 = design_peaking(500, -3.0, 2.0)
        f2 = design_peaking(2000, -3.0, 2.0)
        freqs = np.logspace(1, 4.3, 500)
        combined = combined_response([f1, f2], freqs)
        individual = f1.magnitude_response(freqs) + f2.magnitude_response(freqs)
        assert np.allclose(combined, individual, atol=0.01)
