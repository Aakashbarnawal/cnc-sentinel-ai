"""Database Connection and Session Management for MongoDB Atlas and PyMongo."""

import os
import logging
from typing import Generator, Optional, Any, Tuple, Dict
from dotenv import load_dotenv
import pymongo
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

logger = logging.getLogger(__name__)

# Load environment variables from .env if present
load_dotenv(override=True)


def get_mongo_uri() -> Optional[str]:
    """Retrieve MONGODB_URI from environment variables."""
    load_dotenv(override=True)
    return os.environ.get("MONGODB_URI")


def get_mongo_db_name() -> str:
    """Retrieve MONGODB_DATABASE from environment variables with fallback."""
    load_dotenv(override=True)
    return os.environ.get("MONGODB_DATABASE", "predictive_maintenance")


_mongo_client: Optional[Any] = None
_mongo_db: Optional[Any] = None


def get_mongo_client(uri: Optional[str] = None, timeout_ms: int = 5000) -> Any:
    """Retrieve or initialize PyMongo MongoClient for MongoDB Atlas or local test fallback.
    
    Args:
        uri: Optional MongoDB connection string.
        timeout_ms: Server selection timeout in milliseconds.
    """
    global _mongo_client
    target_uri = uri or get_mongo_uri()

    if target_uri and target_uri.strip():
        # Secure connection to MongoDB Atlas / Remote URI
        client_kwargs: Dict[str, Any] = {"serverSelectionTimeoutMS": timeout_ms}
        try:
            import certifi
            client_kwargs["tlsCAFile"] = certifi.where()
        except ImportError:
            pass

        try:
            _mongo_client = pymongo.MongoClient(target_uri.strip(), **client_kwargs)
        except Exception as err:
            logger.warning(f"Could not connect to configured MONGODB_URI ({err}). Falling back to mock database.")
            try:
                import mongomock
                _mongo_client = mongomock.MongoClient()
            except ImportError:
                _mongo_client = pymongo.MongoClient("mongodb://localhost:27017", serverSelectionTimeoutMS=timeout_ms)
    else:
        # Fallback to mongomock for offline development and automated unit testing
        try:
            import mongomock
            _mongo_client = mongomock.MongoClient()
        except ImportError:
            _mongo_client = pymongo.MongoClient("mongodb://localhost:27017", serverSelectionTimeoutMS=timeout_ms)

    return _mongo_client



def get_mongo_db(db_name: Optional[str] = None) -> Any:
    """Retrieve PyMongo Database instance for MongoDB collections."""
    global _mongo_db
    target_db_name = db_name or get_mongo_db_name()
    client = get_mongo_client()
    _mongo_db = client[target_db_name]
    return _mongo_db


def test_mongo_connection() -> Tuple[bool, str]:
    """Test actual connectivity to MongoDB Atlas / Database cluster.
    
    Returns:
        Tuple of (is_connected: bool, message: str)
    """
    try:
        db = get_mongo_db()
        # Execute ping command to verify Atlas connection
        db.command("ping")
        uri_str = get_mongo_uri()
        if uri_str and uri_str.strip():
            # Sanitize URI for safe display (hide credentials)
            host_part = uri_str.split("@")[-1] if "@" in uri_str else "configured_cluster"
            # Remove query params or trailing slash for clean host display
            cluster_host = host_part.split("/")[0] if "/" in host_part else host_part
            msg = f"Connected successfully to MongoDB Atlas cluster ({cluster_host})"
        else:
            msg = "Connected successfully to Mock/Local MongoDB database"
        return True, msg
    except (ConnectionFailure, ServerSelectionTimeoutError, Exception) as e:
        return False, f"MongoDB connection failure: {str(e)}"



def init_db(db_name: Optional[str] = None):
    """Initialize MongoDB collections and indexes idempotently."""
    db = get_mongo_db(db_name)

    # 1. Machines collection index
    db["machines"].create_index([("machine_id", pymongo.ASCENDING)], unique=True)

    # 2. Telemetry Readings collection index
    db["telemetry_readings"].create_index(
        [("machine_id", pymongo.ASCENDING), ("timestamp", pymongo.ASCENDING)],
        unique=True,
    )
    db["telemetry_readings"].create_index([("reading_id", pymongo.ASCENDING)], unique=True, sparse=True)

    # 3. Prediction Records collection index
    db["prediction_records"].create_index([("machine_id", pymongo.ASCENDING)])
    db["prediction_records"].create_index([("prediction_id", pymongo.ASCENDING)], unique=True, sparse=True)

    # 4. Maintenance Events collection index
    db["maintenance_events"].create_index([("machine_id", pymongo.ASCENDING)])
    db["maintenance_events"].create_index([("event_id", pymongo.ASCENDING)], unique=True, sparse=True)


def get_db() -> Generator[Any, None, None]:
    """FastAPI Dependency generator yielding MongoDB database instance."""
    db = get_mongo_db()
    yield db
