"""Connection test endpoints — verify RPi, CamillaDSP, and MPD connectivity."""

from __future__ import annotations

import logging

from fastapi import APIRouter
from pydantic import BaseModel

from backend.integration.rpi import RPiConfig, RPiConnection
from backend.integration.camilla import CamillaDSPClient
from backend.integration.moode import MPDClient

logger = logging.getLogger("roomtune.api.connection")

router = APIRouter(prefix="/api/connection", tags=["connection"])


class ConnectionTestRequest(BaseModel):
    host: str = "moode.local"
    port: int = 22
    username: str = "pi"
    password: str = ""
    key_path: str | None = None


class ServiceStatus(BaseModel):
    connected: bool
    hostname: str | None = None
    state: str | None = None
    version: str | None = None
    error: str | None = None


class ConnectionTestResponse(BaseModel):
    rpi: ServiceStatus
    camilladsp: ServiceStatus
    mpd: ServiceStatus


@router.post("/test", response_model=ConnectionTestResponse)
async def test_connection(req: ConnectionTestRequest):
    """Test connectivity to RPi (SSH), CamillaDSP (WebSocket), and MPD."""

    # --- RPi SSH ---
    rpi_status = ServiceStatus(connected=False)
    rpi_conn = RPiConnection(
        RPiConfig(
            host=req.host,
            port=req.port,
            username=req.username,
            password=req.password if req.password else None,
            key_path=req.key_path,
        )
    )
    try:
        result = rpi_conn.test_connection()
        rpi_status.connected = result.get("connected", False)
        rpi_status.hostname = result.get("hostname")
        if not rpi_status.connected:
            rpi_status.error = result.get("error")
    except Exception as e:
        rpi_status.error = str(e)

    # --- CamillaDSP ---
    cdsp_status = ServiceStatus(connected=False)
    try:
        client = CamillaDSPClient(host=req.host)
        result = client.test_connection()
        cdsp_status.connected = result.get("connected", False)
        cdsp_status.state = result.get("state")
        if not cdsp_status.connected:
            cdsp_status.error = result.get("error")
    except Exception as e:
        cdsp_status.error = str(e)

    # --- MPD ---
    mpd_status = ServiceStatus(connected=False)
    try:
        mpd = MPDClient(host=req.host)
        result = mpd.test_connection()
        mpd_status.connected = result.get("connected", False)
        mpd_status.version = result.get("version")
        if not mpd_status.connected:
            mpd_status.error = result.get("error")
    except Exception as e:
        mpd_status.error = str(e)

    return ConnectionTestResponse(
        rpi=rpi_status,
        camilladsp=cdsp_status,
        mpd=mpd_status,
    )
