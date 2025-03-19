#!/usr/bin/env python3
"""
This script automatically updates the import statements in all Python files
to match the new project structure.
"""
import os
import re
import sys
from pathlib import Path

# Map of old import statements to new ones
IMPORT_REPLACEMENTS = {
    # Auth related imports
    "import auth_ui": "from rfp_analyzer.app.components import auth_ui",
    "import auth": "from rfp_analyzer.core.auth import user_auth",
    "from auth import UserAuth": "from rfp_analyzer.core.auth.user_auth import UserAuth",
    "from auth_ui import": "from rfp_analyzer.app.components.auth_ui import",
    
    # Storage related imports
    "import document_storage": "from rfp_analyzer.core.storage import document_storage",
    "from document_storage import DocumentStorage": "from rfp_analyzer.core.storage.document_storage import DocumentStorage",
    "import mongodb_connection": "from rfp_analyzer.core.storage import db_connection",
    "from mongodb_connection import get_mongodb_connection": "from rfp_analyzer.core.storage.db_connection import get_mongodb_connection",
    "import document_management_ui": "from rfp_analyzer.app.components import document_ui",
    "from document_management_ui import": "from rfp_analyzer.app.components.document_ui import",
    
    # Processing related imports
    "import process_rfp": "from rfp_analyzer.core.processing import processor",
    "from process_rfp import": "from rfp_analyzer.core.processing.processor import",
    "import rfp_filter": "from rfp_analyzer.core.processing import filters",
    "from rfp_filter import": "from rfp_analyzer.core.processing.filters import",
    
    # AWS related imports
    "import upload_pdf": "from rfp_analyzer.services.aws import s3_service",
    "from upload_pdf import": "from rfp_analyzer.services.aws.s3_service import",
    "import lambda_handler": "from rfp_analyzer.services.aws import lambda_service",
    "from lambda_handler import": "from rfp_analyzer.services.aws.lambda_service import",
    "import test_lambda": "from rfp_analyzer.services.aws import test_lambda",
    
    # Admin panel imports
    "import admin_panel": "from rfp_analyzer.app.components import admin_panel",
    "from admin_panel import": "from rfp_analyzer.app.components.admin_panel import",
}

def update_imports_in_file(file_path):
    """
    Update import statements in a Python file.
    
    Args:
        file_path: Path to the Python file to update
        
    Returns:
        tuple: (number of replacements made, updated content)
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    replacements_made = 0
    
    for old_import, new_import in IMPORT_REPLACEMENTS.items():
        if old_import in content:
            content = content.replace(old_import, new_import)
            replacements_made += content.count(new_import)
    
    return replacements_made, content

def update_all_files():
    """
    Update import statements in all Python files in the refactored project.
    """
    base_path = Path("rfp_analyzer")
    py_files = list(base_path.glob("**/*.py"))
    total_replacements = 0
    total_files_modified = 0
    
    for file_path in py_files:
        replacements, updated_content = update_imports_in_file(file_path)
        
        if replacements > 0:
            total_replacements += replacements
            total_files_modified += 1
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(updated_content)
            print(f"✅ Updated {file_path} ({replacements} replacements)")
        else:
            print(f"ℹ️ No changes needed in {file_path}")
    
    print(f"\nFinished updating imports: {total_replacements} replacements across {total_files_modified} files")

if __name__ == "__main__":
    update_all_files()
