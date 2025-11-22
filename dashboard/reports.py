import logging
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from dashboard.auth import role_required
from utils.mongo_report_config import (
    get_all_report_configs,
    get_report_config,
    create_report_config,
    update_report_config,
    delete_report_config
)

logger = logging.getLogger(__name__)

bp = Blueprint('reports', __name__, url_prefix='/reports')


@bp.route('/')
@login_required
def list_reports():
    """List all report configurations"""
    try:
        reports = get_all_report_configs()
        return render_template('reports/list.html', reports=reports, user=current_user)
    except Exception as e:
        logger.error(f"Error listing reports: {str(e)}")
        flash('Error loading report configurations.', 'danger')
        return render_template('reports/list.html', reports=[], user=current_user)


@bp.route('/create', methods=['GET', 'POST'])
@role_required('ADMIN', 'REPORT_MANAGER')
def create_report():
    """Create a new report configuration"""
    if request.method == 'POST':
        try:
            report_data = {
                'report_id': request.form.get('report_id'),
                'name': request.form.get('name'),
                'description': request.form.get('description'),
                'schedule': request.form.get('schedule'),
                'query_parameters': {
                    'view_name': request.form.get('view_name'),
                    'order_type': request.form.get('order_type'),
                    'sort_field': request.form.get('sort_field')
                },
                'report_fields': request.form.get('report_fields', '').split(','),
                'email': {
                    'recipients': request.form.get('recipients', '').split(','),
                    'subject': request.form.get('subject'),
                    'body': request.form.get('body')
                },
                'active': request.form.get('active') == 'on',
                'created_by': current_user.username
            }
            
            result = create_report_config(report_data)
            if result:
                flash(f'Report "{report_data["name"]}" created successfully!', 'success')
                return redirect(url_for('reports.list_reports'))
            else:
                flash('Error creating report configuration.', 'danger')
        except Exception as e:
            logger.error(f"Error creating report: {str(e)}")
            flash(f'Error: {str(e)}', 'danger')
    
    return render_template('reports/create.html', user=current_user)


@bp.route('/<report_id>')
@login_required
def view_report(report_id):
    """View a specific report configuration"""
    try:
        report = get_report_config(report_id)
        if report:
            return render_template('reports/view.html', report=report, user=current_user)
        else:
            flash('Report not found.', 'warning')
            return redirect(url_for('reports.list_reports'))
    except Exception as e:
        logger.error(f"Error viewing report {report_id}: {str(e)}")
        flash('Error loading report configuration.', 'danger')
        return redirect(url_for('reports.list_reports'))


@bp.route('/<report_id>/edit', methods=['GET', 'POST'])
@role_required('ADMIN', 'REPORT_MANAGER')
def edit_report(report_id):
    """Edit a report configuration"""
    try:
        report = get_report_config(report_id)
        if not report:
            flash('Report not found.', 'warning')
            return redirect(url_for('reports.list_reports'))
        
        if request.method == 'POST':
            update_data = {
                'name': request.form.get('name'),
                'description': request.form.get('description'),
                'schedule': request.form.get('schedule'),
                'query_parameters': {
                    'view_name': request.form.get('view_name'),
                    'order_type': request.form.get('order_type'),
                    'sort_field': request.form.get('sort_field')
                },
                'report_fields': request.form.get('report_fields', '').split(','),
                'email': {
                    'recipients': request.form.get('recipients', '').split(','),
                    'subject': request.form.get('subject'),
                    'body': request.form.get('body')
                },
                'active': request.form.get('active') == 'on',
                'modified_by': current_user.username
            }
            
            result = update_report_config(report_id, update_data)
            if result:
                flash(f'Report "{update_data["name"]}" updated successfully!', 'success')
                return redirect(url_for('reports.view_report', report_id=report_id))
            else:
                flash('Error updating report configuration.', 'danger')
        
        return render_template('reports/edit.html', report=report, user=current_user)
    except Exception as e:
        logger.error(f"Error editing report {report_id}: {str(e)}")
        flash('Error loading report for editing.', 'danger')
        return redirect(url_for('reports.list_reports'))


@bp.route('/<report_id>/delete', methods=['POST'])
@role_required('ADMIN', 'REPORT_MANAGER')
def delete_report(report_id):
    """Delete a report configuration"""
    try:
        result = delete_report_config(report_id)
        if result:
            flash('Report deleted successfully!', 'success')
        else:
            flash('Error deleting report.', 'danger')
    except Exception as e:
        logger.error(f"Error deleting report {report_id}: {str(e)}")
        flash(f'Error: {str(e)}', 'danger')
    
    return redirect(url_for('reports.list_reports'))


@bp.route('/api/reports')
@login_required
def api_list_reports():
    """API endpoint to list all reports"""
    try:
        reports = get_all_report_configs()
        return jsonify({'success': True, 'reports': reports})
    except Exception as e:
        logger.error(f"API error listing reports: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500
