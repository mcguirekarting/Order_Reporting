import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from utils.mongo_utils import get_mongo_client

logger = logging.getLogger(__name__)

REPORTS_DB = "order_reports"
REPORTS_COLLECTION = "report_configurations"


def get_all_report_configs() -> List[Dict[str, Any]]:
    """
    Get all report configurations from MongoDB
    
    Returns:
        List of report configuration dictionaries
    """
    try:
        client = get_mongo_client()
        db = client[REPORTS_DB]
        collection = db[REPORTS_COLLECTION]
        
        reports = list(collection.find({}, {'_id': 0}).sort('report_id', 1))
        
        logger.info(f"Retrieved {len(reports)} report configurations")
        return reports
    except Exception as e:
        logger.error(f"Error retrieving report configurations: {str(e)}")
        return []


def get_report_config(report_id: str) -> Optional[Dict[str, Any]]:
    """
    Get a specific report configuration by report_id
    
    Args:
        report_id: The report ID to retrieve
        
    Returns:
        Report configuration dictionary or None if not found
    """
    try:
        client = get_mongo_client()
        db = client[REPORTS_DB]
        collection = db[REPORTS_COLLECTION]
        
        report = collection.find_one({'report_id': report_id}, {'_id': 0})
        
        if report:
            logger.info(f"Retrieved report configuration: {report_id}")
        else:
            logger.warning(f"Report configuration not found: {report_id}")
        
        return report
    except Exception as e:
        logger.error(f"Error retrieving report {report_id}: {str(e)}")
        return None


def create_report_config(report_data: Dict[str, Any]) -> bool:
    """
    Create a new report configuration in MongoDB
    
    Args:
        report_data: Dictionary containing report configuration
        
    Returns:
        True if successful, False otherwise
    """
    try:
        client = get_mongo_client()
        db = client[REPORTS_DB]
        collection = db[REPORTS_COLLECTION]
        
        if collection.find_one({'report_id': report_data['report_id']}):
            logger.error(f"Report ID already exists: {report_data['report_id']}")
            return False
        
        report_data['created_date'] = datetime.utcnow()
        report_data['modified_date'] = datetime.utcnow()
        
        result = collection.insert_one(report_data)
        
        if result.inserted_id:
            logger.info(f"Created report configuration: {report_data['report_id']}")
            return True
        else:
            logger.error(f"Failed to create report: {report_data['report_id']}")
            return False
    except Exception as e:
        logger.error(f"Error creating report configuration: {str(e)}")
        return False


def update_report_config(report_id: str, update_data: Dict[str, Any]) -> bool:
    """
    Update an existing report configuration
    
    Args:
        report_id: The report ID to update
        update_data: Dictionary containing updated fields
        
    Returns:
        True if successful, False otherwise
    """
    try:
        client = get_mongo_client()
        db = client[REPORTS_DB]
        collection = db[REPORTS_COLLECTION]
        
        update_data['modified_date'] = datetime.utcnow()
        
        result = collection.update_one(
            {'report_id': report_id},
            {'$set': update_data}
        )
        
        if result.modified_count > 0 or result.matched_count > 0:
            logger.info(f"Updated report configuration: {report_id}")
            return True
        else:
            logger.warning(f"Report not found for update: {report_id}")
            return False
    except Exception as e:
        logger.error(f"Error updating report {report_id}: {str(e)}")
        return False


def delete_report_config(report_id: str) -> bool:
    """
    Delete a report configuration
    
    Args:
        report_id: The report ID to delete
        
    Returns:
        True if successful, False otherwise
    """
    try:
        client = get_mongo_client()
        db = client[REPORTS_DB]
        collection = db[REPORTS_COLLECTION]
        
        result = collection.delete_one({'report_id': report_id})
        
        if result.deleted_count > 0:
            logger.info(f"Deleted report configuration: {report_id}")
            return True
        else:
            logger.warning(f"Report not found for deletion: {report_id}")
            return False
    except Exception as e:
        logger.error(f"Error deleting report {report_id}: {str(e)}")
        return False


def get_active_report_ids() -> List[str]:
    """
    Get list of all active report IDs
    
    Returns:
        List of active report IDs
    """
    try:
        client = get_mongo_client()
        db = client[REPORTS_DB]
        collection = db[REPORTS_COLLECTION]
        
        reports = collection.find({'active': True}, {'report_id': 1, '_id': 0})
        report_ids = [r['report_id'] for r in reports]
        
        logger.info(f"Retrieved {len(report_ids)} active report IDs")
        return report_ids
    except Exception as e:
        logger.error(f"Error retrieving active report IDs: {str(e)}")
        return []


def bulk_insert_reports(reports: List[Dict[str, Any]]) -> int:
    """
    Bulk insert multiple report configurations
    
    Args:
        reports: List of report configuration dictionaries
        
    Returns:
        Number of reports successfully inserted
    """
    try:
        client = get_mongo_client()
        db = client[REPORTS_DB]
        collection = db[REPORTS_COLLECTION]
        
        for report in reports:
            report['created_date'] = datetime.utcnow()
            report['modified_date'] = datetime.utcnow()
        
        result = collection.insert_many(reports, ordered=False)
        
        count = len(result.inserted_ids)
        logger.info(f"Bulk inserted {count} report configurations")
        return count
    except Exception as e:
        logger.error(f"Error bulk inserting reports: {str(e)}")
        return 0
