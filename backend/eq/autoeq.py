"""Auto-EQ optimisation engine.

Given a measured room frequency response and a target curve, automatically
designs a set of parametric EQ filters (biquads) that bring the measured
response as close to the target as possible.

**Key principle**: subtractive EQ only — cut peaks, do NOT boost nulls.
Nulls are acoustic cancellations that cannot be corrected with EQ.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import minimize

from backend.analysis.frequency import FrequencyResponse
from backend.eq.filters import (
    BiquadFilter,
    FilterType,
    combined_response,
    design_high_shelf,
    design_low_shelf,
    design_peaking,
)
from backend.eq.targets import TargetCurve

logger = logging.getLogger("roomtune.autoeq")


@dataclass
class AutoEQResult:
    """Result of the auto-EQ optimisation."""

    filters: list[BiquadFilter] = field(default_factory=list)
    target_name: str = ""
    error_before_db: float = 0.0  # RMS error before EQ
    error_after_db: float = 0.0  # RMS error after EQ
    improvement_db: float = 0.0  # error reduction

    def to_dict(self) -> dict:
        return {
            "filters": [f.to_dict() for f in self.filters],
            "target_name": self.target_name,
            "error_before_db": round(self.error_before_db, 2),
            "error_after_db": round(self.error_after_db, 2),
            "improvement_db": round(self.improvement_db, 2),
            "num_filters": len(self.filters),
        }


def auto_eq(
    measured: FrequencyResponse,
    target: TargetCurve,
    max_filters: int = 10,
    max_gain_db: float = -12.0,
    min_q: float = 0.5,
    max_q: float = 10.0,
    f_low: float = 20.0,
    f_high: float = 20000.0,
    sample_rate: int = 48000,
    allow_shelves: bool = True,
) -> AutoEQResult:
    """Run the auto-EQ optimisation.

    Parameters
    ----------
    measured : FrequencyResponse
        The measured room frequency response (should be smoothed).
    target : TargetCurve
        Desired target curve.
    max_filters : int
        Maximum number of EQ filters to use (default 10).
    max_gain_db : float
        Maximum cut in dB (negative, default -12).
    min_q, max_q : float
        Q factor bounds for peaking filters.
    f_low, f_high : float
        Frequency range to optimise over.
    sample_rate : int
        Sample rate for filter design.
    allow_shelves : bool
        Whether to include low/high shelf filters in the optimisation.

    Returns
    -------
    AutoEQResult
    """
    # Restrict to optimisation frequency range
    fr = measured.in_range(f_low, f_high)
    freqs = fr.frequencies
    measured_db = fr.magnitude_db

    # Interpolate target to the same frequencies
    target_db = target.at_frequencies(freqs)

    # Error = measured - target (positive = peak that needs cutting)
    error = measured_db - target_db
    error_before = float(np.sqrt(np.mean(error**2)))

    logger.info(
        "Auto-EQ: %d freq points, %.0f–%.0f Hz, target=%s, max_filters=%d, error_before=%.1f dB",
        len(freqs),
        f_low,
        f_high,
        target.name,
        max_filters,
        error_before,
    )

    # --- Iterative peak-picking approach ---
    # 1. Find the largest positive error (peak above target)
    # 2. Design a peaking filter to cut it
    # 3. Apply the filter to the error curve
    # 4. Repeat up to max_filters times

    filters: list[BiquadFilter] = []
    residual = error.copy()

    for i in range(max_filters):
        # Only consider positive residual (peaks above target)
        positive_residual = np.maximum(residual, 0)

        if np.max(positive_residual) < 0.5:
            logger.info("Residual below 0.5 dB, stopping at %d filters", i)
            break

        # Find the frequency of the largest peak
        peak_idx = int(np.argmax(positive_residual))
        peak_freq = float(freqs[peak_idx])
        peak_error = float(residual[peak_idx])

        if peak_error <= 0:
            break

        # Determine initial filter parameters
        gain_db = max(-peak_error, max_gain_db)  # subtractive only, capped

        # Estimate Q from the width of the peak
        q = _estimate_q(residual, freqs, peak_idx)
        q = np.clip(q, min_q, max_q)

        # Optimise this single filter
        best_filter = _optimise_single_filter(
            residual=residual,
            freqs=freqs,
            init_freq=peak_freq,
            init_gain=gain_db,
            init_q=q,
            max_gain_db=max_gain_db,
            min_q=min_q,
            max_q=max_q,
            sample_rate=sample_rate,
        )

        filters.append(best_filter)

        # Update residual
        filter_response = best_filter.magnitude_response(freqs, sample_rate)
        residual = residual + filter_response  # filter_response is negative (cut)

        logger.info(
            "Filter %d: %s @ %.0f Hz, gain=%.1f dB, Q=%.2f",
            i + 1,
            best_filter.filter_type.value,
            best_filter.frequency,
            best_filter.gain_db,
            best_filter.q,
        )

    # Compute final error
    total_eq = combined_response(filters, freqs, sample_rate)
    corrected = measured_db + total_eq
    final_error = corrected - target_db
    error_after = float(np.sqrt(np.mean(final_error**2)))

    result = AutoEQResult(
        filters=filters,
        target_name=target.name,
        error_before_db=error_before,
        error_after_db=error_after,
        improvement_db=error_before - error_after,
    )

    logger.info(
        "Auto-EQ complete: %d filters, error %.1f → %.1f dB (improved %.1f dB)",
        len(filters),
        error_before,
        error_after,
        result.improvement_db,
    )
    return result


def _estimate_q(residual: np.ndarray, freqs: np.ndarray, peak_idx: int) -> float:
    """Estimate Q factor from the -3 dB width of a peak in the residual."""
    peak_val = residual[peak_idx]
    half_val = peak_val / 2.0  # -3 dB point (approximately)

    # Search left
    left_idx = peak_idx
    for j in range(peak_idx - 1, -1, -1):
        if residual[j] < half_val:
            left_idx = j
            break

    # Search right
    right_idx = peak_idx
    for j in range(peak_idx + 1, len(residual)):
        if residual[j] < half_val:
            right_idx = j
            break

    if left_idx == right_idx or left_idx >= right_idx:
        return 2.0  # default Q

    f_low = freqs[left_idx]
    f_high = freqs[right_idx]
    f_center = freqs[peak_idx]

    if f_high <= f_low or f_center <= 0:
        return 2.0

    bandwidth_octaves = np.log2(f_high / f_low)
    if bandwidth_octaves <= 0:
        return 2.0

    # Q ≈ f_center / bandwidth (for peaking EQ)
    q = f_center / (f_high - f_low)
    return float(q)


def _optimise_single_filter(
    residual: np.ndarray,
    freqs: np.ndarray,
    init_freq: float,
    init_gain: float,
    init_q: float,
    max_gain_db: float,
    min_q: float,
    max_q: float,
    sample_rate: int,
) -> BiquadFilter:
    """Optimise a single peaking filter to minimise the positive residual."""

    def cost(params: np.ndarray) -> float:
        freq, gain, q = params
        filt = design_peaking(freq, gain, q, sample_rate)
        response = filt.magnitude_response(freqs, sample_rate)
        new_residual = residual + response
        # Penalise positive residual (peaks) more than negative (dips)
        positive = np.maximum(new_residual, 0)
        negative = np.maximum(-new_residual, 0)
        return float(np.sum(positive**2) + 0.1 * np.sum(negative**2))

    x0 = np.array([init_freq, init_gain, init_q])
    bounds = [
        (max(20, init_freq * 0.5), min(20000, init_freq * 2.0)),  # freq
        (max_gain_db, -0.1),  # gain (cuts only)
        (min_q, max_q),  # Q
    ]

    result = minimize(cost, x0, method="L-BFGS-B", bounds=bounds)

    opt_freq, opt_gain, opt_q = result.x
    return design_peaking(float(opt_freq), float(opt_gain), float(opt_q), sample_rate)
