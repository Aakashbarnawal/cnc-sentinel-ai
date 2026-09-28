"""Service module for Machine Equipment registration and Telemetry reading persistence in MongoDB."""

from datetime import datetime
from typing import Dict, Any, Tuple, List, Optional
import pymongo
from pymongo.errors import DuplicateKeyError

from backend.schemas import MachineCreate, TelemetryCreate, TelemetryBatchCreate
from database.models import get_next_sequence_val, format_mongo_doc


# =====================================================================
# MACHINE EQUIPMENT SERVICES
# =====================================================================

def register_machine(data: MachineCreate, db: Any) -> Dict[str, Any]:
    """Register a new equipment machine in MongoDB machines collection.
    
    Raises:
        ValueError: If machine_id is already registered.
    """
    existing = db["machines"].find_one({"machine_id": data.machine_id})
    if existing:
        raise ValueError(f"Machine with ID '{data.machine_id}' is already registered.")

    seq_id = get_next_sequence_val(db, "machines")
    doc = {
        "id": seq_id,
        "machine_id": data.machine_id,
        "machine_type": data.machine_type,
        "created_at": datetime.utcnow(),
    }

    try:
        db["machines"].insert_one(doc)
    except DuplicateKeyError as e:
        raise ValueError(f"Machine with ID '{data.machine_id}' is already registered.") from e

    return format_mongo_doc(doc)


def get_machines(db: Any, limit: int = 50, offset: int = 0) -> Tuple[int, List[Dict[str, Any]]]:
    """Retrieve list of registered machines from MongoDB."""
    total = db["machines"].count_documents({})
    cursor = db["machines"].find({}).sort("created_at", pymongo.DESCENDING).skip(offset).limit(limit)
    items = [format_mongo_doc(d) for d in cursor]
    return total, items


def get_machine_by_id(machine_id: str, db: Any) -> Optional[Dict[str, Any]]:
    """Retrieve machine record by string machine_id."""
    doc = db["machines"].find_one({"machine_id": machine_id})
    return format_mongo_doc(doc)


# =====================================================================
# TELEMETRY READINGS SERVICES
# =====================================================================

def create_telemetry_reading(data: TelemetryCreate, db: Any) -> Dict[str, Any]:
    """Persist a single telemetry reading in MongoDB telemetry_readings collection.
    
    Raises:
        ValueError: If duplicate (machine_id, timestamp) record exists.
    """
    existing = db["telemetry_readings"].find_one({"machine_id": data.machine_id, "timestamp": data.timestamp})
    if existing:
        raise ValueError(f"Duplicate telemetry record for machine '{data.machine_id}' at timestamp '{data.timestamp}'.")

    seq_id = get_next_sequence_val(db, "telemetry_readings")
    doc = {
        "id": seq_id,
        "machine_id": data.machine_id,
        "timestamp": data.timestamp,
        "machine_type": data.machine_type,
        "temp": data.temp,
        "vibration": data.vibration,
        "current": data.current,
        "rpm": data.rpm,
        "hours": data.hours,
        "workload": data.workload,
        "tool_wear": data.tool_wear,
        "health_index": data.health_index,
        "scenario": data.scenario,
        "created_at": datetime.utcnow(),
    }

    try:
        db["telemetry_readings"].insert_one(doc)
    except DuplicateKeyError as e:
        raise ValueError(f"Duplicate telemetry record for machine '{data.machine_id}' at timestamp '{data.timestamp}'.") from e

    return format_mongo_doc(doc)


def create_telemetry_batch(data: TelemetryBatchCreate, db: Any) -> List[Dict[str, Any]]:
    """Persist a batch of telemetry readings in MongoDB.
    
    Rolls back transaction/inserted docs on any duplicate key error to ensure atomicity.
    """
    docs_to_insert = []
    inserted_ids = []

    for item in data.readings:
        # Check duplicate prior to batch insert
        existing = db["telemetry_readings"].find_one({"machine_id": item.machine_id, "timestamp": item.timestamp})
        if existing:
            raise ValueError("Batch ingestion failed due to duplicate machine/timestamp or database integrity error.")

        seq_id = get_next_sequence_val(db, "telemetry_readings")
        doc = {
            "id": seq_id,
            "machine_id": item.machine_id,
            "timestamp": item.timestamp,
            "machine_type": item.machine_type,
            "temp": item.temp,
            "vibration": item.vibration,
            "current": item.current,
            "rpm": item.rpm,
            "hours": item.hours,
            "workload": item.workload,
            "tool_wear": item.tool_wear,
            "health_index": item.health_index,
            "scenario": item.scenario,
            "created_at": datetime.utcnow(),
        }
        docs_to_insert.append(doc)

    try:
        res = db["telemetry_readings"].insert_many(docs_to_insert)
        inserted_ids = res.inserted_ids
        return [format_mongo_doc(d) for d in docs_to_insert]
    except (DuplicateKeyError, Exception) as e:
        if inserted_ids:
            db["telemetry_readings"].delete_many({"_id": {"$in": inserted_ids}})
        raise ValueError("Batch ingestion failed due to duplicate machine/timestamp or database integrity error.") from e


def get_telemetry_readings(
    db: Any,
    machine_id: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    limit: int = 50,
    offset: int = 0,
) -> Tuple[int, List[Dict[str, Any]]]:
    """Query telemetry readings with optional machine and time range filters."""
    query_filter: Dict[str, Any] = {}
    if machine_id:
        query_filter["machine_id"] = machine_id
    if start_time or end_time:
        time_filter = {}
        if start_time:
            time_filter["$gte"] = start_time
        if end_time:
            time_filter["$lte"] = end_time
        query_filter["timestamp"] = time_filter

    total = db["telemetry_readings"].count_documents(query_filter)
    cursor = db["telemetry_readings"].find(query_filter).sort("timestamp", pymongo.DESCENDING).skip(offset).limit(limit)
    items = [format_mongo_doc(d) for d in cursor]
    return total, items


def get_telemetry_by_id(reading_id: int, db: Any) -> Optional[Dict[str, Any]]:
    """Retrieve single telemetry reading by integer reading_id."""
    doc = db["telemetry_readings"].find_one({"id": reading_id})
    return format_mongo_doc(doc)
