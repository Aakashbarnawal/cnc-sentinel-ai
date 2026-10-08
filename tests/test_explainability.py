"""Automated Unit Tests for Phase 5 Model Explainability using SHAP."""

import json
import os
import tempfile
import numpy as np
import pandas as pd
import pytest
import joblib

from ml.explainability import (
    load_model_and_metadata,
    prepare_input_features,
    create_shap_explainer,
    compute_shap_matrix,
    explain_single_prediction,
    generate_global_explainability,
)
from ml.train_model import (
    PROPOSED_MODEL_FEATURES,
    PROHIBITED_LEAKAGE_COLUMNS,
    TARGET_COLUMN,
)


@pytest.fixture
def sample_telemetry_record():
    """Fixture providing a valid single telemetry record."""
    return {
        "type": "L",
        "air_temperature_c": 25.4,
        "process_temperature_c": 35.8,
        "rotational_speed_rpm": 1420,
        "torque_nm": 48.5,
        "tool_wear_min": 185,
        "machine_failure": 0,
        "udi": 9999,
        "product_id": "L99999",
        "twf": 0,
        "hdf": 0,
        "pwf": 0,
        "osf": 0,
        "rnf": 0,
    }


def test_production_and_candidate_models_load_unmodified():
    """Test 1 & 2: Verify production and candidate models load without modification."""
    prod_pipe, prod_meta = load_model_and_metadata(
        "models/predictive_maintenance_model.joblib",
        "models/model_metadata.json",
    )
    assert prod_pipe is not None
    assert "selected_threshold" in prod_meta
    assert prod_meta["target"] == TARGET_COLUMN

    cand_path = "models/predictive_maintenance_candidate.joblib"
    cand_meta_path = "models/predictive_maintenance_candidate_metadata.json"
    if os.path.exists(cand_path) and os.path.exists(cand_meta_path):
        cand_pipe, cand_meta = load_model_and_metadata(cand_path, cand_meta_path)
        assert cand_pipe is not None
        assert "selected_threshold" in cand_meta


def test_prepare_input_features_anti_leakage(sample_telemetry_record):
    """Test 3, 4, 10: Test required feature ordering, missing feature errors, and leakage prevention."""
    X = prepare_input_features(sample_telemetry_record)

    assert list(X.columns) == PROPOSED_MODEL_FEATURES
    for col in PROHIBITED_LEAKAGE_COLUMNS:
        assert col not in X.columns

    # Missing feature error check
    invalid_record = {"type": "L", "air_temperature_c": 25.0}
    with pytest.raises(ValueError) as exc:
        prepare_input_features(invalid_record)
    assert "missing required feature columns" in str(exc.value)


def test_probability_and_threshold_from_metadata(sample_telemetry_record):
    """Test 5 & 6: Verify probability prediction is in [0,1] and threshold is read from metadata."""
    prod_pipe, prod_meta = load_model_and_metadata()
    X = prepare_input_features(sample_telemetry_record)

    proba = prod_pipe.predict_proba(X)[:, 1][0]
    assert 0.0 <= proba <= 1.0

    threshold = prod_meta["selected_threshold"]
    assert 0.10 <= threshold <= 0.90


def test_local_shap_explanation_and_additive_identity(sample_telemetry_record):
    """Test 7, 8, 12: Verify local explanation, SHAP shape alignment, and additive identity check."""
    explanation = explain_single_prediction(sample_telemetry_record)

    assert explanation["additive_check_passed"] is True
    assert abs(explanation["shap_sum"] - explanation["failure_probability"]) <= 1e-4

    assert len(explanation["feature_contributions"]) == len(PROPOSED_MODEL_FEATURES)
    assert "factual_explanation" in explanation
    assert isinstance(explanation["predicted_class"], int)


def test_global_explainability_and_artifacts(tmp_path):
    """Test 9 & 11: Verify global explainability execution, non-negative importance, and artifact creation."""
    benchmark_path = "data/processed/ai4i2020_cleaned.csv"
    if os.path.exists(benchmark_path):
        artifacts_dir = os.path.join(tmp_path, "artifacts")
        report = generate_global_explainability(
            data_path=benchmark_path,
            artifacts_dir=artifacts_dir,
            sample_size=30,
            background_size=15,
            seed=42,
        )

        assert os.path.exists(os.path.join(artifacts_dir, "shap_feature_importance.csv"))
        assert os.path.exists(os.path.join(artifacts_dir, "shap_feature_importance.png"))
        assert os.path.exists(os.path.join(artifacts_dir, "shap_summary.png"))
        assert os.path.exists(os.path.join(artifacts_dir, "shap_report.json"))

        for rank_info in report["feature_importance_ranking"]:
            assert rank_info["mean_abs_shap_value"] >= 0.0
            assert not np.isnan(rank_info["mean_abs_shap_value"])
