#!/usr/bin/env python3
import streamlit as st
import os
from datetime import datetime
import time
from typing import Dict, Any, List, Optional
import logging
from document_storage import DocumentStorage
from bson.objectid import ObjectId  # Import ObjectId

# Configure logging
logger = logging.getLogger(__name__)

def format_timestamp(timestamp):
    """Format a timestamp for display"""
    if not timestamp:
        return "N/A"
    
    if isinstance(timestamp, str):
        try:
            timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        except ValueError:
            return timestamp
    
    # Get current time for relative formatting
    now = datetime.utcnow()
    delta = now - timestamp
    
    if delta.days > 30:
        return timestamp.strftime("%Y-%m-%d %H:%M")
    elif delta.days > 0:
        return f"{delta.days} days ago"
    elif delta.seconds > 3600:
        return f"{delta.seconds // 3600} hours ago"
    elif delta.seconds > 60:
        return f"{delta.seconds // 60} minutes ago"
    else:
        return "Just now"

def format_file_size(size_bytes):
    """Format file size in bytes to a human-readable format"""
    if size_bytes is None:
        return "Unknown"
    
    if size_bytes < 1024:
        return f"{size_bytes} bytes"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"

def get_status_badge(status):
    """Get a colored badge for a document status"""
    if status == "uploaded":
        return "🔵 Uploaded"
    elif status == "processing":
        return "🟠 Processing"
    elif status == "processed":
        return "🟢 Processed"
    elif status == "error":
        return "🔴 Error"
    else:
        return f"⚪ {status}"

def render_document_management(document_storage: DocumentStorage, colors: Dict[str, str]):
    """
    Render the document management interface
    
    Args:
        document_storage: DocumentStorage instance
        colors: Color scheme dictionary
    """
    # Initialize session state variables for document deletion
    # This ensures it's always initialized when the function runs
    if "pending_delete_doc" not in st.session_state:
        st.session_state.pending_delete_doc = None
    
    st.markdown(f"""
        <h2 style="color: {colors['primary']}">Document Management</h2>
        <p>View and manage your uploaded RFP documents</p>
    """, unsafe_allow_html=True)
    
    # Get user ID from session
    user_id = st.session_state.user.get('user_id')
    if not user_id:
        st.warning("User ID not found in session state. Please log in again.")
        return
    
    # Check if we need to process a deletion
    pending_delete = st.session_state.get("pending_delete_doc", None)
    if pending_delete:
        doc_id = pending_delete
        
        # Showing confirmation dialog
        st.warning(f"Are you sure you want to delete this document?")
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("Yes, Delete", type="primary"):
                with st.spinner("Deleting document..."):
                    print(f"DEBUG: Attempting to delete document {doc_id}")
                    try:
                        # Convert to string just to be safe
                        document_id = str(doc_id)
                        
                        # Try with user_id first
                        success = document_storage.delete_document(document_id, user_id)
                        
                        if not success:
                            # Try without user_id as fallback
                            print(f"DEBUG: First attempt failed, trying without user_id")
                            success = document_storage.delete_document(document_id, None)
                        
                        if success:
                            st.success(f"Document deleted successfully!")
                            # Safely reset the session state
                            st.session_state["pending_delete_doc"] = None
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error(f"Failed to delete document. Please check logs.")
                    except Exception as e:
                        st.error(f"Error: {str(e)}")
                        print(f"ERROR: {str(e)}")
                    
                    # Clear the pending delete regardless of outcome
                    st.session_state["pending_delete_doc"] = None
                    
        with col2:
            if st.button("Cancel"):
                # Safely reset the session state
                st.session_state["pending_delete_doc"] = None
                st.rerun()
    
    # Fetch documents for this user
    documents = document_storage.get_documents_for_user(user_id)
    
    if not documents:
        st.info("You haven't uploaded any documents yet. Upload an RFP document to get started.")
        return
    
    # Render document list
    st.markdown(f"""
        <div style="margin-bottom: 1rem;">
            <span style="color: {colors['text']}; font-weight: 500;">
                {len(documents)} document(s) found
            </span>
        </div>
    """, unsafe_allow_html=True)
    
    # Create a table to display documents
    for doc in documents:
        # Get document information
        doc_id = doc.get("_id")
        filename = doc.get("original_filename", "Unnamed Document")
        uploaded_at = doc.get("uploaded_at")
        status = doc.get("status", "unknown")
        file_size = doc.get("file_size")
        
        # Create a card for each document
        col1, col2, col3 = st.columns([3, 1, 1])
        
        with col1:
            st.markdown(f"""
                <div style="padding: 0.5rem 0;">
                    <div style="font-weight: 500; font-size: 1.1rem;">{filename}</div>
                    <div style="font-size: 0.8rem; color: {colors['text_muted']};">
                        Uploaded: {format_timestamp(uploaded_at)} • Size: {format_file_size(file_size)}
                    </div>
                </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
                <div style="padding: 0.5rem 0; text-align: center;">
                    <div style="font-size: 0.9rem;">{get_status_badge(status)}</div>
                </div>
            """, unsafe_allow_html=True)        
        with col3:
            # Actions column
            col3_1, col3_2, col3_3 = st.columns(3)
            
            with col3_1:
                # View button
                if st.button("👁️", key=f"view_{doc_id}", help="View"):
                    # Set the current RFP to this document's analysis results
                    if doc.get("analysis_results"):
                        st.session_state.current_rfp = doc["analysis_results"]
                        st.session_state.rfp_name = filename
                        st.session_state.current_document_id = doc_id
                        
                        # Clear previous messages when a new RFP is loaded
                        st.session_state.messages = []
                        
                        # Add system message about loaded RFP
                        st.session_state.messages.append({
                            "role": "assistant", 
                            "content": f"✅ Loaded RFP: **{filename}**\n\nI've loaded the analysis for this RFP. You can now ask me questions about it!"
                        })
                        
                        st.rerun()
                    else:
                        st.warning(f"No analysis results available for {filename}")
            
            with col3_2:
                # Download button
                if st.button("⬇️", key=f"download_{doc_id}", help="Download"):
                    with st.spinner("Generating download link..."):
                        url = document_storage.generate_presigned_url(doc_id, user_id)
                        if url:
                            # Open in new tab automatically
                            st.markdown(f"""
                            <script>
                                window.open('{url}', '_blank');
                            </script>
                            <p>Download started. If it doesn't begin automatically, 
                            <a href="{url}" target="_blank">click here</a>.</p>
                            """, unsafe_allow_html=True)
                        else:
                            st.error("Failed to generate download link")
            
            with col3_3:
                # Delete button - now just sets a session state flag
                if st.button("🗑️", key=f"delete_{doc_id}", help="Delete"):
                    if st.session_state.current_document_id == doc_id:
                        st.warning("This document is currently loaded. Please load a different document first.")
                    else:
                        # Make sure the session state is initialized
                        if "pending_delete_doc" not in st.session_state:
                            st.session_state.pending_delete_doc = None
                            
                        # Set the flag for deletion
                        print(f"DEBUG: Setting pending delete for doc {doc_id}")
                        st.session_state.pending_delete_doc = doc_id
                        st.rerun()
        
        # Add a separator between documents
        st.markdown("<hr style='margin: 0.5rem 0; opacity: 0.2;'>", unsafe_allow_html=True)
    
    # Add some spacing at the bottom
    st.markdown("<div style='margin-bottom: 2rem;'></div>", unsafe_allow_html=True)
