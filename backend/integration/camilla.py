"""CamillaDSP configuration generation and live control.

Generates CamillaDSP YAML pipeline configurations from computed EQ filters,
and communicates with CamillaDSP's websocket API for live parameter updates.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

import yaml
import websocket

from backend.eq.filters import BiquadFilter

logger = logging.getLogger("roomtune.camilla")

# Default CamillaDSP websocket port
DEFAULT_WS_PORT = 1234


@dataclass
class CamillaDSPConfig:
    """CamillaDSP pipeline configuration."""

    sample_rate: int = 48000
    channels: int = 2
    filters: dict[str, list[BiquadFilter]] = field(default_factory=dict)  # channel -> filters

    def to_yaml(self) -> str:
        """Generate CamillaDSP YAML configuration."""
        config: dict = {
            "devices": {
                "samplerate": self.sample_rate,
                "chunksize": 1024,
                "capture": {
                    "type": "File",
                    "channels": self.channels,
                    "filename": "/dev/stdin",
                    "format": "S32LE",
                },
                "playback": {
                    "type": "File",
                    "channels": self.channels,
                    "filename": "/dev/stdout",
                    "format": "S32LE",
                },
            },
        }

        # Build filters section
        filter_defs: dict = {}
        pipeline_steps: list = []

        for channel_name, channel_filters in self.filters.items():
            channel_idx = 0 if channel_name.lower() in ("left", "l", "0") else 1

            filter_names = []
            for i, filt in enumerate(channel_filters):
                name = f"eq_{channel_name}_{i}"
                filter_defs[name] = filt.to_camilladsp()
                filter_names.append(name)

            if filter_names:
                pipeline_steps.append(
                    {
                        "type": "Filter",
                        "channel": channel_idx,
                        "names": filter_names,
                    }
                )

        if filter_defs:
            config["filters"] = filter_defs
        if pipeline_steps:
            config["pipeline"] = pipeline_steps

        return yaml.dump(config, default_flow_style=False, sort_keys=False)

    def to_dict(self) -> dict:
        return {
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "filters": {ch: [f.to_dict() for f in flist] for ch, flist in self.filters.items()},
        }


class CamillaDSPClient:
    """WebSocket client for CamillaDSP's control API."""

    def __init__(self, host: str = "moode.local", port: int = DEFAULT_WS_PORT) -> None:
        self.host = host
        self.port = port
        self._ws: websocket.WebSocket | None = None

    @property
    def url(self) -> str:
        return f"ws://{self.host}:{self.port}"

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def connect(self, timeout: float = 5.0) -> None:
        """Connect to the CamillaDSP websocket."""
        logger.info("Connecting to CamillaDSP at %s …", self.url)
        self._ws = websocket.create_connection(self.url, timeout=timeout)
        logger.info("Connected to CamillaDSP")

    def disconnect(self) -> None:
        if self._ws:
            self._ws.close()
            self._ws = None

    @property
    def is_connected(self) -> bool:
        return self._ws is not None and self._ws.connected

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    def _send(self, command: str, data: dict | None = None) -> dict:
        """Send a command and return the response."""
        if not self.is_connected:
            raise RuntimeError("Not connected to CamillaDSP")

        msg = {"command": command}
        if data is not None:
            msg["data"] = data

        self._ws.send(json.dumps(msg))
        response = json.loads(self._ws.recv())

        if response.get("result") == "Error":
            raise RuntimeError(f"CamillaDSP error: {response.get('value', 'unknown')}")

        return response

    def get_state(self) -> str:
        """Get the current CamillaDSP state (Running, Paused, etc.)."""
        resp = self._send("GetState")
        return resp.get("value", "Unknown")

    def get_signal_range(self) -> float:
        """Get the current signal peak level (dBFS)."""
        resp = self._send("GetSignalRange")
        return float(resp.get("value", -120))

    def get_config(self) -> str:
        """Get the current active configuration as YAML."""
        resp = self._send("GetConfig")
        return resp.get("value", "")

    def set_config(self, yaml_config: str) -> None:
        """Upload and apply a new configuration."""
        logger.info("Uploading new config to CamillaDSP (%d bytes)", len(yaml_config))
        self._send("SetConfig", {"value": yaml_config})

    def reload(self) -> None:
        """Reload the current configuration."""
        self._send("Reload")

    def get_capture_signal_peak(self) -> list[float]:
        """Get peak levels for all capture channels."""
        resp = self._send("GetCaptureSignalPeak")
        return resp.get("value", [])

    def get_playback_signal_peak(self) -> list[float]:
        """Get peak levels for all playback channels."""
        resp = self._send("GetPlaybackSignalPeak")
        return resp.get("value", [])

    # ------------------------------------------------------------------
    # High-level helpers
    # ------------------------------------------------------------------

    def apply_eq(self, config: CamillaDSPConfig) -> None:
        """Generate config YAML and apply it to CamillaDSP."""
        yaml_str = config.to_yaml()
        self.set_config(yaml_str)
        logger.info("EQ configuration applied to CamillaDSP")

    def test_connection(self) -> dict:
        """Test connection and return state info."""
        try:
            self.connect()
            state = self.get_state()
            return {"connected": True, "state": state, "url": self.url}
        except Exception as e:
            logger.error("CamillaDSP connection test failed: %s", e)
            return {"connected": False, "error": str(e), "url": self.url}
        finally:
            self.disconnect()
