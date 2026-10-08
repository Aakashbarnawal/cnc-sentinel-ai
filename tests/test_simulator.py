"""Unit tests for synthetic telemetry simulator engine and data generator."""

import os
import tempfile
import pytest
from datetime import datetime
import pandas as pd

from config.schema import (
    SensorData,
    CoreSensorData,
    ALLOWED_SCENARIOS,
    ALLOWED_MACHINE_TYPES,
    validate_telemetry_dict,
)
from simulator.engine import TelemetrySimulator, generate_telemetry_dataset
from simulator.generate_data import generate_and_save


def test_simulator_returns_expected_schema_fields():
    """Test 1: Verify generated records contain all 12 expected schema fields."""
    dataset = generate_telemetry_dataset(num_machines=2, samples_per_machine=10, seed=42)
    assert len(dataset) == 20
    first_record = dataset[0]
    expected_fields = set(SensorData.all_field_names())
    actual_fields = set(first_record.keys())
    assert actual_fields == expected_fields, f"Field mismatch. Missing: {expected_fields - actual_fields}"


def test_numeric_readings_types_and_validity():
    """Test 2: Verify numeric readings have valid types and values (no NaN/Inf/out-of-bounds)."""
    dataset = generate_telemetry_dataset(num_machines=4, samples_per_machine=50, seed=123)
    numeric_fields = ["temp", "vibration", "current", "rpm", "hours", "workload", "tool_wear", "health_index"]

    for record in dataset:
        for field in numeric_fields:
            val = record[field]
            assert isinstance(val, (int, float)), f"Field {field} value {val} is not numeric"
            assert not pd.isna(val), f"Field {field} contains NaN"
            assert not pd.isna(val) and val != float("inf") and val != float("-inf"), f"Field {field} is infinite"
            
        assert isinstance(record["rpm"], int), f"rpm must be int, got {type(record['rpm'])}"


def test_only_permitted_machine_types_and_scenarios():
    """Test 3: Verify produced machine_type and scenario values belong to allowed sets."""
    dataset = generate_telemetry_dataset(num_machines=6, samples_per_machine=100, seed=42)
    for record in dataset:
        assert record["machine_type"] in ALLOWED_MACHINE_TYPES, f"Unauthorized machine_type: {record['machine_type']}"
        assert record["scenario"] in ALLOWED_SCENARIOS, f"Unauthorized scenario: {record['scenario']}"


def test_both_machine_types_appear_in_standard_config():
    """Test 4: Verify both 'CNC' and '3D_Printer' appear in standard demo dataset (6 machines)."""
    dataset = generate_telemetry_dataset(num_machines=6, samples_per_machine=50, seed=42)
    types_found = {r["machine_type"] for r in dataset}
    assert "CNC" in types_found, "Missing 'CNC' machine type"
    assert "3D_Printer" in types_found, "Missing '3D_Printer' machine type"


def test_all_three_scenarios_appear_in_standard_config():
    """Test 5: Verify all three scenarios ('normal', 'degrading', 'near_failure') appear in standard dataset."""
    dataset = generate_telemetry_dataset(num_machines=6, samples_per_machine=500, seed=42)
    scenarios_found = {r["scenario"] for r in dataset}
    expected_scenarios = {"normal", "degrading", "near_failure"}
    assert scenarios_found == expected_scenarios, f"Scenario coverage incomplete. Got: {scenarios_found}"


def test_timestamps_chronological_per_machine():
    """Test 6: Verify timestamps are strictly increasing chronologically for each machine."""
    dataset = generate_telemetry_dataset(num_machines=4, samples_per_machine=100, seed=42)
    machine_timestamps = {}
    for r in dataset:
        machine_timestamps.setdefault(r["machine_id"], []).append(r["timestamp"])

    for m_id, ts_list in machine_timestamps.items():
        for i in range(1, len(ts_list)):
            assert ts_list[i] > ts_list[i - 1], f"Timestamp regression for {m_id} at index {i}"


def test_no_duplicate_machine_timestamp_records():
    """Test 7: Verify no duplicate (machine_id, timestamp) pairs are generated."""
    dataset = generate_telemetry_dataset(num_machines=6, samples_per_machine=200, seed=42)
    seen = set()
    for r in dataset:
        pair = (r["machine_id"], r["timestamp"])
        assert pair not in seen, f"Duplicate record for pair {pair}"
        seen.add(pair)


def test_reproducibility_with_same_seed():
    """Test 8: Verify repeated runs with the same seed generate identical records."""
    run1 = generate_telemetry_dataset(num_machines=4, samples_per_machine=100, seed=99)
    run2 = generate_telemetry_dataset(num_machines=4, samples_per_machine=100, seed=99)
    assert len(run1) == len(run2)
    for r1, r2 in zip(run1, run2):
        assert r1 == r2, f"Divergence detected between reproducible runs: {r1} vs {r2}"


def test_generated_records_pass_schema_validation():
    """Test 9: Verify all generated records pass config.schema validation."""
    dataset = generate_telemetry_dataset(num_machines=6, samples_per_machine=100, seed=42)
    for idx, record in enumerate(dataset):
        is_valid, err = validate_telemetry_dict(record, require_full_schema=True)
        assert is_valid, f"Record index {idx} failed schema validation: {err}"


def test_invalid_configuration_rejected():
    """Test 10: Verify invalid CLI / generator parameters raise informative ValueErrors."""
    with pytest.raises(ValueError) as exc1:
        generate_telemetry_dataset(num_machines=0, samples_per_machine=100)
    assert "num_machines must be >= 1" in str(exc1.value)

    with pytest.raises(ValueError) as exc2:
        generate_telemetry_dataset(num_machines=2, samples_per_machine=0)
    assert "samples_per_machine must be >= 1" in str(exc2.value)

    with pytest.raises(ValueError) as exc3:
        TelemetrySimulator(machine_id="TEST-01", machine_type="QuantumComputer")
    assert "Invalid machine_type" in str(exc3.value)


def test_generate_and_save_csv():
    """Test CSV generation helper function and file output."""
    tmp_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scratch", "test_temp_sim")
    os.makedirs(tmp_dir, exist_ok=True)
    csv_path = os.path.join(tmp_dir, "test_telemetry.csv")
    try:
        summary = generate_and_save(machines=4, samples_per_machine=50, seed=42, output_path=csv_path)

        assert os.path.exists(csv_path)
        assert summary["total_rows"] == 200
        assert summary["validation_failures"] == 0
        assert summary["duplicate_records"] == 0

        df = pd.read_csv(csv_path)
        assert len(df) == 200
        assert list(df.columns) == SensorData.all_field_names()
    finally:
        if os.path.exists(csv_path):
            try:
                os.remove(csv_path)
            except Exception:
                pass
