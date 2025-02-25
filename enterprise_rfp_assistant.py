#!/usr/bin/env python3
import streamlit as st
import os
import json
import time
import uuid
from typing import Dict, Any, List, Optional
from openai import OpenAI
import upload_pdf
from rfp_filter import run_filter, SECTIONS
import process_rfp
import logging
from datetime import datetime, timedelta
import random

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

# Try to get API key from environment or let user input it
openai_api_key = os.getenv("OPENAI_API_KEY", "")

# Function to get OpenAI client
def get_openai_client():
    return OpenAI(api_key=st.session_state.openai_api_key)

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
    }}
    
    /* Sidebar */
    [data-testid="stSidebar"] {{
        background-color: {colors["sidebar_bg"]};
    }}
    
    /* Typography */
    h1, h2, h3, h4, h5, h6 {{
        color: {colors["text"]};
        font-weight: 600;
    }}
    
    p, li, span, label {{
        color: {colors["text"]};
    }}
    
    /* Card Styling */
    .enterprise-card {{
        background-color: {colors["card_bg"]};
        border-radius: 0.5rem;
        padding: 1.5rem;
        margin: 1rem 0;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
        border: 1px solid {colors["border"]};
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }}
    
    .enterprise-card:hover {{
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
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
    
    /* Dashboard Statistics */
    .stat-container {{
        display: flex;
        flex-wrap: wrap;
        gap: 1rem;
        justify-content: space-between;
        margin-bottom: 1.5rem;
    }}
    
    .stat-card {{
        background-color: {colors["card_bg"]};
        border-radius: 0.5rem;
        padding: 1.25rem;
        flex: 1;
        min-width: calc(25% - 1rem);
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
        border-left: 4px solid {colors["primary"]};
    }}
    
    .stat-value {{
        font-size: 1.5rem;
        font-weight: 700;
        color: {colors["primary"]};
        margin-bottom: 0.25rem;
    }}
    
    .stat-label {{
        font-size: 0.875rem;
        color: {colors["text_muted"]};
    }}
    
    /* Section Headers */
    .section-header {{
        color: {colors["primary"]};
        font-size: 1.25rem;
        font-weight: 600;
        margin: 1.5rem 0 1rem 0;
        padding-bottom: 0.5rem;
        border-bottom: 1px solid {colors["border"]};
        display: flex;
        align-items: center;
    }}
    
    .section-header svg {{
        margin-right: 0.5rem;
    }}
    
    /* Information Panels */
    .info-panel {{
        background-color: {colors["card_bg"]};
        border-radius: 0.5rem;
        padding: 1.5rem;
        margin: 1rem 0;
        border-top: 4px solid {colors["primary"]};
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
    }}
    
    /* Requirement Cards */
    .req-category {{
        font-weight: 600;
        font-size: 1rem;
        color: {colors["primary"]};
        margin-top: 1rem;
        background-color: {colors["background"]};
        padding: 0.5rem 0.75rem;
        border-radius: 0.25rem;
    }}
    
    .req-item {{
        padding: 0.75rem;
        border-left: 3px solid {colors["secondary"]};
        margin: 0.5rem 0;
        background-color: {colors["background"]};
        border-radius: 0 0.25rem 0.25rem 0;
    }}
    
    .page-badge {{
        display: inline-block;
        background-color: {colors["primary_light"]};
        color: white;
        padding: 0.125rem 0.5rem;
        border-radius: 1rem;
        font-size: 0.75rem;
        margin-left: 0.5rem;
        vertical-align: middle;
    }}
    
    /* Button Styling */
    .stButton>button {{
        background-color: {colors["primary"]};
        color: white;
        border-radius: 0.375rem;
        border: none;
        padding: 0.625rem 1.25rem;
        font-weight: 500;
        transition: all 0.2s;
    }}
    
    .stButton>button:hover {{
        background-color: {colors["primary_light"]};
        transform: translateY(-1px);
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }}
    
    /* File Uploader */
    .stFileUploader {{
        border: 2px dashed {colors["primary"]};
        border-radius: 0.5rem;
        padding: 1.5rem;
        background-color: {colors["card_bg"]};
    }}
    
    .upload-container {{
        text-align: center;
        padding: 2rem;
        background-color: {colors["card_bg"]};
        border-radius: 0.5rem;
        border: 2px dashed {colors["border"]};
    }}
    
    .upload-icon {{
        font-size: 3rem;
        color: {colors["primary"]};
        margin-bottom: 1rem;
    }}
    
    /* Alerts and Messages */
    .alert {{
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 0.5rem;
        border-left: 4px solid;
    }}
    
    .alert-info {{
        background-color: rgba(59, 130, 246, 0.1);
        border-left-color: {colors["info"]};
    }}
    
    .alert-success {{
        background-color: rgba(16, 185, 129, 0.1);
        border-left-color: {colors["success"]};
    }}
    
    .alert-warning {{
        background-color: rgba(245, 158, 11, 0.1);
        border-left-color: {colors["warning"]};
    }}
    
    .alert-danger {{
        background-color: rgba(239, 68, 68, 0.1);
        border-left-color: {colors["danger"]};
    }}
    
    /* Chat Messages */
    .chat-container {{
        display: flex;
        flex-direction: column;
        gap: 1rem;
        margin: 1.5rem 0;
        max-width: 100%;
    }}
    
    .chat-message {{
        display: flex;
        padding: 0;
        border-radius: 0.5rem;
    }}
    
    .user-message {{
        justify-content: flex-end;
    }}
    
    .message-content {{
        padding: 1rem;
        border-radius: 0.5rem;
        max-width: 80%;
        box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
    }}
    
    .user-message .message-content {{
        background-color: {colors["user_msg_bg"]};
        color: {colors["text"] if colors["user_msg_bg"] == "#DBEAFE" else "white"};
        border-top-right-radius: 0;
    }}
    
    .assistant-message .message-content {{
        background-color: {colors["bot_msg_bg"]};
        color: {colors["text"]};
        border-top-left-radius: 0;
    }}
    
    .message-avatar {{
        width: 2.5rem;
        height: 2.5rem;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        margin-right: 0.75rem;
        font-weight: bold;
        font-size: 1rem;
    }}
    
    .user-avatar {{
        background-color: {colors["primary"]};
        color: white;
    }}
    
    .assistant-avatar {{
        background-color: {colors["secondary"]};
        color: white;
    }}
    
    /* Form Elements */
    .stTextInput>div>div>input {{
        border-radius: 0.5rem !important;
        border: 1px solid {colors["border"]} !important;
        padding: 0.75rem 1rem !important;
        background-color: {colors["card_bg"]} !important;
        color: {colors["text"]} !important;
    }}
    
    .stTextInput>div>div>input:focus {{
        border-color: {colors["primary"]} !important;
        box-shadow: 0 0 0 2px {colors["primary_light"]}40 !important;
    }}
    
    /* Expander Styling */
    .streamlit-expanderHeader {{
        background-color: {colors["card_bg"]};
        border-radius: 0.5rem;
        padding: 0.75rem 1rem !important;
        font-weight: 500;
        color: {colors["text"]} !important;
        border: 1px solid {colors["border"]};
    }}
    
    .streamlit-expanderContent {{
        background-color: {colors["card_bg"]};
        border-radius: 0 0 0.5rem 0.5rem;
        padding: 1.5rem !important;
        border: 1px solid {colors["border"]};
        border-top: none;
    }}
    
    /* Loading Animation */
    .stSpinner>div {{
        border-top-color: {colors["primary"]} !important;
    }}
    
    /* Status Badge */
    .status-badge {{
        display: inline-flex;
        align-items: center;
        padding: 0.25rem 0.75rem;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 500;
        margin-left: 0.75rem;
    }}
    
    .status-badge.active {{
        background-color: {colors["success"]}20;
        color: {colors["success"]};
    }}
    
    .status-badge.inactive {{
        background-color: {colors["text_muted"]}20;
        color: {colors["text_muted"]};
    }}
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {{
        gap: 0.5rem;
    }}
    
    .stTabs [data-baseweb="tab"] {{
        background-color: {colors["card_bg"]} !important;
        border-radius: 0.5rem 0.5rem 0 0;
        padding: 0.75rem 1rem;
        color: {colors["text_muted"]};
        border: 1px solid {colors["border"]};
        border-bottom: none;
    }}
    
    .stTabs [aria-selected="true"] {{
        color: {colors["primary"]} !important;
        background-color: {colors["card_bg"]} !important;
        border-bottom: 2px solid {colors["primary"]} !important;
    }}
    
    /* Tooltip */
    .tooltip {{
        position: relative;
        display: inline-block;
        cursor: pointer;
    }}
    
    .tooltip .tooltiptext {{
        visibility: hidden;
        width: 200px;
        background-color: {colors["card_bg"]};
        color: {colors["text"]};
        text-align: center;
        border-radius: 6px;
        padding: 0.5rem;
        position: absolute;
        z-index: 1;
        bottom: 125%;
        left: 50%;
        transform: translateX(-50%);
        opacity: 0;
        transition: opacity 0.3s;
        border: 1px solid {colors["border"]};
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }}
    
    .tooltip:hover .tooltiptext {{
        visibility: visible;
        opacity: 1;
    }}
    
    /* Date and progress indicators */
    .date-item {{
        display: flex;
        align-items: center;
        padding: 0.625rem;
        margin: 0.5rem 0;
        background-color: {colors["background"]};
        border-radius: 0.375rem;
        border-left: 3px solid {colors["info"]};
    }}
    
    .date-event {{
        flex: 1;
        font-weight: 500;
    }}
    
    .date-value {{
        font-weight: 600;
        padding: 0.25rem 0.5rem;
        background-color: {colors["primary"]}20;
        border-radius: 0.25rem;
        color: {colors["primary"]};
    }}
    
    /* Progress bar */
    .progress-container {{
        width: 100%;
        background-color: {colors["border"]};
        border-radius: 999px;
        height: 0.5rem;
        margin: 1rem 0;
    }}
    
    .progress-bar {{
        height: 0.5rem;
        border-radius: 999px;
        background-color: {colors["primary"]};
    }}
    
    /* Chat input container */
    .chat-input-container {{
        display: flex;
        margin-top: 1rem;
        background-color: {colors["card_bg"]};
        border-radius: 0.5rem;
        padding: 0.5rem;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
    }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)

# We'll use Streamlit's emoji system instead of SVG icons
# This function is kept for compatibility but not used in the updated code
def get_icons():
    return {}

def display_statistics_cards(rfp_data):
    """Display professional metric cards with clear styling"""
    # Get the metrics
    req_count = len(rfp_data.get('requirements', []))
    task_count = len(rfp_data.get('tasks', []))
    date_count = len(rfp_data.get('dates', []))
    current_time = datetime.now().strftime("%B %d, %Y %H:%M")
    
    # Create title
    st.markdown("### Key Metrics")
    
    # Create columns for metrics
    cols = st.columns(4)
    
    # Professional card style with border and shadow
    card_style = """
        background-color: white;
        border-radius: 8px;
        padding: 20px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        height: 140px;
        display: flex;
        flex-direction: column;
    """
    
    # Card header style
    header_style = """
        color: #333;
        font-size: 18px;
        font-weight: 600;
        margin-bottom: 10px;
        border-bottom: 1px solid #eee;
        padding-bottom: 10px;
    """
    
    # Value style
    value_style = """
        font-size: 32px;
        font-weight: 700;
        margin: 15px 0;
    """
    
    with cols[0]:
        st.markdown(f"""
            <div style="{card_style}">
                <div style="{header_style}">📄 Requirements</div>
                <div style="{value_style} color:#3b82f6;">{req_count}</div>
            </div>
        """, unsafe_allow_html=True)
        
    with cols[1]:
        st.markdown(f"""
            <div style="{card_style}">
                <div style="{header_style}">✅ Tasks</div>
                <div style="{value_style} color:#10b981;">{task_count}</div>
            </div>
        """, unsafe_allow_html=True)
        
    with cols[2]:
        st.markdown(f"""
            <div style="{card_style}">
                <div style="{header_style}">📅 Key Dates</div>
                <div style="{value_style} color:#f43f5e;">{date_count}</div>
            </div>
        """, unsafe_allow_html=True)
        
    with cols[3]:
        st.markdown(f"""
            <div style="{card_style}">
                <div style="{header_style}">🕒 Last Updated</div>
                <div style="font-size: 18px; font-weight: 500; color:#8b5cf6; margin-top: 15px; display: flex; flex-direction: column; justify-content: center;">
                    {current_time}
                </div>
            </div>
        """, unsafe_allow_html=True)
    
    # Add extra space after metrics
    st.markdown("<div style='margin-bottom: 30px;'></div>", unsafe_allow_html=True)

def display_rfp_data(rfp_data: Dict[str, Any]):
    """Display the RFP data in a structured, enterprise-style way"""
    if not rfp_data:
        st.warning("No RFP data to display.")
        return
    
    colors = get_colors()
    
    # Display custom metric cards instead of simple columns
    display_statistics_cards(rfp_data)
    
    # Create tabs for different RFP sections
    tab1, tab2, tab3, tab4 = st.tabs(["📋 Overview", "📝 Requirements", "✅ Tasks", "📅 Timeline"])
    
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

def show_no_rfp_screen():
    """Display welcome screen when no RFP is loaded"""
    colors = get_colors()
    
    # Main welcome container
    st.markdown(f"""
    <div class="enterprise-card">
        <h2 style="text-align: center; margin-bottom: 1.5rem;">Welcome to the Enterprise RFP Analyzer</h2>
        <p style="text-align: center; margin-bottom: 2rem;">
            Upload an RFP document to begin your analysis. Our AI-powered system will extract key information
            and help you understand the requirements, tasks, and timeline.
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Upload container - created separately to avoid rendering issues
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown(f"""
        <div style="text-align: center; padding: 2rem; background-color: {colors['card_bg']}; 
                    border-radius: 0.5rem; border: 2px dashed {colors['border']}; margin: 1rem 0;">
            <div style="font-size: 3rem; color: {colors['primary']}; margin-bottom: 1rem;">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" 
                     stroke="currentColor" width="36" height="36">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                          d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                </svg>
            </div>
            <p>Please upload your RFP document from the sidebar to get started.</p>
        </div>
        """, unsafe_allow_html=True)
    
    # Features section
    st.markdown(f"""
    <div class="enterprise-card" style="margin-top: 1.5rem;">
        <h3 style="color: {colors['primary']}; margin-bottom: 1rem;">Key Features</h3>
        <ul>
            <li>Extract key requirements automatically</li>
            <li>Identify critical tasks and deliverables</li>
            <li>Track important dates and deadlines</li>
            <li>Ask questions about the RFP in natural language</li>
            <li>Get AI-powered insights to help with your response strategy</li>
        </ul>
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
        client = get_openai_client()
        
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
    """Display the chat interface with enterprise styling using Streamlit's native chat components"""
    
    # Display chat messages using Streamlit's chat_message component
    for message in st.session_state.messages:
        if message["role"] == "user":
            with st.chat_message("user"):
                st.markdown(message["content"])
        else:
            with st.chat_message("assistant", avatar="🤖"):
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

def main():
    # Load custom CSS
    load_css()
    
    icons = get_icons()
    colors = get_colors()
    
    # Sidebar for configuration and PDF upload
    with st.sidebar:
        col1, col2 = st.columns([1, 3])
        with col1:
            st.markdown(f"""
            <div style="color: {colors['primary']};">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" width="24" height="24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                    d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
            </div>
            """, unsafe_allow_html=True)
        with col2:
            st.markdown(f"""
            <div>
                <h2 style="margin: 0; color: {colors['primary']}; font-size: 1.5rem;">RFP Analyzer</h2>
                <span style="background-color: #10B981; color: white; padding: 2px 8px; border-radius: 9999px; font-size: 0.7rem;">
                    Enterprise
                </span>
            </div>
            """, unsafe_allow_html=True)
        
        # OpenAI API key input
        st.markdown(f"<p style='font-weight: 500; color: {colors['text']};'>OpenAI API Settings</p>", unsafe_allow_html=True)
        api_key = st.text_input("API Key", value=openai_api_key, type="password", 
                                 help="Your OpenAI API key is required for RFP analysis")
        if api_key:
            st.session_state.openai_api_key = api_key
        
        st.markdown("<hr style='margin: 1.5rem 0;'>", unsafe_allow_html=True)
        
        # AWS Configuration - now hidden and hardcoded
        aws_region = "us-east-1"
        s3_bucket = "my-rfp-bucket"
        s3_key = ""  # Will use the filename if empty
        lambda_url = "https://jc2qj7smmranhdtbxkazthh3hq0ymkih.lambda-url.us-east-1.on.aws/"
        
        # Sections selection
        st.markdown(f"<p style='font-weight: 500; color: {colors['text']};'>Analysis Options</p>", unsafe_allow_html=True)
        section_options = list(SECTIONS.keys())
        selected_sections = st.multiselect(
            "Sections to Extract",
            options=section_options,
            default=["all"],
            help="Select specific sections or 'all' for complete analysis"
        )
        
        st.markdown("<hr style='margin: 1.5rem 0;'>", unsafe_allow_html=True)
        
        # PDF Upload Section
        st.markdown(f"<p style='font-weight: 500; color: {colors['text']};'>Document Upload</p>", unsafe_allow_html=True)
        uploaded_file = st.file_uploader("Upload RFP Document", type=["pdf"], accept_multiple_files=False, 
                                          key=f"uploader_{st.session_state.upload_id}")
        
        if uploaded_file:
            # Add warning about chat history being cleared
            st.markdown("""
            <div class="alert alert-warning">
                <strong>⚠️ Warning:</strong> Processing a new RFP will clear your current chat history.
            </div>
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
                        st.rerun()
    
    # Main content area header with columns for better control
    header_col1, header_col2, header_col3 = st.columns([1, 10, 2])
    
    with header_col1:
        st.markdown(f"""
        <div style="color: {colors['primary']}; margin-top: 0.5rem;">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" width="28" height="28">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" 
                d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
            </svg>
        </div>
        """, unsafe_allow_html=True)
        
    with header_col2:
        st.markdown(f"""
        <h1 style="margin: 0; font-size: 1.8rem; color: {colors['text']};">Enterprise RFP Analyzer</h1>
        """, unsafe_allow_html=True)
        
    with header_col3:
        st.markdown(f"""
        <div style="text-align: right; margin-top: 0.5rem;">
            <span style="background-color: #10B981; color: white; padding: 4px 10px; 
                  border-radius: 9999px; font-size: 0.75rem;">
                Active
            </span>
        </div>
        """, unsafe_allow_html=True)
    
    # Show current RFP info if available, otherwise show welcome screen
    if st.session_state.current_rfp:
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
        display_rfp_data(st.session_state.current_rfp)
        
        st.subheader("💬 RFP Chat Assistant")
        st.write("Ask questions about the RFP and get AI-powered insights to help with your response strategy.")
                
        # Chat interface
        display_chat_interface()
    else:
        show_no_rfp_screen()

    # Add some spacing at the bottom
    st.markdown("<div style='margin-bottom: 100px;'></div>", unsafe_allow_html=True)

if __name__ == "__main__":
    main()