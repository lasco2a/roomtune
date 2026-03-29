"""Audio device detection and UMIK-1 identification.

Uses the ``sounddevice`` library to enumerate host audio devices and identify
a connected miniDSP UMIK-1 microphone by name pattern matching.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import sounddevice as sd

logger = logging.getLogger("roomtune.devices")

# Known name fragments that identify a UMIK-1 across platforms
_UMIK_PATTERNS = ("umik", "minidsp")


@dataclass
class AudioDevice:
    """Simplified representation of an audio input device."""

    index: int
    name: str
    channels: int
    default_samplerate: float
    hostapi: str
    is_umik: bool = False

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "name": self.name,
            "channels": self.channels,
            "default_samplerate": self.default_samplerate,
            "hostapi": self.hostapi,
            "is_umik": self.is_umik,
        }


class AudioDeviceManager:
    """Detect and manage audio input devices."""

    def __init__(self) -> None:
        self._devices: list[AudioDevice] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        """Re-scan the system for audio input devices."""
        self._devices.clear()
        try:
            hostapis = sd.query_hostapis()
            raw_devices = sd.query_devices()
        except Exception:
            logger.exception("Failed to query audio devices")
            return

        for idx, dev in enumerate(raw_devices):
            if dev["max_input_channels"] < 1:
                continue  # skip output-only devices

            hostapi_name = (
                hostapis[dev["hostapi"]]["name"] if dev["hostapi"] < len(hostapis) else ""
            )
            name_lower = dev["name"].lower()
            is_umik = any(pat in name_lower for pat in _UMIK_PATTERNS)

            self._devices.append(
                AudioDevice(
                    index=idx,
                    name=dev["name"],
                    channels=dev["max_input_channels"],
                    default_samplerate=dev["default_samplerate"],
                    hostapi=hostapi_name,
                    is_umik=is_umik,
                )
            )

        logger.info(
            "Found %d input device(s), UMIK detected: %s",
            len(self._devices),
            any(d.is_umik for d in self._devices),
        )

    def list_input_devices(self) -> list[dict]:
        """Return all input devices as dicts."""
        return [d.to_dict() for d in self._devices]

    def find_umik(self) -> dict | None:
        """Return the first UMIK-1 device found, or ``None``."""
        for d in self._devices:
            if d.is_umik:
                return d.to_dict()
        return None

    def get_device(self, index: int) -> AudioDevice | None:
        """Look up a device by its sounddevice index."""
        for d in self._devices:
            if d.index == index:
                return d
        return None

    @property
    def umik_index(self) -> int | None:
        """Shortcut: return the sounddevice index of the UMIK-1, or ``None``."""
        for d in self._devices:
            if d.is_umik:
                return d.index
        return None
