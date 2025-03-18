#!/usr/bin/env python3
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import logging
from typing import Dict, Any, List, Optional
from document_storage import DocumentStorage
from auth import UserAuth
from bson.objectid import ObjectId
import time

# Configure logging
logger = logging.getLogger(__name__)

def render_admin_panel(auth_instance: UserAuth, document_storage: DocumentStorage, colors: Dict[str, str]):
    """
    Render the admin panel with tabs for different admin functions
    
    Args:
        auth_instance: UserAuth instance
        document_storage: DocumentStorage instance
        colors: Color scheme dictionary
    """
    # Verify user is an admin
    if not st.session_state.user or st.session_state.user.get('role') != 'admin':
        st.error("You do not have permission to access the admin panel.")
        return
    
    # Admin panel header
    st.title("📊 Admin Panel")
    
    # Add a button to return to the main app
    if st.button("← Return to Main App", key="return_to_main_app", type="primary"):
        # Set the page to None or 'home' to return to the main view
        st.session_state.page = None
        st.rerun()
    
    st.markdown("Manage users, view system statistics, and browse all documents in the organization.")
    
    # Create tabs for different admin functions
    dashboard_tab, user_mgmt_tab, doc_browser_tab = st.tabs([
        "🏠 Dashboard", 
        "👥 User Management", 
        "📄 Document Browser"
    ])
    
    # Render each tab's content
    with dashboard_tab:
        render_admin_dashboard(auth_instance, document_storage)
    
    with user_mgmt_tab:
        render_user_management(auth_instance, colors)
    
    with doc_browser_tab:
        render_document_browser(document_storage, auth_instance)

def render_admin_dashboard(auth_instance: UserAuth, document_storage: DocumentStorage):
    """
    Render the admin dashboard with summary statistics and charts
    
    Args:
        auth_instance: UserAuth instance
        document_storage: DocumentStorage instance
    """
    st.header("System Dashboard")
    
    # Get statistics
    stats = get_system_stats(auth_instance, document_storage)
    
    # Display an info box about data
    with st.expander("ℹ️ About Dashboard Data", expanded=False):
        st.markdown("""
        **Dashboard Data Source Information**
        
        This dashboard displays real data from your application's database when available:
        
        - User counts, document counts, and approvals are actual numbers from the database
        - Activity data shows real events like logins, document uploads, and approvals
        - In case of limited data, sample values may be shown to demonstrate the UI
        
        As your application usage grows, all statistics will reflect actual usage patterns.
        """)
        
        # Add warning about system date if needed
        if datetime.now().year >= 2025:
            st.warning("""
            ⚠️ **Note**: Your system clock appears to be set to 2025 or later. 
            Dates shown in the dashboard reflect your system's current date and time. 
            If this is incorrect, you may want to adjust your system clock.
            """)
    
    # Display summary cards in columns
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="Total Users", 
            value=stats['user_count'],
            delta=f"+{stats['new_users_30d']} in 30d" if stats['new_users_30d'] > 0 else None
        )
    
    with col2:
        st.metric(
            label="Total Documents", 
            value=stats['document_count'],
            delta=f"+{stats['new_docs_30d']} in 30d" if stats['new_docs_30d'] > 0 else None
        )
    
    with col3:
        st.metric(
            label="Pending Approvals", 
            value=stats['pending_users_count']
        )
    
    with col4:
        st.metric(
            label="Active Users (7d)", 
            value=stats['active_users_7d']
        )
    
    # Create two columns for charts
    chart_col1, chart_col2 = st.columns(2)
    
    with chart_col1:
        st.subheader("User Registration Trend")
        
        # Convert to DataFrame if it's not already
        if not isinstance(stats['user_registration_trend'], pd.DataFrame):
            user_reg_df = pd.DataFrame(stats['user_registration_trend'])
        else:
            user_reg_df = stats['user_registration_trend']
            
        fig = px.line(
            user_reg_df, 
            x='date', 
            y='count',
            labels={'date': 'Date', 'count': 'New Users'},
            title="New User Registrations (Last 30 Days)"
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with chart_col2:
        st.subheader("Document Upload Trend")
        
        # Convert to DataFrame if it's not already
        if not isinstance(stats['document_upload_trend'], pd.DataFrame):
            doc_upload_df = pd.DataFrame(stats['document_upload_trend'])
        else:
            doc_upload_df = stats['document_upload_trend']
            
        fig = px.line(
            doc_upload_df, 
            x='date', 
            y='count',
            labels={'date': 'Date', 'count': 'New Documents'},
            title="Document Uploads (Last 30 Days)"
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # Recent activity
    st.subheader("Recent Activity")
    
    # Use tabs for different activity types
    activity_tabs = st.tabs(["User Activity", "Document Activity"])
    
    with activity_tabs[0]:
        if 'recent_user_activity' in stats and stats['recent_user_activity']:
            if stats.get('user_activity_is_sample', False):
                st.warning("⚠️ Showing sample user activity data - No real activity recorded yet")
            
            activity_df = pd.DataFrame(stats['recent_user_activity'])
            st.dataframe(
                activity_df,
                hide_index=True,
                column_config={
                    "timestamp": st.column_config.DatetimeColumn("Time", format="MMM DD, YYYY, hh:mm a"),
                    "user": "User",
                    "activity": "Activity",
                    "details": "Details"
                },
                use_container_width=True
            )
        else:
            st.info("No recent user activity found.")
    
    with activity_tabs[1]:
        if 'recent_document_activity' in stats and stats['recent_document_activity']:
            if stats.get('document_activity_is_sample', False):
                st.warning("⚠️ Showing sample document activity data - No real activity recorded yet")
            
            activity_df = pd.DataFrame(stats['recent_document_activity'])
            st.dataframe(
                activity_df,
                hide_index=True, 
                column_config={
                    "timestamp": st.column_config.DatetimeColumn("Time", format="MMM DD, YYYY, hh:mm a"),
                    "user": "User",
                    "document": "Document",
                    "activity": "Activity"
                },
                use_container_width=True
            )
        else:
            st.info("No recent document activity found.")

def get_system_stats(auth_instance: UserAuth, document_storage: DocumentStorage) -> Dict[str, Any]:
    """
    Get system statistics for the admin dashboard
    
    Args:
        auth_instance: UserAuth instance
        document_storage: DocumentStorage instance
        
    Returns:
        Dictionary containing system statistics
    """
    admin_id = st.session_state.user.get('user_id')
    
    # Get statistics from database
    stats = auth_instance.get_admin_statistics(admin_id) or {}
    
    # Get document statistics
    doc_stats = document_storage.get_admin_document_statistics() or {}
    
    # Combine statistics
    stats.update(doc_stats)
    
    # Ensure all required keys exist with defaults
    if 'user_count' not in stats:
        stats['user_count'] = 0
    if 'document_count' not in stats:
        stats['document_count'] = 0
    if 'pending_users_count' not in stats:
        stats['pending_users_count'] = 0
    if 'new_users_30d' not in stats:
        stats['new_users_30d'] = 0
    if 'new_docs_30d' not in stats:
        stats['new_docs_30d'] = 0
    if 'active_users_7d' not in stats:
        stats['active_users_7d'] = 0
    
    # Generate trends if not available
    if 'user_registration_trend' not in stats:
        # This is sample data - will be replaced by actual database methods
        today = datetime.now()
        dates = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(30)]
        stats['user_registration_trend'] = pd.DataFrame({
            'date': dates,
            'count': [int(i % 5 + i % 3) for i in range(30)]
        })
    
    if 'document_upload_trend' not in stats:
        today = datetime.now()
        dates = [(today - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(30)]
        stats['document_upload_trend'] = pd.DataFrame({
            'date': dates,
            'count': [int(i % 4 + i % 7) for i in range(30)]
        })
    
    # Ensure activity data exists
    if 'recent_user_activity' not in stats or not stats['recent_user_activity']:
        # Get real login sessions from database if possible
        try:
            # This is a fallback if real data isn't available
            today = datetime.now()
            # Ensure we're using the server's current time, not a hardcoded date
            sample_activities = [
                {"timestamp": today - timedelta(hours=i), 
                 "user": f"user{i}@example.com", 
                 "activity": "Login" if i % 3 == 0 else "Document Upload" if i % 3 == 1 else "Profile Update",
                 "details": f"Sample activity {i} - This is demo data"}
                for i in range(1, 11)
            ]
            stats['recent_user_activity'] = sample_activities
            # Add a flag to indicate this is sample data
            stats['user_activity_is_sample'] = True
        except Exception as e:
            logger.error(f"Error generating user activity: {str(e)}")
            stats['recent_user_activity'] = []
            stats['user_activity_is_sample'] = True
    else:
        stats['user_activity_is_sample'] = False
    
    if 'recent_document_activity' not in stats or not stats['recent_document_activity']:
        # Try to get real document activity
        try:
            # This is a fallback if real data isn't available
            today = datetime.now()
            # Ensure we're using the server's current time, not a hardcoded date
            sample_activities = [
                {"timestamp": today - timedelta(hours=i*2), 
                 "user": f"user{i}@example.com", 
                 "document": f"Sample_Document_{i}.pdf",
                 "activity": "Upload" if i % 2 == 0 else "Analysis"}
                for i in range(1, 11)
            ]
            stats['recent_document_activity'] = sample_activities
            # Add a flag to indicate this is sample data
            stats['document_activity_is_sample'] = True
        except Exception as e:
            logger.error(f"Error generating document activity: {str(e)}")
            stats['recent_document_activity'] = []
            stats['document_activity_is_sample'] = True
    else:
        stats['document_activity_is_sample'] = False
    
    return stats

def render_user_management(auth_instance: UserAuth, colors: Dict[str, str]):
    """
    Render the user management interface with search, filter, and editing capabilities
    
    Args:
        auth_instance: UserAuth instance
        colors: Color scheme dictionary
    """
    st.header("User Management")
    
    # User management tabs
    user_tabs = st.tabs(["All Users", "Pending Approvals", "Add User"])
    
    admin_id = st.session_state.user.get('user_id')
    
    # All Users tab
    with user_tabs[0]:
        st.subheader("All Users")
        
        # Search and filter options
        col1, col2, col3 = st.columns([2, 2, 1])
        with col1:
            search_query = st.text_input("Search by name or email:", placeholder="Enter search terms...")
        with col2:
            filter_role = st.selectbox("Filter by role:", ["All", "Admin", "User", "Inactive"])
        with col3:
            refresh_button = st.button("Refresh", use_container_width=True, key="all_users_refresh")
        
        # Get all users
        all_users = auth_instance.get_all_users(admin_id, search_query, filter_role.lower() if filter_role != "All" else None)
        
        if all_users:
            # Convert to dataframe for display
            users_df = pd.DataFrame(all_users)
            
            # Rename columns for better display
            users_df = users_df.rename(columns={
                "_id": "user_id",
                "created_at": "joined",
                "last_login": "last_active"
            })
            
            # Add action buttons to dataframe
            st.dataframe(
                users_df,
                hide_index=True,
                column_config={
                    "user_id": None,  # Hide ID column
                    "joined": st.column_config.DatetimeColumn("Joined", format="MMM DD, YYYY"),
                    "last_active": st.column_config.DatetimeColumn("Last Active", format="MMM DD, YYYY, hh:mm a"),
                    "fullname": "Full Name",
                    "email": "Email",
                    "role": "Role",
                    "company": "Company",
                    "active": st.column_config.CheckboxColumn("Active")
                },
                use_container_width=True
            )
            
            # User details and actions
            st.subheader("User Actions")
            
            # Select user for actions
            selected_user_email = st.selectbox("Select user:", [user["email"] for user in all_users])
            selected_user = next((user for user in all_users if user["email"] == selected_user_email), None)
            
            if selected_user:
                user_id = selected_user["_id"]
                
                # Display selected user details in columns
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown(f"**Name:** {selected_user['fullname']}")
                    st.markdown(f"**Email:** {selected_user['email']}")
                    st.markdown(f"**Role:** {selected_user.get('role', 'user')}")
                
                with col2:
                    st.markdown(f"**Company:** {selected_user.get('company', 'N/A')}")
                    st.markdown(f"**Joined:** {selected_user.get('joined', 'N/A')}")
                    st.markdown(f"**Status:** {'Active' if selected_user.get('active', False) else 'Inactive'}")
                
                # Actions for selected user
                st.markdown("---")
                
                # Move all controls into a more consistent layout
                # First row for inputs/selections
                input_col1, input_col2 = st.columns(2)
                
                with input_col1:
                    # Change role
                    new_role = st.selectbox("Change role:", ["user", "admin"], 
                                      index=0 if selected_user.get('role') != 'admin' else 1)
                
                # Second row for action buttons with consistent spacing
                button_col1, button_col2, button_col3 = st.columns(3)
                
                with button_col1:
                    if new_role != selected_user.get('role', 'user'):
                        update_role_btn = st.button("Update Role", use_container_width=True, key="update_role_btn")
                    else:
                        # Add a placeholder button that's disabled when role hasn't changed
                        st.button("Update Role", use_container_width=True, key="update_role_btn", disabled=True)
                
                with button_col2:
                    # Toggle active status
                    is_active = selected_user.get('active', False)
                    status_action = "Deactivate" if is_active else "Activate"
                    toggle_status_btn = st.button(status_action, use_container_width=True, key="toggle_status_btn")
                
                with button_col3:
                    # Reset password
                    reset_pwd_btn = st.button("Reset Password", use_container_width=True, key="reset_pwd_btn")
                
                # Handle button actions below
                if 'update_role_btn' in st.session_state and st.session_state.update_role_btn and new_role != selected_user.get('role', 'user'):
                    success = auth_instance.update_user_role(admin_id, user_id, new_role)
                    if success:
                        st.success(f"Role updated to {new_role}")
                        st.rerun()
                    else:
                        st.error("Failed to update role")
                
                if 'toggle_status_btn' in st.session_state and st.session_state.toggle_status_btn:
                    success = auth_instance.update_user_status(admin_id, user_id, not is_active)
                    if success:
                        st.success(f"User {status_action.lower()}d successfully")
                        st.rerun()
                    else:
                        st.error(f"Failed to {status_action.lower()} user")
                
                if 'reset_pwd_btn' in st.session_state and st.session_state.reset_pwd_btn:
                    with st.expander("Confirm Password Reset", expanded=True):
                        st.warning("This will generate a temporary password for the user.")
                        if st.button("Yes, Reset Password", key="confirm_reset"):
                            new_password = auth_instance.admin_reset_password(admin_id, user_id)
                            if new_password:
                                st.success("Password reset successful!")
                                st.code(new_password, language="text")
                                st.info("Please securely share this temporary password with the user.")
                            else:
                                st.error("Failed to reset password")
        else:
            st.info("No users found.")
    
    # Pending Approvals tab
    with user_tabs[1]:
        st.subheader("Users Pending Approval")
        
        # Get pending users
        pending_users = auth_instance.get_pending_users(admin_id)
        
        if pending_users:
            # Convert to dataframe for display
            pending_df = pd.DataFrame(pending_users)
            
            # Rename columns for better display
            pending_df = pending_df.rename(columns={
                "_id": "user_id",
                "created_at": "requested"
            })
            
            # Display pending users
            st.dataframe(
                pending_df,
                hide_index=True,
                column_config={
                    "user_id": None,  # Hide ID column
                    "requested": st.column_config.DatetimeColumn("Requested", format="MMM DD, YYYY, hh:mm a"),
                    "fullname": "Full Name",
                    "email": "Email",
                    "company": "Company"
                },
                use_container_width=True
            )
            
            # Process approvals
            st.subheader("Approve or Reject Users")
            
            # Select pending user
            selected_pending_email = st.selectbox("Select user to process:", 
                                               [user["email"] for user in pending_users],
                                               key="pending_select")
            
            selected_pending = next((user for user in pending_users if user["email"] == selected_pending_email), None)
            
            if selected_pending:
                pending_id = selected_pending["_id"]
                
                # Display pending user details
                st.markdown(f"**Name:** {selected_pending['fullname']}")
                st.markdown(f"**Email:** {selected_pending['email']}")
                st.markdown(f"**Company:** {selected_pending.get('company', 'N/A')}")
                
                # Approve/reject buttons
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Approve User", use_container_width=True, type="primary", key="approve_user_btn"):
                        success = auth_instance.approve_user(admin_id, pending_id, True)
                        if success:
                            st.success(f"User {selected_pending['email']} approved!")
                            st.rerun()
                        else:
                            st.error("Failed to approve user")
                
                with col2:
                    if st.button("Reject User", use_container_width=True, key="reject_user_btn"):
                        success = auth_instance.approve_user(admin_id, pending_id, False)
                        if success:
                            st.success(f"User {selected_pending['email']} rejected!")
                            st.rerun()
                        else:
                            st.error("Failed to reject user")
        else:
            st.info("No pending users to approve.")
    
    # Add User tab
    with user_tabs[2]:
        st.subheader("Add New User")
        
        # Form for adding new user
        with st.form("add_user_form"):
            new_email = st.text_input("Email Address*")
            new_fullname = st.text_input("Full Name*")
            new_company = st.text_input("Company")
            new_role = st.selectbox("Role", ["user", "admin"])
            new_password = st.text_input("Initial Password*", type="password")
            confirm_password = st.text_input("Confirm Password*", type="password")
            
            submitted = st.form_submit_button("Create User")
            
            if submitted:
                if not new_email or not new_fullname or not new_password:
                    st.error("Email, full name, and password are required")
                elif new_password != confirm_password:
                    st.error("Passwords do not match")
                else:
                    success = auth_instance.admin_create_user(
                        admin_id, 
                        new_email, 
                        new_password, 
                        new_fullname, 
                        new_company, 
                        new_role
                    )
                    if success:
                        st.success(f"User {new_email} created successfully!")
                    else:
                        st.error("Failed to create user. Email might be already registered.")

def render_document_browser(document_storage: DocumentStorage, auth_instance: UserAuth):
    """
    Render the organization-wide document browser with filtering and admin actions
    
    Args:
        document_storage: DocumentStorage instance
        auth_instance: UserAuth instance
    """
    st.header("Organization Document Browser")
    
    admin_id = st.session_state.user.get('user_id')
    
    # Filters in columns
    filter_col1, filter_col2, filter_col3, filter_col4 = st.columns([2, 2, 2, 1])
    
    with filter_col1:
        # Get all users for filtering
        all_users = auth_instance.get_all_users(admin_id)
        user_options = [{"_id": "all", "fullname": "All Users", "email": ""}]
        user_options.extend(all_users)
        
        selected_user = st.selectbox(
            "Filter by user:",
            options=[f"{user['fullname']} ({user['email']})" if user['_id'] != 'all' else "All Users" 
                    for user in user_options],
            index=0
        )
        
        # Extract user_id from selection
        selected_user_id = "all"
        if selected_user != "All Users":
            selected_email = selected_user.split('(')[-1].split(')')[0]
            selected_user_obj = next((u for u in all_users if u['email'] == selected_email), None)
            if selected_user_obj:
                selected_user_id = selected_user_obj['_id']
    
    with filter_col2:
        date_filter = st.selectbox(
            "Filter by date:",
            options=["All Time", "Today", "Last 7 Days", "Last 30 Days", 
                     "Last 90 Days", "This Year"]
        )
    
    with filter_col3:
        status_filter = st.selectbox(
            "Filter by status:",
            options=["All", "Analyzed", "Pending Analysis", "Error"]
        )
    
    with filter_col4:
        refresh = st.button("Refresh", use_container_width=True, key="doc_browser_refresh")
    
    # Get documents based on filters
    documents = document_storage.get_all_documents(
        admin_id=admin_id,
        user_id=selected_user_id if selected_user_id != "all" else None,
        date_filter=date_filter,
        status_filter=status_filter if status_filter != "All" else None
    )
    
    # Debug information
    logger.info(f"Document query params: user_id={selected_user_id if selected_user_id != 'all' else None}, date_filter={date_filter}, status_filter={status_filter if status_filter != 'All' else None}")
    logger.info(f"Document query returned {len(documents) if documents else 0} documents")

    if documents:
        # Convert to dataframe for display
        docs_df = pd.DataFrame(documents)
        
        # Rename and format columns - fix duplicate column problem
        if 'uploaded_by' in docs_df.columns and 'user_email' in docs_df.columns:
            # If both columns exist, drop uploaded_by to avoid duplication
            docs_df = docs_df.drop(columns=['uploaded_by'])
        
        # Now rename columns
        docs_df = docs_df.rename(columns={
            # Don't rename _id to document_id since it's already an alias set in get_all_documents
            "uploaded_at": "upload_date",
            "user_email": "uploaded_by",
        })
        
        # Display documents
        st.dataframe(
            docs_df,
            hide_index=True,
            column_config={
                "document_id": None,  # Hide ID column
                "_id": None,  # Also hide the original _id column
                "user_id": None,  # Hide user_id
                "s3_bucket": None,  # Hide S3 bucket
                "s3_key": None,  # Hide S3 key
                "metadata": None,  # Hide metadata object
                "processing_history": None,  # Hide processing history
                "upload_date": st.column_config.DatetimeColumn("Uploaded", format="MMM DD, YYYY, hh:mm a"),
                "original_filename": "Filename",
                "uploaded_by": "User",
                "file_size": "Size",
                "status": st.column_config.TextColumn(
                    "Status",
                    help="Current processing status of the document",
                    width="medium"
                )
            },
            use_container_width=True
        )
        
        # Document actions
        st.subheader("Document Actions")
        
        # Select document for actions
        selected_doc_filename = st.selectbox(
            "Select document:", 
            [f"{doc['original_filename']} (by {doc.get('user_email', 'Unknown')})" for doc in documents]
        )
        
        selected_doc = next((
            doc for doc in documents 
            if f"{doc['original_filename']} (by {doc.get('user_email', 'Unknown')})" == selected_doc_filename
        ), None)
        
        if selected_doc:
            # Use document_id if available, otherwise fall back to _id
            doc_id = selected_doc.get("document_id", selected_doc.get("_id"))
            
            # Display document details
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown(f"**Filename:** {selected_doc['original_filename']}")
                st.markdown(f"**Owner:** {selected_doc.get('user_email', 'Unknown')}")
                st.markdown(f"**Upload Date:** {selected_doc.get('upload_date', 'Unknown')}")
            
            with col2:
                st.markdown(f"**Size:** {selected_doc.get('file_size', 'Unknown')}")
                st.markdown(f"**Status:** {selected_doc.get('status', 'Unknown')}")
                if "analysis_date" in selected_doc:
                    st.markdown(f"**Analysis Date:** {selected_doc['analysis_date']}")
            
            # Actions for selected document
            st.markdown("---")
            
            # First row for owner selection
            input_col1, input_col2 = st.columns(2)
            
            with input_col1:
                # Reassign document to another user - moved from the third column
                all_active_users = [u for u in all_users if u.get('active', False) and u['_id'] != selected_doc.get('user_id')]
                
                if all_active_users:
                    new_owner = st.selectbox(
                        "Select new owner:",
                        options=[f"{user['fullname']} ({user['email']})" for user in all_active_users]
                    )
            
            # Second row for action buttons with consistent spacing
            button_col1, button_col2, button_col3 = st.columns(3)
            
            with button_col1:
                # Download document
                download_btn = st.button("Download Document", use_container_width=True, key="download_doc_btn")
            
            with button_col2:
                # Delete document - using session state for confirmation
                if "confirm_delete_doc" not in st.session_state:
                    st.session_state.confirm_delete_doc = False
                
                if st.session_state.confirm_delete_doc:
                    delete_btn = st.button("Confirm Delete", use_container_width=True, key="confirm_delete_btn", type="primary")
                else:
                    delete_btn = st.button("Delete Document", use_container_width=True, key="delete_doc_btn")
            
            with button_col3:
                # Reassign document button
                if all_active_users:
                    # Extract user_id from selection
                    new_owner_email = new_owner.split('(')[-1].split(')')[0]
                    new_owner_obj = next((u for u in all_active_users if u['email'] == new_owner_email), None)
                    
                    reassign_btn = st.button("Reassign Document", use_container_width=True, key="reassign_doc_btn")
                else:
                    st.info("No other active users to reassign to")
            
            # Handle button actions below
            # Download action
            if download_btn:
                try:
                    presigned_url = document_storage.generate_presigned_url(doc_id, admin_id)
                    if presigned_url:
                        st.success("Download link generated!")
                        st.markdown(f"[Click here to download]({presigned_url})")
                    else:
                        st.error("Failed to generate download link")
                except Exception as e:
                    st.error(f"Error generating download link: {str(e)}")
                    logger.error(f"Download error: {str(e)}", exc_info=True)
            
            # Delete action
            if delete_btn and not st.session_state.confirm_delete_doc:
                # First click - show confirmation
                st.session_state.confirm_delete_doc = True
                st.warning("⚠️ This action cannot be undone. Click 'Confirm Delete' to permanently delete this document.")
                st.rerun()
            
            if delete_btn and st.session_state.confirm_delete_doc:
                # Confirmed delete
                try:
                    success = document_storage.delete_document(doc_id, admin_id)
                    if success:
                        st.session_state.confirm_delete_doc = False
                        st.success("Document deleted successfully!")
                        time.sleep(1)  # Brief pause for feedback
                        st.rerun()
                    else:
                        st.session_state.confirm_delete_doc = False
                        st.error("Failed to delete document")
                except Exception as e:
                    st.session_state.confirm_delete_doc = False
                    st.error(f"Error deleting document: {str(e)}")
                    logger.error(f"Delete error: {str(e)}", exc_info=True)
            
            # Cancel delete if user selects a different document
            if "last_selected_doc" not in st.session_state:
                st.session_state.last_selected_doc = selected_doc_filename
            
            if st.session_state.last_selected_doc != selected_doc_filename:
                st.session_state.confirm_delete_doc = False
                st.session_state.last_selected_doc = selected_doc_filename
            
            # Reassign action
            if all_active_users and 'reassign_btn' in locals() and reassign_btn and new_owner_obj:
                try:
                    success = document_storage.reassign_document(
                        doc_id, 
                        admin_id, 
                        new_owner_obj['_id']
                    )
                    if success:
                        st.success(f"Document reassigned to {new_owner}!")
                        st.rerun()
                    else:
                        st.error("Failed to reassign document")
                except Exception as e:
                    st.error(f"Error reassigning document: {str(e)}")
                    logger.error(f"Reassign error: {str(e)}", exc_info=True)
    else:
        # If no documents, provide a more helpful message and option to create a sample document
        st.info("No documents found matching the filters. Try adjusting your search criteria or check if documents have been uploaded to the system.")
        
        # Get total document count
        total_docs = document_storage.documents.count_documents({})
        
        if total_docs == 0:
            st.warning("Your system doesn't have any documents yet.")
            
            # Offer to create a sample document for testing
            st.write("Would you like to create a sample document for testing?")
            create_sample = st.button("Create Sample Document", key="create_sample_doc")
            
            if create_sample:
                try:
                    # Create a sample document for the current admin
                    success = document_storage.create_sample_document(admin_id)
                    if success:
                        st.success("Sample document created successfully! Refresh to see it.")
                        time.sleep(1)  # Give a moment for the success message to be seen
                        st.rerun()
                    else:
                        st.error("Failed to create sample document.")
                except Exception as e:
                    st.error(f"Error creating sample document: {str(e)}")
        
        # Add a debug expander for admins
        with st.expander("Debug Info", expanded=False):
            st.markdown("Document query parameters:")
            st.json({
                "admin_id": admin_id,
                "user_filter": selected_user_id if selected_user_id != "all" else "None",
                "date_filter": date_filter,
                "status_filter": status_filter if status_filter != "All" else "None"
            }) 