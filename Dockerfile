# syntax=docker/dockerfile:1.4
ARG PYTHON_VERSION=3.11-slim-bookworm

# ============================================
# Builder Stage - Install dependencies
# ============================================
FROM python:${PYTHON_VERSION} AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency files first for better layer caching
COPY pyproject.toml uv.lock* ./

# Install dependencies from pyproject.toml
RUN uv pip install --system --no-dev --compile .

# Copy source code
COPY src/ ./src/

# ============================================
# Runtime Stage - Minimal image
# ============================================
FROM python:${PYTHON_VERSION} AS runtime

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN groupadd -r appgroup && useradd -r -g appgroup appuser && \
    mkdir -p /data /outputs && \
    chown -R appuser:appgroup /data /outputs

# Copy virtual environment from builder
COPY --from=builder --chown=appuser:appgroup /root/.local /home/appuser/.local
COPY --from=builder --chown=appuser:appgroup /opt/venv /opt/venv

# Copy application source
COPY --chown=appuser:appgroup src/ /app/src/

# Set environment variables
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    Z_IMAGE_STUDIO_DATA_DIR=/data \
    Z_IMAGE_STUDIO_OUTPUT_DIR=/data/outputs \
    HOME=/home/appuser

WORKDIR /app

# Switch to non-root user
USER appuser

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" 2>/dev/null || exit 1

# Entrypoint
COPY --chown=appuser:appgroup <<'EOF' /entrypoint.sh
#!/bin/bash
set -e

# GPU Detection and PyTorch installation
install_gpu_pytorch() {
    if command -v nvidia-smi &> /dev/null; then
        echo "NVIDIA GPU detected, installing CUDA PyTorch..."
        pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cu124 2>/dev/null || true
    elif [ -f /sys/class/drm/card0/device/vendor ] && \
         grep -q "0x1002" /sys/class/drm/card0/device/vendor 2>/dev/null; then
        echo "AMD GPU detected, installing ROCm PyTorch..."
        pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/rocm6.1 2>/dev/null || true
    else
        echo "No GPU detected, using CPU PyTorch"
    fi
}

# Run GPU detection
install_gpu_pytorch

# Run the main command
exec "$@"
EOF
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]

# Default command
CMD ["serve"]
