"""Model Explainability Module using SHAP (Phase 5).

Provides model explanation capabilities for the Predictive Maintenance System:
1. Global Feature Importance & SHAP Summary Visualizations.
2. Local Prediction Explanations with Additive Sanity Verification.
3. Feature Governance & Target Leakage Prevention.

Ground Rules & Disclaimers:
- Explanations are computed strictly on valid model input features:
  ['type', 'air_temperature_c', 'process_temperature_c', 'rotational_speed_rpm', 'torque_nm', 'tool_wear_min'].
- Prohibited leakage columns ('twf', 'hdf', 'pwf', 'osf', 'rnf', 'machine_failure', 'udi', 'product_id',
  'health_index', 'scenario') are NEVER passed to the prediction model or explainer.
- SHAP values quantify feature contributions to probability outputs (predict_proba); they describe model
  behavior rather than establishing physical real-world causality.
"""

import json
import os
import sys
from typing import Dict, Any, Tuple, List, Optional, Union
import pandas as pd
import numpy as np
import joblib
import shap
import matplotlib.pyplot as plt

from sklearn.pipeline import Pipeline

# Import feature governance definitions from Phase 4
from ml.train_model import (
    PROPOSED_MODEL_FEATURES,
    PROHIBITED_LEAKAGE_COLUMNS,
    TARGET_COLUMN,
)


def load_model_and_metadata(
    model_path: str = "models/predictive_maintenance_model.joblib",
    metadata_path: str = "models/model_metadata.json",
) -> Tuple[Pipeline, Dict[str, Any]]:
    """Load fitted model pipeline and metadata JSON without modifying files on disk.
    
    Returns:
        Tuple of (pipeline: Pipeline, metadata: Dict[str, Any]).
    """
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Model file not found at '{model_path}'.")
    if not os.path.exists(metadata_path):
        raise FileNotFoundError(f"Metadata file not found at '{metadata_path}'.")

    pipeline = joblib.load(model_path)
    with open(metadata_path, "r", encoding="utf-8") as f:
        metadata = json.load(f)

    return pipeline, metadata


def prepare_input_features(
    data: Union[pd.DataFrame, Dict[str, Any], List[Dict[str, Any]]],
    feature_list: List[str] = PROPOSED_MODEL_FEATURES,
) -> pd.DataFrame:
    """Validate and extract feature matrix, enforcing anti-leakage safeguards.
    
    Args:
        data: Input DataFrame or dictionary record(s).
        feature_list: Allowed predictive feature names in exact order.
        
    Returns:
        pd.DataFrame containing feature columns in canonical order.
    """
    if isinstance(data, dict):
        df = pd.DataFrame([data])
    elif isinstance(data, list):
        df = pd.DataFrame(data)
    else:
        df = data.copy()

    # Leakage check: Verify no prohibited column enters feature matrix
    for col in PROHIBITED_LEAKAGE_COLUMNS:
        if col in df.columns and col not in feature_list:
            pass  # Present in outer dataset, will be excluded during extraction

    missing = [f for f in feature_list if f not in df.columns]
    if missing:
        raise ValueError(f"Input record is missing required feature columns: {missing}")

    # Extract strictly the required feature list
    X = df[feature_list].copy()

    # Double-check that no leakage column is in X
    for col in PROHIBITED_LEAKAGE_COLUMNS:
        if col in X.columns:
            raise ValueError(f"DATA LEAKAGE ERROR: Prohibited column '{col}' present in prediction matrix!")

    return X


def create_shap_explainer(
    pipeline: Pipeline,
    X_background: pd.DataFrame,
) -> Tuple[shap.KernelExplainer, float]:
    """Create a SHAP KernelExplainer operating directly on pipeline probability output.
    
    Args:
        pipeline: Fitted model pipeline.
        X_background: Representative background dataset for explainer baseline.
        
    Returns:
        Tuple of (explainer: shap.KernelExplainer, baseline_expected_value: float).
    """
    feature_names = list(X_background.columns)

    # Define prediction function wrapper returning positive-class probability
    def predict_positive_proba(X_arr):
        if isinstance(X_arr, np.ndarray):
            X_df = pd.DataFrame(X_arr, columns=feature_names)
        else:
            X_df = X_arr
        return pipeline.predict_proba(X_df)[:, 1]

    explainer = shap.KernelExplainer(predict_positive_proba, X_background)
    base_val = float(explainer.expected_value)

    return explainer, base_val


def compute_shap_matrix(
    explainer: shap.KernelExplainer,
    X_sample: pd.DataFrame,
) -> np.ndarray:
    """Compute SHAP value matrix for sample records.
    
    Returns:
        2D numpy array of SHAP values matching (n_samples, n_features).
    """
    shap_values = explainer.shap_values(X_sample)
    if isinstance(shap_values, list):
        # Handle list output if multi-class
        shap_values = shap_values[1]
    return shap_values


def generate_global_explainability(
    model_path: str = "models/predictive_maintenance_model.joblib",
    metadata_path: str = "models/model_metadata.json",
    data_path: str = "data/processed/ai4i2020_cleaned.csv",
    artifacts_dir: str = "artifacts",
    sample_size: int = 150,
    background_size: int = 40,
    seed: int = 42,
) -> Dict[str, Any]:
    """Compute global SHAP feature importance metrics and save visualization artifacts."""
    print("=" * 80)
    print("PHASE 5: SHAP EXPLAINABILITY PIPELINE GENERATION")
    print("=" * 80)

    # 1. Load model, metadata, and dataset
    pipeline, metadata = load_model_and_metadata(model_path, metadata_path)
    df_raw = pd.read_csv(data_path)
    X_full = prepare_input_features(df_raw, metadata.get("features", PROPOSED_MODEL_FEATURES))

    # Stratified or representative sampling for background and explanation evaluation
    np.random.seed(seed)
    
    # Stratify sample to ensure positive failure cases are included in global SHAP
    failures_idx = df_raw[df_raw[TARGET_COLUMN] == 1].index
    normal_idx = df_raw[df_raw[TARGET_COLUMN] == 0].index
    
    sample_failures = np.random.choice(failures_idx, size=min(30, len(failures_idx)), replace=False)
    sample_normal = np.random.choice(normal_idx, size=sample_size - len(sample_failures), replace=False)
    sample_indices = np.concatenate([sample_failures, sample_normal])
    
    X_sample = X_full.iloc[sample_indices].reset_index(drop=True)
    
    background_indices = np.random.choice(len(X_full), size=background_size, replace=False)
    X_background = X_full.iloc[background_indices].reset_index(drop=True)

    print(f"\n[1/4] Background size: {len(X_background)} | Sample size for SHAP: {len(X_sample)}")

    # 2. Build explainer and compute SHAP matrix
    print("\n[2/4] Computing SHAP values across feature matrix...")
    explainer, base_expected_val = create_shap_explainer(pipeline, X_background)
    shap_matrix = compute_shap_matrix(explainer, X_sample)

    # 3. Calculate Global Feature Importance (Mean Absolute SHAP Value)
    mean_abs_shap = np.abs(shap_matrix).mean(axis=0)
    feature_names = list(X_sample.columns)
    
    importance_df = pd.DataFrame({
        "feature": feature_names,
        "mean_abs_shap_value": mean_abs_shap,
    }).sort_values(by="mean_abs_shap_value", ascending=False).reset_index(drop=True)
    importance_df["rank"] = importance_df.index + 1

    # Save CSV artifact
    os.makedirs(artifacts_dir, exist_ok=True)
    csv_path = os.path.join(artifacts_dir, "shap_feature_importance.csv")
    importance_df.to_csv(csv_path, index=False)
    print(f"  -> Feature importance table saved to '{csv_path}'")

    # 4. Save Plots (Bar Plot & Beeswarm Summary Plot)
    print("\n[3/4] Generating SHAP Visualization Artifacts...")
    
    # Plot A: Global Feature Importance Bar Plot
    plt.figure(figsize=(8, 5))
    plt.barh(importance_df["feature"][::-1], importance_df["mean_abs_shap_value"][::-1], color="navy")
    plt.xlabel("Mean |SHAP Value| (Impact on Failure Probability)")
    plt.title(f"Global Feature Importance ({metadata.get('model_name', 'Model')})")
    plt.tight_layout()
    bar_plot_path = os.path.join(artifacts_dir, "shap_feature_importance.png")
    plt.savefig(bar_plot_path, dpi=150)
    plt.close()

    # Plot B: SHAP Beeswarm Summary Plot
    plt.figure(figsize=(9, 6))
    shap.summary_plot(shap_matrix, X_sample, show=False)
    plt.title(f"SHAP Summary Beeswarm Plot ({metadata.get('model_name', 'Model')})", fontsize=12)
    plt.tight_layout()
    beeswarm_path = os.path.join(artifacts_dir, "shap_summary.png")
    plt.savefig(beeswarm_path, dpi=150)
    plt.close()

    print(f"  -> Importance Bar Plot saved to '{bar_plot_path}'")
    print(f"  -> Beeswarm Summary Plot saved to '{beeswarm_path}'")

    # 5. Save Report Artifact JSON
    report = {
        "model_path": model_path,
        "model_name": metadata.get("model_name", "Unknown"),
        "selected_threshold": metadata.get("selected_threshold", 0.5),
        "baseline_expected_value_proba": round(base_expected_val, 6),
        "sample_size": len(X_sample),
        "background_size": len(X_background),
        "feature_importance_ranking": importance_df.to_dict(orient="records"),
        "artifacts_created": [
            bar_plot_path,
            beeswarm_path,
            csv_path,
            os.path.join(artifacts_dir, "shap_report.json"),
        ],
    }

    report_path = os.path.join(artifacts_dir, "shap_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"\n[4/4] Complete SHAP report saved to '{report_path}'.")
    print("=" * 80 + "\n")

    return report


def explain_single_prediction(
    input_record: Dict[str, Any],
    model_path: str = "models/predictive_maintenance_model.joblib",
    metadata_path: str = "models/model_metadata.json",
    X_background: Optional[pd.DataFrame] = None,
    tolerance: float = 1e-4,
) -> Dict[str, Any]:
    """Generate local SHAP feature contribution explanation for an individual prediction.
    
    Args:
        input_record: Dictionary containing telemetry sensor values.
        model_path: Path to serialized model pipeline.
        metadata_path: Path to model metadata JSON.
        X_background: Optional custom background dataset for explainer.
        tolerance: Numerical tolerance for SHAP additive sum identity check.
        
    Returns:
        Structured local explanation dictionary.
    """
    pipeline, metadata = load_model_and_metadata(model_path, metadata_path)
    features = metadata.get("features", PROPOSED_MODEL_FEATURES)
    threshold = float(metadata.get("selected_threshold", 0.5))

    X_single = prepare_input_features(input_record, features)

    # If background dataset is not provided, load a small subset from processed benchmark
    if X_background is None:
        benchmark_path = "data/processed/ai4i2020_cleaned.csv"
        if os.path.exists(benchmark_path):
            df_bm = pd.read_csv(benchmark_path)
            X_background = prepare_input_features(df_bm, features).sample(n=40, random_state=42)
        else:
            X_background = X_single.copy()

    # Predict positive-class failure probability
    proba = float(pipeline.predict_proba(X_single)[:, 1][0])
    predicted_class = int(proba >= threshold)

    # Compute SHAP explanation
    explainer, base_expected_val = create_shap_explainer(pipeline, X_background)
    shap_vals = compute_shap_matrix(explainer, X_single)[0]

    # Verify Additive Identity: base_value + sum(shap_values) == probability
    shap_sum = float(base_expected_val + np.sum(shap_vals))
    additive_check_passed = bool(abs(shap_sum - proba) <= tolerance)

    # Feature contribution breakdown
    contributions = []
    for f_name, s_val in zip(features, shap_vals):
        val_raw = input_record.get(f_name, X_single[f_name].iloc[0])
        contributions.append({
            "feature": f_name,
            "feature_value": val_raw,
            "shap_value": round(float(s_val), 6),
            "effect": "increases_risk" if s_val > 0 else "decreases_risk",
        })

    # Sort contributions
    contributions.sort(key=lambda x: abs(x["shap_value"]), reverse=True)
    top_risk_drivers = [c for c in contributions if c["shap_value"] > 0]
    top_risk_reducers = [c for c in contributions if c["shap_value"] < 0]

    # Build human-readable factual explanation text
    status_str = "FAILURE RISK" if predicted_class == 1 else "NORMAL OPERATION"
    top_driver_str = (
        f"Top risk factor: {top_risk_drivers[0]['feature']}={top_risk_drivers[0]['feature_value']} "
        f"(+{top_risk_drivers[0]['shap_value']:.4f} proba)."
        if top_risk_drivers else "No significant positive risk drivers."
    )
    
    factual_explanation = (
        f"Prediction: {status_str} (Probability: {proba:.2%}, Threshold: {threshold:.2f}). "
        f"Baseline probability: {base_expected_val:.2%}. {top_driver_str}"
    )

    return {
        "model_path": model_path,
        "model_name": metadata.get("model_name", "Model"),
        "predicted_class": predicted_class,
        "predicted_label": "Machine Failure" if predicted_class == 1 else "Normal",
        "failure_probability": round(proba, 6),
        "classification_threshold": threshold,
        "baseline_expected_probability": round(base_expected_val, 6),
        "additive_check_passed": additive_check_passed,
        "shap_sum": round(shap_sum, 6),
        "feature_contributions": contributions,
        "top_risk_drivers": top_risk_drivers[:3],
        "top_risk_reducers": top_risk_reducers[:3],
        "factual_explanation": factual_explanation,
    }


def main():
    """CLI Entrypoint for Global Explainability."""
    generate_global_explainability()


if __name__ == "__main__":
    main()
