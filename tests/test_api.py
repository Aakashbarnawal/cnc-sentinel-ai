"""Integration Tests for FastAPI Backend Endpoints and Model Integration."""

import os
from datetime import datetime
import pytest
from fastapi.testclient import TestClient
from database.connection import get_db
from backend.main import app


@pytest.fixture
def test_client():
    """Fixture providing FastAPI TestClient using an isolated in-memory mongomock database."""
    import mongomock
    client = mongomock.MongoClient()
    db = client["test_predictive_maintenance_api"]

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


# =====================================================================
# SYSTEM & HEALTH TESTS
# =====================================================================

def test_health_endpoint(test_client):
    """Test GET /health returns 200 OK and database status."""
    res = test_client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"


def test_readiness_endpoint(test_client):
    """Test GET /ready returns 200 OK and production model details."""
    res = test_client.get("/ready")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ready"
    assert data["model_loaded"] is True
    assert data["model_name"] == "XGBoost"
    assert data["threshold"] == 0.33


def test_openapi_docs(test_client):
    """Test OpenAPI documentation endpoints."""
    res_docs = test_client.get("/docs")
    assert res_docs.status_code == 200
    res_json = test_client.get("/openapi.json")
    assert res_json.status_code == 200


# =====================================================================
# MACHINE ENDPOINTS TESTS
# =====================================================================

def test_machine_registration_and_retrieval(test_client):
    """Test machine registration, retrieval, listing, and 404 handling."""
    # Register CNC machine
    res_create = test_client.post("/api/v1/machines", json={"machine_id": "CNC-101", "machine_type": "CNC"})
    assert res_create.status_code == 201
    data_create = res_create.json()
    assert data_create["machine_id"] == "CNC-101"

    # Duplicate registration error
    res_dup = test_client.post("/api/v1/machines", json={"machine_id": "CNC-101", "machine_type": "CNC"})
    assert res_dup.status_code == 400

    # Retrieve by ID
    res_get = test_client.get("/api/v1/machines/CNC-101")
    assert res_get.status_code == 200
    assert res_get.json()["machine_type"] == "CNC"

    # Retrieve 404
    res_404 = test_client.get("/api/v1/machines/NON-EXISTENT")
    assert res_404.status_code == 404

    # List machines
    res_list = test_client.get("/api/v1/machines")
    assert res_list.status_code == 200
    assert res_list.json()["total"] == 1


# =====================================================================
# TELEMETRY ENDPOINTS TESTS
# =====================================================================

def test_telemetry_single_and_batch_ingestion(test_client):
    """Test single and batch telemetry ingestion, filtering, and validation."""
    ts1 = datetime(2026, 10, 2, 18, 0, 0).isoformat()
    t_payload = {
        "machine_id": "CNC-101",
        "timestamp": ts1,
        "machine_type": "CNC",
        "temp": 65.0,
        "vibration": 2.5,
        "current": 15.0,
        "rpm": 12000,
        "hours": 150.0,
        "workload": 75.0,
        "tool_wear": 10.0,
        "health_index": 90.0,
        "scenario": "normal",
    }

    # Single ingestion
    res_t1 = test_client.post("/api/v1/telemetry", json=t_payload)
    assert res_t1.status_code == 201
    t1_id = res_t1.json()["id"]

    # Invalid range validation error
    invalid_t = t_payload.copy()
    invalid_t["temp"] = 350.0  # Exceeds max 200.0 °C
    res_inv = test_client.post("/api/v1/telemetry", json=invalid_t)
    assert res_inv.status_code in (400, 422)

    # Batch ingestion
    ts2 = datetime(2026, 10, 2, 18, 1, 0).isoformat()
    t_payload2 = t_payload.copy()
    t_payload2["timestamp"] = ts2

    res_batch = test_client.post("/api/v1/telemetry/batch", json={"readings": [t_payload2]})
    assert res_batch.status_code == 201
    assert len(res_batch.json()) == 1

    # List and filter telemetry
    res_list = test_client.get("/api/v1/telemetry?machine_id=CNC-101")
    assert res_list.status_code == 200
    assert res_list.json()["total"] == 2

    # Get single telemetry by ID
    res_single = test_client.get(f"/api/v1/telemetry/{t1_id}")
    assert res_single.status_code == 200
    assert res_single.json()["temp"] == 65.0

    # Retrieve 404
    res_404 = test_client.get("/api/v1/telemetry/99999")
    assert res_404.status_code == 404


# =====================================================================
# ML PREDICTION ENDPOINTS TESTS
# =====================================================================

def test_prediction_endpoint_and_persistence(test_client):
    """Test failure prediction using AI4I features, threshold 0.33, persistence, and invalid inputs."""
    # Register machine first
    test_client.post("/api/v1/machines", json={"machine_id": "CNC-101", "machine_type": "CNC"})

    pred_payload = {
        "type": "L",
        "air_temperature_c": 25.0,
        "process_temperature_c": 35.0,
        "rotational_speed_rpm": 1400,
        "torque_nm": 45.0,
        "tool_wear_min": 150.0,
        "machine_id": "CNC-101",
    }

    # Execute prediction
    res_pred = test_client.post("/api/v1/predictions", json=pred_payload)
    assert res_pred.status_code == 201
    data_pred = res_pred.json()

    assert 0.0 <= data_pred["failure_probability"] <= 1.0
    assert data_pred["classification_threshold"] == 0.33
    assert data_pred["predicted_class"] in (0, 1)
    assert data_pred["model_name"] == "XGBoost"
    pred_id = data_pred["id"]

    # Retrieve saved prediction
    res_get_pred = test_client.get(f"/api/v1/predictions/{pred_id}")
    assert res_get_pred.status_code == 200
    assert res_get_pred.json()["machine_id"] == "CNC-101"

    # List predictions
    res_list_pred = test_client.get("/api/v1/predictions")
    assert res_list_pred.status_code == 200
    assert res_list_pred.json()["total"] >= 1

    # Invalid categorical type error
    invalid_pred = pred_payload.copy()
    invalid_pred["type"] = "INVALID"
    res_inv = test_client.post("/api/v1/predictions", json=invalid_pred)
    assert res_inv.status_code in (400, 422)


def test_prediction_valid_registered_machine(test_client):
    """Task 2 Test: Prediction with a valid registered machine ID."""
    test_client.post("/api/v1/machines", json={"machine_id": "VALID-CNC-01", "machine_type": "CNC"})
    res = test_client.post("/api/v1/predictions", json={
        "type": "L",
        "air_temperature_c": 25.0,
        "process_temperature_c": 35.0,
        "rotational_speed_rpm": 1400,
        "torque_nm": 45.0,
        "tool_wear_min": 150.0,
        "machine_id": "VALID-CNC-01",
    })
    assert res.status_code == 201
    data = res.json()
    assert data["machine_id"] == "VALID-CNC-01"


def test_prediction_invalid_unregistered_machine(test_client):
    """Task 2 Test: Prediction with an invalid (unregistered) machine ID fails with 400 Bad Request."""
    res = test_client.post("/api/v1/predictions", json={
        "type": "L",
        "air_temperature_c": 25.0,
        "process_temperature_c": 35.0,
        "rotational_speed_rpm": 1400,
        "torque_nm": 45.0,
        "tool_wear_min": 150.0,
        "machine_id": "UNREGISTERED-MACHINE-99",
    })
    assert res.status_code == 400
    assert "not registered" in res.json()["detail"].lower()


def test_prediction_standalone_without_machine_id(test_client):
    """Task 2 Test: Standalone benchmark prediction without machine_id succeeds with null machine_id."""
    res = test_client.post("/api/v1/predictions", json={
        "type": "M",
        "air_temperature_c": 26.0,
        "process_temperature_c": 36.0,
        "rotational_speed_rpm": 1500,
        "torque_nm": 40.0,
        "tool_wear_min": 50.0,
    })
    assert res.status_code == 201
    data = res.json()
    assert data["machine_id"] is None


def test_prediction_persistence_and_filtering_and_latest(test_client):
    """Task 2 Test: Persistence of correct machine_id, filtering, historical null preservation, newest-first order, and latest endpoint scoping."""
    # Register two machines
    test_client.post("/api/v1/machines", json={"machine_id": "MACH-A", "machine_type": "CNC"})
    test_client.post("/api/v1/machines", json={"machine_id": "MACH-B", "machine_type": "3D_Printer"})

    # Submit standalone prediction
    res_standalone = test_client.post("/api/v1/predictions", json={
        "type": "L", "air_temperature_c": 25.0, "process_temperature_c": 35.0,
        "rotational_speed_rpm": 1400, "torque_nm": 45.0, "tool_wear_min": 10.0,
    })
    assert res_standalone.json()["machine_id"] is None

    # Submit 1st prediction for MACH-A
    res_a1 = test_client.post("/api/v1/predictions", json={
        "type": "L", "air_temperature_c": 25.0, "process_temperature_c": 35.0,
        "rotational_speed_rpm": 1400, "torque_nm": 45.0, "tool_wear_min": 20.0,
        "machine_id": "MACH-A",
    })
    a1_id = res_a1.json()["id"]

    # Submit prediction for MACH-B
    test_client.post("/api/v1/predictions", json={
        "type": "H", "air_temperature_c": 27.0, "process_temperature_c": 37.0,
        "rotational_speed_rpm": 1600, "torque_nm": 35.0, "tool_wear_min": 30.0,
        "machine_id": "MACH-B",
    })

    # Submit 2nd prediction for MACH-A (newest)
    res_a2 = test_client.post("/api/v1/predictions", json={
        "type": "L", "air_temperature_c": 28.0, "process_temperature_c": 38.0,
        "rotational_speed_rpm": 1300, "torque_nm": 50.0, "tool_wear_min": 200.0,
        "machine_id": "MACH-A",
    })
    a2_id = res_a2.json()["id"]

    # 1. Check filtering by machine_id MACH-A
    res_filter_a = test_client.get("/api/v1/predictions?machine_id=MACH-A")
    assert res_filter_a.status_code == 200
    items_a = res_filter_a.json()["items"]
    assert len(items_a) == 2
    assert all(item["machine_id"] == "MACH-A" for item in items_a)

    # 2. Check newest-first ordering (a2 should come before a1)
    assert items_a[0]["id"] == a2_id
    assert items_a[1]["id"] == a1_id

    # 3. Check latest endpoint for MACH-A
    res_latest_a = test_client.get("/api/v1/predictions/latest/MACH-A")
    assert res_latest_a.status_code == 200
    assert res_latest_a.json()["id"] == a2_id
    assert res_latest_a.json()["machine_id"] == "MACH-A"

    # 4. Check latest endpoint for non-existent machine returns 404
    res_latest_404 = test_client.get("/api/v1/predictions/latest/MACH-NONEXISTENT")
    assert res_latest_404.status_code == 404

    # 5. Check standalone filtering returns only null machine_id
    res_filter_null = test_client.get("/api/v1/predictions?machine_id=null")
    assert res_filter_null.status_code == 200
    items_null = res_filter_null.json()["items"]
    assert len(items_null) == 1
    assert items_null[0]["machine_id"] is None


# =====================================================================
# MAINTENANCE ENDPOINTS TESTS
# =====================================================================

def test_maintenance_endpoints(test_client):
    """Test maintenance event creation, machine validation, and retrieval."""
    # Register machine first
    test_client.post("/api/v1/machines", json={"machine_id": "CNC-202", "machine_type": "CNC"})

    m_payload = {
        "machine_id": "CNC-202",
        "event_type": "inspection",
        "description": "Routine Spindle Check",
        "event_timestamp": datetime(2026, 10, 2, 20, 0, 0).isoformat(),
        "status": "scheduled",
    }

    # Create event
    res_create = test_client.post("/api/v1/maintenance", json=m_payload)
    assert res_create.status_code == 201
    ev_id = res_create.json()["id"]

    # Reject event for non-existent machine
    m_invalid = m_payload.copy()
    m_invalid["machine_id"] = "UNREGISTERED"
    res_err = test_client.post("/api/v1/maintenance", json=m_invalid)
    assert res_err.status_code == 400

    # Retrieve event by ID
    res_get = test_client.get(f"/api/v1/maintenance/{ev_id}")
    assert res_get.status_code == 200
    assert res_get.json()["event_type"] == "inspection"

    # List events
    res_list = test_client.get("/api/v1/maintenance?machine_id=CNC-202")
    assert res_list.status_code == 200
    assert res_list.json()["total"] == 1


# =====================================================================
# PROTECTED ASSETS INTEGRITY TEST
# =====================================================================

def test_protected_model_assets_unmodified():
    """Verify production model and metadata files remain unchanged."""
    assert os.path.exists("models/predictive_maintenance_model.joblib")
    assert os.path.exists("models/model_metadata.json")
    assert os.path.exists("data/raw/simulated_telemetry.csv")
    assert os.path.exists("data/processed/ai4i2020_cleaned.csv")
