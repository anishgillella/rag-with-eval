FROM python:3.11-slim

WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PIP_NO_CACHE_DIR=1

# Copy requirements
COPY backend/requirements.txt .

# Install dependencies (lightweight without PyTorch)
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY backend/ .

# Expose port
EXPOSE 8000

# Run the app
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
