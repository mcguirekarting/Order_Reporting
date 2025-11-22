# utils/mongo_utils.py
import json
import logging
import os
from datetime import datetime
from pymongo import MongoClient
from airflow.models import Variable

logger = logging.getLogger("mongo_utils")

def get_mongo_client():
    """
    Get a MongoDB client using connection details from environment variables or Airflow variables
    
    Returns:
        MongoClient: A configured MongoDB client
    """
    # Try to get connection string from environment or Airflow variables
    connection_string = os.environ.get(
        "MONGODB_CONNECTION_STRING", 
        Variable.get("mongodb_connection_string", "mongodb://mongodb:27017/")
    )
    
    try:
        client = MongoClient(connection_string, serverSelectionTimeoutMS=5000)
        # Test connection
        client.server_info()
        logger.info("Successfully connected to MongoDB")
        return client
    except Exception as e:
        logger.error(f"Error connecting to MongoDB: {str(e)}")
        # Still return the client, so calling code can handle errors appropriately
        return client

def log_api_response(response_data, report_id=None, query_params=None):
    """
    Log an API response to MongoDB
    
    Args:
        response_data (dict or list): The API response data to log
        report_id (str, optional): The ID of the report being generated
        query_params (dict, optional): The query parameters used in the API request
        
    Returns:
        str: The ID of the inserted document in MongoDB or None if failed
    """
    try:
        # Get MongoDB connection
        client = get_mongo_client()
        
        # Get database and collection names from environment or Airflow variables
        db_name = os.environ.get(
            "MONGODB_DATABASE", 
            Variable.get("mongodb_database", "order_reports")
        )
        collection_name = os.environ.get(
            "MONGODB_COLLECTION", 
            Variable.get("mongodb_collection", "api_responses")
        )
        
        # Access the database and collection
        db = client[db_name]
        collection = db[collection_name]
        
        # Prepare the document to insert
        document = {
            "timestamp": datetime.now(),
            "report_id": report_id,
            "query_parameters": query_params,
            "response_data": response_data,
            "record_count": len(response_data) if isinstance(response_data, list) else 1
        }
        
        # Insert the document
        result = collection.insert_one(document)
        logger.info(f"Logged API response to MongoDB with ID: {result.inserted_id}")
        
        return str(result.inserted_id)
        
    except Exception as e:
        logger.error(f"Error logging API response to MongoDB: {str(e)}")
        # Don't raise exception to avoid breaking the main workflow
        return None