#!/usr/bin/env python3
import streamlit as st
import logging
from typing import Dict, Any, Optional, Callable
import os
import json

# Configure logging
logger = logging.getLogger(__name__)

def init_auth_session_state():
    """Initialize authentication-related session state variables"""
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
            st.experimental_rerun()

def login_form(auth_instance, colors: Dict[str, str]):
    """
    Display login form
    
    Args:
        auth_instance: UserAuth instance
        colors: Color scheme dictionary
    """
    st.markdown(f"""
    <div style="text-align: center; max-width: 400px; margin: 0 auto; 
                padding: 2rem; background-color: white; border-radius: 8px; 
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
        <h1 style="margin-bottom: 1.5rem; color: {colors['primary']};">RFP Analyzer</h1>
        <p style="margin-bottom: 2rem;">Sign in to your account</p>
    </div>
    """, unsafe_allow_html=True)
    
    with st.form("login_form"):
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")
        
        col1, col2 = st.columns([1, 1])
        with col1:
            st.form_submit_button("Register", on_click=lambda: set_page("register"))
        with col2:
            submitted = st.form_submit_button("Login")
        
        if submitted:
            if not email or not password:
                st.session_state.auth_message = "Please enter both email and password"
                st.session_state.auth_status = "error"
                return
            
            # Attempt login
            token = auth_instance.login(email, password)
            if token:
                st.session_state.auth_token = token
                user_info = auth_instance.validate_session(token)
                if user_info:
                    st.session_state.user = user_info
                    st.session_state.auth_message = f"Welcome back, {user_info['fullname']}!"
                    st.session_state.auth_status = "success"
                    st.session_state.page = "main"
                    st.rerun()  # Refresh to show authenticated content
                else:
                    st.session_state.auth_message = "Authentication error"
                    st.session_state.auth_status = "error"
            else:
                st.session_state.auth_message = "Invalid email or password"
                st.session_state.auth_status = "error"
    
    # Display any auth messages
    if st.session_state.auth_message and st.session_state.auth_status:
        message_color = {
            "success": colors["success"],
            "error": colors["danger"],
            "info": colors["info"]
        }.get(st.session_state.auth_status, colors["text"])
        
        st.markdown(f"""
        <div style="text-align: center; max-width: 400px; margin: 1rem auto; 
                    padding: 0.75rem; background-color: {message_color}20; 
                    border-radius: 4px; color: {message_color};">
            {st.session_state.auth_message}
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
    <div style="text-align: center; max-width: 400px; margin: 0 auto; 
                padding: 2rem; background-color: white; border-radius: 8px; 
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
        <h1 style="margin-bottom: 1.5rem; color: {colors['primary']};">RFP Analyzer</h1>
        <p style="margin-bottom: 2rem;">Create a new account</p>
    </div>
    """, unsafe_allow_html=True)
    
    with st.form("register_form"):
        email = st.text_input("Email", key="register_email")
        fullname = st.text_input("Full Name", key="register_fullname")
        company = st.text_input("Company (Optional)", key="register_company")
        password = st.text_input("Password", type="password", key="register_password")
        confirm_password = st.text_input("Confirm Password", type="password", key="register_confirm")
        
        col1, col2 = st.columns([1, 1])
        with col1:
            st.form_submit_button("Back to Login", on_click=lambda: set_page("login"))
        with col2:
            submitted = st.form_submit_button("Register")
        
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
                    st.session_state.auth_message = "Registration successful! You can now log in."
                    st.session_state.auth_status = "success"
                    st.session_state.page = "login"
                    st.rerun()
                else:
                    st.session_state.auth_message = "Registration failed"
                    st.session_state.auth_status = "error"
            except ValueError as e:
                st.session_state.auth_message = str(e)
                st.session_state.auth_status = "error"
    
    # Display any auth messages
    if st.session_state.auth_message and st.session_state.auth_status:
        message_color = {
            "success": colors["success"],
            "error": colors["danger"],
            "info": colors["info"]
        }.get(st.session_state.auth_status, colors["text"])
        
        st.markdown(f"""
        <div style="text-align: center; max-width: 400px; margin: 1rem auto; 
                    padding: 0.75rem; background-color: {message_color}20; 
                    border-radius: 4px; color: {message_color};">
            {st.session_state.auth_message}
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
        else:
            # Set page to main if not on profile
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