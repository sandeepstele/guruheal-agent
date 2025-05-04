FROM python:3.11-slim

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set environment variables
ENV APP_NAME="FastAPI Boilerplate" \
    APP_DESCRIPTION="FastAPI Boilerplate for Microservices" \
    APP_VERSION="0.1.0" \
    ENVIRONMENT="production" \
    APP_PORT=8000

# Expose the port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
