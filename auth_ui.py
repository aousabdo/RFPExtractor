#!/usr/bin/env python3
import streamlit as st
import logging
from typing import Dict, Any, Optional, Callable
import os
import json
from datetime import datetime

# Configure logging
logger = logging.getLogger(__name__)

def init_auth_session_state():
    """Initialize authentication-related session state variables"""
    # First, check if any document or analysis data exists without a user
    # This would indicate a session state issue we should clean up
    if "user" not in st.session_state or st.session_state.user is None:
        # Keys that shouldn't exist when there's no user logged in
        document_keys = [
            'document_id', 'current_document', 'analysis_results', 
            'requirements', 'tasks', 'key_dates', 'chat_history'
        ]
        
        # Check if any of these exist and clear them
        for key in document_keys:
            if key in st.session_state:
                del st.session_state[key]
                logger.warning(f"Cleared leftover session key: {key}")
    
    # Initialize basic auth variables
    if "user" not in st.session_state:
        st.session_state.user = None
    if "auth_token" not in st.session_state:
        st.session_state.auth_token = None
    if "auth_message" not in st.session_state:
        st.session_state.auth_message = None
    if "auth_status" not in st.session_state:
        st.session_state.auth_status = None  # Can be "success", "error", "info"
    if "page" not in st.session_state:
        st.session_state.page = "login"  # login, register, forgot_password, main, profile
        
    # Add custom CSS for auth buttons and better overall styling
    st.markdown("""
    <style>
    /* Add a subtle gradient background to the page */
    .main .block-container {
        background: linear-gradient(135deg, #f8f9fa, #e9ecef);
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    
    /* Button styling */
    .stButton > button {
        font-weight: 500 !important;
        border-radius: 6px !important;
        height: 2.5rem !important;
        transition: all 0.2s ease !important;
    }
    
    /* Primary button style */
    div[data-testid="column"]:nth-of-type(2) .stButton > button {
        background-color: #0d6efd !important;
        color: white !important;
        border: none !important;
    }
    
    /* Primary button hover */
    div[data-testid="column"]:nth-of-type(2) .stButton > button:hover {
        background-color: #0b5ed7 !important;
        box-shadow: 0 4px 12px rgba(13, 110, 253, 0.3) !important;
        transform: translateY(-2px) !important;
    }
    
    /* Secondary button style */
    div[data-testid="column"]:nth-of-type(1) .stButton > button {
        background-color: #f8f9fa !important;
        color: #212529 !important;
        border: 1px solid #dee2e6 !important;
    }
    
    /* Secondary button hover */
    div[data-testid="column"]:nth-of-type(1) .stButton > button:hover {
        background-color: #e9ecef !important;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1) !important;
        transform: translateY(-2px) !important;
    }
    
    /* Form input styling */
    div[data-baseweb="input"] {
        border-radius: 6px !important;
        margin-bottom: 0.75rem !important;
    }
    
    div[data-baseweb="input"]:focus-within {
        border-color: #0d6efd !important;
        box-shadow: 0 0 0 3px rgba(13, 110, 253, 0.25) !important;
    }
    
    /* Hide Streamlit branding */
    footer {
        visibility: hidden;
    }
    
    /* Hide hamburger menu */
    .st-emotion-cache-1rs6os {
        visibility: hidden;
    }
    </style>
    """, unsafe_allow_html=True)

def render_auth_header(colors: Dict[str, str]):
    """
    Render the authentication header with user menu using native Streamlit components
    
    Args:
        colors: Color scheme dictionary
    """
    if not st.session_state.user:
        return
    
    # Create a container in the top-right corner
    user_menu_container = st.container()
    
    # Use columns to push the menu to the right
    col1, col2, col3 = st.columns([6, 3, 1])
    
    with col3:
        user_fullname = st.session_state.user.get('fullname', 'User')
        user_initial = user_fullname[0].upper() if user_fullname else 'U'
        
        # Use a button with the user's initial as the text
        if st.button(f"{user_initial}", key="user_avatar_button"):
            # Toggle between profile and main page
            if st.session_state.page == "main":
                st.session_state.page = "profile"
            else:
                st.session_state.page = "main"
            st.rerun()

def login_form(auth_instance, colors: Dict[str, str]):
    """
    Display login form
    
    Args:
        auth_instance: UserAuth instance
        colors: Color scheme dictionary
    """
    # Create a more visually appealing login container with properly integrated logo
    st.markdown(f"""
    <div style="text-align: center; max-width: 450px; margin: 2rem auto; 
                padding: 2.5rem; background-color: white; border-radius: 12px; 
                box-shadow: 0 8px 24px rgba(0,0,0,0.12);">
        <div style="text-align: center; margin-bottom: 1.5rem;">
            <div style="display: inline-flex; align-items: center; justify-content: center; 
                       width: 80px; height: 80px; border-radius: 16px; 
                       background: linear-gradient(135deg, #0d6efd, #0dcaf0); 
                       margin-bottom: 1rem;">
                <span style="font-size: 2.5rem; color: white; font-weight: bold;">RFP</span>
            </div>
        </div>
        <h1 style="margin-bottom: 1rem; color: {colors['primary']}; font-size: 2.2rem; font-weight: 600;">RFP Analyzer</h1>
        <div style="width: 80px; height: 5px; background: linear-gradient(90deg, {colors['primary']}, {colors['primary']}80); 
                    margin: 0 auto 2rem auto; border-radius: 10px;"></div>
        <p style="margin-bottom: 2rem; font-size: 1.1rem; color: #555;">Sign in to your account</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Create a container to match the width of the logo card
    form_container = st.container()
    with form_container:
        # Center the form and constrain its width
        col1, col2, col3 = st.columns([1, 10, 1])
        with col2:
            # Make a clean-looking, modern form
            with st.form("login_form"):
                email = st.text_input("Email", key="login_email", 
                                     placeholder="your@email.com")
                
                password = st.text_input("Password", type="password", key="login_password",
                                       placeholder="••••••••")
                
                # Add spacing before buttons
                st.markdown("<div style='height: 1.5rem'></div>", unsafe_allow_html=True)
                
                # Enhance button styling with columns for better layout
                col1, col2 = st.columns([1, 1])
                with col1:
                    submitted = st.form_submit_button(
                        "Login",
                        use_container_width=True
                    )
                with col2:
                    register_button = st.form_submit_button(
                        "Register", 
                        on_click=lambda: set_page("register"),
                        use_container_width=True
                    )
                
                if submitted:
                    if not email or not password:
                        st.session_state.auth_message = "Please enter both email and password"
                        st.session_state.auth_status = "error"
                        return
                    
                    # Attempt login using our enhanced login_user function
                    try:
                        # First clear session state to prevent data leakage
                        success = login_user(email, password, auth_instance)
                        
                        if success:
                            # Set additional session state variables
                            st.session_state.auth_message = f"Welcome back, {st.session_state.user['fullname']}!"
                            st.session_state.auth_status = "success"
                            st.session_state.page = "main"
                            st.rerun()  # Refresh to show authenticated content
                        else:
                            st.session_state.auth_message = "Invalid email or password"
                            st.session_state.auth_status = "error"
                    except ValueError as e:
                        # This will catch the pending approval error
                        st.session_state.auth_message = str(e)
                        st.session_state.auth_status = "info"
    
    # Improve the auth message styling with matching width
    if st.session_state.auth_message and st.session_state.auth_status:
        message_color = {
            "success": colors["success"],
            "error": colors["danger"],
            "info": colors["info"]
        }.get(st.session_state.auth_status, colors["text"])
        
        icon = {
            "success": "✓",
            "error": "⚠",
            "info": "ℹ"
        }.get(st.session_state.auth_status, "ℹ")
        
        # Use the same column structure to keep consistent width
        _, msg_col, _ = st.columns([1, 10, 1])
        with msg_col:
            st.markdown(f"""
            <div style="text-align: center; width: 100%; margin: 1rem auto; 
                        padding: 0.9rem; background-color: {message_color}15; 
                        border-left: 4px solid {message_color};
                        border-radius: 4px; color: {message_color};">
                <div style="display: flex; align-items: center; justify-content: center;">
                    <span style="margin-right: 8px; font-size: 1.1rem;">{icon}</span>
                    <span>{st.session_state.auth_message}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

def register_form(auth_instance, colors: Dict[str, str]):
    """
    Display registration form
    
    Args:
        auth_instance: UserAuth instance
        colors: Color scheme dictionary
    """
    st.markdown(f"""
    <div style="text-align: center; max-width: 450px; margin: 2rem auto; 
                padding: 2.5rem; background-color: white; border-radius: 12px; 
                box-shadow: 0 8px 24px rgba(0,0,0,0.12);">
        <div style="text-align: center; margin-bottom: 1.5rem;">
            <div style="display: inline-flex; align-items: center; justify-content: center; 
                       width: 80px; height: 80px; border-radius: 16px; 
                       background: linear-gradient(135deg, #0d6efd, #0dcaf0); 
                       margin-bottom: 1rem;">
                <span style="font-size: 2.5rem; color: white; font-weight: bold;">RFP</span>
            </div>
        </div>
        <h1 style="margin-bottom: 1rem; color: {colors['primary']}; font-size: 2.2rem; font-weight: 600;">RFP Analyzer</h1>
        <div style="width: 80px; height: 5px; background: linear-gradient(90deg, {colors['primary']}, {colors['primary']}80); 
                    margin: 0 auto 2rem auto; border-radius: 10px;"></div>
        <p style="margin-bottom: 2rem; font-size: 1.1rem; color: #555;">Create a new account</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Create a container to match the width of the logo card
    form_container = st.container()
    with form_container:
        # Center the form and constrain its width
        col1, col2, col3 = st.columns([1, 10, 1])
        with col2:
            # Display domain restriction notice
            st.markdown("""
            <div style="text-align: center; margin-bottom: 1rem; padding: 0.5rem; 
                        background-color: #f8f9fa; border-radius: 4px; font-size: 0.9rem; color: #555;">
                <strong>Note:</strong> Registration is limited to Aset Partners email addresses only (@asetpartners.com)
            </div>
            """, unsafe_allow_html=True)
            
            with st.form("register_form"):
                email = st.text_input("Email", key="register_email", 
                                     placeholder="yourname@asetpartners.com")
                
                fullname = st.text_input("Full Name", key="register_fullname",
                                        placeholder="John Doe")
                
                company = st.text_input("Company (Optional)", key="register_company",
                                       placeholder="Your Organization")
                
                password = st.text_input("Password", type="password", key="register_password",
                                       placeholder="••••••••")
                
                confirm_password = st.text_input("Confirm Password", type="password", key="register_confirm",
                                               placeholder="••••••••")
                
                # Add spacing before buttons
                st.markdown("<div style='height: 1.5rem'></div>", unsafe_allow_html=True)
                
                col1, col2 = st.columns([1, 1])
                with col1:
                    st.form_submit_button("Back to Login", 
                                         on_click=lambda: set_page("login"),
                                         use_container_width=True)
                with col2:
                    submitted = st.form_submit_button("Register", use_container_width=True)
                
                if submitted:
                    if not email or not fullname or not password or not confirm_password:
                        st.session_state.auth_message = "Please fill in all required fields"
                        st.session_state.auth_status = "error"
                        return
                    
                    if password != confirm_password:
                        st.session_state.auth_message = "Passwords do not match"
                        st.session_state.auth_status = "error"
                        return
                    
                    # Attempt registration
                    try:
                        success = auth_instance.register_user(email, password, fullname, company)
                        if success:
                            st.session_state.auth_message = "Registration successful! Your account is pending admin approval. You will be able to log in once approved."
                            st.session_state.auth_status = "info"
                            st.session_state.page = "login"
                            st.rerun()
                        else:
                            st.session_state.auth_message = "Registration failed"
                            st.session_state.auth_status = "error"
                    except ValueError as e:
                        st.session_state.auth_message = str(e)
                        st.session_state.auth_status = "error"
    
    # Improve the auth message styling with matching width
    if st.session_state.auth_message and st.session_state.auth_status:
        message_color = {
            "success": colors["success"],
            "error": colors["danger"],
            "info": colors["info"]
        }.get(st.session_state.auth_status, colors["text"])
        
        icon = {
            "success": "✓",
            "error": "⚠",
            "info": "ℹ"
        }.get(st.session_state.auth_status, "ℹ")
        
        # Use the same column structure to keep consistent width
        _, msg_col, _ = st.columns([1, 10, 1])
        with msg_col:
            st.markdown(f"""
            <div style="text-align: center; width: 100%; margin: 1rem auto; 
                        padding: 0.9rem; background-color: {message_color}15; 
                        border-left: 4px solid {message_color};
                        border-radius: 4px; color: {message_color};">
                <div style="display: flex; align-items: center; justify-content: center;">
                    <span style="margin-right: 8px; font-size: 1.1rem;">{icon}</span>
                    <span>{st.session_state.auth_message}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

def user_profile(auth_instance, colors: Dict[str, str]):
    """
    Display user profile and account settings
    
    Args:
        auth_instance: UserAuth instance
        colors: Color scheme dictionary
    """
    user = st.session_state.user
    user_fullname = user.get('fullname', 'User')
    user_email = user.get('email', '')
    user_company = user.get('company', '')
    
    # Account info card
    st.markdown("## Account Settings")
    
    # User profile card
    st.markdown(f"""
    <div style="background-color: white; border-radius: 8px; padding: 1.5rem; 
                margin-bottom: 1.5rem; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
        <div style="display: flex; gap: 1rem; align-items: center; margin-bottom: 1.5rem;">
            <div style="width: 60px; height: 60px; border-radius: 50%; background-color: {colors['primary']}; 
                      display: flex; align-items: center; justify-content: center; color: white; font-size: 1.5rem;">
                {user_fullname[0].upper()}
            </div>
            <div>
                <div style="font-size: 1.2rem; font-weight: 600;">{user_fullname}</div>
                <div style="color: {colors['text_muted']};">{user_email}</div>
                <div style="font-size: 0.9rem; margin-top: 0.25rem;">{user_company}</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Admin Section - Only show for admin users
    if user.get('role') == 'admin':
        with st.expander("Admin: User Approval", expanded=True):
            st.markdown("##### Pending User Approvals")
            
            # Get list of pending users
            pending_users = auth_instance.get_pending_users(user.get('user_id'))
            
            if not pending_users:
                st.info("No pending users to approve.")
            else:
                # Display each pending user
                for pending_user in pending_users:
                    col1, col2, col3 = st.columns([3, 1, 1])
                    with col1:
                        st.markdown(f"""
                        <div>
                            <strong>{pending_user.get('fullname')}</strong><br>
                            {pending_user.get('email')}<br>
                            <small>Company: {pending_user.get('company') or 'Not specified'}</small><br>
                            <small>Registered: {pending_user.get('registration_date').strftime('%Y-%m-%d %H:%M:%S') if pending_user.get('registration_date') else 'Unknown'}</small>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    with col2:
                        # Approve button
                        if st.button("Approve", key=f"approve_{pending_user.get('_id')}"):
                            if auth_instance.approve_user(user.get('user_id'), pending_user.get('_id'), approved=True):
                                st.success(f"User {pending_user.get('email')} approved.")
                                st.rerun()
                            else:
                                st.error("Failed to approve user.")
                    
                    with col3:
                        # Reject button
                        if st.button("Reject", key=f"reject_{pending_user.get('_id')}"):
                            if auth_instance.approve_user(user.get('user_id'), pending_user.get('_id'), approved=False):
                                st.warning(f"User {pending_user.get('email')} rejected.")
                                st.rerun()
                            else:
                                st.error("Failed to reject user.")
                    
                    st.markdown("<hr>", unsafe_allow_html=True)
    
    # Password change section
    with st.expander("Change Password"):
        with st.form("change_password_form"):
            current_password = st.text_input("Current Password", type="password")
            new_password = st.text_input("New Password", type="password")
            confirm_password = st.text_input("Confirm New Password", type="password")
            
            submitted = st.form_submit_button("Update Password")
            
            if submitted:
                if not current_password or not new_password or not confirm_password:
                    st.error("Please fill in all fields")
                    return
                
                if new_password != confirm_password:
                    st.error("New passwords do not match")
                    return
                
                success = auth_instance.change_password(
                    user['user_id'], current_password, new_password
                )
                
                if success:
                    st.success("Password updated successfully. Please log in again.")
                    # Log out
                    logout(auth_instance)
                    st.rerun()
                else:
                    st.error("Failed to update password. Check your current password.")
    
    # Sign Out button at the bottom of the profile page
    if st.button("Sign Out", key="profile_sign_out"):
        logout(auth_instance)
        st.rerun()
    
    # Back button
    if st.button("Back to Application", key="back_to_app"):
        st.session_state.page = "main"
        st.rerun()

def logout(auth_instance):
    """Log out the current user"""
    if auth_instance and st.session_state.auth_token:
        auth_instance.logout(st.session_state.auth_token)
    
    # Use our more thorough logout function instead
    logout_user()
    
    # These will be set by logout_user, but we set them again just in case
    st.session_state.user = None
    st.session_state.auth_token = None
    st.session_state.auth_message = "You have been logged out"
    st.session_state.auth_status = "info"
    st.session_state.page = "login"

def set_page(page_name: str):
    """Set the current auth page"""
    st.session_state.page = page_name
    # Clear auth message when changing pages
    st.session_state.auth_message = None
    st.session_state.auth_status = None

def check_auth(auth_instance) -> bool:
    """
    Check if user is authenticated
    
    Args:
        auth_instance: UserAuth instance
        
    Returns:
        bool: True if authenticated, False otherwise
    """
    # If we already have a validated user in session state, return True
    if st.session_state.user:
        return True
    
    # If we have a token but no validated user, validate the token
    if st.session_state.auth_token:
        user_info = auth_instance.validate_session(st.session_state.auth_token)
        if user_info:
            st.session_state.user = user_info
            return True
        else:
            # Token is invalid, clear it
            st.session_state.auth_token = None
    
    # Not authenticated
    return False

def require_auth(auth_instance, colors: Dict[str, str], page_content_function: Callable):
    """
    Require authentication to access content
    
    Args:
        auth_instance: UserAuth instance
        colors: Color scheme dictionary
        page_content_function: Function to run if authenticated
    """
    # Initialize session state
    init_auth_session_state()
    
    # Store auth instance in session state for use in callbacks
    st.session_state.user_auth = auth_instance
    
    # Check if authenticated
    if check_auth(auth_instance):
        # User is authenticated
        if st.session_state.page == "profile":
            # Render the user profile page
            user_profile(auth_instance, colors)
        elif st.session_state.page == "admin":
            # Add a simple user display in the top right
            if st.session_state.user:
                user_fullname = st.session_state.user.get('fullname', 'User')
                user_initial = user_fullname[0].upper()
                
                # Create header with user info
                cols = st.columns([15, 3])
                with cols[1]:
                    user_menu = st.container()
                    user_menu_col1, user_menu_col2 = st.columns([1, 3])
                    with user_menu_col1:
                        if st.button(f"{user_initial}", key="user_menu_button", 
                                    help="Account Settings",
                                    use_container_width=True):
                            st.session_state.page = "profile"
                            st.rerun()
                    with user_menu_col2:
                        if st.button("Sign Out", key="sign_out_button", use_container_width=True):
                            logout(auth_instance)
                            st.rerun()
                            
            # Render the main application content (will show admin panel based on session state)
            page_content_function()
        else:
            # On main page or others
            if st.session_state.page != "main":
                st.session_state.page = "main"
            
            # Add a simple user display in the top right
            if st.session_state.user:
                user_fullname = st.session_state.user.get('fullname', 'User')
                user_initial = user_fullname[0].upper()
                
                # Create header with user info
                cols = st.columns([15, 3])
                with cols[1]:
                    user_menu = st.container()
                    user_menu_col1, user_menu_col2 = st.columns([1, 3])
                    with user_menu_col1:
                        if st.button(f"{user_initial}", key="user_menu_button", 
                                    help="Account Settings",
                                    use_container_width=True):
                            st.session_state.page = "profile"
                            st.rerun()
                    with user_menu_col2:
                        if st.button("Sign Out", key="sign_out_button", use_container_width=True):
                            logout(auth_instance)
                            st.rerun()
            
            # Render the main application content
            page_content_function()
    else:
        # User is not authenticated, show login or register form
        if st.session_state.page == "register":
            register_form(auth_instance, colors)
        else:  # Default to login
            login_form(auth_instance, colors)

def logout_user():
    """Log out the current user by clearing session state"""
    # Clear ALL session state to prevent data leakage between users
    # Keep only a few system keys 
    keys_to_keep = ['page', 'theme']
    
    # Store keys we want to keep
    preserved_values = {key: st.session_state[key] for key in keys_to_keep if key in st.session_state}
    
    # Clear entire session state
    for key in list(st.session_state.keys()):
        if key not in keys_to_keep:  # Don't clear these yet
            del st.session_state[key]
    
    # Log the logout
    logging.info("User logged out, session cleared")
    
    # Restore keys we wanted to keep
    for key, value in preserved_values.items():
        st.session_state[key] = value
    
    # Reset the page to home
    st.session_state.page = None
    
    # Set a logout message
    st.session_state.logout_message = "You have been logged out successfully."
    
    # Perform a rerun to refresh the page
    st.rerun()

def login_user(email, password, auth_instance):
    """
    Attempt to log in a user with email and password
    
    Args:
        email: User email
        password: User password
        auth_instance: UserAuth instance for authentication
        
    Returns:
        bool: True if login successful, False otherwise
    """
    # Clear any existing user data to prevent session mixing
    # Lists of prefixes for session state keys that should be cleared
    prefixes_to_clear = [
        'user_', 'doc_', 'analysis_', 'chat_', 'active_', 
        'current_', 'selected_', 'rfp_', 'document_', 
        'upload_', 'stats_', 'file_', 'requirements_',
        'tasks_', 'timeline_'
    ]
    
    # Clear all matching keys
    for key in list(st.session_state.keys()):
        if any(key.startswith(prefix) for prefix in prefixes_to_clear):
            del st.session_state[key]
            
    # Clear specific known keys
    specific_keys = [
        'document_id', 'uploaded_document', 'analysis_results', 
        'requirements', 'tasks', 'key_dates', 'chat_history',
        'current_document', 'documents', 'rfp_data'
    ]
    
    for key in specific_keys:
        if key in st.session_state:
            del st.session_state[key]
            
    # Attempt to authenticate
    token = auth_instance.login(email, password)
    
    if token:
        # Set session state variables for the logged in user
        st.session_state.auth_token = token
        user_info = auth_instance.validate_session(token)
        if user_info:
            st.session_state.user = user_info
            st.session_state.logged_in = True
            st.session_state.login_time = datetime.utcnow()
            
            # Reset to a clean state
            st.session_state.page = None
            
            # Log the login
            logging.info(f"User logged in: {email}")
            
            return True
    
    # If we got here, login failed
    logging.warning(f"Failed login attempt for: {email}")
    return False