"""EQ endpoints — target curves, auto-EQ computation, apply to CamillaDSP."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.eq.targets import TargetPreset, get_target
from backend.eq.autoeq import auto_eq

logger = logging.getLogger("roomtune.api.eq")

router = APIRouter(prefix="/api/eq", tags=["eq"])


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class AutoEQRequest(BaseModel):
    target: str = "harman"
    max_filters: int = 10
    max_gain_db: float = -12.0


class ApplyResponse(BaseModel):
    status: str
    detail: str | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/targets")
async def list_targets():
    """Return all available target curve presets."""
    targets = []
    for preset in TargetPreset:
        t = get_target(preset)
        targets.append(t.to_dict())
    return targets


@router.post("/auto")
async def run_auto_eq(req: AutoEQRequest):
    """Run the auto-EQ optimisation on the current measurements."""
    from backend.main import get_orchestrator, get_state

    orch = get_orchestrator()

    if not orch.session.results:
        raise HTTPException(404, "No measurements available — run a measurement first")

    # Get averaged frequency response
    fr = orch.session.averaged_frequency_response
    if fr is None:
        raise HTTPException(500, "Failed to compute averaged frequency response")

    # Get target curve
    try:
        target = get_target(req.target)
    except ValueError:
        raise HTTPException(400, f"Unknown target preset: {req.target}")

    # Run auto-EQ
    result = auto_eq(
        measured=fr,
        target=target,
        max_filters=req.max_filters,
        max_gain_db=req.max_gain_db,
    )

    # Store result on state for later apply
    st = get_state()
    st.last_eq_result = result

    return result.to_dict()


@router.post("/apply", response_model=ApplyResponse)
async def apply_to_camilladsp():
    """Apply the last computed EQ to CamillaDSP via WebSocket."""
    from backend.main import get_state

    st = get_state()

    if not hasattr(st, "last_eq_result") or st.last_eq_result is None:
        raise HTTPException(400, "No EQ result to apply — run /api/eq/auto first")

    from backend.integration.camilla import CamillaDSPConfig, CamillaDSPClient

    # Build CamillaDSP config from filters
    config = CamillaDSPConfig(
        sample_rate=48000,
        channels=2,
        filters={
            "left": st.last_eq_result.filters,
            "right": st.last_eq_result.filters,  # same EQ for both channels for now
        },
    )

    # Connect and apply
    try:
        client = CamillaDSPClient(host=st.rpi_host)
        client.connect()
        try:
            client.apply_eq(config)
        finally:
            client.disconnect()
    except Exception as e:
        logger.error("Failed to apply EQ to CamillaDSP: %s", e)
        raise HTTPException(502, f"CamillaDSP error: {e}")

    return ApplyResponse(
        status="applied", detail=f"Applied {len(st.last_eq_result.filters)} filters"
    )
