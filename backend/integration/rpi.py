"""RPi SSH/SCP integration for remote file transfer and command execution.

Uses paramiko for SSH connections to the Raspberry Pi running Moode Audio.
Handles uploading sweep WAV files and downloading/uploading CamillaDSP configs.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import paramiko

logger = logging.getLogger("roomtune.rpi")


@dataclass
class RPiConfig:
    """Configuration for connecting to the Raspberry Pi."""

    host: str = "10.1.1.85"
    port: int = 22
    username: str = "lasco"
    password: str | None = None
    key_path: str | None = None


class RPiConnection:
    """SSH/SCP connection to the Raspberry Pi."""

    def __init__(self, config: RPiConfig) -> None:
        self.config = config
        self._client: paramiko.SSHClient | None = None

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """Establish SSH connection."""
        self._client = paramiko.SSHClient()
        self._client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        kwargs: dict = {
            "hostname": self.config.host,
            "port": self.config.port,
            "username": self.config.username,
        }

        if self.config.key_path:
            kwargs["key_filename"] = self.config.key_path
        elif self.config.password:
            kwargs["password"] = self.config.password

        logger.info("Connecting to RPi at %s:%d …", self.config.host, self.config.port)
        self._client.connect(**kwargs)
        logger.info("Connected to RPi")

    def disconnect(self) -> None:
        if self._client:
            self._client.close()
            self._client = None
            logger.info("Disconnected from RPi")

    @property
    def is_connected(self) -> bool:
        if self._client is None:
            return False
        transport = self._client.get_transport()
        return transport is not None and transport.is_active()

    # ------------------------------------------------------------------
    # Remote execution
    # ------------------------------------------------------------------

    def exec(self, command: str, timeout: float = 30.0) -> tuple[str, str, int]:
        """Execute a command on the RPi.

        Returns
        -------
        tuple[str, str, int]
            (stdout, stderr, exit_code)
        """
        if not self.is_connected:
            raise RuntimeError("Not connected to RPi")

        logger.debug("RPi exec: %s", command)
        _, stdout, stderr = self._client.exec_command(command, timeout=timeout)
        exit_code = stdout.channel.recv_exit_status()
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")

        if exit_code != 0:
            logger.warning("RPi command failed (exit %d): %s\n%s", exit_code, command, err)

        return out, err, exit_code

    # ------------------------------------------------------------------
    # File transfer
    # ------------------------------------------------------------------

    def upload(self, local_path: str | Path, remote_path: str) -> None:
        """Upload a file to the RPi via SFTP.

        Falls back to /tmp + sudo mv if destination is not writable.
        """
        if not self.is_connected:
            raise RuntimeError("Not connected to RPi")

        sftp = self._client.open_sftp()
        try:
            logger.info("Uploading %s → %s", local_path, remote_path)
            try:
                sftp.put(str(local_path), remote_path)
            except (PermissionError, IOError) as exc:
                if isinstance(exc, IOError) and "Permission denied" not in str(exc):
                    raise
                import os

                tmp_path = f"/tmp/roomtune_{os.path.basename(remote_path)}"
                logger.info("Permission denied, uploading via /tmp → sudo mv")
                sftp.put(str(local_path), tmp_path)
                self.exec(f"sudo mv {tmp_path} {remote_path}")
                self.exec(f"sudo chmod 644 {remote_path}")
        finally:
            sftp.close()

    def upload_bytes(self, data: bytes, remote_path: str) -> None:
        """Upload bytes directly to a remote file.

        If the destination directory is not writable by the SSH user,
        the file is uploaded to /tmp first and then moved with sudo.
        """
        if not self.is_connected:
            raise RuntimeError("Not connected to RPi")

        sftp = self._client.open_sftp()
        try:
            logger.info("Uploading %d bytes → %s", len(data), remote_path)
            try:
                with sftp.open(remote_path, "wb") as f:
                    f.write(data)
            except (PermissionError, IOError) as exc:
                # Destination not writable — upload to /tmp then sudo mv
                if isinstance(exc, IOError) and "Permission denied" not in str(exc):
                    raise
                import os

                tmp_path = f"/tmp/roomtune_{os.path.basename(remote_path)}"
                logger.info("Permission denied, uploading via /tmp → sudo mv")
                with sftp.open(tmp_path, "wb") as f:
                    f.write(data)
                self.exec(f"sudo mv {tmp_path} {remote_path}")
                self.exec(f"sudo chmod 644 {remote_path}")
        finally:
            sftp.close()

    def download(self, remote_path: str, local_path: str | Path) -> None:
        """Download a file from the RPi."""
        if not self.is_connected:
            raise RuntimeError("Not connected to RPi")

        sftp = self._client.open_sftp()
        try:
            logger.info("Downloading %s → %s", remote_path, local_path)
            sftp.get(remote_path, str(local_path))
        finally:
            sftp.close()

    def read_remote(self, remote_path: str) -> str:
        """Read a text file from the RPi and return its contents."""
        if not self.is_connected:
            raise RuntimeError("Not connected to RPi")

        sftp = self._client.open_sftp()
        try:
            with sftp.open(remote_path, "r") as f:
                return f.read().decode("utf-8", errors="replace")
        finally:
            sftp.close()

    # ------------------------------------------------------------------
    # Health checks
    # ------------------------------------------------------------------

    def test_connection(self) -> dict:
        """Test the RPi connection and return system info."""
        try:
            self.connect()
            hostname, _, _ = self.exec("hostname")
            uname, _, _ = self.exec("uname -a")
            uptime, _, _ = self.exec("uptime")
            return {
                "connected": True,
                "hostname": hostname.strip(),
                "uname": uname.strip(),
                "uptime": uptime.strip(),
            }
        except Exception as e:
            logger.error("RPi connection test failed: %s", e)
            return {"connected": False, "error": str(e)}
        finally:
            self.disconnect()

    def check_camilladsp(self) -> dict:
        """Check if CamillaDSP is running on the RPi."""
        out, err, code = self.exec("pgrep -a camilladsp")
        running = code == 0
        return {
            "running": running,
            "process_info": out.strip() if running else None,
        }

    def check_mpd(self) -> dict:
        """Check if MPD (Music Player Daemon) is running."""
        out, err, code = self.exec("systemctl is-active mpd")
        active = out.strip() == "active"
        return {"running": active, "status": out.strip()}
