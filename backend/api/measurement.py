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
    mode: str = "auto"  # "auto" = full automated flow, "manual" = record only


class MeasurementStatusResponse(BaseModel):
    status: str
    position_id: int | None = None
    channel: str | None = None
    peak_db: float | None = None
    clipped: bool | None = None
    duration: float | None = None
    detail: str | None = None


@router.post("/start", response_model=MeasurementStatusResponse)
async def start_measurement(req: StartMeasurementRequest):
    """Start a measurement at the given position/channel.

    mode="auto" (default): Full automated flow — uploads sweep to RPi,
    starts UMIK-1 recording, triggers MPD playback, waits for completion,
    and processes the result. Runs in background; poll /status for progress.

    mode="manual": Starts recording only. Call /stop to stop and process.
    """
    from backend.main import get_orchestrator, get_state

    orch = get_orchestrator()
    st = get_state()

    if orch.session.measuring:
        raise HTTPException(400, "Measurement already in progress")

    # Auto-configure if not yet done
    if orch._recorder is None:
        from pathlib import Path

        cal_path = Path(__file__).resolve().parent.parent.parent / "Umik" / "7055332_90deg.txt"
        cal = st.calibration_loader.load(cal_path) if cal_path.exists() else None
        orch.configure(device_index=req.device_index, calibration=cal)

    # Configure RPi connection from app state
    rpi_cfg = st.rpi_config
    orch.configure_rpi(
        host=rpi_cfg.get("host", "moode.local"),
        port=rpi_cfg.get("port", 22),
        username=rpi_cfg.get("username", "pi"),
        password=rpi_cfg.get("password"),
        key_path=rpi_cfg.get("key_path"),
    )

    try:
        if req.mode == "auto":
            # Full automated flow (runs in background thread)
            orch.run_measurement(req.position_id, req.channel)
            return MeasurementStatusResponse(
                status="running",
                position_id=req.position_id,
                channel=req.channel,
                detail="Automated measurement started — uploading sweep, recording, playing...",
            )
        else:
            # Manual mode: start recording only
            orch.start_measurement(req.position_id, req.channel)
            return MeasurementStatusResponse(
                status="recording",
                position_id=req.position_id,
                channel=req.channel,
                detail="Manual recording started — call /stop when done",
            )
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/stop", response_model=MeasurementStatusResponse)
async def stop_measurement():
    """Stop a manual measurement and return results.

    Only needed for mode="manual". For mode="auto", the measurement
    stops automatically after the sweep completes.
    """
    from backend.main import get_orchestrator

    orch = get_orchestrator()

    if not orch.session.measuring:
        # If not currently measuring, check if the last auto measurement completed
        if orch.session.status == "complete" and orch.session.results:
            last = orch.session.results[-1]
            return MeasurementStatusResponse(
                status="complete",
                position_id=last.position_id,
                channel=last.channel,
                peak_db=last.recording.peak_db,
                clipped=last.recording.clipped,
                duration=last.recording.duration,
                detail=orch.session.status_detail,
            )
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
    """Get current measurement state (for polling).

    Returns the orchestrator status including progress for automated
    measurements.
    """
    from backend.main import get_orchestrator

    orch = get_orchestrator()
    return {
        "measuring": orch.session.measuring,
        "status": orch.session.status,
        "detail": orch.session.status_detail,
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
