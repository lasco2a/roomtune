"""Measurement endpoints — start/stop recording, get sweep WAV."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger("roomtune.api.measurement")

router = APIRouter(prefix="/api/measurement", tags=["measurement"])


class StartMeasurementRequest(BaseModel):
    device_index: int
    channel: str = "left"
    position_id: int = 1
    duration: float | None = None  # unused for streaming; reserved for future blocking mode


class MeasurementStatusResponse(BaseModel):
    status: str
    position_id: int | None = None
    channel: str | None = None
    peak_db: float | None = None
    clipped: bool | None = None
    duration: float | None = None


@router.post("/start", response_model=MeasurementStatusResponse)
async def start_measurement(req: StartMeasurementRequest):
    """Start a streaming measurement at the given position/channel.

    The orchestrator must be configured before calling this (via the setup step).
    """
    from backend.main import get_orchestrator

    orch = get_orchestrator()

    if orch.session.measuring:
        raise HTTPException(400, "Measurement already in progress")

    # Auto-configure if not yet done
    if orch._recorder is None:
        from backend.main import get_state

        st = get_state()
        from pathlib import Path

        cal_path = Path(__file__).resolve().parent.parent.parent / "Umik" / "7055332_90deg.txt"
        cal = st.calibration_loader.load(cal_path) if cal_path.exists() else None
        orch.configure(device_index=req.device_index, calibration=cal)

    try:
        orch.start_measurement(req.position_id, req.channel)
    except Exception as e:
        raise HTTPException(500, str(e))

    return MeasurementStatusResponse(
        status="recording",
        position_id=req.position_id,
        channel=req.channel,
    )


@router.post("/stop", response_model=MeasurementStatusResponse)
async def stop_measurement():
    """Stop the current measurement and return results."""
    from backend.main import get_orchestrator

    orch = get_orchestrator()

    if not orch.session.measuring:
        raise HTTPException(400, "No measurement in progress")

    try:
        result = orch.stop_measurement()
    except Exception as e:
        raise HTTPException(500, str(e))

    return MeasurementStatusResponse(
        status="complete",
        position_id=result.position_id,
        channel=result.channel,
        peak_db=result.recording.peak_db,
        clipped=result.recording.clipped,
        duration=result.recording.duration,
    )


@router.get("/status")
async def measurement_status():
    """Get current measurement state (for polling)."""
    from backend.main import get_orchestrator

    orch = get_orchestrator()
    return {
        "measuring": orch.session.measuring,
        "position_id": orch.session.current_position if orch.session.measuring else None,
        "channel": orch.session.current_channel if orch.session.measuring else None,
        "level_rms_db": orch.session.level_rms_db,
        "level_peak_db": orch.session.level_peak_db,
        "level_clipped": orch.session.level_clipped,
        "completed_count": len(orch.session.results),
    }


@router.post("/reset")
async def reset_measurement():
    """Reset the measurement session."""
    from backend.main import get_orchestrator

    get_orchestrator().reset()
    return {"status": "reset"}
