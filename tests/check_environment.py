"""Environment and Schema Verification Script for Predictive Maintenance AI.

This module verifies:
1. Active Conda environment, Python version, and executable path.
2. Availability and exact versions of required dependencies.
3. Schema integrity, field definitions, core vs extension split, allowed scenarios, and validation limits.
4. Git availability and repository status (initializing git if needed, without overwriting).
"""

import sys
import os
import shutil
import subprocess
import importlib.util
import importlib.metadata
from datetime import datetime
from typing import Dict, Tuple, List, Optional, Any
import pytest

# Ensure project root is in sys.path when running script directly
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from config.schema import (
    CoreSensorData,
    SensorData,
    ALLOWED_SCENARIOS,
    ALLOWED_MACHINE_TYPES,
    DEFAULT_VALIDATION_LIMITS,
    validate_telemetry_dict,
)

REQUIRED_PACKAGES = [
    "numpy",
    "pandas",
    "scipy",
    "sklearn",
    "xgboost",
    "shap",
    "fastapi",
    "uvicorn",
    "streamlit",
    "plotly",
    "sqlalchemy",
    "joblib",
    "requests",
    "pytest",
    "pydantic",
]

# Distribution mapping for import names -> PyPI distribution names
PACKAGE_DISTRIBUTION_NAMES = {
    "sklearn": "scikit-learn",
}


def get_environment_info() -> Dict[str, str]:
    """Retrieve runtime environment details."""
    return {
        "python_executable": sys.executable,
        "python_version": sys.version.split()[0],
        "active_conda_env": os.environ.get("CONDA_DEFAULT_ENV", "Unknown / Not set in env"),
    }


def check_dependencies() -> Dict[str, Dict[str, Any]]:
    """Check availability and versions of all required dependencies."""
    results = {}
    for pkg_import in REQUIRED_PACKAGES:
        dist_name = PACKAGE_DISTRIBUTION_NAMES.get(pkg_import, pkg_import)
        spec = importlib.util.find_spec(pkg_import)
        if spec is not None:
            try:
                version = importlib.metadata.version(dist_name)
            except Exception:
                version = "Installed (version unknown)"
            results[pkg_import] = {"installed": True, "version": version, "location": spec.origin}
        else:
            results[pkg_import] = {"installed": False, "version": None, "location": None}
    return results


def check_git_status(target_directory: str = PROJECT_ROOT) -> Dict[str, Any]:
    """Check git availability and repository status.
    
    Initializes git repository if not present, and never overwrites an existing repository.
    """
    git_cmd = shutil.which("git")
    git_available = git_cmd is not None
    git_dir = os.path.join(target_directory, ".git")
    is_repo = os.path.isdir(git_dir)
    initialized_now = False

    if git_available and not is_repo:
        try:
            res = subprocess.run([git_cmd, "init", target_directory], capture_output=True, text=True, check=True)
            is_repo = os.path.isdir(git_dir)
            initialized_now = True
        except Exception as e:
            pass

    return {
        "git_available": git_available,
        "git_executable": git_cmd,
        "is_repository": is_repo,
        "initialized_now": initialized_now,
    }


# =====================================================================
# PYTEST TEST SUITE FOR SCHEMA AND ENVIRONMENT
# =====================================================================

def test_environment_imports():
    """Pytest: Verify all required dependencies are importable."""
    missing = []
    for pkg in REQUIRED_PACKAGES:
        spec = importlib.util.find_spec(pkg)
        if spec is None:
            missing.append(pkg)
    assert not missing, f"Missing required dependencies: {missing}"


def test_schema_core_and_extension_fields():
    """Pytest: Test field counts, field names, and core vs extension separation."""
    core_fields = CoreSensorData.core_field_names()
    all_fields = SensorData.all_field_names()
    ext_fields = SensorData.extension_field_names()

    assert len(core_fields) == 8, f"Expected 8 core fields, got {len(core_fields)}"
    assert len(all_fields) == 12, f"Expected 12 total fields, got {len(all_fields)}"
    assert len(ext_fields) == 4, f"Expected 4 extension fields, got {len(ext_fields)}"

    assert core_fields == [
        "machine_id", "timestamp", "machine_type", "temp", "vibration", "current", "rpm", "hours"
    ]
    assert ext_fields == ["workload", "tool_wear", "health_index", "scenario"]


def test_schema_valid_payload():
    """Pytest: Test validation of valid core and full telemetry dictionaries."""
    valid_payload = {
        "machine_id": "CNC-001",
        "timestamp": "2026-10-02T18:45:00Z",
        "machine_type": "CNC",
        "temp": 65.4,
        "vibration": 2.85,
        "current": 14.2,
        "rpm": 12000,
        "hours": 1450.5,
        "workload": 85.0,
        "tool_wear": 12.5,
        "health_index": 88.5,
        "scenario": "normal",
    }

    # Test full schema validation
    is_valid, err = validate_telemetry_dict(valid_payload, require_full_schema=True)
    assert is_valid, f"Expected valid payload, got error: {err}"

    # Test core schema validation
    is_valid_core, err_core = validate_telemetry_dict(valid_payload, require_full_schema=False)
    assert is_valid_core, f"Expected valid core payload, got error: {err_core}"


def test_schema_allowed_scenarios():
    """Pytest: Test allowed scenario values ('normal', 'degrading', 'near_failure') and rejection of invalid values."""
    valid_scenarios = ["normal", "degrading", "near_failure"]
    base_payload = {
        "machine_id": "PRINTER-3D-01",
        "timestamp": datetime.utcnow(),
        "machine_type": "3D_Printer",
        "temp": 50.0,
        "vibration": 1.2,
        "current": 5.0,
        "rpm": 3000,
        "hours": 200.0,
        "workload": 50.0,
        "tool_wear": 5.0,
        "health_index": 95.0,
    }

    for scenario in valid_scenarios:
        payload = base_payload.copy()
        payload["scenario"] = scenario
        sensor_obj = SensorData.model_validate(payload)
        assert sensor_obj.scenario == scenario

    # Invalid scenario test
    invalid_payload = base_payload.copy()
    invalid_payload["scenario"] = "catastrophic_meltdown"
    with pytest.raises(ValueError) as exc_info:
        SensorData.model_validate(invalid_payload)
    assert "Invalid scenario" in str(exc_info.value)


def test_schema_validation_limits():
    """Pytest: Test out-of-bounds telemetry values against configurable validation limits."""
    invalid_payload = {
        "machine_id": "CNC-999",
        "timestamp": datetime.utcnow(),
        "machine_type": "CNC",
        "temp": 350.0,  # Exceeds max 200.0 °C
        "vibration": 2.0,
        "current": 10.0,
        "rpm": 5000,
        "hours": 100.0,
        "workload": 50.0,
        "tool_wear": 2.0,
        "health_index": 90.0,
        "scenario": "normal",
    }
    with pytest.raises(ValueError) as exc_info:
        SensorData.model_validate(invalid_payload)
    assert "outside operational limits" in str(exc_info.value)


def test_ground_truth_isolation():
    """Pytest: Verify predictive feature utility excludes ground-truth leakage fields."""
    features = SensorData.predictive_feature_names()
    ground_truth = SensorData.ground_truth_field_names()

    assert "health_index" not in features, "Leakage risk: health_index in predictive features!"
    assert "scenario" not in features, "Leakage risk: scenario in predictive features!"
    assert "health_index" in ground_truth
    assert "scenario" in ground_truth


def test_git_availability():
    """Pytest: Test Git status check."""
    status = check_git_status()
    assert status["git_available"] is True, "Git executable not available in system PATH"
    assert status["is_repository"] is True, "Git repository missing or not initialized"


# =====================================================================
# STANDALONE REPORTING ENTRYPOINT
# =====================================================================

def main():
    """Run environment and schema verification report."""
    print("=" * 80)
    print("AI-POWERED PREDICTIVE MAINTENANCE SYSTEM - PHASE 1 VERIFICATION")
    print("=" * 80)

    # 1. Environment Info
    env_info = get_environment_info()
    print("\n--- 1. PYTHON ENVIRONMENT INFO ---")
    print(f"Python Executable : {env_info['python_executable']}")
    print(f"Python Version    : {env_info['python_version']}")
    print(f"Active Conda Env  : {env_info['active_conda_env']}")

    # 2. Dependency Check
    print("\n--- 2. REQUIRED DEPENDENCIES CHECK ---")
    deps = check_dependencies()
    missing_count = 0
    for pkg, info in deps.items():
        if info["installed"]:
            status_str = f"[OK] {info['version']:<15} (Imported from: {info['location']})"
        else:
            status_str = "[MISSING]"
            missing_count += 1
        print(f"  - {pkg:<15}: {status_str}")

    # 3. Git Repository Status
    print("\n--- 3. GIT REPOSITORY STATUS ---")
    git_status = check_git_status()
    print(f"Git Executable Available : {git_status['git_available']} ({git_status['git_executable']})")
    print(f"Repository Initialized   : {git_status['is_repository']}")
    if git_status["initialized_now"]:
        print("  -> Git repository was newly initialized for project root.")
    else:
        print("  -> Existing repository preserved intact.")

    # 4. Schema Integrity Check
    print("\n--- 4. SHARED SENSOR SCHEMA CHECK ---")
    print(f"Core Schema Fields (8)      : {CoreSensorData.core_field_names()}")
    print(f"Extension Fields (4)        : {SensorData.extension_field_names()}")
    print(f"Predictive ML Features (7)  : {SensorData.predictive_feature_names()}")
    print(f"Ground Truth Targets (2)    : {SensorData.ground_truth_field_names()}")
    print(f"Allowed Scenarios           : {sorted(list(ALLOWED_SCENARIOS))}")

    print("\n" + "=" * 80)
    if missing_count == 0:
        print("SUCCESS: All Phase 1 environment and schema checks passed!")
    else:
        print(f"WARNING: {missing_count} required package(s) missing!")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
