FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    software-properties-common \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Add pymongo and python-dotenv for authentication
RUN pip install --no-cache-dir pymongo python-dotenv

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p /tmp

# Expose port for Streamlit
EXPOSE 8501

# Health check
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Create entrypoint script
RUN echo '#!/bin/bash\n\
streamlit run enterprise_rfp_assistant.py --server.port=8501 --server.address=0.0.0.0\
' > /app/entrypoint.sh && chmod +x /app/entrypoint.sh

# Run the application
ENTRYPOINT ["/app/entrypoint.sh"]