"""
Configuration settings for the RFP Analyzer application.
"""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# OpenAI API configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# MongoDB configuration
MONGODB_URI = os.getenv("MONGODB_URI", "")
MONGODB_DB = os.getenv("MONGODB_DB", "rfp_analyzer")

# AWS configuration
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
S3_BUCKET = os.getenv("S3_BUCKET", "my-rfp-bucket")
LAMBDA_URL = os.getenv("LAMBDA_URL", "https://jc2qj7smmranhdtbxkazthh3hq0ymkih.lambda-url.us-east-1.on.aws/")

# Application settings
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gpt-4o")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
ADMIN_NAME = os.getenv("ADMIN_NAME", "System Administrator")

# UI configuration
COLORS = {
    "primary": "#2563EB",
    "primary_light": "#3B82F6",
    "secondary": "#059669",
    "background": "#F9FAFB",
    "card_bg": "#FFFFFF",
    "sidebar_bg": "#F3F4F6",
    "text": "#111827",
    "text_muted": "#6B7280",
    "border": "#E5E7EB",
    "success": "#10B981",
    "info": "#3B82F6",
    "warning": "#F59E0B",
    "danger": "#EF4444",
    "user_msg_bg": "#DBEAFE",
    "bot_msg_bg": "#F3F4F6"
}
