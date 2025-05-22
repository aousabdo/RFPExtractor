#!/usr/bin/env python3
import streamlit as st
import os
import json
from typing import Dict, Any
import upload_pdf
from rfp_filter import run_filter, SECTIONS  # Your second script
import process_rfp
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Streamlit page configuration
st.set_page_config(
    page_title="RFP Processor",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for styling
st.markdown("""
    <style>
    .main {
        background-color: #f5f5f5;
        padding: 20px;
    }
    .stButton>button {
        background-color: #4CAF50;
        color: white;
        border-radius: 5px;
    }
    .stTextInput>div>input {
        border-radius: 5px;
    }
    .stFileUploader {
        border: 2px dashed #4CAF50;
        border-radius: 5px;
        padding: 10px;
    }
    .section-header {
        color: #2E7D32;
        font-size: 24px;
        margin-top: 20px;
        margin-bottom: 10px;
    }
    .result-box {
        background-color: white;
        padding: 15px;
        border-radius: 5px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        margin-bottom: 15px;
    }
    </style>
""", unsafe_allow_html=True)

def display_results(result: Dict[str, Any]):
    """Display processed RFP results in a formatted way"""
    if not result:
        st.error("No results to display")
        return

    if 'customer' in result:
        st.markdown("<h2 class='section-header'>Customer</h2>", unsafe_allow_html=True)
        st.markdown(f"<div class='result-box'>{result['customer']}</div>", unsafe_allow_html=True)

    if 'scope' in result:
        st.markdown("<h2 class='section-header'>Scope of Work</h2>", unsafe_allow_html=True)
        st.markdown(f"<div class='result-box'>{result['scope']}</div>", unsafe_allow_html=True)

    if 'tasks' in result and result['tasks']:
        st.markdown("<h2 class='section-header'>Major Tasks</h2>", unsafe_allow_html=True)
        for task in result['tasks']:
            st.markdown(f"""
                <div class='result-box'>
                    <strong>{task.get('title', 'Untitled Task')}</strong> (Page {task.get('page', 'N/A')})<br>
                    {task.get('description', 'No description available')}
                </div>
            """, unsafe_allow_html=True)

    if 'requirements' in result and result['requirements']:
        st.markdown("<h2 class='section-header'>Key Requirements</h2>", unsafe_allow_html=True)
        reqs_by_category = {}
        for req in result['requirements']:
            cat = req.get('category', 'General')
            reqs_by_category.setdefault(cat, []).append(req)
        
        for category, reqs in reqs_by_category.items():
            st.markdown(f"<h3>{category}</h3>", unsafe_allow_html=True)
            for req in reqs:
                st.markdown(f"""
                    <div class='result-box'>
                        - (Page {req.get('page', 'N/A')}) {req.get('description', 'No description')}
                    </div>
                """, unsafe_allow_html=True)

    if 'dates' in result and result['dates']:
        st.markdown("<h2 class='section-header'>Key Dates</h2>", unsafe_allow_html=True)
        for date in result['dates']:
            st.markdown(f"""
                <div class='result-box'>
                    - {date.get('event', 'Unnamed Event')}: {date.get('date', 'No date')} 
                    (Page {date.get('page', 'N/A')})
                </div>
            """, unsafe_allow_html=True)

def process_pdf_locally(pdf_path, selected_sections):
    """Process PDF locally when Lambda function is unavailable"""
    try:
        logger.info(f"Processing PDF locally: {pdf_path}")
        st.info("Using local processing as Lambda function is unavailable...")
        
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

def main():
    st.title("📄 RFP Processing Tool")
    st.markdown("Upload a PDF and process it through AWS S3 and Lambda for structured RFP analysis.")

    # Sidebar configuration
    with st.sidebar:
        st.header("Configuration")
        
        # AWS Settings - now hidden and hard-coded
        aws_region = "us-east-1"
        s3_bucket = "my-rfp-bucket"
        s3_key = ""  # Will use the filename if empty
        lambda_url = "https://jc2qj7smmranhdtbxkazthh3hq0ymkih.lambda-url.us-east-1.on.aws/"

        # Section selection
        section_options = list(SECTIONS.keys())
        selected_sections = st.multiselect(
            "Sections to Extract",
            options=section_options,
            default=["all"],
            help="Select specific sections or 'all' for complete analysis"
        )

    # Main content
    uploaded_file = st.file_uploader("Upload RFP PDF", type=["pdf"], accept_multiple_files=False)

    if uploaded_file:
        # Save uploaded file temporarily
        temp_path = f"/tmp/{uploaded_file.name}"
        os.makedirs("/tmp", exist_ok=True)
        with open(temp_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        if st.button("Process PDF"):
            with st.spinner("Processing PDF... This may take a moment."):
                # Upload to S3 and process via Lambda
                try:
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
                            # Try local processing as fallback
                            st.warning("""
                            ⚠️ **Lambda Gateway Error - Using Local Fallback**
                            
                            Cannot connect to the AWS Lambda function. Switching to local processing.
                            Note: This may take longer and require more memory.
                            """)
                            result = process_pdf_locally(temp_path, selected_sections)
                        else:
                            raise e
                    
                    # Clean up temporary file
                    if os.path.exists(temp_path):
                        os.remove(temp_path)

                    if result:
                        st.success("Processing complete!")
                        # If Lambda returns a nested 'result', extract it
                        if isinstance(result, dict) and 'result' in result:
                            display_results(result['result'])
                        else:
                            display_results(result)
                    else:
                        st.error("Failed to process PDF. Check the configuration and try again.")
                except Exception as e:
                    error_message = str(e)
                    if "502 Server Error: Bad Gateway" in error_message:
                        st.error("""
                        🚨 **Lambda Gateway Error**
                        
                        Cannot connect to the AWS Lambda function. This could be due to:
                        - The Lambda function is not active or has been deleted
                        - Your AWS credentials don't have permission to access this function
                        - The Lambda URL is incorrect or has changed
                        
                        Please verify your AWS setup and Lambda function status.
                        """)
                    else:
                        st.error(f"Error processing PDF: {error_message}")
                    
                    if os.path.exists(temp_path):
                        os.remove(temp_path)

if __name__ == "__main__":
    main()