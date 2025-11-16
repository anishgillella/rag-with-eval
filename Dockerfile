# Use Python 3.12 slim base image for better performance
FROM python:3.12-slim

WORKDIR /app

# Set environment variables for memory optimization
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PIP_NO_CACHE_DIR=1
ENV PYTHONHASHSEED=0
# Limit PyTorch threads to reduce memory footprint
ENV OMP_NUM_THREADS=2
ENV MKL_NUM_THREADS=2
ENV NUMEXPR_NUM_THREADS=2
# Pre-allocate minimal memory
ENV PYTORCH_ENABLE_MPS_FALLBACK=1

# Install system dependencies (minimal)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip, setuptools, and wheel
RUN pip install --upgrade pip setuptools wheel

# Create non-root user for security
RUN useradd -m -u 1000 appuser

# Copy requirements
COPY backend/requirements.txt .

# Install Python dependencies with CPU-only PyTorch to reduce image size
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch==2.9.1+cpu && \
    pip install --no-cache-dir -r requirements.txt

# Create necessary directories
RUN mkdir -p /app/logs && chown -R appuser:appuser /app

# Copy app code
COPY --chown=appuser:appuser backend/ .

# Switch to non-root user
USER appuser

# Expose port (use 8080 to match Railway's public networking configuration)
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Run the app with memory limits and optimizations (use PORT env var or default to 8080)
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1", "--loop", "uvloop"]
