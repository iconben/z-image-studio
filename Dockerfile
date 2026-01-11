# syntax=docker/dockerfile:1.4
ARG PYTHON_VERSION=3.11-slim-bookworm

# ============================================
# Builder Stage - Install dependencies
# ============================================
FROM python:${PYTHON_VERSION} AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /install

# Copy dependency files first for better layer caching
COPY pyproject.toml uv.lock* ./

# Install Python dependencies
RUN python -m pip install --no-cache-dir \
    accelerate>=1.12.0 \
    diffusers>=0.36.0 \
    fastapi>=0.123.0 \
    peft>=0.18.0 \
    platformdirs>=4.0.0 \
    psutil>=5.9.0 \
    python-multipart>=0.0.20 \
    sdnq>=0.1.3 \
    torchvision>=0.24.1 \
    transformers>=4.57.3 \
    uvicorn>=0.38.0 \
    mcp>=1.23.2

WORKDIR /app
COPY src/ ./src/

# ============================================
# Runtime Stage - Minimal image
# ============================================
FROM python:${PYTHON_VERSION} AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd -r appgroup && useradd -r -g appgroup appuser && \
    mkdir -p /data /outputs && \
    chown -R appuser:appgroup /data /outputs

COPY --from=builder --chown=appuser:appgroup /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder --chown=appuser:appgroup /usr/local/bin /usr/local/bin
COPY --chown=appuser:appgroup src/ /app/src/

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    Z_IMAGE_STUDIO_DATA_DIR=/data \
    Z_IMAGE_STUDIO_OUTPUT_DIR=/data/outputs \
    HOME=/home/appuser \
    PATH=/usr/local/bin:$PATH

WORKDIR /app
USER appuser

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" 2>/dev/null || exit 1

COPY --chown=appuser:appgroup <<'EOF' /entrypoint.sh
#!/bin/bash
set -e

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

install_gpu_pytorch
exec "$@"
EOF
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
CMD ["serve"]
