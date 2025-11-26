"""
Oracle Database Utilities for Report Microservice
Provides functions to interact with the report database.
"""

import json
import logging
import os
from datetime import datetime
from typing import List, Dict, Any, Optional

import oracledb

# Optional Airflow support
try:
    from airflow.models import Variable
except Exception:
    Variable = None

logger = logging.getLogger("oracle_db_utils")


# ============================================================
#  CONNECTION HANDLING
# ============================================================

def get_oracle_connection() -> oracledb.Connection:
    """
    Create an Oracle database connection using environment variables.
    """
    try:
        db_user = os.environ.get("ORACLE_USER")
        db_password = os.environ.get("ORACLE_PASSWORD")
        db_host = os.environ.get("ORACLE_HOST", "localhost")
        db_port = int(os.environ.get("ORACLE_PORT", "1521"))
        db_service = os.environ.get("ORACLE_SERVICE", "XEPDB1")

        dsn = oracledb.makedsn(db_host, db_port, service_name=db_service)

        connection = oracledb.connect(
            user=db_user,
            password=db_password,
            dsn=dsn
        )

        logger.info(f"Connected to Oracle at {db_host}:{db_port}/{db_service}")
        return connection

    except oracledb.Error as error:
        logger.error(f"Error connecting to Oracle database: {error}")
        raise


# ============================================================
#  REPORT CONFIG
# ============================================================

def get_report_config(report_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve report configuration and metadata.
    """
    connection = None
    try:
        connection = get_oracle_connection()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT report_id, report_name, description, schedule_cron,
                   view_name, order_type, sort_field, is_active
            FROM report_configs
            WHERE report_id = :report_id AND is_active = 1
        """, report_id=report_id)

        row = cursor.fetchone()
        if not row:
            logger.warning(f"No config found for report_id: {report_id}")
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

        # Report fields
        cursor.execute("""
            SELECT field_name, field_label, field_order
            FROM report_fields
            WHERE report_id = :report_id
            ORDER BY field_order
        """, report_id=report_id)

        config["report_fields"] = [row[0] for row in cursor.fetchall()]

        # Summary fields
        cursor.execute("""
            SELECT field_name, operation, label, summary_order
            FROM report_summary_fields
            WHERE report_id = :report_id
            ORDER BY summary_order
        """, report_id=report_id)

        config["summary_fields"] = [
            {"field": r[0], "operation": r[1], "label": r[2]}
            for r in cursor.fetchall()
        ]

        # Recipients
        cursor.execute("""
            SELECT email_address, recipient_type
            FROM report_recipients
            WHERE report_id = :report_id AND is_active = 1
        """, report_id=report_id)

        recipients = cursor.fetchall()
        config["email"] = {
            "recipients": [r[0] for r in recipients if r[1] == "TO"],
            "cc":         [r[0] for r in recipients if r[1] == "CC"],
            "bcc":        [r[0] for r in recipients if r[1] == "BCC"],
        }

        cursor.close()
        return config

    except oracledb.Error as error:
        logger.error(f"Database error retrieving config: {error}")
        return None
    finally:
        if connection:
            connection.close()


# ============================================================
#  REPORT EXECUTION HISTORY
# ============================================================

def start_report_execution(report_id: str, from_date: datetime,
                           to_date: datetime, dag_run_id: str) -> Optional[int]:
    """
    Insert start record and return execution_id.
    """
    connection = None

    try:
        connection = get_oracle_connection()
        cursor = connection.cursor()

        exec_id = cursor.var(oracledb.NUMBER)

        cursor.execute("""
            INSERT INTO report_execution_history
                (report_id, execution_date, start_time, status,
                 from_date, to_date, airflow_dag_run_id)
            VALUES
                (:report_id, SYSTIMESTAMP, SYSTIMESTAMP, 'RUNNING',
                 :from_date, :to_date, :dag_run_id)
            RETURNING execution_id INTO :exec_id
        """,
            report_id=report_id,
            from_date=from_date,
            to_date=to_date,
            dag_run_id=dag_run_id,
            exec_id=exec_id
        )

        execution_id = exec_id.getvalue()
        connection.commit()
        cursor.close()

        logger.info(f"Started execution {execution_id} for report {report_id}")
        return int(execution_id)

    except oracledb.Error as error:
        logger.error(f"Error starting execution: {error}")
        if connection:
            connection.rollback()
        return None
    finally:
        if connection:
            connection.close()


def complete_report_execution(execution_id: int, status: str,
                              records_processed: int = None,
                              error_message: str = None,
                              pdf_file_path: str = None,
                              mongodb_doc_id: str = None):
    """
    Mark a report execution as complete.
    """
    connection = None

    try:
        connection = get_oracle_connection()
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
        """,
            execution_id=execution_id,
            status=status,
            records_processed=records_processed,
            error_message=error_message,
            pdf_file_path=pdf_file_path,
            mongodb_doc_id=mongodb_doc_id
        )

        connection.commit()
        cursor.close()

        logger.info(f"Completed execution {execution_id} with status {status}")

    except oracledb.Error as error:
        logger.error(f"Error completing execution: {error}")
        if connection:
            connection.rollback()

    finally:
        if connection:
            connection.close()


# ============================================================
#  API RESPONSE CACHE
# ============================================================

def cache_api_response(report_id: str, execution_id: int, from_date: datetime,
                       to_date: datetime, view_name: str, order_type: str,
                       response_data: List[Dict], mongodb_doc_id: str = None):
    """
    Cache API response JSON.
    """

    connection = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        response_json = json.dumps(response_data)

        cache_hours = 24
        if Variable:
            try:
                cache_hours = int(Variable.get("cache_expiry_hours", "24"))
            except Exception:
                pass

        cursor.execute("""
            INSERT INTO api_response_cache
                (report_id, execution_id, request_timestamp,
                 from_date, to_date, view_name, order_type,
                 response_status, record_count, response_data,
                 mongodb_doc_id, cache_expiry)
            VALUES
                (:report_id, :execution_id, SYSTIMESTAMP,
                 :from_date, :to_date, :view_name, :order_type,
                 200, :record_count, :response_json,
                 :mongodb_doc_id, SYSTIMESTAMP + INTERVAL :cache_hours HOUR)
        """,
            report_id=report_id,
            execution_id=execution_id,
            from_date=from_date,
            to_date=to_date,
            view_name=view_name,
            order_type=order_type,
            record_count=len(response_data),
            response_json=response_json,
            mongodb_doc_id=mongodb_doc_id,
            cache_hours=str(cache_hours)
        )

        connection.commit()
        cursor.close()

        logger.info(f"Cached response for {execution_id}")

    except oracledb.Error as error:
        logger.error(f"Cache insert error: {error}")
        if connection:
            connection.rollback()

    finally:
        if connection:
            connection.close()


# ============================================================
#  EMAIL DELIVERY LOGGING
# ============================================================

def log_email_delivery(execution_id: int, recipient_email: str, delivery_status: str,
                       email_subject: str = None, attachment_size: int = None,
                       error_message: str = None):
    """
    Log email delivery attempt.
    """
    connection = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            INSERT INTO email_delivery_log
                (execution_id, recipient_email, send_timestamp,
                 delivery_status, email_subject, attachment_size, error_message)
            VALUES
                (:execution_id, :recipient_email, SYSTIMESTAMP,
                 :delivery_status, :email_subject, :attachment_size, :error_message)
        """,
            execution_id=execution_id,
            recipient_email=recipient_email,
            delivery_status=delivery_status,
            email_subject=email_subject,
            attachment_size=attachment_size,
            error_message=error_message
        )

        connection.commit()
        cursor.close()

        logger.info(f"Email logged for {recipient_email}")

    except oracledb.Error as error:
        logger.error(f"Email logging error: {error}")
        if connection:
            connection.rollback()

    finally:
        if connection:
            connection.close()


# ============================================================
#  ERROR LOGGING
# ============================================================

def log_error(report_id: str = None, execution_id: int = None, error_source: str = None,
              error_type: str = None, error_message: str = None, stack_trace: str = None,
              dag_id: str = None, task_id: str = None):
    """
    Log error to centralized table.
    """

    connection = None

    try:
        connection = get_oracle_connection()
        cursor = connection.cursor()

        cursor.execute("""
            INSERT INTO error_log
                (report_id, execution_id, error_source, error_type,
                 error_message, stack_trace, dag_id, task_id)
            VALUES
                (:report_id, :execution_id, :error_source, :error_type,
                 :error_message, :stack_trace, :dag_id, :task_id)
        """,
            report_id=report_id,
            execution_id=execution_id,
            error_source=error_source,
            error_type=error_type,
            error_message=error_message,
            stack_trace=stack_trace,
            dag_id=dag_id,
            task_id=task_id
        )

        connection.commit()
        cursor.close()

        logger.info(f"Logged error: {error_message}")

    except oracledb.Error as error:
        logger.error(f"Error logging error: {error}")
        if connection:
            connection.rollback()

    finally:
        if connection:
            connection.close()


# ============================================================
#  EXECUTION HISTORY
# ============================================================

def get_execution_history(report_id: str = None, days: int = 7) -> List[Dict[str, Any]]:
    """
    Retrieve execution history.
    """

    connection = None

    try:
        connection = get_oracle_connection()
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

        rows = cursor.fetchall()

        results = [{
            "execution_id": row[0],
            "report_id": row[1],
            "execution_date": row[2].isoformat() if row[2] else None,
            "status": row[3],
            "records_processed": row[4],
            "error_message": row[5],
            "pdf_file_path": row[6]
        } for row in rows]

        cursor.close()
        return results

    except oracledb.Error as error:
        logger.error(f"History retrieval error: {error}")
        return []
    finally:
        if connection:
            connection.close()
