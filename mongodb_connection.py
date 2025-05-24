#!/usr/bin/env python3
import os
import logging
from pymongo import MongoClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)


class MongoDBPool:
    """Singleton class managing a pooled MongoDB client."""

    _instance = None
    _client = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MongoDBPool, cls).__new__(cls)
            cls._client = MongoClient(
                os.getenv("MONGODB_URI"),
                maxPoolSize=50,
                minPoolSize=10,
                maxIdleTimeMS=30000,
            )
        return cls._instance

    @property
    def client(self):
        return self._client

def get_mongodb_connection():
    """
    Establish connection to MongoDB using environment variables.
    
    Expected environment variables:
    - MONGODB_URI: MongoDB connection string (required)
    - MONGODB_DB: Database name (default: rfp_analyzer)
    
    Returns:
        tuple: (MongoClient instance, database instance)
    
    Raises:
        ValueError: If MONGODB_URI is not provided
    """
    try:
        mongodb_uri = os.getenv("MONGODB_URI")
        if not mongodb_uri:
            raise ValueError("MONGODB_URI environment variable is required")
        
        mongodb_db = os.getenv("MONGODB_DB", "rfp_analyzer")
        
        logger.info(f"Connecting to MongoDB database: {mongodb_db}")

        # Use pooled MongoDB client
        pool = MongoDBPool()
        client = pool.client
        
        # Get database instance
        db = client[mongodb_db]
        
        # Test connection
        client.server_info()
        logger.info("Successfully connected to MongoDB")
        
        return client, db
    
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {str(e)}")
        raise

