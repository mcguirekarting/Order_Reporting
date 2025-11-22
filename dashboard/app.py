import os
import logging
from flask import Flask, render_template, redirect, url_for, flash, request
from flask_login import LoginManager, login_required, current_user
from flask_wtf.csrf import CSRFProtect
from werkzeug.middleware.proxy_fix import ProxyFix

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['WTF_CSRF_TIME_LIMIT'] = None
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

csrf = CSRFProtect(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please log in to access this page.'


class User:
    def __init__(self, user_id, username, email, roles):
        self.id = user_id
        self.username = username
        self.email = email
        self.roles = roles
        self.is_authenticated = True
        self.is_active = True
        self.is_anonymous = False
    
    def get_id(self):
        return str(self.id)
    
    def has_role(self, role_name):
        return role_name in [r['role_id'] for r in self.roles]


@login_manager.user_loader
def load_user(user_id):
    from utils.user_management import get_user_by_id
    user_data = get_user_by_id(int(user_id))
    if user_data:
        return User(
            user_id=user_data['user_id'],
            username=user_data['username'],
            email=user_data['email'],
            roles=user_data.get('roles', [])
        )
    return None


@app.route('/')
@login_required
def index():
    return render_template('index.html', user=current_user)


@app.route('/health')
def health():
    return {'status': 'healthy', 'service': 'dashboard'}, 200


from dashboard import auth, reports, users

app.register_blueprint(auth.bp)
app.register_blueprint(reports.bp)
app.register_blueprint(users.bp)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
