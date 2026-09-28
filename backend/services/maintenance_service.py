"""Service module for Maintenance Event persistence and querying in MongoDB."""

from datetime import datetime
from typing import Tuple, List, Optional, Dict, Any
import pymongo

from backend.schemas import MaintenanceCreate
from database.models import get_next_sequence_val, format_mongo_doc


def create_maintenance_event(data: MaintenanceCreate, db: Any) -> Dict[str, Any]:
    """Create a new maintenance event in MongoDB.
    
    Raises:
        ValueError: If referenced machine_id is not registered.
    """
    machine = db["machines"].find_one({"machine_id": data.machine_id})
    if not machine:
        raise ValueError(f"Machine '{data.machine_id}' does not exist. Cannot schedule maintenance for unregistered machine.")

    seq_id = get_next_sequence_val(db, "maintenance_events")
    doc = {
        "id": seq_id,
        "machine_id": data.machine_id,
        "event_type": data.event_type,
        "description": data.description,
        "event_timestamp": data.event_timestamp,
        "status": data.status,
        "created_at": datetime.utcnow(),
    }
    db["maintenance_events"].insert_one(doc)
    return format_mongo_doc(doc)


def get_maintenance_events(
    db: Any,
    machine_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Tuple[int, List[Dict[str, Any]]]:
    """Retrieve maintenance events from MongoDB with optional machine_id filter."""
    query_filter: Dict[str, Any] = {}
    if machine_id:
        query_filter["machine_id"] = machine_id

    total = db["maintenance_events"].count_documents(query_filter)
    cursor = db["maintenance_events"].find(query_filter).sort("event_timestamp", pymongo.DESCENDING).skip(offset).limit(limit)
    items = [format_mongo_doc(d) for d in cursor]
    return total, items


def get_maintenance_by_id(event_id: int, db: Any) -> Optional[Dict[str, Any]]:
    """Retrieve maintenance event by integer event_id."""
    doc = db["maintenance_events"].find_one({"id": event_id})
    return format_mongo_doc(doc)

