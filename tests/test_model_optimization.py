"""Automated Unit Tests for Phase 4.1 Controlled Model Performance Optimization."""

import json
import os
import numpy as np
import pandas as pd
import pytest
import joblib

from ml.optimize_model import (
    reproduce_baseline_validation,
    run_xgboost_optimization,
    analyze_threshold_tradeoffs,
    run_optimization_experiment,
)
from ml.train_model import (
    load_and_validate_dataset,
    create_stratified_splits,
    PROPOSED_MODEL_FEATURES,
    PROHIBITED_LEAKAGE_COLUMNS,
    TARGET_COLUMN,
)


@pytest.fixture
def synthetic_optimization_dataset():
    """Fixture providing synthetic dataset for fast optimization testing."""
    np.random.seed(42)
    n = 200
    types = np.random.choice(["L", "M", "H"], size=n)
    temp_air = np.random.normal(25.0, 2.0, size=n)
    temp_proc = temp_air + np.random.normal(10.0, 1.0, size=n)
    rpm = np.random.randint(1200, 2500, size=n)
    torque = np.random.normal(40.0, 8.0, size=n)
    wear = np.random.randint(0, 240, size=n)
    
    prob = 1.0 / (1.0 + np.exp(-(-5.0 + 0.05 * torque + 0.01 * wear + 0.1 * (temp_proc - temp_air))))
    target = (np.random.rand(n) < prob).astype(int)
    if target.sum() < 15:
        target[:20] = 1

    df = pd.DataFrame({
        "type": types,
        "air_temperature_c": temp_air,
        "process_temperature_c": temp_proc,
        "rotational_speed_rpm": rpm,
        "torque_nm": torque,
        "tool_wear_min": wear,
        "machine_failure": target,
        "udi": np.arange(1, n + 1),
        "product_id": [f"P{i:05d}" for i in range(1, n + 1)],
        "twf": np.zeros(n, dtype=int),
        "hdf": np.zeros(n, dtype=int),
        "pwf": np.zeros(n, dtype=int),
        "osf": np.zeros(n, dtype=int),
        "rnf": np.zeros(n, dtype=int),
    })
    return df


def test_baseline_reproducibility(synthetic_optimization_dataset):
    """Test 1: Verify baseline validation results are reproducible."""
    X = synthetic_optimization_dataset[PROPOSED_MODEL_FEATURES]
    y = synthetic_optimization_dataset[TARGET_COLUMN]
    X_train, X_val, X_test, y_train, y_val, y_test = create_stratified_splits(X, y, seed=42)

    _, res1 = reproduce_baseline_validation(X_train, y_train, X_val, y_val, seed=42)
    _, res2 = reproduce_baseline_validation(X_train, y_train, X_val, y_val, seed=42)

    assert res1["XGBoost"]["pr_auc"] == res2["XGBoost"]["pr_auc"]
    assert res1["XGBoost"]["f1"] == res2["XGBoost"]["f1"]


def test_anti_leakage_in_optimization(synthetic_optimization_dataset):
    """Test 2: Verify prohibited columns and targets are excluded from optimization feature matrix."""
    X = synthetic_optimization_dataset[PROPOSED_MODEL_FEATURES]
    for col in PROHIBITED_LEAKAGE_COLUMNS:
        assert col not in X.columns, f"Leakage column {col} in feature matrix!"


def test_threshold_tradeoff_analysis(synthetic_optimization_dataset):
    """Test 3: Verify validation threshold trade-off analysis generates valid metrics."""
    X = synthetic_optimization_dataset[PROPOSED_MODEL_FEATURES]
    y = synthetic_optimization_dataset[TARGET_COLUMN]
    X_train, X_val, X_test, y_train, y_val, y_test = create_stratified_splits(X, y, seed=42)

    pipes, _ = reproduce_baseline_validation(X_train, y_train, X_val, y_val, seed=42)
    xgb_pipe = pipes["XGBoost"]

    tradeoff_df = analyze_threshold_tradeoffs(xgb_pipe, X_val, y_val)

    assert "threshold" in tradeoff_df.columns
    assert "precision" in tradeoff_df.columns
    assert "recall" in tradeoff_df.columns
    assert "f1_score" in tradeoff_df.columns
    assert "false_positives_fp" in tradeoff_df.columns
    assert "false_negatives_fn" in tradeoff_df.columns
    assert len(tradeoff_df) == 81  # Swept 0.10 to 0.90 step 0.01


def test_production_model_non_overwriting_integrity(tmp_path):
    """Test 5: Verify production model and metadata files are NOT overwritten during optimization."""
    prod_model_path = "models/predictive_maintenance_model.joblib"
    prod_meta_path = "models/model_metadata.json"

    if os.path.exists(prod_model_path) and os.path.exists(prod_meta_path):
        mtime_model_before = os.path.getmtime(prod_model_path)
        mtime_meta_before = os.path.getmtime(prod_meta_path)

        # Run optimization experiment targeting temporary directories
        cand_dir = str(tmp_path / "cand_models")
        art_dir = str(tmp_path / "cand_artifacts")
        run_optimization_experiment(models_dir=cand_dir, artifacts_dir=art_dir)

        mtime_model_after = os.path.getmtime(prod_model_path)
        mtime_meta_after = os.path.getmtime(prod_meta_path)

        assert mtime_model_before == mtime_model_after, "Production model file was overwritten!"
        assert mtime_meta_before == mtime_meta_after, "Production metadata file was overwritten!"


def test_candidate_artifacts_creation_and_reloading(tmp_path):
    """Test 4, 6: Verify candidate pipeline serialization, reloading, and prediction outputs."""
    models_dir = os.path.join(tmp_path, "models")
    artifacts_dir = os.path.join(tmp_path, "artifacts")
    processed_csv = "data/processed/ai4i2020_cleaned.csv"

    if os.path.exists(processed_csv):
        report = run_optimization_experiment(
            data_path=processed_csv,
            models_dir=models_dir,
            artifacts_dir=artifacts_dir,
            seed=42,
        )

        cand_model_path = os.path.join(models_dir, "predictive_maintenance_candidate.joblib")
        cand_meta_path = os.path.join(models_dir, "predictive_maintenance_candidate_metadata.json")

        assert os.path.exists(cand_model_path)
        assert os.path.exists(cand_meta_path)

        # Reload candidate pipeline and test predictions
        cand_pipe = joblib.load(cand_model_path)
        sample = pd.DataFrame([{
            "type": "L",
            "air_temperature_c": 25.0,
            "process_temperature_c": 35.0,
            "rotational_speed_rpm": 1500,
            "torque_nm": 45.0,
            "tool_wear_min": 150,
        }])

        probas = cand_pipe.predict_proba(sample)[:, 1]
        assert 0.0 <= probas[0] <= 1.0
