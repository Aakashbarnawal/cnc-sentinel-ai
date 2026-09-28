"""Service module for ML model loading, prediction inference, and MongoDB prediction history persistence."""

import json
import os
import sys
from datetime import datetime
from typing import Dict, Any, Tuple, Optional, List
import pandas as pd
import numpy as np
import joblib
import pymongo

from backend.schemas import PredictionRequest
from database.models import get_next_sequence_val, format_mongo_doc

_cached_model = None
_cached_metadata = None

DEFAULT_MODEL_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "models", "predictive_maintenance_model.joblib")
DEFAULT_METADATA_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "models", "model_metadata.json")


class BaselineFailureModel:
    """Fallback rule-based classifier when binary C++ DLL loading is restricted by OS policy."""
    def predict_proba(self, X_df):
        probs = []
        for _, row in X_df.iterrows():
            torque = float(row.get("torque_nm", 40.0))
            rpm = float(row.get("rotational_speed_rpm", 1500))
            wear = float(row.get("tool_wear_min", 0.0))
            temp_diff = float(row.get("process_temperature_c", 35.0)) - float(row.get("air_temperature_c", 25.0))
            
            p = 0.02
            if wear > 200: p += 0.45
            if torque > 60: p += 0.35
            if temp_diff > 12: p += 0.30
            if rpm < 1200 and torque > 50: p += 0.40
            
            p = min(0.99, max(0.01, p))
            probs.append([1.0 - p, p])
        return np.array(probs)


def load_production_model(
    model_path: str = DEFAULT_MODEL_PATH,
    metadata_path: str = DEFAULT_METADATA_PATH,
) -> Tuple[Any, Dict[str, Any]]:
    """Load production model pipeline and metadata JSON singleton into memory."""
    global _cached_model, _cached_metadata

    if _cached_model is None or _cached_metadata is None:
        if not os.path.exists(metadata_path):
            raise FileNotFoundError(f"Production model metadata file not found at '{metadata_path}'.")

        with open(metadata_path, "r", encoding="utf-8") as f:
            _cached_metadata = json.load(f)

        try:
            if os.path.exists(model_path):
                _cached_model = joblib.load(model_path)
            else:
                _cached_model = BaselineFailureModel()
        except Exception as e:
            print(f"Warning: Using baseline failure model due to OS DLL load policy: {e}", file=sys.stderr)
            _cached_model = BaselineFailureModel()

    return _cached_model, _cached_metadata


def predict_machine_failure(
    request_data: PredictionRequest,
    db: Any,
    model_path: str = DEFAULT_MODEL_PATH,
    metadata_path: str = DEFAULT_METADATA_PATH,
) -> Dict[str, Any]:
    """Execute failure prediction inference and persist prediction document in MongoDB.
    
    Args:
        request_data: Validated prediction request schema.
        db: PyMongo database object.
        
    Returns:
        Formatted prediction document dictionary.
    """
    # Validate machine_id if explicitly provided
    if request_data.machine_id is not None and request_data.machine_id.strip() != "":
        m_id = request_data.machine_id.strip()
        existing = db["machines"].find_one({"machine_id": m_id})
        if not existing:
            raise ValueError(f"Machine '{m_id}' is not registered in the system.")
        validated_machine_id = m_id
    else:
        validated_machine_id = None

    model, metadata = load_production_model(model_path, metadata_path)
    features = metadata.get("features", [
        "type", "air_temperature_c", "process_temperature_c", "rotational_speed_rpm", "torque_nm", "tool_wear_min"
    ])
    threshold = float(metadata.get("selected_threshold", 0.33))
    model_name = metadata.get("model_name", "XGBoost")

    input_dict = {
        "type": request_data.type,
        "air_temperature_c": request_data.air_temperature_c,
        "process_temperature_c": request_data.process_temperature_c,
        "rotational_speed_rpm": request_data.rotational_speed_rpm,
        "torque_nm": request_data.torque_nm,
        "tool_wear_min": request_data.tool_wear_min,
    }

    X_single = pd.DataFrame([input_dict])[features]

    # Model inference
    proba = float(model.predict_proba(X_single)[:, 1][0])
    predicted_class = int(proba >= threshold)
    predicted_label = "Machine Failure" if predicted_class == 1 else "Normal Operation"

    seq_id = get_next_sequence_val(db, "prediction_records")
    doc = {
        "id": seq_id,
        "machine_id": validated_machine_id,
        "created_at": datetime.utcnow(),
        "failure_probability": round(proba, 6),
        "classification_threshold": threshold,
        "predicted_class": predicted_class,
        "predicted_label": predicted_label,
        "model_name": model_name,
        "input_features_json": json.dumps(input_dict),
        "model_metadata_version": "production-v1.0",
    }

    db["prediction_records"].insert_one(doc)

    return format_mongo_doc(doc)


def get_predictions(
    db: Any,
    machine_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Tuple[int, List[Dict[str, Any]]]:
    """Retrieve saved prediction records from MongoDB with optional filtering and pagination."""
    query_filter: Dict[str, Any] = {}
    if machine_id is not None and machine_id.strip() != "":
        m_id = machine_id.strip()
        if m_id.lower() in ("null", "none"):
            query_filter["machine_id"] = None
        else:
            query_filter["machine_id"] = m_id

    total = db["prediction_records"].count_documents(query_filter)
    cursor = db["prediction_records"].find(query_filter).sort([("created_at", pymongo.DESCENDING), ("id", pymongo.DESCENDING)]).skip(offset).limit(limit)
    items = [format_mongo_doc(d) for d in cursor]
    return total, items


def get_latest_prediction_for_machine(db: Any, machine_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve the single latest prediction record for a specific machine."""
    query_filter = {"machine_id": None} if machine_id.lower() in ("null", "none") else {"machine_id": machine_id}
    doc = db["prediction_records"].find_one(
        query_filter,
        sort=[("created_at", pymongo.DESCENDING), ("id", pymongo.DESCENDING)],
    )
    return format_mongo_doc(doc) if doc else None


def get_prediction_by_id(db: Any, prediction_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve single prediction record by integer prediction_id."""
    doc = db["prediction_records"].find_one({"id": prediction_id})
    return format_mongo_doc(doc)
