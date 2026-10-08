"""Unit and Integration Tests for Step 7: Digital Twin Simulator, Equipment Diagnostics, and Telegram Bot Integration."""

import os
import time
import pytest
from datetime import datetime, timezone
import pandas as pd
from unittest.mock import patch, MagicMock

from simulator.engine import TelemetrySimulator, generate_telemetry_dataset
from backend.services.diagnostic_service import evaluate_equipment_diagnostics
from backend.services.telegram_service import (
    is_telegram_enabled,
    send_telegram_message,
    send_machine_alert,
    _last_alert_sent,
    _last_severity,
)
from backend.services.simulation_manager import SimulationManager


def test_1_simulator_scenarios_produce_valid_readings():
    """Test 1: Verify all 4 simulator scenarios produce valid telemetry readings."""
    sim = TelemetrySimulator(machine_id="TEST-SIM-01", machine_type="CNC")
    now = datetime.now(timezone.utc)
    
    for scenario in ["normal", "degrading", "near_failure", "sensor_anomaly"]:
        sim.set_scenario(scenario)
        reading = sim.step(current_time=now)
        assert reading["machine_id"] == "TEST-SIM-01"
        assert reading.get("data_source", "SIMULATION") == "SIMULATION"
        assert isinstance(reading["temp"], float)
        assert isinstance(reading["vibration"], float)
        assert isinstance(reading["current"], float)
        assert isinstance(reading["rpm"], int)



def test_2_generated_readings_bounded_and_correct_types():
    """Test 2: Verify generated readings have correct types and bounded values."""
    dataset = generate_telemetry_dataset(num_machines=4, samples_per_machine=50, seed=42)
    for record in dataset:
        assert 0.0 <= record["temp"] <= 200.0
        assert 0.0 <= record["vibration"] <= 100.0
        assert 0.0 <= record["current"] <= 200.0
        assert 0 <= record["rpm"] <= 50000
        assert 0.0 <= record["health_index"] <= 100.0


def test_3_degradation_changes_signals_over_time():
    """Test 3: Verify degradation scenario increases temperature and vibration over time."""
    sim = TelemetrySimulator(machine_id="TEST-DEG-01", machine_type="CNC", initial_health=90.0, degradation_profile="rapid_degrade_failure")
    now = datetime.now(timezone.utc)
    
    initial_reading = sim.step(current_time=now)
    for _ in range(50):
        sim.step(current_time=now)
    final_reading = sim.step(current_time=now)

    assert final_reading["health_index"] < initial_reading["health_index"]
    assert final_reading["tool_wear"] > initial_reading["tool_wear"]


def test_4_equipment_diagnostics_evaluation():
    """Test 4: Verify equipment-aware diagnostic rules produce expected severity and suspected issues."""
    normal_diag = evaluate_equipment_diagnostics(
        equipment_type="CNC", temp=45.0, vibration=1.2, current=12.0, rpm=12000
    )
    assert normal_diag["severity"] == "NORMAL"

    critical_diag = evaluate_equipment_diagnostics(
        equipment_type="CNC", temp=90.0, vibration=8.5, current=35.0, rpm=12000
    )
    assert critical_diag["severity"] == "CRITICAL"
    assert len(critical_diag["suspected_faults"]) >= 1


def test_5_telegram_cooldown_prevents_spam():
    """Test 5: Verify Telegram alert cooldown prevents duplicate notifications within cooldown window."""
    _last_alert_sent.clear()
    _last_severity.clear()

    with patch("backend.services.telegram_service.is_telegram_enabled", return_value=True), \
         patch("backend.services.telegram_service.send_telegram_message", return_value=(True, "Delivered")) as mock_send:
        
        # 1st alert -> Should send
        ok1, msg1 = send_machine_alert(
            machine_id="TEST-COOL-01",
            equipment_type="CNC",
            severity="WARNING",
            temp=80.0,
            vibration=6.0,
        )
        assert ok1 is True
        assert mock_send.call_count == 1

        # 2nd alert immediately after (same severity) -> Should be suppressed by cooldown
        ok2, msg2 = send_machine_alert(
            machine_id="TEST-COOL-01",
            equipment_type="CNC",
            severity="WARNING",
            temp=81.0,
            vibration=6.1,
        )
        assert ok2 is False
        assert "suppressed" in msg2.lower()
        assert mock_send.call_count == 1  # Not incremented


def test_6_telegram_escalation_bypasses_cooldown():
    """Test 6: Verify severity escalation from WARNING to CRITICAL bypasses cooldown."""
    _last_alert_sent.clear()
    _last_severity.clear()

    with patch("backend.services.telegram_service.is_telegram_enabled", return_value=True), \
         patch("backend.services.telegram_service.send_telegram_message", return_value=(True, "Delivered")) as mock_send:
        
        # WARNING alert
        send_machine_alert("TEST-ESC-01", "CNC", "WARNING", temp=78.0)
        assert mock_send.call_count == 1

        # CRITICAL escalation alert immediately -> Should bypass cooldown
        ok2, _ = send_machine_alert("TEST-ESC-01", "CNC", "CRITICAL", temp=92.0)
        assert ok2 is True
        assert mock_send.call_count == 2


def test_7_telegram_disabled_mode_does_not_break_system():
    """Test 7: Verify Telegram disabled mode returns graceful status without errors."""
    with patch("backend.services.telegram_service.is_telegram_enabled", return_value=False):
        ok, msg = send_machine_alert("TEST-DIS-01", "CNC", "CRITICAL", temp=95.0)
        assert ok is False
        assert "disabled" in msg.lower()


def test_8_telegram_http_error_resilience():
    """Test 8: Verify Telegram API HTTP failures are caught gracefully without crashing."""
    with patch("backend.services.telegram_service.is_telegram_enabled", return_value=True), \
         patch("backend.services.telegram_service.get_telegram_config", return_value=("fake_token", "fake_chat_id", 60)), \
         patch("urllib.request.urlopen", side_effect=Exception("Connection refused")):
        
        ok, msg = send_telegram_message("Test message", force=True)
        assert ok is False
        assert "error" in msg.lower()


def test_9_simulation_manager_lifecycle():
    """Test 9: Verify SimulationManager starts, changes scenarios, sets speed, and stops cleanly."""
    mgr = SimulationManager()
    assert mgr.get_status()["machine_count"] >= 1
    
    mgr.set_speed(2.0)
    assert mgr.speed_factor == 2.0
    
    ok = mgr.set_machine_scenario("SN-CNC-001", "near_failure")
    assert ok is True

    mgr.stop_simulation()
    assert mgr.is_running is False


def test_10_idempotent_virtual_machine_registration():
    """Task 1 Test: Verify default virtual machines are registered idempotently in db['machines']."""
    import mongomock
    from backend.services.telemetry_service import get_machines
    
    db = mongomock.MongoClient()["predictive_maintenance"]
    mgr = SimulationManager()
    
    # 1st run -> Registers 4 virtual machines
    mgr.ensure_virtual_machines_registered(db)
    total1, items1 = get_machines(db)
    assert total1 == 4
    machine_ids1 = {m["machine_id"] for m in items1}
    assert {"SN-CNC-001", "SN-PRN-002", "SN-MTR-003", "SN-PMP-004"}.issubset(machine_ids1)

    # 2nd run -> Idempotent check, no duplicate error, total count remains 4
    mgr.ensure_virtual_machines_registered(db)
    total2, items2 = get_machines(db)
    assert total2 == 4


def test_11_duplicate_machine_registration_prevention():
    """Task 1 Test: Verify duplicate machine registration fails gracefully without overwriting metadata."""
    import mongomock
    from backend.schemas import MachineCreate
    from backend.services.telemetry_service import register_machine, get_machine_by_id
    
    db = mongomock.MongoClient()["predictive_maintenance"]
    
    # Initial registration
    m1 = MachineCreate(machine_id="SN-DUP-001", machine_type="CNC")
    register_machine(m1, db)
    
    # Duplicate attempt -> Raises ValueError
    with pytest.raises(ValueError) as exc_info:
        register_machine(m1, db)
    assert "already registered" in str(exc_info.value)
    
    # Verify metadata is untouched
    fetched = get_machine_by_id("SN-DUP-001", db)
    assert fetched["machine_type"] == "CNC"

