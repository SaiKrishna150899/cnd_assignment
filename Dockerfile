# Use the official Python image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED True

# Copy application code
COPY . /app
WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Run the web service using gunicorn
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 main:app
