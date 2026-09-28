"""Pydantic v2 Request and Response Validation Schemas for FastAPI Backend."""

import math
from datetime import datetime
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, field_validator, ConfigDict

from config.schema import (
    ALLOWED_MACHINE_TYPES,
    ALLOWED_SCENARIOS,
    DEFAULT_VALIDATION_LIMITS,
)

# Allowed categorical types for AI4I prediction model
ALLOWED_PRODUCT_TYPES = {"L", "M", "H"}
ALLOWED_EVENT_TYPES = {"inspection", "maintenance", "repair"}
ALLOWED_EVENT_STATUSES = {"scheduled", "in_progress", "completed"}


# =====================================================================
# MACHINE SCHEMAS
# =====================================================================

class MachineCreate(BaseModel):
    """Schema for registering a new machine equipment."""
    machine_id: str = Field(..., min_length=2, max_length=50, description="Unique machine identifier (e.g. 'CNC-001')")
    machine_type: str = Field(..., description="Machine type ('CNC' or '3D_Printer')")

    @field_validator("machine_type")
    @classmethod
    def validate_type(cls, value: str) -> str:
        if value not in ALLOWED_MACHINE_TYPES:
            raise ValueError(f"Invalid machine_type '{value}'. Allowed: {sorted(list(ALLOWED_MACHINE_TYPES))}")
        return value


class MachineResponse(BaseModel):
    """Schema for machine response payload."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    machine_id: str
    machine_type: str
    created_at: datetime


class MachineListResponse(BaseModel):
    """Paginated list response for machines."""
    total: int
    items: List[MachineResponse]


# =====================================================================
# TELEMETRY SCHEMAS
# =====================================================================

class TelemetryCreate(BaseModel):
    """Schema for persisting synthetic or real equipment sensor telemetry."""
    machine_id: str = Field(..., min_length=2, max_length=50)
    timestamp: datetime = Field(...)
    machine_type: str = Field(...)
    temp: float = Field(...)
    vibration: float = Field(...)
    current: float = Field(...)
    rpm: int = Field(...)
    hours: float = Field(...)
    workload: float = Field(...)
    tool_wear: float = Field(...)
    health_index: Optional[float] = Field(None)
    scenario: Optional[str] = Field(None)

    @field_validator("machine_type")
    @classmethod
    def validate_type(cls, value: str) -> str:
        if value not in ALLOWED_MACHINE_TYPES:
            raise ValueError(f"Invalid machine_type '{value}'. Allowed: {sorted(list(ALLOWED_MACHINE_TYPES))}")
        return value

    @field_validator("scenario")
    @classmethod
    def validate_scenario(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and value not in ALLOWED_SCENARIOS:
            raise ValueError(f"Invalid scenario '{value}'. Allowed: {sorted(list(ALLOWED_SCENARIOS))}")
        return value

    @field_validator("temp", "vibration", "current", "rpm", "hours", "workload", "tool_wear")
    @classmethod
    def validate_finite_numbers(cls, value: Any) -> Any:
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            raise ValueError("Numeric telemetry values must be finite and not NaN/Inf")
        return value

    @field_validator("temp")
    @classmethod
    def validate_temp_range(cls, value: float) -> float:
        limits = DEFAULT_VALIDATION_LIMITS["temp"]
        if not (limits["min"] <= value <= limits["max"]):
            raise ValueError(f"temp value {value} °C is outside operational limits [{limits['min']}, {limits['max']}]")
        return value

    @field_validator("vibration")
    @classmethod
    def validate_vibration_range(cls, value: float) -> float:
        limits = DEFAULT_VALIDATION_LIMITS["vibration"]
        if not (limits["min"] <= value <= limits["max"]):
            raise ValueError(f"vibration value {value} mm/s is outside operational limits [{limits['min']}, {limits['max']}]")
        return value

    @field_validator("current")
    @classmethod
    def validate_current_range(cls, value: float) -> float:
        limits = DEFAULT_VALIDATION_LIMITS["current"]
        if not (limits["min"] <= value <= limits["max"]):
            raise ValueError(f"current value {value} A is outside operational limits [{limits['min']}, {limits['max']}]")
        return value


class TelemetryBatchCreate(BaseModel):
    """Schema for batch telemetry ingestion."""
    readings: List[TelemetryCreate] = Field(..., min_length=1, max_length=1000)


class TelemetryResponse(BaseModel):
    """Schema for telemetry response payload."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    machine_id: str
    timestamp: datetime
    machine_type: str
    temp: float
    vibration: float
    current: float
    rpm: int
    hours: float
    workload: float
    tool_wear: float
    health_index: Optional[float] = None
    scenario: Optional[str] = None
    created_at: datetime


class TelemetryListResponse(BaseModel):
    """Paginated list response for telemetry readings."""
    total: int
    items: List[TelemetryResponse]


# =====================================================================
# PREDICTION SCHEMAS (AI4I Benchmark Classifier Features)
# =====================================================================

class PredictionRequest(BaseModel):
    """Schema for machine failure prediction requests.
    
    Accepts exact feature schema expected by the trained ML production model.
    """
    type: str = Field(..., description="Product variant quality classification ('L', 'M', or 'H')")
    air_temperature_c: float = Field(..., description="Air temperature in °C")
    process_temperature_c: float = Field(..., description="Process temperature in °C")
    rotational_speed_rpm: int = Field(..., description="Rotational speed in RPM")
    torque_nm: float = Field(..., description="Torque in Nm")
    tool_wear_min: float = Field(..., description="Cumulative tool wear in minutes")
    machine_id: Optional[str] = Field(None, description="Optional associated machine ID")

    @field_validator("type")
    @classmethod
    def validate_type(cls, value: str) -> str:
        if value not in ALLOWED_PRODUCT_TYPES:
            raise ValueError(f"Invalid type '{value}'. Must be one of {sorted(list(ALLOWED_PRODUCT_TYPES))}")
        return value

    @field_validator("air_temperature_c", "process_temperature_c", "torque_nm", "tool_wear_min")
    @classmethod
    def validate_finite_and_ranges(cls, value: float) -> float:
        if math.isnan(value) or math.isinf(value):
            raise ValueError("Numeric feature inputs must be finite numbers (no NaN or Inf)")
        return value


class PredictionResponse(BaseModel):
    """Schema for failure prediction response payload."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    machine_id: Optional[str] = None
    failure_probability: float
    classification_threshold: float
    predicted_class: int
    predicted_label: str
    model_name: str
    input_features_json: str
    created_at: datetime


class PredictionListResponse(BaseModel):
    """Paginated list response for prediction history."""
    total: int
    items: List[PredictionResponse]


# =====================================================================
# MAINTENANCE SCHEMAS
# =====================================================================

class MaintenanceCreate(BaseModel):
    """Schema for logging a machine maintenance event."""
    machine_id: str = Field(..., min_length=2, max_length=50)
    event_type: str = Field(..., description="'inspection', 'maintenance', or 'repair'")
    description: Optional[str] = Field(None, max_length=500)
    event_timestamp: datetime = Field(...)
    status: str = Field(..., description="'scheduled', 'in_progress', or 'completed'")

    @field_validator("event_type")
    @classmethod
    def validate_event_type(cls, value: str) -> str:
        if value not in ALLOWED_EVENT_TYPES:
            raise ValueError(f"Invalid event_type '{value}'. Allowed: {sorted(list(ALLOWED_EVENT_TYPES))}")
        return value

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        if value not in ALLOWED_EVENT_STATUSES:
            raise ValueError(f"Invalid status '{value}'. Allowed: {sorted(list(ALLOWED_EVENT_STATUSES))}")
        return value


class MaintenanceResponse(BaseModel):
    """Schema for maintenance event response payload."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    machine_id: str
    event_type: str
    description: Optional[str] = None
    event_timestamp: datetime
    status: str
    created_at: datetime


class MaintenanceListResponse(BaseModel):
    """Paginated list response for maintenance events."""
    total: int
    items: List[MaintenanceResponse]


# =====================================================================
# SYSTEM HEALTH & READINESS SCHEMAS
# =====================================================================

class HealthResponse(BaseModel):
    """Schema for health status endpoint."""
    status: str
    database: str
    timestamp: datetime


class ReadyResponse(BaseModel):
    """Schema for readiness status endpoint."""
    status: str
    model_loaded: bool
    model_name: str
    threshold: float
    database: str
    timestamp: datetime


# =====================================================================
# REPORT NOTIFICATION SCHEMAS
# =====================================================================

class ReportEmailRequest(BaseModel):
    """Schema for sending an automated machine health report via email."""
    machine_id: str = Field(..., min_length=2, max_length=50, description="Machine ID to generate health report for")
    recipient_email: str = Field(..., min_length=5, max_length=120, description="Destination recipient email address")

    @field_validator("recipient_email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        clean = v.strip()
        if "@" not in clean or "." not in clean:
            raise ValueError("Valid email address required.")
        return clean


class ReportEmailResponse(BaseModel):
    """Schema for health report email response."""
    success: bool
    message: str
    machine_id: str
    recipient_email: str
    timestamp: datetime

