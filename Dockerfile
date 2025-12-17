FROM python:3.11-slim

WORKDIR /app

# Install debugging utilities
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/

# Create directories for logs and data
RUN mkdir -p /app/logs /app/data

# Default command runs the agent directly
# Render Cron Jobs will execute this on schedule
CMD ["python", "src/main.py"]
