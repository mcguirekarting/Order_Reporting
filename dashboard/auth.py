import logging
from functools import wraps
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from dashboard.app import User
from utils.user_management import authenticate_user

logger = logging.getLogger(__name__)


bp = Blueprint('auth', __name__, url_prefix='/auth')


def role_required(*required_roles):
    """
    Decorator to restrict access to users with specific roles
    Usage: @role_required('ADMIN', 'REPORT_MANAGER')
    """
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Please log in to access this page.', 'warning')
                return redirect(url_for('auth.login'))
            
            user_role_ids = [r['role_id'] for r in current_user.roles]
            
            if not any(role in user_role_ids for role in required_roles):
                flash('You do not have permission to access this page.', 'danger')
                return redirect(url_for('index'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            flash('Username and password are required.', 'danger')
            return render_template('auth/login.html')
        
        ip_address = request.remote_addr or ''
        user_agent = request.headers.get('User-Agent') or ''
        
        user_data = authenticate_user(username, password, ip_address, user_agent)
        
        if user_data:
            user = User(
                user_id=user_data['user_id'],
                username=user_data['username'],
                email=user_data['email'],
                roles=user_data.get('roles', [])
            )
            login_user(user, remember=True)
            
            flash(f'Welcome back, {user_data["username"]}!', 'success')
            
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password.', 'danger')
    
    return render_template('auth/login.html')


@bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))
