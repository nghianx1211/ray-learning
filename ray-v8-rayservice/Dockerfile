# ===============================================================
# Multi-stage Dockerfile for Ray Serve 2.49.0 + VLLM 0.10+
# Optimized for minimal size and performance
# ===============================================================

# ===============================================================
# Stage 1: Builder - Install Python dependencies
# ===============================================================
FROM nvidia/cuda:12.1.0-cudnn8-devel-ubuntu22.04 AS builder

# Build arguments
ARG PYTHON_VERSION=3.10
ARG RAY_VERSION=2.49.0
ARG VLLM_VERSION=0.10.0

# Environment variables for build
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    CUDA_HOME=/usr/local/cuda \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install minimal system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python${PYTHON_VERSION} \
    python${PYTHON_VERSION}-dev \
    python3-pip \
    curl \
    ca-certificates \
    build-essential \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create python symlink
RUN ln -sf /usr/bin/python${PYTHON_VERSION} /usr/bin/python3 \
    && ln -sf /usr/bin/python3 /usr/bin/python

# Upgrade pip, setuptools, wheel (lighter versions)
RUN python -m pip install --no-cache-dir --upgrade \
    pip==24.0 \
    setuptools==69.0.0 \
    wheel==0.42.0

# Copy requirements
WORKDIR /tmp
COPY requirements.txt .

# Install Python packages to /install prefix
# Split installation to cache common dependencies
RUN pip install --no-cache-dir \
    --prefix=/install \
    --no-warn-script-location \
    ray[serve]==2.49.0 \
    && find /install -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# Install vLLM and other dependencies
RUN pip install --no-cache-dir \
    --prefix=/install \
    --no-warn-script-location \
    "vllm>=0.10.0,<0.11.0" \
    "fastapi>=0.115.0" \
    "uvicorn>=0.22.0" \
    "pydantic>=2.0.0,<3.0.0" \
    "rich>=13.0.0,<14.0.0" \
    "pydantic-settings>=2.0.0,<3.0.0" \
    "pyyaml>=6.0.0,<7.0.0" \
    "async-timeout>=4.0.0,<5.0.0"

# Install cloud storage (optional - comment out if not needed to save time)
RUN pip install --no-cache-dir \
    --prefix=/install \
    --no-warn-script-location \
    "google-cloud-storage>=2.10.0,<3.0.0" \
    "boto3>=1.28.0,<2.0.0" || true

# Aggressive cleanup to reduce size
RUN find /install -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true \
    && find /install -type d -name "tests" -exec rm -rf {} + 2>/dev/null || true \
    && find /install -type d -name "test" -exec rm -rf {} + 2>/dev/null || true \
    && find /install -type f -name "*.pyc" -delete \
    && find /install -type f -name "*.pyo" -delete \
    && find /install -name "*.dist-info/RECORD" -delete 2>/dev/null || true \
    && find /install -name "*.dist-info/WHEEL" -delete 2>/dev/null || true

# ===============================================================
# Stage 2: Runtime - Lightweight production image
# ===============================================================
FROM nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04

# Build arguments (redefine for this stage)
ARG PYTHON_VERSION=3.10

# Labels for metadata
LABEL maintainer="Ray VLLM Service"
LABEL description="Lightweight Ray Serve 2.49.0 with VLLM 0.10+ for LLM inference"
LABEL ray.version="2.49.0"
LABEL vllm.version="0.10+"

# Environment variables for runtime
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    # Ray Serve config (optimized for 2.49.0)
    RAY_TMPDIR=/tmp/ray \
    # VLLM config
    VLLM_USE_V1=0 \
    # HuggingFace cache
    TRANSFORMERS_CACHE=/app/cache \
    HF_HOME=/app/cache \
    # Python path - set explicitly
    PYTHONPATH=/app \
    # Add /usr/local/bin to PATH for ray command
    PATH=/usr/local/bin:$PATH \
    # Locale
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

# Install minimal runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python${PYTHON_VERSION} \
    python${PYTHON_VERSION}-distutils \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create python symlink
RUN ln -sf /usr/bin/python${PYTHON_VERSION} /usr/bin/python3 \
    && ln -sf /usr/bin/python3 /usr/bin/python

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

# Create non-root user for security
RUN useradd -m -u 1000 -s /bin/bash rayserve \
    && mkdir -p /app /mnt/models /app/cache /tmp/ray \
    && chown -R rayserve:rayserve /app /mnt/models /app/cache /tmp/ray

# Set working directory
WORKDIR /app

# Copy application code
COPY --chown=rayserve:rayserve . /app/

# Switch to non-root user
USER rayserve

# Expose ports
# 8000: Ray Serve HTTP
# 8265: Ray Dashboard
# 6379: Ray GCS
EXPOSE 8000 8265 6379

# Health check
HEALTHCHECK --interval=30s \
    --timeout=10s \
    --start-period=90s \
    --retries=3 \
    CMD curl -f http://localhost:8000/-/healthz || exit 1

# Default command
CMD ["python", "deploy_app.py", "model_config.yaml"]
