"""Test UMIK-1 calibration file parser."""

from pathlib import Path

import numpy as np
import pytest

from backend.audio.calibration import CalibrationLoader


# Path to the actual UMIK calibration files in the project
UMIK_DIR = Path(__file__).resolve().parent.parent.parent / "Umik"
CAL_0DEG = UMIK_DIR / "7055332.txt"
CAL_90DEG = UMIK_DIR / "7055332_90deg.txt"


@pytest.fixture
def loader():
    return CalibrationLoader()


class TestCalibrationLoader:
    def test_load_0deg(self, loader):
        if not CAL_0DEG.exists():
            pytest.skip("Calibration file not found")
        cal = loader.load(CAL_0DEG)
        assert cal.serial == "7055332"
        assert abs(cal.sensitivity_db - 1.516) < 0.01
        assert not cal.is_90deg
        assert cal.num_points > 600
        assert cal.freq_min < 15
        assert cal.freq_max > 19000

    def test_load_90deg(self, loader):
        if not CAL_90DEG.exists():
            pytest.skip("Calibration file not found")
        cal = loader.load(CAL_90DEG)
        assert cal.serial == "7055332"
        assert cal.is_90deg
        assert cal.num_points > 600

    def test_correction_at_interpolates(self, loader):
        if not CAL_0DEG.exists():
            pytest.skip("Calibration file not found")
        cal = loader.load(CAL_0DEG)
        # Check single frequency
        correction = cal.correction_at(1000.0)
        assert isinstance(correction, np.ndarray)
        assert len(correction) == 1

        # Check array of frequencies
        freqs = np.array([100.0, 500.0, 1000.0, 5000.0, 10000.0])
        corrections = cal.correction_at(freqs)
        assert len(corrections) == 5

    def test_caching(self, loader):
        if not CAL_0DEG.exists():
            pytest.skip("Calibration file not found")
        cal1 = loader.load(CAL_0DEG)
        cal2 = loader.load(CAL_0DEG)
        assert cal1 is cal2  # Same object from cache

    def test_file_not_found(self, loader):
        with pytest.raises(FileNotFoundError):
            loader.load("/nonexistent/path.txt")
