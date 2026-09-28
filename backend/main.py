"""FastAPI Backend Application for Predictive Maintenance System."""

import os
import sys
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, status, Query
from fastapi.middleware.cors import CORSMiddleware

# Import database connection
from database.connection import init_db, get_db, test_mongo_connection
from database.models import format_mongo_doc

# Import Pydantic schemas
from backend.schemas import (
    MachineCreate,
    MachineResponse,
    MachineListResponse,
    TelemetryCreate,
    TelemetryBatchCreate,
    TelemetryResponse,
    TelemetryListResponse,
    PredictionRequest,
    PredictionResponse,
    PredictionListResponse,
    MaintenanceCreate,
    MaintenanceResponse,
    MaintenanceListResponse,
    HealthResponse,
    ReadyResponse,
    ReportEmailRequest,
    ReportEmailResponse,
)

# Import backend service layers
from backend.services.telemetry_service import (
    register_machine,
    get_machines,
    get_machine_by_id,
    create_telemetry_reading,
    create_telemetry_batch,
    get_telemetry_readings,
    get_telemetry_by_id,
)
from backend.services.prediction_service import (
    load_production_model,
    predict_machine_failure,
    get_predictions,
    get_prediction_by_id,
    get_latest_prediction_for_machine,
)
from backend.services.maintenance_service import (
    create_maintenance_event,
    get_maintenance_events,
    get_maintenance_by_id,
)
from backend.services.telegram_service import (
    get_telegram_status,
    send_telegram_message,
)
from backend.services.email_service import (
    get_email_status,
    send_email_message,
    send_machine_email_alert,
    send_machine_health_report_email,
)
from backend.services.diagnostic_service import (
    evaluate_equipment_diagnostics,
)
from backend.services.simulation_manager import (
    simulation_manager,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI Lifespan context manager for database initialization and model pre-loading."""
    # 1. Initialize MongoDB Collections & Indexes
    try:
        init_db()
        from database.connection import get_mongo_db
        db = get_mongo_db()
        simulation_manager.ensure_virtual_machines_registered(db)
    except Exception as e:
        print(f"Warning: Database initialization error: {e}", file=sys.stderr)

    # 2. Pre-load Production ML Model into memory
    try:
        load_production_model()
    except Exception as e:
        print(f"Warning: Production ML model loading error: {e}", file=sys.stderr)

    yield

    # Cleanup background simulation manager
    try:
        simulation_manager.stop_simulation()
    except Exception:
        pass


app = FastAPI(
    title="CNC Sentinel AI — AI-Powered Predictive Maintenance & Machine Health Monitoring API",
    description="RESTful API for equipment registration, digital twin telemetry simulation, ML predictions, SHAP explainability, and Telegram/Email alerts.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    openapi_url="/openapi.json",
)

# Configure CORS Middleware for Local Development & Production Deployment
cors_origins_env = os.environ.get("CORS_ORIGINS", "")
if cors_origins_env.strip():
    if cors_origins_env.strip() == "*":
        allowed_origins = ["*"]
    else:
        allowed_origins = [orig.strip() for orig in cors_origins_env.split(",") if orig.strip()]
else:
    allowed_origins = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =====================================================================
# SYSTEM HEALTH & READINESS ENDPOINTS
# =====================================================================

@app.get("/health", response_model=HealthResponse, tags=["System"])
def health_check(db: Any = Depends(get_db)):
    """Check API and database connectivity status."""
    try:
        db.command("ping")
        db_status = "connected"
    except Exception:
        db_status = "disconnected"

    return HealthResponse(
        status="ok" if db_status == "connected" else "degraded",
        database=db_status,
        timestamp=datetime.utcnow(),
    )


@app.get("/ready", response_model=ReadyResponse, tags=["System"])
def readiness_check(db: Any = Depends(get_db)):
    """Check system readiness including ML model loading and database connection."""
    try:
        db.command("ping")
        db_status = "connected"
    except Exception:
        db_status = "disconnected"

    model_loaded = False
    model_name = "Unknown"
    threshold = 0.33
    try:
        model, metadata = load_production_model()
        model_loaded = (model is not None)
        model_name = metadata.get("model_name", "XGBoost")
        threshold = float(metadata.get("selected_threshold", 0.33))
    except Exception:
        pass

    is_ready = (db_status == "connected") and model_loaded

    return ReadyResponse(
        status="ready" if is_ready else "not_ready",
        model_loaded=model_loaded,
        model_name=model_name,
        threshold=threshold,
        database=db_status,
        timestamp=datetime.utcnow(),
    )


# =====================================================================
# MACHINE EQUIPMENT ENDPOINTS
# =====================================================================

@app.post("/api/v1/machines", response_model=MachineResponse, status_code=status.HTTP_201_CREATED, tags=["Machines"])
def register_machine_endpoint(data: MachineCreate, db: Any = Depends(get_db)):
    """Register new equipment machine."""
    try:
        return register_machine(data, db)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@app.get("/api/v1/machines", response_model=MachineListResponse, tags=["Machines"])
def list_machines_endpoint(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Any = Depends(get_db),
):
    """Retrieve paginated list of registered machines."""
    total, items = get_machines(db, limit=limit, offset=offset)
    return MachineListResponse(total=total, items=items)


@app.get("/api/v1/machines/{machine_id}", response_model=MachineResponse, tags=["Machines"])
def get_machine_endpoint(machine_id: str, db: Any = Depends(get_db)):
    """Retrieve single machine details by machine_id."""
    machine = get_machine_by_id(machine_id, db)
    if not machine:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Machine '{machine_id}' not found.")
    return machine


# =====================================================================
# TELEMETRY ENDPOINTS
# =====================================================================

@app.post("/api/v1/telemetry", response_model=TelemetryResponse, status_code=status.HTTP_201_CREATED, tags=["Telemetry"])
def create_telemetry_endpoint(data: TelemetryCreate, db: Any = Depends(get_db)):
    """Ingest and persist a single telemetry reading."""
    try:
        return create_telemetry_reading(data, db)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@app.post("/api/v1/telemetry/batch", response_model=List[TelemetryResponse], status_code=status.HTTP_201_CREATED, tags=["Telemetry"])
def create_telemetry_batch_endpoint(data: TelemetryBatchCreate, db: Any = Depends(get_db)):
    """Ingest a batch of telemetry readings inside a single atomic transaction."""
    try:
        return create_telemetry_batch(data, db)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@app.get("/api/v1/telemetry", response_model=TelemetryListResponse, tags=["Telemetry"])
def list_telemetry_endpoint(
    machine_id: Optional[str] = Query(None),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Any = Depends(get_db),
):
    """Query telemetry readings with optional filters and pagination."""
    total, items = get_telemetry_readings(
        db, machine_id=machine_id, start_time=start_time, end_time=end_time, limit=limit, offset=offset
    )
    return TelemetryListResponse(total=total, items=items)


@app.get("/api/v1/telemetry/{reading_id}", response_model=TelemetryResponse, tags=["Telemetry"])
def get_telemetry_reading_endpoint(reading_id: int, db: Any = Depends(get_db)):
    """Retrieve single telemetry reading by ID."""
    reading = get_telemetry_by_id(reading_id, db)
    if not reading:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Telemetry reading with ID {reading_id} not found.")
    return reading


# =====================================================================
# FAILURE PREDICTION ENDPOINTS (AI4I Benchmark Classifier)
# =====================================================================

@app.post("/api/v1/predictions", response_model=PredictionResponse, status_code=status.HTTP_201_CREATED, tags=["Predictions"])
def create_prediction_endpoint(data: PredictionRequest, db: Any = Depends(get_db)):
    """Execute ML machine failure prediction using production model and persist prediction history."""
    try:
        return predict_machine_failure(data, db)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Inference error: {str(e)}")


@app.get("/api/v1/predictions", response_model=PredictionListResponse, tags=["Predictions"])
def list_predictions_endpoint(
    machine_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Any = Depends(get_db),
):
    """List saved prediction records with optional machine filter and pagination."""
    total, items = get_predictions(db, machine_id=machine_id, limit=limit, offset=offset)
    return PredictionListResponse(total=total, items=items)


@app.get("/api/v1/predictions/latest/{machine_id}", response_model=PredictionResponse, tags=["Predictions"])
def get_latest_prediction_endpoint(machine_id: str, db: Any = Depends(get_db)):
    """Retrieve the single latest prediction record for a specific machine."""
    record = get_latest_prediction_for_machine(db, machine_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No predictions found for machine '{machine_id}'.")
    return record


@app.get("/api/v1/predictions/{prediction_id}", response_model=PredictionResponse, tags=["Predictions"])
def get_prediction_endpoint(prediction_id: int, db: Any = Depends(get_db)):
    """Retrieve single prediction record by ID."""
    record = get_prediction_by_id(db, prediction_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Prediction record with ID {prediction_id} not found.")
    return record


@app.post("/api/v1/predictions/explain", tags=["Predictions"])
def explain_prediction_endpoint(data: PredictionRequest):
    """Generate local SHAP explanation for a prediction request."""
    try:
        from ml.explainability import explain_single_prediction
        input_dict = {
            "type": data.type,
            "air_temperature_c": data.air_temperature_c,
            "process_temperature_c": data.process_temperature_c,
            "rotational_speed_rpm": data.rotational_speed_rpm,
            "torque_nm": data.torque_nm,
            "tool_wear_min": data.tool_wear_min,
        }
        return explain_single_prediction(input_dict)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Explanation error: {str(e)}")


# =====================================================================
# MAINTENANCE EVENT ENDPOINTS
# =====================================================================

@app.post("/api/v1/maintenance", response_model=MaintenanceResponse, status_code=status.HTTP_201_CREATED, tags=["Maintenance"])
def create_maintenance_endpoint(data: MaintenanceCreate, db: Any = Depends(get_db)):
    """Log or schedule a machine maintenance event."""
    try:
        return create_maintenance_event(data, db)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@app.get("/api/v1/maintenance", response_model=MaintenanceListResponse, tags=["Maintenance"])
def list_maintenance_endpoint(
    machine_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Any = Depends(get_db),
):
    """Retrieve paginated list of maintenance events."""
    total, items = get_maintenance_events(db, machine_id=machine_id, limit=limit, offset=offset)
    return MaintenanceListResponse(total=total, items=items)


@app.get("/api/v1/maintenance/{event_id}", response_model=MaintenanceResponse, tags=["Maintenance"])
def get_maintenance_endpoint(event_id: int, db: Any = Depends(get_db)):
    """Retrieve single maintenance event by ID."""
    event = get_maintenance_by_id(event_id, db)
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Maintenance event with ID {event_id} not found.")
    return event


# =====================================================================
# =====================================================================
# NOTIFICATION ENDPOINTS (EMAIL & TELEGRAM)
# =====================================================================

@app.get("/api/v1/notifications/status", tags=["Notifications"])
def get_notifications_status_endpoint():
    """Get status overview for Email (SMTP) and Telegram notification integrations."""
    return {
        "email": get_email_status(),
        "telegram": get_telegram_status(),
        "timestamp": datetime.now(timezone.utc),
    }


@app.post("/api/v1/notifications/test-email", tags=["Notifications"])
def test_email_endpoint(payload: Optional[Dict[str, Any]] = None):
    """Safely send a user-triggered test email notification."""
    recipient_override = payload.get("recipient_email") if payload else None

    success, message = send_machine_email_alert(
        machine_id="TEST-CNC-001",
        equipment_type="CNC",
        severity="WARNING",
        scenario="TEST_NOTIFICATION",
        temp=72.5,
        vibration=4.25,
        current=24.0,
        rpm=11500,
        failure_probability=0.485,
        health_index=62.0,
        suspected_issue="User-Triggered System Delivery Verification Test",
        recommended_action="Verification test email delivered successfully. System notification pipeline operational.",
        recipient_override=recipient_override,
        force=True,
    )
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
    return {"success": True, "message": message}


@app.post("/api/v1/reports/email", response_model=ReportEmailResponse, tags=["Reports"])
def send_health_report_endpoint(data: ReportEmailRequest, db: Any = Depends(get_db)):
    """Generate and deliver an official CNC Sentinel AI machine health report via email."""
    success, message = send_machine_health_report_email(
        machine_id=data.machine_id,
        recipient_email=data.recipient_email,
        db=db,
    )
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
    return ReportEmailResponse(
        success=True,
        message=message,
        machine_id=data.machine_id,
        recipient_email=data.recipient_email,
        timestamp=datetime.now(timezone.utc),
    )


@app.get("/api/v1/telegram/status", tags=["Telegram"])
def get_telegram_status_endpoint():
    """Get Telegram integration configuration status without secrets."""
    return get_telegram_status()


@app.post("/api/v1/telegram/test", tags=["Telegram"])
def test_telegram_endpoint():
    """Send a safe test message to Telegram Bot."""
    msg = (
        "<b>CNC SENTINEL AI — TEST ALERT</b>\n\n"
        "This is a test notification from the CNC Sentinel AI Platform backend.\n"
        "Status: System Operational\n"
        f"Timestamp: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
    )
    success, message = send_telegram_message(msg, force=True)
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
    return {"success": True, "message": message}


# =====================================================================
# VIRTUAL MACHINE DIGITAL TWIN SIMULATOR ENDPOINTS
# =====================================================================

@app.get("/api/v1/simulator/status", tags=["Simulator"])
def get_simulator_status_endpoint():
    """Get current status of background virtual machine simulator."""
    return simulation_manager.get_status()


@app.post("/api/v1/simulator/start", tags=["Simulator"])
async def start_simulator_endpoint(db: Any = Depends(get_db)):
    """Start or resume live background virtual machine simulation."""
    await simulation_manager.start_simulation(db)
    return {"success": True, "message": "Simulation manager started.", "status": simulation_manager.get_status()}


@app.post("/api/v1/simulator/stop", tags=["Simulator"])
async def stop_simulator_endpoint():
    """Stop live background virtual machine simulation."""
    simulation_manager.stop_simulation()
    return {"success": True, "message": "Simulation manager stopped.", "status": simulation_manager.get_status()}


@app.post("/api/v1/simulator/scenario", tags=["Simulator"])
def set_simulator_scenario_endpoint(payload: Dict[str, Any]):
    """Set operational scenario for a virtual machine ('normal', 'degrading', 'near_failure', 'sensor_anomaly')."""
    machine_id = payload.get("machine_id")
    scenario = payload.get("scenario")
    if not machine_id or not scenario:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Both 'machine_id' and 'scenario' are required.")
    
    updated = simulation_manager.set_machine_scenario(machine_id, scenario)
    if not updated:
        equipment_category = payload.get("equipment_category", "CNC")
        simulation_manager.add_virtual_machine(machine_id, equipment_category, scenario)

    return {"success": True, "machine_id": machine_id, "scenario": scenario}


@app.post("/api/v1/simulator/speed", tags=["Simulator"])
def set_simulator_speed_endpoint(payload: Dict[str, Any]):
    """Set simulation speed factor (e.g. 0.5, 1.0, 2.0, 5.0)."""
    speed_factor = payload.get("speed_factor", 1.0)
    simulation_manager.set_speed(speed_factor)
    return {"success": True, "speed_factor": simulation_manager.speed_factor}


# =====================================================================
# DIAGNOSTICS ENDPOINTS
# =====================================================================

@app.post("/api/v1/diagnostics", tags=["Diagnostics"])
def evaluate_diagnostics_endpoint(payload: Dict[str, Any]):
    """Evaluate equipment-aware diagnostic rules for given sensor readings."""
    equipment_type = payload.get("equipment_type", payload.get("machine_type", "CNC"))
    temp = float(payload.get("temp", 0.0))
    vibration = float(payload.get("vibration", 0.0))
    current = float(payload.get("current", 0.0))
    rpm = int(payload.get("rpm", 0))
    tool_wear = float(payload.get("tool_wear", 0.0))
    failure_probability = payload.get("failure_probability")

    return evaluate_equipment_diagnostics(
        equipment_type=equipment_type,
        temp=temp,
        vibration=vibration,
        current=current,
        rpm=rpm,
        tool_wear=tool_wear,
        failure_probability=failure_probability,
    )


if __name__ == "__main__":
    import uvicorn
    server_host = os.environ.get("HOST", "0.0.0.0")
    server_port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("backend.main:app", host=server_host, port=server_port, reload=False)

