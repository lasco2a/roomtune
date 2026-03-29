"""Analysis endpoints — frequency response, RT60, room modes."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query

from backend.analysis.room import compute_room_modes, compute_rt60
from backend.analysis.smoothing import octave_smooth

logger = logging.getLogger("roomtune.api.analysis")

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


@router.get("")
async def get_analysis(smoothing: float = Query(6.0, description="Octave fraction (3, 6, 12, 24)")):
    """Return the averaged frequency response across all measurements."""
    from backend.main import get_orchestrator

    orch = get_orchestrator()

    if not orch.session.results:
        raise HTTPException(404, "No measurements available — run a measurement first")

    fr = orch.session.averaged_frequency_response
    if fr is None:
        raise HTTPException(500, "Failed to compute averaged frequency response")

    # Re-smooth if the caller requests a different smoothing level
    if smoothing != 6.0:
        # Get raw averaged (un-smoothed) from individual raw FRs
        # For simplicity, just re-smooth the already smoothed one
        fr = octave_smooth(fr, fraction=smoothing)

    return fr.to_dict()


@router.get("/positions")
async def get_position_results():
    """Return individual frequency responses per position."""
    from backend.main import get_orchestrator

    orch = get_orchestrator()
    results = []
    for r in orch.session.results:
        results.append(
            {
                "position_id": r.position_id,
                "channel": r.channel,
                "peak_db": r.recording.peak_db,
                "frequency_response": r.frequency_response_smoothed.to_dict(),
            }
        )
    return {"positions": results}


@router.get("/rt60")
async def get_rt60():
    """Compute RT60 from the most recent impulse response."""
    from backend.main import get_orchestrator

    orch = get_orchestrator()

    if not orch.session.results:
        raise HTTPException(404, "No measurements available")

    # Use the primary seat (position 1) if available, else the first result
    ir_result = None
    for r in orch.session.results:
        if r.position_id == 1:
            ir_result = r
            break
    if ir_result is None:
        ir_result = orch.session.results[0]

    rt60 = compute_rt60(ir_result.impulse_response)

    return {
        "rt60": round(rt60.rt60, 3),
        "edt": round(rt60.edt, 3),
        "t20": round(rt60.t20, 3),
        "t30": round(rt60.t30, 3),
        "confidence": round(rt60.confidence, 4),
    }


@router.get("/modes")
async def get_room_modes(
    length: float = Query(..., description="Room length in metres"),
    width: float = Query(..., description="Room width in metres"),
    height: float = Query(..., description="Room height in metres"),
    max_freq: float = Query(300.0, description="Max frequency to compute"),
):
    """Compute room resonance modes from dimensions."""
    modes = compute_room_modes(length, width, height, max_freq=max_freq)
    return [
        {
            "frequency": round(m.frequency, 1),
            "mode_type": m.mode_type,
            "indices": list(m.indices),
        }
        for m in modes
    ]
