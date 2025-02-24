FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    software-properties-common \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Expose the port Streamlit runs on
EXPOSE 8501

# Set up a non-root user for security
RUN useradd -m appuser
USER appuser

# Command to run the application (can be overridden)
CMD ["streamlit", "run", "rfp_chat_assistant.py", "--server.port=8501", "--server.address=0.0.0.0"] 