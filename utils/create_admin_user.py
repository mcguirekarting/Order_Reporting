#!/usr/bin/env python3
"""
Initial User Setup Script
Creates the first admin user for the reporting system
Run this after setting up the database schema
"""

import sys
import os
import getpass

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()  
# This will load your .env file

# Add utils directory to path
sys.path.append('/opt/airflow')

from utils.user_management import create_user, get_user_info


def create_admin_user():
    """
    Interactive script to create the first admin user
    """
    print("=" * 60)
    print("Report Microservice - Initial Admin User Setup")
    print("=" * 60)
    print()
    
    # Get user input
    username = input("Enter admin username: ").strip()
    if not username:
        print("ERROR: Username is required")
        return False
    
    email = input("Enter admin email: ").strip()
    if not email:
        print("ERROR: Email is required")
        return False
    
    first_name = input("Enter first name (optional): ").strip() or None
    last_name = input("Enter last name (optional): ").strip() or None
    
    # Get password with confirmation
    while True:
        password = getpass.getpass("Enter password: ")
        if not password:
            print("ERROR: Password is required")
            continue
        
        password_confirm = getpass.getpass("Confirm password: ")
        
        if password != password_confirm:
            print("ERROR: Passwords do not match. Please try again.")
            continue
        
        break
    
    print()
    print("Creating admin user...")
    
    try:
        # Create the user with ADMIN role
        user_id = create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            roles=['ADMIN'],
            created_by='SYSTEM',
            must_change_password=False
        )
        
        if user_id:
            print()
            print("=" * 60)
            print("SUCCESS! Admin user created successfully")
            print("=" * 60)
            print(f"User ID: {user_id}")
            print(f"Username: {username}")
            print(f"Email: {email}")
            print(f"Role: ADMIN")
            print()
            print("You can now log in to the system with these credentials.")
            print("=" * 60)
            return True
        else:
            print()
            print("ERROR: Failed to create admin user")
            print("Please check the logs for more details")
            return False
            
    except Exception as e:
        print()
        print(f"ERROR: An exception occurred: {str(e)}")
        return False


def create_sample_users():
    """
    Create sample users for testing (optional)
    """
    print()
    create_samples = input("Would you like to create sample test users? (y/n): ").strip().lower()
    
    if create_samples != 'y':
        return
    
    print("\nCreating sample users...")
    
    sample_users = [
        {
            'username': 'report_manager',
            'email': 'manager@example.com',
            'password': 'Manager123!',
            'first_name': 'Report',
            'last_name': 'Manager',
            'roles': ['REPORT_MANAGER']
        },
        {
            'username': 'report_viewer',
            'email': 'viewer@example.com',
            'password': 'Viewer123!',
            'first_name': 'Report',
            'last_name': 'Viewer',
            'roles': ['REPORT_VIEWER']
        },
        {
            'username': 'report_executor',
            'email': 'executor@example.com',
            'password': 'Executor123!',
            'first_name': 'Report',
            'last_name': 'Executor',
            'roles': ['REPORT_EXECUTOR']
        }
    ]
    
    for user_data in sample_users:
        try:
            user_id = create_user(
                username=user_data['username'],
                email=user_data['email'],
                password=user_data['password'],
                first_name=user_data['first_name'],
                last_name=user_data['last_name'],
                roles=user_data['roles'],
                created_by='SYSTEM'
            )
            
            if user_id:
                print(f"✓ Created user: {user_data['username']} (Role: {user_data['roles'][0]})")
            else:
                print(f"✗ Failed to create user: {user_data['username']}")
        except Exception as e:
            print(f"✗ Error creating user {user_data['username']}: {str(e)}")
    
    print("\nSample users created!")
    print("\nTest Credentials:")
    print("-" * 40)
    for user_data in sample_users:
        print(f"Username: {user_data['username']}")
        print(f"Password: {user_data['password']}")
        print(f"Role: {user_data['roles'][0]}")
        print("-" * 40)


if __name__ == "__main__":
    try:
        # Create admin user
        success = create_admin_user()
        
        if success:
            # Optionally create sample users
            create_sample_users()
        
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\n\nSetup cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nUnexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
