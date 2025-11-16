# Build stage
FROM python:3.11-slim as builder

WORKDIR /build

# Copy requirements
COPY backend/requirements.txt .

# Install dependencies to a specific directory
RUN pip install --user --no-cache-dir -r requirements.txt

# Runtime stage
FROM python:3.11-slim

WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PATH=/root/.local/bin:$PATH

# Copy only the installed packages from builder (not the cache)
COPY --from=builder /root/.local /root/.local

# Copy app code
COPY backend/ .

# Expose port
EXPOSE 8000

# Run the app
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
