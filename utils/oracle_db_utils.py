"""
Oracle Database Utilities for Report Microservice
Provides functions to interact with the report database
"""

import json
import logging
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
import oracledb

logger = logging.getLogger("oracle_db_utils")


def get_db_connection():
    """
    Get an Oracle database connection using credentials from environment variables
    
    Returns:
        oracledb.Connection: Database connection object
    """
    try:
        # Get connection details from environment variables
        db_user = os.environ.get("ORACLE_USER", "report_user")
        db_password = os.environ.get("ORACLE_PASSWORD", "report_password")
        db_host = os.environ.get("ORACLE_HOST", "localhost")
        db_port = os.environ.get("ORACLE_PORT", "1521")
        db_service = os.environ.get("ORACLE_SERVICE", "ORCL")
        
        # Create DSN
        dsn = oracledb.makedsn(db_host, int(db_port), service_name=db_service)
        
        # Create connection
        connection = oracledb.connect(user=db_user, password=db_password, dsn=dsn)
        
        logger.info(f"Successfully connected to Oracle database: {db_host}:{db_port}/{db_service}")
        return connection
        
    except oracledb.Error as error:
        logger.error(f"Error connecting to Oracle database: {error}")
        raise


def get_report_config(report_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve a report configuration from the database
    
    Args:
        report_id: The report ID to retrieve
        
    Returns:
        Dictionary containing the report configuration or None if not found
    """
    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Get main report config
        cursor.execute("""
            SELECT report_id, report_name, description, schedule_cron, 
                   view_name, order_type, sort_field, is_active
            FROM report_configs
            WHERE report_id = :report_id AND is_active = 1
        """, report_id=report_id)
        
        row = cursor.fetchone()
        if not row:
            logger.warning(f"Report config not found for report_id: {report_id}")
            return None
        
        config = {
            "report_id": row[0],
            "name": row[1],
            "description": row[2],
            "schedule": row[3],
            "query_parameters": {
                "view_name": row[4],
                "order_type": row[5],
                "sort_field": row[6]
            }
        }
        
        # Get report fields
        cursor.execute("""
            SELECT field_name, field_label, field_order
            FROM report_fields
            WHERE report_id = :report_id
            ORDER BY field_order
        """, report_id=report_id)
        
        config["report_fields"] = [row[0] for row in cursor.fetchall()]
        
        # Get summary fields
        cursor.execute("""
            SELECT field_name, operation, label, summary_order
            FROM report_summary_fields
            WHERE report_id = :report_id
            ORDER BY summary_order
        """, report_id=report_id)
        
        config["summary_fields"] = [
            {"field": row[0], "operation": row[1], "label": row[2]}
            for row in cursor.fetchall()
        ]
        
        # Get recipients
        cursor.execute("""
            SELECT email_address, recipient_type
            FROM report_recipients
            WHERE report_id = :report_id AND is_active = 1
        """, report_id=report_id)
        
        recipients = cursor.fetchall()
        config["email"] = {
            "recipients": [row[0] for row in recipients if row[1] == 'TO'],
            "cc": [row[0] for row in recipients if row[1] == 'CC'],
            "bcc": [row[0] for row in recipients if row[1] == 'BCC']
        }
        
        cursor.close()
        return config
        
    except oracledb.Error as error:
        logger.error(f"Database error retrieving report config: {error}")
        return None
    finally:
        if connection:
            connection.close()


def get_active_report_ids() -> List[str]:
    """
    Get list of all active report IDs
    
    Returns:
        List of active report IDs
    """
    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        cursor.execute("""
            SELECT report_id
            FROM report_configs
            WHERE is_active = 1
            ORDER BY report_id
        """)
        
        report_ids = [row[0] for row in cursor.fetchall()]
        cursor.close()
        
        logger.info(f"Retrieved {len(report_ids)} active reports")
        return report_ids
        
    except oracledb.Error as error:
        logger.error(f"Database error retrieving active reports: {error}")
        return []
    finally:
        if connection:
            connection.close()


def start_report_execution(report_id: str, from_date: datetime, to_date: datetime,
                          dag_run_id: Optional[str] = None) -> Optional[int]:
    """
    Log the start of a report execution
    
    Args:
        report_id: The report ID being executed
        from_date: Start date for the report data
        to_date: End date for the report data
        dag_run_id: Optional Airflow DAG run ID
        
    Returns:
        Execution ID if successful, None otherwise
    """
    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        exec_id_var = cursor.var(oracledb.NUMBER)
        cursor.execute("""
            INSERT INTO report_execution_history 
                (report_id, execution_date, start_time, status, from_date, to_date, airflow_dag_run_id)
            VALUES 
                (:report_id, SYSTIMESTAMP, SYSTIMESTAMP, 'RUNNING', :from_date, :to_date, :dag_run_id)
            RETURNING execution_id INTO :exec_id
        """, report_id=report_id, from_date=from_date, to_date=to_date, 
             dag_run_id=dag_run_id, exec_id=exec_id_var)
        
        execution_id = exec_id_var.getvalue()
        connection.commit()
        cursor.close()
        
        logger.info(f"Started execution {execution_id} for report {report_id}")
        return int(execution_id) if execution_id is not None else None
        
    except oracledb.Error as error:
        logger.error(f"Database error starting execution: {error}")
        if connection:
            connection.rollback()
        return None
    finally:
        if connection:
            connection.close()


def complete_report_execution(execution_id: int, status: str, records_processed: Optional[int] = None,
                              error_message: Optional[str] = None, pdf_file_path: Optional[str] = None,
                              mongodb_doc_id: Optional[str] = None):
    """
    Mark a report execution as complete
    
    Args:
        execution_id: The execution ID to update
        status: Final status ('SUCCESS', 'FAILED', 'CANCELLED')
        records_processed: Number of records processed
        error_message: Error message if failed
        pdf_file_path: Path to generated PDF file
        mongodb_doc_id: MongoDB document ID if logged
    """
    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        cursor.execute("""
            UPDATE report_execution_history
            SET end_time = SYSTIMESTAMP,
                status = :status,
                records_processed = :records_processed,
                error_message = :error_message,
                pdf_file_path = :pdf_file_path,
                mongodb_doc_id = :mongodb_doc_id
            WHERE execution_id = :execution_id
        """, execution_id=execution_id, status=status, records_processed=records_processed,
             error_message=error_message, pdf_file_path=pdf_file_path, 
             mongodb_doc_id=mongodb_doc_id)
        
        connection.commit()
        cursor.close()
        
        logger.info(f"Completed execution {execution_id} with status {status}")
        
    except oracledb.Error as error:
        logger.error(f"Database error completing execution: {error}")
        if connection:
            connection.rollback()
    finally:
        if connection:
            connection.close()


def cache_api_response(report_id: str, execution_id: int, from_date: datetime,
                      to_date: datetime, view_name: str, order_type: str,
                      response_data: List[Dict[str, Any]], mongodb_doc_id: Optional[str] = None):
    """
    Cache an API response in the database
    
    Args:
        report_id: Report ID
        execution_id: Execution ID
        from_date: Start date of query
        to_date: End date of query
        view_name: View name used in query
        order_type: Order type used in query
        response_data: The API response data
        mongodb_doc_id: MongoDB document ID if also logged there
    """
    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Convert response data to JSON string
        response_json = json.dumps(response_data)
        
        # Get cache expiry from config (default 24 hours)
        cache_value = get_system_config("cache_expiry_hours", "24")
        try:
            cache_hours = int(cache_value)
        except (TypeError, ValueError):
            cache_hours = 24
        
        cursor.execute("""
            INSERT INTO api_response_cache 
                (report_id, execution_id, request_timestamp, from_date, to_date,
                 view_name, order_type, response_status, record_count, response_data,
                 mongodb_doc_id, cache_expiry)
            VALUES 
                (:report_id, :execution_id, SYSTIMESTAMP, :from_date, :to_date,
                 :view_name, :order_type, 200, :record_count, :response_data,
                 :mongodb_doc_id, SYSTIMESTAMP + INTERVAL :cache_hours HOUR)
        """, report_id=report_id, execution_id=execution_id, from_date=from_date,
             to_date=to_date, view_name=view_name, order_type=order_type,
             record_count=len(response_data), response_data=response_json,
             mongodb_doc_id=mongodb_doc_id, cache_hours=str(cache_hours))
        
        connection.commit()
        cursor.close()
        
        logger.info(f"Cached API response for execution {execution_id}")
        
    except oracledb.Error as error:
        logger.error(f"Database error caching API response: {error}")
        if connection:
            connection.rollback()
    finally:
        if connection:
            connection.close()


def log_email_delivery(execution_id: int, recipient_email: str, delivery_status: str,
                       email_subject: Optional[str] = None, attachment_size: Optional[int] = None,
                       error_message: Optional[str] = None):
    """
    Log an email delivery attempt
    
    Args:
        execution_id: The execution ID
        recipient_email: Email address of recipient
        delivery_status: Status ('PENDING', 'SENT', 'FAILED', 'BOUNCED')
        email_subject: Email subject line
        attachment_size: Size of attachment in bytes
        error_message: Error message if failed
    """
    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        cursor.execute("""
            INSERT INTO email_delivery_log 
                (execution_id, recipient_email, send_timestamp, delivery_status,
                 email_subject, attachment_size, error_message)
            VALUES 
                (:execution_id, :recipient_email, SYSTIMESTAMP, :delivery_status,
                 :email_subject, :attachment_size, :error_message)
        """, execution_id=execution_id, recipient_email=recipient_email,
             delivery_status=delivery_status, email_subject=email_subject,
             attachment_size=attachment_size, error_message=error_message)
        
        connection.commit()
        cursor.close()
        
        logger.info(f"Logged email delivery to {recipient_email} with status {delivery_status}")
        
    except oracledb.Error as error:
        logger.error(f"Database error logging email delivery: {error}")
        if connection:
            connection.rollback()
    finally:
        if connection:
            connection.close()


def log_error(report_id: Optional[str] = None, execution_id: Optional[int] = None, error_source: Optional[str] = None,
              error_type: Optional[str] = None, error_message: Optional[str] = None, stack_trace: Optional[str] = None,
              dag_id: Optional[str] = None, task_id: Optional[str] = None):
    """
    Log an error to the centralized error log
    
    Args:
        report_id: Report ID if applicable
        execution_id: Execution ID if applicable
        error_source: Source of the error (e.g., 'API', 'PDF_GENERATION', 'EMAIL')
        error_type: Type of error (e.g., 'ConnectionError', 'ValidationError')
        error_message: Error message
        stack_trace: Full stack trace
        dag_id: Airflow DAG ID
        task_id: Airflow task ID
    """
    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        cursor.execute("""
            INSERT INTO error_log 
                (report_id, execution_id, error_source, error_type, error_message,
                 stack_trace, dag_id, task_id)
            VALUES 
                (:report_id, :execution_id, :error_source, :error_type, :error_message,
                 :stack_trace, :dag_id, :task_id)
        """, report_id=report_id, execution_id=execution_id, error_source=error_source,
             error_type=error_type, error_message=error_message, stack_trace=stack_trace,
             dag_id=dag_id, task_id=task_id)
        
        connection.commit()
        cursor.close()
        
        logger.info(f"Logged error for report {report_id}: {error_message}")
        
    except oracledb.Error as error:
        logger.error(f"Database error logging error (meta!): {error}")
        if connection:
            connection.rollback()
    finally:
        if connection:
            connection.close()


def get_system_config(config_key: str, default_value: Optional[str] = None) -> str:
    """
    Get a system configuration value
    
    Args:
        config_key: Configuration key to retrieve
        default_value: Default value if not found
        
    Returns:
        Configuration value or default
    """
    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        cursor.execute("""
            SELECT config_value
            FROM system_config
            WHERE config_key = :config_key
        """, config_key=config_key)
        
        row = cursor.fetchone()
        cursor.close()
        
        if row:
            return row[0]
        else:
            logger.warning(f"Config key {config_key} not found, using default: {default_value}")
            return default_value if default_value is not None else ""
            
    except oracledb.Error as error:
        logger.error(f"Database error retrieving config: {error}")
        return default_value if default_value is not None else ""
    finally:
        if connection:
            connection.close()


def set_system_config(config_key: str, config_value: str, config_type: str = 'STRING',
                     description: Optional[str] = None, modified_by: str = 'SYSTEM'):
    """
    Set a system configuration value
    
    Args:
        config_key: Configuration key
        config_value: Configuration value
        config_type: Type of configuration ('STRING', 'NUMBER', 'BOOLEAN', 'JSON')
        description: Description of the configuration
        modified_by: User making the modification
    """
    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        cursor.execute("""
            MERGE INTO system_config sc
            USING DUAL ON (sc.config_key = :config_key)
            WHEN MATCHED THEN
                UPDATE SET config_value = :config_value,
                          modified_date = SYSTIMESTAMP,
                          modified_by = :modified_by
            WHEN NOT MATCHED THEN
                INSERT (config_key, config_value, config_type, description, modified_by)
                VALUES (:config_key, :config_value, :config_type, :description, :modified_by)
        """, config_key=config_key, config_value=config_value, config_type=config_type,
             description=description, modified_by=modified_by)
        
        connection.commit()
        cursor.close()
        
        logger.info(f"Set system config {config_key} = {config_value}")
        
    except oracledb.Error as error:
        logger.error(f"Database error setting config: {error}")
        if connection:
            connection.rollback()
    finally:
        if connection:
            connection.close()


def get_execution_history(report_id: Optional[str] = None, days: int = 7) -> List[Dict[str, Any]]:
    """
    Get execution history for a report or all reports
    
    Args:
        report_id: Optional report ID to filter by
        days: Number of days to look back
        
    Returns:
        List of execution history records
    """
    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        if report_id:
            cursor.execute("""
                SELECT execution_id, report_id, execution_date, status, 
                       records_processed, error_message, pdf_file_path
                FROM report_execution_history
                WHERE report_id = :report_id 
                  AND execution_date >= SYSTIMESTAMP - INTERVAL :days DAY
                ORDER BY execution_date DESC
            """, report_id=report_id, days=str(days))
        else:
            cursor.execute("""
                SELECT execution_id, report_id, execution_date, status, 
                       records_processed, error_message, pdf_file_path
                FROM report_execution_history
                WHERE execution_date >= SYSTIMESTAMP - INTERVAL :days DAY
                ORDER BY execution_date DESC
            """, days=str(days))
        
        results = []
        for row in cursor.fetchall():
            results.append({
                "execution_id": row[0],
                "report_id": row[1],
                "execution_date": row[2].isoformat() if row[2] else None,
                "status": row[3],
                "records_processed": row[4],
                "error_message": row[5],
                "pdf_file_path": row[6]
            })
        
        cursor.close()
        return results
        
    except oracledb.Error as error:
        logger.error(f"Database error retrieving execution history: {error}")
        return []
    finally:
        if connection:
            connection.close()