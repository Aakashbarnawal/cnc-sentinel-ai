"""Data Models and Document Utilities for MongoDB and Relational Persistence."""

from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    Text,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Machine(Base):
    """Registered Equipment Machine Entity (CNC Milling Machines and 3D Printers)."""
    __tablename__ = "machines"

    id = Column(Integer, primary_key=True, autoincrement=True)
    machine_id = Column(String(50), unique=True, index=True, nullable=False)
    machine_type = Column(String(50), nullable=False)  # 'CNC' or '3D_Printer'
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<Machine(machine_id='{self.machine_id}', machine_type='{self.machine_type}')>"


class TelemetryReading(Base):
    """Persisted Sensor Telemetry Reading from Simulator or Equipment Ingestion."""
    __tablename__ = "telemetry_readings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    machine_id = Column(String(50), index=True, nullable=False)
    timestamp = Column(DateTime, index=True, nullable=False)
    machine_type = Column(String(50), nullable=True)
    temp = Column(Float, nullable=False)
    vibration = Column(Float, nullable=False)
    current = Column(Float, nullable=False)
    rpm = Column(Integer, nullable=False)
    hours = Column(Float, nullable=False)
    workload = Column(Float, nullable=False)
    tool_wear = Column(Float, nullable=False)
    health_index = Column(Float, nullable=True)  # Ground truth if available
    scenario = Column(String(50), nullable=True)  # Ground truth if available
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("machine_id", "timestamp", name="uix_machine_timestamp"),
        Index("idx_telemetry_machine_time", "machine_id", "timestamp"),
    )

    def __repr__(self) -> str:
        return f"<TelemetryReading(machine_id='{self.machine_id}', timestamp='{self.timestamp}', temp={self.temp})>"


class PredictionRecord(Base):
    """Persisted ML Model Inference Prediction Record."""
    __tablename__ = "prediction_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    machine_id = Column(String(50), index=True, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    failure_probability = Column(Float, nullable=False)
    classification_threshold = Column(Float, nullable=False)
    predicted_class = Column(Integer, nullable=False)  # 0 or 1
    predicted_label = Column(String(50), nullable=False)  # 'Normal Operation' or 'Machine Failure'
    model_name = Column(String(100), nullable=False)
    input_features_json = Column(Text, nullable=False)
    model_metadata_version = Column(String(50), nullable=True)

    def __repr__(self) -> str:
        return f"<PredictionRecord(id={self.id}, probability={self.failure_probability:.4f}, predicted_class={self.predicted_class})>"


class MaintenanceEvent(Base):
    """Persisted Equipment Maintenance Event."""
    __tablename__ = "maintenance_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    machine_id = Column(String(50), index=True, nullable=False)
    event_type = Column(String(50), nullable=False)  # 'inspection', 'maintenance', 'repair'
    description = Column(String(500), nullable=True)
    event_timestamp = Column(DateTime, nullable=False)
    status = Column(String(50), nullable=False)  # 'scheduled', 'in_progress', 'completed'
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<MaintenanceEvent(machine_id='{self.machine_id}', type='{self.event_type}', status='{self.status}')>"


# =====================================================================
# MONGODB DOCUMENT SERIALIZATION & SEQUENCE UTILITIES
# =====================================================================

def get_next_sequence_val(db: Any, sequence_name: str) -> int:
    """Generate sequential integer ID for MongoDB collection documents."""
    counters = db["counters"]
    res = counters.find_one_and_update(
        {"_id": sequence_name},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=True,
    )
    if isinstance(res, dict) and "seq" in res:
        return res["seq"]
    return 1


def format_mongo_doc(doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Format MongoDB document dictionary for Pydantic response models, mapping _id to id."""
    if not doc:
        return None
    res = dict(doc)
    if "_id" in res:
        if "id" not in res:
            res["id"] = res.get("id") or str(res["_id"])
        del res["_id"]
    return res
