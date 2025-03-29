# Use official Python image
FROM python:3.10-slim

# Set environment variables
ENV PYTHONUNBUFFERED=True \
    PORT=8080 \
    GOOGLE_APPLICATION_CREDENTIALS=/tmp/gcs_credentials.json

# Install system dependencies required for Google Cloud SDK
RUN apt-get update && apt-get install -y \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set proper permissions for runtime files
RUN chmod a+x /app/main.py

# Expose the port Cloud Run requires
EXPOSE 8080

# Configure entrypoint with proper Gunicorn settings
CMD exec gunicorn --bind :$PORT \
    --workers 2 \
    --threads 8 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
    --preload \
    main:app
