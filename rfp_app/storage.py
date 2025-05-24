import os
import logging
import streamlit as st
from mongodb_connection import get_mongodb_connection
from auth import UserAuth
from document_storage import DocumentStorage

from functools import lru_cache
from datetime import datetime
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

@st.cache_resource
def init_mongodb_auth():
    """Initialize MongoDB connection, ensure indexes, and authentication objects."""
    try:
        # Connect to MongoDB
        mongo_client, mongo_db = get_mongodb_connection()
        
        # ── Ensure analysis_results collection and indexes ─────────────────────────
        # Fast lookup by document hash, enforce uniqueness
        mongo_db.analysis_results.create_index(
            [("doc_hash", 1)],
            unique=True,
            name="idx_doc_hash"
        )
        # Optional TTL cleanup after 30 days
        mongo_db.analysis_results.create_index(
            [("timestamp", 1)],
            expireAfterSeconds=60 * 60 * 24 * 30,
            name="idx_ttl_30d"
        )
        # ────────────────────────────────────────────────────────────────────────────

        # Initialize auth and storage helpers
        auth_instance = UserAuth(mongo_db)
        document_storage = DocumentStorage(mongo_db)

        # Create initial admin user if credentials supplied
        admin_email    = os.getenv("ADMIN_EMAIL")
        admin_password = os.getenv("ADMIN_PASSWORD")
        admin_name     = os.getenv("ADMIN_NAME", "System Administrator")
        if admin_email and admin_password:
            auth_instance.create_initial_admin(admin_email, admin_password, admin_name)

        return mongo_client, mongo_db, auth_instance, document_storage

    except Exception as e:
        logger.error(f"Failed to initialize MongoDB and Auth: {str(e)}")
        st.error(f"Database connection error: {str(e)}")
        return None, None, None, None


# ── CACHE LAYER ────────────────────────────────────────────────────────────────

@lru_cache(maxsize=100)
def get_cached_analysis(document_hash: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve a prior analysis by its SHA-256 hash.
    First checks the in-memory LRU cache, then falls back to MongoDB.
    """
    try:
        _, mongo_db = get_mongodb_connection()
        record = mongo_db.analysis_results.find_one({"doc_hash": document_hash})
        return record["result"] if record else None
    except Exception as e:
        logger.error(f"Cache lookup error for hash {document_hash}: {e}")
        return None

def store_analysis_result(doc_hash: str, analysis_result: Dict[str, Any]) -> None:
    """
    Persist a fresh analysis result to MongoDB and prime the in-memory cache.
    """
    try:
        _, mongo_db = get_mongodb_connection()
        mongo_db.analysis_results.insert_one({
            "doc_hash": doc_hash,
            "result": analysis_result,
            "timestamp": datetime.utcnow()
        })
        # Clear and reload this entry into the LRU cache
        get_cached_analysis.cache_clear()
        get_cached_analysis(doc_hash)
    except Exception as e:
        logger.error(f"Failed to store analysis result for hash {doc_hash}: {e}")
