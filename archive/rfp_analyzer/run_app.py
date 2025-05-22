#!/usr/bin/env python3
"""
Simple script to run the RFP Analyzer application.
"""
import streamlit.web.cli as stcli
import sys
import os

# Add the parent directory to the path so we can import rfp_analyzer
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

def main():
    sys.argv = ["streamlit", "run", os.path.join("rfp_analyzer", "app", "main.py")]
    stcli.main()

if __name__ == "__main__":
    main()
