import logging
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from dashboard.auth import role_required
from utils.user_management import (
    get_all_users,
    get_user_by_username,
    create_user,
    update_user,
    delete_user,
    reset_password,
    get_user_roles
)

logger = logging.getLogger(__name__)

bp = Blueprint('users', __name__, url_prefix='/users')


@bp.route('/')
@login_required
def list_users():
    """List all users"""
    try:
        users = get_all_users()
        return render_template('users/list.html', users=users, user=current_user)
    except Exception as e:
        logger.error(f"Error listing users: {str(e)}")
        flash('Error loading users.', 'danger')
        return render_template('users/list.html', users=[], user=current_user)


@bp.route('/<username>')
@login_required
def view_user(username):
    """View a specific user"""
    try:
        user_data = get_user_by_username(username)
        if user_data:
            return render_template('users/view.html', view_user=user_data, user=current_user)
        else:
            flash('User not found.', 'warning')
            return redirect(url_for('users.list_users'))
    except Exception as e:
        logger.error(f"Error viewing user {username}: {str(e)}")
        flash('Error loading user information.', 'danger')
        return redirect(url_for('users.list_users'))


@bp.route('/<username>/reset-password', methods=['GET', 'POST'])
@role_required('ADMIN', 'REPORT_ADMIN')
def reset_user_password(username):
    """Reset a user's password (REPORT_ADMIN or ADMIN only)"""
    try:
        user_data = get_user_by_username(username)
        if not user_data:
            flash('User not found.', 'warning')
            return redirect(url_for('users.list_users'))
        
        if request.method == 'POST':
            new_password = request.form.get('new_password')
            confirm_password = request.form.get('confirm_password')
            must_change = request.form.get('must_change_password') == 'on'
            
            if new_password != confirm_password:
                flash('Passwords do not match.', 'danger')
                return render_template('users/reset_password.html', view_user=user_data, user=current_user)
            
            from utils.user_management import validate_password_strength
            is_valid, error_msg = validate_password_strength(new_password)
            if not is_valid:
                flash(f'Password validation failed: {error_msg}', 'danger')
                return render_template('users/reset_password.html', view_user=user_data, user=current_user)
            
            result = reset_password(
                username=username,
                new_password=new_password,
                changed_by=current_user.username,
                must_change_password=must_change
            )
            
            if result:
                flash(f'Password for {username} has been reset successfully!', 'success')
                return redirect(url_for('users.view_user', username=username))
            else:
                flash('Error resetting password.', 'danger')
        
        return render_template('users/reset_password.html', view_user=user_data, user=current_user)
    except Exception as e:
        logger.error(f"Error resetting password for {username}: {str(e)}")
        flash(f'Error: {str(e)}', 'danger')
        return redirect(url_for('users.list_users'))


@bp.route('/create', methods=['GET', 'POST'])
@role_required('ADMIN', 'REPORT_ADMIN')
def create_new_user():
    """Create a new user"""
    if request.method == 'POST':
        try:
            username = request.form.get('username')
            email = request.form.get('email')
            password = request.form.get('password')
            first_name = request.form.get('first_name')
            last_name = request.form.get('last_name')
            roles = request.form.getlist('roles')
            must_change = request.form.get('must_change_password') == 'on'
            
            user_id = create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
                roles=roles,
                created_by=current_user.username,
                must_change_password=must_change
            )
            
            if user_id:
                flash(f'User "{username}" created successfully!', 'success')
                return redirect(url_for('users.list_users'))
            else:
                flash('Error creating user.', 'danger')
        except Exception as e:
            logger.error(f"Error creating user: {str(e)}")
            flash(f'Error: {str(e)}', 'danger')
    
    try:
        available_roles = get_user_roles()
    except Exception:
        available_roles = []
    
    return render_template('users/create.html', available_roles=available_roles, user=current_user)


@bp.route('/api/users')
@login_required
def api_list_users():
    """API endpoint to list all users"""
    try:
        users = get_all_users()
        return jsonify({'success': True, 'users': users})
    except Exception as e:
        logger.error(f"API error listing users: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500
