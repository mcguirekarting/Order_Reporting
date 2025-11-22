-- SQL Script to drop Oracle report configuration tables
-- Run this script AFTER successfully migrating report configurations to MongoDB
-- and verifying that the MongoDB-based system is working correctly

-- WARNING: This will permanently delete all report configuration tables and data
-- Make sure you have a backup before running this script

PROMPT Dropping Oracle report configuration tables...

-- Drop tables in reverse order of dependencies to avoid foreign key constraint errors

DROP TABLE report_recipients CASCADE CONSTRAINTS PURGE;
DROP TABLE report_summary_fields CASCADE CONSTRAINTS PURGE;
DROP TABLE report_fields CASCADE CONSTRAINTS PURGE;
DROP TABLE report_configs CASCADE CONSTRAINTS PURGE;

PROMPT Report configuration tables dropped successfully.
PROMPT 
PROMPT IMPORTANT: Report configurations are now stored in MongoDB.
PROMPT Make sure all DAGs and utilities are updated to use MongoDB.
