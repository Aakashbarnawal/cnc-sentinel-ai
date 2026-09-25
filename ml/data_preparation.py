"""Data Preparation and Preprocessing Module for Predictive Maintenance.

This module provides data loading, cleaning, validation, and feature governance logic for:
1. AI4I 2020 Predictive Maintenance Dataset (data/raw/ai4i2020.csv -> data/processed/ai4i2020_cleaned.csv).
2. Simulator Telemetry Dataset validation (data/raw/simulated_telemetry.csv).

Data Leakage & Feature Governance Rules:
- Target Variable: `machine_failure`
- Identifiers: `udi`, `product_id` (Excluded from predictive model features)
- Failure-Mode Indicators: `twf`, `hdf`, `pwf`, `osf`, `rnf` (Target leakage fields -> Excluded from predictive model features)
- Candidate Model Features: `type`, `air_temperature_c`, `process_temperature_c`, `rotational_speed_rpm`, `torque_nm`, `tool_wear_min`
"""

import json
import os
import sys
from typing import Dict, Any, Tuple, List, Optional
import pandas as pd
import numpy as np

from config.schema import SensorData, validate_telemetry_dict

# Canonical column name mapping for AI4I dataset
COLUMN_MAPPING = {
    "UDI": "udi",
    "Product ID": "product_id",
    "Type": "type",
    "Air temperature [K]": "air_temperature_k",
    "Process temperature [K]": "process_temperature_k",
    "Rotational speed [rpm]": "rotational_speed_rpm",
    "Torque [Nm]": "torque_nm",
    "Tool wear [min]": "tool_wear_min",
    "Machine failure": "machine_failure",
    "TWF": "twf",
    "HDF": "hdf",
    "PWF": "pwf",
    "OSF": "osf",
    "RNF": "rnf",
}

# Feature governance classifications
IDENTIFIER_COLUMNS = ["udi", "product_id"]
TARGET_COLUMN = "machine_failure"
LEAKAGE_COLUMNS = ["twf", "hdf", "pwf", "osf", "rnf"]
PROPOSED_MODEL_FEATURES = [
    "type",
    "air_temperature_c",
    "process_temperature_c",
    "rotational_speed_rpm",
    "torque_nm",
    "tool_wear_min",
]

# Kelvin to Celsius offset constant
KELVIN_TO_CELSIUS_OFFSET = 273.15


def load_raw_ai4i_dataset(file_path: str = "data/raw/ai4i2020.csv") -> pd.DataFrame:
    """Load raw AI4I 2020 dataset from CSV.
    
    Raises:
        FileNotFoundError: If the raw benchmark CSV file is missing.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(
            f"Raw AI4I dataset not found at '{file_path}'. "
            "Please download the official UCI AI4I 2020 Predictive Maintenance Dataset from: "
            "https://archive.ics.uci.edu/dataset/601/ai4i+2020+predictive+maintenance+dataset"
        )
    return pd.read_csv(file_path)


def clean_ai4i_dataset(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Clean and preprocess the raw AI4I dataset.
    
    Steps:
    1. Validate required columns presence.
    2. Normalize column names.
    3. Check and report missing/null values and duplicates.
    4. Convert Kelvin temperatures to Celsius (`air_temperature_c`, `process_temperature_c`).
    5. Validate numeric ranges and target binary labels.
    6. Generate comprehensive data quality audit stats.
    
    Args:
        df: Input raw DataFrame.
        
    Returns:
        Tuple of (cleaned_df: pd.DataFrame, report: Dict[str, Any]).
    """
    raw_shape = df.shape
    raw_columns = list(df.columns)
    
    # 1. Validate required raw columns
    missing_cols = [col for col in COLUMN_MAPPING.keys() if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Raw dataset is missing required columns: {missing_cols}")

    # Copy DataFrame to avoid mutating input
    cleaned_df = df.copy()

    # 2. Check nulls and duplicates before cleaning
    null_counts_raw = cleaned_df.isnull().sum().to_dict()
    total_nulls_raw = sum(null_counts_raw.values())
    exact_duplicates_raw = int(cleaned_df.duplicated().sum())

    # Handle duplicates if present (drop exact duplicates)
    if exact_duplicates_raw > 0:
        cleaned_df = cleaned_df.drop_duplicates().reset_index(drop=True)

    # 3. Rename columns
    cleaned_df = cleaned_df.rename(columns=COLUMN_MAPPING)

    # 4. Temperature Conversion (Kelvin to Celsius)
    cleaned_df["air_temperature_c"] = (cleaned_df["air_temperature_k"] - KELVIN_TO_CELSIUS_OFFSET).round(2)
    cleaned_df["process_temperature_c"] = (cleaned_df["process_temperature_k"] - KELVIN_TO_CELSIUS_OFFSET).round(2)

    # Reorder columns logically (keep raw Kelvin + new Celsius)
    ordered_cols = [
        "udi",
        "product_id",
        "type",
        "air_temperature_c",
        "process_temperature_c",
        "air_temperature_k",
        "process_temperature_k",
        "rotational_speed_rpm",
        "torque_nm",
        "tool_wear_min",
        "machine_failure",
        "twf",
        "hdf",
        "pwf",
        "osf",
        "rnf",
    ]
    cleaned_df = cleaned_df[ordered_cols]

    # 5. Range and Data Quality Checks
    numeric_checks = {
        "air_temperature_c": (-50.0, 100.0),
        "process_temperature_c": (-50.0, 100.0),
        "rotational_speed_rpm": (0, 10000),
        "torque_nm": (0.0, 200.0),
        "tool_wear_min": (0, 1000),
    }
    
    invalid_rows_count = 0
    for col, (min_val, max_val) in numeric_checks.items():
        out_of_bounds = ((cleaned_df[col] < min_val) | (cleaned_df[col] > max_val)).sum()
        if out_of_bounds > 0:
            invalid_rows_count += out_of_bounds

    # Check target binary validity
    valid_targets = {0, 1}
    target_set = set(cleaned_df[TARGET_COLUMN].unique())
    if not target_set.issubset(valid_targets):
        raise ValueError(f"Target '{TARGET_COLUMN}' contains invalid non-binary values: {target_set - valid_targets}")

    # Compute target distributions before and after
    raw_target_dist = df["Machine failure"].value_counts().to_dict()
    cleaned_target_dist = cleaned_df["machine_failure"].value_counts().to_dict()

    # Build Audit Report
    report = {
        "dataset_name": "AI4I 2020 Predictive Maintenance Dataset",
        "raw_shape": list(raw_shape),
        "cleaned_shape": list(cleaned_df.shape),
        "total_nulls_raw": total_nulls_raw,
        "exact_duplicates_removed": exact_duplicates_raw,
        "invalid_numeric_outliers": invalid_rows_count,
        "raw_target_distribution": {str(k): int(v) for k, v in raw_target_dist.items()},
        "cleaned_target_distribution": {str(k): int(v) for k, v in cleaned_target_dist.items()},
        "categorical_type_distribution": cleaned_df["type"].value_counts().to_dict(),
        "failure_mode_breakdown": {
            "twf": int(cleaned_df["twf"].sum()),
            "hdf": int(cleaned_df["hdf"].sum()),
            "pwf": int(cleaned_df["pwf"].sum()),
            "osf": int(cleaned_df["osf"].sum()),
            "rnf": int(cleaned_df["rnf"].sum()),
        },
        "feature_governance": {
            "proposed_model_features": PROPOSED_MODEL_FEATURES,
            "target_variable": TARGET_COLUMN,
            "excluded_identifiers": IDENTIFIER_COLUMNS,
            "excluded_leakage_columns": LEAKAGE_COLUMNS,
        },
        "numeric_stats": cleaned_df[PROPOSED_MODEL_FEATURES[1:]].describe().to_dict(),
    }

    return cleaned_df, report


def validate_simulator_dataset(file_path: str = "data/raw/simulated_telemetry.csv") -> Dict[str, Any]:
    """Validate existing simulator dataset against config.schema without modifying it.
    
    Returns:
        Validation summary report dictionary.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Simulator telemetry dataset not found at '{file_path}'.")

    df = pd.read_csv(file_path)
    total_rows = len(df)
    validation_failures = 0
    
    # Parse timestamp and validate every row
    for idx, row in df.iterrows():
        row_dict = row.to_dict()
        # Convert timestamp string to datetime if needed
        if isinstance(row_dict.get("timestamp"), str):
            try:
                row_dict["timestamp"] = pd.to_datetime(row_dict["timestamp"])
            except Exception:
                pass
        
        is_valid, err = validate_telemetry_dict(row_dict, require_full_schema=True)
        if not is_valid:
            validation_failures += 1

    duplicate_keys = int(df.duplicated(subset=["machine_id", "timestamp"]).sum())

    return {
        "file_path": file_path,
        "total_rows": total_rows,
        "total_columns": len(df.columns),
        "validation_failures": validation_failures,
        "duplicate_keys": duplicate_keys,
        "machines": df["machine_id"].nunique(),
        "machine_types": df["machine_type"].value_counts().to_dict(),
        "scenarios": df["scenario"].value_counts().to_dict(),
        "is_valid": (validation_failures == 0 and duplicate_keys == 0),
    }


def process_and_save_all(
    raw_benchmark_path: str = "data/raw/ai4i2020.csv",
    processed_benchmark_path: str = "data/processed/ai4i2020_cleaned.csv",
    simulator_path: str = "data/raw/simulated_telemetry.csv",
    report_output_path: str = "artifacts/data_quality_report.json",
) -> Dict[str, Any]:
    """Orchestrate Phase 3 benchmark cleaning, simulator verification, and report generation."""
    print("=" * 80)
    print("PHASE 3: DATASET PREPARATION & DATA QUALITY VALIDATION")
    print("=" * 80)

    # 1. Process AI4I Benchmark
    if os.path.exists(raw_benchmark_path):
        print(f"\n[1/2] Processing AI4I Benchmark from '{raw_benchmark_path}'...")
        df_raw = load_raw_ai4i_dataset(raw_benchmark_path)
        cleaned_df, benchmark_report = clean_ai4i_dataset(df_raw)

        # Save processed CSV
        os.makedirs(os.path.dirname(os.path.abspath(processed_benchmark_path)), exist_ok=True)
        cleaned_df.to_csv(processed_benchmark_path, index=False)
        print(f"  -> Cleaned dataset saved to '{processed_benchmark_path}' ({cleaned_df.shape[0]} rows x {cleaned_df.shape[1]} cols)")
    else:
        print(f"\n[1/2] WARNING: AI4I Benchmark raw file missing at '{raw_benchmark_path}'.")
        benchmark_report = {"status": "MISSING_RAW_FILE", "file_path": raw_benchmark_path}

    # 2. Validate Simulator Dataset (Read-only, preserves file intact)
    if os.path.exists(simulator_path):
        print(f"\n[2/2] Validating Simulator Telemetry from '{simulator_path}'...")
        sim_report = validate_simulator_dataset(simulator_path)
        print(f"  -> Simulator dataset valid: {sim_report['is_valid']} ({sim_report['total_rows']} rows, {sim_report['machines']} machines)")
    else:
        print(f"\n[2/2] WARNING: Simulator file missing at '{simulator_path}'.")
        sim_report = {"status": "MISSING_SIMULATOR_FILE", "file_path": simulator_path}

    # 3. Combine and save artifact report
    combined_report = {
        "timestamp": pd.Timestamp.now().isoformat(),
        "ai4i_benchmark": benchmark_report,
        "simulator_telemetry": sim_report,
        "dataset_separations_documentation": {
            "simulator_telemetry": "Synthetic time-series telemetry for real-time streaming, simulator, and dashboard UI workflow.",
            "ai4i_benchmark": "UCI public benchmark dataset for offline binary machine-failure model training and evaluation.",
        },
    }

    os.makedirs(os.path.dirname(os.path.abspath(report_output_path)), exist_ok=True)
    with open(report_output_path, "w", encoding="utf-8") as f:
        json.dump(combined_report, f, indent=2)

    print(f"\nData quality audit report saved to '{report_output_path}'.")
    print("=" * 80 + "\n")

    return combined_report


def main():
    """CLI Entrypoint for Phase 3 Data Preparation."""
    process_and_save_all()


if __name__ == "__main__":
    main()
