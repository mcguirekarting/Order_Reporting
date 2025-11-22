# Overview

This is an Apache Airflow-based report microservice that generates automated PDF reports from order data. The system queries external order APIs, processes the data, and generates scheduled reports that are distributed via email. It includes a Flask-based administrative dashboard for managing report configurations and user access.

The application uses:
- **Apache Airflow** for workflow orchestration and scheduling
- **Flask** for the web dashboard
- **MongoDB** for storing report configurations
- **Oracle Database** for user authentication and authorization
- **Docker** for containerized deployment

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Workflow Orchestration
- **Apache Airflow DAGs** handle all report generation workflows
- Dynamic DAG generation reads report configurations from MongoDB and creates tasks at runtime
- Multiple specialized DAGs handle different report types (order summaries, long-released orders, custom reports)
- Tasks are organized using TaskGroups for better organization and parallel execution

## Data Storage Strategy
- **MongoDB** stores report configurations, API responses, and operational metadata
  - Chosen for flexibility with semi-structured report configuration data
  - Allows easy schema evolution as report requirements change
- **Oracle Database** stores user accounts, roles, permissions, and audit logs
  - Selected for ACID compliance requirements in authentication/authorization
  - Supports complex role-based access control (RBAC) with many-to-many relationships

## Authentication & Authorization
- **bcrypt password hashing** with 12 rounds for secure password storage
- **Role-based access control** with predefined roles (ADMIN, REPORT_MANAGER, REPORT_VIEWER, etc.)
- **Flask-Login** manages web sessions for the dashboard
- **Activity logging** tracks all user actions (login, password changes, report modifications) for security auditing
- Database-backed authentication (AUTH_DB) rather than LDAP/OAuth to maintain independence from external systems

## Report Generation Pipeline
1. **Query Phase**: DAG tasks call external order APIs with configured parameters
2. **Data Processing**: Python utilities transform API responses into structured data
3. **PDF Generation**: ReportLab library creates formatted PDF documents with tables and charts
4. **Distribution**: Airflow EmailOperator sends reports to configured recipient lists
5. **Logging**: All API responses and report metadata stored in MongoDB for troubleshooting

## Web Dashboard Architecture
- **Flask application** provides administrative interface
- **Blueprint-based routing** separates concerns (auth, reports, users)
- **Jinja2 templates** with Bootstrap 5 for responsive UI
- **CSRF protection** via Flask-WTF
- **Decorator-based authorization** (@role_required) enforces permissions at route level

# External Dependencies

## Third-Party APIs
- **Order Search API**: External service providing order data (endpoint configured via Airflow Variables)
  - Requires token-based authentication
  - Returns JSON responses with order details
  - Base URL stored in `order_api_base_url` variable

## Databases
- **MongoDB** (mongodb://mongodb:27017/)
  - Database: `order_reports`
  - Collections: `report_configurations`, `api_response_logs`
  - Connection string configurable via environment variable `MONGODB_CONNECTION_STRING`
  
- **Oracle Database** (port 1521, service: ORCL)
  - User tables: `users`, `roles`, `user_roles`, `report_permissions`, `user_activity_log`
  - Credentials: Environment variables `ORACLE_USER`, `ORACLE_PASSWORD`, `ORACLE_HOST`

## Python Libraries
- **apache-airflow**: Workflow orchestration engine
- **pymongo**: MongoDB client for report configuration storage
- **oracledb**: Oracle database connectivity (formerly cx_Oracle)
- **bcrypt**: Secure password hashing
- **pandas**: Data manipulation and analysis
- **reportlab**: PDF generation
- **flask**: Web framework for dashboard
- **flask-login**: Session management
- **requests**: HTTP client for API calls

## Infrastructure
- **Docker Compose**: Multi-container orchestration
- **SMTP Server**: Email delivery for report distribution (configured in Airflow)
- Initialization scripts run on Oracle container startup to create database schema