"""Tests for the FastAPI API routers and MeasurementOrchestrator."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.main import app, get_state
from backend.orchestrator import MeasurementOrchestrator, MeasurementSession


# ---------------------------------------------------------------------------
# FastAPI TestClient fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    """Return a FastAPI TestClient for the RoomTune app."""
    return TestClient(app)


# ---------------------------------------------------------------------------
# Health / Devices / Calibration endpoints
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    def test_health(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "version" in data


class TestDevicesEndpoint:
    def test_list_devices(self, client):
        resp = client.get("/api/devices")
        assert resp.status_code == 200
        data = resp.json()
        assert "devices" in data
        assert isinstance(data["devices"], list)
        # umik may be null if not plugged in
        assert "umik" in data


class TestCalibrationEndpoint:
    def test_default_calibration(self, client):
        resp = client.get("/api/calibration")
        assert resp.status_code == 200
        data = resp.json()
        assert data["serial"] == "7055332"
        assert data["is_90deg"] is True
        assert data["num_points"] > 600

    def test_calibration_with_path(self, client):
        from pathlib import Path

        cal_path = Path(__file__).resolve().parent.parent.parent / "Umik" / "7055332.txt"
        if not cal_path.exists():
            pytest.skip("0-degree cal file not present")
        resp = client.get(f"/api/calibration?path={cal_path}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_90deg"] is False


# ---------------------------------------------------------------------------
# RPi config endpoints
# ---------------------------------------------------------------------------


class TestRPiConfigEndpoint:
    def test_set_rpi_host_legacy(self, client):
        resp = client.post("/api/config/rpi-host", json={"host": "test.local"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["host"] == "test.local"
        # Verify it was stored
        assert get_state().rpi_config["host"] == "test.local"

    def test_set_full_rpi_config(self, client):
        payload = {
            "host": "mypi.local",
            "port": 2222,
            "username": "admin",
            "password": "secret123",
            "key_path": "/home/user/.ssh/id_rsa",
        }
        resp = client.post("/api/config/rpi", json=payload)
        assert resp.status_code == 200
        assert resp.json()["host"] == "mypi.local"

        cfg = get_state().rpi_config
        assert cfg["host"] == "mypi.local"
        assert cfg["port"] == 2222
        assert cfg["username"] == "admin"
        assert cfg["password"] == "secret123"
        assert cfg["key_path"] == "/home/user/.ssh/id_rsa"

    def test_set_rpi_config_defaults(self, client):
        """Sending empty body should use defaults."""
        resp = client.post("/api/config/rpi", json={})
        assert resp.status_code == 200
        cfg = get_state().rpi_config
        assert cfg["host"] == "moode.local"
        assert cfg["username"] == "pi"
        assert cfg["password"] is None


# ---------------------------------------------------------------------------
# Measurement endpoints
# ---------------------------------------------------------------------------


class TestMeasurementEndpoints:
    def test_status_idle(self, client):
        """Status when no measurement is running."""
        # Reset first
        client.post("/api/measurement/reset")
        resp = client.get("/api/measurement/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["measuring"] is False
        assert data["status"] == "idle"
        assert data["completed_count"] == 0

    def test_reset(self, client):
        resp = client.post("/api/measurement/reset")
        assert resp.status_code == 200
        assert resp.json()["status"] == "reset"

    def test_stop_when_idle(self, client):
        """Stopping when nothing is recording should return 400."""
        client.post("/api/measurement/reset")
        resp = client.post("/api/measurement/stop")
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Connection test endpoint (mocked — no real RPi)
# ---------------------------------------------------------------------------


class TestConnectionEndpoint:
    @patch("backend.api.connection.RPiConnection")
    @patch("backend.api.connection.CamillaDSPClient")
    @patch("backend.api.connection.MPDClient")
    def test_connection_test_all_fail(self, mock_mpd_cls, mock_cdsp_cls, mock_rpi_cls, client):
        """When all services are unreachable, we get connected=false for each."""
        mock_rpi_cls.return_value.test_connection.return_value = {
            "connected": False,
            "error": "Connection refused",
        }
        mock_cdsp_cls.return_value.test_connection.return_value = {
            "connected": False,
            "error": "Connection refused",
        }
        mock_mpd_cls.return_value.test_connection.return_value = {
            "connected": False,
            "error": "Connection refused",
        }

        resp = client.post(
            "/api/connection/test",
            json={"host": "nonexistent.local", "username": "pi", "password": "test"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["rpi"]["connected"] is False
        assert data["camilladsp"]["connected"] is False
        assert data["mpd"]["connected"] is False

    @patch("backend.api.connection.RPiConnection")
    @patch("backend.api.connection.CamillaDSPClient")
    @patch("backend.api.connection.MPDClient")
    def test_connection_test_all_ok(self, mock_mpd_cls, mock_cdsp_cls, mock_rpi_cls, client):
        mock_rpi_cls.return_value.test_connection.return_value = {
            "connected": True,
            "hostname": "moode",
        }
        mock_cdsp_cls.return_value.test_connection.return_value = {
            "connected": True,
            "state": "Running",
        }
        mock_mpd_cls.return_value.test_connection.return_value = {
            "connected": True,
            "version": "0.23.5",
        }

        resp = client.post(
            "/api/connection/test",
            json={"host": "moode.local", "username": "pi", "password": "moodeaudio"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["rpi"]["connected"] is True
        assert data["camilladsp"]["connected"] is True
        assert data["mpd"]["connected"] is True


# ---------------------------------------------------------------------------
# MeasurementOrchestrator unit tests
# ---------------------------------------------------------------------------


class TestMeasurementOrchestrator:
    def test_initial_state(self):
        orch = MeasurementOrchestrator()
        assert orch.session.measuring is False
        assert orch.session.status == "idle"
        assert orch.session.results == []

    def test_configure(self):
        orch = MeasurementOrchestrator()
        orch.configure(device_index=0, calibration=None)
        assert orch._recorder is not None
        assert orch.session.sweep is not None

    def test_configure_rpi(self):
        orch = MeasurementOrchestrator()
        orch.configure_rpi(
            host="test.local",
            port=2222,
            username="admin",
            password="secret",
            key_path="/tmp/key",
        )
        assert orch._rpi_host == "test.local"
        assert orch._rpi_port == 2222
        assert orch._rpi_username == "admin"
        assert orch._rpi_password == "secret"
        assert orch._rpi_key_path == "/tmp/key"
        # Upload flag should be reset when host changes
        assert orch.session.sweep_uploaded is False

    def test_reset(self):
        orch = MeasurementOrchestrator()
        orch.configure(device_index=0, calibration=None)
        orch.reset()
        assert orch.session.measuring is False
        assert orch.session.status == "idle"
        assert orch.session.results == []

    def test_get_sweep_wav(self):
        orch = MeasurementOrchestrator()
        orch.configure(device_index=0, calibration=None, sweep_duration=1.0)
        wav_bytes = orch.get_sweep_wav()
        assert isinstance(wav_bytes, bytes)
        assert len(wav_bytes) > 1000  # Should be a valid WAV

    def test_start_without_configure_raises(self):
        orch = MeasurementOrchestrator()
        with pytest.raises(RuntimeError, match="not configured"):
            orch.start_measurement(1, "left")

    def test_run_measurement_without_configure_raises(self):
        orch = MeasurementOrchestrator()
        with pytest.raises(RuntimeError, match="not configured"):
            orch.run_measurement(1, "left")


class TestMeasurementSession:
    def test_initial_state(self):
        s = MeasurementSession()
        assert s.measuring is False
        assert s.status == "idle"
        assert s.averaged_frequency_response is None

    def test_get_result_empty(self):
        s = MeasurementSession()
        assert s.get_result(1, "left") is None
