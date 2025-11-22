# User Authentication Tables Setup Guide

## Issue Identified

The original database initialization script (`init-scripts/01_create_schema.sql`) was **missing all user authentication tables**. This is why user tables were not being created on startup.

### What Was Missing:
- `users` table - stores user accounts with hashed passwords
- `roles` table - defines system roles (ADMIN, REPORT_MANAGER, etc.)
- `user_roles` table - maps users to roles (many-to-many)
- `report_permissions` table - controls what roles can do with reports
- `user_activity_log` table - tracks all user actions for security auditing

## Solution

I've created three new files to fix this:

1. **02_create_user_tables.sql** - SQL script to create all missing user tables
2. **user_management.py** - Python module with secure password hashing and user management
3. **create_admin_user.py** - CLI tool to create your first admin user

## Setup Instructions

### Step 1: Update Docker Compose

First, ensure bcrypt is installed in your Airflow containers. Update the `docker-compose.yaml` to include bcrypt:

```yaml
# In the airflow-init, airflow-webserver, and airflow-scheduler services:
command: >
  bash -c "
    pip install pymongo pandas matplotlib reportlab requests cx_Oracle bcrypt
    pip install 'apache-airflow-providers-openlineage>=1.8.0' --no-deps
    # ... rest of commands
  "
```

### Step 2: Run the User Tables SQL Script

There are two ways to run the SQL script:

#### Option A: Add to init-scripts directory (Recommended for new deployments)

```bash
# Copy the SQL script to your init-scripts directory
cp 02_create_user_tables.sql init-scripts/

# Restart the Oracle container to run the script
docker-compose restart oracle-db
```

#### Option B: Run manually via DBeaver (For existing deployments)

1. Open DBeaver
2. Connect to your Oracle database (localhost:1521/XEPDB1)
3. Use credentials: report_user / report_password
4. Open and execute `02_create_user_tables.sql`
5. Verify tables were created:
```sql
SELECT table_name FROM user_tables 
WHERE table_name IN ('USERS', 'ROLES', 'USER_ROLES', 'REPORT_PERMISSIONS', 'USER_ACTIVITY_LOG');
```

### Step 3: Install the User Management Module

```bash
# Copy the user management module to your utils directory
cp user_management.py utils/

# Make sure it's accessible to Airflow
# The docker-compose.yaml already mounts ./utils to /opt/airflow/utils
```

### Step 4: Create Your First Admin User

```bash
# Make the script executable
chmod +x create_admin_user.py

# Run the script inside the Airflow container
docker exec -it airflow-webserver python /opt/airflow/create_admin_user.py

# Follow the interactive prompts
```

Or run it directly on your host if you have Oracle client installed:

```bash
python create_admin_user.py
```

## Using the User Management Functions

### Example: Create a New User Programmatically

```python
from utils.user_management import create_user

# Create a new user
user_id = create_user(
    username='john_doe',
    email='john@example.com',
    password='SecurePass123!',
    first_name='John',
    last_name='Doe',
    roles=['REPORT_VIEWER'],
    created_by='admin'
)

if user_id:
    print(f"User created with ID: {user_id}")
```

### Example: Authenticate a User

```python
from utils.user_management import authenticate_user

# Authenticate user
user_info = authenticate_user(
    username='john_doe',
    password='SecurePass123!',
    ip_address='192.168.1.100',
    user_agent='Mozilla/5.0...'
)

if user_info:
    print(f"Welcome {user_info['first_name']}!")
    print(f"Your roles: {[r['role_name'] for r in user_info['roles']]}")
else:
    print("Authentication failed")
```

### Example: Change Password

```python
from utils.user_management import change_password

success = change_password(
    user_id=123,
    old_password='SecurePass123!',
    new_password='NewSecurePass456!'
)
```

### Example: Reset Password (Admin Function)

```python
from utils.user_management import reset_password

success = reset_password(
    user_id=123,
    new_password='TempPassword123!',
    reset_by='admin'
)
# User will be forced to change password on next login
```

## Password Requirements

The system enforces strong password requirements:
- Minimum 8 characters
- At least one uppercase letter
- At least one lowercase letter  
- At least one digit
- At least one special character (!@#$%^&*()_+-=[]{}etc.)

## Default Roles

The system comes with four pre-configured roles:

1. **ADMIN** - Full system access
   - Can view, execute, modify, and delete all reports
   - Can manage users and roles

2. **REPORT_MANAGER** - Report management
   - Can view, execute, and modify reports
   - Cannot delete reports

3. **REPORT_VIEWER** - View and execute only
   - Can view and execute reports
   - Cannot modify or delete reports

4. **REPORT_EXECUTOR** - Execute only
   - Can view and execute reports
   - Cannot modify or delete reports

## Security Features

### Password Hashing
- Uses bcrypt with 12 rounds (industry standard)
- Passwords are never stored in plain text
- Each password gets a unique salt

### Account Lockout
- Account locks after 5 failed login attempts
- Must be manually unlocked by admin

### Activity Logging
- All authentication attempts are logged
- All password changes are tracked
- All role assignments are recorded
- Includes IP address and user agent for security audits

### Password Expiry
- Administrators can force password change on next login
- Useful for password resets and new user onboarding

## Troubleshooting

### "Module bcrypt not found"
```bash
# Install bcrypt in the Airflow container
docker exec -it airflow-webserver pip install bcrypt
docker exec -it airflow-scheduler pip install bcrypt
```

### "ORA-00942: table or view does not exist"
The user tables SQL script hasn't been run yet. Follow Step 2 above.

### "User already exists"
This is normal if you're trying to create a user that already exists. Use a different username.

### "Password does not meet requirements"
Check the password requirements section above. The password must meet all criteria.

## Integration with Airflow DAGs

You can integrate user authentication into your DAGs for audit trails:

```python
from airflow import DAG
from airflow.operators.python import PythonOperator
from utils.user_management import log_user_activity

def run_report(**kwargs):
    user_id = kwargs['dag_run'].conf.get('user_id')
    
    # Log the report execution
    log_user_activity(
        user_id=user_id,
        activity_type='REPORT_EXECUTED',
        activity_description=f'Executed report {kwargs["dag"].dag_id}',
        success=True
    )
    
    # ... rest of report logic

dag = DAG('secure_report', ...)

task = PythonOperator(
    task_id='run_report',
    python_callable=run_report,
    provide_context=True,
    dag=dag
)
```

## Next Steps

1. ✓ Create the user tables (Step 2)
2. ✓ Create your first admin user (Step 4)
3. Create additional users as needed
4. Integrate authentication into your DAGs
5. Set up role-based permissions for reports
6. Review activity logs regularly for security

## Environment Variables

If using environment variables for database connection:

```bash
# In .env file
ORACLE_USER=report_user
ORACLE_PASSWORD=your_secure_password
ORACLE_HOST=oracle-db
ORACLE_PORT=1521
ORACLE_SERVICE=XEPDB1
```

## Verification

To verify everything is working:

```python
from utils.user_management import get_user_info

# Get user information
user = get_user_info(username='admin')
if user:
    print(f"User: {user['username']}")
    print(f"Email: {user['email']}")
    print(f"Roles: {[r['role_name'] for r in user['roles']]}")
    print(f"Active: {user['is_active']}")
```

## Support

If you encounter any issues:
1. Check the Airflow logs: `docker-compose logs airflow-webserver`
2. Check Oracle logs: `docker-compose logs oracle-db`
3. Verify database connectivity with DBeaver
4. Ensure all required Python packages are installed
