-- =====================================================
-- User Authentication Tables for Report Microservice
-- Run this after 01_create_schema.sql to add user management
-- =====================================================

-- Connect to the pluggable database
ALTER SESSION SET CONTAINER = XEPDB1;

-- Connect as report_user
CONNECT report_user/report_password@XEPDB1;

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

-- Create indexes for better performance
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_active ON users(is_active);
CREATE INDEX idx_user_roles_user ON user_roles(user_id);
CREATE INDEX idx_user_roles_role ON user_roles(role_id);
CREATE INDEX idx_report_perm_role ON report_permissions(role_id);
CREATE INDEX idx_report_perm_report ON report_permissions(report_id);
CREATE INDEX idx_user_activity_user ON user_activity_log(user_id);
CREATE INDEX idx_user_activity_timestamp ON user_activity_log(timestamp);
CREATE INDEX idx_user_activity_type ON user_activity_log(activity_type);

-- Insert default roles
INSERT INTO roles (role_id, role_name, description, created_by)
VALUES ('ADMIN', 'Administrator', 'Full system access with all permissions', 'SYSTEM');

INSERT INTO roles (role_id, role_name, description, created_by)
VALUES ('REPORT_MANAGER', 'Report Manager', 'Can create, modify, and execute reports', 'SYSTEM');

INSERT INTO roles (role_id, role_name, description, created_by)
VALUES ('REPORT_VIEWER', 'Report Viewer', 'Can view and execute reports only', 'SYSTEM');

INSERT INTO roles (role_id, role_name, description, created_by)
VALUES ('REPORT_EXECUTOR', 'Report Executor', 'Can execute reports but not modify them', 'SYSTEM');

-- Grant permissions to ADMIN role for all existing reports
INSERT INTO report_permissions (role_id, report_id, can_view, can_execute, can_modify, can_delete, created_by)
SELECT 'ADMIN', report_id, 1, 1, 1, 1, 'SYSTEM'
FROM report_configs;

-- Grant permissions to REPORT_MANAGER role for all existing reports
INSERT INTO report_permissions (role_id, report_id, can_view, can_execute, can_modify, can_delete, created_by)
SELECT 'REPORT_MANAGER', report_id, 1, 1, 1, 0, 'SYSTEM'
FROM report_configs;

-- Grant permissions to REPORT_VIEWER role for all existing reports
INSERT INTO report_permissions (role_id, report_id, can_view, can_execute, can_modify, can_delete, created_by)
SELECT 'REPORT_VIEWER', report_id, 1, 1, 0, 0, 'SYSTEM'
FROM report_configs;

-- Grant permissions to REPORT_EXECUTOR role for all existing reports
INSERT INTO report_permissions (role_id, report_id, can_view, can_execute, can_modify, can_delete, created_by)
SELECT 'REPORT_EXECUTOR', report_id, 1, 1, 0, 0, 'SYSTEM'
FROM report_configs;

COMMIT;

-- Display summary
SELECT 'User authentication tables created successfully' AS status FROM DUAL;
SELECT 'Roles created: ' || COUNT(*) AS role_count FROM roles;
SELECT 'Default permissions set: ' || COUNT(*) AS permission_count FROM report_permissions;
