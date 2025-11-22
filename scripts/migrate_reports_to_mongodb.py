"""
Migration script to move report configurations from Oracle DB to MongoDB
Run this script once to migrate existing report configurations
"""

import logging
import sys
from datetime import datetime
sys.path.append('.')

from utils.oracle_db_utils import get_report_config, get_active_report_ids
from utils.mongo_report_config import create_report_config, bulk_insert_reports

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def migrate_reports():
    """
    Migrate all active report configurations from Oracle to MongoDB
    """
    logger.info("Starting report configuration migration from Oracle to MongoDB")
    
    try:
        report_ids = get_active_report_ids()
        
        if not report_ids:
            logger.warning("No active reports found in Oracle database")
            return
        
        logger.info(f"Found {len(report_ids)} active reports in Oracle database")
        
        reports_to_migrate = []
        failed_reports = []
        
        for report_id in report_ids:
            logger.info(f"Fetching configuration for report: {report_id}")
            config = get_report_config(report_id)
            
            if config:
                config['migrated_from_oracle'] = True
                config['migration_date'] = datetime.utcnow()
                reports_to_migrate.append(config)
            else:
                logger.error(f"Failed to fetch configuration for report: {report_id}")
                failed_reports.append(report_id)
        
        if reports_to_migrate:
            logger.info(f"Migrating {len(reports_to_migrate)} reports to MongoDB")
            count = bulk_insert_reports(reports_to_migrate)
            logger.info(f"Successfully migrated {count} reports to MongoDB")
        
        if failed_reports:
            logger.warning(f"Failed to migrate {len(failed_reports)} reports: {failed_reports}")
        
        logger.info("Migration completed successfully")
        
    except Exception as e:
        logger.error(f"Error during migration: {str(e)}")
        raise


def add_report_admin_role():
    """
    Add REPORT_ADMIN role to Oracle database if it doesn't exist
    """
    logger.info("Checking for REPORT_ADMIN role in Oracle database")
    
    try:
        from utils.oracle_db_utils import get_db_connection
        import oracledb
        
        connection = get_db_connection()
        cursor = connection.cursor()
        
        cursor.execute("""
            SELECT COUNT(*) FROM roles WHERE role_id = 'REPORT_ADMIN'
        """)
        
        count = cursor.fetchone()[0]
        
        if count == 0:
            logger.info("REPORT_ADMIN role not found, creating it")
            cursor.execute("""
                INSERT INTO roles (role_id, role_name, description, is_active, created_by)
                VALUES ('REPORT_ADMIN', 'Report Administrator', 
                        'Administrator with full access to report management and user password reset capabilities',
                        1, 'SYSTEM')
            """)
            connection.commit()
            logger.info("REPORT_ADMIN role created successfully")
        else:
            logger.info("REPORT_ADMIN role already exists")
        
        cursor.close()
        connection.close()
        
    except Exception as e:
        logger.error(f"Error adding REPORT_ADMIN role: {str(e)}")
        raise


if __name__ == '__main__':
    logger.info("=" * 60)
    logger.info("Report Configuration Migration Script")
    logger.info("=" * 60)
    
    try:
        add_report_admin_role()
        logger.info("")
        migrate_reports()
        
        logger.info("=" * 60)
        logger.info("Migration completed successfully!")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error("=" * 60)
        logger.error("Migration failed!")
        logger.error(f"Error: {str(e)}")
        logger.error("=" * 60)
        sys.exit(1)
