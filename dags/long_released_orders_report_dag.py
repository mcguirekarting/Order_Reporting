# long_released_orders_report_dag.py
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.email import EmailOperator
from airflow.models import Variable
import requests
import json
import pandas as pd
import logging
import os
import sys
sys.path.append("/opt/airflow")
from utils.report_utils import query_order_api, generate_pdf_report
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from airflow.utils.dates import days_ago

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("long_released_orders_report_service")

# Define default arguments for the DAG
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 3,
    'retry_delay': timedelta(minutes=5),
}

# Function to query orders that have been in released status for more than 72 hours
def query_long_released_orders(**kwargs):
    """
    Query the order search API for orders that have been in released status for more than 72 hours
    """
    # Get execution date from context
    execution_date = kwargs['execution_date']
    
    # Get API configuration from Airflow Variables
    api_base_url = Variable.get("order_api_base_url")
    search_endpoint = f"{api_base_url}/order/order/search"
    
    # Calculate the time threshold (72 hours ago from execution date)
    threshold_time = (execution_date - timedelta(hours=72)).strftime("%Y-%m-%dT%H:%M:%S")
    
    logger.info(f"Searching for orders with Released status from before {threshold_time}")
    
    # Build search payload
    payload = {
        "Query": f"Order.Status.StatusId = 'Released' AND Order.UpdatedTimestamp < '{threshold_time}'",
        "Template": {
            "OrderId": None,
            "Order": {
                "Status": {
                    "StatusId": None
                },
                "OrderTypeId": None,
                "CreatedTimestamp": None,
                "UpdatedTimestamp": None,
                "ExpectedDeliveryDate": None
            },
            "OrderLine": [
                {
                    "OrderLineId": None,
                    "ItemId": None,
                    "Description": None,
                    "Quantity": None,
                    "Status": {
                        "StatusId": None
                    },
                    "ShipNode": {
                        "LocationId": None
                    }
                }
            ],
            "Release": [
                {
                    "ReleaseId": None,
                    "Status": {
                        "StatusId": None
                    }
                }
            ]
        },
        "Size": 1000,
        "Sort": [
            {
                "attribute": "UpdatedTimestamp",
                "direction": "asc"
            }
        ]
    }
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {Variable.get('api_token', '')}"
    }
    
    try:
        logger.info("Executing search query...")
        response = requests.post(
            search_endpoint, 
            json=payload,
            headers=headers
        )
        
        if response.status_code != 200:
            logger.error(f"Error in API call: {response.status_code} - {response.text}")
            raise Exception(f"API returned error: {response.status_code}")
        
        result_data = response.json()
        
        # Check if we have results
        if not result_data or len(result_data) == 0:
            logger.info("No orders found matching the criteria")
            all_results = []
        else:
            logger.info(f"Retrieved {len(result_data)} orders that have been in Released status for over 72 hours")
            all_results = result_data
        
    except Exception as e:
        logger.error(f"Error during API search: {str(e)}")
        raise
    
    # Create a temporary file to store the results
    result_file = f"/tmp/long_released_orders_{execution_date.strftime('%Y%m%d')}.json"
    with open(result_file, 'w') as f:
        json.dump(all_results, f)
    
    # Return the path to the result file for the next task
    return result_file

# Function to generate a PDF report from the API results
def generate_long_released_report(**kwargs):
    """
    Generate a PDF report showing orders that have been in Released status for more than 72 hours
    """
    # Get the task instance
    ti = kwargs['ti']
    
    # Get the result file path from the previous task
    result_file = ti.xcom_pull(task_ids='query_long_released_orders')
    execution_date = kwargs['execution_date']
    
    logger.info(f"Generating PDF report from {result_file}")
    
    # Load the results
    with open(result_file, 'r') as f:
        results = json.load(f)
    
    if not results:
        logger.warning("No results found for report generation")
        # Create an empty PDF with a message
        pdf_file = f"/tmp/long_released_orders_report_{execution_date.strftime('%Y%m%d')}.pdf"
        doc = SimpleDocTemplate(pdf_file, pagesize=letter)
        styles = getSampleStyleSheet()
        elements = []
        elements.append(Paragraph(f"Long Released Orders Report - {execution_date.strftime('%Y-%m-%d')}", styles['Title']))
        elements.append(Spacer(1, 12))
        elements.append(Paragraph("No orders found in Released status for more than 72 hours.", styles['Normal']))
        doc.build(elements)
        return pdf_file
    
    # Extract and transform the data for reporting
    report_data = []
    
    # Add header row
    headers = ["Order ID", "Order Type", "Created Date", "Last Updated", "Status", "Days in Released Status", "Ship From Locations"]
    report_data.append(headers)
    
    # Process the data and calculate days in released status
    for order in results:
        try:
            order_id = order.get("OrderId", "N/A")
            order_type = order.get("Order", {}).get("OrderTypeId", "N/A")
            created_timestamp = order.get("Order", {}).get("CreatedTimestamp", "N/A")
            updated_timestamp = order.get("Order", {}).get("UpdatedTimestamp", "N/A")
            status = order.get("Order", {}).get("Status", {}).get("StatusId", "N/A")
            
            # Calculate days in released status
            if updated_timestamp != "N/A":
                updated_date = datetime.strptime(updated_timestamp, "%Y-%m-%dT%H:%M:%S.%fZ")
                days_in_status = (execution_date - updated_date).days
            else:
                days_in_status = "N/A"
            
            # Extract unique ship from locations
            ship_nodes = set()
            for line in order.get("OrderLine", []):
                if line.get("ShipNode") and line.get("ShipNode").get("LocationId"):
                    ship_nodes.add(line.get("ShipNode").get("LocationId"))
            
            ship_locations = ", ".join(ship_nodes) if ship_nodes else "N/A"
            
            # Format timestamps for readability
            if created_timestamp != "N/A":
                created_timestamp = datetime.strptime(created_timestamp, "%Y-%m-%dT%H:%M:%S.%fZ").strftime("%Y-%m-%d %H:%M")
            
            if updated_timestamp != "N/A":
                updated_timestamp = datetime.strptime(updated_timestamp, "%Y-%m-%dT%H:%M:%S.%fZ").strftime("%Y-%m-%d %H:%M")
            
            row = [
                order_id,
                order_type,
                created_timestamp,
                updated_timestamp,
                status,
                str(days_in_status) if days_in_status != "N/A" else "N/A",
                ship_locations
            ]
            report_data.append(row)
        except Exception as e:
            logger.error(f"Error processing order data: {str(e)}")
            continue
    
    # Create a DataFrame for summary statistics
    df = pd.DataFrame(report_data[1:], columns=report_data[0])
    if 'Days in Released Status' in df.columns:
        df['Days in Released Status'] = pd.to_numeric(df['Days in Released Status'], errors='coerce')
    
    # Calculate summary statistics
    total_orders = len(df)
    avg_days = df['Days in Released Status'].mean() if 'Days in Released Status' in df.columns else 0
    max_days = df['Days in Released Status'].max() if 'Days in Released Status' in df.columns else 0
    
    # Count orders by days in status ranges
    days_3_to_5 = len(df[(df['Days in Released Status'] >= 3) & (df['Days in Released Status'] < 5)]) if 'Days in Released Status' in df.columns else 0
    days_5_to_7 = len(df[(df['Days in Released Status'] >= 5) & (df['Days in Released Status'] < 7)]) if 'Days in Released Status' in df.columns else 0
    days_over_7 = len(df[df['Days in Released Status'] >= 7]) if 'Days in Released Status' in df.columns else 0
    
    # Generate the PDF
    pdf_file = f"/tmp/long_released_orders_report_{execution_date.strftime('%Y%m%d')}.pdf"
    doc = SimpleDocTemplate(pdf_file, pagesize=landscape(letter))
    
    styles = getSampleStyleSheet()
    elements = []
    
    # Add title
    title = f"Long Released Orders Report - {execution_date.strftime('%Y-%m-%d')}"
    elements.append(Paragraph(title, styles['Title']))
    elements.append(Spacer(1, 12))
    
    # Add description
    description = "This report shows orders that have been in Released status for more than 72 hours from the time of last status update."
    elements.append(Paragraph(description, styles['Normal']))
    elements.append(Spacer(1, 12))
    
    # Add summary section
    elements.append(Paragraph("Summary", styles['Heading2']))
    summary_data = [
        ["Total Orders in Released Status >72 Hours", str(total_orders)],
        ["Average Days in Released Status", f"{avg_days:.1f}" if avg_days else "0"],
        ["Maximum Days in Released Status", f"{max_days:.1f}" if max_days else "0"],
        ["Orders in Released: 3-5 days", str(days_3_to_5)],
        ["Orders in Released: 5-7 days", str(days_5_to_7)],
        ["Orders in Released: 7+ days", str(days_over_7)]
    ]
    
    summary_table = Table(summary_data, colWidths=[300, 150])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 24))
    
    # Add main table
    elements.append(Paragraph("Order Details", styles['Heading2']))
    
    # Create the table
    table = Table(report_data, repeatRows=1)
    
    # Style the table
    table_style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.blue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ])
    
    # Add a zebra striping pattern
    for i in range(1, len(report_data)):
        if i % 2 == 0:
            table_style.add('BACKGROUND', (0, i), (-1, i), colors.lightgrey)
    
    table.setStyle(table_style)
    elements.append(table)
    
    # Build the PDF
    doc.build(elements)
    
    logger.info(f"PDF report generated: {pdf_file}")
    return pdf_file

# Create the DAG
dag = DAG(
    'long_released_orders_report',
    default_args=default_args,
    description='Search for orders in Released status for more than 72 hours, generate a PDF report, and email it',
    schedule_interval='0 6 * * *',  # Run daily at 6:00 AM
    start_date=days_ago(1),
    catchup=False,
    tags=['order', 'report', 'released'],
)

# Task 1: Query orders in Released status for more than 72 hours
task_query_orders = PythonOperator(
    task_id='query_long_released_orders',
    python_callable=query_long_released_orders,
    provide_context=True,
    dag=dag,
)

# Task 2: Generate the PDF report
task_generate_pdf = PythonOperator(
    task_id='generate_long_released_report',
    python_callable=generate_long_released_report,
    provide_context=True,
    dag=dag,
)

# Task 3: Email the PDF report
task_email_report = EmailOperator(
    task_id='email_report',
    to="{{ var.value.report_recipients }}",
    subject="Long Released Orders Report - {{ ds }}",
    html_content="""
        <p>Hello,</p>
        <p>Please find attached the report of orders that have been in Released status for more than 72 hours.</p>
        <p>This report helps identify orders that may require attention due to extended processing time.</p>
        <p>Best regards,<br/>Automated Reporting System</p>
    """,
    files=["{{ ti.xcom_pull(task_ids='generate_long_released_report') }}"],
    dag=dag,
)

# Define task dependencies
task_query_orders >> task_generate_pdf >> task_email_report