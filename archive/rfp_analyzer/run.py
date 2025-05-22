"""
Entry point for the RFP Analyzer application.
"""
import os
import sys
import streamlit.web.cli as stcli

def main():
    # Add the current directory to the Python path
    sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
    
    # Run the Streamlit app
    sys.argv = ["streamlit", "run", "app/main.py", "--server.port=8501", "--server.address=0.0.0.0"]
    stcli.main()

if __name__ == "__main__":
    main()
