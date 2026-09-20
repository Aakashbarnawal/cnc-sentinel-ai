"""Config package for Predictive Maintenance System."""
from config.schema import (
    CoreSensorData,
    SensorData,
    ALLOWED_SCENARIOS,
    ALLOWED_MACHINE_TYPES,
    DEFAULT_VALIDATION_LIMITS,
    validate_telemetry_dict,
)

__all__ = [
    "CoreSensorData",
    "SensorData",
    "ALLOWED_SCENARIOS",
    "ALLOWED_MACHINE_TYPES",
    "DEFAULT_VALIDATION_LIMITS",
    "validate_telemetry_dict",
]
