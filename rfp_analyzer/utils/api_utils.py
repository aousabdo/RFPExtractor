import os
import logging
from openai import OpenAI

logger = logging.getLogger(__name__)

# Try to get API key from environment or let user input it
def get_env_api_key():
    """Get API key from environment with proper formatting"""
    try:
        # Read directly from .env file to avoid any OS environment variable issues
        with open('.env', 'r') as f:
            for line in f:
                if line.strip() and line.startswith('OPENAI_API_KEY=') and not line.startswith('#'):
                    # Extract everything after the equals sign
                    api_key = line.split('=', 1)[1].strip()
                    print(f"DEBUG - Found API key in .env file with length: {len(api_key)}")
                    return api_key
    except Exception as e:
        print(f"DEBUG - Error reading .env file: {str(e)}")
    
    # Fallback to os.getenv
    api_key = os.getenv("OPENAI_API_KEY", "")
    print(f"DEBUG - Fallback to os.getenv with key length: {len(api_key) if api_key else 0}")
    return api_key

# Add debug logging for API key
def debug_api_key(key, source):
    if key:
        # Only show first 4 and last 4 characters for security
        masked_key = f"{key[:4]}...{key[-4:]}" if len(key) > 8 else "***"
        print(f"DEBUG - API KEY from {source}: {masked_key}, Length: {len(key)}")
    else:
        print(f"DEBUG - API KEY from {source}: Not set or empty")
        

def test_api_key(api_key):
    """Test if the API key is valid by making a small request to OpenAI"""
    if not api_key:
        return False, "No API key provided"
    
    try:
        client = OpenAI(api_key=api_key)
        # Make a minimal API call
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=5
        )
        return True, "API key is valid"
    except Exception as e:
        error_msg = str(e)
        if "quota" in error_msg.lower() or "billing" in error_msg.lower():
            return False, f"API key has quota issues: {error_msg}"
        return False, f"Invalid API key: {error_msg}"
    

# Function to get OpenAI client
def get_openai_client():
    # Use session state API key if available, otherwise fall back to environment key
    api_key = st.session_state.openai_api_key or openai_api_key
    debug_api_key(api_key, "get_openai_client")
    
    # Basic validation to ensure the API key has the expected format
    if not api_key:
        raise ValueError("No OpenAI API key found. Please provide one in the settings.")
    elif not (api_key.startswith('sk-') and len(api_key) > 20):
        print(f"WARNING: API key may have invalid format - length: {len(api_key)}, starts with: {api_key[:5] if len(api_key) >= 5 else api_key}")
    
    return OpenAI(api_key=api_key)