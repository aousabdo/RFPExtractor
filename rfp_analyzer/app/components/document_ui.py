#!/usr/bin/env python3
import streamlit as st
import os
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import time
from typing import Dict, Any, List, Optional
import logging
from rfp_analyzer.core.storage.document_storage import DocumentStorage
from bson.objectid import ObjectId  # Import ObjectId
from rfp_analyzer.app.config import COLORS

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

def get_event_icon(event_type):
    """Get an icon for a timeline event"""
    if event_type == "upload":
        return "📤"
    elif event_type == "analysis_start":
        return "🔍"
    elif event_type == "analysis_complete":
        return "✅"
    elif event_type == "error":
        return "❌"
    elif event_type == "view":
        return "👁️"
    elif event_type == "download":
        return "⬇️"
    elif event_type == "category_update":
        return "🏷️"
    else:
        return "📝"

def render_timeline(document_storage, user_id, colors, days=30, limit=50):
    """Render a timeline view of document activities"""
    timeline_data = document_storage.get_document_timeline(user_id, days, limit)
    
    if not timeline_data:
        st.info("No document activity found for the selected time period.")
        return
    
    # Create a more visually appealing timeline
    st.markdown(f"<h3 style='color: {colors['primary']}'>Document Activity Timeline</h3>", unsafe_allow_html=True)
    
    # Date range selector
    col1, col2, col3 = st.columns([2, 2, 2])
    with col1:
        days_options = {"7 days": 7, "14 days": 14, "30 days": 30, "60 days": 60, "90 days": 90}
        selected_days = st.selectbox(
            "Time range", 
            options=list(days_options.keys()),
            index=2  # Default to 30 days
        )
        days = days_options[selected_days]
    
    # Convert to DataFrame for easier manipulation
    df = pd.DataFrame(timeline_data)
    if df.empty:
        st.info("No document activity found for the selected time period.")
        return
    
    # Convert timestamps
    df['formatted_time'] = df['timestamp'].apply(format_timestamp)
    
    # Create timeline visualization using Plotly
    if not df.empty and 'timestamp' in df.columns:
        # Create date column for plotting
        df['date'] = pd.to_datetime(df['timestamp'])
        
        # Group by date and count events
        daily_counts = df.groupby(df['date'].dt.date).size().reset_index(name='count')
        daily_counts['date'] = pd.to_datetime(daily_counts['date'])
        
        # Create activity chart
        fig = px.bar(
            daily_counts, 
            x='date', 
            y='count',
            labels={'date': 'Date', 'count': 'Activities'},
            title=f'Document Activity ({selected_days})',
            color_discrete_sequence=[colors['primary']]
        )
        
        fig.update_layout(
            height=300,
            margin=dict(l=10, r=10, t=40, b=10),
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(
                showgrid=False,
                zeroline=False
            ),
            yaxis=dict(
                showgrid=True,
                gridcolor='rgba(0,0,0,0.1)',
                zeroline=False
            )
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    # List timeline events
    st.markdown(f"<h4>Recent Activities</h4>", unsafe_allow_html=True)
    
    for i, event in enumerate(timeline_data):
        # Get event details
        doc_name = event.get('document_name', 'Unnamed Document')
        event_type = event.get('event_type', 'unknown')
        timestamp = event.get('formatted_time', 'Unknown time')
        status = event.get('status', '')
        details = event.get('details', {})
        
        # Get icon for event type
        icon = get_event_icon(event_type)
        
        # Create card for the event
        st.markdown(f"""
        <div style="
            display: flex;
            margin-bottom: 1rem;
            padding: 1rem;
            border-radius: 8px;
            background-color: white;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            border-left: 4px solid {colors['primary']};
            position: relative;
        ">
            <div style="
                background-color: {colors['primary']}20;
                border-radius: 50%;
                width: 40px;
                height: 40px;
                display: flex;
                align-items: center;
                justify-content: center;
                margin-right: 1rem;
                font-size: 1.2rem;
            ">
                {icon}
            </div>
            <div style="flex-grow: 1;">
                <div style="font-weight: 500; font-size: 1rem;">{doc_name}</div>
                <div style="color: {colors['text_muted']}; font-size: 0.9rem;">
                    {event_type.replace('_', ' ').title()} • {timestamp}
                </div>
                {f'<div style="font-size: 0.85rem; margin-top: 0.5rem;">{get_status_badge(status)}</div>' if status else ''}
            </div>
        </div>
        """, unsafe_allow_html=True)

def render_document_grid(documents, document_storage, colors):
    """Render documents in a grid view"""
    # Add a search box at the top
    doc_search = st.text_input("🔍 Search documents", key="grid_doc_search", placeholder="Search by name or content...")
    
    # Filter documents if search is active
    if doc_search:
        filtered_docs = [doc for doc in documents if doc_search.lower() in doc.get("original_filename", "").lower()]
        if not filtered_docs:
            st.info(f"No documents found matching '{doc_search}'")
        documents = filtered_docs
    
    # Display document count
    st.markdown(f"**Showing {len(documents)} documents**")
    
    # Create a 3-column grid
    cols = st.columns(3)
    
    for i, doc in enumerate(documents):
        # Get document info
        doc_id = doc.get("_id")
        filename = doc.get("original_filename", "Unnamed Document")
        uploaded_at = doc.get("uploaded_at")
        status = doc.get("status", "unknown")
        file_size = doc.get("file_size")
        category = doc.get("category", "")
        
        # Truncate long filenames
        display_name = filename if len(filename) < 30 else filename[:27] + "..."
        
        with cols[i % 3]:
            # Add CSS styling for the card
            st.markdown("""
            <style>
            .document-card-grid {
                background-color: white;
                border-radius: 8px;
                padding: 1rem;
                margin-bottom: 0.75rem;
                box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                border-top: 4px solid var(--primary-color);
                height: 100%;
            }
            </style>
            """, unsafe_allow_html=True)
            
            # Simple card container
            st.markdown('<div class="document-card-grid">', unsafe_allow_html=True)
            
            # Document name
            st.markdown(f"**{display_name}**")
            
            # Status badge
            st.markdown(get_status_badge(status), unsafe_allow_html=True)
            
            # Metadata with improved layout
            uploaded_text = f"📅 {format_timestamp(uploaded_at)}"
            size_text = f"📏 {format_file_size(file_size)}"
            
            st.markdown(f'<span style="font-size: 0.8rem; color: {colors["text_muted"]};">{uploaded_text}<br>{size_text}</span>', unsafe_allow_html=True)
            
            # Actions row
            col1, col2, col3 = st.columns(3)
            
            # Add View/Load button with improved styling
            if status == "processed" and col1.button("👁️", key=f"view_{doc_id}_{i}", help="View/Load Document"):
                load_document(doc_id, document_storage)
            
            # Download button
            if col2.button("⬇️", key=f"download_{doc_id}_{i}", help="Download Document"):
                download_document(doc_id, document_storage)
            
            # Delete button
            if col3.button("🗑️", key=f"delete_{doc_id}_{i}", help="Delete Document"):
                delete_document(doc_id)
            
            st.markdown('</div>', unsafe_allow_html=True)

def view_document(doc, document_storage):
    """Set the current document to view"""
    try:
        if doc.get("analysis_results"):
            doc_id = doc.get("_id")
            filename = doc.get("original_filename", "Unnamed Document")
            
            # Set session state variables for RFP view
            st.session_state.current_rfp = doc["analysis_results"]
            st.session_state.rfp_name = filename
            st.session_state.current_document_id = doc_id
            
            # Clear previous messages when a new RFP is loaded
            if "messages" in st.session_state:
                st.session_state.messages = []
            
            # Add system message about loaded RFP
            if "messages" in st.session_state:
                st.session_state.messages.append({
                    "role": "assistant", 
                    "content": f"✅ Loaded RFP: **{filename}**\n\nI've loaded the analysis for this RFP. You can now ask me questions about it!"
                })
            
            # Add view event to document history
            document_storage.add_document_event(
                document_id=doc_id,
                event_type="view",
                event_details={"viewed_by": st.session_state.user.get('fullname', 'Unknown')}
            )
            
            # Set a flag to indicate document was viewed (instead of using st.rerun())
            st.session_state.document_viewed = True
            
        else:
            st.session_state.view_error = "Cannot view this document - no analysis results found."
    except Exception as e:
        st.session_state.view_error = f"Error viewing document: {str(e)}"

def download_document(doc_id, document_storage):
    """Generate download link for a document"""
    try:
        user_id = st.session_state.user.get('user_id')
        
        # Add download event to document history
        document_storage.add_document_event(
            document_id=doc_id,
            event_type="download",
            event_details={"downloaded_by": st.session_state.user.get('fullname', 'Unknown')}
        )
        
        # Get download URL
        url = document_storage.generate_presigned_url(doc_id, user_id)
        if url:
            # Set the URL in session state for the UI to use
            st.session_state.download_url = url
        else:
            st.session_state.download_error = "Failed to generate download link"
            
    except Exception as e:
        st.session_state.download_error = f"Error generating download link: {str(e)}"

def delete_document(doc_id):
    """Set the document to be deleted"""
    try:
        if "current_document_id" in st.session_state and st.session_state.current_document_id == doc_id:
            st.session_state.delete_error = "This document is currently loaded. Please load a different document first."
        else:
            # Set the pending delete document
            st.session_state.pending_delete_doc = doc_id
    except Exception as e:
        st.session_state.delete_error = f"Error preparing document for deletion: {str(e)}"

def load_document(doc_id, document_storage):
    """Load a document from storage into the current session"""
    try:
        # Retrieve the document
        document = document_storage.get_document_by_id(doc_id)
        
        if not document:
            st.error("Document not found.")
            return
        
        # Check if document has been processed
        if document.get("status") != "processed" or not document.get("analysis_results"):
            st.warning("This document hasn't been fully processed yet. Please wait for processing to complete.")
            return
        
        # Update session state
        st.session_state.current_rfp = document.get("analysis_results")
        st.session_state.rfp_name = document.get("original_filename")
        st.session_state.current_document_id = doc_id
        
        # Add view event to document history
        document_storage.add_document_event(
            doc_id, 
            "view", 
            {"action": "load", "timestamp": datetime.utcnow()}
        )
        
        # Show success message
        st.success(f"Document '{document.get('original_filename')}' loaded successfully!")
        
        # Force a rerun to update the UI
        st.rerun()
        
    except Exception as e:
        logger.error(f"Error loading document: {str(e)}")
        st.error(f"Error loading document: {str(e)}")

def render_document_list(documents, document_storage, colors):
    """Render documents in a list view"""
    # Add a search box at the top
    doc_search = st.text_input("🔍 Search documents", key="list_doc_search", placeholder="Search by name or content...")
    
    # Filter documents if search is active
    if doc_search:
        filtered_docs = [doc for doc in documents if doc_search.lower() in doc.get("original_filename", "").lower()]
        if not filtered_docs:
            st.info(f"No documents found matching '{doc_search}'")
        documents = filtered_docs
    
    # Display document count
    st.markdown(f"**Showing {len(documents)} documents**")
    
    for i, doc in enumerate(documents):
        # Get document info
        doc_id = doc.get("_id")
        filename = doc.get("original_filename", "Unnamed Document")
        uploaded_at = doc.get("uploaded_at")
        status = doc.get("status", "unknown")
        file_size = doc.get("file_size")
        category = doc.get("category", "")
        
        # Format upload date and time more clearly
        upload_date = format_timestamp(uploaded_at)
        
        # Create a card for each document with improved layout
        st.markdown(f"""
        <div style="
            background-color: white;
            border-radius: 8px;
            padding: 1rem;
            margin-bottom: 0.8rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            border-left: 4px solid {colors['primary']};
            position: relative;
        ">
            <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                <div style="flex-grow: 1;">
                    <div style="font-weight: 600; font-size: 1.1rem; margin-bottom: 0.3rem;">{filename}</div>
                    <div style="display: flex; align-items: center; margin-bottom: 0.3rem;">
                        <span style="color: {colors['text_muted']}; font-size: 0.85rem; margin-right: 0.8rem;">
                            <span style="margin-right: 0.3rem;">📅</span> {upload_date}
                        </span>
                        <span style="color: {colors['text_muted']}; font-size: 0.85rem; margin-right: 0.8rem;">
                            <span style="margin-right: 0.3rem;">📏</span> {format_file_size(file_size)}
                        </span>
                        <span>
                            {get_status_badge(status)}
                        </span>
                    </div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Action buttons in a more compact layout
        col1, col2, col3, col4 = st.columns([1, 1, 1, 3])
        
        # Add View/Load button with enhanced styling
        if status == "processed" and col1.button("👁️ View/Load", key=f"view_list_{doc_id}_{i}", use_container_width=True):
            load_document(doc_id, document_storage)
        
        # Download button
        if col2.button("⬇️ Download", key=f"download_list_{doc_id}_{i}", use_container_width=True):
            download_document(doc_id, document_storage)
        
        # Delete button
        if col3.button("🗑️ Delete", key=f"delete_list_{doc_id}_{i}", use_container_width=True):
            delete_document(doc_id)

def render_document_management(document_storage: DocumentStorage, colors: Dict[str, str]):
    """
    Render the enhanced document management interface
    
    Args:
        document_storage: DocumentStorage instance
        colors: Color scheme dictionary
    """
    # Initialize session state variables
    if "pending_delete_doc" not in st.session_state:
        st.session_state.pending_delete_doc = None
    if "doc_view_type" not in st.session_state:
        st.session_state.doc_view_type = "list"
    if "doc_sort_by" not in st.session_state:
        st.session_state.doc_sort_by = "uploaded_at"
    if "doc_sort_order" not in st.session_state:
        st.session_state.doc_sort_order = -1
    if "doc_status_filter" not in st.session_state:
        st.session_state.doc_status_filter = None
    if "doc_date_range" not in st.session_state:
        st.session_state.doc_date_range = None
    if "doc_search_query" not in st.session_state:
        st.session_state.doc_search_query = ""
    if "doc_category" not in st.session_state:
        st.session_state.doc_category = None
    if "doc_view_tab" not in st.session_state:
        st.session_state.doc_view_tab = "library"
    if "download_url" not in st.session_state:
        st.session_state.download_url = None
    
    # Check for document view flag
    if "document_viewed" in st.session_state and st.session_state.document_viewed:
        st.success(f"Document loaded: {st.session_state.rfp_name}")
        st.session_state.document_viewed = False
    
    # Check for document view error
    if "view_error" in st.session_state and st.session_state.view_error:
        st.error(st.session_state.view_error)
        st.session_state.view_error = None
    
    # Check for document download error
    if "download_error" in st.session_state and st.session_state.download_error:
        st.error(st.session_state.download_error)
        st.session_state.download_error = None
    
    # Check for document delete error
    if "delete_error" in st.session_state and st.session_state.delete_error:
        st.warning(st.session_state.delete_error)
        st.session_state.delete_error = None
        
    # Get user ID from session
    user_id = st.session_state.user.get('user_id')
    if not user_id:
        st.warning("User ID not found in session state. Please log in again.")
        return
    
    # Check if we have a download URL to process
    if st.session_state.download_url:
        url = st.session_state.download_url
        # Display download message and link
        st.success("Download link generated")
        # Safer HTML markup for the link
        st.markdown(f"""
        <div style="margin: 10px 0;">
            <a href="{url}" target="_blank" rel="noopener noreferrer" 
               style="background-color: {colors['primary']}; color: white; padding: 6px 12px; 
                     border-radius: 4px; text-decoration: none; font-weight: 500;">
                Download Document
            </a>
        </div>
        <script>
            window.open('{url}', '_blank');
        </script>
        """, unsafe_allow_html=True)
        # Clear the URL after displaying once
        st.session_state.download_url = None
    
    # Check if we need to process a deletion
    pending_delete = st.session_state.get("pending_delete_doc", None)
    if pending_delete:
        doc_id = pending_delete
        
        # Show confirmation dialog
        st.warning(f"Are you sure you want to delete this document? This action cannot be undone.")
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("Yes, Delete", type="primary"):
                with st.spinner("Deleting document..."):
                    success = document_storage.delete_document(doc_id, user_id)
                    
                    if success:
                        st.success(f"Document deleted successfully!")
                        # Reset the session state
                        st.session_state.pending_delete_doc = None
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(f"Failed to delete document. Please check logs.")
                        # Clear the pending delete regardless of outcome
                        st.session_state.pending_delete_doc = None
        
        with col2:
            if st.button("Cancel"):
                # Reset the session state
                st.session_state.pending_delete_doc = None
                st.rerun()
    
    # Create tabs for different document views
    tab1, tab2 = st.tabs(["📚 Document Library", "⏱️ Activity Timeline"])
    
    with tab1:
        # Get document counts by status
        doc_counts = document_storage.get_document_count_by_status(user_id)
        
        # Create document stats at the top
        status_cols = st.columns(5)
        
        with status_cols[0]:
            st.markdown(f"""
            <div style="background-color: white; border-radius: 5px; padding: 10px; text-align: center;">
                <div style="font-size: 1.5rem; font-weight: 600; color: {colors['primary']};">{doc_counts["total"]}</div>
                <div style="font-size: 0.9rem; color: {colors['text_muted']};">Total</div>
            </div>
            """, unsafe_allow_html=True)
            
        with status_cols[1]:
            st.markdown(f"""
            <div style="background-color: white; border-radius: 5px; padding: 10px; text-align: center;">
                <div style="font-size: 1.5rem; font-weight: 600; color: #3b82f6;">{doc_counts.get("uploaded", 0)}</div>
                <div style="font-size: 0.9rem; color: {colors['text_muted']};">Uploaded</div>
            </div>
            """, unsafe_allow_html=True)
            
        with status_cols[2]:
            st.markdown(f"""
            <div style="background-color: white; border-radius: 5px; padding: 10px; text-align: center;">
                <div style="font-size: 1.5rem; font-weight: 600; color: #f59e0b;">{doc_counts.get("processing", 0)}</div>
                <div style="font-size: 0.9rem; color: {colors['text_muted']};">Processing</div>
            </div>
            """, unsafe_allow_html=True)
            
        with status_cols[3]:
            st.markdown(f"""
            <div style="background-color: white; border-radius: 5px; padding: 10px; text-align: center;">
                <div style="font-size: 1.5rem; font-weight: 600; color: #10b981;">{doc_counts.get("processed", 0)}</div>
                <div style="font-size: 0.9rem; color: {colors['text_muted']};">Processed</div>
            </div>
            """, unsafe_allow_html=True)
            
        with status_cols[4]:
            st.markdown(f"""
            <div style="background-color: white; border-radius: 5px; padding: 10px; text-align: center;">
                <div style="font-size: 1.5rem; font-weight: 600; color: #ef4444;">{doc_counts.get("error", 0)}</div>
                <div style="font-size: 0.9rem; color: {colors['text_muted']};">Error</div>
            </div>
            """, unsafe_allow_html=True)
        
        # Get documents for the user based on the current filters
        documents = document_storage.get_documents_for_user(
            user_id=user_id,
            sort_by=st.session_state.doc_sort_by,
            sort_order=st.session_state.doc_sort_order,
            status_filter=st.session_state.doc_status_filter,
            search_query=st.session_state.doc_search_query if st.session_state.doc_search_query else None,
            category=st.session_state.doc_category
        )
        
        # Add filter and search controls
        filter_cols = st.columns([2, 2, 2, 2])
        
        with filter_cols[0]:
            # View type toggle
            view_options = {"List": "list", "Grid": "grid"}
            view_type = st.selectbox(
                "View", 
                options=list(view_options.keys()),
                index=0 if st.session_state.doc_view_type == "list" else 1,
                key="view_type_select"
            )
            st.session_state.doc_view_type = view_options[view_type]
        
        with filter_cols[1]:
            # Sort by dropdown
            sort_options = {
                "Upload Date": "uploaded_at",
                "Name": "original_filename",
                "Size": "file_size",
                "Status": "status"
            }
            sort_by = st.selectbox(
                "Sort by", 
                options=list(sort_options.keys()),
                index=list(sort_options.values()).index(st.session_state.doc_sort_by) 
                      if st.session_state.doc_sort_by in sort_options.values() else 0,
                key="sort_by_select"
            )
            st.session_state.doc_sort_by = sort_options[sort_by]
        
        with filter_cols[2]:
            # Status filter
            status_options = {
                "All": None,
                "Uploaded": "uploaded",
                "Processing": "processing",
                "Processed": "processed",
                "Error": "error"
            }
            status_filter = st.selectbox(
                "Status", 
                options=list(status_options.keys()),
                index=0 if st.session_state.doc_status_filter is None else 
                    list(status_options.values()).index(st.session_state.doc_status_filter) 
                    if st.session_state.doc_status_filter in status_options.values() else 0,
                key="status_filter_select"
            )
            st.session_state.doc_status_filter = status_options[status_filter]
        
        with filter_cols[3]:
            # Search box
            search_query = st.text_input(
                "Search", 
                value=st.session_state.doc_search_query,
                key="doc_search_input"
            )
            if search_query != st.session_state.doc_search_query:
                st.session_state.doc_search_query = search_query
                # Trigger search by rerunning
                st.rerun()
        
        # Show documents based on view type
        st.markdown(f"### Your Documents")
        
        # Check if documents were found
        if not documents:
            # Show a message when no documents are found
            st.info("No documents found. Upload a document to get started or adjust your filters.")
        elif st.session_state.doc_view_type == "grid":
            # Grid view
            render_document_grid(documents, document_storage, colors)
        else:
            # List view
            render_document_list(documents, document_storage, colors)
    
    with tab2:
        # Show timeline
        render_timeline(document_storage, user_id, colors)
    
    # Add some spacing at the bottom
    st.markdown("<div style='margin-bottom: 2rem;'></div>", unsafe_allow_html=True)
