"""RoomTune - FastAPI application and WebSocket server."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.audio.devices import AudioDeviceManager
from backend.audio.calibration import CalibrationLoader

logger = logging.getLogger("roomtune")

# ---------------------------------------------------------------------------
# Application state (shared across requests)
# ---------------------------------------------------------------------------


class AppState:
    """Mutable application-wide state initialised at startup."""

    def __init__(self) -> None:
        self.device_manager = AudioDeviceManager()
        self.calibration_loader = CalibrationLoader()
        self.connected_ws: list[WebSocket] = []


state = AppState()

# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown hooks."""
    logger.info("RoomTune backend starting …")
    state.device_manager.refresh()
    yield
    logger.info("RoomTune backend shutting down …")


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="RoomTune",
    version="0.1.0",
    description="Automated room acoustic measurement & auto-EQ for CamillaDSP",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}


@app.get("/api/devices")
async def list_devices():
    """Return detected audio input devices."""
    state.device_manager.refresh()
    return {
        "devices": state.device_manager.list_input_devices(),
        "umik": state.device_manager.find_umik(),
    }


@app.get("/api/calibration")
async def get_calibration(path: str | None = None):
    """Load and return calibration data from a .txt cal file."""
    if path is None:
        # Default: look for 90-degree cal file in Umik directory
        default_path = Path(__file__).resolve().parent.parent / "Umik" / "7055332_90deg.txt"
        path = str(default_path)
    cal = state.calibration_loader.load(path)
    return cal.to_dict()


# ---------------------------------------------------------------------------
# WebSocket – real-time updates (level meter, measurement progress, etc.)
# ---------------------------------------------------------------------------


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    state.connected_ws.append(ws)
    logger.info("WebSocket client connected (%d total)", len(state.connected_ws))
    try:
        while True:
            data = await ws.receive_json()
            # Handle incoming commands from the frontend
            cmd = data.get("cmd")
            if cmd == "ping":
                await ws.send_json({"event": "pong"})
            else:
                await ws.send_json({"event": "error", "detail": f"unknown cmd: {cmd}"})
    except WebSocketDisconnect:
        state.connected_ws.remove(ws)
        logger.info("WebSocket client disconnected (%d remaining)", len(state.connected_ws))


async def broadcast(event: dict) -> None:
    """Send an event to every connected WebSocket client."""
    for ws in list(state.connected_ws):
        try:
            await ws.send_json(event)
        except Exception:
            state.connected_ws.remove(ws)


# ---------------------------------------------------------------------------
# Entry-point helper
# ---------------------------------------------------------------------------


def start():
    """CLI entry-point (roomtune command)."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    start()
