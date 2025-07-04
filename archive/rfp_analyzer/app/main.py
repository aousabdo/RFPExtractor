#!/usr/bin/env python3
import streamlit as st
import os
import json
import time
import uuid
from typing import Dict, Any, List, Optional
from openai import OpenAI
import logging
from datetime import datetime, timedelta
import random
import getpass
import socket
import tempfile
from dotenv import load_dotenv
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors as reportlab_colors
from reportlab.lib.units import inch

# Import configuration
from rfp_analyzer.app.config import (
    OPENAI_API_KEY, MONGODB_URI, MONGODB_DB, 
    AWS_REGION, S3_BUCKET, LAMBDA_URL, 
    COLORS, DEFAULT_MODEL, ADMIN_EMAIL, ADMIN_PASSWORD, ADMIN_NAME
)

# Import application components
from rfp_analyzer.core.storage.document_storage import DocumentStorage
from rfp_analyzer.core.storage.db_connection import get_mongodb_connection
from rfp_analyzer.core.auth.user_auth import UserAuth
from rfp_analyzer.app.components import auth_ui
from rfp_analyzer.app.components.auth_ui import require_auth, init_auth_session_state
from rfp_analyzer.app.components.document_ui import render_document_management
from rfp_analyzer.app.components import admin_panel
from rfp_analyzer.app.components.admin_panel import render_admin_panel
from rfp_analyzer.services.aws.s3_service import upload_and_process_pdf
from rfp_analyzer.core.processing.processor import process_pdf
from rfp_analyzer.services import upload_pdf, process_rfp
from rfp_analyzer.app.components import document_management_ui

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Page configuration
st.set_page_config(
    page_title="Enterprise RFP Analyzer",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load custom logo from file
def load_svg_logo():
    try:
        with open("rfp_analyzer_logo.svg", "r") as logo_file:
            return logo_file.read()
    except Exception as e:
        logger.error(f"Error loading logo: {str(e)}")
        return None

# Initialize MongoDB and auth
@st.cache_resource
def init_mongodb_auth():
    """Initialize MongoDB connection, Auth instance, and Document Storage"""
    try:
        # Connect to MongoDB
        mongo_client, mongo_db = get_mongodb_connection()
        
        # Create UserAuth instance
        auth_instance = UserAuth(mongo_db)
        
        # Create DocumentStorage instance
        document_storage = DocumentStorage(mongo_db)
        
        # Create initial admin user if environment variables are set
        admin_email = os.getenv("ADMIN_EMAIL")
        admin_password = os.getenv("ADMIN_PASSWORD")
        admin_name = os.getenv("ADMIN_NAME", "System Administrator")
        
        if admin_email and admin_password:
            auth_instance.create_initial_admin(admin_email, admin_password, admin_name)
        
        return mongo_client, mongo_db, auth_instance, document_storage
    except Exception as e:
        logger.error(f"Failed to initialize MongoDB and Auth: {str(e)}")
        st.error(f"Database connection error: {str(e)}")
        return None, None, None, None

# Get auth instance
# mongo_client, mongo_db, auth_instance = init_mongodb_auth()
mongo_client, mongo_db, auth_instance, document_storage = init_mongodb_auth()


# Store logo in session state so we don't reload it every time
if "logo_svg" not in st.session_state:
    st.session_state.logo_svg = load_svg_logo()

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "current_rfp" not in st.session_state:
    st.session_state.current_rfp = None
if "rfp_name" not in st.session_state:
    st.session_state.rfp_name = None
if "upload_id" not in st.session_state:
    st.session_state.upload_id = str(uuid.uuid4())[:8]
if "system_message" not in st.session_state:
    st.session_state.system_message = """You are an expert RFP analyst assistant for enterprise clients. You help users understand and analyze Request for Proposals (RFPs).
    Your expertise includes extracting key information, identifying requirements, explaining contract terms, and suggesting strategies for responding to RFPs.
    When answering questions, refer specifically to the content of the uploaded RFP. Be precise and cite page numbers when possible.
    If you don't know or the information is not in the RFP, say so clearly.
    Format your responses professionally with markdown formatting where appropriate."""
if "current_document_id" not in st.session_state:
    st.session_state.current_document_id = None

# Try to get API key from environment or let user input it
def get_env_api_key():
    """Get API key from environment with proper formatting"""
    try:
        # Read directly from .env file to avoid any OS environment variable issues
        with open('.env', 'r') as f:
            for line in f:
                if line.strip() and line.startswith('OPENAI_API_KEY=') and not line.startswith('#'):
                    # Extract everything after the equals sign
                    api_key = line.split('=', 1)[1].strip()
                    print(f"DEBUG - Found API key in .env file with length: {len(api_key)}")
                    return api_key
    except Exception as e:
        print(f"DEBUG - Error reading .env file: {str(e)}")
    
    # Fallback to os.getenv
    api_key = os.getenv("OPENAI_API_KEY", "")
    print(f"DEBUG - Fallback to os.getenv with key length: {len(api_key) if api_key else 0}")
    return api_key

# Get API key using the new function
openai_api_key = get_env_api_key()

# Add debug logging for API key
def debug_api_key(key, source):
    if key:
        # Only show first 4 and last 4 characters for security
        masked_key = f"{key[:4]}...{key[-4:]}" if len(key) > 8 else "***"
        print(f"DEBUG - API KEY from {source}: {masked_key}, Length: {len(key)}")
    else:
        print(f"DEBUG - API KEY from {source}: Not set or empty")

# Debug the initial env API key
debug_api_key(openai_api_key, "ENV file")

# Initialize session state for API key with environment value if not already set
if "openai_api_key" not in st.session_state:
    st.session_state.openai_api_key = openai_api_key
    debug_api_key(st.session_state.openai_api_key, "Session state initialization")
    # Also set it in environment for any subprocess calls
    if openai_api_key:
        os.environ["OPENAI_API_KEY"] = openai_api_key
        debug_api_key(os.environ.get("OPENAI_API_KEY", ""), "Environment set at startup")

# Function to get OpenAI client
def get_openai_client():
    # Use session state API key if available, otherwise fall back to environment key
    api_key = st.session_state.openai_api_key or openai_api_key
    debug_api_key(api_key, "get_openai_client")
    
    # Basic validation to ensure the API key has the expected format
    if not api_key:
        raise ValueError("No OpenAI API key found. Please provide one in the settings.")
    elif not (api_key.startswith('sk-') and len(api_key) > 20):
        print(f"WARNING: API key may have invalid format - length: {len(api_key)}, starts with: {api_key[:5] if len(api_key) >= 5 else api_key}")
    
    return OpenAI(api_key=api_key)

def test_api_key(api_key):
    """Test if the API key is valid by making a small request to OpenAI"""
    if not api_key:
        return False, "No API key provided"
    
    try:
        client = OpenAI(api_key=api_key)
        # Make a minimal API call
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=5
        )
        return True, "API key is valid"
    except Exception as e:
        error_msg = str(e)
        if "quota" in error_msg.lower() or "billing" in error_msg.lower():
            return False, f"API key has quota issues: {error_msg}"
        return False, f"Invalid API key: {error_msg}"

# Define color scheme - simplified to just use light mode colors
def get_colors():
    return {
        "primary": "#2563EB",
        "primary_light": "#3B82F6",
        "secondary": "#059669",
        "background": "#F9FAFB",
        "card_bg": "#FFFFFF",
        "sidebar_bg": "#F3F4F6",
        "text": "#111827",
        "text_muted": "#6B7280",
        "border": "#E5E7EB",
        "success": "#10B981",
        "info": "#3B82F6",
        "warning": "#F59E0B",
        "danger": "#EF4444",
        "user_msg_bg": "#DBEAFE",
        "bot_msg_bg": "#F3F4F6"
    }

# Custom CSS for enterprise UI
def load_css():
    colors = get_colors()
    
    css = f"""
    <style>
    /* Global Reset and Fonts */
    * {{
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif;
    }}
    
    /* App Container */
    .main .block-container {{
        padding-top: 2rem;
        max-width: 100%;
    }}
    
    .main {{
        color: {colors["text"]};
        background-color: #f8f9fa;
    }}
    
    /* Sidebar */
    [data-testid="stSidebar"] {{
        background-color: {colors["sidebar_bg"]};
        border-right: 1px solid {colors["border"]};
    }}
    
    [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {{
        padding-top: 1.5rem;
        padding-bottom: 1.5rem;
    }}
    
    /* Improve sidebar section headers */
    .sidebar-section-header {{
        color: {colors["text"]};
        font-size: 0.9rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 1rem;
        padding-bottom: 0.5rem;
        border-bottom: 1px solid {colors["border"]};
    }}
    
    /* Typography */
    h1, h2, h3, h4, h5, h6 {{
        color: {colors["text"]};
        font-weight: 600;
    }}
    
    h1 {{
        font-size: 2.2rem;
        margin-bottom: 1.5rem;
        font-weight: 700;
    }}
    
    h2 {{
        font-size: 1.8rem;
        margin-bottom: 1rem;
    }}
    
    h3 {{
        font-size: 1.4rem;
        margin-bottom: 0.8rem;
    }}
    
    p, li, span, label {{
        color: {colors["text"]};
    }}
    
    /* Card Styling */
    .enterprise-card {{
        background-color: {colors["card_bg"]};
        border-radius: 10px;
        padding: 1.5rem;
        margin: 1rem 0;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
        border: 1px solid {colors["border"]};
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }}
    
    .enterprise-card:hover {{
        box-shadow: 0 10px 20px -3px rgba(0, 0, 0, 0.1), 0 4px 8px -2px rgba(0, 0, 0, 0.05);
    }}
    
    /* Modern feature card */
    .feature-card {{
        background-color: white;
        border-radius: 10px;
        padding: 1.5rem;
        height: 100%;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
        border: 1px solid #f0f0f0;
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.04);
    }}
    
    .feature-card:hover {{
        transform: translateY(-5px);
        box-shadow: 0 12px 20px rgba(0, 0, 0, 0.08);
    }}
    
    .feature-icon {{
        font-size: 2.2rem;
        margin-bottom: 1rem;
        color: {colors["primary"]};
    }}
    
    /* Button improvements */
    [data-testid="stButton"] button {{
        font-weight: 500;
        border-radius: 8px;
        padding: 0.5rem 1rem;
        transition: all 0.3s ease;
    }}
    
    [data-testid="stButton"] button:hover {{
        transform: translateY(-2px);
        box-shadow: 0 6px 12px rgba(0, 0, 0, 0.1);
    }}
    
    /* Checkbox improvements */
    [data-testid="stCheckbox"] {{
        margin-bottom: 1rem;
    }}
    
    /* Headers */
    .enterprise-header {{
        display: flex;
        align-items: center;
        margin-bottom: 1.5rem;
        padding-bottom: 0.75rem;
        border-bottom: 1px solid {colors["border"]};
    }}
    
    .enterprise-header h1 {{
        font-size: 1.875rem;
        margin: 0;
        color: {colors["text"]};
    }}
    
    .enterprise-header img {{
        margin-right: 0.75rem;
    }}
    
    /* File uploader enhancements */
    [data-testid="stFileUploader"] {{
        background-color: white;
        padding: 1rem;
        border-radius: 10px;
        border: 2px dashed {colors["primary"]}40;
    }}
    
    [data-testid="stFileUploader"]:hover {{
        border-color: {colors["primary"]};
    }}
    
    [data-testid="stFileUploader"] button {{
        background-color: {colors["primary"]};
        color: white;
        font-weight: 500;
    }}
    
    /* Dashboard Statistics */
    .stat-container {{
        display: flex;
        flex-wrap: wrap;
        gap: 1.2rem;
        justify-content: space-between;
        margin-bottom: 1.5rem;
    }}
    
    .stat-card {{
        background-color: white;
        border-radius: 12px;
        padding: 1.5rem;
        flex: 1;
        min-width: calc(25% - 1.5rem);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
        border: 1px solid #f0f0f0;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }}
    
    .stat-card:hover {{
        transform: translateY(-3px);
        box-shadow: 0 8px 16px rgba(0, 0, 0, 0.08);
    }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)

def we_need_icons():
    return {}

def generate_pdf_report(rfp_data: Dict[str, Any], rfp_name: str, model_used: str = "gpt-4o") -> str:
    """
    Generate a PDF report from the RFP analysis data
    
    Args:
        rfp_data: The analyzed RFP data dictionary
        rfp_name: Name of the RFP document
        model_used: The LLM model used for analysis
        
    Returns:
        Path to the generated PDF file
    """
    # Create a temporary file for the PDF
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
        pdf_path = tmp.name
    
    # Create the PDF document
    doc = SimpleDocTemplate(pdf_path, pagesize=letter)
    styles = getSampleStyleSheet()
    
    # Create custom styles
    title_style = ParagraphStyle(
        'Title',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=colors.blue,
        spaceAfter=12
    )
    
    heading_style = ParagraphStyle(
        'Heading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.blue,
        spaceAfter=10,
        spaceBefore=10
    )
    
    subheading_style = ParagraphStyle(
        'Subheading',
        parent=styles['Heading3'],
        fontSize=12,
        textColor=colors.darkblue,
        spaceAfter=8
    )
    
    normal_style = styles["Normal"]
    normal_style.fontSize = 10
    
    # Build the content for the PDF
    content = []
    
    # Add title
    content.append(Paragraph(f"RFP Analysis Report: {rfp_name}", title_style))
    content.append(Spacer(1, 0.25*inch))
    
    # Add metadata
    generation_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        username = getpass.getuser()
    except:
        username = "unknown_user"
    
    try:
        hostname = socket.gethostname()
    except:
        hostname = "unknown_host"
    
    metadata = [
        [Paragraph("<b>Generated On:</b>", normal_style), Paragraph(generation_time, normal_style)],
        [Paragraph("<b>Generated By:</b>", normal_style), Paragraph(username, normal_style)],
        [Paragraph("<b>System:</b>", normal_style), Paragraph(hostname, normal_style)],
        [Paragraph("<b>Model Used:</b>", normal_style), Paragraph(model_used, normal_style)]
    ]
    
    metadata_table = Table(metadata, colWidths=[1.5*inch, 4*inch])
    metadata_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey)
    ]))
    
    content.append(metadata_table)
    content.append(Spacer(1, 0.25*inch))
    
    # Add Customer Info
    if 'customer' in rfp_data and rfp_data['customer']:
        content.append(Paragraph("Customer Information", heading_style))
        content.append(Paragraph(rfp_data['customer'], normal_style))
        content.append(Spacer(1, 0.25*inch))
    
    # Add Scope
    if 'scope' in rfp_data and rfp_data['scope']:
        content.append(Paragraph("Scope of Work", heading_style))
        content.append(Paragraph(rfp_data['scope'], normal_style))
        content.append(Spacer(1, 0.25*inch))
    
    # Add Requirements by category
    if 'requirements' in rfp_data and rfp_data['requirements']:
        content.append(Paragraph("Requirements", heading_style))
        
        # Group requirements by category
        reqs_by_category = {}
        for req in rfp_data['requirements']:
            cat = req.get('category', 'General')
            if cat not in reqs_by_category:
                reqs_by_category[cat] = []
            reqs_by_category[cat].append(req)
        
        for category, reqs in reqs_by_category.items():
            content.append(Paragraph(category, subheading_style))
            
            # Create table data with headers
            table_data = [["Requirement", "Page"]]
            for req in reqs:
                description = req.get('description', 'No description')
                page = req.get('page', 'N/A')
                table_data.append([Paragraph(description, normal_style), page])
            
            # Create and style the table
            req_table = Table(table_data, colWidths=[5*inch, 0.5*inch])
            req_table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (1, 0), (1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold')
            ]))
            
            content.append(req_table)
            content.append(Spacer(1, 0.15*inch))
        
        content.append(Spacer(1, 0.1*inch))
    
    # Add Tasks
    if 'tasks' in rfp_data and rfp_data['tasks']:
        content.append(Paragraph("Tasks", heading_style))
        
        table_data = [["Task", "Description", "Page"]]
        for task in rfp_data['tasks']:
            title = task.get('title', 'Task')
            description = task.get('description', 'No description')
            page = task.get('page', 'N/A')
            table_data.append([
                Paragraph(title, normal_style),
                Paragraph(description, normal_style),
                page
            ])
        
        task_table = Table(table_data, colWidths=[1.5*inch, 3.5*inch, 0.5*inch])
        task_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (2, 0), (2, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold')
        ]))
        
        content.append(task_table)
        content.append(Spacer(1, 0.25*inch))
    
    # Add Key Dates
    if 'dates' in rfp_data and rfp_data['dates']:
        content.append(Paragraph("Key Dates", heading_style))
        
        table_data = [["Event", "Date", "Page"]]
        for date_item in rfp_data['dates']:
            event = date_item.get('event', 'Event')
            date = date_item.get('date', 'No date')
            page = date_item.get('page', 'N/A')
            table_data.append([
                Paragraph(event, normal_style),
                Paragraph(date, normal_style),
                page
            ])
        
        date_table = Table(table_data, colWidths=[2.5*inch, 2.5*inch, 0.5*inch])
        date_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (2, 0), (2, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold')
        ]))
        
        content.append(date_table)
    
    # Add a footer with page numbers
    def add_page_number(canvas, doc):
        page_num = canvas.getPageNumber()
        text = f"Page {page_num}"
        canvas.setFont("Helvetica", 9)
        canvas.drawRightString(7.5*inch, 0.5*inch, text)
        canvas.drawString(0.5*inch, 0.5*inch, f"RFP Analysis: {rfp_name[:30]}")
    
    # Build the PDF
    doc.build(content, onFirstPage=add_page_number, onLaterPages=add_page_number)
    
    return pdf_path

def generate_report_filename(rfp_name: str, model_used: str = "gpt-4o") -> str:
    """
    Generate a well-formatted filename for the PDF report
    
    Args:
        rfp_name: Name of the RFP document
        model_used: The LLM model used for analysis
        
    Returns:
        A formatted filename string
    """
    # Get current timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Get username from session if authenticated
    if st.session_state.user:
        username = st.session_state.user['fullname'].replace(" ", "_")
    else:
        try:
            username = getpass.getuser()
        except:
            username = "user"
    
    # Clean the RFP name to make it filename-safe
    # Remove file extension if present
    if "." in rfp_name:
        rfp_name = rfp_name.rsplit(".", 1)[0]
    
    # Replace spaces and special characters
    clean_rfp_name = "".join(c if c.isalnum() else "_" for c in rfp_name)
    clean_rfp_name = clean_rfp_name[:30]  # Limit length
    
    # Clean model name
    clean_model = model_used.replace("-", "").replace(".", "")
    
    # Format: RFP_Analysis_[RFP_NAME]_[MODEL]_[USERNAME]_[TIMESTAMP].pdf
    filename = f"RFP_Analysis_{clean_rfp_name}_{clean_model}_{username}_{timestamp}.pdf"
    
    return filename

def display_statistics_cards(rfp_data):
    """Display professional metric cards with clear styling"""
    # Create title
    st.markdown("### Key Metrics")
    
    # Get the metrics
    req_count = len(rfp_data.get('requirements', []))
    task_count = len(rfp_data.get('tasks', []))
    date_count = len(rfp_data.get('dates', []))
    current_time = datetime.now().strftime("%B %d, %Y %H:%M")
    
    # Create columns for statistics cards
    cols = st.columns(4)
    
    with cols[0]:
        st.markdown(f"""
        <div style="background-color: white; border-radius: 10px; padding: 20px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); height: 140px;">
            <div style="color: #333; font-size: 18px; font-weight: 600; margin-bottom: 10px; display: flex; align-items: center;">
                <span style="margin-right: 8px;">📄</span> Requirements
            </div>
            <div style="font-size: 36px; font-weight: 700; color: #3b82f6; margin: 15px 0;">
                {req_count}
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with cols[1]:
        st.markdown(f"""
        <div style="background-color: white; border-radius: 10px; padding: 20px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); height: 140px;">
            <div style="color: #333; font-size: 18px; font-weight: 600; margin-bottom: 10px; display: flex; align-items: center;">
                <span style="margin-right: 8px;">✅</span> Tasks
            </div>
            <div style="font-size: 36px; font-weight: 700; color: #10b981; margin: 15px 0;">
                {task_count}
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with cols[2]:
        st.markdown(f"""
        <div style="background-color: white; border-radius: 10px; padding: 20px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); height: 140px;">
            <div style="color: #333; font-size: 18px; font-weight: 600; margin-bottom: 10px; display: flex; align-items: center;">
                <span style="margin-right: 8px;">📅</span> Key Dates
            </div>
            <div style="font-size: 36px; font-weight: 700; color: #f43f5e; margin: 15px 0;">
                {date_count}
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with cols[3]:
        st.markdown(f"""
        <div style="background-color: white; border-radius: 10px; padding: 20px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); height: 140px;">
            <div style="color: #333; font-size: 18px; font-weight: 600; margin-bottom: 10px; display: flex; align-items: center;">
                <span style="margin-right: 8px;">🕒</span> Last Updated
            </div>
            <div style="font-size: 16px; font-weight: 500; color: #8b5cf6; margin-top: 15px;">
                {current_time}
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # Add extra space after metrics
    st.markdown("<div style='margin-bottom: 30px;'></div>", unsafe_allow_html=True)

def display_rfp_data(rfp_data: Dict[str, Any], document_storage):
    """Display the RFP data in a structured, enterprise-style way"""
    if not rfp_data:
        st.warning("No RFP data to display.")
        return
    
    colors = get_colors()
    
    # Professional card style
    card_style = """
        background-color: white;
        border-radius: 8px;
        padding: 20px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        margin-bottom: 20px;
    """
    
    # Section header style
    section_header_style = """
        color: #333;
        font-size: 20px;
        font-weight: 600;
        margin-bottom: 15px;
        border-bottom: 1px solid #eee;
        padding-bottom: 10px;
    """
    
    # Display custom metric cards instead of simple columns
    display_statistics_cards(rfp_data)
    
    # Add Download PDF button in a professional card
    st.markdown(f"""
    <div style="{card_style}">
        <div style="{section_header_style}">📊 Analysis Actions</div>
    </div>
    """, unsafe_allow_html=True)
    
    # Create columns for actions
    action_col1, action_col2, action_col3 = st.columns([1, 1, 1])
    
    with action_col1:
        if st.button("📥 Download PDF Report", key="download_pdf"):
            with st.spinner("Generating PDF report..."):
                try:
                    # Generate the PDF file
                    model_used = "gpt-4o"  # You can modify this if you track the model used
                    pdf_path = generate_pdf_report(rfp_data, st.session_state.rfp_name, model_used)
                    
                    # Generate a good filename
                    filename = generate_report_filename(st.session_state.rfp_name, model_used)
                    
                    # Read the PDF file
                    with open(pdf_path, "rb") as pdf_file:
                        pdf_bytes = pdf_file.read()
                    
                    # Offer the download
                    st.download_button(
                        label="💾 Download Ready - Click Here",
                        data=pdf_bytes,
                        file_name=filename,
                        mime="application/pdf",
                        key="download_pdf_ready"
                    )
                    
                    st.success(f"PDF report generated successfully: {filename}")
                    
                    # Clean up the temporary file
                    try:
                        os.remove(pdf_path)
                    except:
                        pass
                except Exception as e:
                    st.error(f"Error generating PDF: {str(e)}")
    
    # Create tabs for different RFP sections
    # tab1, tab2, tab3, tab4 = st.tabs(["📋 Overview", "📝 Requirements", "✅ Tasks", "📅 Timeline"])
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📋 Overview", "📝 Requirements", "✅ Tasks", "📅 Timeline", "📚 Documents"])

    
    # Professional card style
    card_style = """
        background-color: white;
        border-radius: 8px;
        padding: 20px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        margin-bottom: 20px;
    """
    
    # Section header style
    section_header_style = """
        color: #333;
        font-size: 20px;
        font-weight: 600;
        margin-bottom: 15px;
        border-bottom: 1px solid #eee;
        padding-bottom: 10px;
    """
    
    with tab1:
        # Customer Information with card styling
        st.markdown(f"""
        <div style="{card_style}">
            <div style="{section_header_style}">🏢 Customer Information</div>
            <div style="font-size: 16px; line-height: 1.6;">
                {rfp_data.get('customer', 'No customer information available')}
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Scope of Work with card styling
        st.markdown(f"""
        <div style="{card_style}">
            <div style="{section_header_style}">📄 Scope of Work</div>
            <div style="font-size: 16px; line-height: 1.6;">
                {rfp_data.get('scope', 'No scope information available')}
            </div>
        </div>
        """, unsafe_allow_html=True)

    with tab2:
        if 'requirements' in rfp_data and rfp_data['requirements']:
            # Group requirements by category
            reqs_by_category = {}
            for req in rfp_data['requirements']:
                cat = req.get('category', 'General')
                reqs_by_category.setdefault(cat, []).append(req)
            
            for category, reqs in reqs_by_category.items():
                st.markdown(f"""
                <div style="{card_style}">
                    <div style="{section_header_style}">{category} ({len(reqs)})</div>
                """, unsafe_allow_html=True)
                
                for req in reqs:
                    st.markdown(f"""
                    <div style="padding: 12px; border-radius: 6px; background-color: #f9f9f9; 
                                margin-bottom: 10px; border-left: 4px solid #3b82f6;">
                        <div style="display: flex; justify-content: space-between; align-items: top;">
                            <div style="flex: 1; font-size: 15px;">
                                <strong>{req.get('description', 'No description')}</strong>
                            </div>
                            <div style="text-align: right; color: #3b82f6; font-weight: bold; min-width: 70px;">
                                Page {req.get('page', 'N/A')}
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                
                st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.info("No requirements have been extracted from this RFP.")

    with tab3:
        if 'tasks' in rfp_data and rfp_data['tasks']:
            st.markdown(f"""
            <div style="{card_style}">
                <div style="{section_header_style}">Tasks ({len(rfp_data['tasks'])})</div>
            """, unsafe_allow_html=True)
            
            for task in rfp_data['tasks']:
                st.markdown(f"""
                <div style="padding: 15px; border-radius: 6px; background-color: #f9f9f9; 
                            margin-bottom: 15px; border-left: 4px solid #10b981;">
                    <div style="display: flex; justify-content: space-between; align-items: top;">
                        <div style="flex: 1;">
                            <div style="font-weight: 600; font-size: 16px; margin-bottom: 5px; color: #111827;">
                                {task.get('title', 'Task')}
                            </div>
                            <div style="font-size: 15px;">{task.get('description', 'No description available')}</div>
                        </div>
                        <div style="text-align: right; color: #10b981; font-weight: bold; min-width: 70px;">
                            Page {task.get('page', 'N/A')}
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.info("No tasks have been extracted from this RFP.")

    with tab4:
        if 'dates' in rfp_data and rfp_data['dates']:
            # Get current date for timeline calculations
            today = datetime.now().date()
            
            # Sort dates list if dates are available to sort
            sorted_dates = []
            try:
                # Try to parse dates and calculate urgency
                for date_item in rfp_data['dates']:
                    try:
                        # Try different date formats
                        date_str = date_item.get('date', '')
                        for fmt in ["%m/%d/%Y", "%m-%d-%Y", "%B %d, %Y", "%Y-%m-%d"]:
                            try:
                                date_obj = datetime.strptime(date_str, fmt).date()
                                break
                            except ValueError:
                                continue
                        else:
                            # If no format worked, create a random future date
                            days_ahead = random.randint(5, 120)
                            date_obj = (today + timedelta(days=days_ahead))
                            
                        sorted_dates.append({
                            "event": date_item.get('event', 'Unnamed Event'),
                            "date_str": date_item.get('date', 'No date'),
                            "date_obj": date_obj,
                            "page": date_item.get('page', 'N/A')
                        })
                    except Exception:
                        # If date parsing fails, add with default values
                        sorted_dates.append({
                            "event": date_item.get('event', 'Unnamed Event'),
                            "date_str": date_item.get('date', 'No date'),
                            "date_obj": today + timedelta(days=90),  # Far future
                            "page": date_item.get('page', 'N/A')
                        })
                
                # Sort by date
                sorted_dates.sort(key=lambda x: x["date_obj"])
            except Exception:
                # If sorting fails, use original order
                sorted_dates = [{
                    "event": date.get('event', 'Unnamed Event'),
                    "date_str": date.get('date', 'No date'),
                    "page": date.get('page', 'N/A')
                } for date in rfp_data['dates']]
            
            # Display the dates in card format
            st.markdown(f"""
            <div style="{card_style}">
                <div style="{section_header_style}">Key Dates ({len(sorted_dates)})</div>
            """, unsafe_allow_html=True)
            
            for date in sorted_dates:
                st.markdown(f"""
                <div style="padding: 15px; border-radius: 6px; background-color: #f9f9f9; 
                            margin-bottom: 10px; border-left: 4px solid #f43f5e;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div style="flex: 1;">
                            <div style="font-weight: 600; font-size: 16px; margin-bottom: 5px; color: #111827;">
                                {date['event']}
                            </div>
                            <div style="font-size: 15px; color: #4b5563; font-style: italic;">
                                {date['date_str']}
                            </div>
                        </div>
                        <div style="text-align: right; color: #f43f5e; font-weight: bold; min-width: 70px;">
                            Page {date['page']}
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.info("No key dates have been extracted from this RFP.")

    with tab5:
        document_management_ui.render_document_management(document_storage, colors)

def render_app_header():
    """Render the application header with logo"""
    colors = get_colors()
    
    # Create header container
    header_container = st.container()
    
    with header_container:
        # Add a subtle border at the bottom of the header
        st.markdown(f"""
        <div style="margin: -2rem -4rem 2rem -4rem; padding: 1.5rem 4rem; 
                 background: linear-gradient(to right, {colors['card_bg']}, white); 
                 border-bottom: 1px solid {colors['border']};">
        """, unsafe_allow_html=True)
        
        # Use columns for header - main title and user info
        header_col1, header_col2 = st.columns([9, 1])
        
        with header_col1:
            # Main app title with modern logo
            st.markdown(f"""
            <div style="display: flex; align-items: center;">
                <div style="background: linear-gradient(135deg, {colors['primary']}, {colors['primary']}80); 
                            width: 48px; height: 48px; border-radius: 12px; display: flex; 
                            align-items: center; justify-content: center; margin-right: 16px;
                            box-shadow: 0 4px 12px {colors['primary']}40;">
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="white" width="28" height="28">
                        <path d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
                    </svg>
                </div>
                <div>
                    <h1 style="margin: 0; font-size: 1.8rem; font-weight: 700; color: {colors['text']}; 
                              letter-spacing: -0.5px; line-height: 1.2;">
                        Enterprise RFP Analyzer
                    </h1>
                    <div style="display: flex; align-items: center; margin-top: 3px;">
                        <span style="background-color: #10B981; color: white; padding: 2px 10px; 
                              border-radius: 20px; font-size: 0.75rem; font-weight: 500;
                              display: inline-flex; align-items: center;">
                            <span style="width: 6px; height: 6px; background-color: white; 
                                   border-radius: 50%; margin-right: 5px; display: inline-block;"></span>
                            Active
                        </span>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        # Check if user is admin to show the admin panel button in the header
        # Add admin button to header for admin users
        is_admin = "user" in st.session_state and st.session_state.user and st.session_state.user.get('role') == 'admin'
        if is_admin:
            with header_col2:
                # Get current page to highlight the active page
                current_page = st.session_state.get("page", "")
                admin_btn_style = "background-color: #4CAF50; color: white;" if current_page == "admin" else "background-color: #f1f3f4; color: #333;"
                
                # Add the admin button in the header column with better styling
                st.markdown(f"""
                <div style="text-align: right;">
                    <button 
                        onclick="parent.window.document.querySelector('button[key=\"admin_panel_button\"]').click();" 
                        style="cursor: pointer; border: none; border-radius: 6px; padding: 6px 14px; 
                               font-size: 0.8rem; {admin_btn_style}; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                        Admin Dashboard
                    </button>
                </div>
                """, unsafe_allow_html=True)

        # Add the closing div for the header container
        st.markdown("</div>", unsafe_allow_html=True)

def show_no_rfp_screen():
    """Display welcome screen when no RFP is loaded"""
    colors = get_colors()
    
    # Main welcome container with modern design
    st.markdown(f"""
    <div class="enterprise-card" style="text-align: center; padding: 2.5rem; margin-bottom: 2rem; 
        background: linear-gradient(150deg, {colors['card_bg']}, {colors['sidebar_bg']}); border: none;">
        <h1 style="font-size: 2.5rem; margin-bottom: 1rem; color: {colors['primary']};">
            Welcome to the Enterprise RFP Analyzer
        </h1>
        <p style="font-size: 1.1rem; max-width: 800px; margin: 0 auto 1.5rem auto; color: {colors['text']};">
            Upload an RFP document to begin your analysis. Our AI-powered system will extract key information
            and help you understand the requirements, tasks, and timeline.
        </p>
        <div style="width: 60px; height: 6px; background-color: {colors['primary']}; margin: 0 auto;"></div>
    </div>
    """, unsafe_allow_html=True)
    
    # Create main content area with 2 columns
    col1, col2 = st.columns([3, 2], gap="large")
    
    # Features section in column 1 with new grid layout
    with col1:
        st.markdown(f"""
        <div class="enterprise-card" style="border: none; box-shadow: 0 4px 15px rgba(0, 0, 0, 0.05); 
                        padding: 2rem;">
            <h2 style="color: {colors['text']}; margin-bottom: 1.5rem; font-size: 1.8rem;">Key Features</h2>
        """, unsafe_allow_html=True)
        
        # Create a grid of features
        features = [
            {
                "icon": "📋",
                "title": "Extract Requirements",
                "description": "Automatically identify and extract key requirements from RFP documents"
            },
            {
                "icon": "✅",
                "title": "Task Identification",
                "description": "Identify critical tasks and deliverables for your response planning"
            },
            {
                "icon": "📅",
                "title": "Timeline Tracking",
                "description": "Track important dates and deadlines to stay on schedule"
            },
            {
                "icon": "💬",
                "title": "AI Assistant",
                "description": "Ask questions about the RFP in natural language and get instant answers"
            },
            {
                "icon": "🔍",
                "title": "Response Strategy",
                "description": "Get AI-powered insights to help craft a winning proposal"
            },
            {
                "icon": "📊",
                "title": "Analysis Dashboard",
                "description": "View comprehensive analysis results in an intuitive dashboard"
            }
        ]
        
        # Create 3 columns for features
        feature_cols = st.columns(3)
        
        # Add features to the grid with fixed height to ensure consistency
        for i, feature in enumerate(features):
            with feature_cols[i % 3]:
                st.markdown(f"""
                <div style="padding: 1.25rem; margin-bottom: 1.25rem; background-color: white; 
                            border-radius: 8px; height: 250px; box-shadow: 0 2px 8px rgba(0,0,0,0.05);
                            display: flex; flex-direction: column;">
                    <div style="font-size: 2rem; margin-bottom: 0.75rem;">{feature['icon']}</div>
                    <h3 style="font-size: 1.1rem; margin-bottom: 0.75rem; color: {colors['primary']};">
                        {feature['title']}
                    </h3>
                    <p style="font-size: 0.9rem; color: {colors['text_muted']}; line-height: 1.5; flex-grow: 1;">
                        {feature['description']}
                    </p>
                </div>
                """, unsafe_allow_html=True)
        
        st.markdown("</div>", unsafe_allow_html=True)
    
    # Upload container with more prominent design in column 2
    with col2:
        st.markdown(f"""
        <div style="background: linear-gradient(145deg, {colors['primary']}15, {colors['primary']}25); 
                    border-radius: 12px; padding: 2rem; text-align: center; height: 100%;
                    border: 2px dashed {colors['primary']}70; box-shadow: 0 4px 12px rgba(0,0,0,0.05);">
            <div style="background-color: white; width: 80px; height: 80px; border-radius: 50%; 
                        margin: 0 auto 1.5rem auto; display: flex; align-items: center; 
                        justify-content: center; box-shadow: 0 4px 12px rgba(0,0,0,0.1);">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" 
                     stroke="{colors['primary']}" width="40" height="40">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                          d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                </svg>
            </div>
            <h2 style="font-size: 1.4rem; margin-bottom: 1rem; color: {colors['text']};">
                Upload Your RFP Document
            </h2>
            <p style="margin-bottom: 1.5rem; color: {colors['text_muted']}; font-size: 1rem;">
                Use the document uploader in the sidebar to upload your RFP in PDF format
            </p>
            <div style="background-color: {colors['primary']}; color: white; padding: 0.75rem 1.5rem;
                        border-radius: 8px; display: inline-block; font-weight: 500; margin-top: 1rem;
                        box-shadow: 0 4px 12px {colors['primary']}50;">
                <span style="font-size: 1.2rem;">←</span> Upload from Sidebar
            </div>
        </div>
        """, unsafe_allow_html=True)

def process_pdf_locally(pdf_path, selected_sections):
    """Process PDF locally when Lambda function is unavailable"""
    try:
        logger.info(f"Processing PDF locally: {pdf_path}")
        st.info("Using local processing as Lambda function is unavailable...")
        
        # Save the user's OpenAI API key to environment for the local processor to use
        if "openai_api_key" in st.session_state and st.session_state.openai_api_key:
            os.environ["OPENAI_API_KEY"] = st.session_state.openai_api_key
            debug_api_key(os.environ.get("OPENAI_API_KEY", ""), "Environment in process_pdf_locally")
        else:
            st.error("OpenAI API Key is required for local processing. Please enter it in the sidebar.")
            return None
        
        # Process the PDF using the local function
        result = process_rfp.process_pdf(pdf_path)
        
        # Filter by sections if needed
        if "all" not in selected_sections:
            # Simple filtering mechanism - can be enhanced based on your needs
            if "requirements" in result and "requirements" not in selected_sections:
                result["requirements"] = []
            if "tasks" in result and "tasks" not in selected_sections:
                result["tasks"] = []
            if "dates" in result and "dates" not in selected_sections:
                result["dates"] = []
        
        logger.info("Local processing complete")
        return result
    except Exception as e:
        logger.error(f"Local processing failed: {str(e)}")
        raise Exception(f"Failed to process PDF locally: {str(e)}")

def process_uploaded_pdf(uploaded_file, aws_region, s3_bucket, s3_key, lambda_url, selected_sections):
    """Process the uploaded PDF and return structured data"""
    try:
        # Save uploaded file temporarily
        temp_path = f"/tmp/{uploaded_file.name}"
        os.makedirs("/tmp", exist_ok=True)
        with open(temp_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        # Process the PDF
        try:
            result = upload_pdf.upload_and_process_pdf(
                pdf_path=temp_path,
                s3_bucket=s3_bucket,
                s3_key=s3_key or uploaded_file.name,
                aws_region=aws_region,
                lambda_url=lambda_url,
                sections=selected_sections
            )
        except Exception as e:
            error_message = str(e)
            if "502 Server Error: Bad Gateway" in error_message:
                st.markdown("""
                <div class="alert alert-warning">
                    <strong>⚠️ Lambda Gateway Error - Using Local Fallback</strong><br>
                    Cannot connect to the AWS Lambda function. Switching to local processing.
                    This may take longer and require more memory.
                </div>
                """, unsafe_allow_html=True)
                # Try local processing as fallback
                result = process_pdf_locally(temp_path, selected_sections)
            else:
                st.markdown(f"""
                <div class="alert alert-danger">
                    <strong>Error processing PDF:</strong> {error_message}
                </div>
                """, unsafe_allow_html=True)
                return None

        # Clean up temporary file
        if os.path.exists(temp_path):
            os.remove(temp_path)

        # Extract result if nested
        if result and isinstance(result, dict) and 'result' in result:
            return result['result']
        return result

    except Exception as e:
        st.markdown(f"""
        <div class="alert alert-danger">
            <strong>Error processing PDF:</strong> {str(e)}
        </div>
        """, unsafe_allow_html=True)
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return None

def generate_response(prompt: str) -> str:
    """Generate a response using OpenAI based on the prompt and RFP context"""
    try:
        print("DEBUG - Generating response with prompt:", prompt[:50] + "..." if len(prompt) > 50 else prompt)
        client = get_openai_client()
        debug_api_key(client.api_key, "OpenAI client before API call")
        
        # Format RFP data for context
        rfp_context = ""
        if st.session_state.current_rfp:
            rfp_context = "RFP Information:\n"
            if 'customer' in st.session_state.current_rfp:
                rfp_context += f"Customer: {st.session_state.current_rfp['customer']}\n\n"
            if 'scope' in st.session_state.current_rfp:
                rfp_context += f"Scope: {st.session_state.current_rfp['scope']}\n\n"
            
            # Add summary of tasks
            if 'tasks' in st.session_state.current_rfp and st.session_state.current_rfp['tasks']:
                rfp_context += "Major Tasks:\n"
                for task in st.session_state.current_rfp['tasks'][:5]:  # Limit to first 5 for brevity
                    rfp_context += f"- {task.get('title', 'Task')}: {task.get('description', 'No description')} (Page {task.get('page', 'N/A')})\n"
                if len(st.session_state.current_rfp['tasks']) > 5:
                    rfp_context += f"... and {len(st.session_state.current_rfp['tasks']) - 5} more tasks\n"
                rfp_context += "\n"
            
            # Add summary of requirements by category
            if 'requirements' in st.session_state.current_rfp and st.session_state.current_rfp['requirements']:
                rfp_context += "Key Requirements:\n"
                reqs_by_category = {}
                for req in st.session_state.current_rfp['requirements']:
                    cat = req.get('category', 'General')
                    reqs_by_category.setdefault(cat, []).append(req)
                
                for category, reqs in reqs_by_category.items():
                    rfp_context += f"{category}:\n"
                    for req in reqs[:3]:  # Limit to first 3 per category
                        rfp_context += f"- {req.get('description', 'No description')} (Page {req.get('page', 'N/A')})\n"
                    if len(reqs) > 3:
                        rfp_context += f"... and {len(reqs) - 3} more requirements in this category\n"
                rfp_context += "\n"
            
            # Add key dates
            if 'dates' in st.session_state.current_rfp and st.session_state.current_rfp['dates']:
                rfp_context += "Key Dates:\n"
                for date in st.session_state.current_rfp['dates'][:5]:  # Limit to first 5
                    rfp_context += f"- {date.get('event', 'Event')}: {date.get('date', 'No date')} (Page {date.get('page', 'N/A')})\n"
                if len(st.session_state.current_rfp['dates']) > 5:
                    rfp_context += f"... and {len(st.session_state.current_rfp['dates']) - 5} more dates\n"
        
        # Create message list for the API call
        messages = [
            {"role": "system", "content": st.session_state.system_message}
        ]
        
        # Add RFP context if available
        if rfp_context:
            messages.append({"role": "system", "content": f"Current RFP being analyzed: {st.session_state.rfp_name}\n\n{rfp_context}"})
        
        # Add conversation history (limited to last 10 messages to avoid token limits)
        for msg in st.session_state.messages[-10:]:
            messages.append({"role": msg["role"], "content": msg["content"]})
        
        # Add the current prompt
        messages.append({"role": "user", "content": prompt})
        
        # Call the API
        response = client.chat.completions.create(
            model="gpt-4o",  # or another appropriate model
            messages=messages,
            temperature=0.7,
            max_tokens=1000
        )
        
        return response.choices[0].message.content
    except Exception as e:
        return f"I apologize, but I encountered an error: {str(e)}"

def display_chat_interface():
    """Display the chat interface for interacting with the RFP data"""
    st.markdown("<h3>Ask about this RFP</h3>", unsafe_allow_html=True)
    
    # Initialize message history if not already done
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    # Display previous messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"], avatar="🤖" if message["role"] == "assistant" else None):
            st.markdown(message["content"])

    # Chat input using Streamlit's native component
    if "openai_api_key" in st.session_state and st.session_state.openai_api_key:
        if prompt := st.chat_input("Ask me about this RFP..."):
            # Add user message to chat history
            st.session_state.messages.append({"role": "user", "content": prompt})
            
            # Display user message
            with st.chat_message("user"):
                st.markdown(prompt)
            
            # Generate and display response
            with st.chat_message("assistant", avatar="🤖"):
                with st.spinner("Analyzing RFP data..."):
                    response = generate_response(prompt)
                    st.markdown(response)
            
            # Add assistant response to chat history
            st.session_state.messages.append({"role": "assistant", "content": response})
            
            # Force refresh
            st.rerun()
    else:
        st.warning("Please enter your OpenAI API key in the sidebar to enable chat functionality.")

def main_content():
    """Main application content when authenticated"""
    # Load custom CSS
    load_css()
    colors = get_colors()
    
    # Render the app header
    render_app_header()
    
    # Check if user is admin and add admin panel tab if so
    is_admin = "user" in st.session_state and st.session_state.user and st.session_state.user.get('role') == 'admin'
    
    # Sidebar for configuration and PDF upload
    with st.sidebar:
        # Improved sidebar organization with section headers
        
        # Add admin section for admin users
        if is_admin:
            st.markdown(f"""
            <div class="sidebar-section">
                <div class="sidebar-section-header">Admin Controls</div>
            </div>
            """, unsafe_allow_html=True)
            
            if st.button("🔐 Admin Panel", key="admin_panel_button", use_container_width=True):
                st.session_state.page = "admin"
                # Force a rerun to refresh the page
                st.rerun()
                
            st.markdown("<div style='margin-bottom: 25px;'></div>", unsafe_allow_html=True)
        
        # OpenAI API Settings Section
        st.markdown(f"""
        <div class="sidebar-section">
            <div class="sidebar-section-header">OpenAI API Settings</div>
        </div>
        """, unsafe_allow_html=True)
        
        # Check if environment API key exists
        has_env_api_key = bool(openai_api_key)
        
        # Option to use own API key
        use_own_api_key = st.checkbox("Use my own API key", 
                                     value=not has_env_api_key,
                                     help="Check this to provide your own OpenAI API key")
        
        if use_own_api_key:
            # User provides their own API key
            user_api_key = st.text_input("API Key", value="", type="password", 
                                   help="Your OpenAI API key is required for RFP analysis")
            if user_api_key:
                st.session_state.openai_api_key = user_api_key
                debug_api_key(user_api_key, "User input in sidebar")
        else:
            # Use environment API key without showing it
            if has_env_api_key:
                st.success("Using system API key")
                # Ensure the environment API key is set in session state
                st.session_state.openai_api_key = openai_api_key
                debug_api_key(openai_api_key, "Environment key set in sidebar")
            else:
                st.error("No system API key found. Please enter your own API key.")
        
        # Ensure OpenAI API key is also set in environment for subprocess calls
        if "openai_api_key" in st.session_state and st.session_state.openai_api_key:
            os.environ["OPENAI_API_KEY"] = st.session_state.openai_api_key
            debug_api_key(os.environ.get("OPENAI_API_KEY", ""), "Environment updated in sidebar")
        
        # Add a button to test the API key
        if st.button("Test API Key"):
            with st.spinner("Testing API key..."):
                if "openai_api_key" in st.session_state and st.session_state.openai_api_key:
                    is_valid, message = test_api_key(st.session_state.openai_api_key)
                    if is_valid:
                        st.success(message)
                    else:
                        st.error(message)
                else:
                    st.error("No API key available to test")
        
        st.markdown("<div style='margin-bottom: 25px;'></div>", unsafe_allow_html=True)
        
        # Document Upload Section
        st.markdown(f"""
        <div class="sidebar-section">
            <div class="sidebar-section-header">Document Upload</div>
        </div>
        """, unsafe_allow_html=True)
        
        # AWS Configuration - now hidden and hardcoded
        aws_region = "us-east-1"
        s3_bucket = "my-rfp-bucket"
        s3_key = ""  # Will use the filename if empty
        lambda_url = "https://jc2qj7smmranhdtbxkazthh3hq0ymkih.lambda-url.us-east-1.on.aws/"
        
        # Set default to "all" for sections to extract (no UI shown to user)
        selected_sections = ["all"]
        
        # Enhanced uploader with better UI
        st.markdown(f"""
        <div style="margin-bottom: 10px; text-align: center;">
            <svg xmlns="http://www.w3.org/2000/svg" width="36" height="36" fill="none" viewBox="0 0 24 24" stroke="{colors['primary']}">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                d="M9 13h6m-3-3v6m5 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
        </div>
        """, unsafe_allow_html=True)
        
        uploaded_file = st.file_uploader("", type=["pdf"], accept_multiple_files=False, 
                                         key=f"uploader_{st.session_state.upload_id}")
                                         
        # Add helpful instructions below the uploader
        st.markdown(f"""
        <div style="font-size: 0.85rem; color: {colors['text_muted']}; text-align: center; margin-top: 8px;">
            Limit 200MB per file • PDF
        </div>
        """, unsafe_allow_html=True)
        
        if uploaded_file:
            # Add warning about chat history being cleared
            st.markdown(f"""
            <div style="background-color: rgba(245, 158, 11, 0.1); border-left: 4px solid {colors['warning']}; 
                padding: 0.75rem; margin: 1rem 0; border-radius: 0.25rem;">
                <div style="display: flex; align-items: center; gap: 8px;">
                    <div style="color: {colors['warning']}; font-weight: bold;">⚠️</div>
                    <div style="font-weight: 500;">Processing a new RFP will clear your chat history.</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
    
            # Add some space before the button
            st.markdown("<div style='margin-top: 1rem;'></div>", unsafe_allow_html=True)
            
            # Custom button styling
            st.markdown(f"""
            <style>
            div[data-testid="stButton"] > button {{
                background-color: {colors['primary']};
                color: white;
                font-weight: 500;
                border-radius: 0.375rem;
                padding: 0.5rem 1rem;
                width: 100%;
                border: none;
            }}
            div[data-testid="stButton"] > button:hover {{
                background-color: {colors['primary_light']};
                border: none;
            }}
            </style>
            """, unsafe_allow_html=True)
            
            if st.button("Process RFP", key="process_button"):
                with st.spinner("Analyzing document..."):
                    result = process_uploaded_pdf(
                        uploaded_file, 
                        aws_region, 
                        s3_bucket, 
                        s3_key, 
                        lambda_url, 
                        selected_sections
                    )
                    
                    if result:
                        st.session_state.current_rfp = result
                        st.session_state.rfp_name = uploaded_file.name
                        
                        # Clear previous messages when a new RFP is loaded
                        st.session_state.messages = []
                        
                        # Add system message about new RFP being loaded
                        st.session_state.messages.append({
                            "role": "assistant", 
                            "content": f"""✅ **RFP Analysis Complete: {uploaded_file.name}**

I've analyzed this RFP and extracted:
- {len(result.get('requirements', []))} requirements
- {len(result.get('tasks', []))} tasks
- {len(result.get('dates', []))} key dates

You can now ask me questions about this RFP, or explore the analysis using the tabs above."""
                        })
                        
                        st.markdown("""
                        <div class="alert alert-success">
                            <strong>Success!</strong> Document processed successfully.
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # Generate a new upload ID to force the file uploader to reset
                        st.session_state.upload_id = str(uuid.uuid4())[:8]
                        
                        # Store the document in our permanent storage
                        user_id = st.session_state.user.get('user_id')
                        temp_path = f"/tmp/{uploaded_file.name}"
                        os.makedirs("/tmp", exist_ok=True)
                        with open(temp_path, "wb") as f:
                            f.write(uploaded_file.getbuffer())

                        document_id = document_storage.store_document(
                            user_id=user_id,
                            file_path=temp_path,
                            original_filename=uploaded_file.name,
                            metadata={
                                "uploaded_via": "webapp",
                                "aws_region": aws_region,
                                "s3_bucket": s3_bucket,
                                "selected_sections": selected_sections
                            }
                        )

                        # Update the document with analysis results
                        if document_id:
                            document_storage.update_analysis_results(document_id, result)
                            st.session_state.current_document_id = document_id
                        
                        st.rerun()
    
    # Show admin panel if admin user and on admin page
    if is_admin and st.session_state.page == "admin":
        # Debug information
        st.session_state.debug_admin_view = True
        # Render the admin panel
        admin_panel.render_admin_panel(auth_instance, document_storage, colors)
    # Show current RFP info if available, otherwise show welcome screen
    elif st.session_state.current_rfp:
        # Use columns for document info bar
        doc_col1, doc_col2 = st.columns([4, 1])
        with doc_col1:
            st.markdown(f"**Current Document:** {st.session_state.rfp_name}")
        with doc_col2:
            st.markdown("""
            <div style="text-align: right;">
                <span style="background-color: #10B981; color: white; padding: 4px 10px; 
                      border-radius: 9999px; font-size: 0.75rem;">
                    Active Analysis
                </span>
            </div>
            """, unsafe_allow_html=True)
        
        # Display RFP data
        display_rfp_data(st.session_state.current_rfp, document_storage)
        
        st.subheader("💬 RFP Chat Assistant")
        st.write("Ask questions about the RFP and get AI-powered insights to help with your response strategy.")
                
        # Chat interface
        display_chat_interface()
    else:
        show_no_rfp_screen()

    # Add some spacing at the bottom
    st.markdown("<div style='margin-bottom: 100px;'></div>", unsafe_allow_html=True)

def main():
    # Check if MongoDB connection succeeded
    if mongo_db is None or auth_instance is None:
        st.error("Failed to connect to the database. Please check your MongoDB configuration.")
        return
    
    # Load custom CSS
    load_css()
    
    # Require authentication for all content
    auth_ui.require_auth(auth_instance, get_colors(), main_content)

if __name__ == "__main__":
    main()