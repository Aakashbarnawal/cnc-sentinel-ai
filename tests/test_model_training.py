"""Automated Unit Tests for Phase 4 Machine Learning Model Training and Evaluation."""

import json
import os
import tempfile
import numpy as np
import pandas as pd
import pytest
import joblib

from ml.train_model import (
    load_and_validate_dataset,
    create_stratified_splits,
    build_candidate_pipelines,
    evaluate_model_performance,
    optimize_decision_threshold,
    train_evaluate_and_save,
    PROPOSED_MODEL_FEATURES,
    PROHIBITED_LEAKAGE_COLUMNS,
    TARGET_COLUMN,
)


@pytest.fixture
def synthetic_mini_dataset():
    """Fixture providing a synthetic mini-DataFrame for fast unit tests."""
    np.random.seed(42)
    n = 200
    types = np.random.choice(["L", "M", "H"], size=n)
    temp_air = np.random.normal(25.0, 2.0, size=n)
    temp_proc = temp_air + np.random.normal(10.0, 1.0, size=n)
    rpm = np.random.randint(1200, 2500, size=n)
    torque = np.random.normal(40.0, 8.0, size=n)
    wear = np.random.randint(0, 240, size=n)
    
    # Target correlated with torque, wear, and temp
    prob = 1.0 / (1.0 + np.exp(-(-5.0 + 0.05 * torque + 0.01 * wear + 0.1 * (temp_proc - temp_air))))
    target = (np.random.rand(n) < prob).astype(int)
    # Ensure at least 15 positive labels
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


def test_load_and_validate_dataset_leakage_check(tmp_path, synthetic_mini_dataset):
    """Test 1, 2, 3: Test dataset loading, feature list matching, and leakage prevention."""
    csv_path = os.path.join(tmp_path, "test_dataset.csv")
    synthetic_mini_dataset.to_csv(csv_path, index=False)

    X, y = load_and_validate_dataset(csv_path)

    assert list(X.columns) == PROPOSED_MODEL_FEATURES
    assert y.name == TARGET_COLUMN
    for col in PROHIBITED_LEAKAGE_COLUMNS:
        assert col not in X.columns


def test_reproducible_stratified_splits(synthetic_mini_dataset):
    """Test 4: Test 70/15/15 stratified train/val/test splitting."""
    X = synthetic_mini_dataset[PROPOSED_MODEL_FEATURES]
    y = synthetic_mini_dataset[TARGET_COLUMN]

    X_train, X_val, X_test, y_train, y_val, y_test = create_stratified_splits(X, y, seed=42)

    assert len(X_train) == 140
    assert len(X_val) == 30
    assert len(X_test) == 30

    # Verify stratified proportion of positive target
    ratio_all = y.mean()
    ratio_train = y_train.mean()
    ratio_val = y_val.mean()
    ratio_test = y_test.mean()

    assert abs(ratio_train - ratio_all) < 0.05
    assert abs(ratio_val - ratio_all) < 0.08
    assert abs(ratio_test - ratio_all) < 0.08


def test_candidate_pipelines_fitting_and_predictions(synthetic_mini_dataset):
    """Test 5, 6, 10: Test pipeline fitting, non-leakage preprocessing, and prediction shapes/bounds."""
    X = synthetic_mini_dataset[PROPOSED_MODEL_FEATURES]
    y = synthetic_mini_dataset[TARGET_COLUMN]
    X_train, X_val, X_test, y_train, y_val, y_test = create_stratified_splits(X, y, seed=42)

    pipelines = build_candidate_pipelines(scale_pos_weight=5.0, seed=42)

    for name, pipe in pipelines.items():
        pipe.fit(X_train, y_train)
        probas = pipe.predict_proba(X_val)

        assert probas.shape == (len(X_val), 2)
        assert np.all(probas >= 0.0) and np.all(probas <= 1.0)
        assert np.allclose(probas.sum(axis=1), 1.0)


def test_metric_calculation_and_threshold_optimization(synthetic_mini_dataset):
    """Test 7, 8: Test metric computation and validation-only threshold tuning."""
    X = synthetic_mini_dataset[PROPOSED_MODEL_FEATURES]
    y = synthetic_mini_dataset[TARGET_COLUMN]
    X_train, X_val, X_test, y_train, y_val, y_test = create_stratified_splits(X, y, seed=42)

    pipelines = build_candidate_pipelines(scale_pos_weight=5.0, seed=42)
    rf_pipe = pipelines["RandomForest"]
    rf_pipe.fit(X_train, y_train)

    metrics = evaluate_model_performance(rf_pipe, X_val, y_val, threshold=0.5)
    assert "accuracy" in metrics
    assert "precision" in metrics
    assert "recall" in metrics
    assert "f1" in metrics
    assert "pr_auc" in metrics
    assert "roc_auc" in metrics

    opt_thresh, opt_f1 = optimize_decision_threshold(rf_pipe, X_val, y_val)
    assert 0.10 <= opt_thresh <= 0.90
    assert opt_f1 >= metrics["f1"]


def test_pipeline_serialization_and_reloading(tmp_path, synthetic_mini_dataset):
    """Test 9: Verify Joblib serialization and deserialization of fitted pipeline."""
    X = synthetic_mini_dataset[PROPOSED_MODEL_FEATURES]
    y = synthetic_mini_dataset[TARGET_COLUMN]
    X_train, X_val, X_test, y_train, y_val, y_test = create_stratified_splits(X, y, seed=42)

    pipe = build_candidate_pipelines(scale_pos_weight=5.0, seed=42)["LogisticRegression"]
    pipe.fit(X_train, y_train)

    model_file = os.path.join(tmp_path, "model.joblib")
    joblib.dump(pipe, model_file)

    reloaded_pipe = joblib.load(model_file)
    p_orig = pipe.predict_proba(X_test)
    p_reload = reloaded_pipe.predict_proba(X_test)

    np.testing.assert_array_almost_equal(p_orig, p_reload)


def test_missing_dataset_handling():
    """Test 12: Verify FileNotFoundError when loading non-existent dataset path."""
    with pytest.raises(FileNotFoundError):
        load_and_validate_dataset("data/non_existent_file.csv")


def test_full_training_integration_artifacts(tmp_path):
    """Test 11: Integration test for train_evaluate_and_save generating all expected artifacts."""
    processed_csv = "data/processed/ai4i2020_cleaned.csv"
    if os.path.exists(processed_csv):
        models_dir = os.path.join(tmp_path, "models")
        artifacts_dir = os.path.join(tmp_path, "artifacts")

        report = train_evaluate_and_save(
            data_path=processed_csv,
            models_dir=models_dir,
            artifacts_dir=artifacts_dir,
            seed=42,
        )

        assert os.path.exists(os.path.join(models_dir, "predictive_maintenance_model.joblib"))
        assert os.path.exists(os.path.join(models_dir, "model_metadata.json"))
        assert os.path.exists(os.path.join(artifacts_dir, "model_evaluation.json"))
        assert os.path.exists(os.path.join(artifacts_dir, "model_comparison.csv"))
        assert os.path.exists(os.path.join(artifacts_dir, "confusion_matrix.png"))
        assert os.path.exists(os.path.join(artifacts_dir, "precision_recall_curve.png"))
