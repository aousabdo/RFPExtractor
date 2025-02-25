#!/usr/bin/env python3
import os
import logging
from pymongo import MongoClient
from dotenv import load_dotenv

# Configure logging
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

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