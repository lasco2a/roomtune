"""Moode Audio / MPD integration for test signal playback.

Controls music playback on the Raspberry Pi via MPD (Music Player Daemon),
which is the audio engine behind Moode Audio.  Used to play sweep WAV files
through the signal chain (RPi → CamillaDSP → DAC → Amp → Speakers).
"""

from __future__ import annotations

import logging
import socket

logger = logging.getLogger("roomtune.moode")

# MPD default port
MPD_PORT = 6600


class MPDClient:
    """Minimal MPD client for controlling playback on Moode Audio.

    Only implements the subset of MPD commands needed for RoomTune:
    adding a file to the queue, playing, stopping, and checking status.
    """

    def __init__(self, host: str = "10.1.1.85", port: int = MPD_PORT) -> None:
        self.host = host
        self.port = port
        self._sock: socket.socket | None = None
        self._buf: str = ""  # line buffer for incremental reads

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def connect(self, timeout: float = 5.0) -> str:
        """Connect to MPD and return the version banner."""
        self._sock = socket.create_connection((self.host, self.port), timeout=timeout)
        self._buf = ""
        banner = self._readline()
        if not banner.startswith("OK MPD"):
            raise RuntimeError(f"Unexpected MPD banner: {banner}")
        logger.info("Connected to MPD at %s:%d (%s)", self.host, self.port, banner.strip())
        return banner.strip()

    def disconnect(self) -> None:
        if self._sock:
            try:
                self._send("close")
            except Exception:
                pass
            self._sock.close()
            self._sock = None

    @property
    def is_connected(self) -> bool:
        return self._sock is not None

    # ------------------------------------------------------------------
    # MPD commands
    # ------------------------------------------------------------------

    def status(self) -> dict:
        """Get MPD status."""
        return self._command_dict("status")

    def clear(self) -> None:
        """Clear the current playlist."""
        self._command("clear")

    def add(self, uri: str) -> None:
        """Add a URI to the playlist (e.g., a local file path on the RPi)."""
        self._command(f"add {uri}")

    def play(self, pos: int = 0) -> None:
        """Start playback at the given playlist position."""
        self._command(f"play {pos}")

    def stop(self) -> None:
        """Stop playback."""
        self._command("stop")

    def set_volume(self, volume: int) -> None:
        """Set playback volume (0-100)."""
        self._command(f"setvol {volume}")

    def update(self, path: str = "") -> None:
        """Trigger MPD database update (e.g., after uploading a new file)."""
        cmd = f"update {path}" if path else "update"
        self._command(cmd)

    # ------------------------------------------------------------------
    # High-level helpers
    # ------------------------------------------------------------------

    def play_file(self, uri: str, volume: int = 80) -> None:
        """Clear queue, add file, set volume, and play."""
        self.clear()
        self.add(uri)
        self.set_volume(volume)
        self.play()
        logger.info("Playing %s at volume %d", uri, volume)

    def test_connection(self) -> dict:
        """Test MPD connection and return status."""
        try:
            version = self.connect()
            st = self.status()
            return {"connected": True, "version": version, "status": st}
        except Exception as e:
            logger.error("MPD connection test failed: %s", e)
            return {"connected": False, "error": str(e)}
        finally:
            self.disconnect()

    # ------------------------------------------------------------------
    # Low-level protocol
    # ------------------------------------------------------------------

    def _send(self, data: str) -> None:
        if not self._sock:
            raise RuntimeError("Not connected to MPD")
        self._sock.sendall((data + "\n").encode("utf-8"))

    def _readline(self) -> str:
        """Read a single line from the socket, buffering any excess data."""
        if not self._sock:
            raise RuntimeError("Not connected to MPD")
        while "\n" not in self._buf:
            chunk = self._sock.recv(4096)
            if not chunk:
                raise ConnectionError("MPD connection closed")
            self._buf += chunk.decode("utf-8", errors="replace")
        line, self._buf = self._buf.split("\n", 1)
        return line + "\n"

    def _read_response(self) -> list[str]:
        """Read lines until OK or ACK."""
        lines: list[str] = []
        while True:
            line = self._readline().strip()
            if line == "OK":
                break
            if line.startswith("ACK"):
                raise RuntimeError(f"MPD error: {line}")
            lines.append(line)
        return lines

    def _command(self, cmd: str) -> list[str]:
        """Send a command and return response lines."""
        self._send(cmd)
        return self._read_response()

    def _command_dict(self, cmd: str) -> dict:
        """Send a command and parse key: value response into a dict."""
        lines = self._command(cmd)
        result: dict = {}
        for line in lines:
            if ": " in line:
                key, value = line.split(": ", 1)
                result[key] = value
        return result
