# Use a stable Python version
FROM python:3.11-slim

# Set environment variables
# PYTHONUNBUFFERED=1 ensures logs show up immediately
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies (required for some SQL/Crypto libraries)
RUN apt-get update && apt-get install -y \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all your python files
COPY . .

# Expose the port
EXPOSE 8000

# Command to run the server in production mode
# We point to "server:app" (server.py, object app)
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]