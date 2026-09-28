"""Equipment-Aware Diagnostics and Fault Classification Service for CNC Sentinel AI."""

from typing import Dict, Any, List, Optional


# Equipment Category Default Operational Thresholds
DIAGNOSTIC_THRESHOLDS: Dict[str, Dict[str, float]] = {
    "CNC": {"temp_warn": 75.0, "temp_crit": 85.0, "vib_warn": 5.0, "vib_crit": 7.5, "curr_warn": 22.0, "curr_crit": 30.0, "wear_warn": 60.0, "wear_crit": 80.0},
    "3D_Printer": {"temp_warn": 95.0, "temp_crit": 115.0, "vib_warn": 3.5, "vib_crit": 5.5, "curr_warn": 12.0, "curr_crit": 16.0, "wear_warn": 70.0, "wear_crit": 90.0},
    "ELECTRIC_MOTOR": {"temp_warn": 80.0, "temp_crit": 95.0, "vib_warn": 4.5, "vib_crit": 6.5, "curr_warn": 35.0, "curr_crit": 48.0, "wear_warn": 65.0, "wear_crit": 85.0},
    "PUMP_COMPRESSOR": {"temp_warn": 75.0, "temp_crit": 88.0, "vib_warn": 5.5, "vib_crit": 8.0, "curr_warn": 25.0, "curr_crit": 35.0, "wear_warn": 60.0, "wear_crit": 85.0},
    "HVAC_FAN": {"temp_warn": 65.0, "temp_crit": 78.0, "vib_warn": 4.0, "vib_crit": 6.0, "curr_warn": 18.0, "curr_crit": 25.0, "wear_warn": 60.0, "wear_crit": 80.0},
    "CONVEYOR": {"temp_warn": 70.0, "temp_crit": 82.0, "vib_warn": 4.5, "vib_crit": 6.8, "curr_warn": 18.0, "curr_crit": 26.0, "wear_warn": 65.0, "wear_crit": 85.0},
    "GEARBOX": {"temp_warn": 85.0, "temp_crit": 100.0, "vib_warn": 6.0, "vib_crit": 9.0, "curr_warn": 28.0, "curr_crit": 40.0, "wear_warn": 70.0, "wear_crit": 90.0},
}


def evaluate_equipment_diagnostics(
    equipment_type: str,
    temp: float,
    vibration: float,
    current: float,
    rpm: int,
    tool_wear: float = 0.0,
    failure_probability: Optional[float] = None,
) -> Dict[str, Any]:
    """Perform equipment-aware diagnostic evaluation.
    
    Args:
        equipment_type: Category identifier (e.g., 'CNC', '3D_Printer', 'ELECTRIC_MOTOR', etc.)
        temp: Temperature reading in °C.
        vibration: Vibration RMS in mm/s.
        current: Electrical current in Amperes.
        rpm: Rotational speed in RPM.
        tool_wear: Tool wear index.
        failure_probability: ML model output probability if calculated.
        
    Returns:
        Dict containing severity, threshold warnings, rule-based suspected faults,
        ML predicted risk, primary issue, and recommended maintenance action.
    """
    category_key = equipment_type.upper()
    limits = DIAGNOSTIC_THRESHOLDS.get(category_key, DIAGNOSTIC_THRESHOLDS["CNC"])

    warnings: List[str] = []
    suspected_faults: List[str] = []
    severity_score = 0  # 0: NORMAL, 1: WARNING, 2: CRITICAL

    # 1. Temperature Evaluation
    if temp >= limits["temp_crit"]:
        warnings.append(f"Critical temperature: {temp:.1f}°C >= {limits['temp_crit']}°C")
        suspected_faults.append("Thermal Runaway / Cooling System Failure")
        severity_score = max(severity_score, 2)
    elif temp >= limits["temp_warn"]:
        warnings.append(f"Elevated temperature: {temp:.1f}°C >= {limits['temp_warn']}°C")
        suspected_faults.append("Abnormal Heat Accumulation / Inadequate Lubrication")
        severity_score = max(severity_score, 1)

    # 2. Vibration Evaluation
    if vibration >= limits["vib_crit"]:
        warnings.append(f"Critical vibration: {vibration:.2f} mm/s >= {limits['vib_crit']} mm/s")
        suspected_faults.append("Severe Mechanical Imbalance / Bearing Breakdown")
        severity_score = max(severity_score, 2)
    elif vibration >= limits["vib_warn"]:
        warnings.append(f"Elevated vibration: {vibration:.2f} mm/s >= {limits['vib_warn']} mm/s")
        suspected_faults.append("Shaft Misalignment / Rotor Imbalance")
        severity_score = max(severity_score, 1)

    # 3. Current Evaluation
    if current >= limits["curr_crit"]:
        warnings.append(f"Critical current draw: {current:.1f}A >= {limits['curr_crit']}A")
        suspected_faults.append("Motor Overload / Mechanical Jamming")
        severity_score = max(severity_score, 2)
    elif current >= limits["curr_warn"]:
        warnings.append(f"Elevated current draw: {current:.1f}A >= {limits['curr_warn']}A")
        suspected_faults.append("Increased Mechanical Drag / Drive Friction")
        severity_score = max(severity_score, 1)

    # 4. Tool Wear / Component Wear Evaluation
    if tool_wear >= limits["wear_crit"]:
        warnings.append(f"Critical tool/component wear: {tool_wear:.1f}%")
        suspected_faults.append("Extreme Tool/Bearing Wear — Immediate Replacement Needed")
        severity_score = max(severity_score, 2)
    elif tool_wear >= limits["wear_warn"]:
        warnings.append(f"High tool/component wear: {tool_wear:.1f}%")
        suspected_faults.append("Advanced Component Wear — Schedule Replacement")
        severity_score = max(severity_score, 1)

    # 5. Correlated Multi-Sensor Anomalies
    if len(warnings) >= 2:
        suspected_faults.append("Correlated Multi-Sensor Anomaly (High Combined Risk)")
        severity_score = max(severity_score, 2)

    # 6. ML Model Risk Integration
    ml_risk_label = "Model Inference Pending"
    if failure_probability is not None:
        if failure_probability >= 0.70:
            ml_risk_label = f"HIGH FAILURE RISK ({failure_probability*100:.1f}%)"
            severity_score = max(severity_score, 2)
        elif failure_probability >= 0.33:
            ml_risk_label = f"ELEVATED FAILURE RISK ({failure_probability*100:.1f}%)"
            severity_score = max(severity_score, 1)
        else:
            ml_risk_label = f"LOW RISK ({failure_probability*100:.1f}%)"

    # Determine Severity String
    severity_map = {0: "NORMAL", 1: "WARNING", 2: "CRITICAL"}
    severity = severity_map[severity_score]

    # Primary Issue & Recommended Action
    if severity == "CRITICAL":
        primary_issue = suspected_faults[0] if suspected_faults else "Critical Multi-Sensor Anomaly"
        recommended_action = "HALT MACHINE IMMEDIATELY. Perform urgent mechanical & electrical inspection."
    elif severity == "WARNING":
        primary_issue = suspected_faults[0] if suspected_faults else "Elevated Threshold Warning"
        recommended_action = "Schedule preventative maintenance check within 24 operating hours."
    else:
        primary_issue = "Nominal Operating Parameters"
        recommended_action = "Continue standard operating schedule. All sensor signals within bounds."

    return {
        "severity": severity,
        "threshold_warnings": warnings,
        "suspected_faults": suspected_faults,
        "ml_predicted_risk": ml_risk_label,
        "primary_suspected_issue": primary_issue,
        "recommended_action": recommended_action,
        "correlated_anomalies_count": len(warnings),
    }
