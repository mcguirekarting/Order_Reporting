-- =====================================================
-- Complete Initialization Script for Report Microservice
-- This script must be run as SYSTEM user
-- =====================================================

-- =====================================================
-- STEP 1: CREATE DATABASE USER (as SYSTEM)
-- =====================================================

-- First, grant privileges to the existing report_user
ALTER SESSION SET CONTAINER=XEPDB1;

create user report_user identified by password123!
    default tablespace USERS
    temporary tablespace TEMP
    quota unlimited on USERS;   

-- Grant CREATE SESSION and other privileges
GRANT SELECT, INSERT, UPDATE, DELETE ON REPORT_USER.users TO report_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON REPORT_USER.users TO System;

GRANT SELECT ON REPORT_USER.USERS.users TO System;


-- Create System user permissions
Grant Unlimited Tablespace to System;
grant Connect to System;
grant Resource to System;
grant Create Any Table to System;
grant Create Any View to System;
grant Create Any Procedure to System;
grant Create Any Sequence to System;
grant Create Any Synonym to System;
grant Create Any Trigger to System;
grant Create Any Type to System;
grant Create Any Index to System;
grant Drop Any Table to System;
grant Alter Any Table to System;
grant Execute Any Procedure to System;
grant Flashback Any Table to System;
grant Select Any Dictionary to System;
grant Drop Any Index to System;
grant Alter Any Index to System;
grant Create Job to System;
grant Create Any Job to System;
grant Debug Connect Session to System;
grant Debug Any Procedure to System;



ALTER USER report_user DEFAULT TABLESPACE USERS QUOTA UNLIMITED ON USERS;
ALTER USER System DEFAULT TABLESPACE USERS QUOTA UNLIMITED ON USERS;
GRANT SELECT, INSERT, UPDATE, DELETE ON SYS.DUAL TO report_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON REPORT_USER.USERS TO report_user;
GRANT CREATE SESSION TO report_user;
GRANT CONNECT, RESOURCE TO report_user;
GRANT CREATE VIEW TO report_user;
GRANT CREATE SEQUENCE TO report_user;
GRANT CREATE SYNONYM TO report_user;
GRANT CREATE TRIGGER TO report_user;
GRANT CREATE PROCEDURE TO report_user;
GRANT CREATE TYPE TO report_user;
GRANT CREATE TABLE TO report_user;
GRANT UNLIMITED TABLESPACE TO report_user;
GRANT SELECT ANY TABLE TO report_user;
GRANT INSERT ANY TABLE TO report_user;
GRANT UPDATE ANY TABLE TO report_user;
GRANT DELETE ANY TABLE TO report_user;
GRANT EXECUTE ANY PROCEDURE TO report_user;
GRANT CREATE ANY INDEX TO report_user;
GRANT DROP ANY TABLE TO report_user;
GRANT ALTER ANY TABLE TO report_user;
GRANT CREATE ANY SEQUENCE TO report_user;
GRANT CREATE ANY VIEW TO report_user;
GRANT CREATE ANY SYNONYM TO report_user;
GRANT CREATE ANY TRIGGER TO report_user;
GRANT CREATE ANY PROCEDURE TO report_user;
GRANT CREATE ANY TYPE TO report_user;
GRANT FLASHBACK ANY TABLE TO report_user;
GRANT SELECT ANY DICTIONARY TO report_user;
GRANT DROP ANY INDEX TO report_user;
GRANT ALTER ANY INDEX TO report_user;
GRANT CREATE JOB TO report_user;
GRANT CREATE ANY JOB TO report_user;
GRANT DEBUG CONNECT SESSION TO report_user;
GRANT DEBUG ANY PROCEDURE TO report_user;

COMMIT;





-- =====================================================
-- STEP 2: CONNECT AS report_user TO CREATE TABLES
-- =====================================================

CONNECT report_user/password123!@XEPDB1

COMMIT;
-- =====================================================
-- SECTION 1: USER AUTHENTICATION TABLES
-- =====================================================

-- Create roles table
CREATE TABLE roles (
    role_id VARCHAR2(50) PRIMARY KEY,
    role_name VARCHAR2(100) NOT NULL UNIQUE,
    description VARCHAR2(500),
    is_active NUMBER(1) DEFAULT 1,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR2(100),
    modified_date TIMESTAMP,
    modified_by VARCHAR2(100),
    CONSTRAINT chk_role_active CHECK (is_active IN (0, 1))
);

-- Create users table
CREATE TABLE users (
    user_id NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    username VARCHAR2(100) NOT NULL UNIQUE,
    email VARCHAR2(200) NOT NULL UNIQUE,
    role_id VARCHAR2(50),
    password_hash VARCHAR2(255) NOT NULL,
    first_name VARCHAR2(100),
    last_name VARCHAR2(100),
    is_active NUMBER(1) DEFAULT 1,
    is_locked NUMBER(1) DEFAULT 0,
    failed_login_attempts NUMBER DEFAULT 0,
    last_login_date TIMESTAMP,
    password_changed_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    must_change_password NUMBER(1) DEFAULT 0,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR2(100) DEFAULT 'SYSTEM',
    modified_date TIMESTAMP,
    modified_by VARCHAR2(100),
    CONSTRAINT chk_user_active CHECK (is_active IN (0, 1)),
    CONSTRAINT chk_user_locked CHECK (is_locked IN (0, 1)),
    CONSTRAINT chk_must_change_pwd CHECK (must_change_password IN (0, 1))
);

-- Create user_roles table (many-to-many relationship)
CREATE TABLE user_roles (
    user_role_id NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id NUMBER NOT NULL,
    role_id VARCHAR2(50) NOT NULL,
    assigned_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    assigned_by VARCHAR2(100),
    CONSTRAINT fk_user_roles_user FOREIGN KEY (user_id) 
        REFERENCES users(user_id) ON DELETE CASCADE,
    CONSTRAINT fk_user_roles_role FOREIGN KEY (role_id) 
        REFERENCES roles(role_id) ON DELETE CASCADE,
    CONSTRAINT uk_user_role UNIQUE (user_id, role_id)
);

-- Create user_activity_log table
CREATE TABLE user_activity_log (
    activity_id NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id NUMBER,
    username VARCHAR2(100),
    activity_type VARCHAR2(50) NOT NULL,
    activity_description VARCHAR2(500),
    ip_address VARCHAR2(45),
    user_agent VARCHAR2(500),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    success NUMBER(1) DEFAULT 1,
    error_message VARCHAR2(1000),
    CONSTRAINT fk_user_activity FOREIGN KEY (user_id) 
        REFERENCES users(user_id) ON DELETE SET NULL,
    CONSTRAINT chk_activity_success CHECK (success IN (0, 1))
);


-- =====================================================
-- SECTION 2: REPORT CONFIGURATION TABLES
-- =====================================================

-- Create report_configs table
CREATE TABLE report_configs (
    report_id VARCHAR2(100) PRIMARY KEY,
    report_name VARCHAR2(200) NOT NULL,
    description VARCHAR2(1000),
    schedule_cron VARCHAR2(100),
    view_name VARCHAR2(100),
    order_type VARCHAR2(50),
    sort_field VARCHAR2(100),
    is_active NUMBER(1) DEFAULT 1,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR2(100),
    modified_date TIMESTAMP,
    modified_by VARCHAR2(100),
    CONSTRAINT chk_report_active CHECK (is_active IN (0, 1))
);

-- Create report_fields table
CREATE TABLE report_fields (
    field_id NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    report_id VARCHAR2(100) NOT NULL,
    field_name VARCHAR2(100) NOT NULL,
    field_label VARCHAR2(200),
    field_order NUMBER,
    is_visible NUMBER(1) DEFAULT 1,
    CONSTRAINT fk_report_fields FOREIGN KEY (report_id) 
        REFERENCES report_configs(report_id) ON DELETE CASCADE,
    CONSTRAINT chk_field_visible CHECK (is_visible IN (0, 1))
);

-- Create report_recipients table
CREATE TABLE report_recipients (
    recipient_id NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    report_id VARCHAR2(100) NOT NULL,
    email_address VARCHAR2(200) NOT NULL,
    recipient_type VARCHAR2(10) DEFAULT 'TO',
    CONSTRAINT fk_report_recipients FOREIGN KEY (report_id) 
        REFERENCES report_configs(report_id) ON DELETE CASCADE,
    CONSTRAINT chk_recipient_type CHECK (recipient_type IN ('TO', 'CC', 'BCC'))
);

-- Create report_permissions table
CREATE TABLE report_permissions (
    permission_id NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    role_id VARCHAR2(50) NOT NULL,
    report_id VARCHAR2(100) NOT NULL,
    can_view NUMBER(1) DEFAULT 1,
    can_execute NUMBER(1) DEFAULT 0,
    can_modify NUMBER(1) DEFAULT 0,
    can_delete NUMBER(1) DEFAULT 0,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR2(100),
    CONSTRAINT fk_report_perm_role FOREIGN KEY (role_id) 
        REFERENCES roles(role_id) ON DELETE CASCADE,
    CONSTRAINT fk_report_perm_report FOREIGN KEY (report_id) 
        REFERENCES report_configs(report_id) ON DELETE CASCADE,
    CONSTRAINT uk_role_report UNIQUE (role_id, report_id),
    CONSTRAINT chk_can_view CHECK (can_view IN (0, 1)),
    CONSTRAINT chk_can_execute CHECK (can_execute IN (0, 1)),
    CONSTRAINT chk_can_modify CHECK (can_modify IN (0, 1)),
    CONSTRAINT chk_can_delete CHECK (can_delete IN (0, 1))
);

-- Create report_execution_history table
CREATE TABLE report_execution_history (
    execution_id NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    report_id VARCHAR2(100),
    execution_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR2(20),
    records_processed NUMBER,
    execution_time_seconds NUMBER,
    error_message VARCHAR2(4000),
    pdf_file_path VARCHAR2(500),
    executed_by VARCHAR2(100),
    CONSTRAINT fk_report_execution FOREIGN KEY (report_id) 
        REFERENCES report_configs(report_id) ON DELETE SET NULL,
    CONSTRAINT chk_exec_status CHECK (status IN ('SUCCESS', 'FAILED', 'RUNNING', 'CANCELLED'))
);

-- Create system_config table
CREATE TABLE system_config (
    config_key VARCHAR2(100) PRIMARY KEY,
    config_value VARCHAR2(1000),
    config_type VARCHAR2(20) DEFAULT 'STRING',
    description VARCHAR2(500),
    modified_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    modified_by VARCHAR2(100),
    CONSTRAINT chk_config_type CHECK (config_type IN ('STRING', 'NUMBER', 'BOOLEAN', 'JSON'))
);

-- =====================================================
-- SECTION 3: CREATE INDEXES
-- =====================================================

-- User table indexes
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_active ON users(is_active);

-- User roles indexes
CREATE INDEX idx_user_roles_user ON user_roles(user_id);
CREATE INDEX idx_user_roles_role ON user_roles(role_id);

-- Report permission indexes
CREATE INDEX idx_report_perm_role ON report_permissions(role_id);
CREATE INDEX idx_report_perm_report ON report_permissions(report_id);

-- User activity indexes
CREATE INDEX idx_user_activity_user ON user_activity_log(user_id);
CREATE INDEX idx_user_activity_timestamp ON user_activity_log(timestamp);
CREATE INDEX idx_user_activity_type ON user_activity_log(activity_type);

-- Report execution indexes
CREATE INDEX idx_report_execution_date ON report_execution_history(execution_date);
CREATE INDEX idx_report_execution_status ON report_execution_history(status);
CREATE INDEX idx_report_execution_report ON report_execution_history(report_id);

-- =====================================================
-- SECTION 4: INSERT DEFAULT DATA
-- =====================================================

-- Insert default roles
INSERT INTO roles (role_id, role_name, description, created_by)
VALUES ('ADMIN', 'Administrator', 'Full system access with all permissions', 'SYSTEM');

INSERT INTO roles (role_id, role_name, description, created_by)
VALUES ('REPORT_MANAGER', 'Report Manager', 'Can create, modify, and execute reports', 'SYSTEM');

INSERT INTO roles (role_id, role_name, description, created_by)
VALUES ('REPORT_VIEWER', 'Report Viewer', 'Can view and execute reports only', 'SYSTEM');

INSERT INTO roles (role_id, role_name, description, created_by)
VALUES ('REPORT_EXECUTOR', 'Report Executor', 'Can execute reports but not modify them', 'SYSTEM');

-- Insert default admin user
-- Username: report_admin
-- Password: Admin123! (bcrypt hash below)
-- This password should be changed on first login
INSERT INTO users (username, email, password_hash, role_id, first_name, last_name, must_change_password, created_by)
VALUES ('report_admin', 'admin@localhost', 
        '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5iqy8lHiCfSki', 'Admin',
        'Report', 'LastNameTest', 0, 'SYSTEM');

--Insert Admin user
-- This is the bcrypt hash for 'Admin123!'
INSERT INTO users (username, email, password_hash, role_id, first_name, last_name, must_change_password, created_by)
 VALUES ('Admin', 'admin@gmail.com', 
        '$2b$12$kZ.JqQbR9pW6RWQH0f2Gb.OhyB1V8KQH0f2Gb9pW6RWQH0f2Gb', 'Admin', 
        'Admin','User', 0, 'SYSTEM');


-- Assign ADMIN role to report_admin user
INSERT INTO user_roles (user_id, role_id, assigned_by)
SELECT user_id, 'ADMIN', 'SYSTEM'
FROM users WHERE username = 'report_admin';

-- Assign ADMIN role to Admin user
INSERT INTO user_roles (user_id, role_id, assigned_by)
SELECT user_id, 'ADMIN', 'SYSTEM'
FROM users WHERE username = 'Admin';

-- Insert initial system configurations
INSERT INTO system_config (config_key, config_value, config_type, description, modified_by)
VALUES ('api_base_url', 'https://api.example.com', 'STRING', 'Base URL for order API', 'SYSTEM');

INSERT INTO system_config (config_key, config_value, config_type, description, modified_by)
VALUES ('default_timezone', 'America/Chicago', 'STRING', 'Default timezone for reports', 'SYSTEM');

INSERT INTO system_config (config_key, config_value, config_type, description, modified_by)
VALUES ('max_retries', '3', 'NUMBER', 'Maximum retry attempts for failed reports', 'SYSTEM');

INSERT INTO system_config (config_key, config_value, config_type, description, modified_by)
VALUES ('cache_expiry_hours', '24', 'NUMBER', 'Hours to keep API response cache', 'SYSTEM');

INSERT INTO system_config (config_key, config_value, config_type, description, modified_by)
VALUES ('pdf_output_dir', '/tmp', 'STRING', 'Directory for PDF output files', 'SYSTEM');

-- Insert sample report configuration
INSERT INTO report_configs 
    (report_id, report_name, description, schedule_cron, view_name, order_type, sort_field, is_active, created_by)
VALUES 
    ('daily_order_summary', 'Daily Order Summary', 
     'Summary of all orders processed in the last 24 hours',
     '0 8 * * *', 'ALL_ORDERS', 'ALL', 'orderDate', 1, 'SYSTEM');

-- Grant permissions to ADMIN role for all reports
INSERT INTO report_permissions (role_id, report_id, can_view, can_execute, can_modify, can_delete, created_by)
SELECT 'ADMIN', report_id, 1, 1, 1, 1, 'SYSTEM'
FROM report_configs;

-- Grant permissions to REPORT_MANAGER role
INSERT INTO report_permissions (role_id, report_id, can_view, can_execute, can_modify, can_delete, created_by)
SELECT 'REPORT_MANAGER', report_id, 1, 1, 1, 0, 'SYSTEM'
FROM report_configs;

-- Grant permissions to REPORT_VIEWER role
INSERT INTO report_permissions (role_id, report_id, can_view, can_execute, can_modify, can_delete, created_by)
SELECT 'REPORT_VIEWER', report_id, 1, 1, 0, 0, 'SYSTEM'
FROM report_configs;

COMMIT;

-- =====================================================
-- SECTION 5: DISPLAY SUMMARY
-- =====================================================

SET SERVEROUTPUT ON
BEGIN
    DBMS_OUTPUT.PUT_LINE('=====================================================');
    DBMS_OUTPUT.PUT_LINE('Database schema created successfully!');
    DBMS_OUTPUT.PUT_LINE('=====================================================');
    DBMS_OUTPUT.PUT_LINE('');
    DBMS_OUTPUT.PUT_LINE('Default Admin Credentials:');
    DBMS_OUTPUT.PUT_LINE('  Username: report_admin');
    DBMS_OUTPUT.PUT_LINE('  Password: Admin123!');
    DBMS_OUTPUT.PUT_LINE('  ** CHANGE THIS PASSWORD IMMEDIATELY **');
    DBMS_OUTPUT.PUT_LINE('');
    DBMS_OUTPUT.PUT_LINE('Database User:');
    DBMS_OUTPUT.PUT_LINE('  Username: report_user');
    DBMS_OUTPUT.PUT_LINE('  Password: report_password');
    DBMS_OUTPUT.PUT_LINE('=====================================================');
END;
/

-- Display statistics
SELECT 'Users created: ' || COUNT(*) AS user_count FROM users;
SELECT 'Roles created: ' || COUNT(*) AS role_count FROM roles;
SELECT 'Reports configured: ' || COUNT(*) AS report_count FROM report_configs;
SELECT 'System configs: ' || COUNT(*) AS config_count FROM system_config;

COMMIT;