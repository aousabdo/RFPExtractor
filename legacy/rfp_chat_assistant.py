#!/usr/bin/env python3
import streamlit as st
import os
import json
import time
from typing import Dict, Any, List, Optional
from openai import OpenAI
import upload_pdf
from rfp_filter import run_filter, SECTIONS
import process_rfp
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Page configuration
st.set_page_config(
    page_title="RFP Chat Assistant",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "current_rfp" not in st.session_state:
    st.session_state.current_rfp = None
if "rfp_name" not in st.session_state:
    st.session_state.rfp_name = None
if "system_message" not in st.session_state:
    st.session_state.system_message = """You are an expert RFP analyst assistant. You help users understand and analyze Request for Proposals (RFPs).
    Your expertise includes extracting key information, identifying requirements, explaining contract terms, and suggesting strategies for responding to RFPs.
    When answering questions, refer specifically to the content of the uploaded RFP. Be precise and cite page numbers when possible.
    If you don't know or the information is not in the RFP, say so clearly."""

# Try to get API key from environment or let user input it
openai_api_key = os.getenv("OPENAI_API_KEY", "")

# Function to get OpenAI client
def get_openai_client():
    return OpenAI(api_key=st.session_state.openai_api_key)

# Custom CSS for sexy UI
st.markdown("""
    <style>
    /* Main app styling */
    .main {
        background-color: #f8f9fa;
    }
    
    /* Header styling */
    .main-header {
        color: #1e3a8a;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        font-weight: 600;
        margin-bottom: 1rem;
    }
    
    /* Chat containers */
    .chat-message {
        padding: 1.5rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
        display: flex;
        flex-direction: column;
    }
    
    .user-message {
        background-color: #e2e8f0;
        border-left: 5px solid #3b82f6;
    }
    
    .assistant-message {
        background-color: #f1f5f9;
        border-left: 5px solid #14b8a6;
    }
    
    /* RFP info panels */
    .rfp-info-panel {
        background-color: white;
        border-radius: 0.5rem;
        padding: 1.5rem;
        margin: 1rem 0;
        border-top: 4px solid #0ea5e9;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    
    .section-header {
        color: #0369a1;
        font-size: 1.25rem;
        font-weight: 600;
        margin: 1rem 0 0.5rem 0;
        border-bottom: 1px solid #e2e8f0;
        padding-bottom: 0.25rem;
    }
    
    .requirements-category {
        font-weight: 600;
        color: #1e40af;
        margin-top: 0.75rem;
    }
    
    /* Sidebar styling */
    .sidebar .stButton>button {
        background-color: #2563eb;
        color: white;
        border-radius: 0.375rem;
        border: none;
        padding: 0.5rem 1rem;
        width: 100%;
        transition: all 0.2s;
    }
    
    .sidebar .stButton>button:hover {
        background-color: #1d4ed8;
    }
    
    /* File uploader */
    .stFileUploader {
        border: 2px dashed #3b82f6;
        border-radius: 0.5rem;
        padding: 1rem;
    }
    
    /* Chat input */
    .stTextInput>div>div>input {
        border-radius: 1.5rem !important;
        padding: 0.75rem 1.5rem !important;
        border: 1px solid #cbd5e1 !important;
        background-color: white !important;
    }
    
    /* Spinner */
    .stSpinner>div {
        border-color: #3b82f6 !important;
    }
    </style>
""", unsafe_allow_html=True)

def display_rfp_data(rfp_data: Dict[str, Any]):
    """Display the RFP data in a structured way"""
    if not rfp_data:
        st.warning("No RFP data to display.")
        return
    
    st.markdown("<div class='rfp-info-panel'>", unsafe_allow_html=True)
    
    # Customer and Scope sections
    if 'customer' in rfp_data:
        st.markdown(f"<h3 class='section-header'>Customer</h3>", unsafe_allow_html=True)
        st.markdown(f"{rfp_data['customer']}", unsafe_allow_html=True)

    if 'scope' in rfp_data:
        st.markdown(f"<h3 class='section-header'>Scope of Work</h3>", unsafe_allow_html=True)
        st.markdown(f"{rfp_data['scope']}", unsafe_allow_html=True)

    # Tasks section
    if 'tasks' in rfp_data and rfp_data['tasks']:
        st.markdown("<h3 class='section-header'>Major Tasks</h3>", unsafe_allow_html=True)
        for task in rfp_data['tasks']:
            st.markdown(f"""
                <p><strong>{task.get('title', 'Untitled Task')}</strong> (Page {task.get('page', 'N/A')})<br>
                {task.get('description', 'No description available')}</p>
            """, unsafe_allow_html=True)

    # Requirements section
    if 'requirements' in rfp_data and rfp_data['requirements']:
        st.markdown("<h3 class='section-header'>Key Requirements</h3>", unsafe_allow_html=True)
        reqs_by_category = {}
        for req in rfp_data['requirements']:
            cat = req.get('category', 'General')
            reqs_by_category.setdefault(cat, []).append(req)
        
        for category, reqs in reqs_by_category.items():
            st.markdown(f"<p class='requirements-category'>{category}</p>", unsafe_allow_html=True)
            for req in reqs:
                st.markdown(f"""
                    <p>- (Page {req.get('page', 'N/A')}) {req.get('description', 'No description')}</p>
                """, unsafe_allow_html=True)

    # Dates section
    if 'dates' in rfp_data and rfp_data['dates']:
        st.markdown("<h3 class='section-header'>Key Dates</h3>", unsafe_allow_html=True)
        for date in rfp_data['dates']:
            st.markdown(f"""
                <p>- {date.get('event', 'Unnamed Event')}: {date.get('date', 'No date')} 
                (Page {date.get('page', 'N/A')})</p>
            """, unsafe_allow_html=True)
    
    st.markdown("</div>", unsafe_allow_html=True)

def process_pdf_locally(pdf_path, selected_sections):
    """Process PDF locally when Lambda function is unavailable"""
    try:
        logger.info(f"Processing PDF locally: {pdf_path}")
        st.info("Using local processing as Lambda function is unavailable...")
        
        # Save the user's OpenAI API key to environment for the local processor to use
        if "openai_api_key" in st.session_state and st.session_state.openai_api_key:
            os.environ["OPENAI_API_KEY"] = st.session_state.openai_api_key
        else:
            st.error("OpenAI API Key is required for local processing. Please enter it in the sidebar.")
            return None
        
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

def process_uploaded_pdf(uploaded_file, aws_region, s3_bucket, s3_key, lambda_url, selected_sections):
    """Process the uploaded PDF and return structured data"""
    try:
        # Save uploaded file temporarily
        temp_path = f"/tmp/{uploaded_file.name}"
        os.makedirs("/tmp", exist_ok=True)
        with open(temp_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        # Process the PDF
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
                st.warning("""
                ⚠️ **Lambda Gateway Error - Using Local Fallback**
                
                Cannot connect to the AWS Lambda function. Switching to local processing.
                Note: This may take longer and require more memory.
                """)
                # Try local processing as fallback
                result = process_pdf_locally(temp_path, selected_sections)
            else:
                st.error(f"Error processing PDF: {error_message}")
                return None

        # Clean up temporary file
        if os.path.exists(temp_path):
            os.remove(temp_path)

        # Extract result if nested
        if result and isinstance(result, dict) and 'result' in result:
            return result['result']
        return result

    except Exception as e:
        st.error(f"Error processing PDF: {str(e)}")
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return None

def generate_response(prompt: str) -> str:
    """Generate a response using OpenAI based on the prompt and RFP context"""
    try:
        client = get_openai_client()
        
        # Format RFP data for context
        rfp_context = ""
        if st.session_state.current_rfp:
            rfp_context = "RFP Information:\n"
            if 'customer' in st.session_state.current_rfp:
                rfp_context += f"Customer: {st.session_state.current_rfp['customer']}\n\n"
            if 'scope' in st.session_state.current_rfp:
                rfp_context += f"Scope: {st.session_state.current_rfp['scope']}\n\n"
            
            # Add summary of tasks
            if 'tasks' in st.session_state.current_rfp and st.session_state.current_rfp['tasks']:
                rfp_context += "Major Tasks:\n"
                for task in st.session_state.current_rfp['tasks'][:5]:  # Limit to first 5 for brevity
                    rfp_context += f"- {task.get('title', 'Task')}: {task.get('description', 'No description')} (Page {task.get('page', 'N/A')})\n"
                if len(st.session_state.current_rfp['tasks']) > 5:
                    rfp_context += f"... and {len(st.session_state.current_rfp['tasks']) - 5} more tasks\n"
                rfp_context += "\n"
            
            # Add summary of requirements by category
            if 'requirements' in st.session_state.current_rfp and st.session_state.current_rfp['requirements']:
                rfp_context += "Key Requirements:\n"
                reqs_by_category = {}
                for req in st.session_state.current_rfp['requirements']:
                    cat = req.get('category', 'General')
                    reqs_by_category.setdefault(cat, []).append(req)
                
                for category, reqs in reqs_by_category.items():
                    rfp_context += f"{category}:\n"
                    for req in reqs[:3]:  # Limit to first 3 per category
                        rfp_context += f"- {req.get('description', 'No description')} (Page {req.get('page', 'N/A')})\n"
                    if len(reqs) > 3:
                        rfp_context += f"... and {len(reqs) - 3} more requirements in this category\n"
                rfp_context += "\n"
            
            # Add key dates
            if 'dates' in st.session_state.current_rfp and st.session_state.current_rfp['dates']:
                rfp_context += "Key Dates:\n"
                for date in st.session_state.current_rfp['dates'][:5]:  # Limit to first 5
                    rfp_context += f"- {date.get('event', 'Event')}: {date.get('date', 'No date')} (Page {date.get('page', 'N/A')})\n"
                if len(st.session_state.current_rfp['dates']) > 5:
                    rfp_context += f"... and {len(st.session_state.current_rfp['dates']) - 5} more dates\n"
        
        # Create message list for the API call
        messages = [
            {"role": "system", "content": st.session_state.system_message}
        ]
        
        # Add RFP context if available
        if rfp_context:
            messages.append({"role": "system", "content": f"Current RFP being analyzed: {st.session_state.rfp_name}\n\n{rfp_context}"})
        
        # Add conversation history (limited to last 10 messages to avoid token limits)
        for msg in st.session_state.messages[-10:]:
            messages.append({"role": msg["role"], "content": msg["content"]})
        
        # Add the current prompt
        messages.append({"role": "user", "content": prompt})
        
        # Call the API
        response = client.chat.completions.create(
            model="gpt-4o",  # or another appropriate model
            messages=messages,
            temperature=0.7,
            max_tokens=1000
        )
        
        return response.choices[0].message.content
    except Exception as e:
        return f"I apologize, but I encountered an error: {str(e)}"

def main():
    # Sidebar for configuration and PDF upload
    with st.sidebar:
        st.markdown("<h2 style='text-align: center;'>Configuration</h2>", unsafe_allow_html=True)
        
        # OpenAI API key input
        st.markdown("#### OpenAI API Key")
        api_key = st.text_input("Enter your OpenAI API key", value=openai_api_key, type="password")
        if api_key:
            st.session_state.openai_api_key = api_key
        
        st.markdown("<hr>", unsafe_allow_html=True)
        
        # AWS Configuration - now hidden and hard-coded
        aws_region = "us-east-1"
        s3_bucket = "my-rfp-bucket"
        s3_key = ""  # Will use the filename if empty
        lambda_url = "https://jc2qj7smmranhdtbxkazthh3hq0ymkih.lambda-url.us-east-1.on.aws/"
        
        # Sections selection
        st.markdown("#### RFP Sections")
        section_options = list(SECTIONS.keys())
        selected_sections = st.multiselect(
            "Sections to Extract",
            options=section_options,
            default=["all"],
            help="Select specific sections or 'all' for complete analysis"
        )
        
        st.markdown("<hr>", unsafe_allow_html=True)
        
        # PDF Upload Section
        st.markdown("#### Upload New RFP")
        uploaded_file = st.file_uploader("Upload RFP PDF", type=["pdf"], accept_multiple_files=False)
        
        if uploaded_file:
            # Add warning about chat history being cleared
            st.warning("⚠️ Processing a new RFP will clear your current chat history.")
            
            if st.button("Process New RFP"):
                with st.spinner("Processing RFP... This may take a moment."):
                    result = process_uploaded_pdf(
                        uploaded_file, 
                        aws_region, 
                        s3_bucket, 
                        s3_key, 
                        lambda_url, 
                        selected_sections
                    )
                    
                    if result:
                        st.session_state.current_rfp = result
                        st.session_state.rfp_name = uploaded_file.name
                        
                        # Clear previous messages when a new RFP is loaded
                        st.session_state.messages = []
                        
                        # Add system message about new RFP being loaded
                        st.session_state.messages.append({
                            "role": "assistant", 
                            "content": f"✅ New RFP processed: **{uploaded_file.name}**\n\nI've analyzed this RFP and extracted key information. You can now ask me questions about it!"
                        })
                        
                        st.success(f"Successfully processed: {uploaded_file.name}")
                        st.rerun()
    
    # Main content area
    st.markdown("<h1 class='main-header'>💬 RFP Chat Assistant</h1>", unsafe_allow_html=True)
    
    # Show current RFP info if available
    if st.session_state.current_rfp:
        st.markdown(f"<p>Currently analyzing: <strong>{st.session_state.rfp_name}</strong></p>", unsafe_allow_html=True)
        with st.expander("View RFP Analysis", expanded=False):
            display_rfp_data(st.session_state.current_rfp)
    else:
        st.info("👈 Upload an RFP document from the sidebar to begin analysis.")
    
    # Display chat messages
    st.markdown("<div class='chat-container'>", unsafe_allow_html=True)
    for message in st.session_state.messages:
        if message["role"] == "user":
            with st.chat_message("user"):
                st.markdown(message["content"])
        else:
            with st.chat_message("assistant"):
                st.markdown(message["content"])
    st.markdown("</div>", unsafe_allow_html=True)
    
    # Chat input
    if "openai_api_key" in st.session_state and st.session_state.openai_api_key:
        if prompt := st.chat_input("Ask me about this RFP..."):
            # Add user message to chat history
            st.session_state.messages.append({"role": "user", "content": prompt})
            
            # Display user message
            with st.chat_message("user"):
                st.markdown(prompt)
            
            # Generate and display response
            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    response = generate_response(prompt)
                    st.markdown(response)
            
            # Add assistant response to chat history
            st.session_state.messages.append({"role": "assistant", "content": response})
    else:
        st.warning("Please enter your OpenAI API key in the sidebar to enable chat functionality.")

    # Add some spacing at the bottom
    st.markdown("<div style='margin-bottom: 100px;'></div>", unsafe_allow_html=True)

if __name__ == "__main__":
    main() 