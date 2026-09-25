"""Machine Learning Model Training, Comparison, and Evaluation Module.

Trains and evaluates candidate classifiers for binary machine failure prediction using the
cleaned AI4I 2020 dataset (data/processed/ai4i2020_cleaned.csv).

Candidates:
1. Model A — Logistic Regression (Class-weighted interpretable baseline)
2. Model B — Random Forest (Balanced subsample ensemble)
3. Model C — XGBoost (Gradient boosted decision trees with training scale_pos_weight)

Data Leakage & Governance Safeguards:
- Train/Validation/Test split (70% / 15% / 15%) is strictly stratified on target `machine_failure`.
- Preprocessing pipelines (OneHotEncoder, StandardScaler) fit ONLY on training partition.
- Validation set used for model selection and probability threshold tuning.
- Final held-out test set evaluated ONCE after model selection.
- Failure-mode indicators ('twf', 'hdf', 'pwf', 'osf', 'rnf') and identifiers ('udi', 'product_id')
  are strictly excluded from predictive model feature inputs.
"""

import json
import os
import sys
from typing import Dict, Any, Tuple, List, Optional
import pandas as pd
import numpy as np
import joblib

from sklearn.model_selection import train_test_split
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from xgboost import XGBClassifier
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    average_precision_score,
    roc_auc_score,
    confusion_matrix,
    classification_report,
    precision_recall_curve,
)
import matplotlib.pyplot as plt

# Feature governance classifications
PROPOSED_MODEL_FEATURES = [
    "type",
    "air_temperature_c",
    "process_temperature_c",
    "rotational_speed_rpm",
    "torque_nm",
    "tool_wear_min",
]
CATEGORICAL_FEATURES = ["type"]
NUMERIC_FEATURES = [
    "air_temperature_c",
    "process_temperature_c",
    "rotational_speed_rpm",
    "torque_nm",
    "tool_wear_min",
]

TARGET_COLUMN = "machine_failure"
PROHIBITED_LEAKAGE_COLUMNS = [
    "machine_failure",
    "udi",
    "product_id",
    "twf",
    "hdf",
    "pwf",
    "osf",
    "rnf",
    "air_temperature_k",
    "process_temperature_k",
    "health_index",
    "scenario",
]


def load_and_validate_dataset(
    data_path: str = "data/processed/ai4i2020_cleaned.csv",
) -> Tuple[pd.DataFrame, pd.Series]:
    """Load cleaned dataset and validate feature matrix against target leakage rules.
    
    Returns:
        Tuple of (X: pd.DataFrame, y: pd.Series)
    """
    if not os.path.exists(data_path):
        raise FileNotFoundError(
            f"Cleaned dataset not found at '{data_path}'. "
            "Please run 'python -m ml.data_preparation' first to generate processed benchmark."
        )

    df = pd.read_csv(data_path)

    # 1. Target validation
    if TARGET_COLUMN not in df.columns:
        raise ValueError(f"Target column '{TARGET_COLUMN}' missing from dataset!")

    y = df[TARGET_COLUMN].astype(int)

    # 2. Feature validation & leakage check
    missing_features = [f for f in PROPOSED_MODEL_FEATURES if f not in df.columns]
    if missing_features:
        raise ValueError(f"Missing required model features in dataset: {missing_features}")

    X = df[PROPOSED_MODEL_FEATURES].copy()

    # Leakage check: Verify no prohibited column is present in feature matrix X
    for col in PROHIBITED_LEAKAGE_COLUMNS:
        if col in X.columns:
            raise ValueError(f"DATA LEAKAGE ERROR: Prohibited column '{col}' found in model input feature matrix!")

    return X, y


def create_stratified_splits(
    X: pd.DataFrame, y: pd.Series, seed: int = 42
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.Series, pd.Series, pd.Series]:
    """Create reproducible 70% Train / 15% Validation / 15% Test stratified splits."""
    # First split: 70% Train, 30% Temp (Val + Test)
    X_train, X_temp, y_train, y_temp = train_test_split(
        X, y, test_size=0.30, random_state=seed, stratify=y
    )

    # Second split: Split 30% Temp evenly into 15% Val and 15% Test
    X_val, X_test, y_val, y_test = train_test_split(
        X_temp, y_temp, test_size=0.50, random_state=seed, stratify=y_temp
    )

    return (
        X_train.reset_index(drop=True),
        X_val.reset_index(drop=True),
        X_test.reset_index(drop=True),
        y_train.reset_index(drop=True),
        y_val.reset_index(drop=True),
        y_test.reset_index(drop=True),
    )


def build_candidate_pipelines(scale_pos_weight: float, seed: int = 42) -> Dict[str, Pipeline]:
    """Build Scikit-learn feature preprocessing and candidate model pipelines.
    
    Args:
        scale_pos_weight: Class weight for positive target computed strictly from training partition.
        seed: Random seed for reproducibility.
        
    Returns:
        Dictionary of candidate model name -> Pipeline object.
    """
    # 1. Preprocessor with scaling for Logistic Regression
    preprocessor_scaled = ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CATEGORICAL_FEATURES),
            ("num", StandardScaler(), NUMERIC_FEATURES),
        ]
    )

    # 2. Preprocessor without scaling for tree-based models (RandomForest, XGBoost)
    preprocessor_unscaled = ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CATEGORICAL_FEATURES),
            ("num", "passthrough", NUMERIC_FEATURES),
        ]
    )

    pipelines = {
        "LogisticRegression": Pipeline(
            steps=[
                ("preprocessor", preprocessor_scaled),
                (
                    "classifier",
                    LogisticRegression(
                        class_weight="balanced", random_state=seed, max_iter=1000
                    ),
                ),
            ]
        ),
        "RandomForest": Pipeline(
            steps=[
                ("preprocessor", preprocessor_unscaled),
                (
                    "classifier",
                    RandomForestClassifier(
                        n_estimators=100, class_weight="balanced_subsample", random_state=seed
                    ),
                ),
            ]
        ),
        "XGBoost": Pipeline(
            steps=[
                ("preprocessor", preprocessor_unscaled),
                (
                    "classifier",
                    XGBClassifier(
                        n_estimators=100,
                        scale_pos_weight=scale_pos_weight,
                        random_state=seed,
                        eval_metric="logloss",
                    ),
                ),
            ]
        ),
    }

    return pipelines


def evaluate_model_performance(
    pipeline: Pipeline, X: pd.DataFrame, y: pd.Series, threshold: float = 0.5
) -> Dict[str, Any]:
    """Compute comprehensive evaluation metrics for a model pipeline on given dataset.
    
    Args:
        pipeline: Fitted pipeline.
        X: Feature matrix.
        y: True binary target vector.
        threshold: Decision probability threshold for positive class prediction.
        
    Returns:
        Dictionary of computed metrics.
    """
    probas = pipeline.predict_proba(X)[:, 1]
    y_pred = (probas >= threshold).astype(int)

    cm = confusion_matrix(y, y_pred)
    tn, fp, fn, tp = cm.ravel()

    acc = float(accuracy_score(y, y_pred))
    prec = float(precision_score(y, y_pred, zero_division=0))
    rec = float(recall_score(y, y_pred, zero_division=0))
    f1 = float(f1_score(y, y_pred, zero_division=0))
    pr_auc = float(average_precision_score(y, probas))
    roc_auc = float(roc_auc_score(y, probas))

    return {
        "accuracy": acc,
        "precision": prec,
        "recall": rec,
        "f1": f1,
        "pr_auc": pr_auc,
        "roc_auc": roc_auc,
        "threshold": float(threshold),
        "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
        "support": {"negative": int((y == 0).sum()), "positive": int((y == 1).sum())},
    }


def optimize_decision_threshold(
    pipeline: Pipeline, X_val: pd.DataFrame, y_val: pd.Series
) -> Tuple[float, float]:
    """Find optimal decision probability threshold maximizing F1 score on validation set.
    
    Returns:
        Tuple of (best_threshold: float, best_f1: float)
    """
    probas = pipeline.predict_proba(X_val)[:, 1]
    best_thresh = 0.5
    best_f1 = 0.0

    threshold_grid = np.linspace(0.10, 0.90, 81)
    for thresh in threshold_grid:
        y_pred = (probas >= thresh).astype(int)
        score = f1_score(y_val, y_pred, zero_division=0)
        if score > best_f1:
            best_f1 = score
            best_thresh = thresh

    return round(float(best_thresh), 2), round(float(best_f1), 4)


def train_evaluate_and_save(
    data_path: str = "data/processed/ai4i2020_cleaned.csv",
    models_dir: str = "models",
    artifacts_dir: str = "artifacts",
    seed: int = 42,
) -> Dict[str, Any]:
    """Train candidate models, compare on validation set, select best pipeline, and evaluate on held-out test set."""
    print("=" * 80)
    print("PHASE 4: MACHINE LEARNING MODEL TRAINING AND EVALUATION")
    print("=" * 80)

    # 1. Load dataset & validate leakage
    X, y = load_and_validate_dataset(data_path)
    print(f"\n[1/5] Loaded dataset: {X.shape[0]} rows, {X.shape[1]} features")

    # 2. Stratified Data Splitting
    X_train, X_val, X_test, y_train, y_val, y_test = create_stratified_splits(X, y, seed=seed)
    
    # Calculate scale_pos_weight strictly from training partition
    n_neg = (y_train == 0).sum()
    n_pos = (y_train == 1).sum()
    scale_pos_weight = float(n_neg / n_pos)

    print(f"\n[2/5] Partition Distributions (Stratified 70% Train / 15% Val / 15% Test):")
    print(f"  - Train      : {len(X_train)} rows | Positives: {(y_train == 1).sum()} ({(y_train == 1).mean()*100:.2f}%) | scale_pos_weight={scale_pos_weight:.2f}")
    print(f"  - Validation : {len(X_val)} rows | Positives: {(y_val == 1).sum()} ({(y_val == 1).mean()*100:.2f}%)")
    print(f"  - Test       : {len(X_test)} rows | Positives: {(y_test == 1).sum()} ({(y_test == 1).mean()*100:.2f}%)")

    # 3. Build & Train Candidate Models
    candidate_pipelines = build_candidate_pipelines(scale_pos_weight=scale_pos_weight, seed=seed)
    val_comparison_records = []
    val_results_dict = {}

    print("\n[3/5] Training Candidate Models & Evaluating on Validation Set...")
    for model_name, pipeline in candidate_pipelines.items():
        # Fit strictly on training partition
        pipeline.fit(X_train, y_train)
        
        # Evaluate on validation partition at default threshold 0.5
        val_metrics = evaluate_model_performance(pipeline, X_val, y_val, threshold=0.5)
        val_results_dict[model_name] = val_metrics
        
        rec = {"model": model_name}
        rec.update(val_metrics)
        val_comparison_records.append(rec)

        print(f"  - {model_name:<20}: PR-AUC={val_metrics['pr_auc']:.4f} | ROC-AUC={val_metrics['roc_auc']:.4f} | F1={val_metrics['f1']:.4f} | Recall={val_metrics['recall']:.4f} | Precision={val_metrics['precision']:.4f}")

    # Save model comparison CSV artifact
    os.makedirs(artifacts_dir, exist_ok=True)
    comparison_df = pd.DataFrame(val_comparison_records)
    comparison_csv_path = os.path.join(artifacts_dir, "model_comparison.csv")
    comparison_df.to_csv(comparison_csv_path, index=False)
    print(f"  -> Model comparison saved to '{comparison_csv_path}'")

    # 4. Model Selection & Threshold Optimization (Validation Set ONLY)
    # Selection rule: Highest PR-AUC on Validation set
    best_model_name = max(candidate_pipelines.keys(), key=lambda name: val_results_dict[name]["pr_auc"])
    best_pipeline = candidate_pipelines[best_model_name]
    
    # Tune probability threshold on validation set for selected model
    best_threshold, val_opt_f1 = optimize_decision_threshold(best_pipeline, X_val, y_val)
    val_metrics_opt = evaluate_model_performance(best_pipeline, X_val, y_val, threshold=best_threshold)

    selection_rationale = (
        f"Selected '{best_model_name}' based on superior Validation PR-AUC ({val_results_dict[best_model_name]['pr_auc']:.4f}). "
        f"Probability threshold optimized to {best_threshold} on validation data to achieve Validation F1={val_metrics_opt['f1']:.4f}."
    )
    print(f"\n[4/5] Model Selection Result: '{best_model_name}'")
    print(f"  -> Rationale: {selection_rationale}")

    # 5. Final Evaluation on Untouched Held-Out Test Set
    print("\n[5/5] Final Single Evaluation on Untouched Held-Out Test Set...")
    test_metrics = evaluate_model_performance(best_pipeline, X_test, y_test, threshold=best_threshold)

    print(f"  - Test Accuracy     : {test_metrics['accuracy']:.4f}")
    print(f"  - Test Precision    : {test_metrics['precision']:.4f}")
    print(f"  - Test Recall       : {test_metrics['recall']:.4f}")
    print(f"  - Test F1 Score     : {test_metrics['f1']:.4f}")
    print(f"  - Test PR-AUC       : {test_metrics['pr_auc']:.4f}")
    print(f"  - Test ROC-AUC      : {test_metrics['roc_auc']:.4f}")
    print(f"  - Test Confusion Matrix: TN={test_metrics['confusion_matrix']['tn']}, FP={test_metrics['confusion_matrix']['fp']}, FN={test_metrics['confusion_matrix']['fn']}, TP={test_metrics['confusion_matrix']['tp']}")

    # 6. Save Model Binary & Metadata
    os.makedirs(models_dir, exist_ok=True)
    model_binary_path = os.path.join(models_dir, "predictive_maintenance_model.joblib")
    joblib.dump(best_pipeline, model_binary_path)

    metadata = {
        "model_name": best_model_name,
        "selected_threshold": best_threshold,
        "features": PROPOSED_MODEL_FEATURES,
        "target": TARGET_COLUMN,
        "excluded_leakage_columns": PROHIBITED_LEAKAGE_COLUMNS,
        "random_seed": seed,
        "training_dataset": data_path,
        "train_rows": len(X_train),
        "validation_rows": len(X_val),
        "test_rows": len(X_test),
        "scale_pos_weight": scale_pos_weight,
    }
    metadata_path = os.path.join(models_dir, "model_metadata.json")
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    # 7. Generate Evaluation Visualizations (Confusion Matrix & Precision-Recall Curve)
    _generate_plots(best_pipeline, X_test, y_test, best_threshold, best_model_name, artifacts_dir)

    # 8. Save Complete Evaluation Report Artifact
    full_eval_report = {
        "selection": {
            "selected_model": best_model_name,
            "optimal_threshold": best_threshold,
            "selection_rationale": selection_rationale,
        },
        "partition_counts": {
            "train": {"total": len(X_train), "positives": int((y_train == 1).sum()), "negatives": int((y_train == 0).sum())},
            "validation": {"total": len(X_val), "positives": int((y_val == 1).sum()), "negatives": int((y_val == 0).sum())},
            "test": {"total": len(X_test), "positives": int((y_test == 1).sum()), "negatives": int((y_test == 0).sum())},
        },
        "validation_comparison": val_results_dict,
        "final_test_evaluation": test_metrics,
        "classification_report_text": classification_report(
            y_test, (best_pipeline.predict_proba(X_test)[:, 1] >= best_threshold).astype(int)
        ),
    }

    eval_json_path = os.path.join(artifacts_dir, "model_evaluation.json")
    with open(eval_json_path, "w", encoding="utf-8") as f:
        json.dump(full_eval_report, f, indent=2)

    print(f"\nSaved Artifacts:")
    print(f"  - Fitted Pipeline Model : {model_binary_path}")
    print(f"  - Model Metadata        : {metadata_path}")
    print(f"  - Evaluation Report     : {eval_json_path}")
    print(f"  - Comparison CSV        : {comparison_csv_path}")
    print(f"  - Confusion Matrix Plot : {os.path.join(artifacts_dir, 'confusion_matrix.png')}")
    print(f"  - PR Curve Plot        : {os.path.join(artifacts_dir, 'precision_recall_curve.png')}")
    print("=" * 80 + "\n")

    return full_eval_report


def _generate_plots(
    pipeline: Pipeline,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    threshold: float,
    model_name: str,
    artifacts_dir: str,
):
    """Generate and save PNG plots for Confusion Matrix and Precision-Recall Curve."""
    probas = pipeline.predict_proba(X_test)[:, 1]
    y_pred = (probas >= threshold).astype(int)
    cm = confusion_matrix(y_test, y_pred)

    # Plot 1: Confusion Matrix
    plt.figure(figsize=(6, 5))
    plt.imshow(cm, interpolation="nearest", cmap=plt.cm.Blues)
    plt.title(f"Test Set Confusion Matrix ({model_name} @ t={threshold})")
    plt.colorbar()
    tick_marks = np.arange(2)
    plt.xticks(tick_marks, ["No Failure (0)", "Failure (1)"])
    plt.yticks(tick_marks, ["No Failure (0)", "Failure (1)"])
    
    # Text annotations inside grid
    thresh_val = cm.max() / 2.0
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            plt.text(
                j, i, format(cm[i, j], "d"),
                horizontalalignment="center",
                color="white" if cm[i, j] > thresh_val else "black"
            )

    plt.tight_layout()
    plt.ylabel("True Label")
    plt.xlabel("Predicted Label")
    plt.savefig(os.path.join(artifacts_dir, "confusion_matrix.png"), dpi=150)
    plt.close()

    # Plot 2: Precision-Recall Curve
    precision_vals, recall_vals, _ = precision_recall_curve(y_test, probas)
    pr_auc_val = average_precision_score(y_test, probas)

    plt.figure(figsize=(6, 5))
    plt.plot(recall_vals, precision_vals, color="b", lw=2, label=f"PR Curve (AUC = {pr_auc_val:.4f})")
    plt.xlabel("Recall")
    plt.ylabel("Precision")
    plt.title(f"Precision-Recall Curve ({model_name})")
    plt.legend(loc="lower left")
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.tight_layout()
    plt.savefig(os.path.join(artifacts_dir, "precision_recall_curve.png"), dpi=150)
    plt.close()


def main():
    """CLI execution entrypoint for model training."""
    train_evaluate_and_save()


if __name__ == "__main__":
    main()
