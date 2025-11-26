"""
User Management Utilities for Report Microservice
Provides functions for user authentication and management with secure password hashing
"""

import logging
import re
import os
from datetime import datetime
from typing import Optional, Dict, List, Any
import bcrypt
import oracledb

from utils.oracle_db_utils import get_oracle_connection as get_db_connection

logger = logging.getLogger("user_management")


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt
    
    Args:
        password: Plain text password to hash
        
    Returns:
        Hashed password as a string
    """
    # Generate salt and hash the password
    salt = bcrypt.gensalt(rounds=12)  # 12 rounds is a good balance of security and performance
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def verify_password(password: str, password_hash: str) -> bool:
    """
    Verify a password against its hash
    
    Args:
        password: Plain text password to verify
        password_hash: Hashed password to compare against
        
    Returns:
        True if password matches, False otherwise
    """
    try:
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
    except Exception as e:
        logger.error(f"Error verifying password: {str(e)}")
        return False


def validate_password_strength(password: str) -> tuple[bool, str]:
    """
    Validate password meets security requirements
    
    Requirements:
    - At least 8 characters long
    - Contains at least one uppercase letter
    - Contains at least one lowercase letter
    - Contains at least one digit
    - Contains at least one special character
    
    Args:
        password: Password to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"
    
    if not re.search(r'\d', password):
        return False, "Password must contain at least one digit"
    
    if not re.search(r'[!@#$%^&*()_+\-=\[\]{};:\'",.<>?/\\|`~]', password):
        return False, "Password must contain at least one special character"
    
    return True, ""


def validate_email(email: str) -> bool:
    """
    Validate email format
    
    Args:
        email: Email address to validate
        
    Returns:
        True if valid, False otherwise
    """
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def create_user(username: str, email: str, password: str, first_name: str,
                last_name: str, roles: List[str], created_by: str = 'SYSTEM',
                must_change_password: bool = False) -> Optional[int]:
    """
    Create a new user with hashed password
    
    Args:
        username: Unique username
        email: User's email address
        password: Plain text password (will be hashed)
        first_name: User's first name
        last_name: User's last name
        roles: List of role IDs to assign to the user
        created_by: Username of the person creating this user
        must_change_password: Whether user must change password on first login
        
    Returns:
        User ID if successful, None otherwise
    """
    connection = None
    try:
        # Validate inputs
        if not username or not email or not password:
            logger.error("Username, email, and password are required")
            return None
        
        # Validate email format
        if not validate_email(email):
            logger.error(f"Invalid email format: {email}")
            return None
        
        # Validate password strength
        is_valid, error_msg = validate_password_strength(password)
        if not is_valid:
            logger.error(f"Password validation failed: {error_msg}")
            return None
        
        # Hash the password
        password_hash = hash_password(password)
        
        # Get database connection
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Check if username already exists
        cursor.execute("SELECT COUNT(*) FROM users WHERE username = :username", 
                      username=username)
        if cursor.fetchone()[0] > 0:
            logger.error(f"Username already exists: {username}")
            cursor.close()
            return None
        
        # Check if email already exists
        cursor.execute("SELECT COUNT(*) FROM users WHERE email = :email", 
                      email=email)
        if cursor.fetchone()[0] > 0:
            logger.error(f"Email already exists: {email}")
            cursor.close()
            return None
        
        # Insert the user
        cursor.execute("""
            INSERT INTO users 
                (username, email, password_hash, first_name, last_name, 
                 must_change_password, created_by)
            VALUES 
                (:username, :email, :password_hash, :first_name, :last_name,
                 :must_change_password, :created_by)
            RETURNING user_id INTO :user_id
        """, username=username, email=email, password_hash=password_hash,
             first_name=first_name, last_name=last_name,
             must_change_password=1 if must_change_password else 0,
             created_by=created_by, user_id=cursor.var(oracledb.NUMBER))
        
        user_id = int(cursor.getvalue(0))
        
        # Assign roles if provided
        if roles:
            for role_id in roles:
                try:
                    cursor.execute("""
                        INSERT INTO user_roles (user_id, role_id, assigned_by)
                        VALUES (:user_id, :role_id, :assigned_by)
                    """, user_id=user_id, role_id=role_id, assigned_by=created_by)
                except oracledb.IntegrityError:
                    logger.warning(f"Role {role_id} does not exist or already assigned")
        
        # Log the activity
        log_user_activity(
            user_id=user_id,
            username=username,
            activity_type='USER_CREATED',
            activity_description=f'User {username} created by {created_by}',
            success=True
        )
        
        connection.commit()
        cursor.close()
        
        logger.info(f"Successfully created user: {username} (ID: {user_id})")
        return user_id
        
    except oracledb.Error as error:
        logger.error(f"Database error creating user: {error}")
        if connection:
            connection.rollback()
        return None
    finally:
        if connection:
            connection.close()


def authenticate_user(username: str, password: str, ip_address: str = None,
                     user_agent: str = None) -> Optional[Dict[str, Any]]:
    """
    Authenticate a user with username and password
    
    Args:
        username: Username to authenticate
        password: Plain text password
        ip_address: IP address of the login attempt
        user_agent: User agent string of the client
        
    Returns:
        User information dictionary if successful, None otherwise
    """
    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Get user information
        cursor.execute("""
            SELECT user_id, username, email, password_hash, first_name, last_name,
                   is_active, is_locked, failed_login_attempts, must_change_password
            FROM users
            WHERE username = :username
        """, username=username)
        
        row = cursor.fetchone()
        
        if not row:
            logger.warning(f"Authentication failed: User not found - {username}")
            log_user_activity(
                username=username,
                activity_type='LOGIN_FAILED',
                activity_description='User not found',
                ip_address=ip_address,
                user_agent=user_agent,
                success=False,
                error_message='User not found'
            )
            return None
        
        user_id, db_username, email, password_hash, first_name, last_name, \
            is_active, is_locked, failed_attempts, must_change_password = row
        
        # Check if account is active
        if not is_active:
            logger.warning(f"Authentication failed: Account inactive - {username}")
            log_user_activity(
                user_id=user_id,
                username=username,
                activity_type='LOGIN_FAILED',
                activity_description='Account inactive',
                ip_address=ip_address,
                user_agent=user_agent,
                success=False,
                error_message='Account is inactive'
            )
            return None
        
        # Check if account is locked
        if is_locked:
            logger.warning(f"Authentication failed: Account locked - {username}")
            log_user_activity(
                user_id=user_id,
                username=username,
                activity_type='LOGIN_FAILED',
                activity_description='Account locked',
                ip_address=ip_address,
                user_agent=user_agent,
                success=False,
                error_message='Account is locked'
            )
            return None
        
        # Verify password
        if not verify_password(password, password_hash):
            # Increment failed login attempts
            failed_attempts += 1
            lock_account = failed_attempts >= 5
            
            cursor.execute("""
                UPDATE users
                SET failed_login_attempts = :failed_attempts,
                    is_locked = :is_locked
                WHERE user_id = :user_id
            """, failed_attempts=failed_attempts, 
                 is_locked=1 if lock_account else 0,
                 user_id=user_id)
            
            connection.commit()
            
            logger.warning(f"Authentication failed: Invalid password - {username} "
                         f"(Attempts: {failed_attempts})")
            
            log_user_activity(
                user_id=user_id,
                username=username,
                activity_type='LOGIN_FAILED',
                activity_description=f'Invalid password (Attempt {failed_attempts})',
                ip_address=ip_address,
                user_agent=user_agent,
                success=False,
                error_message='Invalid password'
            )
            
            if lock_account:
                logger.warning(f"Account locked due to too many failed attempts: {username}")
            
            return None
        
        # Successful authentication - reset failed attempts and update last login
        cursor.execute("""
            UPDATE users
            SET failed_login_attempts = 0,
                last_login_date = SYSTIMESTAMP
            WHERE user_id = :user_id
        """, user_id=user_id)
        
        # Get user roles
        cursor.execute("""
            SELECT r.role_id, r.role_name, r.description
            FROM roles r
            JOIN user_roles ur ON r.role_id = ur.role_id
            WHERE ur.user_id = :user_id AND r.is_active = 1
        """, user_id=user_id)
        
        roles = [{'role_id': row[0], 'role_name': row[1], 'description': row[2]} 
                for row in cursor.fetchall()]
        
        connection.commit()
        cursor.close()
        
        # Log successful login
        log_user_activity(
            user_id=user_id,
            username=username,
            activity_type='LOGIN_SUCCESS',
            activity_description='User logged in successfully',
            ip_address=ip_address,
            user_agent=user_agent,
            success=True
        )
        
        logger.info(f"User authenticated successfully: {username}")
        
        return {
            'user_id': user_id,
            'username': db_username,
            'email': email,
            'first_name': first_name,
            'last_name': last_name,
            'roles': roles,
            'must_change_password': bool(must_change_password)
        }
        
    except oracledb.Error as error:
        logger.error(f"Database error during authentication: {error}")
        if connection:
            connection.rollback()
        return None
    finally:
        if connection:
            connection.close()


def change_password(user_id: int, old_password: str, new_password: str) -> bool:
    """
    Change a user's password
    
    Args:
        user_id: User ID
        old_password: Current password (for verification)
        new_password: New password
        
    Returns:
        True if successful, False otherwise
    """
    connection = None
    try:
        # Validate new password strength
        is_valid, error_msg = validate_password_strength(new_password)
        if not is_valid:
            logger.error(f"Password validation failed: {error_msg}")
            return False
        
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Get current password hash
        cursor.execute("""
            SELECT password_hash, username
            FROM users
            WHERE user_id = :user_id
        """, user_id=user_id)
        
        row = cursor.fetchone()
        if not row:
            logger.error(f"User not found: {user_id}")
            return False
        
        current_hash, username = row
        
        # Verify old password
        if not verify_password(old_password, current_hash):
            logger.warning(f"Password change failed: Invalid current password for user {username}")
            log_user_activity(
                user_id=user_id,
                username=username,
                activity_type='PASSWORD_CHANGE_FAILED',
                activity_description='Invalid current password',
                success=False,
                error_message='Current password is incorrect'
            )
            return False
        
        # Hash new password
        new_hash = hash_password(new_password)
        
        # Update password
        cursor.execute("""
            UPDATE users
            SET password_hash = :new_hash,
                password_changed_date = SYSTIMESTAMP,
                must_change_password = 0,
                modified_date = SYSTIMESTAMP
            WHERE user_id = :user_id
        """, new_hash=new_hash, user_id=user_id)
        
        connection.commit()
        cursor.close()
        
        # Log activity
        log_user_activity(
            user_id=user_id,
            username=username,
            activity_type='PASSWORD_CHANGED',
            activity_description='Password changed successfully',
            success=True
        )
        
        logger.info(f"Password changed successfully for user: {username}")
        return True
        
    except oracledb.Error as error:
        logger.error(f"Database error changing password: {error}")
        if connection:
            connection.rollback()
        return False
    finally:
        if connection:
            connection.close()


def reset_password(user_id: int, new_password: str, reset_by: str = 'SYSTEM') -> bool:
    """
    Reset a user's password (admin function)
    
    Args:
        user_id: User ID
        new_password: New password
        reset_by: Username of the person resetting the password
        
    Returns:
        True if successful, False otherwise
    """
    connection = None
    try:
        # Validate new password strength
        is_valid, error_msg = validate_password_strength(new_password)
        if not is_valid:
            logger.error(f"Password validation failed: {error_msg}")
            return False
        
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Get username
        cursor.execute("SELECT username FROM users WHERE user_id = :user_id", 
                      user_id=user_id)
        row = cursor.fetchone()
        if not row:
            logger.error(f"User not found: {user_id}")
            return False
        
        username = row[0]
        
        # Hash new password
        new_hash = hash_password(new_password)
        
        # Update password and force password change on next login
        cursor.execute("""
            UPDATE users
            SET password_hash = :new_hash,
                password_changed_date = SYSTIMESTAMP,
                must_change_password = 1,
                failed_login_attempts = 0,
                is_locked = 0,
                modified_date = SYSTIMESTAMP,
                modified_by = :reset_by
            WHERE user_id = :user_id
        """, new_hash=new_hash, user_id=user_id, reset_by=reset_by)
        
        connection.commit()
        cursor.close()
        
        # Log activity
        log_user_activity(
            user_id=user_id,
            username=username,
            activity_type='PASSWORD_RESET',
            activity_description=f'Password reset by {reset_by}',
            success=True
        )
        
        logger.info(f"Password reset successfully for user: {username} by {reset_by}")
        return True
        
    except oracledb.Error as error:
        logger.error(f"Database error resetting password: {error}")
        if connection:
            connection.rollback()
        return False
    finally:
        if connection:
            connection.close()


def assign_role(user_id: int, role_id: str, assigned_by: str = 'SYSTEM') -> bool:
    """
    Assign a role to a user
    
    Args:
        user_id: User ID
        role_id: Role ID to assign
        assigned_by: Username of the person assigning the role
        
    Returns:
        True if successful, False otherwise
    """
    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        # Get username
        cursor.execute("SELECT username FROM users WHERE user_id = :user_id", 
                      user_id=user_id)
        row = cursor.fetchone()
        if not row:
            logger.error(f"User not found: {user_id}")
            return False
        
        username = row[0]
        
        # Assign role
        cursor.execute("""
            INSERT INTO user_roles (user_id, role_id, assigned_by)
            VALUES (:user_id, :role_id, :assigned_by)
        """, user_id=user_id, role_id=role_id, assigned_by=assigned_by)
        
        connection.commit()
        cursor.close()
        
        # Log activity
        log_user_activity(
            user_id=user_id,
            username=username,
            activity_type='ROLE_ASSIGNED',
            activity_description=f'Role {role_id} assigned by {assigned_by}',
            success=True
        )
        
        logger.info(f"Role {role_id} assigned to user {username} by {assigned_by}")
        return True
        
    except oracledb.IntegrityError:
        logger.warning(f"Role assignment failed: Role {role_id} already assigned to user {user_id}")
        return False
    except oracledb.Error as error:
        logger.error(f"Database error assigning role: {error}")
        if connection:
            connection.rollback()
        return False
    finally:
        if connection:
            connection.close()


def log_user_activity(user_id: int = None, username: str = None, activity_type: str = None,
                     activity_description: str = None, ip_address: str = None,
                     user_agent: str = None, success: bool = True, 
                     error_message: str = None):
    """
    Log user activity
    
    Args:
        user_id: User ID (optional if user doesn't exist yet)
        username: Username
        activity_type: Type of activity
        activity_description: Description of the activity
        ip_address: IP address of the client
        user_agent: User agent string
        success: Whether the activity was successful
        error_message: Error message if failed
    """
    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        cursor.execute("""
            INSERT INTO user_activity_log 
                (user_id, username, activity_type, activity_description,
                 ip_address, user_agent, success, error_message)
            VALUES 
                (:user_id, :username, :activity_type, :activity_description,
                 :ip_address, :user_agent, :success, :error_message)
        """, user_id=user_id, username=username, activity_type=activity_type,
             activity_description=activity_description, ip_address=ip_address,
             user_agent=user_agent, success=1 if success else 0, 
             error_message=error_message)
        
        connection.commit()
        cursor.close()
        
    except oracledb.Error as error:
        logger.error(f"Error logging user activity: {error}")
        if connection:
            connection.rollback()
    finally:
        if connection:
            connection.close()


def get_user_info(user_id: int = None, username: str = None) -> Optional[Dict[str, Any]]:
    """
    Get detailed user information
    
    Args:
        user_id: User ID (if provided, username is ignored)
        username: Username
        
    Returns:
        User information dictionary or None
    """
    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        if user_id:
            cursor.execute("""
                SELECT user_id, username, email, first_name, last_name,
                       is_active, is_locked, last_login_date, password_changed_date,
                       must_change_password, created_date
                FROM users
                WHERE user_id = :user_id
            """, user_id=user_id)
        else:
            cursor.execute("""
                SELECT user_id, username, email, first_name, last_name,
                       is_active, is_locked, last_login_date, password_changed_date,
                       must_change_password, created_date
                FROM users
                WHERE username = :username
            """, username=username)
        
        row = cursor.fetchone()
        if not row:
            return None
        
        user_info = {
            'user_id': row[0],
            'username': row[1],
            'email': row[2],
            'first_name': row[3],
            'last_name': row[4],
            'is_active': bool(row[5]),
            'is_locked': bool(row[6]),
            'last_login_date': row[7].isoformat() if row[7] else None,
            'password_changed_date': row[8].isoformat() if row[8] else None,
            'must_change_password': bool(row[9]),
            'created_date': row[10].isoformat() if row[10] else None
        }
        
        # Get roles
        cursor.execute("""
            SELECT r.role_id, r.role_name, r.description
            FROM roles r
            JOIN user_roles ur ON r.role_id = ur.role_id
            WHERE ur.user_id = :user_id AND r.is_active = 1
        """, user_id=user_info['user_id'])
        
        user_info['roles'] = [
            {'role_id': row[0], 'role_name': row[1], 'description': row[2]}
            for row in cursor.fetchall()
        ]
        
        cursor.close()
        return user_info
        
    except oracledb.Error as error:
        logger.error(f"Database error getting user info: {error}")
        return None
    finally:
        if connection:
            connection.close()


def get_all_users() -> List[Dict[str, Any]]:
    """
    Get all users from the database
    
    Returns:
        List of user dictionaries
    """
    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        cursor.execute("""
            SELECT user_id, username, email, first_name, last_name,
                   is_active, is_locked, last_login_date, created_date
            FROM users
            ORDER BY username
        """)
        
        users = []
        for row in cursor.fetchall():
            users.append({
                'user_id': row[0],
                'username': row[1],
                'email': row[2],
                'first_name': row[3],
                'last_name': row[4],
                'is_active': bool(row[5]),
                'is_locked': bool(row[6]),
                'last_login_date': row[7].isoformat() if row[7] else None,
                'created_date': row[8].isoformat() if row[8] else None
            })
        
        cursor.close()
        logger.info(f"Retrieved {len(users)} users")
        return users
        
    except oracledb.Error as error:
        logger.error(f"Database error getting all users: {error}")
        return []
    finally:
        if connection:
            connection.close()


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """
    Get user information by user ID
    
    Args:
        user_id: User ID
        
    Returns:
        User information dictionary or None if not found
    """
    return get_user_info(user_id)


def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    """
    Get user information by username
    
    Args:
        username: Username to look up
        
    Returns:
        User information dictionary or None if not found
    """
    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        cursor.execute("""
            SELECT user_id, username, email, first_name, last_name,
                   is_active, is_locked, last_login_date, password_changed_date,
                   must_change_password, created_date
            FROM users
            WHERE username = :username
        """, username=username)
        
        row = cursor.fetchone()
        if not row:
            logger.warning(f"User not found: {username}")
            return None
        
        user_info = {
            'user_id': row[0],
            'username': row[1],
            'email': row[2],
            'first_name': row[3],
            'last_name': row[4],
            'is_active': bool(row[5]),
            'is_locked': bool(row[6]),
            'last_login_date': row[7].isoformat() if row[7] else None,
            'password_changed_date': row[8].isoformat() if row[8] else None,
            'must_change_password': bool(row[9]),
            'created_date': row[10].isoformat() if row[10] else None
        }
        
        cursor.execute("""
            SELECT r.role_id, r.role_name, r.description
            FROM roles r
            JOIN user_roles ur ON r.role_id = ur.role_id
            WHERE ur.user_id = :user_id AND r.is_active = 1
        """, user_id=user_info['user_id'])
        
        user_info['roles'] = [
            {'role_id': row[0], 'role_name': row[1], 'description': row[2]}
            for row in cursor.fetchall()
        ]
        
        cursor.close()
        return user_info
        
    except oracledb.Error as error:
        logger.error(f"Database error getting user by username: {error}")
        return None
    finally:
        if connection:
            connection.close()


def get_user_roles() -> List[Dict[str, str]]:
    """
    Get all available roles
    
    Returns:
        List of role dictionaries
    """
    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        cursor.execute("""
            SELECT role_id, role_name, description
            FROM roles
            WHERE is_active = 1
            ORDER BY role_name
        """)
        
        roles = [
            {'role_id': row[0], 'role_name': row[1], 'description': row[2]}
            for row in cursor.fetchall()
        ]
        
        cursor.close()
        logger.info(f"Retrieved {len(roles)} roles")
        return roles
        
    except oracledb.Error as error:
        logger.error(f"Database error getting roles: {error}")
        return []
    finally:
        if connection:
            connection.close()


def reset_password(username: str = None, user_id: int = None, new_password: str = None, 
                  changed_by: str = 'SYSTEM', must_change_password: bool = True) -> bool:
    """
    Reset a user's password by username or user_id (admin function)
    
    Args:
        username: Username (optional if user_id is provided)
        user_id: User ID (optional if username is provided)
        new_password: New password
        changed_by: Username of the person resetting the password
        must_change_password: Whether user must change password on next login
        
    Returns:
        True if successful, False otherwise
    """
    connection = None
    try:
        if not new_password:
            logger.error("New password is required")
            return False
        
        is_valid, error_msg = validate_password_strength(new_password)
        if not is_valid:
            logger.error(f"Password validation failed: {error_msg}")
            return False
        
        connection = get_db_connection()
        cursor = connection.cursor()
        
        if username:
            cursor.execute("SELECT user_id, username FROM users WHERE username = :username", 
                          username=username)
        elif user_id:
            cursor.execute("SELECT user_id, username FROM users WHERE user_id = :user_id", 
                          user_id=user_id)
        else:
            logger.error("Either username or user_id must be provided")
            return False
        
        row = cursor.fetchone()
        if not row:
            logger.error(f"User not found")
            return False
        
        resolved_user_id, resolved_username = row
        
        new_hash = hash_password(new_password)
        
        cursor.execute("""
            UPDATE users
            SET password_hash = :new_hash,
                password_changed_date = SYSTIMESTAMP,
                must_change_password = :must_change,
                failed_login_attempts = 0,
                is_locked = 0,
                modified_date = SYSTIMESTAMP,
                modified_by = :changed_by
            WHERE user_id = :user_id
        """, new_hash=new_hash, user_id=resolved_user_id, changed_by=changed_by,
             must_change=1 if must_change_password else 0)
        
        connection.commit()
        cursor.close()
        
        log_user_activity(
            user_id=resolved_user_id,
            username=resolved_username,
            activity_type='PASSWORD_RESET',
            activity_description=f'Password reset by {changed_by}',
            success=True
        )
        
        logger.info(f"Password reset successfully for user: {resolved_username} by {changed_by}")
        return True
        
    except oracledb.Error as error:
        logger.error(f"Database error resetting password: {error}")
        if connection:
            connection.rollback()
        return False
    finally:
        if connection:
            connection.close()


def update_user(user_id: int, email: str = None, first_name: str = None,
               last_name: str = None, is_active: bool = None, 
               modified_by: str = 'SYSTEM') -> bool:
    """
    Update user information
    
    Args:
        user_id: User ID
        email: New email address
        first_name: New first name
        last_name: New last name
        is_active: Active status
        modified_by: Username of the person making changes
        
    Returns:
        True if successful, False otherwise
    """
    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        cursor.execute("SELECT username FROM users WHERE user_id = :user_id", 
                      user_id=user_id)
        row = cursor.fetchone()
        if not row:
            logger.error(f"User not found: {user_id}")
            return False
        
        username = row[0]
        
        updates = []
        params = {'user_id': user_id, 'modified_by': modified_by}
        
        if email is not None:
            if not validate_email(email):
                logger.error(f"Invalid email format: {email}")
                return False
            updates.append("email = :email")
            params['email'] = email
        
        if first_name is not None:
            updates.append("first_name = :first_name")
            params['first_name'] = first_name
        
        if last_name is not None:
            updates.append("last_name = :last_name")
            params['last_name'] = last_name
        
        if is_active is not None:
            updates.append("is_active = :is_active")
            params['is_active'] = 1 if is_active else 0
        
        if not updates:
            logger.warning("No updates to perform")
            return True
        
        updates.append("modified_date = SYSTIMESTAMP")
        updates.append("modified_by = :modified_by")
        
        sql = f"UPDATE users SET {', '.join(updates)} WHERE user_id = :user_id"
        cursor.execute(sql, **params)
        
        connection.commit()
        cursor.close()
        
        log_user_activity(
            user_id=user_id,
            username=username,
            activity_type='USER_UPDATED',
            activity_description=f'User information updated by {modified_by}',
            success=True
        )
        
        logger.info(f"User {username} updated successfully by {modified_by}")
        return True
        
    except oracledb.Error as error:
        logger.error(f"Database error updating user: {error}")
        if connection:
            connection.rollback()
        return False
    finally:
        if connection:
            connection.close()


def delete_user(user_id: int, deleted_by: str = 'SYSTEM') -> bool:
    """
    Deactivate a user (soft delete)
    
    Args:
        user_id: User ID
        deleted_by: Username of the person deleting the user
        
    Returns:
        True if successful, False otherwise
    """
    connection = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor()
        
        cursor.execute("SELECT username FROM users WHERE user_id = :user_id", 
                      user_id=user_id)
        row = cursor.fetchone()
        if not row:
            logger.error(f"User not found: {user_id}")
            return False
        
        username = row[0]
        
        cursor.execute("""
            UPDATE users
            SET is_active = 0,
                modified_date = SYSTIMESTAMP,
                modified_by = :deleted_by
            WHERE user_id = :user_id
        """, user_id=user_id, deleted_by=deleted_by)
        
        connection.commit()
        cursor.close()
        
        log_user_activity(
            user_id=user_id,
            username=username,
            activity_type='USER_DELETED',
            activity_description=f'User deactivated by {deleted_by}',
            success=True
        )
        
        logger.info(f"User {username} deactivated by {deleted_by}")
        return True
        
    except oracledb.Error as error:
        logger.error(f"Database error deleting user: {error}")
        if connection:
            connection.rollback()
        return False
    finally:
        if connection:
            connection.close()