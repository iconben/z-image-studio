# syntax=docker/dockerfile:1.4
ARG PYTHON_VERSION=3.11-slim-bookworm

# ============================================
# Builder Stage - Build wheel and install
# ============================================
FROM python:${PYTHON_VERSION} AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Copy dependency files first for better layer caching
COPY pyproject.toml uv.lock* ./

# Install build dependencies
RUN python -m pip install --no-cache-dir build

# Copy source code and README for build
COPY src/ ./src/
COPY README.md ./

# Build wheel
RUN python -m build

# Install the wheel
RUN python -m pip install --no-cache-dir --prefix=/install dist/*.whl && \
    rm -rf /root/.cache/pip

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

# Copy scripts from /install/bin and packages from /install
COPY --from=builder --chown=appuser:appgroup /install/bin /usr/local/bin
COPY --from=builder --chown=appuser:appgroup /install/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages

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
CMD ["zimg", "serve"]
