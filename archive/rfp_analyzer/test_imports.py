"""
This script tests that all the imports work correctly after refactoring.
"""
import sys
import os
from importlib import import_module

def test_import(module_name):
    try:
        module = import_module(module_name)
        print(f"✅ Successfully imported {module_name}")
        return True
    except Exception as e:
        print(f"❌ Failed to import {module_name}: {str(e)}")
        return False

modules_to_test = [
    "rfp_analyzer.app.config",
    "rfp_analyzer.core.auth.user_auth",
    "rfp_analyzer.app.components.auth_ui",
    "rfp_analyzer.core.storage.db_connection",
    "rfp_analyzer.core.storage.document_storage",
    "rfp_analyzer.app.components.document_ui",
    "rfp_analyzer.core.processing.processor",
    "rfp_analyzer.core.processing.filters",
    "rfp_analyzer.services.aws.s3_service",
    "rfp_analyzer.services.aws.lambda_service",
    "rfp_analyzer.app.components.admin_panel",
]

def main():
    print("Testing imports for refactored structure...")
    failures = 0
    
    for module in modules_to_test:
        if not test_import(module):
            failures += 1
    
    print(f"\nImport test results: {len(modules_to_test) - failures}/{len(modules_to_test)} modules successfully imported")
    
    if failures > 0:
        print("\nSome imports failed. Please check the errors above.")
        sys.exit(1)
    else:
        print("\nAll imports successful!")
        sys.exit(0)

if __name__ == "__main__":
    main()
