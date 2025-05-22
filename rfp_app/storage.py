import os
import logging
import streamlit as st
from mongodb_connection import get_mongodb_connection
from auth import UserAuth
from document_storage import DocumentStorage

logger = logging.getLogger(__name__)

@st.cache_resource
def init_mongodb_auth():
    """Initialize MongoDB connection and authentication objects."""
    try:
        mongo_client, mongo_db = get_mongodb_connection()
        auth_instance = UserAuth(mongo_db)
        document_storage = DocumentStorage(mongo_db)

        admin_email = os.getenv('ADMIN_EMAIL')
        admin_password = os.getenv('ADMIN_PASSWORD')
        admin_name = os.getenv('ADMIN_NAME', 'System Administrator')
        if admin_email and admin_password:
            auth_instance.create_initial_admin(admin_email, admin_password, admin_name)
        return mongo_client, mongo_db, auth_instance, document_storage
    except Exception as e:
        logger.error(f'Failed to initialize MongoDB and Auth: {str(e)}')
        st.error(f'Database connection error: {str(e)}')
        return None, None, None, None
