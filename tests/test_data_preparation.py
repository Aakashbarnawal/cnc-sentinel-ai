"""Automated Unit Tests for Phase 3 Data Preparation and Validation."""

import os
import tempfile
import pandas as pd
import pytest

from ml.data_preparation import (
    load_raw_ai4i_dataset,
    clean_ai4i_dataset,
    validate_simulator_dataset,
    process_and_save_all,
    COLUMN_MAPPING,
    PROPOSED_MODEL_FEATURES,
    LEAKAGE_COLUMNS,
    IDENTIFIER_COLUMNS,
    TARGET_COLUMN,
    KELVIN_TO_CELSIUS_OFFSET,
)


@pytest.fixture
def sample_raw_ai4i_df():
    """Fixture providing a synthetic mini-DataFrame mirroring raw AI4I structure."""
    return pd.DataFrame({
        "UDI": [1, 2, 3, 4, 5],
        "Product ID": ["M14860", "L47181", "L47182", "L47183", "L47184"],
        "Type": ["M", "L", "L", "L", "L"],
        "Air temperature [K]": [298.1, 298.2, 298.1, 298.2, 298.2],
        "Process temperature [K]": [308.6, 308.7, 308.5, 308.6, 308.7],
        "Rotational speed [rpm]": [1551, 1408, 1498, 1433, 1408],
        "Torque [Nm]": [42.8, 46.3, 49.4, 39.5, 40.0],
        "Tool wear [min]": [0, 3, 5, 7, 9],
        "Machine failure": [0, 0, 1, 0, 1],  # Contains 2 positive failure examples
        "TWF": [0, 0, 1, 0, 0],
        "HDF": [0, 0, 0, 0, 1],
        "PWF": [0, 0, 0, 0, 0],
        "OSF": [0, 0, 0, 0, 0],
        "RNF": [0, 0, 0, 0, 0],
    })


def test_clean_ai4i_dataset_basic_transformations(sample_raw_ai4i_df):
    """Test 1: Verify basic cleaning, column renaming, and shape preservation."""
    cleaned_df, report = clean_ai4i_dataset(sample_raw_ai4i_df)

    assert cleaned_df.shape[0] == 5
    assert "air_temperature_c" in cleaned_df.columns
    assert "process_temperature_c" in cleaned_df.columns
    assert "machine_failure" in cleaned_df.columns


def test_missing_value_and_duplicate_detection(sample_raw_ai4i_df):
    """Test 2 & 3: Test duplicate removal and missing value tracking."""
    # Add a duplicate row
    duplicate_df = pd.concat([sample_raw_ai4i_df, sample_raw_ai4i_df.iloc[[0]]], ignore_index=True)
    assert duplicate_df.shape[0] == 6

    cleaned_df, report = clean_ai4i_dataset(duplicate_df)
    assert cleaned_df.shape[0] == 5
    assert report["exact_duplicates_removed"] == 1


def test_temperature_conversion(sample_raw_ai4i_df):
    """Test 4: Verify Kelvin to Celsius conversion math."""
    cleaned_df, _ = clean_ai4i_dataset(sample_raw_ai4i_df)
    
    # 298.1 K - 273.15 = 24.95 C
    expected_air_c = round(298.1 - KELVIN_TO_CELSIUS_OFFSET, 2)
    actual_air_c = cleaned_df.loc[0, "air_temperature_c"]
    assert actual_air_c == expected_air_c

    # 308.6 K - 273.15 = 35.45 C
    expected_proc_c = round(308.6 - KELVIN_TO_CELSIUS_OFFSET, 2)
    actual_proc_c = cleaned_df.loc[0, "process_temperature_c"]
    assert actual_proc_c == expected_proc_c


def test_required_column_validation():
    """Test 5: Verify ValueError when a required column is missing."""
    incomplete_df = pd.DataFrame({"UDI": [1], "Product ID": ["M14860"]})
    with pytest.raises(ValueError) as exc:
        clean_ai4i_dataset(incomplete_df)
    assert "missing required columns" in str(exc.value)


def test_target_label_validation(sample_raw_ai4i_df):
    """Test 6: Verify ValueError when target contains non-binary values."""
    invalid_target_df = sample_raw_ai4i_df.copy()
    invalid_target_df.loc[0, "Machine failure"] = 99
    with pytest.raises(ValueError) as exc:
        clean_ai4i_dataset(invalid_target_df)
    assert "contains invalid non-binary values" in str(exc.value)


def test_leakage_columns_exclusion_from_features():
    """Test 7: Verify failure mode leakage columns and IDs are excluded from proposed feature list."""
    for col in LEAKAGE_COLUMNS:
        assert col not in PROPOSED_MODEL_FEATURES, f"Leakage column {col} in model features!"
    for col in IDENTIFIER_COLUMNS:
        assert col not in PROPOSED_MODEL_FEATURES, f"Identifier column {col} in model features!"
    assert TARGET_COLUMN not in PROPOSED_MODEL_FEATURES, "Target column in model features!"


def test_preservation_of_rare_positive_failures(sample_raw_ai4i_df):
    """Test 8: Verify rare positive failure examples (Machine failure = 1) are preserved intact."""
    raw_failures = (sample_raw_ai4i_df["Machine failure"] == 1).sum()
    cleaned_df, report = clean_ai4i_dataset(sample_raw_ai4i_df)
    cleaned_failures = (cleaned_df["machine_failure"] == 1).sum()

    assert raw_failures == cleaned_failures == 2
    assert report["cleaned_target_distribution"]["1"] == 2


def test_reproducibility_of_preprocessing(sample_raw_ai4i_df):
    """Test 9: Verify processing the same DataFrame twice produces identical results."""
    cleaned1, report1 = clean_ai4i_dataset(sample_raw_ai4i_df)
    cleaned2, report2 = clean_ai4i_dataset(sample_raw_ai4i_df)

    pd.testing.assert_frame_equal(cleaned1, cleaned2)
    assert report1 == report2


def test_validate_simulator_dataset_read_only():
    """Test 10: Verify simulator dataset validation operates read-only and passes schema checks."""
    sim_path = "data/raw/simulated_telemetry.csv"
    if os.path.exists(sim_path):
        mtime_before = os.path.getmtime(sim_path)
        report = validate_simulator_dataset(sim_path)
        mtime_after = os.path.getmtime(sim_path)

        assert report["is_valid"] is True
        assert report["validation_failures"] == 0
        assert report["duplicate_keys"] == 0
        assert mtime_before == mtime_after, "Simulator dataset file was modified!"
