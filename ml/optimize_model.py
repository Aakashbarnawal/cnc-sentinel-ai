"""Controlled Model Performance Optimization Module (Phase 4.1).

Performs hyperparameter search, stratified cross-validation on training data, and validation
threshold trade-off analysis for machine-failure prediction.

Evaluation Integrity & Anti-Leakage Safeguards:
- Test labels, test errors, and test confusion matrices are NEVER used during hyperparameter search,
  model selection, or threshold tuning.
- Hyperparameter tuning uses 5-fold Stratified Cross-Validation strictly on X_train, y_train.
- Model selection and probability threshold optimization use X_val, y_val.
- Production model artifacts ('models/predictive_maintenance_model.joblib') are preserved intact.
  Optimized candidate is saved separately to 'models/predictive_maintenance_candidate.joblib'.
"""

import json
import os
import sys
from typing import Dict, Any, Tuple, List, Optional
import pandas as pd
import numpy as np
import joblib

from sklearn.model_selection import StratifiedKFold, RandomizedSearchCV
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
    precision_recall_curve,
)
import matplotlib.pyplot as plt

# Import project pipeline helpers and schema definitions from Phase 4
from ml.train_model import (
    load_and_validate_dataset,
    create_stratified_splits,
    evaluate_model_performance,
    build_candidate_pipelines,
    PROPOSED_MODEL_FEATURES,
    CATEGORICAL_FEATURES,
    NUMERIC_FEATURES,
    TARGET_COLUMN,
)


def reproduce_baseline_validation(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_val: pd.DataFrame,
    y_val: pd.Series,
    seed: int = 42,
) -> Tuple[Dict[str, Pipeline], Dict[str, Any]]:
    """Reproduce baseline validation results for Phase 4 candidate models."""
    n_neg = (y_train == 0).sum()
    n_pos = (y_train == 1).sum()
    scale_pos_weight = float(n_neg / n_pos)

    baseline_pipes = build_candidate_pipelines(scale_pos_weight=scale_pos_weight, seed=seed)
    metrics_results = {}
    for name, pipe in baseline_pipes.items():
        pipe.fit(X_train, y_train)
        metrics_default = evaluate_model_performance(pipe, X_val, y_val, threshold=0.5)
        metrics_results[name] = metrics_default

    return baseline_pipes, metrics_results


def run_xgboost_optimization(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    seed: int = 42,
    n_iter: int = 20,
) -> Pipeline:
    """Perform Stratified 5-Fold Cross-Validation hyperparameter optimization for XGBoost on training data."""
    preprocessor = ColumnTransformer(
        transformers=[
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CATEGORICAL_FEATURES),
            ("num", "passthrough", NUMERIC_FEATURES),
        ]
    )

    n_neg = (y_train == 0).sum()
    n_pos = (y_train == 1).sum()
    base_scale_pos_weight = float(n_neg / n_pos)

    xgb_model = XGBClassifier(random_state=seed, eval_metric="logloss")
    pipeline = Pipeline(steps=[("preprocessor", preprocessor), ("classifier", xgb_model)])

    # Hyperparameter grid for search
    param_grid = {
        "classifier__n_estimators": [100, 150, 200, 250],
        "classifier__max_depth": [3, 4, 5, 6],
        "classifier__learning_rate": [0.01, 0.03, 0.05, 0.1],
        "classifier__subsample": [0.7, 0.8, 0.9, 1.0],
        "classifier__colsample_bytree": [0.7, 0.8, 0.9, 1.0],
        "classifier__min_child_weight": [1, 3, 5],
        "classifier__gamma": [0.0, 0.1, 0.2],
        "classifier__scale_pos_weight": [
            base_scale_pos_weight * 0.8,
            base_scale_pos_weight,
            base_scale_pos_weight * 1.2,
        ],
    }

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=seed)
    search = RandomizedSearchCV(
        estimator=pipeline,
        param_distributions=param_grid,
        n_iter=n_iter,
        scoring="average_precision",
        cv=cv,
        random_state=seed,
        n_jobs=1,
    )

    search.fit(X_train, y_train)
    return search.best_estimator_, search.best_params_, search.best_score_


def analyze_threshold_tradeoffs(
    pipeline: Pipeline, X_val: pd.DataFrame, y_val: pd.Series
) -> pd.DataFrame:
    """Analyze operating precision-recall trade-offs across probability thresholds on validation set."""
    probas = pipeline.predict_proba(X_val)[:, 1]
    pr_auc = float(average_precision_score(y_val, probas))
    records = []

    thresholds = np.linspace(0.10, 0.90, 81)
    for thresh in thresholds:
        thresh = round(float(thresh), 2)
        y_pred = (probas >= thresh).astype(int)
        
        prec = float(precision_score(y_val, y_pred, zero_division=0))
        rec = float(recall_score(y_val, y_pred, zero_division=0))
        f1 = float(f1_score(y_val, y_pred, zero_division=0))
        acc = float(accuracy_score(y_val, y_pred))
        
        cm = confusion_matrix(y_val, y_pred)
        tn, fp, fn, tp = cm.ravel()

        records.append({
            "threshold": thresh,
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1_score": round(f1, 4),
            "accuracy": round(acc, 4),
            "false_positives_fp": int(fp),
            "false_negatives_fn": int(fn),
            "true_positives_tp": int(tp),
            "true_negatives_tn": int(tn),
            "pr_auc": round(pr_auc, 4),
        })

    return pd.DataFrame(records)


def run_optimization_experiment(
    data_path: str = "data/processed/ai4i2020_cleaned.csv",
    models_dir: str = "models",
    artifacts_dir: str = "artifacts",
    seed: int = 42,
) -> Dict[str, Any]:
    """Execute complete controlled model optimization experiment (Phase 4.1)."""
    print("=" * 80)
    print("PHASE 4.1: CONTROLLED MODEL PERFORMANCE OPTIMIZATION")
    print("=" * 80)

    # 1. Load dataset & validate non-leakage
    X, y = load_and_validate_dataset(data_path)
    X_train, X_val, X_test, y_train, y_val, y_test = create_stratified_splits(X, y, seed=seed)

    print(f"\n[1/5] Loaded partitions: Train={len(X_train)}, Val={len(X_val)}, Test={len(X_test)}")

    # 2. Reproduce Baseline Validation Results
    _, baseline_val_results = reproduce_baseline_validation(X_train, y_train, X_val, y_val, seed=seed)
    baseline_xgb_metrics = baseline_val_results["XGBoost"]
    print(f"\n[2/5] Baseline Validation Metrics (XGBoost @ t=0.5):")
    print(f"  - Baseline Val PR-AUC  : {baseline_xgb_metrics['pr_auc']:.4f}")
    print(f"  - Baseline Val ROC-AUC : {baseline_xgb_metrics['roc_auc']:.4f}")
    print(f"  - Baseline Val F1      : {baseline_xgb_metrics['f1']:.4f}")
    print(f"  - Baseline Val Recall  : {baseline_xgb_metrics['recall']:.4f}")

    # 3. Stratified Cross-Validation Hyperparameter Optimization (Training Data ONLY)
    print("\n[3/5] Running 5-Fold Stratified CV Hyperparameter Optimization on Training Data...")
    best_opt_pipeline, best_params, best_cv_pr_auc = run_xgboost_optimization(
        X_train, y_train, seed=seed, n_iter=25
    )
    print(f"  -> Best CV Training PR-AUC Score: {best_cv_pr_auc:.4f}")
    print("  -> Optimized Hyperparameters:")
    for param, val in best_params.items():
        print(f"     * {param}: {val}")

    # 4. Evaluate Optimized Candidate on Validation Set & Sweep Thresholds
    opt_val_metrics_default = evaluate_model_performance(best_opt_pipeline, X_val, y_val, threshold=0.5)
    tradeoff_df = analyze_threshold_tradeoffs(best_opt_pipeline, X_val, y_val)

    # Find threshold maximizing Validation F1 score
    best_tradeoff_row = tradeoff_df.loc[tradeoff_df["f1_score"].idxmax()]
    opt_threshold = float(best_tradeoff_row["threshold"])
    opt_val_metrics = evaluate_model_performance(best_opt_pipeline, X_val, y_val, threshold=opt_threshold)

    print(f"\n[4/5] Validation Evaluation for Optimized Candidate:")
    print(f"  - Optimized Val PR-AUC : {opt_val_metrics['pr_auc']:.4f} (vs Baseline: {baseline_xgb_metrics['pr_auc']:.4f})")
    print(f"  - Optimized Val ROC-AUC: {opt_val_metrics['roc_auc']:.4f} (vs Baseline: {baseline_xgb_metrics['roc_auc']:.4f})")
    print(f"  - Optimal Val Threshold: {opt_threshold}")
    print(f"  - Optimized Val F1     : {opt_val_metrics['f1']:.4f} (vs Baseline: {baseline_xgb_metrics['f1']:.4f})")
    print(f"  - Optimized Val Recall : {opt_val_metrics['recall']:.4f} (Missed Failures FN: {opt_val_metrics['confusion_matrix']['fn']})")
    print(f"  - Optimized Val Prec   : {opt_val_metrics['precision']:.4f} (False Alarms FP: {opt_val_metrics['confusion_matrix']['fp']})")

    # Determine whether optimization improved validation performance
    improved = opt_val_metrics["pr_auc"] >= baseline_xgb_metrics["pr_auc"] or opt_val_metrics["f1"] > baseline_xgb_metrics["f1"]
    
    tradeoff_discussion = (
        f"Threshold selection trade-off analysis on validation set (t={opt_threshold}): "
        f"At t={opt_threshold}, the model achieves F1={opt_val_metrics['f1']:.4f} with Recall={opt_val_metrics['recall']:.4f} "
        f"(capturing {opt_val_metrics['confusion_matrix']['tp']}/{opt_val_metrics['support']['positive']} failures) "
        f"and Precision={opt_val_metrics['precision']:.4f} ({opt_val_metrics['confusion_matrix']['fp']} false alarms). "
        f"Lowering threshold further increases failure recall but elevates false alarm rate."
    )

    # 5. Subsequent Evaluation on Existing Holdout Test Set (Disclosed as Non-Untouched)
    print("\n[5/5] Subsequent Evaluation on Existing Holdout Dataset...")
    test_metrics_opt = evaluate_model_performance(best_opt_pipeline, X_test, y_test, threshold=opt_threshold)
    print(f"  - Subsequent Test Accuracy  : {test_metrics_opt['accuracy']:.4f}")
    print(f"  - Subsequent Test Precision : {test_metrics_opt['precision']:.4f}")
    print(f"  - Subsequent Test Recall    : {test_metrics_opt['recall']:.4f}")
    print(f"  - Subsequent Test F1 Score  : {test_metrics_opt['f1']:.4f}")
    print(f"  - Subsequent Test PR-AUC    : {test_metrics_opt['pr_auc']:.4f}")
    print(f"  - Subsequent Test ROC-AUC   : {test_metrics_opt['roc_auc']:.4f}")
    print(f"  - Subsequent Test Confusion : TN={test_metrics_opt['confusion_matrix']['tn']}, FP={test_metrics_opt['confusion_matrix']['fp']}, FN={test_metrics_opt['confusion_matrix']['fn']}, TP={test_metrics_opt['confusion_matrix']['tp']}")

    # 6. Save Candidate Artifacts Separately (Preserving Production Model intact)
    os.makedirs(models_dir, exist_ok=True)
    candidate_binary_path = os.path.join(models_dir, "predictive_maintenance_candidate.joblib")
    joblib.dump(best_opt_pipeline, candidate_binary_path)

    candidate_metadata = {
        "model_name": "Optimized_XGBoost_Candidate",
        "selected_threshold": opt_threshold,
        "best_hyperparameters": best_params,
        "cv_pr_auc_score": best_cv_pr_auc,
        "features": PROPOSED_MODEL_FEATURES,
        "target": TARGET_COLUMN,
        "random_seed": seed,
        "is_production_model": False,
        "eval_integrity_note": "Evaluated using validation-only hyperparameter tuning. Test set evaluation is a subsequent check on existing holdout.",
    }
    candidate_meta_path = os.path.join(models_dir, "predictive_maintenance_candidate_metadata.json")
    with open(candidate_meta_path, "w", encoding="utf-8") as f:
        json.dump(candidate_metadata, f, indent=2)

    # Save optimization comparison CSV and report JSON
    os.makedirs(artifacts_dir, exist_ok=True)
    opt_csv_path = os.path.join(artifacts_dir, "optimization_comparison.csv")
    tradeoff_df.to_csv(opt_csv_path, index=False)

    opt_report = {
        "experiment_name": "Phase 4.1 Controlled Model Performance Optimization",
        "baseline_validation_metrics": baseline_xgb_metrics,
        "optimized_validation_metrics": opt_val_metrics,
        "subsequent_test_metrics": test_metrics_opt,
        "optimization_improved_validation": improved,
        "best_hyperparameters": best_params,
        "tradeoff_discussion": tradeoff_discussion,
        "artifacts_created": [
            candidate_binary_path,
            candidate_meta_path,
            opt_csv_path,
            os.path.join(artifacts_dir, "optimization_report.json"),
            os.path.join(artifacts_dir, "optimization_pr_tradeoff.png"),
        ],
    }

    report_path = os.path.join(artifacts_dir, "optimization_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(opt_report, f, indent=2)

    # Generate Precision-Recall Trade-off plot
    _generate_tradeoff_plot(tradeoff_df, opt_threshold, artifacts_dir)

    print(f"\nSaved Candidate Artifacts:")
    print(f"  - Candidate Model Pipeline : {candidate_binary_path}")
    print(f"  - Candidate Metadata       : {candidate_meta_path}")
    print(f"  - Optimization Report      : {report_path}")
    print(f"  - Optimization Comparison  : {opt_csv_path}")
    print(f"  - Tradeoff Plot            : {os.path.join(artifacts_dir, 'optimization_pr_tradeoff.png')}")
    print("=" * 80 + "\n")

    return opt_report


def _generate_tradeoff_plot(tradeoff_df: pd.DataFrame, opt_threshold: float, artifacts_dir: str):
    """Generate threshold trade-off visualization plot for precision, recall, and F1."""
    plt.figure(figsize=(7, 5))
    plt.plot(tradeoff_df["threshold"], tradeoff_df["precision"], label="Precision", color="blue", lw=2)
    plt.plot(tradeoff_df["threshold"], tradeoff_df["recall"], label="Recall", color="green", lw=2)
    plt.plot(tradeoff_df["threshold"], tradeoff_df["f1_score"], label="F1-Score", color="red", lw=2)
    plt.axvline(x=opt_threshold, color="black", linestyle="--", label=f"Selected Threshold ({opt_threshold})")

    plt.xlabel("Probability Decision Threshold")
    plt.ylabel("Validation Metric Score")
    plt.title("Operating Threshold Precision-Recall-F1 Trade-off")
    plt.legend(loc="lower left")
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.tight_layout()
    plt.savefig(os.path.join(artifacts_dir, "optimization_pr_tradeoff.png"), dpi=150)
    plt.close()


def main():
    """CLI Entrypoint for Model Optimization."""
    run_optimization_experiment()


if __name__ == "__main__":
    main()
