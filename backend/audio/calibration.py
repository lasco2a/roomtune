"""UMIK-1 calibration file parser.

Parses miniDSP UMIK-1 calibration .txt files (both 0-degree and 90-degree
variants). The files contain a sensitivity factor header, optional second
header for 90-degree files, followed by tab-separated ``frequency\\tamplitude``
data lines.

For room measurements the **90-degree** file should be used (mic pointed
straight up at the ceiling).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

logger = logging.getLogger("roomtune.calibration")

_SENS_RE = re.compile(r"Sens Factor\s*=\s*([-+]?\d*\.?\d+)\s*dB", re.IGNORECASE)


@dataclass
class CalibrationData:
    """Parsed calibration data from a UMIK-1 .txt file."""

    path: str
    sensitivity_db: float
    serial: str
    is_90deg: bool
    frequencies: np.ndarray = field(repr=False)
    amplitudes_db: np.ndarray = field(repr=False)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @property
    def num_points(self) -> int:
        return len(self.frequencies)

    @property
    def freq_min(self) -> float:
        return float(self.frequencies[0]) if self.num_points else 0.0

    @property
    def freq_max(self) -> float:
        return float(self.frequencies[-1]) if self.num_points else 0.0

    def correction_at(self, freq: float | np.ndarray) -> np.ndarray:
        """Interpolate calibration correction (dB) at arbitrary frequency(ies).

        Uses linear interpolation in the log-frequency domain so that the
        correction curve is smooth on a log-frequency plot.  Frequencies
        outside the calibration range are clamped to the nearest endpoint.
        """
        log_freqs = np.log10(self.frequencies)
        log_query = np.log10(np.atleast_1d(np.asarray(freq, dtype=float)))
        return np.interp(log_query, log_freqs, self.amplitudes_db)

    def to_dict(self) -> dict:
        """Serialisable dict for JSON responses."""
        return {
            "path": self.path,
            "sensitivity_db": self.sensitivity_db,
            "serial": self.serial,
            "is_90deg": self.is_90deg,
            "num_points": self.num_points,
            "freq_min": self.freq_min,
            "freq_max": self.freq_max,
            "frequencies": self.frequencies.tolist(),
            "amplitudes_db": self.amplitudes_db.tolist(),
        }


class CalibrationLoader:
    """Load and cache UMIK-1 calibration files."""

    def __init__(self) -> None:
        self._cache: dict[str, CalibrationData] = {}

    def load(self, path: str | Path) -> CalibrationData:
        """Parse a calibration file, returning cached result if available."""
        path = Path(path).resolve()
        key = str(path)
        if key in self._cache:
            return self._cache[key]

        if not path.exists():
            raise FileNotFoundError(f"Calibration file not found: {path}")

        text = path.read_text(encoding="utf-8")
        cal = self._parse(text, key)
        self._cache[key] = cal
        logger.info(
            "Loaded calibration %s: %d points, %.1f–%.1f Hz, sens=%.3f dB, 90deg=%s",
            path.name,
            cal.num_points,
            cal.freq_min,
            cal.freq_max,
            cal.sensitivity_db,
            cal.is_90deg,
        )
        return cal

    # ------------------------------------------------------------------
    # Internal parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse(text: str, path_str: str) -> CalibrationData:
        lines = text.strip().splitlines()
        if not lines:
            raise ValueError("Empty calibration file")

        # --- Parse header(s) ---
        sensitivity_db = 0.0
        serial = ""
        is_90deg = False
        data_start = 0

        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue

            # Try to extract sensitivity + serial from first header line
            m = _SENS_RE.search(stripped)
            if m:
                sensitivity_db = float(m.group(1))
                # Serial is usually after "SERNO:" in the same line
                serno_match = re.search(r"SERNO:\s*(\S+)", stripped, re.IGNORECASE)
                if serno_match:
                    serial = serno_match.group(1).strip('"')
                data_start = i + 1
                continue

            # 90-degree auto-generated header
            if "90" in stripped and "auto-generated" in stripped.lower():
                is_90deg = True
                data_start = i + 1
                continue

            # If we hit a line that looks like data, stop scanning headers
            parts = stripped.split()
            try:
                float(parts[0])
                data_start = i
                break
            except (ValueError, IndexError):
                data_start = i + 1
                continue

        # --- Parse data lines ---
        freqs: list[float] = []
        amps: list[float] = []
        for line in lines[data_start:]:
            stripped = line.strip()
            if not stripped:
                continue
            parts = stripped.split()
            if len(parts) < 2:
                continue
            try:
                freqs.append(float(parts[0]))
                amps.append(float(parts[1]))
            except ValueError:
                continue

        if not freqs:
            raise ValueError(f"No calibration data found in {path_str}")

        return CalibrationData(
            path=path_str,
            sensitivity_db=sensitivity_db,
            serial=serial,
            is_90deg=is_90deg,
            frequencies=np.array(freqs, dtype=np.float64),
            amplitudes_db=np.array(amps, dtype=np.float64),
        )
