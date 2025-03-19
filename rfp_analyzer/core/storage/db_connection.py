#!/usr/bin/env python3
import os
import logging
from pymongo import MongoClient
from dotenv import load_dotenv

# Import from our new config module
from rfp_analyzer.app.config import MONGODB_URI, MONGODB_DB

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

def get_mongodb_connection():
    """
    Establish connection to MongoDB using environment variables.
    
    Returns:
        tuple: (MongoClient instance, database instance)
    
    Raises:
        ValueError: If MONGODB_URI is not provided
    """
    try:
        mongodb_uri = MONGODB_URI or os.getenv("MONGODB_URI")
        if not mongodb_uri:
            raise ValueError("MONGODB_URI environment variable is required")
        
        mongodb_db = MONGODB_DB or os.getenv("MONGODB_DB", "rfp_analyzer")
        
        logger.info(f"Connecting to MongoDB database: {mongodb_db}")
        
        # Create a MongoDB client
        client = MongoClient(mongodb_uri)
        
        # Get database instance
        db = client[mongodb_db]
        
        # Test connection
        client.server_info()
        logger.info("Successfully connected to MongoDB")
        
        return client, db
    
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {str(e)}")
        raise