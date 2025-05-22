#!/usr/bin/env python3
import os
import uuid
import streamlit as st
from dotenv import load_dotenv

from rfp_app.auth import load_svg_logo
from rfp_app.storage import init_mongodb_auth
from rfp_app.ui import get_colors, load_css, render_app_header, show_no_rfp_screen, display_rfp_data
from rfp_app.chat import openai_api_key, debug_api_key, test_api_key, display_chat_interface
from rfp_app.pdf_processing import process_uploaded_pdf
import auth_ui
import admin_panel

load_dotenv()

# Configure Streamlit page
st.set_page_config(page_title="Enterprise RFP Analyzer", page_icon="🔍", layout="wide", initial_sidebar_state="expanded")

# Initialize database, auth and storage
mongo_client, mongo_db, auth_instance, document_storage = init_mongodb_auth()

# Load logo into session state
if "logo_svg" not in st.session_state:
    st.session_state.logo_svg = load_svg_logo()

# Basic session state defaults
for key, default in {
    "messages": [],
    "current_rfp": None,
    "rfp_name": None,
    "upload_id": str(uuid.uuid4())[:8],
    "system_message": "You are an expert RFP analyst assistant for enterprise clients.",
    "current_document_id": None,
}.items():
    st.session_state.setdefault(key, default)

# Store OpenAI API key from environment if not provided
if "openai_api_key" not in st.session_state:
    st.session_state.openai_api_key = openai_api_key
    if openai_api_key:
        os.environ["OPENAI_API_KEY"] = openai_api_key
        debug_api_key(openai_api_key, "Environment set at startup")


def main_content():
    load_css()
    colors = get_colors()
    render_app_header()

    is_admin = st.session_state.get("user", {}).get("role") == "admin"

    with st.sidebar:
        if is_admin:
            st.markdown("<div class='sidebar-section'><div class='sidebar-section-header'>Admin Controls</div></div>", unsafe_allow_html=True)
            if st.button("🔐 Admin Panel", key="admin_panel_button", use_container_width=True):
                st.session_state.page = "admin"
                st.rerun()
            st.markdown("<div style='margin-bottom: 25px;'></div>", unsafe_allow_html=True)

        st.markdown("""<div class='sidebar-section'><div class='sidebar-section-header'>OpenAI API Settings</div></div>""", unsafe_allow_html=True)
        has_env_api_key = bool(openai_api_key)
        use_own_api_key = st.checkbox("Use my own API key", value=not has_env_api_key)
        if use_own_api_key:
            user_api_key = st.text_input("API Key", value="", type="password")
            if user_api_key:
                st.session_state.openai_api_key = user_api_key
                debug_api_key(user_api_key, "User input in sidebar")
        else:
            if has_env_api_key:
                st.success("Using system API key")
                st.session_state.openai_api_key = openai_api_key
                debug_api_key(openai_api_key, "Environment key set in sidebar")
            else:
                st.error("No system API key found. Please enter your own API key.")

        if st.session_state.get("openai_api_key"):
            os.environ["OPENAI_API_KEY"] = st.session_state.openai_api_key

        if st.button("Test API Key"):
            with st.spinner("Testing API key..."):
                if st.session_state.get("openai_api_key"):
                    ok, msg = test_api_key(st.session_state.openai_api_key)
                    st.success(msg) if ok else st.error(msg)
                else:
                    st.error("No API key available to test")
        st.markdown("<div style='margin-bottom: 25px;'></div>", unsafe_allow_html=True)

        st.markdown("""<div class='sidebar-section'><div class='sidebar-section-header'>Document Upload</div></div>""", unsafe_allow_html=True)
        aws_region = "us-east-1"
        s3_bucket = "my-rfp-bucket"
        s3_key = ""
        lambda_url = "https://jc2qj7smmranhdtbxkazthh3hq0ymkih.lambda-url.us-east-1.on.aws/"
        selected_sections = ["all"]
        uploaded_file = st.file_uploader("", type=["pdf"], accept_multiple_files=False, key=f"uploader_{st.session_state.upload_id}")
        if uploaded_file and st.button("Process RFP", key="process_button"):
            with st.spinner("Analyzing document..."):
                result = process_uploaded_pdf(uploaded_file, aws_region, s3_bucket, s3_key, lambda_url, selected_sections)
                if result:
                    st.session_state.current_rfp = result
                    st.session_state.rfp_name = uploaded_file.name
                    st.session_state.messages = []
                    st.session_state.upload_id = str(uuid.uuid4())[:8]
    if is_admin and st.session_state.get("page") == "admin":
        admin_panel.render_admin_panel(auth_instance, document_storage, colors)
    elif st.session_state.current_rfp:
        display_rfp_data(st.session_state.current_rfp)
        st.subheader("💬 RFP Chat Assistant")
        display_chat_interface()
    else:
        show_no_rfp_screen()


def main():
    if mongo_db is None or auth_instance is None:
        st.error("Failed to connect to the database. Please check your MongoDB configuration.")
        return
    load_css()
    auth_ui.require_auth(auth_instance, get_colors(), main_content)


if __name__ == "__main__":
    main()
