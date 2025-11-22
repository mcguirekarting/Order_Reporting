# User Management Quick Reference

## Common Operations

### Create a User
```python
from utils.user_management import create_user

user_id = create_user(
    username='john_doe',
    email='john@example.com',
    password='SecurePass123!',
    first_name='John',
    last_name='Doe',
    roles=['REPORT_VIEWER'],
    created_by='admin'
)
```

### Authenticate User
```python
from utils.user_management import authenticate_user

user = authenticate_user(
    username='john_doe',
    password='SecurePass123!',
    ip_address='192.168.1.100'
)
```

### Change Password
```python
from utils.user_management import change_password

success = change_password(
    user_id=123,
    old_password='OldPass123!',
    new_password='NewPass456!'
)
```

### Reset Password (Admin)
```python
from utils.user_management import reset_password

success = reset_password(
    user_id=123,
    new_password='TempPass123!',
    reset_by='admin'
)
```

### Assign Role to User
```python
from utils.user_management import assign_role

success = assign_role(
    user_id=123,
    role_id='REPORT_MANAGER',
    assigned_by='admin'
)
```

### Get User Information
```python
from utils.user_management import get_user_info

# By user ID
user = get_user_info(user_id=123)

# By username
user = get_user_info(username='john_doe')
```

### Log User Activity
```python
from utils.user_management import log_user_activity

log_user_activity(
    user_id=123,
    username='john_doe',
    activity_type='REPORT_EXECUTED',
    activity_description='Executed daily sales report',
    ip_address='192.168.1.100',
    success=True
)
```

## Available Roles

| Role ID | Role Name | Permissions |
|---------|-----------|-------------|
| ADMIN | Administrator | Full access (view, execute, modify, delete) |
| REPORT_MANAGER | Report Manager | View, execute, modify reports |
| REPORT_VIEWER | Report Viewer | View and execute reports |
| REPORT_EXECUTOR | Report Executor | View and execute reports |

## Password Requirements

✓ Minimum 8 characters  
✓ At least one uppercase letter  
✓ At least one lowercase letter  
✓ At least one digit  
✓ At least one special character  

Examples of valid passwords:
- `SecurePass123!`
- `MyP@ssw0rd`
- `Admin#2024`

## Activity Types for Logging

Common activity types:
- `USER_CREATED` - New user account created
- `LOGIN_SUCCESS` - Successful login
- `LOGIN_FAILED` - Failed login attempt
- `PASSWORD_CHANGED` - Password changed by user
- `PASSWORD_RESET` - Password reset by admin
- `ROLE_ASSIGNED` - Role assigned to user
- `REPORT_EXECUTED` - Report executed by user
- `REPORT_CREATED` - New report created
- `REPORT_MODIFIED` - Report configuration changed
- `REPORT_DELETED` - Report deleted

## SQL Queries for User Management

### View All Users
```sql
SELECT user_id, username, email, first_name, last_name, is_active, is_locked
FROM users
ORDER BY username;
```

### View User Roles
```sql
SELECT u.username, r.role_name, r.description
FROM users u
JOIN user_roles ur ON u.user_id = ur.user_id
JOIN roles r ON ur.role_id = r.role_id
WHERE u.username = 'john_doe';
```

### View Recent User Activity
```sql
SELECT username, activity_type, activity_description, 
       timestamp, success, ip_address
FROM user_activity_log
WHERE username = 'john_doe'
ORDER BY timestamp DESC
FETCH FIRST 10 ROWS ONLY;
```

### View Failed Login Attempts
```sql
SELECT username, activity_description, timestamp, 
       ip_address, error_message
FROM user_activity_log
WHERE activity_type = 'LOGIN_FAILED'
  AND timestamp > SYSTIMESTAMP - INTERVAL '1' DAY
ORDER BY timestamp DESC;
```

### View Locked Accounts
```sql
SELECT user_id, username, email, failed_login_attempts, last_login_date
FROM users
WHERE is_locked = 1;
```

### Unlock a User Account
```sql
UPDATE users
SET is_locked = 0,
    failed_login_attempts = 0
WHERE username = 'john_doe';
COMMIT;
```

### View Report Permissions by Role
```sql
SELECT r.role_name, rc.report_name,
       rp.can_view, rp.can_execute, rp.can_modify, rp.can_delete
FROM report_permissions rp
JOIN roles r ON rp.role_id = r.role_id
JOIN report_configs rc ON rp.report_id = rc.report_id
ORDER BY r.role_name, rc.report_name;
```

## CLI Commands

### Create Initial Admin User
```bash
docker exec -it airflow-webserver python /opt/airflow/create_admin_user.py
```

### Run SQL Script Manually
```bash
docker exec -i oracle-db sqlplus report_user/report_password@XEPDB1 < 02_create_user_tables.sql
```

### Check User Tables Exist
```bash
docker exec -it oracle-db sqlplus -S report_user/report_password@XEPDB1 << EOF
SELECT table_name FROM user_tables 
WHERE table_name IN ('USERS', 'ROLES', 'USER_ROLES', 'REPORT_PERMISSIONS', 'USER_ACTIVITY_LOG');
EXIT;
EOF
```

## Error Messages

| Error | Cause | Solution |
|-------|-------|----------|
| "Username already exists" | Duplicate username | Use a different username |
| "Email already exists" | Duplicate email | Use a different email |
| "Password validation failed" | Password too weak | Follow password requirements |
| "User not found" | Invalid user ID/username | Verify user exists |
| "Invalid current password" | Wrong password in change | Check current password |
| "Account is locked" | Too many failed logins | Unlock account via SQL or admin |
| "Account is inactive" | User deactivated | Activate user account |
| "Role does not exist" | Invalid role ID | Use one of: ADMIN, REPORT_MANAGER, REPORT_VIEWER, REPORT_EXECUTOR |

## Testing Authentication

### Python Test Script
```python
from utils.user_management import (
    create_user, authenticate_user, 
    change_password, get_user_info
)

# Create test user
user_id = create_user(
    username='test_user',
    email='test@example.com',
    password='TestPass123!',
    roles=['REPORT_VIEWER']
)
print(f"Created user ID: {user_id}")

# Authenticate
user = authenticate_user('test_user', 'TestPass123!')
print(f"Authenticated: {user['username']}")

# Get info
info = get_user_info(username='test_user')
print(f"User roles: {[r['role_name'] for r in info['roles']]}")

# Change password
success = change_password(user_id, 'TestPass123!', 'NewPass456!')
print(f"Password changed: {success}")

# Verify new password
user = authenticate_user('test_user', 'NewPass456!')
print(f"New password works: {user is not None}")
```

## Security Best Practices

1. **Never log passwords** - The system logs activity but never passwords
2. **Use strong passwords** - Follow all password requirements
3. **Rotate admin passwords** - Change admin passwords regularly
4. **Review activity logs** - Check for suspicious login patterns
5. **Lock inactive accounts** - Deactivate users who no longer need access
6. **Use least privilege** - Assign minimum required roles
7. **Monitor failed logins** - Set up alerts for repeated failures
8. **Regular audits** - Review user permissions quarterly

## Environment Setup

Required Python packages:
```bash
pip install bcrypt cx_Oracle
```

Required database tables:
- users
- roles  
- user_roles
- report_permissions
- user_activity_log

Required environment variables:
```
ORACLE_USER=report_user
ORACLE_PASSWORD=your_password
ORACLE_HOST=oracle-db
ORACLE_PORT=1521
ORACLE_SERVICE=XEPDB1
```
