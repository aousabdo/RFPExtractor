import streamlit as st
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Load custom logo from file
def load_svg_logo():
    try:
        with open("rfp_analyzer_logo.svg", "r") as logo_file:
            return logo_file.read()
    except Exception as e:
        logger.error(f"Error loading logo: {str(e)}")
        return None
    
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
        padding-top: 0rem;
        max-width: 100%;
    }}
    
    /* Hide default Streamlit elements */
    #MainMenu {{visibility: hidden;}}
    footer {{visibility: hidden;}}
    .stDeployButton {{visibility: hidden !important;}}
    header {{visibility: hidden;}}
    
    /* Remove extra whitespace at top */
    .stApp {{
        margin-top: -4rem;
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

def we_need_icons():
    return {}