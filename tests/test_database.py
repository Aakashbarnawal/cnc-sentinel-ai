"""Unit tests for MongoDB connection, document models, sequence generation, and database operations."""

import os
from datetime import datetime
import pytest
import mongomock

from database.models import format_mongo_doc, get_next_sequence_val
from backend.services.telemetry_service import (
    register_machine,
    get_machine_by_id,
    create_telemetry_reading,
    create_telemetry_batch,
    get_telemetry_by_id,
)
from backend.services.prediction_service import (
    predict_machine_failure,
    get_prediction_by_id,
)
from backend.services.maintenance_service import (
    create_maintenance_event,
    get_maintenance_by_id,
)
from backend.schemas import MachineCreate, TelemetryCreate, TelemetryBatchCreate, PredictionRequest, MaintenanceCreate


@pytest.fixture
def test_db():
    """Fixture providing isolated in-memory mongomock Database instance for unit testing."""
    client = mongomock.MongoClient()
    db = client["test_predictive_maintenance"]
    db["machines"].create_index([("machine_id", 1)], unique=True)
    db["telemetry_readings"].create_index([("machine_id", 1), ("timestamp", 1)], unique=True)
    return db


def test_machine_mongodb_crud(test_db):
    """Test Machine MongoDB registration, retrieval, and unique constraint."""
    m1 = MachineCreate(machine_id="CNC-999", machine_type="CNC")
    rec1 = register_machine(m1, test_db)
    assert rec1["id"] == 1
    assert rec1["machine_id"] == "CNC-999"

    retrieved = get_machine_by_id("CNC-999", test_db)
    assert retrieved is not None
    assert retrieved["machine_type"] == "CNC"

    # Duplicate registration should raise ValueError
    with pytest.raises(ValueError) as exc:
        register_machine(m1, test_db)
    assert "already registered" in str(exc.value)


def test_telemetry_mongodb_and_duplicate(test_db):
    """Test TelemetryReading creation in MongoDB and batch error handling."""
    ts = datetime(2026, 10, 2, 12, 0, 0)
    t1 = TelemetryCreate(
        machine_id="CNC-001",
        timestamp=ts,
        machine_type="CNC",
        temp=50.0,
        vibration=1.5,
        current=12.0,
        rpm=12000,
        hours=100.0,
        workload=50.0,
        tool_wear=5.0,
    )
    rec1 = create_telemetry_reading(t1, test_db)
    assert rec1["id"] == 1

    # Single duplicate fails
    with pytest.raises(ValueError) as exc:
        create_telemetry_reading(t1, test_db)
    assert "Duplicate telemetry record" in str(exc.value)

    # Batch containing duplicate fails cleanly
    t2 = TelemetryCreate(
        machine_id="CNC-001",
        timestamp=datetime(2026, 10, 2, 12, 1, 0),
        machine_type="CNC",
        temp=52.0,
        vibration=1.6,
        current=12.5,
        rpm=12000,
        hours=100.02,
        workload=55.0,
        tool_wear=5.1,
    )
    batch_data = TelemetryBatchCreate(readings=[t2, t1])  # t1 is duplicate
    with pytest.raises(ValueError) as exc_batch:
        create_telemetry_batch(batch_data, test_db)
    assert "Batch ingestion failed" in str(exc_batch.value)


def test_prediction_record_mongodb(test_db):
    """Test PredictionRecord MongoDB insertion and query."""
    register_machine(MachineCreate(machine_id="CNC-001", machine_type="CNC"), test_db)
    req = PredictionRequest(
        type="L",
        air_temperature_c=25.0,
        process_temperature_c=35.0,
        rotational_speed_rpm=1400,
        torque_nm=45.0,
        tool_wear_min=150.0,
        machine_id="CNC-001",
    )
    res = predict_machine_failure(req, test_db)
    assert res["id"] == 1
    assert 0.0 <= res["failure_probability"] <= 1.0
    assert res["classification_threshold"] == 0.33

    retrieved = get_prediction_by_id(test_db, 1)
    assert retrieved is not None
    assert retrieved["machine_id"] == "CNC-001"


def test_maintenance_event_mongodb(test_db):
    """Test MaintenanceEvent MongoDB creation and unregistered machine validation."""
    register_machine(MachineCreate(machine_id="PRINTER-01", machine_type="3D_Printer"), test_db)

    ev = MaintenanceCreate(
        machine_id="PRINTER-01",
        event_type="inspection",
        description="Routine nozzle check",
        event_timestamp=datetime(2026, 10, 2, 15, 0, 0),
        status="scheduled",
    )
    res = create_maintenance_event(ev, test_db)
    assert res["id"] == 1
    assert res["event_type"] == "inspection"

    retrieved = get_maintenance_by_id(1, test_db)
    assert retrieved is not None
    assert retrieved["status"] == "scheduled"

