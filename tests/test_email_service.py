"""Unit and Integration Tests for Email Alert Notification System."""

import os
import time
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from backend.main import app
from backend.services.email_service import (
    is_email_enabled,
    get_smtp_config,
    get_email_status,
    send_email_message,
    send_machine_email_alert,
    _last_email_sent,
    _last_email_severity,
)


@pytest.fixture
def mock_smtp_config(monkeypatch):
    """Fixture to set up clean SMTP environment variables for testing."""
    monkeypatch.setenv("EMAIL_ENABLED", "true")
    monkeypatch.setenv("SMTP_HOST", "smtp.test.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USERNAME", "test_user@test.com")
    monkeypatch.setenv("SMTP_PASSWORD", "test_secret_password")
    monkeypatch.setenv("SMTP_FROM_EMAIL", "test_user@test.com")
    monkeypatch.setenv("ALERT_RECIPIENT_EMAIL", "recipient@test.com")
    monkeypatch.setenv("SMTP_USE_TLS", "true")
    monkeypatch.setenv("EMAIL_COOLDOWN_SEC", "300")


def test_email_enabled_check(monkeypatch):
    """Test EMAIL_ENABLED environment variable parsing."""
    monkeypatch.setenv("EMAIL_ENABLED", "true")
    assert is_email_enabled() is True

    monkeypatch.setenv("EMAIL_ENABLED", "false")
    assert is_email_enabled() is False

    monkeypatch.delenv("EMAIL_ENABLED", raising=False)
    monkeypatch.setenv("SMTP_ENABLED", "true")
    assert is_email_enabled() is True


def test_get_email_status_hides_secrets(mock_smtp_config):
    """Test get_email_status returns public status and redacts recipient without exposing passwords."""
    status_info = get_email_status()
    assert status_info["enabled"] is True
    assert status_info["configured"] is True
    assert status_info["smtp_host"] == "smtp.test.com"
    assert status_info["smtp_port"] == 587
    assert status_info["recipient_redacted"] == "r***t@test.com"
    
    # Verify passwords and credentials are NEVER exposed
    status_json = str(status_info)
    assert "test_secret_password" not in status_json
    assert "password" not in status_info


def test_send_email_successful_mocked_delivery(mock_smtp_config):
    """Test successful email delivery using mocked smtplib transport."""
    with patch("smtplib.SMTP") as mock_smtp_cls:
        mock_instance = MagicMock()
        mock_smtp_cls.return_value = mock_instance

        success, message = send_email_message(
            subject="Test Subject",
            html_content="<p>Test HTML</p>",
            text_content="Test Text",
            force=True,
        )

        assert success is True
        assert "successfully delivered" in message.lower()
        mock_instance.starttls.assert_called_once()
        mock_instance.login.assert_called_once_with("test_user@test.com", "test_secret_password")
        mock_instance.send_message.assert_called_once()


def test_send_email_auth_failure(mock_smtp_config):
    """Test handling of SMTP authentication failure."""
    import smtplib
    with patch("smtplib.SMTP") as mock_smtp_cls:
        mock_instance = MagicMock()
        mock_instance.login.side_effect = smtplib.SMTPAuthenticationError(535, b"Authentication failed")
        mock_smtp_cls.return_value = mock_instance

        success, message = send_email_message(
            subject="Test Subject",
            html_content="<p>Test</p>",
            text_content="Test",
            force=True,
        )

        assert success is False
        assert "authentication failed" in message.lower()


def test_send_email_connection_timeout(mock_smtp_config):
    """Test handling of SMTP connection timeout."""
    import socket
    with patch("smtplib.SMTP", side_effect=socket.timeout("Timed out")):
        success, message = send_email_message(
            subject="Test Subject",
            html_content="<p>Test</p>",
            text_content="Test",
            force=True,
        )

        assert success is False
        assert "error" in message.lower()


def test_email_alert_cooldown_deduplication(mock_smtp_config):
    """Test alert deduplication and cooldown logic."""
    _last_email_sent.clear()
    _last_email_severity.clear()

    with patch("backend.services.email_service.send_email_message", return_value=(True, "Delivered")) as mock_send:
        # 1st alert -> Delivered
        ok1, msg1 = send_machine_email_alert(
            machine_id="TEST-EML-01",
            equipment_type="CNC",
            severity="WARNING",
            temp=80.0,
        )
        assert ok1 is True
        assert mock_send.call_count == 1

        # 2nd alert immediately after (same severity) -> Suppressed by cooldown
        ok2, msg2 = send_machine_email_alert(
            machine_id="TEST-EML-01",
            equipment_type="CNC",
            severity="WARNING",
            temp=81.0,
        )
        assert ok2 is False
        assert "suppressed" in msg2.lower()
        assert mock_send.call_count == 1  # Not incremented

        # 3rd alert (severity escalation WARNING -> CRITICAL) -> Bypasses cooldown
        ok3, msg3 = send_machine_email_alert(
            machine_id="TEST-EML-01",
            equipment_type="CNC",
            severity="CRITICAL",
            temp=95.0,
        )
        assert ok3 is True
        assert mock_send.call_count == 2


def test_notification_status_api_endpoint(mock_smtp_config):
    """Test GET /api/v1/notifications/status returns valid status structure without exposing secrets."""
    client = TestClient(app)
    res = client.get("/api/v1/notifications/status")
    assert res.status_code == 200
    data = res.json()
    assert "email" in data
    assert "telegram" in data
    assert data["email"]["configured"] is True
    assert "password" not in str(data)


def test_test_email_api_endpoint(mock_smtp_config):
    """Test POST /api/v1/notifications/test-email user-triggered test email endpoint."""
    client = TestClient(app)
    with patch("backend.services.email_service.send_email_message", return_value=(True, "Test email delivered")):
        res = client.post("/api/v1/notifications/test-email", json={"recipient_email": "test_override@example.com"})
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert "delivered" in data["message"].lower()


def test_send_email_disabled_behavior(monkeypatch):
    """Test email behavior when SMTP is disabled."""
    monkeypatch.setenv("EMAIL_ENABLED", "false")
    monkeypatch.setenv("SMTP_HOST", "smtp.test.com")
    monkeypatch.setenv("SMTP_USERNAME", "user@test.com")
    monkeypatch.setenv("SMTP_PASSWORD", "secret")
    monkeypatch.setenv("ALERT_RECIPIENT_EMAIL", "recipient@test.com")

    # When force is False, sending should be rejected because notifications are disabled
    success, message = send_email_message("Test", "<p>Test</p>", "Test", force=False)
    assert success is False
    assert "disabled" in message.lower()


def test_send_email_smtp_not_configured(monkeypatch):
    """Test email behavior when SMTP credentials are not configured."""
    monkeypatch.delenv("SMTP_USERNAME", raising=False)
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)
    monkeypatch.setenv("EMAIL_ENABLED", "true")

    success, message = send_email_message("Test", "<p>Test</p>", "Test", force=True)
    assert success is False
    assert "not configured" in message.lower()


def test_send_email_invalid_recipient(mock_smtp_config):
    """Test email validation failure when recipient is invalid."""
    success, message = send_email_message("Test", "<p>Test</p>", "Test", recipient_override="invalid-email", force=True)
    assert success is False
    assert "valid" in message.lower()


def test_health_report_email_success(mock_smtp_config):
    """Test successful compilation and delivery of machine health report."""
    from mongomock import MongoClient
    from datetime import datetime, timezone
    from backend.services.email_service import send_machine_health_report_email

    client = MongoClient()
    db = client["test_db"]
    db["machines"].insert_one({"machine_id": "SN-CNC-001", "machine_type": "CNC"})
    db["telemetry"].insert_one({
        "machine_id": "SN-CNC-001",
        "temp": 65.2,
        "vibration": 2.1,
        "current": 18.5,
        "rpm": 12000,
        "tool_wear": 4.5,
        "workload": 75.0,
        "health_index": 96.0,
        "scenario": "normal",
        "timestamp": datetime.now(timezone.utc),
    })
    db["prediction_records"].insert_one({
        "machine_id": "SN-CNC-001",
        "failure_probability": 0.02,
        "classification_threshold": 0.33,
        "predicted_class": 0,
        "predicted_label": "Normal Operation",
        "model_name": "XGBoost",
        "created_at": datetime.now(timezone.utc),
    })
    db["maintenance_events"].insert_one({
        "machine_id": "SN-CNC-001",
        "event_type": "maintenance",
        "description": "Spindle Lubrication",
        "event_timestamp": datetime.now(timezone.utc),
        "status": "completed",
    })

    with patch("backend.services.email_service.send_email_message", return_value=(True, "Delivered")) as mock_send:
        ok, msg = send_machine_health_report_email("SN-CNC-001", "operator@factory.com", db)
        assert ok is True
        assert mock_send.call_count == 1
        call_args = mock_send.call_args[1]
        assert "CNC Sentinel AI — Machine Health Report — SN-CNC-001" in call_args["subject"]
        assert "operator@factory.com" == call_args["recipient_override"]
        assert "CNC SENTINEL AI" in call_args["html_content"]


def test_health_report_missing_machine(mock_smtp_config):
    """Test health report error handling when machine is not registered."""
    from mongomock import MongoClient
    from backend.services.email_service import send_machine_health_report_email

    client = MongoClient()
    db = client["test_db"]

    ok, msg = send_machine_health_report_email("NONEXISTENT-999", "operator@factory.com", db)
    assert ok is False
    assert "not registered" in msg.lower()


def test_health_report_graceful_missing_telemetry_and_prediction(mock_smtp_config):
    """Test health report gracefully falls back to 'Not available' when telemetry or prediction records are missing."""
    from mongomock import MongoClient
    from backend.services.email_service import send_machine_health_report_email

    client = MongoClient()
    db = client["test_db"]
    db["machines"].insert_one({"machine_id": "SN-NEW-001", "machine_type": "3D_Printer"})

    with patch("backend.services.email_service.send_email_message", return_value=(True, "Delivered")) as mock_send:
        ok, msg = send_machine_health_report_email("SN-NEW-001", "operator@factory.com", db)
        assert ok is True
        assert mock_send.call_count == 1
        call_args = mock_send.call_args[1]
        assert "Not available" in call_args["html_content"]
        assert "Not available" in call_args["text_content"]


def test_health_report_api_endpoint(mock_smtp_config):
    """Test POST /api/v1/reports/email endpoint with mocked database and SMTP."""
    client = TestClient(app)
    with patch("backend.main.send_machine_health_report_email", return_value=(True, "Health report delivered")):
        res = client.post("/api/v1/reports/email", json={
            "machine_id": "SN-CNC-001",
            "recipient_email": "engineer@plant.com",
        })
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["machine_id"] == "SN-CNC-001"
        assert data["recipient_email"] == "engineer@plant.com"


def test_health_report_api_endpoint_invalid_email(mock_smtp_config):
    """Test POST /api/v1/reports/email endpoint validation on invalid email string."""
    client = TestClient(app)
    res = client.post("/api/v1/reports/email", json={
        "machine_id": "SN-CNC-001",
        "recipient_email": "not-an-email",
    })
    assert res.status_code == 422

