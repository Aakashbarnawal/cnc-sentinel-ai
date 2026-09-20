"""Shared sensor telemetry schema definitions and validation logic.

This module defines Pydantic v2 data models for the predictive maintenance system:
- CoreSensorData: The baseline 8 core telemetry fields.
- SensorData: The full 12-field schema including simulator extension fields.

Ground Truth & Data Leakage Rule:
`health_index` and `scenario` are simulator ground truth labels ONLY.
They MUST NOT be used as input features for predictive machine learning models.
"""

from datetime import datetime
from typing import Dict, Any, List, Set, Literal, Tuple, Optional
from pydantic import BaseModel, Field, field_validator, ConfigDict

# Allowed simulator scenario states
ALLOWED_SCENARIOS: Set[str] = {"normal", "degrading", "near_failure"}

# Allowed machine types
ALLOWED_MACHINE_TYPES: Set[str] = {"CNC", "3D_Printer"}

# Configurable validation limits (Data quality bounds, NOT certified safety thresholds)
DEFAULT_VALIDATION_LIMITS: Dict[str, Dict[str, float]] = {
    "temp": {"min": -20.0, "max": 200.0},
    "vibration": {"min": 0.0, "max": 100.0},
    "current": {"min": 0.0, "max": 200.0},
    "rpm": {"min": 0, "max": 50000},
    "hours": {"min": 0.0, "max": 100000.0},
    "workload": {"min": 0.0, "max": 100.0},
    "tool_wear": {"min": 0.0, "max": 100.0},
    "health_index": {"min": 0.0, "max": 100.0},
}


class CoreSensorData(BaseModel):
    """Core telemetry schema (First 8 fields).
    
    Represents standard raw telemetry collected from physical or simulated sensors.
    """
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    # Core Field 1: machine_id (string)
    machine_id: str = Field(..., description="Unique identifier for the machine equipment")

    # Core Field 2: timestamp (datetime)
    timestamp: datetime = Field(..., description="UTC timestamp of the telemetry reading")

    # Core Field 3: machine_type (string)
    machine_type: str = Field(..., description="Machine type classification ('CNC' or '3D_Printer')")

    # Core Field 4: temp (float)
    temp: float = Field(..., description="Operating temperature in degrees Celsius (°C)")

    # Core Field 5: vibration (float)
    vibration: float = Field(..., description="Vibration RMS velocity in mm/s")

    # Core Field 6: current (float)
    current: float = Field(..., description="Electrical current draw in Amperes (A)")

    # Core Field 7: rpm (integer)
    rpm: int = Field(..., description="Spindle or motor speed in RPM")

    # Core Field 8: hours (float)
    hours: float = Field(..., description="Cumulative operating hours")

    @field_validator("machine_type")
    @classmethod
    def validate_machine_type(cls, value: str) -> str:
        """Validate machine type against allowed types."""
        if value not in ALLOWED_MACHINE_TYPES:
            raise ValueError(f"Invalid machine_type '{value}'. Must be one of {sorted(list(ALLOWED_MACHINE_TYPES))}")
        return value

    @field_validator("temp")
    @classmethod
    def validate_temp(cls, value: float) -> float:
        """Validate temperature against operational limits."""
        limits = DEFAULT_VALIDATION_LIMITS["temp"]
        if not (limits["min"] <= value <= limits["max"]):
            raise ValueError(f"temp value {value} °C is outside operational limits [{limits['min']}, {limits['max']}]")
        return value

    @field_validator("vibration")
    @classmethod
    def validate_vibration(cls, value: float) -> float:
        """Validate vibration against operational limits."""
        limits = DEFAULT_VALIDATION_LIMITS["vibration"]
        if not (limits["min"] <= value <= limits["max"]):
            raise ValueError(f"vibration value {value} mm/s is outside operational limits [{limits['min']}, {limits['max']}]")
        return value

    @field_validator("current")
    @classmethod
    def validate_current(cls, value: float) -> float:
        """Validate electrical current against operational limits."""
        limits = DEFAULT_VALIDATION_LIMITS["current"]
        if not (limits["min"] <= value <= limits["max"]):
            raise ValueError(f"current value {value} A is outside operational limits [{limits['min']}, {limits['max']}]")
        return value

    @field_validator("rpm")
    @classmethod
    def validate_rpm(cls, value: int) -> int:
        """Validate RPM against operational limits."""
        limits = DEFAULT_VALIDATION_LIMITS["rpm"]
        if not (limits["min"] <= value <= limits["max"]):
            raise ValueError(f"rpm value {value} is outside operational limits [{limits['min']}, {limits['max']}]")
        return value

    @field_validator("hours")
    @classmethod
    def validate_hours(cls, value: float) -> float:
        """Validate operating hours."""
        limits = DEFAULT_VALIDATION_LIMITS["hours"]
        if not (limits["min"] <= value <= limits["max"]):
            raise ValueError(f"hours value {value} is outside operational limits [{limits['min']}, {limits['max']}]")
        return value

    @classmethod
    def core_field_names(cls) -> List[str]:
        """Return the list of core schema field names in order."""
        return ["machine_id", "timestamp", "machine_type", "temp", "vibration", "current", "rpm", "hours"]


class SensorData(CoreSensorData):
    """Full telemetry schema including core fields and simulator extension fields (All 12 fields).
    
    Extension Fields (4 fields):
    - workload: Operational workload percentage (0-100%)
    - tool_wear: Tool wear index (0-100 or mm wear)
    - health_index: Simulator ground truth health score (0-100%) [GROUND TRUTH - DO NOT USE AS ML INPUT]
    - scenario: Simulator operational scenario state ('normal', 'degrading', 'near_failure') [GROUND TRUTH - DO NOT USE AS ML INPUT]
    """

    # Extension Field 9: workload (float)
    workload: float = Field(..., description="Operational workload percentage (0.0 to 100.0)")

    # Extension Field 10: tool_wear (float)
    tool_wear: float = Field(..., description="Tool wear metric (0.0 to 100.0)")

    # Extension Field 11: health_index (float) - GROUND TRUTH GROUND RULE
    health_index: float = Field(
        ...,
        description="Simulator ground truth health score (0.0=Failed to 100.0=Perfect). GROUND TRUTH: DO NOT USE AS ML FEATURE INPUT."
    )

    # Extension Field 12: scenario (string) - GROUND TRUTH GROUND RULE
    scenario: str = Field(
        ...,
        description="Simulator operational scenario ('normal', 'degrading', 'near_failure'). GROUND TRUTH: DO NOT USE AS ML FEATURE INPUT."
    )

    @field_validator("scenario")
    @classmethod
    def validate_scenario(cls, value: str) -> str:
        """Validate scenario state against allowed simulator scenarios."""
        if value not in ALLOWED_SCENARIOS:
            raise ValueError(f"Invalid scenario '{value}'. Allowed scenarios are: {sorted(list(ALLOWED_SCENARIOS))}")
        return value

    @field_validator("workload")
    @classmethod
    def validate_workload(cls, value: float) -> float:
        """Validate workload percentage."""
        limits = DEFAULT_VALIDATION_LIMITS["workload"]
        if not (limits["min"] <= value <= limits["max"]):
            raise ValueError(f"workload value {value} % is outside operational limits [{limits['min']}, {limits['max']}]")
        return value

    @field_validator("tool_wear")
    @classmethod
    def validate_tool_wear(cls, value: float) -> float:
        """Validate tool wear metric."""
        limits = DEFAULT_VALIDATION_LIMITS["tool_wear"]
        if not (limits["min"] <= value <= limits["max"]):
            raise ValueError(f"tool_wear value {value} is outside operational limits [{limits['min']}, {limits['max']}]")
        return value

    @field_validator("health_index")
    @classmethod
    def validate_health_index(cls, value: float) -> float:
        """Validate simulator health index score."""
        limits = DEFAULT_VALIDATION_LIMITS["health_index"]
        if not (limits["min"] <= value <= limits["max"]):
            raise ValueError(f"health_index value {value} % is outside operational limits [{limits['min']}, {limits['max']}]")
        return value

    @classmethod
    def all_field_names(cls) -> List[str]:
        """Return all 12 schema field names in canonical order."""
        return [
            "machine_id",
            "timestamp",
            "machine_type",
            "temp",
            "vibration",
            "current",
            "rpm",
            "hours",
            "workload",
            "tool_wear",
            "health_index",
            "scenario",
        ]

    @classmethod
    def extension_field_names(cls) -> List[str]:
        """Return the 4 extension field names."""
        return ["workload", "tool_wear", "health_index", "scenario"]

    @classmethod
    def predictive_feature_names(cls) -> List[str]:
        """Return input feature fields for predictive models, explicitly excluding ground truth target fields.
        
        Excludes: `health_index`, `scenario` (to prevent data leakage).
        Excludes: `machine_id`, `timestamp` (meta identifiers).
        """
        return ["temp", "vibration", "current", "rpm", "hours", "workload", "tool_wear"]

    @classmethod
    def ground_truth_field_names(cls) -> List[str]:
        """Return ground truth target fields reserved for simulator evaluation and loss metrics."""
        return ["health_index", "scenario"]


def validate_telemetry_dict(data: Dict[str, Any], require_full_schema: bool = True) -> Tuple[bool, Optional[str]]:
    """Utility function to validate a telemetry raw dictionary payload.
    
    Args:
        data: Dictionary of sensor telemetry data.
        require_full_schema: If True, validates against full 12-field SensorData schema.
                             If False, validates against baseline 8-field CoreSensorData schema.
    
    Returns:
        Tuple of (is_valid: bool, error_message: Optional[str])
    """
    try:
        if require_full_schema:
            SensorData.model_validate(data)
        else:
            CoreSensorData.model_validate(data)
        return True, None
    except Exception as e:
        return False, str(e)
