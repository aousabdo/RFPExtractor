import streamlit as st
import os
import random
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any
import document_management_ui
import admin_panel
from .pdf_processing import generate_pdf_report, generate_report_filename, process_uploaded_pdf
from .chat import display_chat_interface

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


