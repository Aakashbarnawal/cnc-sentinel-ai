"""Isolated Concept-Drift (CD_01 - CD_06) Experiment Framework.

This module implements six distinct, scientifically rigorous concept-drift scenarios
modifying P(Y|X) while preserving P(X) strictly invariant.

Safety Rules Enforced:
1. Canonical datasets (data/processed/reference.csv, data/processed/production.csv) are NEVER modified.
2. Existing experiment results are NEVER modified.
3. ml/drift.py and model training code are untouched.
4. All outputs are saved exclusively under experiments/isolated/.
5. Strict feature invariance: 0 changed feature cells, 0 changed feature rows.
"""

import os
import sys
import hashlib
import json
import math
from typing import Dict, Any, List, Tuple
import pandas as pd
import numpy as np

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.services.prediction_service import load_production_model


# =====================================================================
# UTILITY FUNCTIONS: PURE PYTHON PSI, KL DIVERGENCE, AUROC, HASHING
# =====================================================================

def calculate_psi(reference_col: pd.Series, production_col: pd.Series, num_bins: int = 10) -> float:
    """Calculate Population Stability Index (PSI) for numerical features."""
    if reference_col.equals(production_col):
        return 0.0

    bins = np.linspace(
        min(reference_col.min(), production_col.min()),
        max(reference_col.max(), production_col.max()),
        num_bins + 1,
    )
    bins = np.unique(bins)
    if len(bins) <= 1:
        return 0.0

    ref_counts, _ = np.histogram(reference_col, bins=bins)
    prod_counts, _ = np.histogram(production_col, bins=bins)

    ref_pct = np.where(ref_counts == 0, 0.0001, ref_counts) / len(reference_col)
    prod_pct = np.where(prod_counts == 0, 0.0001, prod_counts) / len(production_col)

    psi_val = np.sum((prod_pct - ref_pct) * np.log(prod_pct / ref_pct))
    return float(psi_val)


def calculate_kl_divergence(reference_col: pd.Series, production_col: pd.Series, num_bins: int = 10) -> float:
    """Calculate Kullback-Leibler (KL) Divergence for numerical features."""
    if reference_col.equals(production_col):
        return 0.0

    bins = np.linspace(
        min(reference_col.min(), production_col.min()),
        max(reference_col.max(), production_col.max()),
        num_bins + 1,
    )
    bins = np.unique(bins)
    if len(bins) <= 1:
        return 0.0

    ref_counts, _ = np.histogram(reference_col, bins=bins)
    prod_counts, _ = np.histogram(production_col, bins=bins)

    ref_pct = np.where(ref_counts == 0, 0.0001, ref_counts) / len(reference_col)
    prod_pct = np.where(prod_counts == 0, 0.0001, prod_counts) / len(production_col)

    kl_val = np.sum(ref_pct * np.log(ref_pct / prod_pct))
    return float(kl_val)


def calculate_auroc(y_true_seq: List[int], y_score_seq: List[float]) -> float:
    """Pure Python implementation of AUROC (Area Under ROC Curve)."""
    n_pos = sum(1 for y in y_true_seq if y == 1)
    n_neg = len(y_true_seq) - n_pos
    if n_pos == 0 or n_neg == 0:
        return 0.5

    pairs = sorted(zip(y_score_seq, y_true_seq), key=lambda x: x[0], reverse=True)
    tp = 0
    auc = 0.0
    for score, target in pairs:
        if target == 1:
            tp += 1
        else:
            auc += tp
    return round(float(auc / (n_pos * n_neg)), 4)


def compute_file_sha256(filepath: str) -> str:
    """Calculate SHA-256 hex digest of a file for canonical integrity validation."""
    if not os.path.exists(filepath):
        return "FILE_NOT_FOUND"
    sha = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            sha.update(chunk)
    return sha.hexdigest()


# =====================================================================
# CONCEPT DRIFT SCENARIO DEFINITIONS (CD_01 - CD_06)
# =====================================================================

MODEL_FEATURES = [
    "type",
    "air_temperature_c",
    "process_temperature_c",
    "rotational_speed_rpm",
    "torque_nm",
    "tool_wear_min",
]
TARGET_COL = "machine_failure"


def apply_cd_01_subdomain_threshold(df_baseline: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """CD_01: Sub-domain Severity Threshold Drift.
    
    Segment: Latest 25% of production rows (row_index >= 3750).
    Rule: For type == 'L' and (torque_nm > 50.0 or tool_wear_min > 180), machine_failure = 1.
    """
    df = df_baseline.copy()
    total_rows = len(df)
    
    segment_mask = df.index >= 3750
    segment_rows = int(segment_mask.sum())
    
    rule_mask = segment_mask & (df["type"] == "L") & ((df["torque_nm"] > 50.0) | (df["tool_wear_min"] > 180.0))
    
    changed_mask = rule_mask & (df[TARGET_COL] == 0)
    changed_rows = int(changed_mask.sum())
    
    df.loc[changed_mask, TARGET_COL] = 1
    
    meta = {
        "scenario_id": "CD_01",
        "drift_type": "concept_drift",
        "mechanism": "Sub-domain Severity Threshold Shift",
        "segment_definition": "Latest 25% of production rows (row_index >= 3750)",
        "affected_features": "type, torque_nm, tool_wear_min",
        "transformation": "If type=='L' and (torque_nm > 50.0 or tool_wear_min > 180), machine_failure = 1",
        "total_production_rows": total_rows,
        "segment_rows": segment_rows,
        "segment_fraction": round(segment_rows / total_rows, 4),
        "changed_class_rows": changed_rows,
        "relabel_fraction_within_segment": round(changed_rows / segment_rows, 4),
        "overall_relabel_fraction": round(changed_rows / total_rows, 4),
    }
    return df, meta


def apply_cd_02_decision_boundary_shift(df_baseline: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """CD_02: Decision-Boundary Shift (Threshold Movement).
    
    Segment: High tool wear regime (tool_wear_min >= 130.0 -> 1500 rows, 30% of production).
    Rule: Thermal differential tolerance drops from 11.5°C to 10.3°C. If (process_temp - air_temp) > 10.3°C, machine_failure = 1.
    """
    df = df_baseline.copy()
    total_rows = len(df)
    
    segment_mask = df["tool_wear_min"] >= 130.0
    segment_rows = int(segment_mask.sum())
    
    temp_diff = df["process_temperature_c"] - df["air_temperature_c"]
    rule_mask = segment_mask & (temp_diff > 10.3)
    
    changed_mask = rule_mask & (df[TARGET_COL] == 0)
    changed_rows = int(changed_mask.sum())
    
    df.loc[changed_mask, TARGET_COL] = 1
    
    meta = {
        "scenario_id": "CD_02",
        "drift_type": "concept_drift",
        "mechanism": "Decision-Boundary Shift (Threshold Movement)",
        "segment_definition": "High tool wear regime (tool_wear_min >= 130.0 min)",
        "affected_features": "process_temperature_c, air_temperature_c, tool_wear_min",
        "transformation": "If (process_temp - air_temp) > 10.3°C in segment, machine_failure = 1",
        "total_production_rows": total_rows,
        "segment_rows": segment_rows,
        "segment_fraction": round(segment_rows / total_rows, 4),
        "changed_class_rows": changed_rows,
        "relabel_fraction_within_segment": round(changed_rows / segment_rows, 4),
        "overall_relabel_fraction": round(changed_rows / total_rows, 4),
    }
    return df, meta


def apply_cd_03_interaction_rule_change(df_baseline: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """CD_03: Interaction-Rule Change (Multi-Feature Coupling).
    
    Segment: Latest 35% of production rows (row_index >= 3250 -> 1750 rows).
    Rule: High power dissipation coupling: (torque_nm * rotational_speed_rpm)/1000 > 72.0 and tool_wear_min > 90.0 => machine_failure = 1.
    """
    df = df_baseline.copy()
    total_rows = len(df)
    
    segment_mask = df.index >= 3250
    segment_rows = int(segment_mask.sum())
    
    power_term = (df["torque_nm"] * df["rotational_speed_rpm"]) / 1000.0
    rule_mask = segment_mask & (power_term > 72.0) & (df["tool_wear_min"] > 90.0)
    
    changed_mask = rule_mask & (df[TARGET_COL] == 0)
    changed_rows = int(changed_mask.sum())
    
    df.loc[changed_mask, TARGET_COL] = 1
    
    meta = {
        "scenario_id": "CD_03",
        "drift_type": "concept_drift",
        "mechanism": "Interaction-Rule Change (Power-Wear Coupling)",
        "segment_definition": "Latest 35% of production rows (row_index >= 3250)",
        "affected_features": "torque_nm, rotational_speed_rpm, tool_wear_min",
        "transformation": "If (torque * rpm)/1000 > 72.0 and tool_wear > 90.0, machine_failure = 1",
        "total_production_rows": total_rows,
        "segment_rows": segment_rows,
        "segment_fraction": round(segment_rows / total_rows, 4),
        "changed_class_rows": changed_rows,
        "relabel_fraction_within_segment": round(changed_rows / segment_rows, 4),
        "overall_relabel_fraction": round(changed_rows / total_rows, 4),
    }
    return df, meta


def apply_cd_04_coefficient_weight_change(df_baseline: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """CD_04: Coefficient / Weight Relationship Change (Tool Wear Dominance Shift).
    
    Segment: Heavy/Medium Equipment segment (type in ['M', 'H'] -> 2082 rows, 41.64% of production).
    Rule: Tool wear sensitivity increases: tool_wear_min > 155.0 min => machine_failure = 1.
    """
    df = df_baseline.copy()
    total_rows = len(df)
    
    segment_mask = df["type"].isin(["M", "H"])
    segment_rows = int(segment_mask.sum())
    
    rule_mask = segment_mask & (df["tool_wear_min"] > 155.0)
    
    changed_mask = rule_mask & (df[TARGET_COL] == 0)
    changed_rows = int(changed_mask.sum())
    
    df.loc[changed_mask, TARGET_COL] = 1
    
    meta = {
        "scenario_id": "CD_04",
        "drift_type": "concept_drift",
        "mechanism": "Coefficient/Weight Relationship Shift (Tool Wear Dominance)",
        "segment_definition": "Heavy & Medium machinery segment (type in ['M', 'H'])",
        "affected_features": "type, tool_wear_min",
        "transformation": "If type in ['M','H'] and tool_wear_min > 155.0, machine_failure = 1",
        "total_production_rows": total_rows,
        "segment_rows": segment_rows,
        "segment_fraction": round(segment_rows / total_rows, 4),
        "changed_class_rows": changed_rows,
        "relabel_fraction_within_segment": round(changed_rows / segment_rows, 4),
        "overall_relabel_fraction": round(changed_rows / total_rows, 4),
    }
    return df, meta


def apply_cd_05_temporal_regime_change(df_baseline: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """CD_05: Temporal / Regime-Specific Concept Change (Summer Thermal Shift).
    
    Segment: Middle operating regime (1250 <= row_index < 3750 -> 2500 rows, 50% of production).
    Rule: Ambient thermal sensitivity: air_temp > 25.4°C and process_temp > 35.6°C => machine_failure = 1.
    """
    df = df_baseline.copy()
    total_rows = len(df)
    
    segment_mask = (df.index >= 1250) & (df.index < 3750)
    segment_rows = int(segment_mask.sum())
    
    rule_mask = segment_mask & (df["air_temperature_c"] > 25.4) & (df["process_temperature_c"] > 35.6)
    
    changed_mask = rule_mask & (df[TARGET_COL] == 0)
    changed_rows = int(changed_mask.sum())
    
    df.loc[changed_mask, TARGET_COL] = 1
    
    meta = {
        "scenario_id": "CD_05",
        "drift_type": "concept_drift",
        "mechanism": "Temporal/Regime-Specific Concept Shift (Summer Thermal)",
        "segment_definition": "Middle operating regime (1250 <= row_index < 3750)",
        "affected_features": "air_temperature_c, process_temperature_c",
        "transformation": "If air_temp > 25.4°C and process_temp > 35.6°C in regime, machine_failure = 1",
        "total_production_rows": total_rows,
        "segment_rows": segment_rows,
        "segment_fraction": round(segment_rows / total_rows, 4),
        "changed_class_rows": changed_rows,
        "relabel_fraction_within_segment": round(changed_rows / segment_rows, 4),
        "overall_relabel_fraction": round(changed_rows / total_rows, 4),
    }
    return df, meta


def apply_cd_06_nonlinear_boundary_change(df_baseline: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """CD_06: Nonlinear Decision-Boundary Change (Elliptical Resonance Shift).
    
    Segment: High-load regime (torque_nm >= 36.0 -> 2835 rows, 56.70% of production).
    Rule: Radial elliptical boundary in (Torque, RPM) space: ((torque - 40)/10)^2 + ((rpm - 1500)/200)^2 > 3.2 => machine_failure = 1.
    """
    df = df_baseline.copy()
    total_rows = len(df)
    
    segment_mask = df["torque_nm"] >= 36.0
    segment_rows = int(segment_mask.sum())
    
    z_torque = (df["torque_nm"] - 40.0) / 10.0
    z_rpm = (df["rotational_speed_rpm"] - 1500.0) / 200.0
    radial_dist = (z_torque ** 2) + (z_rpm ** 2)
    
    rule_mask = segment_mask & (radial_dist > 3.2)
    
    changed_mask = rule_mask & (df[TARGET_COL] == 0)
    changed_rows = int(changed_mask.sum())
    
    df.loc[changed_mask, TARGET_COL] = 1
    
    meta = {
        "scenario_id": "CD_06",
        "drift_type": "concept_drift",
        "mechanism": "Nonlinear Decision-Boundary Change (Elliptical Resonance)",
        "segment_definition": "High-load operating regime (torque_nm >= 36.0 Nm)",
        "affected_features": "torque_nm, rotational_speed_rpm",
        "transformation": "If z_torque^2 + z_rpm^2 > 3.2 in high-load regime, machine_failure = 1",
        "total_production_rows": total_rows,
        "segment_rows": segment_rows,
        "segment_fraction": round(segment_rows / total_rows, 4),
        "changed_class_rows": changed_rows,
        "relabel_fraction_within_segment": round(changed_rows / segment_rows, 4),
        "overall_relabel_fraction": round(changed_rows / total_rows, 4),
    }
    return df, meta


# =====================================================================
# EXPERIMENT ORCHESTRATOR & VALIDATION RUNNER
# =====================================================================

SCENARIO_FUNCTIONS = [
    apply_cd_01_subdomain_threshold,
    apply_cd_02_decision_boundary_shift,
    apply_cd_03_interaction_rule_change,
    apply_cd_04_coefficient_weight_change,
    apply_cd_05_temporal_regime_change,
    apply_cd_06_nonlinear_boundary_change,
]


def run_all_cd_experiments() -> Tuple[pd.DataFrame, List[Dict[str, Any]]]:
    """Execute CD_01 through CD_06 experiments, validating feature invariance and metrics."""
    output_dir = "experiments/isolated"
    os.makedirs(output_dir, exist_ok=True)

    # 1. Snapshot Canonical Hashes
    canonical_files = {
        "reference.csv": "data/processed/reference.csv",
        "production.csv": "data/processed/production.csv",
    }
    pre_hashes = {k: compute_file_sha256(v) for k, v in canonical_files.items()}

    # 2. Load Reference and Baseline Production Datasets
    ref_df = pd.read_csv("data/processed/reference.csv")
    prod_baseline_df = pd.read_csv("data/processed/production.csv")

    # Save isolated baseline copies
    ref_df.to_csv(os.path.join(output_dir, "reference.csv"), index=False)
    prod_baseline_df.to_csv(os.path.join(output_dir, "production_baseline.csv"), index=False)

    # 3. Load Production ML Model for AUROC Evaluation
    model, metadata = load_production_model()

    results_list: List[Dict[str, Any]] = []

    for fn in SCENARIO_FUNCTIONS:
        # Generate Scenario Dataset
        cd_df, meta = fn(prod_baseline_df)
        scenario_id = meta["scenario_id"]
        
        # Save isolated scenario CSV
        scenario_csv_path = os.path.join(output_dir, f"{scenario_id}_production.csv")
        cd_df.to_csv(scenario_csv_path, index=False)

        # A. Verify Feature Invariance (X_baseline vs X_scenario)
        feature_cols = [c for c in prod_baseline_df.columns if c != TARGET_COL]
        diff_matrix = (prod_baseline_df[feature_cols] != cd_df[feature_cols])
        changed_feature_cells = int(diff_matrix.sum().sum())
        changed_feature_rows = int((diff_matrix.sum(axis=1) > 0).sum())

        assert changed_feature_cells == 0, f"FEATURE INVARIANCE VIOLATION in {scenario_id}: {changed_feature_cells} cells changed!"
        assert changed_feature_rows == 0, f"FEATURE INVARIANCE VIOLATION in {scenario_id}: {changed_feature_rows} rows changed!"

        # B. Measure PSI & KL Divergence between Baseline Production X and Scenario Production X
        continuous_features = [
            "air_temperature_c",
            "process_temperature_c",
            "rotational_speed_rpm",
            "torque_nm",
            "tool_wear_min",
        ]
        psi_values = [calculate_psi(prod_baseline_df[c], cd_df[c]) for c in continuous_features]
        kl_values = [calculate_kl_divergence(prod_baseline_df[c], cd_df[c]) for c in continuous_features]
        
        mean_psi = float(np.mean(psi_values))
        mean_kl = float(np.mean(kl_values))
        dataset_drifted = bool(mean_psi > 0.1)

        # C. Evaluate Production Model AUROC on Scenario
        X_eval = cd_df[MODEL_FEATURES]
        y_true = cd_df[TARGET_COL].tolist()
        y_proba = model.predict_proba(X_eval)[:, 1].tolist()
        
        auroc_val = calculate_auroc(y_true, y_proba)

        # D. Assemble Result Metadata
        res_row = {
            "scenario_id": scenario_id,
            "drift_type": meta["drift_type"],
            "severity": meta["overall_relabel_fraction"],
            "affected_features": meta["affected_features"],
            "segment_definition": meta["segment_definition"],
            "transformation": meta["transformation"],
            "total_production_rows": meta["total_production_rows"],
            "segment_rows": meta["segment_rows"],
            "segment_fraction": meta["segment_fraction"],
            "changed_class_rows": meta["changed_class_rows"],
            "relabel_fraction_within_segment": meta["relabel_fraction_within_segment"],
            "overall_relabel_fraction": meta["overall_relabel_fraction"],
            "changed_feature_cells": changed_feature_cells,
            "changed_feature_rows": changed_feature_rows,
            "mean_psi": round(mean_psi, 6),
            "mean_kl_divergence": round(mean_kl, 6),
            "dataset_drifted": dataset_drifted,
            "detected_features": "none" if not dataset_drifted else "detected",
            "auroc": round(auroc_val, 4),
            "reproducible": True,
        }
        results_list.append(res_row)

    # Save dedicated CD results CSV
    results_df = pd.DataFrame(results_list)
    cd_results_path = os.path.join(output_dir, "CD_experiment_results.csv")
    results_df.to_csv(cd_results_path, index=False)

    # 4. Verify Canonical Hashes Unchanged
    post_hashes = {k: compute_file_sha256(v) for k, v in canonical_files.items()}
    for k in pre_hashes:
        assert pre_hashes[k] == post_hashes[k], f"CANONICAL INTEGRITY VIOLATION: {k} hash changed from {pre_hashes[k]} to {post_hashes[k]}!"

    return results_df, results_list


if __name__ == "__main__":
    df_res, _ = run_all_cd_experiments()
    print("\n" + "=" * 80)
    print("CONCEPT DRIFT (CD_01 - CD_06) ISOLATED EXPERIMENTS COMPLETED")
    print("=" * 80)
    print(df_res[["scenario_id", "severity", "segment_fraction", "relabel_fraction_within_segment", "overall_relabel_fraction", "changed_feature_cells", "auroc"]].to_string(index=False))
    print("\nResults saved to 'experiments/isolated/CD_experiment_results.csv'.\n")
