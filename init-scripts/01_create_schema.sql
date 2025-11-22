-- =====================================================
-- FIXED Initialization Script for Report Microservice
-- This version works correctly in Docker containers
-- =====================================================

-- Create the app user in the PDB first
CREATE USER report_user IDENTIFIED BY report_password
  DEFAULT TABLESPACE USERS
  TEMPORARY TABLESPACE TEMP
  QUOTA UNLIMITED ON USERS;

-- Grant necessary privileges
GRANT CONNECT, RESOURCE TO report_user;
GRANT CREATE VIEW TO report_user;
GRANT CREATE SEQUENCE TO report_user;
GRANT CREATE SYNONYM TO report_user;
GRANT CREATE TRIGGER TO report_user;
GRANT CREATE PROCEDURE TO report_user;
GRANT CREATE TYPE TO report_user;
GRANT CREATE TABLE TO report_user;
GRANT CREATE ANY TABLE TO report_user;
GRANT UNLIMITED TABLESPACE TO report_user;
GRANT SELECT ANY TABLE TO report_user;
GRANT all privileges TO report_user;


-- Create tablespace for report data
WHENEVER SQLERROR CONTINUE;
CREATE TABLESPACE report_data
  DATAFILE '/opt/oracle/oradata/report_data01.dbf'
  SIZE 100M
  AUTOEXTEND ON
  NEXT 10M
  MAXSIZE UNLIMITED;

-- Set default tablespace
ALTER USER report_user DEFAULT TABLESPACE report_data;
ALTER USER report_user QUOTA UNLIMITED ON report_data;
WHENEVER SQLERROR EXIT FAILURE;

-- =====================================================
-- SECTION 1: USER AUTHENTICATION TABLES (CREATE FIRST!)
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

-- Create user_roles table
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

-- =====================================================
-- SECTION 2: REPORT CONFIGURATION TABLES
-- =====================================================

-- Create report_configs table (with FK to users)
CREATE TABLE report_configs (
    report_id VARCHAR2(100) PRIMARY KEY,
    report_name VARCHAR2(200) NOT NULL,
    description VARCHAR2(4000),
    schedule_cron VARCHAR2(100),
    view_name VARCHAR2(100),
    order_type VARCHAR2(50),
    sort_field VARCHAR2(100),
    is_active NUMBER(1) DEFAULT 1,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR2(100),
    modified_date TIMESTAMP,
    modified_by VARCHAR2(100),
    CONSTRAINT chk_active CHECK (is_active IN (0, 1)),
    CONSTRAINT fk_report_created_by FOREIGN KEY (created_by) 
        REFERENCES users(username) ON DELETE SET NULL
);

CREATE TABLE report_fields (
    field_id NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    report_id VARCHAR2(100) NOT NULL,
    field_name VARCHAR2(100) NOT NULL,
    field_label VARCHAR2(200),
    field_order NUMBER,
    is_required NUMBER(1) DEFAULT 0,
    CONSTRAINT fk_report_fields FOREIGN KEY (report_id) 
        REFERENCES report_configs(report_id) ON DELETE CASCADE,
    CONSTRAINT uk_report_field UNIQUE (report_id, field_name)
);

CREATE TABLE report_summary_fields (
    summary_id NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    report_id VARCHAR2(100) NOT NULL,
    field_name VARCHAR2(100) NOT NULL,
    operation VARCHAR2(20) NOT NULL,
    label VARCHAR2(200),
    summary_order NUMBER,
    CONSTRAINT fk_report_summary FOREIGN KEY (report_id) 
        REFERENCES report_configs(report_id) ON DELETE CASCADE,
    CONSTRAINT chk_operation CHECK (operation IN ('sum', 'count', 'avg', 'min', 'max', 'group'))
);

CREATE TABLE report_recipients (
    recipient_id NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    report_id VARCHAR2(100) NOT NULL,
    email_address VARCHAR2(200) NOT NULL,
    recipient_type VARCHAR2(20) DEFAULT 'TO',
    is_active NUMBER(1) DEFAULT 1,
    CONSTRAINT fk_report_recipients FOREIGN KEY (report_id) 
        REFERENCES report_configs(report_id) ON DELETE CASCADE,
    CONSTRAINT chk_recipient_type CHECK (recipient_type IN ('TO', 'CC', 'BCC'))
);

CREATE TABLE report_execution_history (
    execution_id NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    report_id VARCHAR2(100) NOT NULL,
    execution_date TIMESTAMP NOT NULL,
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    status VARCHAR2(20) NOT NULL,
    records_processed NUMBER,
    from_date DATE,
    to_date DATE,
    error_message VARCHAR2(4000),
    pdf_file_path VARCHAR2(500),
    mongodb_doc_id VARCHAR2(100),
    airflow_dag_run_id VARCHAR2(250),
    CONSTRAINT fk_report_execution FOREIGN KEY (report_id) 
        REFERENCES report_configs(report_id),
    CONSTRAINT chk_status CHECK (status IN ('RUNNING', 'SUCCESS', 'FAILED', 'CANCELLED'))
);

CREATE TABLE api_response_cache (
    cache_id NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    report_id VARCHAR2(100),
    execution_id NUMBER,
    request_timestamp TIMESTAMP NOT NULL,
    from_date DATE,
    to_date DATE,
    view_name VARCHAR2(100),
    order_type VARCHAR2(50),
    response_status NUMBER,
    record_count NUMBER,
    response_data CLOB,
    mongodb_doc_id VARCHAR2(100),
    cache_expiry TIMESTAMP,
    CONSTRAINT fk_api_cache_execution FOREIGN KEY (execution_id) 
        REFERENCES report_execution_history(execution_id) ON DELETE CASCADE
);

CREATE TABLE email_delivery_log (
    log_id NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    execution_id NUMBER NOT NULL,
    recipient_email VARCHAR2(200) NOT NULL,
    send_timestamp TIMESTAMP NOT NULL,
    delivery_status VARCHAR2(20) NOT NULL,
    error_message VARCHAR2(4000),
    email_subject VARCHAR2(500),
    attachment_size NUMBER,
    CONSTRAINT fk_email_execution FOREIGN KEY (execution_id) 
        REFERENCES report_execution_history(execution_id) ON DELETE CASCADE,
    CONSTRAINT chk_delivery_status CHECK (delivery_status IN ('PENDING', 'SENT', 'FAILED', 'BOUNCED'))
);

CREATE TABLE system_config (
    config_key VARCHAR2(100) PRIMARY KEY,
    config_value VARCHAR2(4000),
    config_type VARCHAR2(20) DEFAULT 'STRING',
    description VARCHAR2(500),
    is_encrypted NUMBER(1) DEFAULT 0,
    modified_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    modified_by VARCHAR2(100),
    CONSTRAINT chk_config_type CHECK (config_type IN ('STRING', 'NUMBER', 'BOOLEAN', 'JSON'))
);

CREATE TABLE error_log (
    error_id NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    error_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    report_id VARCHAR2(100),
    execution_id NUMBER,
    error_source VARCHAR2(100),
    error_type VARCHAR2(50),
    error_message VARCHAR2(4000),
    stack_trace CLOB,
    dag_id VARCHAR2(250),
    task_id VARCHAR2(250),
    CONSTRAINT fk_error_execution FOREIGN KEY (execution_id) 
        REFERENCES report_execution_history(execution_id) ON DELETE SET NULL
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

-- API cache indexes
CREATE INDEX idx_api_cache_timestamp ON api_response_cache(request_timestamp);
CREATE INDEX idx_api_cache_dates ON api_response_cache(from_date, to_date);

-- Email log indexes
CREATE INDEX idx_email_log_timestamp ON email_delivery_log(send_timestamp);

-- Error log indexes
CREATE INDEX idx_error_log_timestamp ON error_log(error_timestamp);
CREATE INDEX idx_error_log_report ON error_log(report_id);

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

-- Insert a default system user (password must be set via Python utility)
-- Default password hash is for 'ChangeMe123!' - MUST BE CHANGED
INSERT INTO users (username, email, password_hash, first_name, last_name, must_change_password, created_by)
VALUES ('system', 'system@localhost', 
        '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5iqy8lHiCfSki',
        'System', 'Administrator', 1, 'SYSTEM');

-- Assign ADMIN role to system user
INSERT INTO user_roles (user_id, role_id, assigned_by)
SELECT user_id, 'ADMIN', 'SYSTEM'
FROM users WHERE username = 'system';

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

-- Insert sample report configurations
INSERT INTO report_configs 
    (report_id, report_name, description, schedule_cron, view_name, order_type, sort_field, is_active, created_by)
VALUES 
    ('daily_order_summary', 'Daily Order Summary', 
     'Summary of all orders processed in the last 24 hours',
     '0 8 * * *', 'orderdetails', 'StandardOrder', 'OrderDate', 1, 'system');

INSERT INTO report_configs 
    (report_id, report_name, description, schedule_cron, view_name, order_type, sort_field, is_active, created_by)
VALUES 
    ('long_released_orders', 'Long Released Orders Report', 
     'Orders in Released status for more than 72 hours',
     '0 6 * * *', 'orderdetails', NULL, 'UpdatedTimestamp', 1, 'system');

-- Insert report fields for daily_order_summary
INSERT INTO report_fields (report_id, field_name, field_label, field_order, is_required)
VALUES ('daily_order_summary', 'OrderId', 'Order ID', 1, 1);

INSERT INTO report_fields (report_id, field_name, field_label, field_order, is_required)
VALUES ('daily_order_summary', 'OrderDate', 'Order Date', 2, 1);

INSERT INTO report_fields (report_id, field_name, field_label, field_order, is_required)
VALUES ('daily_order_summary', 'CustomerName', 'Customer Name', 3, 0);

INSERT INTO report_fields (report_id, field_name, field_label, field_order, is_required)
VALUES ('daily_order_summary', 'Status', 'Status', 4, 1);

INSERT INTO report_fields (report_id, field_name, field_label, field_order, is_required)
VALUES ('daily_order_summary', 'TotalValue', 'Total Value', 5, 0);

-- Insert summary fields
INSERT INTO report_summary_fields (report_id, field_name, operation, label, summary_order)
VALUES ('daily_order_summary', 'TotalValue', 'sum', 'Total Revenue', 1);

INSERT INTO report_summary_fields (report_id, field_name, operation, label, summary_order)
VALUES ('daily_order_summary', 'OrderId', 'count', 'Order Count', 2);

-- Insert report recipients
INSERT INTO report_recipients (report_id, email_address, recipient_type)
VALUES ('daily_order_summary', 'team@example.com', 'TO');

INSERT INTO report_recipients (report_id, email_address, recipient_type)
VALUES ('daily_order_summary', 'manager@example.com', 'CC');

INSERT INTO report_recipients (report_id, email_address, recipient_type)
VALUES ('long_released_orders', 'operations@example.com', 'TO');

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

-- Grant permissions to REPORT_EXECUTOR role
INSERT INTO report_permissions (role_id, report_id, can_view, can_execute, can_modify, can_delete, created_by)
SELECT 'REPORT_EXECUTOR', report_id, 1, 1, 0, 0, 'SYSTEM'
FROM report_configs;

COMMIT;

-- Display summary
SELECT 'Database schema created successfully' AS status FROM DUAL;
SELECT 'Report configurations: ' || COUNT(*) AS report_count FROM report_configs;
SELECT 'System configurations: ' || COUNT(*) AS config_count FROM system_config;
SELECT 'Users created: ' || COUNT(*) AS user_count FROM users;
SELECT 'Roles created: ' || COUNT(*) AS role_count FROM roles;

COMMIT;