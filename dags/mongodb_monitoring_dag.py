# dags/mongodb_reporting_dag.py
from datetime import datetime, timedelta
import logging
import json
import os
import sys
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.empty import EmptyOperator
from airflow.models import Variable
from airflow.utils.dates import days_ago

# Add utils directory to path for local imports
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("mongodb_reporting")

# Define default arguments for the DAG
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

def check_mongodb_connection(**kwargs):
    """
    Test the connection to MongoDB
    """
    try:
        from utils.mongo_utils import get_mongo_client
        
        # Attempt to connect to MongoDB
        client = get_mongo_client()
        
        # Get database name
        db_name = os.environ.get(
            "MONGODB_DATABASE", 
            Variable.get("mongodb_database", "order_reports")
        )
        
        # Get database stats
        db_stats = client[db_name].command("dbstats")
        
        # Log some basic info
        logger.info(f"Successfully connected to MongoDB")
        logger.info(f"Database: {db_name}")
        logger.info(f"Collections: {client[db_name].list_collection_names()}")
        logger.info(f"Database size: {db_stats.get('dataSize', 0) / (1024*1024):.2f} MB")
        
        return {
            "status": "success",
            "collections": client[db_name].list_collection_names(),
            "db_size_mb": db_stats.get('dataSize', 0) / (1024*1024)
        }
    except Exception as e:
        logger.error(f"Error connecting to MongoDB: {str(e)}")
        return {
            "status": "error",
            "error": str(e)
        }

def list_recent_responses(**kwargs):
    """
    List recent API responses stored in MongoDB
    """
    try:
        from utils.mongo_utils import get_mongo_client
        
        # Get MongoDB client
        client = get_mongo_client()
        
        # Get database and collection names
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
        
        # Find recent documents
        cursor = collection.find().sort("timestamp", -1).limit(10)
        
        # Convert results to a list of dictionaries
        results = []
        for doc in cursor:
            # Convert ObjectId to string
            doc['_id'] = str(doc['_id'])
            # Convert datetime to string
            if 'timestamp' in doc:
                doc['timestamp'] = doc['timestamp'].isoformat()
            
            # Extract summary data
            result = {
                "_id": doc['_id'],
                "timestamp": doc['timestamp'],
                "report_id": doc.get('report_id', 'unknown'),
                "record_count": doc.get('record_count', 0)
            }
            
            # Include query parameters summary
            if 'query_parameters' in doc:
                params = doc['query_parameters']
                result['query'] = {
                    "from_date": params.get('from_date', ''),
                    "to_date": params.get('to_date', '')
                }
            
            results.append(result)
        
        # Log summary
        logger.info(f"Found {len(results)} recent API responses")
        
        # Save results to a file
        output_file = f"/tmp/recent_responses_{kwargs['execution_date'].strftime('%Y%m%d')}.json"
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        return results
    
    except Exception as e:
        logger.error(f"Error listing recent responses: {str(e)}")
        return []

# Create the DAG
dag = DAG(
    'mongodb_reporting',
    default_args=default_args,
    description='MongoDB connection and reporting',
    schedule_interval='@daily',
    start_date=days_ago(1),
    catchup=False,
    tags=['mongodb', 'reporting'],
)

# Task 1: Check MongoDB connection
task_check_connection = PythonOperator(
    task_id='check_mongodb_connection',
    python_callable=check_mongodb_connection,
    provide_context=True,
    dag=dag,
)

# Task 2: List recent responses
task_list_responses = PythonOperator(
    task_id='list_recent_responses',
    python_callable=list_recent_responses,
    provide_context=True,
    dag=dag,
)

# Task 3: End task
task_end = EmptyOperator(
    task_id='end',
    dag=dag,
)

# Define task dependencies
task_check_connection >> task_list_responses >> task_end